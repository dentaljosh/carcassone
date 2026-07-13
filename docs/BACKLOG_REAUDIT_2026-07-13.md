# BACKLOG RE-AUDIT — 2026-07-13 (Fable strategy pass)

> **STATUS: ADVISORY AUDIT, point-in-time 2026-07-13. Nothing here is actioned; Joshua promotes items per the [BACKLOG](../BACKLOG.md) rule.** Every deferred idea in [BACKLOG.md](../BACKLOG.md), the [roadmap](PROGRAM_ROADMAP_2026-07-07.md) Parking lot, and Track E was re-scored against the **current** premises, not the ones it was written under. Prompted by the +148 lesson: the champion flip was a BACKLOG line ("heuristic prior blending at PUCT root", BACKLOG.md:375) that sat 6 weeks.

**Premises used for scoring (all changed in the last two weeks):**
1. **Champion = CLASSICAL** — `HeuristicPriorAgent` PUCT + heuristic-leaf priors + reuse + the curve125 v2.9.2 leaf ([PRODUCTION.yaml](../governance/PRODUCTION.yaml); CL-043/044/051). No learned net anywhere in the champion.
2. **Ruler = the D0 FAIR sub-ladder** (CL-046). Fair (blind PIMC) is the currency; clairvoyant is a demoted dev screen. Fair strength **scales with sims and is not saturating** (+68/~4σ for the top doubling) → *any* equal-time search-efficiency win is now a fair-strength win.
3. **Learned-value route CLOSED at-scale** (CL-038/039/042/049/050; 8 value-inertness nulls incl. the properly-shaped C-cheap v2 residual). Scope guard: the closure covers 7M-net / ≤5 iters / ≤400 games-iter / warmstart / sims≤200 — **NOT** 10–100× scale, Gumbel, or different architectures.
4. **The ~120-elo fair clairvoyance tax persists and does not close with search** (CL-048). C-cheap (the learned tax-attack) is dead (CL-050) → as of today **no live lever attacks the tax**.
5. **E4 (human exam) is the standing NEXT** but Joshua-deferred ("no human yet"). This shortlist is what's worth running while E4 waits.

---

## 1. TRY SOON — ranked by fair-strength-EV / cost

### T1. k_dets marginalization bracket on the fair ruler (~0.5 box-day) — the one live tax lever
The E2 leftover ("fair midgame tax probe, K-sweep") respec'd onto the D0 harness. **CL-046 explicitly names it the untested fair lever:** k_dets=8 was held FIXED in every fair measurement; only sims/det was ever scaled. With C-cheap dead (CL-050), *sampled* marginalization (more/better determinizations) is the only remaining way to attack the ~120 tax. Cells: k_dets {4, 16, 32} × sims/det at **fixed total 2752** (vs the cached k8×344 baseline), plus the compute-matched depth-vs-width cell **k16×344 @5504 vs the existing k8×688 (+149.3)**. Existing `scripts/classical_search/eval_fair_puct.py` + cached CRN decks; n=200/cell. Premise-check: never measured (no `*_kd{4,16,32}*` rows in results.csv). Prior ~30–40% of ≥+20 fair at deploy budget; even a null is valuable (it cleanly kills the sampled-marginalization axis and sharpens "the tax needs learning" for any future reopen). Directly sets the E4 deploy config.

### T2. Second C5 wave — NEW leaf *terms* (not reweights) through the S1→S3 pipeline (~1–2 d dev + ~1 box-day evals per wave)
CL-051 is the precedent: a term-*shape* change (meeple curve ×1.25) fired **+66.8 clair / +48.8 fair** after every reweight died, and leaf changes **transfer fair by construction** (same LeafConfig in every determinization — no CL-044-style clair-only risk). The C5 harness (`--cand-leaf-json`, per-side leaf_hash manifests) makes any leaf A/B ~1.6 box-h per n=100 screen cell. Two untested term-shapes remain from the 2026-05-16 lit review, both adjacent to the axis that just fired (meeple economy):
- **Stranding-risk meeple weighting** (weight committed meeples by completion probability + reserve-meeple option value) — the curve just proved the leaf under-prices meeple commitment under PUCT.
- **Farm majority-flip anticipation** (a 2nd farmer that only *ties* a contested field ≪ one that flips majority) — never tested in any form.
- (Third, low prior: *targeted* denial on near-complete large opponent cities — but both C5 opp_cap wings were the worst cells in the screen (−59.6/−66.8), so the denial direction starts discounted.)
Pre-register S1 screen → n=400 clair confirm → mandatory S3 fair gate, exactly the CL-051 template. Dev cost is real (new terms must land in the Cython float leaf path). Prior ~25–35% one axis fires. **Do NOT include deck-aware closure — see D-list (killed 3×).**

