# TIE-ARBITER WIDENING — SHARED INSTRUMENT RUN, DESIGN (rungs 2 `B>16` + 3 `J>4`)

> **STATUS: BLIND PREREGISTRATION, DRAFT (revision R1). NOT LAUNCHED. NOTHING RUN. NO
> OUTCOME STATISTIC OF ANY KIND WAS READ WHILE WRITING THIS.**
>
> ⚠️ **BLIND-ORDER REQUIREMENT — NOT YET SATISFIED.** This file and
> [`READ_RULE.md`](READ_RULE.md) were drafted and revised in an isolated **worktree** while
> the main tree is under a commit freeze. A worktree commit does **not** satisfy blindness.
> **Both files must be committed to the MAIN tree, in ONE commit, BEFORE the band is claimed
> and BEFORE one position is scored — and AFTER the §9 W-code merge.** Until that commit
> exists, no leg of this run may start. Neither file may be edited after that commit except
> through a numbered `§0` pre-run amendment that leaves every branch condition byte-identical
> (the Stage-2 precedent).
>
> **Revision R1 (this file) folds in [`REVIEW_R1.md`](REVIEW_R1.md)** — an independent
> adversarial review of the first draft (commit `e788b143`) that verified every witness
> address against the emitters and found 21 defects, four of them gates that **void a healthy
> run**. Disposition of all 21: **§13**.
>
> Authorities this obeys: [`CAMPAIGN.md`](../CAMPAIGN.md) rulings 1–5 (rungs 1 and 4 are
> CLOSED; this run carries **only** rungs 2+3) · [`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) ·
> [`PLAN_J_gt_4.md`](../PLAN_J_gt_4.md) · [`census/READOUT.md`](../census/READOUT.md) ·
> [`REVIEW_R1.md`](REVIEW_R1.md) · the merged W1 build (wiring commit `7b82610f`:
> `scripts/tiletie/tier1_rust_leg.py`, `run_tiletie.py --arb-backend rust`).
> Where a PLAN and this DESIGN disagree, **this DESIGN governs the run** and §14 records why.
>
> **Owner ruling 2026-08-18: FUNDED** at the full ≈1,174 worker-h shape (verbatim
> *"funded"*), with two orchestrator rulings folded in: (a) the **N4 `rho_wall ≤ 1.20` waiver
> question above `B = 16` stays OPEN** and is **re-priced at the flip decision** — this run
> may **not** be labelled informational-only and may **not** claim the waiver extends; the
> open question rides as `R6`; (b) **the phone is out of scope for this axis.**
>
> `governance/PRODUCTION.yaml` is untouched by this DESIGN and by every branch of the
> READ_RULE. No claim id is minted. No `experiments/results.csv` strength row is created.

---

## 1. What this run is

One paid instrument run, one corpus, two rungs reading **disjoint statistics**, **one blind
commit, one read-out, one analyzer invocation**. It is an **offline pricing measurement of
tied tile plies** — not a strength cell, not a game cell, not a deploy.

- **Rung 2 (`B>16`)** — is the arbiter's CRN-sample ladder still rising above `B = 16`?
  Primary: `Δ(16→64)` on `arb`.
- **Rung 3 (`J>4`)** — at plies where the `J ≤ 4` cap bit, what does pricing the **full**
  deduped arm set buy? Primary: `Δ_ora` at capped plies, against two pre-registered
  multipliers (legacy **1.400**, dedupe-corrected **1.244**).

**Out of scope on every branch:** any game cell, any pts/game projection without the §7
translation rider, **the phone (owner ruling)**, any `J`-by-condition deploy policy, any
change to `rust/`, `src/`, `engine/`, `scripts/classical_search/`.

---

## 2. Cells and their statistics

Two **root-disjoint** strata mined from ONE fresh game set. `E` = evaluation (clair-puct)
worlds; usable `B` is `M/2` because the estimator cross-fits on parity halves
(`analyze_tiletie.parity_indices`; PLAN_B §0.2).

| cell | stratum | arm set priced | worlds | statistic | owner |
|---|---|---|---|---|---|
| **B-LADDER** (primary, rung 2) | S1 | J=4 seeded subset (`subset_j4`) | `M=128` → `E=64` | `arb(B)`, `B ∈ {1,2,4,8,16,32,64}`; **PRIMARY `Δ(16→64)`** | rung 2 |
| B-LADDER-E16 | S1 | `subset_j4` | `M=128` → `E=16` sub-read | same ladder at Stage-1b's precision | rung 2 |
| **SHARED CELL** `arb(B=16, J≤4, E=16)` | S1 | `subset_j4` | `B=16`, `E=16` | ONE number, **declared shared**; printed identically in both rungs' sections; neither rung's branch may be conditioned on it beyond READ_RULE §2's gates | both |
| **J-RIDER** (primary, rung 3) | S2 | full deduped set **vs** `subset_j4` | `M=32` → `E=16`, `B=16` | **PRIMARY `Δ_ora = ora_full − ora_J4`**; `R_ora = ora_full/ora_J4`; `Δ_arb`, `R_arb` as **deploy riders** | rung 3 |
| J-REPLICATION | S1 ∩ capped (≈244 plies) | full vs `subset_j4` | `M=128`, `E=64` | `Δ_ora` — independent, higher-precision, **non-adjudicating** | rider |
| B×J INTERACTION | S1 ∩ capped | **full set** | `B ∈ {16,64}`, `E=64` | `arb_full(64) − arb_full(16)` and `arb_full(16) − arb_J4(16)` — the selection-noise question | rider |
| `D-DRAW` | S2 capped plies | — (no playouts) | — | agreement rate between the instrument's J=4 draw and the **deployed** rust draw — the reported magnitude of I7's conditional, **non-adjudicating** | rider |

**Adjudicating statistic (PLAN_J ask 3 — RESOLVED):** `ora` adjudicates rung 3, `arb` rides
as the deployable quantity (PLAN_J §9.3's own recommendation).

**Reported in full, never a branch input:** the 7-rung × 2-`E` ladder with `arb`, `z`, `F`,
`F_fixed`, `rho_wall`, contended `ms_ratio` projection · pick-churn per doubling ·
oracle-agreement per rung · `arb − rnd` per rung · the S1/S2 half-split · `R_arb` · `D-DRAW`.

---

## 3. Corpus

**Generation.** Fresh champion self-play, config matched **verbatim** to
`measurement/champ_action_logs/CORPUS_MANIFEST.json` (FairHeuristicPriorAgent, k_dets=4 ×
sims=688 = 2752, exact_endgame K≤2, leaf `a36d2e15a3b3d71d`, `rules_profile=walled`), the
`measurement/tiearb2_20260816/run_gen.sh` pattern:
`scripts/distill_flywheel/gen_fair_distill.py --backend rust`, `--shared-claim` work-stealing,
both boxes, `nice -n 19`, detached. **Only the deck-seed band differs ⇒ root-level
disjointness by construction.**

**Band.** Claim **`135000000000` + 0…+849** (850 games). **Top-up range `136000000000` +
0…+199 RESERVED, not licensed** except by the blind corpus top-up clause below. CAMPAIGN
ruling 4 named `134000000000`; that is **superseded** — the JCZ re-run consumed it. **Re-read
`governance/BAND_REGISTRY.csv` at claim time regardless** and claim the row before game 1
(tier `claim`, `decision_influenced=no`, notes stating **OFFLINE CORPUS SUBSTRATE — no
strength cell, no results.csv row**). Precedent deviation recorded: the Stage-1b corpus used
an *unregistered* band (`28100000000…`); registering is the stricter choice and is what
CAMPAIGN ruling 4 asks for.
**Band witness (REVIEW_R1 §19):** the working analogue is
`tiearb2_corpus_lib.py verify-champgames` → `CHAMP_GAMES_VERIFY.json` with
`{band_ok, seed_band, n_games_realized, n_out_of_band, n_duplicate_seeds,
sha256_of_sorted_seeds}`. That emitter deliberately publishes a **digest, not a seed list** —
a disclosure-discipline choice this DESIGN keeps. **No `seeds_used` list is emitted anywhere.**

**Yield math (PLAN_B §3 / PLAN_J §4).** φ = 17.57 tied tile plies/game (candidate-side);
capped fraction 0.1807 ⇒ **3.17 capped plies/game**.

| stratum | games | mining ceiling | target | supply at target |
|---|---|---|---|---|
| **S1** — uniform tied plies (B-ladder) | 350 (band +0…+349) | `--max-per-game 4` | **n₁ = 1,350** | 1,400 |
| **S2** — capped-only plies (J rider) | 500 (band +350…+849) | `--max-per-game 3` (PLAN_J ask 4 — RESOLVED: ≤3 capped plies/game, root-bootstrap SEs) | **n₂ = 1,100 capped** | ≈1,150 expected |

**Blind corpus top-up clause (pre-licensed here, exercisable ONCE):** if the realized S2
capped yield is `< 1,100` at build time, extend generation into the reserved `136e9` range
until it reaches 1,100. **Licensed ONLY before the first scoring leg starts** — i.e. while no
statistic of this corpus exists. After any leg starts it is dead and a shortfall is read
under READ_RULE §2's completion floor.

**Disjointness.** S1 ∩ S2 root-disjoint by band split. Both disjoint from
`measurement/tiletie_pricing_20260812/positions_pooled`,
`measurement/tiearb2_20260816/corpus/positions`, and
`measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_all.txt` — proved by the **W5** merged
gate, not asserted (`G-DISJOINT`; the stock `gate_disjoint.py` compares exactly **two**
ARMS.json corpora and cannot read a rid-txt, so W5 must wrap it into one merged report —
§8).

---

## 4. Instrument invocation

⚠️ **There is deliberately no runnable command block here.** The first draft carried one and
`REVIEW_R1` §15 showed that, run literally, it would have built the **wrong corpus and then
crashed**: it defaulted `--champgames-path` to the **spent** corpus, defaulted
`--n-champgames 1200` (below S1's 1,400), admitted e4 + bank rows into a fresh-band
disjointness argument (there is no `--no-e4` flag — the stand-ins are `--e4-dir ''`,
`--limit-e4-games 0`, `--bank-path ''`, `--limit-bank 0`), and omitted three working phases of
the precedent driver (collect + band verify; the **shadow-root** transposition/afterstate map,
without which `build_positions` silently globs the SPENT corpus's map; `champ_picks`, without
which the S1 build raises `KeyError` on row 1).

**The invocation of record is the W6 driver** — `scripts/tiletie/build_widening_corpus.sh`, a
**parameterised copy of the working `scripts/tiletie/build_tiearb2_corpus.sh`** (all 5 phases
incl. the shadow-root step and the empty-stand-in switches), reviewed and merged **before the
band claim** (§9). Worker counts live in **`measurement/tiearb_widening_20260817/WORKERS.conf`
— outside this frozen prereg directory** (REVIEW_R1 §20), so a W retune is never a mid-run
edit to a frozen file. Every leg `nice -n 19` and **detached** (`setsid nohup … & disown`).

The knobs the driver must resolve, and which this DESIGN fixes (they are the graded ones):

| knob | S1 | S2 |
|---|---|---|
| `run_census --max-per-game` | 4 | 3 |
| `build_positions --cap-j` | `inf` (uncapped; `arms_full` + `subset_j4` recorded) | `inf` |
| `--sample-seed` | 20260819 | 20260819 |
| `run_tiletie --m` | **128** (`b_ceiling_from_m` 64) | **32** (`b_ceiling_from_m` 16) |
| `run_tiletie --judges` | `clair-puct tier1-greedy` | `clair-puct tier1-greedy` |
| `--arb-backend` / `--arb-legal-mask-cache` | `rust` / **on** | `rust` / **on** |
| `--only-profiles` | `walled` | `walled` |
| S2 build | **two-pass**: pass 1 `--allow-missing-champ-picks` (free, no playouts) to learn `capped_at_4`; select ≤3 capped rids/root; pass 2 with champ picks for the selected rids only. `capped_at_4` is knowable **before** any pricing — the selection is outcome-blind by construction. | |

**All output paths are ABSOLUTE and under `RUN/`** (REVIEW_R1 §16): `--manifest-out`,
`--smoke-manifest`, `--gate-out` and the W6/W5 gate files resolve to
`/home/doctor/projects/carcassone/measurement/tiearb_widening_20260817/shared_run/…`, never a
CWD-relative name. Leg records stay on the share
(`/mnt/c/carc-shared/tiearb_widening_20260817/{s1,s2}/…`, per-record `jsonl`), and the driver's
final phase **copies every leg `manifest.json` back** to
`RUN/legs/<judge>/<profile>/leg<N>/manifest.json` — the address the READ_RULE reads.

**Why S2 runs at `M=32`, not 128.** Rung 3 reads only `B=16`, which `M=32` fully supplies
(sel 16 / eva 16), and `E=16` is **the precision Stage-1b's `capped_only` levels — the source
of the +0.1382 / +0.0842 predictions — were measured at**. Matching it keeps predictions and
measurement in one currency and costs 4× less. `ora` is `E`-dependent (it is the value
reachable by an oracle selecting on `E/2` worlds), so **S1 and S2 are never pooled**.

**Salts, explicit (the W1 two-salt finding).** Three distinct seed streams, recorded, never
conflated:

| stream | value (exact join order) | set by | governs |
|---|---|---|---|
| CRN world/playout salt | **`tiletie-v1`** | `run_tiletie.WORLD_SEED_SALT` (module constant, not a flag) + `tier1_rust_leg --world-seed-salt` | which determinized worlds every arm and both judges share |
| instrument cap draw | **`tiletie-cap` \| `<rid>` \| `20260812`** | `build_positions._seeded_cap` | which arms `subset_j4` contains |
| deployed cap draw | **`tiearb2-deploy-v1` \| `<state_digest>` \| `<ply>` \| `cap`** | `carc-core::tiearb::build_arms` (MT19937) | which arms the **shipped** arbiter would have priced |

---

## 5. The W4 / `G-CAP` decision — **RESOLVED: instrument-draw-only scope**

**W4 is CLOSED as an emission item.** The merged W1 build already emits, per ply, `arms_full`,
`subset_j4`, `subset_j4_id`, `cap_seed`, `capped_at_4`, `n_distinct_afterstates` and
`champ_outside_tieset` — PLAN_J §8 requirements (1)–(3). PLAN_B §3 still lists W4 as
outstanding; it is not.

**What was left to this DESIGN is the *reconstruction* question, and the answer is: we do NOT
build it as a gate, and `G-CAP` as written in PLAN_J §6 is RETIRED as unsatisfiable.**
PLAN_J §6 asks a gate to assert that the recorded J=4 subset reproduces the *deployed* seeded
draw — but PLAN_J §2 itself records that the corpus-time draw
(`random.Random(sha256("tiletie-cap"|rid|20260812))`, python) and the runtime draw (MT19937
seeded `sha256("tiearb2-deploy-v1"|state_digest|ply|"cap")`, rust) are **deliberately not
stream-identical**. A gate demanding their identity **fails on every healthy run** — the exact
shape of the three JCZ conjuncts (`§0.F.2b`, `§0.F.2c`) that made an adjudication unreadable,
and the reason every gate in READ_RULE §2 now carries a healthy-run column. Building the
reconstruction as a *gate* would not repair it: it would import an **unverified cross-language
identity** onto the critical path of a measurement that does not need it, so a failure would be
uninterpretable — an instrument defect wearing the clothes of a finding. And it is not needed:
the estimand is `Δ = E[v(argmax over the full deduped set)] − E[v(argmax over a
uniform-without-replacement J=4 draw from that same set)]`, and **both generators force-include
the reference arm and draw `j−1 = 3` uniformly without replacement from an identically-ordered
candidate list** (verified: `tiearb.rs:293-311` vs `build_positions._seeded_cap`) ⇒ **the same
marginal law at `j = 4`**, so the instrument draw is an unbiased, identically-paired estimator
of the deployed contrast. `G-CAP` is replaced by the satisfiable `G-DRAW` (READ_RULE §2).

### `I7-draw-scope` — the rider, in the form it must be quoted

> **`I7-draw-scope`.** The J=4 comparator is the **instrument's** seeded draw, not the deployed
> arbiter's: different salt, different RNG, by construction. The **population** claim is
> licensed — the two draws share the same marginal law at `j = 4`. The **per-ply** claim (*"at
> this ply the shipped arbiter left X on the table"*) is **NOT** licensed.
> **(a) The instrument draw is NOT nested in `j`.** `random.sample` switches algorithms on
> `k` vs `n`, so `subset_j4` is *not* a prefix of a `j = 8` draw from the same seed;
> `build_positions._seeded_cap`'s docstring ("the same seeded one at every J … a pure function
> of (rid, full arm set, J)") **implies a nesting that is FALSE**. Harmless at `j = 4` — the
> recorded subset is produced by the identical call — but **FATAL to any future `J = 8`
> sub-read of this corpus**, which must therefore never be taken without re-deriving the draw.
> (The *deployed* rust draw **is** nested in `j`: its seed omits `j`. The two facts are
> opposite and must not be swapped.)
> **(b) The load-bearing unverified conjunct is the DEDUPE PARTITION.** The licence above holds
> **conditional on the python afterstate-dedupe key and rust `string_representation` inducing
> the same partition of the tie set**, which **this run does not verify**. If the partitions
> differ, the two draws are over different supports and the marginal-law argument does not
> apply. `D-DRAW` (§2, funded) reports the **magnitude** of that conditional as a measured
> agreement rate; it adjudicates nothing.

Recorded, not relied on: the rust cap seed omits `j` (`tiearb.rs` L300 vs its L353 doc
comment) — a doc bug in a frozen crate.

---

## 6. Power arithmetic (shown, not asserted)

**Rung 2 — the variance law, corrected (REVIEW_R1 §12).** The measured law
`Var(Δ; E) = T + N/E` with `T = 0.19, N = 15.4` is the law fitted to **`Δ(8→16)`**, and it
reproduces that increment exactly: at `n = 1350, E = 16`, `se = √((0.19+0.9625)/1350) =
0.02922` vs Stage-1b's published **0.0290** ✓. **It does NOT reproduce PLAN_B's published
`se(Δ(16→64)) = 0.0198–0.0203`** — that figure back-solves to `T ≈ 0.30`, i.e. PLAN_B
(correctly, but silently) allowed the wider 2-doubling increment more position heterogeneity.
**`T` for `Δ(16→64)` is UNMEASURED.** This DESIGN therefore pre-registers a **bracket** rather
than a point:

```
T = 0.19 (the measured 1-doubling law, extrapolated)  ⇒ se(Δ(16→64)) = √((0.19+15.4/64)/1350) = 0.0179
T = 0.30 (implied by PLAN_B's published figure)       ⇒ se(Δ(16→64)) = √((0.30+15.4/64)/1350) = 0.0200
⇒ se(Δ(16→64)) ∈ [0.0179, 0.0200]   ⇒   2σ ∈ [0.0357, 0.0400]
```

**The committed floor stays `+0.040`** — the conservative end of the bracket and the number
the campaign already carries. **The realized root-bootstrap se governs every significance
test**; the floor is fixed and does not move with it.

| pre-registered model (PLAN_B §1) | Δ(16→64) | z at se 0.0179 / 0.0200 | clears the +0.040 floor? |
|---|---|---|---|
| log-linear in `log2 B` | +0.0640 | 3.58 / 3.20 | **yes** |
| hyperbolic `L·B/(B+K)` | +0.0530 | 2.96 / 2.65 | **yes** |
| power `a·B^p` | +0.1958 | 10.94 / 9.79 | **yes** |
| saturating exp `L(1−e^{−B/τ})` | +0.0171 | 0.96 / 0.86 | **no** |
| selection-noise `L(1−k/√B)` | +0.0209 | 1.17 / 1.05 | **no** |

⇒ **a null here means "no rung above 16 is worth ≥ +0.04 pts/tied ply", NOT "Δ = 0".**
Secondary `Δ(16→32)`, `se ≈ 0.018`, floor +0.036 — under-powered by design, reported with its
CI, **never a branch input on its own**.

**Rung 3.** `sd_Δ` is unmeasured anywhere and is **bracketed** in advance: bounded above by the
per-position level sd (1.7197), reduced by the ~61% of capped plies where the full-set argmax
already lies inside the J=4 subset (exact zeros) ⇒ **`sd_Δ ∈ [0.9, 1.4]`**. At
**N_capped = 1,100**: `se(Δ_ora) = sd_Δ/√1100 ∈ [0.0271, 0.0422]`.

| prediction | `Δ_ora` pts/capped ply | z at sd 0.9 / 1.4 | resolved at 2σ? |
|---|---|---|---|
| legacy ×1.400 | +0.1382 | 5.10 / 3.27 | **yes** |
| corrected ×1.244 | +0.0842 | 3.10 / **1.995** | **yes at `sd_Δ ≤ 1.396`; NO at 1.4** (REVIEW_R1 §13) |
| cap-was-free ×1.00 | 0 | — | separable from both, **but see the X-FREE reachability note** |
| **1.400 vs 1.244** (Δ = 0.054) | — | 2.00 / 1.28 | **NO — pre-registered blind spot** |

**X-FREE reachability (REVIEW_R1 §9).** `X-FREE` needs the CI to contain 0 **and** exclude
+0.0842 simultaneously. At the pessimistic bracket end (`sd_Δ = 1.4`, half-width ≈ 0.0827) that
requires a point estimate `≤ +0.0015` — i.e. **essentially zero, or negative**. The read-out
must print the attainability window at the *realized* se (READ_RULE §5).

**All SEs are root-bootstrap** — resample `root_id`, **2,000 reps, seed `20260819`**, cluster =
root; CIs are percentile (2.5 / 97.5). **Significance is defined ONCE, on the percentile CI**
(REVIEW_R1 §8): a quantity is significant iff `lower(CI95) > 0` (or `upper(CI95) < 0` for a
negative claim). A naive per-ply se is never a branch input.

---

## 7. Cost and ETA — **two currencies, never converted**

**Currency A: offline worker-seconds.** `c_ARB = 0.178232` worker-s/playout (rust, W30
contended), `c_IF = 2.35` (from banked `elapsed_secs`). Playouts per judge =
`n × 2 × (Ā − 1) × M`; `Ā_full` = 3.581 all plies / 7.12 at capped plies.

| item | worker-h |
|---|---|
| generation, 850 games @ 990 worker-s | 233.8 |
| champ picks, 2,450 positions @ 13.755 worker-s | 9.4 |
| S1 ARB (rust) — 891,993 playouts | 44.2 |
| S1 IF (clair-puct) — 891,993 playouts | 582.3 |
| S2 ARB — 430,848 playouts | 21.3 |
| S2 IF — 430,848 playouts | 281.2 |
| `D-DRAW` (funded rider; replay + `tiearb_probe`, no playouts) | 2.0 |
| **TOTAL** | **≈ 1,174** |

**ETA.** Generation at the F7d **GEN** counts (local **W48** / laptop **W24** = 72) ≈ 3.2 h
parity; scoring at the F7d **eval** counts (local **W30** / laptop **W22** = 52) ≈ 17.9 h
parity; with PLAN_B's 25% laptop-slowness + contention allowance, **≈ 26–29 h two-box wall**.
**FUNDED** by the owner at this shape.

**⚠️ `c`-REMEASURE OBLIGATION (binding, pre-run, one-sided).**

1. **Judge legs.** Before the S1 IF leg starts, **on an IDLE box** (a timing bench is an
   exclusive tenant), run `run_tiletie --smoke` at production knobs (`--m 128`,
   `--arb-backend rust`, walled, ≥20 positions) **once per judge** and read
   **`SMOKE_MANIFEST_S1_<judge>.json::c_worker_secs_per_playout`** — the Σ`elapsed_secs`/playout
   figure of record. ⚠️ **NOT `worker_secs_per_playout`**, which is the wall×W figure the
   emitter's own banner says not to cost from (inflated ~1.9×; a healthy smoke read at that key
   would HALT a healthy run — REVIEW_R1 §5).
2. **Generation leg** (REVIEW_R1 §21 — the largest single line-item disagreement, 990 vs the
   ~440 worker-s/game implied by the F7d GEN row, and the judge smoke cannot see it): a
   **separate timed 10-game generation smoke** on the same idle box, at the §3 config and the
   GEN worker counts, recorded to `RUN/corpus/GEN_SMOKE.json::worker_secs_per_game`.
3. **HALT is ONE-SIDED.** Halt and re-price only if a realized `c` is **>25% COSTLIER** than
   committed. Cheaper is recorded, never a halt (the generation line is already ~2.25×
   conservative). A re-priced run above **1,500 worker-h** requires fresh owner authorization.
   Realized-vs-committed for all three legs is written to `RUN/RUN_MANIFEST_S1.json`.

**Currency B: deploy wall (NOT convertible — Stage-2 §0.G; quoted, never derived from currency
A).** `rho_wall` (sequential, N4 bar 1.20): B=16 **0.6224** · B=32 **1.2449** · B=64
**2.4897**. Realized contended in-cell `ms_ratio`: **2.42 at B=16**, projected ≈3.75 / ≈6.50.
Rung 3: `Ā` 3.0022→3.5044 = +16.7% per fired ply, `rho_wall` → ≈0.727, `ms_ratio` ≈2.42 →
**≈2.66** (+9.7% per-move wall). **Every one of these is re-measured at the flip decision,
never inferred** — including whether the N4 waiver extends above B=16, which the owner has
ruled stays **OPEN and re-priced there** (rider `R6`). `rho_phone` is a third currency and is
**out of scope for this axis** (owner ruling).

---

## 8. Instrument work items

| item | state |
|---|---|
| **W1** wire rust ARB judge | ✅ **MERGED** (`7b82610f`) |
| **W4** uncapped arms + draw index | ✅ **CLOSED** (§5) |
| **W2** no hard-coded 32 downstream of `--m` | TODO — §9 merge |
| **W3** analyzer: `m_expected` 128/32, `b_ladder {1,2,4,8,16,32,64}`, `E` sub-read, S1/S2 strata, root bootstrap per §6, **and the `widening.*` verdict block at the exact spellings READ_RULE §2/§4/§5 address** | TODO — §9 merge. **`G-ARMS`, `G-COMPLETE`, `G-REPLICATE` and every `READOUT::widening.*` address are contingent on W3 being built to those spellings: a pre-run acceptance test (§9 step 4) must resolve every address on the smoke's output before the band claim.** |
| **W5** ONE merged `GATE_DISJOINT.json` with `comparisons:{<name>:{layers…, passed}}` over **four** comparisons + a `strata_root_overlap` int — the stock gate does two ARMS.json corpora and cannot read a rid-txt | TODO — §9 merge |
| **W6** `build_widening_corpus.sh`: parameterised copy of `build_tiearb2_corpus.sh` (5 phases, shadow-root step, empty-stand-in switches, absolute `RUN/` outputs, leg-manifest copy-back, `GEN_SMOKE.json`) | TODO — §9 merge |
| **W7** `verify_tier1_rust.py --out` | ✅ **DONE in this worktree** — the gate hard-coded `OUT_PATH` into the **closed** `tiearb2_stage2_20260817` run dir; re-running it for this campaign would have been a mid-run write to tracked artifacts of a closed run (REVIEW_R1 §2/§20) |
| PLAN_J §8(4) runtime `tiearb_capped_total` | **NOT built, NOT a gate** — a deploy-side rust counter behind the freeze; the offline witnesses (`ARMS.json::capped_at_4`, `POSITIONS_PLAN.json::n_positions_capped_at_4`) already satisfy the offline requirement |

---

## 9. Freeze and sequence (REVIEW_R1 §20 — the JCZ failure mode, pre-empted)

Mid-run writes to the main tree are what broke the JCZ cells. This run's code and its
prereg therefore land in a fixed order, and nothing under `scripts/tiletie/` is edited once
the run is live:

1. **All W-code in a worktree.** W2 · W3 · W5 · W6 · W7 are built and tested in a git worktree
   with `PYTHONPATH=<worktree>/src:<worktree>/engine`, never in the main tree.
2. **ONE quiet-window merge**, at a moment when no local run is live (census first), of all
   W-code in a **single commit**.
3. **`verify_tier1_rust.py --out`** points at `RUN/GATE_BITEXACT_HEAD.json`. Nothing this
   campaign runs may write into `measurement/tiearb2_stage2_20260817/` or any other closed
   run's directory.
4. **Pre-run acceptance test** (blind, outcome-free): run the smoke, then resolve **every**
   address named in READ_RULE §2/§4/§5 against the smoke's artifacts. Any address that does not
   resolve is fixed **now**, in code, not adjudicated around later.
5. **THEN** the blind `DESIGN.md` + `READ_RULE.md` commit to main, in one commit.
6. **THEN** the band claim, then generation, then scoring.
7. **`WORKERS.conf` lives OUTSIDE this frozen directory** (`../WORKERS.conf`). If it must be
   retuned mid-run, that is a numbered §7 deviation in the read-out, not a silent edit.

---

## 10. Manifests the run MUST write (self-describing, absolute paths under `RUN/`)

`corpus/CHAMP_GAMES_VERIFY.json` · `corpus/GEN_SMOKE.json` ·
`corpus/positions_{s1,s2}/{POSITIONS_PLAN.json,ARMS.json}` · `GATE_DISJOINT.json` ·
`GATE_BITEXACT_HEAD.json` · `GATE_DRAW.json` · `RUN_MANIFEST_{S1,S2}.json` ·
`SMOKE_MANIFEST_{S1,S2}_<judge>.json` · `legs/<judge>/<profile>/leg<N>/manifest.json`
(copied back from the share) · `verdicts/READOUT.{json,md}` ·
`verdicts/per_position_{s1,s2}.jsonl` · `verdicts/SEALED_G_REPLICATE.json` · `logs/`.

---

## 11. PLAN_J ask 6 — draft `I6` amendment text (**for owner approval; NOT enacted here**)

> **`I6-fullset-extrapolation-scope` — PROPOSED AMENDMENT.** Takes effect **only** if branch
> `X-PARTIAL`, `X-BELOW` or `X-FREE` fires, and only on the owner's approval recorded in
> DECISIONS.
>
> *In force since 2026-08-12:* the full-set ceiling is ≈1.40× the measured `J=4` headroom, an
> extrapolation through the S1a spread estimate, never a measurement.
>
> *Proposed replacement text:* "The ×1.40 multiplier is an order-statistic extrapolation over
> **raw** tied-set sizes (mean 8.55) applied **globally**. The arbiter prices **deduped** arm
> sets (mean 3.348 over all plies; 7.12 full-set at capped plies) and the cap binds on 18.07% of
> plies. Re-running §4.6's own machinery on the deduped population gives **≈1.244× at capped
> plies** and **≈1.087× globally**. Every VERDICT quoting ×1.40 is read with this correction.
> **The multiplier cancels out of `F`, so no prior verdict's branch, bound or claim moves.** The
> measured multiplier of record is `R_ora` = ⟨value, CI⟩ from
> `measurement/tiearb_widening_20260817/shared_run/verdicts/READOUT.json` (or, if the `R_ora`
> guard fired, `Δ_ora` = ⟨value, CI⟩ with the ratio unreported)."
>
> *Scope:* text-only, on the VERDICT riders + `governance/CLAIM_REGISTRY.csv` notes. No claim
> minted, retired or moved. `governance/PRODUCTION.yaml` untouched.

---

## 12. Owner decisions — rulings on record, and what remains open

**RULED 2026-08-18:** ① **FUNDED** at ≈1,174 worker-h / ≈26–29 h two-box wall (the J-FLOOR and
J-BUNDLED cheaper shapes are moot). ② The **N4 waiver above B=16 stays OPEN**, re-priced at the
flip decision; this run is **not** informational-only and **no branch may claim the waiver
extends** (rider `R6`). ③ **The phone is out of scope for this axis.**

**Still open, carried to Joshua:**
1. **Band `135000000000` + `136000000000` reserved** — and: is a BAND_REGISTRY row the right
   home for an **offline corpus substrate** band at all? (Stage-1b's was never registered.)
2. **Pre-approve the §11 `I6` amendment text** (PLAN_J ask 6), so an `X-PARTIAL`/`X-BELOW`
   landing does not stall on a governance decision.
3. **Ratify the §5 W4/`G-CAP` resolution** — instrument-draw-only scope, `G-CAP` retired,
   rider `I7-draw-scope` including its two REVIEW_R1 amendments. (`D-DRAW` is funded as part
   of the approved shape.)
4. **Accept the pre-registered blind spots:** a +0.02 residual on rung 2 reads as a null;
   1.400 vs 1.244 is not separable; `1.244` is unresolved at the top of the `sd_Δ` bracket;
   `X-FREE` is only reachable at a near-zero point estimate.
5. **PLAN_B §6 Q6** — prereg the `B=64` game-cell *trigger and design* now and size `n` from a
   committed formula after the offline read? (This DESIGN sizes **no** game cell.)
6. **Queue** — this queues behind the JCZ re-run; confirm the `c`-remeasure smokes get an
   **idle** box.

---

## 13. Review disposition — `REVIEW_R1.md`, all 21 defects

| # | class | fix, and where it now lives |
|---|---|---|
| 1 | voids-healthy-run | `G-DISJOINT` re-addressed to the **W5 merged** report (`comparisons.<name>.layers.<layer>.n_intersection`, `passed`, `strata_root_overlap`); W5 spec'd in §8; four comparisons + rid-txt handling named in §3 |
| 2 | voids-healthy-run | `verify_tier1_rust.py --out` **built in this worktree** (W7, §8); READ_RULE §2 now uses the real spellings `pass` / `n_playouts_compared` / `n_value_bit_identical` / `n_value_mismatch` / `legal_mask_cache` / `git_rev` |
| 3 | voids-healthy-run | `G-PREFIX` → `preflight.seeds.{ok, prefix_stable_at}`; conjunct is `ok == true` **and** `prefix_stable_at ⊇ {1,2,4,8,16,32,64,128}` at `m=128` (`{…,32}` at `m=32`) |
| 4 | voids-healthy-run | `G-UNCAPPED` restated as the **exact prefix+append identity** (the champion append is intended behaviour, ~16% of rids) |
| 5 | voids-healthy-run | §7 names `c_worker_secs_per_playout`; **HALT is one-sided** (costlier only) |
| 6 | ambiguous-branch | READ_RULE §4 gains catch-all row 5 **`W-INCONCLUSIVE`** = "none of 1–4" (covers the [2σ, 0.040) interval and degenerate/NaN se) |
| 7 | ambiguous-branch | READ_RULE §5 gains **`X-BELOW`** (resolved value below **both** predictions; triggers the `I6` amendment with measured `R_ora` as the number of record) |
| 8 | ambiguous-branch | Significance defined **once**, on the percentile bootstrap CI (§6, READ_RULE §3); the `2σ` conjunct is gone from both branch tables |
| 9 | ambiguous-branch | `X-FREE` reachability stated in §6 and **printed at the realized se** (READ_RULE §5) |
| 10 | ambiguous-branch | `R_ora` degenerate-denominator **guard** + committed `Δ_ora`-only sub-table (READ_RULE §5) |
| 11 | ambiguous-branch | `G-DRAW` identity corrected to `[arms_full[0]] + _seeded_cap(rid, arms_full[1:], 4)[0] == subset_j4` |
| 12 | wrong-number | §6 re-derives the se honestly: the `T=0.19` law is the **Δ(8→16)** law; `T` for Δ(16→64) is unmeasured; bracket `se ∈ [0.0179, 0.0200]`, `2σ ∈ [0.0357, 0.0400]`, **floor stays +0.040**, z-column recomputed |
| 13 | wrong-number | §6 restates 1.244 as "resolved at `sd_Δ ≤ 1.396`, **NOT** at 1.4"; added to §12.4's blind-spot list |
| 14 | clean | cost roll-up unchanged (+2.0 wh for the now-funded `D-DRAW` ⇒ ≈1,174) |
| 15 | process-risk | §4's literal command block **removed**; replaced by the W6 driver pointer + the graded-knob table |
| 16 | process-risk | §4/§10: absolute `RUN/` paths + leg-manifest **copy-back** to `RUN/legs/…` |
| 17 | process-risk | Per-leg fallbacks re-spelled `resolved_config.{world_seed_salt,m,legal_mask_cache}`; `G-LEAF` fallback `…leaf_hash.harness_leaf_hash` |
| 18 | process-risk | Per-judge smokes `SMOKE_MANIFEST_S1_<judge>.json`; CRN witness primary at `READOUT::widening.gates.crn.witness_kinds` (W3), per-record `jsonl` fallback |
| 19 | process-risk | `G-BAND` → `CHAMP_GAMES_VERIFY.json::{band_ok, seed_band, n_games_realized, n_out_of_band, n_duplicate_seeds}`; **`seeds_used` dropped** (its disclosure discipline restored) |
| 20 | process-risk | New **§9 "Freeze and sequence"**: all W-code via worktree in ONE quiet-window merge **before** the blind commit; `--out` redirect; `WORKERS.conf` moved to `../WORKERS.conf` |
| 21 | process-risk | §7 adds a **separate timed 10-game generation smoke** (`GEN_SMOKE.json`) — the judge smoke cannot price the generation leg |
| dim. | blindness | `G-REPLICATE` reports **PASS/FAIL + per-rung booleans only**; its z's go to `verdicts/SEALED_G_REPLICATE.json`, unread by a fixing session (READ_RULE §2/§7) |
| dim. | shared dependency | READ_RULE §2 states that `G-REPLICATE` conditions **both** rungs — **one** instrument check, **not** two independent confirmations |
| dim. | W4/I7 | Both amendments adopted into `I7` (§5): the **not-nested-in-`j`** warning, and the **dedupe-partition conditional**; `D-DRAW` funded as its reported magnitude |
| cos. | cosmetic | Salt join order corrected to `tiletie-cap \| <rid> \| 20260812` (§4) |

---

## 14. Contradictions between the authorities, and how this DESIGN resolves them

1. **n vs N_capped (material).** PLAN_B's n=1,350 yields ≈244 capped plies; PLAN_J §4 needs
   1,100 (floor 700); PLAN_J §8 meanwhile assumes 7,900 tied plies. **Resolved:** two
   root-disjoint strata off one game set — S1 exactly as PLAN_B specified, S2 at rung 3's own
   pre-registered power. Neither plan's n is silently rescaled.
2. **PLAN_J §8's cost is a ~6× under-estimate** (counts only ARB playouts; clair-puct is ~93%
   of the bill). **Resolved:** both judges priced on both strata (§7).
3. **`G-CAP` unsatisfiable** (PLAN_J §6 vs §2). **Resolved in §5.**
4. **PLAN_J §6's branch table mis-reads a result ABOVE 1.400** as "below the legacy
   prediction". **Resolved:** `X-PARTIAL` gains `upper(CI) < 1.400`; `X-ABOVE` added — and, per
   REVIEW_R1 §7, `X-BELOW` closes the symmetric hole underneath.
5. **Band.** CAMPAIGN ruling 4 `134e9` vs the DESIGN-time `135e9`. **Resolved:** `135e9` +
   `136e9` reserved, registry re-read at claim time.
6. **`champ_picks` cost.** PLAN_B 13.7552 vs PLAN_J 1.409 worker-s/position (the realized
   pipeline figure). **Resolved:** budget the conservative 13.7552; < 1% of the bill.
7. **Generation cost.** PLAN_B 990 worker-s/game vs F7d's ~440. **Resolved:** budget 990 and
   **measure it** with the §7 generation smoke.
8. **W4 already built** (PLAN_B §3 lists it outstanding). **Resolved:** closed (§5).
9. **PLAN_J §8(4)'s `tiearb_capped_total`** is a frozen-crate runtime counter. **Resolved:**
   not built, not a gate (§8).
10. **PLAN_B's own `se(Δ(16→64))` does not follow from its own variance law.** **Resolved in
    §6** — bracketed, with the unmeasured `T` named as unmeasured.
