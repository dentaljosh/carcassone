# TILE-TIE PRICING — PRE-REGISTRATION

**Status: PRE-REGISTERED 2026-08-12, written and committed BEFORE any position is scored.**
The CENSUS (leaf evaluations only, no search, no oracle) HAS run — see
[CENSUS.md](census/CENSUS.md); it is a *sizing and replication* instrument and carries no
strength verdict. The SCORING run below is **DESIGNED, BUILT and PRICED ONLY — NOT LAUNCHED.**
The box and the funding decision belong to Joshua.

Lever row: `docs/LEVER_INDEX.md` → *"tile near-tie tie-break term · the 55% tile-tie blind spot
· `tiletie_pricing_20260812`"*.

---

## 0. PRE-SCORING AMENDMENT — 2026-08-12, applied BEFORE any position is scored

**Nothing here is a result.** Two items had to land before the run could be launched: §6
threat 3's dedupe (*"the ONE outstanding build item"*) and §7.4's un-measured `c_rust`
(*"a `walled`/rust smoke is the outstanding item before the rust arm's ETA is a
commitment"*). Both are now done. **No `headroom`, no `sigma2_arm`, no mean delta has been
read from anything** — the smokes below report *cost* and the CRN witness only, the same
discipline [SMOKE.md §4](SMOKE.md) applied to the python smoke. The read-rules in §4 are
untouched.

### 0.A The transposition dedupe is ARMED — realized saving **−26.2% positions / −32.2% arm-playouts**

`transposition_census.py` now emits the grouping itself (`bp_rid` = `build_positions.rid_for`,
plus `action_groups` / `repr_actions`), and `build_positions.py --afterstate-map` consumes it:
arms are deduped by successor board key **before** the cap `J`, and positions whose whole tie
set is one board are **not built**. Maps cover **1,427 / 1,427** qualifying positions across
all three profiles, **0 unresolved** (`census/afterstate_map_{fixed_v1,app_aug2,walled}.json`).

| | before (the 2026-08-12 19:47 plan) | after | Δ |
|---|---|---|---|
| positions built | 1,427 | **1,053** | **−374 (−26.2%)** — §6 predicted ~26% |
| arm-playouts (incl. champion arms) | 185,536 | **125,760** | **−32.2%** |
| tie-set arm-playouts (like-for-like) | 177,984 | **120,192** | **−32.5%** |
| mean arms / position | 3.03 | 2.87 | |
| positions bitten by the cap `J`=4 | 271 | 179 | |
| positions losing ≥1 duplicate arm | — | 188 | |

Dropped by stratum: **e4 115 · selfplay 259**. They are **not lost**: every one is written to
`positions/DROPPED_ALL_TRANSPOSITION.json` and **the analyser MUST add them back as exact
zeros** — that is what makes `headroom_all` (§6) estimable rather than merely definable.
⚠️ **New, and a sensitivity the analyser must run:** on **72 of the 374** the *played* action
lies **outside** the tie set. A different chain value implies a different tile afterstate, so
for those rows the analytic zero covers **the tie-set arms only**, not the played-vs-tie-set
contrast. They are flagged per-row in that file.

Guard rails, so this cannot silently un-arm: `build_positions` **requires** a map (explicit
`--no-dedupe` to build the pre-dedupe plan), and `run_tiletie.py`'s preflight **refuses to
launch** any plan whose `afterstate_dedupe.applied` is not `True`. Tests **52 → 66**, all green.

### 0.B `c_rust` is MEASURED, and it is **phase-weighted 1.4755** (the 1.65 reference was ~10% high)

A `walled` / **rust** / **selfplay** smoke at production knobs (M=32, `--oracle-sims 100`,
salt `tiletie-v1`, `clair-puct`), 5 positions × 2 legs = **10 records / 640 playouts, 5/5 ok,
`crn_verified_all`, CRN cross-leg witness PASS 5/5**, preflight PASS including the rust
identity gate **re-verified at HEAD** (8 positions, 376 field checks, 0 mismatches) →
`SMOKE_RUST_MANIFEST.json`, `GATE_BACKEND_RECHECK_RUSTSMOKE.json`.

```
c_rust (Σ elapsed_secs / playouts) = 788.0 / 640 = 1.2313 worker-s/playout
c_rust (wall x W / playouts)       = 3.2470          <- 2.64x too high, do NOT use
```

⚠️ **The §7.4 wall-vs-sum warning replicates on rust and is BIGGER there** (2.64× vs the
python smoke's 1.9×), because rust's per-position spread is wider relative to its mean.

⚠️ **That pooled 1.2313 is NOT the number to cost from either**, and the reason is §7.4's own
phase caveat: the smoke's 5 positions were **3 late + 2 mid**, while the Stage A rust arm is
**39.6% early / 27.5% mid / 32.9% late** by playout. So a second, deliberately **early**
3-position rust leg was run (ply 8 / 22 / 36, on self-play positions **outside** the Stage A
sample, so nothing in the scored set is peeked at). Measured, per phase:

| phase | records | Σ elapsed_secs | **`c_rust`** |
|---|---|---|---|
| early (ply 8–36) | 3 | 336.6 | **1.7533** |
| mid (ply 53–55) | 4 | 486.6 | **1.9007** |
| late (ply 112–118) | 6 | 301.5 | **0.7850** |
| pooled (all 13) | 13 | 1,124.6 | 1.3518 |
| ⭐ **weighted to the Stage A rust phase mix** | | | **1.4755** |

⇒ **`c_rust` = 1.4755 worker-s/playout** is the commitment figure; **1.65 was ~11.8% high**
for this mix. Two facts worth carrying: rust's phase spread is only **2.4×** (1.90 → 0.785),
*not* python's 9.3× — the clairvoyant playout length that dominates the python cost is not
what dominates the rust cost; and **mid is the most expensive bucket, not early**, which
inverts the python smoke's ordering. `c_python = 9.85` is unchanged (§7.4, measured).

⚠️ Both smokes ran at **W ≤ 8 on a quiet box**; a W=14 run has more DRAM contention, so every
figure below is an **optimistic** floor, not a ceiling. The python `c` additionally ran beside
another job and is an upper bound. Neither is re-measured at W=14 — that would cost more than
it buys.

### 0.C Stage A, re-priced — **2.37 h at local W14** (was 2.72 h)

Stage A is built and integrity-checked at `positions_stageA/` (its own
`POSITIONS_PLAN.json` / `ARMS.json` / `DROPPED_ALL_TRANSPOSITION.json`), seed `20260812`:
**340 positions = 280 selfplay/`walled` (rust) + 60 e4** (53 `fixed_v1` · 4 `walled` ·
3 `app_aug2`), **40,192 arm-playouts = 33,472 rust + 6,720 python**.

| Stage A component | worker-h | **W = 14 (local)** |
|---|---|---|
| power arm — selfplay / RUST (33,472 playouts × 1.4755) | 13.72 | **0.98 h** |
| relevance arm — e4 / PYTHON (6,720 × 9.85) | 18.39 | **1.31 h** |
| champion-pick pass, self-play arm only (280 × 13.7552 s) | 1.07 | 0.08 h |
| **★ Stage A TOTAL, one box** | **33.18** | **≈ 2.37 h** |

*(At the old `c_rust` = 1.65 the same plan is 34.80 worker-h / 2.49 h — the dedupe, not the
firmed `c`, is what moved this number.)* The full deduped supply (1,053 positions) would be
**158.3 worker-h ⇒ 11.3 h at W14**, which is why Stage A is the funding decision and Stage B
is bought only on the rust arm.

⛔ **The two-box split figure (§7.4's "≈1.2 h wall") is UNAVAILABLE TONIGHT** — the laptop is
occupied by an unrelated run. Recorded for the record only: at W=22 the same total is
**1.51 h**, and a python→laptop / rust→local split would land near **1.3 h** wall. **Do not
plan on it tonight.**

⚠️ **Launch the two arms as SEPARATE full-box invocations** (`run_tiletie.py --only-profiles
walled` then `--only-profiles fixed_v1 app_aug2`). One mixed launch splits the pool with
`split_workers`, which apportions by position **count** — and after §2.0 a python position
costs ~8× a rust one, so the python legs (17% of the lines, ~55% of the worker-seconds) get
~2 of 14 workers and become a ~7 h long pole. §7.4's table has always priced the two arms
separately and summed them; this makes the launcher able to honour that.

---

## 1. The question

The production leaf (`a36d2e15a3b3d71d`, the hand-tuned classical heuristic) **cannot
discriminate the top TILE placement** on a large share of tile decisions: the chain-argmax
values `argmax_t [ max_m leaf(s ∘ t ∘ m) ]` land in an **exact float tie** at the top on
7,817 of 14,190 TILE plies (**55.1%**) in the 2026-08-09 JCZ-mining dry run
([MINING_PREREG §7 rider 9](../jcz_mining_20260809/MINING_PREREG.md)). Separately, the
human-vs-AI loss evidence says the champion's losses live in **tile placement, never meeples**.
The champion (PIMC `k8×1376 = 11008` + exact-K≤2, rust) breaks these ties with pooled search.

> **THE QUESTION.** Do leaf-tied tile candidate sets contain **real value spread** that the
> search then resolves **wrongly** — i.e. is there anything for a tie-break term to buy — or
> are leaf ties **true value ties**?

Two sub-questions, deliberately separated because they have different answers and different
consequences:

- **Q1 / SPREAD.** Among candidates the leaf calls exactly equal, do the *oracle* values
  differ? This is a statement about the **leaf**, and the champion plays no part in it.
- **Q2 / REGRET.** Does the champion's 11008-sim search already pick the best member of the
  tied set? This is a statement about the **search**, and it is the one that decides whether a
  tie-break term has anything to add at deploy budget.

**Prior lean is NEGATIVE**, and it is on the record: the budget-headroom memo measured
**+0.0673 pts per changed pick** at the top of the sims ladder (cluster-robust z +0.33,
95% CI [−0.330, +0.467]) — *"above 5504 the deeper pick MOVES but does not IMPROVE"*
([MEMO §9.4/§9.7](../budget_headroom_bound_20260809/MEMO.md)). If deeper search churns
between moves of ~equal value at the top of the ladder, the default expectation is that
leaf-tied siblings are ~equal too. **The measurement must therefore be cheap and
bound-producing either way** — a null here has to ship an explicit pts/ply and elo bound, never
the sentence *"ties don't matter"*.

⚠️ **But the prior is not uniformly negative, and the counterweight is recent and specific.**
The simsplit census ([READOUT 2026-08-11](../simsplit_census_20260811/READOUT.md)) separated
TILE from MEEPLE flips under a budget ladder and found they behave like **different objects**:

- **Meeple** flips concentrate on near-ties (**71%**, 37/52, in the `[0, 0.02)` pooled-Q gap
  bin) and the flip rate is **nearly flat across an 8× budget range** (14.07 → 13.07 → 11.56%)
  — *"the marginal meeple sim is buying re-rolls of a coin, not convergence."*
- **Tile** flips occur *"across **every** stratum, including 13 flips at gap > 0.1: it changes
  picks it had previously scored as clear"*, and the rate **falls steeply** with budget
  (35.21 → 27.71 → 18.54%) — *"the signature of a search still genuinely converging."*

⇒ the coin-flip reading that the budget-headroom top-rung price supports is **measured on
meeples, not on tiles**. On tiles the same instrument says the search is still converging on
real structure. That is the strongest available argument that this measurement is worth its
price — and it is why the design must be able to detect a positive, not merely certify a null.

### 1.1 What the CENSUS found (it RAN — [CENSUS.md](census/CENSUS.md), 2,607 tile plies)

**The 55.1% does not merely replicate — it is an UNDER-statement on our own distributions.**

| stratum | n tile plies | **exact top-2 tie rate** | vs JCZ 55.1% |
|---|---|---|---|
| **E4 champion tile plies, `fixed_v1`** (the decision-relevant epoch) | 805 | **66.2%** [62.9, 69.4] | HIGHER |
| E4, `walled` | 72 | 55.6% [44.1, 66.5] | replicates |
| E4, `app_aug2` | 35 | 68.6% [52.0, 81.4] | HIGHER |
| self-play, CL-070 bank, `walled` | 495 | **64.0%** [59.7, 68.1] | HIGHER |
| self-play, `champ_games`, `walled` | 1,200 | **67.2%** [64.5, 69.8] | HIGHER |
| **ALL** | **2,607** | **66.0%** [64.1, 67.8] | HIGHER |

Four further census facts, each of which changed this design:

1. **Tied sets are LARGE, not pairwise.** Mean **8.55**, median **4**; only **38.1%** are 2-way,
   **32.8%** are ≥5-way, **17%** are ≥13-way. *A 2-way tie and a 13-way tie are different
   objects* — this is what forced the cap and the re-prioritisation in §4.6.
2. **The champion's real move is INSIDE the leaf's tie set 84.7% of the time** (E4 82.5%,
   self-play 86.0%) — but it equals the leaf's lowest-index tie-break only **60.8%** of the
   time. ⇒ on ~24% of tile plies the champion is *already applying a tie-break of its own*,
   silently, through pooled search. That is the behaviour this measurement prices.
3. **Phase trend is U-shaped in RATE and monotone in SIZE.** Tie rate early → mid → late =
   70.1% → 61.0% → 67.1%; mean tied-set size = **4.15 → 7.06 → 13.97**. Late-game tile decisions
   are the blindest, by a factor of 3 in set size.
4. **The epsilon band buys almost nothing, so exact ties are the whole phenomenon.** Tie rate at
   eps = 0.0 / 0.05 / 0.2 / 0.5 / 1.0 = 66.0% / 66.6% / 69.0% / 72.3% / 79.9%; the non-tie gap
   p5 is 0.15 and the modal gaps are 1.0, 3.0, 0.25, 1.5, 2.0 — a coarse integer-ish lattice
   with very little mass just below it. ⇒ §4.5's secondary read is cheap to state and will not
   move the verdict.

⚠️ **The census is a leaf-SILENCE census. It says nothing about whether tied moves differ in
value** — that is exactly what the scoring run is for, and why no strength claim is made here.

### 1.2 Why this is a mechanism class the closed levers do not cover

| context row | what it says | why it does not close this |
|---|---|---|
| **CL-073** | *Outcome prediction is not move discrimination* — a value head beat the heuristic at predicting the result (r 0.6795 vs 0.61) while losing sibling discrimination ~30×. | It is the **reason to look here**: the leaf's 55% tie rate is the same pathology stated as a raw fact about the heuristic. A term that only fires where the leaf is silent is a *discrimination* device, not a prediction device. |
| **CL-065** | Handed the leaf's own union-find features **and** exact-solver labels, **no learner** beats the leaf's sibling move ordering (max held-out τ 0.3856 vs leaf 0.6153; free-reweighting the leaf's own 4 terms only ties at 0.6157). | ⚠️ **This kills any LEARNED tie-breaker representation-independently.** A positive result here funds a **hand-crafted** term mined from evidence — nothing else. Stated here so no future reader re-derives the learned route. |
| **CL-078** | The leaf's **meeple-term SCALE axis** is measured null under `fixed_v1`, closed at ~±17 elo (4 powered cells, n=800 deck-paired each). | Scale closure is about **re-weighting terms that already fire**. A tie-break term fires **only where every existing term is exactly silent**, so it is a *different mechanism class* and must be argued as such — which is exactly what this pre-registration does. It does **not** inherit CL-078's closure, and it does **not** get to ignore it either: if this measurement fires positive, the term must still be shown to add value **on top of** an optimally-scaled leaf. |
| **CL-070 / budget-headroom §9** | The search has not converged above deploy, but the extra disagreements at the top rung are worth ~nothing (+0.0673 pts). | Sets the **prior** (negative) and supplies the **instrument, the price scale and the sd** used to size this run. |
| **CL-076** | Exact endgame depth saturates at the incumbent K=4; the return collapses ~7× exactly there. | The in-house proof that a component of the champion's search **cliffs**. A tie-break term is a candidate for the same shape: valuable at low budget, zero at deploy. Branch 3 below exists for exactly that outcome. |

---

## 2. Instrument

**`scripts/measurement_infra/oracle_score_pilot.py`, UNMODIFIED.** It is the ruler that
produced +0.7375 and +0.0673, and it is licensed on `--backend rust` by the committed identity
gate `measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` (20 positions, 940 field checks,
0 mismatches, every non-timing record field compared as raw f64 bit patterns). The launcher
**re-verifies that gate at HEAD before launch** and refuses to run if it does not reproduce.

### 2.0 ⚠️ THE BACKEND CONSTRAINT — found by the smoke, and it re-prices the run

**The rust clairvoyant continuation cannot be used on the E4 stratum.** The 5-position smoke
failed 5/5 on `fixed_v1` with the harness's own refusal:

> *"the clairvoyant Rust ruler cannot mirror `['start_row/start_col', 'fixed_start_tile',
> 'cloister_scan_fix', 'draw_rule']`: `RustCarryClairvoyantAgent` seeds `MirrorState.from_deck()`
> with no geometry/rules config (unlike the fair `RustFairAgent`, which forwards them), so it
> would run the engine-default rules against a game that does not. Build this ruler with
> `backend='python'` until the forwarding lands."*

This is the harness **failing loud instead of silently grading 23 of 26 E4 games under the wrong
rules** — the right behaviour, and it cost a 5-position smoke rather than a 6-hour run. It also
retroactively explains why `run_farmwar.py` never passes `--backend` at all: its E4 epochs could
not have used rust either.

⇒ **Backend is resolved per (judge, PROFILE), not per judge** (`run_tiletie.backend_for`):

| stratum | profile | judge | backend | note |
|---|---|---|---|---|
| self-play (bank, `champ_games`) | `walled` | `clair-puct` | **rust** | `game_kwargs()` is `{}` — the engine of record; covered by the identity gate |
| **E4** | `fixed_v1` (23/26), `app_aug2` (1/26) | `clair-puct` | **python** | rust mirror cannot represent these rules |
| E4 | `walled` (2/26) | `clair-puct` | rust | |
| any | any | `tier1-greedy` | python | out of the gate's scope regardless |

The committed identity gate measures the rust speedup at **9.41–9.48×**, and the two published
pilot runs bracket the same ratio end-to-end (python era 12.16 worker-s/playout vs the rust run's
1.65 ⇒ **7.4×**). **So the decision-relevant stratum is the expensive one**, and §7.4's ETA is
re-stated per backend rather than quoted as one number. This is the single largest cost fact in
this document and it was not knowable before the smoke.

- Judge: **`clair-puct`** (default), `--oracle-sims 100`, `--max-plies 400`.
- **M = 32 CRN deck completions** per position (`world_seeds` / `playout_seeds`), `--strict-crn`.
- Positions are supplied through the existing **`--positions-jsonl`** adapter (built for
  farm-war 2026-08-05), which requires `rid, deck_seed, ply, pick_a, pick_b, root_player` and
  either inline `actions` or an `archive_path`.

### 2.1 The K-way problem, and how it is solved WITHOUT touching the instrument

`_process` scores exactly **two** arms per row. A leaf tie is a **K-way** object. The design
therefore decomposes each position into `A_p − 1` two-arm **legs** against one fixed reference
arm, and exploits a property the house already relies on:

> the world and playout seeds are `sha256("world"|rid|j|salt)` — they are **keyed on `rid` and
> the run-wide salt, not on the arms**. `run_farmwar.py:15-17` states it explicitly and depends
> on it across judges and epochs.

⇒ **Run one `oracle_score_pilot` invocation per leg index `r = 1 … Kmax−1`**, each with its own
`--out-subdir`, each containing at most one row per position, and **give the row the same `rid`
in every invocation** (`load_positions_jsonl` only forbids duplicate rids *within* a file).
Every leg of a position then sees the **same M worlds and the same playout seeds**, so all arms
at a position are fully CRN-paired against each other, not just within a leg. No instrument
change, no wrapper, no new ruler.

**Costs 2(A−1) arm-playouts per world instead of the minimal A** — a ≤1.75× overhead at A=8,
1.0× at A=2 — and buys two things worth more than that:

1. full cross-arm CRN, which is what makes a *within-position* spread statistic estimable at
   all; and
2. a free integrity witness: the reference arm is re-scored in every leg under **identical**
   (world, playout) seeds, so **`values_a` must be bit-identical across all legs of a
   position**. The analyser asserts this. Any drift means the harness is not deterministic and
   the run is void.

### 2.2 Arms

For each sampled tile-decision position `p`:

- **Reference arm (`pick_a`, index 0) = the leaf's own tie-break of record** — the lowest
  action index among the exact-tie set, i.e. exactly what `argmax_chain` returns today. Every
  reported delta is therefore *"what a better tie-break would buy over the incumbent
  convention"*, which is the quantity the lever is about.
- **Candidate arms** = the remaining members of the exact-tie set, in ascending action order,
  **capped at `J`** (see §4.3). If `K > J` the members beyond the cap are dropped by a *seeded*
  uniform draw (seed `20260812`, recorded per position), never by index — index-truncation
  would correlate the drop with the tie-break convention itself.
- **The champion's actual pick** is always an arm. If it is already in the tie set it costs
  nothing extra; if it lies **outside** the tie set it is appended as one more arm and the
  position is flagged `champ_outside_tieset`.

### 2.3 Where the champion's actual pick comes from

| stratum | source of the champion pick | cost |
|---|---|---|
| **E4** | **the archive** — these are games the champion actually played at `sims_effective 1376`, `k_dets_effective 8` (= the production 11008). `action_played` at a champion tile ply *is* the champion's real pick, under real conditions. | **free** |
| **self-play** | a fresh production search at the position (`k8×1376`, exact-K≤2, rust, `fixed_v1` env off — see §3.2). | ~13.8 worker-s/position (PRODUCTION.yaml clock-legality block: 13.7552 s/move sequential) |

⚠️ The CL-070 bank already carries `q_pick_by_level["2752"]` — a pick at the **same total
budget 11008 but the k4 allocation**, not the champion's k8. It is **not** used as the champion
arm (PRODUCTION.yaml: k4 is optimal at total 2752, k8 at total 11008). It *is* read for free as
a cross-check and reported as `k4_pick_agrees_with_champ`.

---

## 3. Position sources — both strata are required

### 3.1 Stratum `e4` — the decision-relevant distribution

Champion TILE plies from the **26** human-vs-champion archives in `measurement/e4_games/*.json`.
Each game's rules profile is resolved **FROM THE ARCHIVE** with
`scripts/analyzer/ev_loss.py::resolve_profile_name` — never assumed. Today that resolves to
**23 `fixed_v1` · 2 `walled` · 1 `app_aug2`**. A ply qualifies iff `current_player == 1 −
human_player`, `phase == TILES`, `n_legal ≥ 2`.

This is the distribution the lever's motivating evidence lives on (the champion's losses are in
tile placement). It is also **supply-limited** — the census fixes the exact ceiling.

### 3.2 Stratum `selfplay` — volume

The **CL-070 root bank**, `/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl`
— 898 checksum-verified roots, of which **495 are `phase == "TILES"`** — plus a seeded sample
from the bank's own parent corpus `measurement/champ_action_logs/champ_games.jsonl` (449
champion self-play games, 57,675 eligible plies), max 4 plies/game, seed `20260812`. Every
emitted row carries `checksum = game.string_representation(board)` so lossless replay is
verified at scoring time exactly as `adaptive_k_census.py:336-341` does it.

⚠️ **The self-play stratum is `walled` rules.** The bank and its parent corpus predate
`fixed_v1` (2026-08-03). The E4 stratum is 23/26 `fixed_v1`. **The two strata are therefore a
rules-epoch contrast as well as a distribution contrast**, and the R9 farm-adjacency fix
touches farm scoring, hence the leaf, hence the ties. This is a known, unremovable design
tension at this cost (no `fixed_v1` self-play root bank exists), and it is handled the way
farm-war handled its epochs: **each position is replayed under its own profile, the strata are
reported separately, and they are NOT pooled if they disagree in sign.**

---

## 4. Statistics — read-rules fixed now

All statistics are **post-hoc arithmetic on per-world values the instrument already records**
(`values_a`, `values_b`, `per_world_delta`, `within_var`). No new measurement machinery.

Notation: `V[p,a,j]` = terminal margin in **final-score points, root player's seat**, at
position `p`, arm `a`, CRN world `j = 1…M`. Arm 0 is the reference (leaf tie-break of record).

### 4.1 S1 — SPREAD (is there anything to discriminate?)

**Naive range statistics are inadmissible here.** `max_a V̄ − min_a V̄` over noisy arm means is
biased **upward**: under the exact null (all arms truly equal) its expectation is strictly
positive, ~`0.8 σ` even at K=2. A design whose headline can manufacture a positive result out of
pure noise is not a design. Two estimators are pre-registered instead, both unbiased under the
null:

**S1a — variance components (primary spread statistic).** Arms × worlds is a two-way layout
without replication, blocked on the CRN world. With `MS_arm` and `MS_resid` the usual mean
squares over the `A_p × M` matrix at position `p`:

```
sigma2_arm[p]  =  (MS_arm[p] - MS_resid[p]) / M
```

`E[sigma2_arm] = 0` under the exact null. **The signed value is kept, including when negative**
— truncating at zero would reintroduce exactly the bias the estimator exists to remove.
Headline: `mean_p sigma2_arm` in **pts²**, cluster-bootstrapped on `root_id`; reported also as
`rms_spread = sqrt(max(0, mean))` in pts, labelled as a derived, non-inferential summary.

**S1b — cross-fit best-minus-worst gap (interpretable spread).** Worlds are split by index
parity, fixed now: **even `j` = SELECTION half, odd `j` = EVALUATION half**. Select
`a⁺ = argmax_a mean_{j even} V`, `a⁻ = argmin_a mean_{j even} V`; report
`G[p] = mean_{j odd} V[p,a⁺,j] − mean_{j odd} V[p,a⁻,j]`.
Selection and evaluation use disjoint worlds ⇒ `E[G] = 0` under the null and `E[G] ≤` the true
range otherwise. **`G` is a downward-biased estimate of the true range and an unbiased test of
the null** — quote it with that sentence attached.

### 4.2 S2 — REGRET (does 11008-sim search already break ties as well as anything could?)

Same parity cross-fit. `a⁺` is selected on the even worlds **from a pool that INCLUDES the
champion's own pick** — the champion is a legitimate candidate for "the best tie-break rule",
and including it makes `E[R] = 0` exactly under the null.

```
R[p]  =  mean_{j odd} V[p, champ, j]  -  mean_{j odd} V[p, a+, j]        # <= 0 means the search missed
headroom[p]  =  -R[p]                                                    # pts per tied tile ply
```

**`headroom` is the deliverable.** `E[headroom] = 0` under the null; it is the value a
*perfect, oracle-informed* tie-break would add over the champion's current behaviour — i.e. a
**ceiling** on any hand-crafted term, not an estimate of one.

**S2b — incumbent-leaf regret (free companion).** The same with arm 0 (the leaf's
lowest-index convention) in place of the champion. This prices the tie-break for a *greedy leaf*
consumer — the PUCT priors, and the mobile profile at `k4×688` — where the search has far less
budget to rescue a blind leaf. It is reported but is **not** the headline: nothing in this
project deploys a greedy leaf.

Naive (non-cross-fit) versions of S1b and S2 are computed **and printed** alongside, purely so
the size of the winner's-curse correction is auditable. They are never quoted as results.

### 4.3 The bound chain (the deliverable, in the memo's own arithmetic)

Identical chain to `analyze_kwidth110k_oracle.py:52-71` / budget-headroom §9.6, so the number is
directly comparable to the +0.0673 price and the ≈+7 elo bound:

```
tied_tile_plies_per_game =  DECISIONS_PER_GAME(71.5) x tile_ply_share x exact_tie_rate   # both measured by the CENSUS
pts_game                 =  headroom x tied_tile_plies_per_game / NON_ADDITIVITY(3.2)
wr                       =  0.5 + (pts_game / SIGMA_GAME) x phi(0)                        # sigma 20.4 (fixed_v1), 22.2 (walled) reported as sensitivity
elo                      =  400 x log10(wr / (1 - wr))
```

⚠️ Every caveat the memo attaches to this chain is inherited verbatim and must be quoted with
any number produced by it: `NON_ADDITIVITY = 3.2` is **n = 1**, is calibrated at the top of the
ladder, and §4.2 of the memo shows a range-consistent divisor at the low end would be ≈5.23;
the linear-φ approximation degrades above ~1σ. The divisor enters **linearly**, so a bound
quoted through it is quoted with a ±1.6× bracket, not as a point.

### 4.4 Decision map — branch precedence 1 → 2 → 3 → 4, first match wins

Two-sided throughout. `elo(x)` means "x carried through §4.3". Thresholds are the project's own
resolution constants, not new ones: **±17 elo ≈ 1σ at n=400**, **+35 elo ≈ the 2σ re-open bar**
that PRODUCTION.yaml's own promotions cite.

1. **`elo(headroom_CI_hi) < +17`** ⇒ **CLOSED WITH A BOUND.** *A perfect oracle tie-break over
   the leaf's exact-tie tile sets is worth less than +17 elo at deploy budget; the tie-break
   term axis is closed at the project's own 1σ resolution.* The bound ships in **pts per tied
   tile ply AND elo, with the §4.3 bracket**. It does **not** license *"ties don't matter"*, and
   it does not speak to near-tie (eps > 0) sets beyond what §4.5 measures.
2. **`elo(headroom_CI_lo) > +17`** ⇒ **HEADROOM IS REAL AND RESOLVED.** A hand-crafted tie-break
   term is warranted. **Next step is NOT to build one blind**: it is to mine *which* feature
   separates `a⁺` from arm 0 inside the tied sets (the per-position records carry both
   afterstates). ⚠️ **CL-065 forbids the learned route** — the term must be hand-crafted from
   that mined evidence, and it must then be shown to add value on top of an optimally-scaled
   leaf (CL-078).
3. **S1a `sigma2_arm` CI excludes 0 (real spread) AND `elo(headroom_CI_hi) < +17`** ⇒
   **THE LEAF IS BLIND BUT THE SEARCH IS NOT.** 11008 sims already recover the spread. This
   closes the *desktop* term and opens a strictly narrower question — whether the term pays at
   **low budget** (priors, the mobile `k4×688` profile), where S2b is the relevant statistic.
   It does not license a desktop leaf change.
4. **otherwise** ⇒ **INCONCLUSIVE.** Report the estimate and its CI; promote nothing. The
   read-out must state the **realized** sd and the **n required** to reach a ±17-elo bound at
   that sd, so the extension decision is arithmetic and not a new argument.

**Cluster-robust on `root_id` throughout** (positions from one game share a root; the oracle
pilot's own design-effect lesson was 628 records over 385 roots). Bootstrap CIs resample
**roots**, 20,000 reps, seed `20260812`.

**Stratum rule (from farm-war, verbatim in spirit):** the **pooled** estimate is primary;
`e4` and `selfplay` are reported separately and **are not pooled if they disagree in sign**.
Per-stratum reads are expected to be underpowered on their own and are labelled as such.

### 4.5 The epsilon band (secondary)

Exact ties are primary. An epsilon band is the secondary read, and **epsilon is chosen from the
observed top-2 gap distribution, not from taste** — see [CENSUS.md](census/CENSUS.md) §3, which
reports the gap quantiles and the top lattice gap values. The pre-registered grid is
`eps ∈ {0.0, 0.05, 0.2, 0.5, 1.0}` because those are the leaf's own lattice steps (integer base
+ `{0.5, 0.2, 0.05} × Δ` + curve steps). **The scored run scores the exact-tie set only.** The
eps bands are carried as a *census* result and as the sensitivity that says how far the exact-tie
bound can be stretched: if the eps-band tie rate at the chosen eps is `r_eps` and the exact rate
is `r_0`, the eps-band headroom bound is quoted as the exact bound × `r_eps / r_0` **and labelled
an extrapolation, not a measurement.**

### 4.6 The cap `J` — and why the census forced a change to §4.1/§4.2's priority

**The census killed the original plan for `J`.** The pre-census intent was *"set `J` so ≥90% of
tied positions are scored uncapped"*. That is unaffordable: the measured tied sets are **large**
— mean **8.55**, median **4**, only **38.1%** are 2-way, **17%** are 13-way or bigger
([CENSUS.md §2](census/CENSUS.md)). Scoring every tied set in full costs **7.71 legs per
position**, 3.4× the J=4 price. Measured trade-off, from the census (`legs = A_bar − 1`, arms
include the champion's pick when it falls outside the set):

| `J` | mean legs/position | % of tied positions scored UNCAPPED |
|---|---|---|
| 2 | 1.151 | 38.1% |
| 3 | 1.770 | 49.1% |
| **4 (adopted)** | **2.279** | **67.2%** |
| 6 | 2.918 | 73.3% |
| 8 | 3.440 | 79.0% |
| 12 | 4.216 | 83.0% |
| ∞ | 7.705 | 100% |

**`J = 4` is adopted**, and the ≥90%-uncapped criterion is **abandoned as unreachable at any
sane price**. That is a substantive change, so the statistics are re-prioritised to survive it:

- ⭐ **S1a (`sigma2_arm`) is PROMOTED to the primary statistic, because it is CAP-INVARIANT.**
  The scored arms are a *uniform seeded draw* from the tied set, so the between-arm variance
  they exhibit is an unbiased estimate of the between-arm variance of the **whole** tied set, at
  any `J ≥ 2`. Capping costs precision, not validity. This is the property that makes a
  cheap run possible at all, and it is why §4.1 built a variance estimator rather than a range.
- **S2 (`headroom`) is measured over the SCORED subset**, so it is the regret against
  *best-of-J*, not best-of-K. With mean K = 8.55 and J = 4 the shortfall is **not marginal** and
  must not be waved at. It is quantified, not ignored: under the tied set's own estimated
  spread, `E[max of n draws] − mean = sigma_arm × a_n` with `a_2 = 0.56, a_4 = 1.03,
  a_8.55 ≈ 1.44`, so the **full-set ceiling is ≈ 1.40× the J=4 measured headroom**. The read-out
  reports both: `headroom_J4` (measured) and `headroom_fullset ≈ 1.40 × headroom_J4`
  (**an extrapolation through the S1a spread estimate, labelled as such — never quoted as a
  measurement**). §4.4's branch thresholds are applied to the **extrapolated** figure, so the
  cap cannot manufacture a closure.
- The read-out additionally reports branch-1/2 arithmetic on the **uncapped subset alone**
  (`K ≤ 4`, 67.2% of tied positions) as the assumption-free check on that extrapolation.

---

## 5. The judge, and the in-family bias — honestly

The primary judge is `clair-puct`: a clairvoyant PUCT agent that uses **the same leaf under
test** at its own leaves. Farm-war's blunt statement of the general problem stands — *"a
positive result through it is conservative; a null through it is uninformative"*. **That
statement is materially weaker here, and the reason is specific to tie sets:**

- **The first-order bias is absent by construction.** The usual mechanism — the judge prefers
  what the leaf prefers — cannot fire between candidates the leaf scores **exactly equal**. At
  depth 0 the judge has *no* preference among the arms. Its entire discrimination comes from
  **search depth** and the clairvoyant deck, applied to positions where the leaf itself is
  silent. This design is the most favourable case for an in-family judge that this project has
  constructed.
- **The residual bias is second-order, and it points DOWN.** The judge's deeper nodes are still
  scored by the same leaf. If the leaf's blindness is **systematic** — a feature it never
  represents, e.g. farm-race tempo — then a judge built on it is blind to that feature at every
  node too, and will **under-report** the true spread. If the blindness is **idiosyncratic**
  (lattice quantisation at this particular node), the judge recovers it and the estimate is
  unbiased.
  ⇒ **A null through this judge closes "spread visible to a deep clairvoyant search over THIS
  leaf", not "spread in truth".** Branch 1's claim is written to exactly that scope and must be
  quoted with it.
- **The out-of-family sign check is therefore not optional here.** `--oracle-policy
  tier1-greedy` — a greedy `RuleBasedPlayer` sharing neither the search nor the leaf (it runs
  the **v1 OBJECT leaf**, not `flat_leaf`) — is run on a **pre-registered subset of n = 80**
  positions drawn with seed `20260812` from the scored set. ⚠️ **SIGN ONLY.** It is ~1.83×
  noisier, has no curve125, and has **no rust path** (the identity gate explicitly excludes it:
  *"tier1-greedy is out of scope"*), so it runs on `--backend python`. Its magnitude is **never**
  compared to the primary's — the LEVER_INDEX row on the 2026-07-28 discriminator is explicit
  about that trap.
- **The judge is not the champion.** `clair-puct` at `--oracle-sims 100` is a far weaker
  continuation than real play. This is the oracle pilot's untouched secondary threat and it is
  untouched here: it biases toward whichever move looks better under shallow clairvoyant play,
  **direction unknown**.

---

## 6. Pre-stated threats

1. **In-family judge** — §5. Tested-by-sign, not eliminated; the null's scope is narrowed in
   writing rather than papered over.
2. **Chain-granularity on the TILE class** (inherited verbatim from
   [MINING_PREREG threat 4](../jcz_mining_20260809/MINING_PREREG.md)). Our tile candidates are
   *chain*-argmax values — `max_m leaf(s ∘ t ∘ m)` — but the oracle scores the **tile action
   only** and then lets its own continuation choose the meeple. **Neither arm actually gets the
   meeple its chain value assumed.** Milder here than in the mining design (we compare tiles the
   leaf calls equal, so the assumed meeples differ only as much as the tiles do), but real, and
   in an unknown direction.
3. ⭐ **Transpositions — MEASURED, LARGE, and now handled in the DESIGN rather than as a
   caveat.** Two tied tile placements can reach the **same** afterstate (rotationally symmetric
   tiles), making Δ exactly 0 by *identity* rather than by equivalence of value. The smoke found
   this in **2 of its 5 positions** (`distinct_afterstates == 0` in all 32 worlds), so it was
   measured directly over the whole tied population by
   `scripts/tiletie/transposition_census.py` (leaf-side only, no oracle):

   | stratum | tied positions | **whole tie set is ONE board** | ≥1 duplicate arm | mean tie size | mean **distinct** | shrink |
   |---|---|---|---|---|---|---|
   | `e4` / `fixed_v1` | 445 | **23.8%** | 37.3% | 3.611 | 2.703 | 0.749 |
   | `selfplay` / `walled` | 932 | **27.8%** | 40.9% | 3.673 | 2.715 | 0.739 |

   ⇒ **roughly a quarter of "leaf ties" are not blindness at all** — they are the leaf correctly
   assigning equal value to *the same position*. The rate is flat across phase (early 23.7 /
   mid 22.7 / late 25.0 on E4), so it is not a late-game artifact.

   **Consequence, adopted into the design (§2.2 amendment):**
   - **Arms are DEDUPLICATED by successor board key** before the cap `J` is applied. A duplicate
     arm carries no information and costs a full leg.
   - **Positions whose entire tied set collapses to one board are NOT SCORED.** Their
     contribution to `headroom` is exactly **0 with zero variance**, known analytically — so
     they are **included in the population average as exact zeros** and excluded from the
     compute. Same estimand, ~26% less compute, and *lower* estimator variance.
   - The headline is therefore reported twice, and both are pre-registered: **`headroom_all`**
     (over all exact-tied tile plies, the number that feeds §4.3's elo chain) and
     **`headroom_discriminable`** (over the ~74% with ≥2 distinct afterstates, the number that
     describes the leaf's actual blindness). `headroom_all = 0.74 × headroom_discriminable`.
   - ⚠️ **The census's 66.0% headline is a LEAF-SILENCE rate, not a blindness rate.** Net of
     whole-set transpositions the genuine-blindness rate is ≈ **66.2% × (1 − 0.199) ≈ 53%** on
     E4 `fixed_v1` (19.9% = 106 all-transposition / 533 tied, including the >12-way rows the
     transposition pass does not cover). *The JCZ 55.1% is uncorrected too, so the
     census-vs-JCZ comparison in §1.1 remains apples-to-apples at the raw level.*

   ✅ **ARMED 2026-08-12 — see [§0.A](#0a-the-transposition-dedupe-is-armed--realized-saving-262-positions--322-arm-playouts).**
   `build_positions.py --afterstate-map` now dedupes arms by successor board key and drops
   all-transposition positions (written to `positions/DROPPED_ALL_TRANSPOSITION.json` as the
   analytic zeros they are); `run_tiletie.py`'s preflight refuses a plan built without it.
   Realized: **1,427 → 1,053 positions (−26.2%), 185,536 → 125,760 arm-playouts (−32.2%)** —
   the ~26% prediction below held. *(Was: "the ONE outstanding build item … it must land
   before the run is launched — not because the estimate would be wrong without it (the zeros
   are real), but because ~26% of the budget would buy known-zero rows.")*
4. **"Exact tie" is a lattice property, not an indifference proof.** The leaf lands on a coarse
   value lattice; an exact tie means *"the leaf has no resolution below its lattice step here"*.
   That is precisely the blindness of interest, but the claim language must say **that** and not
   *"the leaf judged them equal"*.
5. **Selection on ties conditions on a leaf property, so regression to the mean pushes the
   measured spread toward 0** on re-scoring by an independent instrument. This makes a positive
   harder, not easier — i.e. it protects branch 2 and threatens branch 1. Stated, not corrected.
6. **Rules-epoch confound between strata** (§3.2): `selfplay` is `walled`, `e4` is 23/26
   `fixed_v1`. Handled by per-stratum reporting + the no-pooling-on-sign-disagreement rule.
   ⚠️ Not fixable at this cost.
7. **E4 supply is small and comes from one human's games.** The `e4` stratum measures the leaf
   on *positions his play produces*, not on tile decisions in general — farm-war's threat 3,
   unchanged.
8. **Cap `J` truncation** — §4.6, direction known and conservative.
9. **The champion pick on the `selfplay` stratum is recomputed, not archived.** It is the same
   agent at the same knobs, but it is a fresh search with a fresh seed, and CL-070 measured that
   reseeding **alone** flips ~26–30% of picks at fixed budget. The recorded pick is therefore
   *a* champion pick, not *the* champion pick — which is the honest object anyway, since the
   champion is stochastic. Reported: the free `k4_pick_agrees_with_champ` cross-check, and the
   bank's own 3 reseeded replicates per root (`salt` 1/2/3) as a direct read of **how often the
   champion-budget search even agrees with itself inside a tied set**.

---

## 7. Sizing, cost and the ETA

### 7.1 The cost model

```
oracle_worker_secs  =  n_positions x (A_bar - 1) x 2 x M x c
champ_pick_secs     =  n_selfplay  x t_champ                       # E4 arm is free (archived)
wall_hours          =  (oracle_worker_secs + champ_pick_secs) / (3600 x W)
```

- `A_bar` = mean arms per position = mean scored tied-set size (+1 when the champion pick falls
  outside the set) — **measured by the census**.
- `c` = worker-seconds per playout — **measured by the 5-position smoke at production knobs**
  (§7.4). Reference value from the top-rung budget-headroom run: 150 positions × M 32 × 2 arms
  = 9,600 playouts in 990.1 s at W16 = **15,840 worker-s ⇒ c ≈ 1.65 worker-s/playout**, rust
  backend, `--oracle-sims 100`. Our positions come from a different phase mix, so this is a
  reference, not the estimate.
- `t_champ ≈ 13.76` worker-s (PRODUCTION.yaml: k8×1376 sequential 13.7552 s/move on a quiet
  5900XT).

### 7.2 Power

The planning sd is transplanted from the instrument's **own** published M-projection — the
`sd_delta_projected_by_m` field of the two oracle-pilot `summary.json` files, read off disk:

| run | M=8 | M=16 | **M=32** | M=64 |
|---|---|---|---|---|
| `oracle_score_pilot` (2752v11008, n=100) | 4.287 | **3.160** | 2.406 | 1.921 |
| `oracle_score_pilot_5504v11008` (n=150) | 4.041 | **2.984** | 2.279 | 1.826 |

The cross-fit statistics of §4.1/§4.2 evaluate on **M/2 = 16** worlds ⇒ **planning sd ≈ 3.0–3.2
pts per position**, which is the M=16 column above, not an extrapolation.

> ✅ **The smoke measured this ON OUR OWN POPULATION and it came in BETTER:**
> `sd_delta_positions = 2.257` at M=32 on the 5 E4 `fixed_v1` smoke positions, projecting to
> **2.709 at M=16** — i.e. the leaf-tied population is *tighter* than the CL-070 disagreement
> population the planning number came from, exactly as the "tied siblings are similar" prior
> predicts. **n = 5, so this is a coarse nuisance-parameter read, not a verdict**, but it is
> on-population and it moves the sizing table's operative column from 3.0 to ~2.7:
> **±35 elo needs n ≈ 228; ±17 elo needs n ≈ 965.**
>
> ⚠️ **The smoke's mean delta is deliberately NOT reported here.** It is a 5-position read of a
> quantity this document pre-registers, and quoting it would be peeking at the result the run
> exists to measure. Only the **sd** — a nuisance parameter, which is precisely what the
> original oracle pilot was built to measure — is carried forward. The analyser reads the mean,
> once, on the full run, through §4.4.

⚠️ It is a
transplant from a *disagreement* population; leaf-tied siblings could be tighter (the
hypothesis) or looser. **The staged design below exists because of that uncertainty, and Stage A
re-measures it.**

`elo(headroom) = Kelo × headroom`. **`Kelo` is now measured, not assumed:** the census counts
**22.96 exact-tied champion tile plies per E4 game** (597 tied plies / 26 games — the tile share
and the tie rate are both realized, so `DECISIONS_PER_GAME × share × rate` is replaced by a
direct count). Through §4.3 at `NON_ADDITIVITY = 3.2` and `σ_game = 20.4`:

> **`Kelo` = 97.5 elo per pt per tied tile ply** (i.e. `headroom = 0.10 pts ⇒ +9.75 elo`).

| bound target | needed `2·se` (pts) | n at sd 2.0 | **n at sd 3.0** | n at sd 3.16 | n at sd 4.0 |
|---|---|---|---|---|---|
| **±35 elo** (the 2σ re-open bar) | 0.359 | 125 | **280** | 311 | 497 |
| **±17 elo** (1σ at n=400) | 0.174 | 527 | **1,185** | 1,315 | 2,107 |

### 7.3 The staged plan (pre-registered, so the extension is arithmetic)

- **Stage A — n = 280.** Buys a **±35 elo** bound at the planning sd, and, more importantly,
  **measures the real sd** on this population. Read Stage A against §4.4 immediately: if
  `elo(CI_hi) < +17` already (which happens whenever the point estimate is near 0 **and** the
  realized sd is below ~2.05), **the lever is closed and Stage B is never funded.**
- **Stage B — extend to `n = ceil((2 × sd_A / 0.174)²)`, capped at 1,300** — funded only if
  Stage A lands in branch 4 (inconclusive) or branch 2/3. `--resume` makes it a pure extension
  of the same records directory: no re-scoring, no new ruler.
- **Allocation — REVERSED by the §2.0 backend constraint.** The pre-smoke plan was *"`e4`
  first, it is the decision-relevant stratum"*. That is now the **expensive** stratum by roughly
  an order of magnitude, because it cannot use rust. The allocation is therefore:
  - **`selfplay` (`walled`, RUST) carries the POWER.** It is the cheap arm and supplies the n
    that makes the bound tight. Supply after the census: 1,123 tied positions (317 bank + 806
    `champ_games`); 932 survive the ≤12-way truncation filter into the built plan.
  - **`e4` (`fixed_v1`, PYTHON) carries the RELEVANCE, at a deliberately smaller n.** It is
    reported as a **sign-and-magnitude check on the decision-relevant distribution**, explicitly
    underpowered on its own, and it is the stratum that decides whether the strata agree well
    enough to pool (§4.4's stratum rule). Supply 495 built positions.
  - ⇒ **Stage A = 280 `selfplay`/rust + 60 `e4`/python.** If the two disagree in sign, §4.4
    forbids pooling and the read-out says so rather than averaging them.

  **Total tied supply is 1,427 built positions** (495 e4 + 932 selfplay), so even the ±17-elo
  target sits inside the census bank with no new self-play. *(1,720 positions are exactly tied;
  293 of them are >12-way ties whose member list the census truncates, and those are excluded
  from scoring — the read-out must state that the scored population is the **≤12-way** tied
  set, which is a mild selection against the very blindest positions and therefore
  conservative for branch 2.)*
- **Tier-1 out-of-family sign leg: n = 80**, seeded subset, run **after** the primary and only
  if the primary is not branch-1-closed at Stage A (a closed axis does not need a sign check).

### 7.4 ETA

Per-position worker-seconds `= (A_bar − 1) × 2 × M × c`. The built plan gives
**130.0 arm-playouts per position** (185,536 playouts / 1,427 positions = 2.031 legs at M = 32,
`J = 4`). `c` is now **MEASURED, per backend**:

| backend | `c` (worker-s/playout) | source |
|---|---|---|
| ~~**rust**~~ ⇒ **SUPERSEDED by [§0.B](#0b-c_rust-is-measured-and-it-is-phase-weighted-14755-the-165-reference-was-10-high): `c_rust` = 1.4755 (measured, phase-weighted)** | ~~1.65~~ *(reference)* | budget-headroom run: 9,600 playouts / 15,840 worker-s, on CL-070 *disagreement* positions |
| **python** (`fixed_v1` E4) | **9.85** *(measured)* | ⭐ **this smoke**: Σ per-position `elapsed_secs` = 3,152.6 worker-s / 320 playouts, 5/5 ok, `crn_verified_all` true |

⚠️ **Measure worker-seconds as `Σ elapsed_secs`, not `wall × W`.** The naive wall-based figure
for this same smoke is **18.75** — 1.9× too high — because the pool's wall is set by its slowest
position and these positions are wildly heterogeneous. The launcher's `--smoke` prints the
wall-based number; **the `Σ elapsed_secs` figure is the one to cost from**, and it is the one
used below.

⭐ **Cost per position varies ~9× with game phase**, measured on the smoke's own five positions:

| ply | 10 | 34 | 106 | 114 | 134 |
|---|---|---|---|---|---|
| worker-secs | **1,199.8** | 1,042.9 | 421.1 | 359.1 | **129.7** |

Early roots have far longer clairvoyant playouts to terminal. ⇒ **any ETA is a function of the
sampled phase mix**, the sampler must not be allowed to drift phase-wise between stages, and a
run that over-samples early positions will overrun its estimate. The census's `phase_bucket` /
`tercile` fields exist to let the read-out check this after the fact.

⚠️ The rust `c = 1.65` is a **reference from a different position mix** (CL-070 disagreements
skew mid/late, i.e. cheap). Do **not** read `9.85 / 1.65 = 6.0×` as the backend speedup — the
identity gate measures that at **9.41–9.48×** on matched positions. Each `c` is applied only to
its own stratum below, and the rust arm's `c` should be re-measured by a `walled` smoke before
the rust ETA is treated as a commitment.

Per position (130.0 playouts): **rust ≈ 214.5 worker-s · python ≈ 1,281 worker-s.**

⚠️ **The whole table below is PRE-DEDUPE and pre-`c_rust`. [§0.C](#0c-stage-a-re-priced--237-h-at-local-w14-was-272-h)
is the priced-and-built figure of record (Stage A = 2.37 h at W14 over 340 positions);
the rows here are kept as the derivation and for the arms this run does not buy.**

| stage | stratum / backend | n | worker-h | **W = 14 (local)** | **W = 22 (laptop)** |
|---|---|---|---|---|---|
| smoke (RAN) | e4 / python | 5 | 0.88 | measured: 20 min/leg at 5 workers | — |
| **★ Stage A — power arm** | **selfplay / RUST** | **280** | **16.7** | **1.19 h** | **0.76 h** |
| **★ Stage A — relevance arm** | **e4 / PYTHON** | **60** | **21.3** | **1.52 h** | **0.97 h** |
| **★ Stage A TOTAL, one box** | | **340** | **38.0** | **2.72 h** | **1.73 h** |
| **★ Stage A, SPLIT across both boxes** | rust→local W14, python→laptop W22 | 340 | 38.0 | **≈1.2 h wall** | (concurrent) |
| Stage B — extend the rust arm to ±17 elo (sd 2.71 ⇒ n ≈ 965) | selfplay / rust | 965 | 57.5 | **4.10 h** | 2.61 h |
| Full self-play supply, if ever wanted | selfplay / rust | 932 | 55.5 | 3.97 h | 2.53 h |
| ⛔ Full E4 supply — **NOT AFFORDABLE** | e4 / python | 495 | 176 | **12.6 h** | 8.0 h |
| champion-pick pass — Stage A rust arm needs it | selfplay | 280 | 1.07 | 4.6 min | 2.9 min |
| champion-pick pass — **e4 arm needs NONE** (archived) | e4 | 60 | 0 | **0** | 0 |
| Tier-1 out-of-family sign leg (python) | mixed | 80 | 28.5 | 2.0 h | 1.3 h |

⇒ **The funding decision is Stage A: ≈1.2 h wall split across the two boxes, ≈2.7 h on the local
box alone.** Stage B is a further ~4.1 h that buys the ±17-elo bound, and it is bought **only on
the rust arm** — the E4 arm cannot be scaled at this price and is not meant to be.

⭐ **The E4 arm costs ZERO champion searches** — those games were played by the champion, so
`action_played` *is* its pick. Only the self-play arm pays the (small) `champ_picks` cost.

⛔ **Do not run the Tier-1 sign leg at Stage A.** At 3.9 h it costs as much as the entire primary
and, per §5, it is only worth buying if the primary does **not** branch-1-close. It is priced
here so that decision is arithmetic.

The launcher prints exactly this arithmetic and **refuses to proceed without `--yes`**, which is
how the run gets priced without being launched.

⚠️ **Timing caveat on the measured `c`.** The smoke ran while an unrelated 6-worker
`oracle_score_pilot` job held the box. Per the standing rule that *a throughput farm beside a
timing bench contaminates the bench*, the smoke's seconds/position is an **upper bound on cost,
not a clean measurement** — the real figure on a quiet box is lower, so every ETA above is
conservative. Re-measure on a quiet box before treating any of these as a commitment.

---

## 8. Governance

**Measurement only.** `governance/PRODUCTION.yaml` untouched. No champion change, no promotion
on any branch.

- **NO `experiments/results.csv` row — deliberately, not by oversight.** This instrument has no
  opponent, no elo and no W/L/D; **0 games are played**. Budget-headroom §9.8 established the
  precedent and the reason. Numbers live in `summary.json` / the read-out.
- **NO band claim, no `governance/BAND_REGISTRY.csv` entry** — no games, no deck band.
- **A claim id is minted only on branch 1, 2 or 3** (branch 4 mints nothing). Branch 1's claim is
  a *closure with a bound* and must carry the §5 scope sentence in its text.
- Close-out on read-out is the standing six touches: DECISIONS index line · status stamp on this
  file · `governance/CLAIM_REGISTRY.csv` row · STATUS top block · the
  [roadmap](../../docs/PROGRAM_ROADMAP_2026-07-07.md) line · and the `docs/LEVER_INDEX.md`
  tile-tie row flipped off "in flight". Then `python3 scripts/doc_lint.py`.

---

## 9. Files

| file | what |
|---|---|
| `scripts/tiletie/chain_census.py` | chain enumeration + tie extraction — a copy of `mine_disagreements.chain_values`/`argmax_chain`, **proven bit-identical in pytest against the original on 3 real bank roots** |
| `scripts/tiletie/run_census.py` | census driver — one subprocess per rules profile (R9 is import-latched) |
| `scripts/tiletie/build_positions.py` | census rows → per-(profile, leg) `--positions-jsonl` + `ARMS.json` + `POSITIONS_PLAN.json` + `DROPPED_ALL_TRANSPOSITION.json`. **`--afterstate-map` (required, §0.A)** dedupes arms and drops all-transposition positions; `--n-e4` / `--n-selfplay` build the §7.3 Stage A allocation |
| `scripts/tiletie/transposition_census.py` | the transposition measurement **and** the dedupe join input (`bp_rid` / `action_groups` / `repr_actions`) — one process per rules profile, R9 is import-latched |
| `scripts/tiletie/champ_picks.py` | the self-play champion-pick pass (`k8×1376`, `reseat`-based) + the free CL-070 `k4×2752` cross-check. **Not needed for Stage A** (§7.4) |
| `scripts/tiletie/run_tiletie.py` | the scoring launcher — preflight (gate at HEAD, leaf hash, git-clean, plan integrity), per-(judge, profile, leg) subprocesses, `--yes` gate, `--smoke`, the CRN cross-leg witness |
| `tests/test_tiletie_census.py` (11) · `tests/test_tiletie_positions.py` (55) | coverage — **66 tests, all green** (+14 for §0.A/§0.C: dedupe, dedupe-before-cap, the all-transposition drop + its dropped index, stale-map refusal, champion-arm transposition mapping, the preflight guard, the per-stratum Stage A allocation, `--only-profiles`, the smoke stratum filter) |
| `measurement/tiletie_pricing_20260812/census/afterstate_map_*.json` | the dedupe join input, one per rules profile (1,427/1,427 rows, 0 unresolved) |
| `measurement/tiletie_pricing_20260812/census/` | census artifacts + [CENSUS.md](census/CENSUS.md) |
| `measurement/tiletie_pricing_20260812/positions/` | the built full-supply plan, **deduped**: 11 leg files, `ARMS.json`, `POSITIONS_PLAN.json`, `DROPPED_ALL_TRANSPOSITION.json` (374 analytic-zero rows) |
| `measurement/tiletie_pricing_20260812/positions_stageA/` | **the Stage A plan actually priced in §0.C** — 340 positions (280 selfplay/rust + 60 e4), 10 leg files |
| `measurement/tiletie_pricing_20260812/SMOKE_RUST_MANIFEST.json` | the `walled`/rust/self-play smoke behind §0.B's `c_rust` (+ `GATE_BACKEND_RECHECK_RUSTSMOKE.json`, the gate re-verified at HEAD) |
| `measurement/tiletie_pricing_20260812/GATE_BACKEND_RECHECK.json` | the rust identity gate **re-verified at HEAD: PASS, 8 positions, 376 field checks, 0 mismatches** (a new path — the committed `measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` is never overwritten) |
| `measurement/tiletie_pricing_20260812/SMOKE_MANIFEST.json` | the 5-position production-knob smoke and the measured `c` |

**Deliberately NOT built yet:** the analyser (`scripts/tiletie/analyze_tiletie.py`). §4 specifies every
statistic as executable arithmetic on fields the instrument already writes, and building an
analyser before a single position is scored is work against an unknown record population. It is
the **first** build step if the run is funded, and it must land **before** any record is read —
the read-rules in §4.4 are the contract it implements, and they are frozen by this document.
