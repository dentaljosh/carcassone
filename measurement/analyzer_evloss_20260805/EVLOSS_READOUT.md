# F12 slice 2a — per-move EV-loss readout (2 E4 games)

**Status: RAN 2026-08-05. Acceptance gate PASS on both games.** Built to
[EVLOSS_SPEC.md](EVLOSS_SPEC.md) (pre-registered; D1 units / D2 measured buckets / D3 exact
tail separate / D4 confounds). Tool: `scripts/analyzer/ev_loss.py`; tests
`tests/test_analyzer_evloss.py`. This is **analysis tooling — it makes no strength claim and
touches no production config.**

Artifacts (the source of truth; every number below cites a field of one of them):

| game | archive | JSON | markdown |
|---|---|---|---|
| g1 | `measurement/e4_games/1785205383_867966.json` | [EV_LOSS_g1_867966.json](EV_LOSS_g1_867966.json) | [EV_LOSS_g1_867966.md](EV_LOSS_g1_867966.md) |
| g2 | `measurement/e4_games/1785466497_161583.json` | [EV_LOSS_g2_161583.json](EV_LOSS_g2_161583.json) | [EV_LOSS_g2_161583.md](EV_LOSS_g2_161583.md) |

Grading config, both games (`budget`, `integrity`): rules profile **`walled`** resolved from
the archive's `start_rule`/`grid_rule` (both null ⇒ pre-2026-08-01 engine-of-record epoch),
budget **k4×688 = 2752/move** = `budget.source: "archive sims_effective/k_dets_effective"`,
grading seed 12345, calibration seed 777, Rust backend, leaf
`integrity.leaf_hash_runtime = a36d2e15a3b3d71d` (`leaf_hash_ok: true`),
`integrity.replay_scores_match: true`, `integrity.mirror_desync_events: 0`,
`integrity.n_unrated_pimc: 0` on both.

---

## 1. The acceptance gate (ran BEFORE any human number)

Spec "What would make this wrong": if the champion seat's own mean EV loss is not near the
calibration null, the grader is mis-wired and no human number is reportable.
Criterion shipped: `acceptance_gate.champion_mean_delta_q <= acceptance_gate.null_p95`.

| game | champion mean ΔQ | (sem) | null p95 | `acceptance_gate.pass` |
|---|---:|---:|---:|:--|
| g1 | 0.00827 | 0.00291 | 0.04718 | **true** |
| g2 | 0.01315 | 0.00475 | 0.12452 | **true** |

Both pass with room: the champion seat's residual loss is ~1/6 (g1) and ~1/9 (g2) of the
instrument's own p95 noise, and `≈0.8×` / `≈0.7×` its *mean* (`buckets.null.dist.mean` =
0.01042 / 0.01854). That is what "the grader agrees with the agent that generated the moves"
looks like, and it is the independent evidence that the `walled` profile was the right choice
— together with `integrity.replay_scores_match: true`, i.e. the desktop replay under that
profile reproduces the phone's recorded scores exactly ([111, 113] and [73, 108],
`integrity.final_scores_replayed` == `integrity.recorded_scores`).

## 2. Read this first (D4 — the confounds, not corrected for)

Full list in each artifact's `confounds` block. The four that bound every number below:

1. **Same-family self-preference.** The grading agent *is* the agent that played the game —
   same leaf, same search, same budget. It structurally prefers its own moves. **The human's
   absolute EV loss is not reportable; only the paired human-vs-champion contrast on the same
   board is.**
2. **n = 2 games.** This describes two games of Joshua's play. It is not an estimate of a
   player.
3. **ΔQ is dimensionless (D1).** Q = W/N is a mean of `tanh(virtual_score/15)`, not points.
   `delta_points_tanh_est` is a monotone readability rescaling — never quote it as "you lost N
   points". (This retracts the "Q is natively in expected-margin points" sentence in
   `BACKLOG.md:591` / `ANALYZER_REPORT.md`.)
4. **Buckets are epoch-local.** Thresholds are the measured null of *this* corpus at *this*
   budget with *these* two seeds. A fixed_v1 / k8×1376 archive needs its own calibration
   before its bucket labels mean anything.

Two more, both in the artifacts: eligibility censoring would bias both seats' means *downward*
(it did not fire here — `integrity.n_unrated_pimc: 0` on both games), and exact-tail points are
a different instrument from ΔQ and are never pooled with it.

