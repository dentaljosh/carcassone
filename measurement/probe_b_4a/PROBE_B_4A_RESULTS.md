# PROBE B §4A — Fair-target value arm (Gate-B diagnostic) — RESULTS

Status: **🔄 IN PROGRESS** — full-n (10,067) eval pending. Spec: [docs/PROBE_B_FAIR_INFO_SPEC.md](../../docs/PROBE_B_FAIR_INFO_SPEC.md) §4A. Reader: `scripts/probe_b/verdict_4a.py`.

## The question (one variable = clairvoyance)

Train the CL-037 gate head on **fair (determinization-averaged) targets** vs **clairvoyant targets**, holding *everything else* identical — same head/eval/α-sweep, same 10,067 h6400_v2.9 sibling sets, same v2.9 leaf, and the **same search depth D=800**. The only difference between the two target sets is clairvoyance.

- **H-4A-inert:** does the value's "can rank with residual over the leaf" (best_α>0, beats_leaf) SURVIVE fair targets? Inert holds under fair → **fourth nail** (Gate-B not a clairvoyance artifact). Inert breaks under fair → part of Gate-B was a clairvoyance artifact, the flywheel has hidden room.
- **H-4A-bag:** does the bag input's contribution GROW under fair targets vs clairvoyant? Grows → CL-037 redundancy was clairvoyance-suppression. Vanishes → genuine regime-invariant redundancy (CL-037 holds across regimes) → reinforces the fourth nail.

## Pipeline (all reused / one-variable-clean)

1. `build_fair_targets_4a.py` — label the full `pool_A` (10,067 roots) with matched-depth **fair@800** (K=12 determinizations, `fair_isolate`) AND **clairvoyant@800** (single true-deck search) targets. Sharded `--root-start/--root-count` across boxes, `--merge`d → `targets_full.jsonl` (10,067 roots).
2. `retarget_4a.py --target-kind fair|clair` — swap `oracle_q` into the CL-037 dataset (`/home/doctor/carc_step1_gate/dataset_both`); obs/scalars/leaf_q/split/group-ids UNCHANGED → `ds_fair_full` / `ds_clair_full`.
3. `run_4a_eval.sh` — the CL-037 `step1_train.py` UNCHANGED, 6 arms: fair|clair × full / `--drop-farm` (bag-only) / `--drop-bag` (farm-only).
4. `verdict_4a.py` — reads the 6 summaries → the H-4A-inert / H-4A-bag calls.

## One-variable invariant — VALIDATED

`ds_fair_full` vs `ds_clair_full`: obs md5-identical, `child_scalars`/`leaf_q`/`split`/`group_id` bitwise identical; **only `oracle_q` differs** (mean|Δ| = 0.0075, in 97.4% of rows = the pure clairvoyance effect at matched depth). Both target sets have healthy std ≈ 0.61 (non-degenerate — no residual-target collapse). This is a clean §4A comparison.

## n=150 preview (SANITY ONLY — ~8 test groups, NOT the verdict)

| arm | best α | regret-red% | net-alone τ | beats leaf |
|---|---|---|---|---|
| clair both | 0.05 | +24.0 | 0.167 | ✅ |
| clair bag-only | 0.05 | +36.9 | 0.047 | ✅ |
| clair farm-only | 0.05 | +11.1 | 0.089 | ✅ |
| fair both | 0.0 | 0.0 | 0.208 | ❌ |
| fair bag-only | 0.0 | 0.0 | 0.012 | ❌ |
| fair farm-only | 0.0 | 0.0 | −0.045 | ❌ |

Sanity: clair arm reproduces CL-037 (non-inert, α=0.05, bag carries it). Preview leaned **fourth-nail** — fair value INERT (α=0, adds nothing over the leaf despite a fine net-alone τ), bag signal VANISHES under fair. **n=8 groups cannot carry this; the full-n eval decides.**

## FULL-N VERDICT (n_test≈1544) — _pending_

<!-- fill from: python scripts/probe_b/verdict_4a.py measurement/probe_b_4a/eval_full -->

_TBD — H-4A-inert: ___ · H-4A-bag: ___ · fourth-nail call: ____

## Infra notes

- Gen ran both-box (local W28 roots 0–6000 / laptop W22 roots 6000–10067); the **laptop WSL tore down on the detached launch (0 rows)** — the known [[reference_laptop_cluster_access]] pattern → local fallback for the laptop range (~22 min).
- Retarget copies a **32 GB** obs per dataset; running fair+clair retargets **concurrently OOM-restarted WSL** (~64 GB pressure on a 41 GB box) → re-ran clair **solo**. Lesson: don't parallelize large-obs (memmap/copy) ops on the memory-constrained local box.

MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
