# PROGRAM ROADMAP — post-Phase-1.1 (living doc, created 2026-07-07 ~02:45)

**What this is:** the single queue for everything in flight, gated, or promised — created after Phase 1.1 fired (+148.2, `b3d3312`), the transitivity round-robin passed G1, and the Fable premise-expiration audit added five findings on top of an already-full program. **Maintenance rule: every new finding/lever/promise lands HERE the moment it exists; every close-out updates its line (proposed 6th touch on the CLAUDE.md close-out checklist). A fresh session reads STATUS.md → this file and knows exactly what's next.** Numbers live in `experiments/results.csv` / the per-item PLAN docs — this file carries pointers, gates, and order only.

**Standing lesson behind half this queue (the "premise-expiration" signature):** a design decision whose justifying premises (cost model, component role, data scale, upstream versions) have expired but survives because it's "settled" — random expansion survived two expirations and hid +148 elo; the distillation kill was justified by its symptom. When touching any component, ask *when was this decided and do its premises still hold?*

---

## NOW (running as of 2026-07-07 ~08:15)
- 🔄 **K=3 endgame confirm** (A1): PUCT-priors@2750 vs h6400 @ exact-K=3, n=200, band 9.4e9 (CRN vs the K=2 confirm), **W30 local + W22 laptop, CARCASSONNE_TT_CAP=500000** (the K=4 crash was WSL-VM TT memory — now bounded). Local clean; laptop had 24 RR-4 `exact-k 2` orphans self-draining (watcher armed). → /tmp/k3_primary.log, CONFIRM_PROGRESS.tsv.
- ✅ **ROUND-ROBIN COMPLETE — both gates PASS, RPS retired.** M1 +230.2 / M2 +36.6 / M3 +149.3 / M4 −8.7. rr1-4 rows in results.csv.
- ✅ **CHAMPION FLIPPED** (see GATE #1).
- ⏸️ **Stage-0 adapter** — agent died on session limits (reset 3:20am ET) leaving `scripts/canonical_az/solver_score_agent.py` + test **uncommitted, extraction UNVERIFIED** ("per-child numbers not yet trusted"). Resume/verify before any measurement. [TEACHER_TAU_PLAN.md](../measurement/classical_search/TEACHER_TAU_PLAN.md)

## GATE — Joshua decisions needed (nothing below executes without them)
1. ✅ **Champion flip EXECUTED 2026-07-07** ("flip and go"): PRODUCTION.yaml → `puct_priors_v29_bmild_cap8`, CL-041 SUPERSEDED / CL-043 PROMOTED, docs stamped. (No CHECKPOINT_LINEAGE row — classical agent-config, not a `.pt`.) K=3 confirm running concurrently (does NOT gate the flip; Joshua flipped without waiting).
2. **Approve Track-B Stage 1 spend** if Stage 0 reads REOPEN (one box-day).
3. **Priority call** if compute contends: recommended order below interleaves cheap-decisive first.

---

## Track A — Champion aftermath (mostly compute, this week)
- **A1. K=3 n=200 endgame check** (~4h W52; K=4 crashed at 40h-misscope + WSL-VM memory — K=4 n=100 TT-capped is a weekend option only if K=3 moves the margin). Runs next after RR.
- **A2. Fair/PIMC deployable config derivation** (audit #2): equal-wall-clock grid K∈{2,4,8} × matched sims for fair-PUCT vs a fixed rung, n=100 screens → n=400 confirm (~6-10h). Needs a small launcher (STATUS 2026-07-05 rec #1) + PUCT adapter into `fair_agent.py`. **This is the config any human/superhuman claim is graded on**; also refreshes the stale iter8-only clairvoyance tax (~26.6, CL-022).
- **A3. Close-out for confirm + RR** (attended, ~30min): verify results.csv rows (RR-1/2 rows confirmed present 02:40), DECISIONS index lines, doc stamps, governance touches, `doc_lint.py`.
- **A4. results.csv/manifest spot-check** of the flip proposal's agent-pulled historical citations before any external use.

## Track B — The learned-track reopen (highest stakes: structural blocker #2)
- **B1. Stage 0: teacher-τ — ✅ DONE 2026-07-07, KILL-CONFIRM (value branch).** puct_q τ=0.567 / puct_visits τ=0.578, both < leaf 0.615 by >2σ (dτ z −3.49/−2.86). Value-label route stays CLOSED (5th independent confirmation the leaf is a freakish global ranker). Fable review: the regret/top_share "policy" signal is largely an endgame-terminal-reading artifact (all roots K=2 = last 2 tiles; CL-034 already showed the 6× regret collapse) + confounded top_share (rod1 was already 0.27 multi-phase) → NOT a policy reopen. Blocker #2 read: a stronger classical policy makes *worse* value labels → orthogonal; blocker #2 needs scale/arch not better 7M teachers. [TEACHER_TAU_PLAN.md](../measurement/classical_search/TEACHER_TAU_PLAN.md) verdict block; json `teacher_tau/stage0_sims2750.json`.
- **B1a. Diagnostics (Joshua 🟢) — gate the one unsampled cell:** (a) leaf-prior-vs-teacher-argmax **midgame disagreement rate** (Step-1 funded ONLY if ≥20% real headroom); (b) top-m-visited τ (needs a re-run — json stores only per-root aggregates). Net-free → laptop-safe.
- **B2. Stage 1 (CONDITIONAL on B1a ≥20% midgame headroom):** the ONE unsampled cell = distilled **net-prior vs leaf-prior inside the NEW PUCT**, ~10-20K PUCT@2750 roots → policy-only net on visit-dist targets → judged EXCLUSIVELY by n=400 paired **games** at equal wall-clock (hardware asymmetry in manifest). Pre-register against **CL-031's falsifier** (not a Stage-0 reinterpretation). 3 prior washouts (CL-031/032/sims-washout) predict FAIL; worth 1 box-day only as a clean registered kill in the new regime. Offline-judged = worth zero.
- **B3. Capacity probe re-run** (audit #3; conditional, bundle with B2's dataset): f64b4-vs-f128b6 solver-τ slope on the memory-safe ~2GB subset, **laptop only** (capacity jobs banned local). The 6×96 was sized for the cancelled coaching goal; "weakly-dead" = crash+proxy, never a slope.
- **B4. Recipe-refresh freebies if flywheel revives:** 2-epoch batch-256 (~1.5× throughput, unclaimed from the b512 calibration); the never-run FPU n=400 (mooted for expand-all; NeuralMCTS-side only).

## Track C — Search squeeze (each = pre-registered 1-2 cell A/B vs the confirmed c1.5/τ5/float/visits@2750)
- **C1. Gumbel root / sequential halving** — highest EV (simple-regret-correct at root; low-sims gains) AND is the Phase-5 build. Build ~1-2d attended/agent, then ~2h A/B.
- **C2. LCB final selection** (KataGo-style) — cheap add, closes the visits-vs-Q question properly.
- **C3. Tree reuse between moves** — confirmed absent (clear() per move, heuristic_prior_mcts.py:274); realistic ~1.1-1.3×; flag-gated re-root + hard assert + one n=200 cell. Cache-collision risk noted (Phase 0.3 family).
- **C4. VALUE_NORM bracket {8,15,30}** (audit #4): /15 calibrated on 1000 RANDOM games 2026-04-27; its own pre-registered revisit ("switch to 10") never ran. 2 cells n=100 → confirm a wing only if it wins (~2h).
- **C5. Leaf re-tune under PUCT** ("v2.11-for-PUCT"): v2.9 caps/weights tuned under random expansion — consumer changed. Biggest candidate, slowest (re-sweep + confirm, ~1-2 box-days). After C1-C4.
- **C6. Phase 1.2: ID-alpha-beta + TT** (gate met) — the one family that might BEAT PUCT (deterministic clairvoyant game + µs leaf = chess-engine territory). Attended build, surface cost first (~2-4d).

## Track D — Measurement validity (Phase 3, now load-bearing)
- **D1. Ruler re-anchor** (flip proposal §3 lists the HIGH rows: CL-041/LADDER/HYBRID/CLEAN_EVAL) — after flip signed.
- **D2. Rung-compression cell** (audit #5): PUCT rung @equal-time-h800 vs h800/h1600 rungs, shared decks, n=200 each (~2h) — are ladder *spacings* denominated in weak-search units? Fix the c=1.5-rungs vs c=3.0-champion inconsistency in the same pass.
- **D3. Original Phase 3 scope:** solve K=3 bulk + K=4 subset, TAU_VS_K doc (was "fix the ruler" MT-2).

## Track E — Program leftovers (original post-review phases, unstarted)
- **E1. Phase 2.1:** win-probability endgame objective + pre-registered exact-K winrate re-run.
- **E2. Phase 2.2:** fair midgame tax probe (K-sweep {4,8,16,32} + conservative estimator) — partially superseded by A2; reconcile scopes before running.
- **E3. Phase 5:** Gumbel flywheel BUILD ONLY then STOP+surface — warm-start premise CHANGED twice (from 1.1 winner; possibly distill-from-classical if B1 fires). Re-spec before building; C1 is its first component.
- **E4. Human-anchor arc** (Phase 4 infra ✅): expert suite runs + logged play + the 200-1300-game superhuman protocol ([LUCK_FLOOR.md](../measurement/human_anchor/LUCK_FLOOR.md)) — gated on A2 (fair config) + D1 (honest ruler).

## Parking lot (small / deferred / notes)
- `deck_hash` omits the first drawn tile (provenance-hash blind spot only; harness audit 2026-07-06).
- Phase 0.1 proposed PRODUCTION.yaml wording fix + PIMC deck-sort hardening — apply with the flip's governance touch.
- τ_p bracket + config broadening — DROPPED (Joshua 2026-07-06). value_norm survives as C4 only.
- Stepping-path Cython / de-objectify / compact-leaf — DEAD (break-even spike, `d3896c0`); do not re-propose without new premise.
- BACKLOG.md:375 ("heuristic prior blending at PUCT root") = the +148 ancestor that sat 6 weeks — grep BACKLOG before dismissing "small" ideas.

## Rough compute ledger (if everything runs): RR remainder ~1.5h · A1 ~4h · B1 ~1h · C2-C4 ~6h · A2 ~8h · D2 ~2h · B2 ~1 day · C1/C5/C6 ~1-2 days each ≈ **3-5 box-days** — matches "a few days at least, even if all null."

**Recommended execution order (cheap-decisive first, builds overlap compute):**
RR finish → **A1 (K=3)** ‖ verify B1 adapter → **B1 (Stage 0)** → **C4+C2** (cheap cells) ‖ build A2 launcher → **A2 (fair grid)** → flip signature + A3/D1 → **D2** → B2/C1/C5/C6 per gates.
