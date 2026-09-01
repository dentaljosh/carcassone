# PREREG — the τ_p audit leg (2026-09-01)

**Status: FROZEN, NOT LAUNCHED.** No band claimed, no cell played, `BLIND_COMMIT`
`PENDING`. The one source edit (`scripts/classical_search/eval_fair_puct.py`)
lives in a worktree; the orchestrator merges it at a quiet window.

> ⛔ **THIS IS AN AUDIT-RETIREMENT LEG, NOT AN EFFECT HUNT.** Its job is to close
> the last unclosed limb of the 2026-08-29 false-negative audit by making a
> candidate-side τ_p cell *expressible* on the classical champion and running it
> once. The prior on the axis is LOW and is stated as such in §1. Read §5 before
> reading any number: at the funded n this leg can **bound** the axis, it cannot
> **confirm** at its own bar, and that is said here rather than discovered later.

---

## 1. Why this exists, and what is already known (the honest prior)

### 1.1 The audit limb

The 2026-08-29 false-negative audit found that `--c-puct` and `--tau-p` in
`scripts/classical_search/eval_fair_puct.py` are **SHARED flags**: they build
`champ_cfg_dict`, and `_make_opponent` feeds that *same dict* through the *same*
`_cfg_from_dict`. So either flag moves **both seats**, and a cell built on one
against `--opponent fair-champion` is a champion-vs-champion null wearing a real
cell's name.

`--cand-c-puct` was built, and its cell ran and adjudicated (`F-REKILL`,
`experiments/results.csv` `fpu_resurrection_CELL_CPUCT10_F_REKILL_n800paired_b157e9`).
**`--cand-tau-p` was never built.** The FPU round said so in terms, in
`measurement/fpu_resurrection_prep/screen_lib.py::TAU_PAIR_SPEC["plumbing"]`:

> "⚠️ tau_p is ALREADY a candidate-reachable knob path-wise (it rides
> `champ_cfg_dict` like c_puct) — which means it has the SAME defect c_puct does:
> `--tau-p` moves BOTH SIDES. A tau round needs `--cand-tau-p` added to
> `cand_search` exactly as `--cand-c-puct` was. ⛔ NOT built here."

So **no candidate-side τ_p cell has ever been expressible against the fair
champion.** That, and only that, is what this leg closes.

⚠️ **Be precise about "never expressible."** τ_p *has* been measured on the
candidate before — but only against the **h800 rung**, which is built from the
env `DEFAULT_CONFIG` through `_RungPrefix`, *not* from `champ_cfg_dict`. Against
that opponent the shared flag is not a defect at all. The gap is specifically the
**deployed-config head-to-head** (`--opponent fair-champion`), which is the shape
every modern adoption decision uses.

### 1.2 What the axis has already returned — all of it null

| evidence | shape | result |
|---|---|---|
| `c5_s4_curve125_taup3` / `taup8` (`experiments/results.csv`) | n=200 each, vs the h800 rung | the S4 bracket {3, 8} read **flat**; `docs/LEVER_INDEX.md` records "τ=5 confirmed, null elsewhere" |
| T3 Optuna joint knob sweep (`measurement/classical_search/OPTUNA_KNOB_SWEEP_DESIGN.md`, `t3_s3/`) | `tau_p` log-uniform **[3.0, 8.0]** with a **pinned opponent** | two trials fired at rung C (τ 5.42, τ 5.94) and **both DIED at fair transfer**: t27 +4.7 elo / paired z −0.55; t020's n=400 +32.1/z1.68 spike **COLLAPSED to +3.4 / z +0.73 at n=800** (CL-057, DECISIONS 2026-07-15) |
| standalone τ bracket | — | **DECLINED by the owner 2026-07-06** (`docs/LEVER_INDEX.md` line 106) |
| `TAU_PAIR_SPEC` (fpu_resurrection_prep) | conditional on CELL_CPUCT10 moving ≥2σ | **DID NOT TRIGGER.** Realized M = −0.6325, SE 0.6511, z_M = −0.971, all gates PASS. `ROUND_ADJUDICATION.json::tau_conditionality`: `"triggered": false … ⭐⭐ THE tau PAIR IS RE-KILLED AND NOT FUNDED"` |

