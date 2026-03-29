"""
스테이지별 단독 실행 CLI
사용법:
  python run.py --stage market                     # 1단계: 시장 데이터
  python run.py --stage script-init                # 2단계: 스크립트 템플릿 생성
  python run.py --stage tts                        # 3단계: TTS 전체
  python run.py --stage tts --segment gainer_a     # 3단계: 특정 세그먼트만
  python run.py --stage image                      # 4단계: 이미지 전체
  python run.py --stage image --segment gainer_a   # 4단계: 특정 세그먼트만
  python run.py --stage video                      # 5단계: 영상 합성
  python run.py --stage all                        # 전체 자동 실행 (AI 모드)
  python run.py --date 20250610                    # 날짜 수동 지정
"""
import argparse
import json
from pathlib import Path
from datetime import datetime

import config
from stages.market_data import (get_latest_trading_date, get_market_summary,
                                  get_top_movers, get_chart_data)
from stages.script_gen  import (generate_script_template, generate_script_ai,
                                  load_script)
from stages.image_gen   import (gen_intro, gen_outro, gen_list_card,
                                  gen_chart_card)
from stages.tts_gen     import generate_all_tts, SEGMENT_KEYS
from stages.video_build import make_clip, build_video


# ── 경로 헬퍼 ────────────────────────────────────────
def _paths(date: str):
    work    = config.OUTPUT_DIR / date
    img_dir = work / "images"
    aud_dir = work / "audio"
    clip_dir= work / "clips"
    for d in (work, img_dir, aud_dir, clip_dir):
        d.mkdir(parents=True, exist_ok=True)
    return work, img_dir, aud_dir, clip_dir


def _market_cache_path(date: str) -> Path:
    return config.OUTPUT_DIR / date / "market.json"


def _script_path(date: str) -> Path:
    return config.OUTPUT_DIR / date / "script.json"


