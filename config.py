import os
from pathlib import Path

BASE_DIR   = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── AI API ───────────────────────────────────────────
# Gemini (무료 티어 사용 권장)
# 키 발급: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY_HERE")
GEMINI_MODEL   = "gemini-2.0-flash-lite"   # 무료 티어: 일 1500회 (flash보다 할당량 넉넉)

# Claude (선택적, 유료)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# OpenAI (선택적, 유료)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o"

# ── 폰트 ────────────────────────────────────────────
FONT_BOLD    = str(ASSETS_DIR / "fonts" / "NanumGothicBold.ttf")
FONT_REGULAR = str(ASSETS_DIR / "fonts" / "NanumGothic.ttf")

# ── 배경 이미지 ──────────────────────────────────────
INTRO_BG_KOSPI  = str(ASSETS_DIR / "templates" / "kospi_intro_bg.jpg")
INTRO_BG_KOSDAQ = str(ASSETS_DIR / "templates" / "kosdaq_intro_bg.jpg")
INTRO_BG_NASDAQ = str(ASSETS_DIR / "templates" / "nasdaq_intro_bg.jpg")
INTRO_BG        = INTRO_BG_KOSPI

GAINER_BG = str(ASSETS_DIR / "templates" / "gainer_bg.jpg")
LOSER_BG  = str(ASSETS_DIR / "templates" / "loser_bg.jpg")
OUTRO_BG  = str(ASSETS_DIR / "templates" / "outro_bg.jpg")

# ── BGM ─────────────────────────────────────────────
BGM_PATH = str(ASSETS_DIR / "bgm" / "bgm.mp3")

# ── 영상 규격 ────────────────────────────────────────
VIDEO_W = 1080
VIDEO_H = 1920
FPS     = 30
SPEED   = 1.5

# ── TTS ─────────────────────────────────────────────
TTS_LANG  = "ko"
TTS_VOICE = "ko-KR-SunHiNeural"
TTS_PITCH = "-3Hz"

# ── 시장 데이터 ──────────────────────────────────────
TOP_N          = 3
MARKETS_KOREAN = ["kospi", "kosdaq"]
MARKETS_ALL    = ["kospi", "kosdaq", "nasdaq"]

# ── 레이아웃 ─────────────────────────────────────────
HEADER_TOP     = 0
HEADER_BOTTOM  = int(VIDEO_H * 0.18)
CAPTION_TOP    = int(VIDEO_H * 0.20)
CAPTION_BOTTOM = int(VIDEO_H * 0.35)
MEDIA_TOP      = int(VIDEO_H * 0.37)
MEDIA_BOTTOM   = int(VIDEO_H * 0.90)

# ── YouTube 업로드 ───────────────────────────────────
# OAuth2 클라이언트 시크릿 파일 경로
# Google Cloud Console에서 다운로드한 JSON 파일
YOUTUBE_CLIENT_SECRET = str(BASE_DIR / "youtube_client_secret.json")

# 업로드 설정
YOUTUBE_CATEGORY_ID  = "25"    # News & Politics
YOUTUBE_PRIVACY      = "public"  # public / unlisted / private
YOUTUBE_LANGUAGE     = "ko"

# 시장별 업로드 스케줄 (HH:MM, 24시간)
UPLOAD_SCHEDULE = {
    "kospi":  "06:45",
    "kosdaq": "07:15",
    "nasdaq": "21:00",
}

# 영상 제작 스케줄 (업로드보다 충분히 앞서 실행)
# 한국 시장: 전일 장 마감 후 새벽 제작
# 나스닥: 당일 오후 제작
PRODUCE_SCHEDULE = {
    "korean": "05:30",   # 코스피+코스닥 동시 제작
    "nasdaq": "20:00",   # 나스닥 제작
}
