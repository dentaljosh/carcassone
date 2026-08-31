# FPU PRODUCTION-H2H — PRICING THE DEPLOYED CONFIGURATION — READ RULE

> **STATUS: FROZEN** (2026-08-31). This document and [`DESIGN.md`](DESIGN.md) are **the pair**, and
> the pair is law. ⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every bar, every gate,
> every branch and every prohibition below exists **before any game does**.
>
> If `analyze_h2h.py`, `screen_lib.py` or `run_cells.sh` disagrees with this document,
> **it is the code that is wrong.**
>
> ⚠️ **After game 1 there is no amendment route.** The only one that exists is: freeze the verdict as
> it stands, record the defect, and get the **OWNER** to authorise a re-read of the SAME archive under
> a named, minimal, single-clause correction. ⭐ `fpu_resurrection` had to use it (`FPU-A1`), and §4.1
> of this file is the carried fix that makes the same amendment unnecessary here.
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.**
> `analyze_h2h.py --selftest` is `PASS`. ⛔⛔ **`W_LAPTOP` IS UNSET** and `run_cells.sh` refuses every
> mode until it is stamped (DESIGN §6).

**ONE cell:** `CELL_H2H_FPU02` — `fpu_reduction = 0.2` on the **candidate only**, band
`168000000000`, **laptop**, `n=800` deck-paired (400 seat-balanced decks × 2 seatings) against the
**DEPLOYED CHAMPION**: fair PIMC `k16 × 1376 = 22016` **and the deployed root tie arbiter
`B=64 / J=4 / argmax / salt tiearb2-deploy-v1 / eps 0.0 / phase_gate all`**, ⭐⭐ **ARMED ON BOTH
SEATS**.

⚠️ `W` is **throughput-only**. Games are bit-identical at any `W`, and **no gate in this pair reads a
clock**.

---

## 1. THE STATISTIC

**PRIMARY:**

```
D(deck) = ( diff(deck, a_seat=0) + diff(deck, a_seat=1) ) / 2
M       = mean over decks appearing in BOTH seatings
SE      = sample sd (ddof=1) / sqrt(n_paired)
z       = M / SE
UB95    = M + 2*SE          LB95 = M - 2*SE
```

`diff` is the harness's own final-score margin, **candidate minus opponent, in POINTS**.
**`M > 0` ⇒ the CANDIDATE won.** A deck missing a seating is **DROPPED**, never defaulted to zero, and
surfaces at `G-DECKS` and `G-N` (§4.1).

⛔ **Adjudicated AGAINST ZERO, at the cell's OWN REALIZED SE.** The sizing constant
`sigma_D = 13.81` (DESIGN §3) is **power arithmetic only** and is ⛔ **never a denominator in a branch
test.** ⚠️ Its seven corroborating siblings are all **arbiter-off** and this cell is not, so a wider
realized SE is pre-disclosed as plausible; `se_anomaly()` REPORTS the ratio and it is never a branch
input (DESIGN §3.1).

⛔ **`n_paired` IS IN DECKS, NOT GAMES.** A paired `n=800` cell yields at most **400 decks**. Every bar
below is in **pts/deck**.

### 1.1 THE SECONDARY — elo, and it is NOT A BAR

`elo` is reported with its own **deck-paired** CI, **on every branch**.

⚠️⚠️ **THERE IS NO ELO BAR HERE.** The bar is `+1.0 pts/deck` on the deck-paired margin, and
`+1.0 pts/deck` has **no exchange rate into elo that this round measures**. What is printed beside the
elo is the instrument's **2σ RESOLUTION** — `±17.4` elo, deck-paired at 800 games — a statement about
what the instrument can see, never a threshold anything must clear.

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

The six prior fpu readings (DESIGN §4.1) — `0.2` and `0.4` from `fpu_resurrection`, and the ladder's
`0.05 / 0.10 / 0.15 / 0.30` — plus the older neural-era `+45.4` / `+31.4` screens and the M3 curve are
**context in the read-out and nothing else**.

⛔ **NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT. NEVER INTERPOLATED.** CL-068 measured
**1.8–2.2× over-dispersion on merely CROSS-BAND contrasts**, in both the elo and the
deck-paired-margin statistics, with an identity control exonerating the harness and the "different
decks" explanation arithmetically excluded (the per-deck SEM already prices the deck draw). ⛔ **AND
EVERY ONE OF THOSE ROWS IS ARBITER-OFF**, which is a different **agent pair** on top of a different
band — and is the very quantity this cell exists to measure. The neural rows are cross-band **and**
cross-era **and** cross-agent **and** cross-budget. There is no arithmetic that combines any of them
with this cell's number.

