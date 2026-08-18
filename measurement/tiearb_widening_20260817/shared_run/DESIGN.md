# TIE-ARBITER WIDENING — SHARED INSTRUMENT RUN, DESIGN (rungs 2 `B>16` + 3 `J>4`)

> **STATUS: BLIND PREREGISTRATION — revision R3.1, THE BINDING PAIR PENDING MERGE. NOT
> LAUNCHED. NOTHING RUN. NO OUTCOME STATISTIC OF THIS RUN EXISTS OR WAS READ.**
> No further review round: the closing pass passed rev R2 on everything but one defect (`B1`)
> and pre-approved its fix, which R3 applied verbatim along with cosmetics C1–C6. **R3.1 adds
> the dated pre-blind amendment section §0 (2026-08-18)** — the W-code builder's five
> ratification items — and the committed `STAGE1B_LADDER.json` those amendments create. The
> banked Stage-1b numbers in that file are adjudicated results of a **spent** corpus, already
> quoted in `PLAN_B_gt_16.md` §1; transcribing them is not a read of this run.
>
> ⚠️ **BLIND-ORDER REQUIREMENT — NOT YET SATISFIED.** This file and
> [`READ_RULE.md`](READ_RULE.md) were drafted and revised in an isolated **worktree** while
> the main tree is under a commit freeze. A worktree commit does **not** satisfy blindness.
> **Both files must be committed to the MAIN tree, in ONE commit, AFTER the §9 W-code merge
> and its step-4a acceptance test, and BEFORE the band is claimed and BEFORE one position is
> scored.** Until that commit exists, no leg of this run may start. Neither file may be edited
> after that commit except through a numbered `§0` pre-run amendment that leaves every branch
> condition byte-identical (the Stage-2 precedent).
>
> **Revision history.** **R1** folded in [`REVIEW_R1.md`](REVIEW_R1.md) — an independent
> adversarial review of the first draft (`e788b143`) that verified every witness address
> against the emitters and found 21 defects, four of them gates that **void a healthy run**.
> **R2 (this file)** folds in [`REVIEW_R2.md`](REVIEW_R2.md), which **FAILED R1**: 13 of the 21
> were verified genuinely closed, but the R1 edits introduced **nine new defects of the same
> address/sequencing class**, four blocking — concentrated in §9, where the acceptance test was
> sequenced before the corpus it audits, "resolving" the branch addresses would have computed
> outcome statistics pre-commit, the sealed z-file was simultaneously forbidden-to-open and a
> fallback the reader must open, and a new `git_rev` conjunct failed healthy runs twice over.
> Disposition of all 30: **§13**.
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

## 0. Pre-blind amendments — 2026-08-18 (rev R3.1)

**This is the legal window and it closes at the step-5 blind commit.** The W-code builder
delivered W3/W5/W6/W8 + fixtures + a `c_remeasure.py` emitter (39 tests; the 4a harness verified
end-to-end on fixtures) at `f26f4f29` in worktree `agent-ac2cd3b736f6e2bcc`, and surfaced five
items that need a prereg decision **before** the pair freezes. All five are decided here.
Nothing below moves a branch condition, a bar, a statistic or a power figure.

**0.A — `c_remeasure` key spelling: RATIFIED VERBATIM.** §7 obliged the run to write
realized-vs-committed `c` to `RUN_MANIFEST_S1.json` but named no key. The builder's spelling is
adopted as written:
`RUN_MANIFEST_S1.json::c_remeasure.{legs.{arb,if,generation}.{committed,realized,ratio,halt_fired},
halt_fired, failed_smokes, ok}`. Two documentation riders, neither of which changes the emitter:
(i) **the three legs do not share a unit** — `arb` and `if` are worker-s **per playout**,
`generation` is worker-s **per game** (from `GEN_SMOKE.json::worker_secs_per_game`); `ratio` is
`realized/committed` and is unitless, and **no comparison may be made across legs**;
(ii) `halt_fired` is **one-sided** — true iff some leg's `ratio > 1.25` — while a non-empty
`failed_smokes` (the §7 `null`/`0` case) is **not** a halt and **not** a cheap leg: it means
re-run that smoke, and the long leg does not start until a real number exists.

