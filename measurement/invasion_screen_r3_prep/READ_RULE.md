# INVASION-RISK TERM FAMILY — ROUND-3 FINE LADDERS + JOINT AT 2752 — READ RULE

> **STATUS: FROZEN** (2026-08-27). This document and [`DESIGN.md`](DESIGN.md) are **the pair**, and
> the pair is law. ⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every bar, every gate,
> every branch and every prohibition below exists **before any game does**.
>
> If [`analyze_screen.py`](analyze_screen.py), [`screen_lib.py`](screen_lib.py) or
> [`run_cells.sh`](run_cells.sh) disagrees with this document, **it is the code that is wrong.**
>
> ⚠️ **After game 1 there is no amendment route.** Round 2 had to take the only one that exists:
> freeze the verdict as it stands, record the defect, and get the OWNER to authorise a re-read of the
> SAME archive under a named, minimal, single-clause correction
> ([`AMENDMENTS.md`](AMENDMENTS.md) IS-A1).

**Band `153000000000` · 8 cells · 3200 decks / 6400 games · k4×688 = 2752 both sides · local W=14 +
laptop W=22, concurrent.**

⭐ **The owner constraint this round carries, verbatim: "limit local to w14 starting at 11am"
(2026-08-27).** `W_LOCAL` is frozen at 14 for the whole round. ⚠️ It moves wall clock and the
cell→box assignment and **no bar, no gate and no branch** — `W` is throughput-only, games are
bit-identical at any `W`, and **no gate in this pair reads a clock**.

---

## 1. THE STATISTIC

**Per cell, PRIMARY:**

```
D(deck) = ( diff(deck, a_seat=0) + diff(deck, a_seat=1) ) / 2
D       = mean over decks appearing in BOTH seatings
SE      = sample sd (ddof=1) / sqrt(n_paired)
z       = D / SE
```

`diff` is the harness's own final-score margin, **candidate minus opponent, in POINTS**
(`eval_fair_puct.py:1603`). **`D > 0` ⇒ the CANDIDATE won.** A deck missing a seating is **DROPPED**,
never defaulted to zero, and shows up as a short `n_paired` at `G-DECKS`.

⛔ **Adjudicated AGAINST ZERO, at the cell's OWN REALIZED SE.** The frozen `σ_D = 14.67` sizing model
is **power arithmetic only** and is **never a denominator in a branch test**.

⛔ **A CROSS-CELL CONTRAST IS NEVER A BRANCH INPUT.** The eight deck ranges are **disjoint**. The
**only** pre-registered exceptions are §4.5's within-shape scaling contrast and §4.5b's within-shape
interior lift — and **neither is a branch input either**.

### 1.1 `RECON` — the witness

`screen_lib.paired_margin()` is a **deliberately independent re-implementation** of
`eval_fair_puct._paired_z`, not an import of it (an imported one would agree by construction and
witness nothing), accumulated with `math.fsum` rather than `sum`. It recomputes
`paired_mean_margin`, `paired_z`, `n_paired`, `winrate` and `elo` **from the raw records** and
compares against `summary.json` at rel 1e-6 / abs 1e-9. ⛔ **It can only VOID, never move, a number.**

### 1.2 ⛔ ROUNDS 1 AND 2 ARE DESCRIPTIVE OVERLAYS ONLY

Round 1's mids were played on band `151000000000` and round 2's seven cells on `152000000000`; this
round is on `153000000000`. **CL-068 measured 1.8–2.2× over-dispersion on cross-band contrasts, in
BOTH the elo and the deck-paired-margin statistics**, with an identity control exonerating the
harness and the "different decks" explanation arithmetically excluded.

⛔ **NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT.** ⚠️ **THREE BANDS NOW**, so there are
**two** tempting pools rather than one, and **both** are forbidden — and the most tempting of all is
pooling a round-3 rung with the round-2 reading at a nearby weight, which is exactly why §3.2 of the
design chose weights that **repeat no prior point**.

⭐ **The one thing the overlays legitimately did** was fix **where** round 3 measures
(`DESIGN.md` §3.2). Choosing where to look is a **design act**; combining readings is a statistical
one. That use was spent **before any round-3 number existed**, and **no round-3 branch reaches back
into it**.

---

## 2. THE CELLS, AND WHAT EACH ONE ASKS

| cell | box | dose | opponent | asks | chain-eligible? |
|---|---|---|---|---|---|
| `A_LOW` / `A_MID` / `A_HIGH` | laptop | β 0.02 / 0.05 / 0.10 | **champion** | does an offence tilt at a *light* β beat the champion, and where does it peak? | ⭐ yes |
| **`J_LOW` / `J_HIGH`** | laptop | **β 0.02 + γ 0.03** / **β 0.05 + γ 0.07** | **champion** | ⭐⭐ **does the PACKAGE beat the champion?** | ⭐⭐ **yes** |
| `C_LOW` / `C_MID` / `C_HIGH` | local | γ 0.03 / 0.07 / 0.15 | ⭐ **shape-B invader** | does the defence pay **against the exploit**, and where does it peak? | ⛔ **never** |

