#!/usr/bin/env python3
"""F6 (strategy-scan) win-prob pre-gate — 0-game instrument.

Measures whether the margin-vs-win-probability distinction ever BINDS at real
champion decision points, using only banked corpora (no games played):

  Stage 1  calibration scan over measurement/champ_action_logs/champ_games.jsonl
           (449 champion self-play games, `walled`): per TILES ply and POV,
           (k_left, banked, leaf, prospective, realized outcome).
  Stage 2  outcome models per pre-registered phase bucket:
             M1: logit P(win) = a + b*leaf
             M2: logit P(win) = a + b1*banked + b2*prospective
           mechanism statistic = b2/b1 (win-conversion of a prospective point
           relative to a banked point), game-clustered bootstrap CI.
  Stage 3  binding census over the tile-tie bank's selfplay/walled positions
           (measurement/tiletie_pricing_20260812): per position, chained arm
           values (tile + best meeple by leaf), near-tie pairs by margin,
           max pairwise |dP(win)| under M2 (and under M1 as the honesty row).
  Stage 4  champion posture: among binding positions where the mover trails and
           the full-champion pick is recorded + margin-near-tied, the rate at
           which the champion's arm sacrifices >= DP_BAR of P(win).

Read-rule, bars and branches are PRE-REGISTERED in
measurement/f6_winprob_20260814/DESIGN.md (committed before any number was
read). This script only computes them.

Usage:
  f6_winprob_pregate.py [--out-dir DIR] [--workers 8] [--limit-games N]
                        [--limit-positions N] [--bootstrap 500]
                        [--integrity-only]

`--integrity-only` runs both scans but prints ONLY integrity fields (replay /
checksum / hash counts) — the smoke mode used before the adjudicating run, so
no statistic is read ahead of the committed read-rule.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _rel in ("scripts/tiletie",):
    _p = str(REPO / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

CHAMPGAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
TT_DIR = REPO / "measurement" / "tiletie_pricing_20260812"
OUT_DIR_DEFAULT = REPO / "measurement" / "f6_winprob_20260814"

SCHEMA = "carcassonne-f6-winprob-pregate/v1"

# ---- pre-registered constants (DESIGN.md; do not tune after the fact) ------ #
EPS_MARGIN_PRIMARY = 0.25     # near-tie pair: |leaf_i - leaf_j| <= eps (pts)
EPS_MARGIN_SENS = 1.0
DP_BAR_PRIMARY = 0.02         # binding: max pairwise |dP| >= bar
DP_BAR_SENS = 0.05
BINDING_RATE_KILL = 0.05      # branch K bar
CHAMP_N_MIN = 20              # branch F: minimum Stage-4 n
#: pre-registered buckets on k_left (DESIGN.md §2): late <=12, mid 13-36, early >=37
def bucket_of(k_left: int) -> str:
    k = int(k_left)
    if k <= 12:
        return "late"
    if k <= 36:
        return "mid"
    return "early"

BUCKETS = ("late", "mid", "early")

_LEAF = None                  # set in the leg process before the Pool forks


# --------------------------------------------------------------------------- #
# logistic (IRLS with fractional targets + tiny ridge)                          #
# --------------------------------------------------------------------------- #
def fit_logistic(X, y, ridge=1e-6, iters=60, tol=1e-10):
    """MLE logistic via Newton/IRLS. `X` (n,k) incl. intercept col, `y` in
    [0,1] (0.5 = draw). Returns coefficient vector (k,). Ridge keeps the
    Hessian invertible under separation."""
    import numpy as np

    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(eta, -35, 35)))
        w = np.maximum(p * (1.0 - p), 1e-9)
        g = X.T @ (y - p) - ridge * beta
        H = (X * w[:, None]).T @ X + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            break
    return beta


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, z))))


def fit_bucket_models(rows):
    """rows: list of dicts with k_left, banked, prosp, leaf, y. Returns
    {bucket: {"m1": (a,b), "m2": (a,b1,b2), "n": n}} (buckets with <50 rows are
    refused — a fit on less is noise)."""
    import numpy as np

    by_b = defaultdict(list)
    for r in rows:
        by_b[bucket_of(r["k_left"])].append(r)
    out = {}
    for b, rs in by_b.items():
        if len(rs) < 50:
            continue
        y = np.array([r["y"] for r in rs])
        leaf = np.array([r["leaf"] for r in rs])
        banked = np.array([r["banked"] for r in rs])
        prosp = np.array([r["prosp"] for r in rs])
        one = np.ones(len(rs))
        m1 = fit_logistic(np.column_stack([one, leaf]), y)
        m2 = fit_logistic(np.column_stack([one, banked, prosp]), y)
        out[b] = {"m1": [float(v) for v in m1], "m2": [float(v) for v in m2],
                  "n": len(rs)}
    return out


def p_win_m2(models, bucket, banked, prosp):
    a, b1, b2 = models[bucket]["m2"]
    return sigmoid(a + b1 * banked + b2 * prosp)


def p_win_m1(models, bucket, leaf):
    a, b = models[bucket]["m1"]
    return sigmoid(a + b * leaf)


# --------------------------------------------------------------------------- #
# binding statistics (pure functions — unit-tested)                             #
# --------------------------------------------------------------------------- #
def near_tie_pairs(arms, eps):
    """[(i,j)] over arm indices with |leaf_i - leaf_j| <= eps, i<j."""
    out = []
    for i in range(len(arms)):
        for j in range(i + 1, len(arms)):
            if abs(arms[i]["leaf"] - arms[j]["leaf"]) <= eps:
                out.append((i, j))
    return out


def position_dp(pos, models, eps, which="m2"):
    """(dp_max, n_pairs) for one Stage-3 position record under M1 or M2.
    dp_max is None when the position has no near-tie pair or its bucket has no
    fitted model."""
    b = bucket_of(pos["k_left"])
    if b not in models:
        return None, 0
    arms = pos["arms"]
    pairs = near_tie_pairs(arms, eps)
    if not pairs:
        return None, 0
    if which == "m2":
        ps = [p_win_m2(models, b, a["banked"], a["prosp"]) for a in arms]
    else:
        ps = [p_win_m1(models, b, a["leaf"]) for a in arms]
    dp = max(abs(ps[i] - ps[j]) for i, j in pairs)
    return dp, len(pairs)


def champ_posture(pos, models, eps, dp_bar):
    """Stage-4 record for one position, or None when it does not qualify
    (not trailing / champ pick absent / champ arm not in arms / champ arm not
    margin-near-tied with any other arm / bucket unfitted)."""
    b = bucket_of(pos["k_left"])
    if b not in models:
        return None
    if pos["root_leaf_mover"] >= 0:            # trailing only
        return None
    ca = pos.get("champ_action")
    if ca is None:
        return None
    idx = next((i for i, a in enumerate(pos["arms"]) if a["action"] == ca), None)
    if idx is None:
        return None
    arms = pos["arms"]
    peers = [i for i in range(len(arms))
             if i != idx and abs(arms[i]["leaf"] - arms[idx]["leaf"]) <= eps]
    if not peers:
        return None
    ps = [p_win_m2(models, b, a["banked"], a["prosp"]) for a in arms]
    p_max = max(ps[i] for i in peers + [idx])
    sacrifice = p_max - ps[idx]
    return {"rid": pos["rid"], "sacrifice": sacrifice,
            "champ_lower": sacrifice >= dp_bar}


def adjudicate(binding_rate, beta_ratio_ci, champ_n, champ_lower_rate):
    """The pre-registered branch (DESIGN.md read-rule), first-match-wins."""
    if binding_rate < BINDING_RATE_KILL:
        return "K"
    lo, hi = beta_ratio_ci
    if (hi < 1.0 or lo > 1.0) and champ_n >= CHAMP_N_MIN and \
            champ_lower_rate is not None and champ_lower_rate >= 0.5:
        # CI excludes 1 in either direction = the conversion channel is real
        return "F"
    return "T"


# --------------------------------------------------------------------------- #
# Stage 1 worker — one champ_games record -> calibration rows                   #
# --------------------------------------------------------------------------- #
def _stage1_game(rec):
    import random

    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    from carcassonne_ai import fair_agent
    from carcassonne_ai.game_wrapper import Game

    deck_seed = int(rec["deck_seed"])
    actions = [int(a) for a in rec["actions"]]
    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    rows = []
    for ply, a in enumerate(actions):
        st = board.state
        if st.phase == GamePhase.TILES:
            k_left = int(fair_agent.k_remaining(st))
            leafs = (_LEAF(st, 0), _LEAF(st, 1))
            b0 = int(st.scores[0]) - int(st.scores[1])
            for p in (0, 1):
                banked = b0 if p == 0 else -b0
                rows.append({"deck_seed": deck_seed, "ply": ply, "pov": p,
                             "k_left": k_left, "banked": float(banked),
                             "leaf": float(leafs[p]),
                             "prosp": float(leafs[p]) - float(banked)})
        board, _ = game.get_next_state(board, int(a))
    final = [int(x) for x in board.state.scores]
    rec_final = [int(rec["score_p0"]), int(rec["score_p1"])]
    if final != rec_final:
        raise AssertionError(
            f"replay final scores {final} != recorded {rec_final} for "
            f"deck_seed={deck_seed} — lossless-replay contract broken, STOP")
    for r in rows:
        w = final[r["pov"]] - final[1 - r["pov"]]
        r["y"] = 1.0 if w > 0 else (0.5 if w == 0 else 0.0)
    return {"deck_seed": deck_seed, "rows": rows, "replay_scores_match": True}


# --------------------------------------------------------------------------- #
# Stage 3 worker — one bank position -> chained arm records                     #
# --------------------------------------------------------------------------- #
def _stage3_position(task):
    import random

    import numpy as np

    from carcassonne_ai import fair_agent
    from carcassonne_ai.game_wrapper import Game

    pos, arm_actions, champ_action = task
    deck_seed = int(pos["deck_seed"])
    ply = int(pos["ply"])
    actions = [int(a) for a in pos["actions"]]
    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    for a in actions[:ply]:
        board, _ = game.get_next_state(board, int(a))
    checksum = game.string_representation(board)
    if pos.get("checksum") is not None and checksum != pos["checksum"]:
        raise AssertionError(
            f"bank checksum mismatch at deck_seed={deck_seed} ply={ply} — the "
            "positions bank does not reconstruct against this src tree, STOP")
    seat = int(board.state.current_player)
    if seat != int(pos["root_player"]):
        raise AssertionError(
            f"root_player mismatch at {pos['rid']}: replay says {seat}")
    opp = 1 - seat
    k_left = int(fair_agent.k_remaining(board.state))
    root_leaf = float(_LEAF(board.state, seat))
    valid = set(int(x) for x in np.flatnonzero(game.get_valid_moves(board)))
    arms_out = []
    for a in arm_actions:
        if int(a) not in valid:
            raise AssertionError(f"arm {a} not legal at {pos['rid']} on replay")
        s1, _ = game.get_next_state(board, int(a))
        chained = s1
        if int(s1.state.current_player) == seat:
            legal2 = [int(x) for x in np.flatnonzero(game.get_valid_moves(s1))]
            best_v = None
            for m in legal2:                 # ascending -> lowest index wins ties
                s2, _ = game.get_next_state(s1, m)
                v = float(_LEAF(s2.state, seat))
                if best_v is None or v > best_v:
                    best_v, chained = v, s2
        st = chained.state
        banked = float(int(st.scores[seat]) - int(st.scores[opp]))
        leaf = float(_LEAF(st, seat))
        arms_out.append({"action": int(a), "leaf": leaf, "banked": banked,
                         "prosp": leaf - banked})
    return {"rid": pos["rid"], "deck_seed": deck_seed, "ply": ply, "seat": seat,
            "k_left": k_left, "root_leaf_mover": root_leaf,
            "champ_action": champ_action, "arms": arms_out,
            "checksum_ok": True}


# --------------------------------------------------------------------------- #
# corpus loading                                                                #
# --------------------------------------------------------------------------- #
def load_champgames(limit=None):
    out = []
    with open(CHAMPGAMES) as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    out.sort(key=lambda r: int(r["deck_seed"]))
    return out[:limit] if limit else out


def load_positions(limit=None):
    """Selfplay/walled bank positions joined with ARMS.json + champ_picks."""
    arms = json.load(open(TT_DIR / "positions" / "ARMS.json"))
    champ = {}
    cp = TT_DIR / "champ_picks" / "champ_picks.jsonl"
    if cp.exists():
        with open(cp) as fh:
            for line in fh:
                if not line.strip():
                    continue
                d = json.loads(line)
                if d.get("champ_action") is not None and d.get("error") is None:
                    champ[d["rid"]] = int(d["champ_action"])
    tasks, seen = [], set()
    for leg in sorted((TT_DIR / "positions").glob("positions_walled_leg*.jsonl")):
        with open(leg) as fh:
            for line in fh:
                if not line.strip():
                    continue
                pos = json.loads(line)
                rid = pos["rid"]
                if pos.get("stratum") != "selfplay" or rid in seen:
                    continue
                seen.add(rid)
                ent = arms.get(rid)
                if ent is None:
                    continue
                arm_actions = [int(a) for a in ent["arms"]]
                tasks.append((pos, arm_actions, champ.get(rid)))
    tasks.sort(key=lambda t: t[0]["rid"])
    return tasks[:limit] if limit else tasks


# --------------------------------------------------------------------------- #
# bootstrap                                                                     #
# --------------------------------------------------------------------------- #
def bootstrap_stats(cal_rows, positions, B, seed=20260814):
    """Game-clustered bootstrap: resample calibration games AND position
    deck-seed clusters; per replicate refit M2 and recompute (beta ratios per
    bucket, pooled mid+late ratio, primary binding rate). Returns the replicate
    arrays."""
    import numpy as np

    rng = np.random.default_rng(seed)
    by_game = defaultdict(list)
    for r in cal_rows:
        by_game[r["deck_seed"]].append(r)
    game_ids = sorted(by_game)
    pos_by_cluster = defaultdict(list)
    for p in positions:
        pos_by_cluster[p["deck_seed"]].append(p)
    cluster_ids = sorted(pos_by_cluster)

    ratios = {b: [] for b in BUCKETS}
    pooled, brates = [], []
    for _ in range(B):
        gsel = rng.choice(len(game_ids), size=len(game_ids), replace=True)
        rows = [r for gi in gsel for r in by_game[game_ids[gi]]]
        models = fit_bucket_models(rows)
        rep_r = {}
        for b in BUCKETS:
            if b in models:
                _, b1, b2 = models[b]["m2"]
                if abs(b1) > 1e-12:
                    rep_r[b] = b2 / b1
                    ratios[b].append(b2 / b1)
        ml = [rep_r[b] for b in ("mid", "late") if b in rep_r]
        if ml:
            pooled.append(float(np.mean(ml)))
        csel = rng.choice(len(cluster_ids), size=len(cluster_ids), replace=True)
        pos_rep = [p for ci in csel for p in pos_by_cluster[cluster_ids[ci]]]
        n_scoreable = n_binding = 0
        for p in pos_rep:
            dp, _ = position_dp(p, models, EPS_MARGIN_PRIMARY, "m2")
            if dp is None:
                continue
            n_scoreable += 1
            if dp >= DP_BAR_PRIMARY:
                n_binding += 1
        if n_scoreable:
            brates.append(n_binding / n_scoreable)
    return ratios, pooled, brates


def pct_ci(xs, lo=2.5, hi=97.5):
    import numpy as np
    if not xs:
        return [None, None]
    return [float(np.percentile(xs, lo)), float(np.percentile(xs, hi))]


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-games", type=int, default=None)
    ap.add_argument("--limit-positions", type=int, default=None)
    ap.add_argument("--bootstrap", type=int, default=500)
    ap.add_argument("--integrity-only", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    import chain_census as CC
    env = CC.prepare_env("walled")
    global _LEAF
    leaf, cfg, leaf_hashes, bag_close = CC.build_leaf()
    _LEAF = leaf

    games = load_champgames(args.limit_games)
    tasks = load_positions(args.limit_positions)
    print(f"[f6] corpora: {len(games)} champ games, {len(tasks)} bank positions",
          file=sys.stderr)

    ctx = mp.get_context("fork")
    with ctx.Pool(args.workers) as pool:
        g_results = pool.map(_stage1_game, games, chunksize=4)
        p_results = pool.map(_stage3_position, tasks, chunksize=8)

    cal_rows = [r for g in g_results for r in g["rows"]]
    integrity = {
        "n_games": len(g_results),
        "replay_scores_match": sum(1 for g in g_results if g["replay_scores_match"]),
        "n_positions": len(p_results),
        "checksum_ok": sum(1 for p in p_results if p["checksum_ok"]),
        "n_cal_rows": len(cal_rows),
        "leaf_hash": leaf_hashes.get("harness_leaf_hash"),
        "rules_profile": "walled",
        "champ_picks_joined": sum(1 for p in p_results if p["champ_action"] is not None),
    }
    if args.integrity_only:
        print(json.dumps({"integrity": integrity,
                          "wall_secs": round(time.time() - t0, 1)}, indent=1))
        return 0

    # ---- Stage 2: models on the full corpus -------------------------------- #
    models = fit_bucket_models(cal_rows)

    # ---- Stage 3: binding census ------------------------------------------- #
    cells = {}
    for eps, dp_bar, name in ((EPS_MARGIN_PRIMARY, DP_BAR_PRIMARY, "primary"),
                              (EPS_MARGIN_PRIMARY, DP_BAR_SENS, "dp_sens"),
                              (EPS_MARGIN_SENS, DP_BAR_PRIMARY, "eps_sens"),
                              (EPS_MARGIN_SENS, DP_BAR_SENS, "both_sens")):
        n_sc = n_b = 0
        dps = []
        for p in p_results:
            dp, _ = position_dp(p, models, eps, "m2")
            if dp is None:
                continue
            n_sc += 1
            dps.append(dp)
            if dp >= dp_bar:
                n_b += 1
        cells[name] = {"eps_margin": eps, "dp_bar": dp_bar,
                       "n_scoreable": n_sc, "n_binding": n_b,
                       "binding_rate": (n_b / n_sc) if n_sc else None,
                       "dp_mean": (sum(dps) / len(dps)) if dps else None,
                       "dp_max": max(dps) if dps else None}
    # honesty row: same primary cell under M1
    n_sc = n_b = 0
    dps1 = []
    for p in p_results:
        dp, _ = position_dp(p, models, EPS_MARGIN_PRIMARY, "m1")
        if dp is None:
            continue
        n_sc += 1
        dps1.append(dp)
        if dp >= DP_BAR_PRIMARY:
            n_b += 1
    m1_row = {"n_scoreable": n_sc, "n_binding": n_b,
              "binding_rate": (n_b / n_sc) if n_sc else None,
              "dp_mean": (sum(dps1) / len(dps1)) if dps1 else None,
              "dp_max": max(dps1) if dps1 else None}

    # ---- Stage 4: champion posture ----------------------------------------- #
    posture = []
    for p in p_results:
        dp, _ = position_dp(p, models, EPS_MARGIN_PRIMARY, "m2")
        if dp is None or dp < DP_BAR_PRIMARY:
            continue
        rec = champ_posture(p, models, EPS_MARGIN_PRIMARY, DP_BAR_PRIMARY)
        if rec is not None:
            posture.append(rec)
    champ_n = len(posture)
    champ_lower = sum(1 for r in posture if r["champ_lower"])
    champ_lower_rate = (champ_lower / champ_n) if champ_n else None
    mean_sac = (sum(r["sacrifice"] for r in posture) / champ_n) if champ_n else None

    # ---- bootstrap ---------------------------------------------------------- #
    ratios, pooled, brates = bootstrap_stats(cal_rows, p_results, args.bootstrap)
    beta_point = {}
    for b in BUCKETS:
        if b in models:
            _, b1, b2 = models[b]["m2"]
            beta_point[b] = {"beta_banked": b1, "beta_prosp": b2,
                             "ratio": (b2 / b1) if abs(b1) > 1e-12 else None,
                             "ratio_ci95": pct_ci(ratios[b]), "n": models[b]["n"]}
    ml = [beta_point[b]["ratio"] for b in ("mid", "late")
          if b in beta_point and beta_point[b]["ratio"] is not None]
    pooled_point = (sum(ml) / len(ml)) if ml else None
    pooled_ci = pct_ci(pooled)

    binding_rate = cells["primary"]["binding_rate"]
    branch = adjudicate(binding_rate, tuple(pooled_ci) if None not in pooled_ci
                        else (0.0, 2.0),  # unfittable CI can never satisfy F
                        champ_n, champ_lower_rate)

    git_rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
    verdict = {
        "schema": SCHEMA,
        "design": "measurement/f6_winprob_20260814/DESIGN.md",
        "git_rev": git_rev,
        "wall_secs": round(time.time() - t0, 1),
        "integrity": integrity,
        "models": {b: models[b] for b in models},
        "beta_ratio": {"per_bucket": beta_point, "pooled_mid_late": pooled_point,
                       "pooled_ci95": pooled_ci},
        "binding": {"m2": cells, "m1_honesty_primary": m1_row,
                    "binding_rate_ci95": pct_ci(brates)},
        "champion_posture": {"n": champ_n, "champ_lower": champ_lower,
                             "champ_lower_rate": champ_lower_rate,
                             "mean_sacrifice": mean_sac},
        "read_rule": {"binding_rate_kill": BINDING_RATE_KILL,
                      "dp_bar": DP_BAR_PRIMARY, "eps_margin": EPS_MARGIN_PRIMARY,
                      "champ_n_min": CHAMP_N_MIN},
        "branch": branch,
    }
    out_dir = args.out_dir
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    with open(out_dir / "raw" / "calibration_rows.jsonl", "w") as fh:
        for r in cal_rows:
            fh.write(json.dumps(r) + "\n")
    with open(out_dir / "raw" / "positions_scored.jsonl", "w") as fh:
        for p in p_results:
            fh.write(json.dumps(p) + "\n")
    with open(out_dir / "raw" / "posture.jsonl", "w") as fh:
        for r in posture:
            fh.write(json.dumps(r) + "\n")
    with open(out_dir / "VERDICT.json", "w") as fh:
        json.dump(verdict, fh, indent=1)
    print(json.dumps(verdict, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
