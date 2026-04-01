"""
스크립트 JSON 생성

구조 변경:
- 인트로/아웃트로 고정 (AI 생성 불필요)
- AI는 KOSPI/KOSDAQ 두 영상의 종목 캡션+이유만 한 번에 생성
- 출력: script.json 하나에 kospi/kosdaq 두 섹션 포함

고정 멘트:
  intro_kospi  : "긴 말 안 한다! 어제 코스피 급등급락, 딱 30초 컷으로 보고 가!"
  intro_kosdaq : "긴 말 안 한다! 어제 코스닥 급등급락, 딱 30초 컷으로 보고 가!"
  outro        : "내일 아침 7시, 다음 급등주 놓치기 싫으면 구독!"
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import config

# ── 고정 멘트 ────────────────────────────────────────
FIXED_INTRO = {
    "KOSPI":  "긴 말 안 한다! 어제 코스피 급등급락, 딱 30초 컷으로 보고 가!",
    "KOSDAQ": "긴 말 안 한다! 어제 코스닥 급등급락, 딱 30초 컷으로 보고 가!",
}
FIXED_OUTRO = "내일 아침 7시, 다음 급등주 놓치기 싫으면 구독!"

# ── 필수 키 (시장별 섹션 내부) ───────────────────────
STOCK_SUBKEYS = ["name", "sector", "change", "reason"]

SECTION_REQUIRED: dict[str, type] = {
    "gainer_list_caption": str,
    "gainer_a": dict,
    "gainer_b": dict,
    "gainer_c": dict,
    "loser_list_caption": str,
    "loser_a": dict,
    "loser_b": dict,
    "loser_c": dict,
}


def validate_section(data: dict, label: str = "") -> tuple[bool, list[str]]:
    errors = []
    prefix = f"[{label}] " if label else ""

    for key, expected_type in SECTION_REQUIRED.items():
        if key not in data:
            errors.append(f"{prefix}누락된 키: '{key}'")
            continue
        val = data[key]
        if not isinstance(val, expected_type):
            errors.append(f"{prefix}'{key}' 타입 오류")
            continue
        if expected_type is dict:
            for sub in STOCK_SUBKEYS:
                if sub not in val:
                    errors.append(f"{prefix}'{key}.{sub}' 누락")
        if expected_type is str and not val.strip():
            errors.append(f"{prefix}'{key}' 값이 비어 있음")

    return len(errors) == 0, errors


def validate_script(data: dict) -> tuple[bool, list[str]]:
    """전체 script.json 검증 (kospi + kosdaq 두 섹션)"""
    errors = []
    clean  = {k: v for k, v in data.items() if not k.startswith("_")}

    for market in ("kospi", "kosdaq"):
        if market not in clean:
            errors.append(f"최상위 키 '{market}' 누락")
            continue
        ok, errs = validate_section(clean[market], market.upper())
        errors.extend(errs)

    return len(errors) == 0, errors


# ── 시스템 프롬프트 ──────────────────────────────────
_SYSTEM_PROMPT = """당신은 주식 시황 유튜브 쇼츠 스크립트 작가입니다.

[말투 규칙]
- 경어체 유지, 문장 짧고 리듬감 있게
- "살펴보겠습니다" 대신 "알아볼게요"
- reason은 반드시 30자 이내 한 문장
- 섹터: 종목명 보고 직접 판단 (삼성전자→반도체, 현대차→자동차 등)
- 불확실하면 "~로 보여요" 사용

[출력 규칙]
- 반드시 아래 JSON 구조 그대로 출력
- 키 이름/구조/순서 변경 금지, 추가/삭제 금지
- 마크다운 코드블록 사용 금지
- JSON 객체만 출력 (설명 텍스트 금지)

출력 형식:
{
  "kospi": {
    "gainer_list_caption": "...",
    "gainer_a": {"name": "종목명", "sector": "섹터", "change": "+X.X%", "reason": "..."},
    "gainer_b": {"name": "종목명", "sector": "섹터", "change": "+X.X%", "reason": "..."},
    "gainer_c": {"name": "종목명", "sector": "섹터", "change": "+X.X%", "reason": "..."},
    "loser_list_caption": "...",
    "loser_a": {"name": "종목명", "sector": "섹터", "change": "-X.X%", "reason": "..."},
    "loser_b": {"name": "종목명", "sector": "섹터", "change": "-X.X%", "reason": "..."},
    "loser_c": {"name": "종목명", "sector": "섹터", "change": "-X.X%", "reason": "..."}
  },
  "kosdaq": {
    "gainer_list_caption": "...",
    "gainer_a": {"name": "종목명", "sector": "섹터", "change": "+X.X%", "reason": "..."},
    "gainer_b": {"name": "종목명", "sector": "섹터", "change": "+X.X%", "reason": "..."},
    "gainer_c": {"name": "종목명", "sector": "섹터", "change": "+X.X%", "reason": "..."},
    "loser_list_caption": "...",
    "loser_a": {"name": "종목명", "sector": "섹터", "change": "-X.X%", "reason": "..."},
    "loser_b": {"name": "종목명", "sector": "섹터", "change": "-X.X%", "reason": "..."},
    "loser_c": {"name": "종목명", "sector": "섹터", "change": "-X.X%", "reason": "..."}
  }
}"""


def _build_user_prompt(date: str, market_summary: dict,
                       kospi_movers: dict, kosdaq_movers: dict) -> str:
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일")

    def sign(v):
        return f"+{v}" if v >= 0 else str(v)

    def fmt_movers(movers: dict) -> str:
        g = "\n".join(
            f"  - {s['name']} (티커:{s['ticker']}): {sign(s['change'])}%, 종가 {s['close']:,}원"
            for s in movers["gainers"]
        )
        l = "\n".join(
            f"  - {s['name']} (티커:{s['ticker']}): {s['change']}%, 종가 {s['close']:,}원"
            for s in movers["losers"]
        )
        return f"급등:\n{g}\n급락:\n{l}"

    return f"""날짜: {date_fmt}
