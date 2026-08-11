# ADAPTIVE-K PRE-GATE CENSUS — across-world disagreement and duplicate worlds, by phase

**STATUS: COMPLETE (2026-07-28). 898/898 roots censused, 0 failures, 362 s at W14 local.
No game was played, no opponent, no band consumed, `governance/PRODUCTION.yaml` untouched.**

**GATE VERDICT: ❌ FAIL — the phase-adaptive k schedule DIES FREE. Do not fund a build.**
The lever's own stated mechanism (*"k should track ACROSS-WORLD VALUE DISAGREEMENT"*) is
**flat by phase**: per-decision across-world value spread is 0.092 / 0.096 / 0.092
(early / mid / late), every contrast |z| < 0.6, and it stays flat inside both TILES and
MEEPLES (early−late z −0.01 and −0.27). The decision-relevant version — how often worlds
3–4 actually **change the pooled pick** — is likewise flat at **7.0 / 6.1 / 8.4 %**
(early−late z −0.59). And the duplicate-world prize is arithmetically negligible:
exact duplicates are **0.00 % for every k_remaining ≥ 8**, total wasted budget is
**0.93 % of all search compute**, which at CL-068's calibration (2× compute = +12.2 elo)
is worth **+0.16 elo** if reclaimed *perfectly and for free*.

Two findings cut **against** the row's prior rather than merely failing to support it:
the row expected *"early-game disagreement may be small (substitutable tiles)"* — early is
in fact the phase with the **most** across-world disagreement; and it expected late-game
worlds to be wasteful — late is in fact where extra worlds change the pooled decision
**most often** (k2≠k4: 16.7 % late vs 10.6 % mid, z +2.16). A schedule that trimmed k late
to buy depth would be cutting where the ensemble is worth most.

Pre-gate pre-registered in the **phase-adaptive k schedule** row of
[docs/LEVER_INDEX.md](../../docs/LEVER_INDEX.md) ("*replay archived champion games, per-move
census of (a) root-value spread across the k worlds, (b) duplicate-world rate, by phase —
if disagreement is flat, dies free*"). Harness
`scripts/measurement_infra/adaptive_k_census.py`; tests `tests/test_adaptive_k_census.py`;
outputs `/mnt/c/carc-shared/classical_search/adaptive_k_census/{rows,summary,manifest}_main.*`.

---

## What was measured, and on what

**Positions.** All **898 roots** of the CL-070 move-agreement bank
(`/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl`) — sampled from
449 complete fair-PIMC k4×688 champion self-play games, `(deck_seed, actions)` lossless
replay via `scripts/measurement_infra/root_replay.py`. Every root's replayed board was
**checksum-verified** against the bank's stored `string_representation` (898/898 match), so
this census and CL-070 are looking at bit-identical positions. Forced moves are already
excluded by the bank's eligibility rule (the fair agent short-circuits them without
searching). Phase cuts are the bank's own, reproduced verbatim including its boundary quirk
(k=48 and k=24 fall through to "late").

**25 of the 898 roots are at k_remaining ≤ 2**, where `FairHeuristicPriorAgent` has latched
to the marginalized exact solver and draws **no determinizations at all**. They are outside
any k schedule by construction and are **excluded from every table below** (`n = 873` live).

