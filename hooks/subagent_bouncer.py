#!/usr/bin/env python3
"""subagent-bouncer: no model, no entry.

PreToolUse hook for Claude Code. Denies any Agent spawn that doesn't
carry an explicit `model` param — the deny reason hands the session model
a routing table, so it immediately re-issues the spawn on the cheapest
capable tier. Stdlib only. Never blocks anything except unrouted spawns.
"""

import json
import sys

REASON = (
    "Model routing policy: re-issue this Agent call with an explicit `model` "
    "chosen by task difficulty — haiku: greps, 'where is X', file maps, "
    "mechanical renames/edits; sonnet: single-file builds, standard reviews, "
    "routine exploration; opus: multi-file implementation, hard debugging, "
    "adversarial verification. Reserve the session model for judgment-critical "
    "synthesis only. Pick the cheapest capable tier."
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return  # malformed input: never block the tool call
    if data.get("tool_name") != "Agent":
        return
    if (data.get("tool_input") or {}).get("model"):
        return  # already routed
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }))


if __name__ == "__main__":
    main()
