"""JSON bridge between the Kotlin/Compose app and the production Carcassonne champion.

This is the ONLY hand-written Python under ``android/``. Everything else in the
on-device bundle is copied verbatim from the repo by ``android/tools/sync_python.py``.

DESIGN CONTRACTS
----------------
1. **Importable on desktop.** No ``android`` / ``java`` / ``com.chaquo`` imports, so the
   whole API is pytest-able (``tests/android/test_bridge.py``) and drivable from
   ``android/tools/smoke_selfplay.py``.
2. **Production leaf env FIRST.** The v2.7/v2.9 leaf reads ``CARCASSONNE_*`` knobs at
   *library import time*; ``champion_factory``'s verify RAISES if they were not set. So
   this module applies them via ``os.environ.setdefault`` at module top, BEFORE the
   first ``carcassonne_ai`` import. The values are a literal copy of
   ``scripts/human_anchor/env_preamble.PROD_ENV`` (that file is not in the on-device
   bundle); ``tests/android/test_bridge.py::test_prod_env_matches_repo_preamble``
   asserts the copy has not drifted.
3. **The YAML is the champion.** No strength knob is hardcoded here.
   ``champion_factory.PRODUCTION_YAML`` is a module global resolved at call time, so we
   point it at the bundled ``carcassonne_ai/data/PRODUCTION.yaml`` when that exists
   (device) and leave the repo's ``governance/PRODUCTION.yaml`` otherwise (desktop).
4. **All in/out is a JSON string** — Chaquopy marshals ``str`` cleanly and nothing else
   needs a type mapping. Every response is a JSON object carrying ``ok``; failures are
   ``{"ok": false, "error": {"code", "message"}}`` and never raise across the bridge.
5. **Determinism / save-restore.** The engine touches the global ``random`` stream in
   exactly one place (the deck shuffle inside ``get_init_board``), so a game is fully
   determined by ``(deck_seed, action_log)`` — the ``root_replay.py`` contract. Restore
   replays the log and re-seats the agent's ``_move_idx`` (its per-move search seeds are
   derived from it) and its exact-endgame latch.

THREADING (what Kotlin must respect)
------------------------------------
``new_game`` / ``apply_action`` / ``ai_move`` / ``save_game`` / ``restore_game`` mutate
the single module session and must all run on ONE thread (the app uses a single-thread
coroutine dispatcher). ``get_progress`` is the sole exception: it reads module-global
ints only and is safe to poll from the UI thread while ``ai_move`` blocks.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. Production leaf env — MUST precede any carcassonne_ai import.             #
#    Literal copy of scripts/human_anchor/env_preamble.PROD_ENV (2026-07-27).  #
# --------------------------------------------------------------------------- #
PROD_ENV: dict[str, str] = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
for _k, _v in PROD_ENV.items():
    os.environ.setdefault(_k, _v)
# The knobs as they stood the instant before carcassonne_ai was first imported — i.e.
# the leaf shape this process actually froze into ``virtual_score_v2.DEFAULT_CONFIG``.
# (A later importer may rewrite os.environ; that no longer changes this process's leaf,
# so RESOLVED_ENV, not os.environ, is the honest record for a manifest or a test.)
RESOLVED_ENV: dict[str, str] = {k: os.environ.get(k, "") for k in PROD_ENV}

# Desktop convenience: when the repo tree is visible above this file and the package is
# not installed, make src/ importable. On device this resolves to a path that does not
# exist and is skipped. (android/app/src/main/python/android_bridge.py -> parents[4] is
# `android`, parents[5] is the repo root.)
_HERE = Path(__file__).resolve()
_MAYBE_REPO = _HERE.parents[5] if len(_HERE.parents) > 5 else None
if _MAYBE_REPO is not None and (_MAYBE_REPO / "src" / "carcassonne_ai").is_dir():
    _src = str(_MAYBE_REPO / "src")
    if _src not in sys.path:
        sys.path.append(_src)   # append, never prepend: an installed copy still wins

import numpy as np  # noqa: E402

from carcassonne_ai import champion_factory  # noqa: E402
from carcassonne_ai.action_space import (  # noqa: E402
    decode,
    meeple_pass_index,
    tile_action_count,
    tile_pass_index,
)
from carcassonne_ai.game_wrapper import Board, Game  # noqa: E402
from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction  # noqa: E402
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402

SAVE_SCHEMA = "carcassonne-android-save/v1"
STATE_SCHEMA = "carcassonne-android-state/v1"

# Meeple-dot placement, as RATIOS of the tile size, lifted from
# CarcassonneVisualiser.meeple_position_offsets (tile_size=60, meeple_size=~21). The
# visualiser itself is excluded from the bundle (tkinter/PIL), so the numbers travel
# here and the Compose canvas multiplies them by its own tile size.
MEEPLE_OFFSET_RATIO: dict[str, tuple[float, float]] = {
    "top": (0.5, 0.175),
    "right": (0.825, 0.5),
    "bottom": (0.5, 0.825),
    "left": (0.175, 0.5),
    "center": (0.5, 0.5),
    "top_left": (0.25, 0.175),
    "top_right": (0.75, 0.175),
    "bottom_left": (0.25, 0.825),
    "bottom_right": (0.75, 0.825),
}


# --------------------------------------------------------------------------- #
# 2. Bundled PRODUCTION.yaml                                                    #
# --------------------------------------------------------------------------- #
def _resolve_production_yaml() -> str:
    """Point ``champion_factory.PRODUCTION_YAML`` at the bundled YAML when present.

    On device the package lives at ``<bundle>/carcassonne_ai/`` and the factory's
    ``REPO = parents[2]`` guess is meaningless, so the bundled copy at
    ``carcassonne_ai/data/PRODUCTION.yaml`` is authoritative. On desktop that file does
    not exist and the factory's repo path is already correct."""
    import carcassonne_ai

    bundled = Path(carcassonne_ai.__file__).resolve().parent / "data" / "PRODUCTION.yaml"
    if bundled.is_file():
        champion_factory.PRODUCTION_YAML = bundled
        return str(bundled)
    return str(champion_factory.PRODUCTION_YAML)


