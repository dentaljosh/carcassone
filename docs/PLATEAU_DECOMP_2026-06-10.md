# Plateau decomposition — Track-B flywheel attempt #2 (2026-06-10)

**Question.** Attempt #2 produced a real, significant, *bounded* gain (sealed n=400, champion
iter8 vs iter0 = **+67.4 elo / z2.73**; CL-018 Supported) that **plateaued by ~iter5** (iters
6–10 all within ~1.5σ, trending mildly down). *What* plateaued? Four live hypotheses (from the
external review):

1. the **policy** absorbed the residual (gain is policy, value is along for the ride);
2. the **residual/value head** stopped improving;
3. **both** saturated at the fixed heuristic;
4. the **ruler** (heur@800-v2.7) became the binding constraint.

⚠️ The earlier "tanh-cap" mechanism is **FALSIFIED** (S-R3-1 2.6M-target scan: std 0.071, 0%
with |Δ|>1, saturation 0.013% of MSE) — do not pursue clip/linear-head. See DECISIONS 2026-06-10.

This doc is eval-only (no training). Staged cheapest-informative-first.

---

## Stage A — value-head sibling ranking (`probe_decision_ranking.py`)

Per checkpoint: harvest ~200 decision nodes from self-play, and for each node rank its sibling
moves by (a) the **raw value head** and (b) **v2.7**, scored against a **400-sim oracle** (the
deep search the head was trained to predict). Kendall-τ vs oracle; regret = oracle points lost
by following each ranker's top pick. Run across the cluster (iter8 local, iter5 laptop, iter0
laptop-wave2). Raw: `/mnt/c/carc-shared/decomp/rank_iter{0,5,8}/summary.json`.

| ckpt | τ_net (value head) | τ_v27 | top1_net | top1_v27 | regret_net (pts) | regret_v27 (pts) | n | mean_k |
|------|------|------|------|------|------|------|---|------|
| iter0 | **+0.019 ± 0.020** | +0.562 | 0.120 | 0.400 | 1.757 | 0.499 | 200 | 13.6 |
| iter5 | **−0.011 ± 0.018** | +0.554 | 0.090 | 0.390 | 1.899 | 0.548 | 200 | 13.5 |
| iter8 | **−0.011 ± 0.022** | +0.521 | 0.117 | 0.375 | 2.370 | 0.713 | 120 | 13.4 |

**Finding.** The raw value head ranks sibling moves **at chance (τ≈0) at every checkpoint and
never improves** — its regret even *rises* (1.76 → 2.37). v2.7 ranks well (τ≈+0.55) and carries
the leaf's local discrimination throughout. The flywheel did **not** make the value head a better
local evaluator. (Re-confirms the original STEP-A finding — value head at chance locally, τ≈+0.08
— and shows 8 self-play iters didn't fix it.)

**Implication (leading hypothesis).** Points to the **+67.4 gain being POLICY-driven** (better
self-play data → better priors), with the plateau being **policy/data saturation** — not the value
head, which never bootstrapped local discrimination. It also **rules out the assumed lever**: the
plateau is not a value-head capacity problem fixable by a target/activation tweak.

**⚠️ Caveat (do NOT over-read — the same trap as the withdrawn corr claim).** This probe measures
*local sibling ranking only*, not *global backup utility*. A locally-noisy value can still help
MCTS backups, so this does NOT prove the residual adds nothing to search — only nothing *locally*.
Stage B is the confirmation.

---

## Stage B — policy-only vs residual-on strength (RUNNING, ~18:00 EDT 2026-06-10)

`eval_net_vs_heuristic --residual-scale {0, 0.25}` for iter0/5/8 vs heur@800-v2.7, common fresh
band **2.0e9**, n=200 paired. local W=10 + laptop W=20, shared-claim. Out: `decomp/stageB/`.

Resolves:
- **policy-only trajectory** — does scale-0 (pure-v2.7 leaf, net priors only) strength climb
  iter0→5→8? If yes → the gain is in the **policy**.
- **residual marginal per checkpoint** — (scale0.25 − scale0) deck-paired. If flat/small and
  non-growing → the value head's *global* contribution didn't compound either.

Expected (if Stage A's lead holds): scale-0 climbs across the lineage; the marginal stays a small
near-constant (~the static CL-004 +37.6-ish, not growing). That would confirm **policy-driven,
bounded** — and point the real ceiling lever at the *policy's* data/search (deeper teacher, deck
diversity) or a genuinely different value design, NOT a residual tweak.

_(Results table appended when Stage B lands.)_

---

## Stage C — ruler test (conditional, not yet run)

Only if A+B show internal signals still moving but strength flat → champion vs a **stronger /
stylistically-different reference** (heur@3200-v2.7) to test whether heur@800-v2.7 is the binding
ruler (the v2.7-anchoring hypothesis — still untested, NOT the falsified tanh-cap).

---

## Post-Stage-B decision tree (conditional — NOT a pre-commitment to any lever)

Mapped in advance so we can move immediately when Stage B lands. Which branch fires is decided by
the data, not now.

**S1 — policy-driven, bounded** *(scale-0 strength climbs iter0→8; marginal s0.25−s0 small & flat;
consistent with Stage A).* The gain is the **policy**; the residual value is ~inert locally and
not growing. Plateau = policy/data saturation. → Skip Stage C (ruler not the issue). Candidate
levers (pick by EV, re-sweep first): **(a)** stronger self-play teacher (higher-sims targets — we
have the sims=800 deepsearch precedent); **(b)** opening/deck diversity to widen the training
distribution; **(c)** a *different value design*, since residual-as-leaf is locally inert — e.g.
direct search-Q regression with more capacity, or dropping value-as-leaf and leaning on policy +
shallow v2.7. ⚠️ grep BACKLOG/DECISIONS first — several of these were considered.

**S2 — residual contributes globally** *(s0.25 meaningfully beats s0, and/or the marginal grows
across iters).* Then Stage A's "inert" read was local-only as warned, and the value DOES help via
backups. Plateau is elsewhere → **run Stage C** (heur@3200-v2.7): champion still wins → ceiling is
higher, push harder on depth/scale; champion loses → the **ruler** (heur@800) capped the
measurement (v2.7-anchoring confirmed) → need an out-of-ecosystem reference and a non-v2.7-anchored
leaf.

**S3 — scale-0 flat across the lineage** *(policy didn't climb at the matched leaf either).* Then
neither component improved at a matched leaf, and the +67.4 sealed leaned on this band drawing iter0
low (the −8.7 anomaly vs +22.6/+52.5 elsewhere). → **re-open the magnitude**: the honest gain may be
closer to the 5v0's +40 than +67; CL-018 stays Supported (a gain exists) but its size is revised
down. Confirm with one more held-out band before any lever.
