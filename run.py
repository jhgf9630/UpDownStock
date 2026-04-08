"""
UpDownStock — 스테이지별 실행 CLI

시장 선택:
  --market kospi     코스피만
  --market kosdaq    코스닥만
  --market nasdaq    나스닥만
  --market korean    코스피 + 코스닥
  --market all       코스피 + 코스닥 + 나스닥 (기본값)

사용 예:
  python run.py --stage market --market korean
  python run.py --stage all    --market nasdaq
  python run.py --stage tts    --market kospi --segment gainer_a
  python run.py --stage video  --market all
  python run.py --date 20260401 --stage all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows Microsoft Store Python: ProactorEventLoop socketpair 버그 수정
# Playwright(sync_api)는 내부적으로 asyncio를 사용하므로 반드시 필요
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import config
from stages.market_data import (
    get_latest_trading_date,
    get_market_summary, get_top_movers, get_chart_data,
)
from stages.script_gen import (
    generate_script_template, generate_script_ai,
    load_script, get_market_script, _build_web_prompt,
)
from stages.image_gen   import gen_intro, gen_outro, gen_list_card, gen_chart_card
from stages.tts_gen     import generate_all_tts, SEGMENT_KEYS, ANNOUNCE_IMAGE_MAP
from stages.video_build import make_clip, build_video

# ── 시장 그룹 ────────────────────────────────────────
MARKET_GROUPS = {
    "kospi":  ["kospi"],
    "kosdaq": ["kosdaq"],
    "nasdaq": ["nasdaq"],
    "korean": ["kospi", "kosdaq"],
    "all":    ["kospi", "kosdaq", "nasdaq"],
}


def _resolve_markets(market_arg: str | None) -> list[str]:
    """--market 인자 → 실제 시장 리스트"""
    key = (market_arg or "all").lower()
    return MARKET_GROUPS.get(key, ["kospi", "kosdaq", "nasdaq"])


# ── 경로 헬퍼 ────────────────────────────────────────
def _work_dir(date: str) -> Path:
    d = config.OUTPUT_DIR / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def _market_dir(date: str, market: str) -> Path:
    d = _work_dir(date) / market.lower()
    for sub in ("images", "audio", "clips"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(date: str) -> Path:
    return _work_dir(date) / "market.json"


def _script_path(date: str) -> Path:
    return _work_dir(date) / "script.json"


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


# ── 캐시 로드 ────────────────────────────────────────
def _load_market_cache(date: str, markets: list[str],
                       force: bool = False) -> tuple[dict, dict]:
    """
    반환: (market_summary, movers_map)
    movers_map: {"kospi": {...}, "kosdaq": {...}, "nasdaq": {...}} 중 요청 시장만
    """
    cache = _cache_path(date)

    if cache.exists() and not force:
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        # 요청 시장이 모두 캐시에 있으면 캐시 사용
        movers_map = {}
        all_hit = True
        for mkt in markets:
            key = f"{mkt}_movers"
            if key in data and data[key].get("gainers"):
                movers_map[mkt] = data[key]
            else:
                all_hit = False
                break
        if all_hit:
            print(f"   캐시 사용: {cache}")
            return data.get("market_summary", {}), movers_map
        print("   일부 시장 캐시 없음 — 재수집합니다...")

    # 기존 캐시 로드 (있으면 병합)
    existing: dict = {}
    if cache.exists():
        try:
            with open(cache, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    print("   시장 데이터 수집 중...")
    include_nasdaq = "nasdaq" in markets
    market_summary = get_market_summary(date, include_nasdaq=include_nasdaq)

    movers_map: dict = {}
    for mkt in markets:
        movers_map[mkt] = get_top_movers(date, mkt)

    # 캐시 병합 저장
    save_data = dict(existing)
    save_data["market_summary"] = market_summary
    for mkt, mv in movers_map.items():
        save_data[f"{mkt}_movers"] = mv

    if any(mv.get("gainers") for mv in movers_map.values()):
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        print(f"   캐시 저장: {cache}")
    else:
        print("   ⚠️  데이터 수집 실패 — 캐시 저장 생략")

    return market_summary, movers_map


# ════════════════════════════════════════════════════
#  STAGE: market
# ════════════════════════════════════════════════════
def stage_market(date: str, markets: list[str], force: bool = False):
    print(f"\n▶ [market] {', '.join(m.upper() for m in markets)}")
    summary, movers_map = _load_market_cache(date, markets, force=force)

    print(f"\n  시장: {summary.get('summary', '')}")
    for mkt, mv in movers_map.items():
        print(f"\n  [{mkt.upper()}] 급등:")
        for g in mv.get("gainers", []):
            close_str = f"{g['close']:,}원" if isinstance(g['close'], int) else f"${g['close']}"
            print(f"    {g['name']}  +{g['change']}%  {close_str}")
        print(f"  [{mkt.upper()}] 급락:")
        for l in mv.get("losers", []):
            close_str = f"{l['close']:,}원" if isinstance(l['close'], int) else f"${l['close']}"
            print(f"    {l['name']}  {l['change']}%  {close_str}")

    if not any(mv.get("gainers") for mv in movers_map.values()):
        print("\n  ❌ 데이터 없음. 날짜/네트워크 확인 후 --force 옵션으로 재시도하세요.")


# ════════════════════════════════════════════════════
#  STAGE: script-init
# ════════════════════════════════════════════════════
def stage_script_init(date: str, markets: list[str]):
    print(f"\n▶ [script-init] {', '.join(m.upper() for m in markets)}")
    summary, movers_map = _load_market_cache(date, markets)

    if not any(mv.get("gainers") for mv in movers_map.values()):
        print("  ❌ 데이터 없음.")
        return

    out = _script_path(date)
    # 기존 script.json이 있으면 병합 (다른 시장 섹션 유지)
    existing: dict = {}
    if out.exists():
        try:
            with open(out, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    generate_script_template(date, summary, movers_map, out)

    # 기존 섹션 병합 (이미 채워진 시장 유지)
    with open(out, encoding="utf-8") as f:
        new_data = json.load(f)
    for k, v in existing.items():
        if k not in new_data:
            new_data[k] = v
    with open(out, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 템플릿 저장: {out}")
    print()
    print("=" * 60)
    print(_build_web_prompt(out))
    print("=" * 60)


# ════════════════════════════════════════════════════
#  STAGE: tts
# ════════════════════════════════════════════════════
def stage_tts(date: str, markets: list[str], segment: str | None = None):
    sp = _script_path(date)
    if not sp.exists():
        print(f"  ❌ script.json 없음: {sp}")
        return

    script = load_script(sp, markets)

    for mkt in markets:
        print(f"\n▶ [tts] {mkt.upper()}")
        mkt_script = get_market_script(script, mkt)
        aud_dir    = _market_dir(date, mkt) / "audio"
        generate_all_tts(mkt_script, aud_dir, only=segment)
        print(f"  ✅ {mkt.upper()} 오디오 저장")


# ════════════════════════════════════════════════════
#  STAGE: image
# ════════════════════════════════════════════════════
def stage_image(date: str, markets: list[str], segment: str | None = None):
    summary, movers_map = _load_market_cache(date, markets)
    sp = _script_path(date)
    if not sp.exists():
        print(f"  ❌ script.json 없음: {sp}")
        return
    script = load_script(sp, markets)

    for mkt in markets:
        print(f"\n▶ [image] {mkt.upper()}")
        movers   = movers_map[mkt]
        mkt_scr  = get_market_script(script, mkt)
        img_dir  = _market_dir(date, mkt) / "images"
        img_map  = _image_paths(img_dir)
        targets  = [segment] if segment else list(img_map.keys())

        g_map = {f"gainer_{k}": movers["gainers"][i]
                 for i, k in enumerate(["a", "b", "c"])}
        l_map = {f"loser_{k}":  movers["losers"][i]
                 for i, k in enumerate(["a", "b", "c"])}

        for key in targets:
            print(f"   이미지 생성: {key}")
            out = img_map[key]

            if key == "intro":
                gen_intro(date, out, market=mkt.upper())

            elif key == "outro":
                gen_outro(date, out)

            elif key == "gainer_list_caption":
                enriched = [
                    {**movers["gainers"][i],
                     "sector": mkt_scr.get(f"gainer_{k}", {}).get("sector", "")}
                    for i, k in enumerate(["a", "b", "c"])
                ]
                gen_list_card(True, enriched,
                              mkt_scr.get("gainer_list_caption", ""), out)

            elif key == "loser_list_caption":
                enriched = [
                    {**movers["losers"][i],
                     "sector": mkt_scr.get(f"loser_{k}", {}).get("sector", "")}
                    for i, k in enumerate(["a", "b", "c"])
                ]
                gen_list_card(False, enriched,
                              mkt_scr.get("loser_list_caption", ""), out)

            elif key in g_map:
                info = {**g_map[key],
                        "sector": mkt_scr.get(key, {}).get("sector", "")}
                gen_chart_card(True, info,
                               mkt_scr[key]["reason"],
                               get_chart_data(info["ticker"], date, mkt),
                               out)

            elif key in l_map:
                info = {**l_map[key],
                        "sector": mkt_scr.get(key, {}).get("sector", "")}
                gen_chart_card(False, info,
                               mkt_scr[key]["reason"],
                               get_chart_data(info["ticker"], date, mkt),
                               out)

        print(f"  ✅ {mkt.upper()} 이미지 저장")


# ════════════════════════════════════════════════════
#  STAGE: video
# ════════════════════════════════════════════════════
def stage_video(date: str, markets: list[str]):
    for mkt in markets:
        print(f"\n▶ [video] {mkt.upper()} 영상 합성")
        mkt_d    = _market_dir(date, mkt)
        img_dir  = mkt_d / "images"
        aud_dir  = mkt_d / "audio"
        clip_dir = mkt_d / "clips"

        img_map = _image_paths(img_dir)
        aud_map = {
            key: aud_dir / f"{idx:02d}_{key}.wav"
            for idx, key in enumerate(SEGMENT_KEYS)
        }

        missing = []
        for key in SEGMENT_KEYS:
            if key not in ANNOUNCE_IMAGE_MAP and not img_map[key].exists():
                missing.append(f"이미지 없음: {img_map[key].name}")
            if not aud_map[key].exists():
                missing.append(f"오디오 없음: {aud_map[key].name}")
        if missing:
            print(f"  ❌ [{mkt.upper()}] 누락:")
            for m in missing:
                print(f"     {m}")
            continue

        clips = []
        for idx, key in enumerate(SEGMENT_KEYS):
            clip_out = clip_dir / f"clip_{idx:02d}.mp4"
            print(f"   클립 [{idx+1}/{len(SEGMENT_KEYS)}] {key}")
            img_key = ANNOUNCE_IMAGE_MAP.get(key, key)
            make_clip(img_map[img_key], aud_map[key], clip_out)
            clips.append(clip_out)

        bgm   = Path(config.BGM_PATH)
        final = build_video(clips, bgm, date, mkt_d, market=mkt)
        print(f"\n  ✅ [{mkt.upper()}] 완료: {final.name}")


# ════════════════════════════════════════════════════
#  STAGE: all (자동 전체)
# ════════════════════════════════════════════════════
def stage_all(date: str, markets: list[str]):
    print(f"\n▶ [all] 전체 자동 실행 — {', '.join(m.upper() for m in markets)}")
    summary, movers_map = _load_market_cache(date, markets)

    print(f"   스크립트 생성 중 (Claude API 1회 호출)...")
    script = generate_script_ai(date, summary, movers_map)

    sp = _script_path(date)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    print(f"   스크립트 저장: {sp}")

    stage_tts(date, markets)
    stage_image(date, markets)
    stage_video(date, markets)


# ════════════════════════════════════════════════════
#  진입점
# ════════════════════════════════════════════════════
def _do_login():
    from stages.script_gen import login_browser
    login_browser()


def main():
    parser = argparse.ArgumentParser(description="UpDownStock 실행기")
    parser.add_argument(
        "--stage", required=True,
        choices=["market", "script-init", "tts", "image", "video", "all", "login"],
    )
    parser.add_argument(
        "--market", default="all",
        choices=list(MARKET_GROUPS.keys()),
        help="처리할 시장 (기본: all = 코스피+코스닥+나스닥)",
    )
    parser.add_argument("--date",    default=None)
    parser.add_argument("--segment", default=None,
                        help="특정 세그먼트만 (tts/image)")
    parser.add_argument("--force",   action="store_true",
                        help="캐시 무시 재수집")
    args = parser.parse_args()

    date    = args.date or get_latest_trading_date()
    markets = _resolve_markets(args.market)

    print(f"  기준 날짜: {date}")
    print(f"  대상 시장: {', '.join(m.upper() for m in markets)}")

    {
        "market":      lambda: stage_market(date, markets, force=args.force),
        "script-init": lambda: stage_script_init(date, markets),
        "tts":         lambda: stage_tts(date, markets, args.segment),
        "image":       lambda: stage_image(date, markets, args.segment),
        "video":       lambda: stage_video(date, markets),
        "all":         lambda: stage_all(date, markets),
        "login":        lambda: _do_login(),
    }[args.stage]()


if __name__ == "__main__":
    main()
