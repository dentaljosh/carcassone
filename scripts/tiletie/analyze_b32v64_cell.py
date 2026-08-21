#!/usr/bin/env python3
"""Adjudicate `measurement/tiearb_widening_20260817/b32v64_cell/READ_RULE.md` —
the `B = 32` vs `B = 64` TIE-ARBITER LADDER GAME cell.

Two cells, `CELL_B64` (`B` = 64, a fresh-band replicate of the DEPLOYED
incumbent) and `CELL_B32` (`B` = 32, the cheaper CANDIDATE), `J` = 4, mode
`argmax`, salt `tiearb2-deploy-v1`, `n` = 1,500 deck-paired DECKS each
(3,000 games each) on ONE fresh band `140000000000` and THE SAME decks, at
production budget k8x1376, against the unmodified champion.

    M_64, M_32 = summary.json::paired_mean_margin   ⚠️ READ, NEVER RECOMPUTED
    z_64, z_32 = summary.json::paired_z             secondary, adjudicates nothing
    D          = M_64 − M_32, DECK-PAIRED over the decks completed in BOTH cells
    z_D        = D / se(D)              ⭐ THE PRIMARY, half 1
    CI90(D)    = [D − 1.645·se_D, D + 1.645·se_D]   ⭐ THE PRIMARY, half 2
    f0         = fraction of common decks with D_i EXACTLY 0.0  (G-DIVERGE)

then evaluates §3's THIRTEEN preconditions (which VOID the run), fires §4's
FIVE-branch table in the committed order (FIRST MATCH WINS), and writes
`READOUT_B32V64.{json,md}` carrying every item of the mandatory companion
table §4.3.

⚠️ NOTHING HERE INVENTS AN ESTIMATOR. The paired arithmetic, the two-level
manifest resolution, the phi/arbiter-error blocks and the record loader are
IMPORTED from `analyze_tiearb2_stage2` — Stage 2's adjudicator, whose
conventions this pair inherits by reference. A second convention for `z` would
make the three z's incomparable.

⭐ THE `L-SATURATED` BAR IS NOT A CONSTANT OF THIS MODULE. `TOLERANCE_PTS` and
`EQUIV_SHAPE` are READ, fail-closed, from the committed constants block at the
top of `b32v64_cell/WORKERS.conf`. Changing those two committed lines changes
this adjudicator's behaviour with NO code edit. ⛔ COST IS A BRANCH INPUT
NOWHERE — there is no affordability predicate anywhere in this pair (the N4
`rho_wall` bar was waived by `b64_cell/OWNER_RULING_20260820.md`).

⚠️ THE PAIR IS FROZEN. Where the spec and the buildable disagree, this tool
REPORTS the mismatch (`spec_vs_buildable`) and adjudicates nothing on it.

MODES
    adjudicate      the read-out (default)
    knowngood       ⭐ THE LAUNCH PRECONDITION (DESIGN §12.1 / READ_RULE §0):
                    evaluate every §3 row against the `b64_cell`'s COMPLETED
                    artifacts and classify each PASS / FAIL / N-A(reason). A row
                    that fails a healthy run is a drafting defect.
    nest-witness    emit the §1.3 STRUCTURAL witness, read off the seeding source
                    at HEAD. ⭐ `nest_witness` LIVES HERE (copied, not imported
                    from `analyze_b64_cell`, which is a SPENT run's tool).
    smoke-check     validate a `SMOKE.json` on §9.2's TWO surfaces (RULING 1).
    aggregate-smoke emit `SMOKE.json` from the two smoke cells' own artifacts,
                    by DESIGN §7.1's own cost equation (Σ elapsed_s / n).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# ⚠️ imported, never re-implemented — see the module docstring
import analyze_tiearb2_stage2 as S2  # noqa: E402

CELL_DIR = REPO / "measurement" / "tiearb_widening_20260817" / "b32v64_cell"
#: ⭐ The pair's own committed conf. TWO surfaces read it: the `EQUIV` bar
#: (`TOLERANCE_PTS` / `EQUIV_SHAPE`) and `G-SMOKE`'s production-knobs conjunct
#: (DESIGN §9.2: *"compared field-by-field against `WORKERS.conf`"*). Defined up
#: here because both readers below need it.
WORKERS_CONF = CELL_DIR / "WORKERS.conf"
B64_CELL_DIR = REPO / "measurement" / "tiearb_widening_20260817" / "b64_cell"
DEFAULT_KNOWNGOOD_SHARE = "/mnt/c/carc-shared/tiearb_widening_20260817_b64_cell"

# ---- §1.2 the two cells. HI first: `D = M_64 − M_32` ------------------------ #
CELL_HI = "CELL_B64"          # the DEPLOYED incumbent, replicated on a fresh band
CELL_LO = "CELL_B32"          # the cheaper CANDIDATE
CELLS = (CELL_HI, CELL_LO)
B_BY_CELL = {CELL_HI: 64, CELL_LO: 32}
J_EXPECTED = 4
MODE_EXPECTED = "argmax"
SALT_EXPECTED = "tiearb2-deploy-v1"
EPS_EXPECTED = 0.0
CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"          # G-J1, an EQUALITY gate (INVERTED)

# ---- §2.1 the committed constants — every one of them, in one place --------- #
Z_BAR = 2.0                    # Stage 1 / 1b / Stage 2 Phase B / E-FLAT / W-FLAT
#: ⭐ `1.645` = `z_{0.95}`, the ONE-SIDED 95% critical value (RULING 1, 2026-08-21).
#: ⚠️ SAME NUMBER, DIFFERENT JOB. READ_RULE §4, verbatim: *"AND 1.645 IS THE SAME
#: NUMBER DOING A DIFFERENT JOB: as drafted it was the 90%-two-sided critical
#: value; as ruled it is z_{0.95}, the ONE-SIDED 95% critical value. The
#: arithmetic is identical; the interpretation is not. The read-out must say
#: 'one-sided 95% upper bound', NEVER '90% CI'."*
CI_Z = 1.645
SE_D_COMMITTED = 0.5044        # §6.1 — 0.7133 × sqrt(750/1500). THE SIZING CONSTANT
SE_D_REALIZED_PROJECTION = 0.4570   # §6.1 NON-BINDING sanity line, never sizes
D_FLOOR_2SIGMA = 1.0088        # §6.1, 2 × the committed se(D)
D_FLOOR_2SIGMA_REALIZED_PROJ = 0.9140
ELO_GLOSS = 16.1247            # §6.2 elo per pt/game — DESCRIPTION, adjudicates nothing
BAND_EXPECTED = 140000000000   # §12.2, claimed 2026-08-20
BAND_DECK_MAX = 140000001499

# ---- §3 floors -------------------------------------------------------------- #
N_COMMON_FLOOR = 1200          # DECKS (80% of 1,500)
CELL_GAMES_FLOOR = 2400        # games (the SAME 80% bar: 2,400 games IS 1,200 decks)
CELL_GAMES_PLANNED = 3000
CELL_DECKS_PLANNED = 1500
PHI_EFFECTIVE_FLOOR = 1.0      # G-FIRE
DIVERGE_FLOOR = 0.10           # G-DIVERGE, on 1 − f0
DIVERGE_EXPECTED = 0.98        # §8.2, RE-DERIVED at the 32→64 rung
DIVERGE_ANOMALY_BAR = 0.95     # ⚠️ below this PASSES and is an ANOMALY
FAILED_RATE_BAR = 0.02         # G-FAILED clause 1
KNOWN_FAILURE_CLASS = "WindowTruncationError"

# ---- §4/§5/§7 cost + description constants — printed, GRADING NOTHING ------- #
RHO_WALL_16 = 0.6224           # Phase A, MEASURED
RHO_WALL_32 = 1.2449           # ×2, exact linearity in B
RHO_WALL_64 = 2.4897           # ×4 — the DEPLOYED rung
RHO_WALL_128 = 4.9794          # ×8 — printed BESIDE any B = 128 language (§4.1 #3)
N4_BAR = 1.20                  # ⛔ WAIVED AND RETIRED — history, never a test
RHO_PHONE_32 = (11.04, 11.95)  # NOT SOLVED — a THIRD currency
RHO_PHONE_64 = (22.08, 23.90)
CHAMP_BASELINE_S_PER_MOVE = 1.8
SWAPDOWN_PRIZE_S_PER_MOVE = 2.24    # §4.1, ≈ 1.8 × (3.4897 − 2.2449)
SWAPDOWN_PRIZE_PCT = -35.7
WORKER_S_COMMITTED = {CELL_HI: 928.025,     # §7.1 MEASURED on the b64 cell
                      CELL_LO: 579.389}     # §7.2 PROJECTED — graded NOWHERE
MS_RATIO_PREDICTED = {CELL_HI: 6.608, CELL_LO: 3.74}    # §9.4
PHI_COMMITTED = 17.4810        # §7.2 (mean of the b64 cell's two realized)
PHI_PRIOR_OFFLINE = 22.96
PHI_B64CELL_REALIZED = (17.5533, 17.4087)
WALL_COMMITTED_H = 35.33       # §7.5
EFFECTIVE_POOL_WORKERS = 35.560     # §7.5 MEASURED, not the 46.5 capacity model
OCCUPANCY_DERATE = 1.4623      # §7.5 MEASURED (the b64 cell committed 1.190 — a miss)
WORKER_H_COMMITTED = 1256.2    # §7.5
EFFECT_BRACKET = (0.0399, 0.1555)   # §5.2 — a WIDTH, never a CENTRE
OFFLINE_ARB = {32: 0.1942, 64: 0.2015}      # pts/tied ply, MEASURED (shared_run_r4)
OFFLINE_DELTA_32_64 = 0.0073
OFFLINE_RATIO_64_OVER_32 = 1.038
SATURATED_WINDOW_COMMITTED = 0.1003     # ⚠️ the UPPER EDGE — shape-INVARIANT
SATURATED_WINDOW_REALIZED_PROJ = 0.1782

# --------------------------------------------------------------------------- #
# ⭐ THE POWER CONSTANTS ARE SHAPE-KEYED — READ_RULE §4.0, RECOMPUTED FOR THE   #
# ONE-SIDED SHAPE (RULING 1, 2026-08-21).                                      #
# --------------------------------------------------------------------------- #
#: ⛔ WHY KEYED AND NOT REPLACED. `EQUIV_SHAPE` is a COMMITTED, CHANGEABLE line
#: in `WORKERS.conf`; a single hard-coded power figure would silently describe
#: the wrong shape the moment that line moved — which is exactly the defect
#: RULING 1 left behind in the drafted adjudicator. Every figure below is the
#: pair's own, per shape, and the shape SELECTS which set is printed.
#:
#: ⚠️ `raw` is the one-sided test's own probability; `EFFECTIVE` subtracts the
#: mass `L-REVERSED` takes first by FIRST-MATCH-WINS, and **`EFFECTIVE` is the
#: number that governs what this read-out can say** (READ_RULE §4.0).
POWER_BY_SHAPE = {
    "one_sided": {
        "shape": "one_sided",
        "modal_pre_run_expectation": "L-SATURATED",
        "modal_note": ("at a true D = 0 the EFFECTIVE L-SATURATED probability is "
                       "0.556 > 0.444 ⇒ L-SATURATED is the modal pre-run "
                       "expectation under the ruled shape"),
        # true D = 0 — the rungs equal
        "power_raw_committed": 0.5788,
        "power_l_reversed_mass_committed": 0.0228,
        "power_at_true_D_zero_committed": 0.5560,            # EFFECTIVE
        "power_raw_realized_proj": 0.6517,
        "power_l_reversed_mass_realized_proj": 0.0228,
        "power_at_true_D_zero_realized_proj": 0.6290,        # EFFECTIVE
        # true D = +0.0399 — the offline bracket FLOOR
        "power_at_bracket_floor_committed": 0.5288,
        "power_at_bracket_floor_realized_proj": 0.6005,
        # true D = +0.1555 — the offline bracket TOP
        "power_at_bracket_top_committed": 0.4459,
        "power_at_bracket_top_realized_proj": 0.5102,
        "n_for_80pct_committed": 2728,       # decks/cell (5,456 games)
        "n_for_80pct_realized": 2240,        # decks/cell (4,480 games)
        "n_for_80pct_note": ("⚠️ those are RAW one-sided figures "
                             "(se_D <= 0.93/(1.645+0.8416) = 0.37400); the "
                             "EFFECTIVE power at that n is ~0.777, because "
                             "L-REVERSED still takes ~2.3% of the lower tail "
                             "first"),
        "statement": (
            "⇒ IF B = 32 IS EXACTLY AS GOOD AS B = 64, THIS CELL NOW HAS A ~56% "
            "CHANCE (~63% AT THE REALIZED DISPERSION) OF BEING ABLE TO SAY SO — "
            "up from ~16% (~30%) under the drafted two-sided shape, at the same "
            "tolerance, the same n, and no extra spend. ⚠️ It is still not a "
            "well-powered test: ~44% of the equal-rungs world, and ~55% of the "
            "bracket-top world, still reads L-AMBIGUOUS. That is a declared "
            "property of the owner-funded design, not a failure of it. ⛔ No "
            "read-out may present L-AMBIGUOUS as evidence of a difference."),
        "fire_region": (
            "the predicate fires on D̂ <= 0.930 − 1.645*se_D (committed +0.1003, "
            "realized-proj +0.1782) and is UNBOUNDED BELOW — but branch 2 "
            "pre-empts at D̂ <= −1.0088 (realized-proj −0.9140), so the EFFECTIVE "
            "region is (−1.0088, +0.1003]."),
    },
    "two_sided": {
        "shape": "two_sided",
        "modal_pre_run_expectation": "L-AMBIGUOUS",
        "modal_note": ("under the DRAFTED two-sided shape L-SATURATED fires with "
                       "probability 0.158 at a true D = 0, so L-AMBIGUOUS is "
                       "modal"),
        "power_raw_committed": 0.158,
        "power_l_reversed_mass_committed": 0.0,
        "power_at_true_D_zero_committed": 0.158,
        "power_raw_realized_proj": 0.304,
        "power_l_reversed_mass_realized_proj": 0.0,
        "power_at_true_D_zero_realized_proj": 0.304,
        # ⚠️ X2: the pair never quoted a bracket-FLOOR figure for the drafted
        # shape, so there is nothing to carry. Said explicitly rather than left
        # as a bare `None` a reader would mistake for a missing computation.
        "power_at_bracket_floor_committed": "not quoted by the pair (two_sided)",
        "power_at_bracket_floor_realized_proj":
            "not quoted by the pair (two_sided)",
        "power_at_bracket_top_committed": 0.150,
        "power_at_bracket_top_realized_proj": 0.287,
        "n_for_80pct_committed": 3779,
        "n_for_80pct_realized": 3102,
        "n_for_80pct_note": ("two-sided equivalence power; "
                             "se <= 0.93/(1.645+1.2816) = 0.31778"),
        "statement": (
            "⛔⛔ EVEN IF B = 32 IS EXACTLY AS GOOD AS B = 64, THIS CELL HAS A "
            "~16% CHANCE (~30% AT THE REALIZED DISPERSION) OF BEING ABLE TO SAY "
            "SO. The other ~70–84% of that world reads L-AMBIGUOUS. This is a "
            "DECLARED PROPERTY of the design, not a failure of it. ⛔ No read-out "
            "may present L-AMBIGUOUS as evidence of a difference."),
        "fire_region": (
            "the predicate fires on |D̂| + 1.645*se_D <= 0.93, i.e. a symmetric "
            "window about zero; the L-RISING/L-SATURATED overlap is empty for "
            "every se_D > 0.93/3.645 = 0.2551."),
    },
}


def power_constants(equiv_cfg: dict) -> dict:
    """The pair's §4.0 power figures FOR THE COMMITTED SHAPE. ⛔ Fail-closed: an
    unknown shape is a REFUSAL, never a silent fallback to the drafted set."""
    shape = equiv_cfg["equiv_shape"]
    if shape not in POWER_BY_SHAPE:
        raise SystemExit(f"REFUSING: no §4.0 power constants for EQUIV_SHAPE="
                         f"{shape!r} — a power figure describing the WRONG shape "
                         f"is the defect RULING 1 left behind, and it is not "
                         f"repeated by defaulting.")
    return POWER_BY_SHAPE[shape]
B64CELL_REALIZED = {"elo_wide": 63.9457, "elo_narrow": 36.2644,
                    "D": 1.7167, "se_D": 0.6463, "rho": 0.1237,
                    "one_minus_f0": 0.9840, "band": 139000000000}

SMOKE_HALT_MULTIPLE = 1.50     # §9.3, one-sided
SMOKE_HALT_BAR = SMOKE_HALT_MULTIPLE * WORKER_S_COMMITTED[CELL_HI]   # 1392.0375
SMOKE_BAND = 900000400000      # §9.1 THROWAWAY — never claimed, never read for outcome

#: ⭐ THE §9.3 HALT DECISION RECORD — the `[post-smoke]` address DESIGN §3 names
#: ("`SMOKE.json` (all cost keys), **the HALT decision record**") and which
#: nothing used to write. It lives in the CELL DIR, beside the launcher that
#: reads it, because the launcher must be able to REFUSE a real-cell launch
#: without reaching across to the share.
#: ⛔ THERE IS NO OVERRIDE FLAG. A HALT holds for the owner: DESIGN §9.3's only
#: permitted responses are *stop* or *the owner re-funds at the realized cost*,
#: and neither is a switch the executor flips.
SMOKE_HALT_RECORD = "SMOKE_HALT.json"

#: R6 — `G-SMOKE`'s FIRST conjunct, made implementable. DESIGN §9.2's table fixes
#: the SHAPE of `production_knobs` and this is that shape, field for field:
#: `{k_dets, sims, exact_k, rules_profile, cand_leaf_hash, c_puct, tau_p,
#: leaf_quantize, final_select, opponent, backend, cand_tiearb_per_cell}` —
#: *"compared field-by-field against WORKERS.conf; any mismatch fires."*
PRODUCTION_KNOB_FIELDS = ("k_dets", "sims", "exact_k", "rules_profile",
                          "cand_leaf_hash", "c_puct", "tau_p", "leaf_quantize",
                          "final_select", "opponent", "backend",
                          "cand_tiearb_per_cell")
#: The four knobs whose committed value lives in `WORKERS.conf` (the launcher
#: sources it, so the conf IS the comparison authority DESIGN §9.2 names).
PRODUCTION_KNOBS_FROM_CONF = {"k_dets": "K_DETS", "sims": "SIMS",
                              "exact_k": "EXACT_K",
                              "rules_profile": "RULES_PROFILE",
                              "cand_leaf_hash": "CHAMP_LEAF_HASH"}
#: The rest are DESIGN §2's committed argv constants — `run_cells.sh` passes them
#: literally and `WORKERS.conf` does not carry them.
PRODUCTION_KNOBS_FROM_DESIGN = {"c_puct": 1.5, "tau_p": 5.0,
                                "leaf_quantize": "float",
                                "final_select": "visits",
                                "opponent": "fair-champion", "backend": "rust"}
_CONF_INT_KNOBS = ("k_dets", "sims", "exact_k")


def expected_production_knobs(workers_conf=WORKERS_CONF) -> dict:
    """DESIGN §9.2's *"compared field-by-field against `WORKERS.conf`"*, made
    literal: the committed knob values are READ FROM THE CONF, not typed here.

    ⛔ Fail-closed: a conf missing any of the five knob lines is a REFUSAL. The
    remaining knobs are DESIGN §2's argv constants, named with their source so a
    reader can see which authority each field answers to."""
    conf = parse_workers_conf(workers_conf)
    missing = [k for k in PRODUCTION_KNOBS_FROM_CONF.values() if k not in conf]
    if missing:
        raise SystemExit(f"REFUSING: {Path(workers_conf)} carries no "
                         f"{', '.join(missing)} — G-SMOKE's production-knobs "
                         f"conjunct compares field-by-field AGAINST THE CONF "
                         f"(DESIGN §9.2) and has no default.")
    want = {}
    for field, key in PRODUCTION_KNOBS_FROM_CONF.items():
        v = conf[key]
        want[field] = int(v) if field in _CONF_INT_KNOBS else v
    want.update(PRODUCTION_KNOBS_FROM_DESIGN)
    want["cand_tiearb_per_cell"] = {
        CELL_LO: {"enabled": True, "B": int(conf.get("TIEARB_B_LO", B_BY_CELL[CELL_LO])),
                  "J": J_EXPECTED, "mode": MODE_EXPECTED, "salt": SALT_EXPECTED,
                  "eps": EPS_EXPECTED},
        CELL_HI: {"enabled": True, "B": int(conf.get("TIEARB_B_HI", B_BY_CELL[CELL_HI])),
                  "J": J_EXPECTED, "mode": MODE_EXPECTED, "salt": SALT_EXPECTED,
                  "eps": EPS_EXPECTED},
    }
    return want


def _production_knobs_from_manifest(man: dict) -> dict:
    """DESIGN §9.2's `production_knobs` — *"a dict echo of the §2 knobs AS THE
    SMOKE RESOLVED THEM"* — read off a real cell manifest at the addresses
    `eval_fair_puct` actually writes them.

    ⚠️ OBSERVED, NEVER INJECTED. Every value is lifted from the manifest the
    harness wrote; none is a constant this emitter supplies. A conjunct compared
    against an emitter's own injected constant is a pass-always gate, which is the
    single most-repeated defect in this campaign's catalog. `None` where the
    manifest does not carry the address — and `None` MISMATCHES, so absence
    fires."""
    cfg = (man or {}).get("config") or {}
    champ = cfg.get("champion") or {}
    rules = (man or {}).get("rules_profile")
    leaf_hash, _where = S2._manifest_get(man or {}, "cand_leaf_hash")
    return {
        "k_dets": champ.get("k_dets"),
        "sims": champ.get("sims_per_det"),
        "exact_k": (cfg.get("endgame") or {}).get("exact_k"),
        "rules_profile": (rules.get("name") if isinstance(rules, dict) else rules),
        "cand_leaf_hash": leaf_hash,
        "c_puct": champ.get("c_puct"),
        "tau_p": champ.get("tau_p"),
        "leaf_quantize": champ.get("leaf_quantize"),
        "final_select": champ.get("final_select"),
        "opponent": (cfg.get("opponent") or {}).get("mode"),
        "backend": (cfg.get("backend") or {}).get("name"),
    }

# --------------------------------------------------------------------------- #
# ⭐ THE COMMITTED CONSTANTS BLOCK — READ FROM `WORKERS.conf`, NOT FROM HERE.   #
# --------------------------------------------------------------------------- #
#: The two committed lines this adjudicator reads out of the pair's own conf.
#: ⛔ FAIL-CLOSED, with NO coerced default: an absent, unparseable or
#: out-of-vocabulary value is a REFUSAL. A missing bar is a drafting defect, and
#: silently substituting 0.93 / `two_sided` would make the committed block
#: decorative — the exact "pass-always gate (constant input)" disease §13.1
#: audits for.
EQUIV_SHAPES = ("two_sided", "one_sided")
EQUIV_SHAPE_TEXT = {
    "two_sided": ("|D| + 1.645*se_D <= TOLERANCE_PTS  —  two-sided EQUIVALENCE: "
                  "CI90(D) CONTAINED IN [-TOL, +TOL]. ⚠️ THE DRAFTED shape, "
                  "SUPERSEDED by RULING 1 (2026-08-21); retained because the "
                  "committed block is changeable and a shape the tool cannot "
                  "describe is a shape it must refuse, not mis-label."),
    "one_sided": ("UB95(D) = D + 1.645*se_D <= TOLERANCE_PTS  —  ONE-SIDED "
                  "NON-INFERIORITY at 95%: the ONE-SIDED 95% UPPER BOUND ON THE "
                  "COST is below the tolerance. ⚠️ 1.645 here is z_{0.95}, the "
                  "ONE-SIDED 95% critical value — the read-out must say "
                  "'one-sided 95% upper bound', NEVER '90% CI' (READ_RULE §4). "
                  "⚠️ The |·| is dropped and the negative arm is governed by "
                  "BRANCH ORDER, not by the predicate: L-REVERSED (z_D <= -2.0) "
                  "is branch #2 and pre-empts L-SATURATED (#4) by "
                  "FIRST-MATCH-WINS (§4.4)."),
}
UB95_LABEL = "ONE-SIDED 95% UPPER BOUND ON THE COST"
CI90_LABEL = "two-sided 90% interval — REPORTED FOR CONTEXT, adjudicates nothing"
_CONF_LINE_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$')


def parse_workers_conf(path=WORKERS_CONF) -> dict:
    """Every `KEY=VALUE` line of a `WORKERS.conf`, as a plain dict of strings.

    ⚠️ Deliberately NOT a shell evaluation: the conf is sourced by bash for the
    launchers, but an adjudicator that ran it would execute whatever the file
    contains. Comments, blank lines and `export` prefixes are ignored; inline
    trailing comments are stripped only OUTSIDE quotes."""
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"REFUSING: WORKERS.conf absent at {p} — the committed "
                         f"constants block (TOLERANCE_PTS / EQUIV_SHAPE) is READ "
                         f"from it and there is NO default (fail-closed).")
    out = {}
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        m = _CONF_LINE_RE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if val[:1] in ("'", '"') and val[-1:] == val[:1] and len(val) >= 2:
            val = val[1:-1]
        else:
            val = val.split("#", 1)[0].strip()
        out[key] = val
    return out


def load_equiv_config(path=WORKERS_CONF) -> dict:
    """⭐ `TOLERANCE_PTS` and `EQUIV_SHAPE`, read from the pair's own committed
    block. Changing those two lines changes this adjudicator with NO code edit.

    ⛔ FAIL-CLOSED on all four failure modes, each named separately so a reader
    sees WHICH one fired: absent file, absent key, unparseable tolerance, and a
    shape outside the supported vocabulary."""
    conf = parse_workers_conf(path)
    missing = [k for k in ("TOLERANCE_PTS", "EQUIV_SHAPE") if k not in conf]
    if missing:
        raise SystemExit(
            f"REFUSING: {Path(path)} carries no {', '.join(missing)} — READ_RULE "
            f"§4's EQUIV predicate is READ from the committed constants block and "
            f"there is NO coerced default (fail-closed).")
    raw_tol = conf["TOLERANCE_PTS"]
    try:
        tol = float(raw_tol)
    except (TypeError, ValueError):
        raise SystemExit(f"REFUSING: TOLERANCE_PTS={raw_tol!r} in {Path(path)} is "
                         f"not a number.")
    if not (tol > 0) or tol != tol or tol in (float("inf"), float("-inf")):
        raise SystemExit(f"REFUSING: TOLERANCE_PTS={raw_tol!r} is not a finite "
                         f"positive pts/game tolerance.")
    shape = conf["EQUIV_SHAPE"]
    if shape not in EQUIV_SHAPES:
        raise SystemExit(
            f"REFUSING: EQUIV_SHAPE={shape!r} in {Path(path)} is outside the "
            f"supported vocabulary {list(EQUIV_SHAPES)}. An unsupported shape is a "
            f"REFUSAL, never a silent fallback to two_sided.")
    return {
        "tolerance_pts": tol, "equiv_shape": shape,
        "ci_z": CI_Z,
        "predicate": EQUIV_SHAPE_TEXT[shape],
        "source": str(Path(path)),
        "supported_shapes": list(EQUIV_SHAPES),
        "committed_block": ("READ_RULE §4 / WORKERS.conf's top-of-file committed "
                            "constants block. ⛔ Changing those two lines changes "
                            "this adjudicator's behaviour with NO code edit; the "
                            "adjudicator carries NO default for either."),
        "elo_gloss_non_binding": (
            f"{tol} pts/game x {ELO_GLOSS} elo per pt/game = "
            f"{tol * ELO_GLOSS:+.2f} elo — the gloss is a DESCRIPTION and every "
            f"branch condition is written in pts/game, never in elo."),
    }


def equiv_predicate(D, se_D, equiv_cfg: dict) -> dict:
    """READ_RULE §4's `EQUIV`, in whichever committed shape the conf names.

    ⛔ NEVER a coerced default: `None`/NaN/inf inputs return `EQUIV = False` WITH
    the reason named — but they cannot reach a branch, because `G-STAT` fires on
    them first in §3."""
    tol, shape = equiv_cfg["tolerance_pts"], equiv_cfg["equiv_shape"]
    detail = {"equiv_shape": shape, "tolerance_pts": tol, "ci_z": CI_Z,
              "predicate": EQUIV_SHAPE_TEXT[shape], "D": D, "se_D": se_D,
              "source": equiv_cfg.get("source")}
    if not _finite(D) or not _finite(se_D):
        return dict(detail, EQUIV=False, statistic=None,
                    why="D or se_D is absent / NaN / infinite — EQUIV is FALSE "
                        "(fail-closed). ⚠️ G-STAT fires on this in §3 BEFORE any "
                        "branch comparison is taken.")
    stat = (abs(D) if shape == "two_sided" else D) + CI_Z * se_D
    name = "|D| + 1.645*se_D" if shape == "two_sided" else "UB95(D)"
    return dict(detail, EQUIV=bool(stat <= tol), statistic=stat,
                statistic_name=name,
                UB95=ub95(D, se_D), UB95_label=UB95_LABEL,
                why=(f"{name} = {stat:+.6f} "
                     f"{'<=' if stat <= tol else '>'} {tol}"))


def ub95(D, se_D):
    """⭐ `UB95(D) = D + 1.645·se_D` — **THE PRIMARY, half 2** (READ_RULE §2).

    The **ONE-SIDED 95% UPPER BOUND ON THE COST**. ⛔ It must be labelled that and
    **NEVER "90% CI"** (READ_RULE §4, §4.3 item 2). `None` on absent/non-finite
    inputs — never a half-formed bound.

    ⚠️ It is computed and reported on BOTH shapes, because §2 lists it as a
    committed quantity unconditionally; under `two_sided` it is reported while the
    branch is decided on `|D| + 1.645·se_D` instead."""
    if not _finite(D) or not _finite(se_D):
        return None
    return D + CI_Z * se_D


def _finite(x) -> bool:
    """True iff `x` is a real, finite number. ⚠️ `bool` is rejected on purpose:
    a boolean reaching a statistic slot is a plumbing bug, not a datum."""
    if x is None or isinstance(x, bool):
        return False
    if not isinstance(x, (int, float)):
        return False
    return x == x and x not in (float("inf"), float("-inf"))


def _f(x, spec="+.4f"):
    try:
        return format(float(x), spec)
    except (TypeError, ValueError):
        return "n/a"


# --------------------------------------------------------------------------- #
# §9.2 — the two surfaces (RULING 1, carried VERBATIM)                         #
# --------------------------------------------------------------------------- #
#: §9.2's FAIL-CLOSED EMITTER whitelist. An unlisted key is a REFUSAL at WRITE
#: time. ⚠️ It is NOT the gate's surface — see `smoke_outcome_scan`.
SMOKE_WHITELIST = frozenset({
    "wall_secs", "secs_per_game", "worker_secs_per_game", "games_per_sec",
    "workers", "champ_prefix_ms_per_move", "rung_ms_per_move",
    "ms_ratio_cand_over_opp", "tiearb_phi", "tiearb_fired_plies_total",
    "tiearb_tile_plies_total", "tiearb_fire_rate_on_tile_plies",
    "tiearb_pickchange_rate", "tiearb_mean_arms", "tiearb_playouts_total",
    "tiearb_secs_per_game", "tiearb_errors_total", "tiearb_first_error",
    "tiearb_partial_argmax_total", "cand_leaf_hash", "carc_rs_build",
    "carc_rs_binary_sha", "rust_toolchain", "n_failed",
    # §9.1's condition of acceptance — the throwaway band declares itself
    "band_seed_start", "band_tier", "band_registry_claimed",
    # ⭐ R6: the two STRUCTURAL keys that make `G-SMOKE`'s FIRST conjunct — *"the
    # smoke did not run at PRODUCTION KNOBS before game 1"* — implementable at
    # all. Without them the conjunct reads an address nothing writes, which is
    # the disease-catalog's own "gate reading an address nothing writes".
    # ⚠️ Both are OBSERVATIONS lifted from the smoke cells' real manifests, never
    # constants this emitter injects: a gate that checks an emitter's own
    # injected constant is a pass-always gate.
    "production_knobs", "smoke_utc",
})
#: ⛔ THE OUTCOME KEYS §9.2 forbids outright. ⚠️ `f0` is MARGIN-DERIVED and is
#: forbidden at the smoke — named so a well-meaning implementation cannot add it
#: "because it's just a count".
SMOKE_FORBIDDEN_EXAMPLES = ("paired_mean_margin", "paired_z", "elo", "winrate",
                            "W", "D", "L", "f0", "z_D", "per_deck_margin")
SMOKE_OUTCOME_FORBIDDEN = frozenset({
    "paired_mean_margin", "paired_z", "elo", "elo_sig_1sigma", "winrate",
    "winrate_z", "wr", "wr_z", "W", "D", "L", "f0", "z_D", "se_D",
    "per_deck_margin", "by_deck", "margins", "diff",
})
#: A key whose NAME says outcome even under a house suffix. Matched on the whole
#: key, so a counts key that merely contains "margin" as a word-part is not swept
#: up by accident.
SMOKE_OUTCOME_RE = re.compile(
    r"(?:^|_)(margin|elo|winrate|wr_z|paired_z|z_D|f0)(?:$|_)", re.I)


def smoke_whitelist_check(smoke: dict) -> dict:
    """§9.2 sentence 2 — the EMITTER surface. COUNTS-AND-COST ONLY, FAIL-CLOSED.

    ⚠️ This is the WRITE contract, NOT the `G-SMOKE` row. Applying it as the row
    fails a known-good smoke (RULING 1)."""
    keys = sorted(k for k in (smoke or {}) if not str(k).startswith("_"))
    forbidden = [k for k in keys if k not in SMOKE_WHITELIST]
    return {"ok": not forbidden, "keys": keys, "forbidden_present": forbidden,
            "whitelist": sorted(SMOKE_WHITELIST),
            "forbidden_examples": list(SMOKE_FORBIDDEN_EXAMPLES),
            "surface": "EMITTER (write) — §9.2 sentence 2",
            "mode": "FAIL-CLOSED: an unlisted key is a REFUSAL, not a warning",
            "f0_note": "f0 is MARGIN-DERIVED and is FORBIDDEN at the smoke"}


def smoke_outcome_scan(doc, path="") -> list:
    """§3's `G-SMOKE` row — the GATE surface. Every FORBIDDEN OUTCOME key at ANY
    depth, and NOTHING else.

    ⭐ RULING 1, carried VERBATIM: *"§9.2 defines TWO surfaces. The emitter
    whitelist is fail-closed on unlisted keys and governs what SMOKE.json may
    contain. The G-SMOKE row fires only on forbidden OUTCOME keys, at any depth.
    Structural keys are expected and never fire the row. A reading that applies
    the emitter whitelist to the row fails a known-good smoke."*
    """
    hits = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            here = f"{path}.{k}" if path else str(k)
            if str(k) in SMOKE_OUTCOME_FORBIDDEN or SMOKE_OUTCOME_RE.search(str(k)):
                hits.append(here)
            hits += smoke_outcome_scan(v, here)
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            hits += smoke_outcome_scan(v, f"{path}[{i}]")
    return hits


#: ⭐ THE COST DEFINITION, TAKEN FROM THE PAIR AND NOT CHOSEN HERE.
#: DESIGN §7.1 states it as an equation over the artifacts:
#:     sum over seed*.json of elapsed_s / 1500 = 928.0251 worker-s/game  MEASURED
#: so `worker_secs_per_game` is Σ(per-game `elapsed_s`) / n — the NUMERATOR'S OWN
#: CURRENCY, measured in-cell and contended.
#: ⛔ NEVER `wall × W / n`: that is the house's standing prohibition, and it is
#: also the exact error §9.3 decomposes — Stage 2's ~2× cost miss was a currency
#: error (a sequential `t_champ` divided into a contended per-move wall), and
#: §9.3's whole justification for the 1.50 bar is that §7.2 "never divides by a
#: sequential quantity". Under `--shared-claim` two boxes overlap in wall time,
#: so wall × W would be wrong here twice over.
WORKER_SECS_DEFINITION = (
    "worker_secs_per_game = SUM(seed*.json::elapsed_s) / n — DESIGN §7.1's own "
    "equation ('sum over seed*.json of elapsed_s / 1500 => 928.0251 worker-s per "
    "game'). NEVER wall x W / n: the house forbids costing from wall clock, and "
    "§9.3 names that very substitution as the currency error behind Stage 2's "
    "cost miss."
)


# --------------------------------------------------------------------------- #
# §1.3 — the STRUCTURAL nest witness. ⭐ IT LIVES HERE.                         #
# --------------------------------------------------------------------------- #
#: The four seeding sites §1.3 rests on. The nesting is true IFF none of them
#: takes `B` — the seed is a pure function of `j`.
TIEARB_RS = "rust/carc/carc-core/src/tiearb.rs"
NEST_SITES = (
    ("world_seed", r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*&js\]\)'),
    ("playout_seed",
     r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*&js,\s*"playout"\]\)'),
    ("build_arms_cap",
     r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*"cap"\]\)'),
    ("select_stream",
     r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*"select"\]\)'),
)


def nest_witness(repo=REPO) -> dict:
    """⭐ `G-NEST`'s STRUCTURAL witness, read off the seeding source at HEAD.

    §1.3: `world_seed(j) = seed_i64([salt, digest, ply, j])` and
    `playout_seed(j) = …, j, "playout"`, with `j` running `0..B` — **the seed is a
    pure function of `j`, never of `B`.** ⇒ `B` = 64's worlds `0..31` are
    byte-identical to `B` = 32's entire world set, and the `build_arms` cap draw
    and the selection stream likewise do not depend on `B`.

    ⚠️ Without nesting, `CELL_B64` and `CELL_B32` are two unrelated draws and the
    whole "refinement" framing is void — which is why this is a precondition, not
    a rider.

    ⭐ CARRIED HERE, COPIED AND NOT IMPORTED. `b32v64_cell/gate_nest.py` used to
    import this from `scripts/tiletie/analyze_b64_cell.py` — a live dependency on
    a SPENT run's tooling, reported as a cross-cell dependency by DESIGN §13.2
    item 7, whose own stated resolution is *"when analyze_b32v64_cell.py is built
    it should expose the same function rather than restate the regexes, and the
    import should move there."* Discharged. `analyze_b64_cell.py` is UNTOUCHED.

    ⚠️ The claim asserted is B-INDEPENDENT: it is a property of the RUST SOURCE
    (the four seeding sites are pure functions of `j` with no `B` term), not of
    any `(B_lo, B_hi)` pair, so it transfers between rungs unchanged. The pinned
    per-position BEHAVIOURAL half is `gate_nest.py`'s, not this function's.
    """
    src_path = Path(repo) / TIEARB_RS
    out = {"source": TIEARB_RS, "present": src_path.is_file(), "sites": {},
           "witness": False}
    if not src_path.is_file():
        out["why"] = f"{TIEARB_RS} absent — the witness cannot be taken"
        return out
    src = src_path.read_text()
    ok = True
    for name, pattern in NEST_SITES:
        m = re.search(pattern, src)
        found = bool(m)
        expr = m.group(0) if m else None
        # the load-bearing property: the seed expression takes NO `B` term
        b_free = bool(found and not re.search(r'\bB\b|\bb_worlds\b|&b\b', expr))
        out["sites"][name] = {"found": found, "expression": expr,
                              "b_free": b_free}
        ok &= (found and b_free)
    out["witness"] = bool(ok)
    out["why"] = ("every seeding site is a pure function of j (no B term) ⇒ the "
                  "world sets NEST" if ok else
                  "a seeding site is absent or takes B — the nesting does NOT hold")
    out["scope"] = ("SOURCE-LEVEL witness at HEAD over the four seeding sites. "
                    "The pair's GATE_NEST.json additionally records the pinned "
                    "position/ply/salt byte-identity run at 32 ⊂ 64; this "
                    "function emits the STRUCTURAL half and names the "
                    "behavioural half.")
    out["b_independent"] = (
        "the claim is about the SOURCE — the four seeding sites are pure "
        "functions of j with no B term — so it is not a claim about any "
        "(B_lo, B_hi) pair and transfers between rungs unchanged.")
    return out


# --------------------------------------------------------------------------- #
# §3 — the THIRTEEN preconditions. Each a pure function so a test can fail      #
# exactly one. ⛔ EVERY gate resolves and prints; none is short-circuited.       #
# --------------------------------------------------------------------------- #
GATE_SCOPE = {
    "G-J1": "[PER-CELL]", "G-J4": "[PER-CELL]", "G-J13": "[PER-CELL]",
    "G-NEST": "[RUN]", "G-FIRE": "[PER-CELL]", "G-DIVERGE": "[RUN]",
    "G-BAND": "[RUN]", "G-N": "[RUN]+[PER-CELL]", "G-FAILED": "[RUN]+[PER-CELL]",
    "G-TOOL": "[RUN]", "G-PLY": "[PER-CELL]", "G-STAT": "[RUN]",
    "G-SMOKE": "[RUN]",
}
GATE_MARKER = {
    "G-J1": "[post-cells]", "G-J4": "[post-cells]", "G-J13": "[pre-run]",
    "G-NEST": "[pre-run]", "G-FIRE": "[post-cells]", "G-DIVERGE": "[post-cells]",
    "G-BAND": "[pre-run]+[post-cells]", "G-N": "[post-cells]",
    "G-FAILED": "[post-cells]", "G-TOOL": "[pre-run]+[post-cells]",
    "G-PLY": "[post-cells]", "G-STAT": "[post-cells]", "G-SMOKE": "[post-smoke]",
}
#: ⚠️ `[PER-CELL]` here is deliberately NOT `rung3_r5`'s "the other stratum
#: remains readable" semantics: this run has no per-cell estimand — the primary
#: IS a contrast — so a single-cell failure fails the RUN. The marker records
#: WHERE the failure was, not that anything survives it (READ_RULE §3).
PER_CELL_SEMANTICS = (
    "[PER-CELL] records WHERE a failure was, NOT that anything survives it: D is "
    "a two-cell statistic and there is NO single-cell reading of this design, so "
    "a single-cell failure fails the RUN (READ_RULE §3).")


def gate_j1(cells: dict) -> tuple:
    """`G-J1` `[PER-CELL]` — INVERTED: a DIFFERENCE from the champion's leaf hash
    is an ABORT, not a finding. ABSENT under BOTH levels also fails."""
    obs, ok = {}, True
    for c in CELLS:
        h, where = S2._manifest_get((cells.get(c) or {}).get("manifest", {}),
                                    "cand_leaf_hash")
        obs[c] = {"cand_leaf_hash": h, "resolved_at": where,
                  "ok": bool(h == CHAMP_LEAF_HASH)}
        ok &= obs[c]["ok"]
    return bool(ok), {"expected_equal": CHAMP_LEAF_HASH, "observed": obs,
                      "read_at": "top level, then config.* (two-level, §2.1)",
                      "semantics": "EQUALITY gate — a difference ABORTS; ABSENT "
                                   "under both levels also fails"}


def gate_j4(cells: dict, b_by_cell=None) -> tuple:
    """`G-J4` `[PER-CELL]` — the resolved knob is EXACTLY the deployed shape with
    only `B` differing, and the cell's realized `tiearb_B` is the SINGLETON `[B]`.

    ⚠️ A mixed-`B` cell is a VOID, not a finding."""
    b_by_cell = b_by_cell or B_BY_CELL
    obs, ok = {}, True
    for c in CELLS:
        m = (cells.get(c) or {}).get("manifest", {})
        s = (cells.get(c) or {}).get("summary", {})
        cfg, where = S2._tiearb_cfg(m)
        want = {"enabled": True, "B": b_by_cell[c], "J": J_EXPECTED,
                "mode": MODE_EXPECTED, "salt": SALT_EXPECTED, "eps": EPS_EXPECTED}
        cfg_ok = isinstance(cfg, dict) and all(
            cfg.get(k) == v for k, v in want.items())
        sing_b, sing_j = s.get("tiearb_B"), s.get("tiearb_J")
        modes = s.get("tiearb_modes")
        realized_ok = (sing_b == [b_by_cell[c]] and sing_j == [J_EXPECTED]
                       and modes == [MODE_EXPECTED])
        obs[c] = {"resolved_at": where, "cand_tiearb": cfg, "expected": want,
                  "config_ok": bool(cfg_ok), "tiearb_B": sing_b,
                  "tiearb_J": sing_j, "tiearb_modes": modes,
                  "singletons_ok": bool(realized_ok),
                  "ok": bool(cfg_ok and realized_ok)}
        ok &= obs[c]["ok"]
    return bool(ok), {"observed": obs,
                      "semantics": "a mixed-B cell is a VOID, not a finding"}


#: ⭐ RULING 2 (`b64_cell/RULINGS_PREBLIND.md`, carried) — the key path is PINNED.
#: ⛔ AND THIS CELL READS IT STRICTLY: there is NO `two_sided.*` fallback for the
#: booleans, because `b32v64_cell/preflight.sh` now ASSERTS all four pinned
#: addresses on the emitting host before that host's game 1 (DESIGN §13.1's
#: "gate reading an address nothing writes" row — the b64 residual is CLOSED
#: HERE). A fallback would re-open the address the emitter now guarantees.
PREFLIGHT_B_PATH = "j13_witness.B"          # the B the control RAN at
PREFLIGHT_B_EXPECTED_PATH = "expected.B"    # the B the control ASSERTED
PREFLIGHT_CHANGED_PATH = "j13_witness.pick_changed"
PREFLIGHT_UNCHANGED_PATH = "j13_witness.root_leaf_value_bits_unchanged"
PREFLIGHT_PINNED = (PREFLIGHT_B_PATH, PREFLIGHT_B_EXPECTED_PATH,
                    PREFLIGHT_CHANGED_PATH, PREFLIGHT_UNCHANGED_PATH)
EXPECT_HOSTS = ("Doctor", "laptop-wsl")


def _dig(doc, dotted: str):
    cur = doc
    for part in dotted.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur


def gate_j13(preflights: list, expect_hosts=EXPECT_HOSTS, expect_b=(64, 32)) -> tuple:
    """`G-J13` `[PER-CELL]`/`[pre-run]` — the TWO-SIDED positive control passed on
    EACH host, at BOTH `B` values, BEFORE that host's game 1: the arbiter must
    CHANGE THE PICK at a constructed tied ply AND leave `root_leaf_value_bits`
    UNCHANGED.

    ⚠️ ADDRESSES ARE PINNED AND READ STRICTLY — `j13_witness.B` (int, == the
    file's `expected.B`), `j13_witness.pick_changed` (exactly `true`),
    `j13_witness.root_leaf_value_bits_unchanged` (exactly `true`). ⛔ NO
    `two_sided.*` fallback: this cell's `preflight.sh` asserts all four pinned
    addresses on the emitting host, so a missing pinned boolean is an EMITTER
    defect that must fail loudly rather than be papered over.

    ⚠️ ABSENT `B` ⇒ FAIL, never coerced. ⚠️ Absent file ⇒ fail.

    ⭐ RULING 4's condition, MANDATORY: `files_consumed` records, PER HOST, the
    exact filenames read and the `B` each carried — so a zero-match glob reads as
    ZERO, not as a silent pass.
    """
    by_host, consumed = {}, {}
    for d in preflights or ():
        host = str(d.get("host") or d.get("hostname"))
        b = _dig(d, PREFLIGHT_B_PATH)
        b_expected = _dig(d, PREFLIGHT_B_EXPECTED_PATH)
        changed = _dig(d, PREFLIGHT_CHANGED_PATH)
        unchanged = _dig(d, PREFLIGHT_UNCHANGED_PATH)
        consumed.setdefault(host, []).append(
            {"path": d.get("_path"), "j13_witness.B": b, "expected.B": b_expected,
             "pinned_present": {p: (_dig(d, p) is not None)
                                for p in PREFLIGHT_PINNED}})
        by_host.setdefault(host, {})[str(b)] = {
            "B": b, "expected_B": b_expected,
            "B_matches_expected": bool(b is not None and b == b_expected),
            "pick_changed": changed, "leaf_bits_unchanged": unchanged,
            "two_sided_ok": bool(changed is True and unchanged is True
                                 and b is not None and b == b_expected),
            "source": d.get("_path"),
            "read": "STRICTLY at the pinned addresses — no two_sided.* fallback"}
    ok, detail = True, {}
    for host in expect_hosts:
        rows = by_host.get(host, {})
        per_b = {}
        for b in expect_b:
            r = rows.get(str(b))
            per_b[str(b)] = r or {
                "two_sided_ok": False,
                "why": f"ABSENT — no witness record on host {host} carrying "
                       f"{PREFLIGHT_B_PATH} == {b} (a zero-match glob reads as "
                       f"ZERO, never as a silent pass — RULING 4)"}
            ok &= bool(per_b[str(b)].get("two_sided_ok"))
        detail[host] = per_b
    return bool(ok), {
        "by_host": detail,
        "files_consumed_per_host": {h: consumed.get(h, []) for h in expect_hosts},
        "files_consumed_other_hosts": {h: v for h, v in consumed.items()
                                       if h not in expect_hosts},
        "n_files_consumed": sum(len(v) for v in consumed.values()),
        "expected_hosts": list(expect_hosts), "expected_B": list(expect_b),
        "pinned_addresses": {"B": PREFLIGHT_B_PATH,
                             "expected_B": PREFLIGHT_B_EXPECTED_PATH,
                             "pick_changed": PREFLIGHT_CHANGED_PATH,
                             "root_leaf_value_bits_unchanged":
                                 PREFLIGHT_UNCHANGED_PATH},
        "strictness": ("⛔ STRICTLY PINNED — the b64 cell's two_sided.* fallback "
                       "is GONE. b32v64_cell/preflight.sh asserts all four pinned "
                       "addresses on the emitting host before that host's game 1 "
                       "(DESIGN §13.1), so a missing pinned address is an EMITTER "
                       "defect and must fail loudly."),
        "semantics": ("for EACH host, BOTH B values appear across that host's "
                      "witness records, each with both booleans true and "
                      "expected.B == j13_witness.B. ⚠️ ABSENT B ⇒ FAIL — never "
                      "'assume the file's B' (RULING 2)")}


def named_preflights(verdicts_dir, hosts=EXPECT_HOSTS, bs=(64, 32)) -> tuple:
    """The witness files at THE ADDRESSES THE PAIR NAMES — exactly
    `PREFLIGHT_${HOST}_FIRST_B{B}.json`, one per (host, B) — plus, reported
    separately, every timestamped ROTATION beside them.

    ⚠️ WHY THIS IS A LOOKUP AND NOT A RELAXATION. `preflight.sh` archives each
    earlier probe as `PREFLIGHT_${HOST}_FIRST_B{B}_<epoch>.json` when it re-runs
    after a wheel rebuild. A glob over `*_FIRST_B*.json` therefore sweeps up
    SUPERSEDED wheel epochs and hands `G-TOOL` a per-host set of two builds —
    which reads as "this host mixed builds" when what actually happened is "this
    host was re-probed after a rebuild, exactly as the marker requires
    (`[pre-run]`, *after any wheel rebuild on that host, before that host's game
    1*)". READ_RULE §3 names the un-timestamped address; this reads it.

    ⛔ THE SUPERSESSION IS RECORDED, NEVER SILENT (DESIGN §13.1's `G-TOOL` row:
    *"preflight.sh re-evaluates the probe's two pre-B1 sentinel rows under the
    ruled reading and records the supersession WITH ITS CITATION, never
    silently"*). The rotations are returned so a caller can print them beside the
    gate; they are a REPORT and are wired into no conjunct.
    """
    d = Path(verdicts_dir)
    named, superseded = [], []
    for host in hosts:
        for b in bs:
            p = d / f"PREFLIGHT_{host}_FIRST_B{b}.json"
            if p.is_file():
                named.append(p)
            for rot in sorted(d.glob(f"PREFLIGHT_{host}_FIRST_B{b}_*.json")):
                try:
                    doc = json.loads(rot.read_text())
                except (OSError, json.JSONDecodeError):
                    doc = {}
                superseded.append({
                    "path": str(rot), "host": host, "B": b,
                    "carc_rs_build": doc.get("carc_rs_build"),
                    "status": "SUPERSEDED ROTATION — not a named address, wired "
                              "into no conjunct, recorded rather than dropped"})
    return named, superseded


#: A timestamped ROTATION: the named address plus `_<epoch>` before `.json`.
#: ⚠️ The label slot is `.+` because `preflight.sh` writes
#: `PREFLIGHT_${HOST}_${LABEL}_B${B}_<epoch>.json` (READ_RULE §2.2) and the
#: label is not fixed by the pair — only the promoted, un-timestamped name is.
ROTATION_RE = re.compile(r"^PREFLIGHT_.+_B\d+_\d+\.json$")
ROTATION_SUFFIX_RE = re.compile(r"_\d+\.json$")


def resolve_preflights(supplied, verdicts_dir, hosts=EXPECT_HOSTS,
                       bs=(64, 32)) -> tuple:
    """⭐ THE SINGLE RESOLUTION PATH for `G-J13`/`G-TOOL`'s witness files, used by
    `adjudicate` AND by `knowngood`.

    ⛔ B7: the rotation-exclusion lookup used to be wired into `knowngood` ONLY,
    so the REAL adjudication path had no protection at all — an operator's
    `--preflight verdicts/PREFLIGHT_*_FIRST_B*.json` glob would hand `gate_tool`
    two builds for one host (the pre-rebuild rotation and the current one) and
    fail `G-TOOL` on a perfectly healthy run whose only sin was the wheel rebuild
    the `[pre-run]` marker MANDATES. 6,000 games un-adjudicated. That is this
    campaign's fourth unsatisfiable-gate shape.

    Two modes, and BOTH go through the same exclusion:
      * nothing supplied ⇒ resolve the four NAMED addresses from `verdicts_dir`.
      * paths supplied ⇒ they are honoured, but a supplied ROTATION is a
        **REFUSAL**, not a silent drop: the operator is told exactly which path
        is superseded and which named address to use instead. ⛔ Silently
        discarding an operator's explicit argument would be worse than either
        failing or accepting it — it would adjudicate a set the operator did not
        ask for, without saying so.
    """
    d = Path(verdicts_dir)
    if not supplied:
        named, superseded = named_preflights(d, hosts, bs)
        return named, superseded, {
            "mode": "RESOLVED from the NAMED addresses",
            "verdicts_dir": str(d),
            "named_pattern": "PREFLIGHT_{host}_FIRST_B{B}.json",
            "n_named": len(named), "n_rotations_excluded": len(superseded)}
    rotations = [p for p in supplied if ROTATION_RE.match(Path(p).name)]
    if rotations:
        lines = "\n  - ".join(
            f"{p}  ⇒ use the NAMED address "
            f"{ROTATION_SUFFIX_RE.sub('.json', Path(p).name)} instead"
            for p in rotations)
        raise SystemExit(
            "REFUSING: --preflight names SUPERSEDED ROTATION file(s):\n  - "
            + lines +
            "\n\nREAD_RULE §2 names ONE witness address per (host, B): "
            "PREFLIGHT_${HOST}_FIRST_B{64,32}.json. A rotation is an EARLIER "
            "wheel epoch archived by preflight.sh; feeding it to G-TOOL alongside "
            "the current one manufactures a 'mixed builds' failure on a healthy "
            "run. ⛔ This tool will not silently drop an argument you passed — "
            "pass the named addresses, or pass none and let it resolve them.")
    _named, superseded = named_preflights(d, hosts, bs)
    return ([Path(p) for p in supplied], superseded,
            {"mode": "SUPPLIED by --preflight (rotation-checked)",
             "verdicts_dir": str(d),
             "n_supplied": len(supplied),
             "n_rotations_excluded": len(superseded),
             "note": ("supplied paths passed the same rotation exclusion the "
                      "resolved path applies; rotations found in the verdicts "
                      "dir are reported beside G-TOOL")})


def gate_nest(gate_nest_doc) -> tuple:
    """`G-NEST` `[RUN]`/`[pre-run]` — `GATE_NEST.json` absent, or its witness
    false, voids the run.

    ⚠️ Without nesting the two cells are two unrelated draws and the whole
    "refinement" framing is void (DESIGN §1.3)."""
    if not isinstance(gate_nest_doc, dict):
        return False, {"present": False,
                       "why": "GATE_NEST.json ABSENT — absence is a FAIL, never a "
                              "pass (§3)"}
    w = gate_nest_doc.get("witness")
    return bool(w is True), {
        "present": True, "witness": w,
        "sites": gate_nest_doc.get("sites"),
        "structural": gate_nest_doc.get("structural"),
        "runtime": gate_nest_doc.get("runtime"),
        "anchor": gate_nest_doc.get("anchor") or gate_nest_doc.get("tautology_anchor"),
        "n_distinct_worlds_hi": gate_nest_doc.get("n_distinct_worlds_hi"),
        "n_distinct_worlds_lo": gate_nest_doc.get("n_distinct_worlds_lo"),
        "why": gate_nest_doc.get("why"),
        "claim": gate_nest_doc.get("claim")}


def gate_fire(cells: dict) -> tuple:
    """`G-FIRE` `[PER-CELL]` — `phi_effective < 1.0` in either cell means the
    arbitration surface is inert and the cell grades a champion-vs-champion null
    wearing the shape of a real cell. Realized prior ≈17.4–17.6 ⇒ 17× headroom."""
    obs, ok = {}, True
    for c in CELLS:
        cell = cells.get(c) or {}
        phi = (cell.get("phi") or {}).get("phi") if isinstance(cell.get("phi"), dict) \
            else cell.get("phi")
        err = (cell.get("summary") or {}).get("tiearb_error_rate_on_fired")
        eff = S2.phi_effective(phi, err)
        good = eff is not None and eff >= PHI_EFFECTIVE_FLOOR
        obs[c] = {"phi": phi, "error_rate_on_fired": err, "phi_effective": eff,
                  "floor": PHI_EFFECTIVE_FLOOR, "ok": bool(good)}
        ok &= good
    return bool(ok), {"observed": obs, "floor": PHI_EFFECTIVE_FLOOR,
                      "prior": {"offline": PHI_PRIOR_OFFLINE,
                                "b64_cell_realized": list(PHI_B64CELL_REALIZED),
                                "committed": PHI_COMMITTED},
                      "headroom": "≈17× against the realized prior"}


def f0_block(hi_by_deck: dict, lo_by_deck: dict) -> dict:
    """`f0` — the fraction of COMMON decks whose `D_i` is EXACTLY 0.0, and §4.3
    item 3's divergence block.

    ⚠️ MEASUREMENT DISCLOSURE, carried: `f0` is measured as "`D_i` exactly 0.0",
    which OVERCOUNTS identity (two genuinely different games can coincide on final
    margin) ⇒ `1 − f0` UNDERCOUNTS divergence ⇒ **the floor is CONSERVATIVE**: it
    can only fire early, never late."""
    common = sorted(set(hi_by_deck) & set(lo_by_deck))
    n = len(common)
    identical = sum(1 for s in common if (hi_by_deck[s] - lo_by_deck[s]) == 0.0)
    f0 = (identical / n) if n else None
    one_minus = (1.0 - f0) if f0 is not None else None
    dilution = math.sqrt(one_minus) if (one_minus is not None
                                        and one_minus >= 0) else None
    return {
        "f0": f0, "one_minus_f0": one_minus, "n_common_decks": n,
        "n_identical_decks": identical,
        "floor": DIVERGE_FLOOR, "expected_one_minus_f0": DIVERGE_EXPECTED,
        "anomaly_bar": DIVERGE_ANOMALY_BAR,
        "headroom_x": (DIVERGE_EXPECTED / DIVERGE_FLOOR),
        "dilution_sqrt_one_minus_f0": dilution,
        "anomaly": bool(one_minus is not None
                        and one_minus >= DIVERGE_FLOOR
                        and one_minus < DIVERGE_ANOMALY_BAR),
        "anomaly_note": ("⚠️ A realized 1 − f0 below 0.95 PASSES the gate and is "
                         "an ANOMALY that MUST be reported as one, never as a "
                         "pass (READ_RULE §4.3 item 3)."),
        "expected_derivation": (
            "DESIGN §8.2, RE-DERIVED AT THIS RUNG: the measured 32→64 "
            "value-change fraction on this campaign's own R4 corpus is 0.4045 per "
            "fired ply (shared_run_r4/verdicts/per_position_s1.jsonl, 1,340 "
            "plies); a deck carries ≈34.96 fired plies (2 seats × phi 17.481) ⇒ "
            "the modelled 1 − f0 is 1.0000, calibrated against the b64_cell's "
            "realized 0.9840 at a 31%-churnier rung ⇒ EXPECTED ≈0.98."),
        "measurement_disclosure": (
            "f0 is measured as 'D_i exactly 0.0', which OVERCOUNTS identity (two "
            "different games can coincide on margin) ⇒ 1 − f0 UNDERCOUNTS "
            "divergence ⇒ the floor is CONSERVATIVE: it can only fire early, "
            "never late."),
        "nested_crn": ("B = 64's worlds 0..31 are byte-identical to B = 32's "
                       "entire world set (DESIGN §1.3); CELL_B64 is a strict "
                       "REFINEMENT of CELL_B32, so a large identical fraction is "
                       "a POWER LOSS (z_D ∝ √(1−f0)), not a power win."),
    }


def gate_diverge(fb: dict) -> tuple:
    """`G-DIVERGE` `[RUN]` — `1 − f0 < 0.10` voids: the `B` = 64 surface is inert
    relative to `B` = 32 and the cell grades a `B=32`-vs-`B=32` null wearing the
    shape of a real contrast.

    ⭐ The floor is an INERTNESS DETECTOR, not a power check — ≈10× headroom
    against the expected 0.98, deliberately loose because a tighter floor risks
    failing a healthy run, this campaign's most-repeated defect."""
    v = fb.get("one_minus_f0")
    ok = v is not None and v >= DIVERGE_FLOOR
    keep = ("f0", "one_minus_f0", "n_common_decks", "n_identical_decks",
            "expected_one_minus_f0", "anomaly", "anomaly_bar",
            "dilution_sqrt_one_minus_f0")
    detail = {k: fb.get(k) for k in keep}
    detail.update({
        "floor": DIVERGE_FLOOR, "headroom_x": fb.get("headroom_x"),
        "role": "INERTNESS DETECTOR, not a power check",
        "why": ("inert: ≥90% of the paired sample contributes exactly zero to D "
                "by construction" if not ok else
                "the surface diverges above the inertness floor")})
    return bool(ok), detail


def gate_band(cells: dict, band_claim: dict, expected_band=BAND_EXPECTED) -> tuple:
    """`G-BAND` `[RUN]`/`[pre-run]`+`[post-cells]` — claimed from
    `BAND_REGISTRY.csv` BEFORE game 1, the sentinel reads the pinned band, and the
    two cells ran on the SAME band, equal to it, over the SAME decks."""
    starts, decks = {}, {}
    for c in CELLS:
        v, where = S2._manifest_get((cells.get(c) or {}).get("manifest", {}),
                                    "band_seed_start")
        starts[c] = {"band_seed_start": v, "resolved_at": where,
                     "matches_expected": _same_band(v, expected_band)}
        decks[c] = set((cells.get(c) or {}).get("deck_seeds") or ())
    same_band = (len({str(s["band_seed_start"]) for s in starts.values()}) == 1
                 and starts[CELLS[0]]["band_seed_start"] is not None)
    band_is_expected = all(s["matches_expected"] for s in starts.values())
    same_decks = decks[CELLS[0]] == decks[CELLS[1]] and bool(decks[CELLS[0]])
    claimed = bool((band_claim or {}).get("claimed_before_game_1"))
    sentinel_band = (band_claim or {}).get("band")
    sentinel_ok = _same_band(sentinel_band, expected_band)
    ok = bool(same_band and band_is_expected and same_decks and claimed
              and sentinel_ok)
    return ok, {
        "expected_band": expected_band,
        "band_seed_start": starts, "same_band": same_band,
        "band_is_expected": band_is_expected,
        "same_decks": same_decks,
        "n_decks": {c: len(decks[c]) for c in CELLS},
        "decks_only_in": {CELLS[0]: sorted(decks[CELLS[0]] - decks[CELLS[1]])[:5],
                          CELLS[1]: sorted(decks[CELLS[1]] - decks[CELLS[0]])[:5]},
        "band_claim": band_claim, "claimed_before_game_1": claimed,
        "sentinel_band": sentinel_band, "sentinel_matches_expected": sentinel_ok,
        "deck_range": f"{expected_band}..{expected_band + CELL_DECKS_PLANNED - 1}",
        "semantics": ("four conjuncts, ALL required: a pre-dated claim sentinel, "
                      "the sentinel naming the PINNED band, both cells on that "
                      "same band, and identical realized deck sets")}


def _same_band(a, b) -> bool:
    """Band equality across the int/str spellings a manifest and a sentinel use.
    ⛔ `None` never equals anything — absent is a FAIL, never coerced."""
    if a is None or b is None:
        return False
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return False


def gate_n(n_common, n_games: dict, deck_floor=N_COMMON_FLOOR,
           games_floor=CELL_GAMES_FLOOR, planned=CELL_GAMES_PLANNED,
           decks_planned=CELL_DECKS_PLANNED) -> tuple:
    """`G-N` `[RUN]`+`[PER-CELL]` — `n_common < 1,200` DECKS, or either cell under
    2,400 of its 3,000 paired GAMES.

    Both clauses are the SAME 80% bar in two units (2,400 games IS 1,200 decks);
    the deck clause is INDEPENDENTLY BINDING because two cells can each clear
    2,400 games while overlapping on fewer than 1,200 COMMON decks.

    ⭐ BOTH CLAUSES VERIFIED REACHABLE and the check is MECHANICAL, not a comment:
    Stage 2's version read 600 decks against a 400-deck ceiling and could only
    ever return `U-UNREADABLE`."""
    try:
        nc_ok = n_common is not None and n_common >= deck_floor
    except TypeError:
        nc_ok = False
    cell_ok = bool(n_games) and all(v is not None and v >= games_floor
                                    for v in n_games.values())
    return bool(nc_ok and cell_ok), {
        "n_common": n_common, "n_common_floor": deck_floor,
        "n_common_units": "DECKS", "n_games": dict(n_games),
        "cell_games_floor": games_floor, "cell_games_planned": planned,
        "cell_decks_planned": decks_planned,
        "same_80pct_bar": f"{games_floor} games IS {deck_floor} decks",
        "deck_clause_reachable": bool(deck_floor <= decks_planned),
        "game_clause_reachable": bool(games_floor <= planned),
        "reachability_note": (
            f"{deck_floor} <= the {decks_planned}-deck ceiling and {games_floor} "
            f"<= the {planned}-game ceiling — BOTH clauses are reachable (Stage "
            f"2's version was unreachable by construction)"),
        "deck_clause_independently_binding": (
            "two cells can each clear the game floor while overlapping on fewer "
            "than the deck floor of COMMON decks — that weakens D and still voids")}


def failure_surface(cells: dict) -> dict:
    """⭐ The MECHANICAL per-failure surface `eval_fair_puct` DOES emit, printed
    VERBATIM and wired into NO CONJUNCT (DESIGN §13.2 item 2, READ_RULE §4.3
    item 7).

    `_failure_block()` (`eval_fair_puct.py:2314-2359`, in place since 2026-08-14)
    emits per failed game `summary.json::failed_cells[].{seed, a_seat, attempts,
    permanent, exc_type, window_truncation, window_diag}`, a parallel
    `resolved_failed_cells[]`, plus `failure_rate`, `failure_rate_trigger` and
    `validity_trigger_fired`.

    ⛔ IT IS A REPORT, NOT A GATE CONJUNCT — precisely because wiring a NEW
    address into a gate conjunct after sign-off is how the three unsatisfiable
    gates got shipped. `window_truncation` is exactly the boolean clause 3's
    HUMAN confirmation is about; promoting it to a mechanical conjunct is a
    decision for a FUTURE pair, and this tool does not take it quietly."""
    out = {"wired_into_conjuncts": [],
           "status": "REPORT ONLY — wired into NO conjunct (DESIGN §13.2 item 2)",
           "emitter": "eval_fair_puct.py::_failure_block (since 2026-08-14)",
           "per_cell": {}}
    for c in CELLS:
        s = (cells.get(c) or {}).get("summary", {}) or {}
        out["per_cell"][c] = {
            "failed_cells": s.get("failed_cells", []),
            "resolved_failed_cells": s.get("resolved_failed_cells", []),
            "failure_rate": s.get("failure_rate"),
            "failure_rate_trigger": s.get("failure_rate_trigger"),
            "validity_trigger_fired": s.get("validity_trigger_fired"),
            "n_failed": s.get("n_failed"),
            "tiearb_errors_total": s.get("tiearb_errors_total"),
            "tiearb_error_rate_on_fired": s.get("tiearb_error_rate_on_fired"),
            "tiearb_first_error": s.get("tiearb_first_error"),
            "tiearb_partial_argmax_total": s.get("tiearb_partial_argmax_total"),
            "fields_present": sorted(
                k for k in ("failed_cells", "resolved_failed_cells",
                            "failure_rate", "failure_rate_trigger",
                            "validity_trigger_fired") if k in s),
        }
    return out


def raw_failure_records(cells: dict) -> list:
    """Every failed game's raw failure record, VERBATIM (message and traceback
    tail as emitted) — RULING 3's disclosure obligation.

    ⚠️ Printed verbatim rather than classified: the pair routes no per-failure
    class and the harness emits no `diagnostic_class`/`failed_classes` field
    (re-checked at HEAD, DESIGN §13.2 item 2)."""
    out = []
    for c in CELLS:
        for r in ((cells.get(c) or {}).get("records") or []):
            if r.get("ok") is False or r.get("error"):
                out.append({"cell": c, "seed": r.get("seed"),
                            "a_seat": r.get("a_seat"), "error": r.get("error"),
                            "traceback_tail": r.get("traceback_tail"),
                            "verbatim": True})
    return out


def gate_failed(cells: dict, confirmation: dict = None,
                raw_records: list = None, surface: dict = None) -> tuple:
    """`G-FAILED` `[RUN]`+`[PER-CELL]` — DESIGN §8.1's THREE clauses; ANY one
    fires ⇒ `U-UNREADABLE`.

    1 RATE (not count): `F_x / n_attempted_x > 0.02` in either cell. A bound
      written as a fraction of `n` shrinks with the completion floor while the
      failure rate does not, so it is written in the scale-free RATE.
    2 CANDIDATE-CORRELATION: `max(F) >= 5` AND `max(F) > 3 x max(min(F), 1)` —
      the `capoff` pattern, which biases `D` in an unknown direction. The `>= 5`
      floor exists because a bare ratio rule would have voided Stage 2's
      perfectly good run on its realized 1-vs-0 split.
    3 ⭐ AS NARROWED BY RULING 3, carried VERBATIM: if `F_w + F_n > 0`, the
      read-out prints EVERY failed game's raw failure record VERBATIM and the run
      **HALTS for owner escalation BEFORE ADJUDICATION** unless every failure is
      manually confirmed to be the known `WindowTruncationError` class. The
      confirmation is a HUMAN ACT recorded in the read-out — the one place this
      rule admits one — and it gates ESCALATION, never a branch.

      ⚠️ A DELIBERATE, DISCLOSED EXCEPTION to "no owner call adjudicates any
      outcome": it adjudicates NOTHING — no branch, no bar, no statistic moves on
      it — it decides only whether the run pauses.

    ⛔ The `failed_cells[]` / `resolved_failed_cells[]` / `validity_trigger_fired`
    surface is attached as a REPORT and is wired into NO conjunct.
    """
    per, F = {}, {}
    for c in CELLS:
        s = (cells.get(c) or {}).get("summary", {}) or {}
        f = s.get("n_failed")
        att = (s.get("n_attempted") or s.get("n")
               or (cells.get(c) or {}).get("n_games"))
        rate = (f / att) if (isinstance(f, (int, float)) and att) else None
        per[c] = {"n_failed": f, "n_attempted": att, "rate": rate,
                  "rate_bar": FAILED_RATE_BAR,
                  "clause1_ok": bool(rate is not None and rate <= FAILED_RATE_BAR)}
        F[c] = f if isinstance(f, (int, float)) else 0
    fmax, fmin = max(F.values()), min(F.values())
    clause2 = bool(fmax >= 5 and fmax > 3 * max(fmin, 1))
    n_failed_total = sum(F.values())
    confirmed = bool(confirmation
                     and confirmation.get("all_failures_confirmed") is True)
    clause3_halt = bool(n_failed_total > 0 and not confirmed)
    ok = (all(per[c]["clause1_ok"] for c in CELLS) and not clause2
          and not clause3_halt)
    return bool(ok), {
        "per_cell": per, f"F_{CELL_HI}": F[CELL_HI], f"F_{CELL_LO}": F[CELL_LO],
        "clause2_candidate_correlated": clause2,
        "clause2_rule": "max(F) >= 5 AND max(F) > 3 × max(min(F), 1)",
        "n_failed_total": n_failed_total,
        "clause3_halt": clause3_halt,
        "clause3_confirmation": confirmation or None,
        "clause3_rule": (
            "AS NARROWED (RULING 3, carried VERBATIM): if F_w + F_n > 0 the "
            "read-out prints every failed game's raw failure record VERBATIM and "
            "the run HALTS for owner escalation BEFORE ADJUDICATION unless every "
            "failure is manually confirmed to be the known WindowTruncationError "
            "class. The confirmation is a HUMAN ACT recorded in the read-out and "
            "it gates ESCALATION, never a branch."),
        "clause3_exception_disclosure": (
            "⚠️ A DELIBERATE, DISCLOSED EXCEPTION to 'no owner call adjudicates "
            "any outcome': it adjudicates NOTHING — no branch, no bar, no "
            "statistic moves on it — it decides only whether the run pauses."),
        "clause3_vacuous_at_zero": bool(n_failed_total == 0),
        "raw_failure_records": raw_records or [],
        "failure_surface_REPORT_ONLY": surface,
        "known_class": KNOWN_FAILURE_CLASS,
        "no_class_field_at_HEAD": (
            "eval_fair_puct emits no `diagnostic_class` / `failed_classes` field "
            "(re-checked at HEAD, DESIGN §13.2 item 2), so clause 3 carries "
            "RULING 3's narrowing verbatim. The per-failure surface it DOES emit "
            "(failed_cells[].window_truncation and friends) is PRINTED and wired "
            "into NO conjunct; promoting it is a decision for a FUTURE pair."),
        "selection_effect": (
            "window-truncation failures fire at extreme board extents, so any "
            "dropped set is CORRELATED WITH BOARD GEOMETRY — late-game, "
            "large-extent positions — and that correlation is DISCLOSED rather "
            "than argued away."),
        "hi_exposure_note": (
            "⚠️ CELL_B64 runs 2× the playouts per fired ply of CELL_B32 (not 4× as "
            "the b64 cell's WIDE did over NARROW), so it carries ~2× the per-ply "
            "exposure to the window-refusal class — directional, and it favours "
            "CELL_B32. Clause 2 binds in the direction that PROTECTS the reading.")}


def gate_tool(preflights: list) -> tuple:
    """`G-TOOL` `[RUN]` — ⭐ THE CONJUNCT IS EQUALITY OF `carc_rs_build` ACROSS
    BOXES, AND NOTHING ELSE.

    ⛔ `+rustcunpinned` is NOT a failure and NOT a sentinel — it is the NORMAL
    production value (`rust_agent.py:372`: `tc = os.environ.get("RUSTUP_TOOLCHAIN")
    or "unpinned"`), and D4.13 records BOTH boxes emitting exactly
    `carc_rs-0.1.0+58c2b5395569+rustcunpinned` on the R4 run and PASSING. This row
    is the campaign's THIRD unsatisfiable-gate catch and must never be
    re-tightened into a pinnedness requirement.

    ⚠️ The authoritative cross-box witness is the `PREFLIGHT_*_${HOST}_FIRST_B*`
    files, NOT the manifests: under `--shared-claim` the second box writes no
    manifest, so a manifest's `mixed_builds` is the writer's own observation and
    cannot see the other box. `carc_rs_binary_sha` is BOX-LOCAL and is NEVER
    compared across boxes (the `.so` is not machine-reproducible).
    """
    builds = {}
    for d in preflights or ():
        host = str(d.get("host") or d.get("hostname"))
        b = d.get("carc_rs_build") or ((d.get("execution") or {})
                                       .get("carc_rs_build"))
        builds.setdefault(host, set()).add(b)
    per_host = {h: sorted(str(x) for x in v) for h, v in sorted(builds.items())}
    distinct = {b for v in builds.values() for b in v}
    mixed_in_host = {h: v for h, v in per_host.items() if len(v) > 1}
    ok = (bool(per_host) and len(distinct) == 1 and not mixed_in_host
          and None not in distinct)
    return bool(ok), {
        "carc_rs_build_by_host": per_host,
        "distinct_builds": sorted(str(x) for x in distinct if x is not None),
        "mixed_within_a_host": mixed_in_host,
        "n_hosts": len(per_host),
        "conjunct": "EQUALITY of carc_rs_build across boxes, AND NOTHING ELSE",
        "unpinned_is_normal": (
            "⛔ '+rustcunpinned' is the NORMAL production value "
            "(rust_agent.py:372) and PASSES provided both boxes emit it — this "
            "campaign's THIRD unsatisfiable-gate catch. If pinned toolchains are "
            "wanted that is a change to WORKERS.conf::RUST_TOOLCHAIN, NEVER a "
            "gate conjunct that voids the run."),
        "binary_sha_rule": ("carc_rs_binary_sha is BOX-LOCAL and is NEVER "
                            "compared across boxes (the .so is not "
                            "machine-reproducible)"),
        "authority": "PREFLIGHT_${HOST}_FIRST_B*.json, not the manifests"}


def gate_ply(cells: dict) -> tuple:
    """`G-PLY` `[PER-CELL]` — `tiearb_partial_argmax_total` ABSENT (unknown, not
    zero) or NON-ZERO in either cell voids: an argmax over a partial world set
    means the CRN pairing across arms was broken during play, so the comparison
    is void whatever the margins say."""
    obs, ok = {}, True
    for c in CELLS:
        v = ((cells.get(c) or {}).get("summary", {}) or {}).get(
            "tiearb_partial_argmax_total")
        good = v == 0 and not isinstance(v, bool)
        obs[c] = {"tiearb_partial_argmax_total": v, "ok": bool(good),
                  "semantics": "ABSENT is unknown-not-zero and FAILS"}
        ok &= good
    return bool(ok), {"observed": obs,
                      "prior": "0 in both cells (Stage 2 realized 0 across 28,350 "
                               "fired plies; the b64 cell realized 0 in both)"}


def gate_stat(z_D, D, se_D, ci90, z_hi, z_lo, ub95_D=None) -> tuple:
    """`G-STAT` `[RUN]` — `z_D`, `D`, `se_D`, ⭐ **`UB95(D)`**, `CI90(D)`, `z_64`
    or `z_32` is NaN, INFINITE, or absent; or `se_D <= 0`.

    ⭐ `UB95(D)` IS NAMED HERE BECAUSE READ_RULE §3's `G-STAT` row NAMES IT. It is
    arithmetically implied by finite `D` and `se_D`, but the gate must print the
    realized value of every quantity the row lists — the same naming discipline
    the verb-enumeration rule imposes everywhere else. `None` ⇒ it is recomputed
    from `D` and `se_D` rather than treated as absent.

    ⚠️ Evaluated in §3, BEFORE any branch comparison, so no branch is ever entered
    on a NaN comparison (READ_RULE §4.4)."""
    vals = {"z_D": z_D, "D": D, "se_D": se_D,
            f"z_{CELL_HI}": z_hi, f"z_{CELL_LO}": z_lo}
    lo, hi = (ci90 if isinstance(ci90, (list, tuple)) and len(ci90) == 2
              else (None, None))
    vals["UB95"] = ub95_D if ub95_D is not None else ub95(D, se_D)
    vals["CI90_lo"], vals["CI90_hi"] = lo, hi
    bad = sorted(k for k, v in vals.items() if not _finite(v))
    se_positive = _finite(se_D) and se_D > 0
    return bool(not bad and se_positive), {
        "values": vals, "nan_inf_or_absent": bad,
        "se_D_positive": bool(se_positive),
        "UB95_label": UB95_LABEL, "CI90_label": CI90_LABEL,
        "checks": "NaN, +/-inf and absent all FAIL; se_D <= 0 FAILS",
        "precedence": ("evaluated in §3 BEFORE any branch comparison — this is "
                       "what makes READ_RULE §4.4's 'no branch is entered on a "
                       "NaN comparison' true mechanically")}


def halt_record(smoke: dict, bar=SMOKE_HALT_BAR) -> dict:
    """⭐ DESIGN §9.3's HALT DECISION RECORD, computed from `SMOKE.json`.

    ONE-SIDED by construction: an overrun HALTS, an underrun proceeds. ⛔ Absent
    or non-finite cost ⇒ **HALT** — the bar cannot be evaluated, and a cost check
    that cannot be evaluated must not wave a 6,000-game run through."""
    realized = (smoke or {}).get("worker_secs_per_game")
    if not _finite(realized):
        return {"halt": True, "realized": realized, "bar": bar,
                "graded_cell": CELL_HI, "evaluable": False,
                "why": ("⛔ HALT: SMOKE.json carries no finite "
                        "worker_secs_per_game, so §9.3's bar CANNOT BE EVALUATED. "
                        "Fail-closed: an unevaluable cost check halts."),
                "one_sided": "an overrun HALTS, an underrun proceeds"}
    halt = bool(realized > bar)
    return {
        "halt": halt, "realized": realized, "bar": bar,
        "graded_cell": CELL_HI, "evaluable": True,
        "multiple": SMOKE_HALT_MULTIPLE,
        "committed": WORKER_S_COMMITTED[CELL_HI],
        "why": (f"{CELL_HI} realized {realized:.3f} worker-s/game "
                f"{'>' if halt else '<='} {bar:.3f} "
                f"(= {SMOKE_HALT_MULTIPLE} x {WORKER_S_COMMITTED[CELL_HI]}, "
                f"MEASURED on the b64 cell's WIDE)"),
        "graded_on": (f"§9.3 grades {CELL_HI} ONLY — the one cell whose cost is "
                      f"MEASURED rather than projected. {CELL_LO}'s realized cost "
                      f"is printed against its projection and graded NOWHERE "
                      f"(§9.4); grading a 1.50x bar against a projection would be "
                      f"grading a model against itself."),
        "on_halt": ("⛔ the real cells are NOT launched, the smoke numbers and the "
                    "revised bill are reported, and the decision returns to the "
                    "OWNER. No re-tuning of B, the trigger, J, eps or the playout "
                    "is licensed by a HALT — the only permitted responses are "
                    "STOP, or the OWNER RE-FUNDS at the realized cost. ⛔ There is "
                    "NO override flag: a halt is not a switch the executor flips."),
        "one_sided": "an overrun HALTS, an underrun proceeds",
    }


def gate_smoke(smoke: dict, halt_doc: dict = None, cells_ran: bool = None,
               expected_knobs=None, earliest_cell_record_utc=None) -> tuple:
    """`G-SMOKE` `[RUN]` — three conjuncts, ALL from READ_RULE §3's row:

    1. **the smoke did not run at PRODUCTION KNOBS before game 1** — R6, now
       implementable: the knobs are read off the smoke cells' own manifests into
       `SMOKE.json::production_knobs` and compared to the pair's committed shape,
       and `smoke_utc` must be present. ⛔ Fail-closed on absence.
    2. **it HALTed on DESIGN §9.3 and the cells were LAUNCHED ANYWAY.**
    3. **`SMOKE.json` contains a FORBIDDEN OUTCOME KEY at any depth.**

    ⭐ RULING 1's TWO SURFACES: conjunct 3 is the GATE surface. The EMITTER
    whitelist result is REPORTED beside it and is NOT a gate input — reading the
    whitelist as the row fails a known-good smoke.

    ⛔ `launched_anyway` IS DERIVED, NEVER SUPPLIED. It was an `action="store_true"`
    operator flag whose default was the PASSING value — a "pass-always gate
    (constant input)" landing on a live §3 row, and a SECOND undeclared human
    input into a rule that states there is exactly ONE. It is now
    `halt ∧ cells_ran`, and `cells_ran` is mechanical: at `[post-cells]`
    adjudication the cells demonstrably ran.
    """
    if not isinstance(smoke, dict) or not smoke:
        return False, {"present": False,
                       "why": "SMOKE.json ABSENT — the smoke is a precondition"}
    wl = smoke_whitelist_check(smoke)
    outcome = smoke_outcome_scan(smoke)
    hd = halt_doc if isinstance(halt_doc, dict) else halt_record(smoke)
    halt = bool(hd.get("halt"))
    ran = bool(cells_ran)
    launched_anyway = bool(halt and ran)

    # ---- conjunct 1 (R6, DESIGN §9.2's table) ------------------------------ #
    knobs = smoke.get("production_knobs")
    smoke_utc = smoke.get("smoke_utc")
    if expected_knobs is None:
        knobs_block = {
            "evaluated": False,
            "why": ("⚠️ NOT EVALUATED — expected_knobs is None. Disclosed by the "
                    "caller (the known-good evaluation scales this conjunct "
                    "away because the b64 cell's SMOKE.json predates the "
                    "production_knobs / smoke_utc keys this pair adds); the "
                    "row's OTHER conjuncts still bind."),
            "observed": knobs, "smoke_utc": smoke_utc}
        knobs_ok = True
    elif not isinstance(knobs, dict) or smoke_utc is None:
        knobs_block = {
            "evaluated": True, "ok": False, "observed": knobs,
            "smoke_utc": smoke_utc,
            "why": ("⛔ SMOKE.json carries no production_knobs dict and/or no "
                    "smoke_utc — the FIRST conjunct cannot be evidenced, and "
                    "fail-closed means it FIRES rather than passing on absence.")}
        knobs_ok = False
    else:
        # DESIGN §9.2: "compared field-by-field against WORKERS.conf; ANY
        # MISMATCH FIRES." ⚠️ An observed `None` mismatches, so an address the
        # manifest did not carry fires rather than passing on absence.
        mismatched = {k: {"expected": v, "observed": knobs.get(k)}
                      for k, v in expected_knobs.items() if knobs.get(k) != v}
        # "before game 1" — DESIGN §9.2: smoke_utc compared against the EARLIEST
        # seed*.json mtime across both real cells; `smoke_utc >= that` FIRES.
        ordering_ok, ordering_why = True, (
            "not evaluated — no earliest-record timestamp supplied (the ordering "
            "clause is [post-cells] and needs the real cells' records)")
        if earliest_cell_record_utc is not None:
            # ⭐ N3: PARSED, never compared as strings. The two sides arrive in
            # different ISO spellings (offset vs `Z`) from different emitters.
            s_dt = _parse_utc(smoke_utc)
            e_dt = _parse_utc(earliest_cell_record_utc)
            if s_dt is None or e_dt is None:
                ordering_ok = False
                unparseable = [n for n, v, p in
                               (("smoke_utc", smoke_utc, s_dt),
                                ("earliest_cell_record_utc",
                                 earliest_cell_record_utc, e_dt)) if p is None]
                ordering_why = (
                    f"⛔ UNPARSEABLE timestamp(s) {unparseable} — the ordering "
                    f"clause cannot be evaluated, and fail-closed means it FIRES "
                    f"rather than passing on a timestamp nobody can read.")
            else:
                # DESIGN §9.2: "smoke_utc >= that ⇒ FIRES" — so an EXACT TIE
                # fires. The comparison is strictly-less-than for that reason.
                ordering_ok = bool(s_dt < e_dt)
                ordering_why = (
                    f"smoke_utc {smoke_utc} ({s_dt.isoformat()}) "
                    f"{'<' if ordering_ok else '>='} earliest real-cell record "
                    f"{earliest_cell_record_utc} ({e_dt.isoformat()}) — DESIGN "
                    f"§9.2: 'smoke_utc >= that ⇒ FIRES' (the smoke must COMPLETE "
                    f"before game 1; an EXACT TIE FIRES)")
        knobs_ok = (not mismatched) and ordering_ok
        knobs_block = {"evaluated": True, "ok": knobs_ok, "observed": knobs,
                       "expected": dict(expected_knobs),
                       "fields": list(PRODUCTION_KNOB_FIELDS),
                       "mismatched": mismatched,
                       "smoke_utc": smoke_utc,
                       "smoke_utc_parsed": (
                           _parse_utc(smoke_utc).isoformat()
                           if _parse_utc(smoke_utc) else None),
                       "earliest_cell_record_utc": earliest_cell_record_utc,
                       "ordering_ok": ordering_ok, "ordering_why": ordering_why,
                       "ordering_semantics": (
                           "both sides are PARSED to aware UTC datetimes before "
                           "comparison — the emitters write different ISO "
                           "spellings (offset vs Z) and a lexicographic compare "
                           "is only accidentally right. An EXACT TIE FIRES, per "
                           "DESIGN §9.2's '>='."),
                       "comparison": ("field-by-field against WORKERS.conf "
                                      "(DESIGN §9.2); ANY mismatch fires, and an "
                                      "observed None mismatches"),
                       "provenance": ("read OFF the smoke cells' own manifests, "
                                      "never injected by the emitter")}

    ok = bool(not outcome and not launched_anyway and knobs_ok)
    return ok, {
        "present": True, "whitelist_REPORTED_not_a_gate_input": wl,
        "conjunct1_production_knobs_before_game_1": knobs_block,
        "conjunct2_halted_and_launched_anyway": launched_anyway,
        "conjunct3_forbidden_outcome_keys": outcome,
        "forbidden_outcome_keys": outcome,
        "surfaces": ("EMITTER: fail-closed whitelist (§9.2 sentence 2). GATE: any "
                     "forbidden OUTCOME key at any depth (§3's G-SMOKE row). This "
                     "gate evaluates the GATE surface; structural keys never fire "
                     "it (RULING 1, carried VERBATIM)."),
        "worker_secs_per_game": hd.get("realized"),
        "halt_bar": SMOKE_HALT_BAR,
        "halt_record": hd,
        "halted": halt,
        "cells_ran": ran,
        "launched_anyway": launched_anyway,
        "launched_anyway_provenance": (
            "⛔ DERIVED, NOT SUPPLIED: halt ∧ cells_ran, where cells_ran is "
            "mechanical (at [post-cells] adjudication the cells demonstrably "
            "ran). The old --launched-after-halt store_true flag is DELETED: its "
            "default was the PASSING value, which made this conjunct a "
            "pass-always gate and a second undeclared human input."),
        "cost_definition": WORKER_SECS_DEFINITION,
        "one_sided": "an overrun HALTS, an underrun proceeds"}


# --------------------------------------------------------------------------- #
# §4 — the FIVE-branch table, fired in the committed order, FIRST MATCH WINS    #
# --------------------------------------------------------------------------- #
BRANCH_ORDER = ("U-UNREADABLE", "L-REVERSED", "L-RISING", "L-SATURATED",
                "L-AMBIGUOUS")

#: Rows 1–3 are SHAPE-INVARIANT: the pair did not amend them, because neither
#: `z_D ≤ −2.0` nor `z_D ≥ +2.0` depends on the equivalence predicate.
BRANCH_TEXT_COMMON = {
    "U-UNREADABLE": (
        "U-UNREADABLE — A §3 PRECONDITION FAILED.",
        "⛔ A FAILING GATE SUPPRESSES THE VERDICT. Report cost, integrity, firing "
        "rates, divergence, the failed-record accounting, and EVERY gate with its "
        "realized value — all 13, never short-circuited at the first failure. "
        "Nothing closes, nothing is licensed, nothing is re-labelled. ⛔ The "
        "read-out may NOT print D, z_D or a branch label as if adjudicated."),
    "L-REVERSED": (
        "⛔ NARROWING THE SELECTION WORLDS FROM 64 TO 32 MAKES THE ARBITER BETTER "
        "IN GAMES, AT 2σ, ON A FRESH BAND.",
        "⚠️ MANDATORY RIDER, never separated from the verdict: this is a DIRECT "
        "TENSION with the offline ladder, which prices arb(64) = 0.2015 ABOVE "
        "arb(32) = 0.1942, and with the b64_cell's own +1.7167 pts/game for "
        "16→64. Print both and do NOT present the tension as resolved. Those "
        "reads stand as adjudicated and this branch does not re-adjudicate them; "
        "what it establishes is that the offline→game map fails in THIS direction "
        "too, which is a first-class finding ABOUT THE MAP. Licenses: an "
        "INVESTIGATION, and an owner swap-down consideration on strictly stronger "
        "grounds than L-SATURATED would give. ⛔ NOTHING AUTOMATIC — "
        "PRODUCTION.yaml is untouched, no claim is minted, and a reversal at 2σ on "
        "one band is a reason to LOOK, not a reason to flip."),
    "L-RISING": (
        "⭐ THE LADDER IS STILL RISING AT 64: DROPPING TO B = 32 COSTS REAL GAME "
        "POINTS, RESOLVED AT 2σ ON A FRESH BAND.",
        "Reading: the deploy STAYS at B = 64 (PRODUCTION.yaml already carries it; "
        "this branch changes nothing, it CONFIRMS the incumbent). Licenses exactly "
        "one thing: a PREREGISTRATION for a B = 128 game cell — ⛔ which needs a "
        "FRESH prereg AND FRESH owner funding and is NOT automatic. ⚠️ MANDATORY "
        "RIDERS: (i) print the realized D against the offline-implied bracket "
        "[+0.040, +0.156] and state plainly that a D >= +1.009 read is >=6.5× the "
        "bracket top, i.e. the offline→game map has missed AGAIN and BY MORE, "
        "which is itself the finding; (ii) print rho_wall(128) = 4.9794 and the "
        "≈5.98× per-move total (≈10.8 s/move at the 1.8 s baseline) BESIDE any "
        "B = 128 language, so nobody proposes the rung without its price; (iii) ⛔ "
        "no branch may name B = 64 or B = 128 an optimum — two points cannot "
        "resolve the shape."),
}

# --------------------------------------------------------------------------- #
# ⭐ BRANCHES 4 AND 5 ARE SHAPE-KEYED — READ_RULE §4.1, TRANSCRIBED VERBATIM.   #
# --------------------------------------------------------------------------- #
#: ⛔ THE ROOT CAUSE OF R1's B1–B4, CLOSED HERE. The drafted adjudicator carried
#: the pre-RULING-1 two-sided text for these two rows while the pair carried the
#: ruled one-sided text — so the tool would have announced a two-sided
#: equivalence "AT 90% CONFIDENCE" on a rule that forbids the phrase. Keying the
#: text to the SAME committed line that keys the predicate makes that class of
#: drift impossible: the shape cannot move without the text moving with it.
#:
#: ⚠️ `tests/test_tiearb_b32v64.py`'s branch-TEXT conformance test asserts the
#: required phrases per shape and the forbidden ones' ABSENCE. That is the
#: assertion class whose absence let B1–B5 ship under 130 green tests.
BRANCH_TEXT_BY_SHAPE = {
    "one_sided": {
        "L-SATURATED": (
            "⭐ B = 32 DOES NOT COST MORE THAN THE OWNER'S ±15-ELO TOLERANCE: THE "
            "ONE-SIDED 95% UPPER BOUND ON THE COST IS BELOW +0.93 pts/game, ON A "
            "FRESH BAND, DECK-PAIRED.",
            "Licenses (does NOT do) exactly two things: (i) the deploy swap-down "
            "decision, B = 64 → B = 32, put to the owner carrying the realized D, "
            "UB95(D), the elo gloss, and the prize — ≈2.24 s/move saved, −35.7% "
            "of the per-move wall (DESIGN §4.1); the OWNER executes with one word "
            "and the prereg NEVER edits PRODUCTION.yaml itself; and (ii) it KILLS "
            "the B = 128 question — a rung that adds nothing detectable at 64 "
            "adds nothing at 128, and no future prereg may cite this cell as "
            "licensing one. ⚠️ MANDATORY SCOPE SENTENCE, quoted with the verdict "
            "and never separated from it: \"This is a ONE-SIDED NON-INFERIORITY "
            "result at 95%: it convicts that B = 32 does not COST more than 0.93 "
            "pts/game (15 elo), the owner's stated tolerance. It says NOTHING "
            "about a 0.20-pts cost, and it is NOT a proof that the two rungs are "
            "identical. The realized UB95(D) is printed beside it, and the "
            "two-sided CI90(D) is printed for context and adjudicates nothing.\" "
            "⚠️ SECOND MANDATORY RIDER: print §4.0's pre-run power figures "
            "(EFFECTIVE 0.556 at a true D = 0, 0.446 at the offline bracket top, "
            "both at the committed dispersion) beside the realized se_D, so the "
            "reader can see how much of this verdict was bought by a favourable "
            "dispersion draw. ⚠️ THIRD MANDATORY RIDER, AND IT EXISTS BECAUSE THE "
            "PREDICATE IS ONE-SIDED: if the realized D is NEGATIVE, the read-out "
            "must state plainly that L-REVERSED did NOT fire (z_D > −2.0), that a "
            "negative D firing this branch is CORRECT AND EXPECTED under RULING 1 "
            "— \"B = 32 does not cost 15 elo\" is more comfortably true there "
            "than at D = 0 — and that THIS BRANCH IS NOT THE PLACE TO CLAIM "
            "B = 32 IS BETTER; that claim belongs to L-REVERSED and was not "
            "earned."),
        "L-AMBIGUOUS": (
            "UNRESOLVED — NEITHER A CONVICTED COST NOR A CONVICTED "
            "NON-INFERIORITY.",
            "The deploy STAYS at B = 64 (the incumbent), and B = 128 is UNFUNDED "
            "BY DEFAULT. ⛔ Nothing closes and nothing is licensed. ⭐ NOTE WHAT "
            "THE ONE-SIDED SHAPE DOES TO THIS BRANCH: it is now REACHABLE ONLY "
            "FROM THE HIGH SIDE (D̂ > 0.93 − 1.645·se_D), because every D̂ below "
            "that edge and above L-REVERSED's fires L-SATURATED. ⇒ an "
            "L-AMBIGUOUS read means the realized point estimate was too HIGH to "
            "bound the cost, NEVER too low. ⚠️ MANDATORY POWER PRINT, and the "
            "branch is not readable without it: (i) the realized D, se_D, z_D, "
            "UB95(D) against the +0.93 tolerance, and CI90(D) for context; "
            "(ii) the n that WOULD have resolved the REALIZED point estimate as a "
            "NON-INFERIORITY, i.e. n such that D_realized + 1.645·se(n) ≤ 0.93 "
            "computed at the REALIZED per-deck dispersion, printed in decks AND "
            "in games AND in two-box wall-hours at DESIGN §7.5's measured "
            "35.560-worker pool — ⛔ and if D_realized ≥ 0.93 the read-out must "
            "state that NO n resolves it (the point estimate itself exceeds the "
            "tolerance, so shrinking se_D cannot help) rather than printing an "
            "enormous number; (iii) the same n for a 2σ cost verdict; (iv) §4.0's "
            "pre-run power table. ⚠️ MANDATORY SCOPE SENTENCE: \"This is an "
            "UNDER-POWERED one-sided non-inferiority test reading a high point "
            "estimate. READ_RULE §4.0 states before the run that L-SATURATED "
            "fires with EFFECTIVE probability 0.556 (committed dispersion) / "
            "0.629 (realized-dispersion projection) even when the two rungs are "
            "exactly equal — so ~44% of the equal-rungs world lands here. "
            "L-AMBIGUOUS is therefore NOT evidence that B = 32 is worse, and any "
            "read-out that presents it as such is over-reading it.\""),
    },
    #: ⚠️ THE DRAFTED, SUPERSEDED TEXT — retained ONLY so that a `two_sided`
    #: committed block still renders text that MATCHES its own predicate. It is
    #: not the ruled shape and the conformance test asserts the converse
    #: phrasing on it.
    "two_sided": {
        "L-SATURATED": (
            "⭐ B = 32 CAPTURES THE B = 64 GAIN WITHIN THE OWNER'S ±15-ELO "
            "TOLERANCE, AT 90% CONFIDENCE, ON A FRESH BAND, DECK-PAIRED.",
            "⚠️ THE DRAFTED TWO-SIDED SHAPE — SUPERSEDED BY RULING 1 (2026-08-21). "
            "Licenses (does NOT do) exactly two things: (i) the deploy SWAP-DOWN "
            "DECISION, B = 64 → B = 32, put to the owner carrying the realized D "
            "with its 90% CI, the elo gloss, and the prize — ≈2.24 s/move saved, "
            "−35.7% of the per-move wall (DESIGN §4.1); and (ii) it KILLS the "
            "B = 128 question. ⚠️ MANDATORY SCOPE SENTENCE: \"This convicts "
            "equivalence at ±0.93 pts/game (±15 elo), the owner's stated "
            "tolerance, and it says NOTHING about ±0.20. The realized 90% CI is "
            "printed beside it. This is an EQUIVALENCE result, not a proof that "
            "the two rungs are identical.\" ⚠️ SECOND MANDATORY RIDER: print "
            "§4.0's pre-run power figure (0.158 at the committed dispersion) "
            "beside the realized se_D."),
        "L-AMBIGUOUS": (
            "UNRESOLVED — NEITHER A DIFFERENCE NOR AN EQUIVALENCE.",
            "⚠️ THE DRAFTED TWO-SIDED SHAPE — SUPERSEDED BY RULING 1 (2026-08-21). "
            "The deploy STAYS at B = 64 (the incumbent), and B = 128 is UNFUNDED "
            "BY DEFAULT. ⛔ Nothing closes and nothing is licensed. ⚠️ MANDATORY "
            "POWER PRINT: (i) the realized D, se_D, z_D, CI90(D); (ii) the n that "
            "WOULD have resolved the REALIZED point estimate as an equivalence, "
            "in DECKS and GAMES and TWO-BOX WALL-HOURS; (iii) the same n for a 2σ "
            "DIFFERENCE verdict; (iv) §4.0's pre-run power table. ⚠️ MANDATORY "
            "SCOPE SENTENCE: \"This is an UNDER-POWERED equivalence test reading "
            "its modal outcome. READ_RULE §4.0 states before the run that "
            "L-SATURATED fires with probability 0.158 even when the two rungs are "
            "exactly equal. L-AMBIGUOUS is therefore NOT evidence that B = 32 is "
            "worse, and any read-out that presents it as such is over-reading "
            "it.\""),
    },
}


def branch_text(branch: str, equiv_cfg: dict) -> tuple:
    """`(headline, body)` for a branch UNDER THE COMMITTED SHAPE.

    ⛔ Fail-closed on an unknown shape: mis-labelling a verdict is the failure
    mode this whole keying exists to prevent, so an unrecognised shape refuses
    rather than falling back to the drafted text."""
    if branch in BRANCH_TEXT_COMMON:
        return BRANCH_TEXT_COMMON[branch]
    shape = equiv_cfg["equiv_shape"]
    if shape not in BRANCH_TEXT_BY_SHAPE:
        raise SystemExit(f"REFUSING: no §4.1 branch text for EQUIV_SHAPE="
                         f"{shape!r} — a verdict rendered in the wrong shape's "
                         f"words is a MIS-ADJUDICATION, not a formatting bug.")
    return BRANCH_TEXT_BY_SHAPE[shape][branch]


def decide_branch(z_D, D, se_D, preconditions: dict, equiv_cfg: dict) -> dict:
    """READ_RULE §4, verbatim and in order. FIRST MATCH WINS.

    1 `U-UNREADABLE`  any §3 gate failed — pre-empts everything
    2 `L-REVERSED`    `z_D <= -2.0`
    3 `L-RISING`      `z_D >= +2.0`
    4 `L-SATURATED`   `EQUIV` (shape + tolerance READ from WORKERS.conf)
    5 `L-AMBIGUOUS`   the complement, BY DEFINITION

    ⭐ DISJOINTNESS IS GUARANTEED BY FIRST-MATCH-WINS REGARDLESS OF ANY ARITHMETIC
    OVERLAP — that is the governing rule and nothing rests on the arithmetic. At
    the committed constants `L-RISING`/`L-REVERSED` and `L-SATURATED` cannot
    co-fire under `two_sided` for any `se_D > 0.93/3.645 = 0.2551`; under
    `one_sided` a NEGATIVE `D` at `z_D <= -2` satisfies both, and FIRST-MATCH-WINS
    resolves it to `L-REVERSED` — a 2σ difference is not an equivalence whatever a
    wide-margin bound says, and the read-out prints BOTH facts.

    ⇒ TOTALITY: 5 is defined as the complement, so 2–5 cover the whole space and
    exactly one branch matches every possible read."""
    failed = sorted(k for k, v in (preconditions or {}).items() if not v)
    eq = equiv_predicate(D, se_D, equiv_cfg)
    if failed:
        return {"branch": "U-UNREADABLE", "reason": "a §3 precondition failed",
                "failed_preconditions": failed, "z_D": z_D, "D": D, "se_D": se_D,
                "equiv": eq, "adjudicated": False,
                "suppressed": ("⛔ A failing gate SUPPRESSES the verdict — D, z_D "
                               "and a branch label may not be printed as if "
                               "adjudicated (READ_RULE §4.1 row 1).")}
    if not _finite(z_D):
        # unreachable: G-STAT is a precondition and fires first (§4.4)
        return {"branch": "U-UNREADABLE",
                "reason": "z_D is NaN/infinite/absent and G-STAT did not fire — "
                          "a DEFECT in the gate wiring, reported as one",
                "failed_preconditions": ["G-STAT"], "z_D": z_D, "D": D,
                "se_D": se_D, "equiv": eq, "adjudicated": False}
    if z_D <= -Z_BAR:
        return {"branch": "L-REVERSED", "reason": f"z_D {z_D:+.4f} <= -{Z_BAR}",
                "z_D": z_D, "D": D, "se_D": se_D, "equiv": eq,
                "adjudicated": True,
                "first_match_note": (
                    "⚠️ FIRST-MATCH-WINS: this branch pre-empts L-SATURATED even "
                    "where EQUIV is arithmetically true (which a one_sided shape "
                    "makes REACHABLE for a negative D). A 2σ difference is not an "
                    "equivalence, and BOTH facts are printed."
                    if eq["EQUIV"] else None)}
    if z_D >= Z_BAR:
        return {"branch": "L-RISING", "reason": f"z_D {z_D:+.4f} >= +{Z_BAR}",
                "z_D": z_D, "D": D, "se_D": se_D, "equiv": eq,
                "adjudicated": True,
                "first_match_note": (
                    "⚠️ FIRST-MATCH-WINS: this branch pre-empts L-SATURATED even "
                    "where EQUIV is arithmetically true. A 2σ difference is not "
                    "an equivalence, and BOTH facts are printed."
                    if eq["EQUIV"] else None)}
    if eq["EQUIV"]:
        return {"branch": "L-SATURATED",
                "reason": f"EQUIV under the committed {eq['equiv_shape']} shape: "
                          f"{eq['why']}",
                "z_D": z_D, "D": D, "se_D": se_D, "equiv": eq,
                "adjudicated": True}
    return {"branch": "L-AMBIGUOUS",
            "reason": (f"-{Z_BAR} < z_D {z_D:+.4f} < +{Z_BAR} and NOT EQUIV "
                       f"({eq['why']})"),
            "z_D": z_D, "D": D, "se_D": se_D, "equiv": eq, "adjudicated": True}


def reachable_branches(equiv_cfg: dict, se_d=SE_D_COMMITTED) -> dict:
    """READ_RULE §4.0 — the reachable SET, stated BEFORE the run.

    ⚠️ An unreachable headline branch must be visible BEFORE the run, never
    discovered in the read-out (the Stage-2 `G-N` lesson applied prospectively).
    ⭐ ALL FIVE ARE REACHABLE at the committed constants, and `L-SATURATED`'s
    window and its power at a true null are stated rather than left implicit."""
    tol = equiv_cfg["tolerance_pts"]
    window = tol - CI_Z * se_d
    pc = power_constants(equiv_cfg)
    return {
        "reachable": list(BRANCH_ORDER), "unreachable": [],
        "equiv_shape": equiv_cfg["equiv_shape"],
        "tolerance_pts": tol,
        "saturated_window_at_committed_se": window,
        "saturated_window_committed_documented": SATURATED_WINDOW_COMMITTED,
        "saturated_window_at_realized_projection":
            tol - CI_Z * SE_D_REALIZED_PROJECTION,
        "saturated_fire_region": pc["fire_region"],
        "power_at_true_D_zero_committed": pc["power_at_true_D_zero_committed"],
        "power_at_true_D_zero_realized_projection":
            pc["power_at_true_D_zero_realized_proj"],
        "power_is_EFFECTIVE": (
            "⚠️ EFFECTIVE = the one-sided test's raw probability MINUS the mass "
            "L-REVERSED takes first by FIRST-MATCH-WINS. EFFECTIVE is the number "
            "that governs what this read-out can say (READ_RULE §4.0)."),
        "n_for_80pct_equiv_power": {
            "committed_law_decks_per_cell": pc["n_for_80pct_committed"],
            "realized_law_decks_per_cell": pc["n_for_80pct_realized"],
            "note": pc["n_for_80pct_note"]},
        "modal_pre_run_expectation": pc["modal_pre_run_expectation"],
        "modal_note": pc["modal_note"],
        "power_statement": pc["statement"],
        "knife_edge": (
            "For the offline-implied bracket TOP (+0.1555) to fire L-SATURATED "
            "you need se_D <= (0.93 − 0.1555)/1.645 = 0.4708: the committed law "
            "needs n >= 1,722 decks/cell (n = 1,500 MISSES it), the realized law "
            "n >= 1,413 (n = 1,500 CLEARS it). ⛔ Not a reason to resize."),
        "overlap_arithmetic": (
            "two_sided: z_D >= 2 ⇒ |D| + 1.645*se_D >= 3.645*se_D, which exceeds "
            "the 0.93 tolerance for every se_D > 0.2551 ⇒ the overlap is empty at "
            "the committed se_D = 0.5044. one_sided: a NEGATIVE D at z_D <= -2 "
            "satisfies EQUIV by construction ⇒ the overlap is NON-EMPTY and "
            "FIRST-MATCH-WINS resolves it to L-REVERSED. Either way the governing "
            "rule is FIRST-MATCH-WINS, not the arithmetic."),
    }


# --------------------------------------------------------------------------- #
# §9 — the smoke aggregation, by DESIGN §7.1's OWN cost equation               #
# --------------------------------------------------------------------------- #
def aggregate_smoke(cell_dirs: dict, band=None, out_path=None) -> dict:
    """§9's `SMOKE.json`, aggregated from the two smoke cells' OWN artifacts.

    ⚠️ COUNTS-AND-COST ONLY (§9.2). The per-game records carry outcome fields
    (`diff`, `score_p0/p1`, `won_by_champ`); NONE of them is read, and the write
    is REFUSED if any outcome key reaches the artifact at any depth.

    ⚠️ FAIL-LOUD ON MISSING INPUTS. `elapsed_s` over the per-game records IS the
    cost basis (§7.1); a cell with no records cannot be aggregated and must not be
    silently reported as zero.

    ⭐ §9.3 grades ONE quantity — `CELL_B64`'s `worker_secs_per_game` — because it
    is the one cell whose cost is MEASURED rather than projected. `CELL_B32`'s
    realized cost is printed against its projection and graded NOWHERE (§9.4)."""
    cells, problems = {}, []
    for name, d in sorted((cell_dirs or {}).items()):
        p = Path(d)
        recs = sorted(p.glob("seed*.json"))
        if not recs:
            problems.append(f"{name}: NO per-game records under {p} — "
                            f"`elapsed_s` over seed*.json IS the cost basis "
                            f"(DESIGN §7.1); refusing rather than reporting zero")
            continue
        elapsed, n_with, n_without = 0.0, 0, 0
        for f in recs:
            try:
                r = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"{name}: unreadable record {f.name} ({exc})")
                continue
            e = r.get("elapsed_s")
            if isinstance(e, (int, float)) and not isinstance(e, bool):
                elapsed += float(e)
                n_with += 1
            else:
                n_without += 1
        if n_without:
            problems.append(f"{name}: {n_without} record(s) carry NO elapsed_s — "
                            f"the cost definition cannot be evaluated on them")
        summ = json.loads((p / "summary.json").read_text()) \
            if (p / "summary.json").is_file() else {}
        man = json.loads((p / "manifest.json").read_text()) \
            if (p / "manifest.json").is_file() else {}
        n_games = int(summ.get("n") or n_with)
        champ_ms = summ.get("champ_prefix_ms_per_move")   # ⚠️ THE CANDIDATE SIDE
        rung_ms = summ.get("rung_ms_per_move")            # ⚠️ the OPPONENT side
        wall = None
        if man.get("utc") and man.get("utc_end"):
            try:
                from datetime import datetime
                fmt = "%Y-%m-%dT%H:%M:%SZ"
                wall = (datetime.strptime(man["utc_end"], fmt)
                        - datetime.strptime(man["utc"], fmt)).total_seconds()
            except (ValueError, TypeError):
                wall = None
        cells[name] = {
            # ---- the graded quantity, by the PAIR'S OWN definition ---------
            "worker_secs_per_game": (elapsed / n_with) if n_with else None,
            "n_games": n_games, "n_records": len(recs),
            "n_records_with_elapsed_s": n_with,
            "elapsed_s_total": round(elapsed, 3),
            # ---- reported, never the cost basis ----------------------------
            "wall_secs": wall,
            "n_failed": summ.get("n_failed"),
            "champ_prefix_ms_per_move": champ_ms,
            "rung_ms_per_move": rung_ms,
            "ms_ratio_cand_over_opp": ((champ_ms / rung_ms)
                                       if (champ_ms is not None and rung_ms)
                                       else None),
            "tiearb_phi": summ.get("tiearb_phi"),
            "tiearb_fired_plies_total": summ.get("tiearb_fired_plies_total"),
            "tiearb_tile_plies_total": summ.get("tiearb_tile_plies_total"),
            "tiearb_fire_rate_on_tile_plies":
                summ.get("tiearb_fire_rate_on_tile_plies"),
            "tiearb_pickchange_rate": summ.get("tiearb_pickchange_rate"),
            "tiearb_mean_arms": summ.get("tiearb_mean_arms"),
            "tiearb_playouts_total": summ.get("tiearb_playouts_total"),
            "tiearb_secs_per_game": summ.get("tiearb_secs_per_game"),
            "tiearb_errors_total": summ.get("tiearb_errors_total"),
            "tiearb_first_error": summ.get("tiearb_first_error"),
            "tiearb_partial_argmax_total": summ.get("tiearb_partial_argmax_total"),
            "cand_leaf_hash": (man.get("cand_leaf_hash")
                               or (man.get("config") or {}).get("cand_leaf_hash")),
            "carc_rs_build": man.get("carc_rs_build"),
            "carc_rs_binary_sha": man.get("carc_rs_binary_sha"),
            "rust_toolchain": man.get("rust_toolchain"),
            "band_seed_start": (man.get("band_seed_start")
                                or (man.get("config") or {}).get("band_seed_start")),
            # ⭐ R6 — OBSERVED off this cell's own manifest, never injected.
            # `smoke_utc` is the smoke's COMPLETION (DESIGN §9.2) ⇒ `utc_end`.
            "production_knobs": _production_knobs_from_manifest(man),
            "smoke_utc": man.get("utc_end"),
            "_cand_tiearb": S2._tiearb_cfg(man)[0],
            "_manifest_present": bool(man),
        }
    if problems:
        raise SystemExit("REFUSING to write SMOKE.json:\n  - "
                         + "\n  - ".join(problems))

    hi = cells.get(CELL_HI) or {}
    doc = {
        # top level = the GRADED cell's fields (§9.3 grades CELL_B64's
        # worker_secs_per_game and nothing else), all inside §9.2's whitelist
        "worker_secs_per_game": hi.get("worker_secs_per_game"),
        "wall_secs": hi.get("wall_secs"),
        "workers": None, "secs_per_game": None, "games_per_sec": None,
        "n_failed": hi.get("n_failed"),
        "champ_prefix_ms_per_move": hi.get("champ_prefix_ms_per_move"),
        "rung_ms_per_move": hi.get("rung_ms_per_move"),
        "ms_ratio_cand_over_opp": hi.get("ms_ratio_cand_over_opp"),
        "tiearb_phi": hi.get("tiearb_phi"),
        "tiearb_fired_plies_total": hi.get("tiearb_fired_plies_total"),
        "tiearb_tile_plies_total": hi.get("tiearb_tile_plies_total"),
        "tiearb_fire_rate_on_tile_plies": hi.get("tiearb_fire_rate_on_tile_plies"),
        "tiearb_pickchange_rate": hi.get("tiearb_pickchange_rate"),
        "tiearb_mean_arms": hi.get("tiearb_mean_arms"),
        "tiearb_playouts_total": hi.get("tiearb_playouts_total"),
        "tiearb_secs_per_game": hi.get("tiearb_secs_per_game"),
        "tiearb_errors_total": hi.get("tiearb_errors_total"),
        "tiearb_first_error": hi.get("tiearb_first_error"),
        "tiearb_partial_argmax_total": hi.get("tiearb_partial_argmax_total"),
        "cand_leaf_hash": hi.get("cand_leaf_hash"),
        "carc_rs_build": hi.get("carc_rs_build"),
        "carc_rs_binary_sha": hi.get("carc_rs_binary_sha"),
        "rust_toolchain": hi.get("rust_toolchain"),
        # §9.1's condition of acceptance: the throwaway band DECLARES ITSELF
        # throwaway so it can never be mistaken for a claimed one
        "band_seed_start": band or hi.get("band_seed_start"),
        "band_tier": "throwaway",
        "band_registry_claimed": False,
        # ⭐ R6 — the two STRUCTURAL keys G-SMOKE's FIRST conjunct reads. The
        # GRADED cell's knobs sit at top level; both cells' are under `_cells`,
        # and `cand_tiearb_per_cell` carries BOTH so the per-cell B is checkable
        # from the top-level echo alone.
        "production_knobs": dict(
            hi.get("production_knobs") or {},
            cand_tiearb_per_cell={
                name: (c.get("_cand_tiearb") or None)
                for name, c in sorted(cells.items())}),
        "smoke_utc": (max([c.get("smoke_utc") for c in cells.values()
                           if c.get("smoke_utc")], default=None)),
        # ---- underscore-prefixed EMITTER METADATA (exempt by construction) --
        "_schema": "carcassonne-b32v64-smoke/v1",
        "_generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "_definition": WORKER_SECS_DEFINITION,
        "_graded": (f"§9.3 grades ONE quantity: {CELL_HI}'s worker_secs_per_game "
                    f"against {SMOKE_HALT_BAR:.3f} (= {SMOKE_HALT_MULTIPLE} x "
                    f"{WORKER_S_COMMITTED[CELL_HI]}, MEASURED on the b64 cell). "
                    f"The rest is printed and graded by nothing (§9.4). "
                    f"{CELL_LO}'s cost is a PROJECTION and grading a 1.50x bar "
                    f"against it would be grading a model against itself."),
        "_cells": cells,
        "_cells_note": ("§9.4 prints BOTH cells. They live under an "
                        "underscore-prefixed key because §9.2's emitter whitelist "
                        "is a FLAT list of top-level keys and is fail-closed on "
                        "anything outside it."),
        "_counts_and_cost_only": (
            "the per-game records carry outcome fields (diff, score_p0/p1, "
            "won_by_champ); NONE is read here, and the write is refused if any "
            "outcome key reaches this artifact at any depth (§9.2). ⚠️ f0 is "
            "MARGIN-DERIVED and is FORBIDDEN at the smoke."),
    }

    # ---- FAIL-CLOSED AT WRITE TIME, on BOTH surfaces (RULING 1) ------------
    wl = smoke_whitelist_check(doc)
    if not wl["ok"]:
        raise SystemExit(
            f"REFUSING to write SMOKE.json: key(s) outside §9.2's emitter "
            f"whitelist: {wl['forbidden_present']}")
    leaked = smoke_outcome_scan(doc)
    if leaked:
        raise SystemExit(
            f"REFUSING to write SMOKE.json: FORBIDDEN OUTCOME KEY(S) {leaked} — "
            f"§9.2 is COUNTS-AND-COST ONLY and this is what lets the smoke run "
            f"BEFORE the blind commit is spent without spending blindness.")

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return doc


# --------------------------------------------------------------------------- #
# the `D` block and §4.3 item 2's power arithmetic                             #
# --------------------------------------------------------------------------- #
def _parse_utc(s):
    """An ISO-8601 timestamp → an AWARE UTC `datetime`. `None` when unparseable.

    ⚠️ WHY THIS EXISTS (REVIEW R2 finding N3). The two sides of `G-SMOKE`'s
    ordering clause are written by DIFFERENT emitters in DIFFERENT spellings:
    `smoke_utc` is `manifest::utc_end`, which the harness writes in OFFSET form
    (`2026-08-20T20:47:05+00:00`), while `_earliest_record_utc` emits the `Z`
    form (`2026-08-21T00:00:00Z`). A **lexicographic** comparison of those two
    agrees at second resolution only by the accident of a shared 19-character
    prefix — and on an exact same-second tie `'+'` (0x2B) sorts before `'Z'`
    (0x5A), so the tie read **PASS** where DESIGN §9.2 says *"`smoke_utc` ≥ that
    ⇒ FIRES"*. Parsing both sides removes the accident and the boundary bug
    together.

    A naive timestamp is read as UTC — every emitter in this campaign writes UTC
    and says so — and the assumption is stated rather than hidden."""
    if not isinstance(s, str) or not s.strip():
        return None
    t = s.strip()
    if t[-1:] in ("Z", "z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _earliest_record_utc(dirs) -> str:
    """The EARLIEST `seed*.json` mtime across the given cell dirs, as ISO-8601
    UTC — DESIGN §9.2's clock for *"the smoke ran BEFORE game 1"*.

    `None` when no record exists, which leaves the ordering clause UNEVALUATED
    and disclosed as such: at `[pre-run]` there is nothing to order against, and
    inventing a timestamp would be worse than saying so."""
    best = None
    for d in dirs:
        if not d:
            continue
        for p in Path(d).glob("seed*.json"):
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            best = m if best is None else min(best, m)
    if best is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(best))


def ci90(D, se_D):
    """`CI90(D)` = `[D − 1.645·se_D, D + 1.645·se_D]`. `(None, None)` when either
    input is absent/NaN/infinite — never a half-formed interval."""
    if not _finite(D) or not _finite(se_D):
        return (None, None)
    return (D - CI_Z * se_D, D + CI_Z * se_D)


def n_for_equivalence(n_common, D, se_D, equiv_cfg: dict) -> dict:
    """§4.3 item 2 / `L-AMBIGUOUS` rider (ii): the `n` that WOULD have resolved the
    REALIZED point estimate as an equivalence, at the REALIZED per-deck dispersion.

    `se(n) = sd_per_deck / sqrt(n)` with `sd_per_deck = se_D * sqrt(n_common)`, and
    the requirement is `stat0 + 1.645*se(n) <= TOLERANCE` where `stat0` is `|D|`
    (two_sided) or `D` (one_sided).

    ⛔ `None` when the realized point estimate ALREADY exceeds the tolerance: no
    `n` resolves that as an equivalence, and printing a finite promise would be a
    lie. ⭐ Returns DECKS, GAMES and TWO-BOX WALL-HOURS, because the rider demands
    all three."""
    shape = equiv_cfg["equiv_shape"]
    formula = ("D_realized + 1.645*se(n) <= TOLERANCE" if shape == "one_sided"
               else "|D_realized| + 1.645*se(n) <= TOLERANCE")
    out = {"units": "decks per cell", "tolerance_pts": equiv_cfg["tolerance_pts"],
           "equiv_shape": shape, "formula": formula,
           "resolves_what": ("a NON-INFERIORITY" if shape == "one_sided"
                             else "an EQUIVALENCE"),
           "no_n_resolves_it": False,
           "decks_per_cell": None, "games_per_cell": None,
           "games_total": None, "worker_hours": None, "two_box_wall_hours": None,
           "effective_pool_workers": EFFECTIVE_POOL_WORKERS}
    if not (_finite(n_common) and n_common > 0 and _finite(D) and _finite(se_D)
            and se_D > 0):
        out["why"] = "absent / non-finite inputs — no promise is printed"
        return out
    stat0 = abs(D) if shape == "two_sided" else D
    slack = equiv_cfg["tolerance_pts"] - stat0
    if slack <= 0:
        # ⛔ READ_RULE §4.1 branch 5 rider (ii), VERBATIM: *"if D_realized >= 0.93
        # the read-out must state that NO n resolves it (the point estimate
        # itself exceeds the tolerance, so shrinking se_D cannot help) rather
        # than printing an enormous number."*
        out["no_n_resolves_it"] = True
        out["why"] = (
            f"⛔ NO n RESOLVES IT: the realized point estimate itself "
            f"({stat0:+.4f}) meets or exceeds the tolerance "
            f"{equiv_cfg['tolerance_pts']}, so SHRINKING se_D CANNOT HELP. "
            f"READ_RULE §4.1 branch 5 requires this statement rather than an "
            f"enormous number.")
        return out
    sd = se_D * math.sqrt(n_common)
    decks = int(math.ceil((sd * CI_Z / slack) ** 2))
    out.update(_supply_from_decks(decks))
    out["why"] = (f"se(n) <= ({equiv_cfg['tolerance_pts']} − {stat0:+.4f})/{CI_Z} "
                  f"= {slack / CI_Z:.4f} at the REALIZED per-deck sd {sd:.4f}")
    return out


def _supply_from_decks(decks: int) -> dict:
    """DECKS ⇒ games, worker-hours and two-box wall-hours, by DESIGN §7.5's
    MEASURED 35.560-worker effective pool (never the 46.5 capacity model, which
    under-predicts the measured arrangement by 1.31×)."""
    games_per_cell = 2 * decks
    worker_s = games_per_cell * (WORKER_S_COMMITTED[CELL_HI]
                                 + WORKER_S_COMMITTED[CELL_LO])
    worker_h = worker_s / 3600.0
    return {"decks_per_cell": decks, "games_per_cell": games_per_cell,
            "games_total": 2 * games_per_cell,
            "worker_hours": round(worker_h, 1),
            "two_box_wall_hours": round(worker_h / EFFECTIVE_POOL_WORKERS, 2)}


def d_block(hi_by_deck: dict, lo_by_deck: dict, equiv_cfg: dict,
            se_hi=None, se_lo=None) -> dict:
    """READ_RULE §2's `D` = `M_64 − M_32`, deck-paired, with `se_D`, `z_D`,
    `CI90(D)`, the realized `rho` and §4.3 item 2's full companion arithmetic.

    ⚠️ The paired arithmetic is `analyze_tiearb2_stage2.deck_paired_D`'s, imported
    rather than re-implemented, so `z_D` and the two cells' own `paired_z` remain
    comparable."""
    dpd = S2.deck_paired_D(hi_by_deck, lo_by_deck)
    D, se_D, z_D = dpd["D"], dpd["se_D"], dpd["z_D"]
    lo, hi = ci90(D, se_D)
    rho = None
    if all(_finite(v) and v != 0 for v in (se_hi, se_lo)) and _finite(se_D):
        rho = (se_hi ** 2 + se_lo ** 2 - se_D ** 2) / (2 * se_hi * se_lo)
    n_2sigma = S2.n_to_reach(dpd["n_common"], abs(z_D) if _finite(z_D) else None,
                             Z_BAR)
    out = dict(dpd)
    out.update({
        f"M_{CELL_HI}_on_common": dpd.get("M_arb_on_common"),
        f"M_{CELL_LO}_on_common": dpd.get("M_rnd_on_common"),
        # ⭐ THE PRIMARY, half 2 (READ_RULE §2 / §4.3 item 2)
        "UB95": ub95(D, se_D),
        "UB95_label": UB95_LABEL,
        "UB95_vs_tolerance": {
            "UB95": ub95(D, se_D), "tolerance_pts": equiv_cfg["tolerance_pts"],
            "below_tolerance": (None if ub95(D, se_D) is None else
                                bool(ub95(D, se_D) <= equiv_cfg["tolerance_pts"]))},
        "UB95_naming_rule": ("⛔ labelled 'ONE-SIDED 95% UPPER BOUND ON THE COST' "
                            "and NEVER '90% CI' (READ_RULE §4.3 item 2, RULING 1)."),
        # ⚠️ DEMOTED BY RULING 1 — reported for context, adjudicates nothing
        "CI90": [lo, hi], "CI90_lo": lo, "CI90_hi": hi, "ci_z": CI_Z,
        "CI90_label": CI90_LABEL,
        "rho": rho,
        "se_D_committed": SE_D_COMMITTED,
        "se_D_realized_projection_NON_BINDING": SE_D_REALIZED_PROJECTION,
        "floor_2sigma_committed": D_FLOOR_2SIGMA,
        "floor_2sigma_at_realized_projection": D_FLOOR_2SIGMA_REALIZED_PROJ,
        "dispersion_model_miss_x": ((se_D / SE_D_COMMITTED)
                                    if _finite(se_D) else None),
        "n_to_convict_2sigma_at_realized_dispersion": (
            dict(_supply_from_decks(n_2sigma), decks_per_cell=n_2sigma)
            if n_2sigma else {"decks_per_cell": None,
                              "why": "z_D is absent, NaN or zero — more games do "
                                     "not resolve a wrong-signed or absent effect"}),
        "n_to_convict_equivalence_at_realized_dispersion":
            n_for_equivalence(dpd["n_common"], D, se_D, equiv_cfg),
        "equiv": equiv_predicate(D, se_D, equiv_cfg),
        "elo_gloss_non_binding": (
            (D * ELO_GLOSS) if _finite(D) else None),
        "elo_gloss_disclaimer": (
            f"⛔ the {ELO_GLOSS} elo per pt/game gloss ADJUDICATES NOTHING. It is "
            f"a one-band, one-cell empirical conversion between two statistics of "
            f"the b64 cell's run; elo is a nonlinear function of win-rate and the "
            f"mapping is not a constant of nature. EVERY branch condition is "
            f"written in pts/game."),
        "definition": "D = M_B64 − M_B32, deck-paired over the decks completed in "
                      "BOTH cells; se_D and z_D exactly as eval_fair_puct's "
                      "_paired_z computes them.",
    })
    return out


def power_block(equiv_cfg: dict, se_D_realized=None) -> dict:
    """READ_RULE §4.0's PRE-RUN power table, printed on every branch — and
    MANDATORY on `L-SATURATED` (rider 2) and `L-AMBIGUOUS` (rider iv)."""
    tol = equiv_cfg["tolerance_pts"]
    realized_window = (tol - CI_Z * se_D_realized) if _finite(se_D_realized) else None
    pc = power_constants(equiv_cfg)
    return {
        "equiv_shape": pc["shape"],
        "pre_run": {
            "se_D_committed": SE_D_COMMITTED,
            "saturated_window_committed": SATURATED_WINDOW_COMMITTED,
            # ⭐ READ_RULE §4.0's table, per shape. raw / L-REVERSED mass /
            # EFFECTIVE — and EFFECTIVE is the governing number.
            "P_L_SATURATED_at_true_D_zero_RAW": pc["power_raw_committed"],
            "P_L_REVERSED_mass": pc["power_l_reversed_mass_committed"],
            "P_L_SATURATED_at_true_D_zero_EFFECTIVE":
                pc["power_at_true_D_zero_committed"],
            "P_at_bracket_floor_EFFECTIVE": pc["power_at_bracket_floor_committed"],
            "P_at_bracket_top_EFFECTIVE": pc["power_at_bracket_top_committed"],
            "se_D_realized_projection": SE_D_REALIZED_PROJECTION,
            "saturated_window_at_realized_projection":
                SATURATED_WINDOW_REALIZED_PROJ,
            "P_L_SATURATED_at_true_D_zero_RAW_realized_projection":
                pc["power_raw_realized_proj"],
            "P_L_SATURATED_at_true_D_zero_EFFECTIVE_realized_projection":
                pc["power_at_true_D_zero_realized_proj"],
            "P_at_bracket_floor_EFFECTIVE_realized_projection":
                pc["power_at_bracket_floor_realized_proj"],
            "P_at_bracket_top_EFFECTIVE_realized_projection":
                pc["power_at_bracket_top_realized_proj"],
            "n_for_80pct_power_committed_law": pc["n_for_80pct_committed"],
            "n_for_80pct_power_realized_law": pc["n_for_80pct_realized"],
            "n_for_80pct_note": pc["n_for_80pct_note"],
            "modal_pre_run_expectation": pc["modal_pre_run_expectation"],
        },
        "realized": {"se_D": se_D_realized,
                     "saturated_window_at_realized_se": realized_window},
        "statement": pc["statement"],
        "bought_by_dispersion": (
            "⚠️ Printed beside the realized se_D on L-SATURATED so the reader can "
            "see how much of that verdict was bought by a favourable dispersion "
            "draw rather than by the effect."),
    }


# --------------------------------------------------------------------------- #
# ⭐ THE KNOWN-GOOD GATE EVALUATION — the launch precondition                   #
# --------------------------------------------------------------------------- #
def knowngood_eval(b64_dir=B64_CELL_DIR, share=None, repo=REPO,
                   equiv_cfg=None) -> dict:
    """Evaluate every §3 row against the `b64_cell`'s COMPLETED artifacts.

    ⭐ THE POINT: prove the machinery exercises real data WITHOUT failing a
    healthy run. *"A gate that fails a healthy run is a drafting defect, and a
    fail-closed gate that ALWAYS fails is not conservative — it is a rule that
    cannot be run."* That is how this campaign caught three unsatisfiable gates.

    ⚠️ TWO KINDS OF SUBSTITUTION, both DISCLOSED PER ROW rather than silent:
      * `scaled` — a SCALE constant (the `n` floors, the band, the `B` values)
        replaced by the known-good run's own equivalent, because the b64 cell is a
        1,500-game / 750-deck run on band 139e9 at `B` ∈ {64, 16} and this cell's
        1,200/2,400 floors, its 140e9 band and its `B` = 32 are unreachable on it
        BY CONSTRUCTION. Grading them verbatim would report a FAIL that says
        nothing about the row's machinery.
      * `mapped` — a cell identity substituted (`CELL_B32` ← the b64 cell's
        `NARROW`, which is `B` = 16, the only second argmax cell that exists).
    A row whose machinery cannot be exercised at all is `N-A` and is NAMED, never
    silently counted as covered.
    """
    equiv_cfg = equiv_cfg or load_equiv_config()
    share = Path(share) if share else Path(DEFAULT_KNOWNGOOD_SHARE)
    b64_dir = Path(b64_dir)
    rows = {}

    def row(gid, status, detail, **kw):
        rows[gid] = {"status": status, "scope": GATE_SCOPE[gid],
                     "marker": GATE_MARKER[gid], "detail": detail, **kw}

    hi_dir = share / "b64_WIDE_B64J4_deploy11008"
    lo_dir = share / "b64_NARROW_B16J4_deploy11008"
    if not (hi_dir / "summary.json").is_file():
        return {"ok": False, "n_rows": 0, "rows": {},
                "error": f"b64_cell WIDE cell not found under {share} — the "
                         f"known-good evaluation reads REAL spent artifacts and "
                         f"refuses to invent them"}

    wide = S2.load_cell(CELL_HI, hi_dir / "summary.json", hi_dir / "manifest.json")
    narrow = S2.load_cell(CELL_LO, lo_dir / "summary.json", lo_dir / "manifest.json")
    cells = {CELL_HI: wide, CELL_LO: narrow}
    for c in CELLS:
        cells[c]["records"] = S2.load_records(
            hi_dir if c == CELL_HI else lo_dir)

    ok, d = gate_j1(cells)
    row("G-J1", "PASS" if ok else "FAIL", d,
        note="verbatim — both cells' REAL manifests, same champion leaf hash")

    ok, d = gate_j4(cells, b_by_cell={CELL_HI: 64, CELL_LO: 16})
    row("G-J4", "PASS" if ok else "FAIL", d,
        mapped=f"{CELL_LO} ← the b64 cell's NARROW",
        scaled="B: 32→16 for the low cell (no B = 32 artifact exists on any "
               "completed run — the row's MACHINERY is what is under test)")

    named, superseded = named_preflights(b64_dir / "verdicts",
                                         EXPECT_HOSTS, (64, 16))
    pre = S2.load_preflights(named)
    ok, d = gate_j13(pre, expect_hosts=EXPECT_HOSTS, expect_b=(64, 16))
    row("G-J13", "PASS" if ok else "FAIL", d,
        scaled="expected_B: (64,32)→(64,16) — the b64 cell ran B ∈ {64,16}. "
               "⭐ The STRICT-PINNED read (no two_sided.* fallback) is what is "
               "exercised, and it PASSES on the real files because that cell's "
               "preflight injected the pinned j13_witness.* booleans.")

    gnp = b64_dir / "GATE_NEST.json"
    gn = json.loads(gnp.read_text()) if gnp.is_file() else None
    ok, d = gate_nest(gn)
    row("G-NEST", "PASS" if ok else "FAIL", d,
        scaled="the b64 cell's own GATE_NEST.json witnesses 16 ⊂ 64, not 32 ⊂ 64. "
               "⭐ The ROW is a presence+witness check and transfers verbatim; the "
               "structural claim it rests on is B-INDEPENDENT (the seeding sites "
               "are pure functions of j).",
        structural_witness_at_HEAD=nest_witness(repo))

    ok, d = gate_fire(cells)
    row("G-FIRE", "PASS" if ok else "FAIL", d,
        note="verbatim — the floor 1.0 against a realized phi ≈17.4–17.6")

    fb = f0_block(wide["by_deck"], narrow["by_deck"])
    ok, d = gate_diverge(fb)
    row("G-DIVERGE", "PASS" if ok else "FAIL", d,
        note="⭐ VERBATIM AND ON REAL DATA — unlike the b64 cell's own known-good "
             "pass (which had to mark this N-A against Stage 2's different-MODE "
             "cells), the b64 cell IS a nested refinement (16 ⊂ 64), so f0 is the "
             "same quantity and the row is exercised for real.",
        divergence_block=fb)

    claim = S2.load_band_claim(b64_dir / "BAND_CLAIM.json",
                              expected_band=B64CELL_REALIZED["band"])
    ok, d = gate_band(cells, claim, expected_band=B64CELL_REALIZED["band"])
    row("G-BAND", "PASS" if ok else "FAIL", d,
        scaled=f"expected_band 140000000000 → {B64CELL_REALIZED['band']} (the "
               f"known-good run's own claimed band). ⚠️ Grading this cell's band "
               f"verbatim would report a FAIL about WHICH BAND the b64 cell ran "
               f"on, not about the row.")

    common = len(set(wide["by_deck"]) & set(narrow["by_deck"]))
    ok, d = gate_n(common, {CELL_HI: wide["n_games"], CELL_LO: narrow["n_games"]},
                   deck_floor=600, games_floor=1200, planned=1500,
                   decks_planned=750)
    row("G-N", "PASS" if ok else "FAIL", d,
        scaled="floors 1,200 decks / 2,400 games → the b64 cell's own 600/1,200 "
               "(the SAME 80% bar at its own n). ⚠️ Verbatim floors are "
               "unreachable on a 1,500-game run BY SIZE — grading them here would "
               "report a FAIL about the b64 cell's scale, not about this row",
        verbatim_would_be="FAIL (by size)")

    surf = failure_surface(cells)
    ok, d = gate_failed(cells, raw_records=raw_failure_records(cells),
                        surface=surf)
    row("G-FAILED", "PASS" if ok else "FAIL", d,
        note="verbatim — all three clauses on the real cells (the b64 cell "
             "realized 0/1500 failures in BOTH cells, so clause 3 is vacuous and "
             "clauses 1 and 2 evaluate on real emitted quantities)",
        failure_surface_REPORT_ONLY=surf)

    ok, d = gate_tool(pre)
    row("G-TOOL", "PASS" if ok else "FAIL", d,
        note="⭐ THE ROW THE PRECONDITION EXISTS FOR — a version that treated "
             "'+rustcunpinned' as a sentinel would have FAILED this healthy run. "
             "The conjunct is cross-box EQUALITY and nothing else. Both hosts "
             "emit one identical carc_rs-…+rustcunpinned string at the NAMED "
             "addresses.",
        consumed_named_addresses=[str(p) for p in named],
        superseded_rotations_REPORT_ONLY=superseded)

    ok, d = gate_ply(cells)
    row("G-PLY", "PASS" if ok else "FAIL", d, note="verbatim — 0 in both cells")

    db = d_block(wide["by_deck"], narrow["by_deck"], equiv_cfg,
                 se_hi=(wide.get("recomputed") or {}).get("se"),
                 se_lo=(narrow.get("recomputed") or {}).get("se"))
    ok, d = gate_stat(db["z_D"], db["D"], db["se_D"], db["CI90"],
                      wide["z"], narrow["z"], ub95_D=db["UB95"])
    row("G-STAT", "PASS" if ok else "FAIL", d,
        note="verbatim — z_D from the b64 cell's own WIDE−NARROW contrast, "
             "including UB95(D), the CI90 bounds and the se_D > 0 clause",
        D_block_on_known_good={k: db.get(k) for k in
                               ("D", "se_D", "z_D", "UB95", "CI90", "n_common",
                                "rho")})

    smoke_p = share / "smoke" / "SMOKE.json"
    smoke = json.loads(smoke_p.read_text()) if smoke_p.is_file() else {}
    wl = smoke_whitelist_check(smoke)
    # ⚠️ SCALED, and disclosed: `cells_ran=True` is the REAL state of a completed
    # run, so conjunct 2 is exercised against a genuine [post-cells] observation
    # rather than a convenient False. The knobs conjunct is scaled AWAY because
    # the b64 cell's SMOKE.json predates the two keys this pair adds.
    kg_halt = halt_record(smoke)
    ok, d = gate_smoke(smoke, halt_doc=kg_halt, cells_ran=True,
                       expected_knobs=None)
    row("G-SMOKE", "PASS" if ok else "FAIL", d,
        # ⭐ N4: A ROW-LEVEL "PASS" CAN OVER-STATE A MULTI-CONJUNCT ROW. This
        # file's own banner promises that machinery which cannot be exercised is
        # NAMED and never silently counted as covered — that promise was being
        # kept at ROW granularity while G-SMOKE's three conjuncts hid a scaled
        # one inside a PASS. The marker makes the partial coverage legible.
        conjunct_coverage={
            "conjunct1_production_knobs_before_game_1": "NOT EVALUATED (scaled)",
            "conjunct2_halted_and_launched_anyway": "EVALUATED",
            "conjunct3_forbidden_outcome_keys": "EVALUATED"},
        note="the GATE surface (forbidden OUTCOME keys at any depth) evaluated "
             "against the b64 cell's own SMOKE.json; the EMITTER whitelist result "
             "is reported beside it and is NOT a gate input (RULING 1). ⭐ The "
             "launched-anyway conjunct is exercised with cells_ran=True — the "
             "REAL state of that completed run — so it is graded on a genuine "
             "observation, not on a convenient default.",
        scaled="expected_knobs None — the b64 cell's SMOKE.json predates the "
               "production_knobs / smoke_utc keys DESIGN §9.2 adds here, so the "
               "FIRST conjunct is not evaluable on it. ⚠️ Grading it verbatim "
               "would report a FAIL about that cell's emitter VINTAGE, not about "
               "this row. The halt and outcome-key conjuncts bind unchanged.",
        smoke_path=str(smoke_p),
        halt_record_on_known_good=kg_halt,
        whitelist_forbidden_present=wl["forbidden_present"])

    evaluated = {g: r for g, r in rows.items() if r["status"] != "N-A"}
    na = {g: r for g, r in rows.items() if r["status"] == "N-A"}
    failed = sorted(g for g, r in evaluated.items() if r["status"] == "FAIL")
    # ⭐ N4 — CONJUNCT-LEVEL COVERAGE, so the "13/13 PASS" headline cannot
    # over-state a multi-conjunct row.
    partial = {g: {k: v for k, v in (r.get("conjunct_coverage") or {}).items()
                   if v != "EVALUATED"}
               for g, r in rows.items() if r.get("conjunct_coverage")}
    partial = {g: v for g, v in partial.items() if v}

    # ⭐ the BRANCH machinery, exercised on the known-good numbers too: a branch
    # table that never ran is not evidence that it runs.
    preconditions = {g: (r["status"] == "PASS") for g, r in evaluated.items()}
    branch = decide_branch(db["z_D"], db["D"], db["se_D"], preconditions,
                           equiv_cfg)
    return {
        "schema": "carcassonne-b32v64-knowngood/v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "precondition": ("DESIGN §12.1 / READ_RULE §0 — every §3 row must be "
                         "evaluated against a COMPLETED, KNOWN-GOOD run's "
                         "artifacts and must PASS on it, BEFORE the blind commit. "
                         "A row that fails a healthy run is a drafting defect."),
        "known_good_run": str(b64_dir),
        "known_good_verdict_of_record": "B-COSTKILL (spent; band 139e9 RETIRED)",
        "share": str(share),
        "equiv_config": equiv_cfg,
        "n_rows": len(rows), "n_evaluated": len(evaluated), "n_na": len(na),
        "n_pass": sum(1 for r in evaluated.values() if r["status"] == "PASS"),
        "n_fail": len(failed),
        "failed_rows": failed, "na_rows": sorted(na),
        "all_evaluable_rows_pass": not failed,
        "rows_with_partial_conjunct_coverage": partial,
        "coverage_caveat": (
            "⚠️ 'n/n PASS' is a ROW count. A row whose CONJUNCTS are not all "
            "exercised is listed in rows_with_partial_conjunct_coverage with the "
            "unexercised conjunct NAMED — the same promise this file makes for "
            "N-A rows, kept at conjunct granularity so a multi-conjunct row's "
            "PASS cannot over-state its coverage."
            if partial else
            "every conjunct of every evaluated row was exercised"),
        "branch_on_known_good": branch,
        "branch_on_known_good_disclaimer": (
            "⛔ NOT A VERDICT AND NOT A RE-ADJUDICATION. The b64 cell's verdict of "
            "record is B-COSTKILL, its read-rule is SPENT and its band 139e9 is "
            "RETIRED from confirmatory use. This label is emitted ONLY to prove "
            "the branch machinery runs end-to-end on real numbers; READ_RULE §5 "
            "forbids re-reading, re-labelling or re-adjudicating that cell, and "
            "nothing here does."),
        "meaning": ("'all rows pass' means every row WITH a known-good analogue "
                    "passes AND the rows without one are NAMED. A row that cannot "
                    "be evaluated NEVER silently counts as covered."),
        "rows": rows,
    }