---

## 3. THE NINETEEN GATES

⛔ **ABSENT IS FAIL. Never a skip, never a default.** Every gate resolves across **both** documents
(`config.*` in `manifest.json`; statistics in `summary.json`, which carries **no config block at
all**) and prints **which document and which address** answered. A value found at **no** address is
`ABSENT`, and `ABSENT` is `FAIL`.

⛔ **A FAIL ON ANY GATE MAKES THAT CELL `U-UNREADABLE`**, and `U-UNREADABLE` is checked **first** in
the per-cell branch table.

| id | what it asserts | address | fires on |
|---|---|---|---|
| `G-BAND` | `config.band_seed_start` == this cell's frozen `seed_start`; `n_decks` == 400; `seatings_per_deck` == 2 | `manifest:config.*` | any deviation |
| `G-DECKS` | every realized seed inside **this cell's own** range; no deck at one seat only; `n_common` == 400 | raw `seed*_a*.json` | a seed outside the range, a half-paired deck |
| `G-SINGLEVAR` | (a) the two sides' search knobs are **identical** across the frozen alias table; (b) **TWO-SIDED SET EQUALITY** — `cand_leaf_cfg` and `opp_leaf_cfg` differ in **exactly** this cell's frozen key set: **ONE** key on an A cell (`invasion_beta`), ⭐ **TWO** on a J cell (`invasion_beta`, `invasion_gamma`), **THREE** on a C cell (`invasion_alpha`, `invasion_alpha_cap`, `invasion_gamma`) | `manifest:config.champion.*` vs `config.opponent.*`; `config.cand_leaf_cfg` vs `config.opp_leaf_cfg` | an EXTRA differing key, **or** an expected key identical on both sides. ⚠️ The opponent's search knobs live one level down under `config.opponent.champ_cfg.*` — a gate written from the design rather than from a real manifest would void every healthy cell |
| `G-LEAF` | ⭐ **PER-CELL AND TWO-SIDED.** Four conjuncts, implemented ONCE in `screen_lib.leaf_gate()`: **(a)** `config.opp_leaf_hash` == this cell's **pinned opponent hash** — `a36d2e15a3b3d71d` on A and **J**, `42adadc988784b44` on C; **(b)** `config.cand_leaf_cfg.v29_meeple_curve` == curve125; **(c)** `config.cand_leaf_hash` == this cell's **OWN PINNED HASH, EXACTLY** — `A_LOW e62afec3a84dfabd` · `A_MID 9da236cf49065a21` · `A_HIGH 1fed3422b67be1d5` · **`J_LOW 9e2764605c0b2fff`** · **`J_HIGH d193865634f14543`** · `C_LOW 86a6efb793a40ef2` · `C_MID f05d8576b7a6cc23` · `C_HIGH a8e9083b102a52cf`; **(d)** the two sides are **DIFFERENT leaves** | `manifest.json` → `config.cand_leaf_hash`, `config.opp_leaf_hash`, `config.cand_leaf_cfg` | any deviation. ⛔ **THIS GATE IS THE ONLY THING LEFT STANDING, AND THAT IS WHY IT IS EXACT.** `--allow-leaf-hash-drift` is a **single** flag that downgrades `_assert_netprior_leaf` to a warning on **BOTH** sides (`:3763` candidate, `:3777` opponent), and round 3 passes it on **all eight** cells. On a C cell "the opponent drifted" is EXPECTED and therefore not a tell; ⭐ on a J cell "the candidate moved off the champion" is satisfied by a leaf carrying only ONE of its two knobs. Only exact equality against a pre-registered pin distinguishes the intended leaf from a wrong one |
| `G-INVASION` | **BOTH SIDES, per cell.** The candidate's FULL `asdict` block carries **exactly** its frozen knob(s) at their frozen values with every other invasion field at default; the two `_leaf_dict` blocks (normalised so "absent" == "default") equal the cell's frozen `cand_invasion` / `opp_invasion` | `manifest:config.champion.leaf_cfg` + `config.cand_leaf_cfg` + `config.opp_leaf_cfg` | a wrong value; a second weight nonzero; ⭐ **a J candidate carrying only one of its two knobs**; an A or J cell whose opponent GAINED an invasion key; a C cell whose opponent block is EMPTY (the env regime did not reach the harness) or whose candidate INHERITED the env (the explicit zeros did not land) |
| `G-CAPFWD` | **BOTH SIDES.** `(cap == 0.0 or alpha != 0.0)` and `(stub == 2 or alpha != 0.0)` | as above | an INERT shape-B knob set without a nonzero alpha, which `leaf_config_rs` would **silently drop** while the manifest still showed it — a manifest that lies about the running leaf |
| `G-WHEEL` | `carc_rs_build` present · `carc_rs_binary_sha` present · `mixed_builds` is `false` · `WHEEL_PROBE.json` satisfies **every** required key including ⭐ `joint_two_knob_forward_ok` · the build's embedded rev is one at which `invasion.rs` **exists** and is an **ancestor** of the branch tip | `manifest` + `WHEEL_PROBE.json` + git ancestry | a stale wheel. ⚠️ `carc_rs_version` is permanently "0.1.0" and is NOT a discriminator |
| `G-WHEEL-SAME` | ⭐ **ROUND-LEVEL.** `carc_rs_binary_sha` == `a9ac686bca1417f9` | `manifest:carc_rs_binary_sha` | a changed wheel **or a different box** (the sha is box-local). ⛔ **A FAIL ON ANY CELL VOIDS EVERY CELL** — round 3 carries **no IDENT cell**, it INHERITS round 1's (for the second time; round 2 carried it once and it held 7/7), and the inheritance is valid **only while the wheel that proved it is the wheel that plays**. A changed wheel **RE-OWES AN IDENT CELL** |
| `G-HOST` | the manifest's `host` matches this cell's **frozen box** (substring test on a normalised hostname — `laptop` / `laptop-wsl` / `laptop-pop` / `pop-os` are one physical machine) | `manifest:host` | a cell run on the wrong box. ⚠️ It proves the **sealing pass** ran on the assigned box, not that every record did — the real protection is structural (disjoint cells ⇒ disjoint `--out-subdir`s ⇒ no shared claims to race over) plus the launcher's up-front refusal |
| `G-RULES` | `rules_profile.name == "fixed_v1"`, `r9_env_ok` and `r9_env_observed` both `true` | `manifest:rules_profile.*` | R9 not latched |
| `G-BACKEND` | `name == requested == "rust"`, `mixed_builds false`, `converted_sides == {candidate, opponent}` | `manifest:config.backend.*` | ⛔ a python leg would RAISE on a nonzero weight or, on a stale-wheel path, serve an invasion-BLIND leaf that reads as a null. ⚠️ needed on the OPPONENT side as much as the candidate's — the C cells' opponent carries a nonzero weight |
| `G-BUDGET` | both sides `(k_dets, sims_per_det, total_sims) == (4, 688, 2752)` **and the product multiplies out** | `manifest:config.champion.*` / `config.opponent.*` | any asymmetry |
| `G-TIEARB` | (a) `cand_tiearb.enabled` absent or `false`; (a2) **no** terminal `*.tiearb_enabled` is `true`; (b) **no stray tiearb CONTAINER** other than `cand_tiearb` | `manifest` | an armed arbiter. ⚠️ (b) scans **container** segments only — a healthy archive emits a TERMINAL `config.champion.tiearb_enabled=false`, which (a2) checks instead |
| `G-EXACT` | both sides `exact_k == 2` and `mode == "marginalized"` | `manifest:config.endgame.*` / `config.opponent.endgame.*` | K=3/4 are clairvoyant-only |
| `G-REV` | **(i)** the manifest's short `code_rev` **names** its own box's `PINNED_SRC_REV` (≥7-hex **prefix** rule; the whole-tree `-dirty` marker is **INFORMATIONAL**, never fatal); **(ii)** `SRC_CLEAN.jsonl` records the **code paths** clean at **every** boundary, with a `pre-flight` boundary and an `after-…` boundary per cell; **(iii)** ⭐⭐ **THE CROSS-BOX CLAUSE, §3.6** | `manifest:code_rev` + each box's `PINNED_SRC_REV` + `SRC_CLEAN.jsonl` | a mixed-rev round (the `track_d2_prep` defect) |
| `G-BLIND` | `BLIND_COMMIT` is a 40-hex sha, an **ANCESTOR** of HEAD, the commit that **INTRODUCED** this pair's FROZEN banner, agreed by `BLIND_PROOF.json` against a **live** git re-check, and **stamped into every adjudicated manifest** as `--stamp-key BLIND_COMMIT` | `manifest:BLIND_COMMIT` + `BLIND_PROOF.json` + git | a read that was not blind |
| `G-N` | `n == 800`, `n_failed == 0`, `n_common >= 320` (80% of 400) | `summary.json` | ⚠️ a failure rate **strictly below 2%** is **REPORTED, never silently absorbed** (the `b32v64` 0.100% rust-panic-class precedent); at or above it the cell voids |
| `G-SAT` | `0.35 <= winrate <= 0.65` | `summary:winrate` | a **RAIL** check, not a strength bar: both sides are the same search differing only by the pre-registered leaf terms, so a winrate outside this window means the two sides are not the agents this design says they are |
| `RECON` | §1.1's witness agrees on all five statistics | `summary.json` vs raw records | ⛔ can only VOID, never move, a number |

