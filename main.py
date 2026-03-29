"""
shorts-bot 진입점
실행: python main.py
"""
from pathlib import Path
from datetime import datetime

import config
from stages.market_data  import get_latest_trading_date, get_market_summary, \
                                  get_top_movers, get_chart_data
from stages.script_gen   import generate_script
from stages.image_gen    import gen_intro, gen_outro, gen_list_card, gen_chart_card
from stages.tts_gen      import generate_all_tts, SEGMENT_KEYS
from stages.video_build  import make_clip, build_video


def main():
    # ── 날짜 확정 ────────────────────────────────────
    date     = get_latest_trading_date()
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y%m%d")
    print(f"\n▶ 기준 날짜: {date_fmt}\n")

    # 작업 디렉토리
    work_dir = config.OUTPUT_DIR / date_fmt
    img_dir  = work_dir / "images"
    aud_dir  = work_dir / "audio"
    clip_dir = work_dir / "clips"
    for d in (work_dir, img_dir, aud_dir, clip_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── 1. 시장 데이터 ───────────────────────────────
    print("▶ 1. 시장 데이터 수집...")
    market_summary = get_market_summary(date)
    movers         = get_top_movers(date)
    print(f"   시장: {market_summary['summary']}")
    print(f"   급등: {[g['name'] for g in movers['gainers']]}")
    print(f"   급락: {[l['name'] for l in movers['losers']]}")

    # ── 2. AI 스크립트 생성 ──────────────────────────
    print("\n▶ 2. AI 스크립트 생성 (Claude API)...")
    script = generate_script(date, market_summary, movers)
    print(f"   도입: {script['intro']}")
    print(f"   마무리: {script['outro']}")

    # ── 3. TTS ───────────────────────────────────────
    print("\n▶ 3. TTS 생성 (edge-tts)...")
    audio_paths = generate_all_tts(script, aud_dir)

    # ── 4. 이미지 생성 ───────────────────────────────
    print("\n▶ 4. 이미지 생성...")
    images: dict[str, Path] = {}

    # 도입부
    images["intro"] = gen_intro(date, img_dir / "00_intro.jpg")
    print("   [1/10] intro")

    # 급등 리스트
    images["gainer_list_caption"] = gen_list_card(
        is_gainer=True,
        stocks=movers["gainers"],
        caption=script["gainer_list_caption"],
        out_path=img_dir / "01_gainer_list.jpg",
    )
    print("   [2/10] gainer_list")

    # 급등 개별 A/B/C
    for i, key in enumerate(["gainer_a", "gainer_b", "gainer_c"]):
        info       = movers["gainers"][i]
        chart_data = get_chart_data(info["ticker"], date)
        caption    = script[key]["reason"]
        images[key] = gen_chart_card(
            is_gainer=True,
            stock_info=info,
            caption=caption,
            chart_data=chart_data,
            out_path=img_dir / f"0{i+2}_{key}.jpg",
        )
        print(f"   [{i+3}/10] {key} ({info['name']})")

    # 급락 리스트
    images["loser_list_caption"] = gen_list_card(
        is_gainer=False,
        stocks=movers["losers"],
        caption=script["loser_list_caption"],
        out_path=img_dir / "05_loser_list.jpg",
    )
    print("   [6/10] loser_list")

    # 급락 개별 A/B/C
    for i, key in enumerate(["loser_a", "loser_b", "loser_c"]):
        info       = movers["losers"][i]
        chart_data = get_chart_data(info["ticker"], date)
        caption    = script[key]["reason"]
        images[key] = gen_chart_card(
            is_gainer=False,
            stock_info=info,
            caption=caption,
            chart_data=chart_data,
            out_path=img_dir / f"0{i+6}_{key}.jpg",
        )
        print(f"   [{i+7}/10] {key} ({info['name']})")

    # 마무리
    images["outro"] = gen_outro(date, img_dir / "09_outro.jpg")
    print("   [10/10] outro")

    # ── 5. 클립 합성 ─────────────────────────────────
    print("\n▶ 5. 세그먼트 클립 합성...")
    clips: list[Path] = []
    for idx, key in enumerate(SEGMENT_KEYS):
        clip_out = clip_dir / f"clip_{idx:02d}.mp4"
        make_clip(images[key], audio_paths[key], clip_out)
        clips.append(clip_out)
        print(f"   [{idx+1}/{len(SEGMENT_KEYS)}] {key}")

    # ── 6. 최종 영상 ─────────────────────────────────
    print("\n▶ 6. 최종 영상 빌드...")
    bgm   = Path(config.BGM_PATH)
    final = build_video(clips, bgm, date_fmt, work_dir)

    print(f"\n✅ 완료 → {final}\n")


if __name__ == "__main__":
    main()
