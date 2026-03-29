"""
스크립트 JSON 생성
- Claude API 사용 시: generate_script_ai()
- 수동 작성용 템플릿 생성 시: generate_script_template()
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import config


# ── Claude API (선택적) ──────────────────────────────
def generate_script_ai(date: str, market_summary: dict,
                        movers: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    system = """당신은 주식 시황을 소개하는 유튜브 쇼츠 스크립트 작가입니다.

[말투 규칙]
- 경어체 유지 (합니다/습니다 기반)
- 문장은 짧고 리듬감 있게 끊기
- "살펴보겠습니다" 대신 "알아볼게요", "확인해볼게요" 사용
- 수치는 문장 앞에 배치해서 강조
- 도입부·마무리에만 시청자를 살짝 의식하는 표현 허용

[추론 규칙]
- 급등/급락 이유는 섹터 동향, 최근 이슈, 시장 분위기를 근거로 합리적 추론
- 불확실하면 "~로 보여요", "~영향을 받은 것으로 보여요" 사용
- 이유 파악 불가 시 "시장 전반 흐름에 따라 움직인 것으로 보여요"
- 단정적 표현 금지

[출력 규칙]
- JSON만 출력. 마크다운 코드블록 금지.
- reason은 한 문장 30자 이내

{
  "intro": "...",
  "gainer_list_caption": "...",
  "gainer_a": {"name":"종목명","change":"+X.X%","reason":"..."},
  "gainer_b": {"name":"종목명","change":"+X.X%","reason":"..."},
  "gainer_c": {"name":"종목명","change":"+X.X%","reason":"..."},
  "loser_list_caption": "...",
  "loser_a": {"name":"종목명","change":"-X.X%","reason":"..."},
  "loser_b": {"name":"종목명","change":"-X.X%","reason":"..."},
  "loser_c": {"name":"종목명","change":"-X.X%","reason":"..."},
  "outro": "..."
}"""

    prompt = _build_prompt(date, market_summary, movers)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def _build_prompt(date: str, market_summary: dict, movers: dict) -> str:
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일")

    def sign(v):
        return f"+{v}" if v >= 0 else str(v)

    g_lines = "\n".join(
        f"- {g['name']} ({g['sector']}): {sign(g['change'])}%, 종가 {g['close']:,}원"
        for g in movers["gainers"]
    )
    l_lines = "\n".join(
        f"- {l['name']} ({l['sector']}): {l['change']}%, 종가 {l['close']:,}원"
        for l in movers["losers"]
    )

    return f"""날짜: {date_fmt}
시장 분위기: {market_summary['summary']}

[급등주 TOP3]
{g_lines}

[급락주 TOP3]
{l_lines}

위 종목들의 급등·급락 이유를 추론해 JSON 스크립트를 작성해주세요.
마무리 멘트는 "어제 시황 여기까지고요, 오늘도 좋은 투자 되세요!" 느낌으로 작성해주세요."""


# ── 수동 작성용 템플릿 생성 ──────────────────────────
def generate_script_template(date: str, market_summary: dict,
                              movers: dict, out_path: Path) -> Path:
    """
    웹 AI(Claude/ChatGPT)에 붙여넣을 수 있도록
    시장 데이터가 채워진 템플릿 JSON 저장.
    빈 문자열 필드만 채워서 저장하면 됩니다.
    """
    def sign(v):
        return f"+{v}" if v >= 0 else str(v)

    def stock_entry(s: dict) -> dict:
        return {
            "name":   s["name"],
            "sector": s["sector"],
            "change": f"{sign(s['change'])}%",
            "close":  f"{s['close']:,}원",
            "reason": "",   # ← 채워야 할 필드
        }

    template = {
        "_안내": "아래 _로 시작하는 필드는 참고용 메모입니다. reason, intro, caption, outro의 빈 문자열만 채워주세요.",
        "_날짜": datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일"),
        "_시장": market_summary["summary"],
        "_급등": [stock_entry(g) for g in movers["gainers"]],
        "_급락": [stock_entry(l) for l in movers["losers"]],

        "intro": "",
        "gainer_list_caption": "",
        "gainer_a": stock_entry(movers["gainers"][0]),
        "gainer_b": stock_entry(movers["gainers"][1]),
        "gainer_c": stock_entry(movers["gainers"][2]),
        "loser_list_caption": "",
        "loser_a": stock_entry(movers["losers"][0]),
        "loser_b": stock_entry(movers["losers"][1]),
        "loser_c": stock_entry(movers["losers"][2]),
        "outro":   "",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return out_path


def load_script(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # _로 시작하는 메모 필드 제거
    return {k: v for k, v in data.items() if not k.startswith("_")}
