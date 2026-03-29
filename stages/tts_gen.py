"""
4단계: edge-tts로 세그먼트별 음성 파일 생성 (무료)
"""
import asyncio
from pathlib import Path
import edge_tts
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
    return val


async def _tts(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(
        text=text,
        voice=config.TTS_VOICE,
        rate="+0%",
        pitch=config.TTS_PITCH,
    )
    await communicate.save(str(out_path))


def generate_tts(text: str, out_path: Path) -> Path:
    asyncio.run(_tts(text, out_path))
    return out_path


def generate_all_tts(script: dict, audio_dir: Path,
                     only: str | None = None) -> dict[str, Path]:
    """
    only: 특정 세그먼트 키만 재생성할 때 사용 (예: "gainer_a")
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_paths: dict[str, Path] = {}
    keys = [only] if only else SEGMENT_KEYS

    for idx, key in enumerate(SEGMENT_KEYS):
        out = audio_dir / f"{idx:02d}_{key}.mp3"
        audio_paths[key] = out
        if key not in keys:
            continue
        text = _extract_text(script, key)
        print(f"   TTS [{key}]: {text[:30]}...")
        generate_tts(text, out)

    return audio_paths
