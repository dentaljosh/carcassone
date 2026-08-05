# Phase-5 analyzer — slice 1: corpus descriptive-stats catalog + E4 diff

**Status:** BUILT & RUN 2026-08-02. First real slice of the Phase-5 analyzer, authorised
by Joshua 2026-07-30 ("yes to phase 5"); spec = his seed list in
[BACKLOG.md](../../BACKLOG.md) "2026-07-30 — Phase 5/6 descriptive-stats catalog" (862536f).

**What this is:** pure-replay descriptive statistics over champion game corpora, and a
tool that drops any E4 human-vs-champion phone archive into those distributions. No
search, no network, no leaf eval — every number is a deterministic function of
`(deck_seed, actions)` via the `root_replay` contract, so the whole catalog rebuilds in
under a minute.

**What this is NOT:** move grading. Nothing here says a move was good or bad. That is
the *next* slice (per-move EV loss vs a deep search — ORIGINAL_PROMPT Phase 5 task 2).
This slice answers "what does champion play look like, and where does a human game sit
in that", which is the prerequisite: you cannot say a farmer went down too early without
knowing when the champion puts them down.

## Artifacts

| file | what |
|---|---|
| `CORPUS_STATS_champ449.json` / `.md` | 449 champion-vs-champion self-play games, k4×688 = 2752 sims/move, leaf `v2_9_2_Bmild_cap8_curve125` |
| `CORPUS_STATS_champ125_1500.json` / `.md` | 1500-game replication corpus (see caveat below) |
| `E4_DIFF_1785205383_867966_vs_champ449.json` / `.md` | Joshua's 2026-07-27 game (111–113 L) |
| `E4_DIFF_1785466497_161583_vs_champ449.json` / `.md` | Joshua's 2026-07-30 game (73–108 L) |
| `scripts/analyzer/replay_stats.py` | the stat definitions (module docstring = the definitions of record) |
| `scripts/analyzer/corpus_stats.py` | corpus replay + aggregation + markdown |
| `scripts/analyzer/e4_diff.py` | one archive → percentile/paired/plain-language diff |
| `tests/test_analyzer.py` | 18 tests: replay-count sanity, hand-checked fixture, stranding pinned |

Every number below cites the JSON field it comes from. Nothing is retyped from memory.

## Integrity — the machinery is validated three ways

1. **449/449** champion games replay on the desktop to the score recorded in the corpus
   (`integrity.replay_scores_match`). 1500/1500 score splits reconcile in the second corpus.
2. **Both E4 phone archives replay to the phone's recorded final scores**, and the
   desktop-recomputed during-play/unfinished/farm split matches the breakdown the phone
   itself wrote, field for field (pinned in `tests/test_analyzer.py::test_e4_diff_end_to_end`).
   ARM/Pixel → x86/WSL is lossless for the whole score decomposition, not just the total.
3. The score split reconciles to the true final score in **1949/1949 games** across both
   corpora (`integrity.split_ok`).

---

# Headline findings

### 1. Joshua's farm-timing coaching is two-thirds right — and the wrong third is exactly what he does

The coaching he was given: *early farms around ply 4–12, plus endgame grabs, never
mid-game farm wars.* Against `farm_timing` in the 449-game corpus:

- **Early — confirmed.** Median **first** farmer goes down on **turn 4** (p25 = 2,
  p75 = 8.75, mean 6.8). Dead centre of the coached window.
- **Endgame — confirmed.** 20.2% of all farmer placements land in the late band (k < 24).
- **"Never mid-game" — REFUTED.** **24.6%** of the champion's farmer placements are
  mid-game (24 ≤ k_remaining < 48) — 0.84 farmers per seat per game. The champion fights
  mid-game farm wars about a quarter of the time. (`farm_timing.placement_k_band_frac`:
  early 0.552 / mid 0.246 / late 0.202.)
- The champion plays **3.43 farmers per seat**, and in 449 games **no seat ever played zero**.

