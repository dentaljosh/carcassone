"""Tests for `scripts/tiletie/analyze_rung3_r5.py` — the rung-3 (`J > 4`) R5
read-out driver.

All hermetic: `tmp_path` only, no engine, no real corpus, and NOTHING is ever run
against `measurement/tiearb_widening_20260817/rung3_r5/`.

What is under test, in the order the READ_RULE cares about:

  1. the branch table is TOTAL and DISJOINT under read-in-order/first-match-wins,
     on BOTH the main table and the `R_ora`-degenerate sub-table;
  2. ⛔ P2 — TOKEN DISCIPLINE, INVERTED FROM R4: the fired branch's token appears
     and NO OTHER does, parametrized over ALL TWELVE rows so the bar is proved
     for every branch this run could fire, not just the one a fixture happens to
     produce; `VOID_S2` appears nowhere, unconditionally;
  3. ⛔ P1 — the S1-rider prohibition;
  4. end-to-end on synthetic records whose true `Delta_ora` is known BY
     CONSTRUCTION;
  5. the schema key set, the `[post-scoring]` marker list, and that
     `widening.gates` enumerates every §2 gate — NEVER short-circuited.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import pytest

WT = Path(__file__).resolve().parents[1]
TILETIE = WT / "scripts" / "tiletie"
if str(TILETIE) not in sys.path:
    sys.path.insert(0, str(TILETIE))

import analyze_rung3_r5 as R5                                       # noqa: E402
import analyze_widening as AW                                       # noqa: E402

PRED_LEGACY = AW.PRED_LEGACY                    # 1.400
PRED_DEDUPED = AW.PRED_DEDUPED                  # 1.244
PRED_D_LEGACY = AW.PRED_DELTA_LEGACY            # +0.1382
PRED_D_DEDUPED = AW.PRED_DELTA_DEDUPED          # +0.0842

MAIN_ROWS = ("X-CONFIRMED", "X-ABOVE", "X-PARTIAL", "X-BELOW", "X-FREE",
             "X-INCONCLUSIVE")
SUB_ROWS = tuple(r + "-D" for r in MAIN_ROWS)
ALL_ROWS = MAIN_ROWS + SUB_ROWS


# --------------------------------------------------------------------------- #
# helpers                                                                       #
# --------------------------------------------------------------------------- #
def stat(lo, hi, value="mid"):
    """A bootstrap stat in `AW`'s shape. `value` defaults to the CI midpoint."""
    if value == "mid":
        value = None if (lo is None or hi is None) else (lo + hi) / 2.0
    return {"value": value, "ci95": [lo, hi], "se_root": 0.01, "z": None,
            "n": 64, "n_roots": 12,
            "significant": bool(lo is not None and lo > 0)}


def _fin(x):
    return x is not None and x == x


def independent_rows(d_ora, r_ora, ora_j4):
    """READ_RULE §5's rows, RE-STATED from the rule rather than imported.

    Returns the ordered list of rows whose condition holds. This is deliberately
    a second, independent transcription: comparing it against
    `AW.decide_rung3` checks the implementation, where reusing the module's own
    predicates would only check that a function equals itself.
    """
    dlo, dhi, dv = d_ora["ci95"][0], d_ora["ci95"][1], d_ora.get("value")
    rlo, rhi = r_ora["ci95"][0], r_ora["ci95"][1]
    guard = not (_fin(ora_j4["ci95"][0]) and ora_j4["ci95"][0] > 0)
    hits = []
    if guard:
        if not (_fin(dlo) and _fin(dhi)):
            return ["X-INCONCLUSIVE-D"], True
        if dlo > 0 and _fin(dv) and dlo <= PRED_D_LEGACY <= dhi:
            hits.append("X-CONFIRMED-D")
        if dlo > PRED_D_LEGACY:
            hits.append("X-ABOVE-D")
        if dlo > 0 and dhi < PRED_D_LEGACY and dhi >= PRED_D_DEDUPED:
            hits.append("X-PARTIAL-D")
        if dlo > 0 and dhi < PRED_D_DEDUPED:
            hits.append("X-BELOW-D")
        if dlo <= 0 <= dhi and dhi < PRED_D_DEDUPED:
            hits.append("X-FREE-D")
        return (hits or ["X-INCONCLUSIVE-D"]), True
    if not (_fin(dlo) and _fin(dhi)):
        return ["X-INCONCLUSIVE"], False
    sig = dlo > 0
    if sig and _fin(rlo) and _fin(rhi) and rlo <= PRED_LEGACY <= rhi:
        hits.append("X-CONFIRMED")
    if sig and _fin(rlo) and rlo > PRED_LEGACY:
        hits.append("X-ABOVE")
    if sig and _fin(rhi) and rhi < PRED_LEGACY and rhi >= PRED_DEDUPED:
        hits.append("X-PARTIAL")
    if sig and _fin(rhi) and rhi < PRED_DEDUPED:
        hits.append("X-BELOW")
    if (not sig) and dlo <= 0 <= dhi and dhi < PRED_D_DEDUPED:
        hits.append("X-FREE")
    return (hits or ["X-INCONCLUSIVE"]), False


# --------------------------------------------------------------------------- #
# 1. BRANCH TABLE — TOTAL AND DISJOINT                                          #
# --------------------------------------------------------------------------- #
D_CIS = [
    (None, None),          # degenerate / absent
    (-0.30, -0.10),        # strictly negative
    (-0.02, 0.02),         # 0 inside, upper below +0.0842
    (-0.02, 0.30),         # 0 inside, upper above +0.0842
    (0.001, 0.05),         # significant, resolved below both magnitudes
    (0.05, 0.10),          # significant, upper in [0.0842, 0.1382)
    (0.10, 0.20),          # significant, +0.1382 inside
    (0.20, 0.40),          # significant, lower above +0.1382
]
R_CIS = [
    (None, None),
    (0.80, 1.10),          # upper below 1.244
    (1.25, 1.35),          # upper in [1.244, 1.400)
    (1.20, 1.60),          # 1.400 inside
    (1.60, 2.00),          # lower above 1.400
]
J4_LOS = [None, -0.5, 0.0, 0.4]         # guard fires unless lo > 0
ARB_CIS = [(None, None), (-0.20, -0.05), (-0.05, 0.05), (0.05, 0.20)]


