"""
1단계: pykrx로 당일 급등/급락 TOP N 수집 + 섹터 정보 포함
컬럼명을 동적으로 감지해 pykrx 버전 차이에 대응
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


# ── 컬럼명 유틸 ──────────────────────────────────────
def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """후보 컬럼명 중 df에 실제로 있는 첫 번째를 반환"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame | None:
    """
    pykrx 버전별 컬럼명 차이를 '종가', '거래량', '등락률'로 통일.
    실패 시 None 반환.
    """
    if df is None or df.empty:
        return None

    col_map = {
        "종가":   ["종가", "Close", "close", "Adj Close"],
        "거래량": ["거래량", "Volume", "volume"],
        "등락률": ["등락률", "변동률", "등락율", "Change", "changes", "ChagesRatio"],
    }

    rename = {}
    for target, candidates in col_map.items():
        if target in df.columns:
            continue
        found = _find_col(df, candidates)
        if found:
            rename[found] = target

    if rename:
        df = df.rename(columns=rename)

    required = ["종가", "거래량", "등락률"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        print(f"   [market_data] 컬럼 매핑 실패. 누락: {missing}")
        print(f"   [market_data] 실제 컬럼 목록: {df.columns.tolist()}")
        return None

    return df


# ── 시장 지수 요약 ───────────────────────────────────
def get_market_summary(date: str) -> dict:
    """코스피·코스닥 당일 등락률 반환"""
    def _change(index_code: str) -> float:
        try:
            df = stock.get_index_ohlcv_by_date(date, date, index_code)
            if df is None or df.empty:
                return 0.0
            rate_col  = _find_col(df, ["등락률", "변동률", "등락율"])
            close_col = _find_col(df, ["종가", "Close"])
            if rate_col:
                return round(float(df[rate_col].iloc[-1]), 2)
            if close_col and len(df) >= 2:
                prev = float(df[close_col].iloc[-2])
                curr = float(df[close_col].iloc[-1])
                return round((curr - prev) / prev * 100, 2) if prev else 0.0
        except Exception as e:
            print(f"   [market_data] 지수 조회 오류 ({index_code}): {e}")
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


# ── 급등/급락 TOP N ──────────────────────────────────
def get_top_movers(date: str) -> dict:
    """
    KOSPI + KOSDAQ 전 종목 조회 → 급등/급락 TOP N 반환.
    각 종목에 sector 필드 포함.
    """
    print("   섹터 데이터 로딩...")
    sector_map = build_sector_map(date)

    frames: list[pd.DataFrame] = []
    name_map: dict[str, str] = {}

    for market in ("KOSPI", "KOSDAQ"):
        try:
            raw = stock.get_market_ohlcv_by_ticker(date, market=market)
            df  = _normalize_ohlcv(raw)
            if df is None:
                continue

            df = df[df["거래량"] > 50_000]
            frames.append(df)

            tickers = stock.get_market_ticker_list(date, market=market)
            for t in tickers:
                try:
                    name_map[t] = stock.get_market_ticker_name(t)
                except Exception:
                    name_map[t] = t

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
                "name":   str(row.get("종목명", ticker)),
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


# ── 차트 데이터 ──────────────────────────────────────
def get_chart_data(ticker: str, date: str) -> pd.DataFrame | None:
    """최근 30일 일봉 데이터 반환 (차트용)."""
    try:
        start = (
            datetime.strptime(date, "%Y%m%d") - timedelta(days=30)
        ).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, date, ticker)
        if df is None or df.empty:
            return None
        if "종가" not in df.columns:
            close_col = _find_col(df, ["Close", "close", "Adj Close"])
            if close_col:
                df = df.rename(columns={close_col: "종가"})
        return df if "종가" in df.columns else None
    except Exception as e:
        print(f"   [market_data] 차트 데이터 오류 ({ticker}): {e}")
        return None
