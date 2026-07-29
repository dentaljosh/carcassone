# CL-067 EQUAL-WALL-CLOCK GATE — the distilled net-priors agent at the champion's own clock

**STATUS: COMPLETE (arm A 2026-07-29 03:2x, arm B same). Both arms ran to full n=400
deck-paired, 400/400 records, 0 solver timeouts either side, 0 deck_hash mismatches
in 400 decks, 400/400 endgame latches on both sides of both arms.**

**VERDICT — pre-registered branch **C (WASH)** fired on the verdict arm: at a MEASURED
per-move cost ratio of 1.00, the distilled net-priors agent scores **−17.4 ± 17.4 elo**
(winrate z −1.00, deck-paired margin −1.633 pts/deck z −1.74) against the deploy
champion. Neither statistic clears 2σ, and the point estimate sits inside the
pre-registered wash window [−20, 0). **The +35.7 elo the distilled priors win at equal
SIMS is bought back in full by the clock.** Nothing is promoted; `governance/PRODUCTION.yaml`
is untouched.**

**But every companion view is worse, and none is better.** The candidate-favoured arm B
(same agent, fresh band, and — measured — a **25% clock advantage** to the candidate)
lands at **−37.5 elo with BOTH statistics past 2σ negative**. Pooled over 800 deck-paired
games the effect is **−27.4 ± 12.3, winrate z −2.23, margin z −3.94**. So the honest
one-line summary is **branch C by the pre-registered rule, leaning hard on branch D**:
you can have the strength or the clock, not both.

Run by the experiment-runner session `c0b61ee1`. Pre-registration committed in `df93dcc`
**before any result existed**; the launch script carrying it is
[`../distill_strong_20260723/eqtime_netprior_gate_launch.sh`](../distill_strong_20260723/eqtime_netprior_gate_launch.sh)
and the sims-selection probe is
[`../distill_strong_20260723/eqtime_netprior_probe.sh`](../distill_strong_20260723/eqtime_netprior_probe.sh).
No source file, no `results.csv` row, and no governance row was touched by this run.

---

## 1. What was owed

[DECISIONS.md](../../DECISIONS.md) 2026-07-26 closed the *strength* half of CL-067 and
opened the *cost* half:

> the blocker moved from strength to cost … an equal-WALL-CLOCK arm (`--opp-sims`) is a
> SEPARATE cell and the one that decides deployment.

The equal-sims claim is settled: **+35.7 ± 12.3 elo** pooled over 800 deck-paired games
(gate band 52e9 **+42.8**, confirm band 56e9 **+28.7**), both statistics past 2σ pooled.
What was never measured is whether that edge survives being paid for. Every prior read on
deployability was *arithmetic* — an elo exchange rate applied to a cost ratio — never a
game played at matched cost. This cell plays it.

It also discharges the fresh-band debt this configuration owes in its own right: arm A is
band 82e9 and arm B is band 84e9, both previously unburned.

---

## 2. Design, and why it became two arms

### 2.1 The sims budget was measured, not divided

The pre-registration forbade taking `688 / 4.29` on faith. A timing probe ran first
(n=32 paired, W16 per box, carc-orch SHM, `fwd=6`, `max_batch=W`, server libtorch pool
pinned `OMP=1`, scratch band 99.5e9, per-host out-dir, candidate k4×162 vs champion k4×688):

| box | candidate ms/move | opponent ms/move | ratio |
|---|---|---|---|
| local (RTX 5060 Ti) | 3701.2 | 3854.9 | **0.960** |
| laptop (RTX 4070 Laptop) | 4398.8 | 3294.7 | **1.335** |

⇒ equal-time per-det sims are **168.7 (local)** and **121.3 (laptop)**. **sims = 169** was
adopted. The accept rule, fixed before the probe, was that the ratio must land in
**[0.90, 1.10]**.

### 2.2 Why not both boxes on one band

One sims value cannot equalise both boxes, and per-box sims values are **disqualified**:
under `--shared-claim` the two seats of a single deck can land on different boxes, which
would deck-pair two *different* agents against each other. So the cell split into two arms
on separate bands, **not pooled in the pre-registration**:

