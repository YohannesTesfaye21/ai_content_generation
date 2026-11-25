# Architecture

## Shape

```
                       schema/storyboard.schema.json
                                   │ validated before every stage
                                   ▼
                           storyboard.json  ◄──── script.py fills missing translations only
         ┌──────────────┬──────────┴───────┬───────────────┐
         ▼              ▼                  ▼               ▼
   narration.py    keyframes.py         music.py      (timing block)
   Gemini TTS      FLUX.2 klein         ACE-Step /
   per shot        + reference.jpg      placeholder
         │              │                  │
         │ durations    ▼                  │
         └────────► shots.py               │
                    Ken Burns or Wan 2.2   │
                    16:9 + 9:16            │
                         │                 │
                         ▼                 ▼
                       assemble.py  (FFmpeg, deterministic)
                       voice track → duck music → loudnorm → subtitles → end card
                         │
                         ▼
             outputs/film/the_film_{16x9,9x16}.mp4 + subtitles_en.srt
```

Every model call appends one line to `runs.jsonl`: timestamp, stage, shot, model, provider,
parameters (including the full prompt), seed, latency, status, attempt, cost equivalent.
Failed attempts are logged too (`status: retryable_error`, `daily_quota`, `no_audio`).

## The contract: `storyboard.json`

One file holds every creative decision, so a run is reproducible and explainable:

| Field | Used by |
|---|---|
| `style_block`, `character.description`, `image_model` | keyframes |
| `shots[].image_prompt`, `seed`, `with_character`, `shot_size` | keyframes |
| `shots[].narration` (Amharic), `voice.*` | narration |
| `shots[].narration_en` | subtitles (assemble) |
| `shots[].duration`, `camera`, `motion_prompt` | shots (Ken Burns / Wan) |
| `music.*` | music |
| `timing.*` | shots, assemble |
| `shots[].reason` | humans: reviewers, the interview, DESIGN.md |

Prompts and seeds live in the storyboard, not in code. Only `script.py` writes to it, and only
to fill empty `narration` fields (it reloads the file before saving, see FAILURES.md F8).

## Timing: narration drives the cut

A shot's final length is `max(storyboard duration, lead + narration length + padding)`
(`common.shot_durations`). Like a professional editor cutting picture to the voice track, the
measured TTS output sets the pace; storyboard durations are minimums.

## Caching

Each output file has a sibling `.hash` file containing a hash of exactly the inputs that
produced it:

| Output | Hash inputs |
|---|---|
| `outputs/narration/sNN.wav` | voice name, style, speed, Amharic line |
| `outputs/keyframes/sNN.jpg` | model, size, full prompt, seed, sha256 of the reference image |
| `outputs/shots/<aspect>/sNN.mp4` | source file (keyframe or Wan clip) size+mtime, duration, camera, aspect |
| `outputs/music/score.wav` | source (placeholder length, or ACE-Step file) |

A stage skips any output whose stored hash matches. Consequences:

- Editing one shot's `image_prompt` regenerates one keyframe and its two clips — one API call.
- Regenerating `reference.jpg` invalidates every shot that uses it (the reference's bytes are
  in the hash), which is exactly right.
- The narration hash ignores which fallback model answered, so a quota fallback does not
  re-voice lines that already exist.
- Assembly is not cached: it is local, deterministic and takes ~35 s.

## Failure handling

- **Retries:** `common.with_retries` retries HTTP 429/5xx and network errors with exponential
  backoff (narration: 4 attempts from 20 s, because the free tier allows 3 TTS requests/minute).
- **Quota fallback:** a daily-quota 429 is not retried (it would not succeed for hours);
  narration moves to the next model in `voice.fallback_models` and marks the exhausted one.
- **Visual fallback:** if no Wan 2.2 clip exists for a shot, it gets a Ken Burns move from its
  `camera` field, so the film always renders.
- **Music fallback:** `music.source: placeholder` synthesises a drone pad in FFmpeg until an
  ACE-Step track is chosen.
- **Validation first:** schema errors stop the run before any paid-tier-equivalent call.
- **Fail loudly:** FFmpeg errors print the tail of stderr and exit non-zero, so `make` stops.

## Text in code, not in pictures

Generated images never contain text (`style_block` says "no text"). Subtitles and the end card
are drawn with Pillow (this FFmpeg build has no `drawtext`/`libass`) and overlaid with FFmpeg's
`overlay` filter, timed per subtitle card. Subtitles are split at clause boundaries into cards of
at most 2 × 40 characters and placed inside the vertical safe area.

## Audio chain

1. Each narration WAV is resampled to 48 kHz, delayed by `narration_lead_s`, padded to its
   shot's length, and concatenated into one voice track.
2. Voice is levelled to −16 LUFS, music to −24 LUFS (so balance decisions are creative, not repairs).
3. Music is ducked with `sidechaincompress` (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms).
4. The mix is normalised with a **two-pass** `loudnorm` to −14 LUFS integrated, −1 dBTP.
   Measured result: −14.0 LUFS, peak −2.2 dBFS.

## Wan 2.2 and ACE-Step (Kaggle)

Both need a GPU, so they run in Kaggle notebooks (`kaggle/`) that read the same
`storyboard.json` and keyframes. Their outputs are dropped into `outputs/wan/sNN.mp4` and
`outputs/music/`, and the local stages pick them up automatically (hash changes → re-cut).
