# FPU DOSE-LADDER — BRACKETING THE ENDPOINT — READ RULE

> **STATUS: FROZEN** (2026-08-30). This document and [`DESIGN.md`](DESIGN.md) are **the pair**, and
> the pair is law. ⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every bar, every gate,
> every branch and every prohibition below exists **before any game does**.
>
> If `analyze_ladder.py`, `screen_lib.py` or `run_cells.sh` disagrees with this document,
> **it is the code that is wrong.**
>
> ⚠️ **After game 1 there is no amendment route.** The only one that exists is: freeze the verdict as
> it stands, record the defect, and get the **OWNER** to authorise a re-read of the SAME archive
> under a named, minimal, single-clause correction. ⭐ The parent round had to use it (`FPU-A1`), and
> §4.1 of this file is the fix that makes the same amendment unnecessary here.
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.**
> `analyze_ladder.py --selftest` is `PASS`. ⚠️ The **golden gate has NOT been run** — it is a LAUNCH
> PRECONDITION and `run_cells.sh` refuses without it (DESIGN §9).

**Four rungs, four bands, one dose each:** `CELL_FPU005` (`0.05`, `164e9`, local) ·
`CELL_FPU010` (`0.10`, `165e9`, local) · `CELL_FPU015` (`0.15`, `166e9`, laptop) ·
`CELL_FPU030` (`0.30`, `167e9`, laptop). Each `n=800` deck-paired (400 seat-balanced decks × 2)
against the **UNMODIFIED CHAMPION** at **fair PIMC `k16 × 1376 = 22016` both sides**, tie-arbiter
**OFF** both sides, knob on the **candidate only**.

⚠️ `W` is **throughput-only**. Games are bit-identical at any `W`, and **no gate in this pair reads a
clock**.

---

## 1. THE STATISTIC

**Per rung, PRIMARY:**

```
D(deck) = ( diff(deck, a_seat=0) + diff(deck, a_seat=1) ) / 2
M       = mean over decks appearing in BOTH seatings
SE      = sample sd (ddof=1) / sqrt(n_paired)
z       = M / SE
UB95    = M + 2*SE          LB95 = M - 2*SE
```

`diff` is the harness's own final-score margin, **candidate minus opponent, in POINTS**.
**`M > 0` ⇒ the CANDIDATE won.** A deck missing a seating is **DROPPED**, never defaulted to zero,
and surfaces at `G-DECKS` and `G-N` (§4.1).

⛔ **Adjudicated AGAINST ZERO, at the rung's OWN REALIZED SE.** The sizing constant
`sigma_D = 13.81` (DESIGN §3) is **power arithmetic only** and is ⛔ **never a denominator in a
branch test.**

⛔ **`n_paired` IS IN DECKS, NOT GAMES.** A paired `n=800` rung yields at most **400 decks**. Every
bar below is in **pts/deck**.

### 1.1 THE SECONDARY — elo, and it is NOT A BAR IN THIS ROUND

`elo` is reported for every rung with its own **deck-paired** CI, **on every branch**.

⚠️⚠️ **THERE IS NO ELO BAR HERE.** The adoption bar is `+1.5 pts/deck` on the deck-paired margin, and
`+1.5 pts/deck` has **no exchange rate into elo that this round measures**. What is printed beside
the elo is the instrument's **2σ RESOLUTION** — `±17.4` elo, deck-paired at 800 games — which is a
statement about what the instrument can see, never a threshold anything must clear.

⭐ **R4's footing, carried:** 800 games are 400 decks × 2 seatings, so pairing scales the sigma by
`1/√2`. The textbook binomial figure is the **unpaired** one (`±24.6` at 2σ); quoting it beside a
paired quantity compares two different rulers. Every emitted field **names its footing**
(`elo_sig_1sigma_paired` / `elo_sig_1sigma_unpaired`), and the unlabelled key is gone on purpose.

⭐ **A disagreement between the margin and the elo is DISCLOSED, never arbitrated.** The margin
carries the branch.

### 1.2 `RECON` — the witness

`screen_lib.paired_margin()` is a **deliberately independent re-implementation** of
`eval_fair_puct._paired_z` — not an import of it (an imported one would agree by construction and
witness nothing) — accumulated with `math.fsum` rather than `sum`. It recomputes
`paired_mean_margin`, `paired_z`, `n_paired`, `winrate` and `elo` **from the raw records** and
compares against `summary.json` at rel `1e-6` / abs `1e-9`.

⛔ **It can only VOID, never move, a number.**

