> ⛔→✅ **FROZEN 2026-08-24 (branch-freeze: the blind commit is THE COMMIT INTRODUCING THIS
> BANNER, on branch `h2h22k-freeze`, cut from `tiearb2-stage2`'s tip `ecbbc616` — local main
> is latched under a live `carcasum_arb_challenge` run; the branch merges at a quiet window; a
> committed sha is a provable freeze on any branch, same precedent as `carcasum-arb-freeze` /
> `d1-rebase-freeze`). Owner directive, verbatim: **"fund it"** 2026-08-24, after the menu
> discussion. No game on band `148000000000` exists at freeze time. **NOT LAUNCHED** — this is
> a build-only deliverable; the orchestrator fires it with its own monitors, exactly as
> `carcasum_match_prep/LAUNCH_PROCEDURE.md` did for its rung 1.
> `WORKERS.conf::BLIND_COMMIT` and `PINNED_SRC_REV` cannot be stamped with this commit's own
> sha inside this same commit — a small follow-up commit stamps both before any real launch;
> `run_cells.sh` refuses a real (non-dry-run, non-smoke) launch while either reads `PENDING`.**

# 22016 vs 11008 — DIRECT BUDGET HEAD-TO-HEAD — DESIGN

This is the single non-banner status paragraph in this file, deliberately. Nothing below
contradicts the banner above it. **The orchestrator launches; this build stops at the smoke
(§9).**

Design: this file. Read-out branch table: [`READ_RULE.md`](READ_RULE.md). Constants:
[`WORKERS.conf`](WORKERS.conf). Launcher: [`run_cells.sh`](run_cells.sh). Band claim:
[`BAND_CLAIM.json`](BAND_CLAIM.json). Adjudicator: [`adjudicate.py`](adjudicate.py).

---

## 0. What this cell is, and the closed axis it re-opens

**The purchase (owner-funded 2026-08-24, verbatim "fund it").** A direct head-to-head:

> **F = `k16×1376` = 22016 sims** vs **E = production `k8×1376` = 11008 sims** —
> *does one more budget doubling above production still pay, on the current instrument?*

`n = 700` decks × 2 seatings = **1,400 games**, deck-paired (same deck both colours).

**The axis is CLOSED and this re-opens it.** `docs/LEVER_INDEX.md` carries the row
**"budget-headroom decay bound · geometric extrapolation · how much is left above 11008 ·
decay ratio r · `next-gain/(1−r)` · convergent-sum headroom"**
([MEMO](../budget_headroom_bound_20260809/MEMO.md)). Assembled 2026-08-09, then its own
pre-registered tightener fired the same day and closed it:

- the assembled bound (`+54 elo`) is **SUPERSEDED**;
- the oracle-measured price came in at **`+0.0673` pts/disagreement** (cluster-robust
  se 0.2041, z +0.330), a **price ratio 0.091** against the `+0.7375` reference;
- the re-stated bound: **≈ +7.1 elo, honest bracket ≈ `[−35, +49]` elo, SPANS ZERO**;
- the mechanism, which is the actual finding: **"above 5504 the deeper pick MOVES but does
  not IMPROVE"** — the decay moved out of the *rate* and into the *price*;
- the row's own note: *"22016 is the first rung this bound speaks to, and the bound now says
  it is worth ~nothing."*

**Why re-opening is licensed, and by what route.** Not by more extrapolation — that is the
route the closure already exhausted, and its own honest asterisk (the one adjacent ratio
measured *at* the extrapolation point is `r₄ = 1.19 ± 0.40`, `>1` in both strata, on which
number alone the sum does not converge) is precisely a request for a *direct* read. The
licensed route is a **direct instrument that resolves well below the old bounds**. This cell's
realized 2σ is **≈ ±1.11 pts ≈ ±20 elo** (§3) — about **half the half-width** of `[−35, +49]`.

**So the read rule is written accordingly, before any number exists**
([`READ_RULE.md`](READ_RULE.md) §0/§4): **a null RATIFIES the closure at the tighter bound.**
`H-NULL-BOUND` is the licensed, *expected* deliverable under the closure's own central
estimate — not a failure and not an inconclusive. And a positive **licenses nothing about
deploy**: F costs 2× the wall-clock per move by construction, and affordability is an owner
question this cell does not answer.

**One more thing the closure itself flags, which this cell inherits.** The bound rests on an
oracle judge that is **in-family** (clairvoyant PUCT + the same curve125 leaf) — "tested-and-
not-supported, not excluded" — and its out-of-family read is *lower*. This cell has no judge
at all: it is games, on decks, with a margin. That is the other half of why it is worth
buying.

---

## 1. Primary question and estimator

**Primary:** deck-paired margin, candidate minus opponent, in points.

```
D(d)  = ( diff(d, a_seat=0) + diff(d, a_seat=1) ) / 2       -- one observation per DECK
D     = mean over decks;  SE(D) = sd/sqrt(n_common);  z_D = D/SE(D)
cluster unit = DECK (not game, not seat)
```

**Points are primary. Elo is display only**, computed from this cell's own realized W/D/L and
margin and never used as a branch input ([`READ_RULE.md`](READ_RULE.md) §1).

**Within-band, deck-paired, one instrument, one launch window ⇒ NO CL-068 humility discount.**
This is the robust class `CLAUDE.md`'s cross-band amendment explicitly exempts. That matters
here more than usual, because every *existing* read on this contrast is cross-band (§2.1).

---

## 2. Configuration — the instrument is production, exactly

