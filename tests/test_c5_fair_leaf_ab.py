"""C5 Stage-3 FAIR leaf A/B harness tests (design: measurement/classical_search/
C5_LEAF_RETUNE_DESIGN.md §"Stage 3").

The fair-harness twin of tests/test_c5_leaf_ab.py. Covers the S3 gate for a
candidate-leaf override inside the DEPLOYABLE fair config
(scripts/classical_search/eval_fair_puct.py --cand-leaf-json):

  (a) BIT-EXACT MIRROR (the S3 gate): --cand-leaf-json = the champion leaf verbatim
      reproduces the no-flag FAIR agent move-for-move on 2+ seeds (identical per-game
      records + summary) — the default path is byte-identical and the override plumbing
      is provably transparent when it equals the default.
  (b) OVERRIDE REACHES THE FAIR SEARCH: a different config (curve ×1.25 / cap5) changes
      at least one leaf value AND the fair champion's prior-evaluator value on some
      board, and changes >=1 played-game record vs the no-flag cell.
  (c) THE RUNG IS PROVABLY UNTOUCHED under an active candidate override: the manifest's
      per-side rung_leaf_hash equals the production DEFAULT_CONFIG hash (and != the
      candidate hash), AND — driving the worker code path in-process — the h800 rung is
      constructed with env DEFAULT_CONFIG while the fair champion takes the override.

Tiny knobs (k_dets=2, sims=16, exact-k=0) so every cell runs in seconds; the exact
endgame is leaf-independent (exact scoring) so exact-k=0 fully exercises the leaf A/B.
The fair harness sets the production v2.9 Bmild_cap8 leaf env via setdefault at import,
so importing eval_fair_puct FIRST keeps DEFAULT_CONFIG the cap8 production leaf here.
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"

_spec = importlib.util.spec_from_file_location("eval_fair_puct", SCRIPT)
efp = importlib.util.module_from_spec(_spec)
sys.modules["eval_fair_puct"] = efp  # fork-Pool workers unpickle _play_one by module name
_spec.loader.exec_module(efp)

sys.path.insert(0, str(REPO / "src"))
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)

DEF = efp.DEFAULT_CONFIG
# curve ×1.25 — the S3 candidate cell (curve125). (-8,-4,-1,0,2,3,4,5) * 1.25.
CURVE125 = '{"v29_meeple_curve": [-10, -5, -1.25, 0, 2.5, 3.75, 5, 6.25]}'
CAP5 = '{"bonus_cap": 5, "opp_bonus_cap": 5}'
BAND = 15_100_000_000   # clean-eval band (>1e9), tmp-isolated, distinct from the 15e9 D0 cells

# tiny-but-representative fair knobs shared by every harness cell (rung-sims=16
# too — the h800 default costs minutes/game; the rung's leaf INDEPENDENCE is what's
# under test here, not its strength)
_KNOBS = [
    "--info", "fair", "--exact-k", "0", "--k-dets", "2", "--sims", "16",
    "--rung-sims", "16",
    "--c-puct", "1.5", "--tau-p", "5", "--leaf-quantize", "float",
    "--final-select", "visits", "--value-norm", "15",
    "--n", "4", "--paired", "--workers", "2", "--seed-start", str(BAND),
]


# --------------------------------------------------------------------------- #
# candidate-leaf override reaches the FAIR agent's leaf / prior evaluator      #
# --------------------------------------------------------------------------- #
def _played_boards(seed: int, n_moves: int):
    """Play a fixed pseudo-random game from the init board, yielding Boards."""
    rng = random.Random(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    boards = [board]
    for _ in range(n_moves):
        if game.get_game_ended(board, 0) != 0.0:
            break
        legal = [a for a, ok in enumerate(game.get_valid_moves(board)) if ok]
        board, _ = game.get_next_state(board, rng.choice(legal))
        boards.append(board)
    return boards


def test_override_changes_cython_leaf_value():
    # the fair champion's leaf is flat_virtual_score_v2_float (via make_heuristic_prior
    # _evaluator). curve125 and cap5 must move the Cython float leaf on >=1 board.
    base = efp._load_cand_leaf_cfg(None) or DEF
    for spec in (CURVE125, CAP5):
        cand = efp._load_cand_leaf_cfg(spec)
        assert cand != DEF
        diffs = 0
        # seed 9990004321 = the game test_c5_leaf_ab.py proved reaches a cap5 clip
        for b in _played_boards(seed=9990004321, n_moves=120):
            st = b.state
            if st.players != 2:
                continue
            for player in (0, 1):
                v0 = flat_leaf.flat_virtual_score_v2_float(st, player, base, False)
                v1 = flat_leaf.flat_virtual_score_v2_float(st, player, cand, False)
                if v0 != v1:
                    diffs += 1
        assert diffs > 0, f"{spec} override never reached the leaf hot path"


def test_override_reaches_fair_prior_evaluator():
    # the fair agent's search uses make_heuristic_prior_evaluator(game, cfg) verbatim
    # (fair_agent.FairHeuristicPriorAgent builds exactly this and reuses it across all
    # k_dets determinizations) -> the override must move its value on some board.
    game = Game(enable_legal_moves_cache=True)
    ev0 = make_heuristic_prior_evaluator(game, HeuristicPriorConfig(leaf_cfg=DEF))
    ev1 = make_heuristic_prior_evaluator(
        game, HeuristicPriorConfig(leaf_cfg=efp._load_cand_leaf_cfg(CURVE125)))
    changed = False
    for b in _played_boards(seed=9990004321, n_moves=120):
        if game.get_game_ended(b, 0) != 0.0:
            break
        if ev0(b)[1] != ev1(b)[1]:
            changed = True
            break
    assert changed, "curve125 override did not change the fair prior-evaluator value on any board"


# --------------------------------------------------------------------------- #
# harness cell driver (mirrors test_c5_leaf_ab._run_cell)                      #
# --------------------------------------------------------------------------- #
def _run_cell(tmp: Path, sub: str, extra: list[str]):
    # The fork-Pool pickles _play_one by module name; ensure sys.modules
    # ["eval_fair_puct"] resolves to THIS module's copy during the Pool run, then
    # restore so sibling harness tests keep their own binding.
    prev = sys.modules.get("eval_fair_puct")
    sys.modules["eval_fair_puct"] = efp
    try:
        rc = efp.main(_KNOBS + ["--out-root", str(tmp), "--out-subdir", sub,
                                "--no-results-csv"] + extra)
    finally:
        if prev is not None:
            sys.modules["eval_fair_puct"] = prev
    assert rc == 0
    out = tmp / sub
    recs = {p.name: json.load(open(p)) for p in out.glob("seed*.json")}
    summ = json.load(open(out / "summary.json"))
    man = json.load(open(out / "manifest.json"))["config"]
    return recs, summ, man


# --------------------------------------------------------------------------- #
# (a) BIT-EXACT MIRROR GATE                                                    #
# --------------------------------------------------------------------------- #
_DET_FIELDS = ("diff", "score_p0", "score_p1", "moves", "deck_hash",
               "champ_prefix_moves", "champ_exact_moves", "won_by_champ", "drew",
               "rung_moves", "latch_k")


def test_mirror_champion_verbatim_bit_exact(tmp_path):
    # champion leaf VERBATIM, spelled out through the override path (exercising the
    # closure_p / curve coercions), must resolve to DEFAULT_CONFIG -> identical play.
    mirror = json.dumps({
        "bonus_cap": DEF.bonus_cap, "opp_bonus_cap": DEF.opp_bonus_cap,
        "closure_p": {str(k): v for k, v in DEF.closure_p.items()},
        "v29_meeple_curve": (list(DEF.v29_meeple_curve)
                             if DEF.v29_meeple_curve is not None else None),
        "meeple_k": DEF.meeple_k,
    })
    base_recs, base_summ, base_man = _run_cell(tmp_path, "noflag", [])
    over_recs, over_summ, over_man = _run_cell(tmp_path, "mirror", ["--cand-leaf-json", mirror])

    assert base_recs and set(base_recs) == set(over_recs)        # same seeds/seats present
    assert len({r["seed"] for r in base_recs.values()}) >= 2     # (a): 2+ distinct seeds
    for name in base_recs:
        b, o = base_recs[name], over_recs[name]
        for k in _DET_FIELDS:
            assert b[k] == o[k], f"{name}: {k} differs (no-flag {b[k]} vs mirror {o[k]})"
    # identical games -> identical aggregate verdict
    for k in ("W", "L", "D", "paired_mean_margin", "avg_diff"):
        assert base_summ[k] == over_summ[k], f"summary {k} differs"

    # manifest provenance: per-side leaf hashes present; mirror == rung (== no-flag)
    assert base_man["cand_leaf_hash"] == base_man["rung_leaf_hash"]
    assert over_man["cand_leaf_hash"] == over_man["rung_leaf_hash"]
    assert over_man["cand_leaf_hash"] == base_man["cand_leaf_hash"]
    assert base_man["cand_leaf_json"] is None and over_man["cand_leaf_json"] == mirror
    # the rung side is the production DEFAULT_CONFIG hash in BOTH cells
    assert base_man["rung_leaf_hash"] == efp._leaf_hash(DEF)
    assert over_man["rung_leaf_hash"] == efp._leaf_hash(DEF)


# --------------------------------------------------------------------------- #
# (b) a real candidate cell changes the fair champion's PLAY vs the no-flag cell
# --------------------------------------------------------------------------- #
def test_candidate_cell_changes_play_and_manifest(tmp_path):
    base_recs, _, base_man = _run_cell(tmp_path, "noflag_b", [])
    over_recs, _, over_man = _run_cell(tmp_path, "curve125", ["--cand-leaf-json", CURVE125])

    assert set(base_recs) == set(over_recs)
    # the candidate leaf differs from the (untouched) rung -> hashes must differ
    assert over_man["cand_leaf_hash"] != over_man["rung_leaf_hash"]
    assert over_man["cand_leaf_json"] == CURVE125
    assert over_man["cand_leaf_cfg"]["v29_meeple_curve"] == [-10, -5, -1.25, 0, 2.5, 3.75, 5, 6.25]
    # the champion manifest block reflects the override (mislabel-trap mitigation)
    assert over_man["champion"]["leaf"] != base_man["champion"]["leaf"]
    assert "candidate override" in over_man["champion"]["leaf"]
    # >=1 played game differs (curve125 reshapes every placement prior in the fair search)
    changed = any(base_recs[n][k] != over_recs[n][k]
                  for n in base_recs for k in ("diff", "score_p0", "score_p1", "moves"))
    assert changed, "curve125 candidate leaf did not change any fair-agent game vs no-flag"


# --------------------------------------------------------------------------- #
# (c) the RUNG is provably untouched under an active candidate override        #
# --------------------------------------------------------------------------- #
def test_manifest_rung_untouched_under_override(tmp_path):
    _, _, man = _run_cell(tmp_path, "cap5_c", ["--cand-leaf-json", CAP5])
    # rung = the fixed h800 ruler: ALWAYS env DEFAULT_CONFIG, never the candidate.
    assert man["rung_leaf_hash"] == efp._leaf_hash(DEF)
    assert man["rung"]["leaf_hash"] == efp._leaf_hash(DEF)
    assert man["rung_leaf_cfg"]["bonus_cap"] == DEF.bonus_cap == 8.0
    # the candidate side moved and is distinct
    assert man["cand_leaf_hash"] != man["rung_leaf_hash"]
    assert man["cand_leaf_cfg"]["bonus_cap"] == 5.0
    assert man["cand_leaf_cfg"]["opp_bonus_cap"] == 5.0


def test_worker_path_rung_gets_default_champion_gets_override(tmp_path, monkeypatch):
    # Drive the worker code path (_worker_init + _play_one) IN-PROCESS so we can spy on
    # the actual leaf_cfg objects handed to each side during a real game. (A fork-Pool
    # spy wouldn't work: the child's appends land in a copied list.) exact-k=0 -> no
    # solver, so this is a fast pure-fair-PIMC game.
    cand = efp._load_cand_leaf_cfg(CAP5)
    champ_cfg_dict = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
                      "final_select": "visits", "value_norm": 15.0}
    efp._worker_init("fair", champ_cfg_dict, sims=16, k_dets=2, exact_k=0, rung_sims=16,
                     shared_claim=False, claim_host="test", claim_stale=7200,
                     cand_leaf_cfg=cand)

    seen_rung, seen_champ = [], []
    _orig_rung = efp._RungPrefix.__init__

    def _spy_rung(self, game, sims, seed, leaf_cfg):
        seen_rung.append(leaf_cfg)
        _orig_rung(self, game, sims, seed, leaf_cfg)

    _orig_champ = efp._make_champion

    def _spy_champ(info, cfg, *a, **k):
        seen_champ.append(cfg.resolved_leaf_cfg())
        return _orig_champ(info, cfg, *a, **k)

    monkeypatch.setattr(efp._RungPrefix, "__init__", _spy_rung)
    monkeypatch.setattr(efp, "_make_champion", _spy_champ)

    r = efp._play_one((str(tmp_path / "wp"), BAND, 0))
    assert r is not None
    # the h800 rung was built with env DEFAULT_CONFIG (the SAME object), NOT the override
    assert seen_rung, "rung never constructed"
    assert all(lc is efp.DEFAULT_CONFIG for lc in seen_rung)
    # the fair champion took the cap5 override
    assert seen_champ and seen_champ[0].bonus_cap == 5.0
    assert seen_champ[0] is not efp.DEFAULT_CONFIG
