# Deeper-Search Ruler / Teacher Probe — Report

**Status: IN PROGRESS (2026-06-24)** · branch `deeper-search-ruler` · **no promotion, PRODUCTION.yaml untouched, v2.7 frozen, v2.8 opt-in.**

Question: does deeper heuristic search under the **same v2.8 leaf** (v2.7 + flat `meeple_k=2`)
produce a meaningfully stronger ruler than `heur@3200_v2.8`, and does it reveal actionable
teacher signal? Prior (held going in): h3200_v2.8 may already be near saturation; if h6400/h12800
finds *stable* improvements — especially in late_mid/pre_endgame — that becomes the best teacher
signal. Do not oversell score-margin-only gains as champion strength.

## Method & provenance (constraints honored)

- **Leaf:** v2.8 = v2.7 base (`CARCASSONNE_V25_CAP=12`, `DROP_THREE_OPEN=1`, `USE_FLAT_LEAF=1`,
  `VALUE_BLEND=0`, set at `eval_hybrid_handoff.py` import) **+ flat `meeple_k=2.0`** (`--meeple-k-a/-b 2.0`
  → `LeafConfig.meeple_k`, the flat term at `virtual_score_v2.py:574`). v2.7 is the `meeple_k=0` default,
  untouched and bit-identical.
- **Agents:** `heur@N_v2.8` = `HeuristicMCTS(simulations=N, heur_leaf="v2_7", leaf_cfg=meeple_k2.0)`.
  Pure heuristic MCTS — **no net, no orchestrator** (HeuristicMCTS never calls the net), so the ladder
  is plain CPU multiprocessing. `RoD_iter_01` / `iter_08` = `NeuralMCTS` (sims=200, c_puct=3.0,
  residual_scale=0.25, v2.8 value leaf) — orch-served for the learned-vs-ruler legs.
- **Eval:** `scripts/level2/eval_hybrid_handoff.py`, **paired decks (same deck both seats), both seats**.
  Reported per matchup: WDL, winrate, **winrate Elo** ±1σ + winrate-z, **deck-paired seat-balanced
  score margin** + **paired_z** (these two are distinct — see `_paired_z`), n paired decks, n deck-hashes,
  runtime. n=20/100 are screens, **never verdicts** (n=400 paired ≈ ±12 elo; margin paired_z is the
  powered statistic).
- **Checkpoints (sha256):** RoD_iter_01 `a8b824df0786284c` (`rod_v28_continuation/ckpt/iter_01.pt`),
  iter_08 `5843b3cf0d172f73` (`rod_v28_overnight_flywheel/ckpt/iter_08.pt`), iter8 v2.8 parent
  `0d355002e26a968e`.
- **Seeds:** h6400-vs-h3200 `1924100000`; h12800-vs-h6400 `1924200000`; RoD1-vs-h6400 `1924300000`;
  root-audit suite band `1925000000` (greedy `replay_to`, agent-unbiased, fixed once written).

## Prior context (reconciliation — results-discipline)

No prior **heur@6400-vs-heur@3200** or **heur@12800-vs-heur@6400** direct head-to-head exists in
`experiments/results.csv` (grep clean) — this is the first direct heur-vs-heur depth ladder at these
depths. Adjacent priors that set the expectation (all argue toward saturation, hence the conservative prior):

- **`heurdepth_augoff_*` (2026-06-11):** heur depth 200→800 (v2.7) "**DOES NOT MATTER** for this net —
  v2.7 leaf dominates move choice; tree sims are 2nd-order" (curve flat within noise). Caveat: net-vs-heur,
  and **net-dependent** (iter_11 *did* drift 74%@200→58%@800). Not a heur-vs-heur statement, and only to h800.
- **`odometer_residual_*` (2026-06-07):** against heur@3200 (16× deeper) a leaf correction **washes out** —
  "against a vastly deeper searcher a small leaf correction stops mattering." So h3200 is already "deep".
- **DECISIONS 2026-06-09 (iter_08 autopsy) + 2026-06-24 (exact-endgame verdict):** both explicitly name
  "**h6400/h12800 as a non-saturated ruler**" as the recommended follow-on. This branch executes that.
