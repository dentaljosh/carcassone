#!/usr/bin/env python3
"""PROBE A — MILESTONE 2 per-component training-set builder (structure-first).

For each canonical teacher-Q'd child board of each h6400_v2.9 sibling-set root
(the SAME enumeration as scripts/step2_pens/build_dataset.py — bit-identical env,
cfg 7fc930b82801cb43, replay_to(seed,ply,checksum), root-POV), we emit:

  * the FROZEN 24-dim per-component feature matrix (component_features.py, the
    Python reference == the Cython emit — bit-exact-gated by
    tests/test_probe_a_feature_emit.py). One (n_comp, 24) block per board.

  * per-component NATURAL heuristic targets (self-minus-opp, root-POV), where
    cleanly attributable:
        y_base[i]     : component i's own end-of-game base contribution to
                        (score[self]-score[opp])  (city/road/farm; econ=0).
        y_closure[i]  : component i's own UNCAPPED closure-anticipation
                        contribution to (closure_self - closure_opp)
                        (self meeples add, opp meeples subtract; farm-growth
                        on the farm row; econ=0).
        y_econ (scalar, carried on the econ row's y_comp):
                        meeple_contribution = meeple_flat + meeple_curve_delta
                        (the board-level free-meeple economy / curve).
    y_comp[i] = y_base[i] + y_closure[i] (+ y_econ on the econ row) is the
    per-component target; sum_i y_comp[i] == the UNCAPPED pretransform
    (base + closure_self_uncapped - closure_opp_uncapped + meeple_contribution).

  * the board-level aggregate targets from leaf_v29.decompose_v29():
        pretransform_total  (== virtual_score_v2 pre-tanh, the CAPPED heuristic;
                             the g_theta aggregate must reproduce THIS).
        base, closure_self, closure_opp (capped), meeple_contribution.
    The CAP residual = pretransform_total - sum_i y_comp[i] is the amount the
    board-level closure caps (bonus_cap=8) subtract from the uncapped per-
    component sum. The CLOISTER residual is folded in too (cloisters are not
    enumerated as components -> their base+closure slice is missing from
    sum_i y_comp[i]); we report both residuals' size separately (see
    --report at end).

  * oracle_q (h6400 root/search Q for the child action) + group_id (sibling set)
    + game_seed (for the frozen bucket() TEST split) for stage (ii) fine-tune.

Ragged packing: all component rows are concatenated into ONE (N, 24) matrix;
`board_offsets` (n_boards+1) delimits each board's block. Per-board scalars
(pretransform_total, oracle_q, group_id, game_seed, phase, cap_residual,
cloister_residual, n_comp) are length n_boards. Per-component targets
(y_base, y_closure, y_comp) are length N.

NET-FREE, CPU-parallel.  Writes <out>/component_ds.npz + <out>/meta.json.

  nice -n 19 .venv/bin/python -u scripts/probe_a/build_component_dataset.py \
      --out /home/doctor/carc_probe_a/component_ds --workers 30
  # smoke:
  nice -n 19 .venv/bin/python -u scripts/probe_a/build_component_dataset.py \
      --out /home/doctor/carc_probe_a/component_ds_smoke --limit 200 --workers 12
"""
from __future__ import annotations
import os
# --- GUARD env — VERBATIM from build_dataset.py so the leaf is v2.9 7fc930b8 --- #
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, dataclasses as dc, hashlib, json, math, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))
sys.path.insert(0, str(REPO / "scripts" / "probe_a"))

import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.leaf_v29 import decompose_v29
from carcassonne_ai import flat_leaf
from carcassonne_ai.flat_leaf import (
    decompose, _meeple_weight, _winners, _city_points, _road_points,
    _cloister_points, _surrounding_count, _capped,
)
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
import component_features as cf

HG = REPO / "measurement" / "high_gap_distillation"
FROZEN_V29_HASH = "7fc930b82801cb43"
_FARMER_TYPES = (MeepleType.FARMER, MeepleType.BIG_FARMER)
_W: dict = {}
FEAT_DIM = cf.FEAT_DIM


