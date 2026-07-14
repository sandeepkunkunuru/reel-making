#!/bin/bash
# Download just a time slice of a video at best <=1080p.
#   Usage:  fetch/slice.sh VIDEO_URL START DUR OUT.mp4
set -euo pipefail
URL="${1:?url}"; START="${2:?start s}"; DUR="${3:?dur s}"; OUT="${4:?out}"
YTDLP="${YTDLP:-yt-dlp}"; CLIENT="${YT_CLIENT:-android_vr}"
END=$(awk "BEGIN{printf \"%.2f\", $START+$DUR}")
$YTDLP --no-progress --force-overwrites --extractor-args "youtube:player_client=$CLIENT" \
  -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]" \
  --download-sections "*${START}-${END}" -o "$OUT" "$URL"