⭐ What the overlays legitimately did was fix **which dose** this cell confirms (DESIGN §2.1) and
constrain the bar (DESIGN §0.1, §4.2). Choosing where to look is a **design act**; combining readings
is a statistical one. That use is spent **before any number of this round exists**, and no branch
reaches back into it.

---

## 2. THE ARMS

| side | agent |
|---|---|
| **candidate** | the DEPLOYED champion — fair PIMC `k16×1376 = 22016`, tie arbiter `B=64/J=4/argmax/tiearb2-deploy-v1/0.0/all` — **PLUS `fpu_reduction = 0.2`** |
| **opponent** | ⭐ **the SAME deployed agent, without the dose** |

⛔ **The single variable is the knob.** No `--cand-fpu-reduction` reaches the opponent side, ever;
`--c-puct` and `--tau-p` are **never** used at all (they build BOTH sides, see `G-TWOSIDED`); and there
is **no `--cand-c-puct`** anywhere in this round's launcher.

⭐⭐ **THE ARBITER IS ARMED ON BOTH SEATS AT THE FULL DEPLOYED SPEC**, including `phase_gate`. This is
the round's whole point and it became expressible only on 2026-08-31 (DESIGN §2.3). ⛔ A cell with the
arbiter on the candidate alone is a **CONFOUNDED arb+fpu cell claiming a single variable**;
`G-TIEARB-SIDES` and `G-TIEARB-FIRE` exist to make that unshippable.

---

## 3. THE KNOB — FROZEN SEMANTICS

| `fpu_reduction` | meaning |
|---|---|
| `None` / unset | the NeuralMCTS **legacy optimistic** `q = 0.0` for unvisited children — **the champion, bit-for-bit** |
| a value `r` | an unvisited child scores `q = parent.Q − r` (pessimistic FPU) |

⚠️ **`0.0` IS NOT `None`.** `Some(0.0)` takes the `node_q − 0.0` branch — the **parent's Q** — while
`None` takes the flat `0.0` branch. The two are deliberately distinguished end-to-end and never
coerced. ⛔ A gate that read `null` and `0.0` as the same value would be unable to tell the champion
from a live cell.

⚠️ `parent.Q` is already in `node.player_to_move`'s POV — the same POV the unvisited child is scored
in — so **no sign flip is applied**. `mcts.py:1225` and `carc_core::search/mod.rs:816` implement the
identical rule; the two backends **mirror**. ⛔ Rust is still mandatory here: the **arbiter** is
rust-only and the harness refuses `--{cand,opp}-tiearb-enabled` on python.

---

## 4. THE GATES

⛔ **ABSENT IS FAIL. Never a skip, never a default.** Every gate resolves across **both** documents —
`config.*` in **`manifest.json`**; statistics in **`summary.json`**, which carries **no config block
at all** (IS-D1) — and prints **which document and which address** answered. A value found at **no**
address is `ABSENT`, and `ABSENT` is `FAIL`.

⛔ **A FAIL ON ANY GATE MAKES THE CELL `H-VOID-INSTRUMENT`**, checked **first** in the branch table.
⛔ **The round then discharges nothing**: a voided cell is not a bound, so neither `H-ADOPT` nor
`H-BOUNDED` may be declared over it, and step 2 of the adoption chain remains **unpriced**.

