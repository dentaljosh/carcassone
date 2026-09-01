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
        "fpu_h2h_r2_tiearb_gates", _TG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TG = _load_tiearb_gates()

#: `ROUND_ID` exists so a test can prove it loaded THIS fork and not a sibling's
#: (the R2 regression pin).
ROUND_ID = "fpu_h2h_r2"

# =========================================================================== #
# 0. FROZEN CONSTANTS — the pair is law; these restate it, they do not decide  #
# =========================================================================== #

#: `DESIGN.md` §5. ⛔ PROPOSED, NOT CLAIMED at build time. ONE band, one cell.
#: ⚠️ `162e9`/`163e9` are RESERVED by S1 G3; `164e9`–`167e9` are SPENT by the
#: dose ladder and `168e9` by **ROUND 1 of this H2H** (all five retired
#: `decision_influenced=yes` on 2026-08-31). This round therefore starts at the
#: next monotone free id, `169e9`.
#: ⚠️⚠️ `146000000000` IS THE TRAP THE CLAIM ORDER EXISTS FOR — absent from
#: `governance/BAND_REGISTRY.csv` but carrying references in the tree. The
#: registry is NECESSARY AND NOT SUFFICIENT; the TREE SWEEP is the binding check
#: and is re-run immediately before the CSV append.
BAND = 169_000_000_000
BANDS = {"CELL_H2H2_FPU02": BAND}
#: The sub-range the §9 smoke plays. ⛔ NEVER in the band claim — it buys no deck
#: of the round. Top of the band's own 1e9 space, the house convention.
#: ⚠️ TWO boxes may smoke in this round, so each takes its OWN offset
#: (`SMOKE_OFFSETS` / `IDENT_OFFSETS` below) — a shared offset would let one
#: box's smoke satisfy the other's, which is exactly what a per-box plumbing
#: probe must not do.
THROWAWAY_BASE = 169_999_999_000
THROWAWAY_SPAN = 1000

# --------------------------------------------------------------------------- #
# ⭐⭐ THE CHUNKING — THE UNIT OF BOX ASSIGNMENT AND OF PROVENANCE              #
# --------------------------------------------------------------------------- #
#: `DESIGN.md` §6.3/§6.4. The 800-deck band is executed as `N_CHUNKS` contiguous
#: sub-ranges of `DECKS_PER_CHUNK` decks, each its own out-dir.
#:
#: ⛔⛔ **THIS IS NOT A CONVENIENCE — IT IS WHAT MAKES THE FLEXIBLE-BOX CLAUSE
#: SAFE.** `eval_fair_puct` writes `manifest.json` at run START and
#: `summary.json` at run END, so a run KILLED mid-flight leaves a manifest with
#: no summary. If the whole band were one out-dir, stopping the laptop to add
#: local would destroy that dir's summary permanently and clobber it on the next
#: launch (the harness's summary covers only the seeds of the invocation that
#: wrote it). With chunks: a killed chunk is RESUMED (its per-game records are
#: cached-skipped by the harness), every completed chunk carries a full
#: manifest+summary pair, and a box change can only ever land on a chunk
#: BOUNDARY — which is precisely what makes "which box played which range" an
#: exactly answerable question rather than an estimate.
N_CHUNKS = 8
DECKS_PER_CHUNK = 100
#: ⭐ The two boxes this round may use. ⛔ THROUGHPUT-ONLY — see `HOST_PROVENANCE`
#: and `DESIGN.md` §6.4. No statistic, bar, gate or branch reads the box.
ROLES = ("laptop", "local")
#: Each box's own throwaway offsets, so one box's smoke can never stand in for
#: the other's.
SMOKE_OFFSETS = {"laptop": 500, "local": 520}
IDENT_OFFSETS = {"laptop": 700, "local": 740}

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

