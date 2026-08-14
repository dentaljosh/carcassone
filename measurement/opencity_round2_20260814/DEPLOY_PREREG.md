# OPEN-CITY ROUND 2 — **DEPLOY-BUDGET** CELLS, PRE-REGISTRATION

> **⚠️ STATUS 2026-08-14 — RAN AND CLOSED (six-touch). ALL THREE CELLS FIRED PRE-REGISTERED
> BRANCH `N2 NEGATIVE`, ALL THREE COST-NEUTRAL (`N4` did not fire on any of them).** Every
> cell: 800/800 records, 400/400 decks fully paired, 0 failed games, 0 stranded claims, all
> 13 wiring gates PASS.
>
> | cell | band / seeds | `cand_leaf_hash` | W/D/L · wr | margin ± sem (pts/deck) | **z** | elo (2σ) | `ms_ratio` |
> |---|---|---|---|---|---|---|---|
> | `Asym_d2p0` (own-side-only) | 1.29e11 `+800..+1199` | `3f05d72016d0d09c` | 206/14/580 · 0.2662 | **−13.6862** ± 0.7893 | **−17.3392** | −176.10 ± 27.79 | 0.8743 |
> | `Acap3_d2p0` (per-city cap 3.0) | 1.29e11 `+400..+799` | `687f99980adaeee7` | 312/10/478 · 0.3962 | **−5.2188** ± 0.6775 | **−7.7028** | −73.16 ± 25.11 | 1.0049 |
> | `C_d16p0` **RE-RUN** (6/3 @ dose 16) | **1.31e11** `+0..+399` | `a4acf6d0925f7606` | 216/14/570 · 0.2787 | **−14.8663** ± 0.9016 | **−16.4892** | −165.15 ± 27.40 | 0.9864 |
>
> ⚠️ The arm-C row is the **RE-RUN on fresh band 1.31e11** — the original `C_d16p0` cell on
> band 1.29e11 `+0..+399` is **VOID**; read
> [AMENDMENT_1_C_VOID_AND_RERUN.md](AMENDMENT_1_C_VOID_AND_RERUN.md), whose terms were
> honoured in full (not one threshold, sign, statistic or branch condition changed; no
> top-up taken at any z). Its number is **never contrasted with the voided cell's as a
> statistic**, and the on-the-bar rider of §1/§4.8 is **moot because the cell resolved**.
>
> With CL-080's arm A that is **four named variants measured harmful at the deploy budget**
> ⇒ **claim CL-082 minted**; CL-080 annotated (numbers/status unchanged). The §5 licensed
> sentence binds: *"every calibrated, fundable form measured harmful"* — **arm B (3/2) and
> every shape never calibrated stay UNPRICED, and "the open-cities idea is dead" is STILL a
> FORBIDDEN reading.** Bands **1.29e11** and **1.31e11** retired `decision_influenced=yes`;
> `results.csv` rows `opencity_{Asym_d2p0,Acap3_d2p0}_deploy_fixed_v1_vs_champ11008_n800_b129e9`
> + `opencity_C_d16p0_RERUN_deploy_fixed_v1_vs_champ11008_n800_b131e9`; DECISIONS 2026-08-14.
> Nothing promoted; `governance/PRODUCTION.yaml` **untouched**. Everything below this banner
> is the pre-registration exactly as committed before game 1, unedited.

> **STATUS AT WRITING: WRITTEN BEFORE ANY BAND WAS CLAIMED AND BEFORE GAME 1 (2026-08-14).**
> Three cells — the calibration's funded set, nothing else. `governance/PRODUCTION.yaml`
> is untouched on every branch, no `results.csv` row is owed until close-out, and the
> launching session adjudicates nothing.
>
> ⚠️ **THE BAND IS A CLAIMED-BY-ORCHESTRATOR PLACEHOLDER THROUGHOUT.** Every seed range
> below is expressed as `<BAND> + offset`; the orchestrator claims a fresh band via
> `claim_next_band.py` into `governance/BAND_REGISTRY.csv` at launch (row written with
> `decision_influenced = not yet`), and no earlier decision may have influenced it. This
> file never names a band on purpose.

