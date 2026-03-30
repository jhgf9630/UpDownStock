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

# 좌우 여백: 리스트 콘텐츠가 가장자리에 너무 붙지 않도록
LPAD = 100   # 왼쪽 여백 (종목명 시작점)
RPAD = 100   # 오른쪽 여백 (등락률 끝점)

H_TOP = config.HEADER_TOP
H_BOT = config.HEADER_BOTTOM
C_TOP = config.CAPTION_TOP
C_BOT = config.CAPTION_BOTTOM
M_TOP = config.MEDIA_TOP
M_BOT = config.MEDIA_BOTTOM


# ── 폰트 ─────────────────────────────────────────────
def _find_font_path(bold: bool = False) -> str:
    cfg = config.FONT_BOLD if bold else config.FONT_REGULAR
    win = (["C:/Windows/Fonts/malgunbd.ttf",
            "C:/Windows/Fonts/NanumGothicBold.ttf"] if bold else
           ["C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/NanumGothic.ttf",
            "C:/Windows/Fonts/gulim.ttf"])
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


# ── 배경 ─────────────────────────────────────────────
def _load_bg(path: str) -> Image.Image:
    p = Path(path)
    if p.exists():
        try:
            return Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        except Exception as e:
            print(f"   [image] 배경 로드 실패 ({p.name}): {e}")
    return Image.new("RGB", (W, H), COLOR_BG)


