import pytest

from voice_agent.domain.enums import Language
from voice_agent.understanding.language import detect_language


@pytest.mark.parametrize(
    "text",
    [
        "Diesel pickup in Delhi under 8 lakh",
        "Mini truck in Pune under 5 lakh",
        "Tata Ace in Pune",
        "I need a small truck under 5 Lakaik in Pune",
        "Yes",
        "What is the payload of the second one?",
    ],
)
def test_indian_english_is_english(text: str) -> None:
    assert detect_language(text) == Language.EN


@pytest.mark.parametrize(
    "text",
    [
        "Pune mein paanch lakh tak ka chhota truck chahiye",
        "Mumbai mein diesel pickup dikhao",
        "diesel nahi, CNG wala dikhao",
        "doosre wale ka payload kitna hai?",
        "Haan",
        "पुने में पांच लाख तक का छोटा ट्रक चाहिए",
    ],
)
def test_hindi_grammar_words_or_script_make_hinglish(text: str) -> None:
    assert detect_language(text) == Language.HINGLISH
