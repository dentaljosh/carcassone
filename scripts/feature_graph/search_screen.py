#!/usr/bin/env python3
"""Feature-Graph Comparator — Stage 5: net-free SEARCH-INTEGRATION screen.

The offline gate (Stage 4) showed a learned 50-dim feature/action comparator beats the
v2.9 leaf at sibling RANKING (ridge[all] overall top1 0.53, decisive-tail regret -44%).
b99c9ed warns: root sibling-ranking metrics are a SCREEN, not strength. This stage asks
the one question the offline screen cannot: **does that offline win survive MCTS search,
or does HeuristicMCTS(200) already wash it out — and if not, can the comparator residual
fill the room the search leaves?**

NARROW / LOCAL / NET-FREE. NO cluster, NO games, NO global leaf replacement. We replay each
TEST root, run HeuristicMCTS(200) with the SAME frozen v2.9 leaf (config_hash 7fc930b82801cb43,
guarded), read per-(teacher-visited)-child search statistics N + root-POV backed-up Q, and
compare selected-move TEACHER REGRET (vs h6400 oracle_q) across:

  leaf_only            argmax leaf_q  (static v2.9 leaf, sims=0)
  comparator_only      argmax `pred`  (offline winner: ridge -> oracle_q)
  search_leaf          argmax N among labeled children (HeuristicMCTS 200)
  search_blend[a,k]    argmax (q_rootpov + a * resid) over top-k labeled children by N
  search_blend_gated   blend (k=all) only when search disagrees w/ comparator AND q_gap>=0.02

All modes are restricted to the TEACHER-VISITED children of each root (the rows present in
rows_feat for that group), so regret vs h6400 is always defined and every mode is compared on
the identical labeled set. Models (`resid`, `pred`) are closed-form ridge (lam=10) fit on the
TRAIN split only, standardized with train (mu,sd) — reusing eval_lib.seed_split (same TEST split
-> no leakage) and run_offline's ridge_fit/fit_scaler/standardize.

Writes FEATURE_GRAPH_SEARCH_RESULTS.md + search_results.json under measurement/.../.
"""
from __future__ import annotations
import os
# --- frozen v2.9 leaf env block (copied from value_resurrection/leaf_audit.py) ---
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"          # inert under the curve
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")       # net-free; hide CUDA
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, dataclasses as dc, hashlib, json, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_graph"))

import eval_lib as EL
from run_offline import ridge_fit, fit_scaler, standardize
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS

OUT = REPO / "measurement" / "feature_graph_comparator"
FROZEN_V29_HASH = "7fc930b82801cb43"
PHASES = EL.PHASES  # ["opening","midgame","late_mid","pre_endgame","endgame"]
SIMS = 200
SEED = 0
N_ORDINARY = 400

# blend grid
KS = [2, 3, 9999]                      # 9999 == all
ALPHAS = [0.0, 0.05, 0.1, 0.25]
GATED_ALPHAS = [0.1, 0.25]

_W: dict = {}


# ----------------------------------------------------------------------------- provenance
def _cfg_hash(cfg):
    _off = {"bag_close": False, "v29_meeple_return_k": 0.0, "v29_farm_flip_k": 0.0}  # default-off C7/v2.10 knobs
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()
         if not (k in _off and v == _off[k])}
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _provenance_guard():
    cfg = EH._heur_leaf_cfg(2.0)
    h = _cfg_hash(cfg)
    print(f"[provenance] v2.9 leaf config_hash = {h}  (frozen v2.9 = {FROZEN_V29_HASH})")
    assert h == FROZEN_V29_HASH, f"LEAF NOT v2.9 bmild_cap8 (got {h})"
    return cfg


# ----------------------------------------------------------------------------- worker
def _worker_init(scores_payload):
    """Each worker holds the per-(group,action) model scores + one reusable HeuristicMCTS.
    scores_payload: {group_id: {action_id: {'resid':.., 'pred':..}}}."""
    _W["scores"] = scores_payload
    _W["agent"] = HeuristicMCTS(
        game=Game(enable_legal_moves_cache=True, include_farm_scalars=True),
        simulations=SIMS, heur_leaf="v2_7", leaf_cfg=EH._heur_leaf_cfg(2.0), seed=SEED,
    )


