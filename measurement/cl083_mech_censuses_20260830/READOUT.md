# READOUT — CL-083 mechanism kill-gates (2026-08-30)

**STATUS: CLOSED.** All three censuses computed. Bars and definitions are read from
`PREREG.md`, committed at `aa07fee0` **before** any number in this file existed.
Departures are logged in `DEVIATIONS.md`.

All three censuses are **judge-free** (CL-085) and **zero games** were played.

| Census | Mechanism | Verdict |
|---|---|---|
| 1 | **GT-M1** — CVaR/quantile world pooling | **NOT KILLED** — max reach 0.340 [0.277, 0.404] ≥ the 0.30 survive bar; worlds do **not** already agree (U = 0.367). ⚠️ but the effect is **not contest-specific** — see the scoping note. |
| 2 | **CF-M1** — setup abandonment | **KILLED** — D = −0.057; the champion abandons its setups *less* than the owner, at every declared window. |
| 3 | **SA-M1** — contested-seed budget reservation | **KILLED** — two independent branches fire: 89.7% of plies with a seed already fund it above the floor, and only 6.9% of crux plies are reachable at all. |

---

## §0 — Data-availability audit (decided before any statistic was computed)

The prereg's Censuses 1 and 3 both need **per-world root statistics** and **per-action
pooled visit distributions** for the champion at deploy budget. The audit of what is
banked:

| Corpus | What it banks | Usable for Census 1 / 3? |
|---|---|---|
| `measurement/e4_ply_pricing_20260827/targets.jsonl` | the 290 crux plies (game, ply, stratum, profile, actor, played action) | **Yes as the POPULATION.** Carries no search statistics. |
| `measurement/c1_pricing_prep/C1_PRICING.json` | 188 plies × `world_deltas` (per-world realized outcome deltas), `price`, `insample_gap_pts` | **No.** These are per-world *outcome* prices, not per-world *root search* statistics. No action-level Q or visit vectors. |
| `measurement/classical_search/MOVE_AGREEMENT_REPORT.json` (CL-070) | aggregated agreement rates only | **No.** |
| `/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/records/` (CL-070, 2696 records over 898 roots) | per-root, per-budget-level: `q_argmax_action`, `pooled_top2_q_gap`, `sum_N`, `n_children`, `played_visit_share` | **No.** Pooled *summaries* only — no per-world stats (Census 1) and no per-action visit vector (Census 3, which needs the visits of a *specific tagged* action, not of the argmax). Two further disqualifiers even if it did: the corpus is `k_dets=4`, and it was generated under the **pre-curve125 leaf** (`v29_meeple_curve = -8,-4,-1,0,2,3,4,5`, leaf `7fc930b8…`), an evidence epoch behind the champion of record `a36d2e15a3b3d71d`. |
| `measurement/tiearb_20260816/per_position.jsonl`, `tiearb_widening_20260817/…` | the banked CRN matrices behind the arb_costopt racing analysis — arm-level judged aggregates per position (`arb`, `ora`, `rnd`, folds) | **No.** "Worlds" there are CRN *evaluation* worlds over a J-arm tie set, not the search's PIMC determinizations, and the values are judge-priced (CL-085 bars using them for a judge-free census). |
| repo-wide grep for `world_stats` / `per_world` / `root_stats_list` in `measurement/**/*.json{,l}` | only documentation strings inside `analyzer_evloss_*` | **No banked per-world root statistics exist anywhere in the repo or on the share.** |

**Decision (pre-compute).** Censuses 1 and 3 regenerate their inputs by lossless
`(deck_seed, action-prefix)` root replay — the standing measurement-infra path the task
explicitly licensed — calling the deployed `fair_agent.search_one_world` /
`_merge_root_stats` / `pooled_q_argmax` at k8×1376. Cost turned out small: 554 cells
(290 plies × 2 salts, split by profile leg) at ≈9 s/cell, ≈14 min wall on the idle
laptop at W18.

**CL-070's 898-root set is NOT folded in.** Its banked records lack both statistics the
censuses need, so including it would require regenerating 898 roots (≈2× the crux job,
≈25–30 min at the same W) *and* would still be a different evidence epoch (k4,
pre-curve125 leaf) and a different position distribution (champion self-play, not E4).
Per the prereg's data-availability clause this is recorded as a **precise missing
input**, not silently dropped: regenerating it is cheap in compute but is a
**cross-epoch** extension, and CL-068's cross-band humility plus CL-085's
family-relativity both argue against pooling it with the E4 crux read. It is
**available on request** as a separate leg; it does not change any bar below.

