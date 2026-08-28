# PREREG — E4 PLY PRICING (judge-free)

> **Status: BLIND-COMMITTED, PRE-PRICING.** This file and the frozen target set
> (`targets.jsonl`, `k_histogram.json`, `MODE_CUT.json`) are committed on branch
> `e4-ply-pricing-freeze` **before any price is computed**. House two-commit
> pattern: this commit is the FREEZE; the next commit stamps its sha as
> `BLIND_COMMIT`. Deviations after the freeze go in `DEVIATIONS.md`, never here.
>
> Owner authorization, verbatim (2026-08-27): *"price the plies. laptop w22. local w14"*.

## 0. Why this instrument exists

The owner beats the champion by ~13 pts/game over the 50-game E4 corpus. The
Stage A mechanical census
([`../e4_exploit_grading_20260825/STAGE_A_CENSUS.md`](../e4_exploit_grading_20260825/STAGE_A_CENSUS.md))
attributes the bulk of the behavioural asymmetry to **deliberate merge-invasions**
(90 owner vs 7 champion over 50 games, mean gross transfer ~11 pts/event) and to
**late farm capture** — and Stage A explicitly refused to read its 29.2 pts/game
gross as an EV.

Stage B then priced those plies with the F12 EV-loss grader and read ~zero — but
**that null is structural**: the grader's reference is the champion's OWN leaf, so
it is definitionally blind to the evaluation omission H2/H4 name
([`STAGE_B_VERDICT.md` §5](../e4_exploit_grading_20260825/STAGE_B_VERDICT.md)).

The F4 lesson makes the fix non-negotiable: judged headroom is **family-relative**
(an out-of-family judge read the same clair-family +1.49 pts/ply ceiling as −0.64,
z −3.8), so *judge-free evidence classes outrank judged ones*. This instrument
therefore prices moves with **ground truth only** — the exact endgame solver and
realized archive outcomes. **No search-family judge appears anywhere in it.**

## 1. What is frozen here

### 1.1 The target ply set (built by `build_targets.py`, frozen in `targets.jsonl`)

Selection reads ONLY outcome-blind Stage A census fields. `test_ply_pricing.py::
test_no_outcome_field_is_read_by_the_selector` asserts, at code level, that
`build_targets.py` contains no reference to `winner` / `diff` / `final_scores` /
`recorded_scores` / `margin` — outcome-blind **by construction**, not by discipline.

| stratum | n plies | rule |
|---|---:|---|
| `invasion` | **86** | every census `contest` row with `invader == 0` **and** `actor == 0` — the owner's DELIBERATE merge-invasion onsets. All are TILES-phase plies (the merging move is a tile placement). The census's **90 EVENTS** live on 86 distinct plies: 4 owner moves each open two onsets at once, and the PLY is the unit of pricing, so those events are grouped (`notes.n_events`, `notes.events`; gross fields summed). |
| `farm_capture` | **27** | every census `farm` row `late_switches` entry whose ply is an OWNER move (`actor == 0`), excluding plies already counted as `invasion` (no double count). |
| `defense` | **86** | for each `invasion` ply *p*, the champion's most recent TILES-phase ply *q < p* with `p - q <= DEFENSE_WINDOW_PLIES`, de-duplicated. This is the last state at which the champion could have priced the coming invasion. |
| `control` | **91** | owner TILES-phase plies with `n_legal > 1` that are in no flagged stratum, sampled per game against a fixed seed and **decile-matched** to that game's invasion plies. |
| **total** | **290** | across 47 `fixed_v1` (277) + 2 `walled` (10) + 1 `app_aug2` (3) games. |

Pre-registered constants (asserted equal to the code by
`test_prereg_constants_match_the_code`):

```
DEFENSE_WINDOW_PLIES = 8
CONTROL_SEED = 20260827
REALIZED_WINDOW_PLIES = 20
COUNTERFACTUAL_SEED = 0
CLAIR_WORLD_SEED = 20260827
```

### 1.2 The rules-epoch discipline (binding)

The rules profile is resolved **FROM EACH ARCHIVE**, never from a flag, via
`analyzer.ev_loss.resolve_profile_name` — an explicit `rules_profile` stamp wins
outright; its ABSENCE is positive evidence of a pre-`fixed_v1` build and resolves
among `walled` / `app_aug2`, never to `fixed_v1`. R9 is import-latched, so the
driver runs **one process per profile group** and stamps
`CARCASSONNE_FIX_R9` observed-vs-expected on every artifact. Budget epochs are
carried per row from the archive (`played_sims_effective`, `played_k_dets_effective`,
`result.budget_note`).

