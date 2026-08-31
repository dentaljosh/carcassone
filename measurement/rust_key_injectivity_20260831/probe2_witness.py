#!/usr/bin/env python3
"""Probe 2 — is the rust node-key collision REACHABLE inside ONE deployed search
tree, and are the merged states the same POSITION?

READ-ONLY. No production code is modified; every call is an existing
`carc_rs` binding.

Witness: the banked OM-D2 pair `(deck_seed 28000000011, ply 24, actions 949 /
951)` from `measurement/omd2_chain_values_20260830/COLLISION_WITNESS.json`.

Checks, in order:

  K1  rust `string_repr(S_a) == string_repr(S_b)` -- the RUST key collides
      (byte-exact to python's, so the python defect is inherited verbatim).
  K2  honest `legal_actions(S_a) != legal_actions(S_b)` -- the collision is
      OBSERVABLE in the action set (the farmer-corner label moves).
  K3  the two afterstates are the SAME POSITION:
        * `placed_tiles` differ ONLY in the rotation index of the tile just
          placed (same description, same coordinate);
        * `leaf_value` bit-identical;
        * the MULTISET of successor leaf values over every legal continuation
          is bit-identical (a behavioural isomorphism test that does not need
          to know the corner relabeling).
  K4  REACHABILITY in the deployed search: run `MirrorState.search_single` with
      a JSONL trace and check whether the two colliding ROOT actions descend
      into the SAME node digest (`sha256(string_representation)[:16]`).  If they
      do, ONE tree contained both -- the collision is reachable in production.
  K5  BLAST RADIUS: read the alias structure off `root_children` / `deduped` --
      do the two actions carry identical `(N, W)` (shared node), and does
      `deduped` keep only one of them (so only one can ever be CHOSEN)?
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

SEED, PLY, A1, A2 = 28000000011, 24, 949, 951


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="walled")
    ap.add_argument("--sims", type=int, default=256)
    args = ap.parse_args()

    prepare_env(args.profile)
    import carc_rs
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import leaf_config_rs, search_config_rs

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    leaf_rs = leaf_config_rs(cfg)
    prior_cfg = CF.production_prior_cfg(leaf_cfg=cfg)

    actions = load_corpus()[SEED]

    def at_parent():
        g = carc_rs.MirrorState.from_seed(str(SEED))
        for a in actions[:PLY]:
            g.advance(int(a))
        return g

    parent = at_parent()
    legal_parent = [int(x) for x in parent.legal_actions()]

    def after(a):
        g = at_parent()
        g.advance(int(a))
        return g

    sa, sb = after(A1), after(A2)

    # ---- K1 / K2 --------------------------------------------------------- #
    ka, kb = sa.string_repr(), sb.string_repr()
    la = [int(x) for x in sa.legal_actions()]
    lb = [int(x) for x in sb.legal_actions()]

    # ---- K3 -------------------------------------------------------------- #
    pa = {(r, c): (d, rot) for r, c, d, rot in sa.placed_tiles()}
    pb = {(r, c): (d, rot) for r, c, d, rot in sb.placed_tiles()}
    tile_diffs = sorted(
        (k, pa[k], pb[k]) for k in set(pa) | set(pb) if pa.get(k) != pb.get(k)
    )

    def successor_leaf_multiset(st, seat):
        out = []
        for a in st.legal_actions():
            g2 = at_parent()
            # rebuild: MirrorState has no clone binding, so replay
            g2.advance(int(A1 if st is sa else A2))
            g2.advance(int(a))
            out.append(g2.leaf_value(seat, leaf_rs))
        return Counter(out)

    seat = int(sa.current_player())
    msa = successor_leaf_multiset(sa, seat)
    msb = successor_leaf_multiset(sb, seat)

    k3 = {
        "placed_tile_diffs": [
            {"coord": list(k), "a": list(x), "b": list(y)} for k, x, y in tile_diffs
        ],
        "diff_is_rotation_label_only": bool(tile_diffs)
        and all(x[0] == y[0] and x[1] != y[1] for _k, x, y in tile_diffs)
        and len(tile_diffs) == 1,
        "leaf_value_a": sa.leaf_value(seat, leaf_rs),
        "leaf_value_b": sb.leaf_value(seat, leaf_rs),
        "leaf_value_identical": sa.leaf_value(seat, leaf_rs)
        == sb.leaf_value(seat, leaf_rs),
        "successor_leaf_multiset_identical": msa == msb,
        "n_successors": [len(la), len(lb)],
    }

    # ---- K4 / K5 --------------------------------------------------------- #
    # The PRODUCTION champion search config, only the sim count reduced.
    scfg = search_config_rs(prior_cfg, args.sims)
    trace = HERE / "witness_trace.jsonl"
    res = parent.search_single(scfg, trace_path=str(trace))

    # first-action -> set of child digests, straight off the trace
    child_of = {}
    with trace.open() as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("t") != "sim" or not r.get("acts"):
                continue
            a0 = int(r["acts"][0])
            child_of.setdefault(a0, set()).add(r["path"][1])

    d1, d2 = child_of.get(A1, set()), child_of.get(A2, set())
    rc = {int(a): (int(n), int(w)) for a, n, w in res["root_children"]}
    dedup = {int(a) for a, _n, _w in res["deduped"]}

    k4 = {
        "sims": args.sims,
        "both_actions_visited_in_one_tree": bool(d1) and bool(d2),
        "child_digest_a": sorted(d1),
        "child_digest_b": sorted(d2),
        "SAME_NODE_IN_ONE_TREE": bool(d1) and d1 == d2,
    }
    k5 = {
        "root_children_a": rc.get(A1),
        "root_children_b": rc.get(A2),
        "root_children_NW_identical": rc.get(A1) is not None
        and rc.get(A1) == rc.get(A2),
        "a_in_deduped": A1 in dedup,
        "b_in_deduped": A2 in dedup,
        "exactly_one_of_the_pair_survives_dedup": (A1 in dedup) != (A2 in dedup),
        "chosen_action": int(res["chosen_action"]),
        "n_root_children": len(rc),
        "n_deduped": len(dedup),
        "node_count": int(res["node_count"]),
    }

    out = {
        "profile": args.profile,
        "witness": {"deck_seed": SEED, "ply": PLY, "actions": [A1, A2]},
        "parent_n_legal": len(legal_parent),
        "K1_rust_key_collides": ka == kb,
        "K1_key_len": len(ka),
        "K2_honest_legal_actions_differ": la != lb,
        "K2_legal_a": la,
        "K2_legal_b": lb,
        "K2_a_minus_b": sorted(set(la) - set(lb)),
        "K2_b_minus_a": sorted(set(lb) - set(la)),
        "K3_same_position": k3,
        "K4_reachable_in_one_deployed_tree": k4,
        "K5_blast_radius": k5,
    }
    (HERE / f"WITNESS_{args.profile}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
