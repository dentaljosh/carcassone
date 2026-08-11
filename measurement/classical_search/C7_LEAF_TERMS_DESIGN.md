# C7 — Second C5 wave: NEW leaf terms (meeple-return liquidity + farm majority-flip) — PRE-REGISTERED DESIGN

> **STATUS: DESIGN / PROPOSED 2026-07-13 — NOT LAUNCHED.** No code written, no compute run.
> Charter: [docs/BACKLOG_REAUDIT_2026-07-13.md](../../docs/BACKLOG_REAUDIT_2026-07-13.md) item **T2**
> ("second C5 wave — NEW leaf *terms*, not reweights"). Term shapes originate in the 2026-05-16
> strategy-lit review ([BACKLOG.md](../../BACKLOG.md):309 stranding-risk / :311 farm majority-flip) —
> neither ever tested in any form (checked DECISIONS.md + results.csv 2026-07-13: no kills, no rows).
> Design-only; `governance/PRODUCTION.yaml` untouched by anything in this document.
> Scope: TWO new opt-in `LeafConfig.v29_*` terms, S1 clair screen (6 cells, ~9 box-h) → n=400 clair
> confirm → mandatory S3 fair gate, exactly the CL-051 (curve125) template.

## Premise

CL-051 proved the mechanism this wave bets on: a term-**shape** change on the meeple-economy axis
(curve ×1.25) fired **+66.8 clair (z4.59) / +48.8 fair (z3.13)** after every plain reweight died
(C5 S1: caps flat, opp_cap wings −59.6/−66.8, bagclose null). The leaf therefore **under-prices
meeple commitment under PUCT**, and leaf changes **transfer fair by construction** — the same
`LeafConfig` evaluates every leaf of every PIMC determinization (`fair_agent.py`), so unlike search
knobs (reuse_tree, CL-044) there is no clairvoyant-only failure mode, only magnitude uncertainty
under the ~120-elo tax (CL-048).

C7 adds the two never-tested term shapes adjacent to the axis that just fired:

1. **Term R — meeple-return liquidity** (T2's "stranding-risk meeple weighting"): the curve prices
   the *stock* of free meeples; nothing prices the expected *flow back*. A knight on a 1-open city
   is nearly liquid; a knight on a sprawling 4-open city is stranded capital. R credits each
   committed, returnable meeple with `P(feature closes) × marginal-curve-value-of-one-more-free-meeple`.
2. **Term F — farm majority-flip anticipation**: base scoring awards contested fields by the hard
   step `sign(margin)·V` — a 2-1 field lead is priced identically to 4-1, and a tie is priced as
   secure. F smooths the step by margin **and by meeple liquidity** (the escalation war goes to the
   player who can afford the next farmer), discounting fragile leads and crediting realistic flips.

**Honest prior (pre-registered):** T2 rates the wave 25–35% that ONE axis fires. Per-term:
R ≈ 25–30% (closest neighbor to the fired curve axis; but partially correlated with the existing
capped closure bonus — see Risks), F ≈ 15–20% (genuinely new angle, but two adjacent formulations
are dead: `v28_farm_majority` growth-gating and the opp_cap denial wings). Expect at least one null
and size the kill gates accordingly.

## No-touch guarantees

- **`governance/PRODUCTION.yaml` is NOT modified** by any stage. Both new knobs default OFF
  (`0.0`); with both OFF the leaf is **bit-exact** to the champion `v2_9_2_Bmild_cap8_curve125`
  (hash `158f17ff76adaa02` must recompute UNCHANGED — see §5(d) and the hash-churn trap in §4).
  Adoption of a winner is a separate flip-proposal doc for Joshua, exactly like C5_CURVE125_PROPOSAL.md.
- All evidence lands as `experiments/results.csv` rows (`c7_*`) + per-cell `manifest.json` with
  per-side `leaf_cfg` + `leaf_hash` (C5 Trap-1 wrong-leaf mitigation, already built into both harnesses).
- Champion side of every cell is the PRODUCTION.yaml champion verbatim (curve125 env per
  `scripts/human_anchor/env_preamble.py` conventions; `--cand-leaf-json` overrides the candidate side only).
- Zero cloud. Local 5900XT + laptop, `nice -n 19`, pre-launch process census, git-bundle sync
  before any two-box run, detached (`setsid`) launches, shared-claim work-stealing.
- **Excluded, pre-registered:** deck-aware closure in ANY form (killed 3×, T2 hard rule);
  blanket/capped denial reweights (v2.10 closed + C5 opp_cap wings); `v29_util_tanh_t` /
  `v29_punish_k` / `v29_farm_access_k` (lost in the v2.9 wave, object-path-only, cost-prohibitive);
  the **targeted-denial third term is DROPPED** — see §3.

---

## 1. Term R — meeple-return liquidity (`v29_meeple_return_k`)

### Mechanism hypothesis

`state.meeples[p]` counts only *free* meeples; the curve values that stock nonlinearly (0 free =
−10, the cliff the ×1.25 reweight steepened). But two positions with equal free counts differ
hugely in *expected recovery*: committed meeples on features that will close soon come home
(climbing the curve); meeples on features that will never close are dead. The capped closure bonus
prices the **points** side of imminent closures (and saturates at cap 8); nothing prices the
**liquidity** side. Under PUCT this matters doubly: priors are per-child afterstate deltas, so a
placement that commits the last free meeple to a low-P feature should look strictly worse than one
committing to a 1-open city — today both pay the same curve step. This is the direct refinement of
the axis that just fired, and it is exactly BACKLOG.md:309 ("weight by stranding risk … plus the
option value of holding ≥1 reserve meeple").

### Exact math

For player `p`, over `state.placed_meeples[p]`, **per meeple, NO feature-dedup** (every meeple on a
merged feature returns when it closes — contrast the closure bonus, which dedups because points are
per-feature):

```
P_list(p) = [ P_return(mp) for mp in placed_meeples[p] if P_return(mp) > 0 ]

P_return(mp):
  CITY meeple    (terrain == CITY):     city component c of mp.
                                        finished(c)      -> skip   (engine returns the meeple at scoring; defensive, mirrors the closure bonus)
                                        open_n(c) <= 0   -> skip   (D16 unclosable board-edge city)
                                        else P = closure_p.get(open_n(c), 0.0)
  CLOISTER meeple (CHAPEL or FLOWERS):  needed = 8 - surrounding_count(r, c)
                                        needed <= 0      -> skip
                                        else P = closure_p.get(needed, 0.0)
  ROAD meeple    (terrain == ROAD):     road component d of mp.
                                        finished(d)      -> skip
                                        road_open_n(d) <= 0 -> skip
                                        else P = closure_p.get(road_open_n(d), 0.0)
  FARMER / BIG_FARMER:                  skip (farmers NEVER return — permanent commitment;
                                        their return value is structurally 0)

dcurve(n) = float(curve[min(n+1, L-1)]) - float(curve[min(max(n,0), L-1)])   # L = len(curve) = 8
            # marginal value of recovering ONE meeple at current free count n; 0 when n = L-1

ret(p)    = dcurve(state.meeples[p]) * fsum(P_list(p))

TERM      : score += cfg.v29_meeple_return_k * (ret(player) - ret(opp))
```

`closure_p` is the candidate cfg's own schedule (production `{1:0.5, 2:0.2, 3:0.05}`) — the same
proximity→probability map the closure bonus uses; no new probability model is introduced.
`road_open_n(d)` = # distinct empty board cells adjacent to the component's open road ends —
the road analog of `city_root_open_n` (a **new Decomp field**, see below). `fsum` = `math.fsum`
(order-independent, the house canonical-sum convention) so the three implementations need not
iterate meeples in the same order.

**Deliberate conventions (do not "fix" during implementation):** (a) per-meeple, not per-feature;
(b) finished-feature meeples contribute 0 (transient just-closed states — the defensive skip
mirrors the closure bonus and keeps all paths trivially identical); (c) dcurve is a linearization —
two expected returns both price at the current marginal step, slightly over-crediting under the
concave curve; accepted, `k` absorbs it; (d) **requires a curve**: if `v29_meeple_return_k != 0`
and `v29_meeple_curve is None`, raise `ValueError` (guard in `_load_cand_leaf_cfg` + a defensive
check at the term site). The champion always has a curve.

### Inputs, cost class, plug points

| | |
|---|---|
| State inputs | `placed_meeples[p]` (≤7/player), per-component `finished` / `open_n` / `road_open_n`, `surrounding_count`, `state.meeples`, `cfg.closure_p`, `cfg.v29_meeple_curve` |
| New LeafConfig field | `v29_meeple_return_k: float = 0.0` (OFF) |
| Cost class | **cheap** — one pass over ≤14 meeples with O(1) table lookups against the already-built decomposition; NO new traversal/flood-fill. The ONLY new decomposition work is `road_open_n` (a per-open-road-node empty-neighbor stamp count inside the existing road-facts loop — same pattern as the city one, ~10 lines, O(road nodes)). Expected per-leaf delta ≤ 2–3%; hard-gated ≤ 10% at Stage 0. |
| Flat/Cy computable | YES. Python flat: everything except `road_open_n` already in `Decomp`; Cython: everything in `_WS` (`city_fin/city_open_n/road_fin`, `_cloister_points_c`, meeple partition pattern from `_closure_bonus_c`) except a new `road_open_n` array filled in the road-facts loop. |
| Plug point (object) | `leaf_v29.apply_v29`, inserted between the curve block and the punish block |
| Plug point (flat) | `flat_leaf.flat_virtual_score_v2` / `_float` and `heuristic_prior_mcts.leaf_score_float`, immediately AFTER the curve/meeple_k block (see §4 ordering rule) |

### Screen axis

`k ∈ {0.5, 1.0, 2.0}` — 1.0 is the theoretically-neutral value (expected liquidity flow at face
value), 0.5 the under-dose, 2.0 the deliberate "too much" wing. OFF ≡ champion ≡ 0 by construction
(the C4/C5 champion-sibling null template). Typical magnitude at k=1: ΣP ≈ 0.5–1.5 over 2–4
committed meeples × dcurve 1.25–3.75 → a ±1–4 pt differential term, same order as the curve term
that fired.

---

## 2. Term F — farm majority-flip anticipation (`v29_farm_flip_k`)

### Mechanism hypothesis

For a contested field the base score awards the full end-value by the hard step: leading by ANY
margin = +V, tied = both score (net 0), behind = −V. Real contested fields are escalation wars:
a 1-farmer lead is fragile (one opposing farmer flips or ties it), a tie leans toward whoever has
the meeple reserves to escalate, a 2+ margin is near-safe. The step therefore over-states
confidence at small margins and mis-prices exactly the decision T2 names — "a 2nd farmer that only
*ties* a contested field is worth ≪ one that flips the majority": under the smoothed value the
tie-maker buys a fragile ~half-credit while the flip buys a discounted-but-real lead, with the
discount vanishing as margin or reserve advantage grows. Coupling the tiebreak to free-meeple
counts links F to the meeple-economy axis that just fired. Never tested in any form
(BACKLOG.md:311; distinct from the DEAD `v28_farm_majority`, which hard-gated the *growth bonus*
by majority, and from the dead denial wings — F only *smooths a value base already awards*, is
antisymmetric by construction, and touches contested fields exclusively).

### Exact math

Field membership and weights use **base-scoring semantics** (`farm_pos0_root` / `pos0_tab` — the
`find_meeples` mapping `count_final_scores` uses), NOT the bonus-side anypos mapping: F adjusts
base's award, so it must see exactly base's fields. Big farmer weight 2 (mirror the engine; our
locked scope has none).

```
for each farm component f with w_me(f) >= 1 AND w_opp(f) >= 1:      # contested only
    V      = float(3 * finished_adjacent_cities(f))                  # == what base awards the winner
    m      = w_me(f) - w_opp(f)                                      # int weighted margin
    step   = 1.0 if m > 0 else (-1.0 if m < 0 else 0.0)              # what base implicitly awards (net)
    free_d = clamp(state.meeples[player] - state.meeples[opp], -1, +1)   # int clamp
    m_eff  = m + FLIP_BETA * free_d                                  # FLIP_BETA = 0.5 (module constant)
    ramp   = clamp(m_eff / FLIP_RAMP, -1.0, +1.0)                    # FLIP_RAMP = 2.0 (module constant)
    contrib(f) = V * (ramp - step)

TERM: score += cfg.v29_farm_flip_k * fsum(contribs)                  # player POV; antisymmetric by construction
```

Worked values (k=1, V=9 field): tie w/ equal reserves → 0 (unchanged — ties net 0 in a
differential leaf and stay so); tie, I'm richer → +2.25 (tie leans my way); lead-by-1, equal →
−4.5 (fragile lead discounted halfway); lead-by-1, richer → −2.25; lead ≥2 → ~0 (safe);
behind-by-1, richer → +6.75 of hope-credit against base's −9. `k` interpolates between today's
hard step (k=0) and the full smoothed ramp (k=1).

**Deliberate conventions:** (a) `V` counts **finished** adjacent cities only — the value actually
at stake in base, cheap (`farm_root_finished_cities` / `ws.farm_fincities`), and conservative;a
potential-based V (E-stub style) is the killed direction and is NOT used. Early contested fields
with V=0 contribute 0 — accepted sparsity (see Risks). (b) `FLIP_BETA=0.5`, `FLIP_RAMP=2.0` are
pre-registered module constants (like `V_PUNISH`), NOT config fields — fewer LeafConfig fields,
less hash churn; a β/ramp sweep is a possible wave-3 only if F fires. (c) uncontested and
opponent-solo fields are untouched — no denial component, deliberately. (d) antisymmetry
(`term(player) = −term(opp)`) holds exactly under POV flip (m, free_d, step, ramp are all odd);
pin it with a property test.

### Inputs, cost class, plug points

| | |
|---|---|
| State inputs | placed farmers of both players → per-field weighted counts via pos0 semantics; `farm_root_finished_cities` / `ws.farm_fincities`; `state.meeples` |
| New LeafConfig field | `v29_farm_flip_k: float = 0.0` (OFF) |
| Cost class | **cheap** — one pass over both players' placed meeples (≤14) building a tiny per-field count table (the `_feat_add` pattern, ≤ a handful of fields), then O(#contested fields) float math. Zero new decomposition work. Expected per-leaf delta ≤ 1–2%. |
| Flat/Cy computable | YES with data already present in both paths (`farm_pos0_root`/`pos0_tab`, fincities). The cy loop is a ~25-line copy of `_final_scores_c`'s farm branch. |
| Plug point (object) | `apply_v29`, immediately after Term R |
| Plug point (flat) | immediately after Term R in all flat sites |

### Screen axis

`k ∈ {0.25, 0.5, 1.0}` — 0.5 is the guess (half-smoothing), 0.25 the under-dose, 1.0 the full-ramp
"too much" wing. OFF ≡ champion ≡ 0.

---

## 3. Dropped: targeted denial on near-complete large opponent cities

**DROPPED from this wave, pre-registered (do not resurrect without a new premise).** Reasons:
(1) both C5 opp_cap wings were the WORST screen cells (−59.6 / −66.8) — under PUCT, up-weighting
opponent threats in the leaf demonstrably mis-allocates the visit budget; (2) the only in-repo
"different formulation" (`leaf_v29._punish_signal`, imminent-high-value differential) was already
analyzed in the 2026-06-25 code map as leaf-redundant ("complete my own feature is already in
`base`; the punish gap is in SEARCH/POLICY") and forces the object path; (3) no formulation we can
state reads *differently* from "raise opponent-threat weight," which is the confirmed-dead axis.
The one live denial-adjacent idea — liquidity-aware field contests — is already inside Term F.
If both R and F null AND Joshua asks, a denial re-design would need a mechanism that is not an
opp-side reweight; none is proposed here.

---

## 4. Wiring map (read before coding — this is where the traps are)

The leaf has **THREE real implementations + two flat call-sites** that must stay bit-exact:

| # | Site | What changes |
|---|---|---|
| 1 | `src/carcassonne_ai/virtual_score_v2.py` | `LeafConfig`: add `v29_meeple_return_k: float = 0.0`, `v29_farm_flip_k: float = 0.0` (after the v29 block, before `bag_close`). Add both to `_v29_active` (else the object path silently drops them). Add `_v29_flat_eligible(cfg)` = curve/return/flip active only (util_tanh/punish/farm_access still force object); use it in the flat-redirect condition (line ~588–596) in place of `_v29_curve_only` (keep `_v29_curve_only` itself — tests import it). Add `_open_road_positions(state, road)` (mirror of `_open_city_positions` over `road.road_positions`) for the object path + reconcile reference. |
| 2 | `src/carcassonne_ai/flat_leaf.py` | `decompose()`: add `road_root_open_n` (distinct-empty-adjacent-cell count per road component — same stamp/dedup pattern as `city_root_emptyadj`; new `Decomp` field). Two new helpers `flat_return_term(state, player, decomp, cfg)` and `flat_farm_flip_term(state, player, decomp, cfg)` implementing §1/§2 verbatim. In `flat_virtual_score_v2` AND `flat_virtual_score_v2_float`: after the curve/meeple_k block add, **in this order, as two separate gated adds** (float addition is non-associative — one fused add would break 3-way bit-exactness): `if cfg.v29_meeple_return_k != 0.0: score += cfg.v29_meeple_return_k * (...)` then `if cfg.v29_farm_flip_k != 0.0: score += cfg.v29_farm_flip_k * fsum(...)`. Extend BOTH cy-routing conditions (lines ~823–825 and ~884–886) with `(_c7_off(cfg) or _CY_SUPPORTS_C7)` so a **stale .so can never silently drop the terms** (the SUPPORTS_V29_CURVE precedent — this is the exact trap that flag exists for). |
| 3 | `src/carcassonne_ai/flat_leaf_cy.pyx` | `SUPPORTS_V29_C7_TERMS = True` module flag (one flag for both terms; bump if semantics ever change). `_WS`: new `int *road_open_n` (+ alloc/free), filled in the road-facts loop via the stamp pattern. In `_flat_score_v2_c`, after the curve block: the two gated adds, C ports of §1/§2 (meeple partition pattern from `_closure_bonus_c` incl. a new `terrain is _T_ROAD` branch; farm-count pattern from `_final_scores_c` over `pos0_tab`; contributions collected into a Python list → `_fsum` — same reduction as the closure bonus). Rebuild on all boxes (`setup_flat_leaf_cy.py build_ext --inplace`). |
| 4 | `src/carcassonne_ai/leaf_v29.py` | `_return_liquidity(state, player, cfg)` + `_farm_flip_term(state, player, opp)` object-path implementations (CityUtil/RoadUtil/FarmUtil + `_open_city_positions`/`_open_road_positions`/`_surrounding_count`; farm membership must reproduce pos0 semantics — gate settles any doubt). Insert the two gated adds in `apply_v29` between the curve block and the punish block (same order/expressions as flat). Extend `decompose_v29` with `meeple_return_delta` + `farm_flip_delta` keys. |
| 5 | `src/carcassonne_ai/heuristic_prior_mcts.py` | `leaf_score_float` (the pure-Python fallback the ±1 reproduction test pins) gets the same two gated adds — call the shared `flat_leaf` helpers, do not re-implement. |
| 6 | `scripts/classical_search/c5_leaf_override.py` | `_assert_cy_float_path`: replace the `_v29_curve_only` check with `_v29_flat_eligible` + require `SUPPORTS_V29_C7_TERMS` when either knob ≠ 0 (mirror the bag_close clause). Add the R-requires-curve guard. `_load_cand_leaf_cfg` needs NO change (field names auto-derive from the dataclass). |
| 7 | **Hash-churn ripple** (the bag_close precedent, `virtual_score_v2.py:141-143`) | Adding dataclass fields changes `dataclasses.asdict` → every schema-pinned hash. `scripts/measurement_infra/snapshot.py::_frozen_config_hash` + its two mirrors (`tests/test_frozen_substrates.py:29`, `tests/test_v29_flat_curve.py:61`) already exclude `bag_close is False`; **generalize the exclusion to a shared default-off set** `{bag_close: False, v29_meeple_return_k: 0.0, v29_farm_flip_k: 0.0}` so the frozen `7fc930b8…` and the PRODUCTION `158f17ff…` recipes recompute UNCHANGED. Per-run manifest hashes (`_leaf_hash`, full-asdict) WILL shift for champion-side entries vs pre-C7 manifests — expected, not a wrong-leaf signal; note it in the S1 launch log. Stage-0(d) hunts any other asdict consumer. |

**Ordering rule (bit-exactness across paths):** every path computes
`score = base + bonus_self − bonus_opp` → curve (or meeple_k) → **+ R term** → **+ F term**, as
separate sequential adds with the exact parenthesization written in §1/§2
(`k * (ret_self − ret_opp)`; `k * fsum(contribs)`). fsum makes iteration order irrelevant *within*
each term; the add order *between* terms must match.

---

## 5. Stage 0 — feasibility / cost gate (runs BEFORE any screen cell; GO/NO-GO)

One attended script, `scripts/classical_search/c7_stage0.py`, plus the existing reconcile gates.
~0.5 box-h + the dev itself. **All four parts must pass before S1 launches.**

**(a) Bit-exact-OFF proof.**
- `scripts/reconcile_flat_leaf.py --n 200` and `scripts/reconcile_cy_leaf.py --n 400 --snap-every 1`
  under production env (curve125 exports): **0 mismatches** (covers the OFF path end-to-end incl.
  the `decompose` road_open_n addition, whose existing-field outputs must be untouched).
- `pytest tests/test_frozen_substrates.py tests/test_v29_flat_curve.py tests/test_v29_variants.py
  tests/test_c5_leaf_ab.py tests/test_c5_fair_leaf_ab.py` green — `frozen_v29_cfg()` still asserts
  `7fc930b82801cb43`.
- GO = zero diffs; any mismatch = NO-GO, fix before spending compute.

**(b) Per-leaf cost delta at production knobs.**
- Corpus: ~2,000 states snapshotted from ~30 seeded self-play games (mid+endgame mix), leaf =
  `flat_virtual_score_v2_cy_float`, configs = champion / +R(k=1.0) / +F(k=0.5) / +both.
  Report median + p95 per-leaf ns ratios vs champion.
- **GO: each ON/OFF ratio ≤ 1.10** (pre-registered hard gate; expectation ≤ 1.03). A term over
  1.10 is dropped from the wave (redesign, don't launch) — equal-wall-clock evals mean a 10% leaf
  tax ≈ −9 elo of hidden sims cost (D0 slope ~+68/doubling).
- Also verify the pure-Python flat ON-path runs (fallback sanity), and time one n=4 game pair
  ON-vs-OFF: in-game ms-ratio ∈ [0.9, 1.1].

**(c) 3-way ON bit-exactness + manifest smoke.**
- Extend `reconcile_cy_leaf.py`'s config list with the three ON configs (R1.0 / F0.5 / both):
  cy == flat-py exact (int and pre-round float), full games, 0 mismatches. Extend the
  object-vs-flat gate (the `test_v29_flat_curve.py` pattern) to the new knobs: `leaf_v29` object
  path == flat, exact, over ≥500 fuzzed states. Antisymmetry + R-requires-curve unit tests.
- Harness mirror (the C5 Stage-0 gate re-run): `eval_puct_priors.py` n=20 @ band 1.60e10 with
  `--cand-leaf-json` = champion leaf verbatim → **bit-identical games** to the no-flag run, elo 0;
  then n=20 with `{"v29_meeple_return_k": 1.0}` → manifest `cand_leaf_hash ≠ champ_leaf_hash`,
  games differ, `_assert_cy_float_path` passes (proving the cy route, not the 30× fallback).
- GO = all exact / as-stated.

**(d) Hash/provenance audit.**
- Recompute the PRODUCTION.yaml hash via the frozen recipe → **must equal `158f17ff76adaa02`**;
  `rg -n "asdict.*LeafConfig|_frozen_config_hash|config_hash" src scripts tests` and clear every
  consumer (step2_pens / feature_graph provenance asserts pin `7fc930b8…`). Run the step2/feature-
  graph assert paths if importable. GO = both hashes stable + no unexplained consumer.

---

## 6. Stage 1 — SCREEN (clairvoyant, n=100/cell, 6 cells, ~9 box-h)

**Consumer (identical to C5):** candidate-leaf PUCT@2750 vs champion-leaf PUCT@2750 via
`scripts/classical_search/eval_puct_priors.py --candidate puct --opponent puct`, c1.5/τ5/float/
visits, reuse OFF both sides, exact-K=2 both sides, deck-paired seats (50 decks × 2), equal sims
(Stage-0(b) bounds the leaf-cost asymmetry; ms-ratio recorded per cell, parity gate ∈ [0.9, 1.1]).
Clairvoyant is the sanctioned cheap screen only — **no production proposal on clair evidence**
(Goodhart caveat carried from C5); S3 fair is mandatory.

**Seed bands (verified free 2026-07-13** — no `16e9/1.6e10` hits in scripts, results.csv, or
measurement/; in-use bands: 4.21e9, 9.0–9.031e9, 9.4–9.6e9, 9.99e9, 1.1e10, 1.20–1.24e10,
13/13.1e9, 15e9, 17/17.0001e9, 40e9; C6 reserved 1.40–1.42e10**)**: S1 = **1.60e10** (one band,
CRN across all cells) · noise-guard re-measure = **1.61e10** · S2 confirm = **1.62e10** ·
S3 fair = **1.63e10** · conditional R×F combo = **1.64e10**. Re-verify free at launch (house
discipline).

| Cell (`results.csv` exp_id) | `--cand-leaf-json` payload |
|---|---|
| `c7_ret050_vs_puctchamp2750_k2`  | `{"v29_meeple_return_k": 0.5}` |
| `c7_ret100_vs_puctchamp2750_k2`  | `{"v29_meeple_return_k": 1.0}` |
| `c7_ret200_vs_puctchamp2750_k2`  | `{"v29_meeple_return_k": 2.0}` |
| `c7_flip025_vs_puctchamp2750_k2` | `{"v29_farm_flip_k": 0.25}` |
| `c7_flip050_vs_puctchamp2750_k2` | `{"v29_farm_flip_k": 0.5}` |
| `c7_flip100_vs_puctchamp2750_k2` | `{"v29_farm_flip_k": 1.0}` |

Each axis is a coherent monotone dose ladder with the champion (knob OFF ≡ 0, by construction —
the Stage-0 mirror is the anchor's proof) below it and a deliberate over-dose wing above the guess;
a real effect must show dose-response, a lone-spike wing is a noise signature (results-discipline
rule).

**Cost:** C5 measured ~1.5 box-h per n=100 s2750 K=2 cell two-box (SCREEN_PROGRESS_R5 +
rr_puct timing) → 6 cells ≈ **9 box-h ≈ half a two-box overnight** — inside the T2 "~1 box-day per
wave" target with margin for the Stage-0 smoke + one re-measure. Launch order if squeezed:
ret100 → ret050 → ret200 → flip050 → flip025 → flip100 (R is the higher-prior term). n=100 paired
1σ ≈ ±25 elo; verdict metric everywhere is the **deck-matched CRN paired delta**, never absolute elo.

## 7. Stage 2 — clairvoyant CONFIRM · Stage 3 — FAIR gate · Stage 4-lite

**S2 (n=400, ≤2 cells, ≈6 box-h/cell, fresh band 1.62e10):** promote the top ≤2 S1 winners
(≤1 per axis — the best dose of each term). Gate below. *Conditional combo cell:* only if BOTH
terms confirm at S2, one R×F cell (winner doses, n=100 @ 1.64e10); adopt the combo only if
≥ max(singles) − 1σ. No other factorials.

**S3 (mandatory FAIR confirm — the real bar, the CL-051 template):** two FRESH arms, band 1.63e10,
**450 paired decks each** (n=900 games/arm — sized from CL-051, whose n=200 S3 was underpowered
and whose confirm resolved at 451 decks; read **ONCE** at completion, no optional stopping):
- candidate arm: `eval_fair_puct.py`, `FairHeuristicPriorAgent` at the CURRENT deploy config
  **k_dets=4 × sims=688** (CL-054) with `--cand-leaf-json` = the winning term, vs the fixed
  clairvoyant h800 champion-leaf rung;
- baseline arm: identical, champion leaf (no override), same decks/seats.
- **Ruler-reproduction sanity gate (blocking):** the baseline arm must land within 2σ of the
  CL-054 k4 confirm (+136.0 ± ~19 vs h800). If not, the ruler moved — STOP, investigate, do not
  read the delta.
- Verdict = deck-matched CRN delta candidate-vs-baseline (crn_delta tooling; `kdets_delta.py` is
  the same-band two-arm precedent). ≈ 10–12 box-h. OPENBLAS pin already in both harnesses
  (`eval_puct_priors.py:79`, `eval_fair_puct.py:119`) — verified 2026-07-13.

**S4-lite (consumer re-check, bug-fix-shifts-optima rule):** if a term passes S2, run
τ_p ∈ {3, 8} at the winner leaf, n=100 @ 1.60e10 (CRN vs its screen cell), ≈3 box-h. C5-S4 showed
the curve dose stable across τ — expect the same; if a τ wing beats the winner@τ5 by ≥ +35, the
flip proposal carries the re-tuned τ and S3 re-runs at it.

## 8. Pre-registered decision tree (what KILLS each term)

- **S1 axis kill:** no cell of the axis reaches **≥ +35 elo with paired_z ≥ 1.5** → the term is
  DEAD. Write the rows, close out; do not re-dose, do not "try one more k".
- **Monotone-coherence guard:** the promoted cell must sit in a coherent dose-response pattern
  (neighbors same-sign or a clean peak). A wing ≥ +35 whose *both* neighbors are ≤ 0 = lone-spike
  noise signature → ONE re-measure of that cell @ 1.61e10; promote only if it reproduces ≥ +35.
- **S2 kill:** n=400 fresh-band paired delta **< +25 elo − 70·log₂(ms_ratio)** (the leaf-cost
  adjustment; ≈ +25 for a ≤1.02-ratio term) OR paired_z < 2.0 → DEAD; log the S1 result as a noise
  spike.
- **S3 gates (read once at 450 paired decks):**
  - **PASS** = win-paired Δ ≥ +35 elo with z ≥ 2.0 **AND** margin CRN Δ > 0 pts/deck with z ≥ 2.0
    (both parts, CL-051 template) → write `C7_FLIP_PROPOSAL.md` (leaf name bumps to
    `v2_9_3_…_<term>`, PRODUCTION hash recomputed via the frozen recipe, NOT pasted from manifests);
    Joshua decides.
  - **KILL** = margin Δ ≤ 0 → DEAD. A leaf term has no clair-only mechanism excuse — a fair ≤ 0 at
    this power is a real null, grade it CLOSED, do not rationalize.
  - **POSITIVE-UNRESOLVED** = Δ > 0 but a z < 2.0 → present to Joshua with the exact power math
    (σ≈18 pts/deck → n needed for the observed Δ); extend-or-stop is his call (the C5 S3→confirm
    precedent). Not a pass; nothing is proposed on it.
- **All-null outcome (expected-plausible, ~65–75%):** verdict "the meeple-economy axis is captured
  by the curve; term-shape wave 2 CLOSED (null)" — six-touch close-out, T2 drops off the re-audit
  shortlist, and the honest residue is that the leaf's remaining headroom is NOT in cheap adjacent
  terms.

## 9. Build order (engineer runbook)

1. **LeafConfig + predicates** (`virtual_score_v2.py`): fields, `_v29_active`,
   `_v29_flat_eligible`, redirect condition, `_open_road_positions`. Commit.
2. **Hash-exclusion generalization** (snapshot.py + the two test mirrors) — run (d) asserts NOW,
   before any leaf math, so provenance breakage surfaces first. Commit.
3. **Python flat reference** (`flat_leaf.py`): `road_root_open_n` in `decompose` + `Decomp`;
   `flat_return_term` / `flat_farm_flip_term`; the two gated adds in both entry points; cy-routing
   capability conditions. Unit tests (antisymmetry, R-requires-curve, OFF-inertness). Commit.
4. **Object path** (`leaf_v29.py` + `apply_v29` + `decompose_v29`), then the object-vs-flat ON
   equality test. Commit.
5. **`leaf_score_float`** (heuristic_prior_mcts.py) — call the shared helpers. Commit.
6. **Cython port** (`flat_leaf_cy.pyx`): `road_open_n` array, the two term blocks,
   `SUPPORTS_V29_C7_TERMS`; rebuild local; extend + run `reconcile_cy_leaf.py` (OFF + 3 ON cfgs,
   0 mismatches) and `reconcile_flat_leaf.py` (road_open_n structure check added). Commit.
7. **Harness guard** (`c5_leaf_override.py::_assert_cy_float_path`) + pytest for the new JSON
   fields (extend `test_c5_leaf_ab.py` pattern). Commit.
8. **Stage 0 script + run** (§5 a–d). Rebuild the .so on the laptop (git-bundle sync + rebuild —
   a stale laptop .so falls back to pure-Python flat: correct but ~30× slow; the Stage-0(b) bench
   on BOTH boxes catches it).
9. **S1 launch** (6 cells, shared-claim two-box, detached, census first, ETA stated in chat).
   Dev estimate for 1–8: **~1–1.5 days** (the .pyx port + reconcile extensions are the bulk).
   If dev overruns 2 days or Stage-0 fails a term: scope down to Term R alone (drop the road
   branch of R first — cities+cloisters-only variant — accepting the noted road-vs-city
   commitment artifact; then drop F).

## 10. Budget summary

| Stage | Cells | box-h |
|---|---|---|
| 0 feasibility/cost | smoke + benches | ~0.5 (+1–1.5 d dev) |
| 1 screen | 6 × n=100 | ~9 |
| 2 confirm | ≤2 × n=400 (+1 conditional combo n=100) | ≤13.5 |
| 3 fair | 2 arms × 450 paired decks | ~10–12 |
| 4-lite τ re-check | 2 × n=100 | ~3 |
| **Total** | **null-case ≈ 10 box-h (screen wave ≈ 1 box-day ✓); full-fire worst case ≈ 38 box-h ≈ 1.9 box-days** | |

## 11. Risks / what could make this a dead end (pre-registered honesty)

1. **The curve may already have soaked the meeple-economy headroom.** R's ΣP correlates with the
   (capped) closure bonus and its liquidity weighting with the curve itself; if PUCT only needed
   the *stock* priced right, the *flow* refinement is redundant → null. This is the single most
   likely outcome (~70%). The differentiators R banks on: the closure bonus saturates at cap 8
   (R stays discriminative past it) and prices points, not liquidity (R is worth 3× more to the
   meeple-poor side).
2. **F may be too sparse to detect.** Finished-adjacent-cities V is often 0 before the late
   midgame, and contested-field states are a minority of leaves; a real-but-rare signal needs a
   bigger per-instance effect to clear n=400. If F shows a positive-but-incoherent S1, that is
   what it looks like — the kill gates treat it as noise by design (no rationalizing).
3. **Two dead neighbors flank F** (v28_farm_majority, opp-denial). The margin/liquidity-fragility
   angle is genuinely untested, but the base rate for farm-term interventions in this leaf is 0/2.
4. **Bit-exactness across three implementations of NEW float math** is where the dev risk lives
   (clamp edges, POV signs, add ordering). Mitigations are structural: fsum multisets, two
   separate gated adds, antisymmetry property test, full-game reconcile fuzz at ON configs.
5. **Hash-churn ripple** beyond the known pins (an unlisted asdict consumer) could burn a day —
   Stage 0(d) exists to find it before compute is spent.
6. **Equal-sims screens flatter a costlier leaf** — bounded by the Stage-0 ≤1.10 gate and the
   S2 cost-adjusted threshold; S3's two fresh fair arms at fixed total budget are cost-honest.
7. **Opportunity cost:** T1 (k_dets marginalization ladder — partially discharged by CL-054) and
   T3 (joint TPE) queue behind this; a fast S1 null (~1 overnight) keeps the calendar loss small.

## Close-out checklist (six touches, one sitting — per CLAUDE.md)

results.csv rows (`c7_*`) → DECISIONS.md index line → status stamp on THIS doc →
governance CLAIM_REGISTRY row (new CL on pass; the null verdict also gets one) → STATUS.md top
block → roadmap T2 line (FIRED / CLOSED-null). Then `python3 scripts/doc_lint.py`.
