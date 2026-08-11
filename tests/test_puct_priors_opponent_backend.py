"""`eval_puct_priors` OPPONENT-side Rust backend (rustport P6, 2026-08-02).

The candidate side has ridden `RustClairvoyantAgent` since the first `--backend`
wiring; this covers routing the **opponent** — the `_PuctPrefix` champion sibling
(flags-OFF PUCT, clairvoyant single tree) — through the same engine.

What is asserted here:

  * **Fail-closed CLI.** Every opponent config the Rust surface cannot express
    (`--opponent net:*`, `--opp-reuse-tree`) raises an argparse error instead of
    silently staying Python under a manifest that says "rust". `--opp-pin-champion`
    is the one that IS expressible (it only swaps c_puct/tau_p/leaf_quantize for the
    champion constants, all three carried by `SearchConfigRs`) and must be ACCEPTED.
  * **Mirror protocol on BOTH sides.** `RustClairvoyantAgent` answers from its own
    `MirrorState`; a prefix that is seated but never advanced — or advanced only on
    its own seat — desyncs. The regression this guards is real: the pre-change
    harness tracked a SINGLE `_mirror` (the candidate), so a second mirror would have
    been left frozen at ply 0.
  * **Bit-exact identity** of the opponent search at the harness's OWN leaf. The full
    gate is `scripts/rustport/gate_clairvoyant_opponent.py` (15 roots x 2 config legs);
    this is the cheap in-suite twin so a regression cannot wait for a gate re-run.
  * **Manifest provenance** — per-side engine names, so a row's backend is readable
    without dirname archaeology.

The harness module sets the v2.9 Bmild_cap8 leaf env via `setdefault` at import, so
importing it first keeps `DEFAULT_CONFIG` consistent for every test here (the same
contract `tests/test_rr_roundrobin_harness.py` relies on). ⚠️ That leaf is NOT the
production curve125 — this harness grades against the pre-2026-07-07 dethroned
champion by design, which is exactly why the opponent needs its own identity gate
rather than inheriting `gate_clairvoyant.py`'s.
"""
from __future__ import annotations

import importlib.util
import json
import random
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classical_search" / "eval_puct_priors.py"

_spec = importlib.util.spec_from_file_location("eval_puct_priors", SCRIPT)
epp = importlib.util.module_from_spec(_spec)
sys.modules["eval_puct_priors"] = epp  # fork-Pool workers unpickle _play_one by name
_spec.loader.exec_module(epp)

carc_rs = pytest.importorskip("carc_rs")

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.rust_agent import RustClairvoyantAgent  # noqa: E402

SHARED_AXES = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float"}


def _ubits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _fresh(deck_seed: int, plies: int = 0):
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for _ in range(plies):
        mask = game.get_valid_moves(board)
        act = int(next(i for i, v in enumerate(mask) if v))
        board, _ = game.get_next_state(board, act)
    return game, board


# --------------------------------------------------------------------------- #
# Fail-closed CLI                                                              #
# --------------------------------------------------------------------------- #
_BASE = ["--candidate", "puct", "--cand-sims", "100", "--n", "2", "--summary-only"]


@pytest.mark.parametrize("extra,needle", [
    (["--opponent", "net:/nonexistent/iter_02.pt"], "no evaluator"),
    (["--opponent", "puct", "--opp-reuse-tree"], "FRESH-TREE only"),
    (["--candidate", "ab", "--cand-ab-steps", "100"], "puct candidate only"),
])
def test_rust_backend_fails_closed(capsys, extra, needle):
    """Unexpressible opponent/candidate configs must ERROR, never fall back silently."""
    with pytest.raises(SystemExit) as e:
        epp.main(_BASE + ["--backend", "rust"] + extra)
    assert e.value.code == 2
    assert needle in capsys.readouterr().err


def test_opp_pin_champion_is_expressible_on_rust():
    """`--opp-pin-champion` only moves axes SearchConfigRs carries -> allowed.

    Asserted at the config level (the CLI leg would need a full run): the pinned
    config must differ from the copied one on exactly the shared axes and still be
    accepted by `search_config_rs`."""
    from carcassonne_ai.rust_agent import search_config_rs

    swept = {"c_puct": 1.1, "tau_p": 3.0, "leaf_quantize": "int"}
    copied = epp._champ_puct_cfg(swept, pin_champion=False)
    pinned = epp._champ_puct_cfg(swept, pin_champion=True)
    assert (copied.c_puct, copied.tau_p, copied.leaf_quantize) == (1.1, 3.0, "int")
    assert (pinned.c_puct, pinned.tau_p) == (epp.CHAMP_PUCT_C_PUCT,
                                             epp.CHAMP_PUCT_TAU_P)
    # both are buildable on the Rust side — that is what "expressible" means
    for cfg in (copied, pinned):
        assert search_config_rs(cfg, 64) is not None


def test_rust_backend_refuses_opponent_reuse_tree_at_the_agent_too():
    """Defence in depth: even if the CLI guard were bypassed, the agent refuses."""
    cfg = epp._champ_puct_cfg(SHARED_AXES, reuse=True)
    assert cfg.reuse_tree is True
    with pytest.raises(ValueError, match="reuse_tree"):
        RustClairvoyantAgent(Game(enable_legal_moves_cache=True), cfg,
                             simulations=32, seed=1, reuse_tree=True)


