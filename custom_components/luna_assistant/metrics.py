"""In-memory operational metrics for Luna Assistant Prime."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class CallMetric:
    """One completed provider or tool call."""

    service: str
    provider: str
    operation: str
    duration_ms: float
    success: bool
    input_units: int = 0
    output_units: int = 0
    error_category: str | None = None
    failover: bool = False


class LunaMetrics:
    """Bounded metrics registry safe for Home Assistant's event loop."""

    def __init__(self, max_history: int = 200) -> None:
        self._history: deque[CallMetric] = deque(maxlen=max_history)
        self._counters: Counter[str] = Counter()
        self._durations: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

    def record(
        self,
        *,
        service: str,
        provider: str,
        operation: str,
        started: float,
        success: bool,
        input_units: int = 0,
        output_units: int = 0,
        error_category: str | None = None,
        failover: bool = False,
    ) -> None:
        """Record a completed operation."""
        duration_ms = max(0.0, (time.monotonic() - started) * 1000)
        metric = CallMetric(
            service=service,
            provider=provider,
            operation=operation,
            duration_ms=round(duration_ms, 2),
            success=success,
            input_units=input_units,
            output_units=output_units,
            error_category=error_category,
            failover=failover,
        )
        self._history.append(metric)
        key = f"{provider}.{service}"
        self._counters[f"{key}.calls"] += 1
        self._counters[f"{key}.success" if success else f"{key}.errors"] += 1
        self._counters[f"{key}.input_units"] += max(0, input_units)
        self._counters[f"{key}.output_units"] += max(0, output_units)
        if failover:
            self._counters[f"{key}.failovers"] += 1
        self._durations[key].append(duration_ms)

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
        return round(ordered[index], 2)

    def snapshot(self) -> dict[str, Any]:
        """Return diagnostics-safe aggregate and recent metrics."""
        latency = {}
        for key, values in self._durations.items():
            samples = list(values)
            latency[key] = {
                "last_ms": round(samples[-1], 2) if samples else None,
                "mean_ms": round(sum(samples) / len(samples), 2) if samples else None,
                "p50_ms": self._percentile(samples, 0.50),
                "p95_ms": self._percentile(samples, 0.95),
            }
        return {
            "counters": dict(self._counters),
            "latency": latency,
            "recent": [asdict(item) for item in list(self._history)[-20:]],
        }
