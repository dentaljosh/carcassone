"""Enforce governance/LEAF_SUBSTRATES.yaml — the frozen classical leaf substrates.

A 'frozen' substrate must FAIL LOUDLY if its config silently drifts (someone edits the
MILD_CURVE constant, the cap, the closure schedule, or the harness parser). This recomputes
the config hash from the live candidate_cfg() and asserts it equals the recorded hash, plus
the human-readable fields. If this test fails, either the drift was intentional (update the
YAML + commit/config hashes deliberately) or it's a regression.
"""
from __future__ import annotations

import dataclasses as dc
import hashlib
import json
import os
import sys

import pytest

yaml = pytest.importorskip("yaml")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "v29"))
from eval_v29_vs_v28 import candidate_cfg  # noqa: E402

SPEC = os.path.join(os.path.dirname(__file__), "..", "governance", "LEAF_SUBSTRATES.yaml")


# Default-off knobs excluded from the frozen-cfg recipe so 7fc930b8 / 158f17ff stay
# stable across additive default-off fields (bag_close; C7 Term R/F). Mirrors
# scripts/measurement_infra/snapshot.py::_FROZEN_HASH_DEFAULT_OFF.
_FROZEN_HASH_DEFAULT_OFF = {"bag_close": False, "v29_meeple_return_k": 0.0, "v29_farm_flip_k": 0.0, "soft_cap_slope": 0.0, "opp_soft_cap_slope": 0.0, "farm_base_off": False, "farm_growth_off": False, "v29_phase_beta": 0.0, "v29_phase_norm": 1.0, "denial_dose": 0.0, "denial_size_min": 8.0, "denial_open_max": 2}


def _cfg_hash(cfg):
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()
         if not (k in _FROZEN_HASH_DEFAULT_OFF and v == _FROZEN_HASH_DEFAULT_OFF[k])}
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


@pytest.mark.parametrize("key", ["v2_8_production", "v2_9_bmild_cap8"])
def test_frozen_substrate_not_drifted(key):
    spec = yaml.safe_load(open(SPEC))["substrates"][key]
    live = candidate_cfg(spec["harness_name"])
    assert _cfg_hash(live) == spec["config_hash"], f"{key} config DRIFTED from the frozen hash"
    assert live.bonus_cap == spec["bonus_cap"] and live.opp_bonus_cap == spec["opp_bonus_cap"]
    assert live.meeple_k == spec["meeple_k"]
    rec_curve = spec["v29_meeple_curve"]
    assert (list(live.v29_meeple_curve) if live.v29_meeple_curve else None) == rec_curve
    # closure schedule keys come back as ints from the parser; YAML keys are ints too
    assert {int(k): v for k, v in live.closure_p.items()} == spec["closure_schedule"]
