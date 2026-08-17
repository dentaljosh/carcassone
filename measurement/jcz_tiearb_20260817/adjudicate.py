#!/usr/bin/env python3
"""Adjudicate `measurement/jcz_tiearb_20260817/READ_RULE.md` — the OUT-OF-LINEAGE
pricing of the terminal-grounded tie arbiter through JCloisterZone.

⚠️ **BLIND ORDERING. This file is committed BEFORE game 1.** It adjudicates the
committed text and nothing else: it evaluates every §3 precondition, computes §1's
primary statistic, selects the FIRST §4 branch whose condition holds, and prints
§4.3's companion table on EVERY branch including `U-UNREADABLE`. There is no owner
call in here, no tuning knob, and no bar that is not quoted from the committed
documents.

    CELL A  `jcz_CHAMP_deploy11008`     the UNMODIFIED champion   vs JCZ
    CELL B  `jcz_ARB_B16J4_deploy11008` champion + tie arbiter    vs JCZ

    D     = M_B - M_A,  DECK-PAIRED over the decks common to BOTH cells (pts/game)
    se(D) = the paired standard error over n_common
    z_D   = D / se(D)     (convention: `eval_fair_puct._paired_z`, mirrored below)

`M_A` / `M_B` are each cell's per-deck seat-balanced margins — **exactly**
`scripts/jcz_match/analyze.py`'s `by_deck` construction, which this file IMPORTS
where it can and replicates verbatim only if the import fails (the replication is
flagged in the read-out; the deck pairing is never re-invented).

Usage
-----
    .venv/bin/python measurement/jcz_tiearb_20260817/adjudicate.py \
        --cell-a <cell_a.jsonl> --cell-b <cell_b.jsonl> [--json READOUT.json]

**Exit status is 0 on every branch, `U-UNREADABLE` included** — an unreadable run is
a valid pre-registered outcome, not a crash.

Three properties this file is deliberately built around
-------------------------------------------------------
* **Fail-closed. ABSENT IS FAIL.** Every gate that cannot SHOW its witness fails.
  A witness that resolves to `None` at every address it is looked up at is a FAIL,
  never a pass-by-omission.
* **Both manifest addresses, and REPORT which resolved** (READ_RULE §3, adopting the
  Stage-2 `G-J1`/`G-BAND` fix as shipped behaviour). A witness is read at the
  manifest TOP LEVEL first, then at `config.*`, then at the harness-native address
  where `scripts/jcz_match/match.py` actually writes it — and `resolved_at` names
  the address that answered. Absent at every address still fails; present-but-wrong
  still fails.
* **`G-TOOL` must not be unsatisfiable by construction** (READ_RULE §3.1). Stage 2
  lost an adjudication to a gate that fired on every healthy run
  (`measurement/tiearb2_stage2_20260817/READOUT.md`, the DISCLOSURE section). Here
  the commit-range conjunct is **dispositive in ONE direction only**: a NON-EMPTY or
  UNRESOLVED wheel-relevant diff VOIDS; an EMPTY diff or a degenerate range (the two
  commits are the same, which is what a healthy launcher produces because it
  generates the pre-flight AFTER the wheel build and BEFORE the detached launch)
  PASSES.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics as st
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_DEFAULT = HERE.parents[1]
SCHEMA = "carcassonne-jcz-tiearb-readout/v1"
DESIGN_DOC = "measurement/jcz_tiearb_20260817/DESIGN.md"
READ_RULE_DOC = "measurement/jcz_tiearb_20260817/READ_RULE.md"


# =========================================================================== #
# WORKERS.conf — the constants live in ONE place and are PARSED, not retyped.  #
# =========================================================================== #
#: Documented literals, used ONLY if WORKERS.conf cannot be parsed. When that
#: happens the read-out says so in as many words (`workers_conf.parsed = false`)
#: rather than silently adjudicating against a second copy of the constants.
WORKERS_CONF_FALLBACK = {
    "RUN_ID": "jcz_tiearb_20260817",
    "REPO_LOCAL": str(REPO_DEFAULT),
    "RUN_DIR": str(HERE),
    "CELL_A": "jcz_CHAMP_deploy11008",
    "CELL_B": "jcz_ARB_B16J4_deploy11008",
    "TIEARB_B": "16",
    "TIEARB_J": "4",
    "TIEARB_MODE": "argmax",
    "TIEARB_SALT": "tiearb2-deploy-v1",
    "TIEARB_EPS": "0.0",
    "CHAMP_LEAF_HASH": "a36d2e15a3b3d71d",
    "K_DETS": "8",
    "SIMS": "1376",
    "EXACT_K": "2",
    "DECKS": "400",
    "N_GAMES": "800",
    "BAND_SENTINEL": str(HERE / "BAND_CLAIM.txt"),
    "RULES_PROFILE": "fixed_v1",
    "FIX_R9": "1",
    "JCZ_REV": "29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a",
    "JCZ_JAR": "/home/doctor/jcz_spike/JCloisterZone/build/Engine.jar",
    "JCZ_JAR_SHA256": ("4dc5439dbf228b1360b0b1987f5e90454c4a6ac434a8509be4d2c08"
                       "9f9671190"),
    "JCZ_AI_CLASS": "com.jcloisterzone.ai.AiEngine",
    "JCZ_TILES": "basic:2",
    "RUST_TOOLCHAIN": "1.96.0",
}

_CONF_LINE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$")


def parse_workers_conf(path: Path) -> tuple[dict, dict]:
    """`(constants, meta)` from the `KEY=value` shell file.

    A deliberately small parser: it takes `KEY=value` lines, strips a trailing
    `# comment`, unquotes, and expands `$VAR` / `${VAR}` against the keys already
    parsed (`RUN_DIR="$REPO_LOCAL/measurement/$RUN_ID"` is the only shape that
    needs it). Anything else — functions, conditionals, command substitution — is
    ignored rather than guessed at.

    `meta` carries `parsed` and, on failure, `error`, so the read-out can state
    which copy of the constants it adjudicated against (READ_RULE §3 gates quote
    values; a silent fallback would mean a gate graded against a stale literal).
    """
    out: dict[str, str] = {}
    try:
        text = path.read_text()
    except OSError as e:                                             # noqa: BLE001
        return dict(WORKERS_CONF_FALLBACK), {
            "parsed": False, "path": str(path), "error": f"{type(e).__name__}: {e}",
            "note": ("WORKERS.conf could not be read — the DOCUMENTED LITERALS in "
                     "adjudicate.py::WORKERS_CONF_FALLBACK were used instead."),
        }
    for raw in text.splitlines():
        m = _CONF_LINE.match(raw)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith(("'", '"')):
            q = val[0]
            end = val.find(q, 1)
            val = val[1:end] if end > 0 else val[1:]
        else:
            val = val.split("#", 1)[0].strip()
        def _sub(mm, _o=out):
            return _o.get(mm.group(1) or mm.group(2), "")
        val = re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)", _sub, val)
        out[key] = val
    if not out:
        return dict(WORKERS_CONF_FALLBACK), {
            "parsed": False, "path": str(path), "error": "no KEY=value lines found",
            "note": ("WORKERS.conf parsed to nothing — the DOCUMENTED LITERALS in "
                     "adjudicate.py::WORKERS_CONF_FALLBACK were used instead."),
        }
    missing = [k for k in WORKERS_CONF_FALLBACK if k not in out]
    for k in missing:
        out[k] = WORKERS_CONF_FALLBACK[k]
    return out, {"parsed": True, "path": str(path),
                 "keys": len(out), "filled_from_fallback": missing}


# =========================================================================== #
# READ_RULE §3 / §4 committed bars. NOT new numbers — quoted, with their source. #
# =========================================================================== #
Z_CONFIRM = 2.0        # §4 `J-CONFIRMED`  / `J-REVERSED` (negative side)
Z_SIGN = 1.0           # §4 `J-SIGN` / `J-NULL-BOUNDED` / `J-INDETERMINATE`
PHI_FLOOR = 1.0        # §3 `G-FIRE` — fired tied tile plies per game, EFFECTIVE
N_COMMON_FLOOR = 320   # §3 `G-N` — DECKS common to both cells
CELL_GAMES_FLOOR = 640  # §3 `G-N` — scored games per cell
FINAL_AGREE_FLOOR = 0.99  # §3 `G-DIVERGE`
Z_WITNESS_TOL = 1e-9   # §1 — the recomputation is a WITNESS; this is the "beyond
                       #      floating-point tolerance" threshold (relative)

#: §3 `G-TOOL`'s committed path list, verbatim from the read-rule's own command:
#: `git diff --name-only <preflight_commit>..<manifest_commit> -- rust/ src/ engine/ scripts/`
WHEEL_RELEVANT_PATHS = ("rust/", "src/", "engine/", "scripts/")

ALL_GATES = ("G-BAND", "G-LEAF", "G-ARB", "G-FIRE", "G-J13", "G-RULES", "G-DIVERGE",
             "G-JCZ", "G-TOOL", "G-N", "G-PLY", "G-WITNESS")

#: DESIGN §4.1/§4.2 — the power arithmetic, committed before any number existed.
POWER = {
    "per_deck_paired_sd_assumed": 12.16,
    "se_per_cell_at_400_decks": 0.608,
    "se_D_assumed_rho_0": 0.860,
    "conviction_floor_D_at_2sigma": 1.72,
    "n_to_convict_D_1.00_at_2sigma_decks": 1183,
    "n_to_convict_D_1.50_at_2sigma_decks": 526,
    "source": "DESIGN.md §4.1-§4.3, committed 2026-08-17 before the band claim",
}

#: DESIGN §6.2 — the cost PREDICTION, printed against the realized value on every
#: branch (READ_RULE §0.D: that comparison is the only way a wrong cost model
#: becomes visible; it moves no bar).
COST_PREDICTION = {
    "cell_a_worker_s_per_game": 98.1,
    "arbiter_worker_s_per_fired_ply": 9.57,
    "phi_assumed": 17.6,
    "cell_b_worker_s_per_game": 266.0,
    "cell_b_over_cell_a": 2.71,
    "source": "DESIGN.md §6.2",
}

#: §4.3 item 7 — the 2026-08-09 reading of the champion against JCZ, and the
#: over-dispersion rider that CLAUDE.md attaches to a CROSS-BAND contrast.
READING_20260809 = {
    "elo": 111.4, "win_rate": 0.6550, "paired_margin": 6.50, "paired_margin_sem": 0.86,
    "n_decks": 200, "band": 1.08e11, "code_rev": "9c4bb50",
    "archive": "measurement/jcz_match_20260809/confirm.jsonl",
    "nominal_sigma_elo": 17.4,
    "overdispersion_lo": 1.8, "overdispersion_hi": 2.2,
}

#: §3 `G-ARB` — the ONE authorized rung. Any other rung VOIDS (READ_RULE §3,
#: WORKERS.conf, DESIGN §3). `eps` is compared as a float; everything else exactly.
ARB_RUNG_KEYS = ("enabled", "B", "J", "mode", "salt", "eps")

# =========================================================================== #
# VERBATIM CARRIES — copied character-for-character from the committed text.    #
# DO NOT paraphrase, shorten or re-wrap.                                       #
# =========================================================================== #

#: READ_RULE §0.B — the fail-soft dilution statement. §4.3 item 6 makes this
#: MANDATORY, verbatim, whenever CELL B's `tiearb_errors_total` > 0.
DILUTION_VERBATIM = (
    "**§0.B — the arbiter FAILS SOFT (from Stage-2 §0.E).** On a deep-playout error the "
    "arbiter falls\nback to the champion's own pick and counts it: the ply is "
    "un-arbitrated, not lost. Accepted,\nbecause propagating would kill the GAME and the "
    "exclusion would be **candidate-correlated** — a\nbiased exclusion is far worse than "
    "a diluted effect. **The bias runs toward the champion, so a\npositive read is "
    "UNDERSTATED.** Never a branch input EXCEPT through `G-FIRE`'s `phi_effective`.\n\n"
    "⚠️ **Here the fail-soft asymmetry is NOT symmetric across cells** — CELL A has no "
    "arbiter to fail.\nConsequence, stated now: fail-soft dilutes `D` **toward zero**. A "
    "positive `D` is therefore a\n**lower bound** on the mechanism's true delta, and a "
    "null is correspondingly weaker evidence of\nabsence. This is reported on every "
    "branch (§4.3 item 6)."
)

#: READ_RULE §0.C — the field-name trap, named wherever `ms_ratio` is printed,
#: together with the fields this harness actually read for each side.
FIELD_NAME_TRAP = (
    "⚠️ THE FIELD-NAME TRAP (READ_RULE §0.C): in `eval_fair_puct`, "
    "`champ_prefix_ms_per_move` is the CANDIDATE side, the opposite of "
    "`eval_puct_priors`. ⭐ IN **THIS** HARNESS (`scripts/jcz_match/`) THE FIELDS ARE "
    "`ms_per_move_champ` = OUR SIDE (the champion, ± the arbiter) and `ms_per_move_jcz` "
    "= JCZ, THE OPPONENT. `ms_ratio = ms_per_move_champ / ms_per_move_jcz` is "
    "ours-over-theirs. Do NOT import eval_fair_puct's inverted convention: a read-out "
    "that swaps them INVERTS the reading."
)

#: READ_RULE §0.A — the wall-clock waiver. Printed beside every cost figure.
CLOCK_WAIVER = (
    "READ_RULE §0.A (OWNER RULING, inherited from Stage-2 §0.D), verbatim: \"we can "
    "afford some wallclock during play, especially if its not every tile draw. dont let "
    "that be the constraint right now.\" ⇒ `ms_ratio` and every wall-clock quantity are "
    "MEASURED AND REPORTED on every branch and are NEVER a branch input. WAIVED: the "
    "consequence. NOT WAIVED: the measurement. ⛔ ANTI-GAMING (binding): permission to "
    "spend clock is never licence to reshape the arbiter to look cheaper — B stays 16 "
    "and may not be expanded, the tie predicate is not narrowed, and there is no playout "
    "truncation for cost reasons."
)

#: §4.3 item 8 — the two classified-benign divergence classes (DESIGN §2.1).
BENIGN_DIVERGENCE_CLASSES = ("WALL_LEGALITY", "UNPLACEABLE_REDRAW")
BENIGN_NOTE = (
    "`WALL_LEGALITY` (the bounded 25×25 action window running out before the 35×35 "
    "grid — it only ever ADDS options on JCZ's side, boards stay identical, and both "
    "affected 2026-08-09 games carried final_agree=True) and `UNPLACEABLE_REDRAW` (both "
    "engines discarded and redrew in lockstep; the divergent form "
    "`UNPLACEABLE_TURN_LOSS` fired 0 times) are the TWO CLASSIFIED-BENIGN classes, "
    "DESIGN §2.1. ⛔ ANY entry in a record's `real` ledger is a REAL divergence and "
    "VOIDS the run through `G-DIVERGE` — it is never re-classified here."
)

BRANCH_TEXT = {
    "J-CONFIRMED": (
        "⭐ THE ARBITER'S EDGE SURVIVES OUT OF LINEAGE.",
        "Terminal-grounded tie arbitration buys real points against an opponent that "
        "shares no leaf, no search, no engine and no rules implementation with us. The "
        "Stage-2 edge is NOT an artefact of playing our own lineage at its own blind "
        "spots. LICENSES exactly one thing: it is corroborating evidence the owner may "
        "weigh in the pending production-flip decision. ⛔ It does NOT flip "
        "PRODUCTION.yaml, does NOT license an on-device deploy (rho_phone 5.520 at "
        "B=16, unsolved), does NOT license a leaf term (CL-065 and the two dead menus "
        "stand), does NOT license a second cell or a larger B, and does NOT make "
        "anything superhuman (DESIGN §8.1)."),
    "J-SIGN": (
        "THE DIRECTION RESOLVES BUT NOT AT THE BAR.",
        "The delta points the same way as Stage 2 and this cell could not convict it. "
        "The honest deliverable is a SIGN, in the precedent of the OOF sign check. NOT "
        "a confirmation and it may not be quoted as one. It does not license a bigger-n "
        "follow-up by itself — DESIGN §4.3 already prices that at ~3× this cell's "
        "compute, unfunded."),
    "J-NULL-BOUNDED": (
        "NO EFFECT DETECTED, AND THE BOUND IS STATED.",
        "The arbiter's out-of-lineage delta is BOUNDED at |D| < 1.72 pts/game at 2σ "
        "(DESIGN §4.2) — that is ≈56% of the Stage-2 magnitude. ⚠️ THIS IS NOT A "
        "REFUTATION OF STAGE 2 AND MUST NEVER BE WRITTEN AS ONE. It is consistent with "
        "(a) a lineage-specific edge, (b) an edge attenuated below this cell's "
        "resolution, and (c) fail-soft dilution (§0.B), and this cell CANNOT separate "
        "them. It is a material negative datum for the flip decision and must be "
        "reported to the owner as prominently as a positive would be."),
    "J-REVERSED": (
        "THE DELTA CONVICTS NEGATIVE.",
        "The arbiter COSTS points out of lineage at 2σ. This is a STRONG NEGATIVE for "
        "the flip and is reported as the headline. It also makes the Stage-2 result a "
        "lineage-specific effect by direct evidence, which is a finding in its own right "
        "and goes in LEVER_INDEX as such."),
    "J-INDETERMINATE": (
        "NEGATIVE-LEANING, UNRESOLVED.",
        "Reported as such. Licenses nothing."),
    "U-UNREADABLE": (
        "UNREADABLE — a §3 precondition failed.",
        "No strength statistic from this run is adjudicated, quoted, or entered in "
        "results.csv as a verdict. The failed gate is named with its realized value. "
        "U-UNREADABLE is a FULLY ACCEPTABLE OUTCOME. ⚠️ §4.3's companion table is still "
        "printed in full below — which makes the session that reads it NON-BLIND, so per "
        "READ_RULE §4 any instrument fix must be written by a session that has NOT seen "
        "the strength statistics and must be decidable from gate inputs alone. Bars do "
        "not move. §4 is not edited."),
}

NO_BRANCH_MATCHED = (
    "no §4 branch condition held — z_D fell in a region §4 does not name (or is "
    "absent/NaN). §4 is NOT edited to cover it: the read-out fires U-UNREADABLE, which "
    "is the committed catch-all for 'this run is not adjudicable', and names the reason."
)


# =========================================================================== #
# §1 — the paired statistic. ONE convention, mirrored from                     #
# `eval_fair_puct._paired_z` (live at line 2299).                              #
# =========================================================================== #
def paired_stats(values) -> tuple:
    """`(mean, se, z, n)` — `_paired_z`'s arithmetic, verbatim:

        mean = sum(ds) / len(ds)
        var  = sum((d - mean)**2) / (len(ds) - 1)     # ddof = 1
        se   = sqrt(var / len(ds))
        z    = mean / se   if se > 0   else NaN

    and `(None, None, None, n)` below two values, matching `_paired_z`'s
    `(None, None, 0)` early return. There is exactly ONE convention in this file.
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


