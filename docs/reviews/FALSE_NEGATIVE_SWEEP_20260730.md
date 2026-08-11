# FALSE-NEGATIVE RESERVOIR SWEEP — 2026-07-30

> **⚠️ STATUS 2026-07-30 — COMPLETE, FINDINGS FOR TRIAGE. This memo changes nothing.** It is the
> paper-only discharge of [BURIED_CAVEATS_AUDIT_20260730.md](BURIED_CAVEATS_AUDIT_20260730.md) **F7**
> (Joshua-approved audit follow-up, bucket C). No `docs/LEVER_INDEX.md` row, no
> `governance/CLAIM_REGISTRY.csv` edit, no roadmap line, no `STATUS.md` change was made here — the
> recommended index touches are listed in §6 for Joshua's call. Zero box time was spent.
>
> **Headline: 31 candidates and axes checked across the three never-swept reservoirs → 0
> resurrect-candidates clear the bar.** The reservoirs are not empty of *history* — one of them
> already paid out the single largest pure-leaf gain in the project — but every payout has already
> been collected, and every surviving kill has an independent modern re-test or is architecturally
> moot. The honest shortlist (§5) is three free documentation actions and no cells.

**Commission.** F7 records that the 2026-05-20 retroactive-validation entry measured this project's
own kill error rate at **2 of 4** and then named five reservoirs of likely further false negatives,
of which three were never swept and none was indexed. This memo finds that entry, enumerates the
five, confirms which three are unswept, and sweeps them.

**Method and bar.** For each candidate kill I re-read the original evidence chain at **field level**
(the row in [`experiments/results.csv`](../../experiments/results.csv), the paragraph in
[`DECISIONS.md`](../../DECISIONS.md), the cell in [`CLEAN_RESULTS.csv`](../../clean_eval/CLEAN_RESULTS.csv)),
then asked whether anything measured since removes the kill's evidentiary cover. The bar for
**RESURRECT-CANDIDATE** is a *concrete* reason the original evidence no longer reaches the modern
regime — not "it was underpowered" (that is true of the whole era and is what makes this a reservoir
rather than a queue). Every number below is quoted from the named artifact; anything I computed is
marked **[DERIVED]**.

---

## 1. The 2026-05-20 audit, and which three reservoirs are unswept

The source is [`DECISIONS.md`](../../DECISIONS.md) `## 2026-05-20 (results) — Retroactive-validation
pipeline complete` (index line 139; body line 846). Its measured base rate, verbatim (line 857):

> **Headline:** Of the 4 hypothesized false-negative-suspect calls, the math from the prior entry
> (P(at least one recovered) ≈ 40-50%) actually delivered 2 recoveries.

The five reservoirs are listed under **"Broader audit — other reservoirs of likely false-negatives"**
(lines 866–873). Their disposition:

| # | Reservoir (verbatim head) | Swept? | Evidence |
|---|---|---|---|
| 1 | **Single-iteration rejections** — "Highest EV: chain Option B forward (iter_B2, iter_B3, iter_B4)" | ✅ **ACTIONED** | chained to B4 and killed 2026-05-24 (`DECISIONS.md:733`, `:751` — "Option B as a chain lever is dead"); rows `B2_vs_iter01_anchor` −6.1±17.4 / `B4_vs_iter01_anchor` −19.1±17.4, both n=400 |
| 2 | **Smoke-test rejections (n=20-50)** | ❌ **NEVER SWEPT** | → §2 |
| 3 | **Coarse hyperparameter sweeps** — "never tried 0.5, 3.0, 5.0 … never tested cap=20 or cap=∞" | ✅ **ACTIONED** | → correction below |
| 4 | **Pre-bug-fix benchmarks** | ❌ **NEVER SWEPT** | → §3 |
| 5 | **Other plane mismatches** — "cap value at train vs play, leaf-eval variant at train vs play, orchestrator on/off — not systematically audited" | ❌ **NEVER SWEPT** | → §4 |

**Precision correction to F7 (reservoir 3).** F7 credits the coarse-sweep item to "C5-S5's c_puct
wings and F6-S1's cap=∞". Both of those are real, but they are *second* re-tests. Reservoir 3 was
actioned **within six days**, exactly as the same entry's own next-step plan promised ("wider c_puct
sweep at sims=200; cap=20 and cap=∞ smokes", line 875): `experiments/results.csv` carries
`phase4_cap20_vs_cap12` (−21.7 ± 17.4, n=400) and `phase4_capInf_vs_cap12` (−0.9 ± 17.6, n=390) on
**2026-05-25**, and the full c-axis `phase2_puct_c{05,10,25,30,40,50}_vs_c15` at n=400 each on
**2026-05-26**. Reservoir 3 is the best-discharged of the five, not a late one.