**Never identify a build from `(start_rule, grid_rule)`.**

### 1.3 K, and the K histogram (frozen in `k_histogram.json`)

`K = len(state.deck) + (1 if state.next_tile is not None else 0)` — the exact
solver's convention (`gen_multiphase_positions.k_remaining`), NOT `ev_loss`'s
`len(state.deck)`.

The histogram over all 290 target plies is frozen before any price exists
(`k_histogram.json`; K ranges 1..71). Its governing fact, stated up front because
it bounds everything this instrument can say:

> **The owner's exploit lives in the midgame, far above exact-solvable range.**
> Only **10 of 290 plies (3.5 %) sit at K ≤ 4** and **27 (9.3 %) at K ≤ 9** —
> 3 and 8 of them respectively are `invasion` plies. Invasion onsets sit at mean
> ply-fraction 0.47 (Stage A). And solve cost then bites a second time: it grows
> ~10–30× per K (§1.4), so the affordable exact cut lands at **K ≤ 5 = 13 plies,
> 4.5 %**, not at K ≤ 9. A judge-free EXACT price is therefore reachable for about
> a twentieth of the channel; the rest gets descriptive arithmetic that is **not**
> a price. That is a property of the exploit, not a shortfall of the instrument,
> and it is reported rather than papered over.

| cut | n plies | % | invasion | farm_capture | defense | control |
|---|---:|---:|---:|---:|---:|---:|
| K ≤ 4 | 10 | 3.5 % | 3 | 2 | 3 | 2 |
| K ≤ 6 | 16 | 5.5 % | 5 | 4 | 5 | 2 |
| K ≤ 9 | 27 | 9.3 % | 8 | 7 | 5 | 7 |
| K ≤ 12 | 39 | 13.4 % | 9 | 9 | 9 | 12 |
| K ≤ 16 | 51 | 17.6 % | 13 | 13 | 13 | 12 |

### 1.4 The pricing modes, by K (frozen in `MODE_CUT.json`)

```
k_marginalized_max = 4
k_clairvoyant_max = 5
m_worlds = 8
```

| K | mode | what it is | caveat | rows |
|---|---|---|---|---:|
| `K <= 4` | `exact_marginalized` | `carc_core::endgame` / `endgame_solver.solve(mode="marginalized")` — expectiminimax over the real remaining bag. The value **is** the true final-score differential (P0 − P1). | **NONE.** Ground truth. No clairvoyance gap, no evaluation function, no search heuristic. | **10** |
| `K == 5` | `exact_clairvoyant_M` | the clairvoyant exact solver (alpha-beta, exact) run over `m_worlds = 8` INDEPENDENTLY RESAMPLED deck orders and averaged per root action; the archive's TRUE future is solved separately as world −1 and reported alongside, **never folded into the mean**. | ⚠️ **CLAIRVOYANCE GAP.** Each world's optimal line sees that world's future, so this is an OPTIMISTIC bound for BOTH seats, not a calibrated EV. **Never pooled with `exact_marginalized`.** | **3** |
| `K > 5` | `realized` | pure archive arithmetic — realized score swing over the next 20 plies and to the end of the game, plus Stage A's feature-attributed gross (`invader_gain`, `incumbent_denied`). | ⚠️ **DESCRIPTIVE, WIDE ERROR BARS.** In-play scores only (farms score at the end); no counterfactual. Never quote as a price. | 277 |

**The cut is measured, not guessed** (`COST_PROBE_laptop.json`, run as an exclusive
tenant on the idle laptop, sized by the TAIL not the mean — two real E4 `fixed_v1`
positions per K):

| K | clairvoyant+ab, per world (s) | marginalized (s) |
|---:|---|---|
| 2 | 0.34 / 0.15 | 0.92 / 0.15 |
| 3 | 1.25 / 0.58 | 29.9 / 10.1 |
| 4 | 29.3 / 8.2 | **290**, and a second position still running past the probe's 600 s cap |
| 5 | *projects ~120–680 per world* | *projects ≳ 6000 — outside the cap* |

Marginalized has **no alpha-beta** (chance nodes have no minimax cutoff) and is the
cost wall: it grows ~10–30× per K **with a heavy tail**, so K=4 sits inside the
1800 s cap for the typical position and near it for the worst, while K=5 is firmly
outside. Clairvoyant-per-world gets alpha-beta and is 10–35× cheaper at the same K,
which buys **exactly one more K** — K=5 projects to ~120–680 s per world, and
because the cap is applied PER WORLD, the 9 world-solves are ~18–102 min for the
ply with ~3× headroom on the worst world.

