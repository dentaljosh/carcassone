# P1 order-invariance gate — DEFECT REPORT (the gate crashes; the property is no longer being checked)

**Status: DEFECT RECORDED 2026-08-13, ROOT-CAUSED, ⛔ NOT FIXED. No code was changed.
This is a defect report, not a measurement — no `results.csv` row, no band, no claim,
`governance/PRODUCTION.yaml` untouched.**

> ⛔ **READ THIS FIRST — the headline is NOT "the engine is broken".** The crash is real and
> reproduces on demand, but it is **not** an engine scoring bug and **not** a Rust divergence.
> It is a **corpus-loading regression in the gate harness**: since 2026-08-05 the `e4` corpus
> contains archives from non-`walled` rules epochs, and
> [`property_count_final_scores_order.py`](../../scripts/rustport/property_count_final_scores_order.py)
> replays every one of them under the **default (`walled`)** profile. Replaying an
> `app_aug2`/`fixed_v1` archive under `walled` produces a **garbage board**, and the engine then
> crashes on it. Replayed under its **own** profile every one of the 26 archives is clean.
> **The one durable consequence is real and unfixed:** because the script dies on its first
> `e4` position, the **order-invariance property it exists to test has not been checked since
> 2026-08-02**, and `tests/rustport/test_p1_engine.py::test_count_final_scores_is_order_invariant_smoke`
> is a **red test in the suite**.

