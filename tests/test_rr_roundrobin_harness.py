"""Phase 1.1b round-robin harness extension (--candidate / --opponent) tests.

Covers (pre-registration: measurement/classical_search/ROUND_ROBIN_PLAN.md):
  * LEGACY REGRESSION: work-list construction and the legacy cell naming are
    byte-identical when the new flags are not used;
  * rr_* cell naming matches the plan's convention (rr_puct2750_vs_net-iter02_k2,
    rr_h6400_vs_h12800_k2) when the new flags ARE used;
  * end-to-end: --candidate h<sims> --opponent h<sims> tiny cell runs through the
    real Pool/claim/summary machinery and produces a valid summary.json + a manifest
    with the resolved opponent spec and null puct knobs;
  * net opponent: iter_02.pt loads on CPU, _NetPrefix produces a LEGAL move on a
    fresh board, and the pinned play knobs equal the rod_v2 anchor harness constants
    (scripts/level2/eval_hybrid_handoff.py ITER8_*).

The harness module sets the production v2.9 Bmild_cap8 leaf env via setdefault at
import (matching the production cells), so importing it first keeps DEFAULT_CONFIG
consistent for every test here.
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classical_search" / "eval_puct_priors.py"

_spec = importlib.util.spec_from_file_location("eval_puct_priors", SCRIPT)
epp = importlib.util.module_from_spec(_spec)
sys.modules["eval_puct_priors"] = epp  # fork-Pool workers unpickle _play_one by module name
_spec.loader.exec_module(epp)

ITER02 = Path("/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt")


class _Args:
    """Minimal argparse.Namespace stand-in for spec/tag unit tests."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _mkargs(**over):
    base = dict(candidate="puct", opponent=None, c_puct=1.5, tau_p=5.0,
                leaf_quantize="float", final_select="Q", cand_sims=800,
                champ_sims=6400, exact_k=4)
    base.update(over)
    return _Args(**base)


# --------------------------------------------------------------------------- #
# Legacy regression guards (no new flags -> identical work-list + naming)      #
# --------------------------------------------------------------------------- #
def test_legacy_worklist_unchanged():
    # paired: each deck seed appears twice, seats 0 then 1, seeds consecutive
    assert epp._build_work(9_000_000_000, 4, True) == [
        (9_000_000_000, 0), (9_000_000_000, 1),
        (9_000_000_001, 0), (9_000_000_001, 1)]
    # unpaired: one game per seed, alternating seats
    assert epp._build_work(9_000_000_000, 3, False) == [
        (9_000_000_000, 0), (9_000_000_001, 1), (9_000_000_002, 0)]


def test_legacy_result_path_naming_unchanged():
    out = Path("/x")
    assert epp._result_path(out, 9_400_000_123, 1).name == "seed009400000123_a1.json"


def test_legacy_tag_unchanged():
    a = _mkargs()
    specs = epp._resolve_specs(a)
    assert specs == ("puct", "heur", 6400, None, False)   # new_mode False
    assert epp._cell_tag(a, *specs) == "puct_c1.5_tau5_float_Q_s800_vs_h6400_k4"
    # the confirmed-cell shape (c1.5/tau5/visits/float/2750 vs h6400 k2)
    b = _mkargs(final_select="visits", cand_sims=2750, exact_k=2)
    assert (epp._cell_tag(b, *epp._resolve_specs(b))
            == "puct_c1.5_tau5_float_visits_s2750_vs_h6400_k2")


# --------------------------------------------------------------------------- #
# Round-robin spec parsing + rr_* naming                                       #
# --------------------------------------------------------------------------- #
def test_rr_tag_puct_vs_net():
    a = _mkargs(cand_sims=2750, opponent=f"net:{ITER02}", exact_k=2)
    specs = epp._resolve_specs(a)
    cand_kind, opp_kind, opp_sims, net_ckpt, new_mode = specs
    assert (cand_kind, opp_kind, opp_sims, new_mode) == ("puct", "net", epp.NET_SIMS, True)
    assert net_ckpt == str(ITER02)
    assert epp._cell_tag(a, *specs) == "rr_puct2750_vs_net-iter02_k2"


def test_rr_tag_h_vs_h():
    b = _mkargs(candidate="h6400", opponent="h12800", exact_k=2, cand_sims=None)
    specs = epp._resolve_specs(b)
    assert b.cand_sims == 6400          # the h<sims> token defines the candidate sims
    assert specs == ("heur", "heur", 12800, None, True)
    assert epp._cell_tag(b, *specs) == "rr_h6400_vs_h12800_k2"


