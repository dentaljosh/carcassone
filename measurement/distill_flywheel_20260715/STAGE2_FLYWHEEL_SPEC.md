# Stage-2 fair-net flywheel (iters 4-11) — build spec (2026-07-16)

**STATUS: SPEC — build tomorrow, AFTER stage-1 (sighted) settles + gate G1 passes. Not started.**
Code structure below is stable; the RECIPE (proceed-at-all? mix ratio, sims) is gated on stage-1 results.

## Goal
Iters 4-11 test "does net-guided fair search produce a policy STRONGER than the champion's priors?"
Gen agent = the trained SIGHTED net's **priors** + fair PIMC search + **frozen champion leaf as value**
(severed value loop → no value-collapse). The post-search visit distribution becomes the new policy
target → train → repeat. A fair-**champion** side-stream anchors the net (can't drift below champion).

## Gate G1 (before building/starting stage-2 — check stage-1 sighted first)
Proceed ONLY if stage-1 sighted showed distillation working: probe CE dropped meaningfully below the
sighted-warmstart baseline AND top1 climbed across iters 0-3 (and beat non-sighted's ~59% — else the
bag didn't help and the flywheel inherits a weak seed). If stage-1 was flat, stop and reassess, don't flywheel.

## New code
**A. Fair-net-prior evaluator** — `make_fair_net_prior_evaluator(net_or_orch_handle, leaf_cfg, value_norm, sighted=True)`
returns `Callable[[Board] -> (net_policy_priors, tanh(flat_virtual_score_v2_float(state,mover,leaf_cfg)/value_norm))]`:
NET policy head → priors; FROZEN champion leaf → value. (Mirror `make_heuristic_prior_evaluator_with_net_value`
in heuristic_prior_mcts.py but swap which head each side reads.) Sighted board encode for the net forward.
Pass as `evaluator=` to `FairHeuristicPriorAgent` — the fair wrapper already accepts an arbitrary evaluator
(fair_agent.py:392,419), so NO fair_agent.py change. Net forwards batch through carc-orch (SHM).

**B. Net-fair gen mode in `gen_fair_distill.py`** — add `--net-ckpt <ts.pt>` (+ reuse `--sighted`): when set,
build FairHeuristicPriorAgent with the fair-net-prior evaluator (via orch handle) instead of the net-free
heuristic one. Records the SAME pooled-visit policy + outcome value (agg_n path unchanged). This is the
stage-2 gen; the net-free champion path stays for the side-stream.

**C. Orch wiring** — per-iter: export the sighted net to TorchScript (`export_torchscript.py`, parity-gated),
start `rust/carc-orch/run_server.sh --transport shm --shm-name <name> --workers 28 --forwarders 4
--max-batch 16 --batch-timeout-ms 2.0 --watchdog-secs 30 --n-scalar 42` (sighted!), gen workers attach via
`--shm-eval-server <name>`. Precedent: eval_fair_puct.py `--info fair-net --orch-shm-name`. Kill server per iter.
Endgame K<=2 marginalized is cheap → no orch starvation (unlike K>=4).

**D. Driver `run_distill_stage2.sh`** — copy run_distill_sighted.sh, iters 4-11. Per iter:
  - LOCAL: orch server + net-fair gen (`--net-ckpt <ts> --sighted`, orch W28) → 450 games.
  - LAPTOP: fair-CHAMPION side-stream (net-free, `--sighted`, W12) → 150 games (25% anchor).
  - both shared-claim into `<SIGHTED_run>/iter_NN/`, accumulate `--window 12`, warm from prev iter.
  - train LOCAL, collapse screen (thresh 4.0), probe_metrics.
  Net ckpt for iter N gen = iter_(N-1).pt (the flywheel bootstrap).

## Boxes / workers
LOCAL: orch server + net gen W28 (orch-ON) + train. LAPTOP: champ side-stream W12 (orch-OFF, net-free).
Both sighted (81ch/42). Train LOCAL always.

## Consistency
Sighted end-to-end: the net is sighted, the net-fair evaluator encodes sighted for the forward, the orch
`--n-scalar 42`, the champ side-stream `--sighted`, probe set sighted. Any shape mismatch fails loud.

## After iter 12 (11): FAIR eval (separate task) — sighted net vs fair champion (distillation quality) +
net-iterN ladder (flywheel effect). Deployable = net priors + fair PIMC search.
