#!/usr/bin/env python3
"""PreToolUse gate on the Agent tool: no Fable subagents without explicit permission.

Origin (2026-08-14, the day it bit): a Fable-driven session spawned ~10 subagents with
`model:` UNSET; they inherited Fable, drained Joshua's Fable credit pool, and two
overnight measurements died at launch with "out of usage credits". The pool is
PER-MODEL and the failure is silent — nothing at launch says "wrong pool".
Joshua, 2026-08-16: "should we have a hook to force Claude to only invoke fable
with my explicit permission?"

Rules enforced (exit 2 blocks the call; stderr is shown to the model):
  1. `model` MUST be set explicitly on every Agent call. Unset = silent
     inheritance = the exact Friday failure mode. Blocked with instructions.
  2. `model: "fable"` is blocked UNLESS the literal token FABLE-OK appears in
     the prompt — which the orchestrator may only add after Joshua explicitly
     approves Fable for that spawn, and which makes the approval grep-able in
     the transcript.

This is friction + visibility, not a hard wall (the model types the override
itself). Friday's failure was silence, not defiance; this removes the silence.
"""
import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break tool flow on malformed input

    if payload.get("tool_name") not in ("Agent", "Task"):
        return 0

    ti = payload.get("tool_input") or {}
    model = ti.get("model")
    prompt = ti.get("prompt") or ""

    if model is None or str(model).strip() == "":
        sys.stderr.write(
            "Agent-model gate: `model:` is UNSET. Set it explicitly on every "
            "Agent call — an unset model inherits the session model, which on "
            "2026-08-14 silently routed ~10 subagents to an exhausted Fable "
            "credit pool (per-model pools; the failure surfaces only as a dead "
            "agent AFTER the tokens are spent). Pick 'opus'/'sonnet'/'haiku', "
            "or 'fable' only with Joshua's explicit permission + the FABLE-OK "
            "token in the prompt.\n"
        )
        return 2

    if str(model).strip().lower() == "fable" and "FABLE-OK" not in prompt:
        sys.stderr.write(
            "Agent-model gate: model 'fable' requires Joshua's EXPLICIT "
            "per-spawn permission (standing rule: never spawn a Fable subagent "
            "unless he asks). If he approved this specific spawn, add the "
            "literal token FABLE-OK to the prompt and retry; otherwise use "
            "another model.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
