#!/usr/bin/env python3
"""`screen_lib` — the FPU DOSE-LADDER round's shared instrument library.

⭐ **A FORK of `measurement/fpu_resurrection_prep/screen_lib.py`** (which was
itself a fork of phasegate's). The parts that were hardened by two rounds of
merge review are carried **verbatim in construction**: `cross_box_rev_gate` (the
IS-A1 fold), `rev_matches`, `is_hex40`, `host_matches_box`, `paired_margin`,
`winrate_elo` with the **R4 deck-paired elo footing**, `recon_close`,
`resolve`/`gate`, `se_anomaly`, `arb_off_gate`, `twosided_gate`, `leaf_gate`.

⛔ **WHAT IS NEW, AND WHY A COPY WOULD HAVE BEEN WRONG:**

  ⭐⭐ **THE BARS ARE EFFECT-SIZED, NOT `2σ̂`-SIZED** (owner ruling 2026-08-30,
     "effect size sounds right"; `CLAUDE.md` results-discipline). The parent
     round's `BAR_M = 1.381` was *exactly* `2·se_model(400)`, and §8 of its
     READ_RULE had to disclose that a true null was then very nearly a coin flip
     between `F-REKILL` and `F-UNRESOLVED`. This round writes its bar from the
     DECISION — `+1.5 pts/deck` is the effect that would survive the adoption
     chain — and states, before game 1, exactly what that costs in read
     probability (`READ_RULE.md` §8, `null_read_distribution()` below).
  ⭐⭐ **`G-N` AND `G-DECKS` ARE IMPLEMENTED TO THE PROSE** — this is the
     `FPU-A1` lesson, and it is the single most important carried fix. The
     parent's frozen prose said *"a failure rate strictly below 2% is REPORTED,
     never silently absorbed … at or above it the cell voids"* and
     *"`n_common >= 80%` of 400"*, but its CONDITION COLUMNS demanded
     `n == 800, n_failed == 0` and `n_common == 400`. A single deterministic
     `WindowTruncationError` (1/800 = 0.125%) VOIDED a healthy cell, and the
     amendment had to be written with the statistics visible. Here the 2%
     failure bar and the 80% common-deck floor ARE the implementation.
  ⭐ **`G-CPUCT` IS GONE.** Every cell of this round owns `fpu_reduction`; there
     is no c_puct cell. ⛔ But the c_puct ASSERTION is not gone: `knob_gate`
     still demands `config.cand_search.c_puct is null` on every cell, because a
     stray `--cand-c-puct` would be a second variable that `G-SINGLEVAR` would
     also catch — two witnesses, not one.
  ⭐ **THE ROUND-LEVEL VERDICT IS NEW.** The parent had three independent
     questions and no round verdict. This round is a LADDER: `LADDER-DEAD`
     (every rung bounded below the effect bar) is a conjunction over all four
     rungs and is the branch that discharges the funded decision.

⛔⛔ **IS-D1 IS BINDING ON EVERY ADDRESS.** Config-shaped values resolve from
`manifest.json`; statistics from `summary.json`, **which carries no config block
at all**. `resolve()` returns the ADDRESS that answered and every gate prints it.

⛔ **ABSENT IS FAIL, never a skip and never a default** (`READ_RULE.md` §4).
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path  # noqa: F401  (kept for parity with the parent fork)

# =========================================================================== #
# 0. FROZEN CONSTANTS — the pair is law; these restate it, they do not decide  #
# =========================================================================== #

#: `DESIGN.md` §5. ⛔ PROPOSED, NOT CLAIMED at build time. FOUR bands, ONE PER
#: CELL — the `fpu_resurrection` pattern, NOT the G3 shared-deck-set pattern.
#: Each rung's primary is ITS OWN margin against zero; nothing is pooled and
#: nothing is deck-matched across rungs, so a shared band would buy no
#: deck-matching that any gate reads and would spend ONE band's
#: `decision_influenced` retirement on FOUR verdicts.
#: ⚠️ `162e9` and `163e9` are RESERVED by the S1 G3 round (claimed 161e9,
#: reserved the next two) — this ladder starts at `164e9`.
#: ⚠️⚠️ `146000000000` IS THE TRAP THE CLAIM ORDER EXISTS FOR — absent from
#: `governance/BAND_REGISTRY.csv` but carrying references in the tree. The
#: registry is NECESSARY AND NOT SUFFICIENT; the TREE SWEEP is the binding
#: check and is re-run immediately before the CSV append.
BANDS = {"CELL_FPU005": 164_000_000_000,
         "CELL_FPU010": 165_000_000_000,
         "CELL_FPU015": 166_000_000_000,
         "CELL_FPU030": 167_000_000_000}
#: The sub-range the §9 smoke plays. ⛔ NEVER in any band claim — it buys no
#: decks of the round. Placed at the TOP of the HIGHEST band's 1e9 space, the
#: phasegate/fpu_resurrection convention.
THROWAWAY_BASE = 167_999_999_000
THROWAWAY_SPAN = 1000

#: `DESIGN.md` §2 — identical on BOTH sides of every cell.
LEAF_HASH = "a36d2e15a3b3d71d"
LEAF_CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
#: ⭐⭐ THE BUDGET — the 2026-08-30 promoted desktop champion, BOTH sides.
#: ⛔ `run_cells.sh` RE-ASSERTS this against `governance/PRODUCTION.yaml` at
#: launch (`G-PROD`) rather than trusting the restatement: a frozen budget that
#: has silently drifted from the champion is a cell measuring a knob against a
#: stale opponent, and every other gate would pass it.
K_DETS, SIMS_PER_DET, TOTAL_SIMS = 16, 1376, 22016
EXACT_K, EXACT_MODE = 2, "marginalized"
RULES_PROFILE = "fixed_v1"
BACKEND = "rust"
#: The champion's own PUCT constant. Every cell must leave it alone: this round
#: varies `fpu_reduction` and nothing else.
CHAMP_C_PUCT = 1.5

#: `READ_RULE.md` §4 `G-SAT` — a RAIL check, not a strength bar.
SAT_BAND = (0.35, 0.65)

# --------------------------------------------------------------------------- #
# ⭐⭐ `G-N` / `G-DECKS` — THE `FPU-A1` FIX, AND IT IS THE PROSE                #
# --------------------------------------------------------------------------- #
#: A failure rate **strictly below** this is **REPORTED, never silently
#: absorbed** (the `b32v64` 0.100% rust-panic precedent). **At or above it the
#: cell voids.** ⛔ THE PARENT ROUND'S GATE DEMANDED `n_failed == 0` AND
#: `n_common == 400` INSTEAD, AND VOIDED A HEALTHY CELL OVER 1 GAME IN 800
#: (`measurement/fpu_resurrection_prep/AMENDMENTS.md`, FPU-A1). The bar below IS
#: the condition; there is no stricter column anywhere in this file.
FAILURE_RATE_VOID = 0.02
#: And the common-deck floor is a FRACTION, never an equality.
N_COMMON_FLOOR_FRACTION = 0.80

#: `DESIGN.md` §3 — the sizing constant, carried unchanged from the Stage-2
#: Phase B cell `ARB` (`M +3.0700`, `paired_z +4.445`, `n_paired 400 DECKS`) so
#: this round's power arithmetic sits on the same footing as its parent's.
#: ⭐ THE PARENT ROUND HAS SINCE REALIZED THREE SIBLINGS OF IT at exactly this
#: shape (n≈400 decks, 22016 both sides, arb off): `se` 0.6826 / 0.7153 / 0.6511
#: ⇒ `sigma_D` 13.65 / 14.29 / 13.02. The carried 13.81 sits inside that spread,
#: so the model is corroborated rather than merely inherited.
#: ⛔ POWER ARITHMETIC ONLY: `READ_RULE.md` §1 forbids it as a denominator in
#: any branch test — every branch is adjudicated at the cell's OWN REALIZED SE.
SIGMA_D_MODEL = 13.81
REALIZED_SIGMA_D_SIBLINGS = {"fpu_resurrection/CELL_FPU02 (b155e9, n=400)": 13.65,
                             "fpu_resurrection/CELL_FPU04 (b156e9, n=399)": 14.29,
                             "fpu_resurrection/CELL_CPUCT10 (b157e9, n=400)": 13.02}
#: Flag (never void) a realized/modelled SE ratio outside this band.
SE_ANOMALY_BAND = (0.70, 1.43)

# --------------------------------------------------------------------------- #
# ⭐⭐ THE BARS — WRITTEN FROM THE DECISION, NOT FROM `2σ̂`                      #
# --------------------------------------------------------------------------- #
#: **Owner ruling, 2026-08-30 ("effect size sounds right"), now a standing house
#: rule in `CLAUDE.md`:** *bars are set at the effect size the decision cares
#: about — NEVER at `2σ̂` of the instrument.* A bar defined as exactly
#: `2·se_model` makes the kill branch fire only on a NEGATIVE point estimate, so
#: a true null reads UNRESOLVED about half the time and the round discharges
#: nothing. That was realized twice before the ruling (phasegate A1's
#: `+0.49±0.37` against its `0.80 ≈ 2σ̂` bar, and the parent FPU round's
#: `BAR_M = 1.381 = 2·se(400)`, whose READ_RULE §8 had to disclose the coin
#: flip).
#:
#: ⭐ **`+1.5 pts/deck` IS A DECISION QUANTITY.** It is the effect that would
#: survive the adoption chain's attrition (production H2H with the arbiter ARMED
#: → Carcasum external → an E4 epoch on the phone) and still be worth deploying.
#: It is also, deliberately, *no easier than what we already hold*: the realized
#: `fpu=0.2` cell's own `LB95` was `+1.586`, so a new rung must be at least as
#: good as the incumbent to displace it.
#:
#: ⛔ **THE SAME NUMBER CARRIES BOTH DIRECTIONS**, which is what makes the two
#: branches exhaustive and exclusive:
#:     ADOPT-CANDIDATE  `LB95(M) >= +1.5`   (the rung beats the bar at 95%)
#:     BOUNDED          `UB95(M) <  +1.5`   (the rung is BELOW the bar at 95%)
BAR_EFFECT = 1.5             #: pts/deck — the ONE bar, read in two directions.
BRANCH_Z = 2.0               #: the `R-NEGATIVE` sigma bar (harm, not adoption).

#: ⭐ THE SECONDARY'S RESOLUTION. ⚠️ **NOT A BAR.** `+1.5 pts/deck` has no
#: exchange rate into elo that this round measures, so the elo is reported with
#: its own DECK-PAIRED CI and the instrument's own 2σ resolution beside it — and
#: ⛔ NO branch reads it. `sanity_check()` re-derives this from
#: `elo_sigma_paired` so the constant can never drift from the arithmetic.
ELO_RESOLUTION_2SIGMA = 17.4
#: ⭐ R4 (carried) — **THE ELO FOOTING.** 800 games are 400 decks × 2 seatings,
#: and pairing scales sigma by `1/sqrt(2)`. The textbook binomial sigma
#: `winrate_elo` computes is the UNPAIRED one (±24.6 at 2σ, n=800); quoting it
#: beside a paired figure compared two different rulers. Every emitted field
#: NAMES its footing.
PAIRING_FACTOR = 1.0 / math.sqrt(2.0)          #: ≈ 0.70711

#: `RECON` tolerance (`READ_RULE.md` §1.2).
RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
#: `G-REV`: the minimum short-rev prefix `rev_matches` will canonicalize.
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"

# --------------------------------------------------------------------------- #
# ⛔⛔ THE PRE-STATED CONTEXT ROWS — THE PARENT ROUND'S REALIZED 0.2 AND 0.4    #
# --------------------------------------------------------------------------- #
#: ⭐ These are stated HERE, BEFORE GAME 1, because they are the reason this
#: ladder exists and the reason its bar is `+1.5`. ⛔⛔ THEY ARE CONTEXT ROWS
#: AND NOTHING ELSE — never pooled, never z-combined, never a gate input, never
#: interpolated against a rung of this round.
#:
#: ⚠️⚠️ **CL-068 BINDS IN FULL.** Every contrast between one of these and a rung
#: of this ladder is CROSS-BAND, and CL-068 measured **1.8–2.2× over-dispersion
#: on merely cross-band contrasts** — in BOTH the elo and the deck-paired-margin
#: statistics, with an identity control exonerating the harness. The robust
#: class is the WITHIN-band deck-paired contrast, which is exactly what each
#: rung's own primary is and exactly what no cross-rung comparison can be.
CONTEXT_ROWS = {
    "fpu_reduction=0.2 (fpu_resurrection CELL_FPU02, band 155e9)": {
        "M": 2.95125, "se": 0.6825808836692004, "z": 4.3236634230592745,
        "LB95": 1.586088232661599, "UB95": 4.316411767338401,
        "n_paired": 400, "n_games": 800, "elo": 26.1,
        "ci95_elo_paired": [8.69, 43.53], "winrate": 0.5375,
        "branch": "F-RESURRECT",
        "note": "⭐ THE INCUMBENT. Realized 2026-08-30 on the CLASSICAL "
                "champion at k16x1376=22016, arb OFF both sides, fixed_v1+R9, "
                "exact_k 2 marginalized, rust, leaf a36d2e15a3b3d71d. ⛔ It "
                "licensed PROPOSING follow-on work and NOTHING ELSE: no "
                "production change, and 0.2 is a LADDER ENDPOINT — unbracketed "
                "from below, which is what this round fixes."},
    "fpu_reduction=0.4 (fpu_resurrection CELL_FPU04, band 156e9)": {
        "M": 0.7543859649122807, "se": 0.7153318548949373,
        "z": 1.0545957931973815,
        "LB95": -0.676277744877594, "UB95": 2.1850496747021553,
        "n_paired": 399, "n_games": 799, "elo": -1.74,
        "ci95_elo_paired": [-19.12, 15.64], "winrate": 0.4975,
        "branch": "F-UNRESOLVED (AMENDED — FPU-A1)",
        "note": "⚠️ AMENDED from a frozen `U-VOID` by "
                "`fpu_resurrection_prep/AMENDMENTS.md` FPU-A1: the adjudicator's "
                "G-N/G-DECKS CONDITION COLUMNS were stricter than their own "
                "frozen PROSE and voided the cell over ONE deterministic "
                "`WindowTruncationError` (1/800 = 0.125%). ⛔ `F-UNRESOLVED` "
                "DISCHARGES NOTHING — it is not a null and not a bound "
                "(feedback_noisy_plateau_not_a_conclusion). ⭐ THIS ROUND'S "
                "G-N/G-DECKS ARE WRITTEN TO THAT PROSE so the same healthy cell "
                "would read, not void."},
}
CONTEXT_WARNING = (
    "⛔⛔ CONTEXT ROWS, NEVER A BRANCH INPUT AND NEVER POOLED. The 0.2 and 0.4 "
    "readings are on bands 155e9 / 156e9; every rung of this ladder is on its "
    "own fresh band. CL-068 measured 1.8-2.2x OVER-DISPERSION on merely "
    "CROSS-BAND contrasts, in BOTH the elo and the deck-paired-margin "
    "statistics — so a rung-vs-context difference is not a measurement, and the "
    "arithmetic that would combine them does not exist. ⭐ What these rows "
    "legitimately did is a DESIGN act, spent before any number of this round "
    "exists: they fixed WHICH doses to ask about (0.2 was an unbracketed "
    "endpoint; the falling-with-dose direction says bracket it from BELOW) and "
    "WHAT BAR is worth paying for (+1.5 is no easier than 0.2's own LB95). "
    "⛔ No branch below reaches back into them."
)

#: ⛔⛔ The axis's own history, carried from the parent round.
#: `docs/LEVER_INDEX.md:146` recorded FPU as CLOSED on NEURAL/value-blended
#: evidence; `fpu_resurrection` reopened it narrowly (the knob was structurally
#: unreachable on the classical champion's backend until 2026-08-29) and its
#: 0.2 cell fired. This ladder is the follow-on that reopening licensed.
PRIOR_ART = {
    "verdict_fpu02_paired_n200 (2026-06-02)": {
        "elo": 45.4, "z": 1.85, "n_games": 200,
        "agent": "NeuralMCTS, pathb_loop/ckpt/iter_11.pt priors + v2_7 leaf, c=3.0",
        "note": "a SCREEN (z<2), never confirmed; results.csv row 68"},
    "verdict_fpu04_paired_n200 (2026-06-02)": {
        "elo": 31.4, "z": 1.28, "n_games": 200,
        "agent": "same, fpu 0.4",
        "note": "a SCREEN (z<2), never confirmed; results.csv row 69"},
    "m3 FPU curve (2026-07-02/03, results.csv rows 233-236)": {
        "winrates": {0.4: 0.391, 0.6: 0.496, 0.8: 0.4825, 1.0: 0.476},
        "n_games": 400,
        "agent": "iter_02+warmstart ADDITIVE value-blend b=0.27 vs pure-v2.9 "
                 "anchor, sims=100, band 6.0e9",
        "note": "⚠️ measures FPU as a RESCUE for a bad learned value on a "
                "100-sim neural agent — NOT as a lever on the classical "
                "champion's 1376-sim heuristic-prior search. ⛔ CROSS-ERA as "
                "well as cross-band, which is strictly worse than CL-068's "
                "cross-band over-dispersion."},
}


# =========================================================================== #
# 1. THE CELLS                                                                 #
# =========================================================================== #

@dataclass(frozen=True)
class CellSpec:
    """One archive = one rung = one band. ⛔ Nothing is pooled in this round."""
    name: str
    role: str                       #: "local" | "laptop" — `G-HOST`'s frozen box
    knob: str                       #: "fpu_reduction" (every rung of this round)
    value: float                    #: `G-FPU`'s frozen expectation
    seed_start: int
    n_decks: int
    purpose: str

    @property
    def n_games(self) -> int:
        return self.n_decks * 2

    @property
    def seed_end(self) -> int:
        """INCLUSIVE last seed of this cell's own range."""
        return self.seed_start + self.n_decks - 1

    @property
    def cand_fpu(self):
        """The candidate's RESOLVED fpu_reduction. `None` == the champion."""
        return self.value if self.knob == "fpu_reduction" else None

    @property
    def cand_c_puct(self):
        """⛔ ALWAYS `None` in this round: no rung varies `c_puct`, and
        `knob_gate` asserts the override is absent-as-null on every cell."""
        return self.value if self.knob == "c_puct" else None


