> ⛔→✅ **FROZEN 2026-08-23 (the blind commit is THE COMMIT THAT INTRODUCES THIS
> BANNER, on branch `carcasum-rung2-freeze`, cut from `carcasum-match-freeze`).**
> `WORKERS.conf::BLIND_COMMIT` cannot be stamped with this commit's own sha inside this
> same commit — a commit cannot name its own hash before it exists, git-mechanically —
> so it stays the literal placeholder `PENDING` in this commit, exactly as rung 1's own
> `b32v64_cell/WORKERS.conf` did at its freeze. A small follow-up commit stamps the real
> sha (the `71b3286c` → `7fd9c8de` precedent in this repo's own history) BEFORE any real
> launch; `run_cells.sh` refuses to run a real rung while it reads `PENDING`
> (`--dry-run` and the G-MODE smoke are exempt — see `run_cells.sh` itself). No
> statistic of any kind exists on band `143000000000` at freeze time.

# READ_RULE — Carcasum rung-2 budget ladder

> **⚠️ BLIND ORDERING.** This file is committed BEFORE the band is claimed, BEFORE game
> 1, and BEFORE any rung-2 statistic exists. The branch that fires is taken
> **VERBATIM**, whatever it is. Owner authorization funds the cell and does not name
> its answer — same discipline as rung 1's `PREREG.md` §5 and `track_d2_prep`'s
> `READ_RULE.md` §0.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `carcasum_rung2_prep`. Analyzer:
> [`../../scripts/carcasum_match/analyze_ladder.py`](../../scripts/carcasum_match/analyze_ladder.py).

---

## §1 — THE STATISTIC, NAMED BEFORE IT EXISTS

**Per rung** (rung 0 = r1's already-collected corpus; rungs A/B/C = this cell's new data):

```
M_rung   = deck-paired margin (champion - Carcasum), pts/game, over the rung's own decks
SEM_rung = paired standard error of M_rung
x_rung   = log2(realized median opponent playouts/turn for that rung)
           rung 0: computed from the FULL r1 corpus (measured, = 14.9904)
           rungs A/B/C: log2(m) EXACTLY (16, 17, 18) -- the pilot G-MODE gate (§3)
           licenses treating the assigned m as the realized median to within noise
```

**Ladder-level primary:** weighted least squares of `M_rung` on `x_rung`, weights =
`1/SEM_rung²`, across the (≤4) points that pass §3's preconditions.

```
beta1 (slope, pts/game per log2-playouts-octave)
beta0 (intercept)
se(beta1), se(beta0), cov(beta0, beta1)   -- from the WLS normal equations
z_slope = beta1 / se(beta1)

x*  = -beta0 / beta1                       (crossover, log2 playouts)
Var(x*) = (1/beta1^2) * [Var(beta0) + x*^2 * Var(beta1) + 2*x* * Cov(beta0,beta1)]
          (delta method on the ratio -beta0/beta1)
se(x*)  = sqrt(Var(x*))
B*      = 2^(x*)                            (crossover, playouts)

z_interp = min(x* - x0, x3 - x*) / se(x*)
           -- the SMALLER of x*'s distance to either bracket edge, in SE units;
              "|z| >= 2 on the interpolation" (DESIGN.md's own phrasing) means BOTH
              edges are at least 2 SEM away from the point estimate, i.e. a ~95%
              two-sided CI around x* does not reach outside [x0, x3].
```

`x0` = the smallest rung's x (rung 0 unless rung 0 is dropped by §3), `x3` = the
largest rung's x among the points actually used (8x's log2=18 unless rung C aborted).

**Secondary, reported on every branch, never a branch input:** the same WLS fit run on
`elo_from_win_rate` instead of margin; each rung's own win rate / elo / paired margin
individually; the realized elo-per-point conversion scale, recomputed from THIS run's
own records (not assumed from any prior cell).

⚠️ `z_interp`, `z_slope`, and `B*` are READ off the analyzer's computed value; a
from-scratch recomputation from the raw per-game records is printed alongside (same
"recomputation is a witness, never a branch input" discipline as `track_d2_prep`
§1). A disagreement beyond floating-point tolerance is `U-UNREADABLE`.

---

## §2 — UNITS AND POWER

