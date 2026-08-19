#!/usr/bin/env python3
"""Tests for the `B = 64` GAME cell's adjudication + acceptance tooling
(`scripts/tiletie/analyze_b64_cell.py`), against the FROZEN pair at
`measurement/tiearb_widening_20260817/b64_cell/{DESIGN,READ_RULE}.md`.

⭐ The §4.1 sweep below RE-TRANSCRIBES the branch conditions from the READ_RULE
independently of the implementation, which is what the pair requires of it — and
it is what found Stage 2's unreachable `G-N` before any number existed.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TILETIE = REPO / "scripts" / "tiletie"
for p in (str(TILETIE), str(REPO / "scripts" / "measurement_infra")):
    if p not in sys.path:
        sys.path.insert(0, p)

import analyze_b64_cell as B64                                     # noqa: E402

CELL_DIR = REPO / "measurement" / "tiearb_widening_20260817" / "b64_cell"
STAGE2 = REPO / "measurement" / "tiearb2_stage2_20260817"
SHARE = Path("/mnt/c/carc-shared/tiearb2_stage2_20260817")


# =========================================================================== #
# §4.1 — the branch table, RE-TRANSCRIBED from the READ_RULE, not imported     #
# =========================================================================== #
def independently_transcribed_branch(z_D, A, precondition_failed):
    """READ_RULE §4, transcribed by hand from the frozen text:

        §3 is evaluated FIRST and pre-empts everything      -> U-UNREADABLE
        B-REVERSED  == z_D <= -2.0                          (evaluated SECOND)
        then, on z_D > -2.0:
            z_D >= +2.0  ->  B-CONFIRMED if A else B-COSTKILL
            +1.0 <= z_D < +2.0                              ->  B-PRESENT
            -2.0 <  z_D < +1.0                              ->  B-FLAT
    """
    if precondition_failed:
        return "U-UNREADABLE"
    if z_D <= -2.0:
        return "B-REVERSED"
    if z_D >= 2.0:
        return "B-CONFIRMED" if A else "B-COSTKILL"
    if z_D >= 1.0:
        return "B-PRESENT"
    return "B-FLAT"


def test_the_branch_table_is_TOTAL_and_DISJOINT_over_the_z_D_line():
    """Exactly ONE branch matches every possible read, and the match does not
    depend on presentation order (§4.1)."""
    zs = [-9.0, -2.0001, -2.0, -1.9999, -1.0, 0.0, 0.9999, 1.0, 1.5, 1.9999,
          2.0, 2.0001, 9.0, 1e-12, -1e-12]
    for z in zs:
        for A in (False, True):
            got = B64.decide_branch(z, {"G-STAT": True}, A)["branch"]
            want = independently_transcribed_branch(z, A, False)
            assert got == want, (z, A, got, want)
    # every branch of the table is reachable on SOME cell (given A)
    fired = {B64.decide_branch(z, {"G-STAT": True}, A)["branch"]
             for z in zs for A in (False, True)}
    assert fired == {"B-REVERSED", "B-CONFIRMED", "B-COSTKILL", "B-PRESENT",
                     "B-FLAT"}


def test_a_failed_precondition_PRE_EMPTS_every_branch():
    for z in (-9.0, 0.0, +9.0):
        for A in (False, True):
            out = B64.decide_branch(z, {"G-STAT": True, "G-FIRE": False}, A)
            assert out["branch"] == "U-UNREADABLE"
            assert out["failed_preconditions"] == ["G-FIRE"]


def test_NaN_is_caught_by_G_STAT_BEFORE_any_branch_comparison():
    """⭐ THE PRECEDENCE. §4.1: any NaN in z_D/D/se_D/z_w/z_n is caught by G-STAT
    in §3 BEFORE a comparison is taken, so no branch is ever entered on a NaN."""
    nan = float("nan")
    ok, d = B64.gate_stat(nan, 1.0, 0.5, 1.0, 1.0)
    assert ok is False and d["nan_or_absent"] == ["z_D"]
    assert "BEFORE any branch comparison" in d["precedence"]
    for absent in (None, nan):
        ok, _ = B64.gate_stat(absent, 1.0, 0.5, 1.0, 1.0)
        assert ok is False
    # with G-STAT firing, the branch is U-UNREADABLE and never a comparison
    out = B64.decide_branch(nan, {"G-STAT": False}, False)
    assert out["branch"] == "U-UNREADABLE" and "G-STAT" in out["failed_preconditions"]
    # ⚠️ and if a NaN ever reached the branch with G-STAT passing, that is a
    # DEFECT and it still refuses rather than comparing
    out2 = B64.decide_branch(nan, {"G-STAT": True}, False)
    assert out2["branch"] == "U-UNREADABLE" and "defect" in out2["reason"]
    ok, _ = B64.gate_stat(1.0, 1.0, 0.5, 1.0, 1.0)
    assert ok is True


def test_the_reachable_set_is_stated_BEFORE_the_run_and_B_CONFIRMED_is_default_unreachable():
    """§4.0 — an unreachable headline branch must be visible BEFORE the run, not
    discovered in the read-out (the Stage-2 G-N lesson, applied prospectively)."""
    off = B64.reachable_branches(False)
    assert off["unreachable"] == ["B-CONFIRMED"]
    assert "B-COSTKILL" in off["reachable"]
    on = B64.reachable_branches(True)
    assert on["unreachable"] == [] and len(on["reachable"]) == 6
    # and A is decided ENTIRELY by W, because rho_wall(64) > the N4 bar
    a_off = B64.affordability({"W": False})
    assert a_off["A"] is False and a_off["first_disjunct"] is False
    assert a_off["rho_wall_64"] == 2.4897 and a_off["n4_bar"] == 1.20
    assert B64.affordability({"W": True})["A"] is True
    # ⇒ a win without a waiver fires B-COSTKILL, never B-CONFIRMED
    assert B64.decide_branch(3.0, {}, a_off["A"])["branch"] == "B-COSTKILL"


# =========================================================================== #
# §4.0.1 — `W`, the waiver predicate                                          #
# =========================================================================== #
CONFORMING = ('> OWNER WAIVER (N4 rho_wall, B > 16), 2026-08-19: "fine, run the '
              'B=64 cell and I will pay the wall clock"')


def test_the_waiver_regex_accepts_a_conforming_blockquote():
    m = B64.WAIVER_REGEX.match(CONFORMING)
    assert m, "a conforming line must match"
    assert m.group(1) == "2026-08-19"
    assert m.group(2).startswith("fine, run the B=64 cell")


def test_the_waiver_regex_REJECTS_stage2_0D_and_every_near_miss():
    """⛔ No other route to `A` exists. In particular the Stage-2 §0.D waiver does
    NOT satisfy conjunct 3: it names neither `rho_wall` nor `B > 16`."""
    s2 = STAGE2 / "READ_RULE.md"
    if s2.is_file():
        for line in s2.read_text().splitlines():
            assert not B64.WAIVER_REGEX.match(line), (
                f"Stage 2's own text must NOT satisfy this pair's waiver: {line!r}")
    near_misses = [
        '> OWNER WAIVER (N4 rho_wall), 2026-08-19: "ok"',            # no rung
        '> OWNER WAIVER (B > 16), 2026-08-19: "ok"',                 # no rho_wall
        '> OWNER WAIVER (N4 rho_wall, B > 16), 19-08-2026: "ok"',    # not ISO
        '> OWNER WAIVER (N4 rho_wall, B > 16), 2026-08-19: ""',      # empty quote
        'OWNER WAIVER (N4 rho_wall, B > 16), 2026-08-19: "ok"',      # not a quote
        '> owner waiver (n4 rho_wall, b > 16), 2026-08-19: "ok"',    # case
        '> OWNER WAIVER (N4 rho_wall, B > 16), 2026-08-19: "ok" ',   # trailing
    ]
    for line in near_misses:
        assert not B64.WAIVER_REGEX.match(line), line


def test_W_is_FAIL_CLOSED_on_every_missing_conjunct(tmp_path):
    """`W` is TRUE iff ALL THREE hold; any one absent ⇒ FALSE."""
    out = B64.waiver_predicate(tmp_path, None)
    assert out["W"] is False and out["conjuncts"]["existence"] is False
    (tmp_path / "OWNER_WAIVER.md").write_text(CONFORMING + "\n")
    out = B64.waiver_predicate(tmp_path, None)      # untracked ⇒ conjunct 1 fails
    assert out["W"] is False
    assert out["conjuncts"]["ordering"] is False    # no band claim to precede
    # the CONTENT conjunct is matched, and the date/quote are captured for print
    assert out["conjuncts"]["content"] is True
    assert out["captured_date"] == "2026-08-19"
    assert "B=64 cell" in out["captured_quote"]


def test_no_waiver_exists_in_the_cell_dir_today_so_W_is_FALSE():
    """§4.0: W is EXPECTED to be false — the realistic ceiling is B-COSTKILL."""
    assert not (CELL_DIR / "OWNER_WAIVER.md").exists()
    w = B64.waiver_predicate(CELL_DIR, None)
    assert w["W"] is False
    assert B64.reachable_branches(w["W"])["unreachable"] == ["B-CONFIRMED"]


# =========================================================================== #
# G-NEST — the structural witness, on the REAL seeding code                    #
# =========================================================================== #
def test_the_nested_CRN_witness_fires_on_the_real_seeding_code():
    """⭐ §1.3's load-bearing property, read off `tiearb.rs` at HEAD: the seed is
    a pure function of `j`, NEVER of `B` ⇒ B=64's worlds 0..15 are byte-identical
    to B=16's entire world set."""
    w = B64.nest_witness()
    assert w["present"] is True, "rust/carc/carc-core/src/tiearb.rs must exist"
    assert w["witness"] is True, w
    assert set(w["sites"]) == {"world_seed", "playout_seed", "build_arms_cap",
                               "select_stream"}
    for name, site in w["sites"].items():
        assert site["found"] is True, name
        assert site["b_free"] is True, name
        assert "seed_i64" in site["expression"]
    # the world/playout seeds take `j`; the cap and select streams take neither
    assert "&js" in w["sites"]["world_seed"]["expression"]
    assert '"playout"' in w["sites"]["playout_seed"]["expression"]