def per_deck_balanced(records) -> dict:
    """`{deck_seed: paired observation}` — **exactly** `scripts/jcz_match/analyze.py`'s
    `by_deck` construction (lines 69-74), kept per-deck instead of collapsed to a
    list so `D` can be taken deck-wise.

        by_deck[deck_seed][champ_seat].append(margin_champ_minus_jcz)
        paired  = mean over the two seatings of (mean over that seating's records)

    A deck with only ONE seating is DROPPED — it is not seat-balanced, and that is
    what makes a partial run readable at its realized `n`. `analyze()`'s own
    `paired_margin_mean` / `n_paired_decks` are recomputed from this dict and
    cross-checked against the analyzer's, so a divergence in the pairing rule is
    caught rather than assumed away.
    """
    by_deck: dict[int, dict[int, list[int]]] = {}
    for r in records:
        by_deck.setdefault(int(r["deck_seed"]), {}).setdefault(
            int(r["champ_seat"]), []).append(int(r["margin_champ_minus_jcz"]))
    return {d: st.mean([st.mean(v) for v in seats.values()])
            for d, seats in by_deck.items() if len(seats) == 2}


def deck_paired_D(a_by_deck: dict, b_by_deck: dict) -> dict:
    """§1's `D` — `M_B − M_A`, DECK-PAIRED over the decks common to BOTH cells.

    The per-deck DIFFERENCE is taken first and averaged second (that is what
    deck-paired means, and it is why the deck draw cancels twice over). Also
    returns each cell's mean restricted to the common decks, so a reader can see
    that `D` is their difference and not a rescaling.
    """
    common = sorted(set(a_by_deck) & set(b_by_deck))
    diffs = [b_by_deck[s] - a_by_deck[s] for s in common]
    D, se, z, n = paired_stats(diffs)
    return {"D": D, "se_D": se, "z_D": z, "n_common": n,
            "n_common_decks": len(common),
            "M_A_on_common": (sum(a_by_deck[s] for s in common) / len(common)
                              if common else None),
            "M_B_on_common": (sum(b_by_deck[s] for s in common) / len(common)
                              if common else None),
            "deck_seed_min": common[0] if common else None,
            "deck_seed_max": common[-1] if common else None,
            "units": "DECKS (§2: a paired statistic; each deck is 2 games)"}


def recompute_z_D_witness(a_records, b_records) -> dict:
    """§1's INDEPENDENT recomputation of `z_D`. **A WITNESS, NEVER A BRANCH INPUT.**

    Deliberately a different code path from `per_deck_balanced` + `deck_paired_D`:
    single-pass `(deck, seat)` sum/count accumulation instead of a dict of lists,
    `math.fsum` instead of `sum`, and the variance taken over an explicitly
    materialised difference list. It answers the same arithmetic question; if the
    two answers disagree beyond floating-point tolerance, §1 says the run is
    `U-UNREADABLE` (implemented as gate `G-WITNESS`).
    """
    def cell(records):
        acc: dict[tuple, list] = {}
        for r in records:
            k = (int(r["deck_seed"]), int(r["champ_seat"]))
            s, c = acc.get(k, (0.0, 0))
            acc[k] = (s + float(r["margin_champ_minus_jcz"]), c + 1)
        seats: dict[int, dict[int, float]] = {}
        for (deck, seat), (s, c) in acc.items():
            seats.setdefault(deck, {})[seat] = s / c
        return {d: math.fsum(v.values()) / 2.0 for d, v in seats.items()
                if len(v) == 2}

    A, B = cell(a_records), cell(b_records)
    common = sorted(set(A) & set(B))
    diffs = [B[d] - A[d] for d in common]
    n = len(diffs)
    if n < 2:
        return {"D": None, "se_D": None, "z_D": None, "n_common": n}
    mean = math.fsum(diffs) / n
    var = math.fsum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    return {"D": mean, "se_D": se, "z_D": (mean / se if se > 0 else float("nan")),
            "n_common": n}


