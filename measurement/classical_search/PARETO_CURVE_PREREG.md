# PRE-REGISTRATION — budget/elo Pareto curve for the deploy champion

> **STATUS: COMPLETE 2026-07-27 08:10 — ALL 5 CELLS LANDED, 2000 deck-paired games,
> 0 solver timeouts, 0 guard failures. Headline: the curve is FLAT-THEN-CLIFF.
> 1376 → 5504 (a 4× span of budget) is statistically indistinguishable from the
> deploy champion; below 1376 it falls off a cliff (−37.5 at 688). The knee is at
> 1376 = 14.6% of the tournament clock vs deploy's 26%. Results in §Results below;
> the design above is UNEDITED from before the run.**
>
> **⚠️ ADDENDUM 2026-07-28 — THE OWED CONFIRM RAN AND REFUTED THE HEADLINE. The banner
> above is left as written on 2026-07-27; read it with this correction.** The fresh-band
> n=400 confirmation demanded by §4 is COMPLETE (band 76e9, laptop W16, 0 timeouts,
> 0 guard failures): `k4×344` (1376) vs the deploy champion = **166W/7D/227L, winrate
> 0.4238 (z −3.05), elo −53.4 ± 17.6 (95% CI [−87.9, −18.9]), deck-paired margin
> −3.285 pts/deck (z −3.54)** — both statistics past 3σ NEGATIVE, at a verified 0.50×
> cost ratio. **"Halving to 1376 is free" is REFUTED; `k4×344` costs 3.1σ, FAILS rule 6,
> and is NOT proposal-eligible.** The flat region shrinks to **2752 → 5504** and the cliff
> starts one rung higher than §1 drew it. See §4 and
> [G2_CONFIRM_READOUT_20260728.md](G2_CONFIRM_READOUT_20260728.md); `results.csv
> pareto_k4x344_1376_vs_deploy_CONFIRM`; DECISIONS 2026-07-28.
>
> **PRE-REGISTERED 2026-07-26, BEFORE ANY CELL RAN.** Nothing above the Results
> section may be edited now that results have landed; corrections go in the dated
> Results section. Approved by Joshua 2026-07-26 ("get it going, launch overnight").

## Why

[TOURNAMENT_TIMING_2026-07-26](../../docs/research/TOURNAMENT_TIMING_2026-07-26.md)
established that competitive play is **15 min per player, sudden death, no
increment** ⇒ ~12.9 s per searched decision. The deploy champion (k4×688 = 2752
sims) uses **26% of clock**; every stronger config we have measured uses 91–178%.
So the decision-relevant question is no longer "how much elo can compute buy"
(answered: ~+40–50, plateauing by 4×, per CL-060) but **"what does elo cost when
we go DOWN, and where is the knee"** — because clock margin is now a resource.

The sub-deploy region is **entirely unmeasured at production width**. The only
low-budget ladder (CL-046 D0: +27.9/+61.4/+81.4/+149.3 at 800/1600/2752/5504) was
run at `k_dets=8`, and k8→k4 alone is worth ~+66 elo at 2752 (CL-054), so its
LEVELS do not transfer — only its shape (~−27 to −34 elo per halving) is
indicative.

## Design

**Opponent for every cell: the deploy champion itself** (`--opponent fair-champion`,
k4×688), head-to-head. NOT the h800 rung. Reason: the h800 rung is
ceiling-compressed for strong configs — both arms beat it by ~9 pts/deck, which is
exactly what made CL-060's original closure return "flat past 2752" at z=0.86
before the direct H2H refuted it at z=3.48. Head-to-head vs the config we would
actually field is the design of record.

**Width is re-solved at each budget.** Non-negotiable: at 8× total, k8×2752 scored
+3.5 (flat) while k16×1376 scored +35.6 — same budget, allocation was the entire
effect (CL-060 budget-curve extension). A budget point measured at one arbitrary
allocation is uninterpretable. CL-054 found k4 optimal at 2752 with k2 close
behind (direct k4−k2 z=1.33, a flat peak), and the textbook story is that optimal
width GROWS with budget ⇒ below deploy the candidates are k4 and k2.

