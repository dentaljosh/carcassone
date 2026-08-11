#!/usr/bin/env python3
"""GAP 1 — is `HeuristicPriorAgent`'s search SEED-INVARIANT at champion knobs?

WHY THIS GATE EXISTS.  `carc_rs.MirrorState.search_single` has no `seed` field
(`SearchConfigRs`, lib.rs:758-830), and rustport G3 gated it only against
`HeuristicPriorAgent(..., seed=None)` (`trace_search.py:324`).  Every Class-B
caller in the repo passes a REAL seed — `eval_puct_priors` passes `--seed`, the
per-world loops of the measurement-infra probes pass `base+100+i`.  So before any
clairvoyant/oracle instrument is moved onto the Rust search, the question "does
the seed change the answer?" has to be answered with evidence rather than with a
code-reading.

THE CODE-READING (what this gate is testing, not trusting).  The seed feeds
`NeuralMCTS._np_rng`, which is consumed in exactly two places: temperature
sampling (`mcts.py:696`) and Dirichlet root noise (`mcts.py:1011`).  Neither is
engaged at champion knobs under `best_action` — the champion selects
deterministically and adds no root noise.  If that reading is right the search is
seed-invariant and the missing Rust field is INERT.  If it is wrong, every
converted instrument silently diverges from the Python one it replaces.

THE TEST.  Replay recorded CHAMPION games to a spread of plies (opening / mid /
late — per-leaf cost and tree shape both track placed meeples) and run the same
search at several seeds, including `None` (the value G3 actually gated).  Compare
the FULL comparable surface as RAW f64 BITS, not decimals: chosen action, and
every root child's `(action, N, W)`.  Bit-equality is the standard the rustport
gates are held to; a decimal-equal / bit-unequal result would still be a real
divergence for a reconcile gate.

Green here does NOT license converting an instrument on its own — it removes ONE
of the three blockers (Gap 2 `reuse_tree` and Gap 3 evaluator injection are
separate), and any converted ruler still needs its own identity gate on the G6
pattern before it grades anything.

    .venv/bin/python scripts/rustport/gap1_seed_invariance.py --games 4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "rustport"))

# ⚠️ MANDATORY AND FIRST: fair_common applies the production leaf env and enforces
# the import-order guard. `virtual_score_v2.DEFAULT_CONFIG` is IMPORT-FROZEN from
# those knobs, so a `carcassonne_ai` import that beats this one silently builds a
# cap-5 / meeple_k-0 leaf and the whole gate measures the wrong champion.
import fair_common as F  # noqa: E402

import trace_search as T  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GAP1_SEED_INVARIANCE.json"

# The seeds to cross-compare. `None` is the one G3 gated, so it is the reference
# leg; the others are the shapes real callers pass (`--seed`, `base+100+i`).
SEEDS: list[int | None] = [None, 0, 7, 101, 12345, 999983]


def _replay(deck_seed: int, actions: list[int]):
    """Seat a live (game, board) on a recorded prefix — the lossless root replay."""
    import random

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for a in actions:
        board, _ = game.get_next_state(board, int(a))
    return game, board


def _surface(game, board, cfg, sims: int, seed) -> dict:
    """The comparable surface of ONE search, floats as raw f64 bit patterns."""
    agent = HeuristicPriorAgent(game=game, cfg=cfg, simulations=int(sims), seed=seed)
    with T.production_leaf_dispatch():
        chosen = int(agent.move(board))
    root = agent.mcts._nodes[game.string_representation(board)]
    return {
        "chosen_action": chosen,
        "root_n": int(root.N),
        "root_w_bits": F.ubits(root.W),
        "root_children": [(int(a), int(c.N), F.ubits(c.W))
                          for a, c in sorted(root.children.items())],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gap1_seed_invariance")
    ap.add_argument("--games", type=int, default=4,
                    help="recorded champion games supplying roots")
    ap.add_argument("--plies", default="12,40,72,104,130",
                    help="opening/mid/late spread; tree shape tracks placed meeples")
    ap.add_argument("--sims", type=int, default=None,
                    help="sims for the single-world search (default: the champion's "
                         "per-determinization budget from PRODUCTION.yaml)")
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

    rows, mismatches = [], []
    for deck_seed, ply, prefix in roots:
        ref = None
        for seed in SEEDS:
            game, board = _replay(deck_seed, prefix)
            surf = _surface(game, board, cfg, sims, seed)
            if ref is None:
                ref, ref_seed = surf, seed
                continue
            if surf != ref:
                diff = {"deck_seed": deck_seed, "ply": ply,
                        "ref_seed": ref_seed, "seed": seed,
                        "chosen_ref": ref["chosen_action"],
                        "chosen_got": surf["chosen_action"],
                        "children_equal":
                            surf["root_children"] == ref["root_children"]}
                mismatches.append(diff)
                print(f"  MISMATCH {diff}")
        rows.append({"deck_seed": deck_seed, "ply": ply,
                     "chosen_action": ref["chosen_action"],
                     "root_n": ref["root_n"],
                     "n_children": len(ref["root_children"])})
        print(f"  root deck={deck_seed} ply={ply:>3}  "
              f"action={ref['chosen_action']:>5}  N={ref['root_n']}  "
              f"children={len(ref['root_children'])}  "
              f"{len(SEEDS)} seeds identical", flush=True)

    n_cmp = len(roots) * (len(SEEDS) - 1)
    ok = not mismatches
    out = {
        "gate": "rustport GAP1 — HeuristicPriorAgent seed-invariance at champion knobs",
        "question": "does the search `seed` change the answer? (carc_rs "
                    "SearchConfigRs has no seed field; G3 gated seed=None only)",
        "champion_id": knobs["champion_id"],
        "sims_per_world": sims,
        "seeds": [("None" if s is None else s) for s in SEEDS],
        "roots": len(roots),
        "comparisons": n_cmp,
        "surface": "chosen_action + root N + root W bits + every root child "
                   "(action, N, W-bits) — raw f64 bit patterns, not decimals",
        "mismatches": mismatches,
        "verdict": "PASS" if ok else "FAIL",
        "conclusion": (
            "the missing carc_rs search seed is INERT at champion knobs: the seed "
            "feeds NeuralMCTS._np_rng, consumed only by temperature sampling and "
            "Dirichlet root noise, neither engaged under best_action. Gap 1 is "
            "CLOSED for this knob set. Gaps 2 (reuse_tree) and 3 (evaluator "
            "injection) are untouched by this result, and a converted RULER still "
            "needs its own G6-pattern identity gate."
            if ok else
            "the search is SEED-DEPENDENT — carc_rs.search_single cannot stand in "
            "for a seeded HeuristicPriorAgent until SearchConfigRs plumbs a seed."),
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {n_cmp} cross-seed comparisons over {len(roots)} "
          f"roots, {len(mismatches)} mismatches -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
