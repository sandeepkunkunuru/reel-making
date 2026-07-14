#!/usr/bin/env python3
"""Full-AI card design — OPTIONAL, uses the `claude` CLI. Two levels of prompting:

  1. ART DIRECTOR — given the quote, Claude writes a vivid, concrete design brief
     (scene, palette, animated elements, motion beats, text reveal, mood).
  2. ENGINEER    — given that brief, Claude writes a complete, self-contained
     Python renderer (Pillow + ffmpeg only) that produces the animated card.

We run the renderer, validate the output, and retry the engineer step once with
the error (keeping the concept). Falls back to the procedural card on failure.

    ai/design_card.py "QUOTE" "ACCENT" OUT.mp4 WIDTH HEIGHT SECONDS
    -> writes OUT.mp4, exits 0 on success; non-zero on failure.

Env: CLAUDE_BIN (default claude), PY (python to run the generated script).
Note: this executes model-generated rendering code locally (Pillow + ffmpeg only,
no network). Keep that in mind if you change the prompts.
"""
import os
import re
import subprocess
import sys
import tempfile

CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
PY = os.environ.get("PY", sys.executable)


def claude(prompt, timeout=240):
    r = subprocess.run([CLAUDE, "-p", prompt], capture_output=True, text=True, timeout=timeout)
    return r.stdout


def concept_prompt(quote, accent):
    return f"""You are an art director designing a PREMIUM, minimal, watercolour-mood animated
quote card (vertical 9:16) for social media.

Quote: "{quote}"
Word to emphasize: "{accent}"

The card is rendered purely with code (Pillow drawing + gradients), so favour
ATMOSPHERIC / ABSTRACT imagery — soft light, washes, mist, gradients, drifting
particles, gentle geometric or organic forms (circles, arcs, horizons, ripples,
rays) — and AVOID literal drawn objects (hands, faces, animals, detailed scenes),
which render crudely. Evoke the meaning through mood and light, not illustration.

Write a short, concrete design brief (about 120-160 words) covering:
- SCENE / atmosphere that fits the MEANING of this quote (be specific and evocative,
  but calm and uncluttered — a single strong idea, not a busy collage).
- PALETTE: 4-5 soft colours as hex, including one warm accent.
- 2-4 ANIMATED elements and how each moves (drift, parallax, light shift, sway…).
- TEXT reveal (how the words appear) and where they sit.
- The MOOD in one line.

Prose only, no code."""


def code_prompt(quote, accent, brief, W, H):
    return f"""Implement this animated quote-card design as a COMPLETE, self-contained Python 3
script.

DESIGN BRIEF:
{brief}

Quote to render (wrapped, centered): "{quote}"
Emphasize the word/phrase "{accent}" in the warm accent colour.

Hard constraints:
- CLI exactly: python SCRIPT OUT_MP4 WIDTH HEIGHT SECONDS   (SECONDS is a float)
- Imports ONLY: Python standard library + Pillow (PIL) + subprocess for ffmpeg.
  NO numpy, NO network, NO external asset files. Fonts: use
  /usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf and DejaVuSerif-Italic.ttf.
- Render frames in memory (PIL) and pipe raw rgb24 to ffmpeg to encode H.264,
  -pix_fmt yuv420p, 30 fps, -movflags +faststart. Silent.
- Size = WIDTH x HEIGHT. Keep it fast (<= SECONDS*30 frames).
- Animate richly per the brief (not just a zoom). The final ~4 seconds settle and
  HOLD on the fully-revealed quote.

Output ONLY the Python code. No prose, no markdown fences."""


def extract_code(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = m.group(1) if m else text
    i = re.search(r"(?m)^(#!|import |from )", code)
    return code[i.start():] if i else code


def main():
    quote, accent, out, W, H, secs = sys.argv[1:7]

    # 1) art director → brief (best-effort; empty brief still works)
    try:
        brief = claude(concept_prompt(quote, accent), timeout=180).strip()
    except Exception:
        brief = ""
    if brief:
        sys.stderr.write("· design brief:\n" + brief[:600] + "\n")

    # 2) engineer → renderer code (with one retry on failure)
    base = code_prompt(quote, accent, brief or "(no brief — design it yourself, tastefully)", W, H)
    last_err = ""
    for attempt in range(2):
        p = base if attempt == 0 else base + \
            f"\n\nThe previous attempt failed with:\n{last_err[-1500:]}\nFix it. Output ONLY code."
        try:
            code = extract_code(claude(p, timeout=600))
        except Exception as e:
            last_err = str(e); continue
        if "ffmpeg" not in code or ("PIL" not in code and "Image" not in code):
            last_err = "generated code missing PIL/ffmpeg"; continue
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code); script = f.name
        try:
            rr = subprocess.run([PY, script, out, W, H, secs],
                                capture_output=True, text=True, timeout=300)
        except Exception as e:
            last_err = f"render exception: {e}"; os.unlink(script); continue
        os.unlink(script)
        if rr.returncode != 0:
            last_err = rr.stderr or rr.stdout; continue
        try:
            d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", out], capture_output=True, text=True, timeout=30).stdout.strip()
            if d and abs(float(d) - float(secs)) <= 2.5:
                print(f"AI-designed card ok ({float(d):.1f}s)")
                sys.exit(0)
            last_err = f"bad output duration: {d}"
        except Exception as e:
            last_err = f"validate failed: {e}"
    sys.stderr.write((last_err or "unknown")[-500:] + "\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
