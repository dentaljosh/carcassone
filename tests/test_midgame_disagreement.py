"""scripts/classical_search/midgame_disagreement.py — diagnostic (a) of
TEACHER_TAU_PLAN.md "NEXT": the MIDGAME leaf-prior vs teacher-move disagreement
gate.

Contracts:
  1. The pure classifier core (dedup_by_key + classify) computes agree/disagree,
     the top-2 Δleaf noise gap, and the "real disagreement" filters correctly on
     HAND-CHECKED synthetic cases — including transposition-alias dedup (two legal
     actions -> the SAME successor board key count as the SAME move).
  2. The CLI end-to-end plumbing runs on real midgame roots (N=3, sims=64) and
     emits a well-formed JSON report (no solver, no net).

midgame_disagreement.py mutates os.environ at import (via eval_puct_priors's
_CANON_ENV), so all work runs in ONE subprocess (same isolation pattern as
test_solver_score_agent.py); the pytest side asserts on its JSON output.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
QPROBE = REPO / "measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl"
POOL = REPO / "measurement/high_gap_distillation/scaled/pool_A.jsonl"

pytestmark = pytest.mark.skipif(
    not (QPROBE.exists() and POOL.exists()),
    reason="qprobe_A/pool_A sibling-root files not present on this box",
)

_SCRIPT = r"""
import json, sys
repo, out_path, smoke_out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, repo + "/scripts/classical_search")
import numpy as np
import midgame_disagreement as MD

res = {}

# ---- 1: pure dedup + classify on hand-checked synthetic cases -----------------
# case c1: 3 distinct children A/B/C, prior mass 0.2/0.7/0.1 -> leaf-prior = B.
#          teacher plays A (disagree), big gap, high share -> REAL.
dk, dw, reps = MD.dedup_by_key([3, 7, 5], np.array([0.2, 0.7, 0.1]),
                               {3: "A", 7: "B", 5: "C"})
c1 = MD.classify(dk, dw, teacher_key="A", teacher_visit_share=0.4,
                 tau=5.0, top_share_min=0.15, gap_eps=0.5)

# case c2: ALIASING — actions 3 & 4 lead to the SAME board "X"; teacher plays
#          action 4 (key "X"), leaf-prior rep is action 3 (key "X") -> AGREE
#          even though the raw action ints differ.
dk2, dw2, reps2 = MD.dedup_by_key([3, 4, 7], np.array([0.45, 0.45, 0.10]),
                                  {3: "X", 4: "X", 7: "Y"})
c2 = MD.classify(dk2, dw2, teacher_key="X", teacher_visit_share=0.9,
                 tau=5.0, top_share_min=0.15, gap_eps=0.5)

# case c3: teacher == leaf-prior (both B) -> AGREE, not real.
c3 = MD.classify(dk, dw, teacher_key="B", teacher_visit_share=0.9,
                 tau=5.0, top_share_min=0.15, gap_eps=0.5)

# case c4: disagree but TINY gap (near-tied leaf) -> not real (within noise).
c4 = MD.classify(["A", "B", "C"], np.array([0.34, 0.33, 0.33]),
                 teacher_key="B", teacher_visit_share=0.9,
                 tau=5.0, top_share_min=0.15, gap_eps=0.5)

# case c5: disagree, big gap, but LOW teacher visit share -> not real.
c5 = MD.classify(dk, dw, teacher_key="A", teacher_visit_share=0.10,
                 tau=5.0, top_share_min=0.15, gap_eps=0.5)

res["synthetic"] = {
    "dedup1": {"keys": dk, "weights": [round(float(x), 6) for x in dw], "reps": reps},
    "dedup2": {"keys": dk2, "weights": [round(float(x), 6) for x in dw2], "reps": reps2},
    "c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5,
}

# ---- 2: tiny real smoke via the CLI main() — 3 midgame roots, sims=64 ---------
rc = MD.main(["--n", "3", "--sims", "64", "--workers", "1",
              "--seed-shuffle", "1234", "--out", smoke_out])
assert rc == 0, rc
res["smoke"] = json.load(open(smoke_out))