| | ARM F (candidate) | ARM E (opponent / baseline) |
|---|---|---|
| **budget** | `k_dets 16 × sims_per_det 1376` = **22016** | `k_dets 8 × sims_per_det 1376` = **11008** |
| **identity** | the champion of record, one doubling up | **the champion of record verbatim** — `governance/PRODUCTION.yaml champion.fair_deploy` |
| **backend** | `rust` | `rust` (`--opponent fair-champion` is a `_HEAD_TO_HEAD` mode ⇒ `converted_sides == ["candidate","opponent"]`) |
| **leaf** | curve125, pinned `PROD_LEAF_HASH = a36d2e15a3b3d71d` | **identical** — same pin, same hash |
| **search knobs** | `c_puct 1.5`, `tau_p 5`, `leaf_quantize float`, `final_select visits` | **identical** |
| **rules** | `fixed_v1` + `CARCASSONNE_FIX_R9=1` | **identical** |
| **endgame** | exact **K≤2 marginalized** (§2.3) | **identical**, shared by both arms |
| **tie-arbiter** | **OFF** (§2.2) | **OFF** — structurally (§2.2) |
| **deck band** | `148000000000..148000000699`, 700 decks | **the same decks**, both seatings |

**Single-variable discipline.** The two sides differ in **exactly one experimental axis**:
`k_dets` (16 vs 8), and its arithmetic consequence `total_sims` (22016 vs 11008).
`sims_per_det` is **1376 on both sides** and is in the must-not-differ set. Everything else —
leaf hash, search knobs, endgame, rules, backend, `code_rev` — is asserted **identical from
the manifests themselves**, not from the launch command
([`READ_RULE.md`](READ_RULE.md) §3 `G-SINGLEVAR`). A launch-command diff proves intent; a
manifest diff proves what ran. This is the `track_d2_prep` lesson ported
(`results.csv d2_rung_compression_U_UNREADABLE...b141e9`: single-variability was asserted in
prose and never checked).

### 2.1 — the allocation choice, and what stays unmeasured

At a fixed 22016 total, **how** the budget is spent is a live axis, and the old era measured
it once, on one shared band:

```
results.csv, both 2026-07-23, band 48e9, CRN with each other, vs the same k4x688 deploy:
  curve_k16x1376_22016_vs_deploy_k4x688   n=196   +35.58 elo   paired z +2.68
  curve_k8x2752_22016_vs_deploy_k4x688    n=198    +3.51 elo   paired z +0.21
  deck-matched k16 - k8 (same band)       +2.985 pts/deck  se 1.746  z +1.71
                                          -> "k8x2752 WAS width-starved"
```

**This cell runs the measured winner, `k16×1376`, as its single arm.**

⚠️ **DISCLOSED: `k8×2752` stays UNMEASURED on the current instrument.** No second arm is
built. This is a deliberate single-variable design — adding a second candidate would turn one
clean two-sided question into a three-way comparison, double the cost, and require a
multiplicity correction the purchase did not fund. **Consequence, stated up front:** if
`H-POSITIVE` fires, it fires *for the `k16×1376` allocation*, and "is `k16×1376` still the
right allocation at 22016 on the current instrument?" remains open. If `H-NULL-BOUND` or
`H-REVERSED` fires, the bound is on **this** allocation and a differently-allocated 22016 is
not formally excluded — though the old-era evidence says it would be *worse*, not better.

### 2.2 — tie-arbiter OFF on BOTH sides, and how that is verified

This is a **pure budget question**. The root tie-arbiter (`PRODUCTION.yaml`
`fair_deploy.tiearb`, `B=64 J=4 argmax salt=tiearb2-deploy-v1 eps=0.0`) is a separate,
separately-adjudicated lever; arming it on either side would confound the axis, and arming it
on *one* side would confound it catastrophically.

- **`run_cells.sh` passes NO `--cand-tiearb-*` flag, ever.** The harness default is disarmed.
- **The opponent side is STRUCTURALLY disarmed.** Verified in source during this build:
  `scripts/classical_search/eval_fair_puct.py` exposes `--cand-tiearb-enabled/-b/-j/-mode/
  -salt/-eps` and **no `--opp-tiearb-*` flag of any spelling**; the arbiter is candidate-side
  only, rust-only (`eval_fair_puct.py` ~line 1020: *"tiearb: THE TIE ARBITER (CANDIDATE side
  only, rust-only)"*), and the rust path early-returns the untouched pick when
  `SearchConfig.tiearb_enabled` is false (`rust/carc/carc-core/src/fair/mod.rs`).
- **`G-TIEARB` asserts the ABSENCE anyway** ([`READ_RULE.md`](READ_RULE.md) §3): `cand_tiearb`
  absent or `enabled == false`, plus a whole-manifest key scan for any `*_tiearb` resolving to
  an armed config. The gate exists so the structural fact is **recorded as verified rather
  than believed** — the same reason d1-rebase carries its own `G-TIEARB` over a ladder whose
  launcher likewise never passes the flag.

### 2.3 — exact-K is NOT a free knob here

`WORKERS.conf::EXACT_K=2`, and this is **production**, not a choice:
`governance/PRODUCTION.yaml champion.endgame` distinguishes two handoffs — **(a)** the
CLAIRVOYANT reference/eval agent takes exact **K≤4 clairvoyant alpha-beta**, and **(b)** the
**FAIR deployable agent** (`src/carcassonne_ai/fair_agent.py`) takes the exact **K≤2
MARGINALIZED** expectiminimax handoff. Its own words: *"Alpha-beta and K=3-4 are
clairvoyant-only (they read the true deck order) so the fair agent caps at K≤2 marginalized."*

