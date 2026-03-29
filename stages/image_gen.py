"""
3단계: 세그먼트별 이미지 생성
- 도입/마무리  : 고정 배경 + 날짜 텍스트
- 리스트       : 고정 배경 + 헤더 + 자막 + 3종목 카드 (미디어 박스)
- 개별 종목    : 고정 배경 + 헤더 + 자막(이유) + matplotlib 차트 (미디어 박스)
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

import config

W, H = config.VIDEO_W, config.VIDEO_H

# ── 색상 ────────────────────────────────────────────
COLOR_RISE  = "#FF4444"   # 급등 (한국 주식: 빨강)
COLOR_FALL  = "#4488FF"   # 급락 (한국 주식: 파랑)
COLOR_WHITE = "#FFFFFF"
COLOR_GRAY  = "#CCCCCC"
COLOR_BG    = "#0D0D0D"   # 배경 fallback


# ── 폰트 헬퍼 ───────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = config.FONT_BOLD if bold else config.FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ── 배경 로드 ────────────────────────────────────────
def _load_bg(path: str) -> Image.Image:
    try:
        return Image.open(path).convert("RGB").resize((W, H), Image.LANCZOS)
    except Exception:
        return Image.new("RGB", (W, H), COLOR_BG)


# ── 텍스트 중앙 정렬 ─────────────────────────────────
def _center_text(draw: ImageDraw.ImageDraw, text: str,
                 y: int, font: ImageFont.FreeTypeFont,
                 color: str = COLOR_WHITE, x: int | None = None):
    if x is None:
        x = W // 2
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((x - tw // 2, y), text, font=font, fill=color)


# ── 텍스트 줄바꿈 ────────────────────────────────────
def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, line = [], ""
    for ch in text:
        if font.getlength(line + ch) > max_w:
            lines.append(line)
            line = ch
        else:
            line += ch
    if line:
        lines.append(line)
    return lines


# ── 레이아웃 픽셀값 ──────────────────────────────────
H_TOP = config.HEADER_TOP
H_BOT = config.HEADER_BOTTOM
C_TOP = config.CAPTION_TOP
C_BOT = config.CAPTION_BOTTOM
M_TOP = config.MEDIA_TOP
M_BOT = config.MEDIA_BOTTOM
PAD   = 60   # 좌우 여백


# ────────────────────────────────────────────────────
# 공통 베이스 레이어 (헤더 + 자막)
# ────────────────────────────────────────────────────
def _base_layer(bg_path: str, header: str, caption: str) -> Image.Image:
    img  = _load_bg(bg_path)
    draw = ImageDraw.Draw(img)

    # 헤더
    f_h = _font(62, bold=True)
    _center_text(draw, header,
                 H_TOP + (H_BOT - H_TOP) // 2 - 31,
                 f_h)

    # 자막 (줄바꿈 포함)
    f_c   = _font(44)
    lines = _wrap(caption, f_c, W - PAD * 2)
    total_h = len(lines) * 54
    y0 = C_TOP + (C_BOT - C_TOP) // 2 - total_h // 2
    for line in lines:
        _center_text(draw, line, y0, f_c, color=COLOR_GRAY)
        y0 += 54

    return img


# ────────────────────────────────────────────────────
# 도입부 / 마무리
# ────────────────────────────────────────────────────
def _date_overlay(bg_path: str, date: str, out_path: Path) -> Path:
    img  = _load_bg(bg_path)
    draw = ImageDraw.Draw(img)
    font = _font(52, bold=True)
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y. %m. %d")
    # 하단 10% 영역 중앙에 날짜 표시
    _center_text(draw, date_fmt, int(H * 0.88), font)
    img.save(out_path, quality=95)
    return out_path


def gen_intro(date: str, out_path: Path) -> Path:
    return _date_overlay(config.INTRO_BG, date, out_path)


def gen_outro(date: str, out_path: Path) -> Path:
    return _date_overlay(config.OUTRO_BG, date, out_path)


# ────────────────────────────────────────────────────
# 리스트 세그먼트 (급등/급락 3종목 나열)
# ────────────────────────────────────────────────────
def gen_list_card(is_gainer: bool, stocks: list[dict],
                  caption: str, out_path: Path) -> Path:
    bg     = config.GAINER_BG if is_gainer else config.LOSER_BG
    header = "📈  오늘의 급등주" if is_gainer else "📉  오늘의 급락주"
    color  = COLOR_RISE if is_gainer else COLOR_FALL

    img  = _base_layer(bg, header, caption)
    draw = ImageDraw.Draw(img)

    f_name = _font(56, bold=True)
    f_pct  = _font(60, bold=True)

    media_h  = M_BOT - M_TOP
    row_h    = media_h // config.TOP_N

    for i, s in enumerate(stocks):
        row_mid = M_TOP + i * row_h + row_h // 2 - 30
        sign = "+" if s["change"] >= 0 else ""

        # 종목명 (좌측)
        draw.text((PAD, row_mid), s["name"], font=f_name, fill=COLOR_WHITE)

        # 등락률 (우측)
        pct_text = f"{sign}{s['change']}%"
        bbox = draw.textbbox((0, 0), pct_text, font=f_pct)
        tw = bbox[2] - bbox[0]
        draw.text((W - PAD - tw, row_mid), pct_text, font=f_pct, fill=color)

    img.save(out_path, quality=95)
    return out_path


# ────────────────────────────────────────────────────
# 개별 종목 차트 세그먼트
# ────────────────────────────────────────────────────
def gen_chart_card(is_gainer: bool, stock_info: dict,
                   caption: str, chart_data: pd.DataFrame | None,
                   out_path: Path) -> Path:
    bg     = config.GAINER_BG if is_gainer else config.LOSER_BG
    header = "📈  오늘의 급등주" if is_gainer else "📉  오늘의 급락주"

    img = _base_layer(bg, header, caption)

    chart_img = _render_chart(stock_info, chart_data, is_gainer)

    media_w = W - PAD * 2
    media_h = M_BOT - M_TOP
    chart_img = chart_img.resize((media_w, media_h), Image.LANCZOS)
    img.paste(chart_img, (PAD, M_TOP))

    img.save(out_path, quality=95)
    return out_path


def _render_chart(stock_info: dict,
                  chart_data: pd.DataFrame | None,
                  is_gainer: bool) -> Image.Image:
    # 한국어 폰트 적용
    try:
        fp = fm.FontProperties(fname=config.FONT_REGULAR)
        plt.rcParams["font.family"] = fp.get_name()
    except Exception:
        pass

    color = COLOR_RISE if is_gainer else COLOR_FALL

    fig, ax = plt.subplots(figsize=(9, 8))
    fig.patch.set_facecolor("#111111")
    ax.set_facecolor("#111111")

    if chart_data is not None and not chart_data.empty:
        col = "종가" if "종가" in chart_data.columns else "Close"
        close = chart_data[col]
        ax.plot(close.index, close.values, color=color, linewidth=3)
        ax.fill_between(close.index, close.values, alpha=0.2, color=color)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        plt.setp(ax.get_xticklabels(), rotation=0, ha="center")
    else:
        ax.text(0.5, 0.5, "데이터 없음",
                color="white", ha="center", va="center",
                transform=ax.transAxes, fontsize=20)

    sign = "+" if stock_info["change"] >= 0 else ""
    ax.set_title(
        f"{stock_info['name']}   {sign}{stock_info['change']}%",
        color="white", fontsize=22, pad=16, loc="left"
    )
    ax.tick_params(colors="#AAAAAA", labelsize=13)
    for spine in ax.spines.values():
        spine.set_color("#333333")
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{int(x):,}")
    )
    ax.grid(axis="y", color="#222222", linestyle="--", linewidth=0.7)

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120,
                bbox_inches="tight", facecolor="#111111")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
