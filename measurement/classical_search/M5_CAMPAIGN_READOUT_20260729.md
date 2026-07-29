# M5 CAMPAIGN — luck-floor band 2 (COMPLETE) + the cliff-ladder 688 rung (RUNNING)

**STATUS: CELL 1 COMPLETE (2026-07-29, n=200/200, 0 solver timeouts, 200/200 latches).
CELL 2 RUNNING on the Air under a watchdog — partial, per-record checkpointed.**

**VERDICT (cell 1): THE LUCK FLOOR REPLICATES. On a fresh band the searchless 1-ply tier-1
player takes 12/200 = 6.00% [3.47%, 10.19%] off the deploy champion, against band 1's
13/200 = 6.50% [3.84%, 10.80%] — two-proportion z −0.21. Caveat (2) of
`luckfloor_champ_k4x688_vs_greedy_n200_b54e9` (single-band) is DISCHARGED: the ~6.5% is a
property of the matchup, not of band 54e9. Pooled over both bands the floor is
25/400 = 6.25% [4.27%, 9.06%].**

Run by the experiment-runner session `c0b61ee1` on **Joshua's Apple M5 MacBook Air**, W=10,
under `caffeinate -dimsu`, with a relaunch-on-death watchdog on the box. No source file,
`experiments/results.csv` row, or `governance/` row was touched by this run — the two
draft rows are in §5 for the main session to land.

---

## 1. ⚠️ PLATFORM FLAG — read before citing any number here

**This is the first results-bearing measurement the project has ever produced on
`darwin-arm64`.** Every prior row in [experiments/results.csv](../../experiments/results.csv)
was measured on x86-64 Linux (WSL2 local / laptop / Xeon). This flag travels with both
draft rows and with any number derived from these records.

Everything below was verified **before** any game was scored:

| Check | Result |
|---|---|
| `champion_factory.make_production_champion(..., verify=True)` on arm64 | **PASS** — proves the leaf's curve values and its outputs on real boards, then all three hash dialects |
| `harness_leaf_hash` | `a36d2e15a3b3d71d` — **matches** `governance/PRODUCTION.yaml` |
| `frozen_config_hash_meeple_k0` | `6dfffd57051690f2` — **matches** |
| `frozen_config_hash_meeple_k2` | `158f17ff76adaa02` — **matches** |
| Cython fast path | `flat_leaf_cy` + `flat_repr_cy` compiled **natively for arm64**; `_CY_FLAT_V2=True`, `_CY_SUPPORTS_CURVE=True` at runtime — the fast path, not the pure-Python fallback |
| Harness + agent sources vs the main tree | **7/7 md5 identical** — zero code divergence |

**Provenance trap, recorded so nobody has to reconstruct it.** Each `manifest.json` carries
`code_rev: 3d7ce4f`, which is **not a commit in project history**. The repo reached the Air
by the offline git-bundle pattern, and because a *shallow* bundle cannot be traversed by
`git clone` ("remote did not send all necessary objects"), the snapshot was cut as a
**parentless orphan commit** of the tree at `cc73b3c`. The mapping
`3d7ce4f → cc73b3cc25325a0754835be050afbe040e8c6197 (branch android-app)` is recorded in
`M5_PLATFORM_NOTE.json`, written into **both** output directories on the share.

## 2. The spawn trap — the one platform risk that mattered, and how it was closed

macOS `multiprocessing` defaults to **spawn**, not fork. Workers therefore do **not**
inherit the parent's in-memory state, and the smokes were single-process, so they never
exercised the pool path. If the harness had relied on fork-inherited globals for the
candidate leaf, every worker could have silently searched a **different leaf** — a silent
mis-evaluation, not a crash.

Reading the code says it is safe by construction (`cand_leaf_cfg` is passed explicitly
through `Pool(initializer=_worker_init, initargs=(...))`, and the leaf-hash drift guard runs
in `main()` on the object that gets pickled). **That argument was converted into a
measurement**: the pool-computed record `seed086000000000_a0` was replayed single-process
at the same seed and knobs.

| | score | diff | moves | prefix/exact | latch_k |
|---|---|---|---|---|---|
| pool (spawn worker, W=10) | 113–116 | −3 | 144 | 70/2 | 2 |
| single process (replay) | 113–116 | −3 | 144 | 70/2 | 2 |

