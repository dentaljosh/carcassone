# phasegate_prep — adjudication amendments (post-void re-read, IS-A1 precedent)

## PG-A1 — 2026-08-29 ~05:30Z: frozen adjudicator voided a healthy round on two
## instrument-side defects; amended re-read authorized by the ratified envelope

**Frozen verdict:** `U-VOID-INSTRUMENT` (ADJUDICATION.json, retained unmodified).
**Authorization:** the 2026-08-28 Shabbos envelope pre-authorizes "auto amended
re-read / fix-rerun on instrument voids (IS-A1 precedent)" — owner-ratified
("plan looks good to me"). Disclosure, as the IS-A1 precedent requires: the void
readout printed the primary (M +0.4908, se 0.3695, z 1.328) and the anchor
statistic (M +3.464, z 5.908) before this amendment was written; the amendments
below are nonetheless statistics-blind in CONTENT — each fixes a comparison that
is wrong at ground truth independent of any outcome value.

### Defect 1 — G-LEAF is unsatisfiable by construction (screen_lib.py:668)

`curve_ok = str(cand_curve) == LEAF_CURVE` compares the STRINGIFIED CURVE VALUES
against the literal label `"curve125"` (line 73: `LEAF_CURVE = "curve125"`). No
healthy archive can pass. Ground truth verified before the fix:
- PRODUCTION.yaml: curve125 = the C5 fold, `v29_meeple_curve ×1.25`.
- Base curve `[-8,-4,-1,0,2,3,4,5]` ×1.25 = `[-10.0,-5.0,-1.25,0.0,2.5,3.75,5.0,6.25]`
  — exactly what all four cells emitted, both sides.
- Every cell's manifest carries `curve125_leaf_provenance` with
  `leaf_hash == leaf_hash_expected == a36d2e15a3b3d71d` and
  `frozen_config_hash == expected (6dfffd57051690f2)`; `both_sides_curve125: true`.
**Fix:** compare against the resolved curve125 VALUES (list equality), keeping
the label in the message. Statistics-blind: the gate's subject (leaf identity)
is config, not outcome. Why the smoke could not catch it: smoke archives are not
named cells (`cells:{}` — PG-D10), so no cell-level gate ever executed pre-round.

### Defect 2 — round G-REV sweeps non-cells (analyze_phasegate.py:840)

`args.root.iterdir()` admits every dir with a manifest.json: the two SMOKE_*
archives (which ran at the pre-launch commit `49ddcfc3` BY DESIGN — the launch
sequence commits band claim + launcher fixes after smoke) and the `_VOID_*`
quarantined unpaired smokes. G-REV then correctly reports `49ddcfc3-dirty` is
not a prefix of the pin — true, and irrelevant to the round. The four NAMED
cells all canonicalize to the pin (`a6acd903*`). **Fix:** the round sweep skips
dir names starting `SMOKE_` / `_VOID_`. Statistics-blind: sweep scope, no bar or
statistic touched.

### Non-defect — G-ANCHOR

Failed only as a cascade (`anchor_gates_ok` false ⇐ ARB_FULL's G-LEAF). Its own
pre-registered statistic (M +3.464 ≥ bar z 2.0, realized z 5.908) passed. No
change to the gate.

**Procedure:** frozen ADJUDICATION.json retained as ADJUDICATION_FROZEN_UVOID.json;
adjudicator re-run over the SAME emitted archives after the two fixes; the
amended readout is the reading of record, citing this file. Both fixes carry
comment pointers to this amendment at the patch sites.
