# F9 — Rules-fix program: build spec

> **STATUS 2026-08-02 — DRAFT, AWAITING JOSHUA. Spec only: no code written, no engine touched, no band
> claimed, no `governance/PRODUCTION.yaml` change, no `experiments/results.csv` row.** Committed before the
> first line of implementation (house pre-registration style, the
> [RUSTPORT_BUILD_SPEC_2026-07-31.md](RUSTPORT_BUILD_SPEC_2026-07-31.md) precedent). Charter: the **F9** row of
> [docs/PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md). Dossier: R1–R8 of
> [docs/RULES_FIDELITY_AUDIT_20260802.md](RULES_FIDELITY_AUDIT_20260802.md). Open-decision context:
> [docs/DECISION_QUEUE_20260802.md](DECISION_QUEUE_20260802.md) item 5.
>
> **Nothing in this document adopts a rules change.** Building a flag is not adopting it; §7 lists every
> decision that stays Joshua's.

---

## 0. What this is, and the one sentence that motivates it

Every elo we have ever measured is a **walled-Carcassonne** number. The divergences are symmetric (both
sides of every A/B played the same wrong rule) so **relative orderings are structurally protected** — but
the **transfer error to canonical rules is unmeasured**, and it is invisible to every self-consistency gate
we own by construction: both arms share the wrongness, and the Rust port certifies it bit-exactly. F9 exists
to (a) build the fixed-rules option behind flags, (b) put a **measured bound** on that transfer error, and
(c) leave behind a permanent external referee so the class cannot recur silently.

**Scope discipline.** F9 is a *measurement* program with a *build* prerequisite. It is not a strength
program. Exactly one of its remediations (R2, the cloister scan) is plausibly a strength lever, and that is
noted as an opportunity, not funded as one.

**Numbers policy.** This document carries pointers, gates and order. Authoritative numbers live in
[experiments/results.csv](../experiments/results.csv), [governance/PRODUCTION.yaml](../governance/PRODUCTION.yaml),
[governance/BAND_REGISTRY.csv](../governance/BAND_REGISTRY.csv), the audit, and the dated
[DECISIONS.md](../DECISIONS.md) entries. Where a figure appears below it is either (i) a *design input* whose
source is named on the same line, or (ii) a *pre-registered threshold* that this document is the source of.

---

## 1. Phase A — rules remediation behind flags

**Invariant for the whole phase: default-off, both engines, python↔Rust parity per the G5 pattern.** A flag
that is not set must leave the byte-compatible engine of record untouched, and that must be *proven*, not
asserted — the P5 leg (DECISIONS 2026-08-01 pre-dawn) is the template: full flags-off G1–G4 regate, 0
mismatches, after the flags land.

### A0 — the plumbing gap (do this first; it blocks every later phase)

**Finding, from a read of the harnesses (2026-08-02):** the two n=400 head-to-head harnesses
`scripts/classical_search/eval_puct_priors.py` (~17 `Game(...)` construction sites) and
`scripts/classical_search/eval_fair_puct.py` (~20 sites) **cannot express a rules flag at all** — no
`--start-rule` / `--start-row` / `--start-col` / `--grid-rule` / `--board-size` argparse entry exists and every
`Game(...)` call rides the defaults. The layers that *can* express it are `Game(start_row=, start_col=,
fixed_start_tile=)` (`src/carcassonne_ai/game_wrapper.py`), `carc_rs.resolve_game_config` /
`GameConfig::resolve` (`rust/carc/carc-core/src/game.rs`), `RustFairAgent` (`src/carcassonne_ai/rust_agent.py`),
the Android bridge, and `scripts/rustport/lockstep_fuzz.py` (the closest existing template — it already takes
`--start-rule/--start-row/--start-col`).

