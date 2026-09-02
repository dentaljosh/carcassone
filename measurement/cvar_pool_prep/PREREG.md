# PREREG — GT-M1, risk-asymmetric world pooling (2026-09-02)

**Status: FROZEN, NOT LAUNCHED.** No band claimed, no cell played,
`BLIND_COMMIT` `PENDING`. The source edits (rust `carc_core`/`carc-py`, three
`src/carcassonne_ai/` modules, `scripts/classical_search/eval_fair_puct.py`)
live in a build worktree; the orchestrator merges them at a quiet window,
rebuilds and installs the wheel fleet-wide, claims the bands and launches.

> ⛔ **THIS IS A STRENGTH-LEVER SCREEN, NOT AN OWNER-EDGE DISCRIMINATOR.** The
> census that licensed GT-M1 explicitly **demoted the mechanism claim**: the
> control stratum reads reach(0.25) = 0.333 against the contest-exposed 0.340,
> statistically indistinguishable, so *"a lever that fires equally on control
> plies is not explaining a contest-specific gap"*
> (`measurement/cl083_mech_censuses_20260830/READOUT.md` §1). The question this
> round asks is the surviving one: **does risk-averse world pooling make the
> champion STRONGER?** Nothing here bears on CL-083 or on the owner's edge, and
> no result may be reported as if it did.

> ⚠️ Read §5 before reading any number. At the funded n this round can **bound**
> the axis and can **detect a regression**; it cannot **confirm** at its own
> bar. That is stated here rather than discovered later.

---

## 1. Why this exists, and what is already known

### 1.1 The deployed rule, and the one this round tries

The champion's fair PIMC draws `k_dets = 16` determinization worlds, searches
each at 1376 sims, and merges their root statistics into ONE pooled `(N, W)`
accumulator. The move is `argmax_a (ΣW(a) / ΣN(a))` —
`carc_core::fair::pooled_q_argmax`. That is a **visit-weighted mean over
worlds**, and it is risk-neutral by construction: a move that is excellent in
twelve worlds and catastrophic in four can win on the average.

`GT-M1` replaces the aggregation with a **lower-tail CVaR**: action *a* scores
as the mean of its per-world `Q` over the `ceil(α·k)` worlds where it does
WORST, and the pick is the argmax of that. Small α = adversarial. **Nothing
else changes** — the same 16 worlds, the same 22016 sims, the same leaf, the
same priors, the same exact-K latch. It is an AGGREGATOR swap, not a budget or
a search change.

### 1.2 What the free census established — and what it deliberately did not

`measurement/cl083_mech_censuses_20260830` (judge-free, zero games played,
bars committed at `aa07fee0` before any number existed) ran the arithmetic on
188 `fixed_v1` contest-exposed E4 crux plies at k=8:

| α | **reach(α)** — CVaR pick ≠ deployed pick | marginal vs equal-weight pooling |
|---|---|---|
| **0.25** (worst 2 of 8) | **0.340** [0.277, 0.404] | 0.213 |
| 0.50 (worst 4) | 0.271 | 0.122 |
| 0.75 (worst 6) | 0.239 | 0.080 |
| 1.00 (all 8 = equal-weight mean) | 0.181 | 0.000 |

**Verdict: GT-M1 NOT KILLED.** The rule clears the ≥0.30 survive bar and its CI
lower end sits far above the ≤0.10 kill bar. The worlds do **not** already agree
(unanimity U = 0.367), and `P(a* is CVaR-eligible) = 1.000` on all 188 plies, so
none of the reach is the mechanical artefact `DEVIATIONS` D-2 was added to
detect.

⛔ **What the census refused to do, in its own words:** *"this census says
**nothing** about whether the CVaR pick is better. Changing 34% of moves is a
cost as easily as a gain. Pricing it requires independent-world realized-outcome
pricing … and any in-sample argmax gap on these same worlds would be inflated by
≈ +6.5 pts."*

⭐ **This round is that pricing, done the only way that dodges the inflation:
FRESH deployed-config games.** The +6.5 pt in-sample inflation is a property of
scoring an argmax-selected change on the worlds that selected it. These cells
select nothing and re-use nothing — they play new decks, both seats, and read
the scoreboard. The inflation term does not apply, and that is why the gate had
to be games rather than a cheaper re-analysis.

