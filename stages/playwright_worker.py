"""
Playwright 워커 — 독립 프로세스로 실행됨

프롬프트 입력 방식:
  clipboard API 대신 Gemini 입력창에 직접 DOM 이벤트로 텍스트 주입.
  clipboard는 Playwright에서 권한 문제로 실패하는 경우가 있음.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.sync_api import sync_playwright

BASE_DIR        = Path(__file__).parent.parent
BROWSER_PROFILE = BASE_DIR / ".browser_profile"


def _get_context(playwright):
    BROWSER_PROFILE.mkdir(exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(BROWSER_PROFILE),
        headless=False,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_https_errors=True,
    )


def _type_prompt(page, prompt: str) -> bool:
    """
    Gemini 입력창에 프롬프트를 입력하는 방법을 순서대로 시도.
    성공하면 True, 실패하면 False 반환.
    """
    # 입력창 선택자 후보
    textarea_selectors = [
        "rich-textarea div[contenteditable='true']",
        "div[role='textbox'][contenteditable='true']",
        "div.ql-editor[contenteditable='true']",
        "div[contenteditable='true']",
    ]

    textarea = None
    for sel in textarea_selectors:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=5000)
            textarea = loc
            print(f"  입력창 찾음: {sel}", flush=True)
            break
        except Exception:
            continue

    if textarea is None:
        print("  ❌ 입력창을 찾을 수 없음", flush=True)
        return False

    textarea.click()
    page.wait_for_timeout(400)

    # ── 방법 1: clipboard grant + paste ──────────────
    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        page.evaluate("(text) => navigator.clipboard.writeText(text)", prompt)
        page.keyboard.press("Control+v")
        page.wait_for_timeout(600)

        # 텍스트가 실제로 들어갔는지 확인
        val = textarea.inner_text()
        if len(val.strip()) > 10:
            print(f"  방법1(clipboard) 성공: {len(val)}자 입력", flush=True)
            return True
        print("  방법1(clipboard) 실패 — 방법2 시도", flush=True)
    except Exception as e:
        print(f"  방법1 오류: {e}", flush=True)

    # ── 방법 2: execCommand('insertText') ────────────
    try:
        textarea.click()
        page.wait_for_timeout(300)
        # 기존 내용 지우기
        page.keyboard.press("Control+a")
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)

        page.evaluate(
            """(text) => {
                const el = document.activeElement;
                el.focus();
                document.execCommand('insertText', false, text);
            }""",
            prompt,
        )
        page.wait_for_timeout(600)
        val = textarea.inner_text()
        if len(val.strip()) > 10:
            print(f"  방법2(execCommand) 성공: {len(val)}자 입력", flush=True)
            return True
        print("  방법2(execCommand) 실패 — 방법3 시도", flush=True)
    except Exception as e:
        print(f"  방법2 오류: {e}", flush=True)

    # ── 방법 3: keyboard.type() (느리지만 확실) ───────
    try:
        textarea.click()
        page.wait_for_timeout(300)
        page.keyboard.press("Control+a")
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)

        # 긴 텍스트는 청크로 나눠서 입력
        CHUNK = 500
        for i in range(0, len(prompt), CHUNK):
            page.keyboard.type(prompt[i:i+CHUNK], delay=0)
            page.wait_for_timeout(100)

        val = textarea.inner_text()
        if len(val.strip()) > 10:
            print(f"  방법3(keyboard.type) 성공: {len(val)}자 입력", flush=True)
            return True
        print("  방법3(keyboard.type) 실패", flush=True)
    except Exception as e:
        print(f"  방법3 오류: {e}", flush=True)

    return False


def _send_message(page) -> None:
    """전송 버튼 클릭 또는 Enter"""
    send_selectors = [
        'button[aria-label*="Send message"]',
        'button[aria-label*="전송"]',
        'button[aria-label*="Send"]',
        'button.send-button',
        'button[jsname="Qx7uuf"]',
        'button[data-mat-icon-name="send"]',
    ]
    for sel in send_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible():
                btn.click()
                print(f"  전송 버튼 클릭: {sel}", flush=True)
                return
        except Exception:
            continue
    # fallback
    page.keyboard.press("Enter")
    print("  Enter로 전송", flush=True)


def _wait_response_done(page, timeout_s: int = 120) -> None:
    deadline = time.time() + timeout_s
    stop_selectors = (
        'button[aria-label*="Stop"], '
        'button[jsname="M9rSje"], '
        'button.stop-button'
    )

    # 응답 시작 대기
    for _ in range(20):
        if time.time() > deadline:
            break
        try:
            if page.locator(stop_selectors).count() > 0:
                break
        except Exception:
            pass
        page.wait_for_timeout(500)

    # 응답 완료 대기
    while time.time() < deadline:
        try:
            if page.locator(stop_selectors).count() == 0:
                break
        except Exception:
            break
        page.wait_for_timeout(800)

    page.wait_for_timeout(1500)


def _get_last_response(page) -> str:
    selectors = [
        "model-response .markdown.markdown-main-panel",
        "model-response .response-content",
        ".response-container-content .markdown",
        "message-content .markdown",
        "model-response",
    ]
    for sel in selectors:
        els = page.locator(sel)
        if els.count() > 0:
            text = els.last.inner_text()
            print(f"  응답 추출 ({sel}): {len(text)}자", flush=True)
            return text
    raise RuntimeError("Gemini 응답 텍스트를 찾을 수 없음")


def do_login():
    print("  브라우저를 열어 Gemini에 로그인하세요.")
    print("  로그인 완료 후 이 창에서 Enter를 누르세요.")
    with sync_playwright() as p:
        ctx  = _get_context(p)
        page = ctx.new_page()
        page.goto("https://gemini.google.com/app", timeout=30000)
        input("  로그인 완료 후 Enter: ")
        ctx.close()
    print("  ✅ 로그인 세션 저장 완료")


def do_generate(prompt_file: str, out_file: str):
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    print(f"  프롬프트 로드: {len(prompt)}자", flush=True)

    with sync_playwright() as p:
        ctx  = _get_context(p)
        page = ctx.new_page()

        page.goto("https://gemini.google.com/app", timeout=30000)
        page.wait_for_timeout(2000)

        if "accounts.google.com" in page.url:
            print("  ⚠️  로그인 필요 — python run.py --stage login 먼저 실행", file=sys.stderr)
            ctx.close()
            sys.exit(2)

        print(f"  페이지 로드 완료: {page.url}", flush=True)

        # 프롬프트 입력
        ok = _type_prompt(page, prompt)
        if not ok:
            ctx.close()
            sys.exit(1)

        # 전송
        _send_message(page)

        # 응답 대기
        print("  Gemini 응답 대기 중...", flush=True)
        _wait_response_done(page, timeout_s=120)

        # 응답 추출
        response_text = _get_last_response(page)
        ctx.close()

    Path(out_file).write_text(response_text, encoding="utf-8")
    print(f"  결과 저장: {out_file}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",        required=True, choices=["login", "generate"])
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--out-file",    default="")
    args = parser.parse_args()

    if args.mode == "login":
        do_login()
    elif args.mode == "generate":
        if not args.prompt_file or not args.out_file:
            print("--prompt-file 과 --out-file 필요", file=sys.stderr)
            sys.exit(1)
        do_generate(args.prompt_file, args.out_file)
