# Step 1 — Representation gate: RESULTS

**Date:** 2026-06-29 · **Charter:** superhuman program §7 Step 1 (the decision gate) · **Status:** 🟢 RUNNING (none + both) · **MEASUREMENT ONLY** — no production change.
**Scripts:** `scripts/feature_planes_gate/{step1_planes,step1_dump,step1_train,run_gate}.py/.sh` · **Datasets:** `/home/doctor/carc_step1_gate/dataset_<mode>/` (ext4, streamed) · **Out:** `measurement/feature_planes_gate/stage_<mode>/`

## The question

CL-033 found a learned value/ranker on the **78-channel** board representation cannot out-rank the v2.9 leaf at sibling ordering (best α=0, net-alone Kendall-τ ~0.10 vs leaf ~0.895). Hypothesis (charter): the value head is inert because the representation is **blind to farm connectivity and the bag**. Give it those as inputs and re-run the CL-033 sibling-ranking protocol (same 10,067 roots, same h6400_v2.9 oracle_q / v2.9 leaf_q, same RankNet, same α-sweep) on:

| mode | obs planes | scalars | what it adds |
|---|---|---|---|
| `none` | 78 | 12 (incl farm scalars) | **baseline** — this enumeration's α=0 reference |
| `farm` | 78+3 | 12 | live farm-connectivity planes (mine/opp/contested per cell, from `flat_leaf.decompose`) |
| `bag`  | 78 | 12+32 | per-tile-type bag histogram (32 base types) |
| `both` | 78+3 | 12+32 | farm + bag (the full hypothesis) |
| `both_shuffled` | 78+3 | 12+32 | **negative control** — planes permuted across roots; must NOT help |

> The enumeration keeps all teacher-Q'd legal children (~314,911 rows, like CL-034's), so `none` is the apples-to-apples baseline *for this enumeration*, **not** a byte-reproduction of CL-033's 124,842-row teacher-visited variant. The gate is **`both` vs `none` on the same enumeration**. Baseline sanity: `none` should land α=0 / net-alone τ ~0.08–0.12 (consistent with CL-033's spirit); if `none` doesn't, debug before trusting +planes.

## Pre-registered verdict criteria (LOCKED before the numbers — do not move the goalposts)

- **PASS** (representation is the issue; reopen the flywheel → Step 2): with farm+bag vision, **net-alone τ moves materially toward the leaf's 0.895 — say > 0.4 — OR `leaf + α·net` selects α > 0 with a real regret reduction (≥ ~15%)**, AND no ordinary-position regression, AND the `both_shuffled` negative control does **NOT** pass.
- **FAIL** (classical ceiling stands → pivot toward the analyzer): **α stays 0 and net-alone τ stays < ~0.3** with farm+bag vision (≈ CL-033 unchanged). Do **not** scale this representation.
- **Ambiguous** (τ ∈ ~[0.3, 0.4] or small-but-real α>0): power up — all 5 RankNet variants (not just V4_listwise) + the `both_shuffled` control + a leak check — before calling it.

Guardrails: gate on the **held-out test split** (group-split by game_seed, never row-level); `both_shuffled` is the spuriousness check; if `both` passes, confirm no plane trivially encodes oracle_q/leaf_q (leak check).

## Negative-control LOCK criteria (pre-registered 2026-06-29, BEFORE the control's number printed)

The bar is **"indistinguishable from the `none` baseline,"** NOT merely "lower than +20.5%". Three conditions, all required to lock CLEAN:

1. **Regret reduction collapses to the `none` noise floor:** `both_shuffled` ≤ ~**5%** (vs `none`'s +1.9%; i.e. ≥ ~75% of the +20.5%→+1.9% distance is given back). A residual ≥ ~10% (keeps half the effect) = **DIRTY**.
2. **α returns to ~0** (0 or 0.05-with-negligible-reduction; NOT climbing).
3. **No sub-`none` val-loss leak:** control `best_val_loss` ≈ `none`'s **3.3020** (say ≥ ~3.300), **not** drifting toward `both`'s **3.2958**. A converged plateau materially below 3.300 means the shuffled channels leak structure → the +20.5% is partly contaminated even if (1)/(2) pass.

**Two-gate framing (per external review 2026-06-29 — keep these separate):**
- **Gate A — the scientific lock (this control + ablation):** confirms the farm/bag *representation* carries value signal the blind 78-ch net could not access → refutes CL-033's "value head inert as an architecture-independent law." This is the **load-bearing result** and the only thing the control locks. We are **under** the τ>0.4 alternative bar (τ=0.207 ≪ leaf 0.895), so the lock rests on the **α>0 clause alone**: *representation was a real confound; the value head is now a weak-but-nonzero ranker* — not "rivals the leaf."
- **Gate B — conversion through search (Step 2's question, NOT locked here):** whether this signal survives MCTS. **Open and arguably trends against a static-integration win:** CL-034's bigger −41% offline washed out at the sims=200 search screen (search alone cuts the static leaf's decisive regret ~6×). ⚠️ **A CL-034-style washout on a one-shot search screen does NOT kill Step 2** — the loop (trajectory reshaping + policy-target evolution across iters) is the arbiter, which a fixed-position screen structurally cannot test. Run a search-integrated screen only if cheap, and pre-commit that a **fail downgrades confidence, does not kill**. (Re-killing on the screen would re-commit the exact error the charter exists to undo.)
- **Why our smaller number may be the more relevant one:** the −20.5% is a value head doing the leaf's *actual job* (ordering children by evaluated value) = the right object for Step 2's leaf, whereas CL-034's −41% was a sibling-relative ranker that doesn't transfer cleanly to a leaf evaluator. **Smaller number, more relevant object.** The α>0 flip *justifies* the Step 2 bet; it does not *de-risk* it — spend on Step 2 eyes-open.

## Results

| mode | net-alone τ (V4) | best α | regret: leaf→best | reduction % | beats_leaf | n_test |
|---|---|---|---|---|---|---|
| none | 0.140 | 0.05 | 0.0263→0.0258 | **+1.9%** | true | 1544 |
| both | **0.207** | 0.05 | 0.0263→**0.0209** | **+20.5%** | true | 1544 |
| **both_shuffled** (neg control) | **0.139** | **0.0** | 0.0263→0.0263 | **+0.0%** | **false** | 1544 |
| farm-only (drop bag) | _running (ablation)_ | | | | | |
| bag-only (drop farm) | _queued (ablation)_ | | | | | |

## Verdict — Gate A LOCKED CLEAN (negative control passed 2026-06-29; ablation in flight)

**Negative control (`both_shuffled`) PASSED all three pre-registered lock conditions decisively:** with the farm planes + bag scalars permuted off their true rows, net-τ collapsed 0.207→**0.139** (back to `none`'s 0.140), best-α dropped 0.05→**0.0** (the model correctly finds the scrambled features useless and falls back to leaf-alone), regret reduction →**+0.0%** (vs `both`'s +20.5%), and `best_val_loss`=**3.3014 ≈ `none`'s 3.3020** (no sub-`none` leak; never drifted toward `both`'s 3.2958). **The +20.5% is real and position-aligned — not a leak/artifact.** Gate A (the scientific lock: the farm/bag *representation* carries value signal the blind 78-ch net could not access) is **LOCKED**. CL-033's α=0-as-architecture-independent-law is refuted. (Gate B — search conversion — remains Step 2's open question; see the two-gate framing above.)

Remaining for the full attribution story (NOT lock-blocking): the farm-only / bag-only ablation (which feature drives the +20.5%).

---

`both` **meets the pre-registered α-criterion**: α=0.05>0 with **+20.5% regret reduction** (≥15%), vs the blind `none` baseline's noise-level **+1.9%**. Net-alone τ also lifts 0.140→0.207. **This contradicts CL-033's α=0 on the 78-channel blind representation → the representation WAS part of the value head's inertness.** A genuine positive — the first in the program that says "representation, not just heuristic ceiling."

**Qualifiers (do not over-claim):**
1. α is small (0.05) and net-alone τ=0.207 ≪ the leaf's 0.895 — the net adds a small *sighted residual correction*, it does not replace the leaf. This is the residual regime, not "the value head became the value function."
2. **Confirmations still owed before locking PASS:** the `both_shuffled` negative control (shuffled planes must NOT reproduce +20.5% — else spurious) and the farm-only/bag-only ablation (attribution).
3. **CL-034 precedent:** an analogous offline ranking win (−41% with scalars) **washed out under MCTS search**. Offline ≠ in-game; Step 2 is the real test.

**Architecture finding (answers the "lighter net?" question):** this heavy 32GB dense-CNN got +20.5%; **CL-034's cheap scalars+linear got −41%** (beat the leaf outright). The light explicit-feature model is **both faster and stronger** at this task — the dense-CNN-on-board is the wrong tool. → run the negative control + ablation via the cheap scalar/MLP path, and design Step 2's value head as **structure-aware (feature-MLP / set-transformer over tiles), not a dense CNN.**

**Next:** negative control (`both_shuffled`) + farm/bag ablation (fast path) → if the control is clean, lock PASS → CL-037 + scope Step 2.

## Notes / provenance

- **Streaming dump** (obs → raw f16 on ext4, memmap-loaded at train) after the original accumulate+`np.concatenate` model OOM'd the WSL VM (~61GB peak on the 42GB cap; uptime confirmed a reboot). Peak RAM now ~workers-only (W30 ≈ 21GB, measured flat at 6GB during the loop). Discarded the all-modes `step1_dump_all.py`; per-mode `step1_dump.py` is the live builder.
- Frozen v2.9 leaf config (curve `-8,-4,-1,0,2,3,4,5`, cap8, hash `7fc930b82801cb43`); farm planes reuse `decompose.farm_pos0_root`/`farm_root_keys`/`_winners` — the leaf's own farm scoring (fast Cython path), so plane ownership is consistent with how the leaf scores farms. Bag = 32 base-tile types, frozen census (sums to 72).
- On **PASS** → register CL-037, scope Step 2 (Cython-port planes into `flat_repr_cy`, warmstart at new width, the weaned net-value-leaf loop on the orchestrator). On **FAIL** → CL-037 closes the representation lever; pivot per charter endgame 2 (ship the analyzer).
