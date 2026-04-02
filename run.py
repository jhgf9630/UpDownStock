"""
UpDownStock — 스테이지별 실행 CLI

사용법:
  python run.py --stage market                      # 시장 데이터 수집
  python run.py --stage script-init                 # 스크립트 템플릿 생성
  python run.py --stage tts                         # TTS 생성 (KOSPI+KOSDAQ)
  python run.py --stage tts --market kospi          # KOSPI만
  python run.py --stage tts --segment gainer_a      # 특정 세그먼트만
  python run.py --stage image                       # 이미지 생성 (KOSPI+KOSDAQ)
  python run.py --stage image --market kosdaq       # KOSDAQ만
  python run.py --stage video                       # 영상 합성 (KOSPI+KOSDAQ)
  python run.py --stage video --market kospi        # KOSPI만
  python run.py --stage all                         # 전체 자동 (AI)
  python run.py --date 20250610                     # 날짜 수동 지정
  python run.py --stage market --force              # 캐시 무시 재수집
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
from stages.market_data import (get_latest_trading_date, get_market_summary,
                                  get_top_movers, get_chart_data)
from stages.script_gen  import (generate_script_template, generate_script_ai,
                                  load_script, get_market_script, _build_web_prompt)
from stages.image_gen   import (gen_intro, gen_outro, gen_list_card,
                                   gen_chart_card, gen_announce_card)
from stages.tts_gen     import generate_all_tts, SEGMENT_KEYS, ANNOUNCE_IMAGE_MAP
from stages.video_build import make_clip, build_video

MARKETS = ["kospi", "kosdaq"]


# ════════════════════════════════════════════════════
#  경로 헬퍼
# ════════════════════════════════════════════════════
def _work_dir(date: str) -> Path:
    return config.OUTPUT_DIR / date


def _market_dir(date: str, market: str) -> Path:
    """각 시장별 작업 디렉토리: output/YYYYMMDD/kospi/ or kosdaq/"""
    d = _work_dir(date) / market.lower()
    (d / "images").mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(parents=True, exist_ok=True)
    (d / "clips").mkdir(parents=True, exist_ok=True)
    return d


def _market_cache_path(date: str) -> Path:
    return _work_dir(date) / "market.json"


def _script_path(date: str) -> Path:
    return _work_dir(date) / "script.json"


def _image_paths(img_dir: Path) -> dict[str, Path]:
    return {
        "intro":               img_dir / "00_intro.jpg",
        "gainer_announce":     img_dir / "01_gainer_announce.jpg",
        "gainer_list_caption": img_dir / "02_gainer_list.jpg",
        "gainer_a":            img_dir / "03_gainer_a.jpg",
        "gainer_b":            img_dir / "04_gainer_b.jpg",
        "gainer_c":            img_dir / "05_gainer_c.jpg",
        "loser_announce":      img_dir / "06_loser_announce.jpg",
        "loser_list_caption":  img_dir / "07_loser_list.jpg",
        "loser_a":             img_dir / "08_loser_a.jpg",
        "loser_b":             img_dir / "09_loser_b.jpg",
        "loser_c":             img_dir / "10_loser_c.jpg",
        "outro":               img_dir / "11_outro.jpg",
    }


# ════════════════════════════════════════════════════
#  시장 데이터 (캐시: KOSPI+KOSDAQ 통합 저장)
# ════════════════════════════════════════════════════
def _load_market(date: str, force: bool = False) -> tuple[dict, dict, dict]:
    """반환: (market_summary, kospi_movers, kosdaq_movers)"""
    cache = _market_cache_path(date)
    _work_dir(date).mkdir(parents=True, exist_ok=True)

    if cache.exists() and not force:
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        km = data.get("kospi_movers", {})
        dm = data.get("kosdaq_movers", {})
        if km.get("gainers") and dm.get("gainers"):
            print(f"   캐시 사용: {cache}")
            return data["market_summary"], km, dm
        print("   캐시가 비어 있어 재수집합니다...")

    print("   시장 데이터 수집 중...")
    market_summary = get_market_summary(date)
    kospi_movers   = get_top_movers(date, "KOSPI")
    kosdaq_movers  = get_top_movers(date, "KOSDAQ")

    if kospi_movers.get("gainers") and kosdaq_movers.get("gainers"):
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({
                "market_summary": market_summary,
                "kospi_movers":   kospi_movers,
                "kosdaq_movers":  kosdaq_movers,
            }, f, ensure_ascii=False, indent=2)
        print(f"   캐시 저장: {cache}")
    else:
        print("   ⚠️  데이터 수집 실패 — 캐시 저장 생략")

    return market_summary, kospi_movers, kosdaq_movers


# ════════════════════════════════════════════════════
#  STAGE: market
# ════════════════════════════════════════════════════
def stage_market(date: str, force: bool = False):
    print(f"\n▶ [market] 기준 날짜: {date}")
    market_summary, km, dm = _load_market(date, force=force)

    print(f"\n  시장: {market_summary['summary']}")
    for label, movers in [("KOSPI", km), ("KOSDAQ", dm)]:
        print(f"\n  [{label}] 급등주:")
        for g in movers.get("gainers", []):
            print(f"    {g['name']}  +{g['change']}%  {g['close']:,}원")
        print(f"  [{label}] 급락주:")
        for l in movers.get("losers", []):
            print(f"    {l['name']}  {l['change']}%  {l['close']:,}원")

    if not km.get("gainers"):
        print("\n  ❌ 데이터 없음. 날짜/네트워크 확인 후 --force 옵션으로 재시도하세요.")


# ════════════════════════════════════════════════════
#  STAGE: script-init
# ════════════════════════════════════════════════════
def stage_script_init(date: str):
    print(f"\n▶ [script-init] 스크립트 템플릿 생성")
    market_summary, km, dm = _load_market(date)

    if not km.get("gainers"):
        print("  ❌ 시장 데이터 없음. 먼저 --stage market 실행하세요.")
        return

    out = _script_path(date)
    generate_script_template(date, market_summary, km, dm, out)

    print(f"\n  ✅ 템플릿 저장: {out}")
    print("\n  ── 다음 단계 ─────────────────────────────────")
    print("  1. 아래 프롬프트를 Claude/ChatGPT 웹에 붙여넣으세요.")
    print("  2. 응답 JSON을 복사해 script.json을 덮어쓰세요.")
    print("  3. python run.py --stage tts 로 진행하세요.")
    print()
    print("=" * 60)
    print(_build_web_prompt(out))
    print("=" * 60)


# ════════════════════════════════════════════════════
#  STAGE: tts  (시장별 분리 저장)
# ════════════════════════════════════════════════════
def stage_tts(date: str, market: str | None = None,
              segment: str | None = None):
    markets = [market.lower()] if market else MARKETS
    sp = _script_path(date)
    if not sp.exists():
        print(f"  ❌ script.json 없음: {sp}")
        return

    full_script = load_script(sp)

    for mkt in markets:
        print(f"\n▶ [tts] {mkt.upper()} {'전체' if not segment else segment}")
        mkt_script  = get_market_script(full_script, mkt)
        aud_dir     = _market_dir(date, mkt) / "audio"
        generate_all_tts(mkt_script, aud_dir, only=segment)
        print(f"  ✅ 오디오 저장: {aud_dir}")


# ════════════════════════════════════════════════════
#  STAGE: image  (시장별 분리 저장)
# ════════════════════════════════════════════════════
def stage_image(date: str, market: str | None = None,
                segment: str | None = None):
    markets = [market.lower()] if market else MARKETS
    _, km, dm = _load_market(date)
    movers_map = {"kospi": km, "kosdaq": dm}

    sp = _script_path(date)
    if not sp.exists():
        print(f"  ❌ script.json 없음: {sp}")
        return
    full_script = load_script(sp)

    for mkt in markets:
        print(f"\n▶ [image] {mkt.upper()} {'전체' if not segment else segment}")
        movers   = movers_map[mkt]
        mkt_scr  = get_market_script(full_script, mkt)
        img_dir  = _market_dir(date, mkt) / "images"
        img_map  = _image_paths(img_dir)
        targets  = [segment] if segment else list(img_map.keys())

        gainer_map = {f"gainer_{k}": movers["gainers"][i]
                      for i, k in enumerate(["a", "b", "c"])}
        loser_map  = {f"loser_{k}":  movers["losers"][i]
                      for i, k in enumerate(["a", "b", "c"])}

        for key in targets:
            print(f"   이미지 생성: {key}")
            out = img_map[key]

            if key == "intro":
                gen_intro(date, out, market=mkt.upper())


            elif key in ("gainer_announce", "loser_announce"):
                gen_announce_card(key == "gainer_announce", out)

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

            elif key in gainer_map:
                info = {**gainer_map[key],
                        "sector": mkt_scr.get(key, {}).get("sector", "")}
                gen_chart_card(True, info,
                               mkt_scr[key]["reason"],
                               get_chart_data(info["ticker"], date),
                               out)

            elif key in loser_map:
                info = {**loser_map[key],
                        "sector": mkt_scr.get(key, {}).get("sector", "")}
                gen_chart_card(False, info,
                               mkt_scr[key]["reason"],
                               get_chart_data(info["ticker"], date),
                               out)

        print(f"  ✅ 이미지 저장: {img_dir}")


# ════════════════════════════════════════════════════
#  STAGE: video  (시장별 영상 생성)
# ════════════════════════════════════════════════════
def stage_video(date: str, market: str | None = None):
    markets = [market.lower()] if market else MARKETS

    for mkt in markets:
        print(f"\n▶ [video] {mkt.upper()} 영상 합성")
        mkt_d    = _market_dir(date, mkt)
        img_dir  = mkt_d / "images"
        aud_dir  = mkt_d / "audio"
        clip_dir = mkt_d / "clips"
        clip_dir.mkdir(exist_ok=True)

        img_map = _image_paths(img_dir)
        aud_map = {
            key: aud_dir / f"{idx:02d}_{key}.wav"
            for idx, key in enumerate(SEGMENT_KEYS)
        }

        missing = []
        for key in SEGMENT_KEYS:
            # announce 세그먼트는 이미지 없음 — 체크 제외
            if key not in ANNOUNCE_IMAGE_MAP and not img_map[key].exists():
                missing.append(f"이미지 없음: {img_map[key].name}")
            if not aud_map[key].exists():
                missing.append(f"오디오 없음: {aud_map[key].name}")
        if missing:
            print(f"  ❌ [{mkt.upper()}] 누락 파일:")
            for m in missing:
                print(f"     {m}")
            continue

        clips = []
        for idx, key in enumerate(SEGMENT_KEYS):
            clip_out = clip_dir / f"clip_{idx:02d}.mp4"
            print(f"   클립 [{idx+1}/{len(SEGMENT_KEYS)}] {key}")
            # announce 세그먼트는 이미지 없음 → 해당 리스트 이미지 재사용
            if key in ANNOUNCE_IMAGE_MAP:
                img_key = ANNOUNCE_IMAGE_MAP[key]
                make_clip(img_map[img_key], aud_map[key], clip_out)
            else:
                make_clip(img_map[key], aud_map[key], clip_out)
            clips.append(clip_out)

        bgm   = Path(config.BGM_PATH)
        final = build_video(clips, bgm, date, mkt_d, market=mkt)
        print(f"\n  ✅ [{mkt.upper()}] 완료: {final}")


# ════════════════════════════════════════════════════
#  STAGE: all  (전체 자동, AI 모드)
# ════════════════════════════════════════════════════
def stage_all(date: str):
    print(f"\n▶ [all] 전체 자동 실행 (Claude API)")
    market_summary, km, dm = _load_market(date)

    print("   스크립트 생성 중 (AI 1회 호출)...")
    script = generate_script_ai(date, market_summary, km, dm)

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
    parser = argparse.ArgumentParser(description="UpDownStock 실행기")
    parser.add_argument(
        "--stage", required=True,
        choices=["market", "script-init", "tts", "image", "video", "all"],
    )
    parser.add_argument("--date",    default=None, help="날짜 지정 (YYYYMMDD)")
    parser.add_argument("--market",  default=None, choices=["kospi", "kosdaq"],
                        help="특정 시장만 처리")
    parser.add_argument("--segment", default=None,
                        help="특정 세그먼트만 (tts/image 단계)")
    parser.add_argument("--force",   action="store_true",
                        help="캐시 무시 재수집 (market 단계)")
    args = parser.parse_args()

    date = args.date or get_latest_trading_date()
    print(f"  기준 날짜: {date}")

    {
        "market":      lambda: stage_market(date, force=args.force),
        "script-init": lambda: stage_script_init(date),
        "tts":         lambda: stage_tts(date, args.market, args.segment),
        "image":       lambda: stage_image(date, args.market, args.segment),
        "video":       lambda: stage_video(date, args.market),
        "all":         lambda: stage_all(date),
    }[args.stage]()


if __name__ == "__main__":
    main()
