# E4 autopsy — where do Joshua's points come from? PRE-REGISTRATION

**Status: DESIGN + EXTRACTION COMPLETE 2026-08-12. Written and committed BEFORE any
scoring cell runs. NOTHING HAS BEEN SCORED. No strength verdict is expressed or implied
by this document.**

Cloned pattern: [FARMWAR_PREREG.md](../analyzer_evloss_20260805/FARMWAR_PREREG.md) /
[FARMWAR_READOUT.md](../analyzer_evloss_20260805/FARMWAR_READOUT.md).
Corpus context: [E4_UPDATE_20260812.md](../e4_games/E4_UPDATE_20260812.md).
Extraction census: [CENSUS.md](CENSUS.md) · [CENSUS.json](CENSUS.json) ·
sample + power: [SAMPLE.json](SAMPLE.json).

> **AMENDMENT 1 (2026-08-12, orchestrator review, PRE-SCORING — nothing had been scored
> when this was applied).** Count reconciliation only, no design change. The prose carried
> two draft remnants that disagreed with the committed sample files (`positions.jsonl` and
> the per-epoch splits, which are authoritative): (a) "372 / 322-of-372" in §8 and the
> backend note — the sample is **371 total, 321 `fixed_v1`**; (b) the §6 epoch row read
> "321 / 32 / 18" with MDEs derived from those counts — the true split is
> **321 / 36 / 14**, and the walled / app_aug2 MDEs rescale 1.57 → **1.49** and
> 2.10 → **2.39** (same k = 0.50·√321 constant). All four spots corrected in place; this
> note is the record that they changed and why.

---

## 1. The question

The production champion (`governance/PRODUCTION.yaml`; PIMC k8×1376 = 11008 sims/move,
leaf hash `a36d2e15a3b3d71d`, exact-K2 endgame, rust backend) is **losing to Joshua on his
phone**: over the `fixed_v1` epoch, n = 23 games, W13/L10 to Joshua, paired margin
**+10.043 ± 5.627 pts (z +1.78)**.

Its own EV-loss grader says the opposite about move quality. Over all **26** archived
games — every one of which is now graded (§3) — the human seat's mean pooled ΔQ exceeds
the champion seat's in **26 of 26**, typically by ~4–6×. That is the **grade-vs-outcome
inversion**, and it is not a property of his wins: over the eight 2026-08-12 games, wins
graded at mean ΔQ 0.05721 and losses at 0.04770.

So the champion's evaluator **cannot see where his points come from**, and grading him
with the champion's own leaf is circular. This design asks where the points actually leak,
against an **independent** ruler, **across the whole corpus**, and it is aimed at
**discovery** — locating the leak — not at confirming a hypothesis.

### What this is NOT

- It is **not** a rating instrument. It says nothing about elo, win rate, or "who is
  stronger". §7 of the E4 update already prices that question at 193 seat-swap
  deck-paired games; 26 games is ~1.8σ from a coin.
- It is **not** a promotion instrument. No claim is minted, no governance row flips,
  `governance/PRODUCTION.yaml` is untouched on every branch.
- It carries **no band claim** and writes **no `experiments/results.csv` row** — 0 games
  are played. House precedent: the farm-war run did the same.

### The prior attempt, and why this is not a re-run of it

The farm-war discriminator asked one hypothesis ("does the leaf mis-price contested farm
wars?") on **21 positions from 6 games** and fired its pre-registered branch 4:
**INCONCLUSIVE**. Two things have changed since:

1. **Its motivating anomaly collapsed on replication.** The champion's farm deficit — the
   thing the whole farm-war design existed to explain — was +11.400 ± 3.588 (z +3.18) on
   the first 15 games and **+1.500 ± 3.929 (z +0.38)** on the next 8. The champion's farm
   points went from 14.0 to 21.375 pts/seat, i.e. back to its own corpus norm of 20.5, and
   it was never zeroed again (0 of 8, against 4 of 15). Joshua's own farm points barely
   moved (25.4 → 22.9, z −0.80). See E4_UPDATE_20260812 §5. **A farm-only design would now
   be aimed at a target that is not there.** Meanwhile his margin came out of completely
   different components in the new 8 (during play / unfinished / farms = +6.750 / +3.500 /
   +1.500, against +1.667 / −3.933 / +11.400 in the first 15).
2. **The corpus tripled and is now fully graded**: 26 archives, 26/26 replay-verified
   bit-exact, and — as of this run — **26/26 EV-loss graded** (§3).

Hence: **discovery across every structure, not confirmation on one.**

---

## 2. The primary statistic

For each selected ply, replay the position under **that game's own rules profile**
(resolved from the archive's own stamped fields by `ev_loss.resolve_profile_name`; never
assumed — the 2026-08-05 retraction is exactly about that), take the action Joshua
**played** and the action the champion's search **preferred** (`action_played` /
`action_best`, straight out of the EV-loss artifacts), and score both continuations over
**M = 32 CRN-paired deck completions** — identical world seeds for both arms.

> **Δ = V(played) − V(best), in ENGINE POINTS, Joshua's seat.**
> Positive ⇒ his move earned more than the champion's preferred move.

Mechanically: each position row sets `pick_a = action_best`, `pick_b = action_played`, and
`oracle_score_pilot.position_delta` returns `mean(V_B − V_A)`, so the reported `delta`
**is** Δ as defined. `root_player` is his seat, read from the artifact's `human_player`
(0 in all 26, but read rather than assumed). This sign contract is pinned by a test.