**Build:** one resolved `rules_profile` object, constructed once per run from CLI, threaded to every `Game(...)`
and every Rust mirror construction, and **stamped verbatim into `manifest.json`**. Named profiles only
(`walled` = today's default, plus whatever §A1–A4 add) — never a loose pile of independent flags at the CLI,
because an unstamped or partially-applied profile is precisely the failure this program exists to detect.

**Gate A0 (zero tolerance):** with no rules flag given, 10 deck-paired games through each converted harness
are **byte-identical** to the unconverted harness (the G6 identity pattern —
`measurement/rustport_p6/G6_backend_*.json` is the shape). Plus: a run whose profile is anything other than
`walled` must **refuse to write an `experiments/results.csv` row** unless the profile is also in the row's
`exp_id` — the fail-loud guard against a fixed-rules number silently entering the walled record.

**Effort:** ~0.5 agent-day. **This is the item that makes everything else in F9 runnable.**

---

### A1 — the wall

**The wall is a board-size artifact, and recentring only mitigates it.** State the honest options; the
choice between them is Joshua's (§7 J2) and should be made *after* the cheap probe below, not before.

Two defects are conflated under "the wall" and must be separated:

- **(i) Legality (the rules divergence).** Rule P3 says the playing area is unbounded.
  `CarcassonneGameState(board_size=(35,35), starting_position=Coordinate(6,15))`; `StateUpdater.play_tile`
  bounds-checks before adding to `open_positions`, so a rule-legal cell off the array never enters the
  candidate set and `TilePositionFinder` never offers it. Silent. Blast radius measured twice by two
  instruments (audit RF-C-1; DECISIONS 2026-08-02 early; DECISIONS 2026-08-01 pre-dawn §2).
- **(ii) Safety (the four fatal faces + one encoding face).** The border ledger, all on record: silent wall
  denial · negative-row wrap (`board[-1]` → row 34) · **col-34 placement fatal** (`IndexError` in the farm
  path; G1 fuzz, 4/4 games reaching col 34 died) · **last-row fatal** in `count_final_scores`
  (`board[r+1]` unguarded; 95/96 games die at start-row 30) — and at the last row the **flat and object
  scorers disagree with each other**, which the audit rightly names as the cheapest available detector for
  the whole class. Plus `action_space.WindowOverflowError` from the 25×25 centroid window, which crashed 16/400
  `capoff` ablation games deterministically (CL-074 note; DECISIONS 2026-07-31 Shabbat eve).

#### The options, with honest costs

| id | definition | what it costs | what it buys | what it does NOT fix |
|---|---|---|---|---|
| **W1** | status quo (walled 35×35 @ row 6) | 0 | nothing — this is the **control arm**, not an option | — |
| **W2** | **recentre only** (start row 18, EVEN shift) | **already built + G5-gated + app-shipped**, free | measured **zero denials in 400 random games** (DECISIONS 2026-08-02 early) | it is a **mitigation, not a rules fix**: the denial rate is *policy-dependent* and the transfer-bound cell runs **champion play, not random play**. The wall-seeking test still reaches row 0 at ~60 plies. **And it moves risk, it does not only remove it** — downward headroom falls 28 → 16, so the **last-row fatal face becomes materially more reachable** while the silent-denial face goes away. Trading an invisible bias for a visible crash is an improvement *only if the crash is instrumented* (see W4). |
| **W3** | **board size becomes runtime config**, grid enlarged and centred until the wall is unreachable | Python: `board_size` is **already a real ctor parameter** and `state_updater` derives bounds dynamically — but **0 of ~20 `CarcassonneGameState(...)` call sites pass it**, and `game_wrapper.ENGINE_BOARD_ROWS/COLS` is a *disconnected duplicate* constant. Rust: `BOARD_ROWS/BOARD_COLS` are **compile-time consts** (`engine/mod.rs`) consumed at ~10 sites plus `leaf/decomp.rs` `N_CELLS = ROWS*COLS` ⇒ making it a `GameConfig` field is a real refactor, and **a bigger `N_CELLS` lands directly on the leaf hot path** (decompose enumeration ~45% of leaf cost). A provably-unbounded 143×143 is **16.7× the cells** of 35×35; a 55×55 is 2.5×. **This must be BENCHED, never extrapolated.** | a *rules* answer rather than a *policy* answer: at 143×143 centred, a 72-tile game **cannot** reach a wall, by construction | the 25×25 window (below). Also: absolute coordinates change ⇒ node keys, golden fixtures and every replay corpus are non-replayable **under the flag** (they replay flags-off — that is the gate). |
| **W4** | **fail-loud wall sentinel** — a **mandatory companion to W2 or W3, not an alternative** | trivial | converts every silent denial and every fatal face into a **named, counted, raised** event: `open_positions` bounds-drop → `BoardWallError`; guard `count_final_scores`'s `board[r+1]` and the farm path's col+1 to raise rather than wrap/IndexError; keep `WindowOverflowError` but **count** it into the manifest | nothing — it is the instrument, not the fix |

#### The recommendation, and why it is sequenced this way

**Run W4 first, cheaply, and let the measurement choose between W2 and W3.**

W2 is free and may well be sufficient; W3 is the only *provable* answer but carries an unpriced leaf-hot-path
cost. The house rule is bench-then-extrapolate-then-commit, so:

- **Gate A1-a (the decider, ~1 box-hour):** build W4, then replay/generate **400 champion-play games** (not
  random play) at start row 18 with the sentinel armed. Report: wall denials, negative-row reads, col-34
  events, last-row events, `WindowOverflowError` count, and the max row/col span reached.
  - **Zero sentinel events ⇒ W2 is adopted as the F9 fixed-rules geometry**, and "wall-free under champion
    play" becomes a *measured* statement about the exact policy the cells run, carried in every manifest.
  - **Any sentinel event ⇒ W3 is required**, and its funding gate is a leaf bench: measure `flat_base_score`
    µs/leaf at 35×35 vs the candidate size **before** committing (the G2 corpus is the right workload). Size
    the grid by the **measured** span requirement, not the theoretical 143 — measured spans reach ~17 rows —
    with the sentinel proving the choice per-cell.

**⚠️ The 25×25 action window is orthogonal and no board change fixes it.** `DEFAULT_WINDOW_SIZE = 25`
(`src/carcassonne_ai/action_space.py`) is a **representation** cap, not a rules cap. Under the *classical*
champion of record it is only an action-index encoding, so it can be widened at F9 for free; under **any net
arm it changes the input shape and invalidates every checkpoint**. Therefore: `window_size` is a **separate
flag with a separate decision** (§7 J4), and a fixed-rules cell that widens it **retires the net arms from
that cell**. Its overflow count is reported either way.

**Engine surface touched:** `engine/wingedsheep/carcassonne/carcassonne_game_state.py` (board_size threading),
`utils/state_updater.py` (the bounds check → sentinel), `utils/points_collector.py` (`board[r+1]` guard),
`utils/farm_util.py` (col+1 guard), `src/carcassonne_ai/game_wrapper.py` (`ENGINE_BOARD_ROWS/COLS` must stop
being a disconnected duplicate), `src/carcassonne_ai/action_space.py` (overflow counter);
Rust `engine/mod.rs`, `game.rs`, `leaf/decomp.rs`, `action_space.rs`.

**Constrained by:** `tests/test_start_tile_grid_bound.py` — `test_start_tile_is_not_centred` (pins the
default), `test_off_grid_cells_never_enter_open_positions` (pins the mechanism),
`test_even_shift_preserves_the_encoding` + `test_odd_shift_breaks_the_window_offset` (**any shift F9 adopts
must be EVEN** — banker's rounding in `offset_from_centroid_sums` is equivariant under even translations
only), and the **strict-xfail sentinel `test_no_rule_legal_placement_is_ever_denied`, which must keep
xfailing for as long as the global default stays walled** — its flipping to xpass is the tripwire that a
default moved by accident. Rust side: `tests/rustport/test_p5_flags.py` (start rule / fixed start tile /
even-shift classes, incl. `test_the_recentred_grid_denies_nothing_the_walled_one_denies`).

---

### A2 — cloister completion scan (audit R2) — the cheapest real rules fix, and the one strength opportunity

**Surface:** `engine/wingedsheep/carcassonne/utils/points_collector.py` `remove_meeples_and_collect_points`
(the 3×3 scan rebinds `coordinate` — its own outer loop bound — so scan rows 2 and 3 drift to wherever the
last non-empty cell of the previous row was). Rust twin: ported **verbatim and mutation-proven load-bearing**
at G1 (regressing it ⇒ 86 mismatches on the champ corpus; the 12 golden games alone would NOT have caught
it). The fix is **one rename**.

**Why it is a strength item, not just a fidelity item.** Points are *deferred, not lost* — `count_final_scores`
still awards 9 for a monk sitting on a completed cloister — so **final scores are unchanged**. What is lost is
the **monk**: pinned for the rest of the game, a permanent −1 on a supply of 7, invisible to every score-based
check. And the champion leaf's **meeple term is its single biggest component** (CL-074: ~300 elo, curve SHAPE
~177 of it). So R2 changes the leaf's *inputs* on the axis the leaf is most sensitive to. This is the concrete
form of the `feedback_bug_fix_shifts_optima` rider (§2.4).