## 3. THE HEADLINE — paired EV loss, same board, same deck, same budget

`summary.<seat>.mean_delta_q`, over rated non-forced non-exact plies:

| game | seat | rated plies | agree rate | **mean ΔQ** | sd | p95 | max | mean pts (tanh est) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| g1 | human (0) | 61 | 0.5082 | **0.02507** | 0.05139 | 0.0995 | 0.2798 | 1.195 |
| g1 | champion (1) | 66 | 0.7273 | **0.00827** | 0.02367 | 0.0690 | 0.1083 | 0.277 |
| g2 | human (0) | 60 | 0.4500 | **0.03927** | 0.07269 | 0.1869 | 0.2747 | 0.926 |
| g2 | champion (1) | 63 | 0.7302 | **0.01315** | 0.03770 | 0.1312 | 0.1557 | 0.249 |

**The human seat loses ~3× the champion seat's EV per move, in both games independently:
3.03× (g1) and 2.99× (g2).** The median human ply is still a zero-loss ply
(`summary.human.delta_q_dist.p50` = 0.0 in g1, 0.00021 in g2) — the gap is carried by a tail,
not by uniformly worse play. The human's agree rate (the search's own best action) is 0.51 /
0.45 against the champion's 0.73 / 0.73.

**Is the gap distinguishable from noise? Marginally, and it replicates.** Computed from
`summary.<seat>.mean_delta_q` and `.delta_q_dist.sd` / `.n_rated` (unpaired across seats within
a game — plies are not paired, so this is the honest, not the tightest, comparator):

| game | human − champion | se | z |
|---|---:|---:|---:|
| g1 | +0.01680 | 0.00720 | **+2.33** |
| g2 | +0.02612 | 0.01052 | **+2.48** |

Each game clears 2σ on its own and the two are independent games, which is why the ~3× is
reported at all. But **z≈2.3–2.5 is a screen, not a verdict** by house standards, and the ratio
itself is far less stable than the two matching values suggest — 3.03 and 2.99 agreeing to two
decimals across games with these error bars is a coincidence, not a replicated constant. Read
the finding as "the human seat's per-move disagreement cost is materially higher, ~2–4×",
never as "3.0×".

Do NOT read the ~3× as "three times worse a player". It is three times the per-move
disagreement-cost *as priced by the champion's own 2752-sim search*, with confound 1 pushing
the champion seat's figure down by construction.

## 4. Bucket census (thresholds MEASURED, D2)

Thresholds are the quantiles of the calibration null = `|ΔQ(seed 12345) − ΔQ(seed 777)|` on
the same played action (`buckets.null`):

| game | null n | null mean | **p95 → `inaccuracy` cut** | **p99 → `blunder` cut** | best-action agreement between passes |
|---|---:|---:|---:|---:|---:|
| g1 | 127 | 0.01042 | **0.04718** | **0.13979** | 0.8268 |
| g2 | 123 | 0.01854 | **0.12452** | **0.16807** | 0.7236 |

g2's instrument is ~2.6× noisier at p95 than g1's, so its bar for "blunder" is much higher —
which is exactly why the thresholds are measured per artifact and are not portable.

`summary.<seat>.buckets` / `.bucket_frac`:

| game | seat | agree | within_noise | inaccuracy | **blunder** |
|---|---|---:|---:|---:|---:|
| g1 | human | 31 (0.508) | 18 (0.295) | 10 (0.164) | **2 (0.033)** |
| g1 | champion | 48 (0.727) | 13 (0.197) | 5 (0.076) | **0 (0.000)** |
| g2 | human | 27 (0.450) | 22 (0.367) | 6 (0.100) | **5 (0.083)** |
| g2 | champion | 46 (0.730) | 13 (0.206) | 4 (0.063) | **0 (0.000)** |

**The champion seat produced zero blunders in either game; the human produced 2 and 5.** Seven
blunder-class moves across 121 rated human plies = 5.8%. Given confound 1, treat the *count
asymmetry* (7 vs 0) as the finding and the *rate* as an upper-bounded description of two games.

## 5. Exact tail (k_remaining ≤ 2 — TRUE final-score points, D3)

