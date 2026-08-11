# A-small BUILD SPEC — ID-alpha-beta / deeper-K endgame module (FAIR-gated)

**Author:** recon subagent · **Date:** 2026-07-09 · **Status:** DESIGN (read-only recon; no code/heavy jobs run)
**Roadmap slot:** `docs/PROGRAM_ROADMAP_2026-07-07.md` "A-small (AFTER B, FAIR-gated)"; STATUS.md `Right now` block.
**One-line recommendation:** **Do NOT build make/unmake yet.** Run the cheap, *build-free* fair kill-gate first (`run_fair_grid.sh 3`, attended, ~few hours). The existing clairvoyant K-series predicts the fair winrate gain is ≈0 (winrate flat K=2→K=4 while only margin scaled); the make/unmake build is only justified if that screen fires ≥2σ.

---

## 0. The reframe that governs everything (READ FIRST)

The task brief said the champion "hands off to an exact **K≤4 alpha-beta** endgame solver." That is TRUE only for the **CLAIRVOYANT reference/measurement** agent, NOT the deployable FAIR agent. There are **two structurally-separate code paths** (`measurement/fair_handoff_audit/REPORT.md`, audited 2026-07-06):

| | CLAIRVOYANT (measurement/eval only) | **FAIR (deployable — what A-small must move)** |
|---|---|---|
| Where | `scripts/level2/eval_hybrid_handoff.py exact:K:clair`, regret harness | `src/carcassonne_ai/fair_agent.py` (`FairHeuristicPriorAgent` / `FairHeuristicMCTSAgent`) |
| Solver mode | `mode="clairvoyant"`, **alpha-beta ON** | `mode="marginalized"`, **alpha-beta OFF** (expectiminimax over the hidden bag) |
| Reads true deck order? | YES (cheating path; fair only in clair-vs-clair A/Bs) | NO — keys on `tuple(sorted(descs))` = bag multiset; bit-invariant to deck permutation (12/12 audited) |
| Handoff depth | K≤4 | **K≤2** (`fair_agent.EXACT_MAX_K = 2`) |

`endgame_solver.py:105` **asserts** `alpha-beta is clairvoyant-only (chance nodes break minimax cutoffs)`. **Consequence: "ID-alpha-beta+TT for a bigger K in the same time" is a clairvoyant fantasy in the fair regime** — exactly like full-game alpha-beta over a hidden deck. The FAIR endgame is a chance-node expectiminimax; alpha-beta cannot prune it. So of the three options the brief listed, **(c) is dead for the deployable agent.** The only fair lever is a **faster/lower-RAM MARGINALIZED solver** (option (a): deeper K via make/unmake). Option (b) "earlier handoff" is not a lever — K=2 is both the marginalized tractability frontier and the L2-3 band the marginalized ground truth is validated on (`fair_agent.py:89-92`).

---

## 1. What the CURRENT exact-K endgame handoff actually does

**Solver** (`scripts/level2/endgame_solver.py`, 290 lines, pure CPU, no net):
- Leaf value = REAL final score-diff `flat_base_score(state,0)` (exact farm scoring), P0 maximizes / P1 minimizes.
- `mode="clairvoyant"`: minimax over the KNOWN real future deck; **alpha-beta available** (`_value_ab`, fail-soft, TT bound flags `_EXACT/_LOWER/_UPPER`).
- `mode="marginalized"`: expectiminimax — each post-draw board goes through a **CHANCE node** (`_chance`, lines 172-186) that marginalizes the remaining-bag multiset (group by tile type, weight by count). **No alpha-beta** (chance nodes have no cutoff bound).
- **TT: yes.** EXACT-value memoization. Key = **blake2b-128 digest** of (`string_representation`, deck-order[clair] | sorted-bag-multiset[marg]) — compact key deployed `6f9dd08`, bit-identical incl. node counts, ~140× per-entry shrink. `CARCASSONNE_TT_CAP` env freezes the table at N entries (correctness-neutral memory valve; ~7.8× node inflation — NOT a throughput fix).

