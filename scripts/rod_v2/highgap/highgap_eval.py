#!/usr/bin/env python3
"""High-gap distillation — Stage 5: held-out policy eval (the pass/fail).

On the held-out hard TEST set (Tier A∪B, game-disjoint from train), compare each
checkpoint's policy prior vs the h6400 deep teacher:
  top1     = P(argmax == teacher_best)
  top3     = P(teacher_best in net top-3 legal)
  rank     = mean rank of teacher_best
  p_teach  = mean prior mass on teacher_best
  regret   = mean Q(teacher_best) − Q(student_top)   [value left on the table; lower=better]
  med_reg  = median regret
Plus endgame and Q-gap-tier (strong gap>=0.02) splits.

Pass (vs the iter04 baseline): top1 ↑ materially, top3 ↑, mean regret ↓ ≥20%, endgame
not collapsed. Reads teacher_best + action_q from the manifest (no engine replay).
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
import argparse, json, glob, sys
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))


def _load_npz(npz_dir: Path):
    fs = sorted(glob.glob(str(npz_dir / "iter_00" / "seed_*.npz")))
    B, S, M = [], [], []
    for f in fs:
        d = np.load(f)
        B.append(d["boards"]); S.append(d["scalars"]); M.append(d["valid_masks"])
    return np.concatenate(B), np.concatenate(S), np.concatenate(M)


def _priors(ckpt_path, boards, scalars, masks, device, batch=256):
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
            out[i:i+batch] = torch.softmax(logits.masked_fill(~mm, float("-inf")), -1).cpu().numpy()
    return out


def _metrics(pr, masks, teacher, aq, qbest, idx):
    top1 = top3 = 0; ranks = []; pteach = []; regs = []
    for i in idx:
        legal = np.flatnonzero(masks[i])
        order = legal[np.argsort(-pr[i][legal])]
        a = int(order[0]); h = int(teacher[i])
        if a == h: top1 += 1
        if h in order[:3]: top3 += 1
        ranks.append(int(np.where(order == h)[0][0]) + 1 if h in order else len(order))
        pteach.append(float(pr[i][h]))
        regs.append(float(qbest[i] - aq[i].get(a, min(aq[i].values()))))
    n = len(idx)
    return dict(n=n, top1=top1/n, top3=top3/n, rank=float(np.mean(ranks)),
                p_teach=float(np.mean(pteach)), regret=float(np.mean(regs)),
                med_reg=float(np.median(regs)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--npz-dir", required=True)
    ap.add_argument("--checkpoints", required=True, help="name=path,name=path")
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default="high-gap held-out eval")
    args = ap.parse_args(argv)

    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    man = [json.loads(l) for l in open(args.manifest)]
    boards, scalars, masks = _load_npz(Path(args.npz_dir))
    assert boards.shape[0] == len(man), f"{boards.shape[0]} != {len(man)}"
    teacher = np.array([m["teacher_best"] for m in man])
    qbest = np.array([m["q_best"] for m in man])
    gap = np.array([m["q_gap_1_2"] for m in man])
    phases = [m.get("phase", "?") for m in man]
    aq = [{int(k): v for k, v in m["action_q"].items()} for m in man]
    allidx = list(range(len(man)))
    eg = [i for i in allidx if phases[i] == "endgame"]
    strong = [i for i in allidx if gap[i] >= 0.020]

    ckpts = [(t.split("=", 1)[0].strip(), t.split("=", 1)[1].strip()) for t in args.checkpoints.split(",")]
    L = [f"\n## {args.title}  (n={len(man)}, device={device.type})\n",
         "| net | top1 | top3 | rank | p_teach | regret | med_reg |",
         "|---|--:|--:|--:|--:|--:|--:|"]
    sub = ["\n### endgame / strong-gap(≥0.02) subsets — top1 / regret\n",
           "| net | eg n | eg top1 | eg regret | strong n | st top1 | st regret |",
           "|---|--:|--:|--:|--:|--:|--:|"]
    for name, path in ckpts:
        pr = _priors(path, boards, scalars, masks, device)
        m = _metrics(pr, masks, teacher, aq, qbest, allidx)
        L.append(f"| {name} | {m['top1']:.3f} | {m['top3']:.3f} | {m['rank']:.2f} | "
                 f"{m['p_teach']:.3f} | {m['regret']:.4f} | {m['med_reg']:.4f} |")
        me = _metrics(pr, masks, teacher, aq, qbest, eg) if eg else dict(n=0, top1=float('nan'), regret=float('nan'))
        ms = _metrics(pr, masks, teacher, aq, qbest, strong) if strong else dict(n=0, top1=float('nan'), regret=float('nan'))
        sub.append(f"| {name} | {me['n']} | {me['top1']:.3f} | {me['regret']:.4f} | "
                   f"{ms['n']} | {ms['top1']:.3f} | {ms['regret']:.4f} |")
    txt = "\n".join(L + sub) + "\n"
    print(txt)
    if args.out:
        with open(args.out, "a") as fh:
            fh.write(txt)
        print(f"[highgap-eval] appended to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
