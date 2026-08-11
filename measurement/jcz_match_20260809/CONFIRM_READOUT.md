# JCZ external-AI match, n=400 deck-paired — the program's first out-of-lineage rating

> **Status: COMPLETE 2026-08-09. VERDICT: the champion beats JCloisterZone's AI decisively —
> +111.4 elo (wr 0.655) / deck-paired +6.50 ± 0.86 pts, z 7.55.** The n=20 smoke's "LEVEL"
> reading did **not** hold; see [§3](#3-why-the-smoke-said-level-and-what-actually-generalised).
> Zero voids, zero REAL divergences, 400/400 exact score agreement across 56,777 plies.
>
> Harness: [`scripts/jcz_match/`](../../scripts/jcz_match/) (built + smoked earlier the same day) ·
> archive `confirm.jsonl` · analyzer `scripts/jcz_match/analyze.py` · band **1.08e11** ·
> ~47 min wall at W14 on the exclusive local box. No cloud spend.

---

## TL;DR

1. **The champion wins, and it is not close in the statistical sense.** 258W / 8D / 134L over 400
   games = **wr 0.6550 → +111.4 elo (1σ ±17.4 within-band)**; the deck-paired margin is
   **+6.50 ± 0.86 points per deck, z 7.55**. Both statistics agree, and the paired one is the
   load-bearing one.
2. **But the size of the win is the finding, not the sign.** 11,008 sims of PIMC with an exact
   endgame latch — ~1,329 ms/move — beat a **static one-turn evaluator costing 38 ms/move**
   (~35× cheaper) by 6.5 points a deck. That is a real edge and it is also a *small* edge for
   that compute ratio. The uncomfortable reading in
   [TERM_ARCHAEOLOGY §5](TERM_ARCHAEOLOGY.md) survives the resolution upgrade intact.
3. **This is a usable, non-saturated, out-of-lineage reference.** JCZ's AI shares no leaf, no
   search and no engine with us. wr 0.655 is comfortably off both rails — it is neither the
   ~0.5 of a peer nor the ~1.0 of a saturated Tier-1. It is the first opponent this program has
   that can be beaten *and* can still move.
4. **The rules are certified, not assumed.** Across 400 games / 56,777 plies the per-ply
   legality + score + partition diff produced **zero REAL divergences**, and JCZ's independently
   computed final scores equalled ours in **400/400** games. The win rate cannot be a rules
   artefact.

---

## 1. The numbers

```
records           400   scored=400   voids={}
W/D/L             258/8/134
win rate          0.6550   -> elo +111.4   (1 sigma ~ +/-17.4, within-band)
DECK-PAIRED       +6.50 +/- 0.86 pts   (z 7.55)   over 200 decks
unpaired margin   +6.50   sd 18.39
  champ_seat=0      n=200  W=134 D=3   mean margin +8.37
  champ_seat=1      n=200  W=124 D=5   mean margin +4.62
mean final score  champion 99.5   JCZ 93.0
margin spread     median +7   min -49   max +55
divergences       counts={UNPLACEABLE_REDRAW: 23, WALL_LEGALITY: 2}   REAL={}
score agreement   final_agree 400/400    replay_ok 400/400
timing            champion 1329 ms/move   JCZ 38.1 ms/move   98.1 s/game
```

**Configuration.** Champion `puct_priors_v29_bmild_cap8` at the PRODUCTION.yaml deploy budget
k8×1376 = 11,008 sims, rust backend, `verify=True`, leaf hash `a36d2e15a3b3d71d`. Opponent
`LegacyAiPlayer` on JCZ rev `29a1561`, tile set `basic:2`. Rules `fixed_v1` +
`CARCASSONNE_FIX_R9=1`. Band 1.08e11, seeds `108000000000..108000000199`, each deck played
twice with the seats swapped.

**Seat asymmetry is expected and is exactly what the pairing removes.** Seat 0 earns +8.37 and
seat 1 +4.62; the ~3.75-point gap is the first-player advantage, and averaging the two seatings
of each deck is what makes the +6.50 an unbiased estimate of strength rather than of seat luck.

**The one σ to be careful with.** ±17.4 elo is the *within-band* figure. Nothing here is a
cross-band contrast, so the 1.8–2.2× over-dispersion rider does not apply to this number — but
it **would** apply to anyone comparing this band against another, and that includes comparing
this result to any walled-era elo.

---

## 2. The divergence ledger — and the two free findings

The whole point of running the match through the D1 oracle is that a win rate arrives with its
rules provenance attached. Two classified classes fired; **neither is REAL, neither is
score-moving, and neither voided a game**.

| class | events | games | reading |
|---|---|---|---|
| `UNPLACEABLE_REDRAW` | 23 | 23 | **Benign, and a positive result.** Both engines discarded an unplaceable tile and drew again, in lockstep, 23 times. JCZ does this in `TilePhase` (`placements.isEmpty() → discardTile`, loop); we do it via `fixed_v1`'s `draw_rule="redraw"`. `UNPLACEABLE_TURN_LOSS` — the divergent form — fired **0 times**. This is the A3 rules lever being *confirmed correct against an independent implementation* 23 times over. |
| `WALL_LEGALITY` | 2 | 2 | **The bounded-board class, now with a measured rate.** JCZ offered a placement our representation could not express: deck `108000000062` ply 128 (`BA/CG` at `[1,−13]`) and deck `108000000068` ply 140 (`BA/CFc+` at `[0,−13]`, two rotations). Both at y = −13, i.e. 13 rows north of the start tile — the 25×25 *action window* running out before the 35×35 grid does. Non-contaminating by construction: it only ever *adds* options on JCZ's side and our player picks from *our* set, so the boards stay identical — and the data agrees, since both games carry `final_agree=True` and ordinary scores. |

`WALL_LEGALITY` is the honest asterisk on this result, so state it precisely: the bounded
representation cost us a legal option **twice in 56,777 plies** (~1 in 28,000; 2 games in 400,
0.5%). [VALIDATION_REPORT §5](../jcz_oracle_20260803/VALIDATION_REPORT.md) said the class
"shrinks toward zero; it is not proved empty" — it is now measured at 0.5% of games rather than
bounded by hand-waving. It is far too rare to move a +111 elo verdict, and it is real, and both
of those should be said in the same breath.

**Zero `VOID_UNMAPPABLE`.** JCZ never chose a move our action space could not encode, across
every ply of every game — so the inversion path (forward-map our legal moves through the
certified `to_jcz_position` / `jcz_rotation_quarters` / `jcz_location_for` and match) never once
came up empty.

---

## 3. Why the smoke said LEVEL, and what actually generalised

The n=20 smoke read **wr 0.525, deck-paired +4.60 ± 2.23 (z 2.07)** and was written up as
"level". At n=400 the truth is wr 0.655 / +6.50 ± 0.86. The methodological lesson is sharp, and
it is the one CLAUDE.md already warns about:

| statistic | n=20 | n=400 | held up? |
|---|---|---|---|
| **deck-paired margin** | +4.60 ± 2.23 | **+6.50 ± 0.86** | **YES** — within 0.85σ of the final value. The paired margin was *already telling the truth* at n=20. |
| win rate | 0.525 | **0.655** | **NO** — off by 0.13, about 1.2σ at n=20 (±0.11). Worthless at that n, and it is the number that produced the "level" headline. |

So the smoke was not wrong about the *magnitude*; it was wrong because the **win rate** was
quoted as if it meant something at n=20. The deck-paired margin — the statistic CLAUDE.md names
as the robust class — was accurate from the start and merely under-powered (z 2.07 → 7.55).

**Correcting the record:** the LEVER_INDEX row and the smoke commit both claimed JCZ's AI "plays
our champion LEVEL" and that the saturation prior was wrong. Half of that stands and half does
not:

* ❌ **"LEVEL" is retracted.** +111 elo is a decisive win, not parity.
* ✅ **"Does not saturate" stands, and is the durable claim.** The original prior was that JCZ's
  AI would "saturate instantly (then it's a floor marker, not a ruler)". At wr 0.655 it is
  emphatically not saturated — a saturated reference reads ≥0.95 and cannot resolve anything.
  This opponent has ~111 elo of headroom *below* us that is still measurable, which is exactly
  what a ruler needs.

---

## 4. What this buys the program

**Structural blocker #1 is dented, not closed.** The blocker is "no strong non-saturated
reference exists yet — self-anchored elo can climb while absolute strength regresses". We now
have a reference that is genuinely outside the lineage (independent leaf, independent search,
independent engine, independent rules implementation certified ply-by-ply) and genuinely
non-saturated. It is *not* strong enough to be the superhuman yardstick — it is ~111 elo below
the champion — but it is an **absolute** anchor that cannot drift with our training, which is
precisely the property every internal ladder lacks.

Concretely, it can do three things no internal anchor can:

1. **Catch absolute regression.** Any future champion that scores below +111 elo here has lost
   real strength, whatever the self-play ladder says.
2. **Price a lever in out-of-lineage terms.** A leaf or search change can be graded against an
   opponent that has no correlated blind spots with us.
3. **Host the disagreement mining.** The 400-game archive is a corpus of 56,777 plies where two
   structurally different evaluators chose moves on identical boards — the input
   [TERM_ARCHAEOLOGY](TERM_ARCHAEOLOGY.md) step 1 needs and does not have.

**The compute-ratio finding is the one to sit with.** The champion spends ~35× the per-move
compute of a one-turn static evaluator and converts it into 6.5 points a deck. Read against
blocker #2 (the hand-crafted leaf caps learned strength near strong-human by construction), this
is another instance of the same shape: enormous search on top of a hand-crafted evaluator buys
a modest, bounded amount. It does not by itself prove the leaf is the binding constraint — a
proper attribution needs the budget ladder against *this* opponent — but it is consistent with
every other measurement that says so.

---

## 5. Honest limits

* **One opponent, one configuration.** `LegacyAiPlayer` has **no configuration knobs at all** —
  no depth, budget, temperature, or seed — so there is no "stronger JCZ" to try. The rating is
  against this specific agent, full stop.
* **One band, one deck draw.** 200 decks from band 1.08e11. Within-band deck-paired, which is
  the robust class, but it is still one draw.
* **`fixed_v1` + R9-on ⇒ NOT comparable to walled elo.** R9 is built and **not adopted**; it is
  forced on here because it is the only configuration in which the two engines are provably
  rules-identical. Any comparison of +111.4 against a walled-era number is invalid.
* **Garden semantics remain out of reach** (gardens are off in the JCZ setup so the comparison
  is like-for-like), and **feature-level ownership is not diffed** — only partitions and scores.
  Two engines could in principle disagree about who owns a contested farm while agreeing on both;
  that would be invisible here.
* **The 0.5%-of-games wall class is real.** Rare enough to be irrelevant to this verdict; not
  zero, and not proved empty.

---

## 6. Reproducing

```bash
scripts/jcz_match/build_ai_shim.sh            # javac the AI shim against the shaded Engine.jar

setsid nohup nice -n 19 .venv/bin/python scripts/jcz_match/match.py \
    --decks 200 --seed-base 108000000000 --champ-seat both --workers 14 \
    --out measurement/jcz_match_20260809/confirm.jsonl --resume \
    >> measurement/jcz_match_20260809/confirm_driver.log 2>&1 & disown

measurement/jcz_match_20260809/run_watchdog.sh &      # on-disk heartbeat (dirty-crash box)
.venv/bin/python scripts/jcz_match/analyze.py measurement/jcz_match_20260809/confirm.jsonl
```

The run completed uninterrupted in ~47 min at W14 (14 python workers × 1 JVM each, load ~15 of
32 threads). The box had dirty-crashed twice the previous night and came up 3 minutes before
launch; `--resume` skips any `(deck_seed, champ_seat, replicate)` already in the archive, and
the watchdog log is the crash-vs-hang discriminator. Neither was needed this time.
