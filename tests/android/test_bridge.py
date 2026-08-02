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
    "n_actions", "events",
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


def _replay(actions, human_player: int, Game, deck_seed: int = 0,
            start_rule: str = B.START_RULE):
    """Replay an action log the ``root_replay.py`` way and count the AI seat's decisions
    (== the agent's ``_move_idx`` at that ply). Mirrors ``restore_game``'s loop.

    ``start_rule`` must match the rule the log was played under — (deck_seed,
    actions) is only lossless with respect to its own start-tile convention."""
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True,
                fixed_start_tile=start_rule == B.START_RULE_RETAIL)
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


def test_mobile_profile_is_the_champion_of_record_on_the_rust_backend():
    """THE UNPIN GUARD (2026-08-01). The mobile profile was PINNED at k4x688 from
    2026-07-29 because 11008 sims needed 8 spawn processes and Chaquopy has none. The
    rustport native core (4 OS threads inside ONE call, 1.551 s/move on the Pixel — G7
    leg 3) met the profile's own written unpin condition, so the phone now plays the
    CHAMPION OF RECORD.

    Two halves, and the second is the one that keeps the phone safe: the profile must
    resolve to the champion budget, AND that budget must be inseparable from
    `backend: rust`. 11008 sims on the Python engine is ~25 s/move here."""
    from carcassonne_ai import champion_factory as cf

    spec = cf.load_production_spec()
    mob = B.mobile_budget(spec)
    assert mob["profile"] == "mobile" and mob["from_yaml"] is True
    full = (spec.k_dets, spec.sims_per_det, spec.k_dets * spec.sims_per_det)
    assert (mob["k_dets"], mob["sims_per_det"], mob["total_sims"]) == full, \
        "the phone must now run the champion of record"
    assert mob["backend"] == B.BACKEND_RUST
    assert mob["rust_threads"] and mob["rust_threads"] >= 1
    # parallel_workers stays null forever: Chaquopy has no multiprocessing. The
    # parallelism here is Rust threads inside one call, a different mechanism.
    assert cf.deploy_profile("mobile", spec)["parallel_workers"] is None

    d = ok(B.production_budget())
    assert (d["k_dets"], d["sims_per_det"], d["total_sims"]) == full
    assert d["total_sims"] == d["champion_of_record_total_sims"]

    # THE COUPLING: asking for the Python engine must drop the BUDGET too, never leave
    # the phone holding a 25 s/move champion budget on the slow path.
    py = B.budget_for_backend(B.BACKEND_PYTHON, spec)
    assert py["floored"] is True
    assert (py["k_dets"], py["sims_per_det"]) == (
        B.ANDROID_FALLBACK_BUDGET["k_dets"], B.ANDROID_FALLBACK_BUDGET["sims_per_det"])
    assert py["total_sims"] < spec.k_dets * spec.sims_per_det
    assert B.budget_for_backend(B.BACKEND_RUST, spec)["floored"] is False

    # FAIL-CLOSED: a spec with no `mobile` profile must fall back to the module's own
    # floor, never to the champion budget.
    import dataclasses as dc

    stripped = dc.replace(spec, deploy_profiles={})
    fb = B.mobile_budget(stripped)
    assert fb["from_yaml"] is False
    assert (fb["k_dets"], fb["sims_per_det"]) == (
        B.ANDROID_FALLBACK_BUDGET["k_dets"], B.ANDROID_FALLBACK_BUDGET["sims_per_det"])
    assert fb["backend"] == B.BACKEND_PYTHON, "the floor is a PYTHON budget"
    assert fb["total_sims"] < spec.k_dets * spec.sims_per_det


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
    # The spec manifest carries the CHAMPION OF RECORD budget. Since the 2026-07-29
    # promotion that is NOT what the phone runs, so production_budget()'s headline
    # figures are the mobile profile and the champion of record rides alongside.
    budget = ok(B.production_budget())
    assert man["fair_deploy"]["total_sims"] == budget["champion_of_record_total_sims"]
    assert budget["total_sims"] <= budget["champion_of_record_total_sims"]


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


def test_progress_is_indeterminate_on_the_rust_backend():
    """The leaf counter wraps the PYTHON evaluator, and a Rust-backed champion never
    touches it (the search runs inside carc_rs). Reporting the nominal budget anyway
    would render a bar frozen at 0% for the whole move, so `expected` must be 0 —
    which `get_progress` turns into `fraction: null`, an indeterminate spinner."""
    st = new(seed=6, opponent="champion", human_player=1,
             backend=B.BACKEND_RUST, **TINY)
    if st["backend"] != B.BACKEND_RUST:
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    d = ok(B.get_progress())
    assert d["expected"] == 0
    assert d["fraction"] is None


