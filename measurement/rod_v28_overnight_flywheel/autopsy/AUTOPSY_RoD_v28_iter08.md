# AUTOPSY — RoD v2.8 overnight-flywheel iter_08

**Date:** 2026-06-23 · **Branch:** rod_v28_overnight_flywheel · **MEASUREMENT ONLY.**
No promotion. PRODUCTION.yaml unchanged. Champion `flywheel2_champion_iter8` unchanged.
v2.7 frozen + bit-identical. v2.8 opt-in/experimental. All numbers from **cached match
records + on-disk training metadata** — no replay, no new games (see "open lever" §B/C).

Artifacts: `triangle_summary.csv`, `deck_margins_*.csv`, `training_curves.csv`,
`PART_ADE_digest.md`, `PART_FB_digest.md` (this dir). Generators:
`scripts/rod_v28/autopsy_cached.py`, `scripts/rod_v28/autopsy_rootaudit_metrics.py`.

---

## EXECUTIVE SUMMARY (10 lines)

1. **iter_08 is NOT a champion.** It reaches heur@3200_v2.8 parity, does not exceed it — identical to RoD1.
2. iter_08 vs heur@3200_v2.8: paired margin **−0.38 (z−0.48)**, a well-powered TIE (n=800).
3. RoD1 vs the same ruler: **−0.36 (z−0.47)** — *statistically indistinguishable* from iter_08.
4. So iter_08's **+33 elo / +2.23 paired (z2.0) over RoD1 buys ZERO ground vs the external ruler** — fully non-transitive.
5. That +33 is **concentrated**: the top 10% of decks carry 132% of the net margin (median deck +0.8 vs mean +2.23) — an RPS/exploit tail, not a broad skill edge.
6. **Training space confirms it:** iter_08 has among the *lowest* value_outcome_corr (0.397) and *highest* policy entropy (1.594) in the chain — not a value gain, not a sharper policy.
7. The value head **drifts DOWN** across the continuation (parent 0.510 → RoD1 0.413 → chain 0.36–0.49) — self-play is diffusing, not climbing.
8. **Root audit (executed, 1000 pos):** iter08≡h3200 0.521 ≈ RoD1 0.511 ≈ parent 0.520; iter08's divergence from RoD1 is net **+10 toward the ruler (z+0.7, NOT significant)** = orthogonal/style, confirmed at the move level — and the real gap is the **endgame** (iter08 moves *away* from the ruler there).
9. **Mechanism:** iter_08 = a noisy-screen-selected style/drift point that RoD1 specifically mishandles; neither agent out-plays the deep heuristic.
10. **Verdict:** keep-best parent = **conditional yes** (it is the chain's best, weakly); champion = **no**; gain = **RPS/style + selection noise**; blocker #2 stands. Stop blind RoD continuation; highest-EV next branch = **exact endgame-solver hybrid** (the one lever that can *exceed* a heuristic).

---

## Provenance

| agent | checkpoint | sha256 | leaf | search |
|---|---|---|---|---|
| iter_08 (OV best) | `rod_v28_overnight_flywheel/ckpt/iter_08.pt` | `5843b3cf…b1b6b` | v2.8 (v2_7+meeple_k2, FLAT, cap12, drop3) | NeuralMCTS s200 c3.0 resid0.25 |
| RoD1 (chain parent) | `rod_v28_continuation/ckpt/iter_01.pt` | `a8b824df…a1f4b` | v2.8 | NeuralMCTS s200 c3.0 resid0.25 |
| ITER8_V28_PARENT (champ) | `flywheel_residual_attempt2/ckpt/iter8.pt` | `0d355002…ee2c` | v2.7+resid0.25 (champ leaf) | NeuralMCTS s200 c3.0 resid0.25 |
| heur@3200_v2.8 (ruler) | — (HeuristicMCTS) | — | v2.8 leaf | HeuristicMCTS sims3200 c3.0 |

Match sets (cached, deck-paired both seats): iter08–RoD1 n=400 band 1.952e9; iter08–h3200 n=800 band 1.960e9;
RoD1–h3200 n=800 band 1.9221e9; RoD1–parent n=400 band 1.922e9; iter10–RoD1 n=400 band 1.953e9.
Per-game records hold WDL, A-relative score margin (`diff`), seed, seat, game length; **no move-level / root / policy data is cached** → Parts B/C need one new label run.

---

## Part A — match-level autopsy (the triangle)

| set | A vs B | W/D/L | winrate elo | paired margin | paired_z |
|---|---|---|---|---|---|
| iter08_vs_RoD1 | iter08 / RoD1 | 217/4/179 | **+33.1** | **+2.23** | **+2.00** |
| iter10_vs_RoD1 | iter10 / RoD1 | 211/3/186 | +21.7 | +0.74 | +0.69 |
| iter08_vs_heur3200 | iter08 / h3200 | 402/11/387 | +6.5 | **−0.38** | −0.48 |
| RoD1_vs_heur3200 | RoD1 / h3200 | 412/14/374 | +16.5 | **−0.36** | −0.47 |
| RoD1_vs_iter8parent | RoD1 / parent | 227/7/166 | +53.4 | +3.68 | +3.51 |

**Is iter_08's +33 vs RoD1 broad or narrow? → NARROW (concentrated exploit tail).**
- Deck-paired sign: 105 win / 0 tie / 95 loss — only **52.5% of decks** favor iter_08. Median deck margin **+0.8**, mean **+2.23** (right-skewed).
- **Top 10% of decks (20/200) contribute +587 paired pts = 132% of the net +446**; the other 180 decks net *negative* (−141).
- Win-margin shape: iter_08 has **109 blowout (≥20) wins vs RoD1's 74** (+47%), but close-game splits are even (33 vs 31). The edge lives in the blowout tail, not in converting close games.
- Seat: iter_08 stronger as seat-0 (+40.1 elo) than seat-1 (+26.1) — an asymmetry that differs from RoD1's (RoD1 vs parent is *stronger* at seat-1), consistent with style, not a uniform skill scalar.

**Read:** a real but thin win-rate edge riding on a concentrated blowout tail — the fingerprint of exploiting specific RoD1 lines, not of being broadly stronger.

## Part D — does h3200 parity hide a small edge? → NO usable edge.

iter08 vs h3200 (n=800): deck-paired **198 win / 6 tie / 196 loss** — dead even. By seat: seat-0 +14.8 elo (+0.39 margin), seat-1 −1.7 elo (−1.14 margin) — a small seat-0 lean fully given back at seat-1. Blowout tails symmetric (170 A vs 156 B). No slice in the *cached* (outcome-only) data shows iter_08 robustly beating h3200. (Tactical slices — K-remaining, meeple pressure, farm-heavy — are **not derivable from cache**; they need move-level replay. Flagged, not claimed.)

## Part E — RoD1 ↔ iter08 exploitability / RPS

The triangle is a clean **non-transitive cycle**: iter08 **>** RoD1 (+33), RoD1 **≈** h3200 (tie), iter08 **≈** h3200 (tie). iter_08 does **not** win by "playing more like the ruler" (the ruler itself only ties RoD1). It wins via a *third* style that RoD1 specifically handles worse — evidenced by the concentrated blowout tail (§A). h3200 does **not** punish RoD1 the same way: h3200's edge over RoD1 is a winrate lean (loses 210/wins 184 deck-pairs) with **~0 margin** (−0.36), i.e. broad-thin, whereas iter_08's is margin-tailed. Different opponents, different failure modes → the iter08 advantage is opponent-specific (RPS), which is exactly why it vanishes vs h3200. *Identifying the specific exploited RoD1 line needs the move-level audit (§B/C).*

## Part F — training / policy diagnostics

Per-iter final-epoch metrics (`training_curves.csv`). Cross-comparable signals: `value_outcome_corr`
(value head vs outcome) and `policy_entropy`. (val_pol/val_val are each iter's fit to its OWN self-play
val split → level not cross-comparable; VLW changed 1.0→1.5 at RoD1.)

| agent | VLW | value_outcome_corr | policy_entropy |
|---|---|---|---|
| PARENT champ (fw2_it8) | 1.0 | **0.510** | 1.530 |
| RoD1 (cont it01) | 1.5 | **0.413** | 1.543 |
| ov_it05 | 1.5 | 0.442 | 1.551 |
| **ov_it08 (best)** | 1.5 | **0.397** | **1.594** |
| ov_it15 | 1.5 | 0.488 | 1.557 |
| ov_it17 | 1.5 | 0.468 | 1.566 |
| (baseline warmstart) | — | — | 1.746 |

- **Value head is the weak link and it is *degrading*:** parent 0.510 → RoD1 0.413 → whole continuation 0.36–0.49. Within the clean same-recipe chain, **iter_08 (0.397) is among the *lowest* value_outcome_corr** — iter_15/16/17 are higher. iter_08 is *not* a value improvement.
- **Policy not sharpening:** entropy flat ~1.49–1.59; iter_08 (1.594) is among the *highest* (least peaked).
- **Conclusion:** iter_08's edge is **policy reshaping/DRIFT**, not value calibration and not policy concentration. Selected as keep-best off a noisy n=100 smoke (+49/z1.05 → regressed to +33/z2.0 at n=400); in training space it is unremarkable-to-weak. → "Is iter_08 a genuinely better policy, a value shift, a search interaction, or drift?" **Drift (a style offset), with selection noise — not a scalar improvement.**

## Part B (cached half) — root-move agreement: parent → RoD1 → h3200

On 1000 fixed midgame positions (`MIDGAME_REFERENCE_LABELS.jsonl` + `ROOT_AUDIT_V28.jsonl`),
top-1 root-move agreement vs the v2.8 deep ruler:

| band | n | RoD1≡h3200 | parent≡h3200 | RoD1≡parent | parent≠h3200 | rod_fixed_parent_miss |
|---|---|---|---|---|---|---|
| opening | 200 | 0.540 | 0.585 | 0.770 | 0.415 | 0.045 |
| early_mid | 200 | 0.570 | 0.595 | 0.675 | 0.405 | 0.075 |
| mid | 200 | 0.475 | 0.495 | 0.625 | 0.505 | 0.070 |
| late_mid | 200 | 0.480 | 0.475 | 0.625 | 0.525 | 0.055 |
| pre_endgame | 200 | 0.490 | 0.450 | 0.565 | 0.550 | 0.095 |
| **ALL** | 1000 | **0.511** | **0.520** | 0.652 | 0.480 | 0.068 |

- **Continuation does NOT move toward the ruler:** RoD1≡h3200 (0.511) is *below* parent≡h3200 (0.520).
- Of the 348 positions where RoD1 diverged from its parent: **toward h3200 = 68, away = 77, neither = 203 → net −9 (orthogonal/anti-aligned)**. RoD1 fixed only 14.2% of the parent's 480 ruler-disagreements.
- Yet RoD1 beats the parent +53 elo (§A) → **a +53 head-to-head from a reshaping that is orthogonal to the ruler** = the RPS mechanism, confirmed at the move level for the parent→RoD1 leg.
- Disagreement (and ruler sharpness) **concentrate in the endgame:** parent≠h3200 rises 0.415→0.550 opening→pre_endgame; teacher_gap_q (ruler decisiveness) is highest at pre_endgame (0.0343). The ruler's edge is an **endgame edge**.

## Part B/C — iter_08 root-move audit (EXECUTED: 1000 positions, NeuralMCTS@200, v2.8 leaf)

iter_08's own root choices, generated *identically* to the cached rod/parent labels (same
positions, leaf, sims, c_puct, `best_action` selector, net-on-CPU, per-position seed) → directly
comparable. (`iter08_root_labels.jsonl`, `root_disagreement_iter08.csv`, `PART_BC_digest.md`.)

