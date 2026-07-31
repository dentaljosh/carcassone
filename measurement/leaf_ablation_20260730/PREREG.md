# LEAF-COMPONENT KNOCKOUT ABLATION — PRE-REGISTRATION

> **STATUS: PRE-REGISTERED 2026-07-30, LAUNCHING overnight (both boxes, work-stealing, W16).**
> Committed BEFORE the first game of the run (house rule: prereg before results).
> Authorization (Joshua, 2026-07-30, verbatim): *"run it overnight. both boxes, work stealing, w16."*
> Launcher: [`scripts/classical_search/leaf_ablation_launcher.sh`](../../scripts/classical_search/leaf_ablation_launcher.sh).
> Cell configs: [`cells/`](cells/). Progress: `ABL_PROGRESS.tsv` (written by the primary).
>
> **Nothing in `governance/PRODUCTION.yaml` is touched by this document or this run.** No leaf
> source code was changed — every knockout is an EXISTING `LeafConfig` field (see §"No code change").

## The question

**What is each modular component of the production champion leaf worth, in elo, under the
CURRENT champion search (PUCT + heuristic priors)?**

The champion leaf is **v2.9.2 `Bmild_cap8_curve125`**, runtime fingerprint **`a36d2e15a3b3d71d`**
(verified against `governance/PRODUCTION.yaml` at 2026-07-30 23:0x). Its computation is:

```
score = base_virtual_final_score(self − opp)                      # the virtual-score CORE
      + capped(closure_anticipation(self), bonus_cap=8)           # self unfinished-feature credit
      − capped(closure_anticipation(opp),  opp_bonus_cap=8)       # opponent threat term
      + curve125(free_meeples_self) − curve125(free_meeples_opp)  # meeple-economy curve
```

The record has **adoption-time marginals only, and under dead search regimes** — see
[docs/LEVER_INDEX.md](../../docs/LEVER_INDEX.md) §6. Every leaf number we own is a *reweight*
(cap5 vs cap8, curve×1.0 vs ×1.25, slope dose) measured when it was adopted, often under
random-expansion UCT. **Nobody has ever removed a whole component and measured the hole.**
CL-051 is the reason this matters: the meeple curve ×1.25 was **NULL under random-expansion
UCT and a WIN under PUCT+priors** — a leaf knob's value is a property of the search that
consumes it, so adoption-era marginals do not transfer to the champion of record.

This run is the first systematic **subtractive** ablation, and is intended as the flagship
table for Phase 6 (heuristic research).

## Design

- **Contrast:** champion-config agent with ONE leaf component knocked out (candidate)
  **vs** the intact champion leaf (opponent). **Identical search config on both sides** —
  the ONLY difference is the candidate's `LeafConfig`.
