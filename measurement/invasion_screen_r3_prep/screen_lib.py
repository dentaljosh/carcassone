#!/usr/bin/env python3
"""INVASION-RISK TERM FAMILY — ROUND-3 FINE LADDERS + JOINT AT 2752 — BAR LIBRARY.

⛔ **THIS FILE IS THE ONE IMPLEMENTATION OF EVERY BAR, EVERY CONSTANT AND EVERY
COST FIGURE THIS PAIR USES.** `READ_RULE.md` §7:

    "Every bar and every constant lives in `screen_lib.py`, imported by both the
     adjudicator and the launcher's precondition ladder, so the launcher's
     in-flight per-cell pre-check and the adjudicator's own gates cannot drift
     apart. The launcher pins ONLY the band as a numeric literal; every other
     constant is read from the library."

INHERITANCE — THIS IS ROUND 2'S INSTRUMENT, AMENDED, NOT A NEW ONE
==================================================================
`measurement/invasion_screen_r2_prep/` (round 2, band 152000000000) ran seven
cells across two boxes and adjudicated `BRACKET-CONTINUE`. Its launcher,
adjudicator, bar library and instrument tests are battle-proven, and this pair is
a copy-and-adapt of them **plus round 2's one post-freeze amendment**, changing
only what round 3 requires:

  1. EIGHT cells on a FRESH band (153000000000): a THREE-POINT FINE LADDER for
     shape A, a THREE-POINT FINE LADDER for shape C, and ⭐ TWO JOINT A+C CELLS.
  2. ⭐ **THE JOINT CELLS ARE THE ADOPTION-CHAIN-ELIGIBLE ONES.** Their opponent
     is the CHAMPION OF RECORD, and their candidate is the champion leaf carrying
     a light `invasion_beta` AND a light `invasion_gamma` **as one leaf**. A joint
     cell at `z >= +2.0` fires `PROMOTE-JOINT` and licenses the production H2H per
     the frozen four-link chain. ⛔ AND IT LICENSES IT FOR THE PACKAGE, NOT FOR A
     PART: see `JOINT_ATTRIBUTION_BAN`.
  3. ⭐ **SHAPE B IS NOT A CANDIDATE ANYWHERE IN THIS ROUND** — round 2 demoted it
     (both rungs NULL, `z` +0.04 / -1.00, a noise signature). ⛔ BUT IT REMAINS THE
     INVADER-GENERATOR **INSTRUMENT** on all three C cells, exactly as in round 2:
     C is DEFENCE-ONLY and needs something that invades to defend against. Using a
     demoted shape as an instrument is not a claim about it as a candidate. See
     `SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE`.
  4. ⭐ **BOTH A AND C ARE GENUINELY BRACKETED THIS ROUND** — three points each,
     on ONE band, so each has a real INTERIOR rung and §4.7's noise-signature rule
     applies to BOTH literally. Round 2 could say that of C only.
  5. ⭐ **`G-REV`'s CROSS-BOX CLAUSE IS THE IS-A1 FOLD.** Round 2's frozen
     adjudicator compared the two boxes' EMITTED SHORT REVS for string equality
     and falsely voided a healthy single-rev round (`AMENDMENTS.md` IS-A1). The
     canonicalized form is folded in HERE, in the library, as
     `cross_box_rev_gate()` — revs are canonicalized AGAINST THE PIN, never
     compared rev-to-rev — and it is STRICTER than the amendment script, because
     it also requires the two boxes' pins to agree.

⚠️ **STDLIB ONLY, DELIBERATELY.** Nothing here imports `carcassonne_ai`,
`eval_fair_puct`, numpy or the rust bindings. The launcher's precondition ladder
runs this module *before* the wheel has been proven.

⚠️ **`paired_margin()` IS A DELIBERATELY INDEPENDENT RE-IMPLEMENTATION** of
`eval_fair_puct._paired_z`, NOT an import of it (`READ_RULE.md` §3 `RECON`).

⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every number below
exists before any game does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- #
# THE BAND (DESIGN.md §5)                                                      #
#                                                                              #
# The all-branches sweep of 2026-08-27 (147 refs = 127 refs/heads + 20          #
# refs/remotes, 808 registry-and-claim files) found 153000000000 free           #
# EVERYWHERE: every mention of any band at or above 152e9, on any ref, is round #
# 2's OWN (152e9 and its 152999999xxx smoke ranges), and a direct               #
# `^15[3-9]000000000,` row-start grep over every ref's BAND_REGISTRY.csv        #
# returned ZERO hits. 152000000000 is SPENT by round 2.                        #
# `WORKERS.conf` pins the same integer as its ONE numeric literal and           #
# `tests/test_invasion_screen_r3_instrument.py` asserts the two agree.          #
# --------------------------------------------------------------------------- #
BAND = 153000000000

# --------------------------------------------------------------------------- #
# THE LEAVES (DESIGN.md §2.2, §2.5; READ_RULE.md §3 G-LEAF)                     #
# --------------------------------------------------------------------------- #
#: The champion of record's leaf (governance/PRODUCTION.yaml). It is the
#: OPPONENT on the three A cells AND on the two JOINT cells — ⭐ which is exactly
#: what makes those five cells adoption-chain-eligible. It is NOT the opponent on
#: the three C cells: see `SHAPE_B_LEAF_HASH`.
PROD_LEAF_HASH = "a36d2e15a3b3d71d"
CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)

#: ⭐ THE SHAPE-B AGENT'S LEAF — the OPPONENT on all three C cells, unchanged
#: from round 2: the champion curve125 leaf PLUS `invasion_alpha 0.09 @ cap 11.0`,
#: i.e. BIT-FOR-BIT round 1's `B_MID` CANDIDATE.
SHAPE_B_LEAF_HASH = "42adadc988784b44"

#: ⭐ THE POINT ROUND 3 HAS TO STATE OUT LOUD, because round 2 changed B's status.
SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE = (
    "⭐ SHAPE B IS THE INVADER-GENERATOR INSTRUMENT, NOT A CANDIDATE. Round 2 "
    "DEMOTED B as a candidate: both rungs read NULL (B_LOW D -0.6175 z -1.000; "
    "B_HIGH D +0.0225 z +0.037) around round 1's B_MID +0.7575 — a lone interior "
    "value beating both its neighbours, i.e. the NOISE SIGNATURE that "
    "feedback_results_table_source_of_truth names, not a peak. ⛔ ROUND 3 RUNS NO "
    "B CANDIDATE CELL AND NO BRANCH MAY SAY ANYTHING ABOUT B AS A CANDIDATE. "
    "⚠️ BUT B REMAINS THE OPPONENT ON ALL THREE C CELLS, at alpha 0.09 @ cap 11.0 "
    f"(leaf {SHAPE_B_LEAF_HASH}), because SHAPES.md §3 makes shape C DEFENCE-ONLY: "
    "a C cell needs an opponent that INVADES, and B is the only invader this "
    "program has built. USING A DEMOTED SHAPE AS AN INSTRUMENT IS NOT A CLAIM "
    "ABOUT IT AS A CANDIDATE — the C cells ask 'does gamma defend against this "
    "exploit', which is a well-posed question whether or not the exploit is worth "
    "playing. ⛔ AND IT IS THE **SAME** INSTRUMENT ROUND 2 USED, bit-for-bit, so "
    "the C ladders of the two rounds differ in gamma and in BAND and in nothing "
    "else."
)

#: ⭐ HOW THE C CELLS GET A NON-CHAMPION OPPONENT — the mechanism, in one place,
#: carried verbatim from round 2 (DESIGN §2.5).
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
#: the env's shape-B knobs and the cell would be "B AND C vs B", not "C vs B".
#: `G-SINGLEVAR(b)` and `G-INVASION` both check it.
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
# ⭐ THE INHERITED IDENT — inherited a SECOND time, on the SAME condition       #
#                                                                              #
# Round 1's IDENT cell (400 games, band 151000000000) asked the game-level      #
# weight-0 identity question and PASSED on every conjunct:                     #
#                                                                              #
#     |z| = 0.9624 <= 2.0  (D +0.8325, SE 0.8650, n_paired 200)                #
#     cand_leaf_hash == opp_leaf_hash == a36d2e15a3b3d71d (the champion pin)   #
#     n_failed == 0 · leaf diff EMPTY                                          #
#                                                                              #
# Round 2 inherited it under `G-WHEEL-SAME` and the inheritance HELD: all seven #
# of its cells reported binary_sha a9ac686bca1417f9 and every G-WHEEL-SAME      #
# passed. ROUND 3 INHERITS IT AGAIN, ON THE IDENTICAL CONDITION, and the        #
# condition is MECHANISED unchanged:                                           #
#                                                                              #
# ⛔ `G-WHEEL-SAME` REFUSES THE ROUND unless the emitted manifest's             #
#    `carc_rs_binary_sha` is BYTE-IDENTICAL to a9ac686bca1417f9.               #
#    A CHANGED WHEEL RE-OWES AN IDENT CELL.                                    #
#                                                                              #
# ⚠️ THE FINGERPRINT IS `carc_rs_binary_sha` **ALONE**, and round 2 learned why #
# the hard way (its `--selftest` failed against round 1's own emitted archive   #
# when the gate also compared `carc_rs_build`). `rust_agent.carc_rs_build_id()` #
# composes `carc_rs-<cargo version>+<REPO REV AT CALL TIME>+rustc<toolchain>` — #
# the rev is `run_manifest`'s, read off the WORKING TREE when the manifest is   #
# written. It is NOT compiled into the wheel and it does NOT move when the      #
# wheel does. Round 2's own archives prove it again: its seven cells emitted    #
# build strings carrying `240626a31fee` while round 1's carried `ac709c42c6e2`, #
# and the binary sha was IDENTICAL across all eleven. The build string is       #
# REPORTED beside the sha as INFORMATIONAL; the code-rev question is `G-REV`'s. #
#                                                                              #
# ⚠️ AND IT IS A SAME-BOX GATE, DELIBERATELY. `carc_rs_binary_sha` is BOX-LOCAL:#
# two boxes compiling identical source with an identical toolchain produce      #
# different bytes (measured 2026-08-17). ⭐ ROUND 2 PROVED THE SHIPPED-WHEEL     #
# ANSWER WORKS: ONE wheel FILE installed on both boxes made the sha identical   #
# on all seven cells across both machines. ROUND 3 SHIPS THE SAME FILE.         #
# ⛔ NEVER a laptop-local rebuild.                                              #
# --------------------------------------------------------------------------- #
R1_WHEEL_BINARY_SHA = "a9ac686bca1417f9"
#: ⛔ INFORMATIONAL ONLY — see the banner. NOT a discriminator, NOT gated on.
R1_WHEEL_BUILD_INFORMATIONAL = "carc_rs-0.1.0+ac709c42c6e2+rustcunpinned"
R2_WHEEL_BUILD_INFORMATIONAL = "carc_rs-0.1.0+240626a31fee+rustcunpinned"
R1_IDENT = {
    "band": 151000000000,
    "n_games": 400, "n_paired": 200, "n_failed": 0,
    "D": 0.8325, "SE": 0.8650404288051147, "z": 0.9623827653349533,
    "bar": 2.0,
    "cand_leaf_hash": PROD_LEAF_HASH, "opp_leaf_hash": PROD_LEAF_HASH,
    "verdict": "PRECONDITION-PASS",
    "cost_multiplier": 0.996988008636405,
    "inherited_by": "round 2 (held: 7/7 cells reported the pinned sha), and now round 3",
    "note": ("the ≈1.0 cost CONTROL as well as the wiring proof: with both sides "
             "weight-0 the candidate/opponent ms-per-move ratio was 0.997"),
}


def wheel_is_r1s(binary_sha, build=None) -> tuple[bool, str]:
    """`G-WHEEL-SAME` — the ROUND-LEVEL gate that carries round 1's IDENT PASS
    forward for a SECOND round. ⛔ ABSENT is FAIL, and a FAIL VOIDS EVERY CELL.

    ⛔ KEYED ON `carc_rs_binary_sha` ALONE. `build` is accepted and ECHOED for the
    record but is NOT compared: it embeds the REPO REV AT CALL TIME, not a
    compiled-in value. ⚠️ `carc_rs_version` is permanently "0.1.0" and is NEVER a
    discriminator.
    """
    if not binary_sha or not isinstance(binary_sha, str):
        return False, ("carc_rs_binary_sha ABSENT — ABSENT is FAIL. Round 3 "
                       "inherits round 1's IDENT PASS (via round 2) and cannot "
                       "verify the inheritance without the wheel fingerprint.")
    if binary_sha != R1_WHEEL_BINARY_SHA:
        return False, (
            f"THE WHEEL MOVED: carc_rs_binary_sha {binary_sha!r} vs the pinned "
            f"{R1_WHEEL_BINARY_SHA!r}. ⛔ ROUND 3 CARRIES NO IDENT CELL — it "
            "inherits round 1's game-level weight-0 identity proof (which round 2 "
            "already carried once), and that inheritance is valid ONLY while the "
            "wheel that proved it is the wheel that plays. A CHANGED WHEEL RE-OWES "
            "AN IDENT CELL: add one (400 decks / 800 games on a fresh sub-range, "
            "~15 core-h at this round's cell size) and re-freeze, or reinstall the "
            "wheel round 1 ran. ⚠️ A DIFFERENT BOX ALSO FAILS THIS, CORRECTLY: the "
            "sha is box-local, which is why ONE WHEEL FILE is shipped to both "
            "boxes rather than rebuilt on each. Do NOT read this round past this "
            "gate.")
    return True, ("the installed wheel is byte-identical to the one round 1's IDENT "
                  "PASS was measured on, and round 2 played on"
                  + (f" (build string {build!r} — INFORMATIONAL, a code-rev fact, "
                     "not compared)" if build else ""))


# --------------------------------------------------------------------------- #
# ⭐ THE TWO BOXES (DESIGN.md §6.5)                                            #
#                                                                              #
# Round 2's owner directive ("get round 2 on both local and laptop") stands for #
# round 3. ⭐ AND ROUND 3 CARRIES A SECOND, TIGHTER OWNER CONSTRAINT:           #
#                                                                              #
#     "limit local to w14 starting at 11am"   (owner, 2026-08-27)              #
#                                                                              #
# The round straddles 11:00 EDT (15:00Z), which is the owner's interactive-use  #
# window, and `feedback_desktop_friendly_selfplay` is the standing rule for it. #
# ⛔ SO `W_LOCAL` IS FROZEN AT **14** FOR EVERY LOCAL CELL OF THE WHOLE ROUND — #
# NOT 22-then-14. Three reasons, all structural:                               #
#                                                                              #
#   (a) `--workers` is a PER-INVOCATION argv value, and a cell runs in bounded  #
#       resumable PASSES. A mid-round change would make one cell's passes run at #
#       two different W, so the launcher's own realized worker-s/game log would  #
#       stop being comparable across the passes of a single cell — the one       #
#       operational number this round is trying to measure honestly.            #
#   (b) A frozen pair does not move after the blind commit, and `W` is a frozen  #
#       operational constant of it. "Change W at 11:00" is a mid-round edit to a #
#       frozen constant, which the ceremony does not have a mechanism for and    #
#       which no gate could witness after the fact.                             #
#   (c) The cheap direction is obvious: 14 for the whole round costs ~0.9 h of   #
#       laptop-bounded wall (the laptop is the critical path either way at this  #
#       split — see the table in DESIGN §6.5), and buys certainty that no local  #
#       cell ever competes with the desktop.                                    #
#                                                                              #
# ⚠️ AND IT MOVES NO BAR. `W` IS THROUGHPUT-ONLY: games are BIT-IDENTICAL at any #
# `W` (the determinization merge is a sequential post-join fold —               #
# rust/carc/carc-core/src/fair/mod.rs 22-32). No statistic, gate, claim or       #
# branch in this pair is a function of `W` or of any clock.                     #
#                                                                              #
# ⛔ THE CELL->BOX ASSIGNMENT IS FROZEN IN THE PREREG, WHOLE CELLS PER BOX, AND  #
# `G-HOST` ENFORCES IT AGAINST THE EMITTED MANIFEST. A cell's records are NEVER  #
# split across boxes: a mixed-host archive is a provenance smell with no         #
# recovery, and the manifest's `host` is the ONLY host witness the harness       #
# emits (the per-game records carry no host field at all).                       #
#                                                                              #
# ⭐ WHY OUTCOMES ARE COMPARABLE ACROSS THE TWO BOXES AT ALL — unchanged from    #
# round 2, and round 2 is now the evidence rather than the argument: ONE WHEEL   #
# FILE was installed on both boxes and all seven cells reported the IDENTICAL    #
# `carc_rs_binary_sha`. Two mitigations, both frozen again:                      #
#   (a) the SAME WHEEL FILE on both boxes, so `G-WHEEL-SAME` passes on both. ⛔ A #
#       laptop-local REBUILD produces different bytes and the gate REFUSES.      #
#   (b) ⛔ **NO PRE-REGISTERED STATISTIC IS EVER COMPUTED ACROSS THE TWO BOXES.**#
#       See `BOX_ASSIGNMENT_RULE`. This is the load-bearing one.                 #
# --------------------------------------------------------------------------- #
#: Per-box operational constants. ⚠️ `W` is THROUGHPUT-ONLY.
BOXES: dict[str, dict] = {
    "local": {
        "label": "the local 5900XT (16C/32T)",
        #: ⛔ 14, NOT round 2's 22 — the owner's interactive window. FROZEN FOR THE
        #: WHOLE ROUND; see the banner above and `W_LOCAL_NOTE`.
        "W": 14,
        #: ⚠️ THE SHARE MOUNT SPELLING DIFFERS BY BOX (CLAUDE.md).
        "share_mount": "/mnt/c/carc-shared",
        #: the calibration box: every local-equivalent ms/move figure in this file
        #: is ITS realized number, so its per-game ratio is 1.0 by definition.
        "per_game_ratio": 1.0,
        "ratio_is_measured": True,
    },
    "laptop": {
        "label": "the laptop (24T, 11 GB) via `ssh laptop-wsl`",
        #: unchanged from round 2, which ran three cells at it cleanly.
        "W": 22,
        "share_mount": "/mnt/carc-shared",
        #: ⭐ MEASURED THIS TIME, NOT ASSUMED. See `LAPTOP_RATIO_NOTE`.
        "per_game_ratio": 1.0935,
        "ratio_is_measured": True,
    },
}
BOX_ROLES = tuple(BOXES)

W_LOCAL_NOTE = (
    "⛔ W_LOCAL = 14 FOR THE WHOLE ROUND, frozen at the blind commit. Owner "
    "constraint 2026-08-27, verbatim: \"limit local to w14 starting at 11am\" — "
    "the round straddles 11:00 EDT / 15:00Z, the owner's interactive-use window "
    "(feedback_desktop_friendly_selfplay). ⛔ NOT 22-then-14: `--workers` is a "
    "PER-INVOCATION argv value and a cell runs in bounded resumable passes, so a "
    "mid-round change would run one cell's passes at two different W and destroy "
    "the comparability of the launcher's own realized worker-s/game log; and a "
    "frozen pair does not move after the blind commit. ⚠️ IT MOVES NO BAR: W is "
    "THROUGHPUT-ONLY, games are bit-identical at any W, and no gate in this pair "
    "reads a clock. It moves WALL CLOCK and the CELL->BOX ASSIGNMENT, and nothing "
    "else — and the assignment change is priced in DESIGN §6.5's split table, "
    "computed at W_LOCAL=14 rather than inherited from round 2."
)

#: ⭐ MEASURED, NOT ASSUMED — round 3's one genuine operational upgrade over
#: round 2, and it comes free from round 2's own archives.
#:
#: Round 2 carried the laptop's per-game cost as an ASSUMED 1.4x local inside a
#: 1.3-1.5x envelope, because no cell had ever run the same configuration on both
#: boxes. ⭐ IT HAD, BY ACCIDENT OF DESIGN: the SHAPE-B LEAF (invasion_alpha 0.09
#: @ cap 11.0) ran on the LOCAL box as the B cells' CANDIDATE and on the LAPTOP as
#: the C cells' OPPONENT. Same leaf, same budget, same wheel, same code rev:
#:
#:     local  (B_LOW/B_HIGH candidate)  632.20 / 634.63 ms/move -> mean 633.42
#:     laptop (C_*/opponent)     696.84 / 687.37 / 693.78 ms/move -> mean 692.66
#:     ratio  692.66 / 633.42 = 1.0935
#:
#: ⛔ SO THE 1.4x ASSUMPTION WAS ~28% TOO PESSIMISTIC and round 2's published
#: laptop ETA over-stated its wall by the same factor. Round 3 uses the measured
#: 1.0935 and reports the residual honestly.
#: ⚠️ WHAT IT IS NOT: this is a SHAPE-MATCHED ratio on ONE workload class (a rust
#: both-sides eval_fair_puct head-to-head at 2752). It does NOT transfer to the
#: python-backend cells where `track_d1_fair_rebase` read +73%, and no branch may
#: quote it as a general laptop-vs-local figure.
#: ⚠️ AND IT MOVES NO BAR. It is a WALL-CLOCK number.
LAPTOP_RATIO_MEASURED = 1.0935
LAPTOP_RATIO_ENVELOPE = (1.05, 1.15)
LAPTOP_RATIO_NOTE = (
    "⭐ MEASURED, not assumed (round 2's was assumed 1.4x): the IDENTICAL shape-B "
    "leaf ran on BOTH boxes in round 2 — local 633.42 ms/move as the B cells' "
    f"candidate, laptop 692.66 ms/move as the C cells' opponent — giving "
    f"{LAPTOP_RATIO_MEASURED}x, inside a {LAPTOP_RATIO_ENVELOPE[0]}-"
    f"{LAPTOP_RATIO_ENVELOPE[1]}x envelope. ⚠️ SHAPE-MATCHED AND WORKLOAD-SCOPED: "
    "rust both sides at 2752. It does NOT transfer to python-backend cells "
    "(track_d1_fair_rebase read +73% there). ⚠️ It moves no bar and no branch — "
    "this pair is sims-denominated and no gate reads a clock."
)

#: ⭐ THE ASSIGNMENT RULE, and the arithmetic behind it (DESIGN §6.5).
#: ⛔ IT IS NOT ROUND 2'S ASSIGNMENT. W_LOCAL=14 moves the balance point, and the
#: whole-shape split that minimises the round wall FLIPS: the C ladder goes LOCAL
#: and the A ladder + both JOINT cells go to the LAPTOP.
BOX_ASSIGNMENT_RULE = (
    "⛔ EVERY PRE-REGISTERED CONTRAST IS WITHIN ONE BOX. Shapes are assigned "
    "WHOLE: the C fine ladder (three cells) to the LOCAL box at W=14, and the A "
    "fine ladder plus BOTH JOINT cells (five cells) to the LAPTOP at W=22. So "
    "§4.5's low-vs-high contrast is within-box for all three shapes, §4.5b's "
    "three-point interior-lift statistic is within-box for A and for C, and "
    "§4.7's noise-signature check on BOTH interior rungs is within-box too. "
    "⭐ THIS IS NOT A CONVENIENCE -- it is what lets the round avoid relying on "
    "cross-box float identity, which this program has been bitten by before (the "
    "Xeon's AVX-512 G0 failure, 2026-08-02). Each cell's own margin is a "
    "WITHIN-CELL, WITHIN-BOX, deck-paired statistic in any case: both sides of a "
    "cell run in the same process on the same box at the same budget. "
    "⚠️ AND IT IS ALSO THE FASTEST SPLIT AT THIS ROUND'S W. ⛔ IT IS THE OPPOSITE "
    "OF ROUND 2's, and deliberately so: at W_LOCAL=22 the fastest whole-shape "
    "split put the expensive C shape on the laptop (round 2's), but the owner's "
    "W_LOCAL=14 constraint cuts local throughput by 36% and moves the balance "
    "point past the flip. All SIX whole-shape partitions were computed at "
    "W_LOCAL=14 / W_LAPTOP=22 and are tabulated in DESIGN §6.5(iii): this one "
    "reads 4.98 h round wall (local 4.43 h / laptop 4.98 h) against 5.22 / 5.92 / "
    "7.15 / 7.51 / 8.51 h for the five alternatives, and sits 4.7% off the "
    "unconstrained ideal of 4.75 h."
)


# --------------------------------------------------------------------------- #
# THE EIGHT CELLS (DESIGN.md §3, §5.1)                                          #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CellSpec:
    """One cell of round 3. Every field is frozen by `DESIGN.md`; nothing here is
    chosen by this file.

    ⭐ `knobs`/`weights` ARE TUPLES, not the singular pair round 2 carried. Two of
    round 3's eight cells move TWO knobs on ONE candidate leaf (the JOINT cells),
    and a schema that could only express one weight would have forced the joint to
    be described somewhere other than the cell table — which is exactly how a
    launcher and a bar library drift apart.
    """

    name: str                       # A_LOW | A_MID | A_HIGH | J_LOW | J_HIGH | C_LOW | C_MID | C_HIGH
    shape: str                      # A | C | J
    box: str                        # ⭐ FROZEN box role: "local" | "laptop" (G-HOST)
    rung: str                       # low | mid | high  (position on the shape's ladder)
    knobs: tuple                    # the weight knob(s) this cell moves — ONE, or TWO on a J cell
    weights: tuple                  # their frozen values, positionally
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

    @property
    def dose(self) -> dict:
        """`{knob: weight}` — the cell's full dose, however many knobs it moves."""
        return dict(zip(self.knobs, self.weights))

    @property
    def dose_label(self) -> str:
        """`invasion_beta=0.05` / `invasion_beta=0.05+invasion_gamma=0.07`."""
        return "+".join(f"{k}={w}" for k, w in zip(self.knobs, self.weights))

    @property
    def is_joint(self) -> bool:
        """⭐ Two knobs on ONE candidate leaf. See `JOINT_ATTRIBUTION_BAN`."""
        return len(self.knobs) > 1

    @property
    def chain_eligible(self) -> bool:
        """⭐ Does a PROMOTE on this cell enter the four-link adoption chain?

        The chain's link 1 is defined as a screen AGAINST THE CHAMPION OF RECORD,
        so the answer is exactly "is the opponent the champion" — TRUE on the A
        and J cells, FALSE on the C cells (whose opponent is the shape-B invader).
        ⛔ It is NOT "did the cell read well".
        """
        return self.opponent == "champion"