PRODUCTION_YAML_PATH = _resolve_production_yaml()


# --------------------------------------------------------------------------- #
# 3. Pure helpers (ported from scripts/play_vs_tier1_gui.py:118-188, no tkinter) #
# --------------------------------------------------------------------------- #
def legal_rotations_at_cell(game: Game, board: Board, row: int, col: int) -> list[int]:
    off = board.offset
    win = off.to_window(Coordinate(row=row, column=col))
    if win is None:
        return []
    wr, wc = win
    base = (wr * off.size + wc) * 4
    mask = game.get_valid_moves(board)
    return [r for r in range(4) if mask[base + r]]


def tile_action_index(off, row: int, col: int, rot: int) -> int:
    win = off.to_window(Coordinate(row=row, column=col))
    if win is None:
        raise ValueError(f"cell ({row},{col}) is outside the action window")
    wr, wc = win
    return (wr * off.size + wc) * 4 + rot


def all_legal_tile_cells(game: Game, board: Board) -> set[tuple[int, int]]:
    mask = game.get_valid_moves(board)
    off = board.offset
    n_tile = tile_action_count(off.size)
    cells: set[tuple[int, int]] = set()
    for idx in np.flatnonzero(mask[:n_tile]):
        cell, _rot = divmod(int(idx), 4)
        wr, wc = divmod(cell, off.size)
        coord = off.to_engine(wr, wc)
        cells.add((coord.row, coord.column))
    return cells


def legal_meeple_indices(game: Game, board: Board) -> list[int]:
    mask = game.get_valid_moves(board)
    off = board.offset
    n_tile = tile_action_count(off.size)
    pass_idx = meeple_pass_index(off.size)
    return [int(i) for i in np.flatnonzero(mask)
            if int(i) >= n_tile and int(i) != pass_idx]


def _terrain_name(tile, side: Side) -> str:
    t = tile.get_type(side)
    return t.name if t is not None else "GRASS"


def format_action(idx: int, board: Board) -> str:
    """Human-readable string for a flat action index in the board's current phase."""
    phase = board.state.phase.value
    if phase == "tiles":
        if idx == tile_pass_index(board.offset.size):
            return "pass (no legal placement)"
        action = decode(idx, off=board.offset, phase="tiles",
                        next_tile=board.state.next_tile)
        assert isinstance(action, TileAction)
        c = action.coordinate
        return f"tile @ ({c.row:+d}, {c.column:+d}) rot={action.tile_rotations}"
    if idx == meeple_pass_index(board.offset.size):
        return "skip meeple"
    last = board.state.last_tile_action
    last_coord = last.coordinate if last is not None else None
    action = decode(idx, off=board.offset, phase="meeples", last_tile_coord=last_coord)
    assert isinstance(action, MeepleAction)
    return f"{action.meeple_type.name} on {action.coordinate_with_side.side.name}"


def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand (the fair_agent.k_remaining band)."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


