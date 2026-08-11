# Value Resurrection Pilot — LEAF AUDIT (Stage 3 = Gate 1)

> **STATUS: GATE PASSES → proceed to Stage 4 (NOT Decision A).** (2026-06-28. DIAGNOSTIC ONLY.)
> A learnable target *exists* — the v2.9 leaf mis-ranks a real tail of decisive sibling sets — **but
> the leaf is already a very strong sibling ranker (τ=0.895) and the headroom is thin and concentrated
> in opening/midgame high-gap misses, NOT the endgame.** This is the same small-residual regime CL-021
> found unlearnable; Stage 4/5 tests whether a net can exploit it against the v2.9 leaf.

**Method.** `scripts/rod_v2/value_resurrection/leaf_audit.py` over all **10,067** h6400_v2.9 sibling
sets (`n_err=0`, every replay checksum-verified). For each root, rank the **teacher-visited** children
by the v2.9 leaf (`leaf_q`, root-POV) and compare to h6400's `action_q`. POV-corrected (see
[DATASET](VALUE_RESURRECTION_DATASET.md) — fixed-root-seat, τ=+0.90 not −0.90). Regret is in tanh-Q
units (`action_q ∈ [−1,1]`): `regret = q_teacher_best − q_leaf_pick`.

## Headline — the v2.9 leaf is a STRONG sibling ranker

| metric | value | reading |
|---|---|---|
| Kendall-τ(leaf, h6400) | **0.895** | leaf ranks siblings almost like the 6400-sim teacher |
| top1 (leaf picks h6400's best child) | **0.455** | exact-best ~46% |
| top3 (h6400-best in leaf's top-3) | **0.667** | |
| regret (mean / **median**) | 0.0284 / **0.00023** | typical miss is a near-tie (≈0 cost); cost lives in a tail |
| leaf ≠ teacher (top1 miss) | 0.545 | half the "misses" are near-ties that don't matter |

## The learnable target (Gate 1 tallies, n=10,067)

| condition | n | % | 
|---|---|---|
| leaf-top ≠ teacher-top | 5,483 | 54% |
| …and regret ≥ 0.01 | **2,582** | 26% |
| …and regret ≥ 0.02 | **2,083** | 21% |
| …and regret ≥ 0.04 | 1,621 | 16% |
| **decisive** (teacher gap ≥ 0.02 **and** regret ≥ 0.02) | **1,197** | 12% |
| endgame/pre_endgame with regret ≥ 0.02 | 727 | — |

**Gate criterion** (plan: ≥1k held-out sets with leaf-top≠teacher-top **and** regret≥0.01, substantial
subset regret≥0.02 on teacher-confident sets) → **PASS**: 2,582 / 2,083 / 1,197. There is a real target.
(Test split is 15% → ~180 decisive misses available for the Stage-5 gate — enough to measure, thin for a
tight verdict; sized accordingly.)

## Texture — where the headroom is

**By phase** — the leaf is *weakest early, strongest late* (the opposite of the Decision-F hope):

| phase | n | τ | top1 | regret_mean |
|---|---|---|---|---|
| opening | 1,113 | 0.741 | 0.398 | 0.0627 |
| midgame | 2,238 | 0.848 | 0.433 | 0.0498 |
| late_mid | 1,120 | 0.937 | 0.487 | 0.0196 |
| pre_endgame | 2,238 | 0.943 | 0.463 | 0.0170 |
| **endgame** | 3,358 | **0.939** | 0.474 | **0.0133** |

→ The endgame is where the v2.9 leaf is **already best** (τ=0.94, lowest regret). A learned
*endgame-only* residual (Decision F) has the **least** to gain here — consistent with exact-endgame
being outcome-neutral and the net playing the endgame worst (prior). The leaf's headroom is **opening/
midgame** weighted.

**By teacher gap-tier** — headroom is concentrated in **high-gap misses**:

| gap tier | n | top1 | regret_mean |
|---|---|---|---|
| near-tie <0.005 | 4,801 | 0.286 | 0.0137 |
| weak ≥0.005 | 800 | 0.415 | 0.0260 |
| medium ≥0.01 | 786 | 0.503 | 0.0272 |
| strong ≥0.02 | 918 | 0.620 | 0.0285 |
| **very_strong ≥0.04** | 2,762 | **0.693** | **0.0550** |

→ On clearly-decisive sets (gap≥0.04) the leaf already gets 69% exactly right; the remaining ~31% are
the costly misses (regret 0.055). **That ~31%-of-high-gap tail is the entire target** a learned residual
must capture.

## Interpretation — gate passes, but this is the CL-021 regime

- **NOT Decision A.** The v2.9 leaf does not match the teacher *perfectly*; ~1,200 decisive sibling
  sets carry real regret. A target exists.
- **The leaf is already a τ=0.90 structural ranker** — even higher than v2.7's τ=0.579 in CL-021 (different
  teacher/positions, same conclusion: the hand-crafted leaf is a strong sibling discriminator). The
  residual a net must learn is the *fine, high-gap remainder* — precisely the per-position scalar signal
  CL-021 showed a learned head ranks at ~chance (τ 0.03; prod net on millions τ 0.08), "not probe-limited."
- **Decision-F (endgame-only) looks weak a priori:** the endgame is the leaf's *strongest* phase here.
- **The honest expectation is Decision B** (target exists, net can't beat the leaf offline). Stage 4
  trains V1–V5; Stage 5's combined-ranker α-sweep (`leaf + α·learned` vs leaf-alone) is the decider.

**Provenance:** leaf config_hash `7fc930b82801cb43` (frozen v2.9 bmild_cap8); teacher h6400_v2.9;
n_in=n_ok=10,067, n_err=0. Data: `measurement/value_resurrection_pilot/data/leaf_audit_{rows.jsonl,summary.json}`.
