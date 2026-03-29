"""
2단계: Claude API로 전체 스크립트 JSON 1회 생성
"""
import json
from datetime import datetime
import anthropic
import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """당신은 주식 시황을 소개하는 유튜브 쇼츠 스크립트 작가입니다.

[말투 규칙]
- 경어체 유지 (합니다/습니다 기반)
- 문장은 짧고 리듬감 있게 끊기
- "살펴보겠습니다" 대신 "알아볼게요", "확인해볼게요" 사용
- 수치는 문장 앞에 배치해서 강조
- 도입부·마무리에만 시청자를 살짝 의식하는 표현 허용
  예) "오늘도 주목할 종목들 바로 가볼게요", "오늘도 좋은 투자 되세요"

[추론 규칙]
- 급등/급락 이유는 해당 종목의 섹터 동향, 최근 알려진 이슈, 당일 시장 분위기를 근거로 합리적으로 추론
- 확실하지 않으면 "~로 보여요", "~영향을 받은 것으로 보여요" 표현 사용
- 이유를 전혀 파악하기 어려우면 "시장 전반 흐름에 따라 움직인 것으로 보여요"로 처리
- 근거 없는 단정적 표현 절대 금지

[출력 규칙]
- 반드시 아래 JSON 형식만 출력. 설명·마크다운 코드블록 금지.
- reason은 한 문장, 30자 이내로 간결하게

{
  "intro": "도입부 나레이션 (1~2문장)",
  "gainer_list_caption": "급등 리스트 자막 — 수치 강조 1문장",
  "gainer_a": {"name": "종목명", "change": "+X.X%", "reason": "이유 1줄"},
  "gainer_b": {"name": "종목명", "change": "+X.X%", "reason": "이유 1줄"},
  "gainer_c": {"name": "종목명", "change": "+X.X%", "reason": "이유 1줄"},
  "loser_list_caption": "급락 리스트 자막 — 수치 강조 1문장",
  "loser_a": {"name": "종목명", "change": "-X.X%", "reason": "이유 1줄"},
  "loser_b": {"name": "종목명", "change": "-X.X%", "reason": "이유 1줄"},
  "loser_c": {"name": "종목명", "change": "-X.X%", "reason": "이유 1줄"},
  "outro": "마무리 나레이션 (1~2문장)"
}"""


def _build_prompt(date: str, market_summary: dict, movers: dict) -> str:
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일")

    def sign(v):
        return f"+{v}" if v >= 0 else str(v)

    gainer_lines = "\n".join(
        f"- {g['name']}: {sign(g['change'])}%, 종가 {g['close']:,}원"
        for g in movers["gainers"]
    )
    loser_lines = "\n".join(
        f"- {l['name']}: {l['change']}%, 종가 {l['close']:,}원"
        for l in movers["losers"]
    )

    return f"""날짜: {date_fmt}
시장 분위기: {market_summary['summary']}

[급등주 TOP3]
{gainer_lines}

[급락주 TOP3]
{loser_lines}

위 종목들의 급등·급락 이유를 추론해 JSON 스크립트를 작성해주세요.
마무리 멘트는 "어제 시황 여기까지고요, 오늘도 좋은 투자 되세요!" 느낌으로 작성해주세요."""


def generate_script(date: str, market_summary: dict, movers: dict) -> dict:
    prompt = _build_prompt(date, market_summary, movers)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # 혹시 코드블록이 붙어 나올 경우 제거
    raw = raw.replace("```json", "").replace("```", "").strip()

    return json.loads(raw)
