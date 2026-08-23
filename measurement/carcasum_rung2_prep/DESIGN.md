# CARCASUM RUNG-2 BUDGET LADDER — DESIGN

> ⛔→✅ **FROZEN 2026-08-23 (branch-freeze: the blind commit is THE COMMIT INTRODUCING
> THIS BANNER, on branch `carcasum-rung2-freeze`, cut from `carcasum-match-freeze` —
> local main is latched under a live reconcile suite (`measurement/tiearb2_stage2_20260817/RUN_LIVE.json`);
> the branch merges at the quiet window; a committed sha is a provable freeze on any
> branch, same precedent as `carcasum-match-freeze` itself). Owner funding: "i'm fine
> funding rung2" 2026-08-23. No game on band 143000000000 exists at freeze time. NOT
> LAUNCHED — this is a build-only deliverable; the orchestrator fires it with its own
> monitors, exactly as `measurement/carcasum_match_prep/LAUNCH_PROCEDURE.md` did for
> rung 1.**

> ⚠️ **AMENDED PRE-LAUNCH, zero games run; amended blind commit = the commit
> introducing this line.** Owner's mid-build steer (relayed by the coordinator,
> verbatim: *"100k is way above their 16k flattening, no? so maybe we see its flat
> by just comparing to 50k?"*), mapped onto the real (not the then-believed) 32,551
> median calibration: adds rung **D0 = 16,384 playouts (0.5× the base)**, reorders
> execution cheapest-first (D0→A→B→C) with a kill-only interim futility check between
> rungs, and restructures D0/A/B/C onto **one shared 100-deck set** with the
> **within-deck slope** as the estimator of record. This is design-time — the pair was
> frozen but unlaunched with zero statistics of any kind, so the amendment supersedes
> the pre-amendment text below wherever the two disagree; nothing here retracts the
> original calibration, the smoke result, or the champion/opponent/rules configuration.
> Full detail: `READ_RULE.md` §1.1/§5, `WORKERS.conf`, `run_cells.sh`.

> ⚠️ **AMENDED PRE-LAUNCH #2, zero games run; amended blind commit = this commit.**
> A launch-agent review found `analyze_ladder.py` implemented only 2 of `READ_RULE.md`
> §3's 7 gates (`gate_d_void`, `gate_g_n`) plus a fail-OPEN `G-MODE` passthrough —
> `G-BINARY`, `G-RULES`, `G-CHAMP`, `G-BUDGET`, and `G-SHARED-DECKS` were documented as
> "Fail-closed. ABSENT is FAIL." but never read `manifest.*` at all, so a binary swap,
> rules drift, champion mismatch, leaked time-budget mode, or an out-of-range deck seed
> would have passed the read-out silently. All five are now implemented and wired into
> `main()`'s per-rung gate conjunction, `G-MODE` is fixed to fail-closed, and two wrong
> manifest addresses in `READ_RULE.md`'s own table were found and corrected in the same
> pass. Full detail: `READ_RULE.md` §3 (its own banner and table), and this file's §7.

This is the single non-amendment status paragraph in this file. (r1's `PREREG.md` left
a stale `STATUS: DRAFT` paragraph under its own FROZEN banner — a defect named
explicitly in this cell's brief. This file carries exactly one FROZEN statement plus
the one AMENDED notice above it, and nothing below contradicts either.)

Design: this file. Read-out branch table: [`READ_RULE.md`](READ_RULE.md). Constants:
[`WORKERS.conf`](WORKERS.conf). Launcher: [`run_cells.sh`](run_cells.sh). Analyzer:
[`../../scripts/carcasum_match/analyze_ladder.py`](../../scripts/carcasum_match/analyze_ladder.py).

---

## 0. What this cell is, and what it inherits from rung 1

Rung 1 ([`measurement/carcasum_match_prep/PREREG.md`](../carcasum_match_prep/PREREG.md))
priced the champion against Carcasum's `MCTSPlayer<PortionUtility,RandomPlayout>` at
**one** budget — the thesis's own 5000 ms/move — and found the champion still ahead:
**paired margin +4.08 pts/game, se 0.977, z +4.18** (recomputed here directly from the
frozen archive, `measurement/carcasum_match_20260823/games.jsonl`, 400/400 real games,
0 void — the same corpus copied to this session's scratchpad and used for every
calibration number below). Rung 1's own read-rule explicitly deferred the budget
question: *"The budget ladder is deferred to rung 2… locking the ladder question out of
rung 1 is what stops this cell from quietly becoming a budget-shopping exercise."* This
cell is that deferred question: **does more search budget close the gap, and if so, at
what budget B\* does Carcasum equal the champion?**

