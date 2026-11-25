"""Script stage: draft the narration in the film's language from the English lines (Gemini).

Only fills shots whose `narration` is empty, so hand-corrected lines are never overwritten.
Every drafted line is marked narration_reviewed=false until a native speaker checks it.
"""
import json
import os
import time

from common import (RetryableError, http_json, load_env, load_storyboard, log_call,
                    require_env, save_storyboard, with_retries, PRICE_USD)

MODEL = "gemini-3.8-flash"

load_env()
require_env("GEMINI_API_KEY")
sb = load_storyboard()
todo = [s for s in sb["shots"] if not s.get("narration")]
if not todo:
    print("script: all narration lines present (cache hit)")
    raise SystemExit

lang = sb.get("language_name", sb["language"])
lines = {s["id"]: s["narration_en"] for s in todo}
prompt = (
    f"Translate these narration lines for a short family documentary into natural, spoken {lang}. "
    "Write for the ear: short sentences, simple everyday words, warm tone, as a grandchild would speak. "
    "Keep these Ethiopian coffee-ceremony words as they are spoken: abol, tona, baraka, jebena. "
    "Use the native script. Return only a JSON object mapping each id to its translated line.\n\n"
    + json.dumps(lines, ensure_ascii=False, indent=1)
)
url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
}


def call(attempt):
    t0 = time.time()
    r = http_json(url, payload, {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=300)
    latency = round(time.time() - t0, 2)
    try:
        text = r["candidates"][0]["content"]["parts"][0]["text"]
        out = json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        log_call(stage="script", model=MODEL, provider="gemini", status="bad_response",
                 attempt=attempt, latency_s=latency, error=str(e)[:200])
        raise RetryableError(f"unparseable response: {e}")
    usage = r.get("usageMetadata", {})
    log_call(stage="script", shot=",".join(lines), model=MODEL, provider="gemini",
             params={"temperature": 0.3, "target_language": lang}, seed=None,
             latency_s=latency, status="ok", attempt=attempt,
             tokens_in=usage.get("promptTokenCount"), tokens_out=usage.get("candidatesTokenCount"),
             cost_usd_equiv=PRICE_USD[MODEL])
    return out


translated = with_retries(call, log={"stage": "script", "model": MODEL, "provider": "gemini"})
sb = load_storyboard()  # reload: the file may have been edited while the (slow) call ran
todo = [s for s in sb["shots"] if not s.get("narration")]
for s in todo:
    if s["id"] in translated and translated[s["id"]].strip():
        s["narration"] = translated[s["id"]].strip()
        s["narration_reviewed"] = False
        print(f"  {s['id']}: {s['narration']}")
save_storyboard(sb)
print("script: narration drafted into storyboard.json - please have a native speaker review it")
