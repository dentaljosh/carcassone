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
* **TWO BOXES (READ_RULE §0.F.1, owner ruling).** The run is split across `Doctor`
  (W30) and `laptop-wsl` (W22) by a STATIC contiguous deck split, so two gates are
  added and three become PER-HOST. `G-SPLIT` verifies from the records that the
  deck→host assignment is IDENTICAL across the two cells — load-bearing, not
  tidiness: `D` is deck-paired, so a deck that changed boxes puts every per-box
  difference (JVM packaging, `W` and hence contention, RAM) INSIDE the paired
  difference where it is arithmetically indistinguishable from the arbiter's effect.
  `G-COVER` verifies the coverage shape. `G-J13` / `G-JCZ` / `G-TOOL` are read per
  host, and the hosts that PLAYED are DERIVED from the records, never hard-coded.
* **`G-TOOL` must not be unsatisfiable by construction** (READ_RULE §3.1). Stage 2
  lost an adjudication to a gate that fired on every healthy run
  (`measurement/tiearb2_stage2_20260817/READOUT.md`, the DISCLOSURE section). Here
  the commit-range conjunct is **dispositive in ONE direction only**: a NON-EMPTY or
  UNRESOLVED wheel-relevant diff VOIDS; an EMPTY diff or a degenerate range (the two
  commits are the same, which is what a healthy launcher produces because it
  generates the pre-flight AFTER the wheel build and BEFORE the detached launch)
  PASSES.
* **⛔ `carc_rs_binary_sha` IS NEVER COMPARED ACROSS HOSTS (READ_RULE §0.F.2c).** The
  `.so` is not machine-reproducible — measured on this pair of boxes at the SAME
  build id — so `G-TOOL`'s cross-HOST conjunct binds on `carc_rs_build` (the build
  id) ALONE, and the sha binds WITHIN a host across the two cells (conjunct 1b, the
  rebuilt-here / staleness witness). The cross-host sha comparison is still computed
  and REPORTED, labelled NON-BINDING; it may never touch a gate's `ok`.
* **An UNSTAMPED witness is not a DIFFERENT witness (`G-JCZ`).** A per-record field
  the harness could not resolve (`match.py`'s `_git_rev` returns `None` on any
  subprocess failure) is a COVERAGE GAP, not a provenance difference: it VOIDS unless
  the pinned value is present and equal on EVERY host that played, at the per-host
  pre-flight address the read-rule names. Records that DISAGREE, a value that differs
  from the pin, and absence from EVERY record all still VOID.
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
    # §0.F.1 TWO BOXES (owner ruling). Reported in §4.3's two-box block; the gates
    # derive the hosts that PLAYED from the records, never from these literals.
    "W_LOCAL": "30",
    "W_LAPTOP": "22",
    "DECKS_LOCAL": "240",
    "DECKS_LAPTOP": "160",
    "LAPTOP_HOST": "laptop-wsl",
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

#: §0.F.1 / §3 `G-J13` — "Expected hosts: `Doctor`, `laptop-wsl`". REPORTED against,
#: never hard-coded INTO the gate: the set of hosts that PLAYED is derived from the
#: records (the hostmap), because a host that played and was not expected is exactly
#: the thing this must be able to see rather than assume away. The laptop half is
#: taken from `WORKERS.conf::LAPTOP_HOST` when that parses.
EXPECTED_HOSTS = ("Doctor", "laptop-wsl")

#: §0.F.1 `G-SPLIT` — the sidecar the launcher writes NEXT TO each cell's jsonl,
#: merged from the per-box shards: a `{deck_seed: host}` map.
HOSTMAP_SUFFIX = ".hostmap.json"

#: Offending-seed lists are CAPPED in the read-out (the full count is always given —
#: a truncated list must never be mistakable for the whole ledger).
MAX_LISTED_SEEDS = 20

ALL_GATES = ("G-BAND", "G-LEAF", "G-SPLIT", "G-COVER", "G-ARB", "G-FIRE", "G-J13",
             "G-RULES", "G-DIVERGE", "G-JCZ", "G-TOOL", "G-N", "G-PLY", "G-WITNESS")

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
#:
#: ⭐ DECISION (merge review R5): `phase_gate` is DELIBERATELY NOT a rung key.
#: `champion_manifest.cand_tiearb` gained it after this round's committed rung was
#: frozen, so making it one would turn every PRE-R5 archive's ABSENT field into a
#: retroactive `G-ARB` FAIL — a defect of the §0.F.2 class this gate already learned
#: once. The merge is key-wise (`if k not in ARB_RUNG_KEYS: continue`), so a POST-R5
#: archive carrying `phase_gate` is read exactly like a pre-R5 one and neither
#: direction moves. This round's cells are ungated (`phase_gate == "all"` == the
#: arbiter as committed); a round that VARIES the gate must pre-register it as a
#: rung key of its OWN read rule, not inherit one silently here.
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
# §0.F.1 — THE DECK→HOST MAP. The witness `G-SPLIT` and `G-COVER` are read from. #
# =========================================================================== #
def _coerce_seed(k):
    """A deck seed out of a JSON object key (they are always strings)."""
    try:
        return int(str(k).strip())
    except (TypeError, ValueError):
        return None


def _strip_conflict_markers(m: dict, meta: dict) -> dict:
    """`merge_cells.sh` writes a deck claimed by two shards as the sentinel value
    `CONFLICT:<a>|<b>` rather than dropping it. That is NOT a host: it is the merge
    step SAYING the deck's host is undetermined, so it becomes a `conflict` here —
    fail-closed, exactly like an absent stamp — instead of being adjudicated as a
    box literally called `CONFLICT:…`."""
    out = {}
    for d, h in m.items():
        if isinstance(h, str) and h.upper().startswith("CONFLICT"):
            meta["conflicts"].append({"deck_seed": d, "hosts": [h],
                                      "where": "merge step marked the deck CONFLICT"})
        else:
            out[d] = h
    return out


def parse_hostmap_doc(doc) -> tuple:
    """`(map, meta)` — `{deck_seed: host}` out of the sidecar's parsed JSON.

    The launcher MERGES per-box shards into one sidecar, so several shapes are
    accepted and the one that answered is REPORTED (`shape`):

    * `{"133000000000": "Doctor", ...}`                  — the deck→host map itself
    * `{"hostmap": {...}}` / `{"decks": {...}}`          — the same, wrapped
    * `{"Doctor": [133000000000, ...], "laptop-wsl": [...]}`  — the INVERTED map,
      which is the natural shape of "this box took this contiguous range"
    * `{"shards": [{"host": "Doctor", "decks": [...]}, ...]}` — the unmerged shards

    Anything else is an ERROR, not a guess: `G-SPLIT` VOIDS on an unparseable
    hostmap, because a split that cannot be READ is exactly the unverifiable split
    the gate exists to catch. A deck claimed by two different hosts inside ONE
    sidecar is a `conflict` — also fatal, for the same reason.
    """
    meta = {"shape": None, "error": None, "conflicts": []}
    if isinstance(doc, dict):
        for wrapper in ("hostmap", "host_map", "decks", "deck_hosts"):
            if wrapper in doc and isinstance(doc[wrapper], (dict, list)):
                inner, m = parse_hostmap_doc(doc[wrapper])
                m["shape"] = f"{wrapper}.{m['shape']}" if m["shape"] else wrapper
                return inner, m
        if "shards" in doc and isinstance(doc["shards"], list):
            out: dict = {}
            for sh in doc["shards"]:
                if not isinstance(sh, dict):
                    meta["error"] = "a shard entry is not an object"
                    return {}, meta
                host = sh.get("host") or sh.get("hostname")
                seeds = sh.get("decks") or sh.get("deck_seeds") or sh.get("seeds") or []
                if not isinstance(host, str) or not isinstance(seeds, list):
                    meta["error"] = "a shard entry lacks host/decks"
                    return {}, meta
                for s in seeds:
                    d = _coerce_seed(s)
                    if d is None:
                        meta["error"] = f"shard deck seed {s!r} is not an integer"
                        return {}, meta
                    if d in out and out[d] != host:
                        meta["conflicts"].append({"deck_seed": d,
                                                  "hosts": sorted({out[d], host})})
                    out[d] = host
            meta["shape"] = "shards"
            return _strip_conflict_markers(out, meta), meta
        vals = list(doc.values())
        if vals and all(isinstance(v, str) for v in vals):
            out = {}
            for k, v in doc.items():
                d = _coerce_seed(k)
                if d is None:
                    meta["error"] = f"key {k!r} is not a deck seed"
                    return {}, meta
                out[d] = v
            meta["shape"] = "deck_seed -> host"
            return _strip_conflict_markers(out, meta), meta
        if vals and all(isinstance(v, list) for v in vals):
            out = {}
            for host, seeds in doc.items():
                for s in seeds:
                    d = _coerce_seed(s)
                    if d is None:
                        meta["error"] = f"deck seed {s!r} is not an integer"
                        return {}, meta
                    if d in out and out[d] != host:
                        meta["conflicts"].append({"deck_seed": d,
                                                  "hosts": sorted({out[d], host})})
                    out[d] = host
            meta["shape"] = "host -> [deck_seed] (INVERTED)"
            return _strip_conflict_markers(out, meta), meta
        if not vals:
            meta["error"] = "hostmap is EMPTY"
            return {}, meta
    meta["error"] = f"unrecognised hostmap shape ({type(doc).__name__})"
    return {}, meta