### 3.4 — the round-level gate

`G-WHEEL-SAME` is computed **per cell** (every manifest carries the fingerprint) but **a FAIL on ANY
cell voids EVERY cell**, because the proposition is about *the wheel the round ran on*, not about one
archive — exactly as a failed `G-IDENT` voided all four of round 1's cells.

### 3.5 — the SMOKE's pinned allowed set

`--smoke-mode` PASSES **iff** the only failures are:

```
G-BAND · G-DECKS · G-N · G-SAT · G-HOST · RECON/n_paired
```

Each is listed because a 16-game throwaway archive on a disjoint range **cannot satisfy it by
construction**, and each carries a stated mechanical reason in `screen_lib.SMOKE_ALLOWED_REASONS`.
⛔ **`G-WHEEL-SAME` IS NOT IN THE SET** — the smoke runs the same wheel the cells will, so it must
PASS there. ⛔ **Nor are `G-REV` or `G-BLIND`** — which is why the smoke writes its own launch
artifacts and carries the blind stamp exactly as a real cell does. **A failure OUTSIDE this set is a
LAUNCH BLOCKER.**

⚠️ `G-HOST` is excused **only** because `--smoke-mode` is handed a directory and each box smokes a
**different** cell's config, so the smoke cell's frozen `box` is not necessarily the box that ran it.
⛔ **The property is not unchecked:** the launcher refuses any cell not in `cells_of_box(--host)`
before a game starts, and `G-HOST` is **fully enforced on every REAL cell**.

