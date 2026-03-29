# shorts-bot

주식 시장 급등/급락 종목을 자동 분석해 유튜브 쇼츠 영상을 생성하는 봇.

---

## 사전 준비

### 1. 의존성 설치
```bash
pip install -r requirements.txt
sudo apt install ffmpeg   # Ubuntu
# brew install ffmpeg     # macOS
```

### 2. 폰트 배치
`assets/fonts/` 에 아래 두 파일 복사:
- `NanumGothic.ttf`
- `NanumGothicBold.ttf`

> 나눔고딕 다운로드: https://hangeul.naver.com/font

### 3. 배경 이미지 배치 (1080×1920 JPG)
`assets/templates/` 에 직접 제작 후 저장:
- `intro_bg.jpg`   — 도입부
- `gainer_bg.jpg`  — 급등 세그먼트 공용
- `loser_bg.jpg`   — 급락 세그먼트 공용
- `outro_bg.jpg`   — 마무리

### 4. BGM 배치 (선택)
`assets/bgm/bgm.mp3` (없으면 BGM 없이 진행)

### 5. API 키 설정 (AI 모드 사용 시)
```bash
cp .env.example .env
# ANTHROPIC_API_KEY 입력
export $(cat .env | xargs)
```

---

## 단계별 실행 (수동 모드 — 권장)

```bash
# 1. 시장 데이터 수집 및 확인
python run.py --stage market

# 2. 스크립트 템플릿 생성
#    → output/YYYYMMDD/script.json 생성
#    → 터미널에 Claude/ChatGPT 웹용 프롬프트 출력
python run.py --stage script-init

# 3. script.json 직접 편집
#    (터미널에 출력된 프롬프트를 웹 AI에 붙여넣고 결과를 script.json에 저장)

# 4. TTS 생성
python run.py --stage tts

# 5. 이미지 생성
python run.py --stage image

# 6. 최종 영상 합성
python run.py --stage video
```

### 특정 세그먼트만 재작업 (수정 후 재실행)
```bash
# script.json에서 gainer_a reason 수정 후
python run.py --stage tts   --segment gainer_a
python run.py --stage image --segment gainer_a
python run.py --stage video   # 영상 재합성
```

### 날짜 수동 지정
```bash
python run.py --stage market --date 20250610
```

---

## 전체 자동 실행 (Claude API 모드)
```bash
python main.py
```

---

## 영상 구성 (1.5배속 기준 약 33초)

| 세그먼트 | 시간 | 내용 |
|----------|------|------|
| intro | 0~1s | 도입부 + 날짜 |
| gainer_list | 1~4s | 급등 TOP3 (종목명·섹터·등락률) |
| gainer_a/b/c | 4~16s | 급등 종목별 차트 + 이유 |
| loser_list | 16~19s | 급락 TOP3 (종목명·섹터·등락률) |
| loser_a/b/c | 19~31s | 급락 종목별 차트 + 이유 |
| outro | 31~33s | 마무리 + 날짜 |

---

## 자동 실행 cron 설정
```bash
# 평일 오전 6시 자동 실행 → 7AM 업로드 타이밍
0 6 * * 1-5 cd /path/to/shorts-bot && export $(cat .env | xargs) && python main.py
```

---

## 프로젝트 구조
```
shorts-bot/
├── run.py                   ← 단계별 실행 CLI (핵심)
├── main.py                  ← 전체 자동 실행 (AI 모드)
├── config.py
├── stages/
│   ├── market_data.py       # pykrx 급등/급락 + 섹터
│   ├── sector.py            # 섹터 분류 (WICS + 정적 사전)
│   ├── script_gen.py        # 스크립트 템플릿 / Claude API
│   ├── image_gen.py         # Pillow + matplotlib
│   ├── tts_gen.py           # edge-tts
│   └── video_build.py       # FFmpeg
├── assets/
│   ├── fonts/
│   ├── bgm/
│   └── templates/
└── output/
    └── YYYYMMDD/
        ├── market.json      ← 시장 데이터 캐시
        ├── script.json      ← 스크립트 (직접 편집 대상)
        ├── images/
        ├── audio/
        ├── clips/
        └── shorts_YYYYMMDD.mp4
```
