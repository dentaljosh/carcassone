# F6 (strategy-scan) win-prob pre-gate — does margin-vs-P(win) conditioning ever bind?

> **⚠️ STATUS 2026-08-14 — COMPLETE. DESCRIPTIVE INSTRUMENT, 0 GAMES PLAYED.**
> No `experiments/results.csv` row, no band claim, no claim id — house
> precedent: [j13 pre-gate](../j13_pregate_20260813/READOUT.md), farm-war,
> adaptive-k census. `governance/PRODUCTION.yaml` untouched.
> **Pre-registered branch `K` fired (dies free): binding rate 0/673, CI95
> upper 0.55%.** Forms (a) and (b) of [DESIGN.md](DESIGN.md) §1 are
> **KILLED-FREE**; form (c) (win-objective exact-K solver) is untouched by this
> result and stays in its existing roadmap slot (Track E, E1).
> Machine-readable numbers: [VERDICT.json](VERDICT.json). Instrument:
> [`scripts/analyzer/f6_winprob_pregate.py`](../../scripts/analyzer/f6_winprob_pregate.py)
> · tests: [`tests/test_f6_winprob_pregate.py`](../../tests/test_f6_winprob_pregate.py)
> (14, green). The read-rule was committed before any number was read
> (`aff9a7e7`, then instrument `13586209`, then this read-out).

## What was asked

Scan finding **F6** ([PRO_STRATEGY_SCAN_2026-08-12](../../docs/research/PRO_STRATEGY_SCAN_2026-08-12.md)):
a leader should play low-variance, a trailer should seek variance — and the
champion's leaf maximizes expected margin with no score-differential
conditioning at all. The scan called the axis NEW. The
[DESIGN.md](DESIGN.md) §0 collision audit corrected that: the **static** form
(sharpen the value squash toward P(win)) is the twice-killed winshape /
`value_norm` arc, and the **endgame** form is roadmap E1
(indexed-and-unstarted; the rust solver verifiably maximizes margin —
`endgame/mod.rs` lines 13–20). What remained genuinely open is
**state-conditioned risk posture**, and the pre-gate question is whether the
margin-vs-win distinction ever *binds* where decisions are actually close.

The measurable channel (DESIGN §2): two margin-near-tied moves can split
differently between **banked** points (realized, variance-free) and
**prospective** credit (anticipated, convertible or not) — the "safe −5 vs
volatile −5" distinction. If realized outcomes price prospective points below
banked points, margin-tied arms with different splits differ in P(win).

## What it cannot tell you — read this before quoting a number

1. **P(win) is "under champion self-play continuation"** (both seats are the
   champion, `walled` epoch). Conversion rates against a human differ; the E4
   corpus was deliberately not graded (no `fixed_v1` calibration corpus; 23
   games cannot fit a stable logistic; cross-epoch grading would manufacture a
   number).
2. **M2 is a 2-feature logistic** — it prices the banked/prospective split
   only. A zero here kills the *cheap measurable* forms of F6-conditioning,
   not every conceivable variance feature (e.g. contested-feature structure is
   invisible to it). But note §3: the zero is structural (no exposure), not a
   model-power artifact.
3. **No search in the loop** — arms are priced at chained depth 1. Irrelevant
   to this verdict's direction: search could only *shrink* a binding gap, and
   the gap is already zero.
4. **The late bucket overlaps the exact-K≤2 latch** where play is
   solver-exact; anything about the last two tiles is E1's (form (c)'s)
   question, which this instrument does not adjudicate.
5. **The near-tie bank is tile-placement decisions** (the tile-tie corpus).
   Meeple-decision near-ties were not censused here; nothing in this readout
   speaks to them.

## Integrity

| check | result |
|---|---|
| calibration games replayed | **449/449**, final scores bit-match the recorded `score_p0/p1` |
| calibration rows | 64,656 (TILES plies × both POVs) |
| bank positions replayed | **673/673** checksum-verified (`walled`/selfplay stratum) |
| champion picks joined | 673/673 (full-champion 8×1376 rust picks) |
| leaf | `a36d2e15a3b3d71d` (leaf of record, hash-asserted at build) |
| cost | 22.3 s wall at W8, local CPU, 0 games |

## 1. The outcome models (Stage 2)

Both-POV logistic fits, game-clustered bootstrap (B=500), pre-registered
buckets on tiles-remaining (late ≤12, mid 13–36, early ≥37):

