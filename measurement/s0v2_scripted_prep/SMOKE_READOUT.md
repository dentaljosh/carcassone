# S0v2 SIGNATURE SMOKE — READ-OUT

> # ⛔ PARKED 2026-08-28 after ROUND 3 — [§7](#7-round-3--hold--the-two-instrument-fixes-designmd-42--parked)
>
> **No arm is a valid ruler, on either fresh range, and nothing replicates.**
> The park diagnosis is **not about the agent**: over four disjoint 60-game deck
> ranges the champion-vs-champion CONTROL's own denial-per-game spans **5.1×**
> and its took-all rate **7.0×** — so at this budget every CTRL-relative gate
> measures the deck range, not the agent (§7.4). The pooled two-range denial
> uplift is **−0.17 ± 1.04** (FM) and **−0.57 ± 1.00** (FMH): with all four
> fires, S0v2 does **not** take materially more points from the champion than
> the champion takes from itself. The remaining gap to the owner is **invasion
> QUALITY — victim selection by expected realised value** — which needs search,
> not a rule (§7.5, named and NOT built). Round 3 also **withdraws round 2's own
> §6.3 finding** (§7.3). §1–§5 are round 1, §6 is round 2; both stand as written.

> **ROUND 2 (the MAJORITY amendment) RAN 2026-08-28 — jump to [§6](#6-round-2--the-majority-amendment-designmd-41).**
> The MAJORITY fire works mechanically and closes most of the took-all gap
> (17.9 % → **26.4 %**, owner 28.9 %). It does **not** produce a certifiable
> ruler, and round 2's most important result is a **method** one: the SAME agent
> reads G-DAMAGE **+2.25 pp** on one deck range and **+10.66 pp** on the next, so
> **G-DAMAGE is not resolvable at n=60** and no arm can be certified from a
> single range. §1–§5 below are ROUND 1 and stand as written.

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

---

# §6 ROUND 2 — the MAJORITY amendment ([DESIGN.md](DESIGN.md) §4.1)

**⛔ SMOKE. NOT A CELL. NOT A VERDICT.** Seeds **`900000020000..900000020029`**
— disjoint from the `900000000000`-area (S0), `900000009000`-area (calibration)
and `900000010000`-area (round 1) ranges. No band, no `results.csv` row, no
claim. Bars are DESIGN.md §4 **unchanged**; the amendment (§4.1) added the fourth
fire and its telemetry, and was committed before the first round-2 game
(`s0v2: AMEND the prereg — add the MAJORITY fire (no bar moved)`).

**Ran 2026-08-28**, local box, `nice -n 19`, W=8, same shared tenancy as round 1
(the other agent's 8-worker job ran throughout both rounds), three arms,
**180 games, 180/180 reconciled**. All three arms ran the SAME 30 decks, both
seatings — deck-paired and deck-matched.

**Why CTRL and the majority-off arm were re-run** (the coordinator left this
call open): both G-EXPRESS(b) and G-DAMAGE are **CTRL-relative**, and `CLAUDE.md`
CL-068 puts cross-range contrasts at 1.8–2.2× over-dispersion. Re-running CTRL
and S0V2-F on the new range cost ~13 minutes and made every gate a within-range,
deck-matched contrast. **That decision is what produced round 2's headline
finding** — see §6.2.

## §6.1 The results

| arm | plan | n | **census deliberate / game** | ×CTRL2 | sep σ | **margin** | W-D-L |
|---|---|---|---|---|---|---|---|
| **CTRL2** | none | 60 | **0.633 / 0.450 → pooled 0.542 ± 0.064** | — | — | −0.65 ± 3.03 | 30-1-29 |
| **S0V2-F2** | full, MAJORITY **off** | 60 | **0.933 ± 0.106** | 1.72× | +3.17 | **−8.88 ± 3.52** | 25-1-34 |
| **S0V2-FM** | full + **MAJORITY** | 60 | 0.883 ± 0.098 | 1.63× | +2.92 | −12.82 ± 3.21 | 21-1-38 |

| gate | bar (unchanged) | S0V2-F2 | S0V2-FM |
|---|---|---|---|
| **G-EXPRESS (a)** | ≥ 0.90 / game | **0.933 ✅** | **0.883 ❌** |
| **G-EXPRESS (b)** | ≥ 2 σ over CTRL | +3.17 σ ✅ | +2.92 σ ✅ |
| **G-DAMAGE** | ≥ +10 pp champ farmer-zero | **+10.66 pp ✅** (z 3.06) | **+12.37 pp ✅** (z 3.53) |
| **G-COMPETITIVE** | ≥ −25 (pref −12) | ✅ hard, ✅ preferred | ✅ hard, ❌ preferred (−12.82) |
| **S0v2-VALID** | all three | **YES — but see §6.2** | **NO** (G-EXPRESS a) |

### Deck-matched margin contrasts (all three arms, same 30 decks)

| contrast | n | mean | sem | z |
|---|---|---|---|---|
| S0V2-F2 − CTRL2 | 60 | −8.23 | 3.87 | −2.13 |
| S0V2-FM − CTRL2 | 60 | −12.17 | 3.96 | −3.07 |
| **S0V2-FM − S0V2-F2** (the amendment's own cost) | 60 | **−3.93** | 2.83 | −1.39 |

### The statistic the amendment was built to move

| | owner (E4) | CTRL2 | S0V2-F2 | **S0V2-FM** |
|---|---|---|---|---|
| **`invader_took_all`** | **28.9 %** (26/90) | 13.2 % (5/38) | 17.9 % (10/56) | **26.4 % (14/53)** |
| `shared_tie` | 66.7 % | 71.1 % | 62.5 % | 54.7 % |
| **`incumbent_held`** | **4.4 %** | 15.8 % | 19.6 % | **17.0 %** |
| **out-numbering at score** | **28.9 %** | 13.2 % | 17.9 % | **26.4 %** |
| out-numbering meeple counts | 2v1 ×10, 3v2 ×5, 4v3 ×7 … | 2v1 ×2, 3v2 ×1, 4v2 ×1 | 2v1 ×3, 3v2 ×2, 4v2 ×2, 4v3 ×2 | **2v1 ×5, 3v2 ×4, 4v2 ×3, 3v1 ×1, 4v3 ×1** |

**The gap round 1 named is essentially closed on the point estimate: 26.4 % vs
the owner's 28.9 %.** ⚠️ But the *contrast* is not resolved at this n — the
two-proportion test S0V2-FM vs S0V2-F2 is **z +1.08**, and vs CTRL2 **z +1.53**.
53 invasion events cannot separate 26 % from 18 %. What IS established is the
**mechanism**, from the agent's own ledger rather than from a proportion test:
**42 MAJORITY fires (0.70/game), 38 of them `from_tie`.**

### The MAJORITY / REINFORCE ledger (S0V2-FM, 60 games)

| | |
|---|---|
| MAJORITY fires | **42** (0.70/game) — of which **`from_tie` 38**, fresh 2-v-1 4 |
| MAJORITY candidates seen | 59 |
| REINFORCE-FOOTHOLD fires | **41** — `reinforce_vetoed_by_visits` 47 |
| REINFORCE-SETUP fires | 90 (of 219 setup fires) |
| **meeples spent on reinforcement** | **41** (0.68/game) |
| reinforce plans | **15 / 41 completed = 36.6 %** |
| invade plans | 43 / 161 = 26.7 % |
| **plan completion, all kinds** | **58 / 202 = 28.7 %** (S0V2-F2: 33/188 = **17.6 %**) |
| abandons | 49 — `stub_gone` 27, `merged_not_by_plan` 14, `victim_gone` 8 |
| merge fires | 57 (S0V2-F2: 61); merge candidates 79 (F2: 88) |
| `setup_vetoed_by_visits` | 1050 of 2418 candidates — the gate is still doing most of the work |

**Plan completion nearly doubled, 17.6 % → 28.7 %** — the number round 1 said
this build had to move, and the only one of the amendment's targets that moves
by more than noise.

### Secondary counters

| | owner (E4) | CTRL2 | S0V2-F2 | S0V2-FM |
|---|---|---|---|---|
| champion games farm-ZEROED | 18 % | 5.0 % (pooled) | 10.0 % | **11.7 %** |
| S0v2's own games farm-zeroed | 0 % | 5.0 % (pooled) | 3.3 % | **1.7 %** |
| points S0v2 denied the champion | 620 | 154 | 184 | **241** |
| invader gain (pts) | 1460 | 583 | 644 | 621 |
| champion big-claim contested rate | 39.1 % | 10.2 % (pooled) | 11.7 % | 10.1 % |
| deliberate invasions on FARMS | 41 % | 61 % | 68 % | 66 % |
| foothold → victim (tiles) | **2.75 → 8.29** | 3.98 → 11.60 | 3.80 → 10.07 | **3.62 → 9.90** |
| late farm captures | 15 | 2 | 2 | **5** |
| S0v2's OWN farmers scoring ZERO | **5.4 %** | 11.4 % | 28.0 % | **30.0 %** |

## §6.2 ⭐ THE FINDING THAT OUTRANKS THE BARS: G-DAMAGE IS NOT RESOLVABLE AT n=60

`S0V2-F` and `S0V2-F2` are **the same agent** — the same code, the same profile,
`majority_enabled=False`, pinned bit-for-bit by
`test_majority_off_is_the_previous_agent_exactly`. Only the deck range differs:

| | round 1 (`…10000`) | round 2 (`…20000`) |
|---|---|---|
| census deliberate / game | 0.900 ± 0.111 | 0.933 ± 0.106 |
| margin | −15.57 ± 3.28 | −8.88 ± 3.52 |
| champion farmer-zero rate | 17.30 % (n=185) | **24.38 %** (n=201) |
| CTRL farmer-zero rate | 15.05 % (n=412) | 13.72 % (n=401) |
| **G-DAMAGE** | **+2.25 pp — FAIL** (z 0.68) | **+10.66 pp — PASS** (z 3.06) |

**An 8.4 pp swing on a +10 pp bar, from the identical agent, between two
60-game deck ranges.** The nominal SEM of the difference between the two reads
is 4.79 pp (1.75 σ); under CL-068's measured 1.8–2.2× cross-range
over-dispersion it is ≈ 0.8–1.0 σ — entirely ordinary. So:

> **"S0V2-F2 is S0v2-VALID" is a statement about a deck range, not about an
> agent.** The same agent failed the same gate one range earlier. **No arm in
> either round can be certified as a ruler**, and the honest status of
> `S0V2-F2`'s green row in §6.1 is *passed on one range, failed on another*.

⚠️ **The fix is NOT more games on one range.** The within-range SEM (3.48 pp) is
already small enough to decide a +10 pp bar at 2 σ; what is not established is
**reproducibility across ranges**. Round 1 and round 2 together ARE that
replication for the majority-off agent, and it fails it. **A ruler-certification
protocol needs a two-range replication clause on G-DAMAGE** — a gate that passes
on one range and fails on another has not been measured. That clause does not
exist in DESIGN §4 and is not being retro-fitted here: it is the amendment the
NEXT prereg should carry.

## §6.3 The two gates pull against each other — a design fault in the instrument

S0V2-FM's expression *fell* (0.933 → 0.883) while its damage rose. That is not
noise about a knob; it is mechanical, and the ledger names it:

* **38 of 42 MAJORITY fires were `from_tie`** — they land on features that were
  **already contested**. The census counts a deliberate invasion only at a
  feature's **FIRST** contest, so a majority on an already-contested feature
  scores on **G-DAMAGE and not at all on G-EXPRESS**.
* **MAJORITY outranks MERGE**, so on plies where both are available the agent
  spends its one move on the majority. Merge fires fell 61 → 57 and merge
  candidates 88 → 79.

⇒ **The agent has one move per ply and the two registered gates want it spent
differently.** G-EXPRESS counts *first contests*; G-DAMAGE needs *majorities on
contests already made*. An instrument scored on both simultaneously is being
asked to do two things with one move.

## §6.4 RECOMMENDATION, and the next diagnosed mechanism

**No arm is certified.** `S0V2-F2` passes all three registered bars on range 2
and fails G-DAMAGE on range 1 as the same agent (§6.2); `S0V2-FM` misses
G-EXPRESS(a) by 0.017/game, inside its own SEM of 0.098.

What the amendment did establish, and it is worth keeping:

* **The MAJORITY fire works as designed.** 42 fires, 38 from ties, took-all
  17.9 % → 26.4 % against the owner's 28.9 %, points denied 184 → 241, plan
  completion 17.6 % → **28.7 %**. Direction and mechanism confirmed; magnitude
  not resolved at n=60 (z +1.08 vs its own sibling).
* **It costs ~4 pts/game** (deck-matched −3.93 ± 2.83, z −1.39) and pushes the
  arm just outside the preferred competitiveness band.
* **It is cheap.** S0V2-FM was the *fastest* arm at 43.6 worker-s/game — a
  MAJORITY or MERGE fire returns without running the base search.

### Next diagnosed mechanism — named, NOT built

**`incumbent_held` is 17.0 % for S0V2-FM against the owner's 4.4 %.** After
MAJORITY, S0v2 wins its invasions about as often as the owner does; what it
still does four times too often is **lose them** — the champion merges *its* own
second part in and out-numbers S0v2 back. S0v2 has **no fire that defends a
contested feature it already holds**: the exact mirror of MAJORITY, call it
**HOLD** (reinforce a contested feature where the opponent is tied with me or
about to pass me). It is the same machinery — a second claimed part plus a merge
— pointed the other way, and it targets the one outcome column where the gap to
the owner is still 4×.

Two instrument-design items also fall out of §6.2 and §6.3, and they are not
fires:

1. **A two-range replication clause on G-DAMAGE** before any ruler is certified.
2. **Separate the gates** — either score MAJORITY and MERGE arms independently,
   or replace "count + damage" with a single **denial-per-game** statistic that
   does not make one move serve two counters.

## §6.5 What round 2 cannot say

Everything in §4 still applies, plus: **nothing about the MAJORITY fire's
magnitude.** Its own contrast against the majority-off sibling is z +1.08 on
took-all and z −1.39 on margin. The fire ledger (42 fires, 38 from ties) is
direct evidence the mechanism fires; the outcome shift is direction-consistent
and under-powered. Realized cost across round 2 was **43.6 – 51.3 worker-s/game**
(141.9 moves/game) on a **shared** box — an upper bound, not a cell price.

## §6.6 Reproduce

```bash
measurement/s0v2_scripted_prep/run_smoke.sh play S0V2_FM 400   # resumable
measurement/s0v2_scripted_prep/run_smoke.sh grade S0V2_FM
.venv/bin/python measurement/s0v2_scripted_prep/s0v2_bars.py \
  --root /mnt/c/carc-shared/s0v2_smoke_20260828 --round 2
```

---

# §7 ROUND 3 — HOLD + the two instrument fixes ([DESIGN.md](DESIGN.md) §4.2) — **PARKED**

**⛔ SMOKE. NOT A CELL. NOT A VERDICT.** Two disjoint fresh ranges,
**`900000030000..029` (A)** and **`900000040000..029` (B)**, disjoint from every
prior range. No band, no `results.csv` row, no claim. Bars: §4 as first
registered, amended by §4.2 — committed before the first round-3 game
(`s0v2: AMEND the prereg again (§4.2)`).

**Ran 2026-08-28**, local box, `nice -n 19`, W=8, same shared tenancy as rounds
1–2, six arms, **360 games, 360/360 reconciled**, ~36 min wall.
Realized **37.1 – 53.5 worker-s/game** (141.9 moves/game) — **an upper bound**,
shared box, not a cell price.

# THE ANSWER: NO ARM IS A VALID RULER, ON EITHER RANGE, AND NOTHING REPLICATES.

**This funding line is PARKED here.** The diagnosis is in §7.4, and its core is
not about the agent: **the champion-vs-champion CONTROL is itself unstable across
deck ranges by more than the effect any gate is trying to measure.**

## §7.1 The results

| range | arm | n | delib/game | sep σ | **G-EXPRESS** | **G-DENY uplift** | **G-DENY** | margin | **VALID** | [G-DAMAGE] |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | CTRL_A | 60 | 0.533 ± 0.060 | — | — | — (base 2.650/g) | — | −0.03 ± 2.46 | — | — |
| **A** | FM_A | 60 | 0.767 ± 0.087 | +2.21 | **FAIL** | +0.77 ± 1.65 (z 0.46) | **FAIL** | −12.18 ± 2.50 | **NO** | +0.94 pp |
| **A** | FMH_A | 60 | 0.733 ± 0.089 | +1.87 | **FAIL** | +0.40 ± 1.52 (z 0.26) | **FAIL** | −11.92 ± 2.57 | **NO** | +2.74 pp |
| **B** | CTRL_B | 60 | 0.342 ± 0.050 | — | — | — (base 3.583/g) | — | +0.77 ± 2.56 | — | — |
| **B** | FM_B | 60 | 0.717 ± 0.098 | +3.41 | **FAIL** | **−1.10** ± 1.26 (z −0.87) | **FAIL** | −14.55 ± 3.31 | **NO** | +4.97 pp |
| **B** | FMH_B | 60 | 0.700 ± 0.096 | +3.32 | **FAIL** | **−1.55** ± 1.29 (z −1.20) | **FAIL** | −14.97 ± 3.32 | **NO** | +3.51 pp |

G-COMPETITIVE's hard floor passes everywhere; FMH_A is the only arm inside the
preferred band (−11.92).

### The TWO-RANGE REPLICATION CLAUSE, as registered

| arm | A: delib | B: delib | A: deny+ | B: deny+ | **pooled deny+** | sem | z | **REPLICATED** |
|---|---|---|---|---|---|---|---|---|
| FM | 0.767 | 0.717 | +0.77 | −1.10 | **−0.17** | 1.04 | −0.16 | **NO** |
| FMH | 0.733 | 0.700 | +0.40 | −1.55 | **−0.57** | 1.00 | −0.58 | **NO** |

**The pooled two-range denial uplift is consistent with ZERO**, and the
pre-registered +1.5 bar sits 1.6 σ (FM) and 2.1 σ (FMH) above the point
estimate. This is not "under-powered and hopeful" — it is a **powered-enough
negative on the primary gate**: with all four fires, **S0v2 does not take
materially more points from the champion than the champion takes from itself.**

## §7.2 What HOLD actually did

HOLD fired **21 times on range A (0.35/game) and 12 on range B (0.20/game)**,
defending 21 and 12 distinct contested holdings; `incumbent_held_conversions`
equals `hold_fires` by construction and both matched.

| | FM_A → **FMH_A** | FM_B → **FMH_B** |
|---|---|---|
| `incumbent_held` | 28.3 % → **25.0 %** | 25.6 % → **23.8 %** |
| **plan completion** | 23.4 % → **29.4 %** | 27.4 % → **29.4 %** |
| reinforce plans completed | 8/48 | 15/47 · 21/56 → 24/56 |
| deck-matched margin (FMH − FM) | **+0.27 ± 1.12** (z +0.24) | **−0.42 ± 0.57** (z −0.73) |
| G-DENY uplift | +0.77 → **+0.40** | −1.10 → **−1.55** |

**HOLD is free and it works in the direction designed** — `incumbent_held` falls
on both ranges and plan completion rises on both, the only two counters that
replicate in this whole round. It is also **too small to matter**: 0.2–0.35
fires/game, a 2–3 pp move on `incumbent_held` against the 4× gap to the owner
(4.4 %), and it *lowers* G-DENY on both ranges — correctly and by design, since
a HOLD spends a tile on a merge that denies the opponent nothing.

## §7.3 ⛔ A CORRECTION TO ROUND 2'S OWN FINDING (§6.3)

Round 2 concluded that MAJORITY outranking MERGE was "the mechanical reason"
S0V2-FM's expression fell, and round 3's first instrument fix re-ranked them.
**Round 3 instrumented that claim and it does not hold.** `merge_over_majority`
— plies where a MERGE and a MAJORITY were both available and the new order
chose MERGE — is **2 over 60 games on range A and 1 on range B**.

A conflict that arises 1–2 times per 60 games cannot explain a 0.05/game
expression difference. **§6.3's mechanical story is withdrawn: round 2's
expression dip was noise.** The priority fix is retained because the ordering
argument is still correct on its own terms, but it buys nothing measurable, and
the gate conflict it was meant to resolve is not a real constraint on this
agent's behaviour.

## §7.4 ⭐ THE PARK DIAGNOSIS: the CONTROL is the thing that is not measurable

Four disjoint 60-game deck ranges of **champion vs champion — the same agent,
the same instrument, no plan module at all**:

| control | range | delib/game | **denied/game** | **took_all** | champ farmer-zero |
|---|---|---|---|---|---|
| CTRL | `…10000` | 0.550 ± 0.060 | **0.700** | **5.3 %** | 15.05 % |
| CTRL2 | `…20000` | 0.542 ± 0.064 | **2.567** | **13.2 %** | 13.72 % |
| CTRL_A | `…30000` | 0.533 ± 0.060 | **2.650** | **12.9 %** | 15.81 % |
| CTRL_B | `…40000` | **0.342** ± 0.050 | **3.583** | **36.8 %** | 16.98 % |

**Denial per game spans 5.1×. Took-all spans 7.0×.** These are the baselines
every gate in this prereg is defined as an uplift over. On range B the *control*
denies 3.58 pts/game — **more than either exploiter arm on that range** — which
is why both arms read a *negative* G-DENY uplift there.

⇒ **At 60 games per cell, a CTRL-relative gate measures the deck range, not the
agent.** Round 2 §6.2 caught this on G-DAMAGE; round 3 shows it is not a
property of that one statistic — it is a property of the budget. The two-range
replication clause did its job precisely: it refused to certify what a single
range would have called a pass.

**The honest budget, for whoever resumes.** The deck-matched G-DENY uplift SEM
realized 1.0–1.65 at n=60. Resolving a +1.5 effect at 2 σ needs SEM ≤ 0.75, i.e.
**~180 games per cell**; CTRL + one arm on two ranges is **~720 games** (≈ 1 h at
W14, ~9 core-h). That is cheap. ⚠️ **But the pooled point estimate is ≈ 0, so the
likely purchase is a confirmed NULL, not a pass** — and that should be priced in
before anyone funds it.

## §7.5 Where the remaining gap actually is — the next mechanism, NAMED not built

Across three rounds the instrument closed the counters it was pointed at and
never closed the one that matters:

| | owner (E4) | best S0v2 (any round) |
|---|---|---|
| deliberate invasions / game | 1.80 | 0.93 (round 2 F2) |
| `invader_took_all` | 28.9 % | 26.4 % (round 2 FM) |
| `incumbent_held` | 4.4 % | 23.8 % (round 3 FMH_B) |
| **points denied / game** | **12.40** | **≈ base + 0 (round 3, two ranges)** |
| **invader gain / game** | **29.2** | **≈ 8–10** |

Expression reached half the owner's rate; took-all reached 91 % of his. **Gain
and denial did not move at all** — S0v2 takes ~10 points a game off its
invasions where the owner takes ~29.

That is not a frequency gap and not a majority gap. It is a **victim-SELECTION**
gap: the owner invades features that turn out to be *worth a lot when they
score*, and S0v2 invades whatever happens to be merge-reachable and clears a
static `potential_pts` floor. Its mean victim is 10–11 tiles against the owner's
8.29 — **bigger targets, less money**.

⇒ **The next diagnosed mechanism is invasion QUALITY: choosing the victim by its
EXPECTED REALISED value at scoring time**, not by its current size. That is an
expected-value question over the remaining deck and the opponent's replies — it
needs *search*, not a rule. **Which is itself the conclusion of this funding
line: the part of the owner's exploit a script can carry has been carried, and
the part that is left is exactly the part a script cannot.** It is named here
and NOT built.

Two smaller items also stay named and unbuilt: a **victim-value model** would
need the exact-solver or a CRN continuation pricer to label "what this feature
was ultimately worth", and any future ruler-certification should adopt §4.2's
two-range clause *and* the ~180-games-per-cell budget from §7.4 from the start.

## §7.6 What round 3 cannot say

1. **Nothing about any leaf term, search knob or dose** — both sides ran the
   same champion leaf `a36d2e15a3b3d71d` and the same search config throughout.
2. **Nothing about HOLD's magnitude.** Its own deck-matched contrasts are
   z +0.24 and z −0.73. What replicates is the *direction* on `incumbent_held`
   and on plan completion, and the fire ledger showing it fires as specified.
3. **Nothing about timing** — shared box; the s/game figures are upper bounds.
4. **Nothing about the owner.** S0v2 is a proxy for a proxy; the E4 stream stays
   the only judge-free out-of-family arbiter.
5. **G-DAMAGE, reported under its own two-range clause, agrees with G-DENY that
   nothing is certified**: +0.94 / +2.74 pp on range A and +4.97 / +3.51 pp on
   range B, all below the +10 pp bar it used to gate on — after passing at
   +10.66 / +12.37 pp on range `…20000`. The demoted gate replicates no better
   than the one that replaced it, which is the §4.2 disclosure's own prediction.

## §7.7 Reproduce

```bash
measurement/s0v2_scripted_prep/run_smoke.sh play FMH_A 400   # resumable
measurement/s0v2_scripted_prep/run_smoke.sh grade FMH_A
# the amended gate table + the two-range replication clause
.venv/bin/python measurement/s0v2_scripted_prep/s0v2_bars.py \
  --root /mnt/c/carc-shared/s0v2_smoke_20260828 --round 34
```
