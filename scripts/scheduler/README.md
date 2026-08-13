# Measurement work-queue scheduler

**Status: ✅ ARMED 2026-08-13.** Chain detached on the local box, cron watchdog on 10-min
ticks. Live state: `measurement/scheduler_20260813/state.json`; live log:
`measurement/scheduler_20260813/logs/scheduler.log`.

Launches queued measurement work as boxes free up, so a box that finishes at 03:00 does not
idle until a human notices. (~8 idle box-hours were lost exactly that way on 2026-08-12.)

| File | What it is |
|---|---|
| [queue.json](queue.json) | **The queue — data, not logic.** Boxes + items. Edit this to add/reorder/remove work. |
| [queue_lib.py](queue_lib.py) | Every decision (dispatchable? box free? how many workers?). Stdlib only. |
| [work_queue.sh](work_queue.sh) | The chain: poll → census → dispatch detached → repeat. |
| [work_queue_watchdog.sh](work_queue_watchdog.sh) | Cron tick that restarts the chain if it dies (reboot-safe). |
| [../../tests/test_scheduler_queue.py](../../tests/test_scheduler_queue.py) | 45 tests pinning the safety rules below. |

Runtime dir (state, logs, markers, generated dispatch wrappers):
`measurement/scheduler_20260813/`.

## Safety rules (non-negotiable, test-pinned)

- **Never** edits `governance/PRODUCTION.yaml`, never adjudicates, never claims a band. It
  *reads* `governance/BAND_REGISTRY.csv` only to refuse work whose band is not already claimed.
- **Never** launches anything that plays games unless a pre-registered prereg file **and** a
  claimed band are both on disk. Otherwise: `BLOCKED: prereg/band missing`, and it moves on.
- **Never** two jobs on one box. **Never** the laptop before its occupant's DONE marker exists.
- **Census guard before every dispatch:** a DONE marker can lie (a watchdog may have relaunched
  the occupant), so the target box's live process count must be zero, checked by `ps`/`pgrep`
  locally and over `ssh` remotely. An unreachable box **fails closed** (treated as busy).
- An item whose code is still in an unmerged worktree is `NEEDS_MERGE`: the scheduler emits a
  notice for a human/orchestrator and never merges, never rebuilds, never runs it.
- A `FAILED` item is terminal. The scheduler logs loudly and moves on; it does not retry.

## Queue format

`queue.json` has two keys: `boxes` and `items`.

### `boxes`

```jsonc
"local": {
  "host": "local",                       // "local", or an ssh alias for a remote box
  "occupant_label": "tile-tie Stage B",  // what is on the box now (for the log)
  "occupant_markers": [                  // ANY of these existing => the occupant is finished
    "measurement/tiletie_pricing_20260812/DONE_STAGEB",
    "measurement/tiletie_pricing_20260812/FAILED_STAGEB"
  ],                                     // globs allowed; repo-relative or absolute
  "census_patterns": ["…/.venv/bin/python"],  // pgrep -f regexes; any match => box busy
  "allow_idle_release": true,            // see "idle release" below
  "idle_release_secs": 2700,
  "workers_schedule": [                  // wall-clock worker grant, first match wins;
    {"before_hhmm": "11:00", "w": 30},   // the LAST entry must have no before_hhmm
    {"w": 14}
  ],
  "marker_dir_local": "measurement/scheduler_20260813/markers",
  "bundle_sync": false                   // remote boxes: git-bundle sync before launch
}
```

Remote boxes additionally take `marker_dir_remote` (the same directory as the box sees it —
markers live on the share so the local scheduler can poll them without an ssh per tick),
`share_local` / `share_remote`, and `mem_max` (a `systemd-run --user --scope -p MemoryMax=`
cap; the laptop VM is ~11 GB and an uncapped guest is the documented WSL teardown mechanism).

**Idle release.** A box is normally free only once an occupant marker exists. If
`allow_idle_release` is true and the occupant marker *never appears* while the box stays
census-clean for `idle_release_secs`, the box is released with a loud `IDLE-RELEASE` log line
— this covers "the occupant was never funded / died without a marker". The laptop has it
**off** by owner instruction. Any live process resets the idle clock.

### `items`

