"""
스크립트 JSON 생성

Playwright 웹 자동화는 playwright_worker.py를 subprocess로 실행해
메인 프로세스의 asyncio 이벤트 루프와 완전히 분리함.
(Microsoft Store Python의 socketpair 버그 우회)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import config

# ── 고정 멘트 ────────────────────────────────────────
FIXED_INTRO = {
    "KOSPI":  "긴 말 안 한다! 어제 코스피 급등급락, 딱 30초 컷으로 보고 가!",
    "KOSDAQ": "긴 말 안 한다! 어제 코스닥 급등급락, 딱 30초 컷으로 보고 가!",
    "NASDAQ": "긴 말 안 한다! 어제 나스닥 급등급락, 딱 30초 컷으로 보고 가!",
}
FIXED_OUTRO = "내일 아침 7시, 다음 급등주 놓치기 싫으면 구독!"

STOCK_SUBKEYS = ["name", "sector", "change", "reason"]
SECTION_REQUIRED: dict[str, type] = {
    "gainer_list_caption": str,
    "gainer_a": dict, "gainer_b": dict, "gainer_c": dict,
    "loser_list_caption":  str,
    "loser_a":  dict, "loser_b":  dict, "loser_c":  dict,
}

WORKER = Path(__file__).parent / "playwright_worker.py"


# ── 검증 ────────────────────────────────────────────
def validate_section(data: dict, label: str = "") -> tuple[bool, list[str]]:
    errors, pre = [], f"[{label}] " if label else ""
    for key, typ in SECTION_REQUIRED.items():
        if key not in data:
            errors.append(f"{pre}누락: '{key}'"); continue
        val = data[key]
        if not isinstance(val, typ):
            errors.append(f"{pre}'{key}' 타입 오류"); continue
        if typ is dict:
            for sub in STOCK_SUBKEYS:
                if sub not in val:
                    errors.append(f"{pre}'{key}.{sub}' 누락")
        if typ is str and not val.strip():
            errors.append(f"{pre}'{key}' 비어 있음")
    return len(errors) == 0, errors


def validate_script(data: dict, markets: list[str]) -> tuple[bool, list[str]]:
    errors = []
    clean  = {k: v for k, v in data.items() if not k.startswith("_")}
    for mkt in markets:
        if mkt.lower() not in clean:
            errors.append(f"최상위 키 '{mkt.lower()}' 누락"); continue
        ok, errs = validate_section(clean[mkt.lower()], mkt.upper())
        errors.extend(errs)
    return len(errors) == 0, errors


# ── 프롬프트 빌드 ────────────────────────────────────
_SYSTEM_PROMPT = """당신은 주식 시황 유튜브 쇼츠 스크립트 작가입니다.

[말투 규칙]
- 경어체 유지, 문장 짧고 리듬감 있게
- "살펴보겠습니다" 대신 "알아볼게요"
- reason은 반드시 25자 이내 명사형으로 끝낼 것
  예시(좋음): "신약 허가 기대감으로 투자심리 급등", "실적 부진 우려 및 차익실현"
  예시(나쁨): "~로 보여요", "~했어요", "~입니다", "~됩니다" — 이런 동사형 어미 사용 금지
- gainer_list_caption / loser_list_caption: 해당 세션의 공통 테마·섹터를 "A·B·C 강세" 또는 "A·B·C 약세" 형태로 15자 이내 작성
  예시: "풍력·조선·반도체 약세", "바이오·방산·전자 강세"
- 섹터: 종목명 보고 직접 판단 (삼성전자→반도체, 현대차→자동차, Apple→IT, Tesla→전기차)
- 나스닥 종목은 영어 이름 그대로 사용