| id | asserts | address | fires on |
|---|---|---|---|
| ⭐⭐ `G-TIEARB-SIDES` | **BOTH SEATS ARMED** at the full deployed dict `{enabled true, B 64, J 4, mode argmax, salt tiearb2-deploy-v1, eps 0.0, phase_gate all}` | `manifest:{cand,opp}_tiearb` / `config.{cand,opp}_tiearb` / `config.opponent.tiearb` | ⛔⛔ **THE ROUND'S OWN LIVENESS GATE.** Delegated to `scripts/classical_search/tiearb_gates.assert_tiearb_sides` — the vocabulary merged 2026-08-31 with the opponent-side plumbing. ⛔ **Phasegate's `G-TIEARB-ARM` is NOT reused**: it requires *"Opponent: no tiearb container"* and would FAIL this healthy cell. ⭐ **A MISSING `phase_gate` KEY IS A FAIL AND NEVER A DEFAULT** — absent means a stale wheel whose arbiter ran UNGATED, and a silently-defaulted `"all"` on a gated cell makes it BE the ungated cell. ⚠️ The two seats have different ABSENCE conventions on purpose (`cand_tiearb` is stamped always, `opp_tiearb` only when armed); both are expected ARMED here, and a MISSING opponent container reads `ABSENT from the manifest` |
| ⭐⭐ `G-TIEARB-FIRE` | **BOTH SEATS ARBITRATED IN PLAY**: `*_games > 0`, `*_fired_plies_total > 0`, `*_G_FIRE_fired` is `false`, `*_partial_argmax_total == 0`, `*_B == [64]`, `*_J == [4]`, `*_phase_gates == ["all"]` | `summary.json` (`tiearb_*` and `opp_tiearb_*`) | ⛔⛔ **THE WITNESS `G-TIEARB-SIDES` CANNOT BE.** A config echo is exactly the class of evidence the hard-coded `fpu_reduction = None` satisfied for months. A both-sides cell whose `opp_tiearb_games` is 0 or ABSENT is a **ONE-SIDED cell wearing a symmetric cell's name**. ⚠️⚠️ `*_G_FIRE_fired` **IS THE VOID FLAG BY ITS OWN NAME** — the harness sets it when `phi < 1.0` — so `false` is HEALTHY; a gate that read it as "did it fire?" would void every good cell and pass every dead one. ⚠️ `*_errors_total` is REPORTED (fail-soft: the ply fell back to the champion's own pick), never fatal |
| ⭐⭐ `G-FPU` | `config.cand_search.fpu_reduction == 0.2` EXACTLY (`null` distinguished from ABSENT), **and** `config.cand_search.c_puct` is `null` | `manifest:config.cand_search.*` | ⛔⛔ **THE INVERTED-LIVENESS GATE.** A harness predating the fpu plumbing emits no `cand_search` at all, and its candidate was **dose-blind by construction** — a cell over it is champion-vs-champion, moves no leaf hash, sits inside `G-SAT`'s rail and reads as a clean credible null. `ABSENT` is `FAIL`. ⭐ The `c_puct` half is a second witness against a stray override |
| ⭐⭐ `G-TWOSIDED` | the **RESOLVED** configs: candidate carries `0.2`, opponent carries `fpu_reduction: null`, `c_puct` EQUAL across the sides and equal to the champion's `1.5` | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⛔ the **second, independent** witness for the dose. `G-FPU` proves it was *requested*; this proves it *landed*, on the candidate and **nowhere else**. ⚠️ It is **weaker than a play-derived witness** (a PUCT constant has no fire counter — unlike the arbiter, which has `G-TIEARB-FIRE`). ⭐ The dose's play-derived evidence is the **IDENT legs** (DESIGN §9.3), and DESIGN says so rather than overclaiming this gate |
| `G-SINGLEVAR` | `fpu_reduction` DIFFERS across the two sides and equals `0.2` on the candidate; **every other** alias is EQUAL | `manifest:config.champion.*` vs `config.opponent.champ_cfg.*` | ⚠️ The opponent's knobs live one level down under `champ_cfg` and its **budget** one level up under `config.opponent.*` — a gate written from the design rather than from a real manifest voids every healthy cell. ⛔⛔ **`tiearb_*` IS DELIBERATELY NOT IN THE ALIAS TABLE**: `_cfg_from_dict` reads five keys by name, so the opponent CANNOT stamp `tiearb_*` under `champ_cfg` and such a clause would read ABSENT and void every healthy cell. `G-TIEARB-SIDES` owns that proposition |
| `G-LEAF` | ⭐ **BOTH SIDES EQUAL** `a36d2e15a3b3d71d`, and `config.cand_leaf_cfg.v29_meeple_curve == curve125` | `manifest:config.{cand,opp}_leaf_hash` | neither the dose nor the arbiter is a leaf term, so differing hashes mean a misconfigured cell — and a moved-hash check can **never** prove either surface live, which is why the four gates above exist |
| `G-BAND` | `config.band_seed_start == 168000000000`; `n_decks == 400` and `seatings_per_deck == 2` | `manifest:config.*` | any deviation |
| ⭐⭐ `G-DECKS` | (a) every realized seed inside `168000000000..168000000399` — **HARD**; (b) decks played at ONE SEAT ONLY are **REPORTED**, and void only at or above **2 % OF GAMES**; (c) `n_common >= 80 %` of 400 — **HARD** | raw `seed*_a*.json` | ⛔ **THE CARRIED `FPU-A1` FIX** — see §4.1 |
| ⭐⭐ `G-N` | `n` and `n_failed` present; the **accounting identity** `n + n_failed == 800`; `n_failed / 800 < 2 %`; `n_common >= 80 %` of 400 | `summary.json` | ⛔ **THE CARRIED `FPU-A1` FIX** — see §4.1 |
| `G-BUDGET` | both sides `(k_dets, sims_per_det, total_sims) == (16, 1376, 22016)` **and the product multiplies out** | `manifest:config.{champion,opponent}.*` | any asymmetry, and a **stale 11008** cell — which would grade the dose against a superseded champion while every other gate passed |
| `G-PROD` | ⭐ **LAUNCHER-SIDE, PRE-COMPUTE.** the frozen **budget AND arbiter dict** == `governance/PRODUCTION.yaml` `champion.fair_deploy` | `governance/PRODUCTION.yaml` | ⛔ Hard abort for a real cell and for the smoke; loud-but-continue for `--dry-run`, which spends nothing. ⚠️ **The ladder's `G-PROD` checked the budget only**, because its arbiter was off; here the arbiter is half the definition of the opponent. ⚠️ `PRODUCTION.yaml` carries **no `phase_gate` key** — the deployed arbiter is UNGATED and `"all"` is how the harness spells that; the absence is asserted explicitly rather than defaulted. **The fix is the bundle sync, never an edit to the pair** |
| `G-EXACT` | both sides `exact_k == 2` and `mode == "marginalized"` | `manifest:config.endgame.*` | K=3/4 are clairvoyant-only |
| `G-RULES` | `rules_profile.name == "fixed_v1"`, `r9_env_ok` and `r9_env_observed` both `true` | `manifest:rules_profile.*` | R9 not latched. ⚠️ R9 is env-latched at **import** |
| `G-BACKEND` | `name == requested == "rust"`, `mixed_builds false`, `converted_sides == {candidate, opponent}` | `manifest:config.backend.*` | ⛔⛔ **RUST IS NOT OPTIONAL HERE.** `fpu_reduction` is threaded on both backends, but the **tie arbiter is RUST-ONLY** and the harness refuses `--{cand,opp}-tiearb-enabled` on python — so a python leg could not arm either seat and would silently be the arbiter-off cell this round exists to stop being |
| `G-WHEEL` | `carc_rs_build` and `carc_rs_binary_sha` present; `mixed_builds false` | `manifest` | ⚠️ `carc_rs_version` is permanently `"0.1.0"` and is **NOT** a discriminator. ⭐ The wheel's identity to the **inherited** golden gate is asserted LAUNCHER-SIDE (§4.2) |
| `G-WHEEL-SAME` | ⭐ **ROUND-LEVEL.** one `carc_rs_binary_sha` on the box | `manifest` | a changed wheel mid-round. ⚠️ the sha is **box-local** |
| `G-REV` | (i) the manifest's short `code_rev` **names** `PINNED_SRC_REV`; (ii) `SRC_CLEAN.jsonl` records the code paths clean at both boundaries; (iii) the pin is 40-hex and every emitted rev canonicalizes to it (`screen_lib.cross_box_rev_gate`) | manifest + `PINNED_SRC_REV` + `SRC_CLEAN.jsonl` | ⛔⛔ **THE ROUND'S PRIMARY PROVENANCE RISK, AND IT NOW HAS TWO HEADS.** BOTH the fpu plumbing AND the `--opp-tiearb-*` plumbing are **python-only**, so a box on stale source serves a **dose-free candidate** and/or an **UNARMED OPPONENT** with a healthy `carc_rs_build`, a healthy binary sha and the correct leaf hash. ⛔ **NEVER by comparing one box's emitted short rev to another's** — the IS-A1 defect |
| `G-BLIND` | `BLIND_COMMIT` is a 40-hex sha, stamped into the adjudicated manifest | `manifest:BLIND_COMMIT` | a read that was not blind |
| `G-HOST` | the manifest's `host` is the **laptop** (substring test on a normalised hostname — `laptop`/`laptop-wsl`/`laptop-pop`/`pop-os` are one machine) | `manifest:host` | a cell run on the wrong box. ⛔ The round is LAPTOP ONLY — the owner holds the local box — and `run_cells.sh` refuses `--role local` at launch rather than voiding an archive after ~7 h |
| `G-SAT` | `0.35 <= winrate <= 0.65` | `summary:winrate` | a **RAIL** check, not a strength bar: both sides run the same search on the same leaf at the same budget with the same arbiter, so a winrate outside this window means the two sides are not the agents this design says they are |
| `RECON` | §1.2's witness agrees on all five statistics | `summary.json` vs raw records | ⛔ can only VOID, never move, a number |

