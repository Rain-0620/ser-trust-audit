"""Render a Markdown document to a single tall PNG, for scroll-through video segments.

Only the subset of Markdown used by the audit reports is supported:
  # / ## / ### headings, | tables |, - bullets, **bold**, `code`.
The result is a 1280 px wide image whose height is whatever the content needs;
the video builder then scrolls a 1280x632 window down it.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_R = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
FONT_MONO = "C:/Windows/Fonts/consola.ttf"

BG = (13, 20, 36)
WHITE = (240, 245, 255)
BODY = (212, 222, 238)
ACCENT = (96, 206, 255)
CODE = (255, 196, 120)
H3C = (168, 200, 240)
GRID = (52, 68, 100)
HDRBG = (28, 40, 68)
ROWBG = (19, 27, 46)
ROWBG2 = (23, 32, 53)

_SEP = re.compile(r":?-{2,}:?")
_TOK = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


def _f(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size, index=0)
    except OSError:
        return ImageFont.truetype(FONT_R, size, index=0)


def _runs(text: str, base, base_c, bold, bold_c, code, code_c):
    out = []
    for part in _TOK.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append((part[2:-2], bold, bold_c))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append((part[1:-1], code, code_c))
        else:
            out.append((part, base, base_c))
    return out


def _draw_rich(d, x, y, runs, max_w: int, lh: int) -> int:
    """Draw styled text with wrapping. Returns the next y."""
    cx = float(x)
    for text, f, c in runs:
        for ch in text:
            w = d.textlength(ch, font=f)
            if cx + w > x + max_w:
                y += lh
                cx = float(x)
                if ch == " ":
                    continue
            d.text((round(cx), y), ch, font=f, fill=c)
            cx += w
    return y + lh


def _draw_table(d, rows: list[str], x0: int, y: int, max_w: int, sizes=(21, 19, 17, 15, 13)):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    keep = [c for c in cells if not all(_SEP.fullmatch(v or "-") for v in c)]
    if not keep:
        return y
    ncol = max(len(r) for r in keep)
    keep = [r + [""] * (ncol - len(r)) for r in keep]

    pad = 12
    f_body = f_hdr = None
    widths = None
    for size in sizes:
        fb = _f(FONT_R, size)
        fh = _f(FONT_B, size)
        ws = [0] * ncol
        for ri, r in enumerate(keep):
            f = fh if ri == 0 else fb
            for ci, v in enumerate(r):
                v = v.replace("**", "").replace("`", "")
                ws[ci] = max(ws[ci], int(d.textlength(v, font=f)))
        total = sum(w + 2 * pad for w in ws)
        if total <= max_w:
            f_body, f_hdr, widths = fb, fh, ws
            break
    if widths is None:                              # nothing fits: smallest font + clip
        f_body = f_hdr = _f(FONT_R, sizes[-1])
        ws = [0] * ncol
        for r in keep:
            for ci, v in enumerate(r):
                ws[ci] = max(ws[ci], int(d.textlength(v.replace("**", ""), font=f_body)))
        total = sum(w + 2 * pad for w in ws)
        scale = max_w / total
        widths = [int(w * scale) for w in ws]
    else:
        # natural widths fit; spread the slack so columns are not cramped at the left
        slack = max_w - sum(w + 2 * pad for w in widths)
        if slack > 0 and sum(widths):
            widths = [w + int(slack * w / sum(widths)) for w in widths]

    size = f_body.size
    rh = int(size * 1.75)
    x = x0
    d.rounded_rectangle([x0, y, x0 + max_w, y + rh * len(keep) + 8], radius=8, fill=ROWBG)
    yy = y + 4
    for ri, r in enumerate(keep):
        fill = HDRBG if ri == 0 else (ROWBG if ri % 2 else ROWBG2)
        d.rectangle([x0, yy, x0 + max_w, yy + rh], fill=fill)
        cx = x0
        for ci, v in enumerate(r):
            f = f_hdr if ri == 0 else f_body
            txt = v.replace("`", "")
            if "**" in txt:
                f = _f(FONT_B, size) if ri else f_hdr
                txt = txt.replace("**", "")
            # widths are floored ints, so allow the rounding slack back
            limit = widths[ci] + 2
            while txt and d.textlength(txt, font=f) > limit:
                txt = txt[:-1]
            col = WHITE if ri == 0 else BODY
            if not ri and v.strip().startswith("**"):
                col = (255, 190, 150)
            d.text((cx + pad, yy + (rh - size) // 2 - 2), txt, font=f, fill=col)
            cx += widths[ci] + 2 * pad
        if ri == 0:
            d.line([x0, yy + rh, x0 + max_w, yy + rh], fill=GRID, width=2)
        yy += rh
    return yy + 14


def render(md_path: Path, out_png: Path, width: int = 1280, margin: int = 60) -> int:
    md = Path(md_path).read_text(encoding="utf-8")
    cw = width - 2 * margin

    h1, h2, h3 = _f(FONT_B, 46), _f(FONT_B, 34), _f(FONT_B, 26)
    body, bold = _f(FONT_R, 23), _f(FONT_B, 23)
    code = _f(FONT_MONO, 21)

    canvas = Image.new("RGB", (width, 30000), BG)
    d = ImageDraw.Draw(canvas)
    y = margin

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            y += 13
            i += 1
            continue
        if s.startswith("|") and s.count("|") >= 3:
            blk = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                blk.append(lines[i].strip())
                i += 1
            y = _draw_table(d, blk, margin, y, cw)
            continue
        if s.startswith("### "):
            y += 12
            d.text((margin, y), s[4:], font=h3, fill=H3C)
            y += 46
        elif s.startswith("## "):
            y += 18
            d.text((margin, y), s[3:], font=h2, fill=ACCENT)
            y += 54
        elif s.startswith("# "):
            y += 8
            d.text((margin, y), s[2:], font=h1, fill=WHITE)
            y += 70
        elif s.startswith("- "):
            d.text((margin + 2, y + 2), "\u2022", font=body, fill=ACCENT)
            y = _draw_rich(d, margin + 32, y, _runs(s[2:], body, BODY, bold, WHITE, code, CODE),
                           cw - 34, 36)
        else:
            y = _draw_rich(d, margin, y, _runs(s, body, BODY, bold, WHITE, code, CODE), cw, 36)
        i += 1

    height = min(y + margin, canvas.height)
    out = canvas.crop((0, 0, width, height))
    out.save(out_png)
    return height


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    h = render(src, dst)
    print(f"rendered {src.name} -> {dst}  (1280x{h})")
