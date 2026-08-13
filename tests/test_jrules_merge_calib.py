"""Unit tests for the J-rules calibration directory merge + its CRN identity proof.

`measurement/jrules_on_search_20260813/merge_calib_dirs.py` exists because
CALIB_READ_RULE §3.1's stated mechanism for the pre-committed dose-0.25 rung ("an added
`--arm` over the same output directory") is unsound: resume is per-PLY, so the late-added
arm would never be searched and would roll up as 0.00% — a silent null. The rung is
measured in a fresh directory instead, and merged only if the two runs provably searched
the SAME determinized worlds.

These tests are the proof-of-the-proof: synthetic directories, no engine, no searches.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_MOD_PATH = REPO / "measurement" / "jrules_on_search_20260813" / "merge_calib_dirs.py"


def _load():
    spec = importlib.util.spec_from_file_location("jrules_merge_calib_dirs", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mg = _load()


def _write_run(d: Path, arms, picks, *, champ_picks=None, stem="g1", n_graded=None):
    """One synthetic instrument output dir.

    `picks`: {arm_name: [pick per graded ply]}; `champ_picks`: the champion's picks."""
    d.mkdir(parents=True, exist_ok=True)
    n = len(next(iter(picks.values())))
    champ = champ_picks if champ_picks is not None else [10 + i for i in range(n)]
    recs = []
    for i in range(n):
        r = {"ply": 2 * i, "phase": "tiles", "k_remaining": 40 - i, "n_legal": 12,
             "action_played": 100 + i, "champ_pick": champ[i],
             "champ_agrees_archive": False, "secs": 1.0}
        for name in picks:
            r[f"pick_{name}"] = picks[name][i]
            r[f"flip_{name}"] = picks[name][i] != champ[i]
        recs.append(r)
    (d / f"plies_{stem}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    (d / f"game_{stem}.json").write_text(json.dumps({
        "schema": "carcassonne-jrules-e4-replay/v1", "archive": f"{stem}.json",
        "deck_seed": 777, "rules_profile": "fixed_v1", "human_player": 0,
        "champion_seat": 1, "recorded_scores": [80, 75], "replayed_scores": [80, 75],
        "replay_scores_match": True, "partial": False,
        "budget": {"sims_per_det": 1376, "k_dets": 8, "total_per_decision": 11008,
                   "source": "archive"},
        "seed": 12345,
        "arms": [{"name": a, "dose": arms[a], "mask": 31,
                  "rules": ["J1", "J2", "J5", "J6", "J8"],
                  "leaf_hash": f"hash{a}"} for a in picks],
        "leaf_hash_production": "a36d2e15a3b3d71d",
        "n_plies_total": 70, "n_graded": (n if n_graded is None else n_graded),
        "champ_agrees_archive": 0,
        "flips": {a: sum(1 for i in range(n) if picks[a][i] != champ[i]) for a in picks},
        "flip_plies": {a: [{"ply": 2 * i, "phase": "tiles", "k_remaining": 40 - i,
                            "champ_pick": champ[i], f"pick_{a}": picks[a][i]}
                           for i in range(n) if picks[a][i] != champ[i]] for a in picks},
    }, indent=1))
    return d


def test_merge_combines_arms_and_recomputes_the_rollup(tmp_path):
    a = _write_run(tmp_path / "calib", {"d0p5": 0.5, "d1p0": 1.0},
                   {"d0p5": [10, 99, 12, 99], "d1p0": [99, 99, 12, 13]})
    b = _write_run(tmp_path / "calib_d0p25", {"d0p25": 0.25}, {"d0p25": [10, 11, 99, 13]})
    out = tmp_path / "merged"
    sys.argv = ["merge", "--dir", str(a), "--dir", str(b), "-o", str(out)]
    assert mg.main() == 0
    roll = json.loads((out / "SUMMARY.json").read_text())
    # champ picks are 10, 11, 12, 13
    assert roll["flips_total"] == {"d0p5": 2, "d1p0": 2, "d0p25": 1}
    assert roll["n_graded_plies"] == 4
    assert roll["crn_proof"]["champ_picks_compared"] == 4
    assert roll["merged_from"] == ["calib", "calib_d0p25"]


def test_merge_aborts_when_the_champion_pick_differs(tmp_path):
    """The CRN identity proof: different champion picks == different worlds."""
    a = _write_run(tmp_path / "calib", {"d0p5": 0.5}, {"d0p5": [10, 11]},
                   champ_picks=[10, 11])
    b = _write_run(tmp_path / "calib_d0p25", {"d0p25": 0.25}, {"d0p25": [10, 11]},
                   champ_picks=[10, 44])
    sys.argv = ["merge", "--dir", str(a), "--dir", str(b), "-o", str(tmp_path / "m")]
    with pytest.raises(SystemExit, match="CRN PROOF FAILED"):
        mg.main()


def test_merge_aborts_when_the_graded_ply_sets_differ(tmp_path):
    a = _write_run(tmp_path / "calib", {"d0p5": 0.5}, {"d0p5": [10, 11, 12]})
    b = _write_run(tmp_path / "calib_d0p25", {"d0p25": 0.25}, {"d0p25": [10, 11]})
    sys.argv = ["merge", "--dir", str(a), "--dir", str(b), "-o", str(tmp_path / "m")]
    with pytest.raises(SystemExit, match="CRN PROOF FAILED"):
        mg.main()


def test_merge_aborts_on_a_duplicated_arm_name(tmp_path):
    a = _write_run(tmp_path / "calib", {"d0p5": 0.5}, {"d0p5": [10, 11]})
    b = _write_run(tmp_path / "calib2", {"d0p5": 0.5}, {"d0p5": [10, 11]})
    sys.argv = ["merge", "--dir", str(a), "--dir", str(b), "-o", str(tmp_path / "m")]
    with pytest.raises(SystemExit, match="appears in BOTH"):
        mg.main()


def test_merge_aborts_when_a_game_invariant_differs(tmp_path):
    a = _write_run(tmp_path / "calib", {"d0p5": 0.5}, {"d0p5": [10, 11]})
    b = _write_run(tmp_path / "calib_d0p25", {"d0p25": 0.25}, {"d0p25": [10, 11]})
    g = json.loads((b / "game_g1.json").read_text())
    g["deck_seed"] = 778
    (b / "game_g1.json").write_text(json.dumps(g))
    sys.argv = ["merge", "--dir", str(a), "--dir", str(b), "-o", str(tmp_path / "m")]
    with pytest.raises(SystemExit, match="MERGE ABORTED"):
        mg.main()


def test_merge_aborts_when_the_corpora_differ(tmp_path):
    a = _write_run(tmp_path / "calib", {"d0p5": 0.5}, {"d0p5": [10, 11]}, stem="g1")
    _write_run(tmp_path / "calib", {"d0p5": 0.5}, {"d0p5": [10, 11]}, stem="g2")
    b = _write_run(tmp_path / "calib_d0p25", {"d0p25": 0.25}, {"d0p25": [10, 11]},
                   stem="g1")
    sys.argv = ["merge", "--dir", str(a), "--dir", str(b), "-o", str(tmp_path / "m")]
    with pytest.raises(SystemExit, match="corpora differ"):
        mg.main()


def test_merge_requires_two_directories(tmp_path):
    a = _write_run(tmp_path / "calib", {"d0p5": 0.5}, {"d0p5": [10, 11]})
    sys.argv = ["merge", "--dir", str(a), "-o", str(tmp_path / "m")]
    with pytest.raises(SystemExit, match="at least two"):
        mg.main()
