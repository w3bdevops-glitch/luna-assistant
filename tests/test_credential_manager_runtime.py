"""Executable credential selection and budget tests without Home Assistant."""

import asyncio
import importlib.util
import sys
import types
from enum import StrEnum
from pathlib import Path

DEFAULT_ROUTES = {
    "ai_task": ["google"],
    "conversation": ["google"],
    "stt": ["google", "azure"],
    "tts": ["azure", "google"],
    "search": ["tavily"],
    "image": ["google"],
}


class Capability(StrEnum):
    AI_TASK = "ai_task"
    CONVERSATION = "conversation"
    STT = "stt"
    TTS = "tts"
    SEARCH = "search"
    IMAGE = "image"


class ProviderError(Exception):
    def __init__(self, provider, category, message, *, retryable=False, status=None):
        super().__init__(message)
        self.provider = provider
        self.category = category
        self.retryable = retryable
        self.status = status


class FakeStore:
    def __init__(self, *_args):
        self.data = None

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data


def load_module():
    root = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
    package = types.ModuleType("luna_test")
    package.__path__ = []
    provider_package = types.ModuleType("luna_test.provider_hub")
    provider_package.__path__ = []
    const = types.ModuleType("luna_test.const")
    values = {
        "CONF_AUTO_FAILOVER": "auto_failover",
        "CONF_CREDENTIALS": "credentials",
        "CONF_FAILOVER_ATTEMPTS": "failover_attempts",
        "CONF_FAILOVER_COOLDOWN": "failover_cooldown_seconds",
        "CONF_PROVIDER_INSTANCES": "provider_instances",
        "CONF_PROVIDER_LIMITS": "provider_limits",
        "CONF_PROVIDERS": "providers",
        "CONF_ROTATION_STRATEGY": "rotation_strategy",
        "CONF_ROUTES": "service_routes",
        "DEFAULT_FAILOVER_ATTEMPTS": 0,
        "DEFAULT_FAILOVER_COOLDOWN": 300,
        "DEFAULT_ROTATION_STRATEGY": "highest_balance",
        "DEFAULT_PROVIDER_ROUTES": DEFAULT_ROUTES,
        "PROVIDER_AZURE": "azure",
        "PROVIDER_CAPABILITIES": {
            "google": ("ai_task", "conversation", "stt", "tts", "image"),
            "azure": ("stt", "tts"),
            "tavily": ("search",),
        },
        "PROVIDER_DISPLAY_NAMES": {
            "google": "Google AI",
            "azure": "Microsoft Azure Speech",
            "tavily": "Tavily",
        },
        "PROVIDER_GOOGLE": "google",
        "PROVIDER_TAVILY": "tavily",
    }
    for key, value in values.items():
        setattr(const, key, value)
    models = types.ModuleType("luna_test.provider_hub.models")
    models.ProviderCapability = Capability
    models.ProviderError = ProviderError
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = FakeStore
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.CONF_API_KEY = "api_key"
    sys.modules.update(
        {
            "luna_test": package,
            "luna_test.const": const,
            "luna_test.provider_hub": provider_package,
            "luna_test.provider_hub.models": models,
            "homeassistant": types.ModuleType("homeassistant"),
            "homeassistant.config_entries": config_entries,
            "homeassistant.const": ha_const,
            "homeassistant.helpers": types.ModuleType("homeassistant.helpers"),
            "homeassistant.helpers.storage": storage,
        }
    )
    spec = importlib.util.spec_from_file_location(
        "luna_test.provider_hub.credentials", root / "provider_hub/credentials.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


async def main():
    module = load_module()
    entry = types.SimpleNamespace(entry_id="test", data={}, options={}, subentries={})
    credentials = [
        {
            "id": "first",
            "provider": "google",
            "name": "First",
            "api_key": "one",
            "priority": 1,
        },
        {
            "id": "second",
            "provider": "google",
            "name": "Second",
            "api_key": "two",
            "priority": 2,
        },
        {
            "id": "third",
            "provider": "google",
            "name": "Third",
            "api_key": "three",
            "priority": 3,
        },
        {
            "id": "fourth",
            "provider": "google",
            "name": "Fourth",
            "api_key": "four",
            "priority": 4,
        },
        {
            "id": "azure-one",
            "provider": "azure",
            "name": "Azure One",
            "api_key": "azure-key-one",
            "region": "brazilsouth",
            "priority": 1,
        },
        {
            "id": "azure-two",
            "provider": "azure",
            "name": "Azure Two",
            "api_key": "azure-key-two",
            "region": "eastus",
            "priority": 2,
        },
        {
            "id": "azure-three",
            "provider": "azure",
            "name": "Azure Three",
            "api_key": "azure-key-three",
            "region": "westus",
            "priority": 3,
        },
        {
            "id": "tavily-one",
            "provider": "tavily",
            "name": "Tavily One",
            "api_key": "tavily-key-one",
        },
        {
            "id": "tavily-two",
            "provider": "tavily",
            "name": "Tavily Two",
            "api_key": "tavily-key-two",
        },
    ]
    providers = module.default_providers()
    providers["google"]["limits"]["monthly_unit_limits"] = {"stt": 1000}
    manager = await module.CredentialManager.async_create(
        object(),
        entry,
        credentials,
        {"providers": providers, "service_routes": DEFAULT_ROUTES},
    )
    lease1 = await manager.async_acquire("google", Capability.STT)
    assert lease1.credential.credential_id == "first"
    await manager.async_complete(lease1, units=12)
    lease2 = await manager.async_acquire("google", Capability.STT)
    assert lease2.credential.credential_id == "second"
    await manager.async_complete(lease2, units=8)
    diagnostics = manager.diagnostics()
    assert (
        len(
            [
                item
                for item in diagnostics["credentials"]
                if item["provider"] == "google"
            ]
        )
        == 4
    )
    assert (
        len(
            [item for item in diagnostics["credentials"] if item["provider"] == "azure"]
        )
        == 3
    )
    assert diagnostics["providers"]["google"]["usage"]["monthly_requests"] == 2
    assert diagnostics["providers"]["google"]["usage"]["monthly_units"]["stt"] == 20
    assert diagnostics["providers"]["tavily"]["credential_count"] == 2

    round_robin_credentials = list(credentials)
    round_robin_providers = module.default_providers()
    round_robin_providers["google"]["rotation_strategy"] = "round_robin"
    round_robin = await module.CredentialManager.async_create(
        object(),
        entry,
        round_robin_credentials,
        {
            "providers": round_robin_providers,
            "service_routes": DEFAULT_ROUTES,
        },
    )
    ids = []
    for _ in range(4):
        lease = await round_robin.async_acquire("google", Capability.TTS)
        ids.append(lease.credential.credential_id)
        await round_robin.async_complete(lease)
    assert ids == ["first", "second", "third", "fourth"]

    budget_manager = await module.CredentialManager.async_create(
        object(),
        entry,
        credentials,
        {
            "providers": module.default_providers(),
            "service_routes": DEFAULT_ROUTES,
            "failover_attempts": 1,
        },
    )
    with budget_manager.call_scope():
        first_attempt = await budget_manager.async_acquire("google", Capability.STT)
        await budget_manager.async_fail(
            first_attempt,
            ProviderError("google", "rate_limit", "retry", retryable=True),
        )
        try:
            await budget_manager.async_acquire("google", Capability.STT)
        except ProviderError as err:
            assert err.category == "attempt_limit"
        else:
            raise AssertionError("Global attempt budget was not enforced")

    legacy_entry = types.SimpleNamespace(
        entry_id="legacy",
        data={},
        subentries={},
        options={
            "provider_instances": [
                {
                    "id": "google-one",
                    "adapter": "google",
                    "capabilities": ["conversation", "stt"],
                    "credentials": [{"id": "g1", "api_key": "g-one"}],
                },
                {
                    "id": "google-two",
                    "adapter": "google",
                    "capabilities": ["ai_task", "tts"],
                    "credentials": [{"id": "g2", "api_key": "g-two"}],
                },
                {
                    "id": "azure-one",
                    "adapter": "azure",
                    "capabilities": ["stt", "tts"],
                    "credentials": [
                        {
                            "id": "a1",
                            "api_key": "a-one",
                            "region": "brazilsouth",
                        }
                    ],
                },
            ]
        },
    )
    migrated = module.providers_from_entry(legacy_entry)
    assert [item["id"] for item in migrated["google"]["credentials"]] == [
        "g1",
        "g2",
    ]
    assert migrated["azure"]["credentials"][0]["id"] == "a1"
    assert "search" in migrated["tavily"]["capabilities"]


asyncio.run(main())
print("Luna credential runtime validation passed.")