| | **arm A — PRIMARY / equal-time** | **arm B — COMPANION / candidate-favoured** |
|---|---|---|
| box | local (RTX 5060 Ti) | laptop (RTX 4070 Laptop) |
| band | **82e9** | **84e9** |
| candidate | netprior k4×169 (676 total sims) | *identical agent* |
| opponent | deploy champion k4×688 (2752) | identical |
| predicted clock ratio | 1.00 | 1.39 |
| **measured clock ratio** | **0.981** ✅ | **1.251** |
| role | **the verdict is read off this arm alone** | one-sided bracket, never the verdict |

Arm B's pre-registered role was explicit: *if the candidate loses even here, the equal-time
loss is not a knife-edge artefact of the sims choice; if it wins here but not in arm A, the
break-even clock multiple lies in (1.0, 1.4).* **The first condition fired.**

Note the two arms run the **identical agent pair** — only band and box differ. The clock
ratio differs because the *boxes* differ, not because the agents do.

### 2.3 Configuration integrity (verified from both manifests)

| | arm A | arm B |
|---|---|---|
| candidate leaf hash | `a36d2e15a3b3d71d` | `a36d2e15a3b3d71d` |
| opponent leaf hash | `a36d2e15a3b3d71d` | `a36d2e15a3b3d71d` |
| `both_sides_curve125` | `true` | `true` |
| candidate k_dets × sims | 4 × 169 = 676 | 4 × 169 = 676 |
| opponent k_dets × sims | 4 × 688 = 2752 | 4 × 688 = 2752 |
| endgame, both sides | marginalized, `exact_k=2`, `exact_budget=2000000`, `tt_cap=None` | same |
| net | `distill_strong_20260723/ckpt/iter_03.pt` | same |
| rep (peeked from ckpt) | 81ch / 42 scalar, sighted | same |
| priors / value | `net_policy_head` / `frozen_v29_curve125_leaf` | same |
| `production_config_deviations` | `[]` | `[]` |
| code_rev | `8fe268b-dirty` | `8fe268b6b-dirty` |

Identical to the CL-067 gate in every knob **except the candidate's sims and the band** —
which is the single variable this cell exists to move. (`-dirty` is untracked measurement
output only; both boxes are on the same commit.)

---

## 3. Results — verified off the raw records, not read from the summaries

