"""Contracts for the oracle-scored disagreement PILOT (scripts/measurement_infra/oracle_score_pilot.py).

Covers only the PURE parts — the ones that decide whether the run is interpretable:
  A. position sampling is deterministic and listing-order independent
  B. CRN seed derivation is pick- and budget-independent, and process-stable
  C. the paired delta / variance decomposition arithmetic
  D. the disagreement filter reads the CL-070 record schema correctly
  E. the --oracle-policy discriminator switch: the default path is UNCHANGED, the
     out-of-family path builds no search and no curve125 leaf, and both are stamped

Scoring itself (replay + playout) is exercised by the harness's own smoke run, not here.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

OSP = pytest.importorskip("oracle_score_pilot")


# --------------------------------------------------------------------------- #
# A. sampling determinism                                                       #
# --------------------------------------------------------------------------- #
def _pop(n=50):
    return [{"root_id": f"s1_p{i}", "salt": (i % 3) + 1, "rid": f"s1_p{i}_r{(i % 3) + 1}"}
            for i in range(n)]


def test_sample_is_deterministic_for_a_seed():
    pop = _pop()
    a = OSP.sample_positions(pop, 20, 20260728)
    b = OSP.sample_positions(pop, 20, 20260728)
    assert [x["rid"] for x in a] == [x["rid"] for x in b]
    assert len(a) == 20


def test_sample_is_independent_of_input_order():
    """The population arrives from a filesystem glob; the sample must not depend on it."""
    pop = _pop()
    shuffled = list(reversed(pop))
    a = OSP.sample_positions(pop, 20, 7)
    b = OSP.sample_positions(shuffled, 20, 7)
    assert [x["rid"] for x in a] == [x["rid"] for x in b]


def test_sample_seed_actually_changes_the_draw():
    pop = _pop()
    a = {x["rid"] for x in OSP.sample_positions(pop, 20, 1)}
    b = {x["rid"] for x in OSP.sample_positions(pop, 20, 2)}
    assert a != b


def test_sample_larger_than_population_returns_everything():
    pop = _pop(5)
    got = OSP.sample_positions(pop, 20, 3)
    assert len(got) == 5


def test_sample_is_returned_in_sorted_order():
    pop = _pop()
    got = OSP.sample_positions(pop, 15, 11)
    assert got == sorted(got, key=lambda r: (r["root_id"], r["salt"]))


# --------------------------------------------------------------------------- #
# B. CRN seed derivation                                                        #
# --------------------------------------------------------------------------- #
def test_world_seeds_are_reused_across_picks_by_construction():
    """The seed function takes NO pick and NO budget argument — that is the CRN contract.
    Both picks in _process call world_seeds(rid, m, salt) once and share the result."""
    import inspect
    sig = inspect.signature(OSP.world_seed).parameters
    assert set(sig) == {"rid", "j", "salt"}
    assert OSP.world_seeds("s1_p2_r1", 8, "x") == OSP.world_seeds("s1_p2_r1", 8, "x")


def test_world_and_playout_seeds_are_distinct_streams():
    ws = OSP.world_seeds("s1_p2_r1", 16, "salt")
    ps = [OSP.playout_seed("s1_p2_r1", j, "salt") for j in range(16)]
    assert ws != ps
    assert len(set(ws)) == 16          # no collisions within a position
    assert len(set(ps)) == 16


def test_seeds_vary_with_position_and_salt():
    assert OSP.world_seeds("a", 4, "s") != OSP.world_seeds("b", 4, "s")
    assert OSP.world_seeds("a", 4, "s") != OSP.world_seeds("a", 4, "t")


def test_seeds_are_stable_across_processes():
    """PYTHONHASHSEED-independence: a fresh interpreter must derive the same seeds."""
    code = (f"import sys; sys.path.insert(0, {str(REPO / 'scripts' / 'measurement_infra')!r});"
            "import oracle_score_pilot as O;"
            "print(O.world_seeds('s28000000000_p66_r1', 4, 'oracle-pilot-v1'))")
    outs = []
    for hs in ("0", "1", "12345"):
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": hs})
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(set(outs)) == 1
    assert outs[0] == str(OSP.world_seeds("s28000000000_p66_r1", 4, "oracle-pilot-v1"))


def test_seeds_are_in_range():
    for s in OSP.world_seeds("r", 32, "salt"):
        assert 0 <= s <= 0x7FFFFFFF


# --------------------------------------------------------------------------- #
# C. delta arithmetic                                                           #
# --------------------------------------------------------------------------- #
def test_position_delta_is_the_paired_mean():
    a = [1.0, 2.0, 3.0, 4.0]
    b = [2.0, 4.0, 3.0, 9.0]
    d = OSP.position_delta(a, b)
    assert d["delta"] == pytest.approx(2.0)
    assert d["per_world_delta"] == [1.0, 2.0, 0.0, 5.0]
    assert d["mean_a"] == pytest.approx(2.5)
    assert d["mean_b"] == pytest.approx(4.5)
    assert d["m"] == 4


def test_position_delta_pairing_removes_common_world_variance():
    """Two picks whose values differ by a CONSTANT across a highly variable set of worlds:
    the paired within-variance must be ~0 while the unpaired variance is large."""
    a = [0.0, 10.0, -7.0, 25.0, -3.0]
    b = [x + 1.5 for x in a]
    d = OSP.position_delta(a, b)
    assert d["delta"] == pytest.approx(1.5)
    assert d["within_var"] == pytest.approx(0.0, abs=1e-12)
    assert d["unpaired_var"] > 100.0
    assert math.isinf(d["crn_var_reduction"]) or d["crn_var_reduction"] > 1e6


def test_position_delta_no_crn_gain_when_independent():
    a = [1.0, -1.0, 1.0, -1.0]
    b = [-1.0, 1.0, -1.0, 1.0]
    d = OSP.position_delta(a, b)
    # anti-correlated: pairing makes it WORSE, and the statistic must say so (<1)
    assert d["crn_var_reduction"] < 1.0


def test_position_delta_rejects_ragged_input():
    with pytest.raises(ValueError):
        OSP.position_delta([1.0, 2.0], [1.0])
    with pytest.raises(ValueError):
        OSP.position_delta([], [])


def test_summarize_reports_sd_and_implied_z():
    rows = [{"ok": True, "delta": d, "within_var": 4.0, "crn_var_reduction": 3.0}
            for d in (0.0, 1.0, -1.0, 2.0, -2.0, 0.5, -0.5, 1.5)]
    s = OSP.summarize(rows, m=32, assumed_effect=0.07, full_n_bank=652)
    assert s["n_positions"] == 8
    assert s["sd_delta_positions"] == pytest.approx(
        math.sqrt(sum((d - 0.1875) ** 2 for d in (0.0, 1.0, -1.0, 2.0, -2.0, 0.5, -0.5, 1.5)) / 7))
    # var decomposition: sd^2 - within/M
    assert s["var_between_positions_est"] == pytest.approx(
        s["sd_delta_positions"] ** 2 - 4.0 / 32)
    # more worlds can only shrink the projected sd
    proj = s["sd_delta_projected_by_m"]
    assert proj["64"] <= proj["32"] <= proj["16"] <= proj["8"]
    # the memo's fork must reproduce its own quoted numbers
    assert s["memo_power_fork"]["z_if_sd_0.5"] == pytest.approx(2.28, abs=0.05)
    assert s["memo_power_fork"]["z_if_sd_1.5"] == pytest.approx(0.76, abs=0.05)


def test_summarize_survives_the_disk_round_trip():
    """The live path re-reads records from disk, where json_safe has turned inf/NaN into
    null. `None == None` is True, so a naive NaN filter lets None into the arithmetic —
    this is the regression guard for exactly that."""
    rows = [{"ok": True, "delta": 1.0, "within_var": 0.0, "crn_var_reduction": float("inf"),
             "distinct_afterstates": 4},
            {"ok": True, "delta": -1.0, "within_var": 4.0, "crn_var_reduction": 2.0,
             "distinct_afterstates": 4},
            {"ok": True, "delta": 0.5, "within_var": 2.0, "crn_var_reduction": 3.0,
             "distinct_afterstates": 0}]
    on_disk = json.loads(json.dumps(OSP.json_safe(rows), allow_nan=False))
    assert on_disk[0]["crn_var_reduction"] is None       # the trap is really present
    s = OSP.summarize(on_disk, m=4, assumed_effect=0.07, full_n_bank=628)
    assert s["n_positions"] == 3
    assert s["mean_within_position_var"] == pytest.approx(2.0)
    assert s["median_crn_var_reduction"] == pytest.approx(3.0)
    assert s["n_positions_perfect_pairing"] == 1
    assert s["n_positions_identical_afterstates"] == 1
    json.dumps(OSP.json_safe(s), allow_nan=False)


def test_summarize_needs_two_positions():
    s = OSP.summarize([{"ok": True, "delta": 1.0, "within_var": 1.0,
                        "crn_var_reduction": 1.0}], m=8, assumed_effect=0.07,
                      full_n_bank=652)
    assert "error" in s


def test_summarize_ignores_failed_rows():
    rows = [{"ok": True, "delta": 1.0, "within_var": 1.0, "crn_var_reduction": 2.0},
            {"ok": True, "delta": -1.0, "within_var": 1.0, "crn_var_reduction": 2.0},
            {"ok": False, "delta": 99.0, "within_var": 1.0, "crn_var_reduction": 2.0}]
    s = OSP.summarize(rows, m=8, assumed_effect=0.07, full_n_bank=652)
    assert s["n_positions"] == 2
    assert s["mean_delta_pts"] == pytest.approx(0.0)


def test_json_safe_emits_strict_json():
    """crn_var_reduction is genuinely inf when two picks are value-identical in every
    world; the emitted artifact must still be strict JSON that jq/JS can read."""
    payload = {"a": float("inf"), "b": float("nan"), "c": [1.0, float("-inf")],
               "d": {"e": 2.5}, "f": "text", "g": 3}
    safe = OSP.json_safe(payload)
    txt = json.dumps(safe, allow_nan=False)       # raises if any inf/nan survived
    back = json.loads(txt)
    assert back == {"a": None, "b": None, "c": [1.0, None], "d": {"e": 2.5},
                    "f": "text", "g": 3}


def test_json_safe_round_trips_a_real_summary():
    rows = [{"ok": True, "delta": d, "within_var": 0.0, "crn_var_reduction": float("inf")}
            for d in (1.0, 2.0, 3.0)]
    s = OSP.summarize(rows, m=4, assumed_effect=0.07, full_n_bank=628)
    json.dumps(OSP.json_safe(s), allow_nan=False)


# --------------------------------------------------------------------------- #
# D. the CL-070 record filter                                                   #
# --------------------------------------------------------------------------- #
def _write_rec(d: Path, rid: str, pa, pb, *, ok=True, solver=False):
    (d / f"{rid}.json").write_text(json.dumps({
        "ok": ok, "rid": rid, "root_id": rid.rsplit("_r", 1)[0],
        "deck_seed": 28000000000, "ply": 66, "salt": int(rid.rsplit("_r", 1)[1]),
        "root_player": 1, "solver_region": solver,
        "q_pick_by_level": {"688": pa, "2752": pb},
    }))


def test_load_disagreements_filters(tmp_path):
    d = tmp_path / "records"
    d.mkdir()
    _write_rec(d, "s28000000000_p10_r1", 5, 9)          # disagreement -> keep
    _write_rec(d, "s28000000000_p11_r1", 7, 7)          # agreement    -> drop
    _write_rec(d, "s28000000000_p12_r1", 1, 2, ok=False)     # failed   -> drop
    _write_rec(d, "s28000000000_p13_r1", 3, 4, solver=True)  # solver   -> drop by default
    got = OSP.load_disagreements(d, 688, 2752)
    assert [g["rid"] for g in got] == ["s28000000000_p10_r1"]
    assert got[0]["pick_a"] == 5 and got[0]["pick_b"] == 9

    with_solver = OSP.load_disagreements(d, 688, 2752, include_solver_region=True)
    assert len(with_solver) == 2


def test_load_disagreements_is_sorted(tmp_path):
    d = tmp_path / "records"
    d.mkdir()
    for ply in (30, 10, 20):
        _write_rec(d, f"s28000000000_p{ply}_r1", 1, 2)
    got = OSP.load_disagreements(d, 688, 2752)
    assert [g["rid"] for g in got] == sorted(g["rid"] for g in got)


@pytest.mark.skipif(not Path(OSP.DEFAULT_RUN_DIR, "records").is_dir(),
                    reason="CL-070 bank not mounted")
def test_real_cl070_bank_has_both_picks_and_is_replayable():
    """The load-bearing precondition: the bank really does record BOTH picks per position
    and every sampled root joins back to a replayable action sequence."""
    pop = OSP.load_disagreements(Path(OSP.DEFAULT_RUN_DIR) / "records", 688, 2752)
    assert len(pop) > 200, f"expected a few hundred disagreements, got {len(pop)}"
    roots = set()
    for line in (Path(OSP.DEFAULT_RUN_DIR) / "roots.jsonl").read_text().splitlines():
        if line.strip():
            o = json.loads(line)
            roots.add(f"s{int(o['deck_seed'])}_p{int(o['ply'])}")
    for c in OSP.sample_positions(pop, 20, 20260728):
        assert c["pick_a"] != c["pick_b"]
        assert c["root_id"] in roots


# --------------------------------------------------------------------------- #
# E. --oracle-policy — the out-of-family discriminator switch                    #
#    (ORACLE_PILOT_EXT_READOUT_20260728.md §6 / DISCRIMINATOR)                  #
# --------------------------------------------------------------------------- #
def test_default_policy_is_the_untouched_clairvoyant_construction(monkeypatch):
    """THE BYTE-IDENTITY CONTRACT. Defaulted, the harness must make the SAME
    `build_clairvoyant_champion(game, cfg=_G['cfg'], simulations=..., seed=...)` call it
    made before `--oracle-policy` existed — same callee, same kwargs, nothing added."""
    seen = {}

    def _spy(game, *, cfg, simulations, seed):
        seen.update(game=game, cfg=cfg, simulations=simulations, seed=seed)
        return "CLAIR"

    monkeypatch.setitem(OSP._G, "cfg", "SENTINEL_CFG")
    monkeypatch.setattr(OSP.CF, "build_clairvoyant_champion", _spy)

    agent = OSP.build_continuation_agent("GAME", policy="clair-puct", sims=100, seed=7)
    assert agent == "CLAIR"
    assert seen == {"game": "GAME", "cfg": "SENTINEL_CFG", "simulations": 100, "seed": 7}


def test_greedy_policy_builds_no_search_and_no_curve125(monkeypatch):
    """The out-of-family arm must not touch the clairvoyant factory at all — no PUCT
    search, and no `_G['cfg']` (the frozen curve125 leaf config) anywhere in it."""
    def _boom(*a, **kw):                                   # pragma: no cover - must not run
        raise AssertionError("tier1-greedy must not build the clairvoyant champion")

    monkeypatch.setitem(OSP._G, "cfg", "SENTINEL_CFG")
    monkeypatch.setattr(OSP.CF, "build_clairvoyant_champion", _boom)

    agent = OSP.build_continuation_agent("GAME", policy="tier1-greedy", sims=100, seed=7)
    assert isinstance(agent, OSP._GreedyContinuation)
    assert agent.clear() is None                     # the playout loop calls this
    assert "SENTINEL_CFG" not in repr(vars(agent))

    from carcassonne_ai.rule_based_player import RuleBasedPlayer
    assert isinstance(agent._p, RuleBasedPlayer)


def test_greedy_policy_actually_plays_a_legal_move():
    """The shim really satisfies the playout loop's `best_action(board) -> int` contract."""
    import numpy as np

    from carcassonne_ai.game_wrapper import Game

    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    agent = OSP.build_continuation_agent(game, policy="tier1-greedy", sims=0, seed=99)
    a = agent.best_action(board)
    assert isinstance(a, int)
    assert int(game.get_valid_moves(board)[a]) == 1
    assert a in set(int(x) for x in np.flatnonzero(game.get_valid_moves(board)))


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        OSP.build_continuation_agent("GAME", policy="h6400", sims=1, seed=1)