def hostmap_candidates(cell_path: Path, cell_name: str, run_dir: Path,
                       override=None) -> list:
    """Where the sidecar is looked for, in order: an explicit `--cell-*-hostmap`,
    then `<cell>.hostmap.json` NEXT TO the jsonl (the committed location), then
    `<run_dir>/<cell_name>.hostmap.json`."""
    out = []
    if override:
        out.append(Path(override))
    try:
        out.append(cell_path.with_suffix(HOSTMAP_SUFFIX))
    except ValueError:                                       # pragma: no cover
        pass
    out.append(cell_path.parent / f"{cell_path.name}{HOSTMAP_SUFFIX}")
    out.append(Path(run_dir) / f"{cell_name}{HOSTMAP_SUFFIX}")
    seen, uniq = set(), []
    for p in out:
        if str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)
    return uniq


def load_hostmap(paths: list) -> dict:
    """The FIRST candidate that EXISTS is the sidecar, and if it does not parse the
    gate VOIDS — the next candidate is NOT tried, because silently falling through
    from a broken sidecar to a stale one is how an unverifiable split would slip
    past `G-SPLIT`."""
    out = {"searched": [str(p) for p in paths], "path": None, "exists": False,
           "parsed": None, "map": {}, "shape": None, "error": None, "conflicts": []}
    for p in paths:
        if not p.exists():
            continue
        out["path"], out["exists"] = str(p), True
        try:
            doc = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:                 # noqa: BLE001
            out["parsed"] = False
            out["error"] = f"{type(e).__name__}: {e}"
            return out
        m, meta = parse_hostmap_doc(doc)
        out["map"], out["shape"] = m, meta["shape"]
        out["conflicts"] = meta["conflicts"]
        out["error"] = meta["error"]
        out["parsed"] = meta["error"] is None
        return out
    out["error"] = ("no `<cell>.hostmap.json` sidecar at any candidate path — the "
                    "record `host`/`hostname` field is the only remaining source")
    return out


def _record_host(r: dict):
    """A host stamp ON THE RECORD, accepted as a source in its own right (§0.F.1:
    'accept also a `host`/`hostname` field on the records themselves')."""
    for key in ("host", "hostname"):
        v = r.get(key)
        if isinstance(v, str) and v:
            return v
    m = r.get("manifest") or {}
    for addr in ("host", "hostname", "config.host", "config.hostname"):
        v, hit = _get_path(m, addr)
        if hit and isinstance(v, str) and v:
            return v
    return None


def resolve_cell_hosts(cell: dict, hostmap: dict) -> dict:
    """`{deck_seed: host}` for ONE cell, merged sidecar-first then records, with the
    source that answered REPORTED per the §0.F.1 requirement.

    Fail-closed shape: a deck whose sidecar host and record host DISAGREE, or whose
    two seatings carry DIFFERENT record hosts, is a `conflict` — its host is not
    determined, which is an absent host stamp by another name and `G-SPLIT` VOIDS
    on it.
    """
    from_records: dict = {}
    rec_conflicts: list = []
    for r in cell["scored"]:
        try:
            d = int(r["deck_seed"])
        except (KeyError, TypeError, ValueError):
            continue
        h = _record_host(r)
        if h is None:
            continue
        if d in from_records and from_records[d] != h:
            rec_conflicts.append({"deck_seed": d,
                                  "hosts": sorted({from_records[d], h}),
                                  "where": "two records of the same deck"})
        from_records[d] = h

    merged: dict = {}
    source: dict = {}
    conflicts = list(hostmap.get("conflicts") or []) + rec_conflicts
    for d, h in (hostmap.get("map") or {}).items():
        merged[d], source[d] = h, "hostmap"
    for d, h in from_records.items():
        if d in merged:
            if merged[d] != h:
                conflicts.append({"deck_seed": d, "hosts": sorted({merged[d], h}),
                                  "where": "sidecar vs record host stamp"})
            continue
        merged[d], source[d] = h, "records"
    srcs = sorted(set(source.values()))
    return {"map": merged,
            "resolved_by": ("+".join(srcs) if srcs else None),
            "n_from_hostmap": sum(1 for s in source.values() if s == "hostmap"),
            "n_from_records": sum(1 for s in source.values() if s == "records"),
            "hostmap": {k: v for k, v in hostmap.items() if k != "map"},
            "hosts": dict(sorted(Counter(merged.values()).items())),
            "conflicts": conflicts,
            # a sidecar that FAILED to parse is always an error; a sidecar that is
            # merely ABSENT is only an error if the records did not fill in for it.
            "error": (hostmap.get("error")
                      if (not merged or hostmap.get("parsed") is False) else None)}


def host_of(hostres: dict, deck) -> str:
    return (hostres.get("map") or {}).get(deck)


def per_host_stats(cell: dict, hostres: dict) -> dict:
    """Per-host game counts, deck range and OUR-side `ms_per_move` for one cell —
    §4.3's two-box block. Reported, never a branch input."""
    out: dict = {}
    for r in cell["scored"]:
        try:
            d = int(r["deck_seed"])
        except (KeyError, TypeError, ValueError):
            continue
        h = host_of(hostres, d) or "UNMAPPED"
        b = out.setdefault(h, {"n_games": 0, "decks": set(), "ms": [], "wall": []})
        b["n_games"] += 1
        b["decks"].add(d)
        if isinstance(r.get("ms_per_move_champ"), (int, float)):
            b["ms"].append(float(r["ms_per_move_champ"]))
        if isinstance(r.get("wall_secs"), (int, float)):
            b["wall"].append(float(r["wall_secs"]))
    return {h: {"n_games": b["n_games"], "n_decks": len(b["decks"]),
                "deck_seed_min": min(b["decks"]) if b["decks"] else None,
                "deck_seed_max": max(b["decks"]) if b["decks"] else None,
                "ms_per_move_champ_OURS": (st.mean(b["ms"]) if b["ms"] else None),
                "worker_s_per_game": (st.mean(b["wall"]) if b["wall"] else None)}
            for h, b in sorted(out.items())}


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

    ⭐ **THIS IS NOW THE COMMITTED TEXT (READ_RULE §0.F.2, pre-launch).** The reading
    below was written here first as a declared ambiguity; the read-rule's §3 row now
    names it verbatim — "read top level → `config.*` → the harness-native address,
    and REPORT which resolved; ABSENT AT EVERY ADDRESS STILL FAILS" — so this
    docstring is the implementation of a committed sentence, not an interpretation of
    one. The reasoning is retained because it is why the sentence says what it says.

    ⚠️ READ_RULE names the witness `cand_leaf_hash`, which is
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


def _cap(seq, n=MAX_LISTED_SEEDS) -> dict:
    """A CAPPED list plus the FULL count — a truncated ledger must never be
    mistakable for the whole one."""
    seq = list(seq)
    return {"n_total": len(seq), "listed": seq[:n],
            "truncated": len(seq) > n, "list_cap": n}


