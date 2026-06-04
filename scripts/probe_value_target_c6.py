#!/usr/bin/env python3
"""Offline gate for C6 (de-saturated value target).

Does training the value head on tanh(margin/40) (wide) resolve TRUE margins better than
tanh(margin/15) (current, which pins to +/-1 for 30-80pt margins)? Recovers the per-
position POV margin m = 15*atanh(value) from the self-play npz (0% hit the float32
ceiling -> clean recovery), builds both targets, trains the SAME deep CNN on each, and
measures how well each head's output tracks the true margin -- overall and on the
SATURATED subset |m|>33pts (~44% of positions) where tanh/15 loses resolution.

  t40 corr >> t15 corr on |m|>33  -> C6 improves margin resolution -> worth a real
                                     retrain + value-blend test.
  t40 ~= t15                      -> C6 doesn't help the head -> dead (cheap path done).
"""
import argparse
import glob

import numpy as np
import torch
import torch.nn as nn


def load(iter_dir, n):
    G = []
    for f in sorted(glob.glob(f"{iter_dir}/seed_*.npz"))[:n]:
        d = np.load(f)
        G.append((d["boards"].astype("float32"), d["scalars"].astype("float32"),
                  d["values"].astype("float32")))
    return G


class ValCNN(nn.Module):
    def __init__(self, in_ch, ns=12):
        super().__init__()
        self.c = nn.Sequential(
            nn.Conv2d(in_ch, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1))
        self.h = nn.Sequential(nn.Linear(64 + ns, 64), nn.ReLU(), nn.Linear(64, 1), nn.Tanh())

    def forward(self, b, s):
        return self.h(torch.cat([self.c(b).flatten(1), s], 1)).squeeze(1)


def pk(G, idx, scale, dev):
    B = np.concatenate([G[i][0] for i in idx])
    S = np.concatenate([G[i][1] for i in idx])
    V = np.concatenate([G[i][2] for i in idx])
    m = 15.0 * np.arctanh(np.clip(V, -0.9999, 0.9999))   # recovered POV margin
    t = np.tanh(m / scale).astype("float32")
    return (torch.from_numpy(B).to(dev), torch.from_numpy(S).to(dev),
            torch.from_numpy(t).to(dev), m.astype("float32"))


def train_eval(G, tr, va, scale, seed, dev, epochs):
    torch.manual_seed(seed)
    Btr, Str, Ttr, _ = pk(G, tr, scale, dev)
    Bva, Sva, _, mva = pk(G, va, scale, dev)
    net = ValCNN(Btr.shape[1]).to(dev)
    opt = torch.optim.Adam(net.parameters(), 1e-3)
    lf = nn.MSELoss()
    n = Btr.shape[0]
    for _ in range(epochs):
        net.train()
        perm = torch.randperm(n, device=dev)
        for i in range(0, n, 256):
            j = perm[i:i + 256]
            opt.zero_grad()
            lf(net(Btr[j], Str[j]), Ttr[j]).backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        pred = net(Bva, Sva).cpu().numpy()
    return pred, mva


def corr(a, b):
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter-dir", default="/mnt/c/carc-shared/stage_b/iter_01")
    ap.add_argument("--n-games", type=int, default=60)
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    G = load(a.iter_dir, a.n_games)
    npos = sum(len(g[2]) for g in G)
    print(f"{len(G)} games, {npos} positions, dev={dev}")
    rng = np.random.default_rng(0)
    order = rng.permutation(len(G))
    cut = int(len(G) * 0.8)
    tr, va = list(order[:cut]), list(order[cut:])
    print("metric = corr(head output, TRUE margin); higher = better margin tracking\n")
    for scale, name in [(15, "t15 (current)"), (40, "t40 (C6 wide)")]:
        co, cosat = [], []
        for s in range(a.seeds):
            pred, m = train_eval(G, tr, va, scale, s, dev, a.epochs)
            co.append(corr(pred, m))
            sat = np.abs(m) > 33.0
            cosat.append(corr(pred[sat], m[sat]))
        print(f"  {name}: corr(all)= {np.mean(co):+.3f}±{np.std(co):.3f}  "
              f"| corr(|m|>33 subset)= {np.mean(cosat):+.3f}±{np.std(cosat):.3f}")


if __name__ == "__main__":
    main()