### 3.6 ⭐⭐ `G-REV`'s CROSS-BOX CLAUSE — THE IS-A1 FOLD

**The proposition:** *both boxes were at one commit, and every cell ran at it.*

**⛔ HOW IT IS NOT ASKED.** Round 2's frozen adjudicator compared the two boxes' **emitted short
revs** for string equality. `git rev-parse --short` picks its length **per clone**, so two boxes at
the **identical** commit emitted `240626a3-dirty` and `240626a31f-dirty` and the round **falsely
voided** ([`AMENDMENTS.md`](AMENDMENTS.md) IS-A1). **The lesson, verbatim: *canonicalize revs against
the pin, never rev-vs-rev.***

**⭐ HOW IT IS ASKED** (`screen_lib.cross_box_rev_gate()`, two conjuncts, in order):

1. **THE PINS AGREE.** Every box role that published a `PINNED_SRC_REV` must publish the **same**
   40-hex sha. ⛔ A missing or malformed pin is **FAIL** — ABSENT is FAIL, and there is **no fallback
   to comparing the emitted revs to each other**.
2. **EVERY EMITTED REV CANONICALIZES TO THAT PIN** — strip `-dirty`, require ≥ 7 hex characters,
   require a **PREFIX** match against the shared pin.

⚠️ **Consequences, stated:** short revs of **different lengths** both PASS; a **different commit**
FAILS; **disagreeing pins** FAIL with a message that says explicitly *this is the pins disagreeing,
not the short revs*, so the next reader cannot repeat IS-A1; a sub-7-hex rev FAILS. A single-box run
and the §9 smoke pass conjunct 1 trivially with one pin, which is correct — there is no cross-box
proposition to check.

⛔ **A FAIL VOIDS `G-REV` ON EVERY CELL**, and therefore the round.

---

## 4. THE BRANCHES

### 4.1 — per cell, FIRST-MATCH-WINS

| branch | condition |
|---|---|
| `U-UNREADABLE` | **checked FIRST** — any gate FAIL on the cell (or a round-wide `G-WHEEL-SAME` fail), or no computable `z` |
| `PROMOTE` | `z >= +2.0` |
| `BRACKET` | `+1.0 <= z < +2.0` |
| `REVERSED` | `z <= -2.0` |
| `NULL` | everything else (`-2.0 < z < +1.0`) |

⚠️ The bars are closed at exactly their stated endpoints: exactly `+2.0` PROMOTES, exactly `+1.0`
BRACKETS, exactly `−2.0` REVERSES.

⛔ **THE LABEL MEANS DIFFERENT THINGS ON DIFFERENT CELLS**, and the per-cell table returns only the
raw ladder position — §4.2 applies the meaning:

- on an **A** cell, `PROMOTE` is an offence reading against the **champion** and **is**
  adoption-chain-eligible;
- ⭐⭐ on a **J** cell, `PROMOTE` is a reading of the **PACKAGE** against the champion, **is**
  adoption-chain-eligible, and ⛔ says **NOTHING** about either knob separately (§4.6b);
- ⛔ on a **C** cell, `PROMOTE` is **not** a promotion into the chain at all — C's opponent is a
  shape-B **invader**. §4.2 re-labels it `DEFENDS-C` and §4.6's prose is mandatory.

### 4.2 — the ROUND branch, FIRST-MATCH-WINS

