# CORPUS_PIPELINE — tiearb2_20260816 corpus assembly

**Status: BUILT / NOT YET RUN** (2026-08-16). Driver written, unit-tested and
end-to-end smoke-validated on a 2-game slice; the real input (850 fresh
self-play games) does not exist yet.

**This document describes CORPUS ASSEMBLY (mining) only.** No phase here
computes a strength, headroom or arbitration statistic. Nothing on this page is
a measurement, and no phase writes an `experiments/results.csv` row.

Driver: [`scripts/tiletie/build_tiearb2_corpus.sh`](../../scripts/tiletie/build_tiearb2_corpus.sh)
· support lib: [`scripts/tiletie/tiearb2_corpus_lib.py`](../../scripts/tiletie/tiearb2_corpus_lib.py)
· gate: [`scripts/tiletie/gate_disjoint.py`](../../scripts/tiletie/gate_disjoint.py)
· tests: [`tests/test_tiearb2_corpus.py`](../../tests/test_tiearb2_corpus.py)

The driver **never self-launches**. It is resumable: every phase is skipped when
its own output already exists (delete that output to force a re-run), and it
accepts a phase whitelist (`build_tiearb2_corpus.sh 2 3`). Worker counts come
from [`WORKERS.conf`](WORKERS.conf) (`W_LOCAL`) — **no worker count is
hard-coded anywhere in the driver**, so the owner's "bump to w30" stays a
one-line edit. Everything runs `nice -n 19`; every phase tees to `logs/`.

---

## Constants

| Name | Value | Why |
|---|---|---|
| deck-seed band | `28100000000 .. 28100000849` | disjoint from the spent corpus's `280000000xx` band by construction |
| nominal games | 850 | `run_gen.sh` |
| `MAX_PER_GAME` | 4 | matches the spent corpus's census |
| `SAMPLE_SEED` | 20260816 | fresh corpus ⇒ fresh seed |
| `CAP_J` | 4 | matches the spent corpus (`--cap-j 4`) |
| `TARGET_POSITIONS` | 1400 | `--n 1400`; `stratified_sample` takes ALL supply when supply < n |
| profile | `walled` | this corpus is 100% `walled` self-play — no e4 stratum, no CL-070 bank |

`TIEARB2_MIN_GAMES` (env) lowers the phase-1 realized-game floor. Default = 850,
i.e. a short generation **hard-fails** rather than silently shrinking the corpus.

---

## Phase 1 — COLLECT

```
nice -n 19 .venv/bin/python -u scripts/distill_flywheel/collect_action_logs.py \
  --in    /mnt/c/carc-shared/tiearb2_20260816/gen \
  --out   measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl \
  --verify 10
```

Then, **always** (it is the gate on phase 1's output, not a by-product of the
merge):

```
nice -n 19 .venv/bin/python -u scripts/tiletie/tiearb2_corpus_lib.py verify-champgames \
  --path measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl \
  --seed-lo 28100000000 --seed-hi 28100000849 \
  --expect-games 850 --min-games 850 \
  --out measurement/tiearb2_20260816/corpus/CHAMP_GAMES_VERIFY.json
```

Raises (loudly, naming the offending seeds) on **any** `deck_seed` outside the
band, on any duplicated seed, on zero games, and on a realized count below the
floor. The old corpus's band (`28000000xxx`) is refused outright — that is the
exact contamination this corpus exists to avoid.

## Phase 2 — CENSUS

```
nice -n 19 .venv/bin/python -u scripts/tiletie/run_census.py \
  --out-dir         measurement/tiearb2_20260816/corpus/census \
  --champgames-path measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl \
  --e4-dir          measurement/tiearb2_20260816/corpus/_empty_e4  --limit-e4-games 0 \
  --bank-path       measurement/tiearb2_20260816/corpus/_empty_bank.jsonl --limit-bank 0 \
  --n-champgames    <4 x realized games>   \
  --max-per-game    4 \
  --sample-seed     20260816 \
  --workers         $W_LOCAL \
  --contention-note "tiearb2 corpus assembly; 100% walled self-play (...)"
```

**`--n-champgames` is computed, not constant.** It is `4 x` the *realized* game
count (re-read from the corpus at phase-2 time, so phase 2 is runnable alone),
so `--max-per-game 4` can take up to 4 plies from *every* game instead of
exhausting the budget on a prefix of them. Nominal: `4 x 850 = 3400`.

**Turning the other two strata off.** `run_census.py` has **no `--no-e4` /
`--no-bank` flag** — the supported knobs are the documented "smoke-test" caps
`--limit-e4-games 0` and `--limit-bank 0`, which are exact at 0
(`e4_all[:0]` / `bank_records[:0]`). They are pointed at an empty directory and
an empty file as well, so the manifest records `n_lines_total: 0` rather than
"a bank we chose to ignore". With no e4 archives resolved, `run_census` launches
**one leg** (`walled`) and gives it all the workers.

