# AZ-value route — autopsy (DRAFT · **REOPENING** — M1 KILL, M3 FIRES; M3-confirm + M2 pending)

**Status:** 🚧 DRAFT — §7 is now PARTLY resolved: **M1 KILLED** (iter2's gain was band noise) and **M3 FIRED**
(FPU recovers the Gate-B crater → Gate-B refuted as a *law*), so the read-out is a **reopening, not a death** —
CL-039 stays QUALIFIED, not upgraded to a closure. Still pending before §7 is FINAL: the **n=400 M3-confirm**
(running laptop-only) + **M2** (the never-run canonical-AZ cell, solver-scored). Do NOT flip CL-039 to a hard closure.
· **Created:** 2026-07-01 · **Updated:** 2026-07-02 (M1/M3 landed)

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

## 7. The dimensionality / route-closure clause — **REOPENING (M1 KILL, M3 FIRES; M3-confirm + M2 pending)**

*(Branches were pre-committed below; two of three have read out. The read-out landed on the "ANY fires" branch, so
the strong-form closure is NOT written — the autopsy records a **reopening, not a death**.)*

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
the leaf; it just stops hurting. **Pending: the n=400 confirm** (fpu=0.4/0.6, running laptop-only — does 0.46 hold at
verdict power?). If it holds, the weaned value-leaf lever (closed by CL-038) is **reopened**: the loop earns its
pre-registered §10(b) budget **with FPU installed.**

**M2 — PENDING (the never-run canonical-AZ cell, solver-scored).** The big build; becomes the where-a-future-loop-aims
if the head shows a monotone ≥2σ paired game effect or solver-τ>0.5. The solver-scoring harness
(`scripts/canonical_az/solver_score.py`, b0e7158) is built; M2 is the remaining reopener.

**Net so far:** the strong-form "route exhausted at these resources" **cannot** be written — **M3 fired**, so Gate-B's
generalization dissolves and the value-leaf flywheel is **"available but unproven."** CL-039 stays **QUALIFIED**
(premature closure), not upgraded to an earned closure. Finalize this clause after the n=400 M3-confirm + M2.

## 8. Governance

Filed as **CL-042** (pending finalization; **CL-041 is the S1 v2.9 promotion**, not this). Qualifies **CL-039** (the
premature route-closure — stays qualified, NOT upgraded to a closure, because M3 fired) and folds **CL-040** (§5A)
into M2. The §10(b) 20–30-iter two-band flywheel is a **separate, larger budget decision** that a positive
M1/M2/M3 *enables* but does not auto-commit — surfaced to Joshua explicitly, not a silent continuation.
