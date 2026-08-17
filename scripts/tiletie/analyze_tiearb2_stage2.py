#!/usr/bin/env python3
"""Adjudicate measurement/tiearb2_stage2_20260817/READ_RULE.md — STAGE 2, PHASE B:
the deck-paired GAME cell for TERMINAL-GROUNDED TIE ARBITRATION.

Two cells, `ARB` (mode `argmax`) and `RND` (mode `random`, the wall-clock-matched
control), `B` = 16 / `J` = 4, salt `tiearb2-deploy-v1`, n = 800 deck-paired games
each on band 132000000000, against the unmodified champion.

It computes, per READ_RULE §2:

    M_arb, M_rnd  = summary.json::paired_mean_margin  (per-deck seat-balanced)
    z_arb, z_rnd  = summary.json::paired_z            ⚠️ READ, NEVER RECOMPUTED
    E_arb, E_rnd  = summary.json::elo (+ elo_sig_1sigma), the harness's own conversion
    D             = M_arb − M_rnd, DECK-PAIRED over `n_common` (the decks completed
                    in BOTH cells), with its own paired se
    z_D           = D / se(D), computed the SAME WAY `eval_fair_puct._paired_z`
                    computes its own (mean of per-deck values; var with ddof=1;
                    se = sqrt(var/n); z = mean/se, NaN when se == 0; (None, None, 0)
                    below two decks) — there is exactly ONE convention here.

then evaluates §3's preconditions (which VOID the run) and §4's branch table, in the
committed order, and writes `READOUT.json` + `READOUT.md` carrying every item of the
mandatory companion table §4.3.

⚠️ THE FIELD-NAME TRAP (READ_RULE §2 / §4.2, DESIGN §5, confirmed at live lines
2361/2371/2389 of `eval_fair_puct.py`): `champ_prefix_ms_per_move` **IS THE CANDIDATE
SIDE** in this harness. `ms_ratio = champ_prefix_ms_per_move / rung_ms_per_move` is
therefore candidate-over-opponent. A read-out that swaps them inverts the cost verdict.

⚠️ PARTIAL RUNS. Every statistic is computed at the realized `n` and the realized `n`
is reported. `G-N` still voids below the committed thresholds — a partial run is
READ, then declared `U-UNREADABLE` if it is short. Nothing is extrapolated.

⚠️ THIS ADJUDICATES THE **AMENDED** TEXT. `READ_RULE.md` §0 is a PRE-RUN AMENDMENT
(commit `6c281f9e`, made before the band claim and before game 1, with no band
claimed and no `summary.json` / `manifest.json` in existence). It fixes `G-N`'s
deck floor — the text committed at `b2faa238` read `n_common < 600`, which is
unreachable because a paired `n = 800` cell yields at most 400 decks
(`eval_fair_puct.py:3924`, `"n_decks": (args.n // 2 if args.paired else args.n)`),
so `G-N` would have fired on a PERFECTLY COMPLETE run — and names the `+1.0`
presentation split and the knob's top-level manifest location. **No adjudicating
bar moved**: `+2.0`, `+1.0` and `1.20` are unchanged and every §4 branch condition
is unchanged. `READ_RULE_AMENDMENT` is stamped in the read-out so a reader can see
which text was adjudicated against.

This computes NO estimator that already exists: the paired statistic is
`eval_fair_puct._paired_z`'s arithmetic, mirrored (§2 requires the same convention),
and the NaN-safe `_ge` comes from `analyze_tiearb` UNMODIFIED.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from analyze_tiearb import _ge                                       # noqa: E402

RUN_DIR = REPO / "measurement/tiearb2_stage2_20260817"
DESIGN_DOC = "measurement/tiearb2_stage2_20260817/DESIGN.md"
READ_RULE = "measurement/tiearb2_stage2_20260817/READ_RULE.md"
SCHEMA = "carcassonne-tiearb2-stage2-readout/v1"

#: Which text was adjudicated against. READ_RULE §0 is a PRE-RUN AMENDMENT applied
#: before the band claim and before game 1; it moved NO adjudicating bar.
READ_RULE_AMENDMENT = ("READ_RULE.md §0 — §0.A-C (PRE-RUN AMENDMENT) commit 6c281f9e; "
                       "§0.D (OWNER RULING, N4 downgrade waived) commit a81b8c72")

# ---- READ_RULE §2 committed bars — NOT new numbers -------------------------- #
Z_BAR = 2.0             # "+2.0 is Stage 1's, Stage 1b's, E-FLAT's and W-FLAT's verbatim"
Z_PRESENT_BAR = 1.0     # §2 (as amended, §0.C.1) — the G-PRESENT / G-FLAT PRESENTATION
                        #    split. ⚠️ NOT an adjudicating bar: both branches it
                        #    separates license NOTHING, so it selects a label and the
                        #    mandatory rider that travels with it, never a permission.
                        #    The two bars that gate a licence are +2.0 and 1.20.
MS_RATIO_BAR = 1.20     # §4.2 — the house N4 trigger currency
MS_RATIO_NEUTRAL = 1.05 # §4.2 — "≤ 1.05 restores a fully cost-neutral reading"

# ---- READ_RULE §3 committed gate constants ---------------------------------- #
CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"          # G-J1, an EQUALITY gate (inverted)
B_EXPECTED = 16                                # G-J4
J_EXPECTED = 4                                 # G-J4
SALT_EXPECTED = "tiearb2-deploy-v1"            # DESIGN §2 (reported; G-J4 names B/J/mode)
MODE_BY_CELL = {"ARB": "argmax", "RND": "random"}
PHI_FLOOR = 1.0                                # G-FIRE
BAND_EXPECTED = 132000000000                   # G-BAND
N_COMMON_FLOOR = 320                           # G-N, AMENDED §0.B — 80% of the 400 decks
                                               #   a paired n = 800 cell can produce
CELL_GAMES_PLANNED = 800                       # G-N
CELL_GAMES_FLOOR = 640                         # G-N — the same 80% bar, in games

ALL_GATES = ("G-J1", "G-J4", "G-J13", "G-FIRE", "G-BAND", "G-N", "G-TOOL", "G-STAT")
CELLS = ("ARB", "RND")

# ---- DESIGN §2.1 / §3 — the firing-rate prior and its funnel ---------------- #
PHI_PRIOR = 22.96                 # offline tied tile plies/game (E4 census, n = 26)
PHI_FUNNEL_EXACT_TIE_PCT = 65.98  # exact-tie rate on tile plies
PHI_FUNNEL_DEDUP_PCT = 40.4       # deduped scoreable

# ---- Phase A cost facts (COST_REMEASURE.json) — §4.3 item 7 ------------------ #
C_TIER1_RUST = 0.178232           # worker-s/playout, w30
C_TIER1_SPEEDUP_VS_PILOT = 15.30  # × the python pilot (2.7274)
RHO_WALL_16 = 0.6224
RHO_AMORTIZED_16 = 0.1985         # ⇒ the DESIGN §5 expected in-cell ms_ratio ≈ 1.1985
RHO_PHONE_16 = 5.520              # ⚠️ NOT SOLVED — the phone currency was never brought
                                  #    under 1.20 above B = 2; Phase A stamped it
                                  #    *reported, unadjudicated*
MS_RATIO_EXPECTED = 1.1985        # DESIGN §5, committed BEFORE the measurement

# ---- DESIGN §6 — the offline bound chain and this cell's power -------------- #
OFFLINE_ELO = 18.09
OFFLINE_ELO_LO = 6.32
OFFLINE_ELO_HI = 30.04
OFFLINE_ELO_LOW_BRACKET = 11.06   # the ÷5.23 low-end bracket
POWER_1SIGMA_ELO = 8.5            # n = 800 deck-paired
POWER_2SIGMA_ELO = 17.0

# ---- Stage 1b's published read, carried — NEVER a branch input -------------- #
STAGE1B_ARB_H = 0.1441            # pts/tied ply
STAGE1B_ARB_H_Z = 3.01

# ============================================================================ #
# VERBATIM CARRIES — §4.3 items 3 and 6. Copied from the committed documents.   #
# Reproduced character-for-character; DO NOT paraphrase, shorten or re-wrap.    #
# ============================================================================ #

#: DESIGN §0.2 — condition (b) of A-DEPLOYABLE, i.e. Stage 1b's DESIGN §12.1,
#: carried verbatim. Mandatory on EVERY branch, including the passing ones.
CONDITION_B_VERBATIM = (
    "⭐ **The arbiter and the pricing judge are both terminal-grounded.** They differ in\n"
    "policy (`RuleBasedPlayer` 1-ply argmax vs 100-sim clairvoyant PUCT) and are\n"
    "independent in the leaf, but they **share the property under test**. ⇒ **a positive\n"
    "here is evidence that terminal grounding at ties is worth points *as measured by a\n"
    "terminal-grounded ruler*, which is the estimand — it is NOT yet evidence of deploy\n"
    "elo.** This is why a pass licenses only a game-cell prereg, and why that prereg must\n"
    "be graded on games."
)

#: DESIGN §0.1 — condition (c), arm `C`'s NO CORROBORATION sign-check verdict,
#: carried verbatim. Mandatory on EVERY branch.
CONDITION_C_VERBATIM = (
    "**arm `C`** — over the **1050** positions where the arbiter changes the champion's\n"
    "pick in at least one fold: 511/1033 = **+0.495** with `arb[p] > 0`, exact two-sided\n"
    "binomial **p 0.756**; aggregate sign **+1**, per-position majority -1, mean over the\n"
    "pick-change positions +0.0414 ⇒ **NO CORROBORATION -- sign agreement is not\n"
    "distinguishable from chance**"
)

#: DESIGN §2.1 — the two runtime-vs-corpus mismatches, restated verbatim beside
#: every `phi` reading (§4.3 item 3).
MISMATCH_I_VERBATIM = (
    "**(i) The corpus predicate was evaluated on a REPLAYED board at the champion's seat.**\n"
    "At runtime it is evaluated inside a live search on the candidate's seat. The board\n"
    "distribution is the same population; the *evaluation context* is not identical."
)
MISMATCH_II_VERBATIM = (
    "**(ii) The corpus `champ_picks` came from a FRESH search.** CL-070 established that\n"
    "**reseeding alone flips picks**. ⇒ the offline firing rate **estimates** the runtime\n"
    "rate; it does not equal it."
)
MISMATCH_CONCLUSION_VERBATIM = (
    "⇒ **The offline 22.96 tied tile plies/game (E4 census, n = 26) is a prior, not a\n"
    "prediction.** The realized rate is measured in-cell and reported; §3 states what it may\n"
    "and may not do to a branch."
)

#: READ_RULE §4's `G-FLAT` mandatory scope sentence — quoted WITH the verdict and
#: never separated from it.
G_FLAT_SCOPE_SENTENCE = (
    "This is a BOUNDED null, not an exclusion. DESIGN §6 states before the run that "
    "n = 800 deck-paired resolves ≈ ±8.5 elo at 1σ (±17 at 2σ), while the offline bound "
    "chain reads +18.09 elo CI [+6.32, +30.04] with a ÷5.23 low-end bracket at +11.06 — "
    "so a null here does NOT exclude the low end of the offline estimate. The honest "
    "claim is 'terminal-grounded tie arbitration did not express as deploy elo at n = 800 "
    "on band 132000000000', NOT 'terminal grounding is worth nothing in games'."
)

#: `G-FLAT`'s SECOND rider — mandatory always on that branch.
G_FLAT_TENSION_RIDER = (
    "Stage 1b read `arb_H` = +0.1441 pts/tied ply at z +3.01 with the sign check "
    "CORROBORATING, so a flat game read is a TENSION WITH A PUBLISHED RESULT and must be "
    "reported as such — both are printed and the tension is NOT presented as resolved. "
    "The operative statement to record: the mechanism is real under a terminal-grounded "
    "ruler and did not survive the transfer to games at this power; DESIGN §12.1's caveat "
    "is therefore NOT discharged."
)

#: The N4 field-name trap — named wherever `ms_ratio` is printed (§4.2).
N4_FIELD_NAME_TRAP = (
    "⚠️ THE FIELD-NAME TRAP: `champ_prefix_ms_per_move` IS THE CANDIDATE SIDE in "
    "`eval_fair_puct` (confirmed at live lines 2361/2371/2389), the opposite of "
    "`eval_puct_priors`. `ms_ratio = champ_prefix_ms_per_move / rung_ms_per_move` is "
    "candidate-over-opponent. A read-out that swaps them INVERTS the verdict."
)

N4_RIDER = (
    "§4.2: `ms_ratio` is a DOWNGRADE TRIGGER, never a branch input. It does NOT touch "
    "the mechanism contrast D / z_D: ARB and RND are cost-matched to each other by "
    "construction, so D is immune to a budget confound. DESIGN §5 predicts ms_ratio ≈ "
    "1.1985 — just under the bar — and says so BEFORE the measurement, so a reading "
    "either side of 1.20 was anticipated and is not a surprise; ms_ratio ≤ 1.05 is a "
    "fully cost-neutral reading."
)

#: READ_RULE §0.D — the OWNER RULING, ruled before the band claim and before any game,
#: blind to every number it affects. It waives §4.2's DOWNGRADE, not the MEASUREMENT.
N4_WAIVER_BY = "READ_RULE.md §0.D (OWNER RULING), commit a81b8c72"
N4_WAIVER_OWNER_VERBATIM = (
    "we can afford some wallclock during play, especially if its not every tile draw. "
    "dont let that be the constraint right now"
)
N4_WAIVER_NOTE = (
    "⚠️ THE §4.2 DOWNGRADE IS WAIVED FOR THIS CELL (READ_RULE §0.D, an OWNER RULING made "
    "BEFORE the band claim and BEFORE any game, with no ms_ratio and no statistic of any "
    "kind in existence — blind to every number it affects). G-CONFIRMED / G-DEPLOYS / "
    "G-CLOCK are read AT FACE VALUE against the champion whatever ms_ratio lands at. "
    "WAIVED: the consequence. NOT WAIVED: the measurement — ms_ratio is still measured "
    "and reported for both cells on every branch, with the field-name trap named, and "
    "DESIGN §5's prediction (≈1.1985) is still printed against the realized value, "
    "because that comparison is the only way a wrong cost model becomes visible and its "
    "value does not depend on whether the bar is enforced. NO BRANCH CONDITION MOVES: "
    "§4.2's committed text already calls ms_ratio 'a downgrade trigger, not a conjunct' "
    "and 'NEVER a branch input', so waiving it cannot change which branch fires. §4 is "
    "left BYTE-IDENTICAL by the amendment — the override lives in §0.D — so the "
    "instrument's old-vs-new byte-equality proof over §4 still holds and is re-run as "
    "evidence. ⛔ ANTI-GAMING (binding): permission to SPEND clock, never licence to "
    "reshape the arbiter to look cheaper — B stays 16 (and may not be expanded), the tie "
    "predicate is not narrowed, and no playout truncation for cost reasons. rho_phone is "
    "NOT reopened (5.520 at B = 16) and no branch licenses an on-device deploy."
)

#: READ_RULE §0 — what the pre-run amendment changed, stamped on every read-out so a
#: reader can see which text was adjudicated against.
AMENDMENT_NOTE = (
    "This read-out adjudicates the AMENDED read-rule: READ_RULE.md §0 (PRE-RUN "
    "AMENDMENT), commit 6c281f9e, applied BEFORE the band claim and BEFORE game 1, with "
    "no band claimed and no summary.json / manifest.json in existence. §0.B set G-N's "
    "deck floor to n_common >= 320 — the exact 80% analogue of the committed 640/800 "
    "games clause, because a paired n = 800 cell yields at most 400 decks "
    "(eval_fair_puct.py:3924), which made the original 600-deck floor unreachable on a "
    "PERFECTLY COMPLETE run. §0.C.1 named the +1.0 presentation split in §2; §0.C.2 "
    "corrected the knob's manifest location to top-level `cand_tiearb`. §0.D (OWNER "
    "RULING, commit a81b8c72, also before the band claim and before any game and blind "
    "to every number it affects) WAIVES §4.2's COST-CONFOUNDED downgrade for this cell — "
    "the consequence, never the measurement. ⚠️ NO ADJUDICATING BAR MOVED: +2.0, +1.0 "
    "and 1.20 are unchanged and every §4 branch condition is unchanged — §4 is left "
    "BYTE-IDENTICAL by BOTH amendments, which is why the byte-equality proof against "
    "b2faa238 still runs and now covers two of them."
)

#: §0.C.1, carried so the presentation split can never be read as a licence bar.
Z_PRESENT_BAR_NOTE = (
    "+1.0 is NOT an adjudicating bar (READ_RULE §2 as amended, §0.C.1): the two branches "
    "it separates — G-PRESENT and G-FLAT — are alike NON-LICENSING, so it selects a "
    "LABEL and the mandatory rider that travels with it, never a permission. The two "
    "bars that gate a licence remain +2.0 and 1.20."
)

BRANCH_TEXT = {
    "G-ANOMALY": (
        "THE COST-MATCHED CONTROL ITSELF BEATS THE CHAMPION — THE FRAME IS WRONG AND "
        "NOTHING ELSE IN THIS TABLE MEANS WHAT IT SAYS.",
        "A *random* arm chosen at tied plies, after burning the identical playouts, wins "
        "games. That is a finding about the champion's own tie-break (or about spending "
        "clock at tied plies), NOT about terminal grounding. Both cells are reported in "
        "full, with D, z_D, both phi, both ms_ratio. NOTHING CLOSES AND NOTHING IS "
        "LICENSED."),
    "G-CONFIRMED": (
        "⭐ TERMINAL-GROUNDED TIE ARBITRATION WINS GAMES AGAINST THE CHAMPION, AND IT IS "
        "THE MECHANISM RATHER THAN THE CLOCK.",
        "The candidate convicts at 2σ on a fresh band, its wall-clock-matched control does "
        "not, and the two are RESOLVED against each other at 2σ. This is the first "
        "deploy-elo evidence on this axis and the only reading that discharges DESIGN "
        "§12.1's caveat. LICENSES (does NOT do) exactly one thing: a production-flip "
        "DECISION for the owner. ⛔ It does not flip PRODUCTION.yaml, does not license a "
        "leaf term (CL-065 + two dead menus + the 38% reach bound stand), does not license "
        "an on-device deploy (rho_phone = 5.520 at B = 16 — the phone currency was never "
        "solved), and does not license a second cell."),
    "G-DEPLOYS": (
        "THE CANDIDATE BEATS THE CHAMPION AND THE CONTROL DOES NOT — BUT THE TWO ARE NOT "
        "RESOLVED AGAINST EACH OTHER.",
        "z_arb >= +2 and D >= 0 and z_rnd < +2, yet z_D < +2. DESIGN §6 states BEFORE the "
        "run that n = 800 cannot resolve D to 2σ at the expected effect size (se(D) ≈ "
        "1.41× the single-cell se ⇒ a true +18 elo reads z_D ≈ 1.5), so this branch is "
        "EXPECTED on a real effect and is NOT a demerit. LICENSES (does NOT do) a "
        "production-flip DECISION for the owner, explicitly labelled as resting on an "
        "UNRESOLVED CONTROL. The read-out prints z_D and the n that would resolve D to 2σ."),
    "G-CLOCK": (
        "THE CANDIDATE BEATS THE CHAMPION, BUT ITS WALL-CLOCK-MATCHED CONTROL IS NOT "
        "EXCLUDED — THE WIN CANNOT BE ATTRIBUTED TO THE MECHANISM.",
        "RND burns the identical playouts on the identical worlds at the identical plies "
        "and picks at random, and it did at least as well. ⇒ what is being measured is "
        "clock, or pick perturbation, not terminal grounding. NOTHING CLOSES AND NOTHING "
        "IS LICENSED, and in particular this does NOT license a deploy decision."),
    "G-PRESENT": (
        "PRESENT BUT NOT CONVICTED — UNRESOLVED.",
        "The direction is there and the bar is not met. NOTHING CLOSES AND NOTHING IS "
        "LICENSED. Both cells are reported, with D, z_D, both phi, both ms_ratio, and the "
        "n that would convict at the realized dispersion."),
    "G-FLAT": (
        "THE MECHANISM DID NOT EXPRESS AS DEPLOY ELO ON A FRESH BAND AT n = 800.",
        "Mandatory scope sentence, quoted with the verdict and never separated from it: "
        + G_FLAT_SCOPE_SENTENCE),
    "U-UNREADABLE": (
        "UNREADABLE — a §3 precondition failed.",
        "Report cost, integrity, firing rates, and whichever gate failed. NOTHING CLOSES, "
        "NOTHING IS LICENSED, NOTHING IS RE-LABELLED."),
}


# --------------------------------------------------------------------------- #
# READ_RULE §2 — the paired statistic. ONE convention, mirrored from            #
# `eval_fair_puct._paired_z` (live at ~line 2208).                              #
# --------------------------------------------------------------------------- #
def per_deck_balanced(records) -> dict:
    """`{seed: (diff_seat0 + diff_seat1) / 2}` over the decks that completed BOTH
    seatings — exactly `_paired_z`'s `by_seed` / `ds` construction.

    `records` is any iterable of dicts carrying `seed`, `a_seat` and `diff`; a
    deck with only one seating is DROPPED (it is not seat-balanced), which is
    what makes a partial run readable at its realized `n`.
    """
    by_seed: dict = {}
    for r in records:
        by_seed.setdefault(int(r["seed"]), {})[int(r["a_seat"])] = float(r["diff"])
    return {s: (v[0] + v[1]) / 2.0 for s, v in by_seed.items() if 0 in v and 1 in v}


def paired_stats(values) -> tuple:
    """`(mean, se, z, n)` — `_paired_z`'s arithmetic, verbatim:

        mean = sum(ds) / len(ds)
        var  = sum((d - mean)**2) / (len(ds) - 1)        # ddof = 1
        se   = sqrt(var / len(ds))
        z    = mean / se   if se > 0   else NaN

    and `(None, None, None, n)` below two values, matching `_paired_z`'s
    `(None, None, 0)` early return. ⚠️ Do NOT invent a second convention here:
    `z_arb` / `z_rnd` are READ off `summary.json::paired_z`, and `z_D` must be
    computable by the same rule or the three z's are not comparable.
    """
    ds = list(values)
    n = len(ds)
    if n < 2:
        return None, None, None, n
    mean = sum(ds) / n
    var = sum((d - mean) ** 2 for d in ds) / (n - 1)
    se = math.sqrt(var / n)
    z = mean / se if se > 0 else float("nan")
    return mean, se, z, n


def deck_paired_D(arb_by_deck: dict, rnd_by_deck: dict) -> dict:
    """READ_RULE §2's `D` — `M_arb − M_rnd` DECK-PAIRED over `n_common`.

    The per-deck difference is taken FIRST and averaged second (that is what
    "deck-paired" means and it is why the deck draw largely cancels), over exactly
    the decks that completed in BOTH cells. Returns `D`, its paired `se`, `z_D`
    and `n_common`, plus the two cells' own means restricted to the common decks
    (so a reader can see that `D` is their difference and not a rescaling).
    """
    common = sorted(set(arb_by_deck) & set(rnd_by_deck))
    diffs = [arb_by_deck[s] - rnd_by_deck[s] for s in common]
    D, se, z, n = paired_stats(diffs)
    m_arb = (sum(arb_by_deck[s] for s in common) / len(common)) if common else None
    m_rnd = (sum(rnd_by_deck[s] for s in common) / len(common)) if common else None
    return {"D": D, "se_D": se, "z_D": z, "n_common": n,
            "n_common_decks": len(common),
            "M_arb_on_common": m_arb, "M_rnd_on_common": m_rnd,
            "deck_seed_min": (common[0] if common else None),
            "deck_seed_max": (common[-1] if common else None)}


def n_to_reach(n, z, target=Z_BAR):
    """The `n` that would carry `z` to `target` at the REALIZED dispersion:
    `n_needed = n * (target / z)**2` (z scales as sqrt(n)). `None` when `z` is
    absent, NaN, or non-positive — a wrong-signed effect is not resolved by more
    games and this must never print a finite promise. Returned in the units of
    `n` that was passed in (DECKS for a paired statistic)."""
    try:
        if n in (None, 0) or z is None or z != z or z <= 0:
            return None
    except TypeError:
        return None
    return int(math.ceil(n * (target / z) ** 2))


# --------------------------------------------------------------------------- #
# READ_RULE §3 — the preconditions. Each is a pure function of loaded dicts so   #
# a test can fail exactly one at a time.                                        #
# --------------------------------------------------------------------------- #
def _tiearb_cfg(manifest: dict):
    """The resolved top-level `cand_tiearb` knob.

    READ_RULE §3 `G-J4` as amended (§0.C.2) spells it **top-level `cand_tiearb`**,
    matching every shipped sibling knob (`cand_jrules_prior`,
    `cand_jrules_filter`, `cand_exact_objective` — all at manifest top level,
    `eval_fair_puct.py:3945`). The pre-amendment `config.cand_tiearb` spelling is
    still ACCEPTED and the one that was found is REPORTED, so the read-out never
    silently reads a knob from a place the pre-registration did not name. A dict
    is required: any other type is 'unresolved' and fails the gate.
    """
    for where, cfg in (("cand_tiearb", manifest.get("cand_tiearb")),
                       ("config.cand_tiearb",
                        (manifest.get("config") or {}).get("cand_tiearb"))):
        if cfg is not None:
            return (cfg if isinstance(cfg, dict) else None), where
    return None, None


def gate_j1(cells: dict) -> tuple:
    """`G-J1` — INVERTED: the candidate's resolved `cand_leaf_hash` must EQUAL the
    champion's. A DIFFERENCE is an ABORT, not a finding."""
    obs, ok = {}, True
    for c in CELLS:
        h = (cells.get(c) or {}).get("manifest", {}).get("cand_leaf_hash")
        obs[c] = h
        ok &= (h == CHAMP_LEAF_HASH)
    return bool(ok), {"expected_equal": CHAMP_LEAF_HASH, "observed": obs,
                      "semantics": "EQUALITY gate — a difference ABORTS the run"}


