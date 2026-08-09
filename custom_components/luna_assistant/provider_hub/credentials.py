"""Provider catalog, API-key balance rotation and asynchronous usage metering."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store

from ..const import (
    CONF_AUTO_FAILOVER,
    CONF_CREDENTIALS,
    CONF_FAILOVER_ATTEMPTS,
    CONF_FAILOVER_COOLDOWN,
    CONF_PROVIDER_INSTANCES,
    CONF_PROVIDER_LIMITS,
    CONF_PROVIDERS,
    CONF_ROUTES,
    DEFAULT_FAILOVER_ATTEMPTS,
    DEFAULT_FAILOVER_COOLDOWN,
    DEFAULT_PROVIDER_ROUTES,
    DEFAULT_ROTATION_STRATEGY,
    PROVIDER_AZURE,
    PROVIDER_CAPABILITIES,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_GOOGLE,
    PROVIDER_TAVILY,
)
from .models import ProviderCapability, ProviderError

STORAGE_VERSION = 2
STORAGE_KEY_PREFIX = "luna_assistant_prime_usage"
PERSIST_DELAY_SECONDS = 2.0
SUPPORTED_PROVIDERS = (PROVIDER_GOOGLE, PROVIDER_AZURE, PROVIDER_TAVILY)


def _provider_defaults(provider: str) -> dict[str, Any]:
    return {
        "name": PROVIDER_DISPLAY_NAMES[provider],
        "enabled": True,
        "capabilities": list(PROVIDER_CAPABILITIES[provider]),
        "rotation_strategy": DEFAULT_ROTATION_STRATEGY,
        "max_attempts": 0,
        "cooldown_seconds": DEFAULT_FAILOVER_COOLDOWN,
        "limits": {
            "daily_request_limit": 0,
            "monthly_request_limit": 0,
            "monthly_unit_limits": {},
        },
        "credentials": [],
    }


@dataclass(frozen=True, slots=True)
class CredentialSpec:
    """One API key owned by exactly one provider."""

    credential_id: str
    provider: str
    name: str
    secret: str
    region: str | None
    priority: int
    enabled: bool
    capabilities: frozenset[ProviderCapability]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> CredentialSpec:
        provider = str(raw.get("provider", "")).strip().lower()
        parsed: set[ProviderCapability] = set()
        for value in raw.get("capabilities", PROVIDER_CAPABILITIES.get(provider, ())):
            try:
                parsed.add(ProviderCapability(str(value)))
            except ValueError:
                continue
        return cls(
            credential_id=str(raw.get("id", "")).strip(),
            provider=provider,
            name=str(raw.get("name", "API key")).strip() or "API key",
            secret=str(raw.get("api_key", "")).strip(),
            region=str(raw.get("region", "")).strip().lower() or None,
            priority=max(1, int(raw.get("priority", 100))),
            enabled=bool(raw.get("enabled", True)),
            capabilities=frozenset(parsed),
        )

    def public_dict(self) -> dict[str, Any]:
        """Return diagnostics metadata without revealing the secret."""
        suffix = self.secret[-4:] if len(self.secret) >= 4 else ""
        return {
            "id": self.credential_id,
            "provider": self.provider,
            "name": self.name,
            "masked_key": f"••••{suffix}" if suffix else "configured",
            "region": self.region,
            "enabled": self.enabled,
            "capabilities": sorted(item.value for item in self.capabilities),
        }


@dataclass(frozen=True, slots=True)
class CredentialLease:
    """An in-memory reservation made before a provider request."""

    credential: CredentialSpec
    capability: ProviderCapability
    failover: bool
    reserved_units: int = 0


class CredentialManager:
    """Select the highest-balance key and meter usage outside the critical path."""

    def __init__(
        self,
        hass,
        entry: ConfigEntry,
        credentials: Iterable[Mapping[str, Any]],
        settings: Mapping[str, Any],
    ) -> None:
        self._initialize(hass, entry, credentials, settings)

    def _initialize(
        self,
        hass,
        entry: ConfigEntry,
        credentials: Iterable[Mapping[str, Any]],
        settings: Mapping[str, Any],
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._settings = settings
        configured = settings.get(CONF_PROVIDERS, {})
        self._providers = (
            deepcopy(configured)
            if isinstance(configured, Mapping)
            else default_providers()
        )
        self._credentials = tuple(
            credential
            for item in credentials
            if (credential := CredentialSpec.from_dict(item)).credential_id
            and credential.secret
            and credential.provider in SUPPORTED_PROVIDERS
        )
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry.entry_id}"
        )
        self._usage: dict[str, Any] = {"credentials": {}, "providers": {}}
        self._cooldowns: dict[str, datetime] = {}
        self._last_errors: dict[str, dict[str, Any]] = {}
        self._round_robin: dict[tuple[str, str], int] = {}
        self._last_selected: dict[tuple[str, str], str] = {}
        self._reserved_units: dict[tuple[str, str], int] = {}
        self._lock = asyncio.Lock()
        self._persist_task: asyncio.Task | None = None
        self._attempt_budget: ContextVar[dict[str, int] | None] = ContextVar(
            f"luna_attempt_budget_{entry.entry_id}", default=None
        )

    @classmethod
    async def async_create(
        cls,
        hass,
        entry: ConfigEntry,
        credentials: Iterable[Mapping[str, Any]],
        settings: Mapping[str, Any],
    ) -> CredentialManager:
        manager = cls.__new__(cls)
        manager._initialize(hass, entry, credentials, settings)
        loaded = await manager._store.async_load()
        if isinstance(loaded, Mapping):
            manager._usage = {
                "credentials": dict(loaded.get("credentials", {})),
                "providers": dict(loaded.get("providers", {})),
            }
        return manager

    @property
    def auto_failover(self) -> bool:
        return bool(self._settings.get(CONF_AUTO_FAILOVER, True))

    @property
    def failover_attempts(self) -> int:
        configured = int(
            self._settings.get(CONF_FAILOVER_ATTEMPTS, DEFAULT_FAILOVER_ATTEMPTS)
        )
        return 1000 if configured <= 0 else min(1000, configured)

    def provider_attempts(self, provider: str) -> int:
        configured = int(self._provider(provider).get("max_attempts", 0))
        return self.failover_attempts if configured <= 0 else min(1000, configured)

    @contextmanager
    def call_scope(self) -> Iterator[None]:
        """Apply the global attempt budget to one routed operation."""
        token = self._attempt_budget.set({"used": 0, "limit": self.failover_attempts})
        try:
            yield
        finally:
            self._attempt_budget.reset(token)

    def _provider(self, provider: str) -> Mapping[str, Any]:
        raw = self._providers.get(provider, {})
        return raw if isinstance(raw, Mapping) else {}

    def provider_enabled(self, provider: str) -> bool:
        return bool(self._provider(provider).get("enabled", False))

    def provider_supports(self, provider: str, capability: ProviderCapability) -> bool:
        return self.provider_enabled(provider) and capability.value in set(
            self._provider(provider).get("capabilities", ())
        )

    def has_credential(self, provider: str, capability: ProviderCapability) -> bool:
        return self.provider_supports(provider, capability) and any(
            item.enabled
            and item.provider == provider
            and capability in item.capabilities
            for item in self._credentials
        )

    def available_providers(
        self, capability: ProviderCapability | None = None
    ) -> list[str]:
        return [
            provider
            for provider in SUPPORTED_PROVIDERS
            if self.provider_enabled(provider)
            and (capability is None or self.has_credential(provider, capability))
        ]

    def route_for(self, capability: ProviderCapability) -> list[str]:
        routes = self._settings.get(CONF_ROUTES, DEFAULT_PROVIDER_ROUTES)
        configured = (
            routes.get(capability.value, []) if isinstance(routes, Mapping) else []
        )
        route = [
            str(provider)
            for provider in configured
            if str(provider) in SUPPORTED_PROVIDERS
            and self.has_credential(str(provider), capability)
        ]
        if not route:
            route = [
                provider
                for provider in DEFAULT_PROVIDER_ROUTES.get(capability.value, [])
                if self.has_credential(provider, capability)
            ]
        return route

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
        estimated_units: int = 0,
    ) -> CredentialLease:
        """Reserve the eligible API key with the greatest estimated balance."""
        excluded = excluded or set()
        async with self._lock:
            now = datetime.now(UTC)
            budget = self._attempt_budget.get()
            if budget is not None and budget["used"] >= budget["limit"]:
                raise ProviderError(
                    provider,
                    "attempt_limit",
                    "The maximum number of attempts for this operation was reached",
                )
            if not self.provider_supports(provider, capability):
                raise ProviderError(
                    provider,
                    "unsupported_or_disabled",
                    f"{provider} is disabled for {capability.value}",
                )
            candidates = [
                item
                for item in self._credentials
                if item.enabled
                and item.provider == provider
                and capability in item.capabilities
                and item.credential_id not in excluded
                and self._cooldowns.get(item.credential_id, now) <= now
                and self._credential_within_inherited_limits(item, capability, now)
            ]
            if not self._provider_within_limits(provider, capability, now):
                candidates = []
            if not candidates:
                raise ProviderError(
                    provider,
                    "budget_or_credentials_exhausted",
                    f"No eligible API key in {provider} for {capability.value}",
                )
            selected = self._select(candidates, capability, now)
            if budget is not None:
                budget["used"] += 1
            reservation = max(0, int(estimated_units))
            if reservation:
                key = (selected.credential_id, capability.value)
                self._reserved_units[key] = (
                    self._reserved_units.get(key, 0) + reservation
                )
            self._increment_request(selected, now)
            lease = CredentialLease(selected, capability, failover, reservation)
        await self._queue_persist()
        return lease

    async def async_complete(self, lease: CredentialLease, *, units: int = 0) -> None:
        """Replace the provisional reservation with measured provider usage."""
        async with self._lock:
            self._release_reservation(lease)
            self._increment_units(
                lease.credential,
                lease.capability,
                max(0, int(units)),
                datetime.now(UTC),
            )
            self._cooldowns.pop(lease.credential.credential_id, None)
        await self._queue_persist()

    async def async_fail(self, lease: CredentialLease, error: ProviderError) -> None:
        """Release a reservation, record the error and cool down only that key."""
        async with self._lock:
            self._release_reservation(lease)
            self._last_errors[lease.credential.credential_id] = {
                "category": error.category,
                "status": error.status,
                "at": datetime.now(UTC).isoformat(),
            }
            if error.retryable or error.category in {"authentication", "authorization"}:
                seconds = max(
                    10,
                    int(
                        self._provider(lease.credential.provider).get(
                            "cooldown_seconds",
                            self._settings.get(
                                CONF_FAILOVER_COOLDOWN, DEFAULT_FAILOVER_COOLDOWN
                            ),
                        )
                    ),
                )
                if error.category in {"authentication", "authorization"}:
                    seconds = max(seconds, 3600)
                self._cooldowns[lease.credential.credential_id] = datetime.now(
                    UTC
                ) + timedelta(seconds=seconds)

    def _release_reservation(self, lease: CredentialLease) -> None:
        if not lease.reserved_units:
            return
        key = (lease.credential.credential_id, lease.capability.value)
        remaining = self._reserved_units.get(key, 0) - lease.reserved_units
        if remaining > 0:
            self._reserved_units[key] = remaining
        else:
            self._reserved_units.pop(key, None)

    def _select(
        self,
        candidates: list[CredentialSpec],
        capability: ProviderCapability,
        now: datetime,
    ) -> CredentialSpec:
        provider = candidates[0].provider
        strategy = str(
            self._provider(provider).get("rotation_strategy", DEFAULT_ROTATION_STRATEGY)
        )
        ordered = sorted(candidates, key=lambda item: (item.priority, item.name))
        key = (provider, capability.value)
        if strategy == "round_robin":
            index = self._round_robin.get(key, 0) % len(ordered)
            self._round_robin[key] = index + 1
            return ordered[index]

        scores = {
            item.credential_id: self._balance_score(item, capability, now)
            for item in ordered
        }
        highest = max(scores.values())
        tied = [item for item in ordered if scores[item.credential_id] == highest]
        last_id = self._last_selected.get(key)
        if last_id is None:
            selected = tied[0]
        else:
            last_index = next(
                (
                    index
                    for index, item in enumerate(ordered)
                    if item.credential_id == last_id
                ),
                -1,
            )
            after = ordered[last_index + 1 :] + ordered[: last_index + 1]
            selected = next(
                item for item in after if item.credential_id in scores and item in tied
            )
        self._last_selected[key] = selected.credential_id
        return selected

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

    def _limits(self, provider: str) -> Mapping[str, Any]:
        limits = self._provider(provider).get("limits", {})
        return limits if isinstance(limits, Mapping) else {}

    def _unit_limit(self, provider: str, capability: ProviderCapability) -> int:
        units = self._limits(provider).get("monthly_unit_limits", {})
        if not isinstance(units, Mapping):
            return 0
        return max(0, int(units.get(capability.value, units.get("*", 0))))

    def _balance_score(
        self, item: CredentialSpec, capability: ProviderCapability, now: datetime
    ) -> float:
        """Return the smallest remaining fraction across active inherited limits."""
        usage = self._credential_usage(item, now)
        limits = self._limits(item.provider)
        values: list[float] = []
        for used, limit in (
            (usage["daily_requests"], int(limits.get("daily_request_limit", 0))),
            (usage["monthly_requests"], int(limits.get("monthly_request_limit", 0))),
            (
                int(usage["monthly_units"].get(capability.value, 0))
                + self._reserved_units.get((item.credential_id, capability.value), 0),
                self._unit_limit(item.provider, capability),
            ),
        ):
            if limit > 0:
                values.append(max(0.0, (limit - int(used)) / limit))
        return min(values) if values else 1.0

    def _credential_within_inherited_limits(
        self, item: CredentialSpec, capability: ProviderCapability, now: datetime
    ) -> bool:
        return self._balance_score(item, capability, now) > 0

    def _provider_within_limits(
        self, provider: str, capability: ProviderCapability, now: datetime
    ) -> bool:
        usage = self._provider_usage(provider, now)
        limits = self._limits(provider)
        unit_limit = self._unit_limit(provider, capability)
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
        )

    def _increment_request(self, item: CredentialSpec, now: datetime) -> None:
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
            monthly = self._usage_bucket(collection, key, now)["monthly_units"]
            monthly[capability.value] = int(monthly.get(capability.value, 0)) + units

    async def _queue_persist(self) -> None:
        """Debounce disk writes on Home Assistant; keep test fallbacks deterministic."""
        if hasattr(self._hass, "async_create_task"):
            if self._persist_task is None or self._persist_task.done():
                self._persist_task = self._hass.async_create_task(
                    self._async_delayed_persist(),
                    name=f"luna_usage_persist_{self._entry.entry_id}",
                )
            return
        await self._store.async_save(deepcopy(self._usage))

    async def _async_delayed_persist(self) -> None:
        await asyncio.sleep(PERSIST_DELAY_SECONDS)
        async with self._lock:
            snapshot = deepcopy(self._usage)
        await self._store.async_save(snapshot)

    async def async_close(self) -> None:
        """Flush usage during config-entry unload."""
        if self._persist_task and not self._persist_task.done():
            self._persist_task.cancel()
        async with self._lock:
            snapshot = deepcopy(self._usage)
        await self._store.async_save(snapshot)

    def diagnostics(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        credentials = []
        for item in self._credentials:
            usage = dict(self._credential_usage(item, now))
            credentials.append(
                {
                    **item.public_dict(),
                    "usage": usage,
                    "balance_percent": round(
                        self._balance_score(item, next(iter(item.capabilities)), now)
                        * 100,
                        2,
                    )
                    if item.capabilities
                    else None,
                    "cooldown_until": (
                        self._cooldowns[item.credential_id].isoformat()
                        if item.credential_id in self._cooldowns
                        else None
                    ),
                    "last_error": self._last_errors.get(item.credential_id),
                }
            )
        return {
            "auto_failover": self.auto_failover,
            "maximum_total_attempts": self.failover_attempts,
            "routes": {
                capability.value: self.route_for(capability)
                for capability in ProviderCapability
            },
            "providers": {
                provider: {
                    "enabled": self.provider_enabled(provider),
                    "capabilities": list(
                        self._provider(provider).get("capabilities", ())
                    ),
                    "rotation_strategy": self._provider(provider).get(
                        "rotation_strategy", DEFAULT_ROTATION_STRATEGY
                    ),
                    "limits": deepcopy(self._limits(provider)),
                    "usage": dict(self._provider_usage(provider, now)),
                    "credential_count": sum(
                        item.enabled and item.provider == provider
                        for item in self._credentials
                    ),
                }
                for provider in SUPPORTED_PROVIDERS
            },
            "credentials": credentials,
            "persistence": "asynchronous_debounced",
        }


def default_providers() -> dict[str, dict[str, Any]]:
    return {provider: _provider_defaults(provider) for provider in SUPPORTED_PROVIDERS}


def providers_from_entry(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    """Read v1.2 providers or merge legacy instances into one provider each."""
    configured = entry.options.get(CONF_PROVIDERS) or entry.data.get(CONF_PROVIDERS)
    if isinstance(configured, Mapping):
        result = default_providers()
        for provider in SUPPORTED_PROVIDERS:
            raw = configured.get(provider)
            if isinstance(raw, Mapping):
                result[provider].update(deepcopy(dict(raw)))
                result[provider]["credentials"] = [
                    dict(item)
                    for item in raw.get("credentials", [])
                    if isinstance(item, Mapping)
                ]
        return result

    result = default_providers()
    legacy_instances = entry.options.get(CONF_PROVIDER_INSTANCES) or entry.data.get(
        CONF_PROVIDER_INSTANCES
    )
    if isinstance(legacy_instances, list):
        for instance in legacy_instances:
            if not isinstance(instance, Mapping):
                continue
            provider = str(instance.get("adapter", "")).strip().lower()
            if provider not in result:
                continue
            target = result[provider]
            target["enabled"] = bool(instance.get("enabled", True)) or bool(
                target.get("enabled")
            )
            target["capabilities"] = sorted(
                set(target.get("capabilities", ()))
                | set(instance.get("capabilities", ()))
            )
            if isinstance(instance.get("limits"), Mapping):
                target["limits"] = deepcopy(dict(instance["limits"]))
            target["credentials"].extend(
                dict(item)
                for item in instance.get("credentials", [])
                if isinstance(item, Mapping)
            )

    legacy_credentials = entry.options.get(CONF_CREDENTIALS) or entry.data.get(
        CONF_CREDENTIALS
    )
    if isinstance(legacy_credentials, list):
        for item in legacy_credentials:
            if not isinstance(item, Mapping):
                continue
            provider = str(item.get("provider", "")).strip().lower()
            if provider in result:
                candidate = {
                    key: value
                    for key, value in item.items()
                    if not key.startswith("provider_instance_")
                    and key not in {"provider", "capabilities"}
                }
                if not any(
                    existing.get("id") == candidate.get("id")
                    for existing in result[provider]["credentials"]
                ):
                    result[provider]["credentials"].append(candidate)

    from homeassistant.const import CONF_API_KEY

    google_key = str(entry.data.get(CONF_API_KEY, "")).strip()
    if google_key and not result[PROVIDER_GOOGLE]["credentials"]:
        result[PROVIDER_GOOGLE]["credentials"].append(
            {
                "id": "google-primary",
                "name": "Google principal",
                "api_key": google_key,
                "enabled": True,
                "priority": 1,
            }
        )

    legacy_limits = entry.options.get(CONF_PROVIDER_LIMITS, {})
    if isinstance(legacy_limits, Mapping):
        for provider in (PROVIDER_GOOGLE, PROVIDER_AZURE):
            if isinstance(legacy_limits.get(provider), Mapping):
                result[provider]["limits"] = deepcopy(dict(legacy_limits[provider]))
    return result


def credentials_from_entry(entry: ConfigEntry) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for provider, config in providers_from_entry(entry).items():
        capabilities = list(config.get("capabilities", ()))
        for credential in config.get("credentials", []):
            if isinstance(credential, Mapping):
                result.append(
                    {
                        **dict(credential),
                        "provider": provider,
                        "capabilities": capabilities,
                    }
                )
    return result


def provider_instances_from_entry(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Compatibility view used only by the retired v1.1 options-flow class."""
    return [
        {
            "id": provider,
            "name": config.get("name", PROVIDER_DISPLAY_NAMES[provider]),
            "adapter": provider,
            "enabled": config.get("enabled", True),
            "priority": index,
            "capabilities": list(config.get("capabilities", ())),
            "limits": deepcopy(config.get("limits", {})),
            "credentials": deepcopy(config.get("credentials", [])),
        }
        for index, (provider, config) in enumerate(
            providers_from_entry(entry).items(), start=1
        )
    ]


