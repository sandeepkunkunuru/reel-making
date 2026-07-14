#!/bin/bash
# Download an audio track (for the reel's music bed) as MP3.
#
# Usage:  fetch/get_music.sh AUDIO_URL OUT.mp3
#
# Bring your own rights: use music you are licensed to use.
set -euo pipefail
URL="${1:?audio url}"; OUT="${2:?output path}"
YTDLP="${YTDLP:-yt-dlp}"
CLIENT="${YT_CLIENT:-android_vr}"
$YTDLP --no-progress --extractor-args "youtube:player_client=$CLIENT" \
  -f "bestaudio[ext=m4a]/bestaudio" -x --audio-format mp3 --audio-quality 2 \
  -o "$OUT" "$URL"
echo "· done: $OUT"
