# Joshua-bot — the scripted owner-strategy opponent (J1–J8)

> ## 🔚 STATUS: BUILT 2026-08-12 · **RUN AND ADJUDICATED 2026-08-13** · closed out six-touch
>
> The variant tournament executed and is **spent**: 6-cell screen n=300 (band 1.25e11) →
> J7ZERO confirm n=800 (sealed band 1.26e11). Verdict of record:
> [CONFIRM_VERDICT.md](CONFIRM_VERDICT.md). **The bot is not an anti-champion instrument** —
> confirm margin **−16.036 pts/deck, z −24.42**, wr 0.204. ⚠️ **Confounded by search depth:**
> J1–J9 sit on a **one-ply greedy** base, and JCZ's `LegacyAiPlayer` — a *stronger* shallow
> player — loses to the same champion by only **−6.50**, so Joshua-bot is weaker than JCZ's AI
> and this prices the **encoding on a greedy base**, not the strategy.
>
> **Three of §7's open questions are now answered empirically** (the run's real product):
> **Q1 `j7_weight` → 0.0** (+5.34 pts/deck, z +3.71) · **Q6 preset → `current`** (+5.81,
> z +3.68) · **Q2 J9 → no conviction, stays OFF** (−2.14, z −1.47). ⛔ **Q3 J8 reserve-floor
> exemption → EXACTLY INERT: it changes zero chosen moves**
> ([J8EX_INERT_FINDING.md](J8EX_INERT_FINDING.md)) — J8 is **untested, not refuted**, and
> **this file's "8–28×/game" build figure counted the PREDICATE firing, not chosen moves
> changing; it must never be cited as a behavioural-change rate.**
>
> Follow-up this earned (built, 0 games): the J-rules as a leaf term on the champion's **own**
> search — `docs/LEVER_INDEX.md` row *"J-rules on search"*.

**STATUS AT BUILD TIME: BUILT 2026-08-12, NOT YET RUN. Variant-tournament axes added 2026-08-12
(owner: "test these and see what wins empirically") — J9 encoded (default OFF), and
J7's weight / the J3-vs-J8 conflict / J9 are CLI flags rather than decisions (§7).**
Instrument only — **no strength claim, no claim id, `governance/PRODUCTION.yaml`
untouched.** Nothing here is a champion candidate and nothing here gets promoted. The
deliverable is a margin distribution against the champion of record.

**Primary source (the ground truth this file is audited against):**
[`measurement/e4_games/ANCHOR_INTERVIEW_2026-08-12.md`](../e4_games/ANCHOR_INTERVIEW_2026-08-12.md)
— verbatim self-report, extraction table J1–J12.
**External corroboration:** [`docs/research/PRO_STRATEGY_SCAN_2026-08-12.md`](../../docs/research/PRO_STRATEGY_SCAN_2026-08-12.md)
findings **F1** (large open cities are structurally inefficient — the object J1 exploits),
**F2** (late majority-steal joins are a named core 2p tactic — J1/J2), **F3** (time a
contest to the opponent's meeple reserve — J4).

| artefact | path |
|---|---|
| the bot | [`src/carcassonne_ai/joshua_bot.py`](../../src/carcassonne_ai/joshua_bot.py) |
| the H2H driver | [`scripts/joshuabot/h2h.py`](../../scripts/joshuabot/h2h.py) |
| the tests | [`tests/test_joshua_bot.py`](../../tests/test_joshua_bot.py) |

---

## 0. What this is for, in one paragraph

Joshua is beating the champion head-to-head on the phone (E4 record 9–10 at the time of
writing, mean margin +9.13 ± 7.63 over the `fixed_v1` epoch) and the project's own EV-loss
grader scores several of his winning moves as blunders. That is the one non-saturated
signal in the program, and it arrives one game an evening from a **nonstationary** anchor.
This bot freezes a version of that strategy so it can be played at n=400–800 deck-paired
volume. **Partial reproduction of the lean localises the mechanism; zero reproduction says
the lean is not in these eight rules** — both outcomes are informative, which is why it is
worth building before it is worth tuning.

---

## 1. Integration surface

**Chosen: the `play_harness` agent interface.**
`JoshuaBot.choose_action(board) -> int`, plus the telemetry attributes
`scripts/human_anchor/play_harness.py::_snapshot` reads (`latch_k`, `heur_moves`,
`exact_moves`, `n_timeouts`, `solver_secs`, `solver_nodes`, `neural_moves`, all inert).
It therefore drops into `play_harness.play_game` / `play_paired` **with no harness
change** — the same loop that produced every E4 human game and every
`scripts/e4_deck_baseline.py` self-play game. It deliberately has **no**
`start_game`/`advance`, so `mirror_protocol.seat`/`advance` skip it (duck-typed), and the
Rust-backed champion on the other seat is mirrored exactly as it is in every other caller.

Rejected alternatives:
* `RuleBasedPlayer`'s `choose_action(game, board, valid_mask)` signature — a different,
  older interface with no harness that plays it deck-paired against the champion.
* the `scripts/jcz_match/` path — that harness exists to drive an *external engine over a
  protocol*; there is no external process here.

The driver `scripts/joshuabot/h2h.py` is a thin adapter modelled line-for-line on
`scripts/e4_deck_baseline.py` (same env/R9 latch, same worker bootstrap, same per-game
fsync checkpointing, same `--resume` contract). It plays every deck seed **twice with
seats swapped** and reports the **deck-paired** margin.

---

## 2. Rule coverage — J-rule → code symbol → parameters → the sentence it implements

Sign convention everywhere: **positive = Joshua-bot ahead**. Every J-term is in **points**,
from the bot's own seat, added to `flat_leaf.flat_base_score` (the "virtual score count"
the owner says a human can compute mechanically — interview §3).

