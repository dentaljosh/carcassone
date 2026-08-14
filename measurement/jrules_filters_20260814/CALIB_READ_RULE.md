# CALIB READ RULE — J-rules ROOT FILTERS (surface C) E4-replay exclusion ladder

**COMMITTED BEFORE ANY RATE WAS READ.** At commit time the instrument
(`scripts/classical_search/jrules_filter_e4_replay.py`) has produced **no
exclusion rate on any arm** (a `--limit-plies` wiring smoke stamps `partial`
and is VOID as a calibration by §0). This rule is applied MECHANICALLY to the
rollup; no branch may be chosen, re-weighted or reinterpreted after seeing a
number. Anything this rule does not authorize is not authorized.

## §0 — validity (VOID conditions, checked before any branch)

The calibration is VOID — no branch fires, nothing is funded, the fix is free
(re-run; no band, no games) — if ANY of:

1. any per-game summary is stamped `partial: true` (a `--limit-plies` run);
2. `all_replay_scores_match` is not `true` in the rollup (one failing replay
   checksum voids the whole calibration);
3. the positive control (`_assert_surface_c_live`) did not pass on the grading
   box (it aborts the run — a rollup produced without it cannot exist through
   the instrument; a hand-assembled one is void by construction);
4. any arm's `leaf_hash` differs from the champion's `a36d2e15a3b3d71d` (the
   INVERTED guard — surface C moves no leaf; the instrument aborts on this);
5. the graded corpus is smaller than **20 archives** or **800 graded plies**
   (the bank holds 31 archives at commit time; a thin corpus re-runs, it does
   not re-interpret).

## §1 — what must be reported, with every rate

Per arm (`j10:2` · `j3:8` · `current:11` · `all:15` — the pre-registered mask
lattice; a filter has no dose, so there is NO finer-rung trigger and adding an
arm after seeing the ladder is a NEW calibration):

* **exclusion rate** = excluded champion picks / **ALL graded plies** — THE
  flip rate of this surface (an excluded champion pick is a forced pick-flip).
  Denominator deliberately matches surfaces A/B (all graded plies, tile plies
  included even though a root filter cannot bind there): the rate is the
  perturbation size **at deploy**, comparable across the three ladders.
* its **Wilson-95 interval** (the same `wilson_ci` as surfaces A/B, pinned by
  test);
* **yield rate** = plies where ANY never-empty guard fired / all graded plies,
  with its Wilson-95 (the SAFETY branch's input, §3);
* applicable share (meeple-root plies / graded plies) and the per-filter fire
  histogram — **descriptive only**, barred from the funding decision (§4);
* the rules-profile histogram, per-archive budgets, and `replay_scores_match`
  per archive.

## §2 — the funding bar

Let `f(arm)` be the exclusion-rate POINT ESTIMATE. The funding window is
**[0.10, 0.25]**:

* an arm with `f < 0.10` is NOT fundable — the perturbation is too small for
  an n=800 deck-paired cell to resolve its effect (the surface-B calibration's
  13.05% flip rate read z −0.03 at n=800; a filter below 10% has no realistic
  power story);
* an arm with `f > 0.25` is NOT fundable — more than a quarter of deploy
  decisions forced off the champion's pick is not a perturbation, it is a
  different agent, and its loss would price nothing attributable.

## §3 — the branches (exactly one fires; apply in this order)

1. **`SAFETY` (per arm, evaluated first):** any arm whose **yield rate
   exceeds 0.05** (point estimate, >5% of graded plies) is **MALFORMED — the
   rules contradict the position so often that the never-empty guard is doing
   the playing** — and is struck from fundability regardless of its exclusion
   rate. Struck arms are reported with the SAFETY stamp.
2. **`FUND-SMALLEST`:** among surviving arms with `f ∈ [0.10, 0.25]`, fund
   **exactly one cell** at the arm with the SMALLEST `f` (the smallest
   perturbation that clears the resolvability bar); tie → fewer mask bits;
   still tied → lower mask value. The funded mask + min_keep go verbatim into
   `DEPLOY_PREREG.md`; the deploy decision itself (band, boxes, timing)
   remains the owner/orchestrator's.
3. **`NO-EXPRESSION` (stop):** every surviving arm has `f < 0.10` ⇒ **no cell
   is bought.** The recorded answer parallels surface B's washout reading: the
   champion at deploy depth already plays inside the anchor's hard rules too
   often for this surface to be resolvable — a real finding, minted as no
   claim, costing no band.
4. **`OVER-WINDOW` (stop):** surviving arms exist but ALL have `f > 0.25` ⇒
   no cell is bought — the encoding is too aggressive at every pre-registered
   mask; any weaker configuration is a NEW calibration with its own committed
   rule, not an extension of this one.

## §4 — forbidden readings (binding)

* The exclusion rate is a **LOWER BOUND on behavioural change** — visit
  reallocation among kept actions is uncounted (would cost a full search per
  arm per ply). Never report it as "the total flip rate"; the instrument's
  docstring discloses the same.
* An exclusion is NOT an improvement and NOT evidence of strength either way.
  No elo, no strength adjective may be attached to any number in the rollup.
  (CL-080 anchor: a 10.09% flip rate cost −53.8 elo.)
* "Where the exclusions land" (phase, filter, k-histograms) is descriptive
  and may not move the funding decision.
* No cross-surface contrast is a statistic: "C excludes more than B flipped"
  is an observation about design, never differenced, never given a z
  (CL-068 binding).
* `champ_agrees_archive` is context, not a gate.
* A funded arm is authorization to DRAFT-COMPLETE the prereg, not to launch:
  band claim and launch remain the owner/orchestrator's (C-G6).