def test_branch_table_is_total_and_disjoint():
    """Every input lands on EXACTLY ONE row; no input satisfies two rows.

    `total`  — a branch always fires and it is one of the twelve committed
               tokens (row 6 is the catch-all in each table).
    `disjoint` — AT MOST ONE non-catch-all row's condition holds for any input,
               so "read in order, first match wins" cannot change the verdict if
               someone re-orders the table. That is a stronger property than
               first-match-wins alone and it is what makes the table safe to
               read as a set of mutually exclusive findings.
    """
    n_guard = n_main = 0
    for dci, rci, j4lo, aci in itertools.product(D_CIS, R_CIS, J4_LOS, ARB_CIS):
        d_ora = stat(*dci)
        r_ora = stat(*rci)
        ora_j4 = stat(j4lo, None if j4lo is None else j4lo + 1.0)
        d_arb = stat(*aci)
        got = AW.decide_rung3(d_ora, r_ora, ora_j4, d_arb)
        hits, guard = independent_rows(d_ora, r_ora, ora_j4)
        n_guard += bool(guard)
        n_main += (not guard)

        # TOTAL
        assert got["branch"] in ALL_ROWS, (dci, rci, j4lo, got)
        assert got["guard_fired"] is guard, (dci, rci, j4lo)
        # the guard path must be on the sub-table and vice versa
        assert (got["branch"] in SUB_ROWS) is guard, (dci, rci, j4lo, got)

        # DISJOINT — at most one substantive row, so evaluation order is inert
        substantive = [h for h in hits
                       if h not in ("X-INCONCLUSIVE", "X-INCONCLUSIVE-D")]
        assert len(substantive) <= 1, (dci, rci, j4lo, hits)

        # FIRST MATCH WINS, and the row that fired genuinely holds
        assert got["branch"] == hits[0], (dci, rci, j4lo, hits, got)

        # the ratio is reported IFF the guard did not fire (READ_RULE §5's
        # CLOSED allow_null table: r_ora and ci95_r_ora go null TOGETHER)
        assert got["r_ora_reported"] is (not guard)

    assert n_guard and n_main, "the sweep must cover BOTH the guard path and " \
                               "the main table"


def test_branch_table_covers_every_row_at_least_once():
    """The sweep is not vacuous: every one of the twelve rows is reachable."""
    seen = set()
    for dci, rci, j4lo in itertools.product(D_CIS, R_CIS, J4_LOS):
        got = AW.decide_rung3(
            stat(*dci), stat(*rci),
            stat(j4lo, None if j4lo is None else j4lo + 1.0), stat(None, None))
        seen.add(got["branch"])
    assert seen == set(ALL_ROWS), sorted(set(ALL_ROWS) - seen)


def test_guard_is_a_pre_branch_guard_not_a_row():
    """`lower(CI95(ora_J4)) <= 0` routes to the sub-table BEFORE any row is read
    — including when the main table would have had a clean answer."""
    d_ora = stat(0.10, 0.20)
    r_ora = stat(1.20, 1.60)             # would be the main table's row 1
    assert AW.decide_rung3(d_ora, r_ora, stat(0.4, 1.4), stat(None, None)
                           )["branch"] == "X-CONFIRMED"
    got = AW.decide_rung3(d_ora, r_ora, stat(-0.1, 1.4), stat(None, None))
    assert got["guard_fired"] is True
    assert got["branch"].endswith("-D")
    assert got["r_ora_reported"] is False


# --------------------------------------------------------------------------- #
# emitter harness for the token / prohibition / schema tests                    #
# --------------------------------------------------------------------------- #
#: (d_ora CI, R_ora CI, ora_J4 lo) → the row it fires. Covers ALL TWELVE.
BRANCH_DRIVERS = {
    "X-CONFIRMED": ((0.10, 0.20), (1.20, 1.60), 0.4),
    "X-ABOVE": ((0.10, 0.20), (1.60, 2.00), 0.4),
    "X-PARTIAL": ((0.10, 0.20), (1.25, 1.35), 0.4),
    "X-BELOW": ((0.10, 0.20), (0.80, 1.10), 0.4),
    "X-FREE": ((-0.02, 0.02), (1.20, 1.60), 0.4),
    "X-INCONCLUSIVE": ((-0.02, 0.30), (1.20, 1.60), 0.4),
    "X-CONFIRMED-D": ((0.10, 0.20), (1.20, 1.60), -0.1),
    "X-ABOVE-D": ((0.20, 0.40), (1.20, 1.60), -0.1),
    "X-PARTIAL-D": ((0.09, 0.12), (1.20, 1.60), -0.1),
    "X-BELOW-D": ((0.001, 0.05), (1.20, 1.60), -0.1),
    "X-FREE-D": ((-0.02, 0.02), (1.20, 1.60), -0.1),
    "X-INCONCLUSIVE-D": ((-0.02, 0.30), (1.20, 1.60), -0.1),
}