def test_get_progress_shape():
    d = ok(B.get_progress())
    assert set(d) == {"ok", "leaf_calls", "expected", "elapsed_s", "phase", "fraction"}
    assert d["phase"] == "idle"
    # PYTHON backend explicitly: this test is about the evaluator-counting seam, which
    # is a property of the Python agent. The rust twin is the test above.
    st = new(seed=6, opponent="champion", human_player=1,
             backend=B.BACKEND_PYTHON, **TINY)
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
    """Drop the genuinely-ephemeral fields: the session generation (a restore is a new
    session by construction), the AI's wall-clock, and `events` — a restore REPLAYS
    its decisions rather than playing them, so "what the last move just paid" is not a
    property of the position and is deliberately empty (see
    `test_restored_and_undone_sessions_report_no_events`)."""
    d = copy.deepcopy(st)
    d.pop("generation", None)
    d.pop("restored", None)
    d.pop("events", None)
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
    # PYTHON backend explicitly: `_move_idx` is the PYTHON agent's move timeline, and it
    # only advances when that agent is the one choosing. Under the rust default the
    # Python agent is the bridge's anchor (manifest/progress) and never searches, so its
    # counter legitimately stays 0 live — the mirror carries the timeline instead, and
    # test_bridge_backend.py::test_restore_reseats_the_rust_mirror is that guard.
    st = new(seed=19, opponent="champion", human_player=0,
             backend=B.BACKEND_PYTHON, **TINY)
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
                # Must match the rules the log above was played under, or the
                # replay decodes a different game. `grid_rule` matters for the
                # sharper reason: an action index is a WINDOW cell, so the same
                # log lands on different board cells on a different grid.
                "start_rule": B.START_RULE, "grid_rule": B.GRID_RULE,
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
            k_dets=k_dets, exact_endgame=True, verify=False,
            exact_budget=B.ANDROID_EXACT_BUDGET)
        direct._move_idx = n_ai
        expected = int(direct.choose_action(board))

        st = ok(B.ai_move(st["generation"]))
        assert st["action_id"] == expected, (
            f"bridge chose {st['action_id']}, direct champion chose {expected} "
            f"at ai decision #{n_ai}")
        checked += 1
    assert checked == 2, "the parity check never reached two AI decisions"


# --------------------------------------------------------------------------- #
# on-device endgame-solver bound (ANDROID_WALLCLOCK_MEMO_20260728 lever #1)      #
# --------------------------------------------------------------------------- #
def test_bridge_binds_the_android_exact_budget():
    """The app MUST cap the solver's node budget. Unbounded, a single unlucky endgame
    board is an uncancellable multi-hour hang on the phone (the budget has no wall-clock
    component and reset() queues behind a running ai_move)."""
    from carcassonne_ai.fair_agent import DEFAULT_EXACT_BUDGET

    assert B.ANDROID_EXACT_BUDGET == 100_000
    # >=10x the largest solve observed to date (7,067 nodes) but far under the desktop
    # default -> a real bound that should never fire.
    assert 7_067 * 10 < B.ANDROID_EXACT_BUDGET < DEFAULT_EXACT_BUDGET

    new(seed=7, opponent="champion", sims=8, k_dets=1, verify=False)
    agent = B._require_session().agent
    assert agent._exact_budget == B.ANDROID_EXACT_BUDGET, (
        "the bridge built a champion that is still pinned at the desktop node budget")


def test_android_exact_budget_is_stamped_on_the_manifest():
    """It is a play-affecting bound in the branch where it fires, so the archived game
    must record it — E4 must never read a PIMC-fallback move as the champion's exact one."""
    new(seed=8, opponent="champion", sims=8, k_dets=1, verify=False)
    man = ok(B.get_manifest())["manifest"]
    assert man["exact_budget"]["nodes"] == 100_000
    assert man["exact_budget"]["default"] == 2_000_000


def test_weakened_difficulty_tiers_are_also_bounded():
    """Every tier goes through the one construction site — a tier that skipped the bound
    would be the one that hangs."""
    for sims, k in ((8, 1), (16, 2)):
        new(seed=9, opponent="champion", sims=sims, k_dets=k, verify=False)
        assert B._require_session().agent._exact_budget == B.ANDROID_EXACT_BUDGET


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


# --------------------------------------------------------------------------- #
# meeple-slot feature grouping (UI dedupe; the action space is UNTOUCHED)        #
# --------------------------------------------------------------------------- #
def _base_tiles():
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    return base_tiles


def test_feature_groups_merges_a_multi_opening_city():
    """`city=[[TOP, RIGHT]]` is ONE city with two openings -> one group."""
    tile = _base_tiles()["city_diagonal_top_right"]
    assert [[s.value for s in g] for g in tile.city] == [["top", "right"]]
    g = B.feature_groups(tile)
    assert g["top"] == g["right"], "two openings onto one city must share a group"


def test_feature_groups_keeps_two_separate_cities_apart():
    """`city=[[LEFT], [RIGHT]]` is TWO cities -> two groups. The negative control."""
    tile = _base_tiles()["city_left_right"]
    assert [[s.value for s in g] for g in tile.city] == [["left"], ["right"]]
    g = B.feature_groups(tile)
    assert g["left"] != g["right"], "two distinct cities must NOT be merged"


def test_feature_groups_merges_a_through_road_and_splits_a_crossroads():
    g = B.feature_groups(_base_tiles()["straight_road"])
    assert g["top"] == g["bottom"], "a road running through is one feature"
    # A crossroads is four (side, CENTER) connections — four distinct roads.
    g = B.feature_groups(_base_tiles()["crossroads"])
    assert len({g["top"], g["right"], g["bottom"], g["left"]}) == 4


def test_feature_groups_never_merges_a_road_end_into_the_monastery():
    """`chapel_with_road` is `road=[(BOTTOM, CENTER)]` + `chapel=True`.

    CENTER is the monastery's own slot, so the road's CENTER endpoint must be
    skipped rather than grouped — otherwise the two would collapse into one dot."""
    tile = _base_tiles()["chapel_with_road"]
    assert tile.chapel is True
    g = B.feature_groups(tile)
    assert g["center"] != g["bottom"]


def test_feature_groups_merges_equivalent_farmer_positions():
    """One `FarmerConnection` = one field; all its `farmer_positions` are the same."""
    tile = _base_tiles()["chapel"]
    (farm,) = tile.farms
    sides = [s.value for s in farm.farmer_positions]
    assert len(sides) > 1, "this fixture needs a field with several entry points"
    g = B.feature_groups(tile)
    assert len({g[s] for s in sides}) == 1


