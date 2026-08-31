#!/usr/bin/env python3
"""`screen_lib` — the FPU PRODUCTION-H2H round's shared instrument library.

⭐ **A FORK of `measurement/fpu_ladder_prep/screen_lib.py`** (itself a fork of
`fpu_resurrection_prep`'s, itself a fork of phasegate's). Carried **verbatim in
construction** because two rounds of merge review hardened them:
`cross_box_rev_gate` (the IS-A1 fold), `rev_matches`, `is_hex40`,
`host_matches_box`, `paired_margin`, `winrate_elo` **with R4's deck-paired elo
footing**, `recon_close`, `resolve`/`gate`, `se_anomaly`, `twosided_gate`,
`singlevar_gate`, `knob_gate`, `leaf_gate`, and — the most important carried fix —
`decks_gate` / `n_gate` **written to the prose** (the `FPU-A1` lesson).

⛔ **WHAT IS NEW, AND WHY A COPY WOULD HAVE BEEN WRONG:**

  ⭐⭐ **THE ARBITER IS ARMED ON BOTH SIDES, AND THAT INVERTS A GATE.** The
     ladder's `G-ARB-OFF` walked the whole manifest and FAILED on any armed
     arbiter. This round is the leg that prices the ladder's arbiter-off
     deviation, so an armed arbiter is the *point*: `G-ARB-OFF` is **DELETED**
     and replaced by `G-TIEARB-SIDES` (config) + `G-TIEARB-FIRE` (play).
  ⛔⛔ **AND THE REPLACEMENT DOES NOT REUSE PHASEGATE'S VOCABULARY.**
     `measurement/phasegate_prep/READ_RULE.md`'s `G-TIEARB-ARM` requires
     *"Opponent: **no** tiearb container"* — it treats an armed opponent as a
     DEFECT, because until 2026-08-31 the opponent seat was structurally
     disarmed. Running a healthy both-sides cell past that gate FAILS A GOOD
     CELL. The new vocabulary lives in `scripts/classical_search/tiearb_gates.py`
     (`assert_tiearb_sides`, `tiearb_sides_summary`), it is imported here BY
     EXPLICIT PATH, and it is what this round cites. ⛔ Those frozen prereg gates
     are NOT edited; a frozen prereg keeps its frozen gates.
  ⭐⭐ **THE BAR IS THE CONFIRMATION BAR, `+1.0 pts/deck`, NOT THE LADDER'S
     `+1.5` SCREEN BAR.** Still an EFFECT SIZE and still not `2σ̂` (owner ruling
     2026-08-30) — `2·se_model(400) = 1.381`, and `sanity_check()` asserts the
     bar has not collapsed onto it. §3 of `DESIGN.md` derives `+1.0` from the
     two production folds this program has actually accepted, and `READ_RULE.md`
     §8 states — before game 1 — what the lower bar costs: it makes ADOPT
     EASIER and BOUNDED HARDER, so a true null now reads `H-UNRESOLVED` ~71% of
     the time (the ladder's ~43%).
  ⭐ **ONE CELL, ONE BAND, ONE BOX.** There is no round verdict to compute: the
     cell's branch IS the round's. `round_verdict` is kept only as the thin
     VOID-or-branch wrapper the launcher and adjudicator share.

⛔⛔ **IS-D1 IS BINDING ON EVERY ADDRESS.** Config-shaped values resolve from
`manifest.json`; statistics from `summary.json`, **which carries no config block
at all**. `resolve()` returns the ADDRESS that answered and every gate prints it.

⛔ **ABSENT IS FAIL, never a skip and never a default** (`READ_RULE.md` §4).
"""
from __future__ import annotations

import importlib.util
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

# --------------------------------------------------------------------------- #
# ⭐⭐ THE NEW TWO-SIDED ARBITER VOCABULARY, IMPORTED BY EXPLICIT PATH          #
# --------------------------------------------------------------------------- #
# ⛔ NOT `import tiearb_gates` after a `sys.path` insert. Three sibling rounds
# ship a module named `screen_lib` and the R2 lesson (fpu_resurrection's
# pre-launch merge review) is that a bare import binds whichever fork was cached
# first — 21 failures, of which the DANGEROUS ones were the ~2 that PASSED
# against another round's constants. A name that cannot collide cannot be
# shadowed, so this loads the module under a round-unique name.
_TG_PATH = REPO / "scripts" / "classical_search" / "tiearb_gates.py"