#: ⚠️ Spec-vs-buildable mismatches are REPORTED, never resolved by changing the
#: frozen pair.
SPEC_VS_BUILDABLE = [
    {
        "where": "READ_RULE §3 G-FAILED clause 3 / DESIGN §8.1 clause 3",
        "issue": "eval_fair_puct emits no `diagnostic_class` / `failed_classes` "
                 "field (re-checked at HEAD). ⭐ But a per-failure surface DOES "
                 "exist: summary.json::failed_cells[].{seed, a_seat, attempts, "
                 "permanent, exc_type, window_truncation, window_diag} plus "
                 "resolved_failed_cells[], failure_rate, failure_rate_trigger and "
                 "validity_trigger_fired.",
        "adjudicator_behaviour": "clause 3 carries RULING 3's narrowing VERBATIM "
                                 "(verbatim disclosure + an escalation HALT before "
                                 "adjudication, cleared only by a recorded HUMAN "
                                 "confirmation). The mechanical surface is PRINTED "
                                 "in full and wired into NO conjunct.",
        "resolution": "⛔ NOT PROMOTED HERE. Wiring a new address into a gate "
                      "conjunct after sign-off is how the three unsatisfiable "
                      "gates shipped. Whether a FUTURE pair promotes "
                      "failed_cells[].window_truncation to a mechanical conjunct "
                      "is the orchestrator's decision; this tool does not take it "
                      "quietly.",
        "status": "REPORTED — carried as the pair drafted it",
    },
    {
        "where": "READ_RULE §3 G-J13 / DESIGN §3",
        "issue": "the b64 cell's residual — RULING 2 pins FOUR addresses, but on "
                 "that cell's earlier known-good fixture the two BOOLEANS sat at "
                 "`two_sided.*`, so its adjudicator carried a fallback.",
        "adjudicator_behaviour": "⭐ CLOSED HERE: this cell reads all four "
                                 "addresses STRICTLY at the pinned paths with NO "
                                 "two_sided.* fallback, because "
                                 "b32v64_cell/preflight.sh now ASSERTS all four on "
                                 "the emitting host before that host's game 1. An "
                                 "absent B — or an absent pinned boolean — FAILS.",
        "resolution": "no ruling required: the emitter obligation the b64 cell "
                      "NOTED is discharged by this cell's preflight, and the "
                      "known-good evaluation confirms the strict read still "
                      "passes a healthy run.",
        "status": "CLOSED — strict read, verified against real artifacts",
    },
    {
        "where": "READ_RULE §3 G-SMOKE / DESIGN §9.2",
        "issue": "§9.2 states TWO rules on TWO surfaces. Read as ONE whitelist "
                 "over the artefact, the row FAILS a known-good smoke, whose "
                 "SMOKE.json legitimately carries structural keys.",
        "adjudicator_behaviour": "the GATE fires on forbidden OUTCOME keys at any "
                                 "depth; the EMITTER whitelist is evaluated and "
                                 "REPORTED beside it, never as the gate verdict "
                                 "(RULING 1, carried VERBATIM).",
        "resolution": "carried as ruled on the sibling cell; no new ruling needed.",
        "status": "CARRIED — RULING 1 implemented",
    },
    {
        "where": "DESIGN §13.2 item 7 — gate_nest.py's cross-cell dependency",
        "issue": "b32v64_cell/gate_nest.py imported `nest_witness` from "
                 "scripts/tiletie/analyze_b64_cell.py — a live dependency on a "
                 "SPENT run's tooling, which the drafter reported for the "
                 "orchestrator to rule on.",
        "adjudicator_behaviour": "⭐ DISCHARGED as the drafter's own stated "
                                 "resolution requires: `nest_witness` is COPIED "
                                 "into this module (not imported), gate_nest.py's "
                                 "import is repointed here, and "
                                 "analyze_b64_cell.py is UNTOUCHED.",
        "resolution": "the structural claim is B-INDEPENDENT (a property of the "
                      "rust source, not of any (B_lo, B_hi) pair), so the copy is "
                      "verbatim rather than re-parameterized.",
        "status": "CLOSED — moved, not re-derived",
    },
    {
        "where": "DESIGN §9.3 HALT bar / READ_RULE §3 G-SMOKE launched-anyway "
                 "(REVIEW R1 finding B6)",
        "issue": "⛔ THE BAR WAS UNENFORCED END-TO-END. The launcher LOGGED the "
                 "bar's value and never compared; smoke-check computed `halt` "
                 "and dropped it out of its exit condition; and the gate's "
                 "conjunct hung on `--launched-after-halt`, an operator "
                 "store_true flag whose DEFAULT WAS THE PASSING VALUE — a "
                 "pass-always gate on a live §3 row, and a SECOND undeclared "
                 "human input into a rule that declares exactly one.",
        "adjudicator_behaviour": "smoke-check WRITES SMOKE_HALT.json (DESIGN "
                                 "§9.3.1) and puts `halt` in its exit condition; "
                                 "run_cells.sh READS it and refuses a real-cell "
                                 "launch; G-SMOKE derives launched_anyway = "
                                 "halt AND cells_ran, both mechanical at "
                                 "[post-cells]. The flag is DELETED.",
        "resolution": "⛔ NO OVERRIDE FLAG EXISTS: a HALT holds until the owner "
                      "rules (stop, or re-fund at the realized cost). An absent "
                      "or unreadable cost also HALTS — an unevaluable cost check "
                      "must not wave a 6,000-game run through.",
        "status": "CLOSED — three links, all enforced",
    },
    {
        "where": "READ_RULE §2.2 / §3 G-TOOL — the preflight address "
                 "(REVIEW R1 finding B7)",
        "issue": "the rotation-exclusion lookup was wired into `knowngood` ONLY, "
                 "so the REAL adjudication path had no protection: an operator "
                 "glob would hand G-TOOL two builds for one host and fail a "
                 "healthy run whose only irregularity was the wheel rebuild the "
                 "[pre-run] marker MANDATES.",
        "adjudicator_behaviour": "`resolve_preflights` is the SINGLE resolution "
                                 "path for both modes: with no --preflight it "
                                 "resolves READ_RULE §2.2's four named "
                                 "addresses; with paths supplied it REFUSES any "
                                 "timestamped rotation by name rather than "
                                 "silently dropping an argument the operator "
                                 "passed. Rotations are reported beside G-TOOL.",
        "resolution": "the pair now states the address and the supersession rule "
                      "in §2.2, so the behaviour is supported by the TEXT and "
                      "not only by this docstring.",
        "status": "CLOSED — one resolution path, both modes",
    },
    {
        "where": "READ_RULE §4 EQUIV / WORKERS.conf committed constants block",
        "issue": "⭐ THE BAR IS OWNER-RULED AND MUST BE CHANGEABLE WITHOUT A CODE "
                 "EDIT. A tolerance or a test shape hard-coded in the adjudicator "
                 "would make the pair's committed block decorative — the "
                 "'pass-always gate (constant input)' disease §13.1 audits for.",
        "adjudicator_behaviour": "TOLERANCE_PTS and EQUIV_SHAPE are READ, "
                                 "fail-closed, from b32v64_cell/WORKERS.conf. Two "
                                 "shapes are supported — two_sided (CI90 "
                                 "containment) and one_sided (non-inferiority on "
                                 "the upper bound). An absent, unparseable or "
                                 "out-of-vocabulary value is a REFUSAL, with NO "
                                 "coerced default.",
        "resolution": "OWNER RULING 2026-08-21 selected ONE-SIDED ±15 ⇒ the "
                      "COMMITTED shape is `one_sided`. ⚠️ Under one_sided a "
                      "large-negative D satisfies EQUIV arithmetically; "
                      "FIRST-MATCH-WINS resolves it to L-REVERSED, which is "
                      "branch #2, and the read-out prints BOTH facts.",
        "status": "RULED — parameterized, committed value one_sided",
    },
]


