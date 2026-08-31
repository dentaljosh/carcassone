#!/usr/bin/env python3
"""Probe 3 — how OFTEN does the rust key collide inside a real game, and does the
collision ever separate two states BEHAVIOURALLY?

READ-ONLY. Every call is an existing `carc_rs` binding; nothing is written
outside this directory.

Walks banked champion games (`measurement/champ_action_logs/champ_games.jsonl`).
At every TILES ply it groups the legal TILE actions by the RUST node key
(`string_repr` of the successor).  A group of size > 1 is a KEY COLLISION — the
deployed search's `Tree::intern` would fold those successors onto ONE node.

For each collision group it asks whether the members are the SAME POSITION:

  S1  `placed_tiles` differ only in the ROTATION index of one tile
      (same description, same coordinate);
  S2  `leaf_value` bit-identical at the acting seat;
  S3  the honest legal-action lists differ (the farmer-corner LABEL moves) —
      this is the OBSERVABLE, and it is what the python `_legal_cache` bug rode;
  S4  a full `tier1-greedy` playout to TERMINAL, HONEST mask
      (`legal_mask_cache=False`), same world seed and same playout seed for
      every member, ends on the SAME margin.  S4 is the strong test: it plays
      the whole rest of the game out of each member and compares the result.

And, separately, it prices the RUST `LegalMaskCache` (`tier1::LegalMaskCache`,
`legal_mask_cache=True`) — the ONE rust structure that keys an ACTION LIST on
the non-injective key — by re-running the same playouts with the memo ON.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OMD2 = REPO / "measurement" / "omd2_chain_values_20260830"
sys.path.insert(0, str(OMD2))

from probe_witnesses import load_corpus, prepare_env  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="walled")
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--groups-per-game", type=int, default=12)
    ap.add_argument("--worlds", type=int, default=2)
    args = ap.parse_args()

    prepare_env(args.profile)
    import carc_rs
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import leaf_config_rs

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    leaf_rs = leaf_config_rs(cfg)

    corpus = load_corpus()
    seeds = sorted(corpus)[: args.games]

    tot = {
        "tile_plies": 0,
        "tile_actions": 0,
        "collision_groups": 0,
        "collision_actions": 0,
        "group_sizes": Counter(),
        "tiles": Counter(),
    }
    checked = []
    fails = {"S1": 0, "S2": 0, "S3_no_observable": 0, "S4": 0}
    cache_moved = 0
    cache_pairs = 0

    for seed in seeds:
        actions = corpus[seed]
        g = carc_rs.MirrorState.from_seed(str(seed))
        n_groups_here = 0
        for ply, played in enumerate(actions):
            if g.phase() != "tiles":
                g.advance(int(played))
                continue
            legal = [int(a) for a in g.legal_actions()]
            seat = int(g.current_player())
            tot["tile_plies"] += 1
            tot["tile_actions"] += len(legal)

            def succ(a):
                h = carc_rs.MirrorState.from_seed(str(seed))
                for x in actions[:ply]:
                    h.advance(int(x))
                h.advance(int(a))
                return h

            by_key = {}
            for a in legal:
                by_key.setdefault(succ(a).string_repr(), []).append(a)
            groups = [v for v in by_key.values() if len(v) > 1]
            tot["collision_groups"] += len(groups)
            tot["collision_actions"] += sum(len(v) for v in groups)
            for v in groups:
                tot["group_sizes"][len(v)] += 1

            for grp in groups:
                base = succ(grp[0])
                pa = {(r, c): (d, rot) for r, c, d, rot in base.placed_tiles()}
                lv0 = base.leaf_value(seat, leaf_rs)
                la0 = [int(x) for x in base.legal_actions()]
                for a in grp[1:]:
                    other = succ(a)
                    pb = {
                        (r, c): (d, rot) for r, c, d, rot in other.placed_tiles()
                    }
                    diffs = [k for k in set(pa) | set(pb) if pa.get(k) != pb.get(k)]
                    s1 = (
                        len(diffs) == 1
                        and pa[diffs[0]][0] == pb[diffs[0]][0]
                        and pa[diffs[0]][1] != pb[diffs[0]][1]
                    )
                    if s1:
                        tot["tiles"][pa[diffs[0]][0]] += 1
                    lv1 = other.leaf_value(seat, leaf_rs)
                    la1 = [int(x) for x in other.legal_actions()]
                    if not s1:
                        fails["S1"] += 1
                    if lv0 != lv1:
                        fails["S2"] += 1
                    if la0 == la1:
                        fails["S3_no_observable"] += 1

                if n_groups_here >= args.groups_per_game:
                    continue
                n_groups_here += 1
                # --- S4: play the rest of the game out of every member ------ #
                prefix = [int(x) for x in actions[:ply]]
                for w in range(args.worlds):
                    ws = 1_000_003 * (w + 1) + seed % 97
                    ps = 7_654_321 * (w + 1) + ply
                    honest = []
                    memo = []
                    for a in grp:
                        r = carc_rs.tier1_playout_trace(
                            str(seed), prefix, ply, int(a), seat, ws, ps,
                            legal_mask_cache=False,
                        )
                        honest.append((r[1], r[2]))
                        r2 = carc_rs.tier1_playout_trace(
                            str(seed), prefix, ply, int(a), seat, ws, ps,
                            legal_mask_cache=True,
                        )
                        memo.append((r2[1], r2[2]))
                    same_honest = len(set(honest)) == 1
                    if not same_honest:
                        fails["S4"] += 1
                    cache_pairs += len(grp)
                    cache_moved += sum(
                        1 for h, m in zip(honest, memo) if h != m
                    )
                    checked.append(
                        {
                            "seed": seed,
                            "ply": ply,
                            "actions": grp,
                            "tile": pa[diffs[0]][0] if diffs else None,
                            "rots": [pa[diffs[0]][1], pb[diffs[0]][1]]
                            if diffs
                            else None,
                            "honest_margins": honest,
                            "memo_margins": memo,
                            "S4_same_margin_honest": same_honest,
                        }
                    )
            g.advance(int(played))

    out = {
        "profile": args.profile,
        "seeds": seeds,
        "census": {
            "tile_plies": tot["tile_plies"],
            "tile_actions": tot["tile_actions"],
            "collision_groups": tot["collision_groups"],
            "collision_actions": tot["collision_actions"],
            "pct_tile_actions_in_a_collision_group": round(
                100.0 * tot["collision_actions"] / max(1, tot["tile_actions"]), 3
            ),
            "group_sizes": dict(tot["group_sizes"]),
            "colliding_tiles": dict(tot["tiles"]),
        },
        "same_position_gates": {
            "S1_rotation_label_only_FAILURES": fails["S1"],
            "S2_leaf_value_identical_FAILURES": fails["S2"],
            "S3_pairs_with_NO_observable_action_diff": fails["S3_no_observable"],
            "S4_terminal_margin_identical_FAILURES": fails["S4"],
            "S4_playout_comparisons": len(checked),
        },
        "rust_LegalMaskCache_defect": {
            "playouts_compared": cache_pairs,
            "playouts_the_memo_MOVED": cache_moved,
            "pct": round(100.0 * cache_moved / max(1, cache_pairs), 3),
        },
        "detail": checked[:60],
    }
    (HERE / f"SWEEP_{args.profile}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "detail"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
