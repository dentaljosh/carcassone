# phasegate_prep — execution-layer deviations (launch + post-launch)

The house class distinction, carried from `IS-D1` (invasion round 1) and the `everyply` `EP-D1..D5`
precedent:

- **EXECUTION-LAYER / STATISTICS-BLIND** deviations — a misaddressed reader, a launcher-side typo, a
  path fix, a worker count — are recorded **here**, with root cause, ground truth verified BEFORE
  the fix, the fix itself, and why the smoke could not catch it. They do **not** touch a bar, a gate
  of record, or a branch condition.
- **ANYTHING THAT WOULD MOVE A BAR OR A BRANCH** is not a deviation. Before game 1 it is a
  pre-game-1 amendment to the pair, made in the open with the band unspent. After game 1 it is not
  available at all — only round 2's route (freeze the verdict, record the defect, OWNER authorises a
  named single-clause re-read of the SAME archive).

⛔ **Nothing below moves a bar, a gate of record, or a branch condition.**

---

## PG-D1 — `test_the_band_is_proposed_not_claimed` inverts at authorization (expected)

**2026-08-28, pre-launch.** `tests/test_phasegate_instrument.py::test_the_band_is_proposed_not_claimed`
asserts the **build-time** state — that `BAND_CLAIMED`, `BLIND_COMMIT`, `PINNED_SRC_REV` and
`RUN_LIVE.json` are all **absent** from `measurement/phasegate_prep/`. Every one of those four is an
artifact the launch is *required* to create, so the test **necessarily fails once the round is
authorized**, and it is not a defect in either direction.

**Ground truth verified before proceeding:** with the four artifacts absent (`PINNED_SRC_REV` moved
aside), `tests/test_tiearb_phase_gate.py` + `tests/test_phasegate_instrument.py` = **48 passed, 0
failed**. The pin was then restored. The rust workspace was green in the same window (**201 passed,
3 ignored, 0 failed**).

**Why the smoke could not catch it:** it is a repo-state assertion, not a code path the smoke
exercises. Statistics-blind — it reads no archive and feeds no gate.

**Standing note for the adjudication:** re-running that one test after launch is expected RED and
proves only that the round is authorized. Run the pair's suites at a commit where the four artifacts
are absent if a clean green is wanted.

---

## PG-D2 — `W_LOCAL` 14 → 30 (owner override)

**2026-08-28, pre-launch.** `WORKERS.conf` shipped `W_LOCAL=14` (the design-time figure behind
DESIGN §6.4's realized 1.45:1 fleet ratio and §6.5's 13.5 h balanced wall). The owner's ratified
Shabbos envelope sets the defaults verbatim: *"we should default to w22 laptop w30 local"*.
`W_LOCAL=30`, `W_LAPTOP=22` unchanged.

**Why it is statistics-blind:** `W` is throughput-only. Games are bit-identical at any `W` and **no
gate in this pair reads a clock** (READ_RULE header; DESIGN §6.4). It moves wall clock, and it makes
the design's ETA conservative rather than optimistic — the cell→box assignment is **not** recomputed,
because the assignment is frozen in `screen_lib.CELLS` and is a gate input (`G-HOST`).

---

## PG-D3 — the wheel: DESIGN §7.7 prose vs. the implemented `G-WHEEL-SAME`

**2026-08-28, pre-launch.** DESIGN §7.7 instructs *"Install the SAME WHEEL FILE on both boxes …
NEVER a laptop-local `maturin build`"*, on the stated reason that a per-box build would move
`carc_rs_binary_sha` and `G-WHEEL-SAME` would refuse. The **implemented** gate does not work that
way: `analyze_phasegate.py:481–500` asserts `G-WHEEL-SAME` **per box** (`by_role`), documenting that
`carc_rs_binary_sha` is box-local and that `carc_rs_build` is the cross-box witness — and READ_RULE
§4's `G-WHEEL-SAME` row says the same in its own parenthesis.