def _close(a, b, tol=Z_WITNESS_TOL) -> bool:
    """Float agreement for the §1 witness. Two `None`s agree; two NaNs agree (both
    say 'no dispersion'); a `None` against a number does NOT."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        if a != a and b != b:                                    # both NaN
            return True
        if a != a or b != b:
            return False
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    except TypeError:
        return False


def n_to_reach(n, z, target=Z_CONFIRM):
    """The `n` (in DECKS) that would carry `|z|` to `target` at the REALIZED
    dispersion: `n_needed = n * (target/|z|)**2`, because `z` scales as `sqrt(n)`.

    ⚠️ DEVIATION FROM `analyze_tiearb2_stage2.n_to_reach`, stated rather than
    smuggled: that one returns `None` for `z <= 0`, because there the question was
    "what would CONVICT the candidate". READ_RULE §4.3 item 2 asks for "the `n` that
    would RESOLVE `D` to 2σ", and a negative `D` is resolved by `J-REVERSED` at
    `z_D <= -2.0` — so `|z|` is used and the sign is reported alongside. `None` when
    `z` is absent, NaN or exactly zero (a zero effect is not resolved by more games,
    and this must never print a finite promise).
    """
    try:
        if not n or z is None or z != z or z == 0:
            return None
    except TypeError:
        return None
    return int(math.ceil(n * (target / abs(z)) ** 2))


# =========================================================================== #
# Manifest / record witness resolution — BOTH levels, and REPORT which resolved. #
# =========================================================================== #
def _get_path(obj, dotted: str):
    """`(value, found)` for a dotted address inside nested dicts."""
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None, False
        cur = cur[part]
    return cur, True


def resolve_witness(records, key: str = None, extra: tuple = (),
                    addresses: tuple = None) -> dict:
    """Resolve a manifest witness across a cell's records, at EVERY committed
    address, and report which one answered.

    Address order (READ_RULE §3, the Stage-2 `G-J1`/`G-BAND` fix adopted as shipped
    behaviour): manifest TOP LEVEL → `config.<key>` → the harness-native addresses
    passed in `extra` (where `scripts/jcz_match/match.py` actually writes the field:
    e.g. the leaf hash lives at `champion_manifest.leaf_hashes.harness_leaf_hash`).
    Pass `addresses=` instead of `key=` for a witness that has no top-level spelling
    at all. The two manifest levels are split by HOW a key was written, not by what
    it means, so reading one level only asks a plumbing question. **ABSENT AT EVERY
    ADDRESS STILL FAILS** — that is what keeps this a lookup, not a softened gate.

    Returns `{"value", "resolved_at", "distinct", "consistent", "n_records",
    "n_resolved"}`. `distinct` lists every `(value, address)` pair seen across the
    cell's records: a cell whose records disagree is NOT consistent, which is how a
    mixed-rev cell is caught instead of being represented by record 0.
    """
    if addresses is None:
        addresses = (key, f"config.{key}") + tuple(extra)
    seen: Counter = Counter()
    n_resolved = 0
    for r in records:
        m = r.get("manifest") or {}
        for addr in addresses:
            v, found = _get_path(m, addr)
            if found and v is not None:
                seen[(json.dumps(v, sort_keys=True, default=str), addr)] += 1
                n_resolved += 1
                break
    distinct = [{"value": json.loads(v), "resolved_at": a, "n_records": c}
                for (v, a), c in sorted(seen.items(), key=lambda kv: -kv[1])]
    value = distinct[0]["value"] if distinct else None
    return {"value": value,
            "resolved_at": distinct[0]["resolved_at"] if distinct else None,
            "distinct": distinct,
            "consistent": len(distinct) == 1 and n_resolved == len(records),
            "n_records": len(records), "n_resolved": n_resolved,
            "addresses_tried": list(addresses)}


def _find_key_anywhere(obj, key: str, path="", skip=("moves", "actions", "replay"),
                       out=None, depth=0):
    """Every address at which `key` appears in a nested structure. Used ONLY by
    `G-ARB`'s "CELL A carries NO `champ_tiearb` key" clause, which is a
    PRESENCE question and therefore has to look everywhere, not at a fixed list.
    The per-ply blobs are skipped: they are large and carry no manifest witness."""
    if out is None:
        out = []
    if depth > 8 or not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        if k in skip:
            continue
        p = f"{path}.{k}" if path else k
        if k == key:
            out.append(p)
        _find_key_anywhere(v, key, p, skip, out, depth + 1)
    return out


# =========================================================================== #
# Loading — reuse `scripts/jcz_match/analyze.py`, never re-invent its pairing.  #
# =========================================================================== #
def _import_jcz_analyze(repo: Path):
    """`(module_or_None, provenance)`. The analyzer is IMPORTED when importable so
    the deck pairing is literally the same code; the replication below is a
    fallback that is FLAGGED in the read-out, never a silent second copy."""
    d = str(repo / "scripts" / "jcz_match")
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        import analyze as mod                                       # noqa: PLC0415
        if hasattr(mod, "analyze") and hasattr(mod, "load"):
            return mod, {"imported": True, "from": str(Path(d) / "analyze.py")}
        return None, {"imported": False, "from": str(Path(d) / "analyze.py"),
                      "error": "module lacks analyze()/load()"}
    except Exception as e:                                           # noqa: BLE001
        return None, {"imported": False, "from": str(Path(d) / "analyze.py"),
                      "error": f"{type(e).__name__}: {e}"}


def _fallback_wr_to_elo(wr):
    if wr is None or wr <= 0.0 or wr >= 1.0:
        return None
    return -400.0 * math.log10(1.0 / wr - 1.0)


def _fallback_load(path: Path) -> list[dict]:
    out = []
    try:
        text = path.read_text()
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:            # a torn last line from a dirty crash
            continue
    return out


def _fallback_analyze(records: list[dict]) -> dict:
    """`scripts/jcz_match/analyze.py::analyze`, replicated VERBATIM (its lines
    58-123) for the case where the import fails. The deck pairing is
    character-for-character the same construction; nothing here is a variant."""
    scored = [r for r in records if not r.get("void") and r.get("winner")]
    voids = Counter(r["void"] for r in records if r.get("void"))
    wins = sum(1 for r in scored if r["winner"] == "champ")
    draws = sum(1 for r in scored if r["winner"] == "draw")
    losses = sum(1 for r in scored if r["winner"] == "jcz")
    n = len(scored)
    wr = (wins + 0.5 * draws) / n if n else None
    by_deck: dict = {}
    for r in scored:
        by_deck.setdefault(int(r["deck_seed"]), {}).setdefault(
            int(r["champ_seat"]), []).append(int(r["margin_champ_minus_jcz"]))
    paired = [st.mean([st.mean(v) for v in seats.values()])
              for seats in by_deck.values() if len(seats) == 2]
    half_pairs = [d for d, seats in by_deck.items() if len(seats) != 2]
    p_mean = st.mean(paired) if paired else None
    p_sem = st.stdev(paired) / math.sqrt(len(paired)) if len(paired) > 1 else None
    p_z = (p_mean / p_sem) if (p_mean is not None and p_sem) else None
    margins = [r["margin_champ_minus_jcz"] for r in scored]
    counts: Counter = Counter()
    real: Counter = Counter()
    for r in records:
        counts.update(r.get("counts") or {})
        real.update(r.get("real") or {})
    per_seat = {}
    for cs in (0, 1):
        rs = [r for r in scored if int(r["champ_seat"]) == cs]
        if not rs:
            continue
        per_seat[cs] = {"n": len(rs),
                        "wins": sum(1 for r in rs if r["winner"] == "champ"),
                        "draws": sum(1 for r in rs if r["winner"] == "draw"),
                        "mean_margin": st.mean(r["margin_champ_minus_jcz"] for r in rs)}

    def _m(key):
        vals = [r[key] for r in records if r.get(key) is not None]
        return st.mean(vals) if vals else None

    return {"n_records": len(records), "n_scored": n, "voids": dict(voids),
            "wins": wins, "draws": draws, "losses": losses, "win_rate": wr,
            "elo_unpaired": _fallback_wr_to_elo(wr) if wr is not None else None,
            "elo_sigma_1s": 695.0 * math.sqrt(0.25 / n) if n else None,
            "n_paired_decks": len(paired), "half_pair_decks": half_pairs,
            "paired_margin_mean": p_mean, "paired_margin_sem": p_sem,
            "paired_margin_z": p_z,
            "unpaired_margin_mean": st.mean(margins) if margins else None,
            "unpaired_margin_sd": st.stdev(margins) if len(margins) > 1 else None,
            "per_seat": per_seat, "divergence_counts": dict(counts),
            "divergence_real": dict(real),
            "final_agree_all": all(r.get("final_agree") for r in scored),
            "replay_ok_all": all(r.get("replay_ok") for r in scored),
            "ms_per_move_champ": _m("ms_per_move_champ"),
            "ms_per_move_jcz": _m("ms_per_move_jcz"),
            "wall_secs_per_game": _m("wall_secs")}


def load_cell(path: Path, mod) -> dict:
    """`{records, scored, summary, ...}` for one cell."""
    if mod is not None:
        records = mod.load(path) if path.exists() else []
        summary = mod.analyze(records) if records else _fallback_analyze([])
    else:
        records = _fallback_load(path)
        summary = _fallback_analyze(records)
    scored = [r for r in records if not r.get("void") and r.get("winner")]
    return {"path": str(path), "exists": path.exists(), "records": records,
            "scored": scored, "summary": summary,
            "by_deck": per_deck_balanced(scored),
            "deck_seeds": sorted({int(r["deck_seed"]) for r in scored}),
            "seat_balance": dict(Counter(int(r["champ_seat"]) for r in scored))}


# =========================================================================== #
# CELL B's arbiter telemetry (`champ_tiearb`), aggregated.                      #
# =========================================================================== #
_TELEM_SUM = ("tile_plies", "fired_plies", "fires", "pickchanges", "arms_total",
              "playouts_total", "secs", "errors", "partial_argmax")


def telemetry(records) -> dict:
    """Aggregate the per-game `champ_tiearb` block over a cell's SCORED records.

    Fail-closed on absence: a field that is missing on ANY telemetry-carrying record
    aggregates to `None` (UNKNOWN, not zero), and `None` fails `G-FIRE` /`G-PLY`
    exactly as an absent witness must.
    """
    blocks = [r.get("champ_tiearb") for r in records
              if isinstance(r.get("champ_tiearb"), dict)]
    out: dict = {"n_games": len(records), "n_games_with_telemetry": len(blocks),
                 "telemetry_on_every_game": bool(records) and len(blocks) == len(records)}
    for key in _TELEM_SUM:
        vals = [b.get(key) for b in blocks]
        out[f"{key}_total"] = (sum(float(v) for v in vals)
                               if blocks and all(isinstance(v, (int, float))
                                                 and not isinstance(v, bool)
                                                 for v in vals) else None)
    out["max_plies"] = sorted({b.get("max_plies") for b in blocks}, key=str) or None
    out["mode"] = sorted({b.get("mode") for b in blocks}, key=str) or None
    out["B"] = sorted({b.get("B") for b in blocks}, key=str) or None
    out["J"] = sorted({b.get("J") for b in blocks}, key=str) or None
    first_errors = [b.get("first_error") for b in blocks if b.get("first_error")]
    out["first_error"] = first_errors[0] if first_errors else None
    out["n_games_with_error"] = sum(
        1 for b in blocks if isinstance(b.get("errors"), (int, float))
        and not isinstance(b.get("errors"), bool) and b["errors"] > 0)
    fired = out.get("fired_plies_total")
    if fired is None:
        fired = out.get("fires_total")
        out["fired_source"] = "fires" if fired is not None else None
    else:
        out["fired_source"] = "fired_plies"
    out["fired_plies_used"] = fired
    games = len(records)
    out["phi"] = (fired / games) if (fired is not None and games) else None
    err = out.get("errors_total")
    if err is None or fired is None:
        out["error_rate_on_fired"] = None
    elif fired == 0:
        out["error_rate_on_fired"] = 0.0
    else:
        out["error_rate_on_fired"] = err / fired
    out["phi_effective"] = (
        out["phi"] * (1.0 - out["error_rate_on_fired"])
        if out["phi"] is not None and out["error_rate_on_fired"] is not None else None)
    return out


# =========================================================================== #
# §3 — THE PRECONDITIONS. Each is a pure function so a test can fail exactly    #
# one at a time. Each returns `(PASS, realized)`. FAIL-CLOSED: ABSENT IS FAIL.  #
# =========================================================================== #
def _ge(x, bar) -> bool:
    """NaN-safe `>=`. `None` and NaN are FAILURES, never comparisons."""
    try:
        return x is not None and x == x and float(x) >= bar
    except (TypeError, ValueError):
        return False


def load_band_claim(path: Path) -> dict:
    """The band sentinel (`WORKERS.conf::BAND_SENTINEL`, memoized by
    `claim_next_band.py` immediately before game 1).

    Accepts the house's two shapes: a JSON object carrying `band` (+ optional
    `claimed_at` epoch), or the plain-text sentinel whose FIRST line is the band
    (that is what Stage 2 wrote). The sentinel TIMESTAMP is `claimed_at` when the
    file carries one, else the file's mtime — the only mechanical witness available
    for "claimed BEFORE game 1", which is checked against the EARLIEST `finished_at`
    across both cells.
    """
    out = {"path": str(path), "exists": path.exists(), "band": None,
           "claimed_at": None, "claimed_at_source": None, "raw": None}
    if not path.exists():
        out["error"] = "band sentinel ABSENT — G-BAND cannot be shown and fails closed"
        return out
    text = path.read_text()
    out["raw"] = text[:400]
    try:
        doc = json.loads(text)
        if isinstance(doc, dict):
            out["band"] = doc.get("band")
            if isinstance(doc.get("claimed_at"), (int, float)):
                out["claimed_at"] = float(doc["claimed_at"])
                out["claimed_at_source"] = "claimed_at field"
    except json.JSONDecodeError:
        pass
    if out["band"] is None:
        m = re.search(r"\d{6,}", text.splitlines()[0] if text.splitlines() else "")
        out["band"] = int(m.group(0)) if m else None
    if out["claimed_at"] is None:
        try:
            out["claimed_at"] = os.path.getmtime(path)
            out["claimed_at_source"] = "file mtime"
        except OSError:
            pass
    if out["band"] is None:
        out["error"] = "sentinel carried no parseable band"
    return out


def gate_band(cells: dict, claim: dict, decks_per_cell: int) -> tuple:
    """`G-BAND` — "both cells carry the SAME band; band was claimed BEFORE game 1
    (sentinel timestamp precedes the first record); record-derived deck sets agree
    with the declared band".

    Three binding propositions, exactly as worded:

    1. **Same band.** Each cell's record-derived band — its lowest `deck_seed`
       floored to the registry's 1e9 allocation step (`claim_next_band.STEP`),
       computed WITHOUT reference to the sentinel — is equal across the two cells
       and equal to the declared band.
    2. **Claimed before game 1.** The sentinel timestamp strictly precedes the
       earliest `finished_at` in either cell. An absent sentinel, an absent band, or
       an absent timestamp FAILS (absent is fail).
    3. **Deck sets agree with the declared band.** Every scored record's `deck_seed`
       lies in `[band, band + DECKS - 1]`, in BOTH cells.

    A manifest band witness (`band_seed_start` / `seed_start` / `band`) is READ and
    REPORTED with its resolving address, and binds only when it is PRESENT and
    DIFFERENT from the declared band. ⚠️ AMBIGUITY, DECLARED: the committed sentence
    names the SENTINEL and the RECORD-DERIVED deck sets as the witnesses, not a
    manifest field, and `scripts/jcz_match/match.py` writes no band field at all
    (checked against the 2026-08-09 archive), so requiring one would be a gate that
    fails on every healthy run — the exact §3.1 defect class. Present-but-wrong
    still fails.
    """
    band = claim.get("band")
    per_cell = {}
    ok_range = True
    derived = []
    for name, c in cells.items():
        seeds = c["deck_seeds"]
        in_range = (band is not None and bool(seeds)
                    and all(band <= s <= band + decks_per_cell - 1 for s in seeds))
        # the registry allocates step-aligned bands (claim_next_band.STEP = 1e9), so
        # the band a cell's records were actually drawn from is its lowest seed
        # floored to that step — computed WITHOUT reference to the sentinel, which is
        # what makes "the two cells carry the SAME band" an independent proposition.
        band_of_records = (seeds[0] // 1_000_000_000) * 1_000_000_000 if seeds else None
        derived.append(band_of_records)
        per_cell[name] = {
            "n_decks": len(seeds),
            "deck_seed_min": seeds[0] if seeds else None,
            "deck_seed_max": seeds[-1] if seeds else None,
            "band_derived_from_records": band_of_records,
            "all_within_declared_band": in_range,
            "n_outside": (sum(1 for s in seeds
                              if not (band <= s <= band + decks_per_cell - 1))
                          if band is not None else None)}
        ok_range &= bool(in_range)
    same_band = (len(set(derived)) == 1 and derived[0] is not None
                 and band is not None and derived[0] == band)

    finished = [r.get("finished_at") for c in cells.values() for r in c["records"]
                if isinstance(r.get("finished_at"), (int, float))]
    first_record_at = min(finished) if finished else None
    claimed_at = claim.get("claimed_at")
    before = (claimed_at is not None and first_record_at is not None
              and claimed_at < first_record_at)

    manifest_band = {}
    manifest_ok = True
    for name, c in cells.items():
        w = None
        for key in ("band_seed_start", "seed_start", "band"):
            w = resolve_witness(c["records"], key)
            if w["value"] is not None:
                w["key"] = key
                break
        manifest_band[name] = ({"key": w.get("key"), "value": w["value"],
                                "resolved_at": w["resolved_at"]}
                               if w and w["value"] is not None
                               else {"value": None, "resolved_at": None,
                                     "note": "absent at every address — REPORTED, "
                                             "not binding (see docstring)"})
        v = manifest_band[name]["value"]
        if v is not None and band is not None and int(v) != int(band):
            manifest_ok = False

    ok = bool(band is not None and same_band and before and ok_range and manifest_ok)
    return ok, {"declared_band": band, "band_claim": claim,
                "claimed_before_game_1": before, "sentinel_timestamp": claimed_at,
                "sentinel_timestamp_source": claim.get("claimed_at_source"),
                "earliest_finished_at": first_record_at,
                "decks_per_cell_declared": decks_per_cell,
                "per_cell": per_cell, "same_band_across_cells": same_band,
                "record_deck_sets_agree_with_band": ok_range,
                "manifest_band_witness": manifest_band,
                "manifest_band_agrees_where_present": manifest_ok}


def gate_leaf(cells: dict, expected: str) -> tuple:
    """`G-LEAF` — `cand_leaf_hash == a36d2e15a3b3d71d` on BOTH cells. VOIDS on
    "difference or absence".

    ⚠️ AMBIGUITY, DECLARED: READ_RULE names the witness `cand_leaf_hash`, which is
    `eval_fair_puct`'s spelling. `scripts/jcz_match/match.py` stamps the same
    quantity at `champion_manifest.leaf_hashes.harness_leaf_hash` (verified against
    the 2026-08-09 archive). Both spellings are looked up, top level then `config.*`
    then the harness-native address, and `resolved_at` says which answered. Reading
    only `cand_leaf_hash` would be a gate that fails on every healthy run of THIS
    harness (§3.1's defect class); reading the harness address is implementing the
    committed sentence, not relaxing it. ABSENT AT EVERY ADDRESS STILL FAILS.
    """
    obs, ok = {}, True
    for name, c in cells.items():
        w = resolve_witness(c["records"], "cand_leaf_hash",
                            extra=("champion_manifest.leaf_hashes.harness_leaf_hash",
                                   "champion_manifest.leaf_hash",
                                   "leaf_hashes.harness_leaf_hash"))
        good = (w["value"] == expected) and w["consistent"]
        obs[name] = {"cand_leaf_hash": w["value"], "resolved_at": w["resolved_at"],
                     "consistent_across_records": w["consistent"],
                     "distinct": w["distinct"], "ok": good}
        ok &= good
    return bool(ok), {"expected_equal": expected, "observed": obs,
                      "semantics": "EQUALITY gate — difference OR absence VOIDS; the "
                                   "hash must also be consistent across every record "
                                   "of the cell (a mixed-rev cell fails)"}


def _arb_dicts(records, key="champ_tiearb") -> list:
    """Every `champ_tiearb`-shaped dict a cell exposes, with its address: the
    manifest at both levels, the harness-native champion-manifest addresses, and —
    LAST — the per-game telemetry block, which carries `mode`/`B`/`J`."""
    manifest_addresses = (key, f"config.{key}", f"champion_manifest.{key}",
                          "champion_manifest.tiearb", "tiearb")
    found, seen = [], set()
    for r in records:
        m = r.get("manifest") or {}
        probes = [(a, m, a) for a in manifest_addresses]
        probes.append((f"record.{key}", r, key))       # the per-game telemetry block
        for label, root, path in probes:
            v, hit = _get_path(root, path)
            if not (hit and isinstance(v, dict)):
                continue
            # the per-game telemetry block carries live COUNTERS as well as the rung,
            # so it is deduped on its rung projection — otherwise every game would
            # look like a distinct address.
            proj = {k: v[k] for k in ARB_RUNG_KEYS if k in v}
            value = proj if label.startswith("record.") else v
            sig = (label, json.dumps(proj, sort_keys=True, default=str))
            if sig not in seen:
                seen.add(sig)
                found.append({"resolved_at": label, "value": value})
    return found


def gate_arb(cells: dict, a_name: str, b_name: str, rung: dict) -> tuple:
    """`G-ARB` — "CELL B resolves `champ_tiearb` == {enabled, B:16, J:4,
    mode:'argmax', salt:'tiearb2-deploy-v1', eps:0.0} AND CELL A carries NO
    `champ_tiearb` key". VOIDS on "any other rung; a key present on CELL A".

    CELL B: every `champ_tiearb`-shaped dict the cell exposes (manifest top level,
    `config.*`, the champion-manifest addresses, and the per-game telemetry block)
    is MERGED into one resolved view, with each field's resolving address reported.
    ⚠️ AMBIGUITY, DECLARED: the knob (`enabled`/`salt`/`eps`) and the telemetry
    (`mode`/`B`/`J` + counters) are written by different code paths, so requiring
    all six fields at ONE address would risk a gate no healthy run can satisfy. The
    merge is fail-closed in both directions: a field missing from EVERY address
    fails, and two addresses that DISAGREE on a field fail (`conflicts`).

    CELL A: a recursive search for the key `champ_tiearb` anywhere in the record or
    its manifest. **Any presence fails**, verbatim — including a disabled stamp,
    because DESIGN §6.1's enabling change promises a BYTE-IDENTICAL manifest when
    the arbiter is absent, so a key on CELL A means CELL A is not the champion the
    2026-08-09 run played. Sightings of the neighbouring spellings (`cand_tiearb`,
    `tiearb_enabled`) are REPORTED and do not bind — the committed sentence names
    `champ_tiearb`.
    """
    b_found = _arb_dicts(cells[b_name]["records"])
    merged, where, conflicts = {}, {}, []
    for f in b_found:
        for k, v in f["value"].items():
            if k not in ARB_RUNG_KEYS:
                continue
            if k in merged and merged[k] != v:
                conflicts.append({"field": k, "a": merged[k], "b": v,
                                  "addresses": [where[k], f["resolved_at"]]})
            else:
                merged[k], where[k] = v, f["resolved_at"]
    checks = {}
    for k in ARB_RUNG_KEYS:
        want = rung[k]
        got = merged.get(k)
        if k == "eps":
            good = isinstance(got, (int, float)) and abs(float(got) - float(want)) < 1e-12
        elif k == "enabled":
            good = got is True
        elif k in ("B", "J"):
            good = isinstance(got, (int, float)) and int(got) == int(want)
        else:
            good = got == want
        checks[k] = {"expected": want, "observed": got,
                     "resolved_at": where.get(k), "ok": bool(good)}
    b_ok = all(c["ok"] for c in checks.values()) and not conflicts

    a_hits: list = []
    a_adv: list = []
    for r in cells[a_name]["records"]:
        a_hits += _find_key_anywhere(r, "champ_tiearb")
        for adv in ("cand_tiearb", "tiearb_enabled"):
            a_adv += _find_key_anywhere(r, adv)
    a_hits = sorted(set(a_hits))
    a_ok = not a_hits and bool(cells[a_name]["records"])

    return bool(b_ok and a_ok), {
        "expected_rung": rung,
        "cell_b": {"resolved": merged, "resolved_at": where, "checks": checks,
                   "conflicts": conflicts, "addresses_found": [f["resolved_at"]
                                                               for f in b_found],
                   "ok": b_ok},
        "cell_a": {"champ_tiearb_addresses_found": a_hits,
                   "advisory_neighbour_keys_found": sorted(set(a_adv)),
                   "n_records": len(cells[a_name]["records"]), "ok": a_ok,
                   "semantics": "ANY presence of the key `champ_tiearb` on CELL A "
                                "VOIDS (READ_RULE §3, DESIGN §6.1 byte-identity); "
                                "an EMPTY cell also fails (absent is fail)"}}


def gate_fire(telem: dict) -> tuple:
    """`G-FIRE` — CELL B's `phi_effective >= 1.0` fired tied tile plies per game,
    where `phi = fired_plies_total / games` and
    `phi_effective = phi × (1 − error_rate_on_fired)`.

    Binds on `phi_effective`, verbatim. The reason the EFFECTIVE rate is the right
    quantity is READ_RULE §0.B's: a ply whose arbitration ERRORED reverted to the
    champion's own pick and was therefore not arbitrated at all, so an arbiter that
    triggers 20×/game and falls back 20×/game has a raw `phi` of 20 and arbitrates
    NOTHING — exactly the inert surface this gate exists to refuse.

    `games` is CELL B's SCORED game count (not the telemetry-carrying subset): a
    game that lost its telemetry is a game the arbiter cannot be SHOWN to have fired
    in, and counting it in the denominator is the fail-closed direction. An absent
    `fired_plies` (and absent `fires`) or an absent `errors` gives `None`, which
    fails the floor.
    """
    eff = telem.get("phi_effective")
    return _ge(eff, PHI_FLOOR), {
        "phi": telem.get("phi"), "phi_effective": eff,
        "error_rate_on_fired": telem.get("error_rate_on_fired"),
        "fired_plies_total": telem.get("fired_plies_used"),
        "fired_field_used": telem.get("fired_source"),
        "errors_total": telem.get("errors_total"),
        "games_denominator": telem.get("n_games"),
        "n_games_with_telemetry": telem.get("n_games_with_telemetry"),
        "floor": PHI_FLOOR, "binds_on": "phi_effective",
        "formula": "phi = fired_plies_total / games; "
                   "phi_effective = phi * (1 - error_rate_on_fired)",
        "offline_prior_phi": 22.96, "stage2_realized_phi": 17.573}


def load_preflights(verdicts_dir: Path) -> list:
    """`verdicts/PREFLIGHT_<host>_FIRST.json` — the FIRST pre-flight on each host,
    which is the one §3 `G-J13` names (it must precede that host's game 1)."""
    out = []
    if not verdicts_dir.exists():
        return out
    for p in sorted(verdicts_dir.glob("PREFLIGHT_*_FIRST.json")):
        try:
            doc = json.loads(p.read_text())
        except Exception as e:                                       # noqa: BLE001
            doc = {"_parse_error": f"{type(e).__name__}: {e}"}
        doc["_path"] = str(p)
        m = re.match(r"PREFLIGHT_(.+)_FIRST\.json$", p.name)
        doc.setdefault("host", m.group(1) if m else p.name)
        out.append(doc)
    return out


def _j13_sides(doc: dict) -> tuple:
    """The two witnesses, from an explicit `two_sided` block or, failing that, from
    the `checks` list by name. `None` means ABSENT — which FAILS the gate and is
    never coerced to True."""
    ts = doc.get("two_sided")
    if isinstance(ts, dict):
        return ts.get("pick_changed"), ts.get("root_leaf_value_bits_unchanged")
    pos = neg = None
    for ch in doc.get("checks") or []:
        name = str(ch.get("check", ""))
        if "pick_change" in name or "pick_changed" in name:
            pos = bool(ch.get("ok"))
        if "root_leaf_value_bits" in name:
            neg = bool(ch.get("ok"))
    return pos, neg


def gate_j13(preflights: list, verdicts_dir: Path) -> tuple:
    """`G-J13` — the TWO-SIDED arbiter positive control passed on the launching box
    at the launch commit: **pick CHANGED** and **root leaf value bits UNCHANGED**,
    recorded in `verdicts/PREFLIGHT_<host>_FIRST.json` before that host's game 1.
    VOIDS on "either side failing, or absent".

    Fail-closed: no pre-flight file at all fails; a file that does not carry BOTH
    booleans fails; `all_preflight_pass` is required when the file carries it.
    Without this a zeroed dose grades a perfect null wearing the shape of a real
    cell. DESIGN §6.3 makes this a SINGLE-BOX run, so one host is expected — but
    every `*_FIRST.json` present must pass, because a second host that ran a failing
    control would have contributed games.
    """
    by_host, ok = {}, bool(preflights)
    for doc in preflights:
        pos, neg = _j13_sides(doc)
        aps = doc.get("all_preflight_pass")
        good = (pos is True and neg is True and (aps is None or bool(aps)))
        by_host[doc.get("host")] = {
            "pick_changed": pos, "root_leaf_value_bits_unchanged": neg,
            "all_preflight_pass": aps, "path": doc.get("_path"),
            "parse_error": doc.get("_parse_error"), "ok": bool(good)}
        ok &= bool(good)
    return bool(ok), {"verdicts_dir": str(verdicts_dir), "hosts": by_host,
                      "n_preflights": len(preflights),
                      "semantics": "TWO-SIDED: pick CHANGED **and** "
                                   "root_leaf_value_bits UNCHANGED; absent on either "
                                   "side, or no pre-flight at all, VOIDS"}


def gate_rules(cells: dict, profile: str, r9: str) -> tuple:
    """`G-RULES` — BOTH cells stamp `rules_profile == "fixed_v1"` and
    `r9_env == "1"`. VOIDS on "anything else".

    ⚠️ AMBIGUITY, DECLARED: the committed text quotes `r9_env` as the STRING `"1"`;
    `match.py` stamps exactly that (verified on the 2026-08-09 archive). A `1` or a
    `True` written by some later writer is accepted as the same witness and the RAW
    value is printed, because the proposition is "R9 was on", not "the JSON type was
    str". Anything else — absent, `"0"`, `False` — fails. `rules_manifest.r9_env_ok`
    is cross-checked and REPORTED (advisory: it is the writer's own observation).
    """
    obs, ok = {}, True
    for name, c in cells.items():
        wp = resolve_witness(c["records"], "rules_profile",
                             extra=("rules_manifest.name",))
        wr = resolve_witness(c["records"], "r9_env")
        wok = resolve_witness(c["records"], addresses=("rules_manifest.r9_env_ok",))
        r9_raw = wr["value"]
        r9_good = (r9_raw == r9 or r9_raw is True
                   or (isinstance(r9_raw, int) and not isinstance(r9_raw, bool)
                       and str(r9_raw) == r9))
        good = (wp["value"] == profile and wp["consistent"]
                and bool(r9_good) and wr["consistent"])
        obs[name] = {"rules_profile": wp["value"],
                     "rules_profile_resolved_at": wp["resolved_at"],
                     "r9_env": r9_raw, "r9_env_resolved_at": wr["resolved_at"],
                     "r9_env_ok_advisory": wok["value"],
                     "consistent_across_records": wp["consistent"] and wr["consistent"],
                     "ok": bool(good)}
        ok &= bool(good)
    return bool(ok), {"expected_rules_profile": profile, "expected_r9_env": r9,
                      "observed": obs}


def gate_diverge(cells: dict) -> tuple:
    """`G-DIVERGE` — REAL divergence count == 0 in BOTH cells, and `final_agree` on
    >= 99% of scored games in BOTH cells. VOIDS on "any REAL divergence".

    The `real` ledger is summed over ALL records (not just scored ones): a REAL
    divergence in a game that later voided is still a rules divergence.
    `counts` — the CLASSIFIED ledger, `WALL_LEGALITY` / `UNPLACEABLE_REDRAW` — is
    reported and does NOT void (DESIGN §2.1).
    """
    obs, ok = {}, True
    for name, c in cells.items():
        real: Counter = Counter()
        counts: Counter = Counter()
        for r in c["records"]:
            real.update(r.get("real") or {})
            counts.update(r.get("counts") or {})
        scored = c["scored"]
        n = len(scored)
        agree = sum(1 for r in scored if r.get("final_agree"))
        frac = (agree / n) if n else None
        good = (sum(real.values()) == 0 and n > 0 and frac is not None
                and frac >= FINAL_AGREE_FLOOR)
        obs[name] = {"real_total": sum(real.values()), "real": dict(real),
                     "classified_counts": dict(counts),
                     "n_scored": n, "final_agree_n": agree,
                     "final_agree_frac": frac,
                     "replay_ok_all": all(r.get("replay_ok") for r in scored) if n
                                      else None,
                     "ok": bool(good)}
        ok &= bool(good)
    return bool(ok), {"final_agree_floor": FINAL_AGREE_FLOOR, "observed": obs,
                      "benign_classes": list(BENIGN_DIVERGENCE_CLASSES),
                      "note": BENIGN_NOTE}


def gate_jcz(cells: dict, conf: dict) -> tuple:
    """`G-JCZ` — JCZ provenance identical across cells and equal to DESIGN §7.1
    (rev `29a1561…`, jar sha256 `4dc5439d…`, `LegacyAiPlayer`, `basic:2`, ai class
    `com.jcloisterzone.ai.AiEngine`). VOIDS on "any difference".

    The jar hash is stamped as `jcz_jar_sha256_16` (the first 16 hex chars) by
    `match.py`; the full-length pin from WORKERS.conf is compared by PREFIX, and the
    prefix length actually compared is reported. `LegacyAiPlayer` has no manifest
    field of its own — it is JCZ's DEFAULT player and `jcz_ai_config` is stamped
    empty when nothing overrides it (DESIGN §7.1: "configurability NONE"), so an
    EMPTY `jcz_ai_config` witnesses it and a NON-EMPTY one that does not name
    `LegacyAiPlayer` FAILS.
    """
    want = {"jcz_git_rev": conf["JCZ_REV"], "jcz_ai_class": conf["JCZ_AI_CLASS"],
            "tile_set": conf["JCZ_TILES"]}
    obs, ok = {}, True
    for name, c in cells.items():
        cell_obs = {}
        good = True
        for key, exp in want.items():
            w = resolve_witness(c["records"], key)
            hit = (w["value"] == exp) and w["consistent"]
            cell_obs[key] = {"observed": w["value"], "expected": exp,
                             "resolved_at": w["resolved_at"], "ok": hit}
            good &= hit
        wsha = resolve_witness(c["records"], "jcz_jar_sha256_16",
                               extra=("jcz_jar_sha256",))
        sha = wsha["value"]
        sha_ok = (isinstance(sha, str) and len(sha) >= 8
                  and conf["JCZ_JAR_SHA256"].startswith(sha) and wsha["consistent"])
        cell_obs["jcz_jar_sha256"] = {
            "observed": sha, "expected_full": conf["JCZ_JAR_SHA256"],
            "compared_prefix_len": len(sha) if isinstance(sha, str) else None,
            "resolved_at": wsha["resolved_at"], "ok": bool(sha_ok)}
        good &= bool(sha_ok)
        wcfg = resolve_witness(c["records"], "jcz_ai_config")
        cfg = wcfg["value"]
        cfg_ok = isinstance(cfg, dict) and (
            not cfg or "LegacyAiPlayer" in json.dumps(cfg, default=str))
        cell_obs["jcz_ai_config"] = {
            "observed": cfg, "resolved_at": wcfg["resolved_at"], "ok": bool(cfg_ok),
            "semantics": "EMPTY == the DEFAULT LegacyAiPlayer (DESIGN §7.1: JCZ has "
                         "no depth/budget/temperature/seed knob); a NON-EMPTY config "
                         "that does not name LegacyAiPlayer FAILS"}
        good &= bool(cfg_ok)
        wjar = resolve_witness(c["records"], "jcz_jar")
        cell_obs["jcz_jar_path_reported"] = {"observed": wjar["value"],
                                             "expected": conf["JCZ_JAR"]}
        obs[name] = {"checks": cell_obs, "ok": bool(good)}
        ok &= bool(good)

    def _sig(name):
        return json.dumps({k: v["observed"] for k, v in obs[name]["checks"].items()
                           if k != "jcz_jar_path_reported"}, sort_keys=True,
                          default=str)
    identical = len({_sig(n) for n in obs}) == 1
    return bool(ok and identical), {"expected": {**want,
                                                 "jcz_jar_sha256": conf["JCZ_JAR_SHA256"],
                                                 "ai_player": "LegacyAiPlayer"},
                                    "observed": obs,
                                    "identical_across_cells": identical}


def _commit_of(value):
    """A 7-40 hex commit out of a raw rev, a `<rev>-dirty` stamp, or a
    `carc_rs-<version>+<commit[:12]>+rustc<toolchain>` build id."""
    if not isinstance(value, str):
        return None
    m = re.match(r"^carc_rs-[^+]+\+([0-9a-f]{7,40})\+rustc", value.strip())
    if m:
        return m.group(1)
    m = re.match(r"^([0-9a-f]{7,40})", value.strip())
    return m.group(1) if m else None


def wheel_relevant_diff(commit_a, commit_b, repo: Path) -> dict:
    """`git diff --name-only <preflight_commit>..<manifest_commit> -- rust/ src/
    engine/ scripts/` — printed as its OWN line with the exact command and its exact
    output so a reader can re-run it by hand.

    ⭐ **DISPOSITIVE IN ONE DIRECTION.** EMPTY ⇒ the pre-flight describes what ran
    ⇒ PASS. A DEGENERATE range (the two commits are the same) ⇒ there is nothing
    that could have changed ⇒ PASS — and that is the state a healthy run of this
    launcher produces, because the launcher generates its pre-flight AFTER the wheel
    build and BEFORE the detached launch (READ_RULE §3.1, the fix for Stage 2's
    unsatisfiable-by-construction gate: `measurement/tiearb2_stage2_20260817/
    READOUT.md` DISCLOSURE). NON-EMPTY ⇒ VOIDS. UNRESOLVED (a commit that does not
    parse, a git failure, a commit not in this checkout) ⇒ VOIDS, fail-closed.
    """
    if not commit_a or not commit_b:
        return {"resolved": False, "empty": None, "command": None, "output": None,
                "reason": "a commit witness did not parse — UNRESOLVED, VOIDS",
                "preflight_commit": commit_a, "manifest_commit": commit_b}
    if commit_a.startswith(commit_b) or commit_b.startswith(commit_a):
        return {"resolved": True, "empty": True, "command": None, "output": "",
                "reason": "DEGENERATE RANGE — the pre-flight and the manifest name the "
                          "same commit, so no wheel-relevant path can have changed",
                "preflight_commit": commit_a, "manifest_commit": commit_b}
    cmd = ["git", "diff", "--name-only", f"{commit_a}..{commit_b}", "--",
           *WHEEL_RELEVANT_PATHS]
    try:
        r = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True,
                           timeout=60)
    except Exception as e:                                           # noqa: BLE001
        return {"resolved": False, "empty": None, "command": " ".join(cmd),
                "output": f"{type(e).__name__}: {e}",
                "reason": "git could not be run — UNRESOLVED, VOIDS",
                "preflight_commit": commit_a, "manifest_commit": commit_b}
    if r.returncode != 0:
        return {"resolved": False, "empty": None, "command": " ".join(cmd),
                "output": (r.stderr or "").strip(),
                "reason": f"git exited {r.returncode} — UNRESOLVED, VOIDS",
                "preflight_commit": commit_a, "manifest_commit": commit_b}
    out = r.stdout.strip()
    return {"resolved": True, "empty": (out == ""), "command": " ".join(cmd),
            "output": out,
            "reason": ("EMPTY — no wheel-relevant path changed across the range, so the "
                       "pre-flight describes what ran"
                       if out == "" else
                       "NON-EMPTY — a wheel-relevant path changed, so the G-J13 positive "
                       "control does NOT describe what ran; VOIDS"),
            "preflight_commit": commit_a, "manifest_commit": commit_b}


