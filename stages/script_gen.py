"""
스크립트 JSON 생성
- 수동 모드: generate_script_template() → JSON 템플릿 파일 생성
- AI 자동 모드: generate_script_ai()
- 공통: load_script(), validate_script()
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import config

# ── 필수 키 정의 ─────────────────────────────────────
# 각 항목 키: (타입, 필수 서브키 목록)
REQUIRED_KEYS: dict[str, type] = {
    "intro":               str,
    "gainer_list_caption": str,
    "gainer_a":            dict,
    "gainer_b":            dict,
    "gainer_c":            dict,
    "loser_list_caption":  str,
    "loser_a":             dict,
    "loser_b":             dict,
    "loser_c":             dict,
    "outro":               str,
}
STOCK_SUBKEYS = ["name", "sector", "change", "reason"]


# ── 구조 검증 ────────────────────────────────────────
def validate_script(data: dict) -> tuple[bool, list[str]]:
    """
    필수 키와 타입을 검사.
    반환: (통과 여부, 오류 메시지 목록)
    """
    errors = []

    # _로 시작하는 메모 키 제거 후 검사
    clean = {k: v for k, v in data.items() if not k.startswith("_")}

    for key, expected_type in REQUIRED_KEYS.items():
        if key not in clean:
            errors.append(f"누락된 키: '{key}'")
            continue

        val = clean[key]

        if not isinstance(val, expected_type):
            errors.append(
                f"'{key}' 타입 오류: {type(val).__name__} (기대: {expected_type.__name__})"
            )
            continue

        # 종목 dict 서브키 검사
        if expected_type is dict:
            for sub in STOCK_SUBKEYS:
                if sub not in val:
                    errors.append(f"'{key}.{sub}' 누락")
                elif not isinstance(val[sub], str):
                    errors.append(f"'{key}.{sub}' 타입 오류 (str이어야 함)")

        # 빈 문자열 경고
        if expected_type is str and val.strip() == "":
            errors.append(f"'{key}' 값이 비어 있음")

    return (len(errors) == 0), errors


# ── 공통 프롬프트 텍스트 ─────────────────────────────
_SYSTEM_PROMPT = """당신은 주식 시황을 소개하는 유튜브 쇼츠 스크립트 작가입니다.

[말투 규칙]
- 경어체 유지 (합니다/습니다 기반)
- 문장은 짧고 리듬감 있게 끊기
- "살펴보겠습니다" 대신 "알아볼게요", "확인해볼게요" 사용
- 수치는 문장 앞에 배치해서 강조
- 마무리는 반드시 "어제 시황 여기까지고요, 오늘도 좋은 투자 되세요!" 스타일로

[추론 규칙]
- 급등/급락 이유: 섹터 동향, 최근 이슈, 시장 분위기를 근거로 추론
- 섹터: 종목명을 보고 판단 (예: 삼성전자→반도체, 현대차→자동차)
- 불확실하면 "~로 보여요", "~영향을 받은 것으로 보여요" 사용
- reason은 반드시 30자 이내 한 문장

[출력 규칙 — 반드시 준수]
- 반드시 아래 JSON 형식 그대로 출력
- 키 이름 변경 금지, 키 추가/삭제 금지
- 마크다운 코드블록(```json ```) 사용 금지
- 설명 텍스트, 주석, 안내문 출력 금지
- 오직 JSON 객체만 출력

출력 형식:
{
  "intro": "...",
  "gainer_list_caption": "...",
  "gainer_a": {"name": "종목명", "sector": "섹터명", "change": "+X.X%", "reason": "..."},
  "gainer_b": {"name": "종목명", "sector": "섹터명", "change": "+X.X%", "reason": "..."},
  "gainer_c": {"name": "종목명", "sector": "섹터명", "change": "+X.X%", "reason": "..."},
  "loser_list_caption": "...",
  "loser_a": {"name": "종목명", "sector": "섹터명", "change": "-X.X%", "reason": "..."},
  "loser_b": {"name": "종목명", "sector": "섹터명", "change": "-X.X%", "reason": "..."},
  "loser_c": {"name": "종목명", "sector": "섹터명", "change": "-X.X%", "reason": "..."},
  "outro": "..."
}"""


def _build_user_prompt(date: str, market_summary: dict, movers: dict) -> str:
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일")

    def sign(v):
        return f"+{v}" if v >= 0 else str(v)

    g_lines = "\n".join(
        f"- {g['name']} (티커:{g['ticker']}): {sign(g['change'])}%, 종가 {g['close']:,}원"
        for g in movers["gainers"]
    )
    l_lines = "\n".join(
        f"- {l['name']} (티커:{l['ticker']}): {l['change']}%, 종가 {l['close']:,}원"
        for l in movers["losers"]
    )

    return f"""날짜: {date_fmt}
