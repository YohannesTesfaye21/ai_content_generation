# The Third Cup — an AI heritage short, made by a pipeline

An ~88-second short film in **Amharic** with English subtitles, generated from one file,
[`storyboard.json`](storyboard.json), by a five-stage pipeline: script → narration → keyframes →
moving shots → music → assembly. Every model call is logged in [`runs.jsonl`](runs.jsonl).

> A grandchild remembers how their grandmother's slow coffee ceremony held a scattered family
> together, one cup at a time.

## Run it

Requirements: macOS or Linux, Python 3.10+, FFmpeg on your PATH.

```bash
git clone https://github.com/YohannesTesfaye21/ai_content_generation.git
cd ai_content_generation
cp .env.example .env        # then fill in the three keys (see below)
make film                   # validates the storyboard, runs every stage, writes the film
```

Output:

| File | What it is |
|---|---|
| `outputs/film/the_film_9x16.mp4` | vertical film (phones) |
| `outputs/film/the_film_16x9.mp4` | horizontal film |
| `outputs/film/subtitles_en.srt` | English subtitles (also burned in) |
| `outputs/film/radio_cut.mp4` | narration + music over black, for the first user test (`make radio`) |

Because generated keyframes and narration are committed with their input hashes, a fresh clone
re-runs `make film` **without any API calls**: only the local FFmpeg stages execute. Change a line
in `storyboard.json` and only that shot's model call runs again.

### Keys (all free, no payment card)

| Variable | Where to get it |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | dash.cloudflare.com → AI → Workers AI → *REST API* (token with Workers AI permission) |
| `GEMINI_API_KEY` | aistudio.google.com/apikey |

`.env` is git-ignored. Never commit keys.

## Regenerate one shot

```bash
# edit s03's image_prompt or narration in storyboard.json, then:
make shot S=s03     # keyframe + narration + clip for s03 only (others are cache hits)
make assemble       # re-cut the film
tail -n 3 runs.jsonl   # shows the single new model call
```

## Stages

| Make target | Script | Model / tool | Runs on |
|---|---|---|---|
| `validate` | `pipeline/validate.py` | JSON Schema | local |
| `script` | `pipeline/script.py` | Gemini 3.8 Flash (English → Amharic draft) | Gemini API |
| `narration` | `pipeline/narration.py` | Gemini 3.8 Flash Lite TTS, fallback Flash TTS | Gemini API |
| `keyframes` | `pipeline/keyframes.py` | FLUX.2 klein 4B + character reference image | Cloudflare Workers AI |
| `shots` | `pipeline/shots.py` | Ken Burns in FFmpeg, or Wan 2.2 clips from `kaggle/wan_i2v.py` | local / Kaggle |
| `music` | `pipeline/music.py` | ACE-Step 1.5 via `kaggle/ace_step.py`, or synthesised placeholder | Kaggle / local |
| `assemble` | `pipeline/assemble.py` | FFmpeg: ducking, two-pass loudnorm −14 LUFS, subtitles, end card | local |
| `costs` | `pipeline/costs.py` | summarises `runs.jsonl` | local |

## What it costs

$0 on free tiers. Measured: ~7 minutes of model latency for the whole film, list-price equivalent
about $0.05 (see [COSTS.md](COSTS.md)). The binding constraint was the Gemini TTS free quota
(10 requests/day per model), not money.

## Documents

- [DESIGN.md](DESIGN.md) — audience, intent, shot reasons, user tests
- [ARCHITECTURE.md](ARCHITECTURE.md) — stages, the storyboard contract, caching, failure handling
- [EXPERIMENTS.md](EXPERIMENTS.md) — hypothesis → change → result
- [FAILURES.md](FAILURES.md) — what broke and what fixed it
- [COSTS.md](COSTS.md) — latency, quotas, list-price equivalents
- [ETHICS.md](ETHICS.md) — consent, licences, AI labelling