def _load_tiearb_gates():
    if not _TG_PATH.is_file():
        raise ImportError(
            f"⛔⛔ {_TG_PATH} is ABSENT. This round's whole premise is the "
            "OPPONENT-SIDE tie arbiter, whose gate vocabulary lives there "
            "(merged 2026-08-31). A tree without it predates the plumbing, and "
            "a cell launched from it would arm the CANDIDATE ONLY — a "
            "confounded arb+fpu cell claiming a single variable. Sync the "
            "bundle.")
    spec = importlib.util.spec_from_file_location(
        "fpu_h2h_tiearb_gates", _TG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TG = _load_tiearb_gates()

#: `ROUND_ID` exists so a test can prove it loaded THIS fork and not a sibling's
#: (the R2 regression pin).
ROUND_ID = "fpu_h2h"

# =========================================================================== #
# 0. FROZEN CONSTANTS — the pair is law; these restate it, they do not decide  #
# =========================================================================== #

#: `DESIGN.md` §5. ⛔ PROPOSED, NOT CLAIMED at build time. ONE band, one cell.
#: ⚠️ `162e9`/`163e9` are RESERVED by S1 G3; `164e9`–`167e9` are SPENT by the
#: dose ladder (all four retired `decision_influenced=yes` on 2026-08-31). This
#: round therefore starts at the next monotone free id, `168e9`.
#: ⚠️⚠️ `146000000000` IS THE TRAP THE CLAIM ORDER EXISTS FOR — absent from
#: `governance/BAND_REGISTRY.csv` but carrying references in the tree. The
#: registry is NECESSARY AND NOT SUFFICIENT; the TREE SWEEP is the binding check
#: and is re-run immediately before the CSV append.
BAND = 168_000_000_000
BANDS = {"CELL_H2H_FPU02": BAND}
#: The sub-range the §9 smoke plays. ⛔ NEVER in the band claim — it buys no deck
#: of the round. Top of the band's own 1e9 space, the house convention.
THROWAWAY_BASE = 168_999_999_000
THROWAWAY_SPAN = 1000

#: `DESIGN.md` §2 — identical on BOTH sides. `fpu_reduction` is not a leaf term.
LEAF_HASH = "a36d2e15a3b3d71d"
LEAF_CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
#: ⭐⭐ THE BUDGET — the 2026-08-30 promoted desktop champion, BOTH sides.
#: ⛔ `run_cells.sh` RE-ASSERTS this against `governance/PRODUCTION.yaml` at
#: launch (`G-PROD`) rather than trusting the restatement.
K_DETS, SIMS_PER_DET, TOTAL_SIMS = 16, 1376, 22016
EXACT_K, EXACT_MODE = 2, "marginalized"
RULES_PROFILE = "fixed_v1"
BACKEND = "rust"
CHAMP_C_PUCT = 1.5

#: ⭐⭐ THE DEPLOYED ARBITER, BOTH SEATS. Seven keys, `phase_gate` INCLUDED — a
#: spec that omits it is under-specified, and a silently-defaulted `"all"` on a
#: gated cell makes it BE the ungated cell (phasegate's whole lesson).
#: ⚠️ `governance/PRODUCTION.yaml` carries no `phase_gate` key at all, because
#: the DEPLOYED arbiter is UNGATED — and `"all"` is exactly how the harness
#: spells ungated. `run_cells.sh`'s `G-PROD` reads the YAML's six knobs and
#: asserts the absence of a gate is `"all"` here, rather than letting a default
#: decide it.
DEPLOYED_TIEARB = dict(TG.DEPLOYED_TIEARB_B64)
#: The five knobs `G-PROD` can literally read out of `PRODUCTION.yaml`.
PROD_TIEARB_YAML_KEYS = ("enabled", "B", "J", "mode", "salt", "eps")

#: `READ_RULE.md` §4 `G-SAT` — a RAIL check, not a strength bar.
SAT_BAND = (0.35, 0.65)

# --------------------------------------------------------------------------- #
# ⭐⭐ `G-N` / `G-DECKS` — THE `FPU-A1` FIX, CARRIED, AND IT IS THE PROSE       #
# --------------------------------------------------------------------------- #
#: A failure rate **strictly below** this is **REPORTED, never silently
#: absorbed** (the `b32v64` 0.100% rust-panic precedent). **At or above it the
#: cell voids.** ⛔ `fpu_resurrection`'s gate demanded `n_failed == 0` and
#: `n_common == 400` instead, and VOIDED a healthy cell over 1 game in 800
#: (`fpu_resurrection_prep/AMENDMENTS.md`, FPU-A1). The bar below IS the
#: condition; there is no stricter column anywhere in this file.
FAILURE_RATE_VOID = 0.02
#: And the common-deck floor is a FRACTION, never an equality.
N_COMMON_FLOOR_FRACTION = 0.80

#: `DESIGN.md` §3 — the sizing constant, carried unchanged from the ladder (which
#: carried it from `fpu_resurrection`, which carried it from Stage-2 Phase B's
#: `ARB` cell). ⭐ IT IS NOW CORROBORATED SEVEN TIMES: the parent round's three
#: siblings (13.65 / 14.29 / 13.02) and the ladder's own four realized rungs
#: below. The carried 13.81 sits inside that spread.
#: ⛔⛔ EVERY ONE OF THOSE SEVEN IS AN **ARBITER-OFF** CELL. This round arms the
#: arbiter on BOTH seats, and the arbiter is a stochastic root hook that changes
#: ~46% of the plies it fires on — the per-deck dispersion here could be WIDER.
#: `se_anomaly` REPORTS that and it is ⛔ NEVER a branch input: every branch is
#: adjudicated at the cell's OWN REALIZED SE, so a wider dispersion costs POWER,
#: not VALIDITY. ⚠️ It is disclosed in `DESIGN.md` §3.1 before game 1.
SIGMA_D_MODEL = 13.81
REALIZED_SIGMA_D_SIBLINGS = {
    "fpu_resurrection/CELL_FPU02 (b155e9, n=400, ARB OFF)": 13.65,
    "fpu_resurrection/CELL_FPU04 (b156e9, n=399, ARB OFF)": 14.29,
    "fpu_resurrection/CELL_CPUCT10 (b157e9, n=400, ARB OFF)": 13.02,
    "fpu_ladder/CELL_FPU005 (b164e9, n=400, ARB OFF)": 13.904,
    "fpu_ladder/CELL_FPU010 (b165e9, n=400, ARB OFF)": 13.962,
    "fpu_ladder/CELL_FPU015 (b166e9, n=400, ARB OFF)": 13.722,
    "fpu_ladder/CELL_FPU030 (b167e9, n=400, ARB OFF)": 14.304,
}
#: Flag (never void) a realized/modelled SE ratio outside this band.
SE_ANOMALY_BAND = (0.70, 1.43)

# --------------------------------------------------------------------------- #
# ⭐⭐ THE BAR — THE CONFIRMATION BAR, AN EFFECT SIZE, NOT `2σ̂`                 #
# --------------------------------------------------------------------------- #
#: **Owner ruling, 2026-08-30 ("effect size sounds right"), a standing house rule
#: in `CLAUDE.md`:** *bars are set at the effect size the decision cares about —
#: NEVER at `2σ̂` of the instrument.* Here `2·se_model(400) = 1.381`, and
#: `sanity_check()` asserts `BAR_EFFECT` is NOT that number.
#:
#: ⭐ **WHY `+1.0` AND NOT THE LADDER'S `+1.5`.** The ladder was a SCREEN over
#: four unmeasured doses and set its bar so a new rung had to be *at least as
#: good as the incumbent* (`0.2`'s own `LB95` was `+1.586`). This round is the
#: CONFIRMATION leg of a dose we already hold, in the DEPLOYED configuration, and
#: the decision it feeds is *"is this worth proposing as a `PRODUCTION.yaml`
#: flip?"*. The honest reference for that is what this program has actually
#: accepted as a production fold:
#:     * the **k16 budget promotion** (2026-08-30) folded on `D = +1.229
#:       pts/deck`, `z +2.52`, n=700 decks (`measurement/h2h_22016_20260824/`);
#:     * the **B=64 arbiter fold** (2026-08-20) folded on `D = +1.7167
#:       pts/game`, `z +2.656`, n=750 decks.
#: `+1.0 pts/deck` is at or below both, so a cell that clears it has produced an
#: effect of the size this program has twice judged worth deploying. ⛔ It is
#: still a `LB95` bar, so a point estimate at `+1.0` clears NOTHING.
#:
#: ⛔ **THE SAME NUMBER CARRIES BOTH DIRECTIONS**, which is what makes the two
#: branches exhaustive and exclusive:
#:     H-ADOPT    `LB95(M) >= +1.0`   (the cell beats the bar at 95%)
#:     H-BOUNDED  `UB95(M) <  +1.0`   (the cell is BELOW the bar at 95%)
#:
#: ⚠️⚠️ **AND THE LOWER BAR IS NOT FREE.** It makes ADOPT easier and BOUNDED
#: HARDER. `READ_RULE.md` §8 prints the arithmetic: under a true null this cell
#: reads `H-UNRESOLVED` ~71% of the time (the ladder's bar gave ~43%). ⛔ This
#: round buys the ADOPT direction and its bounding direction is WEAK BY
#: CONSTRUCTION. That is stated before game 1, not discovered afterwards.
BAR_EFFECT = 1.0
BRANCH_Z = 2.0
#: The ladder's screen bar, kept as a named constant so `sanity_check()` can
#: assert this round is deliberately BELOW it rather than accidentally beside it.
LADDER_SCREEN_BAR = 1.5
#: The two realized production folds §3 derives the bar from.
PRODUCTION_FOLD_PRECEDENTS = {
    "k16x1376 budget promotion (2026-08-30, h2h_22016_20260824, b148e9)": {
        "D_pts_per_deck": 1.229, "z": 2.52, "n_decks": 700,
        "note": "⭐ folded into PRODUCTION.yaml on this. Type-M rider stands "
                "(the realized effect was below the cell's own MDE, so the "
                "MAGNITUDE is biased up and the SIGN is the reliable part)."},
    "tie-arbiter B=64 fold (2026-08-20, tiearb_widening b64_cell, b139e9)": {
        "D_pts_per_game": 1.7167, "z": 2.6561, "n_decks": 750,
        "note": "⭐ folded into PRODUCTION.yaml on this, over a frozen "
                "B-COSTKILL verdict, by a fresh owner ruling."},
}

#: ⭐ THE SECONDARY'S RESOLUTION. ⚠️ **NOT A BAR.** `+1.0 pts/deck` has no
#: exchange rate into elo that this round measures, so the elo is reported with
#: its own DECK-PAIRED CI and the instrument's own 2σ resolution beside it — and
#: ⛔ NO branch reads it. `sanity_check()` re-derives this from
#: `elo_sigma_paired` so the constant can never drift from the arithmetic.
ELO_RESOLUTION_2SIGMA = 17.4
#: ⭐ R4 (carried) — **THE ELO FOOTING.** 800 games are 400 decks × 2 seatings,
#: and pairing scales sigma by `1/sqrt(2)`. The textbook binomial sigma is the
#: UNPAIRED one (±24.6 at 2σ, n=800); quoting it beside a paired quantity
#: compares two different rulers. Every emitted field NAMES its footing.
PAIRING_FACTOR = 1.0 / math.sqrt(2.0)

#: `RECON` tolerance (`READ_RULE.md` §1.2).
RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
#: `G-REV`: the minimum short-rev prefix `rev_matches` will canonicalize.
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"

# --------------------------------------------------------------------------- #
# ⛔⛔ THE PRE-STATED CONTEXT ROWS                                              #
# --------------------------------------------------------------------------- #
#: ⭐ Stated HERE, BEFORE GAME 1, because they are the reason this cell exists
#: and the reason its bar is `+1.0`. ⛔⛔ THEY ARE CONTEXT AND NOTHING ELSE —
#: never pooled, never z-combined, never a gate input, never interpolated.
#:
#: ⚠️⚠️ **CL-068 BINDS IN FULL.** Every contrast between one of these and this
#: cell is CROSS-BAND, and CL-068 measured **1.8–2.2× over-dispersion on merely
#: cross-band contrasts** — in BOTH the elo and the deck-paired-margin
#: statistics, with an identity control exonerating the harness. ⛔ AND THESE
#: ARE WORSE THAN CROSS-BAND: every one of them is **ARBITER-OFF**, and this
#: cell is arbiter-ARMED on both seats. That is a different agent pair, not a
#: different deck draw.
CONTEXT_ROWS = {
    "fpu=0.2 — fpu_resurrection CELL_FPU02, band 155e9, ARB OFF": {
        "M": 2.95125, "se": 0.6825808836692004, "z": 4.3236634230592745,
        "LB95": 1.586088232661599, "UB95": 4.316411767338401,
        "n_paired": 400, "n_games": 800, "elo": 26.1,
        "ci95_elo_paired": [8.69, 43.53], "winrate": 0.5375,
        "branch": "F-RESURRECT",
        "note": "⭐⭐ THE DOSE THIS CELL CONFIRMS. The first measurement of "
                "`fpu_reduction` on the classical champion (the knob was "
                "structurally unreachable on its backend until 2026-08-29). ⛔ "
                "It licensed PROPOSING follow-on work and nothing else, and it "
                "is an ARBITER-OFF result on band 155e9."},
    "fpu=0.4 — fpu_resurrection CELL_FPU04, band 156e9, ARB OFF": {
        "M": 0.7543859649122807, "se": 0.7153318548949373,
        "z": 1.0545957931973815,
        "LB95": -0.676277744877594, "UB95": 2.1850496747021553,
        "n_paired": 399, "n_games": 799, "elo": -1.74,
        "ci95_elo_paired": [-19.12, 15.64], "winrate": 0.4975,
        "branch": "F-UNRESOLVED (AMENDED — FPU-A1)",
        "note": "⚠️ AMENDED from a frozen `U-VOID`: the adjudicator's "
                "G-N/G-DECKS condition columns were stricter than their own "
                "frozen prose. ⭐ THIS ROUND'S G-N/G-DECKS ARE WRITTEN TO THAT "
                "PROSE, carried from the ladder."},
    "fpu=0.05 — fpu_ladder CELL_FPU005, band 164e9, ARB OFF": {
        "M": 0.08125, "se": 0.6952455594600834, "z": 0.11686,
        "LB95": -1.30924, "UB95": 1.47174, "n_paired": 400, "n_games": 800,
        "elo": -15.65, "ci95_elo_paired": [-33.03, 1.74], "winrate": 0.4775,
        "branch": "R-BOUNDED",
        "note": "the ladder's low bracket point — bounded below +1.5."},
    "fpu=0.10 — fpu_ladder CELL_FPU010, band 165e9, ARB OFF": {
        "M": 1.5025, "se": 0.6981, "z": 2.152,
        "LB95": 0.1063, "UB95": 2.8987, "n_paired": 400, "n_games": 800,
        "elo": 17.39, "ci95_elo_paired": [-0.01, 34.78], "winrate": 0.5250,
        "branch": "R-UNRESOLVED", "note": "the ladder's middle bracket point."},
    "fpu=0.15 — fpu_ladder CELL_FPU015, band 166e9, ARB OFF": {
        "M": 1.8350, "se": 0.6861, "z": 2.674,
        "LB95": 0.4627, "UB95": 3.2073, "n_paired": 400, "n_games": 800,
        "elo": 9.99, "ci95_elo_paired": [-7.39, 27.37], "winrate": 0.5144,
        "branch": "R-UNRESOLVED",
        "note": "⭐ the ladder's LARGEST point estimate. ⛔ It did NOT clear the "
                "ladder's +1.5 bar and it would NOT clear this round's +1.0 bar "
                "either (LB95 +0.463) — `sanity_check()` pins that, so nobody "
                "reads the lower bar as a bar the ladder already cleared."},
    "fpu=0.30 — fpu_ladder CELL_FPU030, band 167e9, ARB OFF": {
        "M": 1.0588, "se": 0.7152, "z": 1.480,
        "LB95": -0.3716, "UB95": 2.4891, "n_paired": 400, "n_games": 800,
        "elo": -3.04, "ci95_elo_paired": [-20.41, 14.33], "winrate": 0.4956,
        "branch": "R-UNRESOLVED", "note": "the ladder's interior point above."},
}
CONTEXT_WARNING = (
    "⛔⛔ CONTEXT ROWS, NEVER A BRANCH INPUT AND NEVER POOLED. Every row above "
    "is on a different band AND is an ARBITER-OFF cell; this cell is on band "
    "168e9 with the arbiter ARMED ON BOTH SEATS. CL-068 measured 1.8-2.2x "
    "OVER-DISPERSION on merely CROSS-BAND contrasts, in BOTH the elo and the "
    "deck-paired-margin statistics — and an arbiter-off/arbiter-on contrast is "
    "worse than cross-band, because it is a different AGENT PAIR and not a "
    "different deck draw. ⭐ What these rows legitimately did is a DESIGN act, "
    "spent before any number of this round exists: they fixed WHICH DOSE to "
    "confirm (0.2, the only dose that has ever fired) and WHAT BAR is worth "
    "paying for. ⛔ No branch below reaches back into them."
)

#: ⛔ The round the ladder actually read, stated so a citation cannot soften it.
LADDER_VERDICT = (
    "LADDER-UNRESOLVED (2026-08-31): CELL_FPU005 R-BOUNDED; 0.10 / 0.15 / 0.30 "
    "all R-UNRESOLVED; none adopted. ⛔⛔ THAT IS NOT A NULL AND NOT A BOUND. "
    "The ladder's own READ_RULE §8.3 is explicit that LADDER-UNRESOLVED does "
    "NOT discharge the incumbent's confirmation leg the way LADDER-DEAD would — "
    "so THIS ROUND IS FUNDED BY THE OWNER, on the shape of the curve (three of "
    "four rungs positive, peaking at the incumbent), and NOT by an automatic "
    "trigger the ladder fired. ⚠️ `feedback_execute_prereg_triggers` does not "
    "apply: no prereg branch authorised this. The owner did."
)


# =========================================================================== #
# 1. THE CELL                                                                  #
# =========================================================================== #

@dataclass(frozen=True)
class CellSpec:
    """ONE archive = ONE cell = ONE band. ⛔ Nothing is pooled in this round;
    there is nothing to pool it with."""
    name: str
    role: str                       #: "laptop" — `G-HOST`'s frozen box
    knob: str                       #: "fpu_reduction"
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
        """⛔ ALWAYS `None`: this round varies `fpu_reduction` and nothing else,
        and `knob_gate` asserts the override is absent-as-null."""
        return self.value if self.knob == "c_puct" else None


#: ⭐ THE ONE CELL. n=800 games = 400 seat-balanced decks × 2 seatings, on its
#: own fresh band, against the DEPLOYED champion (22016 + arbiter B=64), with the
#: dose on the candidate only.
CELLS: tuple[CellSpec, ...] = (
    CellSpec(
        "CELL_H2H_FPU02", "laptop", "fpu_reduction", 0.2, BAND, 400,
        "⭐⭐ STEP 2 OF `ADOPTION_CHAIN` — the PRODUCTION H2H. Candidate = the "
        "production champion (k16x1376 = 22016) + the DEPLOYED tie arbiter "
        "(B=64, J=4, argmax, salt tiearb2-deploy-v1, eps 0.0, phase_gate all) + "
        "`fpu_reduction = 0.2`. Opponent = THE SAME AGENT WITHOUT THE DOSE. ⭐ "
        "The single variable is the knob, measured in the configuration that "
        "actually ships — which is the one thing every prior fpu cell could not "
        "do, because the harness could not arm the opponent's arbiter until "
        "2026-08-31."),
)


def cell_by_name(name: str) -> CellSpec:
    for c in CELLS:
        if c.name == name:
            return c
    raise KeyError(f"unknown cell {name!r}; known: {[c.name for c in CELLS]}")


def cells_of_box(role: str) -> tuple[CellSpec, ...]:
    return tuple(c for c in CELLS if c.role == role)


#: ⭐ THE ADOPTION CHAIN, RESTATED FROM THE LADDER'S OWN FROZEN COPY
#: (`fpu_ladder_prep/screen_lib.ADOPTION_CHAIN`) so that a fired cell cannot
#: later be walked through a shorter chain than the one already pre-registered.
#: ⛔ THIS ROUND IS STEP 2. It is not the end of the chain.
ADOPTION_CHAIN = (
    "1. THE DOSE LADDER / THE PARENT SCREEN — a dose reads positive on its own "
    "fresh band with the arbiter OFF both sides. ⭐ DONE: fpu=0.2 read "
    "F-RESURRECT (+2.951, z +4.32, band 155e9); the ladder that bracketed it "
    "read LADDER-UNRESOLVED (band 164-167e9).",
    "2. ⭐⭐ THIS ROUND — PRODUCTION H2H: the dose vs the DEPLOYED champion with "
    "the TIE ARBITER ARMED ON BOTH SEATS (B=64, PRODUCTION.yaml since "
    "2026-08-20), on a FRESH band. ⛔ THIS IS THE LEG THAT PRICES THE "
    "ARBITER-OFF DEVIATION every earlier fpu reading carries.",
    "3. CARCASUM EXTERNAL — the arm-on T-TRANSFER protocol, the only "
    "out-of-family check this program has (feedback_evloss_grader's F4 lesson: "
    "judged headroom is family-relative, so out-of-family corroboration comes "
    "first).",
    "4. E4 EPOCH on the phone.",
    "⛔ EACH LEG IS ITS OWN PREREG, ITS OWN BAND AND ITS OWN OWNER FUNDING. A "
    "cell firing here funds NOTHING automatically.",
)

#: ⭐⭐ WHAT `H-ADOPT` LICENSES — AND THE WORD IS *PROPOSING*.
ADOPT_CONSEQUENCE = (
    "⭐⭐ H-ADOPT LICENSES **PROPOSING** TWO THINGS, AND NEITHER IS AUTOMATIC: "
    "(a) a `governance/PRODUCTION.yaml` change setting the champion's "
    "`fpu_reduction` to 0.2 — a PROPOSAL to the owner, who decides; and (b) "
    "funding step 3 of ADOPTION_CHAIN, the Carcasum external leg on the arm-on "
    "T-TRANSFER protocol. ⛔⛔ IT IS NOT AN ADOPTION. `governance/PRODUCTION.yaml` "
    "is UNTOUCHED on every branch of this round, the flip needs an OWNER RULING "
    "on this evidence exactly as the k16 and B=64 folds did, and the "
    "out-of-family leg comes BEFORE any claim that the effect is real outside "
    "this family (F4: a +1.49 in-family ceiling read -0.64 at z -3.8 "
    "out-of-family on the same CRN worlds)."
)

#: ⭐ AND THE MIRROR, equally pre-registered.
BOUNDED_CONSEQUENCE = (
    "⭐ H-BOUNDED DISCHARGES THE ADOPTION CHAIN AT STEP 2: at the DEPLOYED "
    "configuration, fpu=0.2 is below +1.0 pts/deck at 95%, so it is not worth "
    "proposing as a production flip and step 3 is not worth funding. ⛔ It "
    "BOUNDS, it does not ZERO, and it does not retract the arbiter-off +2.951 — "
    "it says the effect does not SURVIVE into the deployed configuration at the "
    "size the decision cares about. ⚠️ That is a real and useful finding: it is "
    "precisely the transfer assumption the ladder's READ_RULE §5.2 rider named "
    "as unpriced."
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
    """⭐ THE IS-A1 FOLD, carried unchanged. "Was this ONE round, at ONE rev?" —
    ⛔ NEVER by comparing one box's emitted short rev to another's.

      (1) **THE PINS AGREE.** Every role that published a `PINNED_SRC_REV` must
          publish the SAME 40-hex sha. A missing pin is FAIL.
      (2) **EVERY EMITTED REV CANONICALIZES TO THAT PIN** via `rev_matches`.

    ⚠️ THIS ROUND IS SINGLE-BOX, so (1) passes trivially with one pin — which is
    correct: there is no cross-box proposition to check. ⛔ The clause is CARRIED
    ANYWAY rather than deleted, because the fpu plumbing is PYTHON-ONLY and the
    stale-source failure mode it exists for is unchanged: a box on pre-fix source
    serves a dose-FREE candidate with a healthy wheel and the right leaf hash."""
    pins = {r: (p or "").strip().lower()
            for r, p in (pins_by_role or {}).items() if p}
    base = {"pins": pins, "revs": dict(revs_by_cell or {}), "canonicalized": {}}
    if not pins:
        return {**base, "ok": False, "distinct_pins": [],
                "why": ("no box published a PINNED_SRC_REV — ABSENT is FAIL. "
                        "IS-A1 forbids falling back to comparing the emitted "
                        "revs to each other.")}
    bad_pins = sorted(r for r, p in pins.items() if not is_hex40(p))
    distinct = sorted(set(pins.values()))
    if bad_pins:
        return {**base, "ok": False, "distinct_pins": distinct,
                "why": (f"box(es) {bad_pins} published a PINNED_SRC_REV that is "
                        "not a 40-hex sha — ABSENT-or-malformed is FAIL.")}
    if len(distinct) > 1:
        return {**base, "ok": False, "distinct_pins": distinct,
                "why": ("⛔ THE BOXES WERE AT DIFFERENT COMMITS: their "
                        f"PINNED_SRC_REV files disagree ({distinct}). ⚠️⚠️ THE "
                        "fpu PLUMBING AND THE opp-tiearb PLUMBING ARE BOTH "
                        "PYTHON-ONLY, so a box on pre-fix source would serve a "
                        "knob-FREE candidate and/or an UNARMED opponent with a "
                        "healthy-looking wheel and leaf hash. ⚠️ NOTE THIS IS "
                        "THE PINS DISAGREEING, NOT THE SHORT REVS — the short "
                        "revs disagreeing is EXPECTED (IS-A1).")}
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
                    f"{pin} that every box published" if not bad else
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
    if role == "local" and not any(a in h for a in _HOST_ALIASES["laptop"]):
        return True, f"host {observed_host!r} is not the laptop ⇒ treated as {role!r}"
    return False, f"host {observed_host!r} does not match box role {role!r}"


# =========================================================================== #
# 4. THE STATISTIC — `RECON`'s independent re-implementation                   #
# =========================================================================== #

def _by_deck(records: Iterable[Mapping]) -> dict[int, dict[int, float]]:
    """`{seed: {a_seat: diff}}`. A record missing `seed`, `a_seat` or `diff` is
    DROPPED here and shows up as a short `n_paired` at `G-DECKS` — never silently
    defaulted to zero."""
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
    ⛔ THE WRONG FOOTING; emitted only so the correction is auditable."""
    return ((400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n_games)
            / (wr * (1 - wr)))


def elo_sigma_paired(wr: float, n_games: int) -> float:
    """⭐ 1σ on elo on the **DECK-PAIRED** footing (R4)."""
    return elo_sigma_unpaired(wr, n_games) * PAIRING_FACTOR


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """W/D/L, winrate and elo recomputed from the raw records.

    ⚠️⚠️ **R4 (carried): THE EMITTED SIGMA IS DECK-PAIRED.** The old unlabelled
    `elo_sig_1sigma` key is GONE ON PURPOSE — a footing that is not in the field
    name is a footing nobody checks.

    ⚠️⚠️ THE ELO IS THE SECONDARY AND IS **NOT A BAR**. The bar is `+1.0
    pts/deck` on the deck-paired margin; there is no exchange rate into elo that
    this round measures. A disagreement between the margin and the elo is
    DISCLOSED rather than arbitrated."""
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
    """`RECON` tolerance: rel 1e-6 / abs 1e-9. `None` closes only to `None`."""
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
    ⛔ Reported, NEVER a branch input.

    ⚠️ IN THIS ROUND A **WIDER** RATIO IS PRE-DISCLOSED AS PLAUSIBLE: the seven
    corroborating siblings are all arbiter-OFF, and an arbiter that changes ~46%
    of the plies it fires on can add per-deck dispersion. A wider realized SE
    costs POWER, never VALIDITY — the branch uses the realized SE."""
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
                          "WIDER than modelled (PRE-DISCLOSED as plausible "
                          "here — the model's seven siblings are all ARB-OFF)"
                          if ratio > hi else "inside the band"),
            "note": "DISPERSION ANOMALY — reported, never a branch input"}


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# =========================================================================== #
# 5. ⭐⭐ THE READ DISTRIBUTION — WHAT THE BAR COSTS, BEFORE GAME 1            #
# =========================================================================== #