#: ⭐ THE FOUR RUNGS. Each is n=800 games = 400 seat-balanced decks × 2 seatings,
#: on ITS OWN fresh band, against the UNMODIFIED champion, candidate-only knob.
#:
#: ⭐⭐ WHY THESE FOUR AND NOT A FINER GRID: the parent round measured 0.2
#: (`+2.95`, fired) and 0.4 (`+0.75`, unresolved). Two doses give a DIRECTION —
#: falling with dose — and NEVER an optimum. 0.2 is therefore a LADDER ENDPOINT,
#: and `feedback_bracket_hyperparams` is explicit that a peak at an endpoint is
#: NOT bracketed: extend before adopting. Three of these rungs (0.05/0.1/0.15)
#: bracket 0.2 FROM BELOW — the direction the data points — and 0.3 adds one
#: interior point between 0.2 and 0.4 so the shape between the two measured
#: doses is not assumed.
#:
#: ⭐ BOX ASSIGNMENT IS **WHOLE CELLS PER BOX** (`G-HOST`), 2 local + 2 laptop.
#: `DESIGN.md` §6 states the realized-rate arithmetic and DISCLOSES the residual
#: imbalance rather than engineering it away with sub-cells and a pooled primary.
CELLS: tuple[CellSpec, ...] = (
    CellSpec("CELL_FPU005", "local", "fpu_reduction", 0.05,
             BANDS["CELL_FPU005"], 400,
             "⭐ THE LOW BRACKET POINT. A dose 4x below the incumbent. ⛔ It is "
             "also the round's own liveness worry: a dose small enough to change "
             "no decision is indistinguishable from a knob that never bound, "
             "which is why the golden gate's positive control is run AT THIS "
             "DOSE and not at 0.2 (DESIGN §9)."),
    CellSpec("CELL_FPU010", "local", "fpu_reduction", 0.10,
             BANDS["CELL_FPU010"], 400,
             "⭐ THE MIDDLE BRACKET POINT, half the incumbent dose."),
    CellSpec("CELL_FPU015", "laptop", "fpu_reduction", 0.15,
             BANDS["CELL_FPU015"], 400,
             "⭐ THE NEAR BRACKET POINT — the rung immediately below the "
             "incumbent 0.2. ⚠️ A rung adjacent to a fired endpoint is where a "
             "winner's-curse crest would show up as a shortfall, and the "
             "read-out says so rather than reading a shortfall as a peak."),
    CellSpec("CELL_FPU030", "laptop", "fpu_reduction", 0.30,
             BANDS["CELL_FPU030"], 400,
             "⭐ THE INTERIOR POINT ABOVE — between the fired 0.2 and the "
             "unresolved 0.4. ⛔ It is NOT a test of the 0.2-to-0.4 direction: "
             "that contrast is cross-band and CL-068 forbids it."),
)


def cell_by_name(name: str) -> CellSpec:
    for c in CELLS:
        if c.name == name:
            return c
    raise KeyError(f"unknown cell {name!r}; known: {[c.name for c in CELLS]}")


def cells_of_box(role: str) -> tuple[CellSpec, ...]:
    return tuple(c for c in CELLS if c.role == role)


#: ⭐ THE ADOPTION CHAIN, FROZEN BEFORE ANY NUMBER EXISTS (`READ_RULE.md` §6).
#: ⛔ Named here so that a fired rung cannot later be walked through a shorter
#: chain than the one this round pre-registered.
ADOPTION_CHAIN = (
    "1. THIS LADDER — a rung reads R-ADOPT-CANDIDATE (LB95 >= +1.5 pts/deck) on "
    "its own fresh band, arbiter OFF both sides.",
    "2. PRODUCTION H2H — the winning dose vs the DEPLOYED champion with the "
    "TIE ARBITER ARMED (B=64, PRODUCTION.yaml since 2026-08-20), on a FRESH "
    "band. ⛔ This round is a B=0 result and the transfer is an ASSUMPTION.",
    "3. CARCASUM EXTERNAL — the arm-on T-TRANSFER protocol, the only "
    "out-of-family check this program has.",
    "4. E4 EPOCH on the phone.",
    "⛔ EACH LEG IS ITS OWN PREREG, ITS OWN BAND AND ITS OWN OWNER FUNDING. A "
    "rung firing here funds NOTHING automatically.",
)

