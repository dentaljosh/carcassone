# FPU RESURRECTION — THE UNREACHABLE-KNOB ROUND — READ RULE

> **STATUS: FROZEN** (2026-08-30). This document and [`DESIGN.md`](DESIGN.md) are **the pair**, and
> the pair is law. ⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every bar, every gate,
> every branch and every prohibition below exists **before any game does**.
>
> If `analyze_fpu.py`, `screen_lib.py` or `run_cells.sh` disagrees with this document,
> **it is the code that is wrong.**
>
> ⚠️ **After game 1 there is no amendment route.** The only one that exists is: freeze the verdict as
> it stands, record the defect, and get the **OWNER** to authorise a re-read of the SAME archive
> under a named, minimal, single-clause correction.
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.**
> `analyze_fpu.py --selftest` is `PASS` and [`FPU_BITEXACT.json`](FPU_BITEXACT.json) is `PASS`.

**Three cells, three bands, one shape:** `CELL_FPU02` (`155e9`, local) · `CELL_FPU04` (`156e9`,
local) · `CELL_CPUCT10` (`157e9`, laptop). Each `n=800` deck-paired (400 seat-balanced decks × 2)
against the **UNMODIFIED CHAMPION** at **fair PIMC `k16 × 1376 = 22016` both sides**.

⚠️ `W` is **throughput-only**. Games are bit-identical at any `W`, and **no gate in this pair reads a
clock**. It moves wall clock and nothing else.

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

`diff` is the harness's own final-score margin, **candidate minus opponent, in POINTS**.
**`M > 0` ⇒ the CANDIDATE won.** A deck missing a seating is **DROPPED**, never defaulted to zero,
and surfaces as a short `n_paired` at `G-DECKS`.

⛔ **Adjudicated AGAINST ZERO, at the cell's OWN REALIZED SE.** The sizing constant
`sigma_D = 13.81` (DESIGN §3) is **power arithmetic only** and is ⛔ **never a denominator in a
branch test.**

⛔ **`n_paired` IS IN DECKS, NOT GAMES.** A paired `n=800` cell yields at most **400 decks**. Every
bar below is in decks.

### 1.1 THE SECONDARY — elo, and the tension it carries

`elo` is reported for every cell with its own CI, **on every branch**.

⚠️ The funding brief states the bar **in elo** (`~±17.5` at 2σ) because the **prior art** is in elo
(`+45.4` / `+31.4`). House doctrine is that **`elo` may never be quoted bare** — Stage-2's own elo
secondary did not convict at `+23.92`, CI `[−0.21, +48.06]`. Both are pre-registered here:
**`BAR_M = 1.381 pts/deck` carries every branch**; `BAR_ELO = 17.4` is the matching 2σ elo
resolution and is reported beside it.

⭐ **A disagreement between the two is DISCLOSED, never arbitrated.** If the margin fires and the elo
does not (or the reverse), the read-out says so, in both numbers, and the **margin** is the branch.

### 1.2 `RECON` — the witness

`screen_lib.paired_margin()` is a **deliberately independent re-implementation** of
`eval_fair_puct._paired_z` — not an import of it (an imported one would agree by construction and
witness nothing) — accumulated with `math.fsum` rather than `sum`. It recomputes
`paired_mean_margin`, `paired_z`, `n_paired`, `winrate` and `elo` **from the raw records** and
compares against `summary.json` at rel `1e-6` / abs `1e-9`.

⛔ **It can only VOID, never move, a number.**

### 1.3 ⛔ THE PRIOR ART IS A DESCRIPTIVE OVERLAY ONLY

`+45.4` / `+31.4` elo (2026-06-02, `results.csv` rows 68–69) and the M3 curve peaking at parity
(rows 233–236) are **context in the read-out and nothing else**.

⛔ **NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT.** CL-068 measured **1.8–2.2×
over-dispersion on merely CROSS-BAND contrasts**, in both the elo and the deck-paired-margin
statistics. These priors are cross-band **and** cross-era **and** cross-agent (neural /
value-blended vs the classical champion) **and** cross-budget. There is no arithmetic that combines
them with this round's numbers.

⭐ What the overlays legitimately did was fix **which doses** this round asks about and **what bar is
worth paying for** (DESIGN §2.1). Choosing where to look is a **design act**; combining readings is a
statistical one. That use is spent **before any number of this round exists**, and no branch reaches
back into it.