def gate_tool(cells: dict, preflights: list, repo: Path) -> tuple:
    """`G-TOOL` — same-box `carc_rs_binary_sha` equal across both cells; AND
    `git diff --name-only <preflight_commit>..<manifest_commit> -- rust/ src/
    engine/ scripts/` is EMPTY or the range is degenerate. VOIDS on "a NON-EMPTY or
    UNRESOLVED wheel-relevant diff".

    Two conjuncts, both fail-closed:

    * **binary sha.** DESIGN §6.3 makes this a SINGLE-BOX run, which collapses
      Stage 2's cross-box build-identity problem into the strictly stronger
      same-box CONTENT hash. It must be PRESENT on both cells (absent is fail) and
      EQUAL. Where a pre-flight also carries it, it must match — that is the
      "did this box play the wheel its own pre-flight validated?" witness; an
      ABSENT pre-flight sha is reported, not failed.
      ⚠️ The `.so` is NOT reproducible across machines, so this hash is NEVER
      compared across BOXES — only across the two cells of the one box.
    * **the commit range**, reported as its own line with command and output, and
      dispositive in one direction only (see `wheel_relevant_diff`).
    """
    obs, sha_ok = {}, True
    shas = set()
    for name, c in cells.items():
        w = resolve_witness(c["records"], "carc_rs_binary_sha",
                            extra=("backend.carc_rs_binary_sha",
                                   "champion_manifest.backend.carc_rs_binary_sha",
                                   "backend_provenance.carc_rs_binary_sha"))
        obs[name] = {"carc_rs_binary_sha": w["value"], "resolved_at": w["resolved_at"],
                     "consistent_across_records": w["consistent"]}
        sha_ok &= bool(w["value"]) and w["consistent"]
        shas.add(json.dumps(w["value"], default=str))
    equal = len(shas) == 1 and sha_ok
    pf_sha = {d.get("host"): d.get("carc_rs_binary_sha")
              or (d.get("backend_provenance") or {}).get("carc_rs_binary_sha")
              for d in preflights}
    cell_sha = json.loads(next(iter(shas))) if len(shas) == 1 else None
    pf_match = {h: (None if s is None else s == cell_sha) for h, s in pf_sha.items()}
    pf_ok = all(v is not False for v in pf_match.values())

    pf_commit = None
    for d in preflights:
        pf_commit = (_commit_of((d.get("toolchain") or {}).get("code_rev"))
                     or _commit_of(d.get("carc_rs_build"))
                     or _commit_of((d.get("backend_provenance") or {})
                                   .get("carc_rs_build")))
        if pf_commit:
            break
    man_commit = None
    man_at = None
    for c in cells.values():
        for addrs in (("our_git_rev", "config.our_git_rev"),
                      ("champion_manifest.code_commit",),
                      ("carc_rs_build", "champion_manifest.backend.carc_rs_build")):
            w = resolve_witness(c["records"], addresses=addrs)
            cm = _commit_of(w["value"])
            if cm:
                man_commit, man_at = cm, w["resolved_at"]
                break
        if man_commit:
            break
    diff = wheel_relevant_diff(pf_commit, man_commit, repo)

    ok = bool(equal and pf_ok and diff.get("empty") is True)
    return ok, {"same_box_binary_sha": {"observed": obs, "equal_across_cells": equal,
                                        "preflight_binary_sha": pf_sha,
                                        "preflight_matches_cells": pf_match,
                                        "preflight_conjunct_ok": pf_ok},
                "commit_range": {**diff, "manifest_commit_resolved_at": man_at},
                "wheel_relevant_paths": list(WHEEL_RELEVANT_PATHS),
                "semantics": "NON-EMPTY or UNRESOLVED diff VOIDS; EMPTY or a "
                             "DEGENERATE range PASSES (READ_RULE §3.1)"}