#: ⭐ AND THE FALLBACK, equally pre-registered: if the ladder is DEAD, the
#: incumbent stands and its own confirmation leg becomes proposable.
LADDER_DEAD_CONSEQUENCE = (
    "⭐ `fpu_reduction = 0.2` STANDS AS BEST-KNOWN and its CONFIRMATION LEG "
    "(step 2 of ADOPTION_CHAIN: a production H2H with the arbiter ARMED, on a "
    "fresh band) is LICENSED TO PROPOSE. ⚠️ 'Licensed to propose' is not "
    "'funded': the owner funds it. ⛔ LADDER-DEAD does NOT re-close the axis "
    "and does NOT retract the 0.2 reading — it says the four doses measured here "
    "are each bounded below +1.5 pts/deck at 95%, and nothing more."
)


# =========================================================================== #
# 2. ADDRESS RESOLUTION — IS-D1 (carried verbatim in construction)             #
# =========================================================================== #

MISSING = object()


def _dig(doc, dotted: str):
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return MISSING
        cur = cur[part]
    return cur


def resolve(docs: Mapping[str, Mapping], *addresses: str):
    """`(value, address)` — the FIRST address that answers, or `(MISSING, None)`.

    ⛔ EVERY gate prints the address that answered: IS-D1's defect was a precheck
    that read `config` off `summary.json` — which carries NO config block at all
    — got `{}`, failed closed on one conjunct and passed VACUOUSLY on another.

    ⚠️⚠️ **`MISSING` IS NOT `None`.** `config.cand_search.fpu_reduction = null`
    is a POSITIVE statement ("the champion's legacy optimistic q=0") while an
    ABSENT key means the harness never resolved the knob. `resolve` returns the
    sentinel, and no gate may collapse the two.
    """
    for addr in addresses:
        doc_name, _, path = addr.partition(":")
        doc = docs.get(doc_name)
        if doc is None:
            continue
        v = _dig(doc, path)
        if v is not MISSING:
            return v, addr
    return MISSING, None


def gate(gid: str, ok: bool, detail, addr: str | None = None, why: str = "") -> dict:
    """One gate's verdict record. ⛔ `ABSENT` is `FAIL`, so an unresolved value
    arrives here as `ok=False` with `address=None` — never as a skip."""
    return {"gate": gid, "ok": bool(ok), "detail": detail,
            "address": addr or "ABSENT (no address answered) — ABSENT is FAIL",
            "why": why}


# =========================================================================== #
# 3. REV / PROVENANCE — carried from phasegate via fpu_resurrection (IS-A1)    #
# =========================================================================== #

def split_dirty(code_rev: str) -> tuple[str, bool]:
    """`(sha_part, had_dirty_marker)`. The marker is WHOLE-TREE scoped and is
    REPORTED, never fatal — `run_manifest.code_rev()` computes dirtiness over the
    whole tree and the main tree is perpetually dirty with measurement logs. The
    fatal, code-path-scoped verdict is `SRC_CLEAN.jsonl`'s."""
    s = (code_rev or "").strip()
    if s.lower().endswith(DIRTY_SUFFIX):
        return s[: -len(DIRTY_SUFFIX)], True
    return s, False


def is_hex40(s) -> bool:
    return (isinstance(s, str) and len(s) == 40
            and all(c in "0123456789abcdef" for c in s.lower()))


def rev_matches(code_rev, pinned) -> tuple[bool, str]:
    """`(ok, why)` — does a manifest's short `code_rev` NAME `PINNED_SRC_REV`?

    Strip the whole-tree `-dirty` marker, then require a `>= MIN_REV_PREFIX`-hex
    PREFIX match against the 40-hex pin. ⛔ Identity only; cleanliness is
    `SRC_CLEAN.jsonl`'s question, because only that reading is scoped to the
    code paths."""
    if not code_rev or not isinstance(code_rev, str):
        return False, "code_rev ABSENT — ABSENT is FAIL"
    if not pinned or not isinstance(pinned, str):
        return False, "PINNED_SRC_REV ABSENT — ABSENT is FAIL"
    cr, dirty = split_dirty(code_rev)
    cr, pn = cr.lower(), pinned.strip().lower()
    note = ("; ⚠️ whole-tree `-dirty` marker present — INFORMATIONAL ONLY (the "
            "code-path verdict is SRC_CLEAN.jsonl's)" if dirty else "")
    if not is_hex40(pn):
        return False, f"PINNED_SRC_REV {pinned!r} is not a 40-hex sha{note}"
    if len(cr) < MIN_REV_PREFIX or any(c not in "0123456789abcdef" for c in cr):
        return False, f"code_rev {code_rev!r} is not >= {MIN_REV_PREFIX} hex chars{note}"
    if not pn.startswith(cr):
        return False, (f"code_rev {code_rev!r} is not a prefix of PINNED_SRC_REV "
                       f"{pinned!r}{note}")
    return True, f"code_rev {code_rev!r} names PINNED_SRC_REV {pinned!r}{note}"


def cross_box_rev_gate(revs_by_cell: Mapping, pins_by_role: Mapping) -> dict:
    """⭐ THE IS-A1 FOLD, carried unchanged. "Was this ONE round, at ONE rev,
    across BOTH boxes?" — ⛔ NEVER by comparing one box's emitted short rev to
    the other's.

      (1) **THE PINS AGREE.** Every role that published a `PINNED_SRC_REV` must
          publish the SAME 40-hex sha. A missing pin is FAIL.
      (2) **EVERY EMITTED REV CANONICALIZES TO THAT PIN** via `rev_matches`.

    ⚠️ A single-box round (and the §9 smoke) passes (1) trivially with one pin,
    which is correct: there is no cross-box proposition to check."""
    pins = {r: (p or "").strip().lower()
            for r, p in (pins_by_role or {}).items() if p}
    base = {"pins": pins, "revs": dict(revs_by_cell or {}), "canonicalized": {}}
    if not pins:
        return {**base, "ok": False, "distinct_pins": [],
                "why": ("no box published a PINNED_SRC_REV — ABSENT is FAIL. The "
                        "cross-box single-rev property cannot be established "
                        "without the pins, and IS-A1 forbids falling back to "
                        "comparing the emitted revs to each other.")}
    bad_pins = sorted(r for r, p in pins.items() if not is_hex40(p))
    distinct = sorted(set(pins.values()))
    if bad_pins:
        return {**base, "ok": False, "distinct_pins": distinct,
                "why": (f"box(es) {bad_pins} published a PINNED_SRC_REV that is "
                        "not a 40-hex sha — ABSENT-or-malformed is FAIL.")}
    if len(distinct) > 1:
        return {**base, "ok": False, "distinct_pins": distinct,
                "why": ("⛔ THE BOXES WERE AT DIFFERENT COMMITS: their "
                        f"PINNED_SRC_REV files disagree ({distinct}). This is a "
                        "mixed-rev round and the git-bundle sync exists to "
                        "prevent exactly it. ⚠️⚠️ IT IS THE PRIMARY RISK OF THIS "
                        "FAMILY OF ROUNDS: the fpu plumbing is PYTHON-ONLY, so "
                        "a box running pre-fix source would silently serve a "
                        "knob-FREE candidate — champion-vs-champion — with a "
                        "healthy-looking wheel and a healthy-looking leaf hash. "
                        "⚠️ NOTE THIS IS THE PINS DISAGREEING, NOT THE SHORT "
                        "REVS — the short revs disagreeing is EXPECTED (IS-A1).")}
    pin = distinct[0]
    canon, bad = {}, []
    for name, rev in (revs_by_cell or {}).items():
        ok, why = rev_matches(rev, pin)
        canon[name] = {"code_rev": rev, "ok": ok, "why": why}
        if not ok:
            bad.append(f"{name}: {why}")
    return {**base, "ok": not bad, "distinct_pins": distinct, "pin": pin,
            "canonicalized": canon,
            "why": ("every cell's emitted code_rev canonicalizes to the ONE pin "
                    f"{pin} that every box published — short revs of different "
                    "lengths are expected and harmless (IS-A1)" if not bad else
                    "⛔ a cell's emitted code_rev does NOT name the shared pin: "
                    + "; ".join(bad))}


_HOST_ALIASES = {"laptop": ("laptop", "laptop-wsl", "laptop-pop", "pop-os", "pop"),
                 "local": ("doctor", "5800x", "desktop", "local")}


def host_matches_box(observed_host, role: str) -> tuple[bool, str]:
    """`G-HOST` — substring test on a NORMALISED hostname.
    ⚠️ `laptop`/`laptop-wsl`/`laptop-pop`/`pop-os` are ONE physical machine."""
    if not observed_host or not isinstance(observed_host, str):
        return False, "host ABSENT — ABSENT is FAIL"
    h = observed_host.strip().lower()
    for alias in _HOST_ALIASES.get(role, ()):
        if alias in h:
            return True, f"host {observed_host!r} matches box role {role!r} (via {alias!r})"
    # the local box is whatever is NOT the laptop — stated explicitly, because a
    # negative test that is not written down is a test nobody can audit
    if role == "local" and not any(a in h for a in _HOST_ALIASES["laptop"]):
        return True, f"host {observed_host!r} is not the laptop ⇒ treated as {role!r}"
    return False, f"host {observed_host!r} does not match box role {role!r}"


# =========================================================================== #
# 4. THE STATISTIC — `RECON`'s independent re-implementation                   #
# =========================================================================== #

def _by_deck(records: Iterable[Mapping]) -> dict[int, dict[int, float]]:
    """`{seed: {a_seat: diff}}`. A record missing `seed`, `a_seat` or `diff` is
    DROPPED here and shows up as a short `n_paired` at `G-DECKS` — it is never
    silently defaulted to zero."""
    out: dict[int, dict[int, float]] = {}
    for r in records:
        if not isinstance(r, Mapping):
            continue
        s, a, d = r.get("seed"), r.get("a_seat"), r.get("diff")
        if s is None or a is None or d is None:
            continue
        out.setdefault(int(s), {})[int(a)] = float(d)
    return out


def per_deck_margins(records: Iterable[Mapping]) -> dict[int, float]:
    """`D(d) = (diff(d, a_seat=0) + diff(d, a_seat=1)) / 2`, over decks appearing
    in BOTH seatings. A deck missing a seating is DROPPED, never zero-filled
    (`READ_RULE.md` §1). `diff` is CANDIDATE minus OPPONENT in POINTS, so
    `D > 0` ⇒ the candidate won."""
    return {s: (v[0] + v[1]) / 2.0
            for s, v in sorted(_by_deck(records).items()) if 0 in v and 1 in v}


def paired_margin(records: Iterable[Mapping]):
    """`READ_RULE.md` §1's statistic, recomputed from the raw records.

    Returns `(mean, z, n_paired, se, per_deck_list)`. ⚠️ Accumulated with
    `math.fsum` rather than `sum` DELIBERATELY: the point of a witness is to be a
    DIFFERENT computation. An imported `_paired_z` would agree by construction
    and witness nothing. ⛔ It can only VOID, never move, a number."""
    per_deck = list(per_deck_margins(records).values())
    n = len(per_deck)
    if n < 2:
        return None, None, n, None, per_deck
    mean = math.fsum(per_deck) / n
    var = math.fsum((d - mean) ** 2 for d in per_deck) / (n - 1)
    se = math.sqrt(var / n)
    z = (mean / se) if se > 0 else float("nan")
    return mean, z, n, se, per_deck


def elo_sigma_unpaired(wr: float, n_games: int) -> float:
    """1σ on elo from the plain binomial, treating every GAME as independent.

    ⛔ THE WRONG FOOTING FOR THIS ROUND; emitted only so the correction is
    auditable: 800 games are 400 decks × 2 seatings, not 800 independent draws."""
    return ((400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n_games)
            / (wr * (1 - wr)))