**Units matter.** Δ is in final-score points from a terminal playout. It is **not** the
grader's ΔQ, which is dimensionless (a tanh-squashed leaf backed up through MCTS), and the
two must never be compared on a common scale. The grader's `delta_points_tanh_est` is a
readability rescaling, not a calibrated EV, and is carried here only as a covariate.

---

## 3. Extraction — what has already run

**Grading backfill (RAN 2026-08-12).** 9 of the 26 archives were ungraded
(`1786045035_338139`, `1786074812_935815`, `1786076853_2116173857`, `1786113542_627623`,
`1786116818_134510`, `1786118143_1621601234`, `1786142936_703591`, `1786242001_49628`,
`1786243458_1382293676` — all `fixed_v1`, all games 4–12 of the epoch). They were graded
with the **identical invocation** used for every prior E4 grading (E4_UPDATE §8): the
archive's own stamped budget (k8×1376 = 11008/move), `--seed 12345 --calibration-seed 777`,
`nice -n 19`, rust backend via the `desktop` deploy profile. Driver:
[`backfill_evloss.sh`](backfill_evloss.sh) (9 concurrent single-threaded processes,
resumable, ~5.5 min wall).

**All 9 pass every instrument gate**: `acceptance_gate.pass`, `replay_scores_match`,
`leaf_hash_ok`, `leaf_hash_matches_archive` — 9/9 each. The inversion held in all 9,
making it **26 of 26** archived games.

⚠️ **Selection effect now closed.** The E4 update flagged that its `corr(final margin,
human mean ΔQ) = −0.540 (t −2.22, n = 14)` was "one marginal test on a sample selected by
what happened to be graded". The graded set is now the whole corpus, so that particular
selection effect no longer applies to anything computed downstream of this point.

**Ply extraction (RAN 2026-08-12).** `autopsy_extract.py emit`, one process per rules
epoch (R9 is import-latched, so epochs cannot share a process). Output:
`plies_{fixed_v1,walled,app_aug2}.jsonl` + `.meta.json`.

⚠️ **Defect found and handled during extraction.** `EV_LOSS_1786337185_638286.json`
stamps `archive_path = /home/doctor/e4_run_20260810/deckdir/1786337185_638286.json` — an
absolute path on a **laptop** scratch directory, where that one game was graded. It does
not exist on this box, so any consumer trusting `archive_path` verbatim dies on it.
`autopsy_extract.resolve_archive_path` falls back by basename into `measurement/e4_games/`
and **verifies** the candidate's `deck_seed` and final `scores` against what the artifact
itself recorded before accepting it; a basename collision with a different game raises
rather than silently grading the wrong archive. The fallback fired exactly once and is
logged. **The stale path is still in the committed artifact** — a separate fix, not made
here (this task modifies no existing file).

---

## 4. The population — and why it is NOT the farm-war population

**Every disagreement ply of Joshua's seat, in all 26 games, unselected on ΔQ.**

A ply enters iff: `actor == human_player`; not `forced` (one legal action — nothing to
disagree about); not `exact` (k_remaining ≤ 2, the endgame solver latched — that tail is
already graded in true final-score points by a different instrument, EV-loss D3, and must
never be pooled with a PIMC-root statistic); `action_best`, `action_played` and `delta_q`
all present with `played_eligible`; and **not `agrees`** — using the artifact's own
alias-aware test (`action_played_rep` vs `action_best`), so a rotation of a symmetric tile
that transposes to the champion's own pick is correctly *not* counted as a disagreement.

**Result: 779 disagreement plies over 26 games** (1224 human plies total; 124 forced, 23
exact-tail, 3 ineligible, 571 agreeing at the 17-game stage).

> ⚠️ **This is the deliberate break from the farm-war design.** That run's population was
> `bucket ∈ {inaccuracy, blunder}` — the tail where the champion disagrees *hardest*. Its
> own readout listed the consequence as a live threat: *"Selection on high ΔQ biases Δ
> toward 0 on re-scoring (regression to the mean)."* Here |ΔQ| is a **recorded covariate,
> never a filter**, and Δ is reported by ΔQ bucket as a secondary marginal (§6). The
> residual selection is milder but real and is restated in §8.

---

## 5. Strata — FIXED NOW, before any result

Six **disjoint primary cells**. Assignment is mechanical; the rules below were fixed
before any scoring and are pinned by tests.

### 5.0 DEGENERATE — the farm-war run's known hole, promoted to a stratum

A ply is **degenerate** iff the production leaf, read from Joshua's seat, values the two
successors identically:

```
|L_full(S_played) − L_full(S_best)| <= 1e-9
```

(`L_full` = `flat_leaf.flat_virtual_score_v2_float` under `production_leaf_cfg()`, verified
by `champion_factory.verify_leaf`; it already returns player-minus-opponent, so the
subtraction is like-for-like.)

The farm-war run **silently dropped 15 of 70 candidates (21%)** as degenerate, because its
statistic — "farm share of the leaf difference" — is 0/0 there. Its readout said so
plainly: *"Those are exactly the plies where the champion's disagreement comes from the
SEARCH, not the immediate leaf."*