json.dump(res, open(out_path, "w"))
print("SUBPROC_OK")
"""


@pytest.fixture(scope="module")
def sub(tmp_path_factory):
    d = tmp_path_factory.mktemp("md")
    out, smoke = d / "res.json", d / "smoke.json"
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(REPO), str(out), str(smoke)],
        capture_output=True, text=True, timeout=900, cwd=str(REPO),
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "SUBPROC_OK" in proc.stdout
    return json.loads(out.read_text())


def test_dedup_by_key(sub):
    s = sub["synthetic"]
    # 3 distinct children preserved in first-appearance order, reps = the actions.
    assert s["dedup1"]["keys"] == ["A", "B", "C"]
    assert s["dedup1"]["reps"] == [3, 7, 5]
    assert s["dedup1"]["weights"] == [0.2, 0.7, 0.1]
    # aliasing: actions 3 & 4 collapse to key "X" (rep = lowest index 3), 7 -> "Y".
    assert s["dedup2"]["keys"] == ["X", "Y"]
    assert s["dedup2"]["reps"] == [3, 7]
    assert s["dedup2"]["weights"] == [0.45, 0.10]


def test_classify_agree_disagree_and_noise(sub):
    s = sub["synthetic"]
    # c1: leaf-prior = B (0.7), teacher = A -> disagree; gap = 5*(ln0.7 - ln0.2).
    c1 = s["c1"]
    assert c1["leaf_prior_key"] == "B"
    assert c1["agree"] is False
    assert abs(c1["top2_gap"] - 5.0 * (math.log(0.7) - math.log(0.2))) < 1e-3
    assert c1["real_disagreement"] is True

    # c2: aliasing -> teacher key "X" == leaf-prior key "X" -> AGREE, not real.
    c2 = s["c2"]
    assert c2["leaf_prior_key"] == "X"
    assert c2["agree"] is True
    assert c2["real_disagreement"] is False

    # c3: teacher == leaf-prior -> agree, not real.
    assert s["c3"]["agree"] is True and s["c3"]["real_disagreement"] is False

    # c4: disagree but tiny gap (5*ln(0.34/0.33) ~ 0.149 < 0.5) -> not real.
    c4 = s["c4"]
    assert c4["agree"] is False
    assert c4["top2_gap"] < 0.5
    assert c4["real_disagreement"] is False

    # c5: disagree + big gap, but low teacher share (0.10 < 0.15) -> not real.
    c5 = s["c5"]
    assert c5["agree"] is False
    assert c5["top2_gap"] > 0.5
    assert c5["real_disagreement"] is False


def test_smoke_report_well_formed(sub):
    rep = sub["smoke"]
    for key in ("manifest", "aggregate", "by_k", "per_root", "n_in_band"):
        assert key in rep, key
    man = rep["manifest"]
    assert man["solver_used"] is False and man["net_used"] is False
    assert man["agent"]["teacher_selector"] == "visit_argmax"
    assert man["midgame_band"] == [15, 45]
    assert rep["n_in_band"] >= 3

    agg = rep["aggregate"]
    assert agg["n_scored"] == len(rep["per_root"]) >= 1
    for rate in ("disagreement_rate", "real_disagreement_rate"):
        assert 0.0 <= agg[rate] <= 1.0
    assert agg["real_disagreement_rate"] <= agg["disagreement_rate"]
    assert agg["gate_bar"] == 0.20

    for r in rep["per_root"]:
        assert 15 <= r["k"] <= 45
        assert r["n_legal"] >= 2 and 1 <= r["n_distinct"] <= r["n_legal"]
        assert isinstance(r["agree"], bool) and r["disagree"] == (not r["agree"])
        assert isinstance(r["real_disagreement"], bool)
        # real disagreement is a strict subset of disagreement.
        assert (not r["real_disagreement"]) or r["disagree"]
        assert r["top_share"] is None or 0.0 < r["top_share"] <= 1.0
        assert 0.0 <= r["teacher_visit_share"] <= 1.0
        assert r["top2_gap"] is None or r["top2_gap"] >= -1e-9
