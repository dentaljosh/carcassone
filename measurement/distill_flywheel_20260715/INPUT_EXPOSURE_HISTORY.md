# Input-exposure track record — does giving this net more inputs ever help?

**STATUS: HISTORICAL AUDIT (read-only). No code changed, running job untouched. No promotion, no PRODUCTION.yaml change.**
**Date:** 2026-07-16 · **Scope:** every input/feature/representation experiment in project history + its verdict.
**Occasion:** the fair-champion distillation flywheel's non-sighted (78ch/10) vs SIGHTED (81ch/42) A/B.

---

## 0. HEADLINE

**Yes — history predicts our sighted-policy null, and it predicts it specifically.**

"Adding public inputs doesn't move this net" is an established, evidenced pattern here. The sharpest
statement of it is **CL-050's bag-blind control**: a bag-BLIND net recovered **~95%** of the offline gain of
the bag-sighted net (+0.0382 vs +0.0403) ⇒ *"deck-awareness contributed ~5% of the offline signal; the net
learned a general leaf-correction, NOT deck marginalization"* (`governance/CLAIM_REGISTRY.csv:51`). That is
our redundancy hypothesis — **the board already implies the bag** — already measured, with a control, and
already the stated reason a sighted run failed.

Three qualifiers keep this honest:

1. **Our deltas are at/below our own noise floor.** `PRIOR_TOP1_CALIBRATION.md` states: *"n_aux_rows = 3356
   over 24 frozen probe games — rows are correlated within game, so treat sub-~3pp deltas as within noise."*
   iter-0 (0.554 vs 0.561) = **0.7pp = within noise**. iter-1 (0.559 vs 0.592) = **3.3pp = borderline**.
   The defensible read is **"no detectable gain,"** not "sighted is behind." The flatter slope is the
   more interesting signal, and it is not yet powered.
2. **We are the FIRST to test sighted on POLICY.** All prior sighted/bag work targeted the **VALUE** head.
   Our null *extends* the pattern to a genuinely new cell; it was not foreclosed.
3. **The one positive (CL-037) is offline-only and F4-contaminated** — see §3.

