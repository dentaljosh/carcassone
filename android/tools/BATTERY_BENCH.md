# Battery A/B bench — energy per move across `rust_threads` (and tie-arbiter) arms

One-sitting (~30 min) measurement of **joules/move** for the on-device champion at
`rust_threads` ∈ {4, 2, 1}, using the debug-only `BenchService` +
`battery_bench.sh`. Play is bit-identical across arms — the rust search folds its
k worlds deterministically at any thread count (`carc-core/src/fair/mod.rs::
search_worlds`, `thread_count_invariance` test; battery-audit commit `7ae0d742`)
— and every session **verifies** that with a move-list hash before any energy
number is printed.

What it never touches: the E4 archive (`files/games/`), the autosave, the live
app session, or `governance/PRODUCTION.yaml` (read for the budget; the bench
overrides thread count via its own intent extra, never by editing the YAML).

## Sunday commands

```bash
cd /home/doctor/projects/carcassone

# 0. One-time per app change: build + install the DEBUG apk (bench mode is debug-only).
( cd android && ./gradlew assembleDebug )
android/tools/adb_connect.sh
adb install -r android/app/build/outputs/apk/debug/app-debug.apk

# 1. Phone prep (at the phone): UNPLUG it, close/finish any game in progress,
#    leave it on the home screen. Wireless debugging on.

# 2. Validate everything without running anything:
android/tools/battery_bench.sh --dry-run

# 3. The measurement (defaults: arms "4 2 1", 3 interleaved reps, 24 moves/run,
#    60 s cooldown, 60 s idle baseline):
android/tools/battery_bench.sh
```

Watch progress in a second terminal (optional): `adb logcat -s CarcBench`.

**Measurement condition (REVISED 2026-08-16 — screen ON, top-app):** the
session holds the debug-only black `BenchActivity` in front at minimum
brightness for the whole session, because that pins the app in the **top-app
cpuset (all 8 cores) — the same scheduling class as real in-app play**. The
original screen-off design measured a different machine: with the screen off,
a shell-started FGS runs in the `/background` cpuset (little cores 0-3 only;
verified on the SDK-37 preview — moves ran 2.00 s vs the in-app 1.551 s, and
measured power sat below idle). Consequences: gross J/move now includes the
screen at min brightness; the idle baseline is measured in the same
screen-on/top-app condition, so the **net column is the marginal search
energy** — the number the thread-count decision wants. The driver verifies
`/proc/<pid>/cpuset == /top-app` before the session and before every run, and
restores brightness/screen state afterward.