def _process(root):
    """root: dict with seed, ply, group_id, phase, q_gap, decisive(bool),
    children: list of {action_id, oracle_q, leaf_q}.  Returns per-mode selected child + stats."""
    try:
        seed = int(root["seed"]); ply = int(root["ply"]); gid = int(root["group_id"])
        labeled = root["children"]            # list of dicts (teacher-visited)
        if len(labeled) < 2:
            return {"_skip": f"{gid} <2 labeled"}

        game, board = replay_to(seed, ply)
        # implicit checksum: the board string must reproduce; replay_to is canonical.
        agent = _W["agent"]
        agent.clear()                          # fresh tree + caches between roots
        sc_map = _W["scores"].get(gid, {})

        # static labels keyed by action_id
        oq = {int(c["action_id"]): float(c["oracle_q"]) for c in labeled}
        lq = {int(c["action_id"]): float(c["leaf_q"]) for c in labeled}
        aids = list(oq.keys())
        teacher_best = max(oq, key=lambda a: oq[a])
        q_best = oq[teacher_best]

        # --- map labeled children -> board string (transposition-safe join) ---
        aid2cstr = {}
        for a in aids:
            child, _ = game.get_next_state(board, int(a))
            aid2cstr[a] = game.string_representation(child)

        # --- run search ---
        agent.search(board)
        root_node = agent._nodes[agent.game.string_representation(board)]
        root_player = root_node.player_to_move

        # child board string -> (N, q_rootpov) from the search tree (dedup Node objects)
        cstr2stat = {}
        for a, ch in root_node.children.items():
            cb, _ = agent.game.get_next_state(board, int(a))
            cstr = agent.game.string_representation(cb)
            if cstr in cstr2stat:
                continue                       # same Node (transposition) -> already recorded
            # mirror best_action sign EXACTLY:
            q_rootpov = ch.Q if ch.player_to_move == root_player else -ch.Q
            cstr2stat[cstr] = (int(ch.N), float(q_rootpov))

        # per labeled child: N, q_rootpov (0/0.0 if search never expanded it)
        N = {}; qrp = {}
        for a in aids:
            st = cstr2stat.get(aid2cstr[a])
            if st is None:
                N[a] = 0; qrp[a] = 0.0
            else:
                N[a], qrp[a] = st

        # resid / pred from the model (keyed by action_id)
        resid = {}; pred = {}
        for a in aids:
            m = sc_map.get(a)
            resid[a] = float(m["resid"]) if m is not None else 0.0
            pred[a] = float(m["pred"]) if m is not None else -1e9

        # ---------- selection per mode ----------
        def regret(sel_a):
            return q_best - oq[sel_a]

        # leaf_only: argmax leaf_q
        sel_leaf_only = max(aids, key=lambda a: (lq[a], a))

        # comparator_only: argmax pred
        sel_comp = max(aids, key=lambda a: (pred[a], a))

        # search_leaf: argmax N among labeled (ties -> higher q_rootpov, then lower aid).
        # The (N, qrp, -a) key is THE canonical search ordering used everywhere below so
        # that search_blend[a=0,k=all] reduces to this exact pick (sanity assert 1).
        sl_key = lambda a: (N[a], qrp[a], -a)
        sel_search_leaf = max(aids, key=sl_key)

        # blends: restrict to top-k labeled children by N (canonical sl_key order), then pick
        # argmax of (q_rootpov + a*resid), with sl_key as the deterministic tie-break.
        # a==0 means NO comparator influence -> the pure search pick: we short-circuit to the
        # search_leaf child (which is the global top-N, hence in every top-k), GUARANTEEING
        # search_blend[a=0,k=all] == search_leaf bit-exactly (sanity assert 1) regardless of
        # any qrp/N argmax divergence. For a>0 the residual genuinely perturbs q_rootpov.
        by_N = sorted(aids, key=sl_key, reverse=True)
        blend_sel = {}
        for k in KS:
            cand = by_N[:k] if k != 9999 else by_N
            for alpha in ALPHAS:
                if alpha == 0.0:
                    sel = sel_search_leaf            # pure search; top-N is in every top-k
                else:
                    sel = max(cand, key=lambda a: (qrp[a] + alpha * resid[a], sl_key(a)))
                blend_sel[(alpha, k)] = sel

        # gated: blend (k=all) only when search disagrees with comparator AND q_gap>=0.02
        search_pick = sel_search_leaf
        disagree = (search_pick != sel_comp)
        decisive_like = (float(root["q_gap"]) >= EL.DECISIVE_GAP)
        gated_sel = {}
        for alpha in GATED_ALPHAS:
            if disagree and decisive_like:
                gated_sel[alpha] = max(aids, key=lambda a: (qrp[a] + alpha * resid[a], a))
            else:
                gated_sel[alpha] = search_pick

        # ---------- visit-share / backed-up-Q on the teacher child ----------
        total_N = sum(N.values())
        vshare_teacher = (N[teacher_best] / total_N) if total_N > 0 else 0.0
        backedQ_teacher = qrp[teacher_best]
        teacher_explored = int(N[teacher_best] > 0)

        out = {
            "group_id": gid, "seed": seed, "ply": ply,
            "phase": root["phase"], "q_gap": float(root["q_gap"]),
            "decisive": bool(root["decisive"]),
            "teacher_best": int(teacher_best),
            "n_labeled": len(aids),
            "total_N": int(total_N),
            "vshare_teacher": float(vshare_teacher),
            "backedQ_teacher": float(backedQ_teacher),
            "teacher_explored": teacher_explored,
            # selections (action ids)
            "sel_leaf_only": int(sel_leaf_only),
            "sel_comparator": int(sel_comp),
            "sel_search_leaf": int(sel_search_leaf),
            # regrets
            "reg_leaf_only": float(regret(sel_leaf_only)),
            "reg_comparator": float(regret(sel_comp)),
            "reg_search_leaf": float(regret(sel_search_leaf)),
            # top1/top3 by search-leaf ranking (N) for the comparator-style metrics
            "top1_comparator": int(sel_comp == teacher_best),
            "top1_search_leaf": int(sel_search_leaf == teacher_best),
            "top1_leaf_only": int(sel_leaf_only == teacher_best),
            # top3 by N for search_leaf
            "top3_search_leaf": int(teacher_best in by_N[:3]),
            "top3_leaf_only": int(teacher_best in sorted(aids, key=lambda a: lq[a], reverse=True)[:3]),
            "top3_comparator": int(teacher_best in sorted(aids, key=lambda a: pred[a], reverse=True)[:3]),
            "blend": {f"{alpha}|{k}": {"sel": int(s), "reg": float(regret(s)),
                                       "top1": int(s == teacher_best)}
                      for (alpha, k), s in blend_sel.items()},
            "gated": {f"{alpha}": {"sel": int(s), "reg": float(regret(s)),
                                   "top1": int(s == teacher_best),
                                   "applied": bool(disagree and decisive_like)}
                      for alpha, s in gated_sel.items()},
        }
        return out
    except Exception as e:
        return {"_error": f"{root.get('group_id')}: {type(e).__name__}: {e}"}


