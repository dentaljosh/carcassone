> # ✅ STATUS: **ADJUDICATED 2026-08-28 (overnight) — PRIMARY NULL, NEGATIVE POINT ESTIMATE** (invasion-minus-control divergence price −1.87 ± 1.88, z −0.99; farm_capture +2.53 z 1.68 n=12 the sole unpromoted thread; prefund 0/8 spent by the envelope's own bars). The per-ply residual is dead; steering conclusion on 3 instruments. results.csv `e4_continuation_pricing_PRIMARY_NULL_n91_judgefree`; CONTINUATION.json on share. Close-out stamp — nothing below is edited.
>
# PREREG — E4 CONTINUATION PRICING (judge-free, CRN-paired game outcomes)

> **Status: BLIND-COMMITTED, PRE-OUTCOME.** This file, the frozen target set
> (`targets_continuation.jsonl`, `TARGETS.json`) and the whole instrument are
> committed on branch `e4-continuation-freeze` **before any continuation
> outcome exists**. House two-commit pattern: this commit is the FREEZE; the
> next commit stamps its sha as `BLIND_COMMIT`. Deviations after the freeze go
> in `DEVIATIONS.md`, never here.
>
> Owner authorization, verbatim (2026-08-27): *"continuation . laptop w22.
> local w30"*.

## 0. Why this instrument exists

The 2026-08-27 ply-pricing run
([`../e4_ply_pricing_20260827/PREREG.md`](../e4_ply_pricing_20260827/PREREG.md))
computed the production champion's counterfactual move at all 290 target plies
and found **the agreement gradient**: the champion would have played the
owner's own move at **74.1 %** of `invasion` plies against **33.7 %** of
`control` plies. The champion mostly does not *disagree* with the owner's
invasion moves — it fails to *reach* those positions. The hole is upstream
position-steering.

That leaves a residual this instrument prices: **at the plies where the two DO
part ways, what is the owner's move actually worth?** The prior run could not
answer it — 96 % of its plies sat above exact-solvable K, and every
search-based substitute is a judge. Its §4.1 named the one judge-free filling,
costed it, and deliberately banked its expensive input (the champion
counterfactual at every ply) without launching it. **This is that instrument.**

Its evidence class is the one the F4 lesson ranks above every judged number
(auto-memory `reference_evloss_grader`: judged headroom is FAMILY-RELATIVE — an
out-of-family judge read the same +1.49 pts/ply clair-family ceiling as −0.64,
z −3.8). **The price here is a REALIZED GAME OUTCOME**: the final score of a
game played to termination. Nothing in this instrument scores a position. The
production champion appears only as a POLICY that plays moves.

### 0.1 ⚠️ Disclosure — what was seen before this freeze

Blind means blind, so this is stated here rather than discovered later. A
**cost probe** was run before this commit to size the compute (§5): three units
at production knobs, killed as soon as the timing question was answered. It
completed **exactly one** unit — `1787618319_251279.json` ply 4 world 0, the
`control` stratum's most expensive ply — and its outcome
(`delta_pts_mover = +37`, 137 continuation decisions per arm) was therefore
visible before this file was committed. Its two `invasion` companions were
killed mid-flight and produced **no outcome at all**; no `invasion`, `defense`
or `farm_capture` outcome exists anywhere at freeze time.

The target set, the arms, the CRN design, the estimator, the primary contrast
and every constant below were written and frozen on disk BEFORE that probe ran.
The probe's one unit stays in the run (the instrument is deterministic, so it
recomputes bit-identically — §6 uses that as a determinism gate) and is **not**
excluded: excluding it would be a post-hoc filter on a seen outcome, which is
worse than declaring it.

## 1. What is frozen here

### 1.1 The target ply set (`build_continuation_targets.py` → `targets_continuation.jsonl`)