def _cfg_hash(cfg):
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()
         if not (k == "bag_close" and v is False)}  # v2.10 bag_close default-off == frozen v2.9 substrate
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _provenance_guard():
    cfg = EH._heur_leaf_cfg(2.0)
    h = _cfg_hash(cfg)
    print(f"[provenance] v2.9 leaf config_hash = {h}  (frozen v2.9 = {FROZEN_V29_HASH})")
    assert h == FROZEN_V29_HASH, f"LEAF NOT v2.9 bmild_cap8 (got {h})"
    return cfg


def _worker_init():
    _W["cfg"] = EH._heur_leaf_cfg(2.0)
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)


# ============================================================================ #
# Per-component FAITHFUL heuristic-contribution attribution (root-POV, self-opp).
# Mirrors flat_leaf._final_scores (base) + flat_closure_bonus (closure) EXACTLY,
# but keeps each root's contribution separate so it lands on the right feature
# row. The row ORDER matches component_features.component_features EXACTLY:
#   cities (asc root) -> roads (asc root) -> farms (asc root) -> econ row (last).
#
# Contributions that have NO real component row (cloister base + cloister closure,
# and the engine's running-score differential) are collected onto the econ row so
# sum_i y_comp[i] reconciles to the UNCAPPED pretransform exactly (only the
# closure CAP is a board-level residual). This makes sum(y_base) EXACTLY the
# leaf's own base (flat_base_score) and sum(y_closure_signed) EXACTLY the uncapped
# (closure_self - closure_opp).
# ============================================================================ #
def _attribute(state, decomp, root_player, cfg):
    """Return per-component y_base / y_closure arrays (canonical row order) PLUS
    econ-row extras (running-diff base, cloister base+closure) and the board-level
    meeple_contribution scalar.

    Faithful: sum(y_base rows) + econ_base_extra == flat_base_score, and
    sum(y_closure rows) + econ_closure_extra == (closure_self_uncapped -
    closure_opp_uncapped)."""
    opp = 1 - root_player
    board = state.board
    H = len(board); W = len(board[0]) if H else 0
    closure_p = cfg.closure_p

    # ---- BASE: replicate _final_scores, per-root winners/points. -------------- #
    city_counts: dict = {}
    road_counts: dict = {}
    farm_counts: dict = {}
    cloister_base = 0  # awards to self minus opp (no component row -> econ)
    for pl in range(state.players):
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row; c = cws.coordinate.column; side = cws.side
            terr = board[r][c].get_type(side)
            w = _meeple_weight(mp.meeple_type)
            if terr == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    city_counts.setdefault(root, [0] * state.players)[pl] += w
            elif terr == TerrainType.ROAD:
                root = decomp.road_side_root.get((r, c, side))
                if root is not None:
                    road_counts.setdefault(root, [0] * state.players)[pl] += w
            elif terr == TerrainType.CHAPEL or terr == TerrainType.FLOWERS:
                pts = _cloister_points(r, c, board, H, W)
                cloister_base += pts if pl == root_player else -pts
            elif mp.meeple_type in _FARMER_TYPES:
                root = decomp.farm_pos0_root.get((r, c, side))
                if root is not None:
                    farm_counts.setdefault(root, [0] * state.players)[pl] += w

    def _signed(root, counts, pts):
        winners = _winners(counts)
        v = 0.0
        if root_player in winners:
            v += pts
        if opp in winners:
            v -= pts
        return float(v)

    y_base = []
    # cities
    for root in sorted(decomp.city_root_coords.keys()):
        counts = city_counts.get(root)
        if counts is None:
            y_base.append(0.0)
            continue
        pts = _city_points(decomp.city_root_coords[root], decomp.city_root_finished[root], board)
        y_base.append(_signed(root, counts, pts))
    # roads
    for root in sorted(decomp.road_root_coords.keys()):
        counts = road_counts.get(root)
        if counts is None:
            y_base.append(0.0)
            continue
        pts = _road_points(decomp.road_root_coords[root], decomp.road_root_finished[root], board)
        y_base.append(_signed(root, counts, pts))
    # farms
    for root in sorted(decomp.farm_root_keys.keys()):
        counts = farm_counts.get(root)
        if counts is None:
            y_base.append(0.0)
            continue
        pts = 3 * decomp.farm_root_finished_cities[root]
        y_base.append(_signed(root, counts, pts))

    # engine running-score differential (part of flat_base_score) — points ALREADY
    # scored, from CLOSED features no longer on the board. NOT representable from
    # any component's features (the components are gone), so it is NOT a g_theta
    # target: it is an exact additive offset added at leaf-eval time from
    # state.scores. Returned separately. Only the CLOISTER base (features can't
    # carry it either -> the reported cloister residual) lands on the econ row.
    running_diff = float(int(state.scores[root_player]) - int(state.scores[opp]))
    econ_base_extra = float(cloister_base)

    # ---- CLOSURE: replicate flat_closure_bonus per player, attribute per root. -- #
    def _closure_by_root(player):
        """dict city_root->contrib, dict farm_root->contrib, cloister_scalar."""
        knight_roots: set = set()
        farm_roots: set = set()
        cloister_tiles: list = []
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row; c = cws.coordinate.column; side = cws.side
            terr = board[r][c].get_type(side)
            if terr == TerrainType.CITY:
                root = decomp.city_side_root.get((r, c, side))
                if root is not None:
                    knight_roots.add(root)
            elif terr == TerrainType.CHAPEL or terr == TerrainType.FLOWERS:
                cloister_tiles.append((r, c))
            elif mp.meeple_type in _FARMER_TYPES:
                root = decomp.farm_anypos_root.get((r, c, side))
                if root is not None:
                    farm_roots.add(root)
        city_c: dict = {}
        for root in knight_roots:
            if decomp.city_root_finished[root]:
                continue
            open_n = decomp.city_root_open_n[root]
            if open_n <= 0:
                continue
            p = closure_p.get(open_n, 0.0)
            if p > 0:
                city_c[root] = p * decomp.city_root_delta[root]
        cloi = 0.0
        for (r, c) in cloister_tiles:
            n_sur = _surrounding_count(state, r, c, H, W)
            needed = 8 - n_sur
            if needed > 0:
                p = closure_p.get(needed, 0.0)
                if p > 0:
                    cloi += p * needed
        # farm growth: dedup incomplete adj cities across the player's farms,
        # attribute the TOTAL growth of a farm to that farm's row. (Growth cities
        # are deduped GLOBALLY across the player's farms in flat_closure_bonus; we
        # dedup the same way and assign each growth-city's 3*P to the first farm
        # that reaches it, so the per-player sum matches flat_closure_bonus.)
        growth_seen: set = set()
        farm_c: dict = {}
        for froot in sorted(farm_roots):
            g = 0.0
            for croot in decomp.farm_root_adj_city_roots[froot]:
                if croot in growth_seen:
                    continue
                growth_seen.add(croot)
                if decomp.city_root_finished[croot]:
                    continue
                open_n = decomp.city_root_open_n[croot]
                if open_n <= 0:
                    continue
                p = closure_p.get(open_n, 0.0)
                if p > 0:
                    g += p * 3
            if g != 0.0:
                farm_c[froot] = g
        return city_c, farm_c, cloi

    self_city_c, self_farm_c, self_cloi = _closure_by_root(root_player)
    opp_city_c, opp_farm_c, opp_cloi = _closure_by_root(opp)

    y_closure = []
    for root in sorted(decomp.city_root_coords.keys()):
        y_closure.append(float(self_city_c.get(root, 0.0) - opp_city_c.get(root, 0.0)))
    for root in sorted(decomp.road_root_coords.keys()):
        y_closure.append(0.0)
    for root in sorted(decomp.farm_root_keys.keys()):
        y_closure.append(float(self_farm_c.get(root, 0.0) - opp_farm_c.get(root, 0.0)))
    econ_closure_extra = float(self_cloi - opp_cloi)

    # ---- meeple economy (board scalar; curve term). ------------------------- #
    m_self, m_opp = state.meeples[root_player], state.meeples[opp]
    if cfg.v29_meeple_curve is not None:
        from carcassonne_ai.leaf_v29 import _meeple_curve_term
        meeple_contribution = _meeple_curve_term(state, root_player, opp, cfg.v29_meeple_curve)
    else:
        meeple_contribution = cfg.meeple_k * (m_self - m_opp) if cfg.meeple_k > 0.0 else 0.0

    return (y_base, y_closure, econ_base_extra, econ_closure_extra,
            float(meeple_contribution), running_diff)


