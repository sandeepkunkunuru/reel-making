#!/usr/bin/env python3
"""Bring a still quote card to gentle life: a slow Ken-Burns push with a soft
fade-in. Produces a silent MP4 the reel builder then slows/holds under music.

Usage:
    python cards/animate_card.py card.png card.mp4 [--seconds 18] [--size 1080x1920]
"""
import argparse
import subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=18)
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--zoom", type=float, default=1.08, help="end zoom factor")
    args = ap.parse_args()

    W, H = (int(x) for x in args.size.lower().split("x"))
    frames = int(args.seconds * args.fps)
    # zoompan: ease a slow zoom toward --zoom, centered; then fade in.
    zexpr = f"min(zoom+{(args.zoom - 1) / frames:.6f},{args.zoom})"
    vf = (
        f"scale={W*4}:-1,"
        f"zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={W}x{H}:fps={args.fps},"
        f"fade=t=in:st=0:d=1.0,format=yuv420p"
    )
    subprocess.run([
        "ffmpeg", "-hide_banner", "-y", "-loglevel", "error",
        "-loop", "1", "-i", args.image, "-t", str(args.seconds),
        "-vf", vf, "-c:v", "libx264", "-crf", "19", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out,
    ], check=True)
    print(f"wrote {args.out} ({args.seconds}s Ken-Burns)")


if __name__ == "__main__":
    main()
