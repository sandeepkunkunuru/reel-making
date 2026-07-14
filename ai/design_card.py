#!/usr/bin/env python3
"""Full-AI card design — OPTIONAL, uses the `claude` CLI. Three roles, looped:

  1. ART DIRECTOR — given the quote, writes a vivid design brief (atmospheric,
     abstract; PIL renders light/gradients/particles/type well, objects poorly).
  2. ENGINEER    — writes a self-contained Python renderer (Pillow + ffmpeg) for it.
  3. ART CRITIC  — *looks at* the rendered frames and judges fidelity/quality,
     returning specific fixes. The engineer then refines. Capped by DESIGN_ATTEMPTS.

    ai/design_card.py "QUOTE" "ACCENT" OUT.mp4 WIDTH HEIGHT SECONDS
    -> writes OUT.mp4, exits 0 if a valid render was produced (best/most-refined
       one is kept), non-zero on total failure (caller uses the procedural card).

Env: CLAUDE_BIN (default claude), PY (python for the generated script),
     DESIGN_ATTEMPTS (default 3 — the max engineer<->critic rounds).
Note: this runs model-generated rendering code locally (Pillow + ffmpeg, no
network), and lets a headless review agent Read the rendered frames.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
PY = os.environ.get("PY", sys.executable)
MAX_ATTEMPTS = max(1, int(os.environ.get("DESIGN_ATTEMPTS", "3")))


def claude(prompt, timeout=600, image_dir=None):
    cmd = [CLAUDE, "-p"]
    if image_dir:                       # let the review agent Read the frames
        cmd += ["--allowedTools", "Read", "--permission-mode", "bypassPermissions",
                "--add-dir", image_dir]
    # Pass the prompt via stdin — variadic flags like --add-dir otherwise swallow it.
    return subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout).stdout


def concept_prompt(quote, accent):
    return f"""You are an art director designing a PREMIUM, minimal, watercolour-mood animated
quote card (vertical 9:16) for social media.

Quote: "{quote}"
Word to emphasize: "{accent}"

The card is rendered purely with code (Pillow drawing + gradients), so favour
ATMOSPHERIC / ABSTRACT imagery — soft light, washes, mist, gradients, drifting
particles, gentle geometric or organic forms (circles, arcs, horizons, rays,
ripples) — and AVOID literal drawn objects (hands, faces, animals, detailed
scenes), which render crudely. Evoke meaning through mood and light, not illustration.

Write a short, concrete design brief (about 120-160 words): the ATMOSPHERE that fits
the quote's meaning, a PALETTE (4-5 hex incl. one warm accent), 2-4 ANIMATED elements
and how each moves, the TEXT reveal and placement, and the MOOD in one line.
Prose only, no code."""


def code_prompt(quote, accent, brief, W, H):
    return f"""Implement this animated quote-card design as a COMPLETE, self-contained Python 3 script.

DESIGN BRIEF:
{brief}

Quote (wrapped, centered): "{quote}"   Emphasize "{accent}" in the warm accent colour.

Hard constraints:
- CLI exactly: python SCRIPT OUT_MP4 WIDTH HEIGHT SECONDS  (SECONDS is a float)
- Imports ONLY: stdlib + Pillow (PIL) + subprocess for ffmpeg. NO numpy, NO network,
  NO external files. Fonts: /usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf and
  DejaVuSerif-Italic.ttf.
- Render frames in memory (PIL), pipe raw rgb24 to ffmpeg, encode H.264 -pix_fmt
  yuv420p, 30 fps, +faststart. Silent. Size = WIDTH x HEIGHT. Fast (<= SECONDS*30 frames).
- Animate richly per the brief (NOT just a zoom). Quote must be fully legible with
  strong contrast. Final ~4 s settle and HOLD on the fully-revealed quote.
- LAYOUT: wrap the quote as ONE tidy, centered block. Keep ALL text within the central
  safe area — avoid the top ~14% and bottom ~14%, and especially the top-left and
  bottom-left corners (reserved for logos). No text may touch the frame edges.

