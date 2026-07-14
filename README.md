# reel-making

A small, scriptable pipeline that turns **a spoken clip + an animated quote card +
a music bed** into a polished **9:16 vertical reel** — with word-synced karaoke
captions, an optional brand overlay, a poster thumbnail, and a cover intro so chat
apps preview the quote instead of a random frame.

Built from plain `ffmpeg`, `yt-dlp`, [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper),
and `Pillow`. No cloud services, no editor — everything is a command.

> **Videos like this can be created with this code.** For a sense of the genre, see
> this [1-minute motivational short by Motiversity](https://www.youtube.com/watch?v=fLeJJPxua3E)
> (speaker clip + captions + music). *That video is by others and not made with this
> tool — it's here only to show the style of reel you can assemble.*

## Features

- **9:16 vertical reels** from three inputs: a speaker clip, a quote card, and a music bed.
- **Word-synced karaoke captions** — forced alignment (faster-whisper) lights up each
  word in time with the *actual* speech, not an even split. Big ALL-CAPS reel style.
- **Clean voice** — no music under speech; the bed enters only on the quote card.
- **Full-bleed talking head** — auto centered 9:16 crop (or an explicit crop), with a
  light sharpen to hold up an upscaled clip.
- **Ends on the quote** — cards that clear their text are slowed only over the
  text-present window, then freeze-held, so the reel finishes on the words.
- **Motion-interpolated slow-mo** for a smooth, dreamy card drift.
- **Procedural quote-card generator** (optional) — paper + serif + accent phrase +
  attribution, brought to motion with a Ken-Burns push. Or bring your own animated card.
- **Subtitle-grep clip finder** — locate a spoken line in a long video and download
  just that slice, instead of the whole thing.
- **Brand overlay** — composite any full-frame transparent PNG (logo, campaign badge).
- **Share-ready** — a poster thumbnail plus a cover intro so chat apps preview the
  quote instead of a random frame.
- **Spec-driven** — one shell file describes a reel; one command builds it. No editor,
  no cloud, reproducible.

## What it makes

```
┌─ Segment A ──────────────┐        ┌─ Segment B ─────────────────┐
│ speaker talking-head     │  0.7s  │ animated quote card          │
│ full-bleed 9:16          │ cross- │ slowed to one held pass      │
│ clean voice, NO music    │ fade   │ music bed (fades in/out)     │
│ ALL-CAPS karaoke caption │───────▶│ ends held on the quote       │
└──────────────────────────┘        └─────────────────────────────┘
   then: brand overlay ─▶ poster thumbnail ─▶ 1s cover intro (first frame = the quote)
```

The **karaoke captions** track the speaker's *actual* word timing (forced alignment
via faster-whisper), so each word lights up in sync — not an even split.

## Three ways to use it

Pick your level — grab a single part, assemble a reel from parts you have, or hand it
a quote and walk away.

**1. Get the parts** — each stage is a standalone tool:
```bash
fetch/find_clip.sh URL "a spoken line" talk.mp4        # locate + slice a talking clip
fetch/get_music.sh  URL music.mp3                      # a music bed
python cards/gen_card.py --quote "…" --out card.png    # a quote-card image
python cards/animate_card.py card.png card.mp4         # …brought to motion
python captions/transcribe_words.py talk-16k.wav w.json && \
python captions/gen_captions.py w.json caps.ass        # word-synced karaoke .ass
```

**2. Assemble a reel from parts you already have** — describe them in a spec:
```bash
cp examples/example.spec.sh my.spec.sh                 # point at your talk / card / music
build/build_reel.sh my.spec.sh
```

**3. Make the whole reel from just a quote** — the script finds the clip and the music
and makes the card itself:
```bash
make_reel.sh "The quote you want as a reel."
# tune via env:  SPEAKER="…"  MUSIC_QUERY="…"  LOGO=logo.png  OUT=out/reel.mp4
```

### AI mode (optional)
With the [`claude` CLI](https://github.com/anthropics/claude-code) installed, set
`AI=1` and Claude reads the candidate clips' subtitles to pick the **best** clip and a
rich, self-contained passage (instead of the first phrase match) — plus the card's
accent word:
```bash
AI=1 make_reel.sh "The quote you want as a reel."
```
Without it, a subtitle phrase-grep heuristic is used.

## Pipeline

| Stage | Module | What it does |
|---|---|---|
| 1. Find & fetch | [`fetch/`](fetch/) | Search for a talking clip, grep its subtitles for a line, download just that slice at best resolution; grab a music track. |
| 2. Captions | [`captions/`](captions/) | Transcribe the cut's audio to word timings → build an ALL-CAPS karaoke `.ass`. |
| 3. Card | [`cards/`](cards/) | *(optional)* Render & animate a minimal procedural quote card if you don't supply one. |
| 4. Build | [`build/build_reel.sh`](build/build_reel.sh) | Crop/caption the talk, slow the card under music, crossfade, brand, thumbnail, cover. |
| ⭐ Drive | [`make_reel.sh`](make_reel.sh) | Quote → reel: runs all of the above; `AI=1` uses [`ai/pick.py`](ai/pick.py) to choose the clip/passage. |

## Requirements

- `ffmpeg` / `ffprobe`
- `yt-dlp` (for the `fetch/` helpers)
- Python 3.10+ with `pip install -r requirements.txt`
- A sans font for captions (default: DejaVu/Noto, configurable)
- *(optional)* the [`claude` CLI](https://github.com/anthropics/claude-code) for **AI mode**

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 1. (optional) find & slice a talking clip by a spoken line
fetch/find_clip.sh "https://www.youtube.com/watch?v=VIDEO_ID" "the line you want" work/talk.mp4
fetch/get_music.sh  "https://www.youtube.com/watch?v=MUSIC_ID" work/music.mp3

# 2. describe the reel in a spec, then build
cp examples/example.spec.sh my-reel.spec.sh   # edit paths, cut points, quote
build/build_reel.sh my-reel.spec.sh
```

The output reel, its `-thumb.jpg`, and intermediates land where the spec's `OUT`
points.

## Reel spec

A spec is a plain shell file that `build_reel.sh` sources. See
[`examples/example.spec.sh`](examples/example.spec.sh) for the annotated template.
Key fields:

| Field | Meaning |
|---|---|
| `TALK`, `TALK_SS`, `TALK_DUR` | talking-head clip and the in-point / length to cut |
| `TALK_CROP` | ffmpeg crop for full-bleed 9:16 (`auto` = centered), e.g. `406:720:267:0` |
| `CARD` | the animated quote card (a video); or set `CARD_IMAGE` to auto-animate a still |
| `CARD_WINDOW`, `CARD_PLAY`, `CARD_HOLD` | source window to slow, seconds of motion, seconds of final freeze-hold |
| `MUSIC`, `MUSIC_SS`, `MUSIC_DUR` | music bed and its in-point / length |
| `LOGO` | *(optional)* full-frame transparent PNG overlay for branding |
| `FONT`, `FONT_SIZE`, `ACCENT` | caption font, size, and the "sung" highlight color |
| `OUT` | output reel path (its basename is reused for the thumbnail) |

## Design notes

- **No music under speech** — the bed enters only on the card; speech stays clean.
- **The card ends on the quote** — many animated cards clear their text at the end,
  so the builder slows only the text-present window and freeze-holds the last frame.
- **Cover intro** — chat apps thumbnail the *first frame*; a 1s quote-card cover makes
  the shared preview show the quote.

## License

MIT — see [LICENSE](LICENSE). Bring your own clips, music, fonts, and brand assets;
this repo ships only the tooling.
