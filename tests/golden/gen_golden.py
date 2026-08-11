#!/usr/bin/env python3
"""Regenerate the STANDING GOLDEN CORRECTNESS FIXTURE (tests/golden/golden_fixture.json).

Phase 0.4 of the post-review program. Freezes the *currently-correct* computed values
(engine final scores, the flat base leaf, the v2.7/v2.8/v2.9 virtual_score_v2 leaves,
K<=2 exact-solver values, legal-move masks) at a spread of seed-driven positions so any
future drift in the leaf / engine / solver / action-space trips `test_golden.py`.

Provenance is seed-driven (no fixture-image files): each position is
`(deck_seed, action_sequence, ply)`, losslessly reconstructable via
`root_replay.replay_actions` (the engine consumes the global RNG ONLY in
`get_init_board`'s deck shuffle). Leaf values are frozen under CANONICAL_BONUS_SUM
(see _golden_common.leaf_canon) so the frozen ints are reproducible.

Run:  nice -n 19 .venv/bin/python tests/golden/gen_golden.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _golden_common as C  # noqa: E402  (sets env + sys.path before carcassonne import)

import json  # noqa: E402
import random  # noqa: E402

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
import endgame_solver as S  # noqa: E402

np = C.np

# (k, n_seeds) snapshot plan -> ~50 positions. k<=2 get an exact-solver value.
# k=1 solves are trivial (~0.1s, no hidden future); a k=2 MARGINALIZED solve is cheap
# in NODES (~2800) but ~3-10s in TIME (deepcopy-heavy chance marginalization), so we
# keep only a few — and NO k>=3 solve (those churn for minutes).
PLAN = [(1, 12), (2, 2), (6, 10), (14, 10), (26, 10), (40, 6)]


def _solve_maybe(game, board):
    try:
        r = S.solve(game, board, mode="marginalized", budget=C.SOLVER_BUDGET, alphabeta=False)
    except S.BudgetExceeded:
        return None
    return {"value": float(r.value),
            "optimal_actions": sorted(int(a) for a in r.optimal_actions),
            "nodes": int(r.nodes)}


def _leaf_triple(state):
    """(v27, v28, v29) P0-POV canonical leaf diffs at a state."""
    return (C.leaf_canon(state, 0, C.CFG_V27),
            C.leaf_canon(state, 0, C.CFG_V28),
            C.leaf_canon(state, 0, C.CFG_V29))


def play_and_snapshot(seed: int, targets: set[int]):
    """Play one full deterministic game; capture the first TILES ply at each target k,
    AND the first TILES ply where the three leaf configs all disagree (v27!=v28!=v29 —
    the asymmetric-meeple regime that DISCRIMINATES the v2.8 meeple-liquidity term and
    the v2.9 meeple curve; most random-play positions have symmetric meeple counts so the
    liquidity DIFFERENTIAL cancels and the configs coincide — a golden position that
    coincides can't catch a v2.8/v2.9 regression)."""
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    b = game.get_init_board()
    mover_rng = random.Random(seed ^ C.MOVER_XOR)
    actions: list[int] = []
    snaps: dict[int, tuple[int, object]] = {}
    disc: tuple[int, object] | None = None
    remaining = set(targets)
    while game.get_game_ended(b, 0) == 0.0:
        if b.state.phase == GamePhase.TILES:
            kk = C.k_remaining(b.state)
            if remaining and kk in remaining:
                snaps[kk] = (len(actions), b)   # b is stable (get_next_state is non-mutating)
                remaining.discard(kk)
            if disc is None:
                v27, v28, v29 = _leaf_triple(b.state)
                if v27 != v28 and v28 != v29:   # all three genuinely distinct
                    disc = (len(actions), b)
        legal = np.flatnonzero(game.get_valid_moves(b))
        a = int(mover_rng.choice(legal))
        actions.append(a)
        b, _ = game.get_next_state(b, a)
    term = [int(b.state.scores[0]), int(b.state.scores[1])]
    final_diff = int(C.flat_base_score(b.state, 0))
    if remaining:
        raise RuntimeError(f"seed {seed} never reached k in {sorted(remaining)}")
    return actions, len(actions), term, final_diff, snaps, disc


def build_position(pos_id: int, seed: int, k: int, ply: int, game, board,
                   kind: str | None = None) -> dict:
    st = board.state
    entry = {
        "id": pos_id, "seed": seed, "deck_seed": seed, "k": k, "ply": ply,
        "kind": kind or ("endgame" if k <= 2 else "midgame"),
        "phase": st.phase.value,
        "current_player": int(st.current_player),
        "flat_base_score": [int(C.flat_base_score(st, 0)), int(C.flat_base_score(st, 1))],
        "vs": {n: [C.leaf_canon(st, 0, cfg), C.leaf_canon(st, 1, cfg)] for n, cfg in C.CFGS.items()},
        "flat_eq_object": {n: C.flat_eq_object(st, cfg) for n, cfg in C.CFGS.items()},
    }
    entry.update(C.mask_info(game, board))
    entry["solver"] = _solve_maybe(game, board) if k <= 2 else None
    return entry


def collect_perm_invariance(games_meta, positions):
    """Deck-permutation invariance goldens for the fair-mode hidden-info gate (b).

    A marginalized solve is deck-order-invariant BY CONSTRUCTION (endgame_solver `_key`
    sorts the remaining-bag multiset). We freeze the K<=2 latch-band solves (the literal
    Phase-0.1 gate). NOTE: at k<=2 the unseen `state.deck` holds <=1 tile (the in-hand
    next_tile is already revealed), so the permutation is a structural no-op — this entry
    is a solver-REPRODUCTION regression gate. The genuine multi-tile order-independence is
    tested cheaply+directly on `_Solver._key` in test_golden.py (a k>=3 marginalized solve
    would churn for minutes, which the Phase-0.4 brief forbids). We keep a few k=1 + one
    k=2 entry."""
    out = []
    n_k2 = 0
    for p in positions:
        if not (p["k"] <= 2 and p["solver"] is not None):
            continue
        if p["k"] == 2:
            if n_k2 >= 1:
                continue
            n_k2 += 1
        elif len([x for x in out if x["k"] == 1]) >= 4:
            continue
        prefix = games_meta[str(p["seed"])]["actions"][:p["ply"]]
        out.append({"seed": p["seed"], "ply": p["ply"], "k": p["k"],
                    "actions": list(prefix),
                    "perm_seed": (p["seed"] * 131 + p["ply"]) & 0x7FFFFFFF,
                    "value": p["solver"]["value"],
                    "optimal_actions": p["solver"]["optimal_actions"]})
    return out


def main() -> int:
    t0 = time.perf_counter()
    seed_targets: dict[int, set[int]] = {}
    for k, n in PLAN:
        for s in range(1, n + 1):
            seed_targets.setdefault(s, set()).add(k)

    N_DISC = 6                              # discriminating (v27!=v28!=v29) positions to keep
    games_meta: dict[str, dict] = {}
    positions: list[dict] = []
    disc_pending: list[tuple[int, int, object]] = []   # (seed, ply, board)
    pos_id = 0
    for seed in sorted(seed_targets):
        targets = seed_targets[seed]
        actions, n_plies, term, final_diff, snaps, disc = play_and_snapshot(seed, targets)
        games_meta[str(seed)] = {"deck_seed": seed, "actions": actions, "n_plies": n_plies,
                                 "terminal_scores": term, "engine_final_diff_p0": final_diff}
        game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
        for k in sorted(targets):
            ply, board = snaps[k]
            positions.append(build_position(pos_id, seed, k, ply, game, board))
            pos_id += 1
        if disc is not None and len(disc_pending) < N_DISC:
            disc_pending.append((seed, disc[0], disc[1]))

    # Discriminating positions: pin all THREE configs distinctly so a regression in the
    # v2.8 meeple-liquidity term or the v2.9 meeple curve changes a frozen value and trips
    # the gate (the k-target positions coincide across configs — symmetric meeple counts).
    for seed, ply, board in disc_pending:
        game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
        k = C.k_remaining(board.state)
        positions.append(build_position(pos_id, seed, k, ply, game, board, kind="discriminating"))
        pos_id += 1

    perm = collect_perm_invariance(games_meta, positions)
    cur_v29 = C.cfg_hash(C.CFG_V29)
    # At GENERATION time the env is controlled (_golden_common set it before importing
    # carcassonne), so DEFAULT_CONFIG is the true production v2.9 leaf here. Record whether
    # the hand-built CFG_V29 matches it (robust "is this the production leaf?" check that
    # doesn't depend on the stale governance hash or on pytest import order).
    import dataclasses as _dc  # noqa: E402
    v29_eq_default = _dc.asdict(C.CFG_V29) == _dc.asdict(C._v2.DEFAULT_CONFIG)

    fixture = {
        "meta": {
            "phase": "0.4 standing golden correctness suite",
            "generated_by": "tests/golden/gen_golden.py",
            "env": C.ENV,
            "n_positions": len(positions),
            "n_games": len(games_meta),
            "solver_budget": C.SOLVER_BUDGET,
            "cfg_hashes": {n: C.cfg_hash(cfg) for n, cfg in C.CFGS.items()},
            "documented_v29_hash": C.FROZEN_V29_HASH,
            "current_v29_hash": cur_v29,
            "v29_hash_matches_governance": cur_v29 == C.FROZEN_V29_HASH,
            "governance_hash_note": (
                "FINDING (0.4): scripts/measurement_infra/snapshot.py FROZEN_V29_HASH "
                "(7fc930b82801cb43) is STALE and frozen_v29_cfg() now RAISES on the tree. "
                "The v2.10 LeafConfig.bag_close field (commit 1f521dd) shifted the asdict "
                "hash to the current value with NO change to config VALUES (bag_close "
                "defaults off, bit-exact). Golden CFG_V29 == env-built DEFAULT_CONFIG "
                "(verified by test_golden.test_v29_config_matches_production). Proposed "
                "(not applied) governance fix: update FROZEN_V29_HASH to the current hash "
                "or hash only value-affecting fields."),
            "n_discriminating": sum(1 for p in positions if p["kind"] == "discriminating"),
            "v29_equals_default_config": v29_eq_default,
            "canonical_bonus_sum": True,
        },
        "games": games_meta,
        "positions": positions,
        "deck_perm_invariance": perm,
    }
    C.FIXTURE.write_text(json.dumps(fixture, indent=1, sort_keys=True) + "\n")

    n_solved = sum(1 for p in positions if p["solver"] is not None)
    n_flat_fail = sum(1 for p in positions for v in p["flat_eq_object"].values() if not v)
    dt = time.perf_counter() - t0
    print(f"wrote {C.FIXTURE.name}: {len(positions)} positions ({n_solved} with solver), "
          f"{len(games_meta)} games, {len(perm)} perm-invariance goldens in {dt:.1f}s")
    print(f"  cfg hashes: " + ", ".join(f"{n}={C.cfg_hash(c)}" for n, c in C.CFGS.items()))
    print(f"  v29 current={cur_v29}  documented={C.FROZEN_V29_HASH}  "
          f"match={cur_v29 == C.FROZEN_V29_HASH}")
    if n_flat_fail:
        print(f"  ** WARNING: {n_flat_fail} flat!=object leaf mismatches under CANONICAL **")
    for a, bnm in (("v27", "v28"), ("v28", "v29")):
        diff = sum(1 for p in positions if p["vs"][a] != p["vs"][bnm])
        print(f"  leaf {a} vs {bnm}: differ on {diff}/{len(positions)} positions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
