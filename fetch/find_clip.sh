#!/bin/bash
# Locate a spoken line inside a video via its subtitles, then download just that
# slice — instead of fetching a whole talk. Cheap: subtitles are tiny.
#
# Usage:  fetch/find_clip.sh VIDEO_URL "the spoken line" OUT.mp4 [DUR=16] [PAD=1.5]
#
#   VIDEO_URL  any yt-dlp-supported URL
#   "line"     a distinctive phrase to grep (case-insensitive) in the subtitles
#   OUT.mp4    where to write the slice
#   DUR        seconds to keep from the line's start (default 16)
#   PAD        seconds of lead-in before the line (default 1.5)
#
# Prints the matched timestamp(s). Downloads the best <=1080p slice around the
# FIRST match. Re-run with a longer/shorter DUR once you see the transcript.
set -euo pipefail
URL="${1:?video url}"; PHRASE="${2:?phrase to find}"; OUT="${3:?output path}"
DUR="${4:-16}"; PAD="${5:-1.5}"
YTDLP="${YTDLP:-yt-dlp}"
CLIENT="${YT_CLIENT:-android_vr}"     # a client that tends to serve subs+media without tokens
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

echo "· fetching subtitles…"
$YTDLP --extractor-args "youtube:player_client=$CLIENT" --skip-download \
  --write-auto-subs --write-subs --sub-langs "en.*" --sub-format vtt \
  -o "$WORK/subs.%(ext)s" "$URL" >/dev/null 2>&1 || true

VTT="$(ls "$WORK"/subs*.vtt 2>/dev/null | head -1 || true)"
[ -n "$VTT" ] || { echo "no subtitles available for this video"; exit 2; }

# Find the cue start time of the line: track the last "HH:MM:SS.mmm -->" seen,
# emit it when a following text line matches the phrase.
START=$(awk -v IGNORECASE=1 -v p="$PHRASE" '
  /-->/ { split($1,a,":"); t=a[1]*3600+a[2]*60+a[3]; next }
  index($0,p) { printf "%.3f\n", t; exit }
' "$VTT")

if [ -z "${START:-}" ]; then
  echo "phrase not found in subtitles. Nearby lines containing the first word:"
  grep -in "${PHRASE%% *}" "$VTT" | head -8 || true
  exit 3
fi

SS=$(awk "BEGIN{s=$START-$PAD; if(s<0)s=0; printf \"%.2f\", s}")
echo "· found at ${START}s → slicing [$SS, +$DUR]s to $OUT"
$YTDLP --no-progress --extractor-args "youtube:player_client=$CLIENT" \
  -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]" \
  --download-sections "*${SS}-$(awk "BEGIN{printf \"%.2f\", $SS+$DUR}")" \
  -o "$OUT" "$URL"
echo "· done: $OUT"
