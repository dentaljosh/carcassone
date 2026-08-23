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
>
> ⚠️ **AMENDED PRE-LAUNCH, zero games run; amended blind commit = the commit
> introducing this line.** The pair was frozen but unlaunched with zero statistics of
> any kind, so this is design-time. The amendment: rung **D0 = 16,384 playouts**
> (0.5× the base, half r1's own cost, lands on the thesis's own doubling table's last
> datum); execution order **D0 → A → B → C** with a **kill-only interim futility
> check** between rungs; **D0/A/B/C share ONE 100-deck set**, and the **within-deck
> slope** across them becomes the estimator of record (§1.1), demoting the
> pre-amendment aggregate WLS fit to a secondary witness (§1.2) — full detail below.
> `WORKERS.conf::BLIND_COMMIT` is re-stamped to this amendment commit's own sha by the
> same follow-up-commit convention as the original freeze.

# READ_RULE — Carcasum rung-2 budget ladder

> **⚠️ BLIND ORDERING.** This file is committed BEFORE the band is claimed, BEFORE game
> 1, and BEFORE any rung-2 statistic exists — true of both the original freeze and this
> amendment (zero games at either point). The branch that fires is taken **VERBATIM**,
> whatever it is. Owner authorization funds the cell and does not name its answer —
> same discipline as rung 1's `PREREG.md` §5 and `track_d2_prep`'s `READ_RULE.md` §0.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `carcasum_rung2_prep`. Analyzer:
> [`../../scripts/carcasum_match/analyze_ladder.py`](../../scripts/carcasum_match/analyze_ladder.py).

---

## §1 — THE STATISTICS, NAMED BEFORE THEY EXIST

**Per rung** (rung 0 = r1's already-collected corpus, band `142000000000`, 200 decks;
rungs D0/A/B/C = this cell's new data, ONE shared 100-deck set, band `143000000000`):

```
M_rung   = deck-paired margin (champion - Carcasum), pts/game, over the rung's own decks
SEM_rung = paired standard error of M_rung
x_rung   = log2(realized median opponent playouts/turn for that rung)
           rung 0: computed from the FULL r1 corpus (measured, = 14.9904)
           rungs D0/A/B/C: log2(m) EXACTLY (14, 16, 17, 18) -- the pilot G-MODE gate
           (§3) licenses treating the assigned m as the realized median to within noise
```

### §1.1 — PRIMARY: the within-deck slope (amendment)

For each of the (up to) 100 decks shared by D0/A/B/C, let `margin_d(rung)` be that
deck's own paired margin at a rung (averaged over its 2 seatings — same construction as
`M_rung`, just not aggregated across decks). For every deck with `margin_d` defined at
**≥2** of the four shared-deck rungs:

```
slope_d = OLS slope of {(x_rung, margin_d(rung))} over just that deck's own points
          (deck's own regression; with exactly 2 points, slope_d = (y2-y1)/(x2-x1) exactly)

mean_slope = mean(slope_d) over all decks with slope_d defined
sem_slope  = stdev(slope_d) / sqrt(n_decks_with_slope)     -- decks are i.i.d. draws,
             so this is a genuine SEM, not a residual-based approximation
z_slope    = mean_slope / sem_slope
```

**Why within-deck, not the plain aggregate fit.** This is the CRN extension of
deck-pairing itself (`DESIGN.md` §2): reusing the SAME `deck_seed` across all four
shared rungs holds the champion's own PIMC determinization seed constant per
(deck, seat) — the only thing that changes between a deck's appearances at D0 vs A vs
B vs C is the opponent's playout budget. Differencing the SAME deck's outcomes across
that one changed variable cancels the deck's own baseline variance, exactly the way a
paired margin already cancels it across seatings — extended here from a single
difference to a slope.

**Anchored crossover.** D0 is the cheapest shared-deck rung (`x0 = 14`); its own
AGGREGATE deck-paired margin `M_D0`/`SEM_D0` anchors the line's intercept:

```
x*  = x0 - M_D0 / mean_slope
Var(x*) = (1/mean_slope)^2 * SEM_D0^2  +  (M_D0/mean_slope^2)^2 * sem_slope^2
          (delta method on x* = x0 - M_D0/mean_slope, treating M_D0 and mean_slope as
          independent — an approximation named, not resolved further, since M_D0 is
          the plain D0 aggregate and mean_slope is built from WITHIN-deck differences:
          related statistics, not exactly independent, but the correlation is expected
          small relative to each term's own variance)
se(x*)  = sqrt(Var(x*))
B*      = 2^(x*)

z_interp = min(x* - x0, x3 - x*) / se(x*)     (x3 = the largest shared-deck rung's x
                                                actually used, up to 18 for rung C)
```

