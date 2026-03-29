"""
4단계: edge-tts CLI를 subprocess로 호출해 음성 생성
asyncio를 전혀 사용하지 않아 Windows 모든 버전에서 안정적으로 동작.

edge-tts 설치 시 'edge-tts' 커맨드라인 툴이 함께 설치되며,
'python -m edge_tts' 로도 동일하게 호출 가능.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import os
from pathlib import Path

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
    edge-tts를 'python -m edge_tts' subprocess로 호출.
    asyncio 이벤트 루프를 전혀 사용하지 않음.
    텍스트를 임시 파일로 전달해 커맨드라인 인코딩 문제 방지.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 텍스트를 임시 파일로 저장 (긴 텍스트 / 한글 인코딩 안전)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".txt", delete=False
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "edge_tts",
                "--voice",       config.TTS_VOICE,
                "--pitch",       config.TTS_PITCH,
                "--text",        text,
                "--write-media", str(out_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        if result.returncode != 0 or not out_path.exists():
            err = result.stderr.strip()
            raise RuntimeError(
                f"edge-tts 실패 (returncode={result.returncode}): {err}"
            )

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

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
