# PRE-REGISTRATION — move agreement vs search budget (does the champion's move converge?)

> **PRE-REGISTERED 2026-07-27, BEFORE ANY RESULT EXISTED.** Nothing above the Results
> section may be edited once results land; corrections go in a dated Results section.
> The read-out code (`scripts/measurement_infra/analyze_move_agreement.py`) is committed
> in the same commit as this document, so the metric definitions are fixed in advance too.
>
> **STATUS: ✅ COMPLETE 2026-07-28 — VERDICT = the search has NOT converged (H1 refuted),
> but the budget effect is small (~4pp) and this probe alone does NOT establish H2.** The
> ruler is implicated by **CL-060**, not by this probe. Claim **CL-070**;
> `results.csv move_agreement_k4_b28e9`; full pair matrix in
> [MOVE_AGREEMENT_REPORT.json](MOVE_AGREEMENT_REPORT.json). See the Results section at the
> foot of this document. Nothing above that section was edited after launch.

## Why

The blind budget curve (7 rungs, n=200 deck-paired each, band 70e9, candidate = the
classical champion at fixed `k_dets=4`, opponent = sighted RoD-v2 iter_02) rises steeply
to ~2064 sims and then goes **FLAT**. Every deck-matched step above 2752 is null on
**both** pre-registered statistics:

| step | wr z | margin z |
|---|---:|---:|
| 2752 − 2064 | +1.00 | −0.30 |
| 5504 − 2752 | −0.92 | −0.27 |
| 11008 − 5504 | +0.39 | +1.51 |

Two hypotheses explain that flatness and **no game-playing experiment against RoD2 can
separate them**, because both predict the same scoreline:

- **H1 GENUINE CONVERGENCE** — above ~2064 the search stops changing its chosen move, so
  extra sims cannot buy strength. The flatness is a property of the **agent**.
- **H2 INSTRUMENT COMPRESSION** — the champion keeps improving, but RoD-v2 iter_02 (a
  ~h3200-tier yardstick) is too weak to register it; elo against a fixed opponent
  flattens near the ceiling regardless. The flatness is a property of the **ruler**.

**H1 is directly measurable with no opponent at all**: does the FINAL SELECTED ACTION stop
changing as budget grows? This probe measures exactly that. It is diagnostic, not a lever.

## The design point the whole probe rests on — the same-budget noise floor

`FairHeuristicPriorAgent` is **stochastic**: it samples `k_dets` determinizations per move
(blind PIMC), so two runs at the SAME budget with different RNG disagree at some nonzero
rate. **A raw cross-budget disagreement number is therefore uninterpretable on its own**,
and this is built in from the start rather than bolted on.

The seed derivation makes two cleanly separated contrasts available:

```
det_seed_base(move_idx) = (seed*1_000_003 + move_idx*8191) & 0x7FFFFFFF
det_search_seed(move_idx, i) = det_seed_base(move_idx) + 100 + i
```

Neither depends on the sim budget. So **at a fixed agent seed, an agent at ANY budget draws
the SAME `k_dets` worlds with the SAME per-world search seeds.** Each root is therefore run
under **R = 3 independent seed lineages ("salts")**, giving, for position `i`, level `L`,
salt `s`, the deployed pick `a_i(L,s)`:

| statistic | definition | what it isolates |
|---|---|---|
| **D_paired(L1,L2)** | `E_i [ mean_s 1{a_i(L1,s) ≠ a_i(L2,s)} ]` | same salt ⇒ same worlds and seeds; **only depth varies**. Its same-budget null is **exactly 0** (a salt replayed at its own budget is bit-identical). Maximum power to detect "depth changes the move at all". |
| **D_same(L)** | `E_i [ mean_{s<s'} 1{a_i(L,s) ≠ a_i(L,s')} ]` | **THE NOISE FLOOR** — the agent's own run-to-run churn from resampled determinizations. |
| **D_cross(L1,L2)** | `E_i [ mean_{s≠s'} 1{a_i(L1,s) ≠ a_i(L2,s')} ]` | different budget AND different seed — **matched to the floor** (both vary worlds), so the comparison is apples-to-apples. |

⚠️ D_paired and D_same are **not** directly comparable (one holds worlds fixed, the other
does not). Comparing them would bias toward "converged". The matched contrast is D_cross
against the floor, via an exact null: if the per-position move *distributions* at L1 and L2
are identical (budget changed nothing about what the agent plays), then for independent
reseeds `D_cross = 1 − Σ_a p_a q_a` with `p ≡ q`, so