**Resolution — satisfy BOTH readings, deviate from neither:** one wheel file was built on the local
box (`maturin build --release -m rust/carc/carc-py/Cargo.toml`, rustc 1.96.0) and the **same file**
was copied to the laptop and installed there. The wheel is `abi3` (`cp312-abi3-manylinux_2_34_x86_64`),
so it installs against the laptop's Python 3.14 as well as local's 3.12. No laptop-local `cargo`
build was performed — the laptop has no `rustc` on its non-interactive `PATH` in any case.

**Statistics-blind:** it is a build-transport choice; both readings of the gate pass under it.

---

## PG-D4 — the installed wheel's sha ≠ `IDENT_BITEXACT.json`'s build-time sha

**2026-08-28, pre-launch.** `IDENT_BITEXACT.json` records `carc_rs_binary_sha =
eff20530854d914a` for the wheel built **in the build worktree**. The wheel deployed for the round,
rebuilt from merged `HEAD` on the main tree, is `05fe19ecb65d06a1`. Rust release builds are not
byte-reproducible across build directories, so a differing sha for identical source is expected.

**Why this is not an identity failure:** `IDENT-BITEXACT` proves a property of the **source** —
`gate=all` reproduces the ungated arbiter's action sequences and `gate=none` reproduces the
champion's, both bit-for-bit — and that proof is carried by the merged source, not by a particular
`.so`. `G-WHEEL-SAME` binds **across this round's own cells** on each box, never against the build
fixture. The round additionally carries its own `IDENT` **game** cell, which is what DESIGN §7.7's
`G-WHEEL-SAME` re-owe rule actually requires of a wheel change.

---

## PG-D5 — `HEAD` moved under the preflight (docs only)

**2026-08-28, pre-launch.** `HEAD` was `2d0ecdde` (the phasegate build merge) when the preflight
opened and `f52978b5` a few minutes later — an orchestrator commit touching
`docs/PROGRAM_ROADMAP_2026-07-07.md` and nothing else (`git diff --stat 2d0ecdde..f52978b5` = 1 file,
1 insertion, 1 deletion). No code path moved; `run_cells.sh`'s `assert_rev` cleanliness check
(`src engine scripts rust tests`) was clean at every boundary.

**Handling:** `PINNED_SRC_REV` is (re)written from `git rev-parse HEAD` on **each box** after the
last launch commit, so the pin names the launch `HEAD` on both boxes and `G-REV`'s cross-box clause
(`screen_lib.cross_box_rev_gate`) sees one 40-hex pin.

---

## PG-D6 — no `RUN_LIVE.json` and no watchdog in this instrument

**2026-08-28, pre-launch.** Unlike `invasion_screen_r3_prep/run_cells.sh` (1,586 lines, which drops
its own `RUN_LIVE.json` freeze-latch sentinel and censuses foreign ones), this round's
`run_cells.sh` is a 246-line launcher that creates **no** `RUN_LIVE.json` and ships **no** watchdog.

**Handling:** the executor drops `RUN_LIVE.json` by hand after the last launch commit, so the
house-wide freeze-latch hook protects the round in the usual way. ⛔ **No watchdog was improvised** —
none exists for this instrument, and inventing one at launch is exactly the class of launcher-side
change that has no selftest behind it. The orchestrator owns liveness monitoring for this round.
---

## PG-D7 — `--out` is ambiguous in `eval_fair_puct` (launcher-side, caught by the smoke)

**2026-08-28, pre-launch, first smoke attempt.** `run_cells.sh:179` passed `--out "$out"`.
`eval_fair_puct` defines `--out-root` and `--out-subdir` and **no** `--out`, so argparse refused:
`ambiguous option: --out could match --out-root, --out-subdir`. The cell died before playing a game.

