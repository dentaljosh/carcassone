#!/usr/bin/env python3
"""High-gap distillation — Stage 3: build tier splits + soft targets.

Reads a probe.jsonl (+ row-aligned npz from probe_signal_density.py), forwards the
PRIMARY student to assign tiers + compute regret, and writes train_iter.py-format npz
with **Q-softmax soft targets** (advantage-based; NOT one-hot argmax, NOT the ~flat
h6400 visit dist that the prior experiment showed carries no peak).

Tiers (per state, via h6400 Q-gap and iter04 regret):
  A (strong)     : q_gap >= 0.020 OR regret >= 0.020
  B (medium)     : q_gap >= 0.010 OR regret >= 0.010   (and not A)
  C (stabiliser) : decisive (q_gap >= 0.010) AND student already correct  → anti-forgetting

Splits are GAME-GROUPED by seed (gen_id = mp{seed}) → no same-game leakage across
train/val/test. Hard set = A ∪ B → train/val/test. Stabiliser = C → a single pool used
as the train-time warmstart mix (`--warmstart-root`, like the prior P2).

Soft target = softmax(Q_legal / temp), temp tunable. On a decisive state (large gap)
this is peaked on the best move ∝ the gap; on an indifferent state it stays diffuse —
exactly encoding decision-relevance.
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
import argparse, json, glob, sys
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
from carcassonne_ai.aux_targets import OWNERSHIP_PLANES  # noqa: E402

PRIMARY = "/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt"


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


def _soft_target(aq: dict, A: int, mask: np.ndarray, temp: float) -> np.ndarray:
    """softmax(Q/temp) over legal actions present in aq; legal-but-unvisited get the min."""
    legal = np.flatnonzero(mask)
    qmin = min(aq.values())
    qv = np.array([aq.get(int(a), qmin) for a in legal], dtype=np.float64)
    z = qv / max(temp, 1e-6)
    z -= z.max()
    w = np.exp(z); w /= w.sum()
    pol = np.zeros(A, dtype=np.float32)
    pol[legal] = w.astype(np.float32)
    return pol


def _write(rows, out_dir: Path, temp: float, chunk: int = 256):
    it = out_dir / "iter_00"
    it.mkdir(parents=True, exist_ok=True)
    if not rows:
        return 0
    W = rows[0]["_board"].shape[-1]
    for ci in range(0, len(rows), chunk):
        grp = rows[ci:ci + chunk]
        n = len(grp)
        np.savez_compressed(
            it / f"seed_{ci:06d}.npz",
            boards=np.stack([r["_board"] for r in grp]),
            scalars=np.stack([r["_scalars"] for r in grp]),
            policies=np.stack([r["_policy"] for r in grp]),
            values=np.zeros(n, dtype=np.float32),
            valid_masks=np.stack([r["_mask"] for r in grp]),
            ownership=np.zeros((n, OWNERSHIP_PLANES, W, W), dtype=np.float32),
            aux_mask=np.ones(n, dtype=bool),
            group_id=np.full(n, -1, dtype=np.int64),
        )
    return len(rows)


def _write_manifest(rows, path: Path):
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(REPO / "measurement/high_gap_distillation/qprobe/probe.jsonl"))
    ap.add_argument("--npz-dir", default=str(REPO / "measurement/high_gap_distillation/qprobe/data"))
    ap.add_argument("--out", default=str(REPO / "measurement/high_gap_distillation"))
    ap.add_argument("--temp", type=float, default=0.03, help="Q-softmax temperature for soft targets")
    ap.add_argument("--strong", type=float, default=0.020)
    ap.add_argument("--medium", type=float, default=0.010)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--split-seed", type=int, default=11)
    args = ap.parse_args(argv)

    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    man = [json.loads(l) for l in open(args.probe)]
    boards, scalars, masks = _load_npz(Path(args.npz_dir))
    assert boards.shape[0] == len(man), f"{boards.shape[0]} != {len(man)}"
    N = len(man)
    aq = [{int(k): v for k, v in m["action_q"].items()} for m in man]
    gap = np.array([m["q_gap_1_2"] for m in man])
    teacher = np.array([m["teacher_best"] for m in man])
    qbest = np.array([m["q_best"] for m in man])

    pr = _priors(PRIMARY, boards, scalars, masks, device)
    stop = np.zeros(N, dtype=int); regret = np.zeros(N); wrong = np.zeros(N, bool)
    for i in range(N):
        legal = np.flatnonzero(masks[i])
        a = int(legal[int(np.argmax(pr[i][legal]))])
        stop[i] = a; regret[i] = qbest[i] - aq[i].get(a, min(aq[i].values()))
        wrong[i] = a != teacher[i]

    # tier assignment — HARD set = student is WRONG by a value amount (repair targets);
    # STABILISER = decisive states the student already gets right (anti-forgetting).
    # Note gap>=0.02 ∧ wrong ⟹ regret>=0.02, so regret is the clean hard-set axis.
    is_A = wrong & (regret >= args.strong)                       # strong hard
    is_B = wrong & ~is_A & (regret >= args.medium)               # medium hard
    is_C = (~wrong) & (gap >= args.strong)                       # decisive & already correct
    tier = np.where(is_A, "A", np.where(is_B, "B", np.where(is_C, "C", "-")))

    # game-grouped split (by seed) — whole games to train/val/test
    seeds = np.array([m["seed"] for m in man])
    uniq = sorted(set(seeds.tolist()))
    rng = np.random.RandomState(args.split_seed)
    perm = rng.permutation(len(uniq))
    nv = int(round(args.val_frac * len(uniq))); nt = int(round(args.test_frac * len(uniq)))
    test_seeds = {uniq[i] for i in perm[:nt]}
    val_seeds = {uniq[i] for i in perm[nt:nt+nv]}

    def split_of(s):
        return "test" if s in test_seeds else ("val" if s in val_seeds else "train")

    buckets = {("hard", "train"): [], ("hard", "val"): [], ("hard", "test"): [], ("stab", "all"): []}
    for i in range(N):
        t = tier[i]
        if t in ("A", "B"):
            row = dict(man[i])
            row["tier"] = t; row["regret_iter04"] = round(float(regret[i]), 6)
            row["student_top_iter04"] = int(stop[i]); row["wrong_iter04"] = bool(wrong[i])
            row["_board"] = boards[i]; row["_scalars"] = scalars[i]; row["_mask"] = masks[i]
            row["_policy"] = _soft_target(aq[i], masks.shape[1], masks[i], args.temp)
            buckets[("hard", split_of(seeds[i]))].append(row)
        elif t == "C":
            row = dict(man[i]); row["tier"] = "C"
            row["_board"] = boards[i]; row["_scalars"] = scalars[i]; row["_mask"] = masks[i]
            row["_policy"] = _soft_target(aq[i], masks.shape[1], masks[i], args.temp)
            buckets[("stab", "all")].append(row)

    out = Path(args.out)
    for (kind, sp), rows in buckets.items():
        name = "stabilizer" if kind == "stab" else f"hard_{sp}"
        _write(rows, out / "data" / name, args.temp)
        _write_manifest(rows, out / f"manifest_{name}.jsonl")

    print(f"[splits] N={N}  tiers: A={int(is_A.sum())} B={int(is_B.sum())} C={int(is_C.sum())} "
          f"none={int((tier=='-').sum())}")
    print(f"[splits] hard train={len(buckets[('hard','train')])} val={len(buckets[('hard','val')])} "
          f"test={len(buckets[('hard','test')])}  stabiliser={len(buckets[('stab','all')])}")
    print(f"[splits] games: total={len(uniq)} test={len(test_seeds)} val={len(val_seeds)} "
          f"train={len(uniq)-len(test_seeds)-len(val_seeds)}  temp={args.temp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