### 1.3 ⛔⛔ THE CONTEXT ROWS ARE A DESCRIPTIVE OVERLAY ONLY

The parent round's realized `0.2` (`+2.951 ± 0.683`, `z +4.32`, band `155e9`) and `0.4`
(`+0.754 ± 0.715`, band `156e9`, `F-UNRESOLVED` amended) — and the older neural-era `+45.4` / `+31.4`
elo screens and the M3 curve — are **context in the read-out and nothing else**.

⛔ **NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT. NEVER INTERPOLATED AGAINST A RUNG.**
CL-068 measured **1.8–2.2× over-dispersion on merely CROSS-BAND contrasts**, in both the elo and the
deck-paired-margin statistics, with an identity control exonerating the harness and the "different
decks" explanation arithmetically excluded (the per-deck SEM already prices the deck draw). The
`0.2` / `0.4` rows are cross-band. The neural rows are cross-band **and** cross-era **and**
cross-agent **and** cross-budget. There is no arithmetic that combines any of them with this round's
numbers.

⭐ What the overlays legitimately did was fix **which doses** this round asks about and **what bar is
worth paying for** (DESIGN §2.1, §4.2). Choosing where to look is a **design act**; combining
readings is a statistical one. That use is spent **before any number of this round exists**, and no
branch reaches back into it.

---

## 2. THE RUNGS

| rung | box | dose | band | role |
|---|---|---|---|---|
| `CELL_FPU005` | local | **0.05** | `164000000000` | ⭐ the low bracket point — and ⛔⛔ the round's own liveness worry (DESIGN §2.2) |
| `CELL_FPU010` | local | **0.10** | `165000000000` | ⭐ the middle bracket point |
| `CELL_FPU015` | laptop | **0.15** | `166000000000` | ⭐ the near bracket point, adjacent to the fired endpoint |
| `CELL_FPU030` | laptop | **0.30** | `167000000000` | ⭐ the interior point above |

Knob on the **candidate only**. Opponent structurally unmodified — ⛔ **no `--cand-fpu-reduction`
reaches the opponent side, ever**; `--c-puct` and `--tau-p` are **never** used at all (they build
BOTH sides, see `G-TWOSIDED`); and there is **no `--cand-c-puct`** anywhere in this round's launcher,
because no rung varies `c_puct`.

⚠️ **The tie arbiter is OFF on both sides.** `PRODUCTION.yaml` has carried `B=64` since 2026-08-20;
DESIGN §2.3 states the reason and the price, and **that price rides on every branch below.**

---

## 3. THE KNOB — FROZEN SEMANTICS

| `fpu_reduction` | meaning |
|---|---|
| `None` / unset | the NeuralMCTS **legacy optimistic** `q = 0.0` for unvisited children — **the champion, bit-for-bit** |
| a value `r` | an unvisited child scores `q = parent.Q − r` (pessimistic FPU) |

⚠️ **`0.0` IS NOT `None`.** `Some(0.0)` takes the `node_q − 0.0` branch — the **parent's Q** — while
`None` takes the flat `0.0` branch. The two are deliberately distinguished end-to-end and never
coerced. ⛔ A gate that read `null` and `0.0` as the same value would be unable to tell the champion
from a live rung. ⭐ **This is why `0.05` is a real dose and not "approximately the champion".**

⚠️ `parent.Q` is already in `node.player_to_move`'s POV — the same POV the unvisited child is scored
in — so **no sign flip is applied**. `mcts.py:1225` and `carc_core::search/mod.rs:816` implement the
identical rule; the two backends **mirror**.

---

## 4. THE GATES

⛔ **ABSENT IS FAIL. Never a skip, never a default.** Every gate resolves across **both** documents —
`config.*` in **`manifest.json`**; statistics in **`summary.json`**, which carries **no config block
at all** (IS-D1) — and prints **which document and which address** answered. A value found at **no**
address is `ABSENT`, and `ABSENT` is `FAIL`.

⛔ **A FAIL ON ANY GATE MAKES THAT RUNG `U-VOID-INSTRUMENT`**, checked **first** in the branch table.
⭐ **The other rungs' own readings are UNAFFECTED** — four separate questions on four separate bands.
⛔ **But the ROUND VERDICT is blocked** (§5.4): a voided rung is not a bound, so `LADDER-DEAD` cannot
be declared over it.

