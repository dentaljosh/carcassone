# v2.8 candidate patch proposals (Phase 2)

> 4 patches, each **small + independently toggleable**, chosen ONLY from the taxonomy-justified
> mechanisms (M1 farm, M2 completion, M3 meeple, M4 denial). M5 scarcity / M6 phase are **held**
> (taxonomy: weak/speculative). Target cases cite [V27_FAILURE_CASES.csv](V27_FAILURE_CASES.csv).
> Two patches need new code (`v28_farm`, `v28_meeple`); two reuse existing LeafConfig knobs as named
> v2.8 variants (`v28_completion`, `v28_denial`). **None alters v2.7** — all are opt-in cfg fields
> defaulting OFF, forcing the engine path (the flat fast path does not implement them).
>
> **Autopsy contract (per the addendum):** a patch survives only if it improves its *intended target
> subset* without broad degradation AND the line-autopsy/counterfactual supports the *named mechanism*.
> Elo gain with an unsupported mechanism → labeled "empirical gain, mechanism unclear," not a clean
> survivor.

---

## Patch 1 — `v28_farm` (farm_final_value_v1)  ·  M1, strongest evidence

- **Hypothesis.** v2.7 over-credits its farm-growth bonus on **contested fields the opponent will
  win**. v2.7 adds `+3×P(closes)` for each incomplete city adjacent to a farmed field, credited to
  *every* player who farms it — but at final scoring only the **majority farmer** scores those cities.
  On a field where the opponent holds strict farmer majority, v2.7's `+3×P` to `player` is spurious
  (and symmetric double-credit roughly cancels in `bonus_self − bonus_opp`, smearing the true owner's
  edge).
- **Exact intended signal.** Gate the farm-growth bonus by **current field farmer-majority**: credit
  `+3×P` for an incomplete adjacent city only if `player`'s farmer count on that field ≥ the
  opponent's (ties score per the engine's canonical all-tied rule). Strict opponent majority → 0.
- **Expected phase.** Endgame + late-mid (mature contested fields). Target bucket is endgame
  `structural-or-farm` (82) + midgame `structural/closure` farm-growth subset.
