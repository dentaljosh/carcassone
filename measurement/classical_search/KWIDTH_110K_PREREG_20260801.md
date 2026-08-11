# PRE-REGISTRATION — "CHAMP vs 10× CHAMP": DOES 10× BUDGET CHANGE OR IMPROVE THE MOVE?

**STATUS: PRE-REGISTERED 2026-08-01, BEFORE ANY SCORING RESULT EXISTS. Committed ahead of
the run, per house style. Nothing below may be edited once the first oracle score lands —
amendments go in a dated §10 block.** The only numbers present at commit time are the §9
pre-flight BENCH (cost + agent-parity), which by construction contains no pick statistics
and no scores.

Instrument: the CRN world-paired oracle scorer
(`scripts/measurement_infra/oracle_score_pilot.py`), validated by
[ORACLE_PILOT_EXT_READOUT_20260728.md](ORACLE_PILOT_EXT_READOUT_20260728.md) and re-used
unchanged at the rung below ([KWIDTH_22016_READOUT_20260729.md](KWIDTH_22016_READOUT_20260729.md)).
Pick phase: `scripts/measurement_infra/kwidth_agreement_probe.py` at new **additive,
default-identical** flags `--k-a 8 --k-b 80 --sims-per-det 1376` (§3.1).
Read-out pass: `scripts/measurement_infra/analyze_kwidth110k_oracle.py`, **committed before
any score exists** (`30df892`).
Drivers: `run_kwidth_110k_20260801.sh` + `chain_kwidth_110k_20260801.sh`.
Data: `/home/doctor/carc_out/oracle_110k_20260801/` on the **laptop**, rsynced to
`/mnt/carc-shared/oracle_110k_20260801/` at completion.

---

## 1. The question, why it is asked, and what it is FOR

Joshua, 2026-07-31, on leaving the boxes running: *"champ vs 10x search champ?"*

This is the **cheap screen that precedes funding a head-to-head**, and that is its whole
purpose. A champ-vs-10×-champ h2h is not free: at 110080 sims the deep arm costs 10× the
champion's already-11.2-s/move clock, so every game is ~5.5× a normal eval pair. Before
spending that, ask the same question with an instrument that needs **no opponent, no elo
and no band**: on the positions where the two budgets choose DIFFERENT moves, is the deeper
pick better?

**THE QUESTION.** On positions where the champion (11008 = k8×1376) and 10× budget
(110080 = k80×1376) choose DIFFERENT moves, does the 110080 pick score better?

**Sign convention, fixed here and never re-read: positive = the 110080 (10×) pick scores
better**, in engine points, root-player POV, averaged over the same M CRN worlds.

**THE DELIVERABLE IS A FUNDING RECOMMENDATION**, so the headline is not the
per-disagreement mean alone but the compound it implies — budget must BOTH change the move
AND improve it:

> `pts/move = D̂ × mean_delta` → pts/game → win-rate → **elo-equivalent**, the same chain
> [KWIDTH_22016_READOUT §3](KWIDTH_22016_READOUT_20260729.md) used (×71.5 decisions, ÷3.2
> measured non-additivity, σ_game 22.2 from [LUCK_FLOOR](../human_anchor/LUCK_FLOOR.md)).
> ⚠️ An **order-of-magnitude consistency figure, never a measurement.**

### 1.1 What this run is NOT — three guard-rails, pre-committed

⚠️ **UNDERSTANDING, NOT A DEPLOY LEVER. THE CL-068 CLOCK SENTENCE TRAVELS WITH EVERY
CITATION OF THIS RUN:** the champion's *current* 11008 already costs ~11.2 s/move = 91 % of
a 15-minute sudden-death clock ([TOURNAMENT_TIMING](../../docs/research/TOURNAMENT_TIMING_2026-07-26.md)),
so 110080 is **10× an already clock-unusable budget**. Nothing measured here can become a
promotion candidate, at any result. `governance/PRODUCTION.yaml` is untouched by
construction.

