"""Click-through GUI for human-vs-Tier1 Carcassonne.

Adapted from `play_vs_mcts_gui.py` (play-vs-mcts branch) with MCTS replaced by
the rule-based Tier-1 player. Tier-1 picks instantly (no thread needed; the
1-ply virtual_score lookup is ~50-200 ms even mid-game), so the threading +
"thinking..." UI is dropped.

  python scripts/play_vs_tier1_gui.py --player 0 --seed 42

Requires a DISPLAY: WSLg on Windows 11 (WSL2), an X server with X11 forwarding,
or run on a desktop with tkinter installed.

Interaction:
  TILES phase   - legal cells outlined green; click a cell to select it,
                  click again to cycle rotation, click [Confirm] to commit.
                  [Cancel] clears the selection.
  MEEPLES phase - colored dots appear on each legal slot of the just-placed
                  tile. Click a dot to commit, or [Skip] to decline.
  Tier-1 turn   - sidebar shows the chosen move + score impact after each
                  Tier-1 turn.
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

# Allow running directly without `pip install -e .`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from carcassonne_ai.action_space import (
    decode,
    meeple_pass_index,
    tile_action_count,
    tile_pass_index,
)
from carcassonne_ai.game_wrapper import Board, Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer

from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType


# Layout. These are derived from `--scale` at startup; the defaults below
# match the unscaled (1.0) original. _apply_scale() reassigns them.
TILE_PX = 60                # matches CarcassonneVisualiser.tile_size
SIDEBAR_X = 1700            # sidebar starts at this canvas x; left of it is board
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


class GameGUI:
    def __init__(
        self,
        game: Game,
        ai: RuleBasedPlayer,
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

        self.selected_cell: tuple[int, int] | None = None
        self.rotation_options: list[int] = []
        self.rotation_idx: int = 0
        self.last_ai: AiSummary | None = None

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
        # it. The wheel zooms the WHOLE canvas (board + sidebar both scale).
        self.base_tile_px = 60
        self.zoom = 1.0
        self.min_zoom = 0.3
        self.max_zoom = 3.0

        self.canvas.bind("<Button-1>", self._on_click)
        self.root.title("Carcassonne — you vs Tier-1")
        self._add_scrollbars_and_center()

    def _add_scrollbars_and_center(self) -> None:
        """Wrap the visualiser's canvas in scrollbars, bind mouse-wheel for
        zoom, and auto-scroll to the start-tile area."""
        import tkinter as tk

        # Repack the visualiser's canvas inside a Frame with scrollbars.
        self.canvas.pack_forget()
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)
        v_scroll = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        h_scroll = tk.Scrollbar(container, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
            scrollregion=(0, 0, CANVAS_W, CANVAS_H),
        )
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Wheel zoom. WSL/Linux X11 emit Button-4 (up) / Button-5 (down);
        # other platforms emit <MouseWheel> with event.delta.
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)

        # Make the window large by default; user can resize.
        self.root.geometry("1500x900")

        # Auto-scroll so the start-tile area (engine ~15,15) is visible.
        def _center_view():
            self.canvas.update_idletasks()
            start_x = 15 * TILE_PX
            start_y = 15 * TILE_PX
            pad = 3 * TILE_PX
            self.canvas.xview_moveto(max(0, start_x - pad) / CANVAS_W)
            self.canvas.yview_moveto(max(0, start_y - pad) / CANVAS_H)

        self.root.after(100, _center_view)

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
        """Rescale tile/meeple rendering by patching the visualiser's class
        constants, clearing its image cache, updating our own TILE_PX +
        SIDEBAR_X + canvas extent, then re-rendering."""
        global TILE_PX, SIDEBAR_X, CANVAS_W, CANVAS_H
        from wingedsheep.carcassonne.carcassonne_visualiser import CarcassonneVisualiser
        from wingedsheep.carcassonne.objects.side import Side

        self.zoom = new_zoom
        tile_size = max(15, int(round(self.base_tile_px * new_zoom)))
        meeple_size = max(5, int(round(15 * new_zoom)))
        big_meeple_size = max(8, int(round(25 * new_zoom)))

        TILE_PX = tile_size
        # Sidebar starts past where a typical board extends; scale with zoom.
        SIDEBAR_X = max(400, int(round(1700 * new_zoom)))
        CANVAS_W = max(800, int(round(2300 * new_zoom)))
        CANVAS_H = max(500, int(round(1300 * new_zoom)))

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
        self._advance()

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
            # Defer Tier-1 turn so the just-played human move renders first.
            self.root.after(250, self._run_ai_turn)

    def _run_ai_turn(self) -> None:
        mask = self.game.get_valid_moves(self.board)
        s0_before, s1_before = self.board.state.scores
        idx = self.ai.choose_action(self.game, self.board, mask)
        chosen_str = format_action(idx, self.board)

        # If the AI played a tile this turn, remember the coordinate so we can
        # highlight it on the board (border in the AI's player color). For
        # meeple actions, leave the prior tile highlight in place.
        phase = self.board.state.phase.value
        if phase == "tiles" and idx != tile_pass_index(self.board.offset.size):
            tile_action = decode(
                idx, off=self.board.offset, phase="tiles",
                next_tile=self.board.state.next_tile,
            )
            assert isinstance(tile_action, TileAction)
            self.ai_last_tile_coord = tile_action.coordinate

        self.last_ai = AiSummary(
            idx=idx,
            chosen_str=chosen_str,
            score_p0_before=s0_before,
            score_p1_before=s1_before,
        )
        self._apply_action(idx)

    def _apply_action(self, idx: int) -> None:
        self.board, _ = self.game.get_next_state(self.board, idx)
        self.selected_cell = None
        self.rotation_options = []
        self.rotation_idx = 0
        self._advance()

    # -------------------- click handler --------------------

    def _on_click(self, event) -> None:
        if self.board.state.is_terminated():
            return
        if self.board.state.current_player != self.human:
            return  # ignore clicks during Tier-1 turn

        # Translate window coords -> canvas coords (the canvas is scrolled).
        x, y = int(self.canvas.canvasx(event.x)), int(self.canvas.canvasy(event.y))
        if x >= SIDEBAR_X:
            self._handle_sidebar_click(x, y)
            return
        phase = self.board.state.phase.value
        if phase == "tiles":
            self._handle_tile_click(x, y)
        else:
            self._handle_meeple_click(x, y)

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

    def _handle_sidebar_click(self, x: int, y: int) -> None:
        for tag, (x0, y0, x1, y1, handler) in self._buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                handler()
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

    def _draw_sidebar(self) -> None:
        self.canvas.delete("sidebar")
        self._buttons: dict[str, tuple[int, int, int, int, Callable[[], None]]] = {}

        x = SIDEBAR_X + SIDEBAR_PAD
        y = SIDEBAR_PAD
        line_h = 24

        self.canvas.create_rectangle(
            SIDEBAR_X, 0, CANVAS_W, CANVAS_H,
            fill="#f6f6f6", outline="", tags="sidebar",
        )
        self.canvas.create_line(
            SIDEBAR_X, 0, SIDEBAR_X, CANVAS_H,
            fill="#bbb", tags="sidebar",
        )

        s0, s1 = self.board.state.scores
        cur = self.board.state.current_player
        phase = self.board.state.phase.value
        who = "you" if cur == self.human else "Tier-1"
        you_label = "You (P0)" if self.human == 0 else "You (P1)"
        ai_label = "Tier-1 (P1)" if self.human == 0 else "Tier-1 (P0)"
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
            self.canvas.create_text(
                x, y, text=line, anchor="nw",
                font=("Arial", 14), tags="sidebar",
            )
            y += line_h
        y += 12

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
            self.canvas.create_text(
                x, y, text=f"Next tile{extra_str}  (preview rot={preview_rot})",
                anchor="nw", font=("Arial", 12, "bold"), tags="sidebar",
            )
            y += line_h
            preview_size = TILE_PX * 2
            preview_img = self._get_tile_preview(tile, preview_rot, preview_size)
            if preview_img is not None:
                # Draw a border so the tile reads as a tile, not floating art.
                self.canvas.create_rectangle(
                    x, y, x + preview_size, y + preview_size,
                    outline="#444", width=2, tags="sidebar",
                )
                self.canvas.create_image(
                    x, y, image=preview_img, anchor="nw", tags="sidebar",
                )
                y += preview_size + 8

            for line in [f"  {desc}", f"  {edges}", f"  {edges2}"]:
                self.canvas.create_text(
                    x, y, text=line, anchor="nw",
                    font=("Arial", 11), tags="sidebar",
                )
                y += line_h
            y += 12

        if self.last_ai is not None:
            self.canvas.create_text(
                x, y, text="Tier-1's last move:", anchor="nw",
                font=("Arial", 13, "bold"), tags="sidebar",
            )
            y += line_h
            self.canvas.create_text(
                x, y, text=f"  {self.last_ai.chosen_str}",
                anchor="nw", font=("Arial", 12), tags="sidebar",
            )
            y += line_h
            # Score delta this turn (after it played).
            ds0 = s0 - self.last_ai.score_p0_before
            ds1 = s1 - self.last_ai.score_p1_before
            ai_delta = ds1 if self.human == 0 else ds0
            you_delta = ds0 if self.human == 0 else ds1
            self.canvas.create_text(
                x, y,
                text=f"  scored: Tier-1 +{ai_delta}, you +{you_delta}",
                anchor="nw", font=("Arial", 11), fill="#666", tags="sidebar",
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
        w, h = 200, 40
        x1, y1 = x + w, y + h
        self.canvas.create_rectangle(
            x, y, x1, y1, fill=color, outline="black", width=2, tags="sidebar",
        )
        self.canvas.create_text(
            x + w // 2, y + h // 2, text=label,
            fill="white", font=("Arial", 13, "bold"), tags="sidebar",
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
        self.canvas.delete("sidebar")
        s0, s1 = self.board.state.scores
        diff = s0 - s1
        if diff == 0:
            verdict = "Tie!"
        else:
            winner = 0 if diff > 0 else 1
            verdict = "You win!" if winner == self.human else "Tier-1 wins."
        self.canvas.create_rectangle(
            SIDEBAR_X, 0, CANVAS_W, CANVAS_H,
            fill="#f6f6f6", outline="", tags="sidebar",
        )
        x = SIDEBAR_X + SIDEBAR_PAD
        y = 100
        for line in [
            "GAME OVER",
            "",
            f"P0: {s0}",
            f"P1: {s1}",
            f"Diff: {abs(diff)}",
            "",
            verdict,
        ]:
            self.canvas.create_text(
                x, y, text=line, anchor="nw",
                font=("Arial", 18, "bold"), tags="sidebar",
            )
            y += 36
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
    global TILE_PX, SIDEBAR_X, CANVAS_W, CANVAS_H

    TILE_PX = max(20, int(round(60 * scale)))
    SIDEBAR_X = max(400, int(round(1700 * scale)))
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="play_vs_tier1_gui")
    p.add_argument("--player", type=int, choices=(0, 1), default=0,
                   help="0 = you go first, 1 = Tier-1 goes first")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--scale", type=float, default=1.0,
                   help="UI scale factor (0.5 = half size, 1.0 = original)")
    args = p.parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)

    _patch_pillow_antialias()
    _apply_scale(args.scale)

    game = Game(enable_legal_moves_cache=True)
    ai = RuleBasedPlayer(seed=args.seed if args.seed is not None else 0)

    from wingedsheep.carcassonne.carcassonne_visualiser import CarcassonneVisualiser
    visualiser = CarcassonneVisualiser()

    gui = GameGUI(game=game, ai=ai, visualiser=visualiser, human_player=args.player)
    gui.start()

    visualiser.canvas.master.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
