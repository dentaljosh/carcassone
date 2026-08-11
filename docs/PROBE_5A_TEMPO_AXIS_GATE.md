# PROBE §5A — TEMPO/TIMING VALUE AXIS (third-independent-axis gate) — 2026-07-01

Pre-registered design spec for **one final offline gate** before the autopsy's ceiling sentence is
written. Read with the closed AZ-value probes ([PROBE_A_STRUCTURED_VALUE_SPEC.md](PROBE_A_STRUCTURED_VALUE_SPEC.md)
§3A, [PROBE_B_FAIR_INFO_SPEC.md](PROBE_B_FAIR_INFO_SPEC.md) §4A, [PROBE_B_4A_RESULTS.md](../measurement/probe_b_4a/PROBE_B_4A_RESULTS.md)),
the representation gate ([CL-037](../governance/CLAIM_REGISTRY.csv)), and the close entry
([DECISIONS.md](../DECISIONS.md) 2026-07-01 / CL-039).

> **OUTCOME — RAN, INCONCLUSIVE on the rigorous gate, but a live OFFLINE LEAD (2026-07-01, `58262ef`→`334bef8`).**
> Gate-zero PASSED (PARTIAL): the naive structural tempo counts (open-road/city, farmer counts) are
> ≥0.72 reconstructible from the already-present representation and were dropped; a genuine **10-feature
> timing-depth core survives** (depth-weighted meeple lockup Σ open_n, closure-race, contested,
> open-city-delta — mean R²=0.28, canonical ρ₁=0.76 < 0.90). Single-seed 4-arm at h6400: **`tempo_only`
> = +44.7% regret-reduction (τ 0.223)**, a clean monotone sweep, **leak-verified** (all tempo features
> |r|≤0.51 vs oracle_q vs the leaf's own 0.996) — the **strongest clean offline ranker in the whole probe
> program, larger than CL-037's farm/bag −20.5%.** So §5A **did NOT confirm H-5A-inert — tempo is NOT a
> redundant/inert third axis.** BUT the run was single-seed with a **broken positive control** (`both`
> came back +0.0% though the same harness gives +20.5% at n_scalar=44 — appending 10 zeroed tempo columns
> flipped it = RNG-init fragility; non-monotonic `all_three +17.5 < tempo_only +44.7` confirms single-seed
> noise), so the pre-registered ≥3pp seed-swept `Δ_indep` was **never obtained** — the confirming 4×4 seed
> sweep OOM-killed the box before any run finished and was **not relaunched.** **Net: a live, unresolved
> OFFLINE tempo lead that QUALIFIES CL-039's "genuinely low-dimensional" clause** (that close rested on two
> known-redundant axes; the third was *not* redundant offline). **Ship decision UNCHANGED — analyzer + B1**
> (§7 is invariant, and tempo is OFFLINE-only → CL-034's washout precedent → a recorded lead, not a loop
> authorization). Full read: [../measurement/probe_5a/PROBE_5A_RESULTS.md](../measurement/probe_5a/PROBE_5A_RESULTS.md).
> Governance: **CL-040** (qualifies CL-039). The pre-registration below is preserved verbatim as filed.

> **Why this gate exists (the honest reason).** CL-039 closed the AZ-value route on the value-inertness
> ledger and shipped "the residual value beyond the v2.9 leaf is low-dimensional." But the *dimensionality*
> half of that sentence currently rests on **exactly two axes — farm and bag — which we already knew were
> mutually redundant** (CL-037 attribution: farm-only −17.1%, bag-only −19.7%, both −20.5%; §3A on the
> structured head: `Δ_indep = +0.05pp`, ~8σ below the 3pp bar). "The residual is low-dimensional" and "we
> only measured two correlated scalars" are observationally identical so far. Before that dimensionality
> claim is written into the autopsy, test it against **one axis that is uncorrelated-by-construction with
> farm/bag: temporal/tempo signal.** This gate either **earns the strong claim on a third independent axis**
> or **reopens a crack.** It does not change the ship decision (analyzer + B1 either way — see §7); it
> changes what the autopsy is *entitled to say*.