def test_G_NEST_fails_closed_on_an_absent_or_false_witness():
    ok, d = B64.gate_nest(None)
    assert ok is False and "ABSENT" in d["why"]
    ok, _ = B64.gate_nest({"witness": False})
    assert ok is False
    ok, _ = B64.gate_nest({"witness": True})
    assert ok is True
    # a truthy non-True value is not a witness
    assert B64.gate_nest({"witness": "yes"})[0] is False


# =========================================================================== #
# §9.2 — the smoke's FAIL-CLOSED whitelist                                     #
# =========================================================================== #
def test_the_smoke_whitelist_REFUSES_a_margin_key():
    good = {"wall_secs": 1.0, "worker_secs_per_game": 900.0, "tiearb_phi": 17.5}
    assert B64.smoke_whitelist_check(good)["ok"] is True
    for forbidden in ("paired_mean_margin", "paired_z", "elo", "winrate", "f0",
                      "z_D"):
        out = B64.smoke_whitelist_check({**good, forbidden: 1.23})
        assert out["ok"] is False, forbidden
        assert forbidden in out["forbidden_present"]
    assert "FAIL-CLOSED" in B64.smoke_whitelist_check(good)["mode"]
    assert "MARGIN-DERIVED" in B64.smoke_whitelist_check(good)["f0_note"]


