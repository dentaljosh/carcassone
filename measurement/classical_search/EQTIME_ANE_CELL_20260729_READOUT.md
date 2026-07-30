# CL-067 EQTIME/ANE CELL — read-out

**STATUS: COMPLETE 2026-07-29. PRE-REGISTERED BRANCH C (WASH) FIRED.**
400/400 games. elo **+19.13 ± 17.40** (z +1.10), deck-paired margin **−0.2675 pts/deck**
(z −0.29). Cost guard PASSES at **0.9522**. The two statistics **disagree in sign** and
neither clears 2σ, so this cell does NOT reopen the distilled line — but it also does not
kill it, and it moves the point estimate ~+36 elo off the desktop gate. **Not promoted;
`governance/PRODUCTION.yaml` untouched.**

The pre-registration (§1–§3) was written and committed (`f6a6ff9`) **before any result
existed** and has not been edited.

---

## 1. The question

The equal-wall-clock gate
([NETPRIOR_EQTIME_GATE_20260728.md](NETPRIOR_EQTIME_GATE_20260728.md)) fired branch C
(WASH) on the desktop CUDA batch-1 forward and fixed a reopen condition in §6:

> REOPEN the distilled-net line for deploy when the target device's measured
> `r = forward_ms / search_ms_per_sim` is <= ~1.5.

This cell is the single direct test §6 caveat 1 called for: the netprior agent on the M5
at its own **measured** equal-time budget, with the policy forward on the **Apple Neural
Engine**, vs the deploy champion.

## 2. Configuration (fixed before launch)

| | |
|---|---|
| candidate | fair-netprior, distilled `iter_03` (sha256 `6e2679908d79a76c`), NET policy priors + FROZEN curve125 leaf (value severed), **forward on the ANE** |
| CoreML artifact | `cl067_iter03_policy_fp16.mlpackage`, sha256(tree) `5883aa7f44e59c09`, policy-only, fp16, `CPU_AND_NE`, fixed batch-1 |
| candidate budget | **k4×438** (1752 total sims) |
| opponent | DEPLOY champion, `FairHeuristicPriorAgent`, k4×688 (2752 total) |
| both sides | exact-K 2 marginalized endgame, curve125 leaf `a36d2e15a3b3d71d`, c_puct 1.5, tau_p 5.0 |
| n | 400 deck-paired (200 decks × 2 seats) |
| band | **92e9** (verified unburned vs ledger + 612 share manifests; claimed before launch) |
| box / W | Apple M5 Air (darwin-arm64, 10-core), **W6** |
| code rev | `f6a6ff9` (worktree `agent-ae16172e9e13c3dfa`; see `CODE_PROVENANCE.txt` in the out-dir — the manifest says `unknown` because the tree was rsynced without `.git`) |