| id | asserts | address | fires on |
|---|---|---|---|
| ⭐⭐ `G-FPU` | `config.cand_search.fpu_reduction` equals this rung's **frozen dose** EXACTLY (`null` distinguished from ABSENT), **and** `config.cand_search.c_puct` is `null` | `manifest:config.cand_search.*` | ⛔⛔ **THE INVERTED-LIVENESS GATE.** A harness predating the fpu plumbing emits no `cand_search` at all, and its candidate was **dose-blind by construction** — a rung over it is champion-vs-champion, moves no leaf hash, sits inside `G-SAT`'s rail and reads as a clean credible null. `ABSENT` is `FAIL`. ⭐ The `c_puct` half is a second witness against a stray override |
| ⭐⭐ `G-TWOSIDED` | the **RESOLVED** configs of the two sides: candidate carries the frozen dose, opponent carries `fpu_reduction: null`, and `c_puct` is EQUAL across the sides and equal to the champion's `1.5` | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⛔ the **second, independent** witness. `G-FPU` proves the dose was *requested*; this proves it *landed*, on the candidate and **nowhere else**. ⚠️ It is **weaker than a play-derived witness** (a PUCT constant has no fire counter, unlike the arbiter's `G-PHI` or S1's `jr_expansions` census) — the play-derived evidence in this family is the **golden gate**, and DESIGN §9 says so rather than overclaiming this gate |
| `G-SINGLEVAR` | `fpu_reduction` DIFFERS across the two sides and equals the frozen dose on the candidate; **every other** alias is EQUAL | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⚠️ The opponent's knobs live one level down under `champ_cfg`, and its **budget** lives one level up under `config.opponent.*` — a gate written from the design rather than from a real manifest voids every healthy rung |
| `G-ARB-OFF` | **no** tie-arbiter armed anywhere in the manifest, either side (full walk) | `manifest` (full walk) | ⚠️ This DEVIATES from the deployed champion and the price rides on every branch (DESIGN §2.3) |
| `G-LEAF` | ⭐ **BOTH SIDES EQUAL** `a36d2e15a3b3d71d`, and `config.cand_leaf_cfg.v29_meeple_curve == curve125` | `manifest:config.{cand,opp}_leaf_hash` | `fpu_reduction` is not a leaf term, so differing hashes mean a misconfigured rung — and a moved-hash check can **never** prove this surface live, which is why `G-FPU`/`G-TWOSIDED` exist |
| `G-BAND` | `config.band_seed_start` == this rung's **own** frozen band; `n_decks` and `seatings_per_deck == 2` match | `manifest:config.*` | any deviation |
| ⭐⭐ `G-DECKS` | (a) every realized seed inside **this rung's own** range — **HARD**; (b) decks played at ONE SEAT ONLY are **REPORTED**, and void only at or above **2 % OF GAMES**; (c) `n_common >= 80 %` of 400 — **HARD**; (d) this rung's range does not intersect any other rung's — **HARD** | raw `seed*_a*.json` | ⛔ **THE `FPU-A1` FIX** — see §4.1 |
| ⭐⭐ `G-N` | `n` and `n_failed` present; the **accounting identity** `n + n_failed == 800`; `n_failed / 800 < 2 %`; `n_common >= 80 %` of 400 | `summary.json` | ⛔ **THE `FPU-A1` FIX** — see §4.1 |
| `G-BUDGET` | both sides `(k_dets, sims_per_det, total_sims) == (16, 1376, 22016)` **and the product multiplies out** | `manifest:config.{champion,opponent}.*` | any asymmetry, and a **stale 11008** rung — which would grade the dose against a superseded champion while every other gate passed |
| `G-PROD` | ⭐ **LAUNCHER-SIDE, PRE-COMPUTE.** the frozen budget == `governance/PRODUCTION.yaml` `champion.fair_deploy` | `governance/PRODUCTION.yaml` | ⛔ Hard abort for a real rung and for the smoke; loud-but-continue for `--dry-run`, which spends nothing. **The fix is the bundle sync, never an edit to the pair** |
| `G-EXACT` | both sides `exact_k == 2` and `mode == "marginalized"` | `manifest:config.endgame.*` | K=3/4 are clairvoyant-only |
| `G-RULES` | `rules_profile.name == "fixed_v1"`, `r9_env_ok` and `r9_env_observed` both `true` | `manifest:rules_profile.*` | R9 not latched. ⚠️ R9 is env-latched at **import** |
| `G-BACKEND` | `name == requested == "rust"`, `mixed_builds false`, `converted_sides == {candidate, opponent}` | `manifest:config.backend.*` | ⚠️ `fpu_reduction` is threaded on BOTH backends, so a python leg would not be dose-blind. It is refused anyway: the champion of record plays on rust, and a mixed-backend round is not one round |
| `G-WHEEL` | `carc_rs_build` and `carc_rs_binary_sha` present; `mixed_builds false` | `manifest` | ⚠️ `carc_rs_version` is permanently `"0.1.0"` and is **NOT** a discriminator |
| `G-WHEEL-SAME` | ⭐ **ROUND-LEVEL.** `carc_rs_binary_sha` identical across every rung **on a box** | `manifest` | a changed wheel mid-round. ⚠️ the sha is **box-local** and is never compared across boxes. ⛔ **A FAIL VOIDS EVERY RUNG** |
| `G-REV` | (i) each manifest's short `code_rev` **names** its own box's `PINNED_SRC_REV`; (ii) `SRC_CLEAN.jsonl` records the code paths clean at every boundary; (iii) ⭐⭐ **the cross-box clause** via `screen_lib.cross_box_rev_gate()` — the pins **agree** as 40-hex and every emitted rev **canonicalizes to that pin** | manifests + each box's `PINNED_SRC_REV` + `SRC_CLEAN.jsonl` | ⛔⛔ **THE ROUND'S PRIMARY PROVENANCE RISK.** The fpu plumbing is **python-only**, so a box on stale source serves a **dose-free candidate** with a healthy `carc_rs_build`, a healthy binary sha and the correct leaf hash. ⛔ **NEVER by comparing one box's emitted short rev to the other's** — the IS-A1 defect |
| `G-BLIND` | `BLIND_COMMIT` is a 40-hex sha, stamped into every adjudicated manifest and agreeing across rungs | `manifest:BLIND_COMMIT` | a read that was not blind |
| `G-HOST` | the manifest's `host` matches this rung's frozen box (substring test on a normalised hostname — `laptop`/`laptop-wsl`/`laptop-pop`/`pop-os` are one machine) | `manifest:host` | a rung run on the wrong box. ⚠️ the real protection is structural (disjoint `--out-subdir`s ⇒ no shared claims to race over); this proves the **sealing pass** ran on the assigned box |
| `G-SAT` | `0.35 <= winrate <= 0.65` | `summary:winrate` | a **RAIL** check, not a strength bar: both sides run the same search on the same leaf at the same budget, so a winrate outside this window means the two sides are not the agents this design says they are |
| `RECON` | §1.2's witness agrees on all five statistics | `summary.json` vs raw records | ⛔ can only VOID, never move, a number |

