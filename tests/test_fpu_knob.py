"""`fpu_reduction` end-to-end plumbing (measurement/fpu_resurrection_prep).

⛔ **THE DEFECT THESE TESTS EXIST FOR.** Until 2026-08-29
`rust_agent.search_config_rs` passed a HARD-CODED `None` into `SearchConfigRs`'s
`fpu_reduction` slot. `carc_rs` had accepted `Option<f64>` there since the
rustport and `carc_core::search` implemented the rule — but **no config could
reach it**, so the champion could not express the knob on the backend it plays
on, and a caller that set it got a python leg that honoured it and a Rust leg
that did not: two different agents wearing one config. That is the same
silent-divergence class as the `c_lcb` hard-code (ROUND2 C-g), one surface over.

The tests below are ordered by what they defend:

  1. the field exists, defaults to `None`, and validates;
  2. the value REACHES `carc_rs` (the readback that the hard-code would fail);
  3. `None` is byte-identical to the pre-knob path (the golden gate's
     proposition, at unit scale) and a set value is NOT (the positive control);
  4. the CLI flags exist, reject malformed values, and the resolved knob lands
     in the manifest on the CANDIDATE side ONLY;
  5. ⭐ `--cand-c-puct` is a REAL flag and not a duplicate of `--c-puct` — the
     build brief asserted a c_puct cell "needs no new plumbing", which is false:
     `--c-puct` builds `champ_cfg_dict`, `_make_opponent` feeds that SAME dict
     to `_cfg_from_dict`, so it moves BOTH SIDES.
"""
from __future__ import annotations

import dataclasses as dc
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EVAL = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"
PREP = REPO / "measurement" / "fpu_resurrection_prep"


def _cfg(**kw):
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig

    return HeuristicPriorConfig(**kw)


# --------------------------------------------------------------------------- #
# 1. THE CONFIG FIELD                                                          #
# --------------------------------------------------------------------------- #

def test_default_is_none_the_champion():
    """`None` == the NeuralMCTS legacy optimistic q=0 == the champion."""
    assert _cfg().fpu_reduction is None


def test_value_passes_through_and_is_coerced_to_float():
    c = _cfg(fpu_reduction=0.2)
    assert c.fpu_reduction == 0.2 and isinstance(c.fpu_reduction, float)
    assert _cfg(fpu_reduction=1).fpu_reduction == 1.0


def test_zero_is_not_none():
    """⛔ `0.0` is NOT "unset". `Some(0.0)` takes the `node_q - 0.0` branch — the
    PARENT's Q — while `None` takes the flat `0.0` branch. A plumbing that
    coerced one into the other would silently change the agent."""
    assert _cfg(fpu_reduction=0.0).fpu_reduction == 0.0
    assert _cfg(fpu_reduction=0.0).fpu_reduction is not None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_is_refused(bad):
    with pytest.raises(ValueError, match="fpu_reduction must be finite"):
        _cfg(fpu_reduction=bad)


def test_manifest_carries_the_resolved_value_always():
    """`G-FPU`'s address. ABSENT is FAIL, so the key is emitted UNCONDITIONALLY
    and `null` is a POSITIVE statement, never a missing key."""
    assert "fpu_reduction" in _cfg().as_manifest()
    assert _cfg().as_manifest()["fpu_reduction"] is None
    assert _cfg(fpu_reduction=0.4).as_manifest()["fpu_reduction"] == 0.4


def test_appended_last_so_positional_construction_is_unchanged():
    """The field is at the END of the dataclass, so every historical positional
    construction keeps its meaning."""
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig

    assert list(HeuristicPriorConfig.__dataclass_fields__)[-1] == "fpu_reduction"


# --------------------------------------------------------------------------- #
# 2. IT REACHES carc_rs — the readback the hard-code would fail                 #
# --------------------------------------------------------------------------- #

