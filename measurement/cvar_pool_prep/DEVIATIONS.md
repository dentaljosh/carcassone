# DEVIATIONS — GT-M1 risk-asymmetric world pooling (2026-09-02)

Everything the build did that a reader of `PREREG.md` alone would not expect,
everything it could not do, and every place it departs from the brief it was
given. Written at the freeze, before any cell exists.

---

## D-0 — the source edits are NOT in the main tree

Five files (`rust/carc/carc-core/src/{fair/pool.rs,fair/mod.rs,search/mod.rs}`,
`rust/carc/carc-py/src/lib.rs`,
`src/carcassonne_ai/{heuristic_prior_mcts,rust_agent,champion_factory}.py`,
`scripts/classical_search/eval_fair_puct.py`) live in the build **worktree**.

A live strength run (`measurement/defense_mech_synth_prep`, band 174e9) was
executing from a separate pinned worktree (`/home/doctor/carc-synth-run`)
throughout the build, and spawn respawns / new `--shared-claim` cells re-import
from disk — so a main-tree source edit could have crashed live workers or
created mixed-rev cells (`feedback_worktree_isolation_live_tree`).

⛔ **The orchestrator merges at a quiet window**, and — uniquely for this
round — must then **rebuild and install the `carc_rs` wheel fleet-wide**
(`BAND_CLAIMED.placeholder` step 2). Until then, the launcher's four-layer
plumbing probe is what stands between a stale box and a champion-vs-champion
cell, and it is a *hard refusal*, not a warning.

---

## D-1 — ⚠️⚠️ THE BRIEF'S "α = 1.0 ⇒ BIT-EXACT WITH MEAN" IS FALSE, AND THE CENSUS ALREADY MEASURED IT FALSE

The build brief asked for a golden-gate leg proving *"α = 1.0 ⇒ bit-exact with
mean"*. **That proposition is false**, and it is false for a reason the
licensing census disclosed in writing before this round existed.

* The **deployed** rule is `argmax_a ΣW(a) / ΣN(a)` — a **visit-weighted** mean
  over worlds. Worlds that spent more visits on an action count for more.
* **CVaR at α = 1.0** takes the whole lower tail, i.e. all k worlds, with
  **EQUAL weight per world**.

They coincide only when every world spends identical visits on every action,
which PUCT guarantees it will not. `measurement/cl083_mech_censuses_20260830/
DEVIATIONS.md` **D-1** says so in terms and refuses to call α = 1.00 an identity
control: *"alpha=1.00 is the EQUAL-WEIGHT-WORLDS mean of per-world Q, which is
NOT the deployed pooled Q = sum(W)/sum(N) whenever visit counts differ across
worlds. So it is not an identity control."* The census measured that rule
changing the champion's pick on **18.1%** of contest-exposed plies **by itself**,
and added a whole `reach_vs_equalweight` column to isolate it.

**What was built instead, and why it is better than what was asked for:**

1. The **arithmetic** statement that IS true is pinned as a rust unit test —
   `fair::pool::tests::alpha_one_is_the_sorted_order_equal_weight_mean` — and it
   is sharper than the brief's: `CVaR_{1.0}` equals the **sorted-order**
   equal-weight mean, `sorted(q).sum() / k`. ⚠️ Not the naive-order mean: float
   addition is not associative, the census sums the sorted prefix, and the test
   uses a fixture where the two differ in the last bits so that a "harmless"
   reordering fails it.
2. The **game-level** leg still runs, as `ALPHA1` — but adjudicated as the
   **equal-weight ARM**, not as an identity. `identity_diff.py`'s
   `ALPHA1-EQUALWEIGHT-ARM` check asserts the arm is expressible and RECORDS
   whether it diverges. It did: **12/12 games differ from the mean-pooled leg,
   reach_in_play 0.0452 at k4×96.**
3. `test_cvar_pool.py::test_the_golden_gate_records_that_alpha_one_is_not_the_deployed_mean`
   asserts `identical_to_mean is False`, so a future reader who "fixes" α = 1.0
   into an identity has to delete an assertion that names the artefact.