```
D_cross_null(L1,L2) = 1 − sqrt( (1 − D_same(L1)) · (1 − D_same(L2)) )
Delta(L1,L2)        = D_cross(L1,L2) − D_cross_null(L1,L2)
```

(the Cauchy–Schwarz equality case). **`Delta` is the decision-bearing quantity.** CI by
**position-level bootstrap**, B = 10 000 (positions are the independent unit; all salts and
levels within a position resample together). Bootstrap seed 20260727.

## Budgets

Fixed `k_dets = 4` — the clean axis from the curve. Seven **per-world** sim levels, whose
totals are the curve's seven rungs:

| per-world sims | 86 | 172 | 344 | 516 | 688 | 1376 | 2752 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **total budget** | 344 | 688 | 1376 | 2064 | **2752** *(deploy)* | 5504 | 11008 |

The task named 688/1376/2752/5504/11008; **2064 and 344 are included because they are free**
(see below) and 2064 is where the curve's knee sits. Reported pairs: every adjacent pair,
every level vs the deepest, and the floor at every level.

## Positions — the sampling frame

**Source: `measurement/champ_action_logs/champ_games.jsonl`** — 449 complete
`FairHeuristicPriorAgent` self-play games at **exactly the deploy budget** (k4×688 = 2752,
exact-K≤2, leaf `v2_9_2_Bmild_cap8_curve125`, runtime hash `6dfffd57051690f2`), seed band
28e9, each carrying the full `(deck_seed, actions)` action log. Round-trip proven lossless
(`CORPUS_MANIFEST.json`: 25 full-game replays + 1448 per-ply `string_representation`
comparisons, 0 mismatches). These are **realistic in-play positions from the champion's own
distribution**, which is the requirement.

⚠️ **The blind-curve game records CANNOT be used for this.** They were checked first: their
`moves` field is an integer **count** (e.g. `144`), not an action sequence — the records
carry `seed`, `deck_hash`, `a_seat`, scores and timings only. There is no way to replay them
to an arbitrary position. The champion action-log corpus is the correct and available frame.

**Census** (deterministic, no search): all 449 games replayed ply-by-ply → **64 610 plies**,
of which **57 675 (89.3%)** are eligible.

- **Eligibility:** `n_legal ≥ 2`. Forced moves are excluded because `_pimc_move`
  short-circuits them without searching at all — they are trivially in agreement at every
  budget and would dilute the headline.
- **Sample:** uniform without replacement over eligible plies, **max 2 per game** (bounds
  within-game correlation), **sampling seed 20260727**.
- ⚠️ **PRE-LAUNCH CORRECTION (2026-07-27, before any record was computed).** This section
  originally asked for **n = 1000**, which is *inconsistent* with the max-2-per-game cap:
  449 games × 2 = **898** is the maximum the cap allows. Resolved in favour of the **cap**,
  because bounding within-game correlation is the load-bearing design choice and 898 vs 1000
  is a negligible power difference. **The realized sample is n = 898 roots drawn from all
  449 games.** No results existed when this was changed.
- **Realized strata** (recorded before the probe ran): phase early 298 / mid 312 / late 288;
  engine phase TILES 495 / MEEPLES 403; median `n_legal` = 11; median `h200_top2_q_gap` =
  0.032; **25 roots are solver-region** (`k_remaining ≤ 2`) and will be excluded at read-out
  per the rule below, leaving **873** analysable positions.
- Roots are consumed via the measurement-infra lossless `(deck_seed, action_sequence, ply)`
  contract (`root_replay.replay_actions`), with a per-root `string_representation` checksum
  verified at both sample time and probe time.

**Exclusions at read-out (pre-registered):** records with `ok != True`; `n_legal < 2`;
and **`solver_region`** roots — `choose_action` latches to the marginalized exact solver at
`k_remaining ≤ exact_max_k = 2` and stays latched, so those decisions are budget-independent
*by construction* and would inflate agreement for an uninteresting reason. They are counted
and reported separately, never silently pooled.

## Stratification

Agreement pooled over trivial positions would hide the effect, so two strata are registered
in advance.