### T3. Joint Optuna/TPE over the champion's knobs, clair-screen + fair-confirm gate (~2 box-days)
The 2026-05-27 backlog entry, premise now FLIPPED TWICE. The 2026-05-28 "stop tuning eval knobs, rounding error" verdict ([DECISIONS](../DECISIONS.md) 2026-05-28) expired with the champion: C5 proved the knob landscape moved under PUCT (+67 from one 1-D axis), and **all C5/Track-C sweeps were 1-D-at-a-time** — interactions (curve × closure_p × bonus_cap × c_puct × tau_p; e.g. pclose120 screened +34.9/z1.0 *pre*-curve125, untested since) are unsampled. Wrap the existing rr_puct harness as the objective: TPE, ~20–30 trials, n=100 CRN clair screens (~1.6 box-h/cell), SuccessiveHalvingPruner (the multi-fidelity backlog entry folds in), then n=400 clair confirm + the CL-051 fair gate for any winner. Infra mostly exists (May study wrapper, results.csv export). Prior ~30% of ≥+30 clair beyond the current config, with good fair-transfer odds for leaf-side knobs. Run *after* T1/T2 so the search space includes their winners.

### T4. Correctness/governance hygiene bundle (~2–4 h, zero compute — do in one sitting)
All flagged, none landed: **(a)** Phase 0.1 PRODUCTION.yaml wording fix + PIMC deck-sort hardening (roadmap Parking lot; proposed by the fair-handoff audit, still unapplied); **(b)** `meeple_k: 2.0` INERT key in PRODUCTION.yaml (C5 design finding — config-hygiene trap); **(c)** `deck_hash` omits the first drawn tile (provenance blind spot); **(d)** the 5-LoC abbots defensive assert; **(e)** stamp `value_target` into `.npz` metadata (matters again the day any training restarts). Cheap insurance on the measurement spine the whole program now leans on. (Track-D D1 ruler re-anchor + D2 rung compression are the bigger open governance items but are already queued on the roadmap — not backlog finds.)

### T5. Meeple-slot action dedup — census first (~2 h), build only if big (~1–2 d)
The 2026-05-14 entry, **resurrected by the regime change**: its deferral reason ("changes the policy-head shape, invalidates every checkpoint") is GONE — the champion has no policy head. Redundant same-feature meeple slots now cost pure search budget in a PUCT agent whose fair strength scales with effective sims (D0). The `_nodes` transposition table does NOT collapse them (different meeple position → different board string). Step 1 is a free census: measure the duplicate fraction at champion roots; build the decode-time dedup only if duplicate visit-mass ≥ ~10% of meeple-phase budget. EV honest: ~+5–15 fair elo, needs n=400 to resolve — mid-tier, census decides.

### T6 (optional, E4 prep). Hand-curated tactical probe set (4–6 h human labeling, zero compute)
Phase-4-era entry, still live and now E4-shaped: 30–50 labeled tactical positions run against the *fair* champion exposes its blind spots before a human does, and doubles as Phase-5 analyzer material. Needs Joshua's labeling time — schedule against E4.

---

## 2. RESPEC-THEN-CONSIDER (premise changed; redesign before actioning)

