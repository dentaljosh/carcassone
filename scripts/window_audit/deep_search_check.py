"""Deep-search preference check for window-dropped legal actions.

For a sample of decisions that dropped >=1 legal action at the production W=25
window, ask: on a W=31 window (wide enough to include the dropped moves), does
HeuristicMCTS at h1600 actually PREFER a dropped move over the in-window best?

Correctness note: encoded action indices are window-size-dependent, so we
reconstruct the engine STATE by replaying through a W=25 Game, then build a
fresh W=31 Board.from_state (recomputing the offset) — we do NOT replay W25
indices through a W31 game.

Reads measurement/window_audit/audit_result_dropped_sample.json.
Run with the production leaf env (so HeuristicMCTS v2_7 == champion leaf).
"""
import argparse
import copy
import json
import random
import sys
from pathlib import Path

from wingedsheep.carcassonne.utils.action_util import ActionUtil

from carcassonne_ai.action_space import WindowOverflowError, encode
from carcassonne_ai.game_wrapper import Board, Game
from carcassonne_ai.mcts import HeuristicMCTS


def reconstruct_state(deck_seed, actions, ply):
    """Replay through a W=25 Game and return (board25, total_tiles)."""
    random.seed(int(deck_seed))
    g25 = Game(window_size=25, enable_legal_moves_cache=False)
    b = g25.get_init_board()
    for a in actions[:ply]:
        b, _ = g25.get_next_state(b, int(a))
    return b


def dropped_coords(state, off25, phase):
    """Return (dropped_actions, inwindow_count) at the W=25 window."""
    dropped = []
    inwin = 0
    for a in ActionUtil.get_possible_actions(state):
        try:
            encode(a, off25, phase)
            inwin += 1
        except WindowOverflowError:
            dropped.append(a)
    return dropped, inwin


def action_key(a):
    """Window-independent semantic key for an engine action (for reporting)."""
    cls = type(a).__name__
    coord = getattr(a, "coordinate", None)
    if coord is not None:
        return (cls, coord.row, coord.column, getattr(a, "tile_rotations", None))
    cws = getattr(a, "coordinate_with_side", None)
    if cws is not None:
        return (cls, cws.coordinate.row, cws.coordinate.column, str(cws.side))
    return (cls,)


def check_one(entry, sims=1600, seed=0):
    deck_seed = entry["deck_seed"]
    actions = entry["actions"]
    ply = entry["ply"]
    b25 = reconstruct_state(deck_seed, actions, ply)
    state = b25.state
    off25 = b25.offset
    phase = state.phase.value
    dropped, inwin = dropped_coords(state, off25, phase)

    # Build a fresh W=31 view of the SAME engine state (deepcopy so MCTS can't
    # disturb the state we still read from for the W25 drop test).
    g31 = Game(window_size=31, enable_legal_moves_cache=True)
    b31 = Board.from_state(copy.deepcopy(state), b25.total_tiles, 31)
    off31 = b31.offset

    # Confirm W=31 actually includes the dropped moves.
    dropped_in_w31 = 0
    for a in dropped:
        try:
            encode(a, off31, phase)
            dropped_in_w31 += 1
        except WindowOverflowError:
            pass

    mcts = HeuristicMCTS(g31, simulations=sims, heur_leaf="v2_7", seed=seed)
    best_idx = mcts.best_action(b31)
    a_star = g31._decode_for(b31.state, off31, best_idx)

    # Is the deep-search-preferred move one W25 would have DROPPED?
    star_dropped = False
    try:
        encode(a_star, off25, phase)
    except WindowOverflowError:
        star_dropped = True

    return {
        "deck_seed": deck_seed,
        "ply": ply,
        "phase": phase,
        "k_remaining": entry.get("k_remaining"),
        "n_dropped_w25": len(dropped),
        "n_inwindow_w25": inwin,
        "dropped_included_in_w31": dropped_in_w31,
        "h1600_w31_best_key": list(action_key(a_star)),
        "h1600_prefers_dropped_move": star_dropped,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="measurement/window_audit/audit_result_dropped_sample.json")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--sims", type=int, default=1600)
    ap.add_argument("--out", default="measurement/window_audit/deep_search_result.json")
    args = ap.parse_args()

    sample = json.loads(Path(args.sample).read_text())
    rng = random.Random(2026)
    if len(sample) > args.n:
        chosen = rng.sample(sample, args.n)
    else:
        chosen = sample
    print(f"checking {len(chosen)} dropped-action decisions at h{args.sims} W31")

    results = []
    n_hits = 0
    for i, entry in enumerate(chosen):
        r = check_one(entry, sims=args.sims)
        results.append(r)
        if r["h1600_prefers_dropped_move"]:
            n_hits += 1
        print(f"[{i+1}/{len(chosen)}] seed={r['deck_seed']} ply={r['ply']} "
              f"k_rem={r['k_remaining']} dropped={r['n_dropped_w25']} "
              f"inwin={r['n_inwindow_w25']} prefers_dropped={r['h1600_prefers_dropped_move']}")

    out = {
        "n_checked": len(results),
        "n_prefers_dropped": n_hits,
        "frac_prefers_dropped": (n_hits / len(results)) if results else 0.0,
        "sims": args.sims,
        "results": results,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"=== {n_hits}/{len(results)} sampled dropped-action decisions: "
          f"h{args.sims}@W31 prefers a dropped move ===")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
