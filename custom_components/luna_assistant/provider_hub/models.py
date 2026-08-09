"""Provider-neutral contracts used by Luna Assistant Prime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderCapability(StrEnum):
    """Capabilities addressable by the Provider Hub."""

    AI_TASK = "ai_task"
    CONVERSATION = "conversation"
    STT = "stt"
    TTS = "tts"
    SEARCH = "search"
    IMAGE = "image"


class ProviderError(Exception):
    """Normalized provider failure."""

    def __init__(
        self,
        provider: str,
        category: str,
        message: str,
        *,
        retryable: bool = False,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.category = category
        self.retryable = retryable
        self.status = status


@dataclass(frozen=True, slots=True)
class AudioResult:
    """Provider-neutral synthesized audio response."""

    provider: str
    format: str
    data: bytes
    sample_rate: int
    channels: int
    bits_per_sample: int
    voice: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Provider-neutral web search response."""

    provider: str
    query: str
    answer: str | None
    results: tuple[dict, ...]
    credits: int = 1
