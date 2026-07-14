#!/bin/bash
# Build a 9:16 quote reel from a spec: talking-head + animated card + music.
#
#   Usage:  build/build_reel.sh my-reel.spec.sh
#
# See examples/example.spec.sh for the annotated field list. The pipeline:
#   A) cut + full-bleed-crop the talk, clean voice, burn word-synced karaoke
#   B) slow the card to one held pass under a music bed (ends on the quote)
#   C) crossfade A -> B (+ brand overlay in the same pass), thumbnail, cover intro
#
# Quality: the talk is low-res upscaled to 1080p, so we minimise re-encodes
# (single-pass A; join+logo in one pass), scale with lanczos, and keep
# near-transparent intermediates (CRF 15) with a CRF 17 final.
set -euo pipefail

SPEC="${1:?path to a reel spec (see examples/example.spec.sh)}"
# shellcheck disable=SC1090
source "$SPEC"

# ---- defaults ----
FF="${FF:-ffmpeg} -hide_banner -y -loglevel error"
FP="${FP:-ffprobe}"
PY="${PY:-python3}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
W="${WORKDIR:-work}"; mkdir -p "$W"

TALK_CROP="${TALK_CROP:-auto}"
CARD_WINDOW="${CARD_WINDOW:-}"          # empty = use whole card
CARD_PLAY="${CARD_PLAY:-13}"
CARD_HOLD="${CARD_HOLD:-5}"
MUSIC_SS="${MUSIC_SS:-0}"
FONT="${FONT:-/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf}"
FONT_NAME="${FONT_NAME:-Noto Sans}"
FONT_SIZE="${FONT_SIZE:-92}"
ACCENT="${ACCENT:-2FB6F2}"              # sung colour, ASS BGR hex
FONTSDIR="${FONTSDIR:-$(dirname "$FONT")}"
XF="${XF:-0.7}"
COVER="${COVER:-1.2}"                   # cover-intro seconds (0 = none)
X264I="-c:v libx264 -crf 15 -preset slow -pix_fmt yuv420p"   # near-transparent intermediate
X264F="-c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p"   # final
AAC="-c:a aac -b:a 192k"
base="${OUT%.mp4}"; thumb="${base}-thumb.jpg"

# ---- Segment A: full-bleed talk, CLEAN VOICE + karaoke captions (ONE pass) ----
if [ "$TALK_CROP" = "auto" ]; then
  FC="$($PY "$HERE/util/face_crop.py" "$TALK" --ss "$TALK_SS" --dur "$TALK_DUR" 2>/dev/null || true)"
  if [ -n "$FC" ]; then CROP="crop=$FC"; echo "· face-aware crop: $FC"
  else CROP="crop='2*trunc(ih*9/16/2)':ih:'(iw-ih*9/16)/2':0"; echo "· no face detected — centered crop"; fi
else
  CROP="crop=$TALK_CROP"
fi
# Transcribe the raw cut's audio first (0-based → matches the burned captions),
# so crop+scale+captions can be a single encode of the upscaled talk.
$FF -ss "$TALK_SS" -t "$TALK_DUR" -i "$TALK" -vn -ac 1 -ar 16000 "$W/talk-16k.wav"
$PY "$HERE/captions/transcribe_words.py" "$W/talk-16k.wav" "$W/talk-words.json" --model "${WHISPER_MODEL:-small}"
$PY "$HERE/captions/gen_captions.py" "$W/talk-words.json" "$W/captions.ass" \
    --font-file "$FONT" --font-name "$FONT_NAME" --font-size "$FONT_SIZE" --sung "$ACCENT"
# Deterministic anti-cutoff: trim the talk to the last COMPLETE sentence (else last
# clause, else last whole word) so speech never ends mid-phrase.
TALK_DUR=$($PY - "$W/talk-words.json" "$TALK_DUR" <<'PY'
import json, sys
words = json.load(open(sys.argv[1])); cut = float(sys.argv[2])
if not words: print(f"{cut:.2f}"); sys.exit()
end_of = lambda cs: [w['end'] for w in words if w['end'] <= cut and w['word'].strip()[-1:] in cs]
sent, clause = end_of('.!?'), end_of('.!?,;:')
last = min(words[-1]['end'], cut)
if sent and sent[-1] >= 0.5 * cut:   eff = sent[-1] + 0.40
elif clause and clause[-1] >= 0.6 * cut: eff = clause[-1] + 0.35
else: eff = last + 0.30
print(f"{min(eff, cut):.2f}")
PY
)
echo "· talk trimmed to last full sentence: ${TALK_DUR}s"
AF_OUT=$(awk "BEGIN{printf \"%.2f\", $TALK_DUR-0.5}")
$FF -ss "$TALK_SS" -t "$TALK_DUR" -i "$TALK" -filter_complex "
  [0:v]${CROP},scale=1080:1920:flags=lanczos,unsharp=5:5:0.5:5:5:0.0,subtitles=$W/captions.ass:fontsdir=$FONTSDIR,setsar=1,fps=30,format=yuv420p[v];
  [0:a]afade=t=out:st=${AF_OUT}:d=0.55,aformat=sample_rates=48000:channel_layouts=stereo[a]
" -map "[v]" -map "[a]" $X264I $AAC -movflags +faststart "$W/segA.mp4"
echo "· Segment A built (single-pass crop+captions)"

