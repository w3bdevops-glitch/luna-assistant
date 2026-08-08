"""Credential catalogue, budgets, rotation and persistent consumption."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store

from ..const import (
    CONF_AUTO_FAILOVER,
    CONF_CREDENTIALS,
    CONF_FAILOVER_ATTEMPTS,
    CONF_FAILOVER_COOLDOWN,
    CONF_PROVIDER_LIMITS,
    CONF_ROTATION_STRATEGY,
    DEFAULT_FAILOVER_ATTEMPTS,
    DEFAULT_FAILOVER_COOLDOWN,
    DEFAULT_ROTATION_STRATEGY,
    PROVIDER_AZURE,
    PROVIDER_GOOGLE,
)
from .models import ProviderCapability, ProviderError

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "luna_assistant_prime_usage"


@dataclass(frozen=True, slots=True)
class CredentialSpec:
    """One provider credential and its local safety budgets."""

    credential_id: str
    provider: str
    name: str
    secret: str
    region: str | None
    priority: int
    enabled: bool
    capabilities: frozenset[ProviderCapability]
    daily_request_limit: int
    monthly_request_limit: int
    monthly_unit_limits: Mapping[str, int]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> CredentialSpec:
        provider = str(raw.get("provider", "")).strip().lower()
        default_capabilities = (
            frozenset(
                {
                    ProviderCapability.AI_TASK,
                    ProviderCapability.CONVERSATION,
                    ProviderCapability.IMAGE,
                    ProviderCapability.STT,
                    ProviderCapability.TTS,
                }
            )
            if provider == PROVIDER_GOOGLE
            else frozenset({ProviderCapability.STT, ProviderCapability.TTS})
        )
        parsed_capabilities: set[ProviderCapability] = set()
        for value in raw.get("capabilities", default_capabilities):
            try:
                parsed_capabilities.add(ProviderCapability(str(value)))
            except ValueError:
                continue
        limits = raw.get("monthly_unit_limits", {})
        if not isinstance(limits, Mapping):
            limits = {}
        return cls(
            credential_id=str(raw.get("id", "")).strip(),
            provider=provider,
            name=str(raw.get("name", "Credencial")).strip() or "Credencial",
            secret=str(raw.get("api_key", "")).strip(),
            region=(str(raw.get("region", "")).strip().lower() or None),
            priority=max(1, int(raw.get("priority", 100))),
            enabled=bool(raw.get("enabled", True)),
            capabilities=frozenset(parsed_capabilities) or default_capabilities,
            daily_request_limit=max(0, int(raw.get("daily_request_limit", 0))),
            monthly_request_limit=max(0, int(raw.get("monthly_request_limit", 0))),
            monthly_unit_limits={
                str(key): max(0, int(value)) for key, value in limits.items()
            },
        )

    def public_dict(self) -> dict[str, Any]:
        """Return diagnostics-safe credential metadata."""
        return {
            "id": self.credential_id,
            "provider": self.provider,
            "name": self.name,
            "region": self.region,
            "priority": self.priority,
            "enabled": self.enabled,
            "capabilities": sorted(item.value for item in self.capabilities),
            "daily_request_limit": self.daily_request_limit,
            "monthly_request_limit": self.monthly_request_limit,
            "monthly_unit_limits": dict(self.monthly_unit_limits),
        }


@dataclass(frozen=True, slots=True)
class CredentialLease:
    """Reserved credential for one provider request."""

    credential: CredentialSpec
    capability: ProviderCapability
    failover: bool


class CredentialManager:
    """Select credentials and enforce local budgets before provider calls."""

    def __init__(
        self,
        hass,
        entry: ConfigEntry,
        credentials: Iterable[Mapping[str, Any]],
        settings: Mapping[str, Any],
    ) -> None:
        self._entry = entry
        self._credentials = tuple(
            credential
            for item in credentials
            if (credential := CredentialSpec.from_dict(item)).credential_id
            and credential.secret
            and credential.provider in {PROVIDER_GOOGLE, PROVIDER_AZURE}
        )
        self._settings = settings
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}_{entry.entry_id}",
        )
        self._usage: dict[str, Any] = {"credentials": {}, "providers": {}}
        self._cooldowns: dict[str, datetime] = {}
        self._round_robin: dict[tuple[str, str], int] = {}
        self._lock = asyncio.Lock()

    @classmethod
    async def async_create(
        cls,
        hass,
        entry: ConfigEntry,
        credentials: Iterable[Mapping[str, Any]],
        settings: Mapping[str, Any],
    ) -> CredentialManager:
        """Create and hydrate persistent usage state."""
        manager = cls.__new__(cls)
        manager._entry = entry
        manager._credentials = tuple(
            credential
            for item in credentials
            if (credential := CredentialSpec.from_dict(item)).credential_id
            and credential.secret
            and credential.provider in {PROVIDER_GOOGLE, PROVIDER_AZURE}
        )
        manager._settings = settings
        manager._store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}_{entry.entry_id}",
        )
        manager._usage = await manager._store.async_load() or {
            "credentials": {},
            "providers": {},
        }
        manager._cooldowns = {}
        manager._round_robin = {}
        manager._lock = asyncio.Lock()
        return manager

    @property
    def auto_failover(self) -> bool:
        return bool(self._settings.get(CONF_AUTO_FAILOVER, True))

    @property
    def failover_attempts(self) -> int:
        return max(
            1,
            min(
                10,
                int(
                    self._settings.get(
                        CONF_FAILOVER_ATTEMPTS, DEFAULT_FAILOVER_ATTEMPTS
                    )
                ),
            ),
        )

    def has_credential(self, provider: str, capability: ProviderCapability) -> bool:
        return any(
            item.enabled
            and item.provider == provider
            and capability in item.capabilities
            for item in self._credentials
        )

    def first(self, provider: str) -> CredentialSpec | None:
        return next(
            (
                item
                for item in self._credentials
                if item.enabled and item.provider == provider
            ),
            None,
        )

    async def async_acquire(
        self,
        provider: str,
        capability: ProviderCapability,
        *,
        excluded: set[str] | None = None,
        failover: bool = False,
    ) -> CredentialLease:
        """Reserve one eligible credential and count the attempted request."""
        excluded = excluded or set()
        async with self._lock:
            now = datetime.now(UTC)
            candidates = [
                item
                for item in self._credentials
                if item.enabled
                and item.provider == provider
                and capability in item.capabilities
                and item.credential_id not in excluded
                and self._cooldowns.get(item.credential_id, now) <= now
                and self._within_limits(item, capability, now)
                and self._provider_within_limits(provider, capability, now)
            ]
            if not candidates:
                raise ProviderError(
                    provider,
                    "budget_or_credentials_exhausted",
                    f"No eligible {provider} credential for {capability.value}",
                )
            selected = self._select(candidates, capability, now)
            self._increment_request(selected, capability, now)
            await self._store.async_save(self._usage)
            return CredentialLease(selected, capability, failover)

    async def async_complete(self, lease: CredentialLease, *, units: int = 0) -> None:
        """Commit measured consumption and clear transient failures."""
        async with self._lock:
            now = datetime.now(UTC)
            self._increment_units(
                lease.credential, lease.capability, max(0, units), now
            )
            self._cooldowns.pop(lease.credential.credential_id, None)
            await self._store.async_save(self._usage)

    async def async_fail(self, lease: CredentialLease, error: ProviderError) -> None:
        """Apply a cooldown after errors that can benefit from another key."""
        if not (
            error.retryable or error.category in {"authentication", "authorization"}
        ):
            return
        seconds = max(
            10,
            int(self._settings.get(CONF_FAILOVER_COOLDOWN, DEFAULT_FAILOVER_COOLDOWN)),
        )
        if error.category in {"authentication", "authorization"}:
            seconds = max(seconds, 3600)
        async with self._lock:
            self._cooldowns[lease.credential.credential_id] = datetime.now(
                UTC
            ) + timedelta(seconds=seconds)

    def _select(
        self,
        candidates: list[CredentialSpec],
        capability: ProviderCapability,
        now: datetime,
    ) -> CredentialSpec:
        strategy = str(
            self._settings.get(CONF_ROTATION_STRATEGY, DEFAULT_ROTATION_STRATEGY)
        )
        if strategy == "round_robin":
            ordered = sorted(candidates, key=lambda item: (item.priority, item.name))
            key = (ordered[0].provider, capability.value)
            index = self._round_robin.get(key, 0) % len(ordered)
            self._round_robin[key] = index + 1
            return ordered[index]
        if strategy == "least_used":
            return min(
                candidates,
                key=lambda item: (
                    self._credential_usage(item, now)["monthly_requests"],
                    item.priority,
                    item.name,
                ),
            )
        return min(
            candidates,
            key=lambda item: (
                item.priority,
                self._credential_usage(item, now)["daily_requests"],
                item.name,
            ),
        )

    @staticmethod
    def _periods(now: datetime) -> tuple[str, str]:
        return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")

    def _usage_bucket(self, collection: str, key: str, now: datetime) -> dict[str, Any]:
        day, month = self._periods(now)
        root = self._usage.setdefault(collection, {})
        bucket = root.setdefault(key, {})
        if bucket.get("day") != day:
            bucket["day"] = day
            bucket["daily_requests"] = 0
        if bucket.get("month") != month:
            bucket["month"] = month
            bucket["monthly_requests"] = 0
            bucket["monthly_units"] = {}
        bucket.setdefault("daily_requests", 0)
        bucket.setdefault("monthly_requests", 0)
        bucket.setdefault("monthly_units", {})
        return bucket

    def _credential_usage(self, item: CredentialSpec, now: datetime) -> dict[str, Any]:
        return self._usage_bucket("credentials", item.credential_id, now)

    def _provider_usage(self, provider: str, now: datetime) -> dict[str, Any]:
        return self._usage_bucket("providers", provider, now)

    def _within_limits(
        self, item: CredentialSpec, capability: ProviderCapability, now: datetime
    ) -> bool:
        usage = self._credential_usage(item, now)
        unit_limit = int(item.monthly_unit_limits.get(capability.value, 0))
        total_unit_limit = int(item.monthly_unit_limits.get("*", 0))
        total_units = sum(int(value) for value in usage["monthly_units"].values())
        return (
            (
                not item.daily_request_limit
                or usage["daily_requests"] < item.daily_request_limit
            )
            and (
                not item.monthly_request_limit
                or usage["monthly_requests"] < item.monthly_request_limit
            )
            and (
                not unit_limit
                or int(usage["monthly_units"].get(capability.value, 0)) < unit_limit
            )
            and (not total_unit_limit or total_units < total_unit_limit)
        )

    def _provider_within_limits(
        self, provider: str, capability: ProviderCapability, now: datetime
    ) -> bool:
        raw_limits = self._settings.get(CONF_PROVIDER_LIMITS, {})
        limits = raw_limits.get(provider, {}) if isinstance(raw_limits, Mapping) else {}
        usage = self._provider_usage(provider, now)
        unit_limits = limits.get("monthly_unit_limits", {})
        unit_limit = (
            int(unit_limits.get(capability.value, 0))
            if isinstance(unit_limits, Mapping)
            else 0
        )
        total_unit_limit = (
            int(unit_limits.get("*", 0)) if isinstance(unit_limits, Mapping) else 0
        )
        total_units = sum(int(value) for value in usage["monthly_units"].values())
        return (
            (
                not int(limits.get("daily_request_limit", 0))
                or usage["daily_requests"] < int(limits["daily_request_limit"])
            )
            and (
                not int(limits.get("monthly_request_limit", 0))
                or usage["monthly_requests"] < int(limits["monthly_request_limit"])
            )
            and (
                not unit_limit
                or int(usage["monthly_units"].get(capability.value, 0)) < unit_limit
            )
            and (not total_unit_limit or total_units < total_unit_limit)
        )

    def _increment_request(
        self, item: CredentialSpec, capability: ProviderCapability, now: datetime
    ) -> None:
        for collection, key in (
            ("credentials", item.credential_id),
            ("providers", item.provider),
        ):
            bucket = self._usage_bucket(collection, key, now)
            bucket["daily_requests"] += 1
            bucket["monthly_requests"] += 1

    def _increment_units(
        self,
        item: CredentialSpec,
        capability: ProviderCapability,
        units: int,
        now: datetime,
    ) -> None:
        for collection, key in (
            ("credentials", item.credential_id),
            ("providers", item.provider),
        ):
            bucket = self._usage_bucket(collection, key, now)
            monthly = bucket["monthly_units"]
            monthly[capability.value] = int(monthly.get(capability.value, 0)) + units

    def diagnostics(self) -> dict[str, Any]:
        """Return consumption and budgets without secrets."""
        now = datetime.now(UTC)
        return {
            "rotation_strategy": self._settings.get(
                CONF_ROTATION_STRATEGY, DEFAULT_ROTATION_STRATEGY
            ),
            "auto_failover": self.auto_failover,
            "failover_attempts": self.failover_attempts,
            "credentials": [
                {
                    **item.public_dict(),
                    "usage": dict(self._credential_usage(item, now)),
                    "cooldown_until": (
                        self._cooldowns[item.credential_id].isoformat()
                        if item.credential_id in self._cooldowns
                        else None
                    ),
                }
                for item in self._credentials
            ],
            "provider_usage": {
                provider: dict(self._provider_usage(provider, now))
                for provider in {item.provider for item in self._credentials}
            },
        }


def credentials_from_entry(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Return central credentials, migrating legacy fields in memory."""
    configured = entry.options.get(CONF_CREDENTIALS) or entry.data.get(CONF_CREDENTIALS)
    if isinstance(configured, list) and configured:
        return [dict(item) for item in configured if isinstance(item, Mapping)]

    from homeassistant.const import CONF_API_KEY

    from ..const import CONF_AZURE_REGION, CONF_AZURE_SPEECH_KEY, DEFAULT_AZURE_REGION

    result: list[dict[str, Any]] = []
    google_key = str(entry.data.get(CONF_API_KEY, "")).strip()
    if google_key:
        result.append(
            {
                "id": "google-primary",
                "provider": PROVIDER_GOOGLE,
                "name": "Google principal",
                "api_key": google_key,
                "priority": 1,
                "enabled": True,
            }
        )
    seen_azure: set[tuple[str, str]] = set()
    for index, subentry in enumerate(entry.subentries.values(), start=1):
        key = str(subentry.data.get(CONF_AZURE_SPEECH_KEY, "")).strip()
        region = str(subentry.data.get(CONF_AZURE_REGION, DEFAULT_AZURE_REGION)).strip()
        if not key or (key, region) in seen_azure:
            continue
        seen_azure.add((key, region))
        result.append(
            {
                "id": f"azure-legacy-{index}",
                "provider": PROVIDER_AZURE,
                "name": f"Azure {region}",
                "api_key": key,
                "region": region,
                "priority": index,
                "enabled": True,
            }
        )
    return result
