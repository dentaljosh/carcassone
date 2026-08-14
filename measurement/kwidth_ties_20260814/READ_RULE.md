# k-WIDTH / DETERMINIZATION AT TIED PLIES — READ-RULE (committed BEFORE the ladder ran)

> **ADJUDICATED 2026-08-14 — branch `W-FLAT`
> ([LADDER_READOUT.md](LADDER_READOUT.md)): no rung cleared the committed
> bars, so no attribution branch was reachable; the holdout was never opened
> and stays unburned. THIS READ-RULE IS SPENT; any future k-width design needs
> a fresh one.** (One first-pass `W-0 UNREADABLE` fired on the laptop from a
> share-path resolution fault — `term_gate._share()` prefers
> `/mnt/c/carc-shared`, which on that box is its OWN Windows drive — dropping
> all 522 oracle joins. The E-0-class branch did exactly its job. The search
> records were intact and untouched; the analysis was re-run unchanged on the
> local box, where the same records produced `W-FLAT`. No bar, statistic or
> record was altered.)

> **STATUS AT WRITING: COMMITTED BEFORE ANY LADDER SEARCH OR CAPTURE NUMBER
> EXISTED ANYWHERE.** `LADDER_READOUT.*` and `records/` do not exist at the
> time of this commit; the instrument (`scripts/tiletie/kwidth_ladder.py`) is
> committed in the next commit, still before any search. Git history proves the
> ordering. Definitions (corpus, arms, oracle means, `scale_all`, transposition
> mapping, parity-split denominator) are [DESIGN.md](DESIGN.md) §3–§5 and are
> frozen here by reference; the statistical routines are imported from
> `scripts/tiletie/escalation_ladder.py` unchanged.

## 1. Scope

- **Dev slice:** 522 positions / 279 roots (the pricing corpus minus
  `../tiletie_mining_20260814/HOLDOUT_ROOTS.json`). The full 6-rung ladder runs
  here and only here.
- **Holdout slice (211 positions / 120 roots): NOT OPENED BY THIS PROGRAM
  UNDER ANY BRANCH.** It stays unburned. The instrument has no holdout code
  path. On a fund branch the one-shot holdout confirm is *named as the licensed
  next step*, to be run under a fresh read-rule with owner authorization — not
  tonight, not by this run.
- 0 games anywhere in this program.

## 2. The rungs (DESIGN §3), frozen

| id | k_dets | sims/det | total | class |
|---|---|---|---|---|
| R0 | 8 | 1376 | 11,008 | base (production champion) |
| R1 | 16 | 1376 | 22,016 | EXPANSION |
| R2 | 32 | 1376 | 44,032 | EXPANSION |
| R3 | 64 | 1376 | 88,064 | EXPANSION |
| C1 | 16 | 688 | 11,008 | **ISO-BUDGET** |
| C2 | 32 | 344 | 11,008 | **ISO-BUDGET** |

## 3. The committed statistics

Per rung r ≠ R0 on the dev slice:

- `mean_capture_r` = mean over paired-resolved positions of
  `(oracle[pick_r] − oracle[pick_R0]) · scale_all` [pts/tied tile ply,
  all-plies scale]
- `se_r` = cluster-robust se on `root_id`; `z_r = mean_capture_r / se_r`
- `denom` = mean over the same base-resolved population of the symmetrized
  parity-split honest regret of the R0 pick
- `capture_ratio_r = mean_capture_r / denom`
- `coverage_r` = fraction of dev positions where BOTH R0 and rung picks
  resolve to scored arms

## 4. The committed bars — the vart's, unchanged

- **B1 (effect size):** `capture_ratio_r ≥ 0.35`
- **B2 (conviction):** `z_r ≥ +2.0`
- **B3 (coverage):** `coverage_r ≥ 0.85`

A rung **CLEARS** iff B1 ∧ B2 ∧ B3.

**Rung selection inside a fund:** the **SMALLEST TOTAL BUDGET** rung that
clears is the named rung; ties in total budget broken toward the SMALLER k.
Never the argmax over rungs (the budget-headroom lesson: value concentrates
early; an argmax over 5 rungs is a winner's-curse draw).

Power, stated in advance (carried from the vart's realized se): at a realized
se of 0.036–0.060 pts, B2 needs a true capture of ~0.07–0.12 pts/ply ≈ 26–43 %
of the corpus headroom. Only a mechanism-sized effect can fund; that is
deliberate.

## 5. Branches — first match wins

| # | condition | read |
|---|---|---|
| **W-0 UNREADABLE** | any checksum mismatch entering the analysis; or >5 % of dev positions error in search; or R0 resolution < 0.85 | Fix the harness. No other branch fires. |
| **W-HARMFUL** | any rung with `z_r ≤ −2.0` | Wider-at-ties is convicted **harmful** through this oracle. Record and stop. |
| **W-FLAT** | **no rung clears** | **The k-width / determinization axis closes.** Mandatory sentence in §6. |
| **W-FUND-WORLDS** | some rung clears **AND at least one ISO-BUDGET rung (C1 or C2) clears** | **Attribution = WORLDS.** The capture survives at the champion's own 11,008 sims ⇒ this is an ALLOCATION result, deployable at 1.00× wall-clock, and a real fundable mechanism. Name the smallest clearing rung (§4). Licenses (does NOT fund) a follow-up: the one-shot holdout confirm under a fresh read-rule, then a deploy prereg with a matched-wall-clock control arm. |
| **W-FUND-AMBIG** | some rung clears, no ISO-BUDGET rung clears, but `max(z_C1, z_C2) > +1.0` | **Attribution UNSEPARATED.** The iso-budget rungs are directionally positive but under-powered against the bars. No prereg, no holdout. The only licensed follow-up is a supply/precision extension on the ISO-BUDGET rungs alone, sized from the realized se. |
| **W-BUDGET-ONLY** | some rung clears, no ISO-BUDGET rung clears, and `max(z_C1, z_C2) ≤ +1.0` | **Attribution = BUDGET, not worlds.** Only the expensive expansion rungs capture; buying the same worlds by selling depth captures nothing. The vart already priced "more budget via depth" as flat and CL-068's G2 closed total budget — so this reading funds NOTHING and the worlds hypothesis is dead as stated. Record the expansion numbers as a budget-axis curiosity, not a lever. |

**No branch anywhere licenses a game, a band, a `results.csv` row, a claim id,
or a `PRODUCTION.yaml` edit.** No branch opens the holdout.

## 6. Mandatory sentence on W-FLAT

> *Neither static afterstate functions (two failed menus + the 38 % reach
> bound), nor deeper same-shape search (the vart, E-FLAT), nor wider
> determinization — at increased budget OR at the champion's own budget —
> expresses the +0.252 pts/ply oracle spread at leaf-tied plies. With all three
> named mechanisms closed, the leading remaining explanation of the tile-tie
> signal is a **judge artifact**: the in-family `clair-puct` oracle's own bias,
> which only an out-of-family re-pricing can settle.*

## 7. Mandatory reporting on every branch

Per rung: capture (pts/ply, all-scale), se, z, capture_ratio, coverage,
pick-change rate (arm-level + action-level), out-of-scored-set rate,
median/mean wall secs (contended-box flagged), deploy multiplier. Plus: the
denominator and its se; the realized 2σ resolution in pts and in elo (÷3.2
non-additivity chain with the ±1.6× divisor bracket, quoted as the pricing
readout quotes it); **both integrity witnesses** (R0 vs corpus champ pick on
`selfplay`; R0 vs the vart's own R0 records, rid-by-rid); and the realized
world-duplication caveat for R3 (DESIGN §7.3).
