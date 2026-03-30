"""
4단계: gTTS로 음성 생성 후 WAV로 변환

gTTS가 저장하는 MP3는 VBR 헤더 때문에 ffprobe가 실제 재생 시간을
잘못 읽는 경우가 있음. MP3를 ffmpeg으로 WAV(PCM)로 변환하면
ffprobe가 정확한 duration을 반환 → 화면 전환 타이밍이 정확해짐.

출력 파일: audio/00_intro.wav, 01_gainer_list_caption.wav ...
"""
from __future__ import annotations

import subprocess
import sys
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
    """
    ffmpeg으로 MP3 → WAV(PCM 16bit 44100Hz) 변환.
    WAV는 헤더에 정확한 길이가 기록되어 ffprobe 오차 없음.
    """
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(mp3_path),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "1",
            str(wav_path),
        ],
        capture_output=True,
        check=True,
    )
    return wav_path


def generate_tts(text: str, out_wav: Path) -> Path:
    """gTTS로 MP3 생성 → WAV 변환 → MP3 삭제"""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    mp3_path = out_wav.with_suffix(".mp3")

    # 1. gTTS MP3 저장
    tts = gTTS(text=text, lang="ko", slow=False)
    tts.save(str(mp3_path))

    # 2. WAV 변환
    _mp3_to_wav(mp3_path, out_wav)

    # 3. 중간 MP3 삭제
    mp3_path.unlink(missing_ok=True)

    return out_wav


def generate_all_tts(script: dict, audio_dir: Path,
                     only: str | None = None) -> dict[str, Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_paths: dict[str, Path] = {}
    keys_to_generate = {only} if only else set(SEGMENT_KEYS)

    for idx, key in enumerate(SEGMENT_KEYS):
        # 출력 파일은 .wav
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
