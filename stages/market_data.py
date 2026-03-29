"""
1단계: pykrx로 당일 급등/급락 TOP N 수집 + 섹터 정보 포함
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from pykrx import stock

import config
from stages.sector import build_sector_map, get_sector


def get_latest_trading_date() -> str:
    """가장 최근 거래일을 YYYYMMDD 문자열로 반환."""
    for i in range(10):
        d = datetime.now() - timedelta(days=i)
        date_str = d.strftime("%Y%m%d")
        try:
            df = stock.get_market_ohlcv_by_date(date_str, date_str, "005930")
            if not df.empty:
                return date_str
        except Exception:
            continue
    return datetime.now().strftime("%Y%m%d")


def get_market_summary(date: str) -> dict:
    """코스피·코스닥 당일 등락률 반환"""
    def _change(index_code: str) -> float:
        try:
            df = stock.get_index_ohlcv_by_date(date, date, index_code)
            return round(float(df["등락률"].iloc[-1]), 2) if not df.empty else 0.0
        except Exception:
            return 0.0

    kospi  = _change("1001")
    kosdaq = _change("2001")

    def fmt(v):
        return f"{'+' if v >= 0 else ''}{v}%"

    return {
        "kospi":   kospi,
        "kosdaq":  kosdaq,
        "summary": f"코스피 {fmt(kospi)}, 코스닥 {fmt(kosdaq)}",
    }


def get_top_movers(date: str) -> dict:
    """
    KOSPI + KOSDAQ 전 종목 조회 → 급등/급락 TOP N 반환.
    각 종목에 sector 필드 포함.

    반환 구조:
      {
        "gainers": [{"ticker", "name", "change", "close", "sector"}, ...],
        "losers":  [...]
      }
    """
    print("   섹터 데이터 로딩...")
    sector_map = build_sector_map(date)

    frames: list[pd.DataFrame] = []
    name_map: dict[str, str] = {}

    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = stock.get_market_ohlcv_by_ticker(date, market=market)
            df = df[df["거래량"] > 50_000]
            frames.append(df)

            tickers = stock.get_market_ticker_list(date, market=market)
            for t in tickers:
                name_map[t] = stock.get_market_ticker_name(t)
        except Exception as e:
            print(f"   [market_data] {market} 조회 오류: {e}")

    if not frames:
        return {"gainers": [], "losers": []}

    combined = pd.concat(frames)
    combined = combined[combined["등락률"].notna()]
    combined = combined[
        (combined["등락률"] < 29.5) & (combined["등락률"] > -29.5)
    ]
    combined["종목명"] = combined.index.map(lambda x: name_map.get(x, x))

    def _to_list(df: pd.DataFrame) -> list[dict]:
        result = []
        for ticker, row in df.iterrows():
            result.append({
                "ticker": str(ticker),
                "name":   str(row["종목명"]),
                "change": round(float(row["등락률"]), 2),
                "close":  int(row["종가"]),
                "sector": get_sector(str(ticker), sector_map),
            })
        return result

    gainers = combined.nlargest(config.TOP_N, "등락률")
    losers  = combined.nsmallest(config.TOP_N, "등락률")

    return {
        "gainers": _to_list(gainers),
        "losers":  _to_list(losers),
    }


def get_chart_data(ticker: str, date: str) -> pd.DataFrame | None:
    """최근 30일 일봉 데이터 반환 (차트용)."""
    try:
        start = (
            datetime.strptime(date, "%Y%m%d") - timedelta(days=30)
        ).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, date, ticker)
        return df if not df.empty else None
    except Exception as e:
        print(f"   [market_data] 차트 데이터 오류 ({ticker}): {e}")
        return None