**That makes them the most interesting cell in a discovery design, not the least.** If the
champion's evaluator cannot see where his points come from, the plies where the evaluator
is *provably indifferent* and the search picks anyway are a first-class suspect. `DEG`
takes precedence over any structural label: "the leaf is indifferent" is a stronger
statement about the instrument than what the move happens to touch.

**Census: 276 of 779 = 35.4% degenerate**, and **247 of those 276 (90%) are tile
placements.**

### 5.1 Structure the move touches

Per arm, the set of feature types the action engages:

- **Meeple plies** — exact, from the newly-placed meeple: `farm` (farmer), `cloister`
  (NORMAL on CENTER), `city` / `road` (NORMAL on a side, resolved by `tile.get_type(side)`),
  or **`pass`** as a first-class label. There is no `contested` for meeple plies: the rules
  forbid claiming an occupied feature, fields included.
- **Tile plies** — from `flat_leaf.decompose` before/after:
  - `city` / `road` iff the placed tile's side joins a component spanning more than the
    placed tile itself (extended or merged an existing region) **or** that component is
    FINISHED in the successor (the placement closed it). A tile cannot abut an open
    city/road edge without supplying the matching edge, so this catches every placement
    that changes an existing region of that type.
  - `cloister` iff the placed tile is a chapel, or it fills a cell in the 8-neighbourhood
    of an existing chapel tile. A structural descriptor, **not** a scoring claim — so it
    is epoch-independent even though `cloister_rule` differs across the three epochs.
  - `farm` iff the placed tile's farm component in the successor carries a farmer meeple
    of either player, i.e. the placement grew a field somebody has claimed. (Every tile
    has fields; without the claimed-field condition the tag would be constant.)
  - `contested` additionally records, per touched type, whether the region already carries
    a meeple — the covariate that separates "he builds" from "he fights".

**Collapse to one disjoint label** (`collapse_structure`): the **symmetric difference** of
the two arms' touch sets decides first — when the arms touch different things, the thing
they differ *on* is what the disagreement is about. Only when the arms touch the same set
(a "where exactly", not a "what kind", disagreement) does the union decide. Within
whichever pool is used, priority is **farm > cloister > city > road**, then `neutral`.

> The priority order is stated **before any result** because it determines the cell sizes.
> Farm first because it is the standing unresolved hypothesis and the only leaf term that
> is severable (`farm_base_off`/`farm_growth_off`, with production `v29_farm_flip_k == 0.0`
> re-checked at extraction time); cloister next because it is rare and would otherwise
> never form a cell.

### 5.2 The primary cells, as measured (five populated of six defined)

| stratum | n | games | mean \|ΔQ\| | tile/meeple |
|---|---:|---:|---:|---|
| **DEG** | 276 | 26 | 0.0926 | 247/29 |
| **FARM** | 252 | 26 | 0.1440 | 156/96 |
| **CITY** | 120 | 26 | 0.1230 | 66/54 |
| **ROAD** | 72 | 25 | 0.0913 | 14/58 |
| **CLOISTER** | 59 | 24 | 0.1329 | 41/18 |
| **NEUTRAL** | 0 | — | — | — |

`NEUTRAL` is **empty**, and that is a bug fix rather than a coincidence.

> ⚠️ **Tagging bug found and fixed during extraction.** The first version of the meeple
> tagger read the placed meeple by diffing `placed_meeples` before/after. That is wrong on
> exactly the plies that matter most: when a meeple placement **completes** the feature it
> claims, the engine scores it and **returns the meeple in the same transition**, so the
> successor's `placed_meeples` is unchanged and the diff reads `pass`. Four scoring meeple
> placements were mislabelled as passes (`g2_161583_p41`,
> `1785984310_1698417952_p121`, `1786076853_2116173857_p73`, `1786511848_634689_p41` —
> each with a 2–4 point leaf swing, so plainly not passes), and they were precisely the
> whole `NEUTRAL` stratum. `_meeple_touch` now **decodes the action index** (exact, and
> immune to score-and-return); the four plies moved to CITY (+1) and ROAD (+3), and
> `NEUTRAL` emptied. Pinned by a test.

### 5.3 Secondary axes — same scored positions, no extra compute

Recorded per ply and reported as marginals: **phase third** (terciles of `k_remaining`:
opening ≥ 48, middle 24–47, endgame ≤ 23), **decision type** (tile / meeple), **rules
epoch** (`fixed_v1` / `walled` / `app_aug2`), **EV-loss bucket** (`within_noise` /
`inaccuracy` / `blunder`, per-game null-calibrated so **not comparable across games** —
carried as a within-game covariate only), **|ΔQ|**, `n_legal`, `alias_group_size`,
`contested`, and `farm_share`.

Plus one axis the census surfaced, promoted to a **pre-registered sub-allocation key** so
it lands powered rather than incidental:

**Meeple economy — `commit_direction`**: on meeple plies, `hold` (the champion commits a
meeple, Joshua keeps his), `spend` (he commits, the champion keeps its), `swap` (both
commit, different targets), `both_pass`.

Census: **hold 120 · spend 64 · swap 71.** He declines a meeple the champion would place
**1.9× more often** than the reverse. The single largest axis cell in the whole corpus is
`road->pass` (48), then `pass->farm` (32) and `farm->pass` (30).

### 5.4 Mechanism tags from the pro-strategy scan (F2/F3/F6/F7/F9)