def read_distribution(delta: float, se: float | None = None) -> dict:
    """⭐⭐ **THE HOUSE RULE'S OWN DEMAND, EVALUATED IN CODE** (owner ruling
    2026-08-30): *"if the honest answer is 'we can only afford the bounding
    direction', SAY SO in the READ_RULE including the null's expected read
    distribution."* Here the honest answer is the OTHER direction — this round
    can afford the ADOPT direction and its bound is weak — and it is computed,
    not asserted.

        H-ADOPT      M - 2se >= BAR   <=>  M >= BAR + 2se
        H-BOUNDED    M + 2se <  BAR   <=>  M <  BAR - 2se
        H-NEGATIVE   M <= 0 AND z <= -2  <=>  M <= -2se  (a SUBSET of BOUNDED,
                                                          checked first)
        H-UNRESOLVED the remainder
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
            "H-ADOPT": p_adopt, "H-BOUNDED": p_bounded,
            "H-NEGATIVE": p_negative, "H-UNRESOLVED": p_unres,
            "P(bounded below the bar)": p_bounded_all}


def _invphi(p: float) -> float:
    lo, hi = -8.0, 8.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def n_decks_for_adopt_power(delta: float, p_target: float = 0.80) -> int:
    """How many decks to fire `H-ADOPT` with probability `p_target` at a TRUE
    effect `delta`? Solve `delta - (BAR + 2se) = z_p * se`.

    ⭐ AT `delta = +2.951` (the incumbent's own arbiter-off reading) THIS IS
    ~405 DECKS — so the funded 400 is, to within a deck, exactly the `n` the
    house rule asks for ("size n to resolve THAT"). ⛔ At the ladder's largest
    point estimate (+1.835) it is ~2,209, which this round does NOT buy and
    `READ_RULE.md` §8 says so."""
    z_p = _invphi(p_target)
    denom = z_p + 2.0
    if delta <= BAR_EFFECT or denom <= 0:
        return -1                          # unreachable at any n
    se = (delta - BAR_EFFECT) / denom
    return int(math.ceil((SIGMA_D_MODEL / se) ** 2))


def n_decks_for_bounded_power(p_target: float = 0.80) -> int:
    """The mirror image: how many decks to read `H-BOUNDED` with probability
    `p_target` under a TRUE NULL? Solve `Phi((BAR - 2se)/se) = p_target`.

    ⛔ ~1,540 decks — nearly 4x the funded 400. THE BOUNDING DIRECTION IS NOT
    BOUGHT BY THIS ROUND, and `READ_RULE.md` §8 states it before game 1."""
    x = _invphi(p_target)
    se = BAR_EFFECT / (x + 2.0)
    return int(math.ceil((SIGMA_D_MODEL / se) ** 2))


def power_at(delta: float, se: float) -> float:
    """P(the cell fires `H-ADOPT`) at a true effect `delta`."""
    if se is None or se <= 0:
        return float("nan")
    return read_distribution(delta, se)["H-ADOPT"]


# =========================================================================== #
# 6. THE BRANCH LADDER — `READ_RULE.md` §5, pre-registered and EXHAUSTIVE      #
# =========================================================================== #

BRANCHES = ("H-VOID-INSTRUMENT", "H-NEGATIVE", "H-ADOPT", "H-BOUNDED",
            "H-UNRESOLVED")


def branch_for_cell(M, se, z, *, gates_ok: bool) -> str:
    """The §5 ladder, IN ORDER. First match wins. Adjudicated on the cell's OWN
    realized SE, AGAINST ZERO.

    ⛔ Exclusive and exhaustive BY CONSTRUCTION, and ORDERED rather than
    disjoint: `H-NEGATIVE` requires `M <= 0 ∧ z <= -2`, which forces
    `UB95 = M + 2SE <= 0 < BAR_EFFECT`, so it would ALSO satisfy `H-BOUNDED` —
    which is exactly why it is checked first. `H-ADOPT` and `H-BOUNDED` cannot
    both hold, because `LB95 <= UB95`.
    """
    if not gates_ok:
        return "H-VOID-INSTRUMENT"
    if M is None or se is None or z is None:
        return "H-VOID-INSTRUMENT"
    lb95 = M - 2.0 * se
    ub95 = M + 2.0 * se
    if M <= 0.0 and z <= -BRANCH_Z:
        return "H-NEGATIVE"
    if lb95 >= BAR_EFFECT:
        return "H-ADOPT"
    if ub95 < BAR_EFFECT:
        return "H-BOUNDED"
    return "H-UNRESOLVED"


def round_verdict(branches: Mapping[str, str], *, round_gates_ok: bool,
                  expected_cells: Sequence[str] | None = None) -> dict:
    """⭐ ONE CELL, so the ROUND VERDICT **IS** THE CELL'S BRANCH.

    ⚠️ The function is kept (rather than deleted) for exactly two reasons, both
    structural: (a) a ROUND-LEVEL gate failure (`G-WHEEL-SAME` / `G-REV` /
    `G-BLIND`) must void even a cell whose own gates passed; (b) an ABSENT
    archive must read VOID rather than "no verdict", because ABSENT is FAIL.
    ⛔ There is nothing to conjoin and nothing to pool."""
    want = list(expected_cells or [c.name for c in CELLS])
    missing = [n for n in want if n not in branches]
    voided = [n for n, b in branches.items() if b == "H-VOID-INSTRUMENT"]
    if not round_gates_ok or voided or missing:
        return {"verdict": "H-VOID-INSTRUMENT", "voided": voided,
                "missing": missing, "bar": BAR_EFFECT,
                "why": ("⛔ THE ROUND DISCHARGES NOTHING. " + "; ".join(filter(None, [
                    "a ROUND-LEVEL gate FAILED (G-WHEEL-SAME / G-REV / G-BLIND)"
                    if not round_gates_ok else "",
                    f"cell(s) {voided} are H-VOID-INSTRUMENT" if voided else "",
                    f"the frozen cell(s) {missing} produced NO ARCHIVE — ABSENT "
                    "is FAIL" if missing else ""]))
                    + ". ⛔ A voided or absent cell is NOT a bound: neither "
                      "H-ADOPT nor H-BOUNDED may be declared over it, and the "
                      "statistics print as a COMPANION TABLE only.")}
    name = want[0]
    v = branches[name]
    return {"verdict": v, "voided": [], "missing": [], "bar": BAR_EFFECT,
            "why": {"H-ADOPT": ADOPT_CONSEQUENCE,
                    "H-BOUNDED": BOUNDED_CONSEQUENCE,
                    "H-NEGATIVE":
                        "⭐ THE DOSE IS ACTIVELY HARMFUL IN THE DEPLOYED "
                        "CONFIGURATION. Pre-registered and mechanistically "
                        "plausible: the arbiter fires on exact ties and a "
                        "pessimistic FPU changes which ties get REACHED, so an "
                        "interaction with the wrong sign is a real mechanism, "
                        "not a surprise. ⛔ It licenses no production change "
                        "either — the champion already runs fpu=None, so there "
                        "is nothing to turn off.",
                    "H-UNRESOLVED":
                        "⛔⛔ NOT A NULL AND NOT A BOUND "
                        "(feedback_noisy_plateau_not_a_conclusion). The round "
                        "bought no verdict on the deployed configuration. "
                        "READ_RULE §8 pre-registers this as the LIKELIEST "
                        "single outcome under a true null (~71%) and §8.2 "
                        "pre-commits its price."}[v]}


def branch_grid(step: float = 0.05, se_values=(0.3, 0.5, 0.691, 0.9, 1.4)) -> dict:
    """⭐ `READ_RULE.md` §5's own demand: sweep a dense `(M, SE)` grid and prove
    EXACTLY ONE branch fires at every point, and that every branch is
    REACHABLE."""
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
            "all_reachable": set(seen) >= {"H-NEGATIVE", "H-ADOPT",
                                           "H-BOUNDED", "H-UNRESOLVED"}}


RIDERS_ALWAYS = (
    "⛔⛔ EVERY CONTEXT ROW IS AN ARBITER-OFF CELL ON ANOTHER BAND. Nothing in "
    "screen_lib.CONTEXT_ROWS is ever pooled or z-combined with this cell. "
    "CL-068 measured 1.8-2.2x over-dispersion on merely cross-band contrasts, "
    "and an arb-off/arb-on contrast is a different AGENT PAIR on top of that.",
    "⛔ governance/PRODUCTION.yaml is UNTOUCHED on every branch. H-ADOPT "
    "licenses PROPOSING the flip and funding step 3; the flip itself needs an "
    "OWNER RULING, exactly as the k16 and B=64 folds did.",
    "⭐ THE ARBITER IS ARMED ON BOTH SEATS AT THE FULL DEPLOYED SPEC (B=64, J=4, "
    "argmax, salt tiearb2-deploy-v1, eps 0.0, phase_gate all). Its rollout "
    "variance therefore rides BOTH arms and CRN deck-pairing absorbs the deck "
    "draw as usual — but the arbiter is STOCHASTIC, so it is a variance source "
    "the seven arb-off sizing siblings did not carry (DESIGN §3.1).",
    "⛔ THIS IS ONE CELL ON ONE FRESH BAND, which retires "
    "decision_influenced=yes the moment the read-out lands. "
    "feedback_results_table_source_of_truth's confirm-before-promotion rule is "
    "satisfied for the AXIS (this cell IS the confirm of the 155e9 screen) and "
    "NOT for the deployed configuration beyond it — step 3 is the "
    "out-of-family check and it comes before any general claim.",
    "⚠️ elo may never be quoted bare, and in this round it is not a bar at all: "
    "the bar is +1.0 pts/deck on the deck-paired margin. A disagreement between "
    "the margin and the elo is DISCLOSED, never arbitrated.",
    "⚠️ B=0 -> B=64 TRANSFER RUNS THE OTHER WAY HERE. This cell is the leg that "
    "PRICES the ladder's arbiter-off deviation. It therefore says nothing about "
    "an arbiter-FREE champion, and no reading here may be quoted back onto the "
    "155e9/164-167e9 cells.",
)
RIDERS_H_ADOPT = (
    ADOPT_CONSEQUENCE,
    "⛔ IT IS A ONE-DOSE RESULT. The cell measures fpu=0.2 in the deployed "
    "configuration; it locates NO optimum and licenses NO interpolation. The "
    "ladder that tried to bracket 0.2 read LADDER-UNRESOLVED.",
    "⚠️ IT IS A k16x1376, fixed_v1+R9, exact-k2-marginalized, rust, B=64-both-"
    "seats result on ONE fresh band. Every one of those is part of the claim.",
    "⚠️ TYPE-M RIDER. The funded n=400 is powered ~80% against a REPEAT of the "
    "incumbent's +2.951 and only ~21% against the ladder's largest point "
    "estimate (+1.835). A cell that adopts near the bar has a MAGNITUDE biased "
    "upward; the SIGN is the reliable part. This is the same rider the k16 fold "
    "carries and it travels with every citation.",
)
RIDERS_H_BOUNDED = (
    BOUNDED_CONSEQUENCE,
    "⚠️ H-BOUNDED BOUNDS; IT DOES NOT ZERO. The reading is 'below +1.0 pts/deck "
    "at 95%', never 'this dose is worthless' — a cell can read H-BOUNDED "
    "carrying a POSITIVE point estimate.",
    "⛔ AND THE BOUNDING DIRECTION IS WEAK BY CONSTRUCTION HERE: under a true "
    "null this branch fires only ~27% of the time at n=400 (READ_RULE §8). A "
    "realized H-BOUNDED is therefore a STRONGER statement than its probability "
    "suggests, and its absence is a much weaker one.",
)
RIDERS_H_NEGATIVE = (
    "⭐ H-NEGATIVE IS PRE-REGISTERED AND MECHANISTICALLY PLAUSIBLE. The arbiter "
    "fires on exact ties; a pessimistic FPU changes which ties are REACHED, so "
    "an interaction with the wrong sign is a real mechanism. It is also exactly "
    "the reading the arbiter-off cells could not have produced.",
    "⛔ It licenses no production change — the champion already runs fpu=None.",
    "⚠️ Its false-fire rate under a true null is 2.28%, and this round runs ONE "
    "cell, so there is no multiplicity to correct.",
)
RIDERS_H_UNRESOLVED = (
    "⛔⛔ H-UNRESOLVED IS NOT A NULL AND NOT A BOUND "
    "(feedback_noisy_plateau_not_a_conclusion). The cell did not resolve its "
    "bar in either direction.",
    "⛔ IT DOES NOT DISCHARGE STEP 2 OF THE ADOPTION CHAIN, and it does not "
    "license proposing the PRODUCTION.yaml flip. READ_RULE §8 pre-registers it "
    "as the LIKELIEST outcome under a true null (~71% at n=400 with a +1.0 "
    "bar) and §8.2 pre-registers its price.",
    "⛔ THE CELL MAY NOT BE EXTENDED, TOPPED UP OR RE-READ AT LARGER n ON ITS "
    "OWN BAND. That is the rodv3 failure mode (n bought after seeing the sign), "
    "and CL-068 means the extension could not be pooled with the original "
    "anyway. A re-run is a NEW round: new pair, new band, new owner funding.",
)


# =========================================================================== #
# 7. THE ROUND-SPECIFIC GATES                                                  #
# =========================================================================== #

def decks_gate(spec: CellSpec, records: Sequence[Mapping],
               all_specs: Sequence[CellSpec] = CELLS) -> dict:
    """⛔⛔ `G-DECKS` — **WRITTEN TO THE PROSE. THE CARRIED `FPU-A1` FIX.**

      (a) ⛔ HARD FAIL — every realized seed inside **this cell's own** range.
      (b) ⚠️ REPORTED, then bar-checked — decks played at ONE SEAT ONLY. Their
          rate voids **only at or above `FAILURE_RATE_VOID`**; below it they are
          REPORTED, never silently absorbed (the `b32v64` 0.100% precedent).
          ⭐⭐ **THE DENOMINATOR IS GAMES, NOT DECKS** — one deck played at one
          seat only IS exactly one failed GAME, so this rate and `G-N`'s
          `n_failed / n_games` are THE SAME QUANTITY read off two different
          documents. A decks denominator would make the two gates disagree by a
          factor of two on the same archive.
      (c) ⛔ HARD FAIL — `n_common < N_COMMON_FLOOR_FRACTION * n_decks`. A
          FRACTION, never an equality, and a BACKSTOP: at 400 decks the 80%
          floor allows 80 lost decks while the 2% bar voids at 16 games.
      (d) ⛔ HARD FAIL — this cell's range intersects another cell's. ⚠️ With
          ONE cell the clause is vacuous by arithmetic; it is CARRIED rather
          than deleted so a future fork that adds a second cell inherits it
          armed. `sanity_check()` asserts the range is disjoint from the
          THROWAWAY block, which is the live version of the same worry.
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
    half_rate = len(half) / float(max(1, spec.n_games))
    floor = N_COMMON_FLOOR_FRACTION * spec.n_decks

    hard, notes = [], []
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
           "one-seat-only rate is BELOW the 2%-of-games void bar, and n_common "
           "clears the 80% floor"
         if ok else
         "⛔ G-DECKS FAILED: " + "; ".join(hard)
         + ((" ⚠️ also reported: " + " ".join(notes)) if notes else "")))


