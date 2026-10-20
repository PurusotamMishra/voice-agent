import importlib
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
sys.path.insert(0, str(EVAL_DIR))  # eval/ is a script directory, not a package
audio_eval = importlib.import_module("run_audio_eval")
normalise, word_error_rate = audio_eval.normalise, audio_eval.word_error_rate


def test_wer_identical_is_zero() -> None:
    assert word_error_rate("tata ace in pune", "Tata Ace in Pune.") == 0.0


def test_wer_counts_substitution_and_deletion() -> None:
    assert word_error_rate("a b c d", "a x c") == 0.5


def test_normalise_strips_punctuation_and_case() -> None:
    assert normalise("Pune, 5 lakh!") == "pune 5 lakh"


def test_stt_error_row_keeps_file_and_provider() -> None:
    row = audio_eval.stt_error_row("en-01.wav", "groq", RuntimeError("boom"))
    assert row == {
        "file": "en-01.wav",
        "provider": "groq",
        "transcript": "",
        "status": "STT ERROR: boom",
    }
