"""Summarise runs.jsonl per stage and model: calls, failures, latency, list-price equivalent.

Prints a Markdown table (paste it into COSTS.md).
"""
import json
from collections import defaultdict

from common import RUNS

rows = defaultdict(lambda: {"ok": 0, "fail": 0, "lat": [], "cost": 0.0, "audio": 0.0})
for line in RUNS.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    k = (r.get("stage", "?"), r.get("model", "?"))
    row = rows[k]
    if r.get("status") == "ok":
        row["ok"] += 1
        row["lat"].append(r.get("latency_s") or 0)
        row["cost"] += r.get("cost_usd_equiv") or 0
        row["audio"] += r.get("audio_s") or 0
    else:
        row["fail"] += 1

print("| Stage | Model | OK calls | Failed | Mean latency (s) | Max latency (s) | Total (s) | List-price equiv. (USD) |")
print("|---|---|---|---|---|---|---|---|")
tot_cost = tot_time = 0
for (stage, model), r in sorted(rows.items()):
    lat = r["lat"] or [0]
    tot_cost += r["cost"]
    tot_time += sum(lat)
    print(f"| {stage} | `{model}` | {r['ok']} | {r['fail']} | {sum(lat) / len(lat):.1f} | {max(lat):.1f} | "
          f"{sum(lat):.0f} | {r['cost']:.4f} |")
print(f"| **total** | | | | | | **{tot_time:.0f}** | **{tot_cost:.4f}** |")