def emit_synthetic(tmp_dir: Path, target: str, gates_ok=True):
    """Drive the EMITTER (not the loader) to a chosen row and write both files.

    Returns `(fired, json_text, md_text, verdict_dict)`.
    """
    dci, rci, j4lo = BRANCH_DRIVERS[target]
    d_ora, r_ora = stat(*dci), stat(*rci)
    ora_j4 = stat(j4lo, j4lo + 1.0)
    d_arb = stat(-0.20, -0.05) if target == "X-ABOVE" else stat(0.05, 0.20)
    decision = AW.decide_rung3(d_ora, r_ora, ora_j4, d_arb)
    assert decision["branch"] == target, (target, decision)

    xfree = R5.sanitized_xfree_window(AW.xfree_window(d_ora))
    params = R5.committed_parameters({"n2": 1060, "gate_floor": 1007}, None)
    gates = {}
    for name in ("G-CORPUS", "G-COMPLETE", "G-FAILED", "G-DDRAW"):
        gates[name] = R5._gate(name, gates_ok, f"READOUT::{name}",
                               None if gates_ok else f"{name} row FAILED",
                               floor=params["gate_floor"],
                               n2_committed=params["n2"])
    branch = R5.build_branch_block(decision, xfree, gates_ok,
                                  [] if gates_ok else sorted(gates))
    s2 = {"delta_ora": d_ora["value"], "ci95_ora": d_ora["ci95"],
          "se_ora": d_ora["se_root"], "z_ora": None, "significant_ora": True,
          "r_ora": r_ora["value"] if decision["r_ora_reported"] else None,
          "ci95_r_ora": r_ora["ci95"] if decision["r_ora_reported"] else None,
          "r_ora_reported": decision["r_ora_reported"],
          "ora_j4": ora_j4["value"], "ora_j4_ci95": ora_j4["ci95"],
          "ora_full": 1.0, "delta_arb": d_arb["value"],
          "ci95_arb": d_arb["ci95"], "n_capped": 1060, "n_roots": 977,
          "e_worlds": 16}
    failed = {"n_failed_rids": 0, "n_attempted": 1060, "rate": 0.0,
              "by_class": {}, "accounting": {},
              "corrected_expectation_r5": "R5's corpus sits slightly DEEPER "
                                          "than S1's.",
              "selection_effect_note": "S1's integers, not this run's."}
    verdict = R5.assemble_readout(
        s2=s2, branch=branch, xfree=xfree, gates=gates, gates_ok=gates_ok,
        s2_n=1060, failed=failed,
        supply_chain=R5.supply_chain_block(
            {"n_in": 1064, "n_positions": 1060}, {"d_internal": 0.0028},
            {"n_total_pairs": 6602}, {"n2": 1060}, params),
        d_draw={"d_draw_ran": True, "n_checked": 40, "agreement_rate": 1.0,
                "adjudicates": "nothing"},
        provenance={"estimator": "analyze_widening"},
        config={"stratum": R5.STRATUM})
    fired = verdict.pop("_fired_branch")
    js = json.dumps(verdict, indent=2, sort_keys=True, default=str)
    md = R5.render_md(verdict)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "READOUT_R5.json").write_text(js)
    (tmp_dir / "READOUT_R5.md").write_text(md)
    return fired, js, md, verdict


# --------------------------------------------------------------------------- #
# 2. ⛔ P2 — TOKEN DISCIPLINE, INVERTED FROM R4                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("target", sorted(BRANCH_DRIVERS))
def test_token_inversion_only_the_fired_branch_appears(tmp_path, target):
    """⛔ R4's rung 3 fired NO branch, so NO token could appear anywhere. R5
    fires ONE: its token appears legitimately, and no other may appear ANYWHERE
    in either emitted file. The non-fired rows must not be narrated as
    near-misses.

    ⚠️ The scan is MAXIMAL-MUNCH, not substring: `X-CONFIRMED` is a prefix of
    `X-CONFIRMED-D`, so a naive grep would read a legitimate sub-table firing as
    if the main-table row had also been printed.
    """
    out = tmp_path / target
    fired, js, md, _ = emit_synthetic(out, target)
    assert fired == target

    for label, text in (("READOUT_R5.json", js), ("READOUT_R5.md", md)):
        seen = R5.scan_branch_tokens(text)
        assert seen == {target}, (
            f"{label}: expected the fired token {target!r} and nothing else; "
            f"found {sorted(seen)}")
        forbidden = sorted(set(ALL_ROWS) - {target})
        assert not (seen & set(forbidden)), (label, sorted(seen & set(forbidden)))

    # the files on disk, re-read — the bar is about what was WRITTEN
    for name in ("READOUT_R5.json", "READOUT_R5.md"):
        assert R5.scan_branch_tokens((out / name).read_text()) == {target}


@pytest.mark.parametrize("target", sorted(BRANCH_DRIVERS))
def test_void_s2_token_never_appears(tmp_path, target):
    """⛔ UNCONDITIONAL: `VOID_S2` must not appear at all. R5 is the SUCCESSOR to
    that void, not a continuation of it — and `AW.void_rung3_block` /
    `AW.VOID_S2` are never called or copied by this tool."""
    _, js, md, _ = emit_synthetic(tmp_path / target, target)
    for label, text in (("READOUT_R5.json", js), ("READOUT_R5.md", md)):
        assert AW.VOID_S2 not in text, label
        assert R5.VOID_TOKEN_FORBIDDEN not in text, label