**Inherited verbatim, not re-derived:**

- **Champion config** — the champion of record in `governance/PRODUCTION.yaml` at its
  deploy budget (desktop `k8×1376` = 11,008, rust backend, `verify=True`, curve125
  leaf, **no tie-arbiter**), exactly as rung 1 ran it. Not a knob here.
- **Opponent identity/config** — `MCTSPlayer<Utilities::PortionUtility,
  Playouts::RandomPlayout>`, `Cp=0.5`, `reuseTree=false`, no priors / widening / bias.
  The ONLY change from rung 1 is the **budget encoding**: rung 1 used
  `budget_ms=5000, mIsTimeout=true`; this cell uses `playouts=<rung value>,
  mIsTimeout=false` — `scripts/carcasum_match/match.py --opp-playouts` already
  implements this (it sets `opponent["playouts"]` and nulls `opponent["budget_ms"]`;
  see `main()` in that file). No harness code changes are needed for the budget swap.
- **Rules** — `fixed_v1` + `CARCASSONNE_FIX_R9=1`, both sides, not a knob.
- **Deck-paired seat-swapped CRN structure**, the divergence-audit gates (§4 below,
  copied verbatim from rung 1's `AUDIT_PLAN.md` taxonomy — rung 1 already discharged
  the audit; this cell reuses that PASS, it does not re-run the audit, because nothing
  about the rules-agreement question changes when the opponent's budget knob changes
  from time to playout count — see §4.1), and the readout discipline (median over mean
  for playouts/turn, deck-paired margin as estimator of record, void/divergence counts
  reported never dropped).
- **Non-CRN-opponent posture** — Carcasum's RNG seed is compile-time only; decks and
  seatings are exactly reproducible, the opponent's MCTS search is not. Same as rung 1.

**What is new:** four playout-budget rungs (D0/A/B/C, amendment-added D0 below), a
fifth ladder point supplied by rung 1's own already-collected datum (relabeled "rung
0"), and a fitted line — primarily the within-deck slope across the four shared-deck
rungs, secondarily an aggregate fit that can include rung 0 — to locate, or bound, the
budget B\* at which the fitted margin crosses zero.

---

## 1. Calibrating the r1-equivalent playout budget — the arithmetic, shown

r1's opponent ran under a **time** budget (5000 ms/move via
`boost::chrono::thread_clock`), so its games have no single "playout count" — every
move ran to whatever playout count 5 CPU-seconds bought, and that count is **violently
skewed by ply** (an early-game rollout is long, a late-game rollout is short), exactly
as `PREREG.md` §2.1 documents from a 142-turn smoke and the reason that document
insists on **median, not mean**, for any playouts/turn statistic.

This cell needs a single *representative* playout count to serve as rung 0's x-value
and the ×1 base for the 2×/4×/8× multipliers — the calibration must therefore be the
**median**, computed here from the **full n=400 corpus** (14,193 real opponent-turn
records; the small 142-turn smoke number quoted in `PREREG.md` is superseded by this
larger, in-band sample):

```
$ python3 -c "
import json, statistics
recs = [json.loads(l) for l in open('measurement/carcasum_match_20260823/games.jsonl')]
turns = [m['carcasum_playouts'] for r in recs if not r.get('void')
         for m in r['moves'] if 'carcasum_playouts' in m]
print(len(turns), statistics.median(turns), statistics.mean(turns))
"
14193 32551 103656.47...
```

- **n = 14,193** real opponent-turn records, pooled across all 400 real games (0 void).
- **Pooled median = 32,551 playouts/turn.** Corroborated by the median-of-per-game-medians
  (32,499.5) — the two agree to within 0.2%, so the pooling choice is not doing any
  work.