#: `DESIGN.md` §3 — the sizing constant. ⭐⭐ **ROUND 2 MOVES IT, AND THE MOVE IS
#: AN IMPROVEMENT, NOT A DRIFT.** Round 1 was the first — and is still the only —
#: cell this program owns with the arbiter ARMED ON BOTH SEATS, and it realized
#: `se = 0.68247` at `n = 400` decks, i.e. `sigma_D = 13.6495`. That is a
#: measurement of THIS EXACT AGENT PAIR, where the carried `13.81` was an
#: arbiter-OFF constant used as a stand-in. ⛔ The seven arbiter-off siblings are
#: kept below as CORROBORATION ONLY: they bracket 13.02–14.30 and the arb-on
#: realization lands inside that spread, which is itself the (welcome, and
#: pre-round-1 non-obvious) finding that arming the arbiter on both seats did NOT
#: inflate the per-deck dispersion.
#: ⛔⛔ IT IS STILL POWER ARITHMETIC ONLY. `se_anomaly` REPORTS the realized /
#: modelled ratio and it is ⛔ NEVER a branch input: every branch is adjudicated
#: at the cell's OWN REALIZED SE, so a wider dispersion costs POWER, not VALIDITY.
SIGMA_D_MODEL = 13.6495
#: ⭐ The one sibling that is the same agent pair as this round.
ARB_ON_SIBLING = {
    "fpu_h2h ROUND 1 / CELL_H2H_FPU02 (b168e9, n=400 decks, ⭐ ARB ON BOTH SEATS)": {
        "realized_se": 0.6824744405461254, "implied_sigma_D": 13.649488810922508,
        "note": "⭐⭐ THE SIZING CONSTANT OF THIS ROUND COMES FROM HERE. It is the "
                "ONLY arbiter-on-both-seats cell in existence and it is the "
                "direct predecessor of this one — same arms, same budget, same "
                "arbiter dict, same leaf, same rules, one band lower. ⛔ Its "
                "MEAN is a CONTEXT ROW and is never pooled (CL-068); its "
                "DISPERSION is a design input, spent before game 1."},
}
REALIZED_SIGMA_D_SIBLINGS = {
    "fpu_resurrection/CELL_FPU02 (b155e9, n=400, ARB OFF)": 13.65,
    "fpu_resurrection/CELL_FPU04 (b156e9, n=399, ARB OFF)": 14.29,
    "fpu_resurrection/CELL_CPUCT10 (b157e9, n=400, ARB OFF)": 13.02,
    "fpu_ladder/CELL_FPU005 (b164e9, n=400, ARB OFF)": 13.904,
    "fpu_ladder/CELL_FPU010 (b165e9, n=400, ARB OFF)": 13.962,
    "fpu_ladder/CELL_FPU015 (b166e9, n=400, ARB OFF)": 13.722,
    "fpu_ladder/CELL_FPU030 (b167e9, n=400, ARB OFF)": 14.304,
    "fpu_h2h ROUND 1/CELL_H2H_FPU02 (b168e9, n=400, ⭐ ARB ON)": 13.6495,
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
#: ⚠️⚠️ **THE BAR IS ROUND 1's, VERBATIM AND UNMOVED.** Round 1 read
#: `H-UNRESOLVED` and its own §8.2 mandated a NEW round on a NEW band with fresh
#: owner funding — which this is. ⛔ A successor round that quietly softened the
#: bar after seeing `M = +1.019` would be a bar chosen from the data, which is
#: the one thing the whole apparatus exists to prevent. `sanity_check()` pins
#: `BAR_EFFECT` to round 1's value.
#:
#: ⚠️⚠️ **WHAT DOUBLING `n` BUYS — AND WHAT IT STILL DOES NOT.** At the funded
#: 800 decks (`se ~ 0.4826`) the bounding direction roughly doubles (a true null
#: reads `H-BOUNDED` 50.6% of the time, up from 27.4%) and a repeat of the
#: incumbent's `+2.951` adopts 97.9% of the time (up from 80.5%). ⛔⛔ BUT THE
#: ROUND STILL CANNOT RESOLVE ROUND 1'S OWN POINT ESTIMATE: at a true `+1.019`
#: this cell reads `H-UNRESOLVED` 95.4% of the time, and `n_decks_for_adopt_power
#: (1.019, 0.80)` is over four MILLION decks. `READ_RULE.md` §8 prints all of it
#: before game 1.
BAR_EFFECT = 1.0
BRANCH_Z = 2.0

#: ⛔⛔⛔ **THE ONE THING THIS ROUND MUST DISCLOSE BEFORE GAME 1, AND IT WAS FOUND
#: BY THE ROUND'S OWN `sanity_check()` RATHER THAN BY A READER.**
#:
#: At the funded 800 decks, `2 * se_model(800) = 0.9652`, and the frozen bar is
#: `+1.0`. ⚠️ **THE BAR HAS NUMERICALLY COLLIDED WITH `2σ̂` OF THIS INSTRUMENT** —
#: the exact coincidence the owner's 2026-08-30 ruling names as a defect, and
#: round 1's own `sanity_check()` carried a guard against it (which fires here).
#:
#: ⭐ **WHY THE BAR STILL DOES NOT MOVE, AND WHY THAT IS THE RIGHT CALL.** The
#: ruling is about PROVENANCE — *"a bar defined as exactly 2·se_model"*, i.e. a
#: bar read off the instrument instead of off the decision. This bar is not that:
#: it was derived in round 1 from the two production folds this program has
#: accepted (+1.229 and +1.7167 pts), frozen there, and is carried VERBATIM. At
#: round 1's own n it sat at `0.73 · 2σ̂`; the collision is an artefact of
#: DOUBLING n while (correctly) refusing to move a pre-registered bar. ⛔ Moving
#: it now — in either direction — after seeing round 1's `M = +1.019` would be
#: choosing a bar from the data, which is strictly the worse sin.
#:
#: ⛔⛔ **BUT THE PATHOLOGY THE RULING WARNS ABOUT IS REAL HERE AND IS PRICED,
#: NOT WAVED AWAY.** The ruling's mechanism is: *"a bar at 2·se_model makes the
#: kill branch fire only on a NEGATIVE point estimate."* At this `n`,
#: `H-BOUNDED` requires `M < BAR - 2se = +0.034` — so in practice **the bounding
#: branch fires almost exactly when the point estimate is non-positive**, and a
#: true null splits ~50.6% `H-BOUNDED` / ~47.1% `H-UNRESOLVED`. ⭐ That is
#: computed by `read_distribution`, asserted by `sanity_check`, and stated in
#: `DESIGN.md` §3.2 and `READ_RULE.md` §8 **before game 1** — which is precisely
#: what the house rule demands of a round that can only afford one direction.
BAR_COINCIDENCE_AT_FUNDED_N = {
    "bar": 1.0,
    "two_sigma_hat_at_funded_n": 0.9652,
    "ratio_bar_over_2sigmahat": 1.036,
    "ratio_at_round_1_n": 0.733,
    "provenance": "⭐ DERIVED FROM THE DECISION, NOT THE INSTRUMENT: the two "
                  "production folds this program has accepted (k16 budget "
                  "+1.229 pts/deck; arbiter B=64 +1.7167 pts/game). Frozen in "
                  "round 1 and carried VERBATIM.",
    "consequence": "⛔ H-BOUNDED requires M < +0.034 at this n, i.e. the kill "
                   "branch effectively needs a NON-POSITIVE point estimate. A "
                   "true null reads H-BOUNDED ~50.6% / H-UNRESOLVED ~47.1%.",
    "why_the_bar_does_not_move": "⛔ Moving a pre-registered bar after seeing "
                                 "round 1's M = +1.019 would be a bar chosen "
                                 "from the data. The disclosure is the remedy; "
                                 "the bar is not.",
}
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
ELO_RESOLUTION_2SIGMA = 12.3
#: ⭐ R4 (carried) — **THE ELO FOOTING.** 1600 games are 800 decks × 2 seatings,
#: and pairing scales sigma by `1/sqrt(2)`. The textbook binomial sigma is the
#: UNPAIRED one (±17.4 at 2σ, n=1600); quoting it beside a paired quantity
#: compares two different rulers. Every emitted field NAMES its footing.
#: ⚠️ Note the coincidence and do not be misled by it: `17.4` was round 1's
#: PAIRED 2σ at 800 games and is round 2's UNPAIRED 2σ at 1600. The field names
#: are the defence.
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
    "⭐⭐ fpu=0.2 — fpu_h2h ROUND 1 CELL_H2H_FPU02, band 168e9, ARB ON BOTH SEATS": {
        "M": 1.01875, "se": 0.6824744405461254, "z": 1.4927298950342849,
        "LB95": -0.3461988810922507, "UB95": 2.3836988810922506,
        "n_paired": 400, "n_games": 800, "elo": 1.7371924043128577,
        "ci95_elo_paired": [-15.63480402312976, 19.109188831755475],
        "winrate": 0.5025,
        "branch": "H-UNRESOLVED",
        "note": "⭐⭐ THE DIRECT PREDECESSOR — the SAME cell, the SAME bar, one "
                "band lower, at HALF this round's n. ⛔⛔ AND IT IS STILL A "
                "CONTEXT ROW: NEVER POOLED, NEVER z-COMBINED, NEVER AVERAGED "
                "WITH THIS CELL. A different band is a different band, and "
                "CL-068 measured 1.8-2.2x over-dispersion on exactly that class "
                "of contrast in BOTH statistics, with an identity control "
                "exonerating the harness. ⛔ Round 1's own READ_RULE §8.2 "
                "forbids extending it at larger n on its own band (the rodv3 "
                "failure mode) and states that the extension could not be "
                "pooled with the original ANYWAY — so this round is a fresh "
                "measurement that stands alone, not a top-up. ⭐ What round 1 "
                "legitimately contributes is a DESIGN input spent before game 1: "
                "its realized DISPERSION (sigma_D 13.6495) is this round's "
                "sizing constant, because it is the only arbiter-on-both-seats "
                "cell in existence."},
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
    "⛔⛔ CONTEXT ROWS, NEVER A BRANCH INPUT AND NEVER POOLED. This cell is on "
    "band 169e9 with the arbiter ARMED ON BOTH SEATS. Six of the seven rows "
    "above are on a different band AND are ARBITER-OFF cells — worse than "
    "cross-band, because that is a different AGENT PAIR and not a different deck "
    "draw. ⛔⛔ AND THE SEVENTH — ROUND 1, band 168e9 — IS THE ONE MOST LIKELY "
    "TO BE MIS-USED, precisely BECAUSE it is the same agent pair: it is STILL "
    "cross-band, CL-068 measured 1.8-2.2x over-dispersion on exactly that class "
    "in BOTH the elo and the deck-paired-margin statistics, and round 1's own "
    "READ_RULE §8.2 pre-committed that its cell may not be extended or topped up "
    "and could not be pooled with an extension anyway. ⛔ THIS ROUND IS 800 "
    "FRESH DECKS, NOT 400 + 400. ⭐ What these rows legitimately did is a DESIGN "
    "act, spent before any number of this round exists: they fixed WHICH DOSE to "
    "confirm (0.2, the only dose that has ever fired), WHAT BAR is worth paying "
    "for (unmoved from round 1), and — from round 1's realized DISPERSION alone "
    "— what n to fund. ⛔ No branch below reaches back into them."
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

#: ⭐⭐ ROUND 1's OWN VERDICT AND ITS OWN MANDATE, restated so a citation of THIS
#: round cannot soften what its predecessor actually bought.
ROUND1_VERDICT = (
    "H-UNRESOLVED (2026-08-31, band 168e9, n=400 decks, ARB ON BOTH SEATS): "
    "M = +1.019 +/- 0.683, z +1.49, LB95 -0.346, UB95 +2.384, against the "
    "LB95 >= +1.0 ADOPT bar. ⛔⛔ NOT A NULL AND NOT A BOUND: round 1 bought NO "
    "verdict on the deployed configuration, did NOT discharge step 2 of the "
    "adoption chain, did NOT license step 3, and did NOT retract the "
    "arbiter-off +2.951. ⭐ Its §8.2 pre-committed the price of exactly that "
    "read BEFORE its game 1: the band is spent either way, the cell may NOT be "
    "extended / topped up / re-read at larger n on its own band (the rodv3 "
    "failure mode), and a re-run is A NEW ROUND needing a NEW PAIR, a NEW BAND "
    "CLAIM and FRESH OWNER FUNDING. ⭐⭐ THIS ROUND IS THAT, EXECUTED TO THE "
    "LETTER — new pair, new band (169e9), owner-funded 2026-08-31 night, and "
    "the bar UNMOVED."
)


# =========================================================================== #
# 1. THE CELL                                                                  #
# =========================================================================== #

@dataclass(frozen=True)
class CellSpec:
    """ONE cell = ONE band = ONE pooled read. ⛔ Nothing is pooled ACROSS BANDS
    in this round; there is nothing to pool it with (`CONTEXT_WARNING`).

    ⭐⭐ **WHAT *IS* POOLED, AND WHY THAT IS NOT THE SAME THING.** The cell's 800
    decks are executed as `N_CHUNKS` contiguous SUB-RANGES of ONE band, possibly
    on TWO boxes, and the read pools their raw records. That is a WITHIN-band,
    deck-paired pool — the exact class CL-068 leaves robust — and it is not a
    statistical combination of separate measurements at all: it is one
    measurement whose games were executed in pieces.

    ⚠️ `role` is the box FROZEN AT LAUNCH (the laptop). It is retained for the
    launcher's default and for the smoke, and it is ⛔ **NOT** a constraint the
    read enforces: `HOST_PROVENANCE` replaces round 1's box-voiding `G-HOST`.
    """
    name: str
    role: str                       #: the launch-time box. ⛔ PROVENANCE, not law
    knob: str                       #: "fpu_reduction"
    value: float                    #: `G-FPU`'s frozen expectation
    seed_start: int
    n_decks: int
    purpose: str
    #: ⭐ How many out-dirs this cell's decks are executed as. The frozen round
    #: uses `N_CHUNKS`; the selftest fixture uses a smaller count at a smaller
    #: scale so the sharding gates are exercised rather than merely defined; and
    #: ⚠️ `n_chunks == 1` means UNSHARDED — `chunk_name(0)` is then the cell name
    #: itself with NO suffix, which is exactly the shape the §9.2 smoke and the
    #: §9.3 IDENT legs emit. ⛔ The sharding gates still RUN in that case (they
    #: are trivially satisfied); nothing is special-cased away.
    n_chunks: int = N_CHUNKS

    @property
    def n_games(self) -> int:
        return self.n_decks * 2

    @property
    def seed_end(self) -> int:
        """INCLUSIVE last seed of this cell's own range."""
        return self.seed_start + self.n_decks - 1

    @property
    def decks_per_chunk(self) -> int:
        return self.n_decks // self.n_chunks

    def chunk_name(self, i: int) -> str:
        """The out-subdir of chunk `i`. ⭐ The chunk index is in the NAME, and
        the box is NOT — a chunk keeps its identity when it changes hands, and
        its manifest's `host` is the record of who played it."""
        if not 0 <= i < self.n_chunks:
            raise IndexError(f"chunk {i} outside 0..{self.n_chunks - 1}")
        return self.name if self.n_chunks == 1 else f"{self.name}__c{i}"

    def chunk_range(self, i: int) -> tuple[int, int]:
        """`(lo, hi)` INCLUSIVE deck seeds of chunk `i`."""
        if not 0 <= i < self.n_chunks:
            raise IndexError(f"chunk {i} outside 0..{self.n_chunks - 1}")
        lo = self.seed_start + i * self.decks_per_chunk
        return lo, lo + self.decks_per_chunk - 1

    def chunk_of_seed(self, seed: int) -> int | None:
        """Which chunk owns `seed`, or `None` if it is outside the band."""
        if not (self.seed_start <= seed <= self.seed_end):
            return None
        return (seed - self.seed_start) // self.decks_per_chunk

    def chunks_for_seed_range(self, lo: int, hi: int) -> list[int]:
        """The chunk indices a `[lo, hi]` INCLUSIVE seed range names.

        ⛔ RAISES unless the range is CHUNK-ALIGNED. `DESIGN.md` §6.4's
        flexible-box clause assigns whole chunks and nothing else: a half-chunk
        assignment would put two boxes' records inside one out-dir, and that dir
        emits exactly ONE `manifest.json` with exactly ONE `host` — so the
        provenance map would become a lie that no gate could see."""
        if lo > hi:
            raise ValueError(f"seed range [{lo},{hi}] is empty")
        if lo < self.seed_start or hi > self.seed_end:
            raise ValueError(f"seed range [{lo},{hi}] leaves the band "
                             f"[{self.seed_start},{self.seed_end}]")
        dpc = self.decks_per_chunk
        if (lo - self.seed_start) % dpc != 0 \
                or (hi - self.seed_start + 1) % dpc != 0:
            raise ValueError(
                f"seed range [{lo},{hi}] is NOT chunk-aligned "
                f"({dpc} decks per chunk from {self.seed_start}). "
                "DESIGN §6.4 assigns WHOLE CHUNKS: a partial chunk would put two "
                "boxes' records in one out-dir, which emits one manifest with "
                "one host, and the provenance map would silently become false.")
        return list(range((lo - self.seed_start) // dpc,
                          (hi - self.seed_start + 1) // dpc))

    @property
    def cand_fpu(self):
        """The candidate's RESOLVED fpu_reduction. `None` == the champion."""
        return self.value if self.knob == "fpu_reduction" else None

    @property
    def cand_c_puct(self):
        """⛔ ALWAYS `None`: this round varies `fpu_reduction` and nothing else,
        and `knob_gate` asserts the override is absent-as-null."""
        return self.value if self.knob == "c_puct" else None


#: ⭐ THE ONE CELL. n=1600 games = 800 seat-balanced decks × 2 seatings, on its
#: own fresh band, against the DEPLOYED champion (22016 + arbiter B=64), with the
#: dose on the candidate only. Executed as 8 chunks of 100 decks.
CELLS: tuple[CellSpec, ...] = (
    CellSpec(
        "CELL_H2H2_FPU02", "laptop", "fpu_reduction", 0.2, BAND, 800,
        "⭐⭐ STEP 2 OF `ADOPTION_CHAIN`, ROUND 2 — the PRODUCTION H2H at DOUBLE "
        "the n. Candidate = the production champion (k16x1376 = 22016) + the "
        "DEPLOYED tie arbiter (B=64, J=4, argmax, salt tiearb2-deploy-v1, eps "
        "0.0, phase_gate all) + `fpu_reduction = 0.2`. Opponent = THE SAME AGENT "
        "WITHOUT THE DOSE. ⭐ The single variable is the knob, measured in the "
        "configuration that actually ships. ⛔ ROUND 1 (band 168e9, n=400) read "
        "H-UNRESOLVED and its own §8.2 mandated a NEW round, NEW pair, NEW band, "
        "FRESH FUNDING — this is that round, with the bar UNMOVED and NOTHING "
        "POOLED across the two."),
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
    "2. ⭐⭐ THIS LEG — PRODUCTION H2H: the dose vs the DEPLOYED champion with "
    "the TIE ARBITER ARMED ON BOTH SEATS (B=64, PRODUCTION.yaml since "
    "2026-08-20), on a FRESH band. ⛔ THE LEG THAT PRICES THE ARBITER-OFF "
    "DEVIATION every earlier fpu reading carries. ⚠️ ROUND 1 (band 168e9, "
    "n=400) read H-UNRESOLVED and DISCHARGED NOTHING; THIS IS ROUND 2 (band "
    "169e9, n=800), a separate owner-funded round whose numbers stand alone.",
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


def host_role_strict(observed_host) -> str | None:
    """⭐⭐ **THE STRICT RESOLVER — AND IT EXISTS BECAUSE ROUND 2 FOUND A HOLE IN
    `host_matches_box`.**

    ⛔⛔ `host_matches_box(h, "local")` carries a CATCH-ALL: *"not the laptop ⇒
    treated as local"*. In round 1 that was harmless — the round was laptop-only
    and the gate voided anything that was not the laptop, so the catch-all was
    never consulted for an accept. In round 2 BOTH boxes are legal, and the
    catch-all would silently map ANY unrecognised host — a cloud node, a
    mistyped box, a second machine nobody planned — onto `local` and let its
    archive into the pool with a clean provenance line.

    ⚠️ It was caught by this round's own selftest defect
    `a_chunk_ran_on_an_UNFUNDED_box`, which fired `G-WHEEL-SAME` and NOT
    `G-HOST` — i.e. the wrong gate, for the wrong reason, by luck.

    ⭐ This resolver returns a role ONLY on an EXPLICIT alias hit, and `None`
    otherwise. `host_matches_box` is left exactly as round 1 froze it."""
    if not observed_host or not isinstance(observed_host, str):
        return None
    h = observed_host.strip().lower()
    for role, aliases in _HOST_ALIASES.items():
        if any(a in h for a in aliases):
            return role
    return None


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
    """`SIGMA_D_MODEL / sqrt(n)`. ⭐ 800 decks -> 0.4826 (the funded shape); 400
    decks -> 0.6825 (round 1's, which is where `SIGMA_D_MODEL` came from).
    ⛔ POWER ARITHMETIC ONLY — never a denominator in a branch test."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    """Print realized vs modelled SE and FLAG a ratio outside `SE_ANOMALY_BAND`.
    ⛔ Reported, NEVER a branch input.

    ⭐ IN ROUND 2 THE MODEL IS AN ARB-ON MEASUREMENT, NOT A STAND-IN: round 1
    realized `sigma_D = 13.6495` at this exact agent pair, so a ratio near 1.0 is
    now the EXPECTATION rather than a hope. ⚠️ It is still ⛔ NEVER a branch
    input — a wider realized SE costs POWER, never VALIDITY, and the branch uses
    the realized SE."""
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
                          "here, though LESS so than in round 1 — the model is "
                          "now round 1's own ARB-ON realization)"
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
    can afford the ADOPT direction against a LARGE effect while remaining blind
    to a small one — and it is computed, not asserted.

        H-ADOPT      M - 2se >= BAR   <=>  M >= BAR + 2se
        H-BOUNDED    M + 2se <  BAR   <=>  M <  BAR - 2se
        H-NEGATIVE   M <= 0 AND z <= -2  <=>  M <= -2se  (a SUBSET of BOUNDED,
                                                          checked first)
        H-UNRESOLVED the remainder
    """
    if se is None:
        se = se_model(CELLS[0].n_decks)
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
    ~396 DECKS, comfortably inside the funded 800 — the funded round is powered
    97.9% there. ⛔⛔ AND THE HONEST OTHER END: at `delta = +1.019` (ROUND 1's
    OWN POINT ESTIMATE) it is over four MILLION decks, so if the true effect is
    what round 1 measured, NO affordable round resolves it. `READ_RULE.md` §8
    prints both, before game 1."""
    z_p = _invphi(p_target)
    denom = z_p + 2.0
    if delta <= BAR_EFFECT or denom <= 0:
        return -1                          # unreachable at any n
    se = (delta - BAR_EFFECT) / denom
    return int(math.ceil((SIGMA_D_MODEL / se) ** 2))


def n_decks_for_bounded_power(p_target: float = 0.80) -> int:
    """The mirror image: how many decks to read `H-BOUNDED` with probability
    `p_target` under a TRUE NULL? Solve `Phi((BAR - 2se)/se) = p_target`.

    ⚠️ ~1,505 decks — 1.9x the funded 800. ⭐ Doubling `n` bought a real
    improvement here (a true null now reads `H-BOUNDED` 50.6% of the time, up
    from round 1's 27.4%) but it is still a COIN FLIP, not a verdict, and
    `READ_RULE.md` §8 states that before game 1."""
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
                        "READ_RULE §8 pre-registers its probability at n=800 "
                        "(~47% under a true null; ~95% if the true effect is "
                        "round 1's own +1.019), §8.2 pre-commits its price, and "
                        "§8.3 pre-commits that a SECOND unresolved read closes "
                        "the axis on affordability rather than funding round "
                        "3."}[v]}


def branch_grid(step: float = 0.05,
                se_values=(0.3, 0.4826, 0.5, 0.683, 0.9, 1.4)) -> dict:
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
    "⛔⛔ EVERY CONTEXT ROW IS ON ANOTHER BAND AND NONE IS EVER POOLED OR "
    "z-COMBINED WITH THIS CELL — INCLUDING ROUND 1's. Six are arbiter-OFF (a "
    "different AGENT PAIR on top of a different band); the seventh is round 1 of "
    "this same H2H at band 168e9, which is the SAME agent pair and is therefore "
    "the row most at risk of being averaged in. ⛔ IT MAY NOT BE. CL-068 "
    "measured 1.8-2.2x over-dispersion on merely cross-band contrasts in BOTH "
    "statistics, and round 1's own READ_RULE §8.2 pre-committed that its cell "
    "could not be pooled with an extension anyway. THIS ROUND IS 800 FRESH "
    "DECKS, NOT 400 + 400.",
    "⭐⭐ BOX ASSIGNMENT IS THROUGHPUT-ONLY AND WAS PRE-REGISTERED AS MOVABLE "
    "MID-ROUND (DESIGN §6.4). The 800 decks are executed as 8 chunks of 100 that "
    "TILE the band; a chunk is the unit of box assignment and of provenance; "
    "G-NODUP proves the realized ranges are disjoint and every (deck, seat) "
    "appears exactly once; G-HOST publishes the chunk -> host -> range map and "
    "voids on NOTHING about which box played what. ⛔ NO CROSS-BOX STATISTIC "
    "EXISTS: both seatings of every deck are played inside one chunk on one box, "
    "so the box is COMMON TO BOTH ARMS of every contrast and cross-box float "
    "identity is not relied on anywhere. Cross-box SOURCE identity is required "
    "and is G-REV's (cross_box_rev_gate, the IS-A1 fold).",
    "⛔ governance/PRODUCTION.yaml is UNTOUCHED on every branch. H-ADOPT "
    "licenses PROPOSING the flip and funding step 3; the flip itself needs an "
    "OWNER RULING, exactly as the k16 and B=64 folds did.",
    "⭐ THE ARBITER IS ARMED ON BOTH SEATS AT THE FULL DEPLOYED SPEC (B=64, J=4, "
    "argmax, salt tiearb2-deploy-v1, eps 0.0, phase_gate all). Its rollout "
    "variance therefore rides BOTH arms and CRN deck-pairing absorbs the deck "
    "draw as usual — but the arbiter is STOCHASTIC, so it is a variance source "
    "round 1 measured directly: sigma_D 13.6495, INSIDE the arb-off siblings' "
    "13.02-14.30 spread (DESIGN §3.1).",
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
    "seats result on ONE fresh band, executed on ONE OR TWO BOXES. Every one of "
    "those is part of the claim; the box split is provenance and is published in "
    "G-HOST's map.",
    "⚠️ TYPE-M RIDER. The funded n=800 decks is powered ~98% against a REPEAT of "
    "the incumbent's +2.951, ~53% at a true +2.0, ~39% at the ladder's largest "
    "point estimate (+1.835) and only ~2.5% at ROUND 1's OWN point estimate "
    "(+1.019). ⛔ THE SMALLEST TRUE EFFECT THIS ROUND ADOPTS AT EVEN COIN-FLIP "
    "ODDS IS +1.97 pts/deck. A cell that adopts near the bar therefore has a "
    "MAGNITUDE biased upward; the SIGN is the reliable part. This is the same "
    "rider the k16 fold carries and it travels with every citation.",
)
RIDERS_H_BOUNDED = (
    BOUNDED_CONSEQUENCE,
    "⚠️ H-BOUNDED BOUNDS; IT DOES NOT ZERO. The reading is 'below +1.0 pts/deck "
    "at 95%', never 'this dose is worthless' — a cell can read H-BOUNDED "
    "carrying a POSITIVE point estimate.",
    "⚠️ THE BOUNDING DIRECTION IS A COIN FLIP, NOT A VERDICT ENGINE: under a "
    "true null this branch fires ~50.6% of the time at n=800 (READ_RULE §8) — "
    "roughly DOUBLE round 1's ~27%, which is most of what doubling n bought. A "
    "realized H-BOUNDED is therefore a stronger statement than its probability "
    "suggests, and its ABSENCE remains a much weaker one.",
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
    "license proposing the PRODUCTION.yaml flip. READ_RULE §8 pre-registers its "
    "probability at n=800 with the +1.0 bar (~47% under a true null; ~95% if the "
    "true effect is round 1's own +1.019) and §8.2 pre-registers its price.",
    "⛔ THE CELL MAY NOT BE EXTENDED, TOPPED UP OR RE-READ AT LARGER n ON ITS "
    "OWN BAND. That is the rodv3 failure mode (n bought after seeing the sign), "
    "and CL-068 means the extension could not be pooled with the original "
    "anyway. A re-run is a NEW round: new pair, new band, new owner funding.",
    "⛔⛔ AND A SECOND UNRESOLVED READ IS NOT A LICENCE TO KEEP BUYING ROUNDS. "
    "Round 1 read H-UNRESOLVED at n=400; this round doubled n and READ_RULE §8.3 "
    "states, BEFORE game 1, what a second one means: the axis is bounded above "
    "by what the program can afford, not by what it has measured, and the honest "
    "next act is to say so in docs/LEVER_INDEX.md and STOP — not to fund round 3 "
    "at n=1600. Escalating n after each unresolved read is the rodv3 failure "
    "mode wearing a new band each time.",
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
          FRACTION, never an equality, and a BACKSTOP: at 800 decks the 80%
          floor allows 160 lost decks while the 2% bar voids at 32 games.
      (d) ⛔ HARD FAIL — this cell's range intersects another cell's. ⚠️ With
          ONE cell the clause is vacuous by arithmetic; it is CARRIED rather
          than deleted so a future fork that adds a second cell inherits it
          armed. `sanity_check()` asserts the range is disjoint from the
          THROWAWAY block, which is the live version of the same worry.

    ⚠️⚠️ **ROUND 2: `records` IS THE POOL, ACROSS EVERY CHUNK.** This gate reads
    the band, not the chunks — a seed inside the band but outside its own CHUNK's
    sub-range is `G-NODUP`'s business, and a chunk that never ran is
    `G-CHUNKS`'. All three are needed and none subsumes another.
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

    ⚠️⚠️ **ROUND 2: `n` AND `n_failed` ARE SUMS OVER EVERY CHUNK'S OWN
    `summary.json`.** ⭐⭐ THE ACCOUNTING IDENTITY THEREFORE DOES DOUBLE DUTY AND
    IT IS THE FLEXIBLE-BOX CLAUSE'S TILING CHECK: `sum(n) + sum(n_failed) ==
    1600` can only hold if the chunks' assigned ranges COVER THE WHOLE BAND. A
    two-box split that left a hole — the realistic orchestrator error when the
    remainder is computed by hand — fails HERE, loudly, instead of producing a
    short pool that reads like a complete round. ⛔ It is a HARD fail and is NOT
    absorbed by the 2% bar: games that vanished without being recorded as
    failures mean the denominator is unknown.
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


# --------------------------------------------------------------------------- #
# ⭐⭐ THE SHARDING GATES — WHAT THE FLEXIBLE-BOX CLAUSE COSTS IN RIGOUR        #
# --------------------------------------------------------------------------- #
# ⛔⛔ THE CLAUSE IS NOT FREE AND THESE THREE GATES ARE THE PRICE, PRE-REGISTERED
# BEFORE GAME 1. Round 1 was ONE archive on ONE box, so "is this one cell?" was
# answered by the filesystem. Round 2 may be up to 8 archives on 2 boxes, and
# three propositions that used to be free must now be PROVEN:
#
#   G-CHUNKS       every chunk of the band EXISTS and is COMPLETE (manifest AND
#                  summary). ⛔ A chunk killed mid-flight has a manifest and NO
#                  summary; ABSENT is FAIL and the fix is to RESUME it, never to
#                  read around it.
#   G-NODUP        the chunks' realized seed ranges are pairwise DISJOINT and
#                  every (deck, seat) appears EXACTLY ONCE across the pool.
#   G-SHARD-IDENT  every chunk resolved the SAME AGENTS. ⛔ Pooling chunks that
#                  ran different configs is pooling different measurements, and
#                  no per-chunk gate can see it.
#
# ⭐ AND WHAT IS **NOT** NEEDED, STATED SO THE ABSENCE IS DELIBERATE:
# CROSS-BOX FLOAT IDENTITY IS NOT RELIED ON ANYWHERE IN THIS ROUND. No statistic
# here differences a quantity computed on one box against one computed on
# another. The primary is `D(deck) = (diff(a_seat=0) + diff(a_seat=1)) / 2`, and
# BOTH seatings of every deck are played inside ONE chunk on ONE box — so the box
# is a factor COMMON TO BOTH ARMS of every contrast that enters the statistic and
# cannot bias candidate-minus-opponent. A box difference could only add
# between-deck dispersion, which the realized SE already prices. ⛔ What IS
# required across boxes is SOURCE identity, and that is `G-REV`'s
# `cross_box_rev_gate` (the IS-A1 fold), which canonicalizes every emitted rev to
# ONE 40-hex pin and NEVER compares one box's short rev to another's.
# ⚠️ `carc_rs_binary_sha` is BOX-LOCAL by construction (two boxes compiling
# identical source produce different bytes), so `G-WHEEL-SAME` is asserted
# WITHIN each box and is REPORTED across them.

def chunk_plan(spec: CellSpec) -> list[dict]:
    """The frozen chunk table: index, out-subdir, INCLUSIVE seed range, games."""
    out = []
    for i in range(spec.n_chunks):
        lo, hi = spec.chunk_range(i)
        out.append({"chunk": i, "name": spec.chunk_name(i), "seed_lo": lo,
                    "seed_hi": hi, "n_decks": spec.decks_per_chunk,
                    "n_games": spec.decks_per_chunk * 2})
    return out


def chunks_gate(spec: CellSpec, shards: Mapping[str, Mapping]) -> dict:
    """⛔⛔ `G-CHUNKS` — the band is COMPLETELY covered by COMPLETE chunks.

    `shards` is `{chunk_dir_name: {"manifest": ..., "summary": ..., "records":
    [...]}}` exactly as the adjudicator loaded it.

      ⛔ HARD FAIL — a frozen chunk dir is missing entirely (ABSENT is FAIL).
      ⛔ HARD FAIL — a chunk has no `manifest.json` (it never started).
      ⛔ HARD FAIL — a chunk has no `summary.json`. ⚠️ THIS IS THE
         FLEXIBLE-BOX CLAUSE'S OWN FAILURE MODE, NAMED: `eval_fair_puct` writes
         the manifest at run START and the summary at run END, so a chunk that
         was KILLED (which is exactly what adding a box does to the laptop's
         in-flight chunk) has the first and not the second. ⭐ THE FIX IS TO
         RESUME THAT CHUNK — its per-game records are on disk and the harness
         cached-skips them, so the resume costs only the unplayed games. ⛔ It is
         NOT to read around it: a chunk with no summary has no `RECON` witness,
         no `G-TIEARB-FIRE` aggregate and no `n_failed` accounting.
      ⛔ HARD FAIL — a chunk dir that is NOT in the frozen plan.
    """
    plan = {c["name"]: c for c in chunk_plan(spec)}
    hard, rows = [], {}
    for name, c in plan.items():
        sh = shards.get(name)
        if sh is None:
            hard.append(f"{name} ABSENT — the chunk produced no archive")
            rows[name] = {"present": False}
            continue
        has_man = bool(sh.get("manifest"))
        has_sum = bool(sh.get("summary"))
        rows[name] = {"present": True, "manifest": has_man, "summary": has_sum,
                      "n_records": len(sh.get("records") or []),
                      "seed_range": [c["seed_lo"], c["seed_hi"]]}
        if not has_man:
            hard.append(f"{name}: manifest.json ABSENT — the chunk never started")
        if not has_sum:
            hard.append(
                f"{name}: summary.json ABSENT — the chunk was KILLED mid-flight "
                "(the harness writes the manifest at START and the summary at "
                "END). ⭐ RESUME THIS CHUNK; its records are cached and the "
                "resume costs only the unplayed games. ⛔ Do NOT read around it.")
    extra = sorted(set(shards) - set(plan))
    if extra:
        hard.append(f"chunk dir(s) not in the frozen plan: {extra}")
    return gate("G-CHUNKS", not hard,
                {"frozen_chunks": list(plan), "by_chunk": rows,
                 "unexpected_dirs": extra},
                "the chunk out-dirs under the round's out-root",
                ("⭐ all %d frozen chunks are present and COMPLETE "
                 "(manifest AND summary)" % spec.n_chunks if not hard
                 else "⛔ G-CHUNKS FAILED: " + "; ".join(hard)))


def nodup_gate(spec: CellSpec, shards: Mapping[str, Mapping]) -> dict:
    """⭐⭐ `G-NODUP` — **THE FLEXIBLE-BOX CLAUSE'S OWN GATE.**

      ⛔ HARD FAIL — any two chunks' realized deck-seed sets INTERSECT. Two
         boxes handed OVERLAPPING ranges would play the same decks twice, and
         the pooled mean would silently over-weight them.
      ⛔ HARD FAIL — any `(deck, a_seat)` pair appears more than once across the
         pool. ⚠️ This is STRICTLY STRONGER than the range check and it is the
         clause that actually binds: records are keyed by `(seed, a_seat)` inside
         a dir, so a duplicate can only arise ACROSS dirs — which is exactly the
         defect a mis-typed `--seed-lo` on the second box would produce.
      ⛔ HARD FAIL — a realized chunk's seeds escape THAT CHUNK's own frozen
         sub-range. (`G-DECKS` checks the band; this checks the chunk.)
      ⛔ HARD FAIL — a chunk realized ZERO records. An empty chunk in a complete
         round means the range was never actually assigned.
      ⛔ HARD FAIL — a shard that is not in the frozen chunk plan, or a POOL
         with no records at all. ⚠️ Both are ANTI-VACUITY clauses and both were
         added because the selftest caught this gate PASSING on an empty
         archive: "no duplicates among zero records" is true and meaningless,
         which is the IS-D1 class of defect.
    """
    plan = {c["name"]: c for c in chunk_plan(spec)}
    seen: dict[tuple[int, int], list[str]] = {}
    seeds_by_chunk: dict[str, set] = {}
    hard = []
    for name, sh in sorted(shards.items()):
        c = plan.get(name)
        if c is None:
            hard.append(f"{name} is NOT in the frozen chunk plan — this gate "
                        "cannot reason about a shard the plan does not name")
        seeds_by_chunk[name] = set()
        for r in (sh.get("records") or []):
            if not isinstance(r, Mapping):
                continue
            s, a = r.get("seed"), r.get("a_seat")
            if s is None or a is None:
                continue
            s, a = int(s), int(a)
            seeds_by_chunk[name].add(s)
            seen.setdefault((s, a), []).append(name)
            if c and not (c["seed_lo"] <= s <= c["seed_hi"]):
                hard.append(f"{name}: seed {s} is outside that chunk's own "
                            f"range [{c['seed_lo']},{c['seed_hi']}]")
        if c is not None and not seeds_by_chunk[name]:
            hard.append(f"{name}: ZERO records — the chunk's range was never "
                        "actually played by anyone")
    dups = {f"seed{ s }_a{ a }": v for (s, a), v in sorted(seen.items())
            if len(v) > 1}
    if dups:
        hard.append(f"⛔⛔ {len(dups)} (deck, seat) pair(s) appear in MORE THAN "
                    f"ONE chunk: {dict(list(dups.items())[:5])} — the boxes were "
                    "handed OVERLAPPING ranges and the pooled mean would "
                    "over-weight those decks")
    overlaps = []
    names = sorted(seeds_by_chunk)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            inter = seeds_by_chunk[a] & seeds_by_chunk[b]
            if inter:
                overlaps.append({"chunks": [a, b], "n_shared_decks": len(inter),
                                 "example": sorted(inter)[:5]})
    if overlaps:
        hard.append(f"realized chunk ranges INTERSECT: {overlaps[:3]}")
    total = sum(len(v) for v in seeds_by_chunk.values())
    union = len(set().union(*seeds_by_chunk.values())) if seeds_by_chunk else 0
    if not union:
        hard.append("⛔ THE POOL CARRIES NO RECORDS AT ALL — 'no duplicates "
                    "among zero records' is true and meaningless. ABSENT is "
                    "FAIL, never a vacuous pass.")
    return gate(
        "G-NODUP", not hard,
        {"n_chunks_seen": len(seeds_by_chunk),
         "decks_per_chunk_realized": {k: len(v) for k, v in
                                      sorted(seeds_by_chunk.items())},
         "sum_of_chunk_deck_counts": total, "union_deck_count": union,
         "duplicate_deck_seat_pairs": dict(list(dups.items())[:20]),
         "n_duplicate_deck_seat_pairs": len(dups),
         "range_overlaps": overlaps[:5]},
        "the pooled raw seed*_a*.json across every chunk dir",
        ("⭐ the chunks TILE the band: their realized ranges are pairwise "
         "disjoint, every (deck, seat) appears EXACTLY ONCE across the pool, and "
         "no chunk's seeds escape its own sub-range" if not hard
         else "⛔ G-NODUP FAILED: " + "; ".join(hard)))


#: The resolved-config addresses `G-SHARD-IDENT` compares across chunks.
#: ⛔ `host`, `code_rev`, `carc_rs_binary_sha`, `utc` and the per-chunk band
#: fields are DELIBERATELY ABSENT: they are EXPECTED to differ between boxes and
#: between chunks, and a clause over them would void every healthy two-box round.
SHARD_IDENT_ADDRESSES = (
    "config.cand_search.fpu_reduction",
    "config.cand_search.c_puct",
    "config.champion.fpu_reduction",
    "config.champion.c_puct",
    "config.champion.tau_p",
    "config.champion.k_dets",
    "config.champion.sims_per_det",
    "config.champion.total_sims",
    "config.opponent.champ_cfg.fpu_reduction",
    "config.opponent.champ_cfg.c_puct",
    "config.opponent.champ_cfg.tau_p",
    "config.cand_leaf_hash",
    "config.opp_leaf_hash",
    "config.endgame.exact_k",
    "config.endgame.mode",
    "config.backend.name",
    "rules_profile.name",
)


def shard_ident_gate(shards: Mapping[str, Mapping]) -> dict:
    """⭐⭐ `G-SHARD-IDENT` — **EVERY CHUNK RESOLVED THE SAME TWO AGENTS.**

    ⛔⛔ THE DEFECT THIS CLOSES IS INVISIBLE TO EVERY OTHER GATE. Each per-chunk
    config gate (`G-FPU`, `G-BUDGET`, `G-LEAF`, …) checks a chunk against the
    FROZEN constants and passes. But a resolved value that is not in any frozen
    table — or a chunk launched from a stale `WORKERS.conf` on the second box —
    can differ between chunks while every chunk still passes its own gates. ⛔
    Pooling those chunks pools two different measurements. This gate compares the
    chunks TO EACH OTHER.

    ⚠️ `MISSING` is compared as a distinct value, so an address present on one
    chunk and absent on another is a FAIL rather than a silent skip.

    ⛔⛔ **AND AN ADDRESS THAT IS ABSENT ON *EVERY* CHUNK IS ALSO A FAIL** — an
    ANTI-VACUITY clause, added because the selftest caught this gate PASSING on
    an empty archive: chunks that agree because none of them says anything agree
    about nothing, which is exactly the IS-D1 defect. Every address in
    `SHARD_IDENT_ADDRESSES` is present in a real emitted manifest (several of
    them as an explicit `null`, which is a POSITIVE statement and resolves).
    """
    docs = {n: {"manifest": (sh.get("manifest") or {})}
            for n, sh in sorted(shards.items())}
    rows, hard = {}, []
    for addr in SHARD_IDENT_ADDRESSES:
        vals = {}
        for n, d in docs.items():
            v, _ = resolve(d, f"manifest:{addr}")
            vals[n] = "<ABSENT>" if v is MISSING else v
        distinct = {json.dumps(v, sort_keys=True, default=str)
                    for v in vals.values()}
        rows[addr] = {"by_chunk": vals, "n_distinct": len(distinct)}
        if len(distinct) > 1:
            hard.append(f"{addr} DIFFERS across chunks: {vals}")
        elif all(v == "<ABSENT>" for v in vals.values()):
            hard.append(f"{addr} is ABSENT on EVERY chunk — chunks that agree "
                        "because none of them states the value agree about "
                        "nothing. ABSENT is FAIL.")
    # ⚠️ The arbiter dict for BOTH seats, compared whole rather than key by key —
    # a per-key comparison would let a chunk with a MISSING container pass.
    for label, addrs in (("cand_tiearb", ("config.cand_tiearb", "cand_tiearb")),
                         ("opp_tiearb", ("config.opp_tiearb", "opp_tiearb",
                                         "config.opponent.tiearb"))):
        vals = {}
        for n, d in docs.items():
            v, _ = resolve(d, *[f"manifest:{a}" for a in addrs])
            vals[n] = "<ABSENT>" if v is MISSING else v
        distinct = {json.dumps(v, sort_keys=True, default=str)
                    for v in vals.values()}
        rows[label] = {"by_chunk": vals, "n_distinct": len(distinct)}
        if len(distinct) > 1:
            hard.append(f"the resolved {label} dict DIFFERS across chunks: {vals}")
        elif all(v == "<ABSENT>" for v in vals.values()):
            hard.append(f"the resolved {label} dict is ABSENT on EVERY chunk — "
                        "ABSENT is FAIL, never a vacuous agreement")
    return gate("G-SHARD-IDENT", not hard and bool(docs), rows,
                "manifest:<the resolved-config addresses>, CHUNK vs CHUNK",
                ("⭐ every chunk resolved the SAME candidate and the SAME "
                 "opponent — the pool is ONE measurement executed in pieces, not "
                 "several measurements combined" if not hard and docs
                 else "⛔ G-SHARD-IDENT FAILED: "
                      + ("; ".join(hard) or "no chunk archives at all")))


def host_provenance_gate(spec: CellSpec, shards: Mapping[str, Mapping]) -> dict:
    """⭐⭐ `G-HOST` — **PROVENANCE-ONLY IN ROUND 2, AND THAT IS A DELIBERATE
    DOWNGRADE FROM ROUND 1.**

    Round 1 was LAPTOP-ONLY (the owner held the local box) and its `G-HOST`
    VOIDED a cell that ran anywhere else. ⛔ THAT CLAUSE IS GONE HERE, ON PURPOSE:
    `DESIGN.md` §6.4 pre-registers box assignment as THROUGHPUT-ONLY and
    explicitly permits it to change MID-ROUND. A gate that voided on the box
    would make the owner's own funded flexibility unusable.

    ⚠️ What it still does, and what it can still FAIL on:

      ⛔ HARD FAIL — a chunk's manifest carries NO `host`. That does not void the
         *statistic*; it destroys the *provenance map*, and "which box played
         which range" is a question this round pre-committed to answering.
      ⛔ HARD FAIL — a chunk's `host` is not one of this round's two funded
         boxes. An archive from an unfunded box is an archive nobody planned,
         and the rev/wheel story for it does not exist.
      ⭐ REPORTED — the map itself: chunk -> host -> role -> realized seed range.

    ⛔ THERE IS NO CLAUSE ON *WHICH* BOX PLAYED *WHICH* CHUNK, AND NONE ON THE
    SPLIT RATIO. Any tiling is legal. The read pools all records on the one band.
    """
    plan = {c["name"]: c for c in chunk_plan(spec)}
    rows, hard = {}, []
    for name, sh in sorted(shards.items()):
        man = sh.get("manifest") or {}
        host = man.get("host")
        seeds = sorted({int(r["seed"]) for r in (sh.get("records") or [])
                        if isinstance(r, Mapping) and r.get("seed") is not None})
        # ⛔ STRICT: an explicit alias hit or nothing. host_matches_box's
        # "not the laptop ⇒ local" catch-all would launder an UNFUNDED box into
        # a clean provenance line (see host_role_strict).
        role = host_role_strict(host)
        rows[name] = {"host": host, "role": role,
                      "frozen_range": ([plan[name]["seed_lo"],
                                        plan[name]["seed_hi"]]
                                       if name in plan else None),
                      "realized_range": [seeds[0], seeds[-1]] if seeds else None,
                      "n_decks_realized": len(seeds)}
        if not host:
            hard.append(f"{name}: manifest carries NO host — ABSENT is FAIL. The "
                        "statistic survives, but the provenance map this round "
                        "pre-committed to publishing does not.")
        elif role is None:
            hard.append(f"{name}: host {host!r} is not one of this round's "
                        f"funded boxes {list(ROLES)}")
    by_role: dict[str, list] = {}
    for name, r in rows.items():
        by_role.setdefault(str(r["role"]), []).append(name)
    return gate("G-HOST", not hard and bool(rows),
                {"provenance_map": rows, "chunks_by_role": by_role,
                 "note": "⭐ PROVENANCE-ONLY. Box assignment is THROUGHPUT-ONLY "
                         "(DESIGN §6.4) and may change mid-round; no bar, gate "
                         "or branch reads it. G-NODUP owns the proposition that "
                         "the ranges did not overlap."},
                "manifest:host, per chunk",
                ("⭐ every chunk names a funded box and the chunk -> host -> "
                 "range map is complete" if not hard and rows
                 else "⛔ G-HOST FAILED: "
                      + ("; ".join(hard) or "no chunk archives at all")))


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
    if c0.n_decks != 800 or c0.n_games != 1600:
        p.append(f"{c0.name} is {c0.n_decks} decks / {c0.n_games} games; the "
                 "funded shape is 800 decks / 1600 games")
    if c0.role not in ROLES:
        p.append(f"{c0.name}'s launch-time box {c0.role!r} is not one of the "
                 f"funded boxes {list(ROLES)}")
    # --- ⭐⭐ THE CHUNKING TILES THE BAND, EXACTLY ---------------------------
    if c0.n_chunks != N_CHUNKS or c0.decks_per_chunk != DECKS_PER_CHUNK:
        p.append(f"the cell is {c0.n_chunks} x {c0.decks_per_chunk} decks; "
                 f"WORKERS.conf and DESIGN §6.3 freeze {N_CHUNKS} x "
                 f"{DECKS_PER_CHUNK}")
    if N_CHUNKS * DECKS_PER_CHUNK != c0.n_decks:
        p.append(f"{N_CHUNKS} chunks x {DECKS_PER_CHUNK} decks != the cell's "
                 f"{c0.n_decks} decks — the chunks MUST tile the band exactly, "
                 "or G-N's accounting identity can never hold")
    covered: set[int] = set()
    for row in chunk_plan(c0):
        rng = set(range(row["seed_lo"], row["seed_hi"] + 1))
        if covered & rng:
            p.append(f"chunk {row['name']} overlaps an earlier chunk")
        covered |= rng
    if covered != set(range(c0.seed_start, c0.seed_end + 1)):
        p.append("the chunk plan does not exactly cover the band's deck range")
    try:
        if c0.chunks_for_seed_range(*c0.chunk_range(0)) != [0]:
            p.append("chunks_for_seed_range does not round-trip chunk 0")
        if c0.chunks_for_seed_range(c0.seed_start, c0.seed_end) \
                != list(range(N_CHUNKS)):
            p.append("chunks_for_seed_range does not round-trip the whole band")
    except Exception as e:                                    # noqa: BLE001
        p.append(f"chunks_for_seed_range raised on a legal range: {e!r}")
    # ⛔ and it MUST refuse a half-chunk assignment — the provenance-lie defect
    try:
        c0.chunks_for_seed_range(c0.seed_start, c0.seed_start + 1)
        p.append("chunks_for_seed_range ACCEPTED a non-chunk-aligned range — "
                 "DESIGN §6.4 assigns WHOLE CHUNKS, because a partial chunk puts "
                 "two boxes' records in one out-dir that emits ONE manifest with "
                 "ONE host, and the provenance map becomes a silent lie")
    except ValueError:
        pass
    if set(SMOKE_OFFSETS) != set(ROLES) or set(IDENT_OFFSETS) != set(ROLES):
        p.append("every funded box needs its OWN throwaway smoke/ident offset, "
                 "or one box's smoke could stand in for the other's")
    if len(set(SMOKE_OFFSETS.values())) != len(ROLES) \
            or len(set(IDENT_OFFSETS.values())) != len(ROLES):
        p.append("two boxes share a throwaway offset")
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
                  167_000_000_000,
                  # ⛔⛔ ROUND 1's OWN BAND. A round-2 fork that forgot to move
                  # the band would silently re-play 168e9 and its records would
                  # land beside round 1's in the same seed space.
                  168_000_000_000):
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
    r1 = ARB_ON_SIBLING[
        "fpu_h2h ROUND 1 / CELL_H2H_FPU02 (b168e9, n=400 decks, ⭐ ARB ON BOTH SEATS)"]
    if abs(SIGMA_D_MODEL - r1["implied_sigma_D"]) > 5e-4:
        p.append(f"SIGMA_D_MODEL {SIGMA_D_MODEL} is not round 1's OWN realized "
                 f"dispersion {r1['implied_sigma_D']:.4f} — the sizing constant "
                 "of this round is the ONLY arbiter-on-both-seats measurement "
                 "in existence, and it must not silently revert to the arb-off "
                 "13.81 stand-in")
    if abs(se_model(800) - 0.4826) > 5e-4:
        p.append(f"se_model(800) = {se_model(800):.4f}, DESIGN §3 says 0.4826")
    if abs(se_model(400) - r1["realized_se"]) > 5e-4:
        p.append("se_model(400) no longer reproduces round 1's realized se — "
                 "the model IS that measurement and the two must agree by "
                 "construction")
    # --- ⭐⭐ THE BAR IS AN EFFECT SIZE, NOT 2 sigma-hat --------------------
    # ⛔⛔ ROUND 2 REPLACES ROUND 1's NUMERIC COLLISION TEST WITH A PROVENANCE
    # TEST PLUS A MANDATORY DISCLOSURE, AND THE REASON IS ON THE RECORD IN
    # `BAR_COINCIDENCE_AT_FUNDED_N`: at 800 decks `2*se_model` = 0.9652 and the
    # frozen bar is 1.0, so the numeric test FIRES — but the owner's ruling is
    # about how a bar is CHOSEN, and this one was chosen in round 1 from two
    # realized production folds and is carried verbatim. Moving it after seeing
    # round 1's M = +1.019 would be the worse sin. ⭐ So the assertion becomes:
    # the bar is the frozen literal, the collision is DISCLOSED with correct
    # arithmetic, and the pathology it implies is PRICED in the read
    # distribution below.
    two_sig = 2 * se_model(c0.n_decks)
    disc = BAR_COINCIDENCE_AT_FUNDED_N
    if abs(disc["two_sigma_hat_at_funded_n"] - two_sig) > 5e-4:
        p.append("BAR_COINCIDENCE_AT_FUNDED_N.two_sigma_hat_at_funded_n "
                 f"{disc['two_sigma_hat_at_funded_n']} != the computed "
                 f"{two_sig:.4f} — the disclosure must carry the real number")
    if disc["bar"] != BAR_EFFECT:
        p.append("BAR_COINCIDENCE_AT_FUNDED_N.bar has drifted from BAR_EFFECT")
    if abs(disc["ratio_bar_over_2sigmahat"] - BAR_EFFECT / two_sig) > 5e-3:
        p.append("BAR_COINCIDENCE_AT_FUNDED_N.ratio_bar_over_2sigmahat is wrong")
    if abs(BAR_EFFECT - two_sig) < 0.05 and "consequence" not in disc:
        p.append("the bar has collided with 2 sigma-hat and the collision is "
                 "NOT disclosed — ⛔ the house rule (owner 2026-08-30) requires "
                 "the consequence to be stated before game 1")
    # ⛔ and the consequence itself must be TRUE, not merely written down: the
    # bounding branch must in fact require a near-zero point estimate.
    bounded_needs = BAR_EFFECT - two_sig
    if not (0.0 < bounded_needs < 0.10):
        p.append(f"H-BOUNDED requires M < {bounded_needs:+.3f}; "
                 "BAR_COINCIDENCE_AT_FUNDED_N states +0.034 and the disclosure "
                 "must match the arithmetic")
    # ⛔⛔ AND IT MUST BE ROUND 1's BAR, UNMOVED. A successor round that softened
    # its bar after seeing its predecessor's M = +1.019 would be choosing a bar
    # from the data, which is the one thing the apparatus exists to prevent.
    if BAR_EFFECT != 1.0:
        p.append(f"BAR_EFFECT {BAR_EFFECT} is not round 1's +1.0. ⛔ ROUND 2 "
                 "CARRIES ROUND 1's BAR VERBATIM; moving it after an "
                 "H-UNRESOLVED read would be a bar chosen from the data.")
    r1row = CONTEXT_ROWS["⭐⭐ fpu=0.2 — fpu_h2h ROUND 1 CELL_H2H_FPU02, "
                         "band 168e9, ARB ON BOTH SEATS"]
    if branch_for_cell(r1row["M"], r1row["se"], r1row["z"],
                       gates_ok=True) != "H-UNRESOLVED":
        p.append("round 1's own realized numbers no longer read H-UNRESOLVED "
                 "under this round's frozen ladder — the two rounds share a bar "
                 "and a branch table, and a divergence means one of them moved")
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
    elo_2s_paired = 2.0 * elo_sigma_paired(0.5, c0.n_games)
    if abs(ELO_RESOLUTION_2SIGMA - elo_2s_paired) > 0.05:
        p.append(f"ELO_RESOLUTION_2SIGMA {ELO_RESOLUTION_2SIGMA} is not the "
                 f"DECK-PAIRED 2-sigma resolution {elo_2s_paired:.4f} at "
                 f"{c0.n_games} games / {c0.n_decks} decks (the UNPAIRED figure "
                 f"is {2 * elo_sigma_unpaired(0.5, c0.n_games):.4f} — R4's fix)")
    if abs(PAIRING_FACTOR - 0.7071) > 1e-4:
        p.append(f"PAIRING_FACTOR {PAIRING_FACTOR} is not 1/sqrt(2)")
    if "elo" in branch_for_cell.__code__.co_varnames:
        p.append("branch_for_cell has taken an elo argument — elo may NEVER be "
                 "a branch input (READ_RULE §1.1)")
    # --- ⭐⭐ THE READ DISTRIBUTION, ASSERTED AT THE FUNDED n ---------------
    # ⛔ Every figure below is COMPUTED by read_distribution and pinned here, so
    # the round cannot quietly improve its own advertised odds. READ_RULE §8
    # prints the same table.
    se0 = se_model(c0.n_decks)
    null = read_distribution(0.0, se0)
    if not (0.44 <= null["H-UNRESOLVED"] <= 0.50):
        p.append("the true-null H-UNRESOLVED probability is "
                 f"{null['H-UNRESOLVED']:.3f}; READ_RULE §8 states ~0.471")
    if not (0.50 <= null["P(bounded below the bar)"] <= 0.56):
        p.append("the true-null bounded probability moved away from READ_RULE "
                 f"§8's ~0.529: {null['P(bounded below the bar)']:.3f}")
    if not (0.0 <= null["H-ADOPT"] <= 0.0005):
        p.append("the true-null FALSE-ADOPT probability moved away from "
                 f"READ_RULE §8's ~0.002%: {null['H-ADOPT']:.6f}")
    at_bar = read_distribution(BAR_EFFECT, se0)
    if not (0.92 <= at_bar["H-UNRESOLVED"] <= 0.98):
        p.append("the AT-THE-BAR H-UNRESOLVED probability moved away from "
                 f"READ_RULE §8's ~0.954: {at_bar['H-UNRESOLVED']:.3f}")
    # ⛔⛔ THE ROUND'S OWN MOST IMPORTANT DISCLOSURE: at round 1's own point
    # estimate this round is essentially BLIND, and that is asserted, not hoped.
    at_r1 = read_distribution(r1row["M"], se0)
    if not (0.92 <= at_r1["H-UNRESOLVED"] <= 0.98):
        p.append("the H-UNRESOLVED probability at ROUND 1's OWN point estimate "
                 f"(+{r1row['M']}) moved away from READ_RULE §8's ~0.954: "
                 f"{at_r1['H-UNRESOLVED']:.3f} — this is the round's headline "
                 "limitation and it must stay stated")
    if at_r1["H-ADOPT"] > 0.05:
        p.append("the ADOPT power at round 1's own point estimate is "
                 f"{at_r1['H-ADOPT']:.3f}; DESIGN §3 says ~2.5% and the round "
                 "must not advertise itself as able to confirm that effect")
    at_inc = read_distribution(2.95125, se0)
    if not (0.95 <= at_inc["H-ADOPT"] <= 0.995):
        p.append("the power against a REPEAT of the incumbent's +2.951 moved "
                 f"away from READ_RULE §8's ~0.979: {at_inc['H-ADOPT']:.3f}")
    at_pk = read_distribution(1.835, se0)
    if not (0.33 <= at_pk["H-ADOPT"] <= 0.46):
        p.append("the power against the ladder's largest point estimate "
                 f"(+1.835) moved away from READ_RULE §8's ~0.394: "
                 f"{at_pk['H-ADOPT']:.3f}")
    at_2 = read_distribution(2.0, se0)
    if not (0.47 <= at_2["H-ADOPT"] <= 0.59):
        p.append("the power at a true +2.0 moved away from READ_RULE §8's "
                 f"~0.529: {at_2['H-ADOPT']:.3f}")
    # ⭐ the 50%-power point — the honest one-number summary of what this
    # instrument can see.
    mde = BAR_EFFECT + 2.0 * se0
    if abs(mde - 1.965) > 0.01:
        p.append(f"the 50%-adopt-power effect size is {mde:.3f}; DESIGN §3 "
                 "states +1.97 pts/deck and it is the round's honest MDE")
    n_adopt = n_decks_for_adopt_power(2.95125, 0.80)
    if not (370 <= n_adopt <= 420):
        p.append("n_decks_for_adopt_power(2.951, 0.80) moved away from DESIGN "
                 f"§3's ~396: {n_adopt}")
    n_r1 = n_decks_for_adopt_power(r1row["M"], 0.80)
    if n_r1 < 1_000_000:
        p.append("n_decks_for_adopt_power at round 1's own point estimate is "
                 f"{n_r1}; DESIGN §3 states it is over four MILLION decks — "
                 "i.e. NO affordable round resolves that effect, which is the "
                 "single most important thing this pair discloses")
    n_bound = n_decks_for_bounded_power(0.80)
    if not (1400 <= n_bound <= 1650):
        p.append("n_decks_for_bounded_power(0.80) moved away from DESIGN §3's "
                 f"~1505: {n_bound}")
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
    # ⛔⛔ AND AT ROUND 2's OWN se: a point estimate above the bar STILL is not an
    # adoption. Doubling n narrowed the interval; it did not move the bar onto
    # the point estimate.
    if branch_for_cell(1.5, se0, 1.5 / se0, gates_ok=True) == "H-ADOPT":
        p.append(f"M=+1.5 at this round's own se ({se0:.4f}, LB95 "
                 f"{1.5 - 2 * se0:+.3f}) fired H-ADOPT — it must not")
    if branch_for_cell(r1row["M"], se0, r1row["M"] / se0,
                       gates_ok=True) != "H-UNRESOLVED":
        p.append("a REPEAT of round 1's point estimate at this round's own se "
                 "does not read H-UNRESOLVED — that is the round's central "
                 "limitation and the ladder must express it")
    # ⭐ the two ends that this n DOES buy
    if branch_for_cell(2.95125, se0, 2.95125 / se0,
                       gates_ok=True) != "H-ADOPT":
        p.append("a repeat of the incumbent's +2.951 does not read H-ADOPT at "
                 "the funded n — that is the one direction this round is sized "
                 "for")
    if branch_for_cell(0.0, se0, 0.0, gates_ok=True) != "H-BOUNDED":
        p.append("an exact null at this round's own se does not read H-BOUNDED "
                 "— doubling n was supposed to buy exactly that")
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

    # --- ⭐⭐ THE SHARDING GATES' OWN BEHAVIOUR, EXERCISED IN THE LIBRARY ----
    # ⛔ These three gates are the price of the flexible-box clause and a test
    # that only ran in the fixture would leave the library's own contract
    # unasserted. Synthetic shards, one healthy set and three defective ones.
    def _synth_manifest(host, dose=0.2):
        """A manifest carrying EVERY `SHARD_IDENT_ADDRESSES` address — because
        `shard_ident_gate` now FAILS an address that is absent on every chunk
        (chunks that agree about nothing agree about nothing)."""
        m: dict = {"host": host, "cand_tiearb": dict(DEPLOYED_TIEARB),
                   "opp_tiearb": dict(DEPLOYED_TIEARB)}
        vals = {
            "config.cand_search.fpu_reduction": dose,
            "config.cand_search.c_puct": None,
            "config.champion.fpu_reduction": dose,
            "config.champion.c_puct": CHAMP_C_PUCT,
            "config.champion.tau_p": 5.0,
            "config.champion.k_dets": K_DETS,
            "config.champion.sims_per_det": SIMS_PER_DET,
            "config.champion.total_sims": TOTAL_SIMS,
            "config.opponent.champ_cfg.fpu_reduction": None,
            "config.opponent.champ_cfg.c_puct": CHAMP_C_PUCT,
            "config.opponent.champ_cfg.tau_p": 5.0,
            "config.cand_leaf_hash": LEAF_HASH,
            "config.opp_leaf_hash": LEAF_HASH,
            "config.endgame.exact_k": EXACT_K,
            "config.endgame.mode": EXACT_MODE,
            "config.backend.name": BACKEND,
            "rules_profile.name": RULES_PROFILE,
        }
        for addr, v in vals.items():
            cur = m
            parts = addr.split(".")
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
            cur[parts[-1]] = v
        return m

    def _shard(idx, host, seeds, *, summary=True, manifest=True, dose=0.2):
        rows = [{"seed": s, "a_seat": a, "diff": 1.0} for s in seeds
                for a in (0, 1)]
        return {"manifest": _synth_manifest(host, dose) if manifest else None,
                "summary": ({"n": len(rows), "n_failed": 0} if summary else None),
                "records": rows}

    healthy = {}
    for i in range(N_CHUNKS):
        lo, hi = c0.chunk_range(i)
        healthy[c0.chunk_name(i)] = _shard(
            i, "laptop-wsl" if i < 4 else "5800x-box", range(lo, hi + 1))
    if not chunks_gate(c0, healthy)["ok"]:
        p.append("G-CHUNKS failed a complete healthy two-box round")
    if not nodup_gate(c0, healthy)["ok"]:
        p.append("G-NODUP failed a healthy tiling")
    if not shard_ident_gate(healthy)["ok"]:
        p.append("G-SHARD-IDENT failed chunks with identical configs")
    if not host_provenance_gate(c0, healthy)["ok"]:
        p.append("G-HOST failed a healthy two-box provenance map")
    hp = host_provenance_gate(c0, healthy)["detail"]["chunks_by_role"]
    if sorted(hp) != ["laptop", "local"]:
        p.append(f"G-HOST did not resolve both boxes' hosts: {sorted(hp)}")
    # (a) a killed chunk — manifest, no summary
    killed = dict(healthy)
    k0 = c0.chunk_name(3)
    lo, hi = c0.chunk_range(3)
    killed[k0] = _shard(3, "laptop-wsl", range(lo, hi + 1), summary=False)
    if chunks_gate(c0, killed)["ok"]:
        p.append("G-CHUNKS PASSED a chunk with no summary.json — that is the "
                 "flexible-box clause's own failure mode (killed mid-flight) "
                 "and it must FAIL so the chunk is RESUMED, not read around")
    # (b) OVERLAPPING ranges — the two-box mis-split
    dup = dict(healthy)
    lo4, hi4 = c0.chunk_range(4)
    dup[c0.chunk_name(4)] = _shard(4, "5800x-box", range(lo4 - 10, hi4 + 1))
    if nodup_gate(c0, dup)["ok"]:
        p.append("G-NODUP PASSED overlapping chunk ranges — the exact defect a "
                 "mis-typed --seed-lo on the second box produces")
    # (c) a chunk that resolved a DIFFERENT dose
    drift = {k: dict(v) for k, v in healthy.items()}
    drift[c0.chunk_name(6)] = dict(
        healthy[c0.chunk_name(6)],
        manifest=_synth_manifest("5800x-box", dose=0.15))
    if shard_ident_gate(drift)["ok"]:
        p.append("G-SHARD-IDENT PASSED chunks that resolved DIFFERENT doses — "
                 "pooling those is pooling two measurements")
    # (d) a chunk with no host
    nohost = dict(healthy)
    _nh = _synth_manifest("laptop-wsl")
    _nh.pop("host")
    nohost[c0.chunk_name(1)] = dict(healthy[c0.chunk_name(1)], manifest=_nh)
    if host_provenance_gate(c0, nohost)["ok"]:
        p.append("G-HOST PASSED a chunk with no host — the statistic survives "
                 "but the provenance map does not, and ABSENT is FAIL")
    # (e) ⛔⛔ AN UNFUNDED BOX. host_matches_box's "not the laptop ⇒ local"
    # catch-all would launder this into a clean provenance line; the strict
    # resolver must refuse it. (Found by this round's own selftest.)
    unfunded = dict(healthy)
    unfunded[c0.chunk_name(2)] = dict(
        healthy[c0.chunk_name(2)], manifest=_synth_manifest("vast-ai-node-7"))
    if host_provenance_gate(c0, unfunded)["ok"]:
        p.append("G-HOST PASSED a chunk from an UNFUNDED box — host_role_strict "
                 "must refuse any host that is not an explicit alias of a "
                 "funded box")
    if host_role_strict("vast-ai-node-7") is not None:
        p.append("host_role_strict resolved an unfunded host — the "
                 "'not the laptop ⇒ local' catch-all has leaked back in")
    if host_role_strict("laptop-wsl") != "laptop" \
            or host_role_strict("5800x-box") != "local":
        p.append("host_role_strict no longer resolves the two funded boxes")
    # (f) ⭐ and the clause that must NOT fire: ANY tiling of boxes is legal
    flipped = {}
    for i in range(N_CHUNKS):
        lo_i, hi_i = c0.chunk_range(i)
        flipped[c0.chunk_name(i)] = _shard(
            i, "5800x-box" if i % 2 else "laptop-wsl", range(lo_i, hi_i + 1))
    if not host_provenance_gate(c0, flipped)["ok"]:
        p.append("G-HOST voided an INTERLEAVED box assignment — box assignment "
                 "is THROUGHPUT-ONLY and no tiling may be refused")
    return p


if __name__ == "__main__":                                    # pragma: no cover
    probs = sanity_check()
    se0 = se_model(CELLS[0].n_decks)
    print(json.dumps({
        "round": ROUND_ID,
        "sanity_problems": probs,
        "cells": [{"name": c.name, "role": c.role, "knob": c.knob,
                   "value": c.value, "band": c.seed_start,
                   "n_decks": c.n_decks, "n_games": c.n_games} for c in CELLS],
        "chunk_plan": chunk_plan(CELLS[0]),
        "budget": [K_DETS, SIMS_PER_DET, TOTAL_SIMS],
        "deployed_tiearb_both_seats": DEPLOYED_TIEARB,
        "bars": {"BAR_EFFECT": BAR_EFFECT, "BRANCH_Z": BRANCH_Z,
                 "ELO_RESOLUTION_2SIGMA": ELO_RESOLUTION_2SIGMA,
                 "ladder_screen_bar": LADDER_SCREEN_BAR},
        "read_distribution": {
            "delta=0 (true null)": read_distribution(0.0, se0),
            "delta=BAR_EFFECT": read_distribution(BAR_EFFECT, se0),
            "delta=1.019 (ROUND 1's OWN point estimate)":
                read_distribution(1.01875, se0),
            "delta=1.835 (the ladder's largest point estimate)":
                read_distribution(1.835, se0),
            "delta=2.0": read_distribution(2.0, se0),
            "delta=2.951 (the incumbent's realized effect)":
                read_distribution(2.95125, se0)},
        "mde_50pct_adopt_power": BAR_EFFECT + 2.0 * se0,
        "n_decks_for_adopt_power(2.951, 0.80)":
            n_decks_for_adopt_power(2.95125, 0.80),
        "n_decks_for_adopt_power(2.0, 0.80)":
            n_decks_for_adopt_power(2.0, 0.80),
        "n_decks_for_adopt_power(1.835, 0.80)":
            n_decks_for_adopt_power(1.835, 0.80),
        "n_decks_for_adopt_power(1.019 = ROUND 1's point estimate, 0.80)":
            n_decks_for_adopt_power(1.01875, 0.80),
        "n_decks_for_bounded_power(0.80)": n_decks_for_bounded_power(0.80),
        "branch_grid": branch_grid()}, indent=2))
    raise SystemExit(1 if probs else 0)
