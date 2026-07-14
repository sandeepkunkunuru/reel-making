#!/usr/bin/env python3
"""Build word-synced, ALL-CAPS karaoke ASS captions from word timings.

Reads per-word timestamps (from `transcribe_words.py`) and emits big, punchy
reel-style captions: a few words at a time, each word lighting up (smooth `\\kf`
fill, unsung -> sung colour) in time with the real speech. Because each word's
fill spans until the next word starts, the highlight tracks the speaker's actual
pacing instead of an even split (which tends to run ahead).

Captions are chunked to at most `--max-lines` visual lines at the given font, so
the text stays big without overflowing; clause/sentence punctuation also closes
a chunk.

Usage:
    python captions/gen_captions.py IN-words.json OUT.ass \\
        --font-file /usr/share/fonts/truetype/noto/NotoSans-Bold.ttf \\
        --font-name "Noto Sans" --font-size 92 \\
        --sung 2FB6F2 --unsung FFFFFF          # colours are ASS BGR hex

Colours are ASS &HBBGGRR hex (blue-green-red), e.g. gold = 2FB6F2, white = FFFFFF.
"""
import argparse
import json

from PIL import ImageFont


def ts(s):
    cs = round(s * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, c = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{c:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words")
    ap.add_argument("out")
    ap.add_argument("--font-file", default="/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
                    help="TTF/OTF used to MEASURE wrap width (a bold sans)")
    ap.add_argument("--font-name", default="Noto Sans", help="family name libass resolves")
    ap.add_argument("--font-size", type=int, default=92)
    ap.add_argument("--sung", default="2FB6F2", help="highlight colour, ASS BGR hex")
    ap.add_argument("--unsung", default="FFFFFF", help="not-yet-spoken colour, ASS BGR hex")
    ap.add_argument("--play-w", type=int, default=1080)
    ap.add_argument("--play-h", type=int, default=1920)
    ap.add_argument("--margin-lr", type=int, default=54)
    ap.add_argument("--margin-v", type=int, default=520)
    ap.add_argument("--max-lines", type=int, default=2)
    ap.add_argument("--upper", action="store_true", default=True)
    ap.add_argument("--no-upper", dest="upper", action="store_false")
    ap.add_argument("--lead", type=float, default=0.10, help="show a line this early (s)")
    ap.add_argument("--linger", type=float, default=0.14, help="hold the last word lit (s)")
    args = ap.parse_args()

    SPACING = 1.0
    wrap_w = args.play_w - 2 * args.margin_lr - 24
    measure = ImageFont.truetype(args.font_file, args.font_size)

    def width(s):
        return measure.getlength(s) * 1.07 + SPACING * max(0, len(s) - 1)

    def wrap(words):
        lines, cur, cur_txt = [], [], ""
        for t, d in words:
            trial = (cur_txt + " " + t).strip()
            if cur and width(trial) > wrap_w:
                lines.append(cur); cur, cur_txt = [(t, d)], t
            else:
                cur.append((t, d)); cur_txt = trial
        if cur:
            lines.append(cur)
        return lines

    def norm(w):
        return w.upper() if args.upper else w

    def chunk(W):
        chunks, cur = [], []
        for w in W:
            trial = cur + [w]
            toks = [(norm(x["word"]), 0) for x in trial]
            if cur and len(wrap(toks)) > args.max_lines:
                chunks.append(cur); cur = [w]
            else:
                cur = trial
            if cur[-1]["word"][-1:] in ".!?,;:":
                chunks.append(cur); cur = []
        if cur:
            chunks.append(cur)
        return chunks

    W = json.load(open(args.words))
    rows, prev_end = [], 0.0
    for ev in chunk(W):
        start = max(prev_end, ev[0]["start"] - args.lead)
        end = ev[-1]["end"] + args.linger
        prev_end = end
        lead_cs = max(0, round((ev[0]["start"] - start) * 100))

        durs = []
        for j, w in enumerate(ev):
            if j < len(ev) - 1:
                durs.append(max(1, round((ev[j + 1]["start"] - w["start"]) * 100)))
            else:
                durs.append(max(1, round((w["end"] - w["start"]) * 100 + args.linger * 100)))
        toks = [(norm(w["word"]), d) for w, d in zip(ev, durs)]

        text = ("{\\k%d}" % lead_cs) if lead_cs else ""
        for li, line in enumerate(wrap(toks)):
            if li:
                text += r"\N"
            for t, d in line:
                text += r"{\kf%d}%s " % (d, t)
        rows.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{text.strip()}")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {args.play_w}
PlayResY: {args.play_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{args.font_name},{args.font_size},&H00{args.sung},&H00{args.unsung},&H00423931,&HB4000000,1,0,0,0,100,100,{SPACING:.1f},0,1,3.4,2.0,2,{args.margin_lr},{args.margin_lr},{args.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # PrimaryColour = the word being spoken (sung); SecondaryColour = not yet.

    with open(args.out, "w") as f:
        f.write(header + "\n".join(rows) + "\n")
    print(f"wrote {args.out}  ({len(rows)} captions, font {args.font_size})")


if __name__ == "__main__":
    main()