**Deepcopy-based, NOT make/unmake.** `_clone_with_tile` (line 77) does `copy.deepcopy(board.state)`; every child via `game.get_next_state(board,a)` deepcopies. **The TRANSIENT deepcopy churn in `get_next_state` is the RAM driver, not the TT** — a hard K=4 monster reaches ~10.6GB of which the TT is only ~0.04GB (DECISIONS 2026-06-21, CL-027). Compact keys therefore bought only ~1.5×.

**Trigger / latch** (`_MarginalizedHandoff.move`, `fair_agent.choose_action:267`): latch on the FIRST **TILES-phase** decision with `k_remaining ≤ K` (`k = len(deck) + (next_tile is not None)`). One-way (k monotone non-increasing), turn-atomic (boundary tile + its meeple both solved). `BudgetExceeded` → fall back to the fair PIMC move for THAT decision only, stays latched. **Audit (20 fair games):** exact solver fires only at **k=1 (20/20) and k=2 (20/20)**; every k≥3 decision is PIMC; 40 solves, 100% `marginalized|ab=False`, 0 clairvoyant. So today ≈**1–2 exact moves/game** at the very end of a ~72-tile game.

**Cost curve** (CLAIRVOYANT+AB, DECISIONS 2026-06-24 + memory `reference_exact_solver_eval_infra`; `measurement/exact_endgame_hybrid/solver_bench_by_k.json`): **K2 ~5s, K3 ~80s, K4 ~6min/game.** RAM: solver TT ~1–2GB/worker on hard K=4; **W=18 OOMed local's 42GB and took the session down.** carc-orch is **INCOMPATIBLE at K≥4** (minutes-long solves starve the SHM server → 60s timeout → BrokenServerError → eval crash) → K≥4 runs net-on-CPU, size **W ≤ RAM/~2GB** or use `CARCASSONNE_TT_CAP`. **⚠️ MARGINALIZED (the fair path) is MORE expensive than these clairvoyant+AB numbers** — chance-node branching over the whole bag multiset AND no pruning — so fair K=3/K=4 is strictly harder than the numbers above.

---

## 2. What A-small would ADD (and the real lever)

- **(a) Deeper fair K (K=3–4 marginalized) via make/unmake — THE ONLY REAL FAIR LEVER.** Replace per-node `deepcopy(state)`+`new Board` with incremental **apply/undo** on one mutable state (push diff → recurse → pop). Removes the ~5–7GB/worker transient → monsters shrink to ~TT-size (~0.1GB compact) → uncapped W becomes real; ~3–5× per-solve speedup. This is the prerequisite for fair K≥3 at scale AND for K=5 (BACKLOG 2026-06-21).
- **(b) Earlier/better handoff — NOT a lever.** K=2 is the validated marginalized frontier.
- **(c) ID-alpha-beta+TT to reach larger K in the same time — DEAD in the fair regime** (alpha-beta is clairvoyant-only; §0). ID-alpha-beta+TT survives ONLY as roadmap **C6** (full-game *clairvoyant* alpha-beta), which the roadmap explicitly ranks **below** A-small "given the ~156 tax" — a clairvoyant-regime bet.

**Is make/unmake already partially built? NO (for the solver).** The engine has `StateUpdater.apply_action_inplace` / `Game.apply_action_inplace` (`game_wrapper.py:419`, used by `mcts.py`, `selfplay.py`, `rule_based_player.py`) but it is **apply-only — there is no `undo`/`unmake`** (grep: 0 hits for `undo`-state-restore in the engine; `mcts._undo_vloss` is virtual-loss bookkeeping, unrelated). The solver does NOT use `apply_action_inplace` at all — it deepcopies via `get_next_state`. So solver make/unmake is a **fresh build** (BACKLOG: "Empty worktree — needs a fresh start"; STATUS item 5: "~week eng"). Scope: **helps the solver family ONLY, not production MCTS** (which runs `flat_leaf`, not the object solver).

---

## 3. FAIR-HEADROOM argument + the cheapest experiment

