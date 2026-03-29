# shorts-bot

주식 시장 급등/급락 종목을 자동으로 분석해 유튜브 쇼츠 영상을 생성하는 봇.

---

## 사전 준비

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

FFmpeg가 없으면 별도 설치 필요:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### 2. 한국어 폰트 배치
`assets/fonts/` 에 아래 두 파일 복사:
- `NanumGothic.ttf`
- `NanumGothicBold.ttf`

> 나눔고딕: https://hangeul.naver.com/font

### 3. 배경 이미지 배치
`assets/templates/` 에 아래 4개 파일 직접 제작 후 저장 (1080×1920 JPG):
- `intro_bg.jpg`   — 도입부 배경
- `gainer_bg.jpg`  — 급등 세그먼트 공용 배경
- `loser_bg.jpg`   — 급락 세그먼트 공용 배경
- `outro_bg.jpg`   — 마무리 배경

### 4. BGM 배치 (선택)
`assets/bgm/bgm.mp3` 에 배경음악 파일 배치.
없으면 BGM 없이 영상 생성.

### 5. API 키 설정
`.env.example` 을 `.env` 로 복사 후 키 입력:
```bash
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력
```

실행 전 환경변수 로드:
```bash
export $(cat .env | xargs)
```

---

## 실행

```bash
python main.py
```

결과물: `output/YYYYMMDD/shorts_YYYYMMDD.mp4`

---

## 자동 실행 (cron 예시)

매일 오전 6시에 실행 (장 마감 다음 날 새벽 생성 → 7AM 업로드):
```
0 6 * * 1-5 cd /path/to/shorts-bot && export $(cat .env | xargs) && python main.py
```

---

## 프로젝트 구조

```
shorts-bot/
├── main.py                  # 진입점
├── config.py                # 설정값
├── stages/
│   ├── market_data.py       # pykrx 급등/급락 수집
│   ├── script_gen.py        # Claude API 스크립트 생성
│   ├── image_gen.py         # Pillow + matplotlib 이미지
│   ├── tts_gen.py           # edge-tts 음성
│   └── video_build.py       # FFmpeg 영상 합성
├── assets/
│   ├── fonts/               # NanumGothic (직접 추가)
│   ├── bgm/                 # 배경음악 (직접 추가)
│   └── templates/           # 배경 이미지 (직접 추가)
└── output/                  # 생성 결과물 (날짜별)
```

---

## 영상 구성 (1.5배속 기준 약 33초)

| 구간 | 시간 | 내용 |
|------|------|------|
| 도입부 | 0~1s | 브랜딩 + 날짜 |
| 급등 리스트 | 1~4s | 급등 TOP3 종목명 + 등락률 |
| 급등 A | 4~8s | A종목 차트 + 이유 |
| 급등 B | 8~12s | B종목 차트 + 이유 |
| 급등 C | 12~16s | C종목 차트 + 이유 |
| 급락 리스트 | 16~19s | 급락 TOP3 종목명 + 등락률 |
| 급락 A | 19~23s | A종목 차트 + 이유 |
| 급락 B | 23~27s | B종목 차트 + 이유 |
| 급락 C | 27~31s | C종목 차트 + 이유 |
| 마무리 | 31~33s | 아웃트로 + 날짜 |