# --------------------------------------------------------------------------- #
# 4. Progress counters — module globals, read WITHOUT the session lock.         #
# --------------------------------------------------------------------------- #
_prog_leaf_calls = 0        # cumulative evaluator calls for the CURRENT ai_move
_prog_expected = 0          # k_dets * sims (the nominal leaf budget)
_prog_t0 = 0.0              # perf_counter at ai_move entry; 0.0 == idle
_prog_thinking = False
_agent_ref = None           # the live agent, for a lock-free `_latched` read


def _wrap_evaluator_with_counter(agent) -> None:
    """Wrap ``agent._evaluator`` in a counting closure (the cheapest honest seam).

    ``FairHeuristicPriorAgent`` reads ``self._evaluator`` afresh on every
    ``NeuralMCTS`` construction inside ``_pimc_move``, so wrapping AFTER construction
    is picked up by every subsequent search. The wrapper forwards ``*args`` because
    ``NeuralMCTS`` calls ``evaluator(board)`` or ``evaluator(board, parent)`` depending
    on the evaluator's ``wants_parent`` flag (absent on the production evaluator)."""
    inner = getattr(agent, "_evaluator", None)
    if inner is None:                     # tier1 (RuleBasedPlayer) has no evaluator
        return

    def counting(*args):
        global _prog_leaf_calls
        _prog_leaf_calls += 1
        return inner(*args)

    if getattr(inner, "wants_parent", False):
        counting.wants_parent = True
    agent._evaluator = counting


# --------------------------------------------------------------------------- #
# 5. The session                                                                #
# --------------------------------------------------------------------------- #
class _Session:
    """Everything one game needs. One instance lives in the module global ``_S``."""

    def __init__(self, *, seed: int, human_player: int, opponent: str,
                 sims: int | None, k_dets: int | None, verify: bool,
                 generation: int):
        self.seed = int(seed)
        self.human_player = int(human_player)
        self.opponent_kind = str(opponent)
        self.req_sims = None if sims is None else int(sims)
        self.req_k_dets = None if k_dets is None else int(k_dets)
        self.verify = bool(verify)
        self.generation = int(generation)

        self.game = Game(enable_legal_moves_cache=True)
        # The agent gets its OWN Game (mirrors play_vs_tier1_gui.build_opponent): the
        # UI-side Game carries a legal-moves cache and the agent may run on another
        # thread, so private Games remove any chance of a cross-thread cache race.
        self.ai_game = Game(enable_legal_moves_cache=True)

        self.agent = None
        self.pick = None
        self.manifest = None
        self.budget_note = None
        self.opponent_name = ""
        self.eff_sims = 0
        self.eff_k_dets = 0
        self._build_opponent()

        # Deck seeding must be the LAST thing before get_init_board: the engine draws
        # its shuffle from the GLOBAL random stream there and nowhere else, which is
        # what makes (deck_seed, action_log) a lossless save (root_replay contract).
        random.seed(self.seed)
        self.board: Board = self.game.get_init_board()

        self.action_log: list[int] = []
        self.turn = 0
        self.ai_last_tile: tuple[int, int] | None = None
        self.ai_last_move: dict | None = None

    # -- opponent construction (mirrors play_vs_tier1_gui.build_opponent) ----
    def _build_opponent(self) -> None:
        if self.opponent_kind == "tier1":
            from carcassonne_ai.rule_based_player import RuleBasedPlayer

            tier1 = RuleBasedPlayer(seed=self.seed)
            self.agent = tier1
            self.pick = lambda board: int(
                tier1.choose_action(self.ai_game, board,
                                    self.ai_game.get_valid_moves(board)))
            self.opponent_name = "Tier-1"
            self.budget_note = None
            self.eff_sims = 0
            self.eff_k_dets = 0
            return

        if self.opponent_kind != "champion":
            raise ValueError(f"opponent must be 'champion'|'tier1'; got "
                             f"{self.opponent_kind!r}")

        spec = champion_factory.load_production_spec()
        eff_sims = spec.sims_per_det if self.req_sims is None else int(self.req_sims)
        eff_k = spec.k_dets if self.req_k_dets is None else int(self.req_k_dets)
        agent = champion_factory.make_production_champion(
            "fair", game=self.ai_game, seed=self.seed, sims=eff_sims, k_dets=eff_k,
            exact_endgame=True, verify=self.verify,
        )
        _wrap_evaluator_with_counter(agent)
        self.agent = agent
        self.pick = lambda board: int(agent.choose_action(board))
        self.manifest = getattr(agent, "manifest", None)
        self.eff_sims, self.eff_k_dets = eff_sims, eff_k

        self.opponent_name = "Champion"
        self.budget_note = None
        if (eff_sims, eff_k) != (spec.sims_per_det, spec.k_dets):
            full = spec.k_dets * spec.sims_per_det
            self.budget_note = (
                f"BELOW CHAMPION BUDGET — running k{eff_k}x{eff_sims}="
                f"{eff_k * eff_sims} sims/move vs the champion's "
                f"k{spec.k_dets}x{spec.sims_per_det}={full}. This is a WEAKENED agent; "
                f"beating it is not beating the champion.")
            self.opponent_name = f"Champion(weakened k{eff_k}x{eff_sims})"

    # -- board mechanics ----------------------------------------------------
    @property
    def ai_player(self) -> int:
        return 1 - self.human_player

    def legal_mask(self):
        return self.game.get_valid_moves(self.board)

    def legal_ids(self) -> list[int]:
        return [int(i) for i in np.flatnonzero(self.legal_mask())]

    def _pass_index(self) -> int:
        size = self.board.offset.size
        return (tile_pass_index(size) if self.board.state.phase == GamePhase.TILES
                else meeple_pass_index(size))

    def apply(self, action_id: int) -> None:
        self.board, _ = self.game.get_next_state(self.board, int(action_id))
        self.action_log.append(int(action_id))
        self.turn += 1

    def auto_pass_forced(self) -> int:
        """Auto-apply a forced pass on the HUMAN seat so the UI never renders a phase
        whose only legal action is 'pass'. Mirrors ``play_vs_tier1_gui._advance``.

        The AI seat is deliberately NOT auto-passed: the agent handles a forced move
        internally and must still burn one ``choose_action`` so its ``_move_idx`` (and
        therefore every per-move search seed) stays aligned with a replayed restore."""
        n = 0
        while not self.board.state.is_terminated():
            if self.board.state.current_player != self.human_player:
                break
            legal = self.legal_ids()
            if legal != [self._pass_index()]:
                break
            self.apply(legal[0])
            n += 1
        return n