# --------------------------------------------------------------------------- #
# the read-out                                                                 #
# --------------------------------------------------------------------------- #
def build_readout(args) -> dict:
    equiv_cfg = load_equiv_config(args.workers_conf)
    cells = {}
    for c, summ, man, recs in ((CELL_HI, args.b64_summary, args.b64_manifest,
                                args.b64_records),
                               (CELL_LO, args.b32_summary, args.b32_manifest,
                                args.b32_records)):
        cells[c] = S2.load_cell(c, summ, man, recs)
        # RULING 3's disclosure needs the RAW records, which `load_cell` digests
        cells[c]["records"] = S2.load_records(
            recs if recs is not None else Path(summ).parent)

    db = d_block(cells[CELL_HI]["by_deck"], cells[CELL_LO]["by_deck"], equiv_cfg,
                 se_hi=(cells[CELL_HI].get("recomputed") or {}).get("se"),
                 se_lo=(cells[CELL_LO].get("recomputed") or {}).get("se"))
    fb = f0_block(cells[CELL_HI]["by_deck"], cells[CELL_LO]["by_deck"])

    # ⭐ B7 — the SAME rotation-exclusion resolution the known-good path uses.
    pre_paths, rotations, pre_resolution = resolve_preflights(
        args.preflight, args.verdicts_dir)
    pre = S2.load_preflights(pre_paths)
    gn = json.loads(Path(args.gate_nest).read_text()) if (
        args.gate_nest and Path(args.gate_nest).is_file()) else None
    claim = S2.load_band_claim(args.band_claim, expected_band=BAND_EXPECTED) \
        if args.band_claim else {"claimed_before_game_1": False, "band": None,
                                 "note": "no --band-claim given"}
    smoke = json.loads(Path(args.smoke).read_text()) if (
        args.smoke and Path(args.smoke).is_file()) else {}
    # ⭐ B6 — the §9.3 HALT DECISION RECORD, read from the [post-smoke] address if
    # the executor emitted one, else recomputed from SMOKE.json. Either way the
    # gate's `launched_anyway` conjunct is DERIVED, never supplied.
    halt_path = Path(args.smoke_halt) if args.smoke_halt else None
    halt_doc = (json.loads(halt_path.read_text())
                if (halt_path and halt_path.is_file()) else
                (halt_record(smoke) if smoke else None))
    # mechanical: at [post-cells] adjudication the cells demonstrably ran
    cells_ran = any((cells[c].get("n_games") or 0) > 0 for c in CELLS)
    # DESIGN §9.2's ordering clause: the EARLIEST seed*.json mtime across BOTH
    # real cells is what "before game 1" is measured against.
    earliest_record_utc = _earliest_record_utc(
        [args.b64_records or Path(args.b64_summary).parent,
         args.b32_records or Path(args.b32_summary).parent])

    surf = failure_surface(cells)
    raws = raw_failure_records(cells)
    confirmation = ({"all_failures_confirmed": True,
                     "confirmed_by": args.failures_confirmed_by,
                     "note": args.failures_confirmed_note,
                     "recorded": "a HUMAN ACT, recorded in the read-out; it gates "
                                 "ESCALATION, never a branch"}
                    if args.failures_confirmed_by else None)

    gates = {}
    gates["G-J1"] = gate_j1(cells)
    gates["G-J4"] = gate_j4(cells)
    gates["G-J13"] = gate_j13(pre)
    gates["G-NEST"] = gate_nest(gn)
    gates["G-FIRE"] = gate_fire(cells)
    gates["G-DIVERGE"] = gate_diverge(fb)
    gates["G-BAND"] = gate_band(cells, claim)
    gates["G-N"] = gate_n(db["n_common_decks"],
                          {c: cells[c]["n_games"] for c in CELLS})
    gates["G-FAILED"] = gate_failed(cells, confirmation=confirmation,
                                    raw_records=raws, surface=surf)
    gates["G-TOOL"] = gate_tool(pre)
    gates["G-PLY"] = gate_ply(cells)
    gates["G-STAT"] = gate_stat(db["z_D"], db["D"], db["se_D"], db["CI90"],
                                cells[CELL_HI]["z"], cells[CELL_LO]["z"],
                                ub95_D=db["UB95"])
    gates["G-SMOKE"] = gate_smoke(
        smoke, halt_doc=halt_doc, cells_ran=cells_ran,
        expected_knobs=expected_production_knobs(args.workers_conf),
        earliest_cell_record_utc=earliest_record_utc)
    gates["G-TOOL"][1]["superseded_rotations_REPORT_ONLY"] = rotations
    gates["G-TOOL"][1]["preflight_resolution"] = pre_resolution
    gates["G-J13"][1]["preflight_resolution"] = pre_resolution

    preconditions = {g: ok for g, (ok, _d) in gates.items()}

    # ⭐ RULING 3's HALT — BEFORE ADJUDICATION, and it is not a branch. No §4
    # branch fires, no statistic is graded, nothing is licensed or re-labelled:
    # the run PAUSES for owner escalation and the disclosure is emitted.
    gf = gates["G-FAILED"][1]
    if gf.get("clause3_halt"):
        return {
            "schema": "carcassonne-b32v64-cell-halt/v1",
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "HALT-OWNER-ESCALATION", "branch": None,
            "adjudicated": False,
            "headline": ("⛔ HALTED FOR OWNER ESCALATION BEFORE ADJUDICATION — "
                         f"{gf['n_failed_total']} failed game(s)."),
            "rule": gf["clause3_rule"],
            "exception_disclosure": gf["clause3_exception_disclosure"],
            "raw_failure_records": gf["raw_failure_records"],
            "failure_surface_REPORT_ONLY": surf,
            "failed_accounting": {k: gf.get(k) for k in
                                  ("per_cell", f"F_{CELL_HI}", f"F_{CELL_LO}",
                                   "n_failed_total",
                                   "clause2_candidate_correlated")},
            "how_to_clear": ("re-run with --failures-confirmed-by <name> "
                             "--failures-confirmed-note '<verbatim confirmation "
                             "that every failure is the known "
                             f"{KNOWN_FAILURE_CLASS} class>'. The confirmation is "
                             "recorded in the read-out and gates ESCALATION ONLY."),
            "adjudicates": ("NOTHING — no branch, no bar, no statistic moves on "
                            "this. It decides only whether the run pauses."),
            "gates": {g: {"ok": ok, "scope": GATE_SCOPE[g],
                          "marker": GATE_MARKER[g], "detail": d}
                      for g, (ok, d) in gates.items()},
            "selection_effect": gf["selection_effect"],
        }

    branch = decide_branch(db["z_D"], db["D"], db["se_D"], preconditions,
                           equiv_cfg)
    head, body = branch_text(branch["branch"], equiv_cfg)

    # ⭐ L-SATURATED's THIRD MANDATORY RIDER — it exists because the predicate is
    # one-sided, and it fires on the realized sign, so it is resolved HERE rather
    # than left as static prose a reader must apply themselves.
    negative_D_disclosure = None
    if (branch["branch"] == "L-SATURATED"
            and equiv_cfg["equiv_shape"] == "one_sided"
            and _finite(db["D"]) and db["D"] < 0):
        negative_D_disclosure = (
            f"⚠️ THIRD MANDATORY RIDER, DISCHARGED: the realized D is NEGATIVE "
            f"({db['D']:+.4f}). L-REVERSED did NOT fire (z_D = {db['z_D']:+.4f} > "
            f"−{Z_BAR}). A negative D firing L-SATURATED is CORRECT AND EXPECTED "
            f"under RULING 1 — \"B = 32 does not cost 15 elo\" is more comfortably "
            f"true here than at D = 0. ⛔ THIS BRANCH IS NOT THE PLACE TO CLAIM "
            f"B = 32 IS BETTER; that claim belongs to L-REVERSED and was NOT "
            f"earned.")

    return {
        "schema": "carcassonne-b32v64-cell-readout/v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "read_rule": "measurement/tiearb_widening_20260817/b32v64_cell/READ_RULE.md",
        "design": "measurement/tiearb_widening_20260817/b32v64_cell/DESIGN.md",
        "blind_commit": args.blind_commit,
        "branch": branch["branch"],
        "branch_headline": head, "branch_body": body, "branch_detail": branch,
        "branch_text_shape": equiv_cfg["equiv_shape"],
        "negative_D_disclosure": negative_D_disclosure,
        "equiv_config": equiv_cfg,
        "halt_record": halt_doc,
        "preflight_resolution": pre_resolution,
        "superseded_rotations_REPORT_ONLY": rotations,
        "reachable_set": reachable_branches(equiv_cfg),
        "power": power_block(equiv_cfg, db.get("se_D")),
        "no_affordability_predicate": (
            "⛔ THERE IS NO AFFORDABILITY PREDICATE IN THIS PAIR. The b64 cell's "
            "A / W / OWNER_WAIVER.md machinery is ABSENT BY DESIGN: the N4 "
            "rho_wall <= 1.20 bar it enforced was WAIVED at B = 64 by "
            "b64_cell/OWNER_RULING_20260820.md. Cost is reported on EVERY branch "
            "and is a branch input NOWHERE. ⚠️ This absence is DECLARED rather "
            "than left to be noticed."),
        "D_block": db,
        "divergence": fb,
        "cells": {c: {k: cells[c].get(k) for k in
                      ("M", "z", "n_paired", "elo", "elo_sig_1sigma", "wr", "wr_z",
                       "W", "D_draws", "L", "n_games", "n_decks_seat_balanced",
                       "n_failed", "ms_ratio", "champ_prefix_ms_per_move",
                       "rung_ms_per_move", "phi", "arbiter_errors", "seat_balance",
                       "recomputed")}
                  for c in CELLS},
        "gates": {g: {"ok": ok, "scope": GATE_SCOPE[g], "marker": GATE_MARKER[g],
                      "detail": d} for g, (ok, d) in gates.items()},
        "gates_all_pass": all(preconditions.values()),
        "gates_failed": sorted(g for g, v in preconditions.items() if not v),
        "n_gates": len(gates),
        "per_cell_semantics": PER_CELL_SEMANTICS,
        "failure_surface_REPORT_ONLY": surf,
        "cost_facts": {
            "rho_wall": {"16": RHO_WALL_16, "32": RHO_WALL_32, "64": RHO_WALL_64,
                         "128": RHO_WALL_128},
            "n4_bar": N4_BAR,
            "n4_bar_status": ("⛔ WAIVED AND RETIRED at B = 64 by "
                              "b64_cell/OWNER_RULING_20260820.md ruling 1 — "
                              "printed as HISTORY, never as a test"),
            "per_move_wall_vs_champion": {"32": 1 + RHO_WALL_32,
                                          "64": 1 + RHO_WALL_64},
            "swapdown_prize": (f"≈{SWAPDOWN_PRIZE_S_PER_MOVE} s/move saved at the "
                               f"{CHAMP_BASELINE_S_PER_MOVE} s/move baseline = "
                               f"{SWAPDOWN_PRIZE_PCT}% of the per-move wall"),
            "rho_phone": {"32": list(RHO_PHONE_32), "64": list(RHO_PHONE_64)},
            "rho_phone_label": ("NOT SOLVED — a THIRD CURRENCY. The mobile profile "
                                "plays the UNMODIFIED champion and no branch here "
                                "changes that."),
            "worker_s_committed": WORKER_S_COMMITTED,
            "worker_s_realized": {c: None for c in CELLS},
            "ms_ratio_predicted": MS_RATIO_PREDICTED,
            "ms_ratio_realized": {c: cells[c].get("ms_ratio") for c in CELLS},
            "wall_committed_h": WALL_COMMITTED_H,
            "worker_h_committed": WORKER_H_COMMITTED,
            "effective_pool_workers": EFFECTIVE_POOL_WORKERS,
            "occupancy_derate": OCCUPANCY_DERATE,
            "field_name_trap": ("⚠️ champ_prefix_ms_per_move IS THE CANDIDATE SIDE "
                                "in eval_fair_puct (lines 2361/2371/2389 — the "
                                "opposite of eval_puct_priors). A read-out that "
                                "swaps them INVERTS the cost verdict."),
            "ms_ratio_is_never_a_branch_input": True,
            "smoke_vs_cells": ("⚠️ the smoke's ms_ratio and the cells' ms_ratio are "
                               "both printed and NEITHER grades the other: a bar "
                               "written after a smoke number exists is not a bar."),
            "cost_immunity": (
                "the two cells are NOT cost-matched (CELL_B64 spends ~1.60× the "
                "worker-seconds per game of CELL_B32), but NEITHER CANDIDATE'S "
                "SEARCH BUDGET MOVES: both run the identical champion at k8×1376 "
                "with identical sims and the arbiter fires AFTER the search, at "
                "the root, on an already-resolved tie ⇒ the extra cost buys NO "
                "extra search. It is a WALL-CLOCK ASYMMETRY and is disclosed as "
                "one on every branch, never claimed away."),
        },
        "phi_block": {
            "per_cell": {c: {"phi": cells[c].get("phi")} for c in CELLS},
            "offline_prior": PHI_PRIOR_OFFLINE,
            "committed": PHI_COMMITTED,
            "b64_cell_realized": list(PHI_B64CELL_REALIZED),
            "equality_assumption": (
                "DESIGN §7.2 assumes phi EQUAL across cells and STATES the "
                "assumption: the trigger predicate does not depend on B, so phi "
                "should be B-invariant AT THE SAME POSITION — but the cells "
                "diverge onto different boards, so realized phi can differ. The "
                "realized cross-cell difference is printed."),
        },
        "offline_ladder_DESCRIPTION_ONLY": {
            "arb_32": OFFLINE_ARB[32], "arb_64": OFFLINE_ARB[64],
            "delta_32_to_64": OFFLINE_DELTA_32_64,
            "ratio_64_over_32": OFFLINE_RATIO_64_OVER_32,
            "bracket_pts_per_game": list(EFFECT_BRACKET),
            "disclaimer": ("⛔ MUST NOT be presented as a projection of the game "
                           "effect. The offline ratio 1.038 is a DESCRIPTION of "
                           "the offline ladder; the bracket is a WIDTH, and "
                           "NEITHER ENDPOINT IS A PROJECTION."),
        },
        "carried_verbatim": {
            "translation_caveat": (
                "⚠️ The offline→game translation factor is not established. Stage "
                "1b's +0.1441 pts/tied ply predicts +0.79 pts/game (× phi 17.57 / "
                "non_additivity 3.2); Phase B realized +3.07 — a 3.9× "
                "under-prediction."),
            "translation_caveat_both_ways": (
                "CAMPAIGN ruling 5 binds in BOTH directions: Stage 1b's offline "
                "read under-predicted the Phase B game cell 3.9× … so the "
                "offline→game map is unestablished and +0.0670 × 3.9 is not a "
                "projection either."),
            "second_datum": (
                "the b64_cell's §5.2 bracket for Δ(16→64) was [+0.368, +1.435] and "
                "it realized +1.7167 — the map missed LOW TWICE, at n = 2, in the "
                "SAME direction. ⛔ Still not a licence to multiply."),
            "b64_cell_scope_fence": (
                "⛔ No branch re-adjudicates the b64_cell. Its verdict of record is "
                "B-COSTKILL, its read-rule is SPENT and its band 139e9 is RETIRED. "
                "No comparison against its numbers is a branch input anywhere."),
        },
        "cross_band_humility": {
            "four_rung_table": [
                {"B": 16, "band": 139000000000, "elo": 36.2644, "status": "RETIRED band"},
                {"B": 64, "band": 139000000000, "elo": 63.9457, "status": "RETIRED band"},
                {"B": 32, "band": BAND_EXPECTED, "elo": cells[CELL_LO].get("elo"),
                 "status": "this cell"},
                {"B": 64, "band": BAND_EXPECTED, "elo": cells[CELL_HI].get("elo"),
                 "status": "this cell"},
            ],
            "over_dispersion": "1.8–2.2× in BOTH statistics (CLAUDE.md)",
            "prohibition": (
                "⛔⛔ The 139e9 numbers MUST NOT be pooled with the 140e9 numbers, "
                "plotted as one curve without the band labels, or differenced to "
                "produce any estimate. Band 139e9 is RETIRED from confirmatory use "
                "and cannot support a new verdict at all. THE ONLY ROBUST CONTRAST "
                "IN THIS RUN IS THE WITHIN-BAND DECK-PAIRED D, and it is the only "
                "branch input. The table may be SHOWN, with its band column, as a "
                "DESCRIPTION — never fitted, differenced across bands, or called a "
                "curve measurement."),
        },
        "band": {"band_seed_start": BAND_EXPECTED,
                 "deck_range": f"{BAND_EXPECTED}..{BAND_DECK_MAX}",
                 "claim": claim,
                 "retires_at_closeout": ("the band is ONE-USE and retires from "
                                         "confirmatory use at close-out on EVERY "
                                         "branch")},
        "spec_vs_buildable": SPEC_VS_BUILDABLE,
        "governance": ("PRODUCTION.yaml is UNTOUCHED on every branch and no branch "
                       "mints a claim in CLAIM_REGISTRY.csv. L-SATURATED LICENSES "
                       "a swap-down DECISION for the owner; the owner executes it "
                       "with one word and the prereg never edits the file. This "
                       "read-rule is SPENT when the read-out lands, on every "
                       "branch, and band 140000000000 retires from confirmatory "
                       "use."),
    }