⚠️ **REPORTED, NEVER A GATE: `config.opponent.production_config_deviations`.** The harness stamps it
against `PRODUCTION.yaml`; on the morning of 2026-08-31 the loader was **stale** (a hard-coded
`k_dets=8` against the promoted 16) and stamped a FALSE deviation on a healthy cell. It now reads the
YAML — but a gate over that field would have voided a healthy cell then and could again on the next
promotion. `G-BUDGET` is the gate, and it reads the manifest directly. The field is surfaced in the
read-out for the reader and adjudicates nothing.

### 4.1 ⭐⭐ `G-N` AND `G-DECKS` ARE THE PROSE — THE CARRIED `FPU-A1` FIX

`fpu_resurrection`'s `CELL_FPU04` was **VOIDED** by its own adjudicator over **one** deterministic
`WindowTruncationError` (`1/800 = 0.125 %`), an order of magnitude below the 2 % void bar its **own
frozen prose** set. The condition columns said `n_failed == 0` and `n_common == 400`; the notes column
— carrying the `b32v64` 0.100 % rust-panic precedent — said a sub-2 % failure rate is *"REPORTED,
never silently absorbed"*. The strict column won, and `AMENDMENTS.md` FPU-A1 had to amend the verdict
**with the statistics already visible**.

**Here the prose IS the condition, in both gates, on ONE denominator:**