시장: {market_summary['summary']}

[KOSPI]
{fmt_movers(kospi_movers)}

[KOSDAQ]
{fmt_movers(kosdaq_movers)}

위 데이터를 바탕으로 JSON 형식의 스크립트를 작성해주세요.
각 종목의 sector는 종목명 보고 직접 판단해 채워주세요."""


# ── AI 자동 생성 ─────────────────────────────────────
def generate_script_ai(date: str, market_summary: dict,
                       kospi_movers: dict, kosdaq_movers: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    prompt = _build_user_prompt(date, market_summary, kospi_movers, kosdaq_movers)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw  = response.content[0].text.strip()
    raw  = raw.replace("```json", "").replace("```", "").strip()
    data = json.loads(raw)

    ok, errors = validate_script(data)
    if not ok:
        raise ValueError("AI 응답 구조 오류:\n" + "\n".join(errors))

    return data


# ── 수동 템플릿 생성 ─────────────────────────────────
def generate_script_template(date: str, market_summary: dict,
                              kospi_movers: dict, kosdaq_movers: dict,
                              out_path: Path) -> Path:
    def sign(v):
        return f"+{v}" if v >= 0 else str(v)

    def stock_entry(s: dict) -> dict:
        return {
            "name":   s["name"],
            "sector": "",
            "change": f"{sign(s['change'])}%",
            "reason": "",
        }

    def section(movers: dict) -> dict:
        return {
            "gainer_list_caption": "",
            "gainer_a": stock_entry(movers["gainers"][0]),
            "gainer_b": stock_entry(movers["gainers"][1]),
            "gainer_c": stock_entry(movers["gainers"][2]),
            "loser_list_caption":  "",
            "loser_a": stock_entry(movers["losers"][0]),
            "loser_b": stock_entry(movers["losers"][1]),
            "loser_c": stock_entry(movers["losers"][2]),
        }

    def ref_lines(movers: dict, label: str) -> list[str]:
        lines = []
        for s in movers["gainers"]:
            lines.append(f"  급등 {s['name']} ({s['ticker']}) {sign(s['change'])}% {s['close']:,}원")
        for s in movers["losers"]:
            lines.append(f"  급락 {s['name']} ({s['ticker']}) {s['change']}% {s['close']:,}원")
        return lines

    template = {
        "_안내": [
            "빈 문자열(\"\")만 채워주세요.",
            "키 이름/구조/순서 변경 금지.",
            "JSON만 출력 (마크다운/설명 금지).",
        ],
        "_날짜":          datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일"),
        "_시장":          market_summary["summary"],
        "_KOSPI_참고":    ref_lines(kospi_movers,  "KOSPI"),
        "_KOSDAQ_참고":   ref_lines(kosdaq_movers, "KOSDAQ"),
        "kospi":          section(kospi_movers),
        "kosdaq":         section(kosdaq_movers),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return out_path


def _build_web_prompt(out_path: Path) -> str:
    with open(out_path, encoding="utf-8") as f:
        content = f.read()
    return f"""{_SYSTEM_PROMPT}

아래 JSON에서 빈 문자열("")만 채워주세요.
_로 시작하는 키는 참고용 — 출력에 포함하지 마세요.

{content}"""


# ── 로드 + 검증 ──────────────────────────────────────
def load_script(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    clean = {k: v for k, v in data.items() if not k.startswith("_")}

    ok, errors = validate_script(clean)
    if not ok:
        print("\n  ⚠️  script.json 구조 오류:")
        for e in errors:
            print(f"     - {e}")
        raise ValueError("script.json 구조 오류")

    return clean


def get_market_script(script: dict, market: str) -> dict:
    """
    전체 script에서 특정 시장 섹션 추출.
    인트로/아웃트로는 고정 멘트로 주입.
    """
    section = script[market.lower()]
    return {
        "intro":               FIXED_INTRO[market.upper()],
        "gainer_list_caption": section["gainer_list_caption"],
        "gainer_a":            section["gainer_a"],
        "gainer_b":            section["gainer_b"],
        "gainer_c":            section["gainer_c"],
        "loser_list_caption":  section["loser_list_caption"],
        "loser_a":             section["loser_a"],
        "loser_b":             section["loser_b"],
        "loser_c":             section["loser_c"],
        "outro":               FIXED_OUTRO,
    }