**The coaching angle:** in *both* of his archived games Joshua placed **2 mid-game
farmers** — 89th percentile, +1.4 sd, against a champion mean of 0.84. The one part of
the advice that the corpus does not support is the one part he is doing most.

### 2. His farm timing was late in game 1 and over-invested in game 2

- **Game 1 (111–113):** first farmer on **turn 14** (87th percentile; corpus median 4).
  Farm placements at turns 14, 20, 32, 34 — nothing in the coached early window at all,
  while the champion seat opened its first farm on turn 5.
- **Game 2 (73–108):** first farmer on turn 4 (on schedule, 47th percentile) but **six
  farmers total — 99th percentile, +2.3 sd** against a corpus mean of 3.43. Placements at
  turns 4, 6, 10, 30, 38, 50.

He won the fields in both games (27–15 and 27–3 farm points). The problem was never that
the farms failed; it was what the farm meeples cost elsewhere.

### 3. The surprise: Joshua strands *fewer* meeples than the champion, not more

The intuition behind the stranding stat was that humans over-commit meeples. For Joshua
it is backwards:

| | non-farmer stranding rate | meeple-turns locked |
|---|---:|---:|
| champion corpus (898 seats) | **0.431** | 121 |
| Joshua, game 1 | 0.375 (35th pct) | 58 (15th pct) |
| Joshua, game 2 | **0.143** (2nd pct, −1.9 sd) | 20 (3rd pct, −1.7 sd) |

The champion *deliberately* strands 43% of its non-farmer deployments — that is the leaf's
meeple curve pricing endgame incomplete-feature points, not a mistake. Stranding rises
steeply with how late the meeple went down (`stranding.by_placement_k_band`): **early
0.288 → mid 0.461 → late 0.825**. A late meeple is placed *knowing* it will not come back.

Joshua is playing the opposite policy — recycling meeples, keeping them clean. Game 2 makes
the cost visible: his `incomplete_pts` was **2** (1st percentile; corpus mean 23.0) against
the champion seat's 16. He left almost nothing on the board to be paid for at the end.

### 4. Game 2 was lost during play, not in the fields — and the ledger says why

Score flow, replayed (`replayed_score_flow`):

| | during play | unfinished | farms | total |
|---|---:|---:|---:|---:|
| Joshua | **44** (24th pct) | 2 (1st pct) | 27 | 73 |
| champion | **89** (98th pct) | 16 | 3 | 108 |
| corpus mean | 54.8 | 23.0 | 20.5 | 98.3 |

A 45-point during-play deficit is not recoverable with a 24-point farm win. The single
sharpest number in either report: Joshua's **points per meeple placed = 5.62, 1st
percentile, −2.2 sd** (corpus mean 8.97). He deployed *more* meeples than the champion
average (13 vs 11.1) and got less from each one. Six of them were farmers.

### 5. Most feature closures pay nobody

Across 449 games (`completed_features.*.frac_unscored`): **62.8% of completed cities**,
**68.1% of completed roads** and **52.7% of completed cloisters** close with no meeple on
them. Closure is mostly structural. The champion's edge is selectivity, not activity — the
cities it *wins* average 4.52 tiles against 2.90 for all closed cities, and the roads it
wins average 5.78 against 3.44.

### 6. Completed cities are small — the 2-tile city dominates

Completed-city size histogram, 449 games: **2:2958**, 3:557, 4:302, 5:189, 6:137, 7:86,
8:72, 9:42, 10:21, 11:14, 12:9, 13:7, 14:3, 16:1, 19:1. Median 2, mean 2.90, p95 = 7,
max 19. Roads: median 3, mean 3.44, max 19. Two-thirds of all city closures are the
minimum-size city.

Against this, game 1 has Joshua at **mean city size won 7.5 — 92nd percentile, +1.6 sd**,
against the champion seat's 3.0 in the same game. He built two big cities; the champion
took eight small features (`n_features_won` 8, 97th pct) while he took four. That game was
a 2-point loss, so this is not framed as an error — it is a visibly different style, and
the diff tool surfaced it as the top divergence without being told to look.

