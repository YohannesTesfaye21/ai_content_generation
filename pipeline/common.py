"""Shared helpers for every pipeline stage.

- load_env():      reads .env (no external dependency)
- load_storyboard(): reads storyboard.json and validates it against schema/
- input_hash():    stable hash of a stage's inputs, used for caching
- cached():        True if an output exists and was produced from the same inputs
- log_call():      appends one line per model call to runs.jsonl
- with_retries():  exponential backoff for flaky / rate-limited APIs
- http_json():     tiny urllib wrapper (no requests dependency)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
RUNS = ROOT / "runs.jsonl"

# Approximate list-price equivalents (USD) used for COSTS.md. These are estimates of
# what the same call would cost on a paid tier; we pay $0 on the free tiers.
# Verify against the providers' pricing pages before quoting them.
PRICE_USD = {
    "@cf/black-forest-labs/flux-1-schnell": 0.0011,   # per 1024x1024 image (approx.)
    "@cf/black-forest-labs/flux-2-klein-4b": 0.0015,  # per 1024x1024 image (approx.)
    "gemini-3.8-flash": 0.0005,                       # per short text call (approx.)
    "gemini-3.8-flash-tts": 0.002,                    # per ~10 s narration line (approx.)
    "gemini-3.8-flash-lite-tts": 0.001,               # per ~10 s narration line (approx.)
}


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        sys.exit("Missing .env - copy .env.example to .env and fill in your keys.")
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def require_env(*names: str) -> None:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")


def load_storyboard(validate: bool = True) -> dict:
    sb = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    if validate:
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(sb, schema)
        except jsonschema.ValidationError as e:
            path = "/".join(str(p) for p in e.absolute_path) or "(root)"
            sys.exit(f"storyboard.json is invalid at {path}: {e.message}")
        ids = [s["id"] for s in sb["shots"]]
        if len(ids) != len(set(ids)):
            sys.exit("storyboard.json: shot ids must be unique")
    return sb


def save_storyboard(sb: dict) -> None:
    STORYBOARD.write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def input_hash(*parts) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def cached(output: Path, h: str) -> bool:
    meta = output.with_suffix(output.suffix + ".hash")
    return output.exists() and meta.exists() and meta.read_text().strip() == h


def mark(output: Path, h: str) -> None:
    output.with_suffix(output.suffix + ".hash").write_text(h)


def log_call(**fields) -> None:
    fields = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **fields}
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fields, ensure_ascii=False) + "\n")


class RetryableError(Exception):
    pass


def with_retries(fn, attempts: int = 3, base_delay: float = 5.0, log: dict | None = None):
    """Call fn(attempt) up to `attempts` times, backing off on RetryableError.

    `log` (stage/shot/model/provider) makes every failed attempt a runs.jsonl line too.
    """
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(attempt)
        except RetryableError as e:
            last = e
            if log:
                log_call(**log, status="retryable_error", attempt=attempt, error=str(e)[:300])
            if attempt < attempts:
                delay = base_delay * 2 ** (attempt - 1)
                print(f"    retry {attempt}/{attempts - 1} in {delay:.0f}s: {e}")
                time.sleep(delay)
    raise SystemExit(f"Giving up after {attempts} attempts: {last}")


def http_json(url: str, payload: dict, headers: dict, timeout: float = 240) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        if e.code == 429 or e.code >= 500:
            raise RetryableError(f"HTTP {e.code}: {body}")
        raise SystemExit(f"HTTP {e.code} from {url.split('?')[0]}: {body}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RetryableError(f"network: {e}")


def run(cmd: list[str]) -> str:
    """Run a command (ffmpeg/ffprobe), fail loudly with its stderr."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"Command failed: {' '.join(cmd[:6])} ...\n{p.stderr[-1500:]}")
    return p.stdout + p.stderr


def media_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip().splitlines()[0])


def shot_durations(sb: dict) -> dict[str, float]:
    """Final length of each shot: the storyboard duration, stretched if the narration is longer.

    The narration sets the pace (professionals cut picture to the voice track).
    """
    pad = sb.get("timing", {}).get("narration_padding_s", 1.0)
    lead = sb.get("timing", {}).get("narration_lead_s", 0.4)
    out = {}
    for s in sb["shots"]:
        d = float(s["duration"])
        wav = OUT / "narration" / f"{s['id']}.wav"
        if wav.exists():
            d = max(d, lead + media_duration(wav) + pad)
        out[s["id"]] = round(d, 2)
    return out


def ensure_dirs(*names: str) -> None:
    for n in names:
        (OUT / n).mkdir(parents=True, exist_ok=True)
