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
    # deny reason must also push the driver to pre-chew context on retry
    assert "file paths" in payload["permissionDecisionReason"]


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


# --- Workflow script lint ---

def wf(script: str) -> str:
    return run_hook(json.dumps({
        "tool_name": "Workflow",
        "tool_input": {"script": script},
    }))


def test_workflow_unrouted_agent_call_is_denied():
    out = wf("export const meta = {name: 'x', description: 'y'}\n"
             "const r = await agent('map the auth module')\nreturn r")
    payload = deny_payload(out)
    assert payload["permissionDecision"] == "deny"
    assert "opts.model" in payload["permissionDecisionReason"]


def test_workflow_opts_without_model_is_denied():
    out = wf("await agent('grep for X', {label: 'find', phase: 'Scan'})")
    assert deny_payload(out)["permissionDecision"] == "deny"


def test_workflow_routed_agent_call_passes():
    assert wf("await agent('grep for X', {model: 'haiku', label: 'find'})") == ""


def test_workflow_commas_inside_prompt_string_ok():
    # commas/parens in the prompt must not be mistaken for an argument split
    assert wf("await agent('find a, b, and c (all of them)', "
              "{model: 'haiku'})") == ""
    out = wf("await agent(`multi ${line}, with (parens), and commas`)")
    assert deny_payload(out)["permissionDecision"] == "deny"


def test_workflow_bare_identifier_opts_fails_open():
    # can't see inside a variable -> pass, never block a working script
    assert wf("const OPTS = {model: pick()}\nawait agent('x', OPTS)") == ""


def test_workflow_mixed_calls_denied_on_the_unrouted_one():
    out = wf("await agent('a', {model: 'haiku'})\nawait agent('b')")
    assert deny_payload(out)["permissionDecision"] == "deny"


def test_workflow_no_script_fails_open():
    assert run_hook(json.dumps({
        "tool_name": "Workflow",
        "tool_input": {"name": "saved-workflow"},
    })) == ""


def test_workflow_script_path_is_linted(tmp_path):
    p = tmp_path / "wf.js"
    p.write_text("await agent('unrouted spawn')\n")
    out = run_hook(json.dumps({
        "tool_name": "Workflow",
        "tool_input": {"scriptPath": str(p)},
    }))
    assert deny_payload(out)["permissionDecision"] == "deny"
    assert run_hook(json.dumps({
        "tool_name": "Workflow",
        "tool_input": {"scriptPath": str(tmp_path / "missing.js")},
    })) == ""
