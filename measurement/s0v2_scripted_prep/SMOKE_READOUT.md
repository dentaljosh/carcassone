# S0v2 SIGNATURE SMOKE — READ-OUT

**⛔ SMOKE. NOT A CELL. NOT A VERDICT.** No band claimed (throwaway seed range
`900000010000..900000010029`), no `results.csv` row, no gate ladder, no claim,
nothing adopted. Bars are [DESIGN.md](DESIGN.md) §4, committed before the first
S0v2 smoke game existed (`s0v2: PRE-REGISTER the scripted exploiter`).

**Ran 2026-08-28**, local box, `nice -n 19`, W=8 (another agent's 8-worker job
shared the box throughout), three arms, **180 games, 180/180 reconciled exactly**
by `stage_a_census.py`, 0 failures. Instrument: the r3 screening instrument
verbatim (k4×688 = **2752** both sides, rust both sides, `fixed_v1`+R9, exact-K 2
marginalized, c_puct 1.5 / τ_p 5 / float / visits, tie-arbiter off), deck-paired
AND deck-matched across all three arms.
Archives + rows: `/mnt/c/carc-shared/s0v2_smoke_20260828/`.

---

## THE ANSWER TO THE DELIVERABLE QUESTION

> *Is S0v2 a valid ruler?*

# NO — neither arm is S0v2-VALID. Both fail G-DAMAGE, and the reason is a named, measured mechanism, not noise.

**S0V2-F clears G-EXPRESS and G-COMPETITIVE and fails G-DAMAGE at +2.25 pp
against a +10 pp bar.** The autopsy in §2 finding (1) says why, in one sentence:
**S0v2's invasions land TIES, and the owner's take MAJORITIES.** Under the
vendored full-points-on-tie rule a tie costs the incumbent nothing, so an
instrument that only ever ties can raise the *invasion count* to owner-adjacent
levels and still deny the champion almost nothing.

---

## §1 THE RESULTS

Reference points for the columns below: the **owner** invades deliberately
**1.80×/game**; the **champion against the owner**, **0.14×/game**; the champion
**against itself on this seed range**, **0.550 ± 0.060/game** (CTRL, pooled over
both seats, 120 observations — consistent with S0's own CTRL, 0.500 ± 0.076 at
n=40 on a different range).

| arm | plan | n | **census deliberate invasions / game** | ×CTRL | sep. σ | **margin (S0v2 − champ) pts/game** | W-D-L |
|---|---|---|---|---|---|---|---|
| **CTRL** | none (champ vs champ) | 60 | **0.633 / 0.467 → pooled 0.550 ± 0.060** | — | — | −4.00 ± 2.63 | 26-1-33 |
| **S0V2-M** | MERGE only | 60 | **0.717 ± 0.089** | 1.30× | +1.55 | **−0.58 ± 2.69** | 31-2-27 |
| **S0V2-F** | SETUP→FOOTHOLD→MERGE | 60 | **0.900 ± 0.111** | 1.64× | **+2.78** | −15.57 ± 3.28 | 18-0-42 |

### Against the pre-registered bars

| gate | bar (DESIGN §4) | S0V2-M | S0V2-F |
|---|---|---|---|
| **G-EXPRESS (a)** | ≥ 0.90 / game | 0.717 ❌ | **0.900 ✅ — exactly ON the bar** |
| **G-EXPRESS (b)** | excess over CTRL at ≥ 2 pooled SEM | +1.55σ ❌ | **+2.78σ ✅** |
| **G-DAMAGE** | champion farmer-zero rate − CTRL ≥ +10 pp | **+2.02 pp ❌** | **+2.25 pp ❌** |
| **G-COMPETITIVE** | ≥ −25 (preferred ≥ −12) | ✅ hard, ✅ preferred | ✅ hard (2.9 SEM clear), ❌ preferred |
| **S0v2-VALID** | all three | **NO** | **NO** |

