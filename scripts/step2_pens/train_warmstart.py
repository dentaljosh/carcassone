#!/usr/bin/env python3
"""Step-2 "PeNS" SCALAR value/ranking-head warmstart trainer (MEASUREMENT ONLY).

A PURE-SCALAR MLP (no conv) over the ~89 PeNS scalars built by build_dataset.py,
warmstarted on the 10,067 h6400_v2.9 sibling sets' oracle_q via per-group ListNet
(temp 0.25, value_ranking_train.listnet_loss), val-loss early-stop (patience 6),
group-split by game_seed bucket (the EXACT step1_train.bucket() md5 hash so the
TEST set matches Step-1 / CL-034).

After best-model selection it runs the alpha-sweep EXACTLY like
scripts/feature_planes_gate/step1_train.sweep(): net-alone Kendall-tau, the
α-sweep combined = leaf_q + alpha*pred/sd over ALPHAS=[0,0.05,0.1,0.25,0.5,1,2],
per-group regret = oracle_q[best]-oracle_q[pick], best_alpha, leaf-alone vs best
regret, regret_reduction_pct, beats_leaf — overall + endgame slices.

The OFFLINE GATE (run separately by the operator) asks: does leaf_q + alpha*net
beat leaf-alone (regret reduction)? Target reproduces Step-1's ~-20% and ideally
approaches CL-034's -41% (more scalars, same scalar-model family).

Saves <out>/warmstart.pt (state_dict, D, feature-name list, normalization, hidden
dims) + <out>/summary.json (sweep results).

  python -u scripts/step2_pens/train_warmstart.py \
      --dataset /home/doctor/carc_step2_pens/dataset --epochs 60 --device cuda \
      --out /home/doctor/carc_step2_pens/warmstart
"""
from __future__ import annotations
import argparse, json, math, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts"))
from value_ranking_train import listnet_loss, kendall_tau_b  # noqa: E402

ALPHAS = [0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]


