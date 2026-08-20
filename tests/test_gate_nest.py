#!/usr/bin/env python3
"""`G-NEST` — the nested-CRN emitter.

Two classes of test, and the pair needs both:
  * BYTE-IDENTITY ON THE REAL SEEDING — the actual rust `tier1_world_deck`
    worlds, the actual arbiter arms. Skipped only where `carc_rs` is absent.
  * A SYNTHETIC DIVERGENCE FAILS — a fake whose worlds depend on `B`. Without
    this the suite could not tell a passing witness from one that cannot fail.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CELL = ROOT / "measurement" / "tiearb_widening_20260817" / "b64_cell"
sys.path.insert(0, str(CELL))
sys.path.insert(0, str(ROOT / "scripts" / "tiletie"))

import analyze_b64_cell as AB                                   # noqa: E402
import gate_nest as GN                                          # noqa: E402

try:
    import carc_rs                                              # noqa: E402
    from carcassonne_ai.rust_agent import leaf_config_rs        # noqa: E402
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
    LC = leaf_config_rs(DEFAULT_CONFIG)
    HAVE_RS = True
except Exception:                                               # noqa: BLE001
    carc_rs, LC, HAVE_RS = None, None, False

needs_rs = pytest.mark.skipif(not HAVE_RS, reason="carc_rs unavailable")


# =========================================================================== #
# 1. the seed function, and the ANCHOR that makes it the arbiter's             #
# =========================================================================== #
def test_seed_i64_is_the_documented_construction():
    """`sha256(parts joined by '|')[:8]`, big-endian, sign bit cleared."""
    parts = ["tiearb2-deploy-v1", "deadbeef", 32, 7]
    h = hashlib.sha256("tiearb2-deploy-v1|deadbeef|32|7".encode()).digest()
    assert GN.seed_i64(parts) == int.from_bytes(h[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF
    assert GN.seed_i64(parts) >= 0
    # the '|'-join is load-bearing: it is what stops ("a|b","c") colliding with
    # ("a","b|c") in a way a concatenation would not
    assert GN.seed_i64(["a", "b"]) != GN.seed_i64(["a", "c"])


def test_the_four_streams_are_DIFFERENT_seeds():
    """world / playout / cap / select must not collide — a collision would make
    the playout reuse the world's stream and quietly destroy the CRN."""
    args = ("tiearb2-deploy-v1", "d1", 5)
    seeds = {GN.world_seed(*args, 0), GN.playout_seed(*args, 0),
             GN.cap_seed(*args), GN.select_seed(*args)}
    assert len(seeds) == 4


@needs_rs
def test_the_ANCHOR_reproduces_the_REAL_arbiter_arms():
    """⭐ THE TEST THAT STOPS THE WITNESS BEING A TAUTOLOGY. `seed_i64` is not
    exported, so the emitter transcribes it — and a transcription compared
    against itself proves nothing. Here the python seeding must reproduce the
    RUST arbiter's own capped arm set, byte for byte, at a position where the
    cap draw is genuinely consulted."""
    pos = GN.pinned_position(carc_rs, LC)
    assert pos["capped"] is True
    assert pos["n_distinct_afterstates"] > GN.DEPLOYED_J, \
        "the cap must actually fire, or the anchor cannot fail"
    a = GN.reproduce_cap_draw(carc_rs, pos)
    assert a["ok"] is True, a
    assert a["reproduced_arms"] == a["arbiter_arms"]
    assert len(a["arbiter_arms"]) == GN.DEPLOYED_J


@needs_rs
def test_a_WRONG_seed_makes_the_anchor_FAIL():
    """The anchor's own falsifier: perturb the salt and the reproduction must
    stop matching. An anchor that passes under a wrong seed is not an anchor."""
    pos = GN.pinned_position(carc_rs, LC)
    bad = GN.reproduce_cap_draw(carc_rs, pos, salt="not-the-deploy-salt")
    assert bad["ok"] is False
    assert "NOT the one the arbiter uses" in bad["why"]


# =========================================================================== #
# 2. BYTE-IDENTITY on the real seeding                                         #
# =========================================================================== #
@needs_rs
def test_the_real_worlds_NEST_byte_for_byte():
    """B=64's worlds 0..15 against B=16's ENTIRE set — real determinized decks
    out of rust, not just the seeds that produced them."""
    pos = GN.pinned_position(carc_rs, LC)
    wide = GN.generate(carc_rs, pos, 64)
    narrow = GN.generate(carc_rs, pos, 16)
    c = GN.compare(wide, narrow)
    assert c["worlds_byte_identical"] is True
    assert c["world_seeds_identical"] and c["playout_seeds_identical"]
    assert c["cap_seed_identical"] and c["select_seed_identical"]
    assert c["first_differing_j"] is None
    assert wide["worlds"][:16] == narrow["worlds"]


@needs_rs
def test_the_worlds_are_DISTINCT_so_identity_is_not_degeneracy():
    """⚠️ 64 identical worlds would also satisfy 'the first 16 match' — and
    would mean the determinization is broken, not nested."""
    pos = GN.pinned_position(carc_rs, LC)
    c = GN.compare(GN.generate(carc_rs, pos, 64), GN.generate(carc_rs, pos, 16))
    assert c["n_distinct_worlds_wide"] == 64
    assert c["n_distinct_worlds_narrow"] == 16


@needs_rs
def test_the_pinned_position_is_REPRODUCIBLE_from_the_two_constants():
    a = GN.pinned_position(carc_rs, LC)
    b = GN.pinned_position(carc_rs, LC)
    assert a["state_digest"] == b["state_digest"] and a["ply"] == b["ply"]
    assert a["prefix_actions"] == b["prefix_actions"]
    assert a["deck_seed"] == GN.CONTROL_DECK_SEED