[출력 규칙 — 반드시 준수]
- 입력으로 받은 JSON을 그대로 반환하되, 빈 문자열("")만 채워서 출력
- _로 시작하는 키(참고용)도 원본 그대로 유지해서 출력
- 키 이름/구조/순서 절대 변경 금지
- 마크다운 코드블록(```json```) 사용 금지
- JSON 외 텍스트 일절 출력 금지"""


def _section_fmt() -> str:
    return (
        '{\n'
        '    "gainer_list_caption": "...",\n'
        '    "gainer_a": {"name":"종목명","sector":"섹터","change":"+X.X%","reason":"..."},\n'
        '    "gainer_b": {"name":"종목명","sector":"섹터","change":"+X.X%","reason":"..."},\n'
        '    "gainer_c": {"name":"종목명","sector":"섹터","change":"+X.X%","reason":"..."},\n'
        '    "loser_list_caption": "...",\n'
        '    "loser_a": {"name":"종목명","sector":"섹터","change":"-X.X%","reason":"..."},\n'
        '    "loser_b": {"name":"종목명","sector":"섹터","change":"-X.X%","reason":"..."},\n'
        '    "loser_c": {"name":"종목명","sector":"섹터","change":"-X.X%","reason":"..."}\n'
        '  }'
    )


def _movers_text(movers: dict) -> str:
    def sign(v): return f"+{v}" if v >= 0 else str(v)
    def fmt_c(s):
        return f"{s['close']:,}원" if isinstance(s['close'], int) else f"${s['close']:.2f}"
    g = "\n".join(
        f"  - {s['name']} ({s['ticker']}): {sign(s['change'])}%, {fmt_c(s)}"
        for s in movers.get("gainers", [])
    )
    l = "\n".join(
        f"  - {s['name']} ({s['ticker']}): {s['change']}%, {fmt_c(s)}"
        for s in movers.get("losers", [])
    )
    return f"급등:\n{g}\n급락:\n{l}"


def _build_prompt(date: str, market_summary: dict,
                  movers_map: dict[str, dict]) -> str:
    date_fmt  = datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일")
    sections  = "".join(
        f"\n[{mkt.upper()}]\n{_movers_text(mv)}\n"
        for mkt, mv in movers_map.items()
    )
    mkt_keys  = list(movers_map.keys())
    fmt_lines = "\n".join(f'  "{k}": {_section_fmt()},' for k in mkt_keys)
    output_fmt = "{\n" + fmt_lines.rstrip(",") + "\n}"

    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"날짜: {date_fmt}\n"
        f"시장: {market_summary.get('summary', '')}\n"
        f"{sections}\n"
        f"위 데이터로 JSON 스크립트를 작성하세요.\n"
        f"섹터는 종목명 보고 직접 판단해 채워주세요.\n\n"
        f"출력 형식:\n{output_fmt}"
    )


# ── JSON 추출 ────────────────────────────────────────
def _extract_json(text: str) -> dict:
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*",     "", text)
    text = text.strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSON 블록 없음. 응답:\n{text[:300]}")
    return json.loads(text[start:end])


# ── subprocess로 워커 실행 ────────────────────────────
def _run_worker(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    """
    playwright_worker.py를 독립 프로세스로 실행.
    메인 프로세스의 asyncio와 완전히 분리됨.
    """
    cmd = [sys.executable, str(WORKER)] + args
    return subprocess.run(
        cmd,
        timeout=timeout,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ── 공개 인터페이스 ──────────────────────────────────
def login_browser():
    """최초 1회 로그인. 세션을 .browser_profile/에 저장."""
    result = _run_worker(["--mode", "login"], timeout=300)
    if result.returncode != 0:
        raise RuntimeError("로그인 실패")


def generate_script_ai(date: str, market_summary: dict,
                       movers_map: dict[str, dict],
                       max_retries: int = 10) -> dict:
    """
    Gemini 웹 자동화로 스크립트 생성.
    --stage script-init 과 동일한 프롬프트(JSON 템플릿 포함) 사용.
    playwright_worker.py를 subprocess로 실행해 asyncio 충돌 완전 회피.
    """
    import tempfile as _tempfile

    # script-init 과 동일한 방식으로 템플릿 JSON 생성 후 프롬프트 빌드
    with _tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        tmp_template = Path(tf.name)

    generate_script_template(date, market_summary, movers_map, tmp_template)
    prompt = _build_web_prompt(tmp_template)
    try:
        tmp_template.unlink(missing_ok=True)
    except Exception:
        pass

    last_err = None

    for attempt in range(1, max_retries + 1):
        # 임시 파일로 프롬프트 전달, 응답 수신
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as pf:
            pf.write(prompt)
            prompt_path = pf.name

        out_path = prompt_path.replace(".txt", "_result.txt")

        try:
            print(f"   Gemini 웹 자동화 실행 중... (시도 {attempt}/{max_retries})")
            result = _run_worker([
                "--mode",        "generate",
                "--prompt-file", prompt_path,
                "--out-file",    out_path,
            ], timeout=180)

            if result.returncode == 2:
                raise RuntimeError("로그인 필요 — python run.py --stage login 먼저 실행")

            if result.returncode != 0:
                raise RuntimeError(f"워커 종료 코드 {result.returncode}")

            response_text = Path(out_path).read_text(encoding="utf-8")
            data = _extract_json(response_text)

            ok, errors = validate_script(data, list(movers_map.keys()))
            if not ok:
                raise ValueError("구조 오류:\n" + "\n".join(errors))

            return data

        except Exception as e:
            last_err = e
            print(f"   ⚠️  Gemini 오류 (시도 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait = min(30 * attempt, 300)
                print(f"      {wait}초 후 재시도...")
                import time; time.sleep(wait)
        finally:
            for p in [prompt_path, out_path]:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass

    raise RuntimeError(f"Gemini 웹 자동화 최종 실패: {last_err}")


# ── 수동 템플릿 생성 ─────────────────────────────────
def generate_script_template(date: str, market_summary: dict,
                              movers_map: dict[str, dict],
                              out_path: Path) -> Path:
    def sign(v): return f"+{v}" if v >= 0 else str(v)

    def stock_entry(s: dict) -> dict:
        return {"name": s["name"], "sector": "", "change": f"{sign(s['change'])}%", "reason": ""}

    def section(movers: dict) -> dict:
        return {
            "gainer_list_caption": "",
            "gainer_a": stock_entry(movers["gainers"][0]),
            "gainer_b": stock_entry(movers["gainers"][1]),
            "gainer_c": stock_entry(movers["gainers"][2]),
            "loser_list_caption": "",
            "loser_a": stock_entry(movers["losers"][0]),
            "loser_b": stock_entry(movers["losers"][1]),
            "loser_c": stock_entry(movers["losers"][2]),
        }

    def ref_lines(movers: dict) -> list[str]:
        lines = []
        for s in movers.get("gainers", []):
            c = f"{s['close']:,}원" if isinstance(s['close'], int) else f"${s['close']:.2f}"
            lines.append(f"  급등 {s['name']} ({s['ticker']}) {sign(s['change'])}% {c}")
        for s in movers.get("losers", []):
            c = f"{s['close']:,}원" if isinstance(s['close'], int) else f"${s['close']:.2f}"
            lines.append(f"  급락 {s['name']} ({s['ticker']}) {s['change']}% {c}")
        return lines

    template: dict = {
        "_날짜": datetime.strptime(date, "%Y%m%d").strftime("%Y년 %m월 %d일"),
        "_시장": market_summary.get("summary", ""),
    }
    for mkt, movers in movers_map.items():
        template[f"_{mkt.upper()}_참고"] = ref_lines(movers)
        template[mkt.lower()] = section(movers)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    return out_path


def _build_web_prompt(out_path: Path) -> str:
    with open(out_path, encoding="utf-8") as f:
        content = f.read()
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"아래 JSON에서 빈 문자열(\"\")만 채워주세요.\n"
        f"_로 시작하는 키(참고용)도 그대로 유지해서 출력하세요.\n\n"
        f"{content}"
    )


def load_script(path: Path, markets: list[str]) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    clean = {k: v for k, v in data.items() if not k.startswith("_")}
    ok, errors = validate_script(clean, markets)
    if not ok:
        print("\n  ⚠️  script.json 구조 오류:")
        for e in errors: print(f"     - {e}")
        raise ValueError("script.json 구조 오류")
    return clean


def get_market_script(script: dict, market: str) -> dict:
    sec = script[market.lower()]
    return {
        "intro":               FIXED_INTRO[market.upper()],
        "gainer_list_caption": sec["gainer_list_caption"],
        "gainer_a": sec["gainer_a"], "gainer_b": sec["gainer_b"],
        "gainer_c": sec["gainer_c"],
        "loser_list_caption":  sec["loser_list_caption"],
        "loser_a":  sec["loser_a"],  "loser_b":  sec["loser_b"],
        "loser_c":  sec["loser_c"],
        "outro":               FIXED_OUTRO,
    }
