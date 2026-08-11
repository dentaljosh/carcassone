"""--leaf-variant machinery of scripts/canonical_az/solver_score.py (v2.10 leaf arc,
docs/V210_LEAF_SPEC_2026-07-04.md TASK 1).

Contracts:
  1. leaf_cfg_from_overrides maps env-knob JSON -> explicit LeafConfig with
     _config_from_env semantics (cap->opp follows, schedule precedence, curve parse),
     never mutating/sharing the baseline cfg's dicts (no cross-contamination).
  2. An all-default variant ranker is bit-identical to the v29_leaf baseline ranker;
     two real variants produce DIFFERENT virtual_score_v2 values on midgame states.

solver_score.py mutates os.environ at import (the canonical v2.9 leaf env block),
so everything runs in a SUBPROCESS to keep this pytest session's DEFAULT_CONFIG
untouched for the other leaf tests.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_SCRIPT = r"""
import sys
sys.path.insert(0, r"%(repo)s/scripts/canonical_az")
import solver_score as SS

# ---- 1. knob mapping ---------------------------------------------------------
cfg0, bag0 = SS.leaf_cfg_from_overrides({})
base = SS.EH._heur_leaf_cfg(2.0)
assert cfg0 == base and bag0 is None, "all-default overrides must equal the baseline cfg"

cfg, bag = SS.leaf_cfg_from_overrides({
    "V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5", "V25_CAP": "12",
    "V25_MEEPLE_K": "2.5", "V25_DROP_THREE_OPEN": "1"})
assert cfg.bonus_cap == 12.0 and cfg.opp_bonus_cap == 12.0, "opp cap must follow V25_CAP"
assert cfg.meeple_k == 2.5
assert cfg.closure_p == {1: 0.5, 2: 0.2}, "DROP_THREE_OPEN=1 schedule"
assert cfg.v29_meeple_curve == (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
assert bag is None
assert cfg.closure_p is not base.closure_p, "schedule dict must be fresh, never shared"
assert base.closure_p == {1: 0.5, 2: 0.2, 3: 0.05}, "baseline schedule untouched"

cfg2, _ = SS.leaf_cfg_from_overrides({"V25_CAP": "6", "V25_OPP_CAP": "10"})
assert cfg2.bonus_cap == 6.0 and cfg2.opp_bonus_cap == 10.0

cfg3, _ = SS.leaf_cfg_from_overrides({"V29_MEEPLE_CURVE": "", "V25_MEEPLE_K": "1.5"})
assert cfg3.v29_meeple_curve is None and cfg3.meeple_k == 1.5, "empty curve -> flat k term"

cfg4, bag4 = SS.leaf_cfg_from_overrides({"V210_BAG_CLOSE": "1"})
assert bag4 is True and cfg4 == base, "bag knob is NOT a LeafConfig field (frozen hash)"

try:
    SS.leaf_cfg_from_overrides({"V25_TYPO": "1"})
    raise SystemExit("unknown knob must raise")
except ValueError:
    pass

# ---- 2. ranker behaviour on real states ---------------------------------------
import random
import numpy as np
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import virtual_score_v2

states = []
for s in range(6):
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    rng = random.Random(1000 + s)
    for ply in range(60):
        if g.get_game_ended(b, 0) != 0.0:
            break
        legal = np.flatnonzero(g.get_valid_moves(b))
        b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
        if ply >= 30 and ply %% 10 == 0:
            states.append(b.state)
assert states

cfg_lo, _ = SS.leaf_cfg_from_overrides({"V25_CAP": "2"})
cfg_hi, _ = SS.leaf_cfg_from_overrides({"V25_CAP": "12"})
n_base_eq, n_lo_hi_diff = 0, 0
for st in states:
    for p in (0, 1):
        v_base = virtual_score_v2(st, p, base)
        v_def = virtual_score_v2(st, p, cfg0)
        assert v_def == v_base, "all-default variant cfg must be bit-identical to baseline"
        n_base_eq += 1
        if virtual_score_v2(st, p, cfg_lo) != virtual_score_v2(st, p, cfg_hi):
            n_lo_hi_diff += 1
        # interleaved re-eval of the baseline: per-call cfgs must not contaminate
        assert virtual_score_v2(st, p, base) == v_base, "cross-contamination detected"
assert n_lo_hi_diff > 0, "cap=2 vs cap=12 variants never differed - variant cfg inert"
print(f"OK n_states={len(states)} base_eq={n_base_eq} lo_hi_diff={n_lo_hi_diff}")
"""


def test_leaf_variant_machinery_subprocess():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT % {"repo": str(REPO)}],
        capture_output=True, text=True, timeout=600,
        cwd=str(REPO),
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "OK n_states=" in proc.stdout
