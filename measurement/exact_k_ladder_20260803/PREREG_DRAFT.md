# F13 — Modern exact-K winrate ladder under fixed_v1 (PREREG DRAFT)

> **STATUS: ✅ RUN AND CLOSED 2026-08-05 — verdict in [READOUT.md](READOUT.md).** All four
> rungs landed uncensored on band 1.06e11; branch 2 fired on margin, the winrate question
> read null, the confirm was NOT bought, the endgame-net lever is stillborn. ⚠️ Known
> drafting defect recorded in the readout §5: this document's *question* is worded on WINS
> while its *decision-map thresholds* are written on paired MARGIN z — they can disagree,
> and here they did. Historical funding banner follows.
>
> **FUNDED 2026-08-04 (Joshua: "ok, f13 it is") — harness build in flight;
> no band claimed yet, nothing launched.** Launch order: identity smoke (K4-vs-K4 ×20,
> 100% action identity) → 10-game K6 bench-then-commit smoke (cap-hit rate + RSS + wall
> at the measured eval W\*) → rungs K2/K3/K5 daytime, K6 overnight, per-iter checkpointed
> (the local box's dirty-reboot cadence assumed). ⚖️ K3 rung RESOLVED: ADDED (the
> within-band trend is the primary statistic; a fifth point costs ~1–2 h).
> Original draft context: written 2026-08-03 while the rust solver bench was fresh.
> Charter: DECISIONS 2026-08-03 (afternoon) solver-port entry; cost basis:
> [../rust_solver_bench_20260803/BENCH.md](../rust_solver_bench_20260803/BENCH.md).

## Question

Does exact endgame play deeper than production buy **wins** (not margin) at today's
champion, under the adopted rules? The June null (DECISIONS 2026-06-24) is powered only
through K=3, is era-bound (RoD1/h3200 prefixes, v2.8 leaf, walled), and its winrate ladder
0.526 → 0.537 → 0.568 was monotone-up. This closes the question powered at every rung —
or fires the specialized-endgame-net lever (LEVER_INDEX) if winrate moves at K≥5.

## Design

- **Incumbent (both-sides base):** the production champion in clairvoyant matched-mode with
  its production exact tail **K≤4** (PRODUCTION.yaml: clairvoyant runs K≤4 identical both
  sides). Candidate = the same champion with the tail at **K = rung**.
- **Rungs:** K=2 (negative-control rung — *shallower* than production, expects ≤0),
  K=5, K=6 vs the K=4 incumbent. (K=4 vs K=4 is an identity, not a cell.)
  ⚖️ Option: add K=3 for a denser trend line (+1 cell cost).
- **n=400 deck-paired per rung** (200 decks × 2 seats), one fresh band per the registry
  (claim at launch; 1.05e11+ is free), all rungs on the SAME band → within-band
  deck-matched contrasts (the robust class). Solver = `carc_rs` (gates PASS; node-count
  equality means the python solver would agree on every solve that completes).
- **Rules:** fixed_v1 + `CARCASSONNE_FIX_R9=1` both sides, manifest-stamped (`r9_env_ok`).
- **Primary statistic:** deck-paired margin z per rung + the **within-band trend across
  rungs** (`feedback_trend_beats_underpowered_steps`); winrate secondary.

## The cap-hit branch (the part the June design lacked)

Per-position solve cost spans orders of magnitude (bench: 434 vs 74k nodes at equal K).
Pre-registered per-solve wall caps: **K≤4 uncapped · K=5 cap 300 s · K=6 cap 600 s.**
On cap hit the candidate's tail **falls back to the K−1 solve of the same position**
(never a raw leaf — the arm degrades toward the incumbent, biasing the measured effect
toward ZERO, i.e. conservatively). Every cap hit is counted in the manifest;
**if >20% of a rung's latch solves cap out, the rung reports "censored at rate r" and
its point estimate carries a ⚠️ not-a-verdict banner** regardless of z.

