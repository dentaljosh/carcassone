# TILE-TIE PRICING — STAGE B ADDENDUM

**Status: ✅ STAGE B SCORED 2026-08-13 10:01 → 11:36 local (1 h 35 min, owner-authorized,
"yes please"). NOT ADJUDICATED.** Rust/`walled` self-play arm only, **+393 new positions**
(every one that the deduped supply still holds), **pooled n = 733**. All 4 cells clean:
`rc=0` on every leg, **0 missing / 0 extra** records, and over the **1,468** pooled records
`ok = 1468/1468`, `crn_verified = 1468/1468`, `checksum_ok` never false. Every leg of the
pooled plan matches its record set exactly (677/409/216/61 walled + 98 e4).

Nothing here is a result: **no `delta`, no mean, no headroom has been read from any record**,
the analyser has **not** been run, and this document changes **no** read-rule in
[DESIGN.md](DESIGN.md). Markers: `DONE_STAGEB` (+ `DONE_STAGEB_cell01…04`) / `FAILED_STAGEB`.

**Next step is the OWNER's:** one pooled run of
`scripts/tiletie/analyze_tiletie.py --records-root /mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct --plan-dir measurement/tiletie_pricing_20260812/positions_pooled`
— read §4 below before reading its output.

⚠️ **DESIGN.md's Stage-A close-out banner still says "Stage B is NOT funded."** That was
true when it was written (2026-08-13 ~08:00) and is now stale: the owner funded Stage B the
same morning. The banner is corrected by this file, not contradicted by it.

---

## 1. Stage B was PRE-REGISTERED. This is an extension, not a post-hoc top-up.

[DESIGN §7.3](DESIGN.md), written and committed **before any position was scored**:

> - **Stage A — n = 280.** Buys a **±35 elo** bound at the planning sd, and, more
>   importantly, **measures the real sd** on this population. Read Stage A against §4.4
>   immediately: if `elo(CI_hi) < +17` already […] **the lever is closed and Stage B is never
>   funded.**
> - **Stage B — extend to `n = ceil((2 × sd_A / 0.174)²)`, capped at 1,300** — funded only if
>   Stage A lands in branch 4 (inconclusive) or branch 2/3. `--resume` makes it a pure
>   extension of the same records directory: no re-scoring, no new ruler.

and §4.4's branch 4, which is where Stage A landed:

> 4. **otherwise** ⇒ **INCONCLUSIVE.** Report the estimate and its CI; promote nothing. The
>    read-out must state the **realized** sd and the **n required** to reach a ±17-elo bound
>    at that sd, **so the extension decision is arithmetic and not a new argument.**

The two gating conditions are both met on the record:

| pre-registered condition | realized | met? |
|---|---|---|
| Stage A lands branch 4, 2 or 3 | `results.branch = 4` (INCONCLUSIVE) | ✅ |
| `elo(headroom_CI_hi) ≥ +17` (else the lever is closed and Stage B is never funded) | `elo CI hi = +58.81` (point +31.24, CI lo +3.88) | ✅ |

**Arm composition is fixed by the same pre-registration and is honoured verbatim** — Stage B
buys the **rust / `walled` self-play arm only**:

> ⇒ **The funding decision is Stage A** […] Stage B is a further ~4.1 h that buys the
> ±17-elo bound, and it is bought **only on the rust arm** — the E4 arm cannot be scaled at
> this price and is not meant to be.

Everything else is unchanged: same instrument (`oracle_score_pilot.py`, unmodified), same
judge (`clair-puct`, `--oracle-sims 100`), same **M = 32** CRN worlds, same salt
`tiletie-v1`, same cap **J = 4**, same estimators (§4.1/§4.2), same cluster-robust
bootstrap on `root_id` (20,000 reps, seed 20260812), same §4.3 bound chain and constants.
**No new ruler, no new statistic, no re-scoring.**

---

## 2. The sizing inputs — REALIZED Stage A numbers, read off disk

