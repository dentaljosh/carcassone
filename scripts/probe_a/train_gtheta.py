#!/usr/bin/env python3
"""PROBE A — MILESTONE 2 two-stage trainer for the per-component head g_theta.

Targets the MECHANISM (spec §5): g_theta must be a MAGNITUDE-CONSISTENT SUBSTRATE,
not just a good ranker. So the loss penalizes MAGNITUDE error (MSE), never pure
rank. g_theta is a tiny per-component MLP (FEAT_DIM -> H -> 1); v_leaf aggregates
by SUM (matched to virtual_score_v2's own aggregation) plus the exact additive
running-score offset:

    v_leaf(board) = tanh( (running_diff(board) + sum_i g_theta(comp_i)) / 15 )

The head shape (FEAT_DIM -> H -> 1, tanh hidden) is IDENTICAL to
structured_leaf.GThetaStub so the trained torch weights export 1:1 to the numpy
leaf-hot-path head (verified separately by export_gtheta.py).

STAGE (i) — structure-first supervision.
  Loss_i = MSE( sum_i g(comp_i) , y_struct )              # aggregate reproduces
                                                            #   the (capped) leaf
         + lambda_c * MSE( g(comp_i) , y_comp_i )         # per-component matches
                                                            #   the heuristic's own
                                                            #   per-component term
  y_struct = pretransform - running_diff (the learnable structural part; running
  score is the exact offset). y_comp_i is the per-component heuristic contribution
  (base+closure real rows / cloister+meeple econ row); its SUM == the UNCAPPED
  y_struct (see build_component_dataset). The cap + cloister residuals are the
  reported un-closable gaps.

STAGE (ii) — aggregate fine-tune vs h6400 root/search-Q, per-board.
  Loss_ii = MSE( v_leaf(board) , oracle_q )               # magnitude, NOT rank
          + lambda_reg * mean_i MSE( g(comp_i) , g_i^(0) )# hold stage-(i) structure
  Aggregation is FIXED to sum; only g_theta learns. lambda_reg keeps (i)'s
  per-component magnitudes from collapsing. Reports whether (ii) improves aggregate
  agreement with Q beyond (i), or is stuck at the v2.9 ceiling (spec open-Q3).

Group split: the FROZEN bucket() md5 hash on game_seed (== step1_train / CL-034 /
Step-2), so TEST is bit-identical to the rest of the program.

  nice -n 19 CUDA_VISIBLE_DEVICES=0 .venv/bin/python -u scripts/probe_a/train_gtheta.py \
      --dataset /home/doctor/carc_probe_a/component_ds \
      --out /home/doctor/carc_probe_a/gtheta --device cuda
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

REPO = Path("/home/doctor/projects/carcassone")

FEAT_DIM = 24


def fast_kendall_tau_b(x, y):
    """O(n log n) Kendall tau-b (merge-sort inversion count) — the pure-Python
    value_ranking_train.kendall_tau_b is O(n^2) and hangs on the 48K-point TEST
    set. Handles ties in both x and y (tau-b denominator). Numpy-vectorized sort."""
    x = np.asarray(x, np.float64); y = np.asarray(y, np.float64)
    n = len(x)
    if n < 2:
        return float("nan")
    # sort by x, then y; count discordant pairs via inversions in y.
    order = np.lexsort((y, x))
    xs = x[order]; ys = y[order]

    # total pairs
    n0 = n * (n - 1) // 2

    def ties(a):
        # sum over groups of equal a of g*(g-1)/2
        _, counts = np.unique(a, return_counts=True)
        return int(np.sum(counts * (counts - 1) // 2))

    n1 = ties(xs)          # pairs tied on x
    n2 = ties(ys)          # pairs tied on y

    # count discordant pairs among x-untied pairs: inversions of ys within blocks
    # where xs strictly increases. We count total inversions of ys after sorting
    # by (x asc, y asc); pairs tied on x are already ordered by y (no inversion),
    # so all inversions are between x-distinct pairs -> discordant count.
    def merge_count(arr):
        arr = list(arr)
        inv = 0
        width = 1
        n_ = len(arr)
        tmp = [0] * n_
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
            arr[:] = tmp[:]
            width *= 2
        return inv

    discordant = merge_count(ys)
    concordant = n0 - n1 - n2 + ties_both(xs, ys) - discordant
    # tau-b = (C - D) / sqrt((n0-n1)*(n0-n2))
    denom = math.sqrt((n0 - n1) * (n0 - n2))
    return (concordant - discordant) / denom if denom > 0 else float("nan")


def ties_both(xs, ys):
    """pairs tied on BOTH x and y (needed for exact concordant count)."""
    pair = np.stack([xs, ys], axis=1)
    _, counts = np.unique(pair, axis=0, return_counts=True)
    return int(np.sum(counts * (counts - 1) // 2))


def bucket(seed):
    # EXACT copy of step1_train.bucket — keeps the TEST set identical program-wide.
    h = int(hashlib.md5(str(int(seed)).encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


# ---------------------------------------------------------------------------- #
# g_theta: per-component MLP  (FEAT_DIM -> H -> 1), tanh hidden. Same shape as
# structured_leaf.GThetaStub so weights export 1:1 to the numpy leaf head.
# NO batchnorm / no residual: the numpy head is a plain 2-layer MLP.
# ---------------------------------------------------------------------------- #
class GTheta(nn.Module):
    def __init__(self, in_dim=FEAT_DIM, hidden=32):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, x):                      # x: (N_comp, FEAT_DIM)
        h = torch.tanh(self.fc1(x))
        return self.fc2(h).squeeze(-1)         # (N_comp,)


N_BAG = 32


class BagHead(nn.Module):
    """Board-level bag/deck-composition head (32 -> H_bag -> 1). Its scalar is
    ADDED to the aggregate (pure sum), so the leaf stays a drop-in. Milestone 2.5:
    the axis CL-037 showed EXCEEDS the v2.9 ceiling."""
    def __init__(self, in_dim=N_BAG, hidden=16):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, bag):                    # bag: (N_boards, 32)
        return self.fc2(torch.tanh(self.fc1(bag))).squeeze(-1)   # (N_boards,)


def _board_sum(per_comp, offsets_t):
    """Segment-sum per_comp (N_comp,) into per-board sums (N_boards,) using a
    ragged offsets tensor (N_boards+1,)."""
    nb = offsets_t.numel() - 1
    seg = torch.repeat_interleave(
        torch.arange(nb, device=per_comp.device),
        (offsets_t[1:] - offsets_t[:-1]),
    )
    out = torch.zeros(nb, device=per_comp.device, dtype=per_comp.dtype)
    out.scatter_add_(0, seg, per_comp)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/home/doctor/carc_probe_a/component_ds")
    ap.add_argument("--out", default="/home/doctor/carc_probe_a/gtheta")
    ap.add_argument("--hidden", type=int, default=32)   # MUST match GThetaStub head
    ap.add_argument("--epochs-i", type=int, default=120)
    ap.add_argument("--epochs-ii", type=int, default=80)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-5)
    ap.add_argument("--boards-per-batch", type=int, default=512)
    ap.add_argument("--lambda-comp", type=float, default=1.0)   # (i) per-comp MSE weight
    ap.add_argument("--lambda-reg", type=float, default=0.3)    # (ii) structure hold
    ap.add_argument("--patience", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    # MILESTONE 2.5: bag/deck-composition side-input + exact cloister offset.
    ap.add_argument("--bag", action="store_true",
                    help="add the 32-dim bag side-input (stage-ii) + pull cloister "
                         "out as an EXACT board-level offset. The CL-037 'exceed "
                         "the ceiling' diagnostic (spec open-Q3).")
    ap.add_argument("--bag-file", default=None, help="default <dataset>/bag_sidetable.npz")
    ap.add_argument("--bag-hidden", type=int, default=16)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    dev = torch.device(args.device)
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)

    dsdir = Path(args.dataset)
    meta = json.loads((dsdir / "meta.json").read_text())
    z = np.load(dsdir / "component_ds.npz", allow_pickle=False)
    feat = z["feat"].astype(np.float32)                 # (Ncomp, 24)
    y_comp = z["y_comp"].astype(np.float32)             # (Ncomp,)
    offsets = z["board_offsets"].astype(np.int64)       # (Nboards+1,)
    y_struct = z["y_struct"].astype(np.float32)         # (Nboards,)
    running = z["running_diff"].astype(np.float32)      # (Nboards,)
    oracle_q = z["oracle_q"].astype(np.float32)         # (Nboards,)
    gid = z["group_id"].astype(np.int64)                # (Nboards,)
    gs = z["game_seed"].astype(np.int64)                # (Nboards,)
    phase = z["phase"].astype(str)                      # (Nboards,)
    col_mean = z["col_mean"].astype(np.float32)
    col_std = z["col_std"].astype(np.float32)
    col_std = np.where(col_std < 1e-6, 1.0, col_std).astype(np.float32)
    cloister = z["cloister_slice"].astype(np.float32)   # (Nboards,) exact cloister value
    nb = len(y_struct)
    print(f"[load] {nb} boards / {feat.shape[0]} component rows / "
          f"{len(np.unique(gs))} games  FEAT_DIM={feat.shape[1]}", flush=True)

    # ---- MILESTONE 2.5: bag side-input + EXACT cloister offset. ------------- #
    # cloister is pulled OUT of the learnable aggregate (its feature columns are
    # reserved-0, so g_theta structurally CANNOT learn it) and added as an EXACT
    # board-level offset, same as running_diff. The leaf then becomes:
    #   v_leaf = tanh((running + cloister + sum g(comp) + bag_head(bag)) / 15)
    # and the STRUCTURAL target the sum must reproduce drops the cloister slice.
    use_bag = bool(args.bag)
    if use_bag:
        bagf = Path(args.bag_file) if args.bag_file else dsdir / "bag_sidetable.npz"
        bz = np.load(bagf, allow_pickle=False)
        bag = bz["bag"].astype(np.float32)
        assert bag.shape == (nb, N_BAG), (bag.shape, nb)
        assert np.allclose(bz["oracle_q"].astype(np.float32), oracle_q, atol=1e-5), \
            "bag side-table <-> component_ds oracle_q mismatch (misaligned)"
        if "filled" in bz.files:
            assert bool(bz["filled"].all()), "bag side-table incomplete"
        bag_mean = bag.mean(axis=0); bag_std = bag.std(axis=0)
        bag_std = np.where(bag_std < 1e-6, 1.0, bag_std).astype(np.float32)
        bag_n = ((bag - bag_mean) / bag_std).astype(np.float32)
        # exact offset that leaves the leaf: running + cloister. y_struct becomes
        # the part the SUM must reproduce, minus the cloister slice.
        offset_exact = running + cloister                 # (Nboards,)
        y_struct = y_struct - cloister                    # learnable structural part
        print(f"[bag] bag side-input ON (H_bag={args.bag_hidden}); cloister pulled "
              f"out as EXACT offset (abs_mean {np.abs(cloister).mean():.3f}). "
              f"y_struct now excludes cloister.", flush=True)
    else:
        bag_n = None
        offset_exact = running
        bag_mean = bag_std = None

    # normalize features (z-score) — the head is well-conditioned; the export step
    # folds the normalization into the numpy head so the leaf feeds RAW features.
    feat_n = (feat - col_mean) / col_std

    # ---- board split by frozen bucket() on game_seed. ---------------------- #
    split = {int(g): bucket(g) for g in np.unique(gs)}
    board_split = np.array([split[int(s)] for s in gs])
    idx = {k: np.flatnonzero(board_split == k) for k in ("train", "val", "test")}
    print(f"[split] boards train/val/test = "
          f"{len(idx['train'])}/{len(idx['val'])}/{len(idx['test'])}", flush=True)

    # When bag mode pulls cloister out, also drop the cloister slice from the
    # ECON-ROW per-component target (its features can't represent it). The cloister
    # slice sits on the LAST component row of each board (the econ pseudo-row).
    if use_bag:
        econ_rows = (offsets[1:] - 1).astype(np.int64)     # last row index per board
        y_comp = y_comp.copy()
        y_comp[econ_rows] = y_comp[econ_rows] - cloister    # remove cloister from econ target

    feat_t = torch.from_numpy(feat_n).to(dev)
    ycomp_t = torch.from_numpy(y_comp).to(dev)
    ystruct_t = torch.from_numpy(y_struct).to(dev)
    run_t = torch.from_numpy(offset_exact).to(dev)          # running (+cloister if bag)
    oq_t = torch.from_numpy(oracle_q).to(dev)
    off_t = torch.from_numpy(offsets).to(dev)
    bag_t = torch.from_numpy(bag_n).to(dev) if use_bag else None
    bag_head = BagHead(N_BAG, args.bag_hidden).to(dev) if use_bag else None

    # per-board component slices as (start,end) for gathering minibatches.
    starts = offsets[:-1]; ends = offsets[1:]

    def batch_iter(board_ids, bs, shuffle):
        order = np.random.permutation(len(board_ids)) if shuffle else np.arange(len(board_ids))
        for b0 in range(0, len(board_ids), bs):
            bids = board_ids[order[b0:b0 + bs]]
            # gather the component rows for these boards; build a local offsets.
            comp_slices = [np.arange(starts[b], ends[b]) for b in bids]
            comp_idx = np.concatenate(comp_slices)
            lens = np.array([len(s) for s in comp_slices], np.int64)
            local_off = np.zeros(len(bids) + 1, np.int64)
            local_off[1:] = np.cumsum(lens)
            yield (torch.from_numpy(comp_idx).to(dev),
                   torch.from_numpy(local_off).to(dev),
                   torch.from_numpy(bids).to(dev))

    net = GTheta(FEAT_DIM, args.hidden).to(dev)
    n_params = sum(p.numel() for p in net.parameters())
    print(f"[model] GTheta {FEAT_DIM}->{args.hidden}->1  params={n_params}", flush=True)

    # ============================ STAGE (i) ============================= #
    print("\n==== STAGE (i) structure-first supervision ====", flush=True)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    def run_i(board_ids, train):
        net.train(train)
        tot_agg = tot_comp = 0.0; nbtot = 0
        for comp_idx, local_off, bids in batch_iter(board_ids, args.boards_per_batch, train):
            with torch.set_grad_enabled(train):
                gc = net(feat_t[comp_idx])                    # (n_comp_in_batch,)
                agg = _board_sum(gc, local_off)               # (nbatch,)
                agg_loss = torch.mean((agg - ystruct_t[bids]) ** 2)
                comp_loss = torch.mean((gc - ycomp_t[comp_idx]) ** 2)
                loss = agg_loss + args.lambda_comp * comp_loss
                if train:
                    opt.zero_grad(); loss.backward(); opt.step()
            nbb = len(bids)
            tot_agg += float(agg_loss.detach()) * nbb; tot_comp += float(comp_loss.detach()) * nbb; nbtot += nbb
        return tot_agg / nbtot, tot_comp / nbtot

    best_val = math.inf; best_state = None; stale = 0
    for ep in range(args.epochs_i):
        te = time.time()
        tra, trc = run_i(idx["train"], True)
        vaa, vac = run_i(idx["val"], False)
        vtot = vaa + args.lambda_comp * vac
        improved = vtot < best_val - 1e-6
        if (ep + 1) % 10 == 0 or improved:
            print(f"  i ep{ep+1}/{args.epochs_i} train(agg={tra:.3f} comp={trc:.3f}) "
                  f"val(agg={vaa:.3f} comp={vac:.3f}) ({time.time()-te:.1f}s)"
                  f"{' *' if improved else ''}", flush=True)
        if improved:
            best_val = vtot
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                print(f"  i early-stop ep{ep+1}", flush=True); break
    if best_state:
        net.load_state_dict(best_state)
    stage_i_state = {k: v.clone() for k, v in best_state.items()}

    # ---- VECTORIZED eval helpers (one net forward over all rows of the board
    #      set, then segment-sum — no 48K-iteration python loop). ------------- #
    def _forward_board_set(board_ids):
        """Return (per_component g over the board set's rows, per-board sums,
        y_comp over those rows). One forward + one scatter-add."""
        net.train(False)
        comp_slices = [np.arange(starts[b], ends[b]) for b in board_ids]
        comp_idx = np.concatenate(comp_slices)
        lens = np.array([len(s) for s in comp_slices], np.int64)
        local_off = np.zeros(len(board_ids) + 1, np.int64)
        local_off[1:] = np.cumsum(lens)
        with torch.no_grad():
            gc = net(feat_t[torch.from_numpy(comp_idx).to(dev)])
            agg = _board_sum(gc, torch.from_numpy(local_off).to(dev))
        return gc.cpu().numpy(), agg.cpu().numpy(), y_comp[comp_idx]

    def eval_recon(board_ids):
        gc_all, aggs, yc_all = _forward_board_set(board_ids)
        ys = y_struct[board_ids]
        ss_res = np.sum((aggs - ys) ** 2); ss_tot = np.sum((ys - ys.mean()) ** 2)
        r2_agg = 1.0 - ss_res / (ss_tot + 1e-12)
        rel_agg = float(np.sqrt(ss_res / len(ys)) / (np.abs(ys).mean() + 1e-12))
        cr = np.sum((gc_all - yc_all) ** 2); ct = np.sum((yc_all - yc_all.mean()) ** 2)
        r2_comp = 1.0 - cr / (ct + 1e-12)
        return {
            "r2_agg": float(r2_agg), "rmse_agg": float(np.sqrt(ss_res / len(ys))),
            "rel_err_agg": rel_agg, "mae_agg": float(np.abs(aggs - ys).mean()),
            "r2_comp": float(r2_comp), "mae_comp": float(np.abs(gc_all - yc_all).mean()),
            "n": int(len(ys)),
        }

    recon_test = eval_recon(idx["test"])
    print(f"[stage-i TEST] agg R2={recon_test['r2_agg']:.4f} "
          f"rel_err={recon_test['rel_err_agg']:.4f} RMSE={recon_test['rmse_agg']:.3f} | "
          f"per-comp R2={recon_test['r2_comp']:.4f} MAE={recon_test['mae_comp']:.3f}", flush=True)

    def _bag_scalar_np(board_ids, with_bag):
        """bag_head over the board set -> (n,) numpy scalar (0 if no/off bag)."""
        if bag_head is None or not with_bag:
            return np.zeros(len(board_ids), np.float32)
        bag_head.train(False)
        with torch.no_grad():
            bs = bag_head(bag_t[torch.from_numpy(board_ids).to(dev)])
        return bs.cpu().numpy().astype(np.float32)

    # aggregate agreement with h6400-Q (the ceiling reference). Uses the EXACT
    # offset (running (+cloister if bag mode)) + the bag scalar (only after the bag
    # head is trained, i.e. with_bag=True in stage ii).
    def leaf_q_pred(board_ids, with_bag):
        _, aggs, _ = _forward_board_set(board_ids)
        bs = _bag_scalar_np(board_ids, with_bag)
        return np.tanh((offset_exact[board_ids] + aggs + bs) / 15.0).astype(np.float32)

    def q_agreement(board_ids, label, with_bag=False):
        pred = leaf_q_pred(board_ids, with_bag)
        oq = oracle_q[board_ids]
        mse = float(np.mean((pred - oq) ** 2))
        # also the pure-heuristic leaf's own tanh(pretransform/15) vs Q (the ceiling).
        heur = np.tanh(z["pretransform"][board_ids] / 15.0)
        mse_heur = float(np.mean((heur - oq) ** 2))
        tau = float(fast_kendall_tau_b(pred, oq))
        tau_heur = float(fast_kendall_tau_b(heur, oq))
        print(f"[{label}] v_leaf-vs-Q MSE={mse:.4f} tau={tau:.4f} | "
              f"heuristic-vs-Q MSE={mse_heur:.4f} tau={tau_heur:.4f}", flush=True)
        return {"mse": mse, "tau": tau, "mse_heur": mse_heur, "tau_heur": tau_heur}

    q_after_i = q_agreement(idx["test"], "stage-i TEST Q")

    # ============================ STAGE (ii) ============================ #
    print("\n==== STAGE (ii) aggregate fine-tune vs h6400-Q ====", flush=True)
    # frozen stage-(i) per-component outputs as the magnitude anchor (net currently
    # holds the stage-(i) best weights).
    with torch.no_grad():
        g0_comp = net(feat_t).detach().clone()   # (Ncomp,) stage-(i) g values

    # stage-ii optimizes g_theta AND (if present) the bag head. The structure-hold
    # regularizer anchors ONLY g_theta's per-component outputs (bag is a NEW,
    # unanchored direction — that is precisely the axis we test).
    ii_params = list(net.parameters())
    if bag_head is not None:
        ii_params = ii_params + list(bag_head.parameters())
    opt2 = torch.optim.Adam(ii_params, lr=args.lr * 0.5, weight_decay=args.weight_decay)

    def run_ii(board_ids, train):
        net.train(train)
        if bag_head is not None:
            bag_head.train(train)
        tot_q = tot_reg = 0.0; nbtot = 0
        for comp_idx, local_off, bids in batch_iter(board_ids, args.boards_per_batch, train):
            with torch.set_grad_enabled(train):
                gc = net(feat_t[comp_idx])
                agg = _board_sum(gc, local_off)
                if bag_head is not None:
                    agg = agg + bag_head(bag_t[bids])
                vleaf = torch.tanh((run_t[bids] + agg) / 15.0)
                q_loss = torch.mean((vleaf - oq_t[bids]) ** 2)
                reg = torch.mean((gc - g0_comp[comp_idx]) ** 2)
                loss = q_loss + args.lambda_reg * reg
                if train:
                    opt2.zero_grad(); loss.backward(); opt2.step()
            nbb = len(bids)
            tot_q += float(q_loss.detach()) * nbb; tot_reg += float(reg.detach()) * nbb; nbtot += nbb
        return tot_q / nbtot, tot_reg / nbtot

    best_val2 = math.inf; best_state2 = None; best_bag2 = None; stale = 0
    for ep in range(args.epochs_ii):
        te = time.time()
        trq, trr = run_ii(idx["train"], True)
        vq, vr = run_ii(idx["val"], False)
        improved = vq < best_val2 - 1e-6      # select on Q-MSE (the objective)
        if (ep + 1) % 10 == 0 or improved:
            print(f"  ii ep{ep+1}/{args.epochs_ii} train(q={trq:.4f} reg={trr:.3f}) "
                  f"val(q={vq:.4f} reg={vr:.3f}) ({time.time()-te:.1f}s)"
                  f"{' *' if improved else ''}", flush=True)
        if improved:
            best_val2 = vq
            best_state2 = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
            best_bag2 = ({k: v.detach().cpu().clone() for k, v in bag_head.state_dict().items()}
                         if bag_head is not None else None)
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                print(f"  ii early-stop ep{ep+1}", flush=True); break
    if best_state2:
        net.load_state_dict(best_state2)
        if bag_head is not None and best_bag2 is not None:
            bag_head.load_state_dict(best_bag2)

    q_after_ii = q_agreement(idx["test"], "stage-ii TEST Q", with_bag=use_bag)
    recon_after_ii = eval_recon(idx["test"])
    print(f"[stage-ii TEST] agg R2={recon_after_ii['r2_agg']:.4f} "
          f"per-comp R2={recon_after_ii['r2_comp']:.4f} "
          f"(structure retention after fine-tune)", flush=True)

    # ---- ceiling verdict. -------------------------------------------------- #
    improved_q = q_after_ii["mse"] < q_after_i["mse"] - 1e-4
    beats_ceiling = q_after_ii["mse"] < q_after_i["mse_heur"] - 1e-4
    print("\n==== VERDICT (spec open-Q3) ====", flush=True)
    print(f"  stage-i  v_leaf-vs-Q MSE = {q_after_i['mse']:.4f}", flush=True)
    print(f"  stage-ii v_leaf-vs-Q MSE = {q_after_ii['mse']:.4f}  "
          f"({'IMPROVED over (i)' if improved_q else 'no improvement over (i)'})", flush=True)
    print(f"  heuristic ceiling    MSE = {q_after_i['mse_heur']:.4f}  "
          f"({'FINE-TUNE BEATS CEILING' if beats_ceiling else 'stuck at/above the v2.9 ceiling'})", flush=True)

    # ---- save the STAGE-(ii) head (the fine-tuned substrate) + summary. ---- #
    ck = {
        "state_dict": net.state_dict(),
        "stage_i_state": {k: v.cpu() for k, v in stage_i_state.items()},
        "FEAT_DIM": FEAT_DIM, "hidden": args.hidden, "arch": "GTheta",
        "col_mean": col_mean, "col_std": col_std,
        "running_offset": True, "tanh_scale": 15.0,
        "v29_hash": meta.get("v29_hash"),
        "use_bag": bool(use_bag), "cloister_exact_offset": bool(use_bag),
    }
    if use_bag:
        ck["bag_state_dict"] = bag_head.state_dict()
        ck["bag_hidden"] = int(args.bag_hidden)
        ck["bag_mean"] = bag_mean.astype(np.float32)
        ck["bag_std"] = bag_std.astype(np.float32)
    torch.save(ck, outd / "gtheta.pt")

    summary = {
        "dataset": str(dsdir), "n_boards": nb, "hidden": args.hidden, "n_params": n_params,
        "lambda_comp": args.lambda_comp, "lambda_reg": args.lambda_reg,
        "stage_i_recon_test": recon_test,
        "stage_i_q_test": q_after_i,
        "stage_ii_q_test": q_after_ii,
        "stage_ii_recon_test": recon_after_ii,
        "verdict": {
            "stage_ii_improves_q_over_i": bool(improved_q),
            "stage_ii_beats_heuristic_ceiling": bool(beats_ceiling),
            "delta_q_mse_ii_minus_i": float(q_after_ii["mse"] - q_after_i["mse"]),
            "delta_q_mse_ii_minus_ceiling": float(q_after_ii["mse"] - q_after_i["mse_heur"]),
        },
        "cap_residual_stats": meta.get("cap_residual_stats"),
        "cloister_residual_stats": meta.get("cloister_residual_stats"),
        "scale_stats": meta.get("scale_stats"),
        "v29_hash": meta.get("v29_hash"),
        "use_bag": bool(use_bag),
        "cloister_pulled_out_as_exact_offset": bool(use_bag),
        "bag_hidden": int(args.bag_hidden) if use_bag else None,
    }
    (outd / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n-> {outd}/gtheta.pt  +  {outd}/summary.json", flush=True)


if __name__ == "__main__":
    main()
