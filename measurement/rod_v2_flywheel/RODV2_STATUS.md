# RoD v2 Flywheel (v2.9 leaf Bmild_cap8) — STATUS

**State:** STOPPED · AUTOPSIED — **confirmed null**
**Updated:** 2026-06-26
**Branch:** rod_v2_flywheel · **Tag:** rod_v2_flywheel

Ran 5 train iters (iter_02..iter_06, warm-from RoD_iter_01) gen+train only, then evaluated +
autopsied. **The flywheel did not restart compounding.** Full diagnosis + the A/B/C/D decision:
[autopsy/ROD2_AUTOPSY_REPORT.md](autopsy/ROD2_AUTOPSY_REPORT.md).

---
- **Verdict:** every checkpoint loses to h6400_v2.9 (−22..−32 elo, no climb); sits at ~h3200_v2.9
  parity; indistinguishable from RoD1 (adjacent deltas non-transitive). Policy prior is **diffuse**
  (77.5% "neither" on h3200≠h6400 states) with **no movement toward h6400** across iters; value head
  inert; self-play diffusing not climbing. Reproduces the v2.8 flywheel signature — the v2.9 leaf swap
  changed nothing. Strength is carried by the v2.9 leaf inside MCTS, not the learned net → blocker #2
  stands.
- **Decision:** **C** — stop the AZ-style blind flywheel; classical v2.9 is the strength. Stage B/C
  NOT run (Stage A confirmed, did not contradict). The only EV-positive direction is endgame/exact
  (D-flavored), named as the decision boundary, **not** proposed or started here.
- MEASUREMENT/EXPLORATORY — no promotion, PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen.
- Artifacts: `autopsy/` (TRAINING_DYNAMICS, DATA_DISTRIBUTION, NONTRANSITIVITY, POLICY_ROOT_AUDIT,
  ROD2_AUTOPSY_REPORT). Checkpoints retained: `/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_*.pt`.
