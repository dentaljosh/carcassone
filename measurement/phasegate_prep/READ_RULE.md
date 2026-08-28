# PHASE-GATED TIE ARBITRATION — JUDGE-FREE PHASE DECOMPOSITION — READ RULE

> **STATUS: FROZEN** (2026-08-28). This document and [`DESIGN.md`](DESIGN.md) are **the pair**, and
> the pair is law. ⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every bar, every gate,
> every branch and every prohibition below exists **before any game does**.
>
> If `analyze_phasegate.py`, `screen_lib.py` or `run_cells.sh` disagrees with this document,
> **it is the code that is wrong.**
>
> ⚠️ **After game 1 there is no amendment route.** The only one that exists is round 2's: freeze the
> verdict as it stands, record the defect, and get the **OWNER** to authorise a re-read of the SAME
> archive under a named, minimal, single-clause correction.
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.** The instrument
> exists (merged `2d0ecdde`) and `IDENT_BITEXACT.json` is `PASS`.

**Band `154000000000` · Option A1 — `IDENT` + `ARB_FULL` + `ARB_EARLY`(`_L`/`_R`) · k8×1376 = 11008
both sides · local W=30 + laptop W=22, concurrent** (the owner's Shabbos-envelope W defaults; the
`W=14` quoted below is the design-time figure and `W` is throughput-only).

⚠️ `W` is **throughput-only**. Games are bit-identical at any `W`, and **no gate in this pair reads a
clock**. It moves wall clock and the cell→box assignment and **no bar, no gate and no branch**.

---

## 1. THE STATISTIC

**Per cell, PRIMARY:**

```
D(deck) = ( diff(deck, a_seat=0) + diff(deck, a_seat=1) ) / 2
M       = mean over decks appearing in BOTH seatings
SE      = sample sd (ddof=1) / sqrt(n_paired)
z       = M / SE
UB95    = M + 2*SE          LB95 = M - 2*SE
```

`diff` is the harness's own final-score margin, **candidate minus opponent, in POINTS**
(`eval_fair_puct.py:1603`). **`M > 0` ⇒ the CANDIDATE won.** A deck missing a seating is **DROPPED**,
never defaulted to zero, and surfaces as a short `n_paired` at `G-DECKS`.

⛔ **Adjudicated AGAINST ZERO, at the cell's OWN REALIZED SE.** The sizing constant
`sigma_D = 13.81` (DESIGN §3.1) is **power arithmetic only** and is ⛔ **never a denominator in a
branch test.**

⛔ **`n_paired` IS IN DECKS, NOT GAMES.** A paired `n=2400` cell yields at most **1,200 decks**.
Every bar below is in decks. (Stage 2's own `§0.B` pre-launch amendment caught a `G-N` floor that
was *unreachable on a perfectly complete run* for exactly this confusion.)

### 1.1 `RECON` — the witness

`screen_lib.paired_margin()` is a **deliberately independent re-implementation** of
`eval_fair_puct._paired_z` — not an import of it (an imported one would agree by construction and
witness nothing) — accumulated with `math.fsum` rather than `sum`. It recomputes
`paired_mean_margin`, `paired_z`, `n_paired`, `winrate` and `elo` **from the raw records** and
compares against `summary.json` at rel 1e-6 / abs 1e-9.

⛔ **It can only VOID, never move, a number.**

### 1.2 ⛔ THE PRIOR BANDS ARE DESCRIPTIVE OVERLAYS ONLY

Stage-2 Phase B ran on band `132000000000` (`M +3.0700`), the b64 cell's `NARROW` arm on
`139000000000` (`M +3.6607`), the JCZ replication on `134000000000`. This round is on
`154000000000`.

**CL-068 measured 1.8–2.2× over-dispersion on cross-band contrasts, in BOTH the elo and the
deck-paired-margin statistics**, with an identity control exonerating the harness and the "different
decks" explanation arithmetically excluded.

