#!/usr/bin/env python3
"""PreToolUse lint hook for the carcassonne project (Bash only).

Catches the mechanically-checkable failure modes the 2026-06-02 transcript
audit found recurring. PROJECT-SCOPED: registered in this project's
.claude/settings.json, so it only fires here.

Contract (Claude Code PreToolUse):
  - stdin = JSON {tool_name, tool_input:{command,...}, cwd, ...}
  - exit 2  -> BLOCK the tool; stderr is fed back to Claude (the only reliable
               model-facing channel, so blocks are reserved for always-wrong cases)
  - exit 0  -> allow; advisories go to stderr + the lint log (non-blocking)
  - FAIL-OPEN: any internal error -> exit 0 (never break a tool over a lint bug)

Escape hatches (put in the command): `# nolint` (skip all), `# allow-sleep`,
`# allow-path`, `# allow-doclint`.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent.parent / ".claude" / "tool_failures.jsonl"


def _log(rec: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _foreground_sleep_ge(cmd: str, thresh: int = 10) -> float | None:
    """Return the largest foreground `sleep N` value >= thresh, else None.
    Short poll sleeps (< thresh) in `until ...; do sleep 2; done` are fine."""
    worst = None
    for m in re.finditer(r"(?<![\w.])sleep\s+(\d+(?:\.\d+)?)", cmd):
        val = float(m.group(1))
        if val < thresh:
            continue
        # backgrounded? (`sleep 600 &`) — look at what follows the number
        rest = cmd[m.end():].lstrip()
        if rest.startswith("&") and not rest.startswith("&&"):
            continue
        worst = val if worst is None else max(worst, val)
    return worst


def _cifs_mismatch(cmd: str) -> str | None:
    """The share is /mnt/c/carc-shared on the 5800x (where this hook runs) but
    /mnt/carc-shared on laptop/xeon. Catch the two unambiguous misuses."""
    has_remote = bool(re.search(r"\bssh\b", cmd)) and ("xeon" in cmd or "laptop" in cmd)
    # local command using the REMOTE mount path
    if not has_remote and "/mnt/carc-shared" in cmd:
        return ("local command uses '/mnt/carc-shared' — on the 5800x the share "
                "is '/mnt/c/carc-shared'. (Remote boxes use /mnt/carc-shared.)")
    # ssh-to-remote command using the LOCAL mount path
    if has_remote and "/mnt/c/carc-shared" in cmd:
        return ("ssh-to-remote command uses '/mnt/c/carc-shared' — laptop/xeon "
                "mount the share at '/mnt/carc-shared'.")
    return None


def _doclint_on_commit(cmd: str) -> str | None:
    """On `git commit`, run the doc linter in errors-only mode on STAGED files.
    Blocks ONLY on E-class findings (broken links / tracked-doc -> untracked-file),
    which are always-wrong and cheap to fix — exactly the class that broke the
    COMPACT_LEAF plan link on every remote clone (2026-06-12 review). Warnings
    (status banners, stale markers) never block. Override: `# allow-doclint`."""
    if not re.search(r"\bgit\b[^|;&]*\bcommit\b", cmd):
        return None
    import subprocess
    lint = Path(__file__).resolve().parent.parent / "doc_lint.py"
    if not lint.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(lint), "--staged", "--errors-only"],
            capture_output=True, text=True, timeout=30)
    except Exception:
        return None  # fail-open
    if r.returncode == 2:
        return ("doc_lint found broken/untracked links in STAGED docs (these break on "
                "every clone/remote):\n" + r.stdout.strip() +
                "\nFix the link or `git add` the target. (Override: add `# allow-doclint`.)")
    return None


def _advisories(cmd: str) -> list[str]:
    out = []
    is_evalish = any(s in cmd for s in (
        "eval_iter_head_to_head", "eval_net_vs_heuristic", "run_selfplay"))
    # close-out nudge: a results.csv / PRODUCTION.yaml write usually means an
    # experiment just concluded — remind the 5-touch close-out (CLAUDE.md norm).
    if re.search(r"(results\.csv|PRODUCTION\.yaml)", cmd) and re.search(
            r"(>>|\bsed -i\b|\btee -a\b|append)", cmd):
        out.append("experiment concluding? run the close-out checklist: results.csv row -> "
                   "DECISIONS index line -> spec-doc status stamp -> governance row flip -> "
                   "STATUS top block (then `python3 scripts/doc_lint.py`).")
    if is_evalish and "--seed-start" in cmd and "--shared-claim" not in cmd:
        out.append("multi-box? prefer --shared-claim (work-stealing) over disjoint "
                   "--seed-start shards so idle boxes pull the tail.")
    # backgrounded python without a detach wrapper
    if re.search(r"python3?\b.*&\s*$", cmd) or re.search(r"python3?\b.*&\s*disown", cmd):
        if not any(w in cmd for w in ("nohup", "setsid", "disown")):
            out.append("backgrounded python without nohup/setsid/disown — Mac-sleep "
                       "SIGHUP / WSL teardown will kill it; detach it.")
    # cluster worker launch without nice
    if is_evalish and "nice " not in cmd:
        out.append("cluster worker without `nice -n 19` — production workers should yield.")
    return out


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    if "# nolint" in cmd:
        return 0

    blocks: list[str] = []
    if "# allow-sleep" not in cmd:
        s = _foreground_sleep_ge(cmd)
        if s is not None:
            blocks.append(
                f"Foreground `sleep {s:g}` (>=10s). Don't block-poll. Use the "
                f"Monitor tool with an until-loop, or run_in_background=true and "
                f"wait for the completion notification. (Override: add `# allow-sleep`.)")
    if "# allow-path" not in cmd:
        c = _cifs_mismatch(cmd)
        if c:
            blocks.append(f"CIFS path mismatch: {c} (Override: add `# allow-path`.)")
    if "# allow-doclint" not in cmd:
        d = _doclint_on_commit(cmd)
        if d:
            blocks.append(d)

    if blocks:
        msg = "PreToolUse lint blocked this command:\n- " + "\n- ".join(blocks)
        _log({"ts": time.time(), "kind": "pre_block", "cmd": cmd[:500],
              "reasons": blocks})
        print(msg, file=sys.stderr)
        return 2

    adv = _advisories(cmd)
    if adv:
        _log({"ts": time.time(), "kind": "pre_advisory", "cmd": cmd[:500],
              "advisories": adv})
        print("PreToolUse lint (advisory, not blocking):\n- " + "\n- ".join(adv),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open: never break a tool over a lint bug