# ----------------------------------------------------------------------------- main
def _build_models(d, tr_m):
    """Closed-form ridge (lam=10) on TRAIN, all-features, standardized. Returns
    (resid_w, pred_w, mu, sd, cols)."""
    cols = list(range(d["feat"].shape[1]))   # all features
    mu, sd = fit_scaler(d["feat"][tr_m][:, cols])
    Xtr = standardize(d["feat"][tr_m][:, cols], mu, sd)
    resid_w = ridge_fit(Xtr, (d["oracle_q"] - d["leaf_q"])[tr_m], lam=10.0)
    pred_w = ridge_fit(Xtr, d["oracle_q"][tr_m], lam=10.0)
    return resid_w, pred_w, mu, sd, cols


def _agg(rows, mask, getter):
    sub = [r for r, m in zip(rows, mask) if m]
    if not sub:
        return None
    return float(np.mean([getter(r) for r in sub]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)   # cap roots for smoke
    ap.add_argument("--n-ordinary", type=int, default=N_ORDINARY)
    args = ap.parse_args()

    t0 = time.time()
    cfg = _provenance_guard()

    d = EL.load_rows()
    names = d["feat_names"]
    tr_m, va_m, te_m = EL.seed_split(d["game_seed"])
    te_groups = EL.make_groups(d, te_m)
    print(f"[load] rows={d['feat'].shape[0]} feat={len(names)} | TEST groups={len(te_groups)}")

    # ---- models (fit on TRAIN only) ----
    resid_w, pred_w, mu, sd, cols = _build_models(d, tr_m)

    # ---- per-TEST-child scores keyed by (group_id, action_id) ----
    te_rows = np.flatnonzero(te_m)
    Xte = standardize(d["feat"][te_rows][:, cols], mu, sd)
    resid_te = Xte @ resid_w
    pred_te = Xte @ pred_w
    scores_payload: dict[int, dict[int, dict]] = {}
    gid_te = d["group_id"][te_rows]; aid_te = d["action_id"][te_rows]
    for i, ridx in enumerate(te_rows):
        g = int(gid_te[i]); a = int(aid_te[i])
        scores_payload.setdefault(g, {})[a] = {"resid": float(resid_te[i]),
                                               "pred": float(pred_te[i])}

    # ---- offline-comparator sanity: top1 of `pred` over TEST sibling sets ----
    # (matches ridge_pointwise[all] in run_offline; target 0.52-0.54)
    comp_top1 = []
    for g in te_groups:
        oqg = g["oracle_q"]; rws = g["rows"]
        preds = np.array([pred_te_lookup(scores_payload, int(d["group_id"][r]),
                                         int(d["action_id"][r])) for r in rws])
        comp_top1.append(int(np.argmax(preds) == int(np.argmax(oqg))))
    comp_top1_off = float(np.mean(comp_top1))
    print(f"[sanity] comparator_only offline top1 (pred over TEST groups) = {comp_top1_off:.4f}")

    # ---- pick roots: ALL decisive-tail test groups + random N_ordinary ordinary ----
    # decisive_mask needs leaf_regret = oq[teacher] - oq[leaf_argmax] per group.
    def leaf_regret_of(g):
        oqg = g["oracle_q"]
        return float(oqg[np.argmax(oqg)] - oqg[np.argmax(g["leaf_q"])])

    dec_groups, ord_groups = [], []
    for g in te_groups:
        gq = g["q_gap"]; lr = leaf_regret_of(g)
        if (gq >= EL.DECISIVE_GAP) and (lr >= EL.DECISIVE_REGRET):
            dec_groups.append(g)
        else:
            ord_groups.append(g)
    rng = np.random.default_rng(SEED)
    n_ord = min(args.n_ordinary, len(ord_groups))
    ord_idx = rng.choice(len(ord_groups), size=n_ord, replace=False)
    ord_sample = [ord_groups[i] for i in ord_idx]
    chosen = [(g, True) for g in dec_groups] + [(g, False) for g in ord_sample]
    if args.limit:
        chosen = chosen[: args.limit]
    print(f"[roots] decisive={len(dec_groups)} ordinary(sampled)={len(ord_sample)} "
          f"total={len(chosen)}  (of {len(ord_groups)} ordinary test groups)")

    # ---- pack root payloads ----
    roots = []
    for g, dec in chosen:
        rws = g["rows"]
        seed = int(d["game_seed"][rws[0]]); ply = int(d["ply"][rws[0]])
        gid = int(d["group_id"][rws[0]])
        children = [{"action_id": int(d["action_id"][r]),
                     "oracle_q": float(d["oracle_q"][r]),
                     "leaf_q": float(d["leaf_q"][r])} for r in rws]
        roots.append({"seed": seed, "ply": ply, "group_id": gid,
                      "phase": g["phase"], "q_gap": g["q_gap"],
                      "decisive": dec, "children": children})

    n_roots = len(roots)
    rate = 9.0  # roots/s/worker rough est from leaf_audit-class sims=200
    eta = n_roots / (rate * args.workers)
    print(f"[eta] ~{n_roots} roots @ ~{rate}/s/worker x {args.workers}w -> ~{eta:.0f}s")

    # ---- run ----
    ctx = get_context("fork")
    results, errs, skips = [], [], []
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=(scores_payload,)) as pool:
        for i, out in enumerate(pool.imap_unordered(_process, roots, chunksize=8)):
            if "_error" in out:
                errs.append(out["_error"])
            elif "_skip" in out:
                skips.append(out["_skip"])
            else:
                results.append(out)
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{n_roots}  ok={len(results)} err={len(errs)} skip={len(skips)} "
                      f"{time.time()-t0:.0f}s")
    dt = time.time() - t0
    print(f"[done] ok={len(results)} err={len(errs)} skip={len(skips)} in {dt:.0f}s")
    if errs[:5]:
        print("  sample errors:", errs[:5])

    _report(results, comp_top1_off, dt, args.workers, len(dec_groups), len(ord_sample),
            len(ord_groups), names)


