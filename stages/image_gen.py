"""
이미지 생성 모듈
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

import config

W, H = config.VIDEO_W, config.VIDEO_H
COLOR_RISE  = "#FF4444"
COLOR_FALL  = "#4488FF"
COLOR_WHITE = "#FFFFFF"
COLOR_GRAY  = "#AAAAAA"
COLOR_LGRAY = "#666666"
COLOR_TAG   = "#FFD700"
COLOR_BG    = "#0D0D0D"
PAD = 60
H_TOP = config.HEADER_TOP
H_BOT = config.HEADER_BOTTOM
C_TOP = config.CAPTION_TOP
C_BOT = config.CAPTION_BOTTOM
M_TOP = config.MEDIA_TOP
M_BOT = config.MEDIA_BOTTOM

_FONT_CACHE: dict[str, str] = {}

def _find_korean_font(bold: bool = False) -> str:
    key = "bold" if bold else "regular"
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = []
    cfg = config.FONT_BOLD if bold else config.FONT_REGULAR
    candidates.append(cfg)
    font_dir = Path(config.BASE_DIR) / "assets" / "fonts"
    if font_dir.exists():
        for f in sorted(font_dir.glob("*.ttf")):
            name = f.name.lower()
            if bold and any(k in name for k in ["bold", "bd"]):
                candidates.insert(1, str(f))
            elif not bold and not any(k in name for k in ["bold", "bd"]):
                candidates.insert(1, str(f))
    win = [
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/NanumGothicBold.ttf" if bold else "C:/Windows/Fonts/NanumGothic.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
    ]
    candidates.extend(win)
    for mf in fm.fontManager.ttflist:
        if any(k in mf.name for k in ["Nanum", "Malgun", "Gothic"]):
            candidates.append(mf.fname)
    for path in candidates:
        if path and Path(path).exists():
            _FONT_CACHE[key] = path
            return path
    _FONT_CACHE[key] = ""
    return ""

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_korean_font(bold)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _set_mpl_font():
    path = _find_korean_font(bold=False)
    if path:
        try:
            prop = fm.FontProperties(fname=path)
            plt.rcParams["font.family"] = prop.get_name()
            return prop
        except Exception:
            pass
    return None

def _load_bg(path: str) -> Image.Image:
    try:
        return Image.open(path).convert("RGB").resize((W, H), Image.LANCZOS)
    except Exception:
        return Image.new("RGB", (W, H), COLOR_BG)

def _center_text(draw, text, y, font, color=COLOR_WHITE):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=color)

def _wrap(text, font, max_w):
    lines, line = [], ""
    for ch in text:
        test = line + ch
        try:
            w = font.getlength(test)
        except Exception:
            w = len(test) * 20
        if w > max_w:
            lines.append(line)
            line = ch
        else:
            line = test
    if line:
        lines.append(line)
    return lines

def _base_layer(bg_path, header, header_color, caption):
    img  = _load_bg(bg_path)
    draw = ImageDraw.Draw(img)
    # 헤더: 124pt, 가운데, 색상
    f_h = _font(124, bold=True)
    header_y = H_TOP + (H_BOT - H_TOP) // 2 - 62
    _center_text(draw, header, header_y, f_h, color=header_color)
    # 자막
    f_c = _font(44)
    lines = _wrap(caption, f_c, W - PAD * 2)
    total = len(lines) * 56
    y0 = C_TOP + (C_BOT - C_TOP) // 2 - total // 2
    for line in lines:
        _center_text(draw, line, y0, f_c, color=COLOR_GRAY)
        y0 += 56
    return img

def _draw_sector_tag(draw, sector, x, y):
    font  = _font(32, bold=True)
    label = f"  {sector}  "
    bbox  = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    bw = tw + 20
    bh = th + 12
    draw.rounded_rectangle([x, y, x+bw, y+bh],
                           radius=10, fill="#2A2A2A",
                           outline=COLOR_TAG, width=2)
    draw.text((x+10, y+6), label, font=font, fill=COLOR_TAG)
    return bw

def _date_overlay(bg_path, date, out_path):
    img  = _load_bg(bg_path)
    draw = ImageDraw.Draw(img)
    font = _font(52, bold=True)
    date_fmt = datetime.strptime(date, "%Y%m%d").strftime("%Y. %m. %d")
    _center_text(draw, date_fmt, int(H * 0.88), font)
    img.save(out_path, quality=95)
    return out_path

def gen_intro(date, out_path):
    return _date_overlay(config.INTRO_BG, date, out_path)

def gen_outro(date, out_path):
    return _date_overlay(config.OUTRO_BG, date, out_path)

def gen_list_card(is_gainer, stocks, caption, out_path):
    bg           = config.GAINER_BG if is_gainer else config.LOSER_BG
    header       = "어제의 급등주" if is_gainer else "어제의 급락주"
    header_color = COLOR_RISE if is_gainer else COLOR_FALL
    acc_color    = COLOR_RISE if is_gainer else COLOR_FALL

    img  = _base_layer(bg, header, header_color, caption)
    draw = ImageDraw.Draw(img)

    f_name  = _font(58, bold=True)
    f_pct   = _font(64, bold=True)
    f_close = _font(36)

    media_h = M_BOT - M_TOP
    row_h   = media_h // max(len(stocks), 1)

    for i, s in enumerate(stocks):
        y_base  = M_TOP + i * row_h
        row_mid = y_base + row_h // 2
        sign    = "+" if s["change"] >= 0 else ""

        name_y = row_mid - 72
        draw.text((PAD, name_y), s["name"], font=f_name, fill=COLOR_WHITE)

        sector = s.get("sector", "") or "기타"
        _draw_sector_tag(draw, sector, PAD, name_y + 68)

        pct_text = f"{sign}{s['change']}%"
        bbox = draw.textbbox((0, 0), pct_text, font=f_pct)
        tw   = bbox[2] - bbox[0]
        draw.text((W - PAD - tw, row_mid - 72), pct_text, font=f_pct, fill=acc_color)

        close_text = f"{s['close']:,}원"
        bbox2 = draw.textbbox((0, 0), close_text, font=f_close)
        tw2   = bbox2[2] - bbox2[0]
        draw.text((W - PAD - tw2, row_mid - 4), close_text, font=f_close, fill=COLOR_LGRAY)

        if i < len(stocks) - 1:
            draw.line([(PAD, y_base + row_h - 1), (W - PAD, y_base + row_h - 1)],
                      fill="#333333", width=1)

    img.save(out_path, quality=95)
    return out_path

def gen_chart_card(is_gainer, stock_info, caption, chart_data, out_path):
    bg           = config.GAINER_BG if is_gainer else config.LOSER_BG
    header       = "어제의 급등주" if is_gainer else "어제의 급락주"
    header_color = COLOR_RISE if is_gainer else COLOR_FALL

    img = _base_layer(bg, header, header_color, caption)

    chart_img = _render_chart(stock_info, chart_data, is_gainer)
    media_w   = W - PAD * 2
    media_h   = M_BOT - M_TOP
    chart_img = chart_img.resize((media_w, media_h), Image.LANCZOS)
    img.paste(chart_img, (PAD, M_TOP))
    img.save(out_path, quality=95)
    return out_path

def _render_chart(stock_info, chart_data, is_gainer):
    fp    = _set_mpl_font()
    color = COLOR_RISE if is_gainer else COLOR_FALL
    sign  = "+" if stock_info["change"] >= 0 else ""

    close = None
    if chart_data is not None and not chart_data.empty:
        col   = "종가" if "종가" in chart_data.columns else chart_data.columns[3]
        close = chart_data[col].iloc[-5:]

    fig, ax = plt.subplots(figsize=(9, 7))
    fig.patch.set_facecolor("#111111")
    ax.set_facecolor("#111111")

    if close is not None and not close.empty:
        labels = [d.strftime("%m/%d") if hasattr(d, "strftime")
                  else str(d)[:5] for d in close.index]
        xs = list(range(len(labels)))

        ax.plot(xs, close.values, color=color, linewidth=3,
                marker="o", markersize=8, markerfacecolor=color)
        ax.fill_between(xs, close.values, alpha=0.15, color=color)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, fontsize=15,
                           fontproperties=fp if fp else None,
                           color="#CCCCCC")

        mn, mx = float(close.min()), float(close.max())
        margin = (mx - mn) * 0.15 if mx != mn else mn * 0.05
        ax.set_ylim(mn - margin, mx + margin)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{int(x):,}")
        )
        ax.tick_params(axis="y", colors="#CCCCCC", labelsize=14)
        ax.tick_params(axis="x", length=0)
    else:
        ax.text(0.5, 0.5, "데이터 없음", color="white",
                ha="center", va="center", transform=ax.transAxes, fontsize=22)

    sector = stock_info.get("sector", "") or "기타"
    title  = f"{stock_info['name']}  {sign}{stock_info['change']}%  [{sector}]"
    ax.set_title(title, color=color, fontsize=18, pad=12, loc="left",
                 fontproperties=fp if fp else None)

    ax.grid(axis="y", color="#2A2A2A", linestyle="--", linewidth=0.8)
    ax.grid(axis="x", color="#1E1E1E", linestyle=":", linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color("#333333")

    plt.tight_layout(pad=0.8)
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=130,
                bbox_inches="tight", facecolor="#111111")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