⚠️⚠️ **AND `docs/LEVER_INDEX.md:146` RECORDS THIS AXIS AS CLOSED.** This round is a deliberate
reopening whose argument is stated in DESIGN §0.2 and is **narrow**: no prior cell could have
measured the classical champion, because the knob was structurally unreachable on its backend. The
prior evidence is not wrong; it is about a different agent. ⭐ It is also the **strongest reason to
expect `F-REKILL`**, and that expectation is recorded here, before any number exists.

---

## 2. THE CELLS

| cell | box | knob | frozen value | band | role |
|---|---|---|---|---|---|
| `CELL_FPU02` | local | `fpu_reduction` | **0.2** | `155000000000` | ⭐⭐ the primary dose (the never-confirmed 2026-06-02 screen's own) |
| `CELL_FPU04` | local | `fpu_reduction` | **0.4** | `156000000000` | ⭐ the second dose |
| `CELL_CPUCT10` | laptop | `c_puct` | **1.0** | `157000000000` | ⭐ the exploration constant — ⛔⛔ **AND THE τ TRIGGER (§6)** |

Knob on the **candidate only**. Opponent structurally unmodified — ⛔ **no `--cand-fpu-reduction`,
`--cand-c-puct` or `--cand-tiearb-*` flag reaches the opponent side, ever**, and `--c-puct` is
**never** used to express a candidate c_puct (it builds BOTH sides; see `G-TWOSIDED`).

⚠️ **The tie arbiter is OFF on both sides.** `PRODUCTION.yaml` has carried `B=64` since 2026-08-20;
DESIGN §2.3 states the reason and the price, and **that price rides on every branch below.**

⚠️ **The budget is the 2026-08-30 promoted champion, `k16 × 1376 = 22016`.** DESIGN §0.1 states why
`G-PROD` re-asserts it against the YAML at launch instead of trusting the freeze.

---

## 3. THE KNOBS — FROZEN SEMANTICS

| knob | `None` / unset means | a value `r` means |
|---|---|---|
| `fpu_reduction` | the NeuralMCTS **legacy optimistic** `q = 0.0` for unvisited children — **the champion, bit-for-bit** | an unvisited child scores `q = parent.Q − r` (pessimistic FPU) |
| `c_puct` override | the **shared** `--c-puct` (1.5, the champion) | the candidate's PUCT constant, opponent unchanged |

⚠️ **`0.0` IS NOT `None` for `fpu_reduction`.** `Some(0.0)` takes the `node_q − 0.0` branch — the
**parent's Q** — while `None` takes the flat `0.0` branch. The two are deliberately distinguished
end-to-end and never coerced. ⛔ A gate that read `null` and `0.0` as the same value would be unable
to tell the champion from a live cell.

⚠️ `parent.Q` is already in `node.player_to_move`'s POV — the same POV the unvisited child is scored
in — so **no sign flip is applied**. `mcts.py:1225` and `carc_core::search/mod.rs:816` implement the
identical rule; the two backends **mirror**.

---

## 4. THE GATES

⛔ **ABSENT IS FAIL. Never a skip, never a default.** Every gate resolves across **both** documents —
`config.*` in **`manifest.json`**; statistics in **`summary.json`**, which carries **no config block
at all** (IS-D1) — and prints **which document and which address** answered. A value found at **no**
address is `ABSENT`, and `ABSENT` is `FAIL`.

⛔ **A FAIL ON ANY GATE MAKES THAT CELL `U-VOID-INSTRUMENT`**, checked **first** in the branch table.
⭐ **The other cells are UNAFFECTED** — three separate questions on three separate bands, with no
anchor and no pooling.

| id | asserts | address | fires on |
|---|---|---|---|
| ⭐⭐ `G-FPU` / `G-CPUCT` | `config.cand_search.fpu_reduction` and `.c_puct` equal this cell's **frozen** values EXACTLY, with `null` distinguished from ABSENT | `manifest:config.cand_search.*` | ⛔⛔ **THE INVERTED-LIVENESS GATE.** A harness predating this round emits no `cand_search` at all, and its candidate was **fpu-blind by construction** — a cell over it is champion-vs-champion, moves no leaf hash, sits inside `G-SAT`'s rail and reads as a clean credible null. `ABSENT` is `FAIL`: a build whose telemetry omits the key **cannot** be adjudicated |
| ⭐⭐ `G-TWOSIDED` | the **RESOLVED** configs of the two sides: candidate carries the frozen knob, opponent carries the champion's values (`fpu_reduction: null`, `c_puct: 1.5`) | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⛔ the **second, independent** witness. `G-FPU` proves the knob was *requested*; this proves it *landed*, on the candidate and **nowhere else**. It also catches the `--c-puct` trap: the shared flag builds BOTH sides, so a cell built on it shows the opponent's `c_puct` moved too. ⚠️ DESIGN §7.2 is explicit that this is **weaker than phasegate's play-derived `G-PHI`** — a PUCT constant has no fire counter — and that the play-derived evidence is the **golden gate** |
| `G-SINGLEVAR` | the cell's **OWN** alias DIFFERS across the two sides and equals the frozen value on the candidate; **every other** alias is EQUAL | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⛔ **REWRITTEN, NOT COPIED.** Phasegate demanded every knob be equal because its variable lived in a separate container; **here the variable IS a search knob**, so an unedited copy would VOID `CELL_CPUCT10`. ⚠️ The opponent's knobs live one level down under `champ_cfg` — a gate written from the design rather than from a real manifest voids every healthy cell |
| `G-ARB-OFF` | **no** tie-arbiter armed anywhere in the manifest, either side (full walk) | `manifest` (full walk) | ⛔ **INVERTED from phasegate's `G-TIEARB-ARM`.** The arbiter is a stochastic root hook whose fires would confound the very visit distribution FPU changes. ⚠️ This DEVIATES from the deployed champion and the price rides on every branch (DESIGN §2.3) |
| `G-LEAF` | ⭐ **BOTH SIDES EQUAL** `a36d2e15a3b3d71d`, and `config.cand_leaf_cfg.v29_meeple_curve == curve125` | `manifest:config.{cand,opp}_leaf_hash` | neither knob is a leaf term, so differing hashes mean a misconfigured cell — and a moved-hash check can **never** prove this surface live, which is why `G-FPU`/`G-TWOSIDED` exist |
| `G-BAND` | `config.band_seed_start` == this cell's **own** frozen band; `n_decks` and `seatings_per_deck == 2` match | `manifest:config.*` | any deviation. ⚠️ read **top level AND `config.*`** and report which resolved |
| `G-DECKS` | every realized seed inside **this cell's own** range; no deck at one seat only; `n_common` == 400; ⭐ this cell's range **does not intersect** any other cell's | raw `seed*_a*.json` | ⛔ **REWRITTEN AGAIN, IN THE OPPOSITE DIRECTION** from phasegate, whose ranges overlapped by design. Three bands ⇒ **disjointness is assertable again**, and a copied phasegate clause would have skipped the check |
| `G-BUDGET` | both sides `(k_dets, sims_per_det, total_sims) == (16, 1376, 22016)` **and the product multiplies out** | `manifest:config.{champion,opponent}.*` | any asymmetry, and a **stale 11008** cell — which would grade the knob against a superseded champion while every other gate passed |
| `G-PROD` | ⭐ **LAUNCHER-SIDE, PRE-COMPUTE.** the frozen budget == `governance/PRODUCTION.yaml` `champion.fair_deploy` | `governance/PRODUCTION.yaml` | the budget promotion landed mid-build (DESIGN §0.1). ⛔ Hard abort for a real cell and for the smoke; loud-but-continue for `--dry-run`, which spends nothing. **The fix is the bundle sync, never an edit to the pair** |
| `G-EXACT` | both sides `exact_k == 2` and `mode == "marginalized"` | `manifest:config.endgame.*` | K=3/4 are clairvoyant-only |
| `G-RULES` | `rules_profile.name == "fixed_v1"`, `r9_env_ok` and `r9_env_observed` both `true` | `manifest:rules_profile.*` | R9 not latched. ⚠️ R9 is env-latched at **import** |
| `G-BACKEND` | `name == requested == "rust"`, `mixed_builds false`, `converted_sides == {candidate, opponent}` | `manifest:config.backend.*` | ⚠️ unlike the J-rules surfaces and the arbiter, **both knobs are threaded on BOTH backends**, so a python leg would not be knob-blind. It is refused anyway: the champion of record plays on rust, and a mixed-backend round is not one round |
| `G-WHEEL` | `carc_rs_build` and `carc_rs_binary_sha` present; `mixed_builds false` | `manifest` | ⚠️ `carc_rs_version` is permanently `"0.1.0"` and is **NOT** a discriminator. ⭐ **This round makes NO rust change**, so the wheel is a constant and phasegate's stale-wheel risk does not arise. The live risk here is the **PYTHON rev** — see `G-REV` |
| `G-WHEEL-SAME` | ⭐ **ROUND-LEVEL.** `carc_rs_binary_sha` identical across every cell **on a box** | `manifest` | a changed wheel mid-round. ⚠️ the sha is **box-local** and is never compared across boxes. ⛔ **A FAIL ON ANY CELL VOIDS EVERY CELL** |
| `G-REV` | (i) each manifest's short `code_rev` **names** its own box's `PINNED_SRC_REV`; (ii) `SRC_CLEAN.jsonl` records the code paths clean at every boundary; (iii) ⭐⭐ **the cross-box clause** via `screen_lib.cross_box_rev_gate()` — the pins **agree** as 40-hex and every emitted rev **canonicalizes to that pin** | manifests + each box's `PINNED_SRC_REV` + `SRC_CLEAN.jsonl` | ⛔⛔ **THIS ROUND'S PRIMARY PROVENANCE RISK, AND IT IS A NEW SHAPE.** The fpu fix is **python-only** — no rust change, no wheel move — so a box on stale source serves a **knob-free candidate** with a healthy `carc_rs_build`, a healthy binary sha and the correct leaf hash. ⛔ **NEVER by comparing one box's emitted short rev to the other's** — the IS-A1 defect |
| `G-BLIND` | `BLIND_COMMIT` is a 40-hex sha, stamped into every adjudicated manifest and agreeing across cells | `manifest:BLIND_COMMIT` | a read that was not blind |
| `G-HOST` | the manifest's `host` matches this cell's frozen box (substring test on a normalised hostname — `laptop`/`laptop-wsl`/`laptop-pop`/`pop-os` are one machine) | `manifest:host` | a cell run on the wrong box. ⚠️ the real protection is structural (disjoint `--out-subdir`s ⇒ no shared claims to race over); this proves the **sealing pass** ran on the assigned box |
| `G-N` | `n == 800`, `n_failed == 0`, `n_common >= 80%` of 400 | `summary.json` | ⚠️ a failure rate **strictly below 2%** is **REPORTED, never silently absorbed** (the `b32v64` 0.100% rust-panic precedent); at or above it the cell voids |
| `G-SAT` | `0.35 <= winrate <= 0.65` | `summary:winrate` | a **RAIL** check, not a strength bar: both sides run the same search on the same leaf at the same budget, so a winrate outside this window means the two sides are not the agents this design says they are |
| `RECON` | §1.2's witness agrees on all five statistics | `summary.json` vs raw records | ⛔ can only VOID, never move, a number |

### 4.1 ⭐⭐ THE GOLDEN GATE IS A LAUNCH PRECONDITION, NOT A GATE

[`FPU_BITEXACT.json`](FPU_BITEXACT.json) must read `PASS` before any cell runs, and `run_cells.sh`
refuses without it. It proves two things no per-cell gate can:

- ⭐ **`fpu=None` is the champion bit-for-bit** — 20 seeded games, identical action-sequence hashes
  across the pre-change and post-change source trees on **one** wheel. The round's opponent **is**
  the unmodified champion; a moved default would mean every cell grades a moved baseline.
- ⭐ **`fpu=0.2` binds** — **20/20** games diverge. ⛔ Without this half the first half is worth
  nothing: the hard-coded `None` this round removes would have passed it perfectly.

⚠️ It is a **code-path** gate at a tiny budget (`k2 × 96`). ⛔ **No number in it is a strength
measurement** and none may be quoted as one.

### 4.2 The reachable branch set, stated BEFORE the run

Recorded here so it cannot be reconstructed later: **every branch in §5 is reachable on every cell**,
including `F-NEGATIVE` and `U-VOID-INSTRUMENT`. ⛔ No branch is unreachable by construction; the
selftest sweeps a dense `(M, SE)` grid and proves it. If any pre-launch fact later makes one
unreachable, that fact is recorded **before game 1** or it does not count.

---

## 5. THE BRANCHES — PRE-REGISTERED, EXCLUSIVE, EXHAUSTIVE

Adjudicated **PER CELL**, on that cell's own realized SE, against zero, **in this order**. First
match wins. ⛔ **There is no anchor cell and no hard ordering**: three bands, three questions.

| # | branch | condition | reading |
|---|---|---|---|
| 0 | **`U-VOID-INSTRUMENT`** | any §4 gate FAILS on this cell, or any round-level gate fails | The instrument, not the world. **No reading of any kind** from this cell. Its statistics print only as a companion table under a `VOID` banner. ⭐ The other cells are unaffected |
| 1 | **`F-NEGATIVE`** | `M <= 0` **and** `z <= -2.0` | ⭐ **The knob is ACTIVELY HARMFUL at this dose.** Fully plausible and pre-registered as such: a pessimistic FPU narrowing an already well-tuned search is a real mechanism, and the M3 curve's roll-off past 0.6 is consistent with it |
| 2 | **`F-RESURRECT`** | `M >= +1.381` **and** `z >= +2.0` | ⭐⭐ **The knob is a live positive lever on the CLASSICAL champion**, at a bar no smaller than what this design can resolve. ⚠️ Licensed reading is **narrow** — see §5.1 |
| 3 | **`F-REKILL`** | `UB95(M) < +1.381` | ⭐ **The effect is BOUNDED BELOW the round's own 2σ resolution at 95%.** The never-confirmed 2026-06-02 screens do **not** reappear as a usable lever on the classical champion; `docs/LEVER_INDEX.md:146`'s CLOSED verdict **stands**, now on evidence about the right agent |
| 4 | **`F-UNRESOLVED`** | everything else | The cell did not resolve its bar in either direction. ⛔ **NOT a null.** `feedback_noisy_plateau_not_a_conclusion` binds |

⛔ **Exclusive and exhaustive by construction**, and **ordered rather than disjoint**: branch 1
requires `M <= 0 ∧ z <= -2`, which forces `UB95 <= 0 < 1.381`, so it would **also** satisfy branch 3
— which is why it is checked first. Branch 4 absorbs the remainder. ⭐ The selftest sweeps a dense
`(M, SE)` grid to prove exactly one branch fires at every point and that all four are reachable.

### 5.1 ⚠️ THE RIDERS ON `F-RESURRECT` — MANDATORY, AND THEY TRAVEL WITH EVERY CITATION

1. ⛔⛔ **IT IS NOT A REPLICATION OF THE 2026-06-02 SCREENS.** Those were a **neural** agent
   (`pathb_loop/iter_11` priors, v2.7 leaf value, `c=3.0`) at **sims 200**. No cross-era comparison
   is licensed, and §1.3 forbids the arithmetic that would make one.
2. ⛔ **IT DOES NOT LICENSE A PRODUCTION CHANGE.** One 2σ cell on a fresh band is one cell.
   `feedback_results_table_source_of_truth` requires a confirm before promotion, on a band that has
   not influenced a decision — and this band retires the moment the read-out lands (§7).
3. ⛔ **IT IS A `B=0` (ARBITER-OFF) RESULT.** `PRODUCTION.yaml` runs `B=64`. Transfer to the
   deployed, arbiter-armed champion is an **assumption**, not a measurement — and the interaction is
   not neutral in principle, since the arbiter fires on exact ties and FPU changes which ties get
   reached (DESIGN §2.3).
4. ⚠️ **IT IS A `k16 × 1376` RESULT.** FPU acts per determinization tree and `sims_per_det` is
   unchanged from the 11008 era, so the mechanism **argues** for transfer downward in `k` — but that
   is an argument (DESIGN §1.2), not a measurement, and nothing here measures it.
5. ⛔ **IT SAYS NOTHING ABOUT THE OTHER DOSE OR ABOUT `c_puct`.** Each cell is its own question, and
   §5.3's multiplicity note binds.
6. ⛔ **IT IS NOT A BRACKET.** Two doses give a direction, never an optimum
   (`feedback_bracket_hyperparams`). No interpolation between 0.2 and 0.4 is licensed.
7. ⚠️ **`elo` may never be quoted bare.** The margin is the statistic (§1.1).

### 5.2 The riders on `F-REKILL`

1. ⚠️ **`F-REKILL` BOUNDS; IT DOES NOT ZERO.** The reading is *"below +1.381 pts/deck at 95%"*,
   never *"FPU is worthless"*.
2. ⚠️ It is a bound **at this dose and this budget**, with the arbiter off.
3. ⭐ It **does** discharge the funded decision: the reopening was measured and failed, the
   `LEVER_INDEX` row is updated from *"never confirmed"* to *"measured on the classical champion and
   bounded"*, and no further FPU work is funded off the 2026-06-02 screens.

### 5.3 ⛔ THREE CELLS ARE THREE COMPARISONS

At the 2σ bar the family-wise false-fire rate under a global null is `≈ 3 × 2.3% ≈ 7%`.
⛔ **No correction is applied** — the bars are pre-registered and each cell is its own question —
**but the inflation is disclosed on every branch**, and ⭐ **a lone firing cell beside two nulls is
read as `feedback_results_table_source_of_truth`'s NOISE SIGNATURE, not as a peak.**

⛔ **No cross-cell contrast is a branch input.** The `fpu 0.2` vs `fpu 0.4` comparison is printed as a
**named companion** — a *direction*, nothing more — and it is a **cross-band** contrast, so CL-068's
1.8–2.2× over-dispersion applies to it in full.

---

## 6. ⭐⭐ THE CONDITIONAL τ PAIR — THE TRIGGER, VERBATIM AND FROZEN

> **The τ pair `{tau_p = 8, tau_p = 12}` is triggered IF AND ONLY IF `CELL_CPUCT10` passes every §4
> gate AND moves at least 2σ on its own realized SE — that is, `|z_M| >= 2.0` — in EITHER direction.**
>
> **If `CELL_CPUCT10` does not move ≥2σ — including every `F-REKILL` and every `F-UNRESOLVED` read —
> THE τ PAIR IS RE-KILLED AND IS NOT FUNDED.** That is this round's funded conditionality, and it is
> pre-registered here before game 1.
>
> **A `U-VOID-INSTRUMENT` on `CELL_CPUCT10` neither triggers NOR re-kills τ.** A broken instrument is
> not a null; the correct action is to re-run the cell, and that is an OWNER decision.

⚠️ **"Triggered" is not "funded."** The trigger makes the τ pair *eligible*; the owner funds it.

**The τ pair's frozen shape, if triggered** (`screen_lib.TAU_PAIR_SPEC`):

- Two cells, `CELL_TAU8` (`tau_p = 8.0`) and `CELL_TAU12` (`tau_p = 12.0`), champion `tau_p = 5.0`.
- **Protocol IDENTICAL to this round's**: `n=800` deck-paired (400 decks × 2 seatings) vs the
  UNMODIFIED champion, fair PIMC `k16 × 1376 = 22016` both sides, `fixed_v1` + R9, `exact_k 2`
  marginalized, rust both sides, leaf `a36d2e15a3b3d71d` both sides, tie-arbiter OFF both sides,
  **each cell on its OWN fresh band** — the next free ids at trigger time, ⛔ **not reserved here**.
- ⚠️ **PLUMBING IT WOULD NEED, NOT BUILT HERE:** `tau_p` has the **same defect `c_puct` does** —
  `--tau-p` rides `champ_cfg_dict` and therefore moves **BOTH SIDES**. A τ round needs
  `--cand-tau-p` added to `cand_search` exactly as `--cand-c-puct` was. ⛔ Deliberately not built:
  building it before the trigger fires would spend the argument that the trigger exists to make.

⛔ **No cell for the τ pair exists in `screen_lib.CELLS` and `run_cells.sh` cannot launch one.**

---

## 7. GOVERNANCE

Measurement only. On **every** branch:

- ⛔ `governance/PRODUCTION.yaml` **UNTOUCHED**. No branch licenses a production change of any kind
  — not `fpu_reduction`, not `c_puct`, not `tau_p`, not the arbiter, not the champion.
- One `experiments/results.csv` row **per cell**, citing the branch and carrying §5.1/§5.2's riders.
- ⭐ **`docs/LEVER_INDEX.md:146` is UPDATED on every branch** — it currently reads "axis CLOSED", and
  after this round it must say what was measured, on which agent, and with what bound. That row is
  the reason the next reader will or will not re-propose this lever.
- Bands `155000000000`, `156000000000`, `157000000000` retire `decision_influenced=yes`.
- ⭐ **THIS READ-RULE IS SPENT WHEN THE READ-OUT LANDS, ON EVERY BRANCH**, and the three bands retire
  from confirmatory use.
- The prior-art figures are **context in the read-out**, never a gate input, never pooled with this
  round's numbers (§1.3).

---

## 8. ⚠️ CAVEAT — WHAT THE BAR COSTS UNDER A TRUE NULL

*Appended 2026-08-30 (pre-launch multi-agent merge review, finding R4→R3). ⛔ **THE BAR DOES NOT
MOVE** — `BAR_M = 1.381` is pre-registered design and this section changes no number, no gate and no
branch. It states plainly what the design already implies, so that the read-out cannot be surprised
by it after the fact.*

**`BAR_M` is exactly `2 × se_model(400)`.** `screen_lib.sanity_check()` asserts that identity, and it
has an arithmetic consequence worth naming before game 1. `F-REKILL` fires when
`UB95 = M + 2·se_realized < BAR_M`; at a realized SE close to the modelled one this collapses to
**`M < 0`**.

So **under a true null (`δ = 0`), on this design:**

| branch | ≈ probability |
|---|---|
| **`F-REKILL`** | **≈ 48%** (`M < 0`, less the tail that reads `F-NEGATIVE`) |
| **`F-UNRESOLVED`** | **≈ 48%** (`M > 0` but short of the bar) |
| `F-NEGATIVE` | ≈ 2.3% |
| `F-RESURRECT` | ≈ 2.3% (the pre-registered false-fire rate; §5.3) |

⛔ **A true null is very nearly a coin flip between `F-REKILL` and `F-UNRESOLVED`.** Which of the two
a null cell lands on is decided by the sign of a noise draw, not by anything about FPU.

### 8.1 ⛔⛔ `F-UNRESOLVED` DOES NOT DISCHARGE THE `LEVER_INDEX` CLOSE-OUT

This is pre-committed here, **before any number exists**, precisely because the temptation after the
fact is to read a null-shaped `F-UNRESOLVED` as if it were `F-REKILL` — they are the same underlying
world half the time. It is not licensed:

1. ⛔ **`F-UNRESOLVED` is NOT a null** and is not a bound. §5's branch 4 is *"the cell did not resolve
   its bar in either direction"*, and `feedback_noisy_plateau_not_a_conclusion` binds. Only
   `F-REKILL` returns a real 95% upper bound, and only `F-REKILL` carries §5.2's clause 3 — the one
   that discharges the funded decision.
2. ⛔ **`docs/LEVER_INDEX.md:146` is still UPDATED** (§7 says *on every branch*), but on
   `F-UNRESOLVED` it is updated to say **the reopening was measured and did not resolve** — never to
   say the axis was re-closed, and never to say the 2026-06-02 screens were refuted.
3. ⛔ **`RIDERS_F_UNRESOLVED` (in `screen_lib.py`) GOVERN** the read-out and travel with every
   citation, exactly as §5.1/§5.2's riders do. On `CELL_CPUCT10` the §6 τ trigger is unaffected:
   `F-UNRESOLVED` still **re-kills** the τ pair, because that trigger is `|z| ≥ 2` and is a **funding**
   decision, not a scientific one.

### 8.2 ⭐ THE PRE-COMMITTED PRICE OF `F-UNRESOLVED`

**A cell that reads `F-UNRESOLVED` is re-runnable ONLY on a NEW BAND and ONLY with fresh owner
funding.** Stated now so the cost is known before it is incurred:

- ⛔ **The band is spent either way.** §7 retires all three bands `decision_influenced=yes` when the
  read-out lands. An `F-UNRESOLVED` cell **may not be extended, topped up, or re-read at larger `n`
  on its own band** — that is the `rodv3` failure mode (`n` bought after seeing the sign), and
  CL-068's cross-band over-dispersion means the extension could not be pooled with the original
  anyway.
- ⛔ **This read-rule is spent when the read-out lands, on every branch** (§7). A re-run is a **new
  round** needing a new pair, a new band claim, and the owner's funding — it is not a continuation of
  this one.
- ⚠️ **The honest description of that outcome is "this round bought no verdict on this cell."** It is
  a real possibility at ≈48% under a true null, it is disclosed here rather than discovered later,
  and no reading stronger than §5's branch-4 text may be taken from it.