1. **Decision criticality — PRIMARY stratifier: `h200_top2_q_gap`**, the measurement-infra
   standard tag (`scripts/measurement_infra/tagging.py`): `HeuristicMCTS(200)`'s top-2
   backed-up Q gap, **median split** over the analysed positions. It is deliberately
   **exogenous** — a different search family (random-expansion UCT) and clairvoyant (it sees
   the true deck), so it cannot be a restatement of the fair-PIMC quantity whose stability is
   being measured. It is a position descriptor and is **never shown to the agent under test**.
   **SECONDARY / robustness: `blind_top2_q_gap`** — a blind fair-PIMC k4×86 (total 344)
   pooled top-2 Q gap computed on a **dedicated tag seed lineage (salt 9000/9001), disjoint
   from the probe salts 1–3**, so it is independent of the picks it stratifies. Both are
   recorded; the primary is fixed here and cannot be swapped after seeing results.
   **If budget matters anywhere it is in the narrow-gap stratum**, and that is where the
   headline must be read.
2. **Game phase** — fixed cut points on `k_remaining` (undrawn deck + tile in hand), NOT
   sample quantiles, so boundaries cannot drift: **early ≥ 48, mid 24–47, late < 24**
   (base deck is 72 tiles). Reported additionally split by engine phase (TILES vs MEEPLES).

## Infra note — the snapshot claim was VERIFIED, not assumed

