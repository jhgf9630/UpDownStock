# UpDownStock

Automated YouTube Shorts generator for daily stock market gainers & losers.
Covers **KOSPI**, **KOSDAQ**, and **NASDAQ** — produces and uploads videos fully automatically.

---

## Quick Command Reference

```bash
# ── First-time setup ──────────────────────────────────────────
playwright install chromium               # Install browser for Gemini automation
python run.py --stage login               # Save Gemini login session (opens browser)
python -c "from stages.youtube_upload import _get_credentials; _get_credentials()"
                                          # Save YouTube OAuth token (opens browser)

# ── Market data ───────────────────────────────────────────────
python run.py --stage market                          # All markets (kospi+kosdaq+nasdaq)
python run.py --stage market --market kospi           # KOSPI only
python run.py --stage market --market korean          # KOSPI + KOSDAQ
python run.py --stage market --market nasdaq          # NASDAQ only
python run.py --stage market --market kospi --force   # Force refresh (ignore cache)

# ── Script (AI via Gemini web) ────────────────────────────────
python run.py --stage script-init                     # Generate template + print prompt
python run.py --stage script-init --market nasdaq     # NASDAQ only template

# ── TTS ───────────────────────────────────────────────────────
python run.py --stage tts                             # All markets
python run.py --stage tts --market kospi              # KOSPI only
python run.py --stage tts --market kospi --segment gainer_a   # Specific segment only

# ── Images ────────────────────────────────────────────────────
python run.py --stage image                           # All markets
python run.py --stage image --market kosdaq           # KOSDAQ only
python run.py --stage image --market kospi --segment loser_b  # Specific segment only

# ── Video ─────────────────────────────────────────────────────
python run.py --stage video                           # All markets
python run.py --stage video --market nasdaq           # NASDAQ only

# ── Full auto (all stages at once) ───────────────────────────
python run.py --stage all                             # All markets
python run.py --stage all --market kospi              # KOSPI only
python run.py --stage all --market korean             # KOSPI + KOSDAQ
python run.py --stage all --market nasdaq             # NASDAQ only

# ── Upload to YouTube ─────────────────────────────────────────
python scheduler.py --upload-only kospi               # Upload KOSPI video now
python scheduler.py --upload-only kosdaq              # Upload KOSDAQ video now
python scheduler.py --upload-only nasdaq              # Upload NASDAQ video now

# ── Produce + Upload immediately ─────────────────────────────
python scheduler.py --once korean                     # Produce & upload KOSPI + KOSDAQ
python scheduler.py --once nasdaq                     # Produce & upload NASDAQ
python scheduler.py --once all                        # Produce & upload all 3

# ── Produce only (no upload) ──────────────────────────────────
python scheduler.py --produce-only korean
python scheduler.py --produce-only nasdaq

# ── Scheduler (runs 24/7, all automated) ─────────────────────
python scheduler.py                                   # Start background scheduler

# ── Date override (default: latest trading day) ───────────────
python run.py --stage all --market kospi --date 20260401
```

---

## Market Groups

| `--market` | Markets processed |
|---|---|
| `kospi` | KOSPI only |
| `kosdaq` | KOSDAQ only |
| `nasdaq` | NASDAQ only |
| `korean` | KOSPI + KOSDAQ |
| `all` | KOSPI + KOSDAQ + NASDAQ *(default)* |

---

## Auto Schedule (weekdays only)

| Time | Action |
|---|---|
| 05:30 | Produce KOSPI + KOSDAQ videos |
| 06:45 | Upload KOSPI → YouTube |
| 07:15 | Upload KOSDAQ → YouTube |
| 20:00 | Produce NASDAQ video |
| 21:00 | Upload NASDAQ → YouTube |

---

## Installation

### 1. Clone & Install

```bash
git clone <repo-url>
cd UpDownStock
pip install -r requirements.txt
pip install schedule
python -m playwright install chromium
```

### 2. Fonts

Place in `assets/fonts/`:
- `NanumGothic.ttf`
- `NanumGothicBold.ttf`

Download: https://hangeul.naver.com/font  
*(Windows fallback: Malgun Gothic is used automatically if fonts are missing)*

### 3. Background Images (1080×1920 JPG)

Place in `assets/templates/`:

| File | Used for |
|---|---|
| `kospi_intro_bg.jpg` | KOSPI intro screen |
| `kosdaq_intro_bg.jpg` | KOSDAQ intro screen |
| `nasdaq_intro_bg.jpg` | NASDAQ intro screen |
| `gainer_bg.jpg` | All gainer segments |
| `loser_bg.jpg` | All loser segments |
| `outro_bg.jpg` | Outro screen |

### 4. BGM (optional)

Place `bgm.mp3` in `assets/bgm/`. If missing, video is produced without BGM.

### 5. Environment Variables

```bash
# Windows CMD
set GEMINI_API_KEY=AIzaSy...

# Windows PowerShell
$env:GEMINI_API_KEY = "AIzaSy..."

# macOS / Linux
export GEMINI_API_KEY=AIzaSy...
```

Get a free Gemini API key: https://aistudio.google.com/app/apikey  
*(Free tier: 1,500 requests/day — sufficient for daily use)*