**Worlds.** For each root, 4 worlds drawn with the champion's exact
`FairHeuristicMCTSAgent.reshuffled_determinization` semantics (canonical sort of the unseen
deck, then `rng.shuffle`; `next_tile` untouched), off a dedicated seed lineage
(`salt=20260728`, disjoint from CL-070's 9000/9001 tag salts).

**Searches.** Each of the 4 worlds got a full **production-budget** search — 688 sims, the
production `HeuristicPriorConfig` (c_puct 1.5, τ_p 5, curve125 v2.9 leaf, champion
`puct_priors_v29_bmild_cap8`) — i.e. literally the searches the champion runs on that move.
Per world we read its own best-action value (root-POV best-child Q, alias-deduped exactly
as `pool_root_stats` does) and its own pick (argmax visits = production `final_select`).
Pooled picks at k=1/2/3/4 use the production `pooled_q_argmax` with the min-visits floor.

**Noise floor: none, and this is verified, not assumed.** `NeuralMCTS` consumes its rng
only in `_reshuffled_root` and `sample_action`, neither of which runs on this path, so a
per-world search is deterministic. `--noise-control` re-searched world 0 under a different
seed on every root: **898/898 produced a bit-identical root-child table.** All spread
reported below is therefore world-induced, with no search-noise component to subtract —
which matters, because a phase-varying noise floor would otherwise be able to manufacture
exactly the phase structure this gate is looking for.

---

## Census (a) — across-world disagreement, by phase

| phase | n | med k_rem | med n_legal | **v_std (mean)** | v_range (med) | distinct picks /4 | worlds disagree on best move | **pooled pick k2≠k4** | **pooled pick k3≠k4** | pooled top-2 Q gap (med) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **early** | 298 | 61 | 7 | **0.092** | 0.171 | 1.51 | 39.9 % | 13.1 % | **7.0 %** | 0.065 |
| **mid** | 312 | 37 | 19 | **0.096** | 0.153 | 1.38 | 29.8 % | 10.6 % | **6.1 %** | 0.066 |
| **late** | 263 | 15 | 24 | **0.092** | 0.116 | 1.33 | 24.0 % | 16.7 % | **8.4 %** | 0.050 |
| **all live** | 873 | 38 | 11 | **0.093** | 0.147 | 1.41 | 31.5 % | 13.3 % | **7.1 %** | 0.060 |

68 % Wilson intervals and the phase contrasts that the gate actually turns on:

| quantity | early | mid | late | early−mid | mid−late | **early−late** |
|---|---:|---:|---:|---:|---:|---:|
| **value spread `v_std`** (Welch) | 0.0921 ± 0.0036 | 0.0957 ± 0.0056 | 0.0924 ± 0.0073 | z −0.54 | z +0.36 | **z −0.04** |
| worlds disagree on best move | 39.9 % [37.1, 42.8] | 29.8 % [27.3, 32.5] | 24.0 % [21.4, 26.7] | z +2.63 | z +1.57 | **z +4.03** |
| **pooled pick k2≠k4** | 13.1 % [11.3, 15.2] | 10.6 % [9.0, 12.4] | 16.7 % [14.6, 19.2] | z +0.96 | z **−2.16** | z −1.21 |
| **pooled pick k3≠k4** | 7.0 % [5.7, 8.7] | 6.1 % [4.9, 7.6] | 8.4 % [6.8, 10.2] | z +0.48 | z −1.06 | **z −0.59** |
| pooled pick k1≠k4 | 21.1 % | 18.6 % | 22.1 % | — | — | flat |

**Mix control.** The phase strata are not balanced between tile and meeple decisions, so
every contrast is repeated *within* game phase. Nothing changes:

| within | v_std early/mid/late | early−late z | argmax-disagree early/mid/late | early−late z | k3≠k4 early/mid/late | early−late z |
|---|---|---:|---|---:|---|---:|
| **TILES** (n=480) | 0.084 / 0.080 / 0.084 | **−0.01** | 52.7 / 44.1 / 33.3 % | +3.39 | 9.5 / 7.8 / 10.5 % | −0.29 |
| **MEEPLES** (n=393) | 0.100 / 0.117 / 0.104 | **−0.27** | 27.3 / 10.5 / 10.9 % | +3.25 | 4.7 / 3.8 / 5.5 % | −0.29 |

### Reading it

1. **The lever's named mechanism is flat.** Across-world *value* spread does not vary by
   phase — not overall (|z| ≤ 0.54), not within TILES (z −0.01), not within MEEPLES
   (z −0.27). There is no phase signal for a k schedule to track.
2. **The one quantity that does vary is not the one that prices reallocation.** Per-world
   *pick* disagreement falls hard from early to late (39.9 % → 24.0 %, z +4.03, and it
   survives the mix control). But it does not propagate to the pooled decision: whether
   worlds 3–4 change the pooled pick is flat at 6–8 % everywhere. Worlds disagree about
   the best move early, and the pool absorbs the disagreement without changing its answer.
3. **Where it does vary, it points the wrong way.** k2≠k4 is *highest* late (16.7 %,
   mid−late z −2.16). The proposed schedule wants to spend fewer worlds late to buy depth;
   late is where the 3rd and 4th worlds are worth the most.
4. **The row's early-game premise is refuted, not just unsupported.** The row predicted
   *"early-game disagreement may be small (substitutable tiles)"*. Early is the **highest**
   disagreement phase on every per-world measure. Substitutable tiles evidently make worlds
   *look* different without making the pooled answer different.
5. **The ensemble as a whole is doing real work, uniformly.** k1≠k4 is 20.5 % overall and
   flat across phases — one world would give a different answer on a fifth of decisions.
   That is a reason k=4 exists (and CL-054 already measured it); it is not a reason for k
   to *vary*.

---

## Census (b) — duplicate-world rate (exact, no proxy)

Because `reshuffled_determinization` canonicalizes the unseen deck before shuffling, a
world **is** its deck-description ordering; two worlds are identical iff those orderings
are equal. This half of the census is therefore exact combinatorics, not an estimate.
Rates below are averaged over **32 independent 4-world groups per root** drawn from the
same continuing seed lineage (group 0 being the searched group), so the per-decision
duplication probability is measured to ~±1 % even in the thin low-k bands.

| k_remaining | n | med deck | **any 2 worlds IDENTICAL** | **wasted worlds / decision (of 4)** | same next tile | same next 2 | same next 3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3–5 | 27 | 3 | **72.7 %** | **1.150** | 99.1 % | 77.9 % | 72.7 % |
| 6–9 | 36 | 6 | 4.3 % | 0.043 | 79.7 % | 27.1 % | 9.5 % |
| 10–15 | 75 | 12 | **0.00 %** | 0.000 | 56.7 % | 9.1 % | 1.0 % |
| 16–23 | 96 | 19 | **0.00 %** | 0.000 | 43.2 % | 4.9 % | 0.4 % |
| 24–35 | 153 | 29 | **0.00 %** | 0.000 | 36.8 % | 3.0 % | 0.3 % |
| 36–47 | 174 | 40 | **0.00 %** | 0.000 | 32.4 % | 2.0 % | 0.1 % |
| 48+ | 312 | 59 | **0.00 %** | 0.000 | 28.2 % | 1.7 % | 0.1 % |
| **all live** | **873** | — | **2.42 %** | **0.037** | 38.9 % | 6.4 % | 2.9 % |

Onset is abrupt and very late: k=7 → 2.8 %, k=6 → 9.9 %, k=5 → 26.3 %, k=4 → 73.7 %,
k=3 → 100 %. **Every k_remaining ≥ 8 is exactly 0.00 %.**

| phase | n | any 2 identical | wasted / decision | same next tile |
|---|---:|---:|---:|---:|
| early | 298 | 0.00 % | 0.000 | 28.1 % |
| mid | 312 | 0.00 % | 0.000 | 34.4 % |
| **late** | 263 | **8.04 %** | **0.124** | 56.7 % |

### The whole prize, priced

| | |
|---|---|
| live (non-latched) decisions | 873 |
| decisions with any duplication at all | 2.42 % |
| decisions in the k ≤ 5 band where duplication is severe | **27 / 873 = 3.1 %** |
| decisions in k ≤ 9 (all duplication lives here) | 63 / 873 = 7.2 % |
| decisions at k ≥ 10 | 92.8 %, **0.000 wasted worlds** |
| mean wasted worlds per decision | 0.0374 of 4 |
| **⇒ share of ALL fair-search compute lost to duplicate worlds** | **0.93 %** |
| ⇒ value if reclaimed perfectly and for free (CL-068: 2× compute = +12.2 elo) | **+0.16 elo** |

The "late-but-pre-latch small bag" the row describes is real — at k ≤ 5 the agent genuinely
searches the same world 1.15 times over per decision — but that band is **27 decisions out
of 873**, sitting 1–3 plies before the exact solver latches at K ≤ 2 and takes over anyway.
De-duplicating it perfectly recovers under one percent of one game's search budget.

The `same next tile` column is high everywhere (28 % early → 57 % late) and is **not** waste:
those worlds diverge from tile 2 onward, and a 688-sim search sees far more than one draw.
It is reported because the row asked for near-identity at N = 1, 2, 3; the decision-relevant
columns are `same next 2/3`, which are ≤ 2 % outside the k ≤ 9 band.

---

## Proxy status and limitations (read before quoting any number)

This census is **not** a shallow proxy on the search side — the per-world searches are at
the production budget with the production evaluator, and the noise floor is verified to be
exactly zero. The limitations are elsewhere, and the third one is the important one:

1. **Seed lineage, not the literal in-game draw.** `champ_games.jsonl` records
   `(deck_seed, actions)` but **not the agent's per-game seed**, so the champion's actual 4
   worlds at a given ply are not reconstructible. Worlds are redrawn with the champion's
   exact determinization semantics from a dedicated salt. Because the canonicalized
   reshuffle makes a world a pure function of (unseen multiset, rng), the redraw is
   *distributionally* the champion's own draw — but a per-root number here is "a draw the
   champion could have made", not "the draw it made". Only the census is valid, not any
   individual row. (This is the one place the roots bank falls short of a literal replay;
   it does not affect any aggregate below.)
2. **Nested prefixes, not independent k-ensembles.** `pick_k2` pools worlds {0,1} of the
   same 4-draw, so `k2≠k4` measures the **marginal information of adding worlds 3–4**. That
   is the lever's mechanism, but it is **not** a k2-vs-k4 strength comparison — that is
   CL-054, already measured (k4 optimal, k4−k2 z +1.33).
3. **⚠️ No re-budgeting — this census measures the SIGNAL, it cannot price the TRADE.**
   Sims-per-world is held fixed at 688. A real phase-varying k at fixed *total* budget
   would give each world proportionally **more** sims wherever k is smaller, and this
   census does not simulate that deeper search. So a **positive** census would have been
   only permission to build and measure, never evidence of gain. The verdict below leans
   entirely on the census being **flat/negative**, which this asymmetry does not rescue:
   there is no phase-varying disagreement signal for a schedule to exploit *regardless* of
   how the reclaimed sims would have been spent.
4. **Statistical honesty.** At n ≈ 300 per phase, a 6–8 % rate carries a 68 % half-width of
   ~1.3 pp; these tables can exclude a *large* phase effect on the marginal-world rate, not
   a 2 pp one. The value-spread nulls are tighter (|z| < 0.6 on n ≈ 300 with a zero noise
   floor). No claim here is that the effect is exactly zero — the claim is that it is far
   too small and too directionally wrong to justify a build.

---

## Gate verdict

**❌ FAIL. The phase-adaptive k schedule does not have a mechanism. It dies free — no build
funded, no `PRODUCTION.yaml` change proposed, no `results.csv` row (nothing was played).**

Against the row's own pre-registered gate ("*if disagreement is flat, dies free*"):

| the row's mechanism claim | what the census found | verdict |
|---|---|---|
| k should track across-world **value** disagreement | value spread flat: 0.092 / 0.096 / 0.092, all \|z\| < 0.6, flat inside TILES (z −0.01) and MEEPLES (z −0.27) | **flat → dies** |
| early-game disagreement may be **small** (substitutable tiles) | early is the **highest**-disagreement phase (39.9 % vs 24.0 % late, z +4.03) | **refuted** |
| late-but-pre-latch, k4 samples **duplicate** worlds (pure waste) | true but tiny: 0.00 % for all k ≥ 8; whole prize 0.93 % of compute = **+0.16 elo** | **true, worthless** |
| a phase-varying k at fixed total could **reallocate** | the marginal-world rate is flat (7.0 / 6.1 / 8.4 %, z −0.59) and where it varies it favours **more** k late, not less | **no direction to move in** |

The row's own prior was already SMALL ("every allocation contrast measured is thin,
k4−k2 z 1.33"). The census does not overturn that prior in either direction; it removes the
mechanism that would have justified spending measurement on it. Consistent with the day's
other allocation results — CL-068's budget closure, the G2 refutation, and the C3-intra
park — the fair-search allocation axis continues to return nothing.

**Re-open bar** (so this is parked with a key, not sealed): a *different* per-decision
statistic that (i) varies by phase with |z| > 3 after the TILES/MEEPLES mix control, and
(ii) is shown to move the **pooled** decision, not just the per-world picks. The obvious
candidate this census rules out is value spread; the obvious candidate it leaves open is
something conditioned on the *pooled top-2 Q gap* rather than on phase (that gap does drift,
0.065 / 0.066 / 0.050) — but that would be a **gap-adaptive**, not phase-adaptive, k, i.e. a
different lever needing its own row and its own pre-gate.

---

## Reproduce

```bash
nice -n 19 .venv/bin/python -u scripts/measurement_infra/adaptive_k_census.py \
    --workers 14 --dup-replicates 32 --noise-control \
    --out-dir /mnt/c/carc-shared/classical_search/adaptive_k_census --tag main
```

362 s at W14 on the local 5900XT box. Outputs: `rows_main.jsonl` (one row per root),
`summary_main.json` (all strata), `manifest_main.json` (resolved config, seed lineage,
limitations). Log: `measurement/classical_search/adaptive_k_census.log`. Unit tests for the
pure parts (world-seed determinism and salt disjointness, the description-shuffle ≡
tile-shuffle equivalence the duplicate census rests on, duplicate/prefix detection, the
pooled-Q prefix picks, the stratified sampler, the bank's phase-cut quirk):
`tests/test_adaptive_k_census.py` — 33 tests, all pass.
