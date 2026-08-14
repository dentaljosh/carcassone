# CALIB READOUT — J-rules ROOT FILTERS (surface C) E4-replay exclusion ladder

**2026-08-14. The read-rule ([`CALIB_READ_RULE.md`](CALIB_READ_RULE.md), committed at
`82f3fa96` BEFORE any rate existed) is applied MECHANICALLY below. Raw rollup:
[`calib/SUMMARY.json`](calib/SUMMARY.json); per-ply jsonl per archive alongside it;
run log [`calib_run.log`](calib_run.log).**

## Corpus

**31 archives / 1,855 graded champion plies** (the full E4 bank at grading time) —
one champion search per ply (CRN seed 12345, budget from each archive's own stamp:
**93.2% of graded plies at the deploy budget 11008**, 2 old archives at 2752), four
pure filter probes per ply. Profiles: fixed_v1 28 · walled 2 · app_aug2 1.
`champ_agrees_archive` 72.3% (context only). Applicable (meeple-root) plies:
**803/1855 = 43.3%**.

## §0 validity — PASS

| check | state |
|---|---|
| no `partial` summary | ✅ (full run, no `--limit-plies`) |
| `all_replay_scores_match` | ✅ `true`, 31/31 |
| positive control `_assert_surface_c_live` | ✅ ran per grading process (aborts otherwise) |
| every arm `leaf_hash` == champion `a36d2e15a3b3d71d` | ✅ (instrument aborts otherwise) |
| corpus ≥ 20 archives and ≥ 800 plies | ✅ 31 / 1,855 |

## The ladder

| arm | mask | filters | **exclusion rate** (== the flip rate) | Wilson-95 | **yield rate** | filter fires (descriptive) |
|---|---|---|---|---|---|---|
| `j10` | 2 | F-J10 | **3.72%** (69/1855) | [2.95%, 4.68%] | 0.00% (0) | f_j10 384 |
| `j3` | 8 | F-J3 | **2.80%** (52/1855) | [2.14%, 3.66%] | 0.00% (0) | f_j3 235 |
| `current` | 11 | F-END+F-J10+F-J3 | **6.52%** (121/1855) | [5.49%, 7.74%] | 0.00% (0) | f_end 1 · f_j10 384 · f_j3 215 |
| `all` | 15 | + F-J9 | **7.76%** (144/1855) | [6.63%, 9.07%] | 0.00% (0) | + f_j9 34 |

## §3 branches, in order

1. **SAFETY** — no arm's yield rate exceeds 0.05 (every arm read **0 yields in
   1,855 plies**: the never-empty guard never once had to block a filter). **No
   arm struck.**
2. **FUND-SMALLEST** — no surviving arm has `f ∈ [0.10, 0.25]`. **Does not fire.**
3. **`NO-EXPRESSION` — FIRES.** Every surviving arm has `f < 0.10` — and not
   marginally: even the LARGEST pre-registered mask (`all`, 15) has its Wilson-95
   **upper** bound at **9.07%, below the 10% bar**. **No cell is bought. No band
   is spent. The [`DEPLOY_PREREG_DRAFT.md`](DEPLOY_PREREG_DRAFT.md) is never
   promoted.**

## The recorded answer (per the rule's own §3.3 wording)

**The champion at deploy depth already plays inside the anchor's hard rules too
often for this surface to be resolvable.** The filters are demonstrably live —
F-J10 bit on 384 plies and F-J3 on 235 — but they remove the move the champion
would actually have played on only 2.8–7.8% of decisions, below the pre-committed
resolvability bar for an n=800 deck-paired cell. Where surface B's null said
"the search overrides the advice", this stop says the constraint surface cannot
even be *priced*: **the anchor's articulated hard rules and the champion's
deploy-depth play already agree on ~93% of decisions** (1 − 6.52% for the
`current` stack).

This completes the encoding triptych without a third cell: **A** (evaluation) =
loss, confounded by budget · **B** (advice) = clean sims-washout null · **C**
(constraint) = NO-EXPRESSION at every pre-registered mask.

## Bound by CALIB_READ_RULE §4 (forbidden readings)

The exclusion rate is a LOWER bound on behavioural change; no elo or strength
adjective attaches to any number here; "where the exclusions land" is
descriptive; no cross-surface contrast is a statistic; extending the ladder
(weaker/stronger masks, `min_keep` variants, `j8brk`, per-game `k0`) is a NEW
calibration needing its own committed rule. **No claim is minted; nothing in
governance moves.**