### 1.3 ⚠️⚠️ The α = 1.00 confound, disclosed here rather than discovered later

The census's own `DEVIATIONS.md` **D-1** records that α = 1.00 is **not** an
identity control. It is the **equal-weight-per-world** mean; the deployed rule
is **visit-weighted** (`ΣW/ΣN`). The two disagree whenever worlds spend
different visit counts on an action, which is the normal case — and the census
measured that disagreement at **18.1% of contest-exposed plies on its own.**

So the 0.340 reach at α = 0.25 is a **sum of two effects**: ~18.1pp of
re-weighting and ~21.3pp of genuine risk aversion (the `reach_vs_equalweight`
column). **Both cells below carry both effects**, because both are what
"replace the deployed pooling rule with CVaR" actually means. ⛔ **A positive
read therefore does NOT attribute the gain to risk aversion.** The arm that
would separate them is a third cell at α = 1.00 — expressible on this build,
costed in §10, and **NOT FUNDED HERE.** §9.4 states the non-inference.

### 1.4 What the axis has already returned

Nothing: **no CVaR/quantile pooling cell has ever been played in this program.**
`docs/LEVER_INDEX.md` carries no row for it (this round adds one). The nearest
neighbours are on the *width* axis, not the *aggregator* axis, and §9.5 explains
why they are a caveat rather than a prior.

---

## 2. The source change

Five files, in three layers. All of them are gated by §2.1.

**RUST.** `carc_core::fair::pool` is new: `PoolMode { Mean, CVaR { alpha } }`
plus `cvar_score` / `cvar_eligible` / `cvar_argmax`, transcribed line for line
from the census's `analyze_census13.py` and pinned against it by
`fair::pool::tests::census_transcription_*`. `SearchConfig` gains
`pool_mode: PoolMode` (default `Mean`), read at ONE site —
`fair::FairAgent::pimc_move`, in a `match` on a `Copy` enum placed immediately
before the existing `pooled_q_argmax` call. **The `Mean` arm never constructs,
allocates or reads anything in the new module**, which is the same byte-identity
discipline `tiearb_enabled == false` and `jrules_filter_mask == 0` follow.