## Cost (bench-derived, pre-registered as an estimate not a promise)

Latch fires once per game per side + cheap TT-carried re-solves. Using bench p90s (not
medians): K=5 ≈ 1–5 min/game of tail, K=6 ≈ 3–10 min/game censored at 600 s. Two-box
W-wide (rust solves are ~100–250 MB/worker — cores-bound, not RAM-bound):
**K=2 rung ~1 h · K=5 ~2–4 h · K=6 ~4–8 h.** Whole ladder ≈ **1–2 box-days**;
schedule K=6 overnight. ⚠️ Bench-then-commit rider: run 10 games of the K=6 arm first
and check the realized cap-hit rate before launching the full rung.

## ⚠️ Amendment 2026-08-04 (BEFORE any cell ran): the ladder runs at the A/B screen budget, not the deploy budget

The cells run at **SIMS=2750**, the standing "champion-sibling A/B knobs (C5/C7)" used by the
CL-074 component table and every leaf-ablation cell — **not** the champion's deploy budget
k8×1376 = 11008. Both arms share it, so every contrast is matched; but the question as worded
("at today's champion") is answered at a *weaker sibling* of today's champion, and that changes
what each branch of the decision map is allowed to conclude. Stated now, before results exist:

- **A NULL at 2750 is the STRONGER conclusion, and it transfers.** A weaker prefix search is
  worse in the endgame, so an exact tail has *more* room to help here than at 11008. If deeper
  exactness cannot beat a 2750-sim search, it will not beat an 11008-sim one. Branch 1 therefore
  fires as written.
- **A POSITIVE at 2750 does NOT transfer and does NOT by itself fund anything.** It is the
  known low-sims inflation pattern (memory `feedback_sims_washout_net_eval`: +82.8/z3.48 at
  sims200 → +8/z0.34 at sims800, same nets). Branch 2 is therefore **amended**: a K≥5 rung at
  ≥+2σ buys a **confirm cell at the deploy budget 11008 on fresh decks of a new band**, and only
  a confirm that survives funds the endgame net.

Rationale for not simply running at 11008: 4× the budget on the two expensive rungs, against a
prior (the June ladder + the F3 fair-optimum ceiling) that strongly favours the null — the cheap
screen answers the likely outcome, and the expensive confirm is bought only if the screen surprises.

## Decision map (pre-registered)

1. **All rungs' paired-margin z < +2 and the trend slope z < +2** → the June null
   generalizes, powered, modern-era: exact:K row gets its final stamp; the endgame-net
   lever is STILLBORN (ceiling argument); no further endgame-exactness work.
2. **K≥5 rung ≥ +2σ (uncensored) or trend z ≥ +2** → deeper endgame exactness is real
   at the modern champion: fund the endgame-net design (fair labels = marginalized —
   the expensive mode; bench prices that next) and/or evaluate shipping a deeper
   clairvoyant tail where mode permits.
3. **Censored-positive** (signal but cap-hit rate >20%) → raise caps ×3 on the affected
   rung only, n=200 re-run, then re-enter this map.
4. K=2 control rung reads **>+2σ** (shallower beats production) → instrument alarm:
   halt, audit the harness before interpreting anything.

## Identity gate: RESULT + a recorded deviation (2026-08-04)

**PASS at 17/20 games, 0 divergences** — not the pre-registered 20/20. What the gate actually
compares is stronger than the prereg's wording: not "the K4 arm vs the K4 arm", but **the new
F13 rust tail vs the pre-F13 inline PYTHON tail**, move for move (`f13_smoke.py:120-127`).
17 games × ~142 plies ≈ 2,400 plies of exact action agreement, 4 latch solves/game, across
4 independent seed families.

**Why it stopped at 17 (Joshua: "let's move on"):** the smoke's *reference* arm runs
**uncapped** (`caps={}`, `k_floor=0`) while the F13 arm is capped — so a single pathological
clairvoyant K4 position in the ~20×-slower python solver blocks its shard indefinitely. One
shard produced 0 games in 3.5 h, then 1 in 7.5 h. The block is in the REFERENCE arm, not in
anything under test.

