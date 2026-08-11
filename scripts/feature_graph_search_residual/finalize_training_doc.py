#!/usr/bin/env python3
"""Write FGSR_TRAINING.md from data/train_summary.json (canonical numbers; no hand-typing)."""
import json
from pathlib import Path

REPO = Path("/home/doctor/projects/carcassone")
OUT = REPO / "measurement" / "feature_graph_search_residual"
S = json.loads((OUT / "data" / "train_summary.json").read_text())

L = ["# FGSR_TRAINING.md — Stage 5 training (G0, G1; both heads)\n",
     "> **STATUS: 🟢 TRAINED.** CPU-only, net-free, no search, no games. Numbers below are read "
     "from `data/train_summary.json` (canonical). _Last updated 2026-06-29._\n",
     f"Split (by game_seed, leak-free): tr={S['n_tr']} va={S['n_va']} te={S['n_te']}. "
     f"Decisive tail: tr={S['tail']['tr']} va={S['tail']['va']} te={S['tail']['te']}.\n",
     "Targets/early-stop: **G3** = BCE(pos_strong), positives weighted by 1+30·regret(h200), "
     "early-stop on VAL AUROC(pos_strong). **G4** = listwise softmax-CE toward q6400 "
     "(weighted 1+20·q_gap_6400), early-stop on VAL decisive-tail selected-move regret.\n",
     "## Realized fit (the sanity check: train AUROC > 0.5, ideally ≳ B5's 0.78 on val)\n",
     "| model | params | G3 train AUROC | G3 val AUROC | G3 test AUROC | G3 best-ep | "
     "G4 val tail-regret | G4 best-ep |",
     "|---|---|---|---|---|---|---|---|"]
for m, d in S["models"].items():
    L.append(f"| {m} | {d.get('params','—'):,} | {d['g3_train_auroc']:.3f} | "
             f"{d['g3_val_auroc']:.3f} | {d['g3_test_auroc']:.3f} | {d['g3_best_epoch']} | "
             f"{d['g4_val_tail_regret']:.5f} | {d['g4_best_epoch']} |")
L.append("")
L.append(f"_Train wall-clock: {S.get('runtime_s','?')} s (CPU, nice -n 19). "
         "Checkpoints `data/ck_{G0,G1}_{g3,g4}.pt` (gitignored); TEST scores "
         "`data/scores_{G0,G1}.npz` feed the Stage-6 offline gate._\n")
L.append("## Notes\n")
L.append("- B5 (the flat-MLP baseline) reproduced AUROC(pos_medium) ≈ 0.79 on val/test "
         "(prior pilot ~0.78) — see `FGSR_BASELINES.md`. G0 (its strict superset) and G1 are "
         "compared against it AND against B3 `low_top2gap` in `FGSR_OFFLINE_RESULTS.md`.")
L.append("- If a model's G3 train AUROC is ≲ 0.5 it failed to fit (implementation bug, not a "
         "null result); if val ≫ test, overfit. See the offline gate for the held-out verdict.")
(OUT / "FGSR_TRAINING.md").write_text("\n".join(L) + "\n")
print("wrote", OUT / "FGSR_TRAINING.md")