def test_the_smoke_GATE_fires_on_a_forbidden_OUTCOME_key_at_any_depth():
    base = {"worker_secs_per_game": 900.0}
    assert B64.gate_smoke(base)[0] is True
    assert B64.gate_smoke({**base, "cells": {"WIDE": {"paired_mean_margin": 1.0}}})[0] \
        is False
    hits = B64.smoke_outcome_scan({"cells": {"WIDE": {"elo": 1, "wall_secs": 2}}})
    assert hits == ["cells.WIDE.elo"]
    # ⚠️ and W/D/L are themselves forbidden outcome keys (§9.2)
    assert B64.smoke_outcome_scan({"W": 1, "D": 2, "L": 3}) == ["W", "D", "L"]
    # ⚠️ a counts key is NOT swept up by a substring
    assert B64.smoke_outcome_scan({"tiearb_mean_arms": 3, "n_failed": 0}) == []


def test_the_smoke_HALT_bar_is_one_sided_and_derived():
    assert B64.SMOKE_HALT_BAR == pytest.approx(1.50 * 958.794)
    over = {"worker_secs_per_game": B64.SMOKE_HALT_BAR + 1.0}
    ok, d = B64.gate_smoke(over, launched_anyway=True)
    assert ok is False and d["halted"] is True
    ok, d = B64.gate_smoke(over, launched_anyway=False)
    assert ok is True, "a HALT that was OBEYED does not fail the gate"
    under = {"worker_secs_per_game": 10.0}
    assert B64.gate_smoke(under)[1]["halted"] is False
    assert "an overrun HALTS, an underrun proceeds" in B64.gate_smoke(under)[1]["one_sided"]


