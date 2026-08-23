"""Click-through GUI for human-vs-AI Carcassonne (locked scope: 2p, Base + Farmers).

The DEFAULT opponent is the CURRENT DEPLOY CHAMPION — the fair (non-clairvoyant)
``FairHeuristicPriorAgent`` built by
``carcassonne_ai.champion_factory.make_production_champion("fair", ...)``, which reads
``governance/PRODUCTION.yaml`` and PROVES the curve125 v2.9 Bmild_cap8 leaf on real
boards at construction (it RAISES on any mismatch). No strength knob is hardcoded in
this file — the YAML owns them (today: k_dets=4 x sims_per_det=688 = 2752 sims/move,
exact-K<=2 marginalized endgame, c_puct=1.5, tau_p=5, visit-argmax final select).
The resolved runtime manifest is printed at startup, same as play_harness.py logs it.

⚠️ THE CHAMPION IS SLOW (~3 s/move, longer when the box is loaded), and tkinter is
single-threaded. So the agent runs on a DAEMON WORKER THREAD and hands its answer back
through a ``queue.Queue`` that the Tk main loop drains on a ``root.after(100, ...)``
tick; the same tick repaints a live "thinking… (Xs)" counter so a multi-second wait
reads as progress rather than a hang. NO tkinter call is ever made from the worker
thread. This restores the threading design of ``play_vs_mcts_gui.py`` (play-vs-mcts
branch, commit 04e4330), which this file was adapted from and which had dropped the
threading only because the Tier-1 stand-in answered instantly.

✅ F-3 LANDED 2026-08-02 — ``--backend rust|auto`` (default still ``python``, so a bare
invocation is byte-identical to before). The champion is then ``rust_agent.RustFairAgent``
over ``carc_rs``, and this GUI drives its MIRROR: ``GameGUI._seat_mirror()`` on the
initial board, ``_advance_mirror()`` inside ``_apply_action`` — the single choke point
every applied action of BOTH seats passes through, on the Tk main thread, never while
the AI worker is alive. The engine never changes the play (G4 bit-exact / G6 100% action
agreement); it changes ~12.7 s/move to ~1.3 s/move at the champion budget, which on an
interactive window is the difference between a hang and a pause. Ignored for
``--opponent tier1`` (the rule-based player has no Rust port and needs none).

``--opponent tier1`` keeps the old instant rule-based player (the SATURATED Tier-1
reference — far weaker than the champion). It uses the same worker-thread path and
simply returns almost immediately.

``--sims`` / ``--k-dets`` default to the PRODUCTION.yaml budget. Lowering them for a
faster casual game plays a WEAKER-THAN-CHAMPION agent, so the window title AND the
sidebar both say "BELOW CHAMPION BUDGET" — mirroring the ``runtime_budget_override``
that ``scripts/human_anchor/play_harness.py`` records into its game logs. A bare
invocation is always the full champion budget.

  # play the champion (you move first)
  .venv/bin/python scripts/play_vs_tier1_gui.py --player 0 --seed 42

Requires a DISPLAY: WSLg on Windows 11 (WSL2), an X server with X11 forwarding,
or run on a desktop with tkinter installed.

Interaction:
  TILES phase   - legal cells outlined orange; click a cell to select it,
                  click again to cycle rotation, click [Confirm] to commit.
                  [Cancel] clears the selection.
  MEEPLES phase - colored dots appear on each legal slot of the just-placed
                  tile. Click a dot to commit, or [Skip] to decline.
  AI turn       - board clicks are ignored, the sidebar shows a live thinking
                  timer, then the chosen move + its score impact.

⚠️ This module imports ``scripts/human_anchor/env_preamble`` BEFORE ``carcassonne_ai``
— the production leaf env (curve125 / FLAT_LEAF / CY_REPR / single-thread BLAS) must be
in ``os.environ`` at library-import time or champion_factory's verify raises. That
preamble also shapes the leaf knobs the ``tier1`` opponent reads, so ``--opponent
tier1`` here is Tier-1-under-production-leaf-env, not a pristine Tier-1 baseline; this
GUI is for play, never for measurement.
"""
from __future__ import annotations

import argparse
import queue
import random
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
# Allow running directly without `pip install -e .`.
sys.path.insert(0, str(_REPO / "src"))
# The production leaf knobs must be in os.environ BEFORE carcassonne_ai is imported.
# scripts/human_anchor/env_preamble.py owns those values (curve125, caps, FLAT_LEAF,
# CY_REPR, CUDA off, 1 BLAS thread) — import it instead of duplicating the knob list.
sys.path.insert(0, str(_REPO / "scripts" / "human_anchor"))
import env_preamble  # noqa: E402,F401  MUST precede any carcassonne_ai import

from carcassonne_ai.action_space import (
    decode,
    meeple_pass_index,
    tile_action_count,
    tile_pass_index,
)
from carcassonne_ai.game_wrapper import Board, Game, resolve_winner
# RuleBasedPlayer / champion_factory are imported lazily in `build_opponent` so a
# champion game never pays for the Tier-1 module and vice versa.

from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet


# Layout. The board canvas uses TILE_PX/CANVAS_W/CANVAS_H, all rescaled by
# zoom + --scale. The sidebar canvas is fixed-size and uses SIDEBAR_PAD only.
TILE_PX = 60                # matches CarcassonneVisualiser.tile_size
SIDEBAR_PAD = 20
CANVAS_W = 2300
CANVAS_H = 1300

TERRAIN_COLOR = {
    TerrainType.CITY: "#c43c3c",
    TerrainType.ROAD: "#8b6f47",
    TerrainType.GRASS: "#4caf50",
    TerrainType.CHAPEL: "#f5c518",
    TerrainType.FLOWERS: "#f5c518",
}
DEFAULT_DOT_COLOR = "#888"


# ---------------------------------------------------------------------------
# Pure helpers (no Tk)
# ---------------------------------------------------------------------------