**Cells** (all `--info fair`, i.e. the classical champion on both sides; frozen
curve125 leaf `a36d2e15a3b3d71d` both sides; exact-K=2; n=400 deck-paired =
200 decks × 2 seats):

| # | cell | candidate | total | ×deploy | band |
|---|---|---|---|---:|---|
| 1 | `pareto_k4x344_1376_vs_deploy` | k4×344 | 1376 | 0.5× | 60e9 |
| 2 | `pareto_k2x688_1376_vs_deploy` | k2×688 | 1376 | 0.5× | 60e9 |
| 3 | `pareto_k4x172_688_vs_deploy` | k4×172 | 688 | 0.25× | 62e9 |
| 4 | `pareto_k2x344_688_vs_deploy` | k2×344 | 688 | 0.25× | 62e9 |
| 5 | `pareto_k4x1376_5504_vs_deploy` | k4×1376 | 5504 | 2× | 64e9 |

Cells 1+2 **share band 60e9** and 3+4 **share band 62e9** — deliberately, so the
within-tier allocation contrast is a **deck-matched double-CRN delta** (the CL-054
method) rather than a comparison of two independent absolutes. Bands 58/60/62/64e9
were chosen by ENUMERATION of every band in `results.csv` (burned:
1.2–3.13, 4.21, 5, 6, 8.8, 9.4, 10, 12.7, 13, 13.2, 15, 17, 22, 24, 26, 28, 32, 39,
40, 44, 46, 48, 52, 56e9; 99e9 is pre-flight scratch, never harvested).

Cell 5 fills a real gap: **2× has never been measured head-to-head vs deploy** —
CL-060 measured 1×, 4×, 8× vs deploy, and 2× only against the h800 rung.

## Read-out rules (pre-registered)

1. **Report BOTH statistics for every cell** — winrate z AND deck-paired margin z.
   Quoting only the one that clears 2σ is how three findings here were later
   overturned (c=3 "+47", anchor-fraction "+39", flywheel "+88.7").
2. **Within-tier allocation contrast = deck-matched delta on the shared band**, not
   a difference of the two absolute elos.
3. **If the allocation delta is |z| < 1**, POOL the tier's two cells into a single
   n=800 estimate of what that budget costs vs deploy. Registered here, in advance,
   because post-hoc pooling was the un-preregistered step in CL-067.
