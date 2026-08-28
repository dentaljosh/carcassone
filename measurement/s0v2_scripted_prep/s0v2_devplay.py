#!/usr/bin/env python3
"""S0v2 DEV HARNESS — pure-python, search-free games for validating the script.

⛔ NOT A MEASUREMENT.  This plays the scripted exploiter against a DEPTH-0 GREEDY
LEAF opponent so the plan module can be exercised, graded and regression-tested
in seconds instead of the ~4 s/ply a 2752-sim champion costs.  Nothing it emits
is a strength statement about anything: a greedy-leaf opponent is far below the
champion, so both the invasion rate and the margin it produces are dev signals
only.  The real instrument is ``s0v2_smoke.py``.

It writes archives in the E4 android-archive schema, so
``measurement/e4_exploit_grading_20260825/stage_a_census.py --games-dir <out>``
grades them unmodified — which is how the script's own detector is checked
against the census that scores it.

Usage:
    PYTHONPATH=<tree>/src:<tree>/engine python s0v2_devplay.py \
        --games 4 --seed-start 1234 --out /tmp/s0v2_dev
"""
from __future__ import annotations

import argparse
import json
import os
import random
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

os.environ.setdefault("CARCASSONNE_FIX_R9", "1")
for _v in ("CARCASSONNE_INVASION_ALPHA", "CARCASSONNE_INVASION_ALPHA_CAP",
           "CARCASSONNE_INVASION_BETA", "CARCASSONNE_INVASION_GAMMA",
           "CARCASSONNE_INVASION_DELTA_FARM", "CARCASSONNE_JRULES_DOSE"):
    os.environ.setdefault(_v, "0.0")

import numpy as np                                        # noqa: E402
sys.path.insert(0, str(HERE))

from carcassonne_ai import flat_leaf                       # noqa: E402
from carcassonne_ai import rules_profile as RP             # noqa: E402
from carcassonne_ai.game_wrapper import Game               # noqa: E402
from s0v2_agent import PlanConfig, ScriptedExploiter       # noqa: E402

RULES_PROFILE = "fixed_v1"


class GreedyLeafAgent:
    """Depth-0 argmax of the production flat leaf.  Deterministic; ties -> lowest
    action index.  No mirror, so ``_drives_mirror`` is False for it."""

    def __init__(self, game, leaf_cfg=None, seed: int = 0):
        self.game = game
        self.leaf_cfg = leaf_cfg
        self.seed = int(seed)

    def move(self, board) -> int:
        me = int(board.state.current_player)
        best, best_a = None, None
        for a in np.flatnonzero(self.game.get_valid_moves(board)):
            a = int(a)
            child, _ = self.game.get_next_state(board, a)
            v = flat_leaf.flat_virtual_score_v2_float(child.state, me, self.leaf_cfg)
            if best is None or v > best:
                best, best_a = v, a
        return int(best_a)


def make_agents(game, cfg: PlanConfig, seed: int, leaf_cfg=None):
    a = ScriptedExploiter(GreedyLeafAgent(game, leaf_cfg, seed), game, cfg,
                          leaf_cfg=leaf_cfg, seed=seed, label="S0v2-dev")
    b = GreedyLeafAgent(game, leaf_cfg, seed)
    return a, b


def play_one(seed: int, a_seat: int, cfg: PlanConfig, leaf_cfg=None) -> dict:
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    exploiter, opponent = make_agents(game, cfg, seed, leaf_cfg)
    t0 = time.perf_counter()
    actions: list[int] = []
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        action = exploiter.move(board) if cur == a_seat else opponent.move(board)
        actions.append(int(action))
        board, _ = game.get_next_state(board, action)
        exploiter.advance(action)
    s0, s1 = (int(x) for x in board.state.scores)
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    return {
        "schema": "carcassonne-android-archive/v1",
        "ok": True,
        "deck_seed": int(seed),
        "actions": actions,
        "human_player": int(a_seat),
        "scores": [s0, s1],
        "rules_profile": RULES_PROFILE,
        "result": {"scores": [s0, s1], "diff": int(diff),
                   "winner": (None if s0 == s1 else (0 if s0 > s1 else 1))},
        "s0v2": {
            "dev": True, "cand_seat": int(a_seat),
            "telemetry": exploiter.telemetry(),
            "fires": exploiter.fires,
            "plans": [vars(p) for p in exploiter.ledger.plans],
            "moves": len(actions),
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "host": socket.gethostname(),
        },
    }


def _job(job):
    seed, a_seat, cfg = job
    RP.activate(RULES_PROFILE)
    return play_one(seed, a_seat, cfg)


def parse_cfg(pairs) -> PlanConfig:
    """``["stub_max_tiles=4", "setup_enabled=false"]`` -> PlanConfig.

    Types come from the dataclass's own field types, so a typo in a name or a
    value fails loudly instead of being silently ignored."""
    import dataclasses
    types = {f.name: f.type for f in dataclasses.fields(PlanConfig)}
    kw = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"--set expects key=value, got {p!r}")
        k, v = p.split("=", 1)
        k = k.strip()
        if k not in types:
            raise SystemExit(f"unknown PlanConfig field {k!r}")
        t = types[k]
        tn = t if isinstance(t, str) else getattr(t, "__name__", str(t))
        if tn.startswith("bool"):
            kw[k] = v.strip().lower() in ("1", "true", "yes", "on")
        elif tn.startswith("int"):
            kw[k] = int(v)
        elif tn.startswith("float"):
            kw[k] = float(v)
        else:
            kw[k] = v
    return PlanConfig(**kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--seed-start", type=int, default=1234)
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", default=[],
                    help="PlanConfig override, e.g. --set stub_max_tiles=4 "
                         "(repeatable; typed from the dataclass field type)")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    RP.activate(RULES_PROFILE)
    cfg = parse_cfg(args.set)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tot = {"merge_fires": 0, "foothold_fires": 0, "setup_fires": 0,
           "plans_started": 0, "plans_completed": 0}
    margins = []
    jobs = [(args.seed_start + i, s, cfg)
            for i in range(args.games) for s in (0, 1)]
    if args.workers > 1:
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        with ctx.Pool(processes=args.workers) as pool:
            recs = pool.map(_job, jobs, chunksize=1)
    else:
        recs = [_job(j) for j in jobs]
    for rec in recs:
        seed, a_seat = rec["deck_seed"], rec["human_player"]
        (out / f"seed{seed}_a{a_seat}.json").write_text(json.dumps(rec))
        t = rec["s0v2"]["telemetry"]
        for k in tot:
            tot[k] += t.get(k, 0) or 0
        margins.append(rec["result"]["diff"])
        print(f"  seed={seed} a{a_seat} diff={rec['result']['diff']:+d} "
              f"merge={t['merge_fires']} foothold={t['foothold_fires']} "
              f"setup={t['setup_fires']} "
              f"plans={t['plans_started']}/{t['plans_completed']} "
              f"{rec['s0v2']['elapsed_s']:.1f}s", flush=True)
    n = len(margins)
    print(f"[dev] {n} games  mean margin {sum(margins)/n:+.2f}  "
          f"merges/game {tot['merge_fires']/n:.3f}  "
          f"footholds/game {tot['foothold_fires']/n:.3f}  "
          f"setups/game {tot['setup_fires']/n:.3f}  "
          f"plan completion {tot['plans_completed']}/{tot['plans_started']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
