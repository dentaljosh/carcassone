# M1 — Recover the discarded deep-plane learned gain (iter2) (runbook, launch-ready)

**Status:** SCOPED — launch-ready, **waiting on fast-local** (S1 arbiter holds it; the Xeon is too slow for n=400
s800 → M1 runs on local after the arbiter). Plan: [docs/POST_REVIEW_PLAN.md](../../docs/POST_REVIEW_PLAN.md) §2.
Scoped 2026-07-01 (subagent read-only pass).

**Question.** deepteacher **iter2** beat iter8 **+53.7 paired elo, z=2.14, @ sims=800** (results.csv
`confirm_iter2_vs_heur800_v27_s800_n400`) — the deep plane where other learned gains wash out — flagged "RECOMMEND
fold," never folded; the run continued to iter12 (ties iter8) and was verdicted off the FINAL iterate (the F7
failure mode). Prior = "promising" (one z=2.14 + one z=1.42 same-direction), NOT established. M1 decides **real
transient gain** vs **forking-paths/band noise** on a FRESH band.

## Design (fixed-rung paired — no forking path)
Both nets play the SAME fixed external rung (heur@800-v2.7) on the SAME decks; `odo_paired_tally.py` differences the
two dirs → paired delta. **Never** iter2-vs-iter8 head-to-head (keep-best-vs-fixed-rung is legit; vs-parent is not).

## Checkpoints (on the share, confirmed)
- iter2: `/mnt/c/carc-shared/deepteacher/ckpt/iter2.pt`
- iter8 (champion): `/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt`

## Fresh band = **5.0e9** (verified clean vs results.csv; clears EVAL_SEED_FLOOR=1e9). Distinct from the arbiter's band.

## Launch — core test (0 code change; runs at sims=800 natively)
Harness `scripts/eval_net_vs_heuristic.py --paired --shared-claim` via the orch wrapper `scripts/eval_orch.sh`
(exports TorchScript parity-gated, starts `rust/carc-orch/run_server.sh --transport shm`, points the eval at it,
trap-cleans /dev/shm). Reference invocation: `scripts/interim_sealed_it8_vs_it2.sh`. Two runs (iter2, iter8), same
`--seed-start 5000000000 --n 400 --paired`, fixed rung heur@800-v2.7:
```
# per net (iter2, then iter8), via eval_orch.sh: CKPT=<ckpt> SIMS=800 HEUR_SIMS=800 OW=16 ...
# out to /mnt/c/carc-shared/m1_iter2/{iter2,iter8}; then:
python scripts/odo_paired_tally.py <iter8_dir> <iter2_dir>   # -> paired delta(iter2-iter8)
```
Worker counts (orch): local 16 / laptop 20 / xeon 10. Net forward is deterministic per ckpt → net-on-CPU/GPU/orch
give identical priors → result-identical (parity-gated by `export_torchscript.py`). Code-sync any remote via
git-bundle first.

## v2.9 cross-check rungs (secondary) — ⚠️ Joshua decision
`iter2 vs h3200_v2.9` and `h6400_v2.9` via `scripts/rod_v2/value_search/run_orch_match.sh` →
`eval_hybrid_handoff.py` (LEAF=v2_9: cap8 + curve + meeple_k2 + rss0.25). **BLOCKER:** `eval_hybrid_handoff.py:85`
hardcodes `ITER8_SIMS=200` (not env-overridable) → the neural side plays at sims=200, not 800. Options: (a) run the
v2.9 rungs at **sims=200** (shipped, no edit); (b) **one-line edit** to parameterize ITER8_SIMS for sims=800. The
CORE heur@800 rung above answers the main question regardless — the v2.9 rungs are cross-checks.

## Read-out
- **Success:** iter2 ≥2σ over iter8 on the fresh band @ sims800 → the gain is real, lost to final-iterate
  verdicting → revive deeper-teacher warm-from-iter2 with per-iterate keep-best-vs-fixed-rung gating; correct the
  "deeper teacher doesn't help" verdict. Autopsy §7 "M1 fires" branch.
- **Kill:** fails fresh-band replication → prior reads were band noise/forking paths; close it, "deepteacher"
  verdict stands. Autopsy §7 "all-kill" contribution. Single read-out, no peeking.

MEASUREMENT ONLY — no champion/PRODUCTION.yaml/v2.7/v2.9 change. Contributes to CL-041 (autopsy).
