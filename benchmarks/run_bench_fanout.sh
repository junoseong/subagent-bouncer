#!/bin/bash
# Fan-out benchmark: one session, FIVE parallel subagents — the multi-agent
# session shape. Arm A pins every spawn to the session model (= inherit);
# arm B spawns unrouted so the bouncer denies and the driver reroutes.
#
# One run per arm (a Fable fan-out is expensive — that's the point). Writes
# real modelUsage + total_cost_usd JSON to benchmarks/out/. Bills your
# subscription. Requires the bouncer hook installed; edit TASK for your repo.
#
# Usage:  cd <some-repo> && bash path/to/run_bench_fanout.sh [model]
set -u
OUT="$(dirname "$0")/out"
mkdir -p "$OUT"
MODEL="${1:-fable}"

TASK='You are investigating this repo. Fan out FIVE parallel subagents via the Agent tool in a single message — one subagent per question below. Do not read any files yourself; delegate everything. Questions: (1) Where is the main entry point and what does it do? (2) What are the public functions/commands and what does each one do? (3) List the test files and summarize what each covers. (4) How is error handling structured? (5) What external dependencies are used and where? After all five return, synthesize their answers into one short report.'
PIN=" When spawning agents, set model: \"${MODEL}\" on every Agent call."

echo "=== fanoutA (${MODEL}-pinned spawns = inherit proxy) ==="
claude -p "${TASK}${PIN}" --model "$MODEL" --output-format json \
  --allowedTools "Agent,Read,Grep,Glob" --max-turns 30 > "$OUT/fanoutA_1.json"
echo "=== fanoutB (unrouted -> bouncer) ==="
claude -p "${TASK}" --model "$MODEL" --output-format json \
  --allowedTools "Agent,Read,Grep,Glob" --max-turns 30 > "$OUT/fanoutB_1.json"

OUT="$OUT" python3 - <<'EOF'
import json, os
out = os.environ['OUT']
for arm in ('fanoutA_1', 'fanoutB_1'):
    try:
        d = json.load(open(os.path.join(out, arm + '.json')))
    except Exception:
        continue
    models = ', '.join(f"{m.split('-2')[0]}:${u.get('costUSD', 0):.2f}"
                       for m, u in (d.get('modelUsage') or {}).items())
    print(f"{arm}: total ${d.get('total_cost_usd', 0):.2f}  [{models}]")
EOF
