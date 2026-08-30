# PROTOCOL — the Carcasum-unfamiliar owner session

> **Status: PREP, 2026-08-30. Pre-registration draft — not launched, no games played.**
> Read [`SETUP.md`](SETUP.md) once to get the program running and
> [`RULES_DELTA.md`](RULES_DELTA.md) once to know what you are playing. Then this page is
> the whole session.

---

## 1. Why — one paragraph, then please stop reading about it

You beat the frozen champion by roughly 13 points a game across ~50 phone games. You have
also now played it ~60 times, and it never changes. Some unknown share of that 13 points
is **transferable skill**, and some is **cross-game adaptation to one stationary
opponent** — you have learned *this* program's habits. Nobody can separate those two from
the phone archive, because every game in it is against the same opponent.
This session separates them by handing you a strong program you have **never mined**:
Carcasum, an out-of-lineage MCTS from a 2014 master's thesis, which our champion beats by
about the same small margin it loses to you by. If your edge is skill, it should show up
against Carcasum too. If it is adaptation, it should mostly vanish.
(Claim [`CL-083`](../../governance/CLAIM_REGISTRY.csv) names this exact experiment as one
of its falsifiers.)

---

## 2. ⚠️ Blindness — the one thing that can spoil this before it starts

**Please don't read up on Carcasum before you play.** No thesis, no source, no forum
posts, no watching it play itself, no asking Claude how it thinks. The whole measurement
is *what your edge looks like against an opponent you have not studied*, and half a day of
reading would quietly delete the thing being measured.

Concretely: don't open `vendor/carcasum/`, and if a build error puts source on your screen,
that's fine — reading a compiler message is not studying an opponent. After the last game,
read anything you like.

