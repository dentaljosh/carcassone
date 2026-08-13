# Window-truncation census — DESIGN + PRE-REGISTERED READ

**Status: BUILT + GROUND-TRUTH VALIDATED + PILOTED 2026-08-13. Full census NOT YET
RUN — this document is written BEFORE it, and the thresholds in §6 are
pre-registered.**

**⭐ The instrument reproduces the production crash (§5.1). The pilots' zeros are
therefore a measurement, not a blind spot.**

| | |
|---|---|
| Instrument | [`scripts/measurement_infra/window_truncation_census.py`](../../scripts/measurement_infra/window_truncation_census.py) |
| Tests | [`tests/test_window_truncation_census.py`](../../tests/test_window_truncation_census.py) — 12 tests, green |
| Pilot A (`walled`) | [`pilot/summary.json`](pilot/summary.json) — 40 roots, **396,872 nodes, 0 truncated** |
| Pilot B (`fixed_v1`) | [`pilot_fixed_v1/summary.json`](pilot_fixed_v1/summary.json) — 40 roots, **357,320 nodes, 0 truncated** |
| **Ground truth** | [`crash_cell/summary.json`](crash_cell/summary.json) — the 2026-08-13 production crash root, **382/10,003 nodes truncated, 6 empty-mask, crash reproduced** |
| Root reconstruction | [`scripts/measurement_infra/reconstruct_crash_root.py`](../../scripts/measurement_infra/reconstruct_crash_root.py) → [`crash_root.jsonl`](crash_root.jsonl) |
| Provoked by | [`measurement/joshuabot_20260812/CONFIRM_EXCLUSIONS.md`](../joshuabot_20260812/CONFIRM_EXCLUSIONS.md) |
| Prior art | [`docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md) rows *"widen the action window"* (J4) and *"full-board / no-crop representation rework"* (declined) |

---

## 1. The defect, restated from the source

`carc-core/src/action_space.rs::encode` returns `None` for a **TILE** placement whose
coordinate falls outside the 25×25 window centred on the placed-tile centroid.
Meeple actions and `Pass` are window-independent and **always** encode — only the
`Action::Tile` arm of `encode` has a `None` branch.

`carc-core/src/game.rs::legal_mask` counts those as `n_overflow` and **drops them
silently**. Python's `game_wrapper._compute_mask` raises `WindowOverflowError` at
exactly this condition; the Rust backend — **the champion's backend of record since
2026-08-01** — does not. So `Game::legal_actions()` can return a strict subset of
the engine's own legal move list with no error anywhere.

### 1.1 LEGAL vs ILLEGAL — verified, not assumed

This is the distinction the whole exercise turns on, so it is settled twice.

**In code.** `legal_mask` iterates `state.possible_actions()`
(`engine/mod.rs:1119`). In `Phase::Tiles` that list is built from
`possible_playing_positions(base)` — the engine's own legality enumeration. Every
action it emits is legal by construction. There is **no path through `encode` by
which an illegal action is filtered out**: `encode` never inspects legality, only
coordinates. Therefore `n_overflow` is a pure window-truncation counter.

**At runtime.** On every truncated node the census re-derives the same node under a
provably overflow-free window and asserts all four of:

| assertion | meaning |
|---|---|
| `wide_n_overflow == 0` | the reference window really does drop nothing |
| `wide_n_total == narrow_n_total` | the engine enumerated the **same** legal moves; only the encoding differs |
| `n_extra_in_narrow == 0` | the narrow legal set is a subset of the wide one |
| `n_dropped_by_setdiff == n_overflow` | the set difference is exactly the counter |

The positive control (§4) exercises all four and records the engine coordinates of
the dropped placements.

A fifth, cheaper gate runs on **every** node, truncated or not:
`len(legal_actions()) == n_total - n_overflow`. A failure would mean two distinct
legal actions collided on one index (`encode_collision`). 0 in both pilots.

---

## 2. Why the played-level ~0.5% figure does NOT bound the search-internal rate

The JCZ `WALL_LEGALITY` figure (≈0.5% of games) and the 2026-07 window audit's
**0/299k dropped legal actions** are both rates over the **played** distribution —
positions that actually occurred in a game. The 2026-07-19 release audit's
adversarial replay (2,159 states, 0 production drops) is the same population again.

The champion is PIMC. At every decision it draws `k_dets = 8` determinized decks and
runs a full 1376-sim PUCT search in each. Those searches descend into hypothetical
continuations that no real game reached, and a hypothetical continuation is free to
sprawl further from the centroid than real play does. Nothing about a rate over
played positions constrains a rate over search-internal ones — in either direction.

The 2026-08-13 crash is the existence proof that the two populations differ. At the
failing ply the **played** position was healthy: 5 legal actions, **0** outside the
window, **0** placed tiles outside, board extent rows 6–23 × cols 10–18 inside a
window covering rows 5–29 × cols 3–27. The champion's own search still reached a
node whose **entire** legal move list was out-of-window
(`SearchError::NoLegalActionsAtInterior`). The wall is inside the search.

**⇒ The search-internal population has never been measured. That is the gap this
census closes.**

---

## 3. What is measured, and how (the instrument)

**Read-only.** No engine edit, no `src/` edit, no rebuilt extension, no env flag.
Everything comes off the public pyo3 surface that already exists:
`MirrorState.mask_counts()` → `(n_total, n_overflow)`,
`MirrorState.search_single(cfg, trace_path, trace_expansions)`,
`FairAgentRs.determinizations(move_idx)`.

**The seam is the champion's own.** `fair::pimc_move` searches each determinized
world with `search::search_single(&world, cfg)` — no seed, fully deterministic
(GAP1 closed: `measurement/rustport_p6/GAP1_SEED_INVARIANCE.json`). The census
reproduces exactly that: seat a mirror at the root, `set_unseen_deck(world_i)`,
`search_single(...)`. This is the identical seam
`scripts/measurement_infra/rust_world_search.py` already uses for the CL-070 probe
family.

**Node reconstruction.** With the trace sink on, each `sim` record carries the
descent's action sequence and the node digests along it. Every expanded node is the
terminus of exactly one simulation's descent, so replaying that action sequence from
the seated root reconstructs it losslessly. Verified per node:
`sha256(string_repr)[:16] == trace path[-1]` (`digest_gate_fail`, 0 in both pilots).
Node re-seating costs 0.115 ms for a 90-ply prefix, which is why full — not
sampled — coverage is affordable.

**Statistics produced** (per root and aggregated):

- `node_truncation_rate` — expanded nodes with ≥1 dropped **legal** action
- `dropped_hist` — distribution of dropped-action counts
- `by_depth` — `[n_nodes, n_truncated, n_dropped]` by search depth in plies from the
  root (the mechanism predicts the rate rises with depth as boards sprawl)
- `by_node_phase` (tiles/meeples), `by_k_bucket` (early/mid/late)
- `empty_mask_rate` — nodes with **zero** encoded actions, i.e. the crash case
- `visit_weighted_truncation_rate` — the same, weighted by how often the search
  actually descended through the node
- `root_truncation_rate` — the **played-level** rate re-measured on this root set,
  so the two populations are read off the same instrument

**Scope gaps, stated up front.** Roots the champion decides with the exact-K≤2
marginalized solver (`solver_region`) run no PUCT search and are skipped-and-counted;
the solver reads `legal_actions()` too and is exposed to the same truncation, but
that is a separate measurement and is deliberately not folded in. Roots with a
single encoded legal action (`forced`) short-circuit before the k searches and are
also skipped-and-counted (4 of 40 in Pilot B).

---

## 4. The decision-relevant leg is EXACT, not a proxy

"How often would the root's chosen action change if the dropped actions had been
available?" is directly computable, because **the search is isomorphic under a change
of window size**:

1. `string_representation` — the transposition key — is a pure function of
   `GameState` (`repr_key.rs:154`). It never mentions the window.
2. Action **ordering** is window-invariant. Tile index is
   `(wr·W + wc)·4 + rot` with `wr = row − origin_row`, so ordering by
   `(row, col, rot)` survives any `(origin, W)` containing both cells; tile-`Pass`
   sorts after all tile actions at every `W`; the 10 meeple slots keep their order.
   `valid_actions` is index-sorted, so the search enumerates the same actions in the
   same order.
3. Priors are `softmax(ΔLeaf(a)/tau_p)` over `legal` **in that order**
   (`search/mod.rs::evaluate`), and the leaf reads the board, not the window. Same
   order + same values ⇒ bit-identical priors, and `np_sum_f64` sums in the same
   order.
4. `pooled_q_argmax`'s tie-break is `−action`; the remap preserves order.

**A window of 71 is provably overflow-free**: the engine board is 35×35
(`engine/mod.rs:43`) and the centroid lies inside it, so no legal coordinate is more
than 34 rows/cols away, and `W=71` covers centroid ± 35.

⇒ Running the same k worlds at `W=71` and comparing the pooled-Q pick (after
remapping) is a **fully controlled A/B whose only possible source of difference is
truncation**. Measured, not argued: at the production budget a `W=71` world search
costs 0.150 s vs 0.147 s at `W=25` and returns **bit-identical** `pooled_stats`,
`node_count` and `leaf_evals` on an untruncated root.

**The isomorphism is also the census's built-in null control.** On any root where
the census finds zero dropped actions anywhere, the narrow and wide pooled stats
*must* be bit-identical; `iso_ok` records it and a violation is an instrument bug,
not a finding. **76/76 green across the two pilots.**

**Positive control.** A census that can only ever report zero is unfalsifiable, so
the window under test is a flag (`--narrow-window`). Squeezed to `W=15` on a real
banked root the instrument reports 8 truncated nodes, 2 dropped actions each, all at
depth 2 in the tiles phase, each verified `dropped_all_legal: true` with
`wide_n_total == narrow_n_total == 56`, `wide_n_overflow == 0`,
`n_extra_in_narrow == 0`, and the dropped placements identified as the two rotations
at engine coordinate (5, 21). The same fixture at `W=25` reports zero. This is
`test_positive_control_census_sees_truncation`.

---

## 5. Pilot results (n=40 roots per leg — UNDERPOWERED, and reported as such)

Both legs run the full production budget: `k_dets=8 × sims_per_det=1376 = 11,008`
per decision, champion `puct_priors_v29_bmild_cap8`, leaf `a36d2e15a3b3d71d`.

| | **Pilot A — `walled`** | **Pilot B — `fixed_v1`** |
|---|---|---|
| roots | 40 (random from the 898-root CL-070 bank, band 28e9) | 40 (random from 1,548 champion decision plies in 23 E4 phone archives) |
| rules epoch | engine start (6,15), walled | centered18 + retail + fixed cloister + redraw + R9 (`r9_env_ok: true`) |
| roots censused | 40 | 36 (+4 forced) |
| **expanded nodes censused** | **396,872** | **357,320** |
| **nodes with ≥1 dropped legal action** | **0** | **0** |
| **nodes with an empty mask** | **0** | **0** |
| root (played-level) truncation | 0/40 | 0/40 |
| world-search errors / crashes | 0 | 0 |
| **root pick changed under an overflow-free window** | **0/40** | **0/36** |
| `iso_ok` null control | 40/40 green | 36/36 green |
| digest gate / encode collisions | 0 / 0 | 0 / 0 |
| cost | 10.85 s/root (7.96 search + 2.74 replay) | 8.76 s/root |

**Read this as a pilot.** An underpowered rate is still a rate, and here it is:

- Rule of three, Pilot A: 0/396,872 ⇒ **≤ 7.6 × 10⁻⁶ per node (95%)**.
- Rule of three, Pilot B: 0/357,320 ⇒ **≤ 8.4 × 10⁻⁶ per node (95%)**.
- A champion seat expands at most `72 decisions × 11,008 = 792,576` nodes per game,
  so those bound the per-game count at **≤ 6.0** and **≤ 6.7** truncation events —
  loose enough that this pilot does **not** settle the question.
- The legs are **not pooled**. `walled` and `fixed_v1` are different wall
  geometries (start row 6 vs 18), and the crash was observed under `fixed_v1`; a
  rate from one is not a rate for the other.

### 5.1 GROUND TRUTH — the production crash reproduces inside the instrument ✅

A census that has only ever reported zero on real roots is worth nothing until it is
shown to fire on a root that is *known* to break. So it was run on the one root that
demonstrably did: the 2026-08-13 J7ZERO confirm crash, deck `126000000135`,
`joshua_seat 0` / champion on seat 1, `champion_seed 9400540`, `fixed_v1`.

**Recovering the root.** Nothing on disk carried the action prefix, so
`reconstruct_crash_root.py` replays the cell exactly as `h2h._play_cell_inner` does
(same profile, same variant `current+j7w0`, same `champion_seed()` derivation, a
verbatim copy of `play_harness.play_game`'s loop) and records the applied actions.
It raised at **79.5 s** — matching the original cell's 78 s.

> **The "ply 59" in the crash diagnostic is NOT the global ply.** It is the
> **champion's own decision counter**. The raise is at **global ply 119**, which is
> the champion's **`move_idx = 59`**. This matters materially: the determinization
> stream is seeded from `det_seed_base(seed, move_idx)`, so feeding ply 119 as
> `move_idx` would have drawn eight *different* worlds and the crash would not have
> reproduced. The census now reads a `move_idx` field off the root
> (`--move-idx` overrides), and its absence falls back to ply — valid for a RATE,
> invalid for reproducing a NAMED decision. **The pilots in §5 used the ply
> fallback; that is sound for a rate and is recorded in their manifests.**

**Result — everything fires, and the numbers corroborate the original diagnostic
independently:**

| | |
|---|---|
| root: phase / `k_remaining` / window | meeples / 12 / `(5, 3, 25)` — **identical to `window_diag_126000000135s0.json`** |
| root legal / root out-of-window | **5 / 0** — identical to the diagnostic; the played position is healthy |
| expanded nodes censused (8 worlds) | 10,003 |
| **nodes with ≥1 dropped legal action** | **382 (3.82%)**, 578 actions dropped, up to 4 per node |
| visit-weighted truncation rate | **6.23%** |
| **nodes with an EMPTY mask (the crash case)** | **6** — and the trace's own `va:[]` count is 6. Independent agreement. |
| **world search that RAISED** | **world 3, `NoLegalActionsAtInterior`** — the production crash, caught and recorded rather than aborting |
| digest gate / encode collisions | 0 / 0 |

**The empty-mask nodes, exactly.** All 6 are in world 3, at **depth 3**, TILES phase,
`k_remaining = 10`, with `n_total = 4` and `n_overflow = 4` — i.e. the engine offered
exactly four legal moves, the **four rotations of a single placement at engine
coordinate (4, 15)**, and the window `(5, 3, 25)` covers rows 5–29. The placement is
**one row above the window**. Every one passes the four legality assertions
(`dropped_all_legal: true`, `wide_n_total == narrow_n_total == 4`,
`wide_n_overflow == 0`, `n_extra_in_narrow == 0`).

**Rate rises with depth, as the mechanism predicts.** Truncation is confined to
TILES-phase nodes (382/4,386; meeples 0/5,617), and among those the rate climbs with
depth: **d3 1.3% → d5 23.0% → d7 13.3% → d9 100% (105/105)**.

**The pick changes, and not by a tie-break.** Under the overflow-free window the
champion's pooled-Q pick moves from a NORMAL meeple on TOP (`2501`) to **meeple-Pass**
(`20174`). Given the isomorphism (§4) that difference is attributable to truncation
and to nothing else.

⚠️ **This cell is SELECTED on having crashed. Its 3.82% node rate and its 1/1 pick
change are conditional on that selection and MUST NOT be pooled into the census
rates.** Its role is validation, not estimation.

**⇒ The instrument detects the phenomenon when it is present, at the production
budget, on the real rules epoch, down to the individual dropped coordinate. The
754,192-node zeros in §5 are a measurement of absence, not an absence of
measurement.**

**What the pilot does already establish**, and it is not nothing: 754,192
search-internal nodes at the production budget, 0 dropped legal actions. That is
**2.5× the entire prior window-audit evidence base** (0/299k, played distribution,
2026-07 Phase 0.2) and it is drawn from the population that had never been sampled.

---

## 6. PRE-REGISTERED READ — what makes this a real defect

Fixed before the full census runs. Three statistics, three independent verdicts.

### P1 (PRIMARY, strength) — `pick_change_rate`

Fraction of censused roots where the champion's pooled-Q pick differs between
`W=25` and the overflow-free window. Exact (§4), not a proxy.

The arithmetic that sets the bands — both constants are the project's own, not
imported:

- A champion seat makes ≈ **72 decisions per game** (72 tiles × 2 phases ÷ 2 seats).
- `PRODUCTION.yaml` CL-060 row: **+2.9775 pts/deck ↔ +49.85 elo** ⇒ **16.74 elo per
  pt/deck**.
- ⇒ `elo_cost ≈ 16.74 × 72 × P1 × r = 1205 · P1 · r`, where `r` is the mean points
  lost per changed move.

| band | verdict | action |
|---|---|---|
| **P1 ≥ 2%** | **REAL DEFECT** | At `r ≥ 0.21 pts` this is ≥ 5 elo, and 0.21 pts per changed move is unremarkable for a disagreement price in this program. Price the changed roots with the existing instrument (`scripts/measurement_infra/oracle_score_pilot.py` + `analyze_oracle_price.py`), then fix (§7). |
| **0.5% ≤ P1 < 2%** | **GREY — price before deciding** | Do **not** fix on the rate alone. Run the oracle price on the changed subset; fix iff the priced cost ≥ +5 elo-equivalent. |
| **P1 < 0.5%** | **CURIOSITY (for strength)** | Reaching 5 elo would need `r ≥ 0.83 pts` per changed move — larger than any per-disagreement price this program has measured. File the finding; do **not** re-architect the window on strength grounds. §6-P3 still applies independently. |

### P2 (SECONDARY, mechanism) — `node_truncation_rate`, `by_depth`, visit-weighted rate

Not a decision statistic on its own. Its job is to say whether the mechanism exists
and whether it behaves as predicted (rate rising with search depth). Pre-registered
guard against a bad inference: **if P2 > 0 while P1 = 0, that is "real but so far
harmless", NOT "dead"** — a pick change is a strictly rarer event than a node
truncation, so P1 has far less power than P2 and a null P1 at this n does not
license a kill.

### P3 (INDEPENDENT, reliability) — `empty_mask_rate`, `world_errors`

**Trigger: ≥ 1 empty-mask node, or ≥ 1 `NoLegalActionsAtInterior` raise. The cost of
this face is not elo — it is a lost tournament game and a hand-written exclusions
dossier — so the trigger is OCCURRENCE, not rate.** Its base rate is plausibly
~10⁻⁹ per node, which no affordable census could bound anyway.

> ### ⚠️ P3 HAS ALREADY FIRED. It is not conditional on this census.
>
> A real `SearchError::NoLegalActionsAtInterior` raise happened **in production**
> on 2026-08-13, inside the champion's own `choose_action`, on cell
> `(deck 126000000135, joshua_seat 0)` of the J7ZERO confirm — reproducibly, three
> times ([CONFIRM_EXCLUSIONS §1](../joshuabot_20260812/CONFIRM_EXCLUSIONS.md)). It
> killed `imap_unordered` and took the confirm leg down at 269/800, and it cost one
> excluded cell plus the audit that wrote that dossier.
>
> **⇒ The minimal fail-loud fix (§7 F-c) is licensed NOW, by this pre-registered
> trigger, whatever P1 and P2 turn out to be.** The census does not decide it and
> cannot un-decide it. What the census is still for is P1 — whether the *silent*
> face costs strength, i.e. whether F-a (widen) is owed on top of F-c.

### Reporting rules (also pre-registered)

- `walled` and `fixed_v1` are reported **separately and never pooled** (different
  wall geometries; the CROSS-BAND humility rule's sibling).
- A null is reported with its rule-of-three upper bound in **events per
  champion-game**, not as "0%".
- No `results.csv` row and no claim is minted from the pilot; the full census owns
  that.

---

## 7. What the fix would be (and what it must not break)

The lever is already indexed: **`docs/LEVER_INDEX.md` → "widen the action window
(25 → ?)"**, F9 spec §7 **J4** — *"cheap for the classical champion, retires the net
arms from any cell that does it."* This census exists to say whether J4 is worth
pulling; it does not propose a new lever.

**F-a — widen the window inside search only (the real fix).** The isomorphism (§4)
makes this behaviour-preserving *except* where truncation was happening, so it
cannot be a strength regression and — by the same argument the k-parallel promotion
used — **owes no new strength measurement**. Measured cost at the production budget:
0.150 s vs 0.147 s per world.
⚠️ **Compatibility.** Action indices are the recorded artifact format: every
`roots.jsonl`, `champ_games.jsonl`, E4 archive and trace stores `W=25` indices.
A naïve global widening is a format epoch change on the scale of `fixed_v1`.
The backward-compatible shape is: search at `W_wide` internally, remap the chosen
action back to `W=25` on the way out (the remap is exact and pure —
`window_truncation_census.remap_action`, with a bijection + order-preservation test).
The only case that cannot be remapped out is a root whose *winning move is itself*
out-of-window, which is exactly today's played-level ~0.5% case and is silently
unplayable already.
⚠️ **Net arms.** Under any learned arm the window is the policy head's output
shape, so widening invalidates every checkpoint. The champion of record is classical
(`kind: classical`, no net), which is why this is available today and why the
decision must be revisited if the learned track returns.

**F-b — recentre.** *Not sufficient, and the census says why.* The window already
follows the centroid: `game.rs:384` re-derives it after every applied action, and
the crash cell's window was correctly centred on a board that fitted inside it. The
F9 recentring work (`centered18` → `fixed_v1`) moved the **start tile** to reduce
**played-level** wall pressure; it does not touch the search-internal population.
Pilot B is a `fixed_v1` census and finds the same zero — consistent with recentring
being orthogonal to this defect rather than a fix for it.

**F-c — fail loudly (the minimum, and ALREADY LICENSED — see §6-P3).** Make the Rust
`legal_mask` surface `n_overflow > 0` instead of swallowing it, matching Python's
`WindowOverflowError`. This fixes nothing; it converts a silent strength leak into a
visible error. It is the natural completion of **`wall_sentinel`** (F9 W4,
`src/carcassonne_ai/wall_sentinel.py`), which already counts the five border faces —
including face 5, `WindowOverflowError` — but only on the **played** path and only in
the Python engine. The clean version of F-c is "give `wall_sentinel` a face-5 counter
that the Rust search feeds", i.e. this census's statistic made continuous.

**F-d — instrument only.** Keep the window, run this census periodically. Sufficient
if P1 lands in the CURIOSITY band and P3 never trips.

Any of F-a/F-c touches `carc-core` ⇒ a rebuild ⇒ the bit-exactness gates, and (for
F-a) a recorded-artifact epoch decision. None of that is in scope here.

---

## 8. Full-census plan — priced

Mean cost measured on the pilots: **10.85 s/root** (`walled`) and **8.76 s/root**
(`fixed_v1`) of single-core time, ~73% search and ~25% node replay.

| leg | roots | ≈ nodes | core-seconds | W=4 | W=8 | W=14 |
|---|---|---|---|---|---|---|
| A `walled` (CL-070 bank, all) | 898 | 8.91 M | 9,743 | 41 min | 20 min | 12 min |
| B `fixed_v1` (all E4 champion plies) | 1,548 | 13.8 M | 13,561 | 57 min | 28 min | 16 min |
| **both** | 2,446 | 22.7 M | 23,304 | **1 h 37 m** | **49 min** | **28 min** |

Resulting power (rule of three, 95%): leg A ≤ 3.4 × 10⁻⁷ per node ⇒ **≤ 0.27
truncation events per champion-game**; leg B ≤ 2.2 × 10⁻⁷ ⇒ **≤ 0.17 per game**.
That is the point of running it — the pilot's ≤ 6/game is not a useful bound, and
≤ 0.2/game is.

**The launcher is [`RUN_CMD.sh`](RUN_CMD.sh)** — the scheduler's dispatch target for
queue item `window_truncation_census` (`scripts/scheduler/queue.json`). It is the
single source of the launch commands; do not re-type them from prose.

```bash
bash measurement/window_truncation_20260813/RUN_CMD.sh <W>     # or let the queue dispatch it
WTC_SMOKE=1 bash measurement/window_truncation_20260813/RUN_CMD.sh   # 2 roots/leg, no markers
```

What the script guarantees, and why each one matters here:

- **Two legs, two PROCESSES, sequential.** `CARCASSONNE_FIX_R9` is latched at import
  (Rust registry `OnceLock` + `base_deck`'s import-time farm derivation), so one
  process cannot run both rules epochs. Each leg's manifest stamps `r9_env_ok`.
- **Foreground / synchronous.** The scheduler has *already* detached the job
  (`setsid`+`nohup` locally, `systemd-run --user --scope -p MemoryMax=8G` remotely)
  and derives its `DONE_`/`FAILED_<id>` markers **from this script's exit code** — so
  the script must never background its own work.
- **Box-agnostic.** Bundle-sync, the `cd`-on-line-1 remote pipe and the memory-capped
  scope are the scheduler's job, not this script's; the only genuine box difference it
  handles itself is the share mount — and it resolves that **by content, never by
  directory existence and never by a default**. The first laptop dispatch
  (2026-08-13 11:21) died `rc=13` in one second because both candidate paths *exist*
  on the laptop and they are different filesystems: `/mnt/c/carc-shared` is a 9p
  `drvfs` mount of the laptop's **own** `C:\` (1 entry, no data) while the real CIFS
  share `//192.168.0.195/carc-shared` is at `/mnt/carc-shared` (369 entries). `[ -d ]`
  cannot tell them apart. The probe now requires a **sentinel** — the CL-070 roots
  file leg A is about to read — under a candidate before accepting it, logs every
  rejection with its reason, and exits 10 if none resolves.
- **Resume-able at ROOT granularity.** Rows stream to `rows.jsonl` (fsync'd per root)
  and every leg runs with `--resume`; a leg with a `DONE_LEG_*` marker is skipped
  outright, so re-running is always safe.
- **Own completion evidence**, independent of scheduler state: `DONE_CENSUS` /
  `FAILED_CENSUS` + `RUN_MANIFEST.json` in this directory.
- **It does not adjudicate itself.** It writes `CENSUS_RESULT.md` — the arithmetic
  plus a mechanical application of §6's bands — and leaves `READOUT.md` to a human.

Knobs if the box is tight: `WTC_N=<n>` caps roots per leg; `--replay-fraction 0.25`
(edit the leg args) cuts the replay quarter of the cost at a 4× coarser node count
and does **not** affect P1, which comes from the searches rather than the replay.

### 8.1 The gate cell — DONE, and it passed ✅

The full census was gated on reproducing the production crash inside the instrument
first. **It reproduces** — §5.1. Reproduced with:

```bash
CARCASSONNE_FIX_R9=1 .venv/bin/python -u \
  scripts/measurement_infra/reconstruct_crash_root.py \
  --deck-seed 126000000135 --joshua-seat 0 --j7-weight 0.0 --profile fixed_v1 \
  --out measurement/window_truncation_20260813/crash_root.jsonl        # 79.5 s

CARCASSONNE_FIX_R9=1 .venv/bin/python -u \
  scripts/measurement_infra/window_truncation_census.py \
  --roots measurement/window_truncation_20260813/crash_root.jsonl \
  --rules-profile fixed_v1 --n 1 --workers 1 --sample head \
  --agent-seed-mode fixed --agent-seed 9400540 \
  --max-examples 256 --verify-all-truncated \
  --out-dir measurement/window_truncation_20260813/crash_cell            # 7.8 s
```

`--agent-seed-mode fixed` is required: the census's `production` seed formula is the
JCZ-match one (`SEED_BASE 9_100_000`, `+seat*4`), while `h2h.champion_seed` uses
`SEED_BASE 9_400_000, +seat*2`. The root's own `move_idx: 59` is read off the file.

**The census legs in §8 are now unblocked.**

---

## 9. Close-out obligations when the census lands

Per the six-touch checklist: `experiments/results.csv` row · `DECISIONS.md` index
line · status banner on this file · `governance/` row if a claim is minted ·
`STATUS.md` top block · `docs/PROGRAM_ROADMAP_2026-07-07.md` line. Plus a
`docs/LEVER_INDEX.md` amendment to the **"widen the action window"** row recording
the search-internal number, since that row currently rests only on the played-level
`0/299k`.