| Idea (BACKLOG date) | What changed / what the new version is |
|---|---|
| **No-warmstart Gumbel flywheel (E3)** | See §4 — gated pilot, don't fund the full run now. |
| **B3 capacity-probe re-run** (roadmap) | Still the right ~1-laptop-day gate for ANY scale bet (§4 step 1). Memory-safe ~2GB subset; capacity jobs banned local. |
| **E1 win-prob endgame objective** | Prior lowered by the winrate-flat clairvoyant K-series (A-spec decline 2026-07-09) + the win-shaping NULL (`v210_winshape_*`). Re-open only if E4 shows close-game losses; the re-spec is a win-prob backup inside the *marginalized fair K≤2 solve*, not the leaf. |
| **Adaptive-compute escalation** (06-29) | Strength CLOSED (CL-035) — do not re-propose as strength. Efficiency-only version was measured on the OLD random-expansion search; would need re-derivation under PUCT+reuse; expected effect below game resolution. Low. |
| **CPython 3.14 bench** (06-12) | Different mechanism from the dead stepping-path Cython (interpreter-wide ~5–10%). Under premise 2 a throughput win is now a small fair-strength win (~+5–10 elo at deploy). Single-box bench first; venv-rebuild + torch-revalidate cost across 3 boxes. Low-mid. |
| **Shortened-game screening** (05-28) | Unchanged risk (endgame-driven findings, and the leaf/endgame matter MORE for the classical champion). Only if a 50+-ablation program materializes (e.g. T3 grows into one). |
| **Flywheel-conditional infra bundle** | HOSTS knob, telemetry stall-window, D9 `.failed` sidecar, claim-tail re-steal, replay-window A/B, async flywheel, symmetry-aug usage, league/specialist portfolios, KataGo planes+aux heads, bigger-net arch, curriculum staging, 2-ply/MCTS warmstart labels — ALL premised on a training loop. Park as a named bundle; they fold into the E3 spec if a flywheel is ever funded (D9 + stall-window are day-1 prerequisites of any multi-iter run). Note C4a farm-planes was already REFUTED by oracle probe (DECISIONS 2026-06-04). |
| **remote_eval_bridge stale-response bug** (05-21) | Bridge unused (Zenbook dead). Keep as a hard pre-deploy gate if the bridge ever returns. |

---

## 3. DEAD / ALREADY DONE (anti-rediscovery — do not re-propose)

