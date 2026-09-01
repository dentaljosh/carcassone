# DEVIATIONS — E-1b ARMED CONTINUATION PRICING

Everything that differs from [`PREREG.md`](PREREG.md), from
[`../cl083_redteam_20260830/SYNTHESIS.md`](../cl083_redteam_20260830/SYNTHESIS.md)
§4 E-1(b), or from the funding brief, recorded as it happens. **The PREREG is
never edited after the freeze commit.**

Ceremony: FREEZE commit, then a second commit stamping its sha into
[`BLIND_COMMIT.json`](BLIND_COMMIT.json).

---

## D-0 — the pre-freeze smoke produced four visible armed outcomes (DISCLOSED IN PREREG)

**Status: disclosed in `PREREG.md` §0.1 item 4 before the freeze commit, not a
post-hoc deviation.** Same shape and same reasoning as E-1a's own D-0. Four of
728 units (0.55 %) — the cheapest ply of each stratum, world 0 — were played at
production knobs to prove the arming binds in play and that the emitter emits
what the adjudicator reads. The four `delta_pts_mover` values are tabulated in
§0.1. The units are **kept**: the instrument is deterministic in
`(deck_seed, ply, world, arm, family)`, so the cell recomputes them
bit-identically and they serve as a determinism gate; dropping them would be a
post-hoc filter on a seen outcome.

## D-1 — the arm cap runs at 1800 s CPU, not the nominal `ARM_WALL_CAP_S = 600`

Inherited verbatim from E-1a's D-1, and pre-authorised by `PREREG.md` §2.5. The
cap is an `RLIMIT_CPU` cap and **DRAM-contention stalls are charged to process
CPU time**; E-1a's measured worst arm was 384 s at W = 30, and a 600 s cap would
fire on legitimately slow, contention-hit arms. Every fired cap VOIDS a CRN
pair, so the attrition would be correlated with load and would silently bias
which plies get priced. 1800 s is ~4.7× the measured worst arm — a runaway
guard, not a budget.

## D-2 — ⛔ THE BUDGET IS PINNED TO E-1a's, NOT INHERITED FROM `PRODUCTION.yaml`

**This is a deviation from "re-run the instrument verbatim", and it is the one
that makes the round single-variable.** `governance/PRODUCTION.yaml`
`champion.fair_deploy` moved from **k8 × 1376 = 11008** to **k16 × 1376 =
22016** on 2026-08-30, *after* E-1a ran, and the same fold added a deployed
`tiearb B = 64`. Running the instrument "verbatim" today would therefore have
changed **three** things at once (budget, arbiter, arming) and the number could
not have been contrasted with E-1a's −1.87 at all.

So `continue_armed.py` pins `k_dets = 8`, `sims_per_det = 1376`,
`exact_max_k = 2` and re-asserts them from the RESOLVED rust config on every arm
(`G-BUDGET`). The observed YAML values and a `drift_vs_pin` flag are recorded in
`manifest.json::production_yaml_observed`.

The tie arbiter needed no handling: `make_production_champion` /
`build_fair_champion` do not read `fair_deploy.tiearb`, so an unmodified rebuild
is arbiter-free exactly as E-1a's was. Verified, then recorded.

**The assumption this creates** (also in PREREG §1.3): G1 adjudicated d\* = 0.25
at k16 × 1376. E-1b arms at the same **per-world depth** (1376 sims per
determinization — DESIGN's own measured note says this surface *"needs depth to
express at all"*, with a total flatline at 256) but half the pooled worlds.
Expression is **measured, not assumed**: `G-WITNESS` reads the play-derived
census in every cell, and the pre-freeze smoke measured coverage 1.000 with an
exact `boosted == total − own_mover` partition on all 8 arms at the pinned
budget.

## D-3 — SINGLE BOX (local, W = 32), not the two-box split E-1a used

Per the funding brief. Consequence: the wall goes from E-1a's ~1.4 h to **~2.5
h**, and SYNTHESIS §4's *"~1.1 two-box hours"* should be read as the two-box
figure it is. Nothing about the numbers changes — units are bit-identical at any
W and on any box (`G-REV`-class concerns do not arise with one box, one rev).
E-1a's `plan_boxes.py` remains available if the orchestrator prefers the split.

## D-4 — `scope=own` is NOT an arm of this round

SYNTHESIS §4 E-1 names two candidate exploit-expressing families and DESIGN §5.4
notes that `scope=own` is *"the program's cheapest remaining attempt"* at a
genuinely exploit-PLAYING agent. E-1b runs **`scope=opp` only**, because (a) it
is the arming G1 adjudicated a `d*` for (the dose ladder was scope=`opp`
throughout) and G3 witnessed, (b) it is the arming that removes the specific
blindness DESIGN §0 names, and (c) a second arm would double the multiplicity of
an already bound-limited instrument. `--scope own` is wired, tested and costed
as the **named licensed follow-on**; PREREG §2.2 and §8.1 state the limit this
leaves open in the readout's own words.

---

_(further deviations appended below as they occur)_
