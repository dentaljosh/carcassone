#!/usr/bin/env python3
"""Merge per-game action-log shards into ONE root_replay games jsonl (+ verify).

`gen_fair_distill.py --log-actions` writes one `actions/seed_<seed>.json` per game
(lock-free over the CIFS share). This collects them into the house replayable-corpus
format — the same `{game_id, deck_seed, actions, n_plies, ...}` jsonl that
`measurement/window_audit/gen_games.jsonl` uses and that
`scripts/measurement_infra/root_replay.load_games` / `scripts/release/replay_audit.py` /
`scripts/f3_public_state_oracle/mine_roots.py --source champion` consume.

`--verify N` REPLAYS N randomly-chosen games end-to-end and asserts the reconstructed
final scores equal the scores recorded at generation time — the round-trip proof that the
log is losslessly replayable (a log that cannot be replayed bit-exactly is worthless).

Usage:
  scripts/distill_flywheel/collect_action_logs.py \
      --in  /mnt/c/carc-shared/champ_action_logs_20260720 \
      --out measurement/champ_action_logs/champ_games.jsonl --verify 10
"""
from __future__ import annotations

import os

# Champion leaf env before any carcassonne_ai import (replay itself is leaf-independent,
# but keep the whole toolchain on the production shape). Mirrors gen_fair_distill.
for _k, _v in {
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}.items():
    os.environ.setdefault(_k, _v)

import argparse  # noqa: E402
import json  # noqa: E402
import random as _pyrandom  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))


def load_shards(indir: Path) -> list[dict]:
    d = indir if indir.name == "actions" else (indir / "actions")
    if not d.is_dir():
        raise SystemExit(f"no actions/ dir under {indir}")
    recs = []
    for p in sorted(d.glob("seed_*.json")):
        try:
            recs.append(json.loads(p.read_text()))
        except Exception as e:  # noqa - a torn shard must never kill the merge
            print(f"[warn] unreadable shard {p.name}: {e}", file=sys.stderr)
    return recs


def verify(recs: list[dict], n: int, seed: int = 0) -> tuple[int, int, list[str]]:
    """Replay n sampled games to the terminal; check plies + final scores round-trip."""
    import root_replay as RR

    rng = _pyrandom.Random(seed)
    sample = recs if n >= len(recs) else rng.sample(recs, n)
    ok = bad = 0
    errs = []
    for r in sample:
        acts = r["actions"]
        game, board = RR.replay_actions(r["deck_seed"], acts, len(acts))
        s0, s1 = int(board.state.scores[0]), int(board.state.scores[1])
        ended = game.get_game_ended(board, 0) != 0.0
        exp0, exp1 = r.get("score_p0"), r.get("score_p1")
        problems = []
        if not ended:
            problems.append("not terminal after replaying every action")
        if exp0 is not None and (s0, s1) != (int(exp0), int(exp1)):
            problems.append(f"scores {s0}-{s1} != recorded {exp0}-{exp1}")
        if int(r.get("n_plies", len(acts))) != len(acts):
            problems.append(f"n_plies {r['n_plies']} != len(actions) {len(acts)}")
        if problems:
            bad += 1
            errs.append(f"game {r['game_id']}: " + "; ".join(problems))
        else:
            ok += 1
    return ok, bad, errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="collect_action_logs")
    ap.add_argument("--in", dest="indir", required=True,
                    help="gen output dir (containing actions/) or the actions/ dir itself")
    ap.add_argument("--out", required=True, help="merged games jsonl")
    ap.add_argument("--verify", type=int, default=10,
                    help="replay this many sampled games end-to-end and check the round-trip "
                         "(0 = skip; a nonzero failure count exits 1)")
    args = ap.parse_args(argv)

    recs = load_shards(Path(args.indir))
    if not recs:
        raise SystemExit("no action shards found")
    recs.sort(key=lambda r: int(r["game_id"]))

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    plies = [int(r.get("n_plies", len(r["actions"]))) for r in recs]
    print(f"wrote {len(recs)} games to {outp} "
          f"(plies min/med/max = {min(plies)}/{sorted(plies)[len(plies)//2]}/{max(plies)})")

    if args.verify:
        ok, bad, errs = verify(recs, args.verify)
        for e in errs:
            print(f"  [FAIL] {e}", file=sys.stderr)
        print(f"round-trip verify: {ok} ok / {bad} bad (of {ok+bad} replayed)")
        if bad:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
