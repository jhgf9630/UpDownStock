"""
4단계: gTTS로 음성 생성 후 WAV(PCM)로 변환

WAV 사용 이유:
  PCM 헤더에 샘플 수가 정확히 기록됨 → ffprobe duration 오차 없음
  → video_build.py의 -shortest 플래그와 결합해 정확한 싱크 보장

무음 처리:
  gTTS 앞뒤 무음은 그대로 유지 (자연스러운 호흡감)
  싱크는 -shortest 플래그로 WAV 끝 시점에 정확히 맞춤
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from gtts import gTTS

SEGMENT_KEYS = [
    "intro",
    "gainer_announce",
    "gainer_list_caption",
    "gainer_a", "gainer_b", "gainer_c",
    "loser_announce",
    "loser_list_caption",
    "loser_a", "loser_b", "loser_c",
    "outro",
]

ANNOUNCE_IMAGE_MAP = {
    "gainer_announce": "gainer_list_caption",
    "loser_announce":  "loser_list_caption",
}

ANNOUNCE_TEXTS = {
    "gainer_announce": "급등 내용입니다.",
    "loser_announce":  "급락 내용입니다.",
}

STOCK_KEYS = {"gainer_a", "gainer_b", "gainer_c",
              "loser_a",  "loser_b",  "loser_c"}


def _extract_tts_text(script: dict, key: str) -> str:
    if key in ANNOUNCE_TEXTS:
        return ANNOUNCE_TEXTS[key]
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
    """MP3 → WAV(PCM 16bit 44100Hz) 단순 변환. 무음 유지."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(mp3_path),
            "-acodec", "pcm_s16le",
            "-ar",     "44100",
            "-ac",     "1",
            str(wav_path),
        ],
        capture_output=True,
        check=True,
    )
    return wav_path


def generate_tts(text: str, out_wav: Path, max_retries: int = 5) -> Path:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    mp3_path   = out_wav.with_suffix(".mp3")
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            tts = gTTS(text=text, lang="ko", slow=False)
            tts.save(str(mp3_path))
            _mp3_to_wav(mp3_path, out_wav)
            mp3_path.unlink(missing_ok=True)
            return out_wav
        except Exception as e:
            last_error = e
            wait = attempt * 2
            print(f"   TTS 오류 (시도 {attempt}/{max_retries}): {e}")
            mp3_path.unlink(missing_ok=True)
            if attempt < max_retries:
                print(f"      {wait}초 후 재시도...")
                time.sleep(wait)

    raise RuntimeError(f"TTS 생성 실패 ({max_retries}회): {last_error}")


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
