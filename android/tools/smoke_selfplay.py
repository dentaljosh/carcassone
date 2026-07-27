#!/usr/bin/env python3
"""Desktop smoke: drive ``android_bridge`` through a FULL game, both seats.

Not a strength measurement — a wiring check. It exercises exactly the call sequence the
Kotlin app makes (``new_game`` → loop of ``apply_action`` / ``ai_move`` → ``save_game``)
and fails loudly if the game does not terminate, a state object goes malformed, or a
score comes back implausible.

The "human" seat is driven by a seeded ``random.Random`` picking uniformly from
``state["legal"]["action_ids"]``; the AI seat runs the real agent through ``ai_move``.
Keep the budget tiny (the defaults are k1x16) unless you actually want to wait.

    python3 android/tools/smoke_selfplay.py                       # tier1, instant
    python3 android/tools/smoke_selfplay.py --opponent champion --sims 16 --k-dets 1
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
sys.path.insert(0, str(_REPO / "android" / "app" / "src" / "main" / "python"))

import android_bridge as B  # noqa: E402


def _j(s: str) -> dict:
    d = json.loads(s)
    if not d.get("ok"):
        raise SystemExit(f"bridge error: {json.dumps(d, indent=1)}")
    return d


def run(*, seed: int, human_player: int, opponent: str, sims, k_dets,
        verify: bool, max_plies: int, quiet: bool) -> dict:
    cfg = {"seed": seed, "human_player": human_player, "opponent": opponent,
           "verify": verify}
    if sims is not None:
        cfg["sims"] = sims
    if k_dets is not None:
        cfg["k_dets"] = k_dets

    t_build = time.perf_counter()
    st = _j(B.new_game(json.dumps(cfg)))
    build_s = time.perf_counter() - t_build

    rng = random.Random(seed ^ 0x5EED)
    ai_times: list[float] = []
    human_moves = 0
    plies = 0
    t0 = time.perf_counter()

    while not st["is_terminated"]:
        plies += 1
        if plies > max_plies:
            raise SystemExit(f"game did not terminate within {max_plies} plies")
        if st["is_human_turn"]:
            ids = st["legal"]["action_ids"]
            if not ids:
                raise SystemExit(f"no legal actions at ply {plies} "
                                 f"(phase {st['phase']}) but game not terminated")
            st = _j(B.apply_action(rng.choice(ids)))
            human_moves += 1
        else:
            st = _j(B.ai_move(st["generation"]))
            if st.get("stale"):
                raise SystemExit("unexpected stale ai_move in a single-threaded smoke")
            ai_times.append(float(st["elapsed_s"]))
        if not quiet and plies % 25 == 0:
            print(f"  ply {plies:3d}  scores={st['scores']}  "
                  f"tiles_left={st['tiles_remaining']}")

    wall = time.perf_counter() - t0
    save = _j(B.save_game())
    scores = st["scores"]
    result = st["result"]

    if sum(scores) <= 0:
        raise SystemExit(f"implausible final scores {scores}")
    if len(save["actions"]) != st["n_actions"]:
        raise SystemExit(f"action log length {len(save['actions'])} != "
                         f"n_actions {st['n_actions']}")
    # The log carries every APPLIED action; the driver loop only sees the decisions it
    # was asked for, because forced human passes are auto-applied inside the bridge.
    auto_passes = len(save["actions"]) - plies
    if auto_passes < 0:
        raise SystemExit(f"action log ({len(save['actions'])}) shorter than the "
                         f"{plies} driven plies")

    print(f"\nsmoke_selfplay: opponent={st['opponent_name']} seed={seed} "
          f"human_player={human_player}")
    print(f"  plies={plies} (human {human_moves}, ai {len(ai_times)})  "
          f"auto-passes={auto_passes}  actions={len(save['actions'])}  "
          f"wall={wall:.1f}s  agent_build={build_s:.2f}s")
    if ai_times:
        print(f"  ai move seconds: mean={statistics.fmean(ai_times):.3f} "
              f"median={statistics.median(ai_times):.3f} "
              f"max={max(ai_times):.3f} total={sum(ai_times):.1f}")
    print(f"  final scores P0={scores[0]} P1={scores[1]}  "
          f"diff={result['diff']}  {result['verdict']}")
    if st["budget_note"]:
        print(f"  ⚠ {st['budget_note']}")
    return {"plies": plies, "scores": scores, "ai_times": ai_times,
            "actions": save["actions"]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="smoke_selfplay",
                                description="Drive android_bridge through a full game.")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--human-player", type=int, default=0, choices=(0, 1))
    p.add_argument("--opponent", choices=("champion", "tier1"), default="tier1")
    p.add_argument("--sims", type=int, default=16,
                   help="per-determinization sims (champion only; omit for the "
                        "PRODUCTION.yaml budget via --sims -1)")
    p.add_argument("--k-dets", type=int, default=1)
    p.add_argument("--verify", action="store_true", default=False,
                   help="run champion_factory's runtime leaf proof at construction")
    p.add_argument("--max-plies", type=int, default=400)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)
    sims = None if a.sims is not None and a.sims < 0 else a.sims
    k_dets = None if a.k_dets is not None and a.k_dets < 0 else a.k_dets
    run(seed=a.seed, human_player=a.human_player, opponent=a.opponent,
        sims=sims, k_dets=k_dets, verify=a.verify, max_plies=a.max_plies,
        quiet=a.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