def pixel_to_cell(x: int, y: int) -> tuple[int, int]:
    return (y // TILE_PX, x // TILE_PX)


def legal_rotations_at_cell(
    game: Game, board: Board, row: int, col: int
) -> list[int]:
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
    assert win is not None
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
    return [int(i) for i in np.flatnonzero(mask) if int(i) >= n_tile and int(i) != pass_idx]


def cycle(idx: int, n: int) -> int:
    return 0 if n == 0 else (idx + 1) % n


def _terrain_name(tile, side: Side) -> str:
    t = tile.get_type(side)
    return t.name if t is not None else "GRASS"


def format_action(idx: int, board: Board) -> str:
    """Human-readable string for a flat action index in the current phase."""
    phase = board.state.phase.value
    if phase == "tiles":
        if idx == tile_pass_index(board.offset.size):
            return "pass (no legal placement)"
        action = decode(idx, off=board.offset, phase="tiles", next_tile=board.state.next_tile)
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


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------


@dataclass
class AiSummary:
    idx: int
    chosen_str: str
    score_p0_before: int
    score_p1_before: int
    elapsed_s: float


@dataclass
class Opponent:
    """Uniform façade over the two opponent kinds — their pick signatures differ
    (the champion's is ``choose_action(board)``, RuleBasedPlayer's is
    ``choose_action(game, board, mask)``), and only the champion has a budget to be
    honest about.

    name          short label shown in the sidebar / title / game-over verdict
    pick          (board, mask) -> action index; called ONLY on the worker thread
    manifest      champion_factory runtime manifest, or None for Tier-1
    budget_note   None when running at (or above) the PRODUCTION.yaml champion budget;
                  otherwise the loud "BELOW CHAMPION BUDGET …" string that must appear
                  in the UI so a win over a weakened agent can never read as a win
                  over the champion.
    """
    name: str
    pick: Callable[[Board, np.ndarray], int]
    manifest: dict | None = None
    budget_note: str | None = None
    # F-3: the agent OBJECT behind `pick`, so the GUI can drive a Rust mirror
    # (start_game once + advance for every applied action of BOTH seats). None for
    # agents that own no mirror; `mirror_protocol` duck-types it either way.
    agent: object | None = None


class GameGUI:
    def __init__(
        self,
        game: Game,
        ai: Opponent,
        visualiser,
        human_player: int,
    ) -> None:
        self.game = game
        self.ai = ai
        self.visualiser = visualiser
        self.canvas = visualiser.canvas
        self.root = self.canvas.master
        self.human = human_player
        self.board: Board = game.get_init_board()
        self.turn = 0
        # THE MIRROR PROTOCOL (F-3), seated on the board the deck was actually dealt
        # into — main thread, before any worker exists. `_apply_action` is the single
        # choke point that advances it, for the human's moves as well as the AI's.
        self._seat_mirror()

        self.selected_cell: tuple[int, int] | None = None
        self.rotation_options: list[int] = []
        self.rotation_idx: int = 0
        self.last_ai: AiSummary | None = None

        # --- AI worker thread plumbing -------------------------------------
        # The champion needs seconds per move. It runs on a daemon thread; the
        # ONLY channel back to Tk is this queue, drained by _tick() on the main
        # thread. The worker touches no widget (tkinter is not thread-safe).
        self.ai_thread: threading.Thread | None = None
        self.ai_queue: queue.Queue = queue.Queue()
        self.ai_t0: float = 0.0
        self.ai_error: str | None = None

        # Cache for tile-preview PhotoImages, keyed by (filename, rot, size).
        # Without keeping a Python ref the image is GC'd and disappears.
        self._tile_preview_refs: dict[tuple[str, int, int], object] = {}

        # Coordinate of Tier-1's most recent TILE placement, for the
        # last-move highlight. Reset when Tier-1 plays a new tile.
        self.ai_last_tile_coord: Coordinate | None = None

        # Player colors (matches the engine's meeple icon order:
        # P0=blue, P1=red).
        self._player_color = {0: "#1976d2", 1: "#c43c3c"}

        # Zoom state. base_tile_px is the unscaled tile size; zoom multiplies
        # it. Only the board canvas is rescaled — sidebar chrome is fixed.
        self.base_tile_px = 60
        self.zoom = 1.0
        self.min_zoom = 0.3
        self.max_zoom = 3.0

        # Click-vs-pan state for the board canvas (Button-1 acts as both).
        self._press_xy: tuple[int, int] | None = None
        self._panning = False
        self._pan_threshold = 5  # pixels of motion before a press becomes a pan

        # Sidebar canvas — created in _add_scrollbars_and_center. Holds all
        # chrome (scores, meeple counts, next-tile preview, buttons) at fixed
        # pixel sizes; never zooms or pans.
        self.sidebar_canvas = None  # type: ignore[assignment]

        title = f"Carcassonne — you vs {self.ai.name}"
        if self.ai.budget_note:
            title += f"   ⚠ {self.ai.budget_note}"
        self.root.title(title)
        self._add_scrollbars_and_center()

    def _add_scrollbars_and_center(self) -> None:
        """Two-canvas layout:
          - board canvas (left, expands): the visualiser's canvas, wrapped in
            scrollbars, with wheel-zoom + click-drag pan
          - sidebar canvas (right, fixed 380 px): all chrome, never moves"""
        import tkinter as tk

        SIDEBAR_W = 380

        self.canvas.pack_forget()
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)

        # Sidebar (right): fixed-width canvas, owns its own coord system
        # starting at (0, 0). Click handler routes to button hit-testing.
        self.sidebar_canvas = tk.Canvas(
            container, width=SIDEBAR_W, bg="#f6f6f6", highlightthickness=0,
        )
        self.sidebar_canvas.pack(side="right", fill="y")
        self.sidebar_canvas.bind("<Button-1>", self._on_sidebar_click)

        # Board (left): visualiser canvas + scrollbars.
        board_frame = tk.Frame(container)
        board_frame.pack(side="left", fill="both", expand=True)
        v_scroll = tk.Scrollbar(board_frame, orient="vertical", command=self.canvas.yview)
        h_scroll = tk.Scrollbar(board_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
            scrollregion=(0, 0, CANVAS_W, CANVAS_H),
        )
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Wheel zoom on board canvas only.
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)

        # Button-1 does double duty: a small motion = click, larger = pan.
        # Distinguished in _on_release by the threshold check.
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self.root.geometry("1500x900")

        def _center_view():
            self.canvas.update_idletasks()
            start_x = 15 * TILE_PX
            start_y = 15 * TILE_PX
            pad = 3 * TILE_PX
            self.canvas.xview_moveto(max(0, start_x - pad) / CANVAS_W)
            self.canvas.yview_moveto(max(0, start_y - pad) / CANVAS_H)

        self.root.after(100, _center_view)

    # -------------------- click-vs-drag pan --------------------

    def _on_press(self, event) -> None:
        self._press_xy = (event.x, event.y)
        self._panning = False
        # Prep tk's built-in scan helper so motion can pan via scan_dragto.
        self.canvas.scan_mark(event.x, event.y)

    def _on_motion(self, event) -> None:
        if self._press_xy is None:
            return
        dx = event.x - self._press_xy[0]
        dy = event.y - self._press_xy[1]
        if not self._panning and (dx * dx + dy * dy) >= self._pan_threshold ** 2:
            self._panning = True
        if self._panning:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_release(self, event) -> None:
        was_panning = self._panning
        self._press_xy = None
        self._panning = False
        if was_panning:
            return  # drag finished; don't treat as a click
        self._on_click(event)

    # -------------------- zoom --------------------

    def _on_mouse_wheel(self, event) -> None:
        """Zoom everything (board + sidebar) around the cursor position."""
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            factor = 1.1
        elif event.num == 5 or getattr(event, "delta", 0) < 0:
            factor = 1 / 1.1
        else:
            return

        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-6:
            return

        anchor_canvas_x = self.canvas.canvasx(event.x)
        anchor_canvas_y = self.canvas.canvasy(event.y)
        ratio = new_zoom / self.zoom

        self._apply_zoom(new_zoom)

        # Re-anchor view so the point under the cursor stays put.
        new_anchor_x = anchor_canvas_x * ratio
        new_anchor_y = anchor_canvas_y * ratio
        self.canvas.xview_moveto((new_anchor_x - event.x) / CANVAS_W)
        self.canvas.yview_moveto((new_anchor_y - event.y) / CANVAS_H)

    def _apply_zoom(self, new_zoom: float) -> None:
        """Rescale board tile/meeple rendering by patching the visualiser's
        class constants, clearing its image cache, updating our TILE_PX +
        board canvas extent. Sidebar is on a separate canvas and never
        rescales."""
        global TILE_PX, CANVAS_W, CANVAS_H
        from wingedsheep.carcassonne.carcassonne_visualiser import CarcassonneVisualiser
        from wingedsheep.carcassonne.objects.side import Side

        self.zoom = new_zoom
        tile_size = max(15, int(round(self.base_tile_px * new_zoom)))
        meeple_size = max(5, int(round(15 * new_zoom)))
        big_meeple_size = max(8, int(round(25 * new_zoom)))

        TILE_PX = tile_size
        # Board scrollregion grows/shrinks with zoom (engine board ~35x35
        # cells; pad to 38x22 for slack). Sidebar is unaffected.
        CANVAS_W = max(800, tile_size * 38)
        CANVAS_H = max(500, tile_size * 22)

        CarcassonneVisualiser.tile_size = tile_size
        CarcassonneVisualiser.meeple_size = meeple_size
        CarcassonneVisualiser.big_meeple_size = big_meeple_size
        CarcassonneVisualiser.meeple_position_offsets = {
            Side.TOP: (tile_size / 2, (meeple_size / 2) + 3),
            Side.RIGHT: (tile_size - (meeple_size / 2) - 3, tile_size / 2),
            Side.BOTTOM: (tile_size / 2, tile_size - (meeple_size / 2) - 3),
            Side.LEFT: ((meeple_size / 2) + 3, tile_size / 2),
            Side.CENTER: (tile_size / 2, tile_size / 2),
            Side.TOP_LEFT: (tile_size / 4, (meeple_size / 2) + 3),
            Side.TOP_RIGHT: ((tile_size / 4) * 3, (meeple_size / 2) + 3),
            Side.BOTTOM_LEFT: (tile_size / 4, tile_size - (meeple_size / 2) - 3),
            Side.BOTTOM_RIGHT: ((tile_size / 4) * 3, tile_size - (meeple_size / 2) - 3),
        }
        CarcassonneVisualiser.big_meeple_position_offsets = {
            Side.TOP: (tile_size / 2, (big_meeple_size / 2) + 3),
            Side.RIGHT: (tile_size - (big_meeple_size / 2) - 3, tile_size / 2),
            Side.BOTTOM: (tile_size / 2, tile_size - (big_meeple_size / 2) - 3),
            Side.LEFT: ((big_meeple_size / 2) + 3, tile_size / 2),
            Side.CENTER: (tile_size / 2, tile_size / 2),
            Side.TOP_LEFT: (tile_size / 4, (big_meeple_size / 2) + 3),
            Side.TOP_RIGHT: ((tile_size / 4) * 3, (big_meeple_size / 2) + 3),
            Side.BOTTOM_LEFT: (tile_size / 4, tile_size - (big_meeple_size / 2) - 3),
            Side.BOTTOM_RIGHT: ((tile_size / 4) * 3, tile_size - (big_meeple_size / 2) - 3),
        }

        # Wipe cached PhotoImages so they're regenerated at the new size.
        self.visualiser.tile_image_refs.clear()
        self.visualiser.meeple_image_refs.clear()
        self._tile_preview_refs.clear()

        self.canvas.configure(scrollregion=(0, 0, CANVAS_W, CANVAS_H))
        self._render_full()

    # -------------------- main loop tick --------------------

    def start(self) -> None:
        self._tick()
        self._advance()

    def _tick(self) -> None:
        """Tk-main-thread heartbeat (100 ms). Two jobs, both cheap:
          1. while the AI thread is alive, repaint the sidebar with a live
             elapsed-seconds counter so a multi-second think reads as progress;
          2. drain the result queue and apply the move.
        This is the ONLY place a worker result crosses into Tk."""
        if self.ai_thread is not None and self.ai_thread.is_alive():
            # Sidebar only — the board is untouched while the AI thinks, so there
            # is nothing else to repaint and no reason to burn CPU redrawing it.
            self._draw_sidebar(thinking_elapsed=time.perf_counter() - self.ai_t0)
        try:
            kind, payload = self.ai_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self.ai_thread = None
            if kind == "err":
                # A crashed worker would otherwise leave the GUI "thinking" forever.
                self.ai_error = payload
                print(payload, file=sys.stderr)
                self._draw_sidebar()
            else:
                self._commit_ai_move(payload)
        try:
            self.root.after(100, self._tick)
        except Exception:
            # Window closed (Close button / WM delete) between ticks — the pending
            # after() would otherwise raise TclError against a destroyed root.
            pass

    def _advance(self) -> None:
        if self.board.state.is_terminated():
            self._render_full()
            self._draw_final()
            return
        self.turn += 1
        self._render_full()
        if self.board.state.current_player == self.human:
            phase = self.board.state.phase.value
            mask = self.game.get_valid_moves(self.board)
            legal = [int(i) for i in np.flatnonzero(mask)]
            pass_idx = (
                tile_pass_index(self.board.offset.size) if phase == "tiles"
                else meeple_pass_index(self.board.offset.size)
            )
            if legal == [pass_idx]:
                self.root.after(400, lambda: self._apply_action(pass_idx))
        else:
            # Defer the AI turn so the just-played human move renders first.
            self.root.after(250, self._start_ai_turn)

    def _start_ai_turn(self) -> None:
        """Launch the AI on a worker thread. Returns immediately — the Tk main
        loop keeps servicing expose/resize/scroll events the whole time."""
        if self.ai_thread is not None:            # defensive: never two in flight
            return
        board = self.board                        # snapshot: Board is not mutated
        mask = self.game.get_valid_moves(board)   # main thread owns self.game
        s0_before, s1_before = board.state.scores
        self.ai_t0 = time.perf_counter()
        self.ai_thread = threading.Thread(
            target=self._ai_worker, args=(board, mask, s0_before, s1_before),
            daemon=True, name="carc-ai",
        )
        self.ai_thread.start()
        self._draw_sidebar(thinking_elapsed=0.0)

    def _ai_worker(self, board, mask, s0_before: int, s1_before: int) -> None:
        """WORKER THREAD. Pure computation + a queue.put — NO tkinter, ever.
        Everything it touches (board, mask, its own Game/agent) is thread-local
        or read-only for the duration."""
        try:
            idx = int(self.ai.pick(board, mask))
            self.ai_queue.put(("ok", AiSummary(
                idx=idx,
                chosen_str=format_action(idx, board),
                score_p0_before=s0_before,
                score_p1_before=s1_before,
                elapsed_s=time.perf_counter() - self.ai_t0,
            )))
        except BaseException:                     # noqa: BLE001 — must not die silently
            self.ai_queue.put(("err", traceback.format_exc()))

    def _commit_ai_move(self, summary: AiSummary) -> None:
        """MAIN THREAD. Apply the worker's chosen action to the live board."""
        # If the AI played a tile this turn, remember the coordinate so we can
        # highlight it on the board (border in the AI's player color). For
        # meeple actions, leave the prior tile highlight in place.
        phase = self.board.state.phase.value
        if phase == "tiles" and summary.idx != tile_pass_index(self.board.offset.size):
            tile_action = decode(
                summary.idx, off=self.board.offset, phase="tiles",
                next_tile=self.board.state.next_tile,
            )
            assert isinstance(tile_action, TileAction)
            self.ai_last_tile_coord = tile_action.coordinate

        self.last_ai = summary
        self._apply_action(summary.idx)

    # -------------------- rust mirror protocol (F-3) --------------------

    def _seat_mirror(self) -> None:
        """Seat the AI's Rust mirror on the initial board. No-op on Python."""
        from carcassonne_ai import mirror_protocol as MP

        MP.seat(self.ai.agent, self.board)

    def _advance_mirror(self, idx: int) -> None:
        """THE choke point: one applied action -> one mirror step, EITHER seat.

        Called on the Tk MAIN thread only, and never while the AI worker thread is
        alive (the turn structure serialises them: the worker's result is applied by
        `_commit_ai_move` after the thread has finished). The Rust agent hard-raises
        `MirrorDesync` if this is ever missed, so a regression here is loud."""
        from carcassonne_ai import mirror_protocol as MP

        MP.advance(self.ai.agent, idx)

    def _apply_action(self, idx: int) -> None:
        self.board, _ = self.game.get_next_state(self.board, idx)
        self._advance_mirror(idx)
        self.selected_cell = None
        self.rotation_options = []
        self.rotation_idx = 0
        self._advance()

    # -------------------- click handler --------------------

    def _on_click(self, event) -> None:
        """Click on the board canvas. Sidebar clicks come in via
        _on_sidebar_click on the separate sidebar_canvas."""
        if self.board.state.is_terminated():
            return
        if self.board.state.current_player != self.human:
            return  # ignore board clicks while the AI thinks (its turn)

        # Translate window coords -> canvas coords (the canvas is scrolled).
        x, y = int(self.canvas.canvasx(event.x)), int(self.canvas.canvasy(event.y))
        phase = self.board.state.phase.value
        if phase == "tiles":
            self._handle_tile_click(x, y)
        else:
            self._handle_meeple_click(x, y)

    def _on_sidebar_click(self, event) -> None:
        """Click on the sidebar canvas. Coords are sidebar-canvas-local."""
        x, y = int(event.x), int(event.y)
        for tag, (x0, y0, x1, y1, handler) in self._buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                handler()
                return

    def _handle_tile_click(self, x: int, y: int) -> None:
        row, col = pixel_to_cell(x, y)
        rotations = legal_rotations_at_cell(self.game, self.board, row, col)
        if not rotations:
            return
        if self.selected_cell == (row, col):
            self.rotation_idx = cycle(self.rotation_idx, len(rotations))
        else:
            self.selected_cell = (row, col)
            self.rotation_options = rotations
            self.rotation_idx = 0
        self._render_overlays()

    def _handle_meeple_click(self, x: int, y: int) -> None:
        last = self.board.state.last_tile_action
        if last is None:
            return
        legals = legal_meeple_indices(self.game, self.board)
        for idx in legals:
            cx, cy = self._meeple_dot_xy(idx, last.coordinate)
            if (x - cx) ** 2 + (y - cy) ** 2 <= 12 ** 2:
                self._apply_action(idx)
                return

    # -------------------- rendering --------------------

    def _render_full(self) -> None:
        self.visualiser.draw_game_state(self.board.state)
        self._render_overlays()

    def _render_overlays(self) -> None:
        # Wipe stale overlays first. _render_full goes through draw_game_state
        # which does canvas.delete('all'), but click-to-change-selection calls
        # us directly — without this, the old ghost lingers under the new one.
        self.canvas.delete("overlay")
        # AI's last-move highlight is drawn first so other overlays paint over
        # it (e.g. green legal-cell outline if the AI placed where you can
        # extend; the AI border stays partially visible).
        self._draw_ai_last_move_highlight()
        if self.board.state.current_player == self.human and not self.board.state.is_terminated():
            phase = self.board.state.phase.value
            if phase == "tiles":
                self._draw_legal_cells()
                if self.selected_cell is not None:
                    self._draw_selection_ghost()
            else:
                self._draw_meeple_slots()
        self._draw_sidebar()

    def _draw_ai_last_move_highlight(self) -> None:
        if self.ai_last_tile_coord is None:
            return
        ai_player = 1 - self.human
        color = self._player_color.get(ai_player, "#000")
        c = self.ai_last_tile_coord
        x0, y0 = c.column * TILE_PX, c.row * TILE_PX
        # Slightly inset so it reads as a frame, not a fill.
        self.canvas.create_rectangle(
            x0 + 1, y0 + 1, x0 + TILE_PX - 1, y0 + TILE_PX - 1,
            outline=color, width=4, tags="overlay",
        )

    def _draw_legal_cells(self) -> None:
        cells = all_legal_tile_cells(self.game, self.board)
        for (row, col) in cells:
            x0, y0 = col * TILE_PX, row * TILE_PX
            # Orange: high contrast against the green grass tiles. The earlier
            # green outline blended in with the field terrain.
            self.canvas.create_rectangle(
                x0, y0, x0 + TILE_PX, y0 + TILE_PX,
                outline="#ff6f00", width=2, tags="overlay",
            )

    def _draw_selection_ghost(self) -> None:
        assert self.selected_cell is not None
        row, col = self.selected_cell
        rot = self.rotation_options[self.rotation_idx]
        x0, y0 = col * TILE_PX, row * TILE_PX

        # Show the actual rotated tile image at the placement location, so
        # the user sees what they'd be committing before clicking Confirm.
        next_tile = self.board.state.next_tile
        if next_tile is not None:
            preview = self._get_tile_preview(next_tile, rot, TILE_PX)
            if preview is not None:
                self.canvas.create_image(
                    x0, y0, image=preview, anchor="nw", tags="overlay",
                )

        # Yellow selection border (universal "currently editing"; distinct
        # from the player-color borders used for placed/last-move tiles).
        self.canvas.create_rectangle(
            x0, y0, x0 + TILE_PX, y0 + TILE_PX,
            outline="#ffc107", width=4, tags="overlay",
        )
        # Compact rotation badge in the corner so the user knows what cycling
        # the click changes; small enough to not obscure the tile art.
        self.canvas.create_text(
            x0 + 14, y0 + 10, text=f"r{rot}",
            fill="#000", font=("Arial", 10, "bold"), tags="overlay",
        )

    def _draw_meeple_slots(self) -> None:
        last = self.board.state.last_tile_action
        if last is None:
            return
        legals = legal_meeple_indices(self.game, self.board)
        coord = last.coordinate
        for idx in legals:
            cx, cy = self._meeple_dot_xy(idx, coord)
            color = self._meeple_dot_color(idx, coord)
            self.canvas.create_oval(
                cx - 9, cy - 9, cx + 9, cy + 9,
                fill=color, outline="black", width=2, tags="overlay",
            )

    def _meeple_dot_xy(self, idx: int, last_coord: Coordinate) -> tuple[int, int]:
        action = decode(idx, off=self.board.offset, phase="meeples", last_tile_coord=last_coord)
        assert isinstance(action, MeepleAction)
        side = action.coordinate_with_side.side
        ox, oy = self.visualiser.meeple_position_offsets[side]
        x = int(last_coord.column * TILE_PX + ox)
        y = int(last_coord.row * TILE_PX + oy)
        return x, y

    def _get_tile_preview(self, tile, rot: int, size: int):
        """Load `tile.image` from the engine's images dir, resize to `size`x
        `size`, rotate -90*rot degrees, return a PhotoImage. Cached per
        (filename, rot, size). Returns None if the load fails (defensive —
        the sidebar should still render text)."""
        filename = getattr(tile, "image", None)
        if not filename:
            return None
        key = (filename, rot, size)
        cached = self._tile_preview_refs.get(key)
        if cached is not None:
            return cached
        try:
            from PIL import Image, ImageTk
            import os
            path = os.path.join(self.visualiser.images_path, filename)
            img = Image.open(path).resize((size, size), Image.LANCZOS)
            if rot:
                img = img.rotate(-90 * rot)
            photo = ImageTk.PhotoImage(img)
            self._tile_preview_refs[key] = photo
            return photo
        except Exception as e:
            # Don't fail the whole render over a missing icon.
            print(f"  [warn] tile preview load failed for {filename}: {e}", file=sys.stderr)
            return None

    def _meeple_dot_color(self, idx: int, last_coord: Coordinate) -> str:
        action = decode(idx, off=self.board.offset, phase="meeples", last_tile_coord=last_coord)
        assert isinstance(action, MeepleAction)
        side = action.coordinate_with_side.side
        last_tile = self.board.state.board[last_coord.row][last_coord.column]
        if last_tile is None:
            return DEFAULT_DOT_COLOR
        terrain = last_tile.get_type(side)
        return TERRAIN_COLOR.get(terrain, DEFAULT_DOT_COLOR)

    # -------------------- sidebar --------------------

    def _draw_sidebar(self, thinking_elapsed: float | None = None) -> None:
        # Sidebar lives on its own canvas — wipe and redraw. Canvas's own
        # bg color (#f6f6f6) shows through, no manual bg rect needed.
        # `thinking_elapsed` is set only by _tick while the AI worker runs.
        sb = self.sidebar_canvas
        sb.delete("all")
        self._buttons: dict[str, tuple[int, int, int, int, Callable[[], None]]] = {}

        x = SIDEBAR_PAD
        y = SIDEBAR_PAD
        line_h = 24

        s0, s1 = self.board.state.scores
        cur = self.board.state.current_player
        phase = self.board.state.phase.value
        who = "you" if cur == self.human else self.ai.name
        you_label = "You (P0)" if self.human == 0 else "You (P1)"
        ai_label = (f"{self.ai.name} (P1)" if self.human == 0
                    else f"{self.ai.name} (P0)")
        you_score = s0 if self.human == 0 else s1
        ai_score = s1 if self.human == 0 else s0
        tiles_left = len(self.board.state.deck)

        # Meeple counts. state.meeples[p] = NORMAL meeples in hand;
        # placed_meeples[p] = list of all placed meeples (NORMAL + FARMER).
        # Total starting per player is 7 in this engine.
        you_idx = self.human
        ai_idx = 1 - self.human
        you_in_hand = int(self.board.state.meeples[you_idx])
        ai_in_hand = int(self.board.state.meeples[ai_idx])
        you_placed = len(self.board.state.placed_meeples[you_idx])
        ai_placed = len(self.board.state.placed_meeples[ai_idx])

        for line in [
            f"Turn {self.turn}",
            f"Phase: {phase}",
            f"To move: P{cur} ({who})",
            f"Tiles left: {tiles_left}",
            "",
            f"{you_label}: {you_score}",
            f"  meeples: {you_in_hand} in hand · {you_placed} on board",
            f"{ai_label}: {ai_score}",
            f"  meeples: {ai_in_hand} in hand · {ai_placed} on board",
        ]:
            sb.create_text(x, y, text=line, anchor="nw", font=("Arial", 14))
            y += line_h
        y += 12

        # Honesty banner: a sub-champion budget must be impossible to miss, so it
        # sits above the fold in the sidebar as well as in the window title.
        if self.ai.budget_note:
            sb.create_rectangle(x - 6, y - 4, x + 340, y + line_h + 4,
                                fill="#ffe0b2", outline="#e65100", width=2)
            sb.create_text(x, y, text=f"⚠ {self.ai.budget_note}", anchor="nw",
                           font=("Arial", 11, "bold"), fill="#bf360c")
            y += line_h + 14

        if self.ai_error is not None:
            sb.create_text(x, y, text="AI ERROR — see terminal", anchor="nw",
                           font=("Arial", 13, "bold"), fill="#b71c1c")
            y += line_h
            sb.create_text(x, y, text=self.ai_error.strip().splitlines()[-1][:44],
                           anchor="nw", font=("Arial", 9), fill="#b71c1c")
            y += line_h + 8

        if thinking_elapsed is not None:
            # Live counter driven by _tick; the whole point is that a 3 s think
            # looks like progress, not a frozen window.
            sb.create_rectangle(x - 6, y - 4, x + 340, y + line_h + 4,
                                fill="#e3f2fd", outline="#1976d2", width=2)
            sb.create_text(
                x, y, text=f"{self.ai.name} thinking… ({thinking_elapsed:.1f}s)",
                anchor="nw", font=("Arial", 13, "bold"), fill="#0d47a1",
            )
            y += line_h + 14

        if phase == "tiles" and self.board.state.next_tile is not None:
            tile = self.board.state.next_tile
            desc = tile.description or "(no description)"
            edges = (
                f"top={_terrain_name(tile, Side.TOP)}  "
                f"right={_terrain_name(tile, Side.RIGHT)}"
            )
            edges2 = (
                f"bot={_terrain_name(tile, Side.BOTTOM)}  "
                f"left={_terrain_name(tile, Side.LEFT)}"
            )
            extras = []
            if getattr(tile, "shield", False):
                extras.append("shield")
            if getattr(tile, "chapel", False):
                extras.append("chapel")
            if getattr(tile, "flowers", False):
                extras.append("flowers")
            if tile.has_river():
                extras.append("river")
            extra_str = "  [" + ", ".join(extras) + "]" if extras else ""

            # Tile preview image: rotated to whichever rotation the user is
            # currently previewing (or rot=0 if no cell selected). Size 2x the
            # board tile so it's clearly visible in the sidebar.
            preview_rot = (
                self.rotation_options[self.rotation_idx]
                if self.selected_cell is not None and self.rotation_options
                else 0
            )
            sb.create_text(
                x, y, text=f"Next tile{extra_str}  (preview rot={preview_rot})",
                anchor="nw", font=("Arial", 12, "bold"),
            )
            y += line_h
            # Preview image is rendered at a fixed sidebar size — independent
            # of board zoom, so chrome stays stable.
            preview_size = 120
            preview_img = self._get_tile_preview(tile, preview_rot, preview_size)
            if preview_img is not None:
                sb.create_rectangle(
                    x, y, x + preview_size, y + preview_size,
                    outline="#444", width=2,
                )
                sb.create_image(x, y, image=preview_img, anchor="nw")
                y += preview_size + 8

            for line in [f"  {desc}", f"  {edges}", f"  {edges2}"]:
                sb.create_text(x, y, text=line, anchor="nw", font=("Arial", 11))
                y += line_h
            y += 12

        if self.last_ai is not None and thinking_elapsed is None:
            sb.create_text(
                x, y, text=f"{self.ai.name}'s last move:", anchor="nw",
                font=("Arial", 13, "bold"),
            )
            y += line_h
            sb.create_text(
                x, y, text=f"  {self.last_ai.chosen_str}",
                anchor="nw", font=("Arial", 12),
            )
            y += line_h
            ds0 = s0 - self.last_ai.score_p0_before
            ds1 = s1 - self.last_ai.score_p1_before
            ai_delta = ds1 if self.human == 0 else ds0
            you_delta = ds0 if self.human == 0 else ds1
            sb.create_text(
                x, y,
                text=f"  scored: {self.ai.name} +{ai_delta}, you +{you_delta}"
                     f"   ({self.last_ai.elapsed_s:.1f}s)",
                anchor="nw", font=("Arial", 11), fill="#666",
            )
            y += line_h
            y += 12

        is_human_turn = (
            self.board.state.current_player == self.human
            and not self.board.state.is_terminated()
        )
        if is_human_turn:
            phase = self.board.state.phase.value
            if phase == "tiles" and self.selected_cell is not None:
                self._draw_button("Confirm", x, y, "#2e7d32", self._confirm_tile)
                y += 50
                self._draw_button("Cancel", x, y, "#777", self._cancel_tile)
                y += 50
            if phase == "meeples":
                self._draw_button("Skip meeple", x, y, "#777", self._skip_meeple)
                y += 50

    def _draw_button(self, label: str, x: int, y: int, color: str, handler: Callable[[], None]) -> None:
        sb = self.sidebar_canvas
        w, h = 200, 40
        x1, y1 = x + w, y + h
        sb.create_rectangle(x, y, x1, y1, fill=color, outline="black", width=2)
        sb.create_text(
            x + w // 2, y + h // 2, text=label,
            fill="white", font=("Arial", 13, "bold"),
        )
        self._buttons[label] = (x, y, x1, y1, handler)

    def _confirm_tile(self) -> None:
        if self.selected_cell is None:
            return
        row, col = self.selected_cell
        rot = self.rotation_options[self.rotation_idx]
        idx = tile_action_index(self.board.offset, row, col, rot)
        self._apply_action(idx)

    def _cancel_tile(self) -> None:
        self.selected_cell = None
        self.rotation_options = []
        self.rotation_idx = 0
        self._render_overlays()

    def _skip_meeple(self) -> None:
        self._apply_action(meeple_pass_index(self.board.offset.size))

    def _draw_final(self) -> None:
        sb = self.sidebar_canvas
        sb.delete("all")
        s0, s1 = self.board.state.scores
        diff = s0 - s1
        # NOTE (WC tie-break plumbing, 2026-08-23): this already branched on an exact
        # tie before computing `winner`, so the "silent player-1 win on a tie" bug
        # described for this line did NOT reproduce in this file as found — `winner`
        # was never even evaluated in the diff==0 case. Routed through
        # `game_wrapper.resolve_winner` anyway for a single source of truth on winner
        # determination; wc_tiebreak is NOT wired to a CLI flag here (out of this
        # pass's scope — a human-facing GUI, not the eval/harness pipeline), so this
        # is a no-op refactor: resolve_winner(s0, s1, wc_tiebreak=False) returns -1 on
        # an exact tie exactly like the old `diff == 0` branch did.
        winner = resolve_winner(s0, s1, wc_tiebreak=False)
        if winner == -1:
            verdict = "Tie!"
        else:
            verdict = "You win!" if winner == self.human else f"{self.ai.name} wins."
        x = SIDEBAR_PAD
        y = 100
        for line in ["GAME OVER", "", f"P0: {s0}", f"P1: {s1}",
                     f"Diff: {abs(diff)}", "", verdict]:
            sb.create_text(x, y, text=line, anchor="nw", font=("Arial", 18, "bold"))
            y += 36
        sb.create_text(x, y, text=f"(opponent: {self.ai.name})", anchor="nw",
                       font=("Arial", 11), fill="#666", width=340)
        y += 26
        if self.ai.budget_note:
            # Never let a win over a throttled agent read as a win over the champion.
            sb.create_text(x, y, text="⚠ " + self.ai.budget_note, anchor="nw",
                           font=("Arial", 12, "bold"), fill="#bf360c", width=340)
            y += 56
        self._buttons = {}
        self._draw_button("Close", x, y + 20, "#555", self.root.destroy)


