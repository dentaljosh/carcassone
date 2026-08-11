#!/usr/bin/env python3
"""Offline KILL-TEST for the C4 hypothesis (does the value head lose because it's
blind to farm/control structure?).

Trains a small value CNN to predict the self-play value target tanh((p0-p1)/15) two
ways on the SAME data + split:
  BLIND : input = 78 board channels (+12 scalars)  -- the current representation
  +OWN  : input = 78 board + 3 terminal-ownership channels (+12 scalars)

The `ownership` planes (farm/city/road control AT GAME END) are an ORACLE UPPER BOUND
on what live farm-connectivity (C4a) could ever provide -- they literally leak the
endgame control the heuristic estimates. So:
  +OWN >> BLIND  -> control/farm sight is the missing ingredient -> C4 worth building
                    (live-approx will be WEAKER than this oracle -> treat as a ceiling).
  +OWN ~= BLIND  -> even oracle control-sight doesn't help value prediction -> C4 is
                    NOT the fix; the ceiling is deeper. Don't spend the retrain.

Each arm trained with N_SEEDS inits; reports mean+/-std held-out Pearson corr & MSE.
Split is BY GAME (no same-game leakage across train/val).
"""
import argparse
import glob

import numpy as np
import torch
import torch.nn as nn


def load(iter_dir, n_games):
    files = sorted(glob.glob(f"{iter_dir}/seed_*.npz"))[:n_games]
    games = []
    for f in files:
        d = np.load(f)
        games.append((d["boards"].astype(np.float32), d["scalars"].astype(np.float32),
                      d["values"].astype(np.float32), d["ownership"].astype(np.float32)))
    return games


class ValCNN(nn.Module):
    def __init__(self, in_ch, n_scalar=12):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Sequential(
            nn.Linear(64 + n_scalar, 64), nn.ReLU(), nn.Linear(64, 1), nn.Tanh())

    def forward(self, b, s):
        x = self.conv(b).flatten(1)
        return self.head(torch.cat([x, s], 1)).squeeze(1)


def pack(games, idx, use_own, dev):
    B = np.concatenate([games[i][0] for i in idx])
    S = np.concatenate([games[i][1] for i in idx])
    V = np.concatenate([games[i][2] for i in idx])
    if use_own:
        O = np.concatenate([games[i][3] for i in idx])
        B = np.concatenate([B, O], axis=1)
    return (torch.from_numpy(B).to(dev), torch.from_numpy(S).to(dev),
            torch.from_numpy(V).to(dev))


def train_eval(games, tr, va, use_own, seed, dev, epochs):
    torch.manual_seed(seed)
    Btr, Str, Vtr = pack(games, tr, use_own, dev)
    Bva, Sva, Vva = pack(games, va, use_own, dev)
    net = ValCNN(Btr.shape[1]).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lossf = nn.MSELoss()
    n = Btr.shape[0]
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(n, device=dev)
        for i in range(0, n, 256):
            j = perm[i:i + 256]
            opt.zero_grad()
            loss = lossf(net(Btr[j], Str[j]), Vtr[j])
            loss.backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        pred = net(Bva, Sva)
        mse = lossf(pred, Vva).item()
        p, v = pred.cpu().numpy(), Vva.cpu().numpy()
        corr = float(np.corrcoef(p, v)[0, 1])
    return corr, mse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter-dir", default="/mnt/c/carc-shared/stage_b/iter_01")
    ap.add_argument("--n-games", type=int, default=40)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"loading {args.n_games} games from {args.iter_dir} ...")
    games = load(args.iter_dir, args.n_games)
    npos = sum(len(g[2]) for g in games)
    print(f"{len(games)} games, {npos} positions, device={dev}")
    rng = np.random.default_rng(0)
    order = rng.permutation(len(games))
    cut = int(len(games) * 0.8)
    tr, va = list(order[:cut]), list(order[cut:])
    nva = sum(len(games[i][2]) for i in va)
    print(f"split: {len(tr)} train games / {len(va)} val games ({nva} val positions)")
    # trivial baseline: predict the train mean
    vtr = np.concatenate([games[i][2] for i in tr])
    vva = np.concatenate([games[i][2] for i in va])
    base_mse = float(np.mean((vva - vtr.mean()) ** 2))
    print(f"baseline (predict train-mean) val MSE = {base_mse:.4f}\n")

    for use_own, name in [(False, "BLIND"), (True, "+OWN ")]:
        cs, ms = [], []
        for s in range(args.seeds):
            c, m = train_eval(games, tr, va, use_own, s, dev, args.epochs)
            cs.append(c); ms.append(m)
        print(f"{name}: corr={np.mean(cs):+.3f}±{np.std(cs):.3f}  "
              f"MSE={np.mean(ms):.4f}±{np.std(ms):.4f}  (seeds={args.seeds})")


if __name__ == "__main__":
    main()