Graded with `endgame_solver.solve(mode="marginalized")` → `regret_of()`. Forced plies (one
legal action) are excluded from this block as from every other. `exact_tail.<seat>`:

| game | seat | plies | played optimally | mean regret (pts) | max | total |
|---|---|---:|---:|---:|---:|---:|
| g1 | human | 2 | 1 | 0.50 | 1.0 | 1.0 |
| g1 | champion | 2 | 2 | 0.00 | 0.0 | 0.0 |
| g2 | human | 1 | 1 | 0.00 | 0.0 | 0.0 |
| g2 | champion | 1 | 1 | 0.00 | 0.0 | 0.0 |

The entire measured endgame cost across both games is **1.0 point**, at g1 ply 140
(`exact_tail.human.plies[0]`: k_remaining 1, 28 legal, played 1663, six optimal actions
1565/1566/1567/1629/1630/1631, 10,291 solver nodes). g1 finished 111–113 — that single point
is not the game, but it is half the margin. **Never add these to the ΔQ table**: different
instrument, different scale.

## 6. Top-3 worst moves per game per seat (`top_losses`)

| game | seat | ply | k left | phase | n legal | played | best | ΔQ | pts (tanh est) | bucket |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| g1 | human | 100 | 21 | tiles | 39 | 1031 | 839 | 0.2798 | 14.18 | blunder |
| g1 | human | 124 | 9 | tiles | 32 | 958 | 1467 | 0.2209 | 3.33 | blunder |
| g1 | human | 5 | 69 | meeples | 5 | 2510 | 2501 | 0.1066 | 1.60 | inaccuracy |
| g1 | champion | 11 | 66 | meeples | 7 | 2507 | 2502 | 0.1083 | 1.79 | inaccuracy |
| g1 | champion | 139 | 2 | meeples | 3 | 2504 | 2510 | 0.0997 | 1.50 | inaccuracy |
| g1 | champion | 130 | 6 | tiles | 50 | 926 | 1633 | 0.0895 | 1.35 | inaccuracy |
| g2 | human | 48 | 47 | tiles | 19 | 1462 | 1051 | 0.2747 | 4.40 | blunder |
| g2 | human | 53 | 45 | meeples | 2 | 2510 | 2505 | 0.2734 | 4.18 | blunder |
| g2 | human | 44 | 49 | tiles | 28 | 1458 | 1051 | 0.2287 | 3.75 | blunder |
| g2 | champion | 39 | 52 | meeples | 5 | 2509 | 2510 | 0.1557 | 2.44 | inaccuracy |
| g2 | champion | 50 | 46 | tiles | 24 | 941 | 1156 | 0.1494 | 2.26 | inaccuracy |
| g2 | champion | 6 | 68 | tiles | 12 | 1148 | 1345 | 0.1427 | 2.16 | inaccuracy |

(Table rendered from `top_losses.<seat>` of each artifact — read the JSON, not this table, if
the two ever disagree.) Two shapes stand out and are **leads, not
findings** at n=2: g1 ply 100 is the single largest disagreement in either game
(ΔQ 0.2798, `delta_points_tanh_est` 14.18 — that estimate is deep in the atanh blow-up region
and is the clearest case in this document of why D1 forbids quoting it as points), and g2's
three worst human moves are all in the 44–53 ply window (k 49→45), i.e. one bad mid-game
stretch rather than a spread.

## 6b. GAME 3 (2026-08-05) — the first human WIN, graded under `app_aug2`. **He won the game he played worst.**

