# UpDownStock

코스피·코스닥 급등락 종목을 자동으로 수집해 유튜브 쇼츠 영상 2개를 생성하는 봇입니다.

---

## 결과물

```
output/20260401/
├── market.json                       ← 시장 데이터 캐시
├── script.json                       ← 두 영상 스크립트 (수동 편집 가능)
├── kospi/
│   └── 260401 코스피 급등급락.mp4
└── kosdaq/
    └── 260401 코스닥 급등급락.mp4
```

---

## 영상 구성

| 세그먼트 | 화면 | 나레이션 |
|---|---|---|
| 인트로 | 고정 배경 + 날짜 | "긴 말 안 한다! 어제 코스피/코스닥 급등급락, 딱 30초 컷으로 보고 가!" |
| 급등 안내 | 급등 리스트 배경 | "급등 내용입니다." |
| 급등 리스트 | 급등 TOP3 카드 | 급등 종목 리스트 캡션 |
| 급등 A/B/C | 개별 차트 | "종목명. 이유 한 줄" |
| 급락 안내 | 급락 리스트 배경 | "급락 내용입니다." |
| 급락 리스트 | 급락 TOP3 카드 | 급락 종목 리스트 캡션 |
| 급락 A/B/C | 개별 차트 | "종목명. 이유 한 줄" |
| 아웃트로 | 고정 배경 + 날짜 | "내일 아침 7시, 다음 급등주 놓치기 싫으면 구독!" |

최종 영상: **1.5배속** 적용, 약 30초

---

## 사전 준비

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

FFmpeg (별도 설치):
```bash
# Windows: https://ffmpeg.org/download.html 에서 다운로드 후 PATH 등록
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
```

### 2. 폰트 배치

`assets/fonts/` 에 복사:
- `NanumGothic.ttf`
- `NanumGothicBold.ttf`

> 다운로드: https://hangeul.naver.com/font
>
> 없으면 Windows 맑은 고딕(`malgun.ttf`)을 자동으로 사용합니다.

### 3. 배경 이미지 배치 (1080×1920 JPG)

`assets/templates/` 에 직접 제작 후 저장:

| 파일명 | 용도 |
|---|---|
| `kospi_intro_bg.jpg` | 코스피 영상 인트로 |
| `kosdaq_intro_bg.jpg` | 코스닥 영상 인트로 |
| `gainer_bg.jpg` | 급등 세그먼트 공용 배경 |
| `loser_bg.jpg` | 급락 세그먼트 공용 배경 |
| `outro_bg.jpg` | 아웃트로 공용 배경 |

### 4. BGM 배치 (선택)

`assets/bgm/bgm.mp3` — 없으면 BGM 없이 생성됩니다.

### 5. API 키 설정

```bash
# .env 파일 생성
cp .env.example .env
# ANTHROPIC_API_KEY 입력 후 저장

# 환경변수 로드 (매 실행 전)
# Windows PowerShell:
$env:ANTHROPIC_API_KEY = "your_key_here"
# Windows CMD:
set ANTHROPIC_API_KEY=your_key_here
# macOS/Linux:
export ANTHROPIC_API_KEY=your_key_here
```

---

## 실행 방법

### 단계별 수동 실행 (권장)

```bash
# 1. 시장 데이터 수집
python run.py --stage market

# 2. 스크립트 템플릿 생성
#    → 터미널에 웹 AI용 프롬프트 출력됨
python run.py --stage script-init

# 3. 출력된 프롬프트를 Claude/ChatGPT 웹에 붙여넣기
#    → 응답 JSON을 복사해 output/YYYYMMDD/script.json 덮어쓰기

# 4. TTS 생성 (KOSPI + KOSDAQ)
python run.py --stage tts

# 5. 이미지 생성
python run.py --stage image

# 6. 영상 합성
python run.py --stage video
```

### 전체 자동 실행 (Claude API 사용)

```bash
python run.py --stage all
```

API를 1회 호출해 코스피·코스닥 두 영상의 스크립트를 동시에 생성합니다.

---

## 옵션

| 옵션 | 설명 | 예시 |
|---|---|---|
| `--date` | 날짜 수동 지정 | `--date 20260401` |
| `--market` | 특정 시장만 처리 | `--market kospi` |
| `--segment` | 특정 세그먼트만 재작업 | `--segment gainer_a` |
| `--force` | 캐시 무시 재수집 | `--force` (market 단계) |

### 부분 재작업 예시

```bash
# script.json 수정 후 코스피 TTS만 재생성
python run.py --stage tts --market kospi

# 특정 세그먼트만 이미지 재생성
python run.py --stage image --market kosdaq --segment gainer_a

# 영상만 재합성
python run.py --stage video --market kospi
```

---

## 프로젝트 구조

```
UpDownStock/
├── run.py                    ← 단계별 실행 CLI
├── main.py                   ← 전체 자동 실행
├── config.py                 ← 경로·설정 모음
├── requirements.txt
├── .env.example
├── stages/
│   ├── market_data.py        # 네이버 금융 크롤링 (코스피/코스닥 분리)
│   ├── sector.py             # 섹터 정적 사전 (fallback)
│   ├── script_gen.py         # 스크립트 템플릿 + Claude API
│   ├── image_gen.py          # Pillow + matplotlib 이미지 생성
│   ├── tts_gen.py            # gTTS → WAV 변환 (재시도 5회)
│   └── video_build.py        # FFmpeg 파이프라인
├── assets/
│   ├── fonts/                ← NanumGothic.ttf 등 (직접 추가)
│   ├── bgm/                  ← bgm.mp3 (직접 추가)
│   └── templates/            ← 배경 이미지 5종 (직접 추가)
└── output/
    └── YYYYMMDD/
        ├── market.json
        ├── script.json
        ├── kospi/
        │   └── YYMMDD 코스피 급등급락.mp4
        └── kosdaq/
            └── YYMMDD 코스닥 급등급락.mp4
```

---

## 데이터 흐름

```
네이버 금융 (급등/급락 페이지)
    ↓ 크롤링
market.json (KOSPI + KOSDAQ 통합 캐시)
    ↓ 템플릿 생성
script.json (웹 AI 또는 Claude API로 채움)
    ↓ 시장별 분리
TTS (gTTS → WAV, 세그먼트당 1개)
이미지 (Pillow + matplotlib, 세그먼트당 1개)
    ↓ FFmpeg
클립 합성 → 1.5배속 → BGM 믹싱 → 최종 MP4
```

---

## 자동 실행 스케줄링 (선택)

평일 오전 6시에 자동 실행 → 7시 업로드 타이밍:

```bash
# Windows 작업 스케줄러 또는 cron (macOS/Linux)
# macOS/Linux crontab -e:
0 6 * * 1-5 cd /path/to/UpDownStock && python run.py --stage all
```

---

## 주요 기술 스택

| 용도 | 라이브러리 |
|---|---|
| 크롤링 | requests, BeautifulSoup4 |
| 주가 데이터 | pykrx (차트용 단일 종목만 사용) |
| AI 스크립트 | anthropic (Claude API) |
| 이미지 생성 | Pillow, matplotlib |
| TTS | gTTS (Google TTS, 무료) |
| 영상 합성 | FFmpeg |