def _patch_pillow_antialias() -> None:
    """Pillow 10+ removed Image.ANTIALIAS (deprecated in 9.1). The vendored
    CarcassonneVisualiser uses it in 5 places (tile + meeple resize). Without
    this shim, the first draw silently crashes inside the engine — canvas is
    wiped but never redrawn, leaving a blank window."""
    from PIL import Image
    if not hasattr(Image, "ANTIALIAS"):
        # LANCZOS is the modern best-quality downsample filter and the named
        # successor; in Pillow 12 it's at Image.Resampling.LANCZOS but the
        # numeric Image.LANCZOS alias is still valid.
        Image.ANTIALIAS = Image.Resampling.LANCZOS


def _apply_scale(scale: float) -> None:
    """Resize every UI dimension to `scale` of the original. Patches both this
    module's layout constants AND the vendored CarcassonneVisualiser class
    attributes (which control tile/meeple image rendering). Must be called
    BEFORE instantiating CarcassonneVisualiser, since the offset dicts are
    evaluated at class definition time and tile images are cached after first
    draw."""
    global TILE_PX, CANVAS_W, CANVAS_H

    TILE_PX = max(20, int(round(60 * scale)))
    CANVAS_W = max(800, int(round(2300 * scale)))
    CANVAS_H = max(500, int(round(1300 * scale)))

    from wingedsheep.carcassonne.carcassonne_visualiser import CarcassonneVisualiser
    from wingedsheep.carcassonne.objects.side import Side

    tile_size = TILE_PX
    meeple_size = max(6, int(round(15 * scale)))
    big_meeple_size = max(10, int(round(25 * scale)))

    CarcassonneVisualiser.tile_size = tile_size
    CarcassonneVisualiser.meeple_size = meeple_size
    CarcassonneVisualiser.big_meeple_size = big_meeple_size

    # Re-derive offset dicts (the originals were computed at class-definition
    # time using the un-scaled constants).
    CarcassonneVisualiser.meeple_position_offsets = {
        Side.TOP: (tile_size / 2, (meeple_size / 2) + 3),
        Side.RIGHT: (tile_size - (meeple_size / 2) - 3, tile_size / 2),
        Side.BOTTOM: (tile_size / 2, tile_size - (meeple_size / 2) - 3),
        Side.LEFT: ((meeple_size / 2) + 3, tile_size / 2),
        Side.CENTER: (tile_size / 2, tile_size / 2),
        Side.TOP_LEFT: (tile_size / 4, (meeple_size / 2) + 3),
        Side.TOP_RIGHT: ((tile_size / 4) * 3, (meeple_size / 2) + 3),
        Side.BOTTOM_LEFT: (tile_size / 4, tile_size - (meeple_size / 2) - 3),
        Side.BOTTOM_RIGHT: ((tile_size / 4) * 3, tile_size - (meeple_size / 2) - 3),
    }
    CarcassonneVisualiser.big_meeple_position_offsets = {
        Side.TOP: (tile_size / 2, (big_meeple_size / 2) + 3),
        Side.RIGHT: (tile_size - (big_meeple_size / 2) - 3, tile_size / 2),
        Side.BOTTOM: (tile_size / 2, tile_size - (big_meeple_size / 2) - 3),
        Side.LEFT: ((big_meeple_size / 2) + 3, tile_size / 2),
        Side.CENTER: (tile_size / 2, tile_size / 2),
        Side.TOP_LEFT: (tile_size / 4, (big_meeple_size / 2) + 3),
        Side.TOP_RIGHT: ((tile_size / 4) * 3, (big_meeple_size / 2) + 3),
        Side.BOTTOM_LEFT: (tile_size / 4, tile_size - (big_meeple_size / 2) - 3),
        Side.BOTTOM_RIGHT: ((tile_size / 4) * 3, tile_size - (big_meeple_size / 2) - 3),
    }


