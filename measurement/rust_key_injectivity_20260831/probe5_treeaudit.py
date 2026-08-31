#!/usr/bin/env python3
"""Probe 5 — a WHOLE-TREE audit of one deployed rust search.

READ-ONLY.

Probe 3 checked SIBLING collisions (two tile actions at the same ply).  This
closes the remaining gap: inside a real search tree, is EVERY node that is
reached by more than one distinct action prefix a same-position merge?

Method: run `MirrorState.search_single` with the JSONL trace, read every `sim`
record's `(path, acts)`, and build `node digest -> {action prefix}`.  Any digest
with >= 2 distinct prefixes is a MERGE the tree actually performed.  Each such
merge is then replayed from the root and the two resulting states compared:

  * `placed_tiles` -- must differ ONLY in rotation indices (same descriptions,
    same coordinates);
  * `scores`, `meeples`, `deck_len`, `phase`, `current_player` -- must match;
  * `leaf_value` at both seats -- must match.

A merge that fails any of these would be two DIFFERENT positions sharing a node,
i.e. a production correctness bug.
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
    ap.add_argument("--roots", type=int, default=8)
    ap.add_argument("--sims", type=int, default=400)
    args = ap.parse_args()

    prepare_env(args.profile)
    import carc_rs
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import leaf_config_rs, search_config_rs

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    prior_cfg = CF.production_prior_cfg(leaf_cfg=cfg)
    scfg = search_config_rs(prior_cfg, args.sims)
    leaf_rs = leaf_config_rs(cfg)

    corpus = load_corpus()
    seeds = sorted(corpus)
    trace = HERE / "tree_audit_trace.jsonl"

    totals = {
        "roots": 0,
        "nodes_seen": 0,
        "merged_nodes": 0,
        "merge_pairs": 0,
        "FAIL_not_rotation_only": 0,
        "FAIL_scalar_mismatch": 0,
        "FAIL_leaf_mismatch": 0,
        "merge_tiles": {},
    }
    examples = []

    for i, seed in enumerate(seeds[: args.roots]):
        actions = corpus[seed]
        target = 24 + (i * 9) % 80
        base_prefix = [int(a) for a in actions[:target]]

        def state(extra):
            h = carc_rs.MirrorState.from_seed(str(seed))
            for a in base_prefix:
                h.advance(int(a))
            for a in extra:
                h.advance(int(a))
            return h

        root = state([])
        if root.is_terminal():
            continue
        totals["roots"] += 1
        root.search_single(scfg, trace_path=str(trace), trace_expansions=False)

        by_digest = {}
        with trace.open() as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("t") != "sim":
                    continue
                path, acts = r["path"], [int(a) for a in r["acts"]]
                for d in range(len(acts)):
                    by_digest.setdefault(path[d + 1], set()).add(tuple(acts[: d + 1]))
        totals["nodes_seen"] += len(by_digest)

        for dig, prefixes in by_digest.items():
            if len(prefixes) < 2:
                continue
            totals["merged_nodes"] += 1
            ps = sorted(prefixes)
            ref = state(ps[0])
            rp = {(r, c): (dd, rot) for r, c, dd, rot in ref.placed_tiles()}
            rscal = (
                tuple(ref.scores()),
                tuple(ref.meeples()),
                ref.deck_len(),
                ref.phase(),
                ref.current_player(),
            )
            rleaf = (ref.leaf_value(0, leaf_rs), ref.leaf_value(1, leaf_rs))
            for p in ps[1:]:
                totals["merge_pairs"] += 1
                oth = state(p)
                op = {(r, c): (dd, rot) for r, c, dd, rot in oth.placed_tiles()}
                diffs = [k for k in set(rp) | set(op) if rp.get(k) != op.get(k)]
                rot_only = all(
                    k in rp and k in op and rp[k][0] == op[k][0] for k in diffs
                )
                oscal = (
                    tuple(oth.scores()),
                    tuple(oth.meeples()),
                    oth.deck_len(),
                    oth.phase(),
                    oth.current_player(),
                )
                oleaf = (oth.leaf_value(0, leaf_rs), oth.leaf_value(1, leaf_rs))
                if not rot_only:
                    totals["FAIL_not_rotation_only"] += 1
                    examples.append(
                        {
                            "seed": seed, "root_ply": target, "digest": dig,
                            "prefix_a": list(ps[0]), "prefix_b": list(p),
                            "tile_diffs": [
                                {"coord": list(k), "a": rp.get(k), "b": op.get(k)}
                                for k in diffs
                            ],
                        }
                    )
                else:
                    for k in diffs:
                        totals["merge_tiles"][rp[k][0]] = (
                            totals["merge_tiles"].get(rp[k][0], 0) + 1
                        )
                if rscal != oscal:
                    totals["FAIL_scalar_mismatch"] += 1
                if rleaf != oleaf:
                    totals["FAIL_leaf_mismatch"] += 1

    out = {
        "profile": args.profile,
        "sims_per_root": args.sims,
        "totals": totals,
        "failures": examples[:20],
        "verdict": (
            "every multi-prefix node in every audited tree is a SAME-POSITION merge"
            if totals["FAIL_not_rotation_only"]
            == totals["FAIL_scalar_mismatch"]
            == totals["FAIL_leaf_mismatch"]
            == 0
            else "AT LEAST ONE NODE MERGED TWO DIFFERENT POSITIONS"
        ),
    }
    (HERE / f"TREE_AUDIT_{args.profile}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
