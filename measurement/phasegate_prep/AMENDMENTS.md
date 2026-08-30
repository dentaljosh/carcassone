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

---

## PG-A2 CANDIDATE (flagged 2026-08-30, ⛔ NO CODE CHANGE MADE) — the smoke-mode filter defect is REALIZED in the banked `SMOKE_local.json`

**Raised by:** the `measurement/fpu_resurrection_prep/` pre-launch multi-agent merge review, whose
finding **R1** is the *same defect in the fork*. Flagged here **for the owner**; ⛔ **nothing in
`measurement/phasegate_prep/` was edited** — this round is frozen and already adjudicated.

**The observation.** `SMOKE_local.json` — banked, in-tree — reads `"cells": {}`. Defect 2 above
already named the mechanism in passing (*"smoke archives are not named cells (`cells:{}` —
PG-D10)"*), but it was recorded as a **reason a cell-level gate went unexercised**, not as a defect
in the smoke instrument itself. It is both:

1. The smoke's cell scan and `adjudicate()`'s `specs = L.CELLS` iteration between them mean a
   `SMOKE_*` archive **cannot be adjudicated by either mechanism**, so `cells` is empty by
   construction whenever `--root` is the parent dir.
2. `main()` **returns 0 regardless**, so the launcher's `|| DIE "the smoke adjudication FAILED"` is
   **unreachable** and an empty smoke reads as a passing one.

⚠️ **Read commit `a6acd903`'s subject line against this.** It records *"band 154e9 CLAIMED + three
launcher fixes — both smokes PASS"*. That is accurate about the **launcher exit code**, and the three
launcher defects it names (PG-D7/D8/D9) were genuinely caught pre-round. It is **not** evidence that
any smoke archive was **adjudicated**: `SMOKE_local.json`'s own `round_gates` show `G-WHEEL-SAME`,
`G-REV`, `G-SUBPOOL` and `G-ANCHOR` all `ok: false` beside that "PASS", and with `cells: {}`
**no cell-level gate ran at all.** The word "PASS" and the banked file do not agree.

**Scope of the impact — the banked verdict is believed UNAFFECTED, and confirming that is the
owner's call, not this note's.** The defect is in the **pre-launch smoke**, not in the round read:
the four named phasegate cells were adjudicated normally. What is worth the owner's attention is the
*class* — Defects 1 and 2 above are **cell-level gate** defects (`G-LEAF`, and the round sweep's
treatment of non-cell dirs), i.e. exactly the surface a smoke that adjudicated its own archive would
have exercised first. ⚠️ Stated as a hypothesis, not a finding: this note has **not** re-run the
smoke against the fixed adjudicator to establish that it would have fired.

**Proposed remedy (⛔ NOT APPLIED — needs owner authorization):** the fix shipped in the fork, ported.
`analyze_phasegate.py` would, in `--smoke-mode`, scan **only** `SMOKE_*` dirs (and exclude the real
round cells, so a re-smoke at a populated root cannot report stale round knobs as a smoke PASS),
take the smoke's spec from the launcher, and **exit non-zero on zero adjudicated cells** — making the
existing `|| DIE` reachable. See `measurement/fpu_resurrection_prep/analyze_fpu.py`
(`parse_smoke_cell`, `SMOKE_REQUIRED_GATES`, `smoke_problems`) and
`tests/test_fpu_instrument.py::test_smoke_mode_exits_NONZERO_when_it_adjudicates_nothing`.

**Statistics-blind:** this note reads only structural keys (`cells`, `round_gates[].ok`) off a banked
file and proposes no change to any bar, gate condition, branch or statistic.