- **Pooled mean = 103,656** (per-game-mean average = 103,502, matching `PREREG.md`'s own
  reported "~103.5k mean playouts" almost exactly — see §6 below, where the MEAN is the
  right statistic for a *different* purpose, wall-clock scaling, and must not be
  confused with the median used here for calibration). The 3.2× mean/median ratio is
  the same endgame-skew artefact `PREREG.md` names ("~28k in the opening, ~2.6M on the
  last few plies" — do not quote the mean as a playout budget).

**r1-equivalent base = 32,551 playouts/turn** (median). Rounded to the nearest power of
two — **32,768 = 2¹⁵**, +0.67% — for two reasons: (a) log2-spacing is the fit's native
axis (§5), so integer log2 x-values are exact rather than irrational; (b) `m` is an
integer CLI argument to `MCTSPlayer` and a round binary number is no less "real" a
budget than 32,551 would be, while being far easier to state and reproduce. The 0.67%
rounding is two orders of magnitude below this cell's measurement noise and immaterial
to every gate below.

**Rung 0 (r1 itself)** is *not* re-run — it enters the fit at its own measured x, not
the rounded base: `x0 = log2(32551) = 14.9904`, unrounded, because rung 0's y-value
(margin +4.08, se 0.977) is real collected data tied to the real median it produced,
not to a number this cell chose after the fact.

---

## 2. The four rungs (D0 added by the pre-launch amendment)

| rung | multiplier | playouts (`m`, `mIsTimeout=false`) | `log2(m)` |
|---|---|---|---|
| **D0** | **0.5×** | **16,384** (2¹⁴) | 14 |
| A | 2× | **65,536** (2¹⁶) | 16 |
| B | 4× | **131,072** (2¹⁷) | 17 |
| C | 8× | **262,144** (2¹⁸) | 18 |

`n = 200` games/rung = **100 decks × 2 seatings**, deck-paired seat-swapped CRN.
Champion config, rules profile, and opponent identity are otherwise byte-identical to
rung 1 (§0) — the *only* experimental variable across all five ladder points (D0, A, B,
C, and rung 0) is the opponent's playout budget.

**Why D0.** Owner's steer (relayed by the coordinator): the original "compare to ~50k"
instinct, mapped onto the REAL 32,551 median (not the then-believed ~100k), lands on a
**0.5× down-rung at 16,384 playouts** — half of r1's own calibrated cost, cheapest of
all four new rungs, AND it lands exactly on the thesis's own doubling table's *last*
measured datum (16,384-vs-8,192 → 56.3%), giving this cell a direct external
cross-check against a published number, for free.

**SHARED DECKS (amendment §3): D0, A, B, and C all draw the SAME 100-deck set**, not
four disjoint 100-deck ranges. This is a deliberate CRN extension of the same trick
`match.py`'s own deck-pairing already uses (differencing the SAME deck's two seatings
cancels that deck's own variance) — reusing the identical `deck_seed` across all four
rungs means `agent_seed(deck_seed, champ_seat)` (the CHAMPION's own PIMC determinization
seed — see `match.py`) is IDENTICAL for a given deck+seat across every rung, so only the
**opponent's budget** differs between a deck's four (or fewer) appearances. That is
exactly the property the **within-deck slope** estimator (`READ_RULE.md` §1.1) needs:
a per-deck regression across rungs where the only thing that changed *is* the
independent variable, not the champion's own randomness too. The opponent itself stays
non-CRN regardless (compile-time-only seed, unchanged posture from rung 1) — reusing the
deck only removes CHAMPION-side noise, never opponent-side.

⚠️ **Rung 0 (r1) is NOT part of the shared-deck set.** It lives on band `142000000000`
(200 decks, a disjoint range from this cell's `143000000000`), so it shares zero
`deck_seed` values with D0/A/B/C by construction — the within-deck estimator cannot
include it. It re-enters the read-out as an independent cross-check on the fitted
line's backward extrapolation only (`READ_RULE.md` §1.1), never as an input to the
primary branch decision. The interim futility test (§READ_RULE.md §5) uses a SEPARATE,
simpler AGGREGATE fit that *can* include rung 0 trivially (no deck-matching needed).

**Why n=200/rung and not n=400 like rung 1.** Unchanged reasoning from the
pre-amendment text: the load-bearing statistic pools information across rungs (now via
the within-deck slope rather than only the aggregate fit), so per-rung n needs to keep
each point informative, not independently clear a ±35-elo bar. See `READ_RULE.md` §2
for the fit's power arithmetic.

---

## 3. Estimator of record and the ladder statistic

**Primary, per rung:** the deck-paired margin (champion − Carcasum), `mean(margin_seat0
+ margin_seat1)/2` over the rung's own decks, with its paired SEM — identical
construction to rung 1's `summarize()`, computed independently by
`analyze_ladder.py` (not `match.py`'s own `summarize()` — see §7 for why a second,
corrected implementation exists).

**Primary, ladder-level (AMENDED):** the **within-deck slope** across the four
shared-deck rungs {D0, A, B, C} — for each of the 100 shared decks, its own margin at
every rung it appears in is regressed against `log2(playouts)` *independently of every
other deck*, and the per-deck slopes are averaged (mean, with the population SEM over
decks). This is the CRN extension of deck-pairing itself: differencing the SAME deck
across budgets cancels that deck's own baseline variance the way differencing the SAME
deck's two seatings already does. Anchored at D0 (the cheapest shared-deck rung, using
D0's own aggregate deck-paired margin as the intercept) for the crossover.

**Secondary, ladder-level (witness, never a branch input):** the pre-amendment
**weighted least-squares fit** of each rung's own aggregate margin against
`log2(playouts)` — the one estimator that CAN include rung 0 (no deck-matching needed,
since it works on rung-level aggregates, not per-deck values). Reported alongside the
primary fit and used, on its own, to drive the interim futility test (`READ_RULE.md`
§5), which needs to fire from as few as 2 points (rung 0 + D0) before any shared-deck
rung besides D0 has even run.

Rung 0 additionally serves as an **independent cross-check** (never a branch input): the
primary within-deck line, extrapolated backward from D0 to rung 0's own `x`, is compared
against rung 0's directly-measured margin (+4.08 pts, §0). A large disagreement is
reported, not silently absorbed.

The fitted line's **zero-margin crossing**, `x* = -β0/β1` (in log2-playouts, or the
anchored form for the primary estimator), converted to `B* = 2^x*` playouts, is the
answer to "at what budget does Carcasum equal the champion" — full formulas, standard
errors via the delta method, the interim test, and the exact branch conditions are all
in `READ_RULE.md` §1.1/§4/§5 (kept out of this file so the read-rule is a single,
self-contained, git-diffable target, matching the `track_d2_prep` precedent).

---

## 4. The band

**Registry state at draft time** (`git show carcasum-match-freeze:governance/BAND_REGISTRY.csv`,
70 rows, high-water mark = `142000000000`, rung 1's own claim): **next free band =
`143000000000`.** Verified by re-reading the registry immediately before this section
was written, per the standing lesson in rung 1's own `PREREG.md` §3 ("a band planned in
a document is not a band reserved… re-read the registry AND census the cluster for a
live `--seed-start` in the planned range"). No process census was run for this
document (build-only, no launch), so **the orchestrator must re-verify both — registry
AND a live-run census — immediately before claiming**, exactly as rung 1's own
close-out lesson demands.

```
band_seed_start : 143000000000
label           : CARCASUM RUNG-2 BUDGET LADDER: champion vs Carcasum MCTSPlayer
                  <PortionUtility,RandomPlayout> @ Cp=0.5, playout-budget mode
                  (mIsTimeout=0), fixed_v1 + CARCASSONNE_FIX_R9=1, deck-paired
                  seat-swapped CRN, 4 rungs (D0/A/B/C) x n=200 games (100 decks x
                  2 seats) -- amendment: ALL FOUR RUNGS SHARE THE SAME 100 DECKS.
tier            : claim
status          : (open at commit)
claimed_date    : (date of blind commit)
decision_influenced : (blank until close-out)
evidence_or_claim   : measurement/carcasum_rung2_prep/DESIGN.md -> the committed design
notes           : Seeds 143000000000..143000000099 -- ONE 100-deck range, REUSED
                  VERBATIM by D0, A, B, AND C (the amendment's shared-deck design,
                  for the within-deck slope estimator). This is a NARROWER claim
                  than the pre-amendment draft (which reserved 300 disjoint seeds,
                  100/rung) -- sharing decks means only 100 seeds are drawn in
                  total, not 400. Per-rung NAMESPACING is by OUTPUT PATH, not seed
                  offset: each rung writes to its own out-subdir
                  (measurement/carcasum_rung2_20260823/rung{D0,A,B,C}/games.jsonl)
                  so match.py's own --resume dedup (keyed on deck_seed+champ_seat
                  within ONE archive file) never collides across rungs -- see
                  READ_RULE.md §1.1 and WORKERS.conf. Rung 0 draws NO new seeds --
                  it is rung 1's already-collected corpus on band 142000000000
                  (a DISJOINT range, shares no deck_seed with this band), cited
                  not re-claimed. No top-up range reserved: this cell's branch
                  table (READ_RULE.md) has no C-style top-up branch.
```

**Band hygiene.** The smoke (§8) used a dev-tier throwaway seed (`900000500000`, well
outside any claimed band) and is explicitly non-confirmatory — it must never be re-used
as, or pooled with, rung data.

---

## 5. Structural gates and the branch table — pointer

Every gate (its exact tool + address, fail-closed, no pass-always/fail-always
conditions) and the full D→K→A→B branch table (first-match-wins) live in
[`READ_RULE.md`](READ_RULE.md), not here — same split as `track_d2_prep`'s
`DESIGN.md`/`READ_RULE.md` pair, so the read-out target is one small, diffable file. A
one-line summary, expanded fully in `READ_RULE.md` §4-§5 (AMENDED: D checked first as
before; K is now checked BOTH as a per-rung interim test after D0/A/B and as the final
test on the primary within-deck estimator; A/B now read off the primary estimator, with
the pre-amendment aggregate WLS demoted to a secondary witness):

⚠️ **Sign convention** (spelled out in full in `READ_RULE.md` §4): margin = champion −
Carcasum, so a genuine closing-the-gap trend is a **negative** slope; "credibly closing"
is `z_slope ≤ −2`, not `≥ 2` — applies identically to the primary within-deck slope and
the secondary aggregate `β1`.

| order | branch | fires when | action |
|---|---|---|---|
| 0 (amendment) | **INTERIM K — kill-only, between rungs** | after each of D0/A/B completes: the SECONDARY aggregate fit (rung 0 + completed shared-deck rungs) has slope ≥0 AND z_slope ≥ +2 | Stop the ladder early — remaining rungs are never launched. Kill-only: a right-signed OR inconclusive interim reading never stops it. `READ_RULE.md` §5. |
| 1 | **D — void-contaminated** | any `VOID_*`/REAL-divergence rate > rung 1's threshold (copied verbatim, `READ_RULE.md` §3) | `U-UNREADABLE`, no strength number published |
| 2 | **K — saturation kill (final)** | PRIMARY (within-deck) mean slope ≥ 0, OR (mean slope < 0 but not credible: z_slope > −2) AND crossover x\* is not found inside the tested range | "Carcasum saturates below champion; better-but-saturating ruler." STOP. |
| 3 | **A — usable price** | mean slope < 0 AND x0(D0) ≤ x\* ≤ x3 (crossover inside [D0, 8×]) AND z_interp ≥ 2 | Report B\* = 2^x\* as the program's first external-currency price of the champion. |
| 4 | **B — bound, not a price** | mean slope < 0 AND x\* > x3 (crossover beyond 8×) AND the slope IS credibly closing (z_slope ≤ −2) | Report the bound; queue a possible 16× extension as an **owner decision**, not pre-authorized here. |

---

## 6. Wall-clock projection

**Basis — the realized r1 corpus, recomputed here, not assumed from `PREREG.md`'s
4-game draft numbers:**

```
mean wall_secs/game (400 real games)      = 249.7 s     (matches PREREG.md's own figure)
mean opp_driver_turns/game                = 35.48
mean opp_driver_ms_per_turn               = 5014.9 ms
mean ms_per_move_champ                    = 1143.2 ms
mean champion moves/game (tile+meeple)    = 70.99

decomposed opponent share  = 35.48 x 5.0149 s  = 177.94 s
decomposed champion share  = 1.1432 s x 70.99  =  81.15 s
decomposed sum                                 = 259.09 s  (3.6% over measured 249.7s --
                                                              bookkeeping/overlap slack,
                                                              not investigated further)
scale factor to match measured total           = 249.7 / 259.09 = 0.9638
opponent share, scaled                         = 177.94 x 0.9638 = 171.50 s
champion share, scaled                         =  81.15 x 0.9638 =  78.22 s   (check: 171.50+78.22=249.72 [OK])
```

**The champion's share is treated as flat across rungs** (unmodified config, same game-
length distribution). **The opponent's share is scaled by the SAME 2×/4×/8× multiplier
used for the playout budgets** — this is an approximation (§1's median-32,551 base and
this section's mean-103,502 base are different statistics, and the wall-clock multiplier
is applied to the *mean-anchored* opponent share, not re-derived from the median), sound
because MCTS-with-full-random-rollout cost is roughly linear in playout count at a fixed
board-size regime, and the brief itself asks for "roughly ×2/×4/×8", not an exact
re-derivation.

| rung | opp share | champ share | total/game | n | wall @ W=14 (linear) |
|---|---|---|---|---|---|
| **D0 (0.5×)** | **85.75 s** | 78.22 s | **163.97 s** | 200 | 2,342 s = **0.65 h** |
| A (2×) | 343.00 s | 78.22 s | 421.22 s | 200 | 6,017 s = **1.67 h** |
| B (4×) | 686.00 s | 78.22 s | 764.22 s | 200 | 10,917 s = **3.03 h** |
| C (8×) | 1,372.00 s | 78.22 s | 1,450.22 s | 200 | 20,717 s = **5.76 h** |
| **linear total** | | | | | **11.11 h** |

Applying the same contention allowance rung 1's own §4.3 measured at W=14 (linear
1.81h → realized ~2.0h, a ×1.105 factor): **≈12.3 h total** — close to, though not
identical to, the coordinator's own ~12.5h ballpark relayed with the amendment; this
cell's own consistent scaling method is what is reported, and the two agree to within
~2%. **Validate, don't trust** (rung 1's own §3 discipline): re-project off the first
~20 games of each rung before assuming the total, exactly as `LAUNCH_PROCEDURE.md` §3
does.