#: §4.3 item 6 — *"every §3 gate WITH ITS REALIZED VALUE"*. A PASS/FAIL column
#: alone is not the realized value, which is what R5 flagged.
def _gate_realized(gid: str, d: dict) -> str:
    def g(*path, default="n/a"):
        cur = d
        for p in path:
            cur = cur.get(p) if isinstance(cur, dict) else None
            if cur is None:
                return default
        return cur
    if gid == "G-J1":
        return "; ".join(f"{c}={(g('observed', c, 'cand_leaf_hash'))}"
                         for c in CELLS)
    if gid == "G-J4":
        return "; ".join(f"{c} tiearb_B={g('observed', c, 'tiearb_B')}"
                         for c in CELLS)
    if gid == "G-J13":
        return (f"{d.get('n_files_consumed', 0)} file(s) consumed, "
                f"expected_B={d.get('expected_B')}")
    if gid == "G-NEST":
        return f"witness={d.get('witness')}"
    if gid == "G-FIRE":
        return "; ".join(f"{c} phi_eff={_f(g('observed', c, 'phi_effective'), '.3f')}"
                         for c in CELLS)
    if gid == "G-DIVERGE":
        return (f"1−f0={_f(d.get('one_minus_f0'), '.4f')} vs floor "
                f"{d.get('floor')}"
                + (" ⚠️ ANOMALY" if d.get("anomaly") else ""))
    if gid == "G-BAND":
        return (f"band={g('band_seed_start', CELLS[0], 'band_seed_start')} "
                f"same_decks={d.get('same_decks')}")
    if gid == "G-N":
        return (f"n_common={d.get('n_common')} decks (floor "
                f"{d.get('n_common_floor')}); games={d.get('n_games')}")
    if gid == "G-FAILED":
        return (f"F_{CELL_HI}={d.get('F_' + CELL_HI)} "
                f"F_{CELL_LO}={d.get('F_' + CELL_LO)}, total "
                f"{d.get('n_failed_total')}")
    if gid == "G-TOOL":
        return f"builds={d.get('distinct_builds')}"
    if gid == "G-PLY":
        return "; ".join(
            f"{c}={g('observed', c, 'tiearb_partial_argmax_total')}" for c in CELLS)
    if gid == "G-STAT":
        return (f"UB95={_f(g('values', 'UB95'))} se_D>0="
                f"{d.get('se_D_positive')}")
    if gid == "G-SMOKE":
        # ⚠️ X3: conjunct 1 is the newest and most complex of the three, so it is
        # the one that must NOT be missing from the summary line.
        c1 = d.get("conjunct1_production_knobs_before_game_1") or {}
        c1s = ("not-evaluated" if c1.get("evaluated") is False
               else ("ok" if c1.get("ok") else "FIRES"))
        return (f"knobs/before-game-1={c1s} halt={d.get('halted')} "
                f"launched_anyway={d.get('launched_anyway')} outcome_keys="
                f"{len(d.get('forbidden_outcome_keys') or [])}")
    return "n/a"