> **HISTORICAL NOTE — this section was graded WRONG once and retracted the same night, before
> anything downstream used it.** The first grading resolved the archive to **`fixed_v1`** from
> `start_rule: retail` + `grid_rule: centered18` alone. That was wrong: the phone was running the
> **2026-08-02 app build**, verified two ways — the installed APK's sha256
> `54a08d51314b3635f5933561dbf266cafcf8674ebe601b38f603575886e6c40b` is byte-identical to
> `android/app/build/outputs/apk/debug/app-debug.apk` (built 2026-08-02) and **differs** from the
> staged `app-debug-fixedv1-20260803.apk`
> (`b8f2cef6185ebce82a66da698ddc678043884475035b621b0af610199915a343`); and the archive carries
> **no `rules_profile` / `cloister_rule` / `farm_rule` fields**, which the fixed_v1 build stamps
> on every archive it writes. The Aug-2 build plays centered18 + retail but keeps **drifting
> cloister scan, `next_player` on an unplaceable tile, and R9 OFF**, so grading it as `fixed_v1`
> re-ran the search with **R9 ON + fixed cloister scan + redraw** — different farm adjacency than
> the game was played under, and farms were live (15–9).
> **Why the fail-closed guard could not fire:** `resolve_profile_name` keyed only on
> `(start_rule, grid_rule)`, and within the registry that pair *did* hit `fixed_v1` uniquely — the
> registry had **no row for the Aug-2 combination**, so a build that exists in the world was
> outside the key space, and "the four profiles partition that key space uniquely" was true of the
> registry and false of reality. `replay_scores_match: true` did not catch it: R9 flips the legal
> mask in only ~1/200 games and cloister/redraw are rare, so a matching replay is weak evidence
> here, not proof.
> **Fixed 2026-08-05 night:** registry row `app_aug2` added (app provenance, adopts nothing) and
> `resolve_profile_name` rewritten to a priority contract — an explicit `rules_profile` stamp
> wins; **absent ⇒ pre-fixed_v1 build ⇒ never `fixed_v1`**; anything else raises. Pinned by
> `tests/test_analyzer_evloss.py` against this very archive. **Everything below is the re-grade
> under `app_aug2`.** (The void numbers are not repeated; they are in git at `6919245`.)

Archive `1785975832_66810.json` (98–78 W), graded at **its own budget k8×1376 = 11008**
(`budget.total_sims_per_move`, `budget.source: "archive sims_effective/k_dets_effective"`) under
**`app_aug2`** — `integrity.rules_profile_name`, resolved by
`integrity.rules_profile_source: "no rules_profile stamp => pre-fixed_v1 build; resolved from
start_rule/grid_rule among pre-fixed_v1 profiles only"`. The profile actually applied is stamped
in `integrity.rules_profile`: grid `centered18`, start `retail`, cloister scan `drifting`,
unplaceable tile `next_player`, `r9_env_expected false` / `r9_env_observed false` /
`r9_env_ok true` — i.e. the Aug-2 phone rules, not the fixed_v1 bundle.
`EV_LOSS_g3_66810.json`.

