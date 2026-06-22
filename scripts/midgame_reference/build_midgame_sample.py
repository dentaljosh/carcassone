#!/usr/bin/env python3
"""Midgame reference (Phase 1) — construct the midgame/opening position sample.

Reuses the full-game ACTION PREFIXES in /mnt/c/carc-shared/l23_k4_expand.jsonl (50 games each
from greedy / heur@3200 / hybrid:8:3200 / iter8, ply ~135 ending at K=4). Each prefix passes
through every tiles-remaining value, so replaying it to EARLIER plies snapshots midgame
positions at target K-bands — all four source distributions, free, no MCTS at gen time.

Bands (tiles remaining K): 52=opening 40=early_mid 28=mid 16=late_mid 10=pre_endgame — all ABOVE
the exact-solver region (K<=4). Each snapshot stores its own action prefix so Phase 2/3 replay
deterministically via replay_actions(seed, prefix).

Out: MIDGAME_POSITION_SAMPLE.jsonl (one line per position) + MIDGAME_SAMPLE_MANIFEST.json.
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")

import argparse
import json
import random
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

from carcassonne_ai.game_wrapper import Game                          # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase      # noqa: E402

BANDS = {52: "opening", 40: "early_mid", 28: "mid", 16: "late_mid", 10: "pre_endgame"}


def k_remaining(board) -> int:
    return len(board.state.deck) + (1 if board.state.next_tile is not None else 0)


def snapshot_game(rec, want_ks):
    """Replay rec['actions'] once; snapshot first TILES position at each target K.
    Returns list of position dicts (each with its own action prefix for replay)."""
    seed = rec["seed"]
    actions = rec["actions"]
    source = rec["source_agent"]
    random.seed(seed)                       # fixes the deck shuffle (same as the generators)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    seen = {}
    for i, a in enumerate(actions):
        if board.state.phase == GamePhase.TILES:
            k = k_remaining(board)
            if k in want_ks and k not in seen:
                s = board.state
                deck_descs = [t.description for t in s.deck]
                mover = int(s.current_player)
                seen[k] = {
                    "position_id": f"{source.replace(':', '_').replace('@', '')}_s{seed}_K{k}",
                    "source_bucket": source,
                    "source_game_seed": seed,
                    "ply": i,
                    "prefix": actions[:i],                  # replay_actions(seed, prefix) -> this board
                    "k_remaining": k,
                    "tiles_remaining": len(deck_descs),
                    "band": BANDS[k],
                    "phase": "TILES",
                    "to_move": mover,
                    "scores": [int(s.scores[0]), int(s.scores[1])],
                    "score_diff_mover": int(s.scores[mover] - s.scores[1 - mover]),
                    "meeples_free": [int(s.meeples[0]), int(s.meeples[1])],
                    "in_hand_tile": s.next_tile.description if s.next_tile is not None else None,
                    "n_legal_tile_actions": int(game.get_valid_moves(board).sum()),
                    "bag_size": len(deck_descs),
                    "bag_multiset": dict(sorted(Counter(deck_descs).items())),
                    # honesty flags (brief Phase 1):
                    "known_deck": True,            # the future deck order is fixed/known on the board
                    "fair_information": False,     # NOT bag-marginalized; search descends the real order
                    "clairvoyance": "real_deck_order",  # see REUSE_AND_SCOPE.md
                    "label_availability": "teacher+agent+static (NO exact solver at midgame K)",
                }
        board, _ = game.get_next_state(board, int(a))
        if len(seen) == len(want_ks):
            break
    return [seen[k] for k in sorted(seen, reverse=True)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/mnt/c/carc-shared/l23_k4_expand.jsonl")
    ap.add_argument("--out", default=os.path.join(REPO, "measurement", "midgame_reference"))
    ap.add_argument("--ks", type=int, nargs="+", default=sorted(BANDS, reverse=True))
    args = ap.parse_args(argv)
    want = set(args.ks)

    recs = [json.loads(l) for l in open(args.src)]
    print(f"[phase1] {len(recs)} source games, bands K={sorted(want, reverse=True)}", flush=True)

    positions = []
    for rec in recs:
        positions.extend(snapshot_game(rec, want))
    positions.sort(key=lambda p: (-p["k_remaining"], p["source_bucket"], p["source_game_seed"]))

    out_path = os.path.join(args.out, "MIDGAME_POSITION_SAMPLE.jsonl")
    with open(out_path, "w") as fh:
        for p in positions:
            fh.write(json.dumps(p) + "\n")

    by_src = Counter(p["source_bucket"] for p in positions)
    by_band = Counter(p["band"] for p in positions)
    by_src_band = Counter((p["source_bucket"], p["band"]) for p in positions)
    legal_by_band = defaultdict(list)
    for p in positions:
        legal_by_band[p["band"]].append(p["n_legal_tile_actions"])
    manifest = {
        "dataset": "MIDGAME_POSITION_SAMPLE.jsonl",
        "purpose": "Phase 1 midgame/opening position sample for the midgame reference build.",
        "built_by": "scripts/midgame_reference/build_midgame_sample.py",
        "source_file": args.src,
        "bands_tiles_remaining": BANDS,
        "n_positions": len(positions),
        "counts_by_source_bucket": dict(by_src),
        "counts_by_band": {b: by_band[b] for b in BANDS.values()},
        "counts_by_source_x_band": {f"{s}|{b}": n for (s, b), n in sorted(by_src_band.items())},
        "median_legal_tile_actions_by_band": {
            b: (sorted(legal_by_band[b])[len(legal_by_band[b]) // 2] if legal_by_band[b] else None)
            for b in BANDS.values()
        },
        "label_availability": {
            "exact_solver": "NONE (midgame K is above the exact-solver region K<=4)",
            "deep_search_teacher": "heur@800/1600/3200 (Phase 3)",
            "learned_agent": "iter8 MCTS@200 + policy prior (Phase 3)",
            "static": "v2.7-depth-0 best action (Phase 3)",
        },
        "honesty_flags": {
            "known_deck": True,
            "fair_information": False,
            "clairvoyance": "real_deck_order — all search labels descend the fixed deck; "
                            "clairvoyant-leaning, weaker leakage than endgame (see REUSE_AND_SCOPE.md)",
        },
    }
    with open(os.path.join(args.out, "MIDGAME_SAMPLE_MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"[phase1] wrote {len(positions)} positions -> {out_path}", flush=True)
    print(f"[phase1] by_source={dict(by_src)}", flush=True)
    print(f"[phase1] by_band={ {b: by_band[b] for b in BANDS.values()} }", flush=True)
    print(f"[phase1] median legal tile-actions by band="
          f"{ {b: (sorted(legal_by_band[b])[len(legal_by_band[b])//2] if legal_by_band[b] else None) for b in BANDS.values()} }",
          flush=True)


if __name__ == "__main__":
    main()