Five hypotheses from [PRO_STRATEGY_SCAN_2026-08-12.md](../../docs/research/PRO_STRATEGY_SCAN_2026-08-12.md)
are tagged **per ply** so that **one** scoring run adjudicates all of them rather than
spawning five follow-ups. All are computed offline from replay state and the existing
grader artifacts; **none adds search compute**.

| # | tag | definition (at decision time, mover's seat) | census |
|---|---|---|---|
| **F6** | `score_diff_bucket` | running differential: `behind` < −5, `level` ±5, `ahead` > +5 | behind **230** · level **335** · ahead **214** |
| **F3** | `own_reserve` / `opp_reserve` | unplaced meeples, both seats (`state.meeples`) | mean his **2.64** vs champion **2.06** (diff **+0.59**) |
| **F9** | `reinforce_losing_contest_*` | the arm adds to a structure whose majority the mover is **losing or tied** on (own ≤ opp, opp > 0) | champion arm **177** · his arm **140** |
| **F2** | `tie_force_join_*` | the arm **newly connects** into a structure where the **opponent holds sole majority** (opp > own) — the late majority-steal class | champion arm **98** · his arm **77** |
| **F7** | `cross_world_spread` | per-world root value / argmax spread across the k=8 determinizations | ⚠️ **UNAVAILABLE — see below** |

F9 and F2 are recorded **per arm**, because the hypotheses are about *who* reinforces and
*who* steals; the raw `contest_detail` (per touched component: own/opp meeple counts and
whether the placement newly joined) ships with every ply so a different majority rule can
be re-derived without re-running the engine. Both are `False` on meeple plies by rule: a
meeple may only claim a **free** feature, so a meeple placement cannot reinforce or steal
an existing majority.

> ### ⚠️ F7 is NOT COMPUTABLE from the existing artifacts — stated limitation, not an omission
>
> `ev_loss.grade_pass` reads `last_move()["pooled"]`, which is **already summed across the
> k = 8 determinizations** before it reaches the artifact (`agg_n`/`agg_w` are built from
> that pooled list). No per-world root value and no per-world argmax survives, so
> cross-world spread cannot be recovered offline at any effort. Obtaining it needs a
> **re-search** with per-world stats retained, which this design explicitly does not buy.
>
> The field is emitted as `cross_world_spread: null` with
> `cross_world_spread_status: "unavailable_pooled_only"` so a consumer cannot mistake
> absence for zero. The nearest **retained** quantity is `pooled_top2_q_gap` — the top-2 Q
> gap *within* the pooled distribution — which is carried as a covariate and is **not** a
> substitute: it measures how decisive the pooled root is, not how much the worlds
> disagreed. **Future work:** a grader pass that persists per-determinization root stats
> would make F7 a first-class tag at one re-search's cost.

All five are wired as **secondary read-out axes** (§8) and F6 additionally joins the
sub-allocation key, so the scored sample preserves its marginals by construction.

---

## 6. Sampling and power — fixed before scoring

**Per-stratum n** from the farm-war run's **measured** spread, not an assumption: its
cluster-robust `se = 0.970` pts at `n = 21` with `M = 32` ⇒ **sd ≈ 0.970·√21 = 4.445
pts/position**. For a `|z| ≥ 2` read on an effect of `E` points/ply:

```
n >= (2 · 4.445 / E)^2      # E = 1.0 -> 80    E = 1.25 -> 51    E = 1.5 -> 36
```

The design targets the **conservative end** of the brief's +1.0…+1.5 pts/ply range, so
`--target-effect 1.0`, i.e. **n = 80 per stratum**, capped by each stratum's population.

| stratum | population | n scored | binding constraint | 2σ MDE (pts) |
|---|---:|---:|---|---:|
| DEG | 276 | 80 | power | 0.99 |
| FARM | 252 | 80 | power | 0.99 |
| CITY | 120 | 80 | power | 0.99 |
| ROAD | 72 | 72 | population | 1.05 |
| CLOISTER | 59 | 59 | population | 1.16 |
| NEUTRAL | 0 | 0 | — (stratum is empty) | — |
| **total** | **779** | **371** | | |

**Within-stratum allocation** is proportional (largest-remainder) on the four-part key
`(phase_third, decision_type, commit_direction, score_diff_bucket)`, then a seeded draw
inside each sub-cell (`--seed 20260812`, deterministic and pinned by a test). This
preserves every secondary marginal by construction:

| axis level | n scored | 2σ MDE (pts) |
|---|---:|---:|
| opening / middle / endgame | 154 / 128 / 89 | 0.72 / 0.79 / 0.94 |
| tile / meeple | 221 / 150 | 0.60 / 0.73 |
| commit `hold` / `spend` / `swap` | 88 / 35 / 27 | 0.95 / 1.50 / 1.71 ⚠ |
| **F6** behind / level / ahead | 105 / 166 / 100 | 0.87 / 0.69 / 0.89 |
| **F9** champion reinforces (True / False) | 82 / 289 | 0.98 / 0.52 |
| **F9** he reinforces (True / False) | 62 / 309 | 1.13 / 0.51 |
| **F2** champion steals (True / False) | 47 / 324 | 1.30 / 0.49 |
| **F2** he steals (True / False) | 38 / 333 | 1.44 / 0.49 |
| bucket noise / inacc / blunder | 222 / 83 / 66 | 0.60 / 0.98 / 1.09 |
| epoch fixed_v1 / walled / app_aug2 | 321 / 36 / 14 | 0.50 / 1.49 / 2.39 |