def gate_j4(cells: dict) -> tuple:
    """`G-J4` — the resolved knob is readable off disk: present, a dict, the right
    `mode` per cell, `B` = 16 and `J` = 4."""
    obs, ok = {}, True
    for c in CELLS:
        cfg, where = _tiearb_cfg((cells.get(c) or {}).get("manifest", {}))
        want = MODE_BY_CELL[c]
        good = bool(cfg is not None
                    and cfg.get("mode") == want
                    and cfg.get("B") == B_EXPECTED
                    and cfg.get("J") == J_EXPECTED)
        obs[c] = {"resolved_at": where, "cand_tiearb": cfg, "expected_mode": want,
                  "expected_B": B_EXPECTED, "expected_J": J_EXPECTED, "ok": good}
        ok &= good
    return bool(ok), obs


def gate_j13(preflights: list, expect_hosts) -> tuple:
    """`G-J13` — the TWO-SIDED positive control passed on EACH host before that
    host's game 1: the arbiter must CHANGE THE PICK at a constructed tied ply
    **and** leave `root_leaf_value_bits` UNCHANGED.

    Fail-closed: a missing witness on either side, a missing host, or a file that
    does not carry both booleans FAILS. "Without this a zeroed dose grades a
    perfect champion-vs-champion null wearing the shape of a real cell."
    """
    by_host, ok = {}, True
    for doc in preflights:
        host = doc.get("host")
        pos, neg = _j13_sides(doc)
        good = bool(doc.get("all_preflight_pass")) and pos is True and neg is True
        by_host[host] = {"all_preflight_pass": bool(doc.get("all_preflight_pass")),
                         "pick_changed": pos,
                         "root_leaf_value_bits_unchanged": neg,
                         "first_on_host": bool(doc.get("first_on_host", True)),
                         "path": doc.get("_path"), "ok": good}
        ok &= good
    missing = [h for h in (expect_hosts or []) if h not in by_host]
    if missing or not preflights:
        ok = False
    return bool(ok), {"hosts": by_host, "expected_hosts": list(expect_hosts or []),
                      "missing_hosts": missing,
                      "semantics": "TWO-SIDED: pick CHANGED and root_leaf_value_bits "
                                   "UNCHANGED, per host, before that host's game 1"}