⛔ **NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT.** In particular, ⛔ **`G-ANCHOR` (§4.0)
does NOT test this round's `M_full` against `+3.07`** — it tests it against **zero**, at its own
realized SE. "Reproduces +3.07" is a **narrative** reading; the gate is a sign-and-significance
test, because a cross-band equality test is exactly the thing CL-068 forbids.

⭐ The one thing the overlays legitimately did was fix **where** this round measures and **what bar
is worth paying for** (DESIGN §4.1). Choosing where to look is a **design act**; combining readings
is a statistical one. That use is spent **before any number of this round exists**, and no branch
reaches back into it.

---

## 2. THE CELLS

| cell | box | `phase_gate` | opponent | role |
|---|---|---|---|---|
| `IDENT` | local | `none` | unmodified champion | ⭐ preflight identity |
| `ARB_FULL` | laptop | `all` | unmodified champion | ⭐ **THE ANCHOR** |
| `ARB_EARLY` (`_L` + `_R` sub-cells) | local + laptop | `early` | unmodified champion | ⭐⭐ **THE PRIMARY** |
| `ARB_MID` *(Option B)* | — | `mid` | unmodified champion | secondary |
| `ARB_LATE` *(Option B)* | — | `late` | unmodified champion | secondary |

Arbiter on the **candidate only**, at `B=16 · J=4 · mode=argmax · salt=tiearb2-deploy-v1 · eps=0.0`.
Opponent structurally disarmed — **no `--cand-tiearb-*` flag reaches the opponent side, ever.**

⚠️ **This is NOT the production rung.** `PRODUCTION.yaml` carries `B=64` since 2026-08-20. DESIGN
§2.3 states the reason and the price; **that price rides on every branch below.**

---

## 3. THE PHASE WINDOWS — FROZEN

| phase | `k_remaining` ∈ |
|---|---|
| `early` | **[49, 71]** |
| `mid` | **[25, 47]** |
| `late` | **[0, 23]** ⚠️ **and `k=48` and `k=24`** |

`k_remaining` = undrawn deck + the tile in hand (`fair_agent.k_remaining` / `carc_core::fair::k_remaining`).
⛔ Never `state.deck_len()`.

⚠️ `k=48` and `k=24` match no interval (both cut ends are strict) and fall through to `"late"` — the
canonical `sample_agreement_roots.phase_bucket` behaviour, reproduced deliberately and pinned by a
golden test. ⛔ **A build that "fixes" the edge VOIDS the round**: it would no longer be measuring
the axis the census, the CL-070 root bank and `split_tiearb2.py`'s strata are keyed on.

---

## 4. THE GATES

⛔ **ABSENT IS FAIL. Never a skip, never a default.** Every gate resolves across **both** documents —
`config.*` in **`manifest.json`**; statistics in **`summary.json`**, which carries **no config block
at all** (IS-D1) — and prints **which document and which address** answered. A value found at **no**
address is `ABSENT`, and `ABSENT` is `FAIL`.

⛔ **A FAIL ON ANY GATE MAKES THAT CELL `U-VOID-INSTRUMENT`**, checked **first** in the branch table.

