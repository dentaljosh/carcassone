#!/usr/bin/env python3
"""IDENTITY GATE for the **OPPONENT** side of `scripts/classical_search/eval_puct_priors.py`
— the `_PuctPrefix` champion sibling (flags-OFF PUCT, clairvoyant single tree) on
`RustClairvoyantAgent`.

⚠️ WHY A SECOND GATE.  `scripts/rustport/gate_clairvoyant.py` licenses the Rust
clairvoyant ruler **at the candidate's knobs and at the PRODUCTION leaf**.  The
opponent here is a DIFFERENT config on a DIFFERENT leaf:

  * `final_select="visits"` (the champion selector) where the candidate default is
    `"Q"` — a genuinely different argmax rule, so the candidate gate proves nothing
    about it;
  * `value_norm=15.0`, `c_lcb=1.0`, `reuse_tree=False`, `root_select="puct"` forced
    to their champion-off values by `_champ_puct_cfg`;
  * the harness's OWN leaf — `eval_puct_priors._CANON_ENV` freezes the **v2.9
    Bmild_cap8** curve `-8,-4,-1,0,2,3,4,5`, NOT the production **curve125**
    `-10,-5,-1.25,…` that `scripts/rustport/env_preamble.PROD_ENV` installs.  This
    harness grades against the pre-2026-07-07 dethroned champion by design (audit
    row A6), so gating it under the production preamble would gate the wrong leaf.

That leaf conflict is also why this file is standalone rather than importing
`fair_common`/`gate_clairvoyant`: `fair_common` applies `PROD_ENV` on import and
hard-errors if `carcassonne_ai` was frozen against anything else, which is exactly
what importing this harness first does.  **`eval_puct_priors` must be the first
import here** — its module-level `_CANON_ENV` preamble is what freezes the leaf.

WHAT IS COMPARED — the same full surface as the candidate gate, as raw f64 BIT
patterns (decimals would hide a 1-ulp divergence):

    chosen_action                      the move the opponent would play
    root_n, root_w_bits                the root's own visit count and value sum
    root_children (action, N, W-bits)  EVERY child edge, not just the argmax

CONFIG LEGS.  Two, because `_champ_puct_cfg` has two live shapes:

  * `shared-axes` — the legacy/default path: c_puct/tau_p/leaf_quantize COPIED from
    the candidate at their defaults (1.5 / 5.0 / float).  Identical to what
    `--opp-pin-champion` produces at those defaults, so the pinned path is covered
    by construction (asserted, not assumed).
  * `shared-axes-swept` — a joint-sweep cell where the candidate moved those axes
    and the opponent copied them (c_puct 1.1, tau_p 3.0, **leaf_quantize int**).
    This is the only leg that drives the INT quantizer through the Rust leaf.

SCOPE OF A GREEN RESULT.  Single-world clairvoyant search, fresh-tree, net-free, at
these knobs and this leaf.  It says nothing about `reuse_tree` (Gap 2) or evaluator
injection (Gap 3) — `--opp-reuse-tree` and every net arm FAIL CLOSED at the harness
CLI, and `RustClairvoyantAgent` refuses both anyway.

    .venv/bin/python scripts/rustport/gate_clairvoyant_opponent.py --games 3
"""
from __future__ import annotations

import argparse
import json
import os
import random
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))

# ⚠️ MANDATORY FIRST — this applies the HARNESS leaf env (_CANON_ENV) before any
# `carcassonne_ai` import, which is what freezes `virtual_score_v2.DEFAULT_CONFIG`
# to the Bmild_cap8 curve the opponent actually plays. Do NOT import fair_common /
# gate_clairvoyant above this line: they install the production curve125 preamble.
import eval_puct_priors as H  # noqa: E402

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent  # noqa: E402
from carcassonne_ai.rust_agent import RustClairvoyantAgent  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GATE_CLAIRVOYANT_OPPONENT.json"