**Sizing first (audit R1, do it before the fix).** Re-run the geometric miss-rate probe under **champion play**
instead of random play, turning "9.55% of completions" into "N monk-pins per game". Random play completes
~0.1 cloisters/game and almost never has a monk on one; strong play engineers completions and routinely has
one. ~1 box-hour, no code change, folds into the Phase C-lite corpus (§3) for free.

**Parity gate design.** The fix is a *deliberate behaviour change*, so the G1 replay gate **fails by
construction** flags-on — the record was played on the drifting scan. Therefore:

1. **flags-off regate**, zero tolerance: full G1–G4 reconcile suite (`scripts/rustport/reconcile_{engine,leaf,search,fair}.py`), 0 mismatches.
2. **flags-on python↔Rust lockstep**: `scripts/rustport/lockstep_fuzz.py` extended with the flag, **1,000 games × the full check battery**, 0 mismatches (the P5 flags-on leg is the template: 4×1,000 games × 12 checks).
3. **behaviour assertion in BOTH engines**: the audit's deterministic control/trigger pair (`rf_cloister_repro.py`) promoted into `tests/` — control scores and returns the monk; trigger, flags-off, does not; trigger, flags-on, does.
4. **mutation probe** (the P1 lesson — "0 mismatches" must be *informative*): regress the fix and prove the flags-on gate goes red.
5. **counter into the manifest**: monk-pins avoided per game.

---

### A3 — unplaceable tile → redraw (audit R4) — the largest re-baselining risk in the set

