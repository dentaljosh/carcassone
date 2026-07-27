"""Desktop tests for the Android Python bridge (``android/app/src/main/python``).

Everything here runs at a TINY budget (k1 x 8-16 sims) — this suite proves WIRING, not
strength. The one test that matters most is ``test_bundle_runs_standalone``: it syncs the
on-device bundle into a tmpdir and plays through it in a subprocess with the repo's
``src/`` absent from the import path, which is the only way a module missing from
``sync_python.py``'s table shows up before the APK is built.

    .venv/bin/python -m pytest tests/android/ -x -q
"""
from __future__ import annotations

import copy
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

import android_bridge as B
import sync_python

REPO = Path(__file__).resolve().parents[2]
BRIDGE_DIR = REPO / "android" / "app" / "src" / "main" / "python"

TINY = {"sims": 8, "k_dets": 1, "verify": False}


# --------------------------------------------------------------------------- #
# helpers                                                                       #
# --------------------------------------------------------------------------- #
def j(s: str) -> dict:
    assert isinstance(s, str), f"bridge must return a JSON string, got {type(s)}"
    return json.loads(s)


def ok(s: str) -> dict:
    d = j(s)
    assert d.get("ok") is True, f"bridge call failed: {d}"
    return d


def new(**cfg) -> dict:
    base = {"seed": 5, "human_player": 0, "opponent": "tier1"}
    base.update(cfg)
    return ok(B.new_game(json.dumps(base)))


STATE_KEYS = {
    "ok", "schema", "generation", "phase", "turn", "current_player", "human_player",
    "ai_player", "is_human_turn", "scores", "meeples_free", "deck_remaining",
    "tiles_remaining", "next_tile", "board", "meeples", "legal", "opponent",
    "opponent_name", "budget_note", "ai_last_tile", "ai_last_move", "is_terminated",
    "n_actions",
}
LEGAL_KEYS = {"tile_cells", "meeple_slots", "meeple_target", "tile_pass_id",
              "meeple_pass_id", "action_ids"}


def assert_state_schema(st: dict) -> None:
    missing = STATE_KEYS - set(st)
    assert not missing, f"state is missing keys: {sorted(missing)}"
    assert st["schema"] == B.STATE_SCHEMA
    assert st["phase"] in ("tiles", "meeples")
    assert isinstance(st["scores"], list) and len(st["scores"]) == 2
    assert isinstance(st["meeples_free"], list) and len(st["meeples_free"]) == 2
    assert st["current_player"] in (0, 1)
    assert st["human_player"] in (0, 1)
    assert st["ai_player"] == 1 - st["human_player"]
    assert isinstance(st["deck_remaining"], int)
    assert LEGAL_KEYS <= set(st["legal"])
    # Every id must survive JSON as a NUMBER — a numpy scalar would have gone through
    # json's default=str and silently reached Kotlin as a string.
    assert all(isinstance(i, int) for i in st["legal"]["action_ids"])
    for cell in st["legal"]["tile_cells"]:
        assert set(cell) == {"row", "col", "rotations", "action_ids"}
        assert len(cell["rotations"]) == len(cell["action_ids"]) >= 1
        assert all(0 <= r < 4 for r in cell["rotations"])
        assert all(isinstance(i, int) for i in cell["action_ids"])
        assert isinstance(cell["row"], int) and isinstance(cell["col"], int)
    for slot in st["legal"]["meeple_slots"]:
        assert {"action_id", "side", "type", "terrain"} <= set(slot)
        assert isinstance(slot["action_id"], int)
        assert slot["side"] in B.MEEPLE_OFFSET_RATIO
        assert slot["type"] in ("normal", "farmer")
    assert all(isinstance(x, int) for x in st["scores"] + st["meeples_free"])
    for tile in st["board"]:
        assert {"row", "col", "image", "turns"} <= set(tile)
        assert 0 <= tile["turns"] < 4
        assert isinstance(tile["row"], int) and isinstance(tile["col"], int)
        assert tile["image"], "every placed tile needs an art filename"
    for m in st["meeples"]:
        assert {"player", "row", "col", "side", "type"} <= set(m)
        assert m["player"] in (0, 1)
        assert m["side"] in B.MEEPLE_OFFSET_RATIO
        assert len(m["offset_ratio"]) == 2
    if st["next_tile"] is not None:
        assert {"image", "turns", "description"} <= set(st["next_tile"])


def play_out(st: dict, *, human_pick=None, max_plies: int = 400) -> dict:
    """Drive a bridge game to termination. ``human_pick(state) -> action_id``."""
    human_pick = human_pick or (lambda s: s["legal"]["action_ids"][0])
    plies = 0
    while not st["is_terminated"]:
        plies += 1
        assert plies <= max_plies, "game did not terminate"
        if st["is_human_turn"]:
            st = ok(B.apply_action(human_pick(st)))
        else:
            st = ok(B.ai_move(st["generation"]))
    return st


