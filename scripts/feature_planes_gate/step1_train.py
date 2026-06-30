#!/usr/bin/env python3
"""Step-1 gate trainer — train_eval.py logic over the STREAMED dataset.

Identical variants / alpha-sweep / metrics to
scripts/rod_v2/value_resurrection/train_eval.py (reuses its RankNet, listnet_loss,
kendall_tau_b), but loads the obs planes via np.memmap from child_obs.f16 (NEVER
materializing the ~30 GB array in RAM — gathers each batch's rows from disk) and
the small arrays from aux.npz. This is the read side of the streaming dump that
replaced the accumulate+concatenate model that OOM'd the VM.

  score(child) = leaf_q(child) + alpha * learned(child),  alpha=0 == leaf-alone.
Gate: does any variant make leaf+alpha*net beat leaf alone (best_alpha>0, regret
down, no ordinary regression)? net-alone Kendall-tau vs h6400 reported too
(CL-021 arm-B was +0.029; CL-033 best net-alone tau ~0.105 / best_alpha=0).
"""
from __future__ import annotations
import argparse, json, math, sys, time
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
    import hashlib
    h = int(hashlib.md5(str(int(seed)).encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


def group_metrics(score, oq):
    best = int(np.argmax(oq)); pick = int(np.argmax(score))
    return float(oq[best] - oq[pick]), int(pick == best), kendall_tau_b(score, oq)


def _avail_gb():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) / 1048576
    except Exception:
        pass
    return 0.0


def load_streamed(dsdir, in_ram=False):
    meta = json.loads((Path(dsdir) / "meta.json").read_text())
    n, c, w = meta["n_rows"], meta["n_chan"], meta["W"]
    p = Path(dsdir) / meta.get("obs_file", "child_obs.f16")
    need = n * c * w * w * 2 / 1e9
    avail = _avail_gb()
    # in-RAM only if it FITS with a +6GB safety margin (else the 42GB WSL cap OOMs,
    # as it did twice during the dump). Otherwise memmap — which is page-cached
    # after epoch 1 anyway, so gather is already RAM-speed.
    if in_ram and avail > need + 6.0:
        obs = np.fromfile(p, dtype=np.float16).reshape(n, c, w, w)
        print(f"[load] obs IN-RAM {need:.1f}GB (avail {avail:.0f}GB)", flush=True)
    else:
        if in_ram:
            print(f"[load] obs MEMMAP — in-RAM UNSAFE: need {need:.1f}GB, only "
                  f"{avail:.0f}GB avail (+6GB guard) → memmap (page-cached)", flush=True)
        obs = np.memmap(p, dtype=np.float16, mode="r", shape=(n, c, w, w))
    aux = np.load(Path(dsdir) / "aux.npz", allow_pickle=False)
    return meta, obs, aux


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
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
    ap.add_argument("--out", required=True)
    ap.add_argument("--in-ram", action="store_true",
                    help="load obs fully into RAM (faster gather) if it fits with a "
                         "+6GB margin; else falls back to memmap. Safe for none-sized "
                         "datasets; the 32GB 'both' set stays memmap on the 42GB box.")
    ap.add_argument("--patience", type=int, default=6,
                    help="early-stop a variant if val loss hasn't improved in this "
                         "many epochs (the real speedup — caps wasted epochs).")
    ap.add_argument("--shuffle-extra", action="store_true",
                    help="NEGATIVE CONTROL: permute ONLY the added farm planes (last "
                         "n_farm_planes obs-channels) and bag scalars (last n_bag_scalars "
                         "scalar cols) across rows by one global permutation, leaving the "
                         "base 78ch+12scalars aligned to their true row. A real farm/bag "
                         "signal MUST collapse back to the 'none' baseline here; if the "
                         "regret reduction survives, the 'both' win is spurious.")
    ap.add_argument("--shuffle-seed", type=int, default=12345,
                    help="seed for the --shuffle-extra global row permutation.")
    ap.add_argument("--drop-farm", action="store_true",
                    help="ABLATION: zero the farm planes (last n_farm_planes obs-channels). "
                         "Turns a 'both' dataset into the 'bag-only' mode without a re-dump.")
    ap.add_argument("--drop-bag", action="store_true",
                    help="ABLATION: zero the bag scalars (last n_bag_scalars scalar cols). "
                         "Turns a 'both' dataset into the 'farm-only' mode without a re-dump.")
    args = ap.parse_args()
    dev = torch.device(args.device)
    outroot = Path(args.out); outroot.mkdir(parents=True, exist_ok=True)
    variants = list(VARIANTS) if args.variant == "all" else args.variant.split(",")

    meta, obs, aux = load_streamed(args.dataset, in_ram=args.in_ram)
    sca = np.asarray(aux["child_scalars"])
    oq = aux["oracle_q"].astype(np.float32); leaf = aux["leaf_q"].astype(np.float32)
    grp = aux["group_id"]; gs = aux["game_seed"]; phase = aux["phase"].astype(str)
    w = meta["W"]; c_in = meta["n_chan"]; n_scalar = sca.shape[1]
    print(f"[load] {len(oq)} rows / {len(np.unique(grp))} groups  obs=({c_in},{w},{w}) "
          f"n_scalar={n_scalar}  (memmap, low-RAM)", flush=True)

    # --- negative control / ablation: perturb the ADDED features (farm planes are the
    #     LAST n_farm_planes obs-channels; bag scalars are the LAST n_bag_scalars scalar
    #     cols). Reuses a 'both' dataset for the shuffled / farm-only / bag-only modes
    #     with NO re-dump. shuffle-extra = decorrelate off the true row (spuriousness
    #     check); drop-farm/drop-bag = zero a block (attribution). ---
    nf = int(meta.get("n_farm_planes", 0)); nb = int(meta.get("n_bag_scalars", 0))
    farm_shuf = None        # permuted farm planes (negative control), gathered per-row
    zero_farm = args.drop_farm and nf > 0   # ablation: blank the farm planes at gather
    if args.shuffle_extra:
        n = len(oq)
        if nf == 0 and nb == 0:
            print("[shuffle-extra] WARNING: no farm planes or bag scalars to shuffle "
                  "— control is a no-op.", flush=True)
        perm = np.random.RandomState(args.shuffle_seed).permutation(n)
        if nb > 0:  # bag scalars are the LAST nb scalar columns
            sca = sca.copy(); sca[:, n_scalar - nb:] = sca[perm, n_scalar - nb:]
        if nf > 0:  # farm planes are the LAST nf obs-channels — pull into RAM once (~1.2GB)
            t = time.time()
            farm_shuf = np.ascontiguousarray(obs[:, c_in - nf:c_in, :, :])[perm]  # f16
            print(f"[shuffle-extra] permuted {nf} farm planes + {nb} bag scalars across "
                  f"{n} rows (seed={args.shuffle_seed}); farm extract {time.time()-t:.0f}s "
                  f"({farm_shuf.nbytes/1e9:.2f}GB RAM)", flush=True)
    if args.drop_bag and nb > 0:  # ablation -> farm-only
        sca = sca.copy(); sca[:, n_scalar - nb:] = 0.0
        print(f"[drop-bag] zeroed {nb} bag scalars (mode -> farm-only)", flush=True)
    if zero_farm:                 # ablation -> bag-only
        print(f"[drop-farm] zeroing {nf} farm planes at gather (mode -> bag-only)", flush=True)

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

    sca_t = torch.from_numpy(sca.astype(np.float16))

    def gather_obs(idx):
        # gather these rows from the memmap (disk) -> small contiguous f32 tensor
        o = np.ascontiguousarray(obs[idx]).astype(np.float32)
        if farm_shuf is not None:  # negative control: overwrite farm planes w/ permuted ones
            nfp = farm_shuf.shape[1]
            o[:, c_in - nfp:c_in, :, :] = farm_shuf[idx].astype(np.float32)
        elif zero_farm:            # ablation: blank farm planes (-> bag-only)
            o[:, c_in - nf:c_in, :, :] = 0.0
        return torch.from_numpy(o)

    # leaf-alone baseline on TEST (alpha=0 reference)
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
                o = gather_obs(flat).to(dev); s = sca_t[flat].float().to(dev); tt = tgt_t[flat].to(dev)
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

        best_val = math.inf; best_state = None; stale = 0
        for ep in range(args.epochs):
            te = time.time(); tl = run(gtr, True); vl = run(g_all["val"], False)
            improved = vl < best_val - 1e-5
            print(f"    [{variant}] ep{ep+1}/{args.epochs} train={tl:.4f} val={vl:.4f} "
                  f"({time.time()-te:.0f}s){' *' if improved else ''}", flush=True)
            if improved:
                best_val = vl; best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}; stale = 0
            else:
                stale += 1
                if stale >= args.patience:
                    print(f"    [{variant}] early-stop ep{ep+1} (no val gain in {args.patience} epochs)", flush=True)
                    break
        if best_state:
            net.load_state_dict(best_state)

        net.train(False)
        preds = {}
        with torch.no_grad():
            for gi, gidx in enumerate(g_all["test"]):
                preds[gi] = net(gather_obs(gidx).to(dev), sca_t[gidx].float().to(dev)).cpu().numpy()
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
        o = summ["overall"]
        if o is None:
            print(f"  [{variant:18s}] no TEST groups (smoke/too-small split)", flush=True)
            return summ
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
    agg = {"dataset": args.dataset, "mode": meta.get("mode"),
           "leaf_alone_test": leaf_base, "variants": results,
           "verdict": {"any_beats_leaf": any(r["overall"]["beats_leaf"] for r in ok),
                       "best_net_alone_tau": max(r["overall"]["net_alone"]["tau"] for r in ok) if ok else None,
                       "cl021_armB_tau": 0.029}}
    (outroot / "stage5_offline_gate.json").write_text(json.dumps(agg, indent=2))
    print("\n==== STEP-1 GATE (mode={}) ====".format(meta.get("mode")))
    print(f"leaf-alone TEST regret={leaf_base['overall']['regret']:.4f}  "
          f"best net-alone tau={agg['verdict']['best_net_alone_tau']:+.3f}")
    print(f"ANY variant beats leaf (leaf+a*net < leaf): {agg['verdict']['any_beats_leaf']}")
    print(f"-> {outroot}/stage5_offline_gate.json")


if __name__ == "__main__":
    main()
