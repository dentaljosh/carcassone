# PROTOCOL_002 — residual-net (scale 0.25) vs iter_11 head-to-head

> Pre-registered BEFORE the run (governance/PROTOCOL_TEMPLATE.md). Stored separately from results so the
> hypothesis cannot be rewritten after the outcome is known. Fill ONLY the RESULT section at completion.

- **experiment_id:** PROTOCOL_002 / `cleaneval_h2h_residual_rs025_vs_iter11`
- **decision being made:** which net is the **production agent** — iter_11 (CL-002, *Supported*) or the residual net @scale 0.25 — and the agent-comparison half of **CL-005** (residual → production). The residual net is also the net we would warm the Track-B flywheel from, so "is it actually the stronger agent?" matters beyond production.
- **primary hypothesis:** the residual net @0.25 **beats** iter_11 head-to-head. Indirect evidence: vs the common matched-v2.7 yardstick, residual@0.25 = +99.6 vs iter_11 +89.7 (≈ +10 elo edge), and the residual value-head marginal is now clean-confirmed (+37.6, CL-004).
- **competing hypotheses:**
  - (H0) tie — the residual net's **policy is weaker** than iter_11's (residual scale-0 = +62.0 vs iter_11 +89.7 vs the same yardstick), so its value head (+37.6 marginal) only roughly compensates; head-to-head could be a wash.
  - (H-iter11) iter_11 wins — non-transitivity (just observed) means vs-common-opponent does not guarantee the direct result; iter_11's stronger policy could dominate in direct play.
- **single variable changed:** the agent — NEW = residual.pt @ `--new-leaf-residual-scale 0.25` (value head ON), OLD = iter_11.pt @ residual-scale 0 (pure v2.7 policy). Both NeuralMCTS, same v2.7 leaf family.
- **held fixed:** sims=200, leaf env CAP=12 DROP_THREE_OPEN=1, c_puct matched (3.0 both), clean 1e9 seeds, deck-paired seats, n=400.
- **primary metric:** head-to-head elo ± σ from the residual net's perspective (deck-paired).
- **secondary metrics:** avg score diff; W/L/D.
- **sample size:** **n=400 paired** (Joshua's call, ~30 min on 3 boxes).
- **pairing / seed design:** deck-paired (same seed both seats); `--seed-start 1e9` clean namespace; deck hashes.
- **top-up rule:** PRE-REGISTERED — if the margin lands 1.3 < z < 2 at n=400, escalate once to n=1500 (the expected effect is small, see power note); no repeated peeking.
- **stopping rule:** fixed n=400 (then n=1500 only under the top-up rule); summarize only at target n.
- **⚠️ POWER NOTE (pre-registered):** the *expected* edge from the vs-common-opponent gap is only ~+10 elo, which n=400 (±17) **cannot resolve** (< 1σ). So n=400 is a **screen**: it resolves only a **larger direct edge (≥35 elo / 2σ)**, e.g. if non-transitivity makes the head-to-head diverge from the indirect prediction. A null at n=400 means "no large edge either way," NOT "they are equal" — that needs n≈1500.
- **success threshold:** residual beats iter_11 by **≥ +35 elo / 2σ** → the residual net is the production agent; CL-002 updates (iter_11 no longer strongest established), CL-005's agent-comparison gate passes.
- **failure threshold:** iter_11 beats residual by **≥ +35 elo / 2σ** → iter_11 stays the production agent; CL-005 weakened (the value head doesn't make the residual net the better *agent* despite the +37.6 marginal).
- **what each outcome PERMITS:** a residual win PERMITS naming it the production agent + the Track-B warm-start net. An iter_11 win PERMITS keeping iter_11 as production + warm-start. A null PERMITS recording "no large direct edge; ~equivalent at n=400."
- **what each outcome FORBIDS:** ANY outcome FORBIDS claiming Track-B progress / superhuman (this is an **in-ecosystem agent comparison**, not out-of-lineage — CL-011 unaffected). A residual win FORBIDS auto-fold-in to production without the clean-seed **out-of-lineage** check PROTOCOL_001 still requires for CL-005. A null FORBIDS claiming the two nets are *equal* (underpowered).
- **estimated compute cost:** ~400 games (paired), 3-box, sims=200, ~30 min wall. EVAL ONLY (no training).
- **links to manifests / raw outputs:** run dir `/mnt/c/carc-shared/h2h_runs/residual_rs025_vs_iter11_s200` (RAW); launcher `scripts/run_h2h_residual_vs_iter11.sh`; harness `scripts/eval_iter_head_to_head.py` (per-side `--new/old-leaf-residual-scale`); manifest.json (evaluator block, both sides) lands in the run dir.

---

## RESULT (2026-06-08 02:48 EDT — auto-chain; independently re-tallied)

| metric | value | z | verdict |
|---|---|---|---|
| head-to-head elo (residual − iter_11), n=400 paired | +29.6 ± 16.7 | 1.77 | in (1.3, 2) band → escalated |
| head-to-head elo (residual − iter_11), **n=1500 paired** | **+34.2 ± 8.5** | **4.00** | **residual_wins** |

**Top-up fired?** YES — n=400 z=1.77 landed in the pre-registered (1.3, 2) escalation band → auto-escalated to n=1500 (no peeking; the rule was fixed in advance). **Verdict: `residual_wins`** — z=4.00 clears the ≥2σ bar 2× over; the point estimate **+34.2** sits right at the pre-registered +35-elo success threshold (well within ±8.5). W/D/L = **815/17/668 over 750 decks**; avg score margin **+0.41 pts/game** — a thin *win-rate* edge (wr 0.527), not domination. Independently re-tallied from the raw JSON — exact match to the orchestrator's number (no trust required).

**Transitions:**
- **CL-002** (*iter_11 is the strongest established policy*) — its named falsifier ("a head-to-head in which the residual net wins beyond noise") FIRED → **Disfavored**. The residual net is the stronger agent.
- **CL-017** (new) — *residual net @0.25 is the strongest established agent* → **Supported** (in-ecosystem; +34.2/z=4.0 direct, n=1500).
- **CL-005** (*residual → production*) — the agent-comparison gate **PASSES**, but production fold-in stays **FORBIDDEN** until the clean-seed **out-of-lineage** check (per "what each outcome FORBIDS"). That odometer is now being produced by the flywheel's iter0 odometer (best vs heur@800-v2.7, clean seed 1.5e9) → resolve CL-005 from `flywheel_residual_v2/odometer.csv`.
- Result row: `results.csv: cleaneval_h2h_residual_rs025_vs_iter11_s200_n1500`.
