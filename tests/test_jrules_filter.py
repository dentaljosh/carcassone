"""J-RULES AS ROOT FILTERS (surface C) — contract tests.

Design of record: measurement/jrules_filters_20260814/DESIGN.md.
Production path: carc_core::fair::jrules_filter, bound in
FairAgent::pimc_move behind SearchConfig.jrules_filter_mask != 0 (RUST-ONLY;
the python search path fail-louds). Reference mirror:
carcassonne_ai.jrules_filter — what the parity tests here compare against
carc_rs.MirrorState.jrules_filter_probe on replayed games.

⚠️ PER-BOX REBUILD FOOTGUN, STATED LOUDLY: the rust-gated tests below SKIP —
they do not fail — when the installed `carc_rs` wheel predates surface C
(no `jrules_filter_probe` / no `jrules_filter_mask` kwarg). A skip on a box
that is about to run a cell means THE CELL WOULD SILENTLY RUN
CHAMPION-VS-CHAMPION IF THE PLUMBING WERE NOT FAIL-CLOSED — rebuild the wheel
on that box (`maturin build --release` in rust/carc/carc-py + reinstall)
before launching anything. The fail-closed guard itself (stale wheel + nonzero
mask ⇒ TypeError in rust_agent.search_config_rs) does not need the new wheel.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import jrules_filter as jf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.joshua_bot import PRESETS  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. constants are the bot's, not new tunables                                 #
# --------------------------------------------------------------------------- #
def test_constants_match_joshua_bot():
    p = PRESETS["current"]
    assert jf.JF_J3_RESERVE_FLOOR == p.j3_reserve_floor
    assert jf.JF_J3_ENDGAME_RELEASE_K == p.j3_endgame_release_k
    assert jf.JF_EARLY_FARM_BLOCK_FRAC == p.early_farm_block_frac
    assert jf.JF_J9_CLOISTER_BLOCK_FRAC == p.j9_cloister_block_frac
    assert jf.JF_J9_MIN_SURROUNDING == p.j9_min_surrounding
    # F-J3's pivotal-overcommit exemption is FROZEN OFF because the
    # tournament-selected preset carries it off; if the preset ever flips,
    # this test must force the filter design to be revisited, not silently pass.
    assert p.j8_break_reserve_floor is False
    # F-J9 is opt-in OFF in the bot ⇒ it must not be in the `current` stack.
    assert p.j9_avoid_cloisters is False
    assert jf.JF_CURRENT == jf.JF_END | jf.JF_J10 | jf.JF_J3 == 11
    assert jf.JF_ALL == 15


def test_constants_match_flat_leaf_k0():
    assert jf.JF_K0 == flat_leaf._JR_K0 == 72.0


def test_mask_filters_names():
    assert jf.mask_filters(11) == ["f_end", "f_j10", "f_j3"]
    assert jf.mask_filters(15) == ["f_end", "f_j10", "f_j9", "f_j3"]
    assert jf.mask_filters(0) == []


# --------------------------------------------------------------------------- #
# 2. config knobs: validation + fail-loud python path + manifest               #
# --------------------------------------------------------------------------- #
def test_config_validates_mask_and_min_keep():
    HeuristicPriorConfig(jrules_filter_mask=0)          # OFF is valid here
    HeuristicPriorConfig(jrules_filter_mask=11)
    HeuristicPriorConfig(jrules_filter_mask=15)
    with pytest.raises(ValueError, match="jrules_filter_mask"):
        HeuristicPriorConfig(jrules_filter_mask=16)
    with pytest.raises(ValueError, match="jrules_filter_mask"):
        HeuristicPriorConfig(jrules_filter_mask=-1)
    with pytest.raises(ValueError, match="jrules_filter_min_keep"):
        HeuristicPriorConfig(jrules_filter_min_keep=0)


def test_python_search_path_fail_louds_on_set_mask():
    g = Game(enable_legal_moves_cache=True)
    with pytest.raises(NotImplementedError, match="rust-only"):
        make_heuristic_prior_evaluator(
            g, HeuristicPriorConfig(jrules_filter_mask=11))
    # mask 0 (the champion) builds fine.
    make_heuristic_prior_evaluator(g, HeuristicPriorConfig())


def test_as_manifest_carries_resolved_filter_knobs():
    m = HeuristicPriorConfig(jrules_filter_mask=11,
                             jrules_filter_min_keep=2).as_manifest()
    assert m["jrules_filter_mask"] == 11
    assert m["jrules_filter_min_keep"] == 2
    m0 = HeuristicPriorConfig().as_manifest()
    assert m0["jrules_filter_mask"] == 0      # the champion stamps 0, visibly


def test_search_config_rs_forwards_kwargs_only_when_live(monkeypatch):
    """The fail-closed stale-wheel mechanism: mask 0 must NOT pass the surface-C
    kwargs (so an old wheel serves the champion unchanged); a nonzero mask MUST
    pass them (so an old wheel raises TypeError instead of silently dropping
    the filter)."""
    import types

    from carcassonne_ai import rust_agent

    captured = {}

    class _FakeCfg:
        def __init__(self, *a, **kw):
            captured.clear()
            captured.update(kw)

    fake = types.SimpleNamespace(SearchConfigRs=_FakeCfg,
                                 LeafConfigRs=lambda *a, **kw: None)
    monkeypatch.setitem(sys.modules, "carc_rs", fake)
    monkeypatch.setattr(rust_agent, "leaf_config_rs", lambda cfg: None)

    rust_agent.search_config_rs(HeuristicPriorConfig(), sims=8)
    assert not any(k.startswith("jrules_filter") for k in captured)
    rust_agent.search_config_rs(
        HeuristicPriorConfig(jrules_filter_mask=11, jrules_filter_min_keep=2),
        sims=8)
    assert captured["jrules_filter_mask"] == 11
    assert captured["jrules_filter_min_keep"] == 2


# --------------------------------------------------------------------------- #
# 3. python mirror semantics on synthetic roots                                #
# --------------------------------------------------------------------------- #
def _drive_to_meeple_root(seed: int, rng_seed: int = 12345):
    """Replay a seeded game with a seeded random policy until a meeple-phase
    root with >1 legal action."""
    import numpy as np

    random.seed(seed)
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    rng = random.Random(rng_seed)
    for _ in range(400):
        legal = np.flatnonzero(g.get_valid_moves(b)).tolist()
        if b.state.phase.value == "meeples" and len(legal) > 1:
            return g, b
        b, _ = g.get_next_state(b, int(rng.choice(legal)))
    raise AssertionError("no meeple root reached")


def test_filter_is_inapplicable_on_tile_phase_and_mask0():
    import numpy as np

    random.seed(7)
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    assert b.state.phase.value == "tiles"
    fo = jf.jrules_root_filter(g, b, jf.JF_ALL)
    assert not fo.applicable
    assert fo.kept == np.flatnonzero(g.get_valid_moves(b)).tolist()
    g2, b2 = _drive_to_meeple_root(7)
    fo2 = jf.jrules_root_filter(g2, b2, 0)
    assert not fo2.applicable and fo2.dropped == []


def test_f_j10_drops_early_farmers_and_guard_yields():
    """On an early meeple root offering a farmer claim: JF_J10 drops every
    farmer action; min_keep == len(legal) forces a yield instead."""
    from carcassonne_ai.action_space import meeple_farmer_base, meeple_pass_index
    from carcassonne_ai.joshua_bot import k_remaining

    found = False
    for seed in (7, 1234, 99, 555, 31337, 42):
        g, b = _drive_to_meeple_root(seed)
        w = g.window_size
        fb, mp = meeple_farmer_base(w), meeple_pass_index(w)
        import numpy as np
        legal = np.flatnonzero(g.get_valid_moves(b)).tolist()
        farmers = [a for a in legal if fb <= a < mp]
        if not farmers or k_remaining(b.state) <= 40:
            continue
        fo = jf.jrules_root_filter(g, b, jf.JF_J10)
        assert fo.applicable and fo.fires[1]
        assert all(a in fo.dropped for a in farmers)
        assert mp in fo.kept                       # PASS survives F-J10
        # the never-empty guard: an impossible min_keep must yield, not empty
        fo2 = jf.jrules_root_filter(g, b, jf.JF_J10, min_keep=len(legal))
        assert fo2.kept == legal and fo2.dropped == []
        assert fo2.yields[1] and not fo2.fires[1]
        found = True
        break
    assert found, "no early meeple root with a legal farmer claim found"


def test_kept_dropped_partition_preserves_order():
    import numpy as np

    for seed in (7, 99, 555):
        g, b = _drive_to_meeple_root(seed)
        legal = np.flatnonzero(g.get_valid_moves(b)).tolist()
        fo = jf.jrules_root_filter(g, b, jf.JF_ALL)
        assert sorted(fo.kept + fo.dropped) == legal
        assert fo.kept == [a for a in legal if a not in fo.dropped]


def test_mask_bits_outside_jf_all_raise():
    g, b = _drive_to_meeple_root(7)
    with pytest.raises(ValueError, match="outside JF_ALL"):
        jf.jrules_root_filter(g, b, 16)


# --------------------------------------------------------------------------- #
# 4. rust-gated: parity + the FairAgentRs binding                              #
# --------------------------------------------------------------------------- #
def _carc_rs_with_surface_c():
    carc_rs = pytest.importorskip("carc_rs")
    if not hasattr(carc_rs.MirrorState, "jrules_filter_probe"):
        pytest.skip(
            "carc_rs wheel PREDATES J-rules root filters surface C — the "
            "per-box rebuild footgun. Rebuild before any cell on this box: "
            "`maturin build --release` in rust/carc/carc-py + reinstall. "
            "(The stale-wheel path itself is FAIL-CLOSED: a nonzero "
            "jrules_filter_mask raises TypeError in search_config_rs.)")
    return carc_rs


def _lockstep(seed: int, carc_rs, max_ply: int = 90):
    """Replay one seeded game in BOTH engines; yield (ply, b, game, mirror)."""
    import numpy as np

    random.seed(seed)
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    m = carc_rs.MirrorState.from_seed(str(seed))
    rng = random.Random(9_000_000 + seed)
    for ply in range(max_ply):
        legal_py = np.flatnonzero(g.get_valid_moves(b)).tolist()
        legal_rs = sorted(m.legal_actions())
        assert legal_py == legal_rs, f"legal-mask divergence at ply {ply}"
        yield ply, b, g, m
        a = int(rng.choice(legal_py))
        b, _ = g.get_next_state(b, a)
        m.advance(a)


@pytest.mark.parametrize("seed", [28000000001, 28000000007])
@pytest.mark.parametrize("mask", [11, 15, 2, 8])
def test_rust_python_filter_parity_on_replayed_games(seed, mask):
    """The parity gate for surface C: rust probe vs the python reference
    mirror on real replayed positions — applicability, kept/dropped sets and
    the per-filter fire/yield flags, at every ply of the replay."""
    carc_rs = _carc_rs_with_surface_c()
    compared = applicable = 0
    for _ply, b, g, m in _lockstep(seed, carc_rs):
        probe = m.jrules_filter_probe(mask)
        fo = jf.jrules_root_filter(g, b, mask)
        assert probe["applicable"] == fo.applicable, (seed, _ply)
        assert list(probe["kept"]) == fo.kept, (seed, _ply)
        assert list(probe["dropped"]) == fo.dropped, (seed, _ply)
        assert dict(probe["fires"]) == dict(zip(jf.JF_FILTER_NAMES, fo.fires))
        assert dict(probe["yields"]) == dict(zip(jf.JF_FILTER_NAMES, fo.yields))
        compared += 1
        applicable += int(fo.applicable)
    assert compared >= 60, f"parity corpus too thin ({compared} plies)"
    assert applicable >= 10, f"too few applicable plies ({applicable})"


def _fair(carc_rs, seed_game: str, **cfg_kw):
    from carcassonne_ai import rust_agent
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    leaf = rust_agent.leaf_config_rs(DEFAULT_CONFIG)
    scfg = carc_rs.SearchConfigRs(leaf, 48, 1.5, 5.0, 15.0, 15.0,
                                  "float", "visits", None, 1.0, True,
                                  "glibc_fma", **cfg_kw)
    a = carc_rs.FairAgentRs(scfg, k_dets=4, seed=0)
    a.start_game_from_seed(seed_game)
    return a


def test_fair_agent_mask0_with_moved_min_keep_is_bit_identical():
    """The surface-C analogue of the dose-0 control, through the pyo3 layer:
    mask 0 with a deliberately moved min_keep must reproduce the champion's
    pooled floats bit-for-bit."""
    carc_rs = _carc_rs_with_surface_c()
    base = _fair(carc_rs, "28000000000")
    moved = _fair(carc_rs, "28000000000",
                  jrules_filter_mask=0, jrules_filter_min_keep=7)
    for _ in range(30):
        la = base.legal_actions()
        a = la[len(la) // 2]
        base.advance(a)
        moved.advance(a)
    a1 = base.choose_action(5)
    a2 = moved.choose_action(5)
    assert a1 == a2
    p1 = base.last_move()["pooled"]
    p2 = moved.last_move()["pooled"]
    assert p1 == p2, "mask-0 surface C changed a pooled float"
    s = moved.stats()
    assert s["jf_dropped_total"] == 0
    assert s["jrules_filter_mask"] == 0


def test_fair_agent_live_filter_restricts_the_root_and_counts():
    """With mask JF_CURRENT live: find a replay ply where the probe drops
    something, then the agent's move must be in the KEPT set, its pooled pool
    must contain no dropped action, and last_move/stats must record the drop."""
    carc_rs = _carc_rs_with_surface_c()
    live = _fair(carc_rs, "28000000000", jrules_filter_mask=11)
    ref = _fair(carc_rs, "28000000000")  # drives the same replay, unused picks
    del ref
    rng = random.Random(424242)
    tested = False
    for ply in range(120):
        if live.is_terminal():
            break
        probe = live.jrules_filter_probe(11)
        if probe["applicable"] and probe["dropped"]:
            act = live.choose_action(ply)
            assert act in list(probe["kept"])
            lm = live.last_move()
            assert list(lm["jf_dropped"]) == list(probe["dropped"])
            pooled_actions = [p[0] for p in lm["pooled"]]
            assert not set(pooled_actions) & set(probe["dropped"])
            s = live.stats()
            assert s["jf_dropped_total"] >= len(probe["dropped"])
            assert any(v for _n, v in s["jf_fires"])
            tested = True
            break
        la = live.legal_actions()
        live.advance(int(rng.choice(la)))
    assert tested, "no ply where JF_CURRENT bites was reached in the replay"


def test_search_config_rs_validates_filter_knobs():
    carc_rs = _carc_rs_with_surface_c()
    from carcassonne_ai import rust_agent
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    leaf = rust_agent.leaf_config_rs(DEFAULT_CONFIG)

    def _cfg(**kw):
        return carc_rs.SearchConfigRs(leaf, 8, 1.5, 5.0, 15.0, 15.0,
                                      "float", "visits", None, 1.0, True,
                                      "glibc_fma", **kw)

    c = _cfg(jrules_filter_mask=11, jrules_filter_min_keep=2)
    assert c.jrules_filter == (11, 2)
    assert "jrules_filter_mask=11" in repr(c)
    c0 = _cfg()
    assert c0.jrules_filter == (0, 1)
    assert "jrules_filter" not in repr(c0)  # champion repr byte-stable
    with pytest.raises(ValueError, match="jrules_filter_mask"):
        _cfg(jrules_filter_mask=16)
    with pytest.raises(ValueError, match="jrules_filter_min_keep"):
        _cfg(jrules_filter_mask=11, jrules_filter_min_keep=0)
