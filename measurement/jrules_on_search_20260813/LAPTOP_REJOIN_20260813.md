# Laptop leg — refused, then re-joined by hand (2026-08-13)

**Status: RESOLVED. The cell was played on BOTH boxes.** This file exists because
`FAILED_LAPTOP_DISPATCH` (13:37:51) records only the first attempt and, read alone, says
the opposite. A close-out that reads the marker without this file will get it wrong —
one subagent already did.

## Timeline

| time | event |
|---|---|
| 13:37:49 | chain START, band 128000000000, local O0 + G4 PASS |
| 13:37:51 | laptop dispatch **rc=6** — sync guard refused (dirty tree). Non-fatal by design; local leg continues alone |
| 13:37:51 | local leg START, W14 |
| ~13:45 | laptop synced by hand (`--ff-only`), `a86c11d8` → `217f0cdb` |
| ~13:47 | laptop leg dispatched from a pre-synced copy — **G3 / G4 / O0 all PASS**, leg LAUNCHED detached W16 |
| 13:48 | verified: 18 `eval_fair_puct` workers on laptop, load 16.09, both hosts claiming |

## Why the guard fired, and why it was right

The launcher refuses to `git reset --hard` a dirty remote tree, on the reasoning that another
session may be mid-rebuild. It fired because the laptop tree carried **untracked** files:
other sessions' run artifacts (`e4_autopsy_20260812/` results and logs, `jcz_mining_20260809/`
logs, `opencity_term_20260812/DONE_DEPLOY_OPENCITY`) plus a hand-written copy of the dose-0.25
cell JSON left by that morning's wheel rebuild.

`git reset --hard` would not in fact have deleted the unrelated untracked files, so the guard is
conservative — but the conservatism is correct: those artifacts are irreplaceable, and the guard
cannot know which untracked files matter.

**The wheel rebuild and the failed dispatch are the same event.** Preparing the laptop is what
dirtied its tree.

## Resolution — by hand, without weakening the guard

1. Removed **only** the laptop's untracked cell JSON. Safe: byte-identical to the committed
   one, `md5 f375ac6e2ba50919426f221bcf4f2429` on both boxes.
2. `git fetch <bundle> && git merge --ff-only FETCH_HEAD`. A fast-forward cannot touch unrelated
   untracked files and fails safely if the history diverged. Laptop HEAD → `217f0cdb`, equal to
   local.
3. Dispatched from a **copy** of `dispatch/laptop_leg.sh` with only the sync block replaced by:
   an `EXPECT_HEAD=217f0cdb…` assertion, and a refusal if any **tracked** file is modified.
   Everything else — the env canon exports, G3/G4/O0 gates, share resolution, the
   `eval_fair_puct` invocation — left byte-identical.

**The chain script itself was not edited.** It was mid-execution running the local leg, and bash
reads scripts incrementally; editing a running script can corrupt its execution.

## Gate evidence on the re-dispatch (identical to local)

```
champion  a36d2e15a3b3d71d
candidate 15948beccf3472d3
trap      92ac0da996e1b37b   (reproduced on-box, not asserted)
resolved_jrules_dose 0.25    jrules_mask 31
G3 reconcile PASS · G4 capability probe PASS · O0 leaf gate PASS
```

Share resolved by **sentinel content** to `/mnt/carc-shared`; `/mnt/c/carc-shared` correctly
rejected (1 entry — the laptop's own `C:`). Both paths exist on that box, so `[ -d ]` cannot
distinguish them; this is the hazard the sentinel probe was built for, and it worked.

## What this changes at close-out

- **Worker counts:** the cell ran local **W14** + laptop **W16**, not local-only. Any absolute
  ms/move or games-per-hour figure must say so.
- **The primary statistic is unaffected.** The deck-paired margin does not depend on worker
  count, and `ms_ratio` is a within-cell ratio of two arms sharing one process pool — it is
  first-order insensitive to contention. (Never quote an *absolute* ms/move from a
  shared-tenancy run; the ratio only.)
- **The scheduler will not auto-rejoin the laptop.** `scripts/scheduler/queue.json` resolves
  this row DONE on `CHAIN_STARTED`, deliberately, so it cannot dispatch a second chain onto a
  band that is already being played. A future re-join stays a manual `--laptop-only` call.
