# POST_REVIEW_PLAN — reconciling the fresh-look review (2026-07-01) with live state

**Status:** DRAFT / execution plan · **Created:** 2026-07-01 · **Branch:** `rod_v2_flywheel`
**Trigger:** `fresh_look_review_20260701` (blind-first external review). The reviewer's own output docs
(REVIEW.md / PHASE1_DIAGNOSIS.md / PHASE2_COLLISION.md) are **not on disk** — the authoritative finding-set
is the reconciliation brief pasted into the 2026-07-01 session (findings F1–F10). This doc distills that brief,
reconciles it against live `STATUS.md` / `DECISIONS.md` / `governance/*.csv` / `results_csv_relevant_rows.csv`,
and flags every conflict rather than assuming through it.

**One-line thesis of the review:** experiment-level rigor was above field norm; the failure was **verdict scope
and selection discipline at the *program* level.** Three specific reopenings (M1/M2/M3), one methodological
correction (score offline gates against the **exact solver**, not the h6400 teacher), two ship actions (S1/S2).
Nothing here reopens a fairly-killed lever (§6).

---

## THE THROUGH-LINE FIX (binds every step below)

The **exact K≤4 alpha-beta endgame solver** (`scripts/level2/endgame_solver.py`: `solve() → SolveResult`,
`regret_of(res, action)`) is the **only non-circular ground truth in the project, and has never been used as a
value/ranking probe.** From here, **every offline value/ranking gate scores against the solver, not h6400.**
Where the solver's K≤4 horizon is too shallow, say so and use **game outcomes on fresh bands** — never the
circular oracle.

**Why (F4):** the h6400 teacher-Q correlates **0.995** with the static v2.9 leaf (already in the record — the
CL-033 value-resurrection row states "leaf~oracle corr 0.995"). Any offline gate scored against h6400 is
measuring "can the value beat the leaf at predicting the leaf's own search," a metric in which the leaf is
**definitionally near-optimal.** This retroactively contaminates the *offline* reads of CL-032/033/034/036,
Probe-A §3A, and §5A stage-2 to the degree h6400 ≈ leaf. It does **not** touch game-gated verdicts.

---

## §0 — Kill the §5A run + salvage — **ALREADY DONE (conflict flagged)**

**CONFLICT #1 (brief assumes a live run):** the brief's §0 says "kill the in-flight §5A run." **There is no live
run.** The §5A seed-sweep OOM-killed the WSL box last session and was **not relaunched** (Joshua's call); the probe
was closed and committed (`8ec46d2`, CL-040). Process census at plan-time: **0 python running.** So the kill is moot.

**Salvage (done):** gate-zero — the tempo-vs-farm/bag correlation residualization — is **non-circular and already
saved** (`measurement/probe_5a/gate_zero_result.json`; verdict PARTIAL, 10-feature timing-depth core, ρ₁=0.76).
That output stands and is reusable.

**CONFLICT #2 (F4 retroactively downgrades CL-040):** §5A's stage-2 "live offline lead" (`tempo_only` +44.7%
regret-reduction at h6400) was **scored against the 0.995-circular oracle** — it is exactly the metric F4 warns is
unreadable. So CL-040's "LIVE OFFLINE LEAD" reading is **not clean**; only gate-zero survives as non-circular.
**Correction (executed with this plan):** CL-040 / `PROBE_5A_RESULTS.md` / STATUS annotated — the +44.7% is
**circular-frame, unresolved**, not a validated lead; §5A's *valid* question (is there a value axis uncorrelated
with farm/bag, and does it add signal *against a non-circular target*) is **absorbed into M2** (§4), scored against
the solver. §5A is **not re-run as-is.**

---

## §1 — The two ship actions (do first; S2 is zero research-risk, S1 needs an explicit flip-gate)

Humans-in-the-loop is **deferred by Joshua** — no human match protocol this week. Internal promotion (S1) and the
bot anchor (S2) proceed.

