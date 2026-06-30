#!/usr/bin/env python3
"""Step-2 PeNS CORRECTNESS FIREWALL (MEASUREMENT ONLY).

The hard gate for Path A. Proves the LIVE parent-threaded feature extraction at
an MCTS leaf reproduces the DATASET's stored `child_scalars` row for the same
(seed, ply, child action) — column-for-column, ESPECIALLY the 16 parent->child
DELTA / move-semantics columns that collapse to 0 without a threaded parent.

For each sampled dataset group it:
  1. replay_to(seed, ply)            -> the PARENT (decision) board
  2. for each stored child action a  -> child_board = game.get_next_state(parent, a)
  3. live  = step2_leaf.extract_step2_features(game, child_board, cfg, parent_board)
  4. stored = aux_step2.npz['child_scalars'][row]   (the build_dataset row)
  5. compare live vs stored per column (f16 tolerance), grouped.

PASS criterion: the 16 delta cols match the dataset within f16 tolerance for ~all
sampled children (proves the threading is correct and the +43% is now served).

  python -u scripts/step2_pens/verify_live_features.py --n-groups 200
"""
from __future__ import annotations

# Import step2_leaf FIRST so its build_dataset import sets the v2.9 GUARD env
# (CARCASSONNE_V25_* / V29_MEEPLE_CURVE / USE_FLAT_LEAF=1 / USE_CY_REPR=1 /
# VALUE_BLEND=0) BEFORE virtual_score_v2.DEFAULT_CONFIG is frozen.
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import carcassonne_ai.step2_leaf as step2_leaf  # noqa: E402 (sets guard env)

import argparse  # noqa: E402
import json  # noqa: E402

import numpy as np  # noqa: E402

import eval_hybrid_handoff as EH  # noqa: E402
from gen_endgame_positions import replay_to  # noqa: E402

FEAT_NAMES = step2_leaf.FEAT_NAMES

# The 16 parent->child DELTA / move-semantics columns (the Path-A target).
DELTA_COLS = [
    "T1_d_base", "T1_d_closure_self", "T1_d_closure_opp", "T1_d_meeple",
    "T1_d_pretransform",
    "T2_net_meeple_delta_self", "T2_imm_score_delta_self", "T2_imm_score_delta_opp",
    "T2_d_total_city_open_edges", "T2_d_n_open_cities", "T2_d_meeples_locked_self",
    "T2_d_n_contested", "T2_opp_feature_touched", "T2_feature_completed_by_move",
    "T2_completed_value_self_div8", "T2_completed_value_opp_div8",
]
# Move-semantics one-hots that are ALSO parent-dependent (a move was/wasn't made).
MOVESEM_COLS = [
    "T2_meeple_placed", "T2_mtype_city", "T2_mtype_road", "T2_mtype_farm",
    "T2_mtype_monastery",
]
# The placed-tile deck-odds col is parent-dependent too.
PLACEDTILE_COLS = ["DO_placed_tile_remaining_count_log1p"]

