#!/usr/bin/env python3
"""Render a minimal, tasteful quote card (still PNG) for a reel.

A clean procedural card: soft paper background with a faint vignette, the quote
auto-wrapped in a serif, an optional accent phrase in a warm colour, a small
divider, and an optional attribution. Deliberately minimal — leave the visual
quiet so the words carry it. Pair with `animate_card.py` to bring it to motion.

Usage:
    python cards/gen_card.py --quote "…" --out card.png \\
        [--accent "phrase to colour"]... [--attrib "— Name"] \\
        [--size 1080x1920] [--font /path/serif.ttf]
"""
import argparse

from PIL import Image, ImageDraw, ImageFont, ImageFilter


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur); cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quote", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--accent", action="append", default=[],
                    help="substring(s) to render in the accent colour")
    ap.add_argument("--attrib", default="")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--paper", default="F6EFE5")
    ap.add_argument("--ink", default="36312B")
    ap.add_argument("--accent-color", default="B0462E")
    ap.add_argument("--font", default="/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
    ap.add_argument("--font-size", type=int, default=58)
    args = ap.parse_args()

    W, H = (int(x) for x in args.size.lower().split("x"))
    S = 2                                   # supersample for crisp text
    CW, CH = W * S, H * S
    paper, ink, acc = hex_rgb(args.paper), hex_rgb(args.ink), hex_rgb(args.accent_color)

    img = Image.new("RGB", (CW, CH), paper)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(args.font, args.font_size * S)
    ital_path = args.font.replace("DejaVuSerif.ttf", "DejaVuSerif-Italic.ttf")
    try:
        ital = ImageFont.truetype(ital_path, int(args.font_size * 0.7) * S)
    except Exception:
        ital = font

    margin = int(CW * 0.11)
    max_w = CW - 2 * margin
    lines = wrap(draw, args.quote, font, max_w)
    lh = int(args.font_size * 1.5 * S)
    block_h = lh * len(lines)
    y = (CH - block_h) // 2 - int(CH * 0.06)

    # small top divider
    cx = CW // 2
    draw.line([(cx - 34 * S, y - 60 * S), (cx + 34 * S, y - 60 * S)], fill=acc, width=2 * S)
    draw.ellipse([cx - 3 * S, y - 63 * S, cx + 3 * S, y - 57 * S], fill=acc)

    acc_lc = [a.lower() for a in args.accent]

    def colour_for(word):
        wl = word.strip(".,;:!?—").lower()
        for a in acc_lc:
            if wl and wl in a.split():
                return acc
        return ink

    for line in lines:
        lw = draw.textlength(line, font=font)
        x = (CW - lw) // 2
        for word in line.split():
            draw.text((x, y), word, font=font, fill=colour_for(word))
            x += draw.textlength(word + " ", font=font)
        y += lh

    if args.attrib:
        aw = draw.textlength(args.attrib, font=ital)
        draw.text(((CW - aw) // 2, y + 30 * S), args.attrib, font=ital, fill=ink)

    # faint vignette
    vig = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(vig).ellipse([-CW * 0.2, -CH * 0.15, CW * 1.2, CH * 1.15], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(CW // 6))
    dark = Image.new("RGB", (CW, CH), (max(ink[0], 20) - 20, 18, 16))
    img = Image.composite(img, Image.blend(img, dark, 0.12), vig)

    img.resize((W, H), Image.LANCZOS).save(args.out, "PNG")
    print(f"wrote {args.out} ({W}x{H}, {len(lines)} lines)")


if __name__ == "__main__":
    main()