- **Possible failure modes.** (a) The base `count_final_scores` already prices *current* majority for
  *finished* cities, so the gain is confined to *incomplete* cities — small surface. (b) Tie semantics:
  must match the engine's tied-farmer fix (both score) or it will mis-gate. (c) Could under-credit a
  field where `player` is about to gain majority (rare; farmers don't move).
- **Search-duplication risk.** **Low.** Majority is a *static* board fact (placed farmers don't move);
  this is a leaf-value correction, not a lookahead. A 1-ply search would not recover it because the
  miscredit persists across the subtree.
- **Minimal implementation.** New `LeafConfig.v28_farm_majority: bool = False`. One helper
  `_field_owner_counts(state)` (one pass over both players' placed farmers → field_key → (c0,c1),
  cached on state). In `_closure_anticipation_bonus` farm-growth branch: skip the `p*3` add when
  `counts[opp] > counts[player]`. Force engine path when on.
- **Offline test (pre-eval).** Constructed position: a field with opponent strict farmer majority + an
  incomplete adjacent city. Assert v2.7 credits player `+3×P`; `v28_farm` credits 0; v2.7 unchanged
  when the field is player-majority.
- **Target cases (175 total; representative — full set = `candidate_patch` contains `farm_final_value_v1`):**
  `end::heur3200_s3502000016_k4`, `end::g3200000022_k2`, `end::g3200000130_k2`, `end::g3200000092_k2`,
  `end::g3200000111_k2`, `end::g3200000021_k2`, `end::hybrid_8_3200_s3503000031_k4`,
  `end::g3200000083_k3`, `end::g3200000090_k2`, `end::g3200000075_k2`, `end::greedy_s3500000004_k4`,
  `end::g3200000032_k3` (+ midgame `structural/closure` farm subset). Each has a stored `raw_path`
  full-position JSON for the line autopsy.

---

## Patch 2 — `v28_completion` (completion_timing_v1)  ·  M2, reuses deck-aware closure

- **Hypothesis.** v2.7's `closure_p={1:0.5, 2:0.2}` is a **fixed schedule independent of deck supply**.
  Late game it over-credits closures the deck can no longer finish (and the bonus then prices a
  point-grab that never lands). The continuous deck-aware ramp (`closure_continuous_slack`) scales
  P(closure) by how plentiful the usable supply is → correctly discounts unreachable closures.
- **Exact intended signal.** `P(closure) ×= supply_factor(supply, need, slack)` — the existing
  `_supply_factor` (Option-1 step 5). Variant tuned at a small `slack` grid {2, 3, 4}.
- **Expected phase.** Late-mid + pre-endgame (deck thinning). Target: midgame `completion/score-greed`
  (12) + the closure-timing share of `structural/closure` (112-case `completion_timing_v1` pool).
- **Possible failure modes.** (a) The midgame audit found bag/scarcity *raw features* τ≈0 — deck-
  awareness as a *leaf value* may also be inert. (b) Slack mis-tuning could over-discount legitimate
  closures and *lose* strength. (c) Interacts with caps.
- **Search-duplication risk.** **Medium.** A deep search partly discovers unreachable closures by
  rollout, so the deck-aware leaf may only help *shallow* search — must show it helps at `heur@200`
  AND ideally `heur@800`, else it's just cheap-search-imitation.
- **Minimal implementation.** **No new code** — `LeafConfig.closure_continuous_slack` already exists
  and already forces the engine path. v2.8 variant = a named config with `closure_continuous_slack=s`.
- **Offline test.** Late-game position where an open-2 city cannot be finished by the remaining deck:
  assert `v28_completion` bonus < v2.7 bonus (monotone reduction; mirrors existing
  `test_tile_counting_gate_only_reduces_bonus`).
- **Target cases (112):** `mid::greedy_s3500000027_K40`, `mid::iter8_s3501000016_K28`,
  `mid::greedy_s3500000009_K52`, `mid::heur3200_s3502000015_K10` (pre-endgame), `mid::iter8_s3501000010_K16`,
  `mid::greedy_s3500000015_K28`, `mid::iter8_s3501000025_K52`, `mid::hybrid_8_3200_s3503000015_K40`,
  `mid::hybrid_8_3200_s3503000022_K52`, `mid::greedy_s3500000001_K52` (+ full `completion_timing_v1` set).

---

## Patch 3 — `v28_meeple` (meeple_economy_v1)  ·  M3, recovery-scaled

- **Hypothesis.** v2.7 ignores meeple supply economy: a placement stranding a meeple for the rest of
  the game vs one returned imminently are valued identically in the base. A free meeple is worth more
  **when tiles remain to redeploy it** (early/mid) and ~nothing in the endgame (no time to place).
- **Exact intended signal.** Add `v28_meeple_k × (meeples_self − meeples_opp) × recovery_factor`,
  where `recovery_factor = min(1, tiles_remaining / v28_meeple_recovery_t0)` (1.0 when t0=0 → flat,
  matching the legacy `meeple_k`). The recovery scaling is the differentiator from the inert legacy
  flat term.
- **Expected phase.** Opening→mid (free meeples have redeploy value); decays to ~0 by endgame. Target:
  midgame `meeple-economy` (22).
- **Possible failure modes.** (a) `meeple_k` was historically left OFF — a linear term may be too crude
  even with recovery scaling. (b) Could reward hoarding meeples (passivity). (c) Small bucket (22) →
  low statistical power to detect a clean win.
- **Search-duplication risk.** **Low–medium.** Meeple supply is a static scalar; search does eventually
  feel meeple exhaustion via rollouts, but a leaf term front-loads it. Risk it just shifts the
  exploration/exploitation balance rather than improving value.
- **Minimal implementation.** New `LeafConfig.v28_meeple_k: float = 0.0`,
  `v28_meeple_recovery_t0: int = 0`. Term added in `virtual_score_v2` final assembly (after caps,
  independent of legacy `meeple_k`). Force engine path when `v28_meeple_k != 0`.
- **Offline test.** Two positions identical except one has more tiles remaining: assert the meeple term
  is larger in the tile-rich one (recovery scaling); assert t0=0 reproduces the flat legacy term; assert
  OFF (k=0) is bit-identical to v2.7.
- **Target cases (22):** `mid::heur3200_s3502000043_K52`, `mid::heur3200_s3502000014_K16`,
  `mid::greedy_s3500000036_K28`, `mid::hybrid_8_3200_s3503000041_K52`, `mid::greedy_s3500000024_K52`,
  `mid::greedy_s3500000018_K16`, `mid::greedy_s3500000005_K40`, `mid::hybrid_8_3200_s3503000046_K52`,
  `mid::heur3200_s3502000024_K16`, `mid::heur3200_s3502000002_K52` (full set = `meeple_economy_v1`).

---

## Patch 4 — `v28_denial` (opponent_denial_v1)  ·  M4, SPECULATIVE, config-only

- **Hypothesis.** v2.7's denial is symmetric (`opp_bonus_cap` defaults = self `bonus_cap`).
  Asymmetrically raising the opponent-bonus cap sharpens the **block-the-opponent's-big-completion**
  signal in search. (Weakest evidence — no isolated denial bucket; folded into structural/unclear.)
- **Exact intended signal.** `opp_bonus_cap > bonus_cap` (e.g. self 12 / opp 18 or 24) → the leaf
  subtracts more of the opponent's anticipated closures → search prefers denial moves.
- **Expected phase.** Mid + late-mid (contested high-value completions).
- **Possible failure modes.** (a) No targeted evidence → likely null. (b) Over-weighting denial can make
  play passive/reactive and *lose* on tempo. (c) Caps interact with the farm/closure terms.
- **Search-duplication risk.** **High.** Denial value is mostly a *search* phenomenon (you see the
  opponent's completion in the tree). A leaf cap-asymmetry mostly re-weights what search already finds.
- **Minimal implementation.** **No new code** — `LeafConfig.opp_bonus_cap` exists. v2.8 variant = a
  named config with `opp_bonus_cap` raised. (Works on flat path too, but registered as v2.8.)
- **Offline test.** Position with a high-value opponent near-closure: assert `bonus_opp` (hence the
  subtraction) is larger when `opp_bonus_cap` is raised; assert symmetric cap reproduces v2.7.
- **Target cases.** No clean isolated subset (folded into structural/unclear 385). **Treated as a
  low-priority probe** — run only if Phase 4 shows the farm/completion patches localize denial-adjacent
  gains. If Phase 4 root-audit shows no movement, **kill before any search eval** (cost discipline).

---

## Decision: what gets implemented in Phase 3

| patch | new code? | evidence | priority | gate to survive |
|---|---|---|---|---|
| `v28_farm` | yes | strongest (175 cases) | **1** | improve farm/endgame subset, mechanism supported in autopsy |
| `v28_completion` | no (reuse) | medium (112) | **2** | help at heur@200 AND not lose at heur@800 |
| `v28_meeple` | yes | small-clean (22) | **3** | improve meeple subset, recovery counterfactual holds |
| `v28_denial` | no (reuse) | speculative | **4** | only if 1–3 localize denial gains; else kill pre-eval |

**We implement all four as opt-in configs** (two need code), but **do NOT compose** any v2.8 until each
is ablated independently (Phase 4 root-audit → Phase 5 search). Expect to **kill** patches — the
taxonomy says ~67% of misses are not leaf-addressable, so a null/negative result on most of these is
the *expected* outcome, not a failure of the branch.

---
*Phase 2 complete. Next: Phase 3 — implement the opt-in variants + parity tests.*