**Execution order is cheapest-first (amendment §2): D0 → A → B → C**, with the
kill-only interim futility check (`READ_RULE.md` §5) run after every completed rung
starting with D0 — so an early, decisive non-closing signal stops the ladder before its
most expensive rungs (B, C) are ever launched, not after.

**Abort-to-partial rule (unchanged in kind, D0 added).** A rung whose wall-clock exceeds
**2× its own linear projection** aborts (the launcher wraps each rung's `match.py`
invocation in `timeout` at that bound) rather than blocking the remaining rungs:

| rung | 2x abort bound |
|---|---|
| D0 | 1.30 h (4,685 s) |
| A | 3.34 h (12,034 s) |
| B | 6.07 h (21,834 s) |
| C | 11.51 h (41,434 s) |

An aborted rung's partial games are kept (archived incrementally, resumable under
`--resume`) but that rung is marked `ABORTED_PARTIAL`, not `DONE`. `analyze_ladder.py`
(§7) computes its **primary** (within-deck) estimator on whichever of D0/A/B/C reached
`DONE` — only if that count is **≥ 2** (an underpowered within-deck slope, from a single
shared-deck rung, is not a slope at all) — and its **secondary** aggregate witness on
rung 0 plus whichever shared-deck rungs are usable, same ≥2-new-rungs floor.

