# DESIGN / PRE-REGISTRATION — C1 OUTCOME PRICING

> **⚠️ Status: DESIGN ONLY — FROZEN, PRE-OUTCOME, NOT LAUNCHED.** This file, the
> frozen target set ([`targets_c1.jsonl`](targets_c1.jsonl) /
> [`TARGETS_C1.json`](TARGETS_C1.json)) and the whole instrument are committed
> **before any C1 continuation outcome exists anywhere**. House two-commit
> pattern: this commit is the FREEZE.
>
> ⚠️ **[`PINNED_SRC_REV.json`](PINNED_SRC_REV.json) is deliberately left at
> `PENDING_FREEZE_STAMP` by the freeze commit, and MUST be stamped from `main`
> AFTER the merge** — `bash measurement/c1_pricing_prep/stamp_pinned_rev.sh`,
> committed alone. The gate exists to prove local and laptop are running the same
> bytes, so it has to pin the sha both boxes will actually sit on; a sha from a
> pre-merge branch would make `run_c1.sh` refuse on `main` (fail-closed, by
> design). Deviations after the freeze go in a `DEVIATIONS.md`, never here.
>
> **No band is claimed.** This instrument plays no fresh competitive games: every
> game it plays is a continuation of an already-archived E4 position, and the
> only randomness it introduces is a throwaway permutation of the unseen deck
> tail. It therefore takes no row in `governance/BAND_REGISTRY.csv` — exactly as
> [`../e4_continuation_20260828/PREREG.md`](../e4_continuation_20260828/PREREG.md)
> did. The world salts are documented in §3 and are retired after this run.
>
> **No governance edit, no `experiments/results.csv` row, no launch is authorised
> by this file.** Owner authorisation for the *work* (2026-08-28, verbatim: *"yes
> to both"*); the launch window is post-A2.

## 0. The question, and why it is the only currency left

[`../microgates_20260828/READOUT.md`](../microgates_20260828/READOUT.md) closed
GATE-LIVE: the tier1-greedy rollout policy is not contest-blind (`R_contest`
0.678), and the terminal-grounded re-ranker is genuinely opinionated — its pick
differs from the production champion's full search at **63.9 %** of contested
plies. Its own last paragraph names the next step and refuses to fund C1 on that
evidence:

> *"A disagreement rate of 0.64 says the re-ranker moves a lot of plies; it says
> nothing about whether it moves them in the right direction… The correct next
> step is not to fund C1 — it is to price a small, judge-free sample of C1's own
> re-rankings against realized game outcomes."*

**This is that instrument.** It asks exactly one thing:

> **At the banked crux plies where the tier1-rollout re-ranker's pick differs
> from the production champion's, is the re-ranker's pick worth MORE REALIZED
> POINTS — CRN-paired continuations played to termination by the production
> champion in both seats, from the divergent ply onward?**

Nothing here scores a position. There is no judge, no evaluation function, no
search score anywhere in the estimator. That is deliberate: the F4 lesson
(auto-memory `reference_evloss_grader`) is that **judged headroom is
family-relative** — the same +1.49 pts/ply clair-family ceiling read −0.64
(z −3.8) under an out-of-family judge on the same CRN worlds. A realized final
score has no family.

### 0.1 And it is simultaneously the cross-fit that de-biases the microgate

The microgates' `rollout_argmax` is an **argmax over ~7.7 arms of a mean taken
over 16 CRN worlds**, and READOUT §3 flags the consequence in bold: with M = 16
the per-arm SE is several points, so that argmax carries a winner's curse. The
frozen selection statistic — `arm_values[c1] − arm_values[champ]`, the *in-sample
gap* — averages **+6.208 pts** over the 188 divergent plies (+6.000 on
`farm_capture`). If that number were real, C1 would be a six-point-per-ply lever
and the program would be over.

This instrument re-measures the identical contrast **on worlds the argmax never
saw** (§3). The difference between the two is, by construction, the winner's
curse — and it is a pre-registered readout, not an afterthought (§4.4).

### 0.2 Why `farm_capture` is the primary

It is the **only stratum where the rollouts side decisively with the human
against the production champion** (`D_owner` 0.192 vs `D_champ` 0.538), it is
where the 2026-08-25 Stage A located the mechanism ("farm-steal, one missing leaf
term"), and it is the one thread `e4_continuation_20260828` left unpromoted
(+2.53, z 1.68, n = 12). **Three independent instruments point there.** It is
also, by a factor of ten, the cheapest stratum to price (§6) — its plies sit at
mean ply-fraction 0.79, so its continuations are 31 plies long instead of 80.

## 1. What is frozen here

### 1.1 The target ply set

Built by [`build_c1_targets.py`](build_c1_targets.py) from two banked artifacts
and nothing else:

* `../microgates_20260828/MICROGATES.json` → `G2.plies` — `rollout_argmax` (the
  C1 pick), `counterfactual_action` (the banked production-champion pick),
  `played_action` (the archive's own move), `arm_values`, `spread_pts`;
* `../e4_ply_pricing_20260827/targets.jsonl` — the decision fields the runner
  needs (`k`, `phase`, `actor`, `n_plies`, `ply_frac`).

`selftest_c1.py::test_selector_reads_no_outcome_field` asserts at code level that
the selector's source does not mention `winner` / `final_scores` /
`recorded_scores` / `margin` / `realized` / `delta_pts_mover` / `price_` /
`scores_at_ply` / `regret`. **Outcome-blind by construction.**

| stratum | plies | games | Σ remaining plies | mean rem | mean in-sample gap | k median | K ≤ 4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`farm_capture`** (PRIMARY) | **14** | 12 | 436 | 31.1 | +6.000 | 19 | 1 |
| `invasion` | 55 | 34 | 4 416 | 80.3 | +5.746 | 43 | 1 |
| `defense` | 61 | 37 | 4 852 | 79.5 | +6.736 | 41 | 2 |
| `control` | 58 | 37 | 4 782 | 82.4 | +6.142 | 47 | 0 |
| **total** | **188** | **45** | 14 486 | 77.1 | +6.208 | — | 4 |
| *contested* (`invasion` ∪ `farm_capture`) | *69* | *41* | *4 852* | *70.3* | *+5.797* | — | *2* |

**Exclusions, all outcome-blind and all stated here rather than discovered
later** (`TARGETS_C1.json.excluded`):

* **89 agreeing plies** (`rollout_argmax == counterfactual_action`). Their two
  arms would be byte-identical, so their paired price is **exactly zero** with no
  compute and no sampling error. They are not dropped from the *estimand* — they
  are folded back analytically as the policy-level price (§4.3). This is
  arithmetic, not a filter.
* **10 `walled` and 3 `app_aug2` plies.** `app_aug2` is the pre-`fixed_v1` phone
  build, which runs **R9 OFF** — a different farm adjacency, hence a different
  farm decomposition (microgates READOUT §2.4 measured `R_farm` 0.021 there
  against 0.44 in the primary pool). `walled` contributes **zero `farm_capture`
  divergent plies**, so it cannot inform the primary, and 6 plies in 2 games
  cannot be reported apart with a straight face. Admitting either would also
  force a second R9-latched process group for no gain. Excluded, named, done.

### 1.2 The rules-epoch discipline (binding, inherited unchanged)

One rules profile: **`fixed_v1`**. The runner re-resolves the profile FROM EACH
ARCHIVE via `analyzer.ev_loss.resolve_profile_name` and hard-fails on any drift
from the frozen target's stamp. An explicit `rules_profile` stamp wins outright;
its ABSENCE is positive evidence of a pre-`fixed_v1` build. **Never identify a
build from `(start_rule, grid_rule)`.** R9 is import-latched, so one process per
profile group and `prepare_env` before any `carcassonne_ai` import; the
observed-vs-expected latch is stamped on every unit (`r9_env`). Budget epoch
(`budget_note`, `played_sims_effective`, `played_k_dets_effective`) is carried
per row from the archive — the E4 anchor is nonstationary and no tally may be
read without it.

### 1.3 Pre-registered constants

```
# build_c1_targets.py  (asserted by selftest_c1.py::test_build_constants_match_the_design)
WORLD_BASE = 16
M_BASE     = { farm_capture: 32, invasion: 16, defense: 8, control: 8 }
EXTENSIONS = [ E1 farm_capture +32, E2 invasion +16, E3 defense+control +8 ]
PROFILE    = fixed_v1

# inherited UNCHANGED from continue_plies.py (the frozen runner)
WORLD_SEED        = 20260828
CONTINUATION_SEED = 0

# operating (D-1 precedent from e4_continuation, carried — §2.4)
ARM_CAP_S = 1800 ; MEM_CAP_GB = 4 local / 3 laptop ; THREADS = 1 ; CHUNK = 4
W_LOCAL = 30 ; W_LAPTOP = 22            (owner-directed, 2026-08-27)

# adjudicate_c1.py bars (asserted by selftest_c1.py::test_prereg_bars_match_the_code)
ALPHA = 0.05 ; SE_PRECISION_BAR_P2 = 1.2 pts ; VOID_WORLD_RATE = 0.10
CO_PRIMARIES = (P1_farm_capture, P2_contested)
```

## 2. The measurement — what is reused, verbatim

**The entrypoint is
[`../e4_continuation_20260828/continue_plies.py`](../e4_continuation_20260828/continue_plies.py),
UNMODIFIED.** Not forked, not patched, not copied — `run_c1.sh` invokes that
file at that path, and `selftest_c1.py::test_run_script_points_at_the_unmodified_runner`
fails if a local copy ever appears in this directory. Every physical mechanism —
world installation, the three deck guards, the Rust mirror's `check_sync`, the
CRN witnesses, `RLIMIT_AS`/`RLIMIT_CPU` isolation, atomic per-unit writes,
resumability — is therefore the *same code that produced the 2026-08-28
continuation verdict*, with the same bugs and the same guarantees.

Exactly two things differ, and both live in data, not code:

1. **which two actions occupy the arm slots** (`targets_c1.jsonl`), and
2. **which world indices are drawn** (`plan_c1.py` emits units at world ≥ 16).

### 2.1 ⚠️ THE ARM-SLOT REMAP — read this twice

The runner hard-codes two arm names. This instrument remaps what they hold:

| runner's slot | runner's label | **what it holds here** |
|---|---|---|
| `t["played_action"]` | `arm_owner` | **the C1 pick** (`rollout_argmax`) |
| `t["counterfactual_action"]` | `arm_cf` | **the production champion's pick** |

so the runner's own `delta_pts_mover`, unchanged and mover-signed, reads as
**C1 pick − champion pick**: positive iff the re-ranker's move was worth more
points TO THE MOVER, at either seat.

**A unit row emitted by this run will say `arm_owner` and it will NOT be an owner
move.** That is the single most misreadable thing in the instrument, and the
program's own standing lesson is that field NAMES lie (auto-memory
`feedback_verify_numbers_before_reporting`: `champ_prefix_ms_per_move` is the
*candidate* side). Three mitigations, all mechanical:

* every target row carries `arm_map`, `c1_action`, `champ_action`, `owner_action`;
* `run_c1.sh`'s per-block sentinel and `adjudicate_c1.py` both **assert on every
  landed row** that `played_action == c1_action` and
  `counterfactual_action == champ_action`, and a violation is an instrument VOID
  (§5), not a warning;
* [`READ_RULE.md`](READ_RULE.md) §1 says it in bold, first.

`followup_agrees_with_archive`, which the runner computes by comparing the
`arm_owner` continuation's first follow-up to the archive's next action, is
**meaningless in this instrument** (the `arm_owner` slot no longer holds an
archive move). It is descriptive-only in the runner, the adjudicator does not
read it, and no readout quotes it.

### 2.2 The CRN pairing, and the witness that proves it

Held IDENTICAL across a unit's two arms by construction, each with a witness the
adjudicator hard-checks: the **root state** at the target ply (`root_repr_sha`,
`n_drawn_prefix`, `n_legal_root`), the **world's deck completion**
(`world_deck_sha`, `world_deck_len`; `world_rng(deck_seed, ply, world)` contains
**no arm term**, and that absence IS the CRN guarantee), and the **policy's
randomness** (`det_seed_base_at_root`, `move_idx_at_root`). What necessarily
differs is the board after the arm move. That is the treatment.

**Any witness mismatch VOIDS the pair** — the arms did not share a root or a
world, so their difference is not a paired contrast. A void is a skip, never a
price, and never a finding.

### 2.3 The estimand, stated exactly

Only the target ply's action is forced. Everything after it, in both arms —
including the meeple follow-up belonging to the same tile — is the production
champion's own choice, both seats. So:

> **the value of the C1 pick over the champion's pick at that ply, under
> subsequent production-champion play by both seats.**

That is what a deployed C1 would actually buy: a re-ranker changes ONE decision
and then the champion carries on. The alternative (also forcing a follow-up) is
deliberately not taken, for the reason
[`../e4_continuation_20260828/PREREG.md`](../e4_continuation_20260828/PREREG.md)
§2.3 gives.

The continuation policy is the production champion of record —
`governance/PRODUCTION.yaml` `champion.fair_deploy` — built through the same
audited construction; `rust_threads` is execution-only (bit-identical merge at
threads {1,4,8}).

### 2.4 Caps and isolation

Per-arm forked child under `RLIMIT_AS` and `RLIMIT_CPU`, plus a parent wall
backstop; an arm over either cap is `TIME_SKIPPED`/`OOM_SKIPPED` and **voids its
unit's pair**. **`ARM_CAP_S = 1800` is carried from `e4_continuation`'s D-1
deviation rather than the 600 in its PREREG**, with reason: 1800 s ran 728 units
× 2 arms at W30+W22 with **0/1456 attrition**, and the cap is a CPU cap while
DRAM contention is charged to CPU time. Headroom here is larger, not smaller —
the worst stratum's arm is ~80 continuation decisions at ~1.16 s solo ≈ 93 s CPU,
i.e. ~19× under the cap, and the primary stratum's arms are 31 decisions.

## 3. ⭐ The world split — the salt, stated numerically

**The cross-fit is a world-INDEX split, not a seed change.** `WORLD_SEED` stays
at its inherited 20260828 and `world_rng` is untouched; what changes is the world
index, which enters the generator as `world * 104729`:

| instrument | worlds | status |
|---|---|---|
| `e4_continuation_20260828` | 0 – 7 | banked |
| `microgates_20260828` (the argmax was selected on these) | 0 – 15 | banked |
| **this run — base block** | **16 – 47** (`farm_capture`) · **16 – 31** (`invasion`) · **16 – 23** (`defense`, `control`) | new |
| elasticity `E1` `farm_capture` | 48 – 79 | new |
| elasticity `E2` `invasion` | 32 – 47 | new |
| elasticity `E3` `defense`, `control` | 24 – 31 | new |

Every world this instrument draws is disjoint from every world any prior
instrument drew (`selftest_c1.py::test_every_world_this_instrument_draws_is_new`
fails otherwise, and `adjudicate_c1.py` voids on any landed unit with
`world < 16`). Choosing an index range rather than a new seed is deliberate: it
requires **zero change to the frozen runner**, and its disjointness is
inspectable by eye rather than by trusting a hash.

⚠️ At small K the *distinct-completion* set is smaller than M — a ply with 4
unseen tiles has far fewer than 32 distinct worlds, so its 32 draws contain
duplicates. The paired estimator stays unbiased (it converges on the exact mean
over that ply's finite world set, which is the estimand); its SE simply stops
shrinking as 1/√M. One `farm_capture` ply has K = 4 and one has K = 6;
`world_deck_len` is recorded per unit and the achieved-M histogram is a
pre-registered readout (§4.5).

## 4. Pre-registered readouts

### 4.1 The estimator

* **A ply's price** = the unweighted mean of its landed CRN worlds'
  `delta_pts_mover`, pooled over the base block and every completed elasticity
  block (the extension worlds are pre-registered index ranges and their landing
  is not outcome-dependent, so pooling is a plain mean, not a re-weighting).
* **A stratum's price** = the unweighted mean over its plies with a
  **cluster-robust SE clustered on GAME** (188 plies live in 45 games).
* The helpers are **imported** from
  [`../e4_continuation_20260828/aggregate.py`](../e4_continuation_20260828/aggregate.py)
  — `collapse_worlds`, `cluster_stats`, `contrast` — not re-implemented.

### 4.2 The two co-primaries, and the multiplicity

* **P1 (PRIMARY) — `farm_capture`.** 14 plies, 12 games, M = 32.
* **P2 (CO-PRIMARY) — the contested cut, `invasion` ∪ `farm_capture`.** 69
  plies, 41 games. This is the cut the microgate's own GATE-LIVE statistic was
  defined on (`D_champ` = 0.639 at 108 contested plies), and it is the cut a
  deployed C1 would be gated to.
* **Holm–Bonferroni over {P1, P2}, family α = 0.05, two-sided.** A branch fires
  only on a co-primary that clears 2σ *and* survives Holm.

**Why two and not one, stated before the outcome.** P1 alone is honestly
underpowered — 14 plies in 12 games, design 2σ MDE ≈ **2.1 pts** (SIZING.md).
P2 has five times the clusters and a design 2σ MDE ≈ **1.6 pts**, but it dilutes
the mechanism with 55 `invasion` plies. Declaring both up front under Holm is
strictly more honest than declaring one and quoting whichever reads better;
P1 ⊂ P2 so the two are positively correlated and Holm is conservative here.
Everything else in §4.3–4.6 is **secondary: reported, never promoted alone,
never multiplicity-protected, hypothesis-generating only.**

### 4.3 The deployment (policy-level) price — exact, not extrapolated

An agreeing ply's price is exactly zero, so for any stratum

```
policy_price_per_ply  =  D_champ(stratum)  ×  divergent_conditional_price
```

with `D_champ` a **fixed constant of the frozen microgates set** (0.538
`farm_capture`, 0.671 `invasion`, 0.744 `defense`, 0.667 `control`, 0.639
contested, 0.679 pooled), not a quantity this run estimates. This converts a
per-divergent-ply price into "what C1 buys per ply if you switch it on across
that stratum". Reported for every stratum and both cuts.

### 4.4 ⭐ The winner's-curse readout

For each stratum: `WC = mean(in-sample gap) − mean(out-of-sample price)`,
computed per ply (both are per-ply quantities) with the same cluster-robust SE.
The in-sample gaps are frozen in `targets_c1.jsonl` and tabulated in §1.1. If
the out-of-sample price is ≈ 0, then WC ≈ +6.2 pts **is** the winner's curse of
an argmax over ~8 arms at M = 16, measured — a reusable number for every future
instrument that argmaxes noisy arms, and the single most likely durable output of
this run.

### 4.5 Coverage and attrition, stated up front

Units run; worlds landed vs void with reasons; per-arm status histogram; the
achieved-M-per-ply histogram; the world-index histogram (proving no in-sample
world leaked); plies with zero landed worlds; the G-LEGAL pre-flight's drop list;
per-arm and per-decision cost.

### 4.6 The exact-solver BONUS leg — n = 4, and a different estimand

At K ≤ 4 the rust `carc_core::endgame` marginalized solver returns the true
expectiminimax value of every child of the root in a single call, so both arms
are priced exactly by one solve. **Measured coverage at freeze: 4 of 188 plies
(1 `farm_capture`, 1 `invasion`, 2 `defense`); 0 at K = 5.** The K cut is
inherited verbatim from `../e4_ply_pricing_20260827/MODE_CUT.json`.

⚠️⚠️ **The exact leg prices the arm under OPTIMAL play by both seats; the
continuation prices it under PRODUCTION-CHAMPION play. These are different
estimands and a sign disagreement between them is not a bug.** The leg is
reported alone, never pooled, never used to void, and **cannot fire a branch**.
It exists because judge-free gold at four positions is worth its twenty minutes.

## 5. Pre-registered branches

Evaluated by [`adjudicate_c1.py`](adjudicate_c1.py), in this order, and written
to `C1_PRICING.json.BRANCH`:

| branch | condition | what it means |
|---|---|---|
| **C1-VOID** | any instrument gate below trips | **no price is read** from the affected stratum; report as an existence proof with named games |
| **C1-PRICED-POSITIVE** | a co-primary's mean > 0, \|z\| ≥ 2, Holm-surviving | the re-ranker's picks beat the champion's in realized outcome at those plies. The mechanism is priced; a C1 build is fundable **at that stratum's gate**, sized against the measured price, not against the in-sample gap |
| **C1-NEGATIVE** | a co-primary's mean < 0, \|z\| ≥ 2, Holm-surviving | the re-ranker's picks are **worse**. C1 dies here, and `D_champ` = 0.639 is re-read as noise-driven re-ranking — the winner's curse, confirmed |
| **C1-NULL-BOUNDED** | neither co-primary at 2σ, **and** achieved `se(P2) ≤ 1.2 pts` | reported as **the bound it is**: "C1's re-ranking is worth less than ±2·SE points per divergent ply at these plies", with the achieved SE quoted beside it. A null here is a bound, never a proof of zero |
| **C1-UNRESOLVED** | neither co-primary at 2σ, and `se(P2) > 1.2 pts` | the instrument did not reach its own design precision. **No reading.** Report coverage, the achieved SE, and the M that would be needed |

**Instrument gates (any one ⇒ C1-VOID for the affected stratum):**

* any `arm_map` violation on a landed row (§2.1);
* any landed unit with `world < 16` (an in-sample world leaked);
* void worlds > **10 %** on a co-primary stratum;
* any `crn_witness_mismatch` — a BUG SIGNAL, not a finding;
* any `root_state_diverged` / `world_not_a_permutation` / `deck_tail_mismatch` /
  `world_prefix_mutated` / `replay_desync` — correctness guards, not attrition;
* **G-LEGAL**: the pre-flight (§7.1) dropping > **20 %** of a co-primary
  stratum's plies. `preflight_c1.py` computes this and `run_c1.sh` **refuses to
  launch** when it trips.

**Also pre-registered as NOT findings:** a large `farm_capture` price alongside
an equally large `control` price is not a finding about farm capture, it is a
finding about rollout re-ranking in general, and will be reported as such
(`contested_minus_uncontested` is computed for exactly this reason). Nothing here
is pooled with the 2026-08-27 run's `exact_marginalized` / `exact_clairvoyant_M`
/ `realized` numbers, nor with the 2026-08-28 continuation's owner-vs-champion
prices. Different estimands.

## 6. ⭐ The elasticity clause — spend the window, don't fork the path

Owner intent: extra box-hours should buy **precision**, never a new hypothesis.
So the extension blocks are frozen here, by world index, with a purely
**wall-clock** trigger.

| block | strata | worlds added | M after | cont-plies | est. fleet-hours |
|---|---|---|---:|---:|---:|
| **base** | all four | see §3 | 32 / 16 / 8 / 8 | 323 360 | **4.40** |
| `E1` | `farm_capture` | 48 – 79 | 64 | 27 904 | 0.38 |
| `E2` | `invasion` | 32 – 47 | 32 | 141 312 | 1.92 |
| `E3` | `defense`, `control` | 24 – 31 | 16 | 154 144 | 2.10 |

**The rule, numerically.** Blocks are attempted in the order `E1 → E2 → E3`.
Immediately before starting block *E*, compute `remaining_window_h` = (window
end − now). **Start *E* iff `remaining_window_h ≥ 1.3 × cost(E)`** from the table.
A block that does not fit is skipped; skipping one does not skip a later one
(they are attempted in cost order anyway). Running everything is 4.40 + 4.40 =
**8.80 fleet-hours**.

**Two guards that make this not a forking path:**

1. **No adjudication between blocks.** `adjudicate_c1.py` is run **exactly once,
   after the last scheduled block finishes.** The extension trigger is wall-clock
   only and cannot see a price. (`run_c1.sh` emits per-block coverage sentinels —
   unit counts, statuses, arm-map violations — and nothing else. Reading those is
   allowed; they contain no outcome.)
2. **Pooling is a plain mean.** A ply's price is the unweighted mean over ALL its
   landed worlds. A partially-completed block is included: worlds land in
   `(game, ply, world)` order with no outcome dependence, and the achieved-M
   histogram is reported (§4.5).

## 7. Launch sequence — and the MANDATORY smoke

⚠️ **The 2026-08-28 PG-D7..D9 lesson: three launcher bugs shipped in one night
because the driver was never exercised against the real entrypoint.** Two layers
answer that here, and **neither is optional**.

### 7.1 Pre-launch, in order

```bash
WT=<worktree>; export PYTHONPATH=$WT/src:$WT/engine:$WT/scripts
D=$WT/measurement/c1_pricing_prep

# 0. STATIC: the argparse contract against the real entrypoint (no engine, ~1 s)
$WT/.venv/bin/python -m pytest $D/selftest_c1.py -q

# 1. rebuild the frozen target set and confirm it is byte-identical to the freeze
python3 $D/build_c1_targets.py && git -C $WT diff --exit-code -- $D/targets_c1.jsonl

# 2. G-LEGAL / G-ROOT / G-ARMS pre-flight  (~1 min, one core, engine only, NO search)
$WT/.venv/bin/python $D/preflight_c1.py     # -> LEGAL_PREFLIGHT.json + preflight_drops.txt

# 3. the box plan for the base block
python3 $D/plan_c1.py --block base --exclude $D/preflight_drops.txt

# 4. LIVE SMOKE at PRODUCTION knobs, adjudicated from the files it emits
BOX=local W=30 SHARE=/mnt/c/carc-shared $D/smoke_c1.sh

# 5. only then, both boxes, base block
BOX=local W=30 SHARE=/mnt/c/carc-shared BLOCK=base $D/run_c1.sh
ssh laptop-wsl 'bash -s' < $D/sync_laptop_c1.sh
ssh laptop-wsl 'bash -s' < $D/launch_laptop_c1.sh    # share is /mnt/carc-shared THERE
```

**Why G-LEGAL exists, and why it is a hard gate.** `microgates.py` ran
`Game(enable_legal_moves_cache=False)` — its PREREG §2.4 took "the honest mask"
because the memo `game_wrapper.Game._legal_cache` is documented in
`carc_core::tier1` as returning a **wrong farmer-corner mask on
rotationally-symmetric tiles**. `continue_plies.py` runs
`enable_legal_moves_cache=True`. So a `rollout_argmax` chosen under the honest
mask can in principle be rejected by the cached mask, and the exposure is
concentrated on MEEPLE-phase farmer placements — i.e. on `farm_capture`, i.e. on
**the primary stratum**. The pre-flight checks both arms of every target ply
against the *runner's* mask, and its drop rule is frozen here, before the freeze
commit: **a ply whose either arm action is illegal under the runner's mask is
dropped, and every drop is named in `LEGAL_PREFLIGHT.json`.** Legality does not
depend on any continuation outcome, so running the check after the freeze commit
is not a post-hoc filter — it is a frozen deterministic rule executing. Above
20 % on a co-primary stratum it is a VOID, not a drop (§5).

### 7.2 The smoke, and what it adjudicates

[`smoke_c1.sh`](smoke_c1.sh) runs **4 real units through `run_c1.sh` itself**
(same script, same flags, same knobs, `SUFFIX=_smoke`): the *most expensive*
`invasion` ply and the median `farm_capture` ply, 2 worlds each, taken from the
**top of the base block's own world range** so the smoke units are real run units
and the resumable run simply skips them. It then adjudicates **from the emitted
unit files**, not from exit codes:

| smoke gate | bar |
|---|---|
| unit files written | 4 / 4 |
| `pair.status` | `OK` on all 4 (no `VOID`, no witness mismatch) |
| arm-map | `played_action == c1_action` and `counterfactual_action == champ_action` on all 4 |
| world indices | all ≥ 16 |
| `arm_status` | `OK` on all 8 arms |
| projected base-block ETA from the measured s/unit | **≤ 8 h** — above that, do not launch |

A smoke that writes zero files, or exits 0 having done nothing, **fails**: the
gate is the emitted artifact, never the exit code (auto-memory
`feedback_verify_numbers_before_reporting` — a launcher's exit-0 ≠ run finished).

### 7.3 Box hygiene, non-negotiable

* **Exclusive tenancy.** `run_c1.sh`'s G-HOST gate censuses by **full args**
  (`ps -eo args`, never `-C python`/comm — a silent long job is invisible
  otherwise) and refuses to start beside a foreign python. The 2026-08-26
  quantification: **one** niced 1-core DRAM churner inflated a saturated W = 22
  eval ~1.8×/move and voided the run. `ALLOW_TENANTS=1` overrides, and using it
  without a census is how that happened.
* **Detach everything.** `setsid` + `nohup`; the harness's background flag alone
  is not enough (Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached
  jobs). The laptop driver additionally runs inside a `systemd-run --user` scope
  with `MemoryMax=9G` — a WSL teardown is a *Windows* OOM.
* **Rev gate.** `PINNED_SRC_REV.json` is stamped **from `main`, after the merge**
  (`stamp_pinned_rev.sh`), and `run_c1.sh` refuses on any box whose `HEAD`
  differs. The laptop is synced by git bundle into its own worktree
  `/home/doctor/carc-c1price` — never a `git checkout` of the laptop's shared
  tree:
  ```bash
  git -C $REPO bundle create /mnt/c/carc-shared/c1_pricing.bundle <branch>
  BR=<branch> ssh laptop-wsl 'bash -s' < $D/sync_laptop_c1.sh   # BR defaults to c1-pricing-freeze
  ```
* **Freeze latch.** Each box writes `RUN_LIVE_<box>_<block>.json` for the
  lifetime of its run; main-tree commits mechanically refuse while it exists.
  A stale sentinel is cleaned only after confirming the run is dead.

## 8. Close-out

On adjudication run the six-touch checklist (CLAUDE.md): `experiments/results.csv`
row (this run plays no fresh competitive games — follow the microgates/e4
precedent and record a row only if the branch is `C1-PRICED-POSITIVE` or
`C1-NEGATIVE`, i.e. only if a *strength* claim is being made), DECISIONS index
line, the status banner on this file, the governance row, the STATUS top block,
the roadmap line — then `python3 scripts/doc_lint.py`.