- ⭐⭐ **THE DENOMINATOR IS GAMES.** A deck played at one seat only **is** exactly one failed game, so
  `G-DECKS`' one-seat-only rate and `G-N`'s `n_failed / n_games` are the **same quantity read off two
  different documents** — which is the whole point of having both.
- **`n_failed / 800 < 2 %`** ⇒ **REPORTED** in the gate's own `why`, and the cell **READS**.
- **`>= 2 %`** ⇒ the cell **VOIDS**, on both gates.
- **`n_common >= 80 %` of 400** — a **fraction**, never an equality. ⚠️ A **backstop**: at 400 decks
  the 80 % floor allows 80 lost decks while the 2 % bar voids at 16 games, so the 2 % bar is the
  operative one and the floor catches a shape it cannot see.
- ⛔ **The accounting identity `n + n_failed == 800` is a HARD fail and is NOT absorbed by the bar.**
  Games that vanished *without* being recorded as failures mean the denominator is unknown — a
  strictly worse defect than a recorded failure.
- ⛔ **Out-of-range seeds remain HARD fails.**

⭐ **A seeded game cannot be re-rolled.** A permanently-failing deck is a fact about the deck set, not
about the dose; the emitter states EXCLUSIONS, not zeros.

`analyze_h2h.py --selftest` proves **both directions at the frozen 400-deck scale**: `15/800 =
1.875 %` must READ on both gates; `16/800 = 2.000 %` must VOID on both.

### 4.2 ⭐⭐ THE GOLDEN GATE IS INHERITED — A LAUNCH PRECONDITION, NOT A GATE

`../fpu_ladder_prep/FPU_BITEXACT_LADDER.json` must read `PASS`, **carrying the launching box's own
`carc_rs_binary_sha`**, before the cell runs; `run_cells.sh` refuses without it. It proves, on this
wheel:

- ⭐ **`fpu=None` is the champion bit-for-bit** — 20 seeded games, identical action-sequence hashes
  across the pre-plumbing and launch source trees on one binary;
- ⭐ **the dose binds** at `0.05 / 0.1 / 0.15 / 0.3`, and the four are `DOSE-DISTINCT`.

⛔⛔ **AND IT HAS TWO GAPS, NAMED IN DESIGN §9.2 AND NOT WAVED THROUGH:** (1) no certificate has ever
exercised `fpu` AND the arbiter TOGETHER; (2) `0.2` is not one of its four control doses. ⭐ **THE
`--smoke` IDENT LEGS PAY THEM** (`IDENT-REPRODUCES` and `POSITIVE-ARB-ON`, DESIGN §9.3), and
`analyze_h2h.py --ident-mode` exits non-zero on either failure.

⚠️ Both are **code-path** gates at a tiny budget (`k2 × 96`). ⛔ **No number in either is a strength
measurement** and none may be quoted as one.

