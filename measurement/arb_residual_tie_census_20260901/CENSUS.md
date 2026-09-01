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

**Companion correction landed the same session (owner: "found it starts to flatten
around 100k?"):** rung2 (`../carcasum_rung2_prep/`, results.csv carcasum_rung2_*)
says Carcasum does NOT flatten by 100k — champion margin +5.64 → +4.40 → +2.60 →
+0.67 pts/deck across 16k/65k/131k/262k fixed playouts, still closing ~2 pts/doubling
at the top; the "~16k flattening" was the thesis's self-relative curve. The arbiter's
own dose curve saturates at B≈64 because its playouts only split leaf-exact ties
(pre-filtered residual decisions), not build a ranking from zero prior.
