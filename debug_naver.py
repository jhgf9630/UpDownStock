"""
네이버 금융 페이지 실제 컬럼 구조 확인
실행: python debug_naver.py
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

def show_table(url: str, label: str):
    print(f"\n{'='*60}")
    print(f"[{label}] {url}")
    print('='*60)
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = soup.select("table.type_2 tr")
    print(f"총 tr 수: {len(rows)}")

    count = 0
    for i, row in enumerate(rows):
        tds = row.select("td")
        if len(tds) < 4:
            continue
        texts = [td.get_text(strip=True) for td in tds]
        links = [a.get("href", "") for a in row.select("a")]
        print(f"\n  tr[{i}] td수={len(tds)}")
        for j, t in enumerate(texts):
            print(f"    cols[{j}] = '{t}'")
        if links:
            print(f"    links = {links[:2]}")
        count += 1
        if count >= 4:   # 첫 4개 데이터 행만
            break

def show_index(url: str, label: str):
    print(f"\n{'='*60}")
    print(f"[{label}] {url}")
    print('='*60)
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    # 다양한 선택자 시도
    for sel in ["table.type_1 tr", "table.type_2 tr", ".sise_area", ".num"]:
        items = soup.select(sel)
        if items:
            print(f"  선택자 '{sel}' → {len(items)}개")
            for item in items[:3]:
                print(f"    텍스트: '{item.get_text(strip=True)[:80]}'")
            break

    # 등락률 관련 텍스트 검색
    print("\n  '등락률' 포함 텍스트:")
    for tag in soup.find_all(string=lambda s: s and "%" in s):
        parent = tag.parent
        print(f"    <{parent.name} class='{parent.get('class', '')}'>: '{tag.strip()}'")
        if len(list(soup.find_all(string=lambda s: s and "%" in s))) > 10:
            break


# ── 실행 ────────────────────────────────────────────
show_table("https://finance.naver.com/sise/sise_rise.naver", "급등")
show_table("https://finance.naver.com/sise/sise_fall.naver", "급락")
show_index("https://finance.naver.com/sise/sise_index.naver?code=KOSPI", "코스피 지수")