### 4.3 The reachable branch set, stated BEFORE the run

Recorded here so it cannot be reconstructed later: **every branch in §5 is reachable**, including
`H-NEGATIVE` and `H-VOID-INSTRUMENT`. ⛔ No branch is unreachable by construction; the selftest sweeps
a dense `(M, SE)` grid and proves it. If any pre-launch fact later makes one unreachable, that fact is
recorded **before game 1** or it does not count.

---

## 5. THE BRANCHES — PRE-REGISTERED, EXCLUSIVE, EXHAUSTIVE

Adjudicated on the cell's own realized SE, against zero, **in this order**. First match wins.

| # | branch | condition | reading |
|---|---|---|---|
| 0 | **`H-VOID-INSTRUMENT`** | any §4 gate FAILS, or any round-level gate fails, or the archive is ABSENT | The instrument, not the world. **No reading of any kind.** The statistics print only as a companion table under a `VOID` banner. ⛔ Step 2 of the adoption chain remains **UNPRICED** |
| 1 | **`H-NEGATIVE`** | `M <= 0` **and** `z <= -2.0` | ⭐ **THE DOSE IS ACTIVELY HARMFUL IN THE DEPLOYED CONFIGURATION.** Fully plausible and pre-registered as such: the arbiter fires on exact ties and a pessimistic FPU changes which ties are REACHED, so an interaction with the wrong sign is a real mechanism. ⭐ It is also a reading **no arbiter-off cell could have produced** |
| 2 | **`H-ADOPT`** | **`LB95(M) >= +1.0`** | ⭐⭐ **THE EFFECT SURVIVES INTO THE DEPLOYED CONFIGURATION** at the size the decision cares about. ⚠️ Licensed reading is **narrow** — see §5.2 |
| 3 | **`H-BOUNDED`** | **`UB95(M) < +1.0`** | ⭐ **BELOW the decision-relevant effect at 95 %, in the configuration that ships.** It DISCHARGES step 2. ⚠️ It **bounds; it does not zero** — the cell can read `H-BOUNDED` carrying a positive point estimate |
| 4 | **`H-UNRESOLVED`** | everything else | ⛔ **NOT a null and NOT a bound.** `feedback_noisy_plateau_not_a_conclusion` binds |

⛔ **Exclusive and exhaustive by construction.** `H-ADOPT` and `H-BOUNDED` cannot both hold
(`LB95 <= UB95`). `H-NEGATIVE` requires `M <= 0 ∧ z <= -2`, which forces `UB95 <= 0 < 1.0`, so it
would **also** satisfy `H-BOUNDED` — which is why it is checked first. Branch 4 absorbs the remainder.

⭐⭐ **THE BAR IS ON THE INTERVAL, NOT THE POINT ESTIMATE.** `M = +1.5` with `se = 0.69` — a point
estimate well above `+1.0` — reads `H-UNRESOLVED`, because `LB95 = +0.12`. That is the whole
difference from a point-estimate bar, and `sanity_check()` pins it.

### 5.1 ⭐⭐ THE BRANCH TABLE, AS CONSEQUENCES

| branch | what happens next |
|---|---|
| `H-ADOPT` | ⭐ **PROPOSE** (a) a `governance/PRODUCTION.yaml` change setting the champion's `fpu_reduction` to `0.2`, and (b) funding **step 3** (Carcasum external, the arm-on T-TRANSFER protocol). ⛔ **BOTH ARE PROPOSALS.** The flip needs an OWNER RULING on this evidence, exactly as the k16 and `B=64` folds did |
| `H-BOUNDED` | ⭐ **DISCHARGE step 2.** The effect does not survive into the deployed configuration at `+1.0`; the flip is not worth proposing and step 3 is not worth funding. Update `docs/LEVER_INDEX.md:146` to say so |
| `H-NEGATIVE` | ⭐ **DISCHARGE step 2, with a stronger statement.** No production change either way — the champion already runs `fpu=None`, so there is nothing to turn off |
| `H-UNRESOLVED` | ⛔ **NOTHING IS DISCHARGED AND NOTHING IS PROPOSED.** §8.2 pre-commits the price |
| `H-VOID-INSTRUMENT` | ⛔ **NOTHING.** Fix the instrument; a re-run is a NEW round on a NEW band with fresh owner funding |

### 5.2 ⚠️ THE RIDERS ON `H-ADOPT` — MANDATORY, AND THEY TRAVEL WITH EVERY CITATION