This is a **fair** cell (`--info fair`). K=2 is therefore simultaneously "as production" and
**the only legal value**. The *"production runs K≤4"* line in `PRODUCTION.yaml`'s CL-071
caveat refers to the clairvoyant ruler side and must not be read across. It is also what every
prior fair budget contrast used — CL-060, `b119e9`, the d1-rebase ladder — which is what makes
§3.1's σ precedents applicable rather than merely adjacent. **No orchestrator decision is
owed here; this paragraph exists so nobody re-litigates it at launch time.**

`G-EXACT` gates it, both sides, `mode == "marginalized"`.

---

## 3. Power arithmetic

### 3.1 — σ_D, measured, not assumed

`σ_D` is read off **seven** `n=400`-deck, deck-paired, `fixed_v1`+R9, rust-backend cells
already in `experiments/results.csv`, by inverting each one's published `paired margin` and
`paired z` (`SE = |margin|/|z|`, `σ_D = SE·√400`):

```
cell                                              SE(n=400)   sigma_D
width_k4x2752_vs_k8x1376_fixed11008_n800_b119e9    0.68005     13.60  <- closest analogue
simsplit_alloc_a_split_t2752_m1376_...b123e9       0.73330     14.67  <- max
simsplit_alloc_b_uniform2064_...b123e9             0.65740     13.15
denial_d1_s5o3_deploy_...b124e9                    0.66192     13.24
joshuabot_confirm_j7zero_...b126e9  (n=799)        0.65669     13.13
jrules_d0p25_deploy_...b128e9                      0.64598     12.92
jpriors_d0p5_deploy_...b130e9                      0.62057     12.41  <- min
                                    median 13.15 | mean 13.30 | max 14.67
```

`b119e9` is the structurally closest: a **direct** head-to-head between two production
champions differing only in budget allocation at fixed total 11008, same leaf both sides,
`fixed_v1`+R9, rust, `exact-k 2`, deck-paired. **Note how tight the seven are** (12.41–14.67,
a 1.18× spread across five different experimental axes) — this is a well-characterised
instrument and the σ model is not the uncertainty in this design.

```
MODEL A  median of seven   sigma_D = 13.15
MODEL B  b119e9 analogue   sigma_D = 13.60
MODEL C  max of seven      sigma_D = 14.67   <-- THIS CELL SIZES ON MODEL C
```

Sizing on the conservative bound follows `carcasum_arb_challenge_prep/DESIGN.md` §3.1's
reasoning: a false positive out of an underpowered cell is the worse failure mode, and no
cheap follow-up is queued to catch one.

### 3.2 — n = 700 decks

```
SE_D = sigma_D / sqrt(700) = sigma_D / 26.458

  Model A: 0.4970 pts   2sigma +-0.994 pts
  Model B: 0.5141 pts   2sigma +-1.028 pts
  Model C: 0.5545 pts   2sigma +-1.109 pts   <- of record

elo/pt (display only), in-family bracket:
  cl060_h2h_k8x1376_vs_deploy_k4x688 :  49.85 / 2.9775 = 16.74 elo/pt
  width_k4x2752_..._b119e9           : -19.56 / 1.01125 = 19.35 elo/pt
  => 2sigma = 1.109 pts ~= +-18.6 .. +-21.5 elo
```

**Resolution of record: 2σ ≈ ±1.11 pts ≈ ±20 elo** — against the closure's `[−35, +49]`,
i.e. roughly half the half-width. That is the purchase.

### 3.3 — what it can and cannot see, stated before the answer

```
alternative                                    delta(pts)  z@SE=.5545  power(2-sided a=.05)
closure CENTRAL      (+7.1 elo, MEMO SS9)         +0.41       0.73            ~11%
closure UPPER        (+49.3 elo)                  +2.82       5.08           ~100%
old-era cross-band point read (-14.3 elo, SS2.1)  -0.82      -1.48            ~32%
80%-POWER MDE                                     +-1.55     +-2.80             80%
                                              ( ~= +-26 .. +-30 elo )
```

⚠️ **The two numbers that must never be conflated: this cell RESOLVES at ±20 elo (2σ) and has
80% POWER only at ±27–30 elo. It is blind by design to the closure's own +7 elo central** —
at that truth it reads z ≈ 0.7 and would return `H-NULL-BOUND` ~89% of the time. That is not a
defect; the deliverable is a *bound*, and the bound is what the closure asked for. Nobody may
later read the null as "we looked for +7 and it wasn't there."
[`READ_RULE.md`](READ_RULE.md) §0 and §4 both carry this clause so the read-out cannot omit it.

**To resolve the +7.1 elo central at 2σ would need `n ≈ 5,220` decks** — i.e. `SE_D` must fall
to `0.406/2 = 0.203` pts, so `n = (14.67/0.203)² = 5,220` — **7.5× this purchase**, ~49 h of
laptop wall at the §7.2 rate. Not funded, not proposed, and named here only so the
size of the un-bought question is on the record.

### 3.4 — NO top-up, deliberately

Unlike `carcasum_arb_challenge_prep` and the r1 precedent, **this cell reserves no top-up
range and its read rule has no top-up branch.** Reason: a top-up exists to rescue a design
whose *inconclusive* region is a failure state. Here the "inconclusive" region **is the
licensed deliverable** — `H-NULL-BOUND` is a bound, and a bound is what was purchased. Buying
n to chase the +7 elo central would need 8× the games (§3.3), which is a fresh funding
decision and a fresh band, not a top-up. The band claim (§4) therefore reserves
**700 decks and nothing more**.

---

## 4. The band