def gate_split(cells: dict, a_name: str, b_name: str, hostres: dict) -> tuple:
    """`G-SPLIT` (ADDED §0.F.1) — "the deck→host assignment is IDENTICAL across both
    cells". VOIDS on "any deck whose host differs between cells; an absent host
    stamp".

    ⭐ WHY THIS IS LOAD-BEARING AND NOT TIDINESS (DESIGN §0.1.2, encoded here so the
    gate carries its own reason): `D` is DECK-PAIRED — deck `d` contributes
    `margin_B(d) − margin_A(d)`. If `d` ran on the laptop in CELL A and locally in
    CELL B, then every per-box difference — the JVM packaging (`24.04.2` vs
    `26.04.2`), the different `W` and hence different contention, the different RAM
    pressure — lands INSIDE that paired difference and is **arithmetically
    indistinguishable from the arbiter's effect**. With the split identical, every
    per-box effect is common to both terms and CANCELS EXACTLY. That cancellation is
    what makes the disclosed per-host JVM difference incapable of touching `D`, and
    it is why `G-JCZ` REPORTS the JVM packaging instead of failing on it.

    Sources for the host of a deck, in order, with the one that answered REPORTED:
    the `<cell>.hostmap.json` sidecar the launcher writes next to each cell's jsonl
    (merged from the per-box shards), then a `host`/`hostname` field on the records
    themselves. **ABSENT AT EVERY SOURCE FAILS** — an unverifiable split is exactly
    the confound this gate exists to catch, so it is never passed by omission.

    The comparison set is the decks `D` is actually taken over (the seat-balanced
    decks common to both cells): those are the decks whose per-box effects could
    enter the paired difference.
    """
    A, B = hostres[a_name], hostres[b_name]
    common = sorted(set(cells[a_name]["by_deck"]) & set(cells[b_name]["by_deck"]))
    mismatched, missing = [], []
    for d in common:
        ha, hb = A["map"].get(d), B["map"].get(d)
        if ha is None or hb is None:
            missing.append({"deck_seed": d, "cell_a_host": ha, "cell_b_host": hb})
        elif ha != hb:
            mismatched.append({"deck_seed": d, "cell_a_host": ha, "cell_b_host": hb})
    parse_errors = {n: hostres[n]["hostmap"].get("error") for n in (a_name, b_name)
                    if hostres[n]["hostmap"].get("parsed") is False}
    conflicts = {n: hostres[n]["conflicts"] for n in (a_name, b_name)
                 if hostres[n]["conflicts"]}
    resolved = bool(A["map"]) and bool(B["map"])
    ok = bool(resolved and common and not mismatched and not missing
              and not parse_errors and not conflicts)
    return ok, {
        "n_common_decks_compared": len(common),
        "mismatched_decks": _cap(mismatched),
        "decks_with_no_host_in_either_cell": _cap(missing),
        "unparseable_hostmap": parse_errors or None,
        "intra_cell_host_conflicts": conflicts or None,
        "per_cell": {n: {"host_source_resolved": hostres[n]["resolved_by"],
                         "n_decks_from_hostmap": hostres[n]["n_from_hostmap"],
                         "n_decks_from_record_stamps": hostres[n]["n_from_records"],
                         "hostmap": hostres[n]["hostmap"],
                         "decks_per_host": hostres[n]["hosts"]}
                     for n in (a_name, b_name)},
        "hosts_seen": sorted(set(A["hosts"]) | set(B["hosts"])),
        "semantics": (
            "FAIL-CLOSED. ABSENT AT EVERY SOURCE FAILS: the sidecar "
            "`<cell>.hostmap.json` is read first, then a `host`/`hostname` field on "
            "the records; a deck with no host in either cell, a deck whose host "
            "DIFFERS between the cells, an unparseable sidecar, or a deck claimed by "
            "two hosts inside one cell all VOID. Rationale: D is deck-paired, so a "
            "deck that changed boxes puts every per-box difference INSIDE the paired "
            "difference, arithmetically indistinguishable from the arbiter's effect "
            "(DESIGN §0.1.2)."),
    }


def gate_cover(cells: dict, decks_per_cell: int) -> tuple:
    """`G-COVER` (ADDED §0.F.1) — "the union of the per-box ranges covers all `DECKS`
    decks × 2 seatings EXACTLY ONCE per cell". VOIDS on "any gap, duplicate, or
    out-of-band deck".

    ⚠️ AMBIGUITY, DECLARED — THE `G-N` RECONCILIATION. `G-N` deliberately allows an
    80% floor (320 of 400 decks, 640 of 800 games), i.e. a PARTIAL run is readable.
    Read literally, "covers all `DECKS` decks" would make every partial run VOID and
    would delete `G-N`'s floor entirely — one committed sentence silently repealing
    another, and a gate that fails on a healthy-but-short run. **The reading
    implemented, so the two rules stand together:**

      * evaluated over what the cell CLAIMS to cover, i.e. its scored records;
      * **NO DUPLICATE** `(deck_seed, champ_seat, replicate)` in a cell — a cell that
        played the same game twice would double-count it;
      * **NO OUT-OF-BAND deck** — every seed inside `[band, band + DECKS − 1]` for
        that cell's OWN record-derived band (the SENTINEL comparison is `G-BAND`'s
        job; using it here too would double-charge one defect to two gates);
      * **BOTH SEATINGS for every deck present** — the per-box ranges are contiguous
        and each box runs `--champ-seat both`, so a deck with one seating means a box
        range was cut mid-deck, which is the coverage defect this gate names.

    A run that is merely SHORT therefore fails `G-N` on VOLUME — the gate that owns
    volume — and passes `G-COVER`, which owns SHAPE. Nothing is softened: every
    "exactly once" clause that a partial run can still satisfy is enforced verbatim.
    """
    per_cell, ok = {}, True
    for name, c in cells.items():
        recs = c["scored"]
        cells_seen: Counter = Counter()
        seats: dict = {}
        for r in recs:
            try:
                d, s = int(r["deck_seed"]), int(r["champ_seat"])
            except (KeyError, TypeError, ValueError):
                continue
            rep = r.get("replicate", 0)
            try:
                rep = int(rep)
            except (TypeError, ValueError):
                pass
            cells_seen[(d, s, rep)] += 1
            seats.setdefault(d, set()).add(s)
        dups = [{"deck_seed": k[0], "champ_seat": k[1], "replicate": k[2], "n": n}
                for k, n in sorted(cells_seen.items()) if n > 1]
        seeds = sorted(seats)
        derived = (seeds[0] // 1_000_000_000) * 1_000_000_000 if seeds else None
        hi = derived + decks_per_cell - 1 if derived is not None else None
        oob = [d for d in seeds if derived is None or not (derived <= d <= hi)]
        unbalanced = [{"deck_seed": d, "seatings_present": sorted(s)}
                      for d, s in sorted(seats.items()) if s != {0, 1}]
        good = bool(recs) and not dups and not oob and not unbalanced
        per_cell[name] = {
            "n_scored": len(recs), "n_decks": len(seeds),
            "band_derived_from_records": derived,
            "band_window": [derived, hi],
            "duplicate_deck_seat_replicate": _cap(dups),
            "out_of_band_deck_seeds": _cap(oob),
            "decks_without_both_seatings": _cap(unbalanced),
            "n_games_if_complete": decks_per_cell * 2,
            "ok": bool(good)}
        ok &= good
    return bool(ok), {
        "per_cell": per_cell, "decks_declared": decks_per_cell,
        "seatings_per_deck_required": 2,
        "reconciliation_with_G_N": (
            "G-N owns VOLUME (its committed 80% floor: n_common >= 320 decks, >= 640 "
            "games/cell) and G-COVER owns SHAPE. G-COVER is therefore evaluated over "
            "what the cell CLAIMS to cover: no duplicate (deck_seed, champ_seat, "
            "replicate), no seed outside the cell's own record-derived band window, "
            "and BOTH seatings present for every deck that is present. A partial run "
            "fails G-N on volume rather than G-COVER on absence — the alternative "
            "reading would repeal G-N's floor and void every healthy-but-short run "
            "(READ_RULE §3.1's defect class)."),
    }


#: `G-ARB`'s committed resolution order (§0.F.2's `G-LEAF` precedent applied to the
#: rung): manifest TOP LEVEL → `config.*` → the HARNESS-NATIVE address where the
#: resolved config is actually stamped → the per-game TELEMETRY block, LAST.
#:
#: ⚠️ **NAMING ASYMMETRY, and they are NOT two spellings of one object.**
#:   * `manifest.champion_manifest.cand_tiearb` is the **resolved CONFIG** the
#:     champion was constructed with — `{enabled, B, J, mode, salt, eps}`. It is the
#:     only address carrying `enabled` / `salt` / `eps` at all.
#:   * `record.champ_tiearb` is the per-game **firing TELEMETRY** —
#:     `{tile_plies, fires, fired_plies, pickchanges, arms_total, playouts_total,
#:     secs, errors, first_error, partial_argmax, max_plies, mode, B, J}`. It
#:     overlaps the config on `mode`/`B`/`J` ONLY, and carries live counters
#:     besides.
#:   Reading the rung from the telemetry alone leaves `enabled`/`salt`/`eps` null and
#:   fails a healthy run — the §0.F.2 defect class. Both are read; a DISAGREEMENT
#:   between them on a shared field is a CONFLICT and FAILS.
ARB_ADDRESSES = ("champ_tiearb", "config.champ_tiearb",
                 "champion_manifest.cand_tiearb",     # the RESOLVED CONFIG
                 "champion_manifest.champ_tiearb", "champion_manifest.tiearb",
                 "tiearb")


def _arb_dicts(records, key="champ_tiearb") -> list:
    """Every rung-shaped dict a cell exposes, with its address: the manifest at both
    levels, the harness-native champion-manifest addresses (`cand_tiearb` — the
    RESOLVED CONFIG, the only carrier of `enabled`/`salt`/`eps`), and — LAST — the
    per-game telemetry block `record.champ_tiearb`, which carries `mode`/`B`/`J`.
    See `ARB_ADDRESSES` for the naming asymmetry between the two objects."""
    manifest_addresses = (ARB_ADDRESSES if key == "champ_tiearb" else
                          (key, f"config.{key}", f"champion_manifest.{key}"))
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

    CELL B: every rung-shaped dict the cell exposes is MERGED into one resolved view,
    read in the committed order (`ARB_ADDRESSES`, the §0.F.2 `G-LEAF` precedent):
    manifest TOP LEVEL → `config.*` → `manifest.champion_manifest.cand_tiearb` (the
    RESOLVED CONFIG) → `record.champ_tiearb` (the firing TELEMETRY), with **each
    field's resolving address reported**.

    ⚠️ AMBIGUITY, DECLARED: the knob (`enabled`/`salt`/`eps`) and the telemetry
    (`mode`/`B`/`J` + counters) are written by different code paths — and under
    DIFFERENT NAMES: the config is `champion_manifest.cand_tiearb`, the telemetry is
    `record.champ_tiearb`. They are different OBJECTS, not two spellings of one.
    Requiring all six fields at ONE address is a gate no healthy run can satisfy
    (`record.champ_tiearb` has no `enabled`/`salt`/`eps` at all), so the merge reads
    every address. It stays fail-closed in BOTH directions: a field **absent at
    EVERY address FAILS**, a field **present-but-different FAILS**, and two addresses
    that **DISAGREE** on a field FAIL (`conflicts`).

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
            if k in merged:
                # The FIRST address in the committed order OWNS the field, so
                # `resolved_at` reports where it was actually read from and is not
                # overwritten by a later address that merely AGREES.
                if merged[k] != v:
                    conflicts.append({"field": k, "a": merged[k], "b": v,
                                      "addresses": [where[k], f["resolved_at"]]})
                continue
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
                   "resolution_order": list(ARB_ADDRESSES) + ["record.champ_tiearb"],
                   "ok": b_ok,
                   "semantics": "PER FIELD: manifest top level → `config.*` → "
                                "`champion_manifest.cand_tiearb` (the resolved "
                                "CONFIG — the only carrier of enabled/salt/eps) → "
                                "`record.champ_tiearb` (the firing TELEMETRY, which "
                                "carries mode/B/J only). ABSENT AT EVERY ADDRESS "
                                "FAILS; PRESENT-BUT-DIFFERENT FAILS; two addresses "
                                "that DISAGREE are a CONFLICT and FAIL"},
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


