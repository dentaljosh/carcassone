# CAPS / CURVE RE-SWEEP UNDER `fixed_v1` — PRE-REGISTRATION (DRAFT)

> **STATUS: 📝 DRAFT — BUILT, SMOKED, NOT AUTHORIZED. Band `1.03e11` is PROPOSED, not
> registered; the orchestrator registers it in `governance/BAND_REGISTRY.csv` before game 1
> and Joshua authorizes the launch. No games of the real band have been played.**
>
> Launcher: [`scripts/classical_search/capscurve_resweep_launcher.sh`](../../scripts/classical_search/capscurve_resweep_launcher.sh) ·
> Cell configs: [`cells/`](cells/) ·
> Conventions parent: [F7B_PREREG.md](../leaf_ablation_20260730/F7B_PREREG.md)
>
> **Nothing in `governance/PRODUCTION.yaml` is touched by this document or this run.**

## The question

Joshua adopted **`fixed_v1`** as the rules profile of record for new eval/desktop work on
2026-08-03 (`06fa067`), and `PRODUCTION.yaml`'s `rules_profile` note gates **absolute
fixed-rules strength claims** on this re-sweep.

**Do the champion leaf's tuned optima — `bonus_cap 8`, `opp_bonus_cap 8`, `curve125` — still
sit where they sat, now that the rules underneath them moved?**

This is `feedback_bug_fix_shifts_optima` applied literally. Two independent shifts:

- **R9** moved **farm decomposition** — and the leaf's caps clamp a closure-anticipation bonus
  whose farm half F7b just measured at **−142.1 elo** (`farmbaseoff`). A term that large sitting
  under a cap is exactly the shape whose optimum moves when the term's magnitude moves.
- **`fixed_v1` moved the meeple economy.** A retail start tile, a redraw rule on an unplaceable
  draw and a fixed cloister scan all change *how many meeples are committed how early* — and
  `v29_meeple_curve` is precisely the meeple-economy term. The curve was tuned against a
  different early game.

Every one of the three optima was established **under `walled`**, in the C5 screens of
2026-07-10..13. None has ever been measured under the rules now in force.

## What this run is NOT

It is not a search for a better leaf. The valuable outcome here is the **powered-ish null** —
"the optima transfer, absolutes unlock as-is". A positive cell is a *finding to confirm*, never
a promotion (see §Decision map).

## Design

**Two axes, six cells, one shared band (CRN).** Candidate = the champion leaf with exactly ONE
knob moved; opponent = the intact champion leaf; **both sides under `fixed_v1` + R9**.

| # | cell | `--cand-leaf-json` | candidate leaf hash | axis |
|---|---|---|---|---|
| 1 | `curve100` | `{"v29_meeple_curve": [-8,-4,-1,0,2,3,4,5]}` | `42af12fce22e1a0f` | curve ×1.00 (the **pre-2026-07-13 champion leaf**) |
| 2 | `curve150` | `{"v29_meeple_curve": [-12,-6,-1.5,0,3,4.5,6,7.5]}` | `165f45134582c7b4` | curve ×1.50 |
| 3 | `cap5` | `{"bonus_cap": 5.0}` | `0a7b068d229e6f25` | own closure cap, below |
| 4 | `cap12` | `{"bonus_cap": 12.0}` | `771fc59803f86ea2` | own closure cap, above |
| 5 | `oppcap4` | `{"opp_bonus_cap": 4.0}` | `f3ca4b52db5a69c3` | opponent closure cap, below |
| 6 | `oppcap12` | `{"opp_bonus_cap": 12.0}` | `a68ab5ebc78d7bf5` | opponent closure cap, above |

