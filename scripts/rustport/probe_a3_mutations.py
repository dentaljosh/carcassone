"""F9 **A3** quirk-mutation probe — are the redraw gates informative?

A gate that cannot go red is not a gate.  P1, P3 and P4 each ran this
(`probe_fair_mutations.py` is the template); A3's gates are new, so they owe the
same evidence.  Every mutation here is a one-line regression of a documented A3
resolution, applied by **runtime monkeypatch to the Python side only** — nothing
is rebuilt and no debug switch leaks into the shipped engine.

The mutations, each undoing one thing the flag decided:

  ignore_the_flag        the TILES-phase pass hands the turn over even under
                         `draw_rule="redraw"` — i.e. the divergence is not fixed
                         at all.  This is the "did we wire it to anything" probe.
  no_remarginalize       `endgame_solver._drew_a_tile` reverts to `was_meeples`
                         only, so the replacement draw is NOT re-marginalized and
                         the exact solver's value becomes a function of residual
                         DECK ORDER — unsound against its sorted-bag TT key
                         (sub-decision 2).
  no_total_tiles_decr    `game_wrapper._next_total_tiles` becomes the identity,
                         so `total_tiles - tile_count` drifts away from
                         `len(deck) + has_next` by the set-aside count.
  tile_returns_to_bag    the set-aside tile is appended back to the deck instead
                         of leaving the game — the exact opposite of the
                         resolution, and the one that silently breaks the bag.
  no_recursion           only the FIRST unplaceable tile of a turn is redrawn;
                         a still-unplaceable replacement hands the turn over.

The gates they are probed against:

  parity        tiles placed per seat differ by at most 1 under `redraw`
  bag           `len(deck) + has_next == total_tiles - tile_count` (TILES phase)
  conservation  board + bag + hand + set-aside is constant per tile kind
  solver_order  the marginalized exact-K value is invariant to residual deck
                order
  lockstep      python vs `carc_rs` agree per ply (repr / mask / scores /
                set_aside / total_tiles)

Usage:
    .venv/bin/python scripts/rustport/probe_a3_mutations.py --games 24
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "level2",
           REPO / "scripts" / "rustport", REPO / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

import carc_rs  # noqa: E402
from carcassonne_ai import game_wrapper as gw  # noqa: E402
from carcassonne_ai.game_wrapper import DRAW_RULE_REDRAW, Board, Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.utils.state_updater import StateUpdater  # noqa: E402

import endgame_solver  # noqa: E402
from test_unplaceable_redraw import (  # noqa: E402
    _forced_unplaceable_exact_k,
    _reverse_residual_deck,
    play_random,
)

OUTDIR = REPO / "measurement" / "f9_a3"
SEED_BASE = 90_000
POLICY_BASE = 500_000

# Seed OFFSETS whose uniform-random game sets at least one tile aside, enumerated
# once over offsets 0..219 (14 hits — a 6.4% game rate, consistent with the
# audit's 7.0% +/- 3.6%).  The gates iterate THESE rather than a dense range:
# a dense range spends ~93% of its wallclock on games that exercise nothing, and
# an earlier version of this probe reported every gate "blind" purely because
# `--games 24` never reached the first hit at offset 40.
REDRAW_OFFSETS = (40, 70, 78, 86, 87, 92, 95, 99, 104, 110, 112, 175, 181, 206)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _patched(obj, name, new):
    old = getattr(obj, name)
    setattr(obj, name, new)
    try:
        yield
    finally:
        setattr(obj, name, old)


@contextlib.contextmanager
def mut_ignore_the_flag():
    orig = StateUpdater._apply_action_to.__func__

    def mutated(cls, target, original_phase, action):
        flag = target.redraw_unplaceable
        target.redraw_unplaceable = False          # <- the regression
        try:
            return orig(cls, target, original_phase, action)
        finally:
            target.redraw_unplaceable = flag

    with _patched(StateUpdater, "_apply_action_to", classmethod(mutated)):
        yield


@contextlib.contextmanager
def mut_no_remarginalize():
    with _patched(endgame_solver, "_drew_a_tile",
                  lambda board, nb, was_meeples: was_meeples):
        yield


@contextlib.contextmanager
def mut_no_total_tiles_decr():
    with _patched(gw, "_next_total_tiles",
                  lambda total_tiles, state, n_before: total_tiles):
        yield


@contextlib.contextmanager
def mut_tile_returns_to_bag():
    orig = StateUpdater._apply_action_to.__func__

    def mutated(cls, target, original_phase, action):
        before = len(target.set_aside_tiles)
        out = orig(cls, target, original_phase, action)
        if len(target.set_aside_tiles) > before:
            for t in target.set_aside_tiles[before:]:
                target.deck.append(t)              # <- the regression
        return out

    with _patched(StateUpdater, "_apply_action_to", classmethod(mutated)):
        yield


@contextlib.contextmanager
def mut_no_recursion():
    orig = StateUpdater._apply_action_to.__func__

    def mutated(cls, target, original_phase, action):
        # Only the FIRST set-aside of a turn keeps the turn; a second one in a
        # row hands it over (i.e. the loop is capped at one redraw).
        repeat = bool(target.set_aside_tiles) and target.phase == GamePhase.TILES
        flag = target.redraw_unplaceable
        if repeat:
            target.redraw_unplaceable = False
        try:
            return orig(cls, target, original_phase, action)
        finally:
            target.redraw_unplaceable = flag

    with _patched(StateUpdater, "_apply_action_to", classmethod(mutated)):
        yield


MUTATIONS = {
    "ignore_the_flag": mut_ignore_the_flag,
    "no_remarginalize": mut_no_remarginalize,
    "no_total_tiles_decr": mut_no_total_tiles_decr,
    "tile_returns_to_bag": mut_tile_returns_to_bag,
    "no_recursion": mut_no_recursion,
}


# ---------------------------------------------------------------------------
# Gates — each returns (violations, checked)
# ---------------------------------------------------------------------------

def gate_parity(n_games: int):
    game = Game(draw_rule=DRAW_RULE_REDRAW)
    bad = checked = 0
    for i in REDRAW_OFFSETS[:n_games]:
        board, seats = play_random(game, SEED_BASE + i, POLICY_BASE + i)
        if not board.state.set_aside_tiles:
            continue
        checked += 1
        if abs(seats[0] - seats[1]) > 1:
            bad += 1
    return bad, checked


def gate_bag(n_games: int):
    game = Game(draw_rule=DRAW_RULE_REDRAW)
    bad = checked = 0
    for i in REDRAW_OFFSETS[:n_games]:
        random.seed(SEED_BASE + i)
        board = game.get_init_board()
        rng = random.Random(POLICY_BASE + i)
        hit = False
        while not board.state.is_terminated():
            st = board.state
            if st.phase == GamePhase.TILES and st.set_aside_tiles:
                hit = True
                k_deck = len(st.deck) + (1 if st.next_tile is not None else 0)
                if k_deck != int(board.total_tiles) - int(board.tile_count):
                    bad += 1
                    break
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        checked += hit
    return bad, checked


def gate_conservation(n_games: int):
    from collections import Counter

    game = Game(draw_rule=DRAW_RULE_REDRAW)
    bad = checked = 0
    for i in REDRAW_OFFSETS[:n_games]:
        random.seed(SEED_BASE + i)
        board = game.get_init_board()
        n0 = len(board.state.deck) + 1
        rng = random.Random(POLICY_BASE + i)
        hit = broke = False
        while not board.state.is_terminated():
            st = board.state
            if st.phase == GamePhase.TILES:
                if st.set_aside_tiles:
                    hit = True
                total = Counter(t.description for t in st.deck)
                total.update(t.description for t in st.set_aside_tiles)
                if st.next_tile is not None:
                    total.update([st.next_tile.description])
                if sum(total.values()) + len(st.placed_coords) != n0:
                    broke = True
                    break
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        checked += hit
        bad += broke and hit
    return bad, checked


def gate_solver_order(_n_games: int):
    """Marginalized exact-K value must not depend on residual DECK ORDER.

    Several constructed positions, not one: whether a given forced-pass position
    can even EXPRESS order-dependence depends on the two residual tiles leading
    to different final scores, which they often do not on a 2-tile endgame. One
    position made this gate blind to `no_remarginalize`; a handful does not.
    """
    game = Game(draw_rule=DRAW_RULE_REDRAW)
    bad = checked = 0
    for start in range(0, 30, 3):
        built = _forced_unplaceable_exact_k(game, k=3, scan_from=start,
                                            distinct_residual=True)
        if built is None:
            continue
        board, _name = built
        checked += 1
        r1 = endgame_solver.solve(game, board, mode="marginalized", budget=2_000_000)
        swapped = Board(state=_reverse_residual_deck(board),
                        total_tiles=board.total_tiles, offset=board.offset,
                        sum_row=board.sum_row, sum_col=board.sum_col,
                        tile_count=board.tile_count)
        r2 = endgame_solver.solve(game, swapped, mode="marginalized",
                                  budget=2_000_000)
        bad += int(abs(r1.value - r2.value) > 1e-9)
    return bad, checked


def gate_lockstep(n_games: int):
    bad = checked = 0
    for i in REDRAW_OFFSETS[:n_games]:
        seed = SEED_BASE + i
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(seed)
        board = game.get_init_board()
        ms = carc_rs.MirrorState.from_seed(str(seed), draw_rule="redraw")
        rng = random.Random(POLICY_BASE + i)
        hit = broke = False
        while not board.state.is_terminated():
            st = board.state
            if st.set_aside_tiles:
                hit = True
            if (game.string_representation(board) != ms.string_repr()
                    or [int(x) for x in st.scores] != list(ms.scores())
                    or [t.description for t in st.set_aside_tiles] != ms.set_aside_tiles()
                    or int(board.total_tiles) != ms.total_tiles()):
                broke = True
                break
            legal = np.flatnonzero(game.get_valid_moves(board))
            a = int(rng.choice(legal))
            board, _ = game.get_next_state(board, a)
            ms.advance(a)
        checked += hit
        bad += broke and hit
    return bad, checked


GATES = {
    "parity": gate_parity,
    "bag": gate_bag,
    "conservation": gate_conservation,
    "solver_order": gate_solver_order,
    "lockstep": gate_lockstep,
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=len(REDRAW_OFFSETS),
                    help="how many of the pinned redraw-hitting seeds to use")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    t0 = time.time()
    rows = {}
    print("control (no mutation):")
    control = {}
    for gname, gfn in GATES.items():
        bad, checked = gfn(args.games)
        control[gname] = {"violations": bad, "checked": checked}
        print(f"  {gname:14s} {bad} violations / {checked} checked")
    if any(v["violations"] for v in control.values()):
        print("  !! CONTROL IS NOT CLEAN — the probe cannot discriminate")

    for mname, mfn in MUTATIONS.items():
        row = {}
        with mfn():
            for gname, gfn in GATES.items():
                try:
                    bad, checked = gfn(args.games)
                except BaseException as exc:              # noqa: BLE001
                    # A mutation that makes a gate CRASH is discriminated too.
                    row[gname] = {"violations": -1, "checked": 0,
                                  "error": f"{type(exc).__name__}: {exc}"[:200]}
                    continue
                row[gname] = {"violations": bad, "checked": checked}
        rows[mname] = row
        red = [g for g, r in row.items() if r["violations"] != 0]
        print(f"{mname:22s} RED on: {', '.join(red) if red else '<NOTHING — gate is blind>'}")

    n_disc = sum(1 for r in rows.values()
                 if any(x["violations"] != 0 for x in r.values()))
    out = {
        "gate": "F9/A3 mutation probe",
        "verdict": "PASS" if n_disc == len(MUTATIONS) else "FAIL",
        "games_per_gate": args.games,
        "control": control,
        "mutations": rows,
        "discriminated": f"{n_disc}/{len(MUTATIONS)}",
        "wallclock_s": round(time.time() - t0, 1),
    }
    path = Path(args.out) if args.out else OUTDIR / "A3_mutation_probe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {n_disc}/{len(MUTATIONS)} mutations discriminated "
          f"({out['wallclock_s']}s) -> {path}")
    return 0 if out["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