# ---- Segment B: card slowed to one held pass, under the music bed ----
if [ "${REUSE_SEGB:-0}" = "1" ] && [ -f "$W/segB.mp4" ]; then
  echo "· reusing existing segB.mp4"
else
  SMOOTH="${CARD_SMOOTH:-0}"   # 1 = card is already a finished, full-length animation
  if [ -z "${CARD:-}" ] && [ -n "${CARD_IMAGE:-}" ]; then
    $PY "$HERE/cards/animate_card.py" "$CARD_IMAGE" "$W/card.mp4" \
        --seconds "$((CARD_PLAY+CARD_HOLD))" --motif "${CARD_MOTIF:-petals}"
    CARD="$W/card.mp4"; CARD_WINDOW=""; CARD_PLAY=$((CARD_PLAY+CARD_HOLD)); CARD_HOLD=0
    SMOOTH=1
  fi
  BDUR=$((CARD_PLAY + CARD_HOLD))
  if [ -n "$CARD_WINDOW" ]; then WIN=(-t "$CARD_WINDOW"); SRC="$CARD_WINDOW"; else \
     SRC=$($FP -v error -show_entries format=duration -of csv=p=0 "$CARD"); WIN=(); fi
  FACTOR=$(awk "BEGIN{printf \"%.4f\", $CARD_PLAY/$SRC}")
  HOLD_F=""
  [ "$CARD_HOLD" -gt 0 ] && HOLD_F=",tpad=stop_mode=clone:stop_duration=$CARD_HOLD"
  if [ "${SMOOTH:-0}" = "1" ]; then
    VCHAIN="[0:v]fps=30,scale=1080:1920:flags=lanczos,setsar=1${HOLD_F},format=yuv420p[v]"
  else
    VCHAIN="[0:v]minterpolate=fps=120:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,setpts=$FACTOR*PTS,fps=30,scale=1080:1920:flags=lanczos,setsar=1${HOLD_F},format=yuv420p[v]"
  fi
  $FF "${WIN[@]}" -i "$CARD" -ss "$MUSIC_SS" -t "$BDUR" -i "$MUSIC" -filter_complex "
    $VCHAIN;
    [1:a]afade=t=in:st=0:d=1.8,afade=t=out:st=$(awk "BEGIN{print $BDUR-2.0}"):d=2.0,loudnorm=I=-16:TP=-1.5:LRA=11,aformat=sample_rates=48000:channel_layouts=stereo[a]
  " -map "[v]" -map "[a]" -t "$BDUR" $X264I $AAC -movflags +faststart "$W/segB.mp4"
  echo "· Segment B built (slowed card + held ending + music)"
fi

# ---- Join (talk -> card) + brand overlay in ONE pass ----
SEGA_DUR=$($FP -v error -show_entries format=duration -of csv=p=0 "$W/segA.mp4")
OFF=$(awk "BEGIN{printf \"%.3f\", $SEGA_DUR - $XF}")
if [ -n "${LOGO:-}" ]; then
  $FF -i "$W/segA.mp4" -i "$W/segB.mp4" -i "$LOGO" -filter_complex "
    [0:v][1:v]xfade=transition=fade:duration=$XF:offset=$OFF[xf];
    [xf][2:v]overlay=0:0:format=auto,format=yuv420p[v];
    [0:a][1:a]acrossfade=d=$XF[a]
  " -map "[v]" -map "[a]" $X264I $AAC -movflags +faststart "$W/joined.mp4"
else
  $FF -i "$W/segA.mp4" -i "$W/segB.mp4" -filter_complex "
    [0:v][1:v]xfade=transition=fade:duration=$XF:offset=$OFF,format=yuv420p[v];
    [0:a][1:a]acrossfade=d=$XF[a]
  " -map "[v]" -map "[a]" $X264I $AAC -movflags +faststart "$W/joined.mp4"
fi
SRC_V="$W/joined.mp4"

# ---- Poster thumbnail (a held quote frame near the end) ----
DUR_SRC=$($FP -v error -show_entries format=duration -of csv=p=0 "$SRC_V")
THUMB_AT="${THUMB_AT:-$(awk "BEGIN{printf \"%.2f\", $DUR_SRC - 1.0}")}"
$FF -ss "$THUMB_AT" -i "$SRC_V" -frames:v 1 -q:v 2 "$thumb"
echo "· thumbnail: $thumb"

# ---- Cover intro so chat apps preview the quote (first frame = the card) ----
if [ "$(awk "BEGIN{print ($COVER>0)}")" = "1" ]; then
  $FF -loop 1 -t "$COVER" -i "$thumb" -i "$SRC_V" -filter_complex "
    [0:v]scale=1080:1920:flags=lanczos,setsar=1,fps=30,format=yuv420p[cov];
    [1:v]setsar=1,fps=30,format=yuv420p[rv];
    [cov][rv]xfade=transition=fade:duration=0.4:offset=$(awk "BEGIN{print $COVER-0.4}"),format=yuv420p[v];
    anullsrc=r=48000:cl=stereo:d=$COVER[sil];
    [sil][1:a]acrossfade=d=0.4[a]
  " -map "[v]" -map "[a]" $X264F $AAC -movflags +faststart "$OUT"
else
  $FF -i "$SRC_V" $X264F $AAC -movflags +faststart "$OUT"
fi

echo "· done: $OUT"
$FP -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT"
