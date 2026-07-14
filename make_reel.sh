#!/bin/bash
# make_reel.sh — fully automated: a QUOTE goes in, a finished reel comes out.
# The script finds a talking clip, finds a music bed, generates a card, and builds.
#
#   make_reel.sh "the quote text"
#
# Nothing is pre-selected by hand. Tune behaviour with env vars:
#   SPEAKER       search hint for the talking clip (e.g. "Sadhguru"); default: none
#   MUSIC_QUERY   search for the music bed (default: "calm instrumental meditation music")
#   LOGO          full-frame transparent PNG brand overlay (optional)
#   ACCENT_WORD   quote word to colour on the card (default: the longest word)
#   OUT           output reel path (default: out/<slug>.mp4)
#   WORKDIR       scratch dir (default: work/<slug>)
#   TALK_DUR CARD_PLAY CARD_HOLD FONT ...  (passed through to build_reel.sh)
set -euo pipefail

QUOTE="${1:?quote text}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-python3}"
YTDLP="${YTDLP:-yt-dlp}"
CLIENT="${YT_CLIENT:-android_vr}"
SPEAKER="${SPEAKER:-}"
MUSIC_QUERY="${MUSIC_QUERY:-calm instrumental meditation music}"
TALK_DUR="${TALK_DUR:-13.5}"