def n_gate(spec: CellSpec, n, n_failed, n_common, addr_n, addr_nf) -> dict:
    """⛔⛔ `G-N` — **WRITTEN TO THE PROSE. THE OTHER HALF OF THE `FPU-A1` FIX.**

      ⛔ HARD FAIL  `n` or `n_failed` ABSENT (ABSENT is FAIL).
      ⛔ HARD FAIL  the ACCOUNTING IDENTITY `n + n_failed != n_games`. Games lost
                    WITHOUT being recorded mean the denominator is unknown —
                    strictly worse than a recorded failure, and NOT the case the
                    bar exists for.
      ⛔ HARD FAIL  `n_failed / n_games >= FAILURE_RATE_VOID`.
      ⚠️ REPORTED   `0 < n_failed / n_games < FAILURE_RATE_VOID`.
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

    NEITHER `fpu_reduction` NOR the tie arbiter is a leaf term (the arbiter is a
    post-search root hook), so both sides must carry the identical hash — and a
    moved-hash check can therefore never prove either surface LIVE, which is why
    `G-FPU` / `G-TWOSIDED` / `G-TIEARB-SIDES` / `G-TIEARB-FIRE` exist."""
    same = (cand_hash is not None and cand_hash == opp_hash)
    right = cand_hash == LEAF_HASH
    curve_ok = list(cand_curve or []) == LEAF_CURVE125
    ok = same and right and curve_ok
    return gate("G-LEAF", ok,
                {"cand_leaf_hash": cand_hash, "opp_leaf_hash": opp_hash,
                 "expected": LEAF_HASH, "cand_curve": cand_curve},
                "manifest:config.{cand,opp}_leaf_hash",
                ("both sides carry the SAME leaf a36d2e15a3b3d71d (curve125) — "
                 "neither the dose nor the arbiter is a leaf term" if ok else
                 "⛔ G-LEAF FAILED: " + "; ".join(filter(None, [
                     "the two sides' leaf hashes DIFFER (misconfigured cell)"
                     if not same else "",
                     f"leaf hash is not {LEAF_HASH}" if not right else "",
                     "v29_meeple_curve is not curve125" if not curve_ok else "",
                 ]))))


