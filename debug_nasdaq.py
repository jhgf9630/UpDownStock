"""
나스닥 데이터 수집 디버그
실행: python debug_nasdaq.py
"""
import requests
import json

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

session = requests.Session()
session.headers.update(HEADERS)

# ── 1. 기존 스크리너 API ───────────────────────────
print("=" * 60)
print("[1] 기존 스크리너 API (predefined/saved)")
url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
params = {
    "scrIds":    "day_gainers",
    "count":     10,
    "formatted": "false",
    "lang":      "en-US",
    "region":    "US",
}
try:
    r = session.get(url, params=params, timeout=12)
    print(f"  status: {r.status_code}")
    data = r.json()
    result = data.get("finance", {}).get("result", [])
    if result:
        quotes = result[0].get("quotes", [])
        print(f"  quotes 수: {len(quotes)}")
        if quotes:
            print(f"  첫 번째: {json.dumps(quotes[0], indent=2)[:300]}")
    else:
        print(f"  응답 원문 (앞 500자): {r.text[:500]}")
except Exception as e:
    print(f"  오류: {e}")

# ── 2. v2 screener API ────────────────────────────
print()
print("=" * 60)
print("[2] v2 screener API")
url2 = "https://query1.finance.yahoo.com/v2/finance/screener"
params2 = {
    "scrIds":    "day_gainers",
    "count":     10,
    "formatted": "false",
    "lang":      "en-US",
    "region":    "US",
}
try:
    r2 = session.get(url2, params=params2, timeout=12)
    print(f"  status: {r2.status_code}")
    print(f"  응답 앞 500자: {r2.text[:500]}")
except Exception as e:
    print(f"  오류: {e}")

# ── 3. Yahoo Finance 트렌딩 / 무버 페이지 ──────────
print()
print("=" * 60)
print("[3] market-summary API")
url3 = "https://query1.finance.yahoo.com/v6/finance/quote/marketSummary"
try:
    r3 = session.get(url3, timeout=12)
    print(f"  status: {r3.status_code}")
    print(f"  응답 앞 500자: {r3.text[:500]}")
except Exception as e:
    print(f"  오류: {e}")

# ── 4. yfinance 라이브러리로 직접 ─────────────────
print()
print("=" * 60)
print("[4] yfinance download 테스트 (AAPL 5일)")
try:
    import yfinance as yf
    df = yf.download("AAPL", period="5d", interval="1d", progress=False)
    print(f"  컬럼: {df.columns.tolist()}")
    print(f"  행 수: {len(df)}")
    print(df.tail(3))
except Exception as e:
    print(f"  오류: {e}")

# ── 5. yfinance Ticker 정보 ────────────────────────
print()
print("=" * 60)
print("[5] yfinance Ticker fast_info (AAPL)")
try:
    import yfinance as yf
    t = yf.Ticker("AAPL")
    fi = t.fast_info
    print(f"  last_price: {fi.last_price}")
    print(f"  previous_close: {fi.previous_close}")
except Exception as e:
    print(f"  오류: {e}")
