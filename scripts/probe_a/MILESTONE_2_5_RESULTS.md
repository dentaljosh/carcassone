# PROBE A — MILESTONE 2.5 RESULTS: board-level side-inputs + §3A INDEPENDENCE GATE

**Date:** 2026-06-30 · **Status:** ⛔ **§3A GATE = REDUNDANT → KILL Probe A** (pre-registered cheap kill, spec `docs/PROBE_A_STRUCTURED_VALUE_SPEC.md` §3A) · **MEASUREMENT ONLY** — offline, LOCAL, no games; champion / PRODUCTION.yaml UNCHANGED. Changes uncommitted.

Milestone 2.5 added the two board-level side-inputs the m2 head was missing (bag/deck histogram + exact cloister offset), then ran the pre-registered §3A farm/bag independence gate — the decisive kill before any in-loop budget.

---

## TASK 1 — head additions (the two board-level side-inputs)

Both are BOARD-LEVEL (one per node); the aggregate stays a PURE SUM so the leaf is a drop-in:

```
v_leaf = tanh( ( running_diff + cloister_offset + Σ_i g_θ(comp_i) + bag_head(bag_hist) ) / 15 )
```

- **32-dim bag/deck histogram** (the axis CL-037 showed exceeds the v2.9 ceiling): REUSED `step1_planes.bag_histogram` verbatim (the frozen 32-type census, = the same extraction `step2_leaf`'s `build_dataset.bag_histogram` imports). Fed through a small `bag_head` (32→16→1), scalar added to the aggregate. New per-board side-table `bag_sidetable.npz` (314,911 boards, joined to `component_ds` by `(seed,ply,rank)`, oracle_q alignment guard PASSED).
- **Cloister gap closed** (m2 residual abs_mean 7.52 on 84% of boards): the heuristic's own cloister/monastery value (base + closure, self−opp, root-POV) is added as an **EXACT board-level offset** (`structured_leaf.cloister_offset`), same pattern as `running_diff`. **Verified bit-exact** vs the dataset's `cloister_slice` (max err 0.0 over 682 boards, 680 nonzero). Σ-identity holds to fp: `pretransform == running + cloister + (y_struct − cloister)`, max err ~7.6e-6 (float32).

### Speed re-confirmation (§3 budget ≤3× the Cython leaf, `enriched25_speed.py`)
Machine-current baselines (5900XT, `CARCASSONNE_USE_CY_LEAF=1`):
| cell | m2 (no bag/cloister) | **m2.5 (enriched)** |
|---|---|---|
| structured-only PATH | 1.86× | **2.42× — PASS** |
| additive-arm (h + v) | 2.91× | **~3.45× — over 3×** |
| new side-inputs marginal (bag_hist + bag_head + cloister) | — | +0.38× |

The **in-loop structured leaf is 2.42× — well within budget.** The additive-arm *pre-gate harness* is ~3.45× because it runs the heuristic leaf `h` AND the full structured leaf (two independent Cython decomposes); the bag+cloister enrichment (+0.38×) nudged the pre-existing 2.91× over 3×. numpy==torch export verified (`export_gtheta.py`, folds bag-head norm; tol comp<1e-4, bag<1e-4, leaf<1e-5). NOTE: bringing the §4 additive arm back ≤3× is a bounded follow-up (derive `h` from the emit's decompose to kill the double-decompose) — not needed for this §3A kill gate.

---

## TASK 3 — §3A FARM/BAG INDEPENDENCE GATE (the pre-registered kill)  ⛔

Protocol = the CL-037 sibling-regret ablation on the **structured head**, same 10,067 h6400_v2.9 sibling sets, h6400-Q ranking target, group-split by game_seed → **n_test = 1544 groups** (== CL-037's n). Four input regimes (structured ranker, listnet-to-Q, V4-arm; farm-connectivity cols 12–14 zeroed or on; bag off/on). `regret_gain(regime)` = regret reduction of `leaf_q + α·net/sd` vs leaf-alone (best-α swept over CL-037's α-grid).

| regime | net-alone τ | best α | regret leaf→best | **regret_gain** |
|---|---|---|---|---|
| none (farm cols zeroed, no bag) | 0.286 | 0.5 | 0.0261→0.0163 | **+37.8%** |
| farm-only | 0.367 | 1.0 | 0.0261→0.0148 | **+43.5%** |
| bag-only | 0.282 | 0.5 | 0.0261→0.0165 | **+36.7%** |
| both | 0.366 | 1.0 | 0.0261→0.0147 | **+43.6%** |

- **Δ_indep = regret_gain(both) − max(farm-only, bag-only) = 43.56 − 43.51 = +0.05pp**
- **Measured eval σ (properly PAIRED, `gate_3a_delta_sigma.py`): 0.36pp** (bootstrap SD 0.36pp; 95% CI **[−0.61, +0.78]pp**). Δ_indep z = +0.15σ. (The naive SE-of-a-single-gain is 5.65pp, but both/farm are measured on the SAME groups and highly correlated → the paired σ is the correct one and is far tighter.)
- **Threshold: SEPARATED iff Δ_indep ≥ 3pp (≈8σ away here).** The 95% CI **excludes +3pp** decisively.

### VERDICT: **REDUNDANT → KILL Probe A**

The structured head does **not** separate farm and bag onto independent directions — the same conclusion as CL-037's scalar (Δ_indep ≈ +0.8pp), but even more decisive (+0.05pp ± 0.36pp). Notable emphasis flip: on the STRUCTURED head, **farm-only carries the entire gain** (+43.5%, = both) while **bag-only (+36.7%) is inert — below even `none` (+37.8%)**; the opposite of the scalar (where bag-only ≈ both). Either way the second axis adds nothing over the best single. The value signal is **genuinely low-dimensional** on this object; the scalar was **not** the bottleneck; the structured object extracts nothing the scalar destroyed. This is a valid decisive outcome that saves the crater screen (§4) and the in-loop budget (§6). **STOPPED at the §3A verdict — no games run.** Per spec §6/charter: combined with Probe B's outcome this routes toward the analyzer.

---

## TASK 2 — does bag unstick the ceiling? (spec open-Q3)  → NO

Fine-tune (ii) vs h6400-Q retrained WITH the bag side-input + cloister pulled out as an exact offset (`train_gtheta.py --bag`; `/home/doctor/carc_probe_a/gtheta_bag/`). All vs the heuristic ceiling **0.0041** (v2.9-vs-Q MSE on TEST):

| head | v_leaf-vs-Q MSE | × ceiling | agg R² |
|---|---|---|---|
| m2 (no bag, cloister IN learnable target) stage-i | 0.0161 | 3.9× | 0.954 |
| **m2.5 stage-i** (cloister EXACT offset, no bag yet) | **0.0069** | **1.7×** | **0.990** |
| **m2.5 stage-ii** (+ bag fine-tune) | **0.0061** | **1.5×** | 0.990 |
| heuristic ceiling | 0.0041 | 1.0× | — |

**Bag does NOT unstick the ceiling** (`stage_ii_beats_heuristic_ceiling = false`). The large improvement over m2 (0.0161→0.0069) came almost entirely from the **exact cloister offset**; the **bag fine-tune added only 0.0069→0.0061** (Δ = −0.0008) and stays **1.5× above the ceiling**. This matches §3A (bag-only inert on the structured head): bag does NOT recover CL-037's ~−20% signal on this object. Note the *aggregate reproduction* is now near-perfect (R²=0.990, τ 0.936→0.940) — the head faithfully reproduces the leaf, but reproducing the leaf ≠ beating it, and bag adds no new orderable magnitude signal. numpy==torch export of the enriched (bag+cloister) head **PASSED** (`checkpoints/probe_a/gtheta_bag_numpy.npz`; comp 5.7e-6, bag 1.8e-7, leaf 2.0e-6). Trained-head enriched speed re-confirmed: structured-only **2.24× PASS**, additive-arm 3.29× (margin).

---

## Files / checkpoints

| what | path |
|---|---|
| bag side-table (314,911 boards, aligned) | `/home/doctor/carc_probe_a/component_ds/bag_sidetable.npz` |
| bag side-table builder | `scripts/probe_a/build_bag_sidetable.py` |
| enriched head (bag_head + cloister offset) | `scripts/probe_a/structured_leaf.py` (`cloister_offset`, `GThetaStub.bag_scalar`, `aggregate_with_offset`) |
| enriched-2.5 speed bench | `scripts/probe_a/enriched25_speed.py` |
| bag trainer (Task 2) | `scripts/probe_a/train_gtheta.py --bag` → `/home/doctor/carc_probe_a/gtheta_bag/` |
| bag/cloister export + numpy==torch verify | `scripts/probe_a/export_gtheta.py` |
| **§3A gate (Task 3)** | `scripts/probe_a/gate_3a_independence.py` → `/home/doctor/carc_probe_a/gate_3a/{summary.json,per_group_regret.npz}` |
| §3A paired Δ_indep σ | `scripts/probe_a/gate_3a_delta_sigma.py` → `/home/doctor/carc_probe_a/gate_3a/delta_sigma.json` |
