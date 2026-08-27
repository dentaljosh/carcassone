#!/usr/bin/env python3
"""INVASION-RISK TERM FAMILY — ROUND-2 BRACKET AT 2752 — THE SHARED BAR LIBRARY.

⛔ **THIS FILE IS THE ONE IMPLEMENTATION OF EVERY BAR, EVERY CONSTANT AND EVERY
COST FIGURE THIS PAIR USES.** `READ_RULE.md` §7:

    "Every bar and every constant lives in `screen_lib.py`, imported by both the
     adjudicator and the launcher's precondition ladder, so the launcher's
     in-flight per-cell pre-check and the adjudicator's own gates cannot drift
     apart. The launcher pins ONLY the band as a numeric literal; every other
     constant is read from the library."

INHERITANCE — THIS IS ROUND 1'S INSTRUMENT, ADAPTED, NOT A NEW ONE
==================================================================
`measurement/invasion_screen_prep/` (round 1, band 151000000000) went through
three smoke rounds, two pre-game-1 amendments and one execution-layer deviation
(IS-D1) before it produced a clean 2800-game round. Its launcher, adjudicator,
bar library and instrument tests are battle-proven, and this pair is a
copy-and-adapt of them changing ONLY what round 2 requires:

  1. SEVEN cells, not four, on a FRESH band (152000000000).
  2. NO `IDENT` cell — round 1's `IDENT` PASSED (z 0.9624 at n=200, all
     conjuncts) on THIS instrument and THIS wheel, and the wheel and the code
     tree have not moved since. That inheritance is CONDITIONAL and the
     condition is MECHANISED: `G-WHEEL-SAME` (below) refuses the round unless
     the manifest's `carc_rs_binary_sha` and `carc_rs_build` are byte-identical
     to round 1's `WHEEL_PROBE.json`. ⛔ A CHANGED WHEEL RE-OWES AN IDENT CELL.
  3. THREE of the seven cells (shape C) run against a NON-CHAMPION opponent —
     a SHAPE-B agent — so round 1's `G-LEAF`/`G-SINGLEVAR` assumption that
     `opp_leaf_hash == the champion pin` is FALSE for them. Every gate that
     touched the opponent side is now PER-CELL and TWO-SIDED: each cell's spec
     pins BOTH sides' expected hashes, and the single-variable property becomes
     "the two sides differ in EXACTLY the pre-registered term knobs".
  4. The read rule is a BRACKET read (does the signal SCALE with weight?), and
     round 1's mids live on a DIFFERENT BAND, so they enter as a DESCRIPTIVE
     OVERLAY ONLY — never pooled, never z-combined (CL-068).
  5. ⭐ TWO BOXES. The owner directed "get round 2 on both local and laptop", so
     the CELL->BOX ASSIGNMENT IS FROZEN IN THE PREREG (`CellSpec.box`), WHOLE
     CELLS PER BOX, and `G-HOST` enforces it against the emitted manifest. The
     assignment is chosen so that **every pre-registered contrast is WITHIN one
     box** — see `BOX_ASSIGNMENT_RULE`.

⚠️ **STDLIB ONLY, DELIBERATELY.** Nothing here imports `carcassonne_ai`,
`eval_fair_puct`, numpy or the rust bindings. The launcher's precondition ladder
runs this module *before* the wheel has been proven, and a library that needed
the harness to import would be unusable at exactly the moment it is most needed.

⚠️ **`paired_margin()` IS A DELIBERATELY INDEPENDENT RE-IMPLEMENTATION** of
`eval_fair_puct._paired_z`, NOT an import of it (`READ_RULE.md` §3 `RECON`). An
imported `_paired_z` would witness nothing — it would agree by construction.

⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every number below
exists before any game does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- #
# THE BAND (DESIGN.md §5)                                                       #
#                                                                               #
# The all-branches sweep of 2026-08-27 (143 refs / 723 registry-and-claim files) #
# found 152000000000 free everywhere: no ref, no registry version and no claim   #
# file mentions any band at or above 152e9. 151000000000 is SPENT by round 1.    #
# `WORKERS.conf` pins the same integer as its ONE numeric literal and            #
# `tests/test_invasion_screen_r2_instrument.py` asserts the two agree.           #
# --------------------------------------------------------------------------- #
BAND = 152000000000

# --------------------------------------------------------------------------- #
# THE LEAVES (DESIGN.md §2.2, §2.5; READ_RULE.md §3 G-LEAF)                     #
# --------------------------------------------------------------------------- #
#: The champion of record's leaf (governance/PRODUCTION.yaml). It is the
#: OPPONENT on the four A/B cells, and it is NOT the opponent on the three C
#: cells — see `SHAPE_B_LEAF_HASH`.
PROD_LEAF_HASH = "a36d2e15a3b3d71d"
CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)

#: ⭐ THE SHAPE-B AGENT'S LEAF — the OPPONENT on all three C cells.
#: It is the champion curve125 leaf PLUS `invasion_alpha 0.09 @ cap 11.0`, i.e.
#: BIT-FOR-BIT round 1's `B_MID` CANDIDATE (`invasion_screen_prep/leaf_b_mid.json`,
#: hash 42adadc988784b44 — the same string round 1 froze and adjudicated).
#: SHAPES.md §3 requires it: shape C is DEFENCE-ONLY and not antisymmetric, so a
#: C-vs-champion cell buys a guaranteed-uninformative null (the champion does not
#: invade). C must be screened against something that DOES invade.
SHAPE_B_LEAF_HASH = "42adadc988784b44"

#: ⭐ HOW THE C CELLS GET A NON-CHAMPION OPPONENT — the mechanism, in one place.
#:
#: `eval_fair_puct.py:3774` gives every head-to-head opponent
#: `_curve125_leaf_cfg()` UNCONDITIONALLY, and there is no `--opp-leaf-json` flag
#: of any spelling. But `_curve125_leaf_cfg()` is
#: `dataclasses.replace(DEFAULT_CONFIG, v29_meeple_curve=CURVE125)` and
#: `DEFAULT_CONFIG` is resolved FROM THE ENVIRONMENT at `virtual_score_v2` import
#: time. So exporting the two variables below BEFORE the process starts moves the
#: OPPONENT's leaf to the shape-B agent — and the CANDIDATE, which is built by
#: `_load_cand_leaf_cfg` replacing named fields on that same `DEFAULT_CONFIG`,
#: takes them back off again with EXPLICIT ZEROS in its JSON.
#:
#: ⚠️ THE EXPLICIT ZEROS ARE LOAD-BEARING. Without `"invasion_alpha": 0.0` and
#: `"invasion_alpha_cap": 0.0` in the candidate JSON the candidate would INHERIT
#: the env's shape-B knobs and the cell would be "B AND C vs B", not "C vs B" —
#: a cell that is not single-variable and that no gate downstream could unpick
#: from the numbers. `G-SINGLEVAR(b)` and `G-INVASION` both check it.
#:
#: ⚠️ The harness's own `_CANON_ENV` (`eval_fair_puct.py:284-313`) is installed
#: with `os.environ.setdefault` and carries NO invasion key, so the two settings
#: compose by construction: setdefault cannot overwrite an exported value, and
#: nothing in `_CANON_ENV` collides.
SHAPE_B_ENV: dict[str, str] = {
    "CARCASSONNE_INVASION_ALPHA": "0.09",
    "CARCASSONNE_INVASION_ALPHA_CAP": "11.0",
}

#: Every field of the invasion family, and the value each holds when the term is
#: OFF. `_leaf_dict` DROPS a field while it holds its default, so in a manifest
#: "absent" IS "default" and both readings must pass (READ_RULE §3 G-INVASION).
#: ⚠️ `invasion_alpha_cap == 0.0` means UNCAPPED in this family (an explicit
#: compare, not a sentinel bug) — which is why the frozen cap is 11.0 and never
#: 0.0, and why `G-CAPFWD` exists at all.
INVASION_DEFAULTS: dict[str, float | int] = {
    "invasion_beta": 0.0,
    "invasion_alpha": 0.0,
    "invasion_alpha_cap": 0.0,
    "invasion_stub_max_tiles": 2,
    "invasion_gamma": 0.0,
    "invasion_delta_farm": 0.0,
}
INVASION_FIELDS = tuple(INVASION_DEFAULTS)

# --------------------------------------------------------------------------- #
# ⭐ THE INHERITED IDENT — and the condition under which the inheritance holds  #
#                                                                              #
# Round 1's IDENT cell (400 games, band 151000000000) asked the game-level      #
# weight-0 identity question: does an explicit-zero invasion config survive the #
# whole pipeline — CLI parse -> `_load_cand_leaf_cfg` -> `leaf_config_rs`'s     #
# CONDITIONAL kwargs -> the rust leaf -> 400 games of scoring — unchanged? It   #
# PASSED, on every conjunct:                                                    #
#                                                                              #
#     |z| = 0.9624 <= 2.0  (D +0.8325, SE 0.8650, n_paired 200)                 #
#     cand_leaf_hash == opp_leaf_hash == a36d2e15a3b3d71d (the champion pin)    #
#     n_failed == 0 · leaf diff EMPTY                                           #
#                                                                              #
# ROUND 2 DOES NOT RE-RUN IT, and that is a DELIBERATE, CONDITIONAL saving of   #
# ~7.7 core-h. What makes a wiring proof transfer is that the WIRING has not    #
# moved, and the wiring is the compiled wheel plus the source tree. So:         #
#                                                                              #
# ⛔ `G-WHEEL-SAME` REFUSES THE ROUND unless the emitted manifest's             #
#    `carc_rs_binary_sha` AND `carc_rs_build` are BYTE-IDENTICAL to round 1's   #
#    `WHEEL_PROBE.json`. A CHANGED WHEEL RE-OWES AN IDENT CELL — a rebuild is   #
#    exactly the event that could move a zero-weight leaf, and no A/B/C reading #
#    could then be attributed to the term rather than to the plumbing.          #
#                                                                              #
# ⚠️ AND THE CONVERSE STAYS TRUE, exactly as round 1 recorded it: a passing     #
# IDENT proves the plumbing carries a ZERO faithfully. It does NOT prove a      #
# nonzero weight reaches the rust leaf — that is `G-INVASION`'s, `G-CAPFWD`'s   #
# and `G-WHEEL`'s job, and `G-LEAF`'s two-sided hash pins are the cheap         #
# cross-check.                                                                  #
# --------------------------------------------------------------------------- #
# ⭐ AND THE FINGERPRINT IS `carc_rs_binary_sha` **ALONE**. THIS BUILD FOUND OUT
# WHY, THE HARD WAY, AND THE FINDING IS RECORDED RATHER THAN PAPERED OVER.
#
# The first implementation of `G-WHEEL-SAME` required BOTH `carc_rs_binary_sha`
# AND `carc_rs_build` to match round 1's. It FAILED `--selftest` against round
# 1's OWN emitted smoke archive — the one archive in existence that is
# guaranteed to be the same wheel — because the two round-1 archives disagree:
#
#     invasion_screen_20260826/smoke_b_mid  build carc_rs-0.1.0+47e7cc0ffb31+...
#     invasion_screen_20260826/b_mid        build carc_rs-0.1.0+ac709c42c6e2+...
#     BOTH                                  binary_sha a9ac686bca1417f9
#
# ⚠️ `rust_agent.carc_rs_build_id()` composes `carc_rs-<cargo version>+<REPO REV
# AT CALL TIME>+rustc<toolchain>` — the rev is `run_manifest`'s, read off the
# WORKING TREE when the manifest is written. It is NOT compiled into the wheel
# and it does NOT move when the wheel does. The smoke and the cells ran the same
# `.so` from two different tree HEADs, so the "build" strings differ and the
# binary sha does not. The source says so itself: `carc_rs_binary_sha`'s
# docstring is *"the only thing that can prove the installed wheel actually
# carries the surface under test"*, and `carc_rs_build_id`'s is *"⚠️ Why NOT the
# binary hash ... the box-local staleness question is answered separately, by
# `carc_rs_binary_sha`"*.
#
# ⛔ SO `G-WHEEL-SAME` KEYS ON `carc_rs_binary_sha` AND NOTHING ELSE. The build
# string is REPORTED beside it as INFORMATIONAL — it is a CODE-REV fact, and the
# code-rev question is `G-REV`'s, which owns `PINNED_SRC_REV` and
# `SRC_CLEAN.jsonl` and answers it properly.
#
# ⚠️ THIS ALSO NARROWS WHAT ROUND 1's INHERITED `G-WHEEL` ANCESTRY CONJUNCT
# PROVES, and round 2 states it rather than repeating round 1's wording: the
# embedded rev proves THE TREE THE GAMES RAN FROM carried `invasion.rs`, not
# that the WHEEL did. That is still worth having (it catches a manifest written
# from a pre-family tree) but it is largely duplicated by `G-REV`, and the
# stale-wheel question it was written for is answered by `WHEEL_PROBE.json`'s
# live nonzero forward plus this gate. Round 1's own gate text is NOT amended
# retroactively — its round is closed — but no round-2 branch may claim the
# ancestry conjunct proves a wheel identity.
#
# ⚠️ AND IT IS A SAME-BOX GATE, DELIBERATELY. `carc_rs_binary_sha` is BOX-LOCAL:
# two boxes compiling identical source with an identical toolchain produce
# different bytes (measured 2026-08-17: local 73aa20102ab98e2f vs laptop
# ec140ac0c0583d53 at the same commit and the same rustc). So running round 2 on
# a DIFFERENT BOX fails this gate even with identical source — and that is the
# CORRECT behaviour, not a false negative: round 1's IDENT was measured on the
# local box's wheel, and a different box's wheel is a wheel whose weight-0
# identity this program has never checked. A different box re-owes an IDENT.
R1_WHEEL_BINARY_SHA = "a9ac686bca1417f9"
#: ⛔ INFORMATIONAL ONLY — see the banner. NOT a discriminator, NOT gated on.
R1_WHEEL_BUILD_INFORMATIONAL = "carc_rs-0.1.0+ac709c42c6e2+rustcunpinned"
R1_IDENT = {
    "band": 151000000000,
    "n_games": 400, "n_paired": 200, "n_failed": 0,
    "D": 0.8325, "SE": 0.8650404288051147, "z": 0.9623827653349533,
    "bar": 2.0,
    "cand_leaf_hash": PROD_LEAF_HASH, "opp_leaf_hash": PROD_LEAF_HASH,
    "verdict": "PRECONDITION-PASS",
    "cost_multiplier": 0.996988008636405,
    "note": ("the ≈1.0 cost CONTROL as well as the wiring proof: with both sides "
             "weight-0 the candidate/opponent ms-per-move ratio was 0.997"),
}


def wheel_is_r1s(binary_sha, build=None) -> tuple[bool, str]:
    """`G-WHEEL-SAME` — the ROUND-LEVEL gate that carries round 1's IDENT PASS
    forward. ⛔ ABSENT is FAIL, and a FAIL VOIDS EVERY CELL (READ_RULE §3.4).

    ⛔ KEYED ON `carc_rs_binary_sha` ALONE — a sha256[:16] of the installed
    `.so`, and per its own docstring "the only thing that can prove the installed
    wheel actually carries the surface under test". `build` is accepted and
    ECHOED for the record but is NOT compared: it embeds the REPO REV AT CALL
    TIME, not a compiled-in value, so it moves when the tree moves and stays put
    when the wheel does. See the banner above for the two round-1 archives that
    proved it.

    ⚠️ `carc_rs_version` is permanently "0.1.0" and is NEVER a discriminator.
    """
    if not binary_sha or not isinstance(binary_sha, str):
        return False, ("carc_rs_binary_sha ABSENT — ABSENT is FAIL. Round 2 "
                       "inherits round 1's IDENT PASS and cannot verify the "
                       "inheritance without the wheel fingerprint.")
    if binary_sha != R1_WHEEL_BINARY_SHA:
        return False, (
            f"THE WHEEL MOVED: carc_rs_binary_sha {binary_sha!r} vs round 1's "
            f"{R1_WHEEL_BINARY_SHA!r}. ⛔ ROUND 2 CARRIES NO IDENT CELL — it "
            "inherits round 1's game-level weight-0 identity proof, and that "
            "inheritance is valid ONLY while the wheel that proved it is the "
            "wheel that plays. A CHANGED WHEEL RE-OWES AN IDENT CELL: add one "
            "(400 decks / 800 games on a fresh sub-range, ~15 core-h at round 2's "
            "cell size) and re-freeze, or reinstall the wheel round 1 ran. "
            "⚠️ A DIFFERENT BOX ALSO FAILS THIS, CORRECTLY: the sha is box-local, "
            "and a different box's wheel is one whose weight-0 identity this "
            "program has never checked. Do NOT read this round past this gate.")
    return True, ("the installed wheel is byte-identical to the one round 1's IDENT "
                  "PASS was measured on"
                  + (f" (build string {build!r} — INFORMATIONAL, a code-rev fact, "
                     "not compared)" if build else ""))


# --------------------------------------------------------------------------- #
# ⭐ THE TWO BOXES (DESIGN.md §6.5)                                             #
#                                                                              #
# Owner directive, verbatim: "get round 2 on both local and laptop".            #
#                                                                              #
# ⛔ THE CELL->BOX ASSIGNMENT IS FROZEN IN THE PREREG, WHOLE CELLS PER BOX, AND #
# `G-HOST` ENFORCES IT AGAINST THE EMITTED MANIFEST. A cell's records are NEVER #
# split across boxes: a mixed-host archive is a provenance smell with no        #
# recovery, and the manifest's `host` is the ONLY host witness the harness      #
# emits (the per-game records carry no host field at all — checked against a    #
# real record at freeze). So the unit of assignment has to be the whole cell,   #
# and the gate has to be on the manifest.                                       #
#                                                                              #
# ⭐ WHY OUTCOMES ARE COMPARABLE ACROSS THE TWO BOXES AT ALL — and it rests on  #
# ONE condition, which is why the executor ships a wheel FILE instead of        #
# rebuilding. The harness is deterministic given `(deck seed, seat, config)`,   #
# and the rust search is bit-identical at any thread count. The remaining       #
# cross-box hazard in THIS program is float/ISA drift — the Xeon was RE-RETIRED #
# 2026-08-02 because AVX-512 makes the G0 determinism check FAIL by default     #
# (`reference_xeon_direct_ssh`). Two mitigations, both frozen:                  #
#   (a) the SAME WHEEL FILE is installed on both boxes, so `carc_rs_binary_sha` #
#       is IDENTICAL on both and `G-WHEEL-SAME` (§ below) passes on both. ⛔ A   #
#       laptop-local REBUILD produces different bytes, a different sha, and the #
#       gate REFUSES — correctly.                                              #
#   (b) ⛔ **NO PRE-REGISTERED STATISTIC IS EVER COMPUTED ACROSS THE TWO BOXES.**#
#       See `BOX_ASSIGNMENT_RULE`. This is the load-bearing one: (a) makes      #
#       cross-box comparison *plausible*, and (b) means the round does not have #
#       to rely on it.                                                          #
# --------------------------------------------------------------------------- #
#: Per-box operational constants. ⚠️ `W` is THROUGHPUT-ONLY — games are
#: bit-identical at any W — so a per-box W changes wall clock and nothing else.
BOXES: dict[str, dict] = {
    "local": {
        "label": "the local 5900XT (16C/32T)",
        "W": 22,
        #: ⚠️ THE SHARE MOUNT SPELLING DIFFERS BY BOX (CLAUDE.md). A launcher that
        #: used the wrong one would write outside the share and the local
        #: adjudicator would never see the archive.
        "share_mount": "/mnt/c/carc-shared",
        #: the calibration box: every ms/move figure in this file is ITS realized
        #: number, so its per-game ratio is 1.0 by definition.
        "per_game_ratio": 1.0,
        "ratio_is_measured": True,
    },
    "laptop": {
        "label": "the laptop (24T, 11 GB) via `ssh laptop-wsl`",
        #: W=22 is `h2h_22016_prep`'s `W_LAPTOP` — the closest precedent by
        #: workload class (a rust `eval_fair_puct` head-to-head with BOTH sides
        #: converted), where it was sized DOWN from W26 against the laptop's
        #: 11 GB ceiling. ⚠️ NOT the W=14 of the carcasum pairs: those run a JVM
        #: opponent process per game and are a different memory shape entirely.
        "W": 22,
        "share_mount": "/mnt/carc-shared",
        #: ⛔ ASSUMED, NOT MEASURED. See `LAPTOP_RATIO_NOTE`.
        "per_game_ratio": 1.4,
        "ratio_is_measured": False,
    },
}
BOX_ROLES = tuple(BOXES)

#: ⛔ THE ONE UNMEASURED OPERATIONAL INPUT OF THE TWO-BOX SPLIT, named so the
#: readout can report the realized figure against it rather than quietly absorb
#: it. `track_d1_fair_rebase`'s laptop W-COST read **+73% vs calibration** — but
#: on PYTHON-backend cells, where the laptop's slower single-thread hurts most.
#: These are RUST cells on both sides, where the gap is smaller. The frozen
#: planning assumption is the midpoint of a **1.3-1.5x** envelope; the round's
#: FIRST laptop pass prints its realized worker-s/game, and the §9 laptop smoke
#: prints a first read before any deck is spent.
#: ⚠️ IT MOVES NO BAR AND NO BRANCH. It is a WALL-CLOCK number: the pair is
#: sims-denominated and every gate reads game outcomes, never a clock.
LAPTOP_RATIO_ASSUMED = 1.4
LAPTOP_RATIO_ENVELOPE = (1.3, 1.5)
LAPTOP_RATIO_NOTE = (
    "⛔ ASSUMED, NOT MEASURED: the laptop's per-game cost on rust-both-sides "
    f"cells is taken as {LAPTOP_RATIO_ASSUMED}x local, inside a "
    f"{LAPTOP_RATIO_ENVELOPE[0]}-{LAPTOP_RATIO_ENVELOPE[1]}x envelope. The "
    "nearest datum is track_d1_fair_rebase's +73%, but that is a PYTHON-backend "
    "cell and does not transfer. The realized ratio is RECORDED from the first "
    "laptop pass and reported; it moves no bar and no branch, because this pair "
    "is sims-denominated and no gate reads a clock."
)

#: ⭐ THE ASSIGNMENT RULE, and the arithmetic behind it (DESIGN §6.5).
BOX_ASSIGNMENT_RULE = (
    "⛔ EVERY PRE-REGISTERED CONTRAST IS WITHIN ONE BOX. Shapes are assigned "
    "WHOLE: A and B (four cells) to the LOCAL box, C (three cells) to the "
    "LAPTOP. So §4.5's low-vs-high contrast is within-box for all three shapes, "
    "and §4.7's noise-signature check across C_LOW/C_MID/C_HIGH is within-box "
    "too. ⭐ THIS IS NOT A CONVENIENCE -- it is what lets the round avoid "
    "relying on cross-box float identity, which this program has been bitten by "
    "before (the Xeon's AVX-512 G0 failure, 2026-08-02). Each cell's own margin "
    "is a WITHIN-CELL, WITHIN-BOX, deck-paired statistic in any case: both sides "
    "of a cell run in the same process on the same box at the same budget. "
    "⚠️ AND THE ASSIGNMENT IS ALSO THE FASTEST ONE: at the assumed 1.4x laptop "
    "ratio the C cells are the round's expensive shape and the laptop is the "
    "slower box, so the split that balances wall-clock and the split that keeps "
    "shapes whole are THE SAME SPLIT (4.12 h vs 3.37 h; see DESIGN §6.5's table "
    "for the four alternatives that were computed and rejected)."
)


# --------------------------------------------------------------------------- #
# THE SEVEN CELLS (DESIGN.md §3, §5.1)                                          #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CellSpec:
    """One cell of round 2. Every field is frozen by `DESIGN.md`; nothing here is
    chosen by this file."""

    name: str                       # A_LOW | A_HIGH | B_LOW | B_HIGH | C_LOW | C_MID | C_HIGH
    shape: str                      # A | B | C
    box: str                        # ⭐ FROZEN box role: "local" | "laptop" (G-HOST)
    rung: str                       # low | mid | high  (position on the shape's ladder)
    knob: str                       # the weight knob this cell moves
    weight: float                   # its frozen value
    seed_start: int                 # first deck seed of this cell's OWN range
    n_decks: int                    # frozen deck count (G-BAND, G-DECKS, G-N)
    n_games: int                    # == 2 * n_decks (deck-paired, both seatings)
    out_subdir: str                 # archive dirname under the run root
    leaf_json: str                  # the --cand-leaf-json this cell runs
    cand_leaf_hash: str             # G-LEAF(c): the pinned CANDIDATE leaf hash
    opp_leaf_hash: str              # G-LEAF(a): the pinned OPPONENT leaf hash
    opponent: str                   # "champion" | "shape_b"
    shape_b_env: bool               # does this cell export SHAPE_B_ENV?
    leaf_diff_keys: frozenset       # G-SINGLEVAR(b): the EXACT frozen differing key set
    cand_invasion: Mapping          # G-INVASION: the CANDIDATE's non-default invasion fields
    opp_invasion: Mapping           # G-INVASION: the OPPONENT's non-default invasion fields
    allow_leaf_hash_drift: bool     # DESIGN §2.2

    @property
    def seed_end(self) -> int:
        """Inclusive last deck seed of this cell's own disjoint range."""
        return self.seed_start + self.n_decks - 1

    @property
    def seeds(self) -> range:
        return range(self.seed_start, self.seed_start + self.n_decks)

    def in_range(self, seed: int) -> bool:
        return self.seed_start <= int(seed) <= self.seed_end