| branch | condition | what it licenses |
|---|---|---|
| `U-UNREADABLE` | any cell unreadable | ⛔ **nothing.** Fix the instrument. `G-WHEEL-SAME` or the §3.6 cross-box clause voids all eight |
| `PROMOTE-<shapes>` | some **CHAIN-ELIGIBLE** cell (**A** or **J** — opponent == the champion of record) reads `z >= +2.0`. The J shape is spelled **`JOINT`**; multiple shapes are listed comma-separated **in CELL order** | ⭐ **ONE production-budget H2H per firing shape**, per the frozen four-link chain — and for `JOINT`, of **that leaf, at that weight pair, AS ONE LEAF** (§4.6b). Each H2H is a fresh pair, a fresh band, a fresh funding decision |
| `DEFENDS-C` | no chain-eligible promote, but some **C** cell reads `z >= +2.0` | ⛔ **C-family only. NEVER the adoption chain** (§4.6). ⭐ And the partnered follow-up a firing C would have licensed **is already running as this round's J cells**, so it licenses **no new action beyond what the J cells already carry** |
| `BRACKET-CONTINUE` | nothing at `+2.0`, but something at `>= +1.0` | names what a **round 4** would need and its cost (§4.8) |
| `REVERSED-<shapes>` | nothing at `>= +1.0`, but some cell reads `z <= -2.0` | ⚠️ a **real finding**, not a gate failure. ⛔ It does **not** license flipping a term's sign |
| `FAMILY-PARKS` | every cell reads `z < +1.0` and nothing REVERSED | ⛔ **parks the FORMULAS, never the MECHANISM** (§4.8) |

⛔ **Listing two shapes is NOT two confirmations of one effect and NOT an additive claim.** Each cell
was adjudicated against zero, on its own disjoint decks. ⛔ **And if both `A` and `JOINT` fire, that
is still not an attribution of the joint margin to β** — they are different leaves on different
decks.

### 4.3 — MANDATORY OUTPUT on every branch

1. **Per cell:** `D`, `SE`, `z`, 95% CI, winrate, W/D/L, elo, both realized leaf hashes beside both
   pins, box, `n_common`, `n_failed`, branch.
2. **Realized vs modelled SE**, with the `[0.70, 1.43]` flag and its **direction**. ⚠️ Reported,
   **never** a branch input; a LOW-end flag is EXPECTED (rounds 1 and 2 realized 0.714–0.885).
3. **The guarded elo limb** (§4.4), labelled.
4. **The power table at BOTH dispersions, and §4.2's headline caveat.** ⛔ **A NULL IS A BOUND, NOT A
   ZERO** — the bound is the cell's 95% CI.
5. **All nineteen gates, every cell**, with the address each resolved at.
6. **The cost multiplier**, descriptive-only.
7. **The frozen inputs AND the full weight derivation** (`DESIGN.md` §3.2), including the C
   derivation's two disagreeing readings and its weakest input.
8. **The ladder as run**, with `B` and `D` shown as NOT RUN.
9. ⭐ **§4.6's defence reading on every C cell, and §4.6b's joint reading on every J cell** — on
   **every** branch, including the nulls.
10. **§5's no-over-read list in full, and §6's stated prior.**

### 4.4 — elo is display-only, and the conversion is guarded

`|z| >= 2.0` ⇒ limb **"own-ratio"**: this cell's realized `elo/D` is reportable, cross-checked
against the in-family bracket `[16.74, 19.35]`; a reading outside it is **FLAGGED as a witness
anomaly** and is **never** a branch input. Otherwise ⇒ limb **"pinned-bracket"**: the cell's own
ratio is **NOT reportable** and must not be printed as a scale — under a null `D ≈ 0`, so `elo/D` is
a quotient of two independently-noisy near-zero quantities whose **sign is not stable**.

### 4.5 — the pre-registered WITHIN-SHAPE SCALING contrast

```
Δ_shape = D_high − D_low         SE = sqrt(SE_high² + SE_low²)         z = Δ / SE
```

Resolves at **2σ**. ⚠️ The rungs are on **disjoint** deck ranges, so this is an **unmatched**
difference of independent samples and the root-sum-square SE is the right one; the price, stated
before any number: **2σ-resolvable only at |Δ| ≥ 2.075 pts/deck (frozen model) / 1.705 (round 2's
realized dispersion)**.

⛔ **NOT A PROMOTION INPUT.** A SHAPE reading and a round-4 input. ⚠️ On the **J** ladder it prices
the **dose of the PAIR** and cannot say which knob's dose mattered — both move together.

### 4.5b ⭐ the pre-registered WITHIN-SHAPE INTERIOR LIFT — new in round 3

```
lift = D_mid − (D_low + D_high)/2     SE = sqrt(SE_mid² + (SE_low² + SE_high²)/4)     z = lift / SE
```

Resolves at **2σ**: **|lift| ≥ 1.796 pts/deck (model) / 1.477 (realized)** — **tighter** than §4.5,
because averaging the two neighbours halves their variance contribution.

⭐ **This is the statistic a fine ladder owes, and round 3 is the first round that can compute one.**
A and C each run three rungs on ONE band, so *"is the optimum strictly INSIDE the bracket?"* is
finally answerable.