Design of record: [`TERM_SPEC.md`](../opencity_term_20260812/TERM_SPEC.md) §5 + §8 + **§10**
(the cap). Cell selection: [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) (committed
`9a2abcd5`, **before any round-2 flip rate was read**) → mechanical read by
[`make_calib_readout_round2.py`](make_calib_readout_round2.py) → [`CALIB_READOUT.md`](CALIB_READOUT.md).

---

## 1. Why these cells, and why NO 2750 screen

`CL-079` (unchanged): a 2750-ablation-instrument verdict does not reliably transfer to
the deploy budget, so — as in round 1, which is CL-079's recommended-practice instance —
the funded cells go **straight to the deploy budget**. The deploy budget is the budget we
play at, so it is the budget that decides.

The calibration measured **expressiveness only** (does the pick change), never strength.
Round 1 is the standing proof of that distinction: its 10.09 %-flip cell lost a little
and its 18.89 %-flip cell lost much more (CL-080) — **a changed pick is not a better
pick**, and nothing in the funding below predicts any sign. The funded set, from the
mechanical read:

| funded cell | CL-080 falsifier it answers | flip rate on 1,556 E4 champion plies | Wilson-95 |
|---|---|---|---|
| `C_d16p0` | arm C — the guides' own "avoid three open edges" predicate, re-dosed to clear the floor | **10.41 %** (162/1556) | 8.99 – 12.03 % |
| `Acap3_d2p0` | the PER-CITY-capped form (the uncapped product is CL-080's leading harm explanation) | **14.20 %** (221/1556) | 12.56 – 16.03 % |
| `Asym_d2p0` | the `opencity_symmetric=False` own-side-only variant | **16.71 %** (260/1556) | 14.94 – 18.64 % |

⚠️ **`C_d16p0` sits ON the 10 % funding bar** (clears by 0.41 pp; its Wilson-95 straddles
the bar, and on the CI lower bound the rule would fund **no cell in family C**). Recorded
at calibration time per the read-rule's mandatory on-the-bar clause. Read it forward:
if `C_d16p0` lands null, "the tight predicate does not express" is **NOT** an available
reading — it was funded at the edge of the floor. `Acap3_d2p0` and `Asym_d2p0` carry no
such caveat. Both pre-registered calibration predictions held (the C ladder crossed 10 %
between doses 8 and 16; every capped rate sat at or below its uncapped round-1
counterpart).

Each cell answers a **different named falsifier of CL-080** and they are read
independently, never pooled, never contrasted with each other or with CL-080's cells.

## 2. The cells

Common to all: opponent = **the unmodified production champion**, leaf `a36d2e15a3b3d71d`;
harness `scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion`
(FAIR PIMC); **budget 11008 on BOTH arms** (`--k-dets 8 --sims 1376` *and*
`--opp-k-dets 8 --opp-sims 1376` — ⚠️ both asymmetry flag pairs set explicitly;
`--opp-sims` alone silently leaves the opponent at the candidate's `k_dets`);
`--backend rust`; `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1`; `--exact-k 2`
shared by both arms; `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select
visits`; `--paired --shared-claim --no-results-csv`; `nice -n 19`; detached;
**n = 800 deck-paired = 400 decks × 2 seats per cell**.

| | `C_d16p0` | `Acap3_d2p0` | `Asym_d2p0` |
|---|---|---|---|
| `opencity_dose` | **16.0** | **2.0** | **2.0** |
| `opencity_size_min` (**TILES**) | **6.0** | 4.0 (default) | 4.0 (default) |
| `opencity_edge_min` | **3** | 2 (default) | 2 (default) |
| `opencity_symmetric` | `True` | `True` | **`False`** |
| `opencity_cap` (per-city) | 0.0 = uncapped | **3.0** | 0.0 = uncapped |
| expected `cand_leaf_hash` | **`a4acf6d0925f7606`** | **`687f99980adaeee7`** | **`3f05d72016d0d09c`** |
| cell JSON | [`cells/opencity_C_d16p0_deploy_fixed_v1_vs_fairchamp11008.json`](cells/opencity_C_d16p0_deploy_fixed_v1_vs_fairchamp11008.json) | [`cells/opencity_Acap3_d2p0_deploy_fixed_v1_vs_fairchamp11008.json`](cells/opencity_Acap3_d2p0_deploy_fixed_v1_vs_fairchamp11008.json) | [`cells/opencity_Asym_d2p0_deploy_fixed_v1_vs_fairchamp11008.json`](cells/opencity_Asym_d2p0_deploy_fixed_v1_vs_fairchamp11008.json) |
| deck seeds | `<BAND>+0 .. +399` | `<BAND>+400 .. +799` | `<BAND>+800 .. +1199` |
| out subdir | `oc2_C_d16p0_deploy11008` | `oc2_Acap3_d2p0_deploy11008` | `oc2_Asym_d2p0_deploy11008` |
| off-default knobs the manifest MUST show (gate O4) | `opencity_size_min: 6.0`, `opencity_edge_min: 3` | `opencity_cap: 3.0` | `opencity_symmetric: false` |

⚠️ Dose 16 (`C_d16p0`) is a large per-fire perturbation by construction — a 6-tile
3-open city is 16 leaf points at the threshold corner. That is the arm's character
(*rare but decisive*), priced deliberately in the read-rule §1; the `ms_ratio` cost
trigger (§4.6) and the N4 branch are the guardrails, not a reason to shade the dose
after the fact.

**Cells DO NOT share decks.** Disjoint `<BAND>+400·i` offsets, deliberately: each cell's
own deck-paired margin vs the champion is its own primary statistic and there is no
cell-vs-cell contrast in this design (the round-1 rationale, unchanged: cross-cell CRN
bought only ~9.9 % of contrast variance on band 1.23e11 and would create a standing
temptation to read an unpowered difference).

The knobs reach the candidate arm via `--cand-leaf-json` + `--allow-cand-curve-drift`;
each cell JSON carries **all five opencity knobs explicitly plus curve125 verbatim** (the
drift flag is not a curve claim — gate O9 proves the curve is a no-op, not assumes it).

**Execution: box-parameterized, sequential per box** —
[`run_deploy_opencity_round2.sh`](run_deploy_opencity_round2.sh) `<laptop|local> <BAND>
[W]` (laptop → `/mnt/carc-shared`, default W 22, under `systemd-run --user --scope -p
MemoryMax=8G`; local → `/mnt/c/carc-shared`, default W 14). Cells are independent
(disjoint decks), so the orchestrator MAY split cells across boxes by running the driver
per box with a cells subset — but any throughput/`ms/move` comparison must then condition
on the box and W, as in round 1 (§2 of its prereg).

## 3. Wiring gates — verified FROM THE MANIFEST **before any number is read**

Pre-flight **O0** runs on the executing box before the band is claimed and before game 1;
**O1–O12** are read from each cell's `manifest.json` at read time, per cell, **before**
the summary is opened. The driver emits `verdicts/GATES_<cell>.json` (pass/fail only, no
strength number).

**O0 (pre-flight, per box):** (a) **cap-capable wheel** — rebuild + install `carc_rs`
from the merged tree and run `chain_capability_probe.py --require opencity` with the
cell-appropriate knobs (**`--cap N` for any capped cell** — TERM_SPEC §10: a CL-080-era
wheel passes the uncapped probe and still `TypeError`s on capped cells; a launcher that
swallowed it would produce a champion-vs-champion perfect null); arm-C-shaped probes gate
on the wiring checks only (identity / dose-0 controls, kwargs), with bite reported —
a 0-bite scripted-playout reading is NOT evidence of inertness (round-1 §4b, measured).
(b) `_leaf_hash(cell JSON)` computed **on the executing box** equals the expected hash
below and differs from `a36d2e15a3b3d71d`. (c) tree/script-hash identity with the rev
this prereg names, per the round-1 gate style.

| # | gate | required |
|---|---|---|
| **O1** | `config.cand_leaf_hash` | the cell's expected hash (§2 table) |
| **O1b** | `cand_leaf_hash != champion` | `a36d2e15a3b3d71d` excluded |
| **O2** | `config.opp_leaf_hash` | `a36d2e15a3b3d71d` |
| **O3** | ⚠️ `config.cand_leaf_cfg.opencity_dose` **resolved value** | the cell's dose — a moved hash does NOT prove a live dose (round-1 §3's probe finding; this is the gate that does) |
| **O4** | **round-2 form:** the cell's off-default knobs (§2 `arm knobs` column) PRESENT in `cand_leaf_cfg` with exactly those values, and **no other** `opencity_*` knob present besides the dose | a missing expected knob OR a stray knob ⇒ a DIFFERENT ARM ran ⇒ VOID |
| **O5** | `config.opp_leaf_cfg` has no `opencity_*` key | intact champion leaf |
| **O6** | `rules_profile.name` / `r9_env_ok` / `leaf_env.CARCASSONNE_FIX_R9` | `fixed_v1` / `true` / `"1"` |
| **O7** | candidate budget | `8 / 1376 / 11008` |
| **O8** | opponent budget | `8 / 1376 / 11008` |
| **O9** | `cand_curve_drift_allowed` + `cand_curve_drift.curve_values` | `true` + curve125 verbatim |
| **O10** | `band_seed_start` / `n_decks` / `seatings_per_deck` | `<BAND>+offset` / `400` / `2` |
| **O11** | `backend.requested` / `endgame.exact_k` / `endgame.shared_by_both_arms` | `rust` / `2` / `true` |
| **O12** | completion | ≥ 90 % of n=800 (else **VOID**) |

### Why O4 changed shape from round 1

Round 1's arm A sat at the threshold defaults, so O4 asserted the *absence* of the three
threshold knobs. Round-2 cells each move a different knob off default —
`_LEAF_HASH_EXCLUDE_IF_DEFAULT` keeps a field in `cand_leaf_cfg` exactly when it is off
its default — so the assertion flips to *presence with exact values* for the cell's own
knobs and *absence* for everything else. Same manifest recipe, same VOID consequence.

## 4. Read rules — pre-committed

**Primary statistic: each cell's own deck-paired margin z vs the champion.** Elo is
reported and is the weaker statistic (CL-072). House map, per cell: `|z| ≥ 2.0` resolve
with sign · `1.5 ≤ |z| < 2.0` → §5 **N3** (no pre-registered top-up) · `|z| < 1.5`
bounded null.

1. **`|z| < 2` is NEVER "refuted".** No branch licenses "killed", "refuted", "dead", or
   "does nothing" for any round-2 form.
2. **A null must state its bound in BOTH units** (pts/deck and elo), computed from that
   cell's own realized `se`.
3. **Winner's-curse paragraph.** Three cells = three looks; any first-look
   positive at `1.5 ≤ |z| < 2.5` is expected to shrink and is curse-calibrated to
   roughly half its face value until replicated on a fresh band. A single cell never
   promotes anything.
4. **NO POOLING** — across cells, with round 1, with CL-080's cells, or across bands
   (CL-068 inflation on any cross-band remark, which must stay qualitative).
5. **Cross-family remarks are OBSERVATIONS, not statistics** — the three falsifiers are
   different terms; no slope, no meta-analysis, no "the capped form rescued/confirmed X"
   without a fresh pre-registered cell.
6. ⚠️ **COST TRIGGER (pre-registered, the jrules-N4 lesson):** if a cell's
   `ms_ratio_cand_over_opp` **> 1.20**, the cell's strength reading is **downgraded to
   "confounded by budget"** — N1/N2 sign language may not be used for it, and the write-up
   must say the cost gate fired. (Both CL-080 cells ran 1.011/1.013, so a large ratio here
   is a real anomaly, not house noise. The ms_ratio is the FAIR-harness
   `champ_prefix/rung` ratio; never quote absolutes from a shared-tenancy run, and read
   the emitter, not the field name — `champ_prefix_*` is the CANDIDATE side.)
7. **Ordering.** Gates O1–O12 first, per cell; a cell that fails any gate is
   **UNREADABLE** — no number from it is quoted anywhere, including "for context".
8. **On-the-bar riders from the calibration carry into the read:** `C_d16p0` was funded
   at **10.41 %** against the 10 % bar with its Wilson-95 (8.99–12.03 %) straddling it —
   on the CI lower bound family C funds nothing. Any null or bounded-null reading of
   `C_d16p0` must carry this rider verbatim and may not be phrased as "the tight
   predicate does not express". `Acap3_d2p0` and `Asym_d2p0` carry no rider.

## 5. Branch map — evaluated per cell, in order

| # | condition | reading — pre-committed |
|---|---|---|
| **N0 VOID** | any gate O0–O12 fails, for that cell | **UNREADABLE.** Fix, re-run on a FRESH band. A VOID in one cell does not void the others. |
| **N4 BUDGET-CONFOUNDED** | `ms_ratio_cand_over_opp` > 1.20 | The strength reading is recorded but **downgraded to "confounded by budget"**; no sign conclusion, no claim. Evaluated BEFORE N1/N2 (a cell can be N4 and nothing else). |
| **N1 POSITIVE** | `z ≥ +2.0` | **The falsified-form hypothesis survives its first deploy look** — the first live positive on a leaf term this campaign if it fires. NOT a promotion, NOT a champion change: one cell, one look (read rule 3). Licensed next step: a confirm on a fresh band, Joshua's funding call. The LEVER_INDEX row moves to "measured, provisional positive, unconfirmed". |
| **N2 NEGATIVE** | `z ≤ −2.0` | **Harmful at deploy budget for that form at that dose** — a resolved negative scoped to exactly that cell's (predicate, dose, cap, symmetry). The CL-080 double-count/horizon mechanism gains a further instance; the write-up must extend CL-080's scope table rather than mint a blanket kill. "The open-cities idea is dead" remains FORBIDDEN unless **every** round-2 family resolves N2, and even then the licensed sentence is "every calibrated, fundable form measured harmful" — shapes never calibrated stay unpriced. |
| **N3 NO CONVICTION** | `1.5 ≤ \|z\| < 2.0` | Lean recorded with sign and bound; **nothing concluded; NO top-up pre-registered** — extension needs a new prereg and Joshua's funding decision. Seed headroom above `<BAND>+1200` is reserved on the band; the reservation is not a licence. |
| **N5 BOUNDED NULL** | `\|z\| < 1.5` | Bounded null at the realized 2σ, stated per read rule 2 in both units, with any §4.8 on-the-bar rider attached. "Does nothing" is a FORBIDDEN reading. |

**Reported alongside on every branch (cross-checks, never verdicts):** W/D/L, elo ± 1σ,
paired margin + se, `ms_ratio_cand_over_opp`, sign agreement between elo and margin,
realized throughput at the recorded (box, W), `n_paired_decks`.

## 6. What these cells CANNOT say

1. Each cell prices **its own (predicate, dose, cap, symmetry) only**. Unfunded arms —
   and every shape never calibrated (points-based size axis, additive escalation, other
   caps/doses) — stay unpriced on every branch.
2. **Expressiveness ≠ strength** (round 1 is the proof).
3. **Not poolable** — with each other, with round 1, with any 2750 cell, across bands.
4. `fixed_v1`+R9 both sides ⇒ not comparable to walled-era numbers.
5. **Nothing is deployable from these cells.** Even N1 is information only.
6. Single-box throughput per cell; `games/h` and `ms/move` condition on (box, W).

## 7. Standing constraints

`governance/PRODUCTION.yaml` untouched on every branch · no promotion · no `results.csv`
row and no claim-registry row until close-out · no adjudication by the launching session ·
band claimed by the orchestrator at launch, row `decision_influenced = not yet`, flipped
only at close-out · `scripts/doc_lint.py` at close-out (six-touch checklist).
