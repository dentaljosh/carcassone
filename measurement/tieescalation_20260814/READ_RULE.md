# TIE-TRIGGERED SEARCH ESCALATION — READ-RULE (committed BEFORE the ladder ran)

> **ADJUDICATED 2026-08-14 — branch `E-FLAT`
> ([LADDER_READOUT.md](LADDER_READOUT.md)): no rung cleared the committed
> bars; the holdout slice was never opened and stays unburned. THIS READ-RULE
> IS SPENT; any future escalation design needs a fresh one.**

> **STATUS AT WRITING: COMMITTED BEFORE ANY LADDER SEARCH OR CAPTURE NUMBER
> EXISTED ANYWHERE.** The instrument (`scripts/tiletie/escalation_ladder.py`)
> is committed alongside; `LADDER_READOUT.*` does not exist at the time of
> this commit. Git history proves the ordering. Definitions (corpus, arms,
> oracle means, scale_all, transposition mapping, parity-split denominator)
> are [DESIGN.md](DESIGN.md) §4–§5 and are frozen here by reference.

## 1. Scope

- **Dev slice:** 522 positions / 279 roots (the pricing corpus minus
  `../tiletie_mining_20260814/HOLDOUT_ROOTS.json`). The full 4-rung ladder
  {1376, 2752, 5504, 13760} sims/det × k8 runs here.
- **Holdout slice:** 211 positions / 120 roots. Opened ONLY inside the FUND
  branch of §4, at {1376, named rung} only, exactly once. A non-FUND dev read
  leaves it unburned.
- Nothing is tuned on the holdout. No second holdout evaluation under any
  branch. 0 games anywhere in this program.

## 2. The committed statistics (per DESIGN §4)

Per escalation rung r ∈ {2×, 4×, 10×} on the dev slice:

- `mean_capture_r` = mean over paired-resolved positions of
  `(oracle[pick_r] − oracle[pick_base]) · scale_all` [pts/tied tile ply,
  all-plies scale]
- `se_r` = cluster-robust se on `root_id`; `z_r = mean_capture_r / se_r`
- `denom` = mean over the same base-resolved population of the symmetrized
  parity-split honest regret of the base pick (DESIGN §4)
- `capture_ratio_r = mean_capture_r / denom`
- `coverage_r` = fraction of dev positions where BOTH base and rung picks
  resolve to scored arms

## 3. The committed bars

- **B1 (effect size):** `capture_ratio_r ≥ 0.35`
- **B2 (conviction):** `z_r ≥ +2.0`
- **B3 (coverage):** `coverage_r ≥ 0.85`
- **Rung selection:** the **SMALLEST** rung satisfying B1 ∧ B2 ∧ B3 is the
  single named rung. Never the argmax over rungs (the budget-headroom lesson:
  value concentrates early; an argmax over 3 rungs is a winner's-curse draw).

Power, stated in advance: at a plausible realized se of 0.04–0.06 pts, B2
needs a true capture of ~0.08–0.12 pts/ply ≈ 32–48% of the corpus headroom
(+0.252 pooled / honest dev ceiling ≈ +0.199). Only a mechanism-sized effect
can fund; that is deliberate — a micro-effect could not survive the deploy
economics (§6 multiplier ≥1.3×) anyway.

## 4. Branches — first match wins

| # | condition | read |
|---|---|---|
| **E-0 UNREADABLE** | any checksum mismatch entering the analysis; or >5% of dev positions error in search; or base-rung resolution < 0.85 | Fix the harness. No other branch fires; holdout untouched. |
| **E-HARMFUL** | any rung with `z_r ≤ −2.0` | Deeper-at-ties is convicted **harmful** through this oracle. Record and stop; holdout untouched. |
| **E-FLAT** | no rung satisfies B1 ∧ B2 ∧ B3 | **The axis closes.** The mandatory sentence: *"neither static afterstate functions (two failed menus + the 38% reach bound) nor deeper same-shape search expresses the oracle spread"* — which points at the ORACLE's in-family bias, or at k-width/determinization, as the remaining explanations of the +0.252 pts/ply. Report every rung's capture/z/coverage + the realized 2σ resolution. Holdout untouched, stays unburned. No lever, no prereg. |
| **E-FUND-DEV** | some rung satisfies B1 ∧ B2 ∧ B3 | Name the SMALLEST such rung. **Fire the one-shot holdout confirm** at {base, named rung}: `z_hold = mean_capture_named / se_hold` (same statistic, holdout positions, cluster-robust on root). Then: |

Holdout sub-branches (only reachable via E-FUND-DEV; the holdout is burned
the moment its oracle records are read):

| # | condition | read |
|---|---|---|
| **E-CONFIRMED** | `z_hold ≥ +2.0` | Conviction on a never-touched-by-this-program slice. **Licenses (does NOT fund) a deploy prereg draft** with the DESIGN §6 matched-wall-clock uniform-escalation control arm (2 cells). The quoted effect is the holdout number only. |
| **E-WEAK** | `0 < z_hold < +2.0` | Directionally confirmed, under-powered. No prereg licensed; the only licensed follow-up is a supply extension sized from the realized holdout se. |
| **E-REFUTED** | `z_hold ≤ 0` | The dev signal did not survive; dev selection convicted. Axis closes as in E-FLAT (with the holdout now burned — say so). |

**No branch anywhere licenses a game.** No results.csv row, no band claim, no
claim id, `PRODUCTION.yaml` untouched, regardless of branch.

## 5. Mandatory reporting on every branch

Per rung: capture (pts/ply, all-scale), z, capture_ratio, coverage,
pick-change rate (afterstate-level + action-level), out-of-scored-set rate,
median/mean wall secs (contended-box flagged). Plus: base-pick vs corpus
champ-pick agreement on selfplay (integrity witness, not a gate), the
denominator and its se, the realized 2σ resolution in pts and elo (÷3.2 chain
with the ±1.6× divisor bracket, quoted as the pricing readout quotes it), and
the DESIGN §6 deploy multiplier estimate with realized census numbers.