@pytest.mark.parametrize("target", ["X-ABOVE", "X-FREE-D"])
def test_mandatory_prints_present_on_every_branch(tmp_path, target):
    """READ_RULE §5's THREE mandatory prints appear on whichever row fires — and
    print (iii) still says what it must WITHOUT spelling the 'cap was free'
    row's token, which P2 forbids on any branch but that one."""
    fired, js, md, v = emit_synthetic(tmp_path / target, target)
    mp = v["widening"]["branch"]["mandatory_prints"]

    # (i) separability, stated without naming the partial-resolution row
    assert "1.400" in mp["i_separability_1400_vs_1244"]
    assert "1.244" in mp["i_separability_1400_vs_1244"]
    assert "0.054" in mp["i_separability_1400_vs_1244"]
    assert not R5.scan_branch_tokens(mp["i_separability_1400_vs_1244"])

    # (ii) the corrected magnitude is unresolved at the top of the bracket
    assert "+0.0842" in mp["ii_0842_unresolved_at_bracket_top"]
    assert "1.995" in mp["ii_0842_unresolved_at_bracket_top"]
    assert "1.4" in mp["ii_0842_unresolved_at_bracket_top"]

    # (iii) the attainability window AT THE REALIZED se, named by the schema's
    # own lowercase key rather than by the row's token
    iii = mp["iii_attainability_window_at_realized_se"]
    assert "xfree_window" in iii
    assert "cap being free" in iii
    assert not R5.scan_branch_tokens(iii)
    assert set(mp["iii_window"]) >= {"lo", "hi", "half_width", "empty"}
    # and the whole print block still carries no stray token
    assert not (R5.scan_branch_tokens(json.dumps(mp)) - {fired})
    assert "xfree_window" in md


def test_xfree_window_numeric_fields_are_verbatim_from_analyze_widening():
    """The re-prosed window recomputes NOTHING: every numeric field is `AW`'s."""
    d_ora = stat(-0.03, 0.05)
    raw = AW.xfree_window(d_ora)
    san = R5.sanitized_xfree_window(raw)
    for k in ("half_width", "lo", "hi", "empty",
              "requires_negative_point_estimate", "point_estimate",
              "reachable_for_point_estimate"):
        assert san[k] == raw[k], k
    # only the prose changed, and only to drop the token
    assert R5.scan_branch_tokens(raw["note"])          # AW's note names the row
    assert not R5.scan_branch_tokens(san["attainability"])


def test_gate_failure_prints_no_branch_token_at_all(tmp_path):
    """§2 + §7: any gate FAIL ⇒ `W-UNREADABLE`, nothing licensed, and the branch
    table's verdict is NOT printed — a fixing session stays blind."""
    fired, js, md, v = emit_synthetic(tmp_path / "unreadable", "X-CONFIRMED",
                                      gates_ok=False)
    assert fired == "W-UNREADABLE"
    assert v["widening"]["branch"]["licensed"] is False
    assert R5.scan_branch_tokens(js) == set()
    assert R5.scan_branch_tokens(md) == set()
    assert "GATE INPUTS ONLY" in md


# --------------------------------------------------------------------------- #
# 3. ⛔ P1 — THE S1-RIDER PROHIBITION                                            #
# --------------------------------------------------------------------------- #
def _numeric_leaves(obj):
    if isinstance(obj, bool) or isinstance(obj, (int, float)):
        return [obj]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in _numeric_leaves(v)]
    if isinstance(obj, list):
        return [x for v in obj for x in _numeric_leaves(v)]
    return []


@pytest.mark.parametrize("target", ["X-ABOVE", "X-CONFIRMED-D"])
def test_s1_riders_carry_no_value_only_their_absence_witness(tmp_path, target):
    """⛔ `widening.j_rider.s1_replication.*` and `widening.j_rider.interaction.*`
    are S1 quantities and R5 HAS NO S1 STRATUM.

    They may be absent, or null WITH THEIR WITNESS — and may NEVER be reported
    as if measured. A rider with no stratum behind it is not a weak result; it
    is not a result.
    """
    _, js, _, v = emit_synthetic(tmp_path / target, target)
    riders = v["widening"]["j_rider"]
    for key in ("s1_replication", "interaction"):
        if key not in riders:
            continue                    # absence satisfies the prohibition
        blk = riders[key]
        assert blk["value"] is None, key
        assert blk["ci95"] is None, key
        # NO number, NO CI and NO boolean anywhere under the subtree: a boolean
        # is still a measurement-shaped answer to a question never asked
        assert _numeric_leaves(blk) == [], (key, _numeric_leaves(blk))
        assert "NO S1 STRATUM" in blk["witness"].upper(), key
        assert "not a result" in blk["witness"] or \
               "no result" in blk["witness"], key

    # and the witness travels WITH the address in the emitted JSON
    reloaded = json.loads(js)["widening"]["j_rider"]
    for key in ("s1_replication", "interaction"):
        assert reloaded[key]["value"] is None
        assert _numeric_leaves(reloaded[key]) == []


def test_s1_rider_prohibition_is_not_the_r4_void_text():
    """⛔ `AW.S1_RIDER_PROHIBITION` is the R4 VOID-era text ('no primary to ride
    on'), and it names an `X-`branch. R5's witness is its own sentence: the
    riders have no STRATUM, which is a different and stronger absence."""
    assert R5.S1_ABSENCE_WITNESS != AW.S1_RIDER_PROHIBITION
    assert "X-branch" not in R5.S1_ABSENCE_WITNESS
    assert not R5.scan_branch_tokens(R5.S1_ABSENCE_WITNESS)


# --------------------------------------------------------------------------- #
# 4. END-TO-END on synthetic records with a KNOWN Delta_ora                      #
# --------------------------------------------------------------------------- #
M_WORLDS = 32
E_WORLDS = 16
LEG_SHA = "a" * 64
EXCL_SHA = "b" * 64

