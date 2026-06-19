# Level-2 saturated-ruler ladder — VERDICT (L2-1)

> **Measurement gate only.** No train / promote / redesign / modify-iter8 follows.
> Executes [LEVEL2_LADDER_PROTOCOL.md](LEVEL2_LADDER_PROTOCOL.md) (§5/§8.3 of the
> MEASUREMENT_FIRST spec). Champion under test FROZEN: iter8 (sha `0d355002…`).
> Run: 2026-06-18, 5800x (W28) + laptop (W20), shared-claim, code_rev `6b5b43f`.
> Raw: `/mnt/c/carc-shared/level2_ladder/<rung>__vs__<rung>/`; machine results
> `LADDER_RESULTS.json` (via `scripts/level2/aggregate_l2_ladder.py`).

## Config note — the heur rungs run at the PRODUCTION ruler's actual c_puct
All heuristic rungs use `HeuristicMCTS` at the module default **c_puct = 1.5**.
This is **not** a deviation: in the production eval gate
(`eval_net_vs_heuristic.py`) the `--c-puct 3.0` flag is applied to the **neural**
side only — the `HeuristicMCTS` opponent is constructed without `c_puct` and so
has *always* run at 1.5. The `old_c=3.0` column in prior results.csv ladder rows
is the **net-side** c, not the heuristic's. Therefore the ladder's R4
(`heur_v2_7@800`, c=1.5) is byte-for-byte the established ruler, and the
saturation gate is measured at the production heuristic config. v2.7 leaf env
matches production: `CAP=12 DROP_THREE_OPEN=1 FLAT_LEAF=1`, no residual/blend.
Provenance smoke passed: each heur rung ran exactly its claimed leaf
(v2.7 rungs `v2_7_calls>0 & v1_calls==0`; v1 rung the inverse).

## The matrix (n=200 paired each, disjoint fresh bands 3.0e9+)

| step | higher vs lower | W/D/L | elo (A vs B) | paired z | flag |
|---|---|---|---|---|---|
| R1vR0 | greedy vs random | 200/0/0 | +800.0 (cap) | +55.62 | ✅ clean |
| R2vR1 | heur_v1@200 vs greedy | 107/1/92 | +26.1 ±24.6 | +1.87 | ⚠️ compressed |
| R3vR2 | heur_v2_7@200 vs heur_v1@200 | 106/2/92 | +24.4 ±24.6 | +1.68 | ⚠️ compressed |
| R4vR3 | heur_v2_7@800 vs heur_v2_7@200 | 120/3/77 | +75.9 ±25.2 | +3.59 | ✅ clean |
| **R5vR4** | **heur_v2_7@1600 vs heur_v2_7@800** | **228/7/165 (n400)** | **+55.2 ±17.6** | **+3.23** | **✅ clean — gate REFUTED** |

> **R5vR4 z=2.23 at n=200 ∈ [1.5, 2.5] → pre-registered power-escalation fired → topped
> up to n=400** (band 3.04e9, 200 paired decks). Result CONFIRMED and tightened: R5
> (heur@1600) beats R4 (heur@800) **+55.2 elo, z=3.23**. The point estimate regressed
> from the n=200 +70.4 (that band ran slightly favorable) but z *strengthened* with n ⇒
> the refutation is solid, not a borderline fluke. **Saturation gate REFUTED.**
>
> _Follow-on (running): R5'@3200 vs @1600 (band 3.06e9, n=200) — does the depth-headroom
> continue above @1600, or does saturation just move up one rung?_

Flag legend: **clean** = higher rung wins with z≥2 (non-overlapping CIs);
**compressed** = within-noise tie (|z|<2), the scale can't resolve that pair at
n=200 (reported, not a failure); **INVERTED** = lower rung beats higher z≤−2
(would indicate a harness/leaf bug — none observed).

