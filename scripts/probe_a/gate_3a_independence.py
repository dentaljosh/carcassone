#!/usr/bin/env python3
"""PROBE A — §3A FARM/BAG INDEPENDENCE GATE (the pre-registered cheap kill).

Re-runs the CL-037 farm/bag sibling-regret ablation on the STRUCTURED head, on
the SAME 10,067 h6400_v2.9 sibling sets, h6400-Q ranking target, group-split by
game_seed (n_test=1544 groups). Four input regimes:

  none      : per-component features with farm-connectivity cols (12,13,14)
              ZEROED, and NO bag input.
  farm-only : farm-connectivity cols ON, bag OFF.
  bag-only  : farm-connectivity cols ZEROED, bag ON.
  both      : farm-connectivity cols ON, bag ON.

The STRUCTURED head (identical across regimes except the input mask):

    net(board) = sum_i g_theta(comp_features_i)   [per-component MLP, sum aggregation]
               + bag_head(bag_hist)               [board-level; 0 if bag OFF]
               + cloister_offset(board)           [EXACT board-level v2.9 offset,
                                                    not learned — same as running_diff]

This is the milestone-2.5 drop-in leaf's own learnable part. The cloister offset
is a fixed exact term (bit-identical to build_component_dataset's cloister_slice)
carried through so the score reflects the enriched leaf. The head is a RANKER
(listnet loss to oracle_q, V4_listwise arm) — the CL-037 headline object.

REGRET METRIC (byte-faithful to step1_train.group_metrics + the alpha-sweep):
  score(child) = leaf_q(child) + alpha * net(child) / sd(net over TEST),
  best-alpha selected to MINIMIZE mean per-group regret,
  regret(group) = oracle_q[argmax oq] - oracle_q[argmax score],
  regret_gain(regime) = 100 * (leaf_regret - best_alpha_regret) / leaf_regret.

  Delta_indep = regret_gain(both) - max(regret_gain(farm-only), regret_gain(bag-only)).
  SEPARATED (Probe A proceeds): Delta_indep >= 3pp (~2 sigma at n=1544).
  REDUNDANT (KILL Probe A):     Delta_indep < 3pp (the scalar CL-037 outcome).

leaf_q here = tanh(pretransform/15) — the v2.9 leaf's OWN board value (the exact
ruler CL-037 used: 'leaf' = the heuristic leaf value per board).

  nice -n 19 CUDA_VISIBLE_DEVICES=0 .venv/bin/python -u \
      scripts/probe_a/gate_3a_independence.py \
      --dataset /home/doctor/carc_probe_a/component_ds \
      --out /home/doctor/carc_probe_a/gate_3a --device cuda
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "probe_a"))

FEAT_DIM = 24
N_BAG = 32
# farm-connectivity feature columns (spec §3A: cols 12-14 of the frozen contract).
FARM_COLS = (12, 13, 14)   # C_FARM_FIN_CITIES, C_FARM_POTENTIAL3, C_SELF_GROWTH_P_SUM
ALPHAS = [0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]   # == step1_train.ALPHAS


def bucket(seed):
    """EXACT step1_train.bucket — keeps the TEST split identical program-wide."""
    h = int(hashlib.md5(str(int(seed)).encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


def kendall_tau_b_np(x, y):
    """O(n log n) tau-b (merge-sort inversions) — same value as
    value_ranking_train.kendall_tau_b but non-hanging on large n. (Only used for a
    diagnostic net-alone tau; the GATE metric is regret, not tau.)"""
    x = np.asarray(x, np.float64); y = np.asarray(y, np.float64)
    n = len(x)
    if n < 2:
        return float("nan")
    order = np.lexsort((y, x)); ys = y[order]
    n0 = n * (n - 1) // 2

    def ties(a):
        _, c = np.unique(a, return_counts=True)
        return int(np.sum(c * (c - 1) // 2))
    n1 = ties(x[order]); n2 = ties(ys)

    def merge_count(arr):
        arr = list(arr); inv = 0; width = 1; n_ = len(arr); tmp = [0] * n_
        while width < n_:
            for i in range(0, n_, 2 * width):
                l = i; m = min(i + width, n_); r = min(i + 2 * width, n_)
                a1 = l; a2 = m; k = l
                while a1 < m and a2 < r:
                    if arr[a1] <= arr[a2]:
                        tmp[k] = arr[a1]; a1 += 1
                    else:
                        inv += (m - a1); tmp[k] = arr[a2]; a2 += 1
                    k += 1
                while a1 < m:
                    tmp[k] = arr[a1]; a1 += 1; k += 1
                while a2 < r:
                    tmp[k] = arr[a2]; a2 += 1; k += 1
            arr[:] = tmp[:]; width *= 2
        return inv

    def ties_both(xs, ys_):
        pair = np.stack([xs, ys_], axis=1)
        _, c = np.unique(pair, axis=0, return_counts=True)
        return int(np.sum(c * (c - 1) // 2))
    disc = merge_count(ys)
    conc = n0 - n1 - n2 + ties_both(x[order], ys) - disc
    denom = math.sqrt((n0 - n1) * (n0 - n2))
    return (conc - disc) / denom if denom > 0 else float("nan")


def listnet_loss(pred, target, temp=0.25):
    """== value_ranking_train.listnet_loss (per-group CE of softmaxed scores)."""
    tdist = F.softmax(target / temp, dim=0)
    return -(tdist * F.log_softmax(pred / temp, dim=0)).sum()


def group_metrics(score, oq):
    """== step1_train.group_metrics (regret, top1, tau)."""
    best = int(np.argmax(oq)); pick = int(np.argmax(score))
    return float(oq[best] - oq[pick]), int(pick == best), kendall_tau_b_np(score, oq)


# ---------------------------------------------------------------------------- #
# Structured ranker head: per-component g_theta (sum) + optional bag_head. The
# cloister offset is a FIXED exact per-board term added to the score (not a
# parameter). Matches the milestone-2.5 leaf's learnable structure.
# ---------------------------------------------------------------------------- #
class StructuredRanker(nn.Module):
    def __init__(self, in_dim=FEAT_DIM, hidden=32, use_bag=False, bag_hidden=16):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden)
        self.fc2 = nn.Linear(hidden, 1)
        self.use_bag = use_bag
        if use_bag:
            self.bfc1 = nn.Linear(N_BAG, bag_hidden)
            self.bfc2 = nn.Linear(bag_hidden, 1)

    def per_component(self, x):
        return self.fc2(torch.tanh(self.fc1(x))).squeeze(-1)   # (N_comp,)

    def bag_scalar(self, bag):                                 # (N_boards, 32) -> (N_boards,)
        if not self.use_bag:
            return None
        return self.bfc2(torch.tanh(self.bfc1(bag))).squeeze(-1)


def _seg_sum(per_comp, offsets_t):
    nb = offsets_t.numel() - 1
    seg = torch.repeat_interleave(
        torch.arange(nb, device=per_comp.device),
        (offsets_t[1:] - offsets_t[:-1]),
    )
    out = torch.zeros(nb, device=per_comp.device, dtype=per_comp.dtype)
    out.scatter_add_(0, seg, per_comp)
    return out


def train_regime(regime, data, dev, args):
    """Train the structured ranker under one input regime; return per-TEST-group
    predictions (the net board score) + net-alone tau + best_val."""
    (feat_n, bag_n, offsets, oq, cloi, run, gid, board_split, col_mean, col_std) = data
    use_bag = regime in ("bag-only", "both")
    zero_farm = regime in ("none", "bag-only")

    # ---- apply the regime input mask to the (normalized) per-component feats.
    feat = feat_n.copy()
    if zero_farm:
        feat[:, list(FARM_COLS)] = 0.0
    feat_t = torch.from_numpy(feat).to(dev)
    bag_t = torch.from_numpy(bag_n).to(dev) if use_bag else None
    off_t = torch.from_numpy(offsets).to(dev)
    oq_t = torch.from_numpy(oq).to(dev)

    torch.manual_seed(args.seed); np.random.seed(args.seed)
    net = StructuredRanker(FEAT_DIM, args.hidden, use_bag, args.bag_hidden).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    starts = offsets[:-1]; ends = offsets[1:]
    idx = {k: np.flatnonzero(board_split == k) for k in ("train", "val", "test")}

    def net_scores(board_ids):
        """One forward over the board set's rows -> per-board net score (structural
        sum + bag). Cloister offset is added at the metric stage (exact, fixed)."""
        comp_slices = [np.arange(starts[b], ends[b]) for b in board_ids]
        comp_idx = np.concatenate(comp_slices)
        lens = np.array([len(s) for s in comp_slices], np.int64)
        local_off = np.zeros(len(board_ids) + 1, np.int64)
        local_off[1:] = np.cumsum(lens)
        gc = net.per_component(feat_t[torch.from_numpy(comp_idx).to(dev)])
        agg = _seg_sum(gc, torch.from_numpy(local_off).to(dev))
        if use_bag:
            agg = agg + net.bag_scalar(bag_t[torch.from_numpy(board_ids).to(dev)])
        return agg

    # group index lists (list of arrays of board rows) for train/val/test.
    def groups_of(split):
        gl = {}
        for b in idx[split]:
            gl.setdefault(int(gid[b]), []).append(b)
        return [np.asarray(v) for v in gl.values()]
    g_train = groups_of("train"); g_val = groups_of("val"); g_test = groups_of("test")

    def run(groups, train):
        net.train(train)
        order = np.random.permutation(len(groups)) if train else np.arange(len(groups))
        tot = 0.0; nb = 0
        for b0 in range(0, len(order), args.groups_per_batch):
            batch = [groups[k] for k in order[b0:b0 + args.groups_per_batch]]
            flat = np.concatenate(batch)
            with torch.set_grad_enabled(train):
                sc = net_scores(flat)                    # (n_boards_in_batch,)
                tt = oq_t[torch.from_numpy(flat).to(dev)]
                loss = 0.0; off = 0
                for gi in batch:
                    k = len(gi); p = sc[off:off + k]; t = tt[off:off + k]; off += k
                    loss = loss + listnet_loss(p, t, args.rank_temp)
                loss = loss / len(batch)
                if train:
                    opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss.detach()); nb += 1
        return tot / max(nb, 1)

    best_val = math.inf; best_state = None; stale = 0
    for ep in range(args.epochs):
        te = time.time()
        tl = run(g_train, True); vl = run(g_val, False)
        improved = vl < best_val - 1e-5
        if (ep + 1) % 5 == 0 or improved:
            print(f"    [{regime:9s}] ep{ep+1}/{args.epochs} train={tl:.4f} "
                  f"val={vl:.4f} ({time.time()-te:.0f}s){' *' if improved else ''}", flush=True)
        if improved:
            best_val = vl
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                print(f"    [{regime:9s}] early-stop ep{ep+1}", flush=True); break
    if best_state:
        net.load_state_dict(best_state)

    # ---- TEST predictions (per group). --------------------------------------- #
    net.train(False)
    preds = {}
    with torch.no_grad():
        for gi, gx in enumerate(g_test):
            preds[gi] = net_scores(gx).cpu().numpy()
    return net, g_test, preds, float(best_val)


def sweep_regret(g_test, preds, oq, leaf_q, cloi):
    """CL-037 regret metric + alpha-sweep on the STRUCTURED net.

    net board score = preds + cloister_offset (exact). Combined score under a
    given alpha:  leaf_q + alpha * net/sd. Returns per-group leaf regret,
    best-alpha net regret, regret_gain%, best_alpha, and the per-group deltas
    (leaf_regret - net_regret) for a paired sigma.

    CRITICAL (independence-test correctness): the NET score is the LEARNED head
    output ONLY (`preds`, which differs across regimes by the farm/bag inputs).
    The exact cloister offset and running-diff are already in `leaf_q` (via
    pretransform) and are HELD FIXED across all four regimes — adding them to the
    net score would create a strong regime-invariant signal path that inflates and
    equalizes all four gains, washing out the very farm-vs-bag difference the gate
    measures. So the net score does NOT include `cloi`. This mirrors CL-037, where
    `net` = the learned representation ranker and `leaf` = the v2.9 leaf (which
    already scores cloisters)."""
    allp = np.concatenate([preds[gi] for gi in range(len(g_test))])
    sd = float(allp.std() + 1e-9)

    # leaf-alone (alpha=0) per-group regret baseline.
    leaf_reg = np.array([group_metrics(leaf_q[gx], oq[gx])[0] for gx in g_test])
    base = float(leaf_reg.mean())

    per_alpha = {}
    for a in ALPHAS:
        reg = []
        for gi, gx in enumerate(g_test):
            net_sc = preds[gi]
            r, _, _ = group_metrics(leaf_q[gx] + a * net_sc / sd, oq[gx])
            reg.append(r)
        per_alpha[a] = np.asarray(reg)
    means = {a: float(per_alpha[a].mean()) for a in ALPHAS}
    ba = min(ALPHAS, key=lambda a: means[a])
    best_reg_vec = per_alpha[ba]
    best = float(means[ba])
    gain = 100.0 * (base - best) / (base + 1e-12)
    # net-alone tau diagnostic (score = learned net alone).
    taus = [group_metrics(preds[gi], oq[g_test[gi]])[2]
            for gi in range(len(g_test))]
    return {
        "leaf_regret": base, "best_alpha": float(ba), "best_regret": best,
        "regret_gain_pct": gain, "n_test": len(g_test),
        "leaf_reg_vec": leaf_reg, "best_reg_vec": best_reg_vec,
        "alpha_means": means, "net_alone_tau": float(np.nanmean(taus)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/home/doctor/carc_probe_a/component_ds")
    ap.add_argument("--bag", default=None, help="default <dataset>/bag_sidetable.npz")
    ap.add_argument("--out", default="/home/doctor/carc_probe_a/gate_3a")
    ap.add_argument("--hidden", type=int, default=32)
    ap.add_argument("--bag-hidden", type=int, default=16)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--groups-per-batch", type=int, default=32)
    ap.add_argument("--rank-temp", type=float, default=0.25)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    dev = torch.device(args.device)
    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)

    dsdir = Path(args.dataset)
    z = np.load(dsdir / "component_ds.npz", allow_pickle=False)
    feat = z["feat"].astype(np.float32)
    offsets = z["board_offsets"].astype(np.int64)
    oq = z["oracle_q"].astype(np.float32)
    pretransform = z["pretransform"].astype(np.float32)
    cloi = z["cloister_slice"].astype(np.float32)
    run = z["running_diff"].astype(np.float32)
    gid = z["group_id"].astype(np.int64)
    gs = z["game_seed"].astype(np.int64)
    col_mean = z["col_mean"].astype(np.float32)
    col_std = z["col_std"].astype(np.float32)
    col_std = np.where(col_std < 1e-6, 1.0, col_std).astype(np.float32)
    nb = len(oq)

    bagp = Path(args.bag) if args.bag else dsdir / "bag_sidetable.npz"
    bz = np.load(bagp, allow_pickle=False)
    bag = bz["bag"].astype(np.float32)
    assert bag.shape == (nb, N_BAG), (bag.shape, nb)
    # bag alignment guard (should be enforced at build; re-assert here).
    assert np.allclose(bz["oracle_q"].astype(np.float32), oq, atol=1e-5), "bag<->ds oq mismatch"
    if "filled" in bz.files:
        assert bool(bz["filled"].all()), "bag side-table incomplete (some boards unfilled)"

    # leaf_q = the v2.9 leaf's own board value == tanh(pretransform/15) (the CL-037
    # 'leaf' ruler). Bit-consistent with structured_leaf's tanh(vs/15).
    leaf_q = np.tanh(pretransform / 15.0).astype(np.float32)

    feat_n = ((feat - col_mean) / col_std).astype(np.float32)
    # bag normalization: bag is already in [0,1]; z-score it for conditioning.
    bag_mean = bag.mean(axis=0); bag_std = bag.std(axis=0)
    bag_std = np.where(bag_std < 1e-6, 1.0, bag_std)
    bag_n = ((bag - bag_mean) / bag_std).astype(np.float32)

    split = {int(g): bucket(g) for g in np.unique(gs)}
    board_split = np.array([split[int(s)] for s in gs])
    n_test_groups = len(np.unique(gid[board_split == "test"]))
    print(f"[load] {nb} boards / {len(np.unique(gid))} groups / {len(np.unique(gs))} games "
          f"| TEST groups={n_test_groups}", flush=True)

    data = (feat_n, bag_n, offsets, oq, cloi, run, gid, board_split, col_mean, col_std)

    regimes = ["none", "farm-only", "bag-only", "both"]
    results = {}
    for reg in regimes:
        print(f"\n==== regime: {reg} ====", flush=True)
        net, g_test, preds, best_val = train_regime(reg, data, dev, args)
        m = sweep_regret(g_test, preds, oq, leaf_q, cloi)
        m["best_val_loss"] = best_val
        results[reg] = m
        print(f"  [{reg:9s}] net-alone tau={m['net_alone_tau']:+.3f} | best_alpha={m['best_alpha']} "
              f"regret {m['leaf_regret']:.4f}->{m['best_regret']:.4f} "
              f"(gain {m['regret_gain_pct']:+.1f}%) n_test={m['n_test']}", flush=True)

    # ---- Delta_indep + sigma. ------------------------------------------------ #
    g_none = results["none"]["regret_gain_pct"]
    g_farm = results["farm-only"]["regret_gain_pct"]
    g_bag = results["bag-only"]["regret_gain_pct"]
    g_both = results["both"]["regret_gain_pct"]
    best_single = max(g_farm, g_bag)
    delta_indep = g_both - best_single

    # Measured eval sigma: sigma of the mean per-group regret. Use the 'both'
    # regime's paired per-group deltas (leaf_regret - best_alpha_net_regret) — the
    # regret metric's own dispersion — to size sigma on the REGRET SCALE, then
    # convert to a pp-of-gain scale (relative to the leaf-alone regret) so the 3pp
    # threshold is interpretable. n_test groups.
    both = results["both"]
    n = both["n_test"]
    # sigma of mean regret at leaf-alone (the denominator base), on the regret scale
    leaf_reg_vec = both["leaf_reg_vec"]
    best_reg_vec = both["best_reg_vec"]
    base_reg = float(leaf_reg_vec.mean())
    # sigma of the gain% via the paired delta (leaf - net) per group:
    paired_delta = leaf_reg_vec - best_reg_vec           # per-group regret reduction
    sd_delta = float(paired_delta.std(ddof=1))
    se_mean_delta = sd_delta / math.sqrt(n)              # SE of mean regret reduction
    # gain% = 100 * mean_delta / base_reg ; SE(gain%) = 100 * se_mean_delta / base_reg
    se_gain_pp = 100.0 * se_mean_delta / (base_reg + 1e-12)

    verdict = "SEPARATED" if delta_indep >= 3.0 else "REDUNDANT"
    branch = ("Probe A PROCEEDS to the crater screen (§4)" if verdict == "SEPARATED"
              else "KILL Probe A here (value signal genuinely low-dimensional; "
                   "the scalar was NOT the bottleneck)")

    print("\n" + "=" * 74)
    print("§3A FARM/BAG INDEPENDENCE GATE — VERDICT")
    print("=" * 74)
    print(f"  regret_gain: none={g_none:+.1f}%  farm-only={g_farm:+.1f}%  "
          f"bag-only={g_bag:+.1f}%  both={g_both:+.1f}%")
    print(f"  best single = max(farm,bag) = {best_single:+.1f}%")
    print(f"  Delta_indep = both - best_single = {delta_indep:+.2f}pp")
    print(f"  measured eval sigma (SE of gain%, n={n}) ~= {se_gain_pp:.2f}pp  "
          f"(3pp threshold ~= {3.0/max(se_gain_pp,1e-9):.1f} sigma)")
    print(f"  THRESHOLD: SEPARATED iff Delta_indep >= 3pp")
    print(f"  ==> VERDICT: {verdict}")
    print(f"  ==> BRANCH:  {branch}")

    summary = {
        "n_test_groups": n_test_groups,
        "regimes": {r: {k: (v if not isinstance(v, np.ndarray) else None)
                        for k, v in results[r].items()
                        if k not in ("leaf_reg_vec", "best_reg_vec")}
                    for r in regimes},
        "regret_gain_pct": {"none": g_none, "farm_only": g_farm,
                            "bag_only": g_bag, "both": g_both},
        "best_single_gain_pct": best_single,
        "delta_indep_pp": delta_indep,
        "measured_sigma_gain_pp": se_gain_pp,
        "threshold_pp": 3.0,
        "verdict": verdict,
        "branch": branch,
        "cl037_scalar_reference": {"farm_only": -17.1, "bag_only": -19.7,
                                   "both": -20.5, "delta_indep_pp": 0.8,
                                   "note": "CL-037 scalar/dense: REDUNDANT"},
    }
    (outd / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    np.savez(outd / "per_group_regret.npz",
             **{f"{r}_leaf_reg": results[r]["leaf_reg_vec"] for r in regimes},
             **{f"{r}_best_reg": results[r]["best_reg_vec"] for r in regimes})
    print(f"\n-> {outd}/summary.json  (+ per_group_regret.npz)")


if __name__ == "__main__":
    main()