#: 8 rids over 3 roots, arm counts 3-5. `D` is the per-row `Delta_ora` that the
#: constants below make TRUE BY CONSTRUCTION.
SYNTH_RIDS = [
    # (rid,             root,  n_arms, D)
    ("tt_sp_900000001_p10", "sp_900000001", 5, 1.0),
    ("tt_sp_900000001_p20", "sp_900000001", 4, 1.0),
    ("tt_sp_900000001_p30", "sp_900000001", 3, 2.0),
    ("tt_sp_900000002_p10", "sp_900000002", 5, 1.0),
    ("tt_sp_900000002_p20", "sp_900000002", 5, 2.0),
    ("tt_sp_900000002_p30", "sp_900000002", 4, 1.0),
    ("tt_sp_900000003_p10", "sp_900000003", 3, 1.0),
    ("tt_sp_900000003_p20", "sp_900000003", 5, 2.0),
]
#: mean over ROWS (RootBoot.stat's `value` is sum(vals)/n, a plain row mean)
EXPECTED_DELTA_ORA = sum(d for _, _, _, d in SYNTH_RIDS) / len(SYNTH_RIDS)


def arm_constants(n_arms, d):
    """Per-arm constant world values, chosen so `Delta_ora == d` EXACTLY.

    index 0        = the champion comparator, 0.0 (in BOTH pools)
    index 1        = +1.0, the best arm INSIDE the `J=4` subset ⇒ ora_J4 = 1.0
    indices 2..n-2 = -1.0, filler inside the subset
    index n-1      = +1.0 + d, the arm OUTSIDE the subset ⇒ ora_full = 1.0 + d

    Cross-fit selection picks the argmax of the SELECTION half and prices it on
    the disjoint EVALUATION half; with constants both halves agree, so
    `ora = max - champ` exactly, in both parity folds, and
    `Delta_ora = ora_full - ora_J4 = d`. Every value is an exact binary float,
    so the assertion is an EQUALITY, not a tolerance.
    """
    vals = [0.0, 1.0] + [-1.0] * max(0, n_arms - 3) + [1.0 + d]
    assert len(vals) == n_arms
    return vals