| band | n | iter08≡h3200 | RoD1≡h3200 | parent≡h3200 | **Δ(iter08−RoD1)** | iter08≡RoD1 |
|---|---|---|---|---|---|---|
| opening | 200 | 0.570 | 0.540 | 0.585 | +0.030 | 0.645 |
| early_mid | 200 | 0.575 | 0.570 | 0.595 | +0.005 | 0.615 |
| mid | 200 | 0.530 | 0.475 | 0.495 | +0.055 | 0.540 |
| late_mid | 200 | 0.445 | 0.480 | 0.475 | **−0.035** | 0.530 |
| pre_endgame | 200 | 0.485 | 0.490 | 0.450 | −0.005 | 0.500 |
| **ALL** | 1000 | **0.521** | **0.511** | 0.520 | **+0.010** | 0.566 |

**Headline (Part B answer): iter_08's divergence from RoD1 is STATISTICALLY ORTHOGONAL to the ruler.**
- iter08 is only **Δ+0.010** more h3200-aligned than RoD1 overall. Toward/away decomposition: of the
  **434/1000 (43.4%)** positions where iter08 changed RoD1's move, **toward h3200 = 101, away = 91 → net +10**.
  SE(toward−away) ≈ √192 ≈ 13.9 → **+10/13.9 ≈ z+0.7, NOT significant.** iter08 did *not* become
  meaningfully more ruler-like (confirms the outcome-level "transfers 0" at the move level), and is not
  a pure anti-ruler style either. All three nets sit at **~0.51–0.52** ruler-agreement (parent 0.520 →
  RoD1 0.511 → iter08 0.521): the chain wobbled and netted ≈0 toward the deep heuristic.