| verdict | reading |
|---|---|
| **INTERIOR PEAK RESOLVED** (`lift > 0`, `|z| >= 2`) | the optimum is **inside** this ladder — the bracket holds and §4.7's endpoint rule is **satisfied** for this shape |
| **INTERIOR TROUGH RESOLVED** (`lift < 0`, `|z| >= 2`) | ⚠️ the interior rung reads **below** the average of its neighbours by >2σ — the shape is **not single-peaked** over this bracket, and no "the optimum is at the mid" reading survives |
| **INTERIOR LIFT UNRESOLVED** | ⛔ **§4.7's ENDPOINT RULE STAYS IN FORCE**: a peak at either end of this ladder is **NOT bracketed** |
| **NOT APPLICABLE** | the shape has no interior rung — the **J** ladder. §4.7 governs it instead |

⛔ **NOT A PROMOTION INPUT.** ⛔ **AND IT IS NOT §4.7's NOISE-SIGNATURE CHECK** — that one is a >1σ
**RE-MEASURE trigger** on `z`, not an estimate with a CI. They can disagree, and **where they do the
re-measure obligation WINS**.

### 4.5c — the overlay plot

Rounds 1, 2 and 3 are drawn on one axis, per shape, labelled by band. ⛔ **NEVER pooled, NEVER
z-combined, NEVER a branch input** (§1.2). ⚠️ **No prior round has a JOINT point at all** — the J
shape has no overlay.

### 4.6 ⭐ SHAPE C READS DEFENCE, NOT STRENGTH

⛔ **C's opponent is an INVADER, not the champion of record.** `SHAPES.md` §3 makes shape C
defence-only and not antisymmetric, so a C-vs-champion cell is a guaranteed-uninformative null.
**A POSITIVE C MARGIN MEANS THE DEFENCE PAYS AGAINST THE EXPLOIT** — it does **not** mean the agent
is stronger, and it says nothing about play against the champion of record or against any
out-of-lineage opponent.

⚠️ **And the invader is a DEMOTED shape, which changes nothing about its use as an instrument**
(`DESIGN.md` §2.6). ⛔ **No branch may say anything about shape B AS A CANDIDATE.**

⛔ **C NEVER PROMOTES PAST ITS OWN FAMILY.** A firing C cell does **not** enter the four-link chain,
because link 1 is defined as a screen **against the champion**. ⭐ The partnered follow-up round 2
licensed **is already running as this round's J cells**, so a firing C in round 3 licenses **no new
action**. ⛔ **No C reading of any size licenses a production H2H, a `governance/PRODUCTION.yaml`
change, or a champion-of-record discussion.**

`screen_lib.c_reading()` is **mandatory prose beside every C result, on every branch.**

### 4.6b ⭐⭐ THE JOINT CELLS — WHAT THEY LICENSE, AND THE ATTRIBUTION BAN

**A joint cell is ONE LEAF, NOT TWO TERMS.** One `LeafConfig`, one leaf hash, one opponent — the
**champion of record**. It asks exactly one question, *does this leaf beat the champion at 2752*, and
its deck-paired margin against zero answers exactly that and no other.

⭐ **`z >= +2.0` fires `PROMOTE-JOINT` and licenses the production-budget H2H**, per the frozen
four-link chain, because its opponent **is** the champion and link 1 is defined as a screen against
the champion. ⛔ **IT LICENSES ONE THING: a production H2H of THAT LEAF, AT THAT WEIGHT PAIR, AS ONE
LEAF.** Not a `PRODUCTION.yaml` edit. Not a champion-of-record discussion. Not an H2H of either knob
alone. The H2H is a fresh pair, a fresh band, a fresh funding decision.

⛔⛔ **THE ATTRIBUTION BAN.** A joint cell moves **two knobs at once**, so its margin is a property of
the **PAIR (β, γ)** and carries **NO information about which knob supplies it**. A firing J cell is
consistent with *"β does all of it"*, with *"γ does all of it"*, and with **every** mixture —
including one where a term that is **negative alone** is carried by a partner that is strongly
positive. **FORBIDDEN, EXPLICITLY:**

1. reading a J margin as evidence for shape **A** or for shape **C** separately;
2. **subtracting** an A cell's margin from a J cell's to "recover" γ, or vice versa — those cells are
   on **disjoint deck ranges** and §1 forbids cross-cell contrasts as branch inputs, so that
   difference is **not even a pre-registered statistic**, let alone an attribution;
3. reading a **NULL** joint as evidence **against** either term;
4. describing a joint margin as the **SUM** of the two marginal margins, in either direction.

⭐ **ATTRIBUTION IS A LATER QUESTION AND IT HAS A NAMED ANSWER:** a two-cell **ABLATION** pair on a
**fresh band** — the joint leaf with β zeroed, and the joint leaf with γ zeroed, both against the
champion, deck-matched. ⛔ **That is not what this round bought**, and a readout that attributes is
**wrong on the design**, not merely on the emphasis.

⚠️ **On (4), and it cuts both ways.** §4.3(4)'s power table publishes an "additive" row (Δ = +1.94,
the arithmetic sum of round 2's two BRACKET readings) as **the effect size the joint cell is SIZED
against** — sizing needs a number and that is the honest one. ⛔ **Publishing it as a sizing target
is not predicting it, and observing it would not confirm additivity**: one cell at n = 400 cannot
distinguish additive from sub-additive-plus-noise from a single dominant term.