**0.B — `allow_null`: RATIFIED as a mechanism, membership AMENDED from two entries to four.**
READ_RULE §1.2 makes `null` a FAIL, which is right for every address except those where `null`
is the *correct* value. The closed list is now in READ_RULE §1.2. ⚠️ **The builder's list was
short by two, and both omissions would have failed a healthy run** — the same disease class this
pair has been fixing since `G-CAP`: `ci95_r_ora` is `null` in exactly the case `r_ora` is (the
degenerate-denominator guard), and `widening.j_rider.d_draw.*` is `null` until W9 runs. **Builder
action:** extend the `allow_null` list to the four entries in READ_RULE §1.2 and key each to its
discriminating witness. **The list is CLOSED at the blind commit — no address may be added to it
afterwards**, because "this null is fine too" is how a fail-closed rule becomes fail-open.

**0.C — `STAGE1B_LADDER.json`: CREATED, committed here, pre-blind.** `widening.stage1_replication.*`
needs the banked Stage-1b ladder as a committed reference, and the analyzer refuses to run
without `--stage1b-ladder` (fail-closed by construction — a good property, not a gate). The file
is transcribed **by script, not by hand**, from `measurement/tiearb2_20260816/READOUT.json`
(`b_ladder.pooled`; source sha256 recorded in the file) and carries the five rungs' `arb`/`se`
plus its `M=32 ⇒ E=16` context. These are **adjudicated, published numbers of a SPENT corpus**;
they are already quoted in `PLAN_B_gt_16.md` §1. Committing them **before** the blind commit is
precisely what makes `G-REPLICATE` a pre-registered comparison rather than a post-hoc one. Named
in §10 and in the `G-REPLICATE` row.

**0.D — `D-DRAW` gets an owner: NEW work item W9.** The owner-funded ≈2 wh probe had no work
item. **W9** replays each S2 capped ply in rust and calls
`carc_rs …tiearb_probe(j=4, salt="tiearb2-deploy-v1", ply=…)`, emitting `RUN/D_DRAW.json`
`{n_checked, n_agree, agreement_rate, n_unreconstructible, git_rev}`, which the analyzer surfaces
at `widening.j_rider.d_draw.*` via `--d-draw`. **No playouts, no outcome statistic.** It runs
**post-corpus, alongside step 4b**, and is `null` until then (READ_RULE §1.2). ⚠️ W9 measures the
very divergence `I7` declares out of scope: it is **reported under `I7` as the magnitude of that
conditional, adjudicates nothing, cannot move any branch, and may NEVER be used to correct,
reweight or re-scale `Δ_ora`.**

**0.E — the §9 step-2 merge has TWO sources.** Written into §9 step 2 so an executor cannot
merge half of it: W7 (`verify_tier1_rust.py --out`) lives in the **prereg** worktree
`agent-a43f00f675fd11b65`; W3/W5/W6/W8 + fixtures + `c_remeasure.py` live in the **builder**
worktree `agent-ac2cd3b736f6e2bcc` (`f26f4f29`).

