# PROGRAM ROADMAP — post-Phase-1.1 (living doc, created 2026-07-07 ~02:45)

**What this is:** the single queue for everything in flight, gated, or promised — created after Phase 1.1 fired (+148.2, `b3d3312`), the transitivity round-robin passed G1, and the Fable premise-expiration audit added five findings on top of an already-full program. **Maintenance rule: every new finding/lever/promise lands HERE the moment it exists; every close-out updates its line (proposed 6th touch on the CLAUDE.md close-out checklist). A fresh session reads STATUS.md → this file and knows exactly what's next.** Numbers live in `experiments/results.csv` / the per-item PLAN docs — this file carries pointers, gates, and order only.

**Standing lesson behind half this queue (the "premise-expiration" signature):** a design decision whose justifying premises (cost model, component role, data scale, upstream versions) have expired but survives because it's "settled" — random expansion survived two expirations and hid +148 elo; the distillation kill was justified by its symptom. When touching any component, ask *when was this decided and do its premises still hold?*

---

## NOW (2026-07-08) — champion arc DONE; first search-squeeze cells RESOLVED (reuse FOLDED); ruler re-anchor now load-bearing
- ✅ **CHAMPION FLIPPED** (`b2ff08f`) · **ROUND-ROBIN** RPS-retired (M1+230/M2+37/M3+149/M4−8.7, `ef95711`) · **K=3** +108.1/z6.11 (`74f23b0`, holds at deeper handoff) · **Stage-0 teacher-τ** KILL-CONFIRM value route (`f77a5da`) · **policy-distillation diagnostics** NO (4.75% real midgame headroom + CL-031 washout; `71c6ae8`+run).
- ✅ **TRACK-C search variants RESOLVED** (2026-07-08): **C3 tree-reuse FIRED → FOLDED into the champion** (`reuse_tree: true` in PRODUCTION.yaml, CL-044; +39.3/z2.81 n=400 equal-time, ms 1.06); **C2 LCB CLOSED** (wash vs visits, 0.0/z0.11); **C4 value_norm CLOSED** (15 optimal — both {8,30} wings negative, −24.4/−36.6). Screen null seat-bias clean. Numbers: `results.csv rr_puct2750-*`; see **Track C**.
- ✅ **A2 fair-PIMC SCREEN DONE** (2026-07-08, CL-045): fair **+49.0/z2.86** (champion blind beats a clairvoyant h800 rung), clair **+205.0/z6.68**, **clairvoyance tax ~156 elo** → clairvoyant ladders OVERSTATE deployable strength; graded-FAIR is mandatory for any human claim. See **Track A2/D**.
- Boxes FREE (local + laptop-net-free). Next cheap-decisive: **ruler re-anchor (Track D — now LOAD-BEARING)** + **human-anchor arc (E4, unblocked by A2's fair config)**; then Gumbel C1 / ID-alpha-beta C6. Learned-track net experiments DEFERRED per Joshua (search first) — see **Track B**.

## GATE / decisions — RESOLVED this session
1. ✅ **Champion flip EXECUTED** ("flip and go"): PRODUCTION.yaml → `puct_priors_v29_bmild_cap8`, CL-041 SUPERSEDED / CL-043 PROMOTED. (No CHECKPOINT_LINEAGE row — classical agent-config.)
2. ✅ **Stage-1 policy-distillation NOT funded** — diagnostics gate failed (4.75% real midgame headroom « 20%) + CL-031 washout. Value route also closed (Stage-0 τ). The learned track is closed **at 7M-warmstart** only.
3. ✅ **Strategic direction (Joshua): MAX SEARCH FIRST**, then revisit the net. The two untested learned-track cells — **from-scratch/tabula-rasa** (never run) and **bigger nets** (capacity probe crashed) — are DEFERRED behind the search-maxing (they're Fable's "scale/architecture" blocker-#2 path; cheaper capacity probe first if/when we return). Rationale: cheap ceiling-raising + re-anchor first tells us where we stand vs strong-human → informs whether the expensive net bets are worth it.

---

## Track A — Champion aftermath (mostly compute, this week)
- **A1. K=3 endgame check — ✅ DONE 2026-07-07: +108.1/z6.11/n199.** +148 holds at the deeper handoff (shrinks from +148 K=2 as expected, stays 6σ). Flip robust toward production K≤4. K=4 not run (~40h/run; K=3 answers it). results.csv `..._k3`; PUCT_PRIORS_RESULTS.md.
- **A2. Fair/PIMC deployable config — ✅ SCREEN DONE 2026-07-08 (CL-045).** K=2 n=100 both arms at the champion config (k_dets=8×sims=344=2752, exact-K=2 marginalized) vs a fixed clairvoyant h800 rung: **fair +49.0/z2.86** (champion blind still beats a deck-sighted rung → genuinely > h800 under honest play) · **clair +205.0/z6.68** · **clairvoyance tax ~156 elo** (~6× the stale iter8 CL-022 ~26.6). This is the config any human/superhuman claim is graded on. `results.csv fair_puct2752_*`; `scripts/classical_search/eval_fair_puct.py`. Follow-ups: n=400 fair confirm + a **determinized-rung** fair-vs-fair variant (cleaner deployable number); K∈{4,8} rows RAM/attended-only; re-check reuse×determinization (reuse now champion but was OFF in this run).
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
- **C2. LCB final selection — ✅ CLOSED 2026-07-08 (wash).** LCB (c_lcb=1) vs visits-argmax = 0.0/z0.11 (n=200 screen) → visits stays; LCB adds nothing at 2750. `results.csv rr_puct2750-lcbclcb1_*`.
- **C3. Tree reuse between moves — ✅ FIRED + FOLDED 2026-07-08 (CL-044).** Screen +47.2/z1.73 → confirm **+39.3/z2.81 n=400** at equal wall-clock (ms 1.06) → **`reuse_tree: true` in PRODUCTION.yaml.** Search-efficiency win (free effective depth on the reused subtree; dodges sims-washout). `results.csv rr_puct2750-reuse_*`. Open: reuse×fair-PIMC determinization re-check (A2 ran reuse-OFF).
- **C4. VALUE_NORM bracket {8,15,30} — ✅ CLOSED 2026-07-08 (15 optimal).** Both wings negative: vn8 −24.4/z−0.80, vn30 −36.6/z−0.66 (n=200 screen) → value_norm=15 confirmed. `results.csv rr_puct2750-vn8_*`/`vn30_*`.
- **C5. Leaf re-tune under PUCT** ("v2.11-for-PUCT"): v2.9 caps/weights tuned under random expansion — consumer changed. Biggest candidate, slowest (re-sweep + confirm, ~1-2 box-days). After C1-C4.
- **C6. Phase 1.2: ID-alpha-beta + TT** (gate met) — the one family that might BEAT PUCT (deterministic clairvoyant game + µs leaf = chess-engine territory). Attended build, surface cost first (~2-4d).

## Track D — Measurement validity (Phase 3, NOW LOAD-BEARING — A2/CL-045's ~156-elo clairvoyance tax + fair≠clair prove the clairvoyant HeuristicMCTS-calibrated ladders overstate deployable strength)
- **D1. Ruler re-anchor** (flip proposal §3 lists the HIGH rows: CL-041/LADDER/HYBRID/CLEAN_EVAL) — flip is signed → **re-anchor is now the top cheap-decisive item** (CL-045 shows the ladder overstates by ~156 elo under fair play).
- **D2. Rung-compression cell** (audit #5): PUCT rung @equal-time-h800 vs h800/h1600 rungs, shared decks, n=200 each (~2h) — are ladder *spacings* denominated in weak-search units? Fix the c=1.5-rungs vs c=3.0-champion inconsistency in the same pass.
- **D3. Original Phase 3 scope:** solve K=3 bulk + K=4 subset, TAU_VS_K doc (was "fix the ruler" MT-2).

## Track E — Program leftovers (original post-review phases, unstarted)
- **E1. Phase 2.1:** win-probability endgame objective + pre-registered exact-K winrate re-run.
- **E2. Phase 2.2:** fair midgame tax probe (K-sweep {4,8,16,32} + conservative estimator) — partially superseded by A2; reconcile scopes before running.
- **E3. Phase 5:** Gumbel flywheel BUILD ONLY then STOP+surface — warm-start premise CHANGED twice (from 1.1 winner; possibly distill-from-classical if B1 fires). Re-spec before building; C1 is its first component.
- **E4. Human-anchor arc** (Phase 4 infra ✅): expert suite runs + logged play + the 200-1300-game superhuman protocol ([LUCK_FLOOR.md](../measurement/human_anchor/LUCK_FLOOR.md)) — **A2 fair-config gate now CLEARED (CL-045: fair +49/z2.86 is the deployable config); remaining gate = D1 (honest ruler).**

## Parking lot (small / deferred / notes)
- `deck_hash` omits the first drawn tile (provenance-hash blind spot only; harness audit 2026-07-06).
- Phase 0.1 proposed PRODUCTION.yaml wording fix + PIMC deck-sort hardening — apply with the flip's governance touch.
- τ_p bracket + config broadening — DROPPED (Joshua 2026-07-06). value_norm survives as C4 only.
- Stepping-path Cython / de-objectify / compact-leaf — DEAD (break-even spike, `d3896c0`); do not re-propose without new premise.
- BACKLOG.md:375 ("heuristic prior blending at PUCT root") = the +148 ancestor that sat 6 weeks — grep BACKLOG before dismissing "small" ideas.

## Rough compute ledger (if everything runs): RR remainder ~1.5h · A1 ~4h · B1 ~1h · C2-C4 ~6h · A2 ~8h · D2 ~2h · B2 ~1 day · C1/C5/C6 ~1-2 days each ≈ **3-5 box-days** — matches "a few days at least, even if all null."

**Recommended execution order (cheap-decisive first, builds overlap compute):**
RR finish → **A1 (K=3)** ‖ verify B1 adapter → **B1 (Stage 0)** → **C4+C2** (cheap cells) ‖ build A2 launcher → **A2 (fair grid)** → flip signature + A3/D1 → **D2** → B2/C1/C5/C6 per gates.
