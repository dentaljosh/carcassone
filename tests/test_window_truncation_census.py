"""Contracts for the window-truncation census instrument.

`scripts/measurement_infra/window_truncation_census.py` measures how often the
champion's OWN PUCT search loses LEGAL actions to the 25x25 centroid action
window. It is a read-only instrument, so every one of its claims has to be
earned by a test rather than by a patched engine:

  A. `remap_action` is a bijection between window index spaces, and it PRESERVES
     ORDER -- the property the whole "wide window is the same search" argument
     rests on.
  B. Seating a mirror at W=25 and at W=71 in lockstep describes the same
     position at every step (`string_repr` is window-independent).
  C. NULL CONTROL -- with no truncation anywhere, the narrow and the wide search
     are BIT-IDENTICAL after remapping (pooled stats, chosen action, node count).
     If this ever fails, the decision-impact leg is meaningless.
  D. POSITIVE CONTROL -- squeeze the window until truncation must happen, and the
     census must SEE it. A census that only ever reports zero is unfalsifiable.
  E. LEGAL vs ILLEGAL -- every dropped action is verified to be LEGAL: the wide
     window's engine enumeration (`n_total`) is IDENTICAL, the wide window drops
     nothing (`n_overflow == 0`), and the narrow legal set is a strict subset of
     the wide one.
  F. The census's own gates (digest gate, encode-collision gate, iso control)
     stay green on a real banked root.

These run at tiny sim budgets on a self-contained synthetic root, so the file is
fast and needs no share mount. The one test that reads the CL-070 bank skips if
the share is not mounted.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "scripts" / "human_anchor", REPO / "scripts" / "measurement_infra"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env_preamble  # noqa: F401,E402

carc_rs = pytest.importorskip("carc_rs")

import window_truncation_census as WTC  # noqa: E402

BANK = "/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl"
DECK_SEED = 1260000001
NARROW = WTC.NARROW_WINDOW
WIDE = WTC.WIDE_WINDOW_DEFAULT


# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def prod():
    from carcassonne_ai import champion_factory as CF

    spec = CF.load_production_spec()
    return spec, CF.production_prior_cfg(spec)


@pytest.fixture(scope="module")
def synth_root():
    """A self-contained mid-game root: a fixed pseudo-random 90-ply playout.

    Recorded as (deck_seed, prefix, checksum) in the W=25 index space -- the same
    shape the banked roots use, so the census code path under test is the real one.
    """
    ms = carc_rs.MirrorState.from_seed(str(DECK_SEED))
    rng = random.Random(7)
    prefix = []
    for _ in range(90):
        la = ms.legal_actions()
        if not la:
            break
        a = rng.choice(la)
        prefix.append(a)
        ms.advance(a)
    return {"deck_seed": DECK_SEED, "ply": len(prefix), "actions": prefix,
            "checksum": ms.string_repr(), "player_to_move": ms.current_player(),
            "rid": "synth_p%d" % len(prefix)}


def _opt(**kw):
    d = dict(k_dets=2, sims=96, geom={}, wide=True, wide_window=WIDE,
             narrow_window=NARROW, replay_fraction=1.0, max_examples=64,
             verify_dropped_are_legal=True, verify_all_truncated=True,
             agent_seed=101, agent_seed_mode="fixed", trace_dir="", trace_path="")
    d.update(kw)
    return WTC._Opt(**d)


# --------------------------------------------------------------------------- #
# A. remap_action                                                              #
# --------------------------------------------------------------------------- #
def test_remap_is_a_bijection_and_round_trips():
    off_a, off_b = (5, 3, 25), (-13, -15, 71)
    seen = set()
    for wr in range(25):
        for wc in range(25):
            for rot in range(4):
                a = (wr * 25 + wc) * 4 + rot
                b = WTC.remap_action(a, off_a, off_b, "tiles")
                assert b not in seen
                seen.add(b)
                assert WTC.remap_action(b, off_b, off_a, "tiles") == a
    # tile-Pass and every meeple slot
    assert WTC.remap_action(25 * 25 * 4, off_a, off_b, "tiles") == 71 * 71 * 4
    for slot in range(10):
        a = 25 * 25 * 4 + 1 + slot
        b = WTC.remap_action(a, off_a, off_b, "meeples")
        assert b == 71 * 71 * 4 + 1 + slot
        assert WTC.remap_action(b, off_b, off_a, "meeples") == a


def test_remap_preserves_order():
    """THE load-bearing property: `valid_actions` is index-sorted, so if the remap
    preserves order the search enumerates the same actions in the same order at
    any window size."""
    off_a, off_b = (5, 3, 25), (-13, -15, 71)
    xs = list(range(0, 25 * 25 * 4, 37)) + [25 * 25 * 4]
    ys = [WTC.remap_action(x, off_a, off_b, "tiles") for x in xs]
    assert ys == sorted(ys)
    assert all(y0 < y1 for y0, y1 in zip(ys, ys[1:]))


def test_remap_refuses_an_escaping_action():
    with pytest.raises(ValueError):
        WTC.remap_action(0, (0, 0, 25), (10, 10, 9), "tiles")


# --------------------------------------------------------------------------- #
# B. lockstep seating                                                          #
# --------------------------------------------------------------------------- #
def test_lockstep_seating_is_the_same_position(synth_root):
    seat = WTC.RootSeat(synth_root["deck_seed"], synth_root["actions"],
                        geom={}, wide_window=WIDE)
    n, w = seat.seat(), seat.seat_wide()
    assert n.string_repr() == w.string_repr() == synth_root["checksum"]
    assert n.state_digest() != w.state_digest()      # differs ONLY by the window
    assert n.window_offset()[2] == NARROW and w.window_offset()[2] == WIDE


def test_wide_window_never_overflows(synth_root):
    """W=71 is claimed overflow-free (board is 35x35). Check it on the root and on
    a hundred descendants."""
    seat = WTC.RootSeat(synth_root["deck_seed"], synth_root["actions"],
                        geom={}, wide_window=WIDE)
    w = seat.seat_wide()
    rng = random.Random(11)
    for _ in range(100):
        assert w.mask_counts()[1] == 0
        la = w.legal_actions()
        if not la:
            break
        w.advance(rng.choice(la))


# --------------------------------------------------------------------------- #
# C. NULL CONTROL -- window isomorphism                                        #
# --------------------------------------------------------------------------- #
def test_search_is_bit_identical_under_a_wider_window(synth_root, prod):
    from carcassonne_ai.rust_agent import search_config_rs

    _spec, cfg = prod
    scfg = search_config_rs(cfg, 256)
    seat = WTC.RootSeat(synth_root["deck_seed"], synth_root["actions"],
                        geom={}, wide_window=WIDE)
    n, w = seat.seat(), seat.seat_wide()
    assert n.mask_counts()[1] == 0, "the fixture root must be untruncated"
    rn, rw = n.search_single(scfg), w.search_single(scfg)

    off_n, off_w, ph = n.window_offset(), w.window_offset(), n.phase()
    pn = {WTC.remap_action(a, off_n, off_w, ph): (v, b) for a, v, b in rn["pooled_stats"]}
    pw = {a: (v, b) for a, v, b in rw["pooled_stats"]}
    assert pn == pw                                   # bit-identical (W is raw f64 bits)
    assert rn["node_count"] == rw["node_count"]
    assert rn["leaf_evals"] == rw["leaf_evals"]
    assert WTC.remap_action(rn["chosen_action"], off_n, off_w, ph) == rw["chosen_action"]


# --------------------------------------------------------------------------- #
# D+E. POSITIVE CONTROL and the legal-vs-illegal distinction                    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("narrow", [15])
def test_positive_control_census_sees_truncation(synth_root, narrow, tmp_path):
    """Squeeze the window until truncation is forced; the census must report it,
    and every dropped action must be verified LEGAL."""
    opt = _opt(narrow_window=narrow, trace_dir=str(tmp_path),
               trace_path=str(tmp_path / "t.jsonl"))
    WTC._SPEC = WTC._CFG = None
    rec = WTC.census_root(dict(synth_root), opt)
    assert rec["ok"] and rec["error"] is None
    assert rec["checksum_ok"]
    assert rec["n_nodes_censused"] > 0
    assert rec["n_nodes_truncated"] > 0, (
        "positive control did not fire -- the instrument cannot see truncation, "
        "or the fixture stopped overflowing at W=%d" % narrow)
    assert rec["digest_gate_fail"] == 0
    assert rec["sum_dropped"] >= rec["n_nodes_truncated"]
    # E: every recorded truncated node proves its dropped actions were LEGAL
    assert rec["examples"], "a truncated node must be exampled"
    for ex in rec["examples"]:
        assert ex["dropped_all_legal"] is True
        assert ex["wide_n_overflow"] == 0             # the reference window drops nothing
        assert ex["wide_n_total"] == ex["narrow_n_total"]   # SAME engine enumeration
        assert ex["n_extra_in_narrow"] == 0           # narrow is a strict subset
        assert ex["n_dropped_by_setdiff"] == ex["n_overflow"]
        assert ex["n_encoded"] == ex["n_total"] - ex["n_overflow"]
    # the iso null control is correctly SUPPRESSED once truncation exists
    assert rec["iso_ok"] is None


def test_census_is_clean_at_the_production_window(synth_root, tmp_path):
    """Same fixture, production window: no truncation, and the built-in null
    control (`iso_ok`) is green."""
    opt = _opt(trace_dir=str(tmp_path), trace_path=str(tmp_path / "t.jsonl"))
    WTC._SPEC = WTC._CFG = None
    rec = WTC.census_root(dict(synth_root), opt)
    assert rec["ok"] and rec["n_nodes_censused"] > 0
    assert rec["n_nodes_truncated"] == 0
    assert rec["n_nodes_empty_mask"] == 0
    assert rec["digest_gate_fail"] == 0
    assert rec.get("encode_collision") is not True
    assert rec["iso_ok"] is True, "narrow/wide diverged with ZERO truncation -- instrument bug"
    assert rec["pick_changed"] is False


def test_node_count_is_window_invariant(synth_root, tmp_path):
    """A corollary of the isomorphism, and a cheap guard against the census
    accidentally censusing a DIFFERENT tree at a different window."""
    WTC._SPEC = WTC._CFG = None
    a = WTC.census_root(dict(synth_root),
                        _opt(trace_dir=str(tmp_path), trace_path=str(tmp_path / "a.jsonl")))
    b = WTC.census_root(dict(synth_root),
                        _opt(narrow_window=17, trace_dir=str(tmp_path),
                             trace_path=str(tmp_path / "b.jsonl")))
    assert a["n_nodes_censused"] == b["n_nodes_censused"] > 0
    assert a["n_exp_records"] == b["n_exp_records"]


# --------------------------------------------------------------------------- #
# F. trace parsing + aggregation                                               #
# --------------------------------------------------------------------------- #
def test_parse_trace_matches_the_search(synth_root, prod, tmp_path):
    from carcassonne_ai.rust_agent import search_config_rs

    _spec, cfg = prod
    seat = WTC.RootSeat(synth_root["deck_seed"], synth_root["actions"],
                        geom={}, wide_window=WIDE)
    ms = seat.seat()
    p = str(tmp_path / "trace.jsonl")
    res = ms.search_single(search_config_rs(cfg, 128), p, True)
    sims, n_exp, n_empty = WTC.parse_trace(p)
    assert len(sims) == 128
    assert n_exp == res["node_count"]
    assert n_empty == 0
    # every sim's terminus is reconstructible and matches the trace digest
    for si, pth, acts in sims[:16]:
        m = seat.seat()
        for a in acts:
            m.advance(a)
        assert WTC.digest16(m.string_repr()) == pth[-1]
        assert len(pth) == len(acts) + 1


def test_summarize_rates(tmp_path):
    rows = [
        {"ok": True, "n_nodes_censused": 100, "n_nodes_truncated": 4,
         "n_nodes_empty_mask": 1, "visits_total": 1000, "visits_through_truncated": 20,
         "by_depth": {"3": [100, 4, 8]}, "by_node_phase": {"tiles": [100, 4, 8]},
         "by_k_bucket": {"late": [100, 4, 8]}, "dropped_hist": {"0": 96, "2": 4},
         "pick_changed": True, "iso_ok": None, "root_truncated": False, "secs": 1.0},
        {"ok": True, "n_nodes_censused": 100, "n_nodes_truncated": 0,
         "n_nodes_empty_mask": 0, "visits_total": 1000, "visits_through_truncated": 0,
         "by_depth": {"3": [100, 0, 0]}, "by_node_phase": {"tiles": [100, 0, 0]},
         "by_k_bucket": {"late": [100, 0, 0]}, "dropped_hist": {"0": 100},
         "pick_changed": False, "iso_ok": True, "root_truncated": False, "secs": 1.0},
        {"ok": True, "skipped": "forced", "root_truncated": False, "secs": 0.1},
    ]
    s = WTC.summarize(rows)
    assert s["n_censused_roots"] == 2
    assert s["nodes_censused"] == 200 and s["nodes_truncated"] == 4
    assert s["node_truncation_rate"] == pytest.approx(0.02)
    assert s["visit_weighted_truncation_rate"] == pytest.approx(0.01)
    assert s["root_incidence_rate"] == pytest.approx(0.5)
    assert s["pick_change_rate"] == pytest.approx(0.5)
    assert s["iso_control_n"] == 1 and s["iso_control_violations"] == 0
    assert s["n_skipped_forced"] == 1
    assert s["dropped_hist"] == {"0": 196, "2": 4}


# --------------------------------------------------------------------------- #
# G. a real banked root (skips without the share)                              #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not os.path.exists(BANK), reason="CL-070 bank not mounted")
def test_real_banked_root_passes_every_gate(tmp_path):
    root = None
    with open(BANK) as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("phase") == "TILES" and r.get("ok"):
                root = r
                break
    assert root is not None
    WTC._SPEC = WTC._CFG = None
    rec = WTC.census_root(root, _opt(trace_dir=str(tmp_path),
                                     trace_path=str(tmp_path / "t.jsonl")))
    assert rec["ok"], rec.get("error")
    assert rec["checksum_ok"], "the seated mirror is not the banked root"
    assert rec["digest_gate_fail"] == 0
    assert rec.get("encode_collision") is not True
    assert rec["root_n_encoded"] == rec["root_n_total"] - rec["root_n_overflow"]
    if rec["root_n_overflow"] == 0 and rec["n_nodes_truncated"] == 0:
        assert rec["iso_ok"] is True