---

## 2. Reservoir 2 — smoke-test rejections (n ≤ 50)

The audit's own scope rule (`DECISIONS.md:870`), verbatim:

> **Smoke-test rejections (n=20-50).** Even more underpowered than n=100. Any past variant
> rejection where the smoke landed **within ±50 elo of zero** was effectively "unknown" — re-run
> candidates that had borderline smokes.

**13 candidates checked · 2 already-resurrected · 7 kills stand · 4 out of the stated band.**

### 2.1 The reservoir already paid out — and nobody connected it back

**`meeple_K` is a confirmed, collected false negative from this exact reservoir**, and it is the
largest pure-leaf gain in the project's record.

- **The kill** (`DECISIONS.md:1147`, table row, verbatim): `| meeple_K ∈ {0.5, 1.0, 2.0} | 10% (all 3) | 90% | — | -31.8 to -42.2 |`,
  concluded at `:1160` — "**Meeple_K is null** — all 3 magnitudes gave identical outcomes at n=20."
- **The overturn**, five and a half weeks later:
  `experiments/results.csv` `v28_meeple_flat_vs_v27_heur200_n200` (2026-06-22), a **pure-leaf,
  no-net, deck-paired HeuristicMCTS@200** cell: `145W/50L/5D`, **+179.5 ± 27.9 elo**, avg_diff
  +15.45, `z_margin=9.92`. Its own note field says: *"OVERTURNS n=20 meeple_K null."*