⚠️ **NOTHING HERE UN-PARKS THE ORACLE TEACHER-CURVE PRICING** (roadmap G6 tail; Joshua
2026-07-28 *"can't commit to days yet"*; the Eff-Jensen memo's *"oracle/200k pricing stays
PARKED"*). That item asks whether a deep TEACHER is worth box-DAYS of generation for a
distill program. This asks whether the DEPLOYED champion's move improves at 10× budget, in
one night, from picks the champion already makes. **Same harness, different purpose.** A
positive result here is a fresh ask to Joshua, not an inference.

⚠️ **PRE-COMMITTED BOOKKEEPING: no CL id, no `results.csv` row, no `PRODUCTION.yaml`
change** — identical terms to the pilot and the 22016 rung. This is not an elo cell, and a
screen that changes no production decision does not assert a claim.

---

## 2. Arms — and why the 10× arm is k80×1376, NOT k8×13760

| arm | allocation | total | role |
|---|---|---:|---|
| **A** | k8 × 1376 | **11008** | the CHAMPION OF RECORD (`governance/PRODUCTION.yaml`) |
| **B** | k80 × 1376 | **110080** | **10×** budget, WIDTH-scaled at fixed sims-per-determinization |

**The allocation choice rule, applied in advance.** Width must be re-solved per budget —
settled project knowledge, not a preference. The measured ladder is: CL-054 found **k4
optimal at total 2752**; the 2026-07-29 promotion found **k8 optimal at total 11008**; and
the measured 22016 cell is **k16×1376** (`results.csv curve_k16x1376_22016_vs_deploy_k4x688`,
the row `PRODUCTION.yaml` itself cites). **Every measured step up this ladder since 1376
became the sims-per-det has moved k and held 1376.** The 22016 lesson was explicitly that
naive depth-doubling (k8×2752) prices a *different and worse* agent. Extrapolating the same
direction to 10× gives **k80×1376**.

Three further reasons, all pre-committed:

1. **The cost trick REQUIRES a fixed sims_per_det** (§3). At k8×13760 the two arms share no
   search, the world-prefix identity does not exist, and the pick phase would cost
   11008+110080 = 121088 sims/cell instead of 110080 — a 10 % cost rise for an allocation
   the ladder says is worse.
2. **The harness imposes no cap on k** (`FairHeuristicPriorAgent` validates only
   `k_dets >= 1`), so k80 is *supported*, not merely tolerated; the flags added for it are
   additive and default-identical (§3.1). No "largest supported k" fallback was needed.
3. **k80 is honest about its own risk, and the risk points the safe way** — see §4.2.

⚠️ **THE HONEST LIMITATION, STATED BEFORE THE RESULT: width-scaling at fixed 1376 is
MEASURED only to k16.** k80 is a 5× extrapolation of that direction. If 110080's true best
allocation is *not* k80×1376 — i.e. if PIMC width saturates somewhere between k16 and k80
and the budget would have been better spent on depth — then **this run UNDER-STATES what
10× budget could buy.** That bias runs the *same* direction as the judge bias (§4.1), which
is the design's one piece of luck: **both threats push the estimate toward zero, so a NULL
here is the weak outcome and a POSITIVE here is the strong one.**

Decision rule, both arms: `pooled_q_argmax(agg_n, agg_w, min_pooled_visits=2)` — the
DEPLOYED fair pick, identical to CL-070's primary metric and to both rungs below.

---

## 3. The cost trick — one k80 run yields BOTH picks

Naively a cell costs 11008 + 110080 = 121088 sims. **It costs 110080**, because arm A is the
world-0..7 **PREFIX** pool of arm B. Three facts, each read off `fair_agent._pimc_move`
rather than assumed, and each **`k_dets`-independent**:

1. Worlds come from ONE stream — `det_rng = random.Random(det_seed_base(move_idx) + 1)`,
   consumed by `k_dets` sequential `reshuffled_determinization` calls. `det_seed_base`
   depends on (agent seed, move_idx) only: **not** on `k_dets`, **not** on sims.
2. World *i*'s search seed is `base + 100 + i` — also `k_dets`-independent.
3. Pooling is `_merge_root_stats` in world order 0..k−1, and the eligibility floor
   `min_pooled_visits = DEFAULT_MIN_POOLED_VISITS = 2` is a **constant**.

(1)+(2) ⇒ the k80 agent's worlds 0..7 **are** the k8 agent's worlds. (3) ⇒ pooling the first
8 reproduces the k8 accumulators through the same `+=` sequence, so even the order-sensitive
float addition matches and the same rule reads the same action. Note the argument never
mentions the value of k — it is the k-parallel split's own "KEY LOGICAL STEP"
(`PRODUCTION.yaml`) applied along **k**, and it therefore transfers from k16 to k80 without
a new assumption. **It is nevertheless re-proven empirically at k80 (§9), because a
transferable argument is not a run-time guarantee.**

⚠️ **PROVEN PER RUN, NOT ASSERTED.** `--verify-agent-parity N` builds REAL
`FairHeuristicPriorAgent`s at k8×1376 and k80×1376 on the same root with the same seed,
calls the **deployed** `_pimc_move`, and asserts both equal the prefix-8 and full-80 picks.
A mismatch fails the cell loudly. **20 cells carry the proof, and 20/20 is required.**
**If parity is not 20/20 the trick is void and the design reverts to running both arms
separately at 121088 sims/cell — which is ~10 % dearer, so N is re-sized and this document
is amended BEFORE the main run, not after.** → **§9: 20/20 PASSED.**

### 3.1 The harness change — additive-flag-only, default-identical, and PROVEN so

`kwidth_agreement_probe.py`'s arms were module constants (8 / 16 / 1376). They are now
CLI-settable (`--k-a` / `--k-b` / `--sims-per-det`) with **unchanged defaults**, so the
2026-07-29 invocation reproduces byte-for-byte. This was verified, not asserted: a
`--dry-run` manifest at default flags differs from the banked 2026-07-29 manifest **only in
the two CLI-set fields** (`workers` 15-vs-16, `verify_agent_parity_cells` 0-vs-20).
`pool_cells` is 2619 in both, so the fixed shuffle is the same shuffle (§7.1). `src/` and
`engine/` are untouched.

---

## 4. The judge — held IDENTICAL to both rungs below, and why

Judge, unchanged: **clairvoyant-PUCT continuation, M=32 CRN-paired deck completions,
`--oracle-sims 100`**; value = the TERMINAL engine score margin after playing the afterstate
out with the continuation policy on BOTH seats.

**COMPARABILITY IS THE DELIVERABLE.** The whole point is to place the 11008→110080 step on
the SAME ruler as the two rungs below (+0.7375 at 2752→11008, +0.1054 at 11008→22016). A
changed judge makes the ladder incommensurable, and *the ladder is the finding* far more
than any single level. The judge is also not "too shallow" in a way that matters: it never
searches for a better move than the candidates and never scores an afterstate with its own
search value — it applies each pick to the SAME determinized world, plays BOTH out under the
SAME continuation with the SAME seed, and returns the engine's own terminal `state.scores`
differential. Depth-matching would be a category error (a stronger continuation is a
different axis from a valid comparator). It was already 27×–220× below the candidates; 1100×
is not a change in kind.

### 4.1 ⚠️ THE BIAS-TOWARD-ZERO CAVEAT — carried verbatim from the rung below

A weak continuation may systematically under-convert exactly the kind of small positional
edge a bigger budget buys, which biases the measured effect **TOWARD ZERO**. **So a NULL
result here is the weaker of the two outcomes and must be reported as "not detected on this
instrument", NEVER as "there is nothing above 11008".** A POSITIVE result is not vulnerable
to this direction. **This sentence travels with any citation of a null from this run.**

### 4.2 The second bias, new to this rung, and it points the same way

§2's allocation risk (k80 may be past the PIMC width optimum) also biases the estimate
toward zero *for the budget*: a mis-allocated 10× would under-perform what 10×
well-allocated could do. The two threats therefore **do not cancel** — they compound in the
conservative direction. The one case they do not cover is a *negative* result, which would
be evidence about the ALLOCATION (k80 is too wide), not about the budget; §6 keeps that as
its own branch and does not let it be read as "10× is worthless".

**Reserved, NOT RUN, and not recommended tonight** (same two as the rung below): an
`--oracle-sims 400` sensitivity subset (the only follow-up that could overturn a null) and
an out-of-family `--oracle-policy tier1-greedy` SIGN check (uninformative on a null).

---

## 5. Sample size — the ADAPTIVE RULE, fixed here in advance

Records are (root, salt) cells with up to 3 salts per root. Planning constants, all taken
from the **realized** figures of the rung below (not from a model):

| constant | value | source |
|---|---:|---|
| per-position sd of the CRN-paired delta | **2.9495** | KWIDTH_22016 read-out §2 |
| design effect (cluster-robust / naive var) | **1.089** ⇒ se ×1.0436 | ibid. |
| pts/move equivalent of the funding bar (§6) | **0.08946** | the elo chain at 25 elo |
| cost per pick cell, laptop W16 | **§9** | measured, not extrapolated |
| cost per scored position, laptop W16 | **§9** | precedent × measured laptop factor |

**THE RULE — a FIXED N, fixed here, with NO adaptive stopping rule:**

> ### N_cells = 900
>
> a prefix of one fixed shuffle, `order_seed = 20260729` (the SAME order the 22016 run
> used — §7.1 explains why that is deliberate and what it buys). A prefix, not a re-draw.
> The 20 §9 pre-probe cells are the first 20 of that order and are already banked, so the
> main run adds 880 and `--resume` skips them.
>
> Then score the **frozen** disagreement set of those 900 cells, **in full**.

The 22016 run used a two-stage adaptive rule to hit a target n. **This run deliberately does
not**, for two reasons: (a) the binding constraint here is wall-clock, not a target n, so the
budget guard alone determines N; and (b) a single fixed N is one launch with no intermediate
decision, which removes the failure mode that already cost this probe a night (an
inter-stage hand-off that never fired). **Stopping is by CELL COUNT, decided now, and no
score is inspected before the pick phase ends.**

**Why 900**, from the §9 measured costs (`c_pick = 12.36` s/cell, `c_score = 93.81` s/position,
both wall-seconds at W16 on the laptop):

| if D̂ = | 0.12 | 0.15 | 0.20 | 0.25 | 0.30 |
|---|---:|---:|---:|---:|---:|
| n scored | 108 | 135 | 180 | 225 | 270 |
| total wall | 5.9 h | **6.6 h** | 7.8 h | 9.0 h | 10.1 h |

The §9 pre-probe's own 20-cell rate is 0.15, so **the run projects ≈ 6.6 h — the ~7 h
target**, and stays under the 10 h abort trigger for any D̂ ≤ 0.29. D̂ ≥ 0.30 at a 10× budget
would contradict both rungs below (0.2398 at 4×, 0.1244 at 2×) and is itself a §5 halt
condition (below).

**Read the realized D̂ off `picks/summary.json` and REPORT IT REGARDLESS of what the score
phase says** — it is a finding in its own right and the direct successor to CL-070's
`D_paired = 0.2398` and the 22016 rung's `D̂ = 0.1244`. At N=900 it lands to about ±0.012.

**Power, stated in advance and NOT hidden.** At D̂ = 0.15 ⇒ n ≈ 135 ⇒ cluster-robust
se ≈ 2.9495 × 1.0436 / √135 = **0.265**, so the elo-equivalent CI half-width is ≈ ±21.7 elo
against a 25-elo bar (§6). **This screen is well-powered on D̂ and only marginally powered on
the per-disagreement mean** — the §6 reachability field will say exactly how marginal, and
if the NOT-DETECTED branch could not have fired, that is reported as the answer rather than
dressed up as one. Buying the mean a decisive n is not affordable in this window: the rung
below needed n=237 to reach se 0.20, which at this rung's cell cost is a ~13 h run.

**Degenerate cases, decided in advance:**
- **D̂ < 0.05** ⇒ the collapsed disagreement rate IS the headline finding (strong evidence
  the champion's move is budget-invariant); score whatever disagreements exist as a
  descriptive, explicitly-underpowered addendum. Do not chase n.
- **D̂ > 0.30** ⇒ the run would breach the 10 h trigger AND would contradict both rungs
  below. Halt after the pick phase, check for a construction bug, and score only what
  fits 7 h of scoring (~270 positions), stating the truncation.
- **D̂ > 0.45** ⇒ suspicious on its face. Halt and check for a construction bug before
  scoring anything.

---

## 6. Inference and the PRE-REGISTERED VERDICT MAP — decided before the numbers exist

Every statistic clusters on `root_id`. **A naive i.i.d. z will not be cited** — the
harness's own `summary.json` z is naive; the read-out recomputes from the on-disk records.

- **THE CITED ROW: cluster-robust sandwich se, clustered on root, G/(G−1) corrected.**
- **Conservative read:** root-collapsed (one unit-weighted mean per root).
- **Non-parametric:** 20 000 bootstrap resamples OF ROOTS (seed 20260801), record-level and
  root-collapsed. **Distribution-free:** sign test on records and on roots.
- Location robustness: median and 10 %-trimmed mean.

**THE FUNDING BAR, fixed in advance: 25 elo.** A head-to-head can only CONFIRM an effect it
can resolve. CLAUDE.md's own n-thresholds put a deck-PAIRED n=400 at ≈ ±12 elo (1σ), so
~25 elo is the smallest effect such a run could land at 2σ. Below that bar the confirm is
unaffordable-to-resolve and the answer is "do not fund". In pts/move the bar is **0.08946**.

| outcome (primary = cluster-robust, on the frozen n) | verdict | funding recommendation |
|---|---|---|
| CR z ≥ +2 **and** root-collapsed mean > 0 | **DETECTED — the 10× pick is genuinely better** | **FUND the confirm**; size the deck-paired h2h from the elo-equivalent (§6.1). Understanding only — CL-068 still forbids deployment. |
| 95 % CI upper bound on the **elo-equivalent** < 25 elo | **NOT DETECTED — a fundable effect is EXCLUDED** | **DO NOT FUND.** Predicted null; the port speedup goes to science throughput. ⚠️ §4.1's sentence attaches. |
| neither | **UNDERPOWERED / INCONCLUSIVE at this n** | Report the interval; do not promote a direction. Default is still **do not fund**, but state explicitly what the screen failed to exclude. |
| CR z ≤ −2 | **THE 10× PICK IS WORSE** | k80 is past the width optimum at 110080 — a statement about ALLOCATION, not about budget. Report as-is; do not rescue it; do not fund a h2h at this allocation. |

**MANDATORY REACHABILITY FIELD.** The read-out prints, for the realized se and D̂, the point
estimate each branch would have required. A branch that could not have fired is reported as
such.

### 6.1 If DETECTED — how the h2h gets sized (pre-committed)

n (deck-paired games) = `(2 × 12 × √(400) / Ê_elo)²` — i.e. scale the CLAUDE.md paired
anchor (n=400 ⇒ ±12 elo) to 2σ at the point estimate Ê. Cost is priced with the Rust-era
backend multiplier from `measurement/rustport_p6/G6_backend_deploy_multiplier.json`
(~7.3× cheaper eval farms), against the ~5.5× per-game penalty of running one seat at 10×.
The sizing goes in the read-out; **launching it is Joshua's decision, not this run's.**

### 6.2 Pre-registered anti-fooling clauses

- Strata (phase, `h200_top2_q_gap` tercile) are **DESCRIPTIVE ONLY**; no stratum may be
  promoted to a finding.
- **Winner's curse is expected.** This project has watched a screen shrink on extension five
  times (c=3 "+47", flywheel it16 "+88.7", C3-intra "+40.1", the oracle pilot's own
  +1.91→+0.74, the 22016 batch-1 D̂). Any early-batch number is a screen, not a verdict.
- The read-out is computed by a separate, pre-committed analysis pass.
- **The ladder, not the level, is the powered comparison.** Report this rung's estimate AND
  its ratio to +0.7375 (4× rung) and +0.1054 (2× rung).

---

## 7. Execution plan

**Box: the LAPTOP (`laptop-wsl`) only.** The local 5900XT is owned by the P6 gate
(`reconcile_backend.py`, live at census time) and the standing rule sends heavy legs to the
other box. `nice -n 19`, **W16**, detached (`setsid` + `nohup` + `disown`), per-record atomic
checkpointing (`.tmp` + `os.replace`), `--resume` safe, chained + watchdogged
(`chain_kwidth_110k_20260801.sh`) so the probe completes unattended.

**Output lives on LAPTOP-LOCAL disk** (`/home/doctor/carc_out/oracle_110k_20260801`), not on
the share: the share is **99 % full (15 G free)** and a ~7-hour run must not depend on SMB
staying up for every per-record write. The chain rsyncs the whole tree to
`/mnt/carc-shared/oracle_110k_20260801/` at completion.

**A LOST WAKE-UP MUST NOT STRAND THIS RUN** (it already did once, costing a night). Three
independent layers, all on the box, none depending on a session: the chain script auto-runs
phase 2 when phase 1 banks its summary; `run_watchdog.sh` is armed on the score phase and
re-execs the driver on a stall; and **both phases are `--resume` safe with per-record atomic
writes**, so the recovery action from any interruption — including "nobody came back for
hours" — is literally to re-run the same driver command. Resumable state lives at
`/home/doctor/carc_out/oracle_110k_20260801/{picks,score}/records/` on the laptop.

**Phase 1 — picks.** `kwidth_agreement_probe.py --k-a 8 --k-b 80 --sims-per-det 1376`,
110080 sims/cell, N=900, `--verify-agent-parity 20`, `--wall-cap 5400`, W16.
**Phase 2 — scoring.** `oracle_score_pilot.py` over `picks/records`, M=32,
`--oracle-sims 100`, `--world-seed-salt kwidth-110k-v1`, W16:

```
--records-dir <out>/picks/records --roots <bank>/roots.jsonl \
--level-a 11008 --level-b 110080 --alloc-a k8x1376 --alloc-b k80x1376
```

### 7.1 Deck source — REPLAYED roots, NO NEW BAND CONSUMED

Roots are **replayed from the CL-070 bank** `move_agreement_k4_b28e9` (band 28e9), exactly
as both rungs below did. There is no opponent, no game is played from a fresh deck, and
worlds are CRN-derived from the replayed roots — so **no band is consumed and the band
protocol does not apply.** The output dir is noted in `BAND_CLAIMS.txt` as a courtesy so a
concurrent session sees the box is busy.

`order_seed = 20260729` is **deliberately the SAME order the 22016 run used**, over the same
pool (2619 cells, verified identical in §3.1). That buys a free, strong validity check: arm
A's pick is a function of the cell alone — same bank, same `root_seed(deck_seed, ply, salt)`,
same world-0..7 prefix — and **cannot** depend on how many worlds arm B ran. So **every cell
present in both runs MUST report the same 11008 pick.** The read-out prints
`ARM-A CROSS-RUN IDENTITY x/y`; anything short of 100 % means the prefix identity or the
champion config moved between the runs and the cross-rung comparison is void (§8).

---

## 8. What would falsify / void this run

- **Agent-parity failure** on any verified cell ⇒ the prefix trick is invalid at k80; the
  run is void and the design reverts to 121088 sims/cell (§3).
- **`ARM-A CROSS-RUN IDENTITY` < 100 %** ⇒ the two rungs are not on a common arm A; the
  ladder comparison is void even if this rung's own statistics survive.
- **`crn_verified_all: false`** ⇒ some position's arms were not paired; `--strict-crn`
  (default on) fails those positions rather than admitting them unpaired.
- **Non-zero `n_positions_identical_afterstates`** ⇒ some "different" picks transpose to the
  same board; their zero deltas are identities, not evidence, and are reported separately.
- Any cell whose replay checksum mismatches is failed, never scored.
- A construction guard refuses to run if `_meeple_dedup` / `_intra_reuse` /
  `_parallel_workers` are on (the prefix argument assumes the plain sequential world loop).

---

## 9. Pre-flight bench at PRODUCTION knobs — RUN BEFORE LAUNCH

The pre-probe ran the SAME `sims_per_det` (1376), the SAME arms (k8 / k80), the SAME decision
rule, the SAME box, the SAME W16 / `nice -n 19` / detached execution as the scaled run — only
the cell count differed. **20 cells, 20/20 ok, 0 failed**, 1508 s wall,
`/home/doctor/carc_out/oracle_110k_20260801/picks/`, `code_rev 30df892`, host `laptop-wsl`.

### ✅ AGENT PARITY AT k80: 20/20 CELLS PASSED

On every one of the 20 cells the harness built REAL `FairHeuristicPriorAgent`s at **k8×1376**
and **k80×1376** on the same root with the same seed, called the **deployed `_pimc_move`**,
and asserted both returned exactly the prefix-8 and full-80 picks this harness reports.
**The §3 cost trick is PROVEN at k80 on this rev, not assumed** — the pick phase therefore
costs 110080 sims/cell, not 121088. (The main run passes `--verify-agent-parity 20` over the
same order prefix; those 20 cells are already banked and are skipped by `--resume`, so the
proof is carried forward in the records rather than re-paid.)

### Cost — measured, then extrapolated, in that order

Every pre-probe cell is a PARITY cell = 110080 (probe) + 11008 + 110080 (the two deployed
`_pimc_move` re-runs) = **231168 sims**. Per-cell `elapsed_secs`:

| min | median | **mean** | max |
|---:|---:|---:|---:|
| 183.0 | 339.7 | **415.2** | 1508.0 |

⚠️ **The MEAN is used, not the first completions** — first completions of a parallel batch
are the order statistic minimum and are ~2× optimistic (the fastest cell here is 2.3× faster
than the mean). The tail is real and tracks endgame depth: the 1508 s cell alone set the
batch's wall clock.

> **1.7962 ms/sim** on the laptop at W16, against **1.4516 ms/sim** measured on the local
> 5900XT in the 22016 production run (3805 s × 16 ÷ 1905 cells ÷ 22016 sims).
> ⇒ **laptop = 0.808× local per core** — the laptop is SLOWER, not faster.

| quantity | value |
|---|---:|
| **c_pick** — a plain 110080-sim cell (no parity re-run) | 197.7 core-s ⇒ **12.36 s/cell wall at W16** |
| local realized score cost (22016 run: 15624.6 s × 16 ÷ 237) | 1054.7 core-s/position |
| ÷ 0.808 laptop factor, **× 1.15 planning margin** | 1501 core-s ⇒ **93.81 s/position wall at W16** |

⚠️ `c_score` is the one **extrapolated** figure: it is the rung-below's *realized* cost scaled
by a speed factor measured on the *pick* path, not the score path. The 15 % margin is for
that. It is the same anchoring the 22016 prereg used (that run's scoring ETA, 3.4 h, came in
at 4.3 h), and it is why §5's N is sized to ~6.6 h inside a 7 h target rather than to the
guard itself. Scoring is `--resume` safe, so an under-estimate extends the run rather than
losing it.

### ⚠️ DISCLOSURE — what the pre-probe revealed about picks, and how it was used

The 20 pre-probe cells contain **3 disagreements**. That is a 20-cell screen with a standard
error of ±0.08 — it is **NOT the reported D̂** and no inference is drawn from it. It is used
for exactly one thing, stated here so it cannot be laundered later: **the ETA row in §5's
table that says the run projects ≈ 6.6 h.** N was fixed at 900 knowing this number. Nothing
else in this document — not the arms, not the judge, not §6's verdict map or its 25-elo bar —
was chosen after seeing it, and the scoring phase has not been run at all.

---

## 10. Amendments

_(none — this section exists so post-hoc changes are visibly dated rather than edited in)_