def _load_verdict_docs(verdicts_dir: Path, label: str) -> list:
    """`verdicts/PREFLIGHT_<host>_<LABEL>.json` for every host, with the host taken
    from the FILENAME (the file's own `host` field only fills in if the name does
    not parse) — the filename is what makes this a PER-HOST roster."""
    out = []
    if not verdicts_dir.exists():
        return out
    for p in sorted(verdicts_dir.glob(f"PREFLIGHT_*_{label}.json")):
        try:
            doc = json.loads(p.read_text())
            if not isinstance(doc, dict):
                doc = {"_parse_error": "not a JSON object"}
        except Exception as e:                                       # noqa: BLE001
            doc = {"_parse_error": f"{type(e).__name__}: {e}"}
        doc["_path"] = str(p)
        m = re.match(rf"PREFLIGHT_(.+)_{label}\.json$", p.name)
        if m:
            doc["host"] = m.group(1)
        else:
            doc.setdefault("host", p.name)
        out.append(doc)
    return out


def load_preflights(verdicts_dir: Path) -> list:
    """`verdicts/PREFLIGHT_<host>_FIRST.json` — the FIRST pre-flight on each host,
    which is the one §3 `G-J13` names (it must precede that host's game 1)."""
    return _load_verdict_docs(verdicts_dir, "FIRST")


def load_preflight_envs(verdicts_dir: Path) -> list:
    """`verdicts/PREFLIGHT_<host>_ENV.json` — the per-host ENVIRONMENT witness:
    the `carc_rs` build id + binary sha (`G-TOOL` conjunct 1, §0.F.2b), the jar
    sha256 verified ON THAT HOST (`G-JCZ`, per-host), and the JVM version string
    (REPORTED by `G-JCZ`, never a branch input)."""
    return _load_verdict_docs(verdicts_dir, "ENV")


def _match_host(host: str, roster: dict) -> tuple:
    """`(key, how)` — an exact hit in `roster`, else a case-insensitive one.
    `hostname` casing is not guaranteed stable across a WSL rebuild, and a VOID on
    a healthy run because one witness said `Doctor` and another `doctor` is exactly
    the §3.1 defect class; the relaxation is REPORTED wherever it is used."""
    if host in roster:
        return host, "exact"
    low = {str(k).lower(): k for k in roster}
    k = low.get(str(host).lower())
    return (k, "case-insensitive") if k is not None else (None, None)


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