시장 분위기: {market_summary['summary']}

[급등주 TOP3]
{g_lines}

[급락주 TOP3]
{l_lines}

위 데이터를 바탕으로 지정된 JSON 형식에 맞게 스크립트를 작성해주세요.
각 종목의 sector는 종목명을 보고 직접 판단해 채워주세요."""


# ── AI 자동 모드 ─────────────────────────────────────
def generate_script_ai(date: str, market_summary: dict, movers: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    prompt = _build_user_prompt(date, market_summary, movers)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    data = json.loads(raw)

    ok, errors = validate_script(data)
    if not ok:
        raise ValueError(f"AI 응답 구조 오류:\n" + "\n".join(errors))

    return data


# ── 수동 템플릿 생성 ─────────────────────────────────
def generate_script_template(date: str, market_summary: dict,
                              movers: dict, out_path: Path) -> Path:
    def sign(v):
        return f"+{v}" if v >= 0 else str(v)

    def stock_entry(s: dict) -> dict:
        return {
            "name":   s["name"],
            "sector": "",       # AI가 채울 필드
            "change": f"{sign(s['change'])}%",
            "reason": "",       # AI가 채울 필드
        }

    template = {
        "_안내": [
            "아래 JSON에서 빈 문자열(\"\")만 채워주세요.",
            "키 이름, 구조, 순서를 절대 변경하지 마세요.",
            "마크다운이나 설명 없이 JSON만 출력해주세요.",
        ],
        "_날짜":   datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일"),
        "_시장":   market_summary["summary"],
        "_급등_참고": [
            f"{g['name']} (티커:{g['ticker']}) {sign(g['change'])}% 종가:{g['close']:,}원"
            for g in movers["gainers"]
        ],
        "_급락_참고": [
            f"{l['name']} (티커:{l['ticker']}) {l['change']}% 종가:{l['close']:,}원"
            for l in movers["losers"]
        ],

        "intro":               "",
        "gainer_list_caption": "",
        "gainer_a": stock_entry(movers["gainers"][0]),
        "gainer_b": stock_entry(movers["gainers"][1]),
        "gainer_c": stock_entry(movers["gainers"][2]),
        "loser_list_caption":  "",
        "loser_a": stock_entry(movers["losers"][0]),
        "loser_b": stock_entry(movers["losers"][1]),
        "loser_c": stock_entry(movers["losers"][2]),
        "outro":               "",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return out_path


def _build_web_prompt(out_path: Path) -> str:
    """웹 AI에 붙여넣을 프롬프트 생성"""
    with open(out_path, encoding="utf-8") as f:
        content = f.read()

    return f"""{_SYSTEM_PROMPT}

아래 JSON 파일에서 빈 문자열("")로 표시된 필드만 채워주세요.
_로 시작하는 키는 참고용이므로 출력에 포함하지 마세요.
반드시 빈 문자열이 있는 키만 채우고, 나머지 구조는 그대로 유지하세요.

{content}"""


# ── 스크립트 로드 + 검증 ─────────────────────────────
def load_script(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # _로 시작하는 메모 키 제거
    clean = {k: v for k, v in data.items() if not k.startswith("_")}

    ok, errors = validate_script(clean)
    if not ok:
        print("\n  ⚠️  script.json 구조 오류:")
        for e in errors:
            print(f"     - {e}")
        print("  스크립트를 수정한 뒤 다시 실행해주세요.\n")
        raise ValueError("script.json 구조 오류")

    return clean