GROUPS = {
    "Fctx(9)": [n for n in FEAT_NAMES if n.startswith("F_")],
    "T1_static(8)": ["T1_leaf_total_div15", "T1_leaf_q_tanh", "T1_base_div15",
                     "T1_closure_self_div8", "T1_closure_opp_div8",
                     "T1_meeple_contribution", "T1_pretransform_div15",
                     "T1_terminal_flag"],
    "T2_child_struct(12)": ["T2_n_open_cities", "T2_n_open_roads", "T2_n_open_farms",
                            "T2_total_city_open_edges", "T2_n_cities_self",
                            "T2_n_cities_opp", "T2_n_cities_contested",
                            "T2_n_meeples_locked_self", "T2_n_meeples_locked_opp",
                            "T2_max_open_city_value_self_div8", "T2_n_farms_self",
                            "T2_n_farms_contested"],
    "BAG(32)": [n for n in FEAT_NAMES if n.startswith("BAG_")],
    "DECKODDS_static(6)": [n for n in FEAT_NAMES if n.startswith("DO_")
                           and n not in PLACEDTILE_COLS],
    "*** DELTA_16 ***": DELTA_COLS,
    "MOVESEM(5)": MOVESEM_COLS,
    "DO_placed_tile(1)": PLACEDTILE_COLS,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/home/doctor/carc_step2_pens/dataset")
    ap.add_argument("--n-groups", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    # f16 round-trip tolerance: child_scalars are stored as f16, so values up to
    # ~|x|*2^-10 of relative error are pure storage quantization, not a bug.
    ap.add_argument("--atol", type=float, default=2e-2)
    ap.add_argument("--rtol", type=float, default=5e-3)
    args = ap.parse_args()

    cfg = EH._heur_leaf_cfg(2.0)
    h = step2_leaf._bd._cfg_hash(cfg)
    assert h == step2_leaf._bd.FROZEN_V29_HASH, f"leaf cfg {h} != frozen"
    game = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)

    z = np.load(Path(args.dataset) / "aux_step2.npz", allow_pickle=False)
    scal = np.asarray(z["child_scalars"]).astype(np.float32)   # (N,89) (f16-stored)
    gid = z["group_id"]; gs = z["game_seed"]; ply = z["ply"]; aid = z["action_id"]
    ds_feat_names = [str(x) for x in z["feat_names"]]
    assert ds_feat_names == FEAT_NAMES, "feat_names mismatch dataset vs live"

    col_idx = {n: i for i, n in enumerate(FEAT_NAMES)}

    # Pick n_groups distinct groups, deterministically.
    uniq = np.unique(gid)
    rng = np.random.default_rng(args.seed)
    pick = rng.choice(uniq, size=min(args.n_groups, len(uniq)), replace=False)
    pick_set = set(int(g) for g in pick)

    # Build per-group row lists.
    by_group: dict[int, list[int]] = {}
    for i in range(len(gid)):
        g = int(gid[i])
        if g in pick_set:
            by_group.setdefault(g, []).append(i)

    # Per-column accumulators.
    n_cols = len(FEAT_NAMES)
    col_match = np.zeros(n_cols, dtype=np.int64)
    col_total = np.zeros(n_cols, dtype=np.int64)
    col_max_abs_err = np.zeros(n_cols, dtype=np.float64)
    n_children = 0
    n_groups_done = 0
    n_replay_err = 0
    n_action_miss = 0
    delta_nonzero_children = 0  # children where at least one delta col is nonzero in the dataset
    mismatch_samples: list[str] = []

    for g, rows in sorted(by_group.items()):
        seed = int(gs[rows[0]]); pl = int(ply[rows[0]])
        try:
            pgame, pboard = replay_to(seed, pl)
        except Exception as e:  # noqa: BLE001
            n_replay_err += 1
            continue
        # Use the freshly replayed game (matches build_dataset's per-rec replay).
        for r in rows:
            a = int(aid[r])
            mask = pgame.get_valid_moves(pboard)
            if a >= mask.shape[0] or not mask[a]:
                n_action_miss += 1
                continue
            child, _ = pgame.get_next_state(pboard, a)
            live = step2_leaf.extract_step2_features(pgame, child, cfg, pboard)
            stored = scal[r]
            # f16 round-trip the LIVE vec so we compare apples to apples (the
            # dataset is stored f16; quantize the live f32 the same way).
            live_q = live.astype(np.float16).astype(np.float32)
            n_children += 1
            if np.any(np.abs(stored[[col_idx[c] for c in DELTA_COLS]]) > 1e-6):
                delta_nonzero_children += 1
            diff = np.abs(live_q - stored)
            tol = args.atol + args.rtol * np.abs(stored)
            ok = diff <= tol
            col_total += 1
            col_match += ok.astype(np.int64)
            col_max_abs_err = np.maximum(col_max_abs_err, diff.astype(np.float64))
            # Record a few delta-col mismatch samples for diagnosis.
            if len(mismatch_samples) < 12:
                for c in DELTA_COLS + MOVESEM_COLS:
                    ci = col_idx[c]
                    if not ok[ci]:
                        mismatch_samples.append(
                            f"  MISMATCH seed={seed} ply={pl} a={a} col={c}: "
                            f"live={live_q[ci]:.5f} stored={stored[ci]:.5f}"
                        )
                        break
        n_groups_done += 1

    print(f"[firewall] groups sampled={n_groups_done} children compared={n_children} "
          f"replay_err={n_replay_err} action_miss={n_action_miss}")
    print(f"[firewall] children with >=1 nonzero DELTA col in dataset: "
          f"{delta_nonzero_children}/{n_children} "
          f"({100*delta_nonzero_children/max(1,n_children):.1f}%) "
          f"(confirms the deltas are genuinely active, not trivially 0)")
    print(f"[tol] atol={args.atol} rtol={args.rtol} (f16-quantized live vs f16-stored)\n")

    # Per-GROUP match rates.
    print(f"{'group':<24} {'cols':>5} {'match%':>8} {'min_col%':>9} {'max|err|':>10}")
    overall_match = 0; overall_total = 0
    for gname, cols in GROUPS.items():
        cis = [col_idx[c] for c in cols]
        m = int(col_match[cis].sum()); t = int(col_total[cis].sum())
        per_col = [col_match[ci] / max(1, col_total[ci]) for ci in cis]
        min_col = min(per_col) if per_col else 1.0
        mx = float(col_max_abs_err[cis].max()) if cis else 0.0
        overall_match += m; overall_total += t
        flag = "" if (m == t) else "  <-- CHECK"
        print(f"{gname:<24} {len(cols):>5} {100*m/max(1,t):>7.2f}% "
              f"{100*min_col:>8.2f}% {mx:>10.5f}{flag}")
    print(f"\n[OVERALL] {overall_match}/{overall_total} "
          f"({100*overall_match/max(1,overall_total):.3f}%) column-comparisons match")

    # The decisive gate: the 16 delta cols.
    delta_cis = [col_idx[c] for c in DELTA_COLS]
    dm = int(col_match[delta_cis].sum()); dt = int(col_total[delta_cis].sum())
    delta_rate = dm / max(1, dt)
    print("\n=== DELTA-16 PER-COLUMN ===")
    for c in DELTA_COLS:
        ci = col_idx[c]
        print(f"  {c:<32} {100*col_match[ci]/max(1,col_total[ci]):>7.2f}%  "
              f"max|err|={col_max_abs_err[ci]:.5f}")
    if mismatch_samples:
        print("\n[mismatch samples]")
        print("\n".join(mismatch_samples))

    GATE = delta_rate >= 0.999 and (overall_match / max(1, overall_total)) >= 0.999
    print(f"\n{'='*60}")
    print(f"FIREWALL {'PASS' if GATE else 'FAIL'}: "
          f"delta-16 match={100*delta_rate:.3f}%  "
          f"overall match={100*overall_match/max(1,overall_total):.3f}%")
    print(f"{'='*60}")
    print(json.dumps({
        "n_groups": n_groups_done, "n_children": n_children,
        "delta16_match_rate": round(delta_rate, 6),
        "overall_match_rate": round(overall_match / max(1, overall_total), 6),
        "delta_nonzero_children_frac": round(delta_nonzero_children / max(1, n_children), 4),
        "gate": "PASS" if GATE else "FAIL",
    }))
    return 0 if GATE else 1


if __name__ == "__main__":
    sys.exit(main())