**Why k4×438, and why not the r-model.** Measured at W6 on the day: champion search
**1.0036 ms/sim** (the gate's 0.5741 projection was single-stream and 1.75× optimistic),
ANE forward **0.427 ms** single-stream. Naive r = 0.436 would license k4×479, but that
divides an *uncontended* forward by a *contended* search while six workers serialise on
the one shared ANE. The budget was therefore set from the **direct paired cost ratio**,
which contains every contention effect: k4×395 → 0.9014, **k4×438 → 0.9893**.

**Fidelity precondition (PASSED before launch).** `verify_coreml_evaluator.py`, 60 real
champion-reached positions: policy max-abs **1.113e-03**, legal-argmax agreement
**60/60**, top-5 overlap **1.0000**, ANE batch-1 **0.427 ms** vs torch-CPU 2.537 ms. The
ANE agent is the same player, so this cell measures a **cost intervention**, not a
different agent.

## 3. Pre-registered branches (inherited verbatim from the gate, so the two are comparable)

| branch | condition | meaning |
|---|---|---|
| **A** | both statistics ≥ +2σ | the forward WAS the binding constraint; reopen the line, unpark G3 as "get the forward onto a cheap accelerator" |
| **B** | positive but < 2σ | directionally right, underpowered; a bigger n is justified |
| **C** | both statistics inside 2σ | WASH — the ANE r ≈ 0.44 is not enough either |
| **D** | negative past 2σ | §7 kill: the equal-sims edge survives no realistic cost model; the distilled policy becomes a Phase-5 analyzer asset |

⚠️ The cost guard is part of the verdict. If the measured in-flight ratio falls outside
**[0.90, 1.10]** the cell is NOT equal-time and the elo must not be read as an
equal-clock number.

---

## 4. RESULT — every number below read off disk

```
records            400/400
winrate            208W-6D-186L  = 0.5275   z +1.100
elo                +19.128 +/- 17.398        z +1.099
deck-paired margin -0.2675 pts/deck   paired_z -0.2929   (200 decks)
cost ratio         candidate 3185.8 vs opponent 3345.9 prefix ms/move = 0.9522
                   -> [0.90,1.10]? PASS
opponent search    1.2158 ms/sim      candidate 1.8184 ms/sim
per-sim multiple   1.496x  (desktop CUDA batch-1 was 4.2-5.5x)
measured r         0.3512  (0.427 ms forward / 1.2158 ms per sim)
integrity          200 distinct decks, 0 deck_hash mismatches, 0 timeouts both sides,
                   400/400 latches both sides, latch_k in {1,2} both sides,
                   both sides leaf a36d2e15a3b3d71d, solver 18.08 s/game
BRANCH FIRED       C  (WASH)
```

### 4.1 Which branch fired, and the drafting weakness I own

**C fires.** Its condition — *"both statistics inside 2σ"* — is unambiguously satisfied:
winrate elo z **+1.099**, deck-paired z **−0.293**, both well inside 2σ. Its stated
meaning: *"WASH — the ANE r ≈ 0.44 is not enough either"*.

**B does not fire.** Its condition is *"positive but < 2σ"*. The two statistics
**disagree in sign** — the winrate is positive, the deck-paired margin is fractionally
negative — so the antecedent "positive" is not satisfied for the pair.

I note plainly that my branch table did **not** anticipate a sign disagreement, and that
B and C would have overlapped for a both-positive-but-weak result. That is a drafting
weakness in my own pre-registration. It does not change the outcome (C's condition is met
on its own terms and B's is not), but the next such table must make the branches mutually
exclusive and name which statistic breaks a tie.

**Why the two statistics can disagree.** They measure different things: the winrate counts
games won, the paired margin averages *points per deck*. A candidate can take slightly
more games while conceding slightly more points in the games it loses. Both are inside
noise here, so the honest one-line summary is **"indistinguishable from zero on 400 paired
games"** — not "positive", not "negative".

### 4.2 The cost guard — a correction worth recording

The guard convention is **candidate/opponent**, matching the gate's arm A
(`3786.75/3859.62 = 0.9811`). Verified against the emitter
(`eval_fair_puct.py:1645/1655` — `champ_ms` sums `champ_prefix_secs` = the CANDIDATE,
`rung_ms` sums `opp_prefix_secs` = the OPPONENT) and recomputed independently from all
400 records (identical, 0.9522).

**Ratio = 0.9522, NOT its inverse 1.0502.** The direction matters: the candidate spent
**4.8% LESS** wall clock than the champion, so this cell is mildly
**candidate-DISfavoured** — conservative — *not* candidate-favoured. The +19 elo point
estimate was earned on slightly *less* clock than the opponent got. (This is the same
field-name inversion that once turned a "4× cheaper" read backwards; the legacy field
names `champ_*` / `rung_*` do not mean what they say in a head-to-head.)

The realised 0.9522 drifted down from the probe's 0.9893 because the full run is longer
and thermally loaded — the fanless Air throttles, and the two sides throttle differently.
Still comfortably in-band, so **equal-time stands**.

### 4.3 Cross-cell contrast with the desktop gate — both halves

| | forward path | elo vs deploy champion |
|---|---|---|
| gate arm A (band 82e9) | desktop CUDA batch-1, r ≈ 3.0 | **−17.4 ± 17.4** |
| **this cell (band 92e9)** | **Apple ANE, r = 0.351** | **+19.13 ± 17.40** |

**Δ = +36.53 ± 24.61, z = +1.485 → UNRESOLVED (< 2σ).**

Both halves, stated plainly:

* **The direction is what the r-model predicted.** Cutting the forward's cost from
  r ≈ 3.0 to r ≈ 0.35 moved the point estimate ~+36 elo, from clearly-negative to
  mildly-positive. That is the sign the gate's §6 projection (+11 to +15) implied, and it
  was arrived at independently.
* **It is NOT a confirmation and must not be cited as one.** z = 1.49 on the contrast. The
  two arms sit on **independent bands and different boxes**, combined in quadrature rather
  than deck-paired — exactly the weaker comparison the gate flagged for its own A-vs-B
  contrast. Cross-band pooling has burned this project twice (L2-2, CL-069). A +36 swing
  this size is fully consistent with a true effect anywhere from ~+10 to ~+60, and also
  with the two cells differing for reasons other than the forward.

So: the reopen condition's **mechanism** looks real; its **effect size** is unmeasured.

### 4.4 What it would take to resolve +15 vs 0 — a JOSHUA DECISION, not queued

At this effect size 400 paired games cannot do it. σ scales as 1/√n:

| n paired | 1σ (elo) | z for a true +15 |
|---|---|---|
| 400 (this cell) | 17.4 | 0.86 |
| 800 | 12.3 | 1.22 |
| 1500 | 9.0 | 1.67 |
| 2000 | 7.8 | 1.93 |

**Even n = 2000 lands at z ≈ 1.9 — still short of a clean 2σ.** Separating +15 from 0 at 2σ
needs σ ≤ 7.5, i.e. **n ≈ 2150 paired**. In Air time: this cell's 400 games took **9.10 h**
wall (mean 492.1 s/game ÷ 6 workers), so the additional ~1750 games is **≈ 40 h of
compute** — realistically **3–4 Air-days** on a fanless, shared, sleep-prone laptop.

**This is explicitly a JOSHUA DECISION and is NOT being queued.** The trade: 3–4 days of
the only Apple-silicon box, to move a ~+15 deploy question from "suggestive" to "decided",
for a candidate that is *at best* mildly positive at equal clock and whose gain applies
only to Apple hardware the project does not deploy on. Costed here so the option is
visible, not so it happens.

## 5. results.csv row

Row `distill_strong_iter03_netprior_EQTIME_ANE_k4x438_vs_champ_deploy_b92e9_n400_paired`
in [experiments/results.csv](../../experiments/results.csv) — the authoritative numbers.

## 6. Six-touch close-out

- [x] `experiments/results.csv` row
- [x] `DECISIONS.md` index line
- [x] status banner on THIS doc
- [x] `governance/CLAIM_REGISTRY.csv` — CL-067 row
- [x] `STATUS.md` top block
- [x] `docs/PROGRAM_ROADMAP_2026-07-07.md` G3 + `docs/LEVER_INDEX.md` ANE/eqtime rows +
      `docs/INDEX.md`
- [x] `python3 scripts/doc_lint.py` → 0 errors

## 7. Operational record

| | |
|---|---|
| launched | 2026-07-29 14:31 UTC; first record 14:35:42; last record 23:41:52 |
| wall clock | **9.10 h** (predicted 7.37 h — the gap is the mid-run sleep plus thermal drift) |
| verified at launch | 6 workers busy, 485.6% → 534.5% aggregate CPU, `0 cached, 400 to play` |
| watchdog | `cell_watchdog.sh` PID 54741 — bounded 12 relaunches, terminates on 400 records |
| artifacts | `/mnt/c/carc-shared/eqtime_ane_netprior_k4x438_b92e9/` (400 records + summary + manifest + `CODE_PROVENANCE.txt`); prep evidence in `/mnt/c/carc-shared/m5_ane_prep_20260729/` |

### 7.1 Mid-run Air sleep at records 377→400 — resumed cleanly

The Air slept near the end of the run **despite `caffeinate -dimsu`**. On wake the watchdog
relaunched the cell and it **resumed from 377 records**, completing to 400.

**Data integrity unaffected.** Each game writes its own record atomically (`.partial` →
`replace`), and the harness skips games whose record already exists, so a relaunch
re-plays nothing and cannot half-write a game. Verified after the fact: all 400 records
present, 200 distinct decks, **0 deck_hash mismatches**, 0 timeouts either side, 400/400
endgame latches both sides.

Three standing lessons re-confirmed:

* **The per-record, resume-by-existence design is what saved this run** — the same property
  that made the watchdog safe to arm in the first place. This is the third time it has
  paid out.
* **Success is RECORD COUNT, never an exit code** (the gate's ops note 7). Had the watchdog
  trusted an exit code it would have declared victory at 377/400.
* **`caffeinate -dimsu` is not an absolute guarantee** on a fanless Mac under sustained
  load — keep a watchdog armed alongside it, never instead of it. The wall-clock overrun
  (9.10 h vs 7.37 h predicted) is partly this sleep and partly thermal throttling, so
  **future Air ETAs should carry ~25% headroom.**

⚠️ Anyone re-running this: **W6 is load-bearing.** The k4×438 budget was measured at W6;
changing W changes the champion's ms/sim and invalidates the budget.
