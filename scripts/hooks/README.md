# Project hooks (carcassonne, 5800x dev box)

Real-time guards for the recurring failure modes the 2026-06-02 transcript audit
found (see BACKLOG.md "PreToolUse failure-mode hook" + DECISIONS.md). **CLAUDE.md-as-code**
for the mechanically-checkable subset.

## Scripts (tracked here)
- `pretooluse_lint.py` — fires before every **Bash** call. **Blocks** (exit 2):
  foreground `sleep ≥10s` (use Monitor/`run_in_background`), and the two unambiguous
  CIFS mount-path misuses (`/mnt/c/carc-shared` vs `/mnt/carc-shared`). **Advises**
  (non-blocking): `--seed-start` without `--shared-claim`, backgrounded python without
  nohup/setsid, cluster launch without `nice -n 19`. Escape hatches in the command:
  `# nolint`, `# allow-sleep`, `# allow-path`. **Fail-open** (any bug → exit 0).
- `posttooluse_log.py` — fires after Bash/Edit/Write/Read/etc. Appends real failures to
  `.claude/tool_failures.jsonl` (skips intentional nonzero exits like `pkill`). Passive,
  always exit 0. Mine that small log instead of re-chewing GB of transcripts.

## Registration (NOT tracked — `.claude/` is gitignored)
Hooks live in **`.claude/settings.local.json`** (project-scoped → fire only in this dir;
kept out of the permission-bearing `settings.json` so the self-modification guard allows it).
To recreate on a fresh checkout, create `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash",
       "hooks": [{"type": "command", "command": "python3 /home/doctor/projects/carcassone/scripts/hooks/pretooluse_lint.py"}]}
    ],
    "PostToolUse": [
      {"matcher": "Bash|Edit|Write|Read|MultiEdit|NotebookEdit",
       "hooks": [{"type": "command", "command": "python3 /home/doctor/projects/carcassone/scripts/hooks/posttooluse_log.py"}]}
    ]
  }
}
```

Hooks load at session start. Mine failures with:
`python3 -c "import json;from collections import Counter;c=Counter(json.loads(l).get('sig') or json.loads(l).get('kind') for l in open('.claude/tool_failures.jsonl'));print(c)"`