_S: _Session | None = None
_GENERATION = 0


# --------------------------------------------------------------------------- #
# 6. State serialisation                                                        #
# --------------------------------------------------------------------------- #
def _tile_json(tile) -> dict:
    return {"image": getattr(tile, "image", None),
            "turns": int(getattr(tile, "turns", 0)),
            "description": getattr(tile, "description", "")}


def _board_tiles(state) -> list[dict]:
    out = []
    for coord in sorted(state.placed_coords, key=lambda c: (c.row, c.column)):
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        d = _tile_json(tile)
        d["row"], d["col"] = int(coord.row), int(coord.column)
        out.append(d)
    return out


def _placed_meeples(state) -> list[dict]:
    out = []
    for player, positions in enumerate(state.placed_meeples):
        for mp in positions:
            cws = mp.coordinate_with_side
            side = cws.side.value
            out.append({
                "player": int(player),
                "row": int(cws.coordinate.row),
                "col": int(cws.coordinate.column),
                "side": side,
                "type": mp.meeple_type.value,
                "offset_ratio": list(MEEPLE_OFFSET_RATIO.get(side, (0.5, 0.5))),
            })
    return out


def _legal_block(s: _Session) -> dict:
    """Legal moves for whoever is on turn, shaped for the Compose UI."""
    state = s.board.state
    empty = {"tile_cells": [], "meeple_slots": [], "meeple_target": None,
             "tile_pass_id": None, "meeple_pass_id": None, "action_ids": []}
    if state.is_terminated():
        return empty
    size = s.board.offset.size
    mask = s.legal_mask()
    ids = [int(i) for i in np.flatnonzero(mask)]
    block = dict(empty)
    block["action_ids"] = ids

    if state.phase == GamePhase.TILES:
        tp = tile_pass_index(size)
        block["tile_pass_id"] = tp if tp in ids else None
        cells = []
        for (row, col) in sorted(all_legal_tile_cells(s.game, s.board)):
            rots = legal_rotations_at_cell(s.game, s.board, row, col)
            cells.append({
                "row": row, "col": col, "rotations": rots,
                "action_ids": [tile_action_index(s.board.offset, row, col, r)
                               for r in rots],
            })
        block["tile_cells"] = cells
        return block

    mp = meeple_pass_index(size)
    block["meeple_pass_id"] = mp if mp in ids else None
    last = state.last_tile_action
    if last is None:
        return block
    coord = last.coordinate
    tile = state.board[coord.row][coord.column]
    block["meeple_target"] = {"row": int(coord.row), "col": int(coord.column)}
    slots = []
    for idx in legal_meeple_indices(s.game, s.board):
        action = decode(idx, off=s.board.offset, phase="meeples", last_tile_coord=coord)
        assert isinstance(action, MeepleAction)
        side = action.coordinate_with_side.side
        slots.append({
            "action_id": int(idx),
            "side": side.value,
            "type": action.meeple_type.value,
            "terrain": _terrain_name(tile, side) if tile is not None else "GRASS",
            "offset_ratio": list(MEEPLE_OFFSET_RATIO.get(side.value, (0.5, 0.5))),
            "describe": format_action(idx, s.board),
        })
    block["meeple_slots"] = slots
    return block


