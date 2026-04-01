import os
from pathlib import Path

BASE_DIR   = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")

FONT_BOLD    = str(ASSETS_DIR / "fonts" / "NanumGothicBold.ttf")
FONT_REGULAR = str(ASSETS_DIR / "fonts" / "NanumGothic.ttf")

# 배경 이미지 — 시장별 intro 분리
INTRO_BG_KOSPI  = str(ASSETS_DIR / "templates" / "kospi_intro_bg.jpg")
INTRO_BG_KOSDAQ = str(ASSETS_DIR / "templates" / "kosdaq_intro_bg.jpg")
GAINER_BG       = str(ASSETS_DIR / "templates" / "gainer_bg.jpg")
LOSER_BG        = str(ASSETS_DIR / "templates" / "loser_bg.jpg")
OUTRO_BG        = str(ASSETS_DIR / "templates" / "outro_bg.jpg")

# 하위 호환
INTRO_BG = INTRO_BG_KOSPI

BGM_PATH = str(ASSETS_DIR / "bgm" / "bgm.mp3")

VIDEO_W = 1080
VIDEO_H = 1920
FPS     = 30
SPEED   = 1.5

TTS_VOICE = "ko-KR-SunHiNeural"
TTS_PITCH = "-3Hz"
TTS_LANG  = "ko"

TOP_N = 3

HEADER_TOP    = 0
HEADER_BOTTOM = int(VIDEO_H * 0.15)
CAPTION_TOP   = int(VIDEO_H * 0.17)
CAPTION_BOTTOM= int(VIDEO_H * 0.32)
MEDIA_TOP     = int(VIDEO_H * 0.34)
MEDIA_BOTTOM  = int(VIDEO_H * 0.92)
