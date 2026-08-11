"""Shared helpers for the Phase-4 human-anchor scripts.

Reconstruction, rendering, action description, and provenance/signature hashing —
all lazy-importing `carcassonne_ai` so a caller that `import env_preamble` first
gets the production leaf. Nothing here MUTATES a board the caller owns, and
nothing here imports the do-not-touch modules for anything but read/call use.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Path-stable imports: src package + the two non-package script dirs the APIs live in.
for _p in ("src", "scripts/level2", "scripts/measurement_infra"):
    _abs = str(REPO_ROOT / _p)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)


# --------------------------------------------------------------------------- #
# provenance / signature hashing
# --------------------------------------------------------------------------- #
def git_rev() -> str:
    """`<short-sha>` or `<short-sha>-dirty` (agent version stamp). '<no-git>' if unavailable."""
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        dirty = subprocess.call(
            ["git", "-C", str(REPO_ROOT), "diff", "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return f"{sha}-dirty" if dirty else sha
    except Exception:
        return "<no-git>"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def leaf_hash() -> str:
    """Content digest of the LEAF implementation (flat_leaf + virtual_score_v2),
    so a game log records exactly which leaf produced its agent's moves."""
    h = hashlib.sha256()
    for rel in ("src/carcassonne_ai/flat_leaf.py",
                "src/carcassonne_ai/virtual_score_v2.py"):
        p = REPO_ROOT / rel
        if p.exists():
            h.update(rel.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def sha256_of(obj) -> str:
    """Stable digest of any JSON-able object (sorted keys) — used to 'sign' logs."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# --------------------------------------------------------------------------- #
# position reconstruction  (deck_seed + [actions] + ply  ->  game, board)
# --------------------------------------------------------------------------- #
def reconstruct(prov: dict):
    """Rebuild (game, board) from a provenance dict.

    prov = {"deck_seed": int, "ply": int, "replay": "greedy"|"actions",
            "actions": [int...]  (only for replay=="actions")}

    * replay=="actions": lossless root_replay for ANY policy (stored action seq).
    * replay=="greedy":  deterministic RuleBasedPlayer self-play to `ply` — the
      exact reconstruction gen_endgame_positions used to MINT the K2/K3 suite,
      so the action-id space (offset) matches the cached child_values bit-for-bit.
    """
    seed = int(prov["deck_seed"])
    ply = int(prov["ply"])
    mode = prov.get("replay", "greedy")
    if mode == "actions":
        from root_replay import replay_actions
        return replay_actions(seed, list(prov["actions"]), ply)
    if mode == "greedy":
        import gen_endgame_positions as gep
        return gep.replay_to(seed, ply)
    raise ValueError(f"unknown replay mode {mode!r}")


def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand (matches fair_agent.k_remaining)."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def legal_action_ids(game, board) -> list[int]:
    import numpy as np
    return [int(a) for a in np.flatnonzero(game.get_valid_moves(board))]


# --------------------------------------------------------------------------- #
# action description  (action_id -> human-readable string)
# --------------------------------------------------------------------------- #
def describe_action(board, action_id: int) -> str:
    """Decode a flat action id to an engine Action and render it in words.
    Mirrors scripts/play_vs_net.decode(...)+describe(...) exactly."""
    from carcassonne_ai.action_space import decode
    from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
    from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
    from wingedsheep.carcassonne.objects.actions.tile_action import TileAction

    st = board.state
    last = st.last_tile_action.coordinate if st.last_tile_action is not None else None
    act = decode(int(action_id), off=board.offset, phase=st.phase.value,
                 next_tile=st.next_tile, last_tile_coord=last)
    if isinstance(act, TileAction):
        co = act.coordinate
        return f"TILE   at (r={co.row},c={co.column}) rot={act.tile_rotations}"
    if isinstance(act, MeepleAction):
        cs = act.coordinate_with_side
        return (f"MEEPLE {act.meeple_type.name} on {cs.side.name} "
                f"of (r={cs.coordinate.row},c={cs.coordinate.column})")
    if isinstance(act, PassAction):
        return "PASS"
    return str(act)


# --------------------------------------------------------------------------- #
# board renderer  (text diagram)
# --------------------------------------------------------------------------- #
def render_board(state) -> str:
    """ASCII map of placed tiles, cropped to the bounding box + a 1-cell margin.
    '.'=empty, '#'=tile (no meeple), a DIGIT = the owning player's meeple sits on
    that tile. Adapted from scripts/play_vs_net.render_board (kept legend-compatible)."""
    coords = list(getattr(state, "placed_coords", []))
    if not coords:
        return "(empty board)"
    rows = [c.row for c in coords]
    cols = [c.column for c in coords]
    r0, r1 = min(rows) - 1, max(rows) + 1
    c0, c1 = min(cols) - 1, max(cols) + 1
    meeple_cells: dict[tuple[int, int], int] = {}
    for pl in range(state.players):
        for mp in state.placed_meeples[pl]:
            cs = mp.coordinate_with_side.coordinate
            meeple_cells[(cs.row, cs.column)] = pl
    lines = ["     " + "".join(f"{c % 10}" for c in range(c0, c1 + 1))]
    for r in range(r0, r1 + 1):
        cells = []
        for c in range(c0, c1 + 1):
            tile = (state.board[r][c]
                    if 0 <= r < len(state.board) and 0 <= c < len(state.board[0])
                    else None)
            if tile is None:
                cells.append(".")
            elif (r, c) in meeple_cells:
                cells.append(str(meeple_cells[(r, c)]))
            else:
                cells.append("#")
        lines.append(f"{r:>4} {''.join(cells)}")
    lines.append("legend: . empty   # tile   0/1 = player-N meeple on tile")
    return "\n".join(lines)


def render_position(rec: dict, board, max_moves: int = 40) -> str:
    """Full text diagram for a suite record: board + header (turn/scores/K/stratum)
    + the enumerated legal moves + the ground-truth/label answer key (elided)."""
    st = board.state
    hdr = [
        f"# position {rec.get('id','?')}   stratum={rec.get('stratum','?')}"
        f"   k_remaining={rec.get('k_remaining','?')}   exact={rec.get('exact')}",
        f"  to_move=player{st.current_player}   scores(p0,p1)={list(st.scores)}"
        f"   phase={st.phase.value}   in_hand={rec.get('in_hand_tile')}",
    ]
    body = [render_board(st)]
    moves = ["  legal moves:"]
    for i, a in enumerate(rec.get("legal_moves", [])[:max_moves]):
        moves.append(f"    [{i:>3}] a={a:<5} {describe_action(board, a)}")
    if len(rec.get("legal_moves", [])) > max_moves:
        moves.append(f"    ... (+{len(rec['legal_moves']) - max_moves} more)")
    return "\n".join(hdr + body + moves)