1. ⛔⛔ **IT DOES NOT LICENSE A PRODUCTION CHANGE — IT LICENSES *PROPOSING* ONE.**
   `governance/PRODUCTION.yaml` is UNTOUCHED on every branch of this round.
2. ⛔ **THE OUT-OF-FAMILY CHECK COMES BEFORE ANY GENERAL CLAIM.** `feedback_evloss_grader`'s F4
   lesson: a `+1.49` in-family ceiling read `−0.64` at `z −3.8` out-of-family on the same CRN worlds.
   Step 3 (Carcasum) is that check and it is its own prereg, band and funding.
3. ⛔ **IT DOES NOT LOCATE AN OPTIMUM AND IT IS NOT A BRACKET.** One dose, one band. The ladder that
   tried to bracket `0.2` read `LADDER-UNRESOLVED`, and no interpolation is licensed.
4. ⛔ **IT SAYS NOTHING ABOUT THE ARBITER-FREE CHAMPION.** The transfer runs the *other* way here:
   this cell prices the deployed configuration, and no reading may be quoted back onto the `155e9` /
   `164–167e9` cells.
5. ⚠️ **TYPE-M RIDER.** The funded `n=400` is powered ~80 % against a repeat of the incumbent's
   `+2.951` and only ~21 % against the ladder's largest point estimate `+1.835`. A cell that adopts
   near the bar carries a **magnitude biased upward**; the SIGN is the reliable part. This is the same
   rider the k16 fold carries.
6. ⚠️ **IT IS A `k16 × 1376`, `B=64`-BOTH-SEATS, `fixed_v1`+R9, exact-k2-marginalized, rust result on
   ONE fresh band**, which retires `decision_influenced=yes` the moment the read-out lands (§7).
7. ⚠️ **`elo` may never be quoted bare**, and here it is not even a bar (§1.1).

### 5.3 ⛔ ONE CELL — THE MULTIPLICITY NOTE, IN BOTH DIRECTIONS

There is **no multiplicity to correct**: one cell, one pre-registered bar, one question. ⭐ At the
`LB95` bar the false-adopt rate under a true null is **≈ 0.028 %** — **this bar cannot fire on
noise**.

⛔ **The price of that conservatism is §8's**: the bounding direction is weak, and a true null reads
`H-UNRESOLVED` ~71 % of the time.

---

## 6. THE ADOPTION CHAIN — FROZEN BEFORE ANY NUMBER EXISTS

`screen_lib.ADOPTION_CHAIN`, restated from the ladder's own frozen copy so that a fired cell cannot
later be walked through a shorter chain than the one already pre-registered:

1. **THE DOSE LADDER / THE PARENT SCREEN** — a dose reads positive on its own fresh band with the
   arbiter OFF both sides. ⭐ DONE: `fpu=0.2` read `F-RESURRECT` (band `155e9`); the ladder that
   bracketed it read `LADDER-UNRESOLVED` (bands `164–167e9`).
2. ⭐⭐ **THIS ROUND — PRODUCTION H2H**, the dose vs the DEPLOYED champion with the tie arbiter ARMED
   ON BOTH SEATS, on a FRESH band. ⛔ **THE LEG THAT PRICES THE ARBITER-OFF DEVIATION** every earlier
   fpu reading carries.
3. **CARCASUM EXTERNAL** — the arm-on T-TRANSFER protocol, the only out-of-family check this program
   has.
4. **E4 EPOCH** on the phone.

⛔ **EACH LEG IS ITS OWN PREREG, ITS OWN BAND AND ITS OWN OWNER FUNDING.** A cell firing here funds
nothing automatically.

---

## 7. GOVERNANCE

Measurement only. On **every** branch:

- ⛔ `governance/PRODUCTION.yaml` **UNTOUCHED**. No branch licenses a production change of any kind;
  `H-ADOPT` licenses **proposing** one.
- One `experiments/results.csv` row, citing the branch and carrying §5.2's riders.
- ⭐ **`docs/LEVER_INDEX.md:146` is UPDATED on every branch** — it must say that the dose was measured
  **in the deployed configuration**, at what bar, and with what bound. That row is the reason the next
  reader will or will not re-propose this lever.
- Band `168000000000` retires `decision_influenced=yes`.
- ⭐ **THIS READ-RULE IS SPENT WHEN THE READ-OUT LANDS, ON EVERY BRANCH**, and the band retires from
  confirmatory use.
- The context rows are **context in the read-out**, never a gate input, never pooled (§1.3).

---

