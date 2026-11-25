# Failures

What broke, what I tried, what fixed it. Times are East Africa Time, 26 November 2026.

### F1 — FLUX.1 schnell rejects `seed` (Cloudflare error 5006)
- **Symptom:** first keyframe run died: `AiError: Bad input: Additional or unevaluated properties '/seed' at '/' not allowed`.
- **Tried:** checked the model's input schema via the Workers AI API.
- **Fix:** switched to `flux-2-klein-4b`, which accepts seeds and reference images (EXPERIMENTS E1).
  The challenge brief lists schnell as a default; the tool had moved.

### F2 — Gemini 503 "model is currently experiencing high demand"
- **Symptom:** the script (translation) call and a transcription check returned HTTP 503.
- **Fix:** `with_retries` backed off 5 s then 10 s; the third attempt succeeded. Failed attempts
  are now logged in `runs.jsonl` as `retryable_error` (added after this run, so the first 503s are
  only in the console log).

### F3 — Gemini text latency of 138 s
- **Symptom:** one translation call for 9 lines took 137.9 s (`runs.jsonl`), most of it inside
  the retries above.
- **Workaround:** the script stage is cached (only runs for empty lines) and uses a 300 s timeout.

### F4 — TTS read the style instruction aloud
- **Symptom:** narration clips were 18–23 s instead of ~8 s.
- **Diagnosis:** `ffmpeg -af silencedetect` showed two speech blocks separated by a 1.5 s gap;
  the first was the English instruction.
- **Fix:** short `Say warmly, at a gentle natural pace:` prefix (EXPERIMENTS E5).

### F5 — Gemini TTS free tier: 3 requests/minute and **10 requests/day per model**
- **Symptom:** `429 … generate_content_free_tier_requests, limit: 3` (per minute), then
  `limit: 10 … GenerateRequestsPerDayPerProjectPerModel-FreeTier`, "retry in 8h49m".
  The brief describes TTS as free; it is, but 10 lines a day is the whole budget for a 9-shot film.
  The F4 mistake consumed 9 of the 10 Flash TTS requests.
- **Tried:** waiting is not an option on deadline day. Quotas are per model, so I probed other TTS
  models.
- **Fix:** `gemini-3.8-flash-lite-tts` as primary with `gemini-3.8-flash-tts` as fallback.
  `narration.py` now distinguishes a per-minute 429 (retry with 20 s backoff) from a daily 429
  (`PerDay` in the body → mark the model exhausted and fall back immediately).
- **Lesson:** test a new prompt format on **one** line before voicing all of them.

### F6 — My own shell bug: every model URL returned 404
- **Symptom:** probing TTS models in a zsh loop, every request was HTTP 404 with an empty body.
- **Cause:** in zsh, `$M:generateContent` applies the `:g` history modifier to `$M`.
- **Fix:** `${M}:generateContent`. Cost: ten minutes of thinking the models did not exist.

### F7 — FFmpeg build without `drawtext` or `subtitles` (no freetype/libass)
- **Symptom:** `ffmpeg -filters` lists neither filter on this Homebrew build.
- **Fix:** draw subtitle cards and the end card as transparent PNGs with Pillow (`pipeline/cards.py`)
  and overlay them with `overlay=enable='between(t,a,b)'`. Works with any FFmpeg build.

### F8 — The script stage overwrote a concurrent storyboard edit
- **Symptom:** while the 138 s translation call ran, I changed `image_model` in `storyboard.json`;
  when the call returned, the script saved its in-memory copy and reverted my change.
- **Fix:** `script.py` reloads the storyboard after the model call and only fills empty
  `narration` fields before saving.

### F9 — Reference image hijacked close-up compositions
- See EXPERIMENTS E3. Fixed by not attaching the reference to insert shots.

### F10 — Film too long (98 s) with no TTS quota left to shorten lines
- See EXPERIMENTS E7. Fixed by cutting a shot and a 1.1× tempo.

### F11 — Wan 2.2 and ACE-Step not yet run
- **Status:** _to fill._ Every shot currently uses the Ken Burns fallback and the score is the
  synthesised placeholder. Record here what happens on Kaggle (GPU queue, out-of-memory errors on the
  T4, time per clip).