Selection reads ONLY the banked rows' *decision* fields — stratum, ply, K,
actor, phase, played action, counterfactual action, agreement flag.
`test_continuation.py::test_selector_reads_no_outcome_field` asserts at code
level that the selector's source does not so much as MENTION `winner` /
`final_scores` / `recorded_scores` / `margin` / `realized` / `delta_pts_mover` /
`price_` / `scores_at_ply` / `regret`. Outcome-blind **by construction**.

Of the 290 banked rows, **120 are divergent** (`counterfactual_agrees is
False`). The target set is:

| stratum | n plies | n games | rule | mean ply-frac | Σ remaining plies |
|---|---:|---:|---|---:|---:|
| `invasion` | **21** | 18 | EVERY divergent invasion ply (`actor == 0`, tiles phase) | 0.334 | 1986 |
| `defense` | **28** | 20 | EVERY divergent defense ply (`actor == 1`, tiles phase) | 0.448 | 2192 |
| `farm_capture` | **12** | 10 | EVERY divergent farm-capture ply (`actor == 0`, MEEPLES phase) | 0.788 | 360 |
| `control` | **30** | 24 | a decile-matched sample of the 59 divergent `control` plies | 0.297 | 2996 |
| **total** | **91** | **38** | 90 `fixed_v1` + 1 `walled` | 0.417 | **7534** |

**The control arm is not optional and is not a nicety.** Without it a nonzero
invasion-divergence price is uninterpretable: it could simply be what ANY
champion-divergence is worth on an ordinary move. `invasion − control` is
therefore the PRIMARY pre-registered contrast (§3.2), and both of its arms are
divergent plies, so the comparison is like-for-like.

**The decile match, stated in full** (`match_controls`, deterministic given the
seed): the quota per ply-fraction decile is a largest-remainder apportionment of
30 over the *invasion* divergent set's decile histogram (ties to the lower
decile); each decile is then sampled with `random.Random(CONTROL_SEED)` from its
candidates sorted by `(game, ply)`; any shortfall — a decile the 59-ply pool
cannot fill — is filled from the remaining candidates ordered by
`|ply_frac − mean invasion ply_frac|` ascending, then `(game, ply)`.

> **Measured, and reported here rather than after the fact: the pool could not
> fill 3 of the 30 slots** (quota `{d0:1, d1:6, d2:9, d3:6, d4:6, d5:1, d7:1}`
> against a pool of `{d0:1, d1:11, d2:8, d3:8, d4:4, d5:8, d6:6, d7:7, d8:5,
> d9:1}` — deciles 2 and 4 are short). The achieved histogram is `{d0:1, d1:7,
> d2:8, d3:8, d4:4, d5:1, d7:1}`, mean ply-fraction **0.297 against the
> invasion set's 0.334**. The match is good but not exact, and the residual
> skew is toward EARLIER controls. Both figures are in `TARGETS.json`.

Pre-registered constants (asserted equal to the code by
`test_prereg_constants_match_the_code`):

```
WORLD_SEED = 20260828
CONTINUATION_SEED = 0
M_WORLDS = 8
ARM_WALL_CAP_S = 600
CONTROL_SEED = 20260828
N_CONTROL = 30
```

### 1.2 The rules-epoch discipline (binding, inherited unchanged)

The rules profile is resolved **FROM EACH ARCHIVE** via
`analyzer.ev_loss.resolve_profile_name`, and the runner **re-resolves it and
hard-fails on any drift** from the frozen target's stamp. An explicit
`rules_profile` stamp wins outright; its ABSENCE is positive evidence of a
pre-`fixed_v1` build. **Never identify a build from `(start_rule, grid_rule)`.**
R9 is import-latched, so the runner asserts a SINGLE profile per process and
calls `prepare_env` before any `carcassonne_ai` import; the observed-vs-expected
latch is stamped on every unit row (`r9_env`). Budget epoch (`budget_note`,
`played_sims_effective`, `played_k_dets_effective`) is carried per row from the
archive — the E4 anchor is nonstationary and no tally may be read without it.

## 2. The measurement

### 2.1 The unit of work, and the two arms