The same applies during the run: **don't review your own finished Carcasum games between
games.** Play them, log the score, start the next one. (You are of course free to *think*
during a game — that's just playing.)

---

## 3. Conditions

| | |
|---|---|
| **Opponent** | Carcasum `MCTS` / utility `Portion` / playout `Random` / **Time Limit 5000 ms** / `Cp 0.5`. In the New Game dialog **the only thing you change is picking `MCTS`** — every other field is already at the right default ([`SETUP.md`](SETUP.md) §1). |
| **Box** | The **laptop**, please. It is the box the anchor was measured on, and Carcasum's budget is CPU-time, so a faster core is literally a stronger opponent ([`SETUP.md`](SETUP.md) §2). If you use the desktop, write "desktop" in the log and we discount accordingly. |
| **Rules** | `fixed_v1` + R9 — **the same rules as your phone games**, audited 50/50 exact including farms ([`RULES_DELTA.md`](RULES_DELTA.md)). Board is effectively unbounded, unlike the app. Tiles are 2014 JCZ artwork; 24 kinds instead of 32 but the same 72-tile deck. |
| **Seats** | **Alternate**: you are seat 0 on odd-numbered games, seat 1 on even. The engine-side anchor is seat-balanced, so this side should be too. |
| **Game ▸ Random Tiles** | must stay **ticked**. `Choose Tiles` lets you pick your own draw — that's a cheat switch. |
| **No takebacks** | The Game menu has **Undo**. Don't use it. A misclick that Undo would fix: use Undo, then write `undo:misclick` in the log's note column — an honest logged undo is fine, a silent one poisons the sample. |
| **No clock on you** | Take as long as you like. Carcasum takes ~5 s per turn × ~35 turns ≈ **3 minutes of thinking per game**; the rest of the wall is yours. |
| **Every started game counts** | Including losses, including bad ones. A game abandoned mid-way is logged as `abandoned` with the reason and is **excluded**, but if more than 2 games get abandoned tell us before continuing — selective abandonment is the one thing that can silently fake this result. |
| **No engine help** | No champion, no analyzer, no second opinion, during or between games. |

---

## 4. How many games — the honest arithmetic

The two hypotheses predict two different mean margins for you against Carcasum, chained
through numbers we already hold. Both anchors are matched to the same conditions —
`fixed_v1`+R9, champion at k8×1376 with the tie-arbiter **off**, which is what 49 of your
archived games were actually against:

```
A = you  − champion         = +13.265 pts/game   SE 3.665   (n=49 E4 games, unpaired)
                                                             measurement/e4_games, stratum:
                                                             fixed_v1, k8x1376, no tiearb_level
B = champion − Carcasum@5s  = + 3.4075 pts/deck  SE 1.019   (n=200 decks x 2 seats = 400 games,
                                                             deck-paired, band 147e9, laptop;
                                                             carcasum_arb_challenge ARM-OFF)

H_TRANSFER  ("the edge is skill")      predicts  M = A + B = +16.67   SE 3.81
H_ADAPT     ("the edge is adaptation") predicts  M = B     = + 3.41   SE 1.02
separation  = A = 13.27 pts/game
```

Your per-game margin scatters with **sd ≈ 25.7** (measured, same stratum). So:

| n games | SE of your mean | σ separating you from H_ADAPT | σ separating you from H_TRANSFER | verdict quality |
|---|---|---|---|---|
| 10 | 8.1 | 1.62 | 1.48 | **directional only** |
| 15 | 6.6 | 1.98 | 1.74 | coarse; can rule out at most one side |
| **20** | **5.7** | **2.28** | **1.93** | **minimum for a real read** |
| 25 | 5.1 | 2.53 | 2.06 | both sides ≥2σ |
| **30** | **4.7** | **2.77** | **2.20** | **recommended if you have the appetite** |
| 40 | 4.1 | 3.16 | 2.39 | diminishing |
| ∞ | 0 | 13.0 | **3.48 — hard ceiling** | |

Two things that table is telling you honestly:

1. **n=10–15 is a pilot, not a verdict.** At 1.5–2.0σ it can point a direction and it
   cannot settle the question. If that is all the appetite there is, run it and we will
   report it *as* a pilot — but don't let anyone quote it as an answer.
2. **There is a ceiling at ~3.5σ no matter how many games you play**, because the
   `A` anchor — your own edge over the champion — is itself only known to ±3.7 pts from 49
   games. More Carcasum games cannot buy past that. The cheap way to lift the ceiling is
   more *phone* games, not more Carcasum games.

**Recommendation: n = 20, extend to 30 if it is going well.** At ~15 min/game that is
about **5 hours** for 20 and **7–8 hours** for 30 — spread over sittings is fine.

**Please interleave ~5 fresh phone games** (champion, current settings, logged as usual)
across the same days. Not for power — for form. Your edge over the champion is known to be
non-stationary, and a session run in a week where you happen to be playing well or badly
is otherwise uncorrectable.

---

## 5. What to record

The read depends only on the tally. Everything else is free upside.

### 5.1 The tally (this is the deliverable)

One line per game, `measurement/carcasum_owner_session/tally.csv`:

```csv
game_no,date,box,your_seat,your_score,carcasum_score,archive_file,notes
1,2026-08-31,laptop,0,84,71,1788012345,
2,2026-08-31,laptop,1,63,79,1788019876,undo:misclick
```

* `your_seat` 0 or 1 — alternate per §3.
* `archive_file` — the filename Carcasum wrote (§5.2). If you lose it, leave blank; the
  scores are what the read uses.
* `notes` — anything: `abandoned:interrupted`, `undo:misclick`, `felt tilted`, blank.

### 5.2 The archive you get for free

Carcasum autosaves the **complete move history** after every move to

```
~/.local/share/YMSolutions/Carcasum/games/<epoch-seconds-at-game-start>
```

(the exact path is printed to stderr when the GUI starts). One file per game, named by
start time. **Please just don't delete that directory** and copy it into the run dir at
the end — that is the entire ask.

Honest statement of what it does and doesn't buy: the files are lossless and replayable
*inside Carcasum*, but **the importer into our own harness does not exist yet**
([`SETUP.md`](SETUP.md) §7). So this session's *pre-registered* read uses **final scores
only**. If the archive is kept, a later adapter unlocks per-ply work (EV-loss grading,
continuation pricing, the agreement gradient) on these games retroactively. If it is lost,
that option is gone and the scores still work.

Screenshots are **not** needed. Don't bother.

---

## 6. The pre-registered read — fixed before game 1, first match wins

Estimator: `M̂ = mean over the n logged games of (your_score − carcasum_score)`,
seats alternated, abandoned games excluded.

Derived quantity — the **adaptation share**:

```
Â = 1 − (M̂ − B) / A            Â = 0 ⇒ the edge transfers entirely
                                Â = 1 ⇒ the edge is entirely adaptation
midpoint M̂ = +10.04  ⇔  Â = 0.50
```

| branch | fires when | reported as |
|---|---|---|
| **T-ADAPT** | `M̂ < 10.04` **and** `\|M̂ − 16.67\| / √(SE_M̂² + 3.81²) ≥ 2.0` | **Adaptation-dominant.** The owner edge does not survive an unmined opponent. CL-083's adaptation-share falsifier fires; the steering program re-ranks. State `M̂`, `Â`, and both z's. |
| **T-SKILL** | `M̂ > 10.04` **and** `\|M̂ − 3.41\| / √(SE_M̂² + 1.02²) ≥ 2.0` | **The edge transfers.** The skill is general, not opponent-specific; CL-083's adaptation route is de-prioritised and the search for the mechanism continues against the champion. |
| **T-PARTIAL** | neither z reaches 2.0 | **Inconclusive.** Report `Â` with its interval and re-rank nothing. Extend to n=30/40 only if the point estimate is near the midpoint — if it is pinned at one end and merely underpowered, more games is the right move; if it is genuinely mid, `Â ≈ 0.5` may just be the true answer. |
| **VOID** | any of §7's gates fails, or fewer than 10 games completed | No read. Say why. |

**A number this session cannot produce.** This is a *suggestive* discriminator, not a
verdict, for one structural reason that must be stated wherever the result is:
**it assumes point margins are additive across opponents**, and this program has been
burned by non-transitivity before — the leaf effect is documented non-transitive
([`clean_eval/CLEAN_EVAL_AUDIT.md`](../../clean_eval/CLEAN_EVAL_AUDIT.md)), and CL-070 had
a same-family anchor mis-order a +50 elo contrast *including its sign*. Carcasum also
plays a completely different way from the champion (tens of thousands of full random
rollouts, versus a narrow heuristic-leaf search), so the owner's margin against it could
move for pure style reasons that have nothing to do with adaptation. **This registers as
evidence toward CL-083, never as a claim of its own.**

---

## 7. Gates — check these, don't assume them

Cheap, and each one has a way of silently faking the headline:

| gate | check | why |
|---|---|---|
| `G-BINARY` | the GUI was built from `vendor/carcasum` (patched), **not** upstream's `Carcasum-win32.zip` | unpatched Carcasum scores a 2-tile city **2, not 4** — a rules result in a strength result's clothes ([`RULES_DELTA.md`](RULES_DELTA.md) §2.1) |
| `G-CONFIG` | player type `MCTS`, utility `Portion`, playout `Random`, `Time Limit` 5000, `Cp` 0.5 — screenshot the dialog **once**, before game 1 | a *normalised* utility would activate the one stale rule we deliberately left unpatched |
| `G-BOX` | which box, logged per game | Carcasum's strength scales with single-core speed (§3) |
| `G-SEATS` | seats alternate, ≈ half each | the anchor is seat-balanced |
| `G-N` | ≥ 10 games, and ≤ 2 abandoned | selective abandonment is the only way this sample can lie |
| `G-BLIND` | no Carcasum material read before or during (§2) | it is the measurement |

---

## 8. Before you start — 60-second checklist

1. Build done, `carcasum_gui` launches ([`SETUP.md`](SETUP.md) §4).
2. First-run "download JCloisterZone-2.6.zip?" → **No**.
3. **Help ▸ Controls** — read it once.
4. **Game ▸ Random Tiles** ticked.
5. New Game: two seats, you + a PlayerSelector opponent set as §3. **Screenshot that
   dialog** (`G-CONFIG`) and never open it again.
6. Note the `QStandardPaths::DataLocation` line the GUI printed at startup — that's where
   your archives are going.
7. `tally.csv` open in another window.
8. Play.
