> ✅ **ADJUDICATED 2026-08-24** against the FROZEN `READ_RULE.md` (blind commit `3adab58bc268729d7f5b1d92af335f8344fe821a`). Branch taken VERBATIM.

# READOUT — track_d1_fair_rebase (G3: the fair ruler on the production instrument)

**BRANCH FIRED (READ_RULE §4, first-match-wins): `FR-RESCALED`**

**ERA SUB-ADJUDICATION (§4.2): `ERA-BOUNDED-NULL`**  ·  **ATTRIBUTION (§4.4, descriptive only): `RULES-BOUNDED-NULL`**

**Says:** the fair sub-ladder, re-measured on the production instrument (rust + `fixed_v1` + R9), resolves its own dynamic range and is monotone across its pure-budget rungs. The five `R_i` are the ruler of record's **absolute readings on the instrument production actually runs.**

**Licenses exactly this:** quoting `R_i` as the fair ladder's absolute readings for `fixed_v1`+rust measurements taken from here on; and the CL-046 amendment in READ_RULE §5.1.

**Does NOT license:** any re-rating of the champion; any re-grading of any existing claim; any statement about rungs outside {800,1600,2752,5504,11008}; any pooling with G1/G2 absolutes; and no statement about Δ₄ as a budget effect (DESIGN §3.2).

---

## 1. Per-cell (READ_RULE §4.3 items 1–3)

| cell | n | W/D/L | seat 0/1 | winrate (z) | elo ± 1σ | R_i ± se (z) | 95% CI | n_failed (rate) |
|---|---|---|---|---|---|---|---|---|
| A800 | 800 | 454/19/327 | 400/400 | 0.5794 (+4.49) | +55.6 ± 12.4 | +2.3850 ± 0.5541 (z=+4.30) | [+1.299, +3.471] | 0 (0.0000%) |
| B1600 | 800 | 511/19/270 | 400/400 | 0.6506 (+8.52) | +108.0 ± 12.9 | +5.4700 ± 0.6436 (z=+8.50) | [+4.209, +6.731] | 0 (0.0000%) |
| C2752 | 800 | 543/16/241 | 400/400 | 0.6887 (+10.68) | +138.0 ± 13.3 | +7.7550 ± 0.6314 (z=+12.28) | [+6.518, +8.992] | 0 (0.0000%) |
| D5504 | 800 | 540/15/245 | 400/400 | 0.6844 (+10.43) | +134.4 ± 13.2 | +8.9800 ± 0.6753 (z=+13.30) | [+7.656, +10.304] | 0 (0.0000%) |
| E11008 | 800 | 575/17/208 | 400/400 | 0.7294 (+12.98) | +172.2 ± 13.8 | +10.5650 ± 0.6548 (z=+16.13) | [+9.282, +11.848] | 0 (0.0000%) |
| W2752 | 800 | 537/10/253 | 400/400 | 0.6775 (+10.04) | +129.0 ± 13.1 | +7.7950 (z=+11.73) | — | 0 (0.0000%) |

**Failure classes:** none in any cell (`failed_cells == []` everywhere; the rate is stated even though it is zero, per §4.3 item 1).

| cell | champ_prefix ms/move (CANDIDATE side) | rung ms/move | ratio | solver s/game | realized s/game | mean moves/game |
|---|---|---|---|---|---|---|
| A800 | 148.9 | 1074.7 | 0.14× | 1.99 | 88.6 | 141.95 |
| B1600 | 290.9 | 1080.5 | 0.27× | 1.94 | 98.7 | 141.94 |
| C2752 | 473.0 | 1078.0 | 0.44× | 1.85 | 111.0 | 141.94 |
| D5504 | 888.0 | 1078.3 | 0.82× | 1.51 | 139.3 | 141.95 |
| E11008 | 1777.5 | 1075.9 | 1.65× | 1.62 | 200.6 | 141.95 |
| W2752 | 443.7 | 1068.1 | 0.42× | 1.36 | 109.3 | 143.90 |

