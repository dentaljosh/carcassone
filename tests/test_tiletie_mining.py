"""TILE-TIE ORACLE-SEPARATION MINING + GATE-2 — instrument contracts.

Covers the PURE arithmetic of `scripts/tiletie/mine_oracle_sep.py` (the DESIGN
§7.2 mined-not-guessed route) and, once it exists, `term_gate2.py`:

  1. The holdout split is deterministic, disjoint, complete, and ~30% of
     roots; the committed HOLDOUT_ROOTS.json reproduces from (seed, roots)
     alone — the corpus-reuse firewall is auditable arithmetic, not state.
  2. Ownership classification is the strict-weighted-majority idiom.
  3. `feature_capture` (the single-feature pick rule) implements
     argmax(sign*f) with exact ties broken by LOWEST action index — a
     constant feature reproduces the incumbent and captures exactly 0.
  4. View A conditions on oracle-vs-incumbent disagreement and diffs
     best-minus-incumbent (the selection-biased-by-construction view).
  5. `_joins` counts distinct root components merged by a placement.

Engine-backed extraction is NOT tested here (it is checksum-asserted at
runtime against the corpus, the term_gate precedent); these tests need no
engine, no share mount, no corpus.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "scripts" / "tiletie"),
           str(REPO / "scripts" / "measurement_infra")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mine_oracle_sep as M  # noqa: E402
import term_gate2 as G2  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. the split                                                                 #
# --------------------------------------------------------------------------- #
def test_split_deterministic_disjoint_complete():
    roots = [f"r{i:03d}" for i in range(399)]
    dev1, hold1 = M.make_split(roots)
    dev2, hold2 = M.make_split(list(reversed(roots)))   # input order irrelevant
    assert dev1 == dev2 and hold1 == hold2
    assert set(dev1) | set(hold1) == set(roots)
    assert not set(dev1) & set(hold1)
    assert len(hold1) == round(0.30 * 399) == 120
    assert dev1 == sorted(dev1) and hold1 == sorted(hold1)


def test_split_duplicate_roots_collapse():
    dev, hold = M.make_split(["a", "b", "a", "c", "b"])
    assert sorted(dev + hold) == ["a", "b", "c"]


def test_committed_holdout_reproduces():
    """The committed HOLDOUT_ROOTS.json must be exactly make_split(corpus
    roots) — the firewall is re-derivable, not trust-me state."""
    if not M.HOLDOUT_PATH.exists():
        import pytest
        pytest.skip("HOLDOUT_ROOTS.json not yet generated")
    d = json.loads(M.HOLDOUT_PATH.read_text())
    per = json.loads("{}")
    per_path = (REPO / "measurement" / "tiletie_pricing_20260812"
                / "readout_POOLED" / "per_position.jsonl")
    roots = [json.loads(line)["root_id"]
             for line in per_path.read_text().splitlines() if line.strip()]
    dev, hold = M.make_split(roots, seed=d["seed"], frac=d["frac"])
    assert d["holdout_roots"] == hold
    assert d["n_dev_roots"] == len(dev)


# --------------------------------------------------------------------------- #
# 2. ownership                                                                 #
# --------------------------------------------------------------------------- #
def test_classify_owner_strict_majority():
    counts = {1: [2, 1], 2: [0, 3], 3: [1, 1], 4: [0, 0]}
    assert M.classify_owner(counts, 1, 0) == "own"
    assert M.classify_owner(counts, 1, 1) == "opp"
    assert M.classify_owner(counts, 2, 0) == "opp"
    assert M.classify_owner(counts, 3, 0) == "cont"      # tie => contested
    assert M.classify_owner(counts, 4, 0) == "un"        # zero weight
    assert M.classify_owner(counts, 99, 0) == "un"       # absent component


# --------------------------------------------------------------------------- #
# 3/4. capture + view A on a toy table                                         #
# --------------------------------------------------------------------------- #
def _toy_table():
    """Two positions, one root each. Feature g separates the oracle-best arm;
    feature h is constant (must capture exactly 0)."""
    def entry(rid, root, acts, means, g_vals, phase="mid", scale=0.75):
        fx = {a: {"g": gv, "h": 1.0} for a, gv in zip(acts, g_vals)}
        return {"rid": rid, "root_id": root, "stratum": "selfplay",
                "phase": phase, "scale_all": scale, "acts": acts,
                "means": means, "pool": list(range(len(acts))),
                "champ_ix": None, "fx": fx}
    return [
        # oracle best = arm 2 (mean 3.0), g largest there
        entry("p1", "rootA", [10, 11, 12], [1.0, 2.0, 3.0], [0.0, 1.0, 5.0]),
        # oracle best = arm 0 (incumbent agrees); g would move to arm 1
        entry("p2", "rootB", [20, 21], [4.0, 1.0], [0.0, 2.0]),
    ]


def test_feature_capture_argmax_and_sign(monkeypatch):
    monkeypatch.setattr(M, "FEATURE_NAMES", ("g", "h"))
    t = _toy_table()
    plus = M.feature_capture(t, "g", +1)
    # p1: picks arm 2 -> (3-1)*0.75 = 1.5 ; p2: picks arm 1 -> (1-4)*0.75 = -2.25
    assert abs(plus["mean"] - (1.5 - 2.25) / 2) < 1e-12
    assert plus["moved_frac"] == 1.0
    minus = M.feature_capture(t, "g", -1)
    # argmin g = arm 0 in both -> capture 0, nothing moved
    assert minus["mean"] == 0.0 and minus["moved_frac"] == 0.0


def test_constant_feature_captures_zero(monkeypatch):
    monkeypatch.setattr(M, "FEATURE_NAMES", ("g", "h"))
    t = _toy_table()
    for sign in (+1, -1):
        d = M.feature_capture(t, "h", sign)
        assert d["mean"] == 0.0 and d["moved_frac"] == 0.0


def test_feature_capture_none_treated_as_zero():
    t = _toy_table()
    # remove g from the incumbent arm of p1 -> None -> treated as 0.0
    del t[0]["fx"][10]["g"]
    d = M.feature_capture(t, "g", +1)
    assert abs(d["mean"] - (1.5 - 2.25) / 2) < 1e-12


def test_view_a_disagreement_only(monkeypatch):
    monkeypatch.setattr(M, "FEATURE_NAMES", ("g", "h"))
    a = M.view_a(_toy_table())
    assert a["n_disagree"] == 1 and a["n_total"] == 2
    # prize = (3-1)*0.75 on the single disagreeing position
    assert abs(a["mean_prize_all_scale"] - 1.5) < 1e-12
    # delta g = 5.0 - 0.0 on that position
    g = a["features"]["g"]
    assert g["n"] == 1 and abs(g["mean"] - 5.0) < 1e-12
    # constant feature: delta 0, nothing nonzero
    h = a["features"]["h"]
    assert h["mean"] == 0.0 and h["frac_nonzero"] == 0.0


def test_view_c_within_set_correlation(monkeypatch):
    monkeypatch.setattr(M, "FEATURE_NAMES", ("g", "h"))
    c = M.view_c(_toy_table())
    # g increases with the oracle mean within p1 and decreases within p2;
    # pooled r must be finite and the constant h must give r == 0
    assert -1.0 <= c["g"]["r_within"] <= 1.0
    assert c["h"]["r_within"] == 0.0 and c["h"]["slope"] == 0.0


# --------------------------------------------------------------------------- #
# 5. _joins                                                                    #
# --------------------------------------------------------------------------- #
def test_joins_counts_distinct_root_components():
    placed = (5, 5)
    # after: one component A spanning the placed cell + two old cells that
    # belonged to DIFFERENT root components; plus a fresh component B on the
    # placed cell only (a new comp: joins nothing).
    side_root_after = {(5, 5, "top"): "A", (4, 5, "bot"): "A",
                       (5, 6, "left"): "A", (5, 5, "right"): "B"}
    root_positions_after = {
        "A": frozenset({(5, 5, "top"), (4, 5, "bot"), (5, 6, "left")}),
        "B": frozenset({(5, 5, "right")}),
    }
    side_root_root = {(4, 5, "bot"): "r1", (5, 6, "left"): "r2"}
    out = dict(M._joins(side_root_after, root_positions_after,
                        side_root_root, placed))
    assert out["A"] == {"r1", "r2"}
    assert out["B"] == set()


# --------------------------------------------------------------------------- #
# 6. gate 2 — branch matrix + FINAL-slice firewall + cross-fit                 #
# --------------------------------------------------------------------------- #
def test_adjudicate_branch_matrix():
    assert G2.adjudicate(-2.5, None) == "G2-HARMFUL"
    assert G2.adjudicate(-2.0, None) == "G2-HARMFUL"
    assert G2.adjudicate(0.0, None) == "G2-SCREEN-FAIL"
    assert G2.adjudicate(1.99, None) == "G2-SCREEN-FAIL"
    assert G2.adjudicate(2.0, -0.5) == "G2-FAIL-FINAL"
    assert G2.adjudicate(2.0, 0.0) == "G2-FAIL-FINAL"
    assert G2.adjudicate(2.0, 1.2) == "G2-WEAK"
    assert G2.adjudicate(2.5, 2.4) == "G2-PASS"


def test_adjudicate_refuses_missing_final_on_screen_pass():
    import pytest
    with pytest.raises(AssertionError):
        G2.adjudicate(2.5, None)


def _gate_toy(n_roots=40, effect=0.0, seed=7):
    """Toy dev table: `g` picks arm 1 whose capture is N(effect, 1)."""
    import random
    rng = random.Random(seed)
    table = []
    for i in range(n_roots):
        cap = effect + rng.gauss(0, 1)
        table.append({
            "rid": f"p{i}", "root_id": f"root{i}", "stratum": "selfplay",
            "phase": "mid", "scale_all": 1.0, "acts": [100, 101],
            "means": [0.0, cap], "pool": [0, 1], "champ_ix": None,
            "fx": {100: {"g": 0.0}, 101: {"g": 1.0}},
        })
    return table


def test_run_gate_screen_fail_never_touches_final():
    menu = (("g+", ("g", 1.0)),)
    table = _gate_toy(effect=0.0)

    def loader():
        raise AssertionError("FINAL slice was opened on a screen fail")

    r = G2.run_gate(table, loader, menu=menu, candidate="g+")
    assert r["branch"] in ("G2-SCREEN-FAIL", "G2-HARMFUL")
    assert r["final"] is None


def test_run_gate_pass_path_evaluates_final_once():
    menu = (("g+", ("g", 1.0)),)
    dev = _gate_toy(effect=3.0)          # huge effect -> screen passes
    fin = _gate_toy(effect=3.0, seed=11)
    calls = []

    def loader():
        calls.append(1)
        return fin

    r = G2.run_gate(dev, loader, menu=menu, candidate="g+")
    assert calls == [1]
    assert r["screen"]["z"] >= 2.0
    assert r["final"]["candidate"] == "g+"
    assert r["branch"] == "G2-PASS"
    # capture arithmetic: mean over positions of means[pick]-means[0]
    exp = sum(e["means"][1] for e in fin) / len(fin)
    assert abs(r["final"]["mean"] - exp) < 1e-12


def test_crossfit_selection_prefers_frozen_order_on_tie():
    # two identical candidates -> the first in menu order must be selected
    menu = (("a+", ("g", 1.0)), ("b+", ("g", 1.0)))
    table = _gate_toy(effect=3.0)
    s = G2.crossfit_screen(table, menu=menu)
    assert set(s["fold_selected"]) == {"a+"}


def test_crossfit_constant_feature_captures_zero():
    menu = (("h+", ("h", 1.0)),)
    table = _gate_toy(effect=3.0)
    for e in table:
        for f in e["fx"].values():
            f["h"] = 5.0
    s = G2.crossfit_screen(table, menu=menu)
    assert s["mean"] == 0.0 and s["heldout_moved_frac"] == 0.0