#: The candidate JSON every cell carries, as a dict — the file on disk must equal
#: this, and `tests/test_invasion_screen_r3_instrument.py` asserts it does.
#: ⚠️ Every JSON carries `v29_meeple_curve` EXPLICITLY: `_load_cand_leaf_cfg`
#: replaces named fields on the ENV `DEFAULT_CONFIG`, which is CURVE100, and
#: `_assert_netprior_leaf` HARD-fails on a candidate whose curve is not curve125
#: — even with `--allow-leaf-hash-drift`.
LEAF_JSON_BODIES: dict[str, dict] = {
    # --- shape A fine ladder: ONE knob, PLAIN regime, CHAMPION opponent --------
    "leaf_a_low.json":  {"v29_meeple_curve": list(CURVE125), "invasion_beta": 0.02},
    "leaf_a_mid.json":  {"v29_meeple_curve": list(CURVE125), "invasion_beta": 0.05},
    "leaf_a_high.json": {"v29_meeple_curve": list(CURVE125), "invasion_beta": 0.1},
    # --- ⭐ THE JOINT CELLS: TWO knobs on ONE leaf, PLAIN regime, CHAMPION -----
    # ⛔ NO explicit alpha zeros here, and that is correct rather than an omission:
    # the J cells run in the PLAIN env regime (shape_b_env=False), so the env
    # carries alpha 0.0 / cap 0.0 already and the candidate has nothing to
    # neutralise. The explicit zeros exist ONLY on the C cells, where the env is
    # deliberately armed. `G-INVASION` checks the resulting block either way.
    "leaf_j_low.json":  {"v29_meeple_curve": list(CURVE125),
                         "invasion_beta": 0.02, "invasion_gamma": 0.03},
    "leaf_j_high.json": {"v29_meeple_curve": list(CURVE125),
                         "invasion_beta": 0.05, "invasion_gamma": 0.07},
    # --- shape C fine ladder: gamma only, SHAPE-B regime, INVADER opponent -----
    # ⛔ THE EXPLICIT ZEROS. See SHAPE_B_ENV's banner: without them the candidate
    # inherits the env's shape-B knobs and the cell is not single-variable.
    "leaf_c_low.json":  {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.0,
                         "invasion_alpha_cap": 0.0, "invasion_gamma": 0.03},
    "leaf_c_mid.json":  {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.0,
                         "invasion_alpha_cap": 0.0, "invasion_gamma": 0.07},
    "leaf_c_high.json": {"v29_meeple_curve": list(CURVE125), "invasion_alpha": 0.0,
                         "invasion_alpha_cap": 0.0, "invasion_gamma": 0.15},
}

#: ⭐ TWO keys on a JOINT cell: the candidate carries beta AND gamma and the
#: opponent is the plain champion, so the two sides differ in both.
_J_DIFF = frozenset({"invasion_beta", "invasion_gamma"})
#: ⚠️ THREE keys on a C cell. The candidate is gamma-only and the OPPONENT carries
#: alpha + cap, so the two sides differ in all three. Carried from round 2.
_C_DIFF = frozenset({"invasion_alpha", "invasion_alpha_cap", "invasion_gamma"})