⚠️ `champ_prefix_ms_per_move` is the **CANDIDATE** side in `eval_fair_puct` (the opposite convention from `eval_puct_priors`).

| cell | band | cand_leaf_hash | rung.leaf_hash | rules_profile (r9_env_ok) | backend / carc_rs | code_rev | tiearb | (k,s,total) |
|---|---|---|---|---|---|---|---|---|
| A800 | 145000000000 | `a36d2e15a3b3d71d` | `42af12fce22e1a0f` | fixed_v1 (True) | rust / 0.1.0 `8ae0b98427de` | `8bd68f848f-dirty` | False | (4, 200, 800) |
| B1600 | 145000000000 | `a36d2e15a3b3d71d` | `42af12fce22e1a0f` | fixed_v1 (True) | rust / 0.1.0 `8ae0b98427de` | `8bd68f848f-dirty` | False | (4, 400, 1600) |
| C2752 | 145000000000 | `a36d2e15a3b3d71d` | `42af12fce22e1a0f` | fixed_v1 (True) | rust / 0.1.0 `8ae0b98427de` | `8bd68f848f-dirty` | False | (4, 688, 2752) |
| D5504 | 145000000000 | `a36d2e15a3b3d71d` | `42af12fce22e1a0f` | fixed_v1 (True) | rust / 0.1.0 `8ae0b98427de` | `8bd68f848f-dirty` | False | (4, 1376, 5504) |
| E11008 | 145000000000 | `a36d2e15a3b3d71d` | `42af12fce22e1a0f` | fixed_v1 (True) | rust / 0.1.0 `8ae0b98427de` | `8bd68f848f-dirty` | False | (8, 1376, 11008) |
| W2752 | 145000000000 | `a36d2e15a3b3d71d` | `42af12fce22e1a0f` | walled (True) | rust / 0.1.0 `8ae0b98427de` | `8bd68f848f-dirty` | False | (4, 688, 2752) |

---

## 2. THE LADDER (§4.3 item 4)

All statistics over the **n_common = 400 decks** present in all five ladder cells; points/game of final-score margin, candidate-minus-rung, deck-paired.

| rung | R_i | se | z | 95% CI | winrate | elo |
|---|---|---|---|---|---|---|
| A800 | +2.3850 | 0.5541 | +4.30 | [+1.299, +3.471] | 0.5794 | +55.6 ± 12.4 |
| B1600 | +5.4700 | 0.6436 | +8.50 | [+4.209, +6.731] | 0.6506 | +108.0 ± 12.9 |
| C2752 | +7.7550 | 0.6314 | +12.28 | [+6.518, +8.992] | 0.6887 | +138.0 ± 13.3 |
| D5504 | +8.9800 | 0.6753 | +13.30 | [+7.656, +10.304] | 0.6844 | +134.4 ± 13.2 |
| E11008 | +10.5650 | 0.6548 | +16.13 | [+9.282, +11.848] | 0.7294 | +172.2 ± 13.8 |

| statistic | value | se_realized | se pre-registered (DESIGN §4.2) | z | 95% CI |
|---|---|---|---|---|---|
| Δ₁ = R_1600 − R_800 | +3.0850 | 0.8298 | 0.885 | +3.72 | [+1.459, +4.711] |
| Δ₂ = R_2752 − R_1600 | +2.2850 | 0.8607 | 0.885 | +2.65 | [+0.598, +3.972] |
| Δ₃ = R_5504 − R_2752 | +1.2250 | 0.8725 | 0.885 | +1.40 | [-0.485, +2.935] |
| Δ₄ = R_11008 − R_5504 | +1.5850 | 0.9104 | 0.885 | +1.74 | [-0.199, +3.369] |
| SPAN = R_11008 − R_800 | +8.1800 | 0.8455 | 0.885 | +9.67 | [+6.523, +9.837] |

