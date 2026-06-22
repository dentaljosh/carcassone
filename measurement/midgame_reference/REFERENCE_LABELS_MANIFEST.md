# Phase 3 — Reference Labels Manifest

> **No exact solver at midgame K.** These are separately-kept reference labels; **none is
> ground truth.** All search descends the **real fixed deck order** → clairvoyant-leaning
> (flagged `clairvoyance: real_deck_order` on every row). Strongest practical ruler =
> heur@3200; `teacher_gap_q` (best−2nd mover-Q at the root) is its confidence.

- built_by: `scripts/midgame_reference/label_midgame.py`  ·  ckpt: `/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt`
- positions labelled: **1000**  ·  errors: 0  ·  wall: 7.2 min @ W=14
- by band: {'opening': 200, 'early_mid': 200, 'mid': 200, 'late_mid': 200, 'pre_endgame': 200}

## Label kinds (kept distinct)

| label | source | semantics |
|---|---|---|
| `heur800/1600/3200_choice` | HeuristicMCTS v2.7 leaf, incremental same-seed tree | deep-search TEACHER root choice at each budget |
| `heur3200_child_q` / `_visits` | heur@3200 root | mover-perspective Q + visit counts per legal action |
| `teacher_gap_q` | heur@3200 | best−2nd mover-Q = teacher confidence (None if <2 children) |
| `shallow_deep_agree` / `ladder_agree` | heur 800 vs 3200 / all three | does deeper search change the pick |
| `iter8_choice` | NeuralMCTS@200, c_puct=3.0, residual_scale=0.25 | production AGENT choice |
| `iter8_prior_argmax` | net policy head, 1 forward | raw learned-policy choice (no search) |
| `v27_static_choice` | argmax virtual_score_v2 over legal afterstates | STATIC depth-0 heuristic |

## Headline agreements (FACT)

- iter8 (MCTS@200) vs heur@3200 teacher: **0.487** top-1 agreement
- v2.7-static vs heur@3200 teacher: **0.480**
- iter8 policy-prior vs iter8 MCTS@200 (search adds how much): **0.266** agree
- shallow (heur@800) vs deep (heur@3200) agree: **0.658** (1−this = deeper search flips the pick)

Interpretation lives in MIDGAME_BASELINE_RESULTS.md / MIDGAME_REFERENCE_REPORT.md; this file is FACT only.