def test_an_absent_smoke_is_a_FAIL():
    assert B64.gate_smoke({})[0] is False
    assert B64.gate_smoke(None)[0] is False


# =========================================================================== #
# the gates, one at a time                                                     #
# =========================================================================== #
def _cell(B=64, mode="argmax", leaf=B64.CHAMP_LEAF_HASH, partial=0, phi=17.5,
          err=0.0, n_failed=0, n=1500, band=137000000000, decks=(1, 2, 3)):
    return {
        "manifest": {"cand_leaf_hash": leaf, "band_seed_start": band,
                     "cand_tiearb": {"enabled": True, "B": B, "J": 4,
                                     "mode": mode, "salt": "tiearb2-deploy-v1",
                                     "eps": 0.0}},
        "summary": {"tiearb_B": [B], "tiearb_J": [4], "tiearb_modes": [mode],
                    "tiearb_partial_argmax_total": partial,
                    "tiearb_error_rate_on_fired": err, "n_failed": n_failed,
                    "n_attempted": n, "n": n},
        "phi": {"phi": phi}, "n_games": n, "deck_seeds": list(decks),
    }


def test_G_J1_is_INVERTED_a_difference_ABORTS():
    cells = {"WIDE": _cell(), "NARROW": _cell(B=16)}
    assert B64.gate_j1(cells)[0] is True
    cells["WIDE"]["manifest"]["cand_leaf_hash"] = "deadbeefdeadbeef"
    ok, d = B64.gate_j1(cells)
    assert ok is False and "ABORTS" in d["semantics"]
    del cells["WIDE"]["manifest"]["cand_leaf_hash"]
    assert B64.gate_j1(cells)[0] is False, "ABSENT under both levels also fails"


def test_G_J4_refuses_a_mixed_B_cell_and_any_knob_drift():
    cells = {"WIDE": _cell(B=64), "NARROW": _cell(B=16)}
    assert B64.gate_j4(cells)[0] is True
    mixed = {"WIDE": _cell(B=64), "NARROW": _cell(B=16)}
    mixed["WIDE"]["summary"]["tiearb_B"] = [16, 64]        # a MIXED-B cell
    ok, d = B64.gate_j4(mixed)
    assert ok is False and "VOID, not a finding" in d["semantics"]
    for knob, bad in (("salt", "other-salt"), ("eps", 0.01), ("J", 5),
                      ("mode", "random"), ("enabled", False)):
        c = {"WIDE": _cell(B=64), "NARROW": _cell(B=16)}
        c["WIDE"]["manifest"]["cand_tiearb"][knob] = bad
        assert B64.gate_j4(c)[0] is False, knob
    # the wrong B in the right cell fails too
    swapped = {"WIDE": _cell(B=16), "NARROW": _cell(B=16)}
    assert B64.gate_j4(swapped)[0] is False


def test_G_FIRE_floors_phi_effective_at_one():
    cells = {"WIDE": _cell(phi=1.2, err=0.0), "NARROW": _cell(B=16, phi=1.2)}
    assert B64.gate_fire(cells)[0] is True
    inert = {"WIDE": _cell(phi=0.9), "NARROW": _cell(B=16, phi=17.5)}
    assert B64.gate_fire(inert)[0] is False
    # phi_effective = phi × (1 − error_rate_on_fired)
    dilute = {"WIDE": _cell(phi=1.2, err=0.5), "NARROW": _cell(B=16, phi=17.5)}
    ok, d = B64.gate_fire(dilute)
    assert ok is False and d["WIDE"]["phi_effective"] == pytest.approx(0.6)


