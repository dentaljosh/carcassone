# Morning brief — night of 2026-07-30 → 31 (leaf ablation + advisor)

> Written 08:45 with cells 1–3 verdicts banked, cell 4 running. Authoritative numbers:
> `ABL_PROGRESS.tsv` (this dir) + per-cell `summary.json` on the share. Sign convention:
> **negative elo = the knocked-out component is worth that much** (candidate = champion
> leaf minus one component, vs intact champion, n=400 deck-paired, band 9.60e10, PUCT@2750).

## The table so far

| # | knockout | removes | elo | ±1σ | paired z | verdict |
|---|---|---|---|---|---|---|
| 1 | `meepleoff` | entire meeple-economy term | **−299.6** | 24.2 | −18.94 | organ. 59W–338L |
| 2 | `oppanticoff` | opponent half of closure anticipation | **−153.4** | 19.1 | −8.71 | organ |
| 3 | `anticoff` | **BOTH** halves of closure anticipation | **−7.8** | 17.4 | −1.81 | **≈ NULL** |
| 4 | `selfanticoff` | self half only | running (started 08:25) | | | prediction: large negative if the balance story is right |
| 5 | `meepleflat` | curve *shape* only (keeps flat k=2.0) | queued | | | decomposes row 1 into existence-vs-shape |
| 6 | `capoff` | the cap8 clamp (uncapped) | queued | | | |

## The headline: a massive non-additive interaction, caught by design

Row 2 + row 3 together are the story. Removing the **opponent half alone** of closure
anticipation costs **−153 elo**; removing **both halves** costs **−7.8 ± 17.4 — statistically
nothing**. The nested triple (cells 2/3/4) was built precisely as an additivity check, and it
fired on the first pair: the value of the anticipation machinery is **not the information — it
is the balance**. An eval that anticipates its own closures but not the opponent's is
systematically biased (over-values its own prospects → presumably overextends) and gets
crushed; an eval that anticipates *neither* stays unbiased and plays nearly champion-level.
Cell 4 (self half removed, opponent kept) is the confirming prediction: if balance is the
mechanism, it should also be large-negative. If it comes back null instead, the story is
asymmetric (only opp-blindness hurts) and more interesting still.

Two sober caveats before anyone deletes code: (a) row 3's CI is ±17.4 — "≈0" here means
"≤ ~40 elo", not zero; (b) interactions with the still-queued cells (curve shape, cap clamp)
are unmeasured, and the one-deletion-per-measured-cell rule stands (2026-07-31 discussion).

Row 1 stands apart: the meeple-economy term is (as predicted from adoption history and last
night's E4 farm autopsy) the single dominant component, −300 elo — and cell 5 will split that
into "having any meeple term" vs "the tuned curve shape".

## Also overnight

- **Fable advisor memo landed** → [FABLE_ADVISOR_20260731.md](../../docs/reviews/FABLE_ADVISOR_20260731.md)
  (`aef2638`). Headlines: **two papers ready now** (P1 prediction≠discrimination ~85%; P2
  measurement methodology ~75% — neither needs the missing human anchor), P3 (game science,
  incl. this ablation) at ~40% gated on walled-variant remediation; calibration = "empirical
  core at/above PhD-dissertation standard; scope is what keeps it from lab-scale"; no
  manuscript may say "superhuman"; 90-day sequence proposed; 7 questions only Joshua can answer.
- **Ops log:** chain has run untouched since 23:32; per-cell pace varies 2× by knockout
  (threat-blind games run long — cell 2 took 4.2 h; cell 3 took 2.6 h); zero stalls, zero
  claim incidents since the pre-launch clock-skew fix; watchdogs healthy all night.
- **Pending Joshua decisions (unchanged):** recentring (app-only 6→18 / global / both) ·
  worktree merges (border fix + retail start tile + CoreML) at a quiet window · W-sweep F7d
  auto-queued after cell 6 · advisor memo's 7 questions.
