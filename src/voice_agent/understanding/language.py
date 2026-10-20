"""Reply language from the words the user said (N13). Code decides, not the LLM.

"lakh", Indian city names and vehicle names are Indian English, not Hinglish. A turn is
Hinglish only if it has Devanagari or a Hindi grammar word.
"""

import re

from voice_agent.domain.enums import Language

# Hindi function words and common verbs in Roman script. None is an English word.
_HINDI_WORDS = frozenset(
    {
        "mein", "ka", "ki", "ke", "ko", "se", "hai", "hain", "tak", "andar", "kam", "zyada",
        "chahiye", "dikhao", "batao", "wala", "wali", "wale", "nahi", "nahin", "haan", "kitna",
        "kitni", "kitne", "kya", "kaun", "kaunsa", "jo", "ho", "aur", "bhi", "uska", "uski",
        "yeh", "woh", "gaadi", "chhota", "bada", "sasta", "chala", "doosra", "doosre",
    }
)  # fmt: skip
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def detect_language(text: str) -> Language:
    if _DEVANAGARI.search(text):
        return Language.HINGLISH
    words = set(re.findall(r"[a-z]+", text.lower()))
    return Language.HINGLISH if words & _HINDI_WORDS else Language.EN