def test_G_DIVERGE_and_the_f0_block():
    wide = {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}
    narrow = {1: 1.0, 2: 2.0, 3: 3.0, 4: 0.0}          # 3 of 4 identical
    fb = B64.f0_block(wide, narrow)
    assert fb["f0"] == pytest.approx(0.75)
    assert fb["one_minus_f0"] == pytest.approx(0.25)
    assert fb["dilution_sqrt_one_minus_f0"] == pytest.approx(0.5)
    ok, d = B64.gate_diverge(fb)
    assert ok is True, "0.25 clears the 0.10 inertness floor"
    # ⚠️ but it is an ANOMALY: materially below the EXPECTED ≈1.0
    assert fb["anomaly"] is True and fb["expected_one_minus_f0"] == 1.0
    assert "ANOMALY" in fb["anomaly_note"]
    inert = B64.f0_block({i: 1.0 for i in range(20)}, {i: 1.0 for i in range(20)})
    assert inert["f0"] == 1.0 and B64.gate_diverge(inert)[0] is False
    assert "CONSERVATIVE" in fb["measurement_disclosure"]


def test_G_N_both_clauses_and_the_deck_clause_binds_independently():
    assert B64.gate_n(600, {"WIDE": 1200, "NARROW": 1200})[0] is True
    assert B64.gate_n(599, {"WIDE": 1500, "NARROW": 1500})[0] is False
    assert B64.gate_n(700, {"WIDE": 1199, "NARROW": 1500})[0] is False
    ok, d = B64.gate_n(700, {"WIDE": 1500, "NARROW": 1500})
    assert ok is True and d["n_common_units"] == "DECKS"
    assert "1200 games IS 600 decks" in d["same_80pct_bar"]


def test_G_FAILED_clauses_1_and_2_are_untouched_by_the_narrowing():
    ok, d = B64.gate_failed({"WIDE": _cell(n_failed=0), "NARROW": _cell(B=16)})
    assert ok is True and d["n_failed_total"] == 0
    conf = {"all_failures_confirmed": True}
    # clause 1 — RATE, not count
    assert B64.gate_failed({"WIDE": _cell(n_failed=31, n=1500),
                            "NARROW": _cell(B=16)}, confirmation=conf)[0] is False
    assert B64.gate_failed({"WIDE": _cell(n_failed=29, n=1500),
                            "NARROW": _cell(B=16, n_failed=29)},
                           confirmation=conf)[0] is True
    # clause 2 — candidate-correlation: >=5 AND > 3 x max(min,1)
    ok, d = B64.gate_failed({"WIDE": _cell(n_failed=5),
                             "NARROW": _cell(B=16, n_failed=0)},
                            confirmation=conf)
    assert ok is False and d["clause2_candidate_correlated"] is True
    # the >=5 floor exists so a 1-vs-0 split (Stage 2's shape) does NOT void
    ok, _ = B64.gate_failed({"WIDE": _cell(n_failed=1),
                             "NARROW": _cell(B=16, n_failed=0)},
                            confirmation=conf)
    assert ok is True


def test_G_FAILED_clause3_AS_NARROWED_halts_on_ANY_failure_until_confirmed():
    """RULING 3: clause 3 is no longer a CLASS check - the harness emits no class
    and commissioning one after sign-off is how the three unsatisfiable gates
    shipped. Any failure => verbatim disclosure + an escalation HALT, and only a
    RECORDED HUMAN CONFIRMATION clears it."""
    cells = {"WIDE": _cell(n_failed=1), "NARROW": _cell(B=16, n_failed=0)}
    ok, d = B64.gate_failed(cells)
    assert ok is False and d["clause3_halt"] is True and d["n_failed_total"] == 1
    assert "HALTS for owner escalation BEFORE ADJUDICATION" in d["clause3_rule"]
    assert "adjudicates NOTHING" in d["clause3_exception_disclosure"]
    assert "rung3_r5" in d["class_field_carried_forward"]
    # the confirmation is a HUMAN ACT and clears the halt without moving a bar
    ok, d = B64.gate_failed(cells, confirmation={"all_failures_confirmed": True,
                                                 "confirmed_by": "owner"})
    assert ok is True and d["clause3_halt"] is False
    assert d["clause3_confirmation"]["confirmed_by"] == "owner"
    # a half-hearted confirmation does NOT clear it (fail-closed)
    assert B64.gate_failed(cells,
                           confirmation={"all_failures_confirmed": "yes"})[0] is False
    assert B64.gate_failed(cells, confirmation={})[0] is False
    # NO class field is CONSULTED any more (it survives only as history in
    # SPEC_VS_BUILDABLE, which is evidence and must stay readable)
    src = (TILETIE / "analyze_b64_cell.py").read_text()
    assert 'get("failed_classes")' not in src
    assert "diagnostic_classes" not in src