def _replay(actions, human_player: int, Game, deck_seed: int = 0):
    """Replay an action log the ``root_replay.py`` way and count the AI seat's decisions
    (== the agent's ``_move_idx`` at that ply). Mirrors ``restore_game``'s loop."""
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    n_ai = 0
    for a in actions:
        if int(board.state.current_player) != human_player:
            n_ai += 1
        board, _ = game.get_next_state(board, int(a))
    return (game, board), n_ai


# --------------------------------------------------------------------------- #
# import / env                                                                  #
# --------------------------------------------------------------------------- #
def test_bridge_imports_and_sets_prod_env():
    """The knobs must have been in os.environ BEFORE carcassonne_ai was imported.

    Asserted against ``B.RESOLVED_ENV`` (captured at that instant), not live
    ``os.environ`` — in a full-suite run a sibling module later HARD-sets the leaf env
    to the frozen v2.9 block (``snapshot.set_frozen_v29_env``), which cannot change the
    leaf this process already froze but does rewrite the environment."""
    assert B.PROD_ENV["CARCASSONNE_USE_FLAT_LEAF"] == "1"
    assert B.RESOLVED_ENV == B.PROD_ENV, "the production leaf env was not applied first"
    # The invariant that actually matters: the frozen leaf is the champion's curve125.
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    assert tuple(DEFAULT_CONFIG.v29_meeple_curve) == B.champion_factory.CURVE125
    assert (DEFAULT_CONFIG.bonus_cap, DEFAULT_CONFIG.opp_bonus_cap) == (8.0, 8.0)
    # No Android/Java import may have leaked in.
    for mod in ("android", "java", "com.chaquo.python"):
        assert mod not in sys.modules