**The headroom question is mostly already answered — negatively — by the clairvoyant K-series** (DECISIONS 2026-06-24, `results.csv exact{2,3,4}_vs_*`):

| K | Δ score-margin vs h3200 | winrate (deck-paired) |
|---|---|---|
| 2 | +0.65 (z+4.5) | 0.526 (z+1.05 **NS**) |
| 3 | +1.26 (z+7.3) | 0.537 (z+1.50 **NS**) |
| 4 | +1.94 (z+2.8) | 0.568 (z+1.44 **NS**) |

**Exact endgame is PROVABLY better on margin and scales with depth, but WINRATE is flat/NS at every K** (empirical margin→winrate slope ~1.6%/pt). Standing decision: *"sharpens the ruler, does not beat it on winrate… STOP at K=4 (K≥5 not worth it — winrate flat at K≤4)."* **Crucially, clairvoyant endgame value is an UPPER BOUND on fair endgame value** (it sees the deck). If clairvoyant K=4 can't move winrate over K=2, fair K=4 can't either. And the ~120-elo tax that A/C target is a **MIDGAME** phenomenon that **persists across a 7× sims range and does NOT close with search** (CL-048) — a deeper endgame does not touch it. The champion already banks the low-tax endgame at K≤2 fair.

**Cheapest fair-gated experiment — BUILD-FREE (the harness already exists).** `scripts/classical_search/eval_fair_puct.py` + `run_fair_grid.sh` already sweep the fair marginalized endgame depth K (deck-paired vs the fixed h800 CL-022 rung, CRN, `--no-results-csv`, `nice -n 19`, `CARCASSONNE_TT_CAP` honored, BudgetExceeded→PIMC RAM safety, K≥3 prints an ATTENDED-ONLY warning). The `--exact-k` CLI arg + `_MarginalizedHandoff(K)` already take K>2 (`FairHeuristicPriorAgent.exact_max_k` is a knob). **A-small's screen requires ZERO new code.**

- **Stage A0 — FREE, no run.** Accept the clairvoyant-series upper bound: fair K=3–4 winrate gain ≤ clairvoyant's ≈0. If accepted → **DECLINE A-small** with no compute. (Honest cheapest answer; matches the existing STOP-at-K=4 decision.)
- **Stage A1 — cheap direct fair screen (attended, NO build).** Fair K=3 vs the deployed K=2, same decks:
  ```
  # baseline (already deployed config; may already exist on the share as K=2):
  scripts/classical_search/run_fair_grid.sh 2 200 13000000000 8 344 14 fair
  # A-small screen — K=3 fair marginalized (ATTENDED, low W, watch RAM):
  CARCASSONNE_TT_CAP=200000 CARCASSONNE_EXACT_BUDGET=1000000 \
    scripts/classical_search/run_fair_grid.sh 3 200 13000000000 8 344 6 fair
  ```
  Same CRN decks → paired Δwinrate isolates the K=2→K=3 endgame. **K=2-safe for unattended; K=3 is attended** (marginalized, no AB): capped `EXACT_BUDGET` + `TT_CAP` keep BudgetExceeded→PIMC bounding RAM; low W (≤6), net-free, `nice -n 19`. Cost ~few hours. **GATE:** paired winrate z ≥ ~2 at n=200 → consider Stage A2; else **KILL A-small.**
- **Stage A2 — only if A1 fires: build make/unmake, then confirm.** Make fair K=3–4 tractable at scale; n=400 fair confirm + a K=4 fair rung, gated ≥2σ paired winrate vs the D0 fair ruler (`fair_ladder_*`).

---

## 4. BUILD COST — make/unmake (only reached if A1 fires)