def test_the_clause3_HALT_carries_the_raw_records_VERBATIM():
    """The run PAUSES before adjudication and the raw failure records are emitted
    as the harness wrote them - no class is invented."""
    rec = {"seed": 1, "a_seat": 0, "diff": 1.0, "ok": False,
           "error": "WindowTruncationError: boom", "traceback_tail": "...frame..."}
    cells = {"WIDE": {**_cell(n_failed=1), "records": [rec]},
             "NARROW": {**_cell(B=16), "records": []}}
    raws = B64.raw_failure_records(cells)
    assert len(raws) == 1 and raws[0]["verbatim"] is True
    assert raws[0]["error"].startswith("WindowTruncationError")
    assert raws[0]["traceback_tail"] == "...frame..."
    ok, d = B64.gate_failed(cells, raw_records=raws)
    assert ok is False and d["raw_failure_records"] == raws


def test_G_TOOL_is_EQUALITY_across_boxes_and_unpinned_PASSES():
    """⛔ THE THIRD UNSATISFIABLE-GATE CATCH. `+rustcunpinned` is the NORMAL
    production value and must PASS when both boxes emit it."""
    build = "carc_rs-0.1.0+58c2b5395569+rustcunpinned"
    pre = [{"host": "Doctor", "carc_rs_build": build},
           {"host": "laptop-wsl", "carc_rs_build": build}]
    ok, d = B64.gate_tool(pre, {})
    assert ok is True, "unpinned, equal on both boxes, PASSES"
    assert "NORMAL production value" in d["unpinned_is_normal"]
    assert "unsatisfiable-gate catch" in d["unpinned_is_normal"]
    assert "NEVER compared" in d["binary_sha_rule"]
    differ = [{"host": "Doctor", "carc_rs_build": build},
              {"host": "laptop-wsl", "carc_rs_build":
               "carc_rs-0.1.0+4b24f512a083+rustcunpinned"}]
    assert B64.gate_tool(differ, {})[0] is False
    # a box that mixed builds within itself fails
    mixed = pre + [{"host": "Doctor", "carc_rs_build": "carc_rs-0.1.0+aaaaaaaaaaaa+rustcunpinned"}]
    assert B64.gate_tool(mixed, {})[0] is False
    assert B64.gate_tool([], {})[0] is False


def _preflight(host, B, changed=True, unchanged=True, expected_B=None):
    return {"host": host,
            "j13_witness": {"B": B, "pick_changed": changed,
                            "root_leaf_value_bits_unchanged": unchanged},
            "expected": {"B": B if expected_B is None else expected_B}}