Output ONLY the Python code. No prose, no markdown fences."""


def critic_prompt(quote, accent, brief, mid, end):
    return f"""You are the art director reviewing a rendered animated quote card against your brief.

BRIEF:
{brief}

Quote: "{quote}"  (accent word: "{accent}")

Read these two rendered frames (mid-animation and final held frame):
{mid}
{end}

Judge honestly: does it realise the brief's atmosphere? Is it PREMIUM, tasteful, and
well-composed? Is the quote fully legible with good contrast and the accent correct?
Are there crude/ugly elements?

Reply ONLY JSON: {{"ok": true|false, "issues": "specific, actionable fixes for the
renderer code — composition, palette, contrast, motion, legibility — empty if great"}}"""


def extract_code(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = m.group(1) if m else text
    i = re.search(r"(?m)^(#!|import |from )", code)
    return code[i.start():] if i else code


def render(code, out, W, H, secs):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code); script = f.name
    try:
        r = subprocess.run([PY, script, out, W, H, secs], capture_output=True, text=True, timeout=300)
    finally:
        os.unlink(script)
    if r.returncode != 0:
        return r.stderr or r.stdout
    try:
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", out], capture_output=True, text=True, timeout=30).stdout.strip()
        if not d or abs(float(d) - float(secs)) > 2.5:
            return f"bad output duration: {d}"
    except Exception as e:
        return f"validate failed: {e}"
    return None   # ok


def frames(video, d):
    mid, end = os.path.join(d, "mid.png"), os.path.join(d, "end.png")
    subprocess.run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-ss", "3",
                    "-i", video, "-frames:v", "1", mid], timeout=60)
    subprocess.run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-sseof", "-2",
                    "-i", video, "-frames:v", "1", end], timeout=60)
    return mid, end


def main():
    quote, accent, out, W, H, secs = sys.argv[1:7]
    try:
        brief = claude(concept_prompt(quote, accent), timeout=200).strip()
    except Exception:
        brief = ""
    if brief:
        sys.stderr.write("· brief:\n" + brief[:500] + "\n")

    have_valid = False
    prev_code = feedback = None
    with tempfile.TemporaryDirectory() as fd:
        for attempt in range(MAX_ATTEMPTS):
            p = code_prompt(quote, accent, brief or "(design it yourself, tastefully)", W, H)
            if prev_code and feedback:
                p += (f"\n\nYour previous script rendered a card with these problems:\n{feedback}\n\n"
                      f"Here is your previous script:\n{prev_code}\n\nRewrite it to fix those problems. "
                      "Output ONLY the corrected code.")
            try:
                code = extract_code(claude(p, timeout=600))
            except Exception as e:
                feedback = str(e); continue
            if "ffmpeg" not in code or ("PIL" not in code and "Image" not in code):
                feedback = "code must use PIL + ffmpeg"; prev_code = code; continue
            tmp_out = out + ".tmp.mp4"
            err = render(code, tmp_out, W, H, secs)
            prev_code = code
            if err:
                feedback = err[-1200:]
                sys.stderr.write(f"· attempt {attempt+1}: render failed\n"); continue
            shutil.move(tmp_out, out); have_valid = True     # keep most-refined valid render
            mid, end = frames(out, fd)
            ok, issues = False, "improve composition, contrast and premium feel"
            try:
                rv = claude(critic_prompt(quote, accent, brief, mid, end), timeout=240, image_dir=fd)
                m = re.search(r"\{.*\}", rv, re.S)
                j = json.loads(m.group(0)) if m else {}
                ok = bool(j.get("ok"))
                issues = j.get("issues") or issues
            except Exception as e:
                issues = f"(critic unavailable: {e}) {issues}"
            sys.stderr.write(f"· attempt {attempt+1}: critic ok={ok} — {issues[:180]}\n")
            if ok:
                break
            feedback = issues
    if have_valid:
        print("AI-designed card ready")
        sys.exit(0)
    sys.stderr.write((feedback or "unknown")[-400:] + "\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
