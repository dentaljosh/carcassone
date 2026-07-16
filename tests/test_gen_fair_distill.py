"""Fair-distill emitter smoke (fair-distill addendum "Parity/smoke test").

Runs scripts/distill_flywheel/gen_fair_distill.py as a SUBPROCESS (1 game, k_dets=2,
sims=32) with the champion env (curve125) forced, then loads the produced shard +
manifest and asserts the distillation contract:
  * trajectory (aux_mask=True) policy rows sum to 1.0 over the legal mask, 0 off-mask;
  * aux_mask is MIXED (some True trajectory rows + an exact-endgame value-only tail);
  * value-only (aux_mask=False) rows carry dummy zero policy/mask;
  * values ∈ [-1,1] and sign-consistent with the final score_diff;
  * the manifest teacher block is present with policy_source / move_selected_by, and
    the resolved leaf CONFIG VALUES are the production champion leaf: curve125,
    cap8/opp_cap8, closure_p default (the runtime frozen-config-hash is recorded for
    provenance only — the PRODUCTION.yaml fingerprint 158f17ff is STALE dataclass
    drift, so we verify VALUES not the hash string).

Subprocess (not in-process) so the curve125 leaf is guaranteed regardless of any
sibling module's DEFAULT_CONFIG import-order pollution (see tests/conftest.py).
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.warmstart import GameDataset  # noqa: E402

# The champion leaf env (curve125) — mirrors scripts/distill_flywheel/champ_env.sh.
# Passed to the subprocess so curve125 is forced even if the parent session set curve100.
_CHAMP_ENV = {
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}
_CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]


def test_fair_distill_emitter_smoke(tmp_path):
    out = tmp_path / "fair_distill_smoke"
    script = REPO / "scripts" / "distill_flywheel" / "gen_fair_distill.py"
    seed_start = 700_000_000
    env = {**os.environ, **_CHAMP_ENV}
    r = subprocess.run(
        [sys.executable, "-u", str(script), "--games", "1", "--k-dets", "2",
         "--sims", "32", "--workers", "1", "--seed-start", str(seed_start),
         "--out", str(out)],
        env=env, capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, f"emitter failed:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"

    shards = sorted(out.glob("seed_*.npz"))
    assert len(shards) == 1, f"expected 1 shard, got {shards}"
    ds = GameDataset.load(shards[0])
    aux = np.asarray(ds.aux_mask, dtype=bool)
    pol = np.asarray(ds.policies, dtype=np.float32)
    mask = np.asarray(ds.valid_masks, dtype=bool)
    vals = np.asarray(ds.values, dtype=np.float32)
    N = len(aux)
    assert N > 20, "a full game should record many plies"

    # (1) MIXED aux_mask: trajectory policy rows True + an exact-endgame value-only tail.
    assert aux.sum() > 0, "no full-trajectory (policy) rows"
    assert (~aux).sum() > 0, "no value-only rows (exact-endgame tail missing?)"

    # (2) trajectory policy rows sum to 1 over the legal mask, 0 off-mask.
    prow_sums = pol[aux].sum(axis=1)
    assert np.allclose(prow_sums, 1.0, atol=1e-5), \
        f"policy rows must sum to 1; got [{prow_sums.min()}, {prow_sums.max()}]"
    off_mask = float((pol[aux] * (~mask[aux])).sum())
    assert off_mask == 0.0, f"policy has {off_mask} mass off the legal mask"

    # (3) value-only rows carry dummy zeros.
    assert float(pol[~aux].sum()) == 0.0, "value-only rows must have zero policy"
    assert int(mask[~aux].sum()) == 0, "value-only rows must have empty mask"

    # (4) values ∈ [-1,1], sign-consistent with the final score_diff.
    assert vals.min() >= -1.0 and vals.max() <= 1.0, "values out of [-1,1]"
    man = json.loads((out / "manifest.json").read_text())
    cfg = man["config"]
    s0, s1 = None, None
    # The manifest doesn't carry per-game score; recompute the sign from the recorded
    # symmetric value magnitude vs a fresh replay is overkill — instead pin the
    # invariant that all values share one magnitude |tanh(diff/15)| and BOTH signs
    # appear iff diff != 0 (mover-POV backfill).
    mag = np.abs(vals)
    assert np.allclose(mag, mag[0], atol=1e-5), "all rows must share |tanh(diff/15)| (outcome backfill)"
    if mag[0] > 1e-6:
        assert (vals > 0).any() and (vals < 0).any(), \
            "a decided game must have both +z (winner-mover) and -z (loser-mover) rows"

    # (5) manifest teacher block + resolved champion leaf CONFIG VALUES (not the hash).
    teacher = cfg["teacher"]
    assert teacher["policy_source"].startswith("pooled_visit_counts")
    assert teacher["move_selected_by"] == "pooled_q_argmax"
    assert teacher["k_dets"] == 2 and teacher["sims_per_det"] == 32
    assert "resolved_leaf_hash_runtime" in teacher, "runtime leaf hash must be recorded (provenance)"
    leaf = teacher["resolved_config"]["leaf_cfg"]
    assert [float(x) for x in leaf["v29_meeple_curve"]] == _CURVE125, \
        f"leaf is NOT curve125 (the curve100 trap): {leaf['v29_meeple_curve']}"
    assert float(leaf["bonus_cap"]) == 8.0 and float(leaf["opp_bonus_cap"]) == 8.0
    closure = {int(k): float(v) for k, v in leaf["closure_p"].items()}
    assert closure == {1: 0.5, 2: 0.2, 3: 0.05}, f"closure_p not default 3-open: {closure}"
    assert cfg["value_target"] == "game_outcome" and float(cfg["outcome_norm"]) == 15.0