**Ground truth before the fix:** `eval_fair_puct.py:4351-4353` resolves the output dir as
`root / sub` with `sub = args.out_subdir or tag` and `root = args.out_root or EVAL_ROOT`, so
`--out-root "$SHARE/$OUT_TAG" --out-subdir "$name"` names **exactly** the `"$SHARE/$OUT_TAG/$name"`
the launcher already `mkdir -p`s and already uses for its `DONE` marker. Both precedent launchers
(`tiearb2_stage2_20260817/run_cells.sh:213`, `invasion_screen_r3_prep/run_cells.sh:324`) use the
two-flag form.

**Fix:** the two-flag form. **Why the smoke could not catch it earlier:** the smoke *is* what caught
it — `--dry-run` only *prints* the argv, it never hands it to argparse. Statistics-blind: the cell
never started, and the directory it names is unchanged.

---

## PG-D8 — `--rules-profile` was never passed: the round would have run `walled`

**2026-08-28, pre-launch, first smoke attempt.** `WORKERS.conf` carries `RULES_PROFILE=fixed_v1`
(DESIGN §2.4) but `run_cells.sh` never passed it to `eval_fair_puct`. The flag's argparse default is
`rules_profile.DEFAULT_PROFILE` = **`walled`** — the pre-F9 engine of record — so **every cell would
have been played under the wrong rules epoch**, and `G-RULES` (`manifest:rules_profile.name` vs
`screen_lib.RULES_PROFILE == "fixed_v1"`) would have voided all four archives after the full ~320
core-h had been spent.

**Ground truth before the fix:** `src/carcassonne_ai/rules_profile.py:365-372` —
`ap.add_argument(flag, choices=known(), default=DEFAULT_PROFILE)`, and `DEFAULT_PROFILE` is
`"walled"`. `invasion_screen_r3_prep/run_cells.sh:323` passes `--rules-profile "$RULES_PROFILE"`.

**Fix:** `--rules-profile "$RULES_PROFILE"` added, sourced from `WORKERS.conf` like every other
constant. **Verified on the emitted smoke manifest** (the IS-D1 address: config from
`manifest.json`): `rules_profile.name = "fixed_v1"`, `r9_env_ok = true`, `r9_env_observed = true`.

**Why the smoke could not catch it in `--dry-run`:** a missing flag prints as a missing flag and
looks like nothing. It is visible only in the **emitted manifest** of a real archive, which is
precisely the reason DESIGN §9 makes the smoke end in the adjudicator rather than in a log grep.

---

## PG-D9 — ⛔ `--paired` was never passed: the round would have produced ZERO deck-paired margins

**2026-08-28, pre-launch, during the first smoke.** `run_cells.sh` passed `--n "$n_games"` without
`--paired`. `eval_fair_puct.py:2865-2872`:

```python
def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]   # n DISTINCT decks, ONE seat each
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))                      # n//2 decks, BOTH seats
    return work
```

**Three separate voids, from one missing flag:**

1. **The primary statistic becomes uncomputable.** READ_RULE §1 is
   `D(deck) = (diff(a_seat=0) + diff(a_seat=1))/2`, *"mean over decks appearing in BOTH seatings"*,
   and a deck missing a seating is **DROPPED**. Unpaired, **no** deck appears in both seatings, so
   `n_paired = 0` on every cell.
2. **`G-DECKS` fails on its own half-played clause** (*"no deck appears at one seat only"*) and on
   `n_common == frozen n_decks` (0 ≠ 1037).
3. **`G-DECKS` also fails on range and on `G-SUBPOOL`.** Unpaired, a cell consumes
   `2 × n_decks` seeds: `ARB_EARLY_L` would have run `154000000000..154000002073`, outside its frozen
   `..154000001036` **and straight through `ARB_EARLY_R`'s sub-range**, destroying the disjointness
   the pool is pooled on.

With `--paired`, `--n 2074` yields exactly `1037` decks × 2 seatings over
`154000000000..154000001036` — the frozen spec, exactly.