> **Reconciled against live repo state 2026-07-01.** CL-037 (α=0.05 / −20.5% at the **h6400** teacher),
> §3A (Δ_indep 3pp bar, n_test=1544, paired σ≈0.36pp), §4A (depth-saturated at play-800), and CL-039's
> close all check out. The one structural correction folded in: **§4A's failure was a depth error, not a
> target error** — it matched to play-depth 800 where even the clairvoyant control floors to α=0. §5A runs
> at **h6400**, where CL-037's non-inert control *already reproduces* (§4). See §8 for the full conflict map.

---

## 0. Framing (honest prior + boxing rules)

**Prior: expect inert.** The base rate says the third axis reads like the first two — redundant, ceiling
earned. This gate is not a resurrection attempt; it is the **falsifier we owe the dimensionality claim**
before we assert it. The value of running it is symmetric: an inert read *strengthens* CL-039 (three
independent axes, not two redundant ones); a live read *bounds* the strong claim honestly (the residual is
not 1-D along tempo) without reopening the ship decision.

**Boxing rules (binding):**
1. Pre-register hypothesis (both directions), gate-zero, metric, threshold, read-out — done here, before any run.
2. Time-box: ~1 day, same order as §3A/§4A (§6). No in-loop games, no cluster flywheel spend.
3. **Gate-zero can kill for free** (§3) — the correlation check runs *before any training* and can end the
   probe at ~an hour of CPU if tempo is not a genuine axis.
4. **Depth discipline (the §4A lesson):** the positive control must be *live* at the chosen depth or the gate
   is invalid — read no null against a floored control (§4).
5. **Read at full n, single read-out point, no peeking-and-stopping** (Step-2 kill-window discipline, §5).
6. **This gate does NOT authorize a loop.** A live read records a *lead*, it does not launch a fair-from-
   scratch loop or a scale-up. The ship decision (analyzer + B1) is unchanged by either branch (§7).

**Do NOT respec anything already cleanly killed.** This is not the dense scalar leaf (CL-038), not the
structured leaf (Probe A / §3A), not the CL-034 reranker, not CL-030/031 distillation, not the CL-036 GNN.
It is a **single new input block (tempo scalars) added to the CL-037 offline sibling-regret head**, run under
the *identical* ablation harness that produced CL-037 and §3A. It reuses their dataset, their split, their
metric, their eval byte-for-byte, and adds exactly one axis of input.

---

## 1. Hypothesis (pre-registered, both directions)

**H-5A-inert** (the prior). A value head given explicit tempo/timing features also shows **no independent
regret reduction over the farm/bag-present baseline** (`Δ_indep_tempo < 1pp` at h6400, full n) → the residual
value space is **low-dimensional across three uncorrelated axes** (farm, bag, tempo). The dimensionality
claim is earned on independent evidence, not on two redundant scalars → **write "ceiling earned across three
independent axes" and ship the analyzer.**