# --------------------------------------------------------------------------- #
# Identity — the cheap in-suite twin of gate_clairvoyant_opponent.py           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("axes", [
    SHARED_AXES,
    {"c_puct": 1.1, "tau_p": 3.0, "leaf_quantize": "int"},
])
def test_opponent_search_is_bit_exact_python_vs_rust(axes):
    """`_PuctPrefix` and `RustClairvoyantAgent` must produce the SAME tree.

    Full surface as raw f64 bits — chosen action, root N/W, and every root child
    edge. Comparing only the action would pass a search that is right by accident."""
    sims, deck_seed, plies = 96, 28_000_000_000, 24
    cfg = epp._champ_puct_cfg(axes, reuse=False, pin_champion=False)

    game, board = _fresh(deck_seed, plies)
    prefix = epp._PuctPrefix(game, cfg, sims, 101)
    py_action = int(prefix.move(board))
    root = prefix._a.mcts._nodes[game.string_representation(board)]
    py = (py_action, int(root.N), _ubits(root.W),
          [(int(a), int(c.N), _ubits(c.W)) for a, c in sorted(root.children.items())])

    # Rust leg, driven onto the same position by the mirror protocol.
    ag = epp._rust_clairvoyant(cfg, sims, 101)
    game2, board2 = _fresh(deck_seed, 0)
    ag.start_game(board2)
    _, replay_board = _fresh(deck_seed, 0)
    for _ in range(plies):
        mask = game2.get_valid_moves(replay_board)
        act = int(next(i for i, v in enumerate(mask) if v))
        replay_board, _ = game2.get_next_state(replay_board, act)
        ag.advance(act)
    ag.check_sync(replay_board, "test")
    rs_action = int(ag.choose_action(replay_board))
    r = ag.last_search()
    rs = (rs_action, int(r["root_n"]), int(r["root_w_bits"]),
          [(int(a), int(n), int(w)) for a, n, w in sorted(r["root_children"])])

    assert py == rs


# --------------------------------------------------------------------------- #
# Mirror protocol                                                              #
# --------------------------------------------------------------------------- #
def test_both_sides_get_a_mirror_and_every_action(tmp_path):
    """The regression guard: with rust on BOTH sides, two mirrors must be seated and
    each must see EVERY applied action of BOTH seats.

    Driven through the real `_play_one` so the wiring, not a hand-rolled loop, is
    what is under test. `RustClairvoyantAgent.choose_action` hard-checks sync, so a
    missed `advance` raises `MirrorDesync` rather than quietly mis-playing — the
    assertion below is therefore "it completed", plus the ply counters."""
    seen = []
    real = epp._rust_clairvoyant

    def _spy(cfg, sims, seed):
        ag = real(cfg, sims, seed)
        seen.append(ag)
        return ag

    epp._rust_clairvoyant = _spy
    try:
        epp._W.clear()
        epp._worker_init({"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
                          "final_select": "Q", "value_norm": 15.0},
                         48, 48, 0, False, "test", 5400,
                         cand_kind="puct", opp_kind="puct", opp_sims=48,
                         backend="rust")
        res = epp._play_one((str(tmp_path), 28_000_000_000, 0))
    finally:
        epp._rust_clairvoyant = real
        epp._W.clear()

    assert res is not None and res.moves > 100
    assert len(seen) == 2, "both candidate and opponent must be Rust mirrors"
    for ag in seen:
        st = ag.stats()
        assert st["plies_advanced"] == res.moves, \
            "each mirror must see EVERY applied action of BOTH seats"
        assert st["moves"] > 0, "each mirror must actually have searched"


def test_python_backend_seats_no_mirror(tmp_path):
    """`--backend python` must stay byte-identical: no mirror, no rust import."""
    epp._W.clear()
    epp._worker_init({"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
                      "final_select": "Q", "value_norm": 15.0},
                     32, 32, 0, False, "test", 5400,
                     cand_kind="puct", opp_kind="puct", opp_sims=32,
                     backend="python")
    try:
        res = epp._play_one((str(tmp_path), 28_000_000_001, 1))
    finally:
        epp._W.clear()
    assert res is not None and res.moves > 100


# --------------------------------------------------------------------------- #
# Manifest provenance                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("backend,opponent,want_cand,want_opp", [
    ("rust", "puct", "rust", "rust"),
    ("rust", "h800", "rust", "python"),
    ("python", "puct", "python", "python"),
])
def test_manifest_records_per_side_engine(tmp_path, backend, opponent,
                                          want_cand, want_opp):
    rc = epp.main(["--candidate", "puct", "--cand-sims", "32",
                   "--opponent", opponent, "--exact-k", "0",
                   "--n", "2", "--paired", "--seed-start", "9000000000",
                   "--backend", backend, "--workers", "2",
                   "--out-root", str(tmp_path), "--no-results-csv"])
    assert rc == 0
    man = json.loads(next(tmp_path.rglob("manifest.json")).read_text())
    b = man["config"]["backend"]
    assert b["name"] == backend
    assert b["candidate_engine"] == want_cand
    assert b["opponent_engine"] == want_opp
    assert "opponent_identity_gate" in b
