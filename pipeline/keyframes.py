"""Keyframe stage: a character reference portrait, then one still per shot.

Model: FLUX.2 klein 4B on Cloudflare Workers AI (Apache 2.0). Unlike FLUX.1 schnell on Workers AI,
it accepts a seed and reference images, so every shot that shows the grandmother is conditioned on
the same golden reference (outputs/keyframes/reference.jpg). The model has no memory: consistency
comes from what we send every time - reference image, character description, style block, seed.

Cached by hash(model, prompt, seed, reference bytes): edit one image_prompt and only that keyframe
regenerates; regenerate the reference and every character shot follows it.
"""
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

from common import (OUT, RetryableError, cached, ensure_dirs, input_hash, load_env,
                    load_storyboard, log_call, mark, require_env, with_retries, PRICE_USD)

load_env()
require_env("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
sb = load_storyboard()
ensure_dirs("keyframes")
model = sb.get("image_model", "@cf/black-forest-labs/flux-2-klein-4b")
SIZE = 1024  # square: composed centre-out, cropped later to 16:9 and 9:16
url = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/ai/run/{model}"
REF = OUT / "keyframes" / "reference.jpg"
only = set(sys.argv[1:])


def post_multipart(fields: dict, files: dict) -> dict:
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    for k, data in files.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{k}.jpg\"\r\n"
                 f"Content-Type: image/jpeg\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
        "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:400]
        if e.code == 429 or e.code >= 500:
            raise RetryableError(f"HTTP {e.code}: {msg}")
        raise SystemExit(f"HTTP {e.code}: {msg}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RetryableError(f"network: {e}")


def build_prompt(s):
    parts = [s["image_prompt"]]
    if s.get("with_character"):
        parts.append(f"The grandmother is the woman in the reference image: {sb['character']['description']}")
    parts.append(sb["style_block"])
    return ". ".join(parts)


def generate(name, prompt, seed, use_ref):
    out = OUT / "keyframes" / f"{name}.jpg"
    ref_bytes = REF.read_bytes() if use_ref else b""
    h = input_hash("keyframe-v2", model, SIZE, prompt, seed, hashlib.sha256(ref_bytes).hexdigest())
    if cached(out, h):
        return f"  {name}: cache hit"
    fields = {"prompt": prompt, "seed": seed, "width": SIZE, "height": SIZE}
    files = {"input_image_0": ref_bytes} if use_ref else {}

    def call(attempt):
        t0 = time.time()
        r = post_multipart(fields, files)
        latency = round(time.time() - t0, 2)
        if not r.get("success") or "image" not in (r.get("result") or {}):
            log_call(stage="keyframes", shot=name, model=model, provider="cloudflare",
                     status="error", attempt=attempt, latency_s=latency, error=str(r.get("errors"))[:300])
            raise RetryableError(str(r.get("errors")))
        out.write_bytes(base64.b64decode(r["result"]["image"]))
        log_call(stage="keyframes", shot=name, model=model, provider="cloudflare",
                 params={"width": SIZE, "height": SIZE, "reference": use_ref, "prompt": prompt},
                 seed=seed, latency_s=latency, status="ok", attempt=attempt,
                 cost_usd_equiv=PRICE_USD.get(model))
        return latency

    latency = with_retries(call, log={"stage": "keyframes", "shot": name, "model": model, "provider": "cloudflare"})
    mark(out, h)
    return f"  {name}: generated in {latency:.1f}s" + (" (with reference)" if use_ref else "")


if not only or "reference" in only or not REF.exists():
    ref_prompt = (f"character reference portrait, front view, head and shoulders, plain warm ochre background: "
                  f"{sb['character']['description']}. {sb['style_block']}")
    print(generate("reference", ref_prompt, 1000, use_ref=False))

for s in sb["shots"]:
    if only and s["id"] not in only:
        continue
    print(generate(s["id"], build_prompt(s), s.get("seed", 0), use_ref=bool(s.get("with_character"))))
print("keyframes: done")
