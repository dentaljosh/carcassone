# Path B — turning the value-bootstrap back on (KataGo-style)

> **Durable handoff doc.** Written 2026-05-29 right before a context compaction.
> A post-compaction Claude (or fresh thread) should be able to execute this
> step-by-step. Read [CLAUDE.md](../CLAUDE.md) → [STATUS.md](../STATUS.md) →
> this file. Live progress tracker mirrors these steps in the TodoWrite list.

## Why this exists (one paragraph)

Goal changed 2026-05-28: **genuinely superhuman play** (beat the world champ).
The blocker is structural: our strength is PUCT search over a **hand-crafted**
leaf (`virtual_score`/v2.7), which caps learned play near strong-human by
construction. Real AlphaZero's S-curve comes from a **value↔policy bootstrap**
fueled by a *learned* value trained on real outcomes — we disabled half of it
(Option 2, the NN-value leaf, was *worse* than the heuristic and got closed
2026-05-18, because the value head was data-starved). **KataGo's contribution
was making a learned value viable at far less compute** via richer inputs +
richer learned targets. Path B re-runs the Option-2 test, but this time with the
KataGo machinery that was missing. See [DECISIONS.md](../DECISIONS.md) 2026-05-28.

## The one question this answers (go/no-go)

> **Can a learned value head — given KataGo-style help (aux heads + domain input
> planes) — beat the v2.7 heuristic leaf head-to-head?**

If **GO** → the bootstrap can turn; commit to scaling (more iters, reference
ladder, Optuna-over-recipe). If **NO-GO** → architecture isn't enough at our
scale; superhuman is likely out of reach on this hardware (honest stop, or seek
more compute).

**The decisive test is cheap because the harness already exists.** Option 2
wired the "use NN value as the leaf" path (`LeafConfig.value_blend`, the
eval-server `compute_value` path). So the go/no-go is a leaf-swap A/B we can
already run:

> Same policy net both sides, sims=200, **n=400**: `(NN-value-as-leaf)` vs
> `(v2.7-heuristic-leaf)`. **GO if NN-value-leaf wins by > +15 elo** (n=400,
> 1σ≈±9, so +15 ≈ 1.7σ). NO-GO if ≤ 0 or within noise.

We don't build the test — we build a value head *worth* testing.

## Diagnostic gate — so a NO-GO is credible, not a tuning artifact

A bare negative A/B is ambiguous: did the architecture fail, or did we freeze a
bad knob? We resolve this by measuring the value head's quality **independent of
the head-to-head**, which turns "negative" into "negative *with a mechanism*."

**The orthogonal signal: value↔outcome correlation.** The Option-2 post-mortem
(2026-05-18) measured the old NN value head at **corr +0.18** with the game
outcome vs the heuristic's **+0.61** (STATUS.md / DECISIONS.md). That **+0.61 is
the baseline to beat.** After Path B training — and BEFORE trusting the A/B elo —
measure the learned value's correlation (and held-out value MSE vs the
heuristic's) on a sample of self-play games:

| value-corr vs 0.61 | A/B elo | reading |
|---|---|---|
| still ~0.2–0.3 | loses | **real NO-GO** — a value head that can't predict outcomes can't be rescued by any eval-side knob. Architecture/data is the wall. Credible stop. |
| ~0.55–0.65 | loses | failure is **integration/eval-side** (leaf-swap blend, search `c`), NOT the value head — a fixable, knob-shaped result. Look there before declaring NO-GO. |
| aux losses flat in training | — | labels are garbage (the Step 1 farm-ownership linchpin), not a tuning problem. |

**Confound insurance on the one genuinely-new knob (aux-weight).** The frozen
knobs split two ways: *inherited + validated* (sims / c_puct / dirichlet / temp /
value_target / epochs / games — the exact iter_01/B1 recipe, so NOT suspects if
the probe fails) and *genuinely-new* (aux-weight, domain planes, head arch). Only
aux-weight is a free scalar worth pre-checking, and it's cheap at warmstart (no
self-play loop): train warmstart at aux-weight **{0.0, 0.15, 0.5}** and confirm
(a) the policy/value mains don't degrade as the weight rises and (b) the aux heads
actually learn. If 0.15 looks clean there, freezing it for the loop is
*justified*, not assumed. Folded into Step 6.