**Why 17 is sufficient, stated as a falsifiable claim:** an identity failure here would be
*systematic* (a wiring bug diverges at ply 1 of game 1, not at game 18), and — the load-bearing
point — **this gate never exercises the capped/fallback path at all**, since K≤4 is uncapped by
construction. The risky new code (cap → K−1 fallback → recursion → counters) is covered by
`tests/test_f13_exact_ladder.py`, not by these games, so games 18-20 would have added zero
coverage of it. If that reasoning is wrong, the failure mode it misses is a divergence that
appears only on rare positions — which the ladder's own per-cell manifests would surface as
anomalous latch counts.

**Free side-measurement:** the rust tail ran **4–10× faster** than the python tail it replaces
on identical positions (per-game pairs: 130.1s/1346.6s, 81.3s/322.7s, 71.2s/354.4s). This is
the direct confirmation that the pre-F13 harness silently ran the python solver under
`--backend rust` — the defect that would have made the K5/K6 rungs infeasible.

## Analysis (pre-registered 2026-08-04)

**The analysis script was written and committed BEFORE any cell ran** — that is the point
of putting it here. It is [`scripts/classical_search/analyze_f13_ladder.py`](../../scripts/classical_search/analyze_f13_ladder.py),
tested by [`tests/test_analyze_f13_ladder.py`](../../tests/test_analyze_f13_ladder.py)
(23 tests). The exact invocation, fixed now:

```bash
python3 scripts/classical_search/analyze_f13_ladder.py \
    --out-root /mnt/c/carc-shared/exact_k_ladder --band 106000000000 \
    --verdict-json measurement/exact_k_ladder_20260803/VERDICT.json
```

(`--band` is what keeps the throwaway smoke bands out; substitute the band actually
registered at launch. It emits the markdown table on stdout and `VERDICT.json` beside it.)

What it does, all fixed in advance:

- **Recomputes every per-rung statistic from the per-game records** (`seed<012d>_a<seat>.json`)
  — n / W-D-L / winrate, elo ± 1σ, deck-paired seat-balanced margin + paired z, cap-hit
  counters — and then **cross-checks against `summary.json`**, surfacing any disagreement
  as a warning rather than silently preferring one.
- **Censoring comes from `exact_tail`'s own functions** (`censored_rate` /
  `censored_rate_capped` / `is_censored`), never a second copy. Any rung above
  `CENSOR_THRESHOLD` is stamped **⚠️ NOT-A-VERDICT regardless of z**, and is excluded
  from the deciding trend fit (a statistic a not-a-verdict rung feeds inherits the banner;
  the all-rungs fit is still printed, labelled diagnostic-only).
- **Primary statistic = the within-band, deck-matched trend.** For each deck shared by all
  entering rungs it takes the within-deck OLS slope of the seat-balanced margin against K,
  and reports mean ± sd/√S. If the decks are *not* shared across rungs — or the rungs span
  more than one band — it **refuses to report a trend** rather than substituting an
  across-cell regression that ignores the CRN structure the design rests on.
- **Decision map, in the pre-registered precedence.** Branch 4 (K=2 control > +2σ, or the
  incumbent arm hitting a wall cap) is checked FIRST and suppresses every other conclusion.
  Then branch 2 (K≥5 uncensored ≥ +2σ, or trend z ≥ +2 — which per the 2026-08-04 amendment
  buys an **11008-budget confirm on a fresh band**, not the endgame net), then branch 3
  (censored-positive), then branch 1 (the powered null). If the trend is unavailable or any
  rung is unreadable/censored, it prints **INCOMPLETE** instead of claiming branch 1.
- **Power beside every estimate** — realised 1σ and the 2σ MDE per rung, plus the standing
  n=400-paired ≈ ±12 elo figure — so a null is never over-read as "no effect".

**Prereg defects found while implementing it** (flagged here rather than after results):

