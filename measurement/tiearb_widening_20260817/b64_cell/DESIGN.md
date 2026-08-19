# THE `B = 64` GAME CELL — DESIGN (DRAFT)

> **STATUS: DRAFT FOR A SECOND DRAFTER. NOT A PREREGISTRATION. NOT COMMITTED BLIND ON
> `main`. NOTHING LAUNCHED, NO BAND CLAIMED, NO SMOKE RUN, NO GAME PLAYED.**
>
> Authored under a 20-hour owner delegation (owner verbatim: *"take the highest EV picks.
> I can't look over details right now"*). That delegation authorizes **drafting and
> committing in a worktree**; it does **not** authorize the blind commit on `main`, the
> band claim, the smoke, or the run. [§10](#10-open-choices-left-for-the-reviewer)
> lists the choices deliberately left open.
>
> Written **before** any statistic of this cell exists. Every number in this file is
> either (a) read off a completed run's artifact on disk with its path given, or (b)
> derived from those by arithmetic shown in full. Nothing is guessed and nothing is
> inherited un-rederived — the R3.3 miss class is *supply arithmetic copied forward
> without re-deriving it* ([`PREREG_FAILURE.md`](../PREREG_FAILURE.md) §2), and
> [§7](#7-supply-chain-and-cost--every-stage-shown) re-derives every stage.
>
> `governance/PRODUCTION.yaml` is untouched on every branch. No claim is minted by this
> file. Its mechanical companion is [`READ_RULE.md`](READ_RULE.md), which must be
> committed in the **same commit** as this file.

---

## 0. The question, and what made it live

**The question, in one sentence:** *does widening the deployed tie-arbiter's selection
worlds from `B = 16` to `B = 64` buy real game points, over and above what the deployed
`B = 16` arbiter already buys?*

**The estimand is the INCREMENT over the deployed arbiter, not over the bare champion.**
Stage 2 Phase B already answered "does the arbiter beat the champion" (branch
`G-CONFIRMED`, `M_arb` +3.0700 pts/game, `z` +4.445 —
[`tiearb2_stage2_20260817/READOUT.md`](../../tiearb2_stage2_20260817/READOUT.md)). This
cell asks a strictly different question and must never be read as re-asking that one.

### 0.1 What made it live — the `W-RISING` read, carried verbatim

[`shared_run_r4/verdicts/READOUT.md`](../shared_run_r4/verdicts/READOUT.md), 2026-08-19,
pre-registered branch **`W-RISING`**, reason verbatim:

> **BRANCH: `W-RISING`** — lower(CI)>0, d>=0.04, arb_64 convicts, arb(64)>arb(16)
>
> - `Δ(16→64)` = 0.0670 CI95 [0.0215, 0.1111] se_root 0.0228 (committed floor +0.04)
> - `Δ(16→32)` = 0.0597 CI95 [0.0190, 0.0998] — reported with its CI, **never a branch
>   input on its own**

The `arb` ladder at `E = 64` evaluation worlds, `n` 1,340 plies / 748 roots:

| B | 1 | 2 | 4 | 8 | **16** | 32 | **64** |
|---|---|---|---|---|---|---|---|
| `arb` (pts/tied ply) | 0.0282 | 0.0118 | 0.1010 | 0.0954 | **0.1345** | 0.1942 | **0.2015** |

### 0.2 ⛔ What `W-RISING` licenses — carried verbatim, and it is NOT this cell

[`docs/LEVER_INDEX.md`](../../../docs/LEVER_INDEX.md) §6, the `B > 16` row, verbatim:

> ⛔ **LICENSES NOTHING AUTOMATIC: `PRODUCTION.yaml` UNTOUCHED, no claim id, no on-device
> deploy, no change to the deployed B=16/J=4 shape.** ⚖️ **A B=64 GAME CELL IS AN OWNER
> DECISION and is not scheduled**

⇒ **This document is a draft of the thing the owner has not yet decided to buy.** It
exists so the decision can be taken against a real design, a real cost, and a real power
figure rather than against a hope. It is not a licence and it does not become one by
being committed.

### 0.3 ⛔ The scope fence on `W-RISING` itself, carried verbatim

> ⛔ **AND READ THE BRANCH FOR EXACTLY WHAT IT SAYS: a null here would have meant "no rung
> above 16 is worth ≥ +0.04 pts/tied ply", NOT Δ = 0 — so `W-RISING` convicts only that
> the ladder still pays AT THE FLOOR, and the saturating-exp (+0.017) and √B-noise
> (+0.021) models are NOT resolved by this design.**

⇒ The offline read establishes **that the ladder still pays at the floor**, in an
**offline per-tied-ply currency, priced by a terminal-grounded oracle on 1,340 selected
plies**. It does **not** establish a magnitude in game points and it does not establish a
shape. This cell measures game points; it does not settle the shape either.

### 0.4 The Stage-2 anti-gaming clause is NOT being violated — stated so nobody has to wonder

Stage 2's owner ruling ([`tiearb2_stage2_20260817/READ_RULE.md`](../../tiearb2_stage2_20260817/READ_RULE.md)
§0.D) contains, verbatim:

> **`B` stays 16** — the evidenced rung, and it may **not** be expanded beyond 16 either;

⚠️ **That clause was scoped to Stage 2's own cell and its own reading.** Its stated
purpose was anti-gaming: *"permission to spend clock, never licence to reshape the
arbiter to look cheaper"* — i.e. it forbade moving `B` **to duck a cost bar inside that
cell**. It was not a programme-wide prohibition on ever measuring a wider rung; the
widening campaign was already chartered when it was written, and `W-RISING` is the
evidence it asked for. **This cell moves `B` to answer a question, not to look cheaper —
and it moves `B` in the direction that makes the cost *worse*, which is the opposite of
gaming.** Nothing else in the deployed shape moves ([§2](#2-the-two-cells)).

---

## 1. The shape of the contrast, and why it is two cells rather than one

### 1.1 ⚠️ THE HARNESS CANNOT PUT AN ARBITER ON THE OPPONENT — verified, not assumed

`scripts/classical_search/eval_fair_puct.py` exposes `--cand-tiearb-{enabled,b,j,mode,salt,eps}`
and threads them to the **candidate only** (`_cfg_from_dict(..., tiearb=_W.get("cand_tiearb"))`
at the candidate construction site; the flag's own help says *"CANDIDATE side only"*).
There is **no `--opp-tiearb-*` and no opponent path to those fields.** ⇒ **a direct
head-to-head `champion+arb(64)` vs `champion+arb(16)` cannot be launched against the
harness as it stands.** This is a plumbing gap, exactly the class the JCZ cell hit and
recorded ([`jcz_tiearb_20260817/DESIGN.md`](../../jcz_tiearb_20260817/DESIGN.md) §6.1).

**Two ways out. This design takes the first; the second is [§10](#10-open-choices-left-for-the-reviewer)'s
first open choice.**

### 1.2 The design of record — two cells against the unmodified champion, DIFFERENCED

| cell | candidate | opponent | arbiter |
|---|---|---|---|
| **`WIDE`** | champion + arbiter, **`B` = 64** | champion, unmodified | `Ā × 64` playouts per tied ply, **argmax** of the world-mean |
| **`NARROW`** | champion + arbiter, **`B` = 16** | champion, unmodified | `Ā × 16` playouts per tied ply, **argmax** of the world-mean |

Both cells run on the **same fresh band and the same decks**, deck-paired (same deck
played twice, seats swapped). The **PRIMARY** statistic is

```
D = M_WIDE − M_NARROW ,  deck-paired over the decks completed in BOTH cells
```

with `z_D = D / se(D)`, `se(D)` computed the same way as `eval_fair_puct._paired_z`.

**This is Stage 2's own construction with `RND` replaced by `NARROW`.** Stage 2's
`D = M_arb − M_rnd` was computed by the same analyzer over the same artifact shape and
read out at `D` +7.4988, `se_D` 0.9332, `z_D` +8.036, `n_common` 400
([`READOUT.json::D_block`](../../tiearb2_stage2_20260817/READOUT.json)). **No new
statistic and no new instrument is invented here** — only the second cell's `B`.

**Why `NARROW` must be re-run rather than read off Stage 2.** Stage 2's `ARB` cell is the
same configuration on band `132000000000`, and that band is **RETIRED from confirmatory
use**. CLAUDE.md's cross-band humility rule prices cross-band contrasts at **1.8–2.2×
over-dispersion in both statistics** and says *"never pool across bands and quote the pool
as an estimate"*. A `WIDE`-on-a-new-band vs `ARB`-on-132e9 contrast is exactly the
forbidden class. **Within-band deck-paired is the robust class and it is the only one
used here** — which costs a full second cell, and that cost is in [§7](#7-supply-chain-and-cost--every-stage-shown).

### 1.3 ⭐ The CRN is NESTED, and it is the load-bearing structural property of this design

`rust/carc/carc-core/src/tiearb.rs::arbitrate` derives each world's seed as

```
world_seed(j)   = seed_i64([salt, state_digest, ply, j])          for j in 0..B
playout_seed(j) = seed_i64([salt, state_digest, ply, j, "playout"])
```

`j` runs `0..B` and **the seed is a pure function of `j`, never of `B`.** ⇒ at the same
salt, the same position and the same ply, **`B = 64`'s worlds 0..15 are byte-identical to
`B = 16`'s entire world set.** The arm construction (`build_arms`, seeded `["…","cap"]`)
and the `Random`-mode selection stream (`["…","select"]`) likewise do not depend on `B`.

Four consequences, all first-class:

1. **`WIDE` is a strict refinement of `NARROW`, not a different experiment.** `B = 64`
   differs from `B = 16` only where the extra 48 worlds move the argmax. Where they do
   not, the two candidates play the **identical move**, and — both facing the identical
   champion from the identical deck — the **entire game is identical**.
2. ⚠️ **A large identical fraction is a POWER LOSS, not a power win, and this design says
   so before the run.** If a fraction `f₀` of common decks yield `D_i` exactly 0, then
   `mean(D) = (1−f₀)·E[D | differ]` and `sd(D) ≈ √(1−f₀)·sd_differ`, so
   **`z_D ∝ √(1−f₀)`**. A surface that rarely disagrees dilutes the read exactly as
   Stage 2's `phi` floor anticipated for a surface that rarely fires. Hence `G-DIVERGE`
   ([READ_RULE](READ_RULE.md) §3), authored here, before any divergence number exists.
3. **It plausibly raises the cross-cell deck correlation `ρ` well above Stage 2's**
   (Stage 2's `ARB`-vs-`RND` cells diverged on nearly every fired ply; `ρ` back-derived
   from `se_D` 0.9332 against `se` 0.6906 / 0.6641 is **≈ 0.051**). A higher `ρ` shrinks
   `se(D)`. ⛔ **It is NOT banked.** [§6](#6-power--sized-from-stage-2s-realized-dispersion)
   sizes at the conservative `ρ = 0`, per the JCZ precedent (*"We assume nil here and do
   not bank a variance reduction that may not arrive."*). The realized `ρ` is reported.
4. **It gives a free structural witness.** `G-NEST` ([READ_RULE](READ_RULE.md) §3)
   requires a pinned test proving the world-set nesting at HEAD before game 1. If the
   nesting does not hold, `WIDE` and `NARROW` are two unrelated draws and the whole
   "increment" framing is void — so it is a precondition, not a rider.

---

## 2. The two cells

Both candidates are the champion of record (`governance/PRODUCTION.yaml`) with the
arbiter armed. **Every arbiter knob except `B` is EXACTLY the deployed `tiearb2` shape:**

| knob | `WIDE` | `NARROW` | source |
|---|---|---|---|
| `enabled` | true | true | `--cand-tiearb-enabled` |
| **`B`** | **64** | **16** | the only difference |
| `J` | 4 | 4 | deployed |
| `mode` | `argmax` | `argmax` | deployed |
| `salt` | `tiearb2-deploy-v1` | `tiearb2-deploy-v1` | deployed; *"a different salt is a different experiment"* |
| `eps` | 0.0 | 0.0 | deployed — exact f64 equality, **not** a tolerance |
| trigger | TILES phase, own seat, `n_legal ≥ 2`, ≥2 actions sharing the top **outer chain value** at exact f64 equality | identical | deployed |
| champion | `cand_leaf_hash` `a36d2e15a3b3d71d`, k8×1376 = 11,008, exact-K 2, `c_puct` 1.5, `tau_p` 5.0 | identical | `PRODUCTION.yaml` |

`--cand-tiearb-b` is `type=int` with **no `choices` restriction**, and the rust arbiter
loops `for j in 0..b` with no cap ⇒ **`B = 64` requires no code change.** ⚠️ It is
nevertheless *unexercised at 64 in a game*, so `G-J13`'s two-sided positive control is
required **at both `B` values, per host, before that host's game 1**.

### 2.1 The arbiter fails soft — carried from Stage 2, unchanged

A `tier1-greedy` continuation can hit the encoder's window refusal deep inside a world.
The arbiter does not propagate: it falls back to the champion's own `pooled_q_argmax`
pick **at ply granularity** and counts the event. Carried verbatim from Stage 2 §0.E.1,
including its conditions, and with Stage 2's own post-hoc correction attached:

> The arbiter is **deterministic given the position**, so the two cells fail
> **identically wherever they are in the same position**. Once they diverge on a pick
> they are on **different boards** and can therefore fail at **different rates**.
> Symmetry is an empirical near-fact to be **measured**, never an entitlement.

⚠️ **That correction bites harder here than it did in Stage 2**, because `WIDE` runs
**4× the playouts per fired ply** and therefore has ~4× the exposure to the failure
class per ply. Stage 2 realized **1 error in 14,292 fired plies (7.0e-5)** with
`tiearb_partial_argmax_total` **0 across 28,350 fired plies**; at 4× exposure and ~1.9×
the games the naive expectation is still **≪ 1 error per cell**, but the asymmetry is
now *directional* (it favours `NARROW`) and so it is a reported quantity on every branch
and it is bounded by `G-FAILED` ([§8](#8-the-failed-record-bound--authored-before-any-data-exists)).

---

## 3. Existence-time markers — the R5 discipline, applied to a game cell

[`rung3_r5/DESIGN.md`](../rung3_r5/DESIGN.md) §R5-6.1, carried verbatim:

> **Every address in this prereg carries an existence-time marker: `[pre-corpus]`,
> `[post-corpus]` or `[post-scoring]`. Each acceptance pass audits exactly the markers
> that can exist at its point in the sequence — statically against a fixture otherwise.
> No pass may demand an address its own position in the sequence makes impossible, and no
> address may be audited at neither pass.**

A game cell has a different sequence, so the marker set is renamed to fit it. **The rule
is unchanged; only the three labels are.**

| marker | exists from | audited statically at | audited live at |
|---|---|---|---|
| `[pre-run]` | the blind commit / before game 1 | the pre-commit pass | the pre-launch pass |
| `[post-smoke]` | the smoke completes | the pre-commit pass, against a **fixture** | the post-smoke pass |
| `[post-cells]` | both cells complete | the pre-commit pass, against a **fixture** | the read-out |

**The fixture set is not hand-maintained.** R4's failure was a fixture list that covered
the leg manifest and the smoke manifest but **not `RUN_MANIFEST`**, so `G-SALT`'s primary
was audited at neither pass. Here: **the fixture for every `[post-smoke]` and
`[post-cells]` address is Stage 2's own completed artifact of the same name**
(`tiearb2_stage2_20260817/SMOKE.json`, and `summary.json` / `manifest.json` / `seed*.json`
from the completed `ARB` cell), and a **completeness assertion over the marker list**
— not over a fixture list — asserts every marked address is covered. An address carrying
no marker is a **DRAFTING DEFECT** that must be fixed before the blind commit, never
adjudicated at read time.

Marker assignment for this cell's addresses is enumerated in
[`READ_RULE.md`](READ_RULE.md) §2 and §3; the load-bearing ones:

- `[pre-run]` — `WORKERS.conf`, `PREFLIGHT_*_${HOST}_FIRST.json` (both `B` values),
  `GATE_NEST.json`, the `BAND_CLAIM.json` sentinel, `OWNER_WAIVER.md` (if any), the blind
  commit hash.
- `[post-smoke]` — `SMOKE.json` (all cost keys), the HALT decision record.
- `[post-cells]` — `summary.json::{paired_mean_margin, paired_z, n_paired, tiearb_*,
  champ_prefix_ms_per_move, rung_ms_per_move, n_failed}`, `manifest.json::{cand_tiearb,
  config.cand_leaf_hash, config.band_seed_start, carc_rs_build}`, `seed*.json::elapsed_s`,
  and every quantity in the `D` block.

⚠️ **`manifest.json` resolution is a two-level lookup, and Stage 2 lost a whole
adjudication pass to it** (§0.I.2: `G-J1` and `G-BAND` read `null` at the top level while
the witnesses sat correct under `config.`). Every manifest address in this pair is
specified as **"top level, else under `config.`, and the read-out prints which was
found"** — hygiene, and the gate still fails closed if the value is absent under both.

---

## 4. The cost facts, stated before the run — and B = 64 is ABOVE the affordability bar

Carried from [`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §5, verbatim, table and all:

| rung | `rho_wall` (sequential; N4 bar 1.20) | contended in-cell `ms_ratio` (projected) | `rho_phone` |
|---|---|---|---|
| B = 16 | **0.6224** ✅ | **2.42 realized** (Phase B) | 5.976 |
| B = 32 | **1.2449** ❌ (fails by 3.7%) | ≈ **3.75** | 11.95 |
| B = 64 | **2.4897** ❌ (2.07× the bar) | ≈ **6.50** | 23.90 |

> ⚠️ **The two currencies are NOT the same number** (Stage 2 §0.G — that equation is
> withdrawn). The projection above scales only the *arbiter* term of Phase B's realized
> split (candidate 4383.6 ms/move, opponent 1808.2 ⇒ arbiter ≈ 2575 ms/move at B=16) and
> **must be re-measured, never inferred.** `rho_phone` is a third currency again; the
> phone is out of scope for this rung and B>16 is dead there regardless.

Three things follow, all pre-registered:

1. **`rho_wall(64)` = 2.4897 is a committed arithmetic constant, not a measurement to
   come.** Phase A measured `rho_wall(16)` = 0.6224 and the arbiter's cost is **exactly
   linear in `B`** (`for j in 0..b`, `Ā` arms per world, one `tier1-greedy` playout each).
   ⇒ **`B = 64` fails the house N4 affordability bar by 2.07× and this is known before
   game 1.**
2. ⇒ **On a win, the branch that fires is `B-COSTKILL`, not `B-CONFIRMED`, unless a fresh
   owner wall-clock waiver covering `B > 16` is on the record before game 1.** That is why
   `A` in [READ_RULE](READ_RULE.md) §4 is a **disjunction** with a committed-file
   condition, and why `OWNER_WAIVER.md` is a `[pre-run]` address. Stage 2's §0.D waiver
   **does not carry** — its own anti-gaming clause explicitly bounded it at `B = 16`
   ([§0.4](#04-the-stage-2-anti-gaming-clause-is-not-being-violated--stated-so-nobody-has-to-wonder)).
   The question is [`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §6 open question 3, verbatim:
   *"Does the N4 `rho_wall ≤ 1.20` waiver … extend above `B = 16`? … worth settling
   **before** the prereg, not after."* **It is still unsettled and it must be settled
   before the blind commit.**
3. **`rho_phone(64)` = 23.90 ⇒ on-device is dead at this rung by a factor of ~20, and no
   branch may say otherwise.** ⚠️ Disclosed disagreement between two committed documents:
   `PLAN_B_gt_16.md` carries `rho_phone(16)` = **5.976** while Phase A / Stage 2 carry
   **5.520** (`COST_REMEASURE.json:ladder_primary_w30.rungs.16.rho_phone`), so the
   ×4 figure is either **23.90 or 22.08** depending on which is used. **Both are printed;
   neither is adjudicated; the phone is a third currency and out of scope either way.**

---

## 5. The effect size we are trying to detect — and the 3.9× translation caveat binds BOTH ways

### 5.1 The caveat, carried verbatim and in full

[`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §5:

> ⚠️ **The offline→game translation factor is not established.** Stage 1b's +0.1441
> pts/tied ply predicts +0.79 pts/game (`× phi 17.57 / non_additivity 3.2`); Phase B
> realized **+3.07** — a **3.9× under-prediction**. So Δ(16→64) = +0.064 maps to anywhere
> from +0.35 (naive) to +1.4 (realized-ratio) pts/game. A deck-paired `B=64` vs `B=16`
> cell resolves +1.4 pts/game at n ≈ 800/cell but needs n ≈ 12,500 for +0.35. **Sizing it
> before the offline read would be guessing at the top of a 4× uncertainty.**

[`docs/LEVER_INDEX.md`](../../../docs/LEVER_INDEX.md) §6, `B > 16` row, on the direction
of the caveat:

> ⚖️ **A B=64 GAME CELL IS AN OWNER DECISION and is not scheduled** — CAMPAIGN ruling 5
> binds **in BOTH directions**: Stage 1b's offline read **under-predicted** the Phase B
> game cell **3.9×** (+0.79 predicted vs +3.07 realized pts/game), so the offline→game map
> is unestablished and **+0.0670 × 3.9 is not a projection either**.

⭐ **Restated so no read-out can soften it: the 3.9× is a MEASURED MISS of an unvalidated
map, in one direction, at n = 1. It licenses a WIDTH, not a CENTRE.** This design uses it
to set a **bracket** and refuses to use it as a multiplier.

### 5.2 The bracket, re-derived at the final `Δ` (PLAN_B used the pre-final +0.064)

```
Δ(16→64)                            = +0.0670  pts/tied ply   MEASURED (W-RISING)
phi (realized fired tied tile plies/game, Stage 2 ARB cell) = 17.5725   MEASURED
NON_ADDITIVITY                      =  3.2      (n = 1, +-1.6x bracket — NOT a point)

naive floor       = 0.0670 x 17.5725 / 3.2      = +0.368 pts/game
realized-ratio    = 0.368 x 3.9                 = +1.435 pts/game
```

⇒ **the plausible effect lies in `[+0.368, +1.435]` pts/game, a 3.9× band.** ⛔ **Neither
endpoint is a projection.** The offline ratio `arb64/arb16` = 0.2015 / 0.1345 = **1.498**
is reported because the brief asks for it and because it is the cleanest one-number
statement of "the ladder still pays" — ⛔ **and it is NOT a projection of the game effect
either.** It is a ratio of two offline per-tied-ply oracle prices on a selected 1,340-ply
corpus; the map from that currency to game points is precisely what the 3.9× says is
unestablished, and a ratio of two unestablished-map quantities is not more established
than either.

---

## 6. Power — sized from Stage 2's REALIZED dispersion

### 6.1 The dispersion we are entitled to assume — measured, with its path

From [`tiearb2_stage2_20260817/READOUT.json`](../../tiearb2_stage2_20260817/READOUT.json),
which is the **same population** this cell measures (champion + arbiter vs the unmodified
champion, deck-paired, production budget):

```
cells.ARB.recomputed.se  = 0.6906057781774855   over n_decks 400
  => per-deck paired sd  = 0.6906057781774855 x sqrt(400) = 13.812  pts   <-- THE SIZING CONSTANT
cells.RND.recomputed.se  = 0.6640859480970063   over n_decks 400
  => per-deck paired sd  = 13.282  pts          (a 3.8% corroboration, different candidate)
D_block.se_D             = 0.9331534557744559   over n_common 400
  => implied cross-cell deck correlation rho = 0.051   (ARB vs RND; NOT this cell's rho)
```

**`sd = 13.812` pts per deck is the sizing constant of record.** It is measured on this
exact configuration, at this exact budget, on 400 deck-paired decks. `RND`'s 13.282
corroborates it to 3.8% across a *different candidate*, which is what licenses quoting it
as a property of the population rather than of one cell.

### 6.2 What `n` buys, at the conservative `ρ = 0`

```
se_cell(n_decks) = 13.812 / sqrt(n_decks)
se(D) | rho = 0  = sqrt(2) x se_cell
2-sigma floor    = 2 x se(D)
```

| n games/cell | decks/cell | `se_cell` | `se(D)` | **2σ floor (pts/game)** | worker-h | 2-box wall |
|---|---|---|---|---|---|---|
| 800 | 400 | 0.6906 | 0.9766 | +1.953 | 308.5 | 7.1 h |
| 1,000 | 500 | 0.6177 | 0.8735 | +1.747 | 385.7 | 8.8 h |
| 1,200 | 600 | 0.5638 | 0.7974 | +1.595 | 462.8 | 10.6 h |
| ⭐ **1,500** | **750** | **0.5044** | **0.7133** | **+1.427** | **578.5** | **13.2 h** |
| 2,000 | 1,000 | 0.4368 | 0.6177 | +1.235 | 771.3 | 17.7 h |

*(worker-h and wall from [§7](#7-supply-chain-and-cost--every-stage-shown); wall carries
the measured 1.19× occupancy derate.)*

**COMMITTED: `n` = 1,500 deck-paired games per cell = 750 decks per cell.**

**Why 1,500, derived and justified rather than chosen:** the floor is set to just clear
the **top of the §5.2 bracket**, which is the only part of the bracket this programme can
afford to resolve. At `n` = 1,500 the 2σ floor is **+1.427** against a bracket top of
**+1.435** ⇒ a realized-ratio-sized effect reads **`z_D` ≈ 2.01** and convicts by a hair.
Anything smaller cannot convict even the optimistic end; anything larger buys ground in
the middle of the bracket at ~1.3 h per 0.05 pts of floor.

### 6.3 ⚠️ What this cell CANNOT do — stated before it runs

- **It cannot exclude the naive floor.** Convicting `D` = +0.368 at 2σ needs
  `se(D) ≤ 0.184` ⇒ **n ≈ 11,270 decks/cell = 22,540 games/cell ≈ 8,693 worker-h ≈ 199 h
  of two-box wall.** ⇒ **a null here is a BOUNDED null at |D| < 1.427 pts/game, roughly
  the top 74% of the bracket, and it does NOT refute `W-RISING`** (different currency,
  different estimand, different population). The read-rule's `B-FLAT` branch carries that
  sentence as mandatory text so it cannot be narrated away afterwards.
- **It cannot resolve the ladder's SHAPE.** `W-RISING` already declined to
  ([§0.3](#03--the-scope-fence-on-w-rising-itself-carried-verbatim)); two points in game
  points resolve even less. No branch may say "B = 64 is the optimum" or "the ladder
  saturates".
- **It cannot license an on-device deploy** ([§4](#4-the-cost-facts-stated-before-the-run--and-b--64-is-above-the-affordability-bar) item 3).

### 6.4 ⚠️ DISCLOSED CONTRADICTION with a prior committed number — resolved here, before the run

[`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §5 states *"A deck-paired `B=64` vs `B=16` cell
resolves +1.4 pts/game at n ≈ 800/cell"*. **That figure is not reproducible from Stage 2's
realized dispersion and it is superseded by §6.2.** House rule: *"A new result that
contradicts a prior one is not a discovery until the contradiction is resolved."*

**The resolution:** +1.4 / 0.6906 = 2.03, i.e. PLAN_B graded the effect against the
**single-cell** `se` (0.6906 at 400 decks) rather than against `se(D) = √2 × se_cell`
(0.9766). **The √2 for differencing two independently-sampled cells was omitted.** At
n = 800 games/cell the true `z_D` for a +1.435 effect is **1.47, not 2.03** — it does not
convict. PLAN_B's companion figure *"needs n ≈ 12,500 for +0.35"* is likewise a
single-cell-`se` figure and is superseded by §6.3's 11,270 **decks** (22,540 games).
⇒ **the R3.3 lesson applied to power rather than supply: re-derive, do not inherit.**

### 6.5 The `ρ` upside — reported, never banked, and never allowed to move `n`

[§1.3](#13--the-crn-is-nested-and-it-is-the-load-bearing-structural-property-of-this-design)
argues the nested CRN plausibly gives `ρ ≫ 0.051`. If it does, `se(D) = sd·√(2(1−ρ))/√n`
and the realized floor drops (at `ρ` = 0.5 the n = 750-deck floor would be **+1.044**).

⛔ **`n` is fixed at the `ρ` = 0 figure and is NOT revised by the smoke or by anything
else.** Revising `n` from a measured divergence rate would be sizing on data correlated
with the effect — the exact pattern the blind-ordering discipline exists to prevent. The
smoke may **halt** the run on cost ([§9](#9-the-pre-registered-benchsmoke-step)); it may
never **resize** it. The realized `ρ` and the realized `se(D)` are reported on every
branch, and the read-out prints the realized floor beside the committed one.

---

## 7. Supply chain and cost — every stage shown

**The R3.3 miss class is supply arithmetic that was inherited rather than re-derived**
([`PREREG_FAILURE.md`](../PREREG_FAILURE.md) §2: *"§3's yield table treated raw census
rows as final supply"*, a 27× miss). Every stage below is re-derived from a MEASURED
integer with its path; back-derived factors are marked `≈` and are never load-bearing.

### 7.1 The measured cost primitives

All from the completed Stage-2 `ARB` cell (band 132e9, 800 games, W_local 30 +
W_laptop 22), read off `/mnt/c/carc-shared/tiearb2_stage2_20260817/tiearb_ARB_B16J4_deploy11008/`:

```
sum over seed*.json of elapsed_s / 800   =  429.612  worker-s/game   MEASURED (whole cell, B=16)
summary.json::tiearb_secs_per_game       =  176.394  worker-s/game   MEASURED (arbiter term only)
summary.json::tiearb_phi                 =   17.5725 fired tied tile plies/game   MEASURED
summary.json::tiearb_playouts_total      =  737,952                  MEASURED
summary.json::tiearb_fired_plies_total   =   14,058                  MEASURED
summary.json::tiearb_secs_total          =  141,115.434 worker-s     MEASURED
```

### 7.2 The derived chain — each line one arithmetic step from the line above

```
playouts per fired ply, B=16   = 737,952 / 14,058          =  52.4862      DERIVED
  => A_bar (arms per fired ply) = 52.4862 / 16             =   3.2804      DERIVED
     (Phase A's corpus constant was 3.0022; realized in-cell is +9.3% — REPORTED,
      not reconciled, and not load-bearing: the chain below never uses A_bar,
      it uses the measured seconds.)
c_incell (worker-s per playout) = 141,115.434 / 737,952    =   0.191225    DERIVED
  (Phase A's W=30 figure was 0.178232 — realized in-cell is +7.3%.)

arbiter per fired ply, B=16    = 176.394 / 17.5725         =  10.0381 worker-s   DERIVED
arbiter per fired ply, B=64    = 4 x 10.0381               =  40.1524 worker-s   DERIVED
  ⭐ the x4 is EXACT, not an estimate: rust/carc/carc-core/src/tiearb.rs::arbitrate
     runs `for j in 0..b` with one tier1-greedy playout per (world, arm), so the
     playout count is A_bar x B and the cost is strictly linear in B.

base game cost, arbiter removed = 429.612 - 176.394        = 253.218 worker-s/game DERIVED

NARROW per game = 253.218 + 17.5725 x 10.0381  = 429.612 worker-s   (identity check: = the measured cell)
WIDE   per game = 253.218 + 17.5725 x 40.1524  = 958.794 worker-s   (= 2.232 x NARROW)
```

⚠️ **`phi` is assumed EQUAL across the two cells and that assumption is stated, not
hidden.** The trigger predicate does not depend on `B`, so `phi` should be
`B`-invariant *at the same position*; but the two cells diverge onto different boards, so
the realized `phi` can differ, exactly as Stage 2's `ARB` 17.5725 vs `RND` 17.865 (+1.7%)
did. **The cost projection therefore carries a ±2% `phi` uncertainty**, which is inside
the §9 HALT bar by a wide margin and is reported at the smoke.

### 7.3 The supply chain — games to adjudicable decks

```
committed n per cell                            1,500  games       DESIGN §6.2
  --paired => decks per cell = n // 2             750  decks       eval_fair_puct.py:3924
  same band + same seed range in both cells  =>   750  COMMON decks by construction
  G-N completion floor, 80% (Stage 2's amended bar, carried)
      games  floor per cell = 0.80 x 1,500      1,200  games
      decks  floor (n_common)                     600  decks       (= 1,200 games, the SAME 80% bar
                                                                     re-expressed in decks — Stage 2 §0.B)
  G-FAILED bound (DESIGN §8)                    <= 2%  of attempted, per cell
```

⚠️ **The two `G-N` clauses must agree in units.** Stage 2's committed text read
`n_common < 600` **decks** against a 400-deck ceiling and was **unreachable by
construction** — a rule that could only ever return `U-UNREADABLE` (§0.A/§0.B). Here the
deck floor (600) and the game floor (1,200) are the **same 80% bar** expressed in the two
units, and the deck clause remains independently binding (two cells can each clear 1,200
games while overlapping on fewer than 600 *common* decks).

### 7.4 The bill

```
NARROW  1,500 games x   429.612 worker-s  =    644,418 worker-s
WIDE    1,500 games x   958.794 worker-s  =  1,438,191 worker-s
TOTAL                                     =  2,082,609 worker-s  =  578.5 worker-h
```

**Two-box wall.** `W_LOCAL` 30 + `W_LAPTOP` 22 = **52 concurrent workers**, both cells
worked concurrently under `--shared-claim` (the Stage-2 arrangement, `WORKERS.conf`):

```
ideal at full occupancy   = 2,082,609 / 52   = 40,050 s  = 11.13 h
occupancy derate  x1.19                      = 47,660 s  = 13.24 h   <-- COMMITTED
```

**The 1.19 derate is measured, not assumed.** Stage 2's `SMOKE.json::eta_for_the_real_cells`
projected `BOTH_CELLS.eta_hours` **4.41 h** from per-box `games_per_sec` measured at
production knobs; the realized worker-seconds of the two cells
(343,689.685 + 350,061.865 = 693,751.55) over 52 workers give an ideal of **3.706 h**.
⇒ realized-throughput-to-ideal = 4.41 / 3.706 = **1.190**. That factor is what the smoke
measures again ([§9](#9-the-pre-registered-benchsmoke-step)), in this cell's own currency.

**Plus, not in the 13.24 h:** the smoke (≈0.6 h, §9), the per-host preflights and the
`G-NEST` test (minutes), and the git-bundle sync before the two-box launch.

⇒ **COMMITTED PROJECTION: ≈ 578.5 worker-h, ≈ 13.2 h of two-box wall, ≈ 14 h door-to-door.**

---

## 8. The failed-record bound — authored BEFORE any data exists

[`DEVIATIONS.md`](../DEVIATIONS.md) **D4.18** declined a post-hoc numeric bound and
required, verbatim:

> 3. **A pre-registered failed-record bound is carried to `rung3_r5`** — authored
>    **before** its data, which is the only way a bound of that shape is worth anything.

**That obligation is discharged here, for this cell, in three clauses.** All three are
authored before the band is claimed, before the smoke, and before one game of this cell
exists. Where a prior run's realized figure informs the *shape*, it is named — a figure
from a **different** run is a prior, not the datum being graded, which is exactly the
distinction D4.18 turns on.

**`G-FAILED`, all three clauses; any one fires ⇒ `U-UNREADABLE`:**

1. **RATE, not count.** `n_failed / n_attempted > 0.02` in **either** cell.
   *Shape justification (R5-1.2's lesson: a bound as a fraction of `n` shrinks with the
   floor while the failure rate does not — so the bound is written in the **rate**, which
   is scale-free, and any absolute count is derived from it, never committed).
   Level justification, from priors on DIFFERENT runs: Stage 2 realized 0/800 and 0/800;
   the JCZ cells realized `n_failed` 0 in both cells. A 2% bar is ≈30 games in a
   1,500-game cell against a realized prior of **zero** ⇒ it fires only on a regime
   change, never on ordinary attrition. It is deliberately generous: its job is to catch
   a broken run, not to grade a good one.*

2. ⭐ **CANDIDATE-CORRELATION, which is the failure that actually threatens `D`.** Let
   `F_w`, `F_n` be the two cells' failed-game counts. Fires if
   **`max(F_w, F_n) ≥ 5` AND `max(F_w, F_n) > 3 × max(min(F_w, F_n), 1)`.**
   *Justification: a failure rate that differs between the cells makes the exclusion
   **candidate-correlated** — the `capoff` pattern — and biases `D` in an unknown
   direction, which is far worse than a diluted effect. The `≥ 5` floor is there because
   a bare ratio rule would have voided Stage 2's perfectly good run on its realized
   **1-vs-0** split; that miscalibration is known from a different run and is designed
   around here rather than discovered here. ⚠️ `WIDE` carries ~4× the per-ply exposure to
   the window-refusal class, so this clause is the one most likely to bind, and it binds
   in the direction that protects the reading.*

3. **QUALITATIVE ESCALATION, which does not grade any observed value.** **Any** failed
   game whose diagnostic class is **not** the known `WindowTruncationError` class ⇒
   **RAISE and escalate, regardless of count**, and the run is `U-UNREADABLE` until
   adjudicated. *D4.18's own words: "A novel failure class is a different question from a
   studied instrument limitation, and count is the wrong axis for it."* Study of record:
   `measurement/window_truncation_20260813/`.

**Mandatory reporting, on every branch including the passing ones:** `n_failed` and
`n_attempted` per cell, the realized rate against the 2% bar, `F_w` vs `F_n` against
clause 2, the diagnostic class of every failure, `tiearb_errors_total`,
`tiearb_error_rate_on_fired`, `tiearb_first_error`, `tiearb_partial_argmax_total`, and
`phi_effective` beside `phi`. **And the D4.18(c) selection-effect sentence, adapted:**
window-truncation failures fire at extreme board extents, so any dropped set is
**correlated with board geometry** — late-game, large-extent positions — and that
correlation is **disclosed rather than argued away**.

---

## 9. The pre-registered bench/smoke step

**No games of the real cells may start until the smoke has run and its HALT bar has been
evaluated.** This is the house c-remeasure pattern
([`c_remeasure_r4/`](../c_remeasure_r4), Stage 2 `SMOKE.json`), and it exists because
`B = 64` is the first time the arbiter is run at this width **in a game**.

### 9.1 What the smoke runs

Both cells, **at production knobs** — same champion, same `k8×1376`, same exact-K 2, same
`--paired --shared-claim`, same `nice 19`, same `W_LOCAL` / `W_LAPTOP`, same rust
toolchain — **only the game count differs.** `N_SMOKE` = **24 games per cell per box**
(Stage 2 used 22; 24 is the smallest multiple of both worker counts' rough duty cycle
that still lands ≥ 1 full pass per worker). Throwaway band **`900000300000`**, which is
outside the `governance/BAND_REGISTRY.csv` allocation range, is **never claimed**, and
**does not touch the cell band**.

*(Precedent: Stage 2's smoke used `900000100000` on the same terms.
`900000300000` is unused anywhere in `measurement/`.)*

### 9.2 ⛔ COUNTS-AND-COST ONLY — the smoke may not read an outcome

The smoke reads and prints **only**: `wall_secs`, `secs_per_game`,
`worker_secs_per_game`, `games_per_sec`, `workers`, `champ_prefix_ms_per_move`,
`rung_ms_per_move`, `ms_ratio_cand_over_opp`, `tiearb_phi`,
`tiearb_fired_plies_total`, `tiearb_tile_plies_total`, `tiearb_fire_rate_on_tile_plies`,
`tiearb_pickchange_rate`, `tiearb_mean_arms`, `tiearb_playouts_total`,
`tiearb_secs_per_game`, `tiearb_errors_total`, `tiearb_first_error`,
`tiearb_partial_argmax_total`, `cand_leaf_hash`, `carc_rs_build`, `carc_rs_binary_sha`,
`rust_toolchain`, `n_failed`.

⛔ **It may not read, compute, print or store `paired_mean_margin`, `paired_z`, `elo`,
`winrate`, `W`/`D`/`L`, or any per-deck margin.** The smoke driver's emitter is
whitelisted to the keys above and **must fail closed on an unlisted key**. This is the
counts-only non-leaking class [`PREREG_FAILURE.md`](../PREREG_FAILURE.md) §3.3
established, and it is what lets the smoke run **before** the blind commit is spent
without spending blindness.

⚠️ **`f₀` (the identical-deck fraction) is a MARGIN-DERIVED quantity and is therefore
FORBIDDEN at the smoke.** It is measured in-cell only, at the read-out. Naming it here so
a well-meaning implementation cannot add it to the smoke "because it's just a count".

### 9.3 The HALT bar — one-sided, on realized-vs-committed cost

```
COMMITTED PROJECTION (DESIGN §7.2):  WIDE = 958.794 worker-s/game
HALT BAR:                            realized WIDE worker_secs_per_game  >  1.50 x 958.794
                                                                          =  1,438.2 worker-s/game
```

**One-sided by construction: an overrun HALTS, an underrun proceeds.** On a HALT the real
cells are **not launched**, the smoke numbers and the projected revised bill are reported,
and the decision returns to the owner. No re-tuning of `B`, the trigger, `J`, `eps` or the
playout is licensed by a HALT — the only permitted responses are *stop*, or *the owner
re-funds at the realized cost*.

**Why 1.50, derived and justified pre-data.** Stage 2's cost model missed the in-cell
`ms_ratio` by ~2× — but §0.G decomposed that miss and found **the numerator model was
right within 11.8%** (8.561 predicted vs 9.57 realized worker-s per fired ply) and the
**denominator was a currency error** (a sequential `t_champ` divided into a contended
per-move wall, ≈8× apart). ⇒ **the historical error class does not apply here**, because
§7.2 projects entirely in the **numerator's own currency** (worker-s per game, measured
in-cell, contended, at these worker counts) and never divides by a sequential quantity.
A 1.50× bar is **≈4× the largest error this currency has on record**. It is deliberately
loose: its job is to catch a regime change (a 4× playout increase behaving
super-linearly, a memory-pressure cliff at `W` 30 with 4× the scratch), not to grade a
15% modelling error.

### 9.4 Prediction vs realized — printed, never graded

The smoke prints, side by side and on every outcome:

| quantity | committed prediction | realized |
|---|---|---|
| `WIDE` worker-s/game | **958.794** (§7.2) | measured |
| `NARROW` worker-s/game | **429.612** (§7.2, = the Stage-2 measured cell) | measured |
| `ms_ratio` `WIDE` | **≈ 6.50** ([PLAN_B](../PLAN_B_gt_16.md) §5) | measured |
| `ms_ratio` `NARROW` | **≈ 2.42** (Stage 2 realized) | measured |
| `phi` both cells | **17.5725** (Stage 2 realized) | measured |
| occupancy derate | **1.190** (§7.4) | measured |

⚠️ **Only the first row is graded (§9.3). The rest are printed because a wrong cost model
should stay visible even where no bar is enforced** — Stage 2 §0.G's discipline, and the
reason that miss was ever found. ⚠️ **The field-name trap travels with the `ms_ratio`
rows: `champ_prefix_ms_per_move` IS THE CANDIDATE SIDE in `eval_fair_puct`** (live lines
2361/2371/2389). A read-out that swaps them inverts the cost verdict.

⚠️ **The real cells' `ms_ratio` is NOT graded against the smoke's.** Both are printed and
neither grades the other — Stage 2 §0.H, carried: a bar written after a smoke number
exists is not a bar, and `ms_ratio` is not a branch input anywhere in this pair.

---

## 10. Open choices left for the reviewer

**None of these is settled by this draft, and the pair must not be blind-committed on
`main` until they are.**

1. ⭐ **THE SHAPE OF THE CONTRAST — two differenced cells (§1.2, this draft) vs one
   head-to-head cell behind a new `--opp-tiearb-*` knob.** This is the biggest lever on
   the bill and I have deliberately not taken it. The arithmetic, so the reviewer decides
   against numbers:

   | | this draft (two cells, differenced) | head-to-head (needs a W-item) |
   |---|---|---|
   | new code | **none** | `--opp-tiearb-*`: `make_production_champion` / opponent factory / manifest / a second two-sided positive control |
   | per game | 429.612 + 958.794 = 1,388.406 worker-s across two cells | 253.218 + 176.394 + 705.6 = **1,135.2** worker-s in one cell |
   | statistic | `D = M_w − M_n`, `se(D) = √2 · se_cell` at `ρ` = 0 | the paired margin **directly** — no √2, and the two agents are near-identical so the per-deck sd is plausibly far smaller |
   | sd | **known** (13.812, measured) | **unknown** — no measurement of this population exists; would have to be measured at the smoke, and sizing `n` from it is sizing on data |
   | precedent | Stage 2's `D`, JCZ's `D`, same analyzer | none in this programme |
   | risk | 2× the games | a new instrument on the **opponent** side, where a bug is invisible to `G-J1`-style candidate gates |

   **My recommendation, and it is only a recommendation:** take this draft's shape for the
   first cell. The head-to-head is probably cheaper *and* stronger, but it buys that with
   an unmeasured dispersion and a new opponent-side instrument, and the programme's two
   most expensive recent losses (R3.3, S2) were both *design-shape* failures rather than
   power failures. If the reviewer prefers the head-to-head, **it needs a fresh pair** —
   this read-rule does not transfer.

2. ⭐ **THE N4 WAIVER ABOVE `B = 16` — unsettled, and it decides whether `B-CONFIRMED` is
   reachable at all.** [`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §6 asked it and it was
   never answered: *"Does the N4 `rho_wall ≤ 1.20` waiver … extend above `B = 16`? …
   worth settling **before** the prereg, not after."* `rho_wall(64)` = 2.4897 fails by
   2.07×. **Without a dated `OWNER_WAIVER.md` committed before game 1, a win fires
   `B-COSTKILL` and licenses nothing deployable** (§4 item 2, [READ_RULE](READ_RULE.md)
   §4). I have deliberately **not** assumed the waiver extends — the delegation covers
   drafting, not moving a cost bar the owner set.

3. **`n` = 1,500 games/cell at ≈13.2 h of two-box wall.** The §6.2 ladder is priced at
   five rungs. 1,500 is the smallest that can convict the top of the §5.2 bracket. If
   ≈13 h is too much wall, 1,200 (≈10.6 h, floor +1.595) is the next honest rung and it
   **cannot** convict the bracket top — that trade should be taken with eyes open, not
   discovered in the read-out.

4. **Whether `B = 32` belongs in this run.** `Δ(16→32)` = +0.0597 is 89% of `Δ(16→64)`
   at **half** the cost, and `rho_wall(32)` = 1.2449 misses the N4 bar **by 3.7%** rather
   than by 2.07× — i.e. `B = 32` is the rung that could plausibly *deploy*. A third cell
   costs +694,000 worker-s (+4.4 h wall) and would make the read a 3-point ladder in game
   points. ⛔ **I have left it out** — a third cell needs its own branch structure
   (pairwise contrasts multiply, and the `+2.0` bar is not multiplicity-corrected
   anywhere in this programme), and adding it silently would be a design change dressed as
   a rider. **But it may be the higher-EV run and the reviewer should weigh it.**

5. **`G-DIVERGE`'s floor (0.10).** Authored pre-data at 10% of common decks showing any
   divergence, by analogy to `G-FIRE`'s inertness role. There is **no prior measurement**
   of the `B=16`-vs-`B=64` pick-disagreement rate in a game — the offline corpus has a
   pick-churn-per-doubling number that was *reported and never a branch input*. A second
   drafter should sanity-check 0.10 against that number **before** the commit, since after
   the smoke it is too late (and the smoke may not measure it anyway, §9.2).

6. **The smoke's `N_SMOKE` = 24/cell/box** and the throwaway band `900000300000`. Both are
   mechanical; both are cheap to change; neither is load-bearing.

---

## 11. Threats — stated before the numbers

1. **Dilution by agreement is the headline threat, and it is new to this cell.** The
   nested CRN means most plies may resolve identically, and `z_D ∝ √(1−f₀)`
   ([§1.3](#13--the-crn-is-nested-and-it-is-the-load-bearing-structural-property-of-this-design)).
   `G-DIVERGE` refuses an inert surface; nothing rescues a merely-thin one, and §6.3's
   bounded-null language is where that lands.
2. **The effect bracket spans 3.9× and this cell can only reach its top**
   ([§5](#5-the-effect-size-we-are-trying-to-detect--and-the-39-translation-caveat-binds-both-ways),
   §6.3). A null is bounded, not an exclusion, and specifically **does not refute
   `W-RISING`**.
3. **`B = 64` is above the affordability bar before the run starts** (§4). A win may be
   unbuyable. `B-COSTKILL` exists precisely so that outcome has a name written in advance.
4. **4× exposure to the window-refusal class in `WIDE` only** — a candidate-correlated
   exclusion risk that Stage 2 did not face at this magnitude. `G-FAILED` clause 2 (§8).
5. **Cross-band humility does not apply within this run** (one band, one deck set) — it
   **does** apply to any comparison of these numbers against Stage 2's band-132e9 figures,
   and **no such comparison is a branch input anywhere.**
6. **`NARROW` is a fresh-band replicate of Stage 2's `G-CONFIRMED` result and will be read
   as one.** It is reported; it is **not** a branch input; and **no branch re-adjudicates
   Stage 2**, whose read-rule is spent and whose band is retired.
7. **The cost model has missed before** (Stage 2 §0.G, ~2× on `ms_ratio`). §9.3 grades the
   projection in the currency where that miss did *not* occur, and §9.4 prints the rest.

---

## 12. Governance

- **This cell plays games.** On a terminal branch it writes: an `experiments/results.csv`
  row **per cell** plus one for `D`, the `governance/BAND_REGISTRY.csv` claim flipped from
  `pending` to the realized `decision_influenced`, and a claim id in
  `governance/CLAIM_REGISTRY.csv`.
- **The band is claimed at claim time, from the registry, and is NOT named in this
  draft.** Procedure, committed here: run
  `scripts/classical_search/claim_next_band.py --tier claim --label <this run>
  --evidence measurement/tiearb_widening_20260817/b64_cell/DESIGN.md --notes <…>
  --sentinel <idempotent resume sentinel>` **immediately before game 1**, with
  `decision_influenced=pending`. The script takes the lowest step-aligned band strictly
  above the registry high-water mark, never a gap. ⇒ **the band number is whatever the
  registry says at claim time**, both cells draw `<band>..<band+749>`, each deck played
  twice with seats swapped, and the band **retires from confirmatory use** at close-out.
  ⛔ Naming a band in this draft would pre-empt a registry the reviewer has not read.
- **`governance/PRODUCTION.yaml` is untouched on EVERY branch.** No branch flips the
  deployed `B = 16` / `J = 4` shape; the most any branch does is license a **decision for
  the owner**.
- **No branch re-reads, re-labels or re-adjudicates** Stage 1, Stage 1b, Phase A, Stage 2
  Phase B, or the R4 widening run. They stand as adjudicated; their read-rules are spent
  and their bands retired.
- **Close-out is the six-touch checklist in one sitting**: `results.csv` rows → DECISIONS
  index line → status banner on this doc → governance row flips
  (`BAND_REGISTRY` / `CLAIM_REGISTRY`) → STATUS top block → roadmap line. Then
  `python3 scripts/doc_lint.py` clean. [`docs/LEVER_INDEX.md`](../../../docs/LEVER_INDEX.md)
  §6's `B > 16` row is amended at close (it currently ends *"A B=64 GAME CELL IS AN OWNER
  DECISION and is not scheduled"*).
- **Launch discipline: launch → verify → report → STOP.** The completion watch belongs to
  the orchestrator; the `DONE_<cell>` / `FAILED_<cell>` marker convention is written into
  the progress log and handed over explicitly. Detach every run (`setsid` / `nohup … &
  disown`); the harness's background flag alone is not enough.
- **Worktree isolation.** This draft was authored in a git worktree. Any source edit the
  cell needs (there should be none — §2) merges at a quiet window after a process census
  on every box, never beside a live run.
