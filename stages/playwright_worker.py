"""
Playwright 워커 — 독립 프로세스로 실행됨

개선된 응답 완료 감지:
  1. 응답 텍스트 길이가 안정화되면 완료로 판단 (Stop 버튼 의존 제거)
  2. 페이지 crash / context close 예외 처리
  3. 타임아웃 시 현재까지 받은 텍스트 저장 후 정상 종료 (오류 대신 경고)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.sync_api import sync_playwright, Error as PWError

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


# ── 프롬프트 입력 ─────────────────────────────────────
def _type_prompt(page, prompt: str) -> bool:
    selectors = [
        "rich-textarea div[contenteditable='true']",
        "div[role='textbox'][contenteditable='true']",
        "div.ql-editor[contenteditable='true']",
        "div[contenteditable='true']",
    ]

    textarea = None
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=10000)
            textarea = loc
            print(f"  입력창 찾음: {sel}", flush=True)
            break
        except Exception:
            continue

    if textarea is None:
        print("  ❌ 입력창 없음", flush=True)
        return False

    textarea.click()
    page.wait_for_timeout(400)

    # 방법 1: clipboard + paste
    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        page.evaluate("(t) => navigator.clipboard.writeText(t)", prompt)
        page.keyboard.press("Control+v")
        page.wait_for_timeout(1000)
        val = textarea.inner_text()
        if len(val.strip()) > 10:
            print(f"  방법1(clipboard) 성공: {len(val)}자", flush=True)
            return True
        print("  방법1 실패 → 방법2", flush=True)
    except Exception as e:
        print(f"  방법1 오류: {e}", flush=True)

    # 방법 2: execCommand
    try:
        textarea.click()
        page.wait_for_timeout(300)
        page.keyboard.press("Control+a")
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)
        page.evaluate(
            """(t) => {
                document.activeElement.focus();
                document.execCommand('insertText', false, t);
            }""",
            prompt,
        )
        page.wait_for_timeout(800)
        val = textarea.inner_text()
        if len(val.strip()) > 10:
            print(f"  방법2(execCommand) 성공: {len(val)}자", flush=True)
            return True
        print("  방법2 실패 → 방법3", flush=True)
    except Exception as e:
        print(f"  방법2 오류: {e}", flush=True)

    # 방법 3: keyboard.type (청크)
    try:
        textarea.click()
        page.wait_for_timeout(300)
        page.keyboard.press("Control+a")
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)
        for i in range(0, len(prompt), 500):
            page.keyboard.type(prompt[i:i+500], delay=0)
            page.wait_for_timeout(100)
        val = textarea.inner_text()
        if len(val.strip()) > 10:
            print(f"  방법3(keyboard.type) 성공: {len(val)}자", flush=True)
            return True
        print("  방법3 실패", flush=True)
    except Exception as e:
        print(f"  방법3 오류: {e}", flush=True)

    return False


def _send_message(page) -> None:
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
            if btn.is_visible(timeout=2000):
                btn.click()
                print(f"  전송 버튼: {sel}", flush=True)
                return
        except Exception:
            continue
    page.keyboard.press("Enter")
    print("  Enter로 전송", flush=True)


def _get_response_text(page) -> str:
    """현재 마지막 응답 텍스트 반환. 없으면 빈 문자열."""
    selectors = [
        "model-response .markdown.markdown-main-panel",
        "model-response .response-content",
        ".response-container-content .markdown",
        "message-content .markdown",
        "model-response",
    ]
    for sel in selectors:
        try:
            els = page.locator(sel)
            if els.count() > 0:
                return els.last.inner_text()
        except Exception:
            continue
    return ""


def _wait_response_stable(page, timeout_s: int = 240,
                           stable_s: float = 4.0) -> str:
    """
    응답 텍스트 길이가 stable_s 초 동안 변하지 않으면 완료로 판단.
    Stop 버튼에 의존하지 않아 더 안정적.

    타임아웃 시 현재까지 받은 텍스트를 반환 (빈 문자열이면 오류).
    """
    print("  응답 대기 중 (안정화 감지)...", flush=True)

    # 응답 시작 대기 (최대 30초)
    start_wait = time.time()
    while time.time() - start_wait < 30:
        try:
            text = _get_response_text(page)
            if len(text.strip()) > 5:
                break
        except PWError:
            pass
        page.wait_for_timeout(500)

    # 안정화 대기
    last_len    = -1
    stable_since = time.time()
    deadline     = time.time() + timeout_s

    while time.time() < deadline:
        try:
            text     = _get_response_text(page)
            curr_len = len(text)

            if curr_len != last_len:
                last_len     = curr_len
                stable_since = time.time()
                print(f"  응답 수신 중: {curr_len}자...", end="\r", flush=True)
            else:
                elapsed = time.time() - stable_since
                if curr_len > 50 and elapsed >= stable_s:
                    print(f"\n  응답 완료: {curr_len}자 ({elapsed:.1f}초 안정)", flush=True)
                    return text

        except PWError as e:
            print(f"\n  ⚠️  페이지 오류: {e}", flush=True)
            break
        except Exception:
            pass

        page.wait_for_timeout(800)

    # 타임아웃 — 현재까지 받은 텍스트 반환
    text = _get_response_text(page)
    if text.strip():
        print(f"\n  ⚠️  타임아웃 — 현재 응답 사용: {len(text)}자", flush=True)
        return text

    raise RuntimeError("응답 타임아웃 및 텍스트 없음")


# ── 로그인 ────────────────────────────────────────────
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


# ── 생성 ─────────────────────────────────────────────
def do_generate(prompt_file: str, out_file: str):
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    print(f"  프롬프트 로드: {len(prompt)}자", flush=True)

    with sync_playwright() as p:
        ctx  = _get_context(p)
        page = ctx.new_page()

        try:
            page.goto("https://gemini.google.com/app", timeout=30000)
            page.wait_for_timeout(3000)

            if "accounts.google.com" in page.url:
                print("  ⚠️  로그인 필요: python run.py --stage login 먼저 실행",
                      file=sys.stderr)
                ctx.close()
                sys.exit(2)

            print(f"  페이지 로드: {page.url}", flush=True)

            ok = _type_prompt(page, prompt)
            if not ok:
                ctx.close()
                sys.exit(1)

            _send_message(page)

            response_text = _wait_response_stable(page, timeout_s=240, stable_s=4.0)

        except PWError as e:
            print(f"\n  ❌ Playwright 오류: {e}", flush=True)
            ctx.close()
            sys.exit(1)
        except Exception as e:
            print(f"\n  ❌ 오류: {e}", flush=True)
            ctx.close()
            sys.exit(1)

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