**Claimed: `148000000000`**, seeds `148000000000..148000000699` (700 decks). No top-up range
(§3.4).

### 4.1 — the ALL-BRANCHES sweep (the corrected procedure, run as prescribed)

`carcasum_arb_challenge_prep/DESIGN.md` §4.1 documents the corrected claim procedure after the
`144e9` collision: **a band-freedom check scoped to the checked-out branch's own
`governance/BAND_REGISTRY.csv` is blind to every claim sitting on an unmerged sibling branch.**
That procedure was run here as written, and extended: **all 114 local branches** enumerated;
**33** carry at least one `measurement/**/BAND_CLAIM.json`; **74** carry a
`governance/BAND_REGISTRY.csv`, in **33 textually-distinct versions**; every claim file read
via `git show <branch>:<path>` without a single checkout.

**Frontier of claims, across every branch:**

| band | experiment | branch(es) | status |
|---|---|---|---|
| `141000000000` | `track_d2_prep` (D2 rung-compression, `U-UNREADABLE`) | 11 | claimed |
| `142000000000` | `carcasum_match_prep` (Carcasum rated match r1) | 7 | claimed |
| `143000000000` | `carcasum_rung2_prep` (Carcasum rung-2 ladder) | 6 | claimed |
| `144000000000` | `track_d2r2_prep` (D2-R2) | `d2r2-freeze` only | claimed |
| `145000000000` | `track_d1_fair_rebase` (fair-ruler re-baseline) | `d1-rebase-freeze` only | claimed |
| `146000000000` | `track_d1_fair_rebase` **extension** | `d1-rebase-freeze` only | **soft-reserved**, `status: DRAFT-NOT-CLAIMED`, no registry row anywhere |
| `147000000000` | `carcasum_arb_challenge_prep` | `carcasum-arb-freeze` only | claimed |
| **`148000000000`** | **this cell** | **`h2h22k-freeze` only** | **claimed here** |

**Global maximum claim anywhere before this one: `147000000000`.** Cross-checked independently
by scanning the max `band_seed_start` in **every one of the 33 distinct registry versions** —
no branch anywhere carries a row above `147000000000`.

**`146000000000` is SKIPPED, deliberately**, on exactly the reasoning
`carcasum_arb_challenge_prep` used when it skipped the same band: by the letter it is free (no
registry row on any branch, its own status field says `DRAFT-NOT-CLAIMED`), but
`d1-rebase-freeze` has spent a committed paragraph earmarking it for its own future
n-extension and asked that nothing run there without a fresh funding decision. Taking it would
manufacture the identical collision the corrected procedure exists to prevent, the moment that
extension is funded. **`148000000000` is the lowest integer clear of everything found
anywhere.**

**Registry append discipline:** the row is appended to `governance/BAND_REGISTRY.csv`
**on this branch only** (`h2h22k-freeze`), never to the main tree, which is latched under a
live run. The `BAND_CLAIMED` sentinel is dropped in the same commit
(`carcasum_match_prep`/`carcasum_rung2_prep`/`carcasum_arb_challenge_prep` precedent: all
claimed their real row at freeze-commit time rather than deferring to launch).

**Band hygiene.** The §9 smoke uses a disjoint dev-tier throwaway seed
(`WORKERS.conf::SMOKE_SEED_START = 990000000000`), never pooled, never claimed, never
adjudicated.

---

## 5. Gates and the branch table — pointer

Full gate table (`G-BAND`, `G-DECKS`, `G-SINGLEVAR`, `G-REV`, `G-BLIND`, `G-LEAF`, `G-RULES`,
`G-BACKEND`, `G-BUDGET`, `G-TIEARB`, `G-EXACT`, `G-N`, `G-SAT`, `RECON`), the `VOID` check,
and the branch table (`H-POSITIVE` / `H-REVERSED` / `H-NULL-BOUND` / `U-UNREADABLE`,
first-match-wins, `VOID` first) all live in [`READ_RULE.md`](READ_RULE.md), matching the
`DESIGN.md`/`READ_RULE.md` split this family established.

**Three gates deviate from the d1-rebase set they are ported from, all flagged for
orchestrator review:**

1. **`G-BACKEND` is STRENGTHENED** to require `converted_sides == ["candidate", "opponent"]`,
   not just `"candidate"`. d1-rebase's opponent was the frozen Python `h800` rung *by design*,
   so its gate could not ask for more. Here the opponent **is** a production champion; a
   Python opponent against a rust candidate would be a different, much slower, un-preregistered
   instrument. Verified implementable: `--opponent fair-champion` is a `_HEAD_TO_HEAD` mode and
   `eval_fair_puct.py` sets `converted_sides = ["candidate", "opponent"]` for exactly that set.
2. **`G-SAT` is WIDER and SYMMETRIC** — `[0.35, 0.65]` vs d1-rebase's one-sided `[0.50, 0.90]`.
   That cell graded a champion against a deliberately weaker frozen rung, where a *low*
   win-rate is the pathology. This one grades a champion against **itself at a different
   budget**, where the expected win-rate is near 0.5 and a departure in **either** direction is
   the mis-wiring signal. It is a rail check, never a strength bar.
3. **`G-TIEARB` scans for `opp_tiearb` too**, not just `cand_tiearb` — cheap, and it converts
   §2.2's structural argument into a recorded verification.