def gate_j13(preflights: list, verdicts_dir: Path, hosts_played=(),
             expected_hosts=EXPECTED_HOSTS) -> tuple:
    """`G-J13` — **PER-HOST (§0.F.1).** "The TWO-SIDED arbiter positive control
    passed on EVERY host that played — pick CHANGED and root leaf value bits
    UNCHANGED — recorded in `verdicts/PREFLIGHT_<host>_FIRST.json`, generated AFTER
    any wheel build on that host and BEFORE that host's game 1." VOIDS on "either
    side failing on any host; a host that played with no pre-flight".

    Two fail-closed clauses:

    * **EVERY host that PLAYED has a pre-flight.** The roster of hosts that played is
      DERIVED from the records (the `G-SPLIT` hostmap), never hard-coded — a host
      that played and was not expected is precisely the thing this has to be able to
      SEE. `EXPECTED_HOSTS` (`Doctor`, `laptop-wsl`) is REPORTED against and is
      advisory: an unexpected host that played still needs a passing control, and an
      expected host that did not play needs nothing.
    * **Every pre-flight present PASSES**, both sides. A file that does not carry
      both booleans fails; `all_preflight_pass` is required when the file carries it.
      Without this control a zeroed dose grades a perfect champion-vs-champion null
      wearing the shape of a real cell, and no leaf-hash gate on this surface could
      detect it.
    """
    by_host = {}
    ok = bool(preflights)
    for doc in preflights:
        pos, neg = _j13_sides(doc)
        aps = doc.get("all_preflight_pass")
        good = (pos is True and neg is True and (aps is None or bool(aps)))
        by_host[doc.get("host")] = {
            "pick_changed": pos, "root_leaf_value_bits_unchanged": neg,
            "all_preflight_pass": aps, "path": doc.get("_path"),
            "parse_error": doc.get("_parse_error"), "ok": bool(good)}
        ok &= bool(good)

    played = sorted({h for h in hosts_played if h})
    matched, missing, relaxed = {}, [], []
    for h in played:
        key, how = _match_host(h, by_host)
        if key is None:
            missing.append(h)
        else:
            matched[h] = key
            if how != "exact":
                relaxed.append({"host_that_played": h, "preflight_host": key})
    ok = bool(ok and not missing)
    return bool(ok), {
        "verdicts_dir": str(verdicts_dir), "hosts": by_host,
        "n_preflights": len(preflights),
        "hosts_that_played": played,
        "hosts_that_played_with_NO_preflight": missing,
        "hosts_expected": list(expected_hosts),
        "expected_hosts_that_did_not_play": [h for h in expected_hosts
                                             if h not in played],
        "hosts_that_played_and_were_not_expected": [h for h in played
                                                    if h not in expected_hosts],
        "preflight_host_name_matched_case_insensitively": relaxed or None,
        "host_roster_source": ("derived from the G-SPLIT hostmap/record host stamps; "
                               "EXPECTED_HOSTS is REPORTED against, never hard-coded "
                               "into the gate"),
        "semantics": "PER-HOST and TWO-SIDED: pick CHANGED **and** "
                     "root_leaf_value_bits UNCHANGED on EVERY host that played; a "
                     "host that played with no pre-flight VOIDS; absent on either "
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


JVM_PACKAGING_NOTE = (
    "⚠️ THE JVM *PACKAGING* DIFFERS BY HOST — `17.0.19+10-1-24.04.2-Ubuntu` locally "
    "vs `+10-1-26.04.2-Ubuntu` on the laptop, the SAME OpenJDK 17.0.19 on a "
    "different distro base (DESIGN §0.1). It is **REPORTED HERE AND IS NEVER A "
    "BRANCH INPUT**: the PINNED artifacts are the jar (sha256, verified on each "
    "host) and the shim CLASSES (copied, not rebuilt — byte-identical bytecode on "
    "both hosts), and both are gated. The runtime difference cannot touch `D` "
    "because `G-SPLIT` holds the deck→host map IDENTICAL across the two cells, so "
    "every per-box effect is common to both terms of `margin_B(d) − margin_A(d)` "
    "and cancels exactly (DESIGN §0.1.2).")

#: READ_RULE §0.F.2c, carried into the read-out beside the number it disarms.
BINARY_SHA_CROSS_HOST_NOTE = (
    "⛔ REPORTED, NEVER BINDING (READ_RULE §0.F.2c). `carc_rs_binary_sha` is "
    "BOX-LOCAL staleness evidence and is NEVER compared across boxes: the `.so` is "
    "NOT reproducible across machines. Measured on THIS pair of boxes at the SAME "
    "`carc_rs_build` — `a4318fd59d9d8349` (Doctor) vs `8ae0b98427debb2e` "
    "(laptop-wsl) — so a cross-host equality conjunct on the sha would void EVERY "
    "healthy two-box run. ACROSS HOSTS the binding witness is `carc_rs_build` (the "
    "build id, machine-independent by construction); WITHIN a host the sha binds "
    "across the two cells (conjunct 1b), which is its true meaning.")


#: `G-JCZ`: the per-record manifest witness → the per-host `PREFLIGHT_<host>_ENV.json`
#: spelling of the SAME pinned artifact. Two spellings of one quantity (the ENV file is
#: written by `preflight.sh`, the manifest by `scripts/jcz_match/match.py`).
JCZ_ENV_KEY_OF = {"jcz_git_rev": "jcz_rev", "jcz_ai_class": "jcz_ai_class",
                  "tile_set": "jcz_tiles"}

JCZ_RECORD_WITNESS_SEMANTICS = (
    "§3 VOIDS on 'any difference in the pinned artifacts on any host', so: records "
    "that DISAGREE void; a value that differs from the pin voids; ABSENT FROM EVERY "
    "RECORD voids. Absent from SOME records (match.py stamps `jcz_git_rev` as "
    "`_git_rev(jcz_repo)`, which returns None on ANY subprocess failure — a box that "
    "cannot answer stamps NULL on every game while running the pinned checkout) voids "
    "UNLESS the pinned value is PRESENT AND EQUAL on EVERY host that played, at the "
    "per-host address the read-rule names (verdicts/PREFLIGHT_<host>_ENV.json, "
    "'verified ON EACH HOST'). No corroboration ⇒ the gap VOIDS.")


def _jcz_per_host(envs, conf: dict) -> tuple:
    """`G-JCZ`'s PER-HOST half (§0.F.1): the jar sha verified ON EACH HOST, plus the
    pinned rev / ai class / tile set as that host's own pre-flight ENV recorded them.
    An ABSENT per-host field is REPORTED (`ok: None`), never coerced to True — see
    `gate_jcz`'s docstring for why absence is charged to `G-J13` and difference here.
    """
    per_host, host_ok = {}, True
    for doc in envs:
        h = doc.get("host")
        checks, good = {}, True
        for key, exp in (("jcz_jar_sha256", conf["JCZ_JAR_SHA256"]),
                         ("jcz_rev", conf["JCZ_REV"]),
                         ("jcz_ai_class", conf["JCZ_AI_CLASS"]),
                         ("jcz_tiles", conf["JCZ_TILES"])):
            got = doc.get(key)
            if got is None:
                checks[key] = {"observed": None, "expected": exp, "ok": None,
                               "note": "ABSENT — REPORTED, not binding (see docstring)"}
                continue
            hit = (str(got) == exp) if key != "jcz_jar_sha256" else (
                isinstance(got, str) and len(got) >= 8 and exp.startswith(got))
            checks[key] = {"observed": got, "expected": exp, "ok": bool(hit)}
            good &= bool(hit)
        m = doc.get("jcz_jar_sha256_match")
        if m is not None:
            checks["jcz_jar_sha256_match_selfreport"] = {"observed": m,
                                                         "ok": bool(m)}
            good &= bool(m)
        per_host[h] = {
            "checks": checks, "path": doc.get("_path"),
            "parse_error": doc.get("_parse_error"),
            "jvm_version_string_REPORTED_NEVER_A_BRANCH_INPUT": doc.get("java"),
            "ok": bool(good)}
        host_ok &= bool(good)
    return per_host, bool(host_ok)


def gate_jcz(cells: dict, conf: dict, envs=(), hosts_played=()) -> tuple:
    """`G-JCZ` — **PER-HOST (§0.F.1).** JCZ provenance identical across cells AND
    across hosts, and equal to DESIGN §7.1 (rev `29a1561…`, jar sha256 `4dc5439d…`
    verified ON EACH HOST, `LegacyAiPlayer`, `basic:2`, ai class
    `com.jcloisterzone.ai.AiEngine`). VOIDS on "any difference in the pinned
    artifacts on any host".

    The jar hash is stamped as `jcz_jar_sha256_16` (the first 16 hex chars) by
    `match.py`; the full-length pin from WORKERS.conf is compared by PREFIX, and the
    prefix length actually compared is reported. `LegacyAiPlayer` has no manifest
    field of its own — it is JCZ's DEFAULT player and `jcz_ai_config` is stamped
    empty when nothing overrides it (DESIGN §7.1: "configurability NONE"), so an
    EMPTY `jcz_ai_config` witnesses it and a NON-EMPTY one that does not name
    `LegacyAiPlayer` FAILS.

    **PER-HOST conjunct.** Each host's `verdicts/PREFLIGHT_<host>_ENV.json` carries
    the jar sha256 it computed ON THAT BOX, plus `jcz_rev` / `jcz_ai_class` /
    `jcz_tiles` and the JVM version string. Every one of those that is PRESENT is
    checked against the pin and a DIFFERENCE VOIDS.

    ⚠️ AMBIGUITY, DECLARED: an ABSENT per-host ENV witness is REPORTED, not failed.
    The committed sentence conditions on the artifacts ("any difference in the
    pinned artifacts on any host") and the read-rule's own instruction is to read the
    per-host sha "if the pre-flight ENV json carries" one; the "a host ran with no
    pre-flight" failure is `G-J13`'s, and charging one defect to two gates would just
    obscure which one fired. Present-but-different fails here, always.

    ⚠️ The JVM *packaging* string differs by host BY DESIGN and is REPORTED, never a
    branch input — see `JVM_PACKAGING_NOTE`, printed with the read-out.

    ⚠️ **§0.F.2-CLASS AMBIGUITY, DECLARED — an UNSTAMPED record is not a DIFFERENT
    record.** `scripts/jcz_match/match.py:352` writes `jcz_git_rev` as
    `_git_rev(jcz_repo)`, and `_git_rev` returns **`None` on ANY failure** of the
    `git -C <jcz_repo> rev-parse HEAD` subprocess (`match.py:327-333`). A box where
    that subprocess cannot answer therefore stamps a NULL on every one of its games
    while running the correctly pinned checkout — so requiring the witness on EVERY
    RECORD (the `resolve_witness` `consistent` flag, which conjoins full coverage with
    non-disagreement) would void **every healthy run that used such a box**: the same
    unsatisfiable-by-construction defect class as §0.F.2 / §0.F.2b / §0.F.2c.

    The committed sentence conditions on a **DIFFERENCE** ("any difference in the
    pinned artifacts on any host"), so each cell-level witness binds as:

    * records that DISAGREE with each other → **VOIDS** (a mixed-provenance cell);
    * a value that differs from the pin → **VOIDS**;
    * ABSENT FROM EVERY RECORD → **VOIDS** (absent at every address still fails);
    * absent from SOME records → **VOIDS UNLESS** the pinned value is witnessed on
      **EVERY host that played**, at the per-host address the read-rule itself names
      (`verdicts/PREFLIGHT_<host>_ENV.json`) — which is the artifact the committed
      sentence points at ("verified ON EACH HOST"). No per-host corroboration, or a
      host that played with no ENV witness at all, and the gap VOIDS. Both the
      coverage and the corroboration are REPORTED per field.
    """
    # ---- PER-HOST (§0.F.1) is resolved FIRST: it is also what corroborates a
    # coverage gap in the per-record witnesses below.
    per_host, host_ok = _jcz_per_host(envs, conf)
    played = sorted({h for h in hosts_played if h})
    hosts_without_env = [h for h in played if _match_host(h, per_host)[0] is None]

    def _env_corroborates(key: str) -> bool:
        """Is the pinned value for `key` witnessed, PRESENT AND EQUAL, on EVERY host
        that played? Fail-closed: no hosts, a host with no ENV witness, an ABSENT
        per-host field (`ok is None`) or a differing one all answer False."""
        env_key = JCZ_ENV_KEY_OF.get(key)
        if env_key is None or not played or hosts_without_env:
            return False
        for h in played:
            k, _how = _match_host(h, per_host)
            if k is None:
                return False
            chk = (per_host[k].get("checks") or {}).get(env_key)
            if not (isinstance(chk, dict) and chk.get("ok") is True):
                return False
        return True

    want = {"jcz_git_rev": conf["JCZ_REV"], "jcz_ai_class": conf["JCZ_AI_CLASS"],
            "tile_set": conf["JCZ_TILES"]}
    obs, ok = {}, True
    for name, c in cells.items():
        cell_obs = {}
        good = True
        for key, exp in want.items():
            w = resolve_witness(c["records"], key)
            # VALUE-level agreement: `resolve_witness`'s `distinct` is keyed by
            # (value, address), so two records that agree on the value but resolved
            # it at different addresses are NOT a disagreement.
            values = {json.dumps(d["value"], sort_keys=True, default=str)
                      for d in w["distinct"]}
            agree = len(values) <= 1
            present = w["n_resolved"] > 0
            full = w["n_resolved"] == w["n_records"]
            corroborated = _env_corroborates(key)
            hit = bool(present and agree and (w["value"] == exp)
                       and (full or corroborated))
            cell_obs[key] = {"observed": w["value"], "expected": exp,
                             "resolved_at": w["resolved_at"], "ok": hit,
                             "matches_pin": bool(present and w["value"] == exp),
                             "records_agree": agree,
                             "values_seen": [json.loads(x) for x in sorted(values)],
                             "records_with_witness": w["n_resolved"],
                             "n_records": w["n_records"],
                             "stamped_on_every_record": full,
                             "coverage_gap_corroborated_on_every_host":
                                 None if full else corroborated,
                             "semantics": JCZ_RECORD_WITNESS_SEMANTICS}
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

    jvm = {h: v["jvm_version_string_REPORTED_NEVER_A_BRANCH_INPUT"]
           for h, v in per_host.items()}
    jar_by_host = {h: (v["checks"].get("jcz_jar_sha256") or {}).get("observed")
                   for h, v in per_host.items()}
    jar_identical_across_hosts = len({str(x) for x in jar_by_host.values()}) <= 1

    return bool(ok and identical and host_ok), {
        "expected": {**want, "jcz_jar_sha256": conf["JCZ_JAR_SHA256"],
                     "ai_player": "LegacyAiPlayer"},
        "observed": obs,
        "identical_across_cells": identical,
        "record_witness_coverage": {
            key: {name: {
                "records_with_witness": obs[name]["checks"][key][
                    "records_with_witness"],
                "n_records": obs[name]["checks"][key]["n_records"],
                "stamped_on_every_record": obs[name]["checks"][key][
                    "stamped_on_every_record"],
                "coverage_gap_corroborated_on_every_host": obs[name]["checks"][key][
                    "coverage_gap_corroborated_on_every_host"]}
                for name in obs}
            for key in want},
        "per_host": per_host,
        "per_host_ok": bool(host_ok),
        "hosts_that_played": played,
        "hosts_that_played_with_no_ENV_witness": hosts_without_env,
        "jar_sha_by_host": jar_by_host,
        "jar_sha_identical_across_hosts": jar_identical_across_hosts,
        "jvm_version_by_host_REPORTED": jvm,
        "jvm_packaging_differs_across_hosts": len({str(x) for x in jvm.values()}) > 1,
        "jvm_packaging_note": JVM_PACKAGING_NOTE}


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


def _preflight_build_witness(preflights: list, envs: list) -> dict:
    """`{host: {build_id, binary_sha, git_head, source}}` — the PRE-FLIGHT side of
    `G-TOOL` conjunct 1, ENV witness first (that is the file the read-rule names),
    the `_FIRST` verdict filling in whatever it also carries."""
    out: dict = {}
    for docs, label in ((envs, "ENV"), (preflights, "FIRST")):
        for d in docs:
            h = d.get("host")
            b = out.setdefault(h, {"build_id": None, "binary_sha": None,
                                   "git_head": None, "rustc": None, "sources": []})
            prov = d.get("backend_provenance") or {}
            vals = {
                "build_id": (d.get("carc_rs_build_id") or d.get("carc_rs_build")
                             or prov.get("carc_rs_build")),
                "binary_sha": (d.get("carc_rs_binary_sha")
                               or prov.get("carc_rs_binary_sha")),
                "git_head": (d.get("git_head")
                             or (d.get("toolchain") or {}).get("code_rev")),
                "rustc": d.get("rustc") or (d.get("toolchain") or {}).get("rustc"),
            }
            for k, v in vals.items():
                if b[k] is None and v is not None:
                    b[k] = v
            b["sources"].append(label)
    return out


def gate_tool(cells: dict, preflights: list, repo: Path, envs=(), hostres=None,
              hosts_played=()) -> tuple:
    """`G-TOOL` — **(amended §0.F.2b + §0.F.2c)** four conjuncts, all fail-closed:

    1. **CROSS-HOST build identity — BINDS ON `carc_rs_build` (THE BUILD ID) ONLY.**
       The build id recorded in each host's `verdicts/PREFLIGHT_<host>_ENV.json` is
       EQUAL across hosts. **Pre-flights are compared with pre-flights ONLY, never a
       pre-flight against a manifest**: `carc_rs_build_id()` embeds `git rev-parse
       HEAD` at CALL TIME, so that cross-comparison answers "did HEAD move between
       the two moments?" and is a false positive by construction (the Stage-2
       corrected shape). MIXED BUILDS ACROSS BOXES FAIL. Absent from EVERY pre-flight
       FAILS.

       ⛔ **`carc_rs_binary_sha` IS NEVER COMPARED ACROSS HOSTS (§0.F.2c).** The
       `.so` is **not machine-reproducible** — measured on this very pair of boxes at
       the SAME build id (`a4318fd59d9d8349` vs `8ae0b98427debb2e`), three
       independent pre-existing records. A cross-host equality conjunct on the sha
       would void EVERY healthy two-box run. It is still COMPUTED and REPORTED as
       `binary_sha_equal_across_hosts` — explicitly **NON-BINDING**, it may never
       touch `ok`.

    1b. **WITHIN-HOST staleness — BINDS ON `carc_rs_binary_sha` (§0.F.2c).** For each
       host (attributed via the hostmap), the manifest binary sha is EQUAL across the
       two cells and unmixed within a cell — the rebuilt-here / stale-wheel witness,
       which is the comparison the sha is actually meaningful for. A sha that MOVED
       within a host between cells FAILS. Evaluated and reported for EVERY host that
       carries the witness. Absent at EVERY source — manifest AND pre-flights — FAILS
       (`any_build_witness_present`).
    2. **CROSS-CELL code identity** — `our_git_rev` (falling back to
       `champion_manifest.code_commit`) equal across CELL A and CELL B, and
       CONSISTENT within each cell (a mixed-rev cell fails).
    3. **The commit range, unchanged** — `git diff --name-only
       <preflight>..<manifest> -- rust/ src/ engine/ scripts/` EMPTY or the range
       DEGENERATE. NON-EMPTY or UNRESOLVED VOIDS. This is the ONE place a pre-flight
       commit legitimately meets a manifest commit, because the question it asks IS
       "did HEAD move between those two moments" — which is exactly what a healthy
       launcher's ordering (pre-flight AFTER the wheel build, BEFORE the detached
       launch) answers "no" to.

    ⚠️ §0.F.2b, DECLARED: `scripts/jcz_match/match.py` **does not stamp
    `carc_rs_binary_sha`** anywhere, so requiring it from the manifest was a third
    conjunct unsatisfiable by construction. The manifest sha still **BINDS WHEN
    PRESENT** — compared WITHIN a host across the two cells, because the `.so` is not
    reproducible across machines and a cross-box comparison of it would be the same
    defect in a new place. **ABSENT AT EVERY SOURCE — manifest AND pre-flights —
    STILL FAILS.**
    """
    hostres = hostres or {}

    # ---- conjunct 1: pre-flight vs pre-flight, across hosts ------------------ #
    # ⛔ §0.F.2c: the BUILD ID is the only cross-host branch input. The binary sha is
    # computed and reported below, and is NEVER conjoined into `cross_host_ok` — the
    # `.so` is not machine-reproducible, so that comparison could not pass on any
    # healthy two-box run.
    pf = _preflight_build_witness(preflights, envs)
    build_ids = {h: b["build_id"] for h, b in pf.items() if b["build_id"] is not None}
    pf_shas = {h: b["binary_sha"] for h, b in pf.items()
               if b["binary_sha"] is not None}
    build_id_equal = len(set(build_ids.values())) <= 1
    pf_sha_equal = len(set(pf_shas.values())) <= 1      # REPORTED ONLY — NON-BINDING
    have_build_id_witness = bool(build_ids)
    have_pf_witness = bool(build_ids or pf_shas)
    cross_host_ok = bool(build_id_equal and have_build_id_witness)

    # ---- conjunct 2: cross-CELL code identity -------------------------------- #
    code_rev, code_ok = {}, True
    for name, c in cells.items():
        w = resolve_witness(c["records"], addresses=(
            "our_git_rev", "config.our_git_rev", "champion_manifest.code_commit"))
        code_rev[name] = {"value": w["value"], "resolved_at": w["resolved_at"],
                          "consistent_across_records": w["consistent"],
                          "distinct": w["distinct"]}
        code_ok &= bool(w["value"]) and w["consistent"]
    revs = {json.dumps(v["value"], default=str) for v in code_rev.values()}
    code_equal = bool(code_ok and len(revs) == 1)

    # ---- conjunct 1b: the binary sha BINDS WITHIN A HOST, across the two cells - #
    # §0.F.2c: this — not the cross-host comparison — is the sha's true meaning: a
    # rebuilt-here / staleness witness that catches a wheel changing under ONE box
    # mid-run. Evaluated for EVERY host that carries the witness.
    man_sha: dict = {}
    for name, c in cells.items():
        by_host: dict = {}
        for r in c["scored"] or c["records"]:
            m = r.get("manifest") or {}
            v = None
            for addr in ("carc_rs_binary_sha", "config.carc_rs_binary_sha",
                         "backend.carc_rs_binary_sha",
                         "champion_manifest.backend.carc_rs_binary_sha",
                         "backend_provenance.carc_rs_binary_sha"):
                got, hit = _get_path(m, addr)
                if hit and got is not None:
                    v = got
                    break
            if v is None:
                continue
            try:
                h = host_of(hostres.get(name) or {}, int(r["deck_seed"])) or "UNMAPPED"
            except (KeyError, TypeError, ValueError):
                h = "UNMAPPED"
            by_host.setdefault(h, set()).add(json.dumps(v, default=str))
        man_sha[name] = {h: sorted(vs) for h, vs in sorted(by_host.items())}
    hosts_with_man_sha = sorted({h for cell in man_sha.values() for h in cell})
    man_sha_ok = True
    man_sha_detail = {}
    for h in hosts_with_man_sha:
        vals = {n: man_sha[n].get(h) for n in man_sha}
        present = [v for v in vals.values() if v]
        mixed_in_cell = any(len(v) > 1 for v in present)
        equal_across_cells = len({json.dumps(v) for v in present}) <= 1
        good = (not mixed_in_cell) and equal_across_cells
        man_sha_detail[h] = {"per_cell": vals, "mixed_within_a_cell": mixed_in_cell,
                             "equal_across_cells": equal_across_cells, "ok": good,
                             "n_cells_with_witness": len(present)}
        man_sha_ok &= good
    have_manifest_witness = bool(hosts_with_man_sha)

    # ---- conjunct 3: the commit range ---------------------------------------- #
    man_commit, man_at = None, None
    for name, v in code_rev.items():
        cm = _commit_of(v["value"])
        if cm:
            man_commit, man_at = cm, v["resolved_at"]
            break
    if man_commit is None:
        for c in cells.values():
            w = resolve_witness(c["records"], addresses=(
                "carc_rs_build", "champion_manifest.backend.carc_rs_build"))
            cm = _commit_of(w["value"])
            if cm:
                man_commit, man_at = cm, w["resolved_at"]
                break
    ranges = {}
    for h in sorted(pf):
        pfc = _commit_of(pf[h]["git_head"]) or _commit_of(pf[h]["build_id"])
        ranges[h] = wheel_relevant_diff(pfc, man_commit, repo)
    if not ranges:
        ranges["<no pre-flight>"] = wheel_relevant_diff(None, man_commit, repo)
    failing = [r for r in ranges.values() if r.get("empty") is not True]
    primary = failing[0] if failing else next(iter(ranges.values()))
    range_ok = not failing

    ok = bool(cross_host_ok and code_equal and man_sha_ok and range_ok
              and (have_pf_witness or have_manifest_witness))
    return ok, {
        "cross_host_build_identity": {
            "preflight_build_id_by_host": build_ids,
            "preflight_binary_sha_by_host": pf_shas,
            "build_id_equal_across_hosts": build_id_equal,
            "build_id_witness_present": have_build_id_witness,
            "binary_sha_equal_across_hosts": pf_sha_equal,
            "binary_sha_equal_across_hosts_IS_NON_BINDING": True,
            "binary_sha_cross_host_note": BINARY_SHA_CROSS_HOST_NOTE,
            "witness_present": have_pf_witness,
            "binds_on": "carc_rs_build (the build id) ONLY",
            "ok": cross_host_ok,
            "semantics": "§0.F.2c: BINDS ON THE BUILD ID ONLY. PRE-FLIGHTS COMPARED "
                         "WITH PRE-FLIGHTS ONLY — never against a manifest "
                         "(carc_rs_build_id() embeds `git rev-parse HEAD` at call "
                         "time, so that comparison is a false positive by "
                         "construction). MIXED BUILDS ACROSS BOXES FAIL; a build id "
                         "absent from every pre-flight FAILS. ⛔ "
                         "`binary_sha_equal_across_hosts` is REPORTED ONLY and may "
                         "NEVER touch `ok` — the .so is not machine-reproducible."},
        "cross_cell_code_identity": {
            "observed": code_rev, "equal_across_cells": code_equal,
            "ok": code_equal,
            "semantics": "`our_git_rev` → `champion_manifest.code_commit`, equal "
                         "across cells AND consistent within each (a mixed-rev cell "
                         "fails)"},
        "manifest_binary_sha_when_present": {
            "by_cell_and_host": man_sha, "per_host": man_sha_detail,
            "hosts_evaluated": hosts_with_man_sha,
            "present": have_manifest_witness, "ok": man_sha_ok,
            "binds_on": "carc_rs_binary_sha, WITHIN a host, across the two cells",
            "semantics": "CONJUNCT 1b (§0.F.2b + §0.F.2c): this harness does not "
                         "reliably write `carc_rs_binary_sha`, so it BINDS ONLY WHEN "
                         "PRESENT — and then WITHIN a host across the two cells (host "
                         "via the hostmap), because the .so is not reproducible "
                         "across machines. A sha that MOVED within a host between "
                         "cells FAILS; a sha MIXED within one cell on one host FAILS. "
                         "Absent at EVERY source (manifest AND pre-flights) FAILS via "
                         "`any_build_witness_present`."},
        "any_build_witness_present": bool(have_pf_witness or have_manifest_witness),
        "commit_range": {**primary, "manifest_commit_resolved_at": man_at},
        "commit_range_by_preflight_host": ranges,
        "hosts_that_played": sorted({h for h in hosts_played if h}),
        "wheel_relevant_paths": list(WHEEL_RELEVANT_PATHS),
        "semantics": "FOUR CONJUNCTS (§0.F.2b + §0.F.2c): (1) cross-HOST build "
                     "identity from the pre-flights, BINDING ON THE BUILD ID ONLY "
                     "(the cross-host binary-sha comparison is REPORTED, NEVER "
                     "BINDING); (1b) within-HOST binary-sha identity across the two "
                     "cells, host via the hostmap; (2) cross-CELL code identity from "
                     "the manifests; and (3) the commit range (NON-EMPTY or "
                     "UNRESOLVED VOIDS, EMPTY or DEGENERATE PASSES). ABSENT AT EVERY "
                     "SOURCE STILL FAILS."}


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
    """`G-PLY` — **(amended §0.F.2)** "BOTH cells carry the harness ply accounting
    (`moves_by_seat`/`moves` + `n_actions`); CELL B additionally carries
    `partial_argmax` on EVERY game with `partial_argmax_total == 0`." VOIDS on
    "absent accounting on either cell; absent `partial_argmax` on CELL B (unknown ≠
    zero); non-zero `partial_argmax`".

    ⭐ **THAT IS NOW THE COMMITTED TEXT.** The reading below was written here first as
    a declared ambiguity and READ_RULE §0.F.2 adopted it verbatim, pre-launch,
    because the original §3 sentence was UNSATISFIABLE BY CONSTRUCTION. The reasoning
    is retained because it is why the committed sentence says what it says.

    Stage-2 §0.F's witness
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

    # ---- §0.F.1 TWO BOXES: the deck→host map, the witness G-SPLIT/G-COVER and the
    # per-host halves of G-J13 / G-JCZ / G-TOOL are all read from.
    hostmaps = {
        a_name: load_hostmap(hostmap_candidates(Path(args.cell_a), a_name, run_dir,
                                                args.cell_a_hostmap)),
        b_name: load_hostmap(hostmap_candidates(Path(args.cell_b), b_name, run_dir,
                                                args.cell_b_hostmap)),
    }
    hostres = {n: resolve_cell_hosts(cells[n], hostmaps[n]) for n in (a_name, b_name)}
    hosts_played = sorted({h for n in (a_name, b_name)
                           for h in hostres[n]["hosts"]})
    expected_hosts = tuple(dict.fromkeys(
        [EXPECTED_HOSTS[0], conf.get("LAPTOP_HOST") or EXPECTED_HOSTS[1]]))

    Dblock = deck_paired_D(cells[a_name]["by_deck"], cells[b_name]["by_deck"])
    wit = recompute_z_D_witness(cells[a_name]["scored"], cells[b_name]["scored"])
    telem = telemetry(cells[b_name]["scored"])

    try:
        decks_per_cell = int(conf.get("DECKS") or 400)
    except (TypeError, ValueError):
        decks_per_cell = 400
    claim = load_band_claim(band_path)
    preflights = load_preflights(verdicts)
    envs = load_preflight_envs(verdicts)
    rung = {"enabled": True, "B": int(conf.get("TIEARB_B") or 16),
            "J": int(conf.get("TIEARB_J") or 4),
            "mode": conf.get("TIEARB_MODE") or "argmax",
            "salt": conf.get("TIEARB_SALT") or "tiearb2-deploy-v1",
            "eps": float(conf.get("TIEARB_EPS") or 0.0)}

    gates: dict = {}
    for gid, (ok, realized) in {
        "G-BAND": gate_band(cells, claim, decks_per_cell),
        "G-LEAF": gate_leaf(cells, conf["CHAMP_LEAF_HASH"]),
        "G-SPLIT": gate_split(cells, a_name, b_name, hostres),
        "G-COVER": gate_cover(cells, decks_per_cell),
        "G-ARB": gate_arb(cells, a_name, b_name, rung),
        "G-FIRE": gate_fire(telem),
        "G-J13": gate_j13(preflights, verdicts, hosts_played, expected_hosts),
        "G-RULES": gate_rules(cells, conf["RULES_PROFILE"], str(conf["FIX_R9"])),
        "G-DIVERGE": gate_diverge(cells),
        "G-JCZ": gate_jcz(cells, conf, envs, hosts_played),
        "G-TOOL": gate_tool(cells, preflights, repo, envs, hostres, hosts_played),
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
        "two_box": {
            "hosts_played": hosts_played,
            "hosts_expected": list(expected_hosts),
            "workers": {"W_LOCAL": conf.get("W_LOCAL"),
                        "W_LAPTOP": conf.get("W_LAPTOP"),
                        "DECKS_LOCAL": conf.get("DECKS_LOCAL"),
                        "DECKS_LAPTOP": conf.get("DECKS_LAPTOP"),
                        "LAPTOP_HOST": conf.get("LAPTOP_HOST")},
            "per_cell": {n: {"host_source_resolved": hostres[n]["resolved_by"],
                             "hostmap": hostres[n]["hostmap"],
                             "decks_per_host": hostres[n]["hosts"],
                             "per_host": per_host_stats(cells[n], hostres[n])}
                         for n in (a_name, b_name)},
            "jvm_version_by_host_REPORTED": (
                gates["G-JCZ"]["realized"].get("jvm_version_by_host_REPORTED")),
            "jvm_packaging_note": JVM_PACKAGING_NOTE,
            "G-SPLIT": {"PASS": gates["G-SPLIT"]["PASS"],
                        "realized": gates["G-SPLIT"]["realized"]},
            "G-COVER": {"PASS": gates["G-COVER"]["PASS"],
                        "realized": gates["G-COVER"]["realized"]},
            "why_the_split_must_be_identical": (
                "DESIGN §0.1.2: `D` is deck-paired, so a deck that ran on different "
                "boxes in the two cells puts every per-box difference (JVM packaging, "
                "W and hence contention, RAM) INSIDE `margin_B(d) − margin_A(d)`, "
                "arithmetically indistinguishable from the arbiter's effect. With the "
                "split identical, every per-box effect is common to both terms and "
                "CANCELS EXACTLY."),
        },
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

    # ---- item 1b — THE TWO-BOX BLOCK (§0.F.1, DESIGN §0.1) ---------------- #
    tb = v["two_box"]
    ap("## §4.3 item 1b — the TWO-BOX block (owner ruling §0.F.1: "
       "\"make sure its both boxes, w22 and w30 respectively\")")
    ap("")
    ap(f"- hosts that PLAYED (derived from the records): "
       f"`{'`, `'.join(tb['hosts_played']) or '(none resolved)'}` · expected: "
       f"`{'`, `'.join(tb['hosts_expected'])}`")
    w_ = tb["workers"]
    ap(f"- WORKERS.conf: `W_LOCAL={w_.get('W_LOCAL')}` · "
       f"`W_LAPTOP={w_.get('W_LAPTOP')}` · `DECKS_LOCAL={w_.get('DECKS_LOCAL')}` · "
       f"`DECKS_LAPTOP={w_.get('DECKS_LAPTOP')}` · "
       f"`LAPTOP_HOST={w_.get('LAPTOP_HOST')}`")
    ap("")
    ap("| cell | host | deck range played | n games | n decks | "
       "`ms_per_move_champ` (OURS) | worker-s/game |")
    ap("|---|---|---|---|---|---|---|")
    for cname in (a, b):
        blk = tb["per_cell"][cname]
        if not blk["per_host"]:
            ap(f"| `{cname}` | (no host resolved) | — | — | — | — | — |")
        for h, st_ in blk["per_host"].items():
            ap(f"| `{cname}` | `{h}` | "
               f"{st_['deck_seed_min']}..{st_['deck_seed_max']} | "
               f"{st_['n_games']} | {st_['n_decks']} | "
               f"{_f(st_['ms_per_move_champ_OURS'], 1)} ms | "
               f"{_f(st_['worker_s_per_game'], 1)} |")
    ap("")
    for cname in (a, b):
        blk = tb["per_cell"][cname]
        ap(f"- `{cname}` deck→host source: **{blk['host_source_resolved'] or 'NONE'}** "
           f"(sidecar `{(blk['hostmap'] or {}).get('path')}`, parsed="
           f"{(blk['hostmap'] or {}).get('parsed')}, shape="
           f"{(blk['hostmap'] or {}).get('shape')}) · decks per host: "
           f"{blk['decks_per_host']}")
    ap("")
    sp = tb["G-SPLIT"]
    spr = sp["realized"]
    ap(f"- **`G-SPLIT` {'✅ PASS' if sp['PASS'] else '❌ **FAIL**'}** — deck→host "
       f"assignment IDENTICAL across both cells over "
       f"{spr['n_common_decks_compared']} common decks · mismatched decks: "
       f"{spr['mismatched_decks']['n_total']} "
       f"{spr['mismatched_decks']['listed'] if spr['mismatched_decks']['n_total'] else ''} "
       f"· decks with NO host in either cell: "
       f"{spr['decks_with_no_host_in_either_cell']['n_total']} "
       f"{spr['decks_with_no_host_in_either_cell']['listed'] if spr['decks_with_no_host_in_either_cell']['n_total'] else ''}"
       + (f" · unparseable hostmap: {spr['unparseable_hostmap']}"
          if spr.get("unparseable_hostmap") else "")
       + (f" · intra-cell host conflicts: {spr['intra_cell_host_conflicts']}"
          if spr.get("intra_cell_host_conflicts") else ""))
    cv = tb["G-COVER"]
    ap(f"- **`G-COVER` {'✅ PASS' if cv['PASS'] else '❌ **FAIL**'}** — per cell: "
       + " · ".join(
           f"`{n}` dups {d['duplicate_deck_seat_replicate']['n_total']}"
           f"{d['duplicate_deck_seat_replicate']['listed'] if d['duplicate_deck_seat_replicate']['n_total'] else ''}"
           f", out-of-band {d['out_of_band_deck_seeds']['n_total']}"
           f"{d['out_of_band_deck_seeds']['listed'] if d['out_of_band_deck_seeds']['n_total'] else ''}"
           f", decks missing a seating {d['decks_without_both_seatings']['n_total']}"
           f"{d['decks_without_both_seatings']['listed'] if d['decks_without_both_seatings']['n_total'] else ''}"
           for n, d in cv["realized"]["per_cell"].items()))
    ap(f"  - {cv['realized']['reconciliation_with_G_N']}")
    ap("")
    ap("| host | JVM version string (REPORTED — NEVER a branch input) |")
    ap("|---|---|")
    for h, jv in sorted((tb["jvm_version_by_host_REPORTED"] or {}).items()):
        ap(f"| `{h}` | {jv or '(absent)'} |")
    ap("")
    ap(tb["jvm_packaging_note"])
    ap("")
    ap(tb["why_the_split_must_be_identical"])
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
    gt = v["precondition_detail"]["G-TOOL"]
    tool = gt["commit_range"]
    ap("### `G-TOOL` — the four conjuncts (§0.F.2b + §0.F.2c)")
    ap("")
    chi = gt["cross_host_build_identity"]
    ap(f"1. CROSS-HOST build identity (pre-flights vs pre-flights ONLY), **BINDING ON "
       f"`carc_rs_build` (THE BUILD ID) ALONE**: build id by host "
       f"{chi['preflight_build_id_by_host']} · equal = "
       f"{chi['build_id_equal_across_hosts']} · witness present = "
       f"{chi['build_id_witness_present']} · **conjunct ok = {chi['ok']}** — "
       f"**MIXED BUILDS ACROSS BOXES FAIL**")
    ap(f"   - binary sha by host {chi['preflight_binary_sha_by_host']} · equal = "
       f"{chi['binary_sha_equal_across_hosts']} — **NON-BINDING, REPORTED ONLY**")
    ap(f"   - {chi['binary_sha_cross_host_note']}")
    msh = gt["manifest_binary_sha_when_present"]
    ap(f"1b. WITHIN-HOST staleness — `carc_rs_binary_sha` across the two cells, host "
       f"via the hostmap: hosts evaluated {msh.get('hosts_evaluated')} · per host "
       f"{msh['per_host']} · present = {msh['present']} · **ok = {msh['ok']}** "
       f"(a sha that MOVED within a host between cells FAILS)")
    ap(f"2. CROSS-CELL code identity (`our_git_rev` → "
       f"`champion_manifest.code_commit`): equal across cells = "
       f"{gt['cross_cell_code_identity']['equal_across_cells']} · "
       + " · ".join(f"`{n}` = {o['value']} (at `{o['resolved_at']}`, consistent="
                    f"{o['consistent_across_records']})"
                    for n, o in gt["cross_cell_code_identity"]["observed"].items()))
    ap(f"3. the commit range — below. Any build witness present at all: "
       f"{gt['any_build_witness_present']} "
       f"(ABSENT AT EVERY SOURCE STILL FAILS).")
    ap("")
    ap("#### the commit-range delta, on its own line")
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
    ap.add_argument("--cell-a-hostmap", default=None,
                    help="override the CELL A `<cell>.hostmap.json` sidecar "
                         "(G-SPLIT's deck→host witness; default: next to the jsonl)")
    ap.add_argument("--cell-b-hostmap", default=None,
                    help="override the CELL B `<cell>.hostmap.json` sidecar")
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
