#!/usr/bin/env python3
"""Stage A-lite: does RoD2 move toward h6400, or stay h3200-like/diffuse?

Fixed shared position set = measurement/deeper_search_ruler/multiphase_positions.jsonl
(seed+ply, checksum-verified). v2.9 leaf on the RULERS (hard-set env BELOW, before any
carcassonne import -> eval_hybrid_handoff's setdefault becomes a no-op -> DEFAULT_CONFIG = v2.9).

Per position we record:
  rulers:  h3200_v2.9, h6400_v2.9   chosen move (HeuristicMCTS best_action)
  nets:    RoD1_v29, iter04, iter06  prior_argmax (policy head, leaf-independent)
                                     + NeuralMCTS@200 (v2.9 leaf, rs=0.25) chosen move
Then: on the h3200 != h6400 DISAGREEMENT subset, does each net's prior/NMCTS pick the
h6400 move (deep), the h3200 move (shallow), or neither (diffuse)?  Trajectory RoD1->04->06.
"""
from __future__ import annotations
import os
# ---- v2.9 FROZEN leaf env (Bmild_cap8) — HARD SET, before any carcassonne/EH import ----
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"            # inert under the curve
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")        # nets on CPU; scale with workers
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, json, math, sys, time
from pathlib import Path
from multiprocessing import get_context

REPO = Path(__file__).resolve().parents[5] if False else Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import eval_hybrid_handoff as EH                          # sets v2.7 env via setdefault (no-op now)
from gen_endgame_positions import replay_to
from carcassonne_ai.mcts import HeuristicMCTS

NETS = {
    "rod1":   "/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt",
    "iter04": "/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt",
    "iter06": "/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_06.pt",
}
RULERS = [("h3200", 3200), ("h6400", 6400)]
_W: dict = {}


def _provenance():
    """Print the resolved leaf config so the log PROVES the rulers are v2.9."""
    import dataclasses as dc
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    cfg = EH._heur_leaf_cfg(2.0)  # exactly what the rulers use
    fields = {f.name: getattr(cfg, f.name) for f in dc.fields(cfg)}
    keys = ["bonus_cap", "opp_cap", "drop_three_open", "v29_meeple_curve",
            "meeple_k", "closure_open_fracs", "tanh_value_norm"]
    print("[provenance] ruler leaf_cfg (must be v2.9 Bmild_cap8):")
    for k in keys:
        if k in fields:
            print(f"    {k} = {fields[k]}")
    try:
        from carcassonne_ai.virtual_score_v2 import config_hash  # type: ignore
        print(f"    config_hash = {config_hash(cfg)}  (frozen v2.9 = 7fc930b82801cb43)")
    except Exception:
        pass
    return fields


def _harvest(mcts, board, game):
    mcts.clear()
    visits = mcts.search(board)
    chosen = int(mcts.best_action(board))
    tot = sum(visits.values()) or 1
    items = sorted(visits.items(), key=lambda kv: -kv[1])
    share = {a: n / tot for a, n in visits.items()}
    ent = -sum(p * math.log(p) for p in share.values() if p > 0)
    return chosen, round(float(items[0][1] / tot), 4), round(float(ent), 4)


def _worker_init():
    import torch
    torch.set_num_threads(1)
    from carcassonne_ai.network import CarcassonneNet
    from carcassonne_ai.evaluators import make_single_evaluator
    dev = torch.device("cpu")
    _W["nets"] = {}
    for name, path in NETS.items():
        ck = torch.load(path, map_location=dev, weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
        net.load_state_dict(ck["model_state"]); net.train(False)
        gf = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=(ns > 10))
        base = make_single_evaluator(net, dev, gf)
        _W["nets"][name] = {"base": base, "game": gf, "ns": ns}


def _process(rec):
    import numpy as np
    try:
        game, board = replay_to(rec["seed"], rec["ply"])
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{rec['gen_id']}: checksum_mismatch"}
        seed = rec["seed"]
        out = {k: rec.get(k) for k in ("gen_id", "seed", "ply", "k_remaining",
                                       "phase", "legal_n")}
        # rulers (v2.9 heuristic)
        for name, sims in RULERS:
            m = HeuristicMCTS(game=game, simulations=sims, seed=seed * 13 + sims,
                              heur_leaf="v2_7", leaf_cfg=EH._heur_leaf_cfg(2.0))
            ch, tshare, ent = _harvest(m, board, game)
            out[f"{name}_choice"] = ch
            out[f"{name}_top_share"] = tshare
        # nets: prior argmax (leaf-independent) + NeuralMCTS@200 (v2.9 leaf)
        for name, w in _W["nets"].items():
            gf = w["game"]
            _, board_f = replay_to(seed, rec["ply"])
            legal = np.flatnonzero(gf.get_valid_moves(board_f)).astype(int)
            prior, _v = w["base"](board_f)
            prior_arg = int(legal[int(np.argmax([prior[a] for a in legal]))])
            nm = EH._make_iter8_mcts(w["base"], gf, seed * 13 + 1, 2.0)
            nm_ch, nm_share, nm_ent = _harvest(nm, board_f, gf)
            out[f"{name}_prior"] = prior_arg
            out[f"{name}_nm"] = nm_ch
            out[f"{name}_nm_share"] = nm_share
        return out
    except Exception as e:
        return {"_error": f"{rec.get('gen_id')}: {type(e).__name__}: {e}"}