**F3 (`own_reserve` / `opp_reserve`) is continuous**, so it is read as a regression of Δ on
the reserve counts over all 371 positions rather than as a cell, and is not sized here.

---

## 7. Judges

- **PRIMARY: in-family** — clairvoyant PUCT continuation over the champion's own leaf
  (`oracle_score_pilot` default, `--oracle-sims 100`, rust backend).
  ⚠️ **It shares the leaf under test.** It is therefore biased **toward the champion's
  picks**, which fixes how each outcome may be read: a verdict **AGAINST the champion is
  conservative and strong**; a **null through it is weak** — it cannot distinguish "no
  effect" from "effect hidden by the shared leaf". This is the same caveat that made the
  farm-war null uninformative, and it is not eliminated here.
- **SECONDARY: out-of-family sign check** — Tier-1 greedy (`--oracle-policy tier1-greedy`,
  python backend by construction: there is no Rust `RuleBasedPlayer`, and porting one
  would destroy the point of an out-of-family judge). ⚠️ **1.83× noisier, no curve125 —
  SIGN ONLY, never compare its magnitude to the primary's.** Benchmark for what
  corroboration looks like: the 2026-07-28 precedent agreed on 80% of signs at p 0.0012;
  the farm-war run got 61.9% at p 0.38, which is not corroboration.
  **Availability confirmed 2026-08-12** by a 1-position probe on `fixed_v1`: 1/1 scored,
  0 failed, `crn_verified`, 143.2 s. Unlike the rust clairvoyant it is rules-agnostic
  (python `RuleBasedPlayer` on the same engine the position is replayed in), so the
  out-of-family sign check IS available for this corpus.

### Backend — the preflight found a blocker, and it changes the price

**Rust backend licensing.** `--backend rust` is licensed by an **identity** gate
(`measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json`: 20 positions, 940 field checks,
every non-timing record field compared as raw f64 bit patterns, 0 mismatches), and that
gate is **cell-and-knob scoped — it licenses the continuation at those knobs on that
revision.** The 2026-08-09 budget-headroom run re-verified it at HEAD before launching (8
positions, 376 field checks, 0 mismatches) **by hand**, and because the gate script's
`--out` defaults to the committed record, the re-verification overwrote it and the
20-position record had to be restored afterwards.

Here the re-verification is **code, in the launcher preflight**: `run_autopsy.py` re-runs
the gate at HEAD, writes to the **run-local** `PREFLIGHT_GATE_AT_HEAD.json` so the
committed record is never touched, and **aborts the launch** on a non-PASS verdict or any
mismatch instead of leaving it a prose claim.

**It re-verified PASS at HEAD**: 8 positions, 376 field checks, 0 mismatches, speedup
**9.43×** ([`PREFLIGHT_GATE_AT_HEAD.json`](PREFLIGHT_GATE_AT_HEAD.json)) — reproducing the
2026-08-09 figures (8 / 376 / 0, 9.48×) on the current revision.

> ### ⚠️ AND THEN THE RUST RULER TURNED OUT NOT TO RUN THIS CORPUS AT ALL
>
> The first smoke attempt failed **6 of 6 positions**, immediately and identically:
>
> ```
> ValueError: the clairvoyant Rust ruler cannot mirror
> ['start_row/start_col', 'fixed_start_tile', 'cloister_scan_fix', 'draw_rule']:
> RustCarryClairvoyantAgent seeds MirrorState.from_deck() with no geometry/rules config
> (unlike the fair RustFairAgent, which forwards them), so it would run the engine-default
> rules against a game that does not. Build this ruler with backend='python' until the
> forwarding lands.
> ```
>
> The E4 epochs carry non-default geometry and rules — `retail` start tile, `centered18`
> grid, the fixed cloister scan, the `redraw` draw rule — and the **rust clairvoyant**
> agent does not forward them (the rust **fair** agent does). It **fails closed**, which is
> the correct behaviour: the alternative was silently scoring these positions under
> engine-default rules.
>
> **This does not contradict the identity gate.** That gate is a real python-vs-rust
> identity result and it re-verified PASS — but it was taken on the **CL-070 bank**, whose
> roots are engine-default-rules positions. Its scope simply never covered a rules profile
> the rust ruler declines to mirror. *A gate that passes is not a gate that applies.*
>
> **Consequence: the whole run is PYTHON-backed, and it costs ~9.4× more.** That is the
> single biggest input to §10 and it was only discoverable by pre-flighting.
>
> `run_autopsy.rust_clair_available()` now encodes the test (a profile whose
> `game_kwargs()` is non-empty cannot be mirrored) and the driver **drops every epoch to
> python if any epoch is blocked** — never a per-epoch backend split, because that would
> make the epochs different instruments and read rule 4's per-epoch reads incomparable.
> `walled` alone (`game_kwargs() == {}`) could run rust; it is 36 of 371 positions and is
> deliberately not special-cased.
>
> This also puts the run on the **same engine as the farm-war discriminator**, which never
> passed `--backend` and therefore ran python throughout — so the two runs' Δs are
> commensurable.

**⚠️ Operational trap, hit and recorded.** The pilot writes a `records/<rid>.json` for a
FAILED position too, and `--resume` skips any rid that has a record — **including failed
ones**. The six rust-failure records had to be deleted before the python smoke would
re-score them. Any resume after a systematic failure must clear the failed records first,
or the run will "resume" straight past the very positions that failed.

