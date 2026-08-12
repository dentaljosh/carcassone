# TARGETED-DENIAL — **DEPLOY-BUDGET CONFIRM**, PRE-REGISTRATION

> **STATUS: PRE-REGISTERED 2026-08-12, BEFORE GAME 1.** Committed before the band was claimed
> and before any game was played. `governance/PRODUCTION.yaml` is untouched on every branch.
> **No promotion, no `results.csv` row, no claim-registry row, no adjudication** by the run or
> by this file — the orchestrating session reads the extract and closes out.

Funded by Joshua 2026-08-12. **One cell. No ladder.**

---

## 1. Why this cell exists — the instrument, not the dose

The D1 screen killed targeted denial on the **2750 ablation instrument**
(`eval_puct_priors.py --cand-sims 2750`, ≈ ¼ of the deploy budget). This project has an
explicit, twice-paid lesson that **a leaf knob's value depends on the search that consumes
it**:

- **curve125** read NULL under random-expansion UCT and was a WIN under PUCT + priors
  (CL-051). Same leaf term, different search, opposite verdict.
- **`meeple_K`** was killed cheap and was later worth **+179 elo**.

Wall clock is no longer a binding cost (Joshua, 2026-08-12). Screening off the deploy path is
therefore no longer justified for a result we are about to write **permanently** into
[`docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md). This cell re-runs the *same candidate leaf*
at the **deploy budget** through the **deploy harness**, and nothing else changes.

**The instrument change IS the experiment.** `eval_puct_priors.py` / 2750 is explicitly NOT
used here.

## 2. The cell

| | |
|---|---|
| **candidate** | champion leaf + targeted denial, **dose 1.0 / size_min 5 / open_max 3** — the identical candidate leaf D1 ran, expected `cand_leaf_hash` **`effeca41772e3e78`** |
| **opponent** | the unmodified production champion, leaf `a36d2e15a3b3d71d` |
| **budget, BOTH arms** | **`--k-dets 8 --sims 1376` = 11008 per decision** (candidate) and **`--opp-k-dets 8 --opp-sims 1376` = 11008** (opponent) — the deploy champion of record |
| **harness** | `eval_fair_puct.py --info fair --opponent fair-champion` (FAIR PIMC) |
| **fixed** | `--backend rust`, `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1`, `--exact-k 2` both arms, `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits`, `--paired`, `--shared-claim`, `--no-results-csv`, `nice -n 19`, detached |
| **workers** | **W=14 local** / W=22 laptop — see §2.1 |
| **n** | **800 deck-paired** = 400 decks × 2 seats |
| **band** | **fresh**, next free above the tile-allocation cells' band; row written at claim time with `decision_influenced=pending` |

The candidate leaf reaches the fair harness via `--cand-leaf-json` +
`--allow-cand-curve-drift`. The drift flag is **not** a curve claim here: the fair harness's
default candidate-side gate asserts the candidate hash *equals* curve125's, which a
knocked-out leaf cannot satisfy. Per `_stamp_cand_leaf`, drift requires the cell JSON to carry
an explicit 8-entry finite curve, so the JSON carries **curve125 verbatim** alongside the
denial knobs:

```json
{"denial_dose": 1.0, "denial_size_min": 5.0, "denial_open_max": 3,
 "v29_meeple_curve": [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]}
```

### 2.1 Worker count — CHANGED MID-SESSION, recorded on purpose

**`W_LOCAL = 14`** (not the 30 used by this session's sims-split cells), `W_LAPTOP = 22`, by
Joshua's 2026-08-12 mid-session instruction that the local box run lighter from this cell
onward. The pool therefore drops from 52 workers to **36**.

This **does not affect the strength statistic**: the cell is deck-paired and both arms play
inside the *same* process pool, so the contrast — and `ms_ratio_cand_over_opp` — is
first-order insensitive to contention. It **does** change `games/h` and every *absolute*
ms/move, so it is recorded here, in the driver, and in the band-registry row. Any future
reader comparing throughput or cost between this cell (W14+22) and the sims-split cells
(W30+22) must condition on the worker count.

**Re-priced ETA:** losing 16 of 52 workers costs ≈ **1.44×** wall clock. At the deploy budget
both arms (~238 s/game realized at 52 workers on this pair of boxes) 36 workers give
≈ **545 games/h**, so n=800 ⇒ **≈ 1.5 h** (vs ≈ 1.0 h at W30+22). Confirmed against the
**mean over completed games** once running — never against the first completions
(order-statistic trap: the first-k mean is ~2× optimistic).

**Post-launch parallelism check:** count busy worker children by PPID and require exactly
**14 local** and **22 laptop** before the run is trusted (`pgrep -cf <script>` undercounts
multiprocessing spawn children and is not used).

**Pre-flight gate D0:** the explicit curve must be a *no-op* — `_leaf_hash` of this JSON must
equal **`effeca41772e3e78`**, D1's candidate hash. If it does not, this is a different
candidate leaf from D1's and the cell **does not launch**.

## 3. No pooling. Ever.

> **This cell stands alone. It is NOT pooled with the D1 screen cells under any circumstance.**

Two independent reasons, either sufficient: **(a) different instrument** — 2750 ablation
(`eval_puct_priors.py`) vs 11008 deploy (`eval_fair_puct.py`), i.e. a different search
consuming the leaf, which is the *entire* point of running this; **(b) different band** —
cross-band pooling is forbidden in this project (CLAUDE.md, "CROSS-BAND z's GET ~2× HUMILITY").
The D1 pooled result is a **prior**, never a summand.

## 4. The prior from the screen (stated before game 1)

Dose 1.0, band 1.21e11, 2750 ablation instrument, pooled n=400 (two same-band halves,
`measurement/denial_screen_20260811/topup_logs/TOPUP_pooled.json`):

| statistic | value |
|---|---|
| W/D/L | 181 / 3 / 216 |
| elo | **−30.479 ± 17.439** (1σ) |
| deck-paired margin | **−1.570 pts/deck** |
| **margin z** | **−2.2932** |
| between-half difference | +0.11 ± 1.3727, **z +0.08** — the effect *replicated*, it did not shrink |
| `ms_ratio_cand_over_opp` | 0.9130 |

Dose 4.0 (band 1.21e11, n=200): margin −11.75, **z −11.005**, elo −230.2 — the dose-response
is steep and monotone in the harmful direction, which is the main reason the dose-1.0 read is
credible rather than noise.

The between-half stability is what makes this an unusually *un*-curse-shaped screen result:
the four winner's-curse instances this campaign all shrank between halves. That raises the
prior on replication — it does **not** license reading a null here as a surprise-free
non-event (see §6, branch C2).

## 5. Wiring gates — verified from the manifest BEFORE any number is read

| # | gate | required value |
|---|---|---|
| D0 | `_leaf_hash(cell JSON)` (pre-flight, before launch) | `effeca41772e3e78` |
| D1 | `config.cand_leaf_hash` | `effeca41772e3e78` |
| D2 | `config.opp_leaf_hash` | `a36d2e15a3b3d71d` |
| D3 | `rules_profile.name` | `fixed_v1` |
| D4 | `rules_profile.r9_env_ok` | `true` |
| D5 | `config.champion.k_dets` / `sims_per_det` / `total_sims` (candidate) | `8` / `1376` / `11008` |
| D6 | `config.opponent.k_dets` / `sims_per_det` / `total_sims` | `8` / `1376` / `11008` |
| D7 | `config.cand_curve_drift_allowed` | `true`, with `cand_curve_drift.curve_values` == curve125 |
| D8 | completion | ≥ 90% of n=800 (else VOID) |

**If `cand_leaf_hash` comes back as the CHAMPION's `a36d2e15a3b3d71d`, the candidate arm ran
the unmodified champion leaf** — the knob never reached the leaf — and the cell's null is an
artifact, not a measurement. This is the campaign's worst failure mode and it is why:

⚠️ **`chain_capability_probe.py --require denial --doses 1.0 --size-min 5 --open-max 3` runs on
BOTH boxes before game 1.** The laptop plays ~40% of every cell and a stale `carc_rs` wheel
there serves a default-off leaf whose games are **indistinguishable at read time** from the
local box's. Probe failure on either box ⇒ **STOP**, do not launch.

⚠️ **Both asymmetry flag pairs are set explicitly** — `--k-dets 8 --sims 1376` AND
`--opp-k-dets 8 --opp-sims 1376`. `--opp-sims` alone silently gives the opponent the
*candidate's* `k_dets`.

## 6. Pre-registered branch map — and what each outcome MEANS

**Primary statistic:** this cell's own deck-paired margin z vs the champion. House map:
**|z| ≥ 2.0** resolve with sign · **1.5 ≤ |z| < 2.0** top-up once on fresh decks of the same
band · **|z| < 1.5** bounded null.

Power at n=800 / 400 decks: **1σ ≈ ±12.3 elo, 2σ ≈ ±24.6 elo**; deck-paired margin se
≈ 0.45–0.7 pts/deck ⇒ 2σ ≈ ±0.9–1.4 pts/deck. The screen's effect (−1.570 pts/deck) is
**≈ 2.2–3.5σ** at this n, so the cell is genuinely decisive on the face-value prior — and is
**not** decisive on a curse-calibrated half-size effect. Branches are evaluated in order.

| # | condition | reading — pre-committed |
|---|---|---|
| **C0 VOID** | any wiring gate D0–D8 fails | UNREADABLE. No number is quoted. Fix, re-run on a FRESH band. |
| **C1 REPLICATES** | `z ≤ −2.0` | **The kill REPLICATES at deploy budget.** The lever closes on strong ground: killed at *both* the 2750 ablation instrument and the 11008 deploy instrument, on two independent bands. `LEVER_INDEX` §5 denial row → measured-dead, citing both cells, and the "leaf-knob value depends on the consuming search" caveat is discharged for this knob. |
| **C2 DOES NOT TRANSFER** | `\|z\| < 1.5` | **The ablation-instrument kill does NOT transfer cleanly.** The `LEVER_INDEX` row must SAY SO — it may **not** claim a deploy-budget kill. Licensed wording is a bounded statement at the REALIZED 2σ bound (e.g. "no deploy-budget denial effect larger than ±X elo; the −30.5-elo 2750-instrument kill did not reproduce"). This is a live instance of the curve125 / `meeple_K` lesson and is written up as one. |
| **C3 FALSE KILL** | `z ≥ +2.0` | **The cheap instrument produced a FALSE KILL.** This is a finding about our **screening methodology** at least as much as about denial, and must be written up that way: a 2750-instrument screen that reads −2.29σ while the deploy path reads +2σ means every lever killed on that instrument alone carries an unquantified transfer risk. Triggers (Joshua's call, not this run's): an audit of which live `LEVER_INDEX` rows rest on 2750-only kills. **Still not a promotion** — a single confirm never promotes. |
| **C4 TOP-UP** | `1.5 ≤ \|z\| < 2.0` | ONE top-up, n→1600, on RESERVED fresh decks of THIS band (`<band>+400..+799`), then re-verdict on the pooled within-band result. The run does NOT auto-execute it; the spend is Joshua's call. **No second top-up, ever.** |

**Reported alongside on every branch (cross-checks, not verdicts):** W/D/L, elo ± 1σ, paired
margin + se, `ms_ratio_cand_over_opp` (prior: 0.913 at the 2750 instrument — denial makes the
candidate slightly *cheaper*; a ratio far from ~0.9–1.0 is a flag), sign agreement between elo
and margin, realized throughput, `n_paired_decks`.

**Seeds `<band>+400 .. <band>+799` are RESERVED for branch C4** and must not be drawn for
anything else.

## 7. What this cell CANNOT say

1. **One dose, one threshold pair.** Dose 1.0 / size_min 5 / open_max 3 only. It prices no
   other point on the dose axis, and dose 4.0's z −11.0 remains a 2750-instrument number.
2. **A null is a bounded null.** "Denial does nothing at deploy budget" is a **forbidden**
   reading of C2; only a realized-bound statement is licensed.
3. **Not poolable with D1** (§3), in either direction, on any branch.
4. **Fresh band, `fixed_v1` + R9 both sides** — not comparable to walled-era elo; the band
   retires from confirmatory use if it influences a decision.
5. **Nothing is deployable from this cell.** Even C3 is information, not a config change:
   a single cell never promotes, and the caps/curve optima were tuned against the intact leaf.

## 8. Standing constraints

`governance/PRODUCTION.yaml` untouched · no promotion · no `results.csv` row · no
claim-registry row · no adjudication by the launcher · band row written at claim time with
`decision_influenced=pending`, flipped only at close-out by the orchestrating session.