def test_prod_env_matches_repo_preamble():
    """The bridge carries a LITERAL copy of env_preamble.PROD_ENV (that file is not in
    the on-device bundle). If the repo's preamble changes, this fails — update the copy.

    Loaded BY PATH: ``scripts/f3_public_state_oracle/env_preamble.py`` shadows the name
    once another test module puts its script dir on sys.path."""
    import importlib.util

    path = REPO / "scripts" / "human_anchor" / "env_preamble.py"
    spec = importlib.util.spec_from_file_location("_human_anchor_env_preamble", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert B.PROD_ENV == mod.PROD_ENV


def test_production_yaml_resolved():
    d = ok(B.production_budget())
    assert d["champion_id"]
    assert d["sims_per_det"] > 0 and d["k_dets"] > 0
    assert Path(d["production_yaml"]).is_file()


# --------------------------------------------------------------------------- #
# new_game / get_state                                                          #
# --------------------------------------------------------------------------- #
def test_new_game_returns_schema_valid_state():
    st = new(seed=1)
    assert_state_schema(st)
    assert st["turn"] == 0 or st["n_actions"] == st["turn"]
    assert st["scores"] == [0, 0]
    assert st["meeples_free"] == [7, 7]
    assert st["is_terminated"] is False
    assert st["next_tile"]["image"]
    assert st["legal"]["tile_cells"], "the opening position must have a legal placement"
    # get_state is a pure read: identical payload, same generation.
    assert ok(B.get_state()) == st


def test_new_game_rejects_bad_config():
    d = j(B.new_game(json.dumps({"opponent": "nope"})))
    assert d["ok"] is False and d["error"]["code"] == "ValueError"
    d = j(B.new_game("[1,2,3]"))
    assert d["ok"] is False and d["error"]["code"] == "bad_config"


def test_champion_budget_note_and_manifest():
    st = new(opponent="champion", seed=2, **TINY)
    assert st["budget_note"] and "BELOW CHAMPION BUDGET" in st["budget_note"]
    assert "k1x8" in st["opponent_name"]
    d = ok(B.get_manifest())
    assert d["manifest_source"] == "session"
    man = d["manifest"]
    assert man["agent_class"] == "FairHeuristicPriorAgent"
    assert man["runtime_budget_override"]["total_sims"] == 8


def test_manifest_without_session_falls_back_to_the_spec():
    """The Settings sheet is reachable before any game exists, so get_manifest must
    answer with the spec-derived manifest rather than a no_session error — and must
    SAY it is the spec one (no runtime budget override to read)."""
    ok(B.reset())
    d = ok(B.get_manifest())
    assert d["manifest_source"] == "spec"
    man = d["manifest"]
    assert man["agent_class"] == "FairHeuristicPriorAgent"
    assert "runtime_budget_override" not in man
    # The spec manifest carries the YAML budget, which is what the sheet shows.
    budget = ok(B.production_budget())
    assert man["fair_deploy"]["total_sims"] == budget["total_sims"]


# --------------------------------------------------------------------------- #
# play                                                                          #
# --------------------------------------------------------------------------- #
def test_full_scripted_game_terminates():
    st = new(seed=13, opponent="tier1", human_player=0)
    st = play_out(st)
    assert_state_schema(st)
    assert st["is_terminated"] is True
    assert st["next_tile"] is None
    assert st["tiles_remaining"] == 0
    assert sum(st["scores"]) > 0
    assert st["result"]["verdict"]
    assert st["result"]["diff"] == abs(st["scores"][0] - st["scores"][1])
    # Every applied action is logged (auto-passes included).
    assert len(ok(B.save_game())["actions"]) == st["n_actions"] > 100
    # A terminated game refuses further input.
    assert j(B.apply_action(0))["error"]["code"] == "game_over"
    assert j(B.ai_move(st["generation"]))["error"]["code"] == "game_over"


def test_full_scripted_game_second_seat():
    """human_player=1 (the AI opens) exercises the other seat ordering."""
    st = new(seed=21, opponent="tier1", human_player=1)
    assert st["is_human_turn"] is False
    st = play_out(st)
    assert st["is_terminated"] and sum(st["scores"]) > 0


def test_illegal_action_rejected_cleanly():
    st = new(seed=4)
    legal = set(st["legal"]["action_ids"])
    bad = next(i for i in range(10_000) if i not in legal)
    d = j(B.apply_action(bad))
    assert d["ok"] is False
    assert d["error"]["code"] == "illegal_action"
    assert bad not in d["legal_action_ids"]
    # rejected != applied: the board is untouched
    assert ok(B.get_state()) == st
    # non-int and out-of-range are equally clean
    assert j(B.apply_action("banana"))["error"]["code"] == "illegal_action"
    assert j(B.apply_action(10 ** 9))["error"]["code"] == "illegal_action"


def test_not_ai_turn_rejected():
    st = new(seed=4, human_player=0)
    assert st["is_human_turn"]
    assert j(B.ai_move(st["generation"]))["error"]["code"] == "not_ai_turn"


def test_stale_generation_rejected():
    st = new(seed=4, human_player=1)          # AI to move
    d = j(B.ai_move(st["generation"] + 7))
    assert d["ok"] is False and d["error"]["code"] == "stale_generation"
    assert d["stale"] is True


def test_forced_pass_is_auto_applied():
    """The UI must never be handed a phase whose only legal action is 'pass'."""
    st = new(seed=13, opponent="tier1", human_player=0)
    seen_forced = 0
    prev_actions = 0
    plies = 0
    while not st["is_terminated"]:
        plies += 1
        assert plies <= 400
        if st["is_human_turn"]:
            ids = st["legal"]["action_ids"]
            pass_id = (st["legal"]["tile_pass_id"] if st["phase"] == "tiles"
                       else st["legal"]["meeple_pass_id"])
            assert ids != [pass_id], (
                f"human was shown a forced-pass-only phase at ply {plies}")
            st = ok(B.apply_action(ids[0]))
        else:
            st = ok(B.ai_move(st["generation"]))
        # more actions logged than decisions driven => auto-passes happened
        if st["n_actions"] > prev_actions + 1:
            seen_forced += st["n_actions"] - prev_actions - 1
        prev_actions = st["n_actions"]
    assert seen_forced > 0, "expected at least one auto-applied forced pass in a game"


def test_get_progress_shape():
    d = ok(B.get_progress())
    assert set(d) == {"ok", "leaf_calls", "expected", "elapsed_s", "phase", "fraction"}
    assert d["phase"] == "idle"
    st = new(seed=6, opponent="champion", human_player=1, **TINY)
    # The opening move is forced (one legal placement) and the fair agent short-circuits
    # without searching, so walk on until a real search happens.
    leaf_calls = 0
    for _ in range(12):
        if st["is_terminated"]:
            break
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
        leaf_calls = max(leaf_calls, st.get("leaf_calls", 0))
        if leaf_calls:
            break
    assert leaf_calls > 0, "the evaluator-counting seam never fired"
    after = ok(B.get_progress())
    assert after["phase"] == "idle" and after["expected"] == 8


# --------------------------------------------------------------------------- #
# save / restore                                                                #
# --------------------------------------------------------------------------- #
def _normalise_for_compare(st: dict) -> dict:
    """Drop the two genuinely-ephemeral fields: the session generation (a restore is a
    new session by construction) and the AI's wall-clock (not reconstructable)."""
    d = copy.deepcopy(st)
    d.pop("generation", None)
    d.pop("restored", None)
    if d.get("ai_last_move"):
        d["ai_last_move"].pop("elapsed_s", None)
    return d


def test_save_restore_round_trip_is_identical():
    st = new(seed=17, opponent="champion", human_player=0, **TINY)
    for _ in range(12):                       # a mid-game position with AI moves in it
        if st["is_terminated"]:
            break
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    before = ok(B.get_state())
    assert before["n_actions"] >= 10 and before["ai_last_move"] is not None

    save = ok(B.save_game())
    assert save["schema"] == B.SAVE_SCHEMA
    assert save["deck_seed"] == 17 and save["human_player"] == 0
    assert save["actions"] == save["actions"]  # json round-trips as ints
    assert all(isinstance(a, int) for a in save["actions"])

    restored = ok(B.restore_game(json.dumps(save)))
    assert restored["restored"]["actions"] == len(save["actions"])
    assert _normalise_for_compare(restored) == _normalise_for_compare(before)
    # and get_state() after the restore agrees with what restore_game returned
    assert _normalise_for_compare(ok(B.get_state())) == _normalise_for_compare(before)


def test_restore_reseats_agent_move_idx():
    st = new(seed=19, opponent="champion", human_player=0, **TINY)
    for _ in range(10):
        if st["is_terminated"]:
            break
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    save = ok(B.save_game())
    live_move_idx = B._S.agent._move_idx
    restored = ok(B.restore_game(json.dumps(save)))
    assert B._S.agent._move_idx == live_move_idx == restored["restored"]["ai_decisions"]
    assert B._S.agent._latched is False       # nowhere near the K<=2 endgame band


def test_restore_rejects_a_corrupt_log():
    st = new(seed=23, opponent="tier1")
    st = ok(B.apply_action(st["legal"]["action_ids"][0]))
    save = ok(B.save_game())
    save["actions"] = list(save["actions"]) + [99999]
    d = j(B.restore_game(json.dumps(save)))
    assert d["ok"] is False and d["error"]["code"] == "bad_save"
    d = j(B.restore_game(json.dumps({"schema": "nope"})))
    assert d["ok"] is False and d["error"]["code"] == "bad_save"


def test_restore_mid_endgame_latches():
    """A save taken inside the exact-endgame band restores with the latch already set —
    otherwise a restored champion would fall back to PIMC for the rest of the game."""
    st = new(seed=29, opponent="tier1", human_player=1)
    st = play_out(st)                                     # cheap full game, tier1 AI
    actions = ok(B.save_game())["actions"]
    # Walk the cut point back from the end until the restored session reports the latch
    # (the exact ply depends on the game; the CONTRACT is that some late cut latches).
    latched_at = None
    for cut in range(len(actions) - 1, max(0, len(actions) - 20), -1):
        save = {"schema": B.SAVE_SCHEMA, "deck_seed": 29, "human_player": 1,
                "opponent": "champion", "sims": 8, "k_dets": 1, "verify": False,
                "actions": actions[:cut]}
        restored = ok(B.restore_game(json.dumps(save)))
        if restored["restored"]["latched"]:
            latched_at = cut
            assert B._S.agent._latched is True
            break
    assert latched_at is not None, (
        "no late cut of a finished game restored with the exact-endgame latch set")


# --------------------------------------------------------------------------- #
# parity with a direct champion construction                                    #
# --------------------------------------------------------------------------- #
def test_ai_move_matches_direct_champion():
    """The bridge must not perturb the agent. Same seed + same position + same
    ``_move_idx`` => the same action as a champion built straight from the repo tree.

    ``fair_agent`` derives every per-move search seed from ``(seed, _move_idx)``, so the
    comparison agent's ``_move_idx`` is aligned to the number of AI decisions replayed."""
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game

    seed, sims, k_dets = 31, 8, 1
    st = new(seed=seed, opponent="champion", human_player=0, sims=sims,
             k_dets=k_dets, verify=False)
    checked = 0
    for _ in range(60):
        if st["is_terminated"] or checked >= 2:
            break
        if st["is_human_turn"]:
            st = ok(B.apply_action(st["legal"]["action_ids"][0]))
            continue

        # Snapshot the position the bridge is about to think about.
        actions = ok(B.save_game())["actions"]
        (_g, board), n_ai = _replay(actions, human_player=0, Game=Game, deck_seed=seed)
        direct = make_production_champion(
            "fair", game=Game(enable_legal_moves_cache=True), seed=seed, sims=sims,
            k_dets=k_dets, exact_endgame=True, verify=False)
        direct._move_idx = n_ai
        expected = int(direct.choose_action(board))

        st = ok(B.ai_move(st["generation"]))
        assert st["action_id"] == expected, (
            f"bridge chose {st['action_id']}, direct champion chose {expected} "
            f"at ai decision #{n_ai}")
        checked += 1
    assert checked == 2, "the parity check never reached two AI decisions"


@pytest.mark.slow
def test_verify_true_construction():
    """``verify=True`` is the on-device canary for a bundling mistake: it proves the
    curve125 leaf on real boards (and needs c5_leaf_override + snapshot importable)."""
    st = new(seed=41, opponent="champion", sims=8, k_dets=1, verify=True)
    man = ok(B.get_manifest())["manifest"]
    assert man["leaf_hashes"]["harness_leaf_hash"]
    assert man["leaf"]["curve125"] == [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
    assert man["leaf_value_panel"]["empty_meeples_3v7_float"] == -6.25
    assert st["ok"]


# --------------------------------------------------------------------------- #
# the bundle                                                                    #
# --------------------------------------------------------------------------- #
def test_sync_python_produces_the_expected_tree(tmp_path):
    out = tmp_path / "bundle"
    summary = sync_python.sync(REPO, out)
    assert summary["carcassonne_ai"] > 20 and summary["wingedsheep"] > 20

    assert (out / "carcassonne_ai" / "champion_factory.py").is_file()
    assert (out / "carcassonne_ai" / "fair_agent.py").is_file()
    assert (out / "carcassonne_ai" / "data" / "PRODUCTION.yaml").is_file()
    assert (out / "wingedsheep" / "carcassonne" / "carcassonne_game_state.py").is_file()
    for name in ("endgame_solver.py", "c5_leaf_override.py", "snapshot.py"):
        assert (out / name).is_file(), f"{name} must be bundled TOP-LEVEL"

    # exclusions
    assert not (out / "wingedsheep" / "carcassonne" / "carcassonne_visualiser.py").exists()
    assert not (out / "wingedsheep" / "carcassonne" / "resources" / "images").exists()
    assert not list(out.rglob("*.png"))
    assert not list(out.rglob("*.so")) and not list(out.rglob("*.pyx"))
    assert not list(out.rglob("*.c")) and not list(out.rglob("__pycache__"))

    # idempotent: a second sync cleans stale content it owns
    stale = out / "carcassonne_ai" / "ZZZ_stale.py"
    stale.write_text("raise SystemExit('stale')\n")
    sync_python.sync(REPO, out)
    assert not stale.exists()


_BUNDLE_DRIVER = r'''
import json, os, sys
bundle = sys.argv[1]
sys.path.insert(0, bundle)
import android_bridge as B
# Prove we are running the BUNDLE, not the repo (the repo's src/ must be irrelevant).
import carcassonne_ai, wingedsheep, endgame_solver, c5_leaf_override, snapshot
for mod in (carcassonne_ai, wingedsheep, endgame_solver, c5_leaf_override, snapshot):
    assert os.path.realpath(mod.__file__).startswith(os.path.realpath(bundle)), (
        mod.__name__ + " resolved OUTSIDE the bundle: " + mod.__file__)
assert os.path.realpath(B.PRODUCTION_YAML_PATH).startswith(os.path.realpath(bundle)), (
    "PRODUCTION.yaml not read from the bundle: " + B.PRODUCTION_YAML_PATH)

st = json.loads(B.new_game(json.dumps(
    {"seed": 3, "human_player": 0, "opponent": "champion",
     "sims": 8, "k_dets": 1, "verify": True})))
assert st["ok"], st
moves = 0
while moves < 4 and not st["is_terminated"]:
    if st["is_human_turn"]:
        st = json.loads(B.apply_action(st["legal"]["action_ids"][0]))
    else:
        st = json.loads(B.ai_move(st["generation"]))
    assert st["ok"], st
    moves += 1
print(json.dumps({"moves": moves, "n_actions": st["n_actions"],
                  "champion_id": json.loads(B.get_manifest())["manifest"]["champion_id"],
                  "bridge": B.__file__}))
'''


def test_bundle_runs_standalone(tmp_path):
    """THE critical test: play through the synced bundle in a subprocess where the
    repo's ``src/`` cannot satisfy an import. A module missing from sync_python's table
    fails here instead of on the phone.

    The bridge is copied INTO the bundle (that is the device layout — Chaquopy merges
    ``src/main/python`` and the sync target into one import root), which also disables
    the bridge's desktop repo-src fallback: from inside tmp_path there is no repo above
    it to fall back to."""
    out = tmp_path / "bundle"
    sync_python.sync(REPO, out)
    (out / "android_bridge.py").write_bytes(
        (BRIDGE_DIR / "android_bridge.py").read_bytes())

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = str(out)
    proc = subprocess.run(
        [sys.executable, "-c", _BUNDLE_DRIVER, str(out)],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, (
        f"bundle subprocess failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["moves"] == 4
    assert result["n_actions"] >= 4
    assert result["champion_id"]
    assert str(out) in result["bridge"]


_STRICT_HOOK_DRIVER = r'''
import json, os, sys
bundle = sys.argv[1]
sys.path.insert(0, bundle)

# Chaquopy's AssetFinder path hook RAISES FileNotFoundError for a sys.path entry
# that does not exist, where desktop CPython silently skips it. That asymmetry is
# exactly what let champion_factory._hashers()'s REPO-relative sys.path inserts
# pass every desktop test and then kill every champion construction on the phone
# (playtest P0, 2026-07-27). Reproduce the device semantics here.
# Only entries inserted AFTER interpreter startup get the strict treatment: the
# desktop interpreter legitimately carries nonexistent baseline entries (e.g.
# /usr/lib/python312.zip) that real Chaquopy never has.
_BASELINE = set(sys.path)

def chaquopy_strict(path):
    if path not in _BASELINE and path.startswith("/") and not os.path.exists(path):
        raise FileNotFoundError(path)
    raise ImportError  # decline: fall through to the normal hooks

sys.path_hooks.insert(0, chaquopy_strict)
sys.path_importer_cache.clear()

import android_bridge as B
assert B.FACTORY_REPO_SHIM is not None, "repo shim should activate outside a checkout"

st = json.loads(B.new_game(json.dumps(
    {"seed": 7, "human_player": 1, "opponent": "champion",
     "sims": 8, "k_dets": 1, "verify": True})))
assert st["ok"], st                      # champion constructs under strict semantics
st = json.loads(B.ai_move(st["generation"]))   # human_player=1 -> AI moves first
assert st["ok"], st

bad = [p for p in sys.path
       if p not in _BASELINE and p.startswith("/") and not os.path.exists(p)]
assert not bad, "nonexistent sys.path entries would poison Chaquopy imports: %r" % bad
print(json.dumps({"ok": True, "shim": B.FACTORY_REPO_SHIM}))
'''


def test_bundle_survives_chaquopy_strict_path_hook(tmp_path):
    """Regression for the on-device P0: construct the champion (verify=True) in the
    bundle layout under a path hook that raises for nonexistent sys.path entries,
    the way Chaquopy's AssetFinder does. Without ``_shim_factory_repo`` this fails
    with FileNotFoundError from ``champion_factory._hashers()``."""
    out = tmp_path / "bundle"
    sync_python.sync(REPO, out)
    (out / "android_bridge.py").write_bytes(
        (BRIDGE_DIR / "android_bridge.py").read_bytes())

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = str(out)
    proc = subprocess.run(
        [sys.executable, "-c", _STRICT_HOOK_DRIVER, str(out)],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, (
        f"strict-hook subprocess failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    assert json.loads(proc.stdout.strip().splitlines()[-1])["ok"] is True


# --------------------------------------------------------------------------- #
# tier-1 restore determinism                                                    #
# --------------------------------------------------------------------------- #
# The champion re-seats deterministically from `_move_idx`, but RuleBasedPlayer's
# randomness lives in a STREAM (`_rng`, one `choice` per virtual-score tie-break) whose
# consumption is data-dependent — `Random.choice` rejection-samples over the number of
# TIED-best actions, which cannot be counted without scoring the position. So the bridge
# rebuilds it by replaying the decisions. Measured before that landed: 12/12 seeds
# played a DIFFERENT game after a mid-game restore.
_TIER1_SEEDS = (0, 1, 2, 3, 4, 5)
_CUT = 40      # plies played before the save
_TAIL = 30     # plies compared after it


def _step(st: dict) -> tuple[dict, int]:
    """One ply, deterministic human (lowest legal id). Returns (new_state, action_id)."""
    if st["is_human_turn"]:
        a = int(st["legal"]["action_ids"][0])
        return ok(B.apply_action(a)), a
    r = ok(B.ai_move(st["generation"]))
    return r, int(r["action_id"])


def _play(st: dict, n: int) -> tuple[dict, list[int]]:
    moves: list[int] = []
    for _ in range(n):
        if st["is_terminated"]:
            break
        st, a = _step(st)
        moves.append(a)
    return st, moves


def _continuous(seed: int) -> tuple[dict, list[int]]:
    """Play _CUT plies, snapshot the save, play _TAIL more. Returns (save, tail)."""
    st = new(seed=seed, opponent="tier1")
    st, _ = _play(st, _CUT)
    save = ok(B.save_game())
    _, tail = _play(st, _TAIL)
    return save, tail


def _after_restore(save: dict) -> tuple[list[int], dict]:
    restored = ok(B.restore_game(json.dumps(save)))
    _, tail = _play(restored, _TAIL)
    return tail, restored


@pytest.mark.parametrize("seed", _TIER1_SEEDS)
def test_tier1_restore_continues_the_same_game(seed):
    """save -> restore -> continue must replay the SAME moves as never having stopped."""
    save, continuous = _continuous(seed)
    assert continuous, "the tail is empty; the cut is past the end of the game"
    restored_tail, restored = _after_restore(save)
    assert restored["restored"]["rng_replayed"] is True
    assert restored_tail == continuous, (
        f"seed {seed}: tier-1 diverged after restore\n"
        f"  continuous: {continuous}\n  restored:   {restored_tail}")


def test_tier1_restore_rng_replay_is_load_bearing(monkeypatch):
    """Negative control: with the RNG replay disabled the same check FAILS.

    Without this, `test_tier1_restore_continues_the_same_game` could pass for a reason
    that has nothing to do with the fix (e.g. no tie-break ever firing in the window)."""
    save, continuous = _continuous(_TIER1_SEEDS[0])
    monkeypatch.setattr(B, "_replays_rng", lambda agent: False)
    restored = ok(B.restore_game(json.dumps(save)))
    assert restored["restored"]["rng_replayed"] is False
    _, tail = _play(restored, _TAIL)
    assert tail != continuous, (
        "tier-1 did NOT diverge with the RNG replay disabled — the positive test is "
        "not actually exercising the fix; widen _CUT/_TAIL")


def test_tier1_restore_does_not_replay_the_champion_rng():
    """The champion must keep the cheap `_move_idx` path — replaying its decisions
    would cost a full search per ply."""
    new(seed=11, opponent="champion", **TINY)
    assert B._replays_rng(B._S.agent) is False
    new(seed=11, opponent="tier1")
    assert B._replays_rng(B._S.agent) is True


def test_restore_rejects_a_bad_human_player():
    st = new(seed=13, opponent="tier1")
    save = ok(B.save_game())
    save["human_player"] = 2
    d = j(B.restore_game(json.dumps(save)))
    assert d["ok"] is False and d["error"]["code"] == "bad_save"
    assert st["ok"]


# --------------------------------------------------------------------------- #
# save stamp / mismatch warning                                                 #
# --------------------------------------------------------------------------- #
def test_save_carries_the_champion_stamp():
    new(seed=31, opponent="tier1")
    save = ok(B.save_game())
    assert save["champion_id"] and save["leaf_hash"]
    # A save from the running build restores without a warning.
    restored = ok(B.restore_game(json.dumps(save)))
    assert "save_mismatch" not in restored


def test_restore_warns_but_does_not_refuse_on_a_stale_stamp():
    new(seed=37, opponent="tier1")
    save = ok(B.save_game())
    save["champion_id"] = "some-older-champion"
    restored = ok(B.restore_game(json.dumps(save)))
    assert restored["ok"] is True                       # advisory, never fatal
    mm = restored["save_mismatch"]
    assert mm["fields"]["champion_id"]["saved"] == "some-older-champion"
    assert mm["message"]


def test_restore_of_a_stampless_save_is_not_a_mismatch():
    """Saves written before the stamp existed must not trip the warning."""
    new(seed=41, opponent="tier1")
    save = ok(B.save_game())
    save.pop("champion_id", None)
    save.pop("leaf_hash", None)
    assert "save_mismatch" not in ok(B.restore_game(json.dumps(save)))


# --------------------------------------------------------------------------- #
# the import-closure gate                                                       #
# --------------------------------------------------------------------------- #
def test_import_gate_passes_for_the_current_bundle(tmp_path):
    """The shipped bundle's module-scope import closure resolves to
    {bundle, stdlib, numpy, yaml} — nothing else exists on the phone."""
    out = tmp_path / "bundle"
    sync_python.sync(REPO, out)               # raises SystemExit if the gate fails
    report = sync_python.check_imports([out, BRIDGE_DIR])
    assert report["violations"] == {}
    assert "android_bridge" in report["reachable"]
    assert "carcassonne_ai.champion_factory" in report["reachable"]
    # fair_agent is imported INSIDE a champion_factory function, so it is absent from
    # the start-up set and present in the any-scope one. That asymmetry is exactly why
    # the gate must never treat "unreachable at module scope" as "safe to delete".
    assert "carcassonne_ai.fair_agent" not in report["reachable"]
    assert "carcassonne_ai.fair_agent" in report["reachable_any"]
    # The torch cluster is declared dead weight (EXCLUDE_MODULES) and never copied.
    for gone in sync_python.EXCLUDE_MODULES:
        assert not (out / "carcassonne_ai" / gone).exists(), f"{gone} still shipped"


def test_import_gate_catches_a_synthetic_violation(tmp_path):
    out = tmp_path / "bundle"
    sync_python.sync(REPO, out)
    # champion_factory is on android_bridge's module-scope import path, so an
    # unsatisfiable import here is fatal rather than droppable.
    f = out / "carcassonne_ai" / "champion_factory.py"
    f.write_text("import torch\n" + f.read_text())
    with pytest.raises(SystemExit) as exc:
        sync_python.enforce_imports([out, BRIDGE_DIR])
    msg = str(exc.value)
    assert "torch" in msg and "champion_factory" in msg


def test_import_gate_exempts_function_scope_imports(tmp_path):
    """The lazy-import idiom the library already uses must stay legal."""
    out = tmp_path / "bundle"
    sync_python.sync(REPO, out)
    f = out / "carcassonne_ai" / "champion_factory.py"
    f.write_text(f.read_text() +
                 "\n\ndef _lazy_torch():\n    import torch\n    return torch\n")
    report = sync_python.enforce_imports([out, BRIDGE_DIR])
    assert report["violations"] == {}


def test_import_gate_exempts_type_checking_blocks(tmp_path):
    out = tmp_path / "bundle"
    sync_python.sync(REPO, out)
    f = out / "carcassonne_ai" / "champion_factory.py"
    f.write_text("from typing import TYPE_CHECKING\n"
                 "if TYPE_CHECKING:\n    import torch\n" + f.read_text())
    report = sync_python.enforce_imports([out, BRIDGE_DIR])
    assert report["violations"] == {}


def test_import_gate_notices_a_module_missing_from_the_bundle(tmp_path):
    """A bundle-internal import that no longer resolves is a violation too — this is
    what a lenient root-only check would have waved through."""
    out = tmp_path / "bundle"
    sync_python.sync(REPO, out)
    # action_space IS imported at module scope (by android_bridge itself).
    (out / "carcassonne_ai" / "action_space.py").unlink()
    report = sync_python.check_imports([out, BRIDGE_DIR])
    offenders = {m for m, targets in report["violations"].items()
                 if any(t.endswith("action_space") for t in targets)}
    assert offenders, "deleting action_space.py went unnoticed by the gate"


# --------------------------------------------------------------------------- #
# runtime_info — the Cython fast-path report                                    #
# --------------------------------------------------------------------------- #
# On desktop the compiled extensions may or may not be present (they are gitignored,
# per-box `.so` builds), and on device they arrive via the carc-cy wheel. So these
# tests assert the SCHEMA and the internal consistency of the report, never that
# Cython happens to be loaded here.
def test_runtime_info_schema():
    d = ok(B.runtime_info())
    assert isinstance(d["python"], str) and d["python"].startswith("3.")
    assert d["python_implementation"] == "CPython"
    assert isinstance(d["numpy"], str) and d["numpy"][0].isdigit()
    assert isinstance(d["flat_leaf"], bool)

    assert set(d["cython"]) == {"flat_leaf_cy", "flat_repr_cy"}
    for name, block in d["cython"].items():
        assert isinstance(block["enabled"], bool), name
        assert isinstance(block["loaded"], bool), name
        assert block["bound"] in {"unbound", "active", "pure_python"}, name

    assert set(d["spec"]) == {"champion_id", "leaf_hash"}
    assert isinstance(d["env"], dict) and "CARCASSONNE_USE_FLAT_LEAF" in d["env"]


def test_runtime_info_env_matches_the_frozen_resolved_env():
    """The report must quote RESOLVED_ENV — the knobs as they were the instant before
    carcassonne_ai was imported — not a later os.environ that no longer affects the leaf."""
    d = ok(B.runtime_info())
    assert d["env"] == B.RESOLVED_ENV


def test_runtime_info_bound_state_is_consistent_with_loading():
    """`bound == "active"` is only reachable if the extension actually loaded."""
    d = ok(B.runtime_info())
    for name, block in d["cython"].items():
        if block["bound"] == "active":
            assert block["loaded"], f"{name} bound active without being loaded"


def test_cy_alias_table_covers_both_modules():
    """_install_cy_aliases must report on both extensions whether or not they exist."""
    assert set(B.CY_LOADED) == set(B.CY_MODULES) == {"flat_leaf_cy", "flat_repr_cy"}
    assert all(isinstance(v, bool) for v in B.CY_LOADED.values())


def test_cy_alias_is_published_under_the_carcassonne_ai_name():
    """Whatever loaded must be reachable under the dotted name flat_leaf.py imports."""
    for name, loaded in B.CY_LOADED.items():
        if loaded:
            assert f"carcassonne_ai.{name}" in sys.modules, name


# --------------------------------------------------------------------------- #
# end-of-game score breakdown                                                   #
# --------------------------------------------------------------------------- #
def _play_to_the_end(seed: int, rng_seed: int = 0) -> dict:
    """Random-but-legal human vs tier1, to termination. Returns the final state."""
    st = new(seed=seed, opponent="tier1", human_player=0)
    rng = random.Random(rng_seed)
    for _ in range(400):
        if st["is_terminated"]:
            return st
        if st["is_human_turn"]:
            legal = j(B.get_state())["legal"]
            ids = [i for c in legal["tile_cells"] for i in c["action_ids"]]
            ids += [m["action_id"] for m in legal["meeple_slots"]]
            ids += [legal[k] for k in ("tile_pass_id", "meeple_pass_id")
                    if legal.get(k) is not None]
            st = ok(B.apply_action(rng.choice(ids)))
        else:
            st = ok(B.ai_move(st["generation"]))
    raise AssertionError("game did not terminate in 400 plies")


def test_result_breakdown_reconciles_with_the_final_scores():
    """The end-of-game jump, itemised — and it must ADD UP.

    Base+Farmers banks most of its points on the last tile (farms settle, open
    features pay a reduced rate), so the scoreboard leaps with nothing on screen
    to explain it. `_final_breakdown` reconstructs that pass by re-applying the
    terminating action to the retained previous board with `count_final_scores`
    stubbed — the engine consumes the placed meeples inside the terminating move,
    so the terminal state itself carries no attribution.

    The bridge REFUSES to emit a block that does not balance (it returns None), so
    a wrong split shows up here as a missing breakdown, not as a wrong number.
    """
    st = _play_to_the_end(seed=5)
    rows = st["result"]["breakdown"]
    assert rows is not None, "breakdown was dropped — the reconstruction failed"
    assert len(rows) == len(st["result"]["scores"])
    for p, row in enumerate(rows):
        assert set(row) == {"during_play", "incomplete", "farms", "total"}
        assert all(isinstance(v, int) for v in row.values())
        assert row["during_play"] + row["incomplete"] + row["farms"] == row["total"]
        assert row["total"] == st["result"]["scores"][p]
    # A finished 72-tile game always settles SOME farm or open-feature points;
    # an all-zero endgame column would mean the reconstruction scored nothing.
    assert any(r["farms"] or r["incomplete"] for r in rows)


def test_result_breakdown_survives_a_save_restore_round_trip():
    """Replay goes through `_Session.apply`, so `prev_board` is rebuilt for free."""
    st = new(seed=11, opponent="tier1", human_player=0)
    saved = B.save_game()
    ok(saved)
    ok(B.restore_game(saved))
    st = _play_to_the_end(seed=11, rng_seed=3)
    assert st["result"]["breakdown"] is not None


def test_breakdown_is_absent_rather_than_wrong_when_unreconstructable():
    """`_final_breakdown` is best-effort: no previous board -> None, never a guess."""
    st = new(seed=7, opponent="tier1")
    s = B._S
    s.prev_board = None
    s.last_action = None
    assert B._final_breakdown(s, [0, 0]) is None