#: `G-SINGLEVAR`'s alias table. ⚠️ The cell OWNS `fpu_reduction`, so it is
#: asserted DIFFERENT and every other alias is asserted EQUAL.
#: ⛔⛔ **THE `tiearb_*` TERMINALS ARE DELIBERATELY *NOT* IN THIS TABLE, AND
#: THAT IS A FACT ABOUT THE EMITTED MANIFEST, NOT A CHOICE.** The candidate
#: stamps `config.champion.tiearb_{enabled,b,j,mode,salt,eps,phase_gate}`; the
#: opponent CANNOT stamp them under `config.opponent.champ_cfg`, because
#: `_cfg_from_dict` reads exactly five keys by name and drops the rest — which
#: is precisely why the arbiter needed its own `tiearb` parameter on
#: `_make_opponent`. A `G-SINGLEVAR` clause over `tiearb_*` would therefore read
#: ABSENT on the opponent and VOID EVERY HEALTHY CELL. ⭐ The proposition "both
#: seats run the DEPLOYED arbiter" is owned by `G-TIEARB-SIDES`, which reads the
#: opponent's own addresses (`opp_tiearb` / `config.opp_tiearb` /
#: `config.opponent.tiearb`) — and by `G-TIEARB-FIRE`, which reads its play.
SINGLEVAR_ALIASES = ("k_dets", "sims_per_det", "total_sims", "c_puct", "tau_p",
                     "value_norm", "leaf_quantize", "final_select",
                     "fpu_reduction")