**0.F — W2 is CLOSED AS VERIFIED, not a phantom work item.** The builder's claim was checked
against `scripts/tiletie/` at main HEAD by this session: every surviving `32` in the scoring path
is an **argparse default** (`run_tiletie.py:960`, `tier1_rust_leg.py:438`,
`oracle_score_pilot.py:1003`) or **docstring prose**; every consumer derives from `args.m` —
`b_ceiling` (`run_tiletie.py:216`), `b_ceiling_from_m` (`:930`), `n_playouts` (`:812`),
`preflight_seeds(salt, m)` and `preflight_m`. **Scope note:** `analyze_tiearb2.py`'s
`M_EXPECTED`/`B_LADDER` constants are still 32/`{1,2,4,8,16}`, but those are **W3's** deliverable
(§8), not W2's residue — do not close W3 on W2's evidence.

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
| `build_positions --exclude-rids` | `measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_all.txt` | same file |
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
(`/mnt/c/carc-shared/tiearb_widening_20260817/{s1,s2}/…`, per-record `records/<rid>.json` — one
JSON object per rid, **there is no `*.jsonl` leg file**), and the driver's
final phase **copies every leg `manifest.json` back** to
`RUN/legs/{s1,s2}/<judge>/walled/leg<N>/manifest.json` — the address the READ_RULE reads. Only
the **`tier1-greedy`** legs are addressed by any gate (the `clair-puct` legs are
`oracle_score_pilot` manifests and carry neither `resolved_config` nor `preflight.seeds`); copy
both back, gate on the ARB ones.

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
   exclusive tenant), run `run_tiletie --smoke` at production knobs — **`--smoke-n 20`
   (default is 5), `--arb-backend rust`, `--only-profiles walled`, and the stratum's own
   `--m`** — **four invocations: {S1 `--m 128`, S2 `--m 32`} × {`clair-puct`, `tier1-greedy`}**,
   each writing its own `--smoke-manifest` (`SMOKE_MANIFEST_{S1,S2}_<judge>.json`; one shared
   path would have the second smoke overwrite the first). Read
   **`…::c_worker_secs_per_playout`** — the Σ`elapsed_secs`/playout figure of record.
   ⚠️ **NOT `worker_secs_per_playout`**, which is the wall×W figure the emitter's own banner
   says not to cost from (inflated ~1.9×; a healthy smoke read at that key would HALT a healthy
   run — REVIEW_R1 §5). ⚠️ **`c_worker_secs_per_playout` is `None` when no per-position
   `elapsed_secs` was collected** (`c_sum = … if n_elapsed else None`). A `null` or `0` value is
   **not** a cheap leg and **not** a HALT: it is a **failed smoke** — re-run the smoke; the
   long leg does not start until a real number exists.
2. **Generation leg** (REVIEW_R1 §21 — the largest single line-item disagreement, 990 vs the
   ~440 worker-s/game implied by the F7d GEN row, and the judge smoke cannot see it): a
   **separate timed 10-game generation smoke** on the same idle box, at the §3 config and the
   GEN worker counts, recorded to `RUN/corpus/GEN_SMOKE.json::worker_secs_per_game`.