### 4.1 ⭐⭐ `G-N` AND `G-DECKS` ARE THE PROSE — THE `FPU-A1` FIX

The parent round's `CELL_FPU04` was **VOIDED** by its own adjudicator over **one** deterministic
`WindowTruncationError` (`1/800 = 0.125 %`), an order of magnitude below the 2 % void bar its **own
frozen prose** set. The condition columns said `n_failed == 0` and `n_common == 400`; the notes
column — carrying the `b32v64` 0.100 % rust-panic precedent, the reasoned rule — said a sub-2 %
failure rate is *"REPORTED, never silently absorbed"*. The strict column won, and
`AMENDMENTS.md` FPU-A1 had to amend the verdict **with the statistics already visible**.

**In this round the prose IS the condition, in both gates, on ONE denominator:**

- ⭐⭐ **THE DENOMINATOR IS GAMES.** A deck played at one seat only **is** exactly one failed game, so
  `G-DECKS`' one-seat-only rate and `G-N`'s `n_failed / n_games` are the **same quantity read off two
  different documents** — which is the whole point of having both. ⚠️ The first draft used a *decks*
  denominator in `G-DECKS`; the two gates then disagreed by a factor of two on the same archive, one
  voiding while the other reported. **Caught in build, before game 1.**
- **`n_failed / 800 < 2 %`** ⇒ **REPORTED** in the gate's own `why`, and the rung **READS**.
- **`>= 2 %`** ⇒ the rung **VOIDS**, on both gates.
- **`n_common >= 80 %` of 400** — a **fraction**, never an equality. ⚠️ A **backstop**: at 400 decks
  the 80 % floor allows 80 lost decks while the 2 % bar voids at 16 games, so the 2 % bar is the
  operative one and the floor catches a shape it cannot see.
- ⛔ **The accounting identity `n + n_failed == 800` is a HARD fail and is NOT absorbed by the bar.**
  Games that vanished *without* being recorded as failures mean the denominator is unknown — a
  strictly worse defect than a recorded failure, and not the case the bar exists for.
- ⛔ **Out-of-range seeds and band-range intersection remain HARD fails.** Nothing about the failure
  bar softens them.

