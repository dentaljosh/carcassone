# v2.8 mechanistic autopsies

> **STATUS (2026-06-22): COMPLETE for the Phase-4 survivors (v28_completion, v28_meeple).** The two
> killed patches (v28_farm, v28_denial) get a short autopsy of *why* they failed. This layer answers
> "why does v2.7 fail / does the patch fix a real structural class," kept SEPARATE from Elo: a patch
> that gains Elo without a supported mechanism here is **"empirical gain, mechanism unclear."**
> Data: [V28_AUTOPSY_DATA.json](V28_AUTOPSY_DATA.json) (harness
> [scripts/heuristic_v28/v28_autopsy.py](../../scripts/heuristic_v28/v28_autopsy.py)).

## Conclusion vocabulary
**supported** = target subset improves + line autopsy shows the named mechanism + counterfactual holds ·
**weak** = partial · **falsified** = doesn't flip / flips for the wrong reason · **unclear** = Elo moved, mechanism unproven.

---

## v28_completion — **SUPPORTED**

- **Hypothesis (M2).** v2.7's fixed `closure_p={1:0.5,2:0.2}` over-credits closures the (near-empty,
  late-game) deck literally cannot finish. The deck-aware `supply_factor` discounts them.
- **Line autopsy (EXACT K=2 = the strong continuation IS the solver).** On the 150 exact-solved K=2
  positions, v28_completion (slack 3) flips **41** picks vs v2.7; of the fully-solver-resolved flips,
  **8 toward optimal, 0 away** (V28_AUTOPSY_DATA.json `flips_vs_v27`). **Every flip is at deck=1** —
  exactly the regime where a 2-open city cannot close, so v2.7's `0.2×delta` phantom-closure credit
  mis-ranks the move and v28_completion zeroes it. The divergence appears at **final scoring** (K=2,
  immediate): v2.7 picks a move banking a closure that never happens; v28_completion picks the
  solver-optimal point-grab. Representative (cited):

  | position | deck | v2.7 pick (regret) | v28_completion pick (regret) |
  |---|---|---|---|
  | g3200000018_k2 | 1 | 1335 (0.0) | 729 (0.0) — tie, but v27 only ties via luck |
  | g3200000000_k2 | 1 | 1564 (0.0) | 660 (0.0) |
  | g3200000004_k2 | 1 | 1651 (**3.0**) | 1657 (**2.0**) — strictly better |
  | g3200000033_k2 | 1 | 842 (0.0) | 672 (0.0) |

- **Counterfactual (slack sweep — the driving condition).** top-1 = {slack 0 (=v2.7): **0.7632**,
  slack 1: **0.8261**, 2: 0.8261, 3: 0.8261, 4: 0.8261}. The gain appears the instant the discount is
  ON and is **flat across slack 1-4** — i.e. it is the *discrete* "discount unreachable closures," not
  a tuned magnitude. Mechanism confirmed and robust; **away-flips = 0** means it never hurts on the
  exact set.
- **Conclusion: SUPPORTED** — a real, exact-label, endgame structural fix. (Open question carried to
  search: the endgame is a small fraction of a full game, so the full-game Elo translation may be
  small — the hybrid-handoff lesson.)

## v28_meeple — **WEAK / mechanism not cleanly supported**

- **Hypothesis (M3).** Free meeples are worth more when tiles remain to redeploy them; recovery-scaling
  (`×min(1, deck/t0)`) should make the preference depend on tiles_remaining.
- **Line autopsy.** 14 midgame positions recover the teacher pick under some t0. But they cluster in
  the **opening / early-mid** (tiles 51, 39), where the recovery factor is *partial* (51/72≈0.71) — and
  one case (`heur3200_s3502000047_K40`) recovers at **every** t0 including **t0=0 (flat, no scaling)**.
- **Counterfactual (t0 sweep) — does NOT cleanly predict the flips.** If the recovery mechanism were
  load-bearing, recoveries should track tiles_remaining and vanish at t0=0. Instead several recover only
  at t0=72 (a *reduced* term vs flat) and one recovers regardless of t0. The flips are driven by the
  meeple term's *magnitude* incidentally crossing a ranking boundary, not by the *recovery* semantics.
- **Conclusion: WEAK.** The static-selector movement is small (Phase 4: net +6/1000, 2/22 of its own
  subset) and the counterfactual does not support the named mechanism. Per the addendum, **weak even if
  the search pilot shows Elo** — any such gain is labeled "empirical gain, mechanism unclear."

## v28_farm — **FALSIFIED (as a static selector)**

- **Why it failed (Phase 4).** Broad midgame degradation (net −15 vs teacher; v27_correct 1.0→0.946),
  recovers 1/93 of its own farm target, worse on exact endgame (0.748 vs 0.763).
- **Mechanism autopsy.** The majority gate is *correct in principle* (don't credit growth on a field
  the opponent wins) but (a) its effect is **cap-masked** — `bonus_cap=12` saturates mid-late game, so
  the gate only moves the argmax on near-ties, where (b) removing the growth credit flips moves the
  *wrong* way more often than right (26 vs 11). The contested-field overvaluation it targets is real
  but **rare and small** relative to the cap, and the gate's collateral on near-ties dominates.
  **Falsified as a leaf-value selector** (it may still be defensible inside a larger redesign that also
  raises the cap — not pursued here).

## v28_denial — **FALSIFIED (no static signal; search phenomenon)**

- Net −4 midgame, no target subset, worse endgame (Phase 4). Denial value is realized by *seeing* the
  opponent's completion in search, not by a static cap-asymmetry — so re-weighting the leaf's opponent
  term mostly perturbs ranking without adding information. **Falsified at the leaf level**, as the
  proposal pre-committed.

---

## What this autopsy taught us about v2.7 (the branch's real goal)

1. **v2.7's most credible *leaf-addressable* failure is endgame phantom-closure credit** — a fixed
   closure schedule that ignores deck supply. It is real, exact-label-confirmed, and cleanly fixable
   (v28_completion). It is also **small and endgame-local**.
2. **v2.7's farm/meeple/denial "failures" are mostly NOT leaf-addressable** — they are cap-masked,
   search-mediated, or rare. The Phase-1 taxonomy's "~67% not leaf-addressable" is confirmed at the
   mechanism level: only the deck-aware closure survives an honest mechanistic test.
3. The dominant lesson reproduces the prior audits: **v2.7's leaf is hard to beat statically; the gains
   live in SEARCH**, and the one true leaf fix (deck-aware closure) lands exactly where deeper search
   already helps most (the endgame). Whether it adds anything *on top of* search is the Phase-5/7 test.

*Cases populated from V28_AUTOPSY_DATA.json. Next: Phase 5 search pilots decide whether the supported
mechanism (v28_completion) translates to full-game strength.*