def bucket(seed):
    # EXACT copy of step1_train.bucket — keeps the TEST set identical to Step-1.
    import hashlib
    h = int(hashlib.md5(str(int(seed)).encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


def group_metrics(score, oq):
    best = int(np.argmax(oq)); pick = int(np.argmax(score))
    return float(oq[best] - oq[pick]), int(pick == best), kendall_tau_b(score, oq)


# ---------------------------------------------------------------------------- #
# Pure-scalar value/ranking head: MLP with residual blocks, tanh output.
# ---------------------------------------------------------------------------- #
class _MLPBlock(nn.Module):
    def __init__(self, h):
        super().__init__()
        self.fc1 = nn.Linear(h, h)
        self.bn1 = nn.BatchNorm1d(h)
        self.fc2 = nn.Linear(h, h)
        self.bn2 = nn.BatchNorm1d(h)

    def forward(self, x):
        r = x
        x = torch.relu(self.bn1(self.fc1(x)))
        x = self.bn2(self.fc2(x))
        return torch.relu(x + r)


class ScalarMLP(nn.Module):
    """D-scalar -> hidden -> [blocks residual MLP] -> 1, tanh output."""
    def __init__(self, d, hidden=256, blocks=2):
        super().__init__()
        self.stem = nn.Sequential(nn.Linear(d, hidden), nn.BatchNorm1d(hidden), nn.ReLU(inplace=True))
        self.blocks = nn.Sequential(*[_MLPBlock(hidden) for _ in range(blocks)])
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        x = self.stem(x)
        x = self.blocks(x)
        return torch.tanh(self.head(x)).squeeze(-1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/home/doctor/carc_step2_pens/dataset")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--groups-per-batch", type=int, default=32)
    ap.add_argument("--rank-temp", type=float, default=0.25)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--blocks", type=int, default=2)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", default="/home/doctor/carc_step2_pens/warmstart")
    args = ap.parse_args()
    dev = torch.device(args.device)
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)

    dsdir = Path(args.dataset)
    meta = json.loads((dsdir / "meta.json").read_text())
    z = np.load(dsdir / "aux_step2.npz", allow_pickle=False)
    sca = np.asarray(z["child_scalars"]).astype(np.float32)
    oq = z["oracle_q"].astype(np.float32)
    leaf = z["leaf_q"].astype(np.float32)
    grp = z["group_id"]; gs = z["game_seed"]; phase = z["phase"].astype(str)
    feat_names = [str(x) for x in z["feat_names"]]
    D = sca.shape[1]
    col_mean = z["col_mean"].astype(np.float32) if "col_mean" in z.files else sca.mean(0)
    col_std = z["col_std"].astype(np.float32) if "col_std" in z.files else (sca.std(0) + 1e-6)
    col_std = np.where(col_std < 1e-6, 1.0, col_std).astype(np.float32)
    print(f"[load] {len(oq)} rows / {len(np.unique(grp))} groups / "
          f"{len(np.unique(gs))} games  D={D}", flush=True)
    assert D == meta.get("D", D), f"D mismatch {D} vs meta {meta.get('D')}"

    # normalize columns (z-score) so the MLP is well-conditioned.
    sca_n = (sca - col_mean) / col_std
    sca_t = torch.from_numpy(sca_n.astype(np.float32))

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

    oq_t = torch.from_numpy(oq.astype(np.float32))

    # leaf-alone baseline on TEST (alpha=0 reference) -----------------------
    leaf_base = {}
    for slc, isend in (("overall", False), ("endgame", True)):
        reg, t1 = [], []
        for gidx in g_all["test"]:
            if isend and phase[gidx[0]] not in ("endgame", "pre_endgame"):
                continue
            r, o1, _ = group_metrics(leaf[gidx], oq[gidx])
            reg.append(r); t1.append(o1)
        leaf_base[slc] = {"regret": float(np.mean(reg)) if reg else None,
                          "top1": float(np.mean(t1)) if t1 else None, "n": len(reg)}
    if leaf_base["overall"]["regret"] is not None:
        print(f"[leaf-alone TEST] overall regret={leaf_base['overall']['regret']:.4f} "
              f"top1={leaf_base['overall']['top1']:.3f} (n={leaf_base['overall']['n']})", flush=True)
    else:
        print("[leaf-alone TEST] overall: 0 test groups (smoke/too-small split)", flush=True)

    net = ScalarMLP(D, hidden=args.hidden, blocks=args.blocks).to(dev)
    n_params = sum(p.numel() for p in net.parameters())
    opt = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    print(f"[model] ScalarMLP D={D} hidden={args.hidden} blocks={args.blocks} "
          f"params={n_params/1e3:.0f}k on {dev}", flush=True)

    def run(gl, train):
        net.train(train)
        order = list(np.random.permutation(len(gl)) if train else range(len(gl)))
        tot = 0.0; nb = 0
        for b0 in range(0, len(order), args.groups_per_batch):
            batch = [gl[order[k]] for k in order[b0:b0 + args.groups_per_batch]]
            flat = np.concatenate(batch)
            s = sca_t[flat].to(dev); tt = oq_t[flat].to(dev)
            with torch.set_grad_enabled(train):
                pred = net(s)
                loss = 0.0; off = 0
                for gi in batch:
                    k = len(gi); p = pred[off:off + k]; t = tt[off:off + k]; off += k
                    loss = loss + listnet_loss(p, t, args.rank_temp)
                loss = loss / len(batch)
                if train:
                    opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss.detach()); nb += 1
        return tot / max(nb, 1)

    best_val = math.inf; best_state = None; stale = 0; val_trend = []
    for ep in range(args.epochs):
        te = time.time(); tl = run(g_all["train"], True); vl = run(g_all["val"], False)
        val_trend.append(round(vl, 4))
        improved = vl < best_val - 1e-5
        print(f"  ep{ep+1}/{args.epochs} train={tl:.4f} val={vl:.4f} "
              f"({time.time()-te:.0f}s){' *' if improved else ''}", flush=True)
        if improved:
            best_val = vl
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                print(f"  early-stop ep{ep+1} (no val gain in {args.patience} epochs)", flush=True)
                break
    if best_state:
        net.load_state_dict(best_state)

    # test predictions -------------------------------------------------------
    net.train(False)
    preds = {}
    with torch.no_grad():
        for gi, gidx in enumerate(g_all["test"]):
            preds[gi] = net(sca_t[gidx].to(dev)).cpu().numpy()
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
        out = {"net_alone": {"regret": float(np.mean(na["regret"])),
                             "top1": float(np.mean(na["top1"])),
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

    overall = sweep(None)
    endgame = sweep(lambda p: p in ("endgame", "pre_endgame"))

    summ = {
        "dataset": str(dsdir), "D": int(D), "n_params": int(n_params),
        "hidden": args.hidden, "blocks": args.blocks, "rank_temp": args.rank_temp,
        "best_val_loss": best_val, "val_loss_trend": val_trend,
        "leaf_alone_test": leaf_base,
        "overall": overall, "endgame": endgame,
        "v29_hash": meta.get("v29_hash"),
        "n_cl034": meta.get("n_cl034"), "n_bag": meta.get("n_bag"),
        "n_deck_odds": meta.get("n_deck_odds"),
    }
    (outd / "summary.json").write_text(json.dumps(summ, indent=2))

    torch.save({
        "state_dict": net.state_dict(),
        "D": int(D), "feat_names": feat_names,
        "col_mean": col_mean, "col_std": col_std,
        "hidden": args.hidden, "blocks": args.blocks,
        "arch": "ScalarMLP", "rank_temp": args.rank_temp,
        "v29_hash": meta.get("v29_hash"),
    }, outd / "warmstart.pt")

    print("\n==== STEP-2 PeNS WARMSTART (D={}) ====".format(D))
    if overall is not None:
        o = overall
        print(f"net-alone tau={o['net_alone']['tau']:+.3f} top1={o['net_alone']['top1']:.3f} | "
              f"combined a*={o['best_alpha']} regret {o['leaf_alone_regret']:.4f}->"
              f"{o['best_alpha_regret']:.4f} ({o['regret_reduction_pct']:+.1f}%) "
              f"beats_leaf={o['beats_leaf']}", flush=True)
    if endgame is not None:
        e = endgame
        print(f"[endgame] a*={e['best_alpha']} regret {e['leaf_alone_regret']:.4f}->"
              f"{e['best_alpha_regret']:.4f} ({e['regret_reduction_pct']:+.1f}%) "
              f"beats_leaf={e['beats_leaf']}", flush=True)
    print(f"-> {outd}/summary.json  +  {outd}/warmstart.pt", flush=True)


if __name__ == "__main__":
    main()
