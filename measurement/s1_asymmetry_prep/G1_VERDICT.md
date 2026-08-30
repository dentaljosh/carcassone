# G1 VERDICT — `G1-EXPRESSES`, d* = 0.25 (2026-08-30, adjudicated ~01:45 EDT)

**Branch fired: `G1-EXPRESSES`** per [READ_RULE_G1.md](READ_RULE_G1.md) §4.1, read against
`g1_20260830/SUMMARY.json` (statistics) + `g1_20260830/MANIFEST.json` (config, IS-D1).

## The read

| arm | E1 flip rate (point est) | Wilson-95 | E2 TV mean | n graded |
|---|---:|---|---:|---:|
| `s1_d0p25` | **5.01%** ✅ | [4.32%, 5.81%] | 0.0089 | 3311 |
| `s1_d0p5`  | 7.10% ✅ | [6.27%, 8.02%] | 0.0133 | 3311 |
| `s1_d1p0`  | 9.73% ✅ | [8.76%, 10.78%] | 0.0201 | 3311 |
| `s1_d2p0`  | 12.38% ✅ | [11.30%, 13.55%] | 0.0294 | 3311 |

- **Bar read on the POINT ESTIMATE per §3** (frozen pre-outcome), interval alongside.
  ⚠️ The emitter's inline comment at `jrules_priors_e4_replay.py:404` ("the bar is read on
  wilson95_lo, CALIB_READ_RULE §2") is a STALE cross-surface reference and was NOT followed
  (2026-08-30 merge-review filing; verify agent died, ground-truthed by the orchestrator
  against READ_RULE_G1 §3 line 79 instead).
- **d\* = 0.25**, the smallest clearing rung. Honest marginality note, on the record: it clears
  by 0.01pp and its Wilson interval straddles the bar. Under the stale wilson95_lo reading the
  smallest clearing rung would instead be 0.5 — recorded as context, not as a statistic.
- E2 never carries any rung (max 0.0294 < 0.05) — §4's stated risk ("E2 may carry the gate
  alone") realized in the OPPOSITE direction: E1 carried, E2 missed everywhere.
- Not `G1-STRONG` (5.01% < 15%). Monotone in dose on both statistics — no §7 flag.
- Corpus: 56 E4 archives, profiles {fixed_v1: 53, walled: 2, app_aug2: 1}, 3311 graded plies,
  ~45 min wall at W=30 local.

## Guards (§5) — all PASS

1. Positive control: PASS per grading process (in-log; SystemExit-on-fail semantics, rc=0).
2. Leaf hash: every arm `a36d2e15a3b3d71d` == champion. PASS.
3. `all_replay_scores_match: true`. PASS.
4. Post-S1 wheel accepted `scope='opp'` (fail-closed otherwise). PASS.
5. `partial: false` in all 56 `game_*.json`. PASS.
6. MANIFEST arms == §2.1 exactly; budget 1376 × 16 = 22016 (CLI override, deliberate). PASS.

## Consequence (per §4.1 + the owner's prefund)

`G1-EXPRESSES` licenses PROPOSING the G3 three-arm decomposition cell at d*=0.25; the owner's
ratified overnight envelope ("S1 G3 three-arm cell AUTO-LAUNCHES if G1 fires EXPRESSES",
2026-08-30) is the pre-given owner decision, so G3 is FUNDED at δ=0.25. Pre-launch conditions
set by the orchestrator under the same envelope: (a) the R7 witness (merge review: played
`scope='opp'` cells currently carry only a config echo, no play-derived binding witness —
`jr_expansions_*` discarded at `fair/mod.rs:810-814`) is built and smoked FIRST; (b) R6
(scope boosts survive `search_carry` tree reuse) is checked against the G3 harness's actual
search-session usage before launch; (c) G3 gets its own frozen prereg + band claim (bands
155-157e9 belong to the FPU round; avoid registry-absent-but-referenced 158e9).

## Forbidden-readings reminder (§6)

A flip is not an improvement (CL-080: 10.09% flip → −53.8 elo). No elo, no band, no
results.csv row, no governance write from G1. Expression ≠ effect; d* is the smallest
OBSERVABLE dose, not "the right dose".