### S1 — Promote v2.9 + ship deep-classical + exact-endgame as the internal deliverable
> **✅ FLIPPED 2026-07-02** (Joshua's 'flip s1'): h6400 arbiter = +64.3 elo/z3.77/wr0.591 (n=399) → PRODUCTION.yaml champion = deep-classical v2.9 Bmild_cap8 + exact-endgame; neural iter8 → lineage. CL-041.
Per F7 + the unsaturated depth ladder, the strongest agent in the ecosystem is **deep HeuristicMCTS on the v2.9
leaf (`Bmild_cap8`, h6400–h12800, Cython leaf) with the exact-solver endgame handoff** — not the sims=200 neural
champion (`flywheel2_champion_iter8`, iter8+v2.7, still in PRODUCTION.yaml). The record's own numbers: h6400 > h3200
(margin +2.49pt z+2.61), h12800 > h6400 (+3.87pt z+2.27 screen), RoD1 **loses** to h6400, v2.9.1 `Bmild_cap8`
beats v2.8-prod +55 elo. Estimated ~+200–250 elo over current production.

- Promote v2.9 (`Bmild_cap8`) to the production leaf.
- Make the reference agent deep-classical + exact-endgame handoff.
- **Note:** the "learned component must exceed the heuristic" framing is self-imposed, not in the goal statement —
  S1 ships the best *agent*, learned-or-not.

**CONFLICT #3 (S1 is a real PRODUCTION change against a standing MEASUREMENT-ONLY freeze).** Every recent ledger
entry ends "PRODUCTION.yaml / champion / v2.7 / v2.9 UNCHANGED." v2.9 promotion was **explicitly deferred** — "promotion
is a SEPARATE explicit call" (STATUS 2026-06-25), and the **h6400 v2.9 arbiter was DEFERRED to promotion-time and
never run.** Therefore S1's actual PRODUCTION.yaml/champion-identity flip is **gated on:**
1. Run the deferred **v2.9 h6400 arbiter confirm** on a **fresh deck band, n=400 paired**, before flipping (the
   brief's own precondition).
2. **Explicit Joshua go** to edit `governance/PRODUCTION.yaml` (the champion pointer) + `CHECKPOINT_LINEAGE.csv`.
Until both clear, S1 is *prepared and measured*, not *flipped*. (Cost discipline: confirm the flip in one sentence
before writing it.)

### S2 — Stand up a bot anchor (no humans)
Port **one** out-of-ecosystem opponent — `SamuelScheit/carcassonne-ai`, `Carcassython`, or the Ameneyro-2020
chance-node baseline — and ladder the promoted stack against it, fair-information, n≥400. This breaks the
v2.x-family circularity (F4/F9) that contaminates **every internal number** and gives M1–M3 a non-circular external
reference. **Bot-only this week.** If no port lands cleanly in budget, **report which and why — do not fake an
anchor.** (The port itself is a local build, no cluster spend; only the ladder eval needs a box.)

---

## §3 — M3: is Gate-B a fixable calibration failure, not a law? (~1 day, cheapest reopener)

**Finding.** Gate-B blended 27% of a τ≈0.43 evaluator into a τ≈0.895 one; the review argues the craters are SNR
arithmetic amplified by MCTS's max-operator hunting the learned value's **optimistic error tail**. The 3 nails ruled
out distribution / subtraction / retraining but **not calibration / tails** (interior-τ is rank-based, blind to
tails; additive+frozen craters are consistent with tail-hunting). If it's tails, "value can rank but can't drive
search" is not a law — it's "an *uncalibrated heavy-tailed* value can't drive search," and the standard fixes were
never tried (LCB/ensemble pessimism, isotonic calibration; c_puct/FPU never re-swept for the new value scale, F10).

**Experiment.** Re-run nail-2's additive arm (static, n=100, sims=100 — cheapest; harness
`scripts/step2_pens/eval_step2.py` + the additive-leaf mode committed `c4be026`) three ways vs the **0.500
pure-heuristic anchor**:
1. `leaf = clip(h + 0.27·(v − k·σ_v))`, σ from a 4-head ensemble or MC-dropout, k∈{1,2} (LCB/pessimism);
2. `leaf = clip(h + 0.27·isotonic(v))`, isotonic map fit on held-out search-Q (calibration);
3. unchanged value, c_puct/FPU re-swept {1.5, 2, 3} × {None, 0.2, 0.4}.

Build cost: arms 1–2 need a small σ-head/isotonic add-on; arm 3 is pure eval flags.

- **Success:** any arm recovers 0.285 → **≥0.45** (≥2σ vs the 0.500 anchor) → Gate-B's *generalization* dissolves;
  the weaned loop earns its pre-registered §10(b) budget **with the fix installed**. Gate-B stays valid narrowly
  (this substrate, blend 0.27, these knobs) but not as "the learned-value-leaf lever is closed."
- **Kill:** all arms ≤0.30 → mechanism isn't tails/calibration/knobs; "can't drive search" hardens and Gate-B's
  general form gains real support.

## §2 — M1: recover the discarded deep-plane learned gain (~1–2 days)

**Finding (verified against `results_csv_relevant_rows.csv`).** Row `confirm_iter2_vs_heur800_v27_s800_n400`:
deepteacher **iter2** (sims-800-teacher continuation, warm-from-iter8) beat iter8 **+53.7 paired elo, z=2.14, at
agent sims=800** — the deep plane where every other learned gain washes out — with a same-direction n=100 screen
(+50.4, z=1.42) on a second band. Flagged "**RECOMMEND fold iter2 to production**," **never folded** (owner OOO). The
run continued to iter12 (ties iter8) and was verdicted "deeper policy teacher doesn't help" **off the final
iterate** — the F7 failure mode (final-iterate/underpowered verdicting burying a real positive). The SEALED audit
measured only iter0-vs-iter12 endpoints; **iter2's +53.7 was never followed up.**

**Honest caveat to encode:** "replicated on two bands" = **one significant (z=2.14) + one non-significant
same-direction (z=1.42)**. Prior is "promising," not "established." This test decides *real transient gain* vs
*forking-paths/band-max noise*.

**Experiment.** `iter2.pt` confirmed on the share (`/mnt/c/carc-shared/deepteacher/ckpt/iter2.pt`, reachable).
Re-eval iter2 vs iter8, deck-paired, **n=400, agent sims=800, on a FRESH band** (not either prior band); same vs
`h3200_v2.9` and `h6400_v2.9`. Harness: `scripts/eval_net_vs_heuristic.py` + `scripts/odo_paired_tally.py`.
**Metric: paired elo vs a fixed external rung (heur@800), never vs parent** (avoid forking-paths;
keep-best-vs-fixed-rung is legitimate, keep-best-vs-parent is not).

- **Success:** ≥2σ over iter8 on the fresh band → the gain is real and was lost to final-iterate verdicting. Revive
  the deeper-teacher line **warm-from-iter2** with **per-iterate keep-best gating vs a fixed rung** (n=200 screen →
  n=400 confirm) on the v2.9 leaf. Record the correction to the "deeper teacher doesn't help" verdict.
- **Kill:** fails fresh-band replication → the two prior reads were band noise / forking paths. Close it, record the
  correction, the "deepteacher" verdict stands.

## §4 — M2: sample the never-run canonical-AZ cell, scored non-circularly (~3–5 days; after M1/M3)

**Finding (F2/F4/F10).** Every game-gated lineage net trained on either the **saturated** `tanh(margin/15)` outcome
or the **near-zero-variance residual** (residual ≈ 0.5% of the Q signal), with `value_global_pool=False` in **every**
checkpoint (KataGo-style pooling built 2026-06-05, never enabled — confirmed in PRODUCTION.yaml arch string), on the
**blind** representation, sims 100–200, no Gumbel. `score_diff_wide` (/40, confirmed in `selfplay.py`) and `wl` exist,
were prescribed (C6 + charter), and have **zero game-gated samples.** So the cell {sighted inputs × pooled value head
× non-degenerate target × sound low-sim improvement} — the closest thing to actually running AlphaZero here — has
**never been sampled.** A head trained on a saturated or 0.5%-variance target *cannot* develop cross-subtree
discrimination regardless of capacity → the observed flat corr/τ may be **target-caused, not capability.**

**Tension to hold honestly (don't let the review's optimism pre-decide):** §3A found farm/bag collapse to ~1
dimension across scalar AND structured heads — real evidence the residual value space may be genuinely small (the
leaf is a decomposable additive evaluator). **BUT §3A scored against the circular h6400 oracle**, so its "1-D"
reading is itself suspect. **M2 resolves the tension by scoring against the solver.** Expect a real chance M2
returns a **kill** — the leaf may simply capture most of the additive value. This test adjudicates; it does not
resurrect.

**Experiment.** One warmstart + short (3–5 iter) loop with **all four ingredients fixed simultaneously:**
- sighted CNN (Gate-A's +3 union-find farm planes + 32-type bag histogram);
- `--global-pool` ON, `--warm-value-fresh` (verify wiring in `network.py`/`train_iter.py` before launch);
- `--value-target score_diff_wide` (or `wl`), value_loss_weight 2–3;
- Gumbel root selection at 64–150 sims if cheap to wire, else PUCT@200;
- per-iterate eval vs `h3200_v2.9`, n=200.

**Fold §5A's valid question in here:** as part of the representation probe, test whether any **uncorrelated** axis
(incl. tempo, gate-zero-checked <0.5 R² vs farm/bag) adds signal **scored against the exact solver**, not h6400.

- **Success:** value-head game contribution measured directly — a residual_scale sweep {0, 0.25, 0.5} on the
  trained head shows a monotone **≥2σ paired game effect** at any point (first time in project history), **OR**
  value-outcome corr on held-out fresh-band games > 0.6 with sibling τ > 0.5 **against the solver.**
- **Kill:** head inert (rs-sweep flat, solver-τ < 0.3) with all four ingredients fixed → inertness is
  architecture-independent at this scale, and CL-039's closure gains the real support it currently lacks.

## §5 — The autopsy: BLOCKED until M1/M2/M3 read out

**Do not finalize the closure sentence.** CL-039's "the AZ-value route is exhausted (scalar/structured/clairvoyant/
fair)" is **premature as a route closure; accurate only as "this recipe family, at this scale, is exhausted."** The
ledger's entries are correlated on the circular oracle (F4), degenerate targets, pooling-off architecture, and
blind-era representation.

- Everything ELSE can be drafted now: Gate-B (valid narrowly), the fairly-killed levers (§6), the ship decision,
  the mechanism findings.
- Write the dimensionality/closure clause as an explicit **`[PENDING M1–M3]`** placeholder.
- After M1–M3: **all three kill** → write the earned strong form, scoped "at these resources." **Any fires** → the
  flywheel is "available but unproven," revive per M1/M2's success path, autopsy records a **reopening, not a death.**

## §6 — Do NOT reopen (fairly killed; the review concurs)

Clairvoyance as a play-strength inflator (F1, +26.6/z−0.9); deck-aware closure for full-game strength (F8, +3.5/
z1.09); farm-majority gating; opp-cap denial; symmetry augmentation; the ML compute scheduler; the typed-GNN head;
deeper exact endgame as a *winrate* lever (F9, margin-positive/winrate-neutral); "root/offline metrics predict game
strength" (correctly killed 4×). **Out of scope.**

---

## §7 — Sequence, budget, guardrails

**Order:** §0 (done) → **§1 S1(prep+measure) + S2** (parallel; S2 zero-risk, S1 flip gated) → **§3 M3** (~1 day,
cheapest) → **§2 M1** (~1–2 days) → **§4 M2** (~3–5 days) → **§5 autopsy finalize** (only after M1–M3). ~1 week of
investigation alongside the ship work.

**Guardrails (charter-binding):**
- Score offline value/ranking gates against the **solver, never h6400** — the through-line fix.
- n=400 paired ≈ ±12 elo (repo-corrected); **+20 elo is NOT resolvable at n=400.** Fresh bands for replication;
  keep-best vs **fixed rung**, never vs parent.
- Gate on **games**, not offline metrics, for in-loop candidates. Read at pre-registered n, single read-out, no peeking.
- **Cheap-and-decisive earns the run; expensive-and-doesn't-change-the-decision doesn't.** M1/M3 are ~1–2 days —
  run them. The full §10(b) 20–30-iter two-band flywheel is a **separate, larger budget decision** that a positive
  M1/M2/M3 *enables* but does not auto-commit — **surface it explicitly to Joshua, not a silent continuation.**
- Do not let the review's well-written optimism pre-decide outcomes ("available but unproven"; M1–M3 may all kill).

**Standing ops constraints (CLAUDE.md — bind every launch):** ask which box + state ETA before any multi-minute run;
`nice -n 19`; detach (`setsid`/nohup) anything >~1 min; remote ssh pipes a `.sh` with `cd` on line 1
(`ssh host 'bash -s' < f.sh`); share path local `/mnt/c/carc-shared` vs remote `/mnt/carc-shared`; pre-launch
process census; commit at good stopping points (push needs an ask); results.csv is source of truth; a lone >1σ value
is noise until re-measured. Local 5900XT box has recurring dirty reboots → checkpoint per-iter. Large-obs ops run
solo/concurrency-2 (the §5A OOM lesson).

**Deliverables:** this plan (done) → per-experiment result docs under the measurement convention → the autopsy with
the `[PENDING M1–M3]` clause. Spec/plan before runs; flag conflicts. **No human-in-the-loop work.**

---

## Open decisions for Joshua (surfaced, not assumed)

1. **S1 production flip** — approve editing `PRODUCTION.yaml`/`CHECKPOINT_LINEAGE.csv` to the deep-classical +
   exact-endgame reference? And run the **deferred v2.9 h6400 arbiter** first (fresh band, n=400) — which box?
2. **Machine selection** for M3 / M1 / M2 cluster runs (5900XT local / Xeon / laptop / split). M2's loop → standing
   all-3-box default; M1/M3 are one-off evals → ask.
3. **S2 bot port** — which opponent to attempt first (SamuelScheit / Carcassython / Ameneyro-2020), or let me scope
   portability and recommend?
4. **Post-M budget** — if any of M1/M2/M3 fires, the full §10(b) 20–30-iter flywheel is a separate ~multi-day
   cluster commit; I will surface it as an explicit decision, not auto-start it.