def _state_dict(s: _Session) -> dict:
    state = s.board.state
    terminated = bool(state.is_terminated())
    scores = [int(x) for x in state.scores]
    d = {
        "ok": True,
        "schema": STATE_SCHEMA,
        "generation": s.generation,
        "phase": state.phase.value,
        "turn": int(s.turn),
        "current_player": int(state.current_player),
        "human_player": int(s.human_player),
        "ai_player": int(s.ai_player),
        "is_human_turn": (not terminated
                          and int(state.current_player) == int(s.human_player)),
        "scores": scores,
        "meeples_free": [int(x) for x in state.meeples],
        "deck_remaining": int(len(state.deck)),
        "tiles_remaining": int(k_remaining(state)),
        "next_tile": _tile_json(state.next_tile) if state.next_tile is not None else None,
        "board": _board_tiles(state),
        "meeples": _placed_meeples(state),
        "legal": _legal_block(s),
        "opponent": s.opponent_kind,
        "opponent_name": s.opponent_name,
        "budget_note": s.budget_note,
        "ai_last_tile": ({"row": s.ai_last_tile[0], "col": s.ai_last_tile[1]}
                         if s.ai_last_tile is not None else None),
        "ai_last_move": s.ai_last_move,
        "is_terminated": terminated,
        "n_actions": len(s.action_log),
    }
    if terminated:
        diff = scores[0] - scores[1]
        if diff == 0:
            verdict, winner = "Tie!", None
        else:
            winner = 0 if diff > 0 else 1
            verdict = ("You win!" if winner == s.human_player
                       else f"{s.opponent_name} wins.")
        d["result"] = {"scores": scores, "diff": abs(diff), "winner": winner,
                       "verdict": verdict, "budget_note": s.budget_note}
    return d


# --------------------------------------------------------------------------- #
# 7. Response plumbing                                                          #
# --------------------------------------------------------------------------- #
def _err(code: str, message: str, **extra) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message}}
    payload.update(extra)
    return json.dumps(payload)


def _ok(d: dict) -> str:
    return json.dumps(d, default=str)


def _require_session() -> _Session:
    if _S is None:
        raise RuntimeError("no active game — call new_game() first")
    return _S


# --------------------------------------------------------------------------- #
# 8. Public API — every function takes/returns JSON strings                     #
# --------------------------------------------------------------------------- #
def new_game(config_json: str = "{}") -> str:
    """Start a game. ``config_json`` keys (all optional):

        seed          int, default 0     — deck seed AND agent seed
        human_player  0|1, default 0     — which seat the human plays
        opponent      "champion"|"tier1", default "champion"
        sims          int|null           — per-determinization sims (null = YAML budget)
        k_dets        int|null           — determinizations   (null = YAML budget)
        verify        bool, default true — champion_factory's runtime leaf proof

    Returns the full state object (see ``get_state``)."""
    global _S, _GENERATION, _prog_leaf_calls, _prog_expected, _prog_t0
    global _prog_thinking, _agent_ref
    try:
        cfg = json.loads(config_json) if config_json else {}
        if not isinstance(cfg, dict):
            return _err("bad_config", "config_json must be a JSON object")
        human_player = int(cfg.get("human_player", 0))
        if human_player not in (0, 1):
            return _err("bad_config", "human_player must be 0 or 1")
        _GENERATION += 1
        s = _Session(
            seed=int(cfg.get("seed", 0)),
            human_player=human_player,
            opponent=str(cfg.get("opponent", "champion")),
            sims=cfg.get("sims"),
            k_dets=cfg.get("k_dets"),
            verify=bool(cfg.get("verify", True)),
            generation=_GENERATION,
        )
        _S = s
        _agent_ref = s.agent
        _prog_leaf_calls = 0
        _prog_expected = max(0, s.eff_sims * s.eff_k_dets)
        _prog_t0 = 0.0
        _prog_thinking = False
        s.auto_pass_forced()
        return _ok(_state_dict(s))
    except Exception as exc:                      # noqa: BLE001 — never raise across JNI
        return _err(type(exc).__name__, str(exc))


