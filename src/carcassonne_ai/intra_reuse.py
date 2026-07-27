"""C3-INTRA — within-turn tree carry (tile decision -> meeple decision).

THE LEVER (docs/LEVER_INDEX.md "within-turn tree carry"; roadmap parking-lot item 6).
``FairHeuristicPriorAgent`` is asked for TWO decisions per turn: first the tile
placement, then the meeple placement. Each one currently runs a FULL PIMC budget
(``k_dets`` fresh determinizations x ``sims`` fresh simulations), and the meeple half
was MEASURED at 52.5% of champion search time (30-decision probe, zero forced skips,
2026-07-27). The tile search already builds the meeple-decision subtree under every
candidate placement — and then throws the whole forest away.

WHY THIS IS FAIR-LEGAL (and across-move reuse is not)
-----------------------------------------------------
NO HIDDEN INFORMATION ARRIVES BETWEEN THE TWO DECISIONS. Verified in the engine, not
assumed: ``StateUpdater._apply_action_to`` applies a ``TileAction`` by
``play_tile`` + ``phase = MEEPLES`` and RETURNS — ``draw_tile`` is called only on the
``original_phase == MEEPLES`` path (and on a TILES-phase pass, which skips the meeple
decision entirely). So the deck the agent cannot see is bit-for-bit the same list
before and after the tile placement, and the posterior over unseen decks is IDENTICAL
at both decisions. A determinization sampled for the tile decision is therefore an
equally-valid sample of the agent's information state at the meeple decision: carrying
it forward leaks nothing.

This is exactly what is NOT true across moves (CL-044). There, a tile is drawn between
the two decisions, so a retained tree is conditioned on a now-counterfactual future —
which is why ``reuse_tree`` is clairvoyant-only and why the fair agent has no reuse
knob. **This module must never be extended to carry state across a draw.** The
continuation check below is what keeps that boundary honest: it re-derives each world's
post-placement position and demands it match the position actually presented, so a
carry can only ever survive a genuine same-turn tile->meeple continuation.

THE FLAG
--------
``CARCASSONNE_INTRA_TURN_REUSE=1`` turns the feature on process-wide. Read ONCE here at
import (like the leaf knobs and ``meeple_equiv``) into ``INTRA_TURN_REUSE``. Default
OFF, and OFF is a provably untouched code path in ``fair_agent`` (golden fixture
``tests/golden/intra_reuse_off.json``).

``FairHeuristicPriorAgent(..., intra_reuse=True/False)`` overrides the global PER AGENT,
which is what a candidate-vs-champion screen needs: both players usually live in ONE
worker process, so a purely process-global flag could not run a carry-ON candidate
against a carry-OFF champion. ``None`` (the default) means "inherit
``INTRA_TURN_REUSE``".

WHAT "THE BUDGET" MEANS WHEN ON
-------------------------------
The meeple decision still runs ``sims`` NEW simulations per determinization, ON TOP OF
the carried subtree's existing visits. So ON does strictly MORE total work per turn at
the same nominal ``sims`` — the strength-at-equal-nominal-budget framing. Any positive
screen MUST be followed by an equal-WALL-CLOCK confirm (the CL-044 ms-ratio house rule);
see ``scripts/classical_search/intra_reuse_screen.sh``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from wingedsheep.carcassonne.objects.game_phase import GamePhase

# --------------------------------------------------------------------------- #
# The flag                                                                     #
# --------------------------------------------------------------------------- #
ENV_VAR = "CARCASSONNE_INTRA_TURN_REUSE"
_TRUE = {"1", "true", "yes", "on"}


def _env_flag() -> bool:
    return os.environ.get(ENV_VAR, "0").strip().lower() in _TRUE


INTRA_TURN_REUSE: bool = _env_flag()


def enabled() -> bool:
    """The process-wide default for new agents."""
    return INTRA_TURN_REUSE


def resolve(flag: bool | None) -> bool:
    """Resolve a per-agent ``intra_reuse`` kwarg: ``None`` means inherit the flag."""
    return INTRA_TURN_REUSE if flag is None else bool(flag)


def set_enabled(on: bool, *, export: bool = True) -> None:
    """Flip the process-wide default at runtime (a CLI flag's entry point).

    ``export`` also writes ``os.environ`` so that multiprocessing children — which
    re-import this module under 'spawn' and would otherwise re-read the *original*
    env — inherit the same setting. Call it BEFORE forking/spawning workers.
    """
    global INTRA_TURN_REUSE
    INTRA_TURN_REUSE = bool(on)
    if export:
        os.environ[ENV_VAR] = "1" if on else "0"


# --------------------------------------------------------------------------- #
# The retained turn + the continuation check                                    #
# --------------------------------------------------------------------------- #
# Discard reasons (kept as constants so the telemetry Counter's keys are greppable and
# the fallback matrix in the tests can name them).
R_NONE = "no_retained_state"          # nothing was carried (normal on a tile decision)
R_NOT_PRIOR = "not_immediately_prior"  # a decision happened in between (or a restore)
R_PHASE = "phase_not_meeples"         # the next decision is not a meeple decision
R_PLAYER = "player_changed"           # the opponent is to move -> different turn
R_KEY = "continuation_key_mismatch"   # the presented position is not "our A applied"
R_REROOT = "reroot_rejected"          # the retained node failed the search-side guard
R_FORCED = "forced_move"              # 1 legal action -> no search runs at all
R_LATCHED = "exact_endgame_latch"     # the solver owns this decision
R_NO_SIGNAL = "no_pooled_signal"      # pathological: nothing was visited


@dataclass
class RetainedTurn:
    """The tile decision's forest, held for exactly one following decision.

    ``trees``/``boards`` are index-aligned per determinization: ``trees[i]`` is the
    ``NeuralMCTS`` that searched ``boards[i]``, the deepcopy of the tile-decision board
    whose UNSEEN deck was reshuffled for world ``i``. ``action`` is the tile action the
    pooled-Q rule actually returned, so the child to re-root at is unambiguous.
    """

    move_idx: int          # the agent's move index OF THE TILE DECISION
    action: int            # the tile action the agent returned
    player: int            # the player to move at the tile decision
    root_key: str          # the tile-decision board's transposition key
    trees: list = field(default_factory=list)   # list[NeuralMCTS], one per world
    boards: list = field(default_factory=list)  # list[Board], one per world (PRE-action)


def match(game, retained: RetainedTurn | None, board, move_idx: int,
          cur_key: str) -> tuple[list | None, str]:
    """Is ``board`` the meeple half of the turn ``retained`` came from?

    Returns ``(post_action_boards, "hit")`` on a match — the retained determinized
    worlds with the tile action APPLIED, index-aligned with ``retained.trees`` and
    ready to be searched — or ``(None, reason)`` otherwise.

    THE CONTINUATION KEY is deliberately *derived*, not predicted. A cheap gate first
    (same agent's immediately-preceding decision, meeple phase, same player to move),
    then the load-bearing check: apply the retained action to EVERY retained world and
    require the resulting position's transposition key to equal the key of the position
    we were actually handed. Because deck ORDER is not in the key, a world that is a
    legitimate continuation lands exactly on ``cur_key``; anything else — the opponent
    moved, a restore/replay jumped the agent elsewhere, a new game, a forced tile-phase
    pass that skipped the meeple step (that path calls ``draw_tile``, so the world's
    ``next_tile`` would come from ITS deck and diverge) — cannot.

    Note this never touches the true deck: the placement is applied to OUR OWN sampled
    worlds, and the only thing read off the real board is its key. There is no path here
    by which hidden information could enter the decision.
    """
    if retained is None:
        return None, R_NONE
    if retained.move_idx != move_idx - 1:
        return None, R_NOT_PRIOR
    st = board.state
    if st.phase != GamePhase.MEEPLES:
        return None, R_PHASE
    if st.current_player != retained.player:
        return None, R_PLAYER
    out = []
    for b in retained.boards:
        nb, _ = game.get_next_state(b, retained.action)
        if game.string_representation(nb) != cur_key:
            return None, R_KEY
        out.append(nb)
    return out, "hit"
