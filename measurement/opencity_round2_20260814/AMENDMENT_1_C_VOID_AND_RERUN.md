# AMENDMENT 1 — `C_d16p0` IS VOID; THE RE-RUN'S TERMS, FIXED IN ADVANCE

> **STATUS 2026-08-14: WRITTEN BEFORE THE RE-RUN'S BAND IS CLAIMED AND BEFORE ITS GAME 1.**
> Amends [DEPLOY_PREREG.md](DEPLOY_PREREG.md) for the arm-C cell ONLY. `Acap3_d2p0` and
> `Asym_d2p0` are untouched by every clause here. Nothing is adjudicated, nothing is promoted,
> `governance/PRODUCTION.yaml` is untouched.

## 1. What happened, and why the cell is void

Owner ruling 2026-08-14 (options put and answered): **`oc2_C_d16p0_deploy11008` on band
1.29e11 is VOID for confirmatory use** and the arm re-runs on a **fresh band**. Two independent
reasons, either sufficient:

1. **The pre-registered validity trigger fired.** 14 of 800 games failed = **1.75 %**, against
   the house reference of 0.5 % — 3.5× over. Cause: a **deterministic**
   `carc_rs.WindowTruncationError` (one distinct crash state across all 16 harness passes; all 4
   legal placements outside the 25×25 window on an elongated board). The trigger's own wording is
   *stop and investigate BEFORE reading*.
2. ⚠️ **THE ORCHESTRATOR BROKE THE CELL'S BLINDNESS.** While grepping the crash log for the
   traceback, the harness summary block was in the same output and **the cell's strength line was
   seen** (disclosed immediately, unintentional, recorded in DECISIONS 2026-08-14 and STATUS).
   Blindness once broken cannot be restored.

The exclusion is additionally **not outcome-independent**: the poisoned game is excluded for a
*structural* property of its board (an elongated board overflowing the action window), unlike the
Joshua-bot confirm's outcome-independent single drop where the cost was n and not bias.

## 2. The single most important clause in this document

**THE RE-RUN IS READ UNDER `DEPLOY_PREREG.md`'S BRANCHES EXACTLY AS ALREADY WRITTEN. NOT ONE
THRESHOLD, SIGN, STATISTIC, OR BRANCH CONDITION MAY BE CHANGED BY THIS AMENDMENT OR AFTER IT.**

This clause exists because the person writing it has seen a number he should not have seen. The
standing house failure mode — four confirmed winner's-curse instances — is a rule rewritten, a
threshold nudged, or a top-up authorised *after* a result is visible. The defence is that the
branches were fixed before any of this and are not being reopened now:

- primary statistic = the **deck-paired margin z**, per cell; elo secondary
- `N2 NEGATIVE`, `N1`/`N3` no-conviction bands, the `ms_ratio > 1.20` cost trigger, the failed-game
  validity trigger, and the O0–O12 wiring gates all carry over **verbatim**
- **no top-up is licensed** for the re-run, at any z, for the same reason none was licensed
  originally

⚠️ **Known, unfixable residue:** a reader who has seen the voided cell's sign cannot un-see it, so
the re-run's *interpretation* is not fully blind even though its *rules* are. This is recorded as a
permanent limitation of the re-run, not waived. If the re-run's own number is ever contrasted with
the voided cell's, that contrast is **forbidden as a statistic** (different bands, one of them
void; CL-068 and read rule 5) and may only be described as an observation about the incident.

## 3. What the re-run is, precisely

**The same cell, not a new hypothesis.** Arm C = `opencity_size_min 6.0` / `opencity_edge_min 3` /
`opencity_symmetric True`, `opencity_dose 16.0`, `cand_leaf_hash a4acf6d0925f7606`, opponent = the
unmodified champion `a36d2e15a3b3d71d`, both arms fair PIMC **k8×1376 = 11008**, `fixed_v1`+R9,
rust both sides, exact-K 2, **n = 800 deck-paired = 400 decks × 2 seats**.

- **FRESH BAND, claimed at launch** via `claim_next_band.py`, `decision_influenced = not yet`.
  Band 1.29e11's C sub-range (+0..+399) is **spent and void** and is never reused, never pooled,
  and never contrasted with the re-run.
- The on-the-bar caveat **carries over unchanged**: arm C was funded at **10.41 %** flip against a
  10 % bar with a Wilson-95 of 8.99–12.03 % straddling it. If the re-run lands null, *"the tight
  predicate does not express"* remains **NOT an available reading** — it was funded at the edge of
  the expressiveness floor. Liveness is independently evidenced by the calibration's
  **162/1,556 champion picks flipped** on real E4 games through this same code path.

## 4. Launch preconditions — ALL of these, before game 1

1. ⛔ **The `eval_fair_puct.py` per-game crash-resilience fix MUST be merged first**
   (`worktree-agent-a1e5dddb01337d3d7`, `8c00b8f1`). Without it a single deterministic crash again
   tears down the whole pass and strands every in-flight claim — the re-run would reproduce the
   exact failure that voided the cell. Merge only at a quiet window: it is a shared eval script and
   live `--shared-claim` cells re-import it from disk.
2. **Orphan-claim hygiene**: the re-run writes to a fresh cell directory, but any resumed cell must
   have claims-without-records cleaned first (`scripts/verify_shared_claim.py` enumerates them).
3. **Per-box wheel + probe** unchanged from the original prereg §3 (a stale wheel fail-closes on
   capped cells; the arm-C probe legitimately reads `values_moved: 0` on the golden corpus — see §3
   above for why that is not evidence of inertness).
4. **Worker counts, owner directive 2026-08-14:** **laptop W22 · local W30** (the driver's local
   default is 14 and must be overridden). See [NEXT_CELL_WORKERS.md](NEXT_CELL_WORKERS.md).
5. **The failed-game rate is re-armed as a validity trigger.** With the resilience fix, failures are
   counted rather than fatal — so the trigger becomes *readable* rather than *inferred from missing
   records*. `> 0.5 %` still means stop and investigate before reading.

## 5. What this amendment does NOT do

It does not touch `Acap3_d2p0` or `Asym_d2p0`; it does not re-open arm A, arm B, the capped or
asymmetric forms, or `CL-080`'s scope; it mints no claim; it licenses no top-up; and it does not
fund **F-a** (widening the action window) — the owner ruled F-a **stays unfunded**, because the
census's `P1 = CURIOSITY` still holds on *strength* grounds and this incident's cost was
*reliability*, which the resilience fix addresses far more cheaply than re-architecting the search
hot path.
