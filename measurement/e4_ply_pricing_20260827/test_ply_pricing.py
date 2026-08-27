#!/usr/bin/env python3
"""Tests for the E4 ply-pricing instrument.

Three classes:
  * the PRICING ARITHMETIC on hand-computed fixtures (no engine, no solver);
  * the REALIZED-outcome arithmetic on hand-computed fixtures;
  * PREREG CONFORMANCE + target-set invariants against the frozen artifacts on
    disk (so a later edit to a constant cannot silently disagree with the
    pre-registration the run was committed against).

Run:  .venv/bin/python -m pytest measurement/e4_ply_pricing_20260827/test_ply_pricing.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_targets as BT            # noqa: E402
import price_plies as PP              # noqa: E402


# --------------------------------------------------------------------------- #
# 1. the pricing arithmetic                                                     #
# --------------------------------------------------------------------------- #
def test_p0_mover_delta_and_best_hand_computed():
    # P0 maximizes. Played action 7 is worth +3, the champion's counterfactual
    # action 4 is worth -2, the best available is +5 (action 9).
    cv = {4: -2.0, 7: 3.0, 9: 5.0}
    r = PP.price_from_child_values(cv, played=7, counterfactual=4, actor=0)
    assert r["price_played"] == 3.0
    assert r["price_counterfactual"] == -2.0
    assert r["price_best"] == 5.0
    assert r["delta_pts_mover"] == pytest.approx(5.0)     # 3 - (-2)
    assert r["regret_pts_mover"] == pytest.approx(2.0)    # 5 - 3
    assert r["n_root_actions"] == 3


def test_p1_mover_signs_are_mirrored():
    # SAME numbers, P1 to move. P1 minimizes the (P0 - P1) differential, so the
    # best move is the SMALLEST value and every sign flips.
    cv = {4: -2.0, 7: 3.0, 9: 5.0}
    r = PP.price_from_child_values(cv, played=7, counterfactual=4, actor=1)
    assert r["price_best"] == -2.0
    assert r["delta_pts_mover"] == pytest.approx(-5.0)    # played is WORSE for P1
    assert r["regret_pts_mover"] == pytest.approx(5.0)    # -(-2 - 3)


def test_agreeing_counterfactual_prices_to_exactly_zero():
    cv = {1: 0.0, 2: 8.0}
    for actor in (0, 1):
        r = PP.price_from_child_values(cv, played=2, counterfactual=2, actor=actor)
        assert r["delta_pts_mover"] == 0.0


def test_missing_counterfactual_leaves_delta_none_but_still_prices_the_played_move():
    cv = {1: 1.0, 2: 4.0}
    r = PP.price_from_child_values(cv, played=2, counterfactual=None, actor=0)
    assert r["delta_pts_mover"] is None
    assert r["price_played"] == 4.0
    assert r["regret_pts_mover"] == pytest.approx(0.0)


def test_empty_child_values_prices_nothing():
    r = PP.price_from_child_values({}, played=1, counterfactual=2, actor=0)
    assert r["price_best"] is None and r["delta_pts_mover"] is None


def test_fbits_round_trips_the_raw_f64():
    import struct
    for v in (0.0, -3.5, 12.25, 1e-9):
        assert PP.fbits(struct.unpack("<Q", struct.pack("<d", v))[0]) == v


def test_clairvoyant_M_averages_resampled_worlds_and_excludes_the_true_future(
        monkeypatch):
    """World -1 is the archive's realized future: reported, never averaged in."""
    canned = {
        -1: {"status": "OK", "nodes": 1, "to_move": 0, "solve_s": 0.1,
             "value": 99.0, "child_values": {5: 99.0, 6: 99.0}},
        0: {"status": "OK", "nodes": 2, "to_move": 0, "solve_s": 0.1,
            "value": 2.0, "child_values": {5: 2.0, 6: -4.0}},
        1: {"status": "OK", "nodes": 3, "to_move": 0, "solve_s": 0.1,
            "value": 4.0, "child_values": {5: 4.0, 6: 0.0}},
        2: {"status": "TIME_SKIPPED", "kill_reason": "rlimit_cpu"},
    }
    monkeypatch.setattr(PP, "solve_isolated",
                        lambda p, m, c: canned[p["world"]])
    r = PP.solve_clairvoyant_M({"profile": "x"}, m_worlds=3, mem_cap_gb=1, cpu_cap_s=1)
    assert r["status"] == "OK"
    assert r["m_worlds_ok"] == 2 and r["m_worlds_requested"] == 3
    # mean over worlds 0 and 1 ONLY — the 99.0 true-future world is excluded
    assert r["child_values"][5] == pytest.approx(3.0)
    assert r["child_values"][6] == pytest.approx(-2.0)
    assert r["true_future_value"] == 99.0
    assert r["nodes"] == 6                       # 1 + 2 + 3, skipped world adds none
    assert "CLAIRVOYANCE GAP" in r["caveat"]
    skipped = [w for w in r["worlds"] if w["status"] == "TIME_SKIPPED"]
    assert len(skipped) == 1 and skipped[0]["kill_reason"] == "rlimit_cpu"