def _emit_board(state, root_player, cfg):
    """Return (feat (n_comp,24), y_base, y_closure, y_comp, board-scalars dict).

    The g_theta STRUCTURAL target is the leaf value MINUS the running-score
    differential:   y_struct = pretransform - running_diff.
    running_diff (points already scored, from closed features off the board) is an
    exact additive offset the leaf wrapper adds from state.scores; g_theta learns
    only the board-structure-derived part. Per-component targets sum to the
    UNCAPPED y_struct; the two un-closable gaps are reported:
      * cap_residual  = y_struct(capped) - uncapped_sum   (closure cap, board-level)
      * cloister slice (base+closure) is folded into y_struct on the econ row, but
        the econ FEATURES cannot represent it -> reported as cloister_residual.
    """
    decomp = decompose(state)
    feat = cf.component_features(state, decomp, root_player, cfg.closure_p)
    (y_base, y_closure, econ_base_extra, econ_closure_extra,
     meeple_contribution, running_diff) = _attribute(state, decomp, root_player, cfg)
    n_real = len(y_base)  # cities+roads+farms
    assert feat.shape[0] == n_real + 1, (feat.shape[0], n_real)

    # econ row carries: cloister base + cloister closure + meeple economy.
    cloister_slice = econ_base_extra + econ_closure_extra
    y_base.append(econ_base_extra)
    y_closure.append(econ_closure_extra)
    y_comp = [y_base[i] + y_closure[i] for i in range(n_real)]
    y_comp.append(y_base[-1] + y_closure[-1] + meeple_contribution)

    # board-level heuristic decomposition (CAPPED, the real leaf).
    d29 = decompose_v29(state, root_player, cfg)
    pretransform = float(d29["pretransform_total"])
    y_struct = pretransform - running_diff       # the learnable structural target
    uncapped_sum = float(np.sum(y_comp))
    cap_residual = y_struct - uncapped_sum        # closure-cap board nonlinearity
    # fidelity: sum(y_base) must == final_diff (== base - running_diff), exactly.
    base_check = (float(d29["base"]) - running_diff) - float(np.sum(y_base))

    scal = {
        "pretransform": pretransform,
        "running_diff": running_diff,
        "y_struct": y_struct,
        "base": float(d29["base"]),
        "closure_self": float(d29["closure_self"]),
        "closure_opp": float(d29["closure_opp"]),
        "meeple_contribution": float(meeple_contribution),
        "cloister_slice": float(cloister_slice),
        "uncapped_sum": uncapped_sum,
        "cap_residual": cap_residual,
        "base_check": base_check,          # ~0 => base attribution faithful
        "n_comp": int(feat.shape[0]),
    }
    return (feat.astype(np.float32),
            np.asarray(y_base, np.float32),
            np.asarray(y_closure, np.float32),
            np.asarray(y_comp, np.float32),
            scal)


