#!/usr/bin/env python3
"""How much of YOUR subagent spend inherited an expensive session model?

Scans the subagent transcripts Claude Code already keeps on disk
(~/.claude/projects/<project>/<session>/subagents/) and reports real token
spend by model tier, plus what the same tokens would have cost routed to
sonnet or haiku. Stdlib only, read-only, nothing leaves your machine.

Usage:
    python3 scan_your_logs.py                     # spend by tier + counterfactual
    python3 scan_your_logs.py --cutoff 2026-07-02 # before/after a date (e.g. hook install)

Numbers are list-price token value ($/MTok; cache writes 1.25x input,
cache reads 0.1x). On a subscription plan this is limits burned, not
dollars invoiced. "Repriced" = same tokens, cheaper meter — conservative,
since expensive models tend to think longer on the same task, not shorter.
"""
import argparse
import glob
import json
import os
from collections import defaultdict

PRICE = {  # $/MTok (input, output)
    "haiku": (1.0, 5.0),
    "sonnet": (3.0, 15.0),
    "opus": (5.0, 25.0),
    "fable": (10.0, 50.0),
}
EXPENSIVE = ("opus", "fable")


def tier(model):
    m = (model or "").lower()
    for t in PRICE:
        if t in m:
            return t
    return None


def cost(t, u):
    i, o = PRICE[t]
    return (u["in"] * i + u["out"] * o + u["cw"] * i * 1.25 + u["cr"] * i * 0.1) / 1e6


def new_bucket():
    return defaultdict(lambda: {"in": 0, "out": 0, "cw": 0, "cr": 0, "n": 0})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cutoff", help="ISO date: split spend into before/after")
    ap.add_argument("--root", default="~/.claude/projects", help="projects dir")
    args = ap.parse_args()

    eras = defaultdict(new_bucket)  # era -> tier -> usage
    sessions = defaultdict(float)   # session path -> total spend
    seen = set()

    pattern = os.path.join(os.path.expanduser(args.root), "*", "*", "subagents", "**", "*.jsonl")
    files = glob.glob(pattern, recursive=True)
    if not files:
        print(f"No subagent transcripts under {args.root} — nothing to scan.")
        return

    for path in files:
        sess = path.split("/subagents/")[0]
        try:
            with open(path, errors="replace") as f:
                for line in f:
                    if '"usage"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = d.get("message") or {}
                    if not isinstance(msg, dict):
                        continue
                    u, t = msg.get("usage"), tier(msg.get("model"))
                    if not u or not t:
                        continue
                    mid = msg.get("id")
                    if mid:
                        key = (mid, u.get("output_tokens", 0))
                        if key in seen:
                            continue
                        seen.add(key)
                    ts = d.get("timestamp") or ""
                    era = "all"
                    if args.cutoff:
                        era = "after" if ts >= args.cutoff else "before"
                    b = eras[era][t]
                    b["in"] += u.get("input_tokens", 0)
                    b["out"] += u.get("output_tokens", 0)
                    b["cw"] += u.get("cache_creation_input_tokens", 0)
                    b["cr"] += u.get("cache_read_input_tokens", 0)
                    b["n"] += 1
                    sessions[sess] += cost(t, {k: u.get(v, 0) for k, v in
                                              (("in", "input_tokens"), ("out", "output_tokens"),
                                               ("cw", "cache_creation_input_tokens"),
                                               ("cr", "cache_read_input_tokens"))})
        except OSError:
            continue

    for era in ("before", "after") if args.cutoff else ("all",):
        per = eras.get(era)
        if not per:
            continue
        total = sum(cost(t, u) for t, u in per.items())
        if not total:
            continue
        exp = sum(cost(t, u) for t, u in per.items() if t in EXPENSIVE)
        at_sonnet = sum(cost("sonnet" if t in EXPENSIVE else t, u) for t, u in per.items())
        at_haiku = sum(cost("haiku" if t in EXPENSIVE else t, u) for t, u in per.items())
        label = f"[{era}]" if args.cutoff else ""
        print(f"\n=== Subagent spend {label} ===")
        for t, u in sorted(per.items(), key=lambda kv: -cost(kv[0], kv[1])):
            print(f"  {t:<8} ${cost(t, u):>9.2f}   ({u['n']} messages)")
        print(f"  {'total':<8} ${total:>9.2f}")
        print(f"  on opus/fable: {100 * exp / total:.1f}%")
        print(f"  same tokens repriced @sonnet: ${at_sonnet:.2f}   @haiku: ${at_haiku:.2f}")

    top = sorted(sessions.items(), key=lambda kv: -kv[1])[:5]
    print("\n=== Top sessions by subagent spend ===")
    for sess, c in top:
        parts = sess.rstrip("/").split("/")
        print(f"  ${c:>8.2f}  {parts[-2].split('-')[-1][:20]}/{parts[-1][:8]}")


if __name__ == "__main__":
    main()
