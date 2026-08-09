# MEEPLE-CURVE SHAPE + PHASE SEARCH — PRE-REGISTRATION (DRAFT, CONDITIONAL ON FUNDING)

> **STATUS: 📝 DRAFT — NOT AUTHORIZED, NOT FUNDED, NO BAND CLAIMED, NO GAMES PLAYED.**
> Written 2026-08-09 alongside [SCOPE.md](SCOPE.md), which carries the rationale, the cost
> arithmetic and the dominance-order analysis. This file is the *runnable* protocol: it is what
> gets committed (with bands flipped to `claimed`) **before game 1** if Joshua funds it.
> `governance/PRODUCTION.yaml` is untouched on every branch of this document.
>
> **Funding is staged.** Part A (the curvature probe) and Part C (the β ladder) are ~3 h each and
> can be authorized independently. **Part B (the Optuna sweep) is authorized only if Part A's
> pre-registered reading says the response surface has curvature.**

---

## 1. Questions

**Q1 (SHAPE).** Holding the overall scale fixed at production's, does any alternative *shape* of
`v29_meeple_curve` beat the incumbent `Bmild × 1.25` by ≥ 25 elo when both play at the production
fair budget under `fixed_v1`?

**Q2 (PHASE).** Does multiplying the curve by a mean-1-renormalized linear function of
`k_remaining` — i.e. making meeple value depend on how much deck is left, in either direction —
beat `β = 0` (no phase dependence)?

**Q3 (CURVATURE, the gate on Q1).** Does the shape response surface exhibit any curvature within
±25 elo over a neighbourhood wide enough that a ±35-elo screen could navigate it?

Q3 is answered first and gates Q1. Q2 is independent of both.

---

## 2. Primary statistic (stated before any threshold)

**Primary: the deck-paired point margin, in points per deck** — `margin_z` = the paired-sample
z of (candidate points − champion points) per deck, over decks played in both seatings.
Reported alongside: **win-paired elo** and its z, and unpaired elo with σ.

Rationale, and the F13 lesson applied: **every threshold below is stated in `margin_z`, the same
statistic the question is posed in.** A prereg whose question is asked in one statistic and whose
threshold fires in another mis-fires. Where a second gate part is required (S3, S4) it is
win-paired z, and that is stated explicitly as a *conjunction*, never as an alternative.

σ reference (deck-paired, near wr 0.5): n=200 → ±17 elo · n=400 → ±12 · n=900 → ±8 · n=1600 → ±6.
**No threshold anywhere in this document is below +25 elo**, because no stage of it can resolve
below that. See SCOPE §3.

---

## 3. Fixed experimental conditions (identical in every cell, all parts)

| | value |
|---|---|
| Plane | **fair PIMC** (`FairHeuristicPriorAgent`, `eval_fair_puct --info fair`) |
| Budget | **`k_dets = 8`, `sims_per_det = 1376` (= 11008)**, both arms |
| Rules | **`fixed_v1`**, `CARCASSONNE_FIX_R9=1`, both arms |
| Backend | **rust**, both arms |
| Champion arm | `governance/PRODUCTION.yaml` champion `puct_priors_v29_bmild_cap8`, leaf hash `a36d2e15a3b3d71d` |
| Candidate arm | identical in every respect **except** `v29_meeple_curve` (and, in Part C, the phase multiplier), injected via `eval_fair_puct --cand-leaf-json` |
| Knobs | c_puct 1.5 · tau_p 5 · final_select visits · leaf_quantize float · value_norm 15 |
| Endgame | fair deploy handoff: exact K≤2 marginalized |
| Pairing | deck-paired, both seatings of every deck |
| Boxes | local 5900XT W30 + laptop W26, `OPENBLAS_NUM_THREADS=1`, `nice -n 19`, detached |

**Forbidden:** routing any candidate through `make_production_champion` (`verify_leaf` hard-raises
unless the curve is exactly `CURVE125`); reusing any deck across stages; pooling reads across bands.

---

## 4. Parametrization (frozen here; see SCOPE §1.1)

Anchored at `curve[3] = 0` (the term is a differential — a constant offset cancels exactly, so
one entry must be pinned and **pure zero-point re-placement is a no-op, not a lever**):