def test_G_J13_reads_the_PINNED_key_path_and_an_ABSENT_B_FAILS():
    """RULING 2: the address is PINNED, not resolved over an order - G-J13 is the
    gate that proves the instrument is LIVE at both B values, and 'the one gate
    that proves the instrument is live should not be the one left to search'.
    ABSENT B => FAIL, never 'assume the file's B'."""
    assert B64.PREFLIGHT_B_PATH == "j13_witness.B"
    assert B64.PREFLIGHT_B_EXPECTED_PATH == "expected.B"
    good = [_preflight(h, b) for h in ("Doctor", "laptop-wsl") for b in (64, 16)]
    ok, d = B64.gate_j13(good)
    assert ok is True
    assert d["pinned_addresses"]["B"] == "j13_witness.B"
    assert "ABSENT" in d["semantics"] and "FAIL" in d["semantics"]

    noB = [{"host": h,
            "j13_witness": {"pick_changed": True,
                            "root_leaf_value_bits_unchanged": True},
            "expected": {}} for h in ("Doctor", "laptop-wsl")]
    assert B64.gate_j13(noB)[0] is False
    # B at the OLD top level is no longer read - the path is pinned
    topB = [{"host": h, "B": b,
             "j13_witness": {"pick_changed": True,
                             "root_leaf_value_bits_unchanged": True},
             "expected": {"B": b}}
            for h in ("Doctor", "laptop-wsl") for b in (64, 16)]
    assert B64.gate_j13(topB)[0] is False


def test_G_J13_requires_BOTH_booleans_BOTH_B_values_and_expected_agreement():
    base = [_preflight(h, b) for h in ("Doctor", "laptop-wsl") for b in (64, 16)]
    assert B64.gate_j13(base)[0] is True
    others = [p for p in base
              if not (p["host"] == "Doctor" and p["j13_witness"]["B"] == 64)]
    assert B64.gate_j13(others)[0] is False              # a B value missing
    assert B64.gate_j13([_preflight("Doctor", 64, changed=False)]
                        + others)[0] is False            # the pick did not change
    assert B64.gate_j13([_preflight("Doctor", 64, unchanged=False)]
                        + others)[0] is False            # the leaf bits moved
    ok, d = B64.gate_j13([_preflight("Doctor", 64, expected_B=16)] + others)
    assert ok is False
    assert d["by_host"]["Doctor"]["64"]["B_matches_expected"] is False


def test_G_PLY_treats_ABSENT_as_unknown_not_zero():
    cells = {"WIDE": _cell(partial=0), "NARROW": _cell(B=16, partial=0)}
    assert B64.gate_ply(cells)[0] is True
    cells["WIDE"]["summary"]["tiearb_partial_argmax_total"] = 3
    assert B64.gate_ply(cells)[0] is False
    del cells["WIDE"]["summary"]["tiearb_partial_argmax_total"]
    ok, d = B64.gate_ply(cells)
    assert ok is False and "unknown-not-zero" in d["WIDE"]["semantics"]


def test_G_BAND_requires_the_same_band_AND_the_same_decks_AND_a_pre_dated_claim():
    cells = {"WIDE": _cell(decks=(1, 2, 3)), "NARROW": _cell(B=16, decks=(1, 2, 3))}
    claim = {"claimed_before_game_1": True, "band": 137000000000}
    assert B64.gate_band(cells, claim)[0] is True
    assert B64.gate_band(cells, {"claimed_before_game_1": False})[0] is False
    other = {"WIDE": _cell(decks=(1, 2, 3)),
             "NARROW": _cell(B=16, decks=(1, 2, 4))}
    assert B64.gate_band(other, claim)[0] is False
    bands = {"WIDE": _cell(band=137000000000), "NARROW": _cell(B=16, band=138000000000)}
    assert B64.gate_band(bands, claim)[0] is False


# =========================================================================== #
# ⭐ THE KNOWN-GOOD GATE EVALUATION — the launch precondition itself            #
# =========================================================================== #
@pytest.mark.skipif(not (SHARE / "tiearb_ARB_B16J4_deploy11008" /
                         "summary.json").is_file(),
                    reason="Stage 2's completed cells are not on this box's share")