Champion side is env-`DEFAULT_CONFIG`, hash **`a36d2e15a3b3d71d`** (recomputed 2026-08-03 under
this launcher's env — unchanged). All six candidate hashes are distinct from it and from each
other, and all six pass `_assert_cy_float_path`.

- **Sign convention:** elo is **candidate − champion**. A **positive** cell says the incumbent
  value is *not* the optimum under `fixed_v1`. A **negative** cell says the incumbent wins its
  neighbour, i.e. the optimum transferred.
- **Deck-paired**, same deck played both colours. **n = 200** per cell (100 decks × 2 seats).
- **One fresh band for all six cells (CRN)** — every cell plays the same 100 decks against the
  same intact champion, so every contrast is within-band deck-paired, the robust class.

### Bracketing — why the caps axis is FOUR cells, not two

The build brief suggested a *symmetric* caps bracket (move `bonus_cap` and `opp_bonus_cap`
together, 5/8/12). **Deviated, deliberately.** The incumbent is the point `(8, 8)`, and the
question is whether that point is still a local optimum. A symmetric move only walks the
diagonal: a null tells you the diagonal is flat and cannot say which coordinate moved, and a
hit cannot be attributed. The C5 cells that *established* cap8 moved the wings independently
(`c5_cap5`, `c5_cap12` at `opp=8`; `c5_oppcap4`, `c5_oppcap12` at `bonus=8`), so four
independent-wing cells both answer the local-optimum question and are the direct
rules-swapped replicate of the evidence PRODUCTION.yaml cites. The cost is two cells.

`curve125` is bracketed above and below per `feedback_bracket_hyperparams`. `×1.25` is an
interior point of the C5 ladder (`×0.75 … ×2.0`), not an endpoint, so a 100/150 bracket is
sufficient here; the wider ladder is not re-run because the walled dose-response was monotone
and its *far* rungs are not candidates.

### Cell configuration

Byte-identical to F7b's cell shape (`--candidate puct --opponent puct`, `--c-puct 1.5 --tau-p 5
--leaf-quantize float --final-select visits`, **sims 2750 both sides**, `--exact-k 2`,
`--backend rust` both sides, net-free, `CUDA_VISIBLE_DEVICES=""`, `OMP/MKL_NUM_THREADS=1`)
**except**:

| Knob | F7b | here | why |
|---|---|---|---|
| rules | `walled` (implicit) | **`--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1`** | the whole subject matter |
| n | 400 (verdict) | **200 (screen)** | screen tier; a hit escalates to a confirm (§Decision map) |
| workers | 32 / 24 | **30 / 26** | CLUSTER_OPS 4th profile, **re-swept 2026-08-03** after the opponent converted to rust |
| `OPENBLAS_NUM_THREADS` | unset | **1** | the C5 curve confirm's "×1.75 hang" was root-caused (`e006036`) to OpenBLAS oversubscription — same axis, comparable W. Free, result-neutral insurance |
| band | 1.00e11 / 1.01e11 (retired) | **fresh, proposed below** | both are retired from confirmatory use |

Every cell writes a self-describing `manifest.json` into `<SHARE>/capscurve_resweep/cc_<cell>/`
carrying `cand_leaf_cfg` + `cand_leaf_hash`, `champ_leaf_cfg` + `champ_leaf_hash`, the per-side
`backend` block, the workers/thread pins, **and the `rules_profile` block** (`name`,
`r9_env_expected`, `r9_env_observed`, `r9_env_ok`). The progress TSV carries `profile` and
`r9_ok` as first-class columns: **a cell whose manifest does not say `fixed_v1` and
`r9_env_ok: true` is void**, whatever the launcher printed.

`exp_id` = `capscurve_<cell>_fixed_v1_vs_puctchamp2750_k2`. The `fixed_v1` substring is load
bearing — `scripts/append_result_row.py:check_rules_profile` refuses a non-walled row whose
`exp_id` does not name its profile, so a fixed-rules number cannot enter the walled record by
accident.

## ⚠️ THE BUILD FOUND A LIVE BUG, AND IT GATES THIS RUN

`eval_puct_priors --backend rust --rules-profile fixed_v1` **did not work before 2026-08-03**,
and it failed *silently*. This combination had never been run: F9 Phase B's `fixed_v1` arm went
through `eval_fair_puct` → `RustFairAgent`, whose geometry `champion_factory` forwards
explicitly. The **clairvoyant** adapters — the ones this harness builds for **both** sides —
seated their mirrors with a bare `MirrorState.from_deck(descs)`, i.e. always on the **engine of
record**, whatever `--rules-profile` said. Measured at ply 0 under `fixed_v1` before the fix:

```
PY : (((18, 15, 'city_top_straight_road', ...),), ...)   # retail start tile, row 18
RS : ((), ...)                                            # empty engine6 board
```

and `_check_sync` is gated on `CARC_RS_RECONCILE` (**default off**), so both graded agents
would have read a different game from the referee with nothing raising.

**Closed in this build** (`src/carcassonne_ai/rust_agent.py`): a new `mirror_geometry_kwargs(game)`
derives the four levers **from the `Game` the mirror mirrors** and both clairvoyant adapters
pass them to `from_deck` / `from_seed`, plus `_draw_order_for_mirror` (the retail
pre-placement inverse `RustFairAgent` already used). The ply-0 digest check is now
**unconditional**, so the silent class is closed structurally rather than by remembering an env
var. `walled` returns `{}` and is byte-identical to before — that is asserted, not asserted-to.

Gate: `tests/test_clairvoyant_mirror_rules.py` (**13 tests, all pass**) — default-off identity,
all four levers reaching the mirror, a full-game referee/mirror lockstep under each profile for
**both** adapters (this is what covers `cloister_scan_fix` and `draw_rule`, which have no ply-0
board tell), the unconditional-check-with-reconcile-off regression, the `window_size`
contradiction refusal, and the loud pre-placement refusals.
Regression: **89 tests, all pass** across `test_puct_priors_opponent_backend`,
`rustport/test_p6_backend`, `rustport/test_p6_persistent`, `test_rules_profile`,
`rustport/test_p4_fair`, `test_fixed_start_tile`, `test_cloister_scan_fix`,
`test_game_wrapper`, `test_fair_agent`. (`rustport/test_p5_flags` and
`rustport/test_cloister_scan_fix_parity` need the built `flat_leaf_cy` `.so`, which lives in the
main tree, not the worktree; both pass there — a worktree artifact, not a regression.)

**Operational consequence:** the laptop must be code-synced (`git bundle`) before it helps. The
change is pure Python in `src/`, so no `maturin`/Cython rebuild is required — but a helper on
stale code would produce `walled` games under a `fixed_v1` manifest, which is the one failure
this run cannot tolerate. **Check the helper's first manifest before trusting its games.**

## Priors on the record (queried before launch, per the results-discipline rule)

All from `experiments/results.csv`, all **`walled`**, all against the **then-champion**:

| cell | walled prior | n | note |
|---|---|---|---|
| `curve100` | **−66.8 ± 17.7 (z 3.45)** | 400 | `c5_s2_curve125_n400` **inverted**: ×1.25 beat ×1.00 by that much. ×1.00 *was* the champion leaf until 2026-07-13 |
| `curve150` | ≈ **−22.3** | 400 | `c5_s2_curve150_n400` (+44.5) minus `c5_s2_curve125_n400` (+66.8), both vs the ×1.00 baseline |
| `cap5` | **0.0 ± 34.7 (z −0.27)** | 100 | `c5_cap5_vs_puctchamp2750_k2` |
| `cap12` | **−13.9 ± 34.8 (z −0.37)** | 100 | `c5_cap12_vs_puctchamp2750_k2` |
| `oppcap4` | **−59.6 ± 35.3 (z −5.13)** | 100 | `c5_oppcap4_vs_puctchamp2750_k2` |
| `oppcap12` | **−66.8 ± 35.4 (z −1.53)** | 100 | `c5_oppcap12_vs_puctchamp2750_k2` |

Two things this table says that the one-line summary in `PRODUCTION.yaml` does not:

1. **`curve100` is a POSITIVE CONTROL with a known walled value.** It is the only cell here whose
   walled effect is large, n=400, and confirmed on two rulers. If it reads ≈ 0 under `fixed_v1`,
   the *instrument* is the first suspect, not the rules — read it as a diagnostic before
   reading it as a finding.
2. **The `bonus_cap` axis was never actually resolved, even under `walled`.** `cap5` read
   `0.0 ± 34.7` and `cap12` `−13.9 ± 34.8` — both deep inside 1σ at n=100. PRODUCTION.yaml's
   "C5 confirmed cap8 optimal" rests on the **opp_cap** wings being negative, and its own comment
   says so. So a null on cells 3–4 here **reproduces a walled null**; it does not upgrade it.

All six priors are **cross-band and cross-era** (the caps cells predate `curve125` folding into
the champion) and take the standing **~1.5–2× σ inflation**. They are *readings*, not verdicts.
The within-cell verdicts of THIS run are within-band deck-paired and unaffected.

## Power — and what this screen CANNOT see

`n = 200` deck-paired, near wr = 0.5:

- unpaired **1σ ≈ ±24.6 elo** (`695·√(0.25/200)`) ⇒ **2σ ≈ ±49 elo**;
- deck-paired margin ~halves the variance ⇒ **1σ ≈ ±17 elo, 2σ ≈ ±35 elo**.

**Say it plainly: this screen resolves ~50 elo (unpaired) / ~35 elo (deck-paired) at 2σ, and
nothing smaller.** Concretely, against the walled priors above it has power for `curve100`
(−67), `oppcap4` (−60) and `oppcap12` (−67), and **no power at all** for `curve150` (−22),
`cap5` (0) or `cap12` (−14). A null on those three is **uninformative about ±20 elo** and must
not be written up as "flat".

That is the deliberate trade. The claim this run is funded to support is *"the optima did not
move enough to invalidate absolute fixed-rules strength claims"*, and a ±20 elo leaf-knob
residual does not invalidate one. **A ±20 elo residual is also not a licence to re-tune**: any
positive cell needs the confirm below before it is anything.

## Decision map (pre-registered, written before game 1)

Read on the **deck-paired margin z**, with the unpaired elo reported alongside.

| Reading | Action |
|---|---|
| **No cell at z ≥ +2.0** | **The current optima TRANSFER at screen resolution.** Absolute fixed-rules strength claims unlock as-is; the `PRODUCTION.yaml` `rules_profile` gate is discharged with the power caveat above recorded verbatim. **This is the expected and the valuable outcome.** No leaf change, no re-tune, no follow-on cells. |
| **Any cell at z ≥ +2.0** | The incumbent value on that axis is a **screen-level candidate to move**. → **CONFIRM at n=400, fresh band `1.04e11`, byte-identical config, that cell only** (pre-priced below; **NOT auto-run** — Joshua's call). Absolutes stay gated until the confirm reads. |
| **Confirm z ≥ +2.0** | A *proposal to Joshua* for the leaf change — **never an automatic promotion**, and note it would itself re-trigger `feedback_bug_fix_shifts_optima` on the other axis. Report the two-band pooled estimate as a secondary. |
| **Confirm \|z\| < 2.0** | Lean UNCONFIRMED. Park suggestive-unpromoted; absolutes unlock on the screen's null. (This is exactly how the F7b `farmgrowthoff` lean closed on 2026-08-03.) |
| **`curve100` NOT strongly negative** | ⚠️ **Instrument alarm, not a finding.** Stop and re-check the wiring (manifest `rules_profile` + `r9_env_ok`, helper code-sync, the ply-0 digest) before interpreting any other cell. |
| Cells strongly **negative** | The incumbent beats its neighbour — the optimum transferred. Expected for `curve100`, `oppcap4`, `oppcap12`. Record; no action. |

No adaptive stopping. **n = 200 fixed** per cell. No `PRODUCTION.yaml` touch under any branch.

## Proposed band (NOT claimed by this file — the orchestrator registers it)

**`1.03e11` — seeds `103,000,000,000 .. 103,000,000,099`** (100 decks × 2 seats = n=200),
**one band shared by all six cells** (CRN).

Verified free 2026-08-03 by **both** prescribed checks:
- `governance/BAND_REGISTRY.csv` — highest registered is `1.02e11` (F9 Phase B, retired today);
  no row ≥ `1.03e11`.
- share-wide census `grep -h seed_start /mnt/c/carc-shared/*/manifest.json
  /mnt/c/carc-shared/*/*/manifest.json` — highest consumed is **`1.09e11`**
  (`f9_wall_probe_20260802/centered18`, which the registry does **not** carry, which is why both
  checks are run). `1.03e11` is unconsumed.

**Pre-priced confirm band: `1.04e11`** (`104,000,000,000 .. 104,000,000,199`, n=400) — reserved
in this document, to be registered only if the decision map fires.

**Smoke band `1.03999e11` is a THROWAWAY** — no `results.csv` row, no band claimed, distinct
out-subdir prefix `ccsmoke_`, and it is ~1e9 seeds clear of the claim band.

## Measured smoke and cost

Run 2026-08-03 through this launcher, local box, `--backend rust`, **W30**, `--smoke --n 4` on
the throwaway band, worktree code (`CC_REPO`), production knobs otherwise byte-identical to the
cells — **plus a saturated-wave (n = 30 = W) throughput pass**, because n=4 measures game
latency and process startup, not throughput. Full numbers and the per-cell manifest evidence
are in [`SMOKE.md`](SMOKE.md). Headline:

- **6/6 cells wired.** Every manifest carries `rules_profile.name = fixed_v1`,
  `r9_env_ok: true`, `rust` on both sides, and the candidate leaf hash this document's cell
  table names — so each cell provably varied the knob it claims to vary, under the rules it
  claims to run. Compute-neutral (`ms_per_move` ratio 0.91–1.06).
- **Mean per-game wall 110.9 s at W30** (median 101.4, max 240.2 — long right tail).
- ⚠️ **`fixed_v1` + R9 cells cost ~1.5× F7b's walled cells** on the identical wave metric
  (448 vs 670 games/h). Do not carry F7b's cost figures onto a fixed-rules cell.
- **Cost: ~1.5 h local / ~0.9 h two-box for the whole 6-cell run** (~15 / ~9 min per cell).
  Plan against local-only; the laptop leg is projected, not measured.
- ⚠️ The throughput pass **peeked**: `curve100` read −34.9 ± 63.8 (paired z −1.32) at n=30 on
  the throwaway band. That is a *positive-control diagnostic* — right sign, right neighbourhood
  of the −66.8 walled prior — not an estimate, and **no threshold in this document was adjusted
  after it**.

## Ops

- Both boxes, work-stealing on the same share dir via `eval_puct_priors.py --shared-claim`
  (`--claim-stale-secs 300`); local = primary (aggregates, writes `results.csv` +
  `SWEEP_PROGRESS.tsv`), laptop = helper.
- **Clock-skew guard armed** (inherited from the F7 launch incident): the launcher writes a
  probe to the share and refuses to start above 60 s skew.
- **Laptop code-sync is MANDATORY before it contributes a game** — see §the build bug.
- `scripts/measurement_infra/run_watchdog.sh` armed on both boxes.
- Launch (per box), after the orchestrator registers the band:
  ```
  nice -n 19 bash scripts/classical_search/capscurve_resweep_launcher.sh auto local
  nice -n 19 bash scripts/classical_search/capscurve_resweep_launcher.sh auto laptop
  ```
  (`auto` → W30 local / W26 laptop; `--backend rust` and `--rules-profile fixed_v1` are the
  defaults and `fixed_v1` is deliberately **not** flag-overridable.)
- Close-out: the six-touch checklist (`results.csv` → DECISIONS index line → status banner on
  this file → `BAND_REGISTRY` row `claimed → retired` → STATUS top block → roadmap line),
  then `python3 scripts/doc_lint.py`.
