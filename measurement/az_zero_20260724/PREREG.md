# AZ-ZERO (tabula-rasa mini-loop) — PRE-REGISTERED READ (written 2026-07-24 ~02:00, BEFORE any curve exists)

**Question.** Every net in the kill chain (CL-039/042/064/C0) was raised inside the heuristic's
basin (warmstart labels and/or heuristic-shaped self-play). This is the first true zero-start:
random-init net, net-value + net-policy self-play, no heuristic leaf, no exact solver. It tests
the *scaffolding confound*, not a strength lever.

**Design (see DESIGN.md for the build):** 12 iters × 300 games, sims ~128, W14 nice-19 LOCAL only
(runs beside the distill gen; laptop untouched). Anchor screen every 2 iters, n=50/anchor:
- **A_rand** — random-move player
- **A_warm** — the SIGHTED same-arch warm-start `m2_sighted/warmstart_sighted.pt` net-agent at the
  SAME sims (= what heuristic scaffolding buys the SAME arch/rep; the primary comparison).
  [Amended pre-launch 2026-07-24 ~09:20, before any curve exists: DESIGN.md §4.3 flagged that the
  originally-named `warmstart_canonical.pt` is BLIND 78ch — a rep confound; same-rep anchor is the
  clean scaffolding read. Canonical stays available as a secondary via the screen's --anchor-ckpt.]

## Pre-registered read (n=50 screens: 1σ ≈ 7pp on wr; treat <±14pp moves as noise)

| verdict | criteria (all at the loop's own sims, same info regime both sides) |
|---|---|
| **ALIVE** | wr vs A_rand ≥ 0.90 by iter 4 AND a monotone-ish climb vs A_warm across iters 4→12 that closes ≥ half the iter-0 gap (or reaches wr ≥ 0.35 vs A_warm) |
| **FLATLINE** | wr vs A_warm shows no trend (±1σ band) across iters 4→12 |
| **AMBIGUOUS** | anything else — report the curve, no conclusion |

## Pre-committed interpretation bounds (written before results)
1. **FLATLINE ≠ "AZ can't play Carcassonne."** At 2-box/12-iter/7M-net scale a null is
   compute-bounded and weakly informative. It closes nothing that isn't already closed; it does
   NOT strengthen CL-039/042/064/C0 (different regime).
2. **ALIVE ≠ a strength lever.** It qualifies the kill chain's scaffolding confound and would
   motivate a scale-up *discussion* — nothing more. No promotion path from this experiment;
   champion + PRODUCTION.yaml untouched regardless of outcome.
3. The information regime of this self-play mode (does search see the true tile order? — DESIGN.md
   documents what the reused machinery does) bounds any claim: both the candidate and A_warm play
   under the SAME regime, so the curve is internally valid, but cross-regime comparisons (vs the
   fair-PIMC champion) are OUT OF SCOPE for this experiment.
4. One-shot: 12 iters, then stop. Extending the loop is a new decision (new entry), not a drift.
5. Contention guard (ops, not science): Joshua's call 2026-07-24 ("I don't mind if performance
   drops 50% from the contention") — the az_zero loop gets throttled/paused only if the distill
   gen's throughput drops **>50%** vs its pre-launch baseline (0.64–0.9 games/min band, measured
   2026-07-23/24). I'll still measure and report the actual delta after launch.
