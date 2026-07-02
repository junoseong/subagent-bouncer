#!/bin/bash
# Token benchmark: subagent pinned to the session model (= what "inherit"
# does without the bouncer) vs unrouted spawn (bouncer denies -> reroutes).
#
# Runs 3 headless Claude Code sessions per arm against the repo in $PWD and
# writes per-run JSON (real modelUsage token counts + cost) to benchmarks/out/.
# Bills your Claude subscription like any other session. Requires the bouncer
# hook installed, and a task the repo can answer — edit TASK for your repo.
#
# Usage:  cd <some-repo> && bash path/to/run_bench.sh
set -u
OUT="$(dirname "$0")/out"
mkdir -p "$OUT"

TASK='Task: determine where build_request is defined in this repo and summarize, in two sentences, how it shapes requests differently for Haiku models. You MUST delegate the investigation to a single subagent via the Agent tool — do not read any files yourself.'
PIN=' When spawning the agent, set model: "opus".'
TAIL=' Then report the answer.'

for i in 1 2 3; do
  echo "=== armA run $i (opus-pinned spawn = inherit proxy) ==="
  claude -p "${TASK}${PIN}${TAIL}" --model opus --output-format json \
    --allowedTools "Agent,Read,Grep,Glob" --max-turns 12 > "$OUT/armA_$i.json"
  echo "=== armB run $i (unrouted -> bouncer) ==="
  claude -p "${TASK}${TAIL}" --model opus --output-format json \
    --allowedTools "Agent,Read,Grep,Glob" --max-turns 12 > "$OUT/armB_$i.json"
done
python3 "$(dirname "$0")/parse.py"