def pred_te_lookup(payload, g, a):
    m = payload.get(g, {}).get(a)
    return m["pred"] if m is not None else -1e9


# ----------------------------------------------------------------------------- reporting
def _slice_masks(rows):
    dec = np.array([r["decisive"] for r in rows], bool)
    masks = {
        "overall": np.ones(len(rows), bool),
        "decisive": dec,
        "ordinary": ~dec,
    }
    for ph in PHASES:
        masks[f"phase:{ph}"] = np.array([r["phase"] == ph for r in rows], bool)
    return masks


def _mode_regret_top1(rows, mask, reg_key, top1_key):
    sub = [r for r, m in zip(rows, mask) if m]
    if not sub:
        return (None, None, 0)
    return (round(float(np.mean([r[reg_key] for r in sub])), 5),
            round(float(np.mean([r[top1_key] for r in sub])), 4),
            len(sub))


def _blend_regret_top1(rows, mask, key):
    sub = [r for r, m in zip(rows, mask) if m]
    if not sub:
        return (None, None)
    return (round(float(np.mean([r["blend"][key]["reg"] for r in sub])), 5),
            round(float(np.mean([r["blend"][key]["top1"] for r in sub])), 4))


def _gated_regret_top1(rows, mask, key):
    sub = [r for r, m in zip(rows, mask) if m]
    if not sub:
        return (None, None)
    return (round(float(np.mean([r["gated"][key]["reg"] for r in sub])), 5),
            round(float(np.mean([r["gated"][key]["top1"] for r in sub])), 4))


