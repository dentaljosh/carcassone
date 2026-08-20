# Tie-arbiter widening campaign — planning consolidation (2026-08-18)

> **🏁 STATUS 2026-08-20 — THE CAMPAIGN IS TERMINAL. ALL FOUR RUNGS *AND* THE B=64 GAME CELL NOW
> HOLD TERMINAL STATES; NOTHING IS RUNNING AND NOTHING IS QUEUED. Exactly ONE follow-up is live,
> and it is an OWNER DECISION: whether the N4 `rho_wall` bar moves above B = 16.**
> This file stays the campaign's rung-state table; it is NOT the verdict of record.
>
> | rung / cell | terminal state | date |
> |---|---|---|
> | (1) meeple plies | `M-DEAD` (census) | 2026-08-18 |
> | (2) `B>16` offline | `W-RISING` (S1, R4 shared run) | 2026-08-19 |
> | (3) `J>4` offline, R4 | `VOID_S2` — bought at n₂ = 1,100, estimand never read | 2026-08-19 |
> | (3) `J>4` successor `rung3_r5` | **`X-INCONCLUSIVE`** — unanswered at the fundable `n`, **not** a null | **2026-08-20** |
> | (4) eps>0 near-ties | `K-DEAD` ∧ `K-STRUCTURAL` (census) | 2026-08-18 |
> | **the `B=64` GAME cell** | **`B-COSTKILL`** — the widening WINS (`z_D` +2.6561) and the rung is UNAFFORDABLE | **2026-08-20** |
>
> ⛔ **`governance/PRODUCTION.yaml` UNTOUCHED on every one of these; NO claim minted by any of them;
> the deployed shape stays B=16 / J=4.** ⛔ **`B-COSTKILL` licenses NOTHING DEPLOYABLE** — B=64 is
> not deployed and is not deployable on this record. ⚖️ **The one live follow-up:** a fresh owner
> wall-clock ruling on the N4 bar above B = 16 (`rho_wall(64)` 2.4897 and `rho_wall(32)` 1.2449 both
> exceed the 1.20 bar, so **the B=32 ladder is not a cheaper route either**; `rho_phone(64)` ≈ 24 is
> a third currency and out of scope). ⛔ **Rung 3 is closed unless re-funded at ~4× n** — the power
> print puts a 2σ resolution of the corrected +0.0842 prediction at `se(Δ_ora)` ≲ 0.021 against the
> realized 0.0455. The rung table's rows are updated in place and a game-cell row is appended;
> the "Sequencing" and "Owner decision asks" sections below are the **funding-time** picture and are
> kept as history. Verdict write-ups: **DECISIONS 2026-08-20** (both) · DECISIONS 2026-08-19 (R4) ·
> `experiments/results.csv` rows `tiearb_widening_r4_S1_rung2_B16to64_offline_n1340plies_b135e9_137e9`,
> `tiearb_widening_r5_S2_rung3_Jgt4_offline_n1059plies_b135e9_137e9`,
> `tiearb_widening_b64_gamecell_WIDE_B64_minus_NARROW_B16_n750decks_b139e9` ·
> [PROGRAM_ROADMAP](../../docs/PROGRAM_ROADMAP_2026-07-07.md).

**Funded 2026-08-17 (late), owner verbatim: "i'm funding all 4. these are our only live
levers for elo. have agents plan them out."** Four rung plans landed the same night
(`PLAN_meeple_ties.md`, `PLAN_B_gt_16.md`, `PLAN_J_gt_4.md`, `PLAN_eps_near_ties.md`),
paper-only — 0 worker-seconds spent, no sealed path touched. This file is the
orchestrator's reconciliation; the rung plans are the authority on their own designs.

## Post-planning state of the four rungs

