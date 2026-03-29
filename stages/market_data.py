"""
1단계: 네이버 금융 크롤링으로 급등/급락 TOP N 수집

참조 URL:
  급등: https://finance.naver.com/sise/sise_rise.naver
  급락: https://finance.naver.com/sise/sise_fall.naver
  지수: https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KOSPI

컬럼 구조 (debug_naver.py 확인):
  cols[1] = 종목명
  cols[2] = 현재가
  cols[4] = 등락률 (+22.58%)

섹터는 크롤링하지 않음 → script_gen.py에서 AI가 추론
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from pykrx import stock

import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ETN/레버리지/인버스 필터
EXCLUDE_KEYWORDS = [
    "ETN", "ETF", "레버리지", "인버스", "2X", "선물",
    "KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO",
    "KOSEF", "FOCUS", "SOL", "ACE", "TIMEFOLIO",
    "TR ETN", "TOP5", "TOP10",
]


def _is_excluded(name: str) -> bool:
    return any(kw in name for kw in EXCLUDE_KEYWORDS)


def get_latest_trading_date() -> str:
    for i in range(10):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = stock.get_market_ohlcv_by_date(d, d, "005930")
            if not df.empty:
                return d
        except Exception:
            continue
    return datetime.now().strftime("%Y%m%d")


def _fetch_index_change(code: str) -> float:
    url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:{code}"
    try:
        resp = SESSION.get(url, timeout=8)
        data = resp.json()
        areas = data.get("result", {}).get("areas", [])
        for area in areas:
            if area.get("name") == "SERVICE_INDEX":
                item = area.get("datas", [{}])[0]
                return round(float(item.get("cr", 0)), 2)
    except Exception as e:
        print(f"   [market_data] 지수 polling 오류 ({code}): {e}")
    return 0.0


def get_market_summary(date: str) -> dict:
    kospi  = _fetch_index_change("KOSPI")
    kosdaq = _fetch_index_change("KOSDAQ")

    def fmt(v):
        return f"{'+' if v >= 0 else ''}{v}%"

    return {
        "kospi":   kospi,
        "kosdaq":  kosdaq,
        "summary": f"코스피 {fmt(kospi)}, 코스닥 {fmt(kosdaq)}",
    }


def _parse_movers_page(url: str, is_gainer: bool, top_n: int) -> list[dict]:
    results = []
    page    = 1

    while len(results) < top_n:
        try:
            paged_url = f"{url}?page={page}"
            resp = SESSION.get(paged_url, timeout=10)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")

            rows = soup.select("table.type_2 tr")
            found_this_page = 0

            for row in rows:
                tds = row.select("td")
                if len(tds) < 5:
                    continue

                link_tag = row.select_one("a[href*='code=']")
                if not link_tag:
                    continue

                m = re.search(r"code=(\d{6})", link_tag.get("href", ""))
                if not m:
                    continue
                ticker = m.group(1)

                name = link_tag.get_text(strip=True)
                if _is_excluded(name):
                    continue

                close_text = re.sub(r"[^0-9]", "", tds[2].get_text(strip=True))
                pct_text   = re.sub(r"[^0-9.]", "", tds[4].get_text(strip=True))

                if not close_text or not pct_text:
                    continue

                change = float(pct_text)
                change = abs(change) if is_gainer else -abs(change)

                results.append({
                    "ticker": ticker,
                    "name":   name,
                    "change": round(change, 2),
                    "close":  int(close_text),
                    # sector는 AI가 채움 — 여기서는 빈 값
                    "sector": "",
                })
                found_this_page += 1

                if len(results) >= top_n:
                    break

            if found_this_page == 0:
                break
            page += 1

        except Exception as e:
            print(f"   [market_data] 크롤링 오류 ({url} p{page}): {e}")
            break

    return results[:top_n]


def get_top_movers(date: str) -> dict:
    top_n = config.TOP_N

    print("   급등주 크롤링...")
    gainers = _parse_movers_page(
        "https://finance.naver.com/sise/sise_rise.naver", True, top_n
    )

    print("   급락주 크롤링...")
    losers = _parse_movers_page(
        "https://finance.naver.com/sise/sise_fall.naver", False, top_n
    )

    return {"gainers": gainers, "losers": losers}


def get_chart_data(ticker: str, date: str):
    try:
        start = (
            datetime.strptime(date, "%Y%m%d") - timedelta(days=30)
        ).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, date, ticker)
        return df if (df is not None and not df.empty) else None
    except Exception as e:
        print(f"   [market_data] 차트 데이터 오류 ({ticker}): {e}")
        return None