3. **HALT is ONE-SIDED.** Halt and re-price only if a realized `c` is **>25% COSTLIER** than
   committed. Cheaper is recorded, never a halt (the generation line is already ~2.25×
   conservative). A re-priced run above **1,500 worker-h** requires fresh owner authorization.
   Realized-vs-committed for all three legs is written by `c_remeasure.py` to
   **`RUN/RUN_MANIFEST_S1.json::c_remeasure.{legs.{arb,if,generation}.{committed,realized,ratio,halt_fired},
   halt_fired, failed_smokes, ok}`** (spelling ratified verbatim, §0.A). ⚠️ `arb`/`if` are
   worker-s **per playout**, `generation` is worker-s **per game** — `ratio` is unitless and the
   legs are **never compared to each other**.

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
| **W2** no hard-coded 32 downstream of `--m` | ✅ **CLOSED AS VERIFIED** (§0.F) — every surviving `32` is an argparse default or docstring prose; every consumer derives from `args.m`. Not a phantom item, and **not** evidence about W3's analyzer constants |
| **W3** analyzer | **DELIVERED** `f26f4f29` (builder worktree) — pending the §9 step-2 merge and the 4a acceptance run. See the **builder delta** below; **W3 additionally owns the `allow_null` handling of §0.B and the `--stage1b-ladder` reference of §0.C** |
| **W5** gate emitters (disjointness **and** draw) | **DELIVERED** `f26f4f29` — pending merge + 4a. See the **builder delta** below |
| **W6** `build_widening_corpus.sh`: parameterised copy of `build_tiearb2_corpus.sh` (5 phases, shadow-root step, empty-stand-in switches, absolute `RUN/` outputs, leg-manifest copy-back, `GEN_SMOKE.json`) | TODO — §9 merge. See the **builder delta** below |
| **W8** acceptance-test harness + fixtures (**NEW in R2**) | **DELIVERED** `f26f4f29`, 4a verified end-to-end on fixtures — pending merge. See the **builder delta** below |
| **W7** `verify_tier1_rust.py --out` | ✅ **DONE in the prereg worktree `agent-a43f00f675fd11b65`** — the gate hard-coded `OUT_PATH` into the **closed** `tiearb2_stage2_20260817` run dir; re-running it for this campaign would have been a mid-run write to tracked artifacts of a closed run (REVIEW_R1 §2/§20). **It is the SECOND source of the §9 step-2 merge (§0.E)** |
| **W9** `D-DRAW` probe (**NEW in R3.1**, §0.D) | TODO — runs **post-corpus, alongside step 4b**. Rust replay + `tiearb_probe(j=4, salt="tiearb2-deploy-v1", ply=…)` over the S2 capped plies → `RUN/D_DRAW.json::{n_checked,n_agree,agreement_rate,n_unreconstructible,git_rev}`, surfaced by the analyzer via `--d-draw` at `widening.j_rider.d_draw.*`. No playouts, no outcome statistic; `null` until it runs; **adjudicates nothing and may never correct, reweight or re-scale `Δ_ora`** |
| PLAN_J §8(4) runtime `tiearb_capped_total` | **NOT built, NOT a gate** — a deploy-side rust counter behind the freeze; the offline witnesses (`ARMS.json::capped_at_4`, `POSITIONS_PLAN.json::n_positions_capped_at_4`) already satisfy the offline requirement |

### Builder delta — what changed between rev R1 and rev R2 (self-contained; diff your work against this)

A builder implementing W3/W5/W6 against **rev R1** must apply these five changes. Nothing else
in the W-scope moved.

1. **W3 owns the sealed file and the print-suppression contract (new).** W3 writes
   `RUN/verdicts/SEALED_G_REPLICATE.json` — the `G-REPLICATE` z's — **write-only**: nothing in
   the READ_RULE addresses it, no gate resolves against it, and the harness must not print its
   contents. W3's `READOUT::widening.stage1_replication` block carries **booleans only**
   (`pass`, `per_rung_inside_envelope`, `arb16_convicts`, `envelope_inflation`) and
   `G-REPLICATE` has **no fallback**: a missing or `null` boolean block is a FAIL, and the fix
   is in W3, not in the seal. W3 also owns the **print-suppression contract**: on any gate
   FAIL the report emits gate inputs only — no `arb`, `ora`, `Δ`, CI or per-position statistic
   — and `G-REPLICATE`'s inputs at that moment are the booleans, never the z's.
2. **W5 owns `GATE_DRAW.json` as well as `GATE_DISJOINT.json`** (in R1 the draw gate had no
   owner). `GATE_DRAW.json::{n_checked,n_mismatch,ok,git_rev}`, computed by re-running
   `build_positions._seeded_cap(rid, arms_full[1:], 4)` and comparing
   `[arms_full[0]] + kept == subset_j4` per rid, on **both** strata.
3. **`GATE_DISJOINT.json` carries FIVE comparisons, not four.** All three layers
   (`a_root_id`, `b_rid`, `c_position_digest`) on each of the **four ARMS-vs-ARMS**
   comparisons — `s1_vs_tiletie0812`, `s1_vs_tiearb2_0816`, `s2_vs_tiletie0812`,
   `s2_vs_tiearb2_0816` — **plus `s1s2_vs_exclude_rids`, on which `b_rid` is the ONLY layer**,
   against `measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_all.txt`, which is a rid text file
   with no root and no digest layer (emitting three layers there, or requiring them, fails a
   healthy run) and which the stock `load_rids` raises on. Shape:
   `{passed, comparisons:{<name>:{layers:{…:{n_intersection}}, passed}}, strata_root_overlap}`.
