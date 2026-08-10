#!/usr/bin/env python3
"""Item-1 (farm-norm replay) build rider: adapt `jcz_match_20260809/confirm.jsonl`
into the `root_replay.load_games` contract so it can be pushed through
`corpus_stats.py` unmodified.

Two shape mismatches, both fixed here, nothing else touched:
  1. `load_games` requires an int `game_id`; confirm.jsonl has none. Synthesized
     as `deck_seed*10 + champ_seat` — each deck_seed appears exactly twice in
     confirm.jsonl (once per seat swap, `champ_seat` in {0,1}), so this is a
     collision-free, deterministic, reconstructable id.
  2. `load_games`/`corpus_stats._one` want `score_p0`/`score_p1` (used as
     `recorded_scores` to verify the replay); confirm.jsonl stores `scores`
     which this file already establishes is `[score of seat0, score of seat1]`
     (scores[champ_seat] == champ_score, scores[jcz_seat] == jcz_score, checked
     against every record on read).

Everything else (`champ_seat`, `jcz_seat`, `replicate`, `deck_hash`,
`final_agree`, `void`, the generator's own `replay_ok`) is carried through as
plain extra keys, which `root_replay.load_games` files under `GameRecord.meta`
without complaint. Pure reshape — no filtering, no game is dropped.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def adapt(in_path: str, out_path: str) -> int:
    src = Path(in_path)
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with src.open() as fh, dst.open("w") as out:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            champ_seat, jcz_seat = r["champ_seat"], r["jcz_seat"]
            scores = r["scores"]
            assert scores[champ_seat] == r["champ_score"], (r["deck_seed"], "champ score mismatch")
            assert scores[jcz_seat] == r["jcz_score"], (r["deck_seed"], "jcz score mismatch")
            game_id = r["deck_seed"] * 10 + champ_seat
            adapted = {
                "game_id": game_id,
                "deck_seed": r["deck_seed"],
                "actions": r["actions"],
                "score_p0": scores[0],
                "score_p1": scores[1],
                "champ_seat": champ_seat,
                "jcz_seat": jcz_seat,
                "replicate": r["replicate"],
                "deck_hash": r["deck_hash"],
                "final_agree": r["final_agree"],
                "void": r["void"],
                "src_replay_ok": r.get("replay_ok"),
            }
            out.write(json.dumps(adapted) + "\n")
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", help="jcz_match confirm.jsonl (or smoke.jsonl)")
    ap.add_argument("-o", "--out", required=True, help="adapted games jsonl to write")
    args = ap.parse_args()
    n = adapt(args.corpus, args.out)
    print(f"[jcz_confirm_adapter] wrote {n} adapted records -> {args.out}")


if __name__ == "__main__":
    main()