def elo_sigma_paired(wr: float, n_games: int) -> float:
    """⭐ 1σ on elo on the **DECK-PAIRED** footing — the one
    `ELO_RESOLUTION_2SIGMA` is stated on, and the one the primary margin already
    uses. `PAIRING_FACTOR` applied (R4)."""
    return elo_sigma_unpaired(wr, n_games) * PAIRING_FACTOR


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """W/D/L, winrate and elo recomputed from the raw records.

    ⚠️⚠️ **R4 (carried): THE EMITTED SIGMA IS DECK-PAIRED.**
    `elo_sig_1sigma_paired` is the field the read-out's CI is built from;
    `elo_sig_1sigma_unpaired` is carried beside it so the factor is visible
    rather than buried. ⛔ The old unlabelled `elo_sig_1sigma` key is GONE ON
    PURPOSE — a footing that is not in the field name is a footing nobody checks.

    ⚠️⚠️ THE ELO IS THIS ROUND'S **SECONDARY AND IS NOT A BAR AT ALL**. The
    adoption bar is `+1.5 pts/deck` on the deck-paired margin; there is no
    exchange rate into elo that this round measures. The elo is reported with its
    own CI on every branch, the instrument's 2σ elo resolution is printed beside
    it as a RESOLUTION (never a bar), and a disagreement between the margin and
    the elo is DISCLOSED rather than arbitrated."""
    scored = [r for r in records if isinstance(r, Mapping) and "diff" in r]
    n = len(scored)
    if n == 0:
        return {"n": 0, "W": 0, "D": 0, "L": 0, "winrate": None, "elo": None,
                "elo_sig_1sigma_paired": None, "elo_sig_1sigma_unpaired": None,
                "elo_footing": "deck-paired", "avg_diff": None}
    w = sum(1 for r in scored if r.get("won_by_champ") is True)
    d = sum(1 for r in scored if r.get("drew") is True)
    wr = (w + 0.5 * d) / n
    if 0.0 < wr < 1.0:
        elo = 400.0 * math.log10(wr / (1.0 - wr))
        sig_u = elo_sigma_unpaired(wr, n)
        sig_p = sig_u * PAIRING_FACTOR
    else:
        elo, sig_u, sig_p = (math.copysign(800.0, wr - 0.5),
                             float("nan"), float("nan"))
    return {"n": n, "W": w, "D": d, "L": n - w - d, "winrate": wr, "elo": elo,
            "elo_sig_1sigma_paired": sig_p,
            "elo_sig_1sigma_unpaired": sig_u,
            "elo_footing": "deck-paired",
            "elo_pairing_factor": PAIRING_FACTOR,
            "avg_diff": math.fsum(float(r["diff"]) for r in scored) / n}


def recon_close(a, b) -> bool:
    """`RECON` tolerance: rel 1e-6 / abs 1e-9. `None` closes only to `None` — an
    absent field must witness ABSENT, not merely small."""
    if a is None or b is None:
        return a is None and b is None
    try:
        af, bf = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if math.isnan(af) and math.isnan(bf):
        return True
    return abs(af - bf) <= max(RECON_ATOL, RECON_RTOL * max(abs(af), abs(bf)))


