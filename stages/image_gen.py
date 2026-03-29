"""
세그먼트별 이미지 생성 (1080x1920)

레이아웃:
  [0~18%]   헤더
  [20~35%]  자막
  [37~90%]  미디어 박스
  [91~100%] 하단 여백
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

import config

W, H = config.VIDEO_W, config.VIDEO_H

COLOR_RISE   = "#FF3333"
COLOR_FALL   = "#3366FF"
COLOR_WHITE  = "#FFFFFF"
COLOR_GRAY   = "#CCCCCC"
COLOR_DARK   = "#999999"
COLOR_BG     = "#0D0D0D"
COLOR_TAG_BG = "#2A2A2A"
COLOR_TAG_BD = "#FFD700"
COLOR_TAG_FG = "#FFD700"
COLOR_ROW_BG = "#1A1A1A"   # 리스트 행 배경

PAD   = 80
H_TOP = config.HEADER_TOP
H_BOT = config.HEADER_BOTTOM
C_TOP = config.CAPTION_TOP
C_BOT = config.CAPTION_BOTTOM
M_TOP = config.MEDIA_TOP
M_BOT = config.MEDIA_BOTTOM


# ════════════════════════════════════════════════════
#  폰트
# ════════════════════════════════════════════════════
def _find_font_path(bold: bool = False) -> str:
    cfg = config.FONT_BOLD if bold else config.FONT_REGULAR
    win = ["C:/Windows/Fonts/malgunbd.ttf",
           "C:/Windows/Fonts/NanumGothicBold.ttf"] if bold else \
          ["C:/Windows/Fonts/malgun.ttf",
           "C:/Windows/Fonts/NanumGothic.ttf",
           "C:/Windows/Fonts/gulim.ttf"]
    candidates = [cfg] + win
    font_dir = Path(config.BASE_DIR) / "assets" / "fonts"
    if font_dir.exists():
        for f in sorted(font_dir.glob("*.ttf")):
            candidates.append(str(f))
    for p in candidates:
        if p and Path(p).exists():
            return p
    return ""


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_font_path(bold)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default(size=max(size, 10))


# ════════════════════════════════════════════════════
#  배경
# ════════════════════════════════════════════════════
def _load_bg(path: str) -> Image.Image:
    p = Path(path)
    if p.exists():
        try:
            return Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        except Exception as e:
            print(f"   [image] 배경 로드 실패 ({p.name}): {e}")
    return Image.new("RGB", (W, H), COLOR_BG)


# ════════════════════════════════════════════════════
#  텍스트 유틸
# ════════════════════════════════════════════════════
def _tw(draw: ImageDraw.ImageDraw, text: str,
        font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(draw: ImageDraw.ImageDraw, text: str,
        font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _draw_center(draw: ImageDraw.ImageDraw, text: str, y: int,
                 font: ImageFont.FreeTypeFont, color: str = COLOR_WHITE):
    x = (W - _tw(draw, text, font)) // 2
    draw.text((x, y), text, font=font, fill=color)


def _word_wrap(text: str, font: ImageFont.FreeTypeFont,
               max_w: int) -> list[str]:
    """
    단어(공백) 단위로 줄바꿈.
    한국어 어절 기준으로 max_w 초과 시 줄 분리.
    """
    words = text.split(" ")
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = (current + " " + word).strip()
        try:
            w = font.getlength(candidate)
        except Exception:
            w = len(candidate) * 20
        if w > max_w and current:
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)
    return lines


# ════════════════════════════════════════════════════
#  헤더
# ════════════════════════════════════════════════════
def _draw_header(draw: ImageDraw.ImageDraw, is_gainer: bool):
    text  = "어제의 급등주" if is_gainer else "어제의 급락주"
    color = COLOR_RISE if is_gainer else COLOR_FALL
    font  = _font(124, bold=True)
    y     = H_TOP + (H_BOT - H_TOP) // 2 - 62
    _draw_center(draw, text, y, font, color)


# ════════════════════════════════════════════════════
#  자막 (단어 단위 줄바꿈)
# ════════════════════════════════════════════════════
def _draw_caption(draw: ImageDraw.ImageDraw, caption: str):
    font   = _font(44)
    lines  = _word_wrap(caption, font, W - PAD * 2)
    line_h = 58
    total  = len(lines) * line_h
    y0     = C_TOP + (C_BOT - C_TOP) // 2 - total // 2
    for line in lines:
        _draw_center(draw, line, y0, font, COLOR_GRAY)
        y0 += line_h


# ════════════════════════════════════════════════════
#  섹터 태그
# ════════════════════════════════════════════════════
def _draw_sector_tag(draw: ImageDraw.ImageDraw,
                     sector: str, x: int, y: int) -> tuple[int, int]:
    """섹터 배지를 그리고 (배지 너비, 배지 높이) 반환"""
    if not sector or sector in ("기타", ""):
        return 0, 0
    font  = _font(30, bold=True)
    text  = f" {sector} "
    bb    = draw.textbbox((0, 0), text, font=font)
    tw    = bb[2] - bb[0]
    th    = bb[3] - bb[1]
    px, py = 18, 10
    bw = tw + px * 2
    bh = th + py * 2
    draw.rounded_rectangle(
        [x, y, x + bw, y + bh],
        radius=10, fill=COLOR_TAG_BG, outline=COLOR_TAG_BD, width=2,
    )
    draw.text((x + px, y + py), text, font=font, fill=COLOR_TAG_FG)
    return bw, bh


# ════════════════════════════════════════════════════
#  도입부 / 마무리
# ════════════════════════════════════════════════════
def _date_overlay(bg_path: str, date: str, out_path: Path) -> Path:
    img  = _load_bg(bg_path)
    draw = ImageDraw.Draw(img)
    font = _font(56, bold=True)
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y. %m. %d")
    _draw_center(draw, date_fmt, int(H * 0.88), font, COLOR_WHITE)
    img.save(out_path, quality=95)
    return out_path


def gen_intro(date: str, out_path: Path) -> Path:
    return _date_overlay(config.INTRO_BG, date, out_path)


def gen_outro(date: str, out_path: Path) -> Path:
    return _date_overlay(config.OUTRO_BG, date, out_path)


# ════════════════════════════════════════════════════
#  리스트 카드
# ════════════════════════════════════════════════════
def gen_list_card(is_gainer: bool, stocks: list[dict],
                  caption: str, out_path: Path) -> Path:
    """
    미디어 박스 안에 3종목 행을 세로 나열.
    각 행에 반투명 배경 패널 적용.
    좌우 여백을 PAD*2로 좁혀 가운데로 모음.
    """
    bg    = config.GAINER_BG if is_gainer else config.LOSER_BG
    color = COLOR_RISE if is_gainer else COLOR_FALL

    img  = _load_bg(bg)
    draw = ImageDraw.Draw(img)
    _draw_header(draw, is_gainer)
    _draw_caption(draw, caption)

    # 미디어 박스 전체 배경
    box_x0, box_x1 = PAD, W - PAD
    media_h = M_BOT - M_TOP
    row_h   = media_h // 3

    f_name  = _font(54, bold=True)
    f_pct   = _font(60, bold=True)
    f_close = _font(34)

    for i, s in enumerate(stocks[:3]):
        ry0 = M_TOP + i * row_h
        ry1 = ry0 + row_h

        # 행 배경 (짝수/홀수 교대) - numpy 없이 Pillow RGBA 합성
        row_color = "#1E1E1E" if i % 2 == 0 else "#141414"
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        r, g, b = _hex_to_rgb(row_color)
        ov_draw.rectangle(
            [box_x0, ry0 + 2, box_x1, ry1 - 2],
            fill=(r, g, b, 210)
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        name   = s.get("name", "")
        sector = s.get("sector", "")
        change = s.get("change", 0)
        close  = s.get("close", 0)
        sign   = "+" if change >= 0 else ""

        row_mid = ry0 + row_h // 2

        # 종목명 (좌측, PAD*2 안쪽)
        name_y = row_mid - 62
        draw.text((PAD + 20, name_y), name, font=f_name, fill=COLOR_WHITE)

        # 섹터 태그 (종목명 아래)
        _draw_sector_tag(draw, sector, PAD + 20, name_y + 68)

        # 등락률 (우측, PAD*2 안쪽)
        pct_text = f"{sign}{change}%"
        tw_pct = _tw(draw, pct_text, f_pct)
        draw.text((W - PAD - 20 - tw_pct, name_y - 4),
                  pct_text, font=f_pct, fill=color)

        # 종가 (등락률 아래)
        close_text = f"{close:,}원"
        tw_close = _tw(draw, close_text, f_close)
        draw.text((W - PAD - 20 - tw_close, name_y + 70),
                  close_text, font=f_close, fill=COLOR_DARK)

        # 행 구분선
        if i < 2:
            draw.line([(box_x0, ry1 - 1), (box_x1, ry1 - 1)],
                      fill="#333333", width=1)

    img.save(out_path, quality=95)
    return out_path


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ════════════════════════════════════════════════════
#  개별 종목 차트 카드
# ════════════════════════════════════════════════════
def gen_chart_card(is_gainer: bool, stock_info: dict,
                   caption: str, chart_data: pd.DataFrame | None,
                   out_path: Path) -> Path:
    bg = config.GAINER_BG if is_gainer else config.LOSER_BG
    img  = _load_bg(bg)
    draw = ImageDraw.Draw(img)
    _draw_header(draw, is_gainer)
    _draw_caption(draw, caption)

    chart_img = _render_chart(stock_info, chart_data, is_gainer)
    mw = W - PAD * 2
    mh = M_BOT - M_TOP
    chart_img = chart_img.resize((mw, mh), Image.LANCZOS)
    img.paste(chart_img, (PAD, M_TOP))

    img.save(out_path, quality=95)
    return out_path


def _render_chart(stock_info: dict,
                  chart_data: pd.DataFrame | None,
                  is_gainer: bool) -> Image.Image:
    color  = COLOR_RISE if is_gainer else COLOR_FALL
    name   = stock_info.get("name", "")
    change = stock_info.get("change", 0)
    sector = stock_info.get("sector", "")
    sign   = "+" if change >= 0 else ""

    # matplotlib 한글 폰트
    fp_path = _find_font_path(bold=False)
    if fp_path:
        try:
            import matplotlib.font_manager as fm
            prop = fm.FontProperties(fname=fp_path)
            plt.rcParams["font.family"] = prop.get_name()
        except Exception:
            pass

    fig = plt.figure(figsize=(9, 8.5))
    # 상단에 종목 타이틀 영역 / 하단에 차트
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 4], hspace=0.08)
    ax_title = fig.add_subplot(gs[0])
    ax       = fig.add_subplot(gs[1])

    fig.patch.set_facecolor("#111111")
    ax_title.set_facecolor("#1A1A1A")
    ax.set_facecolor("#111111")

    # ── 타이틀 영역 ──────────────────────────────
    ax_title.set_xlim(0, 1)
    ax_title.set_ylim(0, 1)
    ax_title.axis("off")

    # 종목명 (중앙, 크게)
    ax_title.text(0.5, 0.65, name,
                  ha="center", va="center",
                  fontsize=28, fontweight="bold",
                  color=COLOR_WHITE,
                  transform=ax_title.transAxes)

    # 등락률 + 섹터 (종목명 아래)
    sector_str = f"  [{sector}]" if sector and sector not in ("기타", "") else ""
    sub_text   = f"{sign}{change}%{sector_str}"
    ax_title.text(0.5, 0.2, sub_text,
                  ha="center", va="center",
                  fontsize=22, fontweight="bold",
                  color=color,
                  transform=ax_title.transAxes)

    # ── 차트 영역 ────────────────────────────────
    if chart_data is not None and not chart_data.empty:
        col   = "종가" if "종가" in chart_data.columns else chart_data.columns[3]
        df5   = chart_data.tail(5)
        close = df5[col]
        n     = len(close)
        xs    = list(range(n))

        ax.plot(xs, close.values, color=color, linewidth=3,
                marker="o", markersize=10, markerfacecolor=color,
                markeredgewidth=0)
        ax.fill_between(xs, close.values, alpha=0.18, color=color)

        # 각 점 위 가격 레이블
        mn, mx = close.min(), close.max()
        rng    = mx - mn if mx != mn else mx * 0.05
        for xi, val in zip(xs, close.values):
            ax.annotate(f"{int(val):,}",
                        xy=(xi, val),
                        xytext=(0, 16),
                        textcoords="offset points",
                        ha="center", fontsize=14,
                        color="#DDDDDD")

        # x축 날짜
        date_labels = [d.strftime("%m/%d") for d in close.index]
        ax.set_xticks(xs)
        ax.set_xticklabels(date_labels, fontsize=16, color="#CCCCCC")
        ax.set_xlim(-0.4, n - 0.6)

        margin = rng * 0.2
        ax.set_ylim(mn - margin, mx + rng * 0.45)
    else:
        ax.text(0.5, 0.5, "데이터 없음", color="white",
                ha="center", va="center",
                transform=ax.transAxes, fontsize=20)

    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{int(v):,}")
    )
    ax.tick_params(axis="y", colors="#CCCCCC", labelsize=14)
    ax.tick_params(axis="x", colors="#CCCCCC", labelsize=16, length=0)
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.grid(axis="y", color="#2A2A2A", linestyle="--", linewidth=0.8)

    plt.tight_layout(pad=0.5)
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120,
                bbox_inches="tight", facecolor="#111111")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