def analyze(rows, out_md):
    valid = [r for r in rows if "_error" not in r
             and r.get("h3200_choice") is not None and r.get("h6400_choice") is not None]
    disagree = [r for r in valid if r["h3200_choice"] != r["h6400_choice"]]
    nD = len(disagree)

    def frac(sub, pred):
        return (sum(1 for r in sub if pred(r)) / len(sub)) if sub else float("nan")

    lines = []
    lines.append("# Stage A-lite — Policy Root Audit (RoD2, v2.9 rulers)\n")
    lines.append(f"Fixed set: multiphase_positions.jsonl · n_valid={len(valid)} · "
                 f"h3200≠h6400 disagreement subset n={nD} ({nD/max(len(valid),1)*100:.0f}%)\n")
    lines.append("Question: on the disagreement subset, does each net pick the **h6400** (deep) "
                 "move, the **h3200** (shallow) move, or **neither** (diffuse)? "
                 "`lean = P(h6400) − P(h3200)`; lean>0 = moving toward deep search.\n")

    # overall top-1 agreement (all valid)
    lines.append("\n## Overall top-1 agreement (all valid positions)\n")
    lines.append("| net | prior=h6400 | prior=h3200 | NMCTS=h6400 | NMCTS=h3200 |")
    lines.append("|---|--:|--:|--:|--:|")
    for n in ("rod1", "iter04", "iter06"):
        lines.append(f"| {n} | {frac(valid, lambda r,n=n: r.get(n+'_prior')==r['h6400_choice']):.3f} "
                     f"| {frac(valid, lambda r,n=n: r.get(n+'_prior')==r['h3200_choice']):.3f} "
                     f"| {frac(valid, lambda r,n=n: r.get(n+'_nm')==r['h6400_choice']):.3f} "
                     f"| {frac(valid, lambda r,n=n: r.get(n+'_nm')==r['h3200_choice']):.3f} |")

    # disagreement subset (the crux)
    lines.append(f"\n## Disagreement subset (h3200≠h6400, n={nD}) — the crux\n")
    lines.append("| net | signal | P(h6400) | P(h3200) | P(neither) | lean (h6400−h3200) |")
    lines.append("|---|---|--:|--:|--:|--:|")
    summary = {}
    for n in ("rod1", "iter04", "iter06"):
        for sig, key in (("prior", n + "_prior"), ("NMCTS@200", n + "_nm")):
            p6 = frac(disagree, lambda r, k=key: r.get(k) == r["h6400_choice"])
            p3 = frac(disagree, lambda r, k=key: r.get(k) == r["h3200_choice"])
            pn = frac(disagree, lambda r, k=key: r.get(k) not in (r["h6400_choice"], r["h3200_choice"]))
            lines.append(f"| {n} | {sig} | {p6:.3f} | {p3:.3f} | {pn:.3f} | {p6-p3:+.3f} |")
            summary[(n, sig)] = (p6, p3, pn, p6 - p3)

    # trajectory verdict
    lines.append("\n## Trajectory (prior lean on disagreement subset)\n")
    traj = [summary[(n, "prior")][3] for n in ("rod1", "iter04", "iter06")]
    lines.append(f"RoD1 {traj[0]:+.3f} → iter04 {traj[1]:+.3f} → iter06 {traj[2]:+.3f}\n")
    moved = (traj[2] - traj[0])
    lines.append(f"Δlean(iter06 − RoD1) = {moved:+.3f}. "
                 f"(|Δ| within ~{1/math.sqrt(max(nD,1)):.3f} ≈ 1/√n is noise.)\n")

    print("\n".join(lines))
    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text("\n".join(lines) + "\n")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", default=str(REPO / "measurement/deeper_search_ruler/multiphase_positions.jsonl"))
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--stride", type=int, default=0, help="if>0, take every Nth (span phases)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=str(REPO / "measurement/rod_v2_flywheel/autopsy"))
    args = ap.parse_args(argv)

    _provenance()
    recs = [json.loads(l) for l in open(args.positions)]
    if args.stride > 0:
        recs = recs[:: args.stride]
    if args.limit:
        recs = recs[: args.limit]
    print(f"[stage-a-lite] {len(recs)} positions x (h3200_v2.9,h6400_v2.9 + 3 nets prior+NMCTS) "
          f"W={args.workers}", flush=True)
    t0 = time.perf_counter()
    ctx = get_context("fork")
    rows, done = [], 0
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for r in pool.imap_unordered(_process, recs, chunksize=1):
            rows.append(r); done += 1
            if done % 50 == 0 or done == len(recs):
                el = time.perf_counter() - t0
                print(f"  {done}/{len(recs)} ({el/done:.2f}s/pos, ~{(len(recs)-done)*el/max(done,1)/60:.1f} min left)", flush=True)
    errs = [r for r in rows if "_error" in r]
    Path(args.out).mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(Path(args.out) / "stage_a_lite_rows.json", "w"))
    print(f"[stage-a-lite] {len(rows)} rows, {len(errs)} errors, {(time.perf_counter()-t0)/60:.1f} min", flush=True)
    if errs:
        print(f"[stage-a-lite] sample errors: {[e['_error'] for e in errs[:3]]}", flush=True)
    analyze(rows, str(Path(args.out) / "POLICY_ROOT_AUDIT.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