4. **`G-LEAF` gates BOTH sides on a full 16-hex hash** — `config.cand_leaf_hash` and
   `config.opponent.leaf_hash`. Recorded here because an earlier draft of this design got it
   **wrong** and the correction is worth preserving: it claimed the opponent's hash was
   available only as an 8-char prefix inside the opponent `leaf` prose string, on the strength
   of seeing that string and seeing `curve125_leaf_provenance` resolve to `None`. Re-reading
   the source settled it — for `--opponent fair-champion` (neither `h800` nor `greedy`) the
   harness writes the opponent block's `leaf_hash` as `_leaf_hash(opp_leaf_cfg)`, **the
   complete hash**. `curve125_leaf_provenance` really is `None` on this path (it is populated
   only for `net`/`bare-net`), but that field is a provenance extra, not the hash, and nothing
   depends on it. **No prefix parsing, no weakened evidence, no harness change owed.**
   The general lesson, which cost nothing here and could have cost 1,400 games: **a gate whose
   fixture was written from the same assumption as the gate proves nothing** — the fixture
   would have fabricated a prefix-only opponent field the real harness never emits, the
   self-test would have gone green, and the gate would have false-`VOID`ed a clean run. Gates
   were therefore verified against `eval_fair_puct.py`'s *emitting* code, not against the
   self-test's *fixtures*.

---

## 6. Sequencing — ONE cell, one box, exclusive tenancy

There is **one** cell (one candidate, one opponent, one band, one launch). The dual-arm
concurrency question `carcasum_arb_challenge_prep` §6 had to solve does not arise: both
"arms" here are the two sides of the *same* game, played in the same process, on the same
deck, at the same instant. Thermal/drift confounding is structurally impossible — any drift
moves both sides of every game identically and cancels in the paired margin.

**Exclusive tenancy is still mandatory** (`feedback_no_agent_compute_beside_eval`): nothing
else runs on the laptop while this runs. This is a multi-hour tenant and its wall-clock feeds
the `W-COST` style witness; a co-tenant does not change the games but does corrupt any cost
read-out taken from the run.

**Ordering constraint:** the laptop is busy with `carcasum_arb_challenge` until ~05:00 EDT.
`run_cells.sh` refuses to start while a foreign `RUN_LIVE.json` is present anywhere under
`measurement/` (§7.4) — the launcher enforces the wait rather than trusting a human clock.

---

## 7. Cost, wall-clock, and the preflight

### 7.1 — the cost model, calibrated on TODAY's realized numbers

**Basis: `track_d1_fair_rebase`, laptop, `W=22`, 2026-08-24** — the same harness
(`eval_fair_puct.py`), the same backend (rust), the same rules (`fixed_v1`+R9), the same
`exact-k 2`, the same box, **today**. Its `E11008` cell is *the production champion at exactly
our E budget*:

```
E11008 (k8x1376 = 11008), laptop W=22, realized:
    champ_prefix_ms_per_move (candidate side)  1777.5 ms
    rung_ms_per_move (its h800 opponent)       1075.9 ms
    solver_secs_per_game                          1.62 s
    mean moves/game                             141.95      (= 2 x 70.98 per side)
    realized s/game (WORKER-seconds)            200.6 s
```

**The model, and its validation.** `s/game = M × (ms_cand + ms_opp)/1000 + solver`, with
`M = 71` moves per side. Checked against **all five** rungs of that ladder:

```
rung    ms_cand   model s/game            realized   err
A800     148.9    71*(0.1489+1.0759)+1.6 =  88.6       88.6   +0.0%
B1600    290.9                              98.7       98.7   +0.0%
C2752    473.0                             111.6      111.0   +0.5%
D5504    888.0                             141.0      139.3   +1.2%
E11008  1777.5                             204.2      200.6   +1.8%
```

**Per-move cost is linear in total sims at the top of the ladder** — per-sim ms reads
0.1861 / 0.1818 / 0.1719 / 0.1613 / **0.16147** across the five rungs, i.e. fixed per-move
overhead amortises out and the top two rungs agree to 0.1%. Extrapolating one doubling is
therefore well-supported, *and mechanically exact*: `k16×1376` searches the **same 1376-sim
worlds**, just **sixteen of them instead of eight**, sequentially (each worker runs the rust
agent at `threads=1`; `search_worlds`' `n_workers = threads.clamp(1, k)` clamps *threads*, not
worlds). Doubling `k` doubles the work with no term that amortises.

```
F side (22016) = 1777.5 x 2 = 3555.0 ms/move
E side (11008) =              1777.5 ms/move   (the identical agent -- opponent IS the champion)

s/game @ W22 = 71 x (3.5550 + 1.7775) + 1.62 = 380.2 worker-s
```

