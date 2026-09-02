# DEVIATIONS — τ_p audit leg (2026-09-01)

Everything the build did that a reader of `PREREG.md` alone would not expect, and
everything the build could not do. Written at the freeze, before any cell exists.

---

## D-0 — the eval_fair_puct patch is NOT in the main tree

The one source edit (`scripts/classical_search/eval_fair_puct.py`, §2 of the
prereg) lives in the build **worktree**. A live E-1b run
(`measurement/e1b_armed_continuation_20260901`) was executing on the main tree
throughout the build, and spawn respawns / new `--shared-claim` cells re-import
from disk — so a main-tree source edit could have crashed live workers or created
mixed-rev cells (`feedback_worktree_isolation_live_tree`).

⛔ **The orchestrator merges it at a quiet window.** Until then, the launcher's
plumbing probe (§8.4) is the only thing standing between a stale box and a
champion-vs-champion cell — and it is a *hard refusal*, not a warning.

## D-1 — a 2-game BUILD-TIME DRY CELL was played

To seed the selftest fixture from the **real emitter** rather than by hand (the
fixture trap, three realized incidents) and to verify that every gate address
actually exists in emitted output, the build ran one genuine cell:

    --cand-tau-p 3.0, --opponent fair-champion, k2 x 32, exact-k 2,
    arbiter armed BOTH seats at the deployed dict, fixed_v1 + R9, rust,
    --n 2 --paired --seed-start 171999999000 --allow-selfplay-seeds

* **Throwaway seeds, no band spent.** 171999999000-1 sits in this leg's
  throwaway sub-range.
* **It emits no readable outcome.** Two games at 1/688th of the deploy budget
  decide nothing and may never be pooled or quoted.
* ⭐ It **paid for itself immediately**: three of the four obvious gate addresses
  turned out to be wrong on this emitter — `config.champion.sims` does not exist
  (it is `sims_per_det`), `config.exact_k` does not exist (it is
  `config.endgame.exact_k`), `config.backend` is a dict (`config.backend.name`),
  and `rules_profile` is top-level rather than under `config`. Gates at those
  addresses would have returned `MISSING`, and in any lib that failed open they
  would have passed **vacuously** — the IS-D1 defect.
* The fixture's `SMOKE_REAL_DRY/` keeps that manifest **byte-untouched**;
  `SMOKE_PASS/` promotes **six budget numbers only** (listed in `SPECS.json`)
  because a fixture that genuinely ran k16×1376 would cost ~6 h. Every key path,
  every other value and the whole document shape are the emitter's.

## D-2 — the banked golden gate is a 4-of-12-seed PREVIEW

`TAUP_BITEXACT.json` reads `PASS` on all nine checks, but at
`seeds_played = 4`, not the frozen 12.

**Why.** The build box was saturated by the live E-1b run (loadavg ≈ 38 on 32
threads) and E-1b carries a hard `--arm-cap-secs 1800` per unit, so an added
tenant risks *losing units*, not merely slowing them
(`feedback_no_agent_compute_beside_eval`; the 2026-08-26 quantification). The
gate was therefore run `nice -n 19` on a reduced seed set — about one minute of
one core — rather than the full ~4–5 minutes across three legs.

**How it is prevented from mattering.** `identity_diff.py` records
`seeds_played` / `frozen_seed_count` / `full_frozen_set`, and `run_cells.sh`
**refuses any run that spends compute** unless `full_frozen_set` is true.
`--dry-run` and `--plan` are exempt (they spend nothing) and say so on the
console. The orchestrator re-runs `goldengate/run_gate.sh` at a quiet window
before launch; `BAND_CLAIMED.placeholder` step 6 carries that instruction.

⚠️ The preview is a **real** pass of what it tested — IDENTITY was exact over 4
decks (≈576 PUCT argmaxes/leg) and POSITIVE diverged 4/4 — it is simply not the
frozen gate, and a frozen gate is what may authorize a band.

## D-3 — `W_LAPTOP=24` is a RULING, not a measured settle

The 2026-08-31 arb-on laptop sweep measured W ∈ {18, 22, 26, 28, 30} at this
exact cell shape and settled 26. The owner's 2026-09-01 threads ruling ("w* =
logical threads … 32 and 24") postdates it and names 24, which was never
measured. W is throughput-only — games are bit-identical at any W and no gate
here reads a clock — so this resolves no bar. The ETA is quoted as a **bracket**
(129.0–135.4 g/h) rather than interpolated to a W=24 point.

## D-4 — one banked test changed

`tests/test_fpu_knob.py::test_manifest_carries_cand_search_even_when_the_knobs_are_off`
asserts `config.cand_search` by **exact dict equality**; the two new keys
(`tau_p`, `shared_tau_p`) break it by construction. Updated in place with the
reason recorded beside the assertion. ⭐ It is the **only** banked test the change
touches: every other consumer of `cand_search`
(`fpu_resurrection_prep/screen_lib.py`, `fpu_ladder_prep/screen_lib.py`,
`fpu_h2h_r2_prep/analyze_h2h.py`) digs the dict **by key name**, so the addition
is invisible to them.

Verified: `tests/test_fpu_knob.py test_fpu_instrument.py
test_fpu_h2h_r2_instrument.py test_fpu_ladder_instrument.py
test_opp_tiearb_plumbing.py` → 218 passed with the patch applied.

⚠️ **Pre-existing failures, NOT caused by this change** (confirmed by re-running
the same suite with the patch stashed — identical failures at HEAD):
`tests/test_fair_puct_opponent.py` (7 tests, only when run in the same process as
the fpu suites — a leaf-env pollution across test files; the file passes alone)
and `tests/test_phasegate_instrument.py::test_the_band_is_proposed_not_claimed`
(that round's `BAND_CLAIMED` has since been created, so its
"proposed-not-claimed" guard is stale). Both are out of this leg's scope and were
left alone.

## D-5 — no adjudicator for the REAL cells is shipped here

This leg ships a **smoke** adjudicator (`adjudicate_smoke.py`, structural keys
only) and the gates (`leg_lib.py`), not a full outcome adjudicator. The read-out
is §6's branch map applied to `summary.json`'s `paired_mean_margin` and its
realized SE, which the FPU family's banked machinery already computes. Writing a
fourth copy of that arithmetic would be the drift this leg's "one implementation"
rule exists to prevent. ⚠️ Whoever reads the cells must apply §6 **as written**,
including the retirement rule in §6.1.

## D-6 — `W_LAPTOP` 24 → 22 BETWEEN cells (owner-ordered, result-safe)

Owner, 2026-09-01 ~22:40 EDT, verbatim: "change it at tau8. carcasum is taking 30s a
turn." CELL_TAU3 ran to completion at W=24; CELL_TAU8 runs at W=22 so the laptop keeps
two threads for the owner's pinned-playout Carcasum server (E-5 epoch B: strength is
tenancy-invariant, only his move latency was suffering). W is a scheduling knob and
never a branch input — every game is deterministic in its seeds — so the pair's
adjudication is unaffected; the two cells' manifests will carry different `workers`
values, which the adjudicator must NOT treat as a config-identity defect. Recorded
here because the smoke (W=24) and the TAU8 cell (W=22) are no longer
tenancy-comparable on TIMING fields (irrelevant to this strength leg). Change made
in the main tree, synced to the laptop and re-pinned at the cell boundary — never
mid-cell (the cross-rev-split trap).