def test_knowngood_partition_against_the_REAL_stage2_artifacts(tmp_path):
    """⭐ DESIGN §13.1: every §3 row must PASS on a known-good run before the blind
    commit. A row that fails a healthy run is a DRAFTING DEFECT — and a row that
    cannot be evaluated must be NAMED, never silently counted as covered."""
    doc = B64.knowngood_eval(STAGE2, SHARE)
    assert doc["n_rows"] == 13, sorted(doc["rows"])
    assert doc["na_rows"] == ["G-DIVERGE", "G-NEST"], (
        "the two rows with no Stage-2 analogue must be NAMED")
    assert doc["failed_rows"] == [], doc["failed_rows"]
    assert doc["all_evaluable_rows_pass"] is True
    assert doc["n_evaluated"] == 11 and doc["n_pass"] == 11
    # every N-A carries its REASON
    for g in doc["na_rows"]:
        assert doc["rows"][g]["detail"]["why"]
    # ⭐ the row the precondition exists for
    assert doc["rows"]["G-TOOL"]["status"] == "PASS"
    assert "unsatisfiable" in doc["rows"]["G-TOOL"]["note"] or \
        "rustcunpinned" in doc["rows"]["G-TOOL"]["note"]
    # every substitution is DISCLOSED on its row
    assert doc["rows"]["G-N"]["scaled"]
    assert doc["rows"]["G-N"]["verbatim_would_be"].startswith("FAIL")
    assert doc["rows"]["G-J4"]["mapped"]
    assert "NEVER silently counts as covered" in doc["meaning"]


def test_knowngood_names_the_rows_that_have_no_analogue():
    """The two N-A rows are declared in code with their reasons, so the partition
    is auditable without running anything."""
    assert set(B64.KNOWNGOOD_NA) == {"G-NEST", "G-DIVERGE"}
    assert "no GATE_NEST.json analogue" in B64.KNOWNGOOD_NA["G-NEST"]
    assert "DIFFERENT-MODE" in B64.KNOWNGOOD_NA["G-DIVERGE"]


# =========================================================================== #
# the pair is FROZEN — mismatches are REPORTED, never resolved here            #
# =========================================================================== #
def test_spec_vs_buildable_mismatches_are_REPORTED_not_resolved():
    assert B64.SPEC_VS_BUILDABLE, "found mismatches must be carried, not dropped"
    for m in B64.SPEC_VS_BUILDABLE:
        for k in ("where", "issue", "adjudicator_behaviour", "resolution"):
            assert m.get(k), (m, k)
        # all three were RULED pre-blind; the entries stay because a
        # superseded finding is evidence — what changed, and why, must remain
        # readable beside the code that changed with it
        assert m.get("status"), m
        if m["status"].startswith("RULED"):
            assert "RULED 2026-08-19" in m["resolution"], m["resolution"]
        else:
            assert m["status"].startswith("NOTE"), m["status"]
    wheres = " | ".join(m["where"] for m in B64.SPEC_VS_BUILDABLE)
    assert "G-SMOKE" in wheres and "G-J13" in wheres
    # all three ORIGINAL findings are RULED; the residual is a NOTE for the emitter
    ruled = [m for m in B64.SPEC_VS_BUILDABLE if m["status"].startswith("RULED")]
    notes = [m for m in B64.SPEC_VS_BUILDABLE if m["status"].startswith("NOTE")]
    assert len(ruled) == 3 and len(notes) == 1
    assert "pinned addresses" in notes[0]["where"]


def test_the_committed_constants_match_the_frozen_pair():
    """Every bar this tool applies is READ from the pair, not invented here."""
    rr = (CELL_DIR / "READ_RULE.md").read_text()
    assert "`+2.0` and `+1.0`" in rr
    assert B64.Z_BAR == 2.0 and B64.Z_PRESENT == 1.0
    for constant in ("2.4897", "1.2449", "0.6224", "1.20", "23.90", "22.08"):
        assert constant in rr or constant in (CELL_DIR / "DESIGN.md").read_text(), \
            constant
    assert B64.RHO_WALL_64 == 2.4897 and B64.RHO_WALL_32 == 1.2449
    assert B64.N_COMMON_FLOOR == 600 and B64.CELL_GAMES_FLOOR == 1200
    assert B64.DIVERGE_FLOOR == 0.10 and B64.FAILED_RATE_BAR == 0.02
    assert B64.SE_D_COMMITTED == 0.7133 and B64.D_FLOOR_2SIGMA == 1.427


def test_no_branch_touches_production_yaml():
    src = (TILETIE / "analyze_b64_cell.py").read_text()
    assert "PRODUCTION.yaml" in src, "the invariant must be STATED"
    for forbidden in ("PRODUCTION.yaml\"", "write_text", "yaml.dump"):
        if forbidden == "write_text":
            continue          # the read-out itself is written; that is the point
    assert "untouched on every branch" in src