def build_opponent(kind: str, *, seed: int, sims: int | None,
                   k_dets: int | None, verbose: bool = True,
                   backend: str = "inherit", rust_threads: int | None = None,
                   profile: str = "desktop") -> Opponent:
    """Construct the AI side and wrap it in the uniform `Opponent` façade.

    The agent gets its OWN `Game` instance: the GUI's Game carries a legal-moves
    cache and the agent runs on a worker thread, so giving each side a private
    Game removes any possibility of a cross-thread cache race. (The turn structure
    already serialises them, but the isolation is free.)

    Strength knobs are NEVER hardcoded here — `make_production_champion` reads
    governance/PRODUCTION.yaml. `sims`/`k_dets` are honest overrides only."""
    ai_game = Game(enable_legal_moves_cache=True)

    if kind == "tier1":
        from carcassonne_ai.rule_based_player import RuleBasedPlayer
        tier1 = RuleBasedPlayer(seed=seed)
        return Opponent(
            name="Tier-1",
            pick=lambda board, mask: tier1.choose_action(ai_game, board, mask),
            # Not a budget override — a different (much weaker) agent entirely,
            # so it is named, not flagged.
            budget_note=None,
        )

    from carcassonne_ai.champion_factory import (
        load_production_spec, make_production_champion,
    )
    from carcassonne_ai.mirror_protocol import resolve_execution

    spec = load_production_spec()
    eff_sims = spec.sims_per_det if sims is None else int(sims)
    eff_k = spec.k_dets if k_dets is None else int(k_dets)
    # WHICH ENGINE (F-3). `--backend auto` reads PRODUCTION.yaml; the default stays
    # python, so a bare invocation is byte-identical to before the flag. The GUI drives
    # the Rust mirror (GameGUI._seat_mirror / _advance_mirror), so rust is safe here —
    # and it is the difference between ~12.7 s and ~1.3 s per move at the champion
    # budget on a window the human is staring at. Same player either way (G4/G6).
    # ⚠️ parallel_workers is NOT resolved here even on python: this GUI has never run
    # the spawn split (the agent lives on a daemon worker thread), and quietly adding
    # it would be a different change wearing this one's clothes.
    execution = resolve_execution(backend, profile=profile, rust_threads=rust_threads)
    # backend is passed EXPLICITLY in both directions — never omitted on the python
    # leg. Omitting it would mean "whatever the factory defaults to", so the day that
    # default flips, `--backend python` would quietly build a Rust champion.
    agent = make_production_champion(
        "fair", game=ai_game, seed=seed, sims=eff_sims, k_dets=eff_k,
        exact_endgame=True, verify=True, backend=execution["backend"],
        **({"rust_threads": execution["rust_threads"]} if execution.is_rust else {}),
    )
    manifest = getattr(agent, "manifest", None)

    # Honesty: mirror play_harness.py's runtime_budget_override. Anything short of
    # the YAML budget is NOT the champion and must say so, everywhere it is visible.
    budget_note = None
    name = "Champion"
    if (eff_sims, eff_k) != (spec.sims_per_det, spec.k_dets):
        full = spec.k_dets * spec.sims_per_det
        budget_note = (
            f"BELOW CHAMPION BUDGET — running k{eff_k}x{eff_sims}={eff_k * eff_sims} "
            f"sims/move vs the champion's k{spec.k_dets}x{spec.sims_per_det}={full}. "
            f"This is a WEAKENED agent; beating it is not beating the champion."
        )
        name = f"Champion(weakened k{eff_k}x{eff_sims})"

    if verbose:
        print(f"[champion] {spec.champion_id}  agent={type(agent).__name__}  "
              f"k_dets={eff_k} sims_per_det={eff_sims} total={eff_k * eff_sims} "
              f"exact_K<={spec.exact_max_k}  {execution.describe()}")
        if manifest is not None:
            import json
            print("[champion] runtime manifest:")
            print(json.dumps(manifest, indent=1, default=str))
        if budget_note:
            print(f"[champion] ⚠ {budget_note}")

    return Opponent(
        name=name,
        pick=lambda board, mask: agent.choose_action(board),
        manifest=manifest,
        budget_note=budget_note,
        agent=agent,          # F-3: the GUI drives this object's mirror
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="play_vs_tier1_gui",
        description="Play the current deploy champion (or Tier-1) with a mouse.",
    )
    p.add_argument("--opponent", choices=("champion", "tier1"), default="champion",
                   help="champion = the PRODUCTION.yaml fair deploy champion "
                        "(FairHeuristicPriorAgent, ~3 s/move). tier1 = the old "
                        "instant rule-based player (SATURATED reference, much weaker).")
    p.add_argument("--player", type=int, choices=(0, 1), default=0,
                   help="your seat: 0 = you go first, 1 = the AI goes first")
    p.add_argument("--seed", type=int, default=None,
                   help="deck seed (also seeds the agent); random if unset")
    p.add_argument("--sims", type=int, default=None,
                   help="sims per determinization. DEFAULT = the PRODUCTION.yaml "
                        "budget (fair_deploy.sims_per_det). Lowering it ONLY speeds "
                        "the AI up and plays a WEAKER-THAN-CHAMPION agent — the title "
                        "bar and sidebar then both say BELOW CHAMPION BUDGET. "
                        "Ignored for --opponent tier1.")
    p.add_argument("--k-dets", type=int, default=None,
                   help="determinizations per move. DEFAULT = the PRODUCTION.yaml "
                        "budget (fair_deploy.k_dets). Same honesty rule as --sims.")
    p.add_argument("--scale", type=float, default=1.0,
                   help="UI scale factor (0.5 = half size, 1.0 = original)")
    p.add_argument("--backend", choices=("inherit", "python", "rust", "auto"),
                   default="inherit",
                   help="which ENGINE computes the champion's search. inherit "
                        "(DEFAULT) = champion_factory's own default, today python — a "
                        "bare invocation is byte-identical to before this flag, and a "
                        "future flip of that default reaches this GUI unedited. python "
                        "= pin it. rust = carc_rs (~12.7 s to ~1.3 s per move at the "
                        "champion budget, i.e. the difference between a hang and a "
                        "pause). auto = the deploy profile's backend from "
                        "PRODUCTION.yaml. The GUI drives the Rust mirror, so all four "
                        "are safe; the engine never changes the play.")
    p.add_argument("--rust-threads", type=int, default=None,
                   help="backend=rust only: fold the k worlds across this many OS "
                        "threads inside one GIL-released call (default: the profile's "
                        "rust_threads, else 1).")
    p.add_argument("--profile", default="desktop",
                   help="deploy EXECUTION profile in PRODUCTION.yaml consulted by "
                        "--backend auto / --rust-threads (default: desktop). The BUDGET "
                        "still comes from fair_deploy/--sims/--k-dets.")
    args = p.parse_args(argv)

    if args.opponent == "tier1" and (args.sims is not None or args.k_dets is not None):
        print("[warn] --sims/--k-dets are champion-only; ignored for --opponent tier1",
              file=sys.stderr)
    if args.opponent == "tier1" and args.backend not in ("python", "inherit"):
        print("[warn] --backend is champion-only (RuleBasedPlayer has no carc_rs port "
              "and needs none — it answers instantly); ignored for --opponent tier1",
              file=sys.stderr)

    # Build the agent BEFORE any Tk work: champion_factory's verify raises on a leaf
    # mismatch, and a traceback in a terminal beats one behind a half-drawn window.
    opponent = build_opponent(
        args.opponent, seed=args.seed if args.seed is not None else 0,
        sims=args.sims, k_dets=args.k_dets,
        backend=args.backend, rust_threads=args.rust_threads, profile=args.profile,
    )

    _patch_pillow_antialias()
    _apply_scale(args.scale)

    # Seed HERE, not earlier: the engine shuffles the deck inside GameGUI.__init__'s
    # get_init_board() off the global `random`, so seeding immediately before it keeps
    # --seed -> deck reproducible regardless of what agent construction consumed.
    if args.seed is not None:
        random.seed(args.seed)

    # Locked scope (2p, Base + Farmers, no River/I&C/Abbots/Big meeples) is enforced
    # by Game's own defaults + its constructor guards — this GUI passes no tile_sets
    # or supplementary_rules, so it inherits exactly that.
    game = Game(enable_legal_moves_cache=True)
    assert game.players == 2 and game.tile_sets == (TileSet.BASE,)
    assert game.supplementary_rules == (SupplementaryRule.FARMERS,)

    from wingedsheep.carcassonne.carcassonne_visualiser import CarcassonneVisualiser
    visualiser = CarcassonneVisualiser()

    gui = GameGUI(game=game, ai=opponent, visualiser=visualiser,
                  human_player=args.player)
    gui.start()

    visualiser.canvas.master.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