**Android 17+ launch notes (same day, same preview build):** (1) newer Android
rejects FGS starts from the adb shell ("Background start not allowed …
pkg=com.android.shell") when the app is not foregrounded; the script arms a
temporary power-allowlist entry (`cmd deviceidle tempwhitelist`, re-armed
per launch — the OS clamps shell grants to ~5 min) and the BenchActivity
foregrounding independently satisfies the restriction. (2) `dumpsys package`
stopped listing intent-filter-less services, so the precondition probe falls
back to md5-matching the installed apk against the local debug build. (3)
`adb pull` of `/data/misc/perfetto-traces/` fails on this build — `--perfetto`
traces record but don't land; treat the flag as broken here. The artifact dir
records `device_build.txt` (`ro.build.fingerprint`) so results can be
conditioned on the OS build — this phone rides a preview channel that will
change under us. (4) adb-shell-eats-stdin: `ashell`/`runas` are stdin-guarded
(`</dev/null`) so calls inside `… | while read` loops can't swallow the run
plan (that truncated a session to 1 of 9 runs), and a run-count gate refuses
to report a truncated session.

**Expected duration** with defaults: 9 runs. At ~1.55 s/move × 24 moves the
4-thread runs are ~40 s; fewer threads are slower (that is half of what is being
measured) — budget ~40–150 s/run + 60 s cooldown each ≈ **20–30 min** total.
The script prints a rough ceiling before starting; per-run timeout is 900 s.

## What a result looks like

Artifacts land in `measurement/battery_bench_<UTCstamp>/`: `results.md`,
`results.json`, `samples.csv`, `runs/*.json`, `batterystats.txt` (cross-check),
optional `traces/*.pftrace`. The table (numbers illustrative, NOT measured):

| rust_threads | reps | J/move (mean ± sd) | s/move (mean ± sd) | mean W | net J/move |
|---|---|---|---|---|---|
| 1 | 3 | 9.412 ± 0.310 | 4.902 ± 0.05 | 1.92 | 8.101 |
| 2 | 3 | 7.855 ± 0.24 | 2.410 ± 0.03 | 3.26 | 7.201 |
| 4 | 3 | 7.210 ± 0.280 | 1.550 ± 0.02 | 4.65 | 6.788 |

Above the table the report states the identity gate result; a hash mismatch
**aborts before any energy number is computed** (exit 5) — that would mean the
arms did different work (mixed builds, or a run silently degraded to the Python
floor) and the comparison is void.

## The tie-arbiter axis (added 2026-08-17)

An arm may be spelled `THREADS:TIEARB_B` instead of a bare thread count, which
arms the **tie arbiter** (`rust/carc/carc-core/src/tiearb.rs`, tiearb2 Stage 2)
at `B` CRN worlds with the mode/salt/eps of record. `B` absent or `0` is the
champion as deployed — no arbiter keyword reaches the rust config at all, so the
control arm is byte-identical to what this bench measured before the axis
existed.

```bash
# champion vs champion+arbiter(B=16) vs champion+arbiter(B=2), all at rust_threads=2
android/tools/battery_bench.sh --arms "2 2:16 2:2" --reps 3 --moves 48
```

⚠️ **The identity gate had to be earned, not weakened.** The arbiter changes the
returned action at tied plies *by design*, so free-running armed and unarmed arms
would diverge and the move-hash gate would — correctly — abort. Instead every arm
drives the **champion trajectory**: `carc_bench` reads
`last_move()["tiearb_champ_pick"]` and applies *that*, so the armed arm performs
all the arbitration work (tie detection, the CRN world set, the `B × arms`
tier-1 playouts) at exactly the positions the champion line visits, and only the
action fed back into the game comes from the champion. The gate therefore keeps
its full strength across this axis, and per-move energy is comparable position
for position. **This prices arbitration; it says nothing about what the
arbiter's picks are worth** — that is a game-cell question, not a bench one.

Liveness is asserted, not assumed: `carc_bench._BenchSession._assert_tiearb`
reads the RESOLVED knobs back off `FairAgentRs.stats()` and compares them
field-by-field to the arm's request, and a run whose armed arbiter fired on zero
tile plies is reported `ok: false`. A stale `carc_rs` wheel would otherwise play
a perfectly ordinary champion and report "the arbiter costs ~nothing" — the J13
failure mode.

The report gains a **tie-arbiter cost block**: fires/tile plies, mean arms,
seconds per fired ply by two independent routes (the rust agent's own
`tiearb_secs` clock and the arm-to-arm subtraction), ΔJ per fired ply, per-game
projections at the desktop-measured `phi`, %battery/game, and **`rho_phone`
measured** against the 1.551 s/move denominator that
`measurement/tiearb2_stage2_20260817/PHASE_A.md` §1 used for its 5.520
prediction.

⚠️ **A bench run covers only the first `--moves` moves of a game**, which are
cheaper than the game average (small board, trivial meeple plies) and tie more
often. So the session's own control `s/move` runs well below 1.551, and the
firing rate per tile ply runs above the whole-game `phi` — which is exactly why
`rho_phone_measured` divides by the 1.551 of record and the session-relative
figure is reported beside it rather than instead of it.

## Interpretation caveats

- **`current_now` sign conventions differ by device** (negative-on-discharge on
  most Pixels, positive on some other kernels). The report step detects the
  convention from the median sample sign — valid because the script refuses to
  run while charging — and normalizes so discharge power is positive. Units are
  sanity-checked as µA/µV; a device reporting mV fails loudly instead of being
  1000× wrong.
- **Gross vs net:** J/move integrates the whole workload window (fuel gauge =
  whole-phone draw, screen ON at min brightness per the top-app condition
  above). The `net` column subtracts the idle baseline measured in the same
  condition — net is the marginal search energy and the decision-relevant
  number; both are honest, quote which one you mean.
- **Fuel-gauge sampling is tier 1.** If the device advertises perfetto's
  `android.power` data source (ODPM power rails; detected at runtime —
  `--perfetto`), a per-run trace is saved as a finer-grained artifact, not
  parsed by this script.
- **batterystats** per-package deltas are saved as a cross-check only; its
  attribution model is coarser than the direct integration.
- The two `t1_r*`-style repeats give an sd from n=3 — enough to rank arms that
  differ by tens of percent, not to resolve a few percent. Re-run with
  `--reps 5` if the arms come out close.

## Decision rule (read before adopting anything)

**The call is the owner's, on the measured numbers — this file decides
nothing.** The trade is **J/move vs latency**: fewer threads generally cost
less energy per move but take longer per move (`s/move` is in the table for
exactly this reason), and the current UX baseline is **1.551 s/move** at the
production setting. The production value lives in `governance/PRODUCTION.yaml`
`deploy_profiles.mobile.rust_threads` — this bench never writes it; changing it
is a governance decision with the usual close-out, taken on this table plus the
latency the owner is willing to feel per move. Strength is NOT part of the
trade: play is identical at any thread count (that is what the hash gate
proves), so the decision is purely energy vs wall-clock.

## How it works (one paragraph)

`BenchService` (debug sourceset only, started via
`am start-foreground-service`, partial wakelock, no UI) calls
`carc_bench.run_bench(n_moves, rust_threads, seed)`, which constructs a private
`android_bridge._Session` exactly as the app would — same YAML budget, same
rules profile, same seeding machinery, untouched — then overrides only the
session's resolved `rust_threads` before the rust mirror starts. It plays
`n_moves` champion decisions back-to-back (both seats, forced single-action
plies applied but not counted), timing each, and writes
`files/bench/<tag>.json` with the move-hash and the loop's device-clock window.
The host script samples `current_now`/`voltage_now` at ~1 Hz with device-clock
timestamps (no clock-skew term), trapezoid-integrates each run's window,
gates on the hashes, and writes the table. Math lives in
`battery_bench_lib.py`, unit-tested in `tests/android/test_battery_bench_lib.py`.