**H-5A-live** (the crack). Tempo features produce **α>0 and independent regret reduction the farm/bag features
did not** (`Δ_indep_tempo ≥ 3pp`, matching §3A's separation standard) → there is a value direction the
heuristic treats crudely; the **"1-D residual" claim is FALSE**; this axis — *not* farm/bag — is where a
future committed fair-from-scratch loop or scale-up would have room. Record the lead; **do not launch that
loop off this gate.**

**Why tempo, specifically.** The leaf's **meeple-economy term is flat** — that is exactly what v2.8 added, a
flat term (a committed meeple counts the same whether it frees next turn or in twenty). Timing/tempo is
therefore the **named axis the heuristic handles crudely and that no value experiment has ever tested**:
CL-033/034 varied architecture and representation but not tempo; CL-037/§3A varied farm/bag; §4A varied
clairvoyance. Tempo is the one uncorrelated-by-construction direction left. The value head's best shot at
orthogonality is the **meeple-lockup × deck-clock interaction** — how much of each player's meeple stock is
dead weight locked in unfinished features, and how much deck remains to free it — which is precisely the
timing structure a flat meeple term throws away.

---

## 2. Reuse map + candidate tempo features (a spec that rebuilds any of this is wrong)

| Piece | Path | Role in §5A |
|---|---|---|
| CL-037 dataset | `/home/doctor/carc_step1_gate/dataset_both` (`child_obs.f16` + `aux.npz` + `meta.json`, gitignored) | **the exact rows** — 10,067 h6400_v2.9 sibling sets, 314,911 child rows, seed-split n_test=1544 groups. Obs/leaf_q/split/group_id **unchanged**; only the aux block gains tempo scalars. |
| Ablation trainer | [`scripts/feature_planes_gate/step1_train.py`](../scripts/feature_planes_gate/step1_train.py) (RankNet V4_listwise; `--drop-farm` / `--drop-bag`) | reuse verbatim; add a `--drop-tempo` flag mirroring the existing drops. |
| Dump / aux emitter | [`scripts/feature_planes_gate/step1_dump.py`](../scripts/feature_planes_gate/step1_dump.py) (writes farm planes into obs, bag histogram into aux) | **the one build touch** — add a tempo-scalar emitter that writes the §2 tempo block into `aux.npz` alongside the 32 bag scalars, from the *same* `flat_leaf.decompose` pass + state bag/meeple counts. Board-level scalars → side-input, exactly like bag. |
| Independence harness | [`scripts/probe_a/gate_3a_independence.py`](../scripts/probe_a/gate_3a_independence.py) (paired Δ_indep, bootstrap CI) | reuse for the §5A read-out; the statistic changes (tempo-over-both), the machinery does not. |
| Positive control | CL-037 `both` arm (α=0.05, −20.5%) — `measurement/feature_planes_gate/STEP1_GATE_RESULTS.md` | **the live baseline tempo must beat.** Reproduced as arm 2 (§4). |

**Candidate tempo features (pick cheap-from-existing-state; do NOT build new game logic).** All are board-
level scalars computable from the `flat_leaf.decompose` decomposition already dumped, plus the state's bag/
meeple counts:

| # | Feature | Source | Orthogonality risk (gate-zero will adjudicate) |
|---|---|---|---|
| 1 | `committed_meeples_self`, `committed_meeples_opp` | Σ owned meeples over components (decompose) | **low** — a count of locked meeples, not which features exist |
| 2 | `in_hand_self`, `in_hand_opp` = 7 − committed | state meeple pool | low |
| 3 | `meeple_commit_differential` = committed_self − committed_opp | (1) | low — the tempo asymmetry the flat term ignores |
| 4 | `open_component_count`, `closed_component_count`, `open_closed_ratio` | decompose finished/open flags | **medium** — overlaps farm/city structure |
| 5 | `deck_length_remaining` (scalar tempo clock) | state bag size | **HIGH — = L1 norm of the bag histogram** → R²≈1 vs bag → gate-zero will DROP it (worked example that the gate has teeth) |
| 6 | `contested_component_count` (both players own a meeple) | decompose meeple ownership | medium |
| 7 | `closure_race_differential` = Σ_contested sign(points-if-closed lead) / (open-edge distance proxy) | decompose open-edge counts | **medium** — completion order is *approximated* by open-edge distance, **not** a true completion model (staying inside "no new game logic") |
| — | ~~`turns_since_last_return`~~ | **NOT in the state** | **EXCLUDED** — non-Markov; the h6400 sibling-set roots carry board+bag+meeples, not trajectory history. Reporting it would require a history side-channel the dataset does not have. Dropped, flagged. |

The load-bearing tempo signal is expected to be **(1)+(3)+(7)** — meeple lockup and closure-race timing.
Features **5** (deck-length) and **4** (open/closed) are *expected to partly wash into bag/farm* and are
included precisely so gate-zero can show which part of "tempo" is genuinely orthogonal.

---

## 3. Gate zero — correlation check (runs FIRST; can kill the probe for free)

**Before training anything**, measure whether the tempo block is a *genuine* axis or a re-encoding of
farm/bag. This is the cheapest possible kill (~1h CPU, no training).

**Data.** The tempo block `T` (the §2 surviving features) and a **farm/bag feature block `FB`** on the same
314,911 child rows: `FB` = the 32 bag scalars **+** scalar reductions of the 3 farm-connectivity planes
(`n_farm_components`, `total_farm_tiles`, `mean_farm_city_adjacency`, `open_farm_edges` — the scalarized farm
summaries the head effectively sees), so a scalar tempo feature can be regressed against a scalar `FB`.

**Pre-registered statistics + thresholds (proceed to training only if ALL pass):**
- **Per-feature redundancy:** for each tempo feature `t_i`, `R²_i` = variance of `t_i` explained by OLS on
  `FB`. Require **mean_i R²_i < 0.50** (tempo block retains ≥half its variance orthogonal to farm/bag) **and
  max_i R²_i < 0.70** (no single tempo feature is >70% reconstructible from farm/bag).
- **Block redundancy:** the largest canonical correlation **ρ₁(T, FB) < 0.90** (no near-perfect shared
  linear direction).

**Branches:**
- **PASS** (tempo is genuinely low-correlation) → proceed to training (§4–§5). Record which features survived
  (e.g. `deck_length_remaining` is expected to be *dropped* at `R²≈1`; the surviving `T` is the real axis).
- **PARTIAL** (some tempo features redundant, some not) → **residualize**: drop features with `R²_i ≥ 0.70`,
  re-run the block statistic on the survivors; proceed only if the residualized block still clears mean-R² and
  ρ₁. Report exactly which features carried the axis.
- **FAIL** (no residualized tempo block clears the thresholds) → **report "no uncorrelated tempo axis available
  in the current state representation" and STOP.** This is a *valid gate-could-not-run outcome*: the ceiling
  claim then stands on farm/bag **plus a documented, powered search for a third axis that found none** — which
  is itself stronger than the two-scalar status quo, but is **not** "three independent axes" (§7, branch C).

---

## 4. Depth — h6400, not play-800 (the §4A lesson, made binding)

**§4A saturated its gate by matching to play-depth 800**, where even the clairvoyant baseline went inert
(α=0). CL-037's only non-inert value signal (α=0.05, −20.5%) **required the deep h6400 teacher.** A gate whose
positive control is floored cannot discriminate a null from a saturation — that is exactly why §4A is recorded
as *inconclusive*, not as a nail.

**Binding requirement.** §5A trains and reads at **h6400 teacher depth** — the depth of the CL-037 dataset's
`oracle_q`, which the dataset already carries. **Reproduce CL-037's non-inert `both` arm (α=0.05, −20.5% ±
its σ) as the live positive control FIRST.** Only once the control reproduces is a tempo null interpretable.