def test_every_base_face_groups_without_collision():
    """No face may put a city/road side and the monastery in the same group."""
    for name, tile in _base_tiles().items():
        g = B.feature_groups(tile)
        assert all(isinstance(v, int) and v >= 0 for v in g.values()), name
        if tile.chapel or tile.flowers:
            centre = g.get("center")
            assert centre is not None, name
            others = [k for k, v in g.items() if v == centre and k != "center"]
            assert not others, f"{name}: monastery merged with {others}"


def test_slots_carry_dense_feature_groups_and_keep_every_action():
    """Grouping is ADVICE: every legal action still ships, ids stay dense."""
    st = new(seed=5, opponent="tier1", human_player=0)
    seen_multi = False
    for _ in range(40):
        if st["is_terminated"]:
            break
        if st["phase"] == "meeples" and st["is_human_turn"]:
            slots = st["legal"]["meeple_slots"]
            if slots:
                groups = [s["feature_group"] for s in slots]
                assert all(isinstance(x, int) for x in groups)
                # dense: exactly 0..n-1 appear
                assert set(groups) == set(range(len(set(groups))))
                # every legal meeple action is still present
                legal = set(B.legal_meeple_indices(B._S.game, B._S.board))
                assert {s["action_id"] for s in slots} == legal
                if len(set(groups)) < len(groups):
                    seen_multi = True
        st = ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"] \
            else ok(B.ai_move(st["generation"]))
    assert seen_multi, "expected at least one tile offering equivalent slots"


# --------------------------------------------------------------------------- #
# preview_meeple_slots — the ghost's prospective dots                           #
# --------------------------------------------------------------------------- #
def test_preview_matches_the_slots_the_move_actually_opens():
    st = new(seed=5, opponent="tier1", human_player=0)
    cell = st["legal"]["tile_cells"][0]
    aid = cell["action_ids"][0]
    preview = ok(B.preview_meeple_slots(aid))["slots"]
    real = ok(B.apply_action(aid))["legal"]["meeple_slots"]
    assert preview == real, "the preview must be the same builder as the real thing"


def test_preview_does_not_mutate_the_session():
    """The whole feature is read-only; prove the live board is untouched."""
    st = new(seed=13, opponent="tier1", human_player=0)
    before = ok(B.get_state())
    for cell in st["legal"]["tile_cells"][:5]:
        for aid in cell["action_ids"]:
            ok(B.preview_meeple_slots(aid))
    assert ok(B.get_state()) == before


def test_preview_rejects_an_illegal_or_wrong_phase_action():
    st = new(seed=5, opponent="tier1", human_player=0)
    bad = j(B.preview_meeple_slots(999_999))
    assert bad["ok"] is False and bad["error"]["code"] == "illegal_action"
    assert j(B.preview_meeple_slots("nope"))["ok"] is False
    # ...and once the tile is down, the tile-phase precondition is gone.
    st = ok(B.apply_action(st["legal"]["tile_cells"][0]["action_ids"][0]))
    assert st["phase"] == "meeples"
    out = j(B.preview_meeple_slots(0))
    assert out["ok"] is False and out["error"]["code"] == "not_tile_phase"


# --------------------------------------------------------------------------- #
# the last-move event summary                                                   #
# --------------------------------------------------------------------------- #
def _implied_deltas(events: list[dict], n: int = 2) -> list[int]:
    out = [0] * n
    for e in events:
        for w in e["winners"]:
            out[w] += e["points"]
    return out


def test_events_itemise_every_mid_game_payout():
    """Over whole games: every score change is explained, every explanation adds up,
    and no move that scored nothing invents an event.

    This is the contract the UI chip depends on — a wrong itemisation next to a
    visible scoreboard is worse than no itemisation at all."""
    kinds: dict[str, dict] = {}
    scoring_moves = 0
    # (seed, seat). Seat is varied so the "You"/opponent naming is exercised from
    # both sides; (1, 0) is in the list because it is the cheapest game that closes a
    # CLOISTER — the one payout kind the others never happen to reach.
    for seed, seat in ((1, 0), (3, 1), (5, 0), (11, 1), (20, 0), (56, 1)):
        st = new(seed=seed, opponent="tier1", human_player=seat)
        prev = st["scores"]
        assert st["events"] == [], "a fresh game has paid out nothing"
        for _ in range(300):
            if st["is_terminated"]:
                break
            lg = st["legal"]
            if st["is_human_turn"]:
                pick = (lg["meeple_slots"][0]["action_id"]
                        if (st["phase"] == "meeples" and lg["meeple_slots"])
                        else lg["action_ids"][0])
                st = ok(B.apply_action(pick))
            else:
                st = ok(B.ai_move(st["generation"]))
            delta = [a - b for a, b in zip(st["scores"], prev)]
            events = st["events"]
            if st["is_terminated"]:
                # The engine's endgame pass consumes every remaining meeple inside
                # the terminating action; itemising that is the result dialog's job.
                assert events == [], "a terminal state must not itemise the endgame"
            else:
                if any(d > 0 for d in delta):
                    assert events, f"seed {seed}: scored {delta} with no explanation"
                    scoring_moves += 1
                else:
                    assert events == [], f"seed {seed}: invented {events}"
                assert _implied_deltas(events) == delta, (seed, events, delta)
                for e in events:
                    assert e["text"] and e["points"] > 0
                    kinds[e["kind"]] = e
            prev = st["scores"]
    assert scoring_moves >= 20, f"only {scoring_moves} scoring moves exercised"
    # `score` is the coarse fallback; it must never be needed on a base+farmers game.
    assert "score" not in kinds, f"fell back to an unexplained payout: {kinds['score']}"
    assert {"city", "road", "cloister"} <= set(kinds), sorted(kinds)