⭐ **A seeded game cannot be re-rolled.** A permanently-failing deck is a fact about the deck set, not
about the dose; the emitter states EXCLUSIONS, not zeros. That is *why* the design absorbs it below
the bar — and why it is REPORTED loudly rather than silently.

`analyze_ladder.py --selftest` proves **both directions at the frozen 400-deck scale**: `15/800 =
1.875 %` must READ on both gates; `16/800 = 2.000 %` must VOID on both.

### 4.2 ⭐⭐ THE GOLDEN GATE IS A LAUNCH PRECONDITION, NOT A GATE

`FPU_BITEXACT_LADDER.json` must read `PASS`, **carrying the launching box's own
`carc_rs_binary_sha`**, before any rung runs; `run_cells.sh` refuses without it. It proves four things
no per-rung gate can:

- ⭐ **`fpu=None` is the champion bit-for-bit ON THIS WHEEL** — 20 seeded games, identical
  action-sequence hashes across the pre-plumbing and launch source trees on one binary.
- ⭐ **every rung's dose BINDS** — one positive control per dose, `0.05` included.
- ⭐⭐ **`DOSE-DISTINCT`** — the four dosed legs differ **from each other**. A build that clamped or
  bucketed the dose would pass every positive control and still flatten the ladder into one
  measurement repeated four times.
- ⭐ **the wheel is a constant of this round**, and the launcher can refuse a gate run on a different
  binary.

⛔⛔ **THE PARENT ROUND'S `FPU_BITEXACT.json` IS NOT INHERITED.** It is `PASS` on binary
`f6316d42838574de`; the S1 `R7`/`R6` merge has since changed `carc_core::search` and
`fair::search_worlds`, and the installed binary has moved twice. The R7 counters are *argued*
play-neutral — which is exactly what the hard-coded `None` also was. DESIGN §9.1 states it in full.

⚠️ It is a **code-path** gate at a tiny budget (`k2 × 96`). ⛔ **No number in it is a strength
measurement** and none may be quoted as one.

### 4.3 The reachable branch set, stated BEFORE the run

Recorded here so it cannot be reconstructed later: **every branch in §5 is reachable on every rung**,
including `R-NEGATIVE` and `U-VOID-INSTRUMENT`, and **every round verdict in §5.4 is reachable**.
⛔ No branch is unreachable by construction; the selftest sweeps a dense `(M, SE)` grid and a full
round-verdict table and proves it. If any pre-launch fact later makes one unreachable, that fact is
recorded **before game 1** or it does not count.

---

## 5. THE BRANCHES — PRE-REGISTERED, EXCLUSIVE, EXHAUSTIVE

### 5.1 Per rung

Adjudicated **PER RUNG**, on that rung's own realized SE, against zero, **in this order**. First match
wins. ⛔ **There is no anchor rung and no hard ordering**: four bands, four questions.

| # | branch | condition | reading |
|---|---|---|---|
| 0 | **`U-VOID-INSTRUMENT`** | any §4 gate FAILS on this rung, or any round-level gate fails | The instrument, not the world. **No reading of any kind** from this rung. Its statistics print only as a companion table under a `VOID` banner. ⭐ The other rungs' readings are unaffected; ⛔ the ROUND verdict is blocked (§5.4) |
| 1 | **`R-NEGATIVE`** | `M <= 0` **and** `z <= -2.0` | ⭐ **This dose is ACTIVELY HARMFUL.** Fully plausible and pre-registered as such: a pessimistic FPU narrowing an already well-tuned search is a real mechanism, and the M3 curve's roll-off is consistent with it. ⚠️ At `0.05` it would be the more surprising reading and the §5.3 multiplicity note applies with force |
| 2 | **`R-ADOPT-CANDIDATE`** | **`LB95(M) >= +1.5`** | ⭐⭐ **This dose is worth taking through the adoption chain.** It has cleared, at 95 %, the effect size the decision cares about. ⚠️ Licensed reading is **narrow** — see §5.2 |
| 3 | **`R-BOUNDED`** | **`UB95(M) < +1.5`** | ⭐ **This dose is BELOW the decision-relevant effect at 95 %.** It discharges THIS RUNG. ⚠️ It **bounds; it does not zero** — a rung can read `R-BOUNDED` carrying a positive point estimate |
| 4 | **`R-UNRESOLVED`** | everything else | The rung did not resolve the bar in either direction. ⛔ **NOT a null and NOT a bound.** `feedback_noisy_plateau_not_a_conclusion` binds |