Every figure below was independently re-derived from the 400 per-game JSON records of each
arm by [`the verification script`](#appendix--verification) and reproduces
`summary.json` exactly.

### 3.1 Arm A — PRIMARY, equal-time (band 82e9, measured ratio 0.981)

| statistic | value |
|---|---|
| record | **185W – 10D – 205L** over n=400 |
| winrate | **0.4750**, **winrate z −1.000** |
| elo | **−17.39**, 1σ **17.39** (elo z −1.00) |
| deck-paired margin | **−1.6325 pts/deck**, se 0.9387, **paired z −1.739**, 200 decks |
| deck_hash mismatches | **0 / 200** |
| candidate prefix ms/move | 3786.75 |
| opponent prefix ms/move | 3859.62 |
| **cost-ratio guard** | **0.9811 — INSIDE [0.90, 1.10] ✅ the cell IS equal-time** |
| timeouts | 0 candidate / 0 opponent |
| endgame latches | 400/400 both sides |

### 3.2 Arm B — COMPANION, candidate-favoured (band 84e9, measured ratio 1.251)

| statistic | value |
|---|---|
| record | **173W – 11D – 216L** over n=400 |
| winrate | **0.4462**, **winrate z −2.150** |
| elo | **−37.49**, 1σ **17.47** (elo z −2.15) |
| deck-paired margin | **−3.3875 pts/deck**, se 0.8619, **paired z −3.930**, 200 decks |
| deck_hash mismatches | **0 / 200** |
| cost ratio | **1.2505** — the candidate spent **25% MORE** wall-clock than the champion |
| timeouts | 0 / 0 |
| endgame latches | 400/400 both sides |

⚠️ The realised ratio was **1.25**, not the projected 1.39 — the probe slightly
over-estimated the laptop's net penalty. The arm still did what it was for: it handed the
candidate a **25% clock advantage** and the candidate still lost on **both** statistics past 2σ.

### 3.3 The two arms are statistically indistinguishable

| contrast | value |
|---|---|
| elo A − B | **+20.11 ± 24.65, z +0.82** |
| margin A − B | **+1.755 ± 1.274, z +1.38** |

Independent bands **and** boxes ⇒ added in quadrature, not deck-paired. **Neither contrast
resolves.** So arm B must *not* be reported as "a steeper loss": it is a second draw from
the same underlying value, and the difference between −17.4 and −37.5 is inside noise.
What arm B *does* establish is that the negative sign replicates on a fresh band, on a
different box, with the clock tilted the candidate's way.

### 3.4 Pooled (NOT pre-registered — read with the caveat)

**358W – 21D – 421L over 800 deck-paired games: winrate 0.4606 (z −2.227), elo −27.42 ±
12.32, deck-paired margin −2.510 pts/deck (z −3.935) over 400 decks. Both statistics past 2σ
negative.**

Cross-band pooling was not pre-registered here, exactly as it was not for CL-067's own
+35.7 — and this project has been burned twice by cross-band comparison (L2-2; CL-069's
supersession of the halving screen). It is reported because the *agent is identical in both
arms*, which makes the pool a legitimate statement about that agent's strength — just not
an "equal-time" statement, since the laptop half over-clocked the candidate. **That
direction matters: the pool is if anything generous to the candidate, so it cannot be
accused of flattering the negative.**

---

## 4. Which pre-registered branch fired

The rules fixed in `df93dcc`, evaluated against arm A:

| branch | condition | fired? |
|---|---|---|
| **A** | both statistics ≥ +2σ ⇒ stronger at equal clock; funds G3 as an amplifier | ❌ |
| **B** | elo ≥ 0 and ≥1 statistic ≥ +1σ ⇒ wall-clock-competitive; funds G3 | ❌ |
| **C** | both statistics inside ±2σ **and** elo ∈ [−20, 0) ⇒ **WASH** | ✅ **−17.39, z −1.00 / −1.74** |
| **D** | both statistics ≤ −2σ ⇒ kill for deploy | ❌ on arm A (✅ on arm B and on the pool) |

**Branch C fired.** Its pre-registered consequence: *neither deployable nor refuted; G3
stays parked unless Joshua funds cost work.* Section 6 argues the ANE result should
change that conclusion, and states the reopen condition in measurable form.

### Against the pre-registered projection

The projection was **"approximately a wash"**, bracketed by three priors:

| prior | source | predicted equal-time elo | outcome |
|---|---|---|---|
| **+8** | CL-060 exchange rate (4.07× budget ⇒ +27.85, the **up**-step) | +8 | ❌ too optimistic |
| **−11** | `pareto_k4x172_688_vs_deploy` = −46.3, the champion's **own measured down-step** | −11 | ✅ closest |
| **−40** | flywheel net's own degradation (688 tie → 154 = −75.9) | −40 | pessimistic, but the pooled −27.4 moves toward it |

**The projection was right and the modal expectation (negative) was right.** Arm A's −17.4
and the pooled −27.4 sit between the −11 and −40 priors. The **+8** prior is refuted, and
for the reason named in advance: it used the **up**-step of a concave curve, and the curve
is flat above ~2064 (CL-068/CL-069) but cliff-like below 688, so the down-step is steeper.
This is a small methodological win worth carrying: **when a budget curve is concave, never
price a budget CUT with an exchange rate measured on a budget INCREASE.**

---

## 5. The cost model, and what multiple WOULD have been break-even

The interesting question a wash raises is *how close*. Define

> **r = (per-forward net cost) ÷ (per-simulation search+leaf cost)** on a given device.

`r` is device-independent in the useful sense: it is exactly the quantity that decides how
many simulations the candidate can afford in the champion's clock, since
**equal-time total sims = 2752 / (1 + r)**, and the equal-**sims** cost ratio that CL-067 has
been quoting all along is simply **1 + r**.

### 5.1 r, measured

| context | search ms/sim | forward ms | **r** | equal-sims ratio (1+r) |
|---|---|---|---|---|
| local 5900XT, this run, W16 | 1.4025 | 4.199 | **2.99** | 3.99× |
| laptop, this run, W16 | 1.2656 | 5.177 | **4.09** | 5.09× |
| local 5900XT, unloaded W2 (2026-07-26 probe) | 1.0000 | 3.243 | **3.24** | 4.24× |

Two things worth noting. First, **local W16 (r 2.99) is a faithful proxy for the honest
single-agent regime** (unloaded W2, r 3.24) — which retro-justifies the choice of W16 for
this cell and confirms the 2026-07-26 finding that the ratio is essentially W-invariant.
Second, the implied equal-time sims from r alone is **2752/3.99 = 689**, and the probe
independently chose **676**. The cost model and the direct measurement agree to 2%.

### 5.2 The break-even multiple

The candidate's own budget→elo line, measured against the same deploy champion:

- **676 total sims → −17.39 elo** (this cell, arm A, band 82e9)
- **2752 total sims → +35.7 elo** (CL-067 pooled, bands 52e9 + 56e9)

⇒ slope **+26.21 elo per doubling** of the candidate's budget (+29.7 against the gate alone,
+22.8 against the confirm alone). A conservative alternative — the champion's *own* measured
down-step, `pareto_k4x172` −46.3 over 2 doublings = **+23.15/doubling** — is carried alongside.

