# Hard-Position Policy Repair — RESULTS

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.**
No promotion · PRODUCTION.yaml / champion / v2.9 evaluator unchanged.
Plan: [HARD_POLICY_REPAIR_PLAN.md](HARD_POLICY_REPAIR_PLAN.md) · Decision:
[HARD_POLICY_REPAIR_DECISION.md](HARD_POLICY_REPAIR_DECISION.md).

Pilot dataset: the fixed 1620-root multiphase pool, labeled with v2.9 rulers
HeuristicMCTS@3200 (classify) + @6400 (deep teacher). 0 errors, 12.6 min local.
**438 hard (h3200≠h6400 = 27%)** + 1182 ordinary; hard split 306 train / 66 val / 66 test.

## 1. Stage 2 — baseline (held-out hard TEST, n=66) — reproduces the autopsy ✓

| net | top1 | top3 | rank | KL | lean | P_neither |
|---|--:|--:|--:|--:|--:|--:|
| rod1   | 0.091 | 0.242 | 12.0 | 1.78 | −0.061 | 0.758 |
| iter04 | 0.091 | 0.227 | 12.0 | 1.49 | −0.015 | 0.803 |
| iter06 | 0.121 | 0.212 | 11.9 | 1.62 | +0.045 | 0.803 |

`lean ≈ 0`, `P_neither ≈ 0.78`, endgame top1 0.00–0.05 with negative lean — the autopsy
signature, reproduced on an independent held-out set. The metric harness is validated.

## 2. The target is signal-free on disagreement states (the pivot)

**h6400 visit distribution on hard states is ~uniform.** Mean top-move share **0.04**
(median 0.03), entropy 3.57 vs uniform floor 3.68; 99% of states have top_share < 0.20,
**0% > 0.50**. Ordinary states are also flat-ish (top-share 0.074) → the flat visit
distribution is a **property of HeuristicMCTS** (broad exploration), not specific to hard
states. `best_action` ranks by **Q**, not visits (confirmed in code; best==most-visited 1.00).

**The Q-values are near-tied at the top on hard states.** Q-gap between the #1 and #2 move:

| state set | Q gap #1−#2 (mean) | median | Q gap #1−median |
|---|--:|--:|--:|
| HARD (h3200≠h6400) | **0.0021** | **0.0007** | 0.083 |
| ORDINARY (agree)   | 0.0402 | 0.0133 | 0.093 |

(value scale: full best-worst range ≈ 0.17.) Hard-state distribution: p50 0.0007, p90 0.0045,
p95 0.0056 — **only 3% of hard states have a gap > 0.02**, 0% > 0.05. The reason h3200 and
h6400 *disagree* is precisely that their top two moves are **value-tied to ~0.002** — argmax
flicker on indifferent positions, **not** a deep strategic distinction. "h3200≠h6400
disagreement" selects **value-indifferent** states, not deep-distinctive ones.

## 3. Stage 3/4 — repair from iter04 (policy-only, --aux-weight 0 --value-loss-weight 0)

Held-out hard TEST (n=66):

| variant | target | TRAIN top1 | TEST top1 | TEST lean | TEST P_neither |
|---|---|--:|--:|--:|--:|
| iter04 (P0 baseline) | — | 0.105 | 0.091 | −0.015 | 0.803 |
| P1-visit | h6400 visit dist | — | 0.076 | −0.030 | 0.818 |
| P1-onehot (aggressive) | h6400 argmax (one-hot) | **0.775** | **0.061** | −0.106 | 0.773 |

- **P1-visit** drove KL to the (flat) target down 1.49→0.15 but top1/lean did not improve
  (got slightly worse, rank 12→16): training to a flat target just flattens the policy.
- **P1-onehot** *memorized* the train argmax (TRAIN top1 0.775, lean +0.752) — proving the net
  has full **capacity** to learn "pick h6400's move" — yet **generalized to 0.061 on held-out,
  below the 0.091 baseline.** The train→test collapse is total: the memorized argmax is
  position-specific **noise** (Q-gap median 0.0007) that cannot transfer.

**Not a capacity problem, not a training problem — a signal problem.** The held-out hard-state
metric does **not** move (Stage-4 pass/fail = FAIL).

## 4. Stage 5 — ordinary-state regression (n=1182)

| net | top1 | top3 | rank |
|---|--:|--:|--:|
| iter04 | **0.311** | 0.541 | 7.0 |
| p1_visit | 0.288 | 0.484 | 9.0 |
| p1_onehot | 0.271 | 0.497 | 7.4 |

iter04's top1 on ordinary states (0.311) is **3.4× its top1 on hard states (0.091)** — the
policy *is* aligned with h6400 exactly where h6400 is decisive (Q-gap 0.040). The fine-tunes
mildly **degraded** ordinary alignment (forgetting from a narrow 306-state fit), no catastrophic
collapse. Repair neither helped hard states nor preserved ordinary ones.

## 5. What this means

The policy's "diffuseness on disagreement states" — the autopsy's headline failure signal — is
the **correct** response to value-indifferent positions, not a learnable failure. There is no
generalizable signal to absorb on these states because the deep teacher itself is indifferent
there (top moves Q-tied to ~0.002). See the decision doc for A/B/C/D + the named boundary.

## Reproduce

`scripts/rod_v2/repair/`: `mine_label.py` (label+split) · `hardset_eval.py` (metrics) ·
`probe_q_separation.py` (Q-gap) · `relabel_onehot.py` (one-hot target) · `run_pilot.sh` (driver).
Checkpoints: `/mnt/c/carc-shared/hard_policy_repair/{p1_from_iter04,p1_onehot_from_iter04}.pt`.