def _fake_args(**over):
    from types import SimpleNamespace
    base = dict(run_dir="RD", records_dir="RD/records", roots="RD/roots.jsonl",
                level_a=688, level_b=2752, n=100, head=30, sample_seed=20260728,
                m=32, oracle_sims=100, oracle_policy="clair-puct", workers=16,
                wall_cap=7200, max_plies=400, include_solver_region=False,
                assumed_effect=0.07, strict_crn=True)
    base.update(over)
    return SimpleNamespace(**base)


def test_manifest_records_the_policy(monkeypatch):
    """Self-describing: the manifest must name the continuation policy and its family, so
    a clair-puct run can never be mistaken for the out-of-family discriminator."""
    monkeypatch.setattr(OSP.CF, "resolved_manifest", lambda *a, **kw: {"stub": True})
    chosen = [{"rid": "s1_p2_r1"}]

    d = OSP.build_manifest(_fake_args(), 628, chosen)
    assert d["oracle"]["policy"] == "clair-puct"
    assert "clairvoyant" in d["oracle"]["continuation_agent"].lower()
    assert d["oracle"]["oracle_sims"] == 100
    assert "IN-FAMILY" in d["oracle"]["policy_family"]

    g = OSP.build_manifest(_fake_args(oracle_policy="tier1-greedy"), 628, chosen)
    assert g["oracle"]["policy"] == "tier1-greedy"
    assert "RuleBasedPlayer" in g["oracle"]["continuation_agent"]
    assert "OUT-OF-FAMILY" in g["oracle"]["policy_family"]
    # tier1-greedy has no search, so quoting a sims budget would be a lie.
    assert g["oracle"]["oracle_sims"] is None
    assert d["sampling"]["head"] == 30


def test_head_is_a_nested_prefix_of_the_larger_draw():
    """WHY --head exists: `--n 100 --head 30` must be a strict SUBSET of the scored 100,
    which `--n 30` is not — `random.sample` switches algorithm with k, so the two draws
    are unrelated. Nesting is what makes the discriminator comparable position-by-position."""
    pop = _pop(200)
    hundred = [x["rid"] for x in OSP.sample_positions(pop, 100, 20260728)]
    head30 = hundred[:30]
    assert len(head30) == 30
    assert set(head30) <= set(hundred)
    assert head30 == hundred[:30] == sorted(head30, key=lambda r: hundred.index(r))
    # and it is order-stable: re-drawing the 100 reproduces the same first 30
    again = [x["rid"] for x in OSP.sample_positions(pop, 100, 20260728)][:30]
    assert again == head30
