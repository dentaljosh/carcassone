"""Contract tests for the TIE-ARBITER plumbing in `scripts/human_anchor/play_harness.py`.

The plumbing is FLAG-GATED and OFF BY DEFAULT, so the load-bearing assertion is a
NEGATIVE one: with the flags untouched, the harness must construct the champion the
way it did before the flags existed — not "with the arbiter disabled", but with the
`tiearb` keyword ABSENT from the factory call entirely. `make_production_champion`
folds an enabled arbiter into the rust search config, and a disarmed keyword is a
no-op there today; relying on that would still be relying on it, so the contract is
tested at the CALL, where it cannot silently rot.

The four contracts:

  1. DISARMED  -> `make_production_champion` receives NO `tiearb` kwarg (all five
     construction sites in the file), i.e. a bit-for-bit unchanged champion.
  2. ARMED     -> it receives exactly the deploy shape of record
     (measurement/tiearb2_stage2_20260817/READOUT.md §4.3 `G-J4`:
     B=16, J=4, mode=argmax, salt=tiearb2-deploy-v1, eps=0.0).
  3. `--backend python` + armed -> refused AT LAUNCH (the arbiter is rust-only), the
     way eval_fair_puct refuses it, rather than per-agent deep inside a run.
  4. Every game manifest carries a `tiearb` block, ARMED OR NOT — `{"enabled": false}`
     is stamped OUT LOUD, because absent is unknown-not-zero (U-UNREADABLE) and an
     armed-but-never-fired arbiter must be distinguishable from one that fired.

Construction-level throughout: no search runs, no rust wheel is required (the factory
is stubbed), and the two full-game tests use instant first-legal-action agents.
"""
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
for _p in ("src", "scripts", "scripts/human_anchor"):
    if str(_REPO / _p) not in sys.path:
        sys.path.insert(0, str(_REPO / _p))

import env_preamble  # noqa: E402,F401  production leaf env BEFORE carcassonne_ai

from carcassonne_ai import mirror_protocol as MP  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

import play_harness as PH  # noqa: E402

# The deploy shape of record — READOUT.md §4.3 `G-J4`, ARB cell.
DEPLOY_SHAPE = {"enabled": True, "B": 16, "J": 4, "mode": "argmax",
                "salt": "tiearb2-deploy-v1", "eps": 0.0}


# --------------------------------------------------------------------------- #
# stubs                                                                        #
# --------------------------------------------------------------------------- #
class _Rs:
    """The FairAgentRs surface `_champ_tiearb_telemetry` reads."""

    def __init__(self, **over):
        self._stats = {
            "tiearb_enabled": True, "tiearb_tile_plies": 71,
            "tiearb_fired_plies": 0, "tiearb_pickchanges": 0,
            "tiearb_arms_total": 0, "tiearb_playouts_total": 0,
            "tiearb_secs": 0.0, "tiearb_errors": 0, "tiearb_first_error": None,
            "tiearb_partial_argmax": 0, "tiearb_max_plies": 0,
            "tiearb_mode": "argmax", "tiearb_b": 16, "tiearb_j": 4,
        } | over

    def stats(self):
        return dict(self._stats)


class _StubChampion:
    """A factory-built champion's shape, minus the search. Plays the first legal
    action, so a full game costs milliseconds."""

    neural_moves = heur_moves = exact_moves = n_timeouts = 0
    solver_secs = solver_nodes = 0
    latch_k = None

    def __init__(self, game, rs=None):
        self._game = game
        self.manifest = {"stub": True}        # what marks it factory-built
        if rs is not None:
            self._rs = rs

    def choose_action(self, board):
        import numpy as np

        return int(np.flatnonzero(self._game.get_valid_moves(board))[0])


@pytest.fixture()
def factory_calls(monkeypatch):
    """Intercept `make_production_champion` and record every call's kwargs."""
    from carcassonne_ai import champion_factory

    calls = []

    def _fake(mode, *, game=None, **kw):
        calls.append({"mode": mode, **kw})
        return _StubChampion(game, rs=_Rs())

    monkeypatch.setattr(champion_factory, "make_production_champion", _fake)
    return calls


# --------------------------------------------------------------------------- #
# 1. DISARMED == the pre-plumbing champion, provably                           #
# --------------------------------------------------------------------------- #
def test_disarmed_passes_no_tiearb_kwarg_at_all(factory_calls):
    """THE contract. Not `tiearb=None`, not `{"enabled": False}` — ABSENT."""
    g = Game(enable_legal_moves_cache=True)
    ex = MP.resolve_execution("rust", profile=None)
    PH._make_fair_agent(g, 8, 1, seed=1, execution=ex)
    assert len(factory_calls) == 1
    assert "tiearb" not in factory_calls[0], (
        "a disarmed run must reach the factory with NO arbiter keyword — the "
        "champion has to be bit-for-bit the pre-plumbing one")