4. **Every per-leg address is bound to `tier1-greedy`.** `resolved_config.*` and
   `preflight.seeds.*` exist **only** on `tier1_rust_leg` manifests; the `clair-puct` legs are
   `oracle_score_pilot` manifests and carry neither. W6's copy-back must therefore place ARB
   leg manifests at `RUN/legs/{s1,s2}/tier1-greedy/walled/leg<N>/manifest.json` (copy the IF
   legs too, but no gate reads them). The per-record CRN fallback is
   `SHARE/{s1,s2}/tier1-greedy/walled/leg<N>/records/<rid>.json` — **one JSON object per rid;
   there is no `*.jsonl` leg file.**
5. **The acceptance test is W8, and it splits 4a/4b with a presence/type-only contract.**
   A harness that walks a committed address list and, for each address, reports
   **`resolved` / `UNRESOLVED` plus the JSON type of the value — and prints no value, ever.**
   It resolves **primary AND fallback independently** (a fallback that is only exercised the
   day it is needed is unaudited), across **both strata**, over every address named in
   READ_RULE §2/§4/§5 **and** in §7's `c`-remeasure obligation (including `GEN_SMOKE.json` and
   the realized-vs-committed `c` block). See §9 steps 4a/4b for what runs when.
   **W8's deliverables are the harness AND the fixture set it audits against**: a committed
   `ARMS.json` fixture (a handful of rids incl. one capped, one with the champion append, one
   `all_transposition`), a `POSITIONS_PLAN.json` fixture, and a `per_position` row fixture for
   each stratum — enough for the 4a schema pass to resolve the `READOUT::widening.*`,
   `GATE_DISJOINT`, `GATE_DRAW`, `POSITIONS_PLAN`/`ARMS` spellings **before any real corpus
   exists**. The fixtures carry synthetic values and are never a data source for any statistic.

---

## 9. Freeze and sequence (REVIEW_R1 §20 — the JCZ failure mode, pre-empted)

Mid-run writes to the main tree are what broke the JCZ cells. This run's code and its
prereg therefore land in a fixed order, and nothing under `scripts/tiletie/` is edited once
the run is live:

1. **All W-code in a worktree.** W2 · W3 · W5 · W6 · W7 · W8 are built and tested in a git
   worktree with `PYTHONPATH=<worktree>/src:<worktree>/engine`, never in the main tree.
2. **ONE quiet-window merge**, at a moment when no local run is live (census first), of all
   W-code in a **single commit** — **and the W-code has TWO SOURCES (§0.E). Merging one is
   merging half the run:**
   - worktree **`agent-ac2cd3b736f6e2bcc`**, commit **`f26f4f29`** — W3 (analyzer) · W5 (gate
     emitters) · W6 (corpus driver) · W8 (acceptance harness + fixtures) · `c_remeasure.py`;
   - worktree **`agent-a43f00f675fd11b65`** — **W7** (`verify_tier1_rust.py --out`). Take the
     `scripts/tiletie/verify_tier1_rust.py` change **only**; the prereg pair,
     `STAGE1B_LADDER.json` and the `REVIEW_R*.md` files do **not** ride in this merge — they are
     the step-5 blind commit.

   **This commit is the `git_rev` of record** for `G-BITEXACT@HEAD` (READ_RULE §2). ⚠️ **Its sha is recorded in TWO places, both created no
   later than the step-5 blind commit: (i) the blind commit's own message, and (ii)
   `RUN/W_CODE_MERGE.txt`, committed as part of that same blind commit.** It is **never**
   recorded by editing this DESIGN or the READ_RULE after step 5 — a post-blind edit to the
   frozen pair is exactly the move the freeze exists to forbid, and a `git_rev` conjunct whose
   referent is written after the fact is not a pre-registration.