`scripts/measurement_infra/` advertises multi-depth snapshot search ("one deep search → all
sim levels, bit-exact"). **That guarantee is written for the clairvoyant `HeuristicMCTS`
path and does NOT automatically cover per-determinization fair PIMC.** It was therefore
re-established for this agent rather than inherited, and is proven per run by two flags:

- `--verify-bit-exact` — re-runs every world standalone at every level and asserts the visit
  vectors equal the snapshot. Bit-exactness holds **within a world** (each world is an
  ordinary serial `NeuralMCTS` on its own fixed reshuffled board with its own fixed seed);
  it is not claimed across worlds, and does not need to be, because a fixed salt draws the
  same worlds at every level.
- `--verify-agent-parity` — runs the **real** `FairHeuristicPriorAgent._pimc_move` at the
  deepest budget and asserts it returns the action the harness reports as the deepest
  level's deployed pick. This is the strongest available check: it proves the harness
  reproduces the **deployed decision**, not merely a plausible one.

**Pre-launch smoke (throwaway sampling seed 999999, disjoint from the real seed; discarded
and not part of the sample): 5/5 roots passed BOTH checks — `BE=True`, `PARITY=True` at all
seven levels × four worlds.** The full run re-verifies on a subset.

Because the claim holds, the whole 7-rung ladder costs what its **deepest rung alone** would
(k_dets searches per salt, not k_dets × n_levels).

## Decision rule

**PRIMARY: `q_argmax_action` = `pooled_q_argmax`** (pooled Q = ΣW/ΣN, `min_pooled_visits`
floor, (Q,N,−a) tiebreak) — **this is the deployed fair pick.** `played_action` (argmax
pooled visits) is recorded too and **both are reported**; quoting only whichever is more
flattering is how three findings in this project were later overturned.

## Read-out rules and what each outcome MEANS (pre-registered)

Headline is read on **`D_paired(2752, 11008)`** and **`Delta(2752, 11008)`**, both overall
and **in the narrow-gap stratum**, with every pair reported.

1. **SUPPORTS H1 — GENUINE CONVERGENCE.** `D_paired(2752,11008) ≤ 0.05` **and**
   `Delta(2752,11008)`'s 95% CI covers 0, **and both hold in the narrow-gap stratum.**
   ⇒ Above deploy the agent is choosing the same move; extra sims cannot buy strength; the
   flat curve is a property of the agent, and budget is a **closed lever** — consistent with
   the Pareto curve's "everything you can spend is already spent".
2. **SUPPORTS H2 — INSTRUMENT COMPRESSION.** `D_paired(2752,11008) ≥ 0.10` **or**
   `Delta(2752,11008) > 0` with a 95% CI excluding 0 — especially in the narrow-gap stratum.
   ⇒ The move is still changing with budget, so the flat curve is telling us about our
   **ruler**, not our agent. The consequence is a **measurement** action (a stronger,
   non-saturated reference is required to price budget above 2752), not a strength claim.
3. **H1-WEAK / INDIFFERENCE — a distinct, named outcome, registered so it cannot be spun
   either way.** `D_paired(2752,11008)` is clearly > 0 **but** `Delta(2752,11008)` ≈ 0
   (CI covers 0). ⇒ Depth changes the move, but **no more than a reseed does**: the extra
   compute is churning among moves the agent treats as interchangeable rather than
   concentrating on a distinguished one. This is evidence *for* the weak form of H1 (budget
   is not converging on something new) but it does **not** rule out that the churned-to moves
   are systematically better. If this is the outcome, say so plainly; do not report it as
   either 1 or 2.
4. Report the **absolute** disagreement levels, not only the contrasts — a floor of 0.02 and
   a floor of 0.40 imply very different things about the agent even at the same `Delta`.
5. **Both decision rules, every pair, both strata, and the excluded-root counts** are
   reported regardless of which way the headline goes.

### ⚠️ What this probe does NOT measure (registered to prevent over-claiming)

**Agreement is stability, not quality.** This measures whether the move *changes*, never
whether it is *better*. A converged agent can be converged on a mistake — which is exactly
the standing project thesis that the hand-crafted leaf eval caps learned strength by
construction. So an H1 result establishes **"budget is not the lever"**, and specifically
does **NOT** establish that the champion is at its strength ceiling, nor that the leaf,
width, or any other axis is exhausted.

## Validity guards — the probe is INVALID, not merely negative, if any fire

- **The floor swallows the signal.** If `D_same ≥ 0.5` at either of the top two budgets, the
  deployed pick is near a coin-flip among several moves under reseeding, `D_cross` saturates,
  and `Delta` loses the power to resolve anything. Then the argmax metric is the wrong
  instrument and the result is reported as **INVALID / unresolvable** — not as convergence.
  (This is the failure mode the task flagged, and it is a real possibility for a PIMC agent.)
- Any `--verify-bit-exact` root reporting `BE=False`, or any `--verify-agent-parity` root
  reporting `PARITY=False`.
- `> 2%` of records failing (`ok != True`), or any `wall_hit`.
- `< 80%` of sampled positions ending with ≥ 2 complete salts (the floor needs pairs).
- Any record whose `checksum_ok` is false (replay drift).
- `fair_agent` / `mcts` resolving outside the pinned source root (the harness asserts this at
  startup via `CARC_REQUIRE_SRC_ROOT` and records `__file__` in the manifest).
- The stratifier failing to separate — if narrow- and wide-gap floors are indistinguishable,
  the criticality split is uninformative and must be reported as such rather than leaned on.

## Nothing is promoted

This is a **diagnostic**, not a lever. `governance/PRODUCTION.yaml` and the champion are
**untouched** whatever the result. No configuration change follows from this run on its own;
under outcome 2 the follow-up is a measurement build (a stronger reference), and under
outcome 1 or 3 the follow-up is to stop pricing budget and move the search elsewhere.

## Code provenance — how "the same agent the curve measured" is guaranteed

The blind curve was produced at commit **c72053a**. Both boxes run source verified
byte-identical to it:

- **Local**: the pinned worktree `/home/doctor/projects/carc-pinned-c72053a`
  (`.venv` + `rust/carc-orch/target` symlinked, Cython `.so` copied in), reached via
  `CARC_SRC_ROOT`, with `CARC_REQUIRE_SRC_ROOT` asserting at startup that
  `carcassonne_ai.fair_agent.__file__` and `carcassonne_ai.mcts.__file__` resolve inside it.
- **Laptop**: its main tree is *already checked out at c72053a* (`HEAD=c72053ab8`, clean on
  `src/` and `engine/`), so it needs no worktree.
- **Verified, not assumed:** `fair_agent.py` / `mcts.py` / `champion_factory.py` /
  `heuristic_prior_mcts.py` md5-match across the two boxes, and the git tree hashes agree —
  `HEAD:src = 3cdae219feebe9c6719ea5cca88070187cf7f726`,
  `HEAD:engine = 54182632722e34081bdcd230f01e5816a7688dfc`.

The three harness scripts are new (they do not exist at c72053a) and are committed on the
working branch; on the laptop they are dropped in as **untracked** files so the tracked
c72053a tree is not disturbed. They import the agent through `champion_factory`, never a
hand-rolled config.

⚠️ Another session was editing `fair_agent` / `mcts` / `champion_factory` /
`heuristic_prior_mcts` / `eval_fair_puct.py` in the **main** tree today (an `--intra-reuse`
feature). Checked rather than trusted: `git status` shows `src/` clean and `git diff --stat`
empty, and the pinned tree has no `_intra_reuse` at all. The harness additionally **refuses
to run** if the constructed agent reports `_meeple_dedup` or `_intra_reuse` enabled, because
this harness mirrors the pinned `_pimc_move` and would silently diverge from a knob it does
not model.

## Operational

Pure CPU — the champion is classical: **no net, no GPU, no carc-orch, no OMP-pin concern**.
All workers `nice -n 19`, all runs `setsid nohup … & disown`.

**Work-stealing across both boxes** on the share via atomic `O_EXCL` `.claim` files
(`/mnt/c/carc-shared` locally, `/mnt/carc-shared` on the laptop), one record per
(root, salt), fully resumable.

⚠️ If the run is killed, **clean stranded `.claim` files before resuming**
(`--clean-stale-claims`) — a killed shared-claim run otherwise stalls a resume forever.

**Jobs:** 898 roots × 3 salts = **2694 records**.

**ETA — benched, not extrapolated.** A 16-job smoke at production knobs (W16 local, all
seven levels, k4×2752 deepest) measured **mean 21.2 s/job** ⇒ steady-state **≈ 2 700 jobs/h
local at W16**. The laptop (12C/24T, W10) is unbenched for this workload and is expected to
add roughly 1 000–1 500 jobs/h. Combined **≈ 3 700–4 200 jobs/h ⇒ ~40 min** for 2694
records; local-only fallback ≈ **1.0 h**. Both are inside one sitting, and the run is
resumable with work-stealing, so
a laptop shortfall costs wall-clock only.

Cost is dominated by the deepest rung: the snapshot means the seven-rung ladder costs what
11008 alone would, i.e. ~7× cheaper than running each level standalone.

---

# Results

**2026-07-28 — VERDICT: THE SEARCH HAS NOT CONVERGED (pre-registered H1 REFUTED). But the
budget-attributable effect on the pick is SMALL (~4pp), and this probe ALONE does not
establish H2.**

> ⚠️ **CORRECTION, 2026-07-28, before any of this was committed.** The first draft of this
> section read "H1 refuted ⇒ H2 established". **That is a false dichotomy, and it was baked
> into the pre-registration above** (which is left unedited, as the rules require). Joshua
> caught it with the obvious question: *if these disagreements are consequential, how does
> the 11008 agent barely beat the 2752 agent?* A **third** explanation fits everything below
> — the move changes, but the change is nearly **strength-neutral**. This probe measured
> whether the pick MOVED, never whether it IMPROVED, so it cannot separate those two.
> What implicates the ruler is **CL-060**, not this probe (see "What this licenses" below).

Run: 898 roots sampled, 25 solver-region excluded per the pre-registered rule → **873
analysable**; 7 levels × 3 salts = **2694 records, 0 failed**, 75 records excluded. Verify
cell **41/41** on both `--verify-bit-exact` and `--verify-agent-parity`. Bootstrap B=10 000,
seed 20260727. Stratifier median `h200_top2_q_gap` = 0.033854.

## Headline — `D_paired(2752, 11008)` and `Delta(2752, 11008)`

| | n | `D_cross` observed | `D_cross_null` (reseed alone) | **Delta** = budget's own | 95% CI | z | `D_paired` |
|---|---:|---:|---:|---:|---|---:|---:|
| **Overall** | 873 | 0.3039 | 0.2644 | **+0.0396** | [0.0283, 0.0517] | 6.72 | 0.2398 |
| **Narrow-gap** *(headline stratum)* | 437 | 0.4622 | 0.4053 | **+0.0570** | [0.0374, 0.0776] | 5.57 | 0.3699 |
| Wide-gap | 436 | 0.1453 | 0.1235 | +0.0218 | [0.0112, 0.0338] | 3.76 | 0.1093 |

⚠️ **Read `Delta`, not `D_paired`.** Reseeding *alone*, at fixed budget, already produces
**26.4%** disagreement; observed cross-budget is 30.4%. So budget contributes **+4.0 points
— 13% of the disagreement**, and the other 87% is the agent's own churn. `D_paired` (worlds
held fixed) is the maximum-power detector of *"does depth change anything at all"*; it is
**not** the size of the budget effect and must not be quoted as one.

