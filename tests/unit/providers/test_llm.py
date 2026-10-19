import pytest
from pydantic import BaseModel

from tests.fakes import FakeLLM
from voice_agent.config import Settings
from voice_agent.domain.ports import ProviderError
from voice_agent.providers.llm import FailoverLLM, LangChainLLM, make_llm


class Out(BaseModel):
    x: int


async def test_primary_used_when_healthy() -> None:
    llm = FailoverLLM(FakeLLM([Out(x=1)], name="groq"), FakeLLM([], name="gemini"))
    r = await llm.structured("s", "u", Out)
    assert r.value.x == 1 and r.usage.provider == "groq" and llm.name == "groq"


async def test_fails_over_on_provider_error() -> None:
    llm = FailoverLLM(
        FakeLLM([ProviderError("groq", "429")], name="groq"),
        FakeLLM([Out(x=2)], name="gemini"),
    )
    r = await llm.structured("s", "u", Out)
    assert r.value.x == 2 and r.usage.provider == "gemini"


async def test_raises_without_fallback() -> None:
    llm = FailoverLLM(FakeLLM([ProviderError("groq", "down")], name="groq"), None)
    with pytest.raises(ProviderError):
        await llm.structured("s", "u", Out)


class _BadSchemaChat:
    def with_structured_output(self, *args: object, **kwargs: object) -> object:
        raise ValueError("unsupported schema")


async def test_langchain_llm_normalises_structured_output_setup_errors() -> None:
    llm = LangChainLLM("groq", _BadSchemaChat())  # type: ignore[arg-type]
    with pytest.raises(ProviderError):
        await llm.structured("s", "u", Out)


@pytest.mark.parametrize("blank", ["", "  "])
def test_empty_fallback_key_is_treated_as_absent(blank: str) -> None:
    settings = Settings(_env_file=None, groq_api_key="x", gemini_api_key=blank)  # type: ignore[arg-type,call-arg]
    llm = make_llm(settings)
    assert isinstance(llm, FailoverLLM) and llm._fallback is None