def _process(rec):
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game, board = replay_to(seed, ply)
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        cfg = _W["cfg"]
        pstate = board.state
        root_player = pstate.current_player
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}
        phase = rec.get("phase", "?")

        feats, ybs, ycs, ycomps, scals, oqs = [], [], [], [], [], []
        seen = set()
        for a in legal:
            a = int(a)
            if a not in aq:
                continue
            child, _ = game.get_next_state(board, a)
            cs = game.string_representation(child)
            if cs in seen:
                continue
            seen.add(cs)
            cstate = child.state
            ended = game.get_game_ended(child, root_player)
            if ended != 0:
                # terminal: no leaf structure to reproduce; skip from the
                # structure-supervision set (the leaf never evaluates terminals
                # via g_theta — the wrapper short-circuits them).
                continue
            feat, yb, yc, ycomp, scal = _emit_board(cstate, root_player, cfg)
            feats.append(feat); ybs.append(yb); ycs.append(yc); ycomps.append(ycomp)
            scals.append(scal); oqs.append(aq[a])

        if len(feats) < 1:
            return {"_error": f"{seed}:{ply} 0 non-terminal children"}
        return {
            "seed": seed, "ply": ply, "phase": phase,
            "feats": feats, "y_base": ybs, "y_closure": ycs, "y_comp": ycomps,
            "scals": scals, "oracle_q": oqs,
        }
    except Exception as e:
        import traceback
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}",
                "_tb": traceback.format_exc()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--out", default="/home/doctor/carc_probe_a/component_ds")
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfg = _provenance_guard()
    print(f"[schema] FEAT_DIM={FEAT_DIM}  (per-component features)")

    checks = {}
    for line in open(args.pool):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.probe):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]; recs.append(r)
    n_avail = len(recs)
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)}/{n_avail} sibling sets  workers={args.workers}")

    t0 = time.time()
    ALL_FEAT, ALL_YB, ALL_YC, ALL_YCOMP = [], [], [], []
    OFFSETS = [0]
    PRE, RUN, YSTR, BASE, CS, CO, MEEP, CLOI, UNCAP, CAPRES, BASECHK, NCOMP = ([] for _ in range(12))
    OQ, GID, GS, PLY, PH = [], [], [], [], []
    gid = 0; nerr = 0; nboards = 0; sample_errs = []
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for i, out in enumerate(pool.imap_unordered(_process, recs, chunksize=8)):
            if "_error" in out:
                nerr += 1
                if len(sample_errs) < 8:
                    sample_errs.append(out["_error"])
                    if "_tb" in out and len(sample_errs) <= 2:
                        print(out["_tb"])
                continue
            for j in range(len(out["feats"])):
                feat = out["feats"][j]
                ALL_FEAT.append(feat)
                ALL_YB.append(out["y_base"][j])
                ALL_YC.append(out["y_closure"][j])
                ALL_YCOMP.append(out["y_comp"][j])
                OFFSETS.append(OFFSETS[-1] + feat.shape[0])
                s = out["scals"][j]
                PRE.append(s["pretransform"]); RUN.append(s["running_diff"])
                YSTR.append(s["y_struct"]); BASE.append(s["base"])
                CS.append(s["closure_self"]); CO.append(s["closure_opp"])
                MEEP.append(s["meeple_contribution"]); CLOI.append(s["cloister_slice"])
                UNCAP.append(s["uncapped_sum"])
                CAPRES.append(s["cap_residual"]); BASECHK.append(s["base_check"])
                NCOMP.append(s["n_comp"])
                OQ.append(out["oracle_q"][j]); GID.append(gid); GS.append(out["seed"])
                PLY.append(out["ply"]); PH.append(out["phase"])
                nboards += 1
            gid += 1
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)} sets={gid} boards={nboards} err={nerr} "
                      f"{time.time()-t0:.0f}s", flush=True)
    dt = time.time() - t0
    print(f"[done] sets={gid} boards={nboards} err={nerr} in {dt:.0f}s "
          f"({len(recs)/max(dt,1):.0f}/s)")
    if sample_errs:
        print("  sample errors:", sample_errs)

    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)
    feat = np.concatenate(ALL_FEAT).astype(np.float32)
    y_base = np.concatenate(ALL_YB).astype(np.float32)
    y_closure = np.concatenate(ALL_YC).astype(np.float32)
    y_comp = np.concatenate(ALL_YCOMP).astype(np.float32)
    offsets = np.asarray(OFFSETS, np.int64)
    pre = np.asarray(PRE, np.float32); run = np.asarray(RUN, np.float32)
    ystr = np.asarray(YSTR, np.float32); base = np.asarray(BASE, np.float32)
    cs = np.asarray(CS, np.float32); co = np.asarray(CO, np.float32)
    meep = np.asarray(MEEP, np.float32); cloi = np.asarray(CLOI, np.float32)
    uncap = np.asarray(UNCAP, np.float32)
    capres = np.asarray(CAPRES, np.float32); basechk = np.asarray(BASECHK, np.float32)
    ncomp = np.asarray(NCOMP, np.int32)
    oq = np.asarray(OQ, np.float32); gid_a = np.asarray(GID, np.int32)
    gs = np.asarray(GS, np.int64); ply_a = np.asarray(PLY, np.int16)
    ph = np.asarray(PH, dtype="<U12")

    # per-column normalization over ALL component rows (f32). Constant columns
    # (reserved cloister cols, one-hots) guarded to std=1.
    col_mean = feat.mean(axis=0)
    col_std = feat.std(axis=0)
    col_std[col_std < 1e-6] = 1.0

    np.savez_compressed(
        outd / "component_ds.npz",
        feat=feat, y_base=y_base, y_closure=y_closure, y_comp=y_comp,
        board_offsets=offsets,
        pretransform=pre, running_diff=run, y_struct=ystr,
        base=base, closure_self=cs, closure_opp=co,
        meeple_contribution=meep, cloister_slice=cloi, uncapped_sum=uncap,
        cap_residual=capres, base_check=basechk, n_comp=ncomp,
        oracle_q=oq, group_id=gid_a, game_seed=gs, ply=ply_a, phase=ph,
        col_mean=col_mean.astype(np.float32), col_std=col_std.astype(np.float32),
        feat_dim=np.int32(FEAT_DIM),
    )
    meta = {
        "n_boards": int(nboards), "n_sets": int(gid), "n_sets_avail": int(n_avail),
        "n_component_rows": int(feat.shape[0]), "FEAT_DIM": int(FEAT_DIM),
        "n_games": int(len(set(gs.tolist()))),
        "teacher": "h6400_v2.9", "leaf": "v2.9_bmild_cap8", "v29_hash": FROZEN_V29_HASH,
        "leaf_config_hash": _cfg_hash(cfg),
        "source": args.probe, "pool": args.pool, "n_err": int(nerr),
        "targets": {
            "y_struct": "the g_theta STRUCTURAL target = pretransform - running_diff (the part derivable from current components). sum(y_comp) reconstructs its UNCAPPED form.",
            "running_diff": "points already scored (state.scores diff) — exact additive offset added at leaf time, NOT a g_theta target (closed features are off the board / not in features)",
            "y_comp": "per-component target = base+closure (real rows) / +cloister+meeple (econ row); sum == UNCAPPED y_struct",
            "pretransform": "board-level CAPPED heuristic pre-tanh (== virtual_score_v2 output float) = running_diff + y_struct",
            "cap_residual": "y_struct - uncapped_sum == closure-cap board-level nonlinearity (per-component sum can't cap)",
            "cloister_slice": "cloister base+closure folded onto econ target but NOT representable from econ features (cols 19-22 reserved 0) -> the reported cloister residual",
            "base_check": "final_diff - sum(y_base) — must be ~0 (base attribution bit-exact to flat_base_score)",
        },
        "scale_stats": {
            "pretransform_abs_mean": float(np.abs(pre).mean()),
            "running_diff_abs_mean": float(np.abs(run).mean()),
            "y_struct_abs_mean": float(np.abs(ystr).mean()),
            "y_struct_std": float(ystr.std()),
        },
        "cap_residual_stats": {
            "mean": float(capres.mean()), "std": float(capres.std()),
            "abs_mean": float(np.abs(capres).mean()),
            "frac_nonzero": float((np.abs(capres) > 1e-6).mean()),
        },
        "cloister_residual_stats": {
            "abs_mean": float(np.abs(cloi).mean()), "std": float(cloi.std()),
            "frac_nonzero": float((np.abs(cloi) > 1e-6).mean()),
        },
        "base_check_stats": {
            "abs_mean": float(np.abs(basechk).mean()),
            "abs_max": float(np.abs(basechk).max()),
            "frac_nonzero": float((np.abs(basechk) > 1e-4).mean()),
        },
        "normalization": "per-column z-score over all component rows (col_mean/col_std in npz)",
    }
    (outd / "meta.json").write_text(json.dumps(meta, indent=2))
    print("meta:", json.dumps({k: v for k, v in meta.items()
                               if k not in ("targets",)}, indent=2))
    print(f"[out] {outd/'component_ds.npz'}  feat.shape={feat.shape}  boards={nboards}")


if __name__ == "__main__":
    main()