def test_event_for_a_closed_city_names_the_points_and_the_meeples():
    """A specific, hand-checked completion: find the move that closes a city and
    assert the whole event, not just that one arrived."""
    st = new(seed=5, opponent="tier1", human_player=0)
    found = None
    for _ in range(300):
        if st["is_terminated"]:
            break
        lg = st["legal"]
        if st["is_human_turn"]:
            pick = (lg["meeple_slots"][0]["action_id"]
                    if (st["phase"] == "meeples" and lg["meeple_slots"])
                    else lg["action_ids"][0])
            st = ok(B.apply_action(pick))
        else:
            st = ok(B.ai_move(st["generation"]))
        city = next((e for e in st["events"] if e["kind"] == "city"), None)
        if city is not None:
            found = (city, st)
            break
    assert found is not None, "no city closed in 300 plies"
    city, st = found
    assert set(city) == {"kind", "points", "winners", "meeples_returned", "text"}
    # A finished city pays 2/tile (+2 per shield), so anything under 4 is impossible.
    assert city["points"] >= 4 and city["points"] % 2 == 0, city
    assert 1 <= city["meeples_returned"] <= 7
    assert city["winners"], "a payout with no winner is not a payout"
    assert city["text"].startswith("City completed — ")
    assert f"+{city['points']}" in city["text"]
    assert f"{city['meeples_returned']} meeple" in city["text"]
    # ...and the seats named match the winners.
    for w in city["winners"]:
        assert ("You" if w == st["human_player"] else "Tier-1") in city["text"]
    # The meeples really came back to their owners' hands.
    assert sum(st["meeples_free"]) > 0