**Consequence for the ROUND, carried into `PREREG.md` §1.3 and §9.4:** both
funded doses conflate risk aversion with re-weighting. ~18.1pp of the census's
34.0pp reach at α = 0.25 is the weighting effect. ⛔ A positive read therefore
may NOT be attributed to risk aversion. The separating arm is a third cell at
α = 1.00 — expressible on this build, costed at +6.2 h in §10 — and it is
**NOT FUNDED**. This is flagged as the single most important thing for the
orchestrator to decide before launch.

---

## D-2 — a 2-game BUILD-TIME DRY CELL was played, and it found a real defect

To seed the selftest fixture from the **real emitter** rather than by hand (the
fixture trap; three realized incidents in this program) the build ran one
genuine cell on the laptop:

    --cand-pool-mode cvar --cand-pool-alpha 0.25, --opponent fair-champion,
    k2 x 32, exact-k 2, arbiter armed BOTH seats at the deployed dict,
    fixed_v1 + R9, rust, --n 2 --paired --seed-start 175999999000
    --allow-selfplay-seeds

* **Throwaway seeds, no band spent.** `175999999000-1` sits in this round's
  throwaway sub-range.
* **It emits no readable outcome.** Two games at 1/344th of the deploy budget
  decide nothing and may never be pooled or quoted.
* ⭐ **It paid for itself immediately.** `config.opponent.champ_cfg.pool_mode`
  came back **ABSENT**. `config.opponent.champ_cfg` is the **FIVE-KNOB SHARED
  DICT** (`c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm`, plus
  the `fpu_reduction: None` that `G-FPU` needed), **not** a resolved
  `as_manifest()` — so `G-POOL`'s opponent address did not exist. A gate at a
  non-existent address returns `MISSING`, and in a lib that failed OPEN it would
  have passed **vacuously** on every cell forever (the IS-D1 defect).
  **Fix:** `eval_fair_puct` now states the opponent's rule POSITIVELY in that
  dict (`"pool_mode": "mean", "pool_alpha": None`), at both `champ_cfg_dict`
  construction sites — the exact move `fpu_reduction: None` made for `G-FPU`,
  and inert for construction because `_cfg_from_dict` reads five keys by name.
  The dry cell was then **re-run** against the corrected emitter, and
  `selftest_fixture/REALCELL_DRY/` holds that second run byte-untouched.
* `SMOKE_PASS/` promotes **six budget numbers only** (listed in `SPECS.json`),
  because a fixture that genuinely ran k16×1376 would cost ~6 h. Every key path,
  every other value and the whole document shape are the emitter's.

---

## D-3 — ⚠️ A REAL CROSS-BOX DEFECT, FOUND BY THE GATE: python 3.14 validates argparse help strings

The first golden-gate run **died on the laptop** with
`ValueError: badly formed help string`, at PARSER BUILD time — i.e. the harness
would not start at all.

Cause: **python 3.14's `argparse` validates every help string through
%-formatting** (`_check_help`), so a bare `%` raises. The new `--cand-pool-mode`
help quoted the census's "34.0%" and "18.1%". **The local build box runs python
3.12, which does not validate — and the LAPTOP, where these cells run, runs
3.14.** A help string that is perfectly fine on the build box is a hard crash on
the play box.

⛔ **This is a defect class, not a typo:** any future help-string edit that
quotes a percentage will do the same, and it will only show up on the box that
matters. Fixed by escaping to `%%`, and pinned by two tests —
`test_the_flags_exist_in_the_real_argparse_and_the_help_renders` (drives the
real `main(["--help"])`) and `test_help_strings_have_no_unescaped_percent`
(static, so the reason is greppable on a 3.12 box).

⭐ Worth propagating: it is only visible because this build ran its gate on the
box the cells will play on rather than on the box it was built on.

---

## D-4 — the golden gate ran on the LAPTOP, from a shipped tree and a `--target` wheel

The brief said to run the gate for real, not as a preview. It was, on the full
frozen 12-seed set, 4 legs, **14/14 PASS** — but on the **laptop**, not the
build box, and from artifacts shipped there.