_HAS_RS = importlib.util.find_spec("carc_rs") is not None
rs_only = pytest.mark.skipif(not _HAS_RS, reason="carc_rs wheel not installed")


@rs_only
@pytest.mark.parametrize("val,want", [(None, "fpu=None"), (0.2, "fpu=Some(0.2)"),
                                      (0.0, "fpu=Some(0.0)")])
def test_value_reaches_search_config_rs(val, want):
    """⛔⛔ THE REGRESSION TEST FOR THE AUDITED DEFECT. `SearchConfigRs.__repr__`
    prints `fpu={:?}` of the stored `Option<f64>`, so this is a genuine readback
    of what the RUST side holds — not a restatement of what python sent. With
    the old hard-coded `None` the 0.2 and 0.0 cases both read `fpu=None`."""
    from carcassonne_ai.rust_agent import search_config_rs

    assert want in repr(search_config_rs(_cfg(fpu_reduction=val), 8))


@rs_only
def test_search_config_rs_survives_a_config_without_the_field():
    """`getattr(cfg, "fpu_reduction", None)` — a config object predating the
    field (or any duck-typed stand-in) must still build."""
    from carcassonne_ai.rust_agent import search_config_rs

    base = _cfg()
    stripped = dc.replace(base)
    object.__delattr__ if False else None       # documentation of intent only
    d = {f: getattr(base, f) for f in base.__dataclass_fields__
         if f != "fpu_reduction"}

    class _Legacy:
        pass

    legacy = _Legacy()
    for k, v in d.items():
        setattr(legacy, k, v)
    legacy.resolved_leaf_cfg = stripped.resolved_leaf_cfg
    assert "fpu=None" in repr(search_config_rs(legacy, 8))


# --------------------------------------------------------------------------- #
# 3. IDENTITY AT None / DIVERGENCE WHEN SET — the golden gate at unit scale     #
# --------------------------------------------------------------------------- #

def test_python_search_honours_the_knob():
    """The python leg is threaded too (unlike the J-rules surfaces and the tie
    arbiter, which are rust-only): `carc_core::search/mod.rs:816` and
    `mcts.py:1225` implement the IDENTICAL rule, so the two backends mirror."""
    import random

    import numpy as np

    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.heuristic_prior_mcts import make_heuristic_prior_mcts

    g = Game(enable_legal_moves_cache=True)
    # ⛔ SEED THE **GLOBAL** RNG, not just the local one below. `get_init_board()`
    # shuffles the deck from the `random` MODULE, so without this the DECK depends
    # on how much global randomness every previously-COLLECTED test module
    # consumed at import time — an order-of-collection artefact that made the
    # sibling assertion in tests/test_neural_mcts.py flaky (diagnosed 2026-08-30;
    # importing tests/test_b64_cell.py is enough to shift the stream). The local
    # `Random(3)` does not protect against it: it does not drive the deck.
    random.seed(12345)
    b = g.get_init_board()
    # ⚠️ The INIT board has ~1 legal move (the first tile is forced), so FPU has
    # nothing to reorder there. Advance to a branchy mid-game position — the same
    # setup tests/test_neural_mcts.py's FPU test uses, and for the same reason.
    rng = random.Random(3)
    for _ in range(12):
        if g.get_game_ended(b, 0) != 0.0:
            break
        b, _ = g.get_next_state(
            b, rng.choice(np.flatnonzero(g.get_valid_moves(b)).tolist()))
    assert len(np.flatnonzero(g.get_valid_moves(b))) > 1, "need a branchy board"

    legacy = make_heuristic_prior_mcts(g, _cfg(), 48, seed=0)
    pess = make_heuristic_prior_mcts(g, _cfg(fpu_reduction=0.5), 48, seed=0)
    assert legacy.fpu_reduction is None
    assert pess.fpu_reduction == 0.5
    v_legacy = legacy.search(b)
    v_pess = pess.search(b)
    assert v_legacy != v_pess, "fpu_reduction had no effect on the python search"