⚠️ **Expected attrition, pre-registered:** a K=4 marginalized row in that heavy
tail can exceed 1800 s and is then recorded `TIME_SKIPPED` — a skip, never a price.
The 13-row exact coverage below is a **CEILING**; each row's `solve.status` is the
truth.

⚠️ **The honest consequence, stated before any price exists: 13 of 290 plies
(4.5 %) get an exact price. The other 277 get descriptive arithmetic that is not
a price.**

### 1.5 The champion counterfactual

The counterfactual move at every target ply is **the production champion's own
move at that exact state** — `governance/PRODUCTION.yaml` `champion.fair_deploy`:
`k_dets = 8` × `sims_per_det = 1376` (11008), leaf `a36d2e15a3b3d71d`, fair PIMC,
exact-K ≤ 2, `backend: rust`, built through
`make_production_champion("fair", ..., **resolve_execution("inherit", profile="desktop").factory_kwargs())`
— the same audited construction `analyzer/ev_loss.grade_archive` uses.

**Determinism policy (pre-registered):** `seed = COUNTERFACTUAL_SEED = 0`, and the
per-ply determinization seeds are pinned by setting `agent._move_idx = <archive
ply index>` before every decision (the `mirror_protocol` contract — the caller owns
the move timeline). `rust_threads` is execution-only (G4: bit-identical merge at
threads {1,4,8}) and is set per box.

⚠️ **The champion NAMES a move; it never SCORES one.** It is the policy under
test, not a judge. Every price in this instrument comes from the exact solver or
from realized archive outcomes.

### 1.6 The pricing arithmetic

`child_values` maps every legal root action to the exact final-score differential
(P0 − P1) that follows it under optimal play. P0 maximizes, P1 minimizes, so:

* `price_best` = `max(cv)` for a P0 mover, `min(cv)` for a P1 mover;
* `delta_pts_mover` = `(price_played − price_counterfactual)` for P0, negated for P1
  — **positive iff the played move is better FOR THE MOVER than the champion's
  counterfactual**;
* `regret_pts_mover` = `(price_best − price_played)` for P0, negated for P1.

The owner is seat 0 in all 50 archives (`human_player == 0`). Every figure is in
TRUE final-score points. Hand-computed fixtures pin all of it
(`test_ply_pricing.py` §1).

### 1.7 ⭐ The RUST-MIRROR verdict — which solver runs, and why

The program record says **the RUST CLAIRVOYANT JUDGE cannot mirror E4 rules
profiles**. That finding is about the *judge*. The separate question this
instrument depends on — *does the rust exact SOLVER reproduce the Python oracle
under each archive's own profile?* — was measured, not assumed, by
`rust_python_diff.py`: real E4 endgame states, Python `Game` and Rust
`MirrorState` driven in LOCKSTEP with a `string_repr` desync guard, comparing
`value_bits` / `to_move` / the whole `optimal_actions` SET / **every** root
action's `child_values` bit-for-bit / and `nodes` (the search SHAPE, not just the
answer). Zero mismatches over zero checks never PASSes.

**VERDICT: RUST MIRRORS EVERY E4 PROFILE — 0 mismatches, every profile.**

| profile | games in corpus | positions | checks | python-skipped | **mismatches** | rust speedup |
|---|---:|---:|---:|---:|---:|---:|
| `fixed_v1` | 47 | 5 | 15 | 0 | **0** | 18.6–24.8× |
| `walled` | 2 | 4 | 9 | 3 | **0** | 18.9–23.4× |
| `app_aug2` | 1 | 2 | 6 | 0 | **0** | 20.5–23.7× |
| `fixed_v1` (K=4 marginalized leg) | 47 | see `DIFF_fixed_v1_k4marg.json` | | | | |

**Higher-K coverage is inherited, not assumed.** The standing
`scripts/rustport/reconcile_exact_solver.py` campaign already gates this same Rust
solver at depths this E4 leg cannot afford to re-gate (the PYTHON oracle is the
expensive side): `measurement/rustport_exact_solver/G7_exact_solver_run2.json` —
**457 checks, 0 mismatches**, including `k3:marginalized` ×74 and
`k4:clairvoyant+ab` ×48 — plus `G7_exact_solver_main.json` (378 checks, 0
mismatches) and `G7_exact_solver_synth_fixedv1.json` (60 checks, 0 mismatches,
`fixed_v1`). So DEPTH is gated by the standing campaign and the RULES PROFILE is
gated by the E4 legs above; this run adds the one load-bearing cell neither
covers, `fixed_v1` marginalized at K=4 — the exact cell `k_marginalized_max = 4`
rests on.

