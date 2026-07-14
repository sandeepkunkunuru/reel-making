# reel-making

A small, scriptable pipeline that turns **a spoken clip + an animated quote card +
a music bed** into a polished **9:16 vertical reel** — with word-synced karaoke
captions, an optional brand overlay, a poster thumbnail, and a cover intro so chat
apps preview the quote instead of a random frame.

Built from plain `ffmpeg`, `yt-dlp`, [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper),
and `Pillow`. No cloud services, no editor — everything is a command.

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

## Pipeline

| Stage | Module | What it does |
|---|---|---|
| 1. Find & fetch | [`fetch/`](fetch/) | Search for a talking clip, grep its subtitles for a line, download just that slice at best resolution; grab a music track. |
| 2. Captions | [`captions/`](captions/) | Transcribe the cut's audio to word timings → build an ALL-CAPS karaoke `.ass`. |
| 3. Card | [`cards/`](cards/) | *(optional)* Render & animate a minimal procedural quote card if you don't supply one. |
| 4. Build | [`build/build_reel.sh`](build/build_reel.sh) | Crop/caption the talk, slow the card under music, crossfade, brand, thumbnail, cover. |

## Requirements

- `ffmpeg` / `ffprobe`
- `yt-dlp` (for the `fetch/` helpers)
- Python 3.10+ with `pip install -r requirements.txt`
- A sans font for captions (default: DejaVu/Noto, configurable)

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