**Rung 0 cross-check, NEVER a branch input.** The primary line, extrapolated backward
from D0 to rung 0's own `x = 14.9904`, is compared against rung 0's directly-measured
margin (+4.08 pts, `DESIGN.md` §0). Rung 0 cannot enter the within-deck estimator
itself — it shares zero `deck_seed` values with D0/A/B/C (disjoint bands, 142e9 vs
143e9) — so this comparison is reported as a plausibility witness only. A large
disagreement is reported, never silently absorbed, and does not by itself change the
branch decision.

### §1.2 — SECONDARY: the aggregate fit (pre-amendment estimator, now a witness)

Unchanged from the pre-amendment design: weighted least squares of each rung's own
`M_rung` on `x_rung`, weights `1/SEM_rung²`, across whichever of {rung 0, D0, A, B, C}
pass §3. This is the ONE estimator that can include rung 0 from the very first new
rung (no deck-matching needed — it works on rung-level aggregates), which is exactly
why it — not the within-deck estimator — drives the interim futility test (§5): the
interim check must be able to fire after just 2 points (rung 0 + D0), before A/B/C
have even run.

```
beta1, beta0, se(beta1), se(beta0), cov(beta0,beta1)   -- WLS normal equations
z_slope_agg = beta1 / se(beta1)
```

Reported alongside the primary on every branch — **never itself a branch input** for
the FINAL D/K/A/B decision (§4), which reads off the primary within-deck estimator
only. It IS the sole input to the INTERIM test (§5).

**Also secondary, reported on every branch, never a branch input:** the same
aggregate-WLS shape run on `elo_from_win_rate` instead of margin; each rung's own win
rate / elo / paired margin individually; the realized elo-per-point conversion scale,
recomputed from THIS run's own records.

