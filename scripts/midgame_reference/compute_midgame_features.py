#!/usr/bin/env python3
"""Midgame reference (Phase 2) — scoring-resolved per-action features + bag-aware quantities.

REUSE: the corrected scoring-resolved afterstate logic is imported verbatim from the pre-tool
audit (`build_action_audit_dataset._per_action_features` / `_resolve_turn`) so the base deltas
are byte-identical to the audit — NO re-introduction of the pre-scoring bug. On top, this adds
bag-aware features built from the production flat-leaf `decompose` and the v2.7 leaf's own
`_deck_city_supply`/`_supply_factor` (no new structural/heuristic code).

In : MIDGAME_POSITION_SAMPLE.jsonl (Phase 1)
Out: MIDGAME_ACTION_FEATURES.jsonl + MIDGAME_FEATURE_MANIFEST.json + FEATURE_VALIDATION.md
     (FEATURE_BACKLOG.md is authored separately — the deliberately-not-built quantities.)
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")

import argparse
import json
import sys
from collections import defaultdict
from multiprocessing import get_context

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

from gen_endgame_multisource import replay_actions                       # noqa: E402
from build_action_audit_dataset import _per_action_features, _resolve_turn  # noqa: E402 (REUSE)
from carcassonne_ai.flat_leaf import decompose                            # noqa: E402
from carcassonne_ai.virtual_score_v2 import _deck_city_supply, _supply_factor  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side                     # noqa: E402

CARDINAL = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)
DIAG_SLACK = 3.0  # diagnostic slack for the supply_factor (production slack is OFF=0.0); see REUSE_AND_SCOPE.md

# Per-action feature keys whose variation across legal actions we track (the "do features vary?" check).
TRACKED = [
    "imm_score_delta_mover", "imm_net_pass", "score_diff_after", "meeple_delta_mover",
    "completion_scored", "best_meeple_net", "claim_gain", "v27_score",
    "aff_city_min_open_after", "city_open_edge_delta", "road_open_edge_delta",
    "bag_city_supply", "completion_scarcity_bucket", "aff_city_owner",
]


def _board_open(decomp) -> tuple[int, int]:
    """(total open city positions, total open road sides) over all components — the cheap,
    unambiguous board-level open-edge proxy (per-component identity is not tracked across a
    merge; see FEATURE_BACKLOG)."""
    city_open = sum(decomp.city_root_open_n.get(root, 0)
                    for root, fin in decomp.city_root_finished.items() if not fin)
    # coarse road-open proxy: count of UNFINISHED road components (per-side open positions are not
    # tracked by decompose for roads; component count is the cheap unambiguous board-level signal).
    road_open = sum(1 for fin in decomp.road_root_finished.values() if not fin)
    return city_open, road_open


def _roots_owner(state, side_root, roots, mover) -> str:
    """self/opp/shared/empty over `roots` (mirrors flat_leaf._final_scores meeple iteration)."""
    if not roots:
        return "empty"
    counts = [0, 0]
    for player in range(2):
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            root = side_root.get((cws.coordinate.row, cws.coordinate.column, cws.side))
            if root in roots:
                counts[player] += 1
    self_n, opp_n = counts[mover], counts[1 - mover]
    if self_n == 0 and opp_n == 0:
        return "empty"
    if self_n > 0 and opp_n == 0:
        return "self"
    if opp_n > 0 and self_n == 0:
        return "opp"
    return "shared"


def _scarcity_bucket(supply: int, need: int) -> str:
    if need <= 0:
        return "none_open"      # the closest affected city has no open positions (closeable/closed)
    if supply <= 0:
        return "impossible"     # deck has no city-bearing tiles left -> cannot close from bag
    f = supply / need
    if f < 1.0:
        return "scarce"
    if f < 3.0:
        return "moderate"
    return "many"


def _bag_aware(game, board, mover, parent_open):
    """Return {action: bag-aware-feature-dict} for the legal TILES actions."""
    out = {}
    legal = np.flatnonzero(game.get_valid_moves(board))
    for a in legal:
        a = int(a)
        child1, _ = game.get_next_state(board, a)
        cs = child1.state
        # placed tile coordinate (the just-placed tile, BEFORE meeple resolution)
        lta = cs.last_tile_action
        pr, pc = lta.coordinate.row, lta.coordinate.column
        cd = decompose(cs)
        aff_city = {cd.city_side_root.get((pr, pc, s)) for s in CARDINAL}
        aff_city.discard(None)
        aff_road = {cd.road_side_root.get((pr, pc, s)) for s in CARDINAL}
        aff_road.discard(None)
        aff_city_unf = [r for r in aff_city if not cd.city_root_finished.get(r, True)]
        aff_road_unf = [r for r in aff_road if not cd.road_root_finished.get(r, True)]
        open_after_list = [cd.city_root_open_n.get(r, 0) for r in aff_city_unf]
        aff_min_open = min(open_after_list) if open_after_list else 0
        aff_city_potential_pts = sum(cd.city_root_delta.get(r, 0) for r in aff_city_unf)
        city_open_after, road_open_after = _board_open(cd)
        supply = _deck_city_supply(cs)
        out[a] = {
            "placed_rc": [int(pr), int(pc)],
            "aff_city_roots_n": len(aff_city),
            "aff_city_unfinished_n": len(aff_city_unf),
            "aff_road_roots_n": len(aff_road),
            "aff_road_unfinished_n": len(aff_road_unf),
            "aff_city_min_open_after": int(aff_min_open),
            "aff_city_potential_pts": int(aff_city_potential_pts),
            "city_open_edge_delta": int(parent_open[0] - city_open_after),  # +ve = removed open city edges
            "road_open_edge_delta": int(parent_open[1] - road_open_after),
            "bag_city_supply": int(supply),
            "completion_scarcity_bucket": _scarcity_bucket(supply, int(aff_min_open)),
            "bag_supply_factor": round(_supply_factor(supply, int(aff_min_open), DIAG_SLACK), 4),
            "aff_city_owner": _roots_owner(cs, cd.city_side_root, aff_city, mover),
            "aff_road_owner": _roots_owner(cs, cd.road_side_root, aff_road, mover),
        }
    return out


def _process(pos):
    try:
        game, board = replay_actions(pos["source_game_seed"], pos["prefix"])
        mover, base = _per_action_features(game, board)        # REUSED corrected deltas
        parent_open = _board_open(decompose(board.state))
        bag = _bag_aware(game, board, mover, parent_open)
    except Exception as e:
        return {"_error": f"{pos['position_id']}: {type(e).__name__}: {e}"}

    actions = []
    for a in sorted(base):
        f = dict(base[a])
        f.update(bag.get(a, {}))
        actions.append(f)
    # per-feature variation (informative = NOT constant across this position's legal actions)
    varies = {}
    for k in TRACKED:
        vals = {json.dumps(f.get(k)) for f in actions}
        varies[k] = len(vals) > 1
    return {
        "position_id": pos["position_id"], "source_bucket": pos["source_bucket"],
        "band": pos["band"], "k_remaining": pos["k_remaining"], "to_move": mover,
        "score_diff_mover": pos["score_diff_mover"], "n_actions": len(actions),
        "in_hand_tile": pos["in_hand_tile"], "actions": actions, "_varies": varies,
    }


def _validation_md(lines, out_dir):
    """Write FEATURE_VALIDATION.md: >=20 positions with before/after examples proving the
    per-action features vary across legal actions where they should (the v1-audit-bug guard)."""
    import random as _r
    rng = _r.Random(20260621)
    sample = rng.sample(lines, min(25, len(lines)))
    md = ["# Phase 2 — Feature Validation (guard against the pre-scoring bug)",
          "",
          "> The v1 pre-tool audit read per-action deltas one half-move too early, so every delta was",
          "> CONSTANT across legal actions (an artifact). This file proves the midgame features VARY",
          "> across legal actions where they should — by showing, for 25 randomly-sampled positions,",
          "> how many distinct values each feature takes across that position's legal tile actions,",
          "> plus concrete before/after action examples. **FACT** (computed from the dataset).", ""]
    md.append("## Per-position feature variation (distinct values across legal actions)")
    md.append("")
    md.append("| position_id | band | n_act | v27 | imm_net | best_meeple | aff_min_open | scarcity | owner |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for ln in sample:
        acts = ln["actions"]
        def nd(k):
            return len({json.dumps(a.get(k)) for a in acts})
        md.append(f"| {ln['position_id']} | {ln['band']} | {ln['n_actions']} | "
                  f"{nd('v27_score')} | {nd('imm_net_pass')} | {nd('best_meeple_net')} | "
                  f"{nd('aff_city_min_open_after')} | {nd('completion_scarcity_bucket')} | "
                  f"{nd('aff_city_owner')} |")
    md.append("")
    md.append("(Each cell = # distinct values that feature takes across the position's legal actions. "
              ">1 everywhere a feature is meaningful ⇒ NOT the constant-delta artifact.)")
    md.append("")
    # concrete before/after examples: pick 3 positions, show 2 contrasting actions each
    md.append("## Concrete before/after action contrasts (3 positions, 2 actions each)")
    md.append("")
    for ln in sample[:3]:
        acts = sorted(ln["actions"], key=lambda a: a.get("v27_score", 0))
        lo, hi = acts[0], acts[-1]
        md.append(f"### {ln['position_id']} (band={ln['band']}, k={ln['k_remaining']}, "
                  f"in_hand={ln['in_hand_tile']}, n_act={ln['n_actions']})")
        md.append("")
        md.append("| action | type | v27 | imm_net | best_meeple | meeple_Δ | completion | "
                  "aff_min_open | scarcity | city_open_Δ | owner |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for tag, a in (("worst-v27", lo), ("best-v27", hi)):
            md.append(f"| {a['action']} ({tag}) | {a['action_type']} | {a['v27_score']} | "
                      f"{a['imm_net_pass']} | {a['best_meeple_net']} | {a['meeple_delta_mover']} | "
                      f"{a['completion_scored']} | {a['aff_city_min_open_after']} | "
                      f"{a['completion_scarcity_bucket']} | {a['city_open_edge_delta']} | "
                      f"{a['aff_city_owner']} |")
        md.append("")
    with open(os.path.join(out_dir, "FEATURE_VALIDATION.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(REPO, "measurement", "midgame_reference"))
    ap.add_argument("--workers", type=int, default=14)
    args = ap.parse_args(argv)

    positions = [json.loads(l) for l in open(os.path.join(args.dir, "MIDGAME_POSITION_SAMPLE.jsonl"))]
    print(f"[phase2] {len(positions)} positions, W={args.workers}", flush=True)

    ctx = get_context("fork")
    with ctx.Pool(args.workers) as pool:
        results = list(pool.imap_unordered(_process, positions, chunksize=8))
    errors = [r for r in results if "_error" in r]
    lines = [r for r in results if "_error" not in r]
    lines.sort(key=lambda x: (-x["k_remaining"], x["source_bucket"], x["position_id"]))

    out_path = os.path.join(args.dir, "MIDGAME_ACTION_FEATURES.jsonl")
    with open(out_path, "w") as fh:
        for ln in lines:
            row = {k: v for k, v in ln.items() if k != "_varies"}
            fh.write(json.dumps(row) + "\n")

    # informative fraction per feature, overall + by band
    n = len(lines)
    inf_overall = {k: round(sum(1 for ln in lines if ln["_varies"][k]) / n, 4) for k in TRACKED}
    by_band = defaultdict(list)
    for ln in lines:
        by_band[ln["band"]].append(ln)
    inf_by_band = {b: {k: round(sum(1 for ln in v if ln["_varies"][k]) / len(v), 4) for k in TRACKED}
                   for b, v in by_band.items()}
    n_action_rows = sum(ln["n_actions"] for ln in lines)
    manifest = {
        "dataset": "MIDGAME_ACTION_FEATURES.jsonl",
        "purpose": "Phase 2 per-action scoring-resolved features + bag-aware quantities for the midgame sample.",
        "built_by": "scripts/midgame_reference/compute_midgame_features.py",
        "reused": "build_action_audit_dataset._per_action_features/_resolve_turn (corrected deltas, byte-identical); "
                  "flat_leaf.decompose; virtual_score_v2._deck_city_supply/_supply_factor",
        "n_positions": n, "n_action_rows": n_action_rows, "errors": len(errors),
        "diagnostic_supply_slack": DIAG_SLACK,
        "feature_informative_fraction_overall": inf_overall,
        "feature_informative_fraction_by_band": inf_by_band,
        "note": "informative_fraction = fraction of positions where the feature takes >1 distinct value "
                "across that position's legal tile actions (i.e. carries ranking signal there). This is the "
                "direct test of 'do features vary in midgame'. completion_scarcity_bucket/aff_city_owner are "
                "categorical; variation = >1 distinct category.",
    }
    with open(os.path.join(args.dir, "MIDGAME_FEATURE_MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    _validation_md(lines, args.dir)

    print(f"[phase2] wrote {n} positions, {n_action_rows} action rows -> {out_path}", flush=True)
    if errors:
        print(f"[phase2] ERRORS ({len(errors)}): {[e['_error'] for e in errors[:5]]}", flush=True)
    print("[phase2] informative fraction overall:")
    for k in TRACKED:
        print(f"   {k:28s} {inf_overall[k]:.3f}", flush=True)


if __name__ == "__main__":
    main()