#: The candidate JSON every cell carries, as a dict — the file on disk must equal
#: this, and `tests/test_invasion_screen_r2_instrument.py` asserts it does.
#: ⚠️ Every JSON carries `v29_meeple_curve` EXPLICITLY: `_load_cand_leaf_cfg`
#: replaces named fields on the ENV `DEFAULT_CONFIG`, which is CURVE100, and
#: `_assert_netprior_leaf` HARD-fails on a candidate whose curve is not curve125
#: — even with `--allow-leaf-hash-drift`.
LEAF_JSON_BODIES: dict[str, dict] = {
    "leaf_a_low.json":  {"v29_meeple_curve": list(CURVE125), "invasion_beta": 0.04},
    "leaf_a_high.json": {"v29_meeple_curve": list(CURVE125), "invasion_beta": 0.36},
    "leaf_b_low.json":  {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.03,
                         "invasion_alpha_cap": 11.0},
    "leaf_b_high.json": {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.27,
                         "invasion_alpha_cap": 11.0},
    # ⛔ THE EXPLICIT ZEROS. See SHAPE_B_ENV's banner: without them the candidate
    # inherits the env's shape-B knobs and the cell is not single-variable.
    "leaf_c_low.json":  {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.0,
                         "invasion_alpha_cap": 0.0, "invasion_gamma": 0.08},
    "leaf_c_mid.json":  {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.0,
                         "invasion_alpha_cap": 0.0, "invasion_gamma": 0.23},
    "leaf_c_high.json": {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.0,
                         "invasion_alpha_cap": 0.0, "invasion_gamma": 0.69},
}

_AB = frozenset({"invasion_alpha", "invasion_alpha_cap"})
#: ⚠️ THREE keys on a C cell, not one. The candidate is gamma-only and the
#: OPPONENT carries alpha + cap, so the two sides differ in all three. This is
#: exactly the `G-SINGLEVAR(b)` set-equality that round 1 could write as "the
#: cell's one knob" and round 2 cannot.
_C_DIFF = frozenset({"invasion_alpha", "invasion_alpha_cap", "invasion_gamma"})

