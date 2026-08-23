# Carcasum smoke at production knobs — timings, and a correction

> **Status: COMPLETE 2026-08-23. Gate 6 discharged.** 4 games, champion vs their
> `MCTSPlayer` at the thesis budget of 5000 ms/turn, on the **laptop under exclusive
> tenancy** (24 cores, loadavg 0.14 at launch). Zero voids, 4/4 final-score agreement,
> 4/4 farm agreement, zero REAL divergences.
>
> **The headline is a correction, not a confirmation:** their throughput on our hardware
> is **not** ~2× the thesis's as the prereg previously estimated. At the median it is
> **1.08×**, and in the opening it is **0.65×** — i.e. *slower*. See §2.
>
> Archive `smoke.jsonl` · driver `c090847e…` (laptop build) · dev seeds `5200000..5200001`,
> deliberately **not** band 1.42e11.

---

## 1. The numbers

```
records                  4   (2 decks x 2 seats, production knobs, opp 5000 ms/turn)
voids                    {}          REAL divergences   {}
final score agreement    4/4         farm agreement     4/4      replay_ok  4/4
champion                 763.0 ms/move      (min 653.2  max 845.4)
opponent                 5016.2 ms/turn     (median 5006.7, max 5157.7, budget 5000)
                         0/142 turns exceeded budget+200ms
opponent playouts/turn   mean 163,786   MEDIAN 46,332   Q1 32,498   Q3 93,524
                         min 27,410     max 2,667,883
wall                     228.5 s/game       (min 223.2  max 235.0)
opponent turns/game      35-36              our think-moves/game  64-70
```

**The budget is honoured precisely.** 5016.2 ms mean against a 5000 ms setting is +0.3 %,
and not one of 142 turns ran more than 200 ms over. That is the `thread_clock` behaving
as designed, and at W=4 there was no contention to inflate it.

**The wall decomposes cleanly**, which is the check that the projection in §3 rests on:
`36 turns × 5.016 s = 180.6 s` (opponent) `+ 67 moves × 0.763 s = 51.1 s` (champion)
`= 231.7 s`, against a measured 228.5 s. Only one side thinks at a time, so a game
consumes ≈ 1 core continuously for its whole wall.

## 2. ⚠️ The playouts figure, and the correction it forces

`PREREG_DRAFT.md` §2.1 previously carried this claim:

> *"Their throughput on our hardware is ~2× the thesis's, so this is a STRONGER Carcasum
> than the one that published 84 %."* — extrapolated linearly from a **50 ms** budget on
> the local box, and explicitly flagged there as "an estimate to be replaced by the gate-6
> smoke's measurement at the real budget."

**Measured at the real budget, that is wrong, and wrong in the direction that matters.**

The distribution is violently skewed, because a Carcasum playout is a **full random rollout
to the end of the game**: early, each rollout is ~70 plies and playouts are expensive; by
the last few turns a rollout is 1–2 plies and playouts explode.

| ply band | mean playouts/turn |
|---|---|
| 0–9 | 27,915 |
| 20–29 | 30,557 |
| 40–49 | 35,193 |
| 60–69 | 43,182 |
| 80–89 | 57,897 |
| 100–109 | 91,702 |
| 120–129 | 217,528 |
| 130–139 | 955,021 |
| 140–149 | 2,595,462 |

So against the thesis's **42,879 playouts/turn**:

| statistic | ours | vs thesis |
|---|---|---|
| **mean** | 163,786 | **3.82×** — an artefact, do not quote |
| **median** | 46,332 | **1.08×** — parity |
| **opening (ply 0–9)** | 27,915 | **0.65×** — we are *slower* |

**The mean is dominated by endgame turns where the decision is nearly trivial and the
rollouts are nearly free.** The plies that decide a game — where the branching is wide and
the position is still open — run at **0.65–1.1×** the thesis's throughput.

**What this changes.** One of the five reasons the inventory gave for the transitive 84 %
possibly *under*-stating a modern Carcasum (§3.1 item 5: "a modern Carcasum is stronger
than the thesis's") **does not survive measurement on this hardware.** The opponent we
will face is, in throughput terms, roughly *the* thesis's Carcasum — not a stronger one.
This does not resurrect the +188 in the other direction either; it removes a thumb from
the scale, which is all. §0.1's refusal to carry the transitive number forward stands
unchanged and is, if anything, better supported.

**Method note worth keeping:** the error came from extrapolating a throughput linearly
from a 40×-smaller budget on a different box. The prereg had already labelled that figure
an estimate pending this measurement, and the measurement duly overturned it. *Bench, then
extrapolate — never the reverse*, and quote a median when the distribution is skewed.

## 3. Projected wall for the rated match (n = 400)

Basis: **228.5 s/game** measured at W=4, and a game occupying ≈ 1 core for its duration.

| workers | linear projection | with contention allowance | note |
|---|---|---|---|
| **W=8** | 3.17 h | ~3.2–3.5 h | comfortable, lots of headroom on 24 cores |
| **W=14** | 1.81 h | **~2.0 h** | **recommended** — the smallest W within ~10 % of practical peak |
| **W=22** | 1.15 h | ~1.4 h | 22 of 24 cores; DRAM contention is this project's known bottleneck |

**Two properties make higher W safe for *validity*, not just speed:**

1. **The opponent's search size is invariant under contention.** Its budget is thread
   CPU-time, so a descheduled opponent still gets its full 5 CPU-seconds — it just takes
   longer in wall terms. **W is a throughput knob, not a strength knob.** Contention
   degrades our champion's wall clock and the run's duration; it cannot quietly weaken the
   opponent.
2. Each game is single-threaded on both sides and strictly alternating, so worker count
   maps almost 1:1 onto cores.

**Validate rather than trust:** the projection is from a 4-game sample at W=4 on an idle
box. Read the realized `wall_secs_per_game_mean` off the first ~20 finished games and
re-project before assuming the full wall.

## 4. What this smoke does NOT establish

**Nothing about strength.** n=4 is noise, and the prereg pre-commits to not reading it.
The two smoke runs make that concrete — *the same 4 decks, the same configuration, run
twice*:

| run | W/D/L | win rate | paired margin |
|---|---|---|---|
| first | 3/0/1 | 0.75 | +15.75 |
| second | 2/0/2 | 0.50 | +10.75 ± 16.25 |

Same decks, opposite-looking headline. That is exactly what a **non-CRN opponent** at n=4
looks like (Carcasum's seed is compile-time only, so its MCTS is not reproducible even on
an identical deck), and it is why the decision rules in the prereg are written against
n=400 with a pre-registered top-up rather than against whatever the first numbers happen
to say.

## 5. Provenance

- Laptop driver sha256 `c090847e1befa007e9b3b3031a9c880a60915e36f143aa6c3c30691599792968`
  (the **primary** provenance witness — the vendored tree has no `.git`, so a git rev is
  secondary). The local build has a different binary sha256, as it must.
- `--dump-tiles` is **byte-identical** across the two boxes (`7c771afe…`), which is the
  cross-box witness that the tile model is toolchain-independent.
- Rules `fixed_v1` + `CARCASSONNE_FIX_R9=1`, stamped per game.
- Opponent `MCTSPlayer<PortionUtility, RandomPlayout>`, `Cp=0.5`, `reuseTree=false`, no
  priors/widening/bias — the exact configuration the thesis's 84 % was measured at.