⚠️ `z_interp`, `z_slope` (both flavors), and `B*` are READ off the analyzer's computed
value; a from-scratch recomputation from the raw per-game records is printed alongside
(same "recomputation is a witness, never a branch input" discipline as `track_d2_prep`
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
therefore NOT independently powered to a strong verdict on its own. The within-deck
estimator's power comes from a DIFFERENT source than the aggregate fit's: it is not
pooling four noisy rung-level aggregates, it is averaging up to 100 individually
low-noise PER-DECK slopes (each deck's own champion-side randomness is IDENTICAL
across its own rungs by construction — §1.1 — so a per-deck slope's noise is
overwhelmingly the opponent's own non-CRN search variance, not deck-to-deck spread).
This is expected to be considerably tighter than the aggregate fit's four-point WLS,
though the realized `sem_slope` is what the read-out reports, not this prior.

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
| `G-SHARED-DECKS` (amendment) | for D0/A/B/C only: the rung's own set of realized `deck_seed` values is a SUBSET of `{143000000000..143000000099}` — i.e. the rung drew from the ONE shared range, not an independent range | `analyze_ladder.py`'s own deck_seed collection per rung | any `deck_seed` outside the shared 100-deck range |

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
- fewer than **2 of the 4 new rungs (D0/A/B/C)** reach `DONE` (§3, `G-N` + the
  launcher's own `DONE` sentinel) — an underpowered within-deck estimator (built from
  fewer than 2 shared-deck rungs) is unreadable, not a weaker verdict.

`D` → **`U-UNREADABLE`.** No B\* is published. Diagnose, patch (never touching
`Carcasum/player/**`), re-audit only what changed, re-run only the affected rung(s).

---

## §4 — FINAL BRANCH TABLE (first-match-wins, D checked first per §3.1, then K, then A,
then B — the INTERIM test in §5 is a SEPARATE, earlier, kill-only check between rungs)

Let the PRIMARY within-deck fit (§1.1) run on D0 plus every shared-deck rung that
survived §3. `x0 = 14` (D0, the anchor) unless D0 itself is dropped by §3 (in which case
the ladder falls to §3.1's `D` — void/underpowered — since D0 is the cheapest rung and
its own kill-only interim check runs first anyway). `x3` is the largest x among the
shared-deck points actually used.

> ⚠️ **SIGN CONVENTION, load-bearing.** Margin = champion − Carcasum. A GENUINE
> closing-the-gap trend as playout budget rises is therefore a **NEGATIVE** slope
> (`mean_slope < 0`, margin shrinking toward and through zero). Flat or positive slope
> means more search budget does not — or does not credibly — bring Carcasum closer;
> that is what "saturation" means here. `z_slope` carries `mean_slope`'s natural sign,
> so the "credibly closing" test is **`z_slope <= -2`**, not `z_slope >= 2`. Identical
> convention for the secondary aggregate `beta1`/`z_slope_agg`.
> (`analyze_ladder.py::decide_branch` implements exactly this and is exercised by
> `--selftest` against nine hand-computable cases, including three within-deck and
> three interim-futility cases added by this amendment, before this file was frozen.)

| branch | condition | action |
|---|---|---|
| **K — SATURATION KILL** | `mean_slope >= 0`, OR (`mean_slope < 0` but NOT credibly closing — `z_slope > -2` — AND no crossing found inside the tested range, `x* is None or x* >= x3`) | Report: *"Carcasum saturates below the champion at this budget range; better-but-saturating ruler."* **STOP.** Same distinguishing logic as the pre-amendment table, now read off the primary within-deck slope. |
| **A — USABLE PRICE** | `mean_slope < 0` AND `x0 <= x* <= x3` AND `z_interp >= 2` | Report **B\* = 2^(x\*)** as the program's **first external-currency price of the champion**. This is the deliverable rung 1 deferred. |
| **B — BOUND, QUEUE A DECISION** | `mean_slope < 0` AND `x* > x3` AND `z_slope <= -2` | Report the one-sided bound: *"B\* > 2^x3 playouts; champion's advantage is closing at a credible rate but is not yet priced."* **Queue a possible 16x rung (2,097,152 playouts) as an OWNER DECISION — this cell does not authorize it.** State the projected 16x wall-clock alongside the queue note. |

**Edge case, named but not separately branched:** if `x* < x0` (the fitted crossover
falls BELOW D0's own budget), that would mean the fit reads Carcasum as already at or
above the champion's strength at D0's own budget — worth a specific note now that D0 is
half of r1's own calibrated budget and r1 itself measured the champion clearly ahead
(z=+4.18) at a HIGHER budget than D0. Should this occur, treat it as `U-UNREADABLE`
regardless of `z_interp` and flag for a design review before any re-run.

---

## §5 — INTERIM FUTILITY TEST (amendment, kill-only, between rungs)

Run by `run_cells.sh` (via `analyze_ladder.py --interim`) **after every completed
rung, in execution order D0 → A → B**, i.e. up to three interim checks total (no check
is needed after C — that is simply the final read). Uses the **SECONDARY aggregate
fit** (§1.2), because it is the one estimator that can be computed from as few as 2
points (rung 0 + D0) — the primary within-deck estimator needs ≥2 SHARED-deck rungs
and cannot fire until after A completes at the earliest.

```
INTERIM-K fires iff:  beta1_agg >= 0  AND  z_slope_agg >= +2.0
```

**Kill-only, by construction:** a negative (right-signed, genuinely closing) point
estimate NEVER fires, at ANY significance — `beta1_agg < 0` alone rules it out,
regardless of `z_slope_agg`. A positive-or-flat point estimate that is not yet
confident (`z_slope_agg < 2.0`) is INCONCLUSIVE and also never fires — a single
flat-looking rung-pair is not a conclusion. Only a slope that is BOTH wrong-signed AND
statistically confident about it stops the ladder early.

**On fire:** the launcher marks every not-yet-run rung `SKIPPED_INTERIM_KILL` (not
`FAILED`, not `ABORTED_PARTIAL` — a distinct, planned-outcome sentinel), clears
`RUN_LIVE.json`, and exits 0. The final read-out (§4) still runs on whatever rungs DID
complete, subject to §3.1's ≥2-shared-deck-rung floor — an interim kill after D0+A
alone (2 shared-deck rungs) can still produce a `K-SATURATION` FINAL verdict if that
same 2-point primary fit also reads as saturating; if it does not (the primary and the
secondary CAN disagree, since they are different estimators, `DESIGN.md` §1.2's
"disagreement... is reported, not silently absorbed" spirit extends here), that
disagreement is itself reported and the ladder still reads `U-UNREADABLE` rather than
silently preferring one estimator's verdict over the other's contradiction.

⚠️ **Multiple-look caveat, named not solved.** Up to 3 interim checks, each at a naive
`z>=2` bar, inflate the false-early-kill rate relative to a single look (a well-known
sequential-testing effect). This amendment does not apply an alpha-spending correction
— out of scope for a same-day design-time steer — and the caveat is carried forward
explicitly rather than silently accepted. A false-kill's cost is bounded: the primary
within-deck read-out at whatever rungs DID complete is still reported and still subject
to §4's own independent test, so an interim false-kill can shorten the ladder but
cannot, by itself, manufacture a false A/B verdict.

---

## §6 — WHAT THIS CANNOT SHOW

- Whether Carcasum's OWN "best" configuration (normalised Heyden evaluation +
  ε-greedy playouts, which the thesis itself concludes is stronger than the
  `PortionUtility`/`RandomPlayout` pair both rungs use) would price differently — out
  of scope, same as rung 1.
- Anything about the R9-off (`walled`) production elo — this cell inherits rung 1's
  R9-on posture and is not comparable to `walled` numbers, same caveat.
- A crossover ABOVE 16x (branch B's queue is the owner's to fund or not; this cell buys
  no evidence past 8x).
- Any correction for the §5 multiple-look inflation — named, not solved, by this
  amendment.

---

## §7 — CLOSE-OUT

Read with `scripts/carcasum_match/analyze_ladder.py`, not `match.py`'s own
`summarize()` (DESIGN.md §7). Apply this file's §4 exactly as written — the fired
branch IS the authorization to report it, not to re-litigate it. Then the six-touch
checklist (DESIGN.md §9).
