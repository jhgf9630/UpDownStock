"""
1단계: 네이버 금융 크롤링으로 급등/급락 TOP N 수집

참조 URL:
  급등: https://finance.naver.com/sise/sise_rise.naver
  급락: https://finance.naver.com/sise/sise_fall.naver
  지수: https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KOSPI
  섹터: https://finance.naver.com/item/coinfo.naver?code={ticker}

컬럼 구조 (debug_naver.py 확인 결과):
  cols[0]  = 순위
  cols[1]  = 종목명
  cols[2]  = 현재가
  cols[3]  = 전일비 (상승/하락 텍스트 포함)
  cols[4]  = 등락률 (+22.58%)
  cols[5]  = 거래량
  cols[6~] = 기타
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


# ── ETN/레버리지/인버스 필터 키워드 ─────────────────
EXCLUDE_KEYWORDS = [
    "ETN", "ETF", "레버리지", "인버스", "2X", "선물",
    "KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO",
    "KOSEF", "FOCUS", "SOL", "ACE", "TIMEFOLIO",
    "TR ETN", "TOP5", "TOP10",
]


def _is_excluded(name: str) -> bool:
    return any(kw in name for kw in EXCLUDE_KEYWORDS)


# ── 최근 거래일 ──────────────────────────────────────
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


# ── 지수 등락률 (polling API) ────────────────────────
def _fetch_index_change(code: str) -> float:
    """
    네이버 polling API로 코스피/코스닥 등락률 조회
    code: 'KOSPI' 또는 'KOSDAQ'
    """
    url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:{code}"
    try:
        resp = SESSION.get(url, timeout=8)
        data = resp.json()

        areas = data.get("result", {}).get("areas", [])
        for area in areas:
            if area.get("name") == "SERVICE_INDEX":
                item = area.get("datas", [{}])[0]
                # cr = change rate (등락률, 단위: %)
                cr = item.get("cr", 0)
                return round(float(cr), 2)
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


# ── 섹터 조회 ────────────────────────────────────────
def get_sector(ticker: str) -> str:
    from stages.sector import STATIC_SECTOR_MAP
    if ticker in STATIC_SECTOR_MAP:
        return STATIC_SECTOR_MAP[ticker]
    try:
        url  = f"https://finance.naver.com/item/coinfo.naver?code={ticker}"
        resp = SESSION.get(url, timeout=8)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.select("table.coinfo_table1 tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td and "업종" in th.get_text():
                return _simplify_sector(td.get_text(strip=True))
    except Exception:
        pass
    return "기타"


def _simplify_sector(raw: str) -> str:
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
    return raw[:5] if len(raw) > 5 else raw


# ── 급등/급락 크롤링 ─────────────────────────────────
def _parse_movers_page(url: str, is_gainer: bool, top_n: int) -> list[dict]:
    """
    컬럼 구조:
      cols[1] = 종목명
      cols[2] = 현재가
      cols[4] = 등락률 (예: '+22.58%' 또는 '-13.73%')
    """
    results = []
    page = 1

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

                # 종목 링크 & ticker 추출
                link_tag = row.select_one("a[href*='code=']")
                if not link_tag:
                    continue

                href   = link_tag.get("href", "")
                m      = re.search(r"code=(\d{6})", href)
                if not m:
                    continue
                ticker = m.group(1)

                name = link_tag.get_text(strip=True)

                # ETN/레버리지 필터
                if _is_excluded(name):
                    continue

                # 현재가 (cols[2])
                close_text = re.sub(r"[^0-9]", "", tds[2].get_text(strip=True))
                if not close_text:
                    continue

                # 등락률 (cols[4]: '+22.58%' 형태)
                pct_raw  = tds[4].get_text(strip=True)
                pct_text = re.sub(r"[^0-9.\-\+]", "", pct_raw)
                if not pct_text:
                    continue

                change = float(pct_text)
                # 급락 페이지는 음수로
                if not is_gainer:
                    change = -abs(change)
                else:
                    change = abs(change)

                results.append({
                    "ticker": ticker,
                    "name":   name,
                    "change": round(change, 2),
                    "close":  int(close_text),
                })
                found_this_page += 1

                if len(results) >= top_n:
                    break

            # 더 이상 데이터 없으면 중단
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
    gainers_raw = _parse_movers_page(
        "https://finance.naver.com/sise/sise_rise.naver", True, top_n
    )

    print("   급락주 크롤링...")
    losers_raw = _parse_movers_page(
        "https://finance.naver.com/sise/sise_fall.naver", False, top_n
    )

    def enrich(items: list[dict]) -> list[dict]:
        enriched = []
        for item in items:
            time.sleep(0.15)
            item["sector"] = get_sector(item["ticker"])
            enriched.append(item)
        return enriched

    print("   섹터 조회 중...")
    gainers = enrich(gainers_raw)
    losers  = enrich(losers_raw)

    return {"gainers": gainers, "losers": losers}


# ── 차트 데이터 ──────────────────────────────────────
def get_chart_data(ticker: str, date: str):
    """최근 30일 일봉 — pykrx 단일 종목 조회 (정상 작동)"""
    try:
        start = (
            datetime.strptime(date, "%Y%m%d") - timedelta(days=30)
        ).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, date, ticker)
        return df if (df is not None and not df.empty) else None
    except Exception as e:
        print(f"   [market_data] 차트 데이터 오류 ({ticker}): {e}")
        return None
