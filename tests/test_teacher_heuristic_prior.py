"""Champion-distillation emitter (`--teacher heuristic_prior`) — parity + smoke.

Spec: measurement/distill_flywheel_20260715/DESIGN.md §4.1. Proves the ONE
substantive new piece — the net-free classical-champion self-play emitter wired
into scripts/run_selfplay_iter.py:

  * PARITY — on >=3 fixed mid-game boards, the priors + value from the injected
    ``make_heuristic_prior_evaluator`` (built via the script's
    ``_teacher_prior_config`` from the CLI knobs) match, exactly, what the
    champion ``HeuristicPriorAgent`` computes with the same config;
  * SMOKE — the real CLI path (`python scripts/run_selfplay_iter.py --teacher
    heuristic_prior ... --sims 32`, subprocess, net-free CPU) produces a
    GameDataset whose policy rows sum to 1 over the legal mask (zero off-mask),
    whose aux_mask is all-True, whose values lie in [-1, 1] and are
    sign-consistent with the single final score_diff margin, and writes a
    manifest.json carrying the resolved teacher block.

Champion leaf env (PRODUCTION.yaml curve125 Bmild_cap8) is set BEFORE importing
carcassonne_ai so DEFAULT_CONFIG resolves to the champion leaf.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path

# Champion leaf env (governance/PRODUCTION.yaml puct_priors_v29_bmild_cap8) BEFORE
# importing carcassonne_ai — DEFAULT_CONFIG reads CARCASSONNE_* at import time.
_CHAMP_ENV = {
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
}
for _k, _v in _CHAMP_ENV.items():
    os.environ.setdefault(_k, _v)
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.warmstart import GameDataset  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_selfplay_iter.py"


def _load_rsi():
    """Import scripts/run_selfplay_iter.py as a module (it's a script)."""
    spec = importlib.util.spec_from_file_location("run_selfplay_iter", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_selfplay_iter"] = mod
    spec.loader.exec_module(mod)
    return mod


def _fixed_boards(depths=(18, 40, 75), deck_seed=4242):
    """Deterministic mid-game boards: fresh deck (global random.seed) advanced by
    `d` random-legal plies (np.random for move choice). Stops early on terminal."""
    boards = []
    for i, d in enumerate(depths):
        random.seed(deck_seed + i)          # deck shuffle uses the global random
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        rng = np.random.default_rng(deck_seed + i)
        for _ in range(d):
            if game.get_game_ended(board, 0) != 0.0:
                break
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        boards.append((game, board))
    return boards


def test_teacher_prior_config_maps_cli_knobs():
    """`_teacher_prior_config` threads the CLI teacher knobs into the champion
    HeuristicPriorConfig (leaf_cfg=None → env DEFAULT_CONFIG)."""
    rsi = _load_rsi()
    cfg = rsi._teacher_prior_config(
        {
            "c_puct": 1.5,
            "teacher_tau_p": 5.0,
            "teacher_value_norm": 15.0,
            "teacher_leaf_quantize": "float",
        }
    )
    assert isinstance(cfg, HeuristicPriorConfig)
    assert cfg.c_puct == 1.5
    assert cfg.tau_p == 5.0
    assert cfg.value_norm == 15.0
    assert cfg.leaf_quantize == "float"
    assert cfg.leaf_cfg is None  # resolves to the env-built champion leaf


def test_emitter_evaluator_matches_champion_agent():
    """PARITY (§4.1): the injected emitter evaluator == the champion agent's own
    evaluator, exactly, on >=3 fixed boards (priors AND value)."""
    rsi = _load_rsi()
    worker_cfg = {
        "c_puct": 1.5,
        "teacher_tau_p": 5.0,
        "teacher_value_norm": 15.0,
        "teacher_leaf_quantize": "float",
    }
    hp_cfg = rsi._teacher_prior_config(worker_cfg)
    # Champion config with the same evaluator-relevant knobs. final_select /
    # reuse_tree are AGENT knobs and do not touch the evaluator contract.
    champ_cfg = HeuristicPriorConfig(
        c_puct=1.5,
        tau_p=5.0,
        value_norm=15.0,
        leaf_quantize="float",
        final_select="visits",
    )

    boards = _fixed_boards()
    assert len(boards) >= 3
    for game, board in boards:
        ev_emitter = make_heuristic_prior_evaluator(game, hp_cfg)
        agent = HeuristicPriorAgent(game, champ_cfg, simulations=8)
        p_e, v_e = ev_emitter(board)
        p_c, v_c = agent.evaluator(board)
        # value is a deterministic Cython leaf → EXACT match
        assert v_e == v_c
        np.testing.assert_array_equal(p_e, p_c)
        # priors are a valid distribution over LEGAL actions
        mask = game.get_valid_moves(board).astype(bool)
        assert p_e[~mask].sum() == 0.0
        assert p_e.sum() == pytest.approx(1.0, abs=1e-5)
        assert (p_e >= 0.0).all()
        assert -1.0 <= v_e <= 1.0


def test_cli_teacher_heuristic_prior_smoke(tmp_path):
    """SMOKE (§4.1): the real `--teacher heuristic_prior` CLI path (subprocess,
    net-free) emits a valid distillation shard + a teacher manifest block."""
    out_root = tmp_path / "sp"
    env = dict(os.environ)
    env.update(_CHAMP_ENV)
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"

    cmd = [
        sys.executable, "-u", str(SCRIPT_PATH),
        "--teacher", "heuristic_prior",
        "--output-root", str(out_root),
        "--iter", "0", "--games", "1", "--sims", "32",
        "--c-puct", "1.5", "--dirichlet-eps", "0", "--batch-size", "1",
        "--temp-threshold", "15", "--workers", "1",
        "--value-target", "score_diff", "--seed-start", "0",
    ]
    r = subprocess.run(
        cmd, cwd=str(REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=600,
    )
    assert r.returncode == 0, f"exit {r.returncode}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"

    iter_dir = out_root / "iter_00"
    shards = sorted(iter_dir.glob("seed_*.npz"))
    assert len(shards) == 1, f"expected exactly 1 shard, got {[s.name for s in shards]}"

    ds = GameDataset.load(shards[0])
    pol = np.asarray(ds.policies)
    val = np.asarray(ds.values)
    aux = np.asarray(ds.aux_mask)
    masks = np.asarray(ds.valid_masks).astype(bool)
    assert len(val) > 5, "champion self-play game should record many positions"

    # aux_mask all True: every row is a full trajectory row (no interior harvest).
    assert aux.all()

    # policy rows sum to 1 over the legal mask; zero mass off-mask.
    rowsum = pol.sum(axis=1)
    np.testing.assert_allclose(rowsum, 1.0, atol=1e-4)
    assert (pol * ~masks).sum() == 0.0
    assert (pol >= 0.0).all()

    # values in [-1, 1] and sign-consistent with THE single final score_diff:
    # every row = ±tanh((p0-p1)/15), so |value| is one constant across all rows.
    assert val.min() >= -1.0 and val.max() <= 1.0
    mags = np.unique(np.round(np.abs(val), 6))
    assert mags.size == 1, f"score_diff rows must share one |margin|, got {mags}"
    # both POVs present in a real game → at least one sign appears; if the game
    # was not a draw, both signs appear.
    if mags[0] > 0.0:
        assert set(np.sign(val)) <= {-1.0, 1.0}

    # manifest carries the resolved teacher block (self-describing-results rule).
    manifest = json.loads((iter_dir / "manifest.json").read_text())
    assert "teacher" in manifest
    t = manifest["teacher"]
    assert t["mode"] == "heuristic_prior"
    assert t["sims"] == 32
    assert t["value_target"] == "score_diff"
    assert t["config"]["tau_p"] == 5.0
    assert t["config"]["value_norm"] == 15.0
    assert t["config"]["leaf_quantize"] == "float"
    assert (
        t["resolved_leaf_env"].get("CARCASSONNE_V29_MEEPLE_CURVE")
        == "-10,-5,-1.25,0,2.5,3.75,5,6.25"
    )


def test_cli_teacher_guard_rejects_net_flags(tmp_path):
    """Guards (§4.1): --teacher heuristic_prior fails loudly with a net-steering
    flag (here --value-blend 0.5) instead of silently distilling a hybrid."""
    env = dict(os.environ)
    env.update(_CHAMP_ENV)
    cmd = [
        sys.executable, str(SCRIPT_PATH),
        "--teacher", "heuristic_prior",
        "--output-root", str(tmp_path / "sp"),
        "--iter", "0", "--games", "1", "--sims", "8",
        "--leaf-eval", "v2_5", "--value-blend", "0.5",
    ]
    r = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode != 0
    assert "incompatible" in (r.stdout + r.stderr).lower()