def write_synth_run(root: Path, *, break_gate=None) -> Path:
    """A complete, gate-passing synthetic RUN in the real on-disk layout."""
    run = root / "run"
    (run / "corpus" / f"positions_{R5.STRATUM}").mkdir(parents=True, exist_ok=True)

    arms_index, ladder = {}, {}
    for rid, rootid, n_arms, d in SYNTH_RIDS:
        base = 1000 + 10 * len(arms_index)
        arms = [base + j for j in range(n_arms)]
        n_j4 = min(4, n_arms - 1)
        arms_index[rid] = {
            "arms": arms, "arms_full": list(arms),
            "subset_j4": arms[:n_j4], "subset_j4_id": f"sub{len(arms_index)}",
            "root_id": rootid, "ply": 40 + len(arms_index),
            "deck_seed": 900000000 + len(arms_index),
            "cap_seed": 111000 + len(arms_index),
            "champ_arm_action": arms[0], "champ_arm_index": 0,
            "champ_action": arms[0], "capped_at_4": True, "capped": False,
            "champ_outside_tieset": False, "n_distinct_afterstates": n_arms,
            "stratum": "selfplay", "rules_profile": "walled",
            "phase_bucket": "mid", "tie_size_exact": n_arms,
        }
        for r in range(1, n_arms):
            ladder.setdefault(r, 0)
            ladder[r] += 1

    (run / "ARMS_R5.json").write_text(json.dumps(arms_index, indent=1,
                                                 sort_keys=True))
    arms_sha = R5._sha256(run / "ARMS_R5.json")
    n2 = len(arms_index)
    max_leg = max(ladder)
    leg_ladder = [ladder.get(r, 0) for r in range(1, max_leg + 1)]
    n_pairs = sum(leg_ladder)

    # ---- the record tree, both judges, real layout ------------------------- #
    for judge in (R5.JUDGE_ORACLE, R5.JUDGE_ARBITER):
        for rid, rootid, n_arms, d in SYNTH_RIDS:
            vals = arm_constants(n_arms, d)
            meta = arms_index[rid]
            for r in range(1, n_arms):
                rd = (run / "legs" / R5.STRATUM / judge / "walled" / f"leg{r}"
                      / "records")
                rd.mkdir(parents=True, exist_ok=True)
                rec = {
                    "rid": rid, "root_id": rootid, "ply": meta["ply"],
                    "deck_seed": meta["deck_seed"],
                    "pick_a": meta["arms"][0], "pick_b": meta["arms"][r],
                    "m": M_WORLDS, "oracle_policy": judge,
                    "world_seed_salt": R5.WORLD_SEED_SALT,
                    "values_a": [vals[0]] * M_WORLDS,
                    "values_b": [vals[r]] * M_WORLDS,
                    "per_world_delta": [vals[r] - vals[0]] * M_WORLDS,
                    "delta": vals[r] - vals[0],
                    "afterstate_deck_hash_a": ["h"] * M_WORLDS,
                    "afterstate_deck_hash_b": ["h"] * M_WORLDS,
                    "crn_verified": True, "checksum_ok": True, "ok": True,
                    "elapsed_secs": 1.0,
                }
                (rd / f"{rid}.json").write_text(json.dumps(rec))
            for r in range(1, n_arms):
                mp = (run / "legs" / R5.STRATUM / judge / "walled" / f"leg{r}"
                      / "manifest.json")
                mp.write_text(json.dumps({"resolved_config": {
                    "m": M_WORLDS, "world_seed_salt": R5.WORLD_SEED_SALT,
                    "legal_mask_cache": True}}))

    # ---- artifacts --------------------------------------------------------- #
    excluded = ["tt_sp_135000000839_p2", "tt_sp_137000002154_p2",
                "tt_sp_137000003379_p2", "tt_sp_137000004174_p2"]
    (run / "CORPUS_R5.json").write_text(json.dumps({
        "leg_path": str(run / "corpus" / "leg1.jsonl"), "leg_sha256": LEG_SHA,
        "r4_exclusion_list_sha256": EXCL_SHA, "n_in": n2 + 4,
        "n_excluded_r5": 4, "n_positions": n2, "excluded_rids": excluded,
        "arms_r5_sha256": arms_sha, "n_distinct_seeds": n2,
        "n_out_of_band": 0, "n_seeds_136e9": 0, "max_positions_per_seed": 3,
        "provenance": "synthetic",
        "seed_ranges": {"banked_135e9": [135000000350, 135000000849],
                        "extension_137e9": [137000000508, 137000005347],
                        "released_unused": 136000000000}}))
    (run / "FLOORS_R5.json").write_text(json.dumps({
        "n2": n2, "gate_floor": n2, "floor_fraction": 0.95, "min_ply": 0,
        "cap_j": None, "deployed_cap_j": 4, "m_worlds": M_WORLDS,
        "failed_record_bound_frac": 0.02,
        "corpus_provenance": {"leg_sha256": LEG_SHA,
                              "r4_exclusion_list_sha256": EXCL_SHA},
        "population_authority": {"identity": "asserted BOTH directions at "
                                             "build time"}}))
    (run / "STAGING_R5.json").write_text(json.dumps({
        "arms_copy_identical": True, "arms_r5_sha256": arms_sha,
        "staged_arms_sha256": arms_sha, "rid_sets_equal": True,
        "missing_in_leg": [], "missing_in_arms": [], "n_arms_rids": n2,
        "n_leg_rids": n2, "stage_chunks_rid_set_agrees": True, "n_chunks": 1,
        "leg_ladder_expected": leg_ladder, "n_total_pairs": n_pairs}))
    (run / "GATE_INTERNAL_DUPE.json").write_text(json.dumps({
        "d_internal": 0.0028, "n_dupe_groups": 3, "n_dupe_positions": 6,
        "ply_histogram": {"2": 6},
        "band_pairs": ["137e9<->137e9"] * 3, "leg_sha256": LEG_SHA}))
    (run / "GATE_DISJOINT_R5.json").write_text(json.dumps({
        "passed": True, "comparisons": {
            "base_vs_extension": {"layers": {"a_root_id": {"n_intersection": 0},
                                             "b_rid": {"n_intersection": 0}}}}}))
    (run / "GATE_DRAW_R5.json").write_text(json.dumps({
        "ok": True, "n_mismatch": 0, "deployed_cap_j": 4, "n_checked": n_pairs}))
    (run / "GATE_BITEXACT_HEAD.json").write_text(json.dumps({
        "pass": True, "digests_equal": True, "n_value_mismatch": 0}))
    (run / "MERGE_REPORT_s2.json").write_text(json.dumps({
        "ok": True, "problems": [], "dry_run": False,
        "n_records_present": n_pairs * 2}))
    (run / "D_DRAW.json").write_text(json.dumps({
        "n_checked": 40, "n_agree": 40, "agreement_rate": 1.0,
        "n_unreconstructible": 0}))
    preflight = {"ok": True, "checks": {
        "leaf_hash": {"ok": True, "harness_leaf_hash": "a36d2e15a3b3d71d",
                      "expected": "a36d2e15a3b3d71d"},
        "m": {"ok": True, "m": M_WORLDS, "b_ceiling": 16}}}
    (run / "SMOKE_R5.json").write_text(json.dumps({
        "m_worlds": M_WORLDS, "crn_cross_leg_identical": True,
        "preflight": preflight}))
    backend_by_leg = {f"{j}/walled/leg{r}": "rust"
                      for j in (R5.JUDGE_ORACLE, R5.JUDGE_ARBITER)
                      for r in range(1, max_leg + 1)}
    (run / "RUN_MANIFEST_R5.json").write_text(json.dumps({
        "m_worlds": M_WORLDS, "b_ceiling_from_m": 16,
        "world_seed_salt": R5.WORLD_SEED_SALT, "arb_backend": "rust",
        "arb_legal_mask_cache": True,
        "resolved_backend_by_leg": backend_by_leg, "preflight": preflight}))
    (run / "corpus" / f"positions_{R5.STRATUM}" / "POSITIONS_PLAN.json"
     ).write_text(json.dumps({
         "uncapped": True, "cap_j": None, "deployed_cap_j": 4,
         "m_worlds": M_WORLDS,
         "afterstate_dedupe": {"applied": True}}))

    if break_gate == "G-DISJOINT":
        # a LEAKAGE violation: the rid layer is non-zero on one comparison
        (run / "GATE_DISJOINT_R5.json").write_text(json.dumps({
            "passed": False, "comparisons": {
                "base_vs_extension": {"layers": {
                    "a_root_id": {"n_intersection": 0},
                    "b_rid": {"n_intersection": 7}}}}}))
    return run


@pytest.fixture(scope="module")
def synth_run(tmp_path_factory):
    return write_synth_run(tmp_path_factory.mktemp("r5"))


@pytest.fixture(scope="module")
def synth_readout(synth_run):
    out = synth_run / "verdicts"
    rc = R5.main(["--run", str(synth_run), "--emit-fixture"])
    assert rc == 0, rc
    return json.loads((out / "READOUT_R5.json").read_text()), \
        (out / "READOUT_R5.md").read_text(), synth_run


def test_end_to_end_delta_ora_is_the_constructed_value(synth_readout):
    """The whole pipeline, on records whose true `Delta_ora` is known BY
    CONSTRUCTION — an EQUALITY, not a tolerance, because every constant is an
    exact binary float and the cross-fit reduces to `max - champ`."""
    v, _, _ = synth_readout
    s2 = v["widening"]["j_rider"]["s2"]
    assert s2["n_capped"] == len(SYNTH_RIDS)
    assert s2["e_worlds"] == E_WORLDS       # M = 32 ⇒ parity halves of 16
    assert s2["delta_ora"] == pytest.approx(EXPECTED_DELTA_ORA, abs=0.0)
    # ora_J4 is exactly 1.0 on every row by construction, so the pre-branch
    # guard must NOT fire and the ratio IS reported
    assert s2["ora_j4"] == pytest.approx(1.0, abs=0.0)
    assert s2["r_ora_reported"] is True
    assert s2["r_ora"] == pytest.approx(1.0 + EXPECTED_DELTA_ORA, abs=0.0)
    assert s2["ci95_ora"][0] > 0            # significant on the root bootstrap