*Smoke-verified* (2 games, `--n-champgames 8`, W=2, 0.6 s):
`E4 archives by profile: {}` · `leg task-count estimate {'walled': 8}` ·
`8 rows` · leg manifest `bank.n_censused = 0`, `e4.n_rows = 0`.

## Phase 3 — TRANSPOSITION MAP

```
ENTRY=$(nice -n 19 .venv/bin/python scripts/tiletie/tiearb2_corpus_lib.py stage-shadow \
          --shadow-root measurement/tiearb2_20260816/corpus/_shadow_repo \
          --champ-games measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl)

nice -n 19 .venv/bin/python -u "$ENTRY" \
  --rows    measurement/tiearb2_20260816/corpus/census/rows.jsonl \
  --profile walled \
  --stratum selfplay \
  --out     measurement/tiearb2_20260816/corpus/census/afterstate_map_walled.json
```

The output filename matches the `afterstate_map_*.json` shape
`build_positions.py` globs, and phase 5 passes it explicitly anyway.

### ⚠️ Why phase 3 goes through a shadow repo root

**`transposition_census.py` has no `--champ-games` flag.** Unlike `champ_picks.py`
and `build_positions.py` (which both do), it resolves self-play action sequences
from two **hard-coded** paths inside `main()`:

```
/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl
<REPO>/measurement/champ_action_logs/champ_games.jsonl     # 449 games, band 280000000xx
```

The tiearb2 band appears in **neither**, so every row would fail to resolve, the
script would exit 3 with an empty map, and `build_positions.py` would then raise
`KeyError: afterstate map does not cover ...`.

`transposition_census.py` must not be edited (a self-play generation run is
live). Its `REPO` is `Path(__file__).resolve().parents[2]`, and its only uses of
`REPO` are two `sys.path` inserts plus those two data paths — so it is invoked
through a tree whose `parents[2]` is ours:

| shadow path | kind | effect |
|---|---|---|
| `scripts/tiletie/transposition_census.py` | **hard link** | same inode as the real script (`.resolve()` does not collapse hard links) ⇒ `REPO` becomes the shadow root |
| `scripts/tiletie/{build_positions,chain_census}.py` | symlink | resolve back to the **real** repo, keeping their own `REPO`, leaf env and `LEAF_HASH_OF_RECORD` assert |
| `scripts/measurement_infra` | symlink | ditto, for `root_replay` |
| `measurement/champ_action_logs/champ_games.jsonl` | symlink | **our** corpus |
| `measurement/e4_games/` | empty dir | no e4 rows in this corpus |

The staging call re-creates the tree and **asserts** inode equality with the real
script, so the shadow can never run a stale copy; it also asserts that the entry
script's `.resolve()` stays inside the shadow root (an accidentally symlinked
ancestor would silently restore the real `REPO`).

*Smoke-verified* end to end: a `sys.addaudithook` trace of a real run shows the
only `champ_action_logs` path opened is
`…/_shadow/measurement/champ_action_logs/champ_games.jsonl`, and the run
completed `rc=0` with `n_unresolved = 0`.

## Phase 4 — CHAMP PICKS

```
nice -n 19 .venv/bin/python -u scripts/tiletie/champ_picks.py \
  --census-rows   measurement/tiearb2_20260816/corpus/census/rows.jsonl \
  --rules-profile walled \
  --champ-games   measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl \
  --out           measurement/tiearb2_20260816/corpus/champ_picks/champ_picks.jsonl \
  --workers       $W_LOCAL \
  --nice          19 \
  --resume
```

k8x1376 rust search, ~1.409 worker-s/position. `champ_picks.py` resumes into an
existing jsonl, so the jsonl existing does **not** mean the phase finished — the
driver writes a separate `champ_picks.jsonl.done` stamp and keys resumability on
that. `--bank-roots` / `--bank-records-dir` are left at their defaults and never
read: they are consulted only for `source == "bank"` rows, of which this corpus
has none.

## Phase 5 — BUILD POSITIONS

```
nice -n 19 .venv/bin/python scripts/tiletie/tiearb2_corpus_lib.py emit-exclude-rids \
  --arms measurement/tiletie_pricing_20260812/positions_pooled/ARMS.json \
  --out  measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_spent733.txt

nice -n 19 .venv/bin/python -u scripts/tiletie/build_positions.py \
  --census-rows    measurement/tiearb2_20260816/corpus/census/rows.jsonl \
  --out-dir        measurement/tiearb2_20260816/corpus/positions \
  --champ-picks    measurement/tiearb2_20260816/corpus/champ_picks/champ_picks.jsonl \
  --cap-j          4 \
  --n              1400 \
  --afterstate-map measurement/tiearb2_20260816/corpus/census/afterstate_map_walled.json \
  --exclude-rids   measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_spent733.txt \
  --sample-seed    20260816 \
  --e4-dir         measurement/tiearb2_20260816/corpus/_empty_e4 \
  --champ-games    measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl
```