---

## 7. Analyzer — why a second `summarize()`-shaped function exists

`scripts/carcasum_match/match.py`'s own `summarize()` (the one rung 1's harness already
runs and freezes) emits **`opp_driver_playouts_per_turn_mean`** only — a defect this
cell's brief names explicitly: the design text throughout this program (`PREREG.md`
§2.1 point 2, `LAUNCH_PROCEDURE.md` §5: *"Median, not mean, for playouts/turn"*)
demands the median, and `summarize()` does not compute it. **`match.py` is NOT edited
by this cell** — it is rung 1's already-frozen, already-blind-committed harness, and
retroactively changing its behavior would be exactly the kind of after-the-fact edit
this program's discipline exists to prevent. Instead,
[`scripts/carcasum_match/analyze_ladder.py`](../../scripts/carcasum_match/analyze_ladder.py)
is a new, separate readout tool (same relationship `jcz_match/analyze.py` has to
`jcz_match/match.py`'s own `summarize()` — see that file's own docstring for the
precedent) that recomputes win rate / paired margin / SEM from the raw per-game
records **and** the pooled per-move `carcasum_playouts` fields directly, reporting
**both median and mean**, per rung, before running the cross-rung fit(s).

**AMENDED (pre-launch):** the same file also computes the **within-deck slope**
(primary, §3) over the shared-deck rungs, the **aggregate WLS** (secondary witness,
unchanged from the pre-amendment design), and the **kill-only interim futility test**
(`--interim` mode, `READ_RULE.md` §5). `--selftest` exercises all three against
hand-computable numbers before any archive exists — the within-deck case constructs
three synthetic decks with KNOWN per-deck slopes (−1, −2, −0.5) and asserts the
recovered mean matches the hand-computed average exactly; the interim case exercises
"confidently wrong-signed fires", "right-signed never fires", and "wrong-signed but not
confident never fires" as three separate assertions.

