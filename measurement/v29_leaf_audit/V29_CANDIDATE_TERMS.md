# V29_CANDIDATE_TERMS — the proposed v2.9 leaf terms

Each term is one ablatable `LeafConfig.v29_*` toggle (logic in
[src/carcassonne_ai/leaf_v29.py](../../src/carcassonne_ai/leaf_v29.py)). Default neutral ⇒ bit-identical v2.8. **Point
margin is a diagnostic; winrate is the throne** — a term ships only if it improves
paired full-game winrate vs h6400_v2.8 (or clearly improves competitive-state paired
margin without being already-won padding).

Baseline for every candidate: **v2.8** = `DEFAULT_CONFIG` (cap=12, drop-three-open) +
flat `meeple_k=2.0`.

---

## Candidate A — win-shaped utility  `v29_util_tanh_t = T`

**Failure mode addressed.** The leaf is linear expected-final-score; the consumer
already squashes it `tanh(diff/15)`, but T=15 was never swept. A linear margin term
rewards already-won padding (running up +30 when +6 already wins) and under-weights
the few points that flip a close game.

**Formula.** Final total → `T·tanh(total/T)` (point-scale preserved). Composed with
the consumer: HeuristicMCTS value = `tanh( T·tanh(diff/T) / 15 )`. T→∞ ⇒ baseline
v2.8; smaller T ⇒ large leads compress toward ±T (anti-padding), close games keep
full resolution.

**Sweep.** T ∈ {8, 12, 16, 24, 32, 48}. **Predicted sign:** intermediate T (12–24)
best — enough anti-padding to value the win without going binary. Very small T (≤8)
risks indifference between a safe win and a marginal one (loses margin resolution
search needs). **Runtime:** ~0 (one tanh per leaf); but v2.9-active forces the object
path ⇒ ~2.26× the flat-path leaf cost. **Toggle:** `v29_util_tanh_t`.

> **Mechanism note (why_decompose finding, 2026-06-25):** `T·tanh` is a *monotonic*
> transform of the leaf total, so it CANNOT change the 1-ply leaf argmax except by
> breaking v2.8's integer-rounding ties (confirmed: A16 flips only ~12% of 1-ply
> decisions, all by ±0.06–0.19 pt). **A's real effect is through MCTS *backup*** — it
> compresses the Q-values large leads contribute, changing selection/exploration over
> multiple plies. ⇒ the 1-ply `why_decompose` tool UNDERSTATES A (predictive for the
> additive terms B/D/E, not for A). Judge A only by the full-MCTS screen.

## Candidate B — nonlinear meeple liquidity  `v29_meeple_curve = (v0..v7)`

**Failure mode addressed.** Flat `meeple_k=2.0` was the ONLY survivor of the 2026-06-22
v2.8 program (+179 elo) — strong evidence meeple economy matters. But "+2 per meeple,
always" is implausible: the 7th→6th free meeple is cheap; the 1st→0th (locked out, no
plays) is a cliff. A diminishing-returns + emergency-penalty curve should price this better.

**Formula.** Replaces the flat term with `curve[m_self] − curve[m_opp]`, `curve`
indexed by free-meeple count 0..7. Two shapes:
- `Bmild`  = (−8,−4,−1, 0, 2, 3, 4, 5) — gentle diminishing returns + mild low-meeple penalty.
- `Baggr`  = (−14,−7,−3, 0, 2, 3, 3.5, 4) — hard emergency penalty at 0–1 meeples, flat top.

Controls: `Bk1` (flat k=1), `Bk3` (flat k=3) — isolates "is it the curve shape, or
just a different scalar?" **Runtime:** ~0 (two table lookups). **Toggle:** `v29_meeple_curve`.

## Candidate C — deck-aware completion probability — ❌ PRE-KILLED, NOT IMPLEMENTED

Confirmed null **twice**: DECISIONS 2026-05-17 (hard gate 45%, continuous ramp
50%/−1.4, pooled 47.5%) and the 2026-06-22 v2.8 program (endgame-local washout). The
existing `closure_continuous_slack` knob already covers it. **No compute to be spent
re-running it.** Listed only for completeness; `deck_completion_delta` is hard-0 in the
decomposition.

## Candidate D — sparse high-confidence tactical punish  `v29_punish_k`  (STUB)

**Evidence (positive, but wrong layer).** The 2026-06-25 high-precision strategic-ladder
finding: h6400 takes MUST_PUNISH_WEAK 92% vs RoD1 84%, HIGH_VALUE_FARM_CLAIM 89% vs 82%.
Real tactical gaps exist — **but they are SEARCH/POLICY gaps, not leaf gaps.** A
leaf-STATE term for "I punished a weak opponent" largely duplicates `base` (completing
a feature or claiming an exposed farm already banks points). Implemented as a 0.0 stub
with a toggle; revisit only if A/B prove the leaf has headroom, and only with an
inspectable example set first (spec Part B). **Toggle:** `v29_punish_k`.

## Candidate E — farm access / denial window  `v29_farm_access_k`  (STUB, low prior)

farm-majority-gate (broad degradation) and opp-denial (no movement) were **both killed**
in the 2026-06-22 v2.8 program. An access-WINDOW formulation (unclaimed high-value field
with legal farmer access; merge swing) is marginally different but starts from a very
negative prior. 0.0 stub + toggle; deferred behind A/B. **Toggle:** `v29_farm_access_k`.

---

## Priority (cost-disciplined)

| Cand | prior | why | wave |
|---|---|---|---|
| **B (curve)** | **high** | refines the one term that demonstrably worked (+179 elo) | 1 |
| **A (win-shape)** | **medium-high** | genuinely untested; cheap; T=15 never swept | 1 |
| C (deck-aware) | dead | null ×2 | — skip |
| D (punish) | low (wrong layer) | search gap, not leaf gap | 2 (stub) |
| E (farm denial) | low | 2 killed cousins | 2 (stub) |

First wave = A{8,12,16,24,32,48} + B{mild,aggr} + controls {k1,k3}. Combination wave
(best-A + best-B) only after individual proof.