def singlevar_gate(spec: CellSpec, rows: Mapping[str, Mapping]) -> dict:
    """`G-SINGLEVAR` — the cell's OWN alias must DIFFER across the two sides and
    equal the frozen value on the candidate; every OTHER alias must be EQUAL.

    ⚠️ The opponent's knobs live one level down under `champ_cfg` and its BUDGET
    lives one level up under `config.opponent.*` — a gate written from the design
    rather than from a real manifest voids every healthy cell."""
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
                ("; ".join(notes) + " — every OTHER alias is identical across "
                 "the two sides" if not bad else
                 "⛔ G-SINGLEVAR FAILED: " + "; ".join(bad)))


def knob_gate(spec: CellSpec, requested_fpu, requested_c, fpu_addr, c_addr,
              shared_c) -> dict:
    """⭐⭐ `G-FPU` — THE INVERTED-LIVENESS GATE, on the REQUEST side.

    ⛔⛔ **THIS IS THE GATE THE WHOLE FAMILY EXISTS BEHIND.** Until 2026-08-29
    `rust_agent.search_config_rs` passed a HARD-CODED `None` into
    `SearchConfigRs`'s `fpu_reduction` slot: a cell run over that defect plays
    champion-vs-champion, moves no leaf hash, produces a healthy winrate inside
    `G-SAT`'s rail, and reads as a clean, credible null.

    ⚠️ `MISSING` IS NOT `None`, and ABSENT is FAIL.
    ⭐ `c_puct` is asserted absent-as-null: a stray `--cand-c-puct` would be a
    second variable, and the request side and the resolved side are different
    bugs, so both get a witness.
    """
    want_fpu, want_c = spec.cand_fpu, spec.cand_c_puct
    bad = []
    if requested_fpu is MISSING:
        bad.append("config.cand_search.fpu_reduction ABSENT — ABSENT is FAIL. A "
                   "harness predating the fpu plumbing cannot be adjudicated: "
                   "its candidate was fpu-BLIND by construction.")
    elif (requested_fpu is None) != (want_fpu is None) or (
            want_fpu is not None and float(requested_fpu) != float(want_fpu)):
        bad.append(f"fpu_reduction is {requested_fpu!r}, this cell is frozen at "
                   f"{want_fpu!r}")
    if requested_c is MISSING:
        bad.append("config.cand_search.c_puct ABSENT — ABSENT is FAIL")
    elif (requested_c is None) != (want_c is None) or (
            want_c is not None and float(requested_c) != float(want_c)):
        bad.append(f"c_puct override is {requested_c!r}, this cell is frozen at "
                   f"{want_c!r} (⛔ this round does not vary c_puct)")
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
                (f"the REQUEST matches this cell's frozen dose "
                 f"(fpu={want_fpu!r}) and carries NO c_puct override" if not bad
                 else "⛔ G-FPU FAILED: " + "; ".join(bad)))