⛔⛔ **THIS LEG IS NOT `TAU_PAIR_SPEC`.** That pre-registered pair (`CELL_TAU8` at
8.0, `CELL_TAU12` at 12.0) was **re-killed and remains unfunded**; its funding
conditionality dissolved when CELL_CPUCT10 read |z| 0.971. This leg is funded
**separately, by the owner on 2026-09-01, on different grounds** — retiring the
audit limb. Different doses (§4), different rationale, a bar set by *this*
decision (§5). ⚠️ `CELL_TAU8` here shares a *name* with a cell of that spec; it
is not that cell and must not be pooled with anything.

### 1.3 What "success" means here

Success is **the limb closes**, not "τ_p wins." A gated read of any sign
discharges the audit item, because what was open was *expressibility*. See §6.

---

## 2. The one source change

`scripts/classical_search/eval_fair_puct.py` gains `--cand-tau-p`, an exact
mirror of `--cand-c-puct`:

* it rides the existing `cand_search` dict to the **candidate construction site
  alone** (`_build_champ_cfg`); the opponent builder passes `cand_search=None`
  and is untouched;
* `cand_search` gains `tau_p` (the request) and `shared_tau_p` (the shared
  `--tau-p` beside it), under the family's **always-present** convention:
  `tau_p: null` is the POSITIVE statement "the shared `--tau-p`", never a missing
  key;
* refused at launch when non-finite or ≤ 0 — τ_p is a softmax **denominator**, so
  0 divides and a negative value silently *inverts* the priors;
* resolved once at launch and **read back out of the rust `SearchConfigRs`**
  (parsed numerically, because rust's `Display` for f64 prints 5.0 as `5`);
* a launch-time **two-sided assertion** that the opponent-dialect config still
  carries the shared knobs, i.e. that nothing leaked;
* the auto out-dir tag gains `-candtau{v:g}` so a dosed cell can never share a
  directory (and therefore a cached per-game record) with the champion — Trap 1.

⭐ **Unset ⇒ bit-identical, everywhere.** `tests/test_fpu_knob.py`'s exact-shape
assertion on `config.cand_search` was updated (additively, with the reason in
place) and is the only banked test the change touches. Every banked adjudicator
digs `cand_search` **by key name**, never by key set.

### 2.1 The golden gate — `TAUP_BITEXACT.json`

`goldengate/` (precedent: `measurement/fpu_resurrection_prep/selftest_fixture/`
→ `FPU_BITEXACT.json`). Three legs on 12 frozen throwaway decks at k2×96, and
nine checks:

| check | what it proves |
|---|---|
| `ONE-WHEEL` / `ONE-SRC` | the `carc_rs` binary and `src/carcassonne_ai` are **constants** of the comparison — this change touches neither |
| `ONE-FILE` | OLD loaded a different `eval_fair_puct.py`; the control ran on the same file NEW did. **The variable is one file**, which is tighter than the FPU precedent's whole-tree swing |
| `SAME-SEEDS` / `SAME-BUDGET` | identical decks and search shape on all three legs |
| **`IDENTITY`** | with the flag unset, play is **bit-identical** to the pre-patch harness |
| **`POSITIVE`** | at the control dose **every game diverges** — the knob binds |
| **`CANDIDATE-ONLY`** | the OPPONENT's resolved config carries the shared τ_p in **every** leg, including the control. ⭐⭐ This is the proposition `--tau-p` itself fails |
| `AUDIT-ADJUDICATED` | the pre-patch harness's **real argparse** (driven via `main(["--help"])`) carries no `--cand-tau-p`; the patched one does |

⛔ A code-path gate at a tiny budget. **No number in it is a strength
measurement.** It proves the default path is unmoved and the knob binds on the
candidate only; it says nothing about whether the knob helps.

---

## 3. The cell shape — the deployed config on BOTH seats

Constants live in `WORKERS.conf` (the ONE place) and in `leg_lib.py` (the ONE
implementation, imported by the launcher's precondition ladder, the smoke
adjudicator and the tests, so they cannot drift). `run_cells.sh` **re-asserts**
them against `governance/PRODUCTION.yaml` at launch (`G-PROD`) rather than
trusting the restatement — parsed as YAML at explicit addresses, never grepped,
because `deploy_profiles.mobile` carries the same key names.

| | |
|---|---|
| opponent | `--opponent fair-champion` — the **unmodified deployed champion** |
| budget, both seats | k_dets 16 × sims 1376 = **22016** |
| endgame | `--exact-k 2`, marginalized, both seats |
| backend | rust, both seats |
| rules | `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1` (env-latched at import) |
| leaf | curve125 `a36d2e15a3b3d71d`, both seats (the harness asserts it) |
| tie arbiter | **ARMED ON BOTH SEATS** at the deployed dict: B=64, J=4, mode `argmax`, salt `tiearb2-deploy-v1`, eps 0.0, phase_gate `all` |
| n | **400 decks × 2 seatings = 800 games**, `--paired` (deck-paired, seat-balanced) |
| box | the **laptop**, W=24 |

⛔ `--paired` is not optional: without it `_build_work` returns n *distinct* decks
at one seat each, `n_paired = 0`, there is no primary, and the cell walks
`2 × n_decks` seeds — outside its own band (the PG-D9 defect).

---

## 4. The two doses — bracketing the default from both sides

The champion's `tau_p` is **5.0** (`governance/PRODUCTION.yaml`
`champion.agent_knobs.tau_p`). One cell each side of it, both **inside T3's
measured-safe interval**:

