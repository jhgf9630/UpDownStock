"""
YouTube Shorts 자동 업로드
YouTube Data API v3 사용

사전 준비:
  1. Google Cloud Console → 프로젝트 생성
  2. YouTube Data API v3 활성화
  3. OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱)
  4. 클라이언트 시크릿 JSON 다운로드 → youtube_client_secret.json
  5. pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

최초 실행 시 브라우저 인증 → token.json 생성 → 이후 자동 인증
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from datetime import datetime

import config

# OAuth2 스코프
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = Path(config.BASE_DIR) / "youtube_token.json"


def _get_credentials():
    """OAuth2 인증. token.json 없으면 브라우저 열어 최초 인증."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.YOUTUBE_CLIENT_SECRET, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def _build_service():
    from googleapiclient.discovery import build
    creds = _get_credentials()
    return build("youtube", "v3", credentials=creds)


def _make_description(market: str, date: str) -> str:
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일")
    market_kr = {"kospi": "코스피", "kosdaq": "코스닥", "nasdaq": "나스닥"}.get(
        market.lower(), market.upper()
    )
    return (
        f"📈 {date_fmt} {market_kr} 급등급락 TOP3\n\n"
        f"매일 아침 7시, 어제 시장에서 주목받은 급등·급락 종목을 30초로 정리해드립니다.\n\n"
        f"⚠️ 본 영상은 투자 권유가 아닙니다. 투자의 책임은 본인에게 있습니다.\n\n"
        f"#주식 #{market_kr} #급등주 #급락주 #주식쇼츠 #UpDownStock"
    )


def _make_tags(market: str) -> list[str]:
    base = ["주식", "급등주", "급락주", "주식쇼츠", "UpDownStock", "주식투자"]
    market_tags = {
        "kospi":  ["코스피", "KOSPI", "국내주식"],
        "kosdaq": ["코스닥", "KOSDAQ", "코스닥주식"],
        "nasdaq": ["나스닥", "NASDAQ", "미국주식", "해외주식"],
    }
    return base + market_tags.get(market.lower(), [])


def upload_video(video_path: Path, market: str, date: str,
                 max_retries: int = 3) -> str | None:
    """
    영상 업로드.
    반환: 업로드된 YouTube 영상 ID (실패 시 None)
    """
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    if not video_path.exists():
        print(f"   [upload] ❌ 파일 없음: {video_path}")
        return None

    # 제목: "260401 코스피 급등급락" (파일명과 동일)
    title = video_path.stem  # 확장자 제거

    body = {
        "snippet": {
            "title":       title,
            "description": _make_description(market, date),
            "tags":        _make_tags(market),
            "categoryId":  config.YOUTUBE_CATEGORY_ID,
            "defaultLanguage": config.YOUTUBE_LANGUAGE,
        },
        "status": {
            "privacyStatus":           config.YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    for attempt in range(1, max_retries + 1):
        try:
            service = _build_service()
            media   = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=5 * 1024 * 1024,  # 5MB 청크
            )
            request  = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            print(f"   [upload] {title} 업로드 중...")
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    print(f"   [upload] {pct}% ...", end="\r")

            video_id = response.get("id", "")
            print(f"\n   [upload] ✅ 완료: https://youtu.be/{video_id}")
            return video_id

        except HttpError as e:
            print(f"   [upload] HTTP 오류 (시도 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(10 * attempt)
        except Exception as e:
            print(f"   [upload] 오류 (시도 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(10 * attempt)

    print(f"   [upload] ❌ 최종 실패: {title}")
    return None


def find_video(date: str, market: str) -> Path | None:
    """해당 날짜·시장의 최종 영상 파일 경로 반환"""
    mkt_dir = config.OUTPUT_DIR / date / market.lower()
    if not mkt_dir.exists():
        return None

    # "260401 코스피 급등급락.mp4" 형태 탐색
    candidates = list(mkt_dir.glob("*.mp4"))
    # 중간 파일(concat/sped) 제외
    finals = [p for p in candidates
              if not any(x in p.stem for x in ["concat", "sped", "bgm", "clip"])]

    return finals[0] if finals else None
