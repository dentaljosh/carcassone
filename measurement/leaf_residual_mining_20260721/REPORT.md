# REPORT — Leaf residual-mining (error-guided leaf-term discovery)

> **⚠️ STATUS 2026-07-21 — CLOSED. Verdict = AMBIGUOUS at the floor of the ambiguous
> band (one candidate, ρ = +0.0507 against a 0.05 null floor) — operationally a
> **powered null**. No HIT. No S1 launched (PREREG §6 reserves that call for Joshua).
> Champion and `governance/PRODUCTION.yaml` UNTOUCHED.** Claim **CL-063**.
> Gate + dictionary fixed in advance → [PREREG.md](PREREG.md) (committed `ffe37c8`,
> 14:31:45, ~2h before the first fit at 16:24:54). Canonical numbers →
> [ANALYSIS_688_pooled.json](ANALYSIS_688_pooled.json) ·
> [ANALYSIS_688_maxq.json](ANALYSIS_688_maxq.json). Every figure below is read from
> those files; none is transcribed from a run log.

## 1. The question, and why it was worth asking

CL-062 established the mechanism behind every washout on this ledger: the policy-prior
channel's influence **decays with search depth via Q-convergence**. In this champion the
prior *is* the heuristic leaf — so search is superseding the leaf's 1-ply opinion with the
leaf's own n-ply backup. That relocates the improvement target: not root-move fidelity,
but **the leaf's accuracy on deep midgame boards**.