⛔ **Exclusive and exhaustive by construction.** `R-ADOPT-CANDIDATE` and `R-BOUNDED` cannot both hold
(`LB95 <= UB95`). `R-NEGATIVE` requires `M <= 0 ∧ z <= -2`, which forces `UB95 <= 0 < 1.5`, so it
would **also** satisfy `R-BOUNDED` — which is why it is checked first. Branch 4 absorbs the
remainder. ⭐ The selftest sweeps a dense `(M, SE)` grid to prove exactly one branch fires at every
point and that all four are reachable.

⭐⭐ **THE BAR IS ON THE INTERVAL, NOT THE POINT ESTIMATE.** `M = +2.0` with `se = 0.69` — a point
estimate well above `+1.5` — reads `R-UNRESOLVED`, because `LB95 = +0.62`. That is the whole
difference from a point-estimate bar, and `sanity_check()` pins it.

### 5.2 ⚠️ THE RIDERS ON `R-ADOPT-CANDIDATE` — MANDATORY, AND THEY TRAVEL WITH EVERY CITATION

1. ⛔ **IT DOES NOT LICENSE A PRODUCTION CHANGE.** It licenses **step 2 of
   `screen_lib.ADOPTION_CHAIN`** — a production H2H against the deployed champion **with the arbiter
   ARMED (`B=64`)**, on a **fresh band** — and nothing else. Each leg after that (Carcasum external
   on the arm-on T-TRANSFER protocol; an E4 epoch on the phone) is its own prereg, its own band and
   its own owner funding.
2. ⛔ **IT IS A `B=0` (ARBITER-OFF) RESULT.** Transfer to the deployed, arbiter-armed champion is an
   **assumption**, not a measurement — and the interaction is not neutral in principle, since the
   arbiter fires on exact ties and FPU changes which ties get reached (DESIGN §2.3).
3. ⛔ **IT DOES NOT LOCATE AN OPTIMUM AND IT IS NOT A BRACKET.** Four rungs on four bands are four
   independent **within-band** readings that do not share a footing.
   `feedback_bracket_hyperparams` wants ≥3 well-spread points on a comparable footing; cross-band
   over-dispersion denies this ladder that footing. **No interpolation between rungs is licensed.**
4. ⛔ **IT SAYS NOTHING ABOUT THE INCUMBENT `0.2`.** A rung firing here neither displaces nor confirms
   it — they are on different bands and §1.3 forbids the arithmetic that would compare them.
5. ⛔ **IT SAYS NOTHING ABOUT THE OTHER RUNGS.** Each rung is its own question, and §5.3 binds.
6. ⚠️ **IT IS A `k16 × 1376`, ARBITER-OFF, `fixed_v1`+R9 RESULT** on one fresh band, which retires
   `decision_influenced=yes` the moment the read-out lands (§7).
7. ⚠️ **`elo` may never be quoted bare**, and in this round it is not even a bar (§1.1).

### 5.3 ⛔ FOUR RUNGS ARE FOUR COMPARISONS — AND THE MULTIPLICITY CUTS THE OTHER WAY HERE

At the **`LB95` adoption bar** the family-wise false-fire rate under a global null is
**≈ 4 × 0.0015 % ≈ 0.006 %**. ⭐ **This bar cannot fire on noise**, which is the strongest thing this
round has going for it. ⛔ **No correction is applied** — the bars are pre-registered and each rung
is its own question — and the figure is **disclosed on every branch**.

⚠️ The inflation that *does* matter is on `R-NEGATIVE`, whose per-rung false-fire rate under a null
is 2.28 % ⇒ **≈ 8.8 % family-wise**. A lone `R-NEGATIVE` beside three nulls is read as
`feedback_results_table_source_of_truth`'s **NOISE SIGNATURE**, not as a discovered harm.

⛔ **NO CROSS-RUNG CONTRAST IS A BRANCH INPUT.** The dose-response shape — the four rungs plus the two
context rows — is printed as a **named companion** and is a **DIRECTION**, nothing more. Every
comparison in it is cross-band and carries CL-068's 1.8–2.2× over-dispersion in full.

⚠️ **AND ONE SPECIFIC TRAP IS NAMED IN ADVANCE:** `CELL_FPU015` sits immediately below a **fired
endpoint**. A winner's-curse crest at `0.2` would show up here as a *shortfall*, and a shortfall at
`0.15` beside `+2.951` at `0.2` may **not** be read as "the peak is at 0.2". It is two within-band
readings on two bands, and that is all.

### 5.4 ⭐⭐ THE ROUND VERDICT — NEW, AND PRE-REGISTERED