def gate_n(n_common, n_a, n_b) -> tuple:
    """`G-N` — `n_common >= 320` DECKS **and** each cell `>= 640` games scored.
    Both clauses are the same 80%-of-plan bar in their own units (640 games IS 320
    decks), and the deck clause stays INDEPENDENTLY BINDING: two cells can each
    clear 640 games while overlapping on fewer than 320 COMMON decks, which would
    silently weaken `D`."""
    nc_ok = _ge(n_common, N_COMMON_FLOOR)
    cell_ok = _ge(n_a, CELL_GAMES_FLOOR) and _ge(n_b, CELL_GAMES_FLOOR)
    return bool(nc_ok and cell_ok), {
        "n_common": n_common, "n_common_floor": N_COMMON_FLOOR,
        "n_common_units": "DECKS (§2)",
        "n_games_scored": {"CELL_A": n_a, "CELL_B": n_b},
        "cell_games_floor": CELL_GAMES_FLOOR,
        "cell_games_planned": 800,
        "deck_clause_independently_binding": (
            "two cells can each clear 640 games while overlapping on fewer than 320 "
            "COMMON decks — that weakens D and still voids")}


def gate_ply(cells: dict, a_name: str, b_name: str, telem: dict) -> tuple:
    """`G-PLY` — "the ply-granularity witness (Stage-2 §0.F) is present for both
    cells". VOIDS on "absent".

    ⚠️ THE BIGGEST AMBIGUITY IN THIS FILE, DECLARED IN FULL. Stage-2 §0.F's witness
    is `tiearb_partial_argmax_total` — "absent is unknown-not-zero and fails;
    non-zero means an argmax was taken over a partial world set, i.e. the CRN
    pairing across arms was broken during play". **CELL A HAS NO ARBITER**, so it
    cannot carry that field, and `G-ARB` positively FORBIDS a `champ_tiearb` key on
    CELL A. Requiring the Stage-2 field on both cells would therefore be
    unsatisfiable by construction — the exact §3.1 defect class this design exists
    to avoid. The reading implemented, chosen so that no healthy run can fail it:

      * **BOTH cells** must carry the HARNESS's ply-granularity witness — per-game
        ply accounting: a `moves_by_seat` (or `moves`) block and `n_actions`. That
        is what "ply granularity is present" means for a cell with no arbiter.
      * **CELL B** must ADDITIONALLY carry the arbiter's own ply witness:
        `tile_plies` and `partial_argmax` present on its telemetry, with
        `partial_argmax_total == 0`, which is Stage-2 §0.F verbatim (absent fails;
        non-zero fails because the CRN pairing across arms was broken during play).
    """
    per_cell = {}
    ok = True
    for name, c in cells.items():
        recs = c["scored"]
        with_ply = sum(1 for r in recs
                       if (isinstance(r.get("moves_by_seat"), dict)
                           or isinstance(r.get("moves"), list))
                       and r.get("n_actions") is not None)
        good = bool(recs) and with_ply == len(recs)
        per_cell[name] = {"n_scored": len(recs), "n_with_ply_witness": with_ply,
                          "witness": "moves_by_seat|moves + n_actions", "ok": good}
        ok &= good
    pa = telem.get("partial_argmax_total")
    tp = telem.get("tile_plies_total")
    arb_ok = (pa is not None and pa == 0 and tp is not None
              and telem.get("telemetry_on_every_game") is True)
    per_cell[b_name]["arbiter_ply_witness"] = {
        "tile_plies_total": tp, "partial_argmax_total": pa,
        "telemetry_on_every_game": telem.get("telemetry_on_every_game"),
        "ok": bool(arb_ok),
        "semantics": "Stage-2 §0.F verbatim: partial_argmax ABSENT is "
                     "unknown-not-zero and FAILS; NON-ZERO means an argmax was taken "
                     "over a partial world set (CRN pairing broken during play) and "
                     "FAILS"}
    return bool(ok and arb_ok), {"per_cell": per_cell,
                                 "cell_a": a_name, "cell_b": b_name}