---

## 8. SMOKE — G-MODE, executed pre-freeze, on this box, at zero band cost

**Requirement (this cell's brief): prove playout-budget mode works end-to-end through
the harness before freezing.** Executed 2026-08-23, in this worktree, against the
already-built local `carcasum_driver` binary from the rung-1 harness build
(`vendor/carcasum/build-driver/carcasum_driver` in the `carcasum-harness` worktree,
sha256 `99aebb4e69eebec…`, PROVENANCE unchanged from rung 1 — same binary, same patch
set, only the CLI opponent config differs). No laptop contact; no band claimed (dev-tier
throwaway seed `900000500000`, discarded, never pooled).

```
.venv/bin/python scripts/carcasum_match/match.py \
  --decks 1 --champ-seat both --workers 2 \
  --opp-playouts 1000 \
  --binary vendor/carcasum/build-driver/carcasum_driver \
  --seed-base 900000500000 \
  --out /tmp/rung2_smoke.jsonl
```

**Result — PASS, and stronger than the ±5% gate demands:**

- 2/2 games completed, `void=None` both, `replay_ok=True` both.
- `opponent={'playouts': 1000, 'budget_ms': None, ...}` — confirms `--opp-playouts`
  correctly nulls `budget_ms` (`mIsTimeout=0` behavior verified by inspection of
  `main()`, not merely assumed).
- **Pooled over all 71 real opponent turns across both games: min = max = median =
  mean = exactly 1000 playouts.** Every single realized `carcasum_playouts` value
  equalled `m` precisely — **0.0% deviation**, not merely inside the ±5% `G-MODE` bar.
  (This is expected and worth stating why: under `mIsTimeout=false` the driver's
  `MCTSPlayer` runs exactly `m` playouts and stops, with no clock involved, unlike
  rung 1's time-budget mode where the realized count is a *consequence* of the clock
  and varies enormously by ply. Playout-count mode is the more deterministic of the
  two, for the search width itself — the driver still nondeterministic in *which*
  moves it picks (no RNG seeding, PREREG.md's standing caveat, unaffected by this
  finding).)
- Raw archive kept for the record: `SMOKE_G_MODE_games.jsonl` in this directory (2
  lines, dev-tier seed, non-confirmatory).

**G-MODE gate, formally (also stated in `READ_RULE.md` §3): median realized
`carcasum_playouts` within ±5% of `m`, read from the pilot's own archive at the start
of each real rung — PASSED here at pilot scale (0.0% deviation, n=71 turns); the
per-rung pilot check at real scale is a `READ_RULE.md` §3 precondition, not assumed
transitive from this smoke.**

---

## 9. Close-out obligations

The six-touch checklist applies in full on read-out, unchanged from rung 1's own §6:
`experiments/results.csv` row → `DECISIONS.md` index line → status banner on this doc
→ governance row flip (`BAND_REGISTRY.csv`, `CLAIM_REGISTRY`) → `STATUS.md` top block
→ roadmap line in `docs/PROGRAM_ROADMAP_2026-07-07.md`. Then `python3
scripts/doc_lint.py`. Plus a `docs/LEVER_INDEX.md` row for *"Carcasum budget ladder /
rung 2"* regardless of outcome.