def test_golden_gate_artifact_is_pass():
    """⭐⭐ THE SHIPPED GOLDEN GATE. `FPU_BITEXACT.json` is the adjudication of
    three real legs — OLD tree / NEW tree at `None` / NEW tree at 0.2 — over 20
    frozen seeded games on ONE installed wheel. It is carried in-tree so the
    claim is auditable without re-running it, and asserted here so it cannot
    silently rot into a FAIL nobody reads."""
    p = PREP / "FPU_BITEXACT.json"
    assert p.is_file(), "FPU_BITEXACT.json ABSENT — ABSENT is FAIL"
    v = json.loads(p.read_text())
    assert v["verdict"] == "PASS", f"golden gate is {v['verdict']}: {v['failed']}"
    by = {c["check"]: c for c in v["checks"]}
    # the two substantive halves, named individually so a partial rot is legible
    assert by["IDENTITY"]["ok"], "the DEFAULT path moved"
    assert by["POSITIVE"]["ok"], "the knob did not bind — the audited defect"
    assert by["ONE-WHEEL"]["ok"], "the legs did not share one carc_rs binary"
    assert by["POSITIVE"]["detail"]["games_that_differ"] == \
        by["POSITIVE"]["detail"]["games_total"]


# --------------------------------------------------------------------------- #
# 4/5. THE CLI                                                                 #
# --------------------------------------------------------------------------- #

def _run_eval(*args):
    return subprocess.run([sys.executable, str(EVAL), *args],
                          capture_output=True, text=True, timeout=300)


def test_flags_exist_and_are_candidate_side():
    h = _run_eval("--help").stdout
    assert "--cand-fpu-reduction" in h
    assert "--cand-c-puct" in h


@pytest.mark.parametrize("flag,bad", [
    ("--cand-fpu-reduction", "banana"),
    ("--cand-fpu-reduction", "nan"),
    ("--cand-c-puct", "banana"),
    ("--cand-c-puct", "0"),
    ("--cand-c-puct", "-1.5"),
])
def test_malformed_values_are_refused(flag, bad):
    """argparse's own float() rejects the non-numeric cases; main()'s
    resolve-once block rejects the numerically-invalid ones. Either way the
    process must DIE, never launch a cell over a knob it could not resolve."""
    r = _run_eval("--summary-only", "--n", "2", flag, bad)
    assert r.returncode != 0, f"{flag} {bad} was ACCEPTED"


def test_cand_c_puct_is_not_a_duplicate_of_c_puct():
    """⭐ THE DEVIATION, PINNED AS A TEST (DEVIATIONS.md D1).

    `--c-puct` is SHARED: `champ_cfg_dict` is built from it and `_make_opponent`
    feeds that SAME dict through `_cfg_from_dict`, so a "candidate c_puct" cell
    built on `--c-puct` would be champion-vs-champion. `cand_search` is the only
    seam that reaches the candidate alone."""
    sys.path.insert(0, str(EVAL.parent))
    import eval_fair_puct as E

    shared = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
              "final_select": "visits", "value_norm": 15.0}
    opp = E._cfg_from_dict(shared)                       # the opponent builder
    cand = E._cfg_from_dict(shared, cand_search={"c_puct": 1.0,
                                                 "fpu_reduction": 0.2})
    assert opp.c_puct == 1.5 and opp.fpu_reduction is None, \
        "the OPPONENT builder saw a candidate-only knob — the cell is not single-variable"
    assert cand.c_puct == 1.0 and cand.fpu_reduction == 0.2


def test_cand_search_none_is_byte_identical():
    """Every historical caller passes `cand_search=None`; that path must produce
    the same config it did before the parameter existed."""
    sys.path.insert(0, str(EVAL.parent))
    import eval_fair_puct as E

    a = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None)
    b = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                           cand_search=None)
    c = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                           cand_search={"c_puct": None, "fpu_reduction": None})
    assert a.as_manifest() == b.as_manifest() == c.as_manifest()
    assert a.fpu_reduction is None