**Gate PASS** (`acceptance_gate.pass`): champion-seat mean ΔQ **0.011904**
(`acceptance_gate.champion_mean_delta_q`, sem **0.004758**) vs calibration null p95 **0.070818**
(`acceptance_gate.null_p95`) — again below the null *mean* (**0.012853**,
`acceptance_gate.null_mean`, n 114). Supporting integrity: `replay_scores_match: true`
(`final_scores_replayed [98, 78]` == `recorded_scores [98, 78]` — and note the desktop reproduces
the phone's score **under `app_aug2`** too), `mirror_desync_events: 0`, `n_unrated_pimc: 0`,
`n_plies_graded: 114` of `n_plies_total: 142` (`n_forced_skipped: 26`, `n_latched_exact: 2`),
`leaf_hash_ok: true`, `pool_total_visits_always_full_budget: true`.

| seat | rated | agree | mean ΔQ | sd | p50 | max | **blunders** |
|---|---:|---:|---:|---:|---:|---:|---:|
| human (seat 0) | 52 | 0.4423 | **0.06098** | 0.11413 | 0.00791 | 0.5625 | **9** |
| champion (seat 1) | 62 | 0.6290 | **0.01190** | 0.03746 | 0.0 | 0.2569 | 1 |

(`summary.<seat>.n_rated / agree_rate / mean_delta_q / sd_delta_q / delta_q_dist.p50 /
delta_q_dist.max / buckets.blunder`. Bucket cut points, MEASURED: `within_noise` ≤
**0.070818** (null p95) < `inaccuracy` ≤ **0.125503** (null p99) < `blunder` —
`buckets.thresholds`, calibration seed 777. Neither seat has a single unrated ply.)

**Human − champion = +0.04908 ± 0.01653, z +2.97, ratio 5.12×** — still the largest paired gap
of the three games, and still the largest z, but it now sits **just under 3σ**, not past it.
⚠️ **Absolute ΔQ is NOT comparable across games** (this one is graded at 11008 on `app_aug2`;
g1/g2 at 2752 on `walled`). The comparable statistic is the *within-game ratio*: 3.03 / 2.99 /
**5.12**.

**Instrument validation, free:** the champion's agree rate is **0.629** here versus 0.727/0.730
in the two 2752 games (`summary.champion.agree_rate` across the three artifacts) — the direction
and rough size CL-070 predicts from self-disagreement growing with budget (D_same 0.2272 → 0.2997
between 2752 and 11008). An independent check that the grader behaves as the budget axis says it
should; the re-grade moved it further in the predicted direction, not less.

**The damage is entirely front-loaded.** All **9** blunder-class human moves fall in plies
**12–60** (k_remaining 64→40: plies 12, 20, 28, 37, 40, 44, 52, 56, 60); **zero** after ply 60.
Split by half, with the champion seat as the control (from `plies[]`, `bucket` and `delta_q`):

| seat | plies ≤60 | plies >60 | compression |
|---|---:|---:|---:|
| human | 0.1029 (n 28, 9 blunders) | **0.0121** (n 24, 0 blunders) | 8.5× |
| champion | 0.0200 (n 29, 1 blunder) | 0.0048 (n 33, 0) | 4.2× |

⚠️ **Both seats compress late, so "he tightened up" is only half the story** — a decided position
shrinks sibling differences for everyone, and the control proves that effect is real (4.2× on an
agent whose policy did not change). What survives the control: the human/champion ratio falls
**5.15× early → 2.52× late**, so he *did* narrow relative to the instrument's own drift, but not
to parity. By phase, the loss is in **tile placement (mean 0.0812, n 35), not meeple placement
(0.0193, n 17)** — the champion's own split is 0.0186 (n 34) tiles / 0.0037 (n 28) meeples, so
tiles are the noisier phase for both seats and the human's tile excess (4.4×) is larger than his
meeple excess (5.2× on a much smaller base).

Worst human moves (`top_losses.human`): ply 56 (k 42, tiles, 37 legal, played 950 vs best 1450,
ΔQ **0.5625**), ply 40 (k 50, tiles, played 1138 vs 1452, ΔQ 0.3497), ply 60 (k 40, tiles, played
1550 vs 1453, ΔQ 0.3040). The champion's single blunder is ply 50 (k 45, tiles, ΔQ 0.2569).
⚠️ `delta_points_tanh_est` for ply 56 is 14.59 — deep in the atanh blow-up region; D1 forbids
quoting that as points.

**Exact tail** (`exact_tail`): one latched ply per seat — human ply 140 (k_remaining 0, 21 legal)
and champion ply 138 (k_remaining 1, 28 legal), **both `played_is_optimal: true`, regret 0.0
points for both seats**. His endgame was exact-perfect.

**Reading, honestly.** The scoreline says a 20-point win; the grader says his roughest game of
the three. The win was built on the endgame ledger (unfinished features +16, farms +6) after an
opening the champion's search rates poorly. Two explanations fit and **n=1 cannot separate
them**: (a) the deck and the banking strategy bailed out a bad start, or (b) the champion's leaf
under-prices the incomplete-feature banking he was playing for, so moves toward it grade as
losses while earning points. (b) is a *lead, not a finding* — testing it means grading the same
game against a stronger reader, or checking whether his high-ΔQ moves are systematically the ones
that later paid as unfinished features. Neither is funded here.

⚠️ **What this section does NOT say:** nothing here is a strength claim, `governance/PRODUCTION.yaml`
is untouched, and `app_aug2` adopts nothing — it is a provenance row so that a pre-fixed_v1 phone
archive can be graded under the rules it was actually played under. The win itself and its
provenance were never in question and are unchanged: `sims_effective 1376` × `k_dets_effective 8`
= **11008**, `verify: true`, leaf `a36d2e15a3b3d71d`, no `runtime_budget_override` ⇒ Joshua beat
the champion of record at full strength, under Aug-2 rules rather than the full fixed_v1 bundle.

## 6c. GAMES 4–6 (2026-08-05 evening) — the first fixed_v1-epoch session: 2 L, 1 W (blowout). **The grade-vs-outcome correlation INVERTS.**

Three games on the freshly installed fixed_v1 build (archives self-label `rules_profile:
fixed_v1` / `farm_rule: r9` — the resolver's priority route 1 fired, `rules_profile_source`
"explicit stamp"). All graded at k8×1376 = 11008 with calibration; **all three gates PASS**
(champion mean ΔQ ≤ null p95 in each: 0.0425/0.1609, 0.0232/0.1726, 0.0156/0.0985),
`replay_scores_match: true` and 0 desyncs on all three. Artifacts `EV_LOSS_1785982194_*.json`,
`EV_LOSS_1785984310_*.json`, `EV_LOSS_1785986044_*.json`.

| game | result | human ΔQ | champ ΔQ | ratio | z | human blunders | champ |
|---|---|---:|---:|---:|---:|---:|---:|
| g4 | **L** 80–87 | 0.06958 | 0.04247 | **1.64×** | +1.19 | 1 | 1 |
| g5 | **L** 101–107 | 0.08962 | 0.02323 | **3.86×** | +3.21 | **12** | 2 |
| g6 | **W** 109–65 | 0.05823 | 0.01555 | **3.74×** | +2.13 | 1 | 1 |

**The night's finding: his graded quality and his results point in opposite directions.**
His *cleanest relative game* (g4, 1.64×, one blunder each, statistically indistinguishable
seats at z +1.19) he **lost**. His *worst-graded game* (g5, 12 blunder-class moves, z +3.21 —
the first past-3σ game in the set) he lost **by 6 points** — the contested-farm battle
(farms 33–30; one ~30-pt farm, 4–5 meeples committed, ownership "kept flipping"). And the
**109–65 destruction** (g6) he played at 3.74× the champion's per-move loss with the single
largest ΔQ in any game (0.924, ply 44). Across six graded games, the two he won are among the
three he played "worst" as priced by the champion's own search.

Mechanically the g5 signature is new: **blunders spread over the whole game** (plies 12→128,
11 of 12 in the tiles phase; early 0.0859 / late 0.0928 — no late clean-up), unlike g3's
front-loaded pattern. His meeple placement stays clean everywhere (g5 0.0361, g6 0.0377 vs
tiles 0.1355 / 0.0715) — across all six games the loss lives in **tile placement**, never in
meeple placement. Exact tail: **0.0 points, both seats, all three games** — five straight
games of exact-perfect endgames on both sides.

**Reading.** Two hypotheses survive, now with three more data points each:
1. **Deck variance dominates single games.** At the measured luck floor (~6% champ-vs-greedy;
   protocol wr 0.55) single-game outcomes are noisy, and grade-vs-outcome inversion across
   n=3 is unremarkable. The 6-pt g5 loss despite 12 blunders and the g4 loss despite clean
   play both fit "the deck decides the close ones".
2. **The champion's pricing is wrong about his strategy, specifically contested farms.** The
   external ledger evidence (README): he is **6-for-6 on farms across every archived game**;
   the champion averages **11.0 farm pts/seat against him vs 20.5 in its own corpus**, and
   took **0** in g6 (its own p5). If fighting for a big shared farm is systematically
   mis-priced by the leaf, his farm-war moves grade as blunders while winning the 30 points —
   which is exactly the g5/g6 shape (high ΔQ concentrated in tile placement, where farm
   connections are made). ⚠️ The grader CANNOT adjudicate this: it prices moves with the same
   leaf that is under suspicion. The discriminating instrument is the one already named in §7:
   score his high-ΔQ moves against an *independent* reference (exact solver where K allows, or
   oracle-style CRN deck-completion scoring — `oracle_score_pilot.py` exists) and check
   whether "blunders" in farm wars systematically out-earn the champion's preferred move.

n=6 total, all screens. Neither hypothesis is promoted; both are now concrete enough to test.

## 7. What this does and does not settle

- It **converts CL-070's "the move changed" into "the move cost N ΔQ"** — the named successor
  the claim asked for.
- It gives a **calibrated, paired instrument**: the champion seat is graded on the same board
  every time, and the acceptance gate is a live wiring check, not a promise.
- It **does not** make a strength claim, does not price the human in points, and does not
  generalise past two games at k4×688 on the walled epoch.
- Next natural steps, unfunded here: a post-2026-08-01 `fixed_v1` archive (needs its own
  calibration), and grading the same games at k8×1376 to read "a stronger reader's opinion"
  against this one (`budget.source` would flip to `"CLI override"`).