## Frozen hyperparameters (decide once, HOLD — do not tweak mid-run)

The discipline (CLAUDE.md "Results discipline"): pick these up front, freeze them,
read the result. Most are NEW (not in results.csv — that's eval-side knobs only).

| knob | value | source / rationale |
|---|---|---|
| trunk | **6×96 ResNet (unchanged)** | bigger net only helps if signal uses it; the aux heads + domain planes ARE the signal change. Widen later only if GO. |
| aux-loss weight | **0.15 each** | KataGo-style: small enough to regularize, not dominate the policy/value mains. |
| self-play sims | **200** | this probe is about the value head, not search depth. Fast. (sims=800 is a separate lever.) |
| self-play c_puct | **1.5** | long-standing default; Dirichlet+temp drive early exploration so c matters little here. **If tonight's hygiene run resurrects c=3, optionally use 3.0 — not critical.** |
| dirichlet α / eps | **0.3 / 0.25** | match current production. |
| temp_threshold | **15** | match current. |
| value_target | **score_diff** | already default; aligns with the score-margin aux head. |
| train epochs / warmstart-mix | **3 / 0.0** | mirror iter_01/B1 (warmstart-mix 0 after the initial warmstart). |
| self-play games/iter | **1200** | matches the v25 retrain line. |

## Deterministic gates (baked into the loop — NOT human check-ins)

The self-play loop runs unattended; these are guardrails that halt+report:
- **NaN/inf loss** in any epoch → abort iter, report.
- **Policy-entropy floor**: if mean policy entropy drops below ~0.5× the
  warmstart net's initial entropy → collapse, abort+report.
- **Anchor-gate per iter** (already the pattern in `eval_iter_head_to_head.py`):
  auto-play iter_N vs previous-best at **n=100, sims=200**; promote iter_N as new
  best only if elo_delta > 0. **Stop the loop after 2 consecutive non-positive
  iters** (the iter_02-flatline detection — saturation reached).
- Human re-engages ONLY on a gate trip or at the final go/no-go A/B.

## Build steps — the TODO (ordered; aux-targets first = correctness linchpin)

> Per-step **dev** estimates are aggressive (Joshua's bet: the dev is hours, not
> a week — the multi-day part is detached *compute*, not attention). Verify each
> file's current signature when implementing — do not trust line numbers from
> memory.

### Step 1 — Aux-target generation + validation  (THE LINCHPIN, ~2-4h dev)
- Compute, at each self-play game's terminal state, the labels the aux heads will
  learn: **(a) feature ownership** (who controls each city/road/farm at game-end),
  **(b) final score-margin** (have via score_diff — extend/confirm), **(c)
  closure-timing** (tiles-remaining when each open feature closed).
- The engine already computes final scores → ownership is derivable. **Farm
  ownership is the risky part** (long-range, the engine's most-likely-buggy area).
- **VALIDATE before training**: on a sample of games, assert the ownership labels
  reconcile with the engine's final scorer. A wrong label teaches the aux head
  garbage. This validation gate is non-negotiable.
- Add the new label arrays to the `.npz` schema (alongside boards/scalars/
  policies/players/valid_masks). Touch: `selfplay.py` (emit), `warmstart.py`
  (`GameDataset` load), the warmstart label generator.

### Step 2 — Domain input planes  (~1-2h dev)
- Add broadcast/scalar input planes in `board_repr.py`: `tiles_remaining`,
  `my_meeples_in_hand`, `opp_meeples_in_hand`, `is_endgame`, `contested_features`,
  `my_dominant_farms`. These are reasoning *inputs* (net decides how to use them),
  NOT frozen verdicts.
- Changes net input channel count → breaks checkpoint compat → fresh warmstart
  required (expected; we're doing one anyway).

### Step 3 — Auxiliary heads + losses  (~2-3h dev)
- In `network.py` (`CarcassonneNet`): add output heads for ownership / score /
  closure-timing predictions. Add their losses to the training objective at
  weight 0.15 each (mains: policy CE + value MSE unchanged).
- Touch `train_iter.py` (loss assembly) + `train_warmstart.py`.

### Step 4 — Bundle deferred feature fixes D1/D13  (~30min dev)
- From REVIEW_LOG.md: D13 (`features.py` `tiles_remaining` off-by-one), D1
  (`board_repr.py` ref-tile TILES-vs-MEEPLES encoding inconsistency). Free riders
  on the fresh-warmstart boundary. Decide D1: unify or keep+document.

### Step 5 — Warmstart pipeline update  (~1h dev)
- Regenerate the warmstart targets to include the new aux labels + new input
  shape. The existing heuristic-labeled warmstart corpus is the base.

### Step 6 — TINY-SCALE SMOKE (de-risks the whole run; ~30min + short compute)
- Run the FULL pipeline at toy scale: new-arch warmstart (small) → 1 short
  self-play iter (e.g. 25 games, sims=25) → train → anchor-gate. Assert: no NaN,
  aux losses decrease, anchor-gate runs, the value-leaf swap works. **This catches
  a bug before it eats days of compute.** Do not skip.
- **Aux-weight sensitivity (confound insurance — see "Diagnostic gate"):** run the
  small warmstart at aux-weight **{0.0, 0.15, 0.5}**; confirm the mains don't
  degrade as weight rises and the aux losses fall. Justifies freezing 0.15 for the
  loop instead of assuming it. Cheap here (warmstart only, no self-play).

### Step 7 — Launch warmstart  (compute: ~hours, detached, ask which box)
- Full warmstart of the new arch from heuristic-labeled data. nice -19, detached.

### Step 8 — Launch the self-play loop  (compute: ~days, detached, gates baked in)
- `run_selfplay_iter.py` → `train_iter.py` → anchor-gate, looped, **knobs frozen
  per the table above**, deterministic gates per the section above. Work-stealing
  across the cluster (5800X+Xeon+laptop). Launch once; walk away.

### Step 9 — The decisive go/no-go A/B  (compute: ~hours)
- `(NN-value-leaf)` vs `(v2.7-heuristic-leaf)`, same policy net both sides,
  sims=200, n=400, via the existing `value_blend` leaf-swap. GO if > +15 elo.
- **Report value↔outcome correlation alongside the elo (see "Diagnostic gate").**
  The elo is the headline; the corr is the *attribution*. A NO-GO is only credible
  paired with its mechanism — corr < 0.61 → real architecture wall; corr ≥ 0.61
  but elo loses → the failure is eval-side, look there before stopping.
- Append the result to `experiments/results.csv` (and write a manifest — see
  "results discipline" / the deferred manifest root-cause fix).

## What's already built (reuse — don't rebuild)
- Warmstart pipeline (`warmstart.py`, `train_warmstart.py`).
- Self-play loop + anchor-gate (`run_selfplay_iter.py`, `train_iter.py`,
  `eval_iter_head_to_head.py`) incl. work-stealing (`--shared-claim`).
- **The NN-value-as-leaf swap** (`LeafConfig.value_blend`, eval-server
  `compute_value`) — the go/no-go harness.
- `score_diff` value targets (the baby score-margin aux head).

## Risks
- **Aux-target correctness for farms** (Step 1) — the linchpin. Validate labels
  vs the engine scorer before training, or the aux head learns garbage.
- **Warmstart bias**: warm-starting the value head from heuristic labels biases
  it toward the heuristic. Mitigate by weighting self-play *outcomes* over
  heuristic labels for the value target during the loop.
- **Bigger/slower net** from new heads+planes — bench inference cost; if it
  meaningfully slows self-play, that's a cost input, not a blocker.

## Measurement note
The go/no-go A/B (Step 9) is self-contained — it does NOT need the strong
reference ladder. But measuring ABSOLUTE progress toward superhuman (after a GO)
DOES require the ladder (Tier-1 is saturated; self-anchored elo can lie). So:
reference ladder is the parallel/next workstream once Step 9 returns GO.
