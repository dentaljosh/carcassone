# Meeple-phase tie arbitration — offline census

**Owner-funded, offline only.** "let's do the cheap meeple offline census." Zero new games
played. Banked E4 archives replayed read-only; the live 1-worker solver suite
(`measurement/tiearb2_stage2_20260817`) was untouched throughout. Compute: one nice-19
process, `rust_threads=8` (matches `PRODUCTION.yaml`'s `desktop` profile exactly — never more
than 8 concurrent OS threads), 39 archives in 994 s wall (16.6 min). No repo file touched, no
`LEVER_INDEX.md` edit, no commit. Banked-replay precedent — no band claim owed.

## The question (docs/LEVER_INDEX.md "meeple-phase tie arbitration" row)

At meeple-phase decisions, how often does the champion's pooled argmax hit **(a)** an exact
Q-tie among top options, and **(b)** a Q+N double-tie (pick falls to the lowest-action-index
fallback)? For double-ties: are the tied options **leaf-distinguishable** (does the v2.9 leaf
value them differently), or are they genuinely equivalent?

## Mechanics (code-verified, cited)

- `rust/carc/carc-core/src/fair/mod.rs::pooled_q_argmax` (lines 261–293): argmax over
  eligible actions (pooled `N >= min_visits`, falling back to ALL pooled actions if none
  qualify) of the strict total-order key `(Q = W/N, N, −action)`. Ties on `Q` break by `N`;
  ties on `(Q, N)` break by **lowest action index** (the fallback this census is about).
- `rust/carc/carc-core/src/tiearb.rs::arbitrate_decision` (line 608): `if g.state.phase !=
  Phase::Tiles { … }` declines — **meeple plies never reach the tie arbiter**, confirmed by
  reading the guard directly. The arbiter only ever sees Tiles-phase ties.
- Python mirror: `fair_agent.pooled_q_argmax`, `fair_agent.DEFAULT_MIN_POOLED_VISITS = 2`,
  `fair_agent.EXACT_MAX_K = 2`.

## Data source: banked archives were thin, so replay was necessary

**Step 1 (inventory) result:** the 47 archives in `measurement/e4_games/` are lean — top-level
keys are `deck_seed`, `actions`, `human_player`, `sims_effective`, `k_dets_effective`, `scores`,
`rules_profile`, etc. **No per-move `root_stats`/pooled (Q,N) table is banked.** So a scan
could not be done directly; the census had to **reconstruct** pooled root stats by replay, per
the brief's step 2.

**Step 2 (replay) chosen:** rather than roll a new replay path, the census reuses the *exact*
production-champion re-search loop already built, tested, and gate-passed for this purpose —
`scripts/analyzer/ev_loss.py::grade_pass` (F12 slice 2a, PASS 2026-08-05; see auto-memory
`reference_evloss_grader`). That function re-runs `make_production_champion("fair", …,
verify=True)` at **every ply** of an archived game (both phases), which is exactly the
champion's own search stack, at the champion's own recorded budget, with `verify=True` meaning
`champion_factory` raises `ProvenanceError` on any leaf-hash/config mismatch. It ran to
completion on all 39 archives below with zero `ProvenanceError`s, which is the load-bearing
guarantee that every re-run search used the frozen production leaf (curve125,
`a36d2e15a3b3d71d`, `CARCASSONNE_USE_FLAT_LEAF=1`, meeple curve
`-10,-5,-1.25,0,2.5,3.75,5,6.25` — `scripts/human_anchor/env_preamble.py::PROD_ENV`, imported
first via `ev_loss` per its own contract).

The census script itself (`/tmp/.../scratchpad/meeple_tie_census.py`, new — the main tree is
read-only under the freeze latch, so it lives in the scratchpad and *imports* `ev_loss`/
`carcassonne_ai` rather than editing them) mirrors `grade_pass`'s loop verbatim (same
`reseat`/`advance`/`_move_idx` discipline, same `resolve_execution("inherit",
profile="desktop", …)`), adding only:
1. the **full** pooled `(N, W)` table per meeple/"pimc" ply (`grade_pass` keeps summary fields
   only, not the full per-action dict — this part is new, straightforward code);
2. an exact replica of `pooled_q_argmax`'s eligibility rule and its strict `(Q, N, −action)`
   tie-break, applied to that table;
3. for any Q-tied ply, a **direct static call** to the production leaf,
   `flat_leaf.flat_virtual_score_v2_float(child_state, actor, cfg=None)` (cfg=None resolves to
   the same env-pinned `DEFAULT_CONFIG` as the search itself), on each tied option's child board
   — this is the leaf-distinguishability probe, independent of what the *search* found.

