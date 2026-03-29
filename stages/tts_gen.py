"""
4단계: gTTS(Google Text-to-Speech)로 음성 생성
- asyncio 미사용 → Windows Microsoft Store Python 호환
- 무료, 한국어 지원
- pip install gtts
"""
from __future__ import annotations

from pathlib import Path
from gtts import gTTS

import config

SEGMENT_KEYS = [
    "intro",
    "gainer_list_caption",
    "gainer_a", "gainer_b", "gainer_c",
    "loser_list_caption",
    "loser_a",  "loser_b",  "loser_c",
    "outro",
]


def _extract_text(script: dict, key: str) -> str:
    val = script.get(key, "")
    if isinstance(val, dict):
        return val.get("reason", "")
    return str(val)


def generate_tts(text: str, out_path: Path) -> Path:
    """
    gTTS로 mp3 생성.
    slow=False: 기본 속도 (영상 합성 후 1.5배속 처리)
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tts = gTTS(text=text, lang="ko", slow=False)
    tts.save(str(out_path))
    return out_path


def generate_all_tts(script: dict, audio_dir: Path,
                     only: str | None = None) -> dict[str, Path]:
    """
    스크립트 JSON → 세그먼트별 mp3 생성.
    only: 특정 키만 재생성 (예: "gainer_a")
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_paths: dict[str, Path] = {}
    keys_to_generate = {only} if only else set(SEGMENT_KEYS)

    for idx, key in enumerate(SEGMENT_KEYS):
        out = audio_dir / f"{idx:02d}_{key}.mp3"
        audio_paths[key] = out

        if key not in keys_to_generate:
            continue

        text = _extract_text(script, key)
        if not text.strip():
            print(f"   TTS [{key}]: 텍스트 없음 — 건너뜀")
            continue

        print(f"   TTS [{key}]: {text[:35]}...")
        generate_tts(text, out)

    return audio_paths
