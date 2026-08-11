# F0b′ — utility calibration on the TRUE v2.9 LEAF margin (2026-07-21)

**Status: DONE — NO-GO / thread effectively CLOSED.** Follow-up to [../utility_calibration_20260719/REPORT.md](../utility_calibration_20260719/REPORT.md) (F0b), mandated by [../../docs/reviews/REVIEW_ADOPTION_20260719.md](../../docs/reviews/REVIEW_ADOPTION_20260719.md) item 2. Claim **CL-061**. Numbers below independently re-verified off `calibration_stats_*.json` before write-up.

**Verdict in one line:** the 07-19 finding "`tanh(m/15)` is ~2× too steep and saturates by ±25–30 (T\*≈31)" was **largely an artifact of the RAW score margin**. On the margin the search actually consumes — the v2.9 leaf — the best-fit denominator is **T\*≈19–20** (≈1.27–1.33× too steep, not 2×), the tail-saturation failure **disappears**, and the global calibration gap **collapses ~6–9× in out-of-sample log-loss** (raw +0.043 → leaf +0.005/+0.007 nats). The gap survives statistically (T\* CI excludes 15) at a magnitude that does not justify an online gate.

## 1. Feasibility — the leaf margin is NOT recoverable from the 07-19 corpus

**Not recoverable; a fresh replayable sample was built instead. No proxy was substituted.**

The 07-19 shards (`distill_flywheel_sighted_20260716/iter_XX/seed_*.npz`) hold encoded **planes** `boards (144,81,25,25)` + `scalars (144,42)`, with **no action sequence** (deck seed only in the filename), and the manifest records `move_selected_by: pooled_q_argmax` — so `argmax(policies)` is *not* the played move and the trajectory cannot be reconstructed from the policy either. No planes→`CarcassonneGameState` decoder exists anywhere in `src/` or `scripts/`. The v2.9 leaf (`flat_leaf.flat_virtual_score_v2_float`) needs a real engine state (union-find over tiles/meeples/deck), so planes are unusable.

Two independent losslessly-replayable corpora were used instead (`(deck_seed, actions)` → exact board at every ply via `scripts/measurement_infra/root_replay.py`):

| tag | corpus | games | positions | generating policy |
|---|---|---|---|---|
| `windowaudit` | `measurement/window_audit/gen_games.jsonl` (existing, 07-05) | 1,400 | 201,482 | HeuristicMCTS sims=100, curve100 + meeple_k=2.0 |
| `champ125` | `gen_games_champ125.jsonl` (**generated for F0b′**, ~28 min local W24) | 1,500 | 215,887 | HeuristicMCTS sims=100 under `champ_env.sh` — the **curve125 champion leaf** |