From [`readout_stageA_FINAL/VERDICT.json`](readout_stageA_FINAL/VERDICT.json) `results.sizing`
(the authoritative file; nothing below is retyped from prose):

| quantity | value |
|---|---|
| `n_realized` / `n_roots_realized` | **340** positions over **247** roots |
| `realized_sd_positions_pts` (S2 `headroom_J4_all`) | **1.8422664** |
| `realized_se_cluster_pts` | **0.10102971** |
| `realized_se_composite_pts` (the se the headline CI is built on) | **0.14144159** |
| `pts_2se_needed_for_17elo` | **0.17421937** |
| **`n_required_17elo`** | **896.3968749** |
| `n_required_35elo` | 212.5693075 |

⇒ the pre-registered ±17-elo target wants **≈ 896 scored positions**, i.e. **≈ 556 new** on
top of Stage A's 340.

### 2.1 ⛔ 556 is not purchasable. The supply holds 393, and Stage B takes all of them.

This is the one place where the realized world does not reach the pre-registered target, and
it is **arithmetic, not a choice**. The deduped, ≤12-way, champion-pick-resolved supply is:

| stratum | built (deduped) positions | Stage A took | **remains** |
|---|---|---|---|
| `selfplay` / `walled` / **rust** | **673** | 280 | **393** |
| `e4` / `fixed_v1`+`app_aug2` / **python** | 380 | 60 | 320 |
| **total** | **1,053** | **340** | **713** |

(`positions/POSITIONS_PLAN.json` → `counts_by_stratum`; the same 673 / 380 split is echoed
in the Stage A verdict's `zero_rates.by_stratum.*.n_built`. The pre-dedupe DESIGN §7.3 figure
of "932 selfplay" is the **pre-dedupe** count — §0.A's transposition drop removed 259 of them
as analytic zeros, which is why §7.4's "Stage B … n ≈ 965 selfplay/rust" row was already
beyond the post-dedupe supply when it was written.)

**Stage B therefore takes the entire remaining rust arm: 393 positions. Pooled n = 733.**
That is not a sample of the self-play supply — it *exhausts* it: pooled, the self-play
stratum becomes a **census** of the deduped ≤12-way tied self-play population (673/673), not
a draw from it.

### 2.2 What n = 733 actually buys, and what it does not

Scaling the realized se by √(340/n) (the same scaling `results.sizing` uses):

| n | 2·se (composite) | **elo half-width** | 2·se (cluster-robust) | elo half-width |
|---|---|---|---|---|
| 340 (Stage A) | 0.28288 | **±27.58** | 0.20206 | ±19.70 |
| **733 (pooled A+B)** | **0.19266** | **±18.78** | 0.13762 | **±13.42** |
| 896 (the §7.3 target) | 0.17422 | ±16.99 | 0.12444 | ±12.13 |

⇒ **the pooled corpus lands just short of the ±17-elo bar on the composite se (±18.8) and
inside it on the cluster-robust se (±13.4).** Which of the two governs is a read-rule the
analyser already implements — it is not re-litigated here. **Stage B is expected to be
close-but-not-guaranteed on the pre-registered bar, and that expectation is on the record
BEFORE the records are read.**

The residual is not affordably closeable: the 163 positions that would carry n from 733 to
896 could only come from the `e4`/python arm, whose **realized** cost is **1,811 worker-s per
position** (108,646 worker-s over 60 positions) against the rust arm's **207.6** — a measured
**8.7×**, consistent with §2.0's 9.41–9.48× identity-gate figure. Those 163 positions would
cost **82.2 worker-h ⇒ ~6.4 h at W14**, i.e. ~3.6× the entire Stage B rust arm, to buy the
last 1.8 elo of half-width. **Not bought.** (And they would also swing the pooled corpus's
stratum mix, which is a change to the estimand, not just to n.)

---

## 3. How the new positions were drawn, and the disjointness check