slug() { echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/-/g; s/^-//; s/-$//' | cut -c1-40; }
SLUG="$(slug "$QUOTE")"
WORK="${WORKDIR:-work/$SLUG}"; mkdir -p "$WORK"
OUT="${OUT:-out/$SLUG.mp4}"; mkdir -p "$(dirname "$OUT")"

log(){ echo "▸ $*"; }

# ── 1. Find & slice a talking clip ───────────────────────────────────────────
# Search "<speaker> <quote>", then for each candidate try to grep a distinctive
# 3-word window of the quote in its subtitles and slice around the first hit.
PHRASE="$($PY -c "import sys,re; w=re.sub(r'[^a-z0-9 ]',' ',sys.argv[1].lower()).split(); k=min(3,len(w)); \
best=max((w[i:i+k] for i in range(max(1,len(w)-k+1))), key=lambda s:sum(map(len,s))) if w else []; \
print(' '.join(best))" "$QUOTE")"
log "clip search phrase: \"$PHRASE\""

mapfile -t CANDS < <($YTDLP --extractor-args "youtube:player_client=$CLIENT" \
  "ytsearch8:${SPEAKER} ${QUOTE}" --flat-playlist --print "%(id)s" 2>/dev/null)
[ "${#CANDS[@]}" -gt 0 ] || { echo "no clip candidates found"; exit 1; }

TALK=""
# AI mode (optional): let Claude read the candidates' subtitles and pick the best
# clip + a rich, self-contained passage — better than "first phrase match".
if [ "${AI:-0}" = "1" ] && command -v "${CLAUDE_BIN:-claude}" >/dev/null 2>&1; then
  log "AI mode: asking Claude to choose the best clip & passage…"
  DEC="$($PY "$HERE/ai/pick.py" "$QUOTE" "${CANDS[@]:0:6}" 2>/dev/null || true)"
  if [ -n "$DEC" ]; then
    AID=$(printf '%s' "$DEC" | cut -f1); AST=$(printf '%s' "$DEC" | cut -f2)
    ADU=$(printf '%s' "$DEC" | cut -f3); AAC=$(printf '%s' "$DEC" | cut -f4)
    AMO=$(printf '%s' "$DEC" | cut -f5)
    log "AI picked $AID @ ${AST}s for ${ADU}s (accent: ${AAC:-—}, motif: ${AMO:-—})"
    if bash "$HERE/fetch/slice.sh" "https://www.youtube.com/watch?v=$AID" "$AST" "$ADU" "$WORK/talk.mp4" >/dev/null 2>&1; then
      TALK="$WORK/talk.mp4"; TALK_DUR="$ADU"; [ -n "$AAC" ] && ACCENT_WORD="$AAC"
      [ -n "$AMO" ] && CARD_MOTIF="$AMO"
    fi
  fi
  [ -n "$TALK" ] || log "AI mode: no usable pick — falling back to phrase-grep"
fi

# Heuristic fallback: grep a distinctive phrase in each candidate's subtitles.
if [ -z "$TALK" ]; then
  for id in "${CANDS[@]}"; do
    log "trying candidate $id …"
    if bash "$HERE/fetch/find_clip.sh" "https://www.youtube.com/watch?v=$id" "$PHRASE" \
          "$WORK/talk.mp4" "$TALK_DUR" 1.5 >/dev/null 2>&1; then
      TALK="$WORK/talk.mp4"; log "matched in $id"; break
    fi
  done
fi
[ -n "$TALK" ] || { echo "no usable clip found in any candidate"; exit 2; }

# ── 2. Find & fetch a music bed, pick a fuller section ───────────────────────
# Pull several candidates and pick one at random, so the bed varies run to run
# (ytsearch1 always returns the same top hit → same audio every time).
mapfile -t MIDS < <($YTDLP --extractor-args "youtube:player_client=$CLIENT" \
  "ytsearch12:${MUSIC_QUERY}" --flat-playlist --print "%(id)s" 2>/dev/null)
[ "${#MIDS[@]}" -gt 0 ] || { echo "no music found"; exit 3; }
MID="${MIDS[$((RANDOM % ${#MIDS[@]}))]}"
log "music: $MID (random of ${#MIDS[@]} candidates)"
bash "$HERE/fetch/get_music.sh" "https://www.youtube.com/watch?v=$MID" "$WORK/music.mp3" >/dev/null 2>&1
# pick the loudest of a few 18s windows (avoids a bare intro)
BEST_SS=60; BEST_DB=-99
for off in 30 60 120 180 300; do
  db=$(ffmpeg -hide_banner -nostats -ss $off -t 18 -i "$WORK/music.mp3" -af volumedetect -f null - 2>&1 \
        | sed -n 's/.*mean_volume: \(-*[0-9.]*\) dB/\1/p'); [ -z "$db" ] && continue
  awk "BEGIN{exit !($db>$BEST_DB)}" && { BEST_DB=$db; BEST_SS=$off; }
done
log "music in-point: ${BEST_SS}s (${BEST_DB} dB)"

# ── 3. Make the quote card (art) ─────────────────────────────────────────────
ACCENT_WORD="${ACCENT_WORD:-$($PY -c "import sys,re; w=[x for x in re.sub(r'[^A-Za-z0-9 ]',' ',sys.argv[1]).split()]; print(max(w,key=len) if w else '')" "$QUOTE")}"
BSECS=$(( ${CARD_PLAY:-13} + ${CARD_HOLD:-5} ))
CARD_LINE=""
# Full-AI design: Claude art-directs + renders a bespoke animated card for the quote.
if [ "${AI:-0}" = "1" ] && [ "${DESIGN:-1}" = "1" ] && command -v "${CLAUDE_BIN:-claude}" >/dev/null 2>&1; then
  log "AI design: Claude art-directing + rendering the card…"
  if $PY "$HERE/ai/design_card.py" "$QUOTE" "$ACCENT_WORD" "$WORK/card.mp4" 1080 1920 "$BSECS" 2>"$WORK/design.err"; then
    CARD_LINE="CARD=\"$WORK/card.mp4\"; CARD_SMOOTH=1; CARD_PLAY=$BSECS; CARD_HOLD=0"
    log "AI-designed card ready"
  else
    log "AI design failed ($(tail -1 "$WORK/design.err" 2>/dev/null)) — using procedural card"
  fi
fi
if [ -z "$CARD_LINE" ]; then
  $PY "$HERE/cards/gen_card.py" --quote "$QUOTE" --accent "$ACCENT_WORD" --out "$WORK/card.png" >/dev/null
  CARD_LINE="CARD_IMAGE=\"$WORK/card.png\"; CARD_PLAY=${CARD_PLAY:-13}; CARD_HOLD=${CARD_HOLD:-5}; CARD_MOTIF=\"${CARD_MOTIF:-petals}\""
  log "card art: procedural (accent: $ACCENT_WORD, motif: ${CARD_MOTIF:-petals})"
fi

# ── 4. Build the reel from a generated spec ──────────────────────────────────
SPEC="$WORK/reel.spec.sh"
cat > "$SPEC" <<EOF
TALK="$TALK"; TALK_SS=0; TALK_DUR=$TALK_DUR; TALK_CROP=auto
CARD_IMAGE="$WORK/card.png"; CARD_PLAY=${CARD_PLAY:-13}; CARD_HOLD=${CARD_HOLD:-5}
CARD_MOTIF="${CARD_MOTIF:-petals}"
MUSIC="$WORK/music.mp3"; MUSIC_SS=$BEST_SS
FONT="${FONT:-/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf}"
FONT_NAME="${FONT_NAME:-Noto Sans}"; FONT_SIZE=${FONT_SIZE:-92}; ACCENT="${ACCENT:-2FB6F2}"
$( [ -n "${LOGO:-}" ] && echo "LOGO=\"$LOGO\"" )
COVER=${COVER:-1.2}
OUT="$OUT"
WORKDIR="$WORK/build"
EOF
log "building reel → $OUT"
bash "$HERE/build/build_reel.sh" "$SPEC"
log "done: $OUT"