| | main slope | conservative |
|---|---|---|
| **break-even r** | **1.57** | **1.42** |
| **break-even equal-sims cost ratio (1+r)** | **2.57×** | **2.42×** |
| break-even equal-time sims | 1071 | 1137 |

> **The candidate needed to be ≤ ~2.5× the champion's per-move cost at equal sims. It
> measures ~4.0×. It missed break-even by a factor of ~1.6–1.7 on the forward.**

This *directly measures* what the 2026-07-26 entry could only assert arithmetically, and the
two agree: that entry's pre-registered rule of thumb was *"≤~2× deployable · ~3× marginal ·
≥~4.3× not deployable"*, and the measured break-even of **2.4–2.6×** falls exactly between
its "deployable" and "marginal" rungs. The arithmetic was sound; it is now grounded.

⚠️ **Caveat on the slope.** It is fitted across **three different bands** (82e9 for the low
point, 52e9+56e9 pooled for the high point) — the cross-band comparison this project has been
burned by twice. Treat the break-even multiple as a **calibrated order-of-magnitude guide,
not a verdict**. Note also that the model reproducing arm A at r = 2.99 is *not* an
independent check — arm A anchors the low point, so that agreement is definitional. The
independent content is entirely in the hardware rows below.

### 5.3 Equal-wall-clock elo as a function of r

| r | equal-time sims | E (main slope) | E (conservative) |
|---|---|---|---|
| 4.09 (laptop today) | 541 | −25.8 | −24.9 |
| 3.24 (desktop unloaded) | 649 | −18.9 | −18.7 |
| **2.99 (desktop today)** | **690** | **−16.6** | **−16.7** |
| 2.00 | 917 | −5.8 | −7.2 |
| **1.57 / 1.42 — BREAK-EVEN** | 1071 / 1137 | **0.0** | **0.0** |
| 1.00 | 1376 | +9.5 | +6.3 |
| 0.73 | 1591 | +15.0 | +11.2 |
| 0.30 | 2117 | +25.8 | +20.7 |
| 0.10 | 2502 | +32.1 | +26.3 |
| 0.00 (free forward) | 2752 | +35.7 | +29.5 |

---

## 6. What this means now that cheap-forward hardware exists — the reopen condition

The verdict above is a verdict about **one forward path**: batch-1 CUDA through carc-orch,
where a forward costs ~3× the simulation it is meant to guide. It is *not* a verdict about
the distilled policy, whose strength is settled and positive.

