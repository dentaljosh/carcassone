"""AlphaZero-style Game wrapper around the wingedsheep Carcassonne engine.

Mirrors alpha-zero-general's Game.py method names so a Coach/Arena port is
trivial later, but does NOT inherit from it (its API assumes 2D board arrays).

Scope (2026-06-02 onward): 2 players, BASE tile set only, FARMERS supplementary
rule. River was DROPPED 2026-06-02 (competitive / world-championship play is
base-only; River is a non-scoring setup variant) — see DECISIONS.md. No Inns &
Cathedrals, no Abbots, no Big meeples. The engine still supports THE_RIVER if a
caller passes it explicitly, but production self-play/eval/training is base-only.

Window size is configurable via Game(window_size=...). Default is 25 based on
Phase 0 random-game measurements, but can be changed at construction time
without code changes if Phase 4 reveals 25 is wrong.
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import dataclass, field
from multiprocessing import Pool

import numpy as np

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
from wingedsheep.carcassonne.utils.action_util import ActionUtil
from wingedsheep.carcassonne.utils.state_updater import StateUpdater

from .action_space import (
    DEFAULT_WINDOW_SIZE,
    WindowOffset,
    WindowOverflowError,
    action_size,
    decode,
    encode,
)
from .board_repr import (
    N_CHANNELS,
    board_overflows_window,
    canonical_swap,
    centroid_sums,
    compute_window_offset,
    encode_board,
    offset_from_centroid_sums,
)
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from .eta import measure_one, print_banner
from .features import N_FARM_SCALARS, N_SCALAR_FEATURES, encode_scalars


SCORE_NORM_SCALE = 15.0  # see DECISIONS.md (validated against 1000 random games)

# WC tie-break (BACKLOG 2026-08-03 "WC tie-break rule flag"). The official WC
# rule resolves a tied final score by ruling the STARTING player the loser; our
# engine's incumbent behaviour is a symmetric draw. `Game(wc_tiebreak=True)`
# flips which seat's epsilon sign wins a tie in `get_game_ended` below.
# Magnitude is deliberately left at the SAME epsilon as the incumbent draw
# sentinel, not inflated to +-1.0: `get_game_ended` is a *margin*-flavored
# value (tanh(score_diff / SCORE_NORM_SCALE)), so a bigger tie magnitude would
# corrupt the margin scale every existing value target/leaf is calibrated
# against. The sign is what the WC rule determines; the magnitude is a
# separate (unmade) policy decision. The exact/unambiguous home for
# seat-asymmetric WC play is the WIN-objective exact solver (see
# scripts/level2/endgame_solver.py's `wc_tiebreak`), not this margin sentinel.
WC_TIE_VALUE = 1e-6


# --- Window-overflow audit (measurement-only, DEFAULT OFF) -------------------
# Phase 0.2 post-review measurement. `get_valid_moves` already computes
# n_total / n_overflow (how many legal actions the centered window drops) but
# exposes them nowhere, and `encode_board` silently skips placed tiles outside
# the window. When CARCASSONNE_WINDOW_AUDIT=1, `get_valid_moves` appends one
# per-decision record to `_WINDOW_AUDIT_LOG` so an offline replay can quantify
# both effects. When the env var is unset (the default) the audit block is
# skipped entirely — the mask, the raise condition, and every leaf/eval
# semantic are byte-for-byte identical to before this change (asserted in the
# audit script by confirming the log stays empty with the flag off). This is
# read-only instrumentation: it NEVER alters the returned mask.
_WINDOW_AUDIT = os.environ.get("CARCASSONNE_WINDOW_AUDIT", "0") == "1"
_WINDOW_AUDIT_LOG: list = []

# --- Legal-cache collision detector (Phase 0.3, DEFAULT OFF) -----------------
# When CARCASSONNE_CACHE_COLLIDE_CHECK=1, every legal-moves-cache HIT recomputes
# the mask fresh and, if it disagrees with the cached one, logs a full repro
# (two distinct boards sharing one `string_representation` key) to
# CARCASSONNE_CLIP_TRACE_DIR/cache_collision_<pid>.jsonl. Read-only diagnostic:
# it returns the FRESH (correct) mask on a detected collision so the run is not
# itself corrupted, but the mask/raise semantics are otherwise unchanged.
_CACHE_COLLIDE_CHECK = os.environ.get("CARCASSONNE_CACHE_COLLIDE_CHECK", "0") == "1"

# --- Strict window mode (F1 release audit, DEFAULT OFF) ----------------------
# Production `get_valid_moves` silently DROPS individual legal actions that fall
# outside the centered window and only raises when ALL of them overflow (the
# review's P1-R1: a single dropped legal action is invisible). When
# CARCASSONNE_WINDOW_STRICT=1, ANY dropped legal action raises WindowOverflowError,
# so the F1 adversarial replay can fail loud on the FIRST drop. Default OFF ->
# production mask/raise semantics are byte-for-byte unchanged. Read as a module
# global (tests monkeypatch `game_wrapper._WINDOW_STRICT`).
_WINDOW_STRICT = os.environ.get("CARCASSONNE_WINDOW_STRICT", "0") == "1"

# --- Legal-cache / transposition key: injective rotation fix (DEFAULT **ON**) -
# THE DEFECT. `_tile_rotation_signature`'s per-tile key component used to be
# `(4 outer edges, shield, chapel, flowers)`. That is NOT injective for a
# 180-degree-rotationally-symmetric tile — witnesses `city_left_right`, whose
# edges read `('grass', 'city', 'grass', 'city')` at both rotation 0 and
# rotation 2, and `straight_road` (`('grass','road','grass','road')`) — even
# though the tile's FARM SLOTS rotate (`farmer_positions` / `tile_connections`
# are permuted, and which absolute Side a given corner ends up on changes).
# Two genuinely different boards therefore collided on one `_legal_cache` key
# (== one `string_representation`, which doubles as the MCTS transposition
# key), and the second board to ask was served the FIRST board's mask —
# offering a farmer corner that is not legal there and withholding the one
# that is. Downstream tools did not merely mis-key: they evaluated ILLEGAL
# afterstates.
#
# THE DEPENDENCY SET the key must be injective over (derived from
# `_compute_mask` -> `ActionUtil.get_possible_actions` ->
# `PossibleMoveFinder.possible_meeple_actions` / `TilePositionFinder`):
#   * every PLACED tile's full action-relevant geometry — outer edges AND the
#     rotating farm-slot geometry, because `FarmUtil.find_farm` /
#     `CityUtil.find_city` / `RoadUtil.find_road` traverse NEIGHBOURS, so the
#     farm slots of every reachable tile (not just the last one) select the
#     region, and `farmer_connection.farmer_positions[0]` selects the emitted
#     action's Side — plus its coordinate;
#   * `last_tile_action` (coordinate; its tile is the placed tile above);
#   * all players' `placed_meeples` (region-occupancy veto) and the current
#     player's supply — `meeples`, and also `big_meeples` / `abbots`, which
#     gate whole action families (structurally 0 in the locked 2p base+farmers
#     scope, but they are in the enumerator, so they are in the key);
#   * `phase`, `current_player`, `scores`, `len(deck)`, and the drawn
#     `next_tile` (identity, now by full signature not just `description`);
#   * `board.offset`, which `encode` uses — determined by the placed-coord
#     centroid + the per-Game window size, so it is implied, not stored;
#   * `supplementary_rules` (FARMERS on/off) and the R9 farm-data latch — both
#     are per-PROCESS/per-`Game` constants and the memo is per-`Game`, so they
#     cannot cross-contaminate one cache.
#
# THE FIX (this flag ON — OPT-IN; see the default note below): fold
# `_farm_slot_signature` into the per-tile signature, and fold `next_tile`'s
# signature + `big_meeples` / `abbots` into the state key. See
# `Game.string_representation`.
#
# ⛔ DEFAULT-OFF (reverted 2026-08-30, same night as the promote). The fix is
# INTACT and correct; what it cannot yet be is DEFAULT, because
# `Game.string_representation` is ALSO the rust mirror's reconcile contract.
# `carc_core`'s `string_representation` still emits the legacy 9-tuple, so with
# the fix on by default `RustFairAgent.check_sync` raises `MirrorDesync` at ply
# 0 of every game — the python key grew three components the rust key has not.
# There is no `FIX_LEGAL_CACHE_KEY` counterpart anywhere under `rust/carc/`.
# Caught on first contact by the FPU-ladder golden gate (`REHEARSAL_CERT.md`,
# §4); the cargo suite cannot see it, because the contract that breaks is
# python<->rust. ⛔ THE RUST HALF IS OWED BEFORE ANY RE-PROMOTE: land the same
# three components in `carc_core::game::string_representation` under the same
# flag, then flip the default and re-run the gate. Until then this is a knob
# that tooling wanting honest masks sets explicitly (`=1`).
#
# The original promote's reasoning still stands on its own terms and is kept
# here because it is what the re-promote should be argued from: a wrong mask is
# a correctness defect, not a rules variant, so the R9 / `fixed_v1` "opt in
# because it moves engine semantics" precedent does NOT apply — nothing here
# changes what a legal move IS, it only stops the memo returning another
# board's answer. Every honestly-computed (cache-off) quantity is unchanged
# bit-for-bit. The one thing that legitimately needs the OLD behaviour is
# REPLAY of a corpus that was banked under it — above all the tiearb2 Stage-2
# rust port's `LegalMaskCache` (`legal_mask_cache=True`), built to reproduce
# the BURNED, unregeneratable Stage-1b bank BIT-FOR-BIT
# (rust/carc/carc-core/src/tier1.rs; tests/test_tier1_rust.py::test_the_memo_
# collision_is_real_and_is_what_the_bank_carries — that test drives the RUST
# memo, which carries its own key and is unaffected by this flag). Making
# bug-reproduction the thing that must declare itself is the house rule for
# banked numbers: supersede-by-rerun, never retro-edit.
#
# OPT-IN LEVER: `CARCASSONNE_FIX_LEGAL_CACHE_KEY=1` enables the fix; unset (or
# an explicit falsey value) is the historical colliding key, byte-identical
# (the fixed components are APPENDED, so the legacy string is unchanged, not
# merely equivalent). ⚠️ Do NOT set it for anything that drives a RUST mirror
# under reconcile until the rust half lands — see the DEFAULT-OFF note above.
# Latched at import like
# `_WINDOW_STRICT`; recorded in every run manifest via `run_manifest`. Tests
# monkeypatch `game_wrapper._FIX_LEGAL_CACHE_KEY` (and must then clear
# `tile._rot_sig_cache`, which memoizes per Tile instance).
#
# Localised 2026-08-17 by tiearb2 Stage-2's G-BITEXACT (57/15,360 banked
# playout values moved), parked as commit `05ed019c`; re-witnessed 2026-08-30
# by OM-D2 (`measurement/omd2_chain_values_20260830/`), which showed the
# banked meeple-tie census reading a PassAction where the honest mask offered
# a farmer, on 10/10 witnesses.
FIX_LEGAL_CACHE_KEY_ENV_VAR = "CARCASSONNE_FIX_LEGAL_CACHE_KEY"


def resolve_fix_legal_cache_key(environ=None) -> bool:
    """Resolve the key mode from the environment. Default OFF; the fix must be
    ASKED for with an explicit truthy value, because it moves a key the rust
    mirror also computes (see the DEFAULT-OFF note above). (A function so the
    default and both spellings are testable without re-importing the module
    under a doctored environment.)"""
    raw = (os.environ if environ is None else environ).get(
        FIX_LEGAL_CACHE_KEY_ENV_VAR, "0")
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


_FIX_LEGAL_CACHE_KEY = resolve_fix_legal_cache_key()


def _state_fingerprint(state) -> dict:
    """A DEEP fingerprint of the engine state — captures fields that
    `string_representation` may omit, so a collision's two boards can be diffed
    to find the missing key component. Diagnostic-only."""
    def _tile_full(t):
        if t is None:
            return None
        from wingedsheep.carcassonne.objects.side import Side
        farms = []
        for fc in getattr(t, "farms", ()) or ():
            farms.append({
                "farmer_positions": [getattr(s, "value", str(s)) for s in fc.farmer_positions],
                "tile_connections": [getattr(s, "value", str(s)) for s in fc.tile_connections],
                "city_sides": [getattr(s, "value", str(s)) for s in fc.city_sides],
            })
        return {
            "desc": t.description,
            "edges": [t.get_type(s).value for s in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)],
            "shield": bool(t.shield), "chapel": bool(t.chapel), "flowers": bool(t.flowers),
            "farms": farms,
        }
    placed = []
    for coord in sorted(state.placed_coords, key=lambda c: (c.row, c.column)):
        placed.append((coord.row, coord.column, _tile_full(state.board[coord.row][coord.column])))
    meeples = []
    for p, lst in enumerate(state.placed_meeples):
        for mp in lst:
            cws = mp.coordinate_with_side
            meeples.append({
                "player": p, "type": mp.meeple_type.value,
                "row": cws.coordinate.row, "col": cws.coordinate.column,
                "side": cws.side.value, "repr": repr(mp),
            })
    lta = state.last_tile_action
    return {
        "phase": state.phase.value,
        "current_player": state.current_player,
        "scores": list(state.scores),
        "meeples_hand": list(state.meeples),
        "abbots": list(getattr(state, "abbots", []) or []),
        "deck_len": len(state.deck),
        "deck_order": [t.description for t in state.deck],
        "next_tile": _tile_full(state.next_tile),
        "last_tile_action_repr": repr(lta),
        "last_tile_coord": (
            (lta.coordinate.row, lta.coordinate.column) if lta is not None else None
        ),
        "last_tile_full": (_tile_full(getattr(lta, "tile", None)) if lta is not None else None),
        "placed": placed,
        "meeples_placed": meeples,
    }


def _log_cache_collision(game, board, key, cached_mask, fresh_mask) -> None:
    import hashlib
    import json
    import time
    d = os.environ.get("CARCASSONNE_CLIP_TRACE_DIR")
    cached_legal = sorted(int(i) for i in np.flatnonzero(cached_mask))
    fresh_legal = sorted(int(i) for i in np.flatnonzero(fresh_mask))
    this_fp = _state_fingerprint(board.state)
    other_fp = getattr(game, "_collide_shadow", {}).get(key)
    # Field-level diff of the two colliding boards' fingerprints.
    fp_diff = {}
    if other_fp is not None:
        for k in set(this_fp) | set(other_fp):
            if this_fp.get(k) != other_fp.get(k):
                fp_diff[k] = {"hit_board": this_fp.get(k), "cached_board": other_fp.get(k)}
    rec = {
        "ts": time.time(),
        "pid": os.getpid(),
        "key": key,
        "key_hash": hashlib.blake2b(key.encode(), digest_size=8).hexdigest(),
        "board_offset": [board.offset.origin_row, board.offset.origin_col, board.offset.size],
        "phase": board.state.phase.value,
        "cur_player": board.state.current_player,
        "cached_legal": cached_legal,
        "fresh_legal": fresh_legal,
        "cached_minus_fresh": sorted(set(cached_legal) - set(fresh_legal)),
        "fresh_minus_cached": sorted(set(fresh_legal) - set(cached_legal)),
        "has_other_board": other_fp is not None,
        "fingerprint_diff_fields": sorted(fp_diff.keys()),
        "fingerprint_diff": fp_diff,
    }
    if d:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"cache_collision_{os.getpid()}.jsonl"), "a") as fh:
            fh.write(json.dumps(rec) + "\n")


def window_audit_enabled() -> bool:
    """True iff CARCASSONNE_WINDOW_AUDIT=1 was set at import time."""
    return _WINDOW_AUDIT


def drain_window_audit() -> list:
    """Return the accumulated per-decision audit records and clear the buffer.

    Each record is a dict:
      phase           'tiles' | 'meeples'
      n_total         legal actions the engine emitted at this decision
      n_overflow      how many of those the centered window dropped
      k_remaining     tiles left to place (total_tiles - tile_count); stage proxy
      n_oow_tiles     placed tiles outside the window (what encode_board skips)
      window_size     live window edge length (board.offset.size)
    """
    global _WINDOW_AUDIT_LOG
    out = _WINDOW_AUDIT_LOG
    _WINDOW_AUDIT_LOG = []
    return out


def _count_out_of_window_tiles(state, off) -> int:
    """Count placed tiles outside the centered window — exactly the tiles
    `encode_board` / `get_canonical_form` silently skip. Read-only; used only by
    the audit block (mirrors board_repr.board_overflows_window but counts)."""
    n = 0
    origin_row, origin_col, size = off.origin_row, off.origin_col, off.size
    for r, row in enumerate(state.board):
        for c, tile in enumerate(row):
            if tile is None:
                continue
            wr, wc = r - origin_row, c - origin_col
            if not (0 <= wr < size and 0 <= wc < size):
                n += 1
    return n


@dataclass
class Board:
    """Container for engine state plus the cached window offset.

    Mutating helpers return new Board instances; the underlying engine state
    is deep-copied to keep MCTS rollouts independent.
    """

    state: CarcassonneGameState
    total_tiles: int
    offset: WindowOffset
    # Incremental centroid tracker for the window offset. The offset centers the
    # window on the centroid of placed tiles; instead of re-scanning the whole
    # 35x35 board every transition (compute_window_offset), we keep a running
    # (sum_row, sum_col, tile_count) of placed-tile coordinates and recompute the
    # offset in O(1). Only a TILE placement changes these (meeple/pass do not),
    # so transitions that don't place a tile leave the offset untouched. Seeded
    # by a one-time scan in from_state; updated in Game.get_next_state /
    # apply_action_inplace. Plain ints -> copy correctly under the dataclass's
    # default deepcopy (used by NeuralMCTS._reshuffled_root) and the manual
    # Board(...) build in mcts._rollout (which forwards them). MUST stay
    # consistent with state.placed_coords at every ply (offset feeds action
    # encode/decode — a wrong offset shifts the action space). Reconciled
    # bit-identical vs the full scan by scripts/reconcile_window_offset.py.
    sum_row: int = 0
    sum_col: int = 0
    tile_count: int = 0
    # Memoized string_representation result. None = not yet computed.
    # Boards are created fresh per Game.get_next_state (apply_action returns
    # a NEW Board around a deepcopied state), so this cache is auto-invalidated
    # by replacement — no manual invalidation needed. apply_action_inplace
    # mutates state but does NOT create a new Board; callers MUST not call
    # string_representation on an inplace-mutated Board (rollout-only contract).
    _str_repr_cache: str | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_state(cls, state: CarcassonneGameState, total_tiles: int, window_size: int) -> "Board":
        # Seed the incremental centroid sums by a one-time scan, then derive the
        # offset from them (same math compute_window_offset uses) so the seed and
        # the per-ply incremental updates can never drift apart.
        sr, sc, tc = centroid_sums(state)
        return cls(
            state=state,
            total_tiles=total_tiles,
            offset=offset_from_centroid_sums(state, sr, sc, tc, window_size),
            sum_row=sr,
            sum_col=sc,
            tile_count=tc,
        )


# Retail/tournament rules pre-place a fixed start tile — the "D" pattern: a city
# on one edge with a road running straight through. In the vendored deck that is
# `city_top_straight_road` at rotation 0 (TOP=city, LEFT/RIGHT=road, BOTTOM=grass),
# of which the base game has 4 copies; retail places one and shuffles the other 71.
RETAIL_START_TILE = "city_top_straight_road"

# --------------------------------------------------------------------------- #
# Start-tile GRID position (2026-08-02). The engine's own defaults, and the two #
# refusals that make moving them safe.                                          #
#                                                                              #
# `CarcassonneGameState` starts the board at (6, 15) on a 35x35 grid — 6 rows   #
# of headroom above vs 28 below — and `StateUpdater.play_tile` bounds-checks    #
# `open_positions`, so a rule-legal cell above row 0 is silently never offered  #
# (2.6% of all rule-legal placements; tests/test_start_tile_grid_bound.py).     #
#                                                                              #
# `Game(start_row=...)` is the OPT-IN escape. DEFAULT OFF: with no argument the #
# state is constructed exactly as before — the same call with the same          #
# arguments — so every training run, eval and solver measurement is byte-       #
# identical. The Android app opts in (`grid_rule: "centered18"`); the GLOBAL    #
# engine default stays walled until that is separately decided, because moving  #
# it changes the legal-move set in ~68% of games and retires every deck band.   #
#                                                                              #
# ⚠️ THE SHIFT MUST BE EVEN ON BOTH AXES. `board_repr.offset_from_centroid_sums`#
# centres the window with banker's-rounded `round(sum/count)`, which is         #
# equivariant under even translations only (round(6.5)=6 but round(17.5)=18).   #
# An odd shift silently slips the window one cell on ~half of all positions and #
# invalidates every trained checkpoint's input distribution. Refused at         #
# construction, the same refusal the Rust port's `GameConfig::resolve` makes    #
# (measurement/rustport_p5, `carc_rs.resolve_game_config`).                     #
# --------------------------------------------------------------------------- #
ENGINE_START_ROW, ENGINE_START_COL = 6, 15
ENGINE_BOARD_ROWS, ENGINE_BOARD_COLS = 35, 35

# --------------------------------------------------------------------------- #
# F9/A3 — THE UNPLACEABLE-TILE DRAW RULE (audit RF-D-2, spec §A3).             #
#                                                                             #
# `"engine"` (DEFAULT, the walled engine of record): a TILES-phase PassAction  #
# discards the unplaceable tile, draws the next AND passes the turn — the      #
# drawer forfeits a whole placement and every turn parity after it flips.      #
# Measured 8.5 discards / 100 games, 7.0% of games affected (audit RF-D-2).    #
#                                                                             #
# `"redraw"` (opt-in): the retail rule — reveal, set the tile aside (it leaves #
# the game), draw again, SAME player continues, repeat while unplaceable. The  #
# rules clause and both sub-decision resolutions (recursion; the bag / the     #
# exact solver's histogram) are documented at length on                        #
# `StateUpdater._apply_action_to`, which is where the divergence lives.        #
#                                                                             #
# LIKE `start_rule` AND `grid_rule`, THIS TRAVELS IN THE SAVE PAYLOAD:         #
# (deck_seed, actions) decodes to a DIFFERENT game under the two rules, so a   #
# record that omits the rule is not replayable. A payload with no `draw_rule`  #
# was written before this shipped and means "engine" (DRAW_RULE_LEGACY).       #
# --------------------------------------------------------------------------- #
DRAW_RULE_ENGINE = "engine"
DRAW_RULE_REDRAW = "redraw"
DRAW_RULES = (DRAW_RULE_ENGINE, DRAW_RULE_REDRAW)
DRAW_RULE_LEGACY = DRAW_RULE_ENGINE   # what a record with no `draw_rule` means


def resolve_winner(score0: int, score1: int, wc_tiebreak: bool = False) -> int:
    """Winner seat index, or -1 for a draw. Seat 0 is the STARTING player.
    Under `wc_tiebreak` (official WC rule) a tied final score is an automatic
    LOSS for the starting player, so -1 is unreachable and seat 1 wins."""
    if score0 > score1:
        return 0
    if score1 > score0:
        return 1
    # score0 == score1
    return 1 if wc_tiebreak else -1


def _next_total_tiles(total_tiles: int, state, n_set_aside_before: int) -> int:
    """`board.total_tiles` after a transition, minus any tile set aside by it.

    Under `draw_rule="redraw"` a tile can leave the game unplaced, so the
    ORIGINAL total stops describing the game. Two live definitions of "tiles
    left" would then drift apart by the set-aside count:

      * `len(state.deck) + (state.next_tile is not None)` — what
        `fair_agent.k_remaining` and the exact-endgame latch band use;
      * `board.total_tiles - board.tile_count` — what the window audit
        (`Game._audit_window`), `scripts/analyzer/clip_trace.py` and
        `features.progress` use.

    Decrementing keeps them equal, which is the bag-accounting invariant that
    `tests/test_unplaceable_redraw.py::test_the_two_tiles_left_definitions_agree_
    under_redraw` pins. Flag-OFF this returns `total_tiles` unchanged — the
    flag-off discard path leaves the same latent drift it always had, and
    byte-identity forbids fixing it here.
    """
    if not state.redraw_unplaceable:
        return total_tiles
    return total_tiles - (len(state.set_aside_tiles) - n_set_aside_before)


def check_start_position(start_row: int, start_col: int) -> None:
    """Refuse an ODD shift or an off-board start — mirrors the Rust `check_flags`.

    Raises ``ValueError``; returns None when the position is usable.
    """
    for axis, v, base, extent in (
        ("start_row", int(start_row), ENGINE_START_ROW, ENGINE_BOARD_ROWS),
        ("start_col", int(start_col), ENGINE_START_COL, ENGINE_BOARD_COLS),
    ):
        if (v - base) % 2 != 0:
            raise ValueError(
                f"{axis} shift must be EVEN: {v} is {v - base} from the engine "
                f"default {base}; banker's rounding in "
                "board_repr.offset_from_centroid_sums is equivariant under even "
                "translations only"
            )
        if not 0 <= v < extent:
            raise ValueError(
                f"{axis} {v} is outside the "
                f"{ENGINE_BOARD_ROWS}x{ENGINE_BOARD_COLS} board"
            )


def preplace_retail_start_tile(state: CarcassonneGameState) -> None:
    """Pre-place the fixed "D" start tile, retail/tournament style (in place).

    The engine's native convention is that the first player DRAWS a random tile
    which is then auto-placed at ``starting_position`` — costing that player a
    turn and handing them a free meeple opportunity on it. Retail pre-places a
    fixed D tile before anyone draws: nobody spends a turn on it and no meeple
    may go on it, so player 0's first real decision is the second tile.

    Tile TOTALS are unchanged (1 pre-placed + 71 drawn = 72 placed either way);
    what changes is which tile starts the board, that it is no longer a player's
    move, and therefore the turn parity of everything after it.

    Leaves ``last_tile_action`` as None on purpose — nobody played this tile, so
    no meeple phase follows it and no feature-completion scoring is triggered.
    """
    from wingedsheep.carcassonne.objects.coordinate import Coordinate
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    if state.placed_coords:
        raise ValueError("preplace_retail_start_tile requires a virgin state")
    start_tile = base_tiles[RETAIL_START_TILE]

    # Draw the D tile OUT of the shuffled pool (next_tile + deck) so the deck is
    # the retail 71, not 72 with a duplicate.
    pool = [state.next_tile] + list(state.deck)
    for i, tile in enumerate(pool):
        if tile is not None and tile.description == start_tile.description:
            pool.pop(i)
            break
    else:
        raise ValueError(
            f"no {RETAIL_START_TILE!r} tile in the deck — the retail start tile "
            "is a base-game tile; is TileSet.BASE enabled?"
        )

    coord = state.starting_position
    state.board[coord.row][coord.column] = start_tile
    state.placed_coords.add(coord)
    n_rows, n_cols = len(state.board), len(state.board[0])
    for nr, nc in ((coord.row - 1, coord.column), (coord.row + 1, coord.column),
                   (coord.row, coord.column - 1), (coord.row, coord.column + 1)):
        if 0 <= nr < n_rows and 0 <= nc < n_cols and state.board[nr][nc] is None:
            state.open_positions.add(Coordinate(row=nr, column=nc))

    state.deck = pool
    state.next_tile = state.deck.pop(0) if state.deck else None
    state.phase = GamePhase.TILES
    state.current_player = 0
    state.last_tile_action = None


class Game:
    """AlphaZero-style Carcassonne game interface."""

    def __init__(
        self,
        players: int = 2,
        tile_sets: tuple[TileSet, ...] = (TileSet.BASE,),
        supplementary_rules: tuple[SupplementaryRule, ...] = (SupplementaryRule.FARMERS,),
        window_size: int = DEFAULT_WINDOW_SIZE,
        enable_legal_moves_cache: bool = False,
        include_farm_scalars: bool = False,
        sighted: bool = False,
        fixed_start_tile: bool = False,
        start_row: int | None = None,
        start_col: int | None = None,
        cloister_scan_fix: bool = False,
        draw_rule: str = DRAW_RULE_ENGINE,
        wc_tiebreak: bool = False,
    ):
        if players != 2:
            raise NotImplementedError("Phase 1 wrapper is 2-player only")
        # Reject out-of-scope configurations at construction time so the
        # action-space encoder doesn't surprise the caller mid-game with a
        # ValueError on an ABBOT/BIG MeepleAction. (External review pass 4,
        # 2026-04-28.)
        if TileSet.INNS_AND_CATHEDRALS in tile_sets:
            raise NotImplementedError(
                "INNS_AND_CATHEDRALS is out of scope for Phase 1-5; "
                "the action-space encoder doesn't handle BIG/BIG_FARMER meeples."
            )
        if SupplementaryRule.ABBOTS in supplementary_rules:
            raise NotImplementedError(
                "ABBOTS supplementary rule is out of scope for Phase 1-5; "
                "the action-space encoder doesn't handle ABBOT meeples."
            )
        self.players = players
        self.tile_sets = tuple(tile_sets)
        self.supplementary_rules = tuple(supplementary_rules)
        self.window_size = int(window_size)
        # Path B Step E (2026-05-29): append the 2 farm-control scalars to the
        # network input. OFF by default so existing 10-scalar checkpoints load &
        # eval unchanged; the new-arch Path-B warmstart opts in (and builds its
        # net with n_scalar_features = get_scalar_feature_size()). MUST match the
        # net the Game feeds — a 12-scalar Game with a 10-scalar net (or vice
        # versa) is a shape error at the policy_fc/value_fc1 cat.
        self.include_farm_scalars = bool(include_farm_scalars)
        # M2 canonical-AZ "sighted" representation (opt-in; DEFAULT OFF). When on,
        # get_canonical_form appends +3 farm-connectivity planes to the board
        # tensor (78 -> 81 channels) and the +32 bag/deck histogram to the scalar
        # vector. The net must be built with matching dims (n_input_channels=81,
        # n_scalar_features = base(+farm) + 32). MEASUREMENT ONLY — with sighted
        # False the branch is never taken and the featurizer is byte-identical to
        # the production path. See measurement/canonical_az/M2_PLAN.md.
        self.sighted = bool(sighted)
        # Retail/tournament fixed start tile (2026-07-30). OPT-IN, DEFAULT OFF —
        # the Android app enables it; training/eval/solver measurement all stay on
        # the engine's native random-start convention that every existing baseline
        # was measured under. Flipping this default is a rules change that
        # re-baselines everything (BACKLOG "Fixed start tile", bundle with G1).
        # It touches game SETUP only: the board tensor, the scalar features and
        # the action space are all window-relative and completely unaffected, so a
        # checkpoint trained on random-start plays a fixed-start game with no
        # shape or semantic change (only a hair of distribution shift).
        # F9 A0 (2026-08-02): the ONE place the process-wide `rules_profile`
        # becomes geometry. The profile fills in ONLY what the caller left
        # unsaid — an explicit kwarg always wins — and under the default
        # `walled` profile it fills in NOTHING (game_kwargs() is empty), so this
        # block is a no-op on every pre-F9 call and the constructed state is the
        # same object graph it always was. That is Gate A0's identity, held
        # structurally rather than by assertion. Resolution is env-backed so a
        # spawn worker cannot disagree with the manifest.
        # See src/carcassonne_ai/rules_profile.py.
        from . import rules_profile as _rp

        _prof_kw = _rp.active().game_kwargs()
        if start_row is None and start_col is None and "start_row" in _prof_kw:
            start_row, start_col = _prof_kw["start_row"], _prof_kw["start_col"]
        if not fixed_start_tile and _prof_kw.get("fixed_start_tile"):
            fixed_start_tile = True
        if window_size == DEFAULT_WINDOW_SIZE and "window_size" in _prof_kw:
            self.window_size = int(_prof_kw["window_size"])
        # A2/A3 joined the profile at the F9 compose merge (2026-08-03). Same
        # "fill in only what the caller left unsaid" rule as the three above:
        # the caller's explicit value always wins, and under `walled` neither key
        # is present so this stays the no-op that Gate A0's identity rests on.
        # ⚠️ These two lines are load-bearing — without them a `fixed_v1` leg
        # resolves the profile, stamps all four levers in its manifest, and then
        # plays the DRIFTING scan and the engine draw rule, which is precisely
        # the half-applied profile F9 exists to detect
        # (tests/test_rules_profile.py::test_fixed_v1_carries_all_four_levers...).
        if not cloister_scan_fix and _prof_kw.get("cloister_scan_fix"):
            cloister_scan_fix = True
        if draw_rule == DRAW_RULE_ENGINE and "draw_rule" in _prof_kw:
            draw_rule = _prof_kw["draw_rule"]
        # WC tie-break (BACKLOG 2026-08-03). Same "fill in only what the caller
        # left unsaid" rule as the four levers above: no shipped profile sets
        # `wc_tiebreak` today (adoption into a future `fixed_v2` bundle is an
        # explicitly separate decision — see rules_profile.py), so this stays
        # the no-op every profile's Gate A0 identity rests on.
        if not wc_tiebreak and _prof_kw.get("wc_tiebreak"):
            wc_tiebreak = True
        self.fixed_start_tile = bool(fixed_start_tile)
        # Where the start tile sits on the 35x35 grid. `None` means "say nothing
        # to the engine", which is what makes the default path byte-identical:
        # get_init_board then constructs CarcassonneGameState with exactly the
        # arguments it always did. See check_start_position above for the
        # EVEN-shift refusal, and `self.recentred` for the one-bit summary.
        self.start_row = ENGINE_START_ROW if start_row is None else int(start_row)
        self.start_col = ENGINE_START_COL if start_col is None else int(start_col)
        check_start_position(self.start_row, self.start_col)
        self.recentred = (self.start_row, self.start_col) != (
            ENGINE_START_ROW, ENGINE_START_COL)
        # F9-A2 (2026-08-03): fix the RF-D-1 cloister-completion scan drift.
        # OPT-IN, DEFAULT OFF. On, a cloister scores the moment its 3x3 is full
        # and its monk returns to supply; off, ~9.6% of completions are deferred
        # to count_final_scores and the monk is pinned for the rest of the game.
        # Final TOTALS are the same either way (the endgame pass awards the same
        # 9) — what changes is the PLY and the meeple supply, which is why this
        # is a re-baselining rules change and not a bug fix to apply silently.
        # Like `start_row`, it is passed to the engine ONLY when asked for, so the
        # default path is the same constructor call it has always been.
        self.cloister_scan_fix = bool(cloister_scan_fix)
        # F9/A3 — the unplaceable-tile draw rule (audit RF-D-2). Named rules,
        # never a loose bool at the CLI, and never a silent default: picking one
        # for the caller would decode a DIFFERENT game from the same
        # (deck_seed, actions), exactly as `start_rule`/`grid_rule` would.
        if draw_rule not in DRAW_RULES:
            raise ValueError(
                f"unknown draw_rule {draw_rule!r}; expected one of {DRAW_RULES}")
        self.draw_rule = str(draw_rule)
        self.redraw_unplaceable = self.draw_rule == DRAW_RULE_REDRAW
        # WC tie-break (BACKLOG 2026-08-03 "WC tie-break rule flag"). OPT-IN,
        # DEFAULT OFF. Terminal-scoring-only: it changes nothing about legal
        # moves, transitions or encoding, only which seat `get_game_ended`
        # reports as the winner of an exact-tie terminal. See WC_TIE_VALUE
        # above for why the magnitude stays at epsilon.
        self.wc_tiebreak = bool(wc_tiebreak)
        # Legal-moves cache. Off by default; MCTS turns it on per search and
        # calls clear_caches() between root moves. See DECISIONS.md
        # ("Phase 4 prerequisite: get_valid_moves performance strategy").
        self._legal_cache: dict[str, np.ndarray] | None = (
            {} if enable_legal_moves_cache else None
        )
        self._legal_cache_hits = 0
        self._legal_cache_misses = 0

    def clear_caches(self) -> None:
        """Reset all per-search caches. Call between MCTS root moves."""
        if self._legal_cache is not None:
            self._legal_cache.clear()
        self._legal_cache_hits = 0
        self._legal_cache_misses = 0
        if hasattr(self, "_collide_shadow"):
            self._collide_shadow.clear()

    def cache_stats(self) -> dict:
        """Returns hits/misses/size for the legal-moves cache."""
        size = len(self._legal_cache) if self._legal_cache is not None else 0
        total = self._legal_cache_hits + self._legal_cache_misses
        hit_rate = self._legal_cache_hits / total if total else 0.0
        return {
            "enabled": self._legal_cache is not None,
            "hits": self._legal_cache_hits,
            "misses": self._legal_cache_misses,
            "hit_rate": hit_rate,
            "size": size,
        }

    # --- Construction ----------------------------------------------------

    def get_init_board(self) -> Board:
        # `starting_position` is passed ONLY when it was asked for. The default
        # path is therefore the same call it has always been — not an equal-
        # valued Coordinate, no call at all — so "default unchanged" is a
        # property of the code, not of Coordinate's __eq__.
        extra = {}
        if self.recentred:
            from wingedsheep.carcassonne.objects.coordinate import Coordinate

            extra["starting_position"] = Coordinate(self.start_row, self.start_col)
        if self.cloister_scan_fix:
            extra["cloister_scan_fix"] = True
        state = CarcassonneGameState(
            players=self.players,
            tile_sets=list(self.tile_sets),
            supplementary_rules=list(self.supplementary_rules),
            **extra,
        )
        # Scope guard (locked scope = 2p Base+Farmers, NO Abbots): a base+farmers
        # state has abbots == [0, 0] and no ABBOT meeple can ever be placed. If this
        # fires, an out-of-scope ABBOTS state slipped past the __init__ guard and
        # would silently mis-score — fail loud instead of scoring the wrong game.
        assert not any(state.abbots), (
            f"scope violation: abbots enabled ({state.abbots}); locked scope is "
            "2p Base+Farmers, no Abbots")
        # F9/A3: latch the draw rule onto the state so it rides deepcopy into
        # every MCTS node, PIMC world and solver clone. Assigned unconditionally
        # (it is already False from the ctor) so the flag can never be *absent*
        # on a state the engine is about to transition.
        state.redraw_unplaceable = self.redraw_unplaceable
        if self.fixed_start_tile:
            preplace_retail_start_tile(state)
        # +1 for the first tile already drawn into next_tile, + any tile already on
        # the board (the retail start tile, which is placed but was never drawn).
        total_tiles = len(state.deck) + 1 + len(state.placed_coords)
        return Board.from_state(state, total_tiles, self.window_size)

    def get_input_channels(self) -> int:
        """Board-tensor channel count the net must accept (78, or 81 sighted)."""
        n = N_CHANNELS
        if self.sighted:
            from .sighted_planes import N_FARM_PLANES
            n += N_FARM_PLANES
        return n

    def get_board_shape(self) -> tuple[int, int, int]:
        return (self.get_input_channels(), self.window_size, self.window_size)

    def get_action_size(self) -> int:
        return action_size(self.window_size)

    def get_scalar_feature_size(self) -> int:
        n = N_SCALAR_FEATURES + (N_FARM_SCALARS if self.include_farm_scalars else 0)
        if self.sighted:
            from .sighted_planes import N_BAG
            n += N_BAG
        return n

    # --- Transitions -----------------------------------------------------

    @staticmethod
    def _next_centroid_sums(board: Board, action) -> tuple[int, int, int]:
        """Centroid sums after `action`, carried forward from `board`.

        The window offset centers on the centroid of placed tiles. Only a TILE
        placement adds a coordinate (engine: StateUpdater.play_tile is the sole
        writer of placed_coords); meeple actions and passes place no tile, so the
        centroid — and therefore the offset — is unchanged. This is the O(1)
        replacement for re-scanning the whole board every transition.
        """
        if isinstance(action, TileAction):
            coord = action.coordinate
            return (
                board.sum_row + coord.row,
                board.sum_col + coord.column,
                board.tile_count + 1,
            )
        return board.sum_row, board.sum_col, board.tile_count

    def get_next_state(self, board: Board, action_idx: int) -> tuple[Board, int]:
        """Apply `action_idx` to `board`. Return (new_board, next_player).

        Safe — input board is unmodified. Use for tree expansion in MCTS.
        For rollouts where the trajectory is discarded, prefer
        apply_action_inplace (3-5x faster mid-game).
        """
        state = board.state
        action = self._decode_for(state, board.offset, action_idx)
        n_set_aside_before = len(state.set_aside_tiles)
        new_state = StateUpdater.apply_action(game_state=state, action=action)
        # Carry the centroid sums forward (O(1)) instead of re-scanning the whole
        # board in Board.from_state. Bit-identical to the full scan; verified by
        # scripts/reconcile_window_offset.py.
        sr, sc, tc = self._next_centroid_sums(board, action)
        new_board = Board(
            state=new_state,
            total_tiles=_next_total_tiles(board.total_tiles, new_state,
                                          n_set_aside_before),
            offset=offset_from_centroid_sums(new_state, sr, sc, tc, self.window_size),
            sum_row=sr,
            sum_col=sc,
            tile_count=tc,
        )
        return new_board, new_state.current_player

    def apply_action_inplace(self, board: Board, action_idx: int) -> tuple[Board, int]:
        """Apply `action_idx` to `board` IN PLACE. Returns (board, next_player).

        WARNING: mutates `board.state` directly. Caller must not retain the
        prior state. Use only in MCTS rollouts and other discard-the-trajectory
        contexts. Saves the deepcopy that dominates mid-game state-copy cost.
        """
        state = board.state
        action = self._decode_for(state, board.offset, action_idx)
        n_set_aside_before = len(state.set_aside_tiles)
        StateUpdater.apply_action_inplace(game_state=state, action=action)
        board.total_tiles = _next_total_tiles(board.total_tiles, state,
                                              n_set_aside_before)
        # Offset depends on placed tiles. Update the running centroid sums in
        # O(1) (only a tile placement moves the centroid) and re-derive the
        # offset — replaces the full board re-scan (compute_window_offset).
        # Bit-identical; verified by scripts/reconcile_window_offset.py.
        sr, sc, tc = self._next_centroid_sums(board, action)
        board.sum_row, board.sum_col, board.tile_count = sr, sc, tc
        board.offset = offset_from_centroid_sums(state, sr, sc, tc, self.window_size)
        # Invalidate the memoized string_representation since state changed.
        # Required for rollouts and warmstart 2-ply lookahead that mutate a
        # Board in place and then re-query get_valid_moves / string_representation.
        board._str_repr_cache = None
        return board, state.current_player

    def _decode_for(self, state, offset, action_idx: int):
        return decode(
            action_idx,
            off=offset,
            phase=state.phase.value,
            next_tile=state.next_tile,
            last_tile_coord=(
                state.last_tile_action.coordinate if state.last_tile_action is not None else None
            ),
        )

    def get_valid_moves(self, board: Board) -> np.ndarray:
        """Return a length-action_size bool mask of legal action indices.

        Built from the engine's own enumerator: encode each emitted Action
        and flip the corresponding bit. Off-phase indices are guaranteed
        zero because our `encode()` only ever produces same-phase indices.

        If the engine has legal placements but ALL of them fall outside the
        centered window (window-overflow), this method raises
        WindowOverflowError so the caller can drop the game from training
        rather than silently see "no legal moves" (the engine's natural
        no-legal-moves signal is a single PassAction, which the mask still
        accepts). (External review pass 4, 2026-04-28.)

        If the legal-moves cache is enabled (constructor flag), checks for
        and writes to it. Returns the cached mask directly without copying
        — callers must NOT mutate the result.
        """
        if self._legal_cache is not None:
            key = self.string_representation(board)
            cached = self._legal_cache.get(key)
            if cached is not None:
                self._legal_cache_hits += 1
                if _CACHE_COLLIDE_CHECK:
                    # DIAGNOSTIC (Phase 0.3): recompute the mask fresh and, if it
                    # disagrees with the cached one, we have TWO distinct boards
                    # sharing one string_representation key — a cache-corrupting
                    # collision. Log a full repro, then return the FRESH mask so
                    # the diagnostic run itself is not corrupted.
                    fresh = self._compute_mask(board)
                    if not np.array_equal(fresh, cached):
                        _log_cache_collision(self, board, key, cached, fresh)
                        return fresh
                return cached
            self._legal_cache_misses += 1

        mask = self._compute_mask(board)
        if self._legal_cache is not None:
            mask.flags.writeable = False  # protect cached masks from mutation
            self._legal_cache[key] = mask
            if _CACHE_COLLIDE_CHECK:
                if not hasattr(self, "_collide_shadow"):
                    self._collide_shadow = {}
                self._collide_shadow[key] = _state_fingerprint(board.state)
        return mask

    def _compute_mask(self, board: Board) -> np.ndarray:
        """Enumerate the engine's legal actions into a bool mask (no cache)."""
        mask = np.zeros(self.get_action_size(), dtype=bool)
        n_total = 0
        n_overflow = 0
        for action in ActionUtil.get_possible_actions(board.state):
            n_total += 1
            try:
                idx = encode(action, board.offset, board.state.phase.value)
            except WindowOverflowError:
                n_overflow += 1
                continue
            mask[idx] = True

        # Window-overflow audit (measurement-only; skipped byte-for-byte when
        # CARCASSONNE_WINDOW_AUDIT is unset). Records the already-computed
        # n_total / n_overflow plus the out-of-window placed-tile count so an
        # offline replay can quantify how often either bug site fires. Placed
        # before the all-overflow raise so the pathological case is recorded too.
        if _WINDOW_AUDIT:
            _WINDOW_AUDIT_LOG.append({
                "phase": board.state.phase.value,
                "n_total": n_total,
                "n_overflow": n_overflow,
                "k_remaining": board.total_tiles - board.tile_count,
                "n_oow_tiles": _count_out_of_window_tiles(board.state, board.offset),
                "window_size": board.offset.size,
            })

        # Strict mode (F1 release audit, default OFF): fail loud on the FIRST
        # dropped legal action, not only when ALL overflow. Production is byte-for-
        # byte unchanged (the flag defaults off); the release audit sets it so an
        # adversarial replay can assert zero dropped legal actions.
        if _WINDOW_STRICT and n_overflow > 0:
            raise WindowOverflowError(
                f"STRICT window: {n_overflow}/{n_total} legal actions fall outside the "
                f"{board.offset.size}x{board.offset.size} window centered at "
                f"({board.offset.origin_row}, {board.offset.origin_col}). "
                f"CARCASSONNE_WINDOW_STRICT=1 fails loud on any dropped legal action."
            )

        # If every legal action is outside the window, surface a clear signal
        # so the caller can drop the game (rather than seeing an empty mask
        # and confusing it with a genuine no-legal-moves terminal).
        if n_total > 0 and n_overflow == n_total:
            raise WindowOverflowError(
                f"All {n_total} legal actions fall outside the {board.offset.size}x"
                f"{board.offset.size} window centered at "
                f"({board.offset.origin_row}, {board.offset.origin_col}). "
                f"Caller should drop this game from training."
            )

        return mask

    # --- Termination / value ---------------------------------------------

    def get_game_ended(self, board: Board, player: int) -> float:
        """0.0 if game ongoing; otherwise normalized score differential.

        Result is from `player`'s perspective: positive = player won (more pts).
        Final value is tanh((score_player - score_opp) / SCORE_NORM_SCALE).
        Exact tie returns a tiny epsilon so callers can distinguish "ended in
        draw" from "still going" — anything in (-1e-4, 1e-4) means draw.

        Under `self.wc_tiebreak` (BACKLOG 2026-08-03, official WC rule) an
        exact tie is NOT a draw: the STARTING player (seat 0) automatically
        loses, so the epsilon's sign is flipped relative to the incumbent
        convention below. The antisymmetry contract
        `get_game_ended(b, 0) == -get_game_ended(b, 1)` still holds in both
        modes, and `abs(v) < 1e-4` still identifies "tied on points" either
        way — only WHICH seat the tiny value favors changes.
        """
        if not board.state.is_terminated():
            return 0.0
        opp = 1 - player
        diff = board.state.scores[player] - board.state.scores[opp]
        v = math.tanh(diff / SCORE_NORM_SCALE)
        # Exact tie: return a tiny epsilon (non-zero so callers can tell
        # "ended in a draw" from "still going"), but make it player-dependent
        # so the perspective contract get_game_ended(b,0) == -get_game_ended(b,1)
        # still holds for draws — MCTS value backup relies on antisymmetry.
        if v == 0.0:
            if self.wc_tiebreak:
                # WC tie-break ARMED: seat 0 (starting player) automatically
                # loses a tied score, so the sign is flipped from the line
                # below rather than sharing it — flag-off must stay reachable
                # and byte-identical.
                return -WC_TIE_VALUE if player == 0 else WC_TIE_VALUE
            return WC_TIE_VALUE if player == 0 else -WC_TIE_VALUE
        return v

    # --- Canonical form / encoding --------------------------------------

    def get_canonical_form(self, board: Board, player: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (board_tensor, scalar_features) from `player`'s perspective.

        Window coordinates are NOT mirrored — only the mine/opp channels
        and player-relative scalar features are perspective-flipped.

        encode_board already reads `player` and writes mine/opp accordingly,
        so no extra canonical_swap is needed here. (A prior version
        double-swapped when player != current_player, silently reversing the
        intended perspective for the one caller that requested non-current
        player. Caught by external review 2026-04-28.)
        """
        arr = encode_board(board.state, player, board.offset)
        scalars = encode_scalars(
            board.state, player, board.total_tiles, include_farm=self.include_farm_scalars
        )
        if self.sighted:
            # M2 sighted cell: append +3 farm-connectivity planes to the board
            # (78 -> 81 ch) and the +32 bag/deck histogram to the scalars. Both
            # are STRUCTURAL functions of state (no label leak). encode_board may
            # return via the Cython fast path (USE_CY_REPR) — we concatenate the
            # Python-computed planes onto whatever the first 78 channels are, so
            # the sighted path is fast-path-agnostic and the first 78 channels
            # stay byte-identical to the blind path.
            from .sighted_planes import bag_histogram, farm_connectivity_planes
            fp = farm_connectivity_planes(
                board.state, player, board.offset, board.offset.size
            )
            arr = np.concatenate([arr, fp], axis=0)
            scalars = np.concatenate([scalars, bag_histogram(board.state)])
        return arr, scalars

    encode_observation = get_canonical_form

    # --- Hashing ---------------------------------------------------------

    def string_representation(self, board: Board) -> str:
        """Stable string for MCTS transposition tables.

        Two distinct game positions yield distinct strings; identical
        positions yield identical strings. Returned as a string (not int)
        so it serializes consistently across processes.

        Implementation note: SPARSE — only emits entries for placed tiles
        (~80 mid/late-game) instead of walking the full 35x35 board (1225
        cells, mostly None) and `repr()`ing the dense nested tuple. The
        dense version was ~166ms in late game, dominating get_valid_moves
        and making the legal-moves cache net-negative. Sparse should be
        ~5-10x faster.

        Memoized on the Board (see Board._str_repr_cache). NeuralMCTS keys
        nodes by this string and calls it many times against the same
        root Board within one search; the cache turns ~22K calls/game
        into ~150 cache misses (one per unique state visited).
        """
        cached = board._str_repr_cache
        if cached is not None:
            return cached
        s = board.state
        # Iterate placed_coords (~80 cells) instead of walking the full 35x35
        # grid (1225 cells, mostly None). Sort for determinism — placed_coords
        # is a set. Patched 2026-05-13.
        placed = []
        for coord in sorted(s.placed_coords, key=lambda c: (c.row, c.column)):
            t = s.board[coord.row][coord.column]
            if t is None:
                continue  # defensive; shouldn't happen since the set tracks placements
            placed.append((coord.row, coord.column, t.description, _tile_rotation_signature(t)))
        meeples = tuple(
            tuple(
                (mp.meeple_type.value, mp.coordinate_with_side.coordinate.row,
                 mp.coordinate_with_side.coordinate.column, mp.coordinate_with_side.side.value)
                for mp in s.placed_meeples[p]
            )
            for p in range(self.players)
        )
        last_tile_coord = (
            (s.last_tile_action.coordinate.row, s.last_tile_action.coordinate.column)
            if s.last_tile_action is not None
            else None
        )
        key = (
            tuple(placed),
            meeples,
            tuple(s.scores),
            tuple(s.meeples),
            s.current_player,
            s.phase.value,
            len(s.deck),
            s.next_tile.description if s.next_tile is not None else None,
            last_tile_coord,
        )
        if _FIX_LEGAL_CACHE_KEY:
            # The remaining non-injective components, APPENDED so the legacy
            # (flag-off) string stays byte-identical to its whole history. See
            # the CARCASSONNE_FIX_LEGAL_CACHE_KEY block at the top of this file
            # for the derivation of the dependency set:
            #   * next_tile by full rotation signature, not just `description`
            #     (the vendored engine has had a description collision before);
            #   * big_meeples / abbots supplies, which gate whole action
            #     families in PossibleMoveFinder.possible_meeple_actions.
            # (The rotating farm-slot geometry of every PLACED tile rides
            # inside `_tile_rotation_signature` above — that is the component
            # the 180-symmetric-tile collision actually turned on.)
            key = key + (
                _tile_rotation_signature(s.next_tile) if s.next_tile is not None else None,
                tuple(getattr(s, "big_meeples", ()) or ()),
                tuple(getattr(s, "abbots", ()) or ()),
            )
        result = repr(key)
        board._str_repr_cache = result
        return result


def _farm_slot_signature(tile) -> tuple:
    """Rotating farm-slot geometry: the part `(4 edges, shield, chapel,
    flowers)` CANNOT see. `Tile.turn()` permutes each `FarmerConnection`'s
    `farmer_positions` / `tile_connections` / `city_sides`
    (SideModificationUtil.turn_farmer_connection), so this differs between
    rotation 0 and rotation 2 of a tile whose 4 outer edges happen to read the
    same both ways (e.g. `city_left_right`, `straight_road`). Folded into the
    key by default since 2026-08-30; skipped only under the
    `CARCASSONNE_FIX_LEGAL_CACHE_KEY=0` legacy rollback — see that flag's
    comment.

    Order matters and is deliberate: `PossibleMoveFinder.__possible_farmer_
    position` emits `farmer_connection.farmer_positions[0]` as the placement
    Side, so two rotations whose farm REGIONS coincide but whose slot ordering
    differs still emit different actions and must not share a key."""
    out = []
    for fc in getattr(tile, "farms", ()) or ():
        out.append((
            tuple(getattr(s, "value", str(s)) for s in fc.farmer_positions),
            tuple(getattr(s, "value", str(s)) for s in fc.tile_connections),
            tuple(getattr(s, "value", str(s)) for s in fc.city_sides),
        ))
    return tuple(out)


def clear_rotation_signature_caches() -> None:
    """Drop every memoized `_tile_rotation_signature`.

    TEST SUPPORT ONLY. `_tile_rotation_signature` memoizes on the Tile
    instance, and `Tile.turn()` itself memoizes its rotated instances on the
    base tile (`_turn_cache`), so a signature computed under one setting of
    `_FIX_LEGAL_CACHE_KEY` survives a mid-session flip of the flag and is read
    back stale. Production never flips the flag mid-process (it is
    import-latched), so nothing production calls this; any test that
    monkeypatches `game_wrapper._FIX_LEGAL_CACHE_KEY` MUST call it on both
    sides of the flip."""
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    for tile in base_tiles.values():
        tile._rot_sig_cache = None
        for rotated in (getattr(tile, "_turn_cache", None) or {}).values():
            rotated._rot_sig_cache = None


def _tile_rotation_signature(tile) -> tuple:
    """Capture tile orientation + scoring-relevant properties.

    `description` alone is rotation-blind — two `tile.turn(...)` results
    with the same description but different orientations would otherwise
    collide. The 4 outer edges uniquely encode rotation EXCEPT on a
    180-degree-rotationally-symmetric tile (e.g. `city_left_right`: edges
    read `('grass', 'city', 'grass', 'city')` at both rotation 0 and rotation
    2), where the edges alone collide even though the farm slots have
    rotated. See the `CARCASSONNE_FIX_LEGAL_CACHE_KEY` flag comment above —
    DEFAULT ON since 2026-08-30, so `_farm_slot_signature` is folded in and
    the key is injective on rotation. `CARCASSONNE_FIX_LEGAL_CACHE_KEY=0`
    restores the historical colliding signature for replay of corpora banked
    under it (the tiearb2 Stage-2 rust port's `legal_mask_cache=True` carries
    its OWN key in rust and does not read this flag).

    Defense-in-depth: also pin shield/chapel/flowers. The vendored engine
    has had at least one description-collision bug (city_diagonal_top_left_road
    vs city_diagonal_top_left_shield_road shared the same description string;
    fixed in our fork). Shields change scoring (+1 per city tile), so a state
    key that doesn't distinguish them would cause MCTS transpositions to
    merge positions with different value functions.

    Cached on the Tile instance: Tiles are canonically-shared immutable refs
    (base_tiles dict + Tile.turn() builds a fresh Tile per rotation), so the
    signature for any given Tile reference is stable for the lifetime of the
    process -- PROVIDED `CARCASSONNE_FIX_LEGAL_CACHE_KEY` does not change
    mid-process (it is an import-time-latched env var, like `_WINDOW_STRICT`
    et al., so it never does in production; tests that monkeypatch the flag
    mid-session must clear `tile._rot_sig_cache` themselves).
    """
    cached = tile._rot_sig_cache
    if cached is not None:
        return cached
    from wingedsheep.carcassonne.objects.side import Side
    edges = (
        tile.get_type(Side.TOP).value,
        tile.get_type(Side.RIGHT).value,
        tile.get_type(Side.BOTTOM).value,
        tile.get_type(Side.LEFT).value,
    )
    sig = (edges, bool(tile.shield), bool(tile.chapel), bool(tile.flowers))
    if _FIX_LEGAL_CACHE_KEY:
        sig = sig + (_farm_slot_signature(tile),)
    tile._rot_sig_cache = sig
    return sig


# --- CLI entry point ---------------------------------------------------------

@dataclass
class _GameOutcome:
    completed: bool
    rule_violation: bool
    mask_violation: bool
    had_overflow: bool
    score_sum: int
    error: str | None = None


def _play_one_random_game(args: tuple[int, int]) -> _GameOutcome:
    """Run a single random self-play game. Module-level so it pickles for Pool."""
    seed, window_size = args
    game = Game(window_size=window_size)
    random.seed(seed)
    board = game.get_init_board()
    had_overflow = False
    try:
        while game.get_game_ended(board, 0) == 0.0:
            if board_overflows_window(board.state, board.offset):
                had_overflow = True
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                return _GameOutcome(False, True, False, had_overflow, 0,
                                    error=f"seed {seed}: empty legal-move mask")
            idx = int(random.choice(legal))
            if not mask[idx]:
                return _GameOutcome(False, False, True, had_overflow, 0,
                                    error=f"seed {seed}: chose idx {idx} not in mask")
            board, _ = game.get_next_state(board, idx)
    except Exception as exc:
        return _GameOutcome(False, True, False, had_overflow, 0,
                            error=f"seed {seed}: {type(exc).__name__}: {exc}")
    return _GameOutcome(
        completed=True,
        rule_violation=False,
        mask_violation=False,
        had_overflow=had_overflow,
        score_sum=int(sum(board.state.scores)),
    )


def _self_play_random(
    n_games: int,
    seed: int = 0,
    window_size: int = DEFAULT_WINDOW_SIZE,
    workers: int | None = None,
) -> dict:
    """Run n_games of random-vs-random through the wrapper. Verify integrity.

    Parallelized via multiprocessing.Pool. Worker count defaults to
    `os.cpu_count()` (full SMT fan-out — see DECISIONS.md and
    scripts/bench_workers.py for why this beats physical-core cap on this
    workload).
    """
    if workers is None:
        workers = min(os.cpu_count() or 1, n_games)
    args_list = [(seed + i, window_size) for i in range(n_games)]

    # Skip the ETA banner for tiny runs (test fuzz reuses this helper)
    if n_games >= 16:
        per_item = measure_one(_play_one_random_game, args_list[0])
        print_banner(
            label=f"random self-play (window={window_size})",
            n_items=n_games,
            workers=workers,
            measured_per_item_seconds=per_item,
        )

    if workers <= 1 or n_games <= 1:
        outcomes = [_play_one_random_game(a) for a in args_list]
    else:
        with Pool(processes=workers) as pool:
            outcomes = pool.map(_play_one_random_game, args_list)

    rule_violations = sum(1 for o in outcomes if o.rule_violation)
    mask_violations = sum(1 for o in outcomes if o.mask_violation)
    completed = sum(1 for o in outcomes if o.completed)
    overflow_games = sum(1 for o in outcomes if o.had_overflow)
    score_sums = [o.score_sum for o in outcomes if o.completed]

    for o in outcomes:
        if o.error:
            print(f"  {o.error}", file=sys.stderr)

    return {
        "n_games": n_games,
        "completed": completed,
        "rule_violations": rule_violations,
        "mask_violations": mask_violations,
        "overflow_games": overflow_games,
        "overflow_rate": overflow_games / max(n_games, 1),
        "mean_score_sum": (sum(score_sums) / len(score_sums)) if score_sums else 0.0,
        "workers": workers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="carcassonne_ai.game_wrapper")
    parser.add_argument("--self-play-random", action="store_true",
                        help="Run random-vs-random games through the wrapper")
    parser.add_argument("--n", type=int, default=100, help="Number of games")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE)
    parser.add_argument("--workers", type=int, default=None,
                        help="Pool size (default: os.cpu_count())")
    args = parser.parse_args(argv)
    if not args.self_play_random:
        parser.error("nothing to do; pass --self-play-random")

    print(f"Running {args.n} random-vs-random games (window={args.window_size}, workers={args.workers or 'auto'})...")
    summary = _self_play_random(
        args.n, seed=args.seed, window_size=args.window_size, workers=args.workers
    )
    for k, v in summary.items():
        print(f"  {k}: {v}")
    if summary["rule_violations"] > 0 or summary["mask_violations"] > 0:
        print("FAIL: rule or mask violations detected", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
