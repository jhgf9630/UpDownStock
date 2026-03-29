"""
1단계: 네이버 금융 크롤링으로 급등/급락 TOP N 수집
pykrx 버전 의존성 없이 안정적으로 동작

사용 URL:
  급등: https://finance.naver.com/sise/sise_rise.naver
  급락: https://finance.naver.com/sise/sise_fall.naver
  지수: https://finance.naver.com/sise/sise_index_day.naver?code=KOSPI / KOSDAQ
  섹터: 종목 정보 페이지에서 업종 파싱
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from pykrx import stock   # 차트 데이터(단일 종목)에만 사용

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


# ── 최근 거래일 ──────────────────────────────────────
def get_latest_trading_date() -> str:
    """
    네이버 금융 급등 페이지에서 날짜를 읽거나,
    pykrx 단일 종목 조회로 가장 최근 거래일 탐색.
    """
    for i in range(10):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = stock.get_market_ohlcv_by_date(d, d, "005930")
            if not df.empty:
                return d
        except Exception:
            continue
    return datetime.now().strftime("%Y%m%d")


# ── 지수 등락률 ──────────────────────────────────────
def get_market_summary(date: str) -> dict:
    """코스피·코스닥 당일 등락률 — 네이버 금융 크롤링"""
    def _fetch(code: str) -> float:
        url = f"https://finance.naver.com/sise/sise_index_day.naver?code={code}"
        try:
            resp = SESSION.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table.type_1 tr")
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 5:
                    # 날짜 셀이 첫 번째
                    date_text = cols[0].get_text(strip=True).replace(".", "")
                    date_text = re.sub(r"\D", "", date_text)
                    change_text = cols[4].get_text(strip=True)   # 전일비%
                    change_text = re.sub(r"[^0-9.\-]", "", change_text)
                    if change_text:
                        val = float(change_text)
                        # 등락 방향은 이미지 alt로 판단
                        img = cols[3].select_one("img")
                        if img:
                            alt = img.get("alt", "")
                            if "하락" in alt or "fall" in alt.lower():
                                val = -abs(val)
                            else:
                                val = abs(val)
                        return round(val, 2)
        except Exception as e:
            print(f"   [market_data] 지수 크롤링 오류 ({code}): {e}")
        return 0.0

    kospi  = _fetch("KOSPI")
    kosdaq = _fetch("KOSDAQ")

    def fmt(v):
        return f"{'+' if v >= 0 else ''}{v}%"

    return {
        "kospi":   kospi,
        "kosdaq":  kosdaq,
        "summary": f"코스피 {fmt(kospi)}, 코스닥 {fmt(kosdaq)}",
    }


# ── 섹터 조회 ────────────────────────────────────────
def get_sector(ticker: str) -> str:
    """네이버 금융 종목 정보 페이지에서 업종 파싱"""
    from stages.sector import STATIC_SECTOR_MAP
    # 정적 사전 우선 (빠름)
    if ticker in STATIC_SECTOR_MAP:
        return STATIC_SECTOR_MAP[ticker]
    # 네이버 금융 업종 파싱
    try:
        url  = f"https://finance.naver.com/item/coinfo.naver?code={ticker}"
        resp = SESSION.get(url, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        # 업종 텍스트 위치: table.coinfo_table1 > th[업종] 옆 td
        for row in soup.select("table.coinfo_table1 tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td and "업종" in th.get_text():
                sector = td.get_text(strip=True)
                return _simplify_sector(sector)
    except Exception:
        pass
    return "기타"


def _simplify_sector(raw: str) -> str:
    """네이버 업종명 → 짧은 섹터명"""
    MAP = {
        "반도체": "반도체", "전기·전자": "전자", "자동차": "자동차",
        "방산": "방산", "항공": "항공", "조선": "조선",
        "화학": "화학", "철강": "철강", "건설": "건설",
        "바이오": "바이오", "제약": "제약", "의약": "바이오",
        "금융": "금융", "은행": "은행", "증권": "증권", "보험": "보험",
        "통신": "통신", "미디어": "미디어", "엔터": "엔터",
        "유통": "유통", "음식": "식품", "운송": "물류",
        "에너지": "에너지", "전력": "전력", "2차전지": "2차전지",
        "소프트웨어": "소프트웨어", "IT": "IT",
    }
    for key, val in MAP.items():
        if key in raw:
            return val
    # 너무 길면 앞 4글자만
    return raw[:4] if len(raw) > 6 else raw


# ── 급등/급락 크롤링 ─────────────────────────────────
def _parse_movers_page(url: str, top_n: int) -> list[dict]:
    """
    네이버 금융 급등/급락 페이지 파싱
    반환: [{"ticker", "name", "change", "close"}, ...]
    """
    results = []
    try:
        resp = SESSION.get(url, timeout=10)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        rows = soup.select("table.type_2 tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 8:
                continue

            # 종목 링크에서 ticker 추출
            link = row.select_one("a[href*='code=']")
            if not link:
                continue
            href   = link.get("href", "")
            ticker = re.search(r"code=(\d{6})", href)
            if not ticker:
                continue
            ticker = ticker.group(1)

            name       = link.get_text(strip=True)
            close_text = re.sub(r"[^0-9]", "", cols[1].get_text(strip=True))
            pct_text   = re.sub(r"[^0-9.]", "", cols[5].get_text(strip=True))

            if not close_text or not pct_text:
                continue

            close  = int(close_text)
            change = float(pct_text)

            # 급락 페이지면 음수
            if "sise_fall" in url:
                change = -change

            results.append({
                "ticker": ticker,
                "name":   name,
                "change": change,
                "close":  close,
            })

            if len(results) >= top_n:
                break

    except Exception as e:
        print(f"   [market_data] 크롤링 오류 ({url}): {e}")

    return results


def get_top_movers(date: str) -> dict:
    """
    네이버 금융 급등/급락 페이지 → TOP N 반환
    각 종목에 sector 필드 포함
    """
    top_n = config.TOP_N

    print("   급등주 크롤링...")
    gainers_raw = _parse_movers_page(
        "https://finance.naver.com/sise/sise_rise.naver", top_n
    )

    print("   급락주 크롤링...")
    losers_raw = _parse_movers_page(
        "https://finance.naver.com/sise/sise_fall.naver", top_n
    )

    def enrich(items: list[dict]) -> list[dict]:
        enriched = []
        for item in items:
            time.sleep(0.2)   # 네이버 과부하 방지
            item["sector"] = get_sector(item["ticker"])
            enriched.append(item)
        return enriched

    print("   섹터 조회 중...")
    gainers = enrich(gainers_raw)
    losers  = enrich(losers_raw)

    return {"gainers": gainers, "losers": losers}


# ── 차트 데이터 ──────────────────────────────────────
def get_chart_data(ticker: str, date: str):
    """
    최근 30일 일봉 데이터 — pykrx 단일 종목 조회 (이건 정상 작동)
    실패 시 None 반환
    """
    try:
        start = (
            datetime.strptime(date, "%Y%m%d") - timedelta(days=30)
        ).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, date, ticker)
        return df if (df is not None and not df.empty) else None
    except Exception as e:
        print(f"   [market_data] 차트 데이터 오류 ({ticker}): {e}")
        return None