**Invalid-gate stop:** if the CL-037 `both` arm does **not** reproduce at h6400 (control floored/inert), the
gate is invalid — **stop and report "positive control did not reproduce," read no null.** (This should not
happen — the dataset's oracle_q is the h6400 teacher and CL-037 is byte-reproducible — but it is the
pre-registered guard so a floored control can never be mis-read as "tempo inert.")

---

## 5. Protocol, arms, and pre-registered read-out

**Reuse the §3A / CL-037 ablation harness unchanged**, four arms (mirrors CL-037's none/farm-only/bag-only/
both, extended by one axis):

| Arm | Inputs | Purpose | Expected (from CL-037) |
|---|---|---|---|
| **none** | blind 78ch | reproduce CL-037 blind control | α=0.05, **+1.9%** (≈inert) |
| **both** | farm planes + bag scalars | **the live positive control** (§4) | α=0.05, **+20.5%** |
| **tempo-only** | tempo block, no farm/bag | does tempo carry ANY signal alone (like bag-only did)? | — |
| **all-three** | farm + bag + tempo | **the binding arm** — does tempo ADD over farm+bag? | — |

**Primary statistic (the binding read):**
```
Δ_indep_tempo = regret_reduction(all-three) − regret_reduction(both)
```
i.e. the §3A "second input adds little" test, with **tempo as the second input over the farm/bag-present
baseline.** Read with the `gate_3a_independence.py` paired bootstrap (paired σ≈0.36pp at n_test=1544).