| id | asserts | address | fires on |
|---|---|---|---|
| ⭐⭐ `G-GATE` | `config.cand_tiearb.phase_gate` == this cell's **frozen** window, EXACTLY (`none`/`all`/`early`/`mid`/`late`) | `manifest:config.cand_tiearb.phase_gate` | ⛔ **THE INVERTED-LIVENESS GATE.** A silently-defaulted `all` makes `ARB_EARLY` **BE** `ARB_FULL` and the primary a guaranteed-meaningless duplicate that looks healthy. `ABSENT` is `FAIL` — a build whose telemetry omits the key **cannot** be adjudicated |
| ⭐⭐ `G-PHI` | per-phase fire counters present, and **the window bit is PROVEN**: on `ARB_EARLY` `fired_mid == 0 ∧ fired_late == 0 ∧ fired_early > 0`; on `ARB_MID`/`ARB_LATE` the mirror; on `ARB_FULL` all three `> 0` **and** `fired_early+fired_mid+fired_late == fired_plies`; on `IDENT` **all four are 0** | `manifest:config.cand_tiearb.fired_{early,mid,late}` + `.fired_plies` | ⛔ the **second** independent witness that the gate is live, and the only one derived from **play** rather than from config. `G-GATE` proves the knob was *set*; `G-PHI` proves it *bound* |
| `G-TIEARB-ARM` | candidate: `enabled true`, `B==16`, `J==4`, `mode=="argmax"`, `salt=="tiearb2-deploy-v1"`, `eps==0.0`. Opponent: **no** tiearb container, **no** terminal `*.tiearb_enabled` true | `manifest` | a wrong rung, or an armed opponent. ⚠️ scan **container** segments only for (b) — a healthy archive emits a TERMINAL `config.opponent.tiearb_enabled=false` |
| `G-LEAF` | ⭐ **BOTH SIDES EQUAL** `a36d2e15a3b3d71d`, and `config.cand_leaf_cfg.v29_meeple_curve == curve125` | `manifest:config.{cand,opp}_leaf_hash` | ⛔ **REWRITTEN, NOT COPIED** from invasion r3, where the two sides differ **by design**. The arbiter is a post-search root hook, **not a leaf change**: differing leaf hashes here mean a misconfigured cell |
| `G-BAND` | `config.band_seed_start` == this cell's frozen `seed_start`; `n_decks` and `seatings_per_deck == 2` match the frozen plan | `manifest:config.*` | any deviation. ⚠️ read **top level AND `config.*`** and report which resolved — the Stage-2 `G-BAND`/`G-J1` defect class |
| `G-DECKS` | every realized seed inside **this cell's own** range; no deck at one seat only; `n_common` == the cell's frozen `n` | raw `seed*_a*.json` | ⛔ **REWRITTEN, NOT COPIED.** This round's ranges **OVERLAP BY DESIGN** (DESIGN §5) — `ARB_FULL`'s 400 decks are a subset of `ARB_EARLY`'s 1,200. An unedited invasion-r3 disjointness clause voids every healthy cell |
| ⭐ `G-SUBPOOL` | `ARB_EARLY_L` and `ARB_EARLY_R` carry **byte-identical** config blocks across the full frozen alias table, and their deck sub-ranges are **disjoint** and **exhaust** the cell's range | both sub-cell manifests | pooling two cells that are not the same cell |
| `G-SINGLEVAR` | the two sides' search knobs are identical across the frozen alias table; the **only** candidate/opponent difference is the `cand_tiearb` block | `manifest:config.champion.*` vs `config.opponent.*` | ⚠️ the opponent's search knobs live one level down under `config.opponent.champ_cfg.*` — a gate written from the design rather than from a real manifest voids every healthy cell |
| `G-BUDGET` | both sides `(k_dets, sims_per_det, total_sims) == (8, 1376, 11008)` **and the product multiplies out** | `manifest:config.champion.*` / `config.opponent.*` | any asymmetry |
| `G-EXACT` | both sides `exact_k == 2` and `mode == "marginalized"` | `manifest:config.endgame.*` | K=3/4 are clairvoyant-only |
| `G-RULES` | `rules_profile.name == "fixed_v1"`, `r9_env_ok` and `r9_env_observed` both `true` | `manifest:rules_profile.*` | R9 not latched. ⚠️ R9 is env-latched at **import** |
| `G-BACKEND` | `name == requested == "rust"`, `mixed_builds false`, `converted_sides == {candidate, opponent}` | `manifest:config.backend.*` | ⛔ the arbiter is **RUST-ONLY**; a python leg serves an arbiter-blind candidate that reads as a clean null |
| `G-WHEEL` | `carc_rs_build` and `carc_rs_binary_sha` present; `mixed_builds false`; the build's embedded rev is one at which the `tiearb_phase_gate` field **exists** and is an **ancestor** of the branch tip | `manifest` + git ancestry | a stale wheel — which would serve a **gate-blind** arbiter, i.e. `ARB_EARLY` == `ARB_FULL`. ⚠️ `carc_rs_version` is permanently `"0.1.0"` and is **NOT** a discriminator |
| `G-WHEEL-SAME` | ⭐ **ROUND-LEVEL.** `carc_rs_binary_sha` identical across every cell | `manifest` | a changed wheel **or a different box** (the sha is box-local). ⛔ **A FAIL ON ANY CELL VOIDS EVERY CELL.** ⚠️ This round **builds a new wheel**, so it **carries its own `IDENT`** and inherits none |
| `G-REV` | (i) each manifest's short `code_rev` **names** its own box's `PINNED_SRC_REV` (≥7-hex prefix; `-dirty` is INFORMATIONAL, never fatal); (ii) `SRC_CLEAN.jsonl` records the code paths clean at every boundary; (iii) ⭐⭐ **the cross-box clause** via `screen_lib.cross_box_rev_gate()` — the pins **agree** as 40-hex, and every emitted rev **canonicalizes to that pin** | manifests + each box's `PINNED_SRC_REV` + `SRC_CLEAN.jsonl` | a mixed-rev round. ⛔ **NEVER by comparing one box's emitted short rev to the other's** — the IS-A1 defect |
| `G-BLIND` | `BLIND_COMMIT` is a 40-hex sha, an **ANCESTOR** of HEAD, the commit that **INTRODUCED** this pair's FROZEN banner, agreed by `BLIND_PROOF.json` against a **live** git re-check, and stamped into every adjudicated manifest | `manifest:BLIND_COMMIT` + `BLIND_PROOF.json` + git | a read that was not blind |
| `G-HOST` | the manifest's `host` matches this **sub-cell's** frozen box (substring test on a normalised hostname — `laptop`/`laptop-wsl`/`laptop-pop`/`pop-os` are one physical machine) | `manifest:host` | a cell run on the wrong box. ⚠️ proves the **sealing pass** ran on the assigned box; the real protection is structural (disjoint `--out-subdir`s ⇒ no shared claims to race over) |
| `G-N` | `n` == the cell's frozen game count, `n_failed == 0`, `n_common` ≥ 80% of the frozen deck count | `summary.json` | ⚠️ a failure rate **strictly below 2%** is **REPORTED, never silently absorbed** (the `b32v64` 0.100% rust-panic precedent); at or above it the cell voids |
| `G-FAILSOFT` | `tiearb_errors_total` and `tiearb_error_rate_on_fired` **present and reported**; error rate `< 0.01` | `manifest:config.cand_tiearb.*` | ⚠️ **REPORT-ONLY above the floor.** A gated-out ply is **not** an error and must not appear here (§7.5 test 6). §0.I.1's withdrawn claim stands: fail-soft is **not** symmetric across cells by construction — once cells diverge they are on different boards — so it is disclosed per cell, never assumed away |
| `G-SAT` | `0.35 <= winrate <= 0.65` | `summary:winrate` | a **RAIL** check, not a strength bar: both sides run the same search on the same leaf, so a winrate outside this window means the two sides are not the agents this design says they are |
| `RECON` | §1.1's witness agrees on all five statistics | `summary.json` vs raw records | ⛔ can only VOID, never move, a number |