### 7. The champion runs its meeple supply to zero

`curves.mean_meeples_in_hand` falls 7.00 → 3.51 (turn 12) → 1.71 (turn 30) → 0.71 (turn 66).
Median `min_meeples_in_hand` across 898 seats is **0** — half of all champion seats bottom
out with no meeples in hand at some point. Deploy rate collapses by phase: **0.524 early →
0.223 mid → 0.178 late**, i.e. the champion passes on a meeple on 82% of its late turns.

### 8. These statistics replicate across a different generator

The 1500-game corpus agrees with the 449-game champion corpus on nearly everything
structural: non-farmer stranding **0.427 vs 0.431**, first-farm median **4 vs 4**, mean
completed city size **2.96 vs 2.90**, unscored-city fraction **0.626 vs 0.628**, score flow
**55.7/24.0/18.8 vs 54.8/23.0/20.5**. These are properties of the game plus a
strong-heuristic policy class, not of one budget. The one real difference is farm
appetite: **2.90 farmers/seat vs 3.43** — the champion plays more farmers than the older
generator.

### 9. Stranding's during-play cost, honestly bounded

At the corpus's own realised rate of **0.4714 points per meeple-turn** (33,893 pts over
71,898 meeple-turns of *returned* meeples), the 108,961 stranded meeple-turns represent a
**gross 57.2 pts/seat/game** opportunity — but stranded meeples are not idle, they collect
**23.0 pts/seat** at game end, giving a **net 34.2 pts/seat/game** upper read. This assumes
a productive alternative placement always existed, which is why it is reported as a bound
and both halves are emitted separately (`stranding.stranding_cost_gross_pts_per_seat`,
`.incomplete_pts_earned_per_seat`, `.stranding_cost_net_pts_per_seat`). Do not quote the
gross figure alone.

---

# Definitions that needed a judgment call

Full text lives in the `definitions` block of every catalog JSON and in the
`scripts/analyzer/replay_stats.py` module docstring. The four that are contestable:

1. **Stranding is reported twice, and the headline excludes farmers.** A farmer is
   unrecoverable by design in Base+Farmers — that is the cost of the claim, not an error.
   `stranded_all` (0.606 corpus-wide) is a board-occupancy figure and is never quoted as an
   error rate; `stranded_nonfarmer` (0.431) is the metric. Pinned by
   `test_farmers_are_always_stranded`.
2. **"Returned" == "scored during play".** The engine removes a meeple from
   `placed_meeples` in exactly one place — `remove_meeples_and_collect_points` — so the two
   can never disagree. Pinned by `test_stranding_definition_pinned`.
3. **The terminal score split needs a stubbed replay.** `count_final_scores` runs *inside*
   the terminating move and consumes the placed meeples, so a plain replay cannot see who
   owned what. The walk stubs `PointsCollector.count_final_scores` for its duration, leaving
   the meeple-intact terminal state, then attributes via
   `aux_targets.extract_terminal_ownership` and reconciles against an unstubbed replay
   (`split_ok`). Same reconstruction the Android bridge's `_final_breakdown` uses;
   `engine/` is untouched.
4. **Completion identity is the coordinate set, not the union-find root id.** Root ids are
   not stable across `decompose` calls. A finished city or road can never grow, so
   first-sighting of a finished coordinate set == its closure turn.

Also worth knowing: **the two phase segmentations are identical on these corpora**
(`move_mix.segmentation_agreement` = 1.0000). Every game runs the full 72 tiles, so turn
terciles and absolute k_remaining bands label every single turn the same way. Both are
emitted as specified; the distinction only earns its keep on a corpus where games end early.

# Caveats

- **Corpus path.** The task named `measurement/distill_flywheel_20260715/gen_games_champ125.jsonl`.
  That file does not exist. The same-named 1500-game corpus that does exist is
  `measurement/utility_calibration_20260721/gen_games_champ125.jsonl` and is what was used.