Three departures from the census are deliberate and are recorded in
`DEVIATIONS.md`: the **empty-eligible-set fallback** (a player cannot decline to
move, so the champion's own pick stands and the event is COUNTED), the
**play-derived counters**, and the **`total_cmp` sort** (deterministic ordering
rather than a comparator that can abort a game).

**PYTHON.** `HeuristicPriorConfig` gains `pool_mode` / `pool_alpha` (appended at
the end of the field list, so every historical positional construction keeps its
meaning), validated fail-closed at BOTH settings, emitted unconditionally by
`as_manifest`. `rust_agent.search_config_rs` forwards them as CONDITIONAL
KEYWORDS — **this is the seam the FPU knob went missing at for months**, so the
values are forwarded from `cfg` and never defaulted here, and a stale wheel
raises `TypeError` on a `cvar` request rather than silently serving a
mean-pooled candidate. `make_heuristic_prior_evaluator` refuses a non-mean rule
on the python search path (rust-only, same rule as the arbiter).

**HARNESS.** `--cand-pool-mode {mean,cvar}` + `--cand-pool-alpha`, mirroring
`--cand-c-puct` / `--cand-tau-p`: they ride the existing `cand_search` dict to
the **candidate construction site alone**; the opponent builder passes
`cand_search=None`. `cand_search` gains both keys under the family's
always-present convention (`pool_mode: "mean"` is the POSITIVE statement, never
a missing key). ⛔ **There is deliberately NO shared `--pool-mode`**, because a
two-sided pooling change is a different CHAMPION, not a cell — which also means
the two-sided assertion here is unconditional rather than conditional on a
shared flag's value.

Two additions the three predecessor rounds did not have, both because this knob
changes the ROOT PICK and can therefore witness itself:

* per-game `cand_pool` / `opp_pool` telemetry read off `FairAgentRs.stats()`,
  and a per-cell `summary.pool.{candidate,opponent}` aggregate;
* the launcher and the adjudicator gate on `pickchanges > 0` (`G-REACH`, §7).

### 2.1 The golden gate — `CVAR_BITEXACT.json`

`goldengate/` (precedent: `taup_audit_leg_20260901/goldengate/` →
`fpu_resurrection_prep/selftest_fixture/`). **Four** legs on 12 frozen throwaway
decks at k4×96, and twelve checks:

| check | what it proves |
|---|---|
| `WHEEL-SWUNG` / `TREE-SWUNG` / `HARNESS-SWUNG` | ⭐ THE INVERSE of the τ_p gate's `ONE-WHEEL`/`ONE-SRC`. This change spans the rust wheel AND `src/` AND the harness, so all three are named VARIABLES: OLD ran a different binary, a different package and a different harness; the three NEW legs ran one of each |
| `OLD-WHEEL-IS-STALE` | the OLD leg's `carc_rs` has no `pool` getter — it PREDATES this round and could not have expressed the rule under any flag. **That is what `IDENTITY` is identical TO** |
| `NEW-WHEEL-IS-FRESH` | every NEW leg's wheel exposes it |
| `SAME-SEEDS` / `SAME-BUDGET` | identical decks and search shape on all four legs |
| **`IDENTITY`** | with the flag unset, play is **bit-identical to the pre-change tree AND wheel** |
| **`MEAN-COUNTERS-ZERO`** | the unset leg never entered `fair::pool` — the byte-identity premise stated as a number |
| **`POSITIVE`** | at α = 0.25 every game diverges **and** the agent's own counter says the rule decided plies and changed the pick. Two independent witnesses; a flag parsed and dropped would fail the second flat |
| **`CANDIDATE-ONLY`** | the OPPONENT pools by the deployed mean in **every** leg, dosed ones included, asserted from its own resolved config |
| **`ALPHA1-EQUALWEIGHT-ARM`** | ⚠️⚠️ see below |
| `DOSES-DISTINCT` | the two dosed legs select different tail widths |
| `AUDIT-ADJUDICATED` | the pre-change harness's REAL argparse (`main(["--help"])`) carries no `--cand-pool-mode` |

⚠️⚠️ **THE α = 1.0 LEG IS NOT AN IDENTITY LEG, AND THE BUILD BRIEF ASKED FOR ONE.**
The brief said *"α=1.0 ⇒ bit-exact with mean"*. Per §1.3 that is **false, and
the census measured it false before this round existed.** The gate therefore
runs α = 1.0 as the **equal-weight arm** — it asserts the arm is expressible and
records whether it diverges (it does) — and the bit-exact statement that IS
true, `CVaR_{1.0} == the sorted-order equal-weight mean`, is *arithmetic* and is
pinned in `carc_core::fair::pool::tests::alpha_one_is_the_sorted_order_equal_weight_mean`
where it belongs. A build that made α = 1.0 identical to the deployed mean would
be a build that got the rule wrong.

⛔ A code-path gate at a tiny budget. **No number in it is a strength
measurement** — including its `reach_in_play`, which at k=4 on self-play decks
is not the census's `reach(α)` and is not this round's.

---

## 3. The cell shape — the deployed config on BOTH seats

Constants live in `WORKERS.conf` (the ONE place) and in `cvar_lib.py` (the ONE
implementation, imported by the launcher's precondition ladder, the smoke
adjudicator and the tests, so they cannot drift). `run_cells.sh` **re-asserts**
them against `governance/PRODUCTION.yaml` at launch (`G-PROD`) — parsed as YAML
at explicit addresses, never grepped, because `deploy_profiles.mobile` carries
the same key names.

| | |
|---|---|
| opponent | `--opponent fair-champion` — the **unmodified deployed champion** |
| budget, both seats | k_dets **16** × sims 1376 = **22016** |
| endgame | `--exact-k 2`, marginalized, both seats |
| backend | rust, both seats (⛔ the rule has no python implementation) |
| rules | `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1` (env-latched at import) |
| leaf | curve125 `a36d2e15a3b3d71d`, both seats (the harness asserts it) |
| tie arbiter | **ARMED ON BOTH SEATS** at the deployed dict: B=64, J=4, mode `argmax`, salt `tiearb2-deploy-v1`, eps 0.0, phase_gate `all` |
| n | **400 decks × 2 seatings = 800 games**, `--paired` (deck-paired, seat-balanced) |
| box | the **laptop**, W = 22 |

⛔ `--paired` is not optional: without it `_build_work` returns n *distinct*
decks at one seat each, `n_paired = 0`, there is no primary, and the cell walks
`2 × n_decks` seeds — outside its own band (the PG-D9 defect).

⚠️ **`k_dets = 16` is load-bearing here in a way it was not for the three
predecessor rounds.** α is a FRACTION of k, so this cell's α = 0.25 averages the
worst **4 of 16** where the census's averaged the worst **2 of 8**. A cell that
silently ran a different width would be running a different RULE.

⚠️⚠️ **THE ARBITER AND THE POOLING RULE COMPOSE.** `pimc_move` computes the
pooled pick first and hands it to the arbiter as `champ_pick`, so on a CVaR
candidate the arbiter arbitrates ties around the CVaR pick. That is the
DEPLOYED agent plus one rule — which is exactly what a deployed-config H2H must
measure — but the two surfaces are not independently attributable inside this
cell. §9.6.

---

## 4. The two doses — read straight off the census's reach curve

| cell | `--cand-pool-alpha` | worst-of-16 | census reach | census marginal | rationale |
|---|---|---|---|---|---|
| `CELL_CVAR25` | **0.25** | worst **4** | **0.340** [0.277, 0.404] | 0.213 | ⭐ **The census's own PRIMARY and the curve's MAXIMUM.** It is the dose the ≥0.30 survive bar was cleared on and the only one whose CI is quoted. If risk-averse pooling does anything, this is where it does the most of it. |
| `CELL_CVAR50` | **0.50** | worst **8** | 0.271 | 0.122 | **The interior point.** Still 2.7× the census's 0.10 kill bar, with the risk-aversion component roughly HALVED. |

**Why not 0.75.** Its marginal risk-aversion contribution is 0.080 — *below the
census's own 0.10 kill bar*. A dose whose risk component the census could not
distinguish from inert answers nothing this round is asking.

**Why not 1.00 as a third cell.** It is the right control (§1.3) and it is
costed in §10 — but it prices the *weighting* half, and the funded question is
whether the rule as a whole helps. Buying it would be a 3-cell round at
≈ 18.6 h; that is an owner call, and §11 puts it in the queue rather than
smuggling it in.

⚠️ **The two cells are NOT a ladder and NOT a measured direction** — §9.1.

---

## 5. ⭐⭐ THE BAR, AND WHAT THE FUNDED n CAN AND CANNOT DO

### 5.1 The primary

**M = the deck-paired mean margin, candidate − opponent, in points per deck**,
on each cell separately, within its own band. Elo/winrate are reported as
secondary colour and **decide nothing**.

### 5.2 The bar

**`BAR_M = +1.0 pts/deck`**, set at the effect size the decision cares about —
**never at 2·σ̂ of the instrument** (owner ruling 2026-08-30, "effect size
sounds right").

Derivation: the only decision downstream of a positive read is *changing the
champion's pooling rule*, i.e. a champion change. The two production folds this
program has actually accepted sat at **+1.229 pts/deck** (the k16 budget
promotion) and **+1.7167 pts/game** (the arbiter B=64 fold); the FPU adoption
chain used **+1.0** and judged its realized +1.02 / +0.86 **not to clear**. So
+1.0 is the class, and it is **not** derived from this instrument's σ.

⚠️ **No clock offset is owed**, unlike the arbiter fold. CVaR pooling costs one
extra O(|legal actions|) pass per ply over statistics the search has already
computed. It buys no sims and spends none, so this is a pure strength bar with
nothing to amortise — which, if anything, argues the bar should be *lower* than
the arbiter's, not higher. It is held at the family value anyway.

**`BAR_REGRESSION = 0.0`.** A rule that changes ~a third of the champion's root
moves is not the kind of knob that can be slightly wrong. If it is wrong it
should show, and a demonstrated regression **closes GT-M1 far more cleanly than
another unresolved bound** — which is why this round carries a regression branch
where the τ_p leg did not.

### 5.3 ⛔ WHAT THE FUNDED n CAN AND CANNOT DO — stated here, not discovered later

The instrument's realized scale on this exact shape is **se(M) ≈ 0.68 pts/deck
at 400 decks** (`CELL_CPUCT10` realized SE 0.6511 at n=800 paired; both τ_p
cells reproduced it at 0.646 / 0.660). One-sided 95% intervals (z = 1.645):

* **`P-POOLING-MOVES`** (`LB95 = M − 1.645·se > 1.0`) needs **M > +2.12**.
* **`P-BOUNDED`** (`UB95 = M + 1.645·se < 1.0`) needs **M < −0.12**.
* **`P-REGRESSION`** (`UB95 < 0`) needs **M < −1.12**.

**The null's expected read distribution** (true M = 0, se = 0.68):

| branch | fires when | P under a true null |
|---|---|---|
| `P-REGRESSION` | M < −1.12 | ≈ **5%** |
| `P-BOUNDED` | −1.12 ≤ M < −0.12 | ≈ **38%** |
| `P-UNRESOLVED` | −0.12 ≤ M ≤ +2.12 | ≈ **57%** |
| `P-POOLING-MOVES` | M > +2.12 | ≈ 0.1% |

Under a **true effect exactly at the bar** (M = +1.0), `P-POOLING-MOVES` fires
only **5%** of the time. Under a **true regression of −2.0**, `P-REGRESSION`
fires ≈ **90%** and `P-BOUNDED`-or-worse ≈ 99.7%.

⭐ **So: at n = 400 decks this round can BOUND the axis below the
adoption-relevant effect and can DETECT a real regression, and it cannot
CONFIRM a gain.** That is a limitation of the funded shape, not a design.

**What would resolve the ADOPT direction.** For `P-POOLING-MOVES` to fire ≥90%
of the time against a true +1.5 you need `1.645·se < 0.5 − 1.282·se`, i.e.
`se < 0.171`, i.e. **≈ 6300 decks per cell** — about 16× the funded n,
≈ 98 h/cell on the laptop. ⛔ **Not funded, and this document does not propose
it:** buying it would need a *mechanism* argument, not more n
(`project_rodv3_fullbudget_flywheel`'s retirement is the standing lesson).

### 5.4 Why the round is still worth its 12.5 hours

Because the modal outcomes are informative in both tails. A `P-REGRESSION` or a
`P-BOUNDED` on the census's own maximum-reach dose **closes GT-M1** — the last
surviving mechanism from the CL-083 menu — with a played, judge-free,
fresh-games result, at ~43% probability under a true null and ~90% under a real
regression. And the round banks the first **played** measurement of
`reach_in_play` at the deployed k=16, which no census could produce.

---

## 6. Branch vocabulary and the read rule

Read **per cell**, after every gate in §7 passes on that cell.
`cvar_lib.read_branch(m, se)` is the ONE implementation.

| branch | fires when | what it means | what it authorizes |
|---|---|---|---|
| **`P-POOLING-MOVES`** | gates PASS and `LB95(M) > +1.0` | risk-averse world pooling moves strength at the adoption-relevant effect, at deploy budget | ⛔ **NOT a production change.** It funds ONE confirmation on a FRESH band at the §5.3 sizing, **plus** the α = 1.00 control arm (§1.3) — without which the gain cannot be attributed to risk aversion rather than to re-weighting. A single screen never promotes (house rule). |
| **`P-REGRESSION`** | gates PASS and `UB95(M) < 0` | the rule actively HURTS at this dose | ⭐ **GT-M1 is CLOSED at this dose**, on played evidence. The mechanism menu's last survivor is discharged. |
| **`P-BOUNDED`** | gates PASS and `UB95(M) < +1.0` (but not `< 0`) | the axis is bounded below the adoption-relevant effect at this dose | closes the dose *with* a bound; the dose is killed |
| **`P-UNRESOLVED`** | gates PASS, none of the above | the cell resolved nothing about effect size | ⛔ **NOT a licence to buy more n** — see §5.3 |
| **`P-VOID`** | ANY gate FAILS | there is **no read at all** | the cell is void; its band retires **unread** |

### 6.1 The round-level read

⛔ **There is no round-level statistic.** Each cell is read on its own band
against its own opponent. "Both cells `P-BOUNDED`" is two bounded doses, not a
bounded axis — the reach curve is continuous and two points on it do not bound
the interval between them, and the two cells' *difference* is cross-band (§9.1).

The **only** round-level statement this design supports is: *if both cells read
`P-BOUNDED` or `P-REGRESSION`, GT-M1 is closed at the two doses that carry
almost all of the census's measured reach* — 0.340 and 0.271 of a curve whose
maximum is 0.340 — *and the LEVER_INDEX row is written as killed-by-measurement.*

---

## 7. The gates — `cvar_lib.py`, one implementation

⛔ Every gate FAILS CLOSED, and **`MISSING` is not `None`**:
`cand_search.pool_alpha = null` is the positive statement "mean pooling takes no
alpha", while an absent key means the harness predates this round and the cell is
champion-vs-champion. No gate may collapse the two.

| gate | reads | what it asserts |
|---|---|---|
| **`G-POOL`** | manifest | six addresses: `config.cand_search.pool_{mode,alpha}` (the REQUEST) · `config.champion.pool_{mode,alpha}` (the candidate's RESOLVED config) · **`config.opponent.champ_cfg.pool_{mode,alpha}` == mean/null** (⭐⭐ the opponent) |
| **`G-REACH`** | **summary.json** | ⭐⭐ **the PLAY-DERIVED gate.** `pool.candidate.cvar_plies > 0` (the rule DECIDED), `pool.candidate.pickchanges > 0` (the rule **REACHED**), `reach_in_play ≥ 0.01`, `pool.opponent.cvar_plies == 0` (the ZERO CONTROL, read off the opponent's own agent), `modes_disagree is False` (no mid-cell rev split) |
| `G-SINGLEVAR` | manifest | `cand_search.{fpu_reduction,c_puct,tau_p}` all **present and null** — one live variable only |
| `G-BUDGET` | manifest | k16×1376=22016 and exact-k 2 marginalized on **both** seats, rust, `fixed_v1`, `paired`, 2 seatings/deck |
| `G-ARB` | manifest | the arbiter ARMED at the deployed dict on **both** seats (the opponent block is absent-when-unarmed by design, so ABSENT here is a FAIL) |
| `G-PROD` | (launcher) | the frozen budget/arbiter still equal `governance/PRODUCTION.yaml` at `champion.fair_deploy` |

⭐⭐ **`G-REACH` IS THE ONE THIS ROUND HAS AND ITS THREE PREDECESSORS DID NOT.**
τ_p, FPU and c_puct could only be gated on config, because nothing they did was
visible in play without a bespoke census. They are exactly the rounds this
program has twice caught with a knob that never bound — the hard-coded-`None`
FPU slot and the phasegate smoke that adjudicated zero cells. GT-M1 changes the
ROOT PICK, so the agent counts its own pick changes and the gate reads them out
of the played record. **`pickchanges == 0` over a nonzero `cvar_plies` is a
`P-VOID`, and every config gate in the table above would pass that cell.**

⚠️ **No leaf hash moves on this knob**, so `cand_leaf_hash` *equals* the
opponent's on a live cell and a moved-hash check proves nothing. The resolved
manifest plus `G-REACH` are the wiring gates — which is why the gate addresses
were read off a **real emitted manifest** and are asserted against the
byte-untouched original in
`test_cvar_pool.py::test_every_gate_address_exists_in_real_emitter_output`.

---

## 8. Blindness, bands, and the launcher's refusals

`run_cells.sh` fails closed, before a deck is spent, on **all** of:

1. `CVAR_BITEXACT.json` missing, not `PASS`, or not over the **full frozen
   12-seed set** (a preview pass may not spend a band);
2. `WORKERS.conf`'s `BLIND_COMMIT` still `PENDING` (real cells);
3. the sibling `BAND_CLAIMED` file absent (real cells) — see
   `BAND_CLAIMED.placeholder`; **this agent claimed nothing**;
4. **the box cannot express the cell** — a live probe that drives the real
   argparse, builds both sides' configs, reads the pooling rule back out of
   `SearchConfigRs.pool` (a real getter, not a repr regex) and **plays two
   moves with a CVaR agent to witness a nonzero `pool_cvar_plies`**. A box on a
   stale bundle or a stale WHEEL would otherwise produce a
   champion-vs-champion cell with a healthy leaf hash and a plausible dirname;
5. `G-PROD` disagreement with `PRODUCTION.yaml`.

A full-args process census runs before every real launch. The launcher
**self-detaches** (`setsid nohup nice -n 19`) and drops a `RUN_LIVE.json`
sentinel, which the freeze-latch hook reads.

⚠️⚠️ **THE LAUNCHER IS INVOKED BY PATH, NEVER PIPED.** It resolves its own
directory from `${BASH_SOURCE[0]}` to find `WORKERS.conf`, and under
`ssh host 'bash -s' < run_cells.sh` `BASH_SOURCE` is not a path — the script
would resolve `HERE` to `$HOME` and either die or, worse, source nothing. The
absolute-path form is also exactly what the repo's "never rely on `cd` in an SSH
command" rule asks for. §11 carries the exact invocation.

### 8.1 The smoke

Per cell, on that cell's own throwaway offset, at **PRODUCTION knobs** —
arbiter armed both seats, the dose on the candidate — with only the game count
reduced (8). It is then **adjudicated from its own emitted manifest AND its own
summary.json** by `adjudicate_cvar_smoke.py`, which **exits nonzero** on a missing
dir, a missing manifest, an unparseable manifest, **zero per-game records**, a
missing summary, or any gate failure. ⛔ The smoke emits **no outcome key** (a
test asserts this); its 8 games decide nothing and may never be pooled.

⭐ The smoke is the first place `G-REACH` can fire on real production-budget
play, and it is cheap: 8 games is enough for `pickchanges > 0` to be
overwhelmingly likely at a reach of ~0.2–0.3 per ply over ~140 plies/game.

---

## 9. ⛔ NON-INFERENCE LIMITS

1. **The two cells are on DIFFERENT bands.** Comparing `CELL_CVAR25` against
   `CELL_CVAR50` is a **cross-band** contrast and is over-dispersed 1.8–2.2×
   (CL-068). ⛔ **Do not read "0.25 vs 0.50" as a measured direction on the α
   axis**, and never pool the two cells into one estimate. The robust class is
   each cell's own **within-band deck-paired** contrast with its own opponent.
2. **A single screen never promotes.** `P-POOLING-MOVES` funds one confirmation
   on a fresh band **and** the α = 1.00 control; it does not move
   `PRODUCTION.yaml`.
3. **The ADOPT bar can only be approached from below** at this n (§5.3). An
   `UNRESOLVED` pair is a statement about the funded shape, not about the axis.
4. **A positive read does NOT attribute the gain to risk aversion.** Both doses
   carry the α = 1.00 re-weighting effect (~18.1pp of the census's 34.0pp reach)
   as well as the risk-aversion effect. Only the unfunded α = 1.00 arm separates
   them (§1.3).
5. ⚠️⚠️ **THE CL-054 INVERTED-U CAVEAT, WRITTEN IN BEFORE ANY NUMBER EXISTS.**
   At fixed total budget the `k_dets` **width** axis is an inverted U peaked at
   k=4 (k32 < k16 ≈ k8 < k2 < k4; CL-054, adopted 2026-07-13). CVaR at α = 0.25
   over k = 16 bases the decision on a **4-world lower-tail mean** — and while
   that is *not* a width reduction (all 16 worlds are still fully searched at
   22016 sims; only the AGGREGATION uses 4), the **estimator's variance rises**:
   the mean of the worst 4 of 16 is a noisier statistic than the mean of all 16,
   and CL-054 is direct evidence that this program's PIMC is sensitive to
   effective-sample-size effects in exactly this aggregation. ⛔ **Consequence,
   pre-registered:** a negative read at α = 0.25 with a *less* negative read at
   α = 0.50 is **equally consistent with a noise story and a risk story**, and
   may NOT be reported as "risk aversion hurts". It may only be reported as
   "the aggregator at this tail width hurts". Distinguishing them needs the
   α = 1.00 arm plus a variance decomposition, neither of which is funded.
6. **The arbiter and the pooling rule compose** (§3). Both seats carry the
   deployed arbiter and the candidate's arbitrates around the CVaR pick, so
   `M` prices *the deployed agent with its pooling rule swapped*, which is the
   right estimand for an adoption decision and the wrong one for attributing an
   effect to either surface alone.
7. **`reach_in_play` is not the census's `reach(α)`.** Comparable in KIND only:
   the census measured k=8 on a fixed E4 crux corpus with a per-world
   eligibility rule applied to 8 worlds; this counts k=16 over whole self-played
   games including non-crux plies. ⛔ A gap between the two numbers is not a
   finding.
8. **The census licensed "not inert", not "where the edge lives"** (§0's
   scoping note). Nothing here bears on CL-083.
9. **W is throughput-only.** Games are bit-identical at any W and no gate here
   reads a clock. No timing statistic is a branch input.
10. **The golden gate is a code-path gate** at k4×96. No number in it is a
    strength measurement.
11. **A band that influences a decision retires from confirmatory use.** Both
    bands here will have.

---

## 10. Cost

| item | box | ETA |
|---|---|---|
| golden gate, full 12 seeds, 4 legs | any idle box | ~10–15 min |
| smoke, per cell (8 games, production knobs) | laptop W=22 | ~4 min |
| `CELL_CVAR25` (800 games) | laptop W=22 | **6.2 h** |
| `CELL_CVAR50` (800 games) | laptop W=22 | **6.2 h** |
| **total, serial** | laptop | **≈ 12.5 h** |
| *(unfunded)* α = 1.00 control arm, 800 games | laptop W=22 | *+6.2 h* |

⚠️ The ETA is a **point, not a bracket** — unlike the τ_p leg's. W = 22 is a
**measured** operating point: the 2026-08-31 arb-on laptop sweep priced it at
**129.0 g/h** at this exact cell shape (k16×1376 both sides, deployed arbiter
dict, fixed_v1 + R9, rust, exact-k2, leaf `a36d2e15a3b3d71d`). 800 / 129.0 =
6.20 h.

⚠️ W = 22 rather than the owner's 24-thread ruling because the laptop keeps two
threads for his pinned-playout Carcasum server (owner, 2026-09-01 ~22:40 EDT,
verbatim *"change it at tau8. carcasum is taking 30s a turn"*), which was still
running at this round's freeze. W is throughput-only and this resolves no bar.

---

## 11. Launch, when authorized

```bash
# 1. the FULL golden gate (4 legs, 12 frozen seeds)
./measurement/cvar_pool_prep/goldengate/run_gate.sh

# 2. per cell, ON THE LAPTOP, BY ABSOLUTE PATH — ⛔ NEVER piped through
#    `bash -s`: the launcher resolves WORKERS.conf from ${BASH_SOURCE[0]}
#    and stdin is not a path.
ssh laptop-wsl '/home/doctor/projects/carcassone/measurement/cvar_pool_prep/run_cells.sh --cell CELL_CVAR25 --smoke'
#    ... then read SMOKE_CELL_CVAR25.json
ssh laptop-wsl '/home/doctor/projects/carcassone/measurement/cvar_pool_prep/run_cells.sh --cell CELL_CVAR25'
#    self-detaches; logs/CELL_CVAR25.log
# ... then the same two for CELL_CVAR50.
```

⛔ **Preconditions, in order:** merge the five source edits at a quiet window →
**rebuild `carc_rs` at `RUSTUP_TOOLCHAIN=1.96.0` and install it on every box
that will play** (⚠️ this round is the first in the family that needs a WHEEL
change, so a bundle sync alone is NOT enough — the launcher's probe refuses a
stale wheel, but only after someone tries) → sync the bundle to the laptop →
re-run the full golden gate → claim the two bands
(`BAND_CLAIMED.placeholder`) → stamp `BLIND_COMMIT` in **both**
`BLIND_COMMIT.json` and `WORKERS.conf` → smoke each cell → launch.