def get_state() -> str:
    """The full UI state object for the live game."""
    try:
        return _ok(_state_dict(_require_session()))
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def apply_action(action_id) -> str:
    """Apply a HUMAN action. Validates against the legal mask, appends to the action
    log, then auto-applies any forced pass. Returns the new state (or a JSON error)."""
    try:
        s = _require_session()
        try:
            idx = int(action_id)
        except (TypeError, ValueError):
            return _err("illegal_action", f"action_id {action_id!r} is not an int")
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("illegal_action",
                        f"action {idx} is not legal in phase "
                        f"{s.board.state.phase.value}",
                        legal_action_ids=s.legal_ids())
        describe = format_action(idx, s.board)
        s.apply(idx)
        s.auto_pass_forced()
        out = _state_dict(s)
        out["applied"] = {"action_id": idx, "describe": describe}
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def ai_move(generation=None) -> str:
    """Run ONE AI decision (blocking; seconds at champion budget) and apply it.

    ``generation`` is the session generation Kotlin believes is current. A mismatch on
    entry is refused; a mismatch on EXIT (the user reset mid-search) discards the move
    instead of applying it to a board it was never computed for. The echoed
    ``generation`` lets the caller drop a stale result unconditionally."""
    global _prog_leaf_calls, _prog_t0, _prog_thinking, _prog_expected
    try:
        s = _require_session()
        gen = s.generation if generation is None else int(generation)
        if gen != s.generation:
            return _err("stale_generation",
                        f"generation {gen} != current {s.generation}",
                        generation=gen, current_generation=s.generation, stale=True)
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        if s.board.state.current_player == s.human_player:
            return _err("not_ai_turn", "it is the human's turn")

        board = s.board
        t0 = time.perf_counter()
        _prog_leaf_calls = 0
        _prog_expected = max(0, s.eff_sims * s.eff_k_dets)
        _prog_t0 = t0
        _prog_thinking = True
        try:
            idx = int(s.pick(board))
        finally:
            _prog_thinking = False
            _prog_t0 = 0.0
        elapsed_s = time.perf_counter() - t0

        if _S is not s or s.generation != gen:
            # Reset landed while we were thinking: the answer belongs to a board that
            # no longer exists. Drop it — never apply a move computed for another game.
            return _ok({"ok": True, "stale": True, "generation": gen,
                        "current_generation": (_S.generation if _S else None),
                        "action_id": idx})

        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("agent_illegal_action",
                        f"agent returned illegal action {idx}")
        describe = format_action(idx, s.board)
        if (s.board.state.phase == GamePhase.TILES
                and idx != tile_pass_index(s.board.offset.size)):
            act = decode(idx, off=s.board.offset, phase="tiles",
                         next_tile=s.board.state.next_tile)
            s.ai_last_tile = (int(act.coordinate.row), int(act.coordinate.column))
        s.ai_last_move = {"action_id": idx, "describe": describe,
                          "elapsed_s": round(elapsed_s, 4)}
        s.apply(idx)
        s.auto_pass_forced()

        out = _state_dict(s)
        out.update({"action_id": idx, "describe": describe,
                    "elapsed_s": round(elapsed_s, 4), "generation": gen,
                    "stale": False, "leaf_calls": _prog_leaf_calls})
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def get_progress() -> str:
    """Cheap, lock-free progress poll — the ONLY function safe to call while
    ``ai_move`` is blocking. Reads module-global ints and one agent bool."""
    try:
        t0 = _prog_t0
        thinking = bool(_prog_thinking)
        leaf_calls = int(_prog_leaf_calls)
        expected = int(_prog_expected)
        latched = bool(getattr(_agent_ref, "_latched", False))
        if not thinking:
            phase = "idle"
        elif latched:
            phase = "exact"     # exact-endgame solve: leaf counter does not move
        else:
            phase = "search"
        elapsed = (time.perf_counter() - t0) if (thinking and t0) else 0.0
        frac = (min(1.0, leaf_calls / expected) if (expected > 0 and phase == "search")
                else None)
        return _ok({"ok": True, "leaf_calls": leaf_calls, "expected": expected,
                    "elapsed_s": round(elapsed, 3), "phase": phase,
                    "fraction": frac})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def _spec_fingerprint() -> dict:
    """``{champion_id, leaf_hash}`` for the CURRENT PRODUCTION.yaml, or empty strings.

    Recorded in every save and re-checked on restore (see ``restore_game``'s
    ``save_mismatch``). The leaf hash matters for BOTH opponents, not just the
    champion: ``RuleBasedPlayer`` ranks its candidates with ``virtual_score``, so a
    leaf change moves tier-1's play too."""
    try:
        spec = champion_factory.load_production_spec()
        return {"champion_id": str(spec.champion_id),
                "leaf_hash": str(spec.yaml_leaf_hash)}
    except Exception:                             # noqa: BLE001 — never break a save
        return {"champion_id": "", "leaf_hash": ""}


