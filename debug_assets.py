"""
에셋 경로 및 파일 존재 여부 확인
실행: python debug_assets.py
"""
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent
print(f"BASE_DIR: {BASE_DIR}")
print()

# ── 폴더 구조 ────────────────────────────────────────
folders = [
    BASE_DIR / "assets" / "fonts",
    BASE_DIR / "assets" / "bgm",
    BASE_DIR / "assets" / "templates",
]
for folder in folders:
    print(f"[폴더] {folder}")
    print(f"  존재: {folder.exists()}")
    if folder.exists():
        files = list(folder.iterdir())
        if files:
            for f in files:
                print(f"  파일: {f.name}  ({f.stat().st_size:,} bytes)")
        else:
            print("  (비어 있음)")
    print()

# ── config 경로 확인 ─────────────────────────────────
print("=" * 50)
print("config.py 경로 값:")
import config
attrs = [
    "FONT_BOLD", "FONT_REGULAR",
    "INTRO_BG", "GAINER_BG", "LOSER_BG", "OUTRO_BG",
    "BGM_PATH",
]
for attr in attrs:
    val = getattr(config, attr, "미정의")
    exists = Path(val).exists() if val != "미정의" else False
    mark = "✅" if exists else "❌"
    print(f"  {mark} {attr} = {val}")

# ── Pillow 폰트 로드 테스트 ───────────────────────────
print()
print("=" * 50)
print("Pillow 폰트 로드 테스트:")
from PIL import ImageFont
for attr in ["FONT_BOLD", "FONT_REGULAR"]:
    path = getattr(config, attr, "")
    try:
        font = ImageFont.truetype(path, 40)
        print(f"  ✅ {attr} 로드 성공")
    except Exception as e:
        print(f"  ❌ {attr} 로드 실패: {e}")

# ── matplotlib 폰트 확인 ─────────────────────────────
print()
print("=" * 50)
print("시스템 한국어 폰트 탐색:")
import matplotlib.font_manager as fm
korean_fonts = []
for f in fm.fontManager.ttflist:
    if any(k in f.name for k in ["Nanum", "Malgun", "Gothic", "나눔", "맑은"]):
        korean_fonts.append((f.name, f.fname))

if korean_fonts:
    for name, path in korean_fonts[:5]:
        print(f"  {name}: {path}")
else:
    print("  한국어 폰트 없음 — 자막 깨짐 원인")
    # Windows 기본 폰트 확인
    win_fonts = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
    ]
    print("\n  Windows 기본 폰트 확인:")
    for p in win_fonts:
        exists = Path(p).exists()
        print(f"  {'✅' if exists else '❌'} {p}")
