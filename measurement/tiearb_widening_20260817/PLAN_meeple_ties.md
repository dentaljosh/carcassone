# TIE-ARBITER WIDENING — RUNG (1), MEEPLE-PLY TIES — PLAN

**Status: PLAN / NOT AUTHORIZED — no compute has run, no code has been touched.** Written
2026-08-17 under the commit-freeze (both boxes on the live JCZ cells; `rust/`, `src/`,
`engine/`, `scripts/classical_search/` sealed). Nothing here is a measurement and nothing
here owes an `experiments/results.csv` row. Funding line: roadmap
[`docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md) row 165,
rung (1).

⚠️ **The free prior already points at DEAD.** Numbers already on disk (§2) put the meeple
exact-tie supply at **≈ 4.8 tied plies/game, ~21% of the tile rung's 22.96**, before any
duplicate removal — below the supply bar derived in §5 from the tile rung's own realized
transfer. The census below is therefore designed to **close the rung cheaply and honestly**,
not to confirm it. It costs minutes; it is worth running exactly because the kill is cheap.

---

## 1. Mechanism, and the distinction that decides the rung

The arbiter fires when the champion's leaf ranks ≥2 candidate chains **exactly** equal (f64,
`eps 0.0`), then breaks the tie by `B` CRN-paired tier1-greedy playouts to terminal per arm. Its
premise: the tied moves are *game-distinct* and the leaf cannot separate them, so terminal
grounding recovers information the leaf discarded. At **meeple** plies that premise is not safe —
the option set contains a class that is equal for a reason arbitration can never exploit:

- **DUPLICATES (game-equivalent).** Two legal meeple actions claiming the **same connected
  feature** — a city with two openings offers a knight slot on each, but either claims the one
  city. `src/carcassonne_ai/meeple_equiv.py:3-7`: *"features only ever MERGE, never split, so an
  equivalence established on the tile can never be invalidated."* These are **guaranteed** leaf
  ties (same meeple, same region), successors differing only in the recorded meeple `side`.
- **ARBITRABLE (distinct-but-tied).** Options claiming *different* features (road vs city, farm
  vs cloister, two regions) that the leaf happens to score equal — the only class where a
  playout can carry information.

**Why the distinction is load-bearing, and worse than "wasted playouts":** the rust arm
builder dedupes on the afterstate repr (`tiearb.rs:275`, key built by `repr_key.rs:88-107`),
and that key writes **`(meeple_type, row, col, side)` per placed meeple** — so two duplicate
slots on one region produce **different** repr keys and survive as **two separate arms**.
Duplicates therefore (a) are never collapsed, (b) consume slots against the `J ≤ 4` cap —
crowding out genuinely distinct options — and (c) return identical world-means, so argmax
falls back to lowest-index. The arbiter would fire, pay full cost, and decide nothing.

Sub-claim to be **verified, not assumed** (census check C5, §4): duplicate arms return
**bit-identical** CRN playout margins. Expected — the seed derivation carries no arm index and
no action (`tiearb.rs:411`, hoisted outside the arm loop; legal-mask memo deliberately `None`,
`tiearb.rs:425`) and `crn_worlds_are_shared_by_every_arm` (`tiearb.rs:673-691`) already asserts
bit-equality for a duplicated arm. If it fails, duplicates are *noise injection*: strictly worse.

**The arbitrable fraction, not the tie rate, is the quantity that funds or kills this rung.**

---

## 2. What is already on disk (free, no compute)

| Source | Number |
|---|---|
| `measurement/jcz_mining_20260809/mining/CANDIDATES.meta.json` (400 games, leaf `a36d2e15a3b3d71d`, profile `fixed_v1`) | plies inspected **TILE 14,190 / MEEPLE 11,681**; `leaf_tie` **TILE 7,817 (55.1%) / MEEPLE 1,928 (16.5%)** ⇒ **4.82 tied meeple plies/game** vs 19.54 tile |
| [`measurement/tiearb2_20260816/corpus/census/CENSUS.md`](../tiearb2_20260816/corpus/census/CENSUS.md) | our own `walled` self-play tile exact-tie rate **64.4%** (2,191/3,400) — i.e. our distribution ties *more* than JCZ's 55.1%, so 16.5% may read ~19–20% here |
| `measurement/classical_search/meeple_dedup_census_20260727.json` | 449 games, 32,282 meeple decisions, **20,281 actionable (≥2 non-pass options)**; **60.75%** of actionable decisions contain ≥1 duplicate group; 18.62% of non-pass actions redundant; **28.58%** of actual placements landed inside a duplicate group; mean non-pass options 2.473 → distinct features 2.013 |
| [`measurement/tiearb2_20260816/READOUT.md`](../tiearb2_20260816/READOUT.md) | `arb_H` **+0.1441 pts/tied ply** (se 0.0479, n=1350), `ora` +0.1801, `rnd` −0.1270 |
| [`measurement/tiearb2_stage2_20260817/READOUT.md`](../tiearb2_stage2_20260817/READOUT.md) | game cell **+3.0700 pts/game**, margin z +4.445, n=800 deck-paired; **22.96 fired tile plies/game** |

⚠️ **The 60.75% figure is not a tie rate.** `meeple_dedup_census.py:86-96` groups options by a
**structural, intra-tile feature-connectivity key** (`feature_groups`,
`src/carcassonne_ai/meeple_equiv.py:102-134`) and **never calls a leaf evaluator**
(`meeple_dedup_census.py:111`, "purely a READ of the tile model"). It counts **duplicates
only** — i.e. exactly the class arbitration *cannot* use. It is also an explicit **lower
bound**: it merges only features connected *on the placed tile*, never features merged across
the board (farms especially), so true duplication is higher than 60.75% (`:20-25`).

Read the two together and the working hypothesis is: **most meeple exact ties are duplicates.**
Order-of-magnitude check — 28.58% of placed decisions land in a duplicate group; a duplicate
group at the top of the ranking is a top-2 tie by construction; 0.2858 × 14,655/20,281 ≈ 21%
of actionable decisions, against a 16.5% observed *total* meeple tie rate. Duplicates alone
can account for the whole of it. The census exists to turn that arithmetic into a measurement.

---

## 3. Where "tile plies only" is enforced (quoted)

**Mining / corpus side (python):**
- `scripts/tiletie/run_census.py:182` — `if int(st.current_player) == champ_seat and st.phase == GamePhase.TILES:` (E4 stratum)
- `scripts/tiletie/run_census.py:264` — `if st.phase == GamePhase.TILES:` (self-play stratum)
- `scripts/tiletie/run_census.py:294` — `if st.phase != GamePhase.TILES:` → hard raise on replay
- `scripts/tiletie/run_census.py:389` — bank stratum: `if rec.get("phase") == "TILES":`
- `scripts/tiletie/chain_census.py:163-166` — `chain_values` is *specialised* to
  `ply_class="TILE"`; "the original's `ply_class` branch is inlined rather than threaded
  through as a parameter".

**The definition of record for the other class already exists**:
`scripts/jcz_mining/mine_disagreements.py:408-432`, `chain_values(..., ply_class)` —
*"On the MEEPLE class every chain is one action."* This is the same function
`chain_census.chain_values` was copied from, and it is the python reference a meeple parity
gate would grade against (§6).

**Runtime side (rust):** one functional gate —
`rust/carc/carc-core/src/tiearb.rs:483` — `if g.state.phase != Phase::Tiles { return Ok(None); }`.
Plus telemetry `fair/mod.rs:600` (`tiearb_tile_plies`, φ's denominator) and the read-only
probe `carc-py/src/lib.rs:629`.

---

## 4. THE FREE CENSUS

**Script (to write, outside the freeze zone):** `scripts/tiletie/meeple_tie_census.py`.
Reuses, does not re-implement: `chain_census.build_leaf()` (leaf `a36d2e15a3b3d71d`),
`chain_census.tie_report()` (identical eps grid `(0.0, 0.05, 0.2, 0.5, 1.0)`), and
`mine_disagreements.chain_values(..., ply_class="MEEPLE")` as the value definition — so the
meeple numbers are comparable **by construction** to the tile census and to the rust arbiter's
meeple-root semantics.

```
meeple_tie_census.py --games <champ_games.jsonl>[,...] --limit N --workers W
                     --out measurement/tiearb_widening_20260817/MEEPLE_CENSUS.json
                     --rows-out .../meeple_rows.jsonl
```

**Corpora (verified present, both `walled`, both champion-policy root-replay jsonl):**
- `measurement/champ_action_logs/champ_games.jsonl` — **449 games**, band 28000000000–449,
  k4×688, leaf `6dfffd57051690f2`/`a36d2e15a3b3d71d` (`CORPUS_MANIFEST.json`). ⚠️ shallower
  than today's champion (k8×1376) — report as its own stratum, never pooled silently.
- `measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl` — **850 games**, band
  28100000000–849, generated for Stage 1b at the deployed budget.
  ⚠️ Its **tile** positions are BURNED. Its **meeple** plies have never been read by any
  instrument, and a census computes no strength/headroom statistic
  ([`CORPUS_PIPELINE.md`](../tiearb2_20260816/CORPUS_PIPELINE.md) preamble). Reading it here
  is a census, not a re-use of a spent read-rule — **but see open question Q1.**

**Per meeple ply with ≥2 legal actions, emit:** `game_id, deck_seed, ply, seat, k_remaining,
phase_bucket, n_legal, n_nonpass`, the chain values, `tie_size_exact`, `by_eps`, and the three
groupings that separate the classes:

1. `repr_arms` — distinct afterstate `string_representation` keys among the tied set (**exactly
   what `tiearb.rs:269-294` would build**);
2. `equiv_groups_intratile` — distinct `feature_groups` ids (the July census's key; a lower
   bound on duplication);
3. `equiv_groups_board` — distinct **board-level** claimed-region ids (union-find region of the
   claimed feature on the *actual* board, so farms merged across tiles collapse correctly).
   **This is the arbitrable-class definition of record.**

**Outputs (`MEEPLE_CENSUS.json`):** `phi_meeple_ply` (tied / champion meeple plies) and
`phi_meeple_move` (tied / all champion moves — the 72-moves/game denominator of
`COST_REMEASURE.json::amortize_22.96_over_72`, directly comparable to the tile rung's 22.96);
`fired_meeple_plies_per_game` at `repr_arms ≥ 2` (what the arbiter would fire on) and
`arbitrable_plies_per_game` at `equiv_groups_board ≥ 2` (what it could use);
**`arbitrable_fraction` = arbitrable / fired — the rung's decision statistic**; tied-set size
distributions for all three groupings; the `J>4` truncation rate (`repr_arms > 4`); the `by_eps`
ladder (feeds rung 4) — all cut by `phase_bucket` and by corpus. Plus **C5**, a
duplicate-invariance check (≤200 plies): where `repr_arms > equiv_groups_board`, run `M=8` CRN
tier1 playouts per arm and assert same-group arms return bit-identical world-means. PASS/FAIL,
not a statistic.

**Cost / ETA.** No search, no PUCT, no MCTS: deterministic replay plus ≈`n_legal` leaf calls
per meeple ply. Anchor: the tile census measured **0.0192 s/ply** for a full tile *chain*
(~50–70 leaf calls); a meeple chain is ~3.5 leaf calls, so replay dominates. 1,299 games
≈ 190k plies ⇒ **≤ 0.5 worker-h total**; **< 5 min wall at W30 local**, **< 7 min at W22
laptop** (C5 adds ~2 min). **Bar: if it exceeds 30 min wall, stop and report — the instrument
is wrong, not the lever.** Precision: ~6,000 tied meeple plies expected ⇒ se on any reported
fraction ≤ 0.7 pp. Both boxes are busy; this queues behind the JCZ cells.

---

## 5. READ-RULE SKELETON — bars stated before any number exists

**Supply bar, derived from the tile rung's own realized transfer.** Tile: 22.96 fired
plies/game × 0.1441 pts/tied ply = 3.309 predicted vs **3.0700 realized** ⇒ transfer
τ = **0.928**. The Phase-B cell resolved that at margin z 4.445 ⇒ se ≈ **0.691 pts/game** at
n=800 deck-paired ⇒ a game cell of the same size resolves (z ≥ 2) only effects
≥ **1.381 pts/game** ⇒ required `f × v ≥ 1.488`. At the tile rung's per-ply value
(v = 0.1441) that is **f ≥ 10.3 arbitrable plies/game**; even at the tile *oracle* value
(v = 0.1801) it is **f ≥ 8.3**. Hence:

| Branch | Condition (on `MEEPLE_CENSUS.json`, pooled over both corpora, reported per corpus) | Action |
|---|---|---|
| **M-DEAD** | `arbitrable_plies_per_game < 4.0` | Rung closed. No pricing, no code touch. LEVER_INDEX row + roadmap row + DECISIONS line. |
| **M-MARGINAL** | `4.0 ≤ arbitrable_plies_per_game < 8.0` | **No pricing funded.** Hand the class to rung (4) `eps>0` — widening eps is the only route by which this supply reaches the bar. Report the `by_eps` supply curve as rung (4)'s input. |
| **M-DUP-BOUND** | `fired_meeple_plies_per_game ≥ 8.0` **and** `arbitrable_fraction < 0.40` | Not a pricing campaign. Propose the cheap hygiene change instead: dedupe arms by **board-region key** rather than afterstate repr, which protects the `J ≤ 4` cap — a free rider on rung (3), gated on that rung's own read-rule. |
| **M-PRICE** | `arbitrable_plies_per_game ≥ 8.0` **and** `arbitrable_fraction ≥ 0.40` | Fund the §6 offline pricing on a **fresh** corpus + **fresh** read-rule. |
| **M-VOID** | C5 duplicate-invariance FAILS, or `phi` differs between the two corpora by > 2× | No branch is adjudicated. Report the discrepancy; re-census on one homogeneous stratum. |

Ties between branches resolve to the **more conservative** (lower-spend) row. The census is
adjudicated **once**, on the pooled read, with the per-corpus split shown but never used to
pick a branch (Stage-1b `C_split` discipline).

---

## 6. IF `M-PRICE` FIRES — the Stage-1b-shaped offline pricing

Same instrument, same two judges, one new ply class: IF judge `clair-puct` (production leaf,
PUCT @ 100 clairvoyant sims to terminal on a known deck); ARB judge `tier1-greedy` (now rust,
G-BITEXACT'd). Statistics unchanged: `arb`, `rnd`, `ora`, `arb − rnd`, `F`, `F_fixed`,
cluster-se by root, boot CI.

**Corpus.** **FRESH games, fresh deck-seed band, fresh read-rule** — the house rule for every
rung of this campaign. Positions mined at **meeple** plies with `repr_arms ≥ 2`, stratified on
`phase_bucket × repr_arms × arbitrable_fraction`, root-disjoint under the same three-layer
`G-DISJOINT` gate (rid / afterstate / board digest).

**Size and power.** Stage 1b realized se 0.0479 at n=1350 ⇒ **se ≈ 1.760/√n**. Targeting the
precision that resolved `arb_H` (se ≈ 0.048): **n = 1,400 mined, floor 1,100 analysed**,
identical to Stage 1b's `G-N` shape. Mechanical size rule if the pilot's realized sd differs:
`n = clip(ceil((sd_pilot/0.048)^2), 1000, 2400)` — committed in the prereg, not chosen after.
Note the meeple per-ply effect may be *smaller* than tile's (fewer points at stake per
decision); the design does **not** get to shrink n to compensate.

**Cost** (measured constants: `c_tier1_rust` = **0.178232** worker-s/playout at W30,
`COST_REMEASURE.json::w_hi`; `c_clair_rust` = **1.60** worker-s/playout,
[`DESIGN.md`](../tiearb2_20260816/DESIGN.md) §11 phase 5; M = 32 CRN worlds):

| item | quantity | worker-h |
|---|---|---|
| fresh self-play, 850 games @ 586 worker-s/game | 138 worker-h | **138** (amortised if the band is shared — §8) |
| `clair-puct` pricing, 1,400 × 32 × Ā playouts @ 1.60 s | Ā = 2.4 ⇒ 107.5k playouts | **47.8** |
| `tier1-greedy` arbitration, same playout count @ 0.178 s | 107.5k | **5.3** |
| census/map/`champ_picks` phases | — | ~1 |
| | | **≈ 192 worker-h (54 excluding generation)** |

**ETA** at W30 local + W22 laptop (52 workers): generation ≈ 2.7 h, pricing ≈ 1.0–1.5 h ⇒
**≈ 4 h wall**, ~1 h if the game band is shared with rungs 2–4. `Ā` (mean arms after repr
dedupe) comes from the census, so this table is re-priced before launch, not after.
Cost is reported, not a kill bar (owner ruling 2026-08-17).

---

## 7. Code touch for meeple firing — scope only, NOT to be made now

Nothing below is implemented until a branch licenses it, and none of it may be built during
the freeze (`rust/`, `src/`, `scripts/classical_search/` are sealed).

- `tiearb.rs:483` — replace the hard `!= Phase::Tiles` early-out with a knob
  (`tiearb_phases: TilesOnly | MeeplesOnly | Both`), **never a deletion**, so the knob-off path
  stays byte-identical. **~1–6 LoC.** `chain_values` itself needs **no change**: at a meeple root
  the turn passes, `tiearb.rs:156` is false, and the chain degenerates to the single leaf
  (`:181-183`) — which is exactly `ply_class="MEEPLE"`.
- `tiearb.rs` contract prose (`:1-78, 127-145, 259-268, 463-468`) asserts "TILE"; test
  `the_trigger_is_tiles_only` (`:740-763`) becomes a knob-conditioned pair. **~50 comment lines
  + ~20 LoC test.**
- `search/mod.rs` config field + `Default`; `carc-py/src/lib.rs:629` probe gate, ctor,
  validation, resolved-dict (`:1458-1614`), telemetry (`:2417-2432`) — `tiearb_tile_plies`
  becomes a misnomer and needs a sibling `tiearb_meeple_plies`, else φ's denominator silently
  changes meaning. **~25–30 LoC.**
- Python plumbing: `rust_agent.py`, `champion_factory.py`, `eval_fair_puct.py`
  (`--cand-tiearb-phases`, the resolved-dict equality assert at `:3736-3742` which aborts the
  run on an unthreaded key, manifest, summary block). **~40–60 LoC.**
- **Total ≈ 60–90 LoC behaviour + ~150 LoC test/telemetry/doc churn across 6 files.**

**Verification obligations (the real cost, per the Phase-A G-BITEXACT precedent):**
1. **A meeple-ply parity gate.** `tests/test_tiearb2_stage2.py:1574-1720` §H grades rust
   `chain_values` against the python census definition and gates on `probe["phase_tiles"]`. The
   meeple reference **already exists** — `mine_disagreements.chain_values(..., "MEEPLE")` — so
   the gate needs no new definition: bank a pre-committed meeple-ply sample, compare **raw f64
   bit patterns**, same shape as `scripts/tiletie/verify_tier1_rust.py` (240 legs / 15,360
   playouts, 15360/15360 bit-identical).
2. `tiearb_disabled_with_moved_knobs_is_bit_identical` (`fair/mod.rs:970`) — the new knob must
   join the "deliberately moved" list at `:974-979`, else the dose-0 guarantee is untested.
3. φ and `G-FIRE`'s `phi < 1.0` void (`eval_fair_puct.py:2549-2612`) are calibrated on tile
   plies (22.96/game) and must be restated before any cell firing on both classes.
4. `tests/test_tiearb{,2,2_corpus,2_pilot,2_digest_exclusions}.py` and the JCZ adjudicator tests
   read `cand_tiearb` shape and fail on a new key until updated.

---

## 8. Interaction with the other three funded rungs

| Rung | Ply class | Shares a corpus with (1)? |
|---|---|---|
| (2) B>16 | TILE | Needs an **M = 64** record bank (banked CRN worlds stop at 16 — not a free sub-read). |
| (3) J>4 | TILE | Needs **uncapped** arm sets banked. |
| (4) eps>0 | TILE (+MEEPLE) | Needs mining at a **wider eps** (e.g. 0.05) so the exact-tie set is a subset. |

**One shared fresh corpus can host all four preregs — if the record bank is generated at the
widest superset**: `M = 64` worlds × **uncapped** arms × mined at `eps = 0.05`, on one fresh
deck-seed band. Then `B ≤ 64`, `J ≤ max`, `eps ≤ 0.05` are all **free sub-reads** of one bank,
exactly as `B ≤ 16` was free in Stage 1b. Blindness holds iff **every** rung's `READ_RULE.md`
is committed **before** any output exists, each rung is adjudicated only on its own conjuncts,
and no rung's branch is chosen using a sibling's realized numbers — state that multiplicity
policy in the shared prereg (four pre-declared families; no pooling; no re-grading).

Rung (1) is a different *ply class*, so it needs its own position pool — but that pool can be
mined from the **same fresh games**, `G-DISJOINT` keyed on `(root_id, ply_class)`, clustered by
root/game. Sharing the band saves the whole 138 worker-h generation, at the price that **one
band influences four decisions**: it then retires from confirmatory use
(`governance/BAND_REGISTRY.csv`), and later cross-band contrasts against it carry the 1.5–2× σ
inflation.

**Order is unchanged: run the §4 census first.** It is minutes, it is independent of the corpus
question, and under the §2 prior it most likely removes rung (1) from the shared prereg
**before** that corpus is designed — making the M=64/uncapped bank cheaper, not dearer.

---

## 9. Open questions for the owner

1. **Q1 — census on burned games.** May it read the Stage-1b games' **meeple** plies? Position:
   yes (no strength statistic computed, no spent read-rule re-graded) — but the corpus is
   nominally burned, so this is a judgement call, not a rule.
2. **Q2 — resolvability bar.** §5 assumes any eventual game cell is n=800 deck-paired
   (se 0.691 pts/game). At n=1,600 the bar falls from 8.0 to ~5.8 arbitrable plies/game and
   `M-MARGINAL` narrows. Which n should the bar assume?
3. **Q3 — profile scope.** `walled` self-play only, or also `fixed_v1`/E4 (where the JCZ prior
   was measured)? Plan assumes `walled`, JCZ as out-of-profile prior only.
4. **Q4 — the `M-DUP-BOUND` rider.** If duplicates dominate, is the board-region arm dedupe
   (protects the `J ≤ 4` cap, ~10 LoC) a rider on rung (3), or does it need its own screen?
5. **Q5 — default after adoption.** If meeple firing is ever built, does `tiearb_phases` stay
   `TilesOnly` in `PRODUCTION.yaml` until a game cell resolves it? (Plan assumes yes: built,
   flag-gated, default OFF, bit-exact-when-off.)
