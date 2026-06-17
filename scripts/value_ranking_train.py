"""Phase 4C/4D — value-ranking arm training + metrics (2026-06-17).

Trains a candidate value head to RANK sibling children (target = deep-oracle
parent-POV value from value_ranking_dump_dataset.py) and reports the ranking
metrics that decide the kill-test (Phase 4E). Architecture-agnostic trunk;
the ARM varies the head and the loss so we can attribute any gain:

  A  conv head      + MSE        control: loss=value-regression (the status quo)
  B  conv head      + ranking    isolates the LOSS-FORM effect (A->B)
  C  attention head + ranking    the SWING: relational/board-spanning head (B->C)
  C0 conv-wide head + ranking    capacity-matched control for C (params ~= C)
  E  conv head      + ranking, within-group ADVANTAGE centering (relative target)

(Arm D "+OWN oracle features" needs terminal-ownership channels not in the core
dump; add via --own-npz when available. Documented extension.)

Leakage-safe: split by game_seed (all children of a group, all groups of a game,
stay in one split). NO random row split.

Decision metric is Kendall-tau and regret vs the deep oracle — NOT global value
correlation. Compares against (a) v2.7 leaf and (b) the 4A oracle self-agreement
CEILING (pass --ceiling-json) so a model tau is read relative to what is even
achievable.

Usage:
  python -u scripts/value_ranking_train.py --dataset /mnt/c/carc-shared/value_ranking/dataset \
      --arm C --trunk-filters 64 --trunk-blocks 4 --epochs 40 \
      --ceiling-json /mnt/c/carc-shared/value_ranking/label_reliability/summary.json \
      --out /mnt/c/carc-shared/value_ranking/arm_C
"""
from __future__ import annotations

import os

os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


# ---- Kendall tau-b (no scipy) ----
def kendall_tau_b(x, y):
    n = len(x)
    if n < 2:
        return float("nan")
    c = d = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            sx = (x[i] > x[j]) - (x[i] < x[j]); sy = (y[i] > y[j]) - (y[i] < y[j])
            if sx == 0 and sy == 0:
                continue
            if sx == 0:
                ty += 1; continue
            if sy == 0:
                tx += 1; continue
            c += int(sx == sy); d += int(sx != sy)
    denom = math.sqrt((c + d + tx) * (c + d + ty))
    return (c - d) / denom if denom else float("nan")


def pairwise_agreement(x, y):
    n = len(x); agree = tot = 0
    for i in range(n):
        for j in range(i + 1, n):
            sx = (x[i] > x[j]) - (x[i] < x[j]); sy = (y[i] > y[j]) - (y[i] < y[j])
            if sx == 0 or sy == 0:
                continue
            tot += 1; agree += int(sx == sy)
    return agree / tot if tot else float("nan")


# ---- model ----
class ResBlock(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.c1 = nn.Conv2d(ch, ch, 3, padding=1, bias=False); self.b1 = nn.BatchNorm2d(ch)
        self.c2 = nn.Conv2d(ch, ch, 3, padding=1, bias=False); self.b2 = nn.BatchNorm2d(ch)

    def forward(self, x):
        r = x; x = F.relu(self.b1(self.c1(x))); x = self.b2(self.c2(x)); return F.relu(x + r)


class Trunk(nn.Module):
    def __init__(self, c_in, f, blocks):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv2d(c_in, f, 3, padding=1, bias=False),
                                  nn.BatchNorm2d(f), nn.ReLU(inplace=True))
        self.blocks = nn.Sequential(*[ResBlock(f) for _ in range(blocks)])

    def forward(self, x):
        return self.blocks(self.stem(x))


class ConvHead(nn.Module):
    """Production-style value head: 1x1 project -> flatten -> cat scalars -> fc -> tanh."""
    def __init__(self, f, w, n_scalar, vproj=1, hidden=64):
        super().__init__()
        self.proj = nn.Sequential(nn.Conv2d(f, vproj, 1, bias=False),
                                  nn.BatchNorm2d(vproj), nn.ReLU(inplace=True))
        self.fc1 = nn.Linear(vproj * w * w + n_scalar, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, x, sca):
        v = self.proj(x).flatten(1)
        v = F.relu(self.fc1(torch.cat([v, sca], 1)))
        return torch.tanh(self.fc2(v)).squeeze(-1)