Since this cell launched, the M5/ANE measurements landed
([`../m5_bench_20260728/M5_BENCH_READOUT_20260728.md`](../m5_bench_20260728/M5_BENCH_READOUT_20260728.md)),
and they change the candidate's **cost class**, not its strength. Applying the same r model
to real devices — champion `k4×688` = 2752 sims per move on each:

| device / forward path | search ms/sim | forward ms | **r** | equal-time sims | **projected equal-clock elo** |
|---|---|---|---|---|---|
| local 5900XT + CUDA batch-1 (measured, this cell) | 1.4025 | 4.199 | 2.99 | 690 | **−16.6 / −16.7** |
| M5 + torch-CPU batch-1 | 0.5741 | 2.600 | 4.53 | 498 | −29.0 / −27.6 |
| **M5 + ANE fp16 batch-1** | **0.5741** | **0.420** | **0.73** | **1589** | **+15.0 / +11.2** |
| Pixel 9 Pro + GPU delegate | 0.6177 | 7.760 | 12.56 | 203 | −62.9 / −57.6 |

*(M5 search 1.58 s/move and ANE 0.42 ms fp16 100%-on-NPU argmax-faithful are from the M5
bench readout; Pixel 1.7 s/move is the shipped-app figure; the 7.76 ms GPU-delegate number
was supplied by the coordinator and is **not** independently verified in this document.)*

**So the reopen condition, stated in measurable form and fixed here before anyone builds
anything:**

> **REOPEN the distilled-net line for deploy when the target device's measured
> `r = forward_ms / search_ms_per_sim` is ≤ ~1.5** — equivalently, when the equal-sims cost
> ratio is **≤ ~2.5×**. Today's desktop path is r ≈ 3.0. **The ANE path is r ≈ 0.73 and
> clears the bar with roughly 2× of margin**, projecting **+11 to +15 elo at equal wall-clock**.
> The Pixel GPU-delegate path (r ≈ 12.6) and the torch-CPU path (r ≈ 4.5) both fail it and
> are further from deployable than the desktop is.

This is **G3's unpark trigger restated in device-independent, measurable terms** — and it
reframes G3. G3 was scoped as *"per-move cost reduction — batch the k determinizations"*.
The measurement says the binding constraint is the **per-forward cost**, and that the single
highest-leverage move is not batching but **getting the forward onto a cheap-forward
accelerator**, which the M5 bench shows is already achieved in principle (0.42 ms, 100%
on-NPU, argmax-faithful).

⚠️ **Three caveats on the ANE row, none of them small.**
1. **It is a projection, not a measurement of an agent.** The M5's 1.58 s/move search figure
   and the 0.42 ms ANE forward were measured *separately*; a real agent interleaves them and
   may contend for CPU and memory bandwidth. The honest next test is one direct run — the
   netprior agent on the M5 at its own equal-time budget (~k4×397 = 1589 sims) vs the
   champion — which would settle it in a single cell.
2. **The ANE row is inside the fitted range** (1589 sims lies between 676 and 2752), so it is
   interpolation. **The Pixel row (203 sims) is extrapolation below the fitted range** and
   should be read as "clearly bad", not as "−62.9".
3. The slope's cross-band caveat (§5.2) applies to every number in the table.

---

## 7. What would have funded G3 vs killed the line — stated crisply

- **Would have funded G3 outright (branches A/B):** any non-negative result at ratio 1.00.
  It did not happen; the result is negative on every view.
- **What actually happened (branch C):** the equal-sims +35.7 is fully consumed by the clock
  on the current forward path. **On the desktop CUDA batch-1 path the distilled line is NOT
  deployable, and that is now measured rather than inferred.** No further work on the
  *strength* axis can change this — the strength is real and it is not the problem.
- **What reopens it:** a forward path with **r ≤ ~1.5** on the target device. The ANE
  measurement already clears that bar on paper. **That, not more distillation, is the work
  worth funding** — and it is cheap to test: one M5 cell.