## 8. ⛔⛔ CAVEAT — WHAT THE BAR COSTS, STATED BEFORE GAME 1

*This section exists because the house rule (owner, 2026-08-30) requires it. ⛔ **THE BAR DOES NOT
MOVE** — `BAR_EFFECT = 1.0` is pre-registered design and this section changes no number, no gate and
no branch.*

`screen_lib.read_distribution()` computes the following and `sanity_check()` asserts them, so this
round cannot quietly improve its own advertised odds.

**At the modelled `se = 0.6905` (n = 400 decks):**

| true effect `δ` | `H-ADOPT` | `H-BOUNDED` | `H-NEGATIVE` | `H-UNRESOLVED` |
|---|---:|---:|---:|---:|
| **0 (true null)** | **0.028 %** | 26.8 % | 2.28 % | **70.9 %** |
| **+1.0 (at the bar)** | 2.28 % | 2.25 % | ~0 % | **95.4 %** |
| **+1.835 (the ladder's largest point estimate)** | 21.5 % | ~0 % | ~0 % | 78.5 % |
| **+2.951 (a repeat of the incumbent)** | **79.6 %** | ~0 % | ~0 % | 20.4 % |

- ⭐ **THE ROUND IS PROPERLY SIZED FOR ITS OWN QUESTION.** *"Does the `+2.951` survive into the
  deployed configuration?"* is answered at ~80 % power, and `n_decks_for_adopt_power(2.951, 0.80) =
  405` — the funded 400 is that number to within a deck. This is the house rule's "size `n` to resolve
  THAT" **met**, not apologised for.
- ⛔ **THE BOUNDING DIRECTION IS WEAK BY CONSTRUCTION.** A lower bar makes `H-BOUNDED` harder, and a
  true null reads `H-UNRESOLVED` ~71 % of the time (the ladder's higher bar gave ~43 %).
- ⛔ **A TRUE EFFECT EXACTLY AT THE BAR IS ESSENTIALLY UNRESOLVABLE** (95 % unresolved). The bar is a
  **decision** threshold, not a detection threshold.
- ⛔⛔ **AND THE REALISTIC DISAPPOINTMENT IS THE MIDDLE ROW.** If the deployed configuration halves the
  arbiter-off effect to the ladder's `+1.8`-ish scale, this cell reads `H-UNRESOLVED` about four times
  in five. That is written down **before game 1**.

### 8.1 ⛔ THE `n` THIS BAR WOULD ACTUALLY NEED

| goal | decks | games | vs funded |
|---|---:|---:|---:|
| **funded** | 400 | 800 | 1× |
| adopt a repeat of `+2.951` at 80 % power | **405** | 810 | **1.01×** ⭐ |
| adopt `+1.835` at 80 % power | 2,209 | 4,418 | 5.5× |
| `H-BOUNDED` at 80 % under a true null | **1,540** | 3,080 | 3.9× |

### 8.2 ⭐ THE PRE-COMMITTED PRICE OF AN UNRESOLVED READ

**An `H-UNRESOLVED` cell is re-runnable ONLY on a NEW BAND and ONLY with fresh owner funding.** Stated
now so the cost is known before it is incurred:

- ⛔ **The band is spent either way.** §7 retires `168e9` `decision_influenced=yes` when the read-out
  lands. The cell **may not be extended, topped up, or re-read at larger `n` on its own band** — that
  is the `rodv3` failure mode (`n` bought after seeing the sign), and CL-068's cross-band
  over-dispersion means the extension could not be pooled with the original anyway.
- ⛔ **This read-rule is spent when the read-out lands, on every branch** (§7). A re-run is a **new
  round** needing a new pair, a new band claim, and the owner's funding.
- ⛔ **`H-UNRESOLVED` DOES NOT DISCHARGE STEP 2 AND DOES NOT LICENSE STEP 3.** The temptation
  afterwards will be to read a null-shaped `H-UNRESOLVED` as if it were `H-BOUNDED` — they are the
  same underlying world most of the time. It is not licensed: only `H-BOUNDED` says *"the effect is
  below the decision-relevant size in the configuration that ships"*.
- ⛔ **AND IT DOES NOT RETRACT THE ARBITER-OFF `+2.951` EITHER.** It says this round bought no verdict
  on the deployed configuration, and nothing more.
- ⚠️ `RIDERS_H_UNRESOLVED` (in `screen_lib.py`) **GOVERN** the read-out and travel with every
  citation, exactly as §5.2's riders do.