def gate_witness(primary: dict, witness: dict) -> tuple:
    """`G-WITNESS` — READ_RULE §1's recomputation clause, not a §3 gate, and named
    separately for exactly that reason: *"`z_D` is READ off the analyzer's computed
    value; the adjudicator ALSO recomputes it from the records and prints both. A
    disagreement beyond floating-point tolerance is `U-UNREADABLE`. The
    recomputation is a WITNESS, never a branch input."*

    So the witness can only ever VOID the run; it can never supply `z_D`. The branch
    is decided from the analyzer-path value alone.
    """
    fields = ("D", "se_D", "z_D", "n_common")
    detail = {f: {"analyzer_path": primary.get(f), "recomputed": witness.get(f),
                  "agree": (_close(primary.get(f), witness.get(f))
                            if f != "n_common" else
                            primary.get(f) == witness.get(f))} for f in fields}
    ok = all(v["agree"] for v in detail.values())
    return bool(ok), {"tolerance_relative": Z_WITNESS_TOL, "fields": detail,
                      "semantics": "§1 — the recomputation is a WITNESS, never a "
                                   "branch input; disagreement beyond float tolerance "
                                   "is U-UNREADABLE"}


# =========================================================================== #
# §4 — THE BRANCHES, read IN ORDER, first match wins.                          #
# =========================================================================== #
def decide_branch(gates: dict, D, z_D) -> dict:
    """READ_RULE §4, verbatim and in the committed order.

        J-CONFIRMED      gates PASS and z_D >= +2.0 and D > 0
        J-SIGN           gates PASS and +1.0 <= z_D < +2.0 and D > 0
        J-NULL-BOUNDED   gates PASS and |z_D| < 1.0
        J-REVERSED       gates PASS and z_D <= -2.0
        J-INDETERMINATE  gates PASS and -2.0 < z_D <= -1.0
        U-UNREADABLE     ANY §3 gate FAILS

    `U-UNREADABLE` is checked FIRST because §4 makes every other branch conditional
    on "all §3 gates PASS". A `z_D` in `[+1.0, +2.0)` with `D <= 0` is impossible by
    construction (`z_D` and `D` share a sign), and a NaN/absent `z_D` matches
    nothing: rather than fall through silently, either emits `U-UNREADABLE` with an
    explicit `no_branch_matched` reason. **§4 is NOT edited to cover them.**
    """
    failed = [g for g in ALL_GATES if not gates.get(g, {}).get("PASS")]
    if failed:
        return {"branch": "U-UNREADABLE", "failed_preconditions": failed,
                "reason": "a §3 precondition failed"}
    ok = (z_D is not None and z_D == z_D and D is not None)
    if ok and z_D >= Z_CONFIRM and D > 0:
        b = "J-CONFIRMED"
    elif ok and Z_SIGN <= z_D < Z_CONFIRM and D > 0:
        b = "J-SIGN"
    elif ok and abs(z_D) < Z_SIGN:
        b = "J-NULL-BOUNDED"
    elif ok and z_D <= -Z_CONFIRM:
        b = "J-REVERSED"
    elif ok and -Z_CONFIRM < z_D <= -Z_SIGN:
        b = "J-INDETERMINATE"
    else:
        return {"branch": "U-UNREADABLE", "failed_preconditions": ["NO-BRANCH"],
                "reason": NO_BRANCH_MATCHED, "no_branch_matched": True,
                "z_D": z_D, "D": D}
    return {"branch": b, "failed_preconditions": [], "reason": None}


# =========================================================================== #
# Assembly                                                                     #
# =========================================================================== #
def _ms_ratio(summary: dict):
    a, b = summary.get("ms_per_move_champ"), summary.get("ms_per_move_jcz")
    if a is None or not b:
        return None
    return a / b


def _elo_ci(summary: dict):
    e, s = summary.get("elo_unpaired"), summary.get("elo_sigma_1s")
    if e is None or s is None:
        return None, None
    return e - 1.96 * s, e + 1.96 * s


def _cell_block(name: str, cell: dict) -> dict:
    s = cell["summary"]
    lo, hi = _elo_ci(s)
    return {"cell": name, "archive": cell["path"], "archive_exists": cell["exists"],
            "n_records": s.get("n_records"), "n_scored": s.get("n_scored"),
            "n_decks_seat_balanced": len(cell["by_deck"]),
            "n_paired_decks_analyzer": s.get("n_paired_decks"),
            "half_pair_decks": len(s.get("half_pair_decks") or []),
            "seat_balance": cell["seat_balance"],
            "W_D_L": [s.get("wins"), s.get("draws"), s.get("losses")],
            "win_rate": s.get("win_rate"),
            "win_rate_z": ((s["win_rate"] - 0.5) / math.sqrt(0.25 / s["n_scored"])
                           if s.get("win_rate") is not None and s.get("n_scored")
                           else None),
            "elo": s.get("elo_unpaired"), "elo_sigma_1s": s.get("elo_sigma_1s"),
            "elo_ci95": [lo, hi],
            "paired_margin_mean": s.get("paired_margin_mean"),
            "paired_margin_sem": s.get("paired_margin_sem"),
            "paired_margin_z": s.get("paired_margin_z"),
            "unpaired_margin_mean": s.get("unpaired_margin_mean"),
            "unpaired_margin_sd": s.get("unpaired_margin_sd"),
            "per_seat": s.get("per_seat"),
            "voids": s.get("voids"), "n_failed": sum((s.get("voids") or {}).values()),
            "failure_rate": (sum((s.get("voids") or {}).values())
                             / s["n_records"] if s.get("n_records") else None),
            "ms_per_move_champ_OURS": s.get("ms_per_move_champ"),
            "ms_per_move_jcz_OPPONENT": s.get("ms_per_move_jcz"),
            "ms_ratio": _ms_ratio(s),
            "worker_s_per_game": s.get("wall_secs_per_game"),
            "divergence_counts": s.get("divergence_counts"),
            "divergence_real": s.get("divergence_real"),
            "final_agree_all": s.get("final_agree_all"),
            "replay_ok_all": s.get("replay_ok_all")}


