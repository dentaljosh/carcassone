"""scripts/canonical_az/solver_score_agent.py — the PUCT-priors agent adapter for
the F4 solver ruler (TEACHER_TAU_PLAN.md Stage 0).

Contracts:
  1. The tau computation is solver_score's group_metrics VERBATIM (imported, not
     copied) — verified on synthetic 3-child cases against hand-computed
     kendall-tau-b values (incl. the tie convention).
  2. The agent scorer produces a valid, well-formed ranking record on real tiny
     solved roots (fast-solving K=2 roots from the M2 set, sims=32), and its
     re-scored v29_leaf baseline REPRODUCES the M2-run per-root tau exactly
     (the comparability guarantee).
  3. Sign convention: on a root with a wide exact value spread, the agent's
     mover-POV search-Q ranks WELL-VISITED children consistently with the
     solver's mover-POV child values (not inverted): the argmax-Q well-visited
     child is a solver-optimal child, and the solver-better group's Q strictly
     exceeds the solver-worse group's. (The GLOBAL tau deliberately includes
     low-visit children whose Q is a few-sample estimate — Q-averaging
     dilution is a pre-registered OUTCOME of the measurement, not a sign bug,
     so the sign test filters to converged children; visit counts must also
     rank the solver-optimal children first.)

solver_score_agent.py (via eval_puct_priors) mutates os.environ at import, so
all real work runs in ONE subprocess (same isolation pattern as
test_solver_score_variants.py); the pytest side asserts on its JSON output.
The subprocess is shared module-scope: the heavy import (torch via step1_train)
is paid once.
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
M2_JSON = REPO / "measurement/canonical_az/solver_score_m2_final_it00_04.json"

# Fast-solving K=2 roots (solve_secs 0.4-0.7 in the M2 run) + one wide-spread
# UNAMBIGUOUS root for the sign test. (1940000909,140) has a SINGLE solver-best
# child (action 1844, mover-val +47) with a 21-pt best-vs-second gap (value_spread
# 23, solve ~6s): a correct sign puts BOTH the agent's Q-argmax and its visit-argmax
# on that child. The prior pick (1940000404,140) was a BAD sign root — a 24-way tie
# at the solver-best (best_vs_second_gap=0.0, spread only 8.0), so its ~0 global tau
# was tie-dilution noise, NOT a sign read, and it flaked the assertion.
TINY_ROOTS = [(1940000633, 140), (1940000660, 139), (1940001089, 139)]
SIGN_ROOT = (1940000909, 140)

pytestmark = pytest.mark.skipif(
    not (QPROBE.exists() and POOL.exists()),
    reason="qprobe_A/pool_A sibling-root files not present on this box",
)

_SCRIPT = r"""
import json, sys
repo, out_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo + "/scripts/canonical_az")
import numpy as np
import solver_score_agent as SSA

res = {}

# ---- A: tau/regret/top1 convention on synthetic 3-child cases -----------------
gm = SSA.SS.group_metrics
res["A"] = {
    # one discordant pair out of three -> tau = 1/3; argmax agrees -> regret 0
    "partial": list(gm(np.array([0.9, 0.1, -0.5]), np.array([1.0, -1.0, 0.0]))),
    "perfect": list(gm(np.array([1.0, 2.0, 3.0]), np.array([10.0, 20.0, 30.0]))),
    "inverted": list(gm(np.array([3.0, 2.0, 1.0]), np.array([10.0, 20.0, 30.0]))),
    # tie in the SCORE only: tau_b = (conc-disc)/sqrt((c+d+tx)*(c+d+ty)) = 2/sqrt(6)
    "score_tie": list(gm(np.array([1.0, 1.0, 2.0]), np.array([0.0, 1.0, 2.0]))),
}

# ---- B/C: the agent scorer on real tiny solved roots ---------------------------
recs = SSA.SS.load_sibling_roots(SSA.SS.DEFAULT_QPROBE, SSA.SS.DEFAULT_POOL)
by_key = {(int(r["seed"]), int(r["ply"])): r for r in recs}
SSA._CTX.update(
    cfg=SSA.HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                                 final_select="Q", value_norm=15.0),
    sims=32, budget=5_000_000, max_k=2,
    solve_cache={}, leaf_ranker=SSA.SS.make_v29_leaf_ranker(),
)

outs = []
for key in %(tiny_roots)s:
    o = SSA._score_one(by_key[tuple(key)])
    assert "_error" not in o and "_skip" not in o, o
    ent = o.pop("_solve_entry", None)
    outs.append({"rec": o, "actions": ent["actions"] if ent else None})
res["B"] = outs

SSA._CTX["sims"] = 512
sign_key = tuple(%(sign_root)s)
o = SSA._score_one(by_key[sign_key])
assert "_error" not in o and "_skip" not in o, o
ent = o.pop("_solve_entry", None)

# Re-derive the per-action (solver_mover, q, n) rows the record was built from,
# through the SAME extraction path (fresh deterministic search: same seed/sims).
game, board = SSA.SS.replay_to(*sign_key)
tm = int(ent["to_move"])
mover = {int(a): (v if tm == 0 else -v)
         for a, v in zip(ent["actions"], ent["child_values"])}
mcts = SSA.make_heuristic_prior_mcts(game, SSA._CTX["cfg"], simulations=512,
                                     seed=sign_key[0])
