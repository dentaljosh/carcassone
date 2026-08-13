#!/usr/bin/env python3
"""Reconstruct the ROOT of the 2026-08-13 JoshuaBot-confirm crash as a census root.

The crash (`measurement/joshuabot_20260812/CONFIRM_EXCLUSIONS.md`) is the only
GROUND TRUTH we have for search-internal window truncation: a real production
`SearchError::NoLegalActionsAtInterior` on a known cell. But the failing position
is mid-game and nothing on disk records the action prefix, so it cannot be fed to
`window_truncation_census.py` directly.

This replays the offending cell EXACTLY as `scripts/joshuabot/h2h.py::_play_cell_inner`
does -- same rules profile, same JoshuaBot variant, same
`champion_seed(deck_seed, joshua_seat)`, same `play_harness.play_game` loop -- with
one addition: it records the applied action sequence, and the CHAMPION'S OWN
`move_idx` at each of its decisions. When the champion raises, it writes a one-line
roots JSONL carrying the prefix, the ply, and (critically) `move_idx`.

⚠️ `move_idx` is NOT the ply. `FairAgent`'s determinization stream is seeded from
`det_seed_base(seed, move_idx)` where `move_idx` counts the agent's OWN decisions,
so at global ply 59 with the champion on seat 1 the agent is on its ~29th decision.
Feeding the ply instead would draw DIFFERENT determinization worlds and would not
reproduce the crash. The census reads a `move_idx` field off the root when present.

READ-ONLY: no engine/src/rust modification, no monkeypatching of the harness --
the play loop is a verbatim copy of `play_harness.play_game`'s (which returns only
aggregate telemetry, not the action list).

    .venv/bin/python scripts/measurement_infra/reconstruct_crash_root.py \\
        --deck-seed 126000000135 --joshua-seat 0 --j7-weight 0.0 \\
        --out measurement/window_truncation_20260813/crash_root.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "scripts", REPO / "scripts" / "joshuabot",
           REPO / "scripts" / "human_anchor"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--deck-seed", type=int, default=126000000135)
    ap.add_argument("--joshua-seat", type=int, default=0)
    ap.add_argument("--preset", default="current")
    ap.add_argument("--j7-weight", type=float, default=0.0)
    ap.add_argument("--j8-break-reserve-floor", action="store_true")
    ap.add_argument("--j9-avoid-cloisters", action="store_true")
    ap.add_argument("--profile", default="fixed_v1")
    ap.add_argument("--rust-threads", type=int, default=1)
    ap.add_argument("--sims", type=int, default=None)
    ap.add_argument("--k-dets", type=int, default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-raise", action="store_true",
                    help="exit 1 if the cell completes WITHOUT raising")
    a = ap.parse_args(argv)

    import h2h

    overrides = {"j7_weight": float(a.j7_weight),
                 "j8_break_reserve_floor": bool(a.j8_break_reserve_floor),
                 "j9_avoid_cloisters": bool(a.j9_avoid_cloisters)}
    h2h._worker_init(a.profile, a.rust_threads, a.sims, a.k_dets, a.preset, overrides)
    W = h2h._W
    prof = W["prof"]

    from carcassonne_ai import mirror_protocol as MP
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.joshua_bot import JoshuaBot

    joshua_seat = int(a.joshua_seat)
    champ_seat = 1 - joshua_seat
    cseed = h2h.champion_seed(a.deck_seed, joshua_seat)
    print(f"[cell] deck={a.deck_seed} joshua_seat={joshua_seat} champ_seat={champ_seat} "
          f"champion_seed={cseed} profile={a.profile} variant={W['variant_id']}", flush=True)

    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    bot = JoshuaBot(game, preset=W["preset"], overrides=W["overrides"])
    champ = make_production_champion("fair", game=game, seed=int(cseed), sims=W["sims"],
                                     k_dets=W["k_dets"], verify=True, **W["factory_kwargs"])
    agents = {joshua_seat: bot, champ_seat: champ}

    # --- play_harness.play_game's loop, verbatim, plus the action recorder ----
    random.seed(int(a.deck_seed))
    board = game.get_init_board()
    MP.seat(agents, board)
    actions: list[int] = []
    champ_decisions = 0
    t0 = time.time()
    out: dict = {}

    while game.get_game_ended(board, 0) == 0.0:
        seat = board.state.current_player
        agent = agents[seat]
        is_champ = (seat == champ_seat)
        mi = champ_decisions if is_champ else None
        try:
            act = int(agent.choose_action(board))
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:                       # noqa: BLE001
            print(f"\n[RAISED] ply={len(actions)} seat={seat} "
                  f"is_champion={is_champ} champ_move_idx={mi}", flush=True)
            print(f"  {type(exc).__name__}: {exc}", flush=True)
            out = {
                "rid": f"crash_{a.deck_seed}_s{joshua_seat}_p{len(actions)}",
                "deck_seed": int(a.deck_seed),
                "ply": len(actions),
                "actions": list(actions),
                "player_to_move": int(seat),
                "move_idx": mi,                    # the AGENT's counter, not the ply
                "champion_seed": int(cseed),
                "raised": True,
                "raiser_is_champion": bool(is_champ),
                "exc_type": type(exc).__name__,
                "exc": str(exc)[:2000],
                "traceback": "".join(traceback.format_exception(exc))[-3000:],
                "phase": board.state.phase.value,
                "n_legal_python": len(game.get_valid_moves_list(board))
                if hasattr(game, "get_valid_moves_list") else None,
                "rules_profile": a.profile,
                "joshua_seat": joshua_seat, "champ_seat": champ_seat,
                "joshua_variant_id": W["variant_id"],
                "checksum": game.string_representation(board),
                "secs_to_raise": round(time.time() - t0, 1),
            }
            break
        if is_champ:
            champ_decisions += 1
        actions.append(act)
        board, _ = game.get_next_state(board, act)
        MP.advance(agents, act)
        if len(actions) % 10 == 0:
            print(f"  ply {len(actions):>3}  champ_decisions={champ_decisions} "
                  f"({time.time() - t0:.0f}s)", flush=True)

    if not out:
        print(f"\n[NO RAISE] the cell completed in {time.time() - t0:.0f}s, "
              f"{len(actions)} plies, scores {list(board.state.scores)}", flush=True)
        out = {"rid": f"crash_{a.deck_seed}_s{joshua_seat}_COMPLETED",
               "deck_seed": int(a.deck_seed), "ply": len(actions), "actions": list(actions),
               "raised": False, "scores": list(board.state.scores),
               "rules_profile": a.profile, "champion_seed": int(cseed)}

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out) + "\n")
    print(f"[out] {a.out}", flush=True)
    if a.expect_raise and not out.get("raised"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
