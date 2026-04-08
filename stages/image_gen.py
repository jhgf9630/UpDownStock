"""
세그먼트별 이미지 생성 (1080x1920) — 카드형 UI

레이아웃:
  [0~15%]   헤더 (상단 여백 확보, 폰트 살짝 축소)
  [17~32%]  자막
  [34~92%]  미디어 박스 (카드형)
  [92~100%] 하단 여백

textbbox 사용 원칙:
  bbox = draw.textbbox((0,0), text, font=font)
  tw = bbox[2] - bbox[0]   ← 반드시 인덱스로 int 추출
  th = bbox[3] - bbox[1]
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

# ── 색상 ─────────────────────────────────────────────
COLOR_RISE    = "#FF4D4D"   # 코랄 레드 (급등)
COLOR_FALL    = "#4D79FF"   # 소프트 블루 (급락)
COLOR_WHITE   = "#FFFFFF"
COLOR_GRAY    = "#CCCCCC"
COLOR_DARK    = "#888888"
COLOR_BG      = "#0D0D0D"

# 카드
CARD_BG       = "#1A1E2E"
CARD_BORDER   = "#2A2F40"
CARD_RADIUS   = 25

# 섹터 태그
TAG_BG        = "#252A3A"
TAG_BORDER    = "#FFD700"
TAG_FG        = "#FFD700"

# ── 여백 ─────────────────────────────────────────────
LPAD = 85    # 화면 좌우 여백
CARD_PAD = 32  # 카드 내부 좌우 패딩

# ── 레이아웃 픽셀 ────────────────────────────────────
H_TOP = int(H * 0.00)
H_BOT = int(H * 0.15)
C_TOP = int(H * 0.17)
C_BOT = int(H * 0.32)
M_TOP = int(H * 0.36)
M_BOT = int(H * 0.90)


# ════════════════════════════════════════════════════
#  폰트
# ════════════════════════════════════════════════════
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
#  텍스트 크기 측정 (항상 int 반환)
# ════════════════════════════════════════════════════
def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0])   # ← tuple 인덱스로 int 추출


def _text_h(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[3] - bbox[1])


# ════════════════════════════════════════════════════
#  공통 그리기 헬퍼
# ════════════════════════════════════════════════════
def _draw_center_x(draw: ImageDraw.ImageDraw, text: str, y: int,
                   font, color: str = COLOR_WHITE) -> None:
    """수평 중앙 정렬"""
    tw = _text_w(draw, text, font)
    x  = int((W - tw) // 2)
    draw.text((x, y), text, font=font, fill=color)


def _draw_right(draw: ImageDraw.ImageDraw, text: str, y: int,
                right_edge: int, font, color: str) -> None:
    """오른쪽 정렬 (right_edge 기준)"""
    tw = _text_w(draw, text, font)
    x  = int(right_edge - tw)
    draw.text((x, y), text, font=font, fill=color)


# ════════════════════════════════════════════════════
#  헤더 (상단 여백 확보, 폰트 살짝 축소 110→100)
# ════════════════════════════════════════════════════
def _draw_header(draw: ImageDraw.ImageDraw, is_gainer: bool) -> None:
    text  = "어제의 급등주" if is_gainer else "어제의 급락주"
    color = COLOR_RISE if is_gainer else COLOR_FALL
    font  = _font(120, bold=True)   # 124 → 100 (답답함 해소)
    th    = _text_h(draw, text, font)
    y     = int(H_TOP + (H_BOT - H_TOP) // 2 - th // 2) + 30
    _draw_center_x(draw, text, y, font, color)


# ════════════════════════════════════════════════════
#  자막 (단어 단위, 절반 기준 2줄)
# ════════════════════════════════════════════════════
def _word_wrap_half(text: str, font, max_w: int) -> list[str]:
    try:
        total_w = int(font.getlength(text))
    except Exception:
        total_w = len(text) * 20

    if total_w <= max_w:
        return [text]

    words = text.split(" ")
    if len(words) <= 1:
        return [text]

    best_idx, best_diff = 1, float("inf")
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


def _draw_caption(draw: ImageDraw.ImageDraw, caption: str) -> None:
    font   = _font(45, bold=True)
    lines  = _word_wrap_half(caption, font, W - LPAD * 2)
    line_h = 58
    total  = int(len(lines) * line_h)
    y0     = int(C_TOP + (C_BOT - C_TOP) // 2 - total // 2) + 60
    for line in lines:
        _draw_center_x(draw, line, y0, font, COLOR_GRAY)
        y0 += line_h + 10


# ════════════════════════════════════════════════════
#  섹터 태그
# ════════════════════════════════════════════════════
def _draw_sector_tag(draw: ImageDraw.ImageDraw,
                     sector: str, x: int, y: int,
                     font) -> tuple[int, int]:
    """태그를 그리고 (너비, 높이) 반환. 섹터 없으면 (0, 0)"""
    if not sector or sector in ("기타", ""):
        return 0, 0
    text = f" {sector} "
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = int(bbox[2] - bbox[0])
    th   = int(bbox[3] - bbox[1])
    px, py = 14, 8
    bw = tw + px * 2
    bh = th + py * 2
    draw.rounded_rectangle(
        [x, y, x + bw, y + bh],
        radius=8, fill=TAG_BG, outline=TAG_BORDER, width=2,
    )
    draw.text((x + px, y + py), text, font=font, fill=TAG_FG)
    return bw, bh


# ════════════════════════════════════════════════════
#  도입부 / 마무리
# ════════════════════════════════════════════════════
def _date_overlay(bg_path: str, date: str, out_path: Path) -> Path:
    img  = _load_bg(bg_path)
    draw = ImageDraw.Draw(img)
    font = _font(60, bold=True)
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y. %m. %d")
    _draw_center_x(draw, date_fmt, int(H * 0.88), font, COLOR_WHITE)
    img.save(out_path, quality=95)
    return out_path

def gen_announce_card(is_gainer: bool, out_path: Path) -> Path:
    """
    급등/급락 안내 전환 카드.
    배경(gainer_bg / loser_bg) 위에 큰 텍스트만 표시.
    TTS: "급등 내용입니다." / "급락 내용입니다."
    """
    bg    = config.GAINER_BG if is_gainer else config.LOSER_BG
    color = COLOR_RISE if is_gainer else COLOR_FALL
    text  = "📈 급등 종목" if is_gainer else "📉 급락 종목"
 
    img  = _load_bg(bg)
    draw = ImageDraw.Draw(img)
    font = _font(100, bold=True)
    th   = _text_h(draw, text, font)
    y    = int((H - th) // 2)
    _draw_center_x(draw, text, y, font, color)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)
    return out_path

def gen_intro(date: str, out_path: Path, market: str = "KOSPI") -> Path:
    """
    market: "KOSPI"  → kospi_intro_bg.jpg
            "KOSDAQ" → kosdaq_intro_bg.jpg
            "NASDAQ" → nasdaq_intro_bg.jpg
    """
    mkt = market.upper()
    if mkt == "KOSDAQ":
        bg = config.INTRO_BG_KOSDAQ
    elif mkt == "NASDAQ":
        bg = config.INTRO_BG_NASDAQ
    else:
        bg = config.INTRO_BG_KOSPI
    return _date_overlay(bg, date, out_path)
 
 
def gen_outro(date: str, out_path: Path) -> Path:
    return _date_overlay(config.OUTRO_BG, date, out_path)


# ════════════════════════════════════════════════════
#  리스트 카드 (카드형 UI)
# ════════════════════════════════════════════════════
def gen_list_card(is_gainer: bool, stocks: list[dict],
                  caption: str, out_path: Path) -> Path:
    """
    각 종목을 독립된 rounded_rectangle 카드 안에 배치.
    카드 내 레이아웃:
      좌측: TOP 뱃지(상단) / 종목명(중앙) / 섹터 태그(하단)
      우측: 등락률(상단) / 종가(하단)
    """
    bg    = config.GAINER_BG if is_gainer else config.LOSER_BG
    color = COLOR_RISE if is_gainer else COLOR_FALL

    img  = _load_bg(bg)
    draw = ImageDraw.Draw(img)
    _draw_header(draw, is_gainer)
    _draw_caption(draw, caption)

    media_h  = M_BOT - M_TOP
    n_stocks = min(len(stocks), 3)
    gap      = 20   # 카드 간 간격
    card_h   = int((media_h - gap * (n_stocks - 1)) / n_stocks) - 20
    card_x0  = LPAD
    card_x1  = W - LPAD

    f_badge  = _font(24, bold=True)
    f_name   = _font(55, bold=True)
    f_pct    = _font(60, bold=True)
    f_close  = _font(32)
    f_sector = _font(28, bold=True)

    for i, s in enumerate(stocks[:3]):
        cy0 = int(M_TOP + i * (card_h + gap)) + 20
        cy1 = cy0 + card_h

        # ── 카드 배경 (rounded_rectangle) ──
        draw.rounded_rectangle(
            [card_x0, cy0, card_x1, cy1],
            radius=CARD_RADIUS,
            fill=CARD_BG,
            outline=CARD_BORDER,
            width=1,
        )

        name   = s.get("name",   "")
        sector = s.get("sector", "")
        change = s.get("change", 0)
        close  = s.get("close",  0)
        sign   = "+" if change >= 0 else ""

        inner_x0 = card_x0 + CARD_PAD
        inner_x1 = card_x1 - CARD_PAD

        # ── TOP 뱃지 (카드 좌측 상단) ──
        badge_text = f"TOP {i + 1}"
        bbox_b = draw.textbbox((0, 0), badge_text, font=f_badge)
        bw = int(bbox_b[2] - bbox_b[0]) + 20
        bh = int(bbox_b[3] - bbox_b[1]) + 10
        bx0 = inner_x0
        by0 = cy0 + 25
        draw.rounded_rectangle(
            [bx0, by0, bx0 + bw, by0 + bh],
            radius=6, fill=color,
        )
        draw.text(
            (bx0 + 10, by0 + 5),
            badge_text, font=f_badge, fill=COLOR_WHITE,
        )

        # ── 종목명 수직 중앙 계산 ──
        bbox_n  = draw.textbbox((0, 0), name, font=f_name)
        name_h  = int(bbox_n[3] - bbox_n[1])
        sec_h = 0
        if sector and sector not in ("기타", ""):
            bbox_s = draw.textbbox((0, 0), f" {sector} ", font=f_sector)
            sec_h  = int(bbox_s[3] - bbox_s[1]) + 18  # bh
        gap_ns  = 10
        block_h = name_h + (sec_h + gap_ns if sec_h else 0)
        name_y  = int(cy0 + (card_h - block_h) // 2)
        
        # ── 등락률 (카드 우측 상단) ──
        pct_text = f"{sign}{change}%"
        bbox_p   = draw.textbbox((0, 0), pct_text, font=f_pct)
        pct_w    = int(bbox_p[2] - bbox_p[0])
        pct_h    = int(bbox_p[3] - bbox_p[1])
        pct_x    = int(inner_x1 - pct_w)
        pct_y    = int(cy0 + (card_h - block_h) // 2)
        draw.text((pct_x, pct_y), pct_text, font=f_pct, fill=color)

        # ── 종가 (등락률 아래, 우측) ──
        close_text = (f"${close:.2f}" if isinstance(close, float)
                      else f"{close:,}원")
        bbox_c     = draw.textbbox((0, 0), close_text, font=f_close)
        close_w    = int(bbox_c[2] - bbox_c[0])
        close_x    = int(inner_x1 - close_w)
        close_y    = pct_y + pct_h + 9
        draw.text((close_x, close_y), close_text, font=f_close, fill=COLOR_DARK)

        # ── 종목명 (좌측, 수직 중앙) ──
        # NASDAQ: close가 float이면 미국 종목 → 이름이 길 수 있으므로
        # 등락률 영역(우측)을 침범하지 않도록 최대 너비를 제한해 절삭
        _is_nasdaq_stock = isinstance(close, float)
        if _is_nasdaq_stock:
            _max_name_w = pct_x - inner_x0 - 16
            _display_name = name
            while (_text_w(draw, _display_name, f_name) > _max_name_w
                   and len(_display_name) > 1):
                _display_name = _display_name[:-1]
            if _display_name != name:
                _display_name = _display_name[:-1] + ".."
            draw.text((inner_x0, name_y), _display_name, font=f_name, fill=COLOR_WHITE)
        else:
            draw.text((inner_x0, name_y), name, font=f_name, fill=COLOR_WHITE)

        # ── 섹터 태그 (종목명 아래) ──
        if sector and sector not in ("기타", ""):
            _draw_sector_tag(
                draw, sector,
                inner_x0, name_y + name_h + gap_ns + 10,
                f_sector,
            )

    img.save(out_path, quality=95)
    return out_path


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
    mw = W - LPAD * 2
    mh = M_BOT - M_TOP - 20
    chart_img = chart_img.resize((mw, mh), Image.LANCZOS)
    img.paste(chart_img, (LPAD, M_TOP + 30))

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
            price_label = (f"${val:.2f}" if isinstance(close.iloc[0], float)
                           else f"{int(val):,}")
            ax.annotate(price_label,
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

    _is_us = (chart_data is not None and not chart_data.empty
              and "종가" in chart_data.columns
              and isinstance(chart_data["종가"].iloc[0], float))
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda v, _: f"${v:.0f}" if _is_us else f"{int(v):,}"
        )
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