def _j13_sides(doc: dict) -> tuple:
    """The two witnesses, from an explicit `two_sided` block or, failing that, from
    the `checks` list by name. `None` means ABSENT (which fails the gate) — never
    coerced to True."""
    ts = doc.get("two_sided")
    if isinstance(ts, dict):
        return (ts.get("pick_changed"), ts.get("root_leaf_value_bits_unchanged"))
    pos = neg = None
    for ch in doc.get("checks") or []:
        name = str(ch.get("check", ""))
        if "pick_change" in name or "pick_changed" in name:
            pos = bool(ch.get("ok"))
        if "root_leaf_value_bits" in name:
            neg = bool(ch.get("ok"))
    return pos, neg


def gate_fire(phi_arb, phi_rnd) -> tuple:
    """`G-FIRE` — `phi < 1.0` in EITHER cell voids: the arbitration surface is inert
    and the cell would grade a champion-vs-champion null wearing the shape of a
    real cell. An ABSENT phi fails (it cannot be shown to clear the floor)."""
    ok = _ge(phi_arb, PHI_FLOOR) and _ge(phi_rnd, PHI_FLOOR)
    return bool(ok), {"phi_arb": phi_arb, "phi_rnd": phi_rnd, "floor": PHI_FLOOR,
                      "prior": PHI_PRIOR}