3. **`verify_tier1_rust.py --out`** points at `RUN/GATE_BITEXACT_HEAD.json`. Nothing this
   campaign runs may write into `measurement/tiearb2_stage2_20260817/` or any other closed
   run's directory. ⚠️ This gate is produced **here, at step 2's HEAD**, while the blind commit
   is step 5 — so the run's own `git_rev` is necessarily *later*, and the two emitters use
   different formats (40-char vs `--short`). READ_RULE's conjunct is written for that reality;
   a literal equality would fail every healthy run (REVIEW_R2 §N1).
4. **4a — PRE-COMMIT acceptance test (corpus-free).** Run the **four smokes** of §7.1
   ({S1 `--m 128`, S2 `--m 32`} × both judges), then run **W8** over: every address that a
   smoke, a leg manifest or a static fixture can answer — the `SMOKE_MANIFEST_*`,
   `RUN/legs/{s1,s2}/tier1-greedy/…/manifest.json` (`resolved_config.*`, `preflight.seeds.*`),
   the `RUN_MANIFEST_*` preflight keys — **plus a static schema audit of W3/W5/W6 outputs
   against committed fixtures** (a fixture ARMS.json/plan/per_position row set), which is how
   the `READOUT::widening.*`, `GATE_DISJOINT`, `GATE_DRAW` and `POSITIONS_PLAN`/`ARMS` spellings
   get audited before any real corpus exists. **Mechanism: key presence + JSON type ONLY. No
   value is computed, printed or stored** — W3 never runs on real corpus positions here, and
   `SEALED_G_REPLICATE.json` is not brought into existence (REVIEW_R2 §N3).