---

## 8. Read rules — house statistical norms, binding

1. **Two-sided z throughout.** A negative Δ is informative (it vindicates the leaf).
2. **|z| < 2 in a stratum means NO CONVICTION. It never means "refuted."** A
   non-significant negative mean is not evidence the champion's picks are better; it is
   absence of resolution. (The farm-war readout is explicit that its branch 4 was not a
   refutation.)
3. **Cluster-robust SE on `game_label`** is the primary interval — 371 positions over 26
   games is ~14 per cluster and the design effect is not negligible. The naive SE is
   reported alongside, never instead.
4. **No pooling across rules epochs when the signs disagree.** Inherited verbatim from the
   farm-war prereg, and it bound there: its epochs disagreed in sign in both strata
   (`_pooling_licensed: false`) and the positive pooled number was carried entirely by two
   legacy epochs, the larger `fixed_v1` epoch leaning the other way. Report the per-epoch
   split first. `fixed_v1` is the epoch he plays now and is 321 of 371 positions.
5. **Selection on ΔQ biases Δ toward 0.** Even unselected on bucket, the population is
   conditioned on the champion having disagreed at all, so regression to the mean pushes
   Δ toward 0 on re-scoring. This makes a positive result **harder**, so a null is softer
   than it looks and must not be read as a refutation.
6. **Cross-epoch contrasts get ~1.5–2× σ humility** (CLAUDE.md / CL-068). Within-epoch
   contrasts are the robust class. The three epochs are not deck bands, but they are
   different rule sets on different games and the same caution applies a fortiori.
7. **A stratum below n = 15 is underpowered by construction** — reported with its CI, never
   promoted, in either direction. `commit swap` (n = 27, MDE 1.71), `commit spend` (n = 35,
   MDE 1.50) and `F2 he-steals` (n = 38, MDE 1.44) are pre-declared as weak; `app_aug2`
   (n = 18, one game) can never carry a verdict on its own.
10. **The five mechanism tags are SECONDARY and multiplicity applies.** F2/F3/F6/F9 are
   read on the same 371 positions as the primary strata. Nine extra two-sided contrasts at
   α = 0.05 expect ~0.45 false positives; a single |z| ≈ 2 on one mechanism tag with the
   others null is a **hypothesis for a targeted follow-up**, not a finding. Only |z| ≥ 3 on
   a mechanism tag, or a consistent sign across related tags (e.g. F9 and F2 both favouring
   the same seat), is quotable from this run alone.
11. **F9/F2 counts are not effects.** The census asymmetries (champion reinforces a losing
   majority 177× vs his 140×; steals 98× vs 77×) are counts of *move class*, not of value.
   They say the two players choose differently, which was already known — the disagreement
   plies are selected for that. Only Δ scored within those tags speaks to whether the class
   is mispriced.
8. **Never quote the grader's ΔQ ratio.** E4_UPDATE §6 retired it: the numerator (human ΔQ)
   is flat while the denominator (champion ΔQ) is the instrument's own noise floor and
   fell z −2.96 across graded-game order. Report raw ΔQ.
9. **Do not read Δ as a strength claim.** Δ prices ONE ply against ONE alternative under a
   shallow continuation. Even a large, significant Δ in a stratum is a statement about
   **where the evaluator misprices**, not about who is stronger.

### Outcome branches — what each one means

Evaluated **per stratum**, all strata reported regardless of which fire. There is no
precedence ordering and no single "verdict": this is a discovery design and the
deliverable is the **map**, not a winner.

- **Δ > 0, |z| ≥ 2 in a stratum** ⇒ **a localized defect in the champion's evaluation.**
  Through the in-family judge this is the conservative direction, so it is a strong read.
  The stratum names *where* his points come from. Consequences: those plies are re-labelled
  in the EV-loss readouts; the corresponding leaf terms become a re-sweep candidate; a
  claim id is minted. Does **not** license "the champion is weak".
- **Δ > 0, |z| ≥ 2 in `DEG` specifically** ⇒ the defect is in the **search**, not the leaf
  — by construction the leaf is indifferent between the two arms there. That is a
  materially different (and cheaper to act on) finding than a leaf-term defect, and it is
  a cell no prior instrument has ever looked at.
- **Δ ≤ 0, |z| ≥ 2 in a stratum** ⇒ the champion's picks really are better there; the
  grader's ΔQ readouts stand for that stratum, and his margin in those games came from
  somewhere else. Combined with the corpus-level margin this **sharpens** the puzzle
  rather than resolving it.
- **Δ > 0 with |z| ≥ 2 in essentially every stratum** ⇒ **general same-family
  self-preference in the judge**, larger than the oracle pilot's +0.74. That is a statement
  about the *instrument* and it gates every future in-family claim, including this run's.
  The Tier-1 sign check is what separates this branch from a real localized defect.
- **Everything |z| < 2** ⇒ **no conviction anywhere at n = 371.** Report the map with CIs;
  promote nothing. The default next step is **more E4 games**, not more compute — the same
  conclusion the farm-war run reached, and the one the 8 new games then vindicated.

---

## 9. Pre-stated threats

1. **Same-family judge.** Handled by the conservative-direction argument (§7) and the
   Tier-1 sign check. **Not eliminated.** A null through the primary is weak evidence.