def test_disarmed_kwargs_are_exactly_the_pre_plumbing_set(factory_calls):
    """Belt-and-braces on the same point: the whole kwarg SET is unchanged, so the
    plumbing cannot have smuggled in some other new keyword either."""
    g = Game(enable_legal_moves_cache=True)
    ex = MP.resolve_execution("rust", profile=None)
    PH._make_fair_agent(g, 8, 1, seed=1, execution=ex)
    assert set(factory_calls[0]) == {"mode", "seed", "sims", "k_dets",
                                     "exact_endgame"} | set(ex.factory_kwargs())


@pytest.fixture()
def stub_play(monkeypatch):
    """Replace the two play entry points with stubs that still CALL the ctors (so the
    factory interception sees every construction site), and record the `tiearb` they
    were handed."""
    seen = {}

    def _paired(game, deck_seed, ctor_a, ctor_b, *a, tiearb="MISSING", **k):
        seen["paired"] = tiearb
        ctor_a(), ctor_b()               # the two fair-vs-fair sites
        return []

    def _game(game, deck_seed, agents, labels, config, tiearb="MISSING"):
        seen["game"] = tiearb
        return {"manifest": {"deck_seed": int(deck_seed)}, "moves": [],
                "result": {"scores": [0, 0], "winner_seat": -1}}

    monkeypatch.setattr(PH, "play_paired", _paired)
    monkeypatch.setattr(PH, "play_game", _game)
    monkeypatch.setattr(PH, "write_record", lambda *a, **k: Path("/dev/null"))
    return seen


def test_every_main_construction_site_defaults_to_disarmed(factory_calls, stub_play):
    """The three `_make_fair_agent` call sites reachable from main() — the two
    fair-vs-fair ctors and the human-vs-AI seat — must default to the unarmed path.
    Driven THROUGH main() so a site that forgot to thread the parameter is caught by
    the recorded call, not by inspection. (The two self_test sites are covered by
    `test_self_test_sites_default_to_disarmed` + `test_self_test_threads_the_arbiter`.)"""
    assert PH.main(["--paired", "--sims", "8", "--k-dets", "1",
                    "--backend", "rust"]) == 0
    assert stub_play["paired"] is None
    assert len(factory_calls) == 2, "both fair-vs-fair ctors must have been built"

    assert PH.main(["--human", "0", "--sims", "8", "--k-dets", "1",
                    "--backend", "rust"]) == 0
    assert stub_play["game"] is None
    assert len(factory_calls) == 3
    assert all("tiearb" not in c for c in factory_calls)


def test_self_test_sites_default_to_disarmed(monkeypatch):
    """The remaining two sites live in self_test(); check main() hands it None."""
    got = {}
    monkeypatch.setattr(PH, "self_test",
                        lambda ex=None, tiearb="MISSING": (got.update(t=tiearb), 0)[1])
    assert PH.main(["--self-test", "--backend", "rust"]) == 0
    assert got["t"] is None


# --------------------------------------------------------------------------- #
# 2. ARMED passes the exact deploy shape                                       #
# --------------------------------------------------------------------------- #
def test_resolve_tiearb_defaults_are_the_deploy_shape(monkeypatch):
    """The flag DEFAULTS (read through main()'s own parser, not retyped here) must
    resolve to READOUT.md §4.3 `G-J4`'s ARB shape the moment the arm flag is set."""
    got = {}
    monkeypatch.setattr(PH, "self_test",
                        lambda ex=None, tiearb=None: (got.update(t=tiearb), 0)[1])
    assert PH.main(["--self-test", "--backend", "rust", "--tiearb-enabled"]) == 0
    assert got["t"] == DEPLOY_SHAPE


def test_resolve_tiearb_is_none_when_unarmed():
    """`None`, never `{"enabled": False}` — the caller keys keyword PRESENCE off it."""
    import argparse

    ns = argparse.Namespace(tiearb_enabled=False, tiearb_b=16, tiearb_j=4,
                            tiearb_mode="argmax", tiearb_salt="tiearb2-deploy-v1",
                            tiearb_eps=0.0)
    assert PH._resolve_tiearb(ns) is None


def test_armed_forwards_the_exact_shape_to_the_factory(factory_calls):
    g = Game(enable_legal_moves_cache=True)
    ex = MP.resolve_execution("rust", profile=None)
    PH._make_fair_agent(g, 8, 1, seed=1, execution=ex, tiearb=dict(DEPLOY_SHAPE))
    assert factory_calls[0]["tiearb"] == DEPLOY_SHAPE