class AttnHead(nn.Module):
    """Relational/board-spanning head: a learned query attends over all WxW spatial
    tokens (cross-attention pooling) so the value can depend on board-wide pairwise
    relations a conv-flatten/pool head cannot express. THE SWING (arm C)."""
    def __init__(self, f, w, n_scalar, heads=4):
        super().__init__()
        self.pos = nn.Parameter(torch.zeros(1, w * w, f)); nn.init.normal_(self.pos, std=0.02)
        self.q = nn.Parameter(torch.zeros(1, 1, f)); nn.init.normal_(self.q, std=0.02)
        self.attn = nn.MultiheadAttention(f, heads, batch_first=True)
        self.fc1 = nn.Linear(f + n_scalar, 64)
        self.fc2 = nn.Linear(64, 1)

    def forward(self, x, sca):
        b, f, w, h = x.shape
        tok = x.flatten(2).transpose(1, 2) + self.pos  # (B, W*W, F)
        q = self.q.expand(b, -1, -1)
        pooled, _ = self.attn(q, tok, tok)             # (B, 1, F)
        v = F.relu(self.fc1(torch.cat([pooled.squeeze(1), sca], 1)))
        return torch.tanh(self.fc2(v)).squeeze(-1)


class RankNet(nn.Module):
    def __init__(self, arm, c_in, w, n_scalar, f, blocks):
        super().__init__()
        self.trunk = Trunk(c_in, f, blocks)
        if arm in ("A", "B", "E"):
            self.head = ConvHead(f, w, n_scalar, vproj=1, hidden=64)
        elif arm == "C0":   # capacity-matched conv control
            self.head = ConvHead(f, w, n_scalar, vproj=4, hidden=128)
        elif arm == "C":
            self.head = AttnHead(f, w, n_scalar)
        else:
            raise ValueError(f"unknown arm {arm}")

    def forward(self, obs, sca):
        return self.head(self.trunk(obs), sca)


