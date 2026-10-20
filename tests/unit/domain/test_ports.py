from voice_agent.domain.ports import SttChoice, Transcript, Usage
from voice_agent.telemetry.timing import Clock


def test_usage_has_audio_and_character_counters() -> None:
    u = Usage(provider="groq-stt", audio_seconds=2.5)
    assert u.input_tokens == 0 and u.characters == 0 and u.audio_seconds == 2.5


def test_transcript_defaults() -> None:
    t = Transcript(text="hi", provider="groq")
    assert t.confidence is None and t.language is None and t.audio_seconds == 0.0


def test_stt_choice_defaults_to_no_fallbacks() -> None:
    class _S:
        name = "x"

    assert SttChoice(stt=_S()).fallbacks == ()  # type: ignore[arg-type]


def test_clock_is_monotonic_ms() -> None:
    c = Clock()
    assert 0 <= c.ms() <= c.ms()
