"""Protocols for swappable components (C5) and shared provider types."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

from voice_agent.domain.enums import AliasKind
from voice_agent.domain.models import Filters, Listing

T = TypeVar("T", bound=BaseModel)


class ProviderError(Exception):
    """A vendor call failed after the provider's own retries."""

    def __init__(self, provider: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.retryable = retryable


class Usage(BaseModel):
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    audio_seconds: float = 0.0  # STT (L5)
    characters: int = 0  # TTS (L5)


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    value: T
    usage: Usage


class LLM(Protocol):
    name: str

    async def structured(self, system: str, user: str, schema: type[T]) -> LLMResult[T]: ...


class Match(BaseModel):
    raw: str
    canonical: str | None
    score: float
    method: Literal["exact", "trigram", "none"]


class Normalizer(Protocol):
    async def normalize(self, kind: AliasKind, raw: str) -> Match: ...


class SearchResult(BaseModel):
    rows: list[Listing]
    sql: str
    params: dict[str, Any]


class Catalog(Protocol):
    async def search(self, filters: Filters, limit: int = 500) -> SearchResult: ...

    async def count(self, filters: Filters) -> int: ...

    async def get(self, listing_id: str) -> Listing | None: ...


class Transcript(BaseModel):
    text: str
    provider: str
    language: str | None = None
    confidence: float | None = None  # 0..1, only when the vendor reports something usable
    audio_seconds: float = 0.0  # 0 when the vendor does not report it


class SpeechToText(Protocol):
    name: str

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript: ...


class TextToSpeech(Protocol):
    name: str

    async def synthesize(self, text: str) -> bytes: ...


@dataclass(frozen=True)
class SttChoice:
    """The STT used for one input language, plus the fallbacks that choice implies (N3)."""

    stt: SpeechToText
    fallbacks: tuple[str, ...] = ()
