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
def _load_market(date: str, force: bool = False) -> tuple[dict, dict]:
    cache = _market_cache_path(date)

    # 캐시가 있고 강제 재수집이 아닌 경우 → 캐시 유효성 검사 후 사용
    if cache.exists() and not force:
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        movers = data.get("movers", {})
        # 캐시가 빈 결과면 무시하고 재수집
        if movers.get("gainers") and movers.get("losers"):
            print(f"   캐시 사용: {cache}")
            return data["market_summary"], movers
        else:
            print("   캐시가 비어 있어 재수집합니다...")

    print("   시장 데이터 수집 중...")
    market_summary = get_market_summary(date)
    movers         = get_top_movers(date)

    # 결과가 있을 때만 캐시 저장
    if movers.get("gainers") and movers.get("losers"):
        cache.parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"market_summary": market_summary, "movers": movers},
                      f, ensure_ascii=False, indent=2)
        print(f"   캐시 저장: {cache}")
    else:
        print("   ⚠️  데이터 수집 실패 — 캐시 저장 생략")

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
def stage_market(date: str, force: bool = False):
    print(f"\n\u25b6 [market] \uae30\uc900 \ub0a0\uc9dc: {date}")
    market_summary, movers = _load_market(date, force=force)

    print(f"\n  \uc2dc\uc7a5: {market_summary['summary']}")
    print("\n  \uae09\ub4f1\uc8fc:")
    for g in movers.get("gainers", []):
        print(f"    {g['name']} ({g['sector']})  +{g['change']}%  {g['close']:,}\uc6d0")
    print("\n  \uae09\ub77d\uc8fc:")
    for l in movers.get("losers", []):
        print(f"    {l['name']} ({l['sector']})  {l['change']}%  {l['close']:,}\uc6d0")

    if not movers.get("gainers"):
        print()
        print("  \u274c \ub370\uc774\ud130\uac00 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. \uc544\ub798\ub97c \ud655\uc778\ud558\uc138\uc694:")
        print("     1. \ud574\ub2f9 \ub0a0\uc9dc\uac00 \uac70\ub798\uc77c\uc778\uc9c0 \ud655\uc778 (\uc8fc\ub9d0/\uacf5\ud734\uc77c \uc81c\uc678)")
        print("     2. pykrx \ubc84\uc804: pip show pykrx")
        print("     3. \ucf74\ub7fc \ub514\ubc84\uadf8: market_data.py\uc758 _normalize_ohlcv() \uc8fc\uc11d print \ud65c\uc131\ud654")


# ════════════════════════════════════════════════════
#  STAGE: script-init
# ════════════════════════════════════════════════════
def stage_script_init(date: str):
    print(f"\n\u25b6 [script-init] \uc2a4\ud06c\ub9bd\ud2b8 \ud15c\ud50c\ub9bf \uc0dd\uc131")
    market_summary, movers = _load_market(date)

    if not movers.get("gainers"):
        print("  \u274c \uc2dc\uc7a5 \ub370\uc774\ud130 \uc5c6\uc74c. \uba3c\uc800 --stage market \uc2e4\ud589\ud558\uc138\uc694.")
        return

    out = _script_path(date)
    generate_script_template(date, market_summary, movers, out)

    print(f"\n  \u2705 \ud15c\ud50c\ub9bf \uc800\uc7a5: {out}")
    print("\n  \u2500 \ub2e4\uc74c \ub2e8\uacc4 \uc548\ub0b4 \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    print("  1. \uc544\ub798 \ud504\ub86c\ud504\ud2b8\ub97c Claude/ChatGPT \uc6f9\uc5d0 \ubd99\uc5ec\ub123\uc73c\uc138\uc694.")
    print("  2. AI\uc758 \uc751\ub2f5(JSON)\uc744 \ubcf5\uc0ac\ud574 script.json\uc744 \ub36e\uc5b4\uc4f0\uc138\uc694.")
    print("  3. python run.py --stage tts \ub85c \ub2e4\uc74c \ub2e8\uacc4\ub97c \uc9c4\ud589\ud558\uc138\uc694.")
    print()

    from stages.script_gen import _build_web_prompt
    prompt = _build_web_prompt(out)

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
            # market.json 종목에 script.json 섹터 병합
            enriched_gainers = [
                {**movers["gainers"][i],
                 "sector": script.get(f"gainer_{k}", {}).get("sector", "")}
                for i, k in enumerate(["a", "b", "c"])
            ]
            gen_list_card(True, enriched_gainers,
                          script.get("gainer_list_caption", ""), out)

        elif key == "loser_list_caption":
            enriched_losers = [
                {**movers["losers"][i],
                 "sector": script.get(f"loser_{k}", {}).get("sector", "")}
                for i, k in enumerate(["a", "b", "c"])
            ]
            gen_list_card(False, enriched_losers,
                          script.get("loser_list_caption", ""), out)

        elif key in gainer_map:
            info = {**gainer_map[key],
                    "sector": script.get(key, {}).get("sector", "")}
            gen_chart_card(True, info,
                           script[key]["reason"],
                           get_chart_data(info["ticker"], date),
                           out)

        elif key in loser_map:
            info = {**loser_map[key],
                    "sector": script.get(key, {}).get("sector", "")}
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
    parser.add_argument("--force", action="store_true",
                        help="캐시 무시하고 재수집 (market 단계)")
    args = parser.parse_args()

    date = args.date or get_latest_trading_date()
    print(f"  기준 날짜: {date}")

    {
        "market":      lambda: stage_market(date, force=args.force),
        "script-init": lambda: stage_script_init(date),
        "tts":         lambda: stage_tts(date, args.segment),
        "image":       lambda: stage_image(date, args.segment),
        "video":       lambda: stage_video(date),
        "all":         lambda: stage_all(date),
    }[args.stage]()


if __name__ == "__main__":
    from stages.market_data import get_latest_trading_date
    main()