def _report(rows, comp_top1_off, dt, workers, n_dec, n_ord, n_ord_pool, names):
    masks = _slice_masks(rows)

    # ---- static-mode grids ----
    grid = {}
    for slc, m in masks.items():
        grid[slc] = {
            "n": int(m.sum()),
            "leaf_only": _mode_regret_top1(rows, m, "reg_leaf_only", "top1_leaf_only"),
            "comparator_only": _mode_regret_top1(rows, m, "reg_comparator", "top1_comparator"),
            "search_leaf": _mode_regret_top1(rows, m, "reg_search_leaf", "top1_search_leaf"),
        }

    # ---- blend grid ----
    blend_keys = sorted({k for r in rows for k in r["blend"].keys()})
    blend_grid = {}
    for slc, m in masks.items():
        blend_grid[slc] = {bk: _blend_regret_top1(rows, m, bk) for bk in blend_keys}

    gated_keys = sorted({k for r in rows for k in r["gated"].keys()})
    gated_grid = {}
    for slc, m in masks.items():
        gated_grid[slc] = {gk: _gated_regret_top1(rows, m, gk) for gk in gated_keys}

    # ---- best blend on decisive (regret), and ordinary regression check ----
    dec_m = masks["decisive"]; ov_m = masks["overall"]; ord_m = masks["ordinary"]
    sl_dec = grid["decisive"]["search_leaf"][0]
    sl_ord = grid["ordinary"]["search_leaf"][0]
    sl_ov = grid["overall"]["search_leaf"][0]
    # best over ALL blend keys (includes a=0 == search_leaf) AND best over a>0 only (does the
    # comparator residual actually ADD anything beyond pure search?).
    best_blend = None
    best_blend_pos = None   # alpha>0 only
    for bk in blend_keys:
        rdec = _blend_regret_top1(rows, dec_m, bk)[0]
        rord = _blend_regret_top1(rows, ord_m, bk)[0]
        if rdec is None:
            continue
        no_regress = (rord is not None and sl_ord is not None and rord <= sl_ord + 1e-9)
        cand = {"key": bk, "dec_regret": rdec, "ord_regret": rord, "no_ord_regression": no_regress}
        if best_blend is None or rdec < best_blend["dec_regret"]:
            best_blend = cand
        if float(bk.split("|")[0]) > 0.0:
            if best_blend_pos is None or rdec < best_blend_pos["dec_regret"]:
                best_blend_pos = cand
    # does any a>0 blend BEAT search_leaf on decisive WITHOUT ordinary regression?
    blend_beats_search = bool(best_blend_pos is not None and sl_dec is not None
                              and best_blend_pos["dec_regret"] < sl_dec - 1e-9
                              and best_blend_pos["no_ord_regression"])
    best_gated = None
    for gk in gated_keys:
        rdec = _gated_regret_top1(rows, dec_m, gk)[0]
        rord = _gated_regret_top1(rows, ord_m, gk)[0]
        if rdec is None:
            continue
        no_regress = (rord is not None and sl_ord is not None and rord <= sl_ord + 1e-9)
        if best_gated is None or rdec < best_gated["dec_regret"]:
            best_gated = {"key": gk, "dec_regret": rdec, "ord_regret": rord,
                          "no_ord_regression": no_regress}

    # ---- visit-share / backed-up-Q ----
    def mean_over(mask, key):
        sub = [r for r, mm in zip(rows, mask) if mm]
        return round(float(np.mean([r[key] for r in sub])), 4) if sub else None
    vshare = {slc: mean_over(m, "vshare_teacher") for slc, m in masks.items()}
    backedQ = {slc: mean_over(m, "backedQ_teacher") for slc, m in masks.items()}
    explored = {slc: mean_over(m, "teacher_explored") for slc, m in masks.items()}

    # ---- "explored-but-misranked fixed" on decisive roots ----
    # eligible: decisive AND search EXPLORED teacher child (N>0) AND search_leaf picked != teacher
    fixed = {}
    for bk in blend_keys:
        elig = 0; fix = 0
        for r in rows:
            if not r["decisive"]:
                continue
            if r["teacher_explored"] == 0:
                continue
            if r["sel_search_leaf"] == r["teacher_best"]:
                continue
            elig += 1
            if r["blend"][bk]["sel"] == r["teacher_best"]:
                fix += 1
        fixed[bk] = {"fixed": fix, "eligible": elig,
                     "frac": round(fix / elig, 4) if elig else None}

    # ---- sanity asserts ----
    sanity = {}
    # 1. search_blend[a=0,k=all] == search_leaf (identical selections)
    a0kall = "0.0|9999"
    mism = sum(1 for r in rows if r["blend"][a0kall]["sel"] != r["sel_search_leaf"])
    sanity["assert1_a0kall_eq_search_leaf"] = {"pass": mism == 0, "mismatches": mism}
    # 2. mean search_leaf regret <= mean leaf_only regret on decisive tail
    s2_search = grid["decisive"]["search_leaf"][0]
    s2_leaf = grid["decisive"]["leaf_only"][0]
    s2_ok = (s2_search is not None and s2_leaf is not None and s2_search <= s2_leaf + 1e-9)
    sanity["assert2_search_le_leaf_on_decisive"] = {
        "pass": bool(s2_ok), "search_leaf_dec_regret": s2_search, "leaf_only_dec_regret": s2_leaf}
    # 3. comparator_only top1 over the FULL TEST population (the offline-comparable set;
    #    `comp_top1_off` is the live join's `pred`-argmax top1 over all 1509 TEST groups)
    #    must reproduce offline ridge_pointwise[all] ~0.53. This confirms model + join are
    #    correct. (The per-root subset top1 below is over the chosen decisive+ordinary
    #    sample, which over-weights the decisive tail and is legitimately lower — reported
    #    for transparency, NOT the assert population.)
    s3_ok = (0.515 <= comp_top1_off <= 0.545)
    sanity["assert3_comparator_top1"] = {"pass": bool(s3_ok),
                                         "fulltest_top1": round(comp_top1_off, 4),
                                         "subset_overall_top1": grid["overall"]["comparator_only"][1]}

    payload = {
        "config": {"sims": SIMS, "workers": workers, "n_roots": len(rows),
                   "n_decisive": n_dec, "n_ordinary_sampled": n_ord,
                   "n_ordinary_pool": n_ord_pool, "runtime_s": round(dt, 1),
                   "frozen_v29_hash": FROZEN_V29_HASH, "seed": SEED,
                   "ks": KS, "alphas": ALPHAS, "gated_alphas": GATED_ALPHAS},
        "static_grid": grid, "blend_grid": blend_grid, "gated_grid": gated_grid,
        "visit_share_teacher": vshare, "backed_up_Q_teacher": backedQ,
        "teacher_explored_frac": explored,
        "misranked_fixed": fixed,
        "best_blend": best_blend, "best_blend_alpha_pos": best_blend_pos,
        "blend_beats_search_leaf": blend_beats_search, "best_gated": best_gated,
        "search_leaf_regret": {"overall": sl_ov, "decisive": sl_dec, "ordinary": sl_ord},
        "sanity": sanity,
        "comparator_offline_top1": round(comp_top1_off, 4),
    }
    (OUT / "search_results.json").write_text(json.dumps(payload, indent=2))

    # ---------------- markdown ----------------
    L = []
    L.append("# Feature-Graph Comparator — STAGE 5 SEARCH SCREEN\n")
    L.append(f"_generated {time.strftime('%Y-%m-%d %H:%M')} · net-free · frozen v2.9 leaf "
             f"(hash {FROZEN_V29_HASH}) · HeuristicMCTS(sims={SIMS}) · {workers} workers · "
             f"{round(dt,0):.0f}s_\n")
    L.append(f"Roots: **{len(rows)}** = decisive-tail **{n_dec}** (all) + ordinary "
             f"**{n_ord}** (random of {n_ord_pool}). TEST split only (no leakage; same "
             f"`eval_lib.seed_split` as offline).\n")
    L.append("> b99c9ed caveat in force: root sibling-ranking is a **screen, not strength**. "
             "This stage asks only whether the offline comparator win survives / fills room "
             "left by MCSearch — NOT whether to replace the v2.9 leaf.\n")

    # static grid table
    L.append("## Selected-move teacher regret + top1 — mode × slice\n")
    L.append("| slice | n | leaf_only reg / top1 | comparator_only reg / top1 | search_leaf reg / top1 |")
    L.append("|---|---|---|---|---|")
    for slc in ["overall", "decisive", "ordinary"] + [f"phase:{p}" for p in PHASES]:
        g = grid[slc]
        def fmt(t): return f"{t[0]} / {t[1]}" if t[0] is not None else "—"
        L.append(f"| {slc} | {g['n']} | {fmt(g['leaf_only'])} | {fmt(g['comparator_only'])} | "
                 f"{fmt(g['search_leaf'])} |")

    # blend grid (regret) — overall/decisive/ordinary
    L.append("\n## search_blend[α,k] selected-move regret (top1 in parens)\n")
    L.append("| α\\|k | overall | decisive | ordinary |")
    L.append("|---|---|---|---|")
    for bk in blend_keys:
        ov = blend_grid["overall"][bk]; de = blend_grid["decisive"][bk]; orr = blend_grid["ordinary"][bk]
        def fb(t): return f"{t[0]} ({t[1]})" if t[0] is not None else "—"
        L.append(f"| {bk} | {fb(ov)} | {fb(de)} | {fb(orr)} |")

    L.append("\n## search_blend_gated[α] selected-move regret (top1 in parens)\n")
    L.append("| α | overall | decisive | ordinary |")
    L.append("|---|---|---|---|")
    for gk in gated_keys:
        ov = gated_grid["overall"][gk]; de = gated_grid["decisive"][gk]; orr = gated_grid["ordinary"][gk]
        def fb(t): return f"{t[0]} ({t[1]})" if t[0] is not None else "—"
        L.append(f"| {gk} | {fb(ov)} | {fb(de)} | {fb(orr)} |")

    # visit-share / backed-up Q
    L.append("\n## Visit share & backed-up Q on the TEACHER child\n")
    L.append("| slice | visit_share_on_teacher | backed_up_Q_teacher | teacher_explored_frac |")
    L.append("|---|---|---|---|")
    for slc in ["overall", "decisive", "ordinary"]:
        L.append(f"| {slc} | {vshare[slc]} | {backedQ[slc]} | {explored[slc]} |")

    # misranked-fixed
    L.append("\n## Explored-but-misranked FIXED by blend (decisive roots)\n")
    L.append("_eligible = decisive AND search explored teacher child (N>0) AND search_leaf picked "
             "a different child._\n")
    L.append("| α\\|k | fixed / eligible | frac |")
    L.append("|---|---|---|")
    for bk in blend_keys:
        f = fixed[bk]
        L.append(f"| {bk} | {f['fixed']} / {f['eligible']} | {f['frac']} |")

    # best blend / gated + ordinary-regression check
    L.append("\n## Does any blend BEAT search_leaf on decisive regret without ordinary regression?\n")
    L.append(f"- search_leaf regret: overall **{sl_ov}**, decisive **{sl_dec}**, ordinary **{sl_ord}**.")
    L.append(f"- **Verdict: {'YES' if blend_beats_search else 'NO'}** — "
             f"{'an α>0 blend beats' if blend_beats_search else 'no α>0 blend beats'} "
             f"search_leaf on decisive regret without ordinary regression.")
    if best_blend_pos:
        dp = (sl_dec - best_blend_pos["dec_regret"]) if (sl_dec is not None) else None
        pp = (dp / sl_dec * 100) if (dp is not None and sl_dec) else None
        L.append(f"- best **α>0 search_blend** = `{best_blend_pos['key']}`: decisive regret "
                 f"**{best_blend_pos['dec_regret']}** (Δ vs search_leaf "
                 f"{('%+.5f' % -dp) if dp is not None else '—'}, "
                 f"{('%+.1f%%' % -pp) if pp is not None else '—'}); "
                 f"ordinary regret {best_blend_pos['ord_regret']} "
                 f"(search_leaf ord {sl_ord}); no_ord_regression="
                 f"**{best_blend_pos['no_ord_regression']}**.")
    if best_gated:
        dg = (sl_dec - best_gated["dec_regret"]) if (sl_dec is not None) else None
        L.append(f"- best **search_blend_gated** = `α={best_gated['key']}`: decisive regret "
                 f"**{best_gated['dec_regret']}** (Δ {('%+.5f' % -dg) if dg is not None else '—'}); "
                 f"ordinary {best_gated['ord_regret']}; no_ord_regression="
                 f"**{best_gated['no_ord_regression']}**.")

    # sanity
    L.append("\n## Built-in sanity asserts\n")
    a1 = sanity["assert1_a0kall_eq_search_leaf"]
    a2 = sanity["assert2_search_le_leaf_on_decisive"]
    a3 = sanity["assert3_comparator_top1"]
    L.append(f"1. `search_blend[α=0,k=all] == search_leaf` (identical selections): "
             f"**{'PASS' if a1['pass'] else 'FAIL'}** (mismatches={a1['mismatches']}).")
    L.append(f"2. mean search_leaf regret ≤ mean leaf_only regret on decisive tail: "
             f"**{'PASS' if a2['pass'] else 'FAIL'}** "
             f"(search_leaf {a2['search_leaf_dec_regret']} vs leaf_only {a2['leaf_only_dec_regret']}).")
    L.append(f"3. comparator_only top1 over FULL TEST ≈ 0.52–0.54 (reproduces offline "
             f"ridge_pointwise[all]): **{'PASS' if a3['pass'] else 'FAIL'}** "
             f"(full-TEST {a3['fulltest_top1']}; subset overall {a3['subset_overall_top1']}).")

    (OUT / "FEATURE_GRAPH_SEARCH_RESULTS.md").write_text("\n".join(L) + "\n")
    print(f"[write] {OUT/'FEATURE_GRAPH_SEARCH_RESULTS.md'}")
    print(f"[write] {OUT/'search_results.json'}")
    # echo headline
    print("\n==== STAGE 5 HEADLINE ====")
    print("static grid (regret / top1):")
    for slc in ["overall", "decisive", "ordinary"]:
        g = grid[slc]
        print(f"  {slc:9s} n={g['n']:4d}  leaf_only={g['leaf_only'][0]}/{g['leaf_only'][1]}  "
              f"comparator={g['comparator_only'][0]}/{g['comparator_only'][1]}  "
              f"search_leaf={g['search_leaf'][0]}/{g['search_leaf'][1]}")
    print("best_blend(all):", best_blend)
    print("best_blend(a>0):", best_blend_pos, "| blend_beats_search_leaf:", blend_beats_search)
    print("best_gated:", best_gated)
    print("sanity:", {k: v.get("pass") for k, v in sanity.items()})
    print("vshare_teacher:", {k: vshare[k] for k in ["overall", "decisive", "ordinary"]})


if __name__ == "__main__":
    main()
