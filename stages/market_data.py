"""
시장 데이터 수집

한국 (KOSPI / KOSDAQ): 네이버 금융 크롤링 + pykrx 차트
나스닥 (NASDAQ):       Yahoo Finance 스크리너 API + yfinance 차트
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

import config

# ── 헤더 ─────────────────────────────────────────────
KR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer":         "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
US_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

KR_SESSION = requests.Session()
KR_SESSION.headers.update(KR_HEADERS)

US_SESSION = requests.Session()
US_SESSION.headers.update(US_HEADERS)

# 한국 ETF/파생 제외 키워드
KR_EXCLUDE = [
    "ETN", "ETF", "레버리지", "인버스", "2X", "선물",
    "KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO",
    "KOSEF", "FOCUS", "SOL", "ACE", "TIMEFOLIO",
]

# 나스닥 제외 quoteType
US_EXCLUDE_TYPES = {"ETF", "MUTUALFUND", "INDEX", "CURRENCY", "CRYPTOCURRENCY"}

MARKET_SOSOK = {"KOSPI": "0", "KOSDAQ": "1"}


# ════════════════════════════════════════════════════
#  공통
# ════════════════════════════════════════════════════
def get_latest_trading_date() -> str:
    from pykrx import stock
    for i in range(10):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = stock.get_market_ohlcv_by_date(d, d, "005930")
            if not df.empty:
                return d
        except Exception:
            continue
    return datetime.now().strftime("%Y%m%d")


# ════════════════════════════════════════════════════
#  한국 시장 (KOSPI / KOSDAQ)
# ════════════════════════════════════════════════════
def _fetch_kr_index(code: str) -> float:
    url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:{code}"
    try:
        resp = KR_SESSION.get(url, timeout=8)
        for area in resp.json().get("result", {}).get("areas", []):
            if area.get("name") == "SERVICE_INDEX":
                return round(float(area.get("datas", [{}])[0].get("cr", 0)), 2)
    except Exception as e:
        print(f"   [market] KR 지수 오류 ({code}): {e}")
    return 0.0


def get_market_summary_kr(date: str) -> dict:
    kospi  = _fetch_kr_index("KOSPI")
    kosdaq = _fetch_kr_index("KOSDAQ")
    def fmt(v): return f"{'+' if v >= 0 else ''}{v}%"
    return {
        "kospi":   kospi,
        "kosdaq":  kosdaq,
        "summary": f"코스피 {fmt(kospi)}, 코스닥 {fmt(kosdaq)}",
    }


def _parse_kr_movers(base_url: str, sosok: str,
                     is_gainer: bool, top_n: int) -> list[dict]:
    results, page = [], 1
    while len(results) < top_n:
        try:
            resp = KR_SESSION.get(
                f"{base_url}?sosok={sosok}&page={page}", timeout=10
            )
            resp.encoding = "euc-kr"
            soup  = BeautifulSoup(resp.text, "html.parser")
            rows  = soup.select("table.type_2 tr")
            found = 0
            for row in rows:
                tds  = row.select("td")
                if len(tds) < 5:
                    continue
                link = row.select_one("a[href*='code=']")
                if not link:
                    continue
                m = re.search(r"code=(\d{6})", link.get("href", ""))
                if not m:
                    continue
                name = link.get_text(strip=True)
                if any(kw in name for kw in KR_EXCLUDE):
                    continue
                close_t = re.sub(r"[^0-9]", "", tds[2].get_text(strip=True))
                pct_t   = re.sub(r"[^0-9.]", "", tds[4].get_text(strip=True))
                if not close_t or not pct_t:
                    continue
                chg = float(pct_t)
                chg = abs(chg) if is_gainer else -abs(chg)
                results.append({
                    "ticker": m.group(1),
                    "name":   name,
                    "change": round(chg, 2),
                    "close":  int(close_t),
                    "sector": "",
                })
                found += 1
                if len(results) >= top_n:
                    break
            if found == 0:
                break
            page += 1
        except Exception as e:
            print(f"   [market] KR 크롤링 오류 (p{page}): {e}")
            break
    return results[:top_n]


def get_top_movers_kr(date: str, market: str = "KOSPI") -> dict:
    sosok = MARKET_SOSOK.get(market.upper(), "0")
    top_n = config.TOP_N
    print(f"   [{market}] 급등주 크롤링...")
    gainers = _parse_kr_movers(
        "https://finance.naver.com/sise/sise_rise.naver", sosok, True,  top_n)
    print(f"   [{market}] 급락주 크롤링...")
    losers  = _parse_kr_movers(
        "https://finance.naver.com/sise/sise_fall.naver",  sosok, False, top_n)
    return {"gainers": gainers, "losers": losers}


def get_chart_data_kr(ticker: str, date: str):
    from pykrx import stock
    try:
        start = (datetime.strptime(date, "%Y%m%d") - timedelta(days=14)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, date, ticker)
        return df if (df is not None and not df.empty) else None
    except Exception as e:
        print(f"   [market] KR 차트 오류 ({ticker}): {e}")
        return None


# ════════════════════════════════════════════════════
#  나스닥 (NASDAQ)
# ════════════════════════════════════════════════════
def _fetch_nasdaq_screener(scrId: str, top_n: int) -> list[dict]:
    """
    Yahoo Finance 스크리너 API.
    exchange 필터 제거 → quoteType EQUITY만 통과.
    debug에서 확인: status 200, quotes 정상 반환됨.
    """
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    params = {
        "scrIds":    scrId,
        "count":     50,
        "formatted": "false",
        "lang":      "en-US",
        "region":    "US",
    }
    results = []
    try:
        resp   = US_SESSION.get(url, params=params, timeout=15)
        data   = resp.json()
        quotes = (
            data.get("finance", {})
                .get("result", [{}])[0]
                .get("quotes", [])
        )

        is_gainer = (scrId == "day_gainers")

        for q in quotes:
            # ETF/펀드/지수 제외, EQUITY만
            qt = q.get("quoteType", "")
            if qt in US_EXCLUDE_TYPES:
                continue

            ticker  = q.get("symbol", "")
            name    = q.get("shortName") or q.get("longName") or ticker
            chg_pct = float(q.get("regularMarketChangePercent", 0.0))
            close   = float(q.get("regularMarketPrice", 0.0))

            if not ticker or close == 0:
                continue

            # 부호 정규화
            chg_pct = abs(chg_pct) if is_gainer else -abs(chg_pct)

            results.append({
                "ticker": ticker,
                "name":   name,
                "change": round(chg_pct, 2),
                "close":  round(close, 2),
                "sector": "",
            })
            if len(results) >= top_n:
                break

    except Exception as e:
        print(f"   [market] NASDAQ 스크리너 오류 ({scrId}): {e}")

    return results[:top_n]


def _fetch_nasdaq_index() -> float:
    """나스닥 지수 등락률 (yfinance fast_info)"""
    try:
        import yfinance as yf
        info = yf.Ticker("^IXIC").fast_info
        prev = getattr(info, "previous_close", None)
        curr = getattr(info, "last_price",     None)
        if prev and curr and prev != 0:
            return round((curr - prev) / prev * 100, 2)
    except Exception as e:
        print(f"   [market] 나스닥 지수 오류: {e}")
    return 0.0


def get_market_summary_nasdaq() -> dict:
    chg = _fetch_nasdaq_index()
    fmt = f"{'+' if chg >= 0 else ''}{chg}%"
    return {"nasdaq": chg, "summary": f"나스닥 {fmt}"}


def get_top_movers_nasdaq(top_n: int = config.TOP_N) -> dict:
    print("   [NASDAQ] 급등주 수집...")
    gainers = _fetch_nasdaq_screener("day_gainers", top_n)
    print(f"   [NASDAQ] 급등주 {len(gainers)}개 수집")

    print("   [NASDAQ] 급락주 수집...")
    losers  = _fetch_nasdaq_screener("day_losers",  top_n)
    print(f"   [NASDAQ] 급락주 {len(losers)}개 수집")

    return {"gainers": gainers, "losers": losers}


def get_chart_data_nasdaq(ticker: str) -> object:
    """나스닥 차트 (yfinance). MultiIndex 컬럼 정규화."""
    try:
        import yfinance as yf
        import pandas as pd

        df = yf.download(ticker, period="14d", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None

        # MultiIndex 해제: ('Close', 'AAPL') → 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Close → 종가
        if "Close" in df.columns:
            df = df.rename(columns={"Close": "종가"})

        return df
    except Exception as e:
        print(f"   [market] NASDAQ 차트 오류 ({ticker}): {e}")
        return None


# ════════════════════════════════════════════════════
#  통합 인터페이스
# ════════════════════════════════════════════════════
def get_top_movers(date: str, market: str) -> dict:
    mkt = market.upper()
    if mkt == "NASDAQ":
        return get_top_movers_nasdaq(config.TOP_N)
    return get_top_movers_kr(date, mkt)


def get_market_summary(date: str, include_nasdaq: bool = False) -> dict:
    summary = get_market_summary_kr(date)
    if include_nasdaq:
        ns = get_market_summary_nasdaq()
        summary["nasdaq"] = ns["nasdaq"]
        def fmt(v): return f"{'+' if v >= 0 else ''}{v}%"
        summary["summary"] += f", 나스닥 {fmt(ns['nasdaq'])}"
    return summary


def get_chart_data(ticker: str, date: str, market: str = "KOSPI") -> object:
    if market.upper() == "NASDAQ":
        return get_chart_data_nasdaq(ticker)
    return get_chart_data_kr(ticker, date)