**Bit-identical.** The spawn workers reconstruct the champion leaf faithfully, and play on
arm64 is deterministic. This is the check that licenses citing the platform at all.

## 3. Cell 1 — LUCK-FLOOR BAND 2 (band **86e9**, n=200 deck-paired)

Replication of `luckfloor_champ_k4x688_vs_greedy_n200_b54e9` (results.csv row 411) on a
fresh band, with an identical configuration: the PRODUCTION fair champion
(`FairHeuristicPriorAgent`, k4×688 = 2752 total, exact K≤2 marginalized handoff, frozen
curve125 leaf, c_puct 1.5 / tau_p 5.0 / float / visits / value_norm 15, **no strength
overrides**, `meeple_dedup` OFF, `intra_reuse` OFF) versus the tier-1 rung — the leafless
1-ply `RuleBasedPlayer`, no search, no leaf, no endgame tail.

| | **band 1 (54e9)** | **band 2 (86e9) — this run** |
|---|---:|---:|
| champion W/D/L | 187/2/11 | **188/0/12** |
| winrate | 0.9400 (z +12.45) | **0.9400 (z +12.45)** |
| elo | +478.0 ± 51.7 | **+478.0 ± 51.7** |
| deck-paired margin | +27.40 pts/deck (z +21.71) | **+26.97 pts/deck (z +18.75)** |
| **tier-1 steal rate** | **13/200 = 6.50%** | **12/200 = 6.00%** |
| Wilson 95% CI | [3.84%, 10.80%] | **[3.47%, 10.19%]** |
| complete decks | 100 | **100** (0 incomplete) |
| solver timeouts / latches | 0 / 200 | **0 / 200** |

**Both statistics reported per house rule, and they agree.** The two bands are statistically
indistinguishable on the steal rate (two-proportion **z −0.21**), so pooling is legitimate:

> **POOLED FLOOR: 25/400 = 6.25%, Wilson 95% CI [4.27%, 9.06%].**

⚠️ **σ = 51.7, not 24.6.** The house `695·√(0.25/n)` approximation is only valid near
wr = 0.5 and **understates** the error badly at wr = 0.94 (it would say ±24.6). 51.7 is the
delta-method value at the observed winrate; the Wilson interval on the floor is the honest
read. This is caveat (1) of the band-1 row and it applies here unchanged.

**What this licenses, and what it does not.** Read as a **floor, not a gap**: a searchless
1-ply player still steals ~1 game in 16 from the deploy champion on deck variance alone.
That bounds what *any* amount of search can buy in a one-off game — a single exhibition game
against a strong human is ~6% coin-flip against us before strength enters. It is **not** a
strength measurement: +478 elo versus a searchless opponent is saturation-adjacent and must
not be put on the same axis as the vs-h800 or vs-RoD-v2 ladders. Do **not** difference it
against the `blindcurve` k4×688 row (different opponent, different band, not deck-matched).

Cost: champion 3233 ms/move versus tier-1 15 ms/move (221×) — **not** cost-matched, and
deliberately so; the point is what the cheap player still gets. The champion's ms/move here
is the **W=10 contended** figure, not a single-stream number (clean single-stream on this box
is 1.58 s/move, `measurement/m5_bench_20260728/`).

## 4. Cell 2 — CLIFF-LADDER RUNG 688 (band **88e9**) — RUNNING, PARTIAL

This is G2's open loose end. The G2 confirm put 1376 (−53.4, band 76e9) *below* 688 (−37.5,
band 62e9) at cross-band z −0.64, so **the low end's ordering is unmeasured**; shaping the
cliff needs 688 / 1376 / 2752 **deck-matched on one shared band**.

> ## 🔴 THE CLIFF LADDER'S SHARED BAND IS **88e9**
>
> **Rung 688 (candidate k4×172 vs the deploy champion k4×688, n=400 deck-paired) started on
> the M5 on 2026-07-29 06:48Z.** The remaining rungs — **1376 (k4×344)** and **2752** — must
> run on the cluster boxes **against this same band 88e9**, or the ladder is not deck-matched
> and the whole experiment is pointless. Band 88e9 is claimed for the ladder in
> `/mnt/c/carc-shared/BAND_CLAIMS.txt` and is reserved for nothing else.

Configuration (verified in the run banner): candidate `k4×172` (688 total) vs opponent
`fair-champion k4×688` (2752 total), **both sides curve125 `a36d2e15a3b3d71d`**, exact K≤2,
n=400 `--paired` (200 decks), seed_start 88000000000. `diff`/elo are candidate-minus-opponent.
The harness's own asymmetric-budget warning applies: this is a whole-config budget contrast,
not a single-variable swap.

