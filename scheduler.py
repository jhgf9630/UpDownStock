"""
UpDownStock 자동 스케줄러

스케줄:
  05:30  한국 시장(코스피+코스닥) 영상 제작
  06:45  코스피 업로드
  07:15  코스닥 업로드
  20:00  나스닥 영상 제작
  21:00  나스닥 업로드

실행:
  python scheduler.py          # 상시 실행 (백그라운드)
  python scheduler.py --once korean   # 한국 시장 즉시 1회 제작+업로드
  python scheduler.py --once nasdaq   # 나스닥 즉시 1회 제작+업로드
  python scheduler.py --upload-only kospi   # 제작 없이 업로드만

pip install schedule
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule

import config
from run import (
    _resolve_markets, _load_market_cache, _script_path,
    stage_tts, stage_image, stage_video, stage_all,
)
from stages.market_data  import get_latest_trading_date
from stages.youtube_upload import upload_video, find_video

# ── 로깅 ─────────────────────────────────────────────
LOG_PATH = Path(config.BASE_DIR) / "scheduler.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scheduler")


# ════════════════════════════════════════════════════
#  영상 제작
# ════════════════════════════════════════════════════
def produce(markets: list[str]):
    """시장 데이터 수집 → ChatGPT 스크립트 → TTS → 이미지 → 영상"""
    date = get_latest_trading_date()
    log.info(f"▶ 영상 제작 시작 — {', '.join(m.upper() for m in markets)} / {date}")
    try:
        stage_all(date, markets)
        log.info(f"✅ 영상 제작 완료 — {', '.join(m.upper() for m in markets)}")
    except Exception as e:
        log.error(f"❌ 영상 제작 실패: {e}", exc_info=True)


# ════════════════════════════════════════════════════
#  영상 업로드
# ════════════════════════════════════════════════════
def upload(market: str):
    date = get_latest_trading_date()
    log.info(f"▶ 업로드 시작 — {market.upper()} / {date}")
    try:
        video_path = find_video(date, market)
        if not video_path:
            log.error(f"❌ 영상 파일 없음: {market} / {date}")
            return
        video_id = upload_video(video_path, market, date)
        if video_id:
            log.info(f"✅ 업로드 완료: {market.upper()} https://youtu.be/{video_id}")
        else:
            log.error(f"❌ 업로드 실패: {market.upper()}")
    except Exception as e:
        log.error(f"❌ 업로드 오류 ({market}): {e}", exc_info=True)


# ════════════════════════════════════════════════════
#  스케줄 등록
# ════════════════════════════════════════════════════
def register_schedules():
    produce_korean = config.PRODUCE_SCHEDULE["korean"]
    produce_nasdaq = config.PRODUCE_SCHEDULE["nasdaq"]
    upload_kospi   = config.UPLOAD_SCHEDULE["kospi"]
    upload_kosdaq  = config.UPLOAD_SCHEDULE["kosdaq"]
    upload_nasdaq  = config.UPLOAD_SCHEDULE["nasdaq"]

    # 평일만 실행
    (schedule.every().monday.at(produce_korean).do(produce, markets=["kospi","kosdaq"]))
    (schedule.every().tuesday.at(produce_korean).do(produce, markets=["kospi","kosdaq"]))
    (schedule.every().wednesday.at(produce_korean).do(produce, markets=["kospi","kosdaq"]))
    (schedule.every().thursday.at(produce_korean).do(produce, markets=["kospi","kosdaq"]))
    (schedule.every().friday.at(produce_korean).do(produce, markets=["kospi","kosdaq"]))

    (schedule.every().monday.at(upload_kospi).do(upload, market="kospi"))
    (schedule.every().tuesday.at(upload_kospi).do(upload, market="kospi"))
    (schedule.every().wednesday.at(upload_kospi).do(upload, market="kospi"))
    (schedule.every().thursday.at(upload_kospi).do(upload, market="kospi"))
    (schedule.every().friday.at(upload_kospi).do(upload, market="kospi"))

    (schedule.every().monday.at(upload_kosdaq).do(upload, market="kosdaq"))
    (schedule.every().tuesday.at(upload_kosdaq).do(upload, market="kosdaq"))
    (schedule.every().wednesday.at(upload_kosdaq).do(upload, market="kosdaq"))
    (schedule.every().thursday.at(upload_kosdaq).do(upload, market="kosdaq"))
    (schedule.every().friday.at(upload_kosdaq).do(upload, market="kosdaq"))

    (schedule.every().monday.at(produce_nasdaq).do(produce, markets=["nasdaq"]))
    (schedule.every().tuesday.at(produce_nasdaq).do(produce, markets=["nasdaq"]))
    (schedule.every().wednesday.at(produce_nasdaq).do(produce, markets=["nasdaq"]))
    (schedule.every().thursday.at(produce_nasdaq).do(produce, markets=["nasdaq"]))
    (schedule.every().friday.at(produce_nasdaq).do(produce, markets=["nasdaq"]))

    (schedule.every().monday.at(upload_nasdaq).do(upload, market="nasdaq"))
    (schedule.every().tuesday.at(upload_nasdaq).do(upload, market="nasdaq"))
    (schedule.every().wednesday.at(upload_nasdaq).do(upload, market="nasdaq"))
    (schedule.every().thursday.at(upload_nasdaq).do(upload, market="nasdaq"))
    (schedule.every().friday.at(upload_nasdaq).do(upload, market="nasdaq"))

    log.info("스케줄 등록 완료:")
    log.info(f"  한국 시장 제작: 평일 {produce_korean}")
    log.info(f"  코스피 업로드:  평일 {upload_kospi}")
    log.info(f"  코스닥 업로드:  평일 {upload_kosdaq}")
    log.info(f"  나스닥 제작:    평일 {produce_nasdaq}")
    log.info(f"  나스닥 업로드:  평일 {upload_nasdaq}")


# ════════════════════════════════════════════════════
#  진입점
# ════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="UpDownStock 자동 스케줄러")
    parser.add_argument(
        "--once", default=None,
        choices=["korean", "kospi", "kosdaq", "nasdaq", "all"],
        help="즉시 1회 실행 (제작+업로드)",
    )
    parser.add_argument(
        "--produce-only", default=None,
        choices=["korean", "kospi", "kosdaq", "nasdaq", "all"],
        help="즉시 제작만 (업로드 없음)",
    )
    parser.add_argument(
        "--upload-only", default=None,
        choices=["kospi", "kosdaq", "nasdaq"],
        help="즉시 업로드만 (제작 없음)",
    )
    args = parser.parse_args()

    # ── 즉시 실행 모드 ──────────────────────────────
    if args.once:
        markets = _resolve_markets(args.once)
        produce(markets)
        for mkt in markets:
            upload(mkt)
        return

    if args.produce_only:
        markets = _resolve_markets(args.produce_only)
        produce(markets)
        return

    if args.upload_only:
        upload(args.upload_only)
        return

    # ── 상시 스케줄 모드 ────────────────────────────
    log.info("=" * 50)
    log.info("UpDownStock 스케줄러 시작")
    log.info("=" * 50)

    register_schedules()

    log.info("스케줄러 실행 중... (Ctrl+C로 종료)")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