Alias dedup (`root_stats_list`/pooled-table dedup by successor node identity — the ev_loss
grader's documented trap #2) does not need correcting for here: the pool is read directly off
`agent.last_move()["pooled"]`, i.e. the search's own already-deduped children, which is exactly
the population `pooled_q_argmax` argmaxes over — there is no separate "legal action" list to
reconcile against for this question.

**Config, exactly:** `fixed_v1` rules profile (stamped on the archive, resolved via
`ev_loss.resolve_profile_name` — never assumed), champion `"fair"` (the rust-backed
`RustFairAgent`), `k_dets=8`, `sims=1376` (= 11008 total sims/move, the deploy budget folded in
2026-07-29), `rust_threads=8`, `backend="rust"` (via `resolve_execution("inherit",
profile="desktop")`), `verify=True`. The tie arbiter is not wired into this path at all
(`fair_agent`/`RustFairAgent` never calls `tiearb::arbitrate_decision`) — consistent with the
brief's note that it doesn't touch meeple plies regardless.

## Sample

39 of the 47 banked E4 archives — **all** the archives on the current `fixed_v1` / `k8×1376`
epoch (the other 8 are either pre-`fixed_v1` unstamped builds or the older `k4×688` budget;
excluded to keep the corpus single-epoch, per the "condition all E4 stats on the archive's
rules epoch" rule). 141–142 plies/game.

| | count |
|---|---|
| games | 39 |
| total plies graded (both seats, both phases) | 5,553 |
| meeple-phase plies (any kind) | 2,765 |
| meeple-phase **pimc** plies (real MCTS pool; excludes forced 1-legal-move and post-latch exact-solver plies) | **2,089** |

2,089 pimc meeple plies across 39 games clears the brief's ≥300-plies/≥30-games bar by a wide
margin — this is the full available same-epoch corpus, not a thin screen.

## Results

### Headline rates (population = 2,089 meeple/pimc plies)

| | n | rate | 95% CI (game-resample bootstrap, n=2000) |
|---|---|---|---|
| exact Q-tie among top options | 6 | **0.287%** | [0.095%, 0.519%] |
| Q+N double-tie (falls to fallback) | 6 | **0.287%** | [0.095%, 0.519%] |

**Every Q-tie found in this corpus was also a double-tie** (tie width and double-tie width were
both exactly 2 in all 6 cases — no case of a 3+-way Q-tie, and no case where N broke a Q-tie
without falling all the way to the action-index fallback). So the two rates are numerically
identical here; that is a property of this sample, not a mechanical necessity of the count
(check: single Q-ties with N breaking them are logically possible; the corpus just didn't
contain one).

**Not literally zero.** The tail of the run log (last few archives) happened to show
`q_ties=0 double_ties=0` per-archive, which reads as "zero" if you only see the tail — the
correct aggregate is 6 double-ties, landing in 6 of the 39 games (one each). Stated precisely:
the corpus-wide rate is **very low, not absent**, and the bootstrap CI's lower bound (0.095%)
stays clear of zero.

### By game phase (ply-fraction thirds within each game)

| phase | n plies | q-tie | double-tie |
|---|---|---|---|
| early (ply < 1/3) | 864 | 1 (0.116%) | 1 (0.116%) |
| mid (1/3 ≤ ply < 2/3) | 744 | 1 (0.134%) | 1 (0.134%) |
| late (ply ≥ 2/3) | 481 | 4 (0.832%) | 4 (0.832%) |

The late-game rate (~0.83%) runs roughly 6–7× the early/mid rate, consistent with the intuitive
mechanism: fewer legal meeple options and more symmetric/near-exhausted board state late,
raising the chance the search's own pooled table lands on an exact float tie. n is small (4
late-game double-ties total) — read this as a directional signal, not a precisely-sized
per-phase rate.

### Leaf-distinguishability of the double-ties (the load-bearing question)

All 6 double-ties were evaluated: the production v2.9 leaf
(`flat_virtual_score_v2_float`, same frozen curve125 config as the search) was called directly
on each tied option's child board state, from the deciding player's own POV.

| | n | leaf-distinguishable (any float difference) |
|---|---|---|
| double-ties | 6 | **0 / 6 (0%)** |

**Every single double-tie's leaf values were bit-for-bit identical, not merely close.** Spread
(max − min leaf value in raw virtual-score points) was exactly `0.0` in all 6 cases — not
"under some noise threshold," literally the same float:

| archive | ply | k_remaining | tied actions | leaf value (both) |
|---|---|---|---|---|
| 1786045035_338139 | 99 | 21 | [2502, 2504] | 23.0 |
| 1786116818_134510 | 123 | 9 | [2501, 2504] | 35.9 |
| 1786243458_1382293676 | 137 | 2 | [2502, 2503] | 20.0 |
| 1786591802_1104719504 | 83 | 29 | [2502, 2503] | 19.15 |
| 1786851750_988400 | 137 | 2 | [2502, 2503] | 47.45 |
| 1786853357_1865394167 | 19 | 61 | [2502, 2504] | 0.8 |

These are all narrow-band meeple-phase action-space indices (`meeple_normal_base`/
`meeple_farmer_base`-region encodings — normal/farmer meeple side slots), and in every example
only two options tie, always at small `n_pooled` (4–7 pooled children total) — i.e. these are
genuinely low-branching meeple decisions (e.g., two farmer-adjacency sides on the same feature
that are symmetric under the leaf's own scoring) where the search pool, the leaf, and (as far as
this census can tell) the game state itself agree there is nothing to distinguish. This is
exactly the "genuinely equivalent options" reading, not "signal being discarded."

## Verdict, against the entry-fee bar

LEVER_INDEX's own bar: **"only a nontrivial double-tie rate with leaf-distinguishable options
would fund an arm."**

This census fails **both** halves of that conjunction, independently:

1. **Rate:** 0.287% of meeple/pimc plies double-tie (95% CI [0.095%, 0.519%]) — roughly 1 in
   350 meeple decisions, occurring in 6 of 39 games. This is not "nontrivial" by any reading
   that would survive comparison to the program's own resolvability bars (e.g. the sibling
   `jrules_filter` row's 10% resolvability floor — this is ~35× below that).
2. **Leaf-distinguishability:** 0 of the 6 double-ties the corpus produced show ANY leaf
   disagreement — exact float equality, not near-equality. So even conditional on a double-tie
   happening, the champion's own v2.9 leaf (the thing an arbiter extension would consult)
   currently sees **zero cases** where it would have picked differently from the lowest-index
   fallback.

**No arm is funded.** The priors named in the LEVER_INDEX row going in — "meeple valuation is
the leaf's core competence, so exact meeple Q-ties are plausibly dominated by genuinely-
equivalent options" — are **confirmed**, not merely un-refuted: both the frequency and the
leaf-blindness point the same direction, and n=6 events across 2,089 plies is enough to place a
CI comfortably under any plausible funding threshold without needing more data.

## Caveats / scope (read before citing)

- **Single epoch.** All 39 games are `fixed_v1` rules, deploy budget `k8×1376` (11008
  sims/move), the current champion leaf (curve125). This is the *live* configuration, which is
  the right one to census for a currently-open lever — but the rate is not claimed to
  generalize to other budgets (e.g. a much shallower or deeper search could tie more or less
  often; not measured here).
- **n=6 double-ties is a small event count**, even though the *plies* denominator (2,089) is
  large — the phase-bucket breakdown in particular (4 late-game events) should be read
  directionally, not as a precise per-phase rate. The overall rate's CI is the number to cite.
  If this ever needs tighter bounds, the fix is more of the SAME cheap replay (every additional
  E4 archive that lands on this epoch costs ~24s single-threaded), not a different method.
- **This corpus only.** Only E4 (on-device) archives were censused, since they were the
  available banked source with a real production-config game record; other eval/self-play
  corpora were not scanned for pooled meeple-phase stats (not needed once the E4 replay proved
  cheap and sufficient — see "results discipline," don't spend more than the question needs).
- **Leaf-distinguishability probe is static, not the search's own dynamic evaluation.** It asks
  "does the frozen v2.9 leaf, called directly on the two child boards, disagree" — which is
  precisely what an arbiter extension would have available to consult (the search itself
  already tied), so this is the right instrument for the question asked.

## Provenance

- Census script: `/tmp/claude-1000/-home-doctor-projects-carcassone/d538aba0-bcf8-4b08-a01a-684a1ae3c7eb/scratchpad/meeple_tie_census.py`
  (new, scratchpad-only; imports `ev_loss` from the read-only main tree, does not modify it)
- Aggregation: `/tmp/claude-1000/-home-doctor-projects-carcassone/d538aba0-bcf8-4b08-a01a-684a1ae3c7eb/scratchpad/build_report.py`
- Raw output: `/tmp/claude-1000/-home-doctor-projects-carcassone/d538aba0-bcf8-4b08-a01a-684a1ae3c7eb/scratchpad/census_out/{rows.jsonl,meta.jsonl,run.log,summary.json}`
- Archive list censused: `/tmp/claude-1000/-home-doctor-projects-carcassone/d538aba0-bcf8-4b08-a01a-684a1ae3c7eb/scratchpad/archive_list.fixed.txt` (39 paths under `measurement/e4_games/`)
- Repo rev: branch `tiearb2-stage2`, HEAD `6542cffb` at census time (main tree untouched — no
  commit made by this census)
- Run: single process, `nice -n 19`, `rust_threads=8` (≤8 concurrent OS threads throughout, no
  external multiprocessing), 994 s / 16.6 min wall, 2026-08-24
