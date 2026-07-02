"""Black-box tests: feed the hook stdin JSON, assert on stdout.

Run: python3 -m pytest -q  (stdlib + pytest only)
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "subagent_bouncer.py"


def run_hook(stdin_text: str) -> str:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def deny_payload(out: str) -> dict:
    payload = json.loads(out)["hookSpecificOutput"]
    assert payload["hookEventName"] == "PreToolUse"
    return payload


def test_unrouted_agent_spawn_is_denied():
    out = run_hook(json.dumps({
        "tool_name": "Agent",
        "tool_input": {"prompt": "map the auth module", "description": "explore"},
    }))
    payload = deny_payload(out)
    assert payload["permissionDecision"] == "deny"
    assert "haiku" in payload["permissionDecisionReason"]
    assert "model" in payload["permissionDecisionReason"]


def test_routed_agent_spawn_passes():
    out = run_hook(json.dumps({
        "tool_name": "Agent",
        "tool_input": {"prompt": "map the auth module", "model": "haiku"},
    }))
    assert out == ""


def test_other_tools_untouched():
    for tool in ("Bash", "Edit", "Read", "Workflow"):
        out = run_hook(json.dumps({"tool_name": tool, "tool_input": {}}))
        assert out == "", f"{tool} should pass through"


def test_missing_tool_input_is_denied():
    out = run_hook(json.dumps({"tool_name": "Agent"}))
    assert deny_payload(out)["permissionDecision"] == "deny"


def test_null_tool_input_is_denied():
    out = run_hook(json.dumps({"tool_name": "Agent", "tool_input": None}))
    assert deny_payload(out)["permissionDecision"] == "deny"


def test_empty_model_string_is_denied():
    out = run_hook(json.dumps({
        "tool_name": "Agent",
        "tool_input": {"prompt": "x", "model": ""},
    }))
    assert deny_payload(out)["permissionDecision"] == "deny"


def test_malformed_stdin_never_blocks():
    assert run_hook("not json {{{") == ""
    assert run_hook("") == ""