- **Its provenance stamp says `gen: heur_v2_7`**, not a champion generation, and it carries
  no per-move budget fields and no recorded scores (so replay-score verification is
  `unchecked` for it — the score *splits* still reconcile 1500/1500). Treat it as a
  strong-heuristic replication corpus, not a second champion corpus. The 449-game corpus is
  the champion reference.
- **Opponent conditioning.** The corpus is champion-vs-champion. Neither E4 seat is drawn
  from that population — the human faces a champion and the champion faces a human. The
  percentiles are descriptive, not a test. The **within-game human-vs-champion column** is
  the robust half of the E4 report: same board, same deck, same tiles.
- **Grading epoch.** Both archives predate the 2026-08-01 build: k4×688 mobile carve-out,
  walled grid, random start tile (`start_rule` / `grid_rule` are `null`). The corpus is
  k4×688 too, so the budget matches — but any archive from the new build must be re-diffed
  against a k8×1376 corpus.
- **n = 2 human games.** Everything in the E4 section is a description of two games, not an
  estimate of Joshua's play. The mid-game-farmer pattern showing up in both is suggestive
  and nothing more.

# Next slice (F12) — open ideas, updated 2026-08-05

Slice 1 remains the only analyzer work landed. Updated context since 2026-08-02: the rust
port shipped (full k8×1376 champion at ~1.55 s/move on the Pixel), the strength program's
compute queue is empty (F13 closed 2026-08-05, CL-076), and the boxes are idle — so F12 is
the natural next build if Joshua funds it. Candidates, cheapest-informative-first:

1. **Per-move EV loss grader, offline** (ORIGINAL_PROMPT Phase 5 task 2 — the actual move
   grader). Replay an E4 archive, run the champion's search at each human ply,
   Δ = Q(best) − Q(played) in expected-margin points. This catalog is its baseline
   ("farmer on turn 30" now has a reference distribution), and CL-070 is its mandatory
   noise floor: the champion self-disagrees ~26–30% at fixed budget, so "not the top move"
   is never a blunder signal — bucket by Δ magnitude (agree / within-noise / inaccuracy /
   blunder). Cost: ~70 searched plies per game on desktop = minutes per archive. This is
   the slice the report's own findings ask for (game 2's during-play deficit says *where*
   points were lost; a grader says *which moves*).
2. **Coach mode, on-device** (BACKLOG 2026-07-30 sketch) — the same grader made real-time
   in the app. Materially cheaper than when sketched: the rust core grades at champion
   budget in ~1.5 s. Needs `grade_last_move()` in the bridge, a UI badge, and the
   `coached: true` archive flag from day one. **The gating question the roadmap carries:**
   coached games measure the learning curve, not the rating — so shipping coach mode
   before a body of *uncoached* E4 games exists contaminates the E4 rating stream.
   Recommendation: land slice-2a (offline grader) first, collect uncoached E4 games,
   gate the coach-mode flip on Joshua's explicit call alongside the APK rebuild.
3. **A k8×1376 reference corpus.** The grading-epoch caveat above is now live: any archive
   from the post-2026-08-01 build (fixed_v1, k8×1376) cannot be diffed against this
   k4×688 corpus. A fixed_v1 champion self-play corpus at deploy budget is a box-day-scale
   run (price before funding) and also refreshes the percentile baselines for slice 1.
4. **Phase-6 Track A folk claims** — one query away descriptively ("first farmer in a
   field usually wins it" needs farm-ownership-over-time, which the meeple ledger already
   carries). Descriptive only; causal versions need the paired-constraint machinery.
5. **More E4 games.** Still the binding constraint (n = 2), exactly as BACKLOG predicted —
   and upstream of it sits the open APK-rebuild + E4-rules call.

Phase 5 stays downstream of the strength milestones (2026-05-28 goal change) — all of the
above is opt-in analysis/coaching value, not a strength lever.
