#!/usr/bin/env python3
"""PostToolUse failure-logger for the carcassonne project.

Passive, zero-risk: after any tool runs, if the result looks like a FAILURE,
append a compact line to .claude/tool_failures.jsonl. Mine that small log
instead of re-chewing 645 MB of raw transcripts. Always exits 0 (never blocks).

Contract (Claude Code PostToolUse):
  - stdin = JSON {tool_name, tool_input, tool_response, cwd, ...}
  - tool_response shape varies; we sniff several failure signals defensively.

Note: some harness-level validation errors (e.g. "File has not been read yet",
parallel-ssh cancellation) may short-circuit before PostToolUse fires — those
still need occasional transcript mining. Bash nonzero/error-output is captured.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent.parent / ".claude" / "tool_failures.jsonl"

ERROR_SIGS = (
    "tool_use_error", "has not been read yet", "modified since read",
    "No such file", "command not found", "Cancelled: parallel",
    "Traceback (most recent call last)", "Permission denied", "cannot access",
    "cannot stat", "unexpected EOF",
)
# commands that exit nonzero ON PURPOSE — don't log these as failures
INTENTIONAL = ("pkill", "pgrep", "|| true", "|| echo", "kill -0", "grep -q")


def _resp_text(resp) -> str:
    if isinstance(resp, str):
        return resp
    try:
        return json.dumps(resp)
    except Exception:
        return str(resp)


def _is_failure(resp) -> tuple[bool, str]:
    """(failed, short_signature)."""
    if isinstance(resp, dict):
        if resp.get("is_error"):
            return True, "is_error"
        for k in ("exit_code", "returnCode", "code", "exitCode"):
            v = resp.get(k)
            if isinstance(v, int) and v != 0:
                return True, f"exit={v}"
    text = _resp_text(resp)
    for sig in ERROR_SIGS:
        if sig in text:
            return True, sig
    return False, ""


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return 0
    tool = data.get("tool_name", "?")
    tin = data.get("tool_input") or {}
    cmd = tin.get("command", "") if isinstance(tin, dict) else ""
    resp = data.get("tool_response")

    failed, sig = _is_failure(resp)
    if not failed:
        return 0
    # skip intentional nonzero exits (kills, guarded greps)
    if cmd and any(w in cmd for w in INTENTIONAL) and sig.startswith("exit"):
        return 0

    # one-line error excerpt
    text = _resp_text(resp)
    excerpt = ""
    for line in text.splitlines():
        line = line.strip()
        if line and any(s in line for s in ERROR_SIGS) or "rror" in line:
            excerpt = line[:200]
            break
    if not excerpt:
        excerpt = text[:200]

    rec = {
        "ts": time.time(), "kind": "post_failure", "tool": tool,
        "sig": sig, "cmd": (cmd or "")[:500], "excerpt": excerpt,
        "cwd": data.get("cwd", ""),
    }
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