- **The lean is band-split:** the (weak) toward-h3200 movement is in **opening/mid** (net +6, +11), but
  iter08 moves **AWAY in the endgame** (late_mid net −7, Δ−0.035; pre_endgame net −1) — exactly where
  ruler-agreement is *lowest* (0.445–0.485 vs 0.53–0.575 early) and the ruler is *most confident*
  (highest teacher_gap, L2-3 most endgame-precise). **The net's costliest, most persistent disagreement
  with optimal-ish play is the endgame, and the continuation does not close it.**

**Part C (lite) — distinctive signature moves.** iter08 has confident picks (root visit-share up to
0.935) that disagree with *both* RoD1 and h3200, clustering in mid→endgame. Several pair high
confidence with high root-value in won positions (e.g. `hybrid…s3503000011_K16` late_mid: iter08=1548
@93.5% visits, rootv 0.99, vs rod 747 / h3200 1324). Given the **weak value head** (value_outcome_corr
0.397), the high-confidence *endgame* divergences are as likely overconfidence as insight — i.e. the
signature is style, not demonstrated superiority. (Full list + the 25 top picks in `PART_BC_digest.md`;
move-level adjudication would need a small replay, deferred.)

**Net for the verdict:** the move-level audit *confirms* the RPS/style reading (orthogonal, z+0.7 NS)
and *localizes* the real skill gap to the **endgame** — direct support for next-lever #1.

