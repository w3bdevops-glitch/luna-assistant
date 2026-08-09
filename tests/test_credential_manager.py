"""Regression checks for central credentials and consumption controls."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
CREDENTIALS = (ROOT / "provider_hub/credentials.py").read_text(encoding="utf-8")
GOOGLE = (ROOT / "provider_hub/google.py").read_text(encoding="utf-8")
AZURE = (ROOT / "provider_hub/azure.py").read_text(encoding="utf-8")
CONFIG = (ROOT / "config_flow.py").read_text(encoding="utf-8")
DIAGNOSTICS = (ROOT / "diagnostics.py").read_text(encoding="utf-8")
HUB = (ROOT / "provider_hub/hub.py").read_text(encoding="utf-8")
INIT = (ROOT / "__init__.py").read_text(encoding="utf-8")

assert "class CredentialManager" in CREDENTIALS
assert "class CredentialLease" in CREDENTIALS
assert "async def async_acquire" in CREDENTIALS
assert "async def async_complete" in CREDENTIALS
assert "async def async_fail" in CREDENTIALS
assert 'strategy == "round_robin"' in CREDENTIALS
assert "_balance_score" in CREDENTIALS
assert 'DEFAULT_ROTATION_STRATEGY = "highest_balance"' in (ROOT / "const.py").read_text(
    encoding="utf-8"
)
assert "daily_request_limit" in CREDENTIALS
assert "monthly_request_limit" in CREDENTIALS
assert "monthly_unit_limits" in CREDENTIALS
assert "Store(" in CREDENTIALS
assert "DEFAULT_FAILOVER_ATTEMPTS = 0" in (ROOT / "const.py").read_text(
    encoding="utf-8"
)
assert "failover=attempt > 0" in GOOGLE
assert "failover=attempt > 0" in AZURE
assert "async_step_providers" in CONFIG
assert "async_step_provider_credentials" in CONFIG
assert "PROVIDER_TAVILY" in CONFIG
assert "duplicate_credential" in CONFIG
assert "MINOR_VERSION = 11" in CONFIG
assert "credentials_from_entry(entry)" in INIT
assert "minor_version=10" in INIT
assert "def _provider_order" in HUB
assert "for provider in self._provider_order(ProviderCapability.STT)" in HUB
assert "for provider in self._provider_order(ProviderCapability.TTS)" in HUB
assert "CONF_API_KEY" in DIAGNOSTICS
assert '"api_key"' not in CREDENTIALS.split("def public_dict", 1)[1].split("def ", 1)[0]

print("Luna credential manager validation passed.")