# ── 텍스트 측정 ───────────────────────────────────────
def _tw(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


# ── 수평 중앙 정렬 그리기 ─────────────────────────────
def _draw_center_x(draw: ImageDraw.ImageDraw, text: str, y: int,
                   font, color: str = COLOR_WHITE):
    x = (W - _tw(draw, text, font)) // 2
    draw.text((x, y), text, font=font, fill=color)


# ── 단어 단위 / 절반 기준 줄바꿈 ─────────────────────
def _word_wrap_half(text: str, font, max_w: int) -> list[str]:
    """
    텍스트가 max_w 이내면 한 줄 반환.
    초과하면 전체 너비의 절반에 가장 가까운 단어 경계에서 분리.
    """
    try:
        total_w = font.getlength(text)
    except Exception:
        total_w = len(text) * 20

    if total_w <= max_w:
        return [text]

    words = text.split(" ")
    if len(words) <= 1:
        return [text]

    best_idx  = 1
    best_diff = float("inf")
    acc = 0.0
    for i, word in enumerate(words):
        try:
            acc += font.getlength(word + " ")
        except Exception:
            acc += len(word + " ") * 20
        if i == 0:
            continue
        diff = abs(acc - total_w / 2)
        if diff < best_diff:
            best_diff = diff
            best_idx  = i

    line1 = " ".join(words[:best_idx])
    line2 = " ".join(words[best_idx:])
    return [l for l in [line1, line2] if l]


# ── 헤더 ─────────────────────────────────────────────
def _draw_header(draw: ImageDraw.ImageDraw, is_gainer: bool):
    text  = "어제의 급등주" if is_gainer else "어제의 급락주"
    color = COLOR_RISE if is_gainer else COLOR_FALL
    font  = _font(124, bold=True)
    y     = H_TOP + (H_BOT - H_TOP) // 2 - 62
    _draw_center_x(draw, text, y, font, color)


# ── 자막 ─────────────────────────────────────────────
def _draw_caption(draw: ImageDraw.ImageDraw, caption: str):
    font   = _font(44)
    lines  = _word_wrap_half(caption, font, W - LPAD * 2)
    line_h = 58
    total  = len(lines) * line_h
    y0     = C_TOP + (C_BOT - C_TOP) // 2 - total // 2
    for line in lines:
        _draw_center_x(draw, line, y0, font, COLOR_GRAY)
        y0 += line_h


# ── 섹터 태그 (왼쪽 정렬) ────────────────────────────
def _draw_sector_tag(draw: ImageDraw.ImageDraw,
                     sector: str, font,
                     x: int, y: int) -> tuple[int, int]:
    """(bw, bh) 반환. 섹터 없으면 (0,0)"""
    if not sector or sector in ("기타", ""):
        return 0, 0
    text = f" {sector} "
    try:
        tw = int(font.getlength(text))
    except Exception:
        tw = len(text) * 18
    th = font.size if hasattr(font, "size") else 30
    bw, bh = tw + 28, th + 18
    draw.rounded_rectangle(
        [x, y, x + bw, y + bh],
        radius=8, fill=COLOR_TAG_BG, outline=COLOR_TAG_BD, width=2,
    )
    draw.text((x + 14, y + 9), text, font=font, fill=COLOR_TAG_FG)
    return bw, bh


# ── 도입부 / 마무리 ───────────────────────────────────
def _date_overlay(bg_path: str, date: str, out_path: Path) -> Path:
    img  = _load_bg(bg_path)
    draw = ImageDraw.Draw(img)
    font = _font(56, bold=True)
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y. %m. %d")
    _draw_center_x(draw, date_fmt, int(H * 0.88), font, COLOR_WHITE)
    img.save(out_path, quality=95)
    return out_path


def gen_intro(date: str, out_path: Path) -> Path:
    return _date_overlay(config.INTRO_BG, date, out_path)


def gen_outro(date: str, out_path: Path) -> Path:
    return _date_overlay(config.OUTRO_BG, date, out_path)


# ── 리스트 카드 ───────────────────────────────────────
def gen_list_card(is_gainer: bool, stocks: list[dict],
                  caption: str, out_path: Path) -> Path:
    """
    3종목 리스트.
    - TOP 뱃지: 행 좌상단
    - 종목명 / 섹터: 왼쪽 정렬 (LPAD에서 시작), 행 내 수직 중앙
    - 등락률 / 종가: 오른쪽 정렬 (RPAD에서 끝), 행 내 수직 중앙
    """
    bg    = config.GAINER_BG if is_gainer else config.LOSER_BG
    color = COLOR_RISE if is_gainer else COLOR_FALL

    img  = _load_bg(bg)
    draw = ImageDraw.Draw(img)
    _draw_header(draw, is_gainer)
    _draw_caption(draw, caption)

    media_h  = M_BOT - M_TOP
    row_h    = media_h // 3

    f_badge  = _font(26, bold=True)
    f_name   = _font(56, bold=True)
    f_pct    = _font(62, bold=True)
    f_close  = _font(34)
    f_sector = _font(30, bold=True)

    for i, s in enumerate(stocks[:3]):
        ry0 = M_TOP + i * row_h
        ry1 = ry0 + row_h

        # 행 배경
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        row_col = (30, 30, 30, 200) if i % 2 == 0 else (20, 20, 20, 200)
        ov_draw.rectangle([LPAD - 20, ry0 + 3, W - RPAD + 20, ry1 - 3],
                          fill=row_col)
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        name   = s.get("name",   "")
        sector = s.get("sector", "")
        change = s.get("change", 0)
        close  = s.get("close",  0)
        sign   = "+" if change >= 0 else ""

        # ── TOP 뱃지 (좌상단 고정) ──
        badge_text = f"TOP {i + 1}"
        bb  = draw.textbbox((0, 0), badge_text, font=f_badge)
        bw  = bb[2] - bb[0] + 24
        bh_badge = bb[3] - bb[1] + 12
        draw.rounded_rectangle(
            [LPAD, ry0 + 10, LPAD + bw, ry0 + 10 + bh_badge],
            radius=6, fill=color
        )
        draw.text((LPAD + 12, ry0 + 16), badge_text,
                  font=f_badge, fill=COLOR_WHITE)

        # ── 왼쪽 블록 높이 계산 (수직 중앙 정렬) ──
        name_h  = _th(draw, name, f_name)
        _, sec_h = _draw_sector_tag.__wrapped__(sector, f_sector) \
            if hasattr(_draw_sector_tag, "__wrapped__") else \
            (0, (f_sector.size + 18) if sector and sector not in ("기타", "") else 0)

        # 섹터 높이 직접 계산
        if sector and sector not in ("기타", ""):
            sec_h = f_sector.size + 18
        else:
            sec_h = 0

        gap     = 10
        block_h = name_h + (sec_h + gap if sec_h else 0)
        content_y0 = ry0 + (row_h - block_h) // 2

        # ── 종목명 (왼쪽 정렬, 수직 중앙) ──
        draw.text((LPAD, content_y0), name, font=f_name, fill=COLOR_WHITE)

        # ── 섹터 태그 (왼쪽 정렬, 종목명 아래) ──
        if sec_h:
            _draw_sector_tag(draw, sector, f_sector,
                             LPAD, content_y0 + name_h + gap)

        # ── 등락률 (오른쪽 정렬, 수직 중앙) ──
        pct_text = f"{sign}{change}%"
        pct_h    = _th(draw, pct_text, f_pct)
        close_h  = _th(draw, f"{close:,}원", f_close)
        right_block_h = pct_h + gap + close_h
        right_y0 = ry0 + (row_h - right_block_h) // 2

        tw_pct = _tw(draw, pct_text, f_pct)
        draw.text((W - RPAD - tw_pct, right_y0),
                  pct_text, font=f_pct, fill=color)

        # ── 종가 (오른쪽 정렬, 등락률 아래) ──
        close_text = f"{close:,}원"
        tw_close   = _tw(draw, close_text, f_close)
        draw.text((W - RPAD - tw_close, right_y0 + pct_h + gap),
                  close_text, font=f_close, fill=COLOR_DARK)

        # 행 구분선
        if i < 2:
            draw.line([(LPAD - 20, ry1 - 1), (W - RPAD + 20, ry1 - 1)],
                      fill="#333333", width=1)

    img.save(out_path, quality=95)
    return out_path


# ── 개별 종목 차트 카드 ───────────────────────────────
def gen_chart_card(is_gainer: bool, stock_info: dict,
                   caption: str, chart_data: pd.DataFrame | None,
                   out_path: Path) -> Path:
    bg = config.GAINER_BG if is_gainer else config.LOSER_BG
    img  = _load_bg(bg)
    draw = ImageDraw.Draw(img)
    _draw_header(draw, is_gainer)
    _draw_caption(draw, caption)

    chart_img = _render_chart(stock_info, chart_data, is_gainer)
    mw = W - LPAD * 2
    mh = M_BOT - M_TOP
    chart_img = chart_img.resize((mw, mh), Image.LANCZOS)
    img.paste(chart_img, (LPAD, M_TOP))

    img.save(out_path, quality=95)
    return out_path


def _render_chart(stock_info: dict,
                  chart_data: pd.DataFrame | None,
                  is_gainer: bool) -> Image.Image:
    color  = COLOR_RISE if is_gainer else COLOR_FALL
    name   = stock_info.get("name",   "")
    change = stock_info.get("change", 0)
    sector = stock_info.get("sector", "")
    sign   = "+" if change >= 0 else ""

    fp_path = _find_font_path(bold=False)
    if fp_path:
        try:
            import matplotlib.font_manager as fm
            prop = fm.FontProperties(fname=fp_path)
            plt.rcParams["font.family"] = prop.get_name()
        except Exception:
            pass

    fig = plt.figure(figsize=(9, 8.5))
    gs  = fig.add_gridspec(2, 1, height_ratios=[1, 4], hspace=0.06)
    ax_t = fig.add_subplot(gs[0])
    ax   = fig.add_subplot(gs[1])

    fig.patch.set_facecolor("#111111")
    ax_t.set_facecolor("#1C1C1C")
    ax.set_facecolor("#111111")

    ax_t.set_xlim(0, 1)
    ax_t.set_ylim(0, 1)
    ax_t.axis("off")

    ax_t.text(0.5, 0.68, name,
              ha="center", va="center",
              fontsize=30, fontweight="bold",
              color=COLOR_WHITE, transform=ax_t.transAxes)

    sector_str = f"  [{sector}]" if sector and sector not in ("기타", "") else ""
    ax_t.text(0.5, 0.22, f"{sign}{change}%{sector_str}",
              ha="center", va="center",
              fontsize=24, fontweight="bold",
              color=color, transform=ax_t.transAxes)

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

        mn, mx = close.min(), close.max()
        rng    = mx - mn if mx != mn else mx * 0.05

        for xi, val in zip(xs, close.values):
            ax.annotate(f"{int(val):,}",
                        xy=(xi, val), xytext=(0, 16),
                        textcoords="offset points",
                        ha="center", fontsize=14, color="#DDDDDD")

        date_labels = [d.strftime("%m/%d") for d in close.index]
        ax.set_xticks(xs)
        ax.set_xticklabels(date_labels, fontsize=16, color="#CCCCCC")
        ax.set_xlim(-0.4, n - 0.6)
        ax.set_ylim(mn - rng * 0.2, mx + rng * 0.5)
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

    plt.tight_layout(pad=0.4)
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120,
                bbox_inches="tight", facecolor="#111111")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
