# KWIDTH_110K READ-OUT — "champ vs 10× champ" screen (11008 vs 110080), 2026-08-02

**STATUS: COMPLETE.** Pre-registered analysis
([KWIDTH_110K_PREREG_20260801.md](KWIDTH_110K_PREREG_20260801.md), prereg commit
`ca5b571` BEFORE the main run; analysis pass
`scripts/measurement_infra/analyze_kwidth110k_oracle.py`, committed before any score
existed). Raw JSON: `oracle_110k_20260801/READOUT_110K.json` on the share (laptop-local
master copy `/home/doctor/carc_out/oracle_110k_20260801`).

**Sign convention: positive = the 110080 (k80×1376) pick scores better.**

## Verdict (pre-registered map, §6)

> ### UNDERPOWERED / INCONCLUSIVE at this n → default **DO NOT FUND**
>
> elo-equivalent **+19.4**, 95% CI **[−5.7, +44.6]** against the pre-fixed 25-elo funding
> bar. The screen could neither detect a fundable effect (needed point ≥ +0.639 pts at the
> realized se) nor exclude one (needed ≤ −0.002 pts — the NOT-DETECTED branch was
> essentially unreachable at this se). A confirm h2h is not funded by default; what the
> screen *failed to exclude* is an effect up to ~45 elo-equivalent.

## Numbers (cluster-robust on root = the cited row)

| quantity | value |
|---|---|
| pick cells / roots | 900 / 608, 0 failed; arm-A cross-run identity 900/900 vs the 22016 run; agent parity 20/20 |
| D̂ disagreement rate | **0.1433 ± 0.0117** (129 disagreements, 115 roots) |
| mean Δ per disagreement (CRN, M=32) | **+0.484**, CR se 0.320, **z +1.51** |
| root-collapsed / trimmed / median | +0.538 (z 1.60) / +0.204 / 0.000 |
| bootstrap-of-roots P(≤0) | 0.061 (records) / 0.051 (roots) |
| sign test | 57+/59− records (p 0.61) — the mean is carried by magnitude, not count |
| per-position sd | 3.556 (prereg planning constant was 2.95) |
| pts/move compound | +0.0693, 95% CI [−0.020, +0.159] |
| **elo-equivalent** (order-of-magnitude chain, ÷3.2 non-additivity) | **+19.4 [−5.7, +44.6]** |

## The ladder (one instrument, M=32, oracle-sims 100)

| rung | D̂ | mean Δ | pts/move | ~elo |
|---|---|---|---|---|
| 2752 → 11008 (pilot, n=100) | 0.240 | +0.738 | 0.177 | **49.7** |
| 11008 → 22016 (n=237) | 0.124 | +0.105 | 0.013 | 3.7 |
| 11008 → 110080 (THIS RUN, n=129) | 0.143 | +0.484 | 0.069 | 19.4 |

The interesting shape: the 2× rung read ≈ null, but the 10× rung's point estimate is ~5×
the 2× rung's, i.e. *consistent with* returns that are flat locally but non-zero over a
decade of budget — yet the whole read is inside one CI. Do not promote the shape; it is
what a follow-up would test, not a finding.

## Standing guard-rails (travel with every citation)

- ⚠️ CL-068 clock sentence: 11008 already costs ~91% of a 15-min sudden-death clock;
  110080 is 10× an unusable budget. **Understanding, not a deploy lever.**
- No CL id, no results.csv row, PRODUCTION.yaml untouched (pre-committed).
- Strata descriptive only; winner's-curse warning applies to any sub-read.
- Does NOT un-park the oracle teacher-curve pricing (separate ask).

## If Joshua wants to overrule the default and fund anyway

§6.1 sizing at the point estimate +19.4 elo: n = (2·12·√400/19.4)² ≈ **610 deck-paired
games**, one seat at 10× budget (~5.5× per-game cost), Rust-era farms ~7.3× cheaper than
the era the prereg priced. That is a real but no-longer-absurd spend; the honest
alternative is another screen rung (e.g. 4×=44032, or M→64 on the same records to shrink
the CI) before any h2h.
