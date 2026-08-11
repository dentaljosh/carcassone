#!/usr/bin/env python3
"""Hard-position policy-repair — Stage 2/4/5 metric.

Given a manifest (+ its aligned npz split) and a list of checkpoints, compute each
net's POLICY-PRIOR behaviour on the set:
  top1   = P(prior argmax == h6400 top move)        [agreement with deep teacher]
  top3   = P(h6400 move in net's top-3 legal)
  rank   = mean rank of the h6400 move under the prior (1 = best; lower better)
  KL     = mean KL(h6400_visit_dist || net_prior)   over legal
  lean   = P(argmax==h6400) − P(argmax==h3200)       [+ = toward deep ruler]
  P_neither = P(argmax ∉ {h3200,h6400 top})          [the diffuse signature]
Plus phase split (endgame called out) and a close-score split.

The npz (boards/scalars/valid_masks/policies=h6400 target) are row-aligned with the
manifest (written from the same ordered list), so NO engine replay is needed — just a
batched net forward. v2.9 env is irrelevant to the prior (leaf-independent) but set
anyway for parity.
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
import argparse, json, glob, math, sys
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))


def _load_split(npz_dir: Path):
    fs = sorted(glob.glob(str(npz_dir / "iter_00" / "seed_*.npz")))
    B, S, M, P = [], [], [], []
    for f in fs:
        d = np.load(f)
        B.append(d["boards"]); S.append(d["scalars"])
        M.append(d["valid_masks"]); P.append(d["policies"])
    if not B:
        return None
    return (np.concatenate(B), np.concatenate(S),
            np.concatenate(M), np.concatenate(P))


def _net_priors(ckpt_path, boards, scalars, masks, device, batch=256):
    import torch
    from carcassonne_ai.network import CarcassonneNet
    ck = torch.load(ckpt_path, map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(device)
    net.load_state_dict(ck["model_state"]); net.train(False)
    out = np.zeros((boards.shape[0], masks.shape[1]), dtype=np.float32)
    with torch.no_grad():
        for i in range(0, boards.shape[0], batch):
            bb = torch.from_numpy(boards[i:i+batch]).to(device)
            ss = torch.from_numpy(scalars[i:i+batch]).to(device)
            mm = torch.from_numpy(masks[i:i+batch]).to(device).bool()
            logits, _, _ = net.forward_train(bb, ss)
            logits = logits.masked_fill(~mm, float("-inf"))
            pr = torch.softmax(logits, dim=-1)
            out[i:i+batch] = pr.cpu().numpy()
    return out


def _metrics(priors, target, masks, h3200, h6400, phases, margins):
    n = priors.shape[0]
    top1 = top3 = lean_pos = lean_neg = neither = 0
    ranks, kls = [], []
    for i in range(n):
        legal = np.flatnonzero(masks[i])
        pr = priors[i]
        arg = int(legal[int(np.argmax(pr[legal]))])
        order = legal[np.argsort(-pr[legal])]
        h6 = h6400[i]; h3 = h3200[i]
        if arg == h6: top1 += 1; lean_pos += 1
        if arg == h3: lean_neg += 1
        if arg != h6 and arg != h3: neither += 1
        top3 += 1 if h6 in order[:3] else 0
        rank = int(np.where(order == h6)[0][0]) + 1 if h6 in order else len(order)
        ranks.append(rank)
        tgt = target[i]
        nz = (tgt > 0) & masks[i]
        kl = float(np.sum(tgt[nz] * (np.log(tgt[nz]) - np.log(np.clip(pr[nz], 1e-12, 1)))))
        kls.append(kl)
    return {
        "n": n,
        "top1": top1 / n, "top3": top3 / n,
        "rank": float(np.mean(ranks)), "KL": float(np.mean(kls)),
        "lean": (lean_pos - lean_neg) / n, "P_neither": neither / n,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--npz-dir", required=True)
    ap.add_argument("--checkpoints", required=True,
                    help="comma list name=path,name=path")
    ap.add_argument("--out", default=None, help="append a markdown section here")
    ap.add_argument("--title", default="hard-set eval")
    args = ap.parse_args(argv)

    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    man = [json.loads(l) for l in open(args.manifest)]
    arrs = _load_split(Path(args.npz_dir))
    if arrs is None:
        print(f"no npz under {args.npz_dir}"); return 1
    boards, scalars, masks, target = arrs
    assert boards.shape[0] == len(man), f"npz {boards.shape[0]} != manifest {len(man)}"
    h3200 = np.array([m["h3200_choice"] for m in man])
    h6400 = np.array([m["h6400_choice"] for m in man])
    phases = [m.get("phase", "?") for m in man]
    margins = np.array([m.get("score_margin_abs", 99) for m in man])

    ckpts = []
    for tok in args.checkpoints.split(","):
        name, path = tok.split("=", 1)
        ckpts.append((name.strip(), path.strip()))

    lines = [f"\n## {args.title}  (n={len(man)}, device={device.type})\n"]
    lines.append("| net | top1 | top3 | rank | KL | lean | P_neither |")
    lines.append("|---|--:|--:|--:|--:|--:|--:|")
    endg_idx = [i for i, p in enumerate(phases) if p == "endgame"]
    close_idx = [i for i, mg in enumerate(margins) if mg <= 5]
    sub_lines = ["\n### Endgame-only / close-score(≤5) subsets — top1 / lean / P_neither\n",
                 "| net | endgame n | eg top1 | eg lean | eg Pneither | close n | cl top1 | cl lean |",
                 "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for name, path in ckpts:
        priors = _net_priors(path, boards, scalars, masks, device)
        m = _metrics(priors, target, masks, h3200, h6400, phases, margins)
        lines.append(f"| {name} | {m['top1']:.3f} | {m['top3']:.3f} | {m['rank']:.2f} "
                     f"| {m['KL']:.3f} | {m['lean']:+.3f} | {m['P_neither']:.3f} |")
        def sub(idx):
            if not idx:
                return (0, float('nan'), float('nan'), float('nan'))
            mm = _metrics(priors[idx], target[idx], masks[idx], h3200[idx], h6400[idx],
                          [phases[i] for i in idx], margins[idx])
            return (mm['n'], mm['top1'], mm['lean'], mm['P_neither'])
        en, et1, el, epn = sub(endg_idx)
        cn, ct1, cl, _ = sub(close_idx)
        sub_lines.append(f"| {name} | {en} | {et1:.3f} | {el:+.3f} | {epn:.3f} "
                         f"| {cn} | {ct1:.3f} | {cl:+.3f} |")
    txt = "\n".join(lines + sub_lines) + "\n"
    print(txt)
    if args.out:
        with open(args.out, "a") as fh:
            fh.write(txt)
        print(f"[hardset-eval] appended to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
