"""
FFmpeg 영상 합성
순서: 클립 생성 → concat → 1.5배속 → BGM 원속도 믹싱 → 중간파일 삭제

싱크 보장:
  오디오가 WAV(PCM)이므로 ffprobe 길이 측정이 정확함.
  make_clip: -t {정확한 duration} 으로 클립 길이를 WAV 길이와 일치시킴.
  apply_speed(1.5x): 영상+음성 동시 배속 → TTS 끝 = 클립 끝 유지.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import config


def _run(cmd: list, label: str = "") -> None:
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg 오류 [{label}]\n{r.stderr[-600:]}")


def get_duration(path: Path) -> float:
    """WAV/MP3/MP4 파일의 정확한 재생 시간(초) 반환"""
    r = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    try:
        return float(r.stdout.strip())
    except Exception:
        return 3.0


def make_clip(image_path: Path, audio_path: Path, out_path: Path) -> Path:
    """
    이미지(정지) + 오디오(WAV) → 클립.

    -shortest 플래그: 오디오(WAV)가 끝나는 순간 정확히 클립 종료.
    WAV는 PCM이므로 FFmpeg이 샘플 수를 정확히 알고 있음
    → 누적 드리프트 없이 모든 세그먼트 싱크 보장.
    """
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",                   # WAV 끝 = 클립 끝 (정확한 싱크)
        "-vf",
        f"scale={config.VIDEO_W}:{config.VIDEO_H}"
        ":force_original_aspect_ratio=decrease,"
        f"pad={config.VIDEO_W}:{config.VIDEO_H}"
        ":(ow-iw)/2:(oh-ih)/2:color=#0d0d0d",
        str(out_path),
    ], label=f"clip:{out_path.name}")
    return out_path


def concat_clips(clip_paths: list[Path], out_path: Path) -> Path:
    list_file = out_path.parent / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")
    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_path),
    ], label="concat")
    return out_path


def apply_speed(input_path: Path, out_path: Path,
                speed: float = config.SPEED) -> Path:
    """
    영상+음성 동시 배속.
    영상: setpts=PTS/1.5 (1.5배 빠르게)
    음성: atempo=1.5
    → 클립 길이와 오디오 길이 비율 그대로 유지 → 싱크 유지
    """
    _run([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-filter_complex",
        f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ], label="speed")
    return out_path


def mix_bgm(video_path: Path, bgm_path: Path, out_path: Path,
            bgm_volume: float = 0.10) -> Path:
    """BGM 원속도로 믹싱 (배속 미적용)"""
    try:
        _run([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(bgm_path),
            "-filter_complex",
            f"[1:a]volume={bgm_volume}[bgm];"
            "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            str(out_path),
        ], label="bgm_mix")
        return out_path
    except Exception as e:
        print(f"   [video] BGM 믹싱 실패 (원본 유지): {e}")
        return video_path


def cleanup_intermediate(work_dir: Path) -> None:
    for name in ["images", "audio", "clips"]:
        d = work_dir / name
        if d.is_dir():
            shutil.rmtree(d)
    for name in ["concat.mp4", "sped.mp4", "with_bgm.mp4", "concat_list.txt"]:
        f = work_dir / name
        if f.exists():
            f.unlink(missing_ok=True)
    print("   중간 파일 정리 완료")


def make_title(date: str, market: str) -> str:
    """
    영상 제목: "260401 코스피 급등급락"
    date   : "20260401" 형식
    market : "kospi" 또는 "kosdaq"
    """
    short_date = date[2:]
    market_kr = {"kospi": "코스피", "kosdaq": "코스닥", "nasdaq": "나스닥"}.get(
        market.lower(), market.upper()
    )
    return f"{short_date} {market_kr} 급등급락"


def build_video(clips: list[Path], bgm_path: Optional[Path],
                date: str, work_dir: Path,
                market: str = "kospi") -> Path:
    """
    date  : "20260401"
    market: "kospi" 또는 "kosdaq"
    최종 파일명: "260401 코스피 급등급락.mp4"
    """
    print("   클립 합치는 중...")
    concat_out = work_dir / "concat.mp4"
    concat_clips(clips, concat_out)

    print(f"   {config.SPEED}배속 체리 중...")
    sped_out = work_dir / "sped.mp4"
    apply_speed(concat_out, sped_out)

    current = sped_out

    if bgm_path and bgm_path.exists():
        print("   BGM 믹싱 중 (원속도)...")
        bgm_out = work_dir / "with_bgm.mp4"
        current = mix_bgm(current, bgm_path, bgm_out)

    title = make_title(date, market)
    final = work_dir / f"{title}.mp4"
    shutil.copy2(str(current), str(final))

    print("   중간 파일 정리 중...")
    cleanup_intermediate(work_dir)

    print(f"   제목: {title}")
    return final
