"""Tavily Search provider with API-key rotation and credit accounting."""

from __future__ import annotations

import time
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from ..metrics import LunaMetrics
from .base import LunaProviderAdapter
from .credentials import CredentialManager
from .models import ProviderCapability, ProviderError, SearchResult


class TavilySearchProvider(LunaProviderAdapter):
    """Search adapter for the Tavily agent-search API."""

    name = "tavily"
    display_name = "Tavily Search"
    capabilities = frozenset({ProviderCapability.SEARCH})

    def __init__(
        self,
        session: ClientSession,
        credentials: CredentialManager,
        metrics: LunaMetrics,
    ) -> None:
        self._session = session
        self._credentials = credentials
        self._metrics = metrics

    async def async_search(
        self,
        *,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
        **_kwargs: Any,
    ) -> SearchResult:
        excluded: set[str] = set()
        last_error: ProviderError | None = None
        attempts = self._credentials.provider_attempts(self.name)
        for attempt in range(attempts):
            try:
                lease = await self._credentials.async_acquire(
                    self.name,
                    ProviderCapability.SEARCH,
                    excluded=excluded,
                    failover=attempt > 0,
                    estimated_units=2 if search_depth == "advanced" else 1,
                )
            except ProviderError:
                if last_error is not None:
                    raise last_error
                raise
            excluded.add(lease.credential.credential_id)
            started = time.monotonic()
            try:
                async with self._session.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": lease.credential.secret,
                        "query": query,
                        "search_depth": (
                            search_depth
                            if search_depth in {"basic", "advanced"}
                            else "basic"
                        ),
                        "max_results": max(1, min(10, int(max_results))),
                        "include_answer": True,
                        "include_raw_content": False,
                    },
                    headers={"User-Agent": "Luna-Assistant-Prime/1.2"},
                    timeout=ClientTimeout(total=30),
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200:
                        raise self._http_error(response.status, payload)
            except ProviderError as err:
                last_error = err
            except (ClientError, TimeoutError, ValueError, TypeError) as err:
                last_error = ProviderError(
                    self.name, "transport", str(err), retryable=True
                )
            else:
                credits = int(payload.get("usage", {}).get("credits", 0) or 0)
                if not credits:
                    credits = 2 if search_depth == "advanced" else 1
                results = tuple(
                    {
                        "title": str(item.get("title", "")),
                        "url": str(item.get("url", "")),
                        "content": str(item.get("content", "")),
                        "score": item.get("score"),
                    }
                    for item in payload.get("results", [])
                    if isinstance(item, dict)
                )
                await self._credentials.async_complete(lease, units=credits)
                self._metrics.record(
                    service="search",
                    provider=self.name,
                    operation="web_search",
                    started=started,
                    success=True,
                    input_units=credits,
                    failover=attempt > 0,
                )
                return SearchResult(
                    provider=self.name,
                    query=query,
                    answer=(str(payload.get("answer", "")).strip() or None),
                    results=results,
                    credits=credits,
                )

            assert last_error is not None
            await self._credentials.async_fail(lease, last_error)
            self._metrics.record(
                service="search",
                provider=self.name,
                operation="web_search",
                started=started,
                success=False,
                error_category=last_error.category,
                failover=attempt > 0,
            )
            if not (
                self._credentials.auto_failover
                and (
                    last_error.retryable
                    or last_error.category in {"authentication", "authorization"}
                )
                and attempt + 1 < attempts
            ):
                raise last_error
        assert last_error is not None
        raise last_error

    def _http_error(self, status: int, payload: Any) -> ProviderError:
        category = {
            401: "authentication",
            403: "authorization",
            429: "rate_limit",
        }.get(status, "provider_error")
        return ProviderError(
            self.name,
            category,
            f"Tavily Search HTTP {status}: {str(payload)[:300]}",
            retryable=status in {429, 500, 502, 503, 504},
            status=status,
        )
