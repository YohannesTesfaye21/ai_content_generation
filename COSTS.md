# Costs and measurements

All numbers are measured from `runs.jsonl` (`make costs` regenerates the table) and from timing
the local stages on an Apple M2 Pro. Actual spend: **$0**.

## Model calls (whole project so far, including failed experiments)

| Stage | Model | OK calls | Failed | Mean latency (s) | Max latency (s) | Total (s) | List-price equiv. (USD) |
|---|---|---|---|---|---|---|---|
| keyframes | `@cf/black-forest-labs/flux-2-klein-4b` | 35 | 0 | 9.8 | 13.5 | 342 | 0.0525 |
| narration | `gemini-3.8-flash-lite-tts` | 9 | 0 | 4.7 | 5.3 | 43 | 0.0090 |
| narration | `gemini-3.8-flash-tts` | 9 | 0 | 7.6 | 8.4 | 68 | 0.0180 |
| script | `gemini-3.8-flash` | 1 | 0 | 137.9 | 137.9 | 138 | 0.0005 |
| **total** | | | | | | **591** | **0.0800** |

35 keyframe calls made 8 final keyframes plus the reference: the rest are the v1 and v2 sets and the
re-generations from experiments E3, E4, E8, E12 and E13. 9 of the 18 TTS calls were the v1 lines lost to the
instruction-read-aloud bug (F4). For one clean run of the final film: 9 image calls (~82 s),
8 TTS calls (~38 s), 1 text call → **about 2 minutes of model time, ≈ $0.02 list-price equivalent**.

The 503 and quota failures happened before failed attempts were logged, so they are in FAILURES.md
(F2, F5) rather than in this table.

List prices are estimates of the same call on a paid tier (table in `pipeline/common.py`),
to be checked against the providers' current pricing pages.

## Local stages (FFmpeg, M2 Pro)

| Stage | Wall time | Notes |
|---|---|---|
| shots (16 Ken Burns clips, 2 aspects × 8 shots) | 20 s | parallel x264 encodes, 1280×720 / 720×1280 @ 24 fps |
| music placeholder | < 1 s | synthesised with `aevalsrc` |
| assemble (both aspects + SRT + two-pass loudnorm) | 35 s | |
| radio cut | 21 s | |
| full `make film` with everything cached | ~40 s | no API calls |

## GPU minutes

| Stage | GPU | Minutes | Status |
|---|---|---|---|
| Wan 2.2 TI2V-5B (image-to-video) | Kaggle 2× T4 | _to fill_ | not run yet: Ken Burns fallback used |
| ACE-Step 1.5 (score) | Kaggle T4 | _to fill_ | not run yet: placeholder score used |

## Free-tier limits as found (26 Nov 2026)

| Service | Limit found | How we found it |
|---|---|---|
| Gemini `gemini-3.8-flash-tts` | 3 requests/min, **10 requests/day** per model | 429 error bodies |
| Gemini `gemini-3.8-flash-lite-tts` | separate per-model quota (10 used without hitting it) | ran 10 requests |
| Gemini `gemini-3.8-flash` | no limit hit; frequent 503 "high demand" | 2 × 503 then success |
| Cloudflare Workers AI | no limit hit with 35 klein images | daily neuron allowance, see dashboard |

## Frontier comparison

Not available: no frontier-lane key was provided for this cohort.
