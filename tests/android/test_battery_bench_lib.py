"""Host tests for the battery A/B bench.

Two layers:

* ``battery_bench_lib`` — the driver's pure math (ABAB schedule, sign/unit
  normalization, trapezoid integration, the move-hash identity gate, report
  assembly). No device, no adb.
* ``carc_bench`` — the ON-DEVICE workload module, run here on the desktop at a
  tiny budget through the real ``android_bridge``/``carc_rs`` stack, proving
  the load-bearing claim end-to-end: two different ``rust_threads`` values
  produce the identical ``move_hash`` (thread-count invariance of the rust
  search), and the E4-archive guard refuses a ``games`` out_dir.

``conftest.py`` puts both ``android/app/src/main/python`` and ``android/tools``
on ``sys.path``; ``carc_bench`` lives in the debug sourceset, added here.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

import battery_bench_lib as L

REPO = Path(__file__).resolve().parents[2]
DEBUG_PY = REPO / "android" / "app" / "src" / "debug" / "python"
if str(DEBUG_PY) not in sys.path:
    sys.path.insert(0, str(DEBUG_PY))


# --------------------------------------------------------------------------- #
# schedule
# --------------------------------------------------------------------------- #
def test_schedule_interleaves_every_arm_in_every_rep():
    plan = L.abab_schedule([4, 2, 1], 3)
    assert [arm for _, arm, _ in plan] == [4, 2, 1, 4, 2, 1, 4, 2, 1]
    assert [rep for rep, _, _ in plan] == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    tags = [t for _, _, t in plan]
    assert len(set(tags)) == 9
    assert tags[0] == "t4_r1" and tags[-1] == "t1_r3"


def test_schedule_rejects_bad_input():
    with pytest.raises(ValueError):
        L.abab_schedule([], 3)
    with pytest.raises(ValueError):
        L.abab_schedule([4, 4], 3)
    with pytest.raises(ValueError):
        L.abab_schedule([4, 0], 3)
    with pytest.raises(ValueError):
        L.abab_schedule([4], 0)


# --------------------------------------------------------------------------- #
# samples: parsing, sign, units
# --------------------------------------------------------------------------- #
def _lines(rows):
    return "\n".join(" ".join(str(x) for x in r) for r in rows)


def test_parse_samples_skips_garbage_and_sorts():
    text = _lines([(2000, -500000, 4000000), (1000, -400000, 4000000)])
    text += "\nnot a line\n123 456\n"
    s = L.parse_samples(text)
    assert [t for t, _, _ in s] == [1000.0, 2000.0]


def test_sign_detection_both_conventions():
    neg = [(0, -500000.0, 4e6), (1000, -480000.0, 4e6), (2000, -510000.0, 4e6)]
    pos = [(t, -i, v) for t, i, v in neg]
    assert L.detect_sign(neg) == -1
    assert L.detect_sign(pos) == 1
    # Either way the normalized discharge power is positive and equal.
    pw_neg = L.power_series(neg, -1)
    pw_pos = L.power_series(pos, 1)
    assert pw_neg == pw_pos
    assert all(w > 0 for _, w in pw_neg)


def test_unit_sanity_rejects_millivolt_scale():
    mv = [(0, -500000.0, 4000.0), (1000, -500000.0, 4000.0), (2000, -500000.0, 4000.0)]
    with pytest.raises(ValueError, match="µV sanity"):
        L.check_units(mv)
    L.check_units([(0, -5e5, 4e6), (1, -5e5, 4e6)])  # µV passes


# --------------------------------------------------------------------------- #
# integration
# --------------------------------------------------------------------------- #
def test_trapezoid_constant_power():
    # 2 W held for 10 s = 20 J; samples at 1 Hz, window exactly on samples.
    power = [(t * 1000.0, 2.0) for t in range(11)]
    assert L.integrate_joules(power, 0, 10_000) == pytest.approx(20.0)
    assert L.mean_watts(power, 0, 10_000) == pytest.approx(2.0)


def test_trapezoid_interpolates_window_edges():
    # Power ramps 0 -> 10 W over 10 s (linear): integral over [2.5 s, 7.5 s]
    # is the exact trapezoid 0.5*(2.5+7.5)*5 = 25 J; edges are between samples.
    power = [(t * 1000.0, float(t)) for t in range(11)]
    assert L.integrate_joules(power, 2500, 7500) == pytest.approx(25.0)


def test_trapezoid_refuses_dead_sampler_windows():
    power = [(t * 1000.0, 2.0) for t in range(11)]
    with pytest.raises(ValueError, match="samples inside"):
        L.integrate_joules(power, 50_000, 60_000)
    # Sampler died 20 s before the window end and there is nothing after it.
    power_gap = [(t * 1000.0, 2.0) for t in range(11)]
    with pytest.raises(ValueError, match="before window end"):
        L.integrate_joules(power_gap, 0, 30_000)


# --------------------------------------------------------------------------- #
# identity gate
# --------------------------------------------------------------------------- #
def _run(tag, h, **kw):
    base = {"ok": True, "tag": tag, "move_hash": h, "rust_threads": 4,
            "t_start_ms": 0, "t_end_ms": 10_000, "n_moves": 10,
            "s_per_move_mean": 1.0, "seed": 1, "k_dets": 8,
            "sims_per_det": 1376, "total_sims": 11008,
            "rules_profile": "fixed_v1", "backend": "rust"}
    base.update(kw)
    return base


def test_check_hashes_pass_and_fail():
    ok, _ = L.check_hashes([_run("a", "h1"), _run("b", "h1")])
    assert ok
    ok, by = L.check_hashes([_run("a", "h1"), _run("b", "h2")])
    assert not ok and by == {"a": "h1", "b": "h2"}
    ok, _ = L.check_hashes([_run("a", "h1"), {"tag": "b"}])  # missing hash
    assert not ok
    ok, _ = L.check_hashes([])
    assert not ok


def test_build_report_aborts_on_hash_mismatch_without_energy():
    runs = [_run("t4_r1", "h1", rust_threads=4),
            _run("t2_r1", "h2", rust_threads=2)]
    samples = _lines([(t * 1000, -500000, 4000000) for t in range(12)])
    with pytest.raises(SystemExit) as e:
        L.build_report(runs, samples, None)
    msg = str(e.value)
    assert "ABORT" in msg and "move_hash" in msg
    assert "J" not in msg.split("ABORT")[0]  # nothing energy-ish precedes it


def test_build_report_aborts_on_failed_run():
    runs = [_run("t4_r1", "h1"),
            {"ok": False, "tag": "t2_r1", "error": "boom"}]
    with pytest.raises(SystemExit, match="failed bench runs"):
        L.build_report(runs, "", None)


def test_build_report_happy_path_math():
    # Two arms, one rep each; constant 500 mA at 4 V -> 2 W. Arm windows of
    # 10 s and 20 s at 10 moves -> 2 J/move and 4 J/move.
    runs = [
        _run("t4_r1", "h", rust_threads=4, t_start_ms=10_000, t_end_ms=20_000,
             s_per_move_mean=1.0),
        _run("t1_r1", "h", rust_threads=1, t_start_ms=40_000, t_end_ms=60_000,
             s_per_move_mean=2.0),
    ]
    samples = _lines([(t * 1000, -500000, 4000000) for t in range(65)])
    report, md = L.build_report(runs, samples, baseline=(0, 8000))
    arms = report["arms"]
    assert arms[4]["j_per_move_mean"] == pytest.approx(2.0)
    assert arms[1]["j_per_move_mean"] == pytest.approx(4.0)
    assert math.isnan(arms[4]["j_per_move_sd"])          # n=1 rep
    assert report["baseline_watts"] == pytest.approx(2.0)
    # Net column: baseline exactly cancels a constant-power workload.
    assert arms[4]["j_per_move_net_mean"] == pytest.approx(0.0, abs=1e-9)
    assert report["hash_identical_across_runs"] is True
    assert "| rust_threads |" in md and "PASS" in md
    assert report["sign_convention"].startswith("current_now negative")


# --------------------------------------------------------------------------- #
# the on-device workload module, on the desktop stack
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def carc_rs_present():
    pytest.importorskip("carc_rs")


def _device_run(tmp_path, threads, tag, **kw):
    import carc_bench

    out = json.loads(carc_bench.run_bench(
        kw.pop("n_moves", 4), threads, kw.pop("seed", 977), str(tmp_path), tag,
        sims=kw.pop("sims", 16), k_dets=kw.pop("k_dets", 1)))
    return out


def test_carc_bench_identical_hash_across_thread_counts(tmp_path, carc_rs_present):
    """The whole point of the harness, end-to-end at a tiny budget: two arms
    with different rust_threads report the identical move hash and trace."""
    a = _device_run(tmp_path, 1, "t1_r1")
    b = _device_run(tmp_path, 2, "t2_r1")
    assert a["ok"] and b["ok"], (a.get("error"), b.get("error"))
    assert a["backend"] == "rust" and b["backend"] == "rust"
    assert a["rust_threads"] == 1 and b["rust_threads"] == 2
    assert a["move_hash"] == b["move_hash"]
    assert a["n_moves"] == 4 and len(a["per_move_ms"]) == 4
    assert a["t_end_ms"] >= a["t_start_ms"]
    # The result files landed where the service would put them, atomically.
    assert json.loads((tmp_path / "t1_r1.json").read_text())["tag"] == "t1_r1"
    # And the two files' hashes gate PASS through the host-side check.
    ok, _ = L.check_hashes([a, b])
    assert ok


def test_carc_bench_seed_changes_the_hash(tmp_path, carc_rs_present):
    """The witness is not vacuous: different work -> different hash."""
    a = _device_run(tmp_path, 1, "s1", seed=977)
    b = _device_run(tmp_path, 1, "s2", seed=978)
    assert a["ok"] and b["ok"]
    assert a["move_hash"] != b["move_hash"]


def test_carc_bench_refuses_the_archive_dir(tmp_path, carc_rs_present):
    import carc_bench

    games = tmp_path / "games"
    games.mkdir()
    out = json.loads(carc_bench.run_bench(1, 1, 1, str(games), "x",
                                          sims=8, k_dets=1))
    assert not out["ok"] and "E4 archive" in out["error"]
    assert list(games.iterdir()) == []  # nothing written there


def test_carc_bench_error_lands_as_json_not_exception(tmp_path, carc_rs_present):
    import carc_bench

    out = json.loads(carc_bench.run_bench(0, 1, 1, str(tmp_path), "bad",
                                          sims=8, k_dets=1))
    assert not out["ok"] and "n_moves" in out["error"]
    assert (tmp_path / "bad.json").exists()
