# ⛔⛔ FREEZE.md — THE TOTAL COMMIT FREEZE FOR `jcz_tiearb_20260817`

> **Read this before you touch this repository while the JCZ tie-arbiter cells are live.**
> It is the operational rule that the voided 2026-08-17 run did not have. It is not a bar,
> it moves no gate, and it is not open to interpretation.

---

## THE RULE, VERBATIM

> **TOTAL COMMIT FREEZE.** From the moment the band is claimed until the fourth
> `DONE_<cell>_<host>_<BAND_TAG>` marker exists, **NO COMMIT MAY LAND IN THIS REPOSITORY —
> none, of any kind, including docs, `measurement/`, `android/`, and README typos.**
>
> Why: `scripts/jcz_match/match.py` stamps `our_git_rev` **per record at record-write time**,
> so *any* commit moves HEAD and splits a cell's records across revisions. `G-TOOL` conjunct 2
> requires `our_git_rev` to be *"equal across CELL A and CELL B, and consistent within each cell
> (no mixed-rev cell)"*. It is violated by **any** commit, wheel-relevant or not.
>
> The 2026-08-17 run was VOIDED by exactly this: a freeze scoped to wheel-relevant paths only
> (`rust/ src/ engine/ scripts/`) let two docs-only commits land, producing 3 distinct revs in one
> cell and 2 in the other. The empty wheel-relevant diff did **not** rescue it — no committed text
> makes an empty diff dispositive in the passing direction. See `DISCLOSURE.md` §3.

---

## WHEN THE FREEZE IS ON

| | |
|---|---|
| **STARTS** | the instant `claim_band.sh` appends the band row to `governance/BAND_REGISTRY.csv` — i.e. step 4 of `launch.sh`, which is also when `$RUN_DIR/FREEZE_HEAD` is written |
| **ENDS** | when **all four** of these exist (`DONE`, not `FAILED`): |
| | `DONE_jcz_CHAMP_deploy11008_Doctor_b134` |
| | `DONE_jcz_ARB_B16J4_deploy11008_Doctor_b134` |
| | `DONE_jcz_CHAMP_deploy11008_laptop-wsl_b134` |
| | `DONE_jcz_ARB_B16J4_deploy11008_laptop-wsl_b134` |
| **DURATION** | ~2.5 h (both boxes finish together by construction — `DECKS_LOCAL=215` / `DECKS_LAPTOP=185` are set from the saturating smoke) |

A `FAILED_` marker does **not** end the freeze. A resume re-enters the same cell on the same
`FREEZE_HEAD`, and `run_cell.sh` will refuse to start if HEAD has moved in the meantime.

## WHAT IS FORBIDDEN

Everything that moves `HEAD` on the box that is playing — **both** boxes:

- `git commit` (of anything: source, docs, `measurement/`, `android/`, `.md`, whitespace)
- `git commit --amend`, `git merge`, `git rebase`, `git cherry-pick`, `git revert`
- `git checkout <branch>` / `git switch`, `git reset --hard <other>`, `git pull`
- `git stash` / `git stash pop` **is fine** (it does not move HEAD), and so is editing files
  in the working tree — but see below, because editing live source is forbidden for a
  *different* reason.

## WHAT IS STILL ALLOWED

- **Reading.** `git log`, `git diff`, `git status`, `git show` — all fine.
- **Writing untracked/uncommitted files.** Logs, `measurement/` artifacts, scratch notes.
  The run itself writes into `measurement/jcz_tiearb_20260817/` constantly.
- **Staging.** `git add` moves no HEAD. Stage as much as you like; just do not commit.

⚠️ Separately and independently: do **not** edit `src/`, `engine/`, `rust/`, or shared eval
scripts in the main tree while a cell is live — spawn-worker respawns re-import from disk
(`feedback_worktree_isolation_live_tree`). That is a different hazard from this freeze; both
apply.

## THE PARKING PATTERN

Commits do not have to be lost — they have to *wait*. Queue the work in the working tree (or
`git add` it, or stash it), and land it in **one** commit after the fourth `DONE` marker. The
run costs ~2.5 h; a README typo can wait 2.5 h.

---

## HOW IT IS ENFORCED (three layers, and exactly what each one does)

| layer | when it checks | what it does |
|---|---|---|
| `launch.sh` | once, at band-claim time | **RECORDS.** Writes `$RUN_DIR/FREEZE_HEAD` (the sha, plus the four marker names), copies it to the share so the laptop gets it, and prints the freeze banner in its final output. |
| `run_cell.sh` | once, before each cell starts (4 times total) | **ABORTS**, loudly, exit code `26`, before game 1 — if `git rev-parse HEAD` ≠ `FREEZE_HEAD`. Also aborts (exit `26`) if `FREEZE_HEAD` is missing entirely in real mode. **A cell never starts on a moved HEAD.** |
| `watchdog.sh` | every 60 s heartbeat, per box | **LOGS ONLY.** Writes `!!! FREEZE VIOLATION` into `logs/watchdog_<host>_b134.log` with both shas. It **kills nothing** — the point is to make the violation impossible to miss *while the run is still salvageable*, not to destroy a run that a human might yet rescue by not committing again. |

The middle layer is the one with teeth, and it is deliberately positioned *before* game 1:
a cell that has already written records under a second rev cannot be un-mixed.

## WHY THE WATCHDOG DOES NOT KILL

By the time the watchdog sees a moved HEAD, records under the new rev may already exist — killing
the leg does not un-write them, and it destroys the other, still-clean cell as collateral. The
right response to a mid-run violation is a **human decision** made with the log in hand: usually
"stop committing, finish the run, and disclose the mixed-rev window", or "abandon now, before the
second cell is spent." The watchdog's job is to make sure that decision is *possible*, not to make
it.

---

## POINTERS

- `DISCLOSURE.md` §3 — the full account of the failure, written blind to the statistics
- `DISCLOSURE.md` §4 — the three things the re-run must change (this file is item 1)
- `READ_RULE.md` — `G-TOOL` as committed. **Unmodified.** This freeze exists so the gate as
  written can pass; it is not an amendment to it.
