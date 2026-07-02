# subagent-bouncer

**Claude Code subagents inherit your session model. This hook checks IDs at the door.**

[![CI](https://github.com/junoseong/subagent-bouncer/actions/workflows/test.yml/badge.svg)](https://github.com/junoseong/subagent-bouncer/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/junoseong/subagent-bouncer)](LICENSE)

[The problem](#the-problem) • [Measured](#measured) • [How it works](#how-it-works) • [Install](#install) • [FAQ](#faq)

A 40-line PreToolUse hook that denies any subagent spawn missing an explicit
`model` param. The deny reason carries a routing table, so your session model
immediately re-issues the spawn on the cheapest capable tier. Self-correcting,
one file, zero dependencies.

```
Session (Opus/Fable)                 subagent-bouncer
     │                                      │
     │  Agent(prompt="grep for X")          │
     ├─────────────────────────────────────►│
     │                                      │  no model param?
     │  ✗ DENIED — "re-issue with explicit  │
     │    model: haiku for greps, sonnet    │
     │    for single-file work, opus for    │
     │◄─────────────────────────────────────┤    hard debugging..."
     │                                      │
     │  Agent(prompt="grep for X",          │
     │        model="haiku")                │
     ├─────────────────────────────────────►│
     │  ✓ pass                              │
```

## The problem

Every subagent you don't explicitly route **inherits the session model** —
run your session on Opus or Fable and every spawned agent, including greps
and file listings, bills at that rate.

This compounds fast, because subagents re-read context instead of sharing
yours: subagent-heavy workflows commonly run **4–7× the tokens** of a
single-thread session, and "85% of your usage came from subagent-heavy
sessions" is a recurring `/usage` complaint. Haiku is 5× cheaper than Opus
and 10× cheaper than Fable per token — explicit model routing is the whole
lever, and by default nothing pulls it.

## Measured

Controlled experiment: six headless Claude Code sessions (`claude -p
--output-format json`), identical investigation task on a small repo, Opus
driver in both arms. Arm A pins the subagent to `opus` — exactly what
inheriting the session model does without the bouncer. Arm B spawns
unrouted, so the bouncer denies and the driver reroutes. Costs are what the
CLI itself reported from real per-model token usage:

| Run | Subagent on Opus (no bouncer) | Bounced | Rerouted to |
|---|---|---|---|
| 1 | $0.387 | $0.261 | haiku |
| 2 | $0.394 | $0.435 | sonnet |
| 3 | $0.375 | $0.246 | haiku |
| **avg** | **$0.385** | **$0.314 (−19%)** | |

All six runs returned the correct answer. When the driver picked Haiku
(2 of 3), the bounced run cost **35% less**. The run it picked Sonnet cost
10% *more* than unbounced — the deny retry plus the subagent's fresh
context re-read aren't free, and routing variance is real. The bigger and
more frequent your spawns, the more the arbitrage dominates: Haiku is 5×
cheaper than Opus and 10× cheaper than Fable per token.

Reproduce (bills your own subscription):

```bash
cd <some-repo> && bash benchmarks/run_bench.sh
```

Earlier single observation, different task, same shape: unhooked spawn
25.3k tokens / 3 tool calls vs bounced 11.4k / 1 — the deny feedback also
made the session model write a tighter prompt on the retry.

## How it works

The whole hook is [one readable file](hooks/subagent_bouncer.py) — audit it
before installing, it's shorter than this README:

1. Claude Code fires the hook before every `Agent` tool call.
2. Spawn has an explicit `model`? Pass through, zero interference.
3. No `model`? Deny, with a reason that doubles as a routing table:
   *haiku* for greps/locates/mechanical edits, *sonnet* for single-file work
   and routine reviews, *opus* for multi-file implementation and hard
   debugging — session model reserved for judgment-critical synthesis.
4. The session model reads the reason and re-issues the spawn with the
   cheapest capable tier. One retry, self-correcting, no config.

**Why deny instead of silently rewriting the call?** A hook could inject
`model: haiku` itself — but a static rule can't judge task difficulty, and
misrouting hard work to Haiku costs more in retries than it saves. Your
session model already knows what the task needs; the bouncer just refuses
to let it *not choose*. Anything malformed or non-Agent passes through
untouched — the hook fails open everywhere except the one case it exists for.

## Install

As a plugin (hooks register automatically):

```
/plugin marketplace add junoseong/subagent-bouncer
/plugin install subagent-bouncer@subagent-bouncer
```

Or manually:

```bash
curl -o ~/.claude/hooks/subagent_bouncer.py https://raw.githubusercontent.com/junoseong/subagent-bouncer/main/hooks/subagent_bouncer.py
```

then add to `~/.claude/settings.json`:

```json
"hooks": {
  "PreToolUse": [
    {
      "matcher": "Agent",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ~/.claude/hooks/subagent_bouncer.py"
        }
      ]
    }
  ]
}
```

Needs Python 3 on PATH. Uninstall: `/plugin uninstall subagent-bouncer` (or
delete the file + settings block).

## FAQ

**Does it break my workflows?** No. Routed spawns pass through untouched;
unrouted ones cost exactly one retry. Malformed input, other tools,
anything unexpected — the hook stays silent and blocks nothing.

**Does it cover `Workflow` orchestration agents?** No — workflow `agent()`
calls aren't matchable by PreToolUse hooks. Set `opts.model` in workflow
scripts manually.

**What if I *want* the session model for a spawn?** Say so explicitly:
`model: opus` (or your session's tier) passes the bouncer. The point is
choosing, not forbidding.

**Custom agent types with pinned models?** Agents whose frontmatter pins a
`model:` still send it in the tool call, so they pass. Only truly unrouted
spawns get bounced.

**Works with which session models?** Any — the routing table in the deny
reason is model-agnostic. The more expensive your session model, the more
this saves.

## Related

[claude-model-router](https://github.com/junoseong/claude-model-router) —
the same philosophy for the Claude API side: a Haiku classifier routes each
prompt to the cheapest capable model, with the per-model request quirks
(thinking configs, refusal handling, effort support) handled correctly.

---

If this cut your bill, a ⭐ helps others find it.

MIT licensed.
