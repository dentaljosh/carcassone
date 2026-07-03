# AZ-value route — autopsy (✅ FINAL — M1 KILL · M3 FIRE-then-bounded · **M2 KILL, earned closure**)

**Status:** ✅ **FINAL (2026-07-03).** All three reopeners have read out: **M1 KILLED** (band noise), **M3 FIRED
then bounded** (Gate-B refuted as a *law*; FPU recovers to parity, not exceeding — the FPU axis is closed), and
**M2 KILLED on both pre-registered reads** (solver-τ 0.02 vs the leaf's 0.615, flat across training; rs-sweep
conversion null). **CL-039 upgrades from "premature closure" to an EARNED, SCOPED closure** (CL-042): even the
canonical-AZ cell — sighted rep × pooled head × non-degenerate target × FPU-installed × value-driven leaf — cannot
rank siblings against the exact solver or convert to game strength at this scale. §7 below is the final clause.
· **Created:** 2026-07-01 · **Updated:** 2026-07-03 (M2 read-out FINAL; verdict executed autonomously per the
pre-registered protocol, Joshua's standing authorization)

> **The one-sentence verdict-scope correction (the review's headline):** CL-039's "the AZ-value route is exhausted
> (scalar / structured / clairvoyant / fair)" is **premature as a route closure; accurate only as "this recipe
> family, at this scale, is exhausted."** This autopsy states what is earned, scoped honestly, and holds the strong
> form pending M1–M3.

---

## 0. What this autopsy covers

The **learned-value route to superhuman strength**: can a *learned* value/policy component **EXCEED the hand-crafted
v2.7/v2.9 leaf inside MCTS** (not merely rank positions, but *drive search* to stronger play)? The ledger
(CL-021, CL-029…CL-040) accumulated to "the AZ-value route is exhausted." The fresh-look review (F1–F10) accepts the
experiment-level rigor as above field norm but flags **verdict scope + selection discipline at the program level**:
the accumulated "value is inert" reads are **correlated on structural weaknesses** — a circular scoring oracle (F4),
degenerate training targets (F2/F10), a pooling-off value head (F10), and the blind-era representation. This autopsy
separates **what is earned** from **what those weaknesses leave open**.

## 1. What is SOLID (earned regardless of M1–M3)

- **The strongest agent in the ecosystem is classical, not neural.** Deep HeuristicMCTS on the v2.9 leaf
  (`Bmild_cap8`, h6400–h12800) + exact-solver endgame handoff beats the sims=200 neural champion; RoD1 loses to
  h6400; v2.9.1 beats v2.8-prod (+55 elo). → the ship decision (S1) stands on its own numbers.
- **Root/offline metrics do NOT predict game strength** (independently confirmed 4× — CL-031/032/034/035 + the
  hard-policy/high-gap null). Gate on GAMES, not offline ranking, for any in-loop candidate.
- **Policy distillation is a dead end for RoD strength** (CL-030/031): search extracts the decision move from the
  existing prior; improving the prior is redundant at depth.
- **Net POLICY gains wash out at deep search** (the deepteacher washout: +82.8/z3.48 @ sims200 → +8/z0.34 @
  sims800). Policy is not the binding learned component; value/search is.

## 2. The F4 contamination (why the OFFLINE ledger is suspect — the through-line correction)

The **h6400 teacher-Q correlates 0.995 with the static v2.9 leaf** (stated in the CL-033 value-resurrection row). So
every offline value/ranking gate scored against h6400 was measuring "can the value beat the leaf at predicting the
leaf's own search" — a metric in which the leaf is **definitionally near-optimal**. This retro-contaminates the
*offline* reads of **CL-032/033/034/036, Probe-A §3A, and §5A** to the degree h6400 ≈ leaf. It does **not** touch
game-gated verdicts. **Correction, forward:** all offline value/ranking gates score against the **exact K≤4
solver** (the only non-circular ground truth), or game outcomes on fresh bands — never h6400.

- **§5A (CL-040) concretely re-read:** its "live offline lead" (`tempo_only` +44.7%) was itself h6400-scored →
  circular-frame/unresolved. Only **gate-zero** (the tempo-vs-farm/bag residualization) survives as non-circular.
  The valid question — does an axis uncorrelated with farm/bag add signal against a *non-circular* target — is
  absorbed into **M2** (solver-scored). §3A's "value space is ~1-D" reading is likewise h6400-scored → also folds
  into M2's adjudication.

## 3. Gate-B — valid NARROWLY, not as a law (M3 tests the boundary)

The Step-2 weaned-value-leaf flywheel (CL-038) gave a genuine Gate-B: the learned value **ranks** (Gate-A: α>0,
τ≈0.43 at every depth) but **craters play when driven** (additive 0.500→0.285, frozen 0.215). The **3 nails**
(interior-τ flat → not distribution mismatch; additive craters → not heuristic subtraction; frozen craters → not
retraining drift) are real and rule out those three mechanisms. **But** all three are blind to the **calibration /
optimistic-tail** mechanism (interior-τ is rank-based; additive+frozen are consistent with MCTS's max-operator
hunting the value's error tail). So Gate-B is valid for **this substrate, blend 0.27, these knobs** — it is **NOT**
established as "the learned-value-leaf lever is closed" until **M3** tests LCB/ensemble-pessimism, isotonic
calibration, and a c_puct/FPU re-sweep. (Standard fixes, never tried — F10.)

## 4. Fairly-killed levers — NOT reopened (the review concurs — §6)

Clairvoyance as a play-strength inflator (F1); deck-aware closure for full-game strength (F8); farm-majority gating;
opp-cap denial; symmetry augmentation; the ML compute scheduler (CL-035); the typed-GNN head (CL-036); deeper exact
endgame as a *winrate* lever (F9, margin-positive/winrate-neutral); "root/offline metrics predict game strength"
(killed 4×). Touching any of these is out of scope.

## 5. The ship decision (independent of the reopeners)

Ship the best **agent**, learned-or-not: **deep-classical (v2.9, h6400–h12800) + exact-endgame handoff** (S1), a
**non-circular bot anchor** (S2), and the **analyzer (endgame-2)** — the original Phase-5 win condition — served by
the proven *sighted* value head. The "learned component must exceed the heuristic" framing is self-imposed, not in
the goal statement. Human-in-the-loop is deferred.

## 6. What actually failed vs what was never tried (the F2/F10 gap M2 closes)

Every game-gated lineage net trained on either the **saturated** `tanh(margin/15)` outcome or the
**near-zero-variance residual** (~0.5% of the Q signal), with `value_global_pool=False` in **every** checkpoint
(KataGo-style pooling built 2026-06-05, never enabled), on the **blind** representation, sims 100–200, no Gumbel. The
cell {sighted inputs × pooled value head × non-degenerate target (`score_diff_wide`/`wl`) × sound low-sim
improvement} — the closest thing to actually running AlphaZero here — **has never been sampled.** A head trained on a
saturated/0.5%-variance target *cannot* develop cross-subtree discrimination regardless of capacity → the observed
flat corr/τ may be **target-caused, not capability**. **M2** samples this cell, **solver-scored**, and adjudicates
against §3A's competing "the residual value space is genuinely small (the leaf is a decomposable additive
evaluator)" reading. Expect a real chance M2 returns a **kill** — this test adjudicates, it does not resurrect.

### 6.1 Provenance of the five departures — deliberate vs inherited (2026-07-03 doc audit)

The five non-canonical choices M2 reverses were **not uniformly deliberate** — and the split is itself the case for
M2. Each was judged with the *other four held at their weak defaults* (correlated one-shot rejections on a blind /
pooling-off / saturated / h6400-circular substrate), so none was ever tested in the configuration where it could pay
off.

| # | departure (what we did) | verdict | evidence |
|---|---|---|---|
| 1 | hand-crafted v2.7 leaf as the MCTS evaluator | **deliberate + strong evidence** | Phase-4 breakthrough (+21pp over warmstart); NN-value alternatives were re-tried and *lost* — Option 2 (NN value blend) closed as a confirmed negative 2026-05-18; the pure-NN-value leaf **cratered −800 elo** 2026-05-31. `DECISIONS.md:595`, `CLAUDE.md:102` |
| 2 | `value_global_pool=False` (every ckpt) | **examined once, abandoned** | "Flywheel Step 2" tested a single time (2026-06-05) → "moved NOTHING, same curve" → pivot to attacking the value *loss*. But that test was on the blind rep + saturated target; never re-tried inside a real loop. `DECISIONS.md:68` |
| 3 | blind representation (78ch/12) | **examined → refuted → reversed, never shipped** | Cheap C4a probe (2026-06-04) found oracle farm planes gained nothing → "don't build it"; **overturned 2026-06-29** — sighted planes flip the value head α=0→live (−20.5% regret, passing shuffled-control, CL-037); never reached a game-gated net until M2. `DECISIONS.md:74` → `:20` |
| 4a | saturated `tanh(margin/15)` target | **inherited default, flagged as a bug, kept** | F-C2: pins to ±1 for typical 30–80pt margins → kills mid-range calibration where close games live; a de-sat probe (/15 vs /40) showed no proxy gain → kept anyway. Just a Phase-3 literal. `docs/research/foundational_audit_2026-06-02.md:99` |
| 4b | near-zero-variance residual target | **deliberate + evidence** | The *first* asset-positive learned value in the investigation (2026-06-06); the residual inherits v2.7's local ranking by construction. Degeneracy (Δ std 0.071, ~0.5% of the Q signal) was measured then frozen 2026-06-08 — a side effect, not a defect at the time. `DECISIONS.md:63` |
| 5 | low sims (100–200), no Gumbel | **mixed** | Low sims = a *deliberate* training-economy default (sims is a free inference knob raised vs a human); **Gumbel = never examined** — absent from the entire decision/backlog/governance record except this autopsy, as a departure to reverse. |

**Tally: two deliberate-with-evidence (#1, #4b), two examined-once-then-abandoned on a confounded substrate (#2, #3),
two inherited defaults (#4a saturation, #5 Gumbel).** The recurring failure mode is not bad reasoning but **correlated
rejection on a weak substrate** — each lever judged with the others at their weak defaults — which is exactly why the
accumulated "value is inert" reads may be **target/representation-caused, not capability**, and why M2 flips all five
simultaneously. **Caveat retained:** #1 is genuinely evidenced (a real −800 cliff, a closed Option-2), so M2 faces a
real prior, not a strawman — it only corrects that those failures could not separate "the value is incapable" from
"we never gave it a target, the context to learn it, or a non-circular ruler."


## 7. The dimensionality / route-closure clause — **FINAL: EARNED, SCOPED CLOSURE (M1 KILL · M3 bounded · M2 KILL)**

*(Branches were pre-committed below; all three have read out. M3's fire refuted Gate-B as a law and reopened the
lever; M2 — the deciding test, with the FPU fix installed as an ingredient — then returned a clean KILL on both
pre-registered reads. So the clause closes, and it closes EARNED: not "we never tried the canonical cell," but
"we tried it, non-circularly scored, and it cannot beat the leaf at this scale.")*

**M1 — KILL (settled, 2026-07-02).** Fresh-band fixed-rung paired (each of iter2/iter8 vs heur@800-v2.7, band 5.0e9,
sims=800, n=400): iter8 +136.0/z7.71, iter2 +138.0/z7.93, **paired Δ(iter2−iter8)=+2.0 elo, z=0.09 = TIE.** iter2 does
**not** clear ≥2σ over iter8 → its prior +53.7/z2.14 was band-max noise / forking paths (refuted on a third fresh
band). The "deeper-teacher doesn't help" verdict **stands, now powered.** No revival of the deeper-teacher line.
(results.csv `m1_deepteacher_iter2_vs_iter8_freshband_h800_s800_n400`.)

**M3 — FIRES (n=100 screen; confirming at n=400).** The FPU sweep recovers the additive-value crater **monotonically**:
fpu=0(0.265)→0.2(0.375)→**0.4(0.46, clears the ≥0.45 bar)**; isotonic 0.33 (< FPU despite a 5.1× offline-MSE fix).
Two things sharpen it: the monotone trend is mechanistically coherent (not a lucky cell), and **isotonic recovering
*less* than FPU** localizes the mechanism to the **MCTS max-operator's optimistic-tail hunting** (which FPU tames
directly), *not* raw miscalibration — the exact mechanism the 3 nails were blind to. **⇒ Gate-B ("a learned value
can't drive MCTS search", CL-038) is refuted as a LAW; it narrows to "an uncalibrated value with the wrong FPU
craters."** The recovery is to ~heuristic **parity** (0.46≈0.50), not *exceeding* — so the value still doesn't beat
the leaf; it just stops hurting. **CONFIRMED @ n=400 (2026-07-02):** fpu=0.4=**0.391** (z−4.35, partial — does NOT clear the bar; the n=100 0.46 was
screen-optimistic) but **fpu=0.6=0.496 (z−0.15) = statistical PARITY with the 0.500 pure-heuristic anchor** → the
monotone recovery **0.265→0.391→0.496 clears the ≥0.45 bar decisively**. So the crater is a fixable FPU/
optimistic-tail artifact and Gate-B is refuted as a law. **Honest caveat:** recovery is to PARITY, not exceeding, and
needs a *high* FPU (0.6) — which may mean FPU is *neutralizing* the value's influence (agent plays ≈ pure-heuristic)
rather than the value *driving* search well. Either way the hard "value POISONS search" reading is dead: a learned
value CAN be blended without cratering (given FPU). Whether a value can be made to *help* (exceed the leaf) is the
wide-open **M2** question. The value-leaf lever is **reopened** (Gate-B doesn't close it); the loop earns its §10(b)
budget with FPU installed. The **full FPU curve** (2026-07-03, n=400): 0.265→0.4(0.391)→**0.6(0.496 PEAK=parity)**→0.8(0.4825)→1.0(0.476) — **peaks at parity and rolls off beyond**, confirming FPU removes the weak value's *harm* but cannot make it *exceed* the leaf; the exceed-lever is a better VALUE (M2), not more FPU. results.csv `m3_confirm_fpu0{4,6,8,10}_c3_b027_n400`.

**M2 — KILL (FINAL, 2026-07-03; both pre-registered reads; protocol committed `9cbd818` BEFORE the numbers).**
The never-run canonical-AZ cell was sampled: 5-iter loop (400 games/iter, sims=200, local+laptop orch), sighted rep
(81ch/42sc) × pooled value head × `score_diff_wide` × FPU=0.6 × `--leaf-eval nn` (the value DRIVING the leaf).
- **PRIMARY (solver-scored value ranking, F4 non-circular):** on 1,119 exact-marginalized K≤2 roots (identical roots
  per ranker, solve-once-score-many), the v2.9 leaf scores **τ=0.615 / top1=0.610 / regret 0.951**; the five nets
  score **τ = 0.018/0.021/0.018/0.021/0.023 (iters 00→04) — ~27× below the leaf and FLAT across training**; top1
  ~0.08; paired-vs-leaf sign-z **−17…−18** (+0.9–1.0 pts exact score margin lost per root). Artifact:
  `measurement/canonical_az/solver_score_m2_final_it00_04.json` (de-risk run reproduces to 4 decimals).
  **Mechanistically sharp:** the heads are NOT dead — v_nn tracks the current-player score-diff (corr 0.50→0.65,
  rising with training) — they learn the position *level* but have **zero between-sibling discrimination**. This
  confirms §3A's "the residual value space is ~1-D / the leaf is a decomposable additive evaluator" **non-circularly,
  for the first time** (every prior version of that reading was h6400-scored).
- **CONVERSION (rs-sweep, n=200/cell, fpu0.6, vs RoD-v2 iter_02):** 0/6 cells gain ≥2σ over their rs=0 baseline;
  every ladder non-monotone; weight hurts (iter_00: −36.6/−34.9/**−68.6**; iter_02: −65.0/−19.1/−31.4; iter_04:
  −22.6/**−68.6**/−38.4) — M3's mechanism replayed: FPU masks a contentless value at low rs, weighting it degrades
  search. The h_v2.9@3200 confirm leg is **moot by its own precondition** (it confirms "the winning rs"; none exists).
- **Secondary (in-loop policy, blend=0):** flat-negative ~−40 elo vs the anchor across 5 iters (−36.6/—/−65.0/−45.4/
  −22.6), never at parity → no policy compounding either. results.csv `m2_solver_score_k2_it00_04_n1119` +
  `m2_inloop_*` + `m2_rs_sweep_*`.

**Net (FINAL):** with M1 killed, M3 bounded (parity-not-exceeding; FPU axis closed), and M2 killed on the
pre-registered criteria, **CL-039 upgrades from "premature" to an EARNED, SCOPED closure**: the AZ-value route —
scalar / structured / clairvoyant / fair / **and now canonical (sighted × pooled × non-degenerate × FPU-installed ×
value-driven)** — cannot exceed the v2.7/v2.9 leaf **at this scale** (7M net, ≤5 iters, ≤400 games/iter, sims≤200).
The scope guard stays: this is not a proof about 10–100× scale, Gumbel search, or fundamentally different
architectures — it is the honest exhaustion of the recipe family this program can afford to sample. The §10(b)
flywheel does NOT launch (its pre-condition was an M2 fire).

## 8. Governance

Filed as **CL-042 — FINALIZED 2026-07-03** (**CL-041 is the S1 v2.9 promotion**, not this). **CL-039 → earned,
scoped closure** (this document, §7). **CL-040 (§5A) folded into M2's frame** — its one surviving non-circular
question ("does a tempo axis add signal against a non-circular target?") is being re-adjudicated with the same
solver ruler (arm retrains + `--arm-ckpt` solver-scoring, prep `7fa6e6e`; results will amend CL-040, not this
verdict). The §10(b) flywheel is NOT triggered (pre-condition failed). Verdict executed autonomously per the
pre-registered protocol under Joshua's 2026-07-03 standing authorization; no PRODUCTION/champion change (the
champion remains deep-classical v2.9 Bmild_cap8, CL-041).