```
curve[3-j] = -d * (j/3)**γ                       j = 1,2,3
curve[3]   = 0
curve[3+i] = Σ_{u≤i} g_u ,  g_1 = s0 ,  g_i = s1 * ρ**(i-2)   i = 1..4
```

| param | production | search range |
|---|---|---|
| `d` | 10.0 | [0, 24] |
| `γ` | 2.0 | [0.5, 3.0] |
| `s0` | 2.5 | [0, 6] |
| `s1` | 1.25 | [0, 4] |
| `ρ` | 1.0 | [0, 1.2] |

Every production value is **interior** to its range (bracketed above and below). After generation
the table is **rescaled so its L1 norm equals production's** — scale is not searched here (it was
swept three times: CL-051, CL-057, capscurve). Trial 0 uses the **literal** production table
`[-10, -5, -1.25, 0, 2.5, 3.75, 5, 6.25]`, not its parametric approximation.

Part C phase multiplier: `f(k; β) = clip(1 + β·(k − 35)/35, 0.0, 2.0)`, then **renormalized so
E[f] = 1** over the empirical `k_remaining` distribution of a game. The renormalization is
load-bearing: without it, β changes the term's mean magnitude and the cell measures scale rather
than phase — which is the confound that invalidates the 2026-06-22 `v28_meeple_recovery_t0` kill.

---

## 5. Stages, thresholds, and branch precedence

**Branch precedence, evaluated in this order; the first that fires wins:**
`INSTRUMENT-BROKEN` → `KILL` → `UNRESOLVABLE` → `PARK` → `PROMOTE`.

### PART A — Curvature probe (**the funding gate for Part B**) · 4 cells · n=400 · ~3.3 h

Band: `1.10e11` (claim before game 1). Cells:

| id | shape | 
|---|---|
| `C0_identity` | production `curve125` (literal) |
| `C1_flattop` | ρ = 0.4 |
| `C2_broadlow` | γ = 0.8, d = 16 |
| `C3_hoard` | ρ = 1.2 |

**A-gate 0 (INSTRUMENT-BROKEN, checked first):** `C0_identity` must read `|elo| < 25` **and** its
manifest must show identical leaf hashes both arms, `rules_profile: fixed_v1`, `r9_env_ok` both
arms. Fail ⇒ **ABORT, no cell counts**, fix wiring, restart on a new band.

**A-readings (pre-registered, exhaustive):**

| # | condition | verdict | action |
|---|---|---|---|
| A1 | all of C1/C2/C3 within ±25 elo of C0 (i.e. no `\|margin_z\| ≥ 2.0`) | **SURFACE FLAT at this resolution** | **DO NOT FUND PART B.** Write CL: "no shape gain ≥ ~35 elo is findable by a ±35-elo screen over this neighbourhood." Explicitly NOT "the shape is optimal." |
| A2 | any cell reads ≤ −40 elo with `margin_z ≤ −2.0` | **CURVATURE PRESENT** | Part B is a reasonable bet. Recommend funding. |
| A3 | any cell reads ≥ +35 elo with `margin_z ≥ +2.0` | **HAND-PICKED WINNER** | Skip the sweep. Take that candidate directly to Part B stage S2, then S3/S4. |
| A4 | mixed (one cell fires, others flat) with no cell past ±2σ | **UNRESOLVABLE** | Park. Record the effect-size floor. Do not fund Part B on a sub-2σ signal. |

A2 and A3 can co-fire; A3 takes precedence.

### PART B — Optuna shape sweep (**only if A2 or A3 fired**) · ~40 trials · ~47 h

Sampler: `optuna.samplers.TPESampler(multivariate=True, n_startup_trials=10, seed=20260809)`,
local SQLite storage. Enqueued (not sampled) trials: **T0 = production literal** (reused from
Part A as `C0_identity` if the band permits, else re-run), **T1 = `Bflattop`×1.25 (ρ≈0.5)**,
**T2 = `Bxaggr`-equivalent (d≈20, γ≈1.1) as a NEGATIVE CONTROL**.

**B-gate 0 (INSTRUMENT-BROKEN):** T2 must read clearly negative (`margin_z ≤ −2.0`). A known-killed
shape reading neutral means the instrument cannot see shape at all ⇒ **ABORT**.

