# Item 1 -- Farm-norm replay (JCZ n=400 confirm corpus)

> **Status: COMPLETE 2026-08-10. REPLAY/DECOMPOSITION INSTRUMENT ONLY -- 0 games played, NO band claimed, NO strength claim minted, `governance/PRODUCTION.yaml` untouched.**

Source: `measurement/jcz_match_20260809/confirm.jsonl` (400 games, 200 decks x 2 seat-swaps, `fixed_v1`+R9, champion k8x1376=11008 vs JCloisterZone's `LegacyAiPlayer`, band **1.08e11, retired**). Replayed via `scripts/analyzer/jcz_confirm_adapter.py` -> `scripts/analyzer/corpus_stats.py` (pure `(deck_seed, actions)` replay, no search, no network). Plan: `docs/LEVER_MENU_PLAN_20260810.md` sections 4.1 and 8.1.

## Replay acceptance gate

**Requirement:** replay must reproduce the archived finals 400/400 before any decomposition number is quoted.

**Result: PASS 400/400** -- replay_scores_match 400/400, mismatch 0/400, score-flow split_ok 400/400.

## Primary statistic

**Champion-seat `farm_pts` mean +/- 95% CI over 400 champion seats: 31.88 +/- 0.77** (sd 7.91, 95% CI [31.11, 32.66]).

| reference | value | source |
|---|---:|---|
| self-play, `walled`, 2752 | 20.49 (sd 10.7, n=898 seats) | `measurement/analyzer_20260802/CORPUS_STATS_champ449.md` |
| self-play, `fixed_v1`, 11008 | 20.81 (n=800 seats) | `measurement/f9_phase_c/PHASE_C_DESCRIPTIVES.md section 3` |
| **champion vs JCZ, this replay** | **31.88 +/- 0.77** (n=400 seats) | this document |
| champion vs Joshua (E4) | ~11.0 | the figure being refereed |

## Branch

**Branch B.** vs-JCZ champion-seat farm pts/seat (31.88 +/- 0.77) is OUTSIDE all three pre-registered bands: it is not near 11-14 (branch A; CI has zero overlap with that band), and it exceeds the self-play norms by more than 1 sd (+11.07 pts / +1.03 sd above the fixed_v1/11008 norm, using the only sd figure either reference carries), so it is not literally 'near 20' either (branch B as worded). The 95% CI also does not straddle both anchors (branch C requires that); it sits cleanly above both. Reported here as its own outcome, not force-fit to a letter -- but on DECISION CONSEQUENCE it sides with B, and more strongly than B's own anchor: a generic non-self opponent does not suppress the champion's farm points, it ELEVATES them (mechanism below), so the ~11.0-vs-Joshua figure cannot be explained as 'what any non-self opponent produces'. Filed as B on that basis, with this numeric caveat stated plainly rather than silently rounded.

**Mechanism.** Mechanism (context, not one of the six required decomposition fields): JCZ's `LegacyAiPlayer` places essentially no farmers -- mean 0.085 farmers/seat, 366/400 JCZ seats placed ZERO farmers across the whole game (vs the champion's own farmer count, always >=1). With almost no farm contest, the champion collects farm points close to uncontested, which is the likely reason the observed value exceeds the self-play norms (where both seats run the same farmer-timing policy and split farm real estate) rather than landing between them.

## Full per-seat decomposition (both seats, all six fields)

| field | champion seat (n=400) | JCZ seat (n=400) |
|---|---|---|
| final_score | 99.54 +/- 1.67  (sd 17.03, n=400) | 93.05 +/- 1.35  (sd 13.78, n=400) |
| during_play | 48.80 +/- 1.61  (sd 16.45, n=400) | 56.61 +/- 1.84  (sd 18.76, n=400) |
| incomplete_pts | 18.86 +/- 0.88  (sd 9.02, n=400) | 35.83 +/- 0.94  (sd 9.57, n=400) |
| farm_pts | 31.88 +/- 0.77  (sd 7.91, n=400) | 0.61 +/- 0.24  (sd 2.48, n=400) |
| farm_pts_per_farmer | 8.98 +/- 0.25  (sd 2.57, n=400) | 7.15 +/- 1.72  (sd 5.12, n=34, 366 null) |
| first_farm_turn | 3.10 +/- 0.25  (sd 2.59, n=400) | 55.03 +/- 5.78  (sd 17.18, n=34, 366 null) |

## Riders

- (i) One opponent (JCloisterZone LegacyAiPlayer), one band (1.08e11), one rules epoch (fixed_v1+R9) -- a single external opponent is not 'all opponents'; this number is bounded to that one comparison, not generalized.
- (ii) farm_pts sd is ~10.7 in the self-play reference corpora; 95% CI at 400 seats is ~+-1.05 pts, enough to separate 11 from 20 but NOT to resolve 14 from 17.
- (iii) band 1.08e11 is retired; this reuse is licensed because it is an exploratory decomposition of an existing archive that mints no strength claim -- the same licence the JCZ mining reuse (item 6 lineage) was granted.
- This item plays ZERO games, claims NO band, and mints NO strength claim.

## Provenance

- Adapted archive: `measurement/lever_menu_20260810/jcz_confirm_adapted.jsonl`
- corpus_stats output: `measurement/lever_menu_20260810/CORPUS_STATS_jcz_confirm400.json` / `.md`
- Replay env: `CARCASSONNE_RULES_PROFILE=fixed_v1 CARCASSONNE_FIX_R9=1` (matches the generating harness's manifest; without these env vars a `fixed_v1`+R9 archive would replay under the `walled` default and the acceptance gate would not have a meaningful footing).
- Logs: `measurement/lever_menu_20260810/logs/`
- Machine-readable twin: `measurement/lever_menu_20260810/ITEM1_FARM_NORM.json`
