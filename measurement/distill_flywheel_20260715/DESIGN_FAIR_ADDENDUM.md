# FAIR PIVOT ADDENDUM — distill the FAIR (blind PIMC) champion, not the clairvoyant one (2026-07-16)

**STATUS: SPEC — supersedes DESIGN.md §D2 (teacher) + §4.1/§4.3 (clair emitter/drivers). NOT launched.**

Joshua's call (2026-07-16): distill the **fair/blind PIMC champion**, not the clairvoyant one. Rationale — clairvoyant distillation injects **strategy-fusion bias**: the net (always blind — it never sees the deck; clairvoyance lives only in the search stepping the true deck) would learn `E_deck[π(board | that game's true deck)]`, the *average of deck-aware policies*, which is NOT the optimal blind policy (it can teach "gambles" justified only by peeking). The fair champion plays the correct information state (PIMC re-determinizes per move, aggregates blind), so its visit distribution is a legitimate blind policy target. Also makes training coherent with a fair (deployable) iter-12 eval.

## Cost correction (vs DESIGN §D2)
DESIGN said clair is "~4× cheaper" than fair — **wrong**; that conflated the elo tax (clair +205 → fair +49, ~4:1 strength) with compute cost. **Measured: fair ≈ 1.3× clair per move** (3882 vs 2986 ms/move at the same 2752-sim budget; source `measurement/classical_search/t3_s3_champ_base.log`). Fair self-play ≈ **~530–580 s/game single-core** (est.) vs clair ~430. **Re-ETA ≈ 36–44 h** (was 28–34 h). Confirm with the stage-1 smoke before launch.

## What's REUSED from the clair work (committed 827884f)
- `probe_metrics.py` — teacher-agnostic distillation-fidelity probe (policy CE / top-1 / value MSE+r vs the frozen probe set). Keep as-is.
- The `--teacher {net,heuristic_prior}` clairvoyant selector in `run_selfplay_iter.py` — **now a CLAIRVOYANT BASELINE only**, NOT the primary path. The fair emitter is a different game loop (below). Leave it committed; don't use it for the distillation run.

## The fair distillation emitter — exact spec (replaces DESIGN §4.1)

**Base:** copy `scripts/canonical_az/gen_fair_selfplay.py` → `scripts/distill_flywheel/gen_fair_distill.py` (do NOT mutate the existing value-only emitter). It already has the multiprocessing `--shared-claim` work-stealing pool, `--seed-start`, `--workers`, `--k-dets`, `--sims`, `--out`, O_EXCL `.claim` protocol — reuse verbatim.

**Change 1 — swap to the champion's fair agent.** Today it instantiates the LEGACY `FairHeuristicMCTSAgent` (random-expansion, c_puct=3.0) at lines 94, 163–167. Swap to **`FairHeuristicPriorAgent`** (the PUCT-priors champion sibling, `src/carcassonne_ai/fair_agent.py:305`) built from `HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, value_norm=15.0, leaf_quantize="float", final_select="visits", leaf_cfg=None)`, `sims=688`, `k_dets=4`, `exact_endgame=True`, `exact_max_k=2`. These are the exact PRODUCTION.yaml fair_deploy defaults (CL-054 k4×688, CL-051 curve125, K≤2 marginalized).

**Change 2 — expose the pooled visit distribution (additive, no behavior change).** In `FairHeuristicPriorAgent._pimc_move` (`fair_agent.py:446–471`), the local `agg_n` (built by `pool_root_stats` at line 467 = summed root-child visit counts across the k_dets trees) is exactly the policy target but is discarded. Before the `return` at line 471, stash `self.last_pooled_visits = dict(agg_n)`. Set it to a one-hot on the forced-move path (line 451) and to `None`/`{}` on the exact-endgame latch path (`choose_action` lines 497–507) so the emitter can detect policy-less rows. This does NOT touch the pooled-Q decision (`pooled_q_argmax`) → play strength unchanged. Add a `tests/test_fair_agent.py` assertion that `choose_action` returns the SAME action with and without the stash (pin no-behavior-change).

**Change 3 — record the fair policy at the move site.** In the game loop (`gen_fair_distill.py`, was `gen_fair_selfplay.py:178–190`): after `action = agent.move(board)` (line 188), read `pv = agent.last_pooled_visits`. If `pv` is a non-empty dict → build `policy = zeros(A); for a,n in pv.items(): policy[a]=n; policy /= policy.sum()`, `valid_mask = game.get_valid_moves(board).astype(bool)`, `aux_mask_row = True`. Else (forced/endgame) → `policy=zeros`, `valid_mask=zeros`, `aux_mask_row=False` (value-only). Stack per-ply and replace the value-only dummies at lines 234 (policies), 236 (valid_masks), 238 (aux_mask). `GameDataset` supports mixed aux_mask (warmstart.py:56–62).

**Change 4 — value target = game OUTCOME score_diff (not the per-move leaf).** DESIGN §D4 chose `--value-target score_diff` = `tanh((p0−p1)/15)` mover-POV, backfilled from the FINAL score. The current fair emitter records `tanh(leaf/15)` per move (a residual proxy, lines 186–187) — replace with the backfilled game outcome so `value_outcome_corr` is meaningful and the value head is absolute (analyzer/flywheel substrate). Compute final scores at terminal, backfill each row mover-POV signed.

**Change 5 — curve125 env (CRITICAL).** The fair scripts' hardcoded `_CANON_ENV` defaults to **curve100** (`-8,-4,-1,0,2,3,4,5`), NOT the production **curve125** (`-10,-5,-1.25,0,2.5,3.75,5,6.25`). Source the champion env from `champ_env.sh` (copied verbatim from `governance/PRODUCTION.yaml`) so we distill the actual production champion (leaf hash 158f17ff). Verify the resolved leaf hash in the manifest.

**Manifest:** self-describing `teacher` block = fair agent cfg (k_dets, sims, c_puct, tau_p, value_norm, exact_max_k) + resolved leaf env + `"policy_source":"pooled_visit_counts(agg_n, summed over k_dets)"` + `"move_selected_by":"pooled_q_argmax"` (NOTE: argmax(policy) ≠ played move on the fair path — pooled-N target vs pooled-Q pick; call it out so no trainer assumes they match). `"row_kind":"mixed (trajectory aux_mask=True; forced/endgame value-only)"`.

**Parity/smoke test:** 1-game fair smoke (k_dets=2, sims=32) asserting trajectory rows sum to 1 over the legal mask, mixed aux_mask (some True, endgame tail False), values ∈ [−1,1] sign-consistent with final score_diff, manifest teacher block + curve125 leaf hash present.

## The fair flywheel stage (iters 4–11) — replaces DESIGN §D1 stage 2

Gen agent = **`FairHeuristicPriorAgent(evaluator=<net-priors + frozen-leaf-value>)`** — the fair wrapper already takes an arbitrary `evaluator=` (fair_agent.py:392,419–420); no fair_agent.py change beyond Change 2. Build a ~20-line evaluator factory `make_fair_net_prior_evaluator(net_or_orch, leaf_cfg, value_norm)` returning `(net_priors_from_policy_head, tanh(flat_virtual_score_v2_float(state,mover,leaf_cfg)/value_norm))` — net priors, **frozen champion leaf as the ONLY value** (the severed-value-loop floor, preserved). Net forwards batch through **carc-orch** (the `--info fair-net` orch path in `eval_fair_puct.py`, `--orch-shm-name`, is the tested precedent). Record `agg_n` policy exactly as stage 1. Champion side-stream (150 fair-champion games/iter) = the SAME `gen_fair_distill.py`.

## Data-window accumulate FIX (bug caught by the clair coder)
rod_v2 passes `--iter 0 --output-root iterN_data`, so `train_iter.py --window` globs only `iter_00/` → it does NOT accumulate; rod_v2 relied on warm-chaining. To actually accumulate (DESIGN §D3, needed for the ≥50% champion-mix anti-drift), the driver must: **gen into `<SHARED>/iter_$(printf %02d $it)/seed_*.npz`** and **train `--output-root <SHARED> --iter $it --window 12`** so it globs `iter_00..iter_$it`. Fix this in the driver, not by mutating train_iter.py.

## Boxes / workers / ETA (fair)
- Fair champion gen is net-free CPU (heuristic leaf) → orch-OFF, local W16 + laptop W12, `--shared-claim`. Same as DESIGN §D5 stage 1.
- Fair flywheel net gen does net forwards → carc-orch (local), laptop keeps the fair-champ side-stream orch-OFF W12. Same topology as DESIGN §D5 stage 2.
- Train: LOCAL always. Accumulate-all (fixed per above). Re-ETA ≈ 36–44 h — CONFIRM at the stage-1 smoke (8 fair-champ games @ k4×688, W16 local, measure real s/game + MB/game; disk is a non-issue at ~0.10 MB/game).
- All else (gates G0/G1/G2, frozen probe set, no in-loop eval, dir layout, close-out) unchanged from DESIGN.md.

## Build order (fair)
1. `champ_env.sh` from PRODUCTION.yaml (curve125). 2. Change 2 in fair_agent.py + no-behavior test. 3. `gen_fair_distill.py` (Changes 1,3,4,5) + fair smoke test. 4. `make_fair_net_prior_evaluator` + a tiny fair-net gen smoke. 5. Drivers (copy rod_v2, fair recipe, accumulate fix, orch net mode). 6. Stage-1 smoke → real ETA → Joshua go. 7. Launch.
