#!/usr/bin/env python3
"""High-gap distillation — Stage 2 GATE, part 2: signal-density analysis.

Loads probe.jsonl (per-action h6400 Q + metadata) + the row-aligned npz
(boards/scalars/valid_masks), forwards the student nets, and answers the gate
question: ARE THERE ENOUGH high-Q-gap, student-WRONG states to train + hold out?

For each student: student_top = prior argmax over legal; regret = q_best - Q(student_top);
wrong = student_top != teacher_best (Q-argmax). Tabulates by Q-gap tier and regret tier,
the joint (gap AND wrong) trainable cell, phase + close-score splits, and projects the
trainable yield to a 25k/50k/100k mine. Writes HIGH_GAP_SIGNAL_DENSITY.md.

Net forward only (no engine replay). Frozen-leaf env irrelevant to the prior.
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
import argparse, json, glob, sys
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))

TIERS = [("weak", 0.005), ("medium", 0.010), ("strong", 0.020), ("very_strong", 0.040)]
STUDENTS = {
    "rod1":   "/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt",
    "iter04": "/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt",
    "iter06": "/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_06.pt",
}


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
            logits = logits.masked_fill(~mm, float("-inf"))
            out[i:i+batch] = torch.softmax(logits, dim=-1).cpu().numpy()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(REPO / "measurement/high_gap_distillation/qprobe/probe.jsonl"))
    ap.add_argument("--npz-dir", default=str(REPO / "measurement/high_gap_distillation/qprobe/data"))
    ap.add_argument("--out", default=str(REPO / "measurement/high_gap_distillation/HIGH_GAP_SIGNAL_DENSITY.md"))
    args = ap.parse_args(argv)

    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    man = [json.loads(l) for l in open(args.probe)]
    boards, scalars, masks = _load_npz(Path(args.npz_dir))
    assert boards.shape[0] == len(man), f"npz {boards.shape[0]} != probe {len(man)}"
    N = len(man)

    gap = np.array([m["q_gap_1_2"] for m in man])
    teacher = np.array([m["teacher_best"] for m in man])
    phases = [m.get("phase", "?") for m in man]
    margins = np.array([m.get("score_margin_abs", 99) for m in man])
    # action_q has string keys after JSON round-trip
    aq = [{int(k): v for k, v in m["action_q"].items()} for m in man]
    qbest = np.array([m["q_best"] for m in man])
    qmin = np.array([min(d.values()) for d in aq])

    # per-student: student_top, regret, wrong
    stud = {}
    fallback_total = 0
    for name, path in STUDENTS.items():
        pr = _priors(path, boards, scalars, masks, device)
        stop = np.zeros(N, dtype=int)
        regret = np.zeros(N, dtype=float)
        wrong = np.zeros(N, dtype=bool)
        fb = 0
        for i in range(N):
            legal = np.flatnonzero(masks[i])
            a = int(legal[int(np.argmax(pr[i][legal]))])
            stop[i] = a
            qa = aq[i].get(a, None)
            if qa is None:
                qa = qmin[i]; fb += 1
            regret[i] = qbest[i] - qa
            wrong[i] = (a != teacher[i])
        stud[name] = {"top": stop, "regret": regret, "wrong": wrong}
        fallback_total += fb
        print(f"[{name}] mean regret {regret.mean():.4f}  wrong {wrong.mean():.3f}  (q-fallback {fb})")

    L = []
    L.append("# High-Contrast Decision-Signal Distillation — Signal Density (Stage 2 GATE)\n")
    L.append("**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.** "
             "No promotion · v2.9 evaluator frozen.\n")
    L.append(f"Pilot pool: the {N}-root replay-verified multiphase set, re-labeled with the v2.9 deep "
             f"teacher HeuristicMCTS@6400 for **per-action Q** (probe_signal_density.py). Students "
             f"forwarded: rod1 / iter04 / iter06 (device={device.type}). "
             f"Plan: [HIGH_GAP_PLAN.md](HIGH_GAP_PLAN.md).\n")

    # 1. Q-gap density (teacher-only)
    L.append("## 1. Q-gap density (teacher only — does the choice matter?)\n")
    L.append("| tier | thr | count | % of pool |")
    L.append("|---|--:|--:|--:|")
    for tname, thr in TIERS:
        c = int((gap >= thr).sum())
        L.append(f"| {tname} | {thr:.3f} | {c} | {c/N*100:.1f}% |")
    L.append(f"\nQ-gap mean {gap.mean():.4f} · median {np.median(gap):.4f} · "
             f"p90 {np.percentile(gap,90):.4f} · p95 {np.percentile(gap,95):.4f}. "
             f"(value scale: best-worst Q-range mean {(qbest-qmin).mean():.3f}.)\n")

    # 2. trainable cell: gap AND student-wrong (the gate number)
    L.append("## 2. Trainable cell — high Q-gap AND student wrong (the gate)\n")
    L.append("Count of states with `q_gap >= tier` **and** `student_top != teacher_best` "
             "(the states worth distilling: decisive AND the net is currently wrong).\n")
    L.append("| tier | thr | iter04 | iter06 | rod1 |")
    L.append("|---|--:|--:|--:|--:|")
    cell = {}
    for tname, thr in TIERS:
        row = [f"| {tname} | {thr:.3f} "]
        for name in ("iter04", "iter06", "rod1"):
            c = int(((gap >= thr) & stud[name]["wrong"]).sum())
            cell[(tname, name)] = c
            row.append(f"| {c} ")
        L.append("".join(row) + "|")
    L.append("")

    # 3. regret tiers (independent of gap)
    L.append("## 3. Student-regret density — Q(teacher_best) − Q(student_top)\n")
    L.append("| regret tier | thr | iter04 | iter06 | rod1 |")
    L.append("|---|--:|--:|--:|--:|")
    for tname, thr in TIERS:
        row = [f"| {tname} | {thr:.3f} "]
        for name in ("iter04", "iter06", "rod1"):
            c = int((stud[name]["regret"] >= thr).sum())
            row.append(f"| {c} ")
        L.append("".join(row) + "|")
    L.append("")

    # 4. phase + close-score split of the strong trainable cell (iter04)
    L.append("## 4. Strong trainable cell (gap≥0.02 ∧ iter04-wrong) by phase / score\n")
    strong_iter04 = (gap >= 0.020) & stud["iter04"]["wrong"]
    L.append("| slice | count | % of slice |")
    L.append("|---|--:|--:|")
    import collections
    by_phase = collections.Counter()
    ph_tot = collections.Counter()
    for i in range(N):
        ph_tot[phases[i]] += 1
        if strong_iter04[i]:
            by_phase[phases[i]] += 1
    for ph in ("opening", "midgame", "late_mid", "pre_endgame", "endgame"):
        t = ph_tot.get(ph, 0)
        c = by_phase.get(ph, 0)
        L.append(f"| {ph} | {c} | {c/max(t,1)*100:.0f}% |")
    close = (margins <= 5)
    L.append(f"| close-score(≤5) | {int((strong_iter04 & close).sum())} | "
             f"{int((strong_iter04 & close).sum())/max(int(close.sum()),1)*100:.0f}% |")
    L.append("")

    # 5. projection to a real mine
    L.append("## 5. Yield projection to a scaled mine\n")
    L.append("Trainable yield = pilot trainable-cell fraction × mine size. Held-out test needs ~1k "
             "states with gap≥0.02 OR regret≥0.02.\n")
    L.append("| selector (iter04) | pilot frac | per 25k | per 50k | per 100k |")
    L.append("|---|--:|--:|--:|--:|")
    sels = [
        ("gap≥0.02 ∧ wrong", ((gap >= 0.020) & stud["iter04"]["wrong"]).mean()),
        ("gap≥0.01 ∧ wrong", ((gap >= 0.010) & stud["iter04"]["wrong"]).mean()),
        ("regret≥0.02", (stud["iter04"]["regret"] >= 0.020).mean()),
        ("gap≥0.02 OR regret≥0.02", ((gap >= 0.020) | (stud["iter04"]["regret"] >= 0.020)).mean()),
    ]
    for sname, frac in sels:
        L.append(f"| {sname} | {frac*100:.1f}% | {int(frac*25000)} | {int(frac*50000)} | {int(frac*100000)} |")
    L.append("")
    L.append(f"<!-- q-fallback rows (student_top unvisited by teacher): {fallback_total} total across 3 nets -->")
    L.append("")

    txt = "\n".join(L)
    with open(args.out, "w") as fh:
        fh.write(txt)
    print(f"\n[analyze] wrote {args.out}")
    print("\n".join(L[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