def test_clairvoyant_M_reports_all_worlds_skipped_rather_than_a_fake_price(monkeypatch):
    monkeypatch.setattr(PP, "solve_isolated",
                        lambda p, m, c: {"status": "TIME_SKIPPED"})
    r = PP.solve_clairvoyant_M({"profile": "x"}, m_worlds=2, mem_cap_gb=1, cpu_cap_s=1)
    assert r["status"] == "ALL_WORLDS_SKIPPED"
    assert "child_values" not in r


# --------------------------------------------------------------------------- #
# 2. the K -> mode cut                                                          #
# --------------------------------------------------------------------------- #
def test_mode_for_k_boundaries():
    cut = {"k_marginalized_max": 4, "k_clairvoyant_max": 9, "m_worlds": 32}
    assert PP.mode_for_k(1, cut) == "exact_marginalized"
    assert PP.mode_for_k(4, cut) == "exact_marginalized"
    assert PP.mode_for_k(5, cut) == "exact_clairvoyant_M"
    assert PP.mode_for_k(9, cut) == "exact_clairvoyant_M"
    assert PP.mode_for_k(10, cut) == "realized"
    assert PP.mode_for_k(71, cut) == "realized"


# --------------------------------------------------------------------------- #
# 3. the realized-outcome arithmetic                                            #
# --------------------------------------------------------------------------- #
def test_attach_realized_hand_computed(tmp_path):
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps({
        "game": "g.json", "ply": 10, "n_plies": 100, "stratum": "invasion",
        "notes": {"invader_gain": 11.0, "incumbent_denied": 4.0},
    }) + "\n")
    scores = {"g.json": {10: [5, 3], 30: [20, 9], 100: [40, 30]}}
    finals = {"g.json": [40, 30]}
    PP.attach_realized(rows, scores, finals)
    r = json.loads(rows.read_text())["realized"]
    assert r["margin_at_ply"] == 2            # 5 - 3
    assert r["margin_at_ply_plus_W"] == 11    # 20 - 9  (ply 10 + W=20)
    assert r["realized_swing_W"] == 9         # 11 - 2
    assert r["realized_swing_end"] == 8       # (40-30) - 2
    assert r["window_plies"] == PP.REALIZED_WINDOW_PLIES
    assert r["feature_gross_gain"] == 11.0
    assert "DESCRIPTIVE" in r["caveat"]


def test_attach_realized_clamps_the_window_to_the_end_of_the_game(tmp_path):
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps({
        "game": "g.json", "ply": 95, "n_plies": 100, "stratum": "control",
        "notes": {},
    }) + "\n")
    scores = {"g.json": {95: [30, 30], 100: [33, 31]}}
    PP.attach_realized(rows, scores, {"g.json": [33, 31]})
    r = json.loads(rows.read_text())["realized"]
    assert r["margin_at_ply_plus_W"] == 2     # clamped to ply 100
    assert r["realized_swing_W"] == 2
    assert r["feature_gross_gain"] is None    # controls carry no feature gross


# --------------------------------------------------------------------------- #
# 3b. the aggregation (forced exclusion, excess-over-control, NO POOLING)        #
# --------------------------------------------------------------------------- #
def _agg_row(**kw):
    r = {"game": "g.json", "ply": 1, "stratum": "control", "n_legal": 5,
         "pricing_mode": "exact_marginalized", "delta_pts_mover": 0.0,
         "counterfactual_agrees": False, "notes": {}}
    r.update(kw)
    return r