def save_game() -> str:
    """Serialise the game to ``{deck_seed, actions, human_player, opponent, sims,
    k_dets, verify}`` — a few hundred ints. Losslessly restorable via
    ``restore_game`` (the root_replay contract).

    Also stamps the champion identity (``champion_id`` + the YAML ``leaf_hash``) so a
    save written by an older build can be RECOGNISED as such on restore. The stamp is
    advisory: ``restore_game`` warns, never refuses."""
    try:
        s = _require_session()
        out = {
            "ok": True,
            "schema": SAVE_SCHEMA,
            "deck_seed": s.seed,
            "actions": list(s.action_log),
            "human_player": s.human_player,
            "opponent": s.opponent_kind,
            "sims": s.req_sims,
            "k_dets": s.req_k_dets,
            "verify": s.verify,
        }
        out.update(_spec_fingerprint())
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def _replays_rng(agent) -> bool:
    """Does this agent need its RNG rebuilt by REPLAYING decisions?

    True for a stream-random agent (``RuleBasedPlayer``: one ``_rng`` advanced by every
    tie-break, no per-move seed). False for the champion, whose search seeds are derived
    from ``_move_idx`` — re-seating that integer is exact and free, and replaying its
    decisions would cost a full search per ply."""
    return hasattr(agent, "_rng") and not hasattr(agent, "_move_idx")


def _save_mismatch(blob: dict) -> dict | None:
    """Compare the save's champion stamp with the running one; ``None`` if they agree.

    Saves written before the stamp existed carry no fields and are treated as matching
    — an absent stamp is not evidence of a difference."""
    cur = _spec_fingerprint()
    fields = {}
    for key in ("champion_id", "leaf_hash"):
        was = str(blob.get(key, "") or "")
        now = str(cur.get(key, "") or "")
        if was and now and was != now:
            fields[key] = {"saved": was, "current": now}
    if not fields:
        return None
    return {
        "fields": fields,
        "message": ("This game was saved against a different champion build; the "
                    "opponent may now play differently from here on."),
    }