### 4.0 ⛔⛔ `G-ANCHOR` — THE HARD ORDERING, RESOLVED BEFORE ANY PHASE BRANCH

**`G-ANCHOR` PASSES iff `ARB_FULL` passes every gate above AND `z_full >= +2.0`.**

⛔ **IF `G-ANCHOR` FAILS, THE ROUND'S BRANCH IS `U-VOID-ANCHOR` AND NO BRANCH ON ANY GATED CELL IS
TAKEN — the gated cells' statistics are NOT PRINTED.**

The entire design presupposes the arbiter wins in this band, on this build, at `B=16`. If it does
not, a phase decomposition has nothing to decompose, and a slice reading in that situation is
uninterpretable rather than informative.

⚠️ Per §1.2 the test is `z_full >= +2.0` **against zero**, ⛔ **never an equality test against
`+3.07`**. Prior-band values are cited in the read-out as context and are never a gate input.

⭐ **`U-VOID-ANCHOR` IS A FULLY ACCEPTABLE OUTCOME** and is recorded as a finding in its own right —
a non-replicating arbiter on a fresh band and a new wheel would be **more** decision-relevant than
any phase slice, and would immediately impugn a production knob.

### 4.1 The reachable branch set, stated BEFORE the run

Recorded here so it cannot be reconstructed later: with `G-ANCHOR` unresolved at freeze time, **every
branch in §5 is reachable**, including `E-REVERSED` and both void branches. ⛔ No branch is
unreachable by construction. If any pre-launch fact later makes one unreachable, that fact is
recorded **before game 1** or it does not count.

