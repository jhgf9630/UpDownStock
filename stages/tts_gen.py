"""
4단계: edge-tts로 세그먼트별 음성 파일 생성 (무료)
"""
import asyncio
from pathlib import Path
import edge_tts
import config

# 스크립트 키 순서 = 영상 세그먼트 순서
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
        # 개별 종목: reason 필드 사용
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


def generate_all_tts(script: dict, audio_dir: Path) -> dict[str, Path]:
    """
    스크립트 JSON → 세그먼트별 mp3 생성
    반환: {key: Path}
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_paths: dict[str, Path] = {}

    for idx, key in enumerate(SEGMENT_KEYS):
        text = _extract_text(script, key)
        out  = audio_dir / f"{idx:02d}_{key}.mp3"
        print(f"   TTS [{idx+1}/{len(SEGMENT_KEYS)}] {key}")
        generate_tts(text, out)
        audio_paths[key] = out

    return audio_paths