**Stated mechanism (project's own words, three converging forms):**
- *Redundancy:* farm and bag are **substitutes, not additive** — CL-037's own ablation.
- *No teacher-aligned signal:* bag-aware features *"vary a LOT (55–62% of positions) but carry ~zero
  teacher-aligned signal (τ +0.01)"* — the midgame reference probe, **a variance trap**.
- *Not information-limited:* the value head is *"NOT bottlenecked by farm-representation blindness"* — the
  C4a oracle probe, where even an **oracle** ownership input made the net **worse**.

**The uncomfortable structural fact (§4):** this project has **never once measured an input addition that
fired in games.** The input changes people cite as wins were adopted at design time and *never A/B'd*.

---

## 1. Every input/feature/representation experiment

| # | Date | Experiment | Input exposed | Verdict | Evidence |
|---|---|---|---|---|---|
| 1 | 2026-04-28 | Board encoding birth | 40ch / 10 scalars, W=25 | *(baseline)* | `d1e80fd`; `board_repr.py` |
| 2 | 2026-04-28 | **"Encoding richness"** (Phase-3 prereq) | **40→78ch**: per-side/per-corner meeple (4→18ch), +12 internal-topology pair channels, scalar normalization | **NEVER MEASURED** — adopted on rationale; old ckpts *"incompatible with the new network input shape"* so no A/B was run | `0fee04d`; DECISIONS.md:2228–2260 |
| 3 | 2026-05-29 | D13 scalar-semantics fix | `tiles_remaining`/`progress` no longer overcount deck by 1 | **BUG FIX** (not new info) | `6ac64f1` |
| 4 | 2026-05-29 | **Path B Step E — farm-control scalars** | +2 scalars (`contested_field_count`, `farm_control_balance`) | **BUILT, NEVER ADOPTED** — `include_farm_scalars` default **OFF**; still OFF today, even inside sighted (42 = 10+32 ⇒ farm scalars off) | `a79419f`; `features.py:48–67`; DECISIONS.md:493 |
| 5 | 2026-06-02 | `DECK_NORM` 85→72 | renormalization after River dropped | housekeeping | `36d9cca` |
| 6 | 2026-06-04 | **C4a oracle-representation probe** | **oracle** terminal ownership planes (upper bound on farm sight) | **REFUTED** — BLIND corr **0.469** vs +OWN **0.447** (tied/worse) ⇒ *"NOT bottlenecked by farm-representation blindness"*; killed a ~1.5-day build in ~30 min | DECISIONS.md:82; `scripts/probe_value_head_c4.py` (`c26e468`) |
| 7 | 2026-06-04 | C6 de-saturated target | *(target, not input)* | **REFUTED** — t15 corr 0.733 vs t40 0.690 on \|m\|>33 | DECISIONS.md:82; `1c862ce` |
| 8 | 2026-06-17 | Cython encoder port | none — **bit-exact** | perf only | `1b55721` |
| 9 | 2026-06-18 | **CL-021** value-ranking kill-test | incl. arm D (+OWN) | **Supported (inert)** — τ: conv+MSE −0.004, attn+rank +0.012 vs **leaf 0.579**; prod net 0.081 ⇒ *"scale is not the unlock"* | `CLAIM_REGISTRY.csv:22` |
| 10 | 2026-06-21 | **Midgame reference probe** | bag-aware + structural features from `decompose` | **KILL** — features *"vary a LOT (55–62%)"* but carry **τ +0.01** teacher-aligned signal; recover only **~2–6%** of disagreements ⇒ **"a variance trap"** | DECISIONS.md:38; `measurement/midgame_reference/` |
| 11 | 2026-06-28 | **CL-033** value-resurrection | blind 78ch | **Supported (inert)** — all 3 variants **best α=0**; net-alone τ 0.105 vs **leaf 0.895** | `CLAIM_REGISTRY.csv:34` |
| 12 | 2026-06-28 | **CL-034** feature-graph comparator | **50 handcrafted scalars** (the rep axis never varied before) | **OFFLINE FIRES, WASHES OUT** — regret **−41%** offline, but **no** search integration beats `search_leaf`; search collapses regret 0.122→0.019 on its own | `CLAIM_REGISTRY.csv:35` |
| 13 | 2026-06-28 | **CL-036** typed feature-GNN | full typed object graph (8 node/8 edge types) | **INERT** — worse than flat scalars *and* the heuristic | `CLAIM_REGISTRY.csv:37` |
| 14 | **2026-06-29** | **CL-037 — REPRESENTATION GATE (the one PASS)** | **+3 farm planes / +32 bag histogram** | **GATE-A PASS (offline only)** — α 0→**0.05**, regret **−20.5%** vs blind −1.9%; neg-control collapses it | `CLAIM_REGISTRY.csv:38`; `measurement/feature_planes_gate/STEP1_GATE_RESULTS.md`; `be1fb7e` |
| 15 | 2026-06-30 | **CL-038** Step-2 PeNS (sighted 89-scalar) | sighted scalars → value **drives** leaf | **GATE-B FAIL** — craters vs RoD2 iter02: MSE 0.525→0.212, ranking 0.453→0.287, frozen 0.355→0.215 | `CLAIM_REGISTRY.csv:39`; results.csv `step2_nail2_*` (armC additive **−159.8**, convex **−246.3**) |
| 16 | 2026-07-01 | **Probe-A §3A** structured value leaf | per-component structured object | **KILLED at the farm/bag INDEPENDENCE gate** — **Δ_indep = +0.05pp** (σ 0.36, CI [−0.61,+0.78], ~8σ below the +3pp bar); *"farm carries it, bag inert"* | DECISIONS.md:27; `315122d`/`b48694a` |
| 17 | 2026-07-01 | Probe-B §4A fair-info | fair vs clair targets | **ALL SIX ARMS INERT** (best_α=0, +0.0%); n=150 "non-inert" preview was a small-sample artifact | DECISIONS.md:27 |
| 18 | **2026-07-03** | **M2 KILL** — canonical AZ, the never-run cell | **sighted 81ch + 32 bag + pooled value + score_diff_wide + nn-leaf** | **KILL, both pre-registered reads** — solver τ **0.018→0.023 FLAT** vs **leaf 0.615** (~27× below); **0/6** rs cells ≥2σ | DECISIONS.md:21; `CLAIM_REGISTRY.csv:43`; results.csv `m2_solver_score_k2_it00_04_n1119` |
| 19 | 2026-07-04 | §5A / CL-040 tempo arm | tempo axis | **REAL-BUT-DOMINATED** — solver-τ 0.145 (~7× M2's 0.02) but sign-z **−9.2** vs leaf | DECISIONS.md:20 |
| 20 | 2026-07-05 | v2.10 `bag_close` leaf | bag → **heuristic** (not net) | **TIE** — **−6.1 / z0.40** (n=400 paired) | DECISIONS.md:19; results.csv `v210_bagclose_vs_cap8_h800_n400` |
| 21 | **2026-07-10** | **C-cheap v1 (CL-049)** | sighted 81ch bag-aware value **replaces** leaf | **CATASTROPHE — W0/L100** | `CLAIM_REGISTRY.csv:50`; results.csv `fair_net_cheap_vs_h800_k2` (**elo −800.0, avg_diff −58.27**) |
| 22 | **2026-07-10** | **C-cheap v2 (CL-050)** | bag-aware **residual** value | **NULL — +9.2 elo** (gate ≥+35), Δz +0.18 | `CLAIM_REGISTRY.csv:51`; results.csv `fairnet_v2_n200_vs_h800_k2` |
| 23 | 2026-07-16 | **THIS RUN** — sighted distill A/B | sighted 81ch/42 → **POLICY** | **NO DETECTABLE GAIN** (first POLICY test) | `probe_metrics.jsonl`; §5 |

Also relevant: **ownership planes are an OUTPUT aux target, never an input** (`network.py:121–126`,
`aux_targets.py:193–205`). This is exactly why Step E chose *scalars not planes* — *"an ownership plane
would duplicate the Step-3 ownership aux target (feeding the answer we want learned)"* (`a79419f`).

---

## 2. The bag/sighted lineage — verification of the four claims

### Origin
`src/carcassonne_ai/sighted_planes.py:1–29` states the thesis verbatim:

> The CL-033 "value resurrection" pilot found that a learned value/ranker on the 78-channel board
> representation CANNOT out-rank the v2.9 heuristic leaf at sibling ordering (best alpha=0, net-alone
> Kendall-tau ~0.105 vs leaf ~0.895). **Hypothesis: the value head is inert because the representation is
> BLIND to (a) farm connectivity ... and (b) the bag (what tiles remain).**

Provenance note: `sighted`/`bag_histogram` first appear in **`be1fb7e` (2026-06-29)** under
`scripts/feature_planes_gate/`, reaching `src/` only at **`86f9695` (2026-07-03)**. `git log --follow` on
`sighted_planes.py` shows just 2 commits and **understates the history by one step**.

### Claim-by-claim audit

| Your claim | Verdict | Evidence |
|---|---|---|
| **CL-033 framed "is the net inert because it's bag-blind?"** | ⚠️ **CORRECTION — attribution is off by one.** CL-033 *poses the puzzle* (best α=0, τ 0.105 vs 0.895) but contains **no bag hypothesis**. The bag-blind hypothesis was authored **in response to** CL-033 — in `sighted_planes.py`'s docstring — and **tested by CL-037**, which **answered YES, offline** (flipped α=0→0.05). So: CL-033 = the puzzle; **CL-037 = the hypothesis + its (offline) confirmation.** | `CLAIM_REGISTRY.csv:34` (CL-033 text); `sighted_planes.py:1–29`; `CLAIM_REGISTRY.csv:38` (CL-037) |
| **M2 sighted got a KILL** | ✅ **VERIFIED.** 2026-07-03, both pre-registered reads. Solver-scored (non-circular, exact K≤2, 1,119 roots): nets **τ 0.018→0.023 flat across iters 00–04**, leaf **τ 0.615** (~27× below), top1 ~0.08 vs 0.610, paired sign-z **−17…−18**. Conversion: **0/6 rs cells ≥2σ**, non-monotone, harm at weight. Upgraded CL-039 "premature" → **EARNED, SCOPED closure**. Scope guard: *"at-this-scale (7M net, ≤5 iters, sims≤200)."* | DECISIONS.md:21; `CLAIM_REGISTRY.csv:43`; `measurement/canonical_az/solver_score_m2_final_it00_04.json` |
| **C-cheap v1 was W0/L100** | ✅ **VERIFIED, exactly.** CL-049, 2026-07-10, **Refuted/high**. results.csv `fair_net_cheap_vs_h800_k2`: **W0 / L100 / elo −800.0 / avg_diff −58.27**. *Not a bug* — sign/POV/encoding ruled out (net corr **+0.503** with labels). | `CLAIM_REGISTRY.csv:50`; results.csv |
| **C-cheap v2 was NULL** | ✅ **VERIFIED.** CL-050, 2026-07-10. Offline gate **PASSED** (val_mse A 0.160 vs null 0.215, ~25% better) → online **+9.2 elo** vs a **≥+35** gate, CRN paired **z=+0.18**. | `CLAIM_REGISTRY.csv:51`; `classical_search/fairnet_v2_n200/crn_delta.json` |
| **"the sighted value head has been falsified 8×"** | ⚠️ **OVERCOUNT / CONFLATION.** The "8" is **CL-050's own self-numbering** — *"value-inertness confirmation **#8**"* — within the **broad value-inertness ledger (CL-021, CL-029…CL-040+)**, **most of which used the BLIND 78ch rep or plain scalars** (CL-021, CL-029, CL-032, CL-033, CL-034, CL-036 are *not* sighted). The **sighted-specific** subset is **~4–6**: CL-038 (PeNS 89-scalar sighted), Probe-A §3A, M2/CL-042, CL-049, CL-050 (+ the C4a oracle probe as a precursor). The phrase originates in **our own `SIGHTED_SCOPE.md`**, which compresses the ledger's count onto the sighted rep. **Correct statement:** *"value inertness has been confirmed ~8× across all representations; the sighted rep specifically has failed ~4–6 game/solver-gated tests and passed exactly 1 offline gate (CL-037)."* | `CLAIM_REGISTRY.csv:51`; `CLAIM_REGISTRY.csv:22,30,34,35,37`; `SIGHTED_SCOPE.md` §0 |

### Ones you were missing
- **C4a oracle probe (2026-06-04)** — the *earliest* falsification, and the strongest form: an **oracle**
  ownership input made the net **worse** (0.469→0.447). Predates sighted by a month.
- **Midgame reference probe (2026-06-21)** — bag-aware features carry **τ +0.01**. Direct.
- **v2.10 `bag_close` (2026-07-05)** — bag exposed to the **heuristic** instead of the net: also a **TIE**
  (−6.1/z0.40). So the bag is inert **even outside the net**.
- **CL-021 arm D (+OWN)** — ownership arm, 2026-06-18.

### Stated failure reasoning, each time
- **CL-049 (W0/L100):** *"the net value is a smooth GLOBAL predictor with NEAR-ZERO LOCAL discrimination
  between sibling afterstates (sibling std ~0.005–0.03 vs the heuristic leaf's ~0.04)"* + pooled-Q selection
  requires a sharp local ranker ⇒ *"pooled-Q picks ~randomly → loses every game."* Crucially:
  **"deck-awareness never got tested because the base local ranking fails first."**
- **CL-050 (null):** *"the offline↔online DISCONNECT at pooled-Q deploy knobs is the finding"* + the A≈B
  control: *"the net learned a generic leaf-correction, not deck marginalization."*
- **M2 (kill):** heads *"NOT dead-forward"* (v_nn↔score-diff corr 0.50→0.65, **rising**) — position **level**
  learned, **between-sibling discrimination ZERO**.
- **Probe-A §3A:** *"the value signal beyond the leaf is genuinely LOW-DIMENSIONAL; the scalar was NOT the
  bottleneck."*
- **C4a:** *"the value head is NOT bottlenecked by farm-representation blindness."*

---

## 3. Counterexamples — what actually helped, and why they're weaker than they look

**The honest answer: there is no measured in-game input win in this project's history.**

| Candidate | Reality |
|---|---|
| **40→78ch per-side meeple fix** (`0fee04d`) — *"Pre-fix all meeple positions on a tile collapsed to a single cell-level flag, hiding which feature was actually claimed"* (`board_repr.py:47–50`) | **Never A/B'd.** Adopted at design time on rationale. DECISIONS.md:2260: old checkpoints were *"incompatible with the new network input shape... They have to be regenerated"* ⇒ no comparison was possible or run. **Compelling rationale ≠ evidence.** |
| **`farm_control_scalars`** (`a79419f`) — *"STRUCTURAL facts the conv can't derive from the raw farmer-meeple channels"* | **Built, never adopted.** Default OFF since birth; still OFF. Even the sighted rep runs with farm scalars **OFF** (42 = 10+32). No verdict exists. |
| **Ownership planes** | **Not an input** — a training-only aux **target** (`network.py:121–126`). As an *input* (C4a) it was **refuted** even in oracle form. |
| **CL-037** — the one genuine PASS | Real, and neg-control-clean (`both_shuffled` collapses it: τ→0.139, α→0). **But:** (a) **offline ranking only**; (b) **F4-contaminated** — see below; (c) **τ 0.207 ≪ leaf 0.895**, α only 0.05, *"a weak-but-nonzero sighted-residual ranker, NOT a value head that rivals the leaf"*; (d) its own ablation shows farm/bag **redundant**. **Every game-gated test of the rep it validated (CL-038, M2, CL-049, CL-050) subsequently failed.** |
| **CL-034** — 50 scalars, offline **−41%** | The biggest offline rep win ever recorded here — **washed out under search entirely.** Its own lesson: *"a learned component must beat what SEARCH extracts, not what the STATIC leaf misses."* |

**The F4 contamination (`docs/AZ_VALUE_ROUTE_AUTOPSY_2026-07-01.md` §2)** — the h6400 teacher-Q
**correlates 0.995 with the static v2.9 leaf**, so every h6400-scored offline gate measured *"can the value
beat the leaf at predicting the leaf's own search"* — a metric where *"the leaf is definitionally
near-optimal."* This retro-contaminates **CL-032/033/034/036, Probe-A §3A, §5A** — **and CL-037**, which was
h6400-scored. The correction: score against the **exact K≤4 solver**. When CL-037's rep was re-scored that
way (**M2**), it gave **τ 0.018 vs leaf 0.615**.

### What distinguishes the changes that "worked"
1. **They were never contested by a measurement.** The 78ch expansion and farm scalars were *design
   decisions*, adopted before any gate existed.
2. **The ones that fired offline, fired against a circular target** (h6400 ≈ leaf, corr 0.995) — and every
   one died on a non-circular or in-game gate.
3. **The genuine pattern:** inputs help a *weak standalone predictor* and stop helping once **search** or a
   **strong leaf** supplies the same signal. CL-034 is the cleanest statement: search alone collapses
   decisive regret 0.122→0.019, leaving the comparator (0.075) **behind**.

---

## 4. Reading our result against this history

**Our numbers vs the pattern:**

| Stage | Non-sighted | Sighted | Δ | Read |
|---|---|---|---|---|
| warmstart (−1) | 0.322 | **0.364** | **+4.2pp** | **sighted WINS** — above the ~3pp floor |
| iter 0 | **0.561** | 0.554 | −0.7pp | **within noise** |
| iter 1 | **0.592** | 0.559 | −3.3pp | **borderline**, flatter slope |

This is **CL-037 → M2 in miniature, on the policy head.** The sighted rep helps exactly where every prior
sighted experiment helped — **the untrained/standalone predictor** (warmstart top1 +4.2pp; value_r 0.468 vs
0.281, a big gap) — and the advantage **evaporates the moment the champion's teacher signal arrives**. That
is the project's mechanism, stated by CL-034 and confirmed by M2: *the net only appears to need the extra
input while it has nothing better; once search/the leaf/the teacher supplies the signal, the input is
redundant.*

**Does history predict the null? Yes — and the redundancy hypothesis is already measured:**
- **CL-050's A≈B control** is our hypothesis with a control group: bag-blind recovered **~95%** of the gain.
- **CL-037's own ablation:** farm-only −17.1%, bag-only −19.7%, both −20.5% ⇒ *"LARGELY REDUNDANT
  (substitutes, not additive)."* Two "independent" signals that don't add ⇒ both are proxies for something
  the board already carries.
- **Probe-A §3A:** **Δ_indep = +0.05pp**, ~8σ below the bar.
- **Midgame probe:** bag-aware features carry **τ +0.01** teacher-aligned signal.

**Where we go beyond history (be precise about our contribution):**
- **First POLICY test.** Every ledger entry is VALUE. Our null is **new evidence**, not a repeat.
- **First test where the value loop is severed** (frozen champion leaf = the only value) — so the
  CL-049 pooled-Q collapse mechanism **cannot** apply here. The null has to come from redundancy, which is
  precisely why it's the cleaner test of the bag hypothesis.
- **We should not claim "sighted is behind."** 0.7pp and 3.3pp against a self-declared ~3pp floor is
  **"no detectable gain."** Claiming a *regression* would repeat the noise-spike error the project has
  logged twice (the c=3 "+47 elo"; the deepteacher "+53.7"). The **flatter slope** is the honest thing to
  watch, and it wants either more iters or more probe rows before it means anything.

**Bottom line:** history does **not** contradict our result — it **anticipates** it, names the mechanism
(redundancy / the board already carries it), and supplies the control (CL-050 A≈B). The correct framing of
our finding is: *"the sighted rep's null now extends from the value head to the policy head, on the one cell
where the value-collapse mechanism was structurally excluded — consistent with a 9-experiment ledger, and
with CL-037's offline pass remaining the lone (h6400-contaminated) positive."*

---

## 5. Sources

`governance/CLAIM_REGISTRY.csv` rows 22 (CL-021), 30 (CL-029), 34 (CL-033), 35 (CL-034), 37 (CL-036),
38 (CL-037), 39 (CL-038), 43 (CL-042), 50 (CL-049), 51 (CL-050) ·
`DECISIONS.md` lines 15, 19, 20, 21, 23, 27, 28, 38, 82, 493, 2228–2260 ·
`docs/AZ_VALUE_ROUTE_AUTOPSY_2026-07-01.md` §2 (F4) ·
`measurement/feature_planes_gate/STEP1_GATE_RESULTS.md` · `measurement/canonical_az/M2_PLAN.md` +
`solver_score_m2_final_it00_04.json` · `measurement/midgame_reference/MIDGAME_REFERENCE_REPORT.md` ·
`measurement/distill_flywheel_20260715/{SIGHTED_SCOPE.md,PRIOR_TOP1_CALIBRATION.md}` ·
`experiments/results.csv`: `fair_net_cheap_vs_h800_k2`, `fairnet_v2_n200_vs_h800_k2`, `fairnet_v2_lam*`,
`m2_solver_score_k2_it00_04_n1119`, `m2_rs_sweep_*`, `step2_nail2_*`, `v210_bagclose_vs_cap8_h800_n400` ·
code: `src/carcassonne_ai/{sighted_planes.py:1–29,board_repr.py:47–50,features.py:48–67,game_wrapper.py:295–308,network.py:121–126}` ·
commits `d1e80fd` `0fee04d` `a79419f` `6ac64f1` `be1fb7e` `86f9695` `c26e468` `1c862ce`.