**Rule: two-phase sampling without replacement — remove what Stage A already scored, then
apply the SAME builder to the remainder.** Concretely:

```
scripts/tiletie/build_positions.py                       # unchanged code path
    --champ-picks   champ_picks/champ_picks.jsonl
    --exclude-rids  positions_stageA/RIDS_STAGEA.txt     # the 340 Stage A rids
    --n-e4 0                                             # rust arm only (DESIGN §7.3)
    --out-dir       positions_stageB
```

- The **afterstate dedupe stays armed** (`--no-dedupe` is not used and would be refused by
  `run_tiletie`'s preflight anyway): `afterstate_dedupe.applied = true`, map covers
  **1,427/1,427** qualifying positions, 374 all-transposition positions dropped as the
  analytic zeros they are.
- `--exclude-rids` removes the Stage A rids from the **kept** (post-dedupe) supply *before*
  sampling. It deliberately does **not** re-scope `selected` / `dropped_rows`: the
  all-transposition zeros are a **population** rate that the analyser scales by, and
  re-scoping them per stage would double-count them once the stages are pooled.
- With 393 of 393 taken, the seeded sampler is a no-op (`k ≥ len(pool)` ⇒ take all), so **no
  randomness enters Stage B at all.** The union A ∪ B is nonetheless still a valid uniform
  subset of the supply, because two-phase without-replacement sampling is exchangeable — and
  in this instance the union is the whole self-play supply, so the question is moot.
- **Champion-pick coverage: complete, no top-up needed.** `champ_picks.py` had already
  resolved all **932/932** qualifying self-play positions (`champ_picks/manifest.json`:
  `n_ok = 932`, `n_error = 0`), a superset of the 673 built. The Stage B build reports
  `champ_pick_missing = 0`.

### 3.1 Disjointness — proven, not asserted

```
|Stage A rids| = 340      (positions_stageA/ARMS.json)
|Stage B rids| = 393      (positions_stageB/ARMS.json)
|A ∩ B|        = 0        <-- DISJOINT
|A ∪ B|        = 733      (= 340 + 393, no double-count)
```

Roots overlap by construction and are *supposed* to (247 A-roots + 277 B-roots, 125 shared,
399 distinct) — that is exactly why every CI in this design is **cluster-robust on
`root_id`**, and why the pooled bootstrap must resample the **399** roots, not the 733 rows.

`make_stageb_cells.py` re-checks the A∩B intersection and refuses to build if it is non-empty.

### 3.2 Phase mix did not drift

DESIGN §7.4 warns that per-position cost varies ~9× with game phase and that *"the sampler
must not be allowed to drift phase-wise between stages"*. It did not:

| | early | mid | late | mean tie size |
|---|---|---|---|---|
| Stage A self-play (n=280) | 42.1% | 28.2% | 29.6% | 4.06 |
| **Stage B (n=393)** | **38.9%** | **33.3%** | **27.7%** | **4.08** |

(mid is +5.1pp, early −3.2pp — mid is the *expensive* bucket per §0.B, so the ETA below is
phase-**re**weighted rather than scaled off the pooled Stage A rate.)

---

## 4. ⭐ THE ANALYSIS POOLS STAGE A + STAGE B INTO **ONE** ESTIMATE

**This is binding, and it is the pre-registered design — it is not two looks at one
hypothesis.** DESIGN §7.3 specifies a single staged corpus (*"`--resume` makes it a pure
extension of the same records directory: no re-scoring, no new ruler"*), and §4.4's
read-rules are written against **the** estimate, singular. Stage A was never adjudicated as a
verdict on the axis: it landed in branch 4, which by construction **defers** the read and
prescribes the extension arithmetic. There is therefore **one** hypothesis test on this axis,
taken once, on n = 733.

Concretely, and with no discretion left to the reader:

1. **The headline is the POOLED estimate over all 733 positions**, through §4.3's bound chain
   with the same constants (`Kelo = 97.5`, `NON_ADDITIVITY = 3.2` with the 5.23 low-end
   sensitivity, `σ_game = 20.4`), and §4.4's branch precedence 1 → 2 → 3 → 4, first match
   wins, applied to the ×1.40 full-set-extrapolated figure exactly as at Stage A.
2. **No alpha is spent on Stage A's read.** Stage A's `+0.2283 pts/ply, z +2.26` is **not** a
   result that Stage B "confirms"; it is an interim number the pre-registration required to
   be published so the extension decision would be arithmetic. The pooled estimate supersedes
   it outright.
3. **The per-stage split is reported for TRANSPARENCY, never as a second test.** The read-out
   should carry Stage A alone / Stage B alone / pooled side by side so a reader can see
   whether the extension moved the estimate — and a **large** Stage-A-to-Stage-B shift is a
   *diagnostic* (regression to the mean on a branch-4 interim, §6 threat 5), not a finding.
   No branch is ever read off a per-stage number.
4. **§4.4's stratum rule survives unchanged**: pooled is primary; `e4` and `selfplay` are
   reported separately and are **not pooled if they disagree in sign**. ⚠️ Stage B changes the
   pooled mix from 82% self-play to **92%** self-play (673 of 733), so the `e4` stratum is
   even more clearly the underpowered relevance check it was always labelled as — and the
   §3.2/§6-threat-6 rules-epoch confound (`selfplay` = `walled`, `e4` = 23/26 `fixed_v1`)
   weighs *more*, not less, on the pooled read. Stage A's sign check passed
   (`sign_disagreement = false`, e4 +0.3367 vs selfplay +0.2050); it must be re-run pooled.

### 4.1 ⛔ If the pooled CI still straddles ±17, the pre-registered read is UNRESOLVABLE — Stage C is NOT licensed

Stated plainly, in advance, so it cannot be re-argued afterwards:

> **If the pooled n = 733 estimate lands with its CI still straddling the ±17-elo bar — i.e.
> §4.4 falls through to branch 4 a second time — the pre-registered read is that THIS AXIS IS
> UNRESOLVABLE AT AFFORDABLE n, and Stage C is NOT automatically licensed.**

The reasoning is on the record before the read: Stage B **exhausts the cheap arm**. There is
no third tranche of rust positions to buy — 673/673 of the deduped self-play supply will have
been scored. Any Stage C would have to come from one of
(a) the `e4`/python arm at **8.7× the per-position cost** (~6.4 h at W14 for 163 positions),
(b) a **new census** over more `champ_games` plies, which is a new instrument run and a new
    build, not an extension, or
(c) relaxing a pre-registered filter (the ≤12-way truncation, the cap `J = 4`, the
    all-transposition drop) — each of which **changes the estimand** and voids the pooling.

None of those is licensed by this pre-registration. A branch-4-at-733 outcome must be written
up as *"measured, bounded, and not resolvable at this price"*, with the pts/ply and elo
interval shipped per §4.4's standing requirement that a null **never** ships as *"ties don't
matter"* — and any further spend becomes a **fresh funding decision with its own argument**,
which the owner makes, not the read-out.

---

## 5. Execution

| | |
|---|---|
| plan (new only) | `positions_stageB/` — 393 positions, 776 walled leg-records, 49,664 arm-playouts |
| execution cells | `positions_stageB/cells/cell01…cell04` — **cumulative** plan dirs (Stage A + chunks 1..k) |
| **pooled plan (analyser input)** | **`positions_pooled/`** — 733 positions, identical to `cells/cell04` |
| records root (shared with Stage A) | `/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct` |
| launcher | `run_stageB_chain.sh` (detached, `nice -n 19`, resume-safe) |
| markers | `DONE_STAGEB` / `FAILED_STAGEB`, plus `DONE_STAGEB_cellNN` per cell |
| per-cell manifests / gates | `manifests_stageB/RUN_MANIFEST_stageB_cellNN.json`, `…/GATE_BACKEND_RECHECK_stageB_cellNN.json` |
| logs | `logs/stageB/chain.log`, `logs/stageB/cellNN.log`, `logs/stageB/cellNN/leg_*.log` |

**Why cumulative cells.** `analyze_tiletie.py` takes a single `--records-root`, so Stage B's
records must land beside Stage A's; and `run_tiletie.verify_leg_records` treats an `extra`
record as a **failure**, not a warning. A plan naming only the new rids would therefore fail
its own integrity check against a records dir that already holds Stage A's. Naming the
cumulative set fixes both: `oracle_score_pilot --resume` skips every rid whose record already
exists (a `Path.exists()` per line and nothing more), so no position is ever re-scored, and
the integrity check sees exactly the rid set it should. **The last cell's plan dir IS the
pooled plan.**

Cells are an **execution device only** — they exist so the launcher can re-pick `W` by
wall-clock at each cell start under the owner's box grant (**W30 until 11:00 local, then
W14**, encoded exactly as `scripts/joshuabot/tournament_chain.sh` encodes it: `W_HI` only if
the window is open **and** the cell is projected to finish before it closes; a `W_HI` cell
never straddles 11:00). Chunking is **phase-stratified round-robin**, so all four cells carry
the same early/mid/late mix (39/32/28, 38/33/27, 38/33/27, 38/33/27) and no cell is a cost
lottery. Nothing about the estimate depends on the cell boundaries.

### 5.1 ETA — priced from Stage A's REALIZED rust rate

Not DESIGN §0.B's planning constant (`c_rust = 1.4755`), and not from first completions
(order-statistic trap). Measured as `Σ elapsed_secs / playouts` over **all 587** Stage A
`walled` leg-records — the §7.4 rule that the wall-based figure is inadmissible:

| phase | records | Σ elapsed_secs | mean/record | **realized `c`** |
|---|---|---|---|---|
| early | 222 | 31,784.3 s | 143.17 s | **2.2371** |
| mid | 170 | 18,386.6 s | 108.16 s | **1.6899** |
| late | 195 | 9,935.3 s | 50.95 s | **0.7961** |
| **pooled** | **587** | **60,106.2 s** | 102.40 s | **1.5999** |

⇒ realized `c_rust` = **1.5999** worker-s/playout, **+8.4%** over §0.B's phase-weighted
commitment of 1.4755 (as §0.B predicted: its smokes ran at W ≤ 8, and *"a W=14 run has more
DRAM contention, which pushes the other way"*). Reweighted to Stage B's own phase mix:

- **81,576 worker-s = 22.66 worker-h** (flat-pooled-`c` cross-check: 22.07 worker-h)
- **207.6 worker-s per new position** — the launcher's own ETA constant
- Stage A's realized parallel efficiency: 60,106 worker-s over a **4,680.6 s** wall at W=14
  nominal ⇒ **12.84 effective workers (91.7%)**

| | ETA |
|---|---|
| whole arm @ W14 | **1.76 h** |
| whole arm @ W30 (per-worker slowdown ×1.6 planning constant) | 1.32 h |
| **as launched** (cell01 @ W30, later cells W-repicked at 11:00) | **≈ 1.5 h ⇒ ~11:30 local** |

Preflight adds ~1.4 min per cell (the rust identity gate is re-verified **at HEAD** for every
cell, never skipped): ~5.5 min total.

---

## 6. Governance — unchanged from §8, and nothing is minted here

Measurement only. **0 games ⇒ no `experiments/results.csv` row, no band claim, no
`governance/BAND_REGISTRY.csv` entry.** `governance/PRODUCTION.yaml` untouched. A claim id is
minted only on branch 1/2/3 **of the pooled read**, and never off a partial corpus. This
addendum mints nothing and adjudicates nothing.

Close-out on the pooled read-out is the standing six touches (DESIGN §8), plus flipping this
file's banner and DESIGN.md's.