`screen_lib.joint_reading()` is **mandatory prose beside every J result, on EVERY branch INCLUDING
THE NULLS** — because the tempting over-read of a null ("so neither term works") is the same error in
the other direction.

### 4.7 — THE LADDER RULES

⭐ **BOTH A AND C ARE GENUINELY BRACKETED THIS ROUND, AND THAT IS NEW.** Three points each on ONE
band, so each has a real INTERIOR rung, §4.5b is computable for both, and the noise-signature rule
applies to both **literally**. Round 2 could say that of C only.

⛔ **THE ENDPOINT RULE HAS NOT BEEN REPEALED; IT HAS BEEN GIVEN SOMETHING TO BITE ON.** A peak at
`A_LOW` (β 0.02), `A_HIGH` (β 0.10), `C_LOW` (γ 0.03) or `C_HIGH` (γ 0.15) is **still at an endpoint
and still NOT BRACKETED** (`feedback_bracket_hyperparams`). The licensed intervals leave headroom on
purpose — β **[0.01, 0.02]** and **[0.10, 0.12]**, γ **[0.02, 0.03]** and **[0.15, 0.23]** — so an
endpoint peak has somewhere to be extended INTO **without re-opening the licence**.

⛔ **THE JOINT LADDER HAS TWO POINTS AND THEREFORE NO INTERIOR.** Every J reading sits at an endpoint
**by construction**. A `PROMOTE` at `J_HIGH` licenses the production H2H **at that weight pair** and
owes a ladder extension **upward** before any claim about a joint optimum; a `PROMOTE` at `J_LOW`
owes one **downward**. ⛔ No branch may say *"the joint optimum is at (0.05, 0.07)"* or *"the joint
effect is monotone in dose"* from two points.

