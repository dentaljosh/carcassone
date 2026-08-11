"""Shared setup + helpers for the Phase-0.4 golden correctness suite.

Importing this module FIRST (before any carcassonne_ai import) pins the frozen v2.9
env block, sets up sys.path, and exposes the three EXPLICITLY-constructed leaf configs
(v2.7 / v2.8 / v2.9 Bmild_cap8) + the canonical leaf/flat/mask helpers used by both
`gen_golden.py` (to freeze values) and `test_golden.py` (to verify them).

The configs are built by hand (NOT `dataclasses.replace(DEFAULT_CONFIG, ...)`) so the
frozen fixture reproduces regardless of import order under a full `pytest tests/` run —
`DEFAULT_CONFIG` is env-built once at first import and another test module may win that
race. Passing an explicit LeafConfig to the leaf functions bypasses DEFAULT_CONFIG
entirely, so the frozen values are a pure function of state + these configs.
"""
from __future__ import annotations

# --- frozen v2.9 env preamble (MUST precede any carcassonne_ai import) ---------
import os

ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
}
for _k, _v in ENV.items():
    os.environ[_k] = _v
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import dataclasses as dc  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "engine",
           ROOT / "scripts" / "level2", ROOT / "scripts" / "measurement_infra"):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import numpy as np  # noqa: E402

import carcassonne_ai.virtual_score_v2 as _v2  # noqa: E402
from carcassonne_ai.flat_leaf import flat_base_score, flat_virtual_score_v2  # noqa: E402
from carcassonne_ai.virtual_score_v2 import LeafConfig, virtual_score_v2  # noqa: E402
from root_replay import replay_actions  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "golden_fixture.json"
FROZEN_V29_HASH = "7fc930b82801cb43"     # documented/governance hash (see finding note)
SOLVER_BUDGET = 500_000
MOVER_XOR = 0x5151

# --- the three EXPLICIT frozen leaf configs -----------------------------------
_CLOSURE = {1: 0.5, 2: 0.2, 3: 0.05}     # DROP_THREE_OPEN=0 schedule
_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
CFG_V27 = LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0)
CFG_V28 = LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0, meeple_k=2.0)
CFG_V29 = LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                     meeple_k=2.0, v29_meeple_curve=_CURVE)
CFGS = {"v27": CFG_V27, "v28": CFG_V28, "v29": CFG_V29}


def cfg_hash(cfg) -> str:
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()}
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def k_remaining(state) -> int:
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def leaf_canon(state, player: int, cfg) -> int:
    """Object-path virtual_score_v2 under CANONICAL_BONUS_SUM (order-independent fsum),
    so the frozen int is reproducible across processes / hash seeds."""
    saved = _v2.CANONICAL_BONUS_SUM
    _v2.CANONICAL_BONUS_SUM = True
    try:
        return int(virtual_score_v2(state, player, cfg))
    finally:
        _v2.CANONICAL_BONUS_SUM = saved


def flat_eq_object(state, cfg) -> bool:
    """flat_virtual_score_v2 == virtual_score_v2 (both players) under CANONICAL."""
    saved = _v2.CANONICAL_BONUS_SUM
    _v2.CANONICAL_BONUS_SUM = True
    try:
        for p in range(2):
            if int(flat_virtual_score_v2(state, p, cfg)) != int(virtual_score_v2(state, p, cfg)):
                return False
        return True
    finally:
        _v2.CANONICAL_BONUS_SUM = saved


def mask_info(game, board) -> dict:
    mask = np.asarray(game.get_valid_moves(board), dtype=bool)
    legal = np.flatnonzero(mask).tolist()
    sample = sorted({int(i) for i in (legal[:5] + legal[-2:])})
    return {
        "window_size": int(board.offset.size),
        "action_size": int(mask.shape[0]),
        "legal_count": int(mask.sum()),
        "legal_mask_sha256": hashlib.sha256(mask.tobytes()).hexdigest(),
        "legal_sample": sample,
    }


__all__ = [
    "ENV", "ROOT", "FIXTURE", "FROZEN_V29_HASH", "SOLVER_BUDGET", "MOVER_XOR",
    "CFGS", "CFG_V27", "CFG_V28", "CFG_V29", "cfg_hash", "k_remaining",
    "leaf_canon", "flat_eq_object", "mask_info", "flat_base_score",
    "flat_virtual_score_v2", "virtual_score_v2", "replay_actions", "np", "_v2",
]