## Ladder shape — where the strength scale resolves (the structural finding)
The ladder is **monotone in point-estimate** (every step has positive elo, no
inverted step ⇒ no harness/leaf bug) but **not all steps are z≥2-clean**. The
resolution is concentrated at the two ends:
- **Floor is wide & clean:** random → greedy = +800 (z=55.6). Any search/heuristic
  crushes uniform-random.
- **The heuristic mid-rungs are COMPRESSED:** greedy ≈ heur_v1@200 ≈ heur_v2_7@200,
  each step only ~+25 elo at z≈1.7 (within-noise at n=200). At fixed low sims,
  *leaf quality* (v1→v2.7) and the *greedy→MCTS* transition buy little resolvable
  strength — the scale cannot crisply separate these three rungs at n=200.
- **DEPTH re-separates cleanly:** v2.7@200 → @800 = +75.9 (z=3.59), and @800 → @1600
  = +70.4 (z=2.23). **Search depth, not leaf design, is what moves the heuristic
  ruler.** This is the *pure heur-vs-heur* restatement of the `heurdepth_*` probe —
  and unlike that probe (which used a *fixed net* opponent and saw ≈0 resolving
  power for 200→800), heur-vs-heur depth scaling adds clear, resolvable strength.

## The 5-point verdict
1. **Is the ladder monotone (V4)?** — **Monotone in ordering, not strictly z≥2 at
   every step.** Clean steps: R1vR0 (z=55.6), R4vR3 (z=3.59), R5vR4 (z=3.23 @n400).
   Compressed steps: R2vR1 (z=1.87), R3vR2 (z=1.68) — reported as "the scale can't
   resolve this pair at n=200," not failures (no inverted z≤−2 step ⇒ no harness/leaf
   bug). The ladder is a *valid ordinal ruler* end-to-end; it is *coarse* in the
   heuristic mid-band (greedy↔v1@200↔v2.7@200 within ~25 elo each) and *sharp* at the
   depth rungs.
2. **Does a stronger ruler than heur@800-v2.7 exist (saturation gate, R5vR4)?** —
   **YES.** R5 (heur@1600) beats R4 (heur@800) **+55.2 / z=3.23** (n=400 paired,
   confirmed after the pre-registered escalation). **Saturation REFUTED** — the elo
   scale has real headroom above the current production ruler.
3. **Where does iter8 sit on the validated ruler (L2-2)?** — not run here. Deferred to
   **L2-2** (iter8 vs R4, and now also **vs R5=heur@1600** since R5 is a validated
   higher rung), fresh band 3.1e9, n=400; V6 reproduce vs the +58.7 sealed / +72.2
   published iter8-vs-heur@800 cell. **L2-2 is a NEURAL matchup ⇒ run through the
   carc-orch SHM eval server at high W** (per `feedback_use_orch_for_eval_and_gen`),
   unlike this pure-CPU L2-1.
4. **Does measurement remain saturated (§8.3)?** — **NO at the heuristic-depth axis.**
   The "ruler tops out at heur@800" worry is refuted: deeper plain heuristic search is
   a stronger, cheap, out-of-lineage reference. The ruler can be made stronger by
   simply spending more search — which *raises the bar* for any "superhuman" claim
   (iter8 must now also clear the deeper rung, not just heur@800).
5. **Next recommended action.** — (a) finish **R5'@3200 vs @1600** (running) to see how
   far the depth-headroom extends before the heuristic itself saturates; (b) run
   **L2-2** = iter8 vs {R4, R5} on the orchestrator at high W (re-ground iter8 on the
   *validated* ladder + V6 reproduce); (c) if @3200 still climbs, the strongest
   validated deep-heuristic rung becomes the new measurement ceiling for the superhuman
   program. **No train/promote/redesign follows from L2-1 — measurement gate only.**

## Power escalation (pre-registered)
If R5vR4 lands z ∈ [1.5, 2.5] (ambiguous), top up that one comparison to n=400
(band 3.04e9) before declaring; do not top up the others.
