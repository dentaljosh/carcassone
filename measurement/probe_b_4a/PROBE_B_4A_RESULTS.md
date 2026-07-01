# PROBE B §4A — Fair-target value arm (Gate-B diagnostic) — RESULTS

Status: **✅ CONCLUDED (2026-07-01)** — full-n (n_test=1544) all-inert; §4A depth-saturated/inconclusive on its own → **Probe B flywheel bet closed on the value-inertness LEDGER (not this screen); ship the analyzer + B1**. See FULL-N VERDICT below. Spec: [docs/PROBE_B_FAIR_INFO_SPEC.md](../../docs/PROBE_B_FAIR_INFO_SPEC.md) §4A. Reader: `scripts/probe_b/verdict_4a.py`.

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

## FULL-N VERDICT (n_test=1544)

**All six arms INERT — best_α=0.0, regret_reduction +0.0%, beats_leaf=False** (net-alone τ: clair 0.034 / 0.034 / 0.009, fair 0.002 / 0.040 / −0.007). The n=150 preview's "clair non-inert (α=0.05), fair inert" pattern was an **8-group small-sample artifact — REFUTED at full n** (clair is inert too).

- **H-4A-inert → AMBIGUOUS / INCONCLUSIVE (the honest call).** The test needs a *non-inert* clair baseline to contrast fair against, but **clair@800 is also inert.** CL-037's non-inert value (α=0.05) required the **deep h6400 teacher**; at matched *play* depth (800) even clairvoyant targets give the value no residual over the v2.9 leaf. So **§4A is DEPTH-SATURATED and cannot isolate the clairvoyance variable** — the "is Gate-B a clairvoyance artifact?" question is **deliberately left UNRESOLVED, out-of-scope for the ship decision.** (An h6400-depth §4A would answer it; a mechanism nicety, not the verdict — not funded.)
- **H-4A-bag → null / uninformative.** Both regimes give bag-marginal = +0.0pp — trivially true when everything is inert; carries no signal about clairvoyance-suppression vs regime-invariant redundancy.

### The close — on the LEDGER, not on this screen

Probe B's flywheel bet is closed **NOT** on §4A's offline screen (depth-saturated, inconclusive), but on the **accumulated weight of the value-inertness ledger**: six independent results — RoD-v2 flywheel null (CL-029), value/search autopsy (CL-032), value-resurrection ranker (CL-033), feature-graph comparator washout (CL-034) / typed-GNN inert (CL-036), Gate-B scalar-leaf (CL-038), and Probe-A §3A structured-leaf redundancy — spanning **scalar and structured** objects on **clairvoyant** targets, plus the **offline→online mechanism established in Gate-B** (a value can rank yet fail to drive search). §4A extends the pattern to the **fair-target** regime (consistent, though inconclusive on its own). No single screen — least of all this depth-saturated one — carries the decision; the cumulative ledger does.

**→ The AZ-value route is exhausted across scalar / structured / clairvoyant / fair. Ship the analyzer** (endgame-2, the original Phase-5 goal), served by the proven sighted value head — with **B1 (the fair-info agent, `fair_isolate` fixed) as the deployable, human-anchorable artifact** (Probe B's non-empty deliverable).

## Infra notes

- Gen ran both-box (local W28 roots 0–6000 / laptop W22 roots 6000–10067); the **laptop WSL tore down on the detached launch (0 rows)** — the known [[reference_laptop_cluster_access]] pattern → local fallback for the laptop range (~22 min).
- Retarget copies a **32 GB** obs per dataset; running fair+clair retargets **concurrently OOM-restarted WSL** (~64 GB pressure on a 41 GB box) → re-ran clair **solo**. Lesson: don't parallelize large-obs (memmap/copy) ops on the memory-constrained local box.

MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