5. **THEN** the blind commit to main, in ONE commit: `DESIGN.md` + `READ_RULE.md` +
   `STAGE1B_LADDER.json` + `W_CODE_MERGE.txt` (carrying step 2's sha) + the `REVIEW_R*.md`
   provenance files.
6. **THEN** the band claim, then the corpus build (generation → census → positions → gates).
7. **4b — POST-CORPUS, PRE-SCORING acceptance test.** Re-run **W8** against the **real** corpus
   artifacts, which exist now and carry **no outcome statistic**: `CHAMP_GAMES_VERIFY.json`,
   `GATE_DISJOINT.json` (incl. `strata_root_overlap` and all five comparisons),
   `POSITIONS_PLAN.json`/`ARMS.json` on both strata, `GATE_DRAW.json`, `GEN_SMOKE.json` and
   §7's realized-vs-committed `c` block. **Primary AND fallback independently, both strata,
   presence/type only.** Any `UNRESOLVED` is fixed in code **before the first scoring leg** —
   which is the last moment a fix is free. (The remaining `READOUT::widening.*` and
   `per_position_*.jsonl` addresses are audited by 4a's fixture schema pass; they cannot exist
   before scoring by construction.)
8. **THEN** scoring: S1, then S2.
9. **`WORKERS.conf` lives OUTSIDE this frozen directory** (`../WORKERS.conf`). If it must be
   retuned mid-run, that is a numbered §7 deviation in the read-out, not a silent edit.

---

## 10. Manifests the run MUST write (self-describing, absolute paths under `RUN/`)

`corpus/CHAMP_GAMES_VERIFY.json` (+ `…_TOPUP.json` iff the blind top-up was exercised) ·
`corpus/GEN_SMOKE.json` · `W_CODE_MERGE.txt` (the §9 step-2 sha, committed with the blind pair) ·
**`STAGE1B_LADDER.json`** (the committed `G-REPLICATE` reference, §0.C — written pre-blind,
passed to the analyzer as `--stage1b-ladder`, which refuses to run without it) ·
**`D_DRAW.json`** (W9, §0.D — `null` until it runs) ·
`corpus/positions_{s1,s2}/{POSITIONS_PLAN.json,ARMS.json}` ·
`GATE_DISJOINT.json` · `GATE_BITEXACT_HEAD.json` · `GATE_DRAW.json` ·
`RUN_MANIFEST_{S1,S2}.json` · `SMOKE_MANIFEST_{S1,S2}_<judge>.json` ·
`legs/{s1,s2}/<judge>/<profile>/leg<N>/manifest.json` (copied back from the share; **only the
`tier1-greedy` legs are addressed by any gate** — §8 builder delta 4) ·
`verdicts/READOUT.{json,md}` · `verdicts/per_position_{s1,s2}.jsonl` · `logs/` ·
`verdicts/SEALED_G_REPLICATE.json` — **WRITE-ONLY**: not an address, never opened to answer a
gate, never opened by a fixing session (READ_RULE §7).
Per-record leg output stays on the share as `records/<rid>.json` (one object per rid; there is
no `*.jsonl` leg file).

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

## 13. Review disposition

### 13.C — closing pass on rev R2 (verdict: FAIL on one defect, fix pre-approved)

Everything else closed: the `git_rev` conjunct was walked step-by-step and passes under both
readings, the 4a/4b coverage matrix verified complete, the `N14` broadening ruled *"strictly
better than the letter"*, `I7` again named the strongest part of the document.

| # | fix, and where it now lives |
|---|---|
| **B1** (blocking) | `G-BAND`'s top-up clause held `CHAMP_GAMES_VERIFY_TOPUP.json` to *"the above"*, **including `n_games_realized ≥ 850`** — but the top-up is pre-licensed at **≤200 games**, so a healthy run that exercises the pre-licensed clause **voids**. Replaced verbatim: each file is checked against **its own** committed range (`[135000000000,135000000849]` / `[136000000000,136000000199]`) for `band_ok`/`seed_band`/`n_out_of_band == 0`/`n_duplicate_seeds == 0`; **the BASE file alone carries `n_games_realized ≥ 850`**, the top-up carries the increment; never one invocation over a widened band |
| C1 | last stale *"per-record `jsonl`"* prose in §4 → `records/<rid>.json` |
| C2 | READ_RULE §7's `DESIGN §9.7` cross-reference → **§9, item 9** (post-renumber) |
| C3 | `G-DISJOINT`'s quantifier tightened in **both** documents: three layers each on the four ARMS-vs-ARMS comparisons; **`b_rid` only** on `s1s2_vs_exclude_rids` |
| C4 | the **fixture set** (ARMS.json / plan / per_position row fixtures, per stratum) named as an explicit **W8 deliverable** in the builder delta |
| C5 | §9 step 2: the W-code merge sha is recorded in the **blind commit message** *and* **`RUN/W_CODE_MERGE.txt`** (committed with the blind pair), **never** by a post-blind edit to the frozen pair; `W_CODE_MERGE.txt` added to §10 |
| C6 | rung-2 row 5 prose now names the **level/increment residue** — `Δ` significant and above the floor while `arb(64) ≤ arb(16)` — and requires the read-out to report the disagreement as an instrument question |

### 13.B — `REVIEW_R2.md` (closing review of rev R1; verdict FAIL), all 14 items

R2 verified 13 of R1's 21 fixes genuinely closed and called `I7` the strongest part of the
document; the nine new defects below are all in the same address/sequencing class R1 was
supposed to have retired. **All adopted; none rejected.** The reviewer's minimal fixes are
taken as written except where noted.

| # | class | fix, and where it now lives |
|---|---|---|
| N1 | blocking | `G-BITEXACT@HEAD`'s `git_rev` conjunct rewritten: **"the §9 step-2 W-code merge commit or a descendant whose cumulative diff touches nothing under `scripts/tiletie/`, `src/`, `engine/`, `rust/`", compared by `startswith` on the 7-char short form.** A literal equality failed twice over — 40-char `rev-parse HEAD` vs `--short`, and the gate is produced at step 3 while the run records step-5+ HEAD. §9.3 states the sequencing that makes it so |
| N2 | blocking | §9 step 4 **split into 4a (pre-commit, corpus-free: four smokes + static fixture schema audit) and 4b (post-corpus, pre-scoring: full address resolution against real corpus artifacts, which carry no outcome statistic)**. Blind commit stays step 5; 4b sits between corpus build and first scoring leg. **Two smokes per judge** (S1 `--m 128`, S2 `--m 32`) so the S2-side gates are covered |
| N3 | blocking | The acceptance test now has an explicit mechanism: **key presence + JSON type ONLY, no value computed, printed or stored** (§9.4, §8 builder delta 5). W3 never runs on real corpus positions pre-commit and `SEALED_G_REPLICATE.json` is not forced into existence |
| N4 | blocking | The sealed file is **not an address**: `G-REPLICATE` gets **no fallback** (missing boolean block = FAIL), and the seal is described in READ_RULE §7 as **write-only**. **N4b:** W3 now **owns** writing it and owns the print-suppression contract (§8 builder delta 1) |
| N5 | required | `EXCLUDE_RIDS_all.txt` restored to every binding surface: **five** comparisons in `G-DISJOINT` (the fifth is rid-layer only) and `--exclude-rids` back in §4's knob table |
| N6 | required | READ_RULE §2 preamble restores **"S1 gates bind BOTH rungs"**, and `G-SALT`/`G-CRN` are extended to `{S1,S2}` — evaluated separately on each stratum, both must pass (S2 is a separate corpus and a separate launch; nothing transfers) |
| N7 | required | **`<judge>` bound to `tier1-greedy`** on all four per-leg addresses; `G-PREFIX`'s primary likewise, with a sentence stating prefix stability is witnessed **once on the ARB leg** as a property of the shared seed derivation. `clair-puct` legs are `oracle_score_pilot` manifests and have neither `resolved_config` nor `preflight.seeds` |
| N8 | required | Per-record CRN fallback re-pathed to `…/records/<rid>.json` (one object per rid) in **both** documents |
| N9 | required | `GATE_DRAW.json` assigned to **W5** (§8 builder delta 2) |
| N10 | cosmetic | Adopted: `c_worker_secs_per_playout` `null`/`0` is a **failed smoke** (re-run), not a cheap leg and not a HALT (§7.1) |
| N11 | cosmetic | Adopted: `--smoke-n 20` named explicitly (default is 5) |
| N12 | cosmetic | Adopted: the top-up disjunct becomes a **second `verify-champgames` invocation** writing `CHAMP_GAMES_VERIFY_TOPUP.json`, both files checked against their own `seed_band` — never one widened band |
| N13 | cosmetic | Adopted: READ_RULE §3 states the +0.040 floor is **deliberately a point test on `Δ`**, stated separately from significance so neither can be traded for the other |
| N14 | cosmetic | Adopted, slightly beyond the letter: row 1 broadened to `lower(CI95(arb_64)) ≤ 0` (total, and it captures the negative case), **plus a mandatory print** labelling a significantly-negative level a **mechanism anomaly** rather than a "noisy" reading |
| — | note | The R1 `--out` change adds one benign key (`out_path`) to the emitted gate JSON, recorded here as the reviewer asked |

### 13.A — `REVIEW_R1.md`, all 21 defects

| # | class | fix, and where it now lives |
|---|---|---|
| 1 | voids-healthy-run | `G-DISJOINT` re-addressed to the **W5 merged** report (`comparisons.<name>.layers.<layer>.n_intersection`, `passed`, `strata_root_overlap`); W5 spec'd in §8. ⚠️ R1 wrote **four** comparisons — **superseded by N5: five**, the fifth being the rid-txt at rid layer only |
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
| 18 | process-risk | Per-judge smokes; CRN witness primary at `READOUT::widening.gates.crn.witness_kinds` (W3), per-record fallback. ⚠️ R1's spellings **superseded**: `SMOKE_MANIFEST_{S1,S2}_<judge>.json` (N2 — both strata) and `records/<rid>.json`, not `*.jsonl` (N8) |
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