4. **The curve is plotted against MEASURED wall-clock** (`prefix ms/move` from each
   cell's own summary, both sides solver-free counters) — not nominal sims — plus
   solver s/game, plus the resulting **% of the 900 s tournament clock**.
5. **⚠️ EXPECTED SIGN IS NEGATIVE.** Less compute should be weaker. A *positive*
   result at a lower budget is a red flag for a config error (wrong side, wrong
   leaf, seat imbalance) — investigate the manifest before believing it. This guard
   is registered because the curve's whole purpose is to price a downgrade, which
   makes a flattering result the dangerous one.
6. **NOTHING IS PROMOTED FROM THIS.** `governance/PRODUCTION.yaml` and the champion
   stay untouched. A sub-deploy config becomes a *proposal for Joshua* only if it
   costs **< ~1σ (≈17 elo at n=400)** while materially cutting clock usage — and
   then it owes its own fresh-band confirmation before any promotion, per the
   never-promote-from-a-single-screen rule.

## Validity guards (a cell is INVALID, not merely negative, if any fail)

- `deck_hash` mismatches ≠ 0 within a cell.
- Either side's leaf hash ≠ `a36d2e15a3b3d71d`, or the log's "BOTH SIDES curve125"
  line is not YES.
- Solver `timeouts` ≠ 0 (a timeout silently changes the endgame policy).
- Games short of the requested n (the harness has clipped before — CL-023 n=384).

## Operational

Two boxes, `--shared-claim` work-stealing on one pool per cell, **W=16 each**
(Joshua's call; the measured pure-CPU optimum on local is higher, so this
sacrifices some throughput for interactive headroom). Pure CPU — `--info fair` runs
no net, so no carc-orch, no GPU, no OMP-pin concern. Cells run in the listed
priority order and are individually resumable; whatever the queue does not reach
by morning simply stays queued.

**ETA (from `cl060_budget_local.log`, the same harness at W16 local: 91 s/game at
candidate 11008 + opponent 2752):** modelled serial cost/game = cand ms/move × 70
+ 263 s opponent + ~31 s solver ⇒ n=400 combined-box ≈ **2.0 h** (cells 1,2),
**1.7 h** (cells 3,4), **3.8 h** (cell 5); **~11 h for the full queue**, i.e. the
first four cells should land overnight.

⚠️ If the queue must be killed, **clean stranded `.claim` files before resuming** —
a killed `--shared-claim` run strands claims and a resume stalls forever.

---

# Results (2026-07-27) — all five cells, read out under the rules above

Every cell: n=400 deck-paired (200 decks × 2 seats), exact-K2, both sides frozen
curve125 `a36d2e15`, **0 solver timeouts**, **0 guard failures**, cost ratio matching
nominal budget to ±2% (an independent confirmation that each cell really ran the
budget it claims).

| tier | alloc | total | elo | 1σ | **wr z** | **margin z** | %clock |
|---|---|---:|---:|---:|---:|---:|---:|
| 0.25× | k4×172 | 688 | −46.3 | 17.5 | −2.65 | −6.29 | 9.1% |
| 0.25× | **k2×344** | 688 | **−37.5** | 17.5 | −2.15 | −3.28 | 9.2% |
| 0.5× | **k4×344** | 1376 | **+0.9** | 17.4 | +0.05 | −1.26 | **14.6%** |
| 0.5× | k2×688 | 1376 | −17.4 | 17.4 | −1.00 | −2.78 | 14.5% |
| 1× | k4×688 | 2752 | 0 (anchor) | — | — | — | 26% |
| 2× | **k4×1376** | 5504 | **+12.2** | 17.4 | +0.70 | +1.23 | 46.6% |
| 4× | k8×1376 | 11008 | +49.9 | — | — | +3.48 | 91% *(CL-060)* |
| 8× | k16×1376 | 22016 | +35.6 | — | — | +2.68 | 178% *(CL-060)* |

## 1. The curve is FLAT-THEN-CLIFF, not a uniform slope

**1376 → 5504 — a 4× span — is statistically indistinguishable from deploy**
(+0.9, 0, +12.2; every |z| < 1.3 on both statistics). Below 1376 it falls off a
cliff: −37.5 at 688, with both statistics significant. Above 5504 the real gain
appears (+49.9 at 11008).

⚠️ This **refutes the shape** CL-046's low-budget ladder suggested (~−27 to −34 elo
per halving, roughly uniform). Its *levels* were already known not to transfer
(k_dets=8); this says its *shape* does not either. The prereg called that ladder
"indicative only" — it was not even that, in the region that matters.

## 2. Optimal width GROWS with budget — the axis is now four points long

The allocation contrast **flips sign** between tiers (deck-matched, shared band):

| budget | 688 | 1376 | 2752 | 11008 |
|---|---|---|---|---|
| k4 − k2 (or k8−k4) | **−2.21** (z −1.92) | +1.34 (z +1.10) | +1.82 (z +1.33) *(CL-054)* | +22 elo (z +1.16) *(CL-060, k8−k4)* |
| best width | **k2** | k4 | k4 | k8 (nominal) |

This is the textbook determinization story, and it is exactly what CL-060
hypothesised ("optimal width grows with budget") but **explicitly could not
establish** from its own data. This run adds the downward half.

⚠️ **Weight it honestly: no individual contrast clears 2σ** (−1.92 / +1.10 / +1.33
/ +1.16). The evidence is the **monotone pattern across four independent budgets**,
not any single cell — the same standard CL-054 used to call a coherent axis
credible rather than a lone spike. Pooling was **blocked by rule 3 in both tiers**
(|z| ≥ 1), which is the rule working: pooling arms that genuinely differ would
have averaged a real effect into mush.

