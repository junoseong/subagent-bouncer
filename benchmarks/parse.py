"""Parse benchmark arm JSONs from out/ -> per-run stats + averages."""

import json
from pathlib import Path

OUT = Path(__file__).parent / "out"


def load(name):
    rows = []
    for f in sorted(OUT.glob(f"{name}_[0-9].json")):
        d = json.loads(f.read_text())
        mu = d.get("modelUsage") or {}
        models = "; ".join(
            f"{m}: {u.get('inputTokens', 0)}in/{u.get('outputTokens', 0)}out ${u.get('costUSD', 0):.4f}"
            for m, u in mu.items()
        )
        rows.append({
            "file": f.name,
            "cost": d.get("total_cost_usd") or 0,
            "turns": d.get("num_turns"),
            "tokens": sum(u.get("inputTokens", 0) + u.get("outputTokens", 0) for u in mu.values()),
            "models": models,
        })
    return rows


for arm, label in (("armA", "A: session-model-pinned spawn (inherit proxy)"),
                   ("armB", "B: unrouted spawn -> bouncer reroutes")):
    rows = load(arm)
    print(f"\n== {label} ==")
    for r in rows:
        print(f"{r['file']}: ${r['cost']:.4f} | {r['tokens']} tokens | turns={r['turns']} | {r['models']}")
    if rows:
        print(f"AVG: ${sum(r['cost'] for r in rows) / len(rows):.4f}, "
              f"{sum(r['tokens'] for r in rows) / len(rows):.0f} tokens")
