"""
pykrx가 실제로 반환하는 컬럼명 확인용 디버그 스크립트
실행: python debug_columns.py
"""
from pykrx import stock
from datetime import datetime, timedelta

# 가장 최근 거래일 탐색
date = None
for i in range(10):
    d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
    try:
        df = stock.get_market_ohlcv_by_date(d, d, "005930")
        if not df.empty:
            date = d
            break
    except Exception:
        continue

if not date:
    print("거래일 탐색 실패")
    exit()

print(f"기준 날짜: {date}\n")

# ── 1. 종목별 OHLCV ──────────────────────────────────
print("=" * 50)
print("[1] get_market_ohlcv_by_ticker (KOSPI)")
try:
    df = stock.get_market_ohlcv_by_ticker(date, market="KOSPI")
    print(f"  컬럼: {df.columns.tolist()}")
    print(f"  인덱스명: {df.index.name}")
    print(df.head(3).to_string())
except Exception as e:
    print(f"  오류: {e}")

# ── 2. 지수 OHLCV ────────────────────────────────────
print("\n" + "=" * 50)
print("[2] get_index_ohlcv_by_date (코스피 1001)")
try:
    df2 = stock.get_index_ohlcv_by_date(date, date, "1001")
    print(f"  컬럼: {df2.columns.tolist()}")
    print(df2.to_string())
except Exception as e:
    print(f"  오류: {e}")

# ── 3. 섹터 분류 ─────────────────────────────────────
print("\n" + "=" * 50)
print("[3] get_market_sector_classifications (KOSPI)")
try:
    df3 = stock.get_market_sector_classifications(date, "KOSPI")
    print(f"  컬럼: {df3.columns.tolist()}")
    print(df3.head(3).to_string())
except Exception as e:
    print(f"  오류: {e}")

# ── 4. 단일 종목 일봉 ────────────────────────────────
print("\n" + "=" * 50)
print("[4] get_market_ohlcv_by_date (삼성전자 005930)")
try:
    df4 = stock.get_market_ohlcv_by_date(date, date, "005930")
    print(f"  컬럼: {df4.columns.tolist()}")
    print(df4.to_string())
except Exception as e:
    print(f"  오류: {e}")
