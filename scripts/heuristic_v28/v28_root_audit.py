#!/usr/bin/env python3
"""Phase 4 — root-action audit of the v2.8 variants as STATIC selectors.

Each variant is evaluated as a depth-0 argmax of its leaf over legal afterstates, on the
EXISTING labelled datasets — NO neural net, NO cluster, pure CPU. Two references:

  MIDGAME (1000 positions, soft teacher labels): replay MIDGAME_POSITION_SAMPLE via `prefix`,
    score each child with `virtual_score_v2(child.state, mover, cfg)` (the same root-action method
    the midgame labels used), compare each variant's argmax to the heur@3200 teacher. By band /
    source / v2.7-miss / per-patch target subset. v27_baseline must reproduce the known ~0.48.

  ENDGAME K=2 (150 positions, EXACT clairvoyant solver): reconstruct via replay_to(seed, ply),
    score the meeple-PASS-resolved afterstate (matches the corrected v27_score_resolved baseline),
    map each variant's argmax tile-action to its `solver_regret_clair`. top-1 = regret==0.

Measurement only. No training / promotion. Champion + production defaults unchanged.

Out: measurement/heuristic_v28/V28_ROOT_AUDIT.jsonl          (per-position midgame variant picks)
     measurement/heuristic_v28/V28_ROOT_AUDIT_RESULTS.csv    (per-variant overall)
     measurement/heuristic_v28/V28_ROOT_AUDIT_BY_SUBSET.csv  (per-variant x subset)
"""
from __future__ import annotations
import os, sys, json, csv, time, random
import dataclasses as dc
from collections import defaultdict
from multiprocessing import get_context

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "heuristic_v28"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

import v28_configs                                   # noqa: E402
v28_configs.set_prod_env()                           # v2.7 base BEFORE importing the leaf
import numpy as np                                   # noqa: E402
from carcassonne_ai.game_wrapper import Game         # noqa: E402
from carcassonne_ai.virtual_score_v2 import virtual_score_v2  # noqa: E402
from gen_endgame_positions import replay_to          # noqa: E402
from build_action_audit_dataset import _resolve_turn  # noqa: E402

MID_POS = os.path.join(REPO, "measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl")
MID_LAB = os.path.join(REPO, "measurement/midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl")
END_DS = os.path.join(REPO, "measurement/pre_tool_audit/ACTION_AUDIT_DATASET.jsonl")
FAIL_CASES = os.path.join(REPO, "measurement/heuristic_v28/V27_FAILURE_CASES.csv")
OUT_JSONL = os.path.join(REPO, "measurement/heuristic_v28/V28_ROOT_AUDIT.jsonl")
OUT_RESULTS = os.path.join(REPO, "measurement/heuristic_v28/V28_ROOT_AUDIT_RESULTS.csv")
OUT_SUBSET = os.path.join(REPO, "measurement/heuristic_v28/V28_ROOT_AUDIT_BY_SUBSET.csv")

VARIANTS = v28_configs.build_variants()   # {name: LeafConfig}
VNAMES = list(VARIANTS.keys())

# per-midgame-pid target-patch tag (from the Phase-1 failure CSV)
_PATCH_OF = {}
for r in csv.DictReader(open(FAIL_CASES)):
    if r["dataset"] == "midgame":
        _PATCH_OF[r["position_id"]] = r["candidate_patch"]


def _argmax_static(game, board, cfg, resolve=False):
    """Action maximizing the variant leaf over legal afterstates (strict >, sorted order =
    first/lowest-id max, matching the label tie-break). resolve=True scores the meeple-PASS
    resolved afterstate (endgame, == v27_score_resolved); else the immediate child."""
    mover = board.state.current_player
    legal = np.flatnonzero(game.get_valid_moves(board))
    best_a, best_v = None, None
    for a in legal:
        a = int(a)
        child, _ = game.get_next_state(board, a)
        st = child.state
        if resolve:
            pass_st, _best = _resolve_turn(game, child, mover)
            st = pass_st.state
        v = virtual_score_v2(st, mover, cfg)
        if best_v is None or v > best_v:
            best_v, best_a = v, a
    return best_a


# ---------------- midgame ----------------
def _mid_worker(pos):
    try:
        random.seed(pos["source_game_seed"])
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        for a in pos["prefix"]:
            b, _ = g.get_next_state(b, int(a))
        picks = {name: _argmax_static(g, b, cfg, resolve=False) for name, cfg in VARIANTS.items()}
        return {"position_id": pos["position_id"], "band": pos["band"],
                "source_bucket": pos["source_bucket"], "k_remaining": pos["k_remaining"],
                "picks": picks}
    except Exception as e:
        return {"_error": f"{pos['position_id']}: {type(e).__name__}: {e}"}


# ---------------- endgame K=2 ----------------
def _end_worker(rec):
    try:
        g, b = replay_to(rec["source_game_seed"], rec["ply"])
        regret_of = {int(a["action"]): float(a["solver_regret_clair"]) for a in rec["actions"]
                     if a.get("solver_regret_clair") is not None}
        out = {"position_id": rec["position_id"], "picks": {}, "regret": {}}
        for name, cfg in VARIANTS.items():
            a = _argmax_static(g, b, cfg, resolve=True)
            out["picks"][name] = a
            out["regret"][name] = regret_of.get(a)
        return out
    except Exception as e:
        return {"_error": f"{rec['position_id']}: {type(e).__name__}: {e}"}