def _run_aggregate(tmp_path, rows):
    import subprocess
    src = tmp_path / "rows.jsonl"
    src.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "agg.json"
    subprocess.run([sys.executable, str(HERE / "aggregate.py"),
                    "--rows", str(src), "--out", str(out)],
                   check=True, capture_output=True)
    return json.loads(out.read_text())


def test_aggregate_excludes_forced_and_computes_excess_over_control(tmp_path):
    rows = [
        _agg_row(ply=1, stratum="invasion", delta_pts_mover=4.0),
        _agg_row(ply=2, stratum="invasion", delta_pts_mover=6.0),
        _agg_row(ply=3, stratum="control", delta_pts_mover=1.0),
        _agg_row(ply=4, stratum="control", delta_pts_mover=3.0),
        # a FORCED ply: one legal action, prices to 0, must not drag the mean
        _agg_row(ply=5, stratum="invasion", n_legal=1, delta_pts_mover=0.0),
    ]
    a = _run_aggregate(tmp_path, rows)
    assert a["n_rows_total"] == 5 and a["n_rows_analyzed"] == 4
    assert a["n_forced_excluded"] == 1
    assert a["forced_by_stratum"]["invasion"] == 1
    e = a["excess_over_control"]["exact_marginalized"]["invasion"]
    assert e["mean"] == pytest.approx(5.0)          # (4+6)/2, forced 0.0 excluded
    assert e["control_mean"] == pytest.approx(2.0)  # (1+3)/2
    assert e["excess"] == pytest.approx(3.0)


def test_aggregate_never_pools_the_three_instruments(tmp_path):
    rows = [
        _agg_row(ply=1, stratum="invasion", pricing_mode="exact_marginalized",
                 delta_pts_mover=2.0),
        _agg_row(ply=2, stratum="invasion", pricing_mode="exact_clairvoyant_M",
                 delta_pts_mover=50.0),
        _agg_row(ply=3, stratum="invasion", pricing_mode="realized",
                 delta_pts_mover=None),
    ]
    a = _run_aggregate(tmp_path, rows)
    m = a["by_mode_by_stratum"]
    assert m["exact_marginalized"]["invasion"]["mean_delta_pts_mover"] == 2.0
    assert m["exact_clairvoyant_M"]["invasion"]["mean_delta_pts_mover"] == 50.0
    # the clairvoyant 50.0 must NOT leak into the marginalized table
    assert m["exact_marginalized"]["invasion"]["n_priced"] == 1
    assert m["realized"]["invasion"]["n_priced"] == 0
    assert "never pooled" in a["caveats"]["pooling"]


