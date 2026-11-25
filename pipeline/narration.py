"""Narration stage: one WAV per shot from Gemini TTS.

- The style is a SHORT prefix ("Say warmly ...:"). A long instruction was read aloud by the model
  and doubled every clip's length (FAILURES.md F4).
- Free-tier TTS quotas are per model and tiny (10 requests/day measured), so on a daily-quota 429
  we fall back to the next model in voice.fallback_models (FAILURES.md F5).
- voice.speed applies a pitch-preserving tempo change in FFmpeg (no extra API call).
Cached by hash(model, voice, style, speed, line): change one line and only that shot is re-voiced.
"""
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave

from common import (OUT, RetryableError, cached, ensure_dirs, input_hash, load_env,
                    load_storyboard, log_call, mark, media_duration, require_env, run, with_retries,
                    PRICE_USD)

load_env()
require_env("GEMINI_API_KEY")
sb = load_storyboard()
ensure_dirs("narration")
voice = sb["voice"]
models = [voice["model"], *voice.get("fallback_models", [])]
speed = float(voice.get("speed", 1.0))
only = set(sys.argv[1:])  # optional: python narration.py s03
exhausted: set[str] = set()


class DailyQuota(Exception):
    pass


def to_wav(raw: bytes) -> bytes:
    """Gemini returns either a WAV file or raw 24 kHz 16-bit mono PCM - normalise to WAV."""
    if raw[:4] == b"RIFF":
        return raw
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(raw)
    return buf.getvalue()


def tts(model: str, text: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice["name"]}}},
        },
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={
        "Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == 429 and "PerDay" in body:
            raise DailyQuota(body[:300])
        if e.code == 429 or e.code >= 500:
            raise RetryableError(f"HTTP {e.code}: {body[:200]}")
        raise SystemExit(f"HTTP {e.code} from {model}: {body[:400]}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RetryableError(f"network: {e}")


def voice_shot(s):
    line = s.get("narration")
    if not line:
        sys.exit(f"{s['id']} has no narration - run `make script` first")
    out = OUT / "narration" / f"{s['id']}.wav"
    # The cache key ignores which fallback model answered, so a quota fallback does not
    # invalidate lines that were already voiced.
    h = input_hash("narration-v2", voice["name"], voice["style"], speed, line)
    if cached(out, h):
        return f"  {s['id']}: cache hit"
    text = f"{voice['style']} {line}"

    for model in models:
        if model in exhausted:
            continue

        def call(attempt):
            t0 = time.time()
            r = tts(model, text)
            latency = round(time.time() - t0, 2)
            try:
                data = r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
            except (KeyError, IndexError):
                log_call(stage="narration", shot=s["id"], model=model, provider="gemini",
                         status="no_audio", attempt=attempt, latency_s=latency, error=str(r)[:300])
                raise RetryableError("response had no audio")
            raw = OUT / "narration" / f"{s['id']}.raw.wav"
            raw.write_bytes(to_wav(base64.b64decode(data)))
            raw_s = media_duration(raw)
            if speed != 1.0:
                run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", f"atempo={speed}", str(out)])
            else:
                raw.replace(out)
            log_call(stage="narration", shot=s["id"], model=model, provider="gemini",
                     params={"voice": voice["name"], "style": voice["style"], "speed": speed}, seed=None,
                     latency_s=latency, status="ok", attempt=attempt, audio_raw_s=round(raw_s, 2),
                     audio_s=round(media_duration(out), 2), chars=len(line),
                     cost_usd_equiv=PRICE_USD.get(model, PRICE_USD["gemini-3.8-flash-tts"]))
            return model

        try:
            used = with_retries(call, attempts=4, base_delay=20,
                               log={"stage": "narration", "shot": s["id"], "model": model, "provider": "gemini"})  # per-minute limit is 3 requests
        except DailyQuota as e:
            exhausted.add(model)
            log_call(stage="narration", shot=s["id"], model=model, provider="gemini",
                     status="daily_quota", error=str(e)[:200])
            print(f"  {s['id']}: {model} daily quota used up, falling back")
            continue
        mark(out, h)
        return f"  {s['id']}: voiced {media_duration(out):.1f}s with {used}"
    sys.exit(f"{s['id']}: every TTS model is out of daily quota ({', '.join(models)}) - try again after reset")


for s in sb["shots"]:
    if only and s["id"] not in only:
        continue
    print(voice_shot(s), flush=True)
print("narration: done")