def test_end_to_end_fires_the_expected_branch(synth_readout):
    """`R_ora = 2.375` with a bootstrap lower bound far above 1.400 ⇒ the
    'above the legacy prediction' row, on the MAIN table (no guard)."""
    v, md, _ = synth_readout
    br = v["widening"]["branch"]
    assert v["widening"]["gates_ok"] is True, \
        sorted(n for n, g in v["widening"]["gates"].items() if not g["ok"])
    assert br["fired"] == "X-ABOVE"
    assert br["licensed"] is True
    assert br["guard_fired"] is False
    assert "X-ABOVE" in md
    # P2 again, on the REAL pipeline output rather than the emitter harness
    assert R5.scan_branch_tokens(json.dumps(v)) == {"X-ABOVE"}
    assert R5.scan_branch_tokens(md) == {"X-ABOVE"}
    assert AW.VOID_S2 not in md and AW.VOID_S2 not in json.dumps(v)


def test_end_to_end_leg_tree_thinning_is_exactly_predicated(synth_readout):
    """G-STAGED's EXACT per-leg predicate: `set(leg_r rids) == {rid : len(arms)
    > r}`. ⚠️ 'subset' is too weak — a truncated leg is what the adopted R4
    build shipped."""
    v, _, _ = synth_readout
    per_leg = v["widening"]["gates"]["G-STAGED"]["detail"]["per_leg"]
    assert per_leg, "no legs were checked"
    for name, row in per_leg.items():
        assert row["exact"] is True, (name, row)
        assert row["n_missing"] == 0 and row["n_extra"] == 0, (name, row)


def test_dry_run_writes_nothing(synth_run, tmp_path):
    out = tmp_path / "dry"
    rc = R5.main(["--run", str(synth_run), "--out-json", str(out / "R.json"),
                  "--out-md", str(out / "R.md"), "--dry-run"])
    assert rc == 0
    assert not (out / "R.json").exists()
    assert not (out / "R.md").exists()


def test_refuses_to_overwrite_an_existing_readout(synth_run, synth_readout):
    """A superseded read-out is EVIDENCE and stays readable; what must be
    impossible is mistaking it for a verdict (§D4.18(d))."""
    with pytest.raises(SystemExit) as exc:
        R5.main(["--run", str(synth_run)])
    assert "REFUSING to overwrite" in str(exc.value)


def test_population_authority_is_read_not_re_derived(synth_run, tmp_path):
    """DESIGN ruling 2026-08-19 shape (a): the analyzer READS `ARMS_R5.json`.
    Shape (b) — deriving the population by subtraction — is D4 with the operands
    swapped, and the tool refuses rather than improvising one."""
    with pytest.raises(SystemExit) as exc:
        R5.main(["--run", str(synth_run), "--arms", str(tmp_path / "nope.json"),
                 "--out-json", str(tmp_path / "a.json"),
                 "--out-md", str(tmp_path / "a.md")])
    msg = str(exc.value)
    assert "population authority" in msg and "subtraction" in msg


# --------------------------------------------------------------------------- #
# 5. SCHEMA, MARKERS, AND THE NEVER-SHORT-CIRCUITED GATE SET                     #
# --------------------------------------------------------------------------- #
def _addr_present(doc, dotted):
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def test_every_schema_address_is_emitted(synth_readout):
    v, _, _ = synth_readout
    missing = [a for a in R5.SCHEMA_ADDRESSES if not _addr_present(v, a)]
    assert not missing, missing


def test_marker_block_lists_every_address_as_post_scoring(synth_readout):
    """§1: every address carries EXACTLY ONE existence-time marker, and every
    address this file writes is `[post-scoring]`. ⭐ The marker LIST is emitted
    explicitly so `A1` audits the list — an address added without its fixture
    entry must FAIL `A1` rather than pass silently."""
    v, _, _ = synth_readout
    mk = v["widening"]["markers"]
    assert mk["marker"] == "[post-scoring]"
    assert mk["addresses"] == list(R5.SCHEMA_ADDRESSES)
    assert mk["n_addresses"] == len(R5.SCHEMA_ADDRESSES)
    assert "A1" in mk["audited_by"]


def test_a1_fixture_key_set_equals_the_schema_address_set(synth_readout):
    """The `A1` fixture: key set == the schema's address set, TYPES ONLY."""
    v, _, run = synth_readout
    fx_path = Path(v["provenance"]["fixture"]["path"])
    assert fx_path.is_file()
    fixture = json.loads(fx_path.read_text())

    def leaves(obj, prefix=""):
        out = []
        for k, val in obj.items():
            addr = f"{prefix}{k}"
            if isinstance(val, dict):
                out += leaves(val, addr + ".")
            else:
                out.append((addr, val))
        return out

    got = dict(leaves(fixture))
    assert sorted(got) == sorted(R5.SCHEMA_ADDRESSES)
    # TYPES ONLY: every leaf is a JSON-type NAME, never an exemplar value
    for addr, val in got.items():
        assert isinstance(val, str), (addr, val)
        assert val == R5.SCHEMA_TYPES[addr]