def test_aggregate_champion_agreement_is_defined_at_every_K(tmp_path):
    rows = [
        _agg_row(ply=1, stratum="invasion", pricing_mode="realized",
                 delta_pts_mover=None, counterfactual_agrees=False),
        _agg_row(ply=2, stratum="invasion", pricing_mode="realized",
                 delta_pts_mover=None, counterfactual_agrees=True),
    ]
    a = _run_aggregate(tmp_path, rows)
    g = a["champion_agreement_all_K"]["invasion"]
    assert g["n"] == 2 and g["agreement_rate"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# 4. prereg conformance + target-set invariants (the frozen artifacts)          #
# --------------------------------------------------------------------------- #
def _targets():
    p = HERE / "targets.jsonl"
    if not p.exists():
        pytest.skip("targets.jsonl not built yet")
    return [json.loads(l) for l in p.open()]


def test_prereg_constants_match_the_code():
    prereg = (HERE / "PREREG.md").read_text()
    assert f"DEFENSE_WINDOW_PLIES = {BT.DEFENSE_WINDOW_PLIES}" in prereg
    assert f"CONTROL_SEED = {BT.CONTROL_SEED}" in prereg
    assert f"REALIZED_WINDOW_PLIES = {PP.REALIZED_WINDOW_PLIES}" in prereg
    assert f"COUNTERFACTUAL_SEED = {PP.COUNTERFACTUAL_SEED}" in prereg
    assert f"CLAIR_WORLD_SEED = {PP.CLAIR_WORLD_SEED}" in prereg


def test_mode_cut_file_is_self_consistent():
    cut = json.loads((HERE / "MODE_CUT.json").read_text())
    assert cut["k_marginalized_max"] <= cut["k_clairvoyant_max"]
    assert cut["m_worlds"] >= 1
    prereg = (HERE / "PREREG.md").read_text()
    assert f"k_marginalized_max = {cut['k_marginalized_max']}" in prereg
    assert f"k_clairvoyant_max = {cut['k_clairvoyant_max']}" in prereg
    assert f"m_worlds = {cut['m_worlds']}" in prereg


def test_invasion_rows_cover_all_90_census_events_on_86_distinct_plies():
    rows = _targets()
    inv = [r for r in rows if r["stratum"] == "invasion"]
    # 4 owner moves each create TWO onsets at once (one merge connecting the
    # stub to two incumbent features), so 90 census EVENTS live on 86 PLIES.
    assert sum(r["notes"]["n_events"] for r in inv) == 90
    assert len(inv) == 86
    assert all(r["actor"] == 0 for r in inv)
    assert all(r["phase"] == "tiles" for r in inv)
    assert all(e["mech"] in ("merge", "merge_equal")
               for r in inv for e in r["notes"]["events"])
    # the grouped gross must be the SUM of its events, not the first one's
    for r in inv:
        assert r["notes"]["invader_gain"] == pytest.approx(
            sum(e["invader_gain"] for e in r["notes"]["events"]))


def test_defense_rows_are_champion_tile_plies_inside_the_window():
    rows = _targets()
    d = [r for r in rows if r["stratum"] == "defense"]
    assert d and all(r["actor"] == 1 for r in d)
    assert all(r["phase"] == "tiles" for r in d)
    assert all(0 < r["notes"]["gap_plies"] <= BT.DEFENSE_WINDOW_PLIES for r in d)


def test_control_rows_are_owner_plies_with_a_real_choice_and_no_overlap():
    rows = _targets()
    c = [r for r in rows if r["stratum"] == "control"]
    assert c and all(r["actor"] == 0 for r in c)
    assert all(r["n_legal"] > 1 for r in c), "a forced ply is not a decision"
    flagged = {(r["game"], r["ply"]) for r in rows
               if r["stratum"] in ("invasion", "farm_capture")}
    assert not ({(r["game"], r["ply"]) for r in c} & flagged)


def test_every_target_row_is_uniquely_keyed_and_well_formed():
    rows = _targets()
    keys = [(r["game"], r["ply"], r["stratum"]) for r in rows]
    assert len(keys) == len(set(keys))
    assert all(r["k"] >= 1 for r in rows)
    assert all(0 <= r["ply"] < r["n_plies"] for r in rows)
    assert all(r["profile"] in ("fixed_v1", "walled", "app_aug2") for r in rows)


def test_owner_is_seat_0_in_every_targeted_archive():
    """The whole sign convention rests on this. Verify it, do not inherit it."""
    rows = _targets()
    archives = HERE.parents[0] / "e4_games"
    for stem in sorted({r["game"] for r in rows}):
        arc = json.loads((archives / stem).read_text())
        assert int(arc.get("human_player", -1)) == 0, stem


def test_every_targeted_archive_resolves_to_the_profile_it_was_built_under():
    """The rules profile must come FROM THE ARCHIVE, never from a flag."""
    sys.path.insert(0, str(HERE.parents[1] / "scripts"))
    try:
        from analyzer.ev_loss import resolve_profile_name
    except Exception:                                   # noqa: BLE001
        pytest.skip("carcassonne_ai not importable in this interpreter")
    rows = _targets()
    archives = HERE.parents[0] / "e4_games"
    seen = {}
    for r in rows:
        seen.setdefault(r["game"], r["profile"])
        assert seen[r["game"]] == r["profile"], f"{r['game']} has two profiles"
    for stem, prof in seen.items():
        arc = json.loads((archives / stem).read_text())
        assert resolve_profile_name(arc) == prof, stem


def test_no_outcome_field_is_read_by_the_selector():
    """The selection must be outcome-blind BY CONSTRUCTION, not by discipline."""
    src = (HERE / "build_targets.py").read_text()
    body = src.split('"""', 2)[-1]          # strip the module docstring
    for banned in ("winner", "\"diff\"", "final_scores", "recorded_scores", "margin"):
        assert banned not in body, f"selector references outcome field {banned!r}"