| | |
|---|---|
| Gate script (the crash site's caller) | [`scripts/rustport/property_count_final_scores_order.py`](../../scripts/rustport/property_count_final_scores_order.py) |
| Crash site | [`engine/wingedsheep/carcassonne/utils/farm_util.py`](../../engine/wingedsheep/carcassonne/utils/farm_util.py) `find_meeples`, L214 |
| The `None` producer | same file, `find_farm_by_coordinate`, L19-L50 (implicit `return None` fall-through) |
| Caller that reaches it | [`engine/.../points_collector.py`](../../engine/wingedsheep/carcassonne/utils/points_collector.py) `count_final_scores`, L306-L308 |
| Replay entry point | [`scripts/measurement_infra/root_replay.py`](../../scripts/measurement_infra/root_replay.py) `replay_actions` (the `game_kwargs` contract) |
| The corpus that regressed it | [`measurement/e4_games/`](../e4_games/README.md) |
| The correct pattern, already in-tree | [`tests/rustport/test_p1_engine.py`](../../tests/rustport/test_p1_engine.py) `_replay_e4_archive` / `_archive_profile` |
| Last GREEN run of this gate | [`P1_p1_count_final_scores_order.json`](P1_p1_count_final_scores_order.json) (2026-08-02) · [`count_final_scores_order.log`](count_final_scores_order.log) (broad run) |
| Red test | `tests/rustport/test_p1_engine.py::test_count_final_scores_is_order_invariant_smoke` |

---

## 1. The crash — VERIFIED

Standalone, at HEAD `5f3dbaf5`, on the first qualifying position:

```bash
.venv/bin/python scripts/rustport/property_count_final_scores_order.py \
    --games 2 --plies-per-game 1 --perms 1
```
```
  File ".../scripts/rustport/property_count_final_scores_order.py", line 274, in main
    PointsCollector.count_final_scores(game_state=ref_state)
  File ".../engine/wingedsheep/carcassonne/utils/points_collector.py", line 308, in count_final_scores
    meeples: [[MeeplePosition]] = FarmUtil.find_meeples(game_state=game_state, farm=farm)
  File ".../engine/wingedsheep/carcassonne/utils/farm_util.py", line 214, in find_meeples
    for farmer_connection_with_coordinate in farm.farmer_connections_with_coordinate:
AttributeError: 'NoneType' object has no attribute 'farms'   # (and, on other seeds,
AttributeError: 'NoneType' object has no attribute 'farmer_connections_with_coordinate'
```

Two distinct dereferences of the same underlying state, both verified:

| symptom | where | meaning |
|---|---|---|
| `'NoneType' object has no attribute 'farmer_connections_with_coordinate'` | `find_meeples` L214 | `find_farm_by_coordinate` fell off the end of its `for` loop and implicitly returned `None` — the farmer's `side` is in **no** `farmer_connection.farmer_positions` on its tile |
| `'NoneType' object has no attribute 'farms'` | `find_farm_by_coordinate` L23 | the farmer's coordinate holds **no tile at all** — `game_state.board[row][col] is None` |

The crash is **not** mid-game-only: with `--plies-per-game 1` (terminal ply only) it still fires,
on the **first** `e4` position.

`count_final_scores` **does** correctly gate on `meeple_type in (FARMER, BIG_FARMER)`
(`points_collector.py:306`) before the farm lookup, so the branch itself is not mis-dispatching.
On every offender the meeple is a genuine `farmer` whose side reports `tile.get_type(side) is None`.

## 2. Root cause — VERIFIED, and it is NOT the engine

[`root_replay.replay_actions`](../../scripts/measurement_infra/root_replay.py) takes a
`game_kwargs` argument, and its own docstring states the contract:

> `game_kwargs` threads a `rules_profile.RulesProfile.game_kwargs()` through to the `Game(...)`
> construction, **for callers replaying archives from a NON-`walled` epoch (the E4 phone games:
> `app_aug2`, `fixed_v1`)**.

`property_count_final_scores_order.py::load_corpus` calls `replay_actions(deck_seed, actions, ply)`
with **no** `game_kwargs` for all three corpora, i.e. it replays every E4 phone archive under
`walled`. Under the wrong profile the start tile and grid geometry differ, so the recorded action
integers decode to different placements and the reconstructed board is unrelated to the game the
phone played.

**Direct A/B over all 26 archives in `measurement/e4_games/`** (replay to terminal ply, profile
resolved per-archive via `analyzer/ev_loss.resolve_profile_name` — the project's own
discriminator, exactly as `test_p1_engine._archive_profile` does it):

| replayed under | archives with a farmer that resolves to `None`/no tile | `count_final_scores` crashes | final scores match the phone's own record |
|---|---|---|---|
| **default (`walled`)** — what the gate does | **15 of 26** | **15 of 26** (12 measured inside `count_final_scores`; the other 3 die one frame earlier, in `find_farm_by_coordinate` on a `None` tile — which is the call `count_final_scores` makes at `points_collector.py:307`) | **2 of 26** (only the 2 genuinely-`walled` archives) |
| **the archive's own profile** | **0 of 26** | **0 of 26** | **26 of 26** |

Under the correct profile every archive reproduces the phone's recorded final scores exactly
(e.g. `1785975832_66810.json`: `[98, 78]` under `app_aug2` vs `[4, 2]` under `walled`).
The `champ` (40 positions) and `golden` (12 positions) corpora — which have no rules-epoch
problem — produced **zero** offenders in the same scan.

**This is therefore corpus drift in the harness, not an engine defect.** Bracket, from
`git log`:

- **2026-07-30** — the first two E4 archives land; both are `walled`.
- **2026-07-31 / 2026-08-02** — the gate runs GREEN: `1407 positions × 20 orders = 28,140
  comparisons, 16,629 meeples, 0 outcome mismatches, 0 residual-list-order differences`
  ([`count_final_scores_order.log`](count_final_scores_order.log)), and a smoke-sized rerun writes
  `verdict: ORDER-IRRELEVANT` ([`P1_p1_count_final_scores_order.json`](P1_p1_count_final_scores_order.json),
  `utc 2026-08-02T05:52:18Z`).
- **2026-08-05** — the first non-`walled` archive lands (`1785975832_66810.json`, `app_aug2`,
  commit `1bc2b1a2`). 23 more follow through 2026-08-12.
- Every run of the gate since then dies on that corpus.

The **2026-05-29 `find_farm` / `opposite_farmer_side` (`TRT→BRR`) fix is NOT implicated.** It
predates the last green run of this very gate by two months, and the offending states are
reachable only through the wrong-profile replay; `find_farm`'s start-independence is not in
question here.

## 3. The genuine engine-side finding (secondary, and it is HYGIENE, not correctness)

`FarmUtil.find_farm_by_coordinate` has an **implicit `return None`** fall-through
(`farm_util.py:19-50` — the `for farmer_connection in tile.farms:` loop simply ends), and both
its caller `count_final_scores` and `FarmUtil.find_meeples` dereference the result unguarded. It
also dereferences `tile.farms` without a `tile is None` check, where the sibling
`farm_for_position` (L189-L200) *does* guard exactly that.

The consequence is that an invalid state surfaces as an `AttributeError` fifteen frames deep
instead of as a named, diagnosable error — which is what turned a one-line harness bug into a
half-day investigation. Under the project's **"fail loudly"** norm this is worth fixing, but note
what it is and is not:

- It is **not** a scoring bug. No legally-reachable state produced a `None` farm in any scan run
  here (26/26 E4 archives under their own profile, 40 `champ` positions, 12 `golden` positions).
- Adding a guard would **not** make the gate pass. It would convert the crash into a clear error
  (or a silently-skipped meeple, which would be worse). The gate needs the corpus fix.

## 4. What is VERIFIED vs what is INFERRED

**Verified (reproduced on disk at HEAD `5f3dbaf5`):**

1. The crash, standalone, exit non-zero, with both tracebacks in §1.
2. That `count_final_scores` filters to `FARMER`/`BIG_FARMER` before the farm lookup, so the
   offending meeple is genuinely a farmer (`points_collector.py:306-307`).
3. That it reproduces with terminal-ply-only sampling (`--plies-per-game 1`), on the first
   `e4` position.
4. That offenders are **exclusively** in the `e4` corpus; `champ` and `golden` are clean.
5. The §2 A/B table: 15/26 archives crash under `walled` (and the 9 remaining non-`walled`
   archives, while not crashing, reconstruct scores unrelated to the phone's record), 0/26 crash
   under their own profile, and 26/26 reproduce the phone's recorded final scores under their
   own profile.
6. That `load_corpus` passes no `game_kwargs`, and that `replay_actions` documents the
   `game_kwargs` requirement for exactly these archives.
7. That the gate was GREEN on 2026-08-02 at 28,140 comparisons, and that the first non-`walled`
   archive landed on 2026-08-05.
8. That `tests/rustport/test_p1_engine.py::test_count_final_scores_is_order_invariant_smoke`
   is currently RED for this reason (it calls `prop.main([...])` directly).

**Inferred (not proven here):**

- That the *mechanism* by which the wrong profile corrupts the board is start-tile/grid geometry
  changing what the recorded action integers decode to. The corruption is proven; this specific
  chain is the reading of `RulesProfile.game_kwargs()`, not an independent measurement.
- That no legally-reachable state can produce a `None` farm. The scans above found none, but
  "none in this sample" is not a proof; §3's guard is recommended precisely because the code
  cannot currently tell the two apart.

**Explicitly NOT known:**

> ⚠️ **Order-independence of `count_final_scores` is UNVERIFIED AT THE CURRENT CORPUS — it is
> not "known-good", and it is also not "never answered".** It was answered on 2026-08-02 over
> 28,140 comparisons against the then-corpus (2 `walled` archives + `champ` + `golden`) and came
> back `ORDER-IRRELEVANT`. It has **not** been re-checked over the 24 phone archives added since,
> and the Rust port's deterministic set-drain order rests on that older, narrower evidence. The
> earlier green run is real evidence; it is not current evidence.

## 5. Fix options — RECORDED, NOT APPLIED

Deliberately not done here; this is the owner's call.

- **(a) The corpus fix — the one that unblocks the gate.** Have `load_corpus` carry each E4
  archive's resolved profile alongside its actions and pass `game_kwargs=prof.game_kwargs()` into
  `replay_actions`, reusing `analyzer/ev_loss.resolve_profile_name` rather than re-deriving the
  discriminator (re-deriving it is what caused the 2026-08-05 EV-loss retraction). The pattern is
  already in-tree in `test_p1_engine._archive_profile` / `_replay_e4_archive`. ⚠️ **R9 is
  import-latched and is NOT expressible through `game_kwargs`** — `_replay_e4_archive` raises when
  the process's latched `CARCASSONNE_FIX_R9` disagrees with the archive's profile, so a
  single-process sweep over mixed epochs needs the same guard (or a re-exec), not a silent grade
  under the wrong farm adjacency.
- **(b) The engine guard (§3).** Make `find_farm_by_coordinate` fail loudly — an explicit raise
  naming the coordinate/side/tile — instead of returning `None` into an unguarded dereference,
  and guard the `tile is None` read the way `farm_for_position` already does. Hygiene; does not
  change any legally-reachable outcome.
- **(c) Re-run the property after (a)** to restore a current `ORDER-IRRELEVANT` verdict over the
  full 26-archive corpus. Until that happens the Rust port's drain-order choice is supported by
  2026-08-02 evidence only.

**Not recommended:** skipping the `e4` corpus, or `try/except`-ing the crash in the gate. Either
would make the red test green while destroying the gate's coverage — the `e4` archives are the
only human-played positions in the corpus.
