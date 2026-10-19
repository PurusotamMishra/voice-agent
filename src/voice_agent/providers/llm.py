"""LLM providers (I1, I2, I3): LangChain chat models behind the LLM protocol, with failover."""

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from voice_agent.config import Settings
from voice_agent.domain.ports import LLM, LLMResult, ProviderError, Usage

log = logging.getLogger(__name__)


class LangChainLLM:
    def __init__(self, name: str, chat: BaseChatModel) -> None:
        self.name = name
        self._chat = chat

    async def structured[T: BaseModel](
        self, system: str, user: str, schema: type[T]
    ) -> LLMResult[T]:
        try:
            runnable = self._chat.with_structured_output(schema, include_raw=True)
            out: dict[str, Any] = await runnable.ainvoke(  # type: ignore[assignment]
                [("system", system), ("human", user)]
            )
        except Exception as exc:  # vendor SDKs raise many types; normalise at the seam
            raise ProviderError(self.name, str(exc), retryable=True) from exc
        parsed = out.get("parsed")
        if parsed is None:
            raise ProviderError(self.name, f"unparseable output: {out.get('parsing_error')}")
        meta = getattr(out.get("raw"), "usage_metadata", None) or {}
        usage = Usage(
            provider=self.name,
            input_tokens=meta.get("input_tokens", 0),
            output_tokens=meta.get("output_tokens", 0),
        )
        return LLMResult(value=parsed, usage=usage)


class FailoverLLM:
    """Tries the primary; on ProviderError tries the fallback once. Usage.provider shows who served."""

    def __init__(self, primary: LLM, fallback: LLM | None) -> None:
        self.name = primary.name
        self._primary = primary
        self._fallback = fallback

    async def structured[T: BaseModel](
        self, system: str, user: str, schema: type[T]
    ) -> LLMResult[T]:
        try:
            return await self._primary.structured(system, user, schema)
        except ProviderError as exc:
            if self._fallback is None:
                raise
            log.warning("llm failover %s -> %s: %s", self._primary.name, self._fallback.name, exc)
            return await self._fallback.structured(system, user, schema)


def _groq(settings: Settings) -> LLM | None:
    if settings.groq_api_key is None:
        return None
    from langchain_groq import ChatGroq

    chat = ChatGroq(
        model_name=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
        max_retries=2,
        timeout=15,
    )
    return LangChainLLM("groq", chat)


def _gemini(settings: Settings) -> LLM | None:
    if settings.gemini_api_key is None:
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI

    chat = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key.get_secret_value(),
        temperature=0,
        max_retries=2,
        timeout=15,
    )
    return LangChainLLM("gemini", chat)


_FACTORIES: dict[str, Callable[[Settings], LLM | None]] = {"groq": _groq, "gemini": _gemini}


def make_llm(settings: Settings) -> LLM:
    primary = _FACTORIES[settings.llm_provider](settings)
    if primary is None:
        raise RuntimeError(f"{settings.llm_provider.upper()}_API_KEY is not set (see .env.example)")
    fallback = None
    if settings.llm_fallback_provider not in ("none", settings.llm_provider):
        fallback = _FACTORIES[settings.llm_fallback_provider](settings)
    return FailoverLLM(primary, fallback)