**On α (the subtlety, pre-registered so it can't be mis-read):** the `all-three` arm inherits **α>0 from
farm/bag** — its α is non-zero *by inheritance*, so **α on `all-three` is NOT the discriminator.** The
discriminator is the **incremental regret reduction `Δ_indep_tempo`**, exactly as in §3A. The **`tempo-only`
arm's** α (does tempo *alone* flip inertness the way bag-only did, α:0→0.05) is the **secondary corroborating
read** — and because gate-zero has already established tempo ⊥ farm/bag, a non-trivial `tempo-only` gain is
attributable to tempo, not to farm/bag leaking through.

**Pre-registered thresholds (match §3A's separation standard; single read at full n):**

| Read | Condition | Call |
|---|---|---|
| **Ceiling-earned (kill)** | `Δ_indep_tempo < 1pp` (redundant; precedent: CL-037 +0.8pp, §3A +0.05pp) | H-5A-inert → **ship, write "three independent axes"** |
| **Crack-found (live)** | `Δ_indep_tempo ≥ 3pp` (~8σ at σ≈0.36pp) **AND** `tempo-only` shows α>0 with a non-trivial standalone gain | H-5A-live → **record the lead, do not launch a loop** |
| **Weak lead (gray band)** | `1pp ≤ Δ_indep_tempo < 3pp` | tempo is a *small-but-real* third axis; **the strong "three independent axes" claim is NOT earned**; autopsy records a bounded tempo residual; no loop; no downgrade of the ship decision |

**Read discipline:** full n (n_test=1544), **single read-out point**, no peeking-and-stopping (Step-2
kill-window). Bootstrap CI reported alongside the point estimate; if the CI straddles the 3pp boundary,
the result is the **gray-band "weak lead"** call, not a coin-flip to either side.

---

## 6. Boxing / time-box (~1 day, gate not program)

| Stage | Budget | Notes |
|---|---|---|
| Gate-zero correlation check | ~1–2h | **runs first; free kill** (§3). No training. |
| Tempo-scalar emitter + aux dump | ~2h | one touch to `step1_dump.py`; reuses the decompose pass |
| 4-arm train + read-out | ~0.5 day | reuse `step1_train.py`; local box, `nice -19` |

**No in-loop games. No cluster flywheel spend. No new champion, no PRODUCTION.yaml touch.** Same-order cost as
§3A/§4A. Two clean early-exits (both leave the farm/bag ceiling claim standing as-is): **gate-zero FAIL** (no
uncorrelated tempo axis) or **positive-control-won't-reproduce** (invalid gate). Neither reads a null.

---

## 7. Decision memo — exactly what the autopsy's ceiling sentence says, per branch

The ship decision — **analyzer (endgame-2) + B1** — is **the same under every branch.** §5A changes only the
sentence the autopsy is *entitled to write* about dimensionality (and, correspondingly, CL-039's language).

- **Branch A — inert (ceiling earned).** Autopsy writes: *"The residual value beyond the v2.9 leaf is
  low-dimensional and heuristic-inert across **three uncorrelated axes** — farm-connectivity, bag/deck-
  composition, and tempo/timing (`Δ_indep_tempo` = X pp < 1pp at h6400, full n). The learned-value route is
  exhausted not on two redundant scalars but on three independent ones; the dimensionality claim is earned."*
  → CL-039 **strengthened**. Ship the analyzer.

- **Branch B — live (crack found).** Autopsy writes: *"The 1-D-residual claim is **false**: a value head given
  explicit tempo/timing features recovers **independent** regret reduction (`Δ_indep_tempo` = X pp ≥ 3pp, α>0)
  that farm/bag could not — a value direction the v2.9 heuristic (whose meeple-economy term is flat by
  construction) treats crudely. The learned-value route is exhausted **along farm/bag/clairvoyance/fair, but
  NOT along tempo**; a future fair-from-scratch loop or scale-up would target tempo, not farm/bag."* → CL-039's
  "genuinely low-dimensional" is **downgraded** to "low-dimensional along the tested axes except tempo"; a
  BACKLOG lead (tempo-targeted loop) is recorded. **Ship the analyzer anyway** — this gate does not authorize
  the loop; it only forbids the overclaim.

- **Branch C — gate could not run** (gate-zero FAIL or control won't reproduce). Autopsy writes: *"A powered
  search for a third value axis uncorrelated with farm/bag found **no uncorrelated tempo axis in the current
  state representation** (tempo features ≥X% reconstructible from farm/bag / positive control did not
  reproduce at h6400). The dimensionality claim therefore stands on farm/bag **plus a documented failed search
  for independence** — it is **NOT** upgraded to 'three independent axes.'"* → CL-039 unchanged; the honest
  limitation is logged. Ship the analyzer.

- **Branch D — weak lead** (`1 ≤ Δ_indep_tempo < 3pp`). Autopsy writes: *"Tempo carries a small, real
  independent residual (`Δ_indep_tempo` = X pp, CI […]) — below the 3pp separation bar, so the strong 'three
  independent axes' claim is **not** earned, but the residual is **not** 1-D either. A bounded tempo residual
  is recorded; no loop is authorized."* → CL-039 nuanced (neither strengthened nor downgraded). Ship the
  analyzer.

**In all four branches: analyzer + B1, no champion change, no cluster spend.** The gate buys *epistemic
license for one sentence*, not a change of course.

---

## 8. Conflict flags vs existing gates

1. **vs §4A (depth) — DELIBERATE CORRECTION, not a conflict.** §4A ran at play-800 and saturated (control
   floored → inconclusive). §5A runs at **h6400** where the control (CL-037 `both`) is *live*. §5A is the
   depth-correct sibling of §4A. **Guard:** §4 stops the gate if the control won't reproduce — the exact
   failure §4A hit is now a pre-registered invalid-gate stop, not a mis-read null.
2. **vs §3A (structure) — DIRECT EXTENSION, composes.** §3A tested farm-vs-bag independence on the same
   h6400 sibling sets at n_test=1544 with `Δ_indep ≥ 3pp`. §5A adds a **third** axis under the identical
   harness/metric/split. Same bar, same σ, same dataset — the results are directly comparable and stack.
3. **vs CL-039 (the close) — the one real tension, and it is intended.** CL-039 already shipped "value signal
   genuinely low-dimensional." §5A is the falsifier of the *dimensionality* half of that claim. **Flag: the
   autopsy's dimensionality sentence should not be finalized until §5A reads out** (§7 gives the four exact
   wordings). The *ship* half of CL-039 (analyzer + B1) is **not** in tension — it holds under every branch.
   So §5A is a scoped reopening of one clause of CL-039, not a reopening of the close.
4. **vs the boxing envelope — consistent.** Gate not program, ~1 day, no in-loop games, no flywheel spend,
   no champion/PRODUCTION.yaml touch — same discipline as §3A/§4A.
5. **No conflict with any cleanly-killed lever** (CL-030/031/033/034/036/038, Probe A). §5A is a single new
   *input axis* on the CL-037 offline head, not a re-run of any killed *object* or *loop*.

---

MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED. Spec pre-registers; no runs authorized.