Computed by `screen_lib.round_verdict()` so it cannot be re-read favourably after the fact.

| verdict | condition | reading |
|---|---|---|
| **`LADDER-VOID`** | any round-level gate failed, **or** any rung is `U-VOID-INSTRUMENT`, **or** a frozen rung produced no archive | ⛔ **THE ROUND DISCHARGES NOTHING.** A voided or absent rung is **not a bound**, so `LADDER-DEAD` may not be declared over it. ⭐ The rungs that passed their gates keep their own per-rung readings; the ROUND verdict does not exist |
| **`LADDER-LIVE`** | at least one rung reads `R-ADOPT-CANDIDATE` | ⭐⭐ There is a dose worth taking to step 2 of the adoption chain. §5.2's riders travel with every citation |
| **`LADDER-DEAD`** | **every** rung has `UB95 < +1.5` (i.e. every rung reads `R-BOUNDED` or `R-NEGATIVE`) | ⭐ **`fpu = 0.2` STANDS AS BEST-KNOWN** and its **confirmation leg** (step 2: a production H2H with the arbiter armed, on a fresh band) is **LICENSED TO PROPOSE**. ⚠️ "Licensed to propose" is not "funded" — the owner funds it. ⛔ It does **not** re-close the axis and does **not** retract the `0.2` reading |
| **`LADDER-UNRESOLVED`** | anything else — at least one rung read `R-UNRESOLVED` and none adopted | ⛔⛔ **NOT A NULL AND NOT A BOUND.** The round bought no ladder verdict. §8 pre-registers this as the **most likely** outcome under a true global null (~90 %) and §8.2 pre-commits its price |

⛔ `LADDER-LIVE` and `LADDER-DEAD` are mutually exclusive: an adopting rung has
`UB95 >= LB95 >= +1.5`.

---

## 6. THE ADOPTION CHAIN — FROZEN BEFORE ANY NUMBER EXISTS

`screen_lib.ADOPTION_CHAIN`, restated so a fired rung cannot later be walked through a shorter chain
than the one this round pre-registered:

1. **THIS LADDER** — a rung reads `R-ADOPT-CANDIDATE` on its own fresh band, arbiter OFF both sides.
2. **PRODUCTION H2H** — the winning dose vs the DEPLOYED champion **with the tie arbiter ARMED**
   (`B=64`, `PRODUCTION.yaml` since 2026-08-20), on a **FRESH band**. ⛔ This is the leg that prices
   the arbiter-off deviation.
3. **CARCASUM EXTERNAL** — the arm-on T-TRANSFER protocol; the only out-of-family check this program
   has (`feedback_evloss_grader`'s F4 lesson: judged headroom is family-relative, and out-of-family
   corroboration comes first).
4. **E4 EPOCH** on the phone.

⛔ **EACH LEG IS ITS OWN PREREG, ITS OWN BAND AND ITS OWN OWNER FUNDING.** A rung firing here funds
nothing automatically.

---

## 7. GOVERNANCE

Measurement only. On **every** branch:

- ⛔ `governance/PRODUCTION.yaml` **UNTOUCHED**. No branch licenses a production change of any kind.
- One `experiments/results.csv` row **per rung**, citing the branch and carrying §5.2's riders.
- ⭐ **`docs/LEVER_INDEX.md:146` is UPDATED on every branch** — it must say what doses were measured,
  on which agent, at what bar, and with what bound. That row is the reason the next reader will or
  will not re-propose this lever.
- Bands `164000000000`–`167000000000` retire `decision_influenced=yes`.
- ⭐ **THIS READ-RULE IS SPENT WHEN THE READ-OUT LANDS, ON EVERY BRANCH**, and the four bands retire
  from confirmatory use.
- The context rows are **context in the read-out**, never a gate input, never pooled (§1.3).

---

## 8. ⛔⛔ CAVEAT — WHAT THE BAR COSTS, STATED BEFORE GAME 1

*This section exists because the house rule (owner, 2026-08-30) requires it: "if the honest answer is
'we can only afford the bounding direction,' SAY SO in the READ_RULE including the null's expected
read distribution." ⛔ **THE BAR DOES NOT MOVE** — `BAR_EFFECT = 1.5` is pre-registered design and
this section changes no number, no gate and no branch. It states plainly what the design already
implies, so the read-out cannot be surprised by it after the fact.*

`screen_lib.read_distribution()` computes the following and `sanity_check()` asserts them, so this
round cannot quietly improve its own advertised odds.