def test_explicit_h_opponent_is_new_mode_even_at_champ_sims():
    # --opponent h6400 (explicit) -> rr naming, even though it equals --champ-sims
    a = _mkargs(opponent="h6400", exact_k=2)
    specs = epp._resolve_specs(a)
    assert specs[-1] is True
    assert epp._cell_tag(a, *specs) == "rr_puct800_vs_h6400_k2"


def test_bad_specs_rejected():
    with pytest.raises(ValueError):
        epp._parse_candidate("puct800")
    with pytest.raises(ValueError):
        epp._parse_candidate("h")
    with pytest.raises(ValueError):
        epp._parse_opponent("net:")
    with pytest.raises(ValueError):
        epp._parse_opponent("iter02")
    with pytest.raises(ValueError):
        epp._resolve_specs(_mkargs(cand_sims=None))   # puct candidate needs --cand-sims


# --------------------------------------------------------------------------- #
# End-to-end: h-vs-h tiny cell through the real machinery                      #
# --------------------------------------------------------------------------- #
def test_h_vs_h_end_to_end(tmp_path):
    rc = epp.main([
        "--candidate", "h48", "--opponent", "h48", "--exact-k", "2",
        "--n", "4", "--paired", "--workers", "4",
        "--seed-start", "9990000000",
        "--out-root", str(tmp_path), "--no-results-csv"])
    assert rc == 0
    out = tmp_path / "rr_h48_vs_h48_k2"
    assert sorted(p.name for p in out.glob("seed*.json")) == [
        "seed009990000000_a0.json", "seed009990000000_a1.json",
        "seed009990000001_a0.json", "seed009990000001_a1.json"]
    summ = json.load(open(out / "summary.json"))
    assert summ["n"] == 4 and summ["W"] + summ["D"] + summ["L"] == 4
    assert summ["n_paired"] == 2                  # 2 decks, both seats each
    assert summ["cand_latched_games"] == 4        # exact-K=2 tail fired every game
    man = json.load(open(out / "manifest.json"))
    cfg = man["config"]
    assert cfg["rr_cell"] == "rr_h48_vs_h48_k2"
    assert cfg["cand_sims"] == 48 and cfg["champ_sims"] == 48
    assert cfg["candidate"]["agent"] == "HeuristicMCTS"
    # puct-specific knobs ignored for an h<sims> candidate -> null in the manifest
    for k in ("c_puct", "tau_p", "leaf_quantize", "final_select", "value_norm"):
        assert cfg["candidate"][k] is None
    assert cfg["opponent"] == {"kind": "heur", "agent": "HeuristicMCTS",
                               "heur_leaf": "v2_7", "c": epp.CHAMP_C, "sims": 48,
                               "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)", "exact_k": 2}
    # deck-paired margin machinery produced a real paired read
    assert summ["paired_mean_margin"] is not None
    assert "champion" not in cfg                   # replaced by the opponent block
    assert man["code_rev"] and cfg["code_rev"]     # git rev recorded
    # mirror match on a shared deck: both per-game records saw the same deck hash
    recs = [json.load(open(out / f"seed009990000000_a{s}.json")) for s in (0, 1)]
    assert recs[0]["deck_hash"] == recs[1]["deck_hash"] != ""


# --------------------------------------------------------------------------- #
# Net opponent construction (net-on-CPU, one position — no full game)          #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not ITER02.is_file(), reason="rod_v2 iter_02.pt not present")
def test_net_opponent_loads_and_moves_legally():
    net, dev, ns = epp._load_net_cpu(str(ITER02))
    assert ns == 12                                # rod_v2 nets carry farm scalars
    from carcassonne_ai.evaluators import make_single_evaluator
    gf = epp.Game(enable_legal_moves_cache=True, include_farm_scalars=ns > 10)
    prefix = epp._NetPrefix(make_single_evaluator(net, dev, gf), gf, seed=123)
    random.seed(9_990_000_123)
    referee = epp.Game(enable_legal_moves_cache=True)
    board = referee.get_init_board()
    mask = referee.get_valid_moves(board)
    act = prefix.move(board)
    assert mask[act], f"net opponent produced an illegal action {act}"


def test_net_play_knobs_pinned_to_rod_v2_anchor():
    # the pinned constants must equal the rod_v2 anchor harness's (drift guard)
    import eval_hybrid_handoff as hh   # scripts/level2 is on sys.path via the harness
    assert epp.NET_SIMS == hh.ITER8_SIMS == 200
    assert epp.NET_CPUCT == hh.ITER8_CPUCT == 3.0
    assert epp.NET_RESIDUAL_SCALE == hh.ITER8_RESIDUAL_SCALE == 0.25
