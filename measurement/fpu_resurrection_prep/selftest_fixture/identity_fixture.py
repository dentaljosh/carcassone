#!/usr/bin/env python3
"""⭐⭐ THE GOLDEN GATE — "bit-exact when `fpu_reduction` is None".

WHAT IS BEING PROVEN, AND WHAT IS NOT.

`measurement/fpu_resurrection_prep` threads `fpu_reduction` end-to-end. The
load-bearing edit is one line: `rust_agent.search_config_rs` used to pass a
HARD-CODED `None` into `SearchConfigRs`'s `fpu_reduction` slot and now forwards
`cfg.fpu_reduction`. Two propositions have to hold before a single deck is spent:

  ⭐ **IDENTITY.** With the knob unset (`None`), the agent's play is BIT-IDENTICAL
     to the pre-change code. The whole round's opponent is the unmodified
     champion, so if the plumbing perturbed the default path the cells would be
     grading a moved baseline against a moved candidate.
  ⭐ **THE POSITIVE CONTROL.** With the knob SET (`0.2`), the play DIFFERS. A
     knob that changes nothing is indistinguishable from a knob that never
     bound — and "never bound" is the exact defect this round was funded to
     close. ⛔ An identity result WITHOUT a positive control is worth nothing:
     the hard-coded `None` would have passed it perfectly.

⛔⛔ **THE POSITIVE CONTROL ALSO ADJUDICATES THE AUDIT FINDING.** The Fable
false-negative audit's claim was *"the champion cannot express `fpu_reduction`"*.
Run this script against the PRE-change tree with `--fpu 0.2` and it produces the
SAME action-sequence hash as `--fpu` unset — that is the defect, reproduced as a
number. Run it against the POST-change tree and the hashes separate. The pair of
runs IS the adjudication; no separate instrument is needed.

⚠️ **NO WHEEL MOVES ACROSS THIS CHANGE.** `carc_rs` already accepted
`Option<f64>` in that slot (`carc-py/src/lib.rs:1580`) and `carc_core::search`
already implemented the rule (`search/mod.rs:816`). The fix is PYTHON PLUMBING
ONLY, so the A/B is `old code vs new code against ONE installed wheel` — which
is also why this round needs no `IDENT` preflight CELL (`DESIGN.md` §9): the
phasegate precedent carried one because ITS wheel moved and a stale wheel would
have served a gate-blind arbiter. Here the binary is a constant of the
comparison, and this fixture proves the only thing that did change.

USAGE

    # the two legs of the golden gate (same wheel, different src tree):
    PYTHONPATH=<OLD>/src:<OLD>/engine python identity_fixture.py --out OLD.json
    PYTHONPATH=<NEW>/src:<NEW>/engine python identity_fixture.py --out NEW.json
    # the positive control (NEW tree only — on OLD it is a NO-OP, which is the bug):
    PYTHONPATH=<NEW>/src:<NEW>/engine python identity_fixture.py --fpu 0.2 \
        --out NEW_FPU02.json
    python identity_diff.py OLD.json NEW.json NEW_FPU02.json

⚠️ THE BUDGET IS DELIBERATELY TINY (k2 x 96, not the champion's k8 x 1376). The
proposition is about a CODE PATH, not about a budget: `fpu_reduction` is read on
EVERY unvisited-child PUCT score, so a 96-sim search exercises it thousands of
times per move. A champion-budget fixture would cost hours and prove the same
bit. ⛔ It is therefore NOT a strength measurement and no number in it may be
read as one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import sys
import time
from pathlib import Path

# ⚠️ The production leaf SHAPE must be frozen BEFORE carcassonne_ai is imported —
# `virtual_score_v2.DEFAULT_CONFIG` is built once, at that import, from the env.
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "scripts" / "human_anchor"))
import env_preamble  # noqa: E402,F401


#: The seeded decks the fixture plays. ⛔ FROZEN: an identity claim over a
#: caller-chosen seed set is not a claim. 20 decks is the brief's floor; the
#: action sequences are long (~70 plies each), so the hash is over ~1,400
#: decisions per leg, every one of them a PUCT argmax that reads the FPU branch.
SEEDS = tuple(range(9_100_000_000, 9_100_000_020))

#: ⛔ FROZEN search shape. See the module docstring on why it is not the
#: champion's budget.
K_DETS = 2
SIMS_PER_DET = 96
EXACT_K = 2


def _agent(game, cfg, seed: int, backend: str):
    from carcassonne_ai import champion_factory as CF

    return CF.build_fair_champion(
        game, cfg=cfg, sims=SIMS_PER_DET, k_dets=K_DETS, seed=seed,
        exact_max_k=EXACT_K, backend=backend, rust_threads=1)


def play(seed: int, fpu, backend: str) -> dict:
    """One SELF-PLAY game: the same agent config drives both seats, so the
    action sequence is a pure function of (seed, cfg, budget, backend)."""
    import random

    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.game_wrapper import Game

    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    cfg = CF.production_prior_cfg()
    if fpu is not None:
        import dataclasses as dc
        cfg = dc.replace(cfg, fpu_reduction=float(fpu))

    agent = _agent(game, cfg, seed, backend)
    drives_mirror = hasattr(agent, "start_game") and hasattr(agent, "advance")
    if drives_mirror:
        agent.start_game(board)

    actions: list[int] = []
    plies = 0
    # ⚠️ The termination and step protocol are COPIED FROM THE PRODUCTION LOOP
    # (`eval_fair_puct._play_one_inner`): `get_game_ended(board, 0) == 0.0` while
    # live, `get_next_state(board, action)` (2-arg — the wrapper reads the mover
    # off the board), `agent.move()` NOT `best_action()` (move() is what advances
    # the agent's own prefix/mirror bookkeeping). A fixture that drives the agent
    # through a DIFFERENT protocol than production proves identity of something
    # nobody ships.
    while game.get_game_ended(board, 0) == 0.0 and plies < 400:
        a = int(agent.move(board))
        actions.append(a)
        board, _ = game.get_next_state(board, a)
        if drives_mirror:
            agent.advance(a)
        plies += 1
    scores = [int(x) for x in board.state.scores]
    return {
        "seed": seed,
        "n_actions": len(actions),
        "actions_sha256": hashlib.sha256(
            ",".join(map(str, actions)).encode()).hexdigest(),
        "first_8_actions": actions[:8],
        "final_scores": scores,
        # The resolved knob, read off the CONFIG THE AGENT WAS BUILT WITH — the
        # fixture never restates the CLI value as if it were an observation.
        # ⚠️ `getattr(..., None)`: on the PRE-change tree the attribute does not
        # EXIST, and "the field is absent" is precisely the leg's finding — it
        # must be recorded, not raised through.
        "resolved_fpu": getattr(cfg, "fpu_reduction", None),
        "resolved_c_puct": cfg.c_puct,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fpu", type=float, default=None,
                    help="candidate fpu_reduction; unset == the champion")
    ap.add_argument("--backend", default="rust", choices=("rust", "python"))
    ap.add_argument("--seeds", type=int, default=len(SEEDS),
                    help="how many of the FROZEN seeds to play (a smaller number "
                         "is a cheaper PREVIEW; the gate itself uses all of them)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import carcassonne_ai
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig

    # ⭐ THE TREE WITNESS. The two legs differ ONLY in PYTHONPATH, so the
    # resolved package path is what proves the run is the leg it claims to be.
    tree = str(Path(carcassonne_ai.__file__).resolve().parents[2])
    has_field = "fpu_reduction" in HeuristicPriorConfig.__dataclass_fields__
    rs_repr = None
    try:
        from carcassonne_ai.rust_agent import search_config_rs
        rs_repr = repr(search_config_rs(CF.production_prior_cfg(), 8))
    except Exception as e:                                    # noqa: BLE001
        rs_repr = f"<unavailable: {e}>"

    if args.fpu is not None and not has_field:
        # ⛔ THE AUDITED DEFECT, NAMED RATHER THAN CRASHED THROUGH. On the
        # pre-change tree `--fpu` cannot even be expressed, so the leg is
        # recorded as what it is: a NO-OP that will hash identically to the
        # unset leg. That equality IS the finding.
        print("[identity_fixture] ⛔ this tree's HeuristicPriorConfig has NO "
              "fpu_reduction field — the requested knob CANNOT be expressed. "
              "Recording the leg as REQUESTED-BUT-UNREACHABLE.", flush=True)

    t0 = time.perf_counter()
    games = []
    for s in SEEDS[: max(1, int(args.seeds))]:
        games.append(play(s, args.fpu if has_field else None, args.backend))
        print(f"[identity_fixture] seed {s} -> {games[-1]['actions_sha256'][:16]} "
              f"({games[-1]['n_actions']} plies)", flush=True)

    out = {
        "fixture": "fpu_resurrection golden gate",
        "requested_fpu": args.fpu,
        "knob_expressible_on_this_tree": has_field,
        "requested_but_unreachable": bool(args.fpu is not None and not has_field),
        "backend": args.backend,
        "src_tree": tree,
        "carc_rs_binary_sha": CF and _rs_sha(),
        "search_config_rs_repr_at_champion": rs_repr,
        "budget": {"k_dets": K_DETS, "sims_per_det": SIMS_PER_DET,
                   "exact_k": EXACT_K,
                   "note": "⛔ NOT the champion's k8x1376 — this is a CODE-PATH "
                           "identity fixture, never a strength measurement."},
        "seeds": list(SEEDS[: max(1, int(args.seeds))]),
        "host": socket.gethostname(),
        "python": platform.python_version(),
        "env_flat_leaf": os.environ.get("CARCASSONNE_USE_FLAT_LEAF"),
        "wall_secs": time.perf_counter() - t0,
        "games": games,
        # THE LEG'S single comparable number: one hash over every game's hash.
        "leg_sha256": hashlib.sha256(
            "|".join(g["actions_sha256"] for g in games).encode()).hexdigest(),
    }
    args.out.write_text(json.dumps(out, indent=2))
    print(f"[identity_fixture] leg_sha256 = {out['leg_sha256']}")
    print(f"[identity_fixture] wrote {args.out}")
    return 0


def _rs_sha():
    try:
        from carcassonne_ai.rust_agent import carc_rs_binary_sha
        return carc_rs_binary_sha()
    except Exception:                                         # noqa: BLE001
        return "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