#: ⛔ ORDERED, AND THE ORDER IS THE EXECUTION ORDER (DESIGN §6.4).
#:
#: The LAPTOP owns A then J, in that order, deliberately: the three A cells are a
#: ONE-KNOB, PLAIN-REGIME, CHAMPION-OPPONENT configuration that rounds 1 and 2
#: have both already run clean, so they confirm the instrument on that box before
#: the two JOINT cells — the only configuration in this program's history to put
#: TWO invasion knobs on one candidate leaf — spend a deck. The LOCAL box owns the
#: three C cells, whose shape-B env regime round 2 proved end to end.
#: ⚠️ The two boxes run CONCURRENTLY, so the global order below is a reading
#: order and a seed-allocation order; only the WITHIN-BOX order is a sequence.
CELLS: tuple[CellSpec, ...] = (
    CellSpec(
        name="A_LOW", box="laptop", shape="A", rung="low",
        knobs=("invasion_beta",), weights=(0.02,),
        seed_start=153000000000, n_decks=400, n_games=800,
        out_subdir="a_low", leaf_json="leaf_a_low.json",
        cand_leaf_hash="e62afec3a84dfabd", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=frozenset({"invasion_beta"}),
        cand_invasion={"invasion_beta": 0.02}, opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="A_MID", box="laptop", shape="A", rung="mid",
        knobs=("invasion_beta",), weights=(0.05,),
        seed_start=153000000400, n_decks=400, n_games=800,
        out_subdir="a_mid", leaf_json="leaf_a_mid.json",
        cand_leaf_hash="9da236cf49065a21", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=frozenset({"invasion_beta"}),
        cand_invasion={"invasion_beta": 0.05}, opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="A_HIGH", box="laptop", shape="A", rung="high",
        knobs=("invasion_beta",), weights=(0.1,),
        seed_start=153000000800, n_decks=400, n_games=800,
        out_subdir="a_high", leaf_json="leaf_a_high.json",
        cand_leaf_hash="1fed3422b67be1d5", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=frozenset({"invasion_beta"}),
        cand_invasion={"invasion_beta": 0.1}, opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    # ⭐⭐ THE TWO ADOPTION-CHAIN-ELIGIBLE CELLS. Opponent = the CHAMPION OF
    # RECORD; candidate = the champion leaf carrying a light beta AND a light
    # gamma AS ONE LEAF. A z >= +2.0 here fires PROMOTE-JOINT and licenses the
    # production H2H — ⛔ FOR THE PACKAGE, NOT FOR A PART (JOINT_ATTRIBUTION_BAN).
    CellSpec(
        name="J_LOW", box="laptop", shape="J", rung="low",
        knobs=("invasion_beta", "invasion_gamma"), weights=(0.02, 0.03),
        seed_start=153000001200, n_decks=400, n_games=800,
        out_subdir="j_low", leaf_json="leaf_j_low.json",
        cand_leaf_hash="9e2764605c0b2fff", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=_J_DIFF,
        cand_invasion={"invasion_beta": 0.02, "invasion_gamma": 0.03},
        opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="J_HIGH", box="laptop", shape="J", rung="high",
        knobs=("invasion_beta", "invasion_gamma"), weights=(0.05, 0.07),
        seed_start=153000001600, n_decks=400, n_games=800,
        out_subdir="j_high", leaf_json="leaf_j_high.json",
        cand_leaf_hash="d193865634f14543", opp_leaf_hash=PROD_LEAF_HASH,
        opponent="champion", shape_b_env=False,
        leaf_diff_keys=_J_DIFF,
        cand_invasion={"invasion_beta": 0.05, "invasion_gamma": 0.07},
        opp_invasion={},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="C_LOW", box="local", shape="C", rung="low",
        knobs=("invasion_gamma",), weights=(0.03,),
        seed_start=153000002000, n_decks=400, n_games=800,
        out_subdir="c_low", leaf_json="leaf_c_low.json",
        cand_leaf_hash="86a6efb793a40ef2", opp_leaf_hash=SHAPE_B_LEAF_HASH,
        opponent="shape_b", shape_b_env=True,
        leaf_diff_keys=_C_DIFF,
        cand_invasion={"invasion_gamma": 0.03},
        opp_invasion={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="C_MID", box="local", shape="C", rung="mid",
        knobs=("invasion_gamma",), weights=(0.07,),
        seed_start=153000002400, n_decks=400, n_games=800,
        out_subdir="c_mid", leaf_json="leaf_c_mid.json",
        cand_leaf_hash="f05d8576b7a6cc23", opp_leaf_hash=SHAPE_B_LEAF_HASH,
        opponent="shape_b", shape_b_env=True,
        leaf_diff_keys=_C_DIFF,
        cand_invasion={"invasion_gamma": 0.07},
        opp_invasion={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="C_HIGH", box="local", shape="C", rung="high",
        knobs=("invasion_gamma",), weights=(0.15,),
        seed_start=153000002800, n_decks=400, n_games=800,
        out_subdir="c_high", leaf_json="leaf_c_high.json",
        cand_leaf_hash="a8e9083b102a52cf", opp_leaf_hash=SHAPE_B_LEAF_HASH,
        opponent="shape_b", shape_b_env=True,
        leaf_diff_keys=_C_DIFF,
        cand_invasion={"invasion_gamma": 0.15},
        opp_invasion={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
        allow_leaf_hash_drift=True,
    ),
)

#: ⭐ THE SELFTEST'S FIXTURE SPEC — ⛔ NOT A ROUND-3 CELL AND NEVER ADJUDICATED.
#:
#: `READ_RULE.md` §7 requires `analyze_screen.py --selftest` to run against a
#: manifest THE HARNESS EMITTED and to refuse a synthesized one. ⛔ ROUND 3 RUNS
#: NO GAMES AT ALL, so it seeds from a REAL EMITTED ARCHIVE THAT ALREADY EXISTS:
#: round 1's own §9 smoke archive (16 games, throwaway range 151999999000..,
#: discarded and never pooled), carried through round 2 into `selftest_fixture/`.
#:
#: ⚠️ ITS SHAPE IS `B`, WHICH IS NOT A ROUND-3 SHAPE, AND THAT IS DELIBERATE. The
#: archive is what it is — a shape-B agent (alpha 0.09 @ cap 11.0) against the
#: plain champion — and bending its description to match a round-3 weight would
#: make it something other than the archive the harness wrote. `sanity_check()`
#: asserts it is NOT one of `CELLS` and that its shape is NOT in `SHAPES`.
#:
#: ⚠️ WHAT IT CANNOT PROVE: it is a PLAIN-regime, ONE-KNOB archive, so it does not
#: exercise the C cells' shape-B opponent or ⭐ the JOINT cells' TWO-KNOB
#: candidate leaf. Those are covered by
#: `tests/test_invasion_screen_r3_instrument.py` (synthesized manifests are
#: legitimate in unit tests; it is the SELFTEST that refuses synthesis) and,
#: definitively, by the §9 SMOKE — whose LAPTOP leg runs `J_HIGH`'s config
#: precisely so the joint machinery emits a real manifest before any cell spends
#: a deck.
FIXTURE_SPEC = CellSpec(
    name="SELFTEST_FIXTURE", box="local", shape="B", rung="mid",
    knobs=("invasion_alpha",), weights=(0.09,),
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
#: ⛔ THREE shapes, and `B` is NOT one of them — see
#: `SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE`.
SHAPES = ("A", "J", "C")
#: The shapes whose PROMOTE enters the four-link adoption chain, because their
#: opponent is the champion of record. ⛔ `C` IS NOT ONE OF THEM, at any z.
CHAIN_ELIGIBLE_SHAPES = ("A", "J")
#: ⚠️ EVERY cell is an ARM in round 3 — there is no precondition cell. The
#: precondition role is played by `G-WHEEL-SAME` (round 1's inherited IDENT, held
#: through round 2) and by the §9 smoke, neither of which spends a deck.
ARM_CELLS = CELLS
#: How a shape's PROMOTE is spelled in the round-level branch label.
SHAPE_PROMOTE_LABEL = {"A": "A", "J": "JOINT", "C": "C"}


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


def cells_of_rung(shape: str, rung: str):
    return next((c for c in cells_of_shape(shape) if c.rung == rung), None)


# --------------------------------------------------------------------------- #
# ⭐ G-HOST — the frozen assignment, enforced against the emitted manifest      #
#                                                                              #
# ⚠️ THE MANIFEST'S `host` IS THE ONLY HOST WITNESS THE HARNESS EMITS. The      #
# per-game records carry NO host field. So this gate CANNOT prove that every    #
# record of a cell came from one box; it proves that the cell's SEALING PASS —  #
# the one that wrote the pooled summary the adjudicator reads — ran on the box  #
# the pair assigned it to.                                                      #
#                                                                              #
# ⛔ THE REAL PROTECTION IS STRUCTURAL: the two boxes are given DISJOINT CELLS   #
# and therefore DISJOINT `--out-subdir`s, so `--shared-claim` has nothing to     #
# race over between them. `G-HOST` catches the launcher-level version of the     #
# mistake — a box handed the wrong `--host` role — and the launcher refuses it   #
# a second time up front.                                                       #
# --------------------------------------------------------------------------- #
def host_matches_box(observed_host, role: str) -> tuple[bool, str]:
    """`G-HOST`. ⛔ ABSENT is FAIL.

    The comparison is deliberately a SUBSTRING match on a normalised hostname
    rather than an equality against a pinned string: this program's boxes report
    different hostnames under Windows vs WSL vs Pop!_OS on the SAME machine
    (`reference_laptop_popos_access`: `laptop`, `laptop-wsl`, `laptop-pop` are one
    physical box), and pinning one spelling would void a healthy cell for a
    dual-boot reason that has nothing to do with the measurement.
    """
    if not observed_host or not isinstance(observed_host, str):
        return False, ("manifest `host` ABSENT — ABSENT is FAIL. The cell->box "
                       "assignment is frozen in the prereg and cannot be verified "
                       "without it.")
    h = observed_host.strip().lower()
    markers = ("laptop", "pop-os", "popos")
    if role == "laptop":
        ok = any(m in h for m in markers)
        why = ("" if ok else
               f"host {observed_host!r} does not look like the laptop, but this "
               "cell is FROZEN to it (DESIGN §6.5). A cell run on the wrong box "
               "breaks the property the assignment exists to protect: that no "
               "pre-registered contrast is ever computed across the two boxes.")
    else:
        ok = not any(m in h for m in markers)
        why = ("" if ok else
               f"host {observed_host!r} looks like the LAPTOP, but this cell is "
               "FROZEN to the local box (DESIGN §6.5).")
    return ok, (why or f"host {observed_host!r} is the frozen box for this cell "
                       f"({role})")


#: Where each box drops the launch artifacts the adjudicator has to read back.
#: ⭐ Each box writes `PINNED_SRC_REV`, `SRC_CLEAN.jsonl`, `BLIND_PROOF.json` and
#: `WHEEL_PROBE.json` into ITS OWN repo checkout, which the LOCAL adjudicator
#: cannot see — so each launcher also copies them to
#: `<out-root>/_provenance/<role>/` on the SHARE. `G-REV`, `G-BLIND` and
#: `G-WHEEL` then evaluate each cell against ITS OWN BOX's artifacts.
#: ⚠️ The adjudicator FALLS BACK to its own directory when a per-box copy is
#: absent, so a single-box run and the §9 smoke keep working unchanged.
PROVENANCE_DIRNAME = "_provenance"


def provenance_subdir(role: str) -> str:
    return f"{PROVENANCE_DIRNAME}/{role}"


# --------------------------------------------------------------------------- #
# ROUNDS 1 AND 2 — ⛔ DESCRIPTIVE OVERLAY ONLY (READ_RULE.md §1.2, §4.5b)       #
#                                                                              #
# These are the numbers rounds 1 and 2 adjudicated, on bands 151000000000 and   #
# 152000000000. They are carried here so the readout can PLOT the ladder, and   #
# because DESIGN §3.2 DERIVES round 3's weights from their SHAPE — and they are #
# fenced off from every statistic in this pair, because they are CROSS-BAND.    #
#                                                                              #
# ⛔ NEVER POOLED. ⛔ NEVER z-COMBINED. ⛔ NEVER A BRANCH INPUT. CL-068 measured  #
# 1.8-2.2x over-dispersion on cross-band contrasts, in BOTH the elo and the     #
# deck-paired-margin statistics. ⚠️ ROUND 3 IS THE THIRD BAND, so there are now  #
# TWO tempting pools rather than one, and BOTH are forbidden.                   #
#                                                                              #
# ⭐ AND THE DERIVATION IS NOT A POOL. DESIGN §3.2 uses these points to CHOOSE   #
# WHERE TO MEASURE — a design act, performed before any round-3 number exists    #
# and disclosed in full. Choosing where to look is not the same act as combining #
# readings, and no round-3 branch reaches back to an overlay for a statistic.    #
# --------------------------------------------------------------------------- #
R1_BAND = 151000000000
R2_BAND = 152000000000

#: Round 1's mids (band 151e9). `D_MID` is retained because DESIGN §3.3 has to
#: say why shape D is still not run.
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

#: ⭐ ROUND 2's SEVEN CELLS (band 152e9), AS AMENDED. These are the AMENDED
#: readings — round 2's frozen verdict was `U-UNREADABLE` on a cross-box short-sha
#: defect (`AMENDMENTS.md` IS-A1), the owner authorised the re-read, and the
#: amended round branch is `BRACKET-CONTINUE`. ⛔ The frozen verdict stands
#: unedited on round 2's record; these are the numbers the amended re-read
#: published, and they are what DESIGN §3.2 derives from.
R2_CELLS = {
    "A_LOW":  {"knob": "invasion_beta", "weight": 0.04, "box": "local",
               "D": 0.93625, "se": 0.5733160171166127, "z": 1.6330435083755324,
               "elo": 5.646325294001462, "branch": "BRACKET", "opponent": "champion"},
    "A_HIGH": {"knob": "invasion_beta", "weight": 0.36, "box": "local",
               "D": -3.36375, "se": 0.5827771661683976, "z": -5.771931700954839,
               "elo": -59.19598622776525, "branch": "REVERSED", "opponent": "champion"},
    "B_LOW":  {"knob": "invasion_alpha", "weight": 0.03, "box": "local",
               "D": -0.6175, "se": 0.6174035976417309, "z": -1.0001561415557625,
               "elo": -16.51561891627038, "branch": "NULL", "opponent": "champion"},
    "B_HIGH": {"knob": "invasion_alpha", "weight": 0.27, "box": "local",
               "D": 0.0225, "se": 0.6019954157437091, "z": 0.03737569989997906,
               "elo": 4.343171035283314, "branch": "NULL", "opponent": "champion"},
    "C_LOW":  {"knob": "invasion_gamma", "weight": 0.08, "box": "laptop",
               "D": 0.9975, "se": 0.6112356394159544, "z": 1.6319401809638057,
               "elo": 12.600060999726589, "branch": "BRACKET", "opponent": "shape_b"},
    "C_MID":  {"knob": "invasion_gamma", "weight": 0.23, "box": "laptop",
               "D": 0.195, "se": 0.5851321531000315, "z": 0.3332580494284745,
               "elo": 20.87120466602866, "branch": "NULL", "opponent": "shape_b"},
    "C_HIGH": {"knob": "invasion_gamma", "weight": 0.69, "box": "laptop",
               "D": -1.01375, "se": 0.6488237592135866, "z": -1.562442782965787,
               "elo": -13.469873593071938, "branch": "NULL", "opponent": "shape_b"},
}
R2_ROUND_BRANCH = "BRACKET-CONTINUE (amended re-read, IS-A1)"

#: ⭐ WHAT ROUND 2 REALIZED for dispersion, per cell: `se * sqrt(400)`. Published
#: beside the frozen model so a round-3 SE near the model's FLOOR reads as
#: "tighter than modelled", not as an anomaly.
R2_REALIZED_SIGMA_D = {n: round(v["se"] * 20.0, 4) for n, v in R2_CELLS.items()}
#: The mean of the above — the HONEST expectation for a round-3 cell's SE.
R2_MEAN_SIGMA_D = round(sum(R2_REALIZED_SIGMA_D.values()) / len(R2_REALIZED_SIGMA_D), 4)

OVERLAY_RULE = (
    "⛔ DESCRIPTIVE OVERLAY ONLY. Round 1's mids were played on band "
    f"{R1_BAND} and round 2's seven cells on band {R2_BAND}; this round is on "
    f"band {BAND}. CL-068 measured 1.8-2.2x over-dispersion on CROSS-BAND "
    "contrasts in BOTH the elo and the deck-paired-margin statistics. The r1 and "
    "r2 readings are PLOTTED on the ladder and are NEVER pooled with a round-3 "
    "cell, NEVER z-combined with one, and NEVER a branch input. ⭐ THE ONE THING "
    "THEY DID DO is fix WHERE round 3 measures (DESIGN §3.2) — a design act, "
    "disclosed in full, performed before any round-3 number existed. Choosing "
    "where to look is not combining readings."
)

#: ⛔ SHAPE D IS STILL NOT RUN. Round 1's D_MID read z -0.49 — a bounded null and
#: the least informative of the three. Round 2 declined it; round 3's funded menu
#: is the A and C fine ladders and the joint cell, and names no D point.
D_NOT_RUN = (
    "Shape D is NOT run in round 3, as it was not in round 2. Its round-1 mid "
    "read D -0.291 / z -0.490 (a bounded null), and the measured one-ply "
    "sibling-delta for T_D is ~0 at 94.6% of the census positions, so a D reading "
    "is the least informative about its own mechanism. No branch may say anything "
    "about shape D at any weight other than round 1's mid."
)

# --------------------------------------------------------------------------- #
# THE §9 SMOKE LEG (DESIGN.md §9)                                               #
#                                                                              #
# 16 games (8 decks x 2 seatings) per box on a THROWAWAY range deliberately     #
# placed far above every cell range, so no arithmetic slip can reach a real     #
# deck. DISCARDED, never pooled, never claimed, never adjudicated as a result.  #
#                                                                              #
# ⭐ ONE SMOKE PER BOX, EACH RUNNING THAT BOX'S OWN MOST-PLUMBING CELL CONFIG,   #
# AT THAT BOX'S OWN FROZEN W. Round 2 smoked at a separate W=8; round 3 does    #
# NOT — each box smokes at the exact `W` its real cells will use, because       #
# UNIFORMITY BEATS SPEED here: the leg's whole job is to prove the plumbing ON  #
# THE MACHINE AND IN THE CONFIGURATION that will spend the decks, and W_LOCAL   #
# is itself an owner constraint this round rather than a free choice. A 16-game #
# leg does not saturate W either way, so the cost of uniformity is ~nothing.    #
# --------------------------------------------------------------------------- #
SMOKE_DECKS = 8
SMOKE_GAMES = 16
SMOKE_BY_BOX: dict[str, dict] = {
    "laptop": {
        "cell": "J_HIGH",
        "seed_start": 153999999100,
        "why": ("⛔ THE LOAD-BEARING LEG. The laptop owns the A ladder AND both "
                "JOINT cells, and the JOINT candidate leaf -- TWO invasion knobs "
                "on ONE leaf, a two-key leaf diff, and the round's only "
                "adoption-chain-eligible novelty -- has NEVER emitted a manifest "
                "on any box, in any round. J_HIGH rather than J_LOW because it "
                "carries the larger dose of both knobs, so a forwarding failure "
                "on either has the most room to show."),
    },
    "local": {
        "cell": "C_MID",
        "seed_start": 153999999000,
        "why": ("the local box owns the three C cells, whose shape-B ENV regime, "
                "non-champion opponent leaf, explicit-zero neutralisation and "
                "THREE-key leaf diff round 2 already proved end to end -- so this "
                "leg is a re-confirmation of the launcher, the wheel install and "
                "the env regime ON THIS BOX rather than a first sight. C_MID "
                "rather than C_LOW/C_HIGH because the interior rung is the one "
                "§4.7's noise-signature rule reads. ⚠️ IT IS ALSO THIS BOX'S FIRST "
                "RUN AT W=14, which is a wall-clock fact and nothing more."),
    },
}
#: back-compat aliases for the single-cell readers (the adjudicator's
#: `--smoke-mode` takes an explicit `--cell` directory and infers the rest).
SMOKE_CELL = SMOKE_BY_BOX["laptop"]["cell"]
SMOKE_SEED_START = SMOKE_BY_BOX["laptop"]["seed_start"]


# --------------------------------------------------------------------------- #
# THE BARS (READ_RULE.md §3, §4)                                                #
#                                                                              #
# ⛔ CARRIED VERBATIM FROM ROUNDS 1 AND 2. Not one bar moved in three rounds.    #
# The comparison operators in `branch_for_cell()` are the ones READ_RULE uses — #
# `>=`, `<=`, `<`. A bar is a CLOSED interval at exactly its stated endpoint;   #
# the instrument tests drive each one AT the endpoint for that reason.          #
# --------------------------------------------------------------------------- #
PROMOTE_Z = 2.0          # §4 PROMOTE:  z >= +2.0
BRACKET_Z = 1.0          # §4 BRACKET:  +1.0 <= z < +2.0
REVERSED_Z = -2.0        # §4 REVERSED: z <= -2.0

#: §4.5 — the pre-registered WITHIN-round low-vs-high contrast resolves at this
#: bar, and so does §4.5b's three-point interior-lift statistic.
#: ⛔ NEITHER IS EVER A PROMOTION INPUT (promotion is per-cell, against zero, at
#: the cell's own realized SE). Both are SHAPE readings and round-4 inputs.
CONTRAST_Z = 2.0

#: §3 G-SAT — a RAIL check, not a strength bar.
SAT_WR = (0.35, 0.65)

#: §3 G-N — `n_common >= 80%` of the frozen deck count.
N_COMMON_FRAC = 0.80

#: §3 G-N — a failure rate STRICTLY BELOW 2% is REPORTED, not silently absorbed.
FAILURE_RATE_VOID = 0.02

#: §2.1 — the sizing model, CARRIED UNCHANGED from rounds 1 and 2 (median 13.15 /
#: closest analogue 13.60 / MAX 14.67, inverted off seven n=400-deck deck-paired
#: fixed_v1+R9 rust cells in experiments/results.csv). This pair sizes on the MAX.
#: ⛔ POWER ARITHMETIC ONLY. Every bar in §4 is evaluated at the cell's OWN
#: REALIZED SE; this constant is NEVER a denominator in a branch test.
#: ⚠️ Round 3 keeps 14.67 even though rounds 1 AND 2 both REALIZED tighter
#: (`R2_REALIZED_SIGMA_D`: 11.47-12.98, mean 12.06). Keeping the conservative
#: model means the published power table UNDER-states this round's real
#: resolution rather than over-stating it, which is the direction a screen that
#: decides funding should err in.
SIGMA_D_MODEL = 14.67

#: §1 — realized/modelled SE outside this window is FLAGGED as a dispersion
#: anomaly. ⛔ CARRIED VERBATIM; reported, never a branch input.
#: ⚠️ Round 1 realized ratios 0.714-0.834 and round 2 realized 0.782-0.885 — both
#: hugging the FLOOR. A round-3 flag at the LOW end is therefore EXPECTED and
#: means "tighter than modelled"; the HIGH end is the concerning direction.
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
#: ⚠️ IDENTICAL TO ROUND 2's — not one member added. `G-WHEEL-SAME` is NOT in it:
#: the smoke runs on the same wheel the cells will, so it MUST pass there.
SMOKE_ALLOWED_FAILURES = frozenset({
    "G-BAND", "G-DECKS", "G-N", "G-SAT", "G-HOST", "RECON/n_paired",
})

#: Why each member of the allowed set cannot pass on a 16-game throwaway.
SMOKE_ALLOWED_REASONS = {
    "G-BAND": "the smoke runs on a DISJOINT throwaway range "
              "(153999999000.. local / 153999999100.. laptop) with "
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
#: ⚠️ NINETEEN, exactly round 2's set and exactly round 2's names. Round 3 adds no
#: gate and retires none: `G-LEAF`, `G-INVASION`, `G-SINGLEVAR` and `G-CAPFWD`
#: were already PER-CELL and TWO-SIDED, which is precisely what a JOINT cell (two
#: knobs, champion opponent, two-key leaf diff) needs — the schema generalised
#: without a new gate, and a round that invented one would be admitting round 2's
#: were narrower than they were written to be.
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
# ⛔ CARRIED VERBATIM FROM ROUND 2, INCLUDING CONJUNCT (d). Round 2 made every   #
# hash pin PER-CELL and TWO-SIDED because three of its cells played a shape-B    #
# agent; round 3 needs the identical generality for a different reason — its     #
# JOINT cells pin a candidate leaf that carries TWO knobs — and the gate already #
# expressed it, because it compares against the cell's own pinned STRINGS rather #
# than against any structural property of the leaf.                             #
#                                                                              #
# ⛔ AND IT IS STILL THE ONLY THING STANDING. `--allow-leaf-hash-drift` is a      #
# SINGLE switch that relaxes `_assert_netprior_leaf` on BOTH sides               #
# (`eval_fair_puct.py:3763` candidate, `:3777` opponent), and round 3 passes it   #
# on ALL EIGHT cells, so the harness's own hash assertion enforces nothing        #
# anywhere. EXACT equality against a pre-registered pin is the only check that    #
# can tell "drifted to the intended leaf" from "drifted to something else".      #
#                                                                              #
# Called by BOTH the adjudicator's `G-LEAF` and the launcher's per-cell           #
# pre-check, so the live gate and the post-hoc gate cannot drift apart.          #
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
        # (d) ⭐ the two sides must be DIFFERENT leaves.
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
# ⭐⭐ THE IS-A1 FOLD — `G-REV`'s CROSS-BOX CLAUSE, CANONICALIZED AGAINST THE PIN #
#                                                                              #
# ⛔ THIS IS THE ONE THING ROUND 3 CHANGED IN A GATE, AND IT IS A BUG FIX WITH   #
# A NAME. `AMENDMENTS.md` IS-A1 (2026-08-27):                                    #
#                                                                              #
#     Round 2's FROZEN adjudicator asked "are the boxes' emitted short revs      #
#     EQUAL AS STRINGS?". But `git rev-parse --short` chooses its length PER     #
#     CLONE (it lengthens to disambiguate against that clone's own object        #
#     database), so two boxes sitting at the IDENTICAL commit emitted            #
#     `240626a3-dirty` (local) and `240626a31f-dirty` (laptop). The gate         #
#     FALSELY VOIDED a healthy single-rev round — frozen verdict U-UNREADABLE,   #
#     which stands unedited on round 2's record. Proof of single-rev: both       #
#     boxes' PINNED_SRC_REV files were byte-identical                            #
#     (240626a31feeab01e22e73b42230a80a9889ec6f) and every boundary was clean    #
#     against that pin on both boxes. Owner authorised the re-read (the          #
#     h2h-option-1 precedent); the amended branch is BRACKET-CONTINUE.           #
#                                                                              #
#     Same defect class as the `h2h_22016` G-REV defect (short-sha-vs-full),     #
#     cross-box variant.                                                        #
#                                                                              #
#     ⭐ THE LESSON, VERBATIM FROM THE AMENDMENT: "canonicalize revs against the #
#     pin, never rev-vs-rev."                                                    #
#                                                                              #
# ⛔ AND THE FOLD IS STRICTER THAN THE AMENDMENT SCRIPT WAS, in two ways:        #
#                                                                              #
#   1. `analyze_screen_amended.py` read ONE pin (the adjudicator's own           #
#      directory) and canonicalized every rev against it. This reads EACH BOX'S  #
#      OWN published pin and REQUIRES THE PINS THEMSELVES TO AGREE — which is    #
#      the proposition "the two boxes were at the same commit" stated directly,  #
#      rather than inferred from a local file the boxes never wrote.             #
#   2. It lives HERE, in the library both the adjudicator and the launcher       #
#      import, rather than in a one-off amendment script — so it is exercised by #
#      the instrument suite instead of being first executed in anger.            #
#                                                                              #
# ⚠️ AND IT CANNOT DEGENERATE INTO "ANY PREFIX PASSES": a canonicalized rev must #
# still be >= MIN_REV_PREFIX hex characters, and it must prefix a pin that is a  #
# real 40-hex sha. A genuinely different commit does not prefix the pin and       #
# FAILS — which the instrument suite drives, in BOTH directions.                 #
# --------------------------------------------------------------------------- #
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"


def split_dirty(code_rev: str) -> tuple[str, bool]:
    """`(sha_part, had_dirty_marker)`. The marker is WHOLE-TREE scoped and is
    reported, never fatal — `run_manifest.code_rev()` computes dirtiness over the
    WHOLE TREE and the main tree is perpetually dirty with measurement logs. The
    FATAL, code-path-scoped verdict is `SRC_CLEAN.jsonl`'s."""
    s = (code_rev or "").strip()
    if s.lower().endswith(DIRTY_SUFFIX):
        return s[: -len(DIRTY_SUFFIX)], True
    return s, False


def is_hex40(s) -> bool:
    return (isinstance(s, str) and len(s) == 40
            and all(c in "0123456789abcdef" for c in s.lower()))


def rev_matches(code_rev, pinned) -> tuple[bool, str]:
    """`(ok, why)` — does a manifest's short `code_rev` NAME `PINNED_SRC_REV`?

    ⛔ This answers the IDENTITY question only. The CLEANLINESS question is
    `SRC_CLEAN.jsonl`'s, because only that reading is scoped to the code paths.

    ⭐ THIS IS ALSO THE CANONICALIZATION IS-A1 CALLS FOR, at the single-cell
    level: strip the whole-tree `-dirty` marker, then require a >= 7-hex PREFIX
    match against the 40-hex pin. It has been a prefix rule since round 1;
    IS-A1's defect was that the CROSS-BOX clause did not use it.
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


def cross_box_rev_gate(revs_by_cell: Mapping, pins_by_role: Mapping) -> dict:
    """⭐ THE IS-A1 FOLD. `(ok, why, ...)` for "was this ONE round, at ONE rev,
    across BOTH boxes?" — ⛔ NEVER by comparing one box's emitted short rev to the
    other's.

    Two conjuncts, in this order:

      (1) **THE PINS AGREE.** Every box role that published a `PINNED_SRC_REV`
          must publish the SAME 40-hex sha. This is the proposition stated
          directly. A missing pin is FAIL — ABSENT is FAIL.
      (2) **EVERY EMITTED REV CANONICALIZES TO THAT PIN**, via `rev_matches()`:
          strip `-dirty`, require >= 7 hex chars, require a PREFIX match. Short
          revs of DIFFERENT LENGTHS both pass; a different commit does not.

    ⚠️ A single-box round (and the §9 smoke) passes conjunct (1) trivially with
    one pin, which is correct: there is no cross-box proposition to check.
    """
    pins = {r: (p or "").strip().lower() for r, p in (pins_by_role or {}).items()
            if p}
    if not pins:
        return {"ok": False, "pins": {}, "distinct_pins": [],
                "revs": dict(revs_by_cell or {}), "canonicalized": {},
                "why": ("no box published a PINNED_SRC_REV — ABSENT is FAIL. The "
                        "cross-box single-rev property cannot be established "
                        "without the pins, and IS-A1 forbids falling back to "
                        "comparing the emitted revs to each other.")}
    bad_pins = sorted(r for r, p in pins.items() if not is_hex40(p))
    distinct = sorted(set(pins.values()))
    if bad_pins:
        return {"ok": False, "pins": pins, "distinct_pins": distinct,
                "revs": dict(revs_by_cell or {}), "canonicalized": {},
                "why": (f"box(es) {bad_pins} published a PINNED_SRC_REV that is not "
                        "a 40-hex sha — ABSENT-or-malformed is FAIL.")}
    if len(distinct) > 1:
        return {"ok": False, "pins": pins, "distinct_pins": distinct,
                "revs": dict(revs_by_cell or {}), "canonicalized": {},
                "why": ("⛔ THE BOXES WERE AT DIFFERENT COMMITS: their "
                        f"PINNED_SRC_REV files disagree ({distinct}). This is a "
                        "mixed-rev round (the track_d2_prep defect, across "
                        "machines) and the git-bundle sync exists to prevent "
                        "exactly it. ⚠️ NOTE THIS IS THE PINS DISAGREEING, NOT THE "
                        "SHORT REVS — the short revs disagreeing is EXPECTED and "
                        "harmless (IS-A1).")}
    pin = distinct[0]
    canon: dict = {}
    bad: list = []
    for name, rev in (revs_by_cell or {}).items():
        ok, why = rev_matches(rev, pin)
        canon[name] = {"code_rev": rev, "ok": ok, "why": why}
        if not ok:
            bad.append(f"{name}: {why}")
    ok = not bad
    return {
        "ok": ok, "pins": pins, "distinct_pins": distinct, "pin": pin,
        "revs": dict(revs_by_cell or {}), "canonicalized": canon,
        "why": ("every cell's emitted code_rev canonicalizes to the ONE pin "
                f"{pin} that BOTH boxes published — short revs of different "
                "lengths are expected and harmless (IS-A1)" if ok else
                "⛔ a cell's emitted code_rev does NOT name the shared pin: "
                + "; ".join(bad)),
    }


# --------------------------------------------------------------------------- #
# THE COST MODEL — REBUILT ON ROUND 2's REALIZED NUMBERS (DESIGN.md §6)         #
#                                                                              #
# ⛔ ROUND 2's INPUTS ARE RETIRED, ITS ARITHMETIC IS KEPT. Round 2 built the     #
# model on ROUND 1's realized ms/move and carried TWO unmeasured inputs (shape  #
# C's per-move cost, and the laptop's per-game ratio). ROUND 2 MEASURED BOTH.   #
#                                                                              #
# THE INPUTS, ALL MEASURED IN ROUND 2 (invasion_r2_READOUT_AMENDED.json):        #
#     plain-champion side   475.87 / 480.86 / 464.28 / 465.23  -> 471.56 (local)#
#     shape-A candidate     685.50 / 683.57                    -> 684.53 (local)#
#     shape-B side          632.20 / 634.63                    -> 633.42 (local)#
#     shape-C candidate     671.00 / 683.78 / 690.45           -> 681.74 (laptop)#
#     shape-B side          696.84 / 687.37 / 693.78           -> 692.66 (laptop)#
#                                                                              #
# ⭐ AND THE LAST TWO LINES ARE THE SAME LEAF ON DIFFERENT BOXES, which is where #
# the MEASURED box ratio comes from: 692.66 / 633.42 = 1.0935 (LAPTOP_RATIO_    #
# MEASURED). Shape C's local-equivalent per-move cost then follows: 681.74 /    #
# 1.0935 = 623.43 ms/move.                                                      #
#                                                                              #
# ⚠️ NOTE HOW LITTLE THE WEIGHT MATTERS TO COST: shape A read 685.50 ms/move at  #
# beta 0.36 and 683.57 at beta 0.04 — a 9x weight ratio for a 0.3% cost         #
# difference. The invasion arithmetic is a per-component SCAN whose cost is set  #
# by the board, not by the coefficient. That is why round 3's much smaller       #
# weights are projected at round 2's per-move costs without apology.            #
#                                                                              #
# THE ARITHMETIC IS UNCHANGED FROM ROUND 2:                                      #
#     s/game(local-equiv) = MOVES_PER_SIDE * (ms_cand + ms_opp)/1000 * OVERHEAD  #
#                                                                              #
# and `sanity_check()` requires it to reproduce each of round 2's three realized #
# shapes WITHOUT EVER UNDER-PREDICTING and by no more than +5% — a DIRECTIONAL   #
# assertion, because a cost model that decides funding should err dear.         #
# --------------------------------------------------------------------------- #
MOVES_PER_SIDE = 69.0     # measured, rust, fixed_v1
#: harness, claim I/O, solver tail. Carried from round 2 unchanged.
OVERHEAD = 1.073

#: Per-side ms/move, LOCAL-EQUIVALENT, all MEASURED in round 2 except `J`.
MS_CHAMPION_SIDE = 471.56       # measured (the opponent on the A and J cells)
MS_SHAPE_A_SIDE = 684.53        # measured (round 2's A_LOW/A_HIGH candidate)
MS_SHAPE_B_SIDE = 633.42        # measured (round 2's B candidate) -- the C cells' OPPONENT
MS_SHAPE_C_SIDE = 623.43        # measured on the laptop (681.74) / 1.0935

#: ⚠️ THE JOINT LEAF'S COST IS ROUND 3's ONE UNMEASURED INPUT. No leaf carrying
#: TWO invasion terms has ever run. The point estimate is ADDITIVE in the two
#: measured INCREMENTS over the champion side:
#:     beta  increment = 684.53 - 471.56 = 212.97 ms/move
#:     gamma increment = 623.43 - 471.56 = 151.87 ms/move
#:     joint = 471.56 + 212.97 + 151.87 = 836.40 ms/move
#: ⭐ ADDITIVE IS THE CONSERVATIVE (DEAR) DIRECTION, and the mechanism says so:
#: T_A and T_C both walk the mover's own claimed components, so the two terms
#: SHARE the contested-feature decomposition and the true cost should be at or
#: below additive. The envelope therefore runs from a sub-additive floor (the
#: larger increment plus HALF the smaller, i.e. the two scans sharing their walk)
#: to a super-additive ceiling (+10% on the summed increment).
MS_SHAPE_J_SIDE = 836.40
MS_SHAPE_J_ENVELOPE = (760.5, 872.9)

#: The realized worker-seconds per game round 2 logged, per shape (steady-state
#: passes; the launcher's own log). `sanity_check()` requires the model to
#: reproduce each without under-predicting and by no more than +5%.
#: ⚠️ Round 2's FIRST pass of A_LOW logged 124 w-s/game over 28 games and its
#: tail passes logged 138-146 over 17-25 games — RAMP artifacts at tiny n, not
#: steady state, and excluded here for that reason (the order-statistic trap
#: named in `feedback_eta_before_launch`).
R2_REALIZED_S_PER_GAME = {"A": 84.75, "B": 79.25, "C_on_laptop": 100.67}


def _cell_ms(spec: CellSpec, j_side: float | None = None) -> tuple[float, float]:
    """`(candidate ms/move, opponent ms/move)` for a cell, LOCAL-EQUIVALENT.

    ⚠️ The C cells are the only ones whose OPPONENT pays invasion arithmetic (it
    is the shape-B invader), which is why they are dear on the opponent side; the
    J cells are the only ones whose CANDIDATE pays it twice.
    """
    cand = {"A": MS_SHAPE_A_SIDE,
            "C": MS_SHAPE_C_SIDE,
            "J": (MS_SHAPE_J_SIDE if j_side is None else float(j_side))}[spec.shape]
    opp = MS_SHAPE_B_SIDE if spec.opponent == "shape_b" else MS_CHAMPION_SIDE
    return cand, opp


def project_cell_cost(spec: CellSpec, w: int | None = None,
                      j_side: float | None = None,
                      laptop_ratio: float | None = None) -> dict:
    """One cell's cost ON ITS OWN FROZEN BOX.

    ⭐ TWO SCALES ARE REPORTED AND THEY ARE NOT THE SAME NUMBER:

    * `core_hours_local_equiv` — what the cell would cost on the CALIBRATION box.
      The only scale on which the eight cells are comparable to each other.
    * `core_hours` — what it actually costs ON ITS BOX. ⛔ This is the one the
      funding line is in, because it is the compute that actually gets spent.

    ⚠️ `wall_hours` uses THAT BOX'S FROZEN `W` — 14 on local (the owner
    constraint), 22 on the laptop. `W` is throughput-only and moves no bar.
    """
    box = BOXES[spec.box]
    w = box["W"] if w is None else int(w)
    ratio = box["per_game_ratio"]
    if spec.box == "laptop" and laptop_ratio is not None:
        ratio = float(laptop_ratio)
    cand, opp = _cell_ms(spec, j_side)
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
        "j_side_is_assumed": (spec.shape == "J" and j_side is None),
    }


def project_round_cost(j_side: float | None = None,
                       laptop_ratio: float | None = None) -> dict:
    """The whole round, per cell AND per box.

    ⭐ THE ROUND'S WALL CLOCK IS THE **MAX** OVER THE BOXES, NOT THE SUM: the two
    boxes run CONCURRENTLY. That is the entire point of the split, and it is why
    the assignment is chosen to balance the two walls at THIS ROUND'S W
    (`BOX_ASSIGNMENT_RULE` — and at W_LOCAL=14 the balancing split is not the one
    round 2 used).
    """
    per_cell: dict[str, dict] = {}
    per_box: dict[str, dict] = {r: {"cells": [], "core_hours": 0.0,
                                    "core_hours_local_equiv": 0.0,
                                    "W": BOXES[r]["W"], "wall_hours": 0.0}
                                for r in BOX_ROLES}
    core = core_le = 0.0
    for c in CELLS:
        p = project_cell_cost(c, j_side=j_side, laptop_ratio=laptop_ratio)
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
        "j_side_ms": MS_SHAPE_J_SIDE if j_side is None else float(j_side),
        "laptop_ratio": (LAPTOP_RATIO_MEASURED if laptop_ratio is None
                         else float(laptop_ratio)),
    }


def round_cost_envelope() -> dict:
    """DESIGN §6.2's published RANGE. ⛔ §0(a)'s funding line is the RANGE, never
    the point.

    ⭐ ROUND 3 COMPOUNDS **ONE** UNMEASURED INPUT, NOT ROUND 2's TWO: the joint
    leaf's per-move cost. The laptop ratio is now MEASURED, so its envelope is a
    narrow measurement band rather than a guess.
    """
    j_lo, j_hi = MS_SHAPE_J_ENVELOPE
    r_lo, r_hi = LAPTOP_RATIO_ENVELOPE
    return {
        "point": project_round_cost(),
        "low": project_round_cost(j_side=j_lo, laptop_ratio=r_lo),
        "high": project_round_cost(j_side=j_hi, laptop_ratio=r_hi),
        "why": ("ONE unmeasured input (the JOINT leaf's per-move cost — no leaf "
                "carrying two invasion terms has ever run; the point estimate is "
                "ADDITIVE in the two measured increments, which the mechanism "
                "says is the DEAR end) plus the measured laptop ratio's narrow "
                "band. Every other figure is round-2 REALIZED."),
    }


def split_table() -> list[dict]:
    """⭐ DESIGN §6.5(iii): ALL SIX whole-shape partitions, priced at THIS ROUND'S
    frozen W (local 14, laptop 22), so the chosen assignment is demonstrably the
    fastest rather than asserted to be.

    ⛔ WHOLE SHAPES ONLY. A split that cut a shape would make §4.5's contrast and
    §4.5b's interior lift CROSS-BOX statistics.
    """
    per_shape_le = {}
    for sh in SHAPES:
        c = cells_of_shape(sh)[0]
        cand, opp = _cell_ms(c)
        s = MOVES_PER_SIDE * (cand + opp) / 1000.0 * OVERHEAD
        per_shape_le[sh] = s * c.n_games / 3600.0 * len(cells_of_shape(sh))
    rows = []
    for mask in range(1, 2 ** len(SHAPES) - 1):
        loc = [s for i, s in enumerate(SHAPES) if mask >> i & 1]
        lap = [s for s in SHAPES if s not in loc]
        lch = sum(per_shape_le[s] for s in loc)
        pch = sum(per_shape_le[s] * LAPTOP_RATIO_MEASURED for s in lap)
        lw = lch / float(BOXES["local"]["W"])
        pw = pch / float(BOXES["laptop"]["W"])
        rows.append({"local": loc, "laptop": lap,
                     "local_core_hours": lch, "laptop_core_hours": pch,
                     "local_wall_hours": lw, "laptop_wall_hours": pw,
                     "round_wall_hours": max(lw, pw),
                     "total_core_hours": lch + pch})
    rows.sort(key=lambda r: r["round_wall_hours"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        r["chosen"] = (sorted(r["local"]) == sorted({c.shape for c in cells_of_box("local")})
                       and sorted(r["laptop"]) == sorted({c.shape for c in cells_of_box("laptop")}))
    return rows


# --------------------------------------------------------------------------- #
# THE STATISTIC (READ_RULE.md §1) — the WITNESS implementation                  #
# ⛔ CARRIED VERBATIM FROM ROUNDS 1 AND 2. Not a line moved.                     #
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
    to `eval_fair_puct._paired_z` (`2371-2383`). Fewer than two paired decks ⇒
    `(None, None, n, None, list)`.

    ⚠️ Accumulated with `math.fsum` rather than `sum` DELIBERATELY: the point of a
    witness is to be a different computation.
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


def se_realized_expectation(n_decks: int) -> float:
    """What round 2 ACTUALLY realized on this instrument, per deck: the mean of
    its seven cells' `se * sqrt(400)`. ⛔ NOT A BAR — it is the honest
    denominator for the power table's second column, published beside the frozen
    conservative model so a reader can see how much power the conservative sizing
    gives away."""
    return R2_MEAN_SIGMA_D / math.sqrt(float(n_decks))


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    """§1: print realized vs modelled SE and FLAG a ratio outside [0.70, 1.43].
    ⛔ Reported, NEVER a branch input.

    ⚠️ Round 1 realized 0.714-0.834 and round 2 realized 0.782-0.885 against this
    model, so a LOW-end flag is expected and means "tighter than modelled". The
    HIGH end is the concerning direction. The band does not move for that."""
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
            "direction": ("TIGHTER than modelled (the expected direction — rounds "
                          "1 and 2 realized 0.714-0.885)" if ratio < lo else
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

    ⛔ THE LABEL MEANS DIFFERENT THINGS ON DIFFERENT CELLS, and this function does
    not encode the difference — it returns the RAW ladder position and the
    round-level table applies the meaning:

      * on an **A** cell PROMOTE is an offence reading against the CHAMPION and
        IS adoption-chain-eligible;
      * on a **J** cell PROMOTE is a reading of the PACKAGE against the CHAMPION,
        is adoption-chain-eligible, and ⛔ says NOTHING about either knob
        separately (`JOINT_ATTRIBUTION_BAN`);
      * on a **C** cell PROMOTE is NOT a promotion into the chain at all — C's
        opponent is a SHAPE-B INVADER. `round_branch()` re-labels it `DEFENDS-C`
        and `c_reading()` is the mandatory prose.
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
# ⭐ THE PRE-REGISTERED WITHIN-ROUND LADDER CONTRASTS (READ_RULE.md §4.5, §4.5b) #
#                                                                              #
# THE ROUND'S DOSING QUESTION IS "WHERE IN THE SMALL-WEIGHT REGION DOES THE     #
# SIGNAL PEAK?", and the honest way to ask it is with contrasts between cells   #
# THIS ROUND MEASURED, on ONE band, in ONE box.                                 #
#                                                                              #
# TWO statistics, both pre-registered here, both resolving at 2 sigma, ⛔ NEITHER#
# EVER A PROMOTION INPUT:                                                       #
#                                                                              #
#   §4.5   SCALING          Delta = D_high - D_low                              #
#                           SE    = sqrt(SE_high^2 + SE_low^2)                  #
#                                                                              #
#   §4.5b  INTERIOR LIFT    Lift  = D_mid - (D_low + D_high)/2                  #
#                           SE    = sqrt(SE_mid^2 + (SE_low^2 + SE_high^2)/4)   #
#                                                                              #
# ⭐ THE INTERIOR LIFT IS NEW IN ROUND 3, AND IT IS THE STATISTIC A FINE LADDER  #
# ACTUALLY OWES. Round 2's A and B ladders had TWO points and therefore no      #
# interior at all; round 3's A and C ladders have THREE points on ONE band, so  #
# "is there a peak strictly inside the bracket?" is finally a question the data #
# can answer. It is the quantitative form of §4.7's endpoint rule: a POSITIVE   #
# resolved lift says the optimum is INTERIOR (the ladder brackets it); a lift   #
# that does not resolve leaves the endpoint rule in force.                      #
# ⛔ IT IS NOT THE NOISE-SIGNATURE CHECK. `noise_signature()` asks whether a lone#
# interior rung beats BOTH neighbours by >1 sigma in z — a RE-MEASURE trigger.  #
# The lift is a pre-registered ESTIMATE with a CI. They can disagree, and if     #
# they do the RE-MEASURE obligation wins.                                       #
#                                                                              #
# ⚠️ THE RUNGS ARE ON DISJOINT DECK RANGES (DESIGN §5.1), so both are UNMATCHED  #
# differences of independent samples and the root-sum-square SE is the right    #
# one. CRN within a shape would have tightened them and was deliberately NOT    #
# taken: the pair's PRIMARY statistic is each cell's own margin against zero,   #
# disjoint ranges cost that nothing, and the funded design named 8 x 400        #
# disjoint decks.                                                              #
#                                                                              #
# ⚠️ NO CROSS-BAND HUMILITY DISCOUNT APPLIES: every rung is on band 153e9, in   #
# one launch window, on ONE box per shape. CL-068's 1.8-2.2x is a CROSS-BAND    #
# figure.                                                                      #
# --------------------------------------------------------------------------- #
def shape_contrast(low: Mapping | None, high: Mapping | None) -> dict:
    """§4.5 `(D_high - D_low)` with its unmatched SE and z. ⛔ ABSENT is
    UNREADABLE."""
    def _get(m, k):
        return None if not isinstance(m, Mapping) else m.get(k)

    d_lo, se_lo = _get(low, "D"), _get(low, "se")
    d_hi, se_hi = _get(high, "D"), _get(high, "se")
    if any(v is None for v in (d_lo, se_lo, d_hi, se_hi)):
        return {"readable": False, "delta": None, "se": None, "z": None,
                "verdict": "UNREADABLE",
                "why": "a rung's D or SE is ABSENT — ABSENT is FAIL, never a skip"}
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


def interior_lift(low: Mapping | None, mid: Mapping | None,
                  high: Mapping | None) -> dict:
    """§4.5b `D_mid - (D_low + D_high)/2` with its unmatched SE and z — the
    three-point ladder's PEAK statistic. ⛔ ABSENT is UNREADABLE, and a two-point
    ladder is NOT APPLICABLE rather than zero."""
    def _get(m, k):
        return None if not isinstance(m, Mapping) else m.get(k)

    if mid is None:
        return {"readable": False, "applicable": False, "lift": None, "se": None,
                "z": None, "verdict": "NOT APPLICABLE",
                "why": ("this shape has no INTERIOR rung — a two-point ladder has "
                        "no interior, so every reading on it sits at an endpoint "
                        "and §4.7's endpoint rule governs instead")}
    vals = [(_get(m, "D"), _get(m, "se")) for m in (low, mid, high)]
    if any(v is None for pair in vals for v in pair):
        return {"readable": False, "applicable": True, "lift": None, "se": None,
                "z": None, "verdict": "UNREADABLE",
                "why": "a rung's D or SE is ABSENT — ABSENT is FAIL, never a skip"}
    (d_lo, s_lo), (d_mid, s_mid), (d_hi, s_hi) = [(float(a), float(b)) for a, b in vals]
    lift = d_mid - (d_lo + d_hi) / 2.0
    se = math.sqrt(s_mid ** 2 + (s_lo ** 2 + s_hi ** 2) / 4.0)
    z = (lift / se) if se > 0 else float("nan")
    resolved = (not math.isnan(z)) and abs(z) >= CONTRAST_Z
    return {
        "readable": True, "applicable": True, "lift": lift, "se": se, "z": z,
        "ci95": (lift - 1.96 * se, lift + 1.96 * se),
        "verdict": ("INTERIOR PEAK RESOLVED" if resolved and lift > 0 else
                    "INTERIOR TROUGH RESOLVED" if resolved and lift < 0 else
                    "INTERIOR LIFT UNRESOLVED"),
        "reading": ("the optimum is INSIDE this ladder — the bracket holds and "
                    "§4.7's endpoint rule is SATISFIED for this shape"
                    if resolved and lift > 0 else
                    "⚠️ the interior rung reads BELOW the average of its "
                    "neighbours by >2σ — the shape is not single-peaked over this "
                    "bracket, and no 'the optimum is at the mid' reading survives"
                    if resolved and lift < 0 else
                    "not resolved at this n — ⛔ §4.7's ENDPOINT RULE STAYS IN "
                    "FORCE: a peak at either end of this ladder is NOT bracketed"),
        "why": ("UNMATCHED three-rung contrast on disjoint deck ranges; the "
                "neighbours' SEs enter halved-and-squared because the comparator "
                "is their MEAN. ⛔ NEVER a promotion input; promotion is per-cell "
                "against zero. ⛔ AND IT IS NOT the noise-signature check — that "
                "one is a >1σ RE-MEASURE trigger on z, and where the two "
                "disagree the re-measure obligation wins."),
    }


# --------------------------------------------------------------------------- #
# ⭐⭐ THE JOINT CELLS — WHAT THEY LICENSE, AND WHAT THEY DO NOT                 #
#                                                                              #
# ⛔ THIS IS THE MOST IMPORTANT BLOCK IN THIS FILE. The joint cells are the only #
# ones in round 3 whose PROMOTE reaches the four-link adoption chain, which     #
# makes them the ones a reader is most tempted to over-read.                    #
# --------------------------------------------------------------------------- #
JOINT_WHAT_IT_IS = (
    "⭐ A JOINT CELL IS ONE LEAF, NOT TWO TERMS. Its candidate is the champion "
    "curve125 leaf with invasion_beta AND invasion_gamma both set, evaluated as a "
    "single LeafConfig with a single leaf hash; its opponent is the CHAMPION OF "
    "RECORD (leaf a36d2e15a3b3d71d). It asks exactly one question -- DOES THIS "
    "LEAF BEAT THE CHAMPION AT 2752 -- and its deck-paired margin against zero "
    "answers exactly that question and no other."
)

JOINT_LICENSES = (
    "⭐ A JOINT CELL AT z >= +2.0 FIRES `PROMOTE-JOINT` AND LICENSES THE "
    "PRODUCTION-BUDGET H2H, per the frozen four-link adoption chain, because its "
    "opponent IS the champion of record and link 1 of that chain is defined as a "
    "screen against the champion. ⛔ IT LICENSES **ONE** THING: a production H2H "
    "of THAT LEAF, AT THAT WEIGHT PAIR, AS ONE LEAF. Not a PRODUCTION.yaml edit, "
    "not a champion-of-record discussion, not an H2H of either knob alone -- and "
    "the H2H itself is a fresh pair, a fresh band and a fresh funding decision."
)

#: ⛔⛔ THE BAN. Printed beside EVERY joint reading, whatever fired.
JOINT_ATTRIBUTION_BAN = (
    "⛔⛔ THE JOINT READ DOES NOT ATTRIBUTE, AND NOTHING IN THIS ROUND MAKES IT "
    "DO SO. A joint cell moves TWO knobs at once, so its margin is a property of "
    "the PAIR (beta, gamma) and carries NO information about which knob supplies "
    "it. A firing J cell is consistent with 'beta does all of it', with 'gamma "
    "does all of it', and with every mixture -- including one where a term that "
    "is NEGATIVE alone is carried by a partner that is strongly positive. "
    "⛔ FORBIDDEN, EXPLICITLY: (i) reading a J margin as evidence for shape A or "
    "for shape C separately; (ii) subtracting an A cell's margin from a J cell's "
    "to 'recover' gamma, or vice versa -- the cells are on DISJOINT deck ranges "
    "and §1 forbids cross-cell contrasts as branch inputs, so that difference is "
    "not even a pre-registered statistic, let alone an attribution; (iii) reading "
    "a NULL joint as evidence AGAINST either term; (iv) describing a joint margin "
    "as the SUM of the two marginal margins, in either direction (see "
    "`JOINT_IS_NOT_A_SUM`). ⭐ ATTRIBUTION IS A LATER QUESTION AND IT HAS A "
    "NAMED ANSWER: a two-cell ABLATION pair on a FRESH band -- the joint leaf "
    "with beta zeroed, and the joint leaf with gamma zeroed, both against the "
    "champion, deck-matched -- which is a fresh pair and a fresh funding "
    "decision. ⛔ IT IS NOT WHAT THIS ROUND BOUGHT, and a readout that attributes "
    "is wrong on the design, not merely on the emphasis."
)

JOINT_IS_NOT_A_SUM = (
    "⛔ JOINT != SUM OF PARTS, IN EITHER DIRECTION. The two terms enter the SAME "
    "leaf and are consumed by the SAME argmax over sibling moves, so their effect "
    "on MOVE ORDERING -- which is the only channel by which a leaf term changes a "
    "game -- composes non-linearly by construction. ⚠️ AND THIS CUTS BOTH WAYS "
    "AND IS STATED BEFORE ANY NUMBER EXISTS: round 3's power table publishes an "
    "'additive' row (Δ = +1.94 pts/deck, the arithmetic sum of round 2's two "
    "BRACKET readings) as THE EFFECT SIZE THE JOINT CELL IS SIZED AGAINST -- "
    "because sizing needs a number and that is the honest one to size against. "
    "⛔ PUBLISHING IT AS A SIZING TARGET IS NOT PREDICTING IT, AND OBSERVING IT "
    "WOULD NOT CONFIRM ADDITIVITY: one cell at n=400 cannot distinguish additive "
    "from sub-additive-plus-noise from a single dominant term."
)

# --------------------------------------------------------------------------- #
# ⭐ SHAPE C READS DEFENCE, NOT STRENGTH (READ_RULE.md §4.6) — carried verbatim #
# --------------------------------------------------------------------------- #
C_OPPONENT_NOTE = (
    "⛔ C'S OPPONENT IS AN INVADER, NOT THE CHAMPION OF RECORD. The three C "
    "cells play the champion curve125 leaf PLUS invasion_alpha 0.09 @ cap 11.0 "
    f"(leaf {SHAPE_B_LEAF_HASH}) -- bit-for-bit round 1's B_MID candidate and "
    "bit-for-bit round 2's C opponent. SHAPES.md §3 requires it: shape C is "
    "DEFENCE-ONLY and not antisymmetric, so a C-vs-champion cell is a "
    "guaranteed-uninformative null (the champion does not invade). A POSITIVE C "
    "margin therefore means THE DEFENCE PAYS AGAINST THE EXPLOIT -- it does NOT "
    "mean the agent is stronger, and it says nothing about play against the "
    "champion of record or against any out-of-lineage opponent. "
    "⚠️ AND THE INVADER IS A DEMOTED SHAPE, WHICH CHANGES NOTHING ABOUT ITS USE "
    "AS AN INSTRUMENT: see SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE."
)

C_NEVER_PROMOTES_ALONE = (
    "⛔ C NEVER PROMOTES PAST ITS OWN FAMILY WITHOUT AN OFFENCE PARTNER. A firing "
    "C cell does NOT enter the four-link adoption chain, because link 1 of that "
    "chain is defined as a screen AGAINST THE CHAMPION and C's opponent is not "
    "the champion. ⭐ ROUND 3 IS ALREADY RUNNING THE PARTNERED FOLLOW-UP ROUND 2 "
    "LICENSED -- the two JOINT cells pair gamma with a surviving offence weight "
    "and screen the pair against the champion AS ONE LEAF -- so a firing C cell "
    "in round 3 licenses NO NEW ACTION BEYOND WHAT THE J CELLS ALREADY CARRY. "
    "⛔ No C reading of any size licenses a production H2H, a "
    "governance/PRODUCTION.yaml change, or a champion-of-record discussion."
)


def c_reading(branch: str, z, delta_note: str = "") -> str:
    """The MANDATORY prose for a C cell's branch (READ_RULE §4.6)."""
    base = {
        "PROMOTE": ("DEFENDS -- at this gamma the dumping-ground discount pays a "
                    "measurable margin AGAINST A SHAPE-B INVADER. " +
                    C_NEVER_PROMOTES_ALONE),
        "BRACKET": ("the defence reads >= +1σ against an invader but does not "
                    "resolve. " + C_NEVER_PROMOTES_ALONE),
        "REVERSED": ("⚠️ THE DEFENCE COSTS POINTS AGAINST AN INVADER at this "
                     "gamma -- a real finding, not a gate failure. The leading "
                     "named hypothesis is SHAPES.md §3's NORMALISATION caveat: "
                     "frac = open_n/edges makes the charge a rate x a value, so "
                     "shape C does NOT rank a large open city above a small "
                     "fully-open feature. The named first follow-up is the "
                     "UN-NORMALISED variant -- A DIFFERENT SHAPE needing its own "
                     "build, fixtures and pair, NOT a re-parameterisation of this "
                     "one. ⛔ A REVERSED reading does not license flipping the "
                     "term's sign."),
        "NULL": ("a BOUND, not a zero. The opponent DOES invade, so a null says "
                 "the defence bought nothing measurable against the very exploit "
                 "it was built for, at this gamma, at 2752, at this n. The bound "
                 "is the cell's 95% CI."),
        "U-UNREADABLE": "no C statistic is reported.",
    }.get(branch, "unrecognised branch")
    return f"{base} {delta_note}".strip()


def joint_reading(branch: str, z, delta_note: str = "") -> str:
    """⭐ The MANDATORY prose for a JOINT cell's branch. `READ_RULE.md` §4.6b
    requires it printed beside every J result, whatever fired — and the
    attribution ban is appended to EVERY branch, including the nulls, because the
    tempting over-read of a null ("so neither term works") is the same error in
    the other direction."""
    base = {
        "PROMOTE": ("⭐ THE PACKAGE BEATS THE CHAMPION at this weight pair, at "
                    "2752, at n=400 deck-paired. " + JOINT_LICENSES),
        "BRACKET": ("the package reads >= +1σ against the champion but does not "
                    "resolve. ⛔ IT LICENSES NO H2H -- the chain's link 1 is a 2σ "
                    "bar, not a 1σ one. What it licenses is one more weight pair "
                    "on a fresh band, and the cost of that is named in §4.8."),
        "REVERSED": ("⚠️ THE PACKAGE COSTS POINTS against the champion at this "
                     "weight pair -- a real finding. ⛔ AND IT DOES NOT SAY WHICH "
                     "KNOB COSTS THEM: see the attribution ban below. ⚠️ Note "
                     "the weights here are far below round 2's A_HIGH beta 0.36, "
                     "whose over-correction mechanism produced the only REVERSED "
                     "reading this family has ever recorded, so a reversal at "
                     "these doses would be a genuinely NEW finding rather than a "
                     "re-observation of that one."),
        "NULL": ("a BOUND, not a zero. The bound is the cell's 95% CI. ⛔ AND IT "
                 "IS A BOUND ON THE PACKAGE, NOT ON EITHER TERM -- a null joint "
                 "is NOT evidence against beta and NOT evidence against gamma."),
        "U-UNREADABLE": "no joint statistic is reported.",
    }.get(branch, "unrecognised branch")
    return f"{base} {JOINT_ATTRIBUTION_BAN} {delta_note}".strip()


# --------------------------------------------------------------------------- #
# THE ROUND-LEVEL BRANCH TABLE (READ_RULE.md §4)                                #
# --------------------------------------------------------------------------- #
def round_branch(cell_branches: Mapping[str, str]) -> str:
    """READ_RULE §4's ROUND-level reading, FIRST-MATCH-WINS.

        U-UNREADABLE       any cell unreadable (G-WHEEL-SAME voids all eight)
        PROMOTE-<shapes>   some CHAIN-ELIGIBLE cell (A or J — opponent == the
                           champion of record) reads z >= +2.0. The J shape is
                           spelled `JOINT`. -> licenses ONE production-budget H2H
                           per firing shape, per the frozen four-link chain.
        DEFENDS-C          no chain-eligible promote, but some C cell reads
                           z >= +2.0 -> C-family only; NEVER the chain (§4.6)
        BRACKET-CONTINUE   nothing at +2.0, but something at >= +1.0
                           -> names what a round 4 would need, and its cost
        REVERSED-<shapes>  nothing at >= +1.0, but some cell reads z <= -2.0
        FAMILY-PARKS       every cell reads z < +1.0 and nothing REVERSED
                           -> parks the FORMULAS, never the MECHANISM

    Multiple shapes may PROMOTE; the label lists them, comma-separated, in CELL
    order. ⛔ Listing two shapes is NOT two confirmations of one effect and NOT an
    additive claim — each cell was adjudicated against zero, on its own disjoint
    decks, and §1 forbids any cross-cell contrast as a branch input. ⛔ AND IF
    BOTH `A` AND `JOINT` FIRE, THAT IS STILL NOT AN ATTRIBUTION of the joint
    margin to beta (`JOINT_ATTRIBUTION_BAN`): they are different leaves on
    different decks.
    """
    vals = [cell_branches.get(c.name) for c in CELLS]
    if any(v == "U-UNREADABLE" for v in vals) or any(v is None for v in vals):
        return "U-UNREADABLE"
    promo = [c.shape for c in CELLS
             if c.chain_eligible and cell_branches.get(c.name) == "PROMOTE"]
    if promo:
        seen = [s for i, s in enumerate(promo) if s not in promo[:i]]
        return "PROMOTE-" + ",".join(SHAPE_PROMOTE_LABEL[s] for s in seen)
    if any((not c.chain_eligible) and cell_branches.get(c.name) == "PROMOTE"
           for c in CELLS):
        return "DEFENDS-C"
    if any(v == "BRACKET" for v in vals):
        return "BRACKET-CONTINUE"
    rev = [c.shape for c in CELLS if cell_branches.get(c.name) == "REVERSED"]
    if rev:
        seen = [s for i, s in enumerate(rev) if s not in rev[:i]]
        return "REVERSED-" + ",".join(SHAPE_PROMOTE_LABEL[s] for s in seen)
    return "FAMILY-PARKS"


#: ⭐ WHAT `FAMILY-PARKS` PARKS, said before any number exists.
FAMILY_PARKS_MEANS = (
    "⛔ `FAMILY-PARKS` PARKS THE FORMULAS, NEVER THE MECHANISM. What would be "
    "parked is THIS PARAMETERISATION of T_A and T_C at THESE weights at 2752: "
    "three rounds, three bands, and no dose of either formula resolved against "
    "the champion. ⛔ IT IS NOT A FINDING ABOUT INVASION RISK AS A PHENOMENON. "
    "The E4 record stands untouched: the owner's farm-steal mechanism was "
    "MEASURED on-device in Stage A (memory `reference_android_app`) and the "
    "champion is behind the owner at phone conditions with one missing leaf term "
    "named. A parked formula means 'this arithmetic did not capture it', and the "
    "named next move is a DIFFERENT SHAPE (SHAPES.md §3's un-normalised variant "
    "is the standing candidate), not more weights on these two."
)

# --------------------------------------------------------------------------- #
# ⛔ THE LADDER RULES THAT CONSTRAIN EVERY FIRING BRANCH (READ_RULE.md §4.7)    #
# --------------------------------------------------------------------------- #
#: ⭐ THE HEADLINE STRUCTURAL CHANGE FROM ROUND 2.
A_AND_C_ARE_BRACKETED = (
    "⭐ BOTH A AND C ARE GENUINELY BRACKETED THIS ROUND, AND THAT IS NEW. Each "
    "runs THREE points on ONE band, so each has a real INTERIOR rung, §4.5b's "
    "interior-lift statistic is computable for both, and §4.7's noise-signature "
    "rule applies to both LITERALLY. Round 2 could say this of C only -- its A "
    "and B ladders had two points and no interior, so every A/B reading sat at an "
    "endpoint by construction. ⛔ THE ENDPOINT RULE HAS NOT BEEN REPEALED, IT HAS "
    "BEEN GIVEN SOMETHING TO BITE ON: a peak at A_LOW (beta 0.02) or A_HIGH (beta "
    "0.10), or at C_LOW (gamma 0.03) or C_HIGH (gamma 0.15), is STILL AT AN "
    "ENDPOINT and is STILL NOT BRACKETED. The licensed intervals leave headroom "
    "on purpose -- beta [0.01, 0.02] and [0.10, 0.12], gamma [0.02, 0.03] and "
    "[0.15, 0.23] -- so an endpoint peak has somewhere to be extended INTO "
    "without re-opening the licence."
)

#: ⭐ THE JOINT LADDER IS TWO POINTS, AND THEREFORE HAS NO INTERIOR.
JOINT_ENDPOINT_RULE = (
    "⛔ THE JOINT LADDER HAS TWO POINTS AND THEREFORE NO INTERIOR. Every J "
    "reading sits at an ENDPOINT by construction, exactly as every A/B reading "
    "did in round 2, and `feedback_bracket_hyperparams` says a peak at an "
    "endpoint is NOT BRACKETED. So: a PROMOTE at J_HIGH licenses the production "
    "H2H AT THAT WEIGHT PAIR and owes a ladder extension UPWARD before any claim "
    "about a joint optimum; a PROMOTE at J_LOW owes one DOWNWARD. ⛔ No branch "
    "may say 'the joint optimum is at (0.05, 0.07)' or 'the joint effect is "
    "monotone in dose' from two points. ⚠️ AND THE TWO J POINTS ARE NOT A "
    "ONE-DIMENSIONAL LADDER AT ALL -- they move BOTH knobs together, so even a "
    "resolved J low-vs-high contrast prices the DOSE OF THE PAIR and cannot say "
    "which knob's dose mattered."
)

NOISE_SIGNATURE_SIGMA = 1.0


def noise_signature(mid: Mapping | None, low: Mapping | None,
                    high: Mapping | None) -> dict:
    """READ_RULE §4.7's noise-signature check for ONE shape's interior rung.
    ⛔ It never moves a branch; it attaches a RE-MEASURE obligation to one."""
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
                "(feedback_results_table_source_of_truth, CLAUDE.md n-thresholds). "
                "⚠️ THIS IS EXACTLY WHAT DEMOTED SHAPE B: round 1's B_MID read "
                "+0.7575 between two round-2 rungs that read -0.6175 and +0.0225."
                if fired else "no noise signature — the interior rung does not "
                              "beat both neighbours by >1σ")}


def noise_signatures(stats_by_cell: Mapping) -> dict:
    """⭐ §4.7 over EVERY shape that has an interior rung — A and C this round.
    A two-point shape (J) is reported NOT APPLICABLE rather than silently
    skipped."""
    out = {}
    for sh in SHAPES:
        mid = cells_of_rung(sh, "mid")
        lo = cells_of_rung(sh, "low")
        hi = cells_of_rung(sh, "high")
        if mid is None:
            out[sh] = {"applicable": False, "fired": False,
                       "why": ("this shape has no INTERIOR rung (a two-point "
                               "ladder) — §4.7's ENDPOINT rule governs it "
                               "instead, see JOINT_ENDPOINT_RULE")}
            continue
        out[sh] = noise_signature(
            (stats_by_cell or {}).get(mid.name),
            (stats_by_cell or {}).get(lo.name) if lo else None,
            (stats_by_cell or {}).get(hi.name) if hi else None)
    return out


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
    independently-noisy near-zero quantities: it does not converge and its SIGN is
    not stable.
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
# ⛔ CARRIED VERBATIM FROM ROUND 2, plus the joint-leaf forward.                 #
# --------------------------------------------------------------------------- #
WHEEL_PROBE_FILENAME = "WHEEL_PROBE.json"

#: Every key the launcher's wheel probe must write true. Each names a DIFFERENT
#: failure the stale wheel produces, and a `hasattr` proxy is deliberately not
#: enough — DESIGN §7 requires the ACTUAL nonzero forward.
#: ⭐ `joint_two_knob_forward_ok` is NEW in round 3: the J cells forward TWO
#: nonzero invasion weights on ONE candidate leaf through `leaf_config_rs`'s
#: conditional kwargs, and nothing in rounds 1 or 2 ever exercised that.
WHEEL_PROBE_REQUIRED_TRUE = (
    "invasion_terms_attr",          # carc_rs.MirrorState has `invasion_terms`
    "nonzero_kwarg_forward_ok",     # leaf_config_rs(candidate cfg) built, every cell
    "cap_biconditional_ok",         # DESIGN §2.3's cap-forwarding biconditional holds
    "opp_side_forward_ok",          # the C cells' SHAPE-B OPPONENT leaf reaches rust
    "joint_two_knob_forward_ok",    # ⭐ the J cells' TWO-KNOB candidate leaf reaches rust
    "wheel_is_round_1s",            # G-WHEEL-SAME, asserted at pre-flight too
)


def wheel_probe_ok(probe: Mapping | None) -> tuple[bool, str]:
    """`(ok, reason)` for a `WHEEL_PROBE.json` payload. ABSENT is FAIL."""
    if not isinstance(probe, Mapping) or not probe:
        return False, "WHEEL_PROBE.json ABSENT or empty — ABSENT is FAIL"
    missing = [k for k in WHEEL_PROBE_REQUIRED_TRUE if probe.get(k) is not True]
    if missing:
        return False, ("wheel probe did not record a successful nonzero-kwarg "
                       f"forward on every side and shape: {', '.join(missing)} "
                       "not true")
    if not probe.get("carc_rs_build"):
        return False, "wheel probe carries no `carc_rs_build` fingerprint"
    return True, ("wheel probe recorded a successful nonzero-kwarg forward on "
                  "BOTH sides AND on the two-knob joint leaf, on round 1's own "
                  "wheel")


# --------------------------------------------------------------------------- #
# ⭐⭐ THE WEIGHT DERIVATION (DESIGN.md §3.2)                                    #
#                                                                              #
# ⛔ ROUND 3 IS THE FIRST ROUND OF THIS PROGRAM THAT **PICKS** WEIGHTS RATHER    #
# THAN INHERITING THEM. Rounds 1 and 2 could say "not re-picked": round 1 named #
# its six bracket points in its own DESIGN before it had an answer, and round 2 #
# ran exactly x1/3 and x3 of round 1's mids. Round 3 cannot say that -- the     #
# owner funded FINE LADDERS IN THE SMALL-WEIGHT REGION, which is by definition  #
# a re-pick. ⛔ SO THE DERIVATION IS DISCLOSED IN FULL, HERE, IN CODE, AND IT IS #
# RECOMPUTED AT IMPORT so the documented peaks cannot drift from the arithmetic #
# that produced them.                                                          #
#                                                                              #
# ⚠️ THE INPUTS ARE CROSS-BAND OVERLAYS AND THAT IS ALLOWED **ONLY HERE**.      #
# Choosing WHERE TO MEASURE is a design act; COMBINING READINGS is a statistical #
# one. This block does the first and never the second, and no round-3 branch    #
# reaches back into it. See `OVERLAY_RULE`.                                     #
# --------------------------------------------------------------------------- #
def _quad_through(points):
    """Fit `y = c + a*x + b*x^2` exactly through three `(x, y)` points; return
    `(c, a, b, vertex_x, is_max)`. Deliberately an EXACT interpolation, not a
    regression: three points, three parameters, no fitting freedom to hide in."""
    (x0, y0), (x1, y1), (x2, y2) = points
    # Newton divided differences — exact interpolation, no fitting freedom.
    f01 = (y1 - y0) / (x1 - x0)
    f12 = (y2 - y1) / (x2 - x1)
    b = (f12 - f01) / (x2 - x0)
    a = f01 - b * (x0 + x1)
    c = y0 - a * x0 - b * x0 * x0
    vertex = (-a / (2.0 * b)) if b != 0 else float("inf")
    return c, a, b, vertex, (b < 0)


#: ⭐ SHAPE A. THE STRUCTURAL ANCHOR IS `D(beta = 0) == 0 EXACTLY, BY
#: CONSTRUCTION` -- at weight zero the candidate IS the champion, which is
#: precisely the identity cell round 1 ran and passed. That anchor plus the two
#: small-weight readings the program owns (r2's beta 0.04 -> +0.936, r1's beta
#: 0.12 -> +0.524) determines a local quadratic, whose peak is the target.
#: ⚠️ ITS LIMITS, STATED: (i) it is a LOCAL small-weight fit and does NOT
#: extrapolate -- it predicts -18.99 at beta 0.36 against a realized -3.36, which
#: is a reason to trust it near zero and not far from it; (ii) the beta-0.12 point
#: is CROSS-BAND and read z=1.00, i.e. it is consistent with anything from ~0 to
#: ~1.6, so the peak location is soft; (iii) it is used to CHOOSE POINTS, never
#: as a prediction to be scored.
A_FIT = _quad_through([(0.0, 0.0), (0.04, 0.93625), (0.12, 0.52375)])

#: ⭐ SHAPE C. TWO READINGS ARE COMPUTED AND **BOTH** ARE REPORTED, because they
#: disagree and the ladder is chosen to bracket BOTH.
#:  (i)  THE R2-ONLY READING: the three round-2 C rungs alone (0.08/0.23/0.69)
#:       interpolate to a CONVEX curve whose vertex is a MINIMUM at gamma ~0.75,
#:       i.e. over the measured range the data are consistent with MONOTONE
#:       DECREASING -- which puts the peak AT OR BELOW 0.08, the ladder's own low
#:       endpoint, and therefore UNBRACKETED BELOW.
#:  (ii) THE ANCHORED READING: at gamma = 0 the candidate is the plain champion
#:       playing the shape-B invader, and the program's only estimate of THAT is
#:       round 1's B_MID with its sign flipped (-0.7575). ⛔ THE WEAKEST INPUT IN
#:       THIS FILE: cross-band AND sign-flipped AND z=1.27. It bends the curve
#:       into a concave one peaking near gamma 0.13 -- i.e. ABOVE 0.08.
#: ⛔ THE TWO DISAGREE, SO THE LADDER BRACKETS THE WHOLE CONTESTED REGION rather
#: than betting on either.
C_FIT_R2_ONLY = _quad_through([(0.08, 0.9975), (0.23, 0.195), (0.69, -1.01375)])
C_FIT_ANCHORED = _quad_through([(0.0, -0.7575), (0.08, 0.9975), (0.23, 0.195)])

#: The intervals the owner licensed for round 3, verbatim from the funded menu.
LICENSED_INTERVALS = {"invasion_beta": (0.01, 0.12), "invasion_gamma": (0.02, 0.23)}

WEIGHT_DERIVATION = {
    "why_a_re_pick_at_all": (
        "Round 2 answered the SCALING question and closed the large-weight end: "
        "A_HIGH at beta 0.36 read D -3.364 / z -5.77, the pre-registered "
        "over-correction, REVERSED. It also found the family's signals at the "
        "LIGHT end -- A_LOW beta 0.04 -> +0.936 / z 1.633 BRACKET, C_LOW gamma "
        "0.08 -> +0.998 / z 1.632 BRACKET -- and BOTH of those sat at the LOW "
        "ENDPOINT of their ladder, which feedback_bracket_hyperparams says is NOT "
        "BRACKETED. The owner funded fine ladders in the small-weight region "
        "precisely to fix that, so round 3 must pick points, and picking them is "
        "the design act disclosed here."),
    "A": {
        "knob": "invasion_beta",
        "licensed": LICENSED_INTERVALS["invasion_beta"],
        "inputs": [
            {"beta": 0.0, "D": 0.0, "source": "STRUCTURAL — at weight 0 the "
             "candidate IS the champion; round 1's IDENT cell measured that "
             "identity and PASSED (z 0.962, |z| <= 2.0)"},
            {"beta": 0.04, "D": 0.93625, "z": 1.6330435083755324,
             "source": f"round 2 A_LOW, band {R2_BAND} — ⛔ OVERLAY"},
            {"beta": 0.12, "D": 0.52375, "z": 0.9999257743437113,
             "source": f"round 1 A_MID, band {R1_BAND} — ⛔ OVERLAY"},
        ],
        "local_quadratic": {"c": A_FIT[0], "a": A_FIT[1], "b": A_FIT[2]},
        "peak": A_FIT[3], "peak_is_maximum": A_FIT[4],
        "chosen": (0.02, 0.05, 0.1),
        "log_ratios": (0.05 / 0.02, 0.1 / 0.05),
        "brackets": {
            "empirical_best_0.04": "between 0.02 and 0.05",
            f"local_fit_peak_{A_FIT[3]:.4f}": "between 0.05 and 0.10",
        },
        "headroom_left_for_round_4": [(0.01, 0.02), (0.1, 0.12)],
        "why_not_equal_to_a_prior_point": (
            "0.04 and 0.12 are OTHER-BAND overlays, so re-running either would "
            "produce a fresh independent reading rather than a repeat -- but "
            "near-but-not-equal points buy the same information AND add ladder "
            "resolution AND make it structurally impossible for a reader to pool "
            "a round-3 cell with its same-weight predecessor. Round 3 therefore "
            "avoids every prior beta (0.04, 0.12, 0.36) by construction."),
        "residual_risk": (
            "⚠️ IF THE TRUE OPTIMUM IS BELOW 0.02 the ladder peaks at its own low "
            "endpoint again and round 4 owes a further extension into [0.01, "
            "0.02]. The structural anchor argues against it -- D(0) == 0 exactly, "
            "so a peak below 0.02 needs a rise-and-fall sharper than the 0.04 and "
            "0.12 readings suggest -- but it is not excluded, and §4.7's endpoint "
            "rule is what catches it."),
    },
    "C": {
        "knob": "invasion_gamma",
        "licensed": LICENSED_INTERVALS["invasion_gamma"],
        "opponent": "⭐ THE SHAPE-B INVADER, not the champion — every C number "
                    "here is a DEFENCE-vs-INVADER margin",
        "inputs": [
            {"gamma": 0.0, "D": -0.7575,
             "source": "⛔ THE WEAKEST INPUT IN THIS DERIVATION: round 1's B_MID "
                       f"(+0.7575, band {R1_BAND}, z 1.27) WITH ITS SIGN FLIPPED "
                       "— at gamma 0 the C candidate is the plain champion facing "
                       "the invader, which is round 1's B_MID cell viewed from "
                       "the other seat. Cross-band AND sign-flipped AND z 1.27. "
                       "Used in ONE of the two readings and disclosed as soft."},
            {"gamma": 0.08, "D": 0.9975, "z": 1.6319401809638057,
             "source": f"round 2 C_LOW, band {R2_BAND} — ⛔ OVERLAY"},
            {"gamma": 0.23, "D": 0.195, "z": 0.3332580494284745,
             "source": f"round 2 C_MID, band {R2_BAND} — ⛔ OVERLAY"},
            {"gamma": 0.69, "D": -1.01375, "z": -1.562442782965787,
             "source": f"round 2 C_HIGH, band {R2_BAND} — ⛔ OVERLAY"},
        ],
        "reading_r2_only": {
            "quadratic": {"c": C_FIT_R2_ONLY[0], "a": C_FIT_R2_ONLY[1],
                          "b": C_FIT_R2_ONLY[2]},
            "vertex": C_FIT_R2_ONLY[3], "vertex_is_maximum": C_FIT_R2_ONLY[4],
            "says": ("CONVEX — the vertex is a MINIMUM and lies at gamma ~0.75, "
                     "OUTSIDE the measured range, so over [0.08, 0.69] the three "
                     "round-2 rungs are consistent with MONOTONE DECREASING. That "
                     "puts the peak AT OR BELOW 0.08, i.e. at round 2's own low "
                     "endpoint — UNBRACKETED BELOW."),
        },
        "reading_anchored": {
            "quadratic": {"c": C_FIT_ANCHORED[0], "a": C_FIT_ANCHORED[1],
                          "b": C_FIT_ANCHORED[2]},
            "vertex": C_FIT_ANCHORED[3], "vertex_is_maximum": C_FIT_ANCHORED[4],
            "says": ("CONCAVE — a genuine interior peak, near gamma 0.13, i.e. "
                     "ABOVE round 2's best point rather than below it."),
        },
        "chosen": (0.03, 0.07, 0.15),
        "log_ratios": (0.07 / 0.03, 0.15 / 0.07),
        "brackets": {
            "r2_only_reading (peak <= 0.08)": "0.03 sits below it; 0.07 and 0.15 above",
            "empirical_best_0.08": "between 0.07 and 0.15",
            f"anchored_peak_{C_FIT_ANCHORED[3]:.4f}": "between 0.07 and 0.15",
        },
        "headroom_left_for_round_4": [(0.02, 0.03), (0.15, 0.23)],
        "why_this_set": (
            "⛔ THE TWO READINGS DISAGREE ABOUT WHICH SIDE OF 0.08 THE PEAK IS ON, "
            "so the ladder is chosen to bracket the WHOLE contested region rather "
            "than to bet on either: 0.03 is below anything either reading "
            "suggests, 0.15 is above the anchored peak, and 0.07 sits between "
            "them near round 2's best point without repeating it. Log-uniform "
            "spacing (ratios 2.33 and 2.14) matches shape A's (2.50 and 2.00), so "
            "the two ladders have the same design language and the same "
            "resolution per rung."),
    },
    "J": {
        "knobs": ("invasion_beta", "invasion_gamma"),
        "chosen": ((0.02, 0.03), (0.05, 0.07)),
        "construction": (
            "⭐ THE JOINT POINTS ARE RUNG-MATCHED TO THE TWO FINE LADDERS, not "
            "picked separately: J_LOW is exactly (A_LOW's beta, C_LOW's gamma) and "
            "J_HIGH is exactly (A_MID's beta, C_MID's gamma). So each joint cell "
            "IS the pair of leaves this round is separately measuring, combined -- "
            "which is the only construction under which a later ABLATION pair "
            "could be posed against cells this round actually ran. "
            "⚠️ THAT IS A DESIGN CONVENIENCE FOR ROUND 4, NOT A LICENCE TO "
            "ATTRIBUTE IN ROUND 3: see JOINT_ATTRIBUTION_BAN."),
        "why_j_high_is_the_mid_rungs": (
            "J_HIGH takes each ladder's MID rung -- the best current guess of each "
            "term's own optimum -- rather than either ladder's high end, because "
            "the joint's job is to price the PACKAGE at plausible doses, and round "
            "2 showed this family punishes over-dosing hard (A_HIGH at beta 0.36 "
            "read z -5.77). J_LOW then takes both LOW rungs, ~0.4x of J_HIGH on "
            "each knob, to price whether the joint optimum sits BELOW the marginal "
            "optima -- the usual finding when two terms push the same direction "
            "through the same argmax."),
        "relation_to_the_funded_menu": (
            "The funded menu named {beta 0.04, gamma 0.08} as an example joint "
            "point -- round 2's two BRACKET weights. Round 3 runs the "
            "near-but-not-equal rung-matched pair {0.05, 0.07} instead, for the "
            "same reason the A and C ladders avoid prior points: it keeps every "
            "round-3 cell structurally unpoolable with a predecessor, and it "
            "makes the joint cells coincide with rungs this round measures."),
        "expectation_stated_before_any_number": (
            "⚠️ HOW MUCH OF C'S EFFECT SHOULD SURVIVE AGAINST A NON-TUNED "
            "OPPONENT IS AN OPEN QUESTION AND IS STATED AS ONE. C's +0.998 was "
            "measured against an agent TUNED to invade (alpha 0.09). The champion "
            "invades in the ordinary course of play but is not tuned to, so "
            "gamma's contribution against it should be SMALLER -- possibly null, "
            "possibly negative if the term's cost outweighs its rarer benefit. "
            "⛔ SO THE JOINT'S REALISTIC BEST CASE IS 'BETA'S GAIN, NOT DILUTED "
            "BY CARRYING GAMMA', and its power table row at +1.94 (the arithmetic "
            "sum) is a SIZING TARGET, not a prediction (JOINT_IS_NOT_A_SUM)."),
    },
    "unchanged_constants": {
        "G_sibling_p90_minus_p10": 1.76,
        "target_fraction_of_G": 0.40,
        "target_contribution_pts": 0.704,
        "M_A": 6.0, "M_B": 8.0, "M_C": 3.03, "M_D": 6.0,
        "alpha_cap": 11.0, "stub_max_tiles": 2,
        "note": ("⛔ NOT RE-DERIVED. These are round 1's frozen scale constants "
                 "and they are unchanged; round 3 re-picks WHERE ON THE LADDER to "
                 "measure, not what a leaf point is worth. Corroboration, also "
                 "unchanged: G=1.76 (median sibling p90-p10) matches the mean "
                 "top1-top2 gap of 1.72 within 3%, from a different definition."),
    },
}

#: The ladder as this round runs it. ⛔ EVERY POINT IS ROUND 3's OWN, on ONE band.
LADDER = {
    "A": {"knob": "invasion_beta", "low": 0.02, "mid": 0.05, "high": 0.1,
          "note": "⭐ a GENUINE three-point bracket on ONE band — A's first ever",
          "mid_source": "ROUND 3 — a genuine interior rung"},
    "C": {"knob": "invasion_gamma", "low": 0.03, "mid": 0.07, "high": 0.15,
          "note": "vs the SHAPE-B INVADER, on ONE band; a genuine interior rung",
          "mid_source": "ROUND 3 — a genuine interior rung"},
    "J": {"knob": "invasion_beta+invasion_gamma", "low": (0.02, 0.03), "mid": None,
          "high": (0.05, 0.07),
          "note": "⛔ TWO POINTS, NO INTERIOR — see JOINT_ENDPOINT_RULE",
          "mid_source": "n/a — the joint ladder has no interior rung"},
    "B": {"knob": "invasion_alpha", "low": 0.03, "mid": 0.09, "high": 0.27,
          "note": "⛔ NOT RUN AS A CANDIDATE — demoted in round 2 (noise "
                  "signature). ⭐ alpha 0.09 @ cap 11.0 IS the C cells' OPPONENT.",
          "mid_source": f"ROUND 1, band {R1_BAND}"},
    "D": {"knob": "invasion_delta_farm", "low": 0.04, "mid": 0.12, "high": 0.36,
          "note": "⛔ NOT RUN — see D_NOT_RUN", "mid_source": f"ROUND 1, band {R1_BAND}"},
}


# --------------------------------------------------------------------------- #
# THE POWER TABLES — §4.3 items 4, 7, 8                                         #
#                                                                              #
# ⛔ COMPUTED AT IMPORT FROM FROZEN CONSTANTS, not typed in. A hand-typed power  #
# table can drift from the SE it claims to use; this one cannot, and the        #
# instrument suite drives the relationships rather than re-asserting the         #
# numbers against themselves.                                                   #
#                                                                              #
# ⛔ A NULL IS A BOUND, NOT A ZERO. This table is MANDATORY output on every null.#
# --------------------------------------------------------------------------- #
def _phi(x: float) -> float:
    """Standard normal CDF, stdlib only."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def power_at(delta: float, se: float, bar: float = None) -> float:
    """One-sided power to clear `bar` sigma given a true effect `delta` and a
    per-cell SE. `P(z_obs >= bar) = Phi(delta/se - bar)`."""
    bar = PROMOTE_Z if bar is None else bar
    return _phi(delta / se - bar)


#: The two dispersions every power figure is published at, side by side.
SE_MODEL_400 = SIGMA_D_MODEL / 20.0            # the frozen CONSERVATIVE model
SE_REALIZED_400 = R2_MEAN_SIGMA_D / 20.0       # what round 2 ACTUALLY realized

#: The effect sizes the table is evaluated at, and WHY each one is on the list.
_POWER_ROWS = (
    (0.94, "⭐ round 2's A_LOW reading (+0.93625). If the A fine ladder's peak is "
           "no larger than round 2's best point, THIS ROUND CANNOT RESOLVE IT."),
    (1.00, "⭐ round 2's C_LOW reading (+0.9975), the same statement for gamma."),
    (1.47, ""),
    (1.71, "the 80%-power MDE at round 2's REALIZED dispersion"),
    (1.94, "⭐⭐ THE JOINT SIZING TARGET: the ARITHMETIC SUM of round 2's two "
           "BRACKET readings (+0.936 + +0.998). ⛔ A SIZING TARGET, NOT A "
           "PREDICTION — see JOINT_IS_NOT_A_SUM. It is on this table because the "
           "joint cell has to be sized against SOMETHING and this is the honest "
           "number to size against."),
    (2.08, "the 80%-power MDE at the FROZEN conservative model"),
)

POWER_TABLE = tuple(
    {"true_effect_pts": d,
     "z_at_model_se": d / SE_MODEL_400,
     "power_model": power_at(d, SE_MODEL_400),
     "z_at_realized_se": d / SE_REALIZED_400,
     "power_realized": power_at(d, SE_REALIZED_400),
     "note": note}
    for d, note in _POWER_ROWS
)

#: §4.5's low-vs-high contrast power, and §4.5b's interior-lift power, both
#: computed from the same two dispersions. ⛔ Computed BEFORE any answer exists.
CONTRAST_POWER = tuple(
    {"statistic": "§4.5 SCALING (D_high - D_low)",
     "sigma": label, "se_cell": s,
     "se_stat": math.sqrt(2.0) * s,
     "mde_2sigma_pts": CONTRAST_Z * math.sqrt(2.0) * s, "note": note}
    for label, s, note in (
        (f"frozen model {SIGMA_D_MODEL}", SE_MODEL_400,
         "sqrt(2) x the conservative per-cell SE"),
        (f"round-2 REALIZED {R2_MEAN_SIGMA_D}", SE_REALIZED_400,
         "sqrt(2) x what round 2 actually realized — the honest expectation"),
    )
)

LIFT_POWER = tuple(
    {"statistic": "§4.5b INTERIOR LIFT (D_mid - mean(D_low, D_high))",
     "sigma": label, "se_cell": s,
     "se_stat": math.sqrt(1.5) * s,
     "mde_2sigma_pts": CONTRAST_Z * math.sqrt(1.5) * s, "note": note}
    for label, s, note in (
        (f"frozen model {SIGMA_D_MODEL}", SE_MODEL_400,
         "sqrt(1.5) x the conservative per-cell SE — TIGHTER than the scaling "
         "contrast, because averaging the two neighbours halves their variance "
         "contribution"),
        (f"round-2 REALIZED {R2_MEAN_SIGMA_D}", SE_REALIZED_400,
         "sqrt(1.5) x round 2's realized per-cell SE"),
    )
)

#: ⭐ THE SINGLE MOST IMPORTANT SENTENCE IN §4, stated before game 1.
POWER_HEADLINE = (
    f"⛔ THIS ROUND IS POWERED TO RESOLVE ~{1.71:.2f} PTS/DECK AT 80%, AND THE "
    "TWO SIGNALS IT IS CHASING READ +0.94 AND +1.00 IN ROUND 2. So if the fine "
    "ladders' peaks are no larger than round 2's best points, EACH SINGLE A OR C "
    "CELL RESOLVES ONLY ~33-37% OF THE TIME even at round 2's realized "
    "dispersion, and ~24-26% at the frozen conservative model. ⭐ THAT IS THE "
    "DESIGN REASON THE JOINT CELLS EXIST: if beta and gamma are even weakly "
    "additive, the package is sized at ~+1.94, where power is ~89% realized / "
    "~74% modelled. ⛔ AND IT IS ALSO WHY A `FAMILY-PARKS` MUST NOT BE READ AS A "
    "REFUTATION OF ROUND 2 — this round is powered to resolve a peak, not to "
    "confirm a +1.0 effect, and a readout that says round 3 'failed to replicate' "
    "is wrong on the power arithmetic, not merely on the emphasis."
)

#: READ_RULE §5 — what NO branch does. Printed in full on every branch.
NO_BRANCH_DOES = (
    "No branch reports a production result — 2752 is the SCREENING budget, "
    "production is 11008. Screens aim, they don't verdict.",
    "No branch ranks the cells against each other — the eight deck ranges are "
    "DISJOINT and §1 forbids any cross-cell contrast as a branch input. The ONLY "
    "pre-registered exceptions are the within-shape low-vs-high contrast (§4.5) "
    "and the within-shape interior lift (§4.5b), and NEITHER is a branch input "
    "either.",
    "⛔⛔ No branch reads a JOINT cell as evidence about invasion_beta OR "
    "invasion_gamma SEPARATELY, in either direction, at any z. A joint cell is "
    "ONE leaf carrying TWO knobs and its margin is a property of the PAIR. "
    "Attribution needs a later ABLATION pair on a fresh band. See "
    "JOINT_ATTRIBUTION_BAN — this is round 3's headline over-read and it is "
    "forbidden explicitly.",
    "⛔ No branch treats a joint margin as the SUM of an A margin and a C margin, "
    "nor subtracts one from another to 'recover' a term. Those cells are on "
    "DISJOINT deck ranges and no such difference is a pre-registered statistic. "
    "The +1.94 row in the power table is a SIZING TARGET, not a prediction, and "
    "observing it would not confirm additivity (JOINT_IS_NOT_A_SUM).",
    "⛔ No branch pools, z-combines or averages a round-3 cell with a round-1 or "
    "round-2 reading. THREE BANDS NOW, so there are TWO tempting pools and BOTH "
    "are forbidden (CL-068: 1.8-2.2x cross-band over-dispersion, in BOTH "
    "statistics). The overlays are DESCRIPTIVE and their one legitimate use — "
    "choosing where round 3 measures — was spent in DESIGN §3.2 before any "
    "round-3 number existed.",
    "⛔ No branch identifies a round-3 cell with the round-2 cell of the SAME "
    "NAME. `A_LOW` was beta 0.04 on band 152e9 and is beta 0.02 on band 153e9; "
    "`C_MID` was gamma 0.23 and is gamma 0.07. The names repeat; the weights, the "
    "band and the box do not.",
    "⛔ No branch reads a C margin as evidence of STRENGTH. C's opponent is a "
    "shape-B invader, not the champion of record; a positive C margin means the "
    "DEFENCE PAYS AGAINST THE EXPLOIT and nothing more.",
    "⛔ No C reading of any size enters the four-link adoption chain, licenses a "
    "production H2H, edits governance/PRODUCTION.yaml, or opens a "
    "champion-of-record discussion. ⭐ The partnered follow-up a firing C would "
    "have licensed is ALREADY RUNNING as this round's J cells.",
    "⛔ No branch says anything about shape B AS A CANDIDATE. Round 2 demoted it "
    "on a noise signature and round 3 runs no B candidate cell. ⚠️ B's continued "
    "use as the C cells' INVADER-GENERATOR INSTRUMENT is not a claim about it as "
    "a candidate (SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE).",
    "No branch says anything about shape D at any weight other than round 1's "
    "mid — D is not run, for the third round running.",
    "No branch treats A and D as independent — T_A == (cities+roads part) + T_D "
    "exactly. Round 3 runs no D cell, so this bites only if a readout reaches "
    "back to round 1's D_MID.",
    "⛔ No branch says 'the optimum is at X' from an ENDPOINT. A and C have "
    "genuine interiors this round and §4.5b prices them — but a peak AT A_LOW, "
    "A_HIGH, C_LOW or C_HIGH is still at an endpoint, and EVERY J reading is at "
    "an endpoint because the joint ladder has only two points.",
    "No branch uses the ms/move ratio as evidence of anything but COST.",
    "No branch pools this band with any other (CL-068; band identity is "
    "load-bearing, and 153000000000 retires from confirmatory use once it has "
    "influenced a decision).",
    "⛔ No branch reads a FAMILY-PARKS as a REFUTATION of round 2, and no branch "
    "reads it as a finding about invasion risk as a PHENOMENON. See "
    "POWER_HEADLINE and FAMILY_PARKS_MEANS: what parks is THIS ARITHMETIC at "
    "THESE weights, and the E4 record stands untouched.",
    "⛔ No branch reads this round past a failed G-WHEEL-SAME. Round 3 carries no "
    "IDENT cell; it INHERITS round 1's (for the second time), and the inheritance "
    "is valid only while the wheel that proved it is the wheel that plays.",
    "⭐ No branch compares a LOCAL cell to a LAPTOP cell. None needs to: shapes "
    "are assigned WHOLE to one box, so every §4.5 contrast, every §4.5b lift and "
    "every §4.7 noise check is within-box. The same wheel file and the same "
    "code_rev make such a comparison plausible, but this round deliberately never "
    "validated it and no branch may rest on it.",
    "⛔ No branch treats W_LOCAL=14, the MEASURED laptop ratio (1.0935), or the "
    "joint leaf's realized per-move cost as anything but COST. W is "
    "throughput-only and games are bit-identical at any W; no gate in this pair "
    "reads a clock.",
    "⛔ No branch re-derives the weights after the fact. The derivation is "
    "WEIGHT_DERIVATION / DESIGN §3.2, it is recomputed at import from frozen "
    "inputs, and it was written before any round-3 number existed.",
)

#: READ_RULE §6 — the stated prior, recorded BEFORE game 1 so the readout can be
#: SCORED against it rather than FITTED to it. ⚠️ Priors, not bars.
STATED_PRIOR = (
    "~40% FAMILY-PARKS (nothing reaches +1σ). ~30% BRACKET-CONTINUE. ~18% "
    "PROMOTE-JOINT -- J_HIGH is the single most likely firing cell in the round, "
    "because it is the only cell sized against an effect (~+1.94 if beta and "
    "gamma are even weakly additive) that this n can actually resolve. ~7% "
    "PROMOTE-A (needs the A fine ladder's peak to be materially above round 2's "
    "+0.94; a peak merely EQUAL to it resolves ~1 time in 3). ~3% DEFENDS-C. ~2% "
    "any REVERSED reading -- ⭐ AND THAT LOW NUMBER IS A REAL PREDICTION, NOT "
    "OPTIMISM: the only reversal this family has ever produced was A_HIGH at beta "
    "0.36, whose over-correction mechanism (0.36 x M_A 6.0 = 2.16 leaf points, "
    "123% of G, a re-weighting of the leaf rather than a tilt on it) is 3.6x above "
    "this round's beta ceiling of 0.10 and out of range by construction. A "
    "reversal at round 3's doses would be a genuinely NEW finding. ⭐ THE SINGLE "
    "MOST IMPORTANT PRIOR is POWER_HEADLINE's: this round is powered to resolve "
    "~1.7 pts/deck and is chasing ~1.0, so the modal outcome is a bounded null "
    "that PARKS FORMULAS rather than a verdict about the mechanism."
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
        if len(c.knobs) != len(c.weights):
            problems.append(f"{c.name}: {len(c.knobs)} knobs but {len(c.weights)} weights")
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
        # every knob the cell claims to move must be in its candidate block, AT
        # its frozen weight — the JOINT generalisation of round 2's single check
        for k, w in zip(c.knobs, c.weights):
            if k not in c.cand_invasion:
                problems.append(f"{c.name}: its knob {k} is not in cand_invasion")
            elif c.cand_invasion[k] != w:
                problems.append(f"{c.name}: weight {w} != cand_invasion[{k}]")
        if c.is_joint and len(c.knobs) != 2:
            problems.append(f"{c.name}: a joint cell must move exactly two knobs")
        if (c.shape == "J") != c.is_joint:
            problems.append(f"{c.name}: shape {c.shape!r} disagrees with is_joint")
        if c.cand_leaf_hash == c.opp_leaf_hash:
            problems.append(f"{c.name}: the two sides pin the SAME leaf hash — the cell "
                            "would measure nothing")
        if c.cand_leaf_hash == PROD_LEAF_HASH:
            problems.append(f"{c.name}: a nonzero weight must MOVE the candidate hash "
                            "off the champion pin")
        if not c.allow_leaf_hash_drift:
            problems.append(f"{c.name}: every round-3 cell carries a nonzero weight and "
                            "MUST be launched with --allow-leaf-hash-drift")
        if (c.opponent == "shape_b") != c.shape_b_env:
            problems.append(f"{c.name}: opponent {c.opponent!r} disagrees with "
                            f"shape_b_env={c.shape_b_env} — the env regime IS how the "
                            "opponent leaf is set")
        if c.opponent == "shape_b" and c.opp_leaf_hash != SHAPE_B_LEAF_HASH:
            problems.append(f"{c.name}: a shape_b opponent must pin {SHAPE_B_LEAF_HASH}")
        if c.opponent == "champion" and c.opp_leaf_hash != PROD_LEAF_HASH:
            problems.append(f"{c.name}: a champion opponent must pin {PROD_LEAF_HASH}")
        if c.chain_eligible != (c.opponent == "champion"):
            problems.append(f"{c.name}: chain_eligible disagrees with the opponent")
        if c.leaf_json not in LEAF_JSON_BODIES:
            problems.append(f"{c.name}: no frozen JSON body for {c.leaf_json}")
        if c.box not in BOXES:
            problems.append(f"{c.name}: box {c.box!r} is not a known role")
        # ⭐ every weight must sit inside the interval the owner LICENSED
        for k, w in zip(c.knobs, c.weights):
            lo, hi = LICENSED_INTERVALS.get(k, (float("-inf"), float("inf")))
            if not (lo <= w <= hi):
                problems.append(f"{c.name}: {k}={w} is OUTSIDE the licensed interval "
                                f"[{lo}, {hi}]")
    # ⛔ the hash pins must be pairwise DISTINCT across cells, or two cells would
    # be the same leaf on different decks
    hashes = [c.cand_leaf_hash for c in CELLS]
    if len(set(hashes)) != len(hashes):
        problems.append("two cells pin the SAME candidate leaf hash")
    # ⭐ EVERY SHAPE MUST SIT WHOLLY ON ONE BOX (BOX_ASSIGNMENT_RULE)
    for sh in SHAPES:
        boxes = {c.box for c in cells_of_shape(sh)}
        if len(boxes) != 1:
            problems.append(f"shape {sh} is SPLIT across boxes {sorted(boxes)} — "
                            "§4.5's contrast and §4.5b's lift would become "
                            "cross-box statistics")
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
    # the eight ranges must be CONTIGUOUS as well as disjoint (DESIGN §5.1)
    ordered = sorted(CELLS, key=lambda c: c.seed_start)
    for a, b in zip(ordered, ordered[1:]):
        if b.seed_start != a.seed_end + 1:
            problems.append(f"gap/overlap between {a.name} and {b.name}")
    if SMOKE_CELL not in CELL_NAMES:
        problems.append(f"SMOKE_CELL {SMOKE_CELL!r} is not a cell")
    # every shape must have exactly one low and one high (the §4.5 contrast needs
    # both); A and C must ALSO have exactly one mid (the §4.5b lift needs it)
    for sh in SHAPES:
        rungs = [c.rung for c in cells_of_shape(sh)]
        if rungs.count("low") != 1 or rungs.count("high") != 1:
            problems.append(f"shape {sh}: the low-vs-high contrast needs exactly one "
                            f"low and one high rung, got {rungs}")
        want_mid = 1 if len(cells_of_shape(sh)) == 3 else 0
        if rungs.count("mid") != want_mid:
            problems.append(f"shape {sh}: a {len(rungs)}-point ladder wants "
                            f"{want_mid} mid rung(s), got {rungs.count('mid')}")
    # ⭐ the fixture must NOT be a round-3 cell, and its shape must not be one
    if FIXTURE_SPEC.name in CELL_NAMES:
        problems.append("FIXTURE_SPEC shares a name with a real cell")
    if FIXTURE_SPEC.shape in SHAPES:
        problems.append("FIXTURE_SPEC's shape is a round-3 shape — it must not be")
    # ⭐ THE COST MODEL MUST REPRODUCE ROUND 2's REALIZED WORKER-SECONDS PER GAME,
    # and it must do so WITHOUT EVER UNDER-PREDICTING (a funding model errs dear).
    _k = MOVES_PER_SIDE * OVERHEAD / 1000.0
    for label, modelled, realized in (
        ("A", _k * (MS_SHAPE_A_SIDE + MS_CHAMPION_SIDE), R2_REALIZED_S_PER_GAME["A"]),
        ("B", _k * (MS_SHAPE_B_SIDE + MS_CHAMPION_SIDE), R2_REALIZED_S_PER_GAME["B"]),
        ("C_on_laptop", _k * (MS_SHAPE_C_SIDE + MS_SHAPE_B_SIDE) * LAPTOP_RATIO_MEASURED,
         R2_REALIZED_S_PER_GAME["C_on_laptop"]),
    ):
        err = (modelled - realized) / realized
        if not (0.0 <= err <= 0.05):
            problems.append(f"cost model reproduces round 2's {label} at "
                            f"{modelled:.2f} s/game vs realized {realized:.2f} "
                            f"({err:+.2%}) — it must never UNDER-predict and never "
                            "over-predict by more than 5%")
    lo, hi = MS_SHAPE_J_ENVELOPE
    if not (lo <= MS_SHAPE_J_SIDE <= hi):
        problems.append("the joint-leaf point estimate is outside its own envelope")
    # ⭐ THE DERIVATION MUST ACTUALLY BRACKET WHAT IT CLAIMS TO BRACKET
    a_lo, a_mid, a_hi = WEIGHT_DERIVATION["A"]["chosen"]
    if not (a_lo < 0.04 < a_mid):
        problems.append("the A ladder does not bracket round 2's best beta (0.04)")
    if not (a_mid < A_FIT[3] < a_hi):
        problems.append(f"the A ladder does not bracket its own fit peak {A_FIT[3]:.4f}")
    if not A_FIT[4]:
        problems.append("the A local quadratic is not concave — its vertex is not a peak")
    c_lo, c_mid, c_hi = WEIGHT_DERIVATION["C"]["chosen"]
    if not (c_lo < 0.08 < c_hi):
        problems.append("the C ladder does not bracket round 2's best gamma (0.08)")
    if not (c_mid < C_FIT_ANCHORED[3] < c_hi):
        problems.append("the C ladder does not bracket the anchored fit peak")
    if C_FIT_R2_ONLY[4]:
        problems.append("the r2-only C interpolation was expected CONVEX (vertex a "
                        "minimum); it is not, and the derivation prose is stale")
    # ⭐ the two JOINT points must be exactly rung-matched to the two fine ladders
    for jname, arung, crung in (("J_LOW", "low", "low"), ("J_HIGH", "mid", "mid")):
        j = cell_by_name(jname)
        a = cells_of_rung("A", arung)
        c = cells_of_rung("C", crung)
        if j.dose.get("invasion_beta") != a.dose.get("invasion_beta"):
            problems.append(f"{jname}'s beta is not {a.name}'s")
        if j.dose.get("invasion_gamma") != c.dose.get("invasion_gamma"):
            problems.append(f"{jname}'s gamma is not {c.name}'s")
    # ⭐ the chosen split must be the wall-clock optimum among whole-shape splits
    rows = split_table()
    if not rows[0]["chosen"]:
        problems.append(f"the frozen box assignment is NOT the fastest whole-shape "
                        f"split at this round's W: rank "
                        f"{next(r['rank'] for r in rows if r['chosen'])} of {len(rows)}")
    return problems


if __name__ == "__main__":  # pragma: no cover — a convenience for the launcher
    import json as _json
    import sys as _sys
    bad = sanity_check()
    env = round_cost_envelope()
    print(_json.dumps({
        "band": BAND,
        "boxes": {r: {"W": BOXES[r]["W"], "share_mount": BOXES[r]["share_mount"],
                      "per_game_ratio": BOXES[r]["per_game_ratio"],
                      "ratio_is_measured": BOXES[r]["ratio_is_measured"],
                      "cells": [c.name for c in cells_of_box(r)],
                      "smoke": SMOKE_BY_BOX[r]} for r in BOX_ROLES},
        "cells": [{"name": c.name, "shape": c.shape, "box": c.box, "rung": c.rung,
                   "knobs": list(c.knobs), "weights": list(c.weights),
                   "dose_label": c.dose_label, "is_joint": c.is_joint,
                   "chain_eligible": c.chain_eligible,
                   "seed_start": c.seed_start, "seed_end": c.seed_end,
                   "n_decks": c.n_decks, "n_games": c.n_games,
                   "out_subdir": c.out_subdir, "leaf_json": c.leaf_json,
                   "cand_leaf_hash": c.cand_leaf_hash,
                   "opp_leaf_hash": c.opp_leaf_hash,
                   "opponent": c.opponent, "shape_b_env": c.shape_b_env,
                   "leaf_diff_keys": sorted(c.leaf_diff_keys),
                   "allow_leaf_hash_drift": c.allow_leaf_hash_drift}
                  for c in CELLS],
        "weight_derivation": {
            "A": {"peak": A_FIT[3], "chosen": WEIGHT_DERIVATION["A"]["chosen"]},
            "C": {"peak_r2_only": C_FIT_R2_ONLY[3],
                  "peak_anchored": C_FIT_ANCHORED[3],
                  "chosen": WEIGHT_DERIVATION["C"]["chosen"]},
            "J": {"chosen": WEIGHT_DERIVATION["J"]["chosen"]},
        },
        "split_table": split_table(),
        "round_cost_point": env["point"]["core_hours"],
        "round_cost_low": env["low"]["core_hours"],
        "round_cost_high": env["high"]["core_hours"],
        "round_cost_local_equiv": env["point"]["core_hours_local_equiv"],
        "wall_hours_point": env["point"]["wall_hours"],
        "wall_hours_single_box_local": env["point"]["wall_hours_single_box_local"],
        "per_box": {r: {"cells": b["cells"], "core_hours": b["core_hours"],
                        "wall_hours": b["wall_hours"], "W": b["W"]}
                    for r, b in env["point"]["per_box"].items()},
        "laptop_ratio_measured": LAPTOP_RATIO_MEASURED,
        "inherited_ident": R1_IDENT,
        "sanity_problems": bad,
    }, indent=2, default=str))
    _sys.exit(1 if bad else 0)
