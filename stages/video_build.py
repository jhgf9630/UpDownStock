"""
FFmpeg 영상 합성
순서: concat → 배속(음성만) → BGM 믹싱(원속도) → 중간파일 삭제
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import config

def get_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1",str(audio_path)],
        capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 3.0

def make_clip(image_path: Path, audio_path: Path, out_path: Path) -> Path:
    duration = get_duration(audio_path) + 0.4  # 오디오 끝 후 0.4초 여유
    subprocess.run([
        "ffmpeg","-y","-loop","1",
        "-i",str(image_path),"-i",str(audio_path),
        "-c:v","libx264","-tune","stillimage",
        "-c:a","aac","-b:a","128k","-pix_fmt","yuv420p",
        "-t",str(duration),"-vf",
        f"scale={config.VIDEO_W}:{config.VIDEO_H}:force_original_aspect_ratio=decrease,"
        f"pad={config.VIDEO_W}:{config.VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color=#0d0d0d",
        str(out_path)],
        check=True, capture_output=True)
    return out_path

def concat_clips(clip_paths: list[Path], out_path: Path) -> Path:
    list_file = out_path.parent / "concat_list.txt"
    with open(list_file,"w",encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")
    subprocess.run([
        "ffmpeg","-y","-f","concat","-safe","0",
        "-i",str(list_file),"-c","copy",str(out_path)],
        check=True, capture_output=True)
    return out_path

def apply_speed(input_path: Path, out_path: Path, speed: float = config.SPEED) -> Path:
    """영상+음성 배속 (BGM 없는 상태에서 실행)"""
    subprocess.run([
        "ffmpeg","-y","-i",str(input_path),
        "-filter_complex",
        f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
        "-map","[v]","-map","[a]",
        "-c:v","libx264","-crf","18","-preset","fast",
        "-c:a","aac","-b:a","128k",str(out_path)],
        check=True, capture_output=True)
    return out_path

def mix_bgm(video_path: Path, bgm_path: Path, out_path: Path, bgm_volume: float = 0.10) -> Path:
    """배속 완료 후 BGM을 원속도로 믹싱"""
    try:
        subprocess.run([
            "ffmpeg","-y","-i",str(video_path),
            "-stream_loop","-1","-i",str(bgm_path),
            "-filter_complex",
            f"[1:a]volume={bgm_volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
            "-map","0:v","-map","[aout]",
            "-c:v","copy","-c:a","aac","-b:a","128k",str(out_path)],
            check=True, capture_output=True)
        return out_path
    except subprocess.CalledProcessError as e:
        print(f"   [video] BGM 믹싱 실패 (원본 유지): {e.stderr.decode()[:200]}")
        return video_path

def cleanup_intermediate(work_dir: Path) -> None:
    """중간 산출물 삭제. 최종 mp4만 유지."""
    for name in ["images","audio","clips"]:
        d = work_dir / name
        if d.exists():
            shutil.rmtree(d)
    for name in ["concat.mp4","sped.mp4","with_bgm.mp4","concat_list.txt"]:
        f = work_dir / name
        if f.exists():
            f.unlink()

def build_video(clips: list[Path], bgm_path: Optional[Path],
                date: str, work_dir: Path) -> Path:
    print("   클립 합치는 중...")
    concat_out = work_dir / "concat.mp4"
    concat_clips(clips, concat_out)

    print(f"   {config.SPEED}배속 처리 중 (나레이션만)...")
    sped_out = work_dir / "sped.mp4"
    apply_speed(concat_out, sped_out)

    final = work_dir / f"shorts_{date}.mp4"
    if bgm_path and bgm_path.exists():
        print("   BGM 믹싱 중 (원속도)...")
        result = mix_bgm(sped_out, bgm_path, final)
        if result == sped_out:          # 믹싱 실패시 sped를 final로
            sped_out.rename(final)
    else:
        sped_out.rename(final)

    print("   중간 파일 정리 중...")
    cleanup_intermediate(work_dir)

    print(f"   완료: {final}")
    return final