def test_events_describe_only_the_latest_decision():
    """`events` is replaced per decision, never accumulated — otherwise the chip
    would keep re-announcing a city that closed five moves ago."""
    st = new(seed=5, opponent="tier1", human_player=0)
    scored_at = None
    for i in range(300):
        if st["is_terminated"]:
            break
        lg = st["legal"]
        st = (ok(B.apply_action(lg["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
        if st["events"]:
            scored_at = i
            break
    assert scored_at is not None
    # ...and a plain get_state re-reads the same decision's events, unchanged.
    assert ok(B.get_state())["events"] == st["events"]
    # The next decision that pays nothing clears them.
    for _ in range(300):
        if st["is_terminated"]:
            break
        lg = st["legal"]
        st = (ok(B.apply_action(lg["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
        if not st["events"]:
            break
    assert st["events"] == []


def test_events_survive_the_claim_that_scores_instantly():
    """Claiming a feature the tile you just laid ALREADY completed places and
    collects the meeple inside one engine call, so it appears in neither state — the
    hole the `claims` argument closes. Without it the bridge falls back to a bare
    '+N', which this asserts does not happen."""
    # Seeds are a fixture, and the trajectory they produce depends on the GRID:
    # (5, 11, 20, 56, 3) all hit on the walled engine6 grid and none of them hit
    # on centered18 (the app default since 2026-08-02), because a different
    # legal-move set is a different game from ply one. 19 and 46 hit 4x each on
    # centered18; both lists are kept so the fixture is not brittle either way.
    hits = 0
    for seed in (5, 11, 20, 56, 3, 19, 46):
        st = new(seed=seed, opponent="tier1", human_player=0)
        for _ in range(300):
            if st["is_terminated"]:
                break
            lg = st["legal"]
            if st["is_human_turn"] and st["phase"] == "meeples" and lg["meeple_slots"]:
                before = ok(B.get_state())["scores"]
                st = ok(B.apply_action(lg["meeple_slots"][0]["action_id"]))
                gained = [a - b for a, b in zip(st["scores"], before)]
                if not st["is_terminated"] and any(g > 0 for g in gained):
                    hits += 1
                    assert st["events"], gained
                    assert all(e["kind"] != "score" for e in st["events"]), st["events"]
                    assert _implied_deltas(st["events"]) == gained
                continue
            st = (ok(B.apply_action(lg["action_ids"][0])) if st["is_human_turn"]
                  else ok(B.ai_move(st["generation"])))
    assert hits > 0, "never hit an instantly-scoring claim; the fixture is stale"


def test_restored_and_undone_sessions_report_no_events():
    """A replayed decision was not *played*, so claiming it just happened would be a
    lie — and an undo un-does the thing the chip was describing."""
    st = new(seed=5, opponent="tier1", human_player=0)
    for _ in range(300):
        if st["is_terminated"] or st["events"]:
            break
        lg = st["legal"]
        st = (ok(B.apply_action(lg["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    assert st["events"], "fixture needs a scoring move"
    assert ok(B.restore_game(json.dumps(ok(B.save_game()))))["events"] == []

    st = new(seed=5, opponent="tier1", human_player=0)
    st = _to_human_meeple_phase(st, min_actions=12)
    assert ok(B.undo_last_tile())["events"] == []


# --------------------------------------------------------------------------- #
# undo_last_tile — take the tile back inside the meeple sub-phase                #
# --------------------------------------------------------------------------- #
def _to_human_meeple_phase(st: dict, *, limit: int = 80, min_actions: int = 0) -> dict:
    """Advance until the HUMAN is in the meeple sub-phase with something to place.

    ``min_actions`` walks past the opening first: the very first placement often has
    only ONE legal square, which is no use to a test that needs an alternative."""
    for _ in range(limit):
        if st["is_terminated"]:
            break
        if (st["is_human_turn"] and st["phase"] == "meeples"
                and st["legal"]["meeple_slots"] and st["n_actions"] >= min_actions):
            return st
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    raise AssertionError("never reached a human meeple sub-phase with slots")


def test_undo_last_tile_returns_to_the_tile_decision():
    st = new(seed=5, opponent="tier1", human_player=0)
    st = _to_human_meeple_phase(st)
    before_log = list(B._S.action_log)
    placed = st["legal"]["meeple_target"]
    generation = st["generation"]

    out = ok(B.undo_last_tile())
    assert_state_schema(out)
    assert out["phase"] == "tiles" and out["is_human_turn"]
    assert out["undone"]["action_id"] == before_log[-1]
    assert B._S.action_log == before_log[:-1]
    assert out["n_actions"] == len(before_log) - 1
    # The tile really came off the board, and its square is choosable again.
    assert [placed["row"], placed["col"]] not in [[t["row"], t["col"]] for t in out["board"]]
    assert (placed["row"], placed["col"]) in {
        (c["row"], c["col"]) for c in out["legal"]["tile_cells"]
    }
    # The session label is deliberately NOT bumped: the UI keys its opening camera
    # fit on it and an undo is not a new game.
    assert out["generation"] == generation


def test_undo_last_tile_then_replacing_matches_never_having_placed_it():
    """The undo is exact, not approximate: undo + place elsewhere is
    indistinguishable from having placed there in the first place."""
    def run(detour: bool) -> dict:
        st = new(seed=11, opponent="tier1", human_player=0)
        st = _to_human_meeple_phase(st, min_actions=12)
        original = B._S.action_log[-1]
        if detour:
            back = ok(B.undo_last_tile())
            pre = ok(B.save_game())          # the position before the tile went down
            alt = next((c["action_ids"][0] for c in reversed(back["legal"]["tile_cells"])
                        if c["action_ids"][0] != original), None)
            assert alt is not None, "this fixture needs a second legal square"
            probe = ok(B.apply_action(alt))
            if probe["is_human_turn"] and probe["phase"] == "meeples":
                ok(B.undo_last_tile())       # take the WRONG placement back
            else:
                # The alternative had no meeple choice, so the bridge auto-passed
                # straight out of the undo window; rewind by the ordinary restore.
                ok(B.restore_game(json.dumps(pre)))
            st = ok(B.apply_action(original))
        return play_out(st)

    plain = run(detour=False)
    detoured = run(detour=True)
    assert plain["scores"] == detoured["scores"]
    assert plain["n_actions"] == detoured["n_actions"]
    assert ok(B.save_game())["actions"] == B._S.action_log


def test_undo_last_tile_leaves_no_trace_in_the_save_or_the_archive():
    """An undone action must not survive into the autosave — and therefore cannot
    reach the archive, which is built on the same payload and replays it."""
    st = new(seed=13, opponent="tier1", human_player=0)
    st = _to_human_meeple_phase(st)
    undone = B._S.action_log[-1]
    ok(B.undo_last_tile())
    saved = ok(B.save_game())
    assert saved["actions"] == B._S.action_log
    assert len(saved["actions"]) == 0 or saved["actions"][-1] != undone

    st = play_out(ok(B.get_state()))
    rec = ok(B.archive_record())
    assert rec["actions"] == ok(B.save_game())["actions"]
    # the archive still replays — the truncated log is a valid game
    back = ok(B.restore_game(json.dumps(rec)))
    assert back["is_terminated"] and back["scores"] == rec["scores"]


def test_undo_last_tile_preserves_the_ai_timing_record():
    """A restore cannot reconstruct wall-clock, but no AI decision was removed, so
    the timings already collected still describe moves that are still in the log."""
    st = new(seed=13, opponent="tier1", human_player=1)     # AI moves first
    st = _to_human_meeple_phase(st)
    before = list(B._S.ai_elapsed)
    assert before, "this fixture needs at least one AI decision behind it"
    ok(B.undo_last_tile())
    assert B._S.ai_elapsed == before


def test_undo_last_tile_refuses_outside_its_window():
    B.reset()
    out = j(B.undo_last_tile())
    assert out["ok"] is False              # no session at all
    st = new(seed=5, opponent="tier1", human_player=0)
    out = j(B.undo_last_tile())
    assert out["ok"] is False and out["error"]["code"] == "not_meeple_phase"
    st = _to_human_meeple_phase(st)
    ok(B.undo_last_tile())
    # ...and having undone, the window is closed again
    out = j(B.undo_last_tile())
    assert out["ok"] is False and out["error"]["code"] == "not_meeple_phase"

    st = new(seed=7, opponent="tier1", human_player=0)
    st = ok(B.debug_fast_forward("yes-destroy-this-game"))
    out = j(B.undo_last_tile())
    assert out["ok"] is False and out["error"]["code"] == "game_over"


def test_undo_last_tile_keeps_the_champion_bit_identical():
    """The champion's per-move search seeds derive from ``_move_idx``; undoing a
    HUMAN action must not consume one."""
    st = new(seed=17, opponent="champion", human_player=0, **TINY)
    st = _to_human_meeple_phase(st)
    move_idx = B._S.agent._move_idx
    ok(B.undo_last_tile())
    assert B._S.agent._move_idx == move_idx
    assert B._S.agent._latched is False


# --------------------------------------------------------------------------- #
# get_ownership — the always-on feature shading                                 #
# --------------------------------------------------------------------------- #
def test_ownership_regions_are_engine_topology_not_guesswork():
    """Every reported region names a real (cell, side) of the feature, and the four
    kinds use the side vocabulary the renderer expects."""
    edges = {"top", "right", "bottom", "left"}
    corners = {"top_left", "top_right", "bottom_left", "bottom_right"}
    allowed = {"city": edges, "road": edges, "chapel": {"center"}, "farm": corners}
    seen = set()
    # Which feature kinds a scripted walk happens to produce is an accident of the
    # deck, so sweep a few seeds rather than pinning the coverage to one game (a
    # single seed made this brittle to the retail start-tile rule, which shifts
    # every game from a given seed).
    for seed in (5, 11, 23, 29):
        if {"city", "road", "farm"} <= seen:
            break
        st = new(seed=seed, opponent="tier1", human_player=0)
        for _ in range(80):
            if st["is_terminated"]:
                break
            st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
                  else ok(B.ai_move(st["generation"])))
            for f in ok(B.get_ownership())["features"]:
                assert f["regions"], f"{f['kind']} reported no regions to draw"
                cells = {tuple(c) for c in f["cells"]}
                for row, col, side in f["regions"]:
                    assert isinstance(row, int) and isinstance(col, int)
                    # A region may never appear on a tile the feature does not occupy —
                    # over-coverage inside a tile is an approximation, a region on the
                    # wrong tile would be a lie.
                    assert (row, col) in cells, (f["kind"], row, col)
                    assert side in allowed[f["kind"]], (f["kind"], side)
                    assert side in B.MEEPLE_OFFSET_RATIO, side
                seen.add(f["kind"])
    assert {"city", "road", "farm"} <= seen, f"only exercised {sorted(seen)}"


def test_ownership_reports_the_feature_a_placed_meeple_claims():
    st = new(seed=5, opponent="tier1", human_player=0)
    assert ok(B.get_ownership())["features"] == [], "nothing is claimed yet"

    st = ok(B.apply_action(st["legal"]["tile_cells"][0]["action_ids"][0]))
    slots = st["legal"]["meeple_slots"]
    assert slots, "this fixture needs a placeable meeple"
    slot = slots[0]
    target = st["legal"]["meeple_target"]
    me = st["current_player"]
    st = ok(B.apply_action(slot["action_id"]))

    feats = ok(B.get_ownership())["features"]
    assert len(feats) == 1
    f = feats[0]
    assert f["kind"] in ("city", "road", "chapel", "farm")
    assert [target["row"], target["col"]] in f["cells"], \
        "the claimed feature must cover the tile the meeple stands on"
    assert f["owners"] == [me]
    assert f["meeple_count_per_player"][me] == 1
    assert sum(f["meeple_count_per_player"]) == 1


def test_ownership_dedupes_two_meeples_in_one_feature_and_is_read_only():
    """Two meeples in one feature is ONE feature, and the walk mutates nothing."""
    st = new(seed=5, opponent="tier1", human_player=0)
    for _ in range(60):
        if st["is_terminated"]:
            break
        st = ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"] \
            else ok(B.ai_move(st["generation"]))
        before = ok(B.get_state())
        feats = ok(B.get_ownership())["features"]
        assert ok(B.get_state()) == before, "get_ownership must not mutate the state"
        keys = [(f["kind"], tuple(map(tuple, f["cells"]))) for f in feats]
        assert len(keys) == len(set(keys)), "features must be deduped"
        placed = sum(len(p) for p in B._S.board.state.placed_meeples)
        claimed = sum(sum(f["meeple_count_per_player"]) for f in feats)
        # Every placed meeple belongs to exactly one reported feature (big meeples
        # are out of scope, so a count is a headcount).
        assert claimed == placed, f"{claimed} claimed vs {placed} on the board"


# --------------------------------------------------------------------------- #
# get_bag — public information only                                             #
# --------------------------------------------------------------------------- #
def test_bag_totals_match_the_base_distribution():
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts

    st = new(seed=5, opponent="tier1", human_player=0)
    bag = ok(B.get_bag())
    assert len(bag["faces"]) == len(base_tile_counts) == 32
    assert sum(f["total"] for f in bag["faces"]) == sum(base_tile_counts.values()) == 72
    for face in bag["faces"]:
        assert face["total"] == base_tile_counts[face["description"]]
        assert 0 <= face["remaining"] <= face["total"]
        assert face["image"], "a face needs art to render"


def test_bag_remaining_tracks_the_deck_without_ever_reading_it():
    """The invariant that proves it is public info: `remaining` is derived from the
    BOARD and the tile in hand, yet must equal `len(deck)` at every ply."""
    st = new(seed=5, opponent="tier1", human_player=0)
    for _ in range(50):
        if st["is_terminated"]:
            break
        bag = ok(B.get_bag())
        assert bag["total_remaining"] == bag["deck_remaining"] == st["deck_remaining"]
        if st["phase"] == "tiles":
            # The tile in hand is seen, so it is excluded from the bag.
            assert bag["in_hand"] == st["next_tile"]["description"]
        else:
            # ...but in the meeple phase `next_tile` is the tile ALREADY on the
            # board (the engine redraws only at the end of the sub-phase), so it
            # must not be subtracted a second time.
            assert bag["in_hand"] is None
        st = ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"] \
            else ok(B.ai_move(st["generation"]))


def test_bag_counts_a_rotated_tile_against_its_own_face():
    """`Tile.turn(n)` preserves `description`, which is what the bag counts by."""
    st = new(seed=21, opponent="tier1", human_player=0)
    st = play_out(st)
    bag = ok(B.get_bag())
    assert bag["total_remaining"] == 0, "a finished game has emptied the bag"
    assert all(f["remaining"] == 0 for f in bag["faces"])


# --------------------------------------------------------------------------- #
# archive_record — the finished-game record                                     #
# --------------------------------------------------------------------------- #
def test_save_game_still_works_at_a_terminated_state():
    """The archive is built on `save_game`, so this precondition is load-bearing."""
    st = new(seed=7, opponent="tier1", human_player=0)
    st = ok(B.debug_fast_forward("yes-destroy-this-game"))
    assert st["is_terminated"]
    saved = ok(B.save_game())
    assert saved["deck_seed"] == 7
    assert len(saved["actions"]) == st["n_actions"] > 0


def test_archive_record_is_a_superset_of_the_save_and_replays():
    st = new(seed=7, opponent="tier1", human_player=0)
    st = ok(B.debug_fast_forward("yes-destroy-this-game"))
    saved = ok(B.save_game())
    rec = ok(B.archive_record())

    assert rec["schema"] == B.ARCHIVE_SCHEMA
    # the restorable core is byte-identical to the autosave
    for key in ("deck_seed", "actions", "human_player", "opponent", "sims", "k_dets"):
        assert rec[key] == saved[key], key
    # ...plus the read-only summary the list needs without replaying anything
    assert rec["result"]["verdict"] == st["result"]["verdict"]
    assert rec["scores"] == st["scores"]
    assert rec["result"]["breakdown"] is not None
    assert rec["tiles_placed"] == len(st["board"]) == 72
    assert isinstance(rec["finished_at"], int) and rec["finished_at"] > 0
    assert rec["opponent_name"] == st["opponent_name"]
    assert all(set(e) == {"ply", "elapsed_s"} for e in rec["ai_elapsed"])

    # and the whole record restores by the same root_replay contract
    back = ok(B.restore_game(json.dumps(rec)))
    assert back["is_terminated"] and back["scores"] == rec["scores"]


def test_archive_record_refuses_a_game_still_in_progress():
    new(seed=5, opponent="tier1", human_player=0)
    out = j(B.archive_record())
    assert out["ok"] is False and out["error"]["code"] == "not_terminated"


def test_debug_fast_forward_is_guarded():
    new(seed=5, opponent="tier1", human_player=0)
    out = j(B.debug_fast_forward())
    assert out["ok"] is False and out["error"]["code"] == "not_confirmed"
    assert j(B.debug_fast_forward("please"))["ok"] is False


# --------------------------------------------------------------------------- #
# Retail fixed start tile (2026-07-30) — app-only rules fidelity                #
# --------------------------------------------------------------------------- #
def test_app_default_start_rule_is_retail():
    """The app plays the retail convention: the fixed D tile is already on the
    board before the human's first move, and it is nobody's move."""
    st = new(seed=11)
    assert st["deck_remaining"] + 1 == 71, "retail leaves 71 tiles to draw"
    assert len(st["board"]) == 1, f"expected only the pre-placed start tile: {st['board']}"
    assert st["board"][0]["description"] == B.RETAIL_START_TILE
    assert st["board"][0]["turns"] == 0
    assert st["current_player"] == 0 and st["is_human_turn"]
    assert st["phase"] == "tiles"
    assert st["meeples_free"] == [7, 7]
    # A real choice, not the engine rule's single forced placement.
    assert len(st["legal"]["tile_cells"]) > 1


def test_start_rule_travels_in_the_save():
    new(seed=11)
    save = ok(B.save_game())
    assert save["start_rule"] == B.START_RULE_RETAIL


def test_unknown_start_rule_is_rejected_not_guessed():
    """Silently picking a rule would decode a different game from the same log."""
    d = j(B.new_game(json.dumps({"seed": 5, "start_rule": "nonsense"})))
    assert d["ok"] is False and d["error"]["code"] == "ValueError"
    d = j(B.restore_game(json.dumps(
        {"schema": B.SAVE_SCHEMA, "deck_seed": 5, "actions": [],
         "human_player": 0, "start_rule": "nonsense"})))
    assert d["ok"] is False and d["error"]["code"] == "ValueError"


def test_engine_start_rule_still_available():
    """An explicit "engine" game reproduces the historical setup: empty board, a
    single forced first placement, 72 tiles to place."""
    st = new(seed=11, start_rule=B.START_RULE_ENGINE)
    assert st["board"] == []
    assert st["deck_remaining"] + 1 == 72
    assert len(st["legal"]["tile_cells"]) == 1


def test_a_save_without_start_rule_restores_under_the_engine_rule():
    """Backward compatibility: games archived before the retail start shipped
    carry no `start_rule`, and MUST replay under the convention they were played
    under — otherwise (deck_seed, actions) silently decodes a different game."""
    st = new(seed=23, start_rule=B.START_RULE_ENGINE, **TINY)
    for _ in range(6):
        if st["is_terminated"]:
            break
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    before = ok(B.get_state())
    save = ok(B.save_game())
    legacy = {k: v for k, v in save.items() if k != "start_rule"}
    assert "start_rule" not in legacy

    restored = ok(B.restore_game(json.dumps(legacy)))
    assert _normalise_for_compare(restored) == _normalise_for_compare(before)


def test_retail_save_round_trips():
    st = new(seed=29, **TINY)
    for _ in range(6):
        if st["is_terminated"]:
            break
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    before = ok(B.get_state())
    save = ok(B.save_game())
    assert save["start_rule"] == B.START_RULE_RETAIL
    restored = ok(B.restore_game(json.dumps(save)))
    assert _normalise_for_compare(restored) == _normalise_for_compare(before)


# --------------------------------------------------------------------------- #
# Start-tile GRID position (2026-08-02) — app-only recentring                    #
#                                                                              #
# Same shape as the retail `start_rule` block above, and for the same reason:   #
# a rules choice the APP makes, carried in the save payload, with the library   #
# default left alone. tests/test_start_tile_grid_bound.py owns the engine-level #
# claim (nothing rule-legal is denied on the recentred grid, and the strict-    #
# xfail sentinel proving the GLOBAL default did not move).                      #
# --------------------------------------------------------------------------- #
def test_app_default_grid_rule_is_centered18():
    """A NEW app game starts on the recentred grid: 18 rows of headroom above
    the start tile instead of 6. That is the fix for the "invisible border"."""
    assert B.GRID_RULE == B.GRID_RULE_CENTERED18
    st = new(seed=11)
    # The app plays retail too, so the start tile is on the board and visible.
    assert len(st["board"]) == 1
    assert (st["board"][0]["row"], st["board"][0]["col"]) == (18, 15)
    assert B._S.grid_row == 18 and B._S.grid_col == 15
    # Real headroom above, which is the whole point: every legal first placement
    # is well clear of row 0. (Not every neighbour cell is offered — the D tile
    # has a city on TOP, so the drawn tile has to match — hence >= not ==.)
    assert min(c["row"] for c in st["legal"]["tile_cells"]) >= 17
    # The invariant that says it is the SAME game, shifted: identical seed on the
    # walled grid gives the identical cell set 12 rows up.
    centered = {(c["row"], c["col"]) for c in st["legal"]["tile_cells"]}
    walled = {(c["row"], c["col"])
              for c in new(seed=11, grid_rule=B.GRID_RULE_ENGINE6)["legal"]["tile_cells"]}
    assert centered == {(r + 12, c) for r, c in walled} and walled


def test_grid_rule_travels_in_the_save_and_the_archive():
    new(seed=11)
    assert ok(B.save_game())["grid_rule"] == B.GRID_RULE_CENTERED18
    st = new(seed=11, opponent="tier1", **TINY)
    st = play_out(st)
    rec = ok(B.archive_record())
    assert rec["grid_rule"] == B.GRID_RULE_CENTERED18, \
        "the E4 manifest must record which grid the game was played on"


def test_unknown_grid_rule_is_rejected_not_guessed():
    """An action index is a WINDOW cell, so the same log decodes different board
    cells on a different grid — guessing would silently replay another game."""
    d = j(B.new_game(json.dumps({"seed": 5, "grid_rule": "centered17"})))
    assert d["ok"] is False and d["error"]["code"] == "ValueError"
    d = j(B.restore_game(json.dumps(
        {"schema": B.SAVE_SCHEMA, "deck_seed": 5, "actions": [],
         "human_player": 0, "grid_rule": "nonsense"})))
    assert d["ok"] is False and d["error"]["code"] == "ValueError"


def test_engine6_grid_still_available():
    """The historical grid stays reachable — it is what every archived game, and
    every eval number ever measured, was played on."""
    st = new(seed=11, grid_rule=B.GRID_RULE_ENGINE6)
    assert B._S.grid_row == 6
    assert (st["board"][0]["row"], st["board"][0]["col"]) == (6, 15)
    assert min(c["row"] for c in st["legal"]["tile_cells"]) >= 5


@pytest.mark.parametrize("grid_rule", [B.GRID_RULE_CENTERED18, B.GRID_RULE_ENGINE6, None])
def test_grid_rule_round_trips_through_save_restore(grid_rule):
    """All three values a payload can carry: both named grids and the ABSENT
    field, which means the walled engine6 grid forever."""
    cfg = dict(TINY, seed=23, opponent="tier1")
    if grid_rule is not None:
        cfg["grid_rule"] = grid_rule
    st = new(**cfg)
    for _ in range(8):
        if st["is_terminated"]:
            break
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    before = ok(B.get_state())
    save = ok(B.save_game())
    expect = B.GRID_RULE if grid_rule is None else grid_rule
    assert save["grid_rule"] == expect

    if grid_rule is None:
        # Simulate a PRE-2026-08-02 payload: no `grid_rule` key at all.
        legacy = {k: v for k, v in save.items() if k != "grid_rule"}
        legacy_before = ok(B.restore_game(json.dumps(
            dict(save, grid_rule=B.GRID_RULE_ENGINE6))))
        assert B._S.grid_rule == B.GRID_RULE_ENGINE6
        restored = ok(B.restore_game(json.dumps(legacy)))
        assert B._S.grid_rule == B.GRID_RULE_LEGACY == B.GRID_RULE_ENGINE6
        assert _normalise_for_compare(restored) == _normalise_for_compare(legacy_before)
        return

    restored = ok(B.restore_game(json.dumps(save)))
    assert B._S.grid_rule == expect
    assert _normalise_for_compare(restored) == _normalise_for_compare(before)


def test_the_same_log_on_the_other_grid_is_a_different_game():
    """WHY the field is load-bearing, demonstrated rather than asserted: replay
    the SAME (deck_seed, actions) under the other grid and the position differs
    (or the log is outright illegal there)."""
    st = new(seed=23, opponent="tier1", grid_rule=B.GRID_RULE_CENTERED18, **TINY)
    for _ in range(8):
        if st["is_terminated"]:
            break
        st = (ok(B.apply_action(st["legal"]["action_ids"][0])) if st["is_human_turn"]
              else ok(B.ai_move(st["generation"])))
    save = ok(B.save_game())
    same = ok(B.restore_game(json.dumps(save)))
    other = j(B.restore_game(json.dumps(dict(save, grid_rule=B.GRID_RULE_ENGINE6))))
    if other.get("ok"):
        assert _normalise_for_compare(other) != _normalise_for_compare(same), (
            "replaying under the wrong grid produced an identical position — "
            "then grid_rule would not need to be in the payload")
    else:
        assert other["error"]["code"] == "bad_save"
