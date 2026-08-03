# F7c — LEAF-COMPONENT KNOCKOUT REMEASURE UNDER `fixed_v1` — PRE-REGISTRATION

> **STATUS: 🔵 RUNNING — pre-registered + launched 2026-08-03 evening (laptop first at W18;
> the local box joins by `--shared-claim` when the G2 solver ruler frees it).**
> **AUTHORIZED 2026-08-03 (Joshua, verbatim: *"anticipation remeasure, go for it. start with
> laptop if local is taken"*).** Band `1.05e11` REGISTERED in
> [`governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) in this same commit,
> before game 1.
> Launcher: [`scripts/classical_search/leaf_ablation_launcher.sh`](../../scripts/classical_search/leaf_ablation_launcher.sh)
> (F7c addendum: `--rules-profile`). Cell configs: [`cells/`](cells/) — **unchanged**, shared
> with F7/F7b. Parent runs + conventions: [PREREG.md](PREREG.md) (F7, CL-074),
> [F7B_PREREG.md](F7B_PREREG.md) (the farm rows). Progress: `ABL_PROGRESS_fixed_v1.tsv`.
>
> **Nothing in `governance/PRODUCTION.yaml` is touched by this document or this run**, and no
> claim row is edited here — close-out is the orchestrator's.

## The question

**Does the CL-074 component-value table transfer to the adopted rules profile `fixed_v1`?**

CL-074 priced eight leaf components by knocking each one out — but every cell was played under
the **walled** engine. Joshua adopted `fixed_v1` as the rules profile of record for new
eval/desktop work on 2026-08-03, and the standing rule is `feedback_bug_fix_shifts_optima`
applied here to a whole *rule set* rather than one knob: **R9** moved farm decomposition, and
the four `fixed_v1` levers moved the meeple economy (a retail start tile, a redraw rule and a
fixed cloister scan all change how many meeples are committed how early). Both of those are
*exactly* the axes the component table is about, so its rows are suspect until re-measured.

**The optima are NOT re-tuned first, and that is a measured call rather than an omission:** the
caps/curve re-sweep under `fixed_v1` (`measurement/capscurve_resweep_20260803/PREREG.md`, band
`1.03e11`, 2026-08-03) closed **all six cells null** on the paired margin, so the incumbent
`cap8 / oppcap8 / curve125` still stands under the new rules and the champion leaf this run
knocks components out of is the same leaf, `a36d2e15a3b3d71d`.

## Design

Identical to F7/F7b — same harness, same cell JSONs, same sign convention — with exactly one
axis changed. **Both sides run `rules_profile=fixed_v1` + `CARCASSONNE_FIX_R9=1`.**

- **Contrast:** champion-config agent with ONE leaf component knocked out (candidate) **vs** the
  intact champion leaf (opponent). Identical search config on both sides; the only difference is
  the candidate's `LeafConfig`.
- **Deck-paired**, same deck played both colors. **n = 400** per cell (200 decks × 2 seats).
- **ONE fresh band for all eight cells (CRN):** `1.05e11`, seeds
  `105,000,000,000 .. 105,000,000,199`. Every cell plays the *same* 200 decks against the *same*
  intact champion, so all within-cell contrasts are **within-band deck-paired** — the robust
  class. Verified free 2026-08-03 against BOTH the registry and a share-wide `manifest.json`
  `seed_start` census. F7's `9.60e10` and F7b's `1.00e11`/`1.01e11` are retired.
- **Sign convention:** elo is **candidate − champion**. A knockout is expected to hurt, so
  **negative elo = the component is worth that much**; the component's value is `−elo`.
- **⚠️ Cross-era, not cross-band-within-era.** Every F7c-vs-F7 comparison is *both* cross-band
  *and* cross-rules. It takes the standing ~1.5–2× σ inflation on the cross-band leg and is a
  **reading, not a verdict**. The verdict class here is the within-cell fixed_v1 number itself.

### Cell configuration

Byte-identical to the F7b table (`--candidate puct --opponent puct`, `--c-puct 1.5 --tau-p 5
--leaf-quantize float --final-select visits`, **sims 2750 both sides**, `--exact-k 2`,
`--backend rust`, net-free, `CUDA_VISIBLE_DEVICES=""`, `OMP/MKL/OPENBLAS_NUM_THREADS=1`)
**except**:

| Knob | F7b | F7c | why |
|---|---|---|---|
| rules | walled | **`--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1`** | the whole question |
| band | 1.00e11 / 1.01e11 (retired) | **1.05e11** | fresh; the old bands influenced CL-074 |
| workers | local 32 / laptop 24 | **laptop 18** to start (the box also runs a 4-worker solver bench; Joshua's standing rust heuristic is W = threads − 2, and 18 + 4 = 22 = 24 − 2). Local joins at its own W when free | box contention, not a design change |

**R9 is env-latched at import** — `base_deck` derives the farm data and the Rust registry latches
a `OnceLock` — so `--rules-profile` cannot apply it and only *stamps* whether the launcher did.
Every cell's `manifest.json` therefore carries `rules_profile.name == fixed_v1` **and**
`r9_env_ok == true`; the launcher refuses to aggregate (status `VOID-PROFILE`, no `results.csv`
row) a cell whose manifest says otherwise, whatever the console printed. The `exp_id`
`abl_<cell>_fixed_v1_vs_puctchamp2750_k2` carries the profile into `results.csv`, which is
otherwise the walled record (`append_result_row.py:check_rules_profile`).

## The cells (8) and their walled priors

Priority order (Joshua's ordering; anticipation leads the middle block because it is the
component whose CL-074 reading — *balance, not information* — is the most structural and the
most likely to be rules-sensitive). All priors from `results.csv`, n=400 unless noted.

| # | cell | knockout | walled prior (elo ± 1σ) | what a change would mean |
|---|---|---|---|---|
| 1 | `meepleoff` | `{"v29_meeple_curve": null, "meeple_k": 0.0}` | **−299.6 ± 24.2** | the flagship term; `fixed_v1` moved the meeple economy directly, so this is the row most exposed to the new rules |
| 2 | `meepleflat` | `{"v29_meeple_curve": null, "meeple_k": 2.0}` | **−177.2 ± 19.7** | the curve **shape** slice of cell 1 |
| 3 | `oppanticoff` | `{"opp_bonus_cap": 0.0}` | **−153.4 ± 19.1** | threat-blindness |
| 4 | `selfanticoff` | `{"bonus_cap": 0.0}` | **−88.7 ± 17.9** | the self half |
| 5 | `anticoff` | `{"bonus_cap": 0.0, "opp_bonus_cap": 0.0}` | **−7.8 ± 17.4** | the powered null that produced "anticipation = BALANCE not information". **The additivity check repeats:** if the halves are independent, `anticoff ≈ selfanticoff + oppanticoff`; walled, they were super-additive by ≈ +234 |
| 6 | `capoff` | `{"soft_cap_slope": 1.0, "opp_soft_cap_slope": 1.0}` | **−13.6 ± 17.7** (n=384) | the F6 soft-cap null. Walled it lost 16 games to a deterministic `action_space WindowOverflowError` at the grid wall — **watch for it again**; a cell short of n=400 is reported at its true n, not padded |
| 7 | `farmbaseoff` | `{"farm_base_off": true}` | **−142.1 ± 18.8** | **R9 moved farm decomposition**, so this is the row most exposed to R9 specifically |
| 8 | `farmgrowthoff` | `{"farm_growth_off": true}` | **+42.8 ± 17.5**, confirm **+10.4 ± 17.4** | the parked suggestive-unpromoted deletion lean. A repeat of the positive sign under `fixed_v1` would be a third look at the same axis and is *still* not a promotion — it opens a proposal |

## What each outcome reads as

Power at n=400 deck-paired: **1σ ≈ ±17 elo unpaired, ≈ ±12 elo deck-paired** — a verdict for
effects ≳ 35 elo, a screen below that.

| Reading | Interpretation |
|---|---|
| a cell reproduces its walled magnitude (within ~2σ, σ inflated for the cross-era leg) | the component's value is a property of the *game*, not of the walled engine's quirks — the CL-074 row stands under the rules of record |
| a large component collapses toward 0 under `fixed_v1` | the walled number was partly an artifact of the walled rules; CL-074's row is era-bound and must be re-stated, not just re-cited |
| a null (`anticoff`, `capoff`) becomes large | the balance/inertness finding was rules-specific — the more interesting outcome, and the one that would reopen an axis CL-074 closed |
| `anticoff` ≉ `selfanticoff` + `oppanticoff` again | the anticipation halves interact under both rule sets ⇒ the "balance not information" reading is structural |
| `farmgrowthoff` positive a third time | a deletion candidate with three looks; escalate as a proposal to Joshua, **do not flip** |

**No promotion, adoption, or `PRODUCTION.yaml` edit follows automatically from any cell.** This
run is descriptive.

## Ops

- Launched **detached** (`nohup setsid … & disown`, `nice -n 19`) on the **laptop** first
  (`/mnt/carc-shared`), W18. The local box is occupied by the F9/G2 solver ruler until ~20:30 and
  **joins the same cells by work-stealing** (`--shared-claim`, `--claim-stale-secs 300`) when
  free; the laptop leg runs as `helper`, so the joining local leg is the `primary` that
  aggregates and writes the `results.csv` rows.
- The laptop is code-synced by `git bundle` before launch (remotes cannot reach github). A
  non-walled leg **requires** the 2026-08-03 `rust_agent` build that threads the profile into the
  clairvoyant mirrors (`mirror_geometry_kwargs` + the unconditional ply-0 digest check); without
  it the rust mirror would play the engine of record under a manifest that says `fixed_v1`.
- Close-out (the six-touch checklist) is the **orchestrator's**, at cell landing: `results.csv`
  rows → DECISIONS index line → the status banner on this file → `BAND_REGISTRY` `claimed →
  retired` → STATUS top block → roadmap line, then `python3 scripts/doc_lint.py`.
