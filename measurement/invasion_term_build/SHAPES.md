# INVASION-RISK TERM FAMILY — the four shapes, exactly as implemented

**STATUS: BUILT, NOT SCREENED (2026-08-26).** Nothing here has been measured
against anything. No band claimed, no cell run, no results.csv row. This document
is the *spec of record* the screening prereg quotes verbatim; the implementation
is `rust/carc/carc-core/src/leaf/invasion.rs` and the formulas below are the code,
not a paraphrase of it.

Mechanism being encoded (`docs/LEVER_INDEX.md`, row "contested-feature /
invasion-risk term"; Stage A census `measurement/e4_exploit_grading_20260825/`):
an invasion is a multi-ply plan whose FIRST move — a 2-tile stub claim beside an
opponent feature — the champion leaf DEMOTES, because the merge payoff is several
plies out and the vendored full-points-on-tie rule hides the victim's loss, so
self-play never priced it. The measured play: deliberate invasions by merge 90 vs
7, late decisive farm captures, champion farm-zeroed in 9 of 50 games. The terms'
job: make step one look good at depth 0 so ordinary search carries the plan, and
symmetrically make one's own big open-edged features look less safe.

---

## 0. Shared definitions (all four shapes)

Everything below ranges over **claimed components** — city, road and farm
components carrying at least one meeple. Cloisters are OUT OF SCOPE for every
shape: a cloister cannot be joined, merged or invaded.

| symbol | definition |
|---|---|
| `cnt[p]` | weighted meeples of player `p` on the component (big meeple = 2), attributed exactly as `final_scores` does (terrain of the meeple's own side; farmers via `farm_pos0_root`) |
| `holder` | the STRICT weighted majority `cnt[p] > cnt[1-p]`, else NONE. A tied or unclaimed component fires no shape. |
| `V(f)` | **the points the leaf's BASE term already awards the holder**: `city_points` / `road_points` / `3 × (finished cities the field touches)`. NOT the closure-anticipated value, NOT `city_root_delta`. |
| `tiles(f)` | distinct tiles the component spans |
| `open_n(f)` | distinct EMPTY board cells the component has a feature edge into, **grid-bounded exactly as `decomp`** (an edge pointing off the 35×35 board is unfinished but NOT open — the D16 walled-variant distortion is part of the measured champion and is reproduced, not fixed) |
| `edges(f)` | feature-edge count: city/road = component node count (one per tile-side); **farm = number of `tile_connections` across the component's `FarmerConnection` nodes**, not the node count (one field node can carry up to four farmer sides, so a node count would be smaller than `open_n` and shape C's fraction could exceed 1) |
| `reserve[p]` | `state.meeples[p]`, the meeples `p` still has in hand |
| `can_join(f, x)` | the draft's cheap `P_contest` proxy, **0/1 and never graded**: `open_n(f) >= 1 AND reserve[x] >= 1` |

`open_n` for cities and roads is `decomp`'s own `city_root_open_n` /
`road_root_open_n`; the module re-derives the open **cells** (which `decomp`
discards) and a rust unit test asserts the re-derivation reproduces `decomp`'s
counts exactly, on every root of every position of five games — so no shape can
price a different board than the leaf does.

Every shape sums its contributions with `compat::fsum`, so the value is a
function of the multiset and not of iteration order.

---

## 1. Shape A — contested-value transfer ("the tie is not free")

**Weight: `invasion_beta`. The leaf ADDS `beta × T_A`.**

```
T_A = Σ  V(f)   over f with holder == OPP    and can_join(f, PLAYER)
    − Σ  V(f)   over f with holder == PLAYER and can_join(f, OPP)
```
over cities, roads AND farms.

Why this sign. The vendored rule is FULL POINTS ON TIE: a successful invasion
pays the invader `V` and costs the victim nothing in raw points, so in the
DIFFERENTIAL leaf the victim loses exactly `V`. The base term prices a
majority-held component as a clean `±V`; shape A walks that back toward 0 by
`beta × V` for every component the other side can still reach. `beta = 1.0` means
"a contestable component is worth nothing in the differential".

**ANTISYMMETRIC**: `T_A(p) == −T_A(1−p)` at every position (unit-tested).
Offense and defense in one weight.

**⚠️ DEVIATION FROM THE DRAFT — exactly a factor of 2, deliberate.** The draft
writes shape A as TWO edits: `v_feature *= (1 − beta·P)` on the holder AND
`+= beta·P·v` credited to the invader. In a two-player DIFFERENTIAL leaf both
edits move the same difference the same way, so the draft's form is identically
`2 × T_A` at every position — a constant rescaling absorbed into the swept
weight. The single signed transfer is implemented instead so `beta = 1.0` carries
the meaning above.

**Known interaction (unmeasured):** shape A subtracts from the same objects the
capped opponent-anticipation bonus already discounts (`V25_OPP_CAP` /
`opp_bonus_cap = 8`). The draft flagged this; nothing here resolves it. A screen
that adopts A owes the `feedback_bug_fix_shifts_optima` re-sweep of the caps.

---

## 2. Shape B — stub-claim merge-potential bonus (OFFENSE ONLY)

**Weights: `invasion_alpha`, `invasion_alpha_cap`, `invasion_stub_max_tiles`.
The leaf ADDS `alpha × T_B`.**

For every ORDERED pair `(S, L)` of components of the **same terrain family** with

* `holder(S) == PLAYER`, `tiles(S) <= invasion_stub_max_tiles` (default 2),
  `open_n(S) >= 1` — the STUB;
* `holder(L) == OPP`, `L != S`, `tiles(L) > tiles(S)`, `open_n(L) >= 1` — the
  LARGER opponent feature;
* **merge distance 1**: `S` and `L` have a feature edge into at least one common
  empty board cell, i.e. one tile placed there could connect them;

the pair contributes `min(V(L), invasion_alpha_cap)`, and

```
T_B = fsum of those contributions        (T_B >= 0 always)
```

`invasion_alpha_cap == 0.0` means **UNCAPPED** — an explicit compare, so the
uncapped route never touches the cap arithmetic. At `cap = 1.0` the term
degenerates to a COUNT of qualifying pairs (unit-tested).

This is the term that directly promotes the demoted FIRST move: after the stub
claim the leaf already sees the merge payoff at depth 0.

**⚠️ NOT ANTISYMMETRIC — by design.** `T_B >= 0` always and
`T_B(player) != −T_B(1−player)`. Each side gets its own offense when it evaluates
from its own POV, but a single leaf value is not seat-invariant under this term.
The symmetric counterpart of the same mechanism is shape A.

---

## 3. Shape C — dumping-ground discount (DEFENSE ONLY)

**Weight: `invasion_gamma`. ⚠️ The leaf SUBTRACTS `gamma × T_C`** — note the sign
against A/B/D, which are added.

For every component with `holder == PLAYER`:

```
unguarded = open_n(f)  if reserve[OPP] >= 1  else  0
frac      = unguarded / edges(f)                       ∈ [0, 1]
contrib   = frac × V(f)
T_C       = fsum(contrib)                              (T_C >= 0 always)
```

This is the linear form of the draft's `v *= (1 − gamma·frac)`: subtracting
`gamma·frac·V` IS that multiplication, written as an additive penalty so the term
composes with the existing city terms instead of replacing them, and so no clamp
(a hidden second knob) is needed. Sweeps stay in `gamma ∈ [0, 1]`, where the two
forms are identical.

A perimeter nobody can walk through is not a liability: with the opponent's
reserve empty the term is silent for that side. `frac <= 1` is a unit-tested
invariant (`open_n <= edges` on every claimed component).

**⚠️ NOT ANTISYMMETRIC — by design, and the READ RULE depends on it.** Shape C is
purely defensive: it can only show up against an opponent that actually invades.
**An H2H-vs-champion NULL for C is EXPECTED and is NOT disconfirming** (the
champion does not invade). Screen C against a shape-B agent or against E4, never
against the base champion.

### ⚠️ Shape C — the normalisation caveat (MEASURED, and it constrains the read)

`frac = open_n / edges` makes the charge a **rate × a value**. A big city has
proportionally MORE edges, so **shape C does not rank a large open city above a
small fully-open feature.** On the 93 census invasion positions the fixtures
replay, the side-aggregate claim `T_C(monster holder) > T_C(other side)` is FALSE
in **8 of 23** one-sided cases, and the per-feature version (`max own contribution`)
is false in 15 of 23. What IS true, and what the fixtures assert, is:

* an undefended monster (>= 4 tiles, >= 2 open cells, `V > 0`) always carries a
  strictly positive charge inside its holder's `T_C`; and
* closing one open cell of one's own feature strictly reduces that feature's
  charge (hand-built pin: `T_C` 1.0 → 0.5, the opponent's untouched).

This is a property of the shape **as the draft specifies it**, not a bug, and it
was not silently "fixed": the obvious alternative — an UN-NORMALISED
`contrib = open_n × V` or `contrib = V` gated on `open_n >= k`, which would rank
by size — is a **different shape** and is deliberately NOT implemented, so the
screen stays single-variable. If C reads null, that variant is the named first
follow-up, not a re-parameterisation of this one.

---

## 4. Shape D — farm-specific contested differential (the H4 conjunction)

**Weight: `invasion_delta_farm`. The leaf ADDS `delta_farm × T_D`.**

Exactly shape A restricted to FIELDS:

```
T_D = Σ V(f) over FARMS with holder == OPP    and can_join(f, PLAYER)
    − Σ V(f) over FARMS with holder == PLAYER and can_join(f, OPP)
```

with `V(f) = 3 × (finished cities the field touches)`. At `delta_farm = 1.0` a
contestable field contributes NOTHING to the differential — the draft's "price
the farm as swing `my_share − opp_potential_share`, not gross". ANTISYMMETRIC.

Closest shape to the measured E4 mechanism (late decisive farm captures).

**⚠️ COLLINEAR WITH SHAPE A — the prereg must say so.** By construction

```
T_A  ==  (cities+roads part of T_A)  +  T_D          exactly
```

(unit-tested). Running `beta` and `delta_farm` together is **not** two independent
effects; it is the parameterisation "`beta` on everything, `beta + delta_farm` on
fields". Screening A against D is a SCOPE contrast, not a shape contrast, and a
joint 2-D sweep must be read on the `(beta, beta+delta_farm)` basis.

---

## 5. Knob schema (`--cand-leaf-json`)

The house dialect is **FLAT** — `--cand-leaf-json` validates keys against
`virtual_score_v2.LeafConfig`'s dataclass fields, so a nested `{"invasion_terms":
{...}}` object would not parse. The six fields:

```json
{
  "invasion_beta":            0.0,
  "invasion_alpha":           0.0,
  "invasion_alpha_cap":       0.0,
  "invasion_stub_max_tiles":  2,
  "invasion_gamma":           0.0,
  "invasion_delta_farm":      0.0
}
```

A screening cell sets exactly one weight, e.g.

```
--cand-leaf-json '{"invasion_beta": 0.25}'
--cand-leaf-json '{"invasion_alpha": 0.5, "invasion_alpha_cap": 8.0}'
--cand-leaf-json '{"invasion_gamma": 0.5}'
--cand-leaf-json '{"invasion_delta_farm": 1.0}'
```

Env equivalents exist for every field (`CARCASSONNE_INVASION_BETA`, `_ALPHA`,
`_ALPHA_CAP`, `_STUB_MAX_TILES`, `_GAMMA`, `_DELTA_FARM`), read by
`_config_from_env`.

### ⚠️ RUST PATH ONLY

This family is implemented in **`carc_core::leaf::invasion` and nowhere else**.
There is deliberately no `flat_leaf.py` mirror and no Cython mirror (owner
decision 2026-08-26: RUST-FIRST, single implementation, no python parity grind).
It is the **tile-tie pattern with the sides reversed**:

* `flat_leaf.flat_virtual_score_v2` / `_float` **raise `NotImplementedError`** on
  any nonzero weight (`flat_leaf._require_invasion_off`), before any route is
  chosen — so the Cython path cannot serve an invasion-blind leaf either;
* `virtual_score_v2`'s object path raises the same way;
* `rust_agent.leaf_config_rs` forwards the knobs as **conditional kwargs**, so a
  `carc_rs` build predating the family still serves every default-off (champion)
  config unchanged, and raises `TypeError` on a nonzero weight;
* `c5_leaf_override._assert_cy_float_path` WARNS that the family is rust-only and
  makes a negative cap / sub-1 stub threshold fatal.

Every screening cell therefore runs `--backend rust`. A `--backend python` leg
fails loudly rather than producing a beautiful, meaningless null.

---

## 6. Leaf-hash behaviour

`c5_leaf_override._leaf_dict` (the `a36d2e15` dialect) drops a field **while it
holds its default**, so all six additive fields are in
`_LEAF_HASH_EXCLUDE_IF_DEFAULT` at their defaults. Consequences, all asserted:

| config | leaf hash |
|---|---|
| champion (fields absent) | `a36d2e15a3b3d71d`, **unchanged** |
| explicit `{"invasion_beta": 0.0}` (or all four weights explicitly 0.0) | **same as the champion** |
| any nonzero weight | **different** |
| a moved INERT knob (`invasion_alpha_cap` / `invasion_stub_max_tiles`) with all weights 0.0 | **different**, while the leaf function is unchanged |

Why explicit-zero hashing AS the champion is safe: **the hash names the leaf
FUNCTION, not the JSON text**, and a zero-weight config is the champion leaf
bit-for-bit (gate 1). A no-op JSON therefore cannot fake a new leaf — which is the
property the wiring gates rely on.

The last row is the same known, accepted asymmetry the open-city thresholds
already carry (a moved-but-inert threshold shifts the hash). It is asserted in the
fixtures so it cannot surprise anyone reading a manifest.

The **full-asdict** hashes (manifest/golden provenance dumps that do not use the
exclusion recipe) DO shift, as they did for every previous additive field. The
FROZEN-substrate recipe (`scripts/measurement_infra/snapshot._FROZEN_HASH_DEFAULT_OFF`
and its mirrors) carries the six fields too, so `6dfffd57` / `158f17ff` /
`7fc930b8` recompute unchanged.

---

## 7. Where the code and the gates live

| what | where |
|---|---|
| the four shapes | `rust/carc/carc-core/src/leaf/invasion.rs` |
| config fields + the four gated statements | `rust/carc/carc-core/src/leaf/mod.rs` (`LeafConfig`, `LeafTerms`, `leaf_terms_with`) |
| pyo3 knobs + `invasion_terms` / `invasion_scan` diagnostics | `rust/carc/carc-py/src/lib.rs` |
| python config fields, env knobs, fail-closed | `src/carcassonne_ai/virtual_score_v2.py`, `src/carcassonne_ai/flat_leaf.py` |
| conditional kwarg forwarding | `src/carcassonne_ai/rust_agent.py::leaf_config_rs` |
| hash dialect mirrors | `scripts/classical_search/c5_leaf_override.py`, `src/carcassonne_ai/alphabeta_agent.py`, `scripts/measurement_infra/snapshot.py` |
| rust unit tests (13) | `invasion.rs::tests` |
| python fixtures (14) | `measurement/invasion_term_build/test_invasion_shapes.py` |
| E4 / Stage A replay helper | `measurement/invasion_term_build/e4_positions.py` |

### Running the fixtures

```
maturin build --release -m rust/carc/carc-py/Cargo.toml -o <wheeldir>     # from THIS tree
unzip <wheeldir>/carc_rs-*.whl -d <shadow>                                # site-packages untouched
CARCASSONNE_FIX_R9=1 PYTHONPATH=<shadow>:<tree>/src:<tree>/engine \
  .venv/bin/python -m pytest measurement/invasion_term_build/ -q
```

`CARCASSONNE_FIX_R9=1` must be in the ENVIRONMENT before the process starts (the
E4 `fixed_v1` archives were played under R9 and the rust tile registry latches a
`OnceLock`). The shadow-dir unpack is the phase-seam pattern — never
`maturin develop` into the shared venv while other runs may be live.

---

## 8. Screening plan (from the draft, unchanged — NOT YET FUNDED)

1. Screen at the 2750 ablation instrument, deck-paired, **fresh band**, n=800:
   A, B, D vs the champion leaf; **C vs a shape-B agent, not vs the champion**
   (§3's read rule).
2. Bracket each weight with 3 points (`feedback_bracket_hyperparams`); a peak at a
   ladder endpoint is not bracketed.
3. Anything >= +2σ at 2750 → ONE production-budget (11008) H2H, n >= 400 paired.
4. All null → then and only then fund the solver pricing instrument (the ceiling
   question).

Discipline: results.csv rows per cell; band claims in
`governance/BAND_REGISTRY.csv`; a nonzero weight is a NEW leaf hash and owes a
lineage entry; and if any shape is adopted, re-sweep the V25 caps
(`feedback_bug_fix_shifts_optima`) — shape A in particular overlaps
`opp_bonus_cap`.