- **Heuristic prior blending at PUCT root** — FIRED: it *is* the +148 champion (CL-043). Done.
- **Tile-counting / deck-aware closure P** — killed 3×: Step-3b hard gate 45% wr (DECISIONS 2026-05-2x, "tile-counting closure probability"); v2.10 `bag_close` −6.1 n=400 (2026-07-05 arc); `c5_bagclose` −3.5 under PUCT.
- **Leaf reweights / caps / blanket or capped denial** — v2.10 CLOSED ("game-tuned leaf") + C5 S1: cap5 0.0, cap12 −13.9, oppcap4 −59.6, oppcap12 −66.8. Only new *term shapes* remain live (T2).
- **Endgame depth boost / deeper endgame search** — superseded by the exact-K handoff; A-small DECLINED 2026-07-09 (no fair endgame winrate headroom; the tax is midgame, CL-048). Includes **make/unmake solver** as a strength lever (3–5 d OOM-prone build, ~0 fair ROI — A-spec). Make/unmake survives only as a K≥5 *measurement* prerequisite if Track-D D3 ever needs it.
- **Stepping-path Cython / de-objectify engine / compact leaf / numba** — DEAD (break-even spike `d3896c0`; roadmap Parking lot: "do not re-propose without new premise"). Cython leaf + window-offset + encode_board_cy: FOLDED (2026-06-17, `1b55721`). `CANONICAL_BONUS_SUM`: production Cython float leaf is fsum-canonical — done. flat_leaf residual enum-key swap: mooted by the Cython fold.
- **Transposition table in MCTS** — exists (`_nodes`, inherited by `HeuristicPriorAgent`); C2 dedup fixed 2026-06-02.
- **Search self-consistency (sims 200 vs 1000)** — superseded: D0 measures search-scaling directly; teacher-τ + the 4.75% midgame-disagreement diagnostic answered the policy-headroom question (roadmap B1/B1a).
- **Distillation (small student)** — premise gone (no net in the champion; phone bench: classical h1600–h3200 fits a phone). Policy-distillation separately NOT FUNDED (B1a gate failed).
- **MuZero / learned dynamics** — no surviving premise; the engine is exact; 6-week bet against an 8-null ledger.
- **ANE / Core ML** — no net to accelerate.
- **Transformer trunk** — not a standalone item; it's an arch cell inside the §4 funding decision.
- **Eval-gauntlet GPU batching** (05-31) — superseded (orch is the default for neural work; the champion's evals are pure-CPU).
- **Multi-box sharding** — done in practice (3-box work-stealing). **PreToolUse hooks** — built (`390b482`). **River regression tests** — done, and River itself dropped. **Phase-5 determinization** — built (`fair_agent.py` PIMC). **D13/D1/D16/D15 review items** — resolved (see BACKLOG inline stamps).
- **τ_p bracket / config broadening** — DROPPED (Joshua 2026-07-06); C5-S4 re-confirmed τ5.
- **Gumbel as a play-strength lever** — CLOSED (CL-052 clair-only selector; top-m sampling −81/−98). Only its *training target* survives, inside §4.

---

## 4. SPECIAL FOCUS — the no-warmstart AlphaZero flywheel (E3)

**Is it outside the CL-039 closure? YES, formally.** The scope guard (CL-039, autopsy §"scope", CL-042) restricts the closure to 7M-net / ≤5 iters / ≤400 games-iter / **warmstart** / sims≤200, and explicitly does "not [make] a claim about 10–100× scale, Gumbel search, or fundamentally different architectures." From-scratch was never run (STATUS 2026-07-06: the two never-tested cells = tabula-rasa and bigger nets); Gumbel was "never examined" as a *training* recipe (autopsy row 5). A from-scratch, larger, Gumbel-trained attempt is the enumerated un-sampled cell.

**But formally-open ≠ good bet. The honest prior stack:**
1. **Eight value-inertness nulls**, ending with C-cheap v2 (CL-050): a properly-shaped residual value that *passed* its offline gate and still converted to ~0 online. The offline→online disconnect is the program's most reproduced finding.
2. **The leaf is a freakish local ranker** (solver-τ 0.615 vs 0.02–0.15 for every net tried) and fair deploy (pooled-Q) *needs* local ranking — the exact thing learned values keep lacking.
3. **Policy headroom is measured small**: real midgame disagreement champion-vs-leaf-1-ply = 4.75% « the 20% funding bar (B1a); deepteacher = TIE (CL-042 M1); policy gains wash out at depth (sims-washout).
4. **The bar moved up ~200 elo**: the product must beat a champion that is +81 fair vs h800 at deploy and still scaling (+149 at 2×) — and it must beat it FAIR, where a clairvoyantly-trained net also pays the ~120 tax, while fair-trained self-play multiplies gen cost by ~k_dets.
5. External base rate: academic attempts at superhuman Carcassonne have stalled since 2020 (CLAUDE.md charter).

**Strongest version worth running (if ever):** from-scratch Gumbel-AZ — ~20–30M params (widen `policy_project` 4→32: the real capacity lever, the trunk is only ~1M of the 7.4M), KataGo-style planes + aux heads + rotation aug (all designed/built, flywheel-conditional bundle §2), `score_diff_wide` + win-prob heads, Gumbel n=32–64 root sampling with **completed-Q policy targets** (the one Gumbel piece CL-052 left alive — makes low-sims training sound), ≥5k games/iter × 30–50 iters, clairvoyant gen for cost with **fair-ladder grading at every checkpoint** (D0 rungs, CRN). Realistic cost: **multi-box-weeks (order 50–100 box-days) or cloud spend.**

**Cheapest kill-or-confirm pilot (gated, in order):**
1. **E4 first** (already the program's NEXT): if the current classical champion already beats strong humans fair, the flywheel is unnecessary for the charter goal; if humans crush it, the *gap size* prices the moonshot vs just scaling fair search (the demonstrated D0 lever).
2. **B3 capacity slope** (~1 laptop-day, memory-safe subset, already on the roadmap): no f128b6-over-f64b4 solver-τ slope → the scale premise dies for ~free → DON'T run the flywheel.
3. Only then: a **5–8-iter from-scratch Gumbel mini-flywheel** (~2–5k games/iter, ~6–10 box-days) with pre-registered kill gates on the D0 fair ladder (kill unless a clean monotone climb crosses ~h800-fair by iter ~8 with trajectory toward +81).

**Verdict: DON'T-BOTHER now / PILOT-FIRST only behind the E4→B3 gates.** Prior ≈ **10%** that a full run ever beats the classical champion fair at matched deploy compute (≈25–35% it clears h800-fair, which is still ~-80 below the champion). It is the only remaining path to "a *learned* component exceeds the heuristic" — but per the currency correction that is no longer the success condition; *the full agent beats humans, fair* is, and the classical champion + fair-search scaling + T1/T2 attack that condition at ~1% of the cost. Keep E3 as "re-spec, build-only-then-stop" — do not fund the run on today's evidence.

---

*Maintenance: any item promoted from here lands on [PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md) per the close-out rule. Kills cited above live in [DECISIONS.md](../DECISIONS.md), [CLAIM_REGISTRY.csv](../governance/CLAIM_REGISTRY.csv) (CL-035/038/039/042/043/044/048/049/050/051/052), and [results.csv](../experiments/results.csv) (`c5_*`, `v210_*`, `fair_*`, `rr_puct*`).*