# ---- losses ----
def listnet_loss(pred, target, temp=0.25):
    """Per-group ListNet: CE between softmax(target/temp) and log-softmax(pred/temp)."""
    tdist = F.softmax(target / temp, dim=0)
    return -(tdist * F.log_softmax(pred / temp, dim=0)).sum()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="value_ranking_train")
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--arm", choices=["A", "B", "C", "C0", "E"], required=True)
    ap.add_argument("--trunk-filters", type=int, default=64)
    ap.add_argument("--trunk-blocks", type=int, default=4)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--groups-per-batch", type=int, default=32)
    ap.add_argument("--rank-temp", type=float, default=0.25)
    ap.add_argument("--ceiling-json", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    dev = torch.device(args.device)

    z = np.load(args.dataset / "rows.npz")
    meta = json.loads((args.dataset / "meta.json").read_text())
    obs = z["child_obs"]; sca = z["child_scalars"]; q = z["oracle_q"].astype(np.float32)
    grp = z["group_id"]; gs = z["game_seed"]; ply = z["ply"]
    w = obs.shape[-1]; c_in = obs.shape[1]; n_scalar = sca.shape[1]
    print(f"dataset: {q.shape[0]} rows / {meta['n_groups']} groups / {meta['n_games']} games "
          f"obs={obs.shape[1:]} arm={args.arm}", flush=True)

    # leakage-safe split by game_seed (hash to train/val/test = 70/15/15)
    def bucket(seed):
        h = int(hashlib.md5(str(int(seed)).encode()).hexdigest(), 16) % 100
        return "train" if h < 70 else "val" if h < 85 else "test"
    split_of = {g: bucket(g) for g in np.unique(gs)}
    groups = {}
    for i in range(len(q)):
        groups.setdefault(int(grp[i]), []).append(i)
    # keep only groups with >=2 children (ranking needs a pair)
    g_by_split = {"train": [], "val": [], "test": []}
    for g, idxs in groups.items():
        if len(idxs) < 2:
            continue
        g_by_split[split_of[gs[idxs[0]]]].append(np.array(idxs))
    for s in g_by_split:
        print(f"  {s}: {len(g_by_split[s])} groups", flush=True)

    obs_t = torch.from_numpy(obs.astype(np.float32))
    sca_t = torch.from_numpy(sca.astype(np.float32))
    q_t = torch.from_numpy(q)

    net = RankNet(args.arm, c_in, w, n_scalar, args.trunk_filters, args.trunk_blocks).to(dev)
    n_params = sum(p.numel() for p in net.parameters())
    opt = torch.optim.Adam(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    print(f"  arm {args.arm}: {n_params/1e3:.0f}k params on {dev}", flush=True)

    def run_groups(gl, train):
        net.train(train)
        order = list(range(len(gl)))
        if train:
            np.random.shuffle(order)
        total = 0.0; nb = 0
        for b0 in range(0, len(order), args.groups_per_batch):
            batch = [gl[order[k]] for k in order[b0:b0 + args.groups_per_batch]]
            if not batch:
                continue
            flat = np.concatenate(batch)
            o = obs_t[flat].to(dev); s = sca_t[flat].to(dev); tq = q_t[flat].to(dev)
            with torch.set_grad_enabled(train):
                pred = net(o, s)
                loss = 0.0; off = 0
                for gidx in batch:
                    k = len(gidx); p = pred[off:off + k]; t = tq[off:off + k]; off += k
                    if args.arm == "A":
                        loss = loss + F.mse_loss(p, t)
                    elif args.arm == "E":
                        loss = loss + listnet_loss(p - p.mean(), t - t.mean(), args.rank_temp)
                    else:
                        loss = loss + listnet_loss(p, t, args.rank_temp)
                loss = loss / len(batch)
                if train:
                    opt.zero_grad(); loss.backward(); opt.step()
            total += float(loss); nb += 1
        return total / max(nb, 1)

    best_val = math.inf; best_state = None
    for ep in range(args.epochs):
        tl = run_groups(g_by_split["train"], True)
        vl = run_groups(g_by_split["val"], False)
        if vl < best_val:
            best_val = vl; best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
        if (ep + 1) % 5 == 0 or ep == 0:
            print(f"  ep {ep+1}/{args.epochs} train={tl:.4f} val={vl:.4f}", flush=True)
    if best_state:
        net.load_state_dict(best_state)

    # ---- test metrics (per group) ----
    net.train(False)
    rows = []
    with torch.no_grad():
        for gidx in g_by_split["test"]:
            o = obs_t[gidx].to(dev); s = sca_t[gidx].to(dev)
            pred = net(o, s).cpu().numpy()
            tq = q[gidx]
            best = int(np.argmax(tq))
            pick = int(np.argmax(pred))
            sp = float(tq.max() - tq.min())
            rows.append({
                "tau": kendall_tau_b(pred, tq), "top1": int(pick == best),
                "pair": pairwise_agreement(pred, tq),
                "regret": float(tq[best] - tq[pick]),
                "spread": sp, "k": len(gidx),
                "ply": int(ply[gidx][0]),
                "phase": ("open" if ply[gidx][0] < 24 else "mid" if ply[gidx][0] < 48 else "end"),
            })

    def agg(key, sub=None):
        vv = [r[key] for r in rows if (sub is None or sub(r)) and not
              (isinstance(r[key], float) and math.isnan(r[key]))]
        if not vv:
            return None
        return {"mean": float(np.mean(vv)), "se": float(np.std(vv) / math.sqrt(len(vv))), "n": len(vv)}

    ceiling = None
    if args.ceiling_json and args.ceiling_json.exists():
        cj = json.loads(args.ceiling_json.read_text())
        ceiling = cj.get("ceiling", {}).get("tau_ab")

    summary = {
        "arm": args.arm, "n_params": int(n_params), "dataset": str(args.dataset),
        "dataset_sha": meta.get("checkpoint_sha256"),
        "trunk": {"filters": args.trunk_filters, "blocks": args.trunk_blocks},
        "n_test_groups": len(rows), "best_val_loss": best_val,
        "tau": agg("tau"), "top1": agg("top1"), "pair": agg("pair"), "regret": agg("regret"),
        "tau_high_spread": agg("tau", lambda r: r["spread"] >= 0.3),
        "tau_low_spread": agg("tau", lambda r: r["spread"] < 0.3),
        "tau_by_phase": {ph: agg("tau", (lambda p: (lambda r: r["phase"] == p))(ph))
                         for ph in ("open", "mid", "end")},
        "oracle_ceiling_tau_ab": ceiling,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    torch.save(net.state_dict(), args.out / "head.pt")
    print("\n" + "=" * 56)
    print(f"ARM {args.arm}  ({len(rows)} test groups, {n_params/1e3:.0f}k params)")
    print("=" * 56)
    tau = summary["tau"]
    print(f"  Kendall-tau vs oracle : {tau['mean']:+.3f} +- {tau['se']:.3f}")
    print(f"  top-1 / pairwise      : {summary['top1']['mean']:.3f} / {summary['pair']['mean']:.3f}")
    print(f"  oracle regret (tanh)  : {summary['regret']['mean']:.4f}")
    if ceiling:
        print(f"  [ceiling tau(A,B)={ceiling['mean']:+.3f}; model achieves "
              f"{100*tau['mean']/ceiling['mean']:.0f}% of the achievable ranking]")
    print(f"  -> {args.out}/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