# ── 시장 데이터 로드 (캐시 우선) ─────────────────────
def _load_market(date: str) -> tuple[dict, dict]:
    cache = _market_cache_path(date)
    if cache.exists():
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        print(f"   캐시 사용: {cache}")
        return data["market_summary"], data["movers"]

    print("   시장 데이터 수집 중...")
    market_summary = get_market_summary(date)
    movers         = get_top_movers(date)

    cache.parent.mkdir(parents=True, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump({"market_summary": market_summary, "movers": movers},
                  f, ensure_ascii=False, indent=2)
    return market_summary, movers


# ── 이미지 경로 맵 ────────────────────────────────────
def _image_paths(img_dir: Path) -> dict[str, Path]:
    return {
        "intro":               img_dir / "00_intro.jpg",
        "gainer_list_caption": img_dir / "01_gainer_list.jpg",
        "gainer_a":            img_dir / "02_gainer_a.jpg",
        "gainer_b":            img_dir / "03_gainer_b.jpg",
        "gainer_c":            img_dir / "04_gainer_c.jpg",
        "loser_list_caption":  img_dir / "05_loser_list.jpg",
        "loser_a":             img_dir / "06_loser_a.jpg",
        "loser_b":             img_dir / "07_loser_b.jpg",
        "loser_c":             img_dir / "08_loser_c.jpg",
        "outro":               img_dir / "09_outro.jpg",
    }


# ════════════════════════════════════════════════════
#  STAGE: market
# ════════════════════════════════════════════════════
def stage_market(date: str):
    print(f"\n▶ [market] 기준 날짜: {date}")
    market_summary, movers = _load_market(date)

    print(f"\n  시장: {market_summary['summary']}")
    print("\n  급등주:")
    for g in movers["gainers"]:
        print(f"    {g['name']} ({g['sector']})  "
              f"+{g['change']}%  {g['close']:,}원")
    print("\n  급락주:")
    for l in movers["losers"]:
        print(f"    {l['name']} ({l['sector']})  "
              f"{l['change']}%  {l['close']:,}원")

    print(f"\n  캐시 저장: {_market_cache_path(date)}")


# ════════════════════════════════════════════════════
#  STAGE: script-init
# ════════════════════════════════════════════════════
def stage_script_init(date: str):
    print(f"\n▶ [script-init] 스크립트 템플릿 생성")
    market_summary, movers = _load_market(date)

    out = _script_path(date)
    generate_script_template(date, market_summary, movers, out)

    print(f"\n  ✅ 템플릿 저장: {out}")
    print("\n  ── 다음 단계 안내 ──────────────────────────────")
    print("  1. 위 파일을 열어 빈 문자열 필드를 채워주세요.")
    print("  2. 아래 프롬프트를 Claude/ChatGPT 웹에 붙여넣으면 됩니다:")
    print()

    with open(out, encoding="utf-8") as f:
        content = f.read()

    prompt = f"""아래 JSON 파일에서 빈 문자열("")로 표시된 필드만 채워주세요.
_로 시작하는 필드는 참고용 정보입니다.

말투 규칙:
- 경어체 유지 (합니다/습니다)
- 문장 짧고 리듬감 있게
- "살펴보겠습니다" 대신 "알아볼게요"
- 수치를 문장 앞에 배치
- reason은 30자 이내 한 문장
- 마무리 멘트는 "어제 시황 여기까지고요, 오늘도 좋은 투자 되세요!" 스타일

{content}

JSON만 출력해주세요."""

    print("=" * 60)
    print(prompt)
    print("=" * 60)


# ════════════════════════════════════════════════════
#  STAGE: tts
# ════════════════════════════════════════════════════
def stage_tts(date: str, segment: str | None = None):
    print(f"\n▶ [tts] {'전체' if not segment else segment}")
    _, _, aud_dir, _ = _paths(date)

    sp = _script_path(date)
    if not sp.exists():
        print(f"  ❌ script.json 없음: {sp}")
        print("  먼저 'python run.py --stage script-init' 실행 후 JSON을 채워주세요.")
        return

    script = load_script(sp)
    generate_all_tts(script, aud_dir, only=segment)
    print(f"\n  ✅ 오디오 저장: {aud_dir}")


# ════════════════════════════════════════════════════
#  STAGE: image
# ════════════════════════════════════════════════════
def stage_image(date: str, segment: str | None = None):
    print(f"\n▶ [image] {'전체' if not segment else segment}")
    _, img_dir, _, _ = _paths(date)

    market_summary, movers = _load_market(date)
    sp = _script_path(date)
    if not sp.exists():
        print(f"  ❌ script.json 없음: {sp}")
        return

    script = load_script(sp)
    img_map = _image_paths(img_dir)

    targets = [segment] if segment else list(img_map.keys())

    gainer_map = {f"gainer_{k}": movers["gainers"][i]
                  for i, k in enumerate(["a", "b", "c"])}
    loser_map  = {f"loser_{k}":  movers["losers"][i]
                  for i, k in enumerate(["a", "b", "c"])}

    for key in targets:
        print(f"   이미지 생성: {key}")
        out = img_map[key]

        if key == "intro":
            gen_intro(date, out)

        elif key == "outro":
            gen_outro(date, out)

        elif key == "gainer_list_caption":
            gen_list_card(True, movers["gainers"],
                          script.get("gainer_list_caption", ""), out)

        elif key == "loser_list_caption":
            gen_list_card(False, movers["losers"],
                          script.get("loser_list_caption", ""), out)

        elif key in gainer_map:
            info = gainer_map[key]
            gen_chart_card(True, info,
                           script[key]["reason"],
                           get_chart_data(info["ticker"], date),
                           out)

        elif key in loser_map:
            info = loser_map[key]
            gen_chart_card(False, info,
                           script[key]["reason"],
                           get_chart_data(info["ticker"], date),
                           out)

    print(f"\n  ✅ 이미지 저장: {img_dir}")


# ════════════════════════════════════════════════════
#  STAGE: video
# ════════════════════════════════════════════════════
def stage_video(date: str):
    print(f"\n▶ [video] 영상 합성")
    work, img_dir, aud_dir, clip_dir = _paths(date)

    img_map = _image_paths(img_dir)
    aud_map = {
        key: aud_dir / f"{idx:02d}_{key}.mp3"
        for idx, key in enumerate(SEGMENT_KEYS)
    }

    # 파일 존재 확인
    missing = []
    for key in SEGMENT_KEYS:
        if not img_map[key].exists():
            missing.append(f"이미지 없음: {img_map[key].name}")
        if not aud_map[key].exists():
            missing.append(f"오디오 없음: {aud_map[key].name}")
    if missing:
        print("  ❌ 누락 파일:")
        for m in missing:
            print(f"     {m}")
        return

    clips = []
    for idx, key in enumerate(SEGMENT_KEYS):
        clip_out = clip_dir / f"clip_{idx:02d}.mp4"
        print(f"   클립 [{idx+1}/{len(SEGMENT_KEYS)}] {key}")
        make_clip(img_map[key], aud_map[key], clip_out)
        clips.append(clip_out)

    bgm   = Path(config.BGM_PATH)
    final = build_video(clips, bgm, date, work)
    print(f"\n  ✅ 완료: {final}")


# ════════════════════════════════════════════════════
#  STAGE: all (자동 전체 실행 — AI 모드)
# ════════════════════════════════════════════════════
def stage_all(date: str):
    print(f"\n▶ [all] 전체 자동 실행 (Claude API)")
    work, img_dir, aud_dir, clip_dir = _paths(date)

    market_summary, movers = _load_market(date)
    print("   스크립트 생성 중 (AI)...")
    script = generate_script_ai(date, market_summary, movers)

    sp = _script_path(date)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    print(f"   스크립트 저장: {sp}")

    stage_tts(date)
    stage_image(date)
    stage_video(date)


# ════════════════════════════════════════════════════
#  진입점
# ════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="shorts-bot 스테이지 실행기")
    parser.add_argument(
        "--stage", required=True,
        choices=["market", "script-init", "tts", "image", "video", "all"],
        help="실행할 스테이지",
    )
    parser.add_argument("--date",    default=None, help="날짜 지정 (YYYYMMDD)")
    parser.add_argument("--segment", default=None,
                        help="특정 세그먼트만 (tts/image 단계에서 사용)")
    args = parser.parse_args()

    date = args.date or get_latest_trading_date()
    print(f"  기준 날짜: {date}")

    {
        "market":      lambda: stage_market(date),
        "script-init": lambda: stage_script_init(date),
        "tts":         lambda: stage_tts(date, args.segment),
        "image":       lambda: stage_image(date, args.segment),
        "video":       lambda: stage_video(date),
        "all":         lambda: stage_all(date),
    }[args.stage]()


if __name__ == "__main__":
    from stages.market_data import get_latest_trading_date
    main()