Artifacts: `DIFF_walled.json`, `DIFF_fixed_v1.json`, `DIFF_fixed_v1_k4marg.json`,
`DIFF_app_aug2.json`. Each row compares `value_bits`, `to_move`, `optimal_actions`,
every `child_values` entry and `nodes` in all of `clairvoyant+ab`, `clairvoyant`
(no prune) and `marginalized`. The 3 `walled` skips are the PYTHON oracle blowing
its wall cap at K=3 (a skip, never a mismatch — a Rust solve that outran its
budget while Python finished would have been reported as a divergence).

So the exact solver is **Rust everywhere**, both boxes, and the laptop's ~12 GB is
not a constraint (the python-era "solves are RAM-heavy, keep them local" rule was
a PYTHON-era rule: `carc_core::endgame` is the ~20× faster, ~19× smaller sibling,
and the measured speedup on these very positions is 19–25×). Python-only fallback
is NOT needed; if any profile had failed its gate, that profile's solves would
have moved to the Python oracle on the local box and the fallback would be named
in `DEVIATIONS.md`.

### 1.8 Caps and isolation

Every solve runs in its own forked child under `RLIMIT_AS` (`--job-mem-cap-gb`)
and `RLIMIT_CPU` (`--job-time-cap-secs`, **1800 s CPU per solve**, `SIGXCPU` left at
its DEFAULT disposition so the kernel can kill a child parked inside a long Rust
solve), plus a parent wall backstop. **The cap is PER WORLD, not per ply**: an
`exact_clairvoyant_M` row runs `m_worlds + 1` separately-isolated solves, so one
pathological deck order is skipped alone (`m_worlds_ok` records how many landed)
instead of voiding the ply's whole average. Reused verbatim in shape from
`scripts/rustport/reconcile_exact_solver.py`, which built it after two whole-scope
OOM kills. A job over either cap is recorded as `TIME_SKIPPED` / `OOM_SKIPPED`
(a SKIP, never a price, never a correctness finding) so it is visible in the
artifact and cannot be silently dropped.

## 2. Pre-registered readouts

1. **Per-ply row**: game, ply, K, rules profile + budget epoch, played action,
   counterfactual action, `price_played`, `price_counterfactual`,
   `delta_pts_mover`, `regret_pts_mover`, pricing mode, solve cost, realized block.
2. **The invasion channel, priced**: mean and total `delta_pts_mover` over the
   `invasion` stratum, per game, against the `control` stratum as baseline —
   reported SEPARATELY per pricing mode, never pooled across modes.
3. **The census gross vs the priced net**: Stage A's ~11 pts/event gross transfer
   next to the exactly-priced net on the sub-population where an exact price exists.
4. **The defense side**: the same statistics on the `defense` stratum, i.e. what
   the champion's pre-invasion move was worth against its own best alternative.
5. **Champion agreement rate** per stratum — how often the production champion
   would have played the owner's move. This is judge-free (a policy agreement
   count, not a score) and is defined at EVERY K, including the un-priceable bulk.
6. **Coverage, stated up front**: how many of the 290 plies got an exact price,
   how many got a clairvoyant-bounded one, and how many are descriptive only.
7. **Forced plies are EXCLUDED from every readout and counted separately.** A ply
   with one legal action carries no decision, so it prices to exactly 0 for both
   sides; averaging it in would drag every mean toward zero and read as "the
   exploit is worth nothing". (Stage B lost 108 of 405 rows to forcing; the
   `control` stratum is pre-filtered on `n_legal > 1` at selection time, and
   `aggregate.py` filters the rest at readout time.) **Measured on the frozen set:
   0 of 290 target plies are forced** — every invasion, defense and farm-capture
   ply is a real decision, so this filter is a guard, not an attrition channel.

## 3. Pre-registered falsifiers / what would kill a reading

* **A `replay_desync` on any position** voids that row (the Rust mirror and the
  Python board must agree at the target ply before anything is solved).
* **Any rust-vs-python mismatch in the differential gate** (`DIFF_*.json`) on a
  profile ⇒ that profile's solves fall back to the PYTHON oracle on the local box,
  and the fallback is stated in `DEVIATIONS.md`.
* **Exact coverage below ~20 rows** ⇒ the exact channel is reported as an
  existence proof with named games, not as an estimate.
