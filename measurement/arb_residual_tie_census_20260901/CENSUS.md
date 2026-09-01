# Arbiter residual-tie census — 2026-09-01 (owner question, banked data, zero games)

**Question (owner, verbatim):** "how often does our arbiter end on a tie itself?"

**Mechanism of record** ([tiearb.rs](../../rust/carc/carc-core/src/tiearb.rs), the
chosen-arm block): the pick is a strict-`>` argmax over the B per-arm playout means —
an exact residual tie keeps the EARLIEST arm, which is the incumbent leaf tie-break
(the champion's own pick). Deterministic; no salt lottery in argmax mode.

**Rate (computed from the banked offline widening corpus,
`measurement/tiearb_widening_20260817/rung3_r5/legs/s2/tier1-greedy/walled/leg*/records/`,
6,602 CRN pair records over 1,060 tied plies, 32-world bank):**

| statistic | value |
|---|---|
| pairwise exact mean tie at B′=8 | 528/6,602 = 8.0% |
| pairwise exact mean tie at B′=16 | 492/6,602 = 7.5% |
| pairwise exact mean tie at B′=32 | 440/6,602 = 6.7% |
| full-arm-set residual tie (argmax shared ≥2 arms, observed arms, B=32 bank) | 81/1,060 = **7.6%** |

Trend ≈ −0.6 pp per doubling of B ⇒ at the deployed **B=64 expect ~6–7% of fired
plies** to end in an exact residual tie and fall back to the leaf's own pick.
Interpretation: 64 terminal samples per arm found zero mean-margin difference —
overwhelmingly genuinely-indifferent moves; the fallback is benign. Scale context
(2026-09-01 deployed probe, `../wheel_rollin_20260901/bench22016_arbon/summary.json`):
fire rate 55.8% of tile plies, mean 3.36 arms, ≈60 playouts/move amortized.

Method: one python pass over the records (means at CRN-prefix truncations B′;
full-set tie = per-rid max mean shared across observed picks). Arms-per-rid observed
5–13; pairs banked ≈6.2/rid so the full-set figure uses observed-arm subsets — a
slight UNDER-count of the true full-set rate.

## Phase stratification (owner "take the free one", 2026-09-01 — ARMS_R5 k_remaining join, 1,060/1,060 coverage)

| phase (deployed gate buckets) | tied/all | rate |
|---|---|---|
| early (k>48) | 5/371 | 1.3% |
| mid (24<k<48) | 3/338 | 0.9% |
| late (k<24) | 73/325 | **22.5%** |
| edge (k=24,48) | 0/26 | 0.0% |

Tied-ply k_remaining: **median 2**, mean 7.8. Cumulative: k≤2 = 57% of all residual
ties (all-ply base 5%), k≤4 = 74%, k≤8 = 84%.

**VERDICT (descriptive): POCKET-CLOSED-BY-CENSUS.** The majority of residual ties sit
at k_remaining ≤ 2 — INSIDE the deployed exact-solver handoff, where the arbiter never
plays and the ply is already solved exactly. Outside solver range (k>2) the residual-tie
rate is ~3.5% of fired plies, clustered at k 3–8 just above the handoff. The only lever
shape left is marginalized-solve-as-TIEBREAKER at k 3–5 on leaf-tied arms — which sits
in CL-076's shadow (exact-K depth CLOSED; deeper solve buys no wins as a play policy,
a fortiori as a tie-break on indifferent arms) with a few-elo ceiling at ~3% incidence.
Deployed-probe context: actual fires split evenly by phase (20/19/19 in the 2026-09-01
probe) precisely because the solver latch removes the tie-dense k≤2 plies. Corpus
caveat: the census corpus (widening program, self-play plies) includes k≤2 plies that
deployment never arbitrates — deployed residual-tie incidence is therefore LOWER than
the headline 6-7%, ~3-4% of fired plies.

**Companion correction landed the same session (owner: "found it starts to flatten
around 100k?"):** rung2 (`../carcasum_rung2_prep/`, results.csv carcasum_rung2_*)
says Carcasum does NOT flatten by 100k — champion margin +5.64 → +4.40 → +2.60 →
+0.67 pts/deck across 16k/65k/131k/262k fixed playouts, still closing ~2 pts/doubling
at the top; the "~16k flattening" was the thesis's self-relative curve. The arbiter's
own dose curve saturates at B≈64 because its playouts only split leaf-exact ties
(pre-filtered residual decisions), not build a ranking from zero prior.