Rule 1 (H1) required `D_paired ≤ 0.05` **and** `Delta` CI covering 0. Rule 2 (H2) required
`D_paired ≥ 0.10` **or** `Delta` CI excluding 0. **Both H2 conditions hold, overall and in
the narrow-gap stratum.** Rule 3 (H1-WEAK / INDIFFERENCE) requires `Delta ≈ 0` with the CI
covering 0 — that **does not occur in any stratum**: `Delta`'s CI excludes 0 for both gap
halves, all three game phases (early +0.0246 z 2.84 · mid +0.0233 z 3.26 · late +0.0758
z 5.40) and both engine phases (TILES +0.0474 z 5.67 · MEEPLES +0.0295 z 3.68).

⇒ **The search has not converged: budget still shifts the pick by ~4 points beyond reseed
noise, decisively (z 6.72).** That refutes H1. It does **not** by itself say the flat curve
is the ruler's fault — see below.

## Secondary findings

**1. The noise floor GROWS monotonically with depth** — more search means *more* run-to-run
churn, not less. This is why the matched null was load-bearing rather than decorative: a raw
cross-budget disagreement number would have been badly misread here.

| total budget | 344 | 688 | 1376 | 2064 | 2752 | 5504 | 11008 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `D_same` | 0.1226 | 0.1615 | 0.2043 | 0.2089 | 0.2272 | 0.2684 | 0.2997 |

