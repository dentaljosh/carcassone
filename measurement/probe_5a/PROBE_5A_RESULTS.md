# PROBE §5A — Tempo/timing third-axis gate — RESULTS

Status: **⏳ RUNNING (2026-07-01)** — gate-zero correlation check first (free kill),
then (if it passes) the 4-arm CL-037 head at h6400. Spec:
[docs/PROBE_5A_TEMPO_AXIS_GATE.md](../../docs/PROBE_5A_TEMPO_AXIS_GATE.md).
Emitter `scripts/probe_5a/emit_tempo.py` · gate-zero `scripts/probe_5a/gate_zero.py` ·
arms `scripts/probe_5a/run_arms.sh` · reader `scripts/probe_5a/verdict_5a.py`.

## The question (one variable = a third, uncorrelated value axis)

CL-039 closed the AZ-value route with "the residual value beyond the v2.9 leaf is
low-dimensional." That dimensionality claim rests on **two mutually-redundant axes
(farm, bag)**. §5A tests it against **tempo/timing** — the axis the flat v2.8
meeple-economy term handles crudely, uncorrelated-by-construction with farm/bag.

## Alignment (proven bit-exact)

The tempo block is emitted with the **identical** `step1_dump.py` child enumeration
(same `replay_to` / legal order / teacher-Q filter / `seen` dedup) and joined to the
CL-037 dataset by `(game_seed, ply, within-root ordinal)`. **Alignment proof:**
recomputed `leaf` matches the dataset `leaf_q` bit-exact (smoke: 520/520 rows,
max abs diff **0.00e+00**).

**Novel-axis discipline:** the CL-037 base 12 aux scalars already carry free-meeple
counts (cols 0,1) and tiles-remaining (col 5), and the blind arm holding them was
inert (+1.9%). Finished features auto-return meeples, so raw "committed" ≈ a linear
function of col 0. The tempo block therefore emits only the **depth-weighted lockup**
(Σ `open_n` = distance-to-freeing) + **closure-race** structure that cols 0-11 cannot
express; gate-zero residualizes against the already-present representation.

## GATE ZERO — correlation check (the free kill) — **PARTIAL**

FB (already-present block) = CL-037 aux `child_scalars` [12 base + 32 bag] + 4 farm-summary
scalars (48 dims). T = 14 tempo features. Unsupervised, all 314,911 rows.

**Full block FAILS** (structural counts wash into board structure, exactly as pre-registered):

| tempo feature | R²(·\|FB) | |
|---|---|---|
| open_road_count | 0.864 | ≥0.70 → dropped |
| open_city_count | 0.791 | ≥0.70 → dropped |
| farmers_opp | 0.737 | ≥0.70 → dropped |
| farmers_self | 0.724 | ≥0.70 → dropped |
| lockup_diff / opp / self | 0.465 / 0.462 / 0.440 | survive |
| open_city_delta_self / opp | 0.363 / 0.363 | survive |
| closure_race_diff | 0.233 | survive |
| lockup_depth_self / opp / diff | 0.181 / 0.127 / 0.094 | survive |
| contested_open_count | 0.072 | survive |

| statistic | full T | residualized survivors (10) | bar |
|---|---|---|---|
| mean R²(tempo_i \| FB) | 0.423 | **0.280** | < 0.50 |
| max R²(tempo_i \| FB)  | 0.864 ✗ | 0.465 | < 0.70 |
| ρ₁(T, FB) canonical corr | 0.964 ✗ | **0.758** | < 0.90 |

**Verdict: PARTIAL → proceed on the residualized survivor block (10 features).** The naive
structural counts (open-road/city, farmer counts) are ≥0.72 reconstructible from the
already-present representation and are dropped; the **timing-depth core survives** — the
depth-weighted lockup (Σ `open_n` = distance-to-freeing), closure-race, contested, and
open-city-delta features, mean R²=0.28, ρ₁=0.76. Gate-zero did its job: it stripped the
redundant structural counts and kept only the genuinely-novel tempo signal.
(`measurement/probe_5a/gate_zero_result.json`.)

## Stage 2 — 4-arm head at h6400 (only if gate-zero passed)

<!-- fill from scripts/probe_5a/verdict_5a.py -->

| arm | regret-red% | best α | net-alone τ | beats leaf |
|---|---|---|---|---|
| none (blind) | — | — | — | — |
| both (farm+bag) — **positive control** | — | — | — | — |
| tempo-only | — | — | — | — |
| all-three (farm+bag+tempo) | — | — | — | — |

- **Positive-control guard (§4):** `both` must reproduce CL-037's non-inert −20.5%
  (α=0.05); if inert, the gate is depth-invalid → read no null.
- **Δ_indep_tempo = regret_red(all-three) − regret_red(both) = — pp**
  (≥3pp CRACK · <1pp CEILING-EARNED · [1,3) WEAK LEAD).

## VERDICT

<!-- one of §7's four branches; state exactly what the autopsy sentence becomes -->

MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.