⚠️ **Δ₄ is budget × ALLOCATION (k4→k8), not a pure budget increment** (DESIGN §3.2) — standing flag.

---

## 3. THE ERA BLOCK (§4.3 item 5)

| statistic | D_i | se_naive | CL-068 tax | se_eff | z_eff | G2 source row |
|---|---|---|---|---|---|---|
| D_2752 = R − 8.6425 | -0.8875 | 1.124 | ×2 | 2.248 | -0.39 | fair_ruler_rebase_2752 (G2, python, walled, band 24e9, k4) |
| D_5504 = R − 10.7825 | -1.8025 | 1.149 | ×2 | 2.299 | -0.78 | fair_ruler_rebase_5504 (G2, python, walled, band 24e9, k4) |
| D_11008 = R − 9.77 | +0.7950 | 1.137 | ×2 | 2.275 | +0.35 | fair_ruler_k8x1376_11008 (G2, python, walled, band 24e9, k8x1376) |

⛔ **No cross-era delta exists at 800 or 1600** — no same-allocation post-fix comparator exists in the repo. Those two rungs are **NEW ABSOLUTES** and are not compared to G1's leaky k8×{100,200} readings (READ_RULE §1, DESIGN §0.2 Q4).

**Says:** no era shift resolves at this power. **The bound is ±4.56 pts ≈ ±62 elo per rung.**

⛔ **This is NOT "the era does not matter."** For calibration, recorded before game 1: the *previous* era shift this cell is the sequel to — G1→G2, the leaky-determinization fix — was **+53.6 elo at the 2752 rung**, i.e. **inside this bound**. A design that could not have resolved the last era shift has not shown the next one is absent.

---

## 4. GATES AND WITNESSES (§4.3 item 6)

### §3A — LADDER gates

| gate | verdict | realized | address that resolved it |
|---|---|---|---|
| `G-BAND` | **PASS** | all five: seed_start=145000000000, n_decks=400, seatings_per_deck=2 | `config.seed_start` |
| `G-DECKS` | **PASS** | n_common=400; deck-set mismatches: none | `records` |
| `G-SINGLEVAR` | **PASS** | only the allowed axis keys differ | `config.*` |
| `G-REV` | **PASS** | code_rev=['8bd68f848f-dirty'] vs PINNED_SRC_REV=8bd68f848fcbadebe40042a97e8b8b90db42be8d; SRC_CLEAN boundaries=13 dirty=none missing=none | `code_rev / SRC_CLEAN.jsonl` |
| `G-BLIND` | **PASS** | blind_commit=3adab58bc268729d7f5b1d92af335f8344fe821a 40hex=True ancestor_of_HEAD=True introduced_FROZEN_banner=True blind_stamp_mode=manifest; manifest stamp == BLIND_COMMIT in all five: True | `BLIND_COMMIT + git (+ manifest, additive)` |
| `G-LEAF` | **PASS** | cand=a36d2e15a3b3d71d rung=42af12fce22e1a0f in all five | `config.cand_leaf_hash / config.rung.leaf_hash` |
| `G-RULES` | **PASS** | name=="fixed_v1" and r9_env_ok==true in all five | `rules_profile.name` |
| `G-BACKEND` | **PASS** | rust-resolved on every leg; carc_rs_version / binary_sha / tile_data_semantic_digest identical across legs | `config.backend.* (+ top-level mixed_builds)` |
| `G-RUNG` | **PASS** | HeuristicMCTS, c=3.0, sims=800 in all five | `config.rung.sims` |
| `G-BUDGET` | **PASS** | (4,200,800)/(4,400,1600)/(4,688,2752)/(4,1376,5504)/(8,1376,11008), products hold | `config.champion.k_dets` |
| `G-TIEARB` | **PASS** | enabled==false in all five | `cand_tiearb.enabled` |
| `G-EXACT` | **PASS** | exact_k=2, mode=marginalized, shared_by_both_arms=true in all five | `config.endgame.shared_by_both_arms` |
| `G-N` | **PASS** | A800: n=800 n_failed=0 rate=0.0000% \| B1600: n=800 n_failed=0 rate=0.0000% \| C2752: n=800 n_failed=0 rate=0.0000% \| D5504: n=800 n_failed=0 rate=0.0000% \| E11008: n=800 n_failed=0 rate=0.0000% | `summary + records` |
| `G-SAT-END` | **PASS** | A800 wr=0.5794, E11008 wr=0.7294 both inside [0.5,0.9] | `summary.winrate` |
| `RECON (READ_RULE §1)` | **PASS** | analyzer == from-scratch witness on every checked statistic | `summary vs records` |

