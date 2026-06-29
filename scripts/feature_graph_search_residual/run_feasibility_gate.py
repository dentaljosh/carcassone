#!/usr/bin/env python3
"""FGSR Stage 0.5 — cheap feasibility gate.

Samples ~50 residual roots stratified across phases (incl. opening) + several
DECISIVE-TAIL roots (h200's top move != h6400's top move). Replays -> decompose ->
extract_graph + action nodes. Times each. Emits:

  measurement/feature_graph_search_residual/feasibility.json
  measurement/feature_graph_search_residual/FEASIBILITY.md

The go/no-go for schema usefulness is the TAIL-SIGNAL CHECK: on the decisive-tail
roots, do the structural node attributes (contested_flag, open_edges / exposure,
meeple lockup, completed_value) actually DIFFER across the two children h200 and
h6400 disagree on? If not -> the graph carries no tail signal -> STOP (Decision A/B).

NET-FREE, CPU. Set the frozen v2.9 env FIRST (before importing engine).
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "scripts" / "measurement_infra",):
    sys.path.insert(0, str(_p))
from snapshot import set_frozen_v29_env, frozen_v29_cfg, FROZEN_V29_HASH  # noqa: E402
set_frozen_v29_env()

import json  # noqa: E402
import time  # noqa: E402
import statistics  # noqa: E402
import numpy as np  # noqa: E402

for _p in (REPO / "src", REPO / "scripts", REPO / "scripts" / "feature_graph_search_residual",
           REPO / "scripts" / "post_search_residual", REPO / "scripts" / "feature_graph"):
    sys.path.insert(0, str(_p))

import extract_graph as EG  # noqa: E402
import psr_lib  # noqa: E402
from measurement_infra import replay_actions, load_games_dict  # noqa: E402

DATA = REPO / "measurement" / "post_search_residual" / "data"
OUT = REPO / "measurement" / "feature_graph_search_residual"
ROOTS = DATA / "roots_mcts.jsonl"
GAMES = DATA / "games_mcts.jsonl"

PHASES = ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]

# structural action-node scalars we check for tail signal (FEAT_NAMES indices)
TAIL_FEATS = [
    "T2_n_cities_contested", "T2_n_farms_contested", "T2_total_city_open_edges",
    "T2_n_meeples_locked_self", "T2_n_meeples_locked_opp",
    "T2_completed_value_self_div8", "T2_completed_value_opp_div8",
    "T2_d_total_city_open_edges", "T2_d_n_open_cities", "T2_d_meeples_locked_self",
    "T2_d_n_contested", "T2_opp_feature_touched", "T2_feature_completed_by_move",
    "T2_n_open_cities", "T2_max_open_city_value_self_div8",
]


def _load_records():
    """game_id->record map of the full roots jsonl (raw, all fields)."""
    recs = {}
    for line in ROOTS.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        recs[(int(r["game_id"]), int(r["ply"]))] = r
    return recs


def _best_action(levelmap):
    return psr_lib._best_action({str(a): v for a, v in levelmap.items()})


def sample_roots(n_per_phase=6, n_tail=20, seed=0):
    rng = np.random.default_rng(seed)
    rows = psr_lib.load_roots(str(ROOTS))  # the 10,351 filtered, derived rows
    by_phase = {p: [r for r in rows if r["phase"] == p] for p in PHASES}
    decisive = [r for r in rows if r["sel"][200] != r["sel"][6400]]  # 3007
    strong_tail = [r for r in rows if r["pos_strong"] and r["sel"][200] != r["sel"][6400]]  # 287

    chosen = {}
    # phase-stratified ordinary sample
    for p in PHASES:
        pool = by_phase[p]
        idx = rng.choice(len(pool), size=min(n_per_phase, len(pool)), replace=False)
        for i in idx:
            r = pool[i]
            chosen[(r["game_id"], r["ply"])] = r
    # decisive-tail: prefer strong_tail, fill from general decisive
    tail_pool = strong_tail if len(strong_tail) >= n_tail else strong_tail + decisive
    idx = rng.choice(len(tail_pool), size=min(n_tail, len(tail_pool)), replace=False)
    tail_keys = set()
    for i in idx:
        r = tail_pool[i]
        chosen[(r["game_id"], r["ply"])] = r
        tail_keys.add((r["game_id"], r["ply"]))
    return list(chosen.values()), tail_keys


def tail_signal_check(action_nodes, feat_names, sel200, sel6400):
    """Compare the structural attributes of the two children h200 vs h6400 pick.
    Returns dict: which TAIL_FEATS differ + magnitudes, plus a verdict bool."""
    fi = {n: i for i, n in enumerate(feat_names)}
    by_aid = {an["action_id"]: an for an in action_nodes}
    a200 = by_aid.get(sel200)
    a6400 = by_aid.get(sel6400)
    if a200 is None or a6400 is None:
        return {"available": False}
    diffs = {}
    n_differ = 0
    for name in TAIL_FEATS:
        i = fi[name]
        v200 = float(a200["feat"][i])
        v6400 = float(a6400["feat"][i])
        d = v6400 - v200
        if abs(d) > 1e-9:
            n_differ += 1
        diffs[name] = {"h200_child": round(v200, 4), "h6400_child": round(v6400, 4),
                       "delta": round(d, 4)}
    # also surface the leaf-Q and search-Q gap between the two children
    diffs["_leaf_q_gap"] = round(a6400["leaf_q"] - a200["leaf_q"], 4)
    diffs["_q6400_gap"] = round(a6400["q6400_rootpov"] - a200["q6400_rootpov"], 4)
    return {"available": True, "n_struct_attrs_differ": n_differ,
            "n_struct_attrs_checked": len(TAIL_FEATS), "diffs": diffs,
            "any_signal": n_differ > 0}


def main():
    cfg = frozen_v29_cfg()  # asserts config_hash == FROZEN_V29_HASH
    recs = _load_records()
    sampled, tail_keys = sample_roots()
    games = load_games_dict(str(GAMES))
    print(f"[gate] sampled {len(sampled)} roots ({len(tail_keys)} decisive-tail); "
          f"leaf {FROZEN_V29_HASH}")

    per_root = []
    tail_results = []
    errors = []
    for r in sampled:
        key = (r["game_id"], r["ply"])
        raw = recs[key]
        try:
            t0 = time.perf_counter()
            game, board = replay_actions(int(r["seed"]), games[r["game_id"]], int(r["ply"]))
            t_replay = (time.perf_counter() - t0) * 1000
            t1 = time.perf_counter()
            graph, anodes, fnames = EG.extract_root(game, board, raw, root_player=raw["root_player"])
            t_extract = (time.perf_counter() - t1) * 1000

            # size estimate: action-node feat matrix + a compact graph attr count
            n_action_scalars = len(anodes) * len(fnames)
            graph_attr_count = sum(len(nd) for nds in graph["nodes"].values() for nd in nds)
            est_bytes = (n_action_scalars * 4 +          # float32 action feats
                         len(anodes) * 6 * 4 +           # N/Q at 3 levels
                         graph_attr_count * 4 +          # graph node attrs (mixed)
                         graph["meta"]["n_edges"] * 4 * 4)  # 4 ints/edge

            rec_out = {
                "game_id": r["game_id"], "ply": r["ply"], "phase": r["phase"],
                "legal_n": r["legal_n"], "is_tail": key in tail_keys,
                "n_nodes": graph["meta"]["n_nodes"], "n_edges": graph["meta"]["n_edges"],
                "node_counts": graph["meta"]["node_counts"],
                "edge_counts": graph["meta"]["edge_counts"],
                "n_action_nodes": len(anodes),
                "ms_replay": round(t_replay, 2), "ms_extract": round(t_extract, 2),
                "est_bytes": int(est_bytes),
            }
            per_root.append(rec_out)

            if key in tail_keys:
                tc = tail_signal_check(anodes, fnames, r["sel"][200], r["sel"][6400])
                tc.update({"game_id": r["game_id"], "ply": r["ply"], "phase": r["phase"],
                           "sel200": r["sel"][200], "sel6400": r["sel"][6400],
                           "regret200": round(r["regret"][200], 4),
                           "q_gap_6400": round(r["q_gap_6400"], 4)})
                tail_results.append(tc)
        except Exception as e:
            import traceback
            errors.append({"key": key, "err": f"{type(e).__name__}: {e}",
                           "tb": traceback.format_exc()})

    # ---- aggregate ---------------------------------------------------------- #
    def _pct(xs, p):
        return float(np.percentile(xs, p)) if xs else None

    extract_ms = [pr["ms_extract"] for pr in per_root]
    total_ms = [pr["ms_extract"] + pr["ms_replay"] for pr in per_root]
    nodes = [pr["n_nodes"] for pr in per_root]
    edges = [pr["n_edges"] for pr in per_root]
    bytes_ = [pr["est_bytes"] for pr in per_root]

    # edge/node count distribution by type (mean over roots)
    def _typewise(field):
        agg = {}
        for pr in per_root:
            for t, v in pr[field].items():
                agg.setdefault(t, []).append(v)
        return {t: {"mean": round(statistics.mean(vs), 1),
                    "min": min(vs), "max": max(vs)} for t, vs in agg.items()}

    tail_with_signal = [t for t in tail_results if t.get("available") and t.get("any_signal")]
    tail_avail = [t for t in tail_results if t.get("available")]
    tail_signal_rate = (len(tail_with_signal) / len(tail_avail)) if tail_avail else 0.0
    mean_attrs_differ = (statistics.mean([t["n_struct_attrs_differ"] for t in tail_avail])
                         if tail_avail else 0.0)

    summary = {
        "leaf_config_hash": FROZEN_V29_HASH,
        "n_sampled": len(sampled), "n_ok": len(per_root), "n_errors": len(errors),
        "n_tail_sampled": len(tail_keys), "n_tail_evaluated": len(tail_avail),
        "node_count": {"mean": round(statistics.mean(nodes), 1) if nodes else 0,
                       "p50": _pct(nodes, 50), "p90": _pct(nodes, 90),
                       "min": min(nodes) if nodes else 0, "max": max(nodes) if nodes else 0},
        "edge_count": {"mean": round(statistics.mean(edges), 1) if edges else 0,
                       "p50": _pct(edges, 50), "p90": _pct(edges, 90),
                       "min": min(edges) if edges else 0, "max": max(edges) if edges else 0},
        "node_count_by_type": _typewise("node_counts"),
        "edge_count_by_type": _typewise("edge_counts"),
        "extract_ms": {"mean": round(statistics.mean(extract_ms), 2) if extract_ms else 0,
                       "p50": _pct(extract_ms, 50), "p90": _pct(extract_ms, 90)},
        "total_ms_per_root": {"mean": round(statistics.mean(total_ms), 2) if total_ms else 0,
                              "p50": _pct(total_ms, 50), "p90": _pct(total_ms, 90)},
        "est_bytes_per_root": {"mean": int(statistics.mean(bytes_)) if bytes_ else 0,
                               "p50": _pct(bytes_, 50), "p90": _pct(bytes_, 90)},
        "tail_signal": {
            "n_tail_evaluated": len(tail_avail),
            "n_tail_with_signal": len(tail_with_signal),
            "tail_signal_rate": round(tail_signal_rate, 3),
            "mean_struct_attrs_differ": round(mean_attrs_differ, 2),
            "n_struct_attrs_checked": len(TAIL_FEATS),
            "verdict": "PASS" if tail_signal_rate >= 0.8 else ("WEAK" if tail_signal_rate >= 0.5 else "FAIL"),
        },
        "errors": errors[:5],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    full = {"summary": summary, "per_root": per_root, "tail_results": tail_results}
    (OUT / "feasibility.json").write_text(json.dumps(full, indent=2))
    print("[gate] wrote", OUT / "feasibility.json")
    print(json.dumps(summary, indent=2))

    _write_md(summary, tail_results)


def _write_md(summary, tail_results):
    s = summary
    ts = s["tail_signal"]
    # pick 2 concrete tail examples with signal
    examples = [t for t in tail_results if t.get("available") and t.get("any_signal")][:3]
    lines = []
    lines.append("# FEASIBILITY.md — FGSR Stage 0.5 cheap feasibility gate\n")
    verdict = ts["verdict"]
    badge = {"PASS": "🟢 GATE PASSES", "WEAK": "🟡 GATE WEAK", "FAIL": "🔴 GATE FAILS"}[verdict]
    lines.append(f"> **STATUS: {badge}** — tail-signal rate "
                 f"{ts['tail_signal_rate']:.0%} on {ts['n_tail_evaluated']} decisive-tail roots; "
                 f"extraction mean {s['extract_ms']['mean']:.1f} ms/root, "
                 f"mean graph {s['node_count']['mean']:.0f} nodes / {s['edge_count']['mean']:.0f} edges.\n")
    lines.append(f"> Leaf config_hash `{s['leaf_config_hash']}` (frozen v2.9). "
                 f"{s['n_ok']}/{s['n_sampled']} roots extracted OK, {s['n_errors']} errors. "
                 f"NET-FREE, CPU. _2026-06-29._\n")

    lines.append("\n## Graph size (per root)\n")
    lines.append("| metric | mean | p50 | p90 | min | max |")
    lines.append("|---|---|---|---|---|---|")
    nc, ec = s["node_count"], s["edge_count"]
    lines.append(f"| nodes | {nc['mean']} | {nc['p50']:.0f} | {nc['p90']:.0f} | {nc['min']} | {nc['max']} |")
    lines.append(f"| edges | {ec['mean']} | {ec['p50']:.0f} | {ec['p90']:.0f} | {ec['min']} | {ec['max']} |")

    lines.append("\n### Node counts by type (mean / min / max)\n")
    lines.append("| node type | mean | min | max |")
    lines.append("|---|---|---|---|")
    for t, d in s["node_count_by_type"].items():
        lines.append(f"| {t} | {d['mean']} | {d['min']} | {d['max']} |")
    lines.append("\n### Edge counts by type (mean / min / max)\n")
    lines.append("| edge type | mean | min | max |")
    lines.append("|---|---|---|---|")
    for t, d in s["edge_count_by_type"].items():
        lines.append(f"| {t} | {d['mean']} | {d['min']} | {d['max']} |")

    lines.append("\n## Extraction cost\n")
    em, tm, eb = s["extract_ms"], s["total_ms_per_root"], s["est_bytes_per_root"]
    lines.append("| metric | mean | p50 | p90 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| extract ms/root | {em['mean']} | {em['p50']:.1f} | {em['p90']:.1f} |")
    lines.append(f"| total ms/root (replay+extract) | {tm['mean']} | {tm['p50']:.1f} | {tm['p90']:.1f} |")
    lines.append(f"| est bytes/root | {eb['mean']} | {eb['p50']:.0f} | {eb['p90']:.0f} |")
    est_full = int(eb["mean"] * 10351)
    lines.append(f"\nProjected full-dataset size (10,351 roots × mean est_bytes) ≈ "
                 f"**{est_full/1e6:.1f} MB** uncompressed (compresses well — mostly float32).\n")

    lines.append("\n## TAIL-SIGNAL CHECK (the go/no-go)\n")
    lines.append(f"On the **{ts['n_tail_evaluated']} decisive-tail roots** (h200 top move != h6400 "
                 f"top move), do the structural action-node attributes differ across the two children "
                 f"h200 and h6400 disagree on?\n")
    lines.append(f"- **{ts['n_tail_with_signal']}/{ts['n_tail_evaluated']} "
                 f"({ts['tail_signal_rate']:.0%})** show ≥1 differing structural attribute.")
    lines.append(f"- Mean **{ts['mean_struct_attrs_differ']:.1f} of "
                 f"{ts['n_struct_attrs_checked']}** checked structural attrs differ per tail root.")
    lines.append(f"- **Verdict: {verdict}.** "
                 + ("The schema captures discriminating structure on the decisive tail — proceed to Stage 2."
                    if verdict == "PASS" else
                    ("Signal is present but partial — proceed with caution / inspect."
                     if verdict == "WEAK" else
                     "No tail signal — the graph does not separate the contested moves (Decision A/B). STOP.")))

    if examples:
        lines.append("\n### Concrete examples (h200-child vs h6400-child structural attrs that differ)\n")
        for ex in examples:
            lines.append(f"**Root game {ex['game_id']} ply {ex['ply']} ({ex['phase']})** — "
                         f"h200 picks action {ex['sel200']}, h6400 picks {ex['sel6400']}; "
                         f"regret(h200)={ex['regret200']}, q_gap_6400={ex['q_gap_6400']}. "
                         f"leaf-Q gap between the two children = {ex['diffs']['_leaf_q_gap']}, "
                         f"h6400-Q gap = {ex['diffs']['_q6400_gap']}.")
            diffed = {k: v for k, v in ex["diffs"].items()
                      if not k.startswith("_") and abs(v["delta"]) > 1e-9}
            lines.append("")
            lines.append("| struct attr | h200 child | h6400 child | Δ (6400−200) |")
            lines.append("|---|---|---|---|")
            for k, v in list(diffed.items())[:8]:
                lines.append(f"| {k} | {v['h200_child']} | {v['h6400_child']} | {v['delta']} |")
            lines.append("")

    lines.append("\n## Schema notes / choices made\n")
    lines.append("- `open_boundary` FOLDED into feature `open_edges`/`open_ends` + "
                 "`feature_has_open_boundary` edges to a singleton sentinel (schema open-question, "
                 "'fold first').")
    lines.append("- `tile` ply-placed recency omitted (not stored on state); move recency lives on "
                 "action nodes.")
    lines.append("- `road_feature.open_ends` reduced to a has-open binary (precise endpoint scan needs "
                 "node-side data; deferred).")
    lines.append("- Action-node attrs = the comparator pilot's 50 per-child scalars "
                 "(`build_feat_dataset.FEAT_NAMES`), reused verbatim; h200/h800/h6400 (N, Q_rootpov) "
                 "joined from `roots_mcts.jsonl levels`.")
    lines.append("- Owner/contested derived with the SAME meeple→root mapping `flat_leaf._final_scores` "
                 "uses (`city_side_root`/`road_side_root`/`farm_pos0_root` + `_winners`).")

    (OUT / "FEASIBILITY.md").write_text("\n".join(lines) + "\n")
    print("[gate] wrote", OUT / "FEASIBILITY.md")


if __name__ == "__main__":
    main()