- **What would kill it for good:** an M5/ANE cell at genuine equal wall-clock that still
  comes back negative. That would mean the equal-sims edge does not survive *any* realistic
  cost model, at which point the distilled policy is an analyzer asset (Phase 5) and not a
  deploy asset.

---

## 8. Draft `results.csv` rows — NOT written by this run

To be landed by the main session with the six-touch close-out. Column order per the file
header; `new_sims`/`old_sims` are **total** sims, following the `eval_iter03_EQWALL_vs_champion`
precedent (the closest prior analogue), with the k×s form carried in the `*_var` columns.

```csv
distill_strong_iter03_netprior_EQTIME_k4x169_vs_champ_deploy_b82e9_n400_paired,2026-07-29,base,8fe268b,400,distill_strong_20260723/ckpt/iter_03.pt,1.5,8,fair-netprior_k4x169_EQTIME,676,fair_champion_curve125,1.5,8,heuristic-prior_k4x688_DEPLOY,2752,185,205,10,-17.4,17.4,-1.633,/mnt/c/carc-shared/eqtime_netprior_k4x169_vs_deploy_b82000000000,verdict,"CL-067 EQUAL-WALL-CLOCK GATE, ARM A = THE VERDICT ARM. Distilled iter_03 net POLICY priors + FROZEN curve125 leaf (value severed) at a budget whose MEASURED per-move cost equals the deploy champion's, vs the deploy champion k4x688. Sims=169 chosen by a timing probe (n=32, W16, carc-orch fwd=6 mb=W server-OMP-pinned), NOT by arithmetic. In-flight cost guard: candidate 3786.75 vs opponent 3859.62 prefix ms/move = ratio 0.9811, INSIDE the pre-registered [0.90,1.10] => the cell IS equal-time. Band 82e9 (fresh), n=400 deck-paired, 200 decks, 0 deck_hash mismatches, 0 timeouts, 400/400 latches both sides, both sides leaf a36d2e15. winrate 0.4750 z -1.000; deck-paired margin -1.6325 pts/deck se 0.9387 paired_z -1.739. PRE-REGISTERED BRANCH C (WASH) FIRED: both statistics inside 2 sigma, elo in [-20,0). The +35.7 elo won at EQUAL SIMS is bought back in full by the clock => NOT deployable on the desktop CUDA batch-1 forward path. Measured break-even is an equal-sims cost ratio of ~2.4-2.6x; the candidate measures ~4.0x. Pre-registration df93dcc BEFORE the result; readout measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md. NOT promoted, PRODUCTION.yaml untouched."
distill_strong_iter03_netprior_EQTIME_k4x169_vs_champ_deploy_b84e9_n400_paired,2026-07-29,base,8fe268b,400,distill_strong_20260723/ckpt/iter_03.pt,1.5,8,fair-netprior_k4x169_CANDFAVOURED,676,fair_champion_curve125,1.5,8,heuristic-prior_k4x688_DEPLOY,2752,173,216,11,-37.5,17.5,-3.388,/mnt/c/carc-shared/eqtime_netprior_k4x169_vs_deploy_b84000000000,verdict,"CL-067 EQUAL-WALL-CLOCK GATE, ARM B = COMPANION / CANDIDATE-FAVOURED, NOT the verdict arm. IDENTICAL agent pair to arm A (k4x169 netprior vs deploy k4x688); only the box (laptop) and band (84e9, fresh) differ. Because the laptop's net penalty is larger, the MEASURED cost ratio is 1.2505 - i.e. the candidate spent 25% MORE wall-clock than the champion and still lost. winrate 0.4462 z -2.150; deck-paired margin -3.3875 pts/deck se 0.8619 paired_z -3.930; 200 decks, 0 mismatches, 0 timeouts, 400/400 latches both sides. BOTH statistics past 2 sigma NEGATIVE. Its pre-registered role was a one-sided bracket ('if the candidate loses even here, the equal-time loss is not a knife-edge artefact of the sims choice') and that condition FIRED. NOT comparable head-to-head with arm A as a difference: elo A-B = +20.11 +/- 24.65, z +0.82, UNRESOLVED (independent bands AND boxes, quadrature not deck-pairing). Pooled over both arms (NOT pre-registered; pool is candidate-favourable so it does not flatter the negative): 358W-21D-421L/800, winrate 0.4606 z -2.227, elo -27.42 +/- 12.32, margin -2.510 pts/deck z -3.935. Readout measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md."
```

