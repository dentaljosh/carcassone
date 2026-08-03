"""F9-A2 quirk-mutation probe — is the cloister gate's "0 mismatches" informative?

A gate that cannot go red is not a gate.  P1, P3 and P4 each ran this pattern
(`probe_fair_mutations.py`); A2 is the first *deliberate behaviour change* in the
series, so it needs the probe twice over — once for the fix and once for the
quirk it replaces:

  * with `--cloister-scan-fix` ON, regressing the fix must make the FLAGS-ON
    lockstep go red;
  * with the flag OFF, applying the fix anyway must make the FLAGS-OFF regate go
    red — i.e. the RF-D-1 rebinding is still load-bearing at the default, which
    is the property `governance`-visible measurements depend on.

As in P4, the mutations are applied to the **PYTHON side only** (never to the
Rust production path), so nothing has to be rebuilt and no debug switch leaks
into the shipped engine.

The four mutations, each a one-line regression:

  fix_regressed   flags ON, but the Python scan runs the LEGACY drifting walk.
                  The direct "did we actually port the fix" check.
  quirk_removed   flags OFF, but the Python scan runs the FIXED walk.  The
                  cloister-quirk mutation check: proves the default path still
                  depends on the rebinding.
  counter_dead    flags ON, `_legacy_scan_cells` claims to have visited
                  everything -> the event counter never increments.  Isolates
                  the new per-ply observable: scores and meeples are untouched,
                  so ONLY the counter check can catch this.
  counter_always  flags ON, `_legacy_scan_cells` claims to have visited nothing
                  -> every completion counts as accelerated.  The other side of
                  the same isolation: it pins the counter's exact semantics, not
                  merely that it is non-zero.

⚠️ **Coverage, not budget, is the trap here** (the A2 analogue of P3's
"sensitivity decays with sims").  Under uniform play the fixed scan runs
thousands of times while its OUTCOME never differs — random play completes ~0.1
cloisters/game and almost never has a monk on one (audit RF-D-1's frequency
caveat).  So this probe runs the fuzz's `monk` policy and, by default, on the
seeds that are already KNOWN to carry an accelerated completion.  A probe on
uniform seeds would report every mutation "not discriminated" and mean nothing
by it.

Usage:
    .venv/bin/python scripts/rustport/probe_cloister_mutations.py
    .venv/bin/python scripts/rustport/probe_cloister_mutations.py --games 40 --scan
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import lockstep_fuzz as LF  # noqa: E402  (sets the leaf/window env preamble)
from wingedsheep.carcassonne.utils.points_collector import PointsCollector  # noqa: E402

OUTDIR = REPO / "measurement" / "f9_a2"

# Seeds measured to carry at least one accelerated completion under the `monk`
# policy (from the 60-game coverage smoke).  Using them keeps the probe cheap
# AND informative; `--scan` re-derives the list instead.
EVENT_SEEDS = [5, 14, 18, 23, 30, 42, 44, 48, 52, 54, 56]


# --------------------------------------------------------------------------- #
# The mutations (context managers over the PYTHON oracle)                      #
# --------------------------------------------------------------------------- #
@contextlib.contextmanager
def _patch(obj, name, new):
    old = getattr(obj, name)
    setattr(obj, name, new)
    try:
        yield
    finally:
        setattr(obj, name, old)


def _force_convention(value: bool):
    """Run the scan under `value` whatever the state says it should be."""
    orig = PointsCollector.remove_meeples_and_collect_points

    @contextlib.contextmanager
    def ctx():
        def mut(game_state, coordinate):
            saved = getattr(game_state, "cloister_scan_fix", False)
            game_state.cloister_scan_fix = value
            try:
                return orig(game_state=game_state, coordinate=coordinate)
            finally:
                game_state.cloister_scan_fix = saved

        with _patch(PointsCollector, "remove_meeples_and_collect_points",
                    staticmethod(mut)):
            yield

    return ctx


class _Everything:
    """A set that claims to contain every cell."""

    def __contains__(self, _item) -> bool:
        return True


def _fake_legacy_cells(result):
    @contextlib.contextmanager
    def ctx():
        with _patch(PointsCollector, "_legacy_scan_cells",
                    staticmethod(lambda game_state, coordinate: result)):
            yield

    return ctx


MUTATIONS = {
    # name: (context-manager factory, flag the driver must run under)
    "fix_regressed": (_force_convention(False), True),
    "quirk_removed": (_force_convention(True), False),
    "counter_dead": (_fake_legacy_cells(_Everything()), True),
    "counter_always": (_fake_legacy_cells(set()), True),
}


# --------------------------------------------------------------------------- #
def _jobs(indices: list[int], fix: bool, max_plies: int) -> list[dict]:
    return [{
        "index": i,
        "deck_seed": LF.FUZZ_SEED_BASE + i,
        "policy_seed": 5_000_000 + i,
        "mode": "monk",
        "max_plies": max_plies,
        "start_rule": "engine",
        "start_row": LF.DEFAULT_START_ROW,
        "start_col": LF.DEFAULT_START_COL,
        "cloister_scan_fix": fix,
    } for i in indices]


def _run(indices: list[int], fix: bool, max_plies: int) -> dict:
    """One lockstep leg, in-process so a monkeypatch is visible to it."""
    mismatch_kinds: dict[str, int] = {}
    games = accel = 0
    for job in _jobs(indices, fix, max_plies):
        r = LF.fuzz_game(job)
        games += 1
        accel += r.get("cloister_accel", 0)
        if r["mismatch"] is not None:
            kind = r["mismatch"]["kind"]
            mismatch_kinds[kind] = mismatch_kinds.get(kind, 0) + 1
        elif r["status"] == "EXCEPTION":
            mismatch_kinds["EXCEPTION"] = mismatch_kinds.get("EXCEPTION", 0) + 1
    return {"games": games, "cloister_accel": accel,
            "mismatch_games": sum(mismatch_kinds.values()),
            "mismatch_kinds": mismatch_kinds}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=0,
                    help="with --scan, how many monk games to search for events")
    ap.add_argument("--scan", action="store_true",
                    help="re-derive the event-bearing seeds instead of using the "
                         "measured EVENT_SEEDS list")
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    if args.scan:
        n = args.games or 60
        found = []
        for i in range(n):
            r = LF.fuzz_game(_jobs([i], True, args.max_plies)[0])
            if r["mismatch"] is not None:
                print(f"  !! control mismatch on seed index {i}: {r['mismatch']['kind']}")
            if r.get("cloister_accel"):
                found.append(i)
        indices = found
        print(f"scan: {len(found)}/{n} monk games carry an accelerated completion")
    else:
        indices = list(EVENT_SEEDS)

    if not indices:
        print("PROBE INCONCLUSIVE: no event-bearing seed found; widen --games")
        return 2

    # Controls: unmutated, both conventions.  Both must be clean, and the
    # flags-on control must actually SEE events, or the probe proves nothing.
    controls = {
        "control_flags_on": _run(indices, True, args.max_plies),
        "control_flags_off": _run(indices, False, args.max_plies),
    }
    for name, c in controls.items():
        print(f"{name}: {c['games']} games, {c['mismatch_games']} mismatches, "
              f"accel={c['cloister_accel']}")
    control_ok = all(c["mismatch_games"] == 0 for c in controls.values())
    covered = controls["control_flags_on"]["cloister_accel"] > 0
    if controls["control_flags_off"]["cloister_accel"] != 0:
        print("  !! flags-off control reported a non-zero counter — that is a bug")

    results = {}
    for name, (ctx, fix) in MUTATIONS.items():
        with ctx():
            results[name] = _run(indices, fix, args.max_plies)
        r = results[name]
        verdict = "RED (discriminated)" if r["mismatch_games"] else "GREEN — BLIND"
        print(f"{name:16s} flags={'on ' if fix else 'off'} -> {verdict}: "
              f"{r['mismatch_games']}/{r['games']} games, kinds={r['mismatch_kinds']}")

    n_disc = sum(1 for r in results.values() if r["mismatch_games"])
    ok = control_ok and covered and n_disc == len(MUTATIONS)
    payload = {
        "probe": "F9-A2/cloister_mutations",
        "verdict": "PASS" if ok else "FAIL",
        "note": ("PASS means: both unmutated controls are clean, the flags-on "
                 "control actually observes accelerated completions (coverage), "
                 "and EVERY mutation is caught. A GREEN mutation means the gate "
                 "is blind to that regression."),
        "seed_indices": indices,
        "deck_seeds": [LF.FUZZ_SEED_BASE + i for i in indices],
        "policy": "monk",
        "controls": controls,
        "control_clean": control_ok,
        "coverage_events_seen": controls["control_flags_on"]["cloister_accel"],
        "mutations": results,
        "n_mutations": len(MUTATIONS),
        "n_discriminated": n_disc,
        "wallclock_s": time.perf_counter() - t0,
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else OUTDIR / "G6_mutation_probe.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    print(f"F9-A2/mutations: {payload['verdict']}  {n_disc}/{len(MUTATIONS)} "
          f"discriminated, controls {'clean' if control_ok else 'DIRTY'}, "
          f"coverage {payload['coverage_events_seen']} events, "
          f"{payload['wallclock_s']:.1f}s")
    print(f"F9-A2/mutations: result -> {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