### §3B — ATTRIBUTION gates (a FAIL here voids E4 alone, never the ladder)

| gate | verdict | realized | address |
|---|---|---|---|
| `GW-RULES` | **PASS** | name='walled' r9_env_ok=True r9_env_observed=False (expected=False) -- INVERTED expectation: walled requires R9 OFF | `rules_profile.name` |
| `GW-PAIR` | **PASS** | config blocks differ only in the allowed keys | `config.*` |
| `GW-DECKS` | **PASS** | n_common(C,W)=400; sets equal=True | `records` |
| `GW-N` | **PASS** | n=800 n_failed=0 rate=0.0000% | `summary + records` |
| `GW-SAT` | **PASS** | W2752 winrate=0.6775 vs [0.5,0.9] | `summary.winrate` |

### WITNESSES (printed on every branch, never voiding)

- **`G-SAT-MID`** — B1600=0.6506; C2752=0.6887; D5504=0.6844  [inside]
- **`W-TIMING`** — A800=1074.7; B1600=1080.5; C2752=1078.0; D5504=1078.3; E11008=1075.9; W2752=1068.1  spread=1.2%  [within +/-25%]
- **`W-COST`** — A800: realized 88.6 s/game vs DESIGN §6 local model 54.8 (+61.8%); B1600: realized 98.7 s/game vs DESIGN §6 local model 63.2 (+56.3%); C2752: realized 111.0 s/game vs DESIGN §6 local model 75.3 (+47.4%); D5504: realized 139.3 s/game vs DESIGN §6 local model 104.3 (+33.6%); E11008: realized 200.6 s/game vs DESIGN §6 local model 162.2 (+23.7%); W2752: realized 109.3 s/game vs DESIGN §6 local model 75.3 (+45.1%)
- **`W-SCALE`** — realized elo/pt: LS-slope 16.74, mean per-cell ratio 18.43, committed 13.7
- **`W-GAMELEN`** — C2752 mean moves/game 141.94 vs W2752 143.90 (delta +1.96)

---

## 5. THE ATTRIBUTION BLOCK (§4.3 item 7 / §4.4)

**Standing flag: descriptive; NOT a branch input (READ_RULE §4.4). The `FR-*` branch above is mechanically identical whether this cell ran clean, ran dirty, or was never funded.**

| statistic | value | se realized | se pre-registered | z | 95% CI | elo-equivalent |
|---|---|---|---|---|---|---|
| A = C2752(`fixed_v1`+R9) − W2752(`walled`, R9 OFF) | -0.0400 pts | 0.9080 | 0.885 | -0.04 | [-1.820, +1.740] | -0.7 elo (@16.74 elo/pt realized) |

- `n_common(C,W)` = **400** decks · C2752 absolute **+7.7550** · W2752 absolute **+7.7950**
- **RESIDUAL** `D_2752 − A` = **-0.8475** pts, carrying the ×2-inflated se it inherits (**2.248**). ⛔ A LEFTOVER — never presented as an estimate of the band effect.
- ⭐ No CL-068 tax on `A`: within-band, same-code, deck-paired, same 400 decks — the robust class.

**Says:** no rules effect resolves at this power. **The two-sided 95% bound is ±1.77 pts ≈ ±24 elo at the 2752 rung.** This is a genuinely informative bound — 2.6× tighter than the E3 era screen and it is within-band — but it is **a bound, not a zero**, and this readout says so in those words.

