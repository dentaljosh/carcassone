#!/usr/bin/env python3
"""⭐⭐ ONE LEG of the FPU DOSE-LADDER's GOLDEN GATE.

⚠️ A FORK of `measurement/fpu_resurrection_prep/selftest_fixture/identity_fixture.py`
(that round is FROZEN; its files do not move). What changed and why:

  ⭐ **`--fpu` takes ANY dose**, and the runner drives it at all FOUR of this
     round's rungs. The parent proved the knob binds at 0.2; a LADDER needs
     every rung's dose to bind, and needs the four to be DISTINGUISHABLE from
     each other (`DOSE-DISTINCT`, below) — a build that clamped or rounded small
     doses would pass a per-dose positive check and still flatten the ladder.
  ⭐ **The wheel is recorded as a first-class field**, because for THIS round
     the wheel is the thing that moved: the parent's `FPU_BITEXACT.json` was
     adjudicated on `carc_rs` binary `f6316d42838574de` under a ONE-WHEEL check,
     and the S1 `R7`/`R6` merge (commit `316df67d`) has since changed
     `carc_core::search` and `fair::search_worlds`.

WHAT THE GATE PROVES, AND WHAT IT DOES NOT.

  ⭐ **IDENTITY** — with the dose unset (`None`), play is BIT-IDENTICAL to the
     PRE-PLUMBING source, **on the wheel this round will actually play**. The
     round's opponent is the unmodified champion; a moved default would mean
     every rung grades a moved baseline.
  ⭐⭐ **POSITIVE, PER RUNG** — with the dose SET, play DIFFERS, at every one of
     `0.05 / 0.1 / 0.15 / 0.3`. ⛔ Without this half `IDENTITY` is worth
     nothing: the hard-coded `None` this family removed would have passed
     `IDENTITY` perfectly, every time.
  ⭐⭐ **DOSE-DISTINCT** — the four dosed legs differ FROM EACH OTHER. This is
     new, and it is the check a ladder specifically needs.
  ⛔ It proves NOTHING about whether any dose HELPS. That is what the four cells
     are for.

USAGE (see `run_golden_gate.sh`, which drives all six legs):

    PYTHONPATH=<OLD>/src:<OLD>/engine python identity_leg.py --out OLD.json
    PYTHONPATH=<NEW>/src:<NEW>/engine python identity_leg.py --out NEW.json
    PYTHONPATH=<NEW>/src:<NEW>/engine python identity_leg.py --fpu 0.05 \
        --out CTRL_005.json      # ... and 0.1 / 0.15 / 0.3

⚠️ THE BUDGET IS DELIBERATELY TINY (k2 x 96, not the champion's k16 x 1376). The
proposition is about a CODE PATH, not about a budget: `fpu_reduction` is read on
EVERY unvisited-child PUCT score, so a 96-sim search exercises it thousands of
times per move. ⛔ It is therefore NOT a strength measurement and no number in
it may be read as one.
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


#: The seeded decks the gate plays. ⛔ FROZEN: an identity claim over a
#: caller-chosen seed set is not a claim. ⚠️ DELIBERATELY THE SAME 20 SEEDS the
#: parent round's gate used, so the two artefacts are comparable leg-for-leg if
#: anyone ever wants to ask what the wheel move did.
#: ⛔ They are NOT on any band of this round or the parent's.
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
        # leg never restates the CLI value as if it were an observation.
        # ⚠️ `getattr(..., None)`: on the PRE-plumbing tree the attribute does
        # not EXIST, and "the field is absent" is precisely that leg's finding —
        # it must be recorded, not raised through.
        "resolved_fpu": getattr(cfg, "fpu_reduction", None),
        "resolved_c_puct": cfg.c_puct,
    }


def _rs_sha():
    try:
        from carcassonne_ai.rust_agent import carc_rs_binary_sha
        return carc_rs_binary_sha()
    except Exception:                                         # noqa: BLE001
        return "unavailable"


def _rs_build():
    try:
        from carcassonne_ai.rust_agent import carc_rs_build_id
        return carc_rs_build_id()
    except Exception:                                         # noqa: BLE001
        return "unavailable"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fpu", type=float, default=None,
                    help="candidate fpu_reduction; unset == the champion")
    ap.add_argument("--backend", default="rust", choices=("rust", "python"))
    ap.add_argument("--seeds", type=int, default=len(SEEDS),
                    help="how many of the FROZEN seeds to play (a smaller number "
                         "is a cheaper PREVIEW; the gate itself uses all of them)")
    ap.add_argument("--label", default="", help="leg label for the log line")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import carcassonne_ai
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig

    # ⭐ THE TREE WITNESS. The OLD and NEW legs differ ONLY in PYTHONPATH, so the
    # resolved package path is what proves the run is the leg it claims to be.
    tree = str(Path(carcassonne_ai.__file__).resolve().parents[2])
    has_field = "fpu_reduction" in HeuristicPriorConfig.__dataclass_fields__
    try:
        from carcassonne_ai.rust_agent import search_config_rs
        rs_repr = repr(search_config_rs(CF.production_prior_cfg(), 8))
    except Exception as e:                                    # noqa: BLE001
        rs_repr = f"<unavailable: {e}>"

    if args.fpu is not None and not has_field:
        # ⛔ THE AUDITED DEFECT, NAMED RATHER THAN CRASHED THROUGH. On the
        # pre-plumbing tree `--fpu` cannot even be expressed, so the leg is
        # recorded as what it is: a NO-OP that will hash identically to the
        # unset leg. That equality IS the finding.
        print("[identity_leg] ⛔ this tree's HeuristicPriorConfig has NO "
              "fpu_reduction field — the requested dose CANNOT be expressed. "
              "Recording the leg as REQUESTED-BUT-UNREACHABLE.", flush=True)

    t0 = time.perf_counter()
    games = []
    for s in SEEDS[: max(1, int(args.seeds))]:
        games.append(play(s, args.fpu if has_field else None, args.backend))
        print(f"[identity_leg] seed {s} -> {games[-1]['actions_sha256'][:16]} "
              f"({games[-1]['n_actions']} plies)", flush=True)

    out = {
        "fixture": "fpu_ladder golden gate",
        "label": args.label or ("NONE" if args.fpu is None else f"CTRL_{args.fpu}"),
        "requested_fpu": args.fpu,
        "knob_expressible_on_this_tree": has_field,
        "requested_but_unreachable": bool(args.fpu is not None and not has_field),
        "backend": args.backend,
        "src_tree": tree,
        # ⭐ ONE-WHEEL's witness. ⚠️⚠️ FOR THIS ROUND THE WHEEL IS THE THING THAT
        # MOVED, so `ladder_diff.py` not only asserts all six legs share it, it
        # STAMPS it into the artefact and `run_cells.sh` refuses unless the
        # stamped sha equals the launching box's own installed binary.
        "carc_rs_binary_sha": _rs_sha(),
        "carc_rs_build": _rs_build(),
        "search_config_rs_repr_at_champion": rs_repr,
        "budget": {"k_dets": K_DETS, "sims_per_det": SIMS_PER_DET,
                   "exact_k": EXACT_K,
                   "note": "⛔ NOT the champion's k16x1376 — this is a CODE-PATH "
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
    print(f"[identity_leg] leg_sha256 = {out['leg_sha256']}")
    print(f"[identity_leg] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
