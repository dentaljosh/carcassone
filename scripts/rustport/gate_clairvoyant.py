#!/usr/bin/env python3
"""IDENTITY GATE for `rust_agent.RustClairvoyantAgent` — the Class-B ruler primitive.

⚠️ WHY THIS GATE IS NOT OPTIONAL.  Class B is the INSTRUMENT tier: the clairvoyant /
oracle agents that PRICE other things.  Converting an instrument changes the
instrument, so a "the engine is bit-exact" argument inherited from G4/G6 does not
transfer — those gated the FAIR PIMC champion, a different agent with a different
search.  Nothing may be graded with the Rust ruler until this gate is green.

WHAT IS COMPARED.  On each recorded-champion root, one search is run through the
Python `HeuristicPriorAgent` and one through `RustClairvoyantAgent`, and the FULL
comparable surface is compared as RAW f64 BIT PATTERNS (the G3 pattern — decimals
would hide a 1-ulp divergence that a reconcile gate must catch):

    chosen_action                      the move the ruler would play
    root_n, root_w_bits                the root's own visit count and value sum
    root_children (action, N, W-bits)  EVERY child edge, not just the argmax

Comparing only the chosen action would pass a search that got the right answer for
the wrong reasons; comparing the child edges makes the two trees prove they are the
same tree.

SCOPE OF A GREEN RESULT.  It licenses the SINGLE-WORLD clairvoyant search at the
knobs tested, fresh-tree, net-free.  It says nothing about `reuse_tree` (Gap 2) or
an injected evaluator (Gap 3) — both of which `RustClairvoyantAgent` REFUSES rather
than approximates.

    .venv/bin/python scripts/rustport/gate_clairvoyant.py --games 3
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "rustport"))

# MANDATORY FIRST — production leaf env + import-order guard (see fair_common).
import fair_common as F  # noqa: E402

import trace_search as T  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent  # noqa: E402
from carcassonne_ai.rust_agent import RustClairvoyantAgent  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GATE_CLAIRVOYANT.json"


def _replay(deck_seed: int, actions: list[int]):
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for a in actions:
        board, _ = game.get_next_state(board, int(a))
    return game, board


def _py_surface(game, board, cfg, sims, seed) -> dict:
    agent = HeuristicPriorAgent(game=game, cfg=cfg, simulations=int(sims), seed=seed)
    with T.production_leaf_dispatch():
        chosen = int(agent.move(board))
    root = agent.mcts._nodes[game.string_representation(board)]
    return {
        "chosen_action": chosen,
        "root_n": int(root.N),
        "root_w_bits": F.ubits(root.W),
        "root_children": [[int(a), int(c.N), F.ubits(c.W)]
                          for a, c in sorted(root.children.items())],
    }


def _rs_surface(game, board, cfg, sims, seed, prefix, deck_seed) -> dict:
    """Drive the Rust ruler onto the SAME position via the mirror protocol."""
    ag = RustClairvoyantAgent(game, cfg, simulations=int(sims), seed=seed)
    _, b0 = _replay(deck_seed, [])
    ag.start_game(b0)
    for a in prefix:
        ag.advance(int(a))
    ag.check_sync(board, "gate-seat")          # the mirror really is at `board`
    chosen = int(ag.choose_action(board))
    r = ag.last_search()
    return {
        "chosen_action": chosen,
        "root_n": int(r["root_n"]),
        "root_w_bits": int(r["root_w_bits"]),
        "root_children": [[int(a), int(n), int(w)]
                          for a, n, w in sorted(r["root_children"])],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_clairvoyant")
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--plies", default="12,40,72,104,130")
    ap.add_argument("--sims", type=int, default=None,
                    help="default: the champion's per-determinization budget")
    ap.add_argument("--seed", type=int, default=101,
                    help="search seed (proven inert by GAP1_SEED_INVARIANCE)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    knobs = T.production_knobs()
    cfg = T.py_config(knobs)
    sims = int(args.sims) if args.sims else int(knobs["sims_per_det"])
    plies = [int(x) for x in args.plies.split(",")]

    recs = [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()][:args.games]
    roots = []
    for g in recs:
        acts = [int(a) for a in g["actions"]]
        for p in plies:
            if p < len(acts):
                roots.append((int(g["deck_seed"]), p, acts[:p]))

    mismatches, checks = [], 0
    for deck_seed, ply, prefix in roots:
        game, board = _replay(deck_seed, prefix)
        py = _py_surface(game, board, cfg, sims, args.seed)
        game2, board2 = _replay(deck_seed, prefix)
        rs = _rs_surface(game2, board2, cfg, sims, args.seed, prefix, deck_seed)
        for field in ("chosen_action", "root_n", "root_w_bits", "root_children"):
            checks += 1
            if py[field] != rs[field]:
                mismatches.append({
                    "deck_seed": deck_seed, "ply": ply, "field": field,
                    "python": py[field] if field != "root_children"
                              else py[field][:6],
                    "rust": rs[field] if field != "root_children"
                            else rs[field][:6]})
        ok_row = all(py[f] == rs[f] for f in
                     ("chosen_action", "root_n", "root_w_bits", "root_children"))
        print(f"  deck={deck_seed} ply={ply:>3} action={py['chosen_action']:>5} "
              f"N={py['root_n']} children={len(py['root_children'])} "
              f"{'IDENTICAL' if ok_row else 'MISMATCH'}", flush=True)

    ok = bool(roots) and not mismatches
    out = {
        "gate": "rustport Class-B — RustClairvoyantAgent vs HeuristicPriorAgent",
        "why": "Class B is the INSTRUMENT tier; G4/G6 gated the FAIR PIMC champion, a "
               "different agent. A converted ruler must prove itself before it prices "
               "anything.",
        "champion_id": knobs["champion_id"],
        "simulations": sims,
        "search_seed": args.seed,
        "seed_note": "inert — measurement/rustport_p6/GAP1_SEED_INVARIANCE.json",
        "surface": "chosen_action + root N + root W bits + EVERY root child "
                   "(action, N, W-bits), compared as raw f64 bit patterns",
        "roots": len(roots),
        "field_checks": checks,
        "mismatches": mismatches,
        "verdict": "PASS" if ok else "FAIL",
        "scope": "single-world clairvoyant search, fresh-tree, net-free, at these "
                 "knobs. Says NOTHING about reuse_tree (Gap 2) or evaluator "
                 "injection (Gap 3) — RustClairvoyantAgent refuses both.",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(roots)} roots, {checks} field checks, "
          f"{len(mismatches)} mismatches -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
