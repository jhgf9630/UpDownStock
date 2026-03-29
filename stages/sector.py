"""
섹터 정보 조회
1순위: pykrx WICS 분류 (KRX 공식)
2순위: 정적 사전 fallback
"""
from __future__ import annotations
from pykrx import stock
import pandas as pd

# ── 정적 fallback 사전 ───────────────────────────────
STATIC_SECTOR_MAP: dict[str, str] = {
    # 반도체
    "005930": "반도체", "000660": "반도체", "058470": "반도체",
    "042700": "반도체", "091990": "반도체", "240810": "반도체",
    # 2차전지
    "006400": "2차전지", "373220": "2차전지", "247540": "2차전지",
    "086520": "2차전지", "003670": "2차전지", "305720": "2차전지",
    # 자동차
    "005380": "자동차", "000270": "자동차", "012330": "자동차",
    "204320": "자동차", "011210": "자동차",
    # 방산
    "012450": "방산",   "047050": "방산",   "003550": "방산",
    "064350": "방산",   "272210": "방산",
    # IT/플랫폼
    "035420": "IT플랫폼", "035720": "IT플랫폼", "259960": "IT플랫폼",
    "293490": "IT플랫폼", "263750": "IT플랫폼",
    # 바이오/제약
    "068270": "바이오", "207940": "바이오", "128940": "바이오",
    "326030": "바이오", "302440": "바이오",
    # 금융
    "105560": "금융",   "055550": "금융",   "086790": "금융",
    "316140": "금융",   "024110": "금융",   "138930": "금융",
    # 철강/소재
    "005490": "철강",   "004020": "철강",   "010130": "철강",
    # 에너지/화학
    "010950": "에너지", "011170": "화학",   "051910": "화학",
    "096770": "에너지",
    # 건설
    "000720": "건설",   "006360": "건설",   "047040": "건설",
    # 유통/소비
    "004170": "유통",   "023530": "유통",   "139480": "유통",
    # 엔터/미디어
    "035900": "엔터",   "041510": "엔터",   "352820": "엔터",
    "122870": "엔터",
    # 항공/물류
    "003490": "항공",   "020560": "항공",   "086280": "물류",
    # 조선
    "009540": "조선",   "010140": "조선",   "042660": "조선",
    # 통신
    "017670": "통신",   "030200": "통신",   "032640": "통신",
    # 디스플레이
    "034220": "디스플레이", "067160": "디스플레이",
}

# WICS 세부 업종 → 한국어 섹터명
WICS_DETAIL_KR: dict[str, str] = {
    "Semiconductors": "반도체",
    "Semiconductor Equipment": "반도체장비",
    "Electronic Equipment": "전자장비",
    "Technology Hardware": "IT하드웨어",
    "Software": "소프트웨어",
    "Internet": "인터넷",
    "Media & Entertainment": "엔터",
    "Automobiles": "자동차",
    "Auto Components": "자동차부품",
    "Aerospace & Defense": "방산",
    "Machinery": "기계",
    "Shipbuilding": "조선",
    "Steel": "철강",
    "Chemicals": "화학",
    "Pharmaceuticals": "제약",
    "Biotechnology": "바이오",
    "Banks": "은행",
    "Insurance": "보험",
    "Capital Markets": "증권",
    "Electric Utilities": "전력",
    "Oil Gas & Consumable Fuels": "에너지",
    "Food & Beverage": "식품음료",
    "Retailing": "유통",
    "Air Freight & Logistics": "물류",
    "Airlines": "항공",
    "Construction": "건설",
    "Real Estate": "부동산",
    "Wireless Telecommunication": "통신",
    "Diversified Telecommunication": "통신",
    "Batteries": "2차전지",
    "Display": "디스플레이",
}

WICS_BROAD_KR: dict[str, str] = {
    "Energy": "에너지",
    "Materials": "소재",
    "Industrials": "산업재",
    "Consumer Discretionary": "경기소비재",
    "Consumer Staples": "필수소비재",
    "Health Care": "헬스케어",
    "Financials": "금융",
    "Information Technology": "IT",
    "Communication Services": "통신서비스",
    "Utilities": "유틸리티",
    "Real Estate": "부동산",
}


def _safe_wics(date: str, market: str) -> dict[str, str]:
    """
    WICS 섹터 조회. pykrx 버전 이슈로 실패할 수 있으므로
    모든 예외를 잡아 빈 딕셔너리 반환.
    """
    try:
        df = stock.get_market_sector_classifications(date, market)
        if df is None or (hasattr(df, "empty") and df.empty):
            return {}

        result: dict[str, str] = {}

        # 실제 컬럼 확인 후 처리
        cols = df.columns.tolist() if hasattr(df, "columns") else []

        # 티커 컬럼 후보
        ticker_col = None
        for c in ["티커", "종목코드", "Symbol", "Ticker"]:
            if c in cols:
                ticker_col = c
                break

        # 업종명 컬럼 후보
        sector_col = None
        for c in ["SEC_NM_KOR", "업종명", "섹터", "Sector"]:
            if c in cols:
                sector_col = c
                break

        broad_col = None
        for c in ["IDX_NM_KOR", "대분류", "Industry"]:
            if c in cols:
                broad_col = c
                break

        if ticker_col is None or sector_col is None:
            return {}

        for _, row in df.iterrows():
            ticker = str(row.get(ticker_col, "")).strip()
            detail = str(row.get(sector_col, "")).strip()
            broad  = str(row.get(broad_col, "")) if broad_col else ""

            sector_kr = (
                WICS_DETAIL_KR.get(detail)
                or detail
                or WICS_BROAD_KR.get(broad)
                or broad
                or "기타"
            )
            if ticker:
                result[ticker] = sector_kr

        return result

    except Exception as e:
        print(f"   [sector] WICS 조회 실패 ({market}): {e}")
        return {}


def build_sector_map(date: str) -> dict[str, str]:
    """
    KOSPI + KOSDAQ 전체 섹터 맵 반환.
    WICS 실패 시 정적 사전만 사용.
    """
    sector_map: dict[str, str] = {}
    for market in ("KOSPI", "KOSDAQ"):
        wics = _safe_wics(date, market)
        sector_map.update(wics)

    if not sector_map:
        print("   [sector] WICS 전체 실패 → 정적 사전 사용")

    return sector_map


def get_sector(ticker: str, sector_map: dict[str, str]) -> str:
    """
    1순위: WICS 맵
    2순위: 정적 사전
    3순위: "기타"
    """
    return (
        sector_map.get(ticker)
        or STATIC_SECTOR_MAP.get(ticker)
        or "기타"
    )
