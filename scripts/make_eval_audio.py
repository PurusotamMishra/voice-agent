"""Synthesise stand-in eval clips with ElevenLabs (N7): 16 kHz mono WAV, plus white noise for `noisy`.

Usage: uv run python scripts/make_eval_audio.py [--force]
Needs ELEVENLABS_API_KEY. Existing files are kept unless --force (real recordings win).
"""

import argparse
import array
import random
import sys
import wave
from pathlib import Path

import httpx
import yaml

from voice_agent.config import get_settings, key

AUDIO_DIR = Path(__file__).resolve().parents[1] / "eval" / "audio"
URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
NOISE_RMS = 1500  # on int16 samples: clearly audible hiss, speech still intelligible


def synthesise(text: str, api_key: str, voice: str, model: str) -> bytes:
    resp = httpx.post(
        URL.format(voice=voice),
        params={"output_format": "pcm_16000"},
        headers={"xi-api-key": api_key},
        json={"text": text, "model_id": model},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content


def add_noise(pcm: bytes, seed: int = 7) -> bytes:
    rng = random.Random(seed)
    samples = array.array("h", pcm)
    for i, s in enumerate(samples):
        samples[i] = max(-32768, min(32767, s + int(rng.gauss(0, NOISE_RMS))))
    return samples.tobytes()


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes(pcm)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    api_key = key(settings.elevenlabs_api_key)
    if api_key is None:
        print("ELEVENLABS_API_KEY is not set", file=sys.stderr)
        return 2
    cases = yaml.safe_load((AUDIO_DIR / "cases.yaml").read_text(encoding="utf-8"))
    for case in cases:
        path = AUDIO_DIR / case["file"]
        if path.exists() and not args.force:
            print(f"keep  {path.name}")
            continue
        pcm = synthesise(
            case["say"], api_key, settings.elevenlabs_voice_id, settings.elevenlabs_model
        )
        write_wav(path, add_noise(pcm) if case.get("noisy") else pcm)
        print(f"wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