**Licenses:** stating the bound in the READ_RULE §5.1 annotations. **Does NOT license:** "the rules change is strength-neutral", or dropping the era caveat from any annotation.

---

## 6. THE GENERATION TABLE (§4.3 item 8), G3 row filled in

| generation | when | candidate side | backend | rules | band | n | reading @2752 |
|---|---|---|---|---|---|---|---|
| **G1 — CL-046 (D0)** | 2026-07-09 | fair PIMC, k8×sims/det, pre-CL-056 leaky determinization | python | pre-`fixed_v1` (walled) | 15e9 | 200 decks | **+81.4 elo** |
| **G2 — F5 rebase** | 2026-07-19/20 | fair PIMC, k4/k8, post-CL-056, curve125 leaf `a36d2e15` | python | pre-`fixed_v1` | 24e9 | 200 decks | **+135.0 elo / +8.6425 pts** |
| **G3 — THIS CELL** | 2026-08-24 | same agent family, same leaf, same rung | **rust** | **`fixed_v1` + R9** | **145e9** | **400 decks** | **+138.0 elo / +7.7550 pts** |

---

## 7. ANALYZER-vs-WITNESS RECONCILIATION (READ_RULE §1)

30 statistics checked across all six cells (`paired_mean_margin`, `paired_z`, `n_paired`, `winrate`, `elo`): **ALL AGREE** within float tolerance (rel 1e-6). The analyzer of record is `scripts/classical_search/eval_fair_puct.py` (each cell's `summary.json`); the witness is an independent from-scratch recomputation from the raw `seed*_a*.json` records. **The recomputation is a WITNESS, never a branch input.**

---

## 8. ANOMALIES AND NOTES (non-adjudicative; no bar in §4 moves)

1. **`W-COST` overshoots by more than the pilot projected.** The frozen h800 rung realized **1068–1080 ms/move** on the laptop across all six cells — vs the DESIGN §6 local calibration of **624.3** (**+73%**) and vs the §6.2.1 pilot's own laptop reading of **781.8** (**+38%**). Realized wall was **166.1 core-h** against the §6.1 funded roll-up of **118.8 core-h** (**+40%**). `W-COST` is a **WITNESS, never voiding** (READ_RULE §3), and the §6.2.1 amendment already accepted the overage class — but the realized overage is larger than the +25.23% the amendment re-costed against, so the ≈6.75 h re-projection under-predicted the realized wall (08:58→16:36 ≈ 7.6 h). **This changes no statistic and no branch.**
2. **The realized elo scale is steeper than the committed one.** `W-SCALE` reads **16.74 elo/pt** (least-squares through origin over the five rungs; 18.43 as a mean of per-cell ratios) against the DESIGN §4.5 committed **13.7**. Elo displays in this readout therefore run ~20–35% larger than the pre-registered conversion would give. **No bar in `READ_RULE.md` is ever set in elo** (§2), so nothing moves; the pre-registered elo-equivalents quoted in the branch texts (±62 / ±24 elo) are kept verbatim at the committed 13.7, exactly as the frozen text states them.
3. **Monotone in the PRIMARY unit, non-monotone in the DISPLAY unit at one rung.** The pre-registered primary statistic (deck-paired points) rises at every rung — Δ₁…Δ₄ are all positive. The derived winrate/elo display dips at D5504 (**+134.4 elo** vs C2752's **+138.0**, winrate 0.6844 vs 0.6887) while R_5504 > R_2752 by Δ₃ = +1.2250 pts. The dip is inside noise (Δ₃ z = +1.40) and the branch bar is on points, not elo — but a reader quoting the elo column alone would see a bend that the ruler does not have.
4. **The top of the ladder is flat at this power.** Δ₁ (z=+3.72) and Δ₂ (z=+2.65) resolve; Δ₃ (z=+1.40) and Δ₄ (z=+1.74) do **not** individually resolve at n=400 decks. 66% of `SPAN` comes from the 800→2752 stretch. This is the DESIGN §6 house prior almost exactly ("a large, easily-resolved SPAN driven almost entirely by the 800→2752 stretch, and a flat-to-bending top") — but note the branch table asks only whether any of Δ₁–Δ₃ is ≤ −2σ, and none is, so `FR-RESCALED` fires rather than `FR-RESCALED-BENT`. **Unresolved is not negative.**
5. **`W-GAMELEN` shows the expected `walled` signature.** W2752 runs +1.96 moves/game longer than C2752 — the `centered18`+`redraw` rules change, visible and small.
6. **The frozen pair carries two different G2 values for the 11008 rung — the branch is robust to which one is right.** `READ_RULE.md` §1 pre-registers `D_11008 = R_11008 − 9.7700` (`fair_ruler_k8x1376_11008`), while `DESIGN.md` §4.1 quotes that same row's realized paired mean as **7.9350** (7.9350 / 8.4547 = 0.939 pts se). This adjudication uses **READ_RULE's 9.7700**, because READ_RULE is the frozen instrument and §1 is where the comparator is pre-registered. Recorded for audit: against 7.9350 the reading would be `D_11008 = +2.6300`, `z_eff = +1.16` — **still under the 2.0 bar, so `ERA-BOUNDED-NULL` fires either way** and no branch depends on resolving the discrepancy. It should be reconciled before the G2 rows are cited again.
7. **`moves` counts plies, not per-side moves.** The per-cell mean of ≈142 is ≈71 per side, which is the ≈70/71 the DESIGN §6 cost model assumes — not a discrepancy.

---

## 9. WHAT THIS READOUT DOES NOT DO (READ_RULE §5)

- Does **not** touch `governance/PRODUCTION.yaml`, on any branch. Nothing here is a strength lever.
- Does **not** re-rate the champion — every `R_i` is a reading against the fixed h800 rung.
- Does **not** re-grade any existing claim; §5.1 claims get **ANNOTATED**, never re-graded.
- Does **not** edit CL-046's G1 numbers or the five G2 `fair_ruler_*` rows in `experiments/results.csv`.
- Does **not** pool this band with any other band, or license a second band or more n.
- Does **not** unpark E4 (the human anchor), or fund DESIGN §6.3 (a)–(c).


---

## ADDENDUM 2026-08-26 — the §6-flagged G2 comparator discrepancy is RECONCILED

Adjudication note 6 above flagged that the frozen pair carried two values for the 11008 G2 row
(`READ_RULE.md` §1: 9.7700; `DESIGN.md` §4.1: 7.9350) and asked for reconciliation before the G2
rows are cited again. Resolved against the cells' own `summary.json` (source of truth, share):

| cell | paired_mean_margin | paired_z |
|---|---|---|
| `fair_ruler_k8x1376_11008` (k8×1376) | **9.765** | 9.866 |
| `fair_ruler_rebase_11008` (k4×2752) | **7.935** | 8.455 |

**DESIGN §4.1 mislabeled a row**: it quoted `fair_ruler_rebase_11008`'s realized 7.9350/8.4547
under the `fair_ruler_k8x1376_11008` label. READ_RULE's pre-registered comparator 9.7700 matches
the named row (9.765 ≈ 9.77, the results.csv margin) and was the correct value; the adjudication
above therefore used the right number, and the ERA-BOUNDED-NULL verdict was already shown robust
to either. Downstream: `measurement/track_d2r3_prep/DESIGN.md` §4.1 copied the same mislabeled
line into its dispersion table; with the correct row, se(M) for that cell is 9.765/9.866 = 0.990
pts (not 0.939), moving the three-row average se(M) from ≈0.93 to ≈0.95 — the d2r3 MDE band
(33–40 elo) is unchanged at that precision. The d2r3 pair is frozen; this note is the record, and
its DESIGN gets an era annotation at close-out rather than an edit.