---

## 5. THE BRANCHES — PRE-REGISTERED, EXCLUSIVE, EXHAUSTIVE

Adjudicated on `ARB_EARLY` (pooled over `_L` + `_R`), **in this order**. First match wins.

| # | branch | condition | reading |
|---|---|---|---|
| 0 | **`U-VOID-INSTRUMENT`** | any gate in §4 FAILS on `ARB_EARLY`, `IDENT`, or a `G-SUBPOOL`/`G-WHEEL-SAME` round-level gate | The instrument, not the world. **No phase reading of any kind.** Statistics are printed **only** as a companion table with a `VOID` banner |
| 1 | **`U-VOID-ANCHOR`** | `G-ANCHOR` fails (§4.0) | The arbiter did not reproduce. ⭐ A finding in its own right; **gated-cell statistics are NOT printed** |
| 2 | **`E-REVERSED`** | `M_early <= 0` **and** `z_early <= -2.0` | ⭐ **Early-only gating is ACTIVELY HARMFUL.** Fully plausible and pre-registered as such: Stage 2's `RND` cell proved a leaf-tied set is **not** a set of interchangeable moves (`-4.4287`, z `-6.669`), so a *partial* arbiter is not guaranteed to be a *weaker* arbiter — it may be a differently-wrong one. **KILLS the steering-ruler reading** |
| 3 | **`E-LIVE`** | `M_early >= +0.80` **and** `z_early >= +2.0` | ⭐⭐ **Early fires carry game-level value at the ruler-validation bar.** ⚠️ Licensed reading is **narrow** — see §5.1 |
| 4 | **`E-DEAD`** | `UB95(M_early) < +0.80` | ⭐ **Early value is BOUNDED BELOW the bar at 95%.** The judge-free early slice does **not** clear the ruler-validation bar ⇒ **terminal-grounded rollouts are dead as a cheap steering ruler for early-game work**, on this evidence |
| 5 | **`E-UNRESOLVED`** | everything else | The cell did not resolve the bar. ⛔ **NOT a null.** `feedback_noisy_plateau_not_a_conclusion` binds: a flat read at z~1 does not prove dead |

⛔ **Exclusive and exhaustive by construction.** Branch 3 requires `M >= +0.80`; branch 4 requires
`M + 2SE < +0.80` (hence `M < +0.80`); branch 2 requires `M <= 0 ∧ z <= -2`, which forces
`UB95 = M + 2SE <= 0 < +0.80`, so 2 would also satisfy 4 — **which is why 2 is checked first** and
the two are ordered, not disjoint. Branch 5 absorbs the remainder. ⭐ **The instrument's selftest
sweeps a dense `(M, SE)` grid to prove exactly one branch fires at every point.**

### 5.1 ⚠️ THE RIDERS — MANDATORY ON `E-LIVE`, AND THEY TRAVEL WITH EVERY CITATION

`E-LIVE` licenses **the decomposition claim** and **only a weakened form of the ruler claim**:

1. ⛔⛔ **`E-LIVE` DOES NOT PROVE FAMILY-BLINDNESS.** The in-family oracle's early cut read
   `+0.1148` with `F = 1.303` — a **POSITIVE** point estimate with `F` **ABOVE 1.0**. The honest
   statement is *"the oracle could not RESOLVE early capture at n=300"*, ⛔ **never** *"the oracle
   read zero"*. `E-LIVE` is **fully consistent with the offline cut simply having been
   underpowered**, which would teach nothing about family-blindness. ⭐ Corroboration must be
   **judge-free** or **out-of-family** (F4: judged headroom is family-relative; a +1.49 in-family
   ceiling read −0.64 at z −3.8 out-of-family on the same CRN worlds), and it is **not** funded here.
2. ⛔ **It does not measure the owner-hole.** No branch touches `measurement/e4_games/`.
3. ⛔ **It does not license a phase-gated deploy.** The cells are a decomposition instrument; the
   ~27% cost reduction of `ARB_EARLY` is a scheduling fact, **never a finding**.
4. ⛔ **It is a `B=16` result.** `PRODUCTION.yaml` runs `B=64`. Transfer is an **assumption**.
5. ⛔ **The slices need not sum to `ARB_FULL`** and nothing tests that they do (DESIGN §1.2).
6. ⚠️ **`elo` may never be quoted bare.** Stage 2's own secondary did not convict (`+23.92`, CI
   `[−0.21, +48.06]`, winrate z `+1.94`). A phase *slice* of it is weaker still. **The margin is
   the statistic.**

### 5.2 The riders on `E-DEAD`

1. ⚠️ **`E-DEAD` bounds; it does not zero.** The reading is *"below +0.80 at 95%"*, never *"early
   fires are worthless"*.
2. ⚠️ It is a bound **at `B=16`**. A wider arbiter could plausibly clear the bar early; this round
   does not measure that and the `Δ(16→64)` offline increment ⛔ **may not be projected into game
   points** (`offline_ratio_disclaimer`).
3. ⭐ It **does** discharge the funded decision: on this evidence, terminal-grounded rollouts are
   not a cheap early-game steering ruler, and steering work should not be funded off them.

### 5.3 Option B — the 3-way decomposition

If Option B is funded, `ARB_MID` and `ARB_LATE` are adjudicated on the **same** ladder with the
**same** `+0.80` bar, branches suffixed `-MID` / `-LATE`, each on **its own** margin against the
unmodified champion.

⛔ **No cross-slice contrast is a branch input.** ⛔ **No slice-sum test exists.** ⭐ A **named
companion**, never a branch input: the three slices' shares of fired plies from `G-PHI`, beside
their margins, as a **description** of where the arbiter's value sits.

⚠️ Option B is a **3-way multiple comparison**. At the `+0.80 ∧ z>=2` bar the family-wise false-fire
rate under a global null is ≈ 3 × 2.3% ≈ **7%**. ⛔ **No correction is applied** — the bars are
pre-registered and each slice is its own question — but the inflation is **disclosed on every
Option-B branch** and a lone firing slice beside two nulls is read as
`feedback_results_table_source_of_truth`'s **noise signature**, not as a peak.

---

## 6. GOVERNANCE

Measurement only. On **every** branch:

- ⛔ `governance/PRODUCTION.yaml` **UNTOUCHED**. No branch licenses a production change of any kind
  — not the arbiter's `B`, not `J`, not a phase gate, not the champion.
- One `experiments/results.csv` row **per cell**, citing the branch and carrying §5.1's riders.
- Band `154000000000` retires `decision_influenced=yes`.
- ⭐ **THIS READ-RULE IS SPENT WHEN THE READ-OUT LANDS, ON EVERY BRANCH**, and the band retires
  from confirmatory use.
- The `+3.07` / `+3.66` prior-band figures are **context in the read-out**, never a gate input,
  never pooled with this round's numbers (§1.2).
