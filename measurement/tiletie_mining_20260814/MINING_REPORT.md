# TILE-TIE ORACLE-SEPARATION MINING — what separates the oracle-best arm from the incumbent pick

> **OUTCOME STAMP (post-hoc, 2026-08-14): the §4 gate ran and FAILED AT THE
> SCREEN — [GATE2_READOUT.md](GATE2_READOUT.md) `G2-SCREEN-FAIL`, dev
> cross-fit +0.0027 ± 0.0420 (z +0.06); the FINAL slice was never opened and
> stays unburned.** Second failed menu on the real +0.234 ceiling; Finding 1's
> bound is now the operative statement of this axis.

> **STATUS: EXPLORATORY, COMPLETE 2026-08-14. ⚠️ EVERY NUMBER IN THIS FILE IS
> SELECTION-BIASED OR IN-SAMPLE BY CONSTRUCTION — view A conditions on
> oracle-vs-incumbent disagreement, view B is single-feature shopping on the
> dev slice, and no statistic here is confirmatory. No p-value in this file
> may be quoted as evidence of anything beyond "worth gating". The only
> confirmatory read this program can ever produce is the phase-2 gate's
> one-shot FINAL-slice evaluation (`GATE2_READ_RULE.md`, committed after this
> report).** 0 games played; no results.csv row, no band, no claim id.

This is the DESIGN §7.2 re-open route of
[../tiletie_term_20260814/DESIGN.md](../tiletie_term_20260814/DESIGN.md):
after the guess-first four-feature menu G-FAILed held-out (−0.0546 ± 0.0300),
characterize what ACTUALLY separates the oracle-best arm from the incumbent
(lowest-index) pick inside leaf-tied sets — board-level, descriptively —
and only then hand-craft. Instrument:
`scripts/tiletie/mine_oracle_sep.py`; machine-readable stats:
[MINING_STATS.json](MINING_STATS.json); tests: `tests/test_tiletie_mining.py`.

## 0. Corpus-reuse firewall (committed before any statistic existed)

The pricing corpus (733 positions / 399 roots, every deduped tied arm
CRN-deep-scored) has already adjudicated one failed gate, so this attempt is
firewalled: [HOLDOUT_ROOTS.json](HOLDOUT_ROOTS.json) (seed 2026081402,
committed `a2f05436`, before any mining number) designates **120/399 roots =
211/733 positions as a FINAL slice this mining NEVER read** — their oracle
record files are skipped **by filename** (never parsed), and the analyzer
asserts the joined table contains no holdout rid. Everything below is the
**dev slice: 522 positions / 279 roots** (30 `fixed_v1` + 489 `walled` + 3
`app_aug2`; checksum-asserted replays, 0 errors; farm-key joins 0 misses).

Dev-slice context numbers: oracle-best ≠ incumbent on **314/522 = 60.2%** of
positions; honest ceiling (the pricing run's parity-split per-position
`headroom_leaf`, all-scale) = **+0.1986 ± 0.0909 (z +2.19)** pts/tied ply —
consistent with the pooled +0.2340. The naive full-M argmax "ceiling" is
+0.9706 — winner's-curse-inflated ~5×, used below only where both sides of a
ratio carry the same inflation.