def se_model(n_decks: int) -> float:
    """`SIGMA_D_MODEL / sqrt(n)`. 400 decks -> 0.6905. ⛔ POWER ARITHMETIC ONLY —
    never a denominator in a branch test."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    """Print realized vs modelled SE and FLAG a ratio outside `SE_ANOMALY_BAND`.
    ⛔ Reported, NEVER a branch input."""
    modelled = se_model(n_decks)
    if realized_se is None or modelled <= 0:
        return {"realized": realized_se, "modelled": modelled, "ratio": None,
                "band": list(SE_ANOMALY_BAND), "flagged": True,
                "note": "SE unavailable — ABSENT is FLAGGED, never silently OK"}
    ratio = realized_se / modelled
    lo, hi = SE_ANOMALY_BAND
    return {"realized": realized_se, "modelled": modelled, "ratio": ratio,
            "band": list(SE_ANOMALY_BAND), "flagged": not (lo <= ratio <= hi),
            "direction": ("TIGHTER than modelled" if ratio < lo else
                          "WIDER than modelled (the CONCERNING direction)"
                          if ratio > hi else "inside the band"),
            "note": "DISPERSION ANOMALY — reported, never a branch input"}


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# =========================================================================== #
# 5. ⭐⭐ THE READ DISTRIBUTION — WHAT THE BAR COSTS, BEFORE GAME 1            #
# =========================================================================== #

def read_distribution(delta: float, se: float | None = None) -> dict:
    """⭐⭐ **THE HOUSE RULE'S OWN DEMAND, EVALUATED IN CODE.**

    *"Write the prereg bar from what effect would change the decision, size `n`
    to resolve THAT, and if the honest answer is 'we can only afford the
    bounding direction', SAY SO in the READ_RULE including the null's expected
    read distribution."* (owner ruling 2026-08-30, `CLAUDE.md`.)

    So the distribution is COMPUTED, not asserted, and `READ_RULE.md` §8 prints
    it at `delta = 0`, `delta = BAR_EFFECT`, and `delta =` the incumbent's
    realized `+2.951`.

    Branch probabilities at a true effect `delta` and modelled `se`:

        R-ADOPT-CANDIDATE  M - 2se >= BAR   <=>  M >= BAR + 2se
        R-BOUNDED          M + 2se <  BAR   <=>  M <  BAR - 2se
        R-NEGATIVE         M <= 0 AND z <= -2  <=>  M <= -2se   (a SUBSET of
                                                    R-BOUNDED, checked first)
        R-UNRESOLVED       the remainder
    """
    if se is None:
        se = se_model(400)
    if se <= 0:
        return {"error": "se must be positive"}
    p_adopt = 1.0 - _phi((BAR_EFFECT + 2.0 * se - delta) / se)
    p_bounded_all = _phi((BAR_EFFECT - 2.0 * se - delta) / se)
    p_negative = _phi((-2.0 * se - delta) / se)
    p_bounded = max(0.0, p_bounded_all - p_negative)
    p_unres = max(0.0, 1.0 - p_adopt - p_bounded_all)
    return {"delta": delta, "se": se, "bar": BAR_EFFECT,
            "R-ADOPT-CANDIDATE": p_adopt, "R-BOUNDED": p_bounded,
            "R-NEGATIVE": p_negative, "R-UNRESOLVED": p_unres,
            "P(this rung is bounded below the bar)": p_bounded_all,
            "P(LADDER-DEAD | all four rungs at this delta)": p_bounded_all ** 4}


def n_decks_for_ladder_dead(p_target: float = 0.80) -> int:
    """⛔⛔ **THE NUMBER THE HOUSE RULE ASKS FOR AND THIS ROUND CANNOT AFFORD.**

    How many decks per rung would make `LADDER-DEAD` (all four rungs bounded)
    fire with probability `p_target` under a TRUE GLOBAL NULL? Solve
    `Phi((BAR - 2se)/se)^4 = p_target` for `se`, then `n = (sigma_D/se)^2`.

    ⭐ At `p_target = 0.80` this is ~1,100 decks per rung — nearly 3x the funded
    400 — and `READ_RULE.md` §8 states it plainly rather than letting a
    disappointed reader discover it after the fact."""
    root = p_target ** 0.25
    # invert Phi by bisection: find x with Phi(x) = root, then se = BAR/(x+2)
    lo, hi = -8.0, 8.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _phi(mid) < root:
            lo = mid
        else:
            hi = mid
    x = (lo + hi) / 2.0
    se = BAR_EFFECT / (x + 2.0)
    return int(math.ceil((SIGMA_D_MODEL / se) ** 2))


def n_decks_for_adopt_power(delta: float, p_target: float = 0.80) -> int:
    """The mirror image: how many decks per rung to fire `R-ADOPT-CANDIDATE`
    with probability `p_target` at a TRUE effect `delta`? Solve
    `delta - (BAR + 2se) = z_p * se`."""
    lo, hi = -8.0, 8.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _phi(mid) < p_target:
            lo = mid
        else:
            hi = mid
    z_p = (lo + hi) / 2.0
    denom = z_p + 2.0
    if delta <= BAR_EFFECT or denom <= 0:
        return -1                          # unreachable at any n
    se = (delta - BAR_EFFECT) / denom
    return int(math.ceil((SIGMA_D_MODEL / se) ** 2))


def power_at(delta: float, se: float) -> float:
    """P(the rung fires `R-ADOPT-CANDIDATE`) at a true effect `delta`."""
    if se is None or se <= 0:
        return float("nan")
    return read_distribution(delta, se)["R-ADOPT-CANDIDATE"]


# =========================================================================== #
# 6. THE BRANCH LADDER — `READ_RULE.md` §5, pre-registered and EXHAUSTIVE      #
# =========================================================================== #

BRANCHES = ("U-VOID-INSTRUMENT", "R-NEGATIVE", "R-ADOPT-CANDIDATE",
            "R-BOUNDED", "R-UNRESOLVED")
ROUND_VERDICTS = ("LADDER-VOID", "LADDER-LIVE", "LADDER-DEAD",
                  "LADDER-UNRESOLVED")


def branch_for_cell(M, se, z, *, gates_ok: bool) -> str:
    """The §5 ladder, IN ORDER. First match wins. Adjudicated PER RUNG on that
    rung's OWN realized SE, AGAINST ZERO.

    ⛔ Exclusive and exhaustive BY CONSTRUCTION, and ORDERED rather than
    disjoint: `R-NEGATIVE` requires `M <= 0 ∧ z <= -2`, which forces
    `UB95 = M + 2SE <= 0 < BAR_EFFECT`, so it would ALSO satisfy `R-BOUNDED` —
    which is exactly why it is checked first. `R-ADOPT-CANDIDATE` and
    `R-BOUNDED` cannot both hold, because `LB95 <= UB95`.
    """
    if not gates_ok:
        return "U-VOID-INSTRUMENT"
    if M is None or se is None or z is None:
        return "U-VOID-INSTRUMENT"
    lb95 = M - 2.0 * se
    ub95 = M + 2.0 * se
    if M <= 0.0 and z <= -BRANCH_Z:
        return "R-NEGATIVE"
    if lb95 >= BAR_EFFECT:
        return "R-ADOPT-CANDIDATE"
    if ub95 < BAR_EFFECT:
        return "R-BOUNDED"
    return "R-UNRESOLVED"


def round_verdict(branches: Mapping[str, str], *, round_gates_ok: bool,
                  expected_cells: Sequence[str] | None = None) -> dict:
    """⭐⭐ **THE ROUND-LEVEL VERDICT — NEW IN THIS ROUND, AND PRE-REGISTERED.**

    The parent had three independent questions and no round verdict. A LADDER is
    different: the funded decision is *"is there a dose worth taking through the
    adoption chain, or does the incumbent stand?"*, and that is a statement about
    ALL FOUR rungs together.

      `LADDER-VOID`        any round gate FAILED, or a rung is
                           `U-VOID-INSTRUMENT`, or a frozen rung is ABSENT.
                           ⛔ A voided rung is NOT a bound, so `LADDER-DEAD`
                           cannot be declared over it. ⚠️ The surviving rungs'
                           OWN readings still stand — they are separate
                           questions on separate bands — but the ROUND
                           discharges nothing.
      `LADDER-LIVE`        at least one rung reads `R-ADOPT-CANDIDATE`.
      `LADDER-DEAD`        EVERY rung has `UB95 < BAR_EFFECT` (i.e. every rung
                           reads `R-BOUNDED` or `R-NEGATIVE`).
      `LADDER-UNRESOLVED`  anything else — i.e. at least one rung read
                           `R-UNRESOLVED` and none adopted. ⛔ NOT a null.

    ⛔ `LADDER-LIVE` and `LADDER-DEAD` are mutually exclusive: an adopting rung
    has `UB95 >= LB95 >= BAR_EFFECT`.
    """
    want = list(expected_cells or [c.name for c in CELLS])
    missing = [n for n in want if n not in branches]
    voided = [n for n, b in branches.items() if b == "U-VOID-INSTRUMENT"]
    adopted = [n for n, b in branches.items() if b == "R-ADOPT-CANDIDATE"]
    bounded = [n for n, b in branches.items()
               if b in ("R-BOUNDED", "R-NEGATIVE")]
    unresolved = [n for n, b in branches.items() if b == "R-UNRESOLVED"]

    if not round_gates_ok or voided or missing:
        v = "LADDER-VOID"
        why = ("⛔ THE ROUND DISCHARGES NOTHING. " + "; ".join(filter(None, [
            "a ROUND-LEVEL gate FAILED (G-WHEEL-SAME / G-REV / G-BLIND) — a fail "
            "on any of those VOIDS EVERY CELL" if not round_gates_ok else "",
            f"rung(s) {voided} are U-VOID-INSTRUMENT" if voided else "",
            f"frozen rung(s) {missing} produced NO ARCHIVE — ABSENT is FAIL"
            if missing else "",
        ])) + ". ⛔ A voided or absent rung is NOT a bound, so LADDER-DEAD may "
              "not be declared. ⚠️ The surviving rungs' own per-rung readings "
              "STAND (separate questions on separate bands) and are printed; "
              "the ROUND verdict does not.")
    elif adopted:
        v = "LADDER-LIVE"
        why = (f"⭐⭐ rung(s) {adopted} read R-ADOPT-CANDIDATE (LB95 >= "
               f"{BAR_EFFECT} pts/deck). ⚠️ READ_RULE §5.1's riders travel with "
               "every citation, and §5.3's multiplicity note binds: a LONE "
               "firing rung beside three nulls is read as "
               "feedback_results_table_source_of_truth's NOISE SIGNATURE, not "
               "as a peak.")
    elif len(bounded) == len(want):
        v = "LADDER-DEAD"
        why = (f"⭐ EVERY rung is bounded below +{BAR_EFFECT} pts/deck at 95% "
               f"({bounded}). " + LADDER_DEAD_CONSEQUENCE)
    else:
        v = "LADDER-UNRESOLVED"
        why = (f"⛔ rung(s) {unresolved} read R-UNRESOLVED and none adopted. "
               "⛔⛔ THIS IS NOT A NULL AND NOT A BOUND "
               "(feedback_noisy_plateau_not_a_conclusion). The round bought no "
               "ladder verdict. ⚠️ READ_RULE §8 pre-registers this as the MOST "
               "LIKELY outcome under a true global null at n=400 decks/rung "
               "(~90%), and §8.2 pre-registers its price.")
    return {"verdict": v, "adopted": adopted, "bounded": bounded,
            "unresolved": unresolved, "voided": voided, "missing": missing,
            "bar": BAR_EFFECT, "why": why}


def branch_grid(step: float = 0.05, se_values=(0.3, 0.5, 0.691, 0.9, 1.4)) -> dict:
    """⭐ `READ_RULE.md` §5's own demand: sweep a dense `(M, SE)` grid and prove
    EXACTLY ONE branch fires at every point, and that every branch is REACHABLE
    (§4.1's "no branch is unreachable by construction")."""
    seen: dict[str, int] = {}
    m = -8.0
    pts = 0
    while m <= 8.0 + 1e-9:
        for se in se_values:
            z = m / se
            b = branch_for_cell(m, se, z, gates_ok=True)
            seen[b] = seen.get(b, 0) + 1
            pts += 1
        m += step
    return {"points": pts, "histogram": seen, "reachable": sorted(seen),
            "all_reachable": set(seen) >= {"R-NEGATIVE", "R-ADOPT-CANDIDATE",
                                           "R-BOUNDED", "R-UNRESOLVED"}}


RIDERS_ALWAYS = (
    "⛔⛔ THE 0.2 AND 0.4 CONTEXT ROWS ARE NEVER POOLED WITH A RUNG OF THIS "
    "ROUND. They are on bands 155e9 / 156e9; every rung here is on its own "
    "fresh band, and CL-068 measured 1.8-2.2x OVER-DISPERSION on merely "
    "cross-band contrasts, in BOTH the elo and the deck-paired-margin "
    "statistics. There is no arithmetic that combines them.",
    "⛔ NO CROSS-RUNG CONTRAST IS A BRANCH INPUT. The four rungs sit on four "
    "bands, so every rung-vs-rung difference is cross-band and carries CL-068's "
    "over-dispersion in full. The dose-response shape is printed as a NAMED "
    "COMPANION and is a DIRECTION, never a curve and never an optimum.",
    "⛔ FOUR RUNGS ARE FOUR COMPARISONS. The multiplicity is DISCLOSED, not "
    "corrected: the bars are pre-registered and each rung is its own question. "
    "⭐ At the LB95 bar the family-wise FALSE-ADOPT rate under a global null is "
    "~0.006% (4 x 0.0015%) — the adoption bar cannot fire on noise. That "
    "conservatism has a PRICE and READ_RULE §8 states it: LADDER-DEAD fires "
    "only ~10% of the time under a true global null.",
    "⛔ governance/PRODUCTION.yaml is UNTOUCHED on every branch. No branch "
    "licenses a production change of any kind; the adoption chain "
    "(screen_lib.ADOPTION_CHAIN) has three more legs after this one and each is "
    "its own prereg, its own band and its own owner funding.",
    "⛔ THE TIE ARBITER IS OFF ON BOTH SIDES OF EVERY RUNG. PRODUCTION.yaml has "
    "carried B=64 since 2026-08-20, so every reading here is about the "
    "ARBITER-FREE champion and its transfer to the deployed one is an "
    "ASSUMPTION, not a measurement.",
    "⚠️ elo may never be quoted bare, and in THIS round it is not even a bar: "
    "the adoption bar is +1.5 pts/deck on the deck-paired margin and there is "
    "no exchange rate into elo that this round measures. The elo is reported "
    "beside the margin with its own paired CI, and a disagreement between the "
    "two is DISCLOSED rather than arbitrated.",
)
RIDERS_R_ADOPT = (
    "⭐⭐ R-ADOPT-CANDIDATE is a claim about THIS DOSE, on THIS BAND, on the "
    "CLASSICAL champion at k16x1376, WITH THE ARBITER OFF. It licenses step 2 "
    "of screen_lib.ADOPTION_CHAIN — a production H2H with the arbiter ARMED, on "
    "a fresh band — and NOTHING ELSE.",
    "⛔ IT DOES NOT LICENSE A PRODUCTION CHANGE. One cell on a fresh band is one "
    "cell; feedback_results_table_source_of_truth requires a confirm before "
    "promotion, and this band retires decision_influenced=yes the moment the "
    "read-out lands.",
    "⛔ IT DOES NOT LOCATE AN OPTIMUM. Four rungs on four bands are four "
    "independent within-band readings, not a curve. feedback_bracket_hyperparams "
    "requires >=3 WELL-SPREAD points on a COMPARABLE footing; cross-band "
    "over-dispersion denies this ladder that footing, which is a disclosed "
    "limitation of the one-band-per-cell shape and not a defect of it.",
    "⚠️ IT SAYS NOTHING ABOUT THE INCUMBENT 0.2. A rung firing here does not "
    "displace 0.2 and does not confirm it — the two are on different bands.",
)
RIDERS_R_BOUNDED = (
    "⚠️ R-BOUNDED BOUNDS; IT DOES NOT ZERO. The reading is 'below +1.5 "
    "pts/deck at 95%', never 'this dose is worthless'. In particular a rung can "
    "read R-BOUNDED while carrying a POSITIVE point estimate.",
    "⭐ It DOES discharge THIS RUNG of the funded decision: this dose is not "
    "worth taking through the adoption chain on this evidence.",
    "⚠️ It is a bound at THIS DOSE, THIS BUDGET, and with the ARBITER OFF.",
)
RIDERS_R_NEGATIVE = (
    "⭐ R-NEGATIVE is fully pre-registered and mechanistically plausible: a "
    "pessimistic FPU narrowing a search that is already well-tuned is a real "
    "harm, and the M3 curve's roll-off is consistent with it.",
    "⛔ It still licenses no production change — the champion already runs "
    "fpu=None, so there is nothing to turn off.",
    "⚠️ At a SMALL dose (0.05) a negative reading is the more surprising result "
    "and should be read with the multiplicity note in hand.",
)
RIDERS_R_UNRESOLVED = (
    "⛔⛔ R-UNRESOLVED IS NOT A NULL AND NOT A BOUND. "
    "feedback_noisy_plateau_not_a_conclusion binds: this rung did not resolve "
    "its own bar in either direction.",
    "⛔ IT DOES NOT DISCHARGE ANYTHING, and a round containing one cannot read "
    "LADDER-DEAD. READ_RULE §8 pre-registers this as the LIKELIEST single-rung "
    "outcome under a true null at n=400 decks (~43%), and the likeliest ROUND "
    "outcome under a true global null (~90% chance at least one rung lands "
    "here).",
    "⛔ AN UNRESOLVED RUNG MAY NOT BE EXTENDED, TOPPED UP OR RE-READ AT LARGER "
    "n ON ITS OWN BAND. That is the rodv3 failure mode (n bought after seeing "
    "the sign), and CL-068 means the extension could not be pooled with the "
    "original anyway. A re-run is a NEW round: new pair, new band, new owner "
    "funding.",
)


# =========================================================================== #
# 7. THE ROUND-SPECIFIC GATES                                                  #
# =========================================================================== #

def decks_gate(spec: CellSpec, records: Sequence[Mapping],
               all_specs: Sequence[CellSpec] = CELLS) -> dict:
    """⛔⛔ `G-DECKS` — **WRITTEN TO THE PROSE. THIS IS THE `FPU-A1` FIX.**

    The parent round's clause demanded `n_common == 400` EXACTLY and voided a
    healthy cell when one seeded game raised a deterministic
    `WindowTruncationError` (1/800 = 0.125% — an order of magnitude below the
    2% void bar its own prose set). The amendment had to be written with the
    statistics already visible. ⭐ Here the prose IS the implementation:

      (a) ⛔ HARD FAIL — every realized seed lies inside **this cell's own**
          range. An out-of-range seed is a cell playing decks it did not claim.
      (b) ⚠️ REPORTED, then bar-checked — decks played at ONE SEAT ONLY. These
          ARE the failures (a failed seating drops its deck from the paired
          statistic; the emitter states EXCLUSIONS, not zeros). Their rate is
          voiding **only at or above `FAILURE_RATE_VOID`**; below it they are
          REPORTED, never silently absorbed (the `b32v64` 0.100% rust-panic
          precedent).
          ⭐⭐ **THE DENOMINATOR IS GAMES, NOT DECKS**, and that is deliberate:
          one deck played at one seat only IS exactly one failed GAME, so this
          rate and `G-N`'s `n_failed / n_games` are THE SAME QUANTITY read off
          two different documents (raw records vs `summary.json`) — which is the
          point of having both. ⛔ A decks denominator here would make the two
          gates disagree by a factor of two at the same archive, and the pair
          would void on one gate while reporting on the other. (Caught in build,
          before game 1: the first draft did exactly that.)
      (c) ⛔ HARD FAIL — `n_common < N_COMMON_FLOOR_FRACTION * n_decks`. This is
          a FRACTION, never an equality. ⚠️ It is a BACKSTOP: at 400 decks the
          80% floor allows 80 lost decks while the 2% bar in (b) voids at 8, so
          (b) is the operative bar and (c) catches a shape (b) cannot see.
      (d) ⛔ HARD FAIL — this cell's range intersects ANY other cell's. Four
          bands ⇒ disjointness is assertable, and a copied overlap clause from
          phasegate would have skipped the check entirely.

    ⭐ A seeded game CANNOT be re-rolled, so a permanently-failing deck is a
    fact about the deck set and not about the knob. That is why the design
    absorbs it below the bar instead of voiding — and why it is REPORTED loudly.
    """
    by_deck = _by_deck(records)
    seeds = sorted(by_deck)
    lo, hi = spec.seed_start, spec.seed_end
    out_of_range = [s for s in seeds if not (lo <= s <= hi)]
    half = sorted(s for s, v in by_deck.items() if not (0 in v and 1 in v))
    n_common = len(per_deck_margins(records))
    clashes = [c.name for c in all_specs
               if c.name != spec.name
               and not (c.seed_end < lo or c.seed_start > hi)]
    # ⭐ GAMES denominator — one one-seat-only deck is one failed GAME, the same
    # quantity `G-N` reads out of `summary.n_failed` (see the docstring).
    half_rate = len(half) / float(max(1, spec.n_games))
    floor = N_COMMON_FLOOR_FRACTION * spec.n_decks

    hard = []
    notes = []
    if out_of_range:
        hard.append(f"{len(out_of_range)} seed(s) outside [{lo},{hi}] "
                    f"(first: {out_of_range[:5]})")
    if clashes:
        hard.append(f"this cell's band range intersects {clashes}")
    if half:
        notes.append(
            f"⚠️ {len(half)} deck(s) played at ONE SEAT ONLY = {len(half)} "
            f"failed game(s) ({half_rate:.4%} of {spec.n_games}) — REPORTED, "
            f"never silently absorbed (the b32v64 0.100% rust-panic precedent). "
            f"Seeds: {half[:10]}. They are DROPPED from the paired statistic "
            "(EXCLUSIONS, not zeros); a seeded game cannot be re-rolled.")
        if half_rate >= FAILURE_RATE_VOID:
            hard.append(f"one-seat-only rate {half_rate:.4%} of {spec.n_games} "
                        f"games >= {FAILURE_RATE_VOID:.0%} — AT OR ABOVE the "
                        "bar, the cell VOIDS")
    if n_common < floor:
        hard.append(f"n_common {n_common} < {N_COMMON_FLOOR_FRACTION:.0%} of "
                    f"{spec.n_decks} ({floor:.0f})")

    ok = not hard
    return gate(
        "G-DECKS", ok,
        {"range": [lo, hi], "n_seeds": len(seeds), "n_common": n_common,
         "frozen_n_decks": spec.n_decks, "n_common_floor": floor,
         "out_of_range": out_of_range[:20],
         "half_played_decks": half[:20], "n_half_played": len(half),
         "half_played_rate_of_games": half_rate,
         "half_played_rate_denominator": spec.n_games,
         "failure_rate_void_bar": FAILURE_RATE_VOID,
         "range_clashes": clashes, "notes": notes,
         "all_cell_ranges": [[c.seed_start, c.seed_end, c.name]
                             for c in all_specs]},
        "raw seed*_a*.json",
        ((" ".join(notes) + " " if notes else "")
         + "⭐ every realized seed is inside this cell's own range, the "
           "one-seat-only rate is BELOW the 2%-of-games void bar, n_common "
           "clears the 80% floor, and this cell's band does not intersect any "
           "other's"
         if ok else
         "⛔ G-DECKS FAILED: " + "; ".join(hard)
         + ((" ⚠️ also reported: " + " ".join(notes)) if notes else "")))


def n_gate(spec: CellSpec, n, n_failed, n_common, addr_n, addr_nf) -> dict:
    """⛔⛔ `G-N` — **WRITTEN TO THE PROSE. THE OTHER HALF OF THE `FPU-A1` FIX.**

    The parent's condition column read `n == 800, n_failed == 0`. Its NOTES
    column — the reasoned rule, carrying the `b32v64` precedent — read *"a
    failure rate strictly below 2% is REPORTED, never silently absorbed; at or
    above it the cell voids."* The two disagreed and the strict one won, voiding
    a healthy cell. Here:

      ⛔ HARD FAIL  `n` or `n_failed` ABSENT (ABSENT is FAIL).
      ⛔ HARD FAIL  the ACCOUNTING IDENTITY `n + n_failed != n_games`. A cell
                    that lost games WITHOUT recording them is a cell whose
                    denominator nobody knows — that is a different and worse
                    defect than a recorded failure, and it is NOT absorbed.
      ⛔ HARD FAIL  `n_failed / n_games >= FAILURE_RATE_VOID`.
      ⚠️ REPORTED   `0 < n_failed / n_games < FAILURE_RATE_VOID`, with the
                    failure classes if the emitter gave them.
      ⛔ HARD FAIL  `n_common < N_COMMON_FLOOR_FRACTION * n_decks`.
    """
    hard, notes = [], []
    if n is MISSING or n is None:
        hard.append("summary.n ABSENT — ABSENT is FAIL")
    if n_failed is MISSING or n_failed is None:
        hard.append("n_failed ABSENT — ABSENT is FAIL")
    rate = None
    if not hard:
        n_i, nf_i = int(n), int(n_failed)
        if n_i + nf_i != spec.n_games:
            hard.append(f"⛔ ACCOUNTING: n {n_i} + n_failed {nf_i} = "
                        f"{n_i + nf_i} != the frozen {spec.n_games} games. "
                        "Games went missing WITHOUT being recorded as failures; "
                        "the denominator is unknown and this is NOT the "
                        "sub-2% case the bar absorbs.")
        rate = nf_i / float(spec.n_games)
        if nf_i > 0:
            notes.append(
                f"⚠️ n_failed = {nf_i} ({rate:.4%} of {spec.n_games}) — "
                "REPORTED, never silently absorbed (the b32v64 0.100% "
                "rust-panic precedent). ⭐ STRICTLY BELOW the 2% bar this is a "
                "READ, not a void — the FPU-A1 lesson.")
        if rate >= FAILURE_RATE_VOID:
            hard.append(f"failure rate {rate:.4%} >= {FAILURE_RATE_VOID:.0%} — "
                        "AT OR ABOVE the bar, the cell VOIDS")
    floor = N_COMMON_FLOOR_FRACTION * spec.n_decks
    if n_common < floor:
        hard.append(f"n_common {n_common} < {N_COMMON_FLOOR_FRACTION:.0%} of "
                    f"{spec.n_decks} ({floor:.0f})")
    return gate("G-N", not hard,
                {"n": None if n is MISSING else n,
                 "frozen_n_games": spec.n_games,
                 "n_failed": None if n_failed is MISSING else n_failed,
                 "failure_rate": rate, "failure_rate_void_bar": FAILURE_RATE_VOID,
                 "n_common": n_common, "n_common_floor": floor,
                 "n_common_floor_fraction": N_COMMON_FLOOR_FRACTION,
                 "notes": notes, "addresses": [addr_n, addr_nf]},
                "summary.json",
                ((" ".join(notes) + " " if notes else "")
                 + "⭐ n accounts for every frozen game, the failure rate is "
                   "below the 2% void bar, and n_common clears the 80% floor"
                 if not hard else
                 "⛔ G-N FAILED: " + "; ".join(hard)
                 + ((" ⚠️ also reported: " + " ".join(notes)) if notes else "")))


def leaf_gate(cand_hash, opp_hash, cand_curve) -> dict:
    """`G-LEAF` — ⭐ BOTH SIDES EQUAL, and equal to `a36d2e15a3b3d71d`.

    `fpu_reduction` is read on the PUCT descent and is NOT a leaf term, so it
    moves NO leaf hash — which is precisely why a moved-hash check can never
    prove this surface LIVE, and why `G-FPU` / `G-TWOSIDED` / the golden gate
    exist."""
    same = (cand_hash is not None and cand_hash == opp_hash)
    right = cand_hash == LEAF_HASH
    curve_ok = list(cand_curve or []) == LEAF_CURVE125
    ok = same and right and curve_ok
    return gate("G-LEAF", ok,
                {"cand_leaf_hash": cand_hash, "opp_leaf_hash": opp_hash,
                 "expected": LEAF_HASH, "cand_curve": cand_curve},
                "manifest:config.{cand,opp}_leaf_hash",
                ("both sides carry the SAME leaf a36d2e15a3b3d71d (curve125) — "
                 "fpu_reduction is not a leaf term" if ok else
                 "⛔ G-LEAF FAILED: " + "; ".join(filter(None, [
                     "the two sides' leaf hashes DIFFER (misconfigured cell — "
                     "the knob moves no leaf hash)" if not same else "",
                     f"leaf hash is not {LEAF_HASH}" if not right else "",
                     "v29_meeple_curve is not curve125" if not curve_ok else "",
                 ]))))


#: `G-SINGLEVAR`'s alias table. ⚠️ PER CELL: the knob the cell OWNS is asserted
#: DIFFERENT, every other alias is asserted EQUAL. In THIS round every cell owns
#: `fpu_reduction`, so `c_puct` / `tau_p` / the budget aliases must all be EQUAL
#: across the two sides on EVERY cell.
SINGLEVAR_ALIASES = ("k_dets", "sims_per_det", "total_sims", "c_puct", "tau_p",
                     "value_norm", "leaf_quantize", "final_select",
                     "fpu_reduction")


def singlevar_gate(spec: CellSpec, rows: Mapping[str, Mapping]) -> dict:
    """`G-SINGLEVAR` — the cell's OWN alias must DIFFER across the two sides and
    equal the frozen value on the candidate; every OTHER alias must be EQUAL.

    ⚠️ Carried from the parent's REWRITE, not from phasegate: the single
    variable here IS a search knob, so a clause demanding every knob be equal
    would void every healthy cell. ⚠️ The opponent's knobs live one level down
    under `champ_cfg` — a gate written from the design rather than from a real
    manifest voids every healthy cell for the other reason.

    `rows` is `{alias: {"champion": v, "opponent": v, "addresses": [...]}}`.
    """
    owned = spec.knob
    bad, notes = [], []
    for alias in SINGLEVAR_ALIASES:
        r = rows.get(alias) or {}
        cv, ov = r.get("champion"), r.get("opponent")
        present = ("champion" in r and "opponent" in r
                   and not r.get("champion_absent") and not r.get("opponent_absent"))
        if not present:
            bad.append(f"{alias} ABSENT on one side")
            continue
        if alias == owned:
            if repr(cv) == repr(ov):
                bad.append(f"⛔ {alias}: the cell's OWN knob is IDENTICAL on both "
                           f"sides ({cv!r}) — this cell is champion-vs-champion")
            elif cv is None or float(cv) != float(spec.value):
                bad.append(f"{alias}: candidate {cv!r} != this cell's frozen "
                           f"{spec.value!r}")
            else:
                notes.append(f"⭐ {alias}: candidate {cv!r} vs opponent {ov!r} — "
                             "the SINGLE VARIABLE, differing as frozen")
        elif repr(cv) != repr(ov):
            bad.append(f"{alias}: champion {cv!r} vs opponent {ov!r} — a SECOND "
                       "variable; this cell is not single-variable")
    return gate("G-SINGLEVAR", not bad,
                {"owned_alias": owned, "frozen_value": spec.value,
                 "rows": dict(rows), "notes": notes},
                "manifest:config.champion.* vs config.opponent.champ_cfg.*",
                ("; ".join(notes) + " — every OTHER alias is identical across the "
                 "two sides" if not bad else
                 "⛔ G-SINGLEVAR FAILED: " + "; ".join(bad)))


def knob_gate(spec: CellSpec, requested_fpu, requested_c, fpu_addr, c_addr,
              shared_c) -> dict:
    """⭐⭐ `G-FPU` — THE INVERTED-LIVENESS GATE, on the REQUEST side.

    ⛔⛔ **THIS IS THE GATE THE WHOLE FAMILY EXISTS BEHIND.** Until 2026-08-29
    `rust_agent.search_config_rs` passed a HARD-CODED `None` into
    `SearchConfigRs`'s `fpu_reduction` slot: a cell run over that defect plays
    champion-vs-champion, moves no leaf hash, produces a perfectly healthy
    winrate inside `G-SAT`'s rail, and reads as a clean, credible null. Every
    other gate in this file would have passed it.

    ⚠️ `MISSING` IS NOT `None`. `config.cand_search.fpu_reduction = null` is a
    POSITIVE statement ("the champion's legacy optimistic q=0"); an ABSENT key
    means a harness that never resolved the knob, and ABSENT is FAIL.

    ⭐ **AND `c_puct` IS ASSERTED ABSENT-AS-NULL ON EVERY CELL.** No rung of this
    round varies `c_puct`; a stray `--cand-c-puct` would be a second variable.
    `G-SINGLEVAR` would also catch it — two witnesses, not one, because the
    request side and the resolved side are different bugs.
    """
    want_fpu, want_c = spec.cand_fpu, spec.cand_c_puct
    bad = []
    if requested_fpu is MISSING:
        bad.append("config.cand_search.fpu_reduction ABSENT — ABSENT is FAIL. A "
                   "harness predating the fpu plumbing cannot be adjudicated: "
                   "its candidate was fpu-BLIND by construction.")
    elif (requested_fpu is None) != (want_fpu is None) or (
            want_fpu is not None and float(requested_fpu) != float(want_fpu)):
        bad.append(f"fpu_reduction is {requested_fpu!r}, this rung is frozen at "
                   f"{want_fpu!r}")
    if requested_c is MISSING:
        bad.append("config.cand_search.c_puct ABSENT — ABSENT is FAIL")
    elif (requested_c is None) != (want_c is None) or (
            want_c is not None and float(requested_c) != float(want_c)):
        bad.append(f"c_puct override is {requested_c!r}, this rung is frozen at "
                   f"{want_c!r} (⛔ NO rung of this round varies c_puct)")
    return gate("G-FPU", not bad,
                {"requested_fpu_reduction": (None if requested_fpu is MISSING
                                             else requested_fpu),
                 "fpu_absent": requested_fpu is MISSING,
                 "requested_c_puct_override": (None if requested_c is MISSING
                                               else requested_c),
                 "c_puct_absent": requested_c is MISSING,
                 "shared_c_puct": (None if shared_c is MISSING else shared_c),
                 "frozen": {"fpu_reduction": want_fpu, "c_puct": want_c},
                 "addresses": {"fpu": fpu_addr, "c_puct": c_addr}},
                fpu_addr or c_addr,
                (f"the REQUEST matches this rung's frozen dose "
                 f"(fpu={want_fpu!r}) and carries NO c_puct override" if not bad
                 else "⛔ G-FPU FAILED: " + "; ".join(bad)))


def twosided_gate(spec: CellSpec, rows: Mapping[str, Mapping]) -> dict:
    """⭐⭐ `G-TWOSIDED` — THE SECOND, INDEPENDENT WITNESS.

    `G-FPU` proves the knob was REQUESTED. This proves it BOUND, and bound ON
    THE CANDIDATE ONLY — read off the two sides' RESOLVED `HeuristicPriorConfig`
    blocks rather than off the flag that asked for it.

    ⚠️ It is weaker than a play-derived witness (a PUCT constant has no fire
    counter, unlike the arbiter's `G-PHI` or the S1 `jr_expansions` census). The
    play-derived evidence in this family is the GOLDEN GATE, and `DESIGN.md` §9
    says so rather than overclaiming this gate.

    ⛔ ABSENT is FAIL on BOTH sides. `config.opponent.champ_cfg.fpu_reduction` is
    emitted as an explicit `null` precisely so this gate has an address to read
    instead of an exception to make.
    """
    bad, seen = [], {}
    for alias, want_cand in (("fpu_reduction", spec.cand_fpu),
                             ("c_puct", spec.cand_c_puct)):
        r = rows.get(alias) or {}
        cv, ov = r.get("champion"), r.get("opponent")
        seen[alias] = {"candidate": cv, "opponent": ov}
        if r.get("champion_absent"):
            bad.append(f"config.champion.{alias} ABSENT — ABSENT is FAIL")
            continue
        if r.get("opponent_absent"):
            bad.append(f"config.opponent.champ_cfg.{alias} ABSENT — ABSENT is "
                       "FAIL (the opponent must state its value POSITIVELY, "
                       "which is why the harness emits an explicit null)")
            continue
        if alias == "fpu_reduction":
            if ov is not None:
                bad.append(f"⛔ the OPPONENT carries fpu_reduction={ov!r} — it is "
                           "not the unmodified champion")
            if want_cand is None and cv is not None:
                bad.append(f"the candidate carries fpu_reduction={cv!r} on a rung "
                           "frozen without one")
            if want_cand is not None and (cv is None
                                          or float(cv) != float(want_cand)):
                bad.append(f"⛔⛔ the candidate's RESOLVED fpu_reduction is {cv!r}, "
                           f"not the frozen {want_cand!r} — the knob did NOT bind. "
                           "This is exactly the hard-coded-None defect the family "
                           "was funded to close, and a cell over it is "
                           "champion-vs-champion.")
        else:                                    # c_puct — EQUAL on every rung
            if want_cand is None:
                if cv is None or ov is None or float(cv) != float(ov):
                    bad.append(f"c_puct differs across the sides ({cv!r} vs "
                               f"{ov!r}) on a rung that froze no override — a "
                               "SECOND variable, or the `--c-puct` both-sides "
                               "trap in mirror image")
                elif float(cv) != float(CHAMP_C_PUCT):
                    bad.append(f"both sides carry c_puct={cv!r}, not the "
                               f"champion's {CHAMP_C_PUCT} — the opponent of "
                               "every rung IS the champion of record")
            else:
                if cv is None or float(cv) != float(want_cand):
                    bad.append(f"the candidate's RESOLVED c_puct is {cv!r}, not "
                               f"the frozen {want_cand!r}")
    return gate("G-TWOSIDED", not bad, {"resolved": seen, "cell_knob": spec.knob,
                                        "frozen_value": spec.value},
                "manifest:config.champion.* vs config.opponent.champ_cfg.*",
                ("⭐ the dose BOUND on the candidate's resolved config, the "
                 "opponent carries the champion's values, and c_puct is equal "
                 "across the two sides" if not bad else
                 "⛔ G-TWOSIDED FAILED: " + "; ".join(bad)))


def arb_off_gate(cell_manifest: Mapping) -> dict:
    """`G-ARB-OFF` — the tie arbiter is OFF on BOTH sides (single-variable
    discipline). ⚠️ `PRODUCTION.yaml` has carried `B=64` since 2026-08-20, so
    "off" is a DEVIATION FROM THE DEPLOYED CHAMPION and `DESIGN.md` §2.3 owes the
    reason: the arbiter is a stochastic post-search hook whose fires would add
    variance orthogonal to the knob under test, on BOTH sides — and it fires on
    exact ties, which is precisely what a changed visit distribution moves. The
    price is that every reading here is about the arbiter-free champion.

    ⚠️ Scan CONTAINER segments for a stray armed block, but read TERMINAL
    `*.tiearb_enabled` values — a healthy archive emits terminal `false` on both
    sides."""
    armed, containers = [], []

    def walk(node, path):
        if isinstance(node, Mapping):
            for k, v in node.items():
                p = f"{path}.{k}" if path else k
                if isinstance(v, Mapping):
                    if k.endswith("tiearb"):
                        containers.append(p)
                        if v.get("enabled") is True:
                            armed.append(p)
                    walk(v, p)
                elif k == "tiearb_enabled" and v is True:
                    armed.append(p)
    walk(cell_manifest or {}, "")
    ok = not armed and bool(cell_manifest)
    return gate("G-ARB-OFF", ok,
                {"armed": armed, "tiearb_containers": containers},
                "manifest (full walk)",
                ("the tie arbiter is DISABLED on both sides — the rung's dose is "
                 "the only moving part. ⚠️ This DEVIATES from the deployed "
                 "champion (PRODUCTION.yaml carries B=64 since 2026-08-20); the "
                 "price rides on every branch (DESIGN §2.3)." if ok else
                 f"⛔ G-ARB-OFF FAILED: an arbiter is ARMED at {armed} — the "
                 "rung has two moving parts and is not single-variable"))


# =========================================================================== #
# 8. SELF-CHECK — the library's own invariants                                 #
# =========================================================================== #

def sanity_check() -> list[str]:
    """Problems with THIS FILE's own constants and arithmetic. Empty == clean.
    ⛔ Run by `analyze_ladder.py --selftest` AND by `run_cells.sh`'s precondition
    ladder; a non-empty list is a BUILD failure, not a round failure."""
    p: list[str] = []
    # --- the rungs ---------------------------------------------------------
    if len(CELLS) != 4:
        p.append(f"CELLS has {len(CELLS)} entries, the ladder is FOUR rungs")
    if {c.name for c in CELLS} != set(BANDS):
        p.append("CELLS' names do not match BANDS' keys")
    doses = [c.value for c in CELLS]
    if sorted(doses) != [0.05, 0.10, 0.15, 0.30]:
        p.append(f"the frozen doses are {sorted(doses)}, the funded ladder is "
                 "[0.05, 0.1, 0.15, 0.3]")
    if len(set(doses)) != len(doses):
        p.append("two rungs carry the SAME dose")
    for c in CELLS:
        if c.seed_start != BANDS[c.name]:
            p.append(f"{c.name} does not start at its own band {BANDS[c.name]}")
        if c.n_decks != 400 or c.n_games != 800:
            p.append(f"{c.name} is {c.n_decks} decks / {c.n_games} games, "
                     "the funded shape is 400 decks / 800 games")
        if c.knob != "fpu_reduction":
            p.append(f"{c.name} owns {c.knob!r}; EVERY rung of this round owns "
                     "fpu_reduction")
        if c.cand_c_puct is not None:
            p.append(f"{c.name} carries a c_puct override — no rung may")
    # --- the disjointness the round rests on -------------------------------
    rng = sorted((c.seed_start, c.seed_end, c.name) for c in CELLS)
    for a, b in zip(rng, rng[1:]):
        if b[0] <= a[1]:
            p.append(f"cell ranges INTERSECT: {a} and {b}")
    # ⛔ no rung's range may touch the throwaway block the smoke plays
    t_lo, t_hi = THROWAWAY_BASE, THROWAWAY_BASE + THROWAWAY_SPAN - 1
    for c in CELLS:
        if not (c.seed_end < t_lo or c.seed_start > t_hi):
            p.append(f"{c.name}'s range intersects the THROWAWAY block "
                     f"[{t_lo},{t_hi}]")
    # ⛔ and no rung may sit on a band the parent round already spent
    for c in CELLS:
        if c.seed_start in (155_000_000_000, 156_000_000_000, 157_000_000_000,
                            161_000_000_000, 162_000_000_000, 163_000_000_000):
            p.append(f"{c.name} sits on a band that is already claimed or "
                     f"reserved ({c.seed_start})")
    # --- boxes -------------------------------------------------------------
    if {c.role for c in CELLS} != {"local", "laptop"}:
        p.append("the round does not use both boxes")
    # --- the budget --------------------------------------------------------
    if K_DETS * SIMS_PER_DET != TOTAL_SIMS:
        p.append(f"{K_DETS} x {SIMS_PER_DET} != {TOTAL_SIMS}")
    if (K_DETS, SIMS_PER_DET, TOTAL_SIMS) != (16, 1376, 22016):
        p.append("the budget is not the 2026-08-30 promoted champion k16x1376")
    # --- the sizing arithmetic ---------------------------------------------
    if abs(se_model(400) - 0.6905) > 5e-4:
        p.append(f"se_model(400) = {se_model(400):.4f}, DESIGN §3 says 0.6905")
    # --- ⭐⭐ THE BAR IS AN EFFECT SIZE, NOT 2 sigma-hat --------------------
    # ⛔ THE ASSERT THE HOUSE RULE DEMANDS, IN THE INVERSE DIRECTION FROM THE
    # PARENT'S: the parent asserted BAR_M == 2*se_model(400) and had to disclose
    # the coin flip that follows. Here the bar must NOT be that number.
    if abs(BAR_EFFECT - 2 * se_model(400)) < 0.05:
        p.append(f"BAR_EFFECT {BAR_EFFECT} has collapsed onto 2*se_model(400) = "
                 f"{2 * se_model(400):.4f}. ⛔ THE HOUSE RULE (owner 2026-08-30) "
                 "FORBIDS A BAR SET AT 2 sigma-hat OF THE INSTRUMENT: it makes "
                 "the kill branch fire only on a NEGATIVE point estimate.")
    if BAR_EFFECT <= 0:
        p.append("BAR_EFFECT must be positive")
    if BAR_EFFECT < CONTEXT_ROWS[
            "fpu_reduction=0.2 (fpu_resurrection CELL_FPU02, band 155e9)"
            ]["LB95"] - 0.15:
        p.append("BAR_EFFECT is materially EASIER than the incumbent 0.2's own "
                 "realized LB95 (+1.586) — the bar is supposed to ask a new rung "
                 "to be at least as good as what we already hold")
    # --- ⭐ R4's provenance assert, carried ---------------------------------
    elo_2s_paired = 2.0 * elo_sigma_paired(0.5, 800)
    if abs(ELO_RESOLUTION_2SIGMA - elo_2s_paired) > 0.05:
        p.append(f"ELO_RESOLUTION_2SIGMA {ELO_RESOLUTION_2SIGMA} is not the "
                 f"DECK-PAIRED 2-sigma resolution {elo_2s_paired:.4f} at 800 "
                 f"games / 400 decks (the UNPAIRED figure is "
                 f"{2 * elo_sigma_unpaired(0.5, 800):.4f} — that is the mismatch "
                 "R4 fixed)")
    if abs(PAIRING_FACTOR - 0.7071) > 1e-4:
        p.append(f"PAIRING_FACTOR {PAIRING_FACTOR} is not 1/sqrt(2)")
    # ⛔ elo is NEVER a branch input — asserted, not assumed.
    if "elo" in branch_for_cell.__code__.co_varnames:
        p.append("branch_for_cell has taken an elo argument — elo may NEVER be "
                 "a branch input (READ_RULE §1.1)")
    # --- ⭐⭐ THE READ DISTRIBUTION, ASSERTED ------------------------------
    se0 = se_model(400)
    null = read_distribution(0.0, se0)
    if not (0.40 <= null["R-UNRESOLVED"] <= 0.47):
        p.append(f"the true-null R-UNRESOLVED probability is "
                 f"{null['R-UNRESOLVED']:.3f}; READ_RULE §8 states ~0.43")
    if not (0.50 <= null["P(this rung is bounded below the bar)"] <= 0.62):
        p.append("the true-null bounded probability moved away from READ_RULE "
                 f"§8's ~0.57: {null['P(this rung is bounded below the bar)']:.3f}")
    if not (0.07 <= null["P(LADDER-DEAD | all four rungs at this delta)"] <= 0.14):
        p.append("the true-null LADDER-DEAD probability moved away from "
                 "READ_RULE §8's ~10%: "
                 f"{null['P(LADDER-DEAD | all four rungs at this delta)']:.3f}")
    at_bar = read_distribution(BAR_EFFECT, se0)
    if not (0.90 <= at_bar["R-UNRESOLVED"] <= 0.99):
        p.append("the AT-THE-BAR R-UNRESOLVED probability moved away from "
                 f"READ_RULE §8's ~0.95: {at_bar['R-UNRESOLVED']:.3f}")
    at_incumbent = read_distribution(2.95125, se0)
    if not (0.45 <= at_incumbent["R-ADOPT-CANDIDATE"] <= 0.62):
        p.append("the power against a REPEAT of the incumbent's +2.951 moved "
                 f"away from READ_RULE §8's ~0.54: "
                 f"{at_incumbent['R-ADOPT-CANDIDATE']:.3f}")
    if not (900 <= n_decks_for_ladder_dead(0.80) <= 1400):
        p.append("n_decks_for_ladder_dead(0.80) moved away from DESIGN §3's "
                 f"~1100: {n_decks_for_ladder_dead(0.80)}")
    # --- the ladder --------------------------------------------------------
    g = branch_grid()
    if not g["all_reachable"]:
        p.append(f"not every §5 branch is reachable: {g['reachable']}")
    if branch_for_cell(0.0, 0.7, 0.0, gates_ok=False) != "U-VOID-INSTRUMENT":
        p.append("a failed gate does not void first")
    if branch_for_cell(-2.0, 0.7, -2.9, gates_ok=True) != "R-NEGATIVE":
        p.append("R-NEGATIVE is not checked before R-BOUNDED")
    if branch_for_cell(0.0, 0.5, 0.0, gates_ok=True) != "R-BOUNDED":
        p.append("a tight null does not read R-BOUNDED")
    if branch_for_cell(0.0, 1.4, 0.0, gates_ok=True) != "R-UNRESOLVED":
        p.append("a WIDE null does not read R-UNRESOLVED — it must not read "
                 "BOUNDED")
    if branch_for_cell(3.5, 0.69, 3.5 / 0.69, gates_ok=True) != "R-ADOPT-CANDIDATE":
        p.append("a clear positive does not read R-ADOPT-CANDIDATE")
    # ⛔⛔ THE BAR'S OWN SEMANTICS: a POINT ESTIMATE above the bar whose LB95 is
    # NOT is NOT an adoption. This is the whole difference from a point-estimate
    # bar and it must be pinned.
    if branch_for_cell(2.0, 0.69, 2.0 / 0.69, gates_ok=True) == "R-ADOPT-CANDIDATE":
        p.append("M=+2.0 (point estimate above the bar, LB95 = +0.62 below it) "
                 "fired R-ADOPT-CANDIDATE — the bar is on the LB95, not the "
                 "point estimate")
    # ⛔ and the incumbent's OWN realized numbers must NOT clear this bar, which
    # is the honest statement of how demanding it is.
    inc = CONTEXT_ROWS["fpu_reduction=0.2 (fpu_resurrection CELL_FPU02, "
                       "band 155e9)"]
    if branch_for_cell(inc["M"], inc["se"], inc["z"],
                       gates_ok=True) != "R-ADOPT-CANDIDATE":
        p.append("the incumbent 0.2 cell's OWN realized numbers (M +2.951, se "
                 "0.683, LB95 +1.586) do NOT clear the adoption bar — the bar "
                 "was chosen so that they just do; check BAR_EFFECT")
    # --- the round verdict -------------------------------------------------
    names = [c.name for c in CELLS]
    all_bounded = {n: "R-BOUNDED" for n in names}
    if round_verdict(all_bounded, round_gates_ok=True)["verdict"] != "LADDER-DEAD":
        p.append("four bounded rungs did not read LADDER-DEAD")
    mixed = dict(all_bounded); mixed[names[0]] = "R-NEGATIVE"
    if round_verdict(mixed, round_gates_ok=True)["verdict"] != "LADDER-DEAD":
        p.append("R-NEGATIVE does not count toward LADDER-DEAD (it implies "
                 "UB95 <= 0 < the bar)")
    one_unres = dict(all_bounded); one_unres[names[1]] = "R-UNRESOLVED"
    if round_verdict(one_unres, round_gates_ok=True)["verdict"] != "LADDER-UNRESOLVED":
        p.append("one unresolved rung did not block LADDER-DEAD")
    one_adopt = dict(all_bounded); one_adopt[names[2]] = "R-ADOPT-CANDIDATE"
    if round_verdict(one_adopt, round_gates_ok=True)["verdict"] != "LADDER-LIVE":
        p.append("an adopting rung did not read LADDER-LIVE")
    one_void = dict(all_bounded); one_void[names[3]] = "U-VOID-INSTRUMENT"
    if round_verdict(one_void, round_gates_ok=True)["verdict"] != "LADDER-VOID":
        p.append("a voided rung did not block the round verdict")
    if round_verdict(all_bounded, round_gates_ok=False)["verdict"] != "LADDER-VOID":
        p.append("a failed ROUND gate did not void the round verdict")
    short = {names[0]: "R-BOUNDED"}
    if round_verdict(short, round_gates_ok=True)["verdict"] != "LADDER-VOID":
        p.append("a MISSING rung archive did not void the round verdict — "
                 "ABSENT is FAIL")
    return p


if __name__ == "__main__":                                    # pragma: no cover
    probs = sanity_check()
    se0 = se_model(400)
    print(json.dumps({
        "sanity_problems": probs,
        "cells": [{"name": c.name, "role": c.role, "knob": c.knob,
                   "value": c.value, "band": c.seed_start,
                   "n_games": c.n_games} for c in CELLS],
        "budget": [K_DETS, SIMS_PER_DET, TOTAL_SIMS],
        "bars": {"BAR_EFFECT": BAR_EFFECT, "BRANCH_Z": BRANCH_Z,
                 "ELO_RESOLUTION_2SIGMA": ELO_RESOLUTION_2SIGMA},
        "read_distribution": {
            "delta=0 (true null)": read_distribution(0.0, se0),
            "delta=BAR_EFFECT": read_distribution(BAR_EFFECT, se0),
            "delta=2.951 (the incumbent's realized effect)":
                read_distribution(2.95125, se0)},
        "n_decks_for_ladder_dead(0.80)": n_decks_for_ladder_dead(0.80),
        "n_decks_for_adopt_power(2.951, 0.80)":
            n_decks_for_adopt_power(2.95125, 0.80),
        "branch_grid": branch_grid()}, indent=2))
    raise SystemExit(1 if probs else 0)