**Progress at hand-off: 0/400 records (started 06:48:15Z).** Per-record checkpointing means
every completed game is banked; the harness resumes by skipping game JSONs that already
exist, so a relaunch never duplicates or loses work. Expected ~4–5 h at the measured rate.
Records land in `/mnt/c/carc-shared/cliff_ladder_688_m5/`.

## 5. Draft `results.csv` rows — **NOT appended by this run**

Land these from the main session. Column order is the file's own header.

**Row 1 — cell 1, COMPLETE and citable:**

```
luckfloor_champ_k4x688_vs_greedy_n200_b86e9,2026-07-29,base,cc73b3c,200,fair_champion_curve125_k4x688_PRODUCTION,1.5,8,fair_k4x688_deploy,2752,greedy_RuleBasedPlayer_1ply_tier1,-,-,v1_1ply,1,188,12,0,+478.0,51.7,+26.97,/mnt/c/carc-shared/luckfloor_band2_m5,high,"DECK-LUCK FLOOR, BAND 2 — the fresh-band replication that discharges caveat (2) of luckfloor_champ_k4x688_vs_greedy_n200_b54e9. Identical config to that row (PRODUCTION fair champion k4x688=2752, exact K<=2 marginalized, frozen curve125 leaf a36d2e15a3b3d71d, c_puct 1.5 / tau_p 5.0 / float / visits / vn15, NO strength overrides, meeple_dedup OFF, intra_reuse OFF) vs the SAME leafless tier1 rung (1-ply RuleBasedPlayer). n=200 deck-paired = 100 complete decks, 0 incomplete, band 86e9 (fresh; verified unburned against BAND_CLAIMS.txt + the share manifests -- results.csv has NO seed_start column and that check fails silently open). 0 solver timeouts; champion latched the exact tail in 200/200. winrate 0.9400 (z +12.45), elo +478.0 +/- 51.7, deck-paired seat-balanced margin +26.97 pts/deck (z +18.75). BOTH STATISTICS REPORTED; they agree. *** THE NUMBER: tier1 took 12/200 = 6.00% (12 wins + 0 draws), Wilson 95% CI [3.47%, 10.19%]. *** REPLICATES BAND 1 (13/200 = 6.50% [3.84%, 10.80%]): two-proportion z -0.21, and winrate/elo land IDENTICAL to 3 s.f. ⇒ the ~6.5% floor is a property of the MATCHUP, not of band 54e9. POOLED OVER BOTH BANDS: 25/400 = 6.25%, Wilson [4.27%, 9.06%] -- cite the pooled figure for the human-facing claim. READ AS A FLOOR, NOT A GAP: a searchless 1-ply player steals ~1 game in 16 on deck variance alone, which bounds what ANY amount of search buys in a one-off game. sigma 51.7 is the delta-method value AT wr=0.94; the house 695*sqrt(0.25/n)=+/-24.6 approximation is valid only near wr=0.5 and UNDERSTATES here -- the Wilson interval is the honest read. Do NOT difference against blindcurve k4x688 (different opponent AND band). elo +478 vs a searchless opponent is saturation-adjacent; keep it off the vs-h800 / vs-RoDv2 axes. COST: champion 3233 ms/move vs tier1 15 ms/move (221x), NOT cost-matched by design; the champion figure is W=10 CONTENDED, not single-stream (clean single-stream on this box is 1.58 s/move). ⚠️⚠️ PLATFORM: darwin-arm64 (Apple M5 MacBook Air, 4P+6E, 32GB, macOS 26.5.2), W=10, 80.5 min wall -- THE FIRST RESULTS-BEARING RUN THE PROJECT HAS PRODUCED ON APPLE SILICON; every other row in this file is x86-64 Linux. Platform trusted only because: verify=True passed on arm64, all THREE leaf-hash dialects match PRODUCTION.yaml, Cython built natively (fast path active, not the pure-Python fallback), harness+agent sources 7/7 md5-identical to the main tree, and -- the load-bearing one -- macOS multiprocessing is SPAWN not fork, so a pool-computed record was REPLAYED SINGLE-PROCESS and came back BIT-IDENTICAL (113-116, diff -3, 144 moves, prefix/exact 70/2, latch_k 2), proving the spawn workers reconstruct the champion leaf. Manifest code_rev reads 3d7ce4f = a PARENTLESS transport snapshot of cc73b3c (shallow bundles cannot be cloned); mapping + all verification in src_dir/M5_PLATFORM_NOTE.json. Harness ran BYTE-UNMODIFIED (a bare --smoke crash was avoided via --games, not patched; fix filed at scripts/m5_bench/patches/0001-eval_fair_puct-bare-smoke-games-none.patch). Read: measurement/classical_search/M5_CAMPAIGN_READOUT_20260729.md"
```