38 descriptors were extracted per scored arm from the **tile afterstate diff
vs the root** (placement geometry; city/road join·closure·ownership·open-cell
deltas; farm merges & finished-city-adjacency deltas; cloister adjacency;
meeple proximity; the spent gate's four features as a contrast set). Note the
tied plies are **tile placements** — there is no meeple-vs-no-meeple dimension
at the compared ply; meeple effects can only appear indirectly (proximity,
ownership deltas of merged components).

## 1. Finding 1 — the tie sets are structurally homogeneous, and the whole descriptor space is blind to ~38% of the prize

The strongest result is a **bound**, not a feature:

- On disagreement rows, the oracle-best and incumbent afterstates are
  **identical on nearly every structural dimension**: city join/ownership
  deltas differ on 1.3–1.6% of rows, city/road closures on 0–1.3%, farm
  contests on 1.3%, opp-city wall-in (`d_open_c_opp`) on 0.0%. Only raw
  placement geometry differs at meaningful rates (meeple distances ~40–44%,
  `d_city` 24%, occ4/frontier ~20%, road joins 9–15%).
- **157/522 pools (30%) are fully indistinguishable**: every scored arm in
  the pool has an identical 38-descriptor vector (distinct afterstates the
  entire mined space cannot tell apart — no static rule over it can move).
- **Feature-space reach**: the best any deterministic pick rule over the full
  38-descriptor space could do, even selected in-sample per position, is
  **62.2%** of the naive prize (+0.6033 vs +0.9706, same curse-inflation on
  both sides). ≈38% of the oracle spread is unreachable by *any* function of
  this descriptor space, cheap or not.

Combined with attempt 1's held-out G-FAIL on the guessed geometry menu, this
pushes toward: **the oracle's tie-break signal is mostly not expressible as a
static function of the tile afterstate** — it plausibly lives in
deck/lookahead-dependent tactics the CRN worlds see and a leaf cannot.

## 2. Finding 2 — the exploitable ordering signal sits at the BOTTOM, not the top

The only |z| ≥ 2 pick-rules in view B are **harmful directions**:

| pick rule | capture (all-scale) | z | moved |
|---|---|---|---|
| `occ4-` (prefer loosest placement) | **−0.0794 ± 0.0298** | **−2.67** | 12% |
| `f_perim+` (prefer jagged frontier) | **−0.0752 ± 0.0301** | **−2.50** | 13% |
| reverse: `occ4+` / `f_perim-` | +0.0219 ± 0.0301 | +0.73 | 13% |

The asymmetry matters: looseness marks the **worst** arm in the tie set, but
snugness does not mark the best — an argmax tie-break term can only harvest
the top of an ordering, so the convicted direction is unusable as a bonus
(and the incumbent lowest-index pick apparently already avoids the loose
arms often enough). Mechanism-wise this *rhymes* with attempt 1's held-out
lean-harmful on its wall-in menu: frontier-tightness geometry prices the tail,
not the head.

## 3. Finding 3 — the best positive directions are weak, meeple-proximity-flavored, and phase-incoherent

| pick rule | capture | z | moved | note |
|---|---|---|---|---|
| `dist_own_meeple+` (away from own meeples) | +0.0532 ± 0.0398 | +1.34 | 25% | ≈27% of the honest dev ceiling |
| `dist_centroid-` (toward board centroid) | +0.0476 ± 0.0456 | +1.04 | 33% | mid-heavy (+0.124, z +1.40 mid) |
| `occ4+` (snuggest placement) | +0.0219 ± 0.0301 | +0.73 | 13% | reverse of the convicted-harmful axis |

View A agrees in *direction* — the oracle-best arm is on average farther from
own meeples and closer to the opponent's (`cmp_meeplediff` Δ +0.242, z +2.16,
the largest positive view-A separation; `dist_own_meeple` Δ +0.129, z +1.85,
concentrated in mid: +0.305) — but the composite `cmp_meeplediff+` *pick
rule* captures only +0.015 (z +0.34): the dimension separates on average yet
its extreme is not the best arm. And the per-phase view-B tables flip signs
across phases on several features (`adj8_opp_meeple+` +0.074 mid / −0.088
late; `dist_centroid` sign flips early↔mid), the same noise signature the
failed gate's fold-selection showed. Nothing positive exceeds in-sample
z +1.40 in the phase slices where the pricing run says the spread lives.

## 4. What this licenses

Per the §7.2 route, a **small** phase-2 gate is still owed — the three
mechanism-argued candidates above (`dist_own_meeple+`, `dist_centroid-`,
`occ4+`), no menu beyond them, adjudicated by
[GATE2_READ_RULE.md](GATE2_READ_RULE.md) (committed after this report, before
any gate number): 5-fold root-clustered cross-fit on the dev slice as a
**screen only** (the menu was mined from these labels, so the dev number is
optimistic by construction), and the never-touched FINAL slice evaluated
**exactly once** on the pre-named best candidate — `dist_own_meeple+` —
and only if the screen passes. Honest prior from this table: the screen bar
(z ≥ +2.0) sits ~1.5× above the best candidate's in-sample z, so the likely
outcome is a clean G2-FAIL with the FINAL slice left unburned; that outcome
would be the second failed menu on a real signal and materially strengthens
the Finding-1 bound.

## Pointers

- [MINING_STATS.json](MINING_STATS.json) — every view (A diffs / B captures /
  C within-set correlations / phase splits / reach bound), machine-readable
- [HOLDOUT_ROOTS.json](HOLDOUT_ROOTS.json) — the FINAL-slice firewall
- [../tiletie_term_20260814/DESIGN.md](../tiletie_term_20260814/DESIGN.md) —
  the failed guess-first attempt + the §7.2 route this executes
- [../tiletie_pricing_20260812/readout_POOLED/VERDICT.md](../tiletie_pricing_20260812/readout_POOLED/VERDICT.md)
  — the underlying headroom measurement (+0.252 pts/ply, z +3.43; untouched)