| cell | `--cand-tau-p` | side | one-line rationale |
|---|---|---|---|
| `CELL_TAU3` | **3.0** | sharper priors | The **LOW end of T3's log-uniform `tau_p` search space [3.0, 8.0]**, whose design note reads "S4 bracket {3,8} flat; **τ=2 known-bad (~−38); don't leave the measured-safe interval**" — so 3.0 is the sharpest dose that still asks *"does the axis move on the candidate side at deploy budget?"* rather than the already-answered *"is τ=2 bad?"* |
| `CELL_TAU8` | **8.0** | softer priors | The **HIGH end of the same interval**, and the direction T3's two rung-C-firing trials sat in (τ 5.42 / 5.94, both dead at fair transfer) — so if any residual signal exists on this axis, this is the side it would be on |

Both doses also have a **banked n=200 sibling** (`c5_s4_curve125_taup3` /
`taup8`) measured against the h800 rung, so this leg's numbers are comparable
rather than free-standing. ⚠️ The comparison is *indicative only*: different
opponent, different era, different n.

3.0 and 8.0 are near-symmetric about 5.0 **in log space** (`ln 3/5 = −0.51`,
`ln 8/5 = +0.47`), which matches the log-uniform prior T3 used on this knob.

---

## 5. ⭐⭐ THE BAR, AND WHAT THE FUNDED n CAN AND CANNOT DO

### 5.1 The primary

**M = the deck-paired mean margin, candidate − opponent, in points per deck**, on
each cell separately, within its own band. Elo/winrate are reported as secondary
colour and **decide nothing**.

### 5.2 The bar