| stage | n | decks | band | selection / gate |
|---|---|---|---|---|
| **S1 screen** | 200 | 100 | `1.11e11` | rank all trials by `margin_z`; **keep top 10**. No significance gate (ranking only — a significance gate here would import selection bias). |
| **S2 confirm** | 400 | 200 | `1.12e11` (**fresh decks — no S1 game is pooled**) | advance if `margin_z ≥ 2.0` **and** elo ≥ +25; **keep top 2** |
| **S3 fair confirm** | 900 | 450 | `1.13e11` (fresh) | **BOTH parts**: `margin_z ≥ 2.0` **AND** win-paired `z ≥ 2.0`, elo ≥ +25. (The CL-051 precedent: curve125's fair confirm resolved at 451 decks with margin z 2.77 / win-paired z 3.13.) |
| **S4 promotion read** | 1600 | 800 | `1.14e11`, **tier = sealed**, claimed only *after* the single candidate is frozen | `margin_z ≥ 2.0` on the sealed band |

**B-verdicts:**

| # | condition | verdict |
|---|---|---|
| B-KILL | S1: no trial reaches +35 elo with `margin_z ≥ 1.5` **and** the trial spread is consistent with the null | **SHAPE AXIS DEAD at this resolution.** Wording constraint: "no gain ≥ ~35 elo exists", never "the shape is optimal." |
| B-UNRESOLVABLE | S1 leaders sit in +15…+35 and fail to separate at S2 on fresh decks | **PARK-UNRESOLVABLE.** Record the floor. Capscurve wording template (SCOPE §3). |
| B-CONFIRMATION | the surviving candidate is statistically tied with production (e.g. ρ≈0.5 rediscovered) | **Confirmation of the 2026-06-25 Wave-2 tie. Not a finding, no CL, no promotion.** |
| B-PROMOTE | S3 both parts pass **AND** S4 sealed read passes | **Propose to Joshua.** `PRODUCTION.yaml` is still NOT edited by this prereg — promotion is a separate decision with the six-touch close-out. |

### PART C — Phase (β) dose ladder · 5 cells + 1 confirm · ~3 h · independent of A and B

Band `1.15e11` (or the next free). Cells: β ∈ {−0.6, −0.3, **0.0**, +0.3, +0.6}, n=200 each,
mean-1 renormalized, all else fixed. β = 0 is the identity cell and doubles as the wiring gate
(`|elo| < 25`).

**Primary statistic for Part C is the FITTED WITHIN-DECK SLOPE of `margin` on β across the five
points** — not any individual cell. ("A trend beats underpowered steps"; the line across the
ladder is the measurement.)

| # | condition | verdict |
|---|---|---|
| C-KILL | slope `\|z\| < 2.0` | **PHASE AXIS DEAD in the modern era with the magnitude confound removed.** Materially stronger than the 2026-06-22 v28 kill (which was one unbracketed endpoint with magnitude confounded). Worth its own CL. |
| C-RECONFIRM | slope significantly **negative** (β>0 is worse) | v28's finding **reconfirmed on clean ground**. Axis closes permanently. |
| C-FIRE | slope `z ≥ 2.0` positive in either direction | run one n=400 fresh-deck confirm at the best-fit β. If `margin_z ≥ 2.0` there, escalate to the Part B S3/S4 ladder. |

---

## 6. Kill conditions (any of these stops the run immediately)

1. Any identity cell reads `|elo| ≥ 25` ⇒ wiring is wrong; abort, no cell counts.
2. Any manifest shows a leaf hash, `rules_profile`, `r9_env_ok`, backend, or budget differing
   from §3 ⇒ that cell is void and re-run; two such cells ⇒ abort the stage.
3. The `Bxaggr` negative control fails to read negative ⇒ the instrument cannot see shape; abort.
4. A cell hangs or completes < 90% of its games ⇒ **void, do not read the partial.** (C5's ×1.75
   cell hung at 141/400 from OpenBLAS oversubscription and produced a hang-biased **+134** that
   looked like a discovery. `OPENBLAS_NUM_THREADS=1` is mandatory and the completion fraction is
   checked before any number is quoted.)
5. Clock drift detected on any box ⇒ stop, `date -s` from the share host, discard the affected cell.
6. A local dirty reboot mid-cell ⇒ discard that cell; clean `--shared-claim` claims-without-records
   before resuming.
7. Cumulative wall-clock exceeds **65 h two-box** (the ~47 h estimate + 40%) ⇒ stop and report
   whatever stages completed. No open-ended extension.

---

## 7. Band plan

| part / stage | band | tier | notes |
|---|---|---|---|
| A curvature probe | `1.10e11` | dev | doubles as B's S0 if B is funded |
| B S1 screen | `1.11e11` | dev | |
| B S2 confirm | `1.12e11` | dev | fresh — no S1 deck reused |
| B S3 fair confirm | `1.13e11` | dev | fresh |
| B S4 promotion read | `1.14e11` | **sealed** | claimed only AFTER the candidate is frozen |
| C β ladder (+ confirm) | `1.15e11` | dev | |

Discipline:
- Rows appended to `governance/BAND_REGISTRY.csv` **via `csv.writer`** (8 fields,
  `newline=''`; the file contains quoted commas and doubled-quote escapes — never hand-edit),
  `status=claimed`, **in the same commit that pre-registers the stage, before game 1**; flipped
  to `retired` at close-out (six-touch checklist item 4).
- Free-band verification at launch uses **both** the registry **and**
  `grep -h seed_start /mnt/c/carc-shared/*/manifest.json /mnt/c/carc-shared/*/*/manifest.json`
  — the registry's own caveat records that `results.csv` has no band column, so the naive check
  fails silently open, and that share consumption at `1.09e11` was never registered.
- **All contrasts within-band.** No pooling across bands; any cross-band remark carries the
  ~1.5–2× σ inflation and cannot be quoted as an estimate.
- A band that influenced a decision **retires from confirmatory use.**

---

## 8. Manifest and artifact requirements

Every cell writes a self-describing `manifest.json` with the **full resolved config** — no
dirname archaeology. Required fields (a cell missing any of these is void per §6.2):

- `champ_leaf_hash`, `cand_leaf_hash`, and the **literal 8-entry `v29_meeple_curve` array for both arms**
- the candidate's `(d, γ, s0, s1, ρ)` and, for Part C, `β` and the realized `E[f]`
- `rules_profile` (`fixed_v1`), `cloister_rule`, `farm_rule`, `r9_env_ok` — **both arms**
- `backend` (`rust`), `k_dets`, `sims_per_det`, `c_puct`, `tau_p`, `final_select`,
  `leaf_quantize`, `value_norm`, endgame `exact_k` + mode
- `band_seed_start`, `deck_range`, `n_games`, `n_decks`, `seatings_per_deck`, `games_completed`
- `code_rev` (git sha), box, `W`, `OPENBLAS_NUM_THREADS`, start/end timestamps
- per-deck results (both seatings) so the paired margin and any slope fit are re-derivable

Additionally, per the six-touch close-out: a row per cell in `experiments/results.csv`
(`curveshape_*` / `curvephase_*` prefixes), a `PROGRESS.tsv` in this directory with a `secs`
column (the only in-repo timing record), a DECISIONS index line, a status banner update on
[SCOPE.md](SCOPE.md) and this file, a governance row flip, the STATUS top block, the
[roadmap](../../docs/PROGRAM_ROADMAP_2026-07-07.md) line, and the
[LEVER_INDEX](../../docs/LEVER_INDEX.md) row status change. Then `python3 scripts/doc_lint.py`.

---

## 9. Riders carried into every write-up

- **CL-051 (consumer = search):** results are valid for production PUCT + `fixed_v1` + rust at
  k8×1376 **only**. Void for a different budget, rules profile, or a neural consumer.
- **The "bug fix shifts hyperparameter optima" rule does NOT apply** — there is no bug here. The
  curve is unsearched, not wrong. Nothing licenses reopening settled optima on the back of this.
- **The Wave-2 tie:** a re-found `Bflattop`≈`Bmild` tie is **confirmation, not news** (branch B-CONFIRMATION).
- **The v28 phase kill:** the retry is licensed only by the `E[f]=1` renormalization and the
  bracketed signed ladder. A negative slope is a *reconfirmation* and closes the axis.
- **No offline pre-screen** was used or is admissible (SCOPE §6.1). If one is ever proposed, its
  admission gate is recovering the CL-051 ordering (−92.5 / −34.9 / 0 / +48.8) with separation.
- **Noise signature:** a lone trial beating its parameter-neighbours by >1σ is noise, not a peak.
  In a 5-param family a real optimum has a *neighbourhood* that also reads positive — check it.
- **Nothing here promotes anything.** `governance/PRODUCTION.yaml` is untouched on every branch.
