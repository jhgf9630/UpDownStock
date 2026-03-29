"""
5단계: FFmpeg로 클립 합성 → BGM 믹싱 → 1.5배속 최종 영상
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import config


def get_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except Exception:
        return 3.0


def make_clip(image_path: Path, audio_path: Path, out_path: Path) -> Path:
    duration = get_duration(audio_path)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-vf",
            (
                f"scale={config.VIDEO_W}:{config.VIDEO_H}"
                ":force_original_aspect_ratio=decrease,"
                f"pad={config.VIDEO_W}:{config.VIDEO_H}"
                ":(ow-iw)/2:(oh-ih)/2:color=#0d0d0d"
            ),
            str(out_path),
        ],
        check=True, capture_output=True,
    )
    return out_path


def concat_clips(clip_paths: list[Path], out_path: Path) -> Path:
    list_file = out_path.parent / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(out_path),
        ],
        check=True, capture_output=True,
    )
    return out_path


def mix_bgm(video_path: Path, bgm_path: Path, out_path: Path) -> Path:
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-stream_loop", "-1",
                "-i", str(bgm_path),
                "-filter_complex",
                "[1:a]volume=0.10[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                str(out_path),
            ],
            check=True, capture_output=True,
        )
        return out_path
    except subprocess.CalledProcessError as e:
        print(f"   [video] BGM 믹싱 실패 (원본 사용): {e.stderr.decode()}")
        return video_path


def apply_speed(input_path: Path, out_path: Path,
                speed: float = config.SPEED) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-filter_complex",
            f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            str(out_path),
        ],
        check=True, capture_output=True,
    )
    return out_path


def build_video(clips: list[Path], bgm_path: Optional[Path],
                date: str, work_dir: Path) -> Path:
    print("   concat...")
    concat_out = work_dir / "concat.mp4"
    concat_clips(clips, concat_out)
    current = concat_out

    if bgm_path and bgm_path.exists():
        print("   BGM 믹싱...")
        bgm_out = work_dir / "with_bgm.mp4"
        current = mix_bgm(current, bgm_path, bgm_out)

    print(f"   {config.SPEED}배속 처리...")
    final = work_dir / f"shorts_{date}.mp4"
    apply_speed(current, final)
    return final