Primary unit: **points/game of final-score margin, champion-minus-Carcasum,
deck-paired.** Elo is a derived display quantity. `x` is always in **log2(playouts)**;
`n` is always in **decks** (each deck = 2 games, seat-swapped) unless a games-count is
named explicitly.

**Power, stated before any number:** at n=100 decks/rung, r1's realized paired-margin
dispersion (SEM ≈0.977 at n=200 decks ⇒ σ_paired ≈ 0.977×√200 ≈ 13.8 pts/deck) implies
SEM_rung ≈ 13.8/√100 ≈ **1.38 pts/game** per new rung — each individual rung is
therefore NOT independently powered to a strong verdict (a single-rung z would need a
~2.8+ pt margin shift to clear z=2 alone). The ladder's power comes from **pooling all
four points in the WLS fit**, which is why the estimator of record is the fitted line,
not any single rung's own margin.

---

## §3 — PRECONDITIONS (every point must pass individually, else it is DROPPED from the
fit before D is even evaluated at the ladder level; DROPPING pushes toward `U-UNREADABLE`
per §3.1)

Fail-closed. **ABSENT is FAIL.** Each gate is read at the manifest top level, then at
`config.*`, and the analyzer reports which address resolved (house `G-BAND`/`G-J1`
precedent, `track_d2_prep/READ_RULE.md` §3).

| id | proposition | address | DROPS the point on |
|---|---|---|---|
| `G-BINARY` | `manifest.carcasum_binary_sha256` for the rung equals rung 1's own recorded sha (same vendored build, same patch set) | `games.jsonl` line 1 → `manifest.carcasum_binary_sha256` | mismatch or absent |
| `G-RULES` | `manifest.rules_manifest.name == "fixed_v1"` and `manifest.r9_env_ok == true` | `manifest.rules_manifest`, `manifest.r9_env_ok` | anything else |
| `G-CHAMP` | `manifest.champion_manifest.leaf_hash` equals rung 1's own recorded champion leaf hash; `manifest.champion_manifest.tiearb == null/off` | `manifest.champion_manifest` | mismatch, absent, or tie-arbiter present |
| `G-BUDGET` | `manifest.opponent.playouts == <the rung's assigned m>` and `manifest.opponent.budget_ms == null` | `manifest.opponent` | wrong m, or budget_ms not null (time-mode leaked in) |
| `G-MODE` | pooled median realized `carcasum_playouts` over the rung's own real turns is within **±5%** of the assigned `m` | recomputed by `analyze_ladder.py` from every `moves[].carcasum_playouts` in the rung's archive | outside ±5% — this is the smoke's own gate, re-checked at real scale, not assumed transitive (DESIGN.md §8) |
| `G-N` | the rung reached `n_common_decks >= 80` (80% of the n=100 target — the same 80%-floor convention `track_d2_prep`'s `N_COMMON_FLOOR` uses) | `analyze_ladder.py`'s own deck-pairing count | under 80 decks paired |

### §3.1 — `D` — void-contaminated (checked FIRST, at the ladder level, before K/A/B)

Copied verbatim from rung 1's `AUDIT_PLAN.md` bar and `match.py`'s own `REAL` taxonomy
(`SCORE_FINAL`, `FARM_SCORE_FINAL`, `MEEPLE_LEGALITY`, `MEEPLE_SLOT_UNMAPPED`,
`LEGALITY_OURS_EXTRA`, `HARNESS_ERROR`, `DRIVER_REJECT`, `SEAT_DESYNC`,
`COORD_FRAME_MISMATCH`) — the taxonomy is not redefined by the budget-mode swap, per
DESIGN.md §0's argument that rules-agreement is orthogonal to the opponent's budget
encoding.

**`D` fires** (any pooled-across-used-rungs occurrence, first-match-wins over K/A/B) if:

- any `VOID_*` count, OR any REAL-class divergence count, exceeds **1% of games** in
  any single rung's own corpus (rung 1's own bar — its audit and match cleared 0%, so
  1% is a real, failable bar, not a rubber stamp); OR
- fewer than **2 of the 3 new rungs (A/B/C)** reach `DONE` (§3, `G-N` + the launcher's
  own `DONE` sentinel) — an underpowered ladder is unreadable, not a weaker verdict.