For every ply, `extract_margins.py` logs mover-POV `m_raw` (= `state.scores[mover] − state.scores[opp]`, the exact 07-19 column, recomputed **within-sample** so raw-vs-leaf is not confounded by corpus), `m_leaf` (= `flat_virtual_score_v2_float(...)`, byte-identical to the search's value line), `tiles_remaining`, and the win label from the actual final score.

Leaf provenance verified at runtime: curve125 `(-10,-5,-1.25,0,2.5,3.75,5,6.25)`, caps 8/8, `_frozen_config_hash = 6dfffd57051690f2` (the hash `champ_env.sh` asserts); Cython flat leaf cross-checked **288/288 exact** against the object path. Estimators are **imported by path** from the 07-19 script — no re-typing, no drift; the 07-19 script was not edited.

## 2. Headline — leaf vs raw on the identical sample

95% CI = bootstrap **over games**, n_boot=200.

| sample | margin | **T\*** | 95% CI | vs audited 15 | margin sd |
|---|---|---|---|---|---|
| windowaudit | **leaf** | **19.00** | [18.00, 21.00] | **1.27×** | 13.49 |
| windowaudit | raw | 30.05 | [27.12, 33.25] | 2.00× | 14.01 |
| champ125 | **leaf** | **20.00** | [18.67, 21.00] | **1.33×** | 13.13 |
| champ125 | raw | 31.12 | [29.17, 33.30] | 2.07× | 13.38 |

**The raw control reproduces 07-19's T\*≈31 on two fresh corpora** → the corpus swap is benign and the leaf-vs-raw difference is genuinely the *margin definition*. Note the leaf margin's sd is **smaller** than raw's, so `T*_leaf < T*_raw` runs *against* the scale direction — it is not a rescaling artifact.

**Saturation** (stage-pooled implied `T_imp = m̄ / atanh(2p̂−1)`):

| bucket | leaf p̂ | leaf tanh15 | leaf T_imp | raw p̂ | raw tanh15 | raw T_imp |
|---|---|---|---|---|---|---|
| [25,30) | 0.9685 | 0.9740 | 15.9 | 0.8801 | 0.9730 | 27.0 |
| [30,35) | 0.9763 | 0.9865 | 17.3 | 0.9354 | 0.9858 | 23.8 |
| [35,40) | 0.9889 | 0.9930 | 16.5 | 0.9453 | 0.9927 | 25.8 |
| [40,45) | 0.9950 | 0.9963 | 15.9 | 0.9666 | 0.9961 | 24.8 |

On **raw**, `tanh(m/15)` is badly overconfident in the tail (predicts 0.996 at m=+42, truth 0.967). On **leaf** it is essentially correct (0.996 vs 0.995), implied T ≈ 16 — near the audited 15. **"Saturates by ±25–30" does not survive on the leaf margin.** The leaf's residual mis-calibration is a mild *flattening near m≈0* (T_imp ≈ 24–25 for |m|<5), which is what drags the single-T fit to 19–20.

## 3. Does a global gap SURVIVE on the leaf margin?

OOS log-loss, 2-fold **by game**. M0 = `tanh(m/15)`; M1 = best global T; M2 = per-tile-band T; M3 = per-band isotonic; M4 = stage-free isotonic.

| sample | model | leaf LL | leaf ΔLL | raw LL | raw ΔLL |
|---|---|---|---|---|---|
| windowaudit | M0 tanh15 | 0.5666 | — | 0.6613 | — |
| windowaudit | M1 global T\* | 0.5616 | **+0.0050** | 0.6184 | **+0.0429** |
| windowaudit | M4 global isotonic | 0.5611 | +0.0055 | 0.6181 | +0.0432 |
| windowaudit | M2 stage T | 0.5469 | +0.0197 | 0.6150 | +0.0463 |
| champ125 | M0 tanh15 | 0.5812 | — | 0.6700 | — |
| champ125 | M1 global T\* | 0.5738 | **+0.0074** | 0.6256 | **+0.0445** |
| champ125 | M4 global isotonic | 0.5732 | +0.0081 | 0.6259 | +0.0442 |
| champ125 | M2 stage T | 0.5591 | +0.0221 | 0.6222 | +0.0479 |

**It survives statistically, collapses practically.** T\* CI excludes 15 with the same sign as raw — but the OOS log-loss purchased drops from **+0.043 nats (raw, ~6.5% rel.)** to **+0.005/+0.007 (leaf, ~1% rel.)**, a **6–9× reduction**. M4≈M1 on leaf ⇒ **no monotone reshaping of the leaf margin buys more than ~0.006–0.008 nats**: the functional form `tanh(·/15)` is near-optimal for this margin; only the denominator is slightly off.

**Side-finding that also reverses 07-19.** The "stage-dependence is only 7.7% of the gap" decomposition is *itself* a raw-margin artifact. Share of the total available gain (M2−M0):

| sample | margin | total ΔLL | global-T share | **stage share** |
|---|---|---|---|---|
| windowaudit | raw | 0.0463 | 92.7% | 7.3% |
| windowaudit | **leaf** | 0.0197 | 25.4% | **74.6%** |
| champ125 | raw | 0.0479 | 93.1% | 6.9% |
| champ125 | **leaf** | 0.0221 | 33.5% | **66.5%** |

On leaf the total gap is 2.2–2.4× smaller **and** what remains is mostly stage-dependence (leaf stage-T runs ~70 → ~7 opening→endgame). So "stage-conditioning is NO-GO because it's only 7.7% of the gap" **no longer holds as stated** — though the absolute prize is now ~0.02 nats, and 07-19's out-of-sample generalization concern is untouched.

## 4. GO/NO-GO against the pre-registered rule

**NO-GO / effectively CLOSED**, with one narrow cheap option left open.

- The **letter** of the rule is met: a global gap survives (CI excludes 15).
- The **spirit** is not. The rule existed because the raw audit implied **2× / 0.043 nats**. On the true leaf margin it is **1.27–1.33× / 0.005–0.007 nats**, and every specific claim that made it interesting ("~2× too steep", "saturates by ±25–30", "T\*≈31") is **refuted**.
- **The C4 `value_norm=30` −36.6 elo null now explains itself.** 30 is exactly what the *raw* analysis pointed at, and F0b′ places it ~1.5× **past** the leaf optimum. So C4 is **not** evidence that calibration is irrelevant to strength — it is evidence that **the raw T\* was the wrong number to play**. This materially changes how that null should be cited.
- **Residual honesty:** nobody has played `value_norm ≈ 19–20`. A powered null would need one deck-paired online bracket at vn ∈ {15, 19}. **Recommendation: do not fund it** — 0.005–0.007 nats is not a strength story, calibration≠strength is already demonstrated (F7), and a monotone reparameterization of the leaf **cannot change sibling ordering at a node** (it only changes how values average up the tree). Close the thread; re-open only if an independent line implicates the value transform.

## 5. Caveats a reviewer should weigh

1. **Fresh sample, weaker generator.** Both corpora are sims=100, far shallower than the fair teacher (2,752/move); P(win|margin) is conditional on the continuation policy. *Mitigation:* the raw control reproduces 07-19's T\*≈31 (measured on the flywheel fair-teacher corpus) to within CI on both samples, so the generator difference moves the raw answer very little.
2. **Two generating leaves, one calibrated leaf.** `windowaudit` was played with pre-CL-051 curve100; `champ125` was generated under curve125 precisely to test that. Both agree (leaf T\* 19 vs 20; gap +0.0050 vs +0.0074).
3. **Clustering kept:** all CIs bootstrap **by game** (n_boot=200); OOS split 2-fold **by game**, as in 07-19.
4. **Grid quantization:** the bootstrap uses 07-19's coarse grid (0.667 spacing below 20), so CI endpoints land on 18.00/21.00; point estimates come from the finer refine grid.
5. **Selection effect (inherent):** positions come from games played by an agent using this leaf — correct conditioning for "how should the search's own leaf be transformed", but not P(win|margin) over arbitrary positions.
6. **The two leaf gaps differ (+0.0050 vs +0.0074) by more than either is large** — treat "≈0.005–0.008 nats" as the claim, not either point value.
7. **Calibration is not the search objective** — log-loss gain is an upper bound on relevance, not a strength prediction.
8. **Draws** follow 07-19 (y=0.5); rate 1.6% / 2.2%.

## Files

`extract_margins.py` · `calibrate_utility_leaf.py` · `margins_{windowaudit,champ125}.npz` · `manifest_extract_margins_*.json` · `calibration_stats_*.json` (canonical) · `calibration_surface_{leaf,raw}_*.csv` · `calibration_pooled_{leaf,raw}_*.csv` (incl. implied T) · `gen_games_champ125.jsonl` · logs.

Reproduce: `extract_margins.py --games <jsonl> --out <npz>` then `calibrate_utility_leaf.py --margins <npz> --tag <tag> --n-boot 200`.