def main():
    workers = int(os.environ.get("V28_WORKERS", "14"))
    ctx = get_context("fork")

    # ---- MIDGAME ----
    positions = [json.loads(l) for l in open(MID_POS)]
    labels = {json.loads(l)["position_id"]: json.loads(l) for l in open(MID_LAB)}
    print(f"[v28-root] midgame: {len(positions)} positions, W={workers}", flush=True)
    t0 = time.perf_counter()
    with ctx.Pool(workers) as pool:
        mid = [r for r in pool.imap_unordered(_mid_worker, positions, chunksize=8)]
    errs = [r for r in mid if "_error" in r]
    mid = [r for r in mid if "_error" not in r]
    print(f"[v28-root] midgame done {len(mid)} rows, {len(errs)} errors, {(time.perf_counter()-t0)/60:.1f} min", flush=True)
    if errs:
        print("  sample errors:", [e["_error"] for e in errs[:3]], flush=True)

    with open(OUT_JSONL, "w") as fh:
        for r in mid:
            lab = labels[r["position_id"]]
            r["teacher"] = lab["heur3200_choice"]
            r["v27_static_label"] = lab["v27_static_choice"]
            r["iter8_choice"] = lab["iter8_choice"]
            r["heur800_choice"] = lab["heur800_choice"]
            fh.write(json.dumps(r) + "\n")

    # aggregate midgame agreement vs teacher
    def agree(rows, name):
        n = len(rows)
        return sum(1 for r in rows if r["picks"][name] == labels[r["position_id"]]["heur3200_choice"]) / n if n else float("nan")

    # subsets
    v27miss = [r for r in mid if labels[r["position_id"]]["v27_static_choice"] != labels[r["position_id"]]["heur3200_choice"]]
    v27ok = [r for r in mid if labels[r["position_id"]]["v27_static_choice"] == labels[r["position_id"]]["heur3200_choice"]]
    iter8finds_v27miss = [r for r in mid
                          if labels[r["position_id"]]["iter8_choice"] == labels[r["position_id"]]["heur3200_choice"]
                          and labels[r["position_id"]]["v27_static_choice"] != labels[r["position_id"]]["heur3200_choice"]]

    subsets = {
        "ALL": mid,
        "v27_miss": v27miss,
        "v27_correct": v27ok,
        "iter8finds_v27miss": iter8finds_v27miss,
    }
    for band in ("opening", "early_mid", "mid", "late_mid", "pre_endgame"):
        subsets[f"band:{band}"] = [r for r in mid if r["band"] == band]
    for src in ("greedy", "heur@3200", "hybrid:8:3200", "iter8"):
        subsets[f"src:{src}"] = [r for r in mid if r["source_bucket"] == src]
    # per-patch target subsets
    for patchkey in ("farm_final_value_v1", "meeple_economy_v1", "completion_timing_v1"):
        subsets[f"target:{patchkey}"] = [r for r in mid if patchkey in _PATCH_OF.get(r["position_id"], "")]

    # ---- ENDGAME K=2 ----
    end_rows = [json.loads(l) for l in open(END_DS)]
    end_k2 = [r for r in end_rows if r["k_remaining"] == 2 and r["recon_ok"]]
    print(f"[v28-root] endgame K=2: {len(end_k2)} positions", flush=True)
    t1 = time.perf_counter()
    with ctx.Pool(workers) as pool:
        endres = [r for r in pool.imap_unordered(_end_worker, end_k2, chunksize=4)]
    eerrs = [r for r in endres if "_error" in r]
    endres = [r for r in endres if "_error" not in r]
    print(f"[v28-root] endgame done {len(endres)} rows, {len(eerrs)} errors, {(time.perf_counter()-t1)/60:.1f} min", flush=True)
    if eerrs:
        print("  sample errors:", [e["_error"] for e in eerrs[:3]], flush=True)

    def end_top1(name):
        regs = [r["regret"][name] for r in endres if r["regret"][name] is not None]
        return (sum(1 for x in regs if x == 0.0) / len(regs)) if regs else float("nan")

    def end_regret(name):
        regs = [r["regret"][name] for r in endres if r["regret"][name] is not None]
        return (sum(regs) / len(regs)) if regs else float("nan")

    # ---- write RESULTS.csv (overall) ----
    with open(OUT_RESULTS, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "mid_top1_vs_teacher", "mid_n",
                    "end_k2_top1_exact", "end_k2_mean_regret", "end_k2_n",
                    "patch"])
        spec = v28_configs.load_spec()["variants"]
        for name in VNAMES:
            w.writerow([name, round(agree(mid, name), 4), len(mid),
                        round(end_top1(name), 4), round(end_regret(name), 4), len(endres),
                        spec[name]["patch"]])

    # ---- write BY_SUBSET.csv ----
    with open(OUT_SUBSET, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["subset", "n"] + VNAMES)
        for sname, rows in subsets.items():
            w.writerow([sname, len(rows)] + [round(agree(rows, n), 4) for n in VNAMES])

    print("\n=== MIDGAME top-1 vs heur@3200 teacher (ALL) ===")
    for name in VNAMES:
        print(f"  {name:16} {agree(mid, name):.4f}")
    print("=== ENDGAME K=2 top-1 (exact) / mean regret ===")
    for name in VNAMES:
        print(f"  {name:16} top1={end_top1(name):.4f}  regret={end_regret(name):.4f}")
    print(f"\nwrote -> {OUT_RESULTS}\n        {OUT_SUBSET}\n        {OUT_JSONL}")


if __name__ == "__main__":
    main()
