"""G1 (open half) — the 10^4-game LOCKSTEP FUZZ.

`reconcile_engine.py` replays the *game record* (golden fixture + 449 champ
games + 2 E4 archives) through both engines.  That corpus is strong but it is
the corpus a strong agent produced: it never visits the pathological geometry.
Two ported quirks are therefore argued-but-unmeasured (DECISIONS 2026-07-31, P1):

  * **`find_roads` non-dedup** — Python `Road` has no `__eq__`/`__hash__`, so
    `set()` keeps one entry per road-typed side.  Argued a no-op; never measured.
  * **the CPython negative-index board wrap** — three direct `board[r][c]` sites
    read row/col `-1`, which CPython wraps to index 34.  Benign *only while the
    far rows stay empty* — a property of the corpus, not of the code.

This script plays fresh random games through **both** engines in lockstep and
compares, at **every ply**:

  1. `Game.string_representation(board)` — byte equality (the MCTS node key);
  2. the legal mask — **byte-for-byte** (strictly stronger than the sha256 the
     record gate compares; the sha256 of both sides is recorded in any
     reproducer);
  3. `(n_total, n_overflow)` — the two counters `Game._compute_mask` builds its
     `WindowOverflowError` conditions from (Python side via
     `CARCASSONNE_WINDOW_AUDIT=1`, Rust side via `MirrorState.mask_counts()`).
     This is the *dropped-legal-action* parity, i.e. direct coverage of the
     window edge;
  4. `state.scores`;
  5. `flat_leaf.flat_base_score(state, p)` for both POVs — the whole
     farm/city/road scorer as a per-ply invariant;
  6. `(current_player, phase, len(deck), is_terminated)`.

**Error parity is part of lockstep identity.**  When every legal action falls
outside the 25x25 centred window, Python's `get_valid_moves` raises
`action_space.WindowOverflowError` (DECISIONS 2026-07-31, Shabbat eve: this
crashed 16/400 eval games deterministically).  The Rust side does not raise —
it reports the same condition through `mask_counts()` — so the fuzz asserts
`python_raised == (n_total > 0 and n_overflow == n_total)` on the SAME ply.
A game that ends that way is a **PASS-with-flag**: counted separately, with a
`(deck_seed, policy_seed, ply)` reproducer written out for the F9 dossier.

The same treatment covers the *other* refusal the fuzz found — the CPython
engine's own `IndexError` out of `FarmUtil.farm_for_position` when a tile is
placed on the last column, so the farm neighbour indexes `board[..][35]` (the
positive-side twin of the negative-index wrap: negatives wrap silently, `>= 35`
raises).  Rust reproduces CPython list indexing by panicking with the same
`IndexError: ...` message, which pyo3 surfaces as `PanicException`; the fuzz
requires the same error class on the same ply, and flags the game.

Policies (both seeded, both sampling only from encodable legal actions — an
action index is the only thing both engines can be driven by):

  uniform  `random.Random(policy_seed).choice(legal)`.
  wall     prefers the LOWEST-ROW legal tile placement (uniform among ties),
           uniform in the meeple phase.  Drives play into the top wall so the
           `board[-1]` wrap sites and the window-overflow class fire far more
           often than under uniform play.

Deck seeds come from the throwaway range **97_000_000_000 + i**, which is NOT a
registered claim band (`governance/BAND_REGISTRY.csv`) — these games are a
correctness fuzz, never an estimate.

**P5 flags (2026-08-01).**  `--start-rule` / `--start-row` / `--start-col` drive
the SAME lockstep through the opt-in rules flags, so the fuzz is reusable as the
G5 flags-on leg instead of being forked:

    --start-rule engine   the vendored default: player 0 draws a random tile
                          which is auto-placed (`Game(fixed_start_tile=False)`).
    --start-rule retail   the retail/tournament fixed "D" start tile, pre-placed
                          before anyone draws (`Game(fixed_start_tile=True)` /
                          `MirrorState.from_seed(..., start_rule="retail")`).
    --start-row / --start-col   move `starting_position` off the engine's
                          (6, 15).  The shift must be EVEN on both axes (see
                          `tests/test_start_tile_grid_bound.py`); the Rust config
                          refuses an odd one and this driver refuses it too.
                          `Game.get_init_board()` hard-codes the engine start, so
                          a shifted Python board is built the way the worktree
                          test does: construct the state with an explicit
                          `starting_position`, optionally pre-place, then
                          `Board.from_state`.

Defaults are unchanged (engine rule, start (6, 15)) — the G1 invocation and its
recorded verdict reproduce byte-for-byte.

Usage:
    .venv/bin/python scripts/rustport/lockstep_fuzz.py --games 10000 \
        --workers 16 --wall-frac 0.2 --tag laptop
    .venv/bin/python scripts/rustport/lockstep_fuzz.py --games 1000 \
        --workers 16 --start-rule retail --tag p5_retail
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
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
# MUST be set before game_wrapper is imported: it latches the flag at import
# time and is what makes the per-decision (n_total, n_overflow) audit available.
os.environ["CARCASSONNE_WINDOW_AUDIT"] = "1"

# ⚠️ BEFORE any carcassonne_ai import — freezes DEFAULT_CONFIG at the production
# leaf SHAPE so a full-tree pytest that collects this module first cannot leave
# the session default bare (see scripts/rustport/prod_leaf_env.py). Inert here:
# the fuzz compares repr/mask/scores/base-score, none of which take a leaf config.
import prod_leaf_env  # noqa: E402,F401

import numpy as np  # noqa: E402

import carc_rs  # noqa: E402
from _g0_common import environment  # noqa: E402
from carcassonne_ai import game_wrapper as gw  # noqa: E402
from carcassonne_ai.action_space import N_ROTATIONS, WindowOverflowError  # noqa: E402
from carcassonne_ai.flat_leaf import flat_base_score  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p1"
FUZZ_SEED_BASE = 97_000_000_000   # throwaway range; NOT a registered band
BOARD_ROWS = BOARD_COLS = 35      # engine grid (walled)

# The engine's `CarcassonneGameState.starting_position` — the P5 flags are
# expressed as (even) shifts away from it.
DEFAULT_START_ROW, DEFAULT_START_COL = 6, 15
START_RULES = ("engine", "retail")


def check_flags(start_rule: str, start_row: int, start_col: int) -> None:
    """Refuse an unknown rule or an ODD shift — the same two refusals the Rust
    `GameConfig::resolve` makes, applied before any game is launched."""
    if start_rule not in START_RULES:
        raise ValueError(
            f"unknown start_rule {start_rule!r}; expected one of {START_RULES}")
    for axis, v, base in (("start_row", start_row, DEFAULT_START_ROW),
                          ("start_col", start_col, DEFAULT_START_COL)):
        if (v - base) % 2 != 0:
            raise ValueError(
                f"{axis} shift must be EVEN: {v} is {v - base} from the engine "
                f"default {base}; banker's rounding in "
                "board_repr.offset_from_centroid_sums is equivariant under even "
                "translations only")
        if not 0 <= v < (BOARD_ROWS if axis == "start_row" else BOARD_COLS):
            raise ValueError(f"{axis} {v} is off the 35x35 board")


def object_engine_refusal(state) -> str | None:
    """Does the Python OBJECT engine refuse to final-score this position?

    `PointsCollector.count_final_scores` is the route the Rust
    `engine::GameState::flat_base_score` mirrors (clone + count).  It indexes
    `board[r + 1]` with no bounds check, so a tile in the LAST ROW raises
    `IndexError` — while `flat_leaf.flat_base_score`, the flat-decomposition
    route, scores the same position without complaint.  Returns the refusal as
    `"Class: message"`, or `None` if it scored.
    """
    import copy

    from wingedsheep.carcassonne.utils.points_collector import PointsCollector
    try:
        PointsCollector.count_final_scores(copy.deepcopy(state))
        return None
    except BaseException as exc:                       # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def init_pair(seed: int, start_rule: str, start_row: int, start_col: int):
    """`(Game, Board, MirrorState)` for one deck seed under the P5 flags.

    The deck comes from `random.seed(deck_seed)` in BOTH branches — the
    `root_replay` contract — so a reproducer replays through the normal tooling
    whatever the flags were.
    """
    fixed = start_rule == "retail"
    game = Game(enable_legal_moves_cache=False, fixed_start_tile=fixed)
    random.seed(int(seed))
    if (start_row, start_col) == (DEFAULT_START_ROW, DEFAULT_START_COL):
        board = game.get_init_board()
    else:
        # `Game.get_init_board` hard-codes the engine's starting_position, so the
        # shifted board is built exactly as tests/test_start_tile_grid_bound.py
        # does: explicit starting_position, optional pre-place, Board.from_state.
        from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
        from wingedsheep.carcassonne.objects.coordinate import Coordinate

        state = CarcassonneGameState(
            players=game.players,
            tile_sets=list(game.tile_sets),
            supplementary_rules=list(game.supplementary_rules),
            board_size=(BOARD_ROWS, BOARD_COLS),
            starting_position=Coordinate(start_row, start_col),
        )
        if fixed:
            gw.preplace_retail_start_tile(state)
        total_tiles = len(state.deck) + 1 + len(state.placed_coords)
        board = gw.Board.from_state(state, total_tiles, game.window_size)
    ms = carc_rs.MirrorState.from_seed(
        str(seed), start_rule=start_rule, start_row=start_row, start_col=start_col)
    return game, board, ms


# ---------------------------------------------------------------------------
def _tile_coord(idx: int, off) -> tuple[int, int]:
    """Engine (row, col) of a TILES-phase placement index (no Action built)."""
    cell, _rot = divmod(idx, N_ROTATIONS)
    wr, wc = divmod(cell, off.size)
    return wr + off.origin_row, wc + off.origin_col


def _choose(rng: random.Random, legal: list[int], mode: str, phase: str, off,
            tile_pass: int) -> int:
    """Seeded policy over the encodable legal actions."""
    if mode != "wall" or phase != "tiles":
        return rng.choice(legal)
    placements = [a for a in legal if a < tile_pass]
    if not placements:
        return rng.choice(legal)
    rows = [_tile_coord(a, off)[0] for a in placements]
    lo = min(rows)
    return rng.choice([a for a, r in zip(placements, rows) if r == lo])


# ---------------------------------------------------------------------------
def fuzz_game(job: dict) -> dict:
    """One game, both engines, in lockstep.  Never raises: every failure mode
    comes back as a result record so the pool cannot die on a divergence."""
    seed, pseed, mode = job["deck_seed"], job["policy_seed"], job["mode"]
    max_plies = job["max_plies"]
    start_rule = job.get("start_rule", "engine")
    start_row = job.get("start_row", DEFAULT_START_ROW)
    start_col = job.get("start_col", DEFAULT_START_COL)

    res = {
        "deck_seed": seed, "policy_seed": pseed, "mode": mode,
        "start_rule": start_rule, "start_row": start_row, "start_col": start_col,
        "plies": 0, "compared": 0, "status": "ok",
        "terminal_scores": None,
        "window_overflow": None,      # {"ply":..., "n_total":...} if it fired
        "engine_error": None,         # matched engine-level refusal (e.g. IndexError)
        "mismatch": None,
        "actions": None,              # only filled on a flag/failure (reproducer)
        # wrap-site instrumentation
        "min_row": None, "min_col": None, "max_row": None, "max_col": None,
        "placements_row0": 0, "placements_col0": 0,
        "placements_row34": 0, "placements_col34": 0,
        "plies_with_dropped_legal": 0, "dropped_legal_total": 0,
        "max_n_overflow_frac": 0.0,
    }
    actions: list[int] = []

    def fail(kind: str, ply: int, py, rs, extra=None):
        res["status"] = "MISMATCH"
        rec = {"kind": kind, "ply": ply, "python": py, "rust": rs,
               "deck_seed": seed, "policy_seed": pseed, "mode": mode,
               "start_rule": start_rule, "start_row": start_row,
               "start_col": start_col,
               "actions": list(actions)}
        if extra:
            rec.update(extra)
        res["mismatch"] = rec
        res["actions"] = list(actions)

    try:
        # cache OFF: every ply audits.  Deck via random.seed(deck_seed).
        game, board, ms = init_pair(seed, start_rule, start_row, start_col)
        gw.drain_window_audit()
        rng = random.Random(pseed)

        # Setup identity, once — the flags land here and nowhere else.
        py_setup = [int(board.total_tiles), int(board.tile_count),
                    [board.state.starting_position.row,
                     board.state.starting_position.column]]
        rs_setup = [ms.total_tiles(), ms.tile_count(), list(ms.starting_position())]
        if py_setup != rs_setup:
            fail("setup", 0, py_setup, rs_setup)
            return res
        if ms.start_rule() != start_rule:
            fail("start_rule", 0, start_rule, ms.start_rule())
            return res

        while True:
            st = board.state
            terminal = st.is_terminated()
            ply = res["plies"]

            # 1. repr — byte equality
            pr, rr = game.string_representation(board), ms.string_repr()
            if pr != rr:
                fail("string_representation", ply, pr, rr)
                return res

            # 4. scores
            py_scores = [int(x) for x in st.scores]
            rs_scores = list(ms.scores())
            if py_scores != rs_scores:
                fail("scores", ply, py_scores, rs_scores)
                return res

            # 5. flat_base_score, both POVs, on BOTH Rust routes:
            #    `flat_base_score_decomp` is the flat decomposition (what the
            #    Python `flat_leaf.flat_base_score` on the left-hand side is),
            #    `flat_base_score` is the engine's own clone +
            #    `count_final_scores`.  The two Rust routes agreeing with the one
            #    Python number is a free cross-check of the decomposition.
            #
            #    ERROR PARITY on the engine route (found 2026-08-01 by the P5
            #    start-row probe): `PointsCollector.count_final_scores` walks
            #    `board[r + 1]` unguarded, so a tile in the LAST ROW makes the
            #    OBJECT engine raise `IndexError` — the row twin of the known
            #    col-34 fatal, and a face the flat leaf does NOT have (it scores
            #    the position fine).  Unreachable from start row 6 (it needs a
            #    28-row span); reachable once `--start-row` moves the board down.
            #    Rust reproduces the refusal; a matched pair is PASS-with-flag.
            engine_route_refusal = None
            for p in (0, 1):
                pb = int(flat_base_score(st, p))
                rd = int(ms.flat_base_score_decomp(p))
                if pb != rd:
                    fail(f"flat_base_score_decomp[p{p}]", ply, pb, rd)
                    return res
                try:
                    rb = int(ms.flat_base_score(p))
                except BaseException as exc:              # noqa: BLE001 — PanicException
                    py_err = object_engine_refusal(st)
                    py_cls = None if py_err is None else py_err.split(":", 1)[0]
                    if py_cls is None or not str(exc).startswith(py_cls + ":"):
                        fail("engine_route_error_parity", ply,
                             py_err or "<python object engine did not raise>",
                             f"{type(exc).__name__}: {exc}")
                        return res
                    engine_route_refusal = {
                        "ply": ply, "error_class": py_cls, "python_error": py_err,
                        "rust_error": f"{type(exc).__name__}: {exc}",
                        "route": "count_final_scores",
                    }
                    break
                if pb != rb:
                    fail(f"flat_base_score[p{p}]", ply, pb, rb)
                    return res
            if engine_route_refusal is not None:
                res["status"] = "engine_error"
                res["engine_error"] = engine_route_refusal
                res["actions"] = list(actions)
                break

            # 6. scalars
            py_sc = [st.current_player, st.phase.value, len(st.deck), bool(terminal)]
            rs_sc = [ms.current_player(), ms.phase(), ms.deck_len(), ms.is_terminal()]
            if py_sc != rs_sc:
                fail("state_scalars", ply, py_sc, rs_sc)
                return res

            # 7. the centred window itself.  Implied by the mask on the engine
            # rule (placements are window-relative), but the retail flag seeds
            # the centroid from a PRE-PLACED tile, so the offset is a first-class
            # observable under P5 and is compared directly.
            py_off = [board.offset.origin_row, board.offset.origin_col, board.offset.size]
            rs_off = list(ms.window_offset())
            if py_off != rs_off:
                fail("window_offset", ply, py_off, rs_off)
                return res

            res["compared"] += 1
            if terminal:
                res["terminal_scores"] = py_scores
                break

            # 2/3. legal mask + the two overflow counters, with ERROR PARITY.
            py_raised = False
            py_engine_exc = None
            mask = None
            try:
                mask = np.asarray(game.get_valid_moves(board), dtype=bool)
            except WindowOverflowError as exc:
                py_raised = True
                py_woe_msg = str(exc)
            except Exception as exc:                      # noqa: BLE001
                # The ENGINE itself refused the position (measured: `IndexError`
                # out of `FarmUtil.farm_for_position` when a tile sits on the last
                # column, so the farm neighbour indexes board[..][35]).  This is
                # the positive-side twin of the negative-index wrap, and it is a
                # lockstep observable like any other: the Rust port must refuse
                # the SAME position with the SAME error class on the SAME ply.
                py_engine_exc = exc
            audit = gw.drain_window_audit()

            if py_engine_exc is not None:
                py_cls = type(py_engine_exc).__name__
                rs_exc = None
                try:
                    ms.mask_counts()
                except BaseException as exc:              # noqa: BLE001 — PanicException
                    rs_exc = exc
                rs_msg = None if rs_exc is None else str(rs_exc)
                # Rust reproduces CPython's list indexing by panicking with the
                # message "IndexError: ..." (carc-core `py_index`), which pyo3
                # surfaces as PanicException.
                if rs_msg is None or not rs_msg.startswith(py_cls + ":"):
                    fail("engine_error_parity", ply,
                         f"{py_cls}: {py_engine_exc}",
                         rs_msg if rs_msg is not None else "<rust did not raise>")
                    return res
                res["status"] = "engine_error"
                res["engine_error"] = {
                    "ply": ply, "phase": st.phase.value, "error_class": py_cls,
                    "python_error": f"{py_cls}: {py_engine_exc}",
                    "rust_error": f"{type(rs_exc).__name__}: {rs_msg}",
                    "last_tile": ([board.state.last_tile_action.coordinate.row,
                                   board.state.last_tile_action.coordinate.column]
                                  if board.state.last_tile_action is not None else None),
                    "extent_rows": [res["min_row"], res["max_row"]],
                    "extent_cols": [res["min_col"], res["max_col"]],
                }
                res["actions"] = list(actions)
                break

            rs_total, rs_over = ms.mask_counts()
            rs_all_overflow = rs_total > 0 and rs_over == rs_total

            if len(audit) != 1:
                fail("window_audit_records", ply, len(audit), 1)
                return res
            py_total, py_over = int(audit[0]["n_total"]), int(audit[0]["n_overflow"])
            if (py_total, py_over) != (rs_total, rs_over):
                fail("mask_counts", ply, [py_total, py_over], [rs_total, rs_over])
                return res
            if py_raised != rs_all_overflow:
                fail("window_overflow_parity", ply,
                     {"python_raised": py_raised},
                     {"rust_all_overflow": rs_all_overflow,
                      "n_total": rs_total, "n_overflow": rs_over})
                return res

            if py_over:
                res["plies_with_dropped_legal"] += 1
                res["dropped_legal_total"] += py_over
                res["max_n_overflow_frac"] = max(res["max_n_overflow_frac"],
                                                 py_over / max(py_total, 1))

            if py_raised:
                # PASS-with-flag: both engines agree the position is unencodable.
                res["status"] = "window_overflow"
                res["window_overflow"] = {
                    "ply": ply, "n_total": py_total, "n_overflow": py_over,
                    "window_origin": [board.offset.origin_row, board.offset.origin_col],
                    "window_size": board.offset.size,
                    "phase": st.phase.value,
                    "python_error": py_woe_msg,
                    "rust_mask_counts": [rs_total, rs_over],
                }
                res["actions"] = list(actions)
                break

            rs_mask = ms.legal_mask_bytes()
            if mask.tobytes() != rs_mask:
                fail("legal_mask", ply,
                     hashlib.sha256(mask.tobytes()).hexdigest(),
                     hashlib.sha256(rs_mask).hexdigest(),
                     {"python_legal": np.flatnonzero(mask).tolist()[:60],
                      "rust_legal": ms.legal_actions()[:60]})
                return res

            legal = np.flatnonzero(mask).tolist()
            if not legal:
                fail("empty_legal_mask", ply, py_total, rs_total)
                return res

            off = board.offset
            tile_pass = off.size * off.size * N_ROTATIONS
            a = int(_choose(rng, legal, mode, st.phase.value, off, tile_pass))

            if st.phase.value == "tiles" and a < tile_pass:
                r, c = _tile_coord(a, off)
                res["min_row"] = r if res["min_row"] is None else min(res["min_row"], r)
                res["max_row"] = r if res["max_row"] is None else max(res["max_row"], r)
                res["min_col"] = c if res["min_col"] is None else min(res["min_col"], c)
                res["max_col"] = c if res["max_col"] is None else max(res["max_col"], c)
                res["placements_row0"] += (r == 0)
                res["placements_col0"] += (c == 0)
                res["placements_row34"] += (r == BOARD_ROWS - 1)
                res["placements_col34"] += (c == BOARD_COLS - 1)

            actions.append(a)
            board, _ = game.get_next_state(board, a)
            ms.advance(a)
            gw.drain_window_audit()   # get_next_state does not audit, but be exact
            res["plies"] += 1
            if res["plies"] > max_plies:
                fail("max_plies_exceeded", res["plies"], max_plies, max_plies)
                return res

    except BaseException as exc:                   # noqa: BLE001 — never kill the pool
        # BaseException, not Exception: a Rust panic arrives as pyo3's
        # PanicException, which does not derive from Exception.
        res["status"] = "EXCEPTION"
        res["mismatch"] = {
            "kind": "exception", "ply": res["plies"],
            "exc_type": type(exc).__name__, "exc": str(exc)[:2000],
            "traceback": traceback.format_exc()[-4000:],
            "deck_seed": seed, "policy_seed": pseed, "mode": mode,
            "actions": list(actions),
        }
        res["actions"] = list(actions)
    return res


# ---------------------------------------------------------------------------
def build_jobs(args) -> list[dict]:
    """Deterministic job list: game i is fully described by its index."""
    jobs = []
    every = max(1, round(1.0 / args.wall_frac)) if args.wall_frac > 0 else 0
    for i in range(args.start, args.start + args.games):
        mode = "wall" if (every and (i % every) == every - 1) else "uniform"
        jobs.append({
            "index": i,
            "deck_seed": FUZZ_SEED_BASE + i,
            "policy_seed": args.policy_base + i,
            "mode": mode,
            "max_plies": args.max_plies,
            "start_rule": args.start_rule,
            "start_row": args.start_row,
            "start_col": args.start_col,
        })
    return jobs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=10000)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--wall-frac", type=float, default=0.2,
                    help="fraction of games played by the wall-biased policy")
    ap.add_argument("--policy-base", type=int, default=5_000_000)
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--tag", default="local")
    ap.add_argument("--out", default=None)
    ap.add_argument("--jsonl", default=None)
    ap.add_argument("--repro-dir", default=None)
    # --- P5 flags (all default to the byte-compatible walled engine) ---
    ap.add_argument("--start-rule", choices=START_RULES, default="engine",
                    help="start-tile convention (default: the vendored engine rule)")
    ap.add_argument("--start-row", type=int, default=DEFAULT_START_ROW,
                    help="starting_position row; the shift from 6 must be EVEN")
    ap.add_argument("--start-col", type=int, default=DEFAULT_START_COL,
                    help="starting_position column; the shift from 15 must be EVEN")
    args = ap.parse_args(argv)
    check_flags(args.start_rule, args.start_row, args.start_col)

    jobs = build_jobs(args)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else OUTDIR / "G1_lockstep_fuzz.json"
    jsonl = Path(args.jsonl) if args.jsonl else OUTDIR / f"G1_lockstep_fuzz_{args.tag}.jsonl"
    repro = Path(args.repro_dir) if args.repro_dir else OUTDIR / "G1_lockstep_reproducers"
    repro.mkdir(parents=True, exist_ok=True)

    def _line(r: dict) -> str:
        # keep the jsonl small: the full action sequence only rides along on a
        # game that is a reproducer (mismatch, exception, or overflow flag).
        rec = r if r["status"] != "ok" else {k: v for k, v in r.items() if k != "actions"}
        return json.dumps(rec, default=str) + "\n"

    t0 = time.perf_counter()
    results: list[dict] = []
    with jsonl.open("w") as fh:
        if args.workers > 1:
            import multiprocessing as mp

            with mp.get_context("spawn").Pool(args.workers) as pool:
                for r in pool.imap_unordered(fuzz_game, jobs, chunksize=4):
                    results.append(r)
                    fh.write(_line(r))
        else:
            for j in jobs:
                r = fuzz_game(j)
                results.append(r)
                fh.write(_line(r))
    elapsed = time.perf_counter() - t0

    by_mode: dict[str, dict] = {}
    mismatches, overflows, engine_errors = [], [], []
    for r in results:
        m = by_mode.setdefault(r["mode"], {
            "games": 0, "plies": 0, "positions_compared": 0, "mismatches": 0,
            "window_overflow_games": 0, "engine_error_games": 0,
            "games_touching_row0": 0,
            "games_touching_col0": 0, "games_touching_row34": 0,
            "games_touching_col34": 0, "placements_row0": 0, "placements_col0": 0,
            "plies_with_dropped_legal": 0, "dropped_legal_total": 0,
            "min_row_seen": None, "min_col_seen": None,
            "max_row_seen": None, "max_col_seen": None,
        })
        m["games"] += 1
        m["plies"] += r["plies"]
        m["positions_compared"] += r["compared"]
        m["placements_row0"] += r["placements_row0"]
        m["placements_col0"] += r["placements_col0"]
        m["plies_with_dropped_legal"] += r["plies_with_dropped_legal"]
        m["dropped_legal_total"] += r["dropped_legal_total"]
        m["games_touching_row0"] += bool(r["placements_row0"])
        m["games_touching_col0"] += bool(r["placements_col0"])
        m["games_touching_row34"] += bool(r["placements_row34"])
        m["games_touching_col34"] += bool(r["placements_col34"])
        for key, cur, better in (("min_row_seen", r["min_row"], min),
                                 ("min_col_seen", r["min_col"], min),
                                 ("max_row_seen", r["max_row"], max),
                                 ("max_col_seen", r["max_col"], max)):
            if cur is not None:
                m[key] = cur if m[key] is None else better(m[key], cur)
        if r["mismatch"] is not None:
            m["mismatches"] += 1
            mismatches.append(r["mismatch"])
        if r["status"] == "window_overflow":
            m["window_overflow_games"] += 1
            overflows.append({"deck_seed": r["deck_seed"],
                              "policy_seed": r["policy_seed"],
                              "mode": r["mode"], **r["window_overflow"]})
        if r["status"] == "engine_error":
            m["engine_error_games"] += 1
            engine_errors.append({"deck_seed": r["deck_seed"],
                                  "policy_seed": r["policy_seed"],
                                  "mode": r["mode"], **r["engine_error"]})

    for i, mm in enumerate(mismatches):
        (repro / f"mismatch_{mm['deck_seed']}_{mm.get('policy_seed')}_{i}.json"
         ).write_text(json.dumps(mm, indent=2, default=str))
    for r in results:
        for kind, key in (("window_overflow", "window_overflow"),
                          ("engine_error", "engine_error")):
            if r["status"] == kind:
                (repro / f"{kind}_{r['deck_seed']}_{r['policy_seed']}.json"
                 ).write_text(json.dumps(
                     {"deck_seed": r["deck_seed"], "policy_seed": r["policy_seed"],
                      "mode": r["mode"], "ply": r[key]["ply"],
                      "detail": r[key], "actions": r["actions"]},
                     indent=2, default=str))

    total_plies = sum(m["plies"] for m in by_mode.values())
    total_pos = sum(m["positions_compared"] for m in by_mode.values())
    ok = not mismatches
    payload = {
        "gate": "G1/lockstep_fuzz",
        "verdict": "PASS" if ok else "FAIL",
        "env": environment(),
        "args": vars(args),
        "deck_seed_range": [FUZZ_SEED_BASE + args.start,
                            FUZZ_SEED_BASE + args.start + args.games - 1],
        "deck_seed_band_note": ("throwaway fuzz-only range 97e9+i — NOT a registered "
                                "claim band (governance/BAND_REGISTRY.csv); these games "
                                "are a correctness fuzz, never an estimate"),
        "flags": {"start_rule": args.start_rule, "start_row": args.start_row,
                  "start_col": args.start_col,
                  "default_semantics": (args.start_rule == "engine"
                                        and args.start_row == DEFAULT_START_ROW
                                        and args.start_col == DEFAULT_START_COL)},
        "per_ply_checks": ["string_representation(bytes)", "legal_mask(bytes)",
                           "mask_counts(n_total,n_overflow)", "scores",
                           "flat_base_score[p0]", "flat_base_score[p1]",
                           "flat_base_score_decomp[p0]", "flat_base_score_decomp[p1]",
                           "state_scalars", "window_offset",
                           "window_overflow_error_parity",
                           "count_final_scores_error_parity"],
        "setup_checks": ["total_tiles", "tile_count", "starting_position",
                         "start_rule"],
        "per_mode": by_mode,
        "total_games": len(results),
        "total_plies": total_plies,
        "total_positions_compared": total_pos,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "window_overflow_games": len(overflows),
        "window_overflow_reproducers": overflows[:200],
        "engine_error_games": len(engine_errors),
        "engine_error_reproducers": engine_errors[:200],
        "matched_error_games": len(overflows) + len(engine_errors),
        "exception_games": sum(1 for r in results if r["status"] == "EXCEPTION"),
        "wallclock_s": elapsed,
        "games_per_s": len(results) / elapsed if elapsed else None,
        "plies_per_s_wall": total_plies / elapsed if elapsed else None,
        "jsonl": str(jsonl),
        "reproducer_dir": str(repro),
    }
    out.write_text(json.dumps(payload, indent=2, default=str))

    for name, m in sorted(by_mode.items()):
        print(f"G1/fuzz[{name}]: {m['games']} games, {m['plies']} plies, "
              f"{m['positions_compared']} positions, {m['mismatches']} mismatches, "
              f"{m['window_overflow_games']} window-overflow games, "
              f"{m['engine_error_games']} matched engine-error games, "
              f"row0-touching games {m['games_touching_row0']}, "
              f"col0-touching {m['games_touching_col0']}, "
              f"rows [{m['min_row_seen']}, {m['max_row_seen']}], "
              f"cols [{m['min_col_seen']}, {m['max_col_seen']}], "
              f"dropped-legal plies {m['plies_with_dropped_legal']}")
    print(f"G1/fuzz: {'PASS' if ok else 'FAIL'}  {len(results)} games, "
          f"{total_pos} positions x {len(payload['per_ply_checks'])} checks, "
          f"{len(mismatches)} mismatches, {len(overflows)} window-overflow + "
          f"{len(engine_errors)} engine-error (matched, PASS-with-flag), {elapsed:.1f}s "
          f"({payload['plies_per_s_wall'] or 0:.0f} plies/s wall)")
    print(f"G1/fuzz: result -> {out}")
    for mm in mismatches[:5]:
        print("  MISMATCH", json.dumps(mm, default=str)[:600])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
