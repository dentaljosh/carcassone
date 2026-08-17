# CORPUS_PIPELINE — tiearb2_20260816 corpus assembly

**Status: RUN / CORPUS ASSEMBLED, G-DISJOINT PASSED** (2026-08-16). All six
phases executed on the real 850-game input. The first pass failed G-DISJOINT on
layer (c) only (board transposition); phase 5b was added and the plan rebuilt
with the existing instrument — **no plan file was hand-edited**. Realized corpus:
**1350 positions / 724 roots**, all three gate layers at intersection 0. See
[phase 5b](#phase-5b--board-digest-exclusions-added-2026-08-16-after-a-layer-c-gate-failure).

**This document describes CORPUS ASSEMBLY (mining) only.** No phase here
computes a strength, headroom or arbitration statistic. Nothing on this page is
a measurement, and no phase writes an `experiments/results.csv` row.

Driver: [`scripts/tiletie/build_tiearb2_corpus.sh`](../../scripts/tiletie/build_tiearb2_corpus.sh)
· support lib: [`scripts/tiletie/tiearb2_corpus_lib.py`](../../scripts/tiletie/tiearb2_corpus_lib.py)
· phase-5b emitter: [`scripts/tiletie/emit_digest_exclusions.py`](../../scripts/tiletie/emit_digest_exclusions.py)
· gate: [`scripts/tiletie/gate_disjoint.py`](../../scripts/tiletie/gate_disjoint.py)
· tests: [`tests/test_tiearb2_corpus.py`](../../tests/test_tiearb2_corpus.py),
[`tests/test_tiearb2_digest_exclusions.py`](../../tests/test_tiearb2_digest_exclusions.py)

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
  --exclude-rids   measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_all.txt \
  --sample-seed    20260816 \
  --e4-dir         measurement/tiearb2_20260816/corpus/_empty_e4 \
  --champ-games    measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl
```

The driver factors this into a `build_positions_into <out-dir> <exclude-file>`
shell function, because phase 5b runs the **same** invocation against a throwaway
probe directory — the two can then differ only in the exclusion list.

- **`--n 1400`** is the *target*: `stratified_sample` returns the whole supply
  when supply < n, so this is "1400 or everything available", not a floor.
  Realized supply is 1355, so **all of it is taken** and no seeded subsample
  runs; the driver asserts `n_positions == n_supply_after_exclusion` to prove it.
- **`--afterstate-map` is passed explicitly.** Its default globs
  `measurement/tiletie_pricing_20260812/census/afterstate_map_*.json` — relying
  on the default would dedupe the fresh corpus against the **spent** map.
- **`--exclude-rids`** carries `EXCLUDE_RIDS_all.txt` = the spent corpus's 733
  rids **+** the phase-5b board-digest exclusions (§5b below), 738 in total.
  - The **733** come from the spent corpus's own `ARMS.json` **keys** (which *are*
    its rid list — never re-derived from the leg files). Those are **defence in
    depth**: the two corpora are root-disjoint by band, so the expected — and
    realized — outcome is that they remove **0** positions. The driver asserts
    that against the phase-5b probe plan, so a non-zero value STOPS the run
    instead of merely warning.
  - The **5** are the layer-(c) exclusions, and they *do* remove 5 positions.
- The driver then **asserts `afterstate_dedupe.applied == true`** on the emitted
  plan — `run_tiletie.py`'s preflight refuses to launch a plan without it, and
  failing here is cheaper than failing at launch — plus the closing arithmetic
  `probe supply (1355) − digest exclusions (5) == final supply (1350)`.
- The corpus ships its **own** `POSITIONS_PLAN.json` and
  `DROPPED_ALL_TRANSPOSITION.json` in its own `positions/` directory. The
  `scale_all` factors the analysers apply are derived from these and are
  **corpus-specific, not population constants** — the spent corpus's plan must
  never be reused here.

*Smoke-verified* (5 qualifying rows): `afterstate_dedupe.applied = true`,
`n_dropped_all_transposition = 1`, `exclude_rids.n_requested = 733`,
`n_removed_from_supply = 0`, legs 1–4 + `ARMS.json` +
`DROPPED_ALL_TRANSPOSITION.json` + `POSITIONS_PLAN.json` all written.

## Phase 5b — BOARD-DIGEST EXCLUSIONS (added 2026-08-16, after a layer-c gate failure)

```
# 1. throwaway PROBE build — the SPENT RID LIST ALONE
nice -n 19 .venv/bin/python -u scripts/tiletie/build_positions.py \
  --out-dir      measurement/tiearb2_20260816/corpus/_probe_positions \
  --exclude-rids measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_spent733.txt \
  ...                                    # every other flag identical to phase 5

# 2. the layer-(c) exclusion list, off the probe's realized board census
nice -n 19 .venv/bin/python -u scripts/tiletie/emit_digest_exclusions.py \
  --new-dir   measurement/tiearb2_20260816/corpus/_probe_positions \
  --spent-dir measurement/tiletie_pricing_20260812/positions_pooled \
  --out       measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_digest.txt \
  --report    measurement/tiearb2_20260816/DIGEST_EXCLUSIONS.json

# 3. concatenate -> the list phase 5 actually consumes
cat EXCLUDE_RIDS_spent733.txt EXCLUDE_RIDS_digest.txt > EXCLUDE_RIDS_all.txt
```

### Why EXCLUSION, not regeneration, is the right response to a layer-c-only failure

On 2026-08-16 the first assembled corpus (1355 positions / 725 roots) **failed**
G-DISJOINT on layer (c) alone:

| layer | spent | new | intersection | reading |
|---|---|---|---|---|
| a `root_id` (the GAME) | 399 | 725 | **0** | the two corpora share no game |
| b `rid` (the POSITION) | 733 | 1355 | **0** | they share no (game, ply) |
| c `sha256(checksum)` (the BOARD) | 733 | 1353 | **3** | 3 shared boards — *and* 1353 distinct digests from 1355 lines, i.e. 2 duplicate boards **inside** the fresh corpus |

The gate's printed remedy — *"rebuild the corpus from a clean deck-seed band"* —
is the **wrong** remedy for this failure mode, for three reasons:

1. **Layers (a) and (b) positively exclude band contamination.** A dirty band
   shows up first as a shared `root_id`; both identity layers that can see a
   band leak read exactly 0. Whatever layer (c) caught, it did not arrive
   through the deck seeds.
2. **Board transposition is intrinsic to Carcassonne, so no band is "clean" in
   this sense.** Different games reach bit-identical boards, overwhelmingly in
   the opening where only a few tiles are down — every one of the 5 offending
   positions here is at **ply 2**. A fresh band would show its own handful of
   digest collisions against the spent corpus, and so would the band after that.
   Regeneration does not converge on 0; it re-rolls the same intrinsic rate.
3. **The cost ratio is absurd.** Regeneration is a ~4.4 h self-play run to avoid
   **5 positions out of 1355 (0.37 %)**.

Excluding is also the *statistically* correct move: DESIGN §7.3's mechanism is
"remove what the earlier stage took, then apply the SAME seeded sampling rule to
the remainder", which is exactly two-phase sampling without replacement. Dropping
5 rids from the supply *before* sampling is that mechanism, not a new draw.

### The two rules

| rule | what it drops | why |
|---|---|---|
| (a) spent overlap | every fresh rid whose `sha256(checksum)` appears anywhere in the spent digest set | the spent corpus already scored that board; re-scoring it re-imports the winner's curse this corpus exists to escape |
| (b) internal dupes | within the fresh corpus, all but the **lexicographically smallest** rid per digest | matches the spent corpus's own construction — 733 rids / 733 distinct checksums, i.e. **one rid per board** |

The two sets are unioned (they can intersect; the report carries
`n_excluded_by_both_rules` so the three counts are unambiguous either way). After
both rules the fresh digests are internally distinct **and** disjoint from the
spent set, so layer (c) is 0 **by construction** — not by luck of the next band.

### ⚠️ Why the list comes from a PROBE build, never from the final corpus

`emit_digest_exclusions.py` reads a **realized** `positions_*_leg1.jsonl` board
census, so it cannot be pointed at the corpus it is about to fix: a corpus built
*with* these exclusions has no overlap left, the tool would emit an **empty**
list, and feeding that back into a rebuild would restore the offending positions
and fail the gate again. The driver therefore always derives it from a throwaway
probe built with the **spent rid list alone**, and keys the whole of phase 5b on
`EXCLUDE_RIDS_all.txt` already existing — so the pipeline stays reproducible
end-to-end from scratch, with no hand-edited plan anywhere.

`DIGEST_EXCLUSIONS.json` reports **counts only** — no rid, checksum or digest
value — matching `gate_disjoint.py`'s disclosure policy, so the fresh corpus's
audit trail cannot itself leak spent-corpus identities. The `.txt` necessarily
names rids: it is an **input** to `build_positions.py`, not a report.

### Realized (2026-08-16)

| quantity | value |
|---|---|
| rule (a) spent-overlap rids | **3** |
| rule (b) internal-duplicate rids | **2** (2 digest groups, 0 in both rules) |
| total excluded | **5** — `sha256` of the sorted list `089993df94d4ac4a…` |
| `EXCLUDE_RIDS_all.txt` | 733 + 5 = **738** rids |
| probe supply → final supply | 1355 → **1350** (`n_removed_from_supply = 5`) |
| spent-733 list's own effect | **0** removed (bands disjoint, as designed) |
| final corpus | **1350 positions / 724 roots**, `afterstate_dedupe.applied = true` |

*Independently re-derived* after the rebuild: a from-scratch probe rebuilt in a
scratch directory is byte-identical to `_probe_positions/positions_walled_leg1.jsonl`,
re-emits the same 5 rids and the same list `sha256`, and the final corpus is
exactly `probe supply − those 5 rids`.

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

### Realized verdict (2026-08-16, after the phase-5b rebuild)

| layer | identity | spent | new | intersection |
|---|---|---|---|---|
| a | `root_id` | 399 | 724 | **0** |
| b | `rid` | 733 | 1350 | **0** |
| c | `sha256(checksum)` | 733 | 1350 | **0** |

`n_layers_violated: 0`, `passed: true`. Layer (c)'s `n_new == n_new_leg_lines
== 1350`, i.e. the corpus now carries one rid per board with no internal
duplicates — the same shape as the spent corpus.
`sha256(new rid list) = cab69086455fa43a…` (the pre-5b 1355-position list was
`ac88d1fb6488ce64…`; the two fingerprints are how a later reader tells the
rebuilt corpus from the one that failed).

⚠️ **The gate's failure banner still says "rebuild from a clean deck-seed band".**
That advice is right for layers (a)/(b) and **wrong for a layer-(c)-only
failure** — see phase 5b above. `gate_disjoint.py` was deliberately left
unmodified (it is the frozen instrument); read its banner with that caveat.

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

## Verification performed (2026-08-16, phase 5b)

- `pytest tests/test_tiearb2.py tests/test_tiearb2_corpus.py tests/test_tiearb.py
  tests/test_tiearb2_digest_exclusions.py -q` → **151 passed** (18 new).
- The new tests cover both rules on synthetic fixtures (including a rule-(a) case
  the real gate confirms layers a/b cannot see), the smallest-rid tie-break and
  its independence from file order, the two rules overlapping, the counts-only
  disclosure policy (asserted by searching the report for every rid, checksum and
  digest), **idempotence** (twice over the same input; and a no-op over an
  already-excluded corpus), that the emitter's digest is byte-for-byte
  `gate_disjoint`'s, and that excluding the emitted rids really drives layer (c)
  to 0.
- `bash -n` clean on the edited driver.
- Post-rebuild, independently re-derived outside the driver: a from-scratch probe
  build is byte-identical to `_probe_positions`, re-emits the identical 5-rid list
  and `sha256`, and `final corpus == probe supply − those 5 rids` exactly.