One unit is one `(game, ply, world)`. It runs **two arms** from the identical
root state at the target ply:

* **`arm_owner`** — the archive's own move at that ply is applied;
* **`arm_cf`** — the production champion's counterfactual move (banked by the
  2026-08-27 run) is applied instead.

and from each, the production champion plays **both seats** to termination.

⚠️ At `defense` plies the `arm_owner` move is the **on-device champion's** own
archived move (`actor == 1`), not the human's. The arm keeps its name for
symmetry; the stratum prices what the champion's pre-invasion move was worth
against the production champion's alternative, i.e. **the cost of the
champion's non-defense**, and it is read separately from the primary contrast.

The continuation policy is the production champion of record —
`governance/PRODUCTION.yaml` `champion.fair_deploy`: `k_dets = 8` ×
`sims_per_det = 1376` (11008), leaf `a36d2e15a3b3d71d`, fair PIMC, exact-K ≤ 2,
`backend: rust` — built through the same audited construction the prior run
used (`make_production_champion("fair", …, **resolve_execution("inherit",
profile="desktop").factory_kwargs())`). `rust_threads` is execution-only (G4:
bit-identical merge at threads {1,4,8}).

### 2.2 ⭐ The CRN pairing — what is shared, and the witness that proves it

The pairing is the variance killer. Held IDENTICAL across a unit's two arms
**by construction**, each with a witness field that the aggregator hard-checks:

| held identical | mechanism | witness |
|---|---|---|
| the ROOT STATE at the target ply | both arms replay the same archive action prefix from ply 0 | `root_repr_sha` (sha of the engine's `string_representation`, which encodes board, phase, scores, meeples and next tile), plus `n_drawn_prefix` and `n_legal_root` |
| the WORLD's DECK COMPLETION | the unseen tail is permuted by `world_rng(deck_seed, ply, world)` — a generator whose inputs contain **no arm term** | `world_deck_sha`, `world_deck_len` |
| the POLICY's RANDOMNESS | one champion per arm, both `seed = CONTINUATION_SEED`, both seated at `_move_idx = ply` before the arm move, so continuation decision *j* draws the same determinization seeds in both arms | `det_seed_base_at_root`, `move_idx_at_root` |

What necessarily DIFFERS is the board after the arm move. That is the treatment.

**Any witness mismatch VOIDS the pair** — it means the arms did not actually
share a root or a world, so their difference is not a paired contrast. A void is
a skip, never a price, and never a finding.

**How the world is installed** (no new Rust surface): the Rust mirror can only
be REPLAYED, never constructed from a board, so the permuted tail is installed
on the **initial** board — whose already-drawn prefix is untouched — and the
archive prefix is replayed on top of it. `mirror_protocol.seat` reads
`[next_tile] + deck` straight out of that board, so python and rust get the same
world. Three guards run before any move: the replayed tail must equal the
initial draw-order tail, the new order must be a permutation of the true order
with an identical drawn prefix, and the reconstructed root's
`string_representation` must equal the TRUE (unpermuted) root's — permuting the
UNSEEN tail must not move the position. The Rust mirror's own unconditional
`check_sync` runs at the root on top of that.

### 2.3 What is forced, and what is not — the estimand, stated exactly

**Only the target ply's action is forced.** Everything after it, in both arms —
including the meeple follow-up that belongs to the same tile — is the
champion's own choice. The estimand is therefore precisely:

> *the value of the target ply's move, under subsequent production-champion play
> by both seats.*

The named alternative — also forcing the archive's meeple follow-up in
`arm_owner` — is **deliberately NOT taken**: it would make the two arms
asymmetric in how much archive behaviour they carry, and the residual question
is about the divergent move, not about a two-ply owner plan. The consequence is
real and is reported rather than papered over: a merge-invasion tile whose
meeple the champion then declines is an invasion the champion did not
consummate. `followup_agrees_with_archive` is recorded on every unit as a
DESCRIPTIVE field so that interpretation is auditable, and it is never part of
a price.

### 2.4 Caps and isolation

Every arm runs in its own forked child under `RLIMIT_AS` (`--job-mem-cap-gb`)
and `RLIMIT_CPU` (`--arm-cap-secs`, `ARM_WALL_CAP_S = 600` s of CPU per
continuation-world by default, `SIGXCPU` left at its DEFAULT disposition so the
kernel can kill a child parked inside a long Rust decision), plus a parent wall
backstop. Reused verbatim in shape from `price_plies.solve_isolated`, which
inherited it from `scripts/rustport/reconcile_exact_solver.py`. An arm over
either cap is recorded `TIME_SKIPPED` / `OOM_SKIPPED` and **voids its unit's
pair** — a half-priced pair would break the very pairing the estimator rests on.
Units are written one file each, atomically (`.tmp` + rename), so a killed
worker loses at most one world and the run is resumable by re-running the same
unit list.

⚠️ **The cap is a CPU cap and DRAM contention is charged to CPU time.** The
per-box cap is therefore set from the measured worst-case arm with ≥3× headroom
(§5), not from the nominal 600, and any box-level value other than the constant
above is recorded in `DEVIATIONS.md`.

## 3. Pre-registered readouts

1. **Per-ply row**: game, ply, world, stratum, K, actor, rules profile + budget
   epoch, both arms' final scores, `delta_pts_mover`, CRN witness, per-arm cost.
2. **A ply's price** = the mean of its landed CRN worlds' `delta_pts_mover`.
3. **A stratum's price** = the unweighted mean over its plies, with a
   **cluster-robust SE clustered on GAME** (91 plies live in 38 games; treating
   plies as independent draws would understate the SE), plus z.
4. ⭐ **THE PRIMARY CONTRAST: `invasion − control`.** Both arms are divergent
   plies. Games contribute to both arms, so the contrast's SE is built from
   per-game influence contributions **of the difference**, which de-correlates a
   shared game instead of pretending independence.
5. **`defense` read separately** — the cost of the champion's non-defense. Never
   pooled into the primary contrast.
6. **`farm_capture` read separately**, with `farm_capture − control` as a
   secondary contrast. Note it is the only MEEPLES-phase stratum.
7. **Coverage and attrition, stated up front**: units run, worlds landed vs
   void, void reasons, per-arm status histogram, plies with zero landed worlds.
8. **Descriptive, never a price**: `followup_agrees_with_archive` rate;
   per-decision and per-arm cost; budget-epoch and profile histograms.

### 3.1 The sign convention (pinned by hand fixtures, `test_continuation.py` §1)

`margin_p0_minus_p1` is the realized final `P0 − P1`. Then
`delta_pts_mover = (owner − cf)` for a seat-0 mover and its negation for a
seat-1 mover — **positive iff the played move was worth more points TO THE
MOVER than the champion's counterfactual**, at either seat.

### 3.2 Power, stated before the outcome

At `M_WORLDS = 8` CRN worlds per ply, 21 invasion plies in 18 games and 30
control plies in 24 games, the SE is driven by the GAME count, not the ply
count. **This instrument is powered to see a large effect, not a subtle one.**
A null here is a bound, not a proof of zero; it will be reported as the bound it
is, with the achieved SE quoted next to it.

⚠️ At small K the world set is *smaller than* `M_WORLDS` — a ply with 3 unseen
tiles has only 6 distinct completions, so its 8 worlds contain duplicates
(`world_deck_len` is recorded per unit). The paired estimator stays unbiased;
its SE simply does not shrink as `1/√M`. This bites `farm_capture` (mean
ply-fraction 0.788) hardest.

## 4. Pre-registered falsifiers / what would kill a reading

* **A `replay_desync`, `root_state_diverged`, `world_not_a_permutation` or
  `deck_tail_mismatch`** on any unit voids it and, if it recurs, the instrument:
  those are correctness guards, not attrition.
* **A CRN witness mismatch** on any unit is a BUG SIGNAL, not a finding.
* **Void worlds above ~10 %** ⇒ the affected stratum is reported as an existence
  proof with named games, not as an estimate.
* **A stratum price larger than the feature's own final points** is a bug
  signal, not a discovery (the Stage A census reconciles 50/50 exactly).
* **`invasion − control` is the primary.** A large invasion price with an
  equally large control price is NOT a finding about invasions; it is a finding
  about champion divergence in general, and will be reported as such.
* Nothing here is pooled with the 2026-08-27 run's `exact_marginalized`,
  `exact_clairvoyant_M` or `realized` numbers. Different estimands.

## 5. Compute — the arithmetic, before the launch

Two measurements feed the model. (a) The prior run's 290 banked champion
decisions at production knobs, `rust_threads = 1`: mean **1.464 s/decision**
(median 1.27, p90 2.52), K-dependent — 2.37 s at K 10–19 down to 0.67 s at
K 60–69. (b) This run's own cost probe (§0.1), a WHOLE continuation on the
single most expensive ply in the set (137 decisions per arm, the longest tail
there is): **136.2 s and 182.4 s per arm → 0.99 and 1.33 s per continuation
ply**, i.e. **~1.16 s/ply solo**, and **319 s for that worst-case unit**.

```
target plies                                              91
Σ remaining plies over the target set                  7,534
continuation-plies = 7,534 × 2 arms × 8 worlds        120,544
      @ 1.00 s/ply ->  33.5 h serial
      @ 1.16 s/ply ->  38.8 h serial          <- MEASURED central
      @ 1.50 s/ply ->  50.2 h serial
work units = 91 plies × 8 worlds                          728   (2 arms each)
worst-case unit (measured, solo)                          319 s
```

Split **LOCAL W = 30** + **LAPTOP W = 22** = 52 concurrent arms.

> ⚠️ **W = 30 on the local box is OWNER-DIRECTED** (verbatim: *"local w30"*),
> above this repo's usual DRAM-bound optimum of ≈14–16. It is his box and his
> W. It is recorded here as owner-directed because it is a THROUGHPUT choice
> only: every game in this instrument is deterministic given
> `(deck_seed, ply, world, arm)`, so the results are **bit-identical at any W**
> and no reading depends on the worker count. The smoke measures what W = 30
> actually buys (§6).

Boxes take **whole plies** — all 8 worlds and both arms of a ply stay on one
box, so a ply's paired estimate is never split across two binaries — and
parallelise over `(ply, world)` units within a box. Ply-to-box assignment is by
predicted cost (Σ remaining plies), interleaved so each box gets a mix of
strata.

**Gate: if the smoke-measured ETA exceeds 6 h, this run does not launch.**

## 6. Reproduce

R9 is import-latched, so every stage runs one process per rules-profile group.
`PYTHONPATH` points at the worktree; the venv is editable-installed against the
main tree, so verify `carcassonne_ai.__file__` resolves inside the worktree.

```bash
export PYTHONPATH=$WT/src:$WT/engine:$WT/scripts
D=$WT/measurement/e4_continuation_20260828

# 1. freeze the target set from the BANKED 2026-08-27 rows (outcome-blind)
python3 $D/build_continuation_targets.py \
    --rows /mnt/c/carc-shared/e4_ply_pricing_20260827 \
    --out $D/targets_continuation.jsonl --meta $D/TARGETS.json

# 2. tests, then the FREEZE commit, then the smoke, then the run
.venv/bin/python -m pytest $D/test_continuation.py -q
python3 $D/plan_boxes.py --targets $D/targets_continuation.jsonl --out-dir $D
BOX=local  W=30 SHARE=/mnt/c/carc-shared $D/run_continuation.sh $D/units_local.txt
ssh laptop-wsl 'bash -s' < $D/launch_laptop.sh    # share is /mnt/carc-shared THERE

# 3. the readout
python3 $D/aggregate.py --units $D/out_local $D/out_laptop \
    --targets $D/targets_continuation.jsonl --out $D/CONTINUATION.json
```
