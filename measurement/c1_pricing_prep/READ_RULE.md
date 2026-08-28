# READ RULE — C1 OUTCOME PRICING

> **⚠️ Status: DESIGN ONLY — FROZEN, PRE-OUTCOME.** How to read
> `C1_PRICING.json` when it exists, written before it exists. Pre-registration:
> [`DESIGN.md`](DESIGN.md). Machine artifact: `C1_PRICING.json`.

## 1. ⚠️⚠️ FIRST — `arm_owner` IS NOT AN OWNER MOVE

This instrument reuses
[`../e4_continuation_20260828/continue_plies.py`](../e4_continuation_20260828/continue_plies.py)
**unmodified**, and that file hard-codes two arm names. Here they hold different
things:

| the file says | it actually holds |
|---|---|
| `arm_owner` / `played_action` | **the C1 pick** — the tier1-rollout re-ranker's `rollout_argmax` |
| `arm_cf` / `counterfactual_action` | **the production champion's pick** |

**Therefore `delta_pts_mover` reads, mover-signed, as C1 pick MINUS champion
pick.** Positive ⇒ the re-ranker's move was worth more realized points to the
mover. Negative ⇒ the champion's move was.

The archive's own move is carried as `owner_action` in `targets_c1.jsonl` and is
**not an arm** — this run does not price the human at all.
`followup_agrees_with_archive`, emitted by the runner, is **meaningless here**
and appears in no readout.

`adjudicate_c1.py` asserts the remap on every landed row and VOIDs on violation;
`C1_PRICING.json.arm_map` restates it. If you are reading a raw `unit_*.json`,
hold this paragraph in your head.

## 2. Read the branch first, then the number

`C1_PRICING.json.BRANCH` is one of five. Nothing below it is quotable until you
have read it.

| branch | how to say it |
|---|---|
| **C1-VOID** | *"The instrument did not measure this stratum."* Read `instrument_void_reasons`. No price from the affected stratum is a finding — report it as an existence proof with named games. |
| **C1-PRICED-POSITIVE** | *"The rollout re-ranker's picks beat the production champion by X ± SE realized points per divergent ply at [stratum], judge-free."* Quote the **realized** number, never the in-sample gap. Then quote the policy-level price (§4) — that is what deployment buys. |
| **C1-NEGATIVE** | *"The re-ranker's picks are WORSE by X ± SE."* C1 dies. `D_champ` = 0.639 is then re-read as noise-driven re-ranking, and the winner's-curse figure (§5) is the headline. |
| **C1-NULL-BOUNDED** | *"C1's re-ranking is worth less than ±(2·SE) points per divergent ply at these plies"* — **quote the achieved SE in the same breath**. A null here is a BOUND, not a proof of zero. |
| **C1-UNRESOLVED** | *"The instrument did not reach its own design precision."* Say nothing about C1's value. Quote coverage, the achieved SE, and the M that would close it. |

## 3. Which number is the finding

* **P1 = `PRIMARY.P1_farm_capture`** — the pre-registered primary, 14 divergent
  plies in 12 games. Design 2σ MDE ≈ **2.1 pts** ([`SIZING.md`](SIZING.md)).
* **P2 = `PRIMARY.P2_contested`** — the co-primary, 69 plies in 41 games,
  the cut the microgate's GATE-LIVE statistic was defined on. Design 2σ MDE ≈
  **1.6 pts**.
* Both carry `holm_reject`. **A branch fires only on a co-primary that clears 2σ
  AND survives Holm.** Quoting a bare z that failed Holm as a finding is the
  error this section exists to prevent.
* Everything under `secondary` — the per-stratum stats, the all-188 pool,
  `farm_capture_minus_control`, `contested_minus_uncontested` — is
  **hypothesis-generating only**. Not multiplicity-protected. Never promoted
  alone. `n = 14` and `n = 55` cells at these SEs cannot settle anything by
  themselves; the program's own rule is that a lone >1σ value beating its
  neighbours is a noise signature, not a peak.

## 4. `deployment_policy_price` — the number a decision uses

An agreeing ply prices exactly zero, so for each stratum

