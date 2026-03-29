import os
from pathlib import Path

BASE_DIR  = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Claude API ──────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")

# ── 폰트 (NanumGothic 권장) ─────────────────────────
FONT_BOLD    = str(ASSETS_DIR / "fonts" / "NanumGothicBold.ttf")
FONT_REGULAR = str(ASSETS_DIR / "fonts" / "NanumGothic.ttf")

# ── 배경 이미지 (직접 제작 후 저장) ────────────────────
INTRO_BG   = str(ASSETS_DIR / "templates" / "intro_bg.jpg")
GAINER_BG  = str(ASSETS_DIR / "templates" / "gainer_bg.jpg")
LOSER_BG   = str(ASSETS_DIR / "templates" / "loser_bg.jpg")
OUTRO_BG   = str(ASSETS_DIR / "templates" / "outro_bg.jpg")

# ── BGM ─────────────────────────────────────────────
BGM_PATH = str(ASSETS_DIR / "bgm" / "bgm.mp3")

# ── 영상 규격 ────────────────────────────────────────
VIDEO_W = 1080
VIDEO_H = 1920
FPS     = 30
SPEED   = 1.5   # 최종 배속

# ── TTS ─────────────────────────────────────────────
# ko-KR-SunHiNeural (여성) / ko-KR-InJoonNeural (남성)
TTS_VOICE = "ko-KR-SunHiNeural"
TTS_PITCH = "-3Hz"

# ── 시장 데이터 ──────────────────────────────────────
TOP_N = 3   # 급등/급락 각 상위 N개

# ── 레이아웃 (비율 → 픽셀) ───────────────────────────
HEADER_TOP    = 0
HEADER_BOTTOM = int(VIDEO_H * 0.18)   # ~346px
CAPTION_TOP   = int(VIDEO_H * 0.20)   # ~384px
CAPTION_BOTTOM= int(VIDEO_H * 0.35)   # ~672px
MEDIA_TOP     = int(VIDEO_H * 0.37)   # ~710px
MEDIA_BOTTOM  = int(VIDEO_H * 0.90)   # ~1728px
