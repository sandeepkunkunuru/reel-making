#!/usr/bin/env python3
"""AI-assisted clip & accent selection — OPTIONAL, uses the `claude` CLI.

Heuristics grep the first place a phrase appears; that often lands on a short or
sparse passage. With a quote and candidate video IDs, this reads each candidate's
subtitles and asks Claude to pick the single best clip and a tight, self-contained
~12–15 s passage of clear continuous speech — plus an accent word for the card.

    ai/pick.py "QUOTE" VIDEO_ID [VIDEO_ID ...]
    -> prints one TSV line:  VIDEO_ID <TAB> START <TAB> DUR <TAB> ACCENT

Non-zero exit if nothing usable is produced (caller falls back to heuristics).
Env: CLAUDE_BIN (default claude), YTDLP, YT_CLIENT.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

YTDLP = os.environ.get("YTDLP", "yt-dlp")
CLIENT = os.environ.get("YT_CLIENT", "android_vr")
CLAUDE = os.environ.get("CLAUDE_BIN", "claude")


def get_subs(vid, d):
    subprocess.run(
        [YTDLP, "--extractor-args", f"youtube:player_client={CLIENT}", "--skip-download",
         "--write-auto-subs", "--write-subs", "--sub-langs", "en.*", "--sub-format", "vtt",
         "-o", os.path.join(d, f"{vid}.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    files = sorted(glob.glob(os.path.join(d, f"{vid}*.vtt")))
    if not files:
        return None
    lines, t, last = [], None, ""
    for ln in open(files[0], errors="ignore"):
        ln = ln.strip()
        m = re.match(r"(\d\d):(\d\d):(\d\d)\.\d+ -->", ln)
        if m:
            t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
            continue
        if not ln or ln.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", ln)).strip()
        if txt and txt != last and t is not None:
            lines.append((t, txt))
            last = txt
    return lines


def transcript(lines, cap=110):
    return "\n".join(f"[{t}s] {txt}" for t, txt in lines[:cap])


def main():
    quote, ids = sys.argv[1], sys.argv[2:]
    with tempfile.TemporaryDirectory() as d:
        blocks = []
        for vid in ids:
            L = get_subs(vid, d)
            if L:
                blocks.append(f"### VIDEO {vid}\n{transcript(L)}")
        if not blocks:
            sys.exit(1)
        prompt = (
            "You are selecting footage for a short vertical quote reel.\n\n"
            f'QUOTE (shown on the end card): "{quote}"\n\n'
            "Below are candidate videos with timestamped subtitles ([SECONDSs] text). "
            "Choose the ONE clip and a single CONTINUOUS passage (about 12-15 seconds) "
            "where the speaker best expresses this theme in clear, unbroken speech — "
            "avoid intros, sponsor/branding lines, long pauses, and stretches that are "
            "mostly silence or music.\n\n"
            "Also choose an animated-card MOTIF whose mood best fits the quote, from "
            "exactly: petals, leaves, blossom, embers, stars, dust.\n\n"
            "Return ONLY a JSON object, no prose:\n"
            '{"video_id":"<id>","start":<seconds>,"dur":<seconds 12-15>,'
            '"accent":"<one word from the quote to highlight on the card>",'
            '"motif":"<petals|leaves|blossom|embers|stars|dust>"}\n\n'
            "Candidates:\n" + "\n\n".join(blocks) + "\n"
        )
        try:
            r = subprocess.run([CLAUDE, "-p", prompt], capture_output=True, text=True, timeout=180)
        except Exception:
            sys.exit(2)
        m = re.search(r"\{.*\}", r.stdout, re.S)
        if not m:
            sys.exit(3)
        try:
            j = json.loads(m.group(0))
        except Exception:
            sys.exit(4)
        vid, st, du = j.get("video_id"), j.get("start"), j.get("dur")
        ac, mo = j.get("accent", ""), j.get("motif", "")
        if not vid or st is None or not du:
            sys.exit(5)
        print(f"{vid}\t{float(st):.2f}\t{float(du):.2f}\t{ac}\t{mo}")


if __name__ == "__main__":
    main()