```
policy_price_per_ply = D_champ × divergent_conditional_price
```

with `D_champ` a fixed constant of the frozen microgates set (0.538
`farm_capture`, 0.671 `invasion`, 0.639 contested). **This is arithmetic, not an
extrapolation.** If someone asks "what would switching C1 on buy per ply", this
is the field; the primary's `mean` is the per-*divergent*-ply price and is ~1.6×
larger. Do not quote the divergent-conditional price as a deployment figure.

## 5. `winners_curse` — likely the most durable output

`mean_insample_gap_pts` is the microgates' own argmax-minus-champion arm value on
the **same 16 worlds the argmax was chosen on** (+6.208 pooled, +6.000 on
`farm_capture`). `mean_out_of_sample_price_pts` is the identical contrast on
**worlds the argmax never saw**. Their difference, with a cluster-robust SE, is
the winner's curse of an argmax over ~8 arms at M = 16 — **measured**.

Quote it that way, and reuse it: any future instrument that argmaxes noisy arms
inherits a bias of this order. It is reportable whatever the branch, including
C1-UNRESOLVED, because it does not depend on the price being resolved — only on
it being measured on fresh worlds.

## 6. `exact_leg_bonus_DIFFERENT_ESTIMAND` — do not pool it

n = 4 plies (1 `farm_capture`, 1 `invasion`, 2 `defense`). It prices each arm
under **optimal play by both seats**; the continuation prices it under
**production-champion play**. **A sign disagreement between the two is not a
bug** — a move can be worth more against the champion than against a perfect
opponent. It is reported alone, never pooled, never voids anything, and
**cannot fire a branch**. If it agrees, say "the four exactly-solvable plies
agree in sign"; if it does not, say exactly that and move on.

## 7. Coverage, before any price

Read `coverage` first:

* `n_plies_priced` vs `n_target_plies` (188), and `n_plies_missing`;
* `worlds_void` / `void_reasons` — **> 10 % on a co-primary stratum is a VOID**,
  and any `crn_witness_mismatch` / `root_state_diverged` /
  `world_not_a_permutation` / `deck_tail_mismatch` / `world_prefix_mutated` /
  `replay_desync` is a BUG SIGNAL, not attrition;
* `world_index_histogram` — every index must be ≥ 16. An index below 16 means an
  in-sample world leaked and the cross-fit is dead;
* `arm_map_violations` — must be empty;
* `achieved_m_worlds` — at small K the distinct-completion set is smaller than M,
  so some plies' SE does not shrink as 1/√M. Two `farm_capture` plies (K = 4 and
  K = 6) are affected by construction;
* `preflight` — the G-LEGAL drop list and its per-stratum drop rate. Any drop is
  a mask-epoch drop by a rule frozen before the freeze, **not attrition**, and
  the dropped plies are named.

## 8. Rules epoch and budget epoch

`profiles` must read `{fixed_v1: …}` and nothing else — `walled` and `app_aug2`
were excluded at build time ([`DESIGN.md`](DESIGN.md) §1.1). `budget_notes`
carries the E4 budget epoch per row; the anchor is **nonstationary**, so no tally
may be read without conditioning on it. This matters less here than in an E4
win-rate tally — both arms of every pair share the same archive and therefore the
same epoch — but it is recorded so the condition is checkable rather than assumed.

## 9. What this run cannot say

* Nothing about the **owner**. The human's move is not an arm.
* Nothing about **position steering**. The 2026-08-28 continuation verdict and
  the ply-pricing inversion put the E4 edge upstream, in reaching positions
  rather than in playing them; this instrument prices a *point decision at a
  handed position* and inherits that limitation whole.
* Nothing about **C1 as a deployed search change**. It prices a re-ranker's pick
  under one-shot substitution; a real C1 would re-rank every ply and compound.
  A positive branch funds *building* C1 and measuring it in games — it is not
  itself an elo claim, and no `experiments/results.csv` row is warranted unless
  the branch is `C1-PRICED-POSITIVE` or `C1-NEGATIVE`.
* Nothing about any **other rules epoch** or any **other champion budget**.