def twosided_gate(spec: CellSpec, rows: Mapping[str, Mapping]) -> dict:
    """⭐⭐ `G-TWOSIDED` — THE SECOND, INDEPENDENT WITNESS FOR THE DOSE.

    `G-FPU` proves the knob was REQUESTED. This proves it BOUND, and bound ON THE
    CANDIDATE ONLY — read off the two sides' RESOLVED `HeuristicPriorConfig`
    blocks rather than off the flag that asked for it.

    ⚠️ It is weaker than a play-derived witness (a PUCT constant has no fire
    counter). ⭐ THE ARBITER, BY CONTRAST, HAS ONE — `G-TIEARB-FIRE` — which is
    why this round's arbiter evidence is strictly stronger than its dose
    evidence, and why the golden-gate inheritance argument (DESIGN §9) still has
    to carry the dose's play-derived half.

    ⛔ ABSENT is FAIL on BOTH sides. `config.opponent.champ_cfg.fpu_reduction` is
    emitted as an explicit `null` precisely so this gate has an address to read.
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
                           "not the deployed champion")
            if want_cand is None and cv is not None:
                bad.append(f"the candidate carries fpu_reduction={cv!r} on a cell "
                           "frozen without one")
            if want_cand is not None and (cv is None
                                          or float(cv) != float(want_cand)):
                bad.append(f"⛔⛔ the candidate's RESOLVED fpu_reduction is {cv!r}, "
                           f"not the frozen {want_cand!r} — the knob did NOT bind. "
                           "This is exactly the hard-coded-None defect the family "
                           "was funded to close, and a cell over it is "
                           "champion-vs-champion.")
        else:                                    # c_puct — EQUAL on both sides
            if want_cand is None:
                if cv is None or ov is None or float(cv) != float(ov):
                    bad.append(f"c_puct differs across the sides ({cv!r} vs "
                               f"{ov!r}) on a cell that froze no override — a "
                               "SECOND variable, or the `--c-puct` both-sides "
                               "trap in mirror image")
                elif float(cv) != float(CHAMP_C_PUCT):
                    bad.append(f"both sides carry c_puct={cv!r}, not the "
                               f"champion's {CHAMP_C_PUCT} — the opponent of "
                               "this cell IS the champion of record")
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


# --------------------------------------------------------------------------- #
# ⭐⭐ THE TWO NEW GATES — THE ARBITER, ON BOTH SEATS                           #
# --------------------------------------------------------------------------- #

def tiearb_sides_gate(cell_manifest: Mapping) -> dict:
    """⭐⭐ `G-TIEARB-SIDES` — **CONFIG.** Both seats ARMED at the FULL deployed
    spec, `phase_gate` INCLUDED.

    ⛔⛔ **THIS GATE REPLACES THE LADDER'S `G-ARB-OFF`, AND IT IS ITS INVERSE.**
    It delegates to `scripts/classical_search/tiearb_gates.assert_tiearb_sides`,
    the vocabulary merged on 2026-08-31 with the opponent-side plumbing.

    ⛔ IT DELIBERATELY DOES NOT REUSE PHASEGATE'S `G-TIEARB-ARM`, which requires
    *"Opponent: no tiearb container"* — a rule that made sense only while the
    opponent seat was structurally disarmed, and which would FAIL A HEALTHY CELL
    here. Those frozen prereg gates are not edited; this is the new vocabulary.

    ⚠️ THE TWO SEATS HAVE DIFFERENT ABSENCE CONVENTIONS ON PURPOSE (`cand_tiearb`
    is stamped always, `opp_tiearb` only when armed), and `tiearb_gates` encodes
    the difference so no read-rule has to re-derive it. Here BOTH are expected
    ARMED, so the asymmetry does not bite — but a MISSING opponent container is
    exactly the "one-sided cell wearing a symmetric cell's name" failure, and it
    reads `ABSENT from the manifest`, which is FAIL.

    ⭐ A MISSING `phase_gate` key is a FAIL and never a default: absent means a
    stale wheel whose arbiter ran UNGATED, and a silently-defaulted `"all"` on a
    gated cell makes it BE the ungated cell (phasegate's whole lesson).
    """
    ok, findings = TG.check_tiearb_sides(cell_manifest or {},
                                         cand_expected=DEPLOYED_TIEARB,
                                         opp_expected=DEPLOYED_TIEARB)
    if not cell_manifest:
        ok = False
        findings = ["FAIL: the manifest is ABSENT — ABSENT is FAIL"]
    resolved = {}
    for side in ("candidate", "opponent"):
        spec_, addr = TG.resolve_tiearb(cell_manifest or {}, side)
        resolved[side] = {
            "address": addr,
            "spec": ({k: spec_.get(k) for k in TG.TIEARB_SPEC_KEYS}
                     if isinstance(spec_, Mapping) else None)}
    return gate("G-TIEARB-SIDES", ok,
                {"expected_both_seats": dict(DEPLOYED_TIEARB),
                 "resolved": resolved, "findings": findings,
                 "vocabulary": "scripts/classical_search/tiearb_gates.py "
                               "(assert_tiearb_sides) — merged 2026-08-31 with "
                               "the --opp-tiearb-* plumbing",
                 "not_phasegate": "⛔ phasegate's G-TIEARB-ARM ('opponent: no "
                                  "tiearb container') would FAIL this healthy "
                                  "cell; it is NOT reused and NOT edited."},
                "manifest:{cand,opp}_tiearb / config.{cand,opp}_tiearb / "
                "config.opponent.tiearb",
                ("⭐⭐ BOTH SEATS carry the DEPLOYED arbiter "
                 f"{DEPLOYED_TIEARB} — the cell's single variable is the dose. "
                 + " | ".join(findings) if ok else
                 "⛔ G-TIEARB-SIDES FAILED: " + " | ".join(findings)))


def tiearb_fire_gate(summary: Mapping) -> dict:
    """⭐⭐ `G-TIEARB-FIRE` — **PLAY.** The arbiter did not merely get REQUESTED
    on both seats; it BOUND and it FIRED on both.

    ⛔⛔ THIS IS THE WITNESS `G-TIEARB-SIDES` CANNOT BE. A config echo is exactly
    the class of evidence the hard-coded `fpu_reduction = None` satisfied for
    months. `tiearb_gates.tiearb_sides_summary` reads the per-seat counters, and
    a both-sides cell whose `opp_tiearb_games` is 0 or ABSENT is a ONE-SIDED cell
    wearing a symmetric cell's name — the exact defect the opponent-side plumbing
    exists to end.

    HARD FAILS, per seat:
      * the seat's summary block is ABSENT (`*_games` 0 or missing);
      * `*_games` != the cell's own game count is NOT checked here — `G-N` owns
        the accounting — but ZERO games on a seat is;
      * `*_fired_plies_total == 0` — armed and never fired is not arbitration;
      * `*_G_FIRE_fired` is True. ⚠️ THE FLAG IS INVERTED BY ITS OWN NAME: the
        harness sets it when `phi < 1.0`, i.e. it is the VOID flag, and `false`
        is HEALTHY. A gate that read it as "did it fire?" would void every good
        cell and pass every dead one;
      * `*_partial_argmax_total != 0` (the Stage-2 `G-PLY` rule, carried).

    REPORTED, never fatal: `*_errors_total` (fail-soft arbiter errors fall back
    to the champion's own pick and the game survives), `*_phi`, `*_B`, `*_J`,
    `*_phase_gates`.
    """
    s = summary or {}
    sides = TG.tiearb_sides_summary(s)
    hard, notes = [], []
    detail = {"sides": sides, "raw": {}}
    for side, prefix in (("candidate", "tiearb_"), ("opponent", "opp_tiearb_")):
        blk = sides.get(side)
        raw = {k: s.get(k) for k in
               (f"{prefix}games", f"{prefix}phi", f"{prefix}fired_plies_total",
                f"{prefix}pickchanges_total", f"{prefix}G_FIRE_fired",
                f"{prefix}partial_argmax_total", f"{prefix}errors_total",
                f"{prefix}B", f"{prefix}J", f"{prefix}phase_gates")}
        detail["raw"][side] = raw
        if not blk:
            hard.append(
                f"⛔⛔ {side}: `{prefix}games` is 0 or ABSENT — THIS SEAT NEVER "
                "ARBITRATED. A both-sides cell with a dead seat is a ONE-SIDED "
                "cell wearing a symmetric cell's name, and every config gate "
                "passes it.")
            continue
        if not blk.get("fired_plies"):
            hard.append(f"⛔ {side}: `{prefix}fired_plies_total` is 0 — the "
                        "arbiter was armed and never fired. Armed-and-silent is "
                        "not arbitration.")
        if blk.get("G_FIRE_fired") is True:
            hard.append(f"⛔ {side}: `{prefix}G_FIRE_fired` is TRUE — ⚠️ THE FLAG "
                        "IS THE VOID FLAG (the harness sets it when phi < 1.0). "
                        f"Realized phi = {blk.get('phi')!r} fires/game.")
        if blk.get("G_FIRE_fired") is None:
            hard.append(f"⛔ {side}: `{prefix}G_FIRE_fired` ABSENT — ABSENT is FAIL")
        pa = raw.get(f"{prefix}partial_argmax_total")
        if pa is None:
            hard.append(f"⛔ {side}: `{prefix}partial_argmax_total` ABSENT — "
                        "ABSENT is FAIL (the Stage-2 G-PLY rule)")
        elif int(pa) != 0:
            hard.append(f"⛔ {side}: `{prefix}partial_argmax_total` = {pa} != 0 "
                        "(G-PLY)")
        gates = raw.get(f"{prefix}phase_gates")
        if gates is not None and list(gates) != [DEPLOYED_TIEARB["phase_gate"]]:
            hard.append(f"⛔ {side}: `{prefix}phase_gates` = {gates!r}, not "
                        f"[{DEPLOYED_TIEARB['phase_gate']!r}] — more than one "
                        "value means the cell MIXED two arbiter configs")
        bs = raw.get(f"{prefix}B")
        if bs is not None and list(bs) != [DEPLOYED_TIEARB["B"]]:
            hard.append(f"⛔ {side}: `{prefix}B` = {bs!r}, not "
                        f"[{DEPLOYED_TIEARB['B']}]")
        js = raw.get(f"{prefix}J")
        if js is not None and list(js) != [DEPLOYED_TIEARB["J"]]:
            hard.append(f"⛔ {side}: `{prefix}J` = {js!r}, not "
                        f"[{DEPLOYED_TIEARB['J']}]")
        err = raw.get(f"{prefix}errors_total") or 0
        if err:
            notes.append(f"⚠️ {side}: {err} fail-soft arbiter error(s) — REPORTED, "
                         "never a branch input (the ply fell back to the "
                         "champion's own pick and the game survived).")
        notes.append(f"⭐ {side}: phi = {blk.get('phi')!r} fires/game over "
                     f"{blk.get('games')} game(s), {blk.get('fired_plies')} "
                     f"fired plies, {blk.get('pickchanges')} pick changes.")
    return gate("G-TIEARB-FIRE", not hard, detail, "summary.json",
                ((" ".join(notes) + " " if notes else "")
                 + "⭐⭐ BOTH SEATS arbitrated — a PLAY-DERIVED witness, not a "
                   "config echo"
                 if not hard else
                 "⛔ G-TIEARB-FIRE FAILED: " + "; ".join(hard)
                 + ((" ⚠️ also reported: " + " ".join(notes)) if notes else "")))


# =========================================================================== #
# 8. SELF-CHECK — the library's own invariants                                 #
# =========================================================================== #

def sanity_check() -> list[str]:
    """Problems with THIS FILE's own constants and arithmetic. Empty == clean.
    ⛔ Run by `analyze_h2h.py --selftest` AND by `run_cells.sh`'s precondition
    ladder; a non-empty list is a BUILD failure, not a round failure."""
    p: list[str] = []
    # --- the cell ----------------------------------------------------------
    if len(CELLS) != 1:
        p.append(f"CELLS has {len(CELLS)} entries; this round is ONE cell")
    if {c.name for c in CELLS} != set(BANDS):
        p.append("CELLS' names do not match BANDS' keys")
    c0 = CELLS[0]
    if c0.value != 0.2:
        p.append(f"the frozen dose is {c0.value}; this round confirms 0.2 — the "
                 "only dose that has ever fired on the classical champion")
    if c0.knob != "fpu_reduction":
        p.append(f"the cell owns {c0.knob!r}, not fpu_reduction")
    if c0.cand_c_puct is not None:
        p.append("the cell carries a c_puct override — it may not")
    if c0.seed_start != BAND or c0.seed_start != BANDS[c0.name]:
        p.append(f"{c0.name} does not start at its own band {BAND}")
    if c0.n_decks != 400 or c0.n_games != 800:
        p.append(f"{c0.name} is {c0.n_decks} decks / {c0.n_games} games; the "
                 "funded shape is 400 decks / 800 games")
    if c0.role != "laptop":
        p.append(f"{c0.name} is assigned to {c0.role!r}; the round is LAPTOP "
                 "ONLY (the owner holds the local box)")
    # --- the throwaway block may never touch the cell's range --------------
    t_lo, t_hi = THROWAWAY_BASE, THROWAWAY_BASE + THROWAWAY_SPAN - 1
    if not (c0.seed_end < t_lo or c0.seed_start > t_hi):
        p.append(f"{c0.name}'s range intersects the THROWAWAY block "
                 f"[{t_lo},{t_hi}]")
    if not (BAND <= t_lo <= BAND + 999_999_999):
        p.append("the THROWAWAY block is outside this band's own 1e9 space — "
                 "the house convention keeps it there so it can never collide "
                 "with another round's band")
    # --- and the band may not be one that is already spent or reserved -----
    for spent in (155_000_000_000, 156_000_000_000, 157_000_000_000,
                  161_000_000_000, 162_000_000_000, 163_000_000_000,
                  164_000_000_000, 165_000_000_000, 166_000_000_000,
                  167_000_000_000):
        if c0.seed_start == spent:
            p.append(f"the band {c0.seed_start} is already claimed, spent or "
                     "reserved")
    # --- the budget --------------------------------------------------------
    if K_DETS * SIMS_PER_DET != TOTAL_SIMS:
        p.append(f"{K_DETS} x {SIMS_PER_DET} != {TOTAL_SIMS}")
    if (K_DETS, SIMS_PER_DET, TOTAL_SIMS) != (16, 1376, 22016):
        p.append("the budget is not the 2026-08-30 promoted champion k16x1376")
    # --- ⭐⭐ THE DEPLOYED ARBITER SPEC -------------------------------------
    if set(DEPLOYED_TIEARB) != set(TG.TIEARB_SPEC_KEYS):
        p.append(f"DEPLOYED_TIEARB keys {sorted(DEPLOYED_TIEARB)} != the "
                 f"vocabulary's {sorted(TG.TIEARB_SPEC_KEYS)} — a spec that "
                 "omits phase_gate is UNDER-SPECIFIED")
    if DEPLOYED_TIEARB != TG.DEPLOYED_TIEARB_B64:
        p.append("DEPLOYED_TIEARB has drifted from "
                 "tiearb_gates.DEPLOYED_TIEARB_B64 — cite the symbol, do not "
                 "retype seven keys")
    if DEPLOYED_TIEARB.get("enabled") is not True:
        p.append("DEPLOYED_TIEARB is not ARMED — this round's whole premise is "
                 "the arbiter live on BOTH seats")
    if DEPLOYED_TIEARB.get("phase_gate") != "all":
        p.append("DEPLOYED_TIEARB.phase_gate is not 'all' — the deployed "
                 "arbiter is UNGATED and 'all' is how the harness spells it")
    # --- the sizing arithmetic ---------------------------------------------
    if abs(se_model(400) - 0.6905) > 5e-4:
        p.append(f"se_model(400) = {se_model(400):.4f}, DESIGN §3 says 0.6905")
    # --- ⭐⭐ THE BAR IS AN EFFECT SIZE, NOT 2 sigma-hat --------------------
    if abs(BAR_EFFECT - 2 * se_model(400)) < 0.05:
        p.append(f"BAR_EFFECT {BAR_EFFECT} has collapsed onto 2*se_model(400) = "
                 f"{2 * se_model(400):.4f}. ⛔ THE HOUSE RULE (owner 2026-08-30) "
                 "FORBIDS A BAR SET AT 2 sigma-hat OF THE INSTRUMENT.")
    if BAR_EFFECT <= 0:
        p.append("BAR_EFFECT must be positive")
    if BAR_EFFECT >= LADDER_SCREEN_BAR:
        p.append(f"BAR_EFFECT {BAR_EFFECT} is not BELOW the ladder's screen bar "
                 f"{LADDER_SCREEN_BAR}. This round is the CONFIRMATION leg of a "
                 "dose already held, not a screen over unmeasured doses, and "
                 "DESIGN §3 derives the difference.")
    k16 = PRODUCTION_FOLD_PRECEDENTS[
        "k16x1376 budget promotion (2026-08-30, h2h_22016_20260824, b148e9)"]
    if BAR_EFFECT > k16["D_pts_per_deck"] + 1e-9:
        p.append(f"BAR_EFFECT {BAR_EFFECT} is HARDER than the k16 budget "
                 f"promotion's own realized {k16['D_pts_per_deck']} pts/deck — "
                 "the bar is supposed to be the effect size this program has "
                 "actually accepted as a production fold, not a harder one")
    # ⛔ the incumbent's own realized numbers MUST clear this bar ...
    inc = CONTEXT_ROWS["fpu=0.2 — fpu_resurrection CELL_FPU02, band 155e9, ARB OFF"]
    if branch_for_cell(inc["M"], inc["se"], inc["z"], gates_ok=True) != "H-ADOPT":
        p.append("the incumbent 0.2 cell's OWN realized numbers (M +2.951, se "
                 "0.683, LB95 +1.586) do NOT clear the confirmation bar — the "
                 "bar is supposed to be clearable by a repeat of the effect "
                 "being confirmed; check BAR_EFFECT")
    # ... and the ladder's LARGEST point estimate must NOT, or the lower bar
    # would be quietly reading as "a bar the ladder already cleared".
    pk = CONTEXT_ROWS["fpu=0.15 — fpu_ladder CELL_FPU015, band 166e9, ARB OFF"]
    if branch_for_cell(pk["M"], pk["se"], pk["z"], gates_ok=True) == "H-ADOPT":
        p.append("the ladder's LARGEST point estimate (0.15, M +1.835, LB95 "
                 "+0.463) clears this bar — it must not: no ladder rung "
                 "adopted, and a bar the ladder already cleared would be a bar "
                 "chosen after seeing the data")
    # --- ⭐ R4's provenance assert, carried ---------------------------------
    elo_2s_paired = 2.0 * elo_sigma_paired(0.5, 800)
    if abs(ELO_RESOLUTION_2SIGMA - elo_2s_paired) > 0.05:
        p.append(f"ELO_RESOLUTION_2SIGMA {ELO_RESOLUTION_2SIGMA} is not the "
                 f"DECK-PAIRED 2-sigma resolution {elo_2s_paired:.4f} at 800 "
                 f"games / 400 decks (the UNPAIRED figure is "
                 f"{2 * elo_sigma_unpaired(0.5, 800):.4f} — R4's fix)")
    if abs(PAIRING_FACTOR - 0.7071) > 1e-4:
        p.append(f"PAIRING_FACTOR {PAIRING_FACTOR} is not 1/sqrt(2)")
    if "elo" in branch_for_cell.__code__.co_varnames:
        p.append("branch_for_cell has taken an elo argument — elo may NEVER be "
                 "a branch input (READ_RULE §1.1)")
    # --- ⭐⭐ THE READ DISTRIBUTION, ASSERTED ------------------------------
    se0 = se_model(400)
    null = read_distribution(0.0, se0)
    if not (0.66 <= null["H-UNRESOLVED"] <= 0.75):
        p.append("the true-null H-UNRESOLVED probability is "
                 f"{null['H-UNRESOLVED']:.3f}; READ_RULE §8 states ~0.71")
    if not (0.25 <= null["P(bounded below the bar)"] <= 0.34):
        p.append("the true-null bounded probability moved away from READ_RULE "
                 f"§8's ~0.29: {null['P(bounded below the bar)']:.3f}")
    if not (0.0 <= null["H-ADOPT"] <= 0.002):
        p.append("the true-null FALSE-ADOPT probability moved away from "
                 f"READ_RULE §8's ~0.03%: {null['H-ADOPT']:.5f}")
    at_bar = read_distribution(BAR_EFFECT, se0)
    if not (0.90 <= at_bar["H-UNRESOLVED"] <= 0.99):
        p.append("the AT-THE-BAR H-UNRESOLVED probability moved away from "
                 f"READ_RULE §8's ~0.95: {at_bar['H-UNRESOLVED']:.3f}")
    at_inc = read_distribution(2.95125, se0)
    if not (0.74 <= at_inc["H-ADOPT"] <= 0.85):
        p.append("the power against a REPEAT of the incumbent's +2.951 moved "
                 f"away from READ_RULE §8's ~0.80: {at_inc['H-ADOPT']:.3f}")
    at_pk = read_distribution(1.835, se0)
    if not (0.15 <= at_pk["H-ADOPT"] <= 0.28):
        p.append("the power against the ladder's largest point estimate "
                 f"(+1.835) moved away from READ_RULE §8's ~0.21: "
                 f"{at_pk['H-ADOPT']:.3f}")
    n_adopt = n_decks_for_adopt_power(2.95125, 0.80)
    if not (380 <= n_adopt <= 430):
        p.append("n_decks_for_adopt_power(2.951, 0.80) moved away from DESIGN "
                 f"§3's ~405: {n_adopt}")
    n_bound = n_decks_for_bounded_power(0.80)
    if not (1400 <= n_bound <= 1700):
        p.append("n_decks_for_bounded_power(0.80) moved away from DESIGN §3's "
                 f"~1540: {n_bound}")
    # --- the ladder --------------------------------------------------------
    g = branch_grid()
    if not g["all_reachable"]:
        p.append(f"not every §5 branch is reachable: {g['reachable']}")
    if branch_for_cell(0.0, 0.7, 0.0, gates_ok=False) != "H-VOID-INSTRUMENT":
        p.append("a failed gate does not void first")
    if branch_for_cell(-2.0, 0.7, -2.9, gates_ok=True) != "H-NEGATIVE":
        p.append("H-NEGATIVE is not checked before H-BOUNDED")
    if branch_for_cell(0.0, 0.3, 0.0, gates_ok=True) != "H-BOUNDED":
        p.append("a tight null does not read H-BOUNDED")
    if branch_for_cell(0.0, 1.4, 0.0, gates_ok=True) != "H-UNRESOLVED":
        p.append("a WIDE null does not read H-UNRESOLVED — it must not read "
                 "BOUNDED")
    if branch_for_cell(3.0, 0.69, 3.0 / 0.69, gates_ok=True) != "H-ADOPT":
        p.append("a clear positive does not read H-ADOPT")
    # ⛔⛔ THE BAR'S OWN SEMANTICS: a POINT ESTIMATE above the bar whose LB95 is
    # NOT is NOT an adoption.
    if branch_for_cell(1.5, 0.69, 1.5 / 0.69, gates_ok=True) == "H-ADOPT":
        p.append("M=+1.5 (point estimate above the bar, LB95 = +0.12 below it) "
                 "fired H-ADOPT — the bar is on the LB95, not the point "
                 "estimate")
    # --- the round verdict wrapper -----------------------------------------
    name = CELLS[0].name
    if round_verdict({name: "H-ADOPT"}, round_gates_ok=True)["verdict"] != "H-ADOPT":
        p.append("a single adopting cell did not read H-ADOPT at the round level")
    if round_verdict({name: "H-ADOPT"}, round_gates_ok=False)["verdict"] \
            != "H-VOID-INSTRUMENT":
        p.append("a failed ROUND gate did not void the round verdict")
    if round_verdict({}, round_gates_ok=True)["verdict"] != "H-VOID-INSTRUMENT":
        p.append("a MISSING cell archive did not void the round verdict — "
                 "ABSENT is FAIL")
    if round_verdict({name: "H-VOID-INSTRUMENT"},
                     round_gates_ok=True)["verdict"] != "H-VOID-INSTRUMENT":
        p.append("a voided cell did not void the round verdict")
    return p


if __name__ == "__main__":                                    # pragma: no cover
    probs = sanity_check()
    se0 = se_model(400)
    print(json.dumps({
        "round": ROUND_ID,
        "sanity_problems": probs,
        "cells": [{"name": c.name, "role": c.role, "knob": c.knob,
                   "value": c.value, "band": c.seed_start,
                   "n_games": c.n_games} for c in CELLS],
        "budget": [K_DETS, SIMS_PER_DET, TOTAL_SIMS],
        "deployed_tiearb_both_seats": DEPLOYED_TIEARB,
        "bars": {"BAR_EFFECT": BAR_EFFECT, "BRANCH_Z": BRANCH_Z,
                 "ELO_RESOLUTION_2SIGMA": ELO_RESOLUTION_2SIGMA,
                 "ladder_screen_bar": LADDER_SCREEN_BAR},
        "read_distribution": {
            "delta=0 (true null)": read_distribution(0.0, se0),
            "delta=BAR_EFFECT": read_distribution(BAR_EFFECT, se0),
            "delta=1.835 (the ladder's largest point estimate)":
                read_distribution(1.835, se0),
            "delta=2.951 (the incumbent's realized effect)":
                read_distribution(2.95125, se0)},
        "n_decks_for_adopt_power(2.951, 0.80)":
            n_decks_for_adopt_power(2.95125, 0.80),
        "n_decks_for_adopt_power(1.835, 0.80)":
            n_decks_for_adopt_power(1.835, 0.80),
        "n_decks_for_bounded_power(0.80)": n_decks_for_bounded_power(0.80),
        "branch_grid": branch_grid()}, indent=2))
    raise SystemExit(1 if probs else 0)
