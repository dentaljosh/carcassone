# OPEN-CITY DISCIPLINE — **DEPLOY-BUDGET** CELLS, PRE-REGISTRATION

> **STATUS: WRITTEN BEFORE THE BAND WAS CLAIMED AND BEFORE GAME 1 (2026-08-13).**
> Two cells, no ladder beyond the two calibrated doses. `governance/PRODUCTION.yaml` is
> untouched on every branch, no `results.csv` row is owed until close-out, and the launching
> session adjudicates nothing.

Design of record: [`TERM_SPEC.md`](TERM_SPEC.md) §5 (parameters) + §8 (what the eval must be).
Cell selection: [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) (committed `6148388`, **before any
arm's flip rate was read**) → branch **`FUND-SMALLEST`** → [`CALIB_READOUT.md`](CALIB_READOUT.md).

---

## 1. Why these two cells, and why NOT a 2750 screen

`CL-079` was minted 2026-08-12 on the targeted-denial pair: **a 2750-ablation-instrument
verdict does not reliably transfer to the deploy budget.** Denial read margin z **−2.293**
(n=400, band 1.21e11) at 2750 and margin z **−0.127** (n=800, band 1.24e11) at 11008 — the
kill did not transfer, in either direction, and the two are not poolable on any branch.

**Consequence, pre-committed:** a 2750 screen is **not a substitute** for these cells and
must not be run *instead* of them. TERM_SPEC §8 licenses a 2750 screen only as an optional,
clearly-labelled "keep / does-not-express" filter; it is **not** being run here. The deploy
budget is the budget we play at, so it is the budget that decides.

The calibration measured **expressiveness only** (does the pick change), never strength.
Its funded pair is arm A — the production-spec predicate — at the two pre-registered doses:

| cell | flip rate on 1,556 E4 champion plies | Wilson-95 |
|---|---|---|
| `A_d0p5` | **10.09 %** (157/1556) | 8.69 – 11.69 % |
| `A_d2p0` | **18.89 %** (294/1556) | 17.03 – 20.92 % |

⚠️ **`A_d0p5` sits ON the 10 % funding bar** (clears by 0.09 pp; its own CI straddles the
bar — `CALIB_READOUT.md` §3). Read this forward, not backward: **if `A_d0p5` lands null,
"the term does not express" is NOT an available reading.** It was funded at the edge of the
floor and a null there is a bound, nothing more. `A_d2p0` carries no such caveat.

## 2. The two cells

Common to both: opponent = **the unmodified production champion**, leaf `a36d2e15a3b3d71d`;
harness `scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion`
(FAIR PIMC); **budget 11008 on BOTH arms** (`--k-dets 8 --sims 1376` *and*
`--opp-k-dets 8 --opp-sims 1376`); `--backend rust`; `--rules-profile fixed_v1` +
`CARCASSONNE_FIX_R9=1`; `--exact-k 2` shared by both arms; `--c-puct 1.5 --tau-p 5
--leaf-quantize float --final-select visits`; `--paired --shared-claim --no-results-csv`;
`nice -n 19`; detached; **n = 800 deck-paired = 400 decks × 2 seats**.

| | `A_d0p5` | `A_d2p0` |
|---|---|---|
| `opencity_dose` | **0.5** | **2.0** |
| `opencity_size_min` (**TILES**, not points) | 4.0 | 4.0 |
| `opencity_edge_min` | 2 | 2 |
| `opencity_symmetric` | `True` | `True` |
| expected `cand_leaf_hash` | **`c128083fb485d20d`** | **`2cf0b7507e6a0921`** |
| cell JSON | [`cells/opencity_A_d0p5_deploy_fixed_v1_vs_fairchamp11008.json`](cells/opencity_A_d0p5_deploy_fixed_v1_vs_fairchamp11008.json) | [`cells/opencity_A_d2p0_deploy_fixed_v1_vs_fairchamp11008.json`](cells/opencity_A_d2p0_deploy_fixed_v1_vs_fairchamp11008.json) |
| deck seeds | `<band>+0 .. +399` | `<band>+400 .. +799` |
| out subdir | `opencity_A_d0p5_deploy11008` | `opencity_A_d2p0_deploy11008` |

**The two cells DO NOT share decks.** Disjoint seed ranges on one band, deliberately: each
cell's own deck-paired margin vs the champion is its own primary statistic, and there is no
A-vs-B contrast in this design. Band 1.23e11 measured that CRN across *cells* bought only
**9.9 %** of the contrast variance, so sharing decks would buy almost nothing while creating
a standing temptation to read an unpowered A−B difference. There is no A−B statistic here.

The knobs reach the candidate arm via `--cand-leaf-json` + `--allow-cand-curve-drift`. The
drift flag is **not** a curve claim: the fair harness's candidate-side gate asserts the
candidate hash *equals* curve125's, which a modified leaf cannot satisfy, and
`_stamp_cand_leaf` requires the cell JSON to carry an explicit 8-entry finite curve. So both
JSONs carry **curve125 verbatim** alongside the open-city knobs. That the curve is a **no-op**
is proven by gate O0 below, not assumed.

**Execution: LAPTOP ONLY, SEQUENTIALLY, `A_d0p5` first.** The local box is running the
Joshua-bot tournament at W30 and is not available; both cells run on `laptop-wsl` at
**W = 22** under `systemd-run --user --scope -p MemoryMax=8G` (the WSL-VM-teardown guard).
This is a **single-box** cell, unlike the 1.24e11 confirm (W14 local + W22 laptop = 36). The
statistic is unaffected — deck-paired, both arms in the same process pool — but **`games/h`
and every absolute `ms/move` are NOT**, so any throughput or cost comparison against this
session's other cells must condition on the worker count. Recorded here, in the driver, and
in the band-registry row.

## 3. Wiring gates — verified FROM THE MANIFEST **before any number is read**

Pre-flight gate **O0** ran before the band was claimed and before game 1; **O1–O12** are read
from each cell's `manifest.json` at read time, per cell, **before** the summary is opened.

| # | gate | required — `A_d0p5` | required — `A_d2p0` |
|---|---|---|---|
| **O0** | *(pre-flight, done)* `_leaf_hash(cell JSON)` on the laptop | `c128083fb485d20d`, **≠** `a36d2e15a3b3d71d` ✅ | `2cf0b7507e6a0921`, **≠** `a36d2e15a3b3d71d` ✅ |
| **O1** | `config.cand_leaf_hash` | `c128083fb485d20d` | `2cf0b7507e6a0921` |
| **O2** | `config.opp_leaf_hash` | `a36d2e15a3b3d71d` | `a36d2e15a3b3d71d` |
| **O3** | ⚠️ **`config.cand_leaf_cfg.opencity_dose`** | **`0.5`** | **`2.0`** |
| **O4** | `config.cand_leaf_cfg` contains **no** `opencity_size_min` / `opencity_edge_min` / `opencity_symmetric` key | absent ⇒ defaults `4.0 / 2 / True` = arm A | same |
| **O5** | `config.opp_leaf_cfg` contains no `opencity_*` key | intact champion leaf | same |
| **O6** | `rules_profile.name` / `rules_profile.r9_env_ok` / `leaf_env.CARCASSONNE_FIX_R9` | `fixed_v1` / `true` / `"1"` | same |
| **O7** | `config.champion.k_dets` / `sims_per_det` / `total_sims` | `8` / `1376` / `11008` | same |
| **O8** | `config.opponent.k_dets` / `sims_per_det` / `total_sims` | `8` / `1376` / `11008` | same |
| **O9** | `config.cand_curve_drift_allowed` + `config.cand_curve_drift.curve_values` | `true` + curve125 verbatim | same |
| **O10** | `config.band_seed_start` / `n_decks` / `seatings_per_deck` | `<band>+0` / `400` / `2` | **`<band>+400`** / `400` / `2` |
| **O11** | `config.backend.requested` / `config.endgame.exact_k` / `shared_by_both_arms` | `rust` / `2` / `true` | same |
| **O12** | completion | ≥ 90 % of n=800 (else **VOID**) | same |

### ⚠️ Why O3 exists and why a moved hash is NOT enough

The capability probe (run on the laptop before game 1, `--require opencity --doses 0.5,2.0
--size-min 4 --edge-min 2`, **PASS**, 14/14 checks) recorded this verbatim:

> `leaf_hash(dose-0 + MOVED thresholds) = eaf6bea637cce74e != champion a36d2e15a3b3d71d`:
> `_LEAF_HASH_EXCLUDE_IF_DEFAULT` drops a field only while it holds its DEFAULT value, so
> the three MOVED thresholds stay in the hashed dict even though the dose gate makes the
> leaf VALUES bit-identical. **Consequence for the chain: a cell whose dose was accidentally
> zeroed would still PASS `cand_hash_moves` — the hash gate cannot catch it.**

So **"the candidate hash moved" does not prove the dose is live.** The gate that proves it is
**O3, the resolved dose value in the manifest** (`config.cand_leaf_cfg` is `_leaf_dict` of the
*resolved* candidate config, and `opencity_dose` survives it precisely because it is off its
default). O4 is the mirror check: for arm A the three thresholds sit **at** their defaults, so
their **absence** from `cand_leaf_cfg` is the assertion that they are `4.0 / 2 / True`; the
appearance of any of them means a different arm ran and the cell is VOID.

⚠️ **Both asymmetry flag pairs are set explicitly.** `--opp-sims` alone silently leaves the
opponent at the *candidate's* `k_dets`.

⚠️ **The laptop plays 100 % of both cells**, so its `carc_rs` is the only build that matters
and a stale wheel there would serve a default-off leaf whose games are indistinguishable at
read time. Pre-flight, on the laptop: rust/src/engine tree identity with the local repo
(`369e61cc… / 5da1acc1… / cad4650c…`) · sha256 identity of the six load-bearing scripts ·
`chain_capability_probe.py --require opencity` **PASS** (140 leaf values moved, 148 same,
`identity_control_breaks = 0` on the rust **and** the python leaf, 288 dose-0 values compared
each with 0 breaks) · candidate hashes derived on the laptop agree with §2.

*(Full `git rev-parse HEAD` identity — the 1.24e11 gate — is deliberately **replaced** by tree
+ script hash identity here: the laptop sits at `f8d14ca`, a strict **ancestor** of local
`6b5e77b`, and the entire delta is `scripts/analyzer/analyze_autopsy.py` plus a
`chain_capability_probe.py` change the laptop already carries byte-identically in its working
tree. Every file this cell executes hashes equal on both boxes; that is the property the rev
gate was a proxy for.)*

## 4. Read rules — pre-committed

**Primary statistic: each cell's own deck-paired margin z vs the champion.** Elo is reported
and is the *weaker* statistic (CL-072: elo alone failed to resolve where the margin did).
House map, applied **per cell**: `|z| ≥ 2.0` resolve with sign · `1.5 ≤ |z| < 2.0` → see §5
branch **N3** (there is **no** pre-registered top-up) · `|z| < 1.5` bounded null.

1. **`|z| < 2` is NEVER "refuted".** No branch of this document licenses the words "killed",
   "refuted", "dead", or "does nothing" for the open-city term. Under-2σ is *no conviction*,
   full stop. The house has a measured ~50 % underpowered-kill error rate; this is the rule
   that pays it down.
2. **A null must state its bound, in BOTH units.** Any null reading must quote the cell's
   **realized** 2σ resolution as *both* pts/deck *and* elo — e.g. "no deploy-budget open-city
   effect larger than ±X pts/deck ≈ ±Y elo at 2σ" — computed from that cell's own realized
   `se`, never from a nominal power figure. Expected ≈ ±0.9–1.4 pts/deck ≈ ±24.6 elo at
   n=800, but the **realized** number is the one that gets written.
3. **Winner's-curse paragraph.** This campaign has **four confirmed winner's-curse
   instances** (a lean that shrank or vanished on extension) against **one** that held (the
   D1 dose-1.0 pair, between-half z +0.08). A first-look positive at `1.5 ≤ |z| < 2.5` is
   therefore *expected* to shrink, and `A_d0p5`/`A_d2p0` are **two** looks, which is two
   chances for a selected maximum. Any positive read must state, in the same paragraph, that
   it is a first look on a two-cell family and is curse-calibrated to roughly **half** its
   face value until replicated on a fresh band. A single cell **never** promotes anything.
4. **NO POOLING of the two dose cells.** They are different candidate leaves — different
   `cand_leaf_hash`, a 4× dose ratio, and measurably different expressiveness (10.09 % vs
   18.89 % flip). They are not two halves of one measurement and must never be summed,
   averaged, meta-analysed, or reported as a single "open-city result". Two independent
   readings, each with its own bound. (Nor may either be pooled with any 2750-instrument
   number — CL-079.)
5. **Dose-response is an OBSERVATION, not a statistic.** If the two signs agree, say so as a
   qualitative remark with both CIs shown; do not fit a slope, and do not treat agreement
   across two under-powered cells as reinforcement. If they disagree, that is what two
   independent under-powered cells do.
6. **Cross-band contrasts get 1.8–2.2× σ inflation** (CL-068). Nothing here may be contrasted
   against a number from another band without that inflation, and nothing here may be pooled
   across bands at all.
7. **Ordering.** Wiring gates O1–O12 first, per cell; only then the summary. A cell that
   fails any gate is **UNREADABLE** — no number from it is quoted anywhere, including "for
   context".

## 5. Branch map — evaluated per cell, in order

| # | condition | reading — pre-committed |
|---|---|---|
| **N0 VOID** | any gate O0–O12 fails for that cell | **UNREADABLE.** No number quoted. Fix, re-run on a FRESH band. A VOID in one cell does not void the other. |
| **N1 POSITIVE** | `z ≥ +2.0` | **The term is expressed AND the sign is favourable at deploy budget** — the first live positive on a leaf term this campaign. Still **NOT** a promotion and **NOT** a champion change: it is one cell, one look, on a two-cell family (read rule 3), and `governance/PRODUCTION.yaml` is untouched. The licensed next step is a **confirm on a fresh band**, whose funding is Joshua's call, plus the `opencity_symmetric=False` ablation TERM_SPEC §3 holds in reserve for exactly this branch. `docs/LEVER_INDEX.md` moves the item-7 NEVER-TRIED row to "measured, provisional positive, unconfirmed". |
| **N2 NEGATIVE** | `z ≤ −2.0` | **The term is harmful at deploy budget at this dose.** Licensed as a resolved negative *for that dose on arm A only* — not for the term's shape, not for arm B/C predicates, and not for the asymmetric variant. The double-count hypothesis of TERM_SPEC §9 becomes the leading explanation and should be written up as such (the search already prices exposure through the closure schedule). If **both** doses read N2 the lever closes for arm A. |
| **N3 NO CONVICTION** | `1.5 ≤ \|z\| < 2.0` | **The lean is recorded with its sign and its bound, and NOTHING is concluded.** ⚠️ **NO top-up branch is pre-registered.** Extending this cell requires a **new prereg** and Joshua's explicit funding decision — topping up a screen that lands just under a threshold is the forking-path pattern the 1.19e11 close-out explicitly declined (`\|z\| = 1.487`, top-up not run, bounded-null branch taken instead). Seed headroom is reserved on the band so that a *future* prereg can draw fresh decks, but **the reservation is not a licence.** |
| **N4 BOUNDED NULL** | `\|z\| < 1.5` | **Bounded null at the realized 2σ**, stated per read rule 2 in pts/deck **and** elo. For `A_d0p5` the bound must additionally carry the on-the-bar caveat of §1 (funded at the edge of the expressiveness floor — a null there is weaker evidence than the same null at `A_d2p0`). "Open-city discipline does nothing" is a **FORBIDDEN** reading on this branch. |

**Reported alongside on every branch (cross-checks, never verdicts):** W/D/L, elo ± 1σ, paired
margin + se, `ms_ratio_cand_over_opp` (a ratio far from ~0.9–1.1 is a flag — the term is
uncapped and TERM_SPEC §9 item 3 notes a 10-tile 4-open city contributes 21 leaf points at
dose 1.0), sign agreement between elo and margin, realized throughput at W22, `n_paired_decks`.

## 6. What these cells CANNOT say

1. **Two doses, one predicate.** Arm A (`size_min = 4` TILES, `edge_min = 2`, symmetric) at
   doses 0.5 and 2.0 only. Nothing is priced for arm B (3/2), arm C (6/3), any other dose, the
   asymmetric variant, a points-based size axis, an additive escalation, or a per-city cap
   (TERM_SPEC §9 open questions 1–3).
2. **Expressiveness ≠ strength.** The 10.09 % / 18.89 % flip rates say the pick changes, not
   that it improves. They are the *reason* these cells are readable at all, not evidence for
   either sign.
3. **Not poolable** — with each other, with any 2750-instrument cell, or across bands.
4. **`fixed_v1` + R9 both sides** ⇒ not comparable to walled-era elo, and not comparable to
   the E4 app epoch's games.
5. **Nothing is deployable from these cells.** Even N1 is information: a single cell never
   promotes, the caps/curve optima were tuned against the intact leaf (2026-05-15 lesson), and
   the term is uncapped by design.
6. **Single-box throughput.** W22 laptop-only; `games/h` and absolute `ms/move` here are not
   comparable to the 36- or 52-worker cells of 2026-08-12.

## 7. Standing constraints

`governance/PRODUCTION.yaml` untouched on every branch · no promotion · no `results.csv` row
and no claim-registry row until close-out · **no adjudication by the launching session** ·
band row written at claim time with `decision_influenced = not yet`, flipped only at close-out
· `scripts/doc_lint.py` run at close-out (six-touch checklist).
