# PROBE §5A — Tempo/timing third-axis gate — RESULTS

Status: **✅ RESOLVED (2026-07-04) — REAL-BUT-DOMINATED (non-circular, solver-scored; CL-040 Supported/high).**
> **RESOLUTION 2026-07-04:** 4 arms × 3 seeds retrained with saved weights (`7fa6e6e`) and scored vs the
> **exact K≤2 solver** on the same 1,119 roots as the M2 verdict (leaf baseline reproduces τ=0.6153 exactly).
> **tempo_only solver-τ 0.116/0.144/0.173 (mean 0.145)** = genuine non-circular sibling signal, ~7× the M2
> canonical value heads (0.02) → H-5A-inert stays refuted. **BUT dominated by the leaf everywhere** — best seed
> paired sign-z **−9.2** (112 better / 299 worse, +0.587 pts exact margin/root), τ 4× below the leaf's 0.615.
> The circular **+44.7% was a tail draw** (h6400-frame retrain spread +17.5/+21.1/+38.8). The `both` control
> bimodality **replicates in both frames** (s1 learns +21.4%/τ 0.110; s0/s2 collapse) → width-54 optimization
> fragility, not data corruption → the original single-seed cross-arm Δ_indep was never interpretable. **No route
> implication** (CL-034 washout precedent; the M2 KILL stands). Artifacts:
> `arms_retrain/solver_score_5a_arms.json` + per-run `summary.json`; results.csv `probe5a_arms_solver_rescore_4x3_n1119`.

Prior status: 🏁 CLOSED (2026-07-01) — INCONCLUSIVE (rigorous gate); gate-zero salvaged.
> **⚠️ CORRECTION 2026-07-01 (fresh-look review F4):** the h6400 oracle_q correlates **0.995**
> with the static v2.9 leaf, so the stage-2 `tempo_only` **+44.7%** below was scored against a
> near-copy of the leaf — the **circular frame** F4 flags as unreadable. Only **gate-zero** (the
> tempo-vs-farm/bag residualization) survives as non-circular. The "live offline lead" reading is
> **downgraded to circular-frame/unresolved**; §5A's valid question is **absorbed into M2**
> ([docs/POST_REVIEW_PLAN.md](../../docs/POST_REVIEW_PLAN.md) §4), scored against the **exact solver**.

Was: gate-zero correlation check first (free kill),
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

## Stage 2 — 4-arm head at h6400 (n_scalar=54, tempo appended to all arms)

**Single-seed (seed 0) run — INVALID as a gate read, but surfaced a strong lead:**

| arm | regret-red% | best α | net-alone τ | beats leaf |
|---|---|---|---|---|
| none (blind) | +0.0 | 0.0 | +0.010 | False |
| both (farm+bag) — **positive control** | **+0.0** | 0.0 | +0.001 | **False** ✗ |
| tempo-only | **+44.7** | 0.25 | +0.223 | True |
| all-three (farm+bag+tempo) | +17.5 | 0.25 | +0.120 | True |

**Why invalid:** the `both` positive control came back **inert (+0.0%)** — but the SAME
harness gives CL-037's `both` **+20.5%** at n_scalar=44. Appending 10 zero-variance tempo
columns (width 44→54) flipped it, an **RNG-init / normalization fragility**. The non-monotonic
`all_three (+17.5) < tempo_only (+44.7)` confirms single-seed training is noise-dominated.
Per §4's invalid-gate guard, no clean Δ_indep is readable from one seed.

**Leak check (`scripts/probe_5a/leak_check.py`): tempo_only's +44.7% is NOT a leak.** Every
tempo feature correlates with `oracle_q` at |r| ≤ 0.51, far below the leaf's own +0.996
(`lockup_diff` −0.51 is the max). So the tempo signal is genuine offline board information,
*larger* than farm/bag's 20.5% — tempo is emphatically **not** an inert/redundant axis.

**→ Seed sweep (`scripts/probe_5a/run_seedsweep.sh`, 4 configs × 4 seeds) LAUNCHED then OOM-KILLED
before ANY of the 16 runs finished** — concurrency-4 on the 41 GB WSL box (32 GB obs page cache +
4 training procs) OOM-restarted the VM. **NOT relaunched** (Joshua's call — start fresh). So **no
seed-swept Δ_indep exists.** (Aggregator `aggregate_seedsweep.py` is ready if it's ever re-run
solo/concurrency-2.)

## VERDICT — INCONCLUSIVE on the rigorous gate, but a live OFFLINE LEAD (not inertness)

**§5A did NOT confirm H-5A-inert.** The one axis uncorrelated-by-construction with farm/bag —
tempo/timing — was, at the single seed measured, the **strongest clean offline ranker in the whole
probe program** (`tempo_only` +44.7%, τ 0.223, leak-verified), *larger* than CL-037's farm/bag
−20.5%. So the autopsy **cannot** write "ceiling earned across three independent inert axes."

**But it did NOT rigorously confirm H-5A-live either.** The single seed had a broken positive
control (`both` +0.0% vs the harness's own +20.5%) and a non-monotonic arm ordering — init-noise —
so the pre-registered ≥3pp seed-swept Δ_indep was **never obtained** (sweep OOMed, not relaunched).

**Honest landing (maps to §7 between branch B and "gate could not fully run"):** tempo is a
**live, unresolved offline lead** — a value direction the v2.9 heuristic (flat meeple term) treats
crudely, which farm/bag did not capture. This **QUALIFIES CL-039's "genuinely low-dimensional"
clause** (that close rested on two known-redundant axes; the third was *not* redundant offline).

**The ship decision is UNCHANGED (analyzer + B1)** — per §7 (invariant across branches) AND because
this is an **OFFLINE** signal: CL-034's −41% offline washed out under search, so even a seed-confirmed
tempo crack is a *recorded lead, not a loop authorization*. If the AZ-value question is ever reopened,
the first step is the seed-swept tempo confirmation (run solo/concurrency-2), and **tempo — not
farm/bag — is where a future fair-from-scratch loop or scale-up would aim.**

MEASUREMENT ONLY — champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED. Governance: **CL-040** (qualifies CL-039).