@needs_rs
def test_the_END_TO_END_witness_is_TRUE_at_HEAD():
    doc = GN.build(carc_rs, LC, repo=ROOT)
    assert doc["witness"] is True, doc.get("why")
    assert all(doc["conjuncts"].values()), doc["conjuncts"]
    assert doc["pinned"]["salt"] == "tiearb2-deploy-v1"
    assert doc["adjudicates"].startswith("NOTHING")


# =========================================================================== #
# 3. A SYNTHETIC DIVERGENCE FAILS — the witness can convict                    #
# =========================================================================== #
class _BDependentRS:
    """A fake whose world decks depend on `B` — i.e. the nesting BROKEN. Only
    `tier1_world_deck` is needed by `generate`."""

    def __init__(self, b_leak=True):
        self.b_leak = b_leak
        self.current_b = None

    def tier1_world_deck(self, deck_seed, actions, ply, world_seed):
        tag = f"{world_seed}" + (f"-B{self.current_b}" if self.b_leak else "")
        return [f"tile-{tag}-{i}" for i in range(3)]


def _pos():
    return {"deck_seed": "1", "prefix_actions": [1, 2, 3], "ply": 3,
            "state_digest": "d0", "seat": 0, "tie_actions": [1, 2, 3, 4, 5],
            "arms": [1, 2, 3, 4], "n_distinct_afterstates": 5, "capped": True}


def test_a_B_DEPENDENT_world_set_FAILS_the_comparison():
    """⛔ The failure the gate exists to catch: if the worlds depend on `B`,
    WIDE and NARROW are two unrelated draws and the increment framing is void."""
    rs = _BDependentRS(b_leak=True)
    pos = _pos()
    rs.current_b = 64
    wide = GN.generate(rs, pos, 64)
    rs.current_b = 16
    narrow = GN.generate(rs, pos, 16)
    c = GN.compare(wide, narrow)
    assert c["worlds_byte_identical"] is False
    assert c["first_differing_j"] == 0
    # ⚠️ the SEEDS still match — which is exactly why the runtime half compares
    # the WORLDS and not only the seeds that produced them
    assert c["world_seeds_identical"] is True


def test_the_same_fake_WITHOUT_the_leak_passes():
    """The control: the fake differs from the failing case in one flag, so the
    failure above is attributable to the B-dependence and nothing else."""
    rs = _BDependentRS(b_leak=False)
    pos = _pos()
    c = GN.compare(GN.generate(rs, pos, 64), GN.generate(rs, pos, 16))
    assert c["worlds_byte_identical"] is True
    assert c["n_distinct_worlds_wide"] == 64


def test_a_DEGENERATE_world_set_is_caught_by_the_distinctness_control():
    class _Constant:
        def tier1_world_deck(self, *a, **k):
            return ["same", "deck", "always"]
    c = GN.compare(GN.generate(_Constant(), _pos(), 64),
                   GN.generate(_Constant(), _pos(), 16))
    assert c["worlds_byte_identical"] is True      # identity holds...
    assert c["n_distinct_worlds_wide"] == 1        # ...but it is degeneracy
    assert c["n_distinct_worlds_narrow"] == 1


def test_a_FAILED_anchor_reports_NOTHING_ELSE():
    """⛔ Fail closed: if the transcribed seeding is not the arbiter's, every
    downstream comparison is a python-vs-python identity, so the emitter must
    not print one."""
    class _WrongArms:
        def shuffle_indices(self, seed, n, mode):
            return list(range(n))

        def tier1_world_deck(self, *a, **k):
            return ["x"]

        class MirrorState:
            pass
    rs = _WrongArms()
    pos = _pos()
    pos["arms"] = [9, 9, 9, 9]                    # cannot be reproduced
    doc_pos, doc_anchor = pos, GN.reproduce_cap_draw(rs, pos)
    assert doc_anchor["ok"] is False
    # and `build` short-circuits on it (checked on the source contract)
    src = Path(GN.__file__).read_text()
    assert 'if not anchor["ok"]:' in src
    assert 'doc["witness"] = False' in src
    assert doc_pos["arms"] == [9, 9, 9, 9]


# =========================================================================== #
# 4. the CONSUMER contract — what `analyze_b64_cell.gate_nest` reads           #
# =========================================================================== #
@needs_rs
def test_the_emitted_doc_satisfies_the_CONSUMER(tmp_path):
    """`gate_nest` reads `witness` (and shows `sites`/`why`). The emitter must
    speak exactly that schema, or the gate fails on a healthy run."""
    doc = GN.build(carc_rs, LC, repo=ROOT)
    p = tmp_path / "GATE_NEST.json"
    p.write_text(json.dumps(doc, indent=2, sort_keys=True))
    ok, obs = AB.gate_nest(json.loads(p.read_text()))
    assert ok is True
    assert obs["present"] is True and obs["witness"] is True
    assert obs["sites"] and obs["why"]


def test_ABSENCE_still_FAILS_the_consumer():
    """The gap this emitter closes: with no artifact the gate could only ever
    fail on absence — and absence is a FAIL, never a pass."""
    ok, obs = AB.gate_nest(None)
    assert ok is False and obs["present"] is False
    assert "ABSENT" in obs["why"]


def test_a_witness_FALSE_doc_fails_the_consumer():
    ok, _ = AB.gate_nest({"witness": False, "why": "broken"})
    assert ok is False