⚠️ **Read G-EXPRESS(a) for S0V2-F precisely: 54 deliberate invasions in 60 games
is 0.900, which meets a "≥ 0.90" bar exactly and with zero margin.** At
SEM 0.111 the true rate is somewhere in ≈ [0.68, 1.12]. It is a pass on the
letter of a pre-registered bar and must not be reported as a comfortable one.

### Deck-matched margin contrasts (all three arms ran the same 30 decks)

| contrast | n | mean | sem | z |
|---|---|---|---|---|
| S0V2-M − CTRL | 60 | **+3.42** | 2.03 | +1.68 |
| S0V2-F − CTRL | 60 | **−11.57** | 3.49 | **−3.32** |

The scripted MERGE fire is **free** — it does not cost points at this n and
directionally gains. The SETUP+FOOTHOLD machinery costs **≈ 12 pts/game at
z −3.3**, and buys **+0.18 census invasions/game**.

### Secondary counters (reported, non-gating)

| | owner (E4) | CTRL | S0V2-M | S0V2-F |
|---|---|---|---|---|
| champion games farm-ZEROED | 18 % | 5.8 % (pooled) | 10.0 % | 10.0 % |
| S0v2's own games farm-zeroed | 0 % | 5.8 % (pooled) | 1.7 % | 10.0 % |
| champion big-claim contested rate | 39.1 % | 9.0 % (pooled) | 6.8 % | 7.5 % |
| S0v2's own big claims contested | 4.3 % | 9.0 % (pooled) | 7.4 % | 7.6 % |
| points S0v2 denied the champion | 620 | 42 / 58 | **162** | 117 |
| invader gain (pts) | 1460 | 433 / 383 | 525 | **606** |
| deliberate invasions on FARMS | 41 % | 66 % | 70 % | **74 %** |
| foothold → victim (tiles) | **2.75 → 8.29** | 3.48 → 10.19 | 3.04 → 10.21 | **3.34 → 9.85** |
| champion farmer deployments scoring ZERO | 46.2 % | 15.05 % (pooled) | 17.07 % | 17.30 % |
| S0v2's OWN farmers scoring ZERO | 5.4 % | 15.05 % (pooled) | 14.02 % | **29.88 %** |

---

## §2 THE FOUR FINDINGS THAT MATTER

### (1) ⭐ THE MECHANISM S0v2 IS MISSING IS **MAJORITY**, NOT COUNT. The owner's invasions WIN; S0v2's TIE.

The census records an `outcome` for every deliberate invasion. Side by side:

| | owner (E4, n=90) | CTRL (n=38) | S0V2-M (n=43) | S0V2-F (n=54) |
|---|---|---|---|---|
| **`invader_took_all`** | **26 (28.9 %)** | 2 (5.3 %) | 6 (14.0 %) | 5 (9.3 %) |
| `shared_tie` | 60 (66.7 %) | 23 (60.5 %) | 23 (53.5 %) | 34 (63.0 %) |
| **`incumbent_held`** | **4 (4.4 %)** | 13 (34.2 %) | 14 (32.6 %) | **15 (27.8 %)** |

And the meeple counts on the feature when it finally scored, `(invader,
incumbent)`:

* **owner:** `(1,1)×54` — but also **`(2,1)×10`, `(3,2)×5`, `(4,2)×1`,
  `(4,3)×7`, `(5,4)×2`, `(6,5)×1` — 26 invasions where he OUT-NUMBERS the
  incumbent.**
* **S0V2-F:** `(1,1)×26`, and only **`(2,1)×2`, `(3,2)×1`, `(4,3)×2`** — 5.

**This is the whole G-DAMAGE failure and it is a structural property of the
build, not a dosing problem.** The vendored engine pays *all tied players in
full* (a deliberate rules patch — `CLAUDE.md` "Engine notes"), so a 1-v-1
invasion denies the incumbent **exactly zero**. The census's
`farmer-deployment-scores-ZERO` counter — G-DAMAGE's statistic — only moves when
the incumbent **loses the majority**. S0v2 places ONE meeple and never
reinforces, so by construction its best case is a tie, and 15 of its 54
invasions are worse than that (`incumbent_held`: the champion out-numbered it
afterwards).

