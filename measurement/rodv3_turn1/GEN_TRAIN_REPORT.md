# rodv3 turn 1 — overnight ops report (2026-07-29 23:30 → 2026-07-30 10:00 EDT)

> **STATUS: GEN PARKED at 65/300, NO TRAIN, and the night was re-prioritised mid-flight by
> Joshua.** The funded scope changed at 01:25 from "gen 300 → train one iteration" to
> "**run the premise eval first**". That eval is **COMPLETE**; its result is the headline and
> lives in [teacher_h2h_94e9/READOUT.md](../teacher_h2h_94e9/READOUT.md). The turn-1 **gate was
> never funded and never ran.** `governance/PRODUCTION.yaml` untouched; no `results.csv` row
> written by this agent.

## Headline

**The CL-067 net at k4×688 = 2752 measures −20.9 ± 17.4 elo (z −1.20) against its own corpus
teacher, the champion at k8×1376 = 11008**, with the deck-paired margin agreeing in sign at
**−2.0025 pts/deck (z −1.90)**, n=400 deck-paired, fresh band 94e9. Pre-registered branch:
**bracket-narrowing, not a verdict** — the pre-committed n→800 extension fires and is **not
launched** (a ~7 h two-box spend; Joshua's call).

## What ran where, and when

| when | box | what | outcome |
|---|---|---|---|
| 23:30–00:26 | local | prep + prereg (session died ~23:55 before any cell fired) | prep survived on the share; **zero games lost** |
| 00:30–01:24 | local 5900XT, **W\*=16** | rodv3 turn-1 gen, 300-game pool | **33 games** banked, then stopped for the pivot |
| 01:38–02:23 | laptop, **W\*=16** | joined the same gen pool | pool **33 → 65**; 32 games in ~43 min ≈ 81 s/game |
| 01:01–01:41 | Air (M5/ANE) | gen-side W mini-sweep (throwaway) | **W\*=4**, 30.1 games/h — [report](../rodv3_air_wsweep/AIR_GEN_WSWEEP.md) |
| 01:34–02:05 | local, W12 | teacher-h2h **pre-flight smoke**, 10 games | costs measured; proposal's estimate corrected |
| 02:08–09:56 | local **W20** + laptop **W12** | teacher-h2h **n=400 cell**, band 94e9 | **COMPLETE, n=400 verified** |

**W\* per box (all settled by the house crude→refine→settle-low rule, never the argmax):**
local gen **16**, laptop gen **16**, Air gen **4**, local eval **20**, laptop eval **12**.

## Games completed at each transition

- rodv3 gen: 0 → **33** (local alone) → **65** (with the laptop) → **parked at 65/300**, claims at
  parity on both hosts, losslessly resumable via `--shared-claim`.
- ℹ️ **READ-THE-RESULT NOTE (added 2026-07-30, false-negative sweep `059c982` S3): this gen is the
  first learned-track generation ever run at `c_puct` 1.5 self-play** (prereg line 43,
  `--c-puct 1.5`) — the never-executed arm of the **2026-05-28 c_puct conflation**, in which the
  self-play `c_sp` and the eval `c` were changed together and the "+47 elo" was later found to be a
  noise spike. Two consequences for whoever reads these 65 (or 300) games' downstream verdict, and
  they point in opposite directions: **a GROWTH signal is confounded with the budget change and must
  NOT be attributed to budget alone**; **a NULL is NOT attributable to the old `c_sp` = 3.0**, because
  this run does not use it. Zero incremental compute is owed — the arm is already covered by this
  gen; only the interpretation needs to carry the caveat.
- teacher h2h: 0 → 400/400 records, `n=400`, `n_paired=200`, verified before any number was read.

## Train outcome

**None — and deliberately so.** Training was chained on-box (`rodv3_train_chain.sh`, armed 00:33 so
a second session death could not stall it) and waits for 300 npz. At the 01:25 pivot I disarmed it
**first**, before touching gen: it would otherwise have fired a GPU training run straight into the
h2h eval when the pool later filled. No checkpoint was produced; `rodv3_turn1/ckpt/` is empty.

## Numbers worth carrying forward

| finding | value | why it matters |
|---|---|---|
| local gen W\* | **16** (5,367 examples/s) | peak *and* settle-low; knee bracketed (W12 −19.8%); **no queue collapse** anywhere on the ladder — the specific hazard the smoke hunted |
| gen cost | **87.6 s/game** effective at W16 | 300 games ≈ 7.3 h local-only |
| h2h per-move cost | candidate **16.10 s**, opponent **14.05 s** | the champion's `parallel_workers: 8` buys **nothing** in a game-parallel eval farm — measured 12.7–14.1 s/move against PRODUCTION's 13.7552 s **sequential**, not its 2.1595 desktop figure |
| eval worker RSS | **537 MB** (local), 549 MB (laptop) | the measurement that sized the laptop at W12 rather than W16 |
| Air gen W\* | **4** (30.1 games/h) | *inverts* the W6 inferred from eval-shaped data; runbook's ~35 games/h was 16% optimistic |

## Incidents

1. **Session death ~23:55, before the first gen game.** Prep on the share survived intact; the box
   did not reboot. Cost: ~35 min of wall. **Fix applied the same night** — every cell script,
   watchdog, and the train chain were moved to the share so they survive the session that starts
   them. Nothing afterwards depended on this session staying alive.
2. **Eval fails-open at 09:52** — a `summary.json` at `n=399, n_paired=199`, indistinguishable from
   success except by `n`. Caught by the integrity check. **My first diagnosis was wrong**: I read a
   claim owned by `laptop:107288`, checked for live clients on *local only*, called it stranded,
   cleared a **live** claim and started a duplicate worker. The laptop was still playing that game
   and rewrote the summary correctly at `n=400`. I killed the duplicate before it could overwrite a
   completed record. **Lesson: a `.claim` names its owning host — check that host.** Full account in
   the read-out.
3. **My laptop health check could never report DOWN** — `pgrep -f 'gen_fair_distill.py --games 300'`
   sent over ssh matches the ssh command's own argv. Bracket-guarded and re-pointed. A direct audit
   confirmed no action had been taken on the false signal.
4. **Air unreachable 02:21–05:49.** Initially recorded as "slept mid-run despite `caffeinate`" and
   as a *second* such failure — **both wrong, and corrected**: the sweep had finished cleanly at
   01:41:58, `caffeinate -dimsu` did its job and released the box when the run it wrapped exited.
   The "caffeinate is insufficient" concern raised on that basis is **withdrawn**.
5. **ETA drift, three revisions** (07:1x → 08:50 → ~10:00, landed 09:56). The 07:1x read was the
   order-statistic trap firing exactly as documented; the 08:50 read rested on a single 60-min
   window that happened to be fast. Only from ~36% completion, with three windows agreeing, did the
   estimate hold. Recorded because "two windows agreed" was not sufficient evidence and looked like
   it was.

## Pre-registration trail (all committed BEFORE the work they govern)

| commit | what |
|---|---|
| `122e32e` | rodv3 turn-1 prereg — before the first gen game |
| `1ed1680` | gen launch record (W\*=16) |
| `d9cce65` | pre-gate amendment (audit F1): DEAD branch re-scoped |
| `e9b8a97` | correction of my own aside in `d9cce65` + roadmap G8 premise wording |
| `6732c5f` | Air held out of the corpus — pre-registered fleet decision |
| `f2e11ca` | **teacher-h2h prereg — before the first game of that cell** |
| `ceb49a9` | stale `PROD_KNOBS` banner finding |
| `01e928e` | h2h smoke + full-cell launch |
| `3be272c` | laptop swapped onto the h2h cell |
| `96647fc` | Air gen W-sweep result + correction |
| `3467f73` | **h2h RESULT** |

## Next step — needs a human decision, nothing is running

1. **Fire the pre-committed n→800 extension?** ~7 h two-box. It is scientifically pre-committed;
   the spend is not. Both boxes are **idle now**.
2. **Or accept the direction and skip to the consequence:** if PREMISE WEAK holds, gen at 11008
   becomes the only clean lever-6 test and a DEAD turn-1 gate is *expected rather than informative*
   — the outcome that saves funding ~29 h on a hunch.
3. **Or resume rodv3 gen** from 65/300 (~5.7 h remaining two-box) and train, accepting that its
   gate now reads against a weakened premise.

**Owed, and outside this agent's authority:** a `results.csv` row for the h2h cell (a real strength
measurement, both statistics), a CLAIM_REGISTRY entry/amendment, and the quiet-window fix for
`eval_fair_puct.py`'s inverted `PROD_KNOBS` banner.