2. **Weak continuation.** The judge plays out at `--oracle-sims 100`, far shallower than
   real play. It biases toward whichever move looks better under shallow play; direction
   unknown. Untouched by the pilot, untouched by the farm-war run, untouched here.
3. **One human, 26 games.** Every ply comes from one player's games, so this measures the
   evaluator **on positions his play produces**, not on Carcassonne in general.
4. **Selection on disagreement.** See read rule 5.
5. **Mixed rules epochs.** Each ply is replayed under its own profile (R9 is import-latched
   ⇒ one process per epoch), but strata pool across epochs. Read rule 4 binds.
6. **Non-stationary anchor.** Joshua self-reports changing strategy, and the component
   ledger shows his margin moving between components across the epoch (§1). Plies from
   game 1 and game 26 are not draws from one distribution. Report the per-game and
   per-epoch splits; do not fit a trend across a changed axis.
7. **The structural tagger is new code.** `collapse_structure`, the tile touch rules and
   the cloister neighbourhood are this run's own definitions, unit-tested but not
   previously used by any other instrument. A finding that hinges entirely on one tag
   boundary should be treated as a hypothesis, not a result.
8. **Bucket labels are per-game.** Thresholds are re-calibrated from each game's own
   second-seed null, so bucket counts are **not** comparable across games (EV-loss D2).
   Used within-game only.

---

## 10. Cost and ETA

**Priced from a smoke at PRODUCTION knobs** — `M = 32`, `--oracle-sims 100`,
`--oracle-policy clair-puct`, `--backend rust`, same salt, same out-root — with **only the
position count differing**, per the house pre-flight rule. Phase-stratified (2 per phase
third) because the continuation runs to terminal, so an opening position costs several
times an endgame one: the 2026-08-09 anchor spans **6.6 s … 163.2 s** per position and a
blind average would misprice the run. The smoke's records land in the real run's output
directory under the same salt, so `--resume` folds them in rather than discarding them.

Sanity anchor: **2026-08-09 budget-headroom, 150 positions × M=32 at W16 rust = 990.1 s
wall**, mean 97.13 s/position, median 111.81, min 6.60, max 163.23, ~92% pool efficiency.

<!-- PRICE_TABLE_START -->
### What the smoke measured

6 positions, 2 per phase third, evenly spaced across games (not `pool[:N]`, which would
have priced the run off one deck), W6, `--wall-cap 780`:

| position | k_remaining | phase | result |
|---|---:|---|---|
| `1786337185_638286_p116` | 12 | endgame | **268.2 s** completed |
| `1785982194_705585_p105` | 18 | endgame | **479.6 s** completed |
| `1786325073_523563_p80` | 30 | middle | **≥ 780 s** (wall-capped) |
| `1785982194_705585_p56` | 42 | middle | **≥ 780 s** (wall-capped) |
| `1786329790_523563_p40` | 50 | opening | **≥ 780 s** (wall-capped) |
| `1785982194_705585_p25` | 58 | opening | **≥ 780 s** (wall-capped) |

⚠️ **4 of 6 are censored lower bounds**, so the price below is a *model*, not a direct
mean. The model is the obvious one — the continuation runs to terminal, so cost is linear
in plies remaining ≈ `2·k_remaining` — fitted on the two completions:
**22.35 and 26.65 s per unit of `k_remaining`**. All four censored positions are
**consistent** with it (the model puts them at 670–1546 s, all ≥ 780).

**Independent cross-check.** The 2026-08-09 rust anchor is 97.13 s/position mean; the
preflight measured the python/rust ratio at **9.43×** on this revision, giving
**916 s/position**. The model's mean over this sample is **901–1074 s/position**. Two
unrelated routes agree, so the price is trustworthy even though the smoke is censored.

Sample: **371 positions, Σ k_remaining = 14 950, mean k = 40.3.**

### ETA

`tier1-greedy` costs **0.534×** the primary judge (143.2 s vs 268.2 s on the *same*
position — measured, not assumed).

| scope | box | primary judge | + Tier-1 sign check | **both** |
|---|---|---|---|---|
| all 3 epochs (371 pos) | **local W14** | 6.6 – 7.9 h | 3.5 – 4.2 h | **10.2 – 12.1 h** |
| all 3 epochs (371 pos) | **laptop W22** | 4.2 – 5.0 h | 2.3 – 2.7 h | **6.5 – 7.7 h** |
| `fixed_v1` only (321 pos) | local W14 | 5.7 – 6.7 h | 3.0 – 3.6 h | 8.7 – 10.3 h |
| `fixed_v1` only (321 pos) | laptop W22 | 3.6 – 4.3 h | 1.9 – 2.3 h | 5.5 – 6.6 h |

**This is an overnight run, not a coffee break** — the python fallback (§7) costs ~9.4×
what a rust-backed run would have. Levers, if the owner wants it cheaper, in the order
that costs the least information:

1. **`fixed_v1` only** — −15% wall, and read rule 4 forbids pooling the epochs anyway;
   the two legacy epochs are 50 positions at MDE 1.57 / 2.10 and cannot carry a verdict.
2. **Primary judge only, Tier-1 later** — −35% wall. The sign check is only *needed* if the
   primary fires; running it first and the sign check on demand loses nothing but a
   round trip. ⚠️ It is needed to separate a localized defect from general same-family
   self-preference, so it must not be dropped *permanently*.