- **Deck-paired**, same deck played both colors. `n = 400` per cell (200 decks × 2 seats).
- **ONE fresh deck band for every cell (CRN):** `9.60e10`, seeds
  `96,000,000,000 .. 96,000,000,199`. Every cell therefore plays the *same* 200 decks against
  the *same* intact champion — all contrasts are **within-band, deck-paired**, the robust class
  (CLAUDE.md: cross-band z's get ~2× humility; within-band deck-paired contrasts are unaffected).
  Band verified free 2026-07-30 against BOTH `governance/BAND_REGISTRY.csv` and a share-wide
  `manifest.json` `seed_start` census. Claimed in the registry in the same commit as this file.
- **Sign convention:** reported elo is **candidate − champion**. A knockout is expected to
  *hurt*, so **negative elo = the component is worth that much**. The component's value is `−elo`.

### Cell configuration (identical for all cells, C5/C7 classical-screen precedent)

| Knob | Value | Why |
|---|---|---|
| harness | `scripts/classical_search/eval_puct_priors.py` | the C5/C7 leaf-A/B harness; `--cand-leaf-json` is the per-side leaf override built for exactly this |
| candidate / opponent | `puct` / `puct` | **PUCT + heuristic priors** — the champion search family (the CL-051 lesson) |
| sims | **2750 both sides** (equal-sims; the harness forces `opp_sims = cand_sims`) | the C5/C7 screen convention and the clairvoyant ruler budget. Deliberately **NOT** the k8×1376=11008 fair deploy budget |
| `--c-puct` / `--tau-p` | 1.5 / 5 | the confirmed champion-sibling knobs |
| `--leaf-quantize` / `--final-select` | `float` / `visits` | ditto |
| `--exact-k` | 2 | exact clairvoyant endgame handoff, identical both sides (does not affect the A/B margin) |
| leaf substrate | flat leaf, **Cython float fast path**, `USE_CY_LEAF=1` | see below |
| workers | **W16 per box** (local 5900XT + laptop) | Joshua-specified. Note this is *below* C7's net-free W30/W22 — a deliberate deviation, see §Deviations |
| net / orchestrator | **none** | heuristic-only cells, pure CPU, `CUDA_VISIBLE_DEVICES=""`, `OMP_NUM_THREADS=1` |

Every cell writes a self-describing `manifest.json` (full resolved config incl. per-side
`leaf_cfg` + `leaf_hash`) into its own share dir `/mnt/c/carc-shared/leaf_ablation/abl_<cell>/`.

## The ablation set (6 cells)

All six are **existing `LeafConfig` fields**, all verified to stay on the Cython float fast
path and to be **bit-exact `cy == pure-python`** on 360 mid-game states (2026-07-30).

| # | cell | knockout (`--cand-leaf-json`) | candidate leaf hash | what it removes |
|---|---|---|---|---|
| 1 | `meepleoff` | `{"v29_meeple_curve": null, "meeple_k": 0.0}` | `15477283b5e8bfad` | the **entire meeple-economy term** — both the adopted curve125 AND its flat `meeple_k` predecessor. The leaf stops pricing free-meeple liquidity at all. |
| 2 | `oppanticoff` | `{"opp_bonus_cap": 0.0}` | `8557800fc361ee1e` | the **opponent threat term** — the leaf stops subtracting the opponent's closure anticipation. Threat-blind. |
| 3 | `anticoff` | `{"bonus_cap": 0.0, "opp_bonus_cap": 0.0}` | `564dd31ec4e509b4` | **all closure anticipation, both sides** — the whole unfinished-feature-credit machinery (city closure + cloister completion + farm growth). The leaf becomes pure virtual-final-score + curve. |
| 4 | `selfanticoff` | `{"bonus_cap": 0.0}` | `168aaa1ba4ec3378` | the **self** half of closure anticipation only. |
| 5 | `meepleflat` | `{"v29_meeple_curve": null, "meeple_k": 2.0}` | `d2f22db46202841d` | the curve **SHAPE** only — reverts to the v2.7 flat `meeple_k` term. Decomposes cell 1 into "having any meeple term" vs "having the curve". |
| 6 | `capoff` | `{"soft_cap_slope": 1.0, "opp_soft_cap_slope": 1.0}` | `2b34ad1be93a60a2` | the **cap8 clamp** on both sides (slope 1.0 == identity == uncapped anticipation). Not strictly subtractive — it removes a *limiter*, so it may go either way. |

`_capped(bonus, 0.0)` returns 0 for all bonuses (the anticipation bonus is a sum of
non-negative `P × delta` contributions), so cells 2/3/4 are exact zeroings, not clamps.

**Additivity check built in:** cells 2 + 3 + 4 are nested. If the leaf's two anticipation halves
are independent, `elo(anticoff) ≈ elo(selfanticoff) + elo(oppanticoff)`. A large super-additive
gap means the two halves interact (the leaf's value comes from the *difference* of threats, not
from either side alone) — itself a Phase-6 finding.

### Prior measurements on these axes (queried before launch — CLAUDE.md results-discipline rule)

- **`capoff` is the one cell with a near-duplicate prior.** `results.csv`
  `f6_softcap1p0_vs_champion` (2026-07-23, n=400): slope 1.0 **SELF side only**, in the FAIR
  `k4×688` harness → **+0.00 ± 17.4 elo**, a clean powered null; LEVER_INDEX §6 records the
  soft-cap channel as *"flat-to-negative at every slope ⇒ the leaf-accuracy channel is confirmed
  closed."* The `bonus_cap` axis more broadly is *"the longest null record in the project"*
  (CL-028), and `c5_cap5`/`c5_cap12` were null at n=100 under this exact PUCT harness.
  **Cell 6 is therefore expected null and is priority LAST.** What it adds that the record does
  not have: the **opponent-side** uncap (never measured) and the clairvoyant PUCT harness.
- **`oppanticoff`:** the asymmetric-opponent-cap kill stands on the C5 cells (`c5_oppcap4/12`),
  but those are *dose* changes within a live cap. A knockout to **0** is far outside that range
  and has never been run. LEVER_INDEX also flags the v3-era source entry as having a measured
  1-of-2 error rate, so the dose null is weak evidence about the term's existence.
- **`meepleflat` / `meepleoff`:** `v28_meeple_flat_vs_v27_heur200_n200` measured the flat term at
  **+179.5 ± 27.9** — but as a *pure-leaf* contrast in a pre-PUCT era against a v2.7 reference.
  It is a prior on the sign, not a prediction of the magnitude here.

### Deferred cell — farm terms (NOT in this run, and why)

The task brief asked for farm terms. **They are not config-severable and are deferred**, with a
measured reason rather than an assumed one:

- The farm contribution enters in two places — the farm points inside `flat_base_score`, and the
  farm-growth block of `flat_closure_bonus` — and **neither has a `LeafConfig` knob**. Knocking
  either out requires a new default-off field in `flat_leaf.py`.
- The Cython leaf (`flat_leaf_cy.pyx`) could not honor such a field, so those cells would have to
  run the pure-Python flat leaf **on both sides**. That is fair, but **measured 2026-07-30 at
  12.5× the Cython cost** (23.3 µs/leaf cy vs 290.2 µs/leaf pure-python, 162 mid-game states) —
  which turns a ~3 h cell into ~37 h. Infeasible in an overnight window.
- Implementing the gates in the `.pyx` (+ rebuild on both boxes + bit-exactness tests) is the
  correct path, but it cannot be *used* tonight either: the night's binding constraint is cell
  wall-clock, and the queue below already overflows it.

Queued as follow-up on [docs/PROGRAM_ROADMAP_2026-07-07.md](../../docs/PROGRAM_ROADMAP_2026-07-07.md).

## No code change

Every knockout is an existing `LeafConfig` field reachable through the already-built
`--cand-leaf-json` override. **`src/` and `engine/` are untouched** — so the worktree-isolation
rule (never edit shared source while a run is live) is satisfied trivially, and there is no
"does the intact config still produce identical output" risk to test for. Verified before launch:

1. `_leaf_hash(DEFAULT_CONFIG) == a36d2e15a3b3d71d` — the harness resolves the champion leaf of
   record from the launcher's env.
2. All 6 candidate configs pass `_assert_cy_float_path` (they stay on the fast path; `capoff`
   needs `SUPPORTS_F6_SOFT_CAP`, **verified True on both boxes**).
3. All 6 are bit-exact `cy == pure-python` across 360 mid-game states, and all 6 genuinely differ
   from the champion leaf (85–352 of 360 states differ; max |Δ| 4.75–12.5 points).

## Priority order

`n=400` **completes per cell** rather than spreading thin across cells — a partial night yields
whole verdicts, not six underpowered ones. The `--shared-claim` work-stealing queue makes the
remainder resumable with zero replay.

1. **`meepleoff`** — the flagship. The meeple-economy axis is the one that produced the last real
   leaf gain (CL-051) and its *absolute* worth has never been measured.
2. **`oppanticoff`** — opponent/threat modeling, genuinely never knocked out.
3. **`anticoff`** — the largest single knockout; also the upper bound for cells 2 and 4.
4. **`selfanticoff`** — completes the additivity check.
5. **`meepleflat`** — shape decomposition of cell 1.
6. **`capoff`** — expected null (see priors above); last.

## What each outcome reads as

Power at `n=400` deck-paired: **1σ ≈ ±17 elo unpaired, ≈ ±12 elo deck-paired**. So a cell is a
**verdict** for effects ≳ 35 elo (2σ) and a *screen* below that. Knockouts of load-bearing terms
should be far outside that band; this is a design where the interesting outcome is a *small* number.

| Reading | Interpretation |
|---|---|
| **elo ≪ 0 (≲ −50)** | The component is **load-bearing**: it carries real strength under the champion search. Phase-6 headroom lives on that axis — a term this valuable is worth trying to *improve*, and its shape is worth re-deriving rather than re-weighting. |
| **elo ≈ 0 (\|elo\| < 25, i.e. < 2σ)** | The component is **inert under this search**. It survives in the leaf for historical reasons, not because it earns its keep. Two consequences: (a) it is a **deletion candidate** (a cheaper leaf at equal strength is a real win — the leaf is the search hot path), and (b) **nobody should sweep it again** — every past and future reweight of an inert term measures pure noise. This is the single most useful outcome for pruning the Phase-6 search space. |
| **elo > 0 significantly** | The component is **actively harmful** — removing it makes the agent stronger. That is an immediate, free production change and would be escalated to Joshua rather than folded silently. |
| `anticoff` ≉ `selfanticoff` + `oppanticoff` | The two anticipation halves **interact**; the leaf's value is in the threat *differential*, not either side. Argues against ever tuning the two caps independently (which the whole `c5_oppcap*` / `phase4_cap*` line of work did). |
| `meepleoff` ≪ `meepleflat` ≈ 0 | The meeple-economy **term** is what matters, its **curve shape** is not — i.e. CL-051's ×1.25 win was a small refinement on a large term. |
| `meepleoff` ≈ `meepleflat` ≪ 0 | The **shape** is doing the work, and curve-shape search is live Phase-6 headroom. |

**No promotion, adoption, or `PRODUCTION.yaml` edit follows automatically from any cell.** This
run is descriptive. A "harmful component" result opens a proposal, not a flip.

## Ops

- Launched **detached** (`nohup … & disown`, `nice -n 19`) on **both boxes**, work-stealing on the
  same share dir via `eval_puct_priors.py --shared-claim` (`--claim-stale-secs 300`), local =
  primary (aggregates, writes `results.csv` + `ABL_PROGRESS.tsv`), laptop = helper.
- Share paths: `/mnt/c/carc-shared` locally, `/mnt/carc-shared` inside `ssh`.
- Laptop code-synced by `git bundle` before launch (no `.pyx` change ⇒ **no Cython rebuild needed**;
  both boxes independently verified to advertise all four `SUPPORTS_*` capability flags).
- `scripts/measurement_infra/run_watchdog.sh` armed on **both** boxes (session-independent: the
  2026-07-28 lesson — a Claude-session heartbeat dies with the session).
- Close-out (per the CLAUDE.md six-touch checklist): `results.csv` rows → DECISIONS index line →
  status banner on this file → `BAND_REGISTRY` row `claimed → retired` → STATUS top block →
  roadmap line, then `python3 scripts/doc_lint.py`.

## Deviations from the C5/C7 precedent (flagged, not silent)

1. **W16 per box**, vs C7's net-free W30 local / W22 laptop. Joshua-specified. Consequence: cells
   are slower than the C7 reference implies; the ETA below is measured at W16, not extrapolated
   from C7.
2. **`n=400` per cell, not C7's n=100 screen.** These are verdict cells, not a screen — a knockout
   is not a dose, so there is no monotone axis to screen along, and a null here needs to be a
   *powered* null to be worth anything (see the "elo ≈ 0" reading above).
3. **Farm cells deferred** (see above) — the one part of the requested ablation set this run does
   not deliver.

## Measured ETA

Smoke at production knobs (identical cell config, only the game count and seed band differ):
`meepleoff`, n=16, W16, local box only, band `9.69e10` (throwaway).

**Measured 2026-07-30, mean over all 16 completed records (not the first completions — that
order statistic would have been ~17% optimistic): 570 s/game at W16 local**, wave 683 s,
candidate/champion cost ratio 0.99 (compute-neutral). Local = 101.1 games/h; laptop assumed at
the CL-067-measured 1.39× clock ratio = 72.7 games/h; **combined ≈ 173.8 games/h ⇒ 2.30 h/cell**
at n=400. Six cells = 13.8 h, which **overflows the ~10.5 h window** ⇒ expect **4 cells complete
+ a 5th partial** by morning. Full arithmetic, the W16-vs-C7-W30 note, and the smoke-hygiene
record in **[SMOKE.md](SMOKE.md)**.