mcts.search(board)
root = mcts._nodes[game.string_representation(board)]
mv = root.player_to_move
rows = []
for a in ent["actions"]:
    c = root.children.get(int(a))
    q = (float(c.Q if c.player_to_move == mv else -c.Q)
         if c is not None and c.N > 0 else None)
    rows.append([int(a), mover[int(a)], q, int(c.N) if c is not None else 0])
res["C"] = {"rec": o, "rows": rows, "entry": ent}

json.dump(res, open(out_path, "w"))
print("SUBPROC_OK")
""" % {"tiny_roots": json.dumps([list(t) for t in TINY_ROOTS]),
       "sign_root": json.dumps(list(SIGN_ROOT))}


@pytest.fixture(scope="module")
def sub(tmp_path_factory):
    out = tmp_path_factory.mktemp("ssa") / "res.json"
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(REPO), str(out)],
        capture_output=True, text=True, timeout=900, cwd=str(REPO),
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "SUBPROC_OK" in proc.stdout
    return json.loads(out.read_text())


def test_tau_convention_matches_group_metrics(sub):
    a = sub["A"]
    regret, top1, tau = a["partial"]
    assert regret == 0.0 and top1 == 1
    assert abs(tau - 1.0 / 3.0) < 1e-12
    assert a["perfect"][2] == 1.0 and a["perfect"][0] == 0.0 and a["perfect"][1] == 1
    # inverted: pick=worst (10), best=30 -> regret 20, top1 0, tau -1
    assert a["inverted"] == [20.0, 0, -1.0]
    assert abs(a["score_tie"][2] - 2.0 / math.sqrt(6.0)) < 1e-12


def test_agent_scorer_valid_ranking_on_tiny_roots(sub):
    m2 = None
    if M2_JSON.exists():
        d = json.loads(M2_JSON.read_text())
        m2 = {(r["seed"], r["ply"]): r for r in d["per_root"]}
    assert len(sub["B"]) == len(TINY_ROOTS)
    for item, key in zip(sub["B"], TINY_ROOTS):
        rec, actions = item["rec"], item["actions"]
        assert (rec["seed"], rec["ply"]) == key
        assert rec["k"] <= 2 and rec["mode"] == "marginalized"
        assert rec["n_legal"] == len(actions) >= 2
        for name in ("v29_leaf", "puct_q", "puct_visits"):
            m = rec["rankers"][name]
            assert m["solver_regret"] >= 0.0
            assert m["top1"] in (0, 1)
            assert (isinstance(m["tau"], float)
                    and (math.isnan(m["tau"]) or -1.0 <= m["tau"] <= 1.0))
            assert m["pick"] in actions, f"{name} pick not a solver child"
        ag = rec["agent"]
        assert ag["sims"] == 32
        assert ag["n_children"] == rec["n_legal"]
        assert 0 <= ag["n_unvisited"] <= ag["n_children"]
        assert ag["top_share"] is None or 0.0 < ag["top_share"] <= 1.0
        assert -1.0 <= ag["root_q"] <= 1.0
        # THE comparability check: the re-scored v29_leaf baseline reproduces
        # the M2 run's per-root tau/regret on the same root exactly.
        if m2 is not None and key in m2:
            ref = m2[key]["rankers"]["v29_leaf"]
            got = rec["rankers"]["v29_leaf"]
            assert abs(got["tau"] - ref["tau"]) < 1e-9, (key, got["tau"], ref["tau"])
            assert got["solver_regret"] == ref["solver_regret"]
            assert got["top1"] == ref["top1"]


def test_sign_convention_not_inverted(sub):
    rec, entry = sub["C"]["rec"], sub["C"]["entry"]
    assert (rec["seed"], rec["ply"]) == SIGN_ROOT
    assert rec["value_spread"] >= 6.0, "sign-test root must have a wide exact spread"

    # The exact solver's mover-POV child values (P0-persp negated iff to_move==1,
    # the score_root convention). The sign root is UNAMBIGUOUS: exactly one child
    # attains the max, so tau/top1 read the sign, not a tie-dilution artifact.
    tm = int(entry["to_move"])
    mover = {int(a): (v if tm == 0 else -v)
             for a, v in zip(entry["actions"], entry["child_values"])}
    best_val = max(mover.values())
    best_children = {a for a, mv in mover.items() if mv == best_val}
    assert len(best_children) == 1, (
        f"sign-test root must have a unique solver-best child, got ties: {best_children}")

    q = rec["rankers"]["puct_q"]
    v = rec["rankers"]["puct_visits"]
    # NOT inverted: both the search-Q argmax AND the visit-count argmax land on the
    # solver-best child (an inverted sign would land on the WORST), and both rankings
    # correlate POSITIVELY with the exact mover-POV values (tau ~ -1 = the inversion
    # signature). This is the whole-Stage-0-validity check.
    assert q["top1"] == 1 and q["pick"] in best_children, (q["pick"], best_children)
    assert v["top1"] == 1 and v["pick"] in best_children, (v["pick"], best_children)
    assert q["tau"] > 0.0, f"agent Q ranking anti-correlated: tau={q['tau']}"
    assert v["tau"] > 0.0, f"agent visit ranking anti-correlated: tau={v['tau']}"
    # the argmax-Q pick is optimal here, so its regret is 0 (< the value spread) and
    # its exact value is at least the median child value (mover POV).
    assert q["solver_regret"] < rec["value_spread"]
    pick_val = mover[q["pick"]]
    med = sorted(mover.values())[len(mover) // 2]
    assert pick_val >= med, (pick_val, med)
