# High-Contrast Decision-Signal Distillation — Dataset

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.**
Plan: [HIGH_GAP_PLAN.md](HIGH_GAP_PLAN.md) · Gate: [HIGH_GAP_SIGNAL_DENSITY.md](HIGH_GAP_SIGNAL_DENSITY.md).

## Stage 1 — pilot candidate pool (the signal-density gate runs on this)

Per the cheapest-informative-first rule, the pilot **reuses the existing replay-verified multiphase
pool** rather than generating fresh roots. Generation is deferred until the gate (Stage 2) shows the
high-gap, student-wrong signal density justifies a 25k–100k mine.

| property | value |
|---|---|
| source file | `measurement/deeper_search_ruler/multiphase_positions.jsonl` |
| roots | 1620 |
| provenance | each root = (seed, ply, checksum); `replay_to(seed, ply)` reconstructs + checksum-verifies |
| generation | greedy self-play snapshots, spans opening → endgame |
| stored covariates | gen_id, seed, ply, phase, k_remaining, score_margin_abs, meeples_free, legal_n, meeples_placed, placed_farmers, scores, source_agent |

**Phase composition (balanced by construction):**

| phase | roots | share |
|---|--:|--:|
| endgame | 450 | 27.8% |
| pre_endgame | 360 | 22.2% |
| late_mid | 270 | 16.7% |
| midgame | 270 | 16.7% |
| opening | 270 | 16.7% |

This is a single self-play ecology (the diversity-of-source requirement — RoD1/RoD2 self-play,
h3200/h6400 games, weak-vs-strong, close-score slices — is a **scale-up** requirement, applied only
if the gate passes). For a *density estimate* (what fraction of states are high-gap AND student-wrong),
1620 cross-phase roots give a per-fraction SE ≈ √(p(1−p)/1620) ≈ ±0.7pp at p=0.1 — ample to size a mine.

## Stage 1 labeling (per root, h6400_v2.9 deep teacher)

`scripts/rod_v2/highgap/probe_signal_density.py` (net-free, CPU-parallel W=16). Per root: run
HeuristicMCTS@6400 on the frozen v2.9 leaf, extract the id-deduped root children's **adjusted Q**
(root-player perspective), and record teacher_best (Q-argmax), q_best/q_second/q_gap, the per-action
Q map, visit share, entropy + all covariates. Row-aligned npz (boards/scalars/valid_masks) lets the
analyzer forward the students without re-replaying.

Outputs: `qprobe/probe.jsonl` (per-root Q + metadata) · `qprobe/data/iter_00/seed_*.npz` (encode).

## Stage 3 — splits (scale-up only; pending gate)

Defined but **not built** until the gate passes. Tiers: **A** strong (gap or regret ≥ 0.020) · **B**
medium (≥ 0.010) · **C** ordinary decisive stabiliser (anti-forgetting). Rules: no same-game leakage,
fixed split-seed, phase + source-agent preserved, separate endgame test slice; soft teacher /
advantage labels (NOT one-hot argmax). Exact counts will be filled here when Stage 3 runs.