The owner's own numbers say the same thing from the other side: he loses
`incumbent_held` only 4.4 % of the time against S0v2's 27.8 %, and takes the
feature outright 28.9 % against 9.3 %.

**⇒ The named next build is a fourth fire: MAJORITY — add a second (or third)
meeple to a feature I am tied on or behind on.** That is a different plan step
with a different cost profile (it spends a scarce meeple on a feature already
committed, which is exactly the trade H3′ is about), and it is the one that
converts invasion COUNT into invasion DAMAGE. Nothing in this smoke tests it.

### (2) The scripted MERGE fire is FREE, and it beats every config-S0 arm on cost at equal expression.

`S0V2-M` reads **0.717 ± 0.089** invasions/game at **−0.58 ± 2.69** pts/game
(deck-matched vs CTRL: **+3.42, z +1.68**). The best config-S0 arm, `S0-B3`
(α 0.27 uncapped stub 3), read **0.729 ± 0.110 at −5.54 ± 2.29**. Same
expression, and S0v2-M does not pay for it.

That is the design claim of this build, confirmed: **a script carries the plan
without a leaf term, and a leaf term that has to make step one attractive at
depth 0 necessarily distorts every other decision it touches.** It is also why
`S0V2-M` is the honest *cheapest available proxy* today even though it is not
valid — see §3.

### (3) SETUP+FOOTHOLD buys +0.18 invasions/game for ≈ 12 pts/game, and 83 % of the plans it starts never complete.