| rung | state after planning | next physical action |
|---|---|---|
| (1) meeple plies | **CLOSED 2026-08-18 — `M-DEAD` fired** on the pre-written §5 bar: pooled `arbitrable_plies_per_game` **1.410 < 4.0** (per-seat 0.705), `arbitrable_fraction` **0.195**, `fired/game` 7.236 over 1,299 banked games; **80.5% of fired plies are game-equivalent duplicates**. Both corpora agree (phi 14.43% vs 14.61%, ratio 1.012 — no `M-VOID`). `M-DUP-BOUND` did NOT fire: fraction conjunct holds (0.195 < 0.40), supply conjunct fails (7.236 < 8.0). Readout: [`census/READOUT.md`](census/READOUT.md) | **none.** No pricing, no corpus, no code touch; rung leaves the shared prereg. Close-out only: LEVER_INDEX row + roadmap row + DECISIONS line. Deviation on record: plan §4's C5 duplicate-CRN-invariance check was NOT run (needs playouts, outside the census's blind discipline) — must run first if meeple arbitration is ever revived |
| (2) B>16 | **CLOSED 2026-08-19 — `W-RISING` fired** on the R4 shared run's S1 stratum (offline, 0 games as a contest): **Δ(16→64) = +0.0670 pts/tied ply, CI95 [+0.0215, +0.1111], se_root 0.0228, z +2.94, E = 64 worlds, n 1,340 plies / 748 roots**, against the committed floor **+0.04**; reason verbatim *"lower(CI)>0, d>=0.04, arb_64 convicts, arb(64)>arb(16)"*. Secondary Δ(16→32) +0.0597 CI95 [+0.0190, +0.0998] — **never a branch input on its own**. All 7 analyzer-owned gates PASS; `G-REPLICATE` all rungs in envelope, `naive_envelope_caveat` **false**; acceptance `--mode post` PASS. ⚠️ Disclosed, branch unchanged: realized `se_root` **ABOVE** the §3 bracket [0.0179, 0.0200], and n 1,340 vs 1,344 planned (4 rids whole-dropped, disclosed `WindowTruncationError` class). ⛔ The planning row's "two worlds" framing is **not** what was resolved — the design can only say *"a rung above 16 is worth ≥ +0.04"*, and it does; the saturating-exp/√B-noise models stay unresolved. Read-out: `shared_run_r4/verdicts/READOUT.md` | **none required.** Close-out done (results.csv row · DECISIONS 2026-08-19 · roadmap · bands 135e9/137e9 retired). ✅ **The owner-gated B=64 GAME cell WAS bought and RAN — see the game-cell row below (`B-COSTKILL` 2026-08-20).** Ruling 5's translation caveat still binds in **both** directions and travels with every citation |
| (3) J>4 | **`VOID_S2` 2026-08-19 — BOUGHT AND NEVER READ.** The J question WAS purchased at **n₂ = 1,100** and then lost to a `G-DISJOINT` **stratum void** before any leg ran: 29 digest exclusions against a bound of 6, **all at ply 2**, density 2.636% at 5,340 games mined vs 0.181% at the 858-game calibration (**14.6×**) ⇒ a linear-in-`n` bound against a pair-counted density was **the wrong shape**. `estimand_read = false`; the branch table was **NEVER EVALUATED**. ⛔ **Forbidden readings: not "not bought", not "answered", not "inconclusive", and not any rung-3 branch.** A void is **not curable by generating more games**. The S1-side riders (Δ_ora +0.1993, interaction arb_full(64−16) +0.1420, n_capped 230) are **reported and adjudicate nothing**. Disposition [`PREREG_FAILURE_S2.md`](PREREG_FAILURE_S2.md) · owner's Reading-A ruling [`ADJUDICATION_R4_GATES.md`](ADJUDICATION_R4_GATES.md) | ✅ **DONE — the successor** [`rung3_r5/`](rung3_r5/DESIGN.md) **RAN AND READ OUT 2026-08-20 on `X-INCONCLUSIVE`** (row below). It discharged the inherited obligation: **`D-DRAW` RAN** and I7's dedupe-partition conditional is **MEASURED**, no longer carried. Nothing further is queued |
| (4) eps>0 | **CLOSED 2026-08-18 — banked kill CORROBORATED on the fresh gap-CDF piggyback.** TILE (31,827 plies, all champ449 tile plies, no sampling): eps=0.05 adds **+0.66%** vs the 5% power-derived `K-DEAD` bar, and `m ≥ 0.30` first arrives at eps≈1.5–2.0 ⇒ `K-STRUCTURAL` holds. MEEPLE: `K-DEAD` also fires (+3.47% < 5%) but with 5.3× less margin, and **`K-STRUCTURAL`'s conjunct (i) does NOT transfer** — `m ≥ 0.30` arrives at eps≈0.25 (an atom of 4,144 plies at gap 0.25). Changes no branch: `K-DEAD` is census-independent power arithmetic, rung (1) is dead on supply, and the eps-widened sets' arbitrable fraction is unmeasured. Readout: [`census/READOUT.md`](census/READOUT.md) §8 | none — owner ratifies closure; the piggyback that was owed has been delivered |
| (3′) J>4 **successor** `rung3_r5` | **CLOSED 2026-08-20 — `X-INCONCLUSIVE` fired**, stratum `s2`, offline (0 games as a contest): **Δ_ora = +0.0268, CI95 [−0.0593, +0.1155], se 0.0455, z +0.589, n_capped 1,059 / 976 roots at E = 16**; `ora_J4` +0.2521 [+0.1035, +0.4004] clears 0 so the pre-branch guard did NOT fire and **`R_ora` = 1.1063 CI95 [+0.7665, +1.7280] IS reported**; deploy rider `Δ_arb` +0.0204 [−0.0584, +0.0968] adjudicates nothing. **All 19 gate rows PASS**, `G-REPLICATE` **dropped deliberately and with a sentence** (its corner is S1's). ⛔ **NOT A NULL — read it through the separability blind spot: this design CANNOT separate `R_ora` 1.400 from 1.244** (gap 0.054 = z 1.28–2.00 across the whole `sd_delta` bracket [0.9, 1.4], under 2σ everywhere), and the realized CI excludes neither. ⭐ **`D-DRAW` RAN and DISCHARGED I7** — partition 1,060/1,060 agree, **exact identity on 1,001 rids, necessary-condition only on 59**; the chartered agreement rate 0.0443 is **confounded and uninterpretable** (different RNG streams by construction) and adjudicates nothing. **1 rid dropped whole-rid**, class `WindowTruncationError` (D4.18); completion 1,059 ≥ floor 1,007. ⚠️ **Two licensed scoring revs `9bc2ab77` + `a5aa4a5e` (D5.1), caused by the ORCHESTRATOR'S FREEZE VIOLATION (D5.3)** — the B64 aggregator commit landed on `main` while the local leg was live; the empty instrument diff is a witnessed fact but it was **luck, not design**. Read-out: `rung3_r5/verdicts/READOUT_R5.md` | **none.** ⛔ **CLOSED UNLESS RE-FUNDED AT ~4× n:** the power print puts a 2σ resolution of the corrected +0.0842 prediction at `se(Δ_ora)` ≲ 0.021 vs the realized 0.0455 (≈4,200 capped plies). No band consumed (135e9 + 137e9 reused), no claim minted, `PRODUCTION.yaml` untouched |
| **the `B = 64` GAME cell** | **CLOSED 2026-08-20 — `B-COSTKILL` fired: THE WIDENING WINS AND THE RUNG IS UNAFFORDABLE, A WIN THAT CANNOT BE BOUGHT.** Two deck-paired cells, band **139e9**, one deck set, 1,500 games/cell (750 decks × 2 seatings), 0 failed, **all 13 gates PASS**. **PRIMARY `D` = M_WIDE − M_NARROW = +1.7167 pts/game, `se_D` 0.6463, `z_D` +2.6561, n_common 750** vs the committed 2σ floor **+1.427**; WIDE (B=64) wr 0.591 / **+63.9457 ± 9.1231 elo** / M +5.3773 · NARROW (B=16, the deployed rung) wr 0.552 / **+36.2644 ± 9.0197 elo** / M +3.6607, both against the **unmodified champion** as common opponent. `f0` 0.0160 (`G-DIVERGE` PASS, and the nested CRN makes identity a **power loss**, not a win); `G-NEST` byte-identity witness PASS. ⛔ **`B-CONFIRMED` WAS UNREACHABLE BEFORE GAME 1** — `rho_wall(64)` = 2.4897 is 2.07× the N4 bar 1.20 and **no `OWNER_WAIVER.md` predated game 1**, so `W` is FALSE fail-closed and `A` is FALSE. ⛔ **`rho_wall(32)` = 1.2449 ALSO exceeds the bar, so a B=32 win would ALSO be `B-COSTKILL`** — the ladder is not a cheaper route; `rho_phone(64)` ≈ 24 kills on-device at this rung regardless. Read-out: `b64_cell/verdicts/READOUT_B64.md` | ⚖️ **THE CAMPAIGN'S ONE LIVE FOLLOW-UP, and it is the OWNER'S: a fresh wall-clock ruling on whether the N4 bar moves above B = 16.** The branch licenses exactly two things, both needing a fresh prereg or a fresh owner ruling: (i) that ruling; (ii) a ladder question **this cell did not measure in game points** and which no branch may infer from two points. Decision-relevant and **NOT a waiver**: the owner's pre-campaign ruling *"we can afford some wallclock during play… dont let that be the constraint right now"* waived the **consequence, not the measurement**, and was made at B=16 where `rho_wall` = 0.6224. Band 139e9 retires `decision_influenced=yes`; `PRODUCTION.yaml` untouched |

## Cross-plan reconciliation (orchestrator rulings for the DESIGN phase)

1. **Shared run adopted**: rungs (2)+(3) read disjoint statistics of ONE paid instrument
   run. Both planners converged independently; the load-bearing requirements are
   **M=128 world records** (cross-fit parity halves cap usable B at M/2 — the M=64
   shorthand in the funding row is wrong, per PLAN_B_gt_16 correction #1), **uncapped
   arm recording with CRN worlds shared across ALL full-set arms** (PLAN_J_gt_4 §8
   requirement — without it the campaign pays twice), and **both READ_RULEs in one
   blind commit, one read-out**, with `arb(B=16,J≤4)` declared a shared cell.
2. **Cost figures reconciled**: PLAN_J_gt_4's ~83 worker-h standalone vs PLAN_B_gt_16's
   ~865 worker-h total are not in conflict — the shared-run total is dominated by the
   **clair-puct pricing judge (~582 wh — ⚠️ label corrected 2026-08-18: this leg is RUST on walled and has been since 2026-08-02 (`run_tiletie.py` JUDGE_BACKEND + `rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` PASS 940 checks); "python-era" was a mislabel — the 9.4× was captured pre-campaign, no backend speedup remains; committed c_IF=2.35 may be ~1.9× conservative vs the idle-box smoke 1.2313, settled by the pre-run c-remeasure)** and fresh corpus generation
   (~234 wh); the arbiter-side playouts (rust, c=0.178232) are noise. The single
   biggest cost lever is **W1: wire the Phase-A rust ARB judge into
   `scripts/tiletie/run_tiletie.py`** (12.2× on that leg) — instrument work, blocked by
   the commit freeze until the JCZ markers land.
3. **Variance budget ruling** (PLAN_B_gt_16): ~84% of increment variance is pricing
   noise, not position heterogeneity ⇒ buy evaluation worlds (E=64), keep n=1,350.
4. **Band correction**: `133000000000` (suggested in two plans) is the JCZ cells' —
   claimed minutes before the planners read the registry. The widening run reserves
   **`134000000000`** + top-up range; re-read `BAND_REGISTRY.csv` at claim time.
5. **Translation caveat carried programme-wide**: Stage 1b's offline read
   under-predicted Phase B's game-cell result 3.9× (+0.79 predicted vs +3.07 realized
   pts/game). No game cell for B=64 gets sized until the offline increment lands; the
   offline→game map is unestablished in BOTH directions and must be quoted with any
   projection.

## Sequencing (recommended)

0. ✅ **DONE 2026-08-18** — meeple kill-census (+eps gap piggyback), 52.2 s wall / 0.4266
   worker-h against a ≤0.5 worker-h bar. Expected outcome realized: rungs (1)+(4) closed,
   campaign narrowed to (2)+(3). See [`census/READOUT.md`](census/READOUT.md).
1. **W1 instrument wiring** (rust ARB judge into `run_tiletie.py`; bit-exactness
   obligation vs the python judge per the Phase-A G-BITEXACT precedent).
2. **Blind DESIGN + READ_RULE** for the shared (2)+(3) run, then the run:
   ~~≈865 worker-h ≈ 20–22 h wall~~ **RE-PRICED AND FUNDED 2026-08-18: 1,174.2
   worker-h ≈ 26–29 h two-box wall** (rev R3.1 DESIGN §7 roll-up; PLAN_J's leg was a
   ~6× under-estimate — clair-puct omitted — and S2 is its own 1,100-capped-ply
   stratum; owner funded the honest price, verbatim "funded"). W1 wiring LANDED
   (`7b82610f`); prereg pair at rev R3.1 (three review rounds, `shared_run/`);
   W-code merged; §9 sequence executing.
3. Game-cell decision only after the offline read, per ruling 5.

## Two-box SCORING layer (build note, 2026-08-18 — NOT a prereg, NOT a ruling)

`run_tiletie.py` has **no `--shared-claim` and no cross-box work stealing**, so the
scoring legs cannot be split the way generation is: as-is they are single-box
(~31 h local-only at `W_EVAL_LOCAL=30`). The owner ruled to build the two-box layer.
It is a **parameterised copy of the `tiearb2_20260816` machinery** and lives OUTSIDE
`shared_run/` — it is throughput plumbing, not part of the frozen pair:

| file | what it owns |
|---|---|
| [`stage_chunks.py`](stage_chunks.py) | `POSITION_ORDER.json` — ONE committed seeded shuffle (seed **20260817**) per stratum, cut into whole-rid sequential chunks — and the per-chunk `run_tiletie`-shaped plan dirs under `chunks/<stratum>/chunk<k>/`. `verify` re-derives byte-identically. |
| [`ALLOCATION.conf`](ALLOCATION.conf) | the static (stratum × box × judge) → chunk map, with the `30 : 22×0.75` capacity arithmetic shown. **Throughput only — it cannot move a value.** |
| [`run_scoring.sh`](run_scoring.sh) | `run_scoring.sh {local\|laptop-side}` — sources `WORKERS.conf` (`W_EVAL_*`) + `ALLOCATION.conf`, pre-launch aborts, then one `run_tiletie` invocation per allocated chunk at DESIGN §4's knobs. |
| [`merge_legs.py`](merge_legs.py) / [`merge_scoring.sh`](merge_scoring.sh) | reassembles the per-chunk leg output into the exact layout the READ_RULE addresses, with a **per-rid completeness check** that fails loudly on any gap or duplicate. |

**Gate neutrality** (the claim the drafter signs): world/playout seeds are
`sha256(tag|rid|j|salt)` (`oracle_score_pilot.world_seed`/`playout_seed`, which
`tier1_rust_leg` **imports** rather than re-implements). Neither the chunk, the box,
the worker count, the row's index in its leg file, nor `M` enters the derivation.
Chunks are sets of **whole rids**, so `G-CRN`'s cross-judge join and the analyzer's
per-position pairing on `rid` are indifferent to the split, and the merged tree is
byte-indistinguishable **per rid** from a single-box run. Tests:
`tests/test_tiearb_widening_chunks.py`.

Realized two-box scoring wall ≈ **20 h** (vs ~31 h single-box); the DESIGN §7 "17.9 h
parity" figure is the 52-*nominal*-worker number that does not price the laptop's
~25% per-worker slowness.

## Owner decision asks (carried to Joshua)

> ✅ **RATIFIED 2026-08-19 — both census closures.** Executed under the owner's
> 20-hour delegation (verbatim: *"take the highest EV picks. I can't look over
> details right now"*, 2026-08-19), applying the orchestrator's standing
> recommendation. (1) **meeple rung: M-DEAD stands** — the 0.4266 worker-h census
> was the rung's entire budget; no meeple-arbitration instrument is built (revival
> still requires plan §4's C5 duplicate-CRN-invariance check first). (2) **eps>0
> rung: K-DEAD ∧ K-STRUCTURAL stand** — production `eps` stays **0.0**. Recorded
> in DECISIONS 2026-08-19 (delegation entry); LEVER_INDEX rows already carry the
> closures.

- Ratify **eps>0 closure** on banked data (rung funded, answered without spend).
- Ratify **meeple kill-census** as the rung's entire budget unless it survives its bar.
- Confirm the **shared-run shape** for (2)+(3) at ~20–22 h two-box wall (his "these are
  our only live levers" funding stands; this line item is the realized price of it).
- PLAN_J_gt_4 asks 3/4/6 (adjudicating statistic, mining depth, I6 amendment
  pre-approval) — deferred to the DESIGN commit, flagged here so they don't silently
  default.

*Nothing here is a prereg. The blind DESIGN/READ_RULE for any run that fires comes
later, as its own commit, per house discipline. `PRODUCTION.yaml` untouched.*
