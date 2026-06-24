# Strategic-behavior MOTIF definitions (frozen)

Operational, computable definitions for the pseudo-human ladder benchmark.
Detector code: [`scripts/strategic_ladder/motifs.py`](../../scripts/strategic_ladder/motifs.py).
Thresholds were tuned on a DEV seed band (greedy self-play, 1930xxx) and FROZEN
before the held-out audit. **Diagnostic only — not a training target, not a champion crown.**

## Design invariants

- **Structural, not score-based.** Opportunity + satisfying-action sets come from the
  flat_leaf board decomposition (feature components, ownership majority, completion
  distance, farm→city adjacency), **not** from any agent's value function. The v2.7
  closure schedule `{1:0.5, 2:0.2}` is used only as a labeled `P(close)` model. We do
  **not** gate "took the motif" on agreeing with the v2.7 leaf score — that would let
  heuristic agents win by construction (they search exactly that leaf).
- **Agent-independent labeling.** `label_position()` is computed once per position;
  agents' chosen actions are harvested separately and joined. `took` ⇔ chosen action ∈
  `satisfying`; `missed` ⇔ opportunity existed and choice ∉ `satisfying`.
- **Residual circularity (acknowledged).** Structural motifs still correlate with what
  v2.7 values. The diagnostic question is whether the NEURAL agent (RoD1) matches the
  heuristic agents, and whether strong agents punish weak-CREATED opportunities more
  than strong-created ones — not whether heuristics score high (they will).

## Fidelity tiers (honest)

| tier | motifs | why |
|---|---|---|
| **structural / credible** | `farm_claim`, `farm_denial`, `contest` | clean ownership-flip detection; survives turn-end (farms never auto-complete) |
| **equity-proxy / low-fidelity** | `block`, `avoid_feeding` | a placed tile rarely interacts with the opponent's feature; real blocking is meeple/tile *denial*, invisible as a board delta. Cities only (decomposition exposes no road completion-distance). |
| **descriptive only** | meeple liquidity / lock | reported as state statistics, not a take-rate motif |
| **separate solver slice** | pre-endgame conversion | exact-K labels, small set, RAM-bound — its own dataset |

## Definitions

All on a position with `mover = state.current_player`, `opp = 1-mover`.
`P(close)`: open_n 1 → 0.5, 2 → 0.2, else 0. City value = closure delta (== points if it closed).
Farm projected value = `3 × (#adjacent city components)`; farm realized = `3 × (#finished adjacent cities)`.

### 1. `block` — deny opponent completion equity  (TILES phase, equity-proxy)
- **opportunity**: opp holds majority/tie on ≥1 OPEN city with open_n ≤ 2, total opp
  completion-equity (`Σ value·P(close)`) ≥ **4.0**, AND the placement choice is
  consequential — the swing across legal placements (max−min opp completion-equity) ≥ **2.0**.
- **satisfying**: legal tile placements achieving the **minimum** opp completion-equity (strict arg-min).
- magnitude = the swing (pts of opp equity denied).

### 2. `avoid_feeding` — don't hand the opponent equity  (TILES phase, equity-proxy)
- **opportunity**: a consequential feeding move exists — swing in opp completion-equity ≥ **2.0**.
- **satisfying**: strict arg-min (placements that hand the opponent the least).
- *Caveat*: base rate is high (most positions have few feeding moves). Discriminating
  power is in the SQUEEZE subset (satisfying-set small, sat_n ≤ 3) — reported separately.

### 3. `farm_claim` — claim a high-value field  (MEEPLES phase, structural)
- **opportunity**: a legal FARMER placement makes the mover SOLE owner of a field with
  projected value ≥ **6** (touches ≥ 2 city components) that the mover did not already own.
- **satisfying**: those farmer placements.
- magnitude = projected value; detail records `finished_adj` (grounded vs speculative)
  and `adj_n`. **Outcome-sanity (Part F.3) conditions on `finished_adj` and phase** — an
  opening claim with finished_adj=0 is speculative and may not be good play.

### 4. `farm_denial` — contest the opponent's field  (MEEPLES phase, structural)
- **opportunity**: a legal FARMER placement moves an opp-SOLE field (projected ≥ **6**) to a
  tie (or take) for the mover.
- **satisfying**: those placements. magnitude = projected value denied.

### 5. `contest` — share an opponent's open feature  (MEEPLES phase, structural)
- **opportunity**: a legal meeple placement makes the mover a co-owner of an OPEN city
  currently opp-sole, value ≥ **4**.
- **satisfying**: those placements.

### 6. `punish_weak` — NOT a separate detector
- The capture motifs (`block`, `farm_claim`, `farm_denial`, `contest`) measured in the
  **strong-vs-weak** regime, where the weak bot exposed the chance. Compared against the
  same agent's take rate in **strong-vs-strong**. Cross-opponent generalization (Part F.4).

### 7. meeple liquidity / lock — descriptive
- Fraction of decisions in low-free-meeple states (≤ 1 free), placed/free ratio over the
  game, recovery after lockup. Reported as ladder statistics, not a take-rate.

### 8. pre-endgame conversion — separate exact-K slice
- For k ≤ 6 positions, the exact solver labels optimal value/action; we measure whether
  the mover's move matches optimal / improves exact convertibility. Information model
  (marginalized vs clairvoyant) is labeled. RAM-bound, local only, small N.

## Known limitations (surfaced, not hidden)

- `block`/`avoid_feeding` are equity proxies; they capture "chose the lowest-opp-equity
  placement," not literal walling. Treat as weak signals.
- Roads excluded from block (no road completion-distance in the decomposition); low loss
  (roads are low value).
- `farm_claim` projected value is optimistic (assumes adjacent cities complete) — the
  speculative-opening subset is the benchmax trap; gated by outcome-sanity.
- `farm_denial`/`contest` are rare events → limited statistical power; reported with n.
