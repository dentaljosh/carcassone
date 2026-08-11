#!/usr/bin/env python3
"""Value Resurrection Pilot — Stage 4 (train V1-V5) + Stage 5 (offline value gate).

Reuses the CL-021 model/loss blocks (RankNet, listnet_loss, kendall_tau_b) but:
  - targets the v2.9 leaf RESIDUAL where the variant calls for it,
  - and gauges the pilot's REAL question with the COMBINED ranker
        score(child) = leaf_q(child) + alpha * learned(child)
    swept over alpha (alpha=0 == v2.9-leaf-alone baseline), on the held-out TEST split.

Variants (policy frozen — standalone value/ranking head only):
  V4_listwise       arm B (ListNet), target = h6400 Q           (≈ CL-021 arm B, the kill-test)
  V2_advantage      arm E (ListNet, within-group centered), target = h6400 Q
  V1_residual_mse   arm A (MSE), target = h6400 Q - v2.9 leaf
  V1r_residual_list arm B (ListNet), target = h6400 Q - v2.9 leaf
  V5_endgame        arm B, target = h6400 Q, TRAIN on end/pre_endgame only

Stage-5 gate: does any variant make `leaf + alpha*learned` beat `leaf` alone on held-out sibling
regret (>=15-20% down, top1 up, no ordinary catastrophe)?  If not -> Decision B.  net-alone
Kendall-tau vs h6400 is reported too (the CL-021-comparable number; CL-021 arm-B was +0.029).

Loads the dataset ONCE and loops `--variant all` (each variant builds its own target+net).
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts"))
from value_ranking_train import RankNet, listnet_loss, kendall_tau_b  # noqa: E402

VARIANTS = {
    "V4_listwise":       ("B", "absolute", None),
    "V2_advantage":      ("E", "absolute", None),
    "V1_residual_mse":   ("A", "residual", None),
    "V1r_residual_list": ("B", "residual", None),
    "V5_endgame":        ("B", "absolute", "endgame"),
}
ALPHAS = [0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]


def bucket(seed):
    h = int(hashlib.md5(str(int(seed)).encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


def group_metrics(score, oq):
    best = int(np.argmax(oq)); pick = int(np.argmax(score))
    return float(oq[best] - oq[pick]), int(pick == best), kendall_tau_b(score, oq)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/mnt/c/carc-shared/value_resurrection/dataset_v29_h6400")
    ap.add_argument("--variant", default="all")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--groups-per-batch", type=int, default=32)
    ap.add_argument("--rank-temp", type=float, default=0.25)
    ap.add_argument("--trunk-filters", type=int, default=64)
    ap.add_argument("--trunk-blocks", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", default=str(REPO / "measurement" / "value_resurrection_pilot" / "stage4"))
    args = ap.parse_args()
    dev = torch.device(args.device)
    outroot = Path(args.out); outroot.mkdir(parents=True, exist_ok=True)
    variants = list(VARIANTS) if args.variant == "all" else [args.variant]

    z = np.load(Path(args.dataset) / "rows.npz")
    obs = z["child_obs"]; sca = z["child_scalars"]
    oq = z["oracle_q"].astype(np.float32); leaf = z["leaf_q"].astype(np.float32)
    grp = z["group_id"]; gs = z["game_seed"]; phase = z["phase"].astype(str)
    w = obs.shape[-1]; c_in = obs.shape[1]; n_scalar = sca.shape[1]
    print(f"[load] {len(oq)} rows / {len(np.unique(grp))} groups  obs={obs.shape[1:]} n_scalar={n_scalar}",
          flush=True)

    split = {g: bucket(g) for g in np.unique(gs)}
    groups = {}
    for i in range(len(oq)):
        groups.setdefault(int(grp[i]), []).append(i)
    g_all = {"train": [], "val": [], "test": []}
    for g, idxs in groups.items():
        if len(idxs) < 2:
            continue
        g_all[split[gs[idxs[0]]]].append(np.array(idxs))
    print(f"[split] train/val/test groups = "
          f"{len(g_all['train'])}/{len(g_all['val'])}/{len(g_all['test'])}", flush=True)

    obs_t = torch.from_numpy(obs)   # keep f16 in RAM; cast per batch
    sca_t = torch.from_numpy(sca)

    # v2.9 leaf-alone baseline on TEST (alpha=0 reference, the thing to beat)
    leaf_base = {}
    for slc, filt in (("overall", None), ("endgame", lambda p: p in ("endgame", "pre_endgame"))):
        reg, t1 = [], []
        for gidx in g_all["test"]:
            if filt and phase[gidx[0]] not in ("endgame", "pre_endgame"):
                continue
            r, o1, _ = group_metrics(leaf[gidx], oq[gidx])
            reg.append(r); t1.append(o1)
        leaf_base[slc] = {"regret": float(np.mean(reg)), "top1": float(np.mean(t1)), "n": len(reg)}
    print(f"[leaf-alone TEST] overall regret={leaf_base['overall']['regret']:.4f} "
          f"top1={leaf_base['overall']['top1']:.3f} (n={leaf_base['overall']['n']})", flush=True)

    def train_one(variant):
        arm, target_mode, train_filter = VARIANTS[variant]
        torch.manual_seed(args.seed); np.random.seed(args.seed)
        tgt = (oq - leaf) if target_mode == "residual" else oq
        tgt_t = torch.from_numpy(tgt.astype(np.float32))
        gtr = g_all["train"]
        if train_filter == "endgame":
            gtr = [gx for gx in gtr if phase[gx[0]] in ("endgame", "pre_endgame")]
        net = RankNet(arm, c_in, w, n_scalar, args.trunk_filters, args.trunk_blocks).to(dev)
        opt = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)

        def run(gl, train):
            net.train(train)
            order = list(np.random.permutation(len(gl)) if train else range(len(gl)))
            tot = 0.0; nb = 0
            for b0 in range(0, len(order), args.groups_per_batch):
                batch = [gl[order[k]] for k in order[b0:b0 + args.groups_per_batch]]
                flat = np.concatenate(batch)
                o = obs_t[flat].float().to(dev); s = sca_t[flat].float().to(dev); tt = tgt_t[flat].to(dev)
                with torch.set_grad_enabled(train):
                    pred = net(o, s); loss = 0.0; off = 0
                    for gi in batch:
                        k = len(gi); p = pred[off:off + k]; t = tt[off:off + k]; off += k
                        if arm == "A":
                            loss = loss + F.mse_loss(p, t)
                        elif arm == "E":
                            loss = loss + listnet_loss(p - p.mean(), t - t.mean(), args.rank_temp)
                        else:
                            loss = loss + listnet_loss(p, t, args.rank_temp)
                    loss = loss / len(batch)
                    if train:
                        opt.zero_grad(); loss.backward(); opt.step()
                tot += float(loss.detach()); nb += 1
            return tot / max(nb, 1)

        best_val = math.inf; best_state = None
        for ep in range(args.epochs):
            tl = run(gtr, True); vl = run(g_all["val"], False)
            if vl < best_val:
                best_val = vl; best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
        if best_state:
            net.load_state_dict(best_state)

        net.train(False)
        preds = {}
        with torch.no_grad():
            for gi, gidx in enumerate(g_all["test"]):
                preds[gi] = net(obs_t[gidx].float().to(dev), sca_t[gidx].float().to(dev)).cpu().numpy()
        allp = np.concatenate([preds[gi] for gi in range(len(g_all["test"]))]) if preds else np.array([0.0])
        sd = float(allp.std() + 1e-9)

        def sweep(filt):
            idxs = [gi for gi, gx in enumerate(g_all["test"]) if (filt is None or filt(phase[gx[0]]))]
            if not idxs:
                return None
            na = {"regret": [], "top1": [], "tau": []}
            for gi in idxs:
                gx = g_all["test"][gi]; r, t1, ta = group_metrics(preds[gi], oq[gx])
                na["regret"].append(r); na["top1"].append(t1); na["tau"].append(ta)
            out = {"net_alone": {"regret": float(np.mean(na["regret"])), "top1": float(np.mean(na["top1"])),
                                 "tau": float(np.nanmean(na["tau"])), "n": len(idxs)}, "alpha": {}}
            for a in ALPHAS:
                reg, t1 = [], []
                for gi in idxs:
                    gx = g_all["test"][gi]
                    r, o1, _ = group_metrics(leaf[gx] + a * preds[gi] / sd, oq[gx])
                    reg.append(r); t1.append(o1)
                out["alpha"][f"{a}"] = {"regret": float(np.mean(reg)), "top1": float(np.mean(t1))}
            base = out["alpha"]["0.0"]["regret"]
            ba = min(out["alpha"], key=lambda k: out["alpha"][k]["regret"])
            out["leaf_alone_regret"] = base; out["best_alpha"] = ba
            out["best_alpha_regret"] = out["alpha"][ba]["regret"]
            out["regret_reduction_pct"] = round(100 * (base - out["alpha"][ba]["regret"]) / (base + 1e-12), 2)
            out["beats_leaf"] = bool(ba != "0.0" and out["alpha"][ba]["regret"] < base - 1e-9)
            return out

        summ = {"variant": variant, "arm": arm, "target_mode": target_mode, "best_val_loss": best_val,
                "n_params": int(sum(p.numel() for p in net.parameters())),
                "overall": sweep(None), "endgame": sweep(lambda p: p in ("endgame", "pre_endgame"))}
        od = outroot / variant; od.mkdir(parents=True, exist_ok=True)
        (od / "summary.json").write_text(json.dumps(summ, indent=2))
        torch.save(net.state_dict(), od / "head.pt")
        o = summ["overall"]
        print(f"  [{variant:18s}] net-alone tau={o['net_alone']['tau']:+.3f} top1={o['net_alone']['top1']:.3f} "
              f"| combined a*={o['best_alpha']} regret {o['leaf_alone_regret']:.4f}->{o['best_alpha_regret']:.4f} "
              f"({o['regret_reduction_pct']:+.1f}%) beats_leaf={o['beats_leaf']}", flush=True)
        return summ

    results = {}
    for v in variants:
        t0 = time.time()
        results[v] = train_one(v)
        print(f"    ({v} done in {time.time()-t0:.0f}s)", flush=True)

    ok = [r for r in results.values() if r["overall"]]
    agg = {"leaf_alone_test": leaf_base, "variants": results,
           "verdict": {"any_beats_leaf": any(r["overall"]["beats_leaf"] for r in ok),
                       "best_net_alone_tau": max(r["overall"]["net_alone"]["tau"] for r in ok) if ok else None,
                       "cl021_armB_tau": 0.029}}
    (outroot / "stage5_offline_gate.json").write_text(json.dumps(agg, indent=2))
    print("\n==== STAGE 5 OFFLINE GATE ====")
    print(f"leaf-alone TEST regret={leaf_base['overall']['regret']:.4f}  "
          f"best net-alone tau={agg['verdict']['best_net_alone_tau']:+.3f} (CL-021 arm-B was +0.029)")
    print(f"ANY variant beats leaf (leaf+a*learned < leaf): {agg['verdict']['any_beats_leaf']}")
    print(f"-> {outroot}/stage5_offline_gate.json")


if __name__ == "__main__":
    main()