1. **Which rungs enter the trend was not specified.** Decided now: all *uncensored* rungs,
   K=2 control included (it is a legitimate ladder point, and excluding it would discard
   the design's own anchor).
2. **Whether the K=4 identity enters the fit was not specified.** Decided now: **NO** by
   default (`--include-identity-anchor` exists but is off) — K=4 is an identity, not a
   measured cell, and a zero-variance anchor would shrink the SE of a slope no data supports.
3. **Branch precedence when several branches fire was not specified** (e.g. one uncensored
   K≥5 positive *and* one censored K≥5 positive). Decided now: 4 → 2 → 3 → 1, with branch 3
   still reported as an additional action on the censored rung.
4. **"z" was not defined as one- or two-sided.** Decided now: the ≥ +2σ triggers are
   **one-sided on a signed statistic**, positive = deeper exactness helps. A large *negative*
   read is not branch 2 and is not branch 4 either — it is a null for the funding question.
5. **The prereg says "+2σ" for the rungs but "trend slope z ≥ +2" for the trend**; treated
   as the same threshold (`Z_FIRE = 2.0`).

**Emitter facts that differ from what the prereg assumes** (parser is written to the emitter,
not to the prose):

- `manifest.json → config.candidate.exact_k` and `config.opponent.exact_k` **both stamp the
  CANDIDATE's K**. The incumbent's K is only correct in `config.exact_tail.opp_exact_k`, which
  is what the analysis reads. (Cosmetic-but-misleading manifest defect in `eval_puct_priors`.)
- `manifest.json → config.backend.unconverted` still asserts the exact-K tail "stays Python on
  both sides" — pre-F13 prose, now false under `--exact-solver rust`. Stale, not load-bearing.
- The strength stats exclude watchdog-abandoned games (`game_timeout`) while the censoring
  counters deliberately **include** them; the analysis mirrors that split exactly.

## K6 bench-then-commit rider: RESULT — the rung is fundable (2026-08-04)

9 games (of a planned 10) of the K=6 arm, 5 shards, rust solver, caps 5:300/6:600, floor 4:

| latch solves | capped attempts | cap hits | **rate (prereg denominator)** | rate over capped | peak RSS | wall/game |
|---|---|---|---|---|---|---|
| 52 | 16 | 2 | **0.038** | 0.125 | 392 MB | 190–912 s |

**Verdict: NOT censored — launch K6 at the configured W.** 0.038 against a 0.20 threshold.

Two reasons this is decisive despite the missing 10th game and the sharded (contended) measurement:
1. **The bias is one-sided and points the safe way.** Sharding inflates walls, which inflates
   cap-hits; the measured rate is therefore an OVER-estimate. Under 0.20 while contended ⇒
   under 0.20 clean.
2. **The 10th game cannot flip it.** Worst case — every one of its ~6 latch solves caps out —
   gives 8/58 = 0.138, still under threshold. The game was killed rather than waited on
   (Joshua: "do we even care about the last game?"); it could not have changed the decision.

**W sizing (the rider's other job):** peak 392 MB/worker. A capped solve forks a child, so a
worker slot can transiently hold two resident processes (~784 MB worst case) — but the fork is
fork-and-WAIT (parent blocks, observed at ~49% CPU while its child computes), so concurrency
stays bounded at W and does not oversubscribe. At W=30 against 37 GB available, RAM is not
binding. **No new W sweep: the F7d re-sweep's measured local W\*=30 / laptop W\*=26 stand**
(they beat the threads−2 policy default, which applies only absent a measured W\*).

## Falsifiers / guards

- Identity smoke before the ladder: K=4-vs-K=4, 20 games, must be 100% identical actions.
- Per-cell manifest: leaf hash both sides, profile, r9, caps, cap-hit counts, solver mode.
- The fair agent's production K≤2 marginalized latch is untouched by all of this.

**No results.csv row, no claim id, no PRODUCTION.yaml change until run + verdict.**