- **Why this matters beyond the one lever:** that leaf became **v2.8**, which became v2.9.1
  `Bmild_cap8` (promoted, CL-041), which became **v2.9.2 `Bmild_cap8_curve125` — the leaf the
  current champion runs today** ([`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml),
  `leaf: v2_9_2_Bmild_cap8_curve125`). The entire production leaf lineage descends from a lever this
  reservoir had recorded as dead.

The recovery was found by an unrelated 2026-06 leaf probe, **not** by sweeping the reservoir. So the
reservoir's realized error rate is **1 of 2 strength knobs in its single densest entry** — matching
the audit's measured ~50% and, unlike the audit's own recoveries, never fed back into the record as
a reservoir result.

**Two citation defects in that overturn chain, both verified this pass.** `DECISIONS.md:2684` and
`experiments/results.csv:175` each date the overturned null to **"2026-05-14"**. The `meeple_K`
table is inside the entry headed `## 2026-05-15 — v3 leaf: cap tuning is fitting n=20 noise`
(`DECISIONS.md:1128`); there is no `meeple_K` verdict in any 2026-05-14 entry. A grep for the kill
by its own date misses it from both surfaces that cite it.

### 2.2 The entry that produced it disqualifies its own instrument, three paragraphs later

This is the sweep's most transferable finding. The 2026-05-15 v3 entry contains **two** kills
(`meeple_K`, `opp_cap`) and **two** self-declared defects in the instrument that produced them:

1. **The reference was saturated** — `DECISIONS.md:1170`, verbatim: *"Tier-1 is saturated as a
   reference now — same ~80% wr regardless of leaf cap, so it doesn't discriminate iter_00 from
   anything similar in strength."*
2. **The knob reached only one side** — `DECISIONS.md:1134`, verbatim: *"`RuleBasedPlayer` uses
   `virtual_score_inplace` from `virtual_score` (v1, NOT v2) … So the `CARCASSONNE_V25_*` env vars
   **only affect the NN's hybrid_v2 leaf, not the rule-player side.**"*

So the kills were graded by a **saturated, leaf-asymmetric** instrument at **n=20**. That is a worse
defect than the small n, and it is stated in the same document as the verdicts. One of the two kills
was later worth +179.5 elo.

**Date correction to my own framing, and to a natural reading of F7.** This entry is *not* a
pre-bug-fix benchmark. `DECISIONS.md` is newest-first within a day; the v3 entry (`:1128`) opens
*"Post-iter_00 retrain landed today"*, and `iter_00` is the checkpoint trained **in** the dedup-fix
entry (`:1173`, same day, earlier). The v3 sweep therefore ran on **fixed** leaf code. It belongs to
reservoir 2 (smoke size) and **not** reservoir 4. That isolates the mechanism cleanly: the
`meeple_K` false negative was caused by **sample size × a saturated reference**, not by inflated
bonus magnitudes.

### 2.3 Per-candidate verdicts

**KILLS STAND (7)** — compact, each with the modern evidence that covers it:

| candidate | original kill | why the kill stands |
|---|---|---|
| **`opp_cap` ∈ {5,8,20,30}** (asymmetric opponent cap) | n=20, two arms escalated to n=50; `DECISIONS.md:1146-1158` | **Re-killed in the modern regime at the champion's own deploy config**: `c5_oppcap4_vs_puctchamp2750_k2` **−59.6 ± 35.3** (avg_diff −5.13) and `c5_oppcap12_vs_puctchamp2750_k2` **−66.8 ± 35.4** (avg_diff −1.53), n=100 CRN-paired, 2026-07-10, PUCT-priors champion at s2750 exact-K≤2. Both point estimates negative. Already indexed (`LEVER_INDEX.md:176`). ⚠️ My reservoir-2 enumeration agent reported this axis as never re-tested — **that is wrong**; the C5 rows exist and I read them. |
| **v3 bonus-cap tuning / "cap=12 is the local optimum"** | n=20 → n=50, same entry | Superseded *upward*, not merely reconfirmed: the cap axis was re-swept post-fix many times and the one real move was found — **cap 5→8, +46.3 ± 18 at n=400** (`v291_waveB_bmild_cap8_vs_cap5_s200_n400`). The wings are powered nulls: cap=20 at **n=1600 = +1.1 ± 8.7** (`hygiene_cap20_n1600`), cap=∞ −0.9 ± 17.6 (n=390), cap=6 +4.3 ± 17.4 (n=400). CL-028; "the longest null record in the project" (`LEVER_INDEX.md:175`). |
| **PUCT c=2.0** (n=20 winner that evaporated at n=50) | `DECISIONS.md:1101-1126` | Resolved by the audit's own pipeline: **+5.2, 0.3σ at n=400** (`puct_c2_vs_c15`). The whole axis then swept at n=400 ×6 points (2026-05-26) and re-swept at the deployable budget — `PRODUCTION.yaml` records c_puct 1.5 *"re-swept AT the deployable 2750 sims (interior plateau)"*. |
| **Option-2 NN-value-leaf blend re-smoke** | n=50, 31% wr | Decisive **despite** n=50 (2.7σ); the audit itself correctly excluded it. Now over-determined by CL-039 / CL-042 (M2 KILL) / CL-064 / CL-065 / CL-073. |
| **Path-B Step-9 blend bracket λ∈{0.1,0.25,0.5}** | n=30 each; `step9_blend_lam*` rows, −46.6 (inside the ±50 band) | Same axis, well-powered modern kills at the *opposite* extreme: NAIL2 arms **−159.8** (n=100) and **−246.3** (n=100), NAIL3 frozen-value **−224.9** (n=172). The value-as-leaf channel is the most re-killed thing in the record. |
| **C-cheap v2 λ=0.1 arm (+137 @ n=40)** and **λ=0.5 arm (+88.7 @ n=40)** | declined 2026-07-10 | **Outside the audit's stated band** (both far past ±50, and both are *positive screens*, not rejections). The decline is also correctly reasoned at `DECISIONS.md:2891`, verbatim: *"chasing a post-hoc arm after a failed pre-registered gate is exactly the c=3-noise-spike mistake."* The pre-registered winner (λ=0.25) then failed the confirm at n=200 (+9.2 vs a ≥+35 gate); CL-050's reopen bar is *a new mechanism, not another blend*. |

**ALREADY RESURRECTED (2)** — `meeple_K` (§2.1) and the `iter_B1` n=20 anchor gate (70%, `DECISIONS.md:961`),
which the 2026-05-20 audit itself recovered to **+25.2 at n=400**.

**OUT OF THE STATED BAND (4)** — `az_zero` tabula-rasa n=50 ×7 (−346.1 to −800.0, CL-066);
Phase-4 v1/v2 recipe kills at n=30/50 (−134 / −200 elo, CI excludes the acceptance threshold);
the λ=1.0 pure-NN-leaf 0W/14L partial; the meeple-only-rules diagnostic (−42 elo, a diagnostic
aside, not a lever verdict). None is "within ±50 elo of zero"; the audit's own rule excludes them.

---

## 3. Reservoir 4 — pre-bug-fix benchmarks (evidence dated ≤ 2026-05-14)

**10 candidates checked · 3 kills stand · 4 moot or superseded · 2 leaf-independent · 1 pointer · 0 resurrect.**

### 3.1 Two structural findings about this reservoir

**(a) It is invisible to the source-of-truth table by construction.**
[`experiments/results.csv`](../../experiments/results.csv) has **zero rows before 2026-05-20** —
verified by `awk` over the date column; the results discipline was created 2026-05-28. So the entire
pre-fix era exists only as `DECISIONS.md` prose. That is *why* it was never swept: the standing
instruction is to query the table, and the table cannot see it. Any future sweep of this era must be
a prose read.

**(b) The bug the audit named is the *smaller* of the era's two defects.** Every strength verdict in
this era was graded against **Tier-1 (`RuleBasedPlayer`)**, which the record declares saturated
(`DECISIONS.md:1170`, quoted in §2.2) and which runs the **v1 object leaf**, immune to the
`CARCASSONNE_V25_*` knobs under test (`DECISIONS.md:1134`). Inflated bonus magnitudes shift an
optimum; a saturated, leaf-asymmetric reference cannot resolve *any* effect. The audit's framing
("tested against inflated bonus magnitudes") understates what is wrong with the era.

### 3.2 Per-candidate verdicts

**KILLS STAND (3):**

| candidate | original kill | why the kill stands |
|---|---|---|
| **Uncapped `virtual_score_v2` with the original P-schedule {1:1.0, 2:0.5, 3:0.25}** — the one genuine bucket-(iii) item in this reservoir | 2026-05-14: hybrid_v2 wr 30.0% vs hybrid_v1 76.7%, "~47pp regression" (`DECISIONS.md:1326-1338`); diagnosed as tanh saturation from a bonus scale 4–7× v1 base | This is the closest thing in the reservoir to a real candidate, because the dedup fix *reduced* bonus magnitudes and so would reduce the diagnosed saturation. It is nonetheless closed by three independent post-fix measurements: **cap=∞ is a null, not a regression** (−0.9 ± 17.6, n=390) — so "uncapped kills you" is already dead; **the closure-P schedule is a null** (`c5_pclose080/120`; `LEVER_INDEX.md:177` — "already well-tuned; closure-probability accuracy is not the lever"); and the *joint* case is covered by the one piece of evidence purpose-built for it — **CL-057's 7-knob Optuna/TPE sweep over c_puct/tau_p/value_norm + curve/closure/caps scales, explicitly run as "interaction insurance", CLOSED NULL** with its two firing candidates killed on the fair-transfer test. Resurrecting this would require an interaction win between two individually-neutral knobs in the exact space a TPE search already covered. |
| **NN value head as the search leaf** | 2026-05-14, "35-percentage-point swing … actively harmful" | Never overturned; now the founding, five-times-re-earned closure (CL-039 / CL-042 / CL-064 / CL-065 / CL-073). |
| **v2.5 cap sweep points cap=2 / 8 / 15** | 2026-05-14, n=30 each | Re-swept post-fix repeatedly; cap=8 was subsequently *adopted* (v2.9.1). The pre-fix reading is superseded by better data on the same axis, in the same direction the audit predicted (the optimum moved). |

**MOOT / SUPERSEDED (4):** sims=50 and the "sims=400/800 scaling ceiling" (the deploy budget is
**2752** and the measured curve reaches **11008**; the budget axis was reopened by CL-060 and
promoted by CL-071 at **+49.85 elo** — this old ceiling claim is the direct ancestor of the defect
F9 caught, and it is already reopened); uniform-priors-vs-NN-priors (the champion has **no NN**, and
the modern analogue — heuristic priors in PUCT — *won*, CL-041/CL-044); the v1–v6 self-play recipe
family incl. warmstart-mix floors and the cancelled symmetry-aug v7 (closed by CL-065
representation-independent leaf closure + CL-066 tabula-rasa flatline; symmetry-aug independently
re-tested null 2026-06-10, `LEVER_INDEX.md:117`).

**LEAF-INDEPENDENT INFRA (2):** the orchestrator multi-process pool / `batch_timeout_ms` / CUDA MPS
/ W-count / OOM findings, and fp16 — none touches the leaf. (fp16 was already partially reversed on
its own merits 2026-06-01 and is indexed.)

**POINTER, NOT A KILL (1):** `--temp-threshold` (15) and Dirichlet (α 0.3 / ε 0.25) were **set** in
this era (2026-05-08), flagged stale 2026-05-26, and **still never swept** — `LEVER_INDEX.md:77-78`
and untried-list item 1. This is the mirror image of the reservoir (a default frozen with no
evidence rather than a variant killed with bad evidence) and it is **already indexed**, so the sweep
adds provenance, not a new row.

### 3.3 The check that matters, and it comes back clean

**Does any knob the current classical champion actually reads rest on pre-2026-05-15 evidence?**
Walking [`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml)'s live knobs against the
record: `bonus_cap`=8 (v2.9.1 wave B, n=400) · closure-P schedule (`c5_pclose*`) · `drop_three_open`
(`v28prod` baseline) · `v29_meeple_curve` ×1.25 (CL-051, fair-confirmed at 451 paired decks) ·
`tanh_norm`=15 (`v210_winshape_n4` screen **+18.3** → fresh-band **−27.9** → combined n=800 null;
"win-shaping axis dead") · `opp_bonus_cap` (`c5_oppcap4/12`) · `c_puct`=1.5, `tau_p`=5.0,
`select=visits`, `reuse` (CL-044), `k_dets` (CL-054), budget (CL-060/CL-068/CL-071), FPU (M3).

**Every one has post-2026-05-15 measurement. Zero live champion knobs rest on pre-fix evidence.**
That is a checkable negative result and it is the main reason this reservoir yields nothing.

---

## 4. Reservoir 5 — other plane mismatches

The audit's named list (`DECISIONS.md:873`), verbatim:

> **Other plane mismatches.** The sims=200 / sims=800 mismatch was caught. Other potential
> mismatches: cap value at train vs play, leaf-eval variant at train vs play, orchestrator on/off —
> **not systematically audited.**

**8 axes checked · 5 resolved · 1 not a mismatch at all · 1 open but moot · 2 modern successors already institutionalized · 0 resurrect.**

No entry anywhere re-cites this checklist by name — it was never revisited *as a checklist*. But
each axis was discharged piecemeal, and two of the discharges found real, large artifacts.

| axis | verdict | evidence |
|---|---|---|
| **leaf-eval variant, agent vs opponent** | ✅ **RESOLVED — and it was a ~192-elo artifact** | The mismatch cell `iter8_v28_vs_heur3200_v27_n200` read **+153.4** with the caveat recorded in its own note ("part of the gain is the leaf gap. Disambiguate with heur@3200_v2.8"). The purpose-built disambiguator `iter8_v28_vs_heur3200_v28_n200` then read **−38.4 ± 24.7** at equal leaf, note verbatim: *"=> the +153.4 vs heur@3200_v2.7 was **ENTIRELY** the leaf gap."* **[DERIVED]** the artifact is 153.4 − (−38.4) ≈ **191.8 elo**. |
| **leaf-eval variant, train vs play** | ✅ **RESOLVED — the central defect of the learned-value era** | Production self-play hardcoded `--leaf-eval v2_5` for generation, so the net value never drove a move in training data at all ([`docs/CORRECTION_PLAN_2026-06-02.md`](../CORRECTION_PLAN_2026-06-02.md) §F-B1); fixed by the G-S1 value-in-loop wiring and regression-guarded by `tests/test_value_in_loop_fb1.py`. |
| **cap value, baseline vs production** | ✅ **RESOLVED — a real mislabel, corrected** | CL-028: every prior v2.9 run was measured against `DEFAULT_CONFIG` = cap=5 + 3-open, **not** production cap=12 + drop-three-open, so *"Bmild beats v2.8"* really meant *"beats cap5/3-open"*. A real `v28prod` baseline was built and the throne test re-run (**+55.2 / z+3.94** at s200, then **+64.3 / z 3.77** at h6400 = CL-041's promotion arbiter). |
| **cap / leaf variant, per-side isolation** | ✅ **RESOLVED BY INFRA** | `eval_puct_priors.py` fed `DEFAULT_CONFIG` to *both* sides, making leaf A/B structurally impossible; the S0 harness patch (`--cand-leaf-json`, per-side `leaf_hash`) landed 2026-07-10 and is the prerequisite for CL-051. Provenance is now runtime-recorded per side (`src/carcassonne_ai/eval_provenance.py` carries `cap` and `opp_cap` fields). |
| **sims, train vs play** | ✅ **RESOLVED** | The originally-caught case; matched-plane testing became standing practice. |
| **orchestrator on/off** | ✅ **NOT A PLANE MISMATCH** | Result-neutral, and *measured* so — not asserted. The earliest statement is contemporaneous with the reservoir itself, `DECISIONS.md` 2026-05-14, verbatim: *"numerical agreement <1e-5 vs baseline at sims≥200; at sims=100 small float noise → argmax flips → different MCTS games. **Production sims=200 is fine.**"* Later reinforced by bit-exact gen parity, 6/6 bit-identical eval games, and a standing regression test (`tests/test_bare_net_opponent.py`). The audit flagged as "not audited" something that had been measured five days earlier. |
| **self-play-side `c_puct` vs eval-side `c_puct`** | ⚠️ **GENUINELY OPEN — AND MOOT** | The one axis with no re-test on record. `DECISIONS.md:673` (2026-05-28) documents the conflation explicitly and queues an A/B that was never executed; the entry's own falsifier: *"Train iter_X(c=1.5_sp) and iter_X(c=3.0_sp) from the same warm-from."* It is aggravated by the fact that the eval-side evidence which justified the bump later shrank: **+47.2 ± 17.5 (n=400) → +18.5 ± 8.7 (n=1599)** (`phase2_puct_c30_vs_c15` → `hygiene_c3_vs_c15_n1600`). **But it does not bind anything live:** the neural `run_selfplay_iter.py` track is closed (CL-065/CL-066/CL-073), and the live full-budget flywheel already sets the other value — [`RODV3_TURN1_PREREG.md`](../../scripts/distill_flywheel/RODV3_TURN1_PREREG.md) line 43: `--c-puct 1.5 --tau-p 5.0 --value-norm 15.0`. See shortlist item **S3** for the free action. |
| **fair vs clairvoyant** (modern successor) | ✅ **INSTITUTIONALIZED** | The largest plane split in the record, and one the 2026-05-20 audit could not have named. CL-045: the clairvoyance tax at the champion's own config is **~156 elo**. CL-048: **~100–150 elo across a 7× sims range, and it does not close with depth**. CL-057: *"clairvoyant edges wash out ~4:1 under PIMC."* Every candidate in reservoirs 2 and 4 was measured **clairvoyant**; the standing protocol is now clair-screen → mandatory fair-confirm (CL-051/CL-054 template). |
| **equal-sims vs equal-wall-clock** (modern successor) | ✅ **LIVE AND TRACKED** | CL-067, verbatim: *"The 4x teacher's strength edge CAN be distilled into net POLICY priors that beat the deploy champion **AT EQUAL SIMS** … Whether it beats the champion at **EQUAL WALL-CLOCK** … is SEPARATE and currently points NEGATIVE."* The same result is a strength-confirm and a deployability-kill. CL-071 then reopened the clock side via k-parallel. |

### 4.1 The one modern instrument that argues *for* resurrection — and why it does not bite here

Intellectual honesty requires flagging this rather than only citing the instruments that argue
against. **Cross-band over-dispersion** ([`CLIFF_LADDER_88E9_READOUT_20260729.md`](../../measurement/classical_search/CLIFF_LADDER_88E9_READOUT_20260729.md))
measures the true band-level σ at **2.20× nominal for elo and 1.83× for deck-paired margin**, with
the citation rule *"Inflate σ by ~1.5–2× on ANY cross-band comparison in this family."* Applied to a
**null**, σ-inflation means the effect a null could be hiding is ~2× larger than its nominal power
calculation implied — i.e. it **raises** the historical false-negative rate across the board.

It does not flip any verdict above, for a specific reason each time: the modern re-kills that carry
the load here are **within-band CRN-paired** contrasts (the C5 `oppcap` cells, the `v210` gates, the
C7 dose axes) or **accumulations across many independent cells** (the cap axis, the value-as-leaf
family), and the readout's own scope note carves exactly this out — *"Prefer within-band
deck-matched contrasts"*, and *"Nothing here reopens or weakens CL-071."* Where a candidate rests on
a *single cross-band* null I have said so; none of them does.

---

## 5. F8 — the v1-vs-v2.7 leaf anomaly, dissolved on arithmetic

**The anomaly.** [`clean_eval/CLEAN_RESULTS.csv`](../../clean_eval/CLEAN_RESULTS.csv) row
`r1_leafgap_heur_v2_7_vs_v1_s200`, read at field level: **n=400 (200 decks, paired), sims=200,
181W/209L/10D, wr 0.465, elo −24.360, σ 16.466, avg_diff −1.85**, band `[1000000000, 1000000200]`,
commit `1973fc1e37`, A-side `HeuristicMCTS` `v2_7` (cap 12.0, c 3.0), B-side `HeuristicMCTS` `v1`.
`CLEAN_EVAL_AUDIT.md:54` classifies it *"inconclusive (leans v2.7-WEAKER)"*, and CL-010's registry
row still carries it as a live caveat: *"v1 may simply be the STRONGER standalone leaf."*

**What was actually compared, and in which direction.** A **fully-tuned** v2.7 (CAP=12,
DROP_THREE_OPEN) against an **untuned** v1, both as bare `HeuristicMCTS` with **no net**, at sims=200,
deck-paired. The sign means v2.7 sits **24.4 elo below** v1. Both sides post-date the 2026-05-15
dedup fix **and** the 2026-05-29 farmer-adjacency involution fix, so the cell itself is clean.

**The arithmetic.** The audit's F8 proposes chaining the within-branch gains "since v2.7" and
starting the chain at v2.9.1-vs-v2.8. **That chain misses its own strongest and best-matched link.**
The very first step off v2.7 is measured by a cell with the *same protocol shape as the anomaly* —
pure leaf, no net, `HeuristicMCTS`@200, deck-paired:

| step | cell | elo ± σ | protocol |
|---|---|---|---|
| v2.7 − v1 | `r1_leafgap_heur_v2_7_vs_v1_s200` | **−24.4 ± 16.5** (z 1.5) | pure leaf, no net, s200, 200 decks paired |
| **v2.8 − v2.7** | `v28_meeple_flat_vs_v27_heur200_n200` | **+179.5 ± 27.9** (`z_margin` 9.92) | **pure leaf, no net, s200, paired — protocol-matched** |
| v2.9.1 − v2.8prod | `v291_THRONE_bmild_cap8_vs_v28prod_s200_n400` | +55.2 ± 18 (z 3.94) | pure leaf, s200, n=400 |
| ″ at deploy depth | `v291_THRONE_bmild_cap8_vs_v28prod_h6400_n399` | +64.3 ± 17.7 (z 3.77) | pure leaf, h6400, fresh band |
| v2.9.2 − v2.9.1 | CL-051 curve125, fair confirm | +48.8 (z 3.13), margin +50.4 (z 2.77) | fair PIMC, 451 paired decks |

**The single protocol-matched link settles it without any chaining.** **[DERIVED]**
179.5 − 24.4 = 155.1 elo; combined σ = √(27.9² + 16.5²) = 32.41; **z = 4.79**. The v2.7 line passed
v1 at its *first* step and never looked back.

**Three stress tests, because the project's own record says elo chaining is unreliable.**

1. **Non-transitivity.** The record contains a measured 41-elo transitivity error
   (`b512_vs_b256_v28_n400`: *"transitivity predicted −43 … but direct is −1.7"*). **Immaterial
   here** — the verdict uses one direct link, not a chain.
2. **Depth washout.** The v2.8 step is measured only at s200 — but so is the anomaly, so the
   comparison is **depth-matched** and answers exactly the question asked. Separately, the one leaf
   step measured across depth was **depth-robust, not washed out** (+55.2 at s200 → +34.9 at s800 →
   +64.3 at h6400); the sims-washout law governs *net/policy* gains, not leaf gains. Even applying
   the harshest observed leaf attenuation (55.2→34.9 = 0.63×) to the v2.8 step **[DERIVED]** leaves
   ~+113 elo, still 4.6× the gap.
3. **Cross-band over-dispersion (§4.1).** The two cells are on different bands, so inflate both σ by
   the worst measured factor, 2.2×: **[DERIVED]** σ_comb = 2.2 × 32.41 = 71.3 → **z = 2.18**. Still
   past 2σ. The verdict survives the most pessimistic correction in the project's toolkit.

**Verdict: F8 DISSOLVED ON PAPER. No cell is warranted.** The "v1-leaf fork" was declined in 2026-06
for re-tune cost; it should now be recorded as **closed on arithmetic**, because the branch that was
24.4 elo behind at the moment of measurement is **[DERIVED]** roughly **+210 elo ahead** by the
v2.9.1 step alone (−24.4 + 179.5 + 55.2, s200 plane, chained — flagged as chained and therefore the
*weaker* of the two readings offered here; the +179.5 single link is the load-bearing one).

**What one cell would settle, if Joshua wants it anyway** (I do not recommend it): one n=400
deck-paired standalone-leaf cell, `v1` vs `curve125`, on the per-side leaf A/B harness
(`--cand-leaf-json`, per-side `leaf_hash`), at h800 or the deploy budget. **Cost caveat, verified:**
v1 is the **object** leaf (`virtual_score.py`, the path `RuleBasedPlayer` uses) — it has no
`flat_leaf` or Cython form, so the cell runs the slow path at materially above normal rung cost, and
CLAUDE.md's engine note explicitly warns that path is not the production hot path. Paying that to
re-confirm a 4.79σ result is not defensible.

---

## 6. Ranked shortlist for triage

**The paid queue is empty.** 31 candidates and axes; **0 resurrect-candidates** clear the bar. That
is an honest empty result, not a shrug: the sweep found the reservoirs *had* real content (§2.1 —
a +179.5 elo lever), that the content was collected by other means, and that the surviving kills each
have an independent modern re-test or are architecturally moot.

Three **free** actions, ranked by value:

| # | action | cost | value |
|---|---|---|---|
| **S1** | **Stamp the 2026-05-15 v3 entry** (`DECISIONS.md:1128`) with its measured **1-of-2 error rate** and its two self-declared instrument defects (saturated Tier-1; env vars reaching only one side). It is still cited as live evidence from two surfaces (`LEVER_INDEX.md:176` for `opp_cap`; the §6 `meeple_k` row). A reader who follows either citation today lands on an entry that killed a +179.5-elo lever, with no marker. | one banner + two pointer clauses | highest — this is the project's densest single false-negative source and it currently reads as ordinary evidence |
| **S2** | **Fix the two date mislabels** — `DECISIONS.md:2684` and `experiments/results.csv:175` both cite the overturned `meeple_K` null as **"2026-05-14"**; it is at `DECISIONS.md:1128`, dated **2026-05-15**. A grep by the cited date misses the kill from both surfaces that cite it. Then add the reservoir/false-negative-audit row `LEVER_INDEX.md` still lacks (F7's actual dedup complaint: zero hits for `reservoir`, `false.negative`, `pre-bug`, `retroactive`). | two string edits + one index row | high — the dedup index's one job |
| **S3** | **Add one interpretive line to the `rodv3` turn-1 read-out plan**: its gen is the first learned-track generation ever run at **`c_puct` 1.5 self-play** (prereg line 43), which is the never-executed arm of the 2026-05-28 conflation (§4, row 7). Consequence for reading the result: a *growth* signal there is confounded with the budget change and must not be attributed to budget alone; a *null* there is **not** attributable to the old `c_sp`=3.0. Zero incremental compute — the arm is already covered. | one sentence | medium — prevents a future misattribution on a live gate, and retires an 11-week-old open item at no cost |

**Explicitly NOT recommended:** the F8 confirmation cell (§5 — 4.79σ already, and it runs the slow
object-leaf path); any re-open of `opp_cap`, the cap axis, the c-axis, or the value-blend family
(each has ≥2 independent modern kills); the "targeted denial on near-complete large opponent cities"
reframe (it is a **NEVER-TRIED** item already carried at `LEVER_INDEX.md:176` and untried-list item 7
— pointing at it here would double-count an existing queue entry, not add one).

---

## 7. The transferable lesson

The 2026-05-20 audit's measured ~50% kill error rate is real, and this sweep confirms it did not stop
in 2026-05 — but the mechanism it named (small n) was the *lesser* half. In every case the sweep
examined, the decisive defect was **the instrument, not the sample size**: a saturated reference
(§2.2), a leaf-asymmetric knob path (§2.2), a mislabeled baseline (CL-028), a harness that could not
isolate the variable at all (the S0 patch), or a regime the measurement did not cover (fair vs
clairvoyant, equal-sims vs equal-clock). Sample size is cheap to fix and easy to notice. An
instrument that cannot resolve the effect produces a *confident* null, and — as §2.2 shows — the
project has written the disqualifying sentence and the verdict into the **same entry**, three
paragraphs apart, and then gone on citing the verdict — one of its two kills is still cited as live
evidence today, two and a half months on.

The forward-looking version: when recording a null, record what the instrument could have resolved,
not only how many games it played.