**Why not the build box.** At gate time the local box was saturated by the live
`defense_mech_synth_prep` round: loadavg 31.27 on 32 threads at W=30, and that
round runs every unit under `run_isolated(..., arm_cap_secs=1800)` — a wall cap
that turns a slowed unit into `TIME_SKIPPED`, i.e. a **LOST unit of a
band-spending round**, not merely a slow one. Observed unit times were 115.6 s
median / 160 s max against the 1800 s cap, so the margin was ~11× and the true
risk was low — but the τ_p leg's D-2 took a 4-seed preview rather than accept
the same hazard, and the brief asked for a full gate. The laptop was idle
(loadavg 0.02 on 24 threads) **and is the box these cells will play on**, which
makes it the strictly better host: the gate now certifies the plumbing where it
matters.

**How it was hosted, and the exemption it uses.** The brief forbids installing
the new wheel into the venv (it serves the live run). So:

* the wheel was built on the local box at `RUSTUP_TOOLCHAIN=1.96.0` (verified
  `rustc 1.96.0`) and `pip install --target`ed into
  `/home/doctor/carc-cvar-gate/wheel` on the laptop, reached by `PYTHONPATH`;
* the NEW tree was `tar`red from the build worktree into
  `/home/doctor/carc-cvar-gate/newtree`; the OLD tree is
  `git archive HEAD src engine scripts governance` into `oldtree`;
* the **OLD leg deliberately omits the wheel prefix**, so it runs the
  `carc_rs` already installed in the laptop venv. `run_gate.sh` pre-flights that
  this binary has **no `pool` getter** and refuses otherwise — without that
  check the OLD leg could silently run the NEW binary and `IDENTITY` would be
  comparing the change to itself.

⚠️ **The banked gate is therefore NOT a certificate of the deployed artifacts.**
It certifies *these bytes*. `BAND_CLAIMED.placeholder` step 5 requires a
post-merge, post-install re-run against the real tree and the real installed
wheel before a band is spent, and `run_cells.sh` refuses anything but a
full-frozen-set PASS.

⚠️ The wheel is `cp312-abi3` and ran under the laptop's python **3.14** — which
is what abi3 is for, and is also how the venv's own wheel is installed there.

---

## D-5 — three deliberate departures from the census's arithmetic

`fair::pool` is a line-for-line transcription of `analyze_census13.py` with
exactly three departures, each because the census was an ANALYSIS and this is a
PLAYER:

1. **The empty-eligible-set fallback.** The census returns `reach[α] = None` for
   a ply with no CVaR-eligible action and does not count it. A player cannot
   decline to move. So `cvar_argmax` returns `action: None` and the AGENT falls
   back to the champion's own `pooled_q_argmax` for that ply. It is **counted**
   (`pool_fallbacks`, surfaced in `summary.pool.*.fallbacks` and
   `fallback_rate`), never silent, and it biases any measured effect **toward
   zero** rather than in an unknown direction. Realized rate: **0/1498 plies**
   at the gate's k4×96, **8/128** at the dry cell's k2×32 (k=2 is a degenerate
   width for a cross-world eligibility rule); expected ~0 at the cells' k16×1376.
2. **The play-derived counters** (`pool_cvar_plies`, `pool_pickchanges`,
   `pool_fallbacks`, `pool_eligible_total`) and the per-ply `MoveInfo` fields.
   The census had no agent to instrument. These cost one extra
   `pooled_q_argmax` per ply **on the CVaR arm only** — the Mean arm is
   untouched — and they are what `G-REACH` reads.
3. **`total_cmp` for the sort**, where python's `sorted` on floats would raise
   on NaN and rust's `partial_cmp` would panic. A NaN cannot reach there
   (`Q = W/N` with `N ≥ min_visits ≥ 1`), but a root argmax must not be at the
   mercy of a comparator that can abort a game.

---

## D-6 — `config.champion.pool_*` moves `_config_hash` by two keys, for every config

`HeuristicPriorConfig.as_manifest()` now emits `pool_mode` / `pool_alpha`
**unconditionally**, so `champion_factory._config_hash(cfg.as_manifest())` moves
by exactly two keys for EVERY config, both sides alike. This is the same one-off
move `fpu_reduction` and `tiearb_phase_gate` each made, and it is safe for the
same reason: `_config_hash` is never pinned to a literal anywhere (a repo-wide
grep finds only its definition and one use — the only consumers compare two LIVE
configs to each other). ⛔ The **leaf** hashes do NOT move: pooling is not a
`LeafConfig` field, and the champion's `a36d2e15a3b3d71d` /
`158f17ff76adaa02` / `6dfffd57051690f2` recompute unchanged on a default-off
rebuild — which `BAND_CLAIMED.placeholder` step 2 requires be verified per box.