**Ground truth before the fix:** both precedent launchers pass it —
`tiearb2_stage2_20260817/run_cells.sh:213` (`--n "$N" --paired --seed-start "$BAND"`) and
`invasion_screen_r3_prep/run_cells.sh:322`. The first smoke's own log line confirmed the defect
live: `info=fair n=22 paired=False`.

**Fix:** `--paired` added. Both smokes were **re-run from scratch** after the fix rather than
adjudicated in the wrong shape — a smoke that does not play the production shape is not a smoke.

**Why this one is the dangerous class:** it is *silent*. The unpaired cells run to completion, emit
healthy-looking archives and burn the full round; the defect surfaces only at adjudication, on a
spent band. It is the same family as the inverted-liveness hazard DESIGN §7.4 names — a default that
looks perfectly healthy — and it is why DESIGN §9 requires the smoke to end in **this pair's own
adjudicator** against a real emitted archive.

---

## PG-D10 — the smoke's §9 product arrives via `summary.json`, not via `SMOKE_<role>.json`

**2026-08-28, pre-launch (observation, no code changed).** DESIGN §9 gives the smoke one substantive
job beyond liveness: *return the realized per-phase fired counts*. The adjudicator's `--smoke-mode`
record cannot carry them, because `adjudicate()` keys `cells` on `screen_lib.CELLS` names and the
smoke archives are `SMOKE_EARLY` / `SMOKE_FULL`, which are not cells. So `SMOKE_<role>.json` comes
back with `cells: {}`, `per_phase_fires: {}` and `round_gates_ok: false` — all **structurally
expected** for a throwaway archive with no named cell in it, and **not** a smoke failure.

⛔ **The adjudicator was NOT modified** — it is frozen law at the blind commit, and a launcher-side
convenience is never a reason to touch it.

**Where the number actually is, and it is complete:** the archive's own `summary.json` carries the
full G-PHI address set — `tiearb_fired_{early,mid,late}_total`, `tiearb_fired_by_phase_sum`,
`tiearb_fired_plies_total`, `tiearb_fired_share_{early,mid,late}`, `tiearb_pickchanges_*_total`,
`tiearb_phase_gates`, plus the emitter's own note that these deduped runtime shares **supersede**
DESIGN §6.2's raw-tie proxy for sizing and are to be read **only on a `phase_gate=all` cell**. The
`gate=all` smoke leg is exactly that cell, so the round's ETA input is available before game 1 as
DESIGN §9 intends.

**Corroboration that the gate is not a no-op, from the `gate=early` leg's own telemetry:**
`fired_early 134 / fired_mid 0 / fired_late 0`, `phase_gates ['early']` — the disjointness property
`tests/test_tiearb_phase_gate.py` asserts offline, reproduced live in a production-knob archive.

---

## PG-D11 — A2: the widened-anchor extension leg, dispatched without touching the frozen cell table

**2026-08-29, A2 launch.** A2 widens the `ARB_FULL` **anchor** from 400 to 1,200 decks on the
**same, already-claimed** band 154e9, so the anchor is deck-matched against the finished `ARB_EARLY`
1,200. The +800 decks are `154000000400..154000001199` — the exact complement of `ARB_FULL`'s first
400 inside `ARB_EARLY`'s range. ⛔ **No new band is claimed** and no seed is invented.

**The problem.** `run_cells.sh` reads its cell table from `screen_lib.CELLS`, which is **frozen law**
and whose `sanity_check()` pins the round's shape (`ARB_EARLY` sub-cells sum to 1200, `ARB_FULL`
starts at `BAND`, sub-ranges disjoint and contiguous). Adding `ARB_FULL_EXT_*` to that table would
edit the pair after game 1 — **not available**. Duplicating the launcher into a second script would
re-introduce exactly the launcher-drift the design forbids by construction.

