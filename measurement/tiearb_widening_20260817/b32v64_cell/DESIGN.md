# THE `B = 32` vs `B = 64` TIE-ARBITER LADDER GAME CELL — DESIGN (DRAFT)

> **STATUS: DRAFT FOR THE ORCHESTRATOR'S REVIEW. NOT YET A PREREGISTRATION.
> NOT COMMITTED BLIND ON `main`. NOTHING LAUNCHED, NO SMOKE RUN, NO GAME PLAYED.**
> The band **IS** claimed (§12.2) — that is the one state change this draft made, on the
> orchestrator's explicit instruction, and it is recorded rather than implied.
>
> **FUNDED.** Owner (Joshua), 2026-08-20, verbatim: *"local 30w. laptop 22w. n1500. put an
> agent on it."* — `W_LOCAL` 30, `W_LAPTOP` 22, **`n` = 1,500 DECKS × 2 seatings = 3,000
> games per cell**, 6,000 games total.
>
> **LICENSED BY TWO THINGS, both named.** (i) The `B-COSTKILL` branch's pre-registered
> follow-up (ii), verbatim from
> [`b64_cell/verdicts/READOUT_B64.md`](../b64_cell/verdicts/READOUT_B64.md): *"a **ladder
> question** — whether a rung between 16 and 64 is both affordable and captures most of the
> gain … ⚠️ which this cell **did not measure in game points** and which **no branch may
> infer from two points**."* (ii) The fresh owner funding above. ⛔ Neither licence is a
> result and this document does not become one by being committed.
>
> Written **before** any statistic of this cell exists. Every number in this file is either
> (a) read off a completed run's artifact on disk **with its path given**, or (b) derived
> from those by arithmetic **shown in full**. Nothing is guessed and **nothing is inherited
> un-rederived** — the R3.3 miss class is *supply/cost arithmetic copied forward without
> re-deriving it* ([`PREREG_FAILURE.md`](../PREREG_FAILURE.md) §2), and
> [§7](#7-supply-chain-and-cost--every-stage-re-derived-from-the-b64-cell-realized-artifacts)
> re-derives **every** stage from the `b64_cell`'s *own* realized artifacts rather than
> carrying that cell's committed projections forward.
>
> ⭐ **AMENDED PRE-BLIND, 2026-08-21, BY OWNER RULING:** `L-SATURATED` is a **ONE-SIDED
> NON-INFERIORITY** test (`D + 1.645·se_D ≤ 0.93`), not the drafted two-sided equivalence band.
> Owner-selected option label, verbatim: **"One-sided ±15 (Recommended)"**. The tolerance,
> `n`, the band, every gate and every other branch are UNCHANGED. Full ruling, with the
> owner's verbatim words and the recomputed power:
> [`RULINGS_PREBLIND.md`](RULINGS_PREBLIND.md) **RULING 1**.
>
> `governance/PRODUCTION.yaml` is untouched on every branch. No claim is minted by this
> file. Its mechanical companion is [`READ_RULE.md`](READ_RULE.md), which **must be
> committed in the same commit as this file** so git history proves the ordering.

---

## 0. The question, and what made it live

**The question, in one sentence:** *now that `B` = 64 is the DEPLOYED arbiter shape, what
does the deploy give up — in game points, on a fresh band, deck-paired — by dropping to the
half-price rung `B` = 32?*

⭐ **THE DIRECTION OF THIS CELL IS THE OPPOSITE OF THE `b64_cell`'s AND THAT MATTERS.** The
`b64_cell` asked *"does widening buy points?"* against a deployed `B` = 16. This cell asks
*"does NARROWING cost points?"* against a deployed `B` = 64. Both halves of the answer are
decision-relevant, and they are decision-relevant to **different** decisions:

| half | the decision it feeds |
|---|---|
| **(a) the cost of stepping DOWN** | whether to swap the deployed arbiter from `B` = 64 to `B` = 32 and bank the clock (≈**2.24×** the champion's per-move baseline instead of ≈**3.49×** — §4) |
| **(b) the SHAPE of the game-currency curve** | whether a `B` = 128 cell is worth funding at all, or whether the ladder has saturated |

### 0.1 What changed on 2026-08-20, and why the affordability machinery is GONE

[`b64_cell/OWNER_RULING_20260820.md`](../b64_cell/OWNER_RULING_20260820.md), owner verbatim
*"I'm buying b64"*:

> 1. **The N4 `rho_wall ≤ 1.20` bar is waived at `B = 64` for DESKTOP production play.**
> 2. **Deploy of the tie arbiter at `B = 64 / J = 4` into the desktop champion shape is
>    AUTHORIZED.**

Folded into `governance/PRODUCTION.yaml::deploy.tiearb` (commit `2f1c8cff`): `enabled: true`,
`B: 64`, `J: 4`, `mode: argmax`, `salt: tiearb2-deploy-v1`, `eps: 0.0`.

⇒ **THREE CONSEQUENCES, ALL STRUCTURAL, ALL STATED BEFORE THE RUN:**

1. ⛔ **There is NO affordability predicate in this pair.** The `b64_cell`'s `A` / `W` /
   `OWNER_WAIVER.md` machinery, its committed regex, and its whole `B-COSTKILL` branch
   existed **only** because the N4 bar stood un-waived above `B` = 16. The owner has since
   moved that bar in writing. **The bar is waived, so there is no affordability conjunct
   here** — `rho_wall(32)` = 1.2449 exceeding the *retired* 1.20 figure is a historical
   fact, not a gate. Cost is reported on **every** branch and is a branch input
   **NOWHERE** ([§4](#4-the-cost-facts-stated-before-the-run--and-cost-is-a-branch-input-nowhere),
   [READ_RULE](READ_RULE.md) §4.2). ⚠️ Naming this explicitly is deliberate: silently
   deleting a predicate that governed the sibling cell would be exactly the kind of quiet
   amendment this campaign has ruled against.
2. **`CELL_B64` is a fresh-band replicate of the INCUMBENT, not of a candidate.** The
   deployed shape is now on the *high* side of the contrast. That flips the burden: a
   swap-down needs positive evidence that `B` = 32 **does not cost more than the tolerance**,
   not evidence of superiority, which is why the primary branch set is a **ONE-SIDED
   NON-INFERIORITY test** and not a one-sided win test
   ([§6](#6-power--and-the-branch-set-this-n-can-and-cannot-reach)). ⭐ **The shape was RULED
   ONE-SIDED by the owner, pre-blind, on 2026-08-21** —
   [`RULINGS_PREBLIND.md`](RULINGS_PREBLIND.md) RULING 1; the draft's two-sided equivalence
   band refused the licence in the case where `B` = 32 turned out *better*, which was a defect
   of shape, not of tolerance.
3. **The phone is untouched and stays untouched.** `rho_phone` is a third currency, unsolved
   at every rung; the mobile profile plays the unmodified champion. No branch here says
   otherwise.

### 0.2 ⛔ What this cell may NOT infer — carried verbatim from the branch that licensed it

[`b64_cell/verdicts/READOUT_B64.md`](../b64_cell/verdicts/READOUT_B64.md), `B-COSTKILL`
clause (ii), verbatim:

> whether a rung between 16 and 64 is both affordable and captures most of the gain
> (`Δ(16→32)` = +0.0597 is 89% of `Δ(16→64)` **offline**) — ⚠️ which this cell **did not
> measure in game points** and which **no branch may infer from two points**.

⇒ the "89% offline" figure is the *reason this cell exists*, and it is **not** an input to
any branch. It is an **offline per-tied-ply oracle price on a selected 1,340-ply corpus**,
and the map from that currency to game points is precisely what the 3.9× translation caveat
([§5](#5-the-effect-we-are-trying-to-detect--and-the-39-caveat-binds-both-ways)) says is
unestablished.

### 0.3 The Stage-2 anti-gaming clause, and why it does not bite here either

Stage 2's ruling (*"`B` stays 16 … it may not be expanded beyond 16 either"*) was scoped to
Stage 2's own cell, its stated purpose was **anti-gaming** — *"permission to spend clock,
never licence to reshape the arbiter to look cheaper"* — and the `b64_cell` already
established (§0.4 there) that it is not a programme-wide prohibition. ⚠️ **But note that
THIS cell moves `B` in the direction that DOES make the cost look cheaper, which is the
direction the anti-gaming clause was pointed at.** So it is stated plainly:

⭐ **`B` = 32 is not proposed as a way to duck a cost bar. There is no cost bar left to
duck** (§0.1). The rung is measured because the owner funded a measurement of it, and the
read-rule **licenses a decision for the owner and edits nothing** ([READ_RULE](READ_RULE.md)
§5). A swap-down that the measurement does not support cannot be taken on this record, and
the branch that would be tempting to over-read (`L-SATURATED`) is the one with the **fully
declared, pre-run reachability and power figures** in
[§6.4](#64--the-reachable-branch-set-and-every-branchs-reachability-computed-before-game-1).

---

## 1. The shape of the contrast

### 1.1 ⚠️ THE HARNESS STILL CANNOT PUT AN ARBITER ON THE OPPONENT — re-verified, not assumed

`scripts/classical_search/eval_fair_puct.py` exposes `--cand-tiearb-{enabled,b,j,mode,salt,eps}`
and threads them to the **candidate only** (the flag's own help says *"CANDIDATE side only"*).
There is still **no `--opp-tiearb-*`.** ⇒ a direct head-to-head `champion+arb(64)` vs
`champion+arb(32)` **cannot be launched against the harness as it stands**, exactly as the
`b64_cell` found (its §1.1) and the JCZ cell before it.

**The design of record is therefore the same known shape: two cells against the unmodified
champion, DIFFERENCED.** ⭐ The `b64_cell`'s review-ruled ground for that choice stands
unchanged and is not re-litigated here: a new opponent-side instrument is a surface where a
bug is invisible to every `G-J1`-class candidate gate this programme has, and *this
programme's two most expensive recent losses were DESIGN-SHAPE failures, not power
failures*. **Take the known shape.**

### 1.2 The two cells

| cell | candidate | opponent | arbiter |
|---|---|---|---|
| **`CELL_B32`** | champion + arbiter, **`B` = 32** | champion, **unmodified** | `Ā × 32` playouts per tied ply, **argmax** of the world-mean |
| **`CELL_B64`** | champion + arbiter, **`B` = 64** | champion, **unmodified** | `Ā × 64` playouts per tied ply, **argmax** of the world-mean |

Both cells run on the **same fresh band `140000000000` and the same 1,500 decks**,
deck-paired (same deck played twice, seats swapped). The **PRIMARY** statistic is

```
D = M_B64 − M_B32 ,  deck-paired over the decks completed in BOTH cells
```

with `z_D = D / se(D)`, `se(D)` computed the same way as `eval_fair_puct._paired_z`.

**This is the `b64_cell`'s own construction with `NARROW` re-parameterised from `B` = 16 to
`B` = 32.** No new statistic and no new instrument is invented here — **only the low cell's
`B`.** The two invocations differ in **exactly one argument**, `--cand-tiearb-b`.

**Why `CELL_B64` must be re-run rather than read off the `b64_cell`.** The `b64_cell`'s
`WIDE` is the same configuration on band `139000000000`, and **that band is RETIRED from
confirmatory use** (`governance/BAND_REGISTRY.csv`, `decision_influenced=yes`). CLAUDE.md's
cross-band humility rule prices cross-band contrasts at **1.8–2.2× over-dispersion in both
statistics** and says *"never pool across bands and quote the pool as an estimate"*. A
`CELL_B32`-on-140e9 vs `WIDE`-on-139e9 contrast is exactly the forbidden class.
**Within-band deck-paired is the robust class and it is the only one used here** — which
costs a full second cell, and that cost is in §7.

### 1.3 ⭐ The CRN is NESTED — and at THIS rung the nesting is TIGHTER than at the last one

`rust/carc/carc-core/src/tiearb.rs::arbitrate` derives each world's seed as

```
world_seed(j)   = seed_i64([salt, state_digest, ply, j])          for j in 0..B
playout_seed(j) = seed_i64([salt, state_digest, ply, j, "playout"])
```

`j` runs `0..B` and **the seed is a pure function of `j`, never of `B`.** ⇒ at the same
salt, the same position and the same ply, **`B` = 64's worlds `0..31` are byte-identical to
`B` = 32's entire world set.** `build_arms` (seeded `[…,"cap"]`) and the `Random`-mode
selection stream (`[…,"select"]`) likewise do not depend on `B`.

Four consequences, all first-class and all carried from the `b64_cell` §1.3 **with their
magnitudes re-derived at this rung**:

1. **`CELL_B64` is a strict refinement of `CELL_B32`, not a different experiment.** It
   differs only where the extra **32** worlds move the argmax. Where they do not, the two
   candidates play the **identical move**, and — both facing the identical champion from the
   identical deck — the **entire game is identical**.
2. ⚠️ **A large identical fraction is a POWER LOSS, not a power win, and this design says so
   before the run.** If a fraction `f₀` of common decks yield `D_i` exactly 0, then
   `mean(D) = (1−f₀)·E[D | differ]` and `sd(D) ≈ √(1−f₀)·sd_differ`, so **`z_D ∝ √(1−f₀)`**.
   Hence `G-DIVERGE` ([READ_RULE](READ_RULE.md) §3), whose floor and **expected value** are
   derived at THIS rung in §8.2 — not carried from the last one.
3. **It plausibly raises the cross-cell deck correlation `ρ`.** The `b64_cell` realized
   `ρ` = **+0.1237** at the 16↔64 rung (`READOUT_B64.json::D_block`); a tighter nesting
   plausibly gives more. ⛔ **It is NOT banked.** §6 sizes at the **committed** `se(D)` the
   orchestrator pinned, which is the `ρ`-agnostic figure. The realized `ρ` is reported.
4. **It gives a free structural witness.** `G-NEST` requires a pinned test proving the
   world-set nesting **at 32 ⊂ 64** at HEAD before game 1. Emitter and address: §12.1.

---

## 2. The two cells' knobs — every knob but `B` is the DEPLOYED shape

| knob | `CELL_B32` | `CELL_B64` | source |
|---|---|---|---|
| `enabled` | true | true | `--cand-tiearb-enabled` |
| **`B`** | **32** | **64** | **the only difference** |
| `J` | 4 | 4 | deployed (`PRODUCTION.yaml`); rung3_r5 read `X-INCONCLUSIVE`, no licence to widen |
| `mode` | `argmax` | `argmax` | deployed |
| `salt` | `tiearb2-deploy-v1` | `tiearb2-deploy-v1` | deployed; *"a different salt is a different experiment"* |
| `eps` | 0.0 | 0.0 | deployed — exact f64 equality, **not** a tolerance |
| trigger | TILES phase, own seat, `n_legal ≥ 2`, ≥2 actions sharing the top **outer chain value** at exact f64 equality | identical | deployed |
| champion | `cand_leaf_hash` `a36d2e15a3b3d71d`, k8×1376 = 11,008, exact-K 2, `c_puct` 1.5, `tau_p` 5.0, `final_select` visits, `leaf_quantize` float | identical | `governance/PRODUCTION.yaml` |
| rules | `fixed_v1` | `fixed_v1` | as the `b64_cell` |
| backend | rust, **both sides** | rust, both sides | as the `b64_cell` |
| opponent | `--opponent fair-champion`, **unmodified** | identical | §1.1 |

`--cand-tiearb-b` is `type=int` with **no `choices` restriction**, and the rust arbiter loops
`for j in 0..b` with no cap ⇒ **`B` = 32 requires no code change.** ⚠️ It is nevertheless
**unexercised at 32 in a game anywhere** — `B` = 32 has been priced only offline — so
`G-J13`'s two-sided positive control is required **at both `B` values, per host, before that
host's game 1**.

### 2.1 The arbiter fails soft — carried unchanged, with its exposure re-derived

A `tier1-greedy` continuation can hit the encoder's window refusal deep inside a world. The
arbiter does not propagate: it falls back to the champion's own `pooled_q_argmax` pick **at
ply granularity** and counts the event. Carried verbatim from Stage 2 §0.E.1 including its
post-hoc correction:

> The arbiter is **deterministic given the position**, so the two cells fail **identically
> wherever they are in the same position**. Once they diverge on a pick they are on
> **different boards** and can therefore fail at **different rates**. Symmetry is an
> empirical near-fact to be **measured**, never an entitlement.

⚠️ **The asymmetry is HALF what it was in the `b64_cell`, and in the same direction.**
`CELL_B64` runs **2×** the playouts per fired ply of `CELL_B32` (not 4× as `WIDE` did over
`NARROW`), so it carries ~2× the exposure to the failure class per ply — directional, and it
favours `CELL_B32`. Realized priors on **different** runs: the `b64_cell` realized
`n_failed` **0/1,500 in BOTH cells** (`summary.json::n_failed`, read off
`/mnt/c/carc-shared/tiearb_widening_20260817_b64_cell/b64_*/summary.json`), and
`tiearb_partial_argmax_total` was clean. It is bounded by `G-FAILED` ([§8](#8-the-failed-record-bound-and-the-divergence-floor--both-authored-before-any-data-exists))
and reported on every branch.

---

## 3. Existence-time markers — the R5 discipline, carried

[`rung3_r5/DESIGN.md`](../rung3_r5/DESIGN.md) §R5-6.1, verbatim:

> **Every address in this prereg carries an existence-time marker … Each acceptance pass
> audits exactly the markers that can exist at its point in the sequence — statically against
> a fixture otherwise. No pass may demand an address its own position in the sequence makes
> impossible, and no address may be audited at neither pass.**

| marker | exists from | audited statically at | audited live at |
|---|---|---|---|
| `[pre-run]` | the blind commit / before game 1 | the pre-commit pass | the pre-launch pass |
| `[post-smoke]` | the smoke completes | the pre-commit pass, against a **fixture** | the post-smoke pass |
| `[post-cells]` | both cells complete | the pre-commit pass, against a **fixture** | the read-out |

**The fixture set is not hand-maintained.** For every `[post-smoke]` and `[post-cells]`
address the fixture is **the `b64_cell`'s own completed artifact of the same name**
(`/mnt/c/carc-shared/tiearb_widening_20260817_b64_cell/…/{summary,manifest,seed*}.json`,
`…/smoke/SMOKE.json`, the `b64_cell`'s four named `verdicts/PREFLIGHT_{Doctor,laptop-wsl}_FIRST_B{64,16}.json`
(⚠️ **enumerated, not globbed** — the same discipline [READ_RULE](READ_RULE.md) §2.2 imposes on
this cell's own gate inputs; a fixture glob would sweep that cell's `_<epoch>` rotations in and
exercise the known-good partition against artifacts from two wheel epochs),
`b64_cell/GATE_NEST.json`),
and a **completeness assertion over the marker list** — not over a fixture list — asserts
every marked address is covered. An address carrying **no** marker is a **DRAFTING DEFECT**
to be fixed before the blind commit, never adjudicated at read time.

Load-bearing assignments (full enumeration in [`READ_RULE.md`](READ_RULE.md) §2/§3):

- `[pre-run]` — `WORKERS.conf`, `BAND_CLAIM.json`, the **four named, un-timestamped**
  `PREFLIGHT_${HOST}_FIRST_B{64,32}.json` (both hosts, both `B`;
  [READ_RULE](READ_RULE.md) **§2.2** — `_<epoch>` rotations are superseded artifacts, report-only,
  never gate inputs), `GATE_NEST.json`, the blind commit hash.
- `[post-smoke]` — `SMOKE.json` (all cost keys, plus `production_knobs` and `smoke_utc`, §9.2),
  and **`SMOKE_HALT.json`** `{halt, realized, bar}` — the HALT decision record (§9.3.1).
- `[post-cells]` — `summary.json::{paired_mean_margin, paired_z, elo, elo_sig_1sigma,
  winrate, winrate_z, tiearb_*, champ_prefix_ms_per_move, rung_ms_per_move, n_failed,
  failed_cells}`, `manifest.json::{cand_tiearb, config.cand_leaf_hash,
  config.band_seed_start, carc_rs_build}`, `seed*.json::elapsed_s`, and every quantity in
  the `D` block.

⚠️ **`manifest.json` resolution is a TWO-LEVEL lookup, and Stage 2 lost a whole adjudication
pass to it** (`G-J1`/`G-BAND` read `null` at the top level while the witnesses sat correct
under `config.`). Every manifest address here is specified as **"top level, else under
`config.`, and the read-out prints which was found"**; the gate still fails closed if the
value is absent under both.

---

## 4. The cost facts, stated before the run — and cost is a branch input NOWHERE

### 4.1 `rho_wall`, and the bar that no longer exists

| rung | `rho_wall` (sequential amortized arbiter overhead) | total per-move wall vs the champion baseline | `rho_phone` |
|---|---|---|---|
| `B` = 16 | **0.6224** (Phase A, MEASURED) | 1.62× | 5.52 / 5.98 |
| **`B` = 32** | **1.2449** (×2, exact linearity) | **2.2449×** | 11.04 / 11.95 |
| **`B` = 64** (DEPLOYED) | **2.4897** (×4, exact linearity) | **3.4897×** | 22.08 / 23.90 |

⚠️ **The old house N4 bar of 1.20 is RETIRED at `B` = 64 by
[`OWNER_RULING_20260820.md`](../b64_cell/OWNER_RULING_20260820.md) and is printed here as
history, not as a bar.** ⛔ **There is no affordability conjunct anywhere in this pair.**

At `PRODUCTION.yaml`'s stated champion baseline of **~1.8 s/move**:

```
B = 64 (deployed)   ~1.8 x 3.4897  =  ~6.28 s/move
B = 32 (candidate)  ~1.8 x 2.2449  =  ~4.04 s/move
=> the swap-down banks  ~2.24 s/move  =  -35.7% of the per-move wall
```

⭐ **THAT −35.7% IS THE PRIZE THIS CELL IS PRICING**, and the price is whatever `D` turns out
to be, glossed at ~16.1 elo per pt/game (§6.2). It is stated here so that a reader knows what
the tolerance was bought for.

⚠️ **`rho_phone` is a THIRD currency and is NOT SOLVED at any rung.** The two committed
figures for `B` = 16 disagree (`PLAN_B_gt_16.md` 5.976 vs Phase A / Stage 2's 5.520), so both
×2 and ×4 products are printed and **neither is adjudicated**. The phone plays the unmodified
champion (`PRODUCTION.yaml::deploy.tiearb`, *"Mobile stays OFF"*) and **no branch here changes
that**.

### 4.2 In-cell `ms_ratio` — projected, printed, graded nowhere

⚠️ **THE FIELD-NAME TRAP, CARRIED VERBATIM:** **`champ_prefix_ms_per_move` IS THE CANDIDATE
SIDE** in `eval_fair_puct.py` (live lines 2361/2371/2389 — the opposite of
`eval_puct_priors`). **A read-out that swaps them inverts the cost verdict.**

Projected from the `b64_cell`'s two realized points, by solving the two-equation
decomposition (arithmetic in §7.3):

| cell | committed prediction | grounds |
|---|---|---|
| `CELL_B64` | **6.608** | `b64_cell` WIDE, **MEASURED** (`summary.json::champ_prefix_ms_per_move` 11,651.2766 / `rung_ms_per_move` 1,763.1966) |
| `CELL_B32` | **≈ 3.74** | §7.3's decomposition; [`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §5's independent projection is **≈3.75** — an agreement to **0.3%** |

⛔ **`ms_ratio` is NOT a branch input anywhere.** It is printed on every branch beside its
prediction, because a wrong cost model must stay visible even where no bar is enforced
(Stage 2 §0.G's discipline, and the reason that miss was ever found).

⚠️ **Neither candidate's SEARCH BUDGET moves.** Both run the identical champion at k8×1376
with identical sims, and the arbiter fires **after** the search, at the root, on an
already-resolved tie ⇒ **the extra cost buys no extra search.** It is a wall-clock asymmetry
and is disclosed as one on every branch, never claimed away.

---

## 5. The effect we are trying to detect — and the 3.9× caveat binds BOTH ways

### 5.1 The caveat, carried verbatim and in full

[`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §5:

> ⚠️ **The offline→game translation factor is not established.** Stage 1b's +0.1441
> pts/tied ply predicts +0.79 pts/game (`× phi 17.57 / non_additivity 3.2`); Phase B realized
> **+3.07** — a **3.9× under-prediction.**

[`docs/LEVER_INDEX.md`](../../../docs/LEVER_INDEX.md) §6, on the direction:

> CAMPAIGN ruling 5 binds **in BOTH directions**: Stage 1b's offline read **under-predicted**
> the Phase B game cell **3.9×** … so the offline→game map is unestablished and
> **+0.0670 × 3.9 is not a projection either**.

⭐ **Restated so no read-out can soften it: the 3.9× is a MEASURED MISS of an unvalidated map,
in one direction, at n = 1. It licenses a WIDTH, not a CENTRE.** This design uses it to set a
**bracket** and refuses to use it as a multiplier.

⚠️ **AND THE `b64_cell` HAS NOW ADDED A SECOND, OPPOSITE-SIGNED DATUM TO THE SAME MAP.** Its
§5.2 bracket for `Δ(16→64)` was `[+0.368, +1.435]` and it realized **+1.7167** — i.e. the map
**under-predicted again**, this time by **1.20×** against the bracket TOP and **4.66×**
against the bracket floor. ⇒ **the map is now known to have missed low twice, at n = 2, in the
same direction.** ⛔ That is *still* not a licence to multiply: two points on an unvalidated
map do not calibrate it, and applying a "1.2× to 3.9× under-prediction correction" would be
exactly the centre-taking the caveat forbids. It is recorded because a bracket that has been
beaten twice on the high side is a bracket a reader should distrust **upward**, and this cell's
`L-SATURATED` branch is the one that would be embarrassed by that.

### 5.2 The bracket, derived at THIS rung

```
arb(32)                             = 0.1942   pts/tied ply    MEASURED (shared_run_r4, E=64, J=4)
arb(64)                             = 0.2015   pts/tied ply    MEASURED (ibid.)
Delta(32->64)                       = +0.0073  pts/tied ply    DERIVED
phi (committed, this cell, §7.2)    = 17.481   fired tied tile plies/game
NON_ADDITIVITY                      = 3.2      (n = 1, +-1.6x bracket -- NOT a point)

naive floor    = 0.0073 x 17.481 / 3.2   = +0.0399  pts/game
realized-ratio = 0.0399 x 3.9            = +0.1555  pts/game
```

⇒ **the offline-implied bracket is `[+0.040, +0.156]` pts/game** — glossed at ~16.1 elo per
pt, **`[+0.6, +2.5]` elo**. ⛔ **Neither endpoint is a projection.** The offline ratio
`arb64/arb32` = 0.2015 / 0.1942 = **1.038** is printed as a *description of the offline
ladder* and **MUST NOT** be presented as a projection of the game effect.

⭐ **THE SINGLE MOST DECISION-RELEVANT SENTENCE IN THIS DOCUMENT, and it is written before
game 1:** the ENTIRE offline-implied bracket `[+0.040, +0.156]` lies **inside** the owner's
±0.93 pts/game (±15 elo) tolerance. ⇒ **if the offline ladder is even roughly right about the
32→64 rung, the true answer is "`B` = 32 does not cost 15 elo" — and the question this cell can
actually settle is not "is `B` = 32 as good" but "can `n` = 1,500 decks PROVE it".**
[§6.4](#64--the-reachable-branch-set-and-every-branchs-reachability-computed-before-game-1)
answers that with numbers, and the answer is uncomfortable.

---

## 6. Power — and the branch set this `n` can and cannot reach

### 6.1 The dispersion, PINNED by the orchestrator and re-derived here

The orchestrator pinned the committed dispersion. It is re-derived rather than accepted:

```
b64_cell committed se(D) at 750 decks   = 0.7133                      (its DESIGN §6.2)
  => this cell, 1500 decks:  0.7133 x sqrt(750/1500) = 0.7133 x 0.70711 = 0.50438
COMMITTED se(D) = 0.5044 pts/game            <-- THE SIZING CONSTANT, and the only one that binds

b64_cell REALIZED se_D at 750 decks     = 0.6463                      (READOUT_B64.json::D_block)
  => this cell, 1500 decks:  0.6463 x 0.70711 = 0.45702
realized-dispersion PROJECTION = 0.4570 pts/game    <-- NON-BINDING SANITY LINE, printed, never used to size
```

⛔ **`n` is fixed at the COMMITTED figure and is NOT revised by the smoke, by the realized
`ρ`, or by anything else.** Revising `n` from data correlated with the effect is the exact
pattern the blind-ordering discipline exists to prevent. The smoke may **halt** the run on cost
([§9](#9-the-pre-registered-benchsmoke-step)); it may **never resize** it.

```
2-sigma conviction floor, committed      = 2 x 0.5044 = +1.0088 pts/game   (= +16.3 elo)
2-sigma floor at the realized projection = 2 x 0.4570 = +0.9140 pts/game   (= +14.7 elo)
```

### 6.2 The elo↔margin gloss — COMMITTED, non-binding, description only

```
b64_cell realized:  WIDE +63.9457 elo  -  NARROW +36.2644 elo  =  +27.6813 elo
                    over D = +1.7167 pts/game
=>  16.1247 elo per pt/game       <-- the COMMITTED GLOSS
```

⛔ **The gloss adjudicates nothing.** It is a one-band, one-cell empirical conversion between
two statistics of the same run; elo is a nonlinear function of win-rate and the mapping is not
a constant of nature. It exists so the owner's tolerance can be *stated* in the currency he
stated it in. **Every branch condition is written in pts/game**, never in elo.

```
owner tolerance:  +-15 elo  ->  15 / 16.1247  =  +-0.9302  ->  COMMITTED EQUIVALENCE MARGIN +-0.93 pts/game
```

Provenance of the tolerance, stated so it is not mistaken for a derived quantity: the
orchestrator offered *"If it's ~15, fund n=1,500"* and the owner funded n = 1,500. **The
margin is a preference, not a measurement.**

### 6.3 What `n` buys

| n decks/cell | games/cell | `se(D)` committed | 2σ floor | fire window `D̂ ≤` | ⭐ one-sided power at true `D`=0 (EFFECTIVE) | worker-h | 2-box wall |
|---|---|---|---|---|---|---|---|
| 750 | 1,500 | 0.7133 | +1.427 | −0.244 (**UNREACHABLE**) | 0.000 | 628.1 | 17.7 h |
| 1,000 | 2,000 | 0.6178 | +1.236 | +0.014 | 0.486 | 837.5 | 23.6 h |
| ⭐ **1,500** | **3,000** | **0.5044** | **+1.009** | **+0.100** | **0.556** | **1,256.2** | **35.3 h** |
| 2,000 | 4,000 | 0.4368 | +0.874 | +0.212 | 0.663 | 1,674.9 | 47.1 h |
| 2,728 | 5,456 | 0.3740 | +0.748 | +0.315 | 0.777 | 2,284.7 | 64.2 h |

*(fire window = `0.93 − 1.645·se(D)`; **EFFECTIVE** one-sided power = `Φ(window/se) − Φ(−2)` at
a true `D` = 0 — the `Φ(−2)` subtracts the mass `L-REVERSED` takes first by branch order
([READ_RULE](READ_RULE.md) §4.4). ⭐ Under the drafted two-sided shape the same rows read
0.000 / 0.018 / **0.158** / 0.371 / 0.596. worker-h and wall from [§7](#7-supply-chain-and-cost--every-stage-re-derived-from-the-b64-cell-realized-artifacts),
scaling linearly in `n`.)*

**COMMITTED: `n` = 1,500 deck-paired DECKS per cell = 3,000 games per cell = 6,000 games
total.** ⚠️ **`n` was set by the OWNER, not derived from a power target**, and this table is
here so that fact is legible rather than dressed up as an optimisation. ⭐ **Note the top
row: at the `b64_cell`'s own `n` this cell's non-inferiority branch would have been
ARITHMETICALLY UNREACHABLE** (the fire window is negative — `1.645 × 0.7133 = 1.173 > 0.93` —
and `L-REVERSED` owns everything below `−1.427`). The owner's
`n1500` is what makes the branch exist at all.

### 6.4 ⭐ THE REACHABLE BRANCH SET, and every branch's reachability computed BEFORE game 1

**The Stage-2 `G-N` lesson, applied prospectively: an unreachable branch must be visible
BEFORE the run, never discovered in the read-out.** All figures at the **committed**
`se(D)` = 0.5044, with the realized-projection figure beside it.

| branch | fires when | reachable? | window / probability |
|---|---|---|---|
| `U-UNREADABLE` | any §3 gate fails | **REACHABLE** | by construction |
| `L-REVERSED` | `z_D ≤ −2.0` | **REACHABLE** | `D ≤ −1.0088`; **25.3× the offline bracket top, in the wrong sign** — a priori very unlikely |
| `L-RISING` | `z_D ≥ +2.0` | **REACHABLE** | `D ≥ +1.0088`; **25.3× the offline bracket top** — a priori very unlikely |
| `L-SATURATED` | ⭐ `UB95(D) = D + 1.645·se_D ≤ +0.93` (**ONE-SIDED**, RULING 1) | **REACHABLE** | fires on `D̂ ≤ 0.930 − 1.645×0.5044 =` **`+0.1003`** (realized-proj **+0.1782**); **unbounded below by the predicate**, bounded below at `−1.0088` by `L-REVERSED`'s precedence ⇒ EFFECTIVE region `(−1.0088, +0.1003]` |
| `L-AMBIGUOUS` | everything else | **REACHABLE — reachable ONLY FROM THE HIGH SIDE** | `D̂ > +0.1003` **and** `z_D < +2.0` |

⛔⛔ **THE POWER STATEMENT THIS DESIGN REFUSES TO BURY.** At the committed dispersion:

⭐ **RECOMPUTED FOR THE ONE-SIDED SHAPE** ([`RULINGS_PREBLIND.md`](RULINGS_PREBLIND.md)
RULING 1). `raw` is the one-sided test's own probability; **`EFFECTIVE` subtracts the mass
`L-REVERSED` takes first by branch order, and EFFECTIVE is the number that governs.**

```
                                      COMMITTED se_D = 0.5044        REALIZED-PROJ se_D = 0.4570
                                      raw     L-REV    EFFECTIVE     raw     L-REV    EFFECTIVE
true D = 0        (the rungs equal)   0.5788  0.0228   0.5560        0.6517  0.0228   0.6290
true D = +0.0399  (bracket FLOOR)     0.5476  0.0188   0.5288        0.6189  0.0184   0.6005
true D = +0.1555  (bracket TOP)       0.4564  0.0105   0.4459        0.5198  0.0096   0.5102

   [the DRAFTED two-sided shape, for comparison: true D=0 -> 0.158 / 0.304 ;
                                                 true D=+0.1555 -> 0.150 / 0.287]

n for 80% RAW one-sided power at a true D = 0   (se_D <= 0.93/(1.645+0.8416) = 0.37400):
    committed law  0.7133*sqrt(750/n) <= 0.37400  =>  n >= 2,728 decks/cell (5,456 games)
    realized law   0.6463*sqrt(750/n) <= 0.37400  =>  n >= 2,240 decks/cell (4,480 games)
    (EFFECTIVE power at that n is ~0.777 -- L-REVERSED still takes ~2.3% of the lower tail)
```

⇒ **if `B` = 32 is EXACTLY as good as `B` = 64, this cell has a ~56% chance (~63% at the
realized dispersion) of being able to SAY so — up from ~16% (~30%) under the drafted two-sided
shape, at the SAME tolerance, the SAME `n`, and no extra spend.** ⚠️ **It is still not a
well-powered test:** ~44% of the equal-rungs world, and ~55% of the bracket-top world, still
reads `L-AMBIGUOUS`. **This is a declared property of the funded design, not a failure of it**,
and it is written here, before game 1, so that an `L-AMBIGUOUS` read-out is understood as the
expected outcome of an under-powered non-inferiority test rather than as evidence of a cost.

⭐ **AND THE KNIFE-EDGE — UNCHANGED BY THE RULING, AND HERE IS WHY.** For the offline-implied
bracket TOP (+0.1555), **as a point estimate**, to fire `L-SATURATED` you need
`se(D) ≤ (0.93 − 0.1555)/1.645 = 0.4708`:

```
committed law   =>  n >= 1,722 decks/cell   (n = 1,500 MISSES it)
realized law    =>  n >= 1,413 decks/cell   (n = 1,500 CLEARS it)
```

*(Both are the same inequality solved and rounded to the deck: raw 1721.45 and 1413.25.)*

⚠️ **These are IDENTICAL to the drafted two-sided figures, and that is arithmetic, not an
oversight: for a POSITIVE point estimate `|D| = D`, so the two shapes coincide exactly on the
upper edge.** What RULING 1 changed is the **probability of landing in the window** (0.150 →
0.446 at the bracket top, committed law), not the window's upper edge.

⇒ **whether an offline-bracket-sized true effect can convict as non-inferior depends entirely on
whether the realized dispersion lands at the committed 0.7133-law or the `b64_cell`'s realized
0.6463-law.** The `b64_cell` beat its own committed dispersion by 9.4%; this cell needs **9.4%
or better again**. ⛔ **That is NOT a reason to resize and it is NOT a hedge** — it is the one
sentence that tells the reader in advance which side of the line a null will land on, and
`L-AMBIGUOUS` carries a mandatory power print for exactly this reason.

### 6.5 ⚠️ What this cell CANNOT do — stated before it runs

- **It cannot exclude a small real cost.** A `D̂ ≤ +0.10` read bounds the cost at **+0.93** and
  says **nothing** about +0.20. Any narrative that turns `L-SATURATED` into "`B` = 32 is exactly
  as good" is over-reading it; the branch text says `+0.93`, the verdict is a **one-sided upper
  bound on the cost**, and the read-out prints the realized `UB95(D)`.
- ⭐ **It cannot convict that `B` = 32 is BETTER except through `L-REVERSED`.** Under RULING 1's
  one-sided predicate a *mildly*-negative `D` fires `L-SATURATED`, whose claim is only *"`B` = 32
  does not cost 15 elo"*. **Claiming superiority requires `z_D ≤ −2.0`**, and `L-SATURATED`
  carries a mandatory rider forbidding the stronger reading ([READ_RULE](READ_RULE.md) §4.1
  branch 4, third rider).
- **It cannot resolve the ladder's SHAPE beyond the rung it measures.** Two points in game
  points cannot separate "log-linear", "saturating-exp" and "√B-noise"
  ([`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §1 fits all five). ⭐ **What it CAN do is gate
  `B` = 128**: `L-SATURATED` at 32↔64 kills it (a rung that adds nothing at 64 adds nothing at
  128); `L-RISING` licenses a *prereg* for it, funded separately. `L-AMBIGUOUS` leaves it
  unfunded by default. **No branch may name `B` = 32 or `B` = 64 "the optimum".**
- **It cannot license an on-device deploy** (§4.1 — `rho_phone` unsolved, third currency).
- **It cannot re-adjudicate the `b64_cell`.** That cell's verdict of record is `B-COSTKILL`,
  its read-rule is spent, and its band 139e9 is retired. **No comparison against its numbers is
  a branch input anywhere here.**

---

## 7. Supply chain and cost — every stage RE-DERIVED from the b64 cell realized artifacts

**The R3.3 miss class is supply arithmetic that was inherited rather than re-derived.** The
`b64_cell` projected its cost from Stage 2's `ARB` cell. This cell does **not** inherit those
projections: it re-derives from the `b64_cell`'s **realized** artifacts, which are a strictly
closer population (same two boxes, same `W_LOCAL` 30 + `W_LAPTOP` 22, same `--shared-claim`
arrangement, same rules profile, same champion, and — for `CELL_B64` — the *identical*
configuration).

### 7.1 The measured cost primitives

All read off `/mnt/c/carc-shared/tiearb_widening_20260817_b64_cell/b64_*/`, 1,500 games each:

```
                                       NARROW (B=16)        WIDE (B=64)
sum over seed*.json of elapsed_s        610,121.0 s        1,392,037.7 s      MEASURED
  / 1500 => worker-s per game            406.7473            928.0251         DERIVED (1 step)
summary.json::tiearb_secs_per_game       164.0068            679.8027         MEASURED
summary.json::tiearb_secs_total          246,010.154       1,019,704.050      MEASURED
summary.json::tiearb_phi                  17.5533             17.4087         MEASURED
summary.json::tiearb_fired_plies_total    26,330              26,113          MEASURED
summary.json::tiearb_playouts_total     1,374,528           5,464,192         MEASURED
summary.json::champ_prefix_ms_per_move  4,128.5725         11,651.2766        MEASURED (CANDIDATE side!)
summary.json::rung_ms_per_move          1,730.3489          1,763.1966        MEASURED (opponent side)
summary.json::n_failed                        0                   0           MEASURED
```

### 7.2 The derived chain — each line one arithmetic step from the line above

```
playouts per fired ply   B=16 = 1,374,528 / 26,330  =  52.2039        DERIVED
                         B=64 = 5,464,192 / 26,113  = 209.2518        DERIVED
   ratio = 4.00838  (the EXACT x4 expected from `for j in 0..b`; realized +0.21%,
                     which is arm-count drift between two different game populations,
                     NOT a cost effect)
A_bar (arms/fired ply)   B=16 = 52.2039 / 16        =   3.26274       DERIVED
                         B=64 = 209.2518 / 64       =   3.26956       DERIVED
   => A_bar COMMITTED = 3.26615 (mean; the two agree to 0.21%)

c_incell (worker-s per playout)
                         B=16 = 246,010.154 / 1,374,528  = 0.1789781  DERIVED
                         B=64 = 1,019,704.050 / 5,464,192 = 0.1866159 DERIVED
   ratio over TWO doublings = 1.042674
   => per-doubling cost inflation = sqrt(1.042674) = 1.021114        DERIVED
   => c_incell(B=32) = 0.1789781 x 1.021114 = 0.1827569              DERIVED
   ⭐ THIS IS A REAL, MEASURED, +2.11%-PER-DOUBLING SUPER-LINEARITY in the per-playout
      cost (cache/scratch pressure at wider world sets). The `b64_cell` could not see it
      -- it had one point. Ignoring it would UNDER-price CELL_B32 by 2.2%.

arbiter worker-s per fired ply
                         B=16 = 246,010.154 / 26,330 =  9.34334       DERIVED (identity)
                         B=64 = 1,019,704.050 / 26,113 = 39.04967     DERIVED (identity)
                         B=32 = A_bar x 32 x c_incell(32)
                              = 3.26615 x 32 x 0.1827569 = 19.10117   PROJECTED
   cross-check, pure-linear:  2 x 9.34334 = 18.68668  (the projection is +2.22% over it,
   which is exactly the +2.11%/doubling inflation -- the two agree, as they must)

base game cost, arbiter removed
   from NARROW = 406.7473 - 164.0068 = 242.7406                        DERIVED
   from WIDE   = 928.0251 - 679.8027 = 248.2224                        DERIVED
   ⚠️ THE TWO DISAGREE BY 2.26% AND THAT IS DISCLOSED, NOT AVERAGED AWAY IN SILENCE.
      The WIDE cell's base is the higher one -- plausibly memory-pressure spillover from
      4x the arbiter scratch onto the same box. B = 32 sits between the two rungs, so
      the mean is the right pick and the spread BOUNDS the error at +-1.1%.
   => base COMMITTED = 245.4815 worker-s/game

phi   B=16 = 17.5533, B=64 = 17.4087 (spread 0.83%)
   ⚠️ phi is assumed EQUAL across cells and the assumption is STATED, not hidden. The
      trigger predicate does not depend on B, so phi should be B-invariant AT THE SAME
      POSITION; but the cells diverge onto different boards, so realized phi can differ.
   => phi COMMITTED = 17.4810 (mean); the projection carries a +-0.5% phi uncertainty

CELL_B32 per game = 245.4815 + 17.4810 x 19.10117 = 579.389 worker-s   <-- COMMITTED
CELL_B64 per game = 928.025 worker-s                                   <-- MEASURED, used directly
   identity check on CELL_B64 through the SAME committed constants:
      245.4815 + 17.4810 x 39.04967 = 928.147   (+0.013% vs the measured 928.025) ✓
   ⭐ THE IDENTITY CHECK IS THE POINT: the same base/phi/c chain that projects CELL_B32
      reproduces the MEASURED CELL_B64 to 1.3 parts in 10,000.
```

### 7.3 The `ms_ratio` decomposition — the same two points, in the per-move currency

```
Let  cand_ms(B) = base_ms + a16 x r(B),  r(16)=1, r(64) = 39.04967/9.34334 = 4.17941 (MEASURED)
   base_ms + a16          =  4,128.5725      (B=16, MEASURED)
   base_ms + 4.17941 a16  = 11,651.2766      (B=64, MEASURED)
   => 3.17941 a16 = 7,522.7041  =>  a16 = 2,366.1  ;  base_ms = 1,762.5

⭐ THE FREE CORROBORATION: base_ms = 1,762.5 lands within 0.04% of the OPPONENT's own
   measured rung_ms_per_move (1,763.20 at B=64 / 1,730.35 at B=16). The decomposition
   recovers the champion's bare per-move cost from the CANDIDATE side alone. That is an
   independent check the b64_cell could not run.

   a32 = a16 x 2 x 1.021114 = 4,832.1
   cand_ms(32) = 1,762.5 + 4,832.1 = 6,594.6
   ms_ratio(32) = 6,594.6 / 1,763.20 = 3.740        (vs 1,730.35: 3.811)
   => COMMITTED PREDICTION ms_ratio(CELL_B32) = 3.74
   PLAN_B_gt_16.md §5's INDEPENDENT projection: 3.75.  Agreement: 0.3%.
```

### 7.4 The supply chain — games to adjudicable decks

```
committed n per cell                            3,000  games       DESIGN §6.3
  --paired => decks per cell = n // 2           1,500  decks       eval_fair_puct.py:3924
  same band + same seed range in both cells => 1,500  COMMON decks by construction
  G-N completion floor, 80% (the campaign's amended bar, carried)
      games floor per cell = 0.80 x 3,000       2,400  games
      decks floor (n_common)                    1,200  decks       (the SAME 80% bar in decks)
  G-FAILED bound (DESIGN §8)                    <= 2%  of attempted, per cell
```

⚠️ **The two `G-N` clauses must agree in units AND be reachable.** Stage 2's committed text
read `n_common < 600` **decks** against a **400-deck ceiling** and was **unreachable by
construction** — a rule that could only ever return `U-UNREADABLE`. Here: 1,200 decks against
a **1,500-deck ceiling** ✓ and 2,400 games against a **3,000-game ceiling** ✓. **Both clauses
are reachable and both are independently binding** (two cells can each clear 2,400 games while
overlapping on fewer than 1,200 *common* decks).

### 7.5 The bill, and the two-box wall

```
CELL_B32   3,000 games x  579.389 worker-s  =  1,738,167 worker-s
CELL_B64   3,000 games x  928.025 worker-s  =  2,784,075 worker-s
TOTAL                                       =  4,522,243 worker-s  =  1,256.2 worker-h
```

**Two-box wall — and the occupancy derate is MEASURED on this exact arrangement, not
inherited.**

```
b64_cell realized worker-s (both cells) = 610,121.0 + 1,392,037.7 = 2,002,158.7 s = 556.155 wh
b64_cell realized WALL SPAN             = first -> last seed*.json mtime across both cells
                                        = 2026-08-20 01:08 -> 16:46 = 15.64 h    MEASURED
=> realized EFFECTIVE POOL              = 556.155 / 15.64 = 35.560 workers        DERIVED
=> realized occupancy derate vs 52 nominal = 52 / 35.560 = 1.4623                 DERIVED

=> THIS CELL'S COMMITTED WALL = 1,256.2 / 35.560 = 35.33 h                        <-- COMMITTED
   (nominal-52 ideal = 24.16 h; the derate is what turns it into 35.33 h)
```

⭐ **AND THAT DERATE IS A DISCLOSED MISS OF THE `b64_cell`'S OWN COMMITTED FIGURE.** The
`b64_cell` committed **1.190** (measured on Stage 2 and carried forward); the realized figure
on the run it committed it for is **1.4623** — a **1.229× miss**, in the direction that costs
wall-clock. **This cell commits the realized 1.4623, not the inherited 1.190.** That is the
R3.3 lesson applied to the derate: *re-derive, do not inherit*.

⚠️ **The `LAPTOP_RATE = 0.75` "effective capacity" model of
[`ALLOCATION.conf`](ALLOCATION.conf) is PRINTED AND NOT USED.** It says `30 + 22×0.75 = 46.5`
effective workers ⇒ 27.01 h, and it **under-predicts the measured arrangement by 1.31×**. The
committed wall uses the **measured** pool. The 0.75 figure survives in `ALLOCATION.conf` only
as the *sizing assumption on the log*, exactly as the campaign root's file does.

**Plus, not in the 35.33 h:** the smoke (≈0.6 h, §9), the per-host preflights and the `G-NEST`
witness (minutes), and the git-bundle sync before the two-box launch.

⇒ **COMMITTED PROJECTION: ≈ 1,256 worker-h, ≈ 35.3 h of two-box wall, ≈ 36–37 h door-to-door.**

⛔⛔ **THAT IS 2.26× THE `b64_cell`'S ENTIRE GAME PHASE AND IT IS THE HEADLINE COST FACT.** The
`b64_cell` ran 3,000 games in 15.64 h; this cell runs 6,000 games, of which the cheaper cell is
still 1.42× the price of that run's cheap cell. **The orchestrator and the owner should see
35.3 h before game 1, not after.**

---

## 8. The failed-record bound, and the divergence floor — both authored BEFORE any data exists

### 8.1 `G-FAILED` — three clauses, any one fires ⇒ `U-UNREADABLE`

[`DEVIATIONS.md`](../DEVIATIONS.md) **D4.18** declined a post-hoc numeric bound and required a
pre-registered one *"authored **before** its data, which is the only way a bound of that shape
is worth anything."* Discharged here.

1. **RATE, not count.** `n_failed / n_attempted > 0.02` in **either** cell.
   *Shape: a bound written as a fraction of `n` shrinks with the completion floor while the
   failure rate does not, so the bound is written in the scale-free **rate**. Level, from
   priors on DIFFERENT runs: the `b64_cell` realized **0/1,500 in both cells**; Stage 2
   realized 0/800 and 0/800; the JCZ cells realized 0. A 2% bar is ≈60 games in a 3,000-game
   cell against a realized prior of **zero** ⇒ it fires only on a regime change. Deliberately
   generous: its job is to catch a broken run, not to grade a good one.*
2. ⭐ **CANDIDATE-CORRELATION — the failure that actually threatens `D`.** With `F_32`, `F_64`
   the two cells' failed-game counts, fires if
   **`max(F) ≥ 5` AND `max(F) > 3 × max(min(F), 1)`.**
   *A failure rate that differs between cells makes the exclusion **candidate-correlated** —
   the `capoff` pattern — and biases `D` in an unknown direction, which is far worse than a
   diluted effect. The `≥ 5` floor exists because a bare ratio rule would have voided Stage 2's
   perfectly good run on its realized 1-vs-0 split. ⚠️ `CELL_B64` carries ~2× the per-ply
   exposure to the window-refusal class (§2.1), so this clause binds in the direction that
   protects the reading.*
3. **QUALITATIVE ESCALATION — carried VERBATIM from
   [`b64_cell/RULINGS_PREBLIND.md`](../b64_cell/RULINGS_PREBLIND.md) RULING 3, and the reason
   it is still the narrowed form is stated in §13.2:**

   > *"**(3)** If `F_w + F_n > 0`, the read-out must print, for every failed game, the
   > harness's raw failure record verbatim (message and traceback tail as emitted), and the run
   > **HALTS for owner escalation before adjudication** unless every failure is manually
   > confirmed to be the known `WindowTruncationError` class. **The confirmation is a human act
   > recorded in the read-out, and it is the one place this rule admits one** — it gates
   > escalation, never a branch."*

   ⚠️ **That is a deliberate, disclosed exception to "no owner call adjudicates any outcome":**
   it adjudicates **nothing** — no branch, no bar, no statistic moves on it — it decides only
   whether the run pauses. **Recorded as an exception rather than hidden as a convention.**

   ⭐ **NEW, AND NON-ADJUDICATING: the mechanical surface that DOES exist is now PRINTED.**
   §13.2 records that `eval_fair_puct` emits no `diagnostic_class` / `failed_classes` field —
   but it **does** emit, per failed game,
   `summary.json::failed_cells[].{seed, a_seat, attempts, permanent, exc_type,
   window_truncation, window_diag}` plus `resolved_failed_cells[]`. **The read-out MUST print
   all of it** ([READ_RULE](READ_RULE.md) §4.3 item 7). ⛔ **It is a REPORT, not a gate
   conjunct**, precisely because wiring a *new* address into a gate conjunct after sign-off is
   how the three unsatisfiable gates got shipped. It makes the human confirmation of clause 3
   mechanical in practice while leaving clause 3's text exactly as ruled.

**Mandatory reporting on every branch, including the passing ones:** `n_failed` and
`n_attempted` per cell, the realized rate against the 2% bar, `F_32` vs `F_64` against clause 2,
the full `failed_cells[]` dump, `tiearb_errors_total`, `tiearb_error_rate_on_fired`,
`tiearb_first_error`, `tiearb_partial_argmax_total`, and `phi_effective` beside `phi`. **And
the D4.18(c) selection-effect sentence, adapted:** window-truncation failures fire at extreme
board extents, so any dropped set is **correlated with board geometry** — late-game,
large-extent positions — and that correlation is **disclosed rather than argued away**.

### 8.2 ⭐ `G-DIVERGE` — the floor KEPT at 0.10, with its expected value RE-DERIVED at this rung

The `b64_cell` derived its expected `1 − f₀` from `PLAN_B_gt_16.md`'s pick-churn figures
(0.303 / 0.309 / 0.290 / 0.287), **which are the `1→2` / `2→4` / `4→8` / `8→16` rungs and say
nothing about `32→64`.** Carrying them here would be exactly the inherit-don't-re-derive class.
So the number is **measured directly, at this rung, on this campaign's own corpus**:

```
SOURCE: measurement/tiearb_widening_20260817/shared_run_r4/verdicts/per_position_s1.jsonl
        1,340 tied plies, J = 4, the R4 widening corpus (SPENT and ADJUDICATED -- a PRIOR,
        never the datum being graded)
STATISTIC: fraction of plies where arb_j4_E64_B<hi> != arb_j4_E64_B<lo>

   16 -> 32 :  581 / 1340 = 0.4336
   32 -> 64 :  542 / 1340 = 0.4045      <-- THIS CELL'S RUNG
   16 -> 64 :  704 / 1340 = 0.5254      <-- the b64_cell's rung, for CALIBRATION
   (at E = 16 the same three read 0.4291 / 0.4015 / 0.5201 -- 0.7% apart, so the read is
    E-insensitive)

⚠️ THIS IS A VALUE-CHANGE FRACTION AND IT IS A SUBSET OF PICK-CHANGE: a pick that moves to a
   DIFFERENTLY-INDEXED but EQUALLY-PRICED arm shows no value change. ⇒ it UNDERSTATES churn
   ⇒ every conclusion below is CONSERVATIVE.

fired plies per deck = 2 seats x phi 17.4810 = 34.962
expected 1 - f0 = 1 - (1 - 0.4045)^34.962 = 1 - 1.3e-8 = 1.0000
```

**Calibration against the one realized point:** at the `16→64` rung the same model predicted
`1 − f₀` ≈ 1.0000 and the **`b64_cell` realized 0.9840** (`READOUT_B64.json`). ⇒ the model
over-predicts by **1.6 pp** at a rung with 31% more churn.

⇒ **COMMITTED: the `G-DIVERGE` floor stays 0.10 on `1 − f₀`; the EXPECTED value is ≈0.98; and
a realized `1 − f₀` below 0.95 is an ANOMALY that must be REPORTED as one even though it
PASSES.** The 0.10 floor carries **≈10× headroom**: it is an **INERTNESS detector, not a power
check**, and the looseness is deliberate — a tighter floor risks failing a healthy run, this
campaign's most-repeated defect.

⚠️ **`f₀` is measured as "`D_i` exactly 0.0", which OVERCOUNTS identity** (two genuinely
different games can coincide on final margin) ⇒ `1 − f₀` **UNDERCOUNTS** divergence ⇒ **the
floor is CONSERVATIVE: it can only fire early, never late.**

---

## 9. The pre-registered bench/smoke step

**No games of the real cells may start until the smoke has run and its HALT bar has been
evaluated.** `B` = 32 has never been run at production knobs in a game anywhere.

### 9.1 What the smoke runs

Both cells, **at production knobs** — same champion, same k8×1376, same exact-K 2, same
`--paired --shared-claim`, same `nice 19`, same `W_LOCAL` / `W_LAPTOP`, same rust toolchain —
**only the game count differs.** `N_SMOKE` = **24 games per cell**. Throwaway band
**`900000400000`**, which is outside the `governance/BAND_REGISTRY.csv` allocation range, is
**never claimed**, and **does not touch the cell band `140000000000`**.

*(Precedent: Stage 2 used `900000100000` and the `b64_cell` `900000300000` on the same terms.
`900000400000` is verified unused anywhere in the repo.)*

⭐ **THE W-FREEZE-LATCH IS DROPPED FOR THE SMOKE LEG TOO, AND THAT IS DELIBERATE.** `run_cells.sh`
drops `RUN_LIVE.json` on the smoke exactly as on a real leg; **only `--dry-run` is exempt**
(§12.3). **The smoke plays 48 real games at production knobs**, so a main-tree commit landing
mid-smoke could put two revisions into one cost measurement — spawn respawns and each new
`--shared-claim` cell re-import from disk — which is precisely the hazard the latch exists for.
⚠️ **It is stated here rather than left to be inferred from the script** (REVIEW R1 item C6).
The `EXIT INT TERM` trap plus the close-out clear mean **no exit path — including the `exit 9`
refusals and a §9.3 HALT — can leave the tree latched.**

⭐ **CONDITION OF ACCEPTANCE (carried from the `b64_cell`'s R1 ruling 6): the throwaway band
must DECLARE ITSELF THROWAWAY in the smoke manifest.** `SMOKE.json` and every smoke
`manifest.json` carry `"band_tier": "throwaway"` and `"band_registry_claimed": false` beside
`band_seed_start`. It is **never** claimed in the registry and **never** read for an outcome
⇒ **it cannot later be mistaken for a claimed band**, the only way a throwaway band can do harm.

### 9.2 ⛔ COUNTS-AND-COST ONLY — the smoke may not read an outcome

The smoke reads and prints **only**: `wall_secs`, `secs_per_game`, `worker_secs_per_game`,
`games_per_sec`, `workers`, `champ_prefix_ms_per_move`, `rung_ms_per_move`,
`ms_ratio_cand_over_opp`, `tiearb_phi`, `tiearb_fired_plies_total`, `tiearb_tile_plies_total`,
`tiearb_fire_rate_on_tile_plies`, `tiearb_pickchange_rate`, `tiearb_mean_arms`,
`tiearb_playouts_total`, `tiearb_secs_per_game`, `tiearb_errors_total`, `tiearb_first_error`,
`tiearb_partial_argmax_total`, `cand_leaf_hash`, `carc_rs_build`, `carc_rs_binary_sha`,
`rust_toolchain`, `n_failed`, ⭐ **`production_knobs`**, ⭐ **`smoke_utc`**.

⭐ **THE LAST TWO ARE NEW, AND THEY EXIST TO MAKE A GATE CONJUNCT IMPLEMENTABLE.**
[READ_RULE](READ_RULE.md) §3's `G-SMOKE` fires when *"the smoke did not run at production knobs
before game 1"* — a conjunct that, as drafted, **read an address nothing wrote**, which is the
disease catalog's *"gate reading an address nothing writes"* landing on a live §3 row. The two
keys close it:

| key | shape | what it lets `G-SMOKE` check |
|---|---|---|
| **`production_knobs`** | a **dict echo of the §2 knobs as the smoke RESOLVED them**: `{k_dets, sims, exact_k, rules_profile, cand_leaf_hash, c_puct, tau_p, leaf_quantize, final_select, opponent, backend, cand_tiearb_per_cell}` | *"at production knobs"* — compared field-by-field against `WORKERS.conf`; **any mismatch fires** |
| **`smoke_utc`** | an **ISO-8601 UTC timestamp** of the smoke's completion | *"before game 1"* — compared against the earliest `seed*.json` mtime across both real cells; **`smoke_utc` ≥ that ⇒ fires** |

⚠️ **Both are COUNTS-AND-COST-CLASS structural keys, not outcomes.** A knob echo and a clock
reading carry no margin, no win-rate and no per-deck information, so admitting them does not
spend blindness — which is the only test §9.2 applies. ⚠️ **And they are STRUCTURAL keys, so
per RULING 1 of the `b64_cell` they never fire the `G-SMOKE` row's outcome-key scan.**

⛔ **It may not read, compute, print or store `paired_mean_margin`, `paired_z`, `elo`,
`winrate`, `W`/`D`/`L`, or any per-deck margin.**

⭐ **§9.2 DEFINES TWO SURFACES, and the distinction is CARRIED VERBATIM from
[`b64_cell/RULINGS_PREBLIND.md`](../b64_cell/RULINGS_PREBLIND.md) RULING 1 because collapsing
them fails a known-good smoke:**

> *"§9.2 defines TWO surfaces. The **emitter** whitelist is fail-closed on unlisted keys and
> governs what `SMOKE.json` may contain. The **`G-SMOKE` row** fires only on forbidden
> **outcome** keys, at any depth. Structural keys are expected and never fire the row. A
> reading that applies the emitter whitelist to the row fails a known-good smoke."*

⚠️ **`f₀` (the identical-deck fraction) is a MARGIN-DERIVED quantity and is therefore FORBIDDEN
at the smoke.** It is measured in-cell only, at the read-out. Named here so a well-meaning
implementation cannot add it "because it's just a count".

### 9.3 The HALT bar — one-sided, on realized-vs-committed cost

```
COMMITTED PROJECTION (§7.2):  CELL_B64 = 928.025 worker-s/game   (MEASURED on the b64 cell)
HALT BAR:                     realized CELL_B64 worker_secs_per_game > 1.50 x 928.025
                                                                    = 1,392.04 worker-s/game
```

**One-sided by construction: an overrun HALTS, an underrun proceeds.** On a HALT the real cells
are **not launched**, the smoke numbers and the revised bill are reported, and the decision
returns to the owner. No re-tuning of `B`, the trigger, `J`, `eps` or the playout is licensed by
a HALT — the only permitted responses are *stop*, or *the owner re-funds at the realized cost*.

#### 9.3.1 ⭐ `SMOKE_HALT.json` — the HALT decision record, and the three actors that touch it

**VERB ENUMERATION (§12.1, [`DEVIATIONS.md`](../DEVIATIONS.md) D6.2): the HALT is a named pass,
so its TOOL and its ADDRESS are named here, in the pair.** As drafted the bar had **no
artifact, no comparison and no enforcement** — it was logged and nothing read it, and the
`G-SMOKE` conjunct that was supposed to catch a launch-after-halt hung on an operator flag whose
default was the passing value. **That is the disease catalog's *pass-always gate (constant
input)* on a live §3 row, and it is closed here.**

```
ADDRESS   measurement/tiearb_widening_20260817/b32v64_cell/SMOKE_HALT.json
SHAPE     { "halt": <bool>, "realized": <float, CELL_B64 worker_secs_per_game>,
            "bar": 1392.038 }
MARKER    [post-smoke]
```

| actor | what it does with it |
|---|---|
| **WRITER** — `analyze_b32v64_cell.py smoke-check` | computes `halt = (realized > bar)` on `CELL_B64`'s realized `worker_secs_per_game` and **writes the record**. ⭐ **`halt` is in its EXIT CONDITION**: a HALT exits non-zero, so the smoke leg cannot return success on an overrun. |
| **ENFORCER** — `run_cells.sh` | **reads it before a real-cell launch and REFUSES (non-zero exit) when `halt == true`.** ⛔ **There is NO override flag.** A HALT holds until the owner rules — *stop*, or *re-fund at the realized cost* (§9.3) — and neither is a launcher decision. |
| **READER** — `G-SMOKE`'s launched-anyway conjunct | fires when **`halt == true` AND game records exist for either real cell**. ⭐ **Both terms are MECHANICAL and `[post-cells]`-observable**: at adjudication the cells demonstrably either ran or did not. |

⛔⛔ **THIS REPLACES ANY HUMAN FLAG.** An earlier build derived *"launched anyway"* from an
operator-supplied `--launched-after-halt` switch defaulting to `False` — i.e. to **PASS** —
which meant the gate could only ever fire if the person it was policing chose to accuse
themselves. ⚠️ **[READ_RULE](READ_RULE.md) §3 states there is EXACTLY ONE disclosed human input
into this rule — `G-FAILED` clause 3's escalation confirmation.** A second undeclared one would
have broken that promise. **`launched_anyway` is derived from the artifacts, never asserted by a
person.**

⚠️ **A HALT is not a branch and not a bar on the read.** It stops a launch; it adjudicates
nothing, moves no statistic, and appears in no branch condition. Cost remains a branch input
nowhere (§4, [READ_RULE](READ_RULE.md) §4.2).

⭐ **THE BAR IS GRADED ON `CELL_B64`, THE ONE CELL WHOSE COST IS MEASURED RATHER THAN
PROJECTED** — deliberately. Grading a 1.50× bar against `CELL_B32`'s *projection* would be
grading a model against itself. `CELL_B32`'s realized cost is **printed against its projection
and graded nowhere** (§9.4). ⚠️ **The consequence is stated rather than left implicit: a
`CELL_B32` cost blow-out passes the HALT bar.** That is accepted, because `CELL_B32` is the
CHEAPER cell by construction (it runs half the playouts of a cell that has already been
measured at these knobs, on the same box, and 2.11%/doubling super-linearity is already priced
in) — a blow-out there would have to be a >2.4× regime change against a cell that costs 62% of
the graded one, and the graded cell would see the same regime change first.

**Why 1.50, derived and justified pre-data.** The historical cost-model error class (Stage 2's
~2× `ms_ratio` miss) was a **currency error** — a sequential `t_champ` divided into a contended
per-move wall — and it does not apply here: §7.2 projects entirely in the **numerator's own
currency** (worker-s per game, measured in-cell, contended, at these worker counts) and never
divides by a sequential quantity. The largest error this currency has on record is the
`b64_cell`'s own **928.025 realized vs 958.794 committed = −3.2%**. A 1.50× bar is **≈16× the
largest error this currency has ever shown.** It is deliberately loose: its job is to catch a
regime change, not to grade a 15% modelling error.

### 9.4 Prediction vs realized — printed, never graded (except row 1)

| quantity | committed prediction | grounds | realized |
|---|---|---|---|
| `CELL_B64` worker-s/game | **928.025** | §7.1, MEASURED | measured |
| `CELL_B32` worker-s/game | **579.389** | §7.2, PROJECTED | measured |
| `ms_ratio` `CELL_B64` | **6.608** | `b64_cell` realized | measured |
| `ms_ratio` `CELL_B32` | **≈ 3.74** | §7.3 (PLAN_B's independent 3.75) | measured |
| `phi` both cells | **17.481** | §7.2 (b64 realized 17.5533 / 17.4087) | measured |
| effective worker pool | **35.560** | §7.5, MEASURED | measured |
| occupancy derate vs 52 | **1.4623** | §7.5, MEASURED | measured |

⚠️ **Only row 1 is graded (§9.3).** ⚠️ **The field-name trap travels with the `ms_ratio` rows:
`champ_prefix_ms_per_move` IS THE CANDIDATE SIDE.** ⚠️ **The real cells' `ms_ratio` is NOT
graded against the smoke's** — both are printed and neither grades the other (Stage 2 §0.H): a
bar written after a smoke number exists is not a bar.

---

## 10. Threats — stated before the numbers

1. ⭐ **UNDER-POWERED NON-INFERIORITY IS THE HEADLINE THREAT, and it is declared, not
   discovered.** At the committed dispersion the `L-SATURATED` branch fires with EFFECTIVE
   probability **0.556** (0.629 at the realized-dispersion projection) when `B` = 32 is exactly
   as good as `B` = 64, and **0.446** at the offline bracket top (§6.4). ⭐ **RULING 1's
   one-sided shape roughly TRIPLED that from the drafted 0.158 at no extra spend** — but ~44% of
   the equal-rungs world still reads `L-AMBIGUOUS`, which carries a mandatory power print. ⛔ **No
   read-out may present `L-AMBIGUOUS` as evidence of a cost.**
2. **The offline-implied effect sits INSIDE the tolerance and OUTSIDE the reachable window**
   (§5.2 bracket top +0.1555 vs the committed-dispersion window 0.1003). A knife-edge on the
   realized dispersion, stated in §6.4.
3. **Dilution by agreement.** The nested CRN means most plies may resolve identically and
   `z_D ∝ √(1−f₀)`. `G-DIVERGE` refuses an inert surface; nothing rescues a merely-thin one.
   Expected `1 − f₀` ≈ 0.98, anomaly bar 0.95, gate floor 0.10 (§8.2).
4. **~2× exposure to the window-refusal class in `CELL_B64` only** — a candidate-correlated
   exclusion risk. `G-FAILED` clause 2 (§8.1).
5. **The cost is 35.3 h of two-box wall** (§7.5), 2.26× the `b64_cell`'s whole game phase, and
   the derate that produces it is a **1.229× miss** of the figure the `b64_cell` committed. A
   further miss of the same size would put this run near 43 h.
6. **Cross-band humility does not apply within this run** (one band, one deck set) — it **does**
   apply to every comparison of these numbers against the `b64_cell`'s band-139e9 figures, and
   **no such comparison is a branch input anywhere.**
7. **`CELL_B64` is a fresh-band replicate of the DEPLOYED shape and will be read as one.** It is
   reported; it is **not** a branch input; and **no branch re-adjudicates the `b64_cell`**, whose
   read-rule is spent and whose band is retired. ⚠️ A large band-to-band discrepancy in
   `CELL_B64`'s own elo would be **evidence about band dispersion**, not about the arbiter, and
   the read-out must say so if it appears.
8. **The elo gloss is a one-run empirical conversion.** Every branch is written in pts/game; the
   gloss exists only to state the owner's tolerance in his own currency (§6.2).

---

## 11. Secondary readings — reported, adjudicating nothing

Each cell's **win-rate, elo with CI, and W/D/L against the common unmodified-champion
opponent** are reported. Together with the `b64_cell`'s two points they sketch a four-rung
game-currency curve:

| rung | band | elo vs the unmodified champion | status |
|---|---|---|---|
| `B` = 16 | 139e9 | **+36.2644 ± 9.0197** (wr 0.552, M +3.6607) | RETIRED band |
| `B` = 64 | 139e9 | **+63.9457 ± 9.1231** (wr 0.591, M +5.3773) | RETIRED band |
| `B` = 32 | **140e9** | *this cell* | fresh |
| `B` = 64 | **140e9** | *this cell* | fresh |

⛔⛔ **THE MANDATORY CROSS-BAND HUMILITY DISCLAIMER, and it is not optional prose.** CLAUDE.md:
cross-band contrasts are **over-dispersed 1.8–2.2× in BOTH statistics**, and *"never pool across
bands and quote the pool as an estimate"*. Therefore:

- **The 139e9 numbers MUST NOT be pooled with the 140e9 numbers**, plotted as one curve without
  the band labels, or differenced to produce any estimate.
- **Band 139e9 is RETIRED from confirmatory use** (`decision_influenced=yes`) and cannot support
  a new verdict at all.
- **The only robust contrast in this run is the WITHIN-BAND deck-paired `D`**, and it is the
  only branch input.
- The four-rung table may be **shown, with its band column**, as a *description*. It may not be
  fitted, differenced across bands, or called a curve measurement.

---

## 12. Governance, and the VERB ENUMERATION

### 12.1 ⭐ Every pass, gate and witness this pair names — with its TOOL and its ADDRESS

[`DEVIATIONS.md`](../DEVIATIONS.md) **D6.2**, the standing rule: *a pair may not name a pass
without naming its tool.* Discharged in full. **A row with no emitter is a drafting defect.**

| named thing | TOOL that performs it | ADDRESS it writes | exists? | pinned relative to |
|---|---|---|---|---|
| the band claim | `scripts/classical_search/claim_next_band.py` | `governance/BAND_REGISTRY.csv` row + `b32v64_cell/BAND_CLAIM.json` | ✅ **DONE** (§12.2) | before game 1 |
| `G-J13` two-sided control | `b32v64_cell/preflight.sh` → `measurement/tiearb2_stage2_20260817/preflight_tiearb.py` | `b32v64_cell/verdicts/PREFLIGHT_${HOST}_FIRST_B{64,32}.json` at the PINNED keys `j13_witness.{B,pick_changed,root_leaf_value_bits_unchanged}` + `expected.B` | ✅ built | **after** any wheel rebuild on that host, **before** that host's game 1 |
| `G-NEST` 32 ⊂ 64 witness | `b32v64_cell/gate_nest.py` | `b32v64_cell/GATE_NEST.json` | ✅ built | at HEAD, before game 1 |
| the two cells | `b32v64_cell/run_cells.sh` → `scripts/classical_search/eval_fair_puct.py` | `$SHARE/tiearb_widening_20260817_b32v64_cell/b32v64_B{32,64}J4_deploy11008/{summary,manifest,seed*}.json` | ✅ built | after the preflight and the smoke |
| the W-FREEZE-LATCH sentinel | `b32v64_cell/run_cells.sh` (drop at leg start, clear on EXIT/INT/TERM) | `b32v64_cell/RUN_LIVE.json` | ✅ built | for the life of every leg; **never on a dry run** |
| the smoke aggregation | `scripts/tiletie/analyze_b32v64_cell.py aggregate-smoke` | `$SHARE/…/smoke/SMOKE.json` (incl. `production_knobs`, `smoke_utc`) | ✅ built | after both smoke cells |
| the §9.2 whitelist / outcome scan | `scripts/tiletie/analyze_b32v64_cell.py smoke-check` — ⚠️ **it READS `SMOKE.json`; `aggregate-smoke` above WRITES it** | **stdout only** — the report doc's `emitter_surface` (the write-discipline result, reported beside the gate) and `gate_surface` (the forbidden-outcome-key scan, the gate input). ⛔ **Nothing is written back into `SMOKE.json`** | ✅ built | after `aggregate-smoke`, on `SMOKE.json` |
| ⭐ **the HALT decision record** | `scripts/tiletie/analyze_b32v64_cell.py smoke-check` — computes `halt = realized > bar` on `CELL_B64` (`halt_record()`) and **exits non-zero on a HALT**; the record is its **only file output** | **`b32v64_cell/SMOKE_HALT.json`** `{halt, realized, bar}`, path passed as `--halt-out` (§9.3.1) | ✅ **built** | after `aggregate-smoke`, before any real-cell launch |
| ⭐ **the HALT ENFORCEMENT** | `b32v64_cell/run_cells.sh::require_no_halt` — reads `SMOKE_HALT.json` and **REFUSES a real-cell launch on `halt == true`, with NO override flag**; exempt on `--dry-run` and `--smoke`, which report the record's state and never create one | non-zero exit; **no game record written** | ✅ **built** | before game 1 |
| ⭐ **the four NAMED preflight addresses** (§2.2) | `scripts/tiletie/analyze_b32v64_cell.py::named_preflights` — resolves the four un-timestamped names itself and collects `_<epoch>` rotations SEPARATELY as report-only superseded artifacts | the `G-J13` / `G-TOOL` input set + the rotation report | ✅ **built, and it is the SINGLE resolution path** — `knowngood` and `adjudicate` both go through it; no caller-supplied glob is accepted | before the read-out |
| the `D` block and every §3 gate | `scripts/tiletie/analyze_b32v64_cell.py adjudicate` | `b32v64_cell/verdicts/READOUT_B32V64.{json,md}` | ✅ built | after both cells |
| the §4.1 branch-truth-table sweep | `tests/test_tiearb_b32v64.py` (re-transcribing [READ_RULE](READ_RULE.md) §4 **independently of the implementation**) | pytest | ✅ built (130 passing) | before the blind commit |
| the known-good partition | `scripts/tiletie/analyze_b32v64_cell.py knowngood` over the `b64_cell`'s completed artifacts | `b32v64_cell/KNOWNGOOD_EVAL.json` | ✅ built (13/13 PASS, 0 N-A) | before the blind commit |

⛔⛔ **NAMING A PASS'S TOOL AND ADDRESS IS A LAUNCH PRECONDITION, NOT A RIDER.** ⭐ **Status as
of REVIEW R2 (2026-08-21): every row above is BUILT and tested — the table has NO open rows.**
R1's three blocking gaps (the `SMOKE_HALT.json` write, its enforcement in the launcher, and
`named_preflights` as the single resolution path) are closed at site and verified functionally,
and R2's verdict is **PASS, 0 blocking**. ⚠️ **The two stale `⛔ BUILDER'S QUEUE` markers and
the `SMOKE.json::whitelist_report` address that nothing writes were themselves R2 findings
(N1/N2), corrected here** — a verb table that records the wrong writer, or a status that has
moved on, is the same defect class it exists to prevent.

They are listed here rather than assumed, because *"the pair named a pass and named no tool"* is
[`DEVIATIONS.md`](../DEVIATIONS.md) D6's own defect class and it has now fired **three** times
in this campaign — ⭐ **and it fired a FOURTH time in this very package**: the drafted §9.3
named a HALT bar and named **no artifact, no writer and no enforcer**, so the bar was logged and
nothing read it (REVIEW R1 B6). §9.3.1 is that gap closed in the pair's own text.
`run_cells.sh` **refuses** (exit 9) if the adjudicator is absent at the smoke step, so an
absence cannot be discovered late.

⭐ **AND THE B1 LAUNCH PRECONDITION IS ADOPTED VERBATIM from the `b64_cell`
([its DESIGN §13.1](../b64_cell/DESIGN.md)): every §3 gate row must be evaluated against a
COMPLETED, KNOWN-GOOD run's artifacts and must PASS on it, before the blind commit.** The
known-good fixture set for this cell is the `b64_cell`'s own completed run (§3). **A gate that
fails a healthy run is a drafting defect, and a fail-closed gate that *always* fails is not
conservative — it is a rule that cannot be run.** That campaign has caught **three**
unsatisfiable gates this way (Stage 2's `G-N`, R4-0.2's probe loop, the `b64_cell`'s own
`G-TOOL`); §13.1 below records the checks this draft ran against the same class.

### 12.2 The band — CLAIMED, and recorded rather than implied

⚠️ **The `b64_cell` deliberately did NOT name its band in the draft** (*"naming a band in this
draft would pre-empt a registry the reviewer has not read"*). **This draft does the opposite,
on the orchestrator's explicit instruction**, and the difference is recorded so it reads as a
deviation from the sibling's practice rather than as an oversight.

```
TOOL      scripts/classical_search/claim_next_band.py --tier claim
ADDRESS   governance/BAND_REGISTRY.csv (row appended) + b32v64_cell/BAND_CLAIM.json (sentinel)
BAND      140000000000        (registry high-water mark was 139000000000, RETIRED)
RANGE     140000000000 .. 140000001499   (1,500 decks, each played twice with seats swapped)
STATUS    claimed / decision_influenced = pending      <- doc_lint W4 flags live rows ON PURPOSE
DATE      2026-08-20, BEFORE game 1 and before any statistic of this run exists
```

⚠️ **If this cell is never funded to launch, the row must be flipped to `RELEASED UNUSED`**, the
way the `136000000000` row was. A claimed band that never ran is a bookkeeping obligation, not a
silent gap. ⇒ **the band is one-use and it retires from confirmatory use at close-out** on every
branch.

### 12.3 The rest

- **This cell plays games.** On a terminal branch it writes: an `experiments/results.csv` row
  **per cell** plus one for `D`, the `BAND_REGISTRY` row flipped from `pending` to the realized
  `decision_influenced`, and a claim id in `governance/CLAIM_REGISTRY.csv` **only if a branch
  mints one** (none does — see [READ_RULE](READ_RULE.md) §5).
- **`governance/PRODUCTION.yaml` is untouched on EVERY branch.** No branch flips the deployed
  `B` = 64 / `J` = 4 shape. `L-SATURATED` **licenses** a swap-down decision for the owner; the
  owner executes it with one word, and the prereg never edits the file itself.
- **No branch re-reads, re-labels or re-adjudicates** Stage 1, Stage 1b, Phase A, Stage 2 Phase
  B, the R4 widening run, `rung3_r5`, or the `b64_cell`. They stand as adjudicated; their
  read-rules are spent and their bands retired.
- **Numbered deviations continue the shared sequence.** [`DEVIATIONS.md`](../DEVIATIONS.md)
  currently runs to group **D6** (D6.1–D6.6). Deviations from this cell open group **D7** and
  number **D7.1, D7.2, …** ⛔ **Nothing existing is renumbered, reordered or edited.**
- **Close-out is the six-touch checklist in one sitting**: `results.csv` rows → DECISIONS index
  line → status banner on this doc → governance row flips (`BAND_REGISTRY` / `CLAIM_REGISTRY`)
  → STATUS top block → roadmap line. Then `python3 scripts/doc_lint.py` clean.
  [`docs/LEVER_INDEX.md`](../../../docs/LEVER_INDEX.md) §6's `B > 16` row is amended at close.
- **Launch discipline: launch → verify → report → STOP.** The completion watch belongs to the
  orchestrator; the `DONE_<cell>` / `FAILED_<cell>` marker convention is written into the
  progress log and handed over explicitly. **Detach every run** (`setsid` / `nohup … & disown`);
  the harness's background flag alone is not enough.
- **W-FREEZE-LATCH.** `run_cells.sh` drops `RUN_LIVE.json` at leg start and clears it at
  close-out **and on any exit** (`trap … EXIT INT TERM`), so an abort cannot leave the tree
  latched, and it is **never dropped on a dry run**. `scripts/hooks/pretooluse_lint.py` refuses
  a main-tree commit while it exists; `tests/test_freeze_latch.py` is its test.
- **Worktree isolation.** Any source edit this cell needs (there should be none — §2) merges at a
  quiet window after a process census on every box, never beside a live run.

---

## 13. Self-review against the disease catalog, and the spec-vs-buildable mismatches

### 13.1 ⭐ The disease catalog — each disease named, and where this draft checked for it

| disease | where it was checked | finding |
|---|---|---|
| **pass-always gate (constant input)** | every §3 row's input traced to a per-run emitted address | ⚠️ `G-J13`'s `expected.B` is a *constant the emitter injects* — but it is checked **against the probe's own measured `j13_witness.B`** and a disagreement is FATAL in `preflight.sh`, so the pair is not self-satisfying. `G-NEST` is a *structural* claim about code at HEAD and is **deliberately** near-constant across runs; that is what a precondition witness is, and it is not a run-outcome gate. |
| **pass-always gate (empty exclude-list default)** | `G-FAILED` clause 3 | ⚠️ **REAL AND CARRIED.** At `F_32 + F_64 = 0` clause 3 is **vacuous** and the gate passes on emptiness. That is the b64 residual, ruled at RULING 3, and it is **kept as ruled** rather than re-litigated. Clauses 1 and 2 evaluate on quantities the harness emits and are not vacuous. |
| **fail-always gate (wrong currency)** | `G-N` (decks vs games), `G-FIRE` (phi vs phi_effective), `G-DIVERGE` (`1−f₀` vs `f₀`) | `G-N`: 1,200 decks against a **1,500-deck ceiling** and 2,400 games against a **3,000-game ceiling** — **both reachable** (Stage 2's version was not). `G-FIRE`'s floor 1.0 against a realized prior of 17.4–17.6. `G-DIVERGE`'s floor 0.10 against an expected 0.98. **None can fail a healthy run.** |
| **fail-always gate (normal value treated as a sentinel)** | `G-TOOL` | **The `b64_cell`'s B1 fix is carried verbatim: `+rustcunpinned` is the NORMAL production value and PASSES provided both boxes emit it.** The conjunct is **equality of `carc_rs_build` across boxes and nothing else**. `preflight.sh` re-evaluates the probe's two pre-B1 sentinel rows under the ruled reading and records the supersession **with its citation**, never silently. |
| **gate reading an address nothing writes** | §12.1's verb table | **Five addresses have no emitter yet** and they are named as **LAUNCH PRECONDITIONS** with `run_cells.sh` refusing at exit 9 rather than proceeding. ⭐ **The one address the `b64_cell` left unwritten — the pinned `j13_witness.*` booleans — is CLOSED HERE**: `preflight.sh` injects them (copying, never inventing) **and then asserts all four pinned addresses are present and both booleans are `true`**, failing loudly and naming the absent address. |
| **a bar written after its number exists** | the smoke's `ms_ratio`, the real cells' `ms_ratio`, `f₀` | **None of the three is a bar anywhere.** The smoke's and the cells' `ms_ratio` are both printed and **neither grades the other**; `f₀` is forbidden at the smoke entirely. |
| **an unreachable headline branch** | §6.4 | **All five branches computed and declared reachable BEFORE game 1**, with `L-SATURATED`'s window (`D̂ ≤ +0.1003`) and its **55.6% EFFECTIVE power at a true null** stated in the design rather than discovered in the read-out. ⭐ Recomputed for the one-sided shape at RULING 1 and re-declared — **the amendment did not move a bar without moving its reachability figures with it.** |
| ⭐ **a one-sided predicate silently swallowing the other tail** | [READ_RULE](READ_RULE.md) §4.4 | **REAL, DELIBERATE, AND SPELLED OUT.** RULING 1's `EQUIV` is TRUE for every sufficiently negative `D`; the predicate alone would let `L-SATURATED` claim the whole lower half-line. `L-REVERSED` is evaluated **second** and pre-empts it, so the EFFECTIVE region is `(−2·se_D, 0.93 − 1.645·se_D]` — **bounded below by BRANCH ORDER, not by the predicate.** ⇒ **the order is load-bearing and any re-implementation must preserve it**, and the mildly-negative case that *does* fire `L-SATURATED` is correct (the claim *"32 does not cost 15 elo"* is more comfortably true there) with a mandatory rider forbidding the superiority reading. |
| **sizing on data** | §6.1 | `n` is fixed at the committed dispersion and is **not** revised by the smoke, by `ρ`, or by `f₀`. The smoke may HALT; it may never resize. |
| **inheriting arithmetic instead of re-deriving it (R3.3)** | §7, §8.2 | Every cost primitive re-read off the `b64_cell`'s realized artifacts; the **occupancy derate re-measured (1.4623 vs the inherited 1.190)**; the **`G-DIVERGE` expected value re-measured at the 32→64 rung** instead of carrying `PLAN_B`'s `8→16` churn. |
| **a whitelist read as governing two surfaces** | §9.2 | RULING 1's two-surface distinction carried **verbatim**. |
| **cross-band pooling** | §11 | The only branch input is the within-band deck-paired `D`. The four-rung table carries a band column and a prohibition. |

### 13.2 ⚠️ Spec-vs-buildable mismatches found by this draft — REPORTED, not resolved

1. ⛔ **THE ADJUDICATOR DOES NOT EXIST.** `scripts/tiletie/analyze_b64_cell.py` is hard-coded to
   the `b64_cell` at module scope (`CELL_DIR`, `B_BY_CELL = {"WIDE": 64, "NARROW": 16}`,
   `CELL_GAMES_PLANNED = 1500`, `SE_D_COMMITTED = 0.7133`, `WORKER_S_COMMITTED`,
   `BRANCH_ORDER`/`BRANCH_TEXT` for the six `B-*` branches, the `WAIVER_REGEX`, the
   `SMOKE_HALT_BAR`). **It cannot be reused by flag** and its branch set is not this cell's.
   ⇒ **`scripts/tiletie/analyze_b32v64_cell.py` must be BUILT** (§12.1). ⚠️ **Reported, not
   resolved: building it is a separate, briefed job, and writing an adjudicator inside the same
   pass that writes the pair it adjudicates is the coupling this campaign has ruled against.**
2. ⚠️ **`eval_fair_puct` STILL emits no `diagnostic_class` / `failed_classes` field** — checked
   at HEAD (`grep -n "failed_classes\|diagnostic_class" scripts/classical_search/eval_fair_puct.py`
   → no match). ⇒ **`G-FAILED` clause 3 carries RULING 3's narrowing VERBATIM** (§8.1 clause 3),
   as the brief required. ⭐ **BUT A PER-FAILURE SURFACE DOES EXIST AND THE `b64_cell` DID NOT
   NAME IT:** `_failure_block()` (`eval_fair_puct.py:2314-2359`, in place since **2026-08-14**,
   i.e. **before** the `b64_cell` was drafted) emits, per failed game,
   `summary.json::failed_cells[].{seed, a_seat, attempts, permanent, exc_type,
   window_truncation, window_diag}` and a parallel `resolved_failed_cells[]`, plus
   `failure_rate`, `failure_rate_trigger` and `validity_trigger_fired`. **`window_truncation` is
   exactly the boolean clause 3's human confirmation is about.** ⇒ **This draft PRINTS all of it
   (§8.1, [READ_RULE](READ_RULE.md) §4.3 item 7) and WIRES IT INTO NO CONJUNCT** — the brief's
   instruction was "wire clause 3 to a `diagnostic_class`/`failed_classes` field if it exists,
   else carry RULING 3 verbatim", and neither named field exists. **The orchestrator should
   decide whether a future pair promotes `failed_cells[].window_truncation` to a mechanical
   conjunct; this draft does not, and says so rather than doing it quietly.**
3. ⚠️ **`gate_nest.py` was hard-coded, not parameterized.** `b64_cell/gate_nest.py` carries
   `B_WIDE, B_NARROW = 64, 16` as module constants with no `--b-*` flags, so the "reuse by flag"
   preference could not be honoured. ⇒ **copied into `b32v64_cell/` and given real `--b-hi` /
   `--b-lo` flags** (the brief's stated fallback: *"copy into `b32v64_cell/` if parameterization
   requires edits"*). The `b64_cell`'s file is **untouched**.
4. ⚠️ **`preflight.sh` and `run_cells.sh` could not be thin wrappers either.** Both source
   `WORKERS.conf` **from their own directory** by design (`. "$(dirname "$0")/WORKERS.conf"`),
   and the `b64_cell`'s copies name `$TIEARB_B_WIDE` / `$TIEARB_B_NARROW`, `b64_cell` paths, and
   `analyze_b64_cell.py`. A wrapper would have to re-export half the conf and would break the
   "one place per-box counts live" discipline. ⇒ **copied and parameterized**, `b64_cell`'s
   originals untouched.
5. ⚠️ **`ALLOCATION.conf` has no enforcement surface for a game cell.** The campaign root's
   `ALLOCATION.conf` allocates *static chunks* because `run_tiletie.py` has no work-stealing.
   `eval_fair_puct.py` **does** (`--shared-claim`), so **the split between the two boxes is
   DYNAMIC and this file cannot pin it.** ⇒ [`ALLOCATION.conf`](ALLOCATION.conf) here is a
   **sizing and expectation document**, and it says so in its own header rather than pretending
   to control something it does not.
6. ⚠️ **"the two invocations differ in EXACTLY ONE argument" is not literally true, and the
   launcher's banner now says so.** They also differ in `--out-subdir`
   (`b32v64_B32J4_deploy11008` vs `…B64J4…`) and `--claim-host` (`b32v64-B32-<host>` vs
   `b32v64-B64-<host>`). **Both are BOOKKEEPING**: two cells cannot share one output directory
   or one `--shared-claim` tag without corrupting each other. This is exactly the `b64_cell`'s
   shape and it is kept; the banner reads **"EXACTLY ONE EXPERIMENTAL ARGUMENT"** and names the
   two bookkeeping differences. ⇒ **exactly one experimental knob differs, and the claim is now
   stated at the precision it is true at.**
7. ⚠️ **`gate_nest.py`'s STRUCTURAL half still imports
   `scripts/tiletie/analyze_b64_cell.py::nest_witness`** — a live dependency on a **spent
   run's** tooling. It is carried because `nest_witness` asserts a property of the **rust
   source** (the four seeding sites in `tiearb.rs` are pure functions of `j` with no `B` term),
   which is a claim about the code and not about any `(B_lo, B_hi)` pair, so it transfers
   unchanged. **Documented in-file** (`structural_source` field + docstring). ⇒ **REPORTED as a
   cross-cell dependency for the orchestrator to rule on**: when
   `scripts/tiletie/analyze_b32v64_cell.py` is built it should expose the same function rather
   than restate the regexes, and the import should move there.
8. ⭐ **THE INHERITED `LAPTOP_RATE = 0.75` IS WRONG FOR THIS WORKLOAD, and this draft measured
   it rather than carrying it.** `PLAN_B_gt_16.md`'s ~25% per-worker laptop slowness was
   measured on the **OFFLINE SCORING** layer (clair-puct legs). Recovered per-box from the
   `b64_cell`'s `*.claim` files joined to `seed*.json::elapsed_s` (3,000 records, 100%
   attributed), the laptop is **FASTER** per worker on **game play**: rate laptop/local
   **1.121** (WIDE) / **1.032** (NARROW). ⚠️ **And the under-occupied box is the LOCAL one —
   55.8% occupancy at `W` = 30 (16.73 effective workers) vs the laptop's 85.6% at `W` = 22** —
   consistent with CLAUDE.md's standing DRAM-bound `W ≈ 14–16` finding, i.e. **`W_LOCAL` = 30
   is very plausibly past the knee.** ⛔ **NOT CHANGED HERE: the owner pinned "local 30w. laptop
   22w." verbatim and a drafter does not move an owner-set knob.** It is reported in
   [`ALLOCATION.conf`](ALLOCATION.conf) with the recommendation (a `W_LOCAL` re-bench at THIS
   cell's production knobs) flagged as **a recommendation for the orchestrator, not an action**.
   The committed wall is unaffected either way — §7.5 divides by the **measured** 35.560-worker
   pool, not by any rate model.