3. **`M = 16` instead of 32** — halves the wall (5.1 – 6.1 h for both at W14) but multiplies
   every 2σ MDE by **1.41**, which pushes DEG/FARM/CITY from 0.99 to 1.40 pts and takes the
   design off the "+1.0 pts/ply" target it was sized for. **Not recommended**; prefer
   cutting scope over cutting M.
4. Splitting local + laptop is the obvious parallel play — the epochs are already separate
   processes, so `fixed_v1` on one box and `walled`+`app_aug2` on the other is a clean split
   (though it leaves the long pole untouched; splitting `fixed_v1`'s own positions across
   boxes via two `--positions-jsonl` halves under one `--out-root` is the real win).

**Wall cap.** The scoring run should use the driver default `--wall-cap 7200`; the smoke's
780 s was chosen only to bound a pricing run. The pilot records a wall-capped position as a
failed row (never as a zero Δ) and keeps the pool alive.
<!-- PRICE_TABLE_END -->

Both judges are run; the Tier-1 leg is python-backend and is priced separately.

**Worker split.** The driver apportions workers across the three epoch legs in proportion
to their position counts (`run_farmwar.split_workers`, reused unmodified). With a min-1
floor and very unequal legs that is `{fixed_v1: 12, walled: 1, app_aug2: 1}` at W14 and
`{fixed_v1: 19, walled: 2, app_aug2: 1}` at W22 — `fixed_v1` is the long pole either way.
**If the budget is tight, run `fixed_v1` alone first**: it is 321 of the 371 positions and
it is the epoch he actually plays, and read rule 4 forbids pooling the epochs anyway, so
the two legacy epochs (50 positions, MDE 1.57 / 2.10) buy little and can be deferred or
dropped without touching the primary read.

**⚠️ The owner picks the box. Nothing above the smoke has been launched.**

---

## 11. Governance

Measurement only. `governance/PRODUCTION.yaml` untouched. No champion change, no promotion
on any branch, **no band claim** and **no `experiments/results.csv` row** (0 games played).
A claim id is minted only on a branch that fires with |z| ≥ 2. Every number ships in a
manifest with the resolved strata rules, the per-ply records, the judge configs, and the
at-HEAD identity-gate verdict.

---

## 12. Files and reproduce

| file | what |
|---|---|
| [`DESIGN.md`](DESIGN.md) | this document |
| [`backfill_evloss.sh`](backfill_evloss.sh) | the 9-game grading backfill (RAN) |
| [`CENSUS.json`](CENSUS.json) / [`CENSUS.md`](CENSUS.md) | the disagreement census (RAN) |
| [`SAMPLE.json`](SAMPLE.json) | per-stratum sizing + power (RAN) |
| `plies_{fixed_v1,walled,app_aug2}.jsonl` | every tagged disagreement ply (RAN) |
| `positions.jsonl` + `positions_<epoch>.jsonl` | the 371 sampled positions (RAN) |
| `PREFLIGHT_GATE_AT_HEAD.json` | rust identity gate re-verified at HEAD |
| [`SMOKE.json`](SMOKE.json) | the priced smoke |
| `scripts/analyzer/autopsy_extract.py` | extraction / census / sampling |
| `scripts/analyzer/run_autopsy.py` | the scoring-run driver (preflight + legs) |
| `tests/test_e4_autopsy.py` | contract tests |

```bash
# 1. grading backfill (already done; resumable, skips graded archives)
bash measurement/e4_autopsy_20260812/backfill_evloss.sh

# 2. extraction — ONE PROCESS PER EPOCH (R9 is import-latched)
for P in fixed_v1 walled app_aug2; do
  .venv/bin/python scripts/analyzer/autopsy_extract.py emit --profile $P \
      --out measurement/e4_autopsy_20260812/plies_$P.jsonl &
done; wait

# 3. census + power-based sample
.venv/bin/python scripts/analyzer/autopsy_extract.py census \
    --inputs measurement/e4_autopsy_20260812/plies_*.jsonl \
    --out measurement/e4_autopsy_20260812/CENSUS.json \
    --md  measurement/e4_autopsy_20260812/CENSUS.md
.venv/bin/python scripts/analyzer/autopsy_extract.py sample \
    --inputs measurement/e4_autopsy_20260812/plies_*.jsonl \
    --out       measurement/e4_autopsy_20260812/SAMPLE.json \
    --positions measurement/e4_autopsy_20260812/positions.jsonl \
    --target-effect 1.0

# 4. price it (preflight gate at HEAD + phase-stratified smoke at production knobs)
.venv/bin/python scripts/analyzer/run_autopsy.py --smoke 2 --workers 6

# 5. THE SCORING RUN — NOT LAUNCHED. The owner picks the box and the W.
#    local:  --workers 14      laptop: --workers 22
#    The driver auto-drops to python (§7); --backend python just makes it explicit and
#    skips the (inapplicable) rust identity gate.
setsid nohup .venv/bin/python -u scripts/analyzer/run_autopsy.py \
    --workers 14 --backend python --skip-gate \
    > measurement/e4_autopsy_20260812/logs/run.log 2>&1 < /dev/null &

# resume after a crash — BUT clear failed records first, or resume skips them (§7)
#   find /mnt/c/carc-shared/analyzer_e4_autopsy_20260812 -name '*.json' -path '*/records/*' \
#     | xargs grep -l '"ok": false' | xargs rm -f
```