def _n_to_resolve_line(blk: dict) -> str:
    """§4.1 branch 5 rider (ii), including its ⛔ NO-n edge case."""
    if blk.get("no_n_resolves_it"):
        return f"- ⛔ **{blk['why']}**"
    if blk.get("decks_per_cell") is None:
        return f"- `n` to resolve {blk.get('resolves_what', 'it')}: n/a — " \
               f"{blk.get('why', 'inputs absent')}"
    return (f"- `n` to resolve {blk['resolves_what']} at the realized dispersion: "
            f"**{blk['decks_per_cell']} decks/cell** / {blk['games_total']} games "
            f"total / **{blk['two_box_wall_hours']} two-box wall-h** "
            f"(at the measured {blk['effective_pool_workers']}-worker pool)")


def render(v: dict) -> str:
    L = ["# `B = 32` vs `B = 64` TIE-ARBITER LADDER GAME CELL — READ-OUT", "",
         f"generated: {v['generated_utc']}", "",
         f"## BRANCH: `{v['branch']}`", "",
         f"**{v['branch_headline']}**", "", v["branch_body"], ""]

    ec = v["equiv_config"]
    L += ["## The committed `EQUIV` bar — READ from `WORKERS.conf`, not from code",
          "",
          f"- `TOLERANCE_PTS` = **{ec['tolerance_pts']}** pts/game · "
          f"`EQUIV_SHAPE` = **`{ec['equiv_shape']}`**",
          f"- predicate: {ec['predicate']}",
          f"- source: `{ec['source']}` — ⛔ changing those two committed lines "
          f"changes this adjudicator with NO code edit; there is no default.", ""]

    if v.get("negative_D_disclosure"):
        L += [v["negative_D_disclosure"], ""]

    rs = v["reachable_set"]
    pw = v["power"]["pre_run"]
    L += ["## §4.0 — the reachable branch set, stated BEFORE the run", "",
          f"- reachable: {rs['reachable']}",
          f"- unreachable: **{rs['unreachable'] or 'none'}**",
          f"- modal pre-run expectation: **{rs['modal_pre_run_expectation']}** — "
          f"{rs['modal_note']}",
          f"- `L-SATURATED` window at the committed `se(D)`: "
          f"**{rs['saturated_window_at_committed_se']:.4f}** · "
          f"P(fires | true D = 0) = **{rs['power_at_true_D_zero_committed']}** "
          f"(EFFECTIVE; raw {pw['P_L_SATURATED_at_true_D_zero_RAW']}, "
          f"L-REVERSED takes {pw['P_L_REVERSED_mass']} first)",
          f"- at the offline bracket top: "
          f"**{pw['P_at_bracket_top_EFFECTIVE']}** (EFFECTIVE, committed law)",
          f"- `n` for 80% power: {pw['n_for_80pct_power_committed_law']} decks/cell "
          f"(committed law) / {pw['n_for_80pct_power_realized_law']} (realized law) "
          f"— {pw['n_for_80pct_note']}",
          f"- {rs['power_statement']}", "",
          f"## §4.3 item 6 — ALL {v['n_gates']} §3 gates, with their REALIZED "
          f"values, never short-circuited", "",
          "| gate | scope | marker | ok | realized |", "|---|---|---|---|---|"]
    for g, row in sorted(v["gates"].items()):
        L.append(f"| `{g}` | {row['scope']} | {row['marker']} | "
                 f"{'PASS' if row['ok'] else '**FAIL**'} | "
                 f"{_gate_realized(g, row['detail'])} |")
    if v.get("gates_failed"):
        L += ["", f"⛔ **FAILED: {v['gates_failed']}** — a failing gate SUPPRESSES "
                  f"the verdict.", ""]

    gj13 = v["gates"]["G-J13"]["detail"]
    L += ["", "### `G-J13` — RULING 4: the exact filenames consumed, per host", ""]
    for host, rows in sorted((gj13.get("files_consumed_per_host") or {}).items()):
        if not rows:
            L.append(f"- **{host}**: ⛔ **ZERO files consumed** — a zero-match "
                     f"glob reads as ZERO, never as a silent pass")
        for r in rows:
            L.append(f"- **{host}**: `{r['path']}` carried "
                     f"`j13_witness.B` = {r['j13_witness.B']}")
    rot = v.get("superseded_rotations_REPORT_ONLY") or []
    L += ["", f"- preflight resolution: {v['preflight_resolution']['mode']} · "
              f"{len(rot)} superseded rotation(s) excluded and recorded "
              f"(REPORT-ONLY, wired into NO conjunct — READ_RULE §2.2)", ""]

    d = v["D_block"]
    lo, hi = d.get("CI90_lo"), d.get("CI90_hi")
    L += ["", "## §4.3 item 2 — the `D` block: THE PRIMARY", "",
          f"- `D` = {_f(d['D'])} · `se_D` = {_f(d['se_D'], '.4f')} · "
          f"**`z_D` = {_f(d['z_D'], '+.4f')}** · `n_common` = {d['n_common']} decks",
          # ⭐ THE PRIMARY, half 2 — bolded, named, and NEVER called a 90% CI
          f"- ⭐ **`UB95(D)` = {_f(d.get('UB95'))}** — **{UB95_LABEL}** — against "
          f"the +{ec['tolerance_pts']} pts/game tolerance",
          f"- `CI90(D)` = [{_f(lo)}, {_f(hi)}] — {CI90_LABEL}",
          f"- realized `rho` = {_f(d.get('rho'), '+.4f')}",
          f"- committed `se(D)` = {SE_D_COMMITTED} · 2σ floor = "
          f"+{D_FLOOR_2SIGMA} · non-binding realized-dispersion projection = "
          f"{SE_D_REALIZED_PROJECTION}",
          f"- `EQUIV` ({ec['equiv_shape']}) = **{d['equiv']['EQUIV']}** — "
          f"{d['equiv']['why']}",
          f"- `n` to convict a 2σ COST at the realized dispersion: "
          f"{d['n_to_convict_2sigma_at_realized_dispersion'].get('decks_per_cell')}"
          f" decks",
          _n_to_resolve_line(d["n_to_convict_equivalence_at_realized_dispersion"]),
          ""]

    # ---- §4.3 item 1 — BOTH CELLS, in full -------------------------------- #
    L += ["## §4.3 item 1 — both cells", "",
          "| quantity | " + " | ".join(f"`{c}`" for c in CELLS) + " |",
          "|---|" + "---|" * len(CELLS)]
    cb = v["cells"]
    for label, key, spec in (
            ("`n` attempted (planned)", "_planned", None),
            ("`n` completed (games)", "n_games", None),
            ("decks seat-balanced", "n_decks_seat_balanced", None),
            ("`M` (pts/game)", "M", "+.4f"),
            ("`se` (recomputed)", "_se", ".4f"),
            ("`paired_z`", "z", "+.4f"),
            ("elo", "elo", "+.4f"),
            ("elo ±1σ", "elo_sig_1sigma", ".4f"),
            ("`wr`", "wr", ".4f"),
            ("`wr_z`", "wr_z", "+.4f"),
            ("W / D / L", "_wdl", None),
            ("seat balance", "seat_balance", None),
            ("`n_failed`", "n_failed", None)):
        cells_row = []
        for c in CELLS:
            if key == "_planned":
                val = CELL_GAMES_PLANNED
            elif key == "_se":
                val = (cb[c].get("recomputed") or {}).get("se")
            elif key == "_wdl":
                val = (f"{cb[c].get('W')} / {cb[c].get('D_draws')} / "
                       f"{cb[c].get('L')}")
            else:
                val = cb[c].get(key)
            cells_row.append(_f(val, spec) if spec else str(val))
        L.append(f"| {label} | " + " | ".join(cells_row) + " |")
    L += ["", f"- `n_common` = {v['D_block']['n_common']} decks", ""]

    f = v["divergence"]
    L += ["## §4.3 item 3 — the divergence block", "",
          f"- `f0` = {_f(f['f0'], '.4f')} · `1 − f0` = "
          f"{_f(f['one_minus_f0'], '.4f')} vs floor {f['floor']} — **beside the "
          f"EXPECTED ≈{f['expected_one_minus_f0']}** (≈{f['headroom_x']:.0f}× "
          f"headroom)",
          f"- dilution `√(1−f0)` = {_f(f['dilution_sqrt_one_minus_f0'], '.4f')}",
          ("- ⚠️ **ANOMALY: a realized `1 − f0` below 0.95 PASSES the gate and "
           "MUST be reported as an ANOMALY, never as a pass.**" if f["anomaly"]
           else "- (not flagged anomalous)"),
          f"- {f['measurement_disclosure']}", ""]

    # ---- §4.3 item 4 — the phi block --------------------------------------- #
    pb = v["phi_block"]
    L += ["## §4.3 item 4 — the `phi` block", ""]
    for c in CELLS:
        gf = (v["gates"]["G-FIRE"]["detail"].get("observed") or {}).get(c, {})
        L.append(f"- **`{c}`**: `phi` = {_f(pb['per_cell'][c]['phi'], '.4f')} · "
                 f"`phi_effective` = {_f(gf.get('phi_effective'), '.4f')} "
                 f"(error rate on fired {_f(gf.get('error_rate_on_fired'), '.5f')})")
    _phis = [pb["per_cell"][c]["phi"] for c in CELLS]
    L += [f"- cross-cell `phi` difference: "
          f"{_f((_phis[0] - _phis[1]) if all(_finite(x) for x in _phis) else None)}",
          f"- beside the offline prior **{pb['offline_prior']}**, the committed "
          f"**{pb['committed']}** and the b64 cell's realized "
          f"{pb['b64_cell_realized']}",
          f"- {pb['equality_assumption']}", ""]

    cf = v["cost_facts"]
    L += ["## Cost — reported on every branch, a branch input NOWHERE", "",
          f"- {v['no_affordability_predicate']}",
          f"- `rho_wall` 16/32/64/128 = {cf['rho_wall']['16']} / "
          f"{cf['rho_wall']['32']} / {cf['rho_wall']['64']} / "
          f"{cf['rho_wall']['128']} · N4 bar {cf['n4_bar']} — "
          f"{cf['n4_bar_status']}",
          f"- the prize: {cf['swapdown_prize']}",
          f"- `rho_phone` 32 {cf['rho_phone']['32']} / 64 {cf['rho_phone']['64']} "
          f"— **{cf['rho_phone_label']}**",
          f"- `ms_ratio` predicted {cf['ms_ratio_predicted']} vs realized "
          f"{ {k: _f(x, '.3f') for k, x in cf['ms_ratio_realized'].items()} }",
          f"- {cf['field_name_trap']}", f"- {cf['smoke_vs_cells']}",
          f"- {cf['cost_immunity']}", ""]

    # ---- §4.3 item 7 — the failed-record accounting IN FULL ---------------- #
    gfd = v["gates"]["G-FAILED"]["detail"]
    surf = v["failure_surface_REPORT_ONLY"]
    L += ["## §4.3 item 7 — the failed-record accounting, printed whether or not "
          "any failure occurred", ""]
    for c in CELLS:
        pc = (gfd.get("per_cell") or {}).get(c, {})
        s = (surf.get("per_cell") or {}).get(c, {})
        L.append(
            f"- **`{c}`**: `n_failed` = {pc.get('n_failed')} / `n_attempted` = "
            f"{pc.get('n_attempted')} ⇒ rate {_f(pc.get('rate'), '.5f')} vs the "
            f"{pc.get('rate_bar')} bar · `failure_rate` = {s.get('failure_rate')} "
            f"· `failure_rate_trigger` = {s.get('failure_rate_trigger')} · "
            f"`validity_trigger_fired` = {s.get('validity_trigger_fired')}")
        L.append(
            f"  - `tiearb_errors_total` = {s.get('tiearb_errors_total')} · "
            f"`tiearb_error_rate_on_fired` = "
            f"{s.get('tiearb_error_rate_on_fired')} · `tiearb_first_error` = "
            f"{s.get('tiearb_first_error')} · `tiearb_partial_argmax_total` = "
            f"{s.get('tiearb_partial_argmax_total')}")
        fcs = s.get("failed_cells") or []
        L.append(f"  - `failed_cells[]` ({len(fcs)} record(s)): "
                 + (json.dumps(fcs) if fcs else "none"))
        rfc = s.get("resolved_failed_cells") or []
        L.append(f"  - `resolved_failed_cells[]` ({len(rfc)}): "
                 + (json.dumps(rfc) if rfc else "none"))
    L += [f"- clause 2 (candidate-correlation): "
          f"{gfd.get('clause2_candidate_correlated')} — "
          f"{gfd.get('clause2_rule')}",
          f"- clause 3: {'HALT' if gfd.get('clause3_halt') else 'not triggered'}"
          + (" (vacuous at zero failures)"
             if gfd.get("clause3_vacuous_at_zero") else ""),
          f"- ⛔ **{surf['status']}**",
          f"- {gfd.get('selection_effect')}", ""]

    ol = v["offline_ladder_DESCRIPTION_ONLY"]
    L += ["## The offline ladder — a DESCRIPTION, explicitly NOT a projection", "",
          f"- `arb(32)` = {ol['arb_32']} · `arb(64)` = {ol['arb_64']} · "
          f"`Δ(32→64)` = +{ol['delta_32_to_64']} pts/tied ply · ratio "
          f"{ol['ratio_64_over_32']}",
          f"- the §5.2 bracket: {ol['bracket_pts_per_game']} pts/game",
          f"- {ol['disclaimer']}", ""]

    cv = v["carried_verbatim"]
    L += ["## Carried VERBATIM", ""] + [f"- **{k}**: {t}" for k, t in cv.items()]

    cb = v["cross_band_humility"]
    L += ["", "## ⛔⛔ Cross-band humility — MANDATORY, not optional prose", "",
          "| rung | band | elo vs the unmodified champion | status |",
          "|---|---|---|---|"]
    for r in cb["four_rung_table"]:
        L.append(f"| `B` = {r['B']} | {r['band']} | {_f(r['elo'], '+.4f')} | "
                 f"{r['status']} |")
    L += ["", f"- over-dispersion: {cb['over_dispersion']}",
          f"- {cb['prohibition']}", ""]

    # ---- §4.3 item 12 + 13 — the band, and the blind-commit ordering ------- #
    bnd = v["band"]
    hr = v.get("halt_record") or {}
    L += ["## §4.3 items 12–13 — the band, and this rule's own blind commit", "",
          f"- band **{bnd['band_seed_start']}**, decks {bnd['deck_range']} · "
          f"claim: {bnd['claim'].get('source') or 'n/a'} "
          f"(claimed_before_game_1 = {bnd['claim'].get('claimed_before_game_1')})",
          f"- {bnd['retires_at_closeout']}",
          f"- **blind commit: `{v.get('blind_commit') or 'NOT SUPPLIED'}`** — "
          f"`DESIGN.md` and `READ_RULE.md` landed in the SAME commit before game "
          f"1, and the band claim (2026-08-20) PREDATES that commit; that "
          f"ordering is itself printed here (DESIGN §12.2).",
          (f"- §9.3 HALT record: halt = **{hr.get('halt')}** "
           f"(realized {_f(hr.get('realized'), '.3f')} vs bar "
           f"{_f(hr.get('bar'), '.3f')}) — {hr.get('why', 'n/a')}"
           if hr else "- §9.3 HALT record: not supplied"), ""]

    if v.get("spec_vs_buildable"):
        L += ["## ⚠️ SPEC-vs-BUILDABLE — REPORTED, never resolved here", ""]
        for m in v["spec_vs_buildable"]:
            L += [f"- **{m['where']}** [{m['status']}] — {m['issue']}",
                  f"  - adjudicator: {m['adjudicator_behaviour']}",
                  f"  - resolution: {m['resolution']}"]
    L += ["", f"*{v['governance']}*", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode")

    a = sub.add_parser("adjudicate", help="the read-out")
    a.add_argument("--b64-summary", required=True)
    a.add_argument("--b64-manifest", required=True)
    a.add_argument("--b64-records", default=None)
    a.add_argument("--b32-summary", required=True)
    a.add_argument("--b32-manifest", required=True)
    a.add_argument("--b32-records", default=None)
    a.add_argument("--preflight", action="append", default=None,
                   help="OPTIONAL. By default the four NAMED addresses of "
                        "READ_RULE §2.2 are resolved from --verdicts-dir. A "
                        "supplied path that is a timestamped ROTATION is "
                        "REFUSED, never silently dropped.")
    a.add_argument("--verdicts-dir", default=str(CELL_DIR / "verdicts"),
                   help="where READ_RULE §2.2's four named preflight addresses "
                        "live; rotations found here are reported, never graded")
    a.add_argument("--gate-nest", default=None)
    a.add_argument("--band-claim", default=None)
    a.add_argument("--smoke", default=None)
    a.add_argument("--smoke-halt", default=str(CELL_DIR / SMOKE_HALT_RECORD),
                   help="DESIGN §9.3.1's HALT decision record. Read, not "
                        "written, here; absent ⇒ recomputed from SMOKE.json")
    a.add_argument("--workers-conf", default=str(WORKERS_CONF),
                   help="the committed constants block (TOLERANCE_PTS / "
                        "EQUIV_SHAPE) is READ from here — fail-closed, no "
                        "default; G-SMOKE's production-knobs conjunct also "
                        "compares field-by-field against it (DESIGN §9.2)")
    a.add_argument("--blind-commit", default=None)
    # ⛔ `--launched-after-halt` is DELETED (B6 / DESIGN §9.3.1). Its default was
    # the PASSING value, so the gate could only fire if the person it policed
    # chose to accuse themselves. `launched_anyway` is now DERIVED from
    # SMOKE_HALT.json ∧ the existence of real-cell records.
    a.add_argument("--failures-confirmed-by", default=None,
                   help="RULING 3: the HUMAN who confirmed every failure is the "
                        "known WindowTruncationError class. Gates ESCALATION "
                        "ONLY — it adjudicates nothing")
    a.add_argument("--failures-confirmed-note", default=None,
                   help="the confirmation, recorded verbatim in the read-out")
    a.add_argument("--out-dir", required=True)

    k = sub.add_parser("knowngood", help="the launch precondition (DESIGN §12.1)")
    k.add_argument("--b64-cell-dir", default=str(B64_CELL_DIR))
    k.add_argument("--share", default=None)
    k.add_argument("--workers-conf", default=str(WORKERS_CONF))
    k.add_argument("--out", default=None)

    n = sub.add_parser("nest-witness", help="emit the STRUCTURAL nest witness")
    n.add_argument("--out", default=None)

    s = sub.add_parser("smoke-check",
                       help="§9.2's TWO surfaces (RULING 1) + §9.3's HALT bar; "
                            "WRITES SMOKE_HALT.json and EXITS NON-ZERO ON A HALT")
    s.add_argument("--smoke", required=True)
    s.add_argument("--halt-out", default=str(CELL_DIR / SMOKE_HALT_RECORD),
                   help="DESIGN §9.3.1's HALT decision record — this mode is its "
                        "WRITER")

    g = sub.add_parser("aggregate-smoke",
                       help="emit SMOKE.json from the two smoke cells' artifacts")
    g.add_argument("--lo-dir", required=True, help=f"{CELL_LO}'s smoke cell dir")
    g.add_argument("--hi-dir", required=True, help=f"{CELL_HI}'s smoke cell dir")
    g.add_argument("--band", default=None)
    g.add_argument("--out", required=True)
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    mode = a.mode or "adjudicate"

    if mode == "knowngood":
        cfg = load_equiv_config(a.workers_conf)
        doc = knowngood_eval(a.b64_cell_dir, a.share, equiv_cfg=cfg)
        out = Path(a.out or (CELL_DIR / "KNOWNGOOD_EVAL.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")
        if doc.get("error"):
            print(f"[knowngood] ⛔ {doc['error']}", file=sys.stderr)
            print(f"[knowngood] -> {out}")
            return 1
        for g, r in sorted(doc.get("rows", {}).items()):
            mark = {"PASS": "PASS", "FAIL": "**FAIL**", "N-A": "N-A "}[r["status"]]
            extra = r.get("scaled") or r.get("mapped") or r.get("note") or ""
            print(f"[knowngood] {mark:8s} {g:10s} "
                  + (f"({extra[:70]})" if extra else ""))
        print(f"[knowngood] {doc['n_pass']}/{doc['n_evaluated']} evaluable rows "
              f"PASS; {doc['n_na']} N-A: {doc['na_rows']}")
        for g, cov in sorted((doc.get("rows_with_partial_conjunct_coverage")
                              or {}).items()):
            for cj, state in sorted(cov.items()):
                print(f"[knowngood] ⚠️ PARTIAL  {g:10s} {cj}: {state}")
        print(f"[knowngood] EQUIV bar READ from {doc['equiv_config']['source']}: "
              f"shape={doc['equiv_config']['equiv_shape']} "
              f"tolerance={doc['equiv_config']['tolerance_pts']}")
        print(f"[knowngood] branch machinery on the known-good numbers: "
              f"{doc['branch_on_known_good']['branch']} "
              f"⛔ NOT a verdict — {doc['known_good_verdict_of_record']} stands")
        print(f"[knowngood] -> {out}")
        return 0 if doc["all_evaluable_rows_pass"] else 1

    if mode == "nest-witness":
        doc = nest_witness()
        out = Path(a.out or (CELL_DIR / "NEST_WITNESS_STRUCTURAL.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print(f"[nest] structural witness = {doc['witness']} — {doc['why']}")
        print(f"[nest] ⚠️ this is the STRUCTURAL half only; the pinned "
              f"position/ply byte-identity run at 32 ⊂ 64 is gate_nest.py's")
        print(f"[nest] -> {out}")
        return 0 if doc["witness"] else 1

    if mode == "aggregate-smoke":
        doc = aggregate_smoke({CELL_LO: a.lo_dir, CELL_HI: a.hi_dir},
                              band=a.band, out_path=a.out)
        hi = doc["_cells"].get(CELL_HI, {})
        lo = doc["_cells"].get(CELL_LO, {})
        for name, c in ((CELL_HI, hi), (CELL_LO, lo)):
            print(f"[smoke] {name:9s} worker_secs_per_game = "
                  f"{_f(c.get('worker_secs_per_game'), '.3f')}  "
                  f"(Σ elapsed_s {c.get('elapsed_s_total')} / n "
                  f"{c.get('n_records_with_elapsed_s')})")
        realized = hi.get("worker_secs_per_game") or 0
        print(f"[smoke] §9.3 HALT bar: {CELL_HI} "
              f"{_f(realized, '.3f')} vs {SMOKE_HALT_BAR:.3f} "
              f"({SMOKE_HALT_MULTIPLE} x {WORKER_S_COMMITTED[CELL_HI]}) — "
              f"{'⛔ OVER (HALT)' if realized > SMOKE_HALT_BAR else 'under'}")
        print(f"[smoke] ⚠️ ONE-SIDED: an overrun HALTS, an underrun proceeds. "
              f"{CELL_LO}'s cost is PRINTED and graded NOWHERE (§9.4).")
        print(f"[smoke] ⚠️ This tool REPORTS; it adjudicates nothing.")
        print(f"[smoke] -> {a.out}")
        return 0

    if mode == "smoke-check":
        p = Path(a.smoke)
        if not p.is_file():
            print(f"[smoke] ⛔ SMOKE.json ABSENT at {p} — that is a MISSING "
                  f"ARTIFACT, not a whitelist violation.", file=sys.stderr)
            return 1
        smoke = json.loads(p.read_text())
        wl = smoke_whitelist_check(smoke)
        outcome = smoke_outcome_scan(smoke)
        realized = smoke.get("worker_secs_per_game")
        # ⭐ B6 / DESIGN §9.3.1 — THIS MODE IS THE HALT RECORD'S **WRITER**.
        hd = halt_record(smoke)
        halt_path = Path(a.halt_out)
        halt_path.parent.mkdir(parents=True, exist_ok=True)
        halt_path.write_text(json.dumps(hd, indent=2, sort_keys=True) + "\n")
        doc = {
            "surfaces": ("§9.2 defines TWO surfaces (RULING 1, VERBATIM). The "
                         "EMITTER whitelist is fail-closed on unlisted keys and "
                         "governs what SMOKE.json may contain. The G-SMOKE ROW "
                         "fires only on forbidden OUTCOME keys, at any depth. "
                         "Structural keys are expected and NEVER fire the row. A "
                         "reading that applies the emitter whitelist to the row "
                         "fails a known-good smoke."),
            "emitter_surface": wl,
            "gate_surface": {"ok": not outcome,
                             "forbidden_outcome_keys": outcome,
                             "scanned": "every key, at ANY depth"},
            "cost_definition": WORKER_SECS_DEFINITION,
            "worker_secs_per_game": realized,
            "halt_bar": SMOKE_HALT_BAR,
            "halt_bar_derivation": (f"{SMOKE_HALT_MULTIPLE} x "
                                    f"{WORKER_S_COMMITTED[CELL_HI]} (§9.3, graded "
                                    f"on {CELL_HI} only)"),
            "halt_record": hd,
            "halt_record_path": str(halt_path),
            "halt": hd["halt"],
            "one_sided": "an overrun HALTS, an underrun proceeds",
            "adjudicates": ("NOTHING about the CELLS — this tool REPORTS both "
                            "§9.2 surfaces. It DOES decide the §9.3 HALT, which "
                            "is a COST gate on whether the real cells launch at "
                            "all, and is a branch input NOWHERE."),
        }
        print(json.dumps(doc, indent=1))
        if outcome:
            print(f"\n[smoke] ⛔ G-SMOKE WOULD FIRE: forbidden OUTCOME key(s) "
                  f"{outcome} — §9.2 is COUNTS-AND-COST ONLY.", file=sys.stderr)
        if not wl["ok"]:
            print(f"\n[smoke] ⛔ EMITTER REFUSAL: key(s) outside §9.2's "
                  f"whitelist {wl['forbidden_present']} — the emitter surface is "
                  f"FAIL-CLOSED. ⚠️ This is NOT the G-SMOKE row.", file=sys.stderr)
        # ⭐ `halt` IS IN THE EXIT CONDITION (DESIGN §9.3.1's WRITER row): the
        # smoke leg cannot return success on an overrun.
        if hd["halt"]:
            print(f"\n[smoke] ⛔⛔ §9.3 HALT — {hd['why']}\n"
                  f"[smoke] {hd.get('on_halt', '')}\n"
                  f"[smoke] record -> {halt_path}", file=sys.stderr)
        else:
            print(f"[smoke] §9.3: under the bar — {hd['why']}", file=sys.stderr)
            print(f"[smoke] halt record -> {halt_path}", file=sys.stderr)
        return 0 if (wl["ok"] and not outcome and not hd["halt"]) else 1

    v = build_readout(a)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if v.get("status") == "HALT-OWNER-ESCALATION":
        (out_dir / "HALT_B32V64.json").write_text(
            json.dumps(v, indent=2, sort_keys=True, default=str))
        print(f"\n{'=' * 70}\n[b32v64] {v['headline']}\n{'=' * 70}",
              file=sys.stderr)
        for r in v["raw_failure_records"][:10]:
            print(f"[b32v64]   {r['cell']} seed={r['seed']} : "
                  f"{str(r['error'])[:160]}", file=sys.stderr)
        print(f"[b32v64] {v['how_to_clear']}", file=sys.stderr)
        print(f"[b32v64] ⚠️ {v['adjudicates']}", file=sys.stderr)
        print(f"[b32v64] -> {out_dir / 'HALT_B32V64.json'}")
        return 2
    (out_dir / "READOUT_B32V64.json").write_text(
        json.dumps(v, indent=2, sort_keys=True, default=str))
    (out_dir / "READOUT_B32V64.md").write_text(render(v))
    # ⭐ UB95(D) is THE PRIMARY, half 2 — it leads the console line, and CI90 is
    # printed after it as context (READ_RULE §1 / §4.3 item 2).
    print(f"[b32v64] branch = {v['branch']} | z_D = {_f(v['D_block']['z_D'])} | "
          f"UB95(D) = {_f(v['D_block']['UB95'])} "
          f"({UB95_LABEL}) vs tolerance "
          f"{v['equiv_config']['tolerance_pts']} | gates_all_pass = "
          f"{v['gates_all_pass']}")
    print(f"[b32v64] CI90(D) = [{_f(v['D_block']['CI90_lo'])}, "
          f"{_f(v['D_block']['CI90_hi'])}] — {CI90_LABEL}")
    print(f"[b32v64] EQUIV bar: shape={v['equiv_config']['equiv_shape']} "
          f"tolerance={v['equiv_config']['tolerance_pts']} "
          f"(READ from {v['equiv_config']['source']})")
    print(f"[b32v64] -> {out_dir / 'READOUT_B32V64.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