**Row 2 — cell 2, PENDING (do not land until the cell finishes; W/L/D/elo/margin are placeholders):**

```
cliff688_k4x172_vs_deploy_n400_b88e9,2026-07-29,base,cc73b3c,400,fair_champion_curve125_k4x172_CANDIDATE,1.5,8,fair_k4x172_688total,688,fair_champion_curve125_k4x688_PRODUCTION,1.5,8,fair_k4x688_deploy,2752,<W>,<L>,<D>,<elo>,<sigma>,<avg_diff>,/mnt/c/carc-shared/cliff_ladder_688_m5,<conf>,"CLIFF LADDER RUNG 688 — rung 1 of 3 for G2's unresolved loose end (the low end's budget ORDERING is unmeasured: the G2 confirm put 1376 at -53.4 BELOW 688 at -37.5, cross-band z -0.64). *** SHARED BAND 88e9 — rungs 1376 (k4x344) and 2752 MUST run against THIS band or the ladder is not deck-matched. *** Candidate k4x172 (688 total) vs the deploy champion k4x688 (2752 total), BOTH SIDES curve125 a36d2e15a3b3d71d, exact K<=2, n=400 --paired (200 decks), seed_start 88000000000. Asymmetric budgets by design (whole-config budget contrast, not a single-variable swap); diff/elo are candidate-minus-opponent. ⚠️ PLATFORM: darwin-arm64 (Apple M5), W=10 -- see the cell-1 row and M5_PLATFORM_NOTE.json for the full platform verification, which covers this cell too. Read: measurement/classical_search/M5_CAMPAIGN_READOUT_20260729.md"
```

## 6. Ops record

- **Bands claimed** (appended to `/mnt/c/carc-shared/BAND_CLAIMS.txt` **before** launch):
  **86e9** (luck-floor band 2) and **88e9** (the cliff ladder's shared band). Both verified
  unburned by enumerating `seed_start` across the share manifests **and** the claims file —
  `results.csv` has no band column, so the prescribed grep fails silently open.
- **Box**: Apple M5 MacBook Air, 4P+6E, 32 GB, macOS 26.5.2, `ssh joshuaishal@100.64.175.108`.
  W=10 (the measured throughput optimum for this box). Verified immediately after launch:
  10 workers at 91–98% CPU, ~914% aggregate.
- **Sleep is the hazard on this box.** Idle-sleep is 1 minute, and an un-caffeinated attached
  smoke was killed mid-flight during setup — the Air then dropped off Tailscale entirely and
  was unreachable for ~20 minutes. Every launch is wrapped in `caffeinate -dimsu`, plus a
  standalone 20 h assertion so the box cannot drop off even if the driver dies. A local
  "catcher" loop was left armed to fire the campaign the instant the box reappeared.
- **Watchdog**: `~/m5_campaign.sh` relaunches a dead cell up to 40 times; because the harness
  resumes by skipping existing per-game JSONs, relaunch never duplicates or loses a record.
- **Sync**: the Air has no share mount, so records rsync to `/mnt/c/carc-shared/` every
  15 min (`M5_SYNC.log`).
- **Timing**: cell 1 ran 05:27:44Z → 06:48:15Z = **80.5 min** for 200 games at W=10
  (2.5 games/min, mean 185 s/game).
- **Patch filed, deliberately NOT applied**:
  `scripts/m5_bench/patches/0001-eval_fair_puct-bare-smoke-games-none.patch`. `_smoke()` reads
  `args.games`, which argparse leaves `None` unless passed, so a **bare `--smoke` always
  crashes** with `TypeError: '>' not supported between instances of 'NoneType' and 'int'`.
  The defect is **platform-independent** — it reproduces on Linux. Both smokes passed
  `--games N` instead, which keeps this campaign's code divergence at exactly **zero**.