def gate_band(cells: dict, band_claim: dict, expected_band=BAND_EXPECTED) -> tuple:
    """`G-BAND` — the band was claimed BEFORE game 1, and the two cells ran on the
    SAME band and the SAME decks."""
    seeds = {c: (cells.get(c) or {}).get("manifest", {}).get(
        "band_seed_start", (cells.get(c) or {}).get("manifest", {}).get("seed_start"))
        for c in CELLS}
    decks = {c: (cells.get(c) or {}).get("deck_seeds") for c in CELLS}
    claimed = bool(band_claim.get("claimed_before_game_1"))
    band_ok = (band_claim.get("band") == expected_band
               and all(s == expected_band for s in seeds.values()))
    same_decks = bool(decks["ARB"] is not None and decks["RND"] is not None
                      and set(decks["ARB"]) == set(decks["RND"]))
    # a partial run legitimately loses decks on one side; the gate asks that the
    # two cells were LAUNCHED on the same deck range, which is the manifest's
    # (seed_start, n) pair — the realized overlap is `n_common`, not this gate.
    launch = {c: ((cells.get(c) or {}).get("manifest", {}).get("seed_start"),
                  (cells.get(c) or {}).get("manifest", {}).get("n"))
              for c in CELLS}
    same_launch = launch["ARB"] == launch["RND"] and None not in launch["ARB"]
    ok = bool(claimed and band_ok and same_launch)
    return ok, {"expected_band": expected_band, "band_claim": band_claim,
                "claimed_before_game_1": claimed, "band_seed_start": seeds,
                "same_launch_deck_range": same_launch, "launch": launch,
                "realized_deck_sets_identical": same_decks}


def gate_n(n_common, n_arb, n_rnd) -> tuple:
    """`G-N` AS AMENDED (§0.B) — `n_common < 320` **decks**, OR either cell completed
    fewer than 640 of its 800 paired **games**.

    Both clauses are the SAME 80% completion bar in their own units (640 games IS
    320 decks), which is why they now agree instead of contradicting. The deck
    clause stays INDEPENDENTLY BINDING: two cells can each clear 640 games while
    overlapping on fewer than 320 COMMON decks, which would silently weaken `D`,
    and that must still void.
    """
    try:
        nc_ok = n_common is not None and n_common >= N_COMMON_FLOOR
    except TypeError:
        nc_ok = False
    cell_ok = all(v is not None and v >= CELL_GAMES_FLOOR for v in (n_arb, n_rnd))
    return bool(nc_ok and cell_ok), {
        "n_common": n_common, "n_common_floor": N_COMMON_FLOOR,
        "n_common_units": "DECKS (READ_RULE §2)",
        "n_games": {"ARB": n_arb, "RND": n_rnd},
        "cell_games_floor": CELL_GAMES_FLOOR, "cell_games_planned": CELL_GAMES_PLANNED,
        "both_clauses_are_the_same_80pct_bar": "640 games IS 320 decks",
        "deck_clause_independently_binding": (
            "two cells can each clear 640 games while overlapping on fewer than 320 "
            "COMMON decks — that weakens D and still voids"),
        "read_rule_amendment": READ_RULE_AMENDMENT}


def gate_tool(cells: dict, preflights: list) -> tuple:
    """`G-TOOL` — the two boxes ran the same rust toolchain / the same `carc_rs`
    build, and no cell mixed builds. Fail-closed on an absent stamp."""
    def _bad(x):
        """An absent stamp, or the harness's own provenance-failure sentinel
        (`"<unavailable: ...>"`, `eval_fair_puct` ~line 4498). ⚠️ Without this the
        sentinel PASSES the gate: both cells carry the SAME sentinel string, so a
        pure equality check sees one distinct build and calls it agreement."""
        return x is None or (isinstance(x, str)
                             and (not x.strip() or x.startswith("<unavailable")))

    stamps, ok = {}, True
    seen = set()
    for c in CELLS:
        m = (cells.get(c) or {}).get("manifest", {})
        tc = m.get("rust_toolchain")
        # ⚠️ `carc_rs_version` is the CARGO version and does NOT move between
        # builds — it cannot tell a fresh wheel from a stale one. `carc_rs_build`
        # is the content hash and is the witness of record; the version is only a
        # fallback, and it is reported as a weaker one.
        rs = m.get("carc_rs_build", m.get("carc_rs_version"))
        mixed = m.get("mixed_builds")
        stamps[c] = {"rust_toolchain": tc, "carc_rs_build": rs, "mixed_builds": mixed,
                     "build_witness": ("carc_rs_build (content hash)"
                                       if m.get("carc_rs_build") is not None else
                                       "carc_rs_version (WEAK — cargo version does not "
                                       "move between builds)")}
        # `mixed_builds is None` means the provenance block RAISED — unknown, not clean.
        if _bad(tc) or _bad(rs) or mixed is None or bool(mixed):
            ok = False
        seen.add((tc, rs))
    for doc in preflights:
        tc = doc.get("rust_toolchain")
        rs = doc.get("carc_rs_build", doc.get("carc_rs_version"))
        stamps[f"preflight:{doc.get('host')}"] = {"rust_toolchain": tc,
                                                  "carc_rs_build": rs}
        if _bad(tc) or _bad(rs):
            ok = False
        seen.add((tc, rs))
    if len(seen) != 1:
        ok = False
    return bool(ok), {
        "stamps": stamps, "distinct_builds": len(seen),
        "cross_box_note": (
            "under --shared-claim a second box writes NO manifest, so the "
            "authoritative cross-box comparison is the PREFLIGHT_*_${HOST}_FIRST.json "
            "witnesses against each other — they are folded into the same equality "
            "set here (eval_fair_puct ~line 4484)")}


def gate_stat(z_arb, z_rnd, z_D) -> tuple:
    """`G-STAT` — `z_arb`, `z_rnd` or `z_D` is NaN or absent.

    ⭐ READ_RULE §4.1: this is what guarantees no branch is ever entered on a NaN
    comparison — every NaN in the three z's routes to `U-UNREADABLE` HERE, in §3,
    BEFORE §4 takes a comparison."""
    obs = {"z_arb": z_arb, "z_rnd": z_rnd, "z_D": z_D}
    bad = [k for k, v in obs.items()
           if v is None or (isinstance(v, float) and v != v)]
    return (not bad), {"observed": obs, "nan_or_absent": bad}


def evaluate_preconditions(cells: dict, preflights: list, band_claim: dict,
                           expect_hosts, n_common, z_arb, z_rnd, z_D) -> tuple:
    """§3, in the committed order. Returns `({gate: bool}, {gate: detail})`."""
    n_arb = (cells.get("ARB") or {}).get("n_games")
    n_rnd = (cells.get("RND") or {}).get("n_games")
    phi_arb = (cells.get("ARB") or {}).get("phi")
    phi_rnd = (cells.get("RND") or {}).get("phi")
    order = (("G-J1", gate_j1(cells)),
             ("G-J4", gate_j4(cells)),
             ("G-J13", gate_j13(preflights, expect_hosts)),
             ("G-FIRE", gate_fire(phi_arb, phi_rnd)),
             ("G-BAND", gate_band(cells, band_claim)),
             ("G-N", gate_n(n_common, n_arb, n_rnd)),
             ("G-TOOL", gate_tool(cells, preflights)),
             ("G-STAT", gate_stat(z_arb, z_rnd, z_D)))
    return {k: v[0] for k, v in order}, {k: v[1] for k, v in order}