**`BAR_M = +1.0 pts/deck`**, set at the effect size the decision cares about —
**never at 2·σ̂ of the instrument** (owner ruling 2026-08-30, "effect size sounds
right").

Derivation: the only decision downstream of a positive read is *adopting a new
production `tau_p`*, which means a champion change. The FPU adoption chain — the
most recent knob-adoption argument on this exact champion, budget and arbiter —
sat on the **+1.0 pts/deck class** (its realized point estimates were +1.02 /
+0.86 and were judged not to clear). A τ_p effect smaller than that would not
move a production knob that three independent prior investigations have already
read null (§1.2). So +1.0 is the bar, and it is **not** derived from this
instrument's σ.

### 5.3 ⛔ WHAT THE FUNDED n CANNOT DO — stated here, not discovered later

The instrument's realized scale on this exact shape is **se(M) ≈ 0.68 pts/deck at
400 decks** (`CELL_CPUCT10` realized SE 0.6511 at n=800 paired). With a one-sided
95% interval:

* **KILL** (`UB95 = M + 1.645·se < 1.0`) needs **M < −0.12**.
* **ADOPT** (`LB95 = M − 1.645·se > 1.0`) needs **M > +2.12**.

**The null's expected read distribution** (true M = 0, se = 0.68):

| branch | fires when | P under a true null |
|---|---|---|
| `T-BOUNDED` (kill) | M < −0.12 | **≈ 43%** |
| `T-UNRESOLVED` | −0.12 ≤ M ≤ +2.12 | **≈ 57%** |
| `T-EXPRESSES-AND-MOVES` | M > +2.12 | ≈ 0.1% |

And under a **true effect exactly at the bar** (M = +1.0), `T-EXPRESSES` fires
only **5%** of the time.

⭐ **So: at n=400 decks this leg can only afford the BOUNDING direction against a
+1.0 bar.** It is a screen that can *rule the axis out below the adoption-relevant
effect*, and it is **not** an instrument that can confirm one. That is stated as
a limitation of the funded shape, not smuggled in as a design.

**What would resolve it.** For the KILL branch to fire ≥90% of the time under a
true null you need `1.645·se < 1.0 − 1.282·se`, i.e. `se < 0.342`, i.e.
**≈ 1600 decks (3200 games) per cell** — about 4× the funded n, ≈ 24 h/cell on
the laptop, ≈ 48 h for the pair. ⛔ That is **not** funded here, and this document
does not propose it: buying it would need a *mechanism* argument, not more n
(`project_rodv3_fullbudget_flywheel`'s retirement is the standing lesson).

### 5.4 Why the leg is still worth its 12 hours

Because the deliverable is **§6's retirement**, which the *expressibility* of the
cell discharges, plus a one-sided bound on a previously unmeasurable surface. The
number is the by-product; the closed limb is the product.

---

## 6. Branch vocabulary and the read rule

Read **per cell**, after every gate in §7 passes on that cell.

| branch | fires when | what it means | what it authorizes |
|---|---|---|---|
| **`T-EXPRESSES-AND-MOVES`** | gates PASS and `LB95(M) > +1.0` | the candidate-side τ_p axis moves at the adoption-relevant effect at deploy budget | ⛔ **NOT a production change.** A genuine surprise against three prior nulls; it funds ONE confirmation on a FRESH band at the sizing in §5.3, and nothing else. A single screen never promotes (house rule). |
| **`T-BOUNDED`** | gates PASS and `UB95(M) < +1.0` | the axis is **bounded below the adoption-relevant effect** on the candidate side at deploy budget, at this dose | closes the limb *with* a bound; the dose is re-killed |
| **`T-UNRESOLVED`** | gates PASS, neither of the above | the cell resolved nothing about effect size | closes the limb *without* a bound. ⛔ **NOT a licence to buy more n** — see §5.3 |
| **`T-VOID`** | ANY gate FAILS | there is **no read at all** | the cell is void; its band retires **unread**; the limb stays open |

### 6.1 ⭐⭐ THE RETIREMENT RULE — pre-registered, before any number exists

**The audit limb RETIRES on any gated read: `T-EXPRESSES-AND-MOVES`,
`T-BOUNDED` or `T-UNRESOLVED`, on both cells.** What was open was *expressibility*
— "no candidate-side τ_p cell has ever been runnable against the fair champion" —
and that is discharged the moment two gated cells exist, whatever they say.

**Only `T-VOID` leaves it open.**

⛔ This is written down now precisely so that a `T-UNRESOLVED` pair cannot later
be re-read as "we still don't know, fund more." The thing we did not know was
whether the cell could be *expressed*. After this leg we will know that, and the
effect-size question will carry a stated, funded-shape-limited bound.

### 6.2 Reporting

Per cell: the branch, M, se(M), UB95, LB95, elo ± 1σ, winrate, `n_paired`, every
gate's verdict, and the resolved `config.cand_search`. Two `experiments/
results.csv` rows (one per cell) at close-out, tagged
`taup_audit_leg_CELL_TAU{3,8}_<branch>_n800paired_b<band>`, plus the six-touch
close-out checklist (results.csv → DECISIONS → status banner → CLAIM_REGISTRY →
STATUS → roadmap) and `docs/LEVER_INDEX.md` line 106 amended in place.

---

## 7. The gates — `leg_lib.py`, one implementation

⛔ Every gate FAILS CLOSED, and **`MISSING` is not `None`**: `cand_search.tau_p =
null` is the positive statement "the shared `--tau-p`", while an absent key means
the harness predates this leg and the cell is champion-vs-champion. No gate may
collapse the two.

| gate | what it reads |
|---|---|
| **`G-TAUP`** | four addresses that must agree pairwise: `config.cand_search.tau_p` == the dose (the REQUEST) · `config.champion.tau_p` == the dose (the candidate's RESOLVED config) · `config.cand_search.shared_tau_p` == 5.0 · **`config.opponent.champ_cfg.tau_p` == 5.0** (⭐⭐ the opponent — the proposition `--tau-p` fails) |
| `G-SINGLEVAR` | `cand_search.fpu_reduction` and `.c_puct` are both **present and null** — one live variable only |
| `G-BUDGET` | k16×1376=22016 and exact-k 2 marginalized on **both** seats, rust, `fixed_v1`, `paired`, 2 seatings/deck |
| `G-ARB` | the arbiter ARMED at the deployed dict on **both** seats (the opponent block is absent-when-unarmed by design, so ABSENT here is a FAIL) |
| `G-PROD` | (launcher) the frozen budget/arbiter/τ_p still equal `governance/PRODUCTION.yaml` at `champion.fair_deploy` / `champion.agent_knobs` |

⚠️ **No leaf hash moves on this knob**, so `cand_leaf_hash` *equals* the
opponent's on a live cell and a moved-hash check proves nothing. The resolved
manifest is the wiring gate — which is why the gate addresses were read off a
**real emitted manifest** and are asserted against the byte-untouched original in
`test_taup_leg.py::test_every_gate_address_exists_in_real_emitter_output`. Three
of the four obvious address guesses are wrong on this emitter.

---

## 8. Blindness, bands, and the launcher's refusals

`run_cells.sh` fails closed, before a deck is spent, on **all** of:

1. `TAUP_BITEXACT.json` missing, not `PASS`, or not over the **full frozen
   12-seed set** (a preview pass may not spend a band);
2. `WORKERS.conf`'s `BLIND_COMMIT` still `PENDING` (real cells);
3. the sibling `BAND_CLAIMED` file absent (real cells) — see
   `BAND_CLAIMED.placeholder`; **this agent claimed nothing**;
4. **the box cannot express the cell** — a live probe that drives the real
   argparse, builds both sides' configs, and reads `tau_p` back out of
   `SearchConfigRs`. A box on a stale bundle would otherwise produce a
   champion-vs-champion cell with a healthy wheel, a healthy leaf hash and a
   perfectly plausible dirname;
5. `G-PROD` disagreement with `PRODUCTION.yaml`.

A full-args process census runs before every real launch. The launcher
**self-detaches** (`setsid nohup nice -n 19`) and drops a `RUN_LIVE.json`
sentinel, which the freeze-latch hook reads.

### 8.1 The smoke

Per cell, on that cell's own throwaway offset, at **PRODUCTION knobs** — arbiter
armed both seats, dose on the candidate — with only the game count reduced (8).
It is then **adjudicated from its own emitted manifest** by
`adjudicate_smoke.py`, which **exits nonzero** on a missing dir, a missing
manifest, an unparseable manifest, **zero per-game records**, or any gate
failure. ⛔ The smoke emits **no outcome key** (a test asserts this); its 8 games
decide nothing and may never be pooled.

---

## 9. ⛔ NON-INFERENCE LIMITS

1. **The two cells are on DIFFERENT bands.** Comparing `CELL_TAU3` against
   `CELL_TAU8` is a **cross-band** contrast and is over-dispersed 1.8–2.2×
   (CL-068). ⛔ **Do not read "3.0 vs 8.0" as a measured direction on the axis**,
   and never pool the two cells into one estimate. The robust class is each
   cell's own **within-band deck-paired** contrast with its own opponent.
2. **A single screen never promotes.** `T-EXPRESSES-AND-MOVES` funds one
   confirmation on a fresh band; it does not move `PRODUCTION.yaml`.
3. **The bar can only be approached from below** at this n (§5.3). An
   `UNRESOLVED` pair is a statement about the funded shape, not about the axis.
4. **The banked `c5_s4_curve125_taup{3,8}` rows are not a baseline for this leg.**
   Different opponent (the h800 rung, where `--tau-p` is not a shared-flag
   defect), different era, n=200. Indicative only.
5. **This is not `TAU_PAIR_SPEC`** (§1.2). Nothing here may be pooled with, or
   reported as, that re-killed pair.
6. **W is throughput-only.** Games are bit-identical at any W and no gate here
   reads a clock. No timing statistic is a branch input.
7. **The golden gate is a code-path gate** at k2×96. No number in it is a
   strength measurement.
8. **A band that influences a decision retires from confirmatory use.** Both
   bands here will have.

---

## 10. Cost

| item | box | ETA |
|---|---|---|
| golden gate, full 12 seeds | any | ~4–5 min |
| smoke, per cell (8 games, production knobs) | laptop W=24 | ~12 min |
| `CELL_TAU3` (800 games) | laptop W=24 | **5.9–6.2 h** |
| `CELL_TAU8` (800 games) | laptop W=24 | **5.9–6.2 h** |
| **total, serial** | laptop | **≈ 12.5 h** |

⚠️ The ETA is a **bracket, not a point**: the 2026-08-31 arb-on laptop sweep
measured W ∈ {18, 22, 26, 28, 30} at this exact cell shape and **no W=24 point
exists**. W=24 is the owner's 2026-09-01 threads ruling, and it sits between the
measured W22 (129.0 g/h) and W26 (135.4 g/h); the realized steady state of
`fpu_h2h_r2`'s laptop chunks c1–c3 was 129.4 g/h. The house rule forbids
interpolating a new operating point out of two measured ones, so the bracket is
quoted. This resolves no bar either way.

---

## 11. Launch, when authorized

```bash
# 1. the FULL golden gate (the banked one is a 4-seed preview; DEVIATIONS D-2)
./measurement/taup_audit_leg_20260901/goldengate/run_gate.sh

# 2. per cell, ON THE LAPTOP, via the house pipe pattern (never inline ssh+cd)
ssh laptop-wsl 'bash -s' < measurement/taup_audit_leg_20260901/run_cells.sh -- \
    --cell CELL_TAU3 --smoke        # then read SMOKE_CELL_TAU3.json
ssh laptop-wsl 'bash -s' < measurement/taup_audit_leg_20260901/run_cells.sh -- \
    --cell CELL_TAU3                # self-detaches; logs/CELL_TAU3.log
# …then the same two for CELL_TAU8.
```

⛔ Preconditions, in order: merge the `eval_fair_puct.py` patch at a quiet window
→ sync the bundle to the laptop → re-run the full golden gate → claim the two
bands (`BAND_CLAIMED.placeholder`) → stamp `BLIND_COMMIT` in **both**
`BLIND_COMMIT.json` and `WORKERS.conf` → smoke each cell → launch.