def test_armed_reaches_every_main_construction_site(factory_calls, stub_play):
    arm = ["--backend", "rust", "--tiearb-enabled", "--sims", "8", "--k-dets", "1"]
    assert PH.main(["--paired", *arm]) == 0
    assert PH.main(["--human", "0", *arm]) == 0
    assert len(factory_calls) == 3
    assert all(c["tiearb"] == DEPLOY_SHAPE for c in factory_calls), (
        "every construction site must receive the resolved arbiter, not just the first")
    assert stub_play["paired"] == stub_play["game"] == DEPLOY_SHAPE, (
        "play_game/play_paired must be told what the seats were BUILT with, so the "
        "manifest can stamp it")


def test_self_test_threads_the_arbiter_into_both_of_its_ctors(factory_calls,
                                                              monkeypatch):
    """The two remaining sites. `self_test` is called for real but its play is stubbed,
    so only the construction happens."""
    monkeypatch.setattr(PH, "play_paired",
                        lambda game, seed, ca, cb, *a, **k: [ca(), cb()] and [])
    monkeypatch.setattr(PH, "write_record", lambda *a, **k: Path("/dev/null"))
    with pytest.raises(Exception):
        # self_test asserts on records it never got (play_paired is stubbed); we only
        # care that its two ctors ran, with the arbiter, before it complained.
        PH.self_test(MP.resolve_execution("rust", profile=None),
                     tiearb=dict(DEPLOY_SHAPE))
    assert len(factory_calls) == 2
    assert all(c["tiearb"] == DEPLOY_SHAPE for c in factory_calls)


def test_flag_values_are_honoured_not_hardcoded(monkeypatch):
    """A non-default salt/mode/B/J must travel — otherwise the RND control cell and
    any future rung would silently run the ARB shape."""
    got = {}
    monkeypatch.setattr(PH, "self_test",
                        lambda ex=None, tiearb=None: (got.update(t=tiearb), 0)[1])
    assert PH.main(["--self-test", "--backend", "rust", "--tiearb-enabled",
                    "--tiearb-mode", "random", "--tiearb-b", "8", "--tiearb-j", "2",
                    "--tiearb-salt", "not-the-deploy-salt",
                    "--tiearb-eps", "1e-9"]) == 0
    assert got["t"] == {"enabled": True, "B": 8, "J": 2, "mode": "random",
                        "salt": "not-the-deploy-salt", "eps": 1e-9}


# --------------------------------------------------------------------------- #
# 3. the rust-only guard fires AT LAUNCH                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("extra", [[], ["--human", "0"], ["--self-test"]])
def test_python_backend_plus_armed_arbiter_fails_at_launch(extra, capsys):
    """argparse `ap.error` => SystemExit(2), BEFORE any agent is constructed and
    before a single move is played (precedent: eval_fair_puct's identical refusal)."""
    with pytest.raises(SystemExit) as ei:
        PH.main(["--backend", "python", "--tiearb-enabled", *extra])
    assert ei.value.code == 2
    assert "RUST-ONLY" in capsys.readouterr().err


def test_rust_backend_plus_armed_arbiter_is_accepted(monkeypatch):
    monkeypatch.setattr(PH, "self_test", lambda ex=None, tiearb=None: 0)
    assert PH.main(["--self-test", "--backend", "rust", "--tiearb-enabled"]) == 0


def test_inherit_backend_resolving_to_rust_is_accepted(monkeypatch):
    """`--backend inherit`/`auto` is the DEFAULT and today resolves to rust; the guard
    must read the RESOLVED backend, not the flag string."""
    if not MP.resolve_execution("inherit", profile="desktop").is_rust:
        pytest.skip("factory default no longer resolves to rust on this box")
    monkeypatch.setattr(PH, "self_test", lambda ex=None, tiearb=None: 0)
    assert PH.main(["--self-test", "--tiearb-enabled"]) == 0


def test_python_backend_unarmed_is_untouched(monkeypatch):
    """The guard must not have made `--backend python` harder to use unarmed."""
    monkeypatch.setattr(PH, "self_test", lambda ex=None, tiearb=None: 0)
    assert PH.main(["--self-test", "--backend", "python"]) == 0


# --------------------------------------------------------------------------- #
# 4. telemetry: the block is ALWAYS stamped                                    #
# --------------------------------------------------------------------------- #
def test_block_is_explicit_false_when_disarmed():
    g = Game(enable_legal_moves_cache=True)
    assert PH._game_tiearb_block({0: _StubChampion(g)}, None) == {"enabled": False}
    assert PH._game_tiearb_block({0: _StubChampion(g)},
                                 {"enabled": False, "B": 16}) == {"enabled": False}