# --------------------------------------------------------------------------- #
# READ_RULE §4 — fully mechanical, a PURE function of emitted numbers.          #
# --------------------------------------------------------------------------- #
def decide_branch(z_arb, z_rnd, z_D, D, preconditions: dict) -> dict:
    """READ_RULE §3 (preconditions, FIRST) then §4, verbatim.

        U-UNREADABLE  ≡  any §3 gate failed                  (pre-empts EVERYTHING)
        G-ANOMALY     ≡  z_rnd >= +2.0                       (pre-empts the rest)
        p ≡ C_arb     ≡  z_arb >= +2.0
        q ≡ C_ctl     ≡  D     >= 0
        r ≡ C_res     ≡  z_D   >= +2.0

        p ∧ q ∧ r  -> G-CONFIRMED
        p ∧ q ∧ ¬r -> G-DEPLOYS
        p ∧ ¬q     -> G-CLOCK      (TOTAL in r; r => q makes p ∧ ¬q ∧ r vacuous)
        ¬p ∧ (z_arb >= +1.0 ∨ z_D >= +1.0)  -> G-PRESENT
        ¬p ∧ ¬(z_arb >= +1.0 ∨ z_D >= +1.0) -> G-FLAT   (the EXACT negation)

    NaN never satisfies any conjunct (`_ge`), and §3's `G-STAT` has already routed
    every NaN z to `U-UNREADABLE` before this function is reached on a real run.
    Takes ONLY numbers and booleans, so a test can sweep it.
    """
    failed = sorted(k for k, ok in preconditions.items() if not ok)
    base = {"branch": "U-UNREADABLE", "failed_preconditions": failed,
            "p": None, "q": None, "r": None, "G_ANOMALY": None, "PRESENT": None,
            "z_arb": z_arb, "z_rnd": z_rnd, "z_D": z_D, "D": D,
            "failed_conjuncts": [],
            "branch_headline": BRANCH_TEXT["U-UNREADABLE"][0],
            "read": BRANCH_TEXT["U-UNREADABLE"][1]}
    if failed:
        return base

    anomaly = _ge(z_rnd, Z_BAR)
    p = _ge(z_arb, Z_BAR)
    q = _ge(D, 0.0)
    r = _ge(z_D, Z_BAR)
    present = _ge(z_arb, Z_PRESENT_BAR) or _ge(z_D, Z_PRESENT_BAR)

    if anomaly:
        br = "G-ANOMALY"
    elif p and q and r:
        br = "G-CONFIRMED"
    elif p and q:
        br = "G-DEPLOYS"
    elif p:
        br = "G-CLOCK"
    elif present:
        br = "G-PRESENT"
    else:
        br = "G-FLAT"

    base.update({"branch": br, "failed_preconditions": [],
                 "p": p, "q": q, "r": r, "G_ANOMALY": anomaly, "PRESENT": present,
                 "failed_conjuncts": _failed_conjuncts(p, q, r),
                 "branch_headline": BRANCH_TEXT[br][0], "read": BRANCH_TEXT[br][1]})
    return base


def _failed_conjuncts(p, q, r) -> list:
    """Which of the top branch's three conjuncts did not hold — named exactly."""
    out = []
    if p is False:
        out.append("p = C_arb (z_arb >= +2.0)")
    if q is False:
        out.append("q = C_ctl (D >= 0)")
    if r is False:
        out.append("r = C_res (z_D >= +2.0)")
    return out


def cost_rider(ms_ratio_arb, ms_ratio_rnd, waived=True) -> dict:
    """§4.2 — a DOWNGRADE TRIGGER, never a branch input, and it never touches
    `D` / `z_D` (ARB and RND are cost-matched to each other by construction).

    ⚠️ `waived` implements READ_RULE §0.D's OWNER RULING: the DOWNGRADE is waived
    for this cell, the MEASUREMENT is not. `N4_FIRED` is therefore still computed
    and reported exactly as before — only `cost_confounded` (the consequence) is
    suppressed. Defaults to the ruling. This function CANNOT move a branch either
    way: `decide_branch` never sees it (asserted in `tests/`).
    """
    def gt(x):
        try:
            return bool(x == x and x > MS_RATIO_BAR)
        except TypeError:
            return False

    def le_neutral(x):
        try:
            return bool(x == x and x <= MS_RATIO_NEUTRAL)
        except TypeError:
            return False

    fired = gt(ms_ratio_arb) or gt(ms_ratio_rnd)
    # ⚠️ §4.3(4) makes the MEASUREMENT mandatory on every branch. §0.D waived the
    # consequence, not the measurement — so an ABSENT ms_ratio is a DEFECT in the
    # read-out and is shouted about, on every branch, waiver or no waiver.
    missing = [c for c, v in (("ARB", ms_ratio_arb), ("RND", ms_ratio_rnd))
               if v is None or v != v]
    return {"ms_ratio_arb": ms_ratio_arb, "ms_ratio_rnd": ms_ratio_rnd,
            "bar": MS_RATIO_BAR, "neutral_bar": MS_RATIO_NEUTRAL,
            "expected_from_design_5": MS_RATIO_EXPECTED,
            "prediction_vs_realized": {
                "predicted": MS_RATIO_EXPECTED,
                "realized": {"ARB": ms_ratio_arb, "RND": ms_ratio_rnd},
                "delta": {c: (None if (v is None or v != v) else v - MS_RATIO_EXPECTED)
                          for c, v in (("ARB", ms_ratio_arb), ("RND", ms_ratio_rnd))},
                "why": ("evidence about the COST MODEL, and its value does not depend on "
                        "whether the bar is enforced — it is the only way a wrong cost "
                        "model becomes visible. DESIGN §5 pre-registered ≈1.1985 before "
                        "the measurement.")},
            "N4_FIRED": fired,
            # the CONSEQUENCE, waived by §0.D
            "downgrade_waived": bool(waived),
            "n4_downgrade_waived_by": (N4_WAIVER_BY if waived else None),
            "owner_ruling_verbatim": (N4_WAIVER_OWNER_VERBATIM if waived else None),
            "cost_confounded": bool(fired and not waived),
            "cost_neutral": bool(le_neutral(ms_ratio_arb) and le_neutral(ms_ratio_rnd)),
            "ms_ratio_missing": missing,
            "MEASUREMENT_DEFECT": bool(missing),
            "applies_to": "the AGAINST-CHAMPION reading only — D / z_D are immune",
            "field_name_trap": N4_FIELD_NAME_TRAP, "rider": N4_RIDER,
            "waiver_note": (N4_WAIVER_NOTE if waived else None)}