---

## YouTube Upload Setup

### Step 1 — Google Cloud Console

```
1. https://console.cloud.google.com
2. Create new project (e.g. UpDownStock)
3. APIs & Services → Library → search "YouTube Data API v3" → Enable
4. APIs & Services → OAuth consent screen
   → External → App name: UpDownStock
   → Test users: add your Gmail
5. APIs & Services → Credentials
   → + CREATE CREDENTIALS → OAuth client ID → Desktop app
   → Download JSON → rename to: youtube_client_secret.json
   → Place in: D:\UpDownStock\
```

### Step 2 — First-time Auth

```bash
python -c "from stages.youtube_upload import _get_credentials; _get_credentials()"
```

Browser opens → Login → Allow → `youtube_token.json` saved automatically.

### Step 3 — Test Upload

```bash
python scheduler.py --upload-only kospi
```

### YouTube Playlists

Videos are automatically added to the matching playlist (auto-created if not exists):

| Market | Playlist |
|---|---|
| KOSPI | 코스피 급등급락 |
| KOSDAQ | 코스닥 급등급락 |
| NASDAQ | 나스닥 급등급락 |

Playlist IDs are cached in `playlist_cache.json` after first use.

---

## Gemini Web Automation Setup

Gemini web automation is used instead of the API to avoid quota costs.

```bash
# Step 1: Install browser
python -m playwright install chromium

# Step 2: Save login session (opens browser window)
python run.py --stage login
# → Log in to Google in the browser
# → Return to terminal → press Enter
# → Session saved to .browser_profile/
```

After login, `--stage all` runs fully automatically without manual intervention.

---

## Project Structure

```
UpDownStock/
├── run.py                    ← Main CLI (stage-by-stage execution)
├── scheduler.py              ← Auto scheduler (produce + upload)
├── config.py                 ← All settings (paths, API keys, schedules)
├── requirements.txt
├── youtube_client_secret.json  ← Google OAuth secret (you add this)
├── youtube_token.json          ← Auto-generated after first auth
├── playlist_cache.json         ← Auto-generated playlist ID cache
├── .browser_profile/           ← Gemini login session (auto-generated)
├── stages/
│   ├── market_data.py        # Naver Finance (KR) + Yahoo Finance (NASDAQ)
│   ├── sector.py             # Static sector dictionary (fallback)
│   ├── script_gen.py         # Gemini web automation → JSON script
│   ├── playwright_worker.py  # Playwright subprocess worker
│   ├── image_gen.py          # Pillow + matplotlib image generation
│   ├── tts_gen.py            # gTTS → WAV conversion
│   ├── video_build.py        # FFmpeg pipeline
│   └── youtube_upload.py     # YouTube Data API v3 upload
├── assets/
│   ├── fonts/                ← NanumGothic (you add these)
│   ├── bgm/                  ← bgm.mp3 (you add this)
│   └── templates/            ← Background images (you add these)
└── output/
    └── YYYYMMDD/
        ├── market.json         ← Market data cache
        ├── script.json         ← AI-generated script
        ├── kospi/
        │   └── 260401 코스피 급등급락.mp4
        ├── kosdaq/
        │   └── 260401 코스닥 급등급락.mp4
        └── nasdaq/
            └── 260401 나스닥 급등급락.mp4
```

---

## Video Structure (~30 seconds at 1.5× speed)

| Segment | Screen | Narration |
|---|---|---|
| Intro | Fixed background + date | "긴 말 안 한다! 어제 코스피 급등급락, 딱 30초 컷으로 보고 가!" |
| Gainer announce | Gainer background | "급등 내용입니다." |
| Gainer list | TOP 3 cards | Sector theme summary |
| Gainer A/B/C | Stock chart | Stock name + reason |
| Loser announce | Loser background | "급락 내용입니다." |
| Loser list | TOP 3 cards | Sector theme summary |
| Loser A/B/C | Stock chart | Stock name + reason |
| Outro | Fixed background + date | "내일 아침 7시, 다음 급등주 놓치기 싫으면 구독!" |

---

## Data Pipeline

```
Naver Finance (KR gainers/losers)
Yahoo Finance (NASDAQ gainers/losers)
    ↓
market.json  (cached per date)
    ↓
Gemini Web (script template → filled JSON)
    ↓
script.json
    ↓
gTTS → WAV  +  Pillow/matplotlib → JPG
    ↓
FFmpeg: clips → concat → 1.5× speed → BGM mix → MP4
    ↓
YouTube Data API v3 → upload + playlist
```

---

## Tech Stack

| Purpose | Tool | Cost |
|---|---|---|
| KR market data | Naver Finance (crawling) | Free |
| NASDAQ data | Yahoo Finance API | Free |
| KR chart data | pykrx | Free |
| NASDAQ chart data | yfinance | Free |
| AI script | Gemini web automation | Free |
| TTS | gTTS (Google TTS) | Free |
| Image generation | Pillow + matplotlib | Free |
| Video synthesis | FFmpeg | Free |
| Browser automation | Playwright | Free |
| YouTube upload | YouTube Data API v3 | Free (quota-based) |