**W22 → W26 contention.** From the F7d laptop ladder
(`measurement/classical_search/WSWEEP_F7D_laptop.tsv`), per-move cost inflates
`6244.3 / 5483.6 = 1.1387×` going W22→W26. (Only the *ratio* is used — that TSV's absolute
ms/move are half-converted-era and ~3× our instrument's; **do not quote its absolutes**.)

```
s/game @ W26 = 380.2 x 1.1387          = 433.0 worker-s
             x 1.02 (harness calibration, d1-rebase's own model uses the same +2%)
                                        = 441.7  ->  442 worker-s/game   <-- OF RECORD
```

### 7.2 — projected wall-clock, and a correction to the purchase's own estimate

```
1,400 games x 442 worker-s = 618,800 worker-s
                 / W=26    =  23,800 s  =  6.6 h          <-- PROJECTION
throughput                 =  212 games/h at W=26
```

⚠️ **FLAGGED FOR ORCHESTRATOR REVIEW — this is ~2.5× FASTER than the ~16–17 h the purchase
projected.** The discrepancy is not a disagreement about the design; it is a calibration era.
A 16–17 h figure is reproduced almost exactly by the **F7d TSV's absolute** champion ms/move
(`6244 ms` at W26 → ~21 h), and those rows are **half-converted-era** (the F7d TSV's
timestamps are 2026-08-02, before the rust opponent conversion; `docs/CLUSTER_OPS.md` notes
the re-swept era is *"~6.6× the morning's half-converted workload"* and that the mixed-era rows
*"remain in the TSVs for the record"*). This design uses **today's** realized numbers from the
same harness on the same box instead. **Nothing in the design depends on which figure is
right** — the timeout ladder (§7.3) is sized off 442 s/game with 2× margin and bounded at
18.9 h total, so it survives being 2.8× wrong before it fires. But the orchestrator should
know it is likely to finish before breakfast, not after lunch, and should size its monitors
accordingly. **If the run's first pass realizes materially above ~442 s/game, re-project
before assuming the total** — the house "validate, don't trust" rule; `run_cells.sh` prints a
realized s/game after every pass for exactly this.

### 7.3 — passes and the per-pass timeout derivation

`eval_fair_puct.py` has **no `--limit` flag** (verified in source), so d1-rebase's "one long
foreground invocation" and `carcasum_arb_challenge_prep`'s `--limit` chunking are both
unavailable as written. **This build uses bounded PASSES**: each pass is one `timeout`d
invocation over the *full* range under `--shared-claim`; the harness skips already-recorded
cells, so each pass advances the archive, and the **final** pass walks the whole range and
therefore writes the pooled `summary.json` the adjudicator reads. Between passes the launcher
re-asserts the rev pin, sweeps stale claims, checks RAM, and checks the void rate.

```
CHUNK_GAMES        = 100                     games a pass is SIZED to complete
expected pass wall = 100 x 442 / 26 = 1,700 s
PASS_TIMEOUT_SECS  = 2 x 1,700      = 3,400 s      <-- WORKERS.conf
MAX_PASSES         = 20      (14 expected; 20 bounds a pathological resume loop)
hard ceiling       = 20 x 3,400 s   = 18.9 h
CLAIM_STALE_SECS   = 1,800   (~4.1x one game's 442 s)
```

⛔ **The timeout is derived from THIS cell's own 22016-sims game cost and from nothing else.**
It is **not** a `5000ms`-opponent formula, and not any budget-independent constant. That class
of error — a timeout sized to the wrong opponent's clock — produced the rung-C void storm, and
it is the single most expensive mistake available to this build.

**Stale-claim sweep.** A pass killed by `timeout` strands `.claim` files, and a stranded claim
stalls resume until it ages past `CLAIM_STALE_SECS` (`feedback_shared_claim_orphan_stall`).
`run_cells.sh` therefore sweeps, between passes, every `.claim` with **no matching record**
whose mtime predates the pass it just killed — the documented fix, applied proactively rather
than after a stall.

### 7.4 — W, RAM, and the preflight

**`W = 26`** — the F7d **raw peak** for this exact workload class
(`eval_fair_puct --backend rust`, both sides rust; `docs/CLUSTER_OPS.md` "Fourth profile":
*local `W*=30` (peak `W36`) / laptop `W*=26`*). The **settled** value is `W=22`
(`docs/PROGRAM_ROADMAP_2026-07-07.md` F7d: *laptop `W*=22` (peak `W26`, nproc 24)*).
**The owner accepted the peak over the settle for this batch run.** This is a throughput
choice and not a strength choice — W changes wall-clock only; the games are bit-identical at
any W. It is recorded here because the house W-protocol
(`feedback_worker_count_by_bottleneck`: *settle on the SMALLEST W within ~5–10% of peak, never
the argmax*) points the other way, and a future reader should see that the deviation was
chosen, not drifted into.

**RAM, and why the floors exist.** The laptop's WSL VM is capped near **11.7 GB**, and a guest
OOM **tears down the whole VM** rather than killing one worker
(`reference_wsl2_host_memory_teardown`). `docs/CLUSTER_OPS.md`'s own table records the historic
failure at high W on this box: *"W26 gen → 131 MB free, sshd wedge."* That row is the **gen**
profile (net-in-process), not this rust-classical one — the fifth-profile note says RAM is *"no
longer the binding axis"* for rust classical work (≤4 GB box-wide at laptop `W=24`) — but the
sweep saw `min_avail` tighten at high W and W=26 is the peak, so the floors are not optional:

```
PREFLIGHT_RAM_FLOOR_MB = 2500    refuse to START below this MemAvailable
RUNTIME_RAM_FLOOR_MB   =  800    ABORT the sequence (fail-closed) if a between-pass
                                 reading falls below this -- do not ride it into a
                                 VM teardown
```

**Full preflight, enforced by `run_cells.sh` before pass 1** (any failure = refuse to start,
exit nonzero, no games):

| # | check | fails on |
|---|---|---|
| 1 | `BLIND_COMMIT` is 40-hex, not `PENDING`, and an **ancestor of HEAD** | placeholder / non-ancestor / absent |
| 2 | `PINNED_SRC_REV` is 40-hex and **equals `git rev-parse HEAD`** | any drift |
| 3 | `src/ engine/ scripts/ rust/ tests/ pyproject.toml setup.py` **clean** | any dirt |
| 4 | `BAND_CLAIMED` sentinel present | absent (the launcher never claims a band itself) |
| 5 | **R9 latched in a CHILD process** — `rules_profile.resolve("fixed_v1").as_manifest()["r9_env_ok"] is True` via the same import path the cells use | the `track_d2_prep` `G-RULES` defect |
| 6 | **leaf hash resolves to `a36d2e15a3b3d71d`** in a child process, from the same `--cand-leaf-json` the cells pass | any drift, before 1,400 games are spent on the wrong leaf |
| 7 | **`nproc >= W`** on this box | an under-provisioned box silently thrashing |
| 8 | **`MemAvailable >= PREFLIGHT_RAM_FLOOR_MB`** | §7.4 |
| 9 | **no foreign `RUN_LIVE.json`** anywhere under `measurement/` | §6 — the laptop is busy until ~05:00 EDT and the launcher waits on the artifact, not the clock |
| 10 | **process census clean** — no other `python`/`carcasum_driver` tenant | `feedback_no_agent_compute_beside_eval`; this is an exclusive tenant |

---

## 8. The adjudicator

`adjudicate.py`, committed **in this same blind commit, before game 1**. Its full contract is
[`READ_RULE.md`](READ_RULE.md) §7. The two properties that matter to this design:

- **ANALYZER vs WITNESS.** The analyzer of record is `eval_fair_puct.py` itself, which wrote
  `summary.json`; the witness is an **independent from-scratch recomputation** from the raw
  `seed*_a*.json` records. Disagreement beyond `rel 1e-6 / abs 1e-9` on any of
  `paired_mean_margin` / `paired_z` / `n_paired` / `winrate` / `elo` is the `RECON` gate, and a
  `RECON` FAIL is a `VOID`. **The witness can only void, never move, the number.**
- **THE GUARDED ELO CONVERSION** ([`READ_RULE.md`](READ_RULE.md) §1). Worth calling out in the
  design because it is a **numerical trap sitting directly under this cell's most likely
  headline**: the natural scale, this cell's own `elo_per_point = elo_D / D`, is unusable
  precisely under `H-NULL-BOUND`, where `D ≈ 0` by construction and the ratio becomes a
  quotient of two independently-noisy near-zero quantities — unbounded, non-convergent, sign
  unstable. A 2σ elo bound quoted through it would be an artifact of division rather than a
  measurement. So the conversion **branches**: at `|z_D| ≥ 2.0` the cell's own realized ratio
  is used (and cross-checked against the in-family bracket as a witness); at `|z_D| < 2.0` the
  **points** interval is the interval of record and the elo display is quoted as a **range**
  through the pinned in-family bracket `[16.74, 19.35]` elo/pt, explicitly labelled a bracket
  conversion. `ADJUDICATION.json` records which limb applied. **Guarding only against `D == 0`
  exactly would have done nothing** — `D = 0.003` is equally broken and far likelier.
- **`--selftest`.** Runs the entire gate + branch + witness machinery against synthetic
  fixtures with no real archive present: one fixture landing on each of the four §4 branches,
  one fixture per §3 gate that breaks exactly that gate, and one analyzer/witness disagreement
  fixture. It exits nonzero if any fixture's `(branch, failing-gate-set)` differs from
  expected. **It must be run and must pass before the real adjudication is trusted.** It reads
  no real record, touches no band, and spends no blindness — so the orchestrator can run it at
  any time, including now.

---

## 9. SMOKE — required before the real launch, zero band cost

Same discipline as `carcasum_arb_challenge_prep/DESIGN.md` §9 and the house rule *"pre-flight
smoke must use PRODUCTION knobs, not arbitrary ones"* — **only the game count differs.**

**Recipe (`./run_cells.sh --smoke`, exempt from the blind/band preconditions):**

```
2 games, --seed-start 990000000000 (dev-tier throwaway, disjoint from every claimed band,
                                    never pooled, never adjudicated)
--workers 2
EVERYTHING ELSE IDENTICAL TO THE REAL CELL:
  --info fair --opponent fair-champion --backend rust
  --k-dets 16 --sims 1376  --opp-k-dets 8 --opp-sims 1376
  --exact-k 2 --rules-profile fixed_v1  (CARCASSONNE_FIX_R9=1 exported)
  --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
  --cand-leaf-json <curve125>
  --paired
  NO --cand-tiearb-* flag
```

**Minimum bar to clear before a real launch — all six:**

1. **2/2 games complete**, `n_failed == 0`.
2. `summary.json` `config.backend.converted_sides == ["candidate", "opponent"]` and
   `mixed_builds == false` — **the `G-BACKEND` strengthening (§5) proven live**, not inferred
   from source reading. *This is the single most valuable thing the smoke buys.*
3. `config.cand_leaf_hash == "a36d2e15a3b3d71d"` **and** the opponent-side leaf hash equal to
   it.
4. `cand_tiearb` **absent** (or `enabled == false`) and **no `*_tiearb` key resolves armed** —
   `G-TIEARB` proven live.
5. Budgets read back `(16, 1376, 22016)` / `(8, 1376, 11008)` with the product identity
   holding — `G-BUDGET` proven live, i.e. **`--k-dets 16` really produced 16 determinizations**
   and was not silently clamped. (Source review found no cap: the only guard is a floor,
   `k_dets >= 1`, `rust/carc/carc-py/src/lib.rs`; `--k-dets 16` emits a non-fatal
   `_prod_deviations` **warning** — *"k_dets=16 (production 8)"* — and proceeds. **Expect that
   warning in the log; it is correct and must not be suppressed.**)
6. **Realized `champ_prefix_ms_per_move` within ±25% of the §7.1 projection (3555 ms/move)**
   at `--workers 2`, adjusted for the near-unloaded contention regime — a gross miss means the
   §7 cost model is wrong and the timeout ladder should be re-derived **before** launch, not
   after a void storm.

Also run, before launch: **`python3 adjudicate.py --selftest`** (§8) — it must exit 0.

---

## 10. Close-out obligations

The six-touch checklist in full: `experiments/results.csv` row → `DECISIONS.md` index line →
status banner on this file **and** `READ_RULE.md` → governance row flip
(`BAND_REGISTRY.csv` `decision_influenced` + band retirement; a `CLAIM_REGISTRY.csv` row if a
claim is minted) → `STATUS.md` top block → roadmap line in
`docs/PROGRAM_ROADMAP_2026-07-07.md`. Then `python3 scripts/doc_lint.py`.

**Plus, regardless of outcome:** amend the `docs/LEVER_INDEX.md` **budget-headroom decay
bound** row. On `H-NULL-BOUND` it is *ratified at the tighter bound* and the row's interval of
record becomes this cell's realized 2σ. On `H-POSITIVE` the row's operative reading is
*falsified at this rung* and must be amended, not merely annotated. On `H-REVERSED` the row is
*strengthened beyond ratification*. **A cell that re-opens a closed row owes that row an edit
in every branch** — including `U-UNREADABLE`, which owes it a "re-test attempted, void,
band not spent" line so the next reader's grep cannot miss that it was tried.

⚠️ **`fixed_v1` refuses a `results.csv` row unless the profile name is in the `exp_id`**
(`rules_profile.py` spec A0). Proposed `exp_id`:
`budget_h2h_k16x1376_22016_vs_champ_k8x1376_11008_fixed_v1_n1400_b148e9`.

---

## 11. LAUNCH PROCEDURE — the orchestrator's steps, in order

**This build stops at the end of step 0.** Everything below is the orchestrator's.

```
0. [THIS BUILD, DONE]  freeze commit + stamp commit on branch h2h22k-freeze,
                       pushed. BAND_CLAIM.json / BAND_CLAIMED / the
                       BAND_REGISTRY.csv row are committed on THIS BRANCH ONLY.

1. WAIT for the laptop.  carcasum_arb_challenge holds it until ~05:00 EDT.
                       Do NOT trust the clock -- run_cells.sh preflight check 9
                       refuses to start while ANY foreign RUN_LIVE.json exists
                       under measurement/, and check 10 refuses on any co-tenant
                       process. Let the launcher be the judge.

2. GET THE BRANCH ONTO THE LAPTOP.  The laptop cannot reach github
                       (reference_offline_git_bundle_sync) -- sync via
                       `git bundle` on the share + `git fetch <bundle>`, then
                       check out h2h22k-freeze there. ⚠️ STALE CODE ON THE
                       LAUNCH BOX IS THE CLASSIC CONTAMINATION; G-REV will catch
                       it after the fact, but only after the games are spent.

3. VERIFY THE BLIND.    git merge-base --is-ancestor $(cat BLIND_COMMIT) HEAD
                       must succeed, and BLIND_COMMIT must NOT be PENDING.

4. STAMP PINNED_SRC_REV (the one uncommitted act -- WORKERS.conf explains why
   this is safe and why it cannot be done in a commit):
       git -C $REPO rev-parse HEAD > $REPO/measurement/h2h_22016_prep/PINNED_SRC_REV

5. SELFTEST THE ADJUDICATOR (free, no band, no blindness, any time):
       $REPO/.venv/bin/python $REPO/measurement/h2h_22016_prep/adjudicate.py --selftest
   Must exit 0.

6. DRY RUN, and READ THE ARGV (free):
       bash $REPO/measurement/h2h_22016_prep/run_cells.sh --dry-run
   Confirm by eye: --k-dets 16 --sims 1376 --opp-k-dets 8 --opp-sims 1376,
   --backend rust, --rules-profile fixed_v1, --exact-k 2, --seed-start
   148000000000, --n 1400 --paired, and NO --cand-tiearb-* flag anywhere.

7. SMOKE, at production knobs (SS9), and CHECK ALL SIX BARS BY HAND:
       bash $REPO/measurement/h2h_22016_prep/run_cells.sh --smoke
   Bar 2 (converted_sides == [candidate, opponent]) and bar 5 (k_dets really
   16, not silently clamped) are the two this cell most needs proven LIVE.

8. LAUNCH -- chmod +x is the orchestrator's own act, and DETACH it:
       chmod +x $REPO/measurement/h2h_22016_prep/run_cells.sh
       cd $REPO/measurement/h2h_22016_prep
       setsid nohup ./run_cells.sh </dev/null >/dev/null 2>&1 & disown
   ⚠️ A detached ssh launch can return rc=124 from `timeout` AFTER launching --
   treat 124 as LAUNCHED and never retry (retries stack pools).

9. VERIFY PARALLELISM within the next tool call: `ps -o %cpu` / loadavg should
   show W=26 busy workers, not 1.

10. ARM A COMPLETION MONITOR on DONE_cell_h2h_k16x1376_vs_champ_k8x1376 (and on
    the FAILED_* sentinels). The on-disk watchdog only restarts a DEAD chain --
    it never announces a finished one. Session heartbeats at 55 min, not 60.

11. RE-PROJECT off pass 1. run_cells.sh prints a REALIZED worker-s/game after
    every pass against the 442 model. A gross miss means SS7's cost model is
    wrong and the timeout ladder should be re-derived BEFORE burning the band.

12. ADJUDICATE, then apply READ_RULE.md SS4 verbatim:
       adjudicate.py --run-dir $REPO/measurement/h2h_22016_20260824/h2h_k16x1376_vs_champ_k8x1376
   The fired branch IS the authorization to report it. Then SS10.
```