def test_block_carries_the_full_liveness_read_when_armed():
    g = Game(enable_legal_moves_cache=True)
    rs = _Rs(tiearb_fired_plies=7, tiearb_pickchanges=3, tiearb_arms_total=21,
             tiearb_playouts_total=336, tiearb_secs=1.25)
    block = PH._game_tiearb_block({1: _StubChampion(g, rs=rs)}, dict(DEPLOY_SHAPE))
    assert block["enabled"] is True and block["config"] == DEPLOY_SHAPE
    t = block["seats"]["1"]
    # `fires` and `fired_plies` are the same number under both spellings, on purpose.
    assert t["fires"] == t["fired_plies"] == 7
    assert (t["pickchanges"], t["arms_total"], t["playouts_total"]) == (3, 21, 336)
    assert t["secs"] == 1.25 and t["B"] == 16 and t["J"] == 4 and t["mode"] == "argmax"
    # U-UNREADABLE guards: these must be PRESENT, never inferred from absence.
    for k in ("partial_argmax", "errors", "max_plies", "tile_plies", "first_error"):
        assert k in t


def test_armed_but_never_fired_is_distinguishable_from_armed_and_fired():
    """The whole point of the block: three states, three readable records."""
    g = Game(enable_legal_moves_cache=True)
    dead = PH._game_tiearb_block({0: _StubChampion(g, rs=_Rs(tiearb_fired_plies=0))},
                                 dict(DEPLOY_SHAPE))
    live = PH._game_tiearb_block({0: _StubChampion(g, rs=_Rs(tiearb_fired_plies=9))},
                                 dict(DEPLOY_SHAPE))
    off = PH._game_tiearb_block({0: _StubChampion(g)}, None)
    assert off["enabled"] is False
    assert dead["enabled"] is True and dead["seats"]["0"]["fires"] == 0
    assert live["seats"]["0"]["fires"] == 9
    assert off != dead != live


def test_armed_champion_without_rust_raises_rather_than_stamping_none():
    """A wiring bug must be LOUD. A silent `None` would let a champion that never
    arbitrated a ply be graded as one that did (the J13 failure mode)."""
    g = Game(enable_legal_moves_cache=True)
    with pytest.raises(RuntimeError, match="rust-only"):
        PH._game_tiearb_block({0: _StubChampion(g)}, dict(DEPLOY_SHAPE))


def test_armed_but_rust_reports_the_knob_dropped_raises():
    g = Game(enable_legal_moves_cache=True)
    champ = _StubChampion(g, rs=_Rs(tiearb_enabled=False))
    with pytest.raises(RuntimeError, match="tiearb_enabled=False"):
        PH._game_tiearb_block({0: champ}, dict(DEPLOY_SHAPE))


def test_armed_game_with_no_champion_seat_raises():
    g = Game(enable_legal_moves_cache=True)
    human = PH.HumanCLIAgent(g)          # no `.manifest` -> not a factory champion
    with pytest.raises(RuntimeError, match="no seat"):
        PH._game_tiearb_block({0: human}, dict(DEPLOY_SHAPE))


def test_human_seat_is_skipped_not_probed():
    """A human seat cannot carry an arbiter; it must be skipped silently, not raise."""
    g = Game(enable_legal_moves_cache=True)
    agents = {0: PH.HumanCLIAgent(g), 1: _StubChampion(g, rs=_Rs())}
    block = PH._game_tiearb_block(agents, dict(DEPLOY_SHAPE))
    assert set(block["seats"]) == {"1"}


# --- the same, through a real (instant) game, so the MANIFEST is what is checked --- #
def _play_instant_game(tiearb, rs=None):
    g = Game(enable_legal_moves_cache=True)
    agents = {0: _StubChampion(g, rs=rs), 1: _StubChampion(g, rs=rs)}
    return PH.play_game(g, 777_000_001, agents, {0: "a", 1: "b"}, {"t": 1},
                        tiearb=tiearb)


def test_manifest_carries_the_block_disarmed():
    rec = _play_instant_game(None)
    assert rec["manifest"]["tiearb"] == {"enabled": False}, (
        "a disarmed game must say so OUT LOUD — absent is unknown-not-zero")


def test_manifest_carries_the_block_armed():
    rec = _play_instant_game(dict(DEPLOY_SHAPE), rs=_Rs(tiearb_fired_plies=4))
    block = rec["manifest"]["tiearb"]
    assert block["enabled"] is True and block["config"] == DEPLOY_SHAPE
    assert set(block["seats"]) == {"0", "1"}
    assert block["seats"]["0"]["fires"] == 4


def test_the_block_is_covered_by_the_record_signature():
    """The manifest signature is computed over the manifest INCLUDING the block, so a
    stripped/edited arbiter record breaks the tamper-evident signature."""
    import _common as C

    rec = _play_instant_game(dict(DEPLOY_SHAPE), rs=_Rs(tiearb_fired_plies=4))
    m = dict(rec["manifest"])
    sig = m.pop("signature")
    assert C.sha256_of({"manifest": m, "moves": rec["moves"]}) == sig
    m["tiearb"] = {"enabled": False}          # tamper
    assert C.sha256_of({"manifest": m, "moves": rec["moves"]}) != sig