| J | code symbol (`carcassonne_ai.joshua_bot`) | parameters | interview quote |
|---|---|---|---|
| **J1** | `j1_majority_steal()` | `j1_min_city_tiles=5`, `j1_min_open_edges=2`, `j1_join_bonus=3.0`, `j1_late_extra=1.0` | "i notice he tends to build large cities that probably wont close. if they are getting on the bigger side, i will attempt to sneak a meeple in, sometimes late in hte game" |
| **J2** | `j2_farm_attack()` (realized steal + approach), `j2_reach()` (the deck-counted plan), `farm_potential_value()` / `farm_total_value()` (the valuation), `remaining_tiles()` / `bag_farm_fraction()` (the multiset) | `j2_steal_w=1.0`, `j2_approach_w=0.15`, `j2_plan_horizon=3`, `j2_reach_threshold=0.50`, `j2_entry_cells_cap=3`, `j2_min_farm_value=3.0`, `j2_low_farm_penalty=2.0`, `j2_unfinished_city_weight=1.0`, `j2_city_count_from_k=36`, `j2_city_close_open_max=2` | "if i see a farm is valuable, i will try to tie it or steal from him. sometimes this requires planning 2-4 tiles in advance, so i look at remaining tiles and try to see if its realistic to get there." |
| **J3** | `JoshuaBot._apply_filters()` → filter **F-J3** | `j3_reserve_floor=1`, `j3_endgame_release_k=8` | "i try to keep at least 1 meeple in my hand so i can quickly collect on easy to close vacant cities." |
| **J4** | `j4_urgency()` — a multiplier on J1, J2, J5, J6b, J8 | `j4_min_urgency=0.35`, `j4_full_reserve=4` | "if i see he is out of meeple, i am more okay with leaving a something juicy unclaimed" |
| **J5** | `j5_dump()`, `unclaimed_value()` | `j5_weight=0.5`, `j5_value_floor=4.0`, `j5_throwaway_gain=1.0` | "if he has meeple and i have a throwaway tile, i will place it somewhere where it doesn't add to anything unclaimed that is already worth more than a few points" |
| **J6** | `j6_anchor_and_roads()` — (a) anchor, (b) road join, (c) road skepticism | `j6_anchor_bonus=2.0`, `j6_anchor_city_min=3`, `j6_anchor_road_min=2`, `j6_road_join_min_len=4`, `j6_road_join_bonus=2.0`, `j6_road_skeptic_max_len=3`, `j6_road_claim_penalty=1.5`, `j6_road_anchor_allowance=1` | "keep a big city and road as mine, even if there is no plan to close it... somewhere to dump otherwise worthless tiles... sometimes i see his road is getting long and thats my signal to tie it up. but i'm generally less bullish on roads than him." |
| **J7** | `j7_close_vs_farm()` | `j7_weight=1.0`, `j7_points_per_field=3.0` | "its hard for me to pass up on closing unclaimed cities. i hesistate if I've already surrendered the farm to him because he gets an easy 3 points there." |
| **J8** | `j8_overcommit()` = `j8_city_term()` + `j8_farm_term()` (the per-component predicate, shared with the F-J3 exemption); filter exemption **F-J3/j8** | `j8_pivotal_swing=12.0`, `j8_overcommit_bonus=3.0`, `j8_value_norm=10.0`, `j8_max_city_meeples=2`, `j8_max_farm_meeples=3`, **`j8_break_reserve_floor=False`** (axis) | "sometimes it takes 2 meeple to secure a city. sometimes 3 for a single farm. you can sometimes see that the game will turn on a single large feature, and in those cases, you have to take chances." |
| **J9** | filter **F-J9** in `JoshuaBot._apply_filters()`, prospects read by `surrounding_count()` | **`j9_avoid_cloisters=False`** (axis), `j9_cloister_block_frac=0.55`, `j9_min_surrounding=6` | "he is good at blocking my cloister completions. i'm more cautious about grabbing them now." |
| **J10** | `PRESETS["early"]` vs `PRESETS["current"]`; filter **F-J10** | `early_farm_block_frac` (`current` 0.55 / `early` 0.0) plus the J2 overrides listed in §4 | "i think i did go less aggressive on farms, especially early on in the game, since my first few games against him... so i started to count the cities, especially late in game, and surrender a farm" |

