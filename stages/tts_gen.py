"""
4단계: gTTS로 세그먼트별 음성 생성 (asyncio 미사용)

개별 종목 세그먼트(gainer_a/b/c, loser_a/b/c)는
TTS 텍스트 앞에 종목명을 붙여 읽음.
자막(caption)에는 reason만 표시 — 이 파일은 오디오만 담당.
"""
from __future__ import annotations

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

# 개별 종목 키 집합
STOCK_KEYS = {"gainer_a", "gainer_b", "gainer_c",
              "loser_a",  "loser_b",  "loser_c"}


def _extract_tts_text(script: dict, key: str) -> str:
    """
    TTS용 텍스트 추출.
    개별 종목: "{종목명}. {reason}" 형태로 합성
    나머지: 문자열 그대로
    """
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


def generate_tts(text: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tts = gTTS(text=text, lang="ko", slow=False)
    tts.save(str(out_path))
    return out_path


def generate_all_tts(script: dict, audio_dir: Path,
                     only: str | None = None) -> dict[str, Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_paths: dict[str, Path] = {}
    keys_to_generate = {only} if only else set(SEGMENT_KEYS)

    for idx, key in enumerate(SEGMENT_KEYS):
        out = audio_dir / f"{idx:02d}_{key}.mp3"
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