- **Effort:** ~3–5 days / "~week eng" (BACKLOG 2026-06-21; STATUS item 5). Fresh start, empty worktree.
- **Change:** incremental apply/undo on one mutable engine state inside `endgame_solver` (push the transition diff, recurse, pop) reusing the trusted engine transition — NOT a new rules impl.
- **Profile after:** transient collapses ~5–7GB → ~TT-size (~0.1GB compact); ~3–5× per-solve speedup; W=ncores uncapped becomes real; unlocks fair K=3–4 and K=5 feasibility.
- **Risks:**
  1. **OOM (history-backed).** K≥3 marginalized is the RAM/OOM regime; W=18 K=4 OOMed 42GB + downed the session; carc-orch incompatible K≥4. Even *with* make/unmake, first K=4 fair confirm stays **attended, net-on-CPU, W ≤ RAM/~2GB**.
  2. **Correctness (silent).** undo must bit-exactly restore ALL engine state (open_positions adjacency, centroid sum_row/sum_col, farm union-find, phase/current_player). A subtle restore bug silently corrupts a *ground-truth* solver. **Mitigation:** the AB-gauntlet pattern — assert make/unmake solve == deepcopy solve bit-for-bit (value + node count) on the frozen K2/K3 suites before any use.
  3. **Low ROI (the real risk).** §3 says the expected fair winrate payoff is ~0; a week of attended, OOM-prone build for a margin-only, outcome-neutral gain that doesn't touch the tax.

---

## 5. RECOMMENDATION

**Decline the make/unmake build up front; run the build-free fair kill-gate (Stage A1) only if Joshua wants a direct fair number; otherwise Stage A0 closes it.**

Reasoning: the endgame is genuinely the low-tax regime and the naturally fair-valuable place for exact search — but (1) the champion **already** exploits it at K≤2 fair; (2) the clairvoyant K-series (an upper bound on fair value) already proved deeper exact endgame is **margin-positive but winrate-flat / outcome-neutral** through K=4, with a standing STOP-at-K=4 decision; (3) the ~120-elo prize is a **midgame** tax that a deeper endgame provably does not touch (CL-048); (4) alpha-beta — the "same-time-bigger-K" idea — is **clairvoyant-only** and unusable fair. Against that, A-small costs a 3–5 day attended, OOM-prone build.

**Staged, cheapest-informative-first:**
1. **A0 (free):** cite the clairvoyant K-series upper bound + STOP-at-K=4 → decline, zero compute. Recommended default.
2. **A1 (few hrs, attended, no build):** `run_fair_grid.sh 3` vs deployed K=2, CRN n=200, capped budget/TT, W≤6. **KILL-GATE: winrate z<2 → stop.** This is the only spend worth making before any build.
3. **A2 (only if A1 fires ≥2σ):** build make/unmake (§4) with the bit-exact gauntlet, then n=400 fair confirm + K=4 rung gated ≥2σ vs the D0 fair ruler.

Do **not** pursue full-game/ID-alpha-beta (roadmap C6) for the deployable agent — it is a clairvoyant-regime bet the roadmap already ranks below A-small given the tax. If appetite exists for a fair strength lever, **C-cheap** (deck-aware value head to shrink the ~120 midgame tax) and **E4** (human-anchor, the actual fair exam, config already built) are higher-EV than A-small.

### Files
- **Create (only in A2):** make/unmake apply/undo inside `scripts/level2/endgame_solver.py` (or a sibling `endgame_solver_mu.py` behind an env flag) + a `tests/` bit-exact gauntlet vs the deepcopy solver on the K2/K3 suites.
- **Reuse as-is (A1, no edits):** `scripts/classical_search/eval_fair_puct.py`, `run_fair_grid.sh`, `src/carcassonne_ai/fair_agent.py` (`exact_max_k` knob), `endgame_solver.solve(mode="marginalized")`.
- **Evidence read:** `measurement/fair_handoff_audit/REPORT.md`, `measurement/exact_endgame_hybrid/EXACT_ENDGAME_HYBRID_REPORT.md`, DECISIONS.md 2026-06-24 (STOP-at-K4) + 2026-06-21 (make/unmake lever, CL-027), `results.csv` `exact{2,3,4}_*` / `fair_ladder_*` / `clair_ladder_*`, BACKLOG.md 2026-06-21.
