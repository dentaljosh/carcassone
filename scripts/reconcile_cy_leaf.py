#!/usr/bin/env python3
"""Bit-exact equivalence gate for the Cython flat-leaf port (2026-06-12).

NON-NEGOTIABLE before trusting `flat_leaf.USE_CY_LEAF`. Mirrors
scripts/reconcile_compact_leaf.py: play N seeded random games, snapshot states
across every depth, and require EXACT int equality between the Python
reference (`flat_leaf.flat_virtual_score_v2` — what production runs under
CARCASSONNE_USE_FLAT_LEAF=1) and the compiled port
(`flat_leaf_cy.flat_virtual_score_v2_cy`), for BOTH players at EVERY position.

Unlike the compact-leaf gate there is no float-order escape hatch here: the
flat reference already uses the order-independent math.fsum (canonical
semantics), and the port reproduces the same contribution multiset + fsum —
so the acceptance bar is 0 int mismatches, full stop.

Checks:
  1. LEAF INT — flat_virtual_score_v2 (py) == flat_virtual_score_v2_cy, per
     player, per config. Configs: the env-built DEFAULT_CONFIG (run under
     production knobs: CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1)
     plus two off-production configs (pre-v2.7 schedule w/ 3-open; one-open +
     asymmetric caps + meeple_k) to catch config-dependent divergence.
  2. BASE INT — flat_base_score (py) == flat_base_score_cy (pure-int path).
  3. STRUCTURE (diagnostic, every --structs-every states) — the exported C
     decomposition equals flat_leaf.decompose field-for-field (root ids are
     bit-identical by construction: same enumeration + union order).
  4. WIRING — flipping flat_leaf.USE_CY_LEAF at runtime actually routes
     flat_virtual_score_v2 through the compiled port (lazy bind fires) and
     returns identical values.

Usage (production knobs):
  CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 \
    python scripts/reconcile_cy_leaf.py --n 400 --snap-every 1
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import flat_leaf_cy  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, LeafConfig  # noqa: E402

# Off-production configs (robustness): pre-v2.7 schedule incl. 3-open, and a
# deliberately weird one (one-open only, asymmetric caps, meeple_k ON) to
# exercise every cfg-dependent branch of the port.
CFG_Pre27 = LeafConfig(closure_p={1: 0.5, 2: 0.2, 3: 0.05}, bonus_cap=5.0, opp_bonus_cap=5.0)
CFG_Weird = LeafConfig(closure_p={1: 1.0}, bonus_cap=3.0, opp_bonus_cap=7.5, meeple_k=0.35)

STRUCT_FIELDS = [
    ("city_side_root", "city_side_root"),
    ("city_root_finished", "city_root_finished"),
    ("city_root_open_n", "city_root_open_n"),
    ("city_root_delta", "city_root_delta"),
    ("road_side_root", "road_side_root"),
    ("road_root_finished", "road_root_finished"),
    ("farm_pos0_root", "farm_pos0_root"),
    ("farm_anypos_root", "farm_anypos_root"),
    ("farm_root_adj_city_roots", "farm_root_adj_city_roots"),
    ("farm_root_finished_cities", "farm_root_finished_cities"),
]


def collect_states(game: Game, seed: int, snap_every: int, max_plies: int = 400):
    """Random-legal play; snapshot live states across depth + the terminal.
    (Same sampling as reconcile_compact_leaf.collect_states.)"""
    random.seed(seed)
    board = game.get_init_board()
    states = []
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        action = int(random.choice(legal.tolist()))
        board, _ = game.get_next_state(board, action)
        plies += 1
        if plies % snap_every == 0 and game.get_game_ended(board, 0) == 0.0:
            states.append(board.state)
    states.append(board.state)
    return [s for s in states if s.players == 2]


def check_wiring(state) -> tuple[bool, bool]:
    """Flip flat_leaf.USE_CY_LEAF at runtime; verify the lazy bind fires and
    the routed value matches the direct py + direct cy values."""
    saved = flat_leaf.USE_CY_LEAF
    try:
        flat_leaf.USE_CY_LEAF = False
        py = flat_leaf.flat_virtual_score_v2(state, 0, DEFAULT_CONFIG)
        flat_leaf.USE_CY_LEAF = True
        routed = flat_leaf.flat_virtual_score_v2(state, 0, DEFAULT_CONFIG)
    finally:
        flat_leaf.USE_CY_LEAF = saved
    bound = flat_leaf._CY_FLAT_V2 is not None
    return bound, routed == py


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="games to play")
    ap.add_argument("--snap-every", type=int, default=1, help="snapshot cadence (plies)")
    ap.add_argument("--seed", type=int, default=24680)
    ap.add_argument(
        "--structs-every", type=int, default=25,
        help="full Decomp structure compare every K states (diagnostic)",
    )
    ap.add_argument(
        "--skip-offprod", action="store_true",
        help="only check the env-built DEFAULT_CONFIG (faster)",
    )
    args = ap.parse_args()

    print(
        f"env: CAP={os.environ.get('CARCASSONNE_V25_CAP')} "
        f"DROP_THREE_OPEN={os.environ.get('CARCASSONNE_V25_DROP_THREE_OPEN')}"
    )
    print(
        f"DEFAULT_CONFIG: closure_p={DEFAULT_CONFIG.closure_p} "
        f"bonus_cap={DEFAULT_CONFIG.bonus_cap} opp_cap={DEFAULT_CONFIG.opp_bonus_cap} "
        f"meeple_k={DEFAULT_CONFIG.meeple_k}"
    )
    if DEFAULT_CONFIG.bonus_cap != 12.0 or 2 not in DEFAULT_CONFIG.closure_p or 3 in DEFAULT_CONFIG.closure_p:
        print("WARN: DEFAULT_CONFIG is NOT the production v2.7 (CAP=12, drop-3-open). "
              "Set CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 for the verdict run.")

    configs = [("prod-default", DEFAULT_CONFIG)]
    if not args.skip_offprod:
        configs += [("pre-v2.7", CFG_Pre27), ("weird", CFG_Weird)]

    game = Game()
    states_seen = 0
    v2_checks = 0
    v2_mism = 0
    mism_by_cfg = {name: 0 for name, _ in configs}
    base_checks = base_mism = 0
    struct_checks = struct_mism = 0
    first_fail = None

    for g in range(args.n):
        states = collect_states(game, args.seed + g, args.snap_every)
        for state in states:
            states_seen += 1
            for p in range(2):
                for name, cfg in configs:
                    py = flat_leaf.flat_virtual_score_v2(state, p, cfg)
                    cy = flat_leaf_cy.flat_virtual_score_v2_cy(state, p, cfg)
                    v2_checks += 1
                    if py != cy:
                        v2_mism += 1
                        mism_by_cfg[name] += 1
                        if first_fail is None:
                            first_fail = (
                                f"LEAF game_seed={args.seed + g} p={p} cfg={name}: "
                                f"py={py} cy={cy}"
                            )
                base_checks += 1
                bpy = flat_leaf.flat_base_score(state, p)
                bcy = flat_leaf_cy.flat_base_score_cy(state, p)
                if bpy != bcy:
                    base_mism += 1
                    if first_fail is None:
                        first_fail = f"BASE game_seed={args.seed + g} p={p}: py={bpy} cy={bcy}"
            if states_seen % args.structs_every == 0:
                struct_checks += 1
                d_py = flat_leaf.decompose(state)
                d_cy = flat_leaf_cy.decompose_export(state)
                for py_f, cy_f in STRUCT_FIELDS:
                    if getattr(d_py, py_f) != d_cy[cy_f]:
                        struct_mism += 1
                        if first_fail is None:
                            first_fail = f"STRUCT field {py_f} differs (state #{states_seen})"
                        break
        if (g + 1) % max(1, args.n // 10) == 0:
            print(
                f"  [{g + 1}/{args.n}] states={states_seen} v2_checks={v2_checks} "
                f"mism={v2_mism} base_mism={base_mism} struct_mism={struct_mism}",
                flush=True,
            )

    # wiring check on the last state
    bound, routed_ok = check_wiring(states[-1])

    print("\n=== reconcile_cy_leaf summary ===")
    print(f"games                  : {args.n} (seed {args.seed}, snap-every {args.snap_every})")
    print(f"states evaluated       : {states_seen}")
    print(f"leaf int checks        : {v2_checks:>8}   mismatches: {v2_mism}")
    for name, _ in configs:
        print(f"  cfg {name:<14}: mismatches {mism_by_cfg[name]}")
    print(f"base int checks        : {base_checks:>8}   mismatches: {base_mism}")
    print(f"structure compares     : {struct_checks:>8}   mismatches: {struct_mism}")
    print(f"wiring (USE_CY_LEAF)   : bound={bound} routed_value_ok={routed_ok}")

    if first_fail is not None:
        print(f"\nFIRST FAILURE: {first_fail}")
    if v2_mism or base_mism:
        print("\nFAIL: Cython port is NOT bit-exact against the Python flat leaf.")
        return 1
    if struct_mism:
        print("\nFAIL: decomposition structure diverges (scores matched — investigate).")
        return 1
    if not (bound and routed_ok):
        print("\nFAIL: USE_CY_LEAF wiring did not route through the compiled port.")
        return 1
    if v2_checks < 10000:
        print(f"\nWARN: only {v2_checks} leaf checks (<10k); re-run larger for the verdict.")
    print(
        f"\nPASS (BIT-EXACT): cy == py across {v2_checks} leaf evals "
        f"({states_seen} states x 2 players x {len(configs)} cfgs), "
        f"{base_checks} base evals, {struct_checks} structure compares, wiring OK."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