def restore_game(json_str: str) -> str:
    """Rebuild a session from ``save_game``'s payload and return the state.

    Replays the action log from the seeded init board, then re-seats the agent:
    ``_move_idx`` = the number of AI *decisions* replayed (its per-move search seeds
    derive from it, ``fair_agent.det_seed_base``) and ``_latched`` = whether the
    exact-endgame latch would already have fired. Without both, a restored game would
    silently play a different champion than the one that was saved.

    An agent whose randomness lives in a *stream* rather than a per-move seed —
    ``RuleBasedPlayer._rng``, which breaks virtual-score ties — cannot be re-seated by
    an index: ``Random.choice`` consumes a data-dependent number of ``getrandbits``
    calls (rejection sampling over ``len(best_local)``, the count of TIED-best actions,
    which is unknowable without scoring the position). So its stream is rebuilt the only
    exact way there is — by replaying the decisions themselves (see ``_replays_rng``).
    Measured before this was added: 12/12 seeds diverged after a mid-game restore."""
    global _S, _GENERATION, _prog_leaf_calls, _prog_expected, _prog_t0
    global _prog_thinking, _agent_ref
    try:
        blob = json.loads(json_str) if isinstance(json_str, str) else dict(json_str)
        if not isinstance(blob, dict):
            return _err("bad_save", "save payload must be a JSON object")
        schema = blob.get("schema", SAVE_SCHEMA)
        if schema != SAVE_SCHEMA:
            return _err("bad_save", f"unknown save schema {schema!r}")
        actions = [int(a) for a in blob.get("actions", [])]
        human_player = int(blob.get("human_player", 0))
        if human_player not in (0, 1):
            return _err("bad_save", "human_player must be 0 or 1")

        _GENERATION += 1
        s = _Session(
            seed=int(blob.get("deck_seed", 0)),
            human_player=human_player,
            opponent=str(blob.get("opponent", "champion")),
            sims=blob.get("sims"),
            k_dets=blob.get("k_dets"),
            verify=bool(blob.get("verify", True)),
            generation=_GENERATION,
        )

        # Replay. Whose decision each logged action was is decided by the board it was
        # played on — human auto-passes are logged too but never consume an AI decision.
        exact_max_k = int(getattr(s.agent, "_exact_max_k", 2))
        exact_on = bool(getattr(s.agent, "_exact_endgame", False))
        replay_rng = _replays_rng(s.agent)
        ai_decisions = 0
        latched = False
        for a in actions:
            st = s.board.state
            if st.is_terminated():
                return _err("bad_save",
                            f"action log is longer than the game ({len(actions)} "
                            f"actions, terminated after {ai_decisions} AI decisions)")
            is_ai_turn = int(st.current_player) != s.human_player
            if is_ai_turn:
                if exact_on and not latched:
                    if st.phase == GamePhase.TILES and k_remaining(st) <= exact_max_k:
                        latched = True
                ai_decisions += 1
            mask = s.game.get_valid_moves(s.board)
            if not (0 <= a < len(mask)) or not bool(mask[a]):
                return _err("bad_save",
                            f"replay hit an illegal action {a} at ply "
                            f"{len(s.action_log)}")
            if is_ai_turn and replay_rng:
                # Burn the agent's RNG stream exactly as live play did: same board,
                # same rng state in, therefore identical consumption out. The RETURNED
                # action is discarded — the log is authoritative — but it should equal
                # `a`, and a mismatch means the save predates a strength change (the
                # `save_mismatch` warning below is the user-visible half of that).
                s.pick(s.board)
            # Cosmetic parity with live play: rebuild the AI's last-move highlight so a
            # restored state deep-compares equal to the state that was saved (only the
            # un-reconstructable wall-clock is left None).
            if is_ai_turn:
                s.ai_last_move = {"action_id": int(a),
                                  "describe": format_action(a, s.board),
                                  "elapsed_s": None}
                if (st.phase == GamePhase.TILES
                        and a != tile_pass_index(s.board.offset.size)):
                    act = decode(a, off=s.board.offset, phase="tiles",
                                 next_tile=st.next_tile)
                    if isinstance(act, TileAction):
                        s.ai_last_tile = (int(act.coordinate.row),
                                          int(act.coordinate.column))
            s.apply(a)

        if hasattr(s.agent, "_move_idx"):
            s.agent._move_idx = ai_decisions
        if hasattr(s.agent, "_latched"):
            s.agent._latched = latched

        _S = s
        _agent_ref = s.agent
        _prog_leaf_calls = 0
        _prog_expected = max(0, s.eff_sims * s.eff_k_dets)
        _prog_t0 = 0.0
        _prog_thinking = False
        s.auto_pass_forced()
        out = _state_dict(s)
        out["restored"] = {"actions": len(actions), "ai_decisions": ai_decisions,
                           "latched": latched, "rng_replayed": replay_rng}
        # Advisory, never fatal: an old save still restores and still plays.
        mismatch = _save_mismatch(blob)
        if mismatch is not None:
            out["save_mismatch"] = mismatch
        return _ok(out)
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def get_manifest() -> str:
    """The champion's resolved runtime manifest (Settings sheet). ``null`` for Tier-1.

    With a live session this is the manifest of the agent that is ACTUALLY playing,
    budget override included. With no session — Settings opened before any game — it
    falls back to ``resolved_manifest("fair")``, the deterministic spec-derived
    manifest for the champion of record, so the sheet is never empty.
    ``manifest_source`` says which one you are looking at; never read a budget out of
    the ``spec`` variant and assume a game is running at it."""
    try:
        s = _S
        if s is None:
            return _ok({"ok": True, "manifest_source": "spec",
                        "manifest": champion_factory.resolved_manifest("fair"),
                        "production_yaml": PRODUCTION_YAML_PATH,
                        "opponent_name": "Champion (no game in progress)",
                        "budget_note": None})
        return _ok({"ok": True, "manifest_source": "session", "manifest": s.manifest,
                    "production_yaml": PRODUCTION_YAML_PATH,
                    "opponent_name": s.opponent_name,
                    "budget_note": s.budget_note})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def production_budget() -> str:
    """The YAML champion budget, so the UI never hardcodes a strength knob."""
    try:
        spec = champion_factory.load_production_spec()
        return _ok({"ok": True, "champion_id": spec.champion_id,
                    "sims_per_det": spec.sims_per_det, "k_dets": spec.k_dets,
                    "total_sims": spec.k_dets * spec.sims_per_det,
                    "exact_max_k": spec.exact_max_k,
                    "production_yaml": PRODUCTION_YAML_PATH})
    except Exception as exc:                      # noqa: BLE001
        return _err(type(exc).__name__, str(exc))


def reset() -> str:
    """Drop the session (bumps the generation so an in-flight ai_move is discarded)."""
    global _S, _GENERATION, _agent_ref, _prog_thinking, _prog_t0
    _GENERATION += 1
    _S = None
    _agent_ref = None
    _prog_thinking = False
    _prog_t0 = 0.0
    return _ok({"ok": True, "generation": _GENERATION})