* `exact_clairvoyant_M` deltas are **never** pooled with `exact_marginalized`
  deltas, and neither is ever pooled with `realized` arithmetic.
* A single ply's delta larger than the feature's own final points is a bug signal,
  not a discovery — Stage A reconciles 50/50 exactly, so any disagreement with its
  feature-level facts is this instrument's bug.

## 4. What this instrument CANNOT answer

* It cannot price the **midgame bulk** of the invasion channel. Exact solving is
  out of reach above K≈9 and every search-based substitute is a judge. The
  descriptive `realized` block is not a substitute and is labeled everywhere.
* It cannot attribute the owner's margin causally. The corpus is 50 games of one
  human; `corr(owner invasions, owner margin) = −0.17` (Stage A) — invasion COUNT
  is not the discriminator.
* It is a `fixed_v1` result: 47 of 50 games. The `walled` (n=2) and `app_aug2`
  (n=1) rows are anecdote, not a profile contrast.

### 4.1 The instrument that WOULD price the midgame bulk — named, costed, NOT funded

The gap above has one judge-free filling, and this run deliberately banks its
expensive prerequisite rather than doing it: a **CRN-paired counterfactual
continuation**. From each target state, play the owner's move and then the
champion's counterfactual move, and from each continue champion-vs-champion to
terminal on the SAME resampled decks and seeds; the price is the difference in
**final score**. That is a *game outcome*, not a judged score — the evidence class
the F4 lesson ranks above every judged number — and it works at any K.

Costed at production knobs from this run's own measurement (1.4 s/decision,
~70 plies of continuation ⇒ ~98 s/playout): 290 plies × 2 arms × 8 CRN worlds
≈ 126 h serial, ≈ **3.5 h wall at the funded W's (local 14 + laptop 22)**. It is
NOT launched here — it is a different instrument and a separate compute decision.

**This run makes it cheap to start:** the champion counterfactual action at every
one of the 290 plies is exactly that instrument's expensive input, and it is
computed and banked here for all of them, priced or not.

## 5. Reproduce

R9 is import-latched, so every stage runs **one process per rules-profile group**.
`PYTHONPATH` points at the worktree; the venv is editable-installed against the
main tree, so verify `carcassonne_ai.__file__` resolves inside the worktree first.

```bash
export PYTHONPATH=$WT/src:$WT/engine:$WT/scripts
D=$WT/measurement/e4_ply_pricing_20260827

# 1. target set + K histogram (frozen BEFORE the mode cut is pre-registered)
for p in fixed_v1 walled app_aug2; do
  .venv/bin/python $D/build_targets.py --profile $p --out $D/targets_$p.jsonl
done
cat $D/targets_{fixed_v1,walled,app_aug2}.jsonl > $D/targets.jsonl
python3 $D/freeze_histogram.py

# 2. ⭐ the rust-mirror gate, per profile (correctness; DIFF_*.json)
.venv/bin/python $D/emit_endgame_positions.py --profile $p --out $D/diffpos_$p.jsonl
.venv/bin/python $D/rust_python_diff.py --profile $p --positions $D/diffpos_$p.jsonl \
    --n 5 --max-k-marg 3 --max-k-noab 3 --max-k-clair 6 --out $D/DIFF_$p.json

# 3. the cost model (EXCLUSIVE TENANT — a timing bench owns its box)
.venv/bin/python $D/cost_probe.py --profile fixed_v1 --positions $D/diffpos_fixed_v1.jsonl \
    --per-k 2 --k-max 8 --marg-k-max 4 --per-solve-cap-s 600 --out $D/COST_PROBE.json
.venv/bin/python $D/cf_probe.py --profile fixed_v1 --targets $D/targets.jsonl \
    --games 1 --plies-per-game 3 --out $D/CF_PROBE.json

# 4. tests, then the FREEZE commit, then the smoke, then the run
.venv/bin/python -m pytest $D/test_ply_pricing.py -q
.venv/bin/python $D/price_plies.py --profile fixed_v1 --targets $D/targets.jsonl \
    --mode-cut $D/MODE_CUT.json --limit-plies 10 --out $D/SMOKE_rows.jsonl
python3 $D/plan_shards.py --cf-secs ... --marg-secs ... --clair-secs ...
BOX=local W=14 SHARE=/mnt/c/carc-shared $D/run_pricing.sh $D/shards_local.txt
ssh laptop-wsl 'bash -s' < $D/launch_laptop.sh     # share is /mnt/carc-shared THERE
python3 $D/aggregate.py --rows $D/out_*/rows_*.jsonl --out $D/PRICED.json
```