**Under a true null (`δ = 0`), at the modelled `se = 0.6905`:**

| branch | ≈ probability |
|---|---|
| **`R-BOUNDED`** | **54.6 %** |
| **`R-UNRESOLVED`** | **43.2 %** |
| `R-NEGATIVE` | 2.28 % |
| `R-ADOPT-CANDIDATE` | 0.0015 % |

**And at the round level, under a true GLOBAL null:**

| round verdict | ≈ probability |
|---|---|
| **`LADDER-UNRESOLVED`** | **≈ 89.6 %** |
| **`LADDER-DEAD`** | **≈ 10.4 %** |
| `LADDER-LIVE` | ≈ 0.006 % |

⛔⛔ **THE MOST LIKELY OUTCOME OF THIS ROUND UNDER A TRUE NULL IS THAT IT DISCHARGES NOTHING.** That
is not a prediction about FPU; it is arithmetic about a demanding `LB95` bar at `n=400`, and it is
written here before game 1.

**At other true effects:**

| true effect `δ` | `R-ADOPT` | `R-BOUNDED` | `R-UNRESOLVED` |
|---|---:|---:|---:|
| **+1.5 (exactly at the bar)** | 2.28 % | 2.27 % | **95.4 %** |
| **+2.951 (a repeat of the incumbent)** | **54.1 %** | ~0 % | 45.9 % |

⛔ **A TRUE EFFECT EXACTLY AT THE BAR IS ESSENTIALLY UNRESOLVABLE HERE.** The bar is a **decision**
threshold, not a detection threshold, and `n` was not sized to detect it. ⛔ **AND EVEN A REPEAT OF
THE INCUMBENT'S OWN `+2.951` ADOPTS ONLY ~54 % OF THE TIME.**

### 8.1 ⛔ THE `n` THIS BAR WOULD ACTUALLY NEED

| goal | decks/rung | games/rung | round games | vs funded |
|---|---:|---:|---:|---:|
| **funded** | 400 | 800 | 3,200 | 1× |
| adopt a repeat of `+2.951` at 80 % power | **732** | 1,464 | 5,856 | 1.8× |
| `LADDER-DEAD` at 80 % under a true null | **1,102** | 2,204 | 8,816 | **2.8×** |

⭐ This is the "size `n` to resolve THAT" half of the house rule, answered honestly: **this round
cannot afford it**, and the funded shape buys a screen against a demanding bar rather than a powered
test of it.

### 8.2 ⭐ THE PRE-COMMITTED PRICE OF AN UNRESOLVED READ

**A rung that reads `R-UNRESOLVED` is re-runnable ONLY on a NEW BAND and ONLY with fresh owner
funding.** Stated now so the cost is known before it is incurred:

- ⛔ **The band is spent either way.** §7 retires all four bands `decision_influenced=yes` when the
  read-out lands. An `R-UNRESOLVED` rung **may not be extended, topped up, or re-read at larger `n`
  on its own band** — that is the `rodv3` failure mode (`n` bought after seeing the sign), and
  CL-068's cross-band over-dispersion means the extension could not be pooled with the original
  anyway.
- ⛔ **This read-rule is spent when the read-out lands, on every branch** (§7). A re-run is a **new
  round** needing a new pair, a new band claim, and the owner's funding.
- ⚠️ **The honest description of that outcome is "this round bought no verdict on this rung."** It is
  disclosed here rather than discovered later, and no reading stronger than §5.1's branch-4 text may
  be taken from it.

### 8.3 ⛔ `LADDER-UNRESOLVED` DOES NOT DISCHARGE THE INCUMBENT'S CONFIRMATION LEG EITHER

Pre-committed here, **before any number exists**, because the temptation after the fact will be to
read a null-shaped `LADDER-UNRESOLVED` as if it were `LADDER-DEAD` — they are the same underlying
world most of the time. It is not licensed:

1. ⛔ Only `LADDER-DEAD` says *"every dose measured here is bounded below the decision-relevant
   effect"*, and only `LADDER-DEAD` carries §5.4's consequence — that `0.2` stands best-known and its
   confirmation leg becomes proposable.
2. ⛔ `docs/LEVER_INDEX.md:146` is still **UPDATED** (§7 says *on every branch*), but on
   `LADDER-UNRESOLVED` it is updated to say **the ladder was measured and did not resolve** — never
   to say the axis was re-closed, and never to say any dose was refuted.
3. ⛔ `RIDERS_R_UNRESOLVED` (in `screen_lib.py`) **GOVERN** the read-out and travel with every
   citation, exactly as §5.2's riders do.
