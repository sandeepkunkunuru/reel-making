# Example reel spec — copy this, edit, then: build/build_reel.sh my-reel.spec.sh
# A spec is just shell variables that build_reel.sh sources.

# ── Segment A: the talking-head clip ─────────────────────────────────────────
# Any local video of a person speaking. Use fetch/find_clip.sh to pull a slice
# from a URL by a spoken line, e.g.:
#   fetch/find_clip.sh "https://youtu.be/VIDEO_ID" "you have power over your mind" work/talk.mp4
TALK="work/talk.mp4"
TALK_SS=0            # in-point (seconds) within TALK
TALK_DUR=13.5        # how many seconds of talk to use
TALK_CROP=auto       # "auto" = centered 9:16, or an ffmpeg crop like 406:720:267:0

# ── Segment B: the animated quote card ───────────────────────────────────────
# EITHER supply a finished animated card video:
#   CARD="work/card.mp4"
#   CARD_WINDOW=2.2   # only slow this leading window (where the quote is on screen)
# OR let the builder render + animate a minimal card from text. Generate the
# still first (or point CARD_IMAGE at any 9:16 art with room for the words):
#   python cards/gen_card.py \
#     --quote "You have power over your mind — not outside events. Realize this, and you will find strength." \
#     --accent "strength" --attrib "— Marcus Aurelius" --out work/card.png
CARD_IMAGE="work/card.png"
CARD_PLAY=13         # seconds of slowed motion
CARD_HOLD=5          # seconds of freeze-hold on the final (quote) frame

# ── Music bed (plays only on the card, never under speech) ───────────────────
# fetch/get_music.sh "https://youtu.be/MUSIC_ID" work/music.mp3   (use licensed music)
MUSIC="work/music.mp3"
MUSIC_SS=0           # in-point into the music
# MUSIC_DUR=18       # defaults to the card segment length

# ── Captions (word-synced ALL-CAPS karaoke over the talk) ────────────────────
FONT="/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
FONT_NAME="Noto Sans"
FONT_SIZE=92
ACCENT="2FB6F2"      # "sung" highlight colour, ASS BGR hex (gold)
# WHISPER_MODEL=small

# ── Branding (optional) ──────────────────────────────────────────────────────
# A full-frame 1080x1920 transparent PNG overlaid on every frame.
# LOGO="assets/logo-overlay.png"

# ── Output ───────────────────────────────────────────────────────────────────
OUT="out/example-reel.mp4"     # thumbnail written alongside as example-reel-thumb.jpg
# COVER=1.2          # cover-intro seconds so chat apps preview the quote (0 = off)