**The fix.** The leg is named on the **command line** (`--ext-name/--ext-gate/--ext-seed-start/--ext-n`)
and dispatched through the **same `run_cell()`** the frozen cells use. Every other knob still
resolves from `WORKERS.conf`, and the entire precondition ladder — selftest, `IDENT-BITEXACT`,
`BLIND_COMMIT`, `BAND_CLAIMED`, `assert_rev` before and after, the full-args census — runs unchanged.
A guard **refuses** `--ext-name` equal to any frozen cell name, so an extension can never write into
a finished archive.

**Ground truth that no smoke is owed — the same-role argv diff.** Dry-running `ARB_FULL_EXT_R` at
`--role laptop` against the frozen `ARB_FULL` at `--role laptop` yields 46 tokens each, differing in
**exactly three**:

```
20c20   800            -> 740                    (--n)
23c23   154000000000   -> 154000000830           (--seed-start)
29c29   ARB_FULL       -> ARB_FULL_EXT_R         (--out-subdir)
```

`--paired`, `--rules-profile fixed_v1`, `--cand-tiearb-phase-gate all`, the budget, the endgame, the
backend, the arbiter rung and the `BLIND_COMMIT` stamp are **byte-identical**. (A cross-role diff
additionally shows `--workers` and `--out-root`, which are role resolution — the same way A1's own
two boxes differed from each other.) This is the coordinator's stated condition for waiving a new
smoke, verified rather than asserted.

**What this leg does NOT do.** It does not re-read, re-run or write into `ARB_FULL`. It does not
touch a bar, a gate or a branch: A1's verdict is adjudicated (`E-UNRESOLVED`), `G-ANCHOR` already
fired on the frozen 400 (+3.46, z 5.9), and the `FULL−EARLY` contrast these decks enable is a
pre-registered **companion** that DESIGN §3.2/§4.4 forbid as a branch input.

⚠️ **A2 owes its own reader.** `analyze_phasegate.py` keys `cells` on `screen_lib.CELLS`, so
`ARB_FULL_EXT_L/R` are invisible to it — deliberately, and exactly as `SMOKE_*` and `_VOID_*` are.
Nothing in this launcher adjudicates A2.

### The split, derived from A1's REALIZED costs (not from the design's ratio)

Per-game worker-seconds at 72 moves/side, from each finished cell's own summary, reading
`champ_prefix_ms_per_move` as the **candidate** side (the field-name trap, DESIGN §6.1):

| cell | box | W | gate | cand ms/move | opp ms/move | worker-s/game |
|---|---|---:|---|---:|---:|---:|
| `ARB_FULL` | laptop | 22 | all | 4065.0 | 1714.1 | **416.1** |
| `ARB_EARLY_R` | laptop | 22 | early | 2601.2 | 1681.2 | 308.3 |
| `ARB_EARLY_L` | local | 30 | early | 3048.7 | 1972.1 | 361.5 |
| `IDENT` | local | 30 | none | 1871.4 | 1907.0 | 272.0 |

The laptop ran **both** gates, giving an in-box `all/early` ratio of **1.350**; applying it to local's
early cost projects local `gate=all` at **488.0** worker-s/game. Throughputs are then
local `30/488.0 = 0.06148` and laptop `22/416.1 = 0.05287` games/s.

⚠️ **The realized local:laptop advantage is 1.163×, NOT the design's 1.45×.** At `W=30` on a 16C/32T
box each worker is ~17% slower than the laptop's at `W=22` on 24 threads, so nominal `W` overstates
local's edge. Balancing on the realized rates rather than the nominal ones:

| leg | box | W | seeds | decks | games | projected wall |
|---|---|---:|---|---:|---:|---:|
| `ARB_FULL_EXT_L` | local | 30 | `154000000400..154000000829` | 430 | 860 | 3.89 h |
| `ARB_FULL_EXT_R` | laptop | 22 | `154000000830..154000001199` | 370 | 740 | 3.89 h |

Disjoint, contiguous, and together exactly the 800 decks `154000000400..154000001199`. The two legs
finish within ~9 s of each other on the model; the coordinator's illustrative 470/330 would have
left local ~45 min long.