```jsonc
{
  "id": "window_truncation_census",      // unique; names the DONE_/FAILED_ markers and the log
  "priority": 10,                        // LOWER RUNS FIRST
  "box": "local",                        // "local" | "laptop" | "any"
  "prefer_box": "laptop",                // with box:"any", try this one first
  "dir": "measurement/window_truncation_20260813",   // must exist, else NOT_READY
  "launch_cmd": ["…/RUN_CMD.sh", "…/run_census.sh"], // first EXISTING candidate wins
  "plays_games": false,                  // true => prereg + band are hard requirements
  "prereg": "…/PREREG.md",
  "band": "1.24e11",                     // must appear in governance/BAND_REGISTRY.csv
  "merge_probe_paths": ["…/DESIGN.md"],  // all must exist in the MAIN tree, else NEEDS_MERGE
  "merge_note": "…",                     // appended to the merge notice
  "done_if_exists": ["…/READOUT.md"],    // the item already ran itself => skip
  "log": "…/logs/scheduler_run.log",
  "note": "free text"
}
```

**The launch-command contract.** The scheduler *consumes* a ready-to-launch, priced command
that the item's own designer landed — it never invents an invocation. The command must exist
and be executable (a non-`+x` `.sh` is accepted and run via `bash`, with a note). It is invoked
as `bash <launch_cmd> <W>` with `SCHED_W`, `SCHED_BOX`, `SCHED_JOB_ID` and `SCHED_LOG` exported,
so honour `"${SCHED_W:-14}"` or `$1` for worker count. If no candidate has landed yet, the item
is `NOT_READY` and is skipped with a loud log line — siblings may land their command after the
scheduler is already running, and it will pick it up on the next tick with no restart.

**Statuses** (in the log and in `state.json`): `DONE` · `FAILED` · `DISPATCHED` (in flight)
· `NEEDS_MERGE` · `BLOCKED` (prereg/band) · `NOT_READY` (command/dir not landed) ·
`WAIT_BOX` (dispatchable, waiting for a box) · `READY`.

## How to …

```bash
cd /home/doctor/projects/carcassone

# ADD OR REORDER AN ITEM  -- edit the data, never the shell, then validate:
$EDITOR scripts/scheduler/queue.json
python3 scripts/scheduler/queue_lib.py validate
#   the running scheduler re-reads queue.json every tick — no restart needed.
#   (An invalid queue makes the tick a no-op with a loud TICK ERROR line rather
#    than dispatching anything; it recovers by itself once the file parses. So
#    validate before you walk away — a broken queue costs box-hours, not safety.)

# REMOVE AN ITEM: delete its object, or set its priority to 999 to park it.

# SEE WHAT THE QUEUE DID / WHAT IS PENDING
cat measurement/scheduler_20260813/state.json
tail -40 measurement/scheduler_20260813/logs/scheduler.log

# STOP THE WHOLE QUEUE (graceful; the watchdog will NOT restart it)
touch measurement/scheduler_20260813/STOP

# RESUME
rm measurement/scheduler_20260813/STOP     # the cron watchdog relaunches within 10 min

# RESTART BY HAND
setsid nohup nice -n 19 bash scripts/scheduler/work_queue.sh \
  >> measurement/scheduler_20260813/logs/chain.log 2>&1 & disown

# DRY-RUN ONE TICK (safe: it will dispatch if something is genuinely dispatchable)
SCHED_ONCE=1 bash scripts/scheduler/work_queue.sh

# TESTS
.venv/bin/python -m pytest tests/test_scheduler_queue.py -q
bash -n scripts/scheduler/work_queue.sh scripts/scheduler/work_queue_watchdog.sh
```

Env overrides: `SCHED_QUEUE`, `SCHED_POLL_SECS` (300), `SCHED_MAX_HOURS` (72, then it exits and
the watchdog starts a fresh one), `SCHED_PY` (`python3`), `SCHED_ONCE`, `SCHED_RUN_DIR` (state
/ lock / marker tree — only for smoke-testing the dispatch path off to one side).

⚠️ A `SCHED_ONCE` smoke run shares the chain's process name, so the cron watchdog can read
"chain alive" while the real chain is down. Don't leave a smoke running unattended, and check
`pgrep -af 'scheduler/work_queue\.sh'` if the watchdog log looks too quiet.

## Remote launch mechanics (laptop)

Per house rules, a laptop dispatch: (1) cuts a **git bundle** onto the share — incremental when
the laptop's HEAD is already in our history, full otherwise, skipped entirely when the laptop is
already at HEAD — because remotes cannot reach github and stale code means a contaminated cell;
(2) **pipes a real script** (`ssh laptop-wsl 'bash -s' < file`, `cd` on line 1) because the
inline `ssh host 'cd … && …'` form gets the `cd` stripped in transit; (3) guards against WSL
clock drift (>300 s vs the bundle mtime aborts); (4) `git fetch` + `git reset --hard FETCH_HEAD`
and an import check; (5) launches the job detached under
`systemd-run --user --scope -p MemoryMax=8G`. Markers are written to the share so the local
scheduler polls them with no per-tick ssh.