**Instrument checks (all legs).** Leaf hash resolved to `a36d2e15a3b3d71d` in every
process. `CARCASSONNE_FIX_R9` latched to each profile's `r9_env_expected`
(`fixed_v1` → 1, `walled`/`app_aug2` → 0). Pooled visit counts sum to exactly
11008 = the deploy budget on every cell. 0 replay desyncs, 0 recon failures.

---

## §2 — CENSUS 2 (CF-M1, setup-abandonment) — **VERDICT: CF-M1 KILLED**

*(numbered §2 to match the prereg's census numbering; it closed first because it needed
no regenerated search statistics.)*

**Artifacts:** `CENSUS2.json`, raw rows `out/C2_{fixed_v1,walled,app_aug2}.jsonl`,
harness `census2_followthrough.py`, analysis `analyze_census2.py`.

**Coverage.** 56 archives (`fixed_v1` 53 / `walled` 2 / `app_aug2` 1), **0 recon
failures** (every replayed final score matches the archive's recorded score),
642 setups — 336 champion, 306 owner. Primary window N = 12; 37 setups censored by
the game ending inside their window and dropped as pre-registered.

### The headline

| Window | owner abandonment | champion abandonment | **D = champ − owner** | 95% game-cluster CI |
|---|---|---|---|---|
| N = 6 | 0.7138 (n=297) | 0.6801 (n=322) | **−0.0337** | [−0.114, +0.043] |
| **N = 12 (primary)** | **0.4251 (n=287)** | **0.3679 (n=318)** | **−0.0572** | [−0.126, +0.020] |
| N = 20 | 0.2635 (n=277) | 0.2444 (n=311) | **−0.0192** | [−0.088, +0.052] |

**D ≤ 0 at every pre-declared window.** By the prereg's read rule — *"CF-M1 IS KILLED
if D ≤ 0 — the champion abandons its own setups no more than the owner does"* —
**CF-M1 is dead.** The champion does not merely fail to abandon more; the point
estimate runs the other way at all three windows.

### It is not a slice artifact

| Slice | D (N = 12) | n owner / champion |
|---|---|---|
| city | **−0.0740** | 212 / 175 |
| road | **−0.0224** | 75 / 143 |
| `fixed_v1` (the dominant rules epoch) | **−0.0584** | 269 / 298 |
| `walled` | −0.2115 | 13 / 16 |
| budget epoch k8×1376 (the 22k epoch) | **−0.0426** | 270 / 295 |
| budget epoch k4×688 | −0.2115 | 13 / 16 |
| budget epoch k16×1376 | −0.3571 | 4 / 7 |
| `app_aug2` | +0.5500 | 5 / 4 |

Every slice with a usable n is negative. The single positive cell is `app_aug2` at
n = 4/5 — one archive, and exactly the "carried by fewer than 20 setups" case the
prereg pre-committed to discount.

### The companions point the same way, and one of them is interesting

| Companion (N = 12, eligible setups) | owner | champion |
|---|---|---|
| mean own-growth events per setup | 0.683 | **0.811** |
| finished-in-window rate | 0.195 | 0.192 |
| still-open-at-window-end rate | 0.801 | 0.808 |
| **opponent-growth rate in the window** | **0.136** | **0.223** |

The champion follows through on its own setups **more** often (0.811 vs 0.683 growth
events per setup), on features that are equally often still live at the end of the
window — so the contrast is not an artifact of the champion's features being foreclosed
or completed at different rates.

The last row is a by-catch worth flagging and *not* part of any bar: when the
**champion** claims a feature, the **owner** extends it 22.3% of the time; when the
**owner** claims one, the champion extends it 13.6%. The owner reaches into the
champion's features at roughly 1.6× the rate the champion reaches into his. That is
consistent with — though in no way a test of — CL-083's invasion story, and it is a
purely descriptive count with no pricing attached (CL-084 forbids reading a gap off a
selected statistic).

### What this kills, and what it does not

**Killed:** the compute-first lens's proposed behavioral signature. There is no
"champion abandons its setups" phenomenon in the E4 record to explain, so a CF gate
built to price setup-abandonment has nothing to price. The next CF gate is **not**
licensed.

**Not touched:** this says nothing about whether *follow-through quality* differs, only
about follow-through *occurrence*. And the census deliberately scopes out farms and
cloisters (`PREREG` §Census 2), so it is silent on farm-side setup behaviour — which is
the stratum CL-083 already flags as its live counterevidence.

---

## §1 — CENSUS 1 (GT-M1, world-spread) — **VERDICT: GT-M1 NOT KILLED** (with a scoping caveat)

**Artifacts:** `CENSUS1.json`, raw `out/C13_*.jsonl`, harness `census13_rootstats.py`,
analysis `analyze_census13.py`.

**Coverage.** 580 cells ran (290 plies × 2 salts across three profile legs), **0
failures, 0 forced moves, 4 exact-region roots excluded** as pre-registered. Primary
population = the `fixed_v1` contest-exposed strata at salt 0: **n = 188** plies
(invasion 81, defense 81, farm_capture 26). Companion control stratum n = 87.

### The worlds do NOT already agree

| Statistic (contest-exposed, n=188) | Value |
|---|---|
| **U — all-8 unanimity rate** | **0.367** [0.294, 0.442] |
| dissent rate (≥1 world disagrees) | 0.633 |
| mean agreement fraction | 0.676 |
| mean distinct per-world picks per ply | 2.39 |

`agree_frac` histogram (worlds agreeing with the pooled pick, out of 8):

| 0/8 | 1/8 | 2/8 | 3/8 | 4/8 | 5/8 | 6/8 | 7/8 | 8/8 |
|---|---|---|---|---|---|---|---|---|
| 5 | 17 | 15 | 14 | 15 | 20 | 15 | 18 | **69** |

The prereg's "already agree" label resolves to **FALSE** (U ≤ 0.50). The premise the
census was built to test — that k=8 PIMC worlds have already converged on the root
argmax at contest-exposed plies — is **refuted**. Only 37% of these plies are unanimous;
on 5 plies not a single world names the pooled pick.

### But unanimity is the weak instrument — here is the arithmetic that matters

The prereg made the **CVaR reachability** the primary precisely because unanimity is
only a *sufficient* inertness test. It earned that: **most world dissent is
arithmetically inert.** A pooled winner can be beaten in some individual world and still
dominate on the mean *and* on the lower tail, because the pooled Q is visit-weighted and
the dissenting worlds' preferred moves score badly elsewhere.

| α (lower-tail CVaR level) | **reach(α)** — CVaR pick ≠ deployed pick | marginal vs equal-weight pooling |
|---|---|---|
| 0.25 (worst 2 of 8 worlds) | **0.340** [0.277, 0.404] | 0.213 |
| 0.50 (worst 4) | 0.271 | 0.122 |
| 0.75 (worst 6) | 0.239 | 0.080 |
| 1.00 (all 8 = equal-weight mean) | 0.181 | 0.000 |

**PRIMARY: `max_α reach(α)` = 0.340 over α ∈ {0.25, 0.50, 0.75}, CI [0.277, 0.404].**
The prereg's survive bar is ≥ 0.30 and the kill bar ≤ 0.10. The point estimate clears
the survive bar and the CI's lower end (0.277) sits far above the kill bar.
**GT-M1 is NOT KILLED.** Quantile/CVaR pooling is *not* arithmetically inert: at the
most risk-averse level it would change the champion's move on roughly a third of
contest-exposed plies.

Two clean instrument facts behind that number:

- **`P(a* is CVaR-eligible) = 1.000`** on all 188 plies, so `reach_star_eligible_only`
  is identical to `reach` and none of the reach is the mechanical artifact DEVIATIONS
  D-2 was added to detect.
- The α = 1.00 row is the **equal-weight-world pooling** rule, not an identity control
  (DEVIATIONS D-1). It changes the pick on 18.1% of plies by itself. Subtracting it,
  the **marginal contribution of risk aversion** is 21.3 pp at α = 0.25 — still double
  the 10% kill bar on its own. So the survival does not rest on the weighting artifact.
- **Salt-1 replicate** (independent world draw, same plies): U = 0.335, reach(0.25) =
  0.394. Same order, same verdict. Not pooled with the primary.

### ⚠️ Scoping caveat — the effect is NOT contest-specific

| Stratum | n | U | reach(0.25) |
|---|---|---|---|
| **control** | 87 | 0.345 | **0.333** |
| invasion | 81 | 0.506 | 0.222 |
| defense | 81 | 0.185 | **0.494** |
| farm_capture | 26 | 0.500 | 0.231 |

The **control stratum reads 0.333 — statistically indistinguishable from the
contest-exposed 0.340.** World spread and CVaR reachability are a general property of
the champion's PIMC search, not something contest exposure creates. And within the
contest-exposed strata the effect is carried almost entirely by **defense** (0.494);
`invasion`, the stratum CL-083's agreement-gradient story is actually about, is the
*second lowest* at 0.222.

So the honest reading is: **GT-M1 survives its kill gate on the arithmetic, but the
census provides no evidence it is a mechanism for the owner's edge.** A lever that
fires equally on control plies is not explaining a contest-specific gap. Whoever funds
the next GT gate should note that the free census licensed "the pooling rule is not
inert", not "the pooling rule is where the edge lives".

**Pre-committed non-inference (prereg, restated):** this census says **nothing** about
whether the CVaR pick is *better*. Changing 34% of moves is a cost as easily as a gain.
Pricing it requires independent-world realized-outcome pricing — precisely the
instrument CL-084 was measured on — and any in-sample argmax gap on these same worlds
would be inflated by ≈ +6.5 pts.

---

## §3 — CENSUS 3 (SA-M1, contested-seed reachability) — **VERDICT: SA-M1 KILLED**

**Artifacts:** `CENSUS3.json`, same raw cells as Census 1.

**Coverage.** Primary population = all `fixed_v1` crux plies at salt 0, **n = 275**
(277 minus 2 exact-region). Mean legal actions 26.6; mean tagged contested seeds 4.1.

### Both kill branches fire, and so does the compound

| Statistic | Value | Prereg bar | Fires? |
|---|---|---|---|
| **P(EXISTS)** — a contested seed exists among legal actions | 0.669 [0.609, 0.726] | Branch A kills if < 0.50 | no |
| **P(N_seed ≥ m \| EXISTS)** — the seed is already funded above the floor (m = 110 = 1% of the 11008 budget) | **0.897** [0.856, 0.934] | **Branch B kills if ≥ 0.80** | **YES** |
| **compound reachable share** — seed exists AND is under-visited | **0.069** [0.043, 0.095] | **kills if ≤ 0.20** | **YES** |

**Branch A does not fire** — contested seeds do exist, at two thirds of crux plies. The
kill comes from the other side, and it is not marginal: the champion's unmodified search
*already* funds the contested seed far above any floor a reservation would install.

How far above:

| How well-funded is the best contested seed? | |
|---|---|
| **median pooled-visit RANK among all root actions** | **1** — it is usually the single most-visited action |
| mean budget share of the best seed | **41.4%** of the 11008 sims |
| `N_seed` quartiles (min / Q1 / med / Q3 / max) | 0 / 458 / 3983 / 8131 / 11008 |
| best seed entirely unvisited | 1.6% of plies with a seed |

Even Q1 — the 25th percentile — is 458 visits, **4.2× the reservation floor**. A budget
reservation exists to guarantee an arm a minimum share of attention; here the median
contested seed is already the search's top choice with 36% of the whole budget.

### It survives the stricter reading and the stratum split

Under the **`onset`-only** tag (the narrower "starts a new contest", dropping
`extend`): P(EXISTS) = 0.535, P(well-visited | exists) = **0.830**, compound =
**0.091**. Both bars still fire.

| Stratum | n | P(EXISTS) | P(wv \| exists) | compound reachable |
|---|---|---|---|---|
| invasion | 81 | **1.000** | **0.988** | **0.012** |
| defense | 81 | 0.605 | 0.694 | 0.185 |
| control | 87 | 0.621 | 0.944 | 0.034 |
| farm_capture | 26 | **0.000** | — | 0.000 |

The kill is *strongest exactly where SA-M1 was supposed to help*: at **invasion** plies a
contested seed exists at every single ply and is already well-visited at 98.8% of them —
compound reachable share **1.2%**. Reservation is a no-op on the invasion stratum.

Two disclosed sub-findings:
- **`farm_capture` plies have no contested seed at all** (0 of 26). No legal action there
  creates or extends a both-player component under the prereg's tag — farm contests in
  this corpus are already established rather than initiated at these roots.
- **Meeple-phase roots have no contested seeds** (0 of 26), as expected: no tile is
  placed, so no merge can occur. Restricting to tile-phase roots raises P(EXISTS) to
  0.739 and leaves the compound share at 0.076 — the verdict is unchanged.

**Salt-1 replicate:** P(EXISTS) 0.669, P(wv|exists) 0.902, compound 0.065. Stable.

### What this kills

**Killed:** budget *reservation* for contested seeds. The census shows the lever's
target is already funded an order of magnitude above the floor on the plies that
matter, and that only ~7 crux plies in 100 are even reachable by a reservation scheme.
This is the quantitative form of the red-team's "crack A" deflation of SA-M1.

**Not touched:** this measures *how much search the seed gets*, not *whether the search
evaluates it correctly*. A mechanism that changes how contested seeds are **valued**
(rather than how much budget they receive) is untouched by this census — but it is a
different mechanism and would need its own gate.