**J9 semantics (added 2026-08-12, default OFF).** While more than `j9_cloister_block_frac`
of the bag remains, a CLOISTER claim is dropped **unless its completion prospects are
strong** — `surrounding_count(board, r, c) >= j9_min_surrounding`, i.e. the cloister's 3×3
already holds ≥6 of its 9 tiles (that count is exactly what the cloister would score if the
game ended now, and exactly `flat_leaf._cloister_points`). Conservative by design: it is
"more cautious", not "never", and it is a **filter, not a penalty**, so it cannot be traded
away against a big base score. Like every filter it is skipped if it would empty the
candidate set. Off by default because it is the one J-rule the brief scoped as a champion
behaviour; it is now an axis rather than a decision.

Rules **NOT** encoded, deliberately: **J11, J12** are champion behaviours the owner
described (late new farms, denial-by-extension), not instructions for his own play.

### Supporting symbols (not J-rules, but part of the contract)

| symbol | what it is |
|---|---|
| `remaining_tiles(state)` | the remaining tile **MULTISET**, order destroyed by construction; the ONLY function permitted to touch `state.deck` |
| `bag_farm_fraction(state)` | share of the remaining multiset that can carry a field (J2's "does the bag still hold it") |
| `k_remaining(state)` | the game clock; identical to `flat_leaf._k_remaining` / `fair_agent.k_remaining` |
| `Clock` | clock + bag + reserves + margin, read **once from the decision root** — never from a candidate afterstate (see §3) |
| `Position` / `analyze(state)` | board decomposition (`flat_leaf.decompose`) + per-component meeple ownership, attributed exactly as `flat_leaf._final_scores` does |
| `surrounding_count(board, r, c)` | placed tiles in a 3×3 including the centre — a cloister's score-if-scored-now; J9's "completion prospects" and J5's cloister valuation both read it |
| `JoshuaBot.rule_fires` | audit counter: how often each J-term / hard filter actually moved a real decision (lookahead calls are not counted) |
| `JoshuaBot.variant_id` | short, stable tournament-cell label derived from the RESOLVED params, e.g. `current+j7w0+j8brk+j9avoid0.55s6` |
| `JoshuaBot.manifest` | recorded verbatim into every `play_harness` game log and every H2H record: `variant_id`, the three `axes`, the explicit `overrides`, and the FULL resolved `params` |
| `JoshuaBot.TOURNAMENT_AXES` | the three axis names, so the driver and the tests read one list rather than three copies |

---

## 3. Information contract (hard, and tested)

**MAY read:** the board, both score totals, both meeple **reserves**, and the **remaining
tile MULTISET**. The multiset is legal public information — it is the bag minus what has
been seen — and the owner states plainly that he counts it ("tile bag peak because a pro is
counting", interview §3). It is what J2's "i look at remaining tiles" means.

**MAY NOT read:** draw **ORDER**, ever. Three structural guards, not just a promise:

1. `remaining_tiles()` consumes `state.deck` into a dict keyed by tile description and
   re-emits it **sorted** — the order is gone before any rule sees it.
2. It deliberately **excludes `state.next_tile`** (unlike `flat_leaf._bag_stats`, which
   counts it in the TILES phase), because inside the tile-phase lookahead `next_tile` is
   whatever the engine happened to draw, and that identity is order information.
3. Every clock/bag quantity lives on `Clock`, built **once from the decision root** and
   reused for every candidate — so a lookahead can never pick up the drawn tile.

Test: `tests/test_joshua_bot.py::TestFairInformation::test_deck_permutation_invariance`
shuffles the undrawn deck mid-game and asserts the chosen action does not move.

**Determinism.** No RNG anywhere. `seed` is accepted on the constructor purely so the call
site matches the other agents; it is discarded. Ties break on the **lowest action index**
after rounding to `score_round=6` decimals. Two `JoshuaBot` instances on the same board
return the same int (`test_deterministic_same_position_same_move`).

---

## 4. The two presets (J10 — the anchor moved)

One class, `preset=` switched. `PRESETS["current"]` is the default and the dataclass
defaults; `PRESETS["early"]` overrides exactly these:

| knob | `early` (his first few games) | `current` (today) | why |
|---|---|---|---|
| `early_farm_block_frac` | **0.0** (never blocks) | **0.55** | "sometimes i lay down a farm early" → "i did go less aggressive on farms, especially early on in the game" |
| `j2_steal_w` | 1.5 | 1.0 | farm-aggressive vs farm-disciplined |
| `j2_approach_w` | 0.30 | 0.15 | ditto |
| `j2_reach_threshold` | 0.30 | 0.50 | early Joshua chased longer-odds farm plans |
| `j2_min_farm_value` | **0.0** (never surrenders) | **3.0** | "some games, at the end, the farms really aren't worth much... and surrender a farm" |
| `j2_low_farm_penalty` | 0.0 | 2.0 | the cost of the surrender bar |
| `j2_unfinished_city_weight` | 0.5 | 1.0 | how hard he counts city potential into a field |
| `j2_city_count_from_k` | **999** (always) | **36** (second half) | "i started to count the cities, **especially late in game**" |

`with_overrides(preset, **knobs)` returns a modified `JoshuaParams` for sweeps and for the
tests that isolate one rule.

---

## 5. Precedence — the explicit conflict order

Rules conflict (J3 says hold a meeple; J1 says spend it on his city). The order is fixed
and is part of the spec, not an implementation detail:

```
0. FORCED MOVE            one legal action -> take it, no evaluation.

1. SCORE every candidate  value(afterstate) = flat_base_score(afterstate, me)
                                            + j1 + j2 + j5 + j6 + j7 + j8
   TILES phase scores a whole TURN: the placement PLUS the best meeple follow-up
   it enables (a J1 join and a J2 farm entry are each a tile move AND a meeple
   move; scoring the tile alone cannot see either).

2. HARD FILTERS, in this order, each SKIPPED if it would empty the candidate set:
     F-END   endgame deployment — k_remaining <= my reserve: drop PASS.
             An unplaced meeple is wasted points.  **OVERRIDES J3.**
     F-J10   early-farmer block — drop FARMER claims while more than
             early_farm_block_frac of the bag remains.  (`early`: off.)
     F-J9    cloister caution (OPT-IN, j9_avoid_cloisters) — drop CLOISTER
             claims while more than j9_cloister_block_frac of the bag remains,
             UNLESS the 3x3 already holds j9_min_surrounding tiles.
     F-J3    own-reserve floor — with reserve <= j3_reserve_floor, drop meeple
             placements UNLESS the meeple comes straight back (the feature
             finishes this turn), or the placement is a majority swing
             (ties/takes a feature the opponent already holds), or
             — ONLY when j8_break_reserve_floor is ON — it is a pivotal-feature
             overcommit (decided by J8's OWN per-component predicate, so the
             rule and its exemption can never drift apart).
             Lifted entirely once k_remaining <= j3_endgame_release_k.

3. ARGMAX, ties -> LOWEST ACTION INDEX. No RNG.
```

**F-J9 sits after F-J10 and before F-J3** because both F-J10 and F-J9 are *claim-class*
adaptations he described adopting ("less aggressive on farms", "more cautious about
grabbing cloisters"), while F-J3 is the meeple-economy floor that applies to whatever
claims survive.

**Why filters beat scores.** J3, F-END and F-J10 are *economy* statements ("never do X"),
not *preference* statements ("X is worth n points"); encoding them as large weights would
make them tradeable against a big enough base score, which is exactly what the owner says
he does not do. J4 is neither — it is a **multiplier**, so it appears nowhere in the
precedence list and instead scales the contest terms (J1, J2, J5, J6b, J8).

---

## 6. Interpretation notes (where the interview underdetermined the code)

These are decisions taken to make the rule executable. They are the places to look first if
the owner says "that isn't how I play".

* **J1 "tie reachable"** was read as *this action achieves the tie or majority*, evaluated
  on the afterstate — not as a multi-ply reachability search. The turn-level lookahead
  means the tile move that opens the join is credited with it.
* **J1 double-counting is intentional.** `flat_base_score` already pays for a tie (all tied
  players score in full), so `j1_join_bonus` is a **premium**, not the value of the join: it
  is what makes the bot prefer the join over an equally-scored alternative.
* **J2's "realistic to get there"** has no bar in the interview. `j2_reach()` uses a small,
  deliberately permissive model — my remaining turns, the count of empty cells adjacent to
  the field, and the share of the bag that can carry a field — combined as
  `1 - (1 - per_turn)^horizon` over `j2_plan_horizon` of my own turns, and compared against
  `j2_reach_threshold`. Rotation is free, so "an adjacent empty cell is a way in" is a
  proxy, the same spirit as `flat_leaf._bag_stats`' city-edge proxy. See §7 item 4.
* **J2 counts only UNFINISHED adjacent cities** in the potential. `flat_base_score` already
  pays 3 per *finished* adjacent city, so counting those again would double-count. The
  finished ones do enter `farm_total_value`, which is what the surrender bar is read
  against — a distinction the code keeps explicit.
* **J5's "throwaway tile"** was operationalised as *a placement that gains me at most
  `j5_throwaway_gain` points of naive count*. J5 is off for placements that actually score.
* **J6's "one big city and one road"** is a **presence** bonus, not a per-tile bonus: a
  second city anchor pays nothing extra, which is what makes it read as "keep **a** big
  city and **a** road".
* **J7 is deliberately a second charge.** `flat_base_score` already prices the 3 points his
  field takes when a bordering city closes. `j7_weight=1.0` therefore counts it **twice** —
  that *is* the "i hesitate": a human over-weighting a cost his own arithmetic already
  contains. `j7_weight=0.0` recovers the naive count. **Now the `--j7-weight` axis** (§7).
* **J8's "the game will turn on a single large feature"** was operationalised as: the
  feature's swing (2× its value) both clears `j8_pivotal_swing` **and** is at least the
  current margin — i.e. winning or losing it can actually flip the result.
* **J9's "more cautious"** was operationalised as a *filter with an escape*, not a penalty:
  cloister claims are refused in the first `j9_cloister_block_frac` of the bag **unless**
  the 3×3 is already `j9_min_surrounding`-full. The block fraction is borrowed from J10's
  farm block because the interview gives no timing for the cloister adaptation — that reuse
  is an assumption, not a reading. **Now the `--j9-avoid-cloisters` axis** (§7).

---

## 7. OPEN QUESTIONS → TOURNAMENT AXES

**Owner ruling, 2026-08-12: "test these and see what wins empirically."** So the three
contested interpretations are now **flags**, not decisions, and Q1 is **encoded** (J9,
default OFF). What remains below is either (a) an axis with a CLI flag, or (b) a knob
nobody has funded a sweep for — flagged as such.

### The three funded axes

| axis | flag | OFF / default | ON |
|---|---|---|---|
| **Q3 — J7's weight** (was "the biggest single interpretation in the file") | `--j7-weight` | `1.0` = *hesitate*: his 3 farm points are counted a **second** time, on top of the once `flat_base_score` already pays | `0.0` = *naive*: exactly the arithmetic, no hesitation |
| **Q8 — J3 vs J8** | `--j8-break-reserve-floor` | off = **J3 wins**: an overcommit onto a feature you already lead is not a "majority swing", so the reserve floor refuses it | on = "you have to take chances": a pivotal-feature overcommit is exempt from F-J3 |
| **Q1 — J9 cloister caution** | `--j9-avoid-cloisters` | off = grabs cloisters on their naive merit | on = no cloister claim in the first `j9_cloister_block_frac` of the bag unless its 3×3 already holds `j9_min_surrounding` tiles |

Cross with `--preset {current,early}` for the full grid. Any other knob is sweepable via
`--override key=value` without a new flag.

> ⛔ **CORRECTED 2026-08-13 BY MEASUREMENT — THE PARAGRAPH BELOW IS WRONG AND IS KEPT ONLY
> AS THE PROVENANCE OF A RETRACTED FIGURE.** Against the **champion**, cell `J8EX`
> reproduced cell `BASE` **bit-for-bit** — same win rate, same margin (−23.3333), same sem,
> same z, and **0 of 300 games differing in margin** over 300/300 common `(deck_seed, seat)`
> keys. The exemption **changed zero chosen moves.** It is *not* a plumbing failure (four
> checks) — F-J3 is skipped when it would empty the candidate set, so pivotal overcommits are
> already legal without the flag. **The "8–28" below counted the PREDICATE firing
> (`rule_fires`), not the chosen move changing, and/or was measured against `RuleBasedPlayer`
> whose game shapes differ from the champion's. DO NOT CITE IT AS A BEHAVIOURAL-CHANGE RATE.**
> ⇒ Q8 is **untested, not refuted**; reaching the intent ("you have to take chances on the
> pivotal feature") probably needs J8 as a *score* term, not a filter exemption.
> → [J8EX_INERT_FINDING.md](J8EX_INERT_FINDING.md).

⚠️ **Q8 is not a small axis — it changes how often J8 runs at all.** Measured over full
`current`-preset games vs `RuleBasedPlayer`: with the flag OFF, `j8_overcommit` fired on
**0** chosen moves; with it ON it fires on **8–28** moves per game, and F-J3's bite drops
from ~16 to ~10 per game. The reserve floor was silently suppressing J8 almost entirely,
so "does J8 help" and "does J8 break the floor" are very nearly the same question. Read
the two arms as *J8 on* vs *J8 off*, not as a tweak.

### Still open, NOT funded as axes (guesses that nobody is sweeping yet)

4. **J2's planning bar** (was Q2). "Realistic to get there" has no number;
   `j2_reach_threshold=0.50` and the `early`/`current` split (0.30 / 0.50) are invented.
   Sweep with `--override j2_reach_threshold=…` if it becomes interesting.
5. **J6 road-skepticism magnitude.** "generally less bullish on roads than him" is a
   direction, not a number; `j6_road_claim_penalty=1.5` is invented.
6. **J1/J8 thresholds.** "getting on the bigger side" → 5 tiles; "a single large feature"
   → 12 points of swing. Both guess where his eye sets the bar.
7. **J9's own two knobs.** `j9_cloister_block_frac=0.55` (reused from the J10 farm block,
   for lack of a stated one) and `j9_min_surrounding=6` (of 9) are the conservative
   reading; `--override` reaches both.
8. **Which preset is the reference?** The E4 record spans both epochs. `current` is the
   default; if the comparison of record should be `early`, say so.
7. **Assists.** Interview §3 puts tile-bag peek, a virtual-score menu and an occasional
   undo *in scope* for the human reference. The bot already has the first two by
   construction (it counts the multiset, and its base term IS a virtual-score count) and
   cannot brainfart. So the bot is, on those three axes, an **upper bound** on your
   assisted self, not a model of your unassisted play. Is that the intent?
8. **J3 vs J8 — the one rule pair that actively fights.** "Keep at least 1 meeple in hand"
   and "sometimes it takes 2 meeple to secure a city, 3 for a single farm" cannot both hold
   at a thin reserve. As encoded, **J3 wins**: F-J3 is a hard filter and an overcommit onto
   a feature you already lead is not a "majority swing", so at reserve ≤ 1 the second
   meeple is refused. Measured consequence: over full `current`-preset games J8 fires
   rarely (it is live in `early`, which spends more freely). If "you have to take chances"
   is meant to *break* the reserve floor on a pivotal feature, J8 needs its own exemption
   in F-J3 — a one-line change, but a real change of player, so it is not made unasked.

---

## 8. How to run the H2H (do NOT run without an explicit go-ahead — this is champion-budget compute)

Bench one game first (house rule: pre-flight at PRODUCTION knobs, only the count differs):

```bash
.venv/bin/python scripts/joshuabot/h2h.py --decks 1 --limit 1 --out /tmp/jb_bench.jsonl
```

The fleet — **n=400 paired decks = 800 games**, detached, resumable:

```bash
setsid nohup nice -n 19 .venv/bin/python scripts/joshuabot/h2h.py \
    --decks 400 --preset current --profile fixed_v1 --workers 14 \
    --out measurement/joshuabot_20260812/h2h_current.jsonl \
    --resume >> measurement/joshuabot_20260812/driver.log 2>&1 & disown
```

A tournament arm (all three axes flipped):

```bash
setsid nohup nice -n 19 .venv/bin/python scripts/joshuabot/h2h.py \
    --decks 400 --preset current \
    --j7-weight 0.0 --j8-break-reserve-floor --j9-avoid-cloisters \
    --workers 14 \
    --out measurement/joshuabot_20260812/h2h_j7w0_j8brk_j9av.jsonl \
    --resume >> measurement/joshuabot_20260812/driver.log 2>&1 & disown
```

**The full flag surface**

| flag | default | meaning |
|---|---|---|
| `--decks N` | 400 | deck seeds; each is played BOTH seatings → 2N games |
| `--seed-base` | 5400000 | picks the deck band — **register it in `governance/BAND_REGISTRY.csv`** |
| `--preset {current,early}` | `current` | the J10 epoch |
| `--j7-weight FLOAT` | `1.0` | J7 hesitation; `0.0` = naive count |
| `--j8-break-reserve-floor` | off | pivotal overcommit is exempt from the J3 reserve floor |
| `--j9-avoid-cloisters` | off | J9 cloister caution |
| `--override KEY=VALUE` | — | any other `JoshuaParams` knob, repeatable, typed, applied last (wins over the named flags); an unknown knob raises |
| `--profile` | `fixed_v1` | rules profile (implies `R9=1`) |
| `--workers` / `--rust-threads` | 14 / 1 | fleet shape |
| `--sims` / `--k-dets` | PRODUCTION.yaml | SMOKE ONLY overrides of the champion budget |
| `--out` / `--resume` / `--limit` | — | output JSONL, resume contract, bench cap |

* **One variant per `--out`.** The driver reads the `joshua_variant_id` already in the file
  and **refuses to append a different one** — a paired margin blended across two players is
  not a measurement of anything.
* Every run writes `<out>.manifest.json` **before the first game**: `variant_id`, the full
  resolved `JoshuaParams`, the axes, the overrides, the profile env, and `argv`; the
  summary is written back into it at the end. Every JSONL record also carries
  `joshua_variant_id` / `joshua_axes` / `joshua_overrides`, so a cell is self-describing
  even in isolation.
* `--decks N` plays **both seatings** of each of N deck seeds → 2N games; the reported
  statistic is `paired_margin_mean ± paired_margin_sem` over the N decks.
* `--preset early` runs the other epoch (a separate output file, never the same one).
* **Tournament sizing warning.** These are champion-budget games; the axis grid is
  2 presets × 2 × 2 × 2 = 16 arms, and 16 × 800 games is not a thing to launch casually.
  Screen the axes one at a time against the default arm before buying the full grid, and
  give **each arm its own band** or accept that cross-arm contrasts inherit the ~1.5–2×
  cross-band humility factor.
* `--profile fixed_v1` is the default and matches the E4 rules epoch. ⚠️ It implies
  `CARCASSONNE_FIX_R9=1`, which is **not** the production default — numbers from here are
  **not comparable to walled elo**. Use `--profile walled` for an R9-off run.
* **Band discipline:** `--seed-base` picks the deck band. Register the band in
  `governance/BAND_REGISTRY.csv` before a confirmatory run, and do not reuse a band that
  already influenced a decision.
* Read the verdict off the **paired** margin, never the unpaired mean, and remember the
  cross-band humility factor (CLAUDE.md: inflate σ ~1.5–2× on any cross-band contrast).

**ETA (measured, not extrapolated):** Joshua-bot costs ~50–85 ms/move on the local box
(one `flat_leaf.decompose` per candidate, plus one per meeple follow-up); the champion at
the PRODUCTION.yaml budget on the Rust backend dominates the cell. Bench one cell before
sizing the fleet.
