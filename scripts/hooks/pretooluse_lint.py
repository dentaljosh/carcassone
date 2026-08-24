#!/usr/bin/env python3
"""PreToolUse lint hook for the carcassonne project (Bash + Read).

Catches the mechanically-checkable failure modes the 2026-06-02 transcript
audit found recurring. PROJECT-SCOPED: registered in this project's
.claude/settings.local.json (matcher `Bash|Read`), so it only fires here.

Contract (Claude Code PreToolUse):
  - stdin = JSON {tool_name, tool_input:{command,...}, cwd, ...}
  - exit 2  -> BLOCK the tool; stderr is fed back to Claude (the only reliable
               model-facing channel, so blocks are reserved for always-wrong cases)
  - exit 0  -> allow; advisories go to stderr + the lint log (non-blocking)
  - FAIL-OPEN: any internal error -> exit 0 (never break a tool over a lint bug)

Read handling (the 2026-06-19 context-discipline add): a whole-file `Read`
(no offset/limit) of a large source-of-truth file (results.csv ~90KB, the
governance CSVs, any >50KB doc) is the #1 avoidable context cost behind the
"context fills to 400K fast" problem — advise grep/offset. Advisory only.

Block-message design (the 2026-06-23 cd-loop fix): when a block has a single
mechanical fix, the message hands over the CORRECTED command verbatim ("copy
this line") rather than describing the fix. The model's failure mode is
rebuilding the command from memory on each retry and re-dropping the same token
(the cd got dropped 6x in a row, 2026-06-23) — a paste-ready string defeats that
where an instruction does not. A loop-breaker (see _recent_block_count) escalates
loudly once the same error class has fired repeatedly in a short window.

Escape hatches (put in the command): `# nolint` (skip all), `# allow-sleep`,
`# allow-path`, `# allow-doclint`, `# allow-nocd`, and
`# allow-freeze: <reason>` (the W-FREEZE-LATCH — REASON MANDATORY). For Read, pass an explicit
`limit` to read a known-large file whole on purpose (suppresses the nudge).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

REPO = "/home/doctor/projects/carcassone"
LOG = Path(__file__).resolve().parent.parent.parent / ".claude" / "tool_failures.jsonl"


def _log(rec: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _recent_block_count(signature: str, window_s: int = 900) -> int:
    """How many times a block whose reason contains `signature` has fired in the
    last `window_s` seconds (scan the tail of the block log). Used as a loop-
    breaker: a repeat means the model is re-sending a near-identical broken
    command and needs a louder, switch-tactics nudge. Fail-open -> 0."""
    try:
        if not LOG.exists():
            return 0
        now = time.time()
        count = 0
        with open(LOG) as f:
            tail = f.readlines()[-80:]
        for ln in tail:
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            if rec.get("kind") != "pre_block":
                continue
            if now - float(rec.get("ts", 0)) > window_s:
                continue
            if any(signature in r for r in rec.get("reasons", [])):
                count += 1
        return count
    except Exception:
        return 0


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


def _ssh_remote_no_cd(cmd: str) -> str | None:
    """A remote `ssh <host> '<inner>'` whose inner command is repo-relative
    (git / python / scripts / pytest / .venv) but has NO path-stable addressing —
    no `cd`, no `git -C`, no `bash -s` script, and the absolute repo path doesn't
    appear. The remote shell lands in $HOME, so it fails ('not a git repository' /
    'No such file'). Always-wrong -> block. NB: Claude Code drops an inline
    `cd /path &&` from SSH commands at generation time (known failure mode, proven
    2026-06-23 — a plain non-ssh echo drops it too), so the message recommends
    PATH-STABLE forms (git -C, absolute paths, wrapper script), NOT an inline cd."""
    m_ssh = re.search(r"\bssh\b", cmd)
    if not m_ssh:
        return None
    after = cmd[m_ssh.end():]
    # the piped-script pattern (`ssh host 'bash -s' < file`) carries its own cd
    # inside the file -> always OK.
    if "bash -s" in after:
        return None
    # the remote command is the first quoted arg after ssh
    m = re.search(r"""(['"])(.*?)\1""", after, re.S)
    if not m:
        return None  # no quoted remote cmd (interactive ssh / -O etc.) -> skip
    inner = m.group(2).strip()
    # path-stable forms -> no cd needed -> fine:
    #  - explicit cd/pushd, or git -C / --git-dir
    #  - the absolute repo path appears (python /abs/x.py, --manifest-path /abs/..,
    #    docker -f /abs/.., a wrapper /abs/x.sh) -> not $HOME-relative
    if re.search(r"\bcd\s+\S", inner) or re.search(r"\bpushd\b", inner):
        return None
    if re.search(r"\bgit\s+(-C|--git-dir)\b", inner):
        return None
    if REPO in inner:
        return None
    # repo-relative op that needs the repo CWD?
    if re.search(r"(^|;|&&|\|\|?|\bnice\s+-n\s+\d+\s+)\s*"
                 r"(git|python3?|\.?/?scripts/|bash\s+scripts/|\.venv/|pytest)\b", inner):
        snippet = inner[:48].replace("\n", " ")
        return ("remote `ssh … '" + snippet + "…'` runs a repo-relative command with no path-"
                "stable addressing — it lands in $HOME and fails. NOTE: Claude Code silently "
                "drops an inline `cd /path &&` from SSH commands (known failure mode), so do NOT "
                "use cd. Use a PATH-STABLE form:\n"
                "    git:    ssh <host> 'git -C " + REPO + " <subcmd>'\n"
                "    python: ssh <host> '" + REPO + "/.venv/bin/python " + REPO + "/scripts/x.py'  (abs paths)\n"
                "    multi:  a wrapper that cd's itself —  ssh <host> '" + REPO + "/scripts/x.sh'\n"
                "            (or  ssh <host> 'bash -s' < /tmp/x.sh  with cd on line 1)\n"
                "  (Override: add `# allow-nocd`.)")
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


# A whole-file Read above this size is worth a grep/offset nudge (~12.5K tokens).
_LARGE_READ_BYTES = 50_000


def _large_whole_read(data: dict) -> str | None:
    """A `Read` with neither offset nor limit pulls the whole file (up to the
    harness ~25K-token cap) into context. For the big source-of-truth files
    (results.csv ~90KB, the governance CSVs, DECISIONS.md) that's ~10-25K tokens
    you almost never need whole — grep the row/section instead. The empirical
    driver of the 2026-06-19 "context fills to 400K fast" finding. Advisory only
    (whole reads are sometimes legitimate; an explicit `limit` suppresses this)."""
    ti = data.get("tool_input") or {}
    if ti.get("offset") is not None or ti.get("limit") is not None:
        return None  # already a targeted read
    fp = ti.get("file_path") or ""
    if not fp:
        return None
    try:
        sz = Path(fp).stat().st_size
    except Exception:
        return None  # missing / unstat-able -> let Read report it
    if sz < _LARGE_READ_BYTES:
        return None
    name = Path(fp).name
    how = (f"grep the specific row(s) (`grep <key> {name}`)" if name.endswith(".csv")
           else "grep the section, or Read with offset/limit")
    return (f"Reading {name} whole (~{sz // 1024} KB ≈ {sz // 4000}K tokens) — {how}. "
            f"Whole-file reads of the big source-of-truth files are the #1 avoidable "
            f"context cost (the 400K-context problem). "
            f"(Need it all? pass an explicit large `limit` to suppress this.)")


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


# --------------------------------------------------------------------------- #
# W-FREEZE-LATCH — refuse a MAIN-TREE commit while a scoring leg is live        #
#                                                                              #
# ⭐ Ruled by DEVIATIONS D5 (b) (`3b7cd11a`). The B64 aggregator commit was      #
# merged to main while rung-3's local scoring leg was live — the same class     #
# that voided the first JCZ run, and the direct cause of R5's two-rev split.    #
# The mitigation (the instrument diff happened to be empty) is a WITNESSED      #
# FACT, NOT AN EXCUSE: it was LUCK, NOT DESIGN, because nothing about the merge #
# checked whether a leg was live. Had the commit touched rust/, src/ or         #
# scripts/tiletie/, chunks 3-5 would have been UNRECOVERABLE.                   #
#                                                                              #
# ⚠️ The discipline has now failed TWICE and BOTH times at the ORCHESTRATOR's   #
# hands, not a builder's or an executor's. "We checked afterwards and it was    #
# fine" is not a control — a convention that has failed twice at the same hands #
# is a hook's job.                                                             #
# --------------------------------------------------------------------------- #
#: Dropped by the launchers at leg start and cleared at close-out (and on trap).
RUN_LIVE_NAME = "RUN_LIVE.json"


def _live_sentinels(repo=None) -> list:
    """Every live-leg sentinel under `measurement/`. On-disk, so it is visible
    to WHOEVER commits — the latch is orchestrator-proof by construction.

    ⚠️ `repo` is resolved LATE (module global, not a default-arg binding) so the
    root stays overridable — a default-arg would freeze it at import."""
    root = Path(repo if repo is not None else REPO) / "measurement"
    if not root.is_dir():
        return []
    try:
        return sorted(str(p) for p in root.glob("**/" + RUN_LIVE_NAME))
    except OSError:
        return []


# Git subcommands that create or rewrite a commit on the checked-out tree.
# An explicit allow-list (not "the text contains commit somewhere") so BYPASS
# classes that don't literally say "commit" -- merge, cherry-pick, rebase,
# commit-tree, pull (its merge/rebase side) -- latch too.
_COMMIT_CREATING_GIT_SUBCOMMANDS = {
    "commit", "merge", "cherry-pick", "rebase", "commit-tree", "pull",
}

# A heredoc marker -- `<<'EOF'`, `<<-EOF`, `<<"TAG"` -- captured so the BODY
# text (stdin payload, never itself executed as a shell command) can be
# dropped before we go hunting for a git invocation. A scratchpad write whose
# heredoc body happens to mention a git verb must never trip the latch.
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")

# A leading `FOO=bar` env-var assignment ahead of the actual program name,
# e.g. `GIT_AUTHOR_DATE=... git commit ...`.
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# git global options that consume a SEPARATE following token as their
# argument (as opposed to a self-contained `--opt=value`).
_GIT_ARG_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def _strip_heredoc_bodies(cmd: str) -> str:
    """Drop heredoc BODY lines (stdin payload, not shell commands) so their
    text can never be mistaken for an invocation. Keeps the marker line
    itself (`cat <<'EOF' > /tmp/x.sh`) so anything genuinely chained on a
    later line is still visible to the segment scan below."""
    lines = cmd.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = _HEREDOC_RE.search(line)
        if not m:
            i += 1
            continue
        delim = m.group(2)
        i += 1
        while i < len(lines) and lines[i].strip() != delim:
            i += 1
        if i < len(lines):  # skip the terminator line itself too
            i += 1
    return "\n".join(out)


def _split_pipeline(cmd: str) -> list[str]:
    """Split into segments at top-level `&&`, `||`, `;`, `|`, `&`, newline --
    but NEVER inside a quoted string, so a quoted grep pattern (or any other
    argument) that happens to contain one of these characters, or the words
    `git`/`commit`, is never split apart or surfaced as a leading word."""
    segments: list[str] = []
    buf: list[str] = []
    i, n = 0, len(cmd)
    in_squote = in_dquote = False
    while i < n:
        c = cmd[i]
        if in_squote:
            buf.append(c)
            in_squote = c != "'"
            i += 1
            continue
        if in_dquote:
            if c == "\\" and i + 1 < n:
                buf.append(c); buf.append(cmd[i + 1])
                i += 2
                continue
            buf.append(c)
            if c == '"':
                in_dquote = False
            i += 1
            continue
        if c == "'":
            in_squote = True
            buf.append(c); i += 1; continue
        if c == '"':
            in_dquote = True
            buf.append(c); i += 1; continue
        if c == "\\" and i + 1 < n:
            buf.append(c); buf.append(cmd[i + 1]); i += 2; continue
        if cmd[i:i + 2] in ("&&", "||"):
            segments.append("".join(buf)); buf = []; i += 2; continue
        if c in (";", "|", "&", "\n"):
            segments.append("".join(buf)); buf = []; i += 1; continue
        buf.append(c); i += 1
    segments.append("".join(buf))
    return segments


def _git_invocation(tokens: list[str]) -> tuple[str, str | None] | None:
    """`tokens` = one already-tokenized pipeline segment. If it's an actual
    git invocation (leading env-assignments skipped, matched on the PROGRAM
    NAME, not substring), return `(subcommand, dash_C_target)` -- subcommand
    is "" if `git` was invoked with no subcommand. Else None (not git)."""
    i = 0
    while i < len(tokens) and _ENV_ASSIGN_RE.match(tokens[i]):
        i += 1
    if i >= len(tokens) or os.path.basename(tokens[i]) != "git":
        return None
    i += 1
    target = None
    while i < len(tokens):
        t = tokens[i]
        if not t.startswith("-"):
            return t, target  # first non-option token = the subcommand
        if t in _GIT_ARG_OPTS:
            if t == "-C" and i + 1 < len(tokens):
                target = tokens[i + 1]
            i += 2
            continue
        i += 1  # a self-contained flag (-p, --no-pager, --opt=value, ...)
    return "", target  # bare `git` (+ options only), no subcommand


def _is_main_tree_commit(cmd: str, cwd: str | None) -> bool:
    """A commit-CREATING git invocation (commit / merge / cherry-pick /
    rebase / commit-tree / pull) that lands on the MAIN tree. A commit inside
    a git worktree is exactly the safe pattern this project already mandates
    for live trees, so it is never latched.

    Matches by TOKENIZING each pipeline segment's leading words (env-var
    prefixes skipped, `&&`/`;`/`|`/`&`/newline segment splits, heredoc BODIES
    dropped first) rather than by substring/regex search over the whole
    command text. That means: (a) commit-creating verbs a
    `git ... commit`-shaped regex would miss (merge, cherry-pick, rebase,
    commit-tree, pull) are now caught, and (b) a read-only command that
    merely CONTAINS the trigger phrase in a quoted argument, or a heredoc
    payload that mentions a git verb in its body text, never fires -- only an
    actual leading `git <subcmd>` process invocation does."""
    stripped = _strip_heredoc_bodies(cmd)
    for segment in _split_pipeline(stripped):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            continue  # unbalanced quote in this segment -> not ours to parse
        inv = _git_invocation(tokens)
        if inv is None:
            continue
        subcommand, dash_c_target = inv
        if subcommand not in _COMMIT_CREATING_GIT_SUBCOMMANDS:
            continue
        target = dash_c_target if dash_c_target is not None else (cwd or "")
        if "/.claude/worktrees/" not in str(target):
            return True
    return False


def _freeze_latch(cmd: str, cwd: str | None) -> str | None:
    if not _is_main_tree_commit(cmd, cwd):
        return None
    live = _live_sentinels()
    if not live:
        return None
    return (
        "⛔ W-FREEZE-LATCH: a scoring leg is LIVE and this is a MAIN-TREE commit.\n"
        "   live sentinel(s): " + ", ".join(live[:4])
        + ("" if len(live) <= 4 else f" (+{len(live) - 4} more)") + "\n"
        "   Committing to main while a leg runs is what caused R5's two-rev "
        "split (DEVIATIONS D5 (b)): spawn respawns and each new --shared-claim "
        "cell RE-IMPORT FROM DISK, so a mid-run commit can put two revisions "
        "into one run. That it was harmless last time was LUCK, NOT DESIGN.\n"
        "   Do this instead: commit in a git worktree "
        "(agents: isolation=\"worktree\") and merge at a quiet window.\n"
        "   Override (LAST RESORT, REASON MANDATORY): add "
        "`# allow-freeze: <why this cannot wait>` to the command. "
        "`# allow-freeze` with no reason does NOT override.")


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        return 0
    tool = data.get("tool_name")
    if tool == "Read":
        adv = _large_whole_read(data)
        if adv:
            _log({"ts": time.time(), "kind": "pre_advisory_read",
                  "path": (data.get("tool_input") or {}).get("file_path"),
                  "advisory": adv})
            print("PreToolUse lint (advisory, not blocking):\n- " + adv, file=sys.stderr)
        return 0
    if tool != "Bash":
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
    if "# allow-nocd" not in cmd:
        n = _ssh_remote_no_cd(cmd)
        if n:
            blocks.append(n)
    if "# allow-doclint" not in cmd:
        d = _doclint_on_commit(cmd)
        if d:
            blocks.append(d)
    # ⚠️ THE REASON IS MANDATORY: a bare `# allow-freeze` does not override, so
    # the override cannot be muscle-memory — it has to be an argument.
    if not re.search(r"#\s*allow-freeze\s*:\s*\S", cmd):
        f = _freeze_latch(cmd, data.get("cwd"))
        if f:
            blocks.append(f)

    if blocks:
        msg = "PreToolUse lint blocked this command:\n- " + "\n- ".join(blocks)
        # Loop-breaker: if this SAME class of block has already fired repeatedly in
        # a short window, the model is re-sending a near-identical broken command
        # (the 2026-06-23 cd-thrash). Escalate loudly so it switches tactic — copy
        # the corrected line / pipe a script — instead of retyping the same string.
        sig = "path-stable" if any("path-stable" in b for b in blocks) else None
        if sig:
            prior = _recent_block_count(sig)
            if prior >= 2:
                msg = (f"⛔ REPEAT BLOCK ({prior + 1}x in 15min) — Claude Code drops the inline "
                       f"`cd` from SSH at generation; retrying it will NEVER work. STOP using cd. "
                       f"Use a PATH-STABLE form: `git -C " + REPO + " ..`, absolute python paths "
                       f"(`" + REPO + "/.venv/bin/python " + REPO + "/scripts/x.py`), or a wrapper "
                       f"`ssh <host> '" + REPO + "/scripts/x.sh'`.\n\n" + msg)
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
