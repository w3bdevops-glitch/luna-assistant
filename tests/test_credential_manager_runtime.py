"""Executable credential selection and budget tests without Home Assistant."""

import asyncio
import importlib.util
import sys
import types
from enum import StrEnum
from pathlib import Path


class Capability(StrEnum):
    AI_TASK = "ai_task"
    CONVERSATION = "conversation"
    STT = "stt"
    TTS = "tts"
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
        "CONF_PROVIDER_LIMITS": "provider_limits",
        "CONF_ROTATION_STRATEGY": "rotation_strategy",
        "DEFAULT_FAILOVER_ATTEMPTS": 3,
        "DEFAULT_FAILOVER_COOLDOWN": 300,
        "DEFAULT_ROTATION_STRATEGY": "priority",
        "PROVIDER_AZURE": "azure",
        "PROVIDER_GOOGLE": "google",
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
    sys.modules.update(
        {
            "luna_test": package,
            "luna_test.const": const,
            "luna_test.provider_hub": provider_package,
            "luna_test.provider_hub.models": models,
            "homeassistant": types.ModuleType("homeassistant"),
            "homeassistant.config_entries": config_entries,
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
            "daily_request_limit": 1,
        },
        {
            "id": "second",
            "provider": "google",
            "name": "Second",
            "api_key": "two",
            "priority": 2,
        },
    ]
    manager = await module.CredentialManager.async_create(
        object(), entry, credentials, {"rotation_strategy": "priority"}
    )
    lease1 = await manager.async_acquire("google", Capability.STT)
    assert lease1.credential.credential_id == "first"
    await manager.async_complete(lease1, units=12)
    lease2 = await manager.async_acquire("google", Capability.STT)
    assert lease2.credential.credential_id == "second"
    await manager.async_complete(lease2, units=8)
    diagnostics = manager.diagnostics()
    assert diagnostics["provider_usage"]["google"]["monthly_requests"] == 2
    assert diagnostics["provider_usage"]["google"]["monthly_units"]["stt"] == 20

    round_robin = await module.CredentialManager.async_create(
        object(), entry, credentials, {"rotation_strategy": "round_robin"}
    )
    ids = []
    for _ in range(2):
        lease = await round_robin.async_acquire("google", Capability.TTS)
        ids.append(lease.credential.credential_id)
        await round_robin.async_complete(lease)
    assert ids == ["first", "second"]


asyncio.run(main())
print("Luna credential runtime validation passed.")