## Part G — VERDICT

- **Real promoted champion?** **No.** iter_08 reaches heur@3200_v2.8 parity and does not exceed it (−0.38 paired, z−0.48, n=800), statistically identical to RoD1. Blocker #2 (learned must *exceed* the heuristic) stands at verdict power.
- **Keep-best parent?** **Conditional yes.** It is the chain's best checkpoint (+33/z2.0 over RoD1, the lone ≥2σ point), so it is the right warm-start *if* the continuation is resumed — but it is a *style* best, not a strength best, and the tail iters (11–17) tie it (iter_17 +6.3/z−0.16, n=384). Do not over-invest in it.
- **Its gain is:** mostly **RPS/style shift + selection noise** (concentrated blowout tail, transfers 0 to the ruler, training-space unremarkable). Not h3200-aligned improvement; not a scalar gain; the *real* signal that survives n=400 is genuine but opponent-specific.
- **Most likely bottleneck:** the **value head** (degrading value_outcome_corr) and the **hand-crafted leaf ceiling** — the learned components are at the heuristic's level, reshaping laterally (RPS) instead of climbing. Continuation self-play is **diffusing**, not improving.

### Next-branch EV ranking

1. **Exact / endgame-solver hybrid (HIGHEST EV).** The only lever that can *provably exceed* a heuristic: an exact solver out-plays h3200 in the endgame, where (a) the ruler's edge and decisiveness concentrate (§B: parent≠h3200 0.55, sharpest teacher_gap at pre_endgame), (b) L2-3 already named h3200 most endgame-precise, **(c) the executed iter_08 audit shows the net's ruler-agreement is *lowest* in late_mid/pre_endgame (0.445–0.485) and the continuation moves *away* there (net −7/−1) — the learned policy's costliest gap is the endgame and self-play is not closing it.** Bounded, concrete, attacks "exceed not match." The heuristic-handoff hybrids (l2hyb) only *tied* h3200 because they handed off to *another heuristic*; hand off to an **exact** endgame instead.
2. **Stronger ruler h6400/h12800 as a non-saturated MEASUREMENT reference (medium-high).** The measurement-first spec's real blocker is the absence of a non-saturated reference. If h3200 ≈ the heuristic's ceiling, h6400 tells us whether headroom even exists above parity. Cheap-ish; caveat: net gains wash out at high sims, so use it as a *ruler*, not a net-eval depth.
3. **v2.9 leaf feature search (medium, pessimistic prior).** A better leaf lifts the ruler AND the net's leaf equally (the v2.8 disambiguator already showed both rise, net still doesn't exceed) — EV-positive *only* if it adds a component the net can learn to exceed. Foundational audit is skeptical.
4. **Policy distillation from h3200 root visits (low standalone, good enabler).** `heur3200_visits` are cached — cheap supervised distillation pulls a net *to* the ruler (useful as a stronger fast policy / self-play teacher), but copying a teacher cannot *exceed* it. Pairs well with #1.
5. **Abandon blind RoD continuation (do regardless).** 16 iters produced one noise-selected style point, a degrading value head, no policy sharpening. Further undirected continuation iters will not break blocker #2.

**Diagnostic done (§B/C):** the iter_08 root-label audit was run — iter_08's divergence from h3200 *does* concentrate in the endgame (it moves *away* from the ruler in late_mid/pre_endgame while the ruler is most confident there). This is direct, executed evidence for #1 over #3.