# The two live `_champ_puct_cfg` shapes (see the module docstring).
CFG_LEGS = {
    "shared-axes": {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float"},
    "shared-axes-swept": {"c_puct": 1.1, "tau_p": 3.0, "leaf_quantize": "int"},
}
SURFACE = ("chosen_action", "root_n", "root_w_bits", "root_children")


def ubits(x: float) -> int:
    """Raw IEEE-754 bits of a float as an unsigned int (Rust: `f64::to_bits`)."""
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _replay(deck_seed: int, actions: list[int]):
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for a in actions:
        board, _ = game.get_next_state(board, int(a))
    return game, board


def _py_surface(game, board, cfg, sims, seed) -> dict:
    """The ORACLE leg: the exact object `_PuctPrefix` wraps."""
    prefix = H._PuctPrefix(game, cfg, sims, seed)
    chosen = int(prefix.move(board))
    agent = prefix._a
    root = agent.mcts._nodes[game.string_representation(board)]
    return {
        "chosen_action": chosen,
        "root_n": int(root.N),
        "root_w_bits": ubits(root.W),
        "root_children": [[int(a), int(c.N), ubits(c.W)]
                          for a, c in sorted(root.children.items())],
    }


def _rs_surface(cfg, sims, seed, prefix_actions, deck_seed, board) -> dict:
    """The Rust leg, driven onto the SAME position via the mirror protocol —
    `start_game` on the true initial board, then one `advance` per applied action,
    exactly as `_play_one` does it."""
    ag = RustClairvoyantAgent(Game(enable_legal_moves_cache=True), cfg,
                              simulations=int(sims), seed=seed)
    _, b0 = _replay(deck_seed, [])
    ag.start_game(b0)
    for a in prefix_actions:
        ag.advance(int(a))
    ag.check_sync(board, "gate-opponent")     # the mirror really is at `board`
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
    ap = argparse.ArgumentParser(prog="gate_clairvoyant_opponent")
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--plies", default="12,40,72,104,130")
    ap.add_argument("--sims", type=int, default=2750,
                    help="opponent per-move budget (default 2750 = the F7 ablation "
                         "cell class the conversion was built for)")
    ap.add_argument("--seed", type=int, default=101,
                    help="search seed (proven inert by GAP1_SEED_INVARIANCE)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    plies = [int(x) for x in args.plies.split(",")]
    recs = [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()][:args.games]
    roots = []
    for g in recs:
        acts = [int(a) for a in g["actions"]]
        for p in plies:
            if p < len(acts):
                roots.append((int(g["deck_seed"]), p, acts[:p]))

    # `--opp-pin-champion` at the default candidate axes must REDUCE to the
    # shared-axes leg; assert it rather than trusting the constants to stay put.
    pinned = H._champ_puct_cfg(CFG_LEGS["shared-axes-swept"], pin_champion=True)
    shared = H._champ_puct_cfg(CFG_LEGS["shared-axes"], pin_champion=False)
    pin_reduces = (pinned.c_puct == shared.c_puct and pinned.tau_p == shared.tau_p
                   and pinned.leaf_quantize == shared.leaf_quantize)

    mismatches, checks, legs = [], 0, {}
    for leg, axes in CFG_LEGS.items():
        cfg = H._champ_puct_cfg(axes, reuse=False, pin_champion=False)
        assert cfg.reuse_tree is False and cfg.root_select == "puct"
        legs[leg] = {"c_puct": cfg.c_puct, "tau_p": cfg.tau_p,
                     "leaf_quantize": cfg.leaf_quantize,
                     "final_select": cfg.final_select,
                     "value_norm": cfg.value_norm, "c_lcb": cfg.c_lcb,
                     "reuse_tree": cfg.reuse_tree, "root_select": cfg.root_select}
        print(f"[{leg}] {legs[leg]}", flush=True)
        for deck_seed, ply, prefix in roots:
            game, board = _replay(deck_seed, prefix)
            py = _py_surface(game, board, cfg, args.sims, args.seed)
            _, board2 = _replay(deck_seed, prefix)
            rs = _rs_surface(cfg, args.sims, args.seed, prefix, deck_seed, board2)
            for field in SURFACE:
                checks += 1
                if py[field] != rs[field]:
                    mismatches.append({
                        "leg": leg, "deck_seed": deck_seed, "ply": ply,
                        "field": field,
                        "python": py[field] if field != "root_children"
                                  else py[field][:6],
                        "rust": rs[field] if field != "root_children"
                                else rs[field][:6]})
            ok_row = all(py[f] == rs[f] for f in SURFACE)
            print(f"  deck={deck_seed} ply={ply:>3} action={py['chosen_action']:>5} "
                  f"N={py['root_n']} children={len(py['root_children'])} "
                  f"{'IDENTICAL' if ok_row else 'MISMATCH'}", flush=True)

    ok = bool(roots) and not mismatches and pin_reduces
    out = {
        "gate": "rustport Class-B — eval_puct_priors OPPONENT (_PuctPrefix champion "
                "sibling) vs RustClairvoyantAgent",
        "why": "gate_clairvoyant.py licenses the CANDIDATE knobs on the PRODUCTION "
               "leaf. The opponent runs final_select=visits (a different argmax rule) "
               "on this harness's OWN v2.9 Bmild_cap8 leaf, so it needs its own gate.",
        "leaf_env": {k: os.environ.get(k) for k in H._CANON_ENV
                     if k.startswith("CARCASSONNE_")},
        "leaf_hash": H._leaf_hash(H.DEFAULT_CONFIG),
        "config_legs": legs,
        "pin_champion_reduces_to_shared_axes": pin_reduces,
        "pin_champion_note": "--opp-pin-champion swaps only c_puct/tau_p/"
                             "leaf_quantize for the CHAMP_PUCT_* constants, all three "
                             "carried by SearchConfigRs; at those constants it is "
                             "byte-identical to the shared-axes leg gated here.",
        "simulations": args.sims,
        "search_seed": args.seed,
        "seed_note": "inert — measurement/rustport_p6/GAP1_SEED_INVARIANCE.json",
        "surface": "chosen_action + root N + root W bits + EVERY root child "
                   "(action, N, W-bits), compared as raw f64 bit patterns",
        "roots": len(roots),
        "config_legs_count": len(CFG_LEGS),
        "field_checks": checks,
        "mismatches": mismatches,
        "verdict": "PASS" if ok else "FAIL",
        "scope": "single-world clairvoyant search, fresh-tree, net-free, at these "
                 "knobs and this leaf. Says NOTHING about reuse_tree (Gap 2) or "
                 "evaluator injection (Gap 3) — --opp-reuse-tree and every net arm "
                 "fail CLOSED at the eval_puct_priors CLI.",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(roots)} roots x {len(CFG_LEGS)} config legs, "
          f"{checks} field checks, {len(mismatches)} mismatches -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