So instead of guessing leaf terms (C7's approach — both terms died, CL-055), measure the
leaf's actual error and ask what predicts it:

```
resid = V_deep(688) − V_leaf
```

where `V_deep` is the pooled visit-weighted root Q of the **deployed** fair-PIMC champion
at k4×688 = 2752 sims. A feature that predicts this error names a missing leaf term, with
the error itself pointing at it.

## 2. What was pre-registered (verbatim from PREREG.md, fixed before any fit)

**Statistic.** OOS partial correlation ρ of each candidate with `resid`, cross-fitted
5-fold **grouped by deck seed** (never by position — positions within a game are
correlated). Both sides partialled on `{1, v_leaf, v_leaf², tiles_remaining, corpus}` so a
candidate cannot win by re-encoding the leaf value or game stage. p-values from a
**game-clustered bootstrap** (2000 resamples of whole games). **Holm–Bonferroni** over the
**K = 18** family (BH-FDR reported as secondary).

**Cost tiering** (a term must be cheap enough to live in a leaf that runs millions of times):
**A** = leaf-viable · **B** = leaf-viable, different functional form from a killed family ·
**C** = diagnostic only, needs move generation, *cannot* become a leaf term.

| verdict | rule |
|---|---|
| **HIT** | \|ρ\| ≥ **0.10** AND Holm p < 0.05 AND tier ∈ {A,B} AND same-signed replication with \|ρ\| ≥ 0.05 |
| **AMBIGUOUS** | Holm p < 0.05 with **0.05 ≤ \|ρ\| < 0.10**; OR ≥ 0.10 failing replication; OR ≥ 0.10 but tier C |
| **NULL** | nothing reaches Holm p < 0.05 with \|ρ\| ≥ 0.05 |

The band 0.05 ≤ \|ρ\| < 0.10 was **named as ambiguous in advance**, and the NULL floor was
placed at the design's detection limit by construction — so a NULL here is a *powered*
null for effects ≥ 0.05, not a failure to look.

## 3. Validity — the run is sound

| check | result |
|---|---|
| Labeling failures | **0** — 10,047 / 10,047 roots ok, 0 exact latches |
| Negative control (`blake2b` noise) | ρ = **+0.0051**, p = 0.664, CI [−0.0158, +0.0247] → in the null band, as required |
| `V_leaf` provenance | matches Gate-B's independently recorded `root.leaf_value` on all **436** shared roots to **3e-8** (float32-vs-float64 only) |
| Clustering | ICC 0.0152, design effect 1.030, **n_eff = 8443** of 8700 |
| Residual scale | mean +0.0572, sd 0.1415 |

The negative control mattering is not a formality: it is the evidence that this pipeline
*can* return nothing when nothing is there, which is what licenses reading the main result
as a null rather than as a weak search.

## 4. Results — primary, L = 688, pooled-Q target (n = 8700 roots / 2900 games)

Full family, ranked by |ρ|. `repl` = same statistic on the champion's own games.

| feature | tier | ρ | CI95 | p | Holm p | repl ρ |
|---|---|---|---|---|---|---|
| `pos_ref_c5_curve` *(positive ref, outside family)* | — | −0.0822 | [−0.1042, −0.0598] | 0.0005 | — | −0.0812 |
| **`bonus_overflow_self`** | **A** | **+0.0507** | [+0.0198, +0.0813] | 0.0005 | **0.009** | **+0.0786** |
| `cloister_far_diff` | A | +0.0475 | [+0.0264, +0.0674] | 0.0005 | 0.009 | +0.0222 |
| `open_city_liability_diff` | A | +0.0413 | [+0.0184, +0.0646] | 0.0005 | 0.009 | +0.0769 |
| `bonus_overflow_opp` | A | −0.0340 | [−0.0569, −0.0127] | 0.0010 | 0.015 | −0.0298 |
| `n_legal` | **C** | +0.0319 | [+0.0111, +0.0540] | 0.0010 | 0.015 | +0.0470 |
| `free_meeples_sum` | A | +0.0237 | [+0.0028, +0.0453] | 0.0220 | 0.286 | +0.0677 |
| `pending_diff` | A | +0.0227 | [+0.0003, +0.0443] | 0.0470 | 0.564 | −0.0291 |
| `pending_share` | A | +0.0142 | [−0.0094, +0.0370] | 0.212 | 1.000 | −0.0280 |
| `deck_city_share` | B | −0.0128 | [−0.0336, +0.0083] | 0.242 | 1.000 | +0.0135 |
| `stuck_meeple_diff` | A | −0.0112 | [−0.0359, +0.0121] | 0.349 | 1.000 | +0.0330 |
| `hopeless_city_diff` | A | −0.0104 | [−0.0319, +0.0105] | 0.324 | 1.000 | −0.0088 |
| `running_diff` | A | +0.0103 | [−0.0110, +0.0310] | 0.336 | 1.000 | +0.0564 |
| `road_anticip_diff` | A | −0.0102 | [−0.0336, +0.0129] | 0.378 | 1.000 | −0.0352 |
| `open_frontier` | A | +0.0101 | [−0.0103, +0.0316] | 0.327 | 1.000 | −0.0257 |
| `leaf_x_tiles` | A | −0.0063 | [−0.0229, +0.0090] | 0.424 | 1.000 | −0.0193 |
| `barren_farm_diff` | A | +0.0060 | [−0.0145, +0.0335] | 0.670 | 1.000 | +0.0072 |
| `neg_control` *(outside family)* | — | +0.0051 | [−0.0158, +0.0247] | 0.664 | — | −0.0024 |
| `city_exposure_diff` | A | +0.0044 | [−0.0164, +0.0250] | 0.702 | 1.000 | +0.0183 |
| `frontier_x_leaf` | A | +0.0040 | [−0.0116, +0.0214] | 0.612 | 1.000 | +0.0337 |

**Only `bonus_overflow_self` clears the 0.05 floor — by 0.0007.** It is the closure bonus
lost to the `cap=8` truncation (the *truncation*, not the cap *level*, which C5/v2.10
already killed).

Collinearity worth knowing when reading the table (|r| ≥ 0.5 among candidates):
`frontier_x_leaf ~ leaf_x_tiles` +0.90 · `pending_diff ~ pending_share` +0.87 ·
`open_city_liability_diff ~ city_exposure_diff` +0.82 · `hopeless_city_diff ~ city_exposure_diff` +0.75 ·
`running_diff ~ frontier_x_leaf` +0.75 · `running_diff ~ leaf_x_tiles` +0.68 ·
`open_frontier ~ free_meeples_sum` −0.54 · `open_frontier ~ n_legal` +0.53.

**Several long-standing "never tested" items died quietly here**, which is part of the
value: `open_city_liability_diff` is BACKLOG 2026-05-16 #2 ("penalize large open cities"),
the one lit-review term never implemented — it lands at +0.0413. `road_anticip_diff`
(review P1-L6, roads get *exactly zero* bonus in the leaf, never isolated because C7's
Term R bundled them) lands at **−0.0102**, indistinguishable from noise. `pending_diff` /
`running_diff` together were the direct test of the leaf's 1:1 banked-vs-pending weighting
(review P1-L2, never directly tested) — both null. `deck_city_share` is the 4th
independent confirmation for the deck-aware-closure family.

## 5. The yardstick — this is what settles it

The pre-registered comparator: **CL-051's curve125**, a leaf change that actually shipped
at **+66.8 elo clairvoyant / +48.8–50.4 fair-confirmed**, retro-scored on the *identical*
statistic against the residual of the pre-CL-051 leaf:

| | ρ |
|---|---|
| CL-051 curve125 (a real, shipped leaf win) | **+0.1679** [+0.1443, +0.1904] |
| `bonus_overflow_self` (best survivor here) | **+0.0507** [+0.0198, +0.0813] |
| ratio | **30%** |

**Converted to leaf units:** the survivor implies a correction of ~**0.15 leaf points per
1σ**, against a leaf sd of **12.02 points**, binding on **16.4%** of roots. That is ~1% of
leaf scale on a sixth of positions.

**Joint** OOS R² of the entire 17-feature leaf-viable dictionary (over and above the
controls): **+0.0128** [+0.0071, +0.0187] — statistically real, practically negligible.
Controls alone reach R² 0.0438; controls + all candidates 0.0570.

## 6. Replication, depth, and a second target — all consistent

**Replication** on the champion's own 1,347 roots / 449 games (n_eff 1332.6):
`bonus_overflow_self` **+0.0786**, same sign, above the 0.05 replication bar — so the
survivor is real, just small. Note `cloister_far_diff` fades to +0.0222 on replication
while `open_city_liability_diff` strengthens to +0.0769; neither changes the verdict.

**Depth trend** — the effect is flat in search depth, i.e. not an artifact of one budget:

| L | resid mean | `bonus_overflow_self` | neg control | pos ref |
|---|---|---|---|---|
| 200 | +0.0323 | +0.0587 | +0.0093 | −0.0851 |
| 344 | +0.0438 | +0.0532 | +0.0062 | −0.0880 |
| 688 | +0.0572 | +0.0507 | +0.0051 | −0.0822 |
| 1376 | +0.0676 | +0.0501 | +0.0042 | −0.0731 |

The residual itself grows with depth (the leaf falls further behind deeper search, as
Q-convergence predicts) while the survivor's ρ mildly *shrinks* — the extra error deep
search finds is **not** the part this feature explains.

**Secondary target** (max-child-Q instead of pooled-Q) reproduces: verdict AMBIGUOUS, same
single candidate, ρ = **+0.0508**.

## 7. Free passes — hypothesis-only, and they did not survive

Run first on data already on disk, labeled hypothesis-generating in advance because both
sets are **endgame-bounded** and therefore ineligible to pass or fail the gate:

- **436** champion K=3 roots (fair-PIMC target): verdict **NULL** — nothing survives Holm.
- **216** exact-solver-**solved** F3 roots, scored against *truth* rather than deep search:
  `running_diff` +0.212, `road_anticip_diff` +0.188, `open_city_liability` −0.185. (138
  budget-hit records excluded.)

**None of these carried into the powered midgame test**, and the two free passes
**disagree on sign** for `road_anticip_diff` and `open_city_liability_diff`. Had the
endgame roots been allowed to gate — the tempting shortcut, since they were free — this
cell would have reported a hit that the real test does not support. The
hypothesis-only labeling was load-bearing.

## 8. Verdict, and what it does and does not close

**AMBIGUOUS by the pre-registered rule; a powered null in substance.** Three independent
reasons the conversion case is weak:

1. **30% of the yardstick** — and the yardstick is a term that shipped for ~+50 fair elo.
2. **~1% of leaf scale**, binding on 16.4% of roots.
3. **Prior art on the same knob is a run of nulls** — `phase4_capInf_vs_cap12` (cap removed
   entirely) −0.9 ± 17.6 (n=390, river-era); `v210_cap6_vs_cap8` +4.3 ± 17.4; C5 cap5 0.0,
   cap12 −13.9.

**What this closes:** the **cheap-leaf-term channel as an autonomous lever** — now the
error-guided counterpart to what C7 (CL-055), CL-034 and CL-036 closed by guessing. The
leaf's error against its own deep backup is *not* predicted to any convertible degree by
cheap, interpretable, leaf-viable board features. Combined with CL-061 (value transform)
and CL-051 (the curve, which already soaked the extractable headroom), the hand-crafted
leaf is measured out.

**What this does NOT close** — stated so nobody over-reads it: features requiring a **new
traversal, move generation, or parent→child structure** were out of scope *by
construction*, because they cannot be cheap leaf terms. The one tier-C diagnostic
(`n_legal`, +0.0319) was included precisely to check whether the residual is mostly "how
many options does the mover have" — a *search* story rather than a leaf story. It is
significant but small, so the answer is mostly no.

**Recommendation (overrulable):** do not fund S1 for `bonus_overflow_self`. PREREG §6
reserves the AMBIGUOUS decision for Joshua.

## 9. Provenance

- Roots: 8,700 primary (F0b′ corpora — `windowaudit` 4,200 + `champ125` 4,500) + 1,347
  champion replication = **10,047**, 3 roots/game, `k_dets=4`, levels {200, 344, 688, 1376}.
- Compute: laptop only, W12, ~95 min. Local box untouched (it was running B3).
- Code: `mine_residual.py` · `leaf_features.py` · `analyze_residual.py`; 22 contract tests
  in `tests/test_leaf_residual_mining.py` (green).
- Close-out commit `ed0b217`; registry row **CL-063**; results.csv row
  `leaf_residual_mining_midgame`.