# --------------------------------------------------------------------------- #
# IO — deliberately THIN: it turns files into the plain dicts every function     #
# above already takes, and does no arithmetic and no adjudication.              #
# --------------------------------------------------------------------------- #
def load_records(cell_dir) -> list:
    """Every per-game `GameResult` in a cell dir. NON-recursive by construction —
    `eval_fair_puct` writes failure records to the `failed/` SUBDIRECTORY exactly
    so a glob like this cannot mistake one for a game."""
    if cell_dir is None:
        return []
    out = []
    for p in sorted(Path(cell_dir).glob("seed*_a*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if "diff" in d and "seed" in d and "a_seat" in d:
            out.append(d)
    return out


def cell_phi(records: list, summary: dict):
    """`phi` — realized tied tile plies per game at which the arbiter FIRED,
    from the candidate's own per-game instrumentation (`cand_tiearb.fires`),
    falling back to a summary-level mean. `None` when neither exists, which
    FAILS `G-FIRE` (fail-closed: an unmeasured surface is not a live one)."""
    fires = [r["cand_tiearb"]["fires"] for r in records
             if isinstance(r.get("cand_tiearb"), dict)
             and r["cand_tiearb"].get("fires") is not None]
    if fires:
        return sum(float(f) for f in fires) / len(fires)
    for k in ("tiearb_phi", "phi", "tiearb_fires_per_game"):
        if summary.get(k) is not None:
            return float(summary[k])
    return None


def load_cell(name: str, summary_path, manifest_path, records_dir=None) -> dict:
    """One cell -> the plain dict every §3/§4 function above consumes."""
    summary = json.loads(Path(summary_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    records = load_records(records_dir if records_dir is not None
                           else Path(summary_path).parent)
    by_deck = per_deck_balanced(records)
    ms_ratio = None
    champ_ms = summary.get("champ_prefix_ms_per_move")   # ⚠️ THE CANDIDATE SIDE
    rung_ms = summary.get("rung_ms_per_move")            # ⚠️ the OPPONENT side
    if champ_ms is not None and rung_ms:
        ms_ratio = champ_ms / rung_ms
    return {
        "cell": name, "summary": summary, "manifest": manifest,
        "summary_path": str(summary_path), "manifest_path": str(manifest_path),
        "n_games": summary.get("n", len(records)),
        "n_records_on_disk": len(records),
        "n_decks_seat_balanced": len(by_deck),
        "by_deck": by_deck, "deck_seeds": sorted(by_deck),
        # ⚠️ READ, never recomputed (READ_RULE §2)
        "M": summary.get("paired_mean_margin"),
        "z": summary.get("paired_z"),
        "n_paired": summary.get("n_paired"),
        "elo": summary.get("elo"), "elo_sig_1sigma": summary.get("elo_sig_1sigma"),
        "wr": summary.get("winrate"), "wr_z": summary.get("winrate_z"),
        "W": summary.get("W"), "D_draws": summary.get("D"), "L": summary.get("L"),
        "n_failed": summary.get("n_failed"), "failure_rate": summary.get("failure_rate"),
        "champ_prefix_ms_per_move": champ_ms, "rung_ms_per_move": rung_ms,
        "ms_ratio": ms_ratio,
        "phi": cell_phi(records, summary),
        "seat_balance": _seat_balance(records),
        # a WITNESS, never a branch input: our own recomputation of the cell's z
        # from the records, so a summary/records mismatch is visible.
        "recomputed": dict(zip(("M", "se", "z", "n"), paired_stats(by_deck.values()))),
    }


def _seat_balance(records: list) -> dict:
    """`a_seat` is the CANDIDATE's seat; `_paired_z` averages the two per deck, so
    neither side owns a seat. Reported as §4.3 item 1 asks."""
    s0 = sum(1 for r in records if int(r.get("a_seat", -1)) == 0)
    s1 = sum(1 for r in records if int(r.get("a_seat", -1)) == 1)
    return {"a_seat_0": s0, "a_seat_1": s1, "balanced": s0 == s1}


def load_preflights(paths) -> list:
    out = []
    for p in paths or []:
        doc = json.loads(Path(p).read_text())
        doc["_path"] = str(p)
        out.append(doc)
    return out


def load_band_claim(path, expected_band=BAND_EXPECTED) -> dict:
    """The claim artefact. Accepts the JSON shape and the plain-text house shape
    (`BAND_CLAIMED.json` is historically three lines: band, label, 'claimed <date>').
    Never invents a claim: an unreadable/absent file yields a claim that FAILS."""
    if path is None:
        return {"band": None, "claimed_before_game_1": False, "source": None,
                "note": "no --band-claim given"}
    p = Path(path)
    if not p.exists():
        return {"band": None, "claimed_before_game_1": False, "source": str(p),
                "note": "band-claim artefact ABSENT"}
    raw = p.read_text()
    try:
        doc = json.loads(raw)
        if isinstance(doc, dict):
            doc.setdefault("source", str(p))
            doc.setdefault("claimed_before_game_1",
                           bool(doc.get("claimed_date") or doc.get("claimed_utc")))
            return doc
    except Exception:
        pass
    first = raw.strip().splitlines()[0].strip() if raw.strip() else ""
    m = re.match(r"^(\d+)$", first)
    return {"band": (int(m.group(1)) if m else None),
            "claimed_before_game_1": bool(re.search(r"^claimed\s", raw, re.M)),
            "raw": raw.strip(), "source": str(p),
            "expected_band": expected_band}


# --------------------------------------------------------------------------- #
def build_readout(args) -> dict:
    arb = load_cell("ARB", args.arb_summary, args.arb_manifest, args.arb_records)
    rnd = load_cell("RND", args.rnd_summary, args.rnd_manifest, args.rnd_records)
    cells = {"ARB": arb, "RND": rnd}
    preflights = load_preflights(args.preflight)
    band_claim = load_band_claim(args.band_claim)

    d = deck_paired_D(arb["by_deck"], rnd["by_deck"])
    z_arb, z_rnd = arb["z"], rnd["z"]

    pre, pre_detail = evaluate_preconditions(
        cells, preflights, band_claim, args.expect_host,
        d["n_common"], z_arb, z_rnd, d["z_D"])
    branch = decide_branch(z_arb, z_rnd, d["z_D"], d["D"], pre)
    cost = cost_rider(arb["ms_ratio"], rnd["ms_ratio"])

    e_hi = _elo_95_upper(arb)
    readout = {
        "schema": SCHEMA, "design": DESIGN_DOC, "read_rule": READ_RULE,
        "band": BAND_EXPECTED,
        "branch": branch["branch"],
        "branch_headline": branch["branch_headline"],
        "read": branch["read"],
        "failed_preconditions": branch["failed_preconditions"],
        "failed_conjuncts": branch["failed_conjuncts"],
        "p_q_r": {"p": branch["p"], "q": branch["q"], "r": branch["r"],
                  "G_ANOMALY": branch["G_ANOMALY"], "PRESENT": branch["PRESENT"]},
        "cells": {c: _cell_block(cells[c]) for c in CELLS},
        "D_block": dict(d, naive_M_difference=_naive_diff(arb["M"], rnd["M"]),
                        n_to_resolve_D_2sigma=n_to_reach(d["n_common"], d["z_D"]),
                        units="DECKS (a paired statistic; each deck is 2 games)"),
        "n_to_convict_z_arb_2sigma": n_to_reach(arb["n_paired"] or arb["n_decks_seat_balanced"],
                                                z_arb),
        "preconditions": pre, "precondition_detail": pre_detail,
        "cost_N4": cost,
        "phi_block": {
            "phi_arb": arb["phi"], "phi_rnd": rnd["phi"],
            "offline_prior": PHI_PRIOR,
            "funnel": {"exact_tie_rate_on_tile_plies_pct": PHI_FUNNEL_EXACT_TIE_PCT,
                       "deduped_scoreable_pct": PHI_FUNNEL_DEDUP_PCT},
            "design_2_1_mismatch_i": MISMATCH_I_VERBATIM,
            "design_2_1_mismatch_ii": MISMATCH_II_VERBATIM,
            "design_2_1_conclusion": MISMATCH_CONCLUSION_VERBATIM,
            "low_phi_note": ("DESIGN §3: a phi materially below the prior (say < 10) "
                             "shrinks the effect proportionally — the offline elo bound "
                             "is PER TIED PLY scaled by the rate, so a low phi makes a "
                             "null LESS informative, not more."),
        },
        "phase_a_cost_facts": {
            "c_tier1_rust_worker_s_per_playout": C_TIER1_RUST,
            "speedup_vs_pilot": C_TIER1_SPEEDUP_VS_PILOT,
            "rho_wall_16": RHO_WALL_16,
            "rho_amortized_16": RHO_AMORTIZED_16,
            "rho_phone_16": RHO_PHONE_16,
            "rho_phone_16_status": ("NOT SOLVED — the phone currency was never brought "
                                    "under 1.20 above B = 2; Phase A stamped it "
                                    "*reported, unadjudicated*. NO BRANCH LICENSES AN "
                                    "ON-DEVICE DEPLOY."),
            "source": "measurement/tiearb2_stage2_20260817/COST_REMEASURE.json",
        },
        "carried_verbatim": {
            "condition_b_design_12_1": CONDITION_B_VERBATIM,
            "condition_c_no_corroboration": CONDITION_C_VERBATIM,
        },
        "power": {"offline_elo": OFFLINE_ELO,
                  "offline_ci": [OFFLINE_ELO_LO, OFFLINE_ELO_HI],
                  "offline_low_bracket_div_5_23": OFFLINE_ELO_LOW_BRACKET,
                  "cell_1sigma_elo": POWER_1SIGMA_ELO,
                  "cell_2sigma_elo": POWER_2SIGMA_ELO,
                  "E_arb_95_upper": e_hi},
        "stage1b_carried": {"arb_H_pts_per_tied_ply": STAGE1B_ARB_H,
                            "z": STAGE1B_ARB_H_Z,
                            "note": "PUBLISHED and already adjudicated; NEVER a branch "
                                    "input here."},
        "band_registry": {"band_seed_start": BAND_EXPECTED,
                          "registry": "governance/BAND_REGISTRY.csv",
                          "claim": band_claim,
                          "deck_range_common": [d["deck_seed_min"], d["deck_seed_max"]]},
        "read_rule_amendment": READ_RULE_AMENDMENT,
        "read_rule_amendment_note": AMENDMENT_NOTE,
        "presentation_split_note": Z_PRESENT_BAR_NOTE,
        "what_no_branch_does": [
            "No branch edits governance/PRODUCTION.yaml. A pass licenses a "
            "production-flip DECISION for the owner and nothing more.",
            "No branch licenses an on-device / phone deploy (rho_phone(16) = 5.520).",
            "No branch adds a leaf term, changes the production leaf, or trains anything.",
            "No branch re-reads, re-labels or re-adjudicates Stage 1, Stage 1b or Phase A.",
            "No branch licenses a second game cell. This read-rule is SPENT when the "
            "read-out lands, on every branch.",
        ],
        "partial_run": {
            "planned_games_per_cell": CELL_GAMES_PLANNED,
            "realized_games": {c: cells[c]["n_games"] for c in CELLS},
            "realized_decks_seat_balanced": {c: cells[c]["n_decks_seat_balanced"]
                                             for c in CELLS},
            "n_common_decks": d["n_common_decks"],
            "note": ("Every statistic is at the REALIZED n. G-N still voids below the "
                     "committed thresholds — a partial run is read, then declared "
                     "U-UNREADABLE if it is short. Nothing is extrapolated."),
        },
    }
    if branch["branch"] == "G-FLAT":
        readout["g_flat_riders"] = {
            "scope_sentence": G_FLAT_SCOPE_SENTENCE,
            "offline_ci_excluded_at_95": bool(e_hi is not None and e_hi < OFFLINE_ELO_LO),
            "offline_ci_exclusion_rider": (
                "The 95% upper bound on E_arb is below +6.32 elo ⇒ the offline CI is "
                "EXCLUDED at 95% and the scope sentence is superseded IN THAT ONE "
                "RESPECT."
                if (e_hi is not None and e_hi < OFFLINE_ELO_LO) else
                "NOT APPLICABLE: the 95% upper bound on E_arb is not below +6.32 elo."),
            "tension_rider": G_FLAT_TENSION_RIDER,
        }
    # §4.2's downgrade — applied ONLY if §0.D's waiver is off. Under the ruling it
    # never fires, and the branch sentence is read at face value. This is a
    # PRESENTATION prefix either way: `branch` itself is untouched, always.
    if cost["cost_confounded"] and branch["branch"] != "U-UNREADABLE":
        readout["branch_headline"] = (
            "[COST-CONFOUNDED — ms_ratio > 1.20] " + readout["branch_headline"])
    assert readout["branch"] == branch["branch"], "the cost rider moved a branch"
    return readout


def _naive_diff(a, b):
    try:
        return a - b
    except TypeError:
        return None


def _elo_95_upper(cell: dict):
    e, s = cell.get("elo"), cell.get("elo_sig_1sigma")
    try:
        if e is None or s is None or s != s:
            return None
        return e + 1.96 * s
    except TypeError:
        return None


def _cell_block(c: dict) -> dict:
    return {k: c[k] for k in (
        "cell", "n_games", "n_records_on_disk", "n_decks_seat_balanced", "n_paired",
        "M", "z", "elo", "elo_sig_1sigma", "wr", "wr_z", "W", "D_draws", "L",
        "n_failed", "failure_rate", "champ_prefix_ms_per_move", "rung_ms_per_move",
        "ms_ratio", "phi", "seat_balance", "recomputed",
        "summary_path", "manifest_path")}


# --------------------------------------------------------------------------- #
def _f(x, spec="+.4f"):
    if x is None:
        return "ABSENT"
    try:
        if x != x:
            return "NaN"
        return format(x, spec)
    except (TypeError, ValueError):
        return str(x)


def render(v: dict) -> str:
    """READOUT.md — every item of the mandatory companion table §4.3, in order."""
    L = []
    a, r = v["cells"]["ARB"], v["cells"]["RND"]
    d = v["D_block"]
    L.append("# STAGE 2 — PHASE B READ-OUT: the deck-paired GAME cell")
    L.append("")
    L.append(f"> Adjudicates `{READ_RULE}` mechanically. "
             f"No owner call adjudicates any outcome.")
    L.append(">")
    L.append(f"> Text adjudicated: **{v['read_rule_amendment']}** — a PRE-RUN "
             "amendment, applied before the band claim and before game 1. "
             "**No adjudicating bar moved.**")
    L.append("")
    L.append(f"## BRANCH: `{v['branch']}`")
    L.append("")
    L.append(f"**{v['branch_headline']}**")
    L.append("")
    L.append(v["read"])
    L.append("")
    if v["failed_preconditions"]:
        L.append(f"**FAILED §3 PRECONDITIONS: {', '.join(v['failed_preconditions'])}** — "
                 "nothing closes, nothing is licensed, nothing is re-labelled.")
        L.append("")
    if v["failed_conjuncts"]:
        L.append("Failed conjuncts: " + "; ".join(v["failed_conjuncts"]))
        L.append("")
    if v.get("g_flat_riders"):
        g = v["g_flat_riders"]
        L.append("### Mandatory scope sentence (never separated from the verdict)")
        L.append("")
        L.append(f"> *\"{g['scope_sentence']}\"*")
        L.append("")
        L.append(f"**Offline-CI rider:** {g['offline_ci_exclusion_rider']}")
        L.append("")
        L.append(f"**Second rider (mandatory always on this branch):** {g['tension_rider']}")
        L.append("")

    # --- §4.3 (1) both cells ------------------------------------------------- #
    L.append("## §4.3 (1) — both cells")
    L.append("")
    L.append("| | ARB (argmax) | RND (random, wall-clock control) |")
    L.append("|---|---|---|")
    for label, key, spec in (("n games completed", "n_games", "d"),
                             ("decks seat-balanced", "n_decks_seat_balanced", "d"),
                             ("n_paired (summary)", "n_paired", "d"),
                             ("M (pts/game, paired)", "M", "+.4f"),
                             ("paired_z ⭐ PRIMARY", "z", "+.3f"),
                             ("elo", "elo", "+.2f"),
                             ("elo 1σ", "elo_sig_1sigma", ".2f"),
                             ("winrate", "wr", ".4f"),
                             ("winrate z", "wr_z", "+.2f"),
                             ("n_failed", "n_failed", "d"),
                             ("failure_rate", "failure_rate", ".5f")):
        L.append(f"| {label} | {_f(a.get(key), spec)} | {_f(r.get(key), spec)} |")
    L.append(f"| elo 95% CI | [{_f(_ci(a)[0], '+.2f')}, {_f(_ci(a)[1], '+.2f')}] | "
             f"[{_f(_ci(r)[0], '+.2f')}, {_f(_ci(r)[1], '+.2f')}] |")
    L.append(f"| seat balance (a_seat = CANDIDATE's seat) | {a['seat_balance']} | "
             f"{r['seat_balance']} |")
    L.append(f"| n_common (decks in BOTH cells) | {d['n_common_decks']} | "
             f"{d['n_common_decks']} |")
    L.append("")
    L.append("Witness (never a branch input) — our own recomputation of each cell's "
             f"paired z from the records: ARB {_f((a['recomputed'] or {}).get('z'), '+.3f')}, "
             f"RND {_f((r['recomputed'] or {}).get('z'), '+.3f')}. `z_arb`/`z_rnd` in the "
             "branch are READ off `summary.json::paired_z`, never recomputed.")
    L.append("")

    # --- §4.3 (2) D ---------------------------------------------------------- #
    L.append("## §4.3 (2) — `D`, its paired se, `z_D`, and the `n` that resolves it")
    L.append("")
    L.append(f"- **`D` = M_arb − M_rnd, deck-paired over n_common = "
             f"{d['n_common_decks']} decks: {_f(d['D'])} pts/game**")
    L.append(f"- paired se(`D`) = {_f(d['se_D'], '.4f')}")
    L.append(f"- **`z_D` = {_f(d['z_D'], '+.3f')}**  (same convention as "
             "`eval_fair_puct._paired_z`)")
    L.append(f"- M_arb / M_rnd restricted to the common decks: "
             f"{_f(d['M_arb_on_common'])} / {_f(d['M_rnd_on_common'])}; the naive "
             f"difference of the two summaries is {_f(d['naive_M_difference'])} "
             "(a diagnostic — the branch uses the DECK-PAIRED `D`)")
    L.append(f"- **the `n` that would resolve `D` to 2σ at the realized dispersion: "
             f"{d['n_to_resolve_D_2sigma'] if d['n_to_resolve_D_2sigma'] is not None else 'N/A (z_D absent, NaN or non-positive — more games do not resolve a wrong-signed effect)'}"
             f"** ({d['units']})")
    L.append(f"- **the `n` that would convict `z_arb` at 2σ: "
             f"{v['n_to_convict_z_arb_2sigma'] if v['n_to_convict_z_arb_2sigma'] is not None else 'N/A (z_arb absent, NaN or non-positive)'}** (decks)")
    L.append("")

    # --- §4.3 (3) phi -------------------------------------------------------- #
    ph = v["phi_block"]
    L.append("## §4.3 (3) — the firing rate `phi`, beside the offline prior")
    L.append("")
    L.append(f"- `phi_arb` = {_f(ph['phi_arb'], '.3f')} · `phi_rnd` = "
             f"{_f(ph['phi_rnd'], '.3f')} tied tile plies/game")
    L.append(f"- offline prior **{ph['offline_prior']}** (E4 census, n = 26); funnel: "
             f"{ph['funnel']['exact_tie_rate_on_tile_plies_pct']}% exact-tie rate on tile "
             f"plies, {ph['funnel']['deduped_scoreable_pct']}% deduped scoreable")
    L.append(f"- `G-FIRE` floor {PHI_FLOOR} (a precondition, the ONLY way phi touches a "
             "branch)")
    L.append("")
    L.append("**DESIGN §2.1's two runtime-vs-corpus mismatches, restated verbatim:**")
    L.append("")
    L.append("> " + ph["design_2_1_mismatch_i"].replace("\n", "\n> "))
    L.append("")
    L.append("> " + ph["design_2_1_mismatch_ii"].replace("\n", "\n> "))
    L.append("")
    L.append("> " + ph["design_2_1_conclusion"].replace("\n", "\n> "))
    L.append("")
    L.append(ph["low_phi_note"])
    L.append("")

    # --- §4.3 (4) ms_ratio --------------------------------------------------- #
    c = v["cost_N4"]
    L.append("## §4.3 (4) — `ms_ratio` for both cells, with the field-name trap named")
    L.append("")
    pvr = c["prediction_vs_realized"]
    L.append(f"- `ms_ratio_arb` = {_f(c['ms_ratio_arb'], '.4f')} · `ms_ratio_rnd` = "
             f"{_f(c['ms_ratio_rnd'], '.4f')} (bar {c['bar']})")
    # ⭐ a FIRST-CLASS line, not a footnote (§0.D): the cost model on trial.
    L.append(f"- ⭐ **PREDICTION vs REALIZED — DESIGN §5 predicted "
             f"≈ {pvr['predicted']} BEFORE the measurement; realized ARB "
             f"{_f(pvr['realized']['ARB'], '.4f')} (Δ {_f(pvr['delta']['ARB'], '+.4f')}), "
             f"RND {_f(pvr['realized']['RND'], '.4f')} "
             f"(Δ {_f(pvr['delta']['RND'], '+.4f')}).** {pvr['why']}")
    if c["cost_neutral"]:
        L.append(f"- **COST-NEUTRAL: both cells are ≤ {c['neutral_bar']}.**")
    if c["MEASUREMENT_DEFECT"]:
        L.append(f"- 🛑 **DEFECT — `ms_ratio` IS ABSENT for {c['ms_ratio_missing']}.** "
                 "§4.3(4) makes the measurement mandatory on every branch, and §0.D "
                 "waived the CONSEQUENCE, not the MEASUREMENT. This read-out is "
                 "incomplete until the cell reports its cost.")
    L.append(f"- **N4 FIRED: {c['N4_FIRED']}** — "
             + ("but the §4.2 DOWNGRADE IS WAIVED (§0.D); the against-champion reading "
                "stands AT FACE VALUE"
                if (c["N4_FIRED"] and c["downgrade_waived"]) else
                "the against-champion reading is DOWNGRADED TO COST-CONFOUNDED"
                if c["N4_FIRED"] else
                "the against-champion reading is not downgraded"))
    if c["downgrade_waived"]:
        L.append(f"- waiver authorised by **{c['n4_downgrade_waived_by']}** — owner, "
                 f"verbatim: *\"{c['owner_ruling_verbatim']}\"*")
    L.append(f"- ARB `champ_prefix_ms_per_move` (CANDIDATE) "
             f"{_f(a['champ_prefix_ms_per_move'], '.1f')} / `rung_ms_per_move` "
             f"(OPPONENT) {_f(a['rung_ms_per_move'], '.1f')}; RND "
             f"{_f(r['champ_prefix_ms_per_move'], '.1f')} / "
             f"{_f(r['rung_ms_per_move'], '.1f')}")
    L.append("")
    L.append(c["field_name_trap"])
    L.append("")
    L.append(c["rider"])
    if c["waiver_note"]:
        L.append("")
        L.append(c["waiver_note"])
    L.append("")

    # --- §4.3 (5) gates ------------------------------------------------------ #
    L.append("## §4.3 (5) — every §3 gate with its realized value")
    L.append("")
    L.append("| gate | PASS | realized |")
    L.append("|---|---|---|")
    for g in ALL_GATES:
        det = json.dumps(v["precondition_detail"].get(g), default=str)
        det = det.replace("|", "\\|")
        if len(det) > 600:
            det = det[:600] + "…"
        L.append(f"| `{g}` | {'PASS' if v['preconditions'].get(g) else '**FAIL**'} | {det} |")
    L.append("")
    j13 = v["precondition_detail"].get("G-J13", {})
    L.append("**J13 two-sided witness, per host** (the arbiter must CHANGE THE PICK at a "
             "constructed tied ply AND leave `root_leaf_value_bits` UNCHANGED):")
    L.append("")
    for host, blk in (j13.get("hosts") or {}).items():
        L.append(f"- `{host}`: pick_changed={blk.get('pick_changed')}, "
                 f"root_leaf_value_bits_unchanged="
                 f"{blk.get('root_leaf_value_bits_unchanged')}, "
                 f"all_preflight_pass={blk.get('all_preflight_pass')} "
                 f"({blk.get('path')})")
    if not (j13.get("hosts") or {}):
        L.append("- **NO PREFLIGHT WITNESS FOUND** — `G-J13` fails closed.")
    if j13.get("missing_hosts"):
        L.append(f"- **MISSING HOSTS: {j13['missing_hosts']}**")
    L.append("")

    # --- §4.3 (6) the verbatim carries --------------------------------------- #
    L.append("## §4.3 (6) — carried verbatim, on EVERY branch")
    L.append("")
    L.append("**Condition (b) — Stage 1b DESIGN §12.1:**")
    L.append("")
    L.append("> " + v["carried_verbatim"]["condition_b_design_12_1"].replace("\n", "\n> "))
    L.append("")
    L.append("**Condition (c) — arm `C`'s NO CORROBORATION sign-check verdict:**")
    L.append("")
    L.append("> " + v["carried_verbatim"]["condition_c_no_corroboration"].replace("\n", "\n> "))
    L.append("")

    # --- §4.3 (7) Phase-A cost ----------------------------------------------- #
    pa = v["phase_a_cost_facts"]
    L.append("## §4.3 (7) — the Phase-A cost facts that licensed this cell")
    L.append("")
    L.append(f"- `c_tier1_rust` = {pa['c_tier1_rust_worker_s_per_playout']} worker-s/playout, "
             f"{pa['speedup_vs_pilot']}× the pilot")
    L.append(f"- `rho_wall(16)` = {pa['rho_wall_16']} · `rho_amortized(16)` = "
             f"{pa['rho_amortized_16']}")
    L.append(f"- **`rho_phone(16)` = {pa['rho_phone_16']} — NOT SOLVED.** "
             f"{pa['rho_phone_16_status']}")
    L.append("")

    # --- §4.3 (8) band ------------------------------------------------------- #
    br = v["band_registry"]
    L.append("## §4.3 (8) — the realized band, the deck range, the registry claim")
    L.append("")
    L.append(f"- band `{br['band_seed_start']}` · common deck range "
             f"{br['deck_range_common']} · registry `{br['registry']}`")
    L.append(f"- claim artefact: `{json.dumps(br['claim'], default=str)[:500]}`")
    L.append("")

    # --- power + partial + what no branch does ------------------------------- #
    pw = v["power"]
    L.append("## Power, and what this cell can and cannot do (DESIGN §6)")
    L.append("")
    L.append(f"- n = 800 deck-paired ≈ ±{pw['cell_1sigma_elo']} elo (1σ), "
             f"±{pw['cell_2sigma_elo']} at 2σ")
    L.append(f"- offline bound chain: +{pw['offline_elo']} elo CI "
             f"[+{pw['offline_ci'][0]}, +{pw['offline_ci'][1]}], ÷5.23 low-end bracket "
             f"+{pw['offline_low_bracket_div_5_23']}")
    L.append(f"- realized 95% upper bound on `E_arb`: {_f(pw['E_arb_95_upper'], '+.2f')}")
    L.append(f"- Stage 1b carried (NEVER a branch input): `arb_H` = "
             f"+{v['stage1b_carried']['arb_H_pts_per_tied_ply']} pts/tied ply at z "
             f"+{v['stage1b_carried']['z']}")
    L.append("")
    L.append("## Partial-run status")
    L.append("")
    pr = v["partial_run"]
    L.append(f"- planned {pr['planned_games_per_cell']} games/cell; realized "
             f"{pr['realized_games']}; seat-balanced decks "
             f"{pr['realized_decks_seat_balanced']}; `n_common` "
             f"{pr['n_common_decks']} decks")
    L.append(f"- {pr['note']}")
    L.append("")
    L.append("## Which text was adjudicated")
    L.append("")
    L.append(f"- **{v['read_rule_amendment']}**")
    L.append(f"- {v['read_rule_amendment_note']}")
    L.append(f"- {v['presentation_split_note']}")
    L.append("")
    L.append("## What no branch does (READ_RULE §5)")
    L.append("")
    for line in v["what_no_branch_does"]:
        L.append(f"- {line}")
    L.append("")
    return "\n".join(L)


def _ci(cell: dict) -> tuple:
    e, s = cell.get("elo"), cell.get("elo_sig_1sigma")
    try:
        if e is None or s is None or s != s:
            return (None, None)
        return (e - 1.96 * s, e + 1.96 * s)
    except TypeError:
        return (None, None)


# --------------------------------------------------------------------------- #
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arb-summary", required=True, help="ARB cell summary.json")
    ap.add_argument("--arb-manifest", required=True, help="ARB cell manifest.json")
    ap.add_argument("--arb-records", default=None,
                    help="ARB per-game record dir (default: the summary's own dir)")
    ap.add_argument("--rnd-summary", required=True, help="RND cell summary.json")
    ap.add_argument("--rnd-manifest", required=True, help="RND cell manifest.json")
    ap.add_argument("--rnd-records", default=None,
                    help="RND per-game record dir (default: the summary's own dir)")
    ap.add_argument("--preflight", action="append", default=None,
                    help="repeatable; PREFLIGHT_*_${HOST}_FIRST.json, one per host")
    ap.add_argument("--expect-host", action="append", required=True,
                    help="repeatable; every host that played a game. REQUIRED — G-J13 is "
                         "per-host, so the roster cannot be inferred and is never assumed")
    ap.add_argument("--band-claim", default=str(RUN_DIR / "BAND_CLAIMED.json"))
    ap.add_argument("--out-dir", default=str(RUN_DIR))
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    v = build_readout(args)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "READOUT.json").write_text(json.dumps(v, indent=2, default=str) + "\n")
    md = render(v)
    (out / "READOUT.md").write_text(md + "\n")
    print(md)
    print(f"\n[wrote] {out / 'READOUT.json'}\n[wrote] {out / 'READOUT.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