- **Midgame reference probe (2026-06-21):** static v2.7 explains the deep teacher (Kendall τ **+0.61**);
  where v2.7 errs, the fix is **deeper search** (heur@800 recovers ~47% of iter8's misses), not a feature —
  ~90% of disagreements are structural/positional. Directly relevant to Part D/E.

So the prior is: the v2.7/v2.8 leaf dominates move selection and tree sims are second-order by ~h3200 →
**h6400 ≈ h3200 (saturation) is the expected outcome**; a *stable* h6400/h12800-over-h3200 signal in
late_mid/pre_endgame would be the surprise worth distilling.

---

## Part A — Runtime feasibility

Measured on the local box (5900XT, 16C/32T), net-on-CPU, `OMP_NUM_THREADS=1`, paired both-seats.
heur-vs-heur is **RAM-light** (each worker holds one search tree ≤ N nodes, cleared per move;
~0.6–0.7 GB/worker baseline = torch import) and has **zero timeouts** (heuristic search never times out).

| matchup | s/game mean | median | p95 | max | moves/game | RAM/worker | crashes/OOM/timeout |
|---|---|---|---|---|---|---|---|
| **heur@6400 vs heur@3200** | **480** | 475 | 521 | 521 | 144 | ~0.65 GB | 0 / 0 / 0 |
| heur@12800 vs heur@6400 | ~960 (proj.)¹ | — | — | — | 144 | ~0.7 GB | 0 / 0 / 0 |

¹ Projected from the per-move cost (a heur@N move ≈ N·~0.3 ms incl. tree + leaf; the deeper agent does
half the moves): h6400-move ≈ 4.4 s, h3200-move ≈ 2.2 s, h12800-move ≈ 8.8 s. **Confirmed value folded in
from the local h12800-vs-h6400 run below.** (The laptop was intended to run this leg in parallel but its
WSL distro could not hold a >5-min detached job — see "Box note".)

**Projected wall-clock (16 W local):**

| matchup | n=100 | n=400 | n=800 |
|---|---|---|---|
| h6400 vs h3200 (480 s/game) | ~50 min | ~3.2 h | ~6.4 h |
| h12800 vs h6400 (~960 s/game) | ~100 min | ~6.7 h | — |

**Verdict on feasibility:** h6400-vs-h3200 to **n=400** is affordable (~3.2 h). h12800-vs-h6400 is
affordable as a **screen (n≈100, ~100 min)**; full n=400 (~6.7 h) is not worth it unless h6400 clearly
un-saturates h3200. The root-audit (Part D) runs a *single* search per position so h12800 there is cheap
(~8.8 s/position × 1620 = one ~25-min column at full width). **No exact-solver-style RAM blowup** here:
heuristic trees are tiny, so worker count is core-bound, not RAM-bound.

**Box note (laptop):** the laptop (24T, 11 GB WSL) was meant to run h12800 in parallel. Four detach
methods (`setsid &`, foreground-over-bg-ssh, `tmux`, Windows `start /b`) all died within ~5–8 min: the
WSL **distro tears down once the launching ssh session ends** (the documented "VM not held" flapping;
its keepalive is not holding). Not fixable without Windows-side admin, so this campaign ran **local-only**.
Local is in fact *faster* per game for h12800 (16 W vs the laptop's RAM-capped 10 W), so the only loss
was parallelism, not capability.

---

## Part B — Ruler ladder (full-game)

_[PENDING — local h6400-vs-h3200 n=400 + h12800-vs-h6400 n=100 running. Table to be filled from
`scripts/deeper_search/analyze_ladder.py`.]_

| matchup | n | W/D/L | winrate | winrate-z | Elo ±1σ | paired margin | paired_z | n_pair | s/game |
|---|---|---|---|---|---|---|---|---|---|
| heur@6400 vs heur@3200 | — | — | — | — | — | — | — | — | — |
| heur@12800 vs heur@6400 | — | — | — | — | — | — | — | — | — |

Interpretation rubric (from the spec): h6400 ≫ h3200 → h3200 not saturated, h6400 is the new ruler;
h6400 ≈ h3200 → search saturated near h3200; deeper wins margin but not games → "sharper ruler, not a
stronger match agent" (the exact-endgame pattern).

---

## Part C — Learned agents vs the deeper ruler

_[PENDING — RoD_iter_01 vs heur@6400 n=200 (orch, high-W); iter_08 optional.]_
Key question: did RoD_iter_01 merely reach h3200 parity, or does it also hold against h6400?

---

## Part D — Root-action deeper-search audit

Suite: **1620 positions**, greedy `replay_to` (agent-unbiased), TILES-phase, spanning the whole game by
k_remaining: endgame 450 / pre_endgame 360 / late_mid 270 / midgame 270 / opening 270. Each audited by
h3200/h6400/h12800/RoD1 → root choice (`best_action`, = what it plays), top visit-share, top-k, visit
entropy, value. _[Agreement matrices + choice-chain stability PENDING from `analyze_root_audit.py`.]_

Note: the greedy generator **does not place farmers** (greedy maximizes immediate score), so the
"farm-heavy" slice is not represented — same limitation as the l23 suite. Phase / legal-count /
meeple-pressure / score-state slices are well covered.

---

## Part E — Mechanism classification

_[PENDING — 50–100 high-confidence h12800/h6400-over-h3200 disagreements, prioritised late_mid/pre_endgame.]_

---

## Part F — Teacher / distillation feasibility

_[PENDING — conditioned on Parts B/D.]_

---

## Part G — Decision output (brutally honest verdict)

_[PENDING.]_

---

## Executive summary (10 lines)

_[PENDING.]_