**Surface:** `engine/wingedsheep/carcassonne/utils/state_updater.py` — a TILES-phase `PassAction` discards,
draws the next, **and calls `next_player`**. The rules say the same player draws again and continues.
Measured 8.5 discards/100 games, **7.0% of games affected** (audit RF-D-2). ⚠️ **Do not disturb** the
deliberate 2026-04-28 rewrite this path carries (it fixed a stale `last_tile_action` leaking a meeple onto a
previous turn's tile) — only the `next_player` call is the divergence. `action_util.py` is correct and
unchanged (the must-place-if-possible rule is already honoured).

**The three non-obvious sub-decisions this flag must pre-register:**

1. **Recursion.** The redrawn tile may itself be unplaceable. The loop needs a terminal condition, and
   "deck exhausted mid-redraw" must resolve to the same `is_terminated()` semantics as the normal path
   (`count_final_scores` fires from both, audit E7).
2. **The exact solver's bag.** The K≤2 marginalized expectiminimax groups the bag by description; a discard
   removes a tile mid-turn, so the bag histogram the solver marginalizes over changes *within* a turn.
   This is a real touch on the latch path and needs its own equality check in the G4-pattern gate.
3. **Turn parity.** This is the one flag that changes **who places which tile from that point on**, which is
   why it is the largest re-baseline risk of the set and why the bundle-vs-single-flag question (§6, T1) is
   sharpest here.

**Gate:** the A2 five-part pattern, plus an explicit **parity-invariant test** (tiles placed per seat, per
game, flags-on vs flags-off, over ≥1,000 fuzz games) — the direct observable of what this flag changes.

---

### A4 — retail fixed start tile (audit R5) — already built, G5-gated

**Surface:** `game_wrapper.py` `fixed_start_tile` (defaults False); Rust `StartRule::{Engine,Retail}`.
Semantics already pinned at P5: first "D" removed from `[next_tile] + deck` (200-seed verify),
`last_tile_action=None` visible in the node key, the `total_tiles` +1 quirk ported verbatim, and
`test_retail_and_recentring_compose` proving it composes with A1.

**Build cost: a flag flip in the harness (A0) and nothing else.** But note the measurement cost (§2.3, §7 J3):
**retail changes the deck composition**, so the same seed no longer yields the same 72-tile sequence, which
**degrades CRN deck-pairing across the walled/fixed conditions**. It is the one member of the bundle with a
statistical cost rather than a build cost.

---

### A5 — explicitly OUT of scope

- **R6, the WC tie-break — OUT, note only.** It is a *tournament scoring convention at game end*, not a
  fidelity defect against the retail rules (which have no tie-break). Three reasons to keep it out of F9:
  (a) it mechanically shifts every win-rate in the program by up to ~1.25pp for reasons that have nothing to
  do with play (audit: ~1–2.5% of games are drawn); (b) it makes the **seats asymmetric**, and seat-swap
  symmetry is an assumption of every deck-paired estimator we own — including the luck-floor instrument;
  (c) it is orthogonal to the transfer question, which is about the *legal-move set and turn structure*, not
  about how a tie is booked. Revisit if and only if a WC-rules exhibition or E4 grading needs it, as its own
  item with its own re-baselining.
- **R7 (separate `cathedral` from `inn`; stop scoring gardens as cloisters) — OUT.** Provably inert under the
  locked scope (no base tile sets `inn` or `cathedral`; a meeple cannot reach a garden centre without ABBOTS
  or a supplementary rule, both rejected). Record as a **scope-widening tripwire**: both become live RF-A
  errors the moment Inns & Cathedrals or Abbots is enabled, and either fix would need this same flag-and-
  regate treatment. Do not "fix casually while the file is open" — a silent semantic change to a hot scoring
  file is exactly the class F9 exists to prevent.
- **The 8 `flowers`/garden tiles' non-garden geometry** — assumed identical to their plain counterparts,
  never checked. Not fixable by inspection; it is a **Phase D** target (§4), with the caveat noted there.

---

## 2. Phase B — the transfer-bound cell

### 2.1 The contrast (recommended)

**Re-run the champion promotion pair: `k8×1376` (11008) vs `k4×688` (2752), fair PIMC, exact-K≤2, both sides
the frozen curve125 leaf.** Walled reference of record: `experiments/results.csv`
`cl060_h2h_k8x1376_vs_deploy_k4x688` (band 32e9, n=400 deck-paired), the evidence
[governance/PRODUCTION.yaml](../governance/PRODUCTION.yaml) cites for the 2026-07-29 budget promotion.

Why this one, over any other contrast in the record:

1. **It is the promotion of record.** The deployed champion rests on it. If it does not transfer, the
   champion's own justification is condition-specific — that is the highest-value thing F9 can learn.
2. **It is the robust class**: a *within-band deck-paired* head-to-head, exactly the class the CL-068
   over-dispersion amendment endorses and the 2026-07-29 promotion rests on.
3. **It is large** (~3.5σ paired). n=400 can resolve a material move in it; it cannot resolve a +20 elo
   effect (CLAUDE.md n-thresholds), and F9 must not pretend otherwise.
4. **Both arms are pure classical** — no checkpoint is exposed to a grid or window change (§A1).
5. **Both arms now run Rust**, so the cell costs ~45 min rather than ~7.5 h (DECISIONS 2026-08-02 night).
6. **Budget × rules is the plausible interaction.** More reachable board ⇒ longer decision horizons ⇒ more
   for search to buy. If any contrast in the record is going to move under fixed rules, a *budget* contrast is
   the one.

### 2.2 ⚠️ Design correction to the charter: two cells on ONE fresh band, not one cell vs history

The charter says "n=400 deck-paired, FRESH band". Taken literally that compares a fresh-band fixed-rules cell
against the historical **band-32e9** walled number — a **cross-band** contrast, and the house's own practice
note (CL-068 amendment, DECISIONS 2026-07-29) requires inflating σ **1.5–2×** on exactly that class. The
measured band-level over-dispersion is **1.8–2.2×, in both the elo and the deck-paired-margin statistic**, and
the "different decks" explanation is arithmetically excluded. Applying it: a per-cell paired σ of ~14 gives
σ(Δ) ≈ 20 within-band, inflating to **≈ 31–40 elo cross-band** — comparable to the entire effect being tested.
**The cell as chartered would be structurally unable to fire.**

**Therefore, mandatory:** run **both arms on the same fresh band**, the same deck seeds, seat-swapped:

- **Arm W (control):** the identical contrast, **walled profile**, n=400 deck-paired, band `B_F9`.
- **Arm F (treatment):** the identical contrast, **fixed-rules profile**, n=400 deck-paired, band `B_F9`,
  same 200 deck seeds.

Cost of the correction: **+1 cell ≈ +45 min**. This is the single highest-leverage line in the spec. It is the
cliff-ladder precedent (DECISIONS 2026-07-29): when a comparison must cross a condition, put both conditions
on one band and pair the decks.

⚠️ **Pairing caveat, stated up front:** the two arms share the *deck seed* (the dominant variance source) but
the games diverge from ply 1 because the legal-move set differs. This is CRN on the deck draw, not paired
games — it removes the deck component of variance and nothing more. And **if A4 (retail) is in the bundle the
deck composition itself differs**, weakening even that (§7 J3).

### 2.3 Pre-registered decision map (commit before the first game)

Let **Δ = elo(Arm F) − elo(Arm W)**, both n=400 deck-paired on `B_F9`. **σ(Δ) is taken from the run's own
measured paired σ**, not from a prior; the estimate used for sizing is σ(Δ) ≈ 20 elo. **Report the CI, always,
not only the z.**

| branch | condition | pre-committed consequence |
|---|---|---|
| **1 — TRANSFER BOUND** | \|Δ\| ≤ 1σ(Δ) | The walled record **transfers within the measured bound**. The publishable statement is the **95% CI of Δ** (≈ ±40 elo at n=400), quoted **as a bound, never as "zero"**. Kills the publication objection at a stated resolution. Annotate the walled record with the bound; nothing is adopted, nothing is re-run. |
| **2 — MATERIAL MOVE (re-baselining trigger)** | \|Δ\| ≥ 2σ(Δ) | (a) the walled record is annotated **condition-specific** in `results.csv` + `governance/CLAIM_REGISTRY.csv`; (b) the **single-flag attribution ladder** fires (one cell per flag, same band, same contrast — that is why the per-flag event counters of §1 exist: they attribute *for free* and the ladder only spends where they cannot); (c) `feedback_bug_fix_shifts_optima` fires — see §2.4; (d) an **adoption proposal** goes to Joshua. **No automatic adoption, in either direction.** |
| **3 — INCONCLUSIVE** | 1σ(Δ) < \|Δ\| < 2σ(Δ) | The **n→800 extension on fresh decks of `B_F9`** (the CL-072 precedent), a decision to be made **before the sign is looked at** — pre-commit the trigger here, not after. If not funded: the record carries "unresolved, \|Δ\| < CI" and **nothing is claimed in either direction** (`feedback_noisy_plateau_not_a_conclusion`). |

**Hard falsifiers — the cell is VOID, not "accepted at n=384":** any wall-sentinel event in either arm · any
`WindowOverflowError` · fewer than 400/400 latches · any timeout · a `rules_profile` in the manifest that is
not the one pre-registered. F9's entire subject matter is that exclusions here are **candidate-correlated by
construction** (the capoff precedent), so the standing worst-case-bound accommodation does **not** apply.

**Fail-loud requirement:** each arm's `manifest.json` carries the full resolved `rules_profile`, the sentinel
counter block, and the code_rev + wheel hash of both boxes. A cell whose two arms differ in any manifest key
other than the profile is void.

### 2.4 The riders (charter, restated with teeth)

- **`feedback_bug_fix_shifts_optima` applies to the whole set.** The champion leaf (`v29_meeple_curve ×1.25`,
  cap8) was tuned under walled rules with a scan that pins monks. A2 changes **meeple supply**; the meeple
  term is the leaf's **largest single component** (CL-074). ⇒ **If any rules change is globally adopted, the
  leaf caps/curve are re-swept BEFORE any old optimum is trusted** — and until that re-sweep, the fixed-rules
  champion is *not known to be* the walled champion. Consequence worth stating plainly: **Phase B measures the
  transfer of a contrast, not of the champion's absolute strength.** Absolute fixed-rules strength is not
  obtainable without the re-sweep, and F9 does not claim it.
- **Band retirement.** Walled bands retire from confirmatory use for fixed-rules claims. The mechanism is
  §2.2: the control lives on the *fresh* band, not in history.
- **`governance/PRODUCTION.yaml` is untouched throughout F9**, whichever branch fires.

---

## 3. Phase C — fixed-rules descriptives (the advisor's P3 gate)

Two tranches. **C-lite runs BEFORE Phase B** (it sizes the flags and costs almost nothing); C-full runs after.

**C-lite — event rates under champion play** (audit R1 generalized). One ~400-game champion-play corpus per
profile, sentinel armed, emitting per game: wall denials by face · `WindowOverflowError` count · max row/col
span · unplaceable-tile discards/redraws · **cloister completions and monk-pins** · tiles placed per seat.
This is what turns every "≈X% of games" in the audit — all of it random-play — into a number about the policy
the cells actually run. **~45 min two-box** at the measured gen rate (DECISIONS 2026-08-02 late afternoon).

**C-full — the three P3 descriptives, re-derived under fixed rules:**

| descriptive | instrument | status |
|---|---|---|
| **Luck floor** (σ_game, deck-luck ICC, required-n table) | `scripts/human_anchor/luck_floor.py` → [measurement/human_anchor/LUCK_FLOOR.md](../measurement/human_anchor/LUCK_FLOOR.md) | **exists**; point it at the fixed-rules archives. ⚠️ **This is the highest-stakes descriptive in F9** — the luck floor sizes the entire E4/human program, so if fixed rules move σ_game, every "games needed for a superhuman claim" number moves with it. |
| **Decision density** | **no instrument exists.** Closest: `scripts/measure_action_space.py` (legal-action count per ply) and `scripts/classical_search/midgame_disagreement.py` (self-disagreement, the CL-070 metric) | **build** a thin `scripts/rules_fixed/descriptives.py` over the C-lite corpus: plies, searched decisions/game, legal-action-count distribution, branching by phase. Cheap — it is a replay, not a search. |
| **Farm-economy norms** | `scripts/analyzer/corpus_stats.py` already emits `farm_pts`, `farm_pts_frac`, `farm_pts_per_farmer`, `first_farm_turn`, placement-k bands | **exists**; run it on both corpora and diff. Free. |

**Gate C (anti-cherry-pick):** the descriptive set is **pre-registered as reported-regardless-of-direction**,
walled vs fixed side by side, in one document. Descriptives carry **no claim id and retire no band** — but a
descriptive that is *selected after seeing it* is a finding laundered as a fact, and this gate is what
prevents that.

---

## 4. Phase D — the JCloisterZone differential oracle (R8 / BACKLOG 2026-08-02)

**Why it belongs in F9 rather than alongside it:** it is the only instrument that can **certify the fixed
rules before they are measured on**, and the only permanent guard against the class. Every gate we own is a
self-consistency gate; shared wrongness is invisible to all of them. JCloisterZone is Java, mature, and shares
no code — shared wrongness is impossible.

**What it validates, in priority order:**

1. **Farm `city_sides` for the 25 of 32 tile kinds never audited** — the audit's own verdict on the largest
   unaudited surface left. A wrong `city_sides` on one tile is worth 3 points per farm per game,
   *systematically*, and the traversal being provably correct does not help: the **data** is hand-authored in
   `base_deck.py`. Mechanism: farm-region equality on positions where farms are non-trivial.
2. **Legality** — the per-ply legal-placement set. This is the check that would have caught the wall, and it
   is the one that certifies A1.
3. **Scoring cross-check** — during-game events and final scores per player, which independently re-confirms
   the audit's "zero scoring-amount errors" verdict mechanically rather than by careful reading.

**Harness shape:**

- a small **Java driver** wrapping JCZ's game engine, reading a JSONL of `(ordered deck as tile ids, actions as
  (tile id, rotation, coordinate, meeple slot))` and emitting per-ply JSON: legal-set digest, running scores,
  free-meeple counts, completed-feature events;
- a python-side `scripts/rules_oracle/` adapter: **tile-id mapping table** (our 32 kinds ↔ JCZ ids), action
  translation (our action index → placement + rotation + meeple slot), and a differ;
- **CI mode**: N golden games replayed on every commit that touches `engine/` or the Rust core — this is the
  permanent-referee half and the reason to build it well rather than quickly.

**⚠️ Two unpriced risks, and the spike that must retire them before the build is funded (§7 J6, ~half a day):**

1. **Does JCZ expose a scriptable/headless game API**, or must the driver drive its internal controller? A
   "no scriptable API" answer reprices this from an agent-day to a week and comes straight back to Joshua.
2. **Edition mismatch.** Our deck is the **C3** base set with the **garden ("flowers") variants substituted
   in place**; JCZ implements the C1/C2 base set. So the tile map is not 1:1 for 8 tiles — and those 8 are
   *exactly* the ones whose non-garden geometry the audit lists as **assumed, not checked**. Resolution: map
   each garden tile to its plain counterpart and treat the comparison as **a test of that assumption** — a
   mismatch is a finding, not a harness bug. But state the limit honestly: **the oracle can certify the
   geometry of those 8 tiles, not their garden semantics.**

**Effort:** BACKLOG says ~an agent-day. Honest re-estimate: **half-day spike + 1–2 agent-days**, contingent on
the spike; the tile-id mapping and the action translation are the work, not the diffing.

---

## 5. Sequencing, gates, cost

### 5.1 Order (each phase gated; a red gate stops the phase, it does not get "worked around")

| # | phase | gate | build effort | box time |
|---|---|---|---|---|
| 1 | **A0** plumbing + `rules_profile` + manifest stamping | **G-A0**: 10 deck-paired games byte-identical with no flag (G6 pattern) · results.csv write refused for a non-`walled` profile unless stamped in `exp_id` | ~0.5 d | minutes |
| 2 | **A1-a** W4 sentinel + the 400-game champion-play probe | **G-A1a**: sentinel counts reported for every face; **the probe decides W2 vs W3** | ~0.5 d | ~1 h |
| 3 | **A1-b** the chosen geometry (W2 free, or W3 + a leaf `µs/leaf` bench **before** committing) | **G-A1b**: flags-off G1–G4 regate 0-mismatch · flags-on lockstep 1,000 games · even-shift property · **strict-xfail sentinel still xfails** · (W3 only) leaf bench inside the adoption bar | 0 d (W2) / 1–2 d (W3) | ~2–4 h |
| 4 | **A2** cloister scan | the five-part pattern of §A2 (flags-off regate · 1,000-game flags-on lockstep · both-engine reproducer · **mutation probe** · manifest counter) | ~0.5 d | ~2 h |
| 5 | **A3** unplaceable → redraw | same, **plus** the solver-bag equality check and the tiles-per-seat parity-invariant test over ≥1,000 fuzz games | ~1 d | ~2 h |
| 6 | **A4** retail start tile | already built; flag flip + `test_retail_and_recentring_compose` re-run | ~0.25 d | minutes |
| 7 | **C-lite** event rates under champion play (2 profiles × ~400 games) | **G-C**: reported regardless of direction, both profiles side by side | ~0.25 d | ~45 min two-box |
| 8 | **B** transfer-bound cell: **Arm W + Arm F, one fresh band** | **G-B**: the §2.3 decision map, committed before the first game; the §2.3 hard falsifiers | ~0.25 d (prereg) | **~1.5–2 h** |
| 9 | **C-full** luck floor · decision density · farm economy | **G-C** | ~0.5 d | ~1 h |
| 10 | **D** JCZ oracle | **spike gate first** (§4), then build + CI mode | 0.5 d spike + 1–2 d | — |

**Total: ~4–6 agent-days of build, ~a box-day of gates, and ~2 box-hours for the measurement everything
exists to serve.** The asymmetry is the point and should be read as a cost-discipline statement: the
expensive part is making the fixed-rules game *exist and be provably default-off*, not measuring on it.

### 5.2 ETAs at Rust-era speeds — and the stale-W rider

- **n=400 elo cell ≈ 45 min** local at the settled fair-eval **W\*=32** (DECISIONS 2026-08-02 night; the
  python-era price was ~7.5 h). Derived rate ≈ 530–555 games/h local.
- **Champion-play generation ≈ 328 games/h local, ≈ 260 laptop, ≈ 590 two-box** at production budget k8×1376
  (DECISIONS 2026-08-02 late afternoon). ⇒ a 400-game descriptive corpus ≈ 45 min two-box.
- **Ablation-class cells** (if the attribution ladder fires): the F7-era figure was ~45 s/game/worker; the
  workload has since converted to Rust on both sides (49×/side, 28× farm wall).
- ⚠️ **RIDER — re-sweep W before sizing any F9 farm.** DECISIONS 2026-08-02 (night) states plainly that the
  F7d morning W\* (local 30 / laptop 22) is **STALE** because the ablation workload changed era when its
  opponent converted. Adding rules flags is itself a workload change on top of that. The re-bench rule went
  2-for-2 in one day; a sweep is cheap at 49×/side and **must precede** any multi-hour F9 farm.
- ⚠️ **Any AVX-512 box must pass G0 first** (DECISIONS 2026-08-02 evening — a fourth libm implementation;
  results-capable only with the `NPY_DISABLE_CPU_FEATURES` env var in the launcher). Applies to cloud rentals.

### 5.3 Band plan

- **Reserve the block `1.00e11 – 1.10e11` for F9.** The registry's current high-water mark is 98e9 and the
  W-sweep throwaways used 9.69e10, so the block is clear.
- **Rows land in [governance/BAND_REGISTRY.csv](../governance/BAND_REGISTRY.csv) in the same commit that
  pre-registers each cell**, per the file's own rule — **not** in this spec. This document claims no band.
- **Arm W and Arm F share `B_F9`** (that is §2.2). The band retires at Phase-B close-out.
- **Walled bands (32e9, 88e9, 96e9, …) may not serve as the control for a fixed-rules claim.** The control
  is Arm W, on the fresh band. That is the operational content of "walled bands retire from confirmatory use".
- Enumerate before claiming: this registry **plus** `grep -h seed_start /mnt/c/carc-shared/*/manifest.json
  /mnt/c/carc-shared/*/*/manifest.json | sort -u` plus `/mnt/c/carc-shared/BAND_CLAIMS.txt` — `results.csv`
  has no band column and the old grep **fails silently open**.

---

## 6. Design tensions found while writing this spec

**T1 — "Fixed rules" is a bundle, but attribution wants one flag at a time.** A bound is only *publishable*
on a bundle (the question "does the walled record transfer to canonical rules" is a bundle question), while a
material move in a bundle is unattributable. Running 4 single-flag cells instead costs 4× and each is
underpowered for anything smaller than ~35 elo. **Resolution:** bundle for the bound; make every flag emit a
free per-flag **event counter** (§1) so attribution is usually available without spending; pre-register the
single-flag ladder to fire **only** on Branch 2. Sharpest for A3, which changes turn parity.

**T2 — recentring moves risk rather than only removing it, and the window is orthogonal to all of it.**
W2 takes downward headroom from 28 rows to 16, so it removes a **silent** face (denial) and makes a **fatal**
one (last-row, where the flat and object scorers additionally *disagree with each other*) materially more
reachable. That is a good trade **only with the W4 sentinel armed** — otherwise F9 replaces an unmeasurable
bias with an uncounted crash. And no board change of any size fixes `WindowOverflowError`: the 25×25 centroid
window is a *representation* cap, cheap to widen for the classical champion and checkpoint-invalidating for
every net arm.

**T3 — the charter's "FRESH band" instruction is, taken literally, structurally underpowered.** A fresh-band
fixed-rules cell compared against the historical band-32e9 walled number is a **cross-band** contrast, and the
house's own measured over-dispersion (1.8–2.2×, both statistics, "different decks" arithmetically excluded)
inflates σ(Δ) to ~31–40 elo — comparable to the entire effect under test. The fix costs **one extra 45-minute
cell**: put the walled control on the fresh band and pair the decks (§2.2). Without it, Branch 1 could fire
for lack of power and be misread as "the record transfers".

*(A fourth, folded into §2.4 rather than listed: because A2 changes meeple supply and the meeple curve is the
leaf's largest component, the fixed-rules champion may not be the walled champion — so Phase B measures the
transfer of a **contrast**, and absolute fixed-rules strength is not obtainable without a leaf re-sweep.)*

---

## 7. What stays Joshua's decision

Nothing below is pre-decided by this spec, and **building a flag adopts nothing**.

| # | decision |
|---|---|
| **J1** | **Fund F9, and at what scope** — A+B (the bound) · +C (descriptives) · +D (the oracle). |
| **J2** | **Which wall definition is "fixed rules" for eval** — W2 recentre-only (free) vs W3 runtime board size (provable, costs a leaf bench). **Recommend deciding after Gate A1-a**, not before. |
| **J3** | **Is A4 (retail start tile) in the transfer-bound bundle?** It is free to build and it *costs statistical power* (different deck composition ⇒ weaker CRN across arms). |
| **J4** | **Widen `window_size` (25 → ?)** — cheap for the classical champion, **retires the net arms** from any cell that does it. |
| **J5** | **ADOPTION of any rules change for the eval/desktop path.** Separate from every build gate above. The app is already centred and stays so; the global engine default and its strict-xfail sentinel do not move without this decision. |
| **J6** | **Fund the JCZ spike** (~half a day) before funding its build; a "no scriptable API" or edition answer comes back for a re-decision. |
| **J7** | **If Branch 2 fires:** fund the single-flag attribution ladder + the leaf caps/curve re-sweep. |
| **J8** | **If Branch 3 fires:** fund the n→800 extension (the trigger is pre-committed in §2.3; the *funding* is not). |
| **J9** | Which boxes, and whether F9 farms run beside anything else (`feedback_no_agent_compute_beside_eval`). |

**Standing throughout F9:** `governance/PRODUCTION.yaml` untouched · no `experiments/results.csv` row until a
cell closes · no band claimed until its cell is pre-registered · the global engine default stays walled and
`test_no_rule_legal_placement_is_ever_denied` stays a strict xfail until J5 says otherwise.

---

## 8. Close-out checklist for this program (the six touches, per CLAUDE.md)

Per closing phase: (1) `experiments/results.csv` row → (2) DECISIONS index line → (3) status stamp on **this**
doc → (4) governance row flip (`CLAIM_REGISTRY.csv` / `BAND_REGISTRY.csv` claimed→retired) → (5) STATUS top
block → (6) the **F9 line** in [docs/PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md). Then
`python3 scripts/doc_lint.py`. New levers or declined options discovered along the way get a row in
[docs/LEVER_INDEX.md](LEVER_INDEX.md) — **including the declined ones, with their one-clause reason** (W1/W3,
R6, R7 all qualify).