## 3. What this means for the tournament clock

The clock-legal range is where this bites. Within everything comfortably legal
(≤ ~50% of clock), **budget buys nothing measurable**: 1376 (14.6%), 2752 (26%)
and 5504 (46.6%) are one flat region. The only real gain we have measured, +49.9,
sits at **91% of clock** — unusable in sudden death.

⇒ This **sharpens** [TOURNAMENT_TIMING_2026-07-26](../../docs/research/TOURNAMENT_TIMING_2026-07-26.md).
It is not merely that 4× is unspendable; it is that **everything you *can* spend is
already spent.** Search budget is a closed lever for clocked play, in both directions.

The one actionable option: **k4×344 (1376) halves clock usage to 14.6% for no
resolvable strength cost** — real margin against time trouble.

## 4. Rule-6 status, and what is OWED

> **✅ DEBT DISCHARGED / ❌ CLAIM REFUTED — 2026-07-28.** The confirmation this section
> demanded ran on fresh band **76e9** (n=400 deck-paired, identical config, env replicated
> byte-for-byte from the original cell's manifest, laptop-only W16, code_rev `4e67f2b`):
> **elo −53.4 ± 17.6, winrate 0.4238 (z −3.05), deck-paired margin −3.285 pts/deck
> (z −3.54)**, cost ratio 0.50× verified, 0 timeouts, 400/400 endgame latches, 0 deck_hash
> mismatches. Versus the original cell (+0.9 ± 17.4, band 60e9) the difference is
> **−54.3 ± 24.7 = z −2.20**, and the confirm lands *outside* the original's own 95% CI —
> so pooling is BLOCKED by the same logic as rule 3 (an inverse-variance pool would read
> −26.0 ± 12.4 and **must not be cited as an estimate**). Note the original's *margin*
> statistic already leaned negative (z −1.26); it was the winrate dead-tie that failed to
> reproduce — **rule 1 working exactly as designed.** ⇒ under rule 6 (`< ~1σ` to be
> proposal-eligible) `k4×344` costs **3.1σ** and is **NOT proposal-eligible**; do not
> propose it for production. The deploy budget k4×688 = 2752 (26% of clock) stays.
> Read-out: [G2_CONFIRM_READOUT_20260728.md](G2_CONFIRM_READOUT_20260728.md);
> `results.csv pareto_k4x344_1376_vs_deploy_CONFIRM`; DECISIONS 2026-07-28.
> *The 2026-07-27 text below is preserved unedited.*

Under rule 6, `k4×344` **is proposal-eligible** (costs < 1σ while materially cutting
clock). It is **NOT promoted**, and `governance/PRODUCTION.yaml` is UNTOUCHED.

⚠️ **The honest limit on the headline.** +0.9 ± 17.4 gives a 95% interval of roughly
**[−33, +35] elo**. That rules out a *large* loss, not a *moderate* one — "halving is
free" is **not** established, and rule 3 blocked the pooling that would have tightened
it. This project has overturned three findings that looked this clean at n=400
(c=3 "+47", anchor-fraction "+39", flywheel "+88.7"). **What is owed before anyone
acts: a fresh-band n=400 confirmation of `k4×344` vs deploy** (bands 60/62/64e9 now
burned). Only after that is a production proposal appropriate, and it remains
Joshua's call.

## 5. Validity note — mid-run branch switch, checked and cleared

The repo was switched to branch `android-app` by another session while the queue ran,
so the cells recorded three different `code_rev` values (`0bfdc00` / `b2e6744` /
`b9150a9`), and the two boxes differed *within* cells 3–4. **Verified harmless:**
`eval_fair_puct.py` is md5-identical (`26b75b2bf6b3`) and the `src/carcassonne_ai/` +
`engine/` tree hash is identical (`d634871ba112`) across all three revs. The
intervening commits touch only docs, tests, the GUI, `play_harness` and the Android
app — none on the eval import path. Results are comparable across cells and with
CL-060's.
