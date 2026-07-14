#!/usr/bin/env python3
"""Bring a still quote card to life — more than a zoom.

Composites drifting *motif* particles (petals, leaves, embers, stars, blossoms,
dust) over a gentle parallax push and a soft light, then a fade-in. The motif +
palette give each quote its own mood; in AI mode the driver picks a motif that
fits the words (e.g. "compassion" → blossoms, "stillness" → dust/light).

Usage:
    python cards/animate_card.py card.png card.mp4 [--seconds 18] [--size 1080x1920]
        [--motif petals|leaves|blossom|embers|stars|dust] [--seed 0] [--zoom 1.06]
"""
import argparse
import math
import random
import subprocess

from PIL import Image, ImageDraw, ImageFilter

MOTIFS = {
    #            palette (RGB)                                   motion    count size(px)  rot   glow
    "petals":  (([(224, 122, 90), (230, 180, 140), (198, 116, 78)]), "fall", 16, (16, 40), True, False),
    "leaves":  (([(150, 161, 110), (120, 140, 90), (170, 176, 120)]), "fall", 14, (16, 36), True, False),
    "blossom": (([(236, 182, 190), (242, 202, 208), (226, 162, 176)]), "fall", 18, (14, 30), True, False),
    "embers":  (([(242, 172, 82), (250, 202, 120), (255, 150, 60)]), "rise", 22, (6, 15), False, True),
    "stars":   (([(255, 250, 236), (240, 234, 214)]), "twinkle", 42, (4, 10), False, True),
    "dust":    (([(255, 250, 240), (232, 222, 206), (245, 236, 220)]), "drift", 26, (6, 14), False, True),
}


def soft_sprite(size, glow):
    """A soft round (glow) or teardrop (petal) alpha sprite, white, to be tinted."""
    S = 64
    a = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(a)
    if glow:
        for r in range(S // 2, 0, -1):
            d.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], fill=int(255 * (1 - r / (S / 2)) ** 1.5))
    else:
        d.ellipse([S * 0.30, S * 0.06, S * 0.70, S * 0.94], fill=235)   # teardrop-ish petal
        a = a.filter(ImageFilter.GaussianBlur(2))
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image"); ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=18)
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--zoom", type=float, default=1.06)
    ap.add_argument("--motif", default="petals", choices=list(MOTIFS))
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    W, H = (int(x) for x in args.size.lower().split("x"))
    N = max(2, int(args.seconds * args.fps))
    rnd = random.Random(args.seed * 1000 + hash(args.motif) % 997)
    palette, motion, count, (smin, smax), rot, glow = MOTIFS[args.motif]
    sprite = soft_sprite((smax, smax), glow)

    card = Image.open(args.image).convert("RGB")
    # particles: x,y in [0,1] card space, size px, drift speed, sway, phase, spin, colour
    P = []
    for _ in range(count):
        P.append(dict(
            x=rnd.random(), y=rnd.random(), s=rnd.uniform(smin, smax),
            v=rnd.uniform(0.04, 0.12), sway=rnd.uniform(10, 40), ph=rnd.uniform(0, 6.28),
            spin=rnd.uniform(-40, 40), col=rnd.choice(palette), a=rnd.uniform(0.35, 0.8)))

    enc = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-",
        "-vf", "fade=t=in:st=0:d=0.9,format=yuv420p",
        "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-movflags", "+faststart", args.out,
    ], stdin=subprocess.PIPE)

    for i in range(N):
        t = i / N
        # parallax push
        z = 1 + (args.zoom - 1) * t
        zw, zh = int(W * z), int(H * z)
        frame = card.resize((zw, zh), Image.LANCZOS).crop(
            ((zw - W) // 2, int((zh - H) * 0.35), (zw - W) // 2 + W, int((zh - H) * 0.35) + H)).convert("RGBA")
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for p in P:
            prog = (p["y"] + p["v"] * t * ((-1) if motion == "rise" else 1)) % 1.0
            px = p["x"] * W + math.sin(p["ph"] + t * 6.28) * p["sway"]
            py = (prog if motion != "rise" else 1 - prog) * H
            if motion == "twinkle":
                px, py = p["x"] * W, p["y"] * H
                alpha = p["a"] * (0.4 + 0.6 * abs(math.sin(p["ph"] + t * 12.56)))
            elif motion == "drift":
                px = (p["x"] + 0.05 * math.sin(p["ph"] + t * 3.14)) * W
                py = (p["y"] + 0.05 * math.cos(p["ph"] + t * 2.0)) * H
                alpha = p["a"] * (0.6 + 0.4 * math.sin(p["ph"] + t * 6.28))
            else:
                edge = min(1, prog / 0.12, (1 - prog) / 0.12)   # fade at top/bottom
                alpha = p["a"] * max(0, edge)
            if alpha <= 0.02:
                continue
            spr = sprite.resize((int(p["s"]), int(p["s"] * (1.6 if not glow else 1))), Image.LANCZOS)
            if rot:
                spr = spr.rotate(p["spin"] * t * 360 % 360, expand=True, resample=Image.BICUBIC)
            tint = Image.new("RGBA", spr.size, p["col"] + (0,))
            tint.putalpha(spr.point(lambda v: int(v * alpha)))
            layer.alpha_composite(tint, (int(px - spr.size[0] / 2), int(py - spr.size[1] / 2)))
        out = Image.alpha_composite(frame, layer).convert("RGB")
        enc.stdin.write(out.tobytes())
    enc.stdin.close()
    enc.wait()
    print(f"wrote {args.out} ({args.seconds}s, motif={args.motif})")


if __name__ == "__main__":
    main()
