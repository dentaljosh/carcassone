# WEEKEND QUEUE — the autonomous decision tree (2026-08-14 → Sunday morning)

> **STATUS: LIVE through Sunday morning 2026-08-16.** Joshua: "get agents working on 1-3. the
> boxes are yours until sunday morning. default to w22 laptop, w30 local" + the tie-escalation
> proposal ("the vart"). **Shabbos window: no owner rulings from Friday sundown to Saturday
> night.** Every branch below was committed BEFORE its numbers exist; a fired pre-registered
> branch IS its authorization (`feedback_execute_prereg_triggers`). This file is what the hourly
> heartbeat and any fresh session follow — mechanically, no improvisation.

## Hard lines (hold regardless of what fires)

- `governance/PRODUCTION.yaml` untouched on every branch. Nothing is promoted.
- No top-ups of any cell, at any z. No re-runs of closed calibrations on enlarged corpora.
- A band is claimed only when this queue's own branch logic funds a cell, via
  `claim_next_band.py`, `decision_influenced = not yet`.
- Anything a written read-rule does not cover: STOP that thread, record state in STATUS.md,
  leave the box idle. Idle beats improvised.
- Workers: **laptop W22 · local W30** (every driver's `local` default is 14 — always pass 30).
- Detach every run (`setsid nohup … < /dev/null &`); arm an on-box watchdog for anything
  expected > 2 h; verify N>1 workers with `ps` within a minute of launch.
- Six-touch close-out after every concluded cell; gates before any strength read; N4/cost
  BEFORE the primary statistic, from the emitter's field semantics
  (`champ_prefix_ms_per_move` = the CANDIDATE side).

## In flight at writing (~16:00 Fri)

| thread | state | next event |
|---|---|---|
| R3-2 root filters (surface C) | 🔚 **CLOSED — `NO-EXPRESSION` fired (9.07% Wilson-hi < 10% bar); merged `97038182`; Q1 RESOLVED, no cell** | none |
| R3-3 E1 win-objective | build agent running (worktree) | build lands → step Q2 |
| tie-escalation pre-gate ("the vart") | 🔚 **CLOSED — `E-FLAT`; merged; Q3 RESOLVED, no cell** | none |
| h2h stale-failure fix | ✅ merged `d366de4b`-era; done | — |
| tile-tie leaf route (R3-1) | 🔚 closed (G2-SCREEN-FAIL + reach bound) | none — do not reopen |

## The queue (execute top-down as gates land; cells are ~2.2–2.9 h each at standing W)

**Q1 — root filters (surface C). ✅ RESOLVED 2026-08-14 ~16:20: `NO-EXPRESSION` fired; closed at 0 games; merged. Heartbeat: SKIP this step.** *(original logic kept for the record:)* When the build lands: merge worktree at a quiet window →
per-box wheel rebuild (pinned rustc 1.96.0) + capability/positive control on EVERY box that
plays → run its calibration if the agent didn't (0 games, local W30) → apply its
`CALIB_READ_RULE.md` mechanically. **FUND branch** → claim fresh band, launch the single funded
cell (n=800, either box, standing W). **NO-EXPRESSION or the >5% guard-yield SAFETY branch** →
close out (0-game precedent), no cell, record in STATUS/LEVER_INDEX.

**Q2 — E1 win-objective.** When the build lands: merge at quiet window → wheel rebuild + the
two-mode positive control on the playing box → run its 0-game divergence pre-gate if not run →
apply its read-rule. **Divergence < ~1%** → bounded-tiny, close free, no cell. **Funded** →
claim fresh band, launch the cell (⚠️ its prereg carries paired WIN-RATE as named co-primary —
that is pre-registered, not optional). 

**Q3 — tie-escalation. ✅ RESOLVED 2026-08-14 ~16:35: `E-FLAT` fired; axis closed at 0 games; merged. Heartbeat: SKIP.** *(original logic kept for the record:)* The pre-gate agent's read-rule governs. **FLAT** → the axis closes
(record: neither static functions nor deeper same-shape search expresses the oracle spread).
**DEV-PASS + holdout confirm** → this becomes the highest-value pending cell BUT its deploy
design needs the uniform-escalation CONTROL arm at matched wall-clock (2 cells) and was only
sketched, not pre-registered. ⚠️ **If and only if a full DEPLOY_PREREG for both cells exists
and was committed blind, launch; otherwise PARK for Joshua** — a control-arm design invented
during the autonomous window is improvisation, not execution.

**Q4 — ⚠️ SUPERSEDED Fri evening (Joshua: "so is nothing worth running over Shabbos?" = the funding ask): TWO overnight 0-game measurements are AUTHORIZED and launched — the two remaining explanations of the tile-tie signal.**
**Q5 — out-of-family re-pricing of the tie corpus** (local W30): re-score dev-slice tied arms under an out-of-family judge; blind branches CONFIRM (signal real → k-width/search-side licensed) / COLLAPSE (judge artifact → the tile-tie axis closes ENTIRELY incl. Stage-B ±17) / PARTIAL. Heartbeat: restart per its committed launcher if dead; apply its read-rule mechanically on DONE.
> ✅ **Q5 DONE 2026-08-14 — branch `C-CONFIRM` (`measurement/tiletie_oof_20260814/`, [READOUT](tiletie_oof_20260814/READOUT.md)).** Judge = `tier1-greedy` (forced: `ORACLE_POLICIES` has exactly two members and it is the only out-of-family one). 502 positions / 1033 legs, both judges on **bit-identical CRN worlds**. **The out-of-family judge sees MORE headroom: `R = H_OOF/H_IF = 1.827`, CI [+0.913, +3.995]**, `R_norm` 0.820, `G-CAL` PASS. ⇒ **the judge-artifact explanation is refuted; the axis does NOT close.** Q6 is now the ONLY surviving explanation and the single highest-information open item.
**Q6 — k-width ladder at tied plies** (laptop W22, or local after Q5): k 8→16→32(→64) at 1376/det + the BUDGET-MATCHED control rung k32×344; blind branches fund-consideration / W-FLAT; attribution = worlds vs budget via the control rung. Same heartbeat treatment.
Beyond Q5/Q6: nothing further is authorized. Leave idle. (The E4 +55-games bar needs Joshua playing, not compute;
everything else named this week is closed or parked.)

## Ordering rule when multiple cells are fundable

Priority: Q1 before Q2 before Q3 (Q1/Q2 preregs are complete; Q3's may not be). Two boxes ⇒
run the top two concurrently, one cell per box, never two cells sharing a box. Chain the next
queue item on each box's DONE marker — and watch markers in the REPO dir, not the share
(the 08-14 chain bug).

## If something breaks

Driver dead + no DONE: diagnose from its driver log; clean ONLY claims-without-records; relaunch
per its committed launch script (once; a second death on the same cell = park it, record, stop).
`WindowTruncationError` in a cell: the resilience fix counts it — let the cell finish; the
validity trigger (>0.5% failed) is applied at read time by the read-rule, not mid-run.
Box unreachable: it is almost always the WSL VM, not the machine (`reference_wsl2_host_memory_teardown`);
do not launch replacement work on the surviving box beyond the queue.
