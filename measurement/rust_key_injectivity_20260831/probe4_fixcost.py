#!/usr/bin/env python3
"""Probe 4 — what does the MERGE currently buy, i.e. what would a naive
"make the rust key injective on rotation" fix COST?

READ-ONLY. No production code touched.

The rust key folds rotations of a 180-symmetric tile onto one node.  Probe 1/3
show every such fold joins states that are the SAME POSITION, so the fold is a
correct TRANSPOSITION merge, and the `Node::alias` / `child_canon` machinery
(`search/mod.rs::link_child`) concentrates the duplicate's prior on the
canonical action instead of splitting PUCT visits across identical siblings.

If the python `_FIX_LEGAL_CACHE_KEY` signature were ported to the rust key, the
two rotations would get DIFFERENT keys, the alias would never fire, and the
root's branching factor would grow by the duplicate count.  This probe prices
that at REAL roots:

  n_legal              legal tile actions at the root
  n_distinct           distinct successor afterstates (what the key sees today)
  redundant_pct        (n_legal - n_distinct) / n_legal
  n_root_children      root children the search actually visited
  n_deduped            distinct child NODES among them (today)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OMD2 = REPO / "measurement" / "omd2_chain_values_20260830"
sys.path.insert(0, str(OMD2))

from probe_witnesses import load_corpus, prepare_env  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="fixed_v1")
    ap.add_argument("--roots", type=int, default=24)
    ap.add_argument("--sims", type=int, default=256)
    args = ap.parse_args()

    prepare_env(args.profile)
    import carc_rs
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import leaf_config_rs, search_config_rs

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    prior_cfg = CF.production_prior_cfg(leaf_cfg=cfg)
    scfg = search_config_rs(prior_cfg, args.sims)
    _ = leaf_config_rs(cfg)

    corpus = load_corpus()
    seeds = sorted(corpus)
    rows = []
    i = 0
    for seed in seeds:
        if len(rows) >= args.roots:
            break
        actions = corpus[seed]
        # one root per game, spread across the midgame
        target = 20 + (i * 7) % 90
        i += 1
        g = carc_rs.MirrorState.from_seed(str(seed))
        ok = True
        for a in actions[:target]:
            g.advance(int(a))
        if g.phase() != "tiles" or g.is_terminal():
            ok = False
        if not ok:
            continue
        legal = [int(a) for a in g.legal_actions()]

        keys = set()
        for a in legal:
            h = carc_rs.MirrorState.from_seed(str(seed))
            for x in actions[:target]:
                h.advance(int(x))
            h.advance(int(a))
            keys.add(h.string_repr())

        res = g.search_single(scfg)
        rc = len(res["root_children"])
        dd = len(res["deduped"])
        rows.append(
            {
                "seed": seed,
                "ply": target,
                "n_legal": len(legal),
                "n_distinct": len(keys),
                "redundant_pct": round(
                    100.0 * (len(legal) - len(keys)) / max(1, len(legal)), 2
                ),
                "n_root_children": rc,
                "n_deduped": dd,
                "visited_alias_pct": round(100.0 * (rc - dd) / max(1, rc), 2),
                "node_count": int(res["node_count"]),
            }
        )

    agg = {
        "roots": len(rows),
        "sims": args.sims,
        "sum_n_legal": sum(r["n_legal"] for r in rows),
        "sum_n_distinct": sum(r["n_distinct"] for r in rows),
        "pooled_redundant_pct": round(
            100.0
            * (sum(r["n_legal"] for r in rows) - sum(r["n_distinct"] for r in rows))
            / max(1, sum(r["n_legal"] for r in rows)),
            2,
        ),
        "sum_root_children": sum(r["n_root_children"] for r in rows),
        "sum_deduped": sum(r["n_deduped"] for r in rows),
        "pooled_visited_alias_pct": round(
            100.0
            * (
                sum(r["n_root_children"] for r in rows)
                - sum(r["n_deduped"] for r in rows)
            )
            / max(1, sum(r["n_root_children"] for r in rows)),
            2,
        ),
    }
    out = {"profile": args.profile, "aggregate": agg, "rows": rows}
    (HERE / f"FIXCOST_{args.profile}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(agg, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