def test_manifest_emits_the_resolved_cand_search_on_a_real_run(tmp_path):
    """⭐ `G-FPU`'s and `G-CPUCT`'s addresses, on an ACTUAL emitted manifest —
    not on a hand-built dict. The two witnesses are:
      * `config.cand_search` — the resolved request; and
      * `config.champion.fpu_reduction` vs `config.opponent.champ_cfg.
        fpu_reduction` — the two sides' RESOLVED configs, which is the read that
        cannot be faked by a flag that never bound.
    ⚠️ Tiny budget: this asserts WIRING, never strength."""
    out = tmp_path / "cell"
    r = _run_eval("--info", "fair", "--backend", "rust", "--opponent",
                  "fair-champion", "--k-dets", "1", "--sims", "16",
                  "--opp-k-dets", "1", "--opp-sims", "16", "--exact-k", "2",
                  "--n", "2", "--paired", "--seed-start", "13900000000",
                  "--workers", "1", "--rules-profile", "fixed_v1",
                  "--no-results-csv",
                  "--out-root", str(tmp_path), "--out-subdir", "cell",
                  "--cand-fpu-reduction", "0.2", "--cand-c-puct", "1.0")
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    man = json.loads((out / "manifest.json").read_text())
    cs = man["config"]["cand_search"]
    assert cs["fpu_reduction"] == 0.2
    assert cs["c_puct"] == 1.0
    assert cs["shared_c_puct"] == 1.5
    # the two-sided witness
    assert man["config"]["champion"]["fpu_reduction"] == 0.2
    assert man["config"]["champion"]["c_puct"] == 1.0
    assert man["config"]["opponent"]["champ_cfg"]["fpu_reduction"] is None
    assert man["config"]["opponent"]["champ_cfg"]["c_puct"] == 1.5
    # the leaf deliberately does NOT move — which is exactly why the manifest
    # dict above is the wiring gate and a moved-hash check proves nothing here
    assert man["config"]["cand_leaf_hash"] == man["config"]["opponent"]["leaf_hash"]


def test_manifest_carries_cand_search_even_when_the_knobs_are_off(tmp_path):
    """⛔ ABSENT is FAIL, so an OFF cell must still say so on disk, in full."""
    out = tmp_path / "cell"
    r = _run_eval("--info", "fair", "--backend", "rust", "--opponent",
                  "fair-champion", "--k-dets", "1", "--sims", "16",
                  "--opp-k-dets", "1", "--opp-sims", "16", "--exact-k", "2",
                  "--n", "2", "--paired", "--seed-start", "13900000100",
                  "--workers", "1", "--rules-profile", "fixed_v1",
                  "--no-results-csv",
                  "--out-root", str(tmp_path), "--out-subdir", "cell")
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    man = json.loads((out / "manifest.json").read_text())
    # ⭐ GREW 2026-09-01 (measurement/taup_audit_leg_20260901): `tau_p` and
    # `shared_tau_p` joined the dict when `--cand-tau-p` was added as the exact
    # mirror of `--cand-c-puct`. ADDITIVE and under the SAME convention —
    # `tau_p: null` is the POSITIVE statement "the shared --tau-p", never a
    # missing key. Every banked gate digs this dict BY KEY NAME
    # (fpu_resurrection_prep/screen_lib.py, fpu_h2h_r2_prep/analyze_h2h.py), so
    # nothing downstream reads the key SET — but THIS test does, deliberately, so
    # that a future addition has to be noticed and justified here rather than
    # slipping in.
    assert man["config"]["cand_search"] == {
        "fpu_reduction": None, "c_puct": None, "tau_p": None,
        "shared_c_puct": 1.5, "shared_tau_p": 5.0}
    assert man["config"]["champion"]["fpu_reduction"] is None
