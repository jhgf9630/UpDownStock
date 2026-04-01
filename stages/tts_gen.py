"""
4단계: gTTS로 음성 생성 후 WAV로 변환

gTTS MP3 → ffmpeg WAV(PCM) 변환으로 ffprobe duration 정확도 보장.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from gtts import gTTS

SEGMENT_KEYS = [
    "intro",
    "gainer_list_caption",
    "gainer_a", "gainer_b", "gainer_c",
    "loser_list_caption",
    "loser_a",  "loser_b",  "loser_c",
    "outro",
]

STOCK_KEYS = {"gainer_a", "gainer_b", "gainer_c",
              "loser_a",  "loser_b",  "loser_c"}


def _extract_tts_text(script: dict, key: str) -> str:
    val = script.get(key, "")
    if key in STOCK_KEYS and isinstance(val, dict):
        name   = val.get("name",   "")
        reason = val.get("reason", "")
        if name and reason:
            return f"{name}. {reason}"
        return reason or name
    if isinstance(val, dict):
        return val.get("reason", "")
    return str(val)


def _mp3_to_wav(mp3_path: Path, wav_path: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3_path),
         "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
         str(wav_path)],
        capture_output=True, check=True,
    )
    return wav_path


def generate_tts(text: str, out_wav: Path) -> Path:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    mp3_path = out_wav.with_suffix(".mp3")
    tts = gTTS(text=text, lang="ko", slow=False)
    tts.save(str(mp3_path))
    _mp3_to_wav(mp3_path, out_wav)
    mp3_path.unlink(missing_ok=True)
    return out_wav


def generate_all_tts(script: dict, audio_dir: Path,
                     only: str | None = None) -> dict[str, Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_paths: dict[str, Path] = {}
    keys_to_generate = {only} if only else set(SEGMENT_KEYS)

    for idx, key in enumerate(SEGMENT_KEYS):
        out = audio_dir / f"{idx:02d}_{key}.wav"
        audio_paths[key] = out

        if key not in keys_to_generate:
            continue

        text = _extract_tts_text(script, key)
        if not text.strip():
            print(f"   TTS [{key}]: 텍스트 없음 — 건너뜀")
            continue

        print(f"   TTS [{key}]: {text[:40]}...")
        generate_tts(text, out)

    return audio_paths
