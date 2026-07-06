#!/usr/bin/env python3
"""subagent-bouncer: no model, no entry.

PreToolUse hook for Claude Code. Denies any Agent spawn that doesn't
carry an explicit `model` param — the deny reason hands the session model
a routing table, so it immediately re-issues the spawn on the cheapest
capable tier. Also lints Workflow scripts: an agent() call that provably
omits opts.model gets the same treatment before the workflow runs.
Stdlib only. Fails open everywhere except provably unrouted spawns.
"""

import json
import re
import sys

REASON = (
    "Model routing policy: re-issue this Agent call with an explicit `model` "
    "chosen by task difficulty — haiku: greps, 'where is X', file maps, "
    "mechanical renames/edits; sonnet: single-file builds, standard reviews, "
    "routine exploration; opus: multi-file implementation, hard debugging, "
    "adversarial verification. Reserve the session model for judgment-critical "
    "synthesis only. Pick the cheapest capable tier. In the re-issued prompt, "
    "include what you already know — relevant file paths, key snippets, prior "
    "findings — so the subagent starts warm instead of re-exploring from cold."
)

WORKFLOW_REASON = (
    "Model routing policy: every workflow agent() call must pass an explicit "
    "opts.model chosen by task difficulty — haiku: greps, 'where is X', file "
    "maps, mechanical renames/edits; sonnet: single-file builds, standard "
    "reviews, routine exploration; opus: multi-file implementation, hard "
    "debugging, adversarial verification. Unrouted spawns inherit the session "
    "model and bill at its rate. Re-issue this Workflow call with model set "
    "on each agent() spawn, and include known context in each prompt so "
    "agents start warm."
)


def _call_args(src: str, open_paren: int):
    """Text between a call's balanced parens, or None if unparseable."""
    depth, i, quote = 0, open_paren, None
    while i < len(src):
        c = src[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return src[open_paren + 1:i]
        i += 1
    return None


def _split_top(args: str):
    """Split argument text on top-level commas (string- and bracket-aware)."""
    parts, cur, depth, quote, i = [], [], 0, None, 0
    while i < len(args):
        c = args[i]
        if quote:
            cur.append(c)
            if c == "\\" and i + 1 < len(args):
                cur.append(args[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
            cur.append(c)
        elif c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    return parts


def workflow_script_unrouted(src: str) -> bool:
    """True if some agent() call in the script provably omits opts.model.

    Fail-open rules: opts passed as a bare identifier/expression can't be
    inspected -> pass; unparseable call -> pass. Only a missing second
    argument or an object literal without `model:` is a violation.
    """
    for m in re.finditer(r"\bagent\s*\(", src):
        args = _call_args(src, m.end() - 1)
        if args is None:
            continue
        parts = _split_top(args)
        if len(parts) < 2 or not parts[1].strip():
            return True
        opts = parts[1].strip()
        if opts.startswith("{") and not re.search(r"\bmodel\s*:", opts):
            return True
    return False


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return  # malformed input: never block the tool call
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    tool = data.get("tool_name")
    if tool == "Agent":
        if not tool_input.get("model"):
            deny(REASON)
    elif tool == "Workflow":
        src = tool_input.get("script")
        if not src and tool_input.get("scriptPath"):
            try:
                with open(tool_input["scriptPath"], errors="replace") as f:
                    src = f.read()
            except OSError:
                return  # unreadable path: fail open
        if src and workflow_script_unrouted(src):
            deny(WORKFLOW_REASON)
        # named workflows / no script visible: fail open


if __name__ == "__main__":
    main()