**2. ⚠️ The validity guard passed, but narrowly in the headline stratum.** The pre-registered
guard voids the probe if `D_same ≥ 0.5` at the top budgets (argmax would be the wrong
instrument). Overall `D_same(11008)` = 0.2997 ✅ — but **narrow-gap `D_same(11008)` = 0.4493**,
under the line and close to it. The stratum carrying the headline is approaching the
instrument's own limit. **Quote both; never the overall figure alone.**

**3. Volatility is lowest at deploy and rises above it.** Adjacent-step `D_paired` falls to a
minimum at 2064→2752 and then climbs again:

| step | 344→688 | 688→1376 | 1376→2064 | 2064→2752 | 2752→5504 | 5504→11008 |
|---|---:|---:|---:|---:|---:|---:|
| `D_paired` | 0.2104 | 0.1764 | 0.1466 | **0.1218** | 0.1749 | 0.1810 |
| `Delta` | +0.0866 | +0.0497 | +0.0214 | +0.0179 | +0.0173 | +0.0206 |

Every adjacent `Delta` CI excludes 0. Full pair matrix (all 21 pairs × 8 strata):
[MOVE_AGREEMENT_REPORT.json](MOVE_AGREEMENT_REPORT.json).

## What this licenses, and what it does not

**Licensed by THIS probe:** the flat top of the blind curve (CL-069) and the self-anchored
Pareto curve (CL-068) **cannot be attributed to the agent having converged**. That is the
whole of it.

**NOT licensed by this probe — that the flatness is instrument compression.** The probe
never measured move *quality*, so "the move changes but the change is worth almost nothing"
survives it untouched. Two facts actively support that reading:

- **The agent disagrees with itself 30.0% of the time at 11008** at *fixed* budget (44.9% in
  the narrow-gap stratum). A move set it cannot rank stably across seeds is close to by
  definition a set of near-equal moves — which is exactly why 30% self-churn does not
  destabilise its measured strength.
- **Budget's own share of the disagreement is 13%.** The headline effect is 4 points, not 24.

**What DOES implicate the ruler is CL-060, not this probe.** The same pair of agents,
measured two ways, disagrees by ~70 elo:

| 11008 vs 2752, measured by | result |
|---|---|
| direct head-to-head — `cl060_h2h_k8x1376_vs_deploy_k4x688`, n=400 paired, 221W–164L–15D | **+49.85 ± 17.55** |
| via RoD-v2 as ruler — this band, deck-matched (11008 +105.6, 2752 +127.0) | **−21.4**, wrong sign, n.s. |

**The honest synthesis — the exchange rate.** ~4 points of budget-attributable move change
buys ~+50 elo. Real, but thin for 4× the compute: *weakly* consequential, not "deeper search
finds much better moves". The practical decision stands either way — **RoD-v2 cannot price
budget above 2752, so stop buying budget rungs graded against it** — but it rests on CL-060's
contrast, not on this probe.

**The successor experiment this points at**, and it needs no game-playing opponent: take the
positions where 2752 and 11008 disagree and score **both** picks against a stronger reference
(the exact solver where `k_remaining` allows, or a much deeper search). That converts "the
move changed" into "the move improved" and prices budget directly, sidestepping structural
blocker #1 for this one question.

Nothing here promotes anything; `governance/PRODUCTION.yaml` is untouched.
