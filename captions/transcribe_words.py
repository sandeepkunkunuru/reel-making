#!/usr/bin/env python3
"""Word-level forced alignment of a speech clip, for synced karaoke captions.

Transcribes a mono 16 kHz WAV with faster-whisper and dumps each word's real
start/end time. `gen_captions.py` reads this to build karaoke that tracks the
speaker's actual pacing instead of an even split.

Usage:
    python captions/transcribe_words.py IN.wav OUT-words.json [--model small] [--lang en]

The WAV timeline must be 0-based and match the clip you will caption, e.g.:
    ffmpeg -i talk-cut.mp4 -ac 1 -ar 16000 talk-16k.wav
"""
import argparse
import json
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")   # tolerate duplicate OpenMP
os.environ.setdefault("OMP_NUM_THREADS", "4")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("out")
    ap.add_argument("--model", default="small",
                    help="faster-whisper model (tiny/base/small/medium); bump if mistimed")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--compute", default="int8")
    args = ap.parse_args()

    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type=args.compute)
    segments, _ = model.transcribe(args.wav, language=args.lang,
                                   word_timestamps=True, beam_size=5, vad_filter=False)

    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({"word": w.word.strip(),
                          "start": round(w.start, 3), "end": round(w.end, 3)})

    with open(args.out, "w") as f:
        json.dump(words, f, indent=1)

    print(f"wrote {len(words)} words -> {args.out}")
    print("  " + " ".join(w["word"] for w in words))


if __name__ == "__main__":
    main()