#: ⛔ ORDERED. Execution order is A -> B -> C (DESIGN §6.4): the four A/B cells
#: re-use round 1's already-proven PLAIN-regime plumbing, while the three C cells
#: are the ONLY cells in this program's history to move the OPPONENT's leaf, so
#: they run last — after four real cells have confirmed the instrument, and after
#: the §9 smoke has already exercised a C config end to end.
CELLS: tuple[CellSpec, ...] = (
    CellSpec(
        name="A_LOW", box="local", shape="A", rung="low",
        knob="invasion_beta", weight=0.04,
        seed_start=152000000000, n_decks=400, n_games=800,
        out_subdir="a_low", leaf_json="leaf_a_low.json",
        cand_leaf_hash="f8c0f04092734f9e", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=frozenset({"invasion_beta"}),
        cand_invasion={"invasion_beta": 0.04}, opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="A_HIGH", box="local", shape="A", rung="high",
        knob="invasion_beta", weight=0.36,
        seed_start=152000000400, n_decks=400, n_games=800,
        out_subdir="a_high", leaf_json="leaf_a_high.json",
        cand_leaf_hash="f6ce81145cbd5102", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=frozenset({"invasion_beta"}),
        cand_invasion={"invasion_beta": 0.36}, opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="B_LOW", box="local", shape="B", rung="low",
        knob="invasion_alpha", weight=0.03,
        seed_start=152000000800, n_decks=400, n_games=800,
        out_subdir="b_low", leaf_json="leaf_b_low.json",
        cand_leaf_hash="f5b7a26216794290", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        # ⚠️ TWO keys: the cap travels with alpha. `rust_agent.leaf_config_rs`
        # forwards `invasion_alpha_cap` ONLY when `invasion_alpha != 0.0`
        # (DESIGN §2.3), so a cell that set a cap without an alpha would have it
        # silently dropped by the rust config while the manifest still showed it.
        leaf_diff_keys=_AB,
        cand_invasion={"invasion_alpha": 0.03, "invasion_alpha_cap": 11.0},
        opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="B_HIGH", box="local", shape="B", rung="high",
        knob="invasion_alpha", weight=0.27,
        seed_start=152000001200, n_decks=400, n_games=800,
        out_subdir="b_high", leaf_json="leaf_b_high.json",
        cand_leaf_hash="1a42effad7066c0b", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=_AB,
        cand_invasion={"invasion_alpha": 0.27, "invasion_alpha_cap": 11.0},
        opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="C_LOW", box="laptop", shape="C", rung="low",
        knob="invasion_gamma", weight=0.08,
        seed_start=152000001600, n_decks=400, n_games=800,
        out_subdir="c_low", leaf_json="leaf_c_low.json",
        cand_leaf_hash="a6ab04dbb69ad29e", opp_leaf_hash=SHAPE_B_LEAF_HASH,
        opponent="shape_b", shape_b_env=True,
        leaf_diff_keys=_C_DIFF,
        cand_invasion={"invasion_gamma": 0.08},
        opp_invasion={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="C_MID", box="laptop", shape="C", rung="mid",
        knob="invasion_gamma", weight=0.23,
        seed_start=152000002000, n_decks=400, n_games=800,
        out_subdir="c_mid", leaf_json="leaf_c_mid.json",
        cand_leaf_hash="897c21aca11b6fbd", opp_leaf_hash=SHAPE_B_LEAF_HASH,
        opponent="shape_b", shape_b_env=True,
        leaf_diff_keys=_C_DIFF,
        cand_invasion={"invasion_gamma": 0.23},
        opp_invasion={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="C_HIGH", box="laptop", shape="C", rung="high",
        knob="invasion_gamma", weight=0.69,
        seed_start=152000002400, n_decks=400, n_games=800,
        out_subdir="c_high", leaf_json="leaf_c_high.json",
        cand_leaf_hash="df34cb874fea6273", opp_leaf_hash=SHAPE_B_LEAF_HASH,
        opponent="shape_b", shape_b_env=True,
        leaf_diff_keys=_C_DIFF,
        cand_invasion={"invasion_gamma": 0.69},
        opp_invasion={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
        allow_leaf_hash_drift=True,
    ),
)

#: ⭐ THE SELFTEST'S FIXTURE SPEC — ⛔ NOT A ROUND-2 CELL AND NEVER ADJUDICATED.
#:
#: `READ_RULE.md` §7 requires `analyze_screen.py --selftest` to run against a
#: manifest THE HARNESS EMITTED and to refuse a synthesized one — the fix for
#: gates "validated" against a manifest the DESIGN described. Round 1 seeded that
#: from an off-band 2-deck dev probe it ran itself. ⛔ ROUND 2 RUNS NO GAMES AT
#: ALL, so it seeds from a REAL EMITTED ARCHIVE THAT ALREADY EXISTS: round 1's
#: own §9 smoke archive (16 games, `invasion_screen_20260826/smoke_b_mid/`,
#: throwaway range 151999999000.., discarded and never pooled), copied verbatim
#: into `selftest_fixture/`.
#:
#: That archive is a B-shaped, PLAIN-regime, champion-opponent cell — the shape
#: `B_LOW`/`B_HIGH` have, at round 1's alpha rather than round 2's. This spec
#: describes it EXACTLY so `--selftest` question 2 ("can a healthy run pass?")
#: is answered on a real archive rather than dodged. ⚠️ It carries round 1's
#: alpha 0.09 / cap 11.0 deliberately: a fixture bent to match a round-2 weight
#: would no longer be the archive the harness wrote.
#:
#: ⚠️ WHAT IT CANNOT PROVE: it is a PLAIN-regime archive, so it does not exercise
#: the C cells' shape-B opponent, the two-sided hash pins in their interesting
#: direction, or the three-key leaf diff. Those are covered by
#: `tests/test_invasion_screen_r2_instrument.py` (synthesized manifests are
#: legitimate in unit tests; it is the SELFTEST that refuses synthesis) and,
#: definitively, by the §9 SMOKE — which runs `C_MID`'s config precisely so the
#: C machinery emits a real manifest before any cell spends a deck.
FIXTURE_SPEC = CellSpec(
    name="SELFTEST_FIXTURE", box="local", shape="B", rung="mid",
    knob="invasion_alpha", weight=0.09,
    seed_start=151999999000, n_decks=8, n_games=16,
    out_subdir="selftest_fixture", leaf_json="(round 1's leaf_b_mid.json)",
    cand_leaf_hash=SHAPE_B_LEAF_HASH, opp_leaf_hash=PROD_LEAF_HASH,
    opponent="champion", shape_b_env=False,
    leaf_diff_keys=frozenset({"invasion_alpha", "invasion_alpha_cap"}),
    cand_invasion={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
    opp_invasion={},
    allow_leaf_hash_drift=True,
)

CELL_NAMES = tuple(c.name for c in CELLS)
SHAPES = ("A", "B", "C")
#: ⚠️ EVERY cell is an ARM in round 2 — there is no precondition cell. The
#: precondition role is played by `G-WHEEL-SAME` (round 1's inherited IDENT) and
#: by the §9 smoke, neither of which spends a deck of this band.
ARM_CELLS = CELLS


def cell_by_name(name: str) -> CellSpec:
    for c in CELLS:
        if c.name == name:
            return c
    raise KeyError(f"no such cell: {name!r} (have {list(CELL_NAMES)})")


def cells_of_shape(shape: str) -> tuple[CellSpec, ...]:
    return tuple(c for c in CELLS if c.shape == shape)


def cells_of_box(role: str) -> tuple[CellSpec, ...]:
    """The cells FROZEN to one box. `run_cells.sh --host <role>` runs exactly
    these and refuses any other; `G-HOST` re-checks it against the manifest."""
    if role not in BOXES:
        raise KeyError(f"no such box role: {role!r} (have {list(BOX_ROLES)})")
    return tuple(c for c in CELLS if c.box == role)


# --------------------------------------------------------------------------- #
# ⭐ G-HOST — the frozen assignment, enforced against the emitted manifest      #
#                                                                              #
# ⚠️ THE MANIFEST'S `host` IS THE ONLY HOST WITNESS THE HARNESS EMITS. The      #
# per-game records carry NO host field (verified against a real round-1 record  #
# at freeze: seed/a_seat/diff/scores/timings and nothing else). So this gate    #
# CANNOT prove that every record of a cell came from one box; it proves that    #
# the cell's SEALING PASS — the one that wrote the pooled summary the           #
# adjudicator reads — ran on the box the pair assigned it to.                   #
#                                                                              #
# ⛔ THAT IS WHY THE REAL PROTECTION IS STRUCTURAL, NOT THIS GATE: the two      #
# boxes are given DISJOINT CELLS and therefore DISJOINT `--out-subdir`s, so     #
# `--shared-claim` has nothing to race over between them. Two boxes pointed at  #
# one cell would race on claims; two boxes pointed at different cells cannot.   #
# `G-HOST` catches the launcher-level version of the mistake — a box handed the #
# wrong `--host` role — and the launcher refuses it a second time up front.     #
#                                                                              #
# ⚠️ ALSO WHY THE WSL CLOCK-DRIFT GUARD (the F7c class,                         #
# `reference_wsl_clock_drift_after_sleep`) is a WITHIN-box concern here and not #
# a cross-box one: a skewed clock lets a box steal STALE CLAIMS, and there are  #
# no shared claims to steal. It still matters inside a box's own pass-resume    #
# loop, which is why the launcher keeps `--claim-stale-secs` and the orphan     #
# sweep.                                                                        #
# --------------------------------------------------------------------------- #
def host_matches_box(observed_host, role: str) -> tuple[bool, str]:
    """`G-HOST`. ⛔ ABSENT is FAIL.

    The comparison is deliberately a SUBSTRING match on a normalised hostname
    rather than an equality against a pinned string: this program's boxes report
    different hostnames under Windows vs WSL vs Pop!_OS on the SAME machine
    (`reference_laptop_popos_access`: `laptop`, `laptop-wsl`, `laptop-pop` are
    one physical box), and pinning one spelling would void a healthy cell for a
    dual-boot reason that has nothing to do with the measurement.

    What it must catch is the mistake that matters: a cell that ran on the OTHER
    box. Since the two roles' hostname markers are disjoint, a substring test
    does that exactly.
    """
    if not observed_host or not isinstance(observed_host, str):
        return False, ("manifest `host` ABSENT — ABSENT is FAIL. The cell->box "
                       "assignment is frozen in the prereg and cannot be verified "
                       "without it.")
    h = observed_host.strip().lower()
    markers = {"laptop": ("laptop", "pop-os", "popos"), "local": ()}
    if role == "laptop":
        ok = any(m in h for m in markers["laptop"])
        why = ("" if ok else
               f"host {observed_host!r} does not look like the laptop, but this "
               "cell is FROZEN to it (DESIGN §6.5). A cell run on the wrong box "
               "breaks the property the assignment exists to protect: that no "
               "pre-registered contrast is ever computed across the two boxes.")
    else:
        ok = not any(m in h for m in markers["laptop"])
        why = ("" if ok else
               f"host {observed_host!r} looks like the LAPTOP, but this cell is "
               "FROZEN to the local box (DESIGN §6.5).")
    return ok, (why or f"host {observed_host!r} is the frozen box for this cell "
                       f"({role})")


#: Where each box drops the launch artifacts the adjudicator has to read back.
#: ⭐ The two boxes each write `PINNED_SRC_REV`, `SRC_CLEAN.jsonl`,
#: `BLIND_PROOF.json` and `WHEEL_PROBE.json` into THEIR OWN repo checkout, which
#: the LOCAL adjudicator cannot see — so each launcher also copies them to
#: `<out-root>/_provenance/<role>/` on the SHARE. `G-REV`, `G-BLIND` and
#: `G-WHEEL` then evaluate each cell against ITS OWN BOX's artifacts.
#: ⚠️ The adjudicator FALLS BACK to its own directory when a per-box copy is
#: absent, so a single-box run and the §9 smoke keep working unchanged.
PROVENANCE_DIRNAME = "_provenance"


def provenance_subdir(role: str) -> str:
    return f"{PROVENANCE_DIRNAME}/{role}"


# --------------------------------------------------------------------------- #
# ROUND 1'S MIDS — ⛔ DESCRIPTIVE OVERLAY ONLY (READ_RULE.md §1.2, §4.5)         #
#                                                                              #
# These are the numbers round 1 adjudicated, on band 151000000000. They are     #
# carried here so the readout can PLOT the ladder — and they are fenced off     #
# from every statistic in this pair, because they are CROSS-BAND.              #
#                                                                              #
# ⛔ NEVER POOLED. ⛔ NEVER z-COMBINED. ⛔ NEVER A BRANCH INPUT. CL-068 measured  #
# 1.8-2.2x over-dispersion on cross-band contrasts, in BOTH the elo and the     #
# deck-paired-margin statistics, with an identity control exonerating the       #
# harness and the "different decks" explanation arithmetically excluded (the    #
# per-deck SEM already prices the deck draw). A r1-mid-vs-r2-endpoint contrast  #
# is exactly that class. The bracket question is answered WITHIN round 2, by    #
# `shape_contrast()` below; the r1 mid is drawn on the same axes and nothing    #
# more.                                                                        #
# --------------------------------------------------------------------------- #
R1_MIDS = {
    "A": {"cell": "A_MID", "knob": "invasion_beta", "weight": 0.12,
          "D": 0.52375, "SE": 0.5237888785732688, "z": 0.9999257743437113,
          "n_paired": 400, "winrate": 0.51, "elo": 6.94963842776909,
          "branch": "NULL", "cand_leaf_hash": "0fd1680fa363d65e"},
    "B": {"cell": "B_MID", "knob": "invasion_alpha", "weight": 0.09,
          "D": 0.7575, "SE": 0.5986643315160625, "z": 1.265316739485215,
          "n_paired": 400, "winrate": 0.5225, "elo": 15.64516754533055,
          "branch": "BRACKET", "cand_leaf_hash": SHAPE_B_LEAF_HASH},
    "D": {"cell": "D_MID", "knob": "invasion_delta_farm", "weight": 0.12,
          "D": -0.29125, "SE": 0.5943279274163528, "z": -0.4900493255737024,
          "n_paired": 400, "winrate": 0.495, "elo": -3.474471674037067,
          "branch": "NULL", "cand_leaf_hash": "5012569b4e93d559"},
}
R1_BAND = 151000000000
R1_OVERLAY_RULE = (
    "⛔ DESCRIPTIVE OVERLAY ONLY. Round 1's mids were played on band "
    f"{R1_BAND}; this round is on band {BAND}. CL-068 measured 1.8-2.2x "
    "over-dispersion on CROSS-BAND contrasts in BOTH the elo and the "
    "deck-paired-margin statistics. The r1 mid is PLOTTED on the ladder and is "
    "NEVER pooled with an r2 cell, NEVER z-combined with one, and NEVER a "
    "branch input. The scaling question is answered WITHIN round 2 by the "
    "pre-registered low-vs-high contrast."
)

#: ⛔ SHAPE D IS NOT RUN IN ROUND 2. Round 1's D_MID read z -0.49 — a bounded
#: null and the LEAST informative of the three (SHAPES.md/DESIGN §3.2(v): T_D's
#: one-ply sibling-delta is ~0 at 94.6% of the census positions). Bracketing a
#: shape that read below zero at its scale-matched mid buys the least per
#: core-hour of any point on the menu, and the owner's funded menu named the B
#: bracket, the A bracket and the C-vs-B-agent cells — not D. Recorded here so
#: no branch can imply D was screened at a second weight.
D_NOT_RUN = (
    "Shape D is NOT run in round 2. Its round-1 mid read D -0.291 / z -0.490 (a "
    "bounded null), and DESIGN §3.2(v)'s measured one-ply sibling-delta for T_D "
    "is ~0 at 94.6% of the census positions, so a D reading is the least "
    "informative about its own mechanism. No branch may say anything about "
    "shape D at any weight other than round 1's mid."
)


# --------------------------------------------------------------------------- #
# THE §9 SMOKE LEG (DESIGN.md §9)                                               #
#                                                                              #
# 16 games (8 decks x 2 seatings) on a THROWAWAY range deliberately placed far  #
# above every cell range, so no arithmetic slip can reach a real deck.          #
#                                                                              #
# ⭐ THE SMOKE RUNS `C_MID`'s CONFIG — a DELIBERATE CHANGE FROM ROUND 1, which  #
# smoked B_MID. B was round 1's most-plumbing cell (a nonzero weight, the drift #
# flag, the cap biconditional). Round 2's most-plumbing cell is a C cell, and   #
# by some distance: it adds the SHAPE-B ENV REGIME, an OPPONENT-side leaf that  #
# is not the champion, the explicit-zero neutralisation on the candidate side,  #
# a THREE-key leaf diff, and two-sided hash pins. Every one of those is new     #
# machinery that has never emitted a manifest. C_MID rather than C_LOW/C_HIGH   #
# because the interior rung is the one the noise-signature rule will read.      #
#                                                                              #
# It is DISCARDED, never pooled, never claimed, never adjudicated as a result.  #
# --------------------------------------------------------------------------- #
#: ⭐ ONE SMOKE PER BOX, EACH ON ITS OWN DISJOINT THROWAWAY SUB-RANGE, EACH
#: RUNNING THAT BOX'S OWN MOST-PLUMBING CELL CONFIG.
#:
#: A single-box round could smoke once. A two-box round cannot: each box has its
#: own wheel install, its own repo checkout, its own share mount spelling and its
#: own W, and the §9 leg's whole purpose is to prove the plumbing on the machine
#: that will spend the decks. ⛔ THE LAPTOP SMOKE IS THE LOAD-BEARING ONE — the
#: laptop runs the three C cells, which are simultaneously round 2's new
#: machinery AND the box's first sight of it.
SMOKE_DECKS = 8
SMOKE_GAMES = 16
SMOKE_BY_BOX: dict[str, dict] = {
    "laptop": {
        "cell": "C_MID",
        "seed_start": 152999999000,
        "why": ("the laptop owns the three C cells, and C_MID is round 2's "
                "most-plumbing config by a wide margin: the shape-B ENV regime, "
                "an OPPONENT leaf that is not the champion, the explicit-zero "
                "neutralisation on the candidate side, a THREE-key leaf diff and "
                "two-sided hash pins -- none of which has ever emitted a "
                "manifest, on any box. C_MID rather than C_LOW/C_HIGH because "
                "the interior rung is the one §4.7's noise-signature rule reads."),
    },
    "local": {
        "cell": "B_LOW",
        "seed_start": 152999999100,
        "why": ("the local box owns the four A/B cells, whose PLAIN-regime "
                "plumbing round 1 already proved on this exact box with this "
                "exact wheel -- so this leg is a cheap re-confirmation of the "
                "launcher and the wheel install rather than a first sight. B "
                "rather than A because B is the only A/B config with the "
                "cap-forwarding biconditional to break."),
    },
}
#: back-compat aliases for the single-cell readers (the adjudicator's
#: `--smoke-mode` takes an explicit `--cell` directory and infers the rest).
SMOKE_CELL = SMOKE_BY_BOX["laptop"]["cell"]
SMOKE_SEED_START = SMOKE_BY_BOX["laptop"]["seed_start"]


# --------------------------------------------------------------------------- #
# THE BARS (READ_RULE.md §3, §4)                                                #
#                                                                              #
# ⛔ CARRIED VERBATIM FROM ROUND 1. Not one bar moved. The comparison operators  #
# in `branch_for_cell()` are the ones READ_RULE uses — `>=`, `<=`, `<`. A bar   #
# is a CLOSED interval at exactly its stated endpoint; the instrument tests     #
# drive each one AT the endpoint for that reason.                              #
# --------------------------------------------------------------------------- #
PROMOTE_Z = 2.0          # §4 PROMOTE:  z_C >= +2.0
BRACKET_Z = 1.0          # §4 BRACKET:  +1.0 <= z_C < +2.0
REVERSED_Z = -2.0        # §4 REVERSED: z_C <= -2.0

#: §4.5 — the pre-registered WITHIN-r2 low-vs-high contrast resolves at this bar.
#: ⛔ It is a SHAPE reading and a round-3 input; it is NEVER a promotion input
#: (promotion is per-cell, against zero, at the cell's own realized SE).
CONTRAST_Z = 2.0

#: §3 G-SAT — a RAIL check, not a strength bar.
SAT_WR = (0.35, 0.65)

#: §3 G-N — `n_common >= 80%` of the frozen deck count.
N_COMMON_FRAC = 0.80

#: §3 G-N — a failure rate STRICTLY BELOW 2% is REPORTED, not silently absorbed,
#: and does not by itself void (the `b32v64` 0.100% rust-panic-class precedent).
FAILURE_RATE_VOID = 0.02

#: §2.1 — the sizing model, CARRIED UNCHANGED from round 1 (median 13.15 /
#: closest analogue 13.60 / MAX 14.67, inverted off seven n=400-deck deck-paired
#: fixed_v1+R9 rust cells in experiments/results.csv). This pair sizes on the MAX.
#: ⛔ POWER ARITHMETIC ONLY. Every bar in §4 is evaluated at the cell's OWN
#: REALIZED SE; this constant is NEVER a denominator in a branch test.
#: ⚠️ Round 2 keeps 14.67 even though round 1 REALIZED tighter (see
#: `R1_REALIZED_SIGMA_D`). Keeping the conservative model means the published
#: power table UNDER-states this round's real resolution rather than over-stating
#: it, which is the direction a screen that decides funding should err in.
SIGMA_D_MODEL = 14.67

#: ⭐ WHAT ROUND 1 ACTUALLY REALIZED, on this exact instrument: `SE x sqrt(n)`
#: per arm. Published beside the model so the readout can say how much power the
#: conservative sizing gave away, and so a round-2 SE near the model's FLOOR is
#: read as "tighter than modelled", not as an anomaly.
R1_REALIZED_SIGMA_D = {"A_MID": 10.4758, "B_MID": 11.9733, "D_MID": 11.8866,
                       "IDENT": 12.2335}

#: §1 — realized/modelled SE outside this window is FLAGGED as a dispersion
#: anomaly. ⛔ CARRIED VERBATIM; reported, never a branch input.
#: ⚠️ Round 1 realized ratios 0.714 / 0.816 / 0.810 / 0.834 against this model,
#: i.e. hugging the FLOOR — A_MID sat 2% above the flag. A round-2 flag at the
#: LOW end is therefore EXPECTED and means "tighter than modelled"; a flag at
#: the HIGH end is the concerning direction. The band does not move for that.
SE_ANOMALY_BAND = (0.70, 1.43)

#: §4.4 — the in-family elo/pt bracket, carried verbatim. Endpoints are two
#: in-family cells: `cl060_h2h_k8x1376_vs_deploy_k4x688` (16.74) and
#: `width_k4x2752_..._b119e9` (19.35).
ELO_PER_PT_BRACKET = (16.74, 19.35)

#: §3 RECON tolerance: rel 1e-6 / abs 1e-9.
RECON_RTOL = 1e-6
RECON_ATOL = 1e-9

#: §3.5 — THE SMOKE LEG'S PINNED ALLOWED SET. A 16-game throwaway archive on a
#: disjoint range cannot satisfy these BY CONSTRUCTION. A failure OUTSIDE this
#: set is a LAUNCH BLOCKER.
#: ⚠️ `G-IDENT` is GONE from round 2 (there is no IDENT cell) and `G-WHEEL-SAME`
#: has taken its slot — and `G-WHEEL-SAME` is NOT in the allowed set: the smoke
#: runs on the same wheel the cells will, so it MUST pass there. That is a
#: TIGHTENING relative to round 1's allowed set, not a widening.
SMOKE_ALLOWED_FAILURES = frozenset({
    "G-BAND", "G-DECKS", "G-N", "G-SAT", "G-HOST", "RECON/n_paired",
})

#: Why each member of the allowed set cannot pass on a 16-game throwaway.
SMOKE_ALLOWED_REASONS = {
    "G-BAND": "the smoke runs on the DISJOINT throwaway range "
              f"({SMOKE_SEED_START}..{SMOKE_SEED_START + SMOKE_DECKS - 1}) with "
              f"{SMOKE_DECKS} decks, never a cell's claimed band/deck count.",
    "G-DECKS": "same reason: every realized seed is outside every cell's own "
               "range, and n_common is 8, not 400.",
    "G-N": f"a smoke is {SMOKE_GAMES} games, not 800.",
    "G-SAT": "a 16-game winrate is a property of the DATA at a sample size that "
             "cannot establish a saturation property; a smoke must not be able "
             "to block a launch on a coin flip.",
    "G-HOST": "⚠️ ALLOWED ONLY BECAUSE THE ADJUDICATOR CANNOT KNOW WHICH BOX A "
              "SMOKE ARCHIVE CAME FROM: --smoke-mode is handed a directory, and "
              "each box smokes a DIFFERENT cell's config on its own throwaway "
              "range, so the smoke cell's frozen `box` is not necessarily the "
              "box that ran it. ⛔ THE PROPERTY IS NOT UNCHECKED: the launcher "
              "refuses to run any cell not in `cells_of_box(--host)` before a "
              "game starts, and G-HOST is fully enforced on every REAL cell.",
    "RECON/n_paired": "the deck-count half of the reconciliation is a band "
                      "property; the MARGIN/z/winrate/elo halves are NOT allowed "
                      "to fail and are enforced separately.",
}

#: The 19 gate ids of READ_RULE §3, in the order the readout prints them.
#: ⚠️ NINETEEN, not round 1's eighteen: `G-IDENT` retired with the IDENT cell,
#: `G-WHEEL-SAME` took its place as the ROUND-LEVEL gate, and ⭐ `G-HOST` is NEW
#: — a two-box round whose cell->box assignment is frozen in the prereg has to
#: be able to check it against the emitted manifest, or the assignment is a
#: sentence rather than a gate.
GATE_IDS = (
    "G-BAND", "G-DECKS", "G-SINGLEVAR", "G-LEAF", "G-INVASION", "G-CAPFWD",
    "G-WHEEL", "G-WHEEL-SAME", "G-HOST", "G-RULES", "G-BACKEND", "G-BUDGET",
    "G-TIEARB", "G-EXACT", "G-REV", "G-BLIND", "G-N", "G-SAT", "RECON",
)
assert len(GATE_IDS) == 19, "READ_RULE §3 names NINETEEN gates"

#: The statistics `RECON` reconciles, in print order.
RECON_STATS = ("paired_mean_margin", "paired_z", "n_paired", "winrate", "elo")


# --------------------------------------------------------------------------- #
# G-LEAF — THE ONE IMPLEMENTATION OF THE TWO-SIDED HASH GATE                    #
#                                                                              #
# ⭐ THE SINGLE BIGGEST ADAPTATION FROM ROUND 1. Round 1 could write `G-LEAF(a)` #
# as the CONSTANT `opp_leaf_hash == a36d2e15a3b3d71d`, because every one of its  #
# four cells played the plain champion. Three of round 2's seven do not — the C #
# cells' opponent is the SHAPE-B AGENT — so the gate is now PER-CELL and reads   #
# BOTH pins off the cell's own spec.                                            #
#                                                                              #
# ⛔ AND THE GATE IS NOT WEAKER FOR IT — IT IS STRICTER. Round 1's opponent      #
# conjunct existed because `--allow-leaf-hash-drift` is a SINGLE switch that     #
# relaxes `_assert_netprior_leaf` on BOTH sides (`eval_fair_puct.py:3763`        #
# candidate, `:3777` opponent), so on every drift-flagged cell the harness's own #
# opponent-side hash assertion enforces NOTHING. Round 2 passes that flag on ALL #
# SEVEN cells, so this gate is the ONLY thing standing between the round and a   #
# silently-drifted opponent leaf — on the C cells in particular, where the       #
# opponent is SUPPOSED to drift and "it drifted" is therefore not a tell.        #
# EXACT equality against a pre-registered pin is the only check that can tell    #
# "drifted to the shape-B agent" from "drifted to something else".               #
#                                                                              #
# Called by BOTH the adjudicator's `G-LEAF` and the launcher's per-cell          #
# pre-check, so the live gate and the post-hoc gate cannot drift apart — the     #
# `track_d2r2_prep` defect this whole library exists against.                    #
# --------------------------------------------------------------------------- #
def leaf_gate(spec: CellSpec, cand_hash, opp_hash, cand_curve) -> dict:
    """READ_RULE §3 `G-LEAF`, in full, for ONE cell. ⛔ ABSENT is FAIL."""
    curve_ok = False
    if cand_curve is not None:
        try:
            curve_ok = tuple(float(x) for x in cand_curve) == tuple(CURVE125)
        except (TypeError, ValueError):
            curve_ok = False
    conj = {
        # (a) the OPPONENT side, pinned per cell
        "opp_hash_is_pinned": (isinstance(opp_hash, str)
                               and opp_hash == spec.opp_leaf_hash),
        # (b) the candidate curve — a hard fail in the harness too, but only
        #     BEFORE the drift flag; re-established here against the manifest
        "cand_curve_is_curve125": bool(curve_ok),
        # (c) the CANDIDATE side, pinned per cell — EXACT, never "merely different"
        "cand_hash_is_pinned": (isinstance(cand_hash, str)
                                and cand_hash == spec.cand_leaf_hash),
        # (d) ⭐ the two sides must be DIFFERENT leaves. On a C cell both pins are
        #     nonzero-invasion leaves, so "not the champion" is no longer a proxy
        #     for "the swap happened" — this states the property directly.
        "sides_are_different_leaves": (isinstance(cand_hash, str)
                                       and isinstance(opp_hash, str)
                                       and cand_hash != opp_hash),
    }
    ok = all(conj.values())
    return {
        "ok": ok, "conjuncts": conj,
        "cand_leaf_hash": cand_hash, "cand_leaf_hash_expected": spec.cand_leaf_hash,
        "opp_leaf_hash": opp_hash, "opp_leaf_hash_expected": spec.opp_leaf_hash,
        "opponent": spec.opponent,
        "why": "" if ok else (
            f"{spec.name} pins candidate {spec.cand_leaf_hash} vs opponent "
            f"{spec.opp_leaf_hash} ({spec.opponent}). "
            "⛔ --allow-leaf-hash-drift relaxes the harness's assertion on BOTH "
            "sides, so this gate is the only thing re-establishing either pin."),
    }


# --------------------------------------------------------------------------- #
# THE COST MODEL — REBUILT ON ROUND 1's REALIZED NUMBERS (DESIGN.md §6)         #
#                                                                              #
# ⛔ ROUND 1's PROJECTION MODEL IS RETIRED. It was a two-point fit ported from   #
# `track_d2r4_prep` (`160 + 0.12025*N` ms/move, +25% on the candidate half) and  #
# it landed at 54-62 core-h against a REALIZED ~64. Round 2 does not need a      #
# model: round 1 measured every input on this exact instrument, at this exact    #
# budget, at W=22, with the same solver co-tenant.                              #
#                                                                              #
# THE INPUTS, ALL MEASURED (invasion_screen_20260826/*/summary.json):            #
#     plain-champion side   461.4 / 457.8 / 480.7 / 481.6 ms/move                #
#     shape-A candidate     693.8 ms/move   (multiplier 1.4434)                  #
#     shape-B candidate     626.2 ms/move   (multiplier 1.3679)                  #
#     shape-D candidate     679.7 ms/move   (multiplier 1.4115)                  #
#     IDENT (both weight-0) 461.4 / 462.8   (multiplier 0.997 -- the CONTROL)    #
#                                                                              #
# THE MODEL IS JUST ARITHMETIC ON THOSE:                                        #
#     s/game = MOVES_PER_SIDE * (ms_cand + ms_opp)/1000 * OVERHEAD              #
#                                                                              #
# and it REPRODUCES all three round-1 arms within ~1% of their realized          #
# worker-seconds per game (A 86.96 vs 87.45 realized; B 80.25 vs 79.2;           #
# D 86.00 vs 85.8). `sanity_check()` asserts that reproduction, so a typo in     #
# any constant below cannot survive to launch.                                  #
# --------------------------------------------------------------------------- #
MOVES_PER_SIDE = 69.0     # measured, rust, fixed_v1
#: realized worker-seconds / measured move-time, from round 1's A_MID cell
#: (87.45 realized vs 81.05 of pure move time): harness, claim I/O, solver tail.
OVERHEAD = 1.073
W_DEFAULT = 22

#: Per-side ms/move, MEASURED in round 1 except where marked.
MS_CHAMPION_SIDE = 470.0        # the plain champion, mean of round 1's four cells
MS_SHAPE_A_SIDE = 693.8         # measured (A_MID candidate)
MS_SHAPE_B_SIDE = 626.2         # measured (B_MID candidate) -- ALSO the C cells' OPPONENT
MS_SHAPE_D_SIDE = 679.7         # measured (D_MID candidate) -- round 2 does not run D

#: ⚠️ SHAPE C'S COST IS THE ONE UNMEASURED INPUT. No gamma cell has ever run.
#: `T_C` is a PER-COMPONENT scan over the mover's own claimed components — the
#: same algorithmic class as A and D (which measured 1.443x and 1.412x) and
#: strictly cheaper than B's ORDERED-PAIR scan over same-terrain components with
#: a merge-distance test (which measured 1.368x -- lower, because B's pair scan
#: is gated on a small stub set). The point estimate takes the A/D mean; the
#: honest envelope is [B's measured multiplier, A's +10%].
MS_SHAPE_C_SIDE = 686.8                    # ASSUMED = mean(A, D) = the point estimate
MS_SHAPE_C_ENVELOPE = (626.2, 763.2)       # [B measured, A measured x1.10]


def _cell_ms(spec: CellSpec, c_side: float | None = None) -> tuple[float, float]:
    """`(candidate ms/move, opponent ms/move)` for a cell. The C cells are the
    only ones whose BOTH sides pay invasion arithmetic — the candidate for gamma
    and the opponent for alpha — which is why they are the round's expensive
    cells and why round 1's "charged to the candidate side only" note does not
    carry over."""
    cand = {"A": MS_SHAPE_A_SIDE, "B": MS_SHAPE_B_SIDE,
            "C": (MS_SHAPE_C_SIDE if c_side is None else float(c_side))}[spec.shape]
    opp = MS_SHAPE_B_SIDE if spec.opponent == "shape_b" else MS_CHAMPION_SIDE
    return cand, opp


def project_cell_cost(spec: CellSpec, w: int | None = None,
                      c_side: float | None = None,
                      laptop_ratio: float | None = None) -> dict:
    """One cell's cost ON ITS OWN FROZEN BOX.

    ⭐ TWO SCALES ARE REPORTED AND THEY ARE NOT THE SAME NUMBER:

    * `core_hours_local_equiv` — what the cell would cost on the CALIBRATION box.
      This is the scale round 1's realized figures are in, and the only scale on
      which the seven cells are comparable to each other.
    * `core_hours` — what it actually costs ON ITS BOX, i.e. the local-equivalent
      times that box's `per_game_ratio`. ⛔ This is the one the funding line is in,
      because it is the compute that actually gets spent.

    ⚠️ The laptop's ratio is ASSUMED, not measured (`LAPTOP_RATIO_NOTE`).
    """
    box = BOXES[spec.box]
    w = box["W"] if w is None else int(w)
    ratio = box["per_game_ratio"]
    if spec.box == "laptop" and laptop_ratio is not None:
        ratio = float(laptop_ratio)
    cand, opp = _cell_ms(spec, c_side)
    s_local = MOVES_PER_SIDE * (cand + opp) / 1000.0 * OVERHEAD
    s_per_game = s_local * ratio
    core_s = s_per_game * spec.n_games
    return {
        "cell": spec.name, "box": spec.box, "n_games": spec.n_games,
        "ms_cand": cand, "ms_opp": opp,
        "cost_multiplier": cand / opp,
        "s_per_game_local_equiv": s_local,
        "s_per_game": s_per_game,
        "box_ratio": ratio,
        "box_ratio_is_measured": bool(box["ratio_is_measured"]),
        "core_hours_local_equiv": s_local * spec.n_games / 3600.0,
        "core_hours": core_s / 3600.0,
        "wall_hours": (core_s / float(w)) / 3600.0 if w else float("nan"),
        "wall_minutes": (core_s / float(w)) / 60.0 if w else float("nan"),
        "w": int(w),
        "c_side_is_assumed": (spec.shape == "C" and c_side is None),
    }


def project_round_cost(c_side: float | None = None,
                       laptop_ratio: float | None = None) -> dict:
    """The whole round, per cell AND per box.

    ⭐ THE ROUND'S WALL CLOCK IS THE **MAX** OVER THE BOXES, NOT THE SUM: the two
    boxes run CONCURRENTLY. That is the entire point of the two-box split, and it
    is why the assignment is chosen to balance the two walls (`BOX_ASSIGNMENT_RULE`).
    """
    per_cell: dict[str, dict] = {}
    per_box: dict[str, dict] = {r: {"cells": [], "core_hours": 0.0,
                                    "core_hours_local_equiv": 0.0,
                                    "W": BOXES[r]["W"], "wall_hours": 0.0}
                                for r in BOX_ROLES}
    core = core_le = 0.0
    for c in CELLS:
        p = project_cell_cost(c, c_side=c_side, laptop_ratio=laptop_ratio)
        per_cell[c.name] = p
        b = per_box[c.box]
        b["cells"].append(c.name)
        b["core_hours"] += p["core_hours"]
        b["core_hours_local_equiv"] += p["core_hours_local_equiv"]
        core += p["core_hours"]
        core_le += p["core_hours_local_equiv"]
    for r, b in per_box.items():
        b["wall_hours"] = b["core_hours"] / float(b["W"]) if b["W"] else float("nan")
    return {
        "per_cell": per_cell, "per_box": per_box,
        "core_hours": core,
        "core_hours_local_equiv": core_le,
        #: ⭐ MAX, not sum — the boxes run concurrently.
        "wall_hours": max(b["wall_hours"] for b in per_box.values()),
        "wall_hours_single_box_local": core_le / float(BOXES["local"]["W"]),
        "c_side_ms": MS_SHAPE_C_SIDE if c_side is None else float(c_side),
        "laptop_ratio": (LAPTOP_RATIO_ASSUMED if laptop_ratio is None
                         else float(laptop_ratio)),
    }


def round_cost_envelope() -> dict:
    """DESIGN §6.2's published RANGE. ⛔ §0(a)'s funding line is the RANGE, never
    the point. TWO unmeasured inputs compound here, and both are named:

      * shape C's per-move cost (no gamma cell has ever run), and
      * the laptop's per-game ratio (`LAPTOP_RATIO_NOTE`).

    The low end takes the cheap end of both; the high end takes the dear end of
    both. Every other figure is round-1 REALIZED.
    """
    c_lo, c_hi = MS_SHAPE_C_ENVELOPE
    r_lo, r_hi = LAPTOP_RATIO_ENVELOPE
    return {
        "point": project_round_cost(),
        "low": project_round_cost(c_side=c_lo, laptop_ratio=r_lo),
        "high": project_round_cost(c_side=c_hi, laptop_ratio=r_hi),
        "why": ("TWO unmeasured inputs, compounded: shape C's per-move cost (no "
                "gamma cell has ever run) and the laptop's per-game ratio "
                "(assumed 1.3-1.5x). Every other figure is round-1 REALIZED."),
    }


#: The realized round-1 worker-seconds per game, per cell, reconstructed from the
#: launcher's own pass log (wall x W / games). `sanity_check()` requires the cost
#: model to reproduce each within 3%.
R1_REALIZED_S_PER_GAME = {"A_MID": 87.45, "B_MID": 79.2, "D_MID": 85.8}
_R1_SHAPE_MS = {"A_MID": MS_SHAPE_A_SIDE, "B_MID": MS_SHAPE_B_SIDE,
                "D_MID": MS_SHAPE_D_SIDE}


# --------------------------------------------------------------------------- #
# THE STATISTIC (READ_RULE.md §1) — the WITNESS implementation                  #
# ⛔ CARRIED VERBATIM FROM ROUND 1. Not a line moved.                            #
# --------------------------------------------------------------------------- #
def _by_deck(records: Iterable[Mapping]) -> dict[int, dict[int, float]]:
    """`{seed: {a_seat: diff}}` over records that carry all three fields.

    A record missing `seed`, `a_seat` or `diff` is DROPPED here and shows up as a
    short `n_paired` at the gate — it is never silently defaulted to zero.
    """
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
    """`D(d) = (diff(d, a_seat=0) + diff(d, a_seat=1)) / 2`, over decks that
    appear in BOTH seatings. A deck missing a seating is DROPPED — READ_RULE §1,
    and `eval_fair_puct._paired_z`'s own `if 0 in v and 1 in v`.

    `diff` is the harness's own final-score margin, CANDIDATE minus OPPONENT, in
    POINTS (`eval_fair_puct.py:1603`). Sign: `D > 0` ⇒ the CANDIDATE won.
    """
    return {s: (v[0] + v[1]) / 2.0
            for s, v in sorted(_by_deck(records).items()) if 0 in v and 1 in v}


def paired_margin(records: Iterable[Mapping]):
    """READ_RULE §1's statistic, recomputed from scratch off the raw records.

    Returns `(mean, z, n_paired, se, per_deck_list)`. Identical in construction
    to `eval_fair_puct._paired_z` (`2371-2383`): per-deck seat-balanced margin,
    SAMPLE stdev (ddof=1), `se = sd/sqrt(n)`, `z = mean/se`. Fewer than two
    paired decks ⇒ `(None, None, n, None, list)`.

    ⚠️ Accumulated with `math.fsum` rather than `sum` DELIBERATELY: the point of
    a witness is to be a different computation.
    """
    per_deck = list(per_deck_margins(records).values())
    n = len(per_deck)
    if n < 2:
        return None, None, n, None, per_deck
    mean = math.fsum(per_deck) / n
    var = math.fsum((d - mean) ** 2 for d in per_deck) / (n - 1)
    se = math.sqrt(var / n)
    z = (mean / se) if se > 0 else float("nan")
    return mean, z, n, se, per_deck


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """`eval_fair_puct._summary`'s W/D/L, winrate and elo, recomputed from the raw
    records (`2574-2586`).

    Wins come from the record's own `won_by_champ`, draws from `drew` — NOT from
    re-deriving them from `diff`, because the W/D/L classification moves under the
    WC tie rule while `diff` does not, and this pair does not run that rule.
    """
    scored = [r for r in records if isinstance(r, Mapping) and "diff" in r]
    n = len(scored)
    w = sum(1 for r in scored if r.get("won_by_champ") is True)
    d = sum(1 for r in scored if r.get("drew") is True)
    losses = n - w - d
    if n == 0:
        return {"n": 0, "W": 0, "D": 0, "L": 0, "winrate": None,
                "elo": None, "elo_sig_1sigma": None, "avg_diff": None}
    wr = (w + 0.5 * d) / n
    if 0.0 < wr < 1.0:
        elo = 400.0 * math.log10(wr / (1.0 - wr))
        sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, sig = math.copysign(800.0, wr - 0.5), float("nan")
    return {"n": n, "W": w, "D": d, "L": losses, "winrate": wr,
            "elo": elo, "elo_sig_1sigma": sig,
            "avg_diff": math.fsum(float(r["diff"]) for r in scored) / n}


def recon_close(a, b) -> bool:
    """READ_RULE §3 RECON tolerance: rel 1e-6 / abs 1e-9.

    `None` closes only to `None`: an analyzer field that is genuinely absent must
    witness absent too, not merely small. ABSENT is FAIL, never a skip.
    """
    if a is None or b is None:
        return a is None and b is None
    try:
        af, bf = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if math.isnan(af) and math.isnan(bf):
        return True
    return abs(af - bf) <= max(RECON_ATOL, RECON_RTOL * max(abs(af), abs(bf)))


# --------------------------------------------------------------------------- #
# SE MODELLING (READ_RULE.md §1, §4.3 item 2)                                   #
# --------------------------------------------------------------------------- #
def se_model(n_decks: int) -> float:
    """`SE_D(model) = 14.67 / sqrt(n_decks)`. 400 decks -> 0.7335."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    """§1: print realized vs modelled SE and FLAG a ratio outside [0.70, 1.43].
    ⛔ Reported, NEVER a branch input.

    ⚠️ Round 1 realized 0.714-0.834 on this instrument, so a LOW-end flag is
    expected and means "tighter than modelled". The HIGH end is the concerning
    direction. The band does not move for that (READ_RULE §1)."""
    modelled = se_model(n_decks)
    if realized_se is None or modelled <= 0:
        return {"realized": realized_se, "modelled": modelled, "ratio": None,
                "band": list(SE_ANOMALY_BAND), "flagged": True, "direction": None,
                "note": "SE unavailable — ABSENT is FLAGGED, never silently OK"}
    ratio = realized_se / modelled
    lo, hi = SE_ANOMALY_BAND
    flagged = not (lo <= ratio <= hi)
    return {"realized": realized_se, "modelled": modelled, "ratio": ratio,
            "band": list(SE_ANOMALY_BAND), "flagged": flagged,
            "direction": ("TIGHTER than modelled (the expected direction — round 1 "
                          "realized 0.714-0.834)" if ratio < lo else
                          "WIDER than modelled (the CONCERNING direction)" if ratio > hi
                          else "inside the band"),
            "note": "DISPERSION ANOMALY — reported, never a branch input"}


# --------------------------------------------------------------------------- #
# THE PER-CELL BRANCHES (READ_RULE.md §4) — first-match-wins                    #
# --------------------------------------------------------------------------- #
def branch_for_cell(z, gates_ok: bool) -> str:
    """READ_RULE §4's per-cell branch table, FIRST-MATCH-WINS, with
    `U-UNREADABLE` checked FIRST.

        U-UNREADABLE   any gate FAIL on the cell (or a round-wide G-WHEEL-SAME
                       fail, which the caller folds into `gates_ok`), or no z
        PROMOTE        z >= +2.0
        BRACKET        +1.0 <= z < +2.0
        REVERSED       z <= -2.0
        NULL           everything else  (-2.0 < z < +1.0)

    ⚠️ The bars are the ones READ_RULE writes: `>=`, `<=`, `<`. Exactly `+2.0`
    PROMOTES, exactly `+1.0` BRACKETS, exactly `-2.0` REVERSES.

    ⛔ ON A C CELL THE LABEL MEANS SOMETHING DIFFERENT. `PROMOTE` on a C cell is
    NOT a promotion into the four-link adoption chain — C's opponent is a
    SHAPE-B AGENT, not the champion of record, so its margin says nothing about
    play against the champion. `round_branch()` re-labels it `DEFENDS-C`, and
    `c_reading()` is the mandatory prose. This function returns the RAW ladder
    position; the round-level table applies the meaning.
    """
    if not gates_ok or z is None or (isinstance(z, float) and math.isnan(z)):
        return "U-UNREADABLE"
    if z >= PROMOTE_Z:
        return "PROMOTE"
    if z >= BRACKET_Z:          # and, by the line above, z < PROMOTE_Z
        return "BRACKET"
    if z <= REVERSED_Z:
        return "REVERSED"
    return "NULL"


# --------------------------------------------------------------------------- #
# ⭐ THE PRE-REGISTERED WITHIN-r2 LOW-vs-HIGH CONTRAST (READ_RULE.md §4.5)      #
#                                                                              #
# THE ROUND'S QUESTION IS "DOES THE SIGNAL SCALE WITH WEIGHT?", and the honest  #
# way to ask it is a contrast between two cells THIS ROUND MEASURED, on ONE     #
# band, rather than against round 1's mid on another one.                       #
#                                                                              #
#     Delta_shape = D_high - D_low                                             #
#     SE(Delta)   = sqrt(SE_high^2 + SE_low^2)                                 #
#     z_Delta     = Delta / SE(Delta)                                          #
#                                                                              #
# ⚠️ THE TWO CELLS ARE ON DISJOINT DECK RANGES (DESIGN §5.1), so this is an     #
# UNMATCHED difference of two independent samples and the root-sum-square SE is #
# the right one. CRN within a shape would have halved SE(Delta) and was         #
# deliberately NOT taken: the pair's PRIMARY statistic is each cell's own       #
# margin against zero, disjoint ranges cost that nothing, and the funded design #
# named 7 x 400 disjoint decks. The price is paid HERE and is stated: at round  #
# 1's realized dispersion SE(Delta) ~ 0.85 pts, so the contrast RESOLVES at 2σ  #
# only for |Delta| >= ~1.7 pts/deck.                                            #
#                                                                              #
# ⛔ IT IS NOT A PROMOTION INPUT. Promotion is per-cell, against zero, at the    #
# cell's own realized SE. This contrast is a SHAPE reading and a round-3 input. #
#                                                                              #
# ⚠️ NO CROSS-BAND HUMILITY DISCOUNT APPLIES: both cells are on band 152e9, in  #
# one launch window, on one instrument. CL-068's 1.8-2.2x is a CROSS-BAND       #
# figure; the deck draw differs between the two ranges and the per-deck SEM     #
# already prices exactly that.                                                 #
# --------------------------------------------------------------------------- #
def shape_contrast(low: Mapping | None, high: Mapping | None) -> dict:
    """`(D_high - D_low)` with its unmatched SE and z. ⛔ ABSENT is UNREADABLE."""
    def _get(m, k):
        return None if not isinstance(m, Mapping) else m.get(k)

    d_lo, se_lo = _get(low, "D"), _get(low, "se")
    d_hi, se_hi = _get(high, "D"), _get(high, "se")
    if any(v is None for v in (d_lo, se_lo, d_hi, se_hi)):
        return {"readable": False, "delta": None, "se": None, "z": None,
                "verdict": "UNREADABLE",
                "why": "a cell's D or SE is ABSENT — ABSENT is FAIL, never a skip"}
    delta = float(d_hi) - float(d_lo)
    se = math.sqrt(float(se_hi) ** 2 + float(se_lo) ** 2)
    z = (delta / se) if se > 0 else float("nan")
    resolved = (not math.isnan(z)) and abs(z) >= CONTRAST_Z
    return {
        "readable": True, "delta": delta, "se": se, "z": z,
        "ci95": (delta - 1.96 * se, delta + 1.96 * se),
        "verdict": ("SCALING RESOLVED" if resolved else "SCALING UNRESOLVED"),
        "direction": ("increases with weight" if resolved and delta > 0 else
                      "DECREASES with weight" if resolved and delta < 0 else
                      "not resolved at this n"),
        "why": ("UNMATCHED difference of two independent same-band cells "
                "(disjoint deck ranges), root-sum-square SE. ⛔ NEVER a promotion "
                "input; promotion is per-cell against zero."),
    }


#: §4.5's power statement for the contrast, computed BEFORE any answer exists.
CONTRAST_POWER = (
    {"sigma_model": "frozen 14.67", "se_delta": 1.0374,
     "mde_2sigma_pts": 2.0748,
     "note": "sqrt(2) x 0.7335 -- the conservative sizing model"},
    {"sigma_model": "round-1 REALIZED ~11.97", "se_delta": 0.8467,
     "mde_2sigma_pts": 1.6934,
     "note": "sqrt(2) x 0.5987 -- what round 1 actually realized on this "
             "instrument; the honest expectation"},
)


# --------------------------------------------------------------------------- #
# ⭐ SHAPE C READS DEFENCE, NOT STRENGTH (READ_RULE.md §4.6)                    #
# --------------------------------------------------------------------------- #
C_OPPONENT_NOTE = (
    "⛔ C'S OPPONENT IS AN INVADER, NOT THE CHAMPION OF RECORD. The three C "
    "cells play the champion curve125 leaf PLUS invasion_alpha 0.09 @ cap 11.0 "
    f"(leaf {SHAPE_B_LEAF_HASH}) -- bit-for-bit round 1's B_MID candidate. "
    "SHAPES.md §3 requires it: shape C is DEFENCE-ONLY and not antisymmetric, so "
    "a C-vs-champion cell is a guaranteed-uninformative null (the champion does "
    "not invade). A POSITIVE C margin therefore means THE DEFENCE PAYS AGAINST "
    "THE EXPLOIT -- it does NOT mean the agent is stronger, and it says nothing "
    "about play against the champion of record or against any out-of-lineage "
    "opponent."
)

C_NEVER_PROMOTES_ALONE = (
    "⛔ C NEVER PROMOTES PAST ITS OWN FAMILY WITHOUT AN OFFENSE PARTNER. A "
    "firing C cell does NOT enter the four-link adoption chain, because link 1 "
    "of that chain is defined as a screen AGAINST THE CHAMPION and C's opponent "
    "is not the champion. What a firing C licenses is exactly one thing: a "
    "PARTNERED follow-up -- either (i) a C-vs-E4 cell against the human invader "
    "the mechanism was discovered in, or (ii) a joint cell pairing C with a "
    "surviving offence weight so the pair can be screened against the champion "
    "as one leaf. Both are a fresh pair, a fresh band and a fresh funding "
    "decision. ⛔ No C reading of any size licenses a production H2H, a "
    "governance/PRODUCTION.yaml change, or a champion-of-record discussion."
)


def c_reading(branch: str, z, delta_note: str = "") -> str:
    """The MANDATORY prose for a C cell's branch. `READ_RULE.md` §4.6 requires it
    printed beside every C result, whatever fired."""
    base = {
        "PROMOTE": ("DEFENDS -- at this gamma the dumping-ground discount pays a "
                    "measurable margin AGAINST A SHAPE-B INVADER. " +
                    C_NEVER_PROMOTES_ALONE),
        "BRACKET": ("the defence reads >= +1σ against an invader but does not "
                    "resolve. It licenses one more gamma point on a fresh band "
                    "and nothing else. " + C_NEVER_PROMOTES_ALONE),
        "REVERSED": ("⚠️ THE DEFENCE COSTS POINTS AGAINST AN INVADER -- a real "
                     "finding, not a gate failure. The leading named hypothesis "
                     "is SHAPES.md §3's NORMALISATION caveat: frac = open_n/edges "
                     "makes the charge a rate x a value, so shape C does NOT rank "
                     "a large open city above a small fully-open feature (false in "
                     "8 of 23 one-sided census cases at the side aggregate, 15 of "
                     "23 per-feature). The named first follow-up is the "
                     "UN-NORMALISED variant (contrib = open_n x V, or V gated on "
                     "open_n >= k) -- which is A DIFFERENT SHAPE needing its own "
                     "build, fixtures and pair, NOT a re-parameterisation of this "
                     "one. ⛔ A REVERSED reading does not license flipping the "
                     "term's sign."),
        "NULL": ("a BOUND, not a zero. ⚠️ AND UNLIKE ROUND 1's DEFERRAL, THIS "
                 "NULL IS INFORMATIVE: round 1 declined to run C because a "
                 "vs-champion null was expected by construction. Here the "
                 "opponent DOES invade, so a null says the defence bought "
                 "nothing measurable against the very exploit it was built for, "
                 "at this gamma, at 2752, at this n. The bound is the cell's 95% "
                 "CI."),
        "U-UNREADABLE": "no C statistic is reported.",
    }.get(branch, "unrecognised branch")
    return f"{base} {delta_note}".strip()


# --------------------------------------------------------------------------- #
# THE ROUND-LEVEL BRANCH TABLE (READ_RULE.md §4)                                #
# --------------------------------------------------------------------------- #
def round_branch(cell_branches: Mapping[str, str]) -> str:
    """READ_RULE §4's ROUND-level reading, FIRST-MATCH-WINS.

        U-UNREADABLE      any cell unreadable (G-WHEEL-SAME voids all seven)
        PROMOTE-<shape>   some A or B cell reads z >= +2.0
                          -> licenses ONE production-budget H2H for that shape,
                             per the frozen four-link adoption chain
        DEFENDS-C         no A/B promote, but some C cell reads z >= +2.0
                          -> C-family only; NEVER the adoption chain (§4.6)
        BRACKET-CONTINUE  nothing at +2.0, but something at >= +1.0
                          -> names what a round 3 would need, and its cost
        REVERSED-<shape>  nothing at >= +1.0, but some cell reads z <= -2.0
        FAMILY-PARKS      every cell reads z < +1.0 and nothing REVERSED

    Multiple shapes may PROMOTE; the label lists them, comma-separated, in
    CELL order. ⛔ Listing two shapes is NOT two confirmations of one effect and
    NOT an additive claim — each cell was adjudicated against zero, on its own
    disjoint decks, and §1 forbids any cross-cell contrast as a branch input
    (the pre-registered low-vs-high contrast is the ONE exception and it is not
    a branch input either).
    """
    vals = [cell_branches.get(c.name) for c in CELLS]
    if any(v == "U-UNREADABLE" for v in vals) or any(v is None for v in vals):
        return "U-UNREADABLE"
    ab_promo = [c.shape for c in CELLS
                if c.shape in ("A", "B") and cell_branches.get(c.name) == "PROMOTE"]
    if ab_promo:
        seen = [s for i, s in enumerate(ab_promo) if s not in ab_promo[:i]]
        return "PROMOTE-" + ",".join(seen)
    if any(c.shape == "C" and cell_branches.get(c.name) == "PROMOTE" for c in CELLS):
        return "DEFENDS-C"
    if any(v == "BRACKET" for v in vals):
        return "BRACKET-CONTINUE"
    rev = [c.shape for c in CELLS if cell_branches.get(c.name) == "REVERSED"]
    if rev:
        seen = [s for i, s in enumerate(rev) if s not in rev[:i]]
        return "REVERSED-" + ",".join(seen)
    return "FAMILY-PARKS"


# --------------------------------------------------------------------------- #
# ⛔ THE LADDER RULES THAT CONSTRAIN EVERY FIRING BRANCH (READ_RULE.md §4.7)    #
#                                                                              #
# Round 1 recorded these and noted they would BITE in round 2. They do.         #
# --------------------------------------------------------------------------- #
#: ⭐ A AND B ARE NOT BRACKETED WITHIN ROUND 2, AND THIS IS STRUCTURAL.
#: Their round-2 ladders have TWO points, `x1/3` and `x3`, and the interior point
#: (the mid) is round 1's, ON ANOTHER BAND, admissible only as a descriptive
#: overlay. A two-point ladder has no interior, so EVERY A/B reading sits at a
#: ladder ENDPOINT by construction, and `feedback_bracket_hyperparams` says a
#: peak at an endpoint is NOT BRACKETED. Stated before any number exists.
AB_ENDPOINT_RULE = (
    "⛔ A PEAK AT A LADDER ENDPOINT IS NOT BRACKETED. Shapes A and B measure only "
    "x1/3 and x3 within round 2 -- the interior mid is round 1's, on band "
    f"{R1_BAND}, and enters as a DESCRIPTIVE OVERLAY ONLY. So every A/B reading "
    "is at an endpoint. A PROMOTE at x3 licenses the production H2H AT THAT "
    "WEIGHT and owes a ladder EXTENSION before any claim about an optimum; a "
    "PROMOTE at x1/3 owes an extension DOWNWARD. ⛔ No branch may say 'the "
    "optimum is at x3' or 'the term is monotone' from two endpoints."
)

#: ⭐ C IS THE ONLY SHAPE WITH A REAL BRACKET THIS ROUND — three points on ONE
#: band, so C_MID is a genuine INTERIOR rung and the noise-signature rule applies
#: to it literally.
C_INTERIOR_RULE = (
    "⭐ SHAPE C IS THE ONLY SHAPE BRACKETED WITHIN ROUND 2: three points "
    "(0.08 / 0.23 / 0.69) on ONE band, so C_MID is a genuine INTERIOR rung. "
    "⛔ A LONE VALUE THAT BEATS ITS NEIGHBOURS BY >1σ IS A NOISE SIGNATURE, NOT A "
    "PEAK: if C_MID fires while BOTH C_LOW and C_HIGH read >1σ lower, it is "
    "RE-MEASURED before it is believed, never promoted from the single screen. "
    "Symmetrically, a C peak at C_LOW or C_HIGH is at an endpoint and is not "
    "bracketed -- extend the ladder first."
)

NOISE_SIGNATURE_SIGMA = 1.0


def noise_signature(mid: Mapping | None, low: Mapping | None,
                    high: Mapping | None) -> dict:
    """READ_RULE §4.7's noise-signature check, for the ONE interior rung this
    round has (C_MID). ⛔ It never moves a branch; it attaches a RE-MEASURE
    obligation to one."""
    def _z(m):
        return None if not isinstance(m, Mapping) else m.get("z")

    zm, zl, zh = _z(mid), _z(low), _z(high)
    if any(v is None or (isinstance(v, float) and math.isnan(v))
           for v in (zm, zl, zh)):
        return {"applicable": False, "fired": False,
                "why": "a rung's z is ABSENT — the check is not applicable"}
    fired = (zm - zl > NOISE_SIGNATURE_SIGMA) and (zm - zh > NOISE_SIGNATURE_SIGMA)
    return {
        "applicable": True, "fired": bool(fired),
        "z_low": zl, "z_mid": zm, "z_high": zh,
        "why": ("⚠️ NOISE SIGNATURE: the interior rung beats BOTH neighbours by "
                f">{NOISE_SIGNATURE_SIGMA}σ. RE-MEASURE before believing it; do "
                "NOT promote from the single screen "
                "(feedback_results_table_source_of_truth, CLAUDE.md n-thresholds)."
                if fired else "no noise signature — the interior rung does not "
                              "beat both neighbours by >1σ"),
    }


# --------------------------------------------------------------------------- #
# THE GUARDED ELO CONVERSION (READ_RULE.md §4.4) — CARRIED VERBATIM              #
# --------------------------------------------------------------------------- #
def elo_display(z, D, elo, se) -> dict:
    """READ_RULE §4.4's two-limb conversion.

    `|z| >= 2.0`  -> limb "own-ratio": THIS cell's realized `elo/D` is reportable,
                     cross-checked against `ELO_PER_PT_BRACKET`; a reading outside
                     it is FLAGGED as a witness anomaly and is NEVER a branch input.
    otherwise     -> limb "pinned-bracket": the cell's own ratio is NOT reportable
                     and MUST NOT be printed as a scale.

    Under a null `D ~ 0`, so a cell's own `elo/D` is a quotient of two
    independently-noisy near-zero quantities: it does not converge and its SIGN
    is not stable.
    """
    lo_b, hi_b = ELO_PER_PT_BRACKET
    two_sigma_pts = (2.0 * se) if se is not None else None
    usable_z = (z is not None and not (isinstance(z, float) and math.isnan(z)))

    if usable_z and abs(z) >= PROMOTE_Z and elo is not None and D not in (None, 0, 0.0):
        epp = elo / D
        outside = not (min(lo_b, hi_b) <= abs(epp) <= max(lo_b, hi_b))
        return {
            "limb": "own-ratio",
            "label": "MEASURED SCALE — this cell's own realized elo/pt",
            "elo_per_point": epp,
            "elo_per_point_bracket": [lo_b, hi_b],
            "elo_per_point_outside_bracket": outside,
            "anomaly_note": ("⚠️ elo/pt OUTSIDE the in-family bracket "
                             f"[{lo_b}, {hi_b}] — FLAGGED as a witness anomaly, "
                             "NEVER a branch input." if outside else ""),
            "elo": elo,
            "two_sigma_pts": two_sigma_pts,
            "two_sigma_elo": (abs(epp) * two_sigma_pts) if two_sigma_pts is not None else None,
            "two_sigma_elo_lo": None, "two_sigma_elo_hi": None,
        }

    return {
        "limb": "pinned-bracket",
        "label": ("BRACKET CONVERSION, NOT A MEASURED SCALE — this cell's own "
                  "elo/D is a quotient of two noisy near-zero quantities and is "
                  "NOT reportable (READ_RULE §4.4)"),
        "elo_per_point": None,
        "elo_per_point_bracket": [lo_b, hi_b],
        "elo_per_point_outside_bracket": None,
        "anomaly_note": "",
        "elo": elo,
        "two_sigma_pts": two_sigma_pts,
        "two_sigma_elo": None,
        "two_sigma_elo_lo": (two_sigma_pts * lo_b) if two_sigma_pts is not None else None,
        "two_sigma_elo_hi": (two_sigma_pts * hi_b) if two_sigma_pts is not None else None,
    }


# --------------------------------------------------------------------------- #
# THE WHEEL PROBE CONTRACT (DESIGN.md §7, READ_RULE.md §3 G-WHEEL)              #
# ⛔ CARRIED VERBATIM FROM ROUND 1, plus the shape-B env regime.                 #
# --------------------------------------------------------------------------- #
WHEEL_PROBE_FILENAME = "WHEEL_PROBE.json"

#: Every key the launcher's wheel probe must write true. Each names a DIFFERENT
#: failure the stale wheel produces, and a `hasattr` proxy is deliberately not
#: enough for the middle one — DESIGN §7 requires the ACTUAL nonzero forward.
#: ⚠️ `opp_side_forward_ok` is NEW in round 2: the C cells forward a nonzero
#: weight on the OPPONENT side too, through the SAME `leaf_config_rs` conditional
#: kwargs, and nothing in round 1 ever exercised that direction.
WHEEL_PROBE_REQUIRED_TRUE = (
    "invasion_terms_attr",        # carc_rs.MirrorState has `invasion_terms`
    "nonzero_kwarg_forward_ok",   # leaf_config_rs(candidate cfg) built, every cell
    "cap_biconditional_ok",       # DESIGN §2.3's cap-forwarding biconditional holds
    "opp_side_forward_ok",        # the C cells' SHAPE-B OPPONENT leaf reaches rust
    "wheel_is_round_1s",          # G-WHEEL-SAME, asserted at pre-flight too
)


def wheel_probe_ok(probe: Mapping | None) -> tuple[bool, str]:
    """`(ok, reason)` for a `WHEEL_PROBE.json` payload. ABSENT is FAIL."""
    if not isinstance(probe, Mapping) or not probe:
        return False, "WHEEL_PROBE.json ABSENT or empty — ABSENT is FAIL"
    missing = [k for k in WHEEL_PROBE_REQUIRED_TRUE if probe.get(k) is not True]
    if missing:
        return False, ("wheel probe did not record a successful nonzero-kwarg "
                       f"forward on both sides: {', '.join(missing)} not true")
    if not probe.get("carc_rs_build"):
        return False, "wheel probe carries no `carc_rs_build` fingerprint"
    return True, ("wheel probe recorded a successful nonzero-kwarg forward on "
                  "BOTH sides, on round 1's own wheel")


# --------------------------------------------------------------------------- #
# SOURCE-REVISION MATCHING (READ_RULE.md §3 G-REV) — CARRIED VERBATIM            #
#                                                                              #
# ⭐ INCLUDING amendment round 2's correction: the `-dirty` suffix on `code_rev` #
# is INFORMATIONAL, not fatal. `run_manifest.code_rev()` computes dirtiness over #
# the WHOLE TREE and the main tree is perpetually dirty with measurement logs;   #
# treating that as fatal voided every healthy run. The FATAL, code-path-scoped   #
# verdict is `SRC_CLEAN.jsonl`'s.                                               #
# --------------------------------------------------------------------------- #
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"


def split_dirty(code_rev: str) -> tuple[str, bool]:
    """`(sha_part, had_dirty_marker)`. The marker is WHOLE-TREE scoped and is
    reported, never fatal."""
    s = (code_rev or "").strip()
    if s.lower().endswith(DIRTY_SUFFIX):
        return s[: -len(DIRTY_SUFFIX)], True
    return s, False


def rev_matches(code_rev, pinned) -> tuple[bool, str]:
    """`(ok, why)` — does a manifest's short `code_rev` NAME `PINNED_SRC_REV`?

    ⛔ This answers the IDENTITY question only. The CLEANLINESS question is
    `SRC_CLEAN.jsonl`'s, because only that reading is scoped to the code paths.
    """
    if not code_rev or not isinstance(code_rev, str):
        return False, "code_rev ABSENT — ABSENT is FAIL"
    if not pinned or not isinstance(pinned, str):
        return False, "PINNED_SRC_REV ABSENT — ABSENT is FAIL"
    cr, dirty = split_dirty(code_rev)
    cr = cr.lower()
    pn = pinned.strip().lower()
    note = ("; ⚠️ whole-tree `-dirty` marker present — INFORMATIONAL ONLY "
            "(the code-path verdict is SRC_CLEAN.jsonl's)" if dirty else "")
    if not is_hex40(pn):
        return False, f"PINNED_SRC_REV {pinned!r} is not a 40-hex sha{note}"
    if len(cr) < MIN_REV_PREFIX or any(ch not in "0123456789abcdef" for ch in cr):
        return False, f"code_rev {code_rev!r} is not >= {MIN_REV_PREFIX} hex chars{note}"
    if not pn.startswith(cr):
        return False, f"code_rev {code_rev!r} is not a prefix of PINNED_SRC_REV {pinned!r}{note}"
    return True, f"code_rev {code_rev!r} names PINNED_SRC_REV {pinned!r}{note}"


def is_hex40(s) -> bool:
    return (isinstance(s, str) and len(s) == 40
            and all(c in "0123456789abcdef" for c in s.lower()))


# --------------------------------------------------------------------------- #
# THE FROZEN INPUTS AND THE POWER TABLE — §4.3 items 4, 7, 8                    #
# --------------------------------------------------------------------------- #
#: DESIGN §3.2 — round 1's derivation constants, UNCHANGED. Round 2 re-picks
#: NOTHING: its weights are `x1/3` and `x3` of round 1's frozen mids, exactly as
#: round 1 named them in its own §3.4 bracket table.
FROZEN_DERIVATION = {
    "G_sibling_p90_minus_p10": 1.76,
    "target_fraction_of_G": 0.40,
    "target_contribution_pts": 0.704,
    "M_A": 6.0, "M_B": 8.0, "M_D": 6.0, "M_C": 3.03,
    "alpha_cap": 11.0,
    "stub_max_tiles": 2,
    "ladder_rule": "low = mid/3, high = mid x3 (round 1 DESIGN §3.4, named there, "
                   "not re-picked here)",
    "corroboration": ("G=1.76 (median sibling p90-p10) is independently "
                      "corroborated by the mean top1-top2 gap of 1.72, within 3%, "
                      "from a completely different definition"),
}

#: The ladder as this round runs it. `mid` is round 1's, ⛔ DESCRIPTIVE ONLY.
LADDER = {
    "A": {"knob": "invasion_beta", "low": 0.04, "mid": 0.12, "high": 0.36,
          "mid_source": f"ROUND 1, band {R1_BAND} — DESCRIPTIVE OVERLAY ONLY"},
    "B": {"knob": "invasion_alpha", "low": 0.03, "mid": 0.09, "high": 0.27,
          "note": "at cap 11.0 on every rung",
          "mid_source": f"ROUND 1, band {R1_BAND} — DESCRIPTIVE OVERLAY ONLY"},
    "C": {"knob": "invasion_gamma", "low": 0.08, "mid": 0.23, "high": 0.69,
          "note": "ALL THREE RUN THIS ROUND, on ONE band, vs a SHAPE-B AGENT",
          "mid_source": "ROUND 2 — a genuine interior rung"},
    "D": {"knob": "invasion_delta_farm", "low": 0.04, "mid": 0.12, "high": 0.36,
          "note": "⛔ NOT RUN IN ROUND 2 — see D_NOT_RUN"},
}

#: DESIGN §4.2 — computed BEFORE any answer existed. MANDATORY output on every
#: null (§4.3 item 4). ⛔ A NULL IS A BOUND, NOT A ZERO.
#: Published at BOTH dispersions: the frozen conservative model and what round 1
#: actually realized on this instrument.
POWER_TABLE = (
    {"true_effect_pts": 0.76, "z_at_model_se": 1.04, "power_model": "~18%",
     "z_at_realized_se": 1.27, "power_realized": "~24%",
     "note": "⭐ round 1's own B_MID reading (+0.7575). If the effect does NOT "
             "grow with weight, THIS ROUND CANNOT CONFIRM IT — the round is "
             "powered to detect SCALING, not to confirm the mid."},
    {"true_effect_pts": 1.20, "z_at_model_se": 1.64, "power_model": "~38%",
     "z_at_realized_se": 2.00, "power_realized": "~52%", "note": ""},
    {"true_effect_pts": 1.47, "z_at_model_se": 2.00, "power_model": "~52%",
     "z_at_realized_se": 2.45, "power_realized": "~69%", "note": ""},
    {"true_effect_pts": 1.68, "z_at_model_se": 2.29, "power_model": "~62%",
     "z_at_realized_se": 2.80, "power_realized": "80%",
     "note": "the 80%-power MDE at round 1's REALIZED dispersion"},
    {"true_effect_pts": 2.06, "z_at_model_se": 2.80, "power_model": "80%",
     "z_at_realized_se": 3.44, "power_realized": "~94%",
     "note": "the 80%-power MDE at the FROZEN conservative model"},
)

#: READ_RULE §5 — what NO branch does. Printed in full on every branch.
NO_BRANCH_DOES = (
    "No branch reports a production result — 2752 is the SCREENING budget, "
    "production is 11008. Screens aim, they don't verdict.",
    "No branch ranks the shapes against each other — the seven deck ranges are "
    "DISJOINT and §1 forbids any cross-cell contrast as a branch input. The ONE "
    "pre-registered exception is the within-shape low-vs-high contrast, and that "
    "is not a branch input either.",
    "⛔ No branch pools, z-combines or averages an r2 cell with round 1's mid. "
    "They are on DIFFERENT BANDS (CL-068: 1.8-2.2x cross-band over-dispersion, "
    "in BOTH statistics). The r1 mid is a DESCRIPTIVE OVERLAY on the ladder plot "
    "and nothing else.",
    "⛔ No branch says 'the optimum is at x3' or 'the term is monotone' from A's "
    "or B's two endpoints — a two-point ladder has no interior "
    "(feedback_bracket_hyperparams).",
    "⛔ No branch reads a C margin as evidence of STRENGTH. C's opponent is a "
    "shape-B invader, not the champion of record; a positive C margin means the "
    "DEFENCE PAYS AGAINST THE EXPLOIT and nothing more.",
    "⛔ No C reading of any size enters the four-link adoption chain, licenses a "
    "production H2H, edits governance/PRODUCTION.yaml, or opens a "
    "champion-of-record discussion.",
    "No branch says anything about shape D at any weight other than round 1's "
    "mid — D is not run.",
    "No branch treats A and D as independent — T_A == (cities+roads part) + T_D "
    "exactly. Round 2 runs no D cell, so this bites only if a readout reaches "
    "back to round 1's D_MID.",
    "No branch uses the ms/move ratio as evidence of anything but COST.",
    "No branch pools this band with any other (CL-068; band identity is "
    "load-bearing, and 152000000000 retires from confirmatory use once it has "
    "influenced a decision).",
    "No branch re-derives the weights — they are x1/3 and x3 of round 1's frozen "
    "mids, named in round 1's own DESIGN §3.4 before round 1 had an answer.",
    "⛔ No branch reads this round past a failed G-WHEEL-SAME. Round 2 carries no "
    "IDENT cell; it INHERITS round 1's, and the inheritance is valid only while "
    "the wheel that proved it is the wheel that plays.",
    "⛔ No branch reads a FAMILY-PARKS as a REFUTATION of round 1. This round is "
    "powered to detect SCALING, not to confirm round 1's mid: a flat +0.76 "
    "pts/deck effect is caught only ~24% of the time even at round 1's realized "
    "dispersion. FAMILY-PARKS bounds the GROWTH of the effect with weight, and a "
    "readout that says round 2 'failed to replicate' round 1 is wrong on the "
    "power arithmetic, not merely on the emphasis.",
    "⭐ No branch compares a LOCAL cell to a LAPTOP cell. None needs to: shapes "
    "are assigned WHOLE to one box, so every §4.5 contrast and the §4.7 noise "
    "check is within-box. The same wheel file and the same code_rev make such a "
    "comparison plausible, but this round deliberately never validated it and no "
    "branch may rest on it.",
    "⛔ No branch treats the laptop's realized per-game ratio, or shape C's "
    "realized per-move cost, as anything but COST. Both were carried as "
    "assumptions with stated envelopes; the round measures and reports them. "
    "Neither moves a bar, and no gate reads a clock.",
)

#: READ_RULE §6 — the stated prior, recorded BEFORE game 1 so the readout can be
#: SCORED against it rather than FITTED to it. ⚠️ Priors, not bars.
STATED_PRIOR = (
    "~45% FAMILY-PARKS (nothing reaches +1σ). ~25% BRACKET-CONTINUE. ~15% "
    "PROMOTE-B (B_HIGH is the single most likely firing cell: B is the only "
    "shape that reached BRACKET in round 1, at z 1.265, and x3 is where a real "
    "effect would show if it scales at all). ~8% DEFENDS-C. ~7% a REVERSED "
    "reading, concentrated on A_HIGH and B_HIGH via the opp_bonus_cap "
    "over-correction mechanism -- beta 0.36 contributes 0.36 x 6.0 = 2.16 leaf "
    "points, 123% of G, which is no longer a tilt on the leaf but a "
    "re-weighting of it. ⭐ THE SINGLE MOST IMPORTANT PRIOR: this round is "
    "powered to detect SCALING, not to confirm round 1's mid -- an effect that "
    "stays flat at +0.76 pts/deck is caught only ~24% of the time even at round "
    "1's realized dispersion."
)


def sanity_check() -> list[str]:
    """Internal consistency of the frozen spec. Returns a list of PROBLEMS (empty
    == clean). Called by the adjudicator's `--selftest` and by the instrument
    tests, so a typo in a seed range or a cost constant cannot survive to launch.
    """
    problems: list[str] = []
    seen: dict[int, str] = {}
    for c in CELLS:
        if c.n_games != 2 * c.n_decks:
            problems.append(f"{c.name}: n_games {c.n_games} != 2 * n_decks {c.n_decks}")
        for s in c.seeds:
            if s in seen:
                problems.append(f"seed {s} claimed by BOTH {seen[s]} and {c.name}")
            seen[s] = c.name
        if c.seed_start < BAND:
            problems.append(f"{c.name}: seed_start {c.seed_start} below the band {BAND}")
        if set(c.cand_invasion) - set(INVASION_DEFAULTS):
            problems.append(f"{c.name}: a candidate invasion key is not an invasion field")
        if set(c.opp_invasion) - set(INVASION_DEFAULTS):
            problems.append(f"{c.name}: an opponent invasion key is not an invasion field")
        for k, v in c.cand_invasion.items():
            if v == INVASION_DEFAULTS[k]:
                problems.append(f"{c.name}: candidate {k} frozen AT its default — it "
                                "would be dropped by _leaf_dict and could never be "
                                "observed")
        # the frozen leaf diff must be exactly the symmetric difference of the
        # two sides' non-default invasion fields
        want = set(c.cand_invasion) ^ set(c.opp_invasion)
        want |= {k for k in set(c.cand_invasion) & set(c.opp_invasion)
                 if c.cand_invasion[k] != c.opp_invasion[k]}
        if want != set(c.leaf_diff_keys):
            problems.append(f"{c.name}: leaf_diff_keys {sorted(c.leaf_diff_keys)} != the "
                            f"actual two-sided difference {sorted(want)}")
        if c.knob not in c.cand_invasion:
            problems.append(f"{c.name}: its own knob {c.knob} is not in cand_invasion")
        elif c.cand_invasion[c.knob] != c.weight:
            problems.append(f"{c.name}: weight {c.weight} != cand_invasion[{c.knob}]")
        if c.cand_leaf_hash == c.opp_leaf_hash:
            problems.append(f"{c.name}: the two sides pin the SAME leaf hash — the cell "
                            "would measure nothing")
        if c.cand_leaf_hash == PROD_LEAF_HASH:
            problems.append(f"{c.name}: a nonzero weight must MOVE the candidate hash "
                            "off the champion pin")
        if not c.allow_leaf_hash_drift:
            problems.append(f"{c.name}: every round-2 cell carries a nonzero weight and "
                            "MUST be launched with --allow-leaf-hash-drift")
        if (c.opponent == "shape_b") != c.shape_b_env:
            problems.append(f"{c.name}: opponent {c.opponent!r} disagrees with "
                            f"shape_b_env={c.shape_b_env} — the env regime IS how the "
                            "opponent leaf is set")
        if c.opponent == "shape_b" and c.opp_leaf_hash != SHAPE_B_LEAF_HASH:
            problems.append(f"{c.name}: a shape_b opponent must pin {SHAPE_B_LEAF_HASH}")
        if c.opponent == "champion" and c.opp_leaf_hash != PROD_LEAF_HASH:
            problems.append(f"{c.name}: a champion opponent must pin {PROD_LEAF_HASH}")
        if c.leaf_json not in LEAF_JSON_BODIES:
            problems.append(f"{c.name}: no frozen JSON body for {c.leaf_json}")
        if c.box not in BOXES:
            problems.append(f"{c.name}: box {c.box!r} is not a known role")
    # ⭐ EVERY SHAPE MUST SIT WHOLLY ON ONE BOX (BOX_ASSIGNMENT_RULE). If a shape
    # were split, §4.5's low-vs-high contrast would be a CROSS-BOX statistic and
    # the round would be relying on float identity between two machines — which
    # this program has been bitten by (the Xeon's AVX-512 G0 failure).
    for sh in SHAPES:
        boxes = {c.box for c in cells_of_shape(sh)}
        if len(boxes) != 1:
            problems.append(f"shape {sh} is SPLIT across boxes {sorted(boxes)} — "
                            "§4.5's contrast would become a cross-box statistic")
    for role in BOX_ROLES:
        if not cells_of_box(role):
            problems.append(f"box {role} has no cells — the owner directed BOTH "
                            "boxes be used")
        sm = SMOKE_BY_BOX.get(role)
        if not sm:
            problems.append(f"box {role} has no §9 smoke leg")
        elif cell_by_name(sm["cell"]).box != role:
            problems.append(f"box {role}'s smoke runs {sm['cell']}, which is frozen "
                            f"to {cell_by_name(sm['cell']).box} — a box must smoke "
                            "a config it will actually run")
    # the per-box smoke ranges must be disjoint from each other AND from every cell
    smoke_seen: dict[int, str] = {}
    for role, sm in SMOKE_BY_BOX.items():
        for s in range(sm["seed_start"], sm["seed_start"] + SMOKE_DECKS):
            if s in smoke_seen:
                problems.append(f"SMOKE seed {s} claimed by BOTH {smoke_seen[s]} "
                                f"and {role}")
            smoke_seen[s] = role
            if s in seen:
                problems.append(f"SMOKE seed {s} ({role}) overlaps cell {seen[s]}")
    # the seven ranges must be CONTIGUOUS as well as disjoint (DESIGN §5.1)
    ordered = sorted(CELLS, key=lambda c: c.seed_start)
    for a, b in zip(ordered, ordered[1:]):
        if b.seed_start != a.seed_end + 1:
            problems.append(f"gap/overlap between {a.name} and {b.name}")
    if SMOKE_CELL not in CELL_NAMES:
        problems.append(f"SMOKE_CELL {SMOKE_CELL!r} is not a cell")
    # every shape must have exactly one low and one high (the contrast needs both)
    for sh in SHAPES:
        rungs = [c.rung for c in cells_of_shape(sh)]
        if rungs.count("low") != 1 or rungs.count("high") != 1:
            problems.append(f"shape {sh}: the low-vs-high contrast needs exactly one "
                            f"low and one high rung, got {rungs}")
    # ⭐ THE COST MODEL MUST REPRODUCE ROUND 1's REALIZED WORKER-SECONDS PER GAME
    for cell_name, realized in R1_REALIZED_S_PER_GAME.items():
        modelled = MOVES_PER_SIDE * (_R1_SHAPE_MS[cell_name] + MS_CHAMPION_SIDE) \
            / 1000.0 * OVERHEAD
        if abs(modelled - realized) / realized > 0.03:
            problems.append(f"cost model reproduces round 1's {cell_name} at "
                            f"{modelled:.2f} s/game vs realized {realized:.2f} "
                            "— more than 3% off")
    lo, hi = MS_SHAPE_C_ENVELOPE
    if not (lo <= MS_SHAPE_C_SIDE <= hi):
        problems.append("the shape-C point estimate is outside its own envelope")
    return problems


if __name__ == "__main__":  # pragma: no cover — a convenience for the launcher
    import json as _json
    import sys as _sys
    bad = sanity_check()
    env = round_cost_envelope()
    print(_json.dumps({
        "band": BAND,
        "boxes": {r: {"W": BOXES[r]["W"], "share_mount": BOXES[r]["share_mount"],
                      "cells": [c.name for c in cells_of_box(r)],
                      "smoke": SMOKE_BY_BOX[r]} for r in BOX_ROLES},
        "cells": [{"name": c.name, "shape": c.shape, "box": c.box, "rung": c.rung,
                   "knob": c.knob, "weight": c.weight,
                   "seed_start": c.seed_start, "seed_end": c.seed_end,
                   "n_decks": c.n_decks, "n_games": c.n_games,
                   "out_subdir": c.out_subdir, "leaf_json": c.leaf_json,
                   "cand_leaf_hash": c.cand_leaf_hash,
                   "opp_leaf_hash": c.opp_leaf_hash,
                   "opponent": c.opponent, "shape_b_env": c.shape_b_env,
                   "leaf_diff_keys": sorted(c.leaf_diff_keys),
                   "allow_leaf_hash_drift": c.allow_leaf_hash_drift}
                  for c in CELLS],
        "round_cost_point": env["point"]["core_hours"],
        "round_cost_low": env["low"]["core_hours"],
        "round_cost_high": env["high"]["core_hours"],
        "round_cost_local_equiv": env["point"]["core_hours_local_equiv"],
        "wall_hours_point": env["point"]["wall_hours"],
        "wall_hours_single_box_local": env["point"]["wall_hours_single_box_local"],
        "per_box": {r: {"cells": b["cells"], "core_hours": b["core_hours"],
                        "wall_hours": b["wall_hours"], "W": b["W"]}
                    for r, b in env["point"]["per_box"].items()},
        "inherited_ident": R1_IDENT,
        "sanity_problems": bad,
    }, indent=2))
    _sys.exit(1 if bad else 0)