⛔ **THE NOISE-SIGNATURE RULE, on EVERY interior rung** (two this round): **a lone value that beats
BOTH its neighbours by >1σ in `z` is a NOISE SIGNATURE, not a peak.** It is **RE-MEASURED before it
is believed** and is **never promoted from the single screen**
(`feedback_results_table_source_of_truth`, CLAUDE.md's n-thresholds). ⚠️ **This is exactly what
demoted shape B**: round 1's `B_MID` read +0.7575 between two round-2 rungs reading −0.6175 and
+0.0225. ⛔ It never moves a branch; it attaches a **RE-MEASURE obligation** to one.

### 4.8 — what a `BRACKET-CONTINUE` or a `FAMILY-PARKS` costs and means

**`BRACKET-CONTINUE`** names what a round 4 would need and its cost, in the readout: which rung
bracketed, whether §4.5b resolved an interior peak, whether §4.7's endpoint rule is in force for that
shape, and which headroom interval an extension would spend. ⛔ **It licenses nothing by itself** —
round 4 is a fresh pair, a fresh band and a fresh funding decision.

**`FAMILY-PARKS` PARKS THE FORMULAS, NEVER THE MECHANISM.** What would be parked is **this
parameterisation** of `T_A` and `T_C` at **these weights** at **2752**: three rounds, three bands, and
no dose of either formula resolved against the champion. ⛔ **It is NOT a finding about invasion risk
as a phenomenon.** The E4 record stands untouched — the owner's farm-steal mechanism was **measured
on-device** in Stage A and the champion is behind the owner at phone conditions with one missing leaf
term named. A parked formula means *"this arithmetic did not capture it"*, and the named next move is
a **DIFFERENT SHAPE** (`SHAPES.md` §3's un-normalised variant is the standing candidate), not more
weights on these two.

⛔ **And no branch reads a `FAMILY-PARKS` as a refutation of round 2** — §4.2's power arithmetic says
a +1.0 effect is caught ~1 time in 3.

---

## 5. WHAT NO BRANCH DOES

⛔ Printed **in full on every branch**. The canonical list is `screen_lib.NO_BRANCH_DOES`; this is it.

1. No branch reports a **production** result — 2752 is the SCREENING budget, production is 11008.
   Screens aim, they don't verdict.
2. No branch **ranks the cells** against each other — the eight deck ranges are DISJOINT and §1
   forbids any cross-cell contrast as a branch input. The only pre-registered exceptions are §4.5 and
   §4.5b, and **neither is a branch input either**.
3. ⛔⛔ **No branch reads a JOINT cell as evidence about `invasion_beta` OR `invasion_gamma`
   SEPARATELY**, in either direction, at any `z`. §4.6b. **This is round 3's headline over-read and
   it is forbidden explicitly.**
4. ⛔ No branch treats a joint margin as the **SUM** of an A margin and a C margin, nor subtracts one
   from another to "recover" a term. The +1.94 power row is a **SIZING TARGET, not a prediction**.
5. ⛔ No branch **pools, z-combines or averages** a round-3 cell with a round-1 or round-2 reading.
   **THREE BANDS NOW** — two tempting pools, both forbidden (CL-068).
6. ⛔ No branch **identifies a round-3 cell with the round-2 cell of the SAME NAME**. `A_LOW` was
   β 0.04 on 152e9 and is β 0.02 on 153e9; `C_MID` was γ 0.23 and is γ 0.07. The names repeat; the
   weights, the band and the box do not.
7. ⛔ No branch reads a **C margin as STRENGTH**. §4.6.
8. ⛔ **No C reading of any size** enters the four-link chain, licenses a production H2H, edits
   `governance/PRODUCTION.yaml`, or opens a champion-of-record discussion.
9. ⛔ No branch says anything about **shape B AS A CANDIDATE**. ⚠️ Its continued use as the C cells'
   invader-generator **instrument** is not a claim about it as a candidate.
10. No branch says anything about **shape D** at any weight other than round 1's mid.
11. No branch treats **A and D as independent** — `T_A == (cities+roads part) + T_D` exactly.
12. ⛔ No branch says *"the optimum is at X"* from an **ENDPOINT**. §4.7.
13. No branch uses the **ms/move ratio** as evidence of anything but COST.
14. No branch **pools this band with any other**; `153000000000` retires from confirmatory use once
    it has influenced a decision.
15. ⛔ No branch reads a **`FAMILY-PARKS`** as a refutation of round 2, or as a finding about the
    mechanism. §4.8.
16. ⛔ No branch reads this round **past a failed `G-WHEEL-SAME`**.
17. ⭐ No branch compares a **LOCAL cell to a LAPTOP cell**. None needs to — shapes are assigned
    whole, so every §4.5 contrast, every §4.5b lift and every §4.7 noise check is within-box. The
    same wheel file and the same `code_rev` make such a comparison plausible, but this round
    deliberately never validated it and **no branch may rest on it**.
18. ⛔ No branch treats **`W_LOCAL=14`**, the **measured laptop ratio (1.0935)**, or the joint leaf's
    realized per-move cost as anything but **COST**. No gate in this pair reads a clock.
19. ⛔ No branch **re-derives the weights after the fact**. The derivation is `DESIGN.md` §3.2 /
    `screen_lib.WEIGHT_DERIVATION`, recomputed at import from frozen inputs, written before any
    round-3 number existed.

---

## 6. THE STATED PRIOR (recorded BEFORE game 1)

⚠️ **Priors, not bars.** Recorded so the readout can be **SCORED** against them rather than **FITTED**
to them.

| outcome | prior |
|---|---|
| `FAMILY-PARKS` | **~40%** |
| `BRACKET-CONTINUE` | **~30%** |
| `PROMOTE-JOINT` | **~18%** — `J_HIGH` is the single most likely firing cell in the round, because it is the **only** cell sized against an effect (~+1.94 if β and γ are even weakly additive) that this `n` can actually resolve |
| `PROMOTE-A` | **~7%** — needs the A fine ladder's peak to be materially **above** round 2's +0.94; a peak merely **equal** to it resolves ~1 time in 3 |
| `DEFENDS-C` | **~3%** |
| any `REVERSED` | **~2%** — ⭐ **and that low number is a real prediction, not optimism**: the only reversal this family has produced was `A_HIGH` at β 0.36, whose over-correction mechanism (0.36 × M_A 6.0 = 2.16 leaf points, **123% of G**) is **3.6× above this round's β ceiling of 0.10** and out of range **by construction**. A reversal at round 3's doses would be a genuinely **NEW** finding |

⭐ **THE SINGLE MOST IMPORTANT PRIOR** is §4.2's: this round is powered to resolve ~1.7 pts/deck and
is chasing ~1.0, so **the modal outcome is a bounded null that parks formulas rather than a verdict
about the mechanism**.

---

## 7. THE INSTRUMENT'S OWN GUARANTEES

- **Every bar and every constant lives in [`screen_lib.py`](screen_lib.py)**, imported by both the
  adjudicator and the launcher's precondition ladder, so the launcher's in-flight per-cell pre-check
  and the adjudicator's own gates **cannot drift apart**. The launcher pins **only the band** as a
  numeric literal, and `require_table_agrees()` proves even that one agrees.
- **`analyze_screen.py --selftest` must exit 0** before any real read is trusted. It runs against
  `selftest_fixture/` — **a manifest the HARNESS EMITTED** — and **refuses a synthesized one**.
- **The instrument tests** (`tests/test_invasion_screen_r3_instrument.py`) drive relationships and
  behaviour, never constants against themselves — including §3.6's cross-box gate **in both
  directions**, `PROMOTE-JOINT` end-to-end, the attribution ban on every J branch, and the split
  table's optimality at this round's `W`.
- ⛔ **The adjudicator NEVER writes `experiments/results.csv`.** Close-out rows are a human act on the
  six-touch checklist.
- ⛔ **The fired branch IS the authorization to report it** — and every **ACTION** a branch licenses
  is a fresh funding decision and a fresh pair.