---

## 9. Ops notes worth carrying

1. **The probe was worth its 26 minutes.** `688 / 4.29 = 160` would have been within 6% of
   the right answer on local — but it would have silently mis-set the laptop by 39%, and the
   two-arm design (and therefore the bracket that produced the strongest negative evidence in
   this document) only exists because the probe measured both boxes separately.
2. **The cost ratio is a property of the box, not the agent.** local r 2.99 vs laptop r 4.09
   for the identical agent pair. Any future equal-time cell must probe **every** box it
   intends to use, and must not assume one sims value serves a heterogeneous cluster.
3. **`--shared-claim` across boxes is incompatible with per-box budget tuning**, because a
   deck's two seats can be claimed by different boxes. If per-box budgets are ever wanted,
   the arms must be split by band, as they were here.
4. **W16 was load-bearing and must not be "optimised".** The sims choice is only valid in
   the regime it was probed in; raising W would have invalidated `sims=169` mid-run. The
   header says so explicitly, which is why the watchdog's relaunch command pins `W=16`.
5. **Both watchdogs sat idle** — neither arm stalled, no relaunches, no orphaned claims
   (400 claims / 400 records on each arm). First clean run of the fixed `run_watchdog.sh`.
6. **`measurement_infra/run_watchdog.sh` `pgrep` pattern:** `'seed-start <BAND>'` worked well
   as a band-specific pattern — it matches the orch wrapper and the client but not the
   watchdog's own argv beyond the excluded self/parent pids.
7. ⚠️ **`fair_net_vs_net_orch.sh` exits `rc=1` on a fully SUCCESSFUL run.** Both arms printed
   `=== EQTIME GATE exited rc=1 ===` after writing complete, correct output — 400/400
   records, `summary.json` written, the full verdict block and the harness's own
   `prefix ms/move: candidate 3787 opponent 3860 (ratio 0.98x)` / `(ratio 1.25x)` lines
   printed (both of which independently confirm the ratios computed in §3). The status
   comes from the wrapper's `EXIT` trap tearing down the carc-orch server, not from the
   eval. **This is the exact mirror of the CL-069 ops finding that
   `bare_net_opp_orch.sh` exits `rc=0` after printing `FATAL: carc-orch died early`.** Both
   directions of launcher-status unreliability are now on record for this script family:
   **do not read success or failure off these wrappers' exit codes — count the records.**
   A watchdog keyed on record count (as here) is immune to both bugs, which is a further
   argument for arming it by default.

---

## Appendix — verification

Every statistic in §3 was re-derived from the 800 per-game record files rather than read
from `summary.json`, and reproduces the harness exactly (W/D/L, winrate, elo, 1σ, the
seat-balanced deck-paired margin and its z, the solver-free prefix ms/move ratio, timeout
and latch counts, and 0/400 deck_hash mismatches). The cost decomposition in §5 uses
**total** sims on both sides (candidate 4×169 = 676, champion 4×688 = 2752); the `k_dets`
factor cancels in the ratio, but it does **not** cancel in the per-sim decomposition, and
getting that wrong is exactly the shape of the 2026-07-26 sign error.

Field semantics were taken from the emitter, not the field name
([`eval_fair_puct.py`](../../scripts/classical_search/eval_fair_puct.py) lines 1606-1619):
for a `_HEAD_TO_HEAD` opponent, `champ_prefix_ms_per_move` is the **CANDIDATE** and
`rung_ms_per_move` is the **OPPONENT**, and both **exclude** the marginalized endgame solve —
which is `exact_k=2` on both sides and identical by construction, so equalising the
**prefix** is the correct target.
