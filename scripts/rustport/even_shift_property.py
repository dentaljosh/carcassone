"""P5 / G5 leg 2 — the EVEN-shift property, four engines in lockstep.

`tests/test_start_tile_grid_bound.py` (merged 2026-07-31) pins the property that
makes a future recentring of the start tile safe for every trained checkpoint:

    the network representation is translation-invariant, so moving
    `starting_position` is representation-neutral **provided the shift is EVEN
    on both axes** — `board_repr.offset_from_centroid_sums` centres the window
    with `round(sum / count)`, and CPython's banker's rounding is equivariant
    under even translations only (`round(6.5) == 6`, `round(17.5) == 18`).

This driver reproduces that property against the Rust port and, at the same
time, gates the port at the shifted row.  Four engines are advanced by ONE
action-index stream (the only thing all four can be driven by):

    Py@base   Rs@base        the engine's (6, 15)
    Py@shift  Rs@shift       (6 + d_row, 15 + d_col), both shifts EVEN

Per ply it asserts, in this order:

  1. **port identity at BOTH rows** — `string_representation` byte-equal
     Python↔Rust at base and at shift.  (A shifted board is built the way the
     worktree test does; `Game.get_init_board` hard-codes the engine start.)
  2. **the exact documented transform** — every row/col in the shifted state is
     the base state's plus `(d_row, d_col)`: `placed_coords` with their tiles,
     `placed_meeples` in list order, `last_tile_action`; and scores, meeple
     counts, deck length, current player, phase and terminality are EQUAL.
  3. **the window translates exactly** — `offset.origin_(row,col)` shifted by
     exactly `(d_row, d_col)`, no banker's-rounding slip.
  4. **the encoding is bit-identical** — `get_canonical_form` board tensor and
     scalars byte-equal between base and shift (the worktree assertion), and the
     legal mask byte-equal across all four engines.
  5. `flat_base_score` equal for both POVs.

Comparison stops (PASS-with-flag, `compared` recorded) the first time the legal
MASKS diverge: that divergence IS the invisible-border bug — the base board's
6 rows of headroom deny rule-legal placements the shifted board offers — and
past it the two games are no longer the same game.  Every other check is a hard
failure whenever it fires.

Deck seeds: the throwaway fuzz range 97_000_000_000 + i (NOT a registered claim
band).

Usage:
    .venv/bin/python scripts/rustport/even_shift_property.py --games 200 \
        --workers 16 --d-row 12
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ["CARCASSONNE_WINDOW_AUDIT"] = "1"   # before game_wrapper is imported

# ⚠️ BEFORE any carcassonne_ai import (see scripts/rustport/prod_leaf_env.py).
import prod_leaf_env  # noqa: E402,F401

import numpy as np  # noqa: E402

import carc_rs  # noqa: E402
import lockstep_fuzz as lf  # noqa: E402
from _g0_common import environment  # noqa: E402
from carcassonne_ai import game_wrapper as gw  # noqa: E402
from carcassonne_ai.action_space import N_ROTATIONS, WindowOverflowError  # noqa: E402
from carcassonne_ai.flat_leaf import flat_base_score  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p5"


# ---------------------------------------------------------------------------
def _state_view(board, d_row: int = 0, d_col: int = 0) -> dict:
    """The shift-equivariant view of a state: every coordinate translated by
    `(d_row, d_col)`, everything else verbatim.  Two states satisfy the even-shift
    property exactly when their views are equal."""
    st = board.state
    placed = []
    for c in sorted(st.placed_coords, key=lambda c: (c.row, c.column)):
        tile = st.board[c.row][c.column]
        placed.append((c.row + d_row, c.column + d_col,
                       tile.description if tile is not None else None,
                       tuple(s.name for s in getattr(tile, "grass", ()) or ())))
    # placed_meeples in LIST INSERTION ORDER (it feeds the repr key), not sorted.
    meeples = [
        [(m.meeple_type.value,
          m.coordinate_with_side.coordinate.row + d_row,
          m.coordinate_with_side.coordinate.column + d_col,
          m.coordinate_with_side.side.value) for m in st.placed_meeples[p]]
        for p in range(len(st.placed_meeples))
    ]
    lta = st.last_tile_action
    return {
        "placed": placed,
        "meeples": meeples,
        "scores": [int(x) for x in st.scores],
        "meeple_counts": [int(x) for x in st.meeples],
        "current_player": st.current_player,
        "phase": st.phase.value,
        "deck_len": len(st.deck),
        "next_tile": None if st.next_tile is None else st.next_tile.description,
        "last_tile": None if lta is None else (lta.coordinate.row + d_row,
                                               lta.coordinate.column + d_col),
        "terminated": bool(st.is_terminated()),
    }


def _open_positions(board, d_row: int = 0, d_col: int = 0) -> set:
    return {(c.row + d_row, c.column + d_col) for c in board.state.open_positions}


def _canon(game, board):
    c = game.get_canonical_form(board, 1)
    return (c[0], c[1]) if isinstance(c, tuple) else (c, None)


# ---------------------------------------------------------------------------
def run_game(job: dict) -> dict:
    """One deck seed through all four engines.  Never raises."""
    seed, pseed, mode = job["deck_seed"], job["policy_seed"], job["mode"]
    d_row, d_col = job["d_row"], job["d_col"]
    rule = job.get("start_rule", "engine")
    base_row, base_col = lf.DEFAULT_START_ROW, lf.DEFAULT_START_COL

    res = {"deck_seed": seed, "policy_seed": pseed, "mode": mode,
           "d_row": d_row, "d_col": d_col, "start_rule": rule,
           "plies": 0, "compared": 0, "status": "ok",
           "wall_denied_plies": 0, "wall_denied_cells": 0,
           "stopped_by": None, "mismatch": None}
    actions: list[int] = []

    def fail(kind, ply, a, b, extra=None):
        res["status"] = "MISMATCH"
        res["mismatch"] = {"kind": kind, "ply": ply, "base": a, "shift": b,
                           "deck_seed": seed, "policy_seed": pseed, "mode": mode,
                           "d_row": d_row, "d_col": d_col,
                           "actions": list(actions), **(extra or {})}

    try:
        import random

        ga, ba, ma = lf.init_pair(seed, rule, base_row, base_col)
        gb, bb, mb = lf.init_pair(seed, rule, base_row + d_row, base_col + d_col)
        gw.drain_window_audit()
        rng = random.Random(pseed)

        while True:
            ply = res["plies"]

            # 1. the port is byte-exact at BOTH rows
            for tag, g, b, m in (("base", ga, ba, ma), ("shift", gb, bb, mb)):
                pr, rr = g.string_representation(b), m.string_repr()
                if pr != rr:
                    fail(f"port_repr[{tag}]", ply, pr, rr)
                    return res

            # 2. the exact documented transform
            va, vb = _state_view(ba, 0, 0), _state_view(bb, -d_row, -d_col)
            if va != vb:
                diff = [k for k in va if va[k] != vb[k]]
                fail("shift_transform", ply,
                     {k: va[k] for k in diff}, {k: vb[k] for k in diff},
                     {"fields": diff})
                return res

            # 2b. `open_positions` is the ONE field the shift legitimately
            # changes, and it changes for exactly one reason: `StateUpdater`
            # bounds-checks before recording a neighbour, so each grid silently
            # drops the candidates that fall off ITS OWN edge (this is the
            # invisible-border mechanism — tests/test_start_tile_grid_bound.py,
            # `test_off_grid_cells_never_enter_open_positions`).  Restricted to
            # the cells both grids can represent, the two sets must be EQUAL.
            oa_set = _open_positions(ba)
            ob_set = _open_positions(bb, -d_row, -d_col)   # back into base coords

            def _on_base(c):
                return 0 <= c[0] < lf.BOARD_ROWS and 0 <= c[1] < lf.BOARD_COLS

            def _on_shift(c):
                return (0 <= c[0] + d_row < lf.BOARD_ROWS
                        and 0 <= c[1] + d_col < lf.BOARD_COLS)

            both = lambda c: _on_base(c) and _on_shift(c)          # noqa: E731
            if sorted(filter(both, oa_set)) != sorted(filter(both, ob_set)):
                fail("open_positions", ply,
                     sorted(c for c in oa_set if both(c) and c not in ob_set),
                     sorted(c for c in ob_set if both(c) and c not in oa_set))
                return res
            denied_base = sorted(c for c in ob_set if not _on_base(c))
            denied_shift = sorted(c for c in oa_set if not _on_shift(c))
            if denied_base or denied_shift:
                res["wall_denied_plies"] = res.get("wall_denied_plies", 0) + 1
                res["wall_denied_cells"] = (res.get("wall_denied_cells", 0)
                                            + len(denied_base) + len(denied_shift))

            # 3. the window translates exactly (no banker's-rounding slip)
            oa, ob = ba.offset, bb.offset
            want = [oa.origin_row + d_row, oa.origin_col + d_col, oa.size]
            got = [ob.origin_row, ob.origin_col, ob.size]
            if want != got:
                fail("window_offset", ply, want, got)
                return res
            if list(ma.window_offset()) != [oa.origin_row, oa.origin_col, oa.size] or \
                    list(mb.window_offset()) != got:
                fail("port_window_offset", ply,
                     [list(ma.window_offset()), list(mb.window_offset())],
                     [[oa.origin_row, oa.origin_col, oa.size], got])
                return res

            # 5. the scorer is translation-invariant.  The FLAT route is the
            # hard equality (all four engines).  The engine route (clone +
            # `count_final_scores`) is checked with error parity: it walks
            # `board[r + 1]` unguarded, so a tile in the last row makes BOTH
            # object engines refuse — see `lf.object_engine_refusal`.
            refusal = None
            for p in (0, 1):
                s = [int(flat_base_score(ba.state, p)), int(flat_base_score(bb.state, p)),
                     ma.flat_base_score_decomp(p), mb.flat_base_score_decomp(p)]
                if len(set(s)) != 1:
                    fail(f"flat_base_score[p{p}]", ply, s[0], s[1:])
                    return res
                for tag, b, m in (("base", ba, ma), ("shift", bb, mb)):
                    try:
                        if int(m.flat_base_score(p)) != s[0]:
                            fail(f"engine_route[{tag}][p{p}]", ply, s[0],
                                 m.flat_base_score(p))
                            return res
                    except BaseException as exc:       # noqa: BLE001
                        py_err = lf.object_engine_refusal(b.state)
                        py_cls = None if py_err is None else py_err.split(":", 1)[0]
                        if py_cls is None or not str(exc).startswith(py_cls + ":"):
                            fail(f"engine_route_error_parity[{tag}]", ply,
                                 py_err or "<python object engine did not raise>",
                                 f"{type(exc).__name__}: {exc}")
                            return res
                        refusal = {"ply": ply, "side": tag, "python_error": py_err,
                                   "rust_error": f"{type(exc).__name__}: {exc}"}
                if refusal is not None:
                    break
            if refusal is not None:
                res["stopped_by"] = "count_final_scores_refusal"
                res["refusal"] = refusal
                break

            res["compared"] += 1
            if ba.state.is_terminated():
                res["stopped_by"] = "terminal"
                break

            # 4a. the encoding is bit-identical
            ta, sa = _canon(ga, ba)
            tb, sb = _canon(gb, bb)
            if not np.array_equal(ta, tb):
                fail("board_tensor", ply, "base", "shift",
                     {"n_diff": int((np.asarray(ta) != np.asarray(tb)).sum())})
                return res
            if (sa is None) != (sb is None):
                fail("scalars_shape", ply, sa is None, sb is None)
                return res
            if sa is not None and not np.array_equal(np.asarray(sa), np.asarray(sb)):
                fail("scalars", ply, np.asarray(sa).tolist(), np.asarray(sb).tolist())
                return res

            # 4b. the legal mask, all four engines.  DIVERGENCE HERE IS THE BUG,
            # not a failure: the base board's 6 rows of headroom deny placements
            # the shifted board offers.  Stop comparing; the games have parted.
            raised = []
            masks = []
            for g, b in ((ga, ba), (gb, bb)):
                try:
                    masks.append(np.asarray(g.get_valid_moves(b), dtype=bool))
                    raised.append(None)
                except WindowOverflowError as exc:
                    masks.append(None)
                    raised.append(f"WindowOverflowError: {exc}")
                except Exception as exc:                      # noqa: BLE001
                    masks.append(None)
                    raised.append(f"{type(exc).__name__}: {exc}")
            gw.drain_window_audit()
            if any(r is not None for r in raised):
                res["stopped_by"] = "engine_refusal"
                res["refusal"] = {"ply": ply, "base": raised[0], "shift": raised[1]}
                break
            if masks[0].tobytes() != masks[1].tobytes():
                res["stopped_by"] = "mask_divergence"
                res["mask_divergence"] = {
                    "ply": ply,
                    "base_legal": int(masks[0].sum()),
                    "shift_legal": int(masks[1].sum()),
                    "min_row_base": min((divmod(int(i), N_ROTATIONS)[0] // ba.offset.size)
                                        + ba.offset.origin_row
                                        for i in np.flatnonzero(masks[0])[:1] or [0]),
                }
                break
            # the port must agree with Python on the mask at BOTH rows
            if ma.legal_mask_bytes() != masks[0].tobytes():
                fail("port_mask[base]", ply, "python", "rust")
                return res
            if mb.legal_mask_bytes() != masks[1].tobytes():
                fail("port_mask[shift]", ply, "python", "rust")
                return res

            legal = np.flatnonzero(masks[0]).tolist()
            if not legal:
                fail("empty_legal_mask", ply, 0, 0)
                return res
            tile_pass = ba.offset.size * ba.offset.size * N_ROTATIONS
            a = int(lf._choose(rng, legal, mode, ba.state.phase.value,
                               ba.offset, tile_pass))
            actions.append(a)
            ba, _ = ga.get_next_state(ba, a)
            bb, _ = gb.get_next_state(bb, a)
            ma.advance(a)
            mb.advance(a)
            gw.drain_window_audit()
            res["plies"] += 1
            if res["plies"] > job["max_plies"]:
                fail("max_plies_exceeded", res["plies"], job["max_plies"], None)
                return res

    except BaseException as exc:                   # noqa: BLE001 — never kill the pool
        res["status"] = "EXCEPTION"
        res["mismatch"] = {"kind": "exception", "ply": res["plies"],
                           "exc_type": type(exc).__name__, "exc": str(exc)[:2000],
                           "traceback": traceback.format_exc()[-4000:],
                           "deck_seed": seed, "actions": list(actions)}
    return res


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--wall-frac", type=float, default=0.2)
    ap.add_argument("--policy-base", type=int, default=6_000_000)
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--d-row", type=int, default=12,
                    help="EVEN row shift; 6 -> 18 restores the headroom")
    ap.add_argument("--d-col", type=int, default=0, help="EVEN column shift")
    ap.add_argument("--start-rule", choices=lf.START_RULES, default="engine")
    ap.add_argument("--tag", default="local")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    # The evenness bar is the point of the exercise — refuse an odd shift here
    # too, with the same message the Rust config gives.
    lf.check_flags(args.start_rule,
                   lf.DEFAULT_START_ROW + args.d_row,
                   lf.DEFAULT_START_COL + args.d_col)

    every = max(1, round(1.0 / args.wall_frac)) if args.wall_frac > 0 else 0
    jobs = [{"deck_seed": lf.FUZZ_SEED_BASE + i,
             "policy_seed": args.policy_base + i,
             "mode": "wall" if (every and (i % every) == every - 1) else "uniform",
             "d_row": args.d_row, "d_col": args.d_col,
             "start_rule": args.start_rule,
             "max_plies": args.max_plies}
            for i in range(args.start, args.start + args.games)]

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else OUTDIR / f"G5_even_shift_{args.tag}.json"

    t0 = time.perf_counter()
    if args.workers > 1:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(args.workers) as pool:
            results = list(pool.imap_unordered(run_game, jobs, chunksize=2))
    else:
        results = [run_game(j) for j in jobs]
    elapsed = time.perf_counter() - t0

    mismatches = [r["mismatch"] for r in results if r["mismatch"] is not None]
    stopped = {}
    for r in results:
        stopped[r["stopped_by"]] = stopped.get(r["stopped_by"], 0) + 1
    compared = sum(r["compared"] for r in results)
    ok = not mismatches
    payload = {
        "gate": "G5/even_shift_property",
        "verdict": "PASS" if ok else "FAIL",
        "env": environment(),
        "args": vars(args),
        "shift": [args.d_row, args.d_col],
        "shift_is_even": [args.d_row % 2 == 0, args.d_col % 2 == 0],
        "per_ply_checks": [
            "python_vs_rust_repr[base]", "python_vs_rust_repr[shift]",
            "shift_transform(placed/meeples/last_tile/scores/deck/next_tile)",
            "open_positions(restricted to cells both grids can represent)",
            "window_offset_translates_exactly", "python_vs_rust_window_offset",
            "flat_base_score[p0,p1] x 4 engines", "board_tensor", "scalars",
            "legal_mask(bytes) python_vs_rust at both rows",
        ],
        "stop_reasons": stopped,
        "wall_denied_plies": sum(r.get("wall_denied_plies", 0) for r in results),
        "wall_denied_cells": sum(r.get("wall_denied_cells", 0) for r in results),
        "games_with_wall_denial": sum(1 for r in results
                                      if r.get("wall_denied_plies", 0)),
        "total_games": len(results),
        "total_positions_compared": compared,
        "mean_plies_compared": compared / max(len(results), 1),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "exception_games": sum(1 for r in results if r["status"] == "EXCEPTION"),
        "wallclock_s": elapsed,
        "per_game": [{k: r[k] for k in ("deck_seed", "mode", "plies", "compared",
                                        "status", "stopped_by", "wall_denied_plies")}
                     for r in results],
    }
    out.write_text(json.dumps(payload, indent=2, default=str))
    print(f"G5/even_shift: {'PASS' if ok else 'FAIL'}  {len(results)} games, "
          f"shift ({args.d_row}, {args.d_col}), rule={args.start_rule}, "
          f"{compared} positions x {len(payload['per_ply_checks'])} checks, "
          f"{len(mismatches)} mismatches, stops={stopped}, "
          f"wall-denied plies {payload['wall_denied_plies']} in "
          f"{payload['games_with_wall_denial']} games, {elapsed:.1f}s")
    print(f"G5/even_shift: result -> {out}")
    for mm in mismatches[:5]:
        print("  MISMATCH", json.dumps(mm, default=str)[:600])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