- **`--n 1400`** is the *target*: `stratified_sample` returns the whole supply
  when supply < n, so this is "1400 or everything available", not a floor.
- **`--afterstate-map` is passed explicitly.** Its default globs
  `measurement/tiletie_pricing_20260812/census/afterstate_map_*.json` — relying
  on the default would dedupe the fresh corpus against the **spent** map.
- **`--exclude-rids`** carries the complete 733-rid list of the spent corpus,
  generated from that corpus's own `ARMS.json` **keys** (which *are* its rid
  list — never re-derived from the leg files). This is **defence in depth**: the
  two corpora are root-disjoint by band, so the expected outcome is
  `exclude_rids.n_removed_from_supply == 0`, and the driver prints a loud warning
  if it is not.
- The driver then **asserts `afterstate_dedupe.applied == true`** on the emitted
  plan — `run_tiletie.py`'s preflight refuses to launch a plan without it, and
  failing here is cheaper than failing at launch.
- The corpus ships its **own** `POSITIONS_PLAN.json` and
  `DROPPED_ALL_TRANSPOSITION.json` in its own `positions/` directory. The
  `scale_all` factors the analysers apply are derived from these and are
  **corpus-specific, not population constants** — the spent corpus's plan must
  never be reused here.

*Smoke-verified* (5 qualifying rows): `afterstate_dedupe.applied = true`,
`n_dropped_all_transposition = 1`, `exclude_rids.n_requested = 733`,
`n_removed_from_supply = 0`, legs 1–4 + `ARMS.json` +
`DROPPED_ALL_TRANSPOSITION.json` + `POSITIONS_PLAN.json` all written.

## Phase 6 — G-DISJOINT gate (always runs)

```
nice -n 19 .venv/bin/python -u scripts/tiletie/gate_disjoint.py \
  --spent-dir measurement/tiletie_pricing_20260812/positions_pooled \
  --new-dir   measurement/tiearb2_20260816/corpus/positions \
  --out       measurement/tiearb2_20260816/DISJOINTNESS.json
```

Three independent identities; **any** non-empty intersection exits 1 with a
banner:

| layer | identity | source | catches |
|---|---|---|---|
| a | `root_id` — the **game** | `ARMS.json` values | two plies of the same game (not independent draws) |
| b | `rid` — the **(game, ply) position** | `ARMS.json` keys | a re-scored position |
| c | `sha256(checksum)` — the **board** | `checksum` on every `positions_*_leg1.jsonl` line, = `game.string_representation(board)` | the *same board* reached from a different game or ply — invisible to (a) and (b) |

`leg1` carries every position exactly once, so it is the complete board census
of a corpus (higher legs would duplicate checksums). Spent side: 733 lines
across `positions_{walled,fixed_v1,app_aug2}_leg1.jsonl` — 733 rids, 399 roots,
733 distinct checksums.

`DISJOINTNESS.json` records the three set sizes, the three intersection sizes,
and the sha256 of both rid lists. It reports **counts only** — no rid, root_id,
checksum or digest value appears in it by construction, so the fresh corpus's
audit trail cannot itself leak spent-corpus identities; the two rid-list
sha256s let a later reader prove *which* two sets were compared without either
being reproducible from the report. Exit codes: `0` pass, `1` overlap, `2` an
input was missing (the gate could not be evaluated — never silently a pass).

*Smoke-verified on real data:* running the gate with a smoke corpus built from
the **spent** band produced `a_root_id intersection = 2` while `b_rid` and
`c_position_digest` were both 0 — i.e. layer (a) caught a real contamination
that a rid-only or board-only check would have waved straight through.

---

## Verification performed (2026-08-16, before any real input existed)

- `pytest tests/test_tiearb2_corpus.py tests/test_tiearb.py -q` → **80 passed**
  (28 new + the existing 52).
- Every flag in the driver checked against the target script's **real `--help`**
  by a script that also fails on any flag the driver uses that is not on the
  verified list (36 distinct flags).
- `bash -n` clean. `shellcheck` not installed on this box.
- End-to-end smoke of phases 2 → 3 → 4 → 5 → 6 on a 2-game slice of the *old*
  corpus (8 census rows → 5 qualifying → 1 transposition drop → 4 positions),
  `rc=0` at every phase, gate correctly `rc=1` on the deliberately overlapping
  input.
