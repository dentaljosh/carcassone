#!/usr/bin/env python3
"""GAP 2 — is the ORACLE PILOT's continuation policy fresh-tree? (audit item A3)

WHY THIS EXISTS.  `oracle_score_pilot` is a RULER: it prices whether the deeper pick is
better (+0.7375 pts/disagreement, cluster-robust z +2.97).  Converting a ruler changes the
ruler, so before its continuation policy could be moved onto
`carc_rs.MirrorState.search_single`, the question "is the Python continuation the same
SEARCH that search_single implements?" had to be answered with a measurement rather than a
code-reading.  `search_single`'s own docstring pins it as *"equivalent to
`HeuristicPriorAgent(game, cfg, sims).move(board)` with **reuse_tree=False** (a fresh tree
+ fresh legal-move cache per move)"* — and the pilot's playout loop calls
`agent.best_action(b)`, **not** `agent.move(b)`.

THE CODE-READING BEING TESTED.  `HeuristicPriorAgent.move()` clears the tree when
`reuse_tree` is False (`heuristic_prior_mcts.py:1214-1219`); `best_action()` does NOT — it
goes straight to `self.mcts.search(board)` on a `NeuralMCTS` whose `_nodes` transposition
table is never cleared between plies.  `_playout_value` builds ONE continuation agent and
calls `best_action` for every ply to terminal, so each ply's root can arrive with
statistics accumulated while it was a descendant of an earlier ply's tree.  If that is
real, the pilot's continuation is a PERSISTING-TREE search and `search_single` is not a
drop-in for it.

THE TEST.  Play the same afterstate out twice, from the SAME determinized world with the
SAME seed, and change exactly one thing:

    persistent   ONE agent, `best_action` every ply       <- what the pilot runs today
    fresh        a NEW agent every ply (same seed)        <- search_single's semantics

and compare, per ply, the CHOSEN ACTION and the root's pre-search N.  A single action
divergence is decisive: the two legs are different players, so a converted continuation
would be a different ruler, and the +0.7375 could not be quoted across the change.

    .venv/bin/python scripts/rustport/gap2_oracle_continuation_tree.py --positions 4
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

# MUST precede any carcassonne_ai import (import-frozen DEFAULT_CONFIG).
import oracle_score_pilot as O  # noqa: E402

import root_replay as RR  # noqa: E402
from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GAP2_ORACLE_CONTINUATION_TREE.json"


def playout(game, world_board, action, *, sims, seed, max_plies, fresh: bool) -> dict:
    """The pilot's `_playout_value` loop, with the tree policy as the ONE variable."""
    b = copy.deepcopy(world_board)
    b, _ = game.get_next_state(b, int(action))
    agent = None if fresh else O.build_continuation_agent(
        game, policy="clair-puct", sims=int(sims), seed=int(seed))
    actions, preexisting, over_budget = [], 0, 0
    plies = 0
    while not b.state.is_terminated() and plies < max_plies:
        ag = O.build_continuation_agent(game, policy="clair-puct", sims=int(sims),
                                        seed=int(seed)) if fresh else agent
        key = game.string_representation(b)
        pre = ag.mcts._nodes.get(key)
        pre_n = int(pre.N) if pre is not None else 0
        if pre_n > 0:
            preexisting += 1
        a = int(ag.best_action(b))
        root_n = int(ag.mcts._nodes[key].N)
        if root_n > int(sims):
            over_budget += 1
        actions.append(a)
        b, _ = game.get_next_state(b, a)
        plies += 1
    margin = float(b.state.scores[0] - b.state.scores[1])
    return {"actions": actions, "plies": plies, "margin_p0": margin,
            "plies_with_preexisting_root": preexisting,
            "plies_root_N_over_budget": over_budget}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gap2_oracle_continuation_tree")
    ap.add_argument("--games", type=int, default=2)
    ap.add_argument("--plies", default="40,72,104")
    ap.add_argument("--sims", type=int, default=100,
                    help="the pilot's own --oracle-sims default")
    ap.add_argument("--max-plies", type=int, default=200)
    ap.add_argument("--positions", type=int, default=4, help="afterstates to play out")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    O._G["cfg"] = CF.production_prior_cfg()
    plies = [int(x) for x in args.plies.split(",")]

    recs = [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()][:args.games]
    roots = []
    for g in recs:
        acts = [int(a) for a in g["actions"]]
        for p in plies:
            if p < len(acts):
                roots.append((int(g["deck_seed"]), p, acts))
    roots = roots[:int(args.positions)]

    rows, diverged = [], 0
    for deck_seed, ply, acts in roots:
        game, board = RR.replay_actions(deck_seed, acts, ply)
        world = FairHeuristicMCTSAgent.reshuffled_determinization(
            board, random.Random(deck_seed * 31 + ply))
        import numpy as np

        legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        if not legal:
            continue
        action = legal[0]
        seed = deck_seed * 7 + ply
        per = playout(game, world, action, sims=args.sims, seed=seed,
                      max_plies=args.max_plies, fresh=False)
        fre = playout(game, world, action, sims=args.sims, seed=seed,
                      max_plies=args.max_plies, fresh=True)
        n = min(len(per["actions"]), len(fre["actions"]))
        first_diff = next((i for i in range(n)
                           if per["actions"][i] != fre["actions"][i]), None)
        same = (per["actions"] == fre["actions"])
        if not same:
            diverged += 1
        rows.append({
            "deck_seed": deck_seed, "ply": ply, "root_action": action,
            "persistent": {k: v for k, v in per.items() if k != "actions"},
            "fresh": {k: v for k, v in fre.items() if k != "actions"},
            "actions_identical": same,
            "first_divergent_ply": first_diff,
            "n_divergent_plies": sum(1 for i in range(n)
                                     if per["actions"][i] != fre["actions"][i]),
            "margin_delta": per["margin_p0"] - fre["margin_p0"],
        })
        print(f"  deck={deck_seed} ply={ply}: persistent {per['plies']} plies "
              f"(preexisting root on {per['plies_with_preexisting_root']}, "
              f"root N > sims on {per['plies_root_N_over_budget']}) | fresh "
              f"{fre['plies']} plies (preexisting {fre['plies_with_preexisting_root']}) "
              f"| actions {'IDENTICAL' if same else f'DIVERGE at ply {first_diff}'} "
              f"| margin {per['margin_p0']} vs {fre['margin_p0']}", flush=True)

    fresh_is_drop_in = bool(rows) and diverged == 0
    out = {
        "gate": "rustport GAP2 (audit A3) — is oracle_score_pilot's continuation fresh-tree?",
        "question": "`MirrorState.search_single` is documented fresh-tree (reuse_tree=False). "
                    "The pilot's playout calls HeuristicPriorAgent.best_action(), which — "
                    "unlike .move() — never clears the tree. Are the two the same player?",
        "oracle_sims": int(args.sims),
        "positions": len(rows),
        "positions_with_divergent_action_stream": diverged,
        "verdict": "FRESH-TREE-EQUIVALENT" if fresh_is_drop_in else "NOT-FRESH-TREE",
        "conclusion": (
            "the pilot's continuation is a PERSISTING-TREE search: its per-ply root arrives "
            "with statistics accumulated as a descendant of earlier plies' trees, and "
            "replaying the identical world fresh-tree per ply yields a DIFFERENT action "
            "stream and a different terminal margin. `carc_rs.MirrorState.search_single` is "
            "fresh-tree only (Gap 2 of BACKEND_BYPASS_AUDIT_20260801 §3, still OPEN), so it "
            "is NOT a drop-in for this continuation. Converting A3 would silently CHANGE THE "
            "RULER that priced +0.7375 pts/disagreement. oracle_score_pilot therefore fails "
            "closed on --backend rust."
            if not fresh_is_drop_in else
            "the continuation happens to be fresh-tree-equivalent at these knobs; the Gap-2 "
            "objection does not bind here and a conversion would need only its own G6-pattern "
            "identity gate."),
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {diverged}/{len(rows)} positions have a divergent action "
          f"stream -> {args.out}")
    # Exit 0 either way: this is a MEASUREMENT that informs a decision, not a pass/fail gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