def routes_from_entry(entry: ConfigEntry) -> dict[str, list[str]]:
    configured = entry.options.get(CONF_ROUTES) or entry.data.get(CONF_ROUTES)
    if isinstance(configured, Mapping):
        return {
            capability: [
                str(provider)
                for provider in configured.get(capability, [])
                if str(provider) in SUPPORTED_PROVIDERS
            ]
            for capability in DEFAULT_PROVIDER_ROUTES
        }

    instance_to_adapter: dict[str, str] = {}
    instances = entry.options.get(CONF_PROVIDER_INSTANCES) or entry.data.get(
        CONF_PROVIDER_INSTANCES
    )
    if isinstance(instances, list):
        for instance in instances:
            if isinstance(instance, Mapping):
                instance_to_adapter[str(instance.get("id", ""))] = str(
                    instance.get("adapter", "")
                )
    legacy_routes = entry.options.get("provider_routes") or entry.data.get(
        "provider_routes"
    )
    if isinstance(legacy_routes, Mapping):
        migrated: dict[str, list[str]] = {}
        for capability, route in legacy_routes.items():
            migrated[str(capability)] = []
            for value in route if isinstance(route, list) else []:
                provider = instance_to_adapter.get(str(value), str(value))
                if (
                    provider in SUPPORTED_PROVIDERS
                    and provider not in migrated[str(capability)]
                ):
                    migrated[str(capability)].append(provider)
        return {**deepcopy(DEFAULT_PROVIDER_ROUTES), **migrated}
    return deepcopy(DEFAULT_PROVIDER_ROUTES)