| bucket | n rows | β_banked | β_prosp | **β₂/β₁** | CI95 |
|---|---:|---:|---:|---:|---|
| late | 10,776 | 0.1466 | 0.1346 | **0.918** | [0.801, 1.050] |
| mid | 21,552 | 0.0773 | 0.0601 | **0.777** | [0.581, 1.000] |
| early | 32,328 | 0.0430 | 0.0472 | 1.097 | [0.665, 1.753] |
| pooled mid+late | | | | **0.848** | **[0.713, 1.002]** |

The discount channel **leans real but does not resolve**: a prospective point
converts to win-probability at ~85% of a banked point's rate mid/late, but the
95% CI touches 1.0. Even had it resolved, it would not have rescued the lever —
see below.

## 2. The binding census (Stage 3) — the read-rule statistic

673/673 positions have a margin-near-tie pair at ε=0.25 pts (the bank is a tie
bank by construction).

| cell | ε_margin | ΔP bar | binding | rate |
|---|---:|---:|---:|---:|
| **primary** | 0.25 | 0.02 | **0 / 673** | **0.0%** (CI95 ≤ 0.55%) |
| ΔP sensitivity | 0.25 | 0.05 | 0 / 673 | 0.0% |
| ε sensitivity | 1.0 | 0.02 | 0 / 673 | 0.0% |
| both | 1.0 | 0.05 | 0 / 673 | 0.0% |

Max ΔP(win) observed across all 673 positions: **0.0104**. Mean: **0.00007**.
The M1 honesty row is exactly 0.0 everywhere, as it must be (a deterministic
margin→P map cannot separate margin-ties); the entire measured effect is the
decomposition channel, and it is an order of magnitude under the bar.

**Stage 4 (champion posture) is empty by construction** — with zero binding
positions there is nothing for the champion to mis-pick. The scan's
"champion takes the lower-P(win) arm when trailing" mechanism has no
opportunity to exist at near-tie decision points in this corpus (366/673 roots
had the mover trailing, so trailing states were abundantly represented).

## 3. Why it is zero — structural, not statistical

Among margin-near-tied arms, the banked-score split differs in
**12 of 673 positions** (p50 = p90 = 0.0 pts; max 4 pts). Near-tied tile
placements almost never differ in *immediately banked* points — when two
placements score differently right now, the leaf margin separates them and
they stop being near-tied. So the "safe vs volatile same-margin choice" that
F6's risk posture would arbitrate essentially **does not occur** at close tile
decisions: the exposure is absent, independent of how large the
banked/prospective conversion discount turns out to be. A conditioning term
with no exposure has nothing to move.

## Honest read + verdict

**Pre-registered branch `K` — the lever dies free.**

* Form **(a)** (risk-sensitive utility on the banked/prospective split,
  score-diff-conditioned): **KILLED-FREE.** The decision points where it could
  act (margin-near-ties differing in split) occur at a ~1.8% rate, and even
  there the implied ΔP(win) never reaches 0.02. Ceiling on the whole form:
  under any plausible conversion discount, ≤ ~0.01 win-prob per affected
  decision × ~0 affected decisions per game.
* Form **(b)** (phase/score-dependent value squash): already carried an
  unfavorable double kill (winshape T∈{4,12}, `value_norm` {8,15,30}); this
  pre-gate adds that the state-conditioned rescue has no exposure to work
  with. **Do not fund.**
* Form **(c)** (win-objective exact-K solver = roadmap **E1**): **untouched by
  this verdict** — the last-2-tiles regime is the one place margin/win
  divergence is a solver-objective question rather than a leaf question, and
  this instrument deliberately does not adjudicate it. E1 keeps its queue slot
  on its own merits; nothing here funds or kills it.

**Re-open bars (any one):** a corpus where near-tied decisions *do* differ in
banked/prospective split at a material rate (e.g. a meeple-decision near-tie
census, which this bank does not cover); or a variance feature beyond the
banked/prospective split shown to separate margin-tied siblings with
|ΔP| ≥ 0.02; or human-opponent (E4 `fixed_v1`) calibration once enough games
exist to fit — with the caveat that all three re-open the *instrumented
question*, not the killed winshape family.

**Do not re-derive the numbers** — [VERDICT.json](VERDICT.json) carries every
statistic above plus the raw per-row records under `raw/`.
