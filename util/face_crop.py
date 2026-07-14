#!/usr/bin/env python3
"""Face-aware 9:16 crop for a talking-head clip.

Samples frames across the clip, detects faces (OpenCV Haar cascade), and prints a
crop geometry `W:H:X:Y` that keeps the (median) face centered — so the full-bleed
9:16 crop doesn't slice the speaker off. Prints nothing and exits non-zero if
OpenCV/cascade is unavailable or no face is found (caller falls back to a centered
crop). Best-effort: frontal faces work best; heavy occlusion (e.g. sunglasses) may
not detect, in which case we degrade gracefully.

Usage:
    python util/face_crop.py VIDEO [--ss 0] [--dur 0] [--aspect 0.5625] [--samples 14]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--ss", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=0.0)
    ap.add_argument("--aspect", type=float, default=9 / 16, help="target W/H")
    ap.add_argument("--samples", type=int, default=14)
    ap.add_argument("--cascade", default=os.path.join(HERE, "haarcascade_frontalface_default.xml"))
    args = ap.parse_args()

    try:
        import cv2
    except Exception:
        sys.exit(1)
    if not os.path.exists(args.cascade):
        sys.exit(1)
    det = cv2.CascadeClassifier(args.cascade)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(1)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    iw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ih = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = args.dur if args.dur > 0 else (total / fps if total else 0)

    centers, sizes = [], []
    for k in range(args.samples):
        t = args.ss + (dur * (k + 0.5) / args.samples if dur else k)
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = det.detectMultiScale(gray, 1.1, 5, minSize=(int(ih * 0.08), int(ih * 0.08)))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])   # largest face
            centers.append((x + w / 2, y + h / 2))
            sizes.append(h)
    cap.release()

    if len(centers) < max(3, args.samples // 4):    # too few detections → not confident
        sys.exit(2)

    centers.sort(key=lambda c: c[0]); fcx = centers[len(centers) // 2][0]
    centers.sort(key=lambda c: c[1]); fcy = centers[len(centers) // 2][1]

    def even(v):
        return int(v) - (int(v) % 2)

    if iw / ih > args.aspect:                       # wider than 9:16 → crop width, full height
        cw, ch = even(ih * args.aspect), even(ih)
        x = min(max(int(fcx - cw / 2), 0), iw - cw); y = 0
    else:                                           # taller → crop height, bias face high
        cw, ch = even(iw), even(iw / args.aspect)
        x = 0; y = min(max(int(fcy - ch * 0.42), 0), ih - ch)
    print(f"{cw}:{ch}:{x}:{y}")


if __name__ == "__main__":
    main()