---

## D-7 — the launcher is BY-PATH-ONLY, and it says so at runtime

`run_cells.sh` resolves `WORKERS.conf` from `${BASH_SOURCE[0]}`. Under the house
pipe pattern `ssh host 'bash -s' < run_cells.sh` the body arrives on **stdin**,
so `BASH_SOURCE[0]` is not a path: `HERE` would resolve to the remote `$HOME`
and the `.` of `WORKERS.conf` would source **nothing**, leaving every constant
unbound.

The τ_p launcher documents the pipe form in its own header **while using
`BASH_SOURCE`** — a latent instance of exactly this bug that happened not to
fire. This launcher **detects the piped case and refuses with a one-line
message** naming the correct invocation, and PREREG §11 and
`BAND_CLAIMED.placeholder` step 8 give only the absolute-path form. That form
also satisfies the repo's "never rely on `cd` in an SSH command" rule, since it
depends on no starting directory.

---

## D-7b — the round's modules are `cvar_lib` / `adjudicate_cvar_smoke`, NOT `leg_lib` / `adjudicate_smoke`

The house name for a round's one-implementation module is `leg_lib.py`, and this
round started out following it. **It broke 20 tests the moment the suites were
run together.**

`measurement/taup_audit_leg_20260901/leg_lib.py` already owns that name. Both
test files do `sys.path.insert(0, <own dir>)` then `import leg_lib`, so in a
shared pytest process whichever suite is collected first wins `sys.modules` and
the other silently gets the WRONG constants and the WRONG gates. Every failure
looked like a logic bug and none of them were.

⛔ This is the **"test import collision"** defect the 2026-08-30 weekend merge
review filed as launch-blocking, recurring under a different name. Fixed by
giving this round's modules UNIQUE basenames — `cvar_lib.py` and
`adjudicate_cvar_smoke.py` — rather than by papering over it with importlib
gymnastics, so the collision cannot come back when a fourth round copies this
one. ⚠️ The next round in this family should do the same: the house convention
is a per-round module, and a per-round module needs a per-round NAME.

Verified: the five banked knob-family suites plus the τ_p leg's plus this
round's all pass in ONE process.

---

## D-8 — no adjudicator for the REAL cells is shipped here

This round ships a **smoke** adjudicator (`adjudicate_cvar_smoke.py`, structural keys
+ `G-REACH`) and the gates (`cvar_lib.py`), plus the read rule as code
(`cvar_lib.read_branch`) — but not a full outcome adjudicator. The read-out is
§6's branch map applied to `summary.json`'s `paired_mean_margin` and its
realized SE, which the FPU family's banked machinery already computes. Writing a
fourth copy of that arithmetic would be the drift this round's "one
implementation" rule exists to prevent.

⚠️ Whoever reads the cells must apply §6 **as written**, must run **`G-REACH`
first** (a cell that did not reach has no read at all), and must respect §9.1
(the two cells are cross-band) and §9.5 (the CL-054 noise-vs-risk
indistinguishability).

---

## D-9 — what this build did NOT do

* **Launched nothing, claimed no band, edited no `governance/`.** The only games
  played are the golden gate's 48 (4 legs × 12 seeds, k4×96) and the 2-game
  k2×32 dry cell — 50 games total, all on the throwaway sub-range
  `175999999xxx`, none of it part of any claim.
* **Did not install the new wheel into any venv.** It lives in
  `/home/doctor/carc-cvar-gate/wheel` on the laptop and in the build box's
  scratchpad, reached by `PYTHONPATH` only.
* **Did not add the `docs/LEVER_INDEX.md` row**, the `STATUS.md` block or the
  roadmap line. Those are close-out touches and this round has not run; the
  index row in particular should be written by whoever knows the outcome. ⚠️ But
  it is owed the moment the round exists: the index is keyed by *intervention*,
  and "CVaR / quantile world pooling" currently has NO row, which a future
  reader's grep would read as "nobody tried it".
* **Did not measure the cells' wall clock at the deployed budget.** The ETA is
  the 2026-08-31 laptop sweep's measured 129.0 g/h at this exact cell shape, not
  a fresh bench.