def test_fixture_naming_conflict_is_recorded_not_resolved(synth_readout):
    """⚠️ The DESIGN's fixture list and its execution-layer ruling disagree on
    the filename. The tool PREFERS `READOUT_R5`, ACCEPTS `READOUT`, and RECORDS
    which it used — the conflict is disclosed, not silently decided."""
    v, md, _ = synth_readout
    fx = v["provenance"]["fixture"]
    assert fx["name_used"] == R5.FIXTURE_PREFERRED
    assert fx["accepted_alternative"] == R5.FIXTURE_ACCEPTED
    assert "READOUT.fixture.json" in fx["conflict"]
    assert "READOUT_R5.fixture.json" in fx["conflict"]
    assert R5.FIXTURE_NAMING_CONFLICT in md


#: READ_RULE §2's gate set, `G-REPLICATE` excluded because §0 DROPS it —
#: deliberately, and with a sentence rather than silently.
EXPECTED_GATES = {
    "G-CORPUS", "G-STAGED", "G-INTERNAL-DUPE", "G-DISJOINT", "G-BAND",
    "G-COMPLETE", "G-FAILED", "G-M", "G-SALT", "G-BACKEND", "G-DDRAW",
    "G-LEAF", "G-PREFIX", "G-CRN", "G-UNCAPPED", "G-DRAW", "G-ARMS",
    "G-BITEXACT@HEAD", "G-TWOBOX",
}


def test_gates_enumerate_every_section_2_row(synth_readout):
    v, _, _ = synth_readout
    gates = v["widening"]["gates"]
    assert set(gates) == EXPECTED_GATES, (
        sorted(EXPECTED_GATES - set(gates)), sorted(set(gates) - EXPECTED_GATES))
    for name, g in gates.items():
        assert isinstance(g["ok"], bool), name
        assert g["resolved_at"], name
    # the dropped gate is named WITH its reason — R2's objection was the
    # silence, not the drop
    assert "G-REPLICATE" in v["widening"]["gates_dropped"]
    assert "S1" in v["widening"]["gates_dropped"]["G-REPLICATE"]


def test_a_failing_gate_does_not_short_circuit_the_rest(tmp_path):
    """⛔ A gate set that stops at the first failure is a gate set whose later
    rows were never checked — and 'not checked' reads on the page as 'passed'.
    Break the LEAKAGE gate and assert every other row still resolves."""
    run = write_synth_run(tmp_path, break_gate="G-DISJOINT")
    rc = R5.main(["--run", str(run)])
    assert rc == 0
    v = json.loads((run / "verdicts" / "READOUT_R5.json").read_text())
    gates = v["widening"]["gates"]

    assert set(gates) == EXPECTED_GATES
    assert gates["G-DISJOINT"]["ok"] is False
    assert "G-DISJOINT row FAILED" in gates["G-DISJOINT"]["why"]
    # every OTHER row still resolved, with a real resolved_at and a boolean
    others = {n: g for n, g in gates.items() if n != "G-DISJOINT"}
    assert all(g["ok"] for g in others.values()), \
        sorted(n for n, g in others.items() if not g["ok"])
    assert all(g["resolved_at"] != "UNRESOLVED" for g in others.values())

    # ...and the read is UNREADABLE, with no branch token printed anywhere
    assert v["widening"]["gates_ok"] is False
    assert v["widening"]["branch"]["fired"] == "W-UNREADABLE"
    md = (run / "verdicts" / "READOUT_R5.md").read_text()
    assert R5.scan_branch_tokens(json.dumps(v)) == set()
    assert R5.scan_branch_tokens(md) == set()


def test_failed_block_carries_the_corrected_r5_expectation(synth_readout):
    """READ_RULE §3's CORRECTION, on the record: R5's corpus sits slightly
    DEEPER than S1's, so the pre-registered failure expectation is
    EQUAL-OR-HIGHER than S1's 0.30%, not lower."""
    v, _, _ = synth_readout
    f = v["widening"]["failed"]
    assert f["n_failed_rids"] == 0
    assert f["n_attempted"] == len(SYNTH_RIDS)
    assert f["rate"] == 0.0
    assert f["by_class"] == {}
    assert "EQUAL-OR-HIGHER" in f["corrected_expectation_r5"]
    assert "Where collisions happen is not where the population lives" in \
        f["corrected_expectation_r5"]


def test_supply_chain_carries_corpus_realized_integers(synth_readout):
    v, _, _ = synth_readout
    sc = v["widening"]["supply_chain"]
    assert sc["n_in"] == len(SYNTH_RIDS) + 4
    assert sc["n_positions"] == len(SYNTH_RIDS)
    assert sc["n_excluded_r5"] == 4
    assert sc["max_positions_per_seed"] == 3
    assert sc["internal_dupe"]["n_dupe_groups"] == 3
    assert "CORPUS-IDENTITY checks" in sc["internal_dupe"]["what_it_establishes"]
    assert sc["d_model_fit"]["status"].startswith("VACUOUS")


def test_committed_parameters_come_from_the_artifacts_not_a_hard_coded_copy():
    """READ_RULE §2a: the floors are PARAMETERS committed in `FLOORS_R5.json`.
    The module constants are a DEFAULT plus a cross-check, and a divergence is
    DISCLOSED rather than resolved by one side quietly winning."""
    real = R5.committed_parameters({"n2": 1060, "gate_floor": 1007},
                                   {"leg_ladder_expected":
                                    list(R5.LEG_LADDER_EXPECTED),
                                    "n_total_pairs": R5.LEG_PAIRS_TOTAL})
    assert real["agrees_with_module_pin"] is True
    other = R5.committed_parameters({"n2": 8, "gate_floor": 8}, None)
    assert other["n2"] == 8 and other["gate_floor"] == 8
    assert other["agrees_with_module_pin"] is False
    assert other["module_pin"]["n2"] == 1060
    # absent artifact ⇒ the module default, stated as such
    fallback = R5.committed_parameters(None, None)
    assert fallback["n2"] == R5.N2_COMMITTED
    assert fallback["gate_floor"] == R5.GATE_FLOOR_COMMITTED