def build_readout(args) -> dict:
    repo = Path(args.repo).resolve()
    conf, conf_meta = parse_workers_conf(Path(args.workers_conf))
    run_dir = Path(args.run_dir or conf.get("RUN_DIR") or HERE)
    verdicts = Path(args.verdicts_dir) if args.verdicts_dir else run_dir / "verdicts"
    band_path = Path(args.band_claim) if args.band_claim else Path(
        conf.get("BAND_SENTINEL") or (run_dir / "BAND_CLAIM.txt"))
    if not band_path.exists() and band_path.with_suffix(".json").exists():
        band_path = band_path.with_suffix(".json")

    mod, an_prov = _import_jcz_analyze(repo)
    a_name, b_name = conf["CELL_A"], conf["CELL_B"]
    cells = {a_name: load_cell(Path(args.cell_a), mod),
             b_name: load_cell(Path(args.cell_b), mod)}

    Dblock = deck_paired_D(cells[a_name]["by_deck"], cells[b_name]["by_deck"])
    wit = recompute_z_D_witness(cells[a_name]["scored"], cells[b_name]["scored"])
    telem = telemetry(cells[b_name]["scored"])

    try:
        decks_per_cell = int(conf.get("DECKS") or 400)
    except (TypeError, ValueError):
        decks_per_cell = 400
    claim = load_band_claim(band_path)
    preflights = load_preflights(verdicts)
    rung = {"enabled": True, "B": int(conf.get("TIEARB_B") or 16),
            "J": int(conf.get("TIEARB_J") or 4),
            "mode": conf.get("TIEARB_MODE") or "argmax",
            "salt": conf.get("TIEARB_SALT") or "tiearb2-deploy-v1",
            "eps": float(conf.get("TIEARB_EPS") or 0.0)}

    gates: dict = {}
    for gid, (ok, realized) in {
        "G-BAND": gate_band(cells, claim, decks_per_cell),
        "G-LEAF": gate_leaf(cells, conf["CHAMP_LEAF_HASH"]),
        "G-ARB": gate_arb(cells, a_name, b_name, rung),
        "G-FIRE": gate_fire(telem),
        "G-J13": gate_j13(preflights, verdicts),
        "G-RULES": gate_rules(cells, conf["RULES_PROFILE"], str(conf["FIX_R9"])),
        "G-DIVERGE": gate_diverge(cells),
        "G-JCZ": gate_jcz(cells, conf),
        "G-TOOL": gate_tool(cells, preflights, repo),
        "G-N": gate_n(Dblock["n_common"], cells[a_name]["summary"].get("n_scored"),
                      cells[b_name]["summary"].get("n_scored")),
        "G-PLY": gate_ply(cells, a_name, b_name, telem),
        "G-WITNESS": gate_witness(Dblock, wit),
    }.items():
        gates[gid] = {"PASS": bool(ok), "realized": realized}

    br = decide_branch(gates, Dblock["D"], Dblock["z_D"])
    head, read = BRANCH_TEXT[br["branch"]]

    a_sum = cells[a_name]["summary"]
    naive = None
    if (a_sum.get("paired_margin_mean") is not None
            and cells[b_name]["summary"].get("paired_margin_mean") is not None):
        naive = (cells[b_name]["summary"]["paired_margin_mean"]
                 - a_sum["paired_margin_mean"])

    ratio_a = _ms_ratio(a_sum)
    ratio_b = _ms_ratio(cells[b_name]["summary"])
    ws_a = a_sum.get("wall_secs_per_game")
    ws_b = cells[b_name]["summary"].get("wall_secs_per_game")

    return {
        "schema": SCHEMA, "design": DESIGN_DOC, "read_rule": READ_RULE_DOC,
        "run_id": conf.get("RUN_ID"),
        "cell_a": a_name, "cell_b": b_name,
        "branch": br["branch"],
        "branch_headline": head, "read": read,
        "failed_preconditions": br["failed_preconditions"],
        "no_branch_matched": bool(br.get("no_branch_matched")),
        "branch_reason": br.get("reason"),
        "D": Dblock["D"], "se_D": Dblock["se_D"], "z_D": Dblock["z_D"],
        "n_common": Dblock["n_common"],
        "D_block": {**Dblock,
                    "naive_summary_difference_DIAGNOSTIC": naive,
                    "n_to_resolve_D_2sigma_decks": n_to_reach(Dblock["n_common"],
                                                              Dblock["z_D"]),
                    "n_to_resolve_units": "DECKS per cell at the REALIZED dispersion",
                    "power_committed_before_the_run": POWER},
        "z_D_witness": {"analyzer_path": {k: Dblock[k]
                                          for k in ("D", "se_D", "z_D", "n_common")},
                        "recomputed": wit,
                        "gate": gates["G-WITNESS"]["realized"]},
        "cells": {a_name: _cell_block(a_name, cells[a_name]),
                  b_name: _cell_block(b_name, cells[b_name])},
        "arbiter_telemetry": telem,
        "preconditions": {g: gates[g]["PASS"] for g in ALL_GATES},
        "precondition_detail": {g: gates[g]["realized"] for g in ALL_GATES},
        "cost": {"field_name_trap": FIELD_NAME_TRAP,
                 "our_side_field": "ms_per_move_champ",
                 "opponent_field": "ms_per_move_jcz",
                 "ms_ratio": {a_name: ratio_a, b_name: ratio_b},
                 "ms_ratio_B_over_A": (ratio_b / ratio_a
                                       if ratio_a and ratio_b else None),
                 "worker_s_per_game": {a_name: ws_a, b_name: ws_b},
                 "worker_s_per_game_B_over_A": (ws_b / ws_a if ws_a and ws_b else None),
                 "prediction": COST_PREDICTION,
                 "waiver": CLOCK_WAIVER,
                 "never_a_branch_input": True},
        "cell_a_absolute": {
            "reading_20260809": READING_20260809,
            "realized": {"elo": a_sum.get("elo_unpaired"),
                         "elo_sigma_1s": a_sum.get("elo_sigma_1s"),
                         "win_rate": a_sum.get("win_rate"),
                         "paired_margin_mean": a_sum.get("paired_margin_mean"),
                         "paired_margin_sem": a_sum.get("paired_margin_sem"),
                         "paired_margin_z": a_sum.get("paired_margin_z"),
                         "n_paired_decks": a_sum.get("n_paired_decks")},
            "delta_elo_vs_20260809": (a_sum["elo_unpaired"] - READING_20260809["elo"]
                                      if a_sum.get("elo_unpaired") is not None
                                      else None),
            "cross_band_rider": (
                "⚠️ CROSS-BAND CONTRAST (this band vs 1.08e11, at a different code "
                "era): CLAUDE.md's over-dispersion rider applies — σ inflates ≈1.8-2.2×, "
                f"so ±{READING_20260809['nominal_sigma_elo']} elo becomes ≈±"
                f"{READING_20260809['nominal_sigma_elo'] * 1.8:.0f}-"
                f"{READING_20260809['nominal_sigma_elo'] * 2.2:.0f} elo on this "
                "contrast. It is a REGRESSION TRIPWIRE, not a precision comparison. D — "
                "the primary statistic — is WITHIN-band and deck-matched, i.e. the "
                "robust class, and is unaffected."),
            "why_printed_on_every_branch": (
                "DESIGN §3.2: the champion's out-of-lineage strength is a finding "
                "independent of D, and it is the single thing an out-of-lineage anchor "
                "exists to catch."),
        },
        "dilution": {"cell_b_tiearb_errors_total": telem.get("errors_total"),
                     "cell_b_tiearb_first_error": telem.get("first_error"),
                     "statement_required": bool(telem.get("errors_total")),
                     "verbatim_0B": DILUTION_VERBATIM},
        "divergence_ledger": {
            n: {"classified_counts": c["summary"].get("divergence_counts"),
                "REAL": c["summary"].get("divergence_real")}
            for n, c in cells.items()},
        "benign_classes": list(BENIGN_DIVERGENCE_CLASSES), "benign_note": BENIGN_NOTE,
        "provenance": {"workers_conf": conf_meta, "constants": conf,
                       "analyzer": an_prov,
                       "analyzer_note": ("scripts/jcz_match/analyze.py::analyze is the "
                                         "deck-pairing authority; per_deck_balanced() "
                                         "mirrors its by_deck construction so D can be "
                                         "taken deck-wise"),
                       "band_sentinel": str(band_path),
                       "verdicts_dir": str(verdicts), "repo": str(repo)},
        "what_no_branch_does": (
            "READ_RULE §5: No branch flips governance/PRODUCTION.yaml. No branch "
            "licenses an on-device deploy. No branch licenses a change to B, J, the tie "
            "predicate, the salt, or the playout. No branch licenses a second cell. No "
            "branch makes any claim about superhuman strength."),
    }