`S0V2-F`'s ledger over 60 games: **192 plans started, 33 completed (17.2 %),
67 abandoned, 92 still open at the end.** Abandon reasons: `stub_gone` 39
(the foothold meeple came back — the stub's own feature closed and scored),
`merged_not_by_plan` 17, `victim_gone` 11.

167 SETUP fires and 192 FOOTHOLD fires per 60 games — ~6 tile/meeple overrides
per game — produced **+0.18 census invasions/game over the merge-only arm** and
cost **11.6 pts/game (z −3.3)**. The gate was doing real work: 747 SETUP
candidates and 149 FOOTHOLD candidates were **vetoed by the visit gate**
(the base agent's search gave them < 10 % of the top action's visits), i.e. the
plan wanted to play four to five times as many overrides as it was allowed to.

The cost also shows up directly in S0v2-F's own farm ledger: **its own farmer
deployments score ZERO 29.88 % of the time**, against 14.02 % for the merge-only
arm, 15.05 % in champion self-play and **5.4 % for the owner**. It is spending
farmers on stubs that lose — the exact opposite of the owner's discipline.

**⇒ "More setup" is not the lever.** The plan module reliably *starts* plans and
the merge step reliably *completes the ones that are completable*; what it cannot
do is make a specific multi-ply merge arrive. Only ~8 % of the agent's own tile
plies ever have a merge cell available at all.

### (4) The censusible ceiling is opportunity, and the plain champion already harvests most of it.

The champion's self-play deliberate rate on this range is **0.550/game**, and an
agent that mechanically takes EVERY available merge (`S0V2-M`) gets to
**0.717** — a 30 % lift. Everything above that (S0V2-F's 0.900) had to be
*manufactured*, at ~12 pts/game. The owner reaches **1.80** while *gaining*
13.24 pts/game.

`scan_plies` (plies where any merge cell existed) was 210 over 60 games for
S0V2-M — ~3.5 per game out of ~35 own tile plies — and yielded 71 merge
candidates and 47 fires. **The bottleneck is that merge opportunities are rare
and tile-conditional, and the champion is not declining many of them.**

---

## §3 RECOMMENDATION

**There is no recommended S0v2 config, because neither is valid.** Naming a
"best of two" would be the promotion-by-sympathy the read rules forbid.

If the owner wants the strongest available proxy *today*, with its label
attached:

* **S0V2-M** (`--plan merge`) — **the cheapest instrument this program has**:
  0.717 invasions/game at **no measurable strength cost** (deck-matched +3.42,
  z +1.68), 162 points denied to the champion (vs 42/58 in self-play), 70 % of
  its invasions on farms. **It is a WEAK proxy, not an S0** — 1.30× the base
  rate, 40 % of the owner's — and any cell run against it must carry that
  sentence. Its advantage over `S0-B3` is that it is not simultaneously a
  distorted player.
* **S0V2-F** if raw invasion COUNT is what a cell needs: 0.900/game, but
  −15.57 pts/game and outside the preferred competitiveness band, and its extra
  invasions are ties that damage nothing.

**The funded-work-shaped conclusion is §2 finding (1):** the gap between S0v2
and the owner is not *how often* he invades — S0V2-F is at half his rate — it is
that **he takes the majority and S0v2 ties.** A MAJORITY fire is a small,
well-specified addition to `s0v2_agent.py` (reinforce a contested feature where
`m_me <= m_opp`), it targets the exact statistic G-DAMAGE measures, and it is the
only lever in sight that could move that gate. It was not in this funding line
and it is not built.

---

## §4 WHAT THIS SMOKE CANNOT SAY

1. **Nothing about any leaf term, search knob or dose.** Both sides ran the SAME
   champion leaf `a36d2e15a3b3d71d` and the same search config; S0v2 overrides
   only the python-side move choice. There is not even a knob to mis-promote
   (DESIGN §0).
2. **Nothing at better than ±3 pts/game on any margin.** The invasion COUNTS are
   the powered statistic; the margins are context — except the deck-matched
   arm-minus-CTRL contrasts, which are the tightest numbers here.
3. **Nothing about the owner.** S0v2 is a proxy for a proxy; the E4 stream
   remains the only judge-free out-of-family arbiter.
4. **Nothing about timing.** The box was SHARED with another agent's 8-worker job
   for the entire run, so the realized **46.9 – 55.6 worker-s/game** (141.9
   moves/game) is an **UPPER BOUND** and the DESIGN §7.2 / S0 §7.2 cell-cost
   table must NOT be re-priced from it. What it does license: **an S0v2 cell
   costs no more than a plain champion cell** — S0V2-F actually read *faster*
   than CTRL, because a MERGE fire returns without running the base search.
   An exclusive-tenancy timing run is the only way to get a real figure
   (auto-memory `feedback_no_agent_compute_beside_eval`).
5. **The agent's own fire counts are not the census's.** S0V2-M fired 47 merges
   and the census counted 43 deliberate invasions; S0V2-F fired 60 and the census
   counted 54 (90 % and 90 %). The gap is the causal-vs-global-union-find
   difference documented in DESIGN §1.2 and is expected. **Every number in §1's
   bar table is the census's.**

### Two descriptive observations worth recording

* **Seat asymmetry in champion self-play.** CTRL's two seats — the same agent —
  read **0.633** and **0.467** deliberate invasions/game (n=60 each). S0's
  DESIGN §8.6 asked for this split before any cell design was frozen; it is
  material (a ~35 % relative spread) and any future per-seat cut should carry it.
* **S0v2 does NOT raise the champion's big-claim contested rate.** CTRL 9.0 %
  pooled, S0V2-M 6.8 %, S0V2-F 7.5 % — both *below* self-play, against the
  owner's 39.1 %. In champion self-play both seats invade; a one-sided invader
  contests less in total than two mutual ones. The owner's 39.1 % is a different
  regime again and neither instrument approaches it.

---

## §5 REPRODUCE

```bash
# one arm (resumable; --time-budget 0 = run to completion)
measurement/s0v2_scripted_prep/run_smoke.sh play S0V2_F 400
# census + signature + telemetry read-out for one arm
measurement/s0v2_scripted_prep/run_smoke.sh grade S0V2_F
# the pre-registered gate table across all three arms
.venv/bin/python measurement/s0v2_scripted_prep/s0v2_bars.py \
  --root /mnt/c/carc-shared/s0v2_smoke_20260828
# the tests
PYTHONPATH=src:engine .venv/bin/python -m pytest tests/test_s0v2_agent.py -q
```

Cost realized: 180 games ≈ **22 min wall at W=8** on a shared box
(≈ 50 worker-s/game — an upper bound; see §4.4).