`D` → **`U-UNREADABLE`.** No B\* is published. Diagnose, patch (never touching
`Carcasum/player/**`), re-audit only what changed, re-run only the affected rung(s).

---

## §4 — BRANCH TABLE (first-match-wins, D checked first per §3.1, then K, then A, then B)

Let the fit (§1) run on rung 0 plus every rung that survived §3. `x0`/`x3` are the
smallest/largest x among the points actually fit.

> ⚠️ **SIGN CONVENTION, load-bearing.** Margin = champion − Carcasum. A GENUINE
> closing-the-gap trend as playout budget rises is therefore a **NEGATIVE** slope
> (`beta1 < 0`, margin shrinking toward and through zero). Flat or positive slope means
> more search budget does not — or does not credibly — bring Carcasum closer; that is
> what "saturation" means here. `z_slope = beta1/se(beta1)` carries beta1's natural
> sign, so the "credibly closing" test is **`z_slope <= -2`**, not `z_slope >= 2`.
> (`analyze_ladder.py::decide_branch` implements exactly this and is exercised by
> `--selftest` against four hand-computable fits before this file was frozen.)

| branch | condition | action |
|---|---|---|
| **K — SATURATION KILL** | `beta1 >= 0`, OR (`beta1 < 0` but NOT credibly closing — `z_slope > -2` — AND no crossing found inside the tested range, `x* is None or x* >= x3`) | Report: *"Carcasum saturates below the champion at this budget range; better-but-saturating ruler."* **STOP — no further rungs, no 16x extension considered here.** The distinguishing test from branch B is credibility of the closing (negative-slope) trend: a slope that is not distinguishable from flat/rising (`z_slope > -2`) with no crossing inside the tested range gives no basis to expect a higher budget would ever close the gap. |
| **A — USABLE PRICE** | `beta1 < 0` AND `x0 <= x* <= x3` AND `z_interp >= 2` | Report **B\* = 2^(x\*)** as the program's **first external-currency price of the champion** — the budget at which Carcasum's fitted strength equals the champion's, with its interpolation CI. This is the deliverable rung 1 deferred. |
| **B — BOUND, QUEUE A DECISION** | `beta1 < 0` AND `x* > x3` AND `z_slope <= -2` (slope IS credibly closing; the crossing is real but past the tested range) | Report the one-sided bound: *"B\* > 2^18 = 262,144 playouts; champion's advantage is closing at a credible rate but is not yet priced."* **Queue a possible 16x rung (2,097,152 playouts) as an OWNER DECISION — this cell does not authorize it.** State the projected 16x wall-clock (≈ 2x rung C's, §DESIGN.md §6 scaling) alongside the queue note, so the owner has a cost figure to rule on. |

**Edge case, named but not separately branched:** if `x* < x0` (the fitted crossover
falls BELOW rung 0's own budget), that would mean the fit reads Carcasum as already at
or above the champion's strength at r1's own calibrated budget — inconsistent with
rung 1's own measured z=+4.18 in the champion's favor at that same point. Should this
occur, treat it as `U-UNREADABLE` regardless of `z_interp` (a fit that contradicts its
own anchor point's directly-measured sign is a fit to distrust, not a price to
publish) and flag for a design review before any re-run.

---

## §5 — WHAT THIS CANNOT SHOW

- Whether Carcasum's OWN "best" configuration (normalised Heyden evaluation +
  ε-greedy playouts, which the thesis itself concludes is stronger than the
  `PortionUtility`/`RandomPlayout` pair both rungs use) would price differently — out
  of scope, same as rung 1.
- Anything about the R9-off (`walled`) production elo — this cell inherits rung 1's
  R9-on posture and is not comparable to `walled` numbers, same caveat.
- A crossover ABOVE 16x (branch B's queue is the owner's to fund or not; this cell buys
  no evidence past 8x).

---

## §6 — CLOSE-OUT

Read with `scripts/carcasum_match/analyze_ladder.py`, not `match.py`'s own
`summarize()` (DESIGN.md §7). Apply this file's §4 exactly as written — the fired
branch IS the authorization to report it, not to re-litigate it. Then the six-touch
checklist (DESIGN.md §9).