# =========================================================================== #
# Rendering — §4.3's companion table, on EVERY branch.                          #
# =========================================================================== #
def _f(x, nd=4, sign=False):
    if x is None:
        return "n/a"
    try:
        if x != x:
            return "NaN"
        return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def render(v: dict) -> str:
    L: list = []
    a, b = v["cell_a"], v["cell_b"]
    A, B = v["cells"][a], v["cells"][b]
    ap = L.append

    ap(f"# READOUT — {v['run_id']}: JCZ out-of-lineage pricing of the tie arbiter")
    ap("")
    ap(f"> Adjudicates [`{v['read_rule']}`]({Path(v['read_rule']).name}) "
       f"(design: [`{v['design']}`]({Path(v['design']).name})). "
       "**Blind ordering: the read-rule and this adjudicator were committed before "
       "game 1.** The branch is taken VERBATIM.")
    ap("")
    ap(f"## BRANCH: `{v['branch']}` — {v['branch_headline']}")
    ap("")
    ap(v["read"])
    ap("")
    if v["failed_preconditions"]:
        ap(f"**FAILED PRECONDITIONS: {', '.join(v['failed_preconditions'])}**")
        if v.get("branch_reason"):
            ap("")
            ap(f"> {v['branch_reason']}")
        ap("")
    ap(f"`D = {_f(v['D'], 4, True)}` pts/game · `se(D) = {_f(v['se_D'])}` · "
       f"`z_D = {_f(v['z_D'], 4, True)}` · `n_common = {v['n_common']}` decks")
    ap("")
    ap(v["what_no_branch_does"])
    ap("")

    # ---- item 1 --------------------------------------------------------- #
    ap("## §4.3 item 1 — per cell")
    ap("")
    ap("| | CELL A `%s` | CELL B `%s` |" % (a, b))
    ap("|---|---|---|")
    rows = [
        ("archive", A["archive"], B["archive"]),
        ("n games (records / scored)",
         f"{A['n_records']} / {A['n_scored']}", f"{B['n_records']} / {B['n_scored']}"),
        ("n decks (seat-balanced)", A["n_decks_seat_balanced"],
         B["n_decks_seat_balanced"]),
        ("half-pair decks (excluded)", A["half_pair_decks"], B["half_pair_decks"]),
        ("seat balance (champ_seat: n)", A["seat_balance"], B["seat_balance"]),
        ("W/D/L", "/".join(str(x) for x in A["W_D_L"]),
         "/".join(str(x) for x in B["W_D_L"])),
        ("win rate (z)", f"{_f(A['win_rate'])} ({_f(A['win_rate_z'], 2, True)})",
         f"{_f(B['win_rate'])} ({_f(B['win_rate_z'], 2, True)})"),
        ("elo ±1σ (within-band)", f"{_f(A['elo'], 1, True)} ± {_f(A['elo_sigma_1s'], 1)}",
         f"{_f(B['elo'], 1, True)} ± {_f(B['elo_sigma_1s'], 1)}"),
        ("elo 95% CI",
         f"[{_f(A['elo_ci95'][0], 1, True)}, {_f(A['elo_ci95'][1], 1, True)}]",
         f"[{_f(B['elo_ci95'][0], 1, True)}, {_f(B['elo_ci95'][1], 1, True)}]"),
        ("deck-paired margin ± se (z)",
         f"{_f(A['paired_margin_mean'], 4, True)} ± {_f(A['paired_margin_sem'])} "
         f"({_f(A['paired_margin_z'], 3, True)})",
         f"{_f(B['paired_margin_mean'], 4, True)} ± {_f(B['paired_margin_sem'])} "
         f"({_f(B['paired_margin_z'], 3, True)})"),
        ("per-seat mean margin",
         {k: round(x["mean_margin"], 3) for k, x in (A["per_seat"] or {}).items()},
         {k: round(x["mean_margin"], 3) for k, x in (B["per_seat"] or {}).items()}),
        ("n_failed (voids) / rate",
         f"{A['n_failed']} / {_f(A['failure_rate'])}",
         f"{B['n_failed']} / {_f(B['failure_rate'])}"),
    ]
    for r in rows:
        ap(f"| {r[0]} | {r[1]} | {r[2]} |")
    ap("")

    # ---- item 2 --------------------------------------------------------- #
    d = v["D_block"]
    ap("## §4.3 item 2 — `D`, its se, `z_D`, `n_common`, the diagnostic, and the "
       "resolving `n`")
    ap("")
    ap(f"- **`D = M_B − M_A = {_f(d['D'], 4, True)}` pts/game**, deck-paired over "
       f"`n_common = {d['n_common']}` decks "
       f"(seeds {d['deck_seed_min']}..{d['deck_seed_max']})")
    ap(f"- `se(D) = {_f(d['se_D'])}` · **`z_D = {_f(d['z_D'], 4, True)}`** "
       "(convention: `eval_fair_puct._paired_z`)")
    ap(f"- on the common decks: `M_A = {_f(d['M_A_on_common'], 4, True)}` · "
       f"`M_B = {_f(d['M_B_on_common'], 4, True)}`")
    ap(f"- DIAGNOSTIC ONLY — naive difference of the two cell summaries: "
       f"`{_f(d['naive_summary_difference_DIAGNOSTIC'], 4, True)}`. "
       "**The branch uses the deck-paired `D`.**")
    ap(f"- **the `n` (DECKS/cell) that would resolve `D` to 2σ at the realized "
       f"dispersion: {d['n_to_resolve_D_2sigma_decks']}** "
       "(`n · (2/|z_D|)²`; `None` when `z_D` is absent, NaN or exactly zero)")
    ap(f"- committed power (DESIGN §4.2, before any number): se(D) assumed "
       f"{POWER['se_D_assumed_rho_0']} ⇒ 2σ conviction floor "
       f"|D| = {POWER['conviction_floor_D_at_2sigma']} pts/game; "
       f"§4.3's unfunded ladder: D=+1.00 needs "
       f"{POWER['n_to_convict_D_1.00_at_2sigma_decks']} decks/cell, D=+1.50 needs "
       f"{POWER['n_to_convict_D_1.50_at_2sigma_decks']}")
    w = v["z_D_witness"]
    ap(f"- §1 WITNESS (never a branch input): analyzer-path `z_D` = "
       f"{_f(w['analyzer_path']['z_D'], 6, True)}, independently recomputed `z_D` = "
       f"{_f(w['recomputed'].get('z_D'), 6, True)} — agreement: "
       f"`G-WITNESS` {'PASS' if v['preconditions']['G-WITNESS'] else 'FAIL'} "
       f"(tolerance {Z_WITNESS_TOL:g} relative)")
    ap("")

    # ---- item 3 --------------------------------------------------------- #
    t = v["arbiter_telemetry"]
    ap("## §4.3 item 3 — CELL B arbiter telemetry")
    ap("")
    ap("| quantity | realized | reference |")
    ap("|---|---|---|")
    ap(f"| `phi` (fired tied tile plies / game) | {_f(t.get('phi'), 4)} | "
       f"offline prior **22.96**, Stage-2 realized **17.573** |")
    ap(f"| `error_rate_on_fired` | {_f(t.get('error_rate_on_fired'), 6)} | — |")
    ap(f"| **`phi_effective`** (G-FIRE binds here) | "
       f"{_f(t.get('phi_effective'), 4)} | floor **{PHI_FLOOR}** |")
    ap(f"| `pickchanges` | {t.get('pickchanges_total')} | — |")
    ap(f"| `arms_total` | {t.get('arms_total_total')} | — |")
    ap(f"| `playouts_total` | {t.get('playouts_total_total')} | — |")
    ap(f"| `tiearb_errors_total` | {t.get('errors_total')} | — |")
    ap(f"| `tiearb_first_error` | {t.get('first_error')} | — |")
    ap(f"| `tile_plies_total` | {t.get('tile_plies_total')} | — |")
    ap(f"| games with telemetry | {t.get('n_games_with_telemetry')} / "
       f"{t.get('n_games')} | — |")
    ap("")

    # ---- item 4 --------------------------------------------------------- #
    c = v["cost"]
    ap("## §4.3 item 4 — cost (`ms_ratio`), and DESIGN §6.2's prediction vs realized")
    ap("")
    ap(c["field_name_trap"])
    ap("")
    ap(f"- fields read: **OUR side = `{c['our_side_field']}`**, "
       f"**opponent = `{c['opponent_field']}`**")
    ap(f"- CELL A `ms_ratio` = {_f(c['ms_ratio'][a])} "
       f"(`{c['our_side_field']}` {_f(A['ms_per_move_champ_OURS'], 1)} ms / "
       f"`{c['opponent_field']}` {_f(A['ms_per_move_jcz_OPPONENT'], 1)} ms)")
    ap(f"- CELL B `ms_ratio` = {_f(c['ms_ratio'][b])} "
       f"(`{c['our_side_field']}` {_f(B['ms_per_move_champ_OURS'], 1)} ms / "
       f"`{c['opponent_field']}` {_f(B['ms_per_move_jcz_OPPONENT'], 1)} ms)")
    ap(f"- **DESIGN §6.2 PREDICTED: CELL B ≈ {COST_PREDICTION['cell_b_over_cell_a']}× "
       f"CELL A per game, {COST_PREDICTION['cell_b_worker_s_per_game']} worker-s/game** "
       f"(CELL A {COST_PREDICTION['cell_a_worker_s_per_game']} worker-s/game)")
    ap(f"- REALIZED: CELL A {_f(c['worker_s_per_game'][a], 1)} worker-s/game · "
       f"CELL B {_f(c['worker_s_per_game'][b], 1)} worker-s/game · "
       f"**B/A = {_f(c['worker_s_per_game_B_over_A'], 3)}×** "
       f"(per-move `ms_ratio` B/A = {_f(c['ms_ratio_B_over_A'], 3)}×)")
    ap("")
    ap(c["waiver"])
    ap("")

    # ---- item 5 --------------------------------------------------------- #
    ap("## §4.3 item 5 — every §3 gate, its realized value, and which address resolved")
    ap("")
    ap("| gate | PASS | key realized evidence |")
    ap("|---|---|---|")
    for g in ALL_GATES:
        det = json.dumps(v["precondition_detail"][g], default=str)
        det = det.replace("|", "\\|")
        ap(f"| `{g}` | {'✅' if v['preconditions'][g] else '❌ **FAIL**'} | "
           f"{det[:600]}{'…' if len(det) > 600 else ''} |")
    ap("")
    tool = v["precondition_detail"]["G-TOOL"]["commit_range"]
    ap("### `G-TOOL` — the commit-range delta, on its own line")
    ap("")
    ap(f"- pre-flight commit `{tool.get('preflight_commit')}` .. manifest commit "
       f"`{tool.get('manifest_commit')}`")
    ap(f"- command: `{tool.get('command') or '(none — degenerate range)'}`")
    ap(f"- output: `{(tool.get('output') or '') or '(empty)'}`")
    ap(f"- **{tool.get('reason')}**")
    ap("- DISPOSITIVE IN ONE DIRECTION: a NON-EMPTY or UNRESOLVED wheel-relevant diff "
       "VOIDS; an EMPTY diff or a degenerate range PASSES (READ_RULE §3.1 — the fix "
       "for Stage 2's unsatisfiable-by-construction gate).")
    ap("")

    # ---- item 6 --------------------------------------------------------- #
    dil = v["dilution"]
    ap("## §4.3 item 6 — fail-soft dilution (READ_RULE §0.B)")
    ap("")
    ap(f"CELL B `tiearb_errors_total` = **{dil['cell_b_tiearb_errors_total']}**"
       + (f" (first error: `{dil['cell_b_tiearb_first_error']}`)"
          if dil.get("cell_b_tiearb_first_error") else ""))
    ap("")
    if dil["statement_required"]:
        ap("**§0.B, VERBATIM (mandatory: `tiearb_errors_total` > 0):**")
        ap("")
        for line in DILUTION_VERBATIM.split("\n"):
            ap("> " + line if line else ">")
    else:
        ap("`tiearb_errors_total` is 0 or unknown, so §0.B's verbatim dilution "
           "statement is not triggered by errors. The ASYMMETRY still holds and is "
           "restated: CELL A has no arbiter to fail, so any fail-soft dilutes `D` "
           "toward zero — a positive `D` is a lower bound and a null is weaker "
           "evidence of absence. (An UNKNOWN error count is itself a `G-FIRE` "
           "failure: absent is fail.)")
    ap("")

    # ---- item 7 --------------------------------------------------------- #
    ca = v["cell_a_absolute"]
    r09, rz = ca["reading_20260809"], ca["realized"]
    ap("## ⭐ §4.3 item 7 — CELL A's ABSOLUTE RESULT vs JCZ "
       "(printed on EVERY branch, `U-UNREADABLE` included)")
    ap("")
    ap("| | CELL A, THIS RUN | 2026-08-09 reading |")
    ap("|---|---|---|")
    ap(f"| elo | **{_f(rz['elo'], 1, True)}** ± {_f(rz['elo_sigma_1s'], 1)} (1σ) | "
       f"**+{r09['elo']}** |")
    ap(f"| win rate | **{_f(rz['win_rate'])}** | **{r09['win_rate']}** |")
    ap(f"| deck-paired margin | **{_f(rz['paired_margin_mean'], 4, True)} ± "
       f"{_f(rz['paired_margin_sem'])}** (z {_f(rz['paired_margin_z'], 3, True)}) over "
       f"{rz['n_paired_decks']} decks | **+{r09['paired_margin']} ± "
       f"{r09['paired_margin_sem']}** over {r09['n_decks']} decks |")
    ap(f"| band / rev | see `G-BAND` | {r09['band']:.2e} / `{r09['code_rev']}` |")
    ap("")
    ap(f"**Δelo vs the 2026-08-09 reading: {_f(ca['delta_elo_vs_20260809'], 1, True)}**")
    ap("")
    ap(ca["cross_band_rider"])
    ap("")
    ap(ca["why_printed_on_every_branch"])
    ap("")

    # ---- item 8 --------------------------------------------------------- #
    ap("## §4.3 item 8 — the divergence ledger, by class, for both cells")
    ap("")
    ap("| cell | classified `counts` | REAL |")
    ap("|---|---|---|")
    for n_, led in v["divergence_ledger"].items():
        ap(f"| `{n_}` | {led['classified_counts'] or '{}'} | "
           f"{led['REAL'] or '{}'}{'' if not led['REAL'] else ' ⛔ **VOIDS**'} |")
    ap("")
    ap(v["benign_note"])
    ap("")

    # ---- provenance ------------------------------------------------------ #
    p = v["provenance"]
    ap("## Provenance")
    ap("")
    ap(f"- WORKERS.conf parsed: **{p['workers_conf'].get('parsed')}** "
       f"(`{p['workers_conf'].get('path')}`)"
       + ("" if p["workers_conf"].get("parsed")
          else f" — ⚠️ {p['workers_conf'].get('note')}"))
    ap(f"- deck pairing: `scripts/jcz_match/analyze.py` imported = "
       f"**{p['analyzer'].get('imported')}** "
       f"({p['analyzer'].get('error') or p['analyzer'].get('from')})"
       + ("" if p["analyzer"].get("imported")
          else " — ⚠️ the VERBATIM replication in `_fallback_analyze` was used"))
    ap(f"- band sentinel: `{p['band_sentinel']}` · verdicts: `{p['verdicts_dir']}` · "
       f"repo: `{p['repo']}`")
    ap("")
    return "\n".join(L)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell-a", required=True,
                    help="CELL A archive (.jsonl) — the UNMODIFIED champion vs JCZ")
    ap.add_argument("--cell-b", required=True,
                    help="CELL B archive (.jsonl) — champion + tie arbiter vs JCZ")
    ap.add_argument("--json", default=None, help="write READOUT.json here")
    ap.add_argument("--out-md", default=None,
                    help="also write the markdown read-out here (it always goes to "
                         "stdout)")
    ap.add_argument("--run-dir", default=str(HERE),
                    help="run directory (default: this file's directory); supplies the "
                         "band sentinel and verdicts/ unless overridden")
    ap.add_argument("--verdicts-dir", default=None,
                    help="override <run-dir>/verdicts (G-J13 pre-flights)")
    ap.add_argument("--band-claim", default=None,
                    help="override WORKERS.conf::BAND_SENTINEL")
    ap.add_argument("--workers-conf", default=str(HERE / "WORKERS.conf"),
                    help="the constants file, PARSED (not re-typed)")
    ap.add_argument("--repo", default=str(REPO_DEFAULT),
                    help="repo root for G-TOOL's git diff")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    v = build_readout(args)
    md = render(v)
    print(md)
    if args.json:
        Path(args.json).write_text(json.dumps(v, indent=2, default=str) + "\n")
    if args.out_md:
        Path(args.out_md).write_text(md + "\n")
    # ⭐ EXIT 0 ON EVERY BRANCH, `U-UNREADABLE` INCLUDED: an unreadable run is a
    # pre-registered, fully acceptable OUTCOME, not a crash, and a non-zero exit
    # would make a launcher or a watchdog treat it as one.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
