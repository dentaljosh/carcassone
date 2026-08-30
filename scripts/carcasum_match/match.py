#!/usr/bin/env python3
"""F9 / D3 — champion vs Carcasum: the match driver.

THE POINT. Same reason `scripts/jcz_match/match.py` exists: every strength number
this project owns is self-anchored (CLAUDE.md blocker #1). Carcasum
(``TripleWhy/Carcasum``, AGPL-3.0) is a SECOND, wholly independent open-source
Carcassonne implementation — independent lineage from JCloisterZone, independent
tile data, independent AI (an MCTS with several playout/utility variants). This
driver plays our champion against Carcasum's own `MCTSPlayer` and diffs the two
boards at every ply, so a win rate can never quietly be a rules artefact.

## The C++ side does not exist yet — this is deliberate

The protocol (``scripts/carcasum_match/PROTOCOL.md``) was frozen before either
side was built, specifically so neither could define the interface by accident.
This file was developed and tested entirely against ``stub_driver.py`` — a TEST
DOUBLE that speaks the same protocol, backed by OUR OWN engine playing both
seats. The stub proves the protocol plumbing (coordinate/rotation/meeple maps,
message framing, timeouts, void classification) is self-consistent; it proves
**nothing** about Carcasum itself. Point ``--binary`` at the real
``carcasum_driver`` the moment it exists — nothing else in this file changes.

## The configuration is not negotiable: ``fixed_v1`` + ``CARCASSONNE_FIX_R9=1``

Same reasoning as the JCZ driver, and the SAME underlying divergence: Carcasum's
``basic.xml`` declares ``RCr`` (our ``city_top_straight_road``) as
``<farm city="N">EL WR</farm>`` — byte-identical text to JCZ 5.x's equivalent
declaration (see ``tests/data/carcasum/PROVENANCE.md``), i.e. the SAME R9 farm
data bug, corroborated against a second, decade-older, unrelated codebase. R9-off
would reintroduce genuine farm-partition divergences and void the games, so the
env var is exported before any ``carcassonne_ai`` import and stamped in every
manifest (``rules_manifest.r9_env_ok``) — refuse to run otherwise. Under
``fixed_v1``, the retail start tile is already placed on the board, so the forced
deck is ``[next_tile] + deck`` = 71 entries (PROTOCOL.md §3.1), matching Carcasum's
own ``TileFactory::createPack`` / ``takeFirst()`` construction exactly.

## Who is the game of record

**Our engine is.** Carcasum's ``Game`` mirrors it and happens to also own the
turn loop (``Game::step()``), so there is no message-chain/Confirm plumbing to
maintain (PROTOCOL.md §0) — but the inversion discipline is identical to the JCZ
driver: the champion's chosen action is forward-mapped onto Carcasum's
coordinates; Carcasum's own ``MCTSPlayer`` move is INVERTED onto our action space
by enumerating OUR legal actions and forward-mapping each one until one matches.
**There is no inverse map anywhere in this file.** A placement outside our 25x25
action window is ``WALL_LEGALITY`` (counted, never ignored); an unmappable
opponent move is ``VOID_UNMAPPABLE`` with the offered move and our full legal
image set recorded verbatim.

## Score diffing: what our side can and cannot provide (READ BEFORE TRUSTING A NUMBER)

Our engine keeps only a flat ``state.scores[player]`` running total — there is no
per-terrain (field/city/road/cloister) breakdown anywhere in ``engine/``, and
this driver does NOT instrument the engine to add one (``engine/`` is shared,
off-limits for a protocol-driver task). So the score diff here is layered:

1. **Every ply**: our running total vs Carcasum's ``ev_move.scores`` (seat-for-
   seat — no seat-offset inference needed, unlike the JCZ driver, because we
   DICTATE ``external_seat`` to Carcasum in ``new_game`` rather than discovering
   it). A mismatch that reconciles by the terminal state is ``SCORE_TIMING``;
   one that does not is ``SCORE_FINAL``.
2. **Farm points, exact, at game end**: fields never score before the game ends
   in EITHER engine (official rules), so Carcasum's final ``score_detail["field"]``
   IS the whole-game farm total, and we can price the same number independently
   and exactly: ``carcassonne_ai.aux_targets.extract_terminal_ownership`` is a
   *recording replica* of the engine's own ``PointsCollector.count_final_scores``
   walk (city/road/farm/monastery, by construction sums to the engine's own
   additions). It needs a terminal state with meeples STILL PLACED, which the
   engine's own terminal sweep has already consumed by the time ``game_over``
   arrives — so we reconstruct it exactly the way ``selfplay.py`` builds
   ownership-aux-target labels (``src/carcassonne_ai/selfplay.py`` ~L570-592):
   deepcopy the board from just BEFORE the terminating action, stub
   ``PointsCollector.count_final_scores`` to a no-op for that one
   ``apply_action_inplace`` call (so the terminating tile/meeple placement lands
   but the endgame sweep does not remove the meeples we need to attribute), then
   run the extractor. See ``compute_endgame_ownership``. Compared directly
   against ``score_detail["field"]`` -> ``FARM_SCORE_FINAL`` if it disagrees.
3. **City/road/cloister, endgame-only**: the SAME extraction also gives city/
   road/monastery ownership for every feature still OPEN at game end — but only
   for those, because a feature that finished mid-game was already scored and
   its meeples removed (same reasoning as (2), just not exclusive to farms).
   Compared against the DELTA of Carcasum's ``score_detail`` between the
   TERMINATING ``ev_move`` (the one that empties the tile bag) and the ply
   BEFORE it -> ``ENDGAME_TERRAIN_MISMATCH`` per terrain. ⚠️ The delta is
   deliberately NOT ``game_over.score_detail`` minus the terminating
   ``ev_move``'s — those two are the SAME ply's numbers and differ by
   construction only if the driver's endgame sweep runs as a SEPARATE step
   after ``game_over``. Our own engine's ``count_final_scores`` runs
   SYNCHRONOUSLY inside the SAME state transition that empties the deck (so
   the terminating ``ev_move`` already carries the fully-swept totals, and
   that first-drafted delta was always zero — caught by
   `stub_driver.py` DISagreeing with itself on its own clean transcript,
   2026-08-23), and PROTOCOL.md's single `Game::step()` per ply makes the same
   synchronous-sweep shape plausible for Carcasum too. **This synchronicity is
   still an ASSUMPTION about Carcasum specifically, not a protocol guarantee**
   — if the real driver's endgame sweep is NOT synchronous with the
   terminating ply, this ONE check (never the farm check at (2), never the
   per-ply total check at (1)) will read noisy near game-end. Reported, never
   fatal — a REAL class on the record, excluded from win rate, not a crash.
4. **What we cannot check**: mid-game per-terrain attribution (was THIS specific
   ply's score bump a city or a road). Nothing on our side tracks it, and
   inventing an instrumentation layer for it was explicitly ruled out of scope
   for this driver (see the code review this file's docstring survived).

## Protocol notes that cost time if you rediscover them

* Carcasum's ``ev_move`` bundles a FULL turn (tile placement + optional meeple)
  into one event; our engine is two-phase (TILES then MEEPLES). So one Carcasum
  ply can correspond to ONE of our actions (tile only, no meeple offered) or TWO
  (tile then meeple/pass). ``req_meeple`` is not sent when Carcasum's own
  ``possibleMeeples.size() <= 1`` (i.e. nothing to choose from besides "no
  meeple") — in that case we owe our own meeple-phase pass, applied the moment
  we see ``ev_move`` for our own seat still sitting in the MEEPLES phase
  (mirrors the JCZ driver's ``jcz_meeple_pass_implicit`` case).
* Inverting an opponent meeple placement needs the board-absolute half-edge /
  edge labels for that ``(tile_type, node_index)`` at the placed ``orientation``.
  ``ev_move`` gives only the bare integer; the labels come from ``--dump-tiles``
  (tile-local) rotated via ``rotate_labels`` (PROTOCOL.md §2/§4) — cached once
  per worker, never re-fetched per game.
* ``req_meeple``'s own ``nodes`` field is DIFFERENT from the dump-tiles cache:
  the driver has ALREADY rotated those labels to board-absolute (PROTOCOL.md
  §3.2b), so replying to a request needs no rotation at all — only the opponent-
  inversion path touches ``rotate_labels``.
* An orphaned Carcasum MCTS process is a silent full-core leak across a
  multi-hundred-game match (PROTOCOL.md §3.3) — ``CarcasumDriver`` guarantees
  ``kill()`` in a ``finally``, both on the happy path and on a hard read timeout.

## Usage

    # the audit gate (rules coverage, NOT a strength run: cheap champion, cheap opp)
    .venv/bin/python scripts/carcasum_match/match.py --decks 2 --champ-seat both \\
        --audit-mode greedy --opp-budget-ms 200 --binary scripts/carcasum_match/stub_driver.py \\
        --out /tmp/carcasum_audit.jsonl --repeats 1

    # a real match, detached, once carcasum_driver exists
    setsid nohup nice -n 19 .venv/bin/python scripts/carcasum_match/match.py \\
        --decks 50 --champ-seat both --workers 8 \\
        --out measurement/carcasum_match/games.jsonl --resume >> driver.log 2>&1 & disown
"""
from __future__ import annotations

# ⚠️ STDLIB ONLY at module level — same reason as jcz_match/match.py:
# `carcassonne_ai` must not be imported before `CARCASSONNE_FIX_R9` is exported
# (base_deck latches it at import into a Rust OnceLock), and spawn workers
# re-import this module fresh.
import argparse
import hashlib
import json
import os
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRIPTS = REPO / "scripts"
JCZ_ORACLE = SCRIPTS / "jcz_oracle"
HUMAN_ANCHOR = SCRIPTS / "human_anchor"

SCHEMA = "carcassonne-carcasum-match/v1"

#: NOT a knob — the only rules configuration Carcasum's field data agrees with
#: (see the module docstring's R9 note).
PROFILE = "fixed_v1"

#: Agent-seed base for the CHAMPION (Python side). Mirrors jcz_match's discipline:
#: `replicate` is deliberately excluded (a replicate is a pure re-run of the
#: identical cell, which is what makes the determinism report mean anything).
SEED_BASE = 9_300_000
#: Separate base for the seed we hand Carcasum's own RNG (`new_game.seed`) —
#: distinct arithmetic so the two seed streams can never collide.
OPP_SEED_BASE = 9_400_000

START_TILE_DESC = "city_top_straight_road"
#: The board geometry, VERIFIED against the real binary on 2026-08-23 (handshake
#: read back `board_size: 145`, `start_xy: [72, 72]`, `start_tile_type: 2` = RCr).
#: `Board::Board(Game *, uint s)` initialises `size(s * 2 + 1)` and `Game::newGame`
#: passes `tiles.size()` (= 72), hence 145 and not 72. An earlier revision of both
#: PROTOCOL.md and this file said 72/36; that was wrong and is corrected here.
#:
#: ⚠️ These are ASSERTION TARGETS, never inputs to a coordinate computation. The
#: live origin always comes from the handshake (`ready.start_xy`) and is threaded
#: through as `offset_xy`. There is deliberately NO fallback: a `ready` line
#: without `start_xy` is a hard void, not a guess. Guessing an origin is precisely
#: how a coordinate bug disguises itself as a rules finding — it yields a
#: legal-LOOKING move at the wrong square, ~100 % VOID_UNMAPPABLE, and an audit
#: readout that says "the engines disagree" when they do not.
CARCASUM_BOARD_SIZE = 145
CARCASUM_OFFSET = 72  # == CARCASUM_BOARD_SIZE // 2; asserted, never assumed
CARCASUM_DECK_LEN = 71  # [next_tile] + deck under fixed_v1 (PROTOCOL.md §3.1)

VOID_UNMAPPABLE = "VOID_UNMAPPABLE"
VOID_DIVERGENT = "VOID_DIVERGENT"
VOID_ERROR = "VOID_ERROR"

#: Divergence taxonomy. Class NAMES are reused verbatim, same meaning, wherever
#: `jcz_oracle/replay_diff.py` already names the concept (HARNESS_ERROR,
#: WALL_LEGALITY, SCORE_FINAL, SCORE_TIMING, UNPLACEABLE_REDRAW, SEAT_DESYNC,
#: MEEPLE_LEGALITY, MEEPLE_SLOT_UNMAPPED, LEGALITY_OURS_EXTRA) — this driver
#: never redefines what those strings mean. New classes exist only for
#: situations the JCZ oracle has no analogue for (Carcasum's coarser protocol
#: has no live feature-partition channel, and the score-detail layering above
#: is new).
REAL = frozenset({
    "SCORE_FINAL",               # terminal totals disagree
    "FARM_SCORE_FINAL",          # our exact farm total vs score_detail["field"]
    # ⚠️ ENDGAME_TERRAIN_MISMATCH is DELIBERATELY *NOT* REAL — see the constant
    # below and `_ENDGAME_DELTA_UNSOUND` for the measurement that demoted it.
    "MEEPLE_LEGALITY",           # canonicalised meeple option sets differ
    "MEEPLE_SLOT_UNMAPPED",      # our legal slot resolves to no Carcasum feature
    "LEGALITY_OURS_EXTRA",       # we allow a tile placement Carcasum does not offer
    "HARNESS_ERROR",
    "DRIVER_REJECT",             # the Carcasum analogue of JCZ_REJECT
    "SEAT_DESYNC",
    "COORD_FRAME_MISMATCH",      # the `ready` handshake's own start_xy/board_size are mutually
                                  # inconsistent with PROTOCOL.md's stated offset=board_size/2 relation
                                  # — caught BEFORE ply 0 so a coordinate bug can never masquerade as
                                  # a wall of per-ply rules divergences.
})
CLASSIFIED = frozenset({
    "UNPLACEABLE_REDRAW",  # A3 retail redraw — expected under fixed_v1 on both sides
    "SCORE_TIMING",        # a running mismatch that reconciles by the terminal
    "WALL_LEGALITY",       # Carcasum offers a placement our bounded window cannot express
    "ENDGAME_TERRAIN_MISMATCH",   # telemetry only — NOT a rules finding; see below
})

#: WHY `ENDGAME_TERRAIN_MISMATCH` IS TELEMETRY AND NOT A REAL DIVERGENCE.
#:
#: The check wants OUR endgame-only per-terrain vector (from
#: `aux_targets.extract_terminal_ownership`) against THEIRS. We have no absolute
#: per-terrain figure of our own — our engine tracks a flat `scores[player]` — so
#: theirs has to be turned into an endgame-only quantity by differencing
#: `score_detail` across the end of the game. **There is no ply at which that
#: difference is the endgame-only quantity**, which was measured, not assumed
#: (2026-08-23, real driver, deck 5100013):
#:
#:   * against the TERMINATING ply's `ev_move`, the delta is EXACTLY ZERO on every
#:     terrain — `game_over.score_detail` and the last `ev_move.score_detail` are
#:     byte-identical, because Carcasum's `endGame()` runs INSIDE the terminating
#:     `Game::step()`, so the last `ev_move` already contains the endgame sweep;
#:   * against the ply BEFORE it, the delta additionally contains that ply's
#:     MID-GAME closures, so it over-reports. That is the direction actually
#:     observed in the 50-game audit: theirs >= ours on 8/50 games, never the
#:     reverse.
#:
#: So the class fires on a bookkeeping-alignment artefact, not on a rules
#: disagreement — and the audit corroborates that reading, since those same 8
#: games had EXACT final-score agreement and EXACT farm agreement. Leaving it in
#: REAL would void ~16 % of games for a non-rules reason and corrupt the rated
#: match's void accounting.
#:
#: It stays as reported telemetry because the direction and size are still worth
#: eyeballing. To make it sound, the DRIVER must publish a `score_detail` snapshot
#: taken after the terminating ply's mid-game closures but BEFORE `endGame()` —
#: i.e. a `pre_endgame` field on `game_over`. That is a small change at the
#: `simEndGame()` boundary and is the way to recover a full per-terrain endgame
#: check; it is NOT needed for the rated match, because `FARM_SCORE_FINAL` below
#: already covers the terrain that matters.
#:
#: `FARM_SCORE_FINAL` IS sound and stays REAL: fields never score mid-game in
#: either engine, so their ABSOLUTE `score_detail["field"]` at `game_over` IS the
#: endgame-only field figure, with no differencing and nothing to contaminate it.
#: The 50-game audit agreed 50/50 on it, with farms exercised in 50/50 games.
_ENDGAME_DELTA_UNSOUND = True

_COMPASS_CW = {"N": "E", "E": "S", "S": "W", "W": "N"}
_CARCASUM_TERRAIN_TO_FEATURE = {"field": "Field", "road": "Road", "city": "City", "cloister": "Monastery"}
#: `aux_targets.FeatureOwnership.terrain` vocabulary ("city"/"road"/"farm"/
#: "monastery") -> Carcasum's `score_detail` key vocabulary.
_OWNERSHIP_TERRAIN_TO_CARCASUM = {"city": "city", "road": "road", "farm": "field", "monastery": "cloister"}


def agent_seed(deck_seed: int, champ_seat: int, replicate: int = 0) -> int:
    """Deterministic CHAMPION seed for a cell. `replicate` excluded on purpose —
    see jcz_match.match.agent_seed's docstring for why (the determinism gate)."""
    del replicate
    return SEED_BASE + (int(deck_seed) % 1_000_000) * 8 + int(champ_seat) * 4


def opp_seed(deck_seed: int, champ_seat: int, replicate: int = 0) -> int:
    """Deterministic seed for CARCASUM's own RNG (`new_game.seed`). Same
    replicate-exclusion discipline as `agent_seed`, and a disjoint arithmetic
    base so the two seed streams can never collide."""
    del replicate
    return OPP_SEED_BASE + (int(deck_seed) % 1_000_000) * 8 + int(champ_seat) * 4


# --------------------------------------------------------------------------- #
# lazy imports                                                                 #
# --------------------------------------------------------------------------- #
def export_profile_env(profile: str = PROFILE) -> dict:
    """Export the import-latched env this profile owes (R9). House pattern,
    REUSED from `scripts/e4_deck_baseline.py` rather than re-implemented."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from e4_deck_baseline import export_profile_env as _export
    return _export(profile)


def _tile_map_mod():
    """`scripts/jcz_oracle/tile_map.py`, imported not copied (task constraint:
    import `to_jcz_position` / `jcz_rotation_quarters` / `jcz_location_for` /
    `parse_location`, never re-derive them)."""
    if str(JCZ_ORACLE) not in sys.path:
        sys.path.insert(0, str(JCZ_ORACLE))
    import tile_map as TM
    return TM


# --------------------------------------------------------------------------- #
# the Carcasum tile mapping (tests/data/carcasum/TILE_MAPPING.tsv)              #
# --------------------------------------------------------------------------- #
TILE_MAPPING_TSV = REPO / "tests" / "data" / "carcasum" / "TILE_MAPPING.tsv"


def load_carcasum_tile_mapping(path: Path | str | None = None) -> dict[str, tuple[str, int, int]]:
    """our tile `description` -> `(carcasum_id, carcasum_tile_type, rot_cw90)`.

    Many-to-one on `carcasum_id` (the garden-variant collapse — PROVENANCE.md),
    but a total FUNCTION from our 32 kinds, which is all this driver needs: it
    only ever looks up FROM our tile description, never the reverse.
    """
    import csv

    p = Path(path) if path is not None else TILE_MAPPING_TSV
    out: dict[str, tuple[str, int, int]] = {}
    with p.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if not row.get("our_kind"):
                continue
            out[row["our_kind"]] = (
                row["carcasum_id"], int(row["carcasum_tile_type"]), int(row["rot_cw90"]),
            )
    if len(out) != 32:
        raise ValueError(f"{p}: expected 32 tile kinds, got {len(out)}")
    return out


# --------------------------------------------------------------------------- #
# rotate_labels — the pure helper PROTOCOL.md §2/§4 names                      #
# --------------------------------------------------------------------------- #
def rotate_labels(labels, quarters: int) -> frozenset[str]:
    """CW quarter-turn rotation of a Carcasum `dump_tiles` tile-local label set.

    The compass letter rotates N->E->S->W->N; an L/R half-edge suffix is
    preserved verbatim; `"CLOISTER"` is rotation-invariant. (PROTOCOL.md §2: "a
    tile we placed at `tile.turns = t`" rotates board-absolute the same way our
    own farmer/edge rotation does — this is Carcasum's OWN label vocabulary
    rotated by Carcasum's OWN reported `orientation`, never our geometry.)
    """
    q = int(quarters) % 4
    out = []
    for lab in labels:
        if lab == "CLOISTER":
            out.append(lab)
            continue
        compass, suffix = lab[0], lab[1:]
        for _ in range(q):
            compass = _COMPASS_CW[compass]
        out.append(compass + suffix)
    return frozenset(out)


def carcasum_node_key(terrain: str, labels) -> tuple[str, frozenset[str]]:
    """A Carcasum node's `(terrain, labels)` -> the `(feature, tokens)` key
    `tile_map.jcz_location_for` returns for one of OUR meeple slots — the
    shared comparison key both inversion directions match against. `labels`
    must already be BOARD-ABSOLUTE (either supplied that way by `req_meeple`,
    or rotated via `rotate_labels` from the `dump_tiles` tile-local cache)."""
    feature = _CARCASUM_TERRAIN_TO_FEATURE[terrain]
    if terrain == "cloister":
        # Carcasum's "CLOISTER" marker isn't a geometry token; jcz_location_for's
        # own monastery convention is the single interior token "I".
        return (feature, frozenset({"I"}))
    return (feature, frozenset(labels))


# --------------------------------------------------------------------------- #
# the inversion: Carcasum move -> OUR action int, THROUGH the forward map        #
# --------------------------------------------------------------------------- #
def our_tile_carcasum_options(game, board, tile_map, origin, offset_xy=None, periods=None):
    """Our legal tile placements, forward-mapped to Carcasum's `(x, y, o)`.

    Returns `(carcasum_tile_type | None, {(x, y, o)})`. Used both to reply-check
    and to diff against Carcasum's own `req_tile.placements` (WALL_LEGALITY).

    ⚠️ `offset_xy` MUST come from the driver's own `ready` handshake
    (`start_xy`), never a hardcoded constant — PROTOCOL.md states
    `offset = board_size/2`, but the offset is a DERIVED property of whatever
    the driver actually built, not a number this file gets to assume. See
    `play_one_match`'s handshake handling and `CARCASUM_OFFSET`'s docstring.
    """
    from carcassonne_ai import action_space as A

    TM = _tile_map_mod()
    ox, oy = offset_xy if offset_xy is not None else (CARCASUM_OFFSET, CARCASUM_OFFSET)
    state = board.state
    tile = state.next_tile
    if tile is None:
        return None, set()
    _c_id, c_type, rot_cw90 = tile_map[tile.description]
    period = int((periods or {}).get(int(c_type), 4)) or 4
    off, W = board.offset, game.window_size
    valid = game.get_valid_moves(board)
    opts: set[tuple[int, int, int]] = set()
    for idx in range(A.tile_action_count(W)):
        if not valid[idx]:
            continue
        cell, rot = divmod(idx, A.N_ROTATIONS)
        wr, wc = divmod(cell, W)
        coord = off.to_engine(wr, wc)
        jp = TM.to_jcz_position(coord, *origin)
        # `% period`: Carcasum enumerates only physically DISTINCT placements, so a
        # symmetric tile's four rotations collapse onto `period` of theirs. Without
        # this the set simply never intersects theirs for chapel/full-city/
        # crossroads/FCFC-shaped tiles. See `tile_rotation_period`.
        opts.add((jp[0] + ox, jp[1] + oy,
                  TM.jcz_rotation_quarters(rot, rot_cw90) % period))
    return c_type, opts


def invert_tile_move(game, board, tile_map, *, x, y, o, tile_type, origin, offset_xy=None,
                     periods=None) -> tuple[int | None, dict]:
    """A Carcasum `(x, y, o, tile_type)` move -> our action int (or `None`).

    Enumerates OUR legal tile actions and forward-maps each through
    `to_jcz_position` + the HANDSHAKE-DERIVED offset (never a hardcoded one —
    see `our_tile_carcasum_options`) and `jcz_rotation_quarters(rot, rot_cw90)`
    — never inverts Carcasum's coordinate or rotation by arithmetic.
    """
    from carcassonne_ai import action_space as A

    TM = _tile_map_mod()
    ox, oy = offset_xy if offset_xy is not None else (CARCASUM_OFFSET, CARCASUM_OFFSET)
    st = board.state
    tile = st.next_tile
    offered = {"carcasum_tile_type": None if tile_type is None else int(tile_type),
               "x": int(x), "y": int(y), "o": int(o),
               "our_tile": tile.description if tile is not None else None}
    if tile is None:
        return None, offered
    _c_id, c_type, rot_cw90 = tile_map[tile.description]
    offered["our_tile_as_carcasum_type"] = c_type
    if tile_type is not None and int(tile_type) != int(c_type):
        return None, offered  # Carcasum placed a tile we do not hold -> deck desync
    period = int((periods or {}).get(int(c_type), 4)) or 4
    offered["rotation_period"] = period
    want = (int(x), int(y), int(o) % period)

    valid = game.get_valid_moves(board)
    off, W = board.offset, game.window_size
    ours: list[list[int]] = []
    matches: list[int] = []
    for idx in range(A.tile_action_count(W)):
        if not valid[idx]:
            continue
        cell, rot = divmod(idx, A.N_ROTATIONS)
        wr, wc = divmod(cell, W)
        coord = off.to_engine(wr, wc)
        jp = TM.to_jcz_position(coord, *origin)
        img = (jp[0] + ox, jp[1] + oy,
               TM.jcz_rotation_quarters(rot, rot_cw90) % period)
        ours.append([img[0], img[1], img[2]])
        if img == want:
            matches.append(idx)
    # ⚠️ One-to-many by construction on a SYMMETRIC tile (period < 4): our action
    # space carries all four rotations, Carcasum only the physically distinct ones,
    # so several of our actions image onto the same offered placement. They encode
    # the SAME move -- identical board, identical score -- so taking the first in
    # canonical action order is exact, not a heuristic. Multiplicity is recorded for
    # the same reason invert_meeple_move records its own: so a reader can tell an
    # encoding difference from a rules one.
    offered["n_matching_actions"] = len(matches)
    if matches:
        return matches[0], offered
    offered["our_legal_images"] = sorted(ours)
    return None, offered


def forward_tile_action(game, board, tile_map, action_idx: int, origin, offset_xy=None,
                        periods=None) -> dict:
    """Our chosen tile action -> the `{"t":"tile",...}` reply to `req_tile`."""
    TM = _tile_map_mod()
    ox, oy = offset_xy if offset_xy is not None else (CARCASUM_OFFSET, CARCASUM_OFFSET)
    st = board.state
    decoded = game._decode_for(st, board.offset, action_idx)
    _c_id, _c_type, rot_cw90 = tile_map[st.next_tile.description]
    jp = TM.to_jcz_position(decoded.coordinate, *origin)
    x, y = jp[0] + ox, jp[1] + oy
    period = int((periods or {}).get(int(_c_type), 4)) or 4
    # `% period`: reply in Carcasum's own encoding, which lists a symmetric tile's
    # rotations only once (see `tile_rotation_period`). Sending an unreduced
    # orientation gets "tile move not among the offered placements".
    o = TM.jcz_rotation_quarters(decoded.tile_rotations, rot_cw90) % period
    return {"t": "tile", "x": int(x), "y": int(y), "o": int(o)}


def invert_meeple_move(game, board, node_labels_by_type, *, tile_type, o, node_index) -> tuple[int | None, dict]:
    """A Carcasum opponent meeple `(tile_type, o, node_index)` -> our action int.

    `node_labels_by_type` is the `--dump-tiles` cache (tile-local labels);
    rotated via `rotate_labels` to board-absolute, then matched against OUR
    legal meeple slots via `jcz_location_for` — same enumerate-and-forward-map
    discipline, never an inverse map. Carries the SAME multiplicity caveat the
    JCZ driver's `invert_meeple_message` documents (our slots are finer than
    Carcasum's): first match in canonical slot order, `n_matching_slots` kept.
    """
    from carcassonne_ai import action_space as A

    TM = _tile_map_mod()
    st = board.state
    coord = st.last_tile_action.coordinate if st.last_tile_action is not None else None
    offered = {"carcasum_tile_type": None if tile_type is None else int(tile_type),
               "o": None if o is None else int(o), "carcasum_node": node_index}
    if coord is None or node_index is None:
        return None, offered
    tile = st.board[coord.row][coord.column]
    offered["our_last_tile"] = tile.description if tile is not None else None
    nodes = node_labels_by_type.get(int(tile_type)) if tile_type is not None else None
    if not nodes:
        offered["reason"] = "tile_type missing from the dump_tiles cache"
        return None, offered
    node = next((n for n in nodes if int(n["i"]) == int(node_index)), None)
    if node is None:
        offered["reason"] = "node index missing from the dump_tiles cache"
        return None, offered
    want = carcasum_node_key(node["terrain"], rotate_labels(node["labels"], int(o)))
    offered["wanted"] = [want[0], sorted(want[1])]

    valid = game.get_valid_moves(board)
    W = game.window_size
    matches: list[int] = []
    ours: list[list] = []
    for base, sides in ((A.meeple_normal_base(W), A.NORMAL_SIDES),
                        (A.meeple_farmer_base(W), A.FARMER_SIDES)):
        for i, side in enumerate(sides):
            idx = base + i
            if not valid[idx]:
                continue
            got = TM.jcz_location_for(tile, side)
            ours.append([str(side), None if got is None else [got[0], sorted(got[1])]])
            if got == want:
                matches.append(idx)
    offered["our_legal_slots"] = ours
    offered["n_matching_slots"] = len(matches)
    if not matches:
        return None, offered
    return matches[0], offered


def forward_meeple_action(game, board, action_idx: int, nodes) -> tuple[int | None, dict]:
    """Our chosen meeple action -> a Carcasum node index (or `None` = pass),
    matched against `req_meeple`'s OWN board-absolute `nodes` list — no
    rotation needed here (the driver already rotated them, PROTOCOL.md §3.2b)."""
    from wingedsheep.carcassonne.objects.actions.pass_action import PassAction

    TM = _tile_map_mod()
    st = board.state
    decoded = game._decode_for(st, board.offset, action_idx)
    if isinstance(decoded, PassAction):
        return None, {"our_choice": "pass"}
    cws = decoded.coordinate_with_side
    tile = st.board[cws.coordinate.row][cws.coordinate.column]
    want = TM.jcz_location_for(tile, cws.side)
    offered = {"our_choice": str(cws.side)}
    if want is None:
        offered["reason"] = "our slot has no jcz_location_for mapping"
        return None, offered
    offered["wanted"] = [want[0], sorted(want[1])]
    matches = [n["i"] for n in nodes if carcasum_node_key(n["terrain"], n["labels"]) == want]
    offered["n_matching_nodes"] = len(matches)
    if not matches:
        return None, offered
    return int(matches[0]), offered


def invert_pass_meeple(game, board) -> tuple[int | None, dict]:
    """The meeple-phase pass action, when Carcasum owes us one implicitly (no
    `req_meeple` was sent because it had nothing real to offer)."""
    from carcassonne_ai import action_space as A

    idx = A.meeple_pass_index(game.window_size)
    if game.get_valid_moves(board)[idx]:
        return idx, {}
    return None, {"reason": "meeple-phase pass is not legal for us"}


# --------------------------------------------------------------------------- #
# legal-set diffs (req_tile / req_meeple time — OUR own decisions only)          #
# --------------------------------------------------------------------------- #
def diff_tile_legality(div, ply: int, game, board, tile_map, origin, placements, offset_xy=None,
                       periods=None) -> None:
    _c_type, ours = our_tile_carcasum_options(game, board, tile_map, origin, offset_xy, periods)
    theirs = {(int(x), int(y), int(o)) for x, y, o in (placements or [])}
    if ours == theirs:
        return
    extra, missing = ours - theirs, theirs - ours
    if extra:
        div.add("LEGALITY_OURS_EXTRA", ply, {"extra": sorted(extra)[:8], "n": len(extra)})
    if missing:
        div.add("WALL_LEGALITY", ply, {"carcasum_only": sorted(missing)[:8], "n": len(missing)})


def diff_meeple_legality(div, ply: int, game, board, nodes) -> None:
    from carcassonne_ai import action_space as A

    TM = _tile_map_mod()
    st = board.state
    coord = st.last_tile_action.coordinate if st.last_tile_action is not None else None
    if coord is None:
        return
    tile = st.board[coord.row][coord.column]
    valid = game.get_valid_moves(board)
    W = game.window_size
    ours: set[tuple[str, frozenset]] = set()
    unmapped: list[str] = []
    for base, sides in ((A.meeple_normal_base(W), A.NORMAL_SIDES),
                        (A.meeple_farmer_base(W), A.FARMER_SIDES)):
        for i, side in enumerate(sides):
            if not valid[base + i]:
                continue
            got = TM.jcz_location_for(tile, side)
            if got is None:
                unmapped.append(str(side))
            else:
                ours.add(got)
    theirs = {carcasum_node_key(n["terrain"], n["labels"]) for n in (nodes or [])}
    if unmapped:
        div.add("MEEPLE_SLOT_UNMAPPED", ply, {"legal_slots_with_no_carcasum_feature": unmapped})
    if ours != theirs:
        div.add("MEEPLE_LEGALITY", ply, {
            "ours_only": sorted((f, sorted(t)) for f, t in ours - theirs),
            "carcasum_only": sorted((f, sorted(t)) for f, t in theirs - ours)})


def diff_running_scores(div, ply: int, state, carcasum_scores) -> None:
    if carcasum_scores is None:
        return
    ours = [int(x) for x in state.scores]
    theirs = [int(x) for x in carcasum_scores]
    if ours != theirs:
        div.add("SCORE_RUNNING", ply, {"ours": ours, "carcasum": theirs})


# --------------------------------------------------------------------------- #
# endgame per-terrain audit (aux_targets.extract_terminal_ownership)             #
# --------------------------------------------------------------------------- #
def compute_endgame_ownership(game, prev_board, last_action_idx: int):
    """Reconstruct the meeples-still-placed terminal state and return
    `aux_targets.extract_terminal_ownership` records — the SAME technique
    `selfplay.py` uses for ownership-aux-target labels (deepcopy `prev_board`,
    stub `PointsCollector.count_final_scores` to a no-op for exactly one
    `apply_action_inplace`, restore it in `finally`). See the module docstring's
    score-diffing section for why this is the only sound way to get city/road/
    farm/cloister ATTRIBUTION rather than a bare running total.
    """
    import copy

    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    from carcassonne_ai.aux_targets import extract_terminal_ownership

    term_board = copy.deepcopy(prev_board)
    _orig = PointsCollector.count_final_scores
    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
    try:
        game.apply_action_inplace(term_board, int(last_action_idx))
    finally:
        PointsCollector.count_final_scores = _orig
    if not term_board.state.is_terminated():
        raise RuntimeError(
            "endgame ownership reconstruction did not reach a terminal state — "
            "the terminating action was mis-identified")
    return extract_terminal_ownership(term_board.state)


def endgame_terrain_totals(records, n_players: int = 2) -> dict[str, list[int]]:
    """`extract_terminal_ownership` records -> `{carcasum_terrain: [p0, p1]}`."""
    out = {"field": [0] * n_players, "city": [0] * n_players,
           "road": [0] * n_players, "cloister": [0] * n_players}
    for r in records:
        key = _OWNERSHIP_TERRAIN_TO_CARCASUM[r.terrain]
        for w in r.winners:
            out[key][w] += r.points
    return out


# --------------------------------------------------------------------------- #
# the archive contract (identical in spirit to jcz_match.replay_actions)        #
# --------------------------------------------------------------------------- #
def replay_actions(deck_seed: int, actions, profile: str = PROFILE) -> dict:
    """Replay an archived `(deck_seed, actions)` pair through OUR engine alone.
    A record that does not replay is a broken archive."""
    import random

    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.resolve(profile)
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    for i, a in enumerate(actions):
        a = int(a)
        if not game.get_valid_moves(board)[a]:
            return {"ok": False, "illegal_at": i, "action": a, "scores": None, "n_actions": i}
        board, _ = game.get_next_state(board, a)
    ended = bool(game.get_game_ended(board, 0) != 0)
    return {"ok": ended, "illegal_at": None, "scores": list(board.state.scores),
            "n_actions": len(actions), "ended": ended}


def deck_hash(state) -> str:
    """Order-sensitive digest of the dealt deck — SAME rule as
    `jcz_match.match.deck_hash`, so hashes are comparable across drivers."""
    tiles = ([state.next_tile] if state.next_tile is not None else []) + list(state.deck)
    h = hashlib.sha256()
    h.update("\x1f".join(t.description for t in tiles).encode())
    return h.hexdigest()[:16]


def draw_order_for(state, tile_map) -> list[int]:
    """Our dealt deck as Carcasum `tileType` ints, in draw order. Under
    `fixed_v1` the start tile is already on the board, so everything still to
    come is `[next_tile] + deck` — PROTOCOL.md §3.1's exact construction, and
    the same one `jcz_match.match.draw_order_for` uses for the JCZ string ids.
    """
    upcoming = ([state.next_tile] if state.next_tile is not None else []) + list(state.deck)
    return [tile_map[t.description][1] for t in upcoming]


# --------------------------------------------------------------------------- #
# CarcasumDriver — the subprocess, line-JSON, timeout + kill discipline          #
# --------------------------------------------------------------------------- #
class CarcasumError(RuntimeError):
    """The driver produced no usable line (closed, crashed, or malformed)."""


class CarcasumTimeout(CarcasumError):
    """No line within the per-read timeout. The child is killed before this
    is raised — PROTOCOL.md §3.3: an orphaned MCTS is a silent core leak."""


def _default_binary() -> Path:
    env = os.environ.get("CARCASUM_DRIVER")
    if env:
        return Path(env)
    # The binary does not exist yet (PROTOCOL.md predates the C++ side) — this
    # is a best-guess default path for when it does, never relied on by tests
    # (which always pass --binary explicitly, pointed at stub_driver.py).
    return REPO / "vendor" / "carcasum" / "build" / "carcasum_driver"


class CarcasumDriver:
    """One `carcasum_driver` (or a test double speaking the same protocol) child
    process = one game (or, in `--dump-tiles` mode, one static query). Line-JSON
    over stdin/stdout, `\\n`-terminated, per PROTOCOL.md §1. Guarantees the
    child is killed in `close()` / on any read timeout — an orphaned 5-s/move
    MCTS is a silent full-core leak across a multi-hundred-game match.
    """

    def __init__(self, binary: Path | str | None = None, *, read_timeout_s: float = 30.0):
        self.binary = Path(binary) if binary else _default_binary()
        if not self.binary.is_file():
            raise FileNotFoundError(
                f"carcasum_driver not found at {self.binary} — the real binary "
                "does not exist yet; pass --binary pointed at stub_driver.py for "
                "development, or set $CARCASUM_DRIVER once it is built.")
        self.read_timeout_s = float(read_timeout_s)
        # stderr goes to a REAL FILE, not a pipe — the same fix jcz_driver.py
        # already needed and documents: once a child writes more than the OS
        # pipe buffer (~64KB) to an undrained stderr PIPE, the write blocks and
        # the child hangs forever with nothing on stdout to read — which reads
        # exactly like a stuck opponent search, not what it actually is. A file
        # never blocks the writer. `_drain_stderr` reads the tail of it.
        self._err = tempfile.NamedTemporaryFile(              # noqa: SIM115 — closed in close()
            prefix="carcasum_stderr_", suffix=".log", mode="w+", delete=False)
        # ⚠️ BINARY pipes, and OUR OWN line buffer. Do NOT switch this back to
        # `text=True` + `selectors.select()` on `self._p.stdout`.
        #
        # That combination is silently broken and cost a full debugging cycle:
        # `readline()` on a buffered TextIOWrapper pulls a LARGE CHUNK off the fd
        # into Python's userspace buffer, typically swallowing the NEXT protocol
        # line along with the one it returns. The following `select()` then asks
        # the KERNEL whether the fd is readable, the kernel says no (the data is
        # already in userspace), and the read blocks for the full timeout even
        # though a complete line is sitting in the buffer. Symptom: the handshake
        # succeeds, then every game voids as `VOID_ERROR: no protocol line within
        # Ns` with an EMPTY stderr tail — which reads like a hung opponent search
        # and is nothing of the kind.
        #
        # The fix is to own the buffering: read raw bytes with `os.read`, split
        # lines ourselves, and only `select()` when our own buffer holds no
        # complete line. Then "readable" means the same thing to us and to the
        # kernel.
        self._p = subprocess.Popen(                           # noqa: S603
            [str(self.binary)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._err,
            bufsize=0,
        )
        self._fd = self._p.stdout.fileno()
        self._buf = b""
        self._eof = False
        self._sel = selectors.DefaultSelector()
        self._sel.register(self._fd, selectors.EVENT_READ)

    # --- plumbing ------------------------------------------------------------ #
    def send(self, obj: dict) -> None:
        assert self._p.stdin is not None
        self._p.stdin.write((json.dumps(obj) + "\n").encode())
        self._p.stdin.flush()

    def _take_line(self) -> bytes | None:
        """Pop one complete line from our own buffer, or None if none is there."""
        i = self._buf.find(b"\n")
        if i < 0:
            return None
        line, self._buf = self._buf[:i], self._buf[i + 1:]
        return line

    def recv(self) -> dict:
        """One protocol line, or raise. HARD per-read timeout — never a bare
        blocking read (PROTOCOL.md §3.3's exact failure mode: a hung or crashed
        opponent-search process must never wedge the fleet).

        The timeout is per LINE, not per syscall: a partial read restarts the
        wait only for the remainder of the deadline, so a driver that dribbles
        bytes cannot extend its budget indefinitely.
        """
        deadline = time.monotonic() + self.read_timeout_s
        while True:
            line = self._take_line()
            if line is not None:
                if not line.strip():
                    continue                      # tolerate stray blank lines
                try:
                    return json.loads(line)
                except json.JSONDecodeError as e:
                    raise CarcasumError(f"non-JSON protocol line {line!r}: {e}") from None
            if self._eof:
                self.kill()
                raise CarcasumError(
                    f"driver closed stdout with no line (exit={self._p.poll()}); "
                    f"stderr tail: {self._drain_stderr()[-800:]!r}")
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._sel.select(timeout=remaining):
                self.kill()
                raise CarcasumTimeout(
                    f"no protocol line within {self.read_timeout_s}s "
                    f"(exit={self._p.poll()}); stderr tail: {self._drain_stderr()[-800:]!r}")
            try:
                chunk = os.read(self._fd, 65536)
            except OSError as e:
                raise CarcasumError(f"read from driver failed: {e}") from None
            if not chunk:
                self._eof = True
            else:
                self._buf += chunk

    def _drain_stderr(self) -> str:
        """Best-effort stderr tail for an error message, read from the backing
        FILE (never the child's own fd — see `__init__`'s note on why stderr
        is a file, not a pipe). Safe to call at any time; never blocks."""
        try:
            self._err.flush()
            self._err.seek(0)
            return self._err.read()
        except Exception:                                     # noqa: BLE001
            return ""

    def kill(self) -> None:
        if self._p.poll() is None:
            try:
                self._p.kill()
            except Exception:                                 # noqa: BLE001
                pass
        try:
            self._p.wait(timeout=5)
        except Exception:                                     # noqa: BLE001
            pass

    def close(self) -> None:
        try:
            if self._p.stdin is not None and not self._p.stdin.closed:
                try:
                    self.send({"t": "quit"})
                except Exception:                              # noqa: BLE001
                    pass
                try:
                    self._p.stdin.close()
                except Exception:                               # noqa: BLE001
                    pass
            self._p.wait(timeout=5)
        except Exception:                                       # noqa: BLE001
            pass
        finally:
            self.kill()  # guaranteed, even after a clean wait
            try:
                self._sel.close()
            except Exception:                                    # noqa: BLE001
                pass
            try:
                self._err.close()
                os.unlink(self._err.name)
            except Exception:                                    # noqa: BLE001
                pass

    def __enter__(self) -> "CarcasumDriver":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- dump_tiles mode ------------------------------------------------------ #
    @classmethod
    def dump_tiles(cls, binary: Path | str | None = None, timeout_s: float = 20.0) -> dict:
        """`carcasum_driver --dump-tiles`: one JSON line, no game (PROTOCOL.md §4).
        A short-lived synchronous subprocess — no CarcasumDriver session needed.
        """
        b = Path(binary) if binary else _default_binary()
        if not b.is_file():
            raise FileNotFoundError(f"carcasum_driver not found at {b} for --dump-tiles")
        out = subprocess.run(                                    # noqa: S603
            [str(b), "--dump-tiles"], capture_output=True, text=True, timeout=timeout_s)
        line = (out.stdout or "").strip().splitlines()
        if out.returncode != 0 or not line:
            raise CarcasumError(
                f"--dump-tiles failed (rc={out.returncode}): {(out.stderr or '')[-1000:]}")
        resp = json.loads(line[0])
        if resp.get("t") != "tiles":
            raise CarcasumError(f"--dump-tiles returned unexpected shape: {resp!r}")
        return resp


def tile_rotation_period(tile: dict) -> int:
    """Smallest `p > 0` with `rotate(tile, p) == tile`; 4 when the tile is asymmetric.

    ⚠️ THIS IS NOT COSMETIC — it is a genuine encoding difference between the two
    engines, and getting it wrong voids every game with a symmetric tile.

    **Carcasum enumerates only PHYSICALLY DISTINCT placements; our action space
    enumerates all four rotations regardless.** A chapel (`FFFF`), a full city
    (`CCCC`) and the crossroads (`RRRR`) have p == 1, so Carcasum offers exactly ONE
    orientation where we offer four. The four `FCFC`/`FRFR`-shaped tiles
    (`CFc+`, `CFc.1`, `CFC.2`, `RFr`) have p == 2. Everything else is p == 4.

    So the correspondence is `carcasum_o == our_o % p`, and inverting is one-to-many
    — exactly the same *finer-slots* situation `invert_meeple_move` already documents
    for meeples, and handled the same way: match, then record the multiplicity.

    The period is derived from the tile's OWN structure as the driver reports it —
    edges *and* the node partition, not edges alone, because two tiles can share an
    edge signature while differing in how their fields are cut.
    """
    order = ("W", "N", "E", "S")                 # edges = [left, up, right, down]
    edges = list(tile["edges"])
    old = {order[i]: edges[i] for i in range(4)}

    def sig(k: int):
        # A CW rotation by k moves the content of side s to side s+k: new[s] = old[s-k].
        rot_edges = tuple(old[order[(order.index(s) - k) % 4]] for s in order)
        rot_nodes = frozenset(
            (str(n["terrain"]), frozenset(rotate_labels(n["labels"], k)))
            for n in tile["nodes"])
        return rot_edges, rot_nodes

    base = sig(0)
    for k in (1, 2, 3):
        if sig(k) == base:
            return k
    return 4


def load_carcasum_node_labels(binary: Path | str | None = None):
    """`--dump-tiles` -> `({tile_type: [{"i","terrain","labels"}]}, {tile_type: period}, resp)`.

    The node-label cache is what `invert_meeple_move` rotates through
    `rotate_labels`; the period cache is what the tile-coordinate maps reduce
    orientations by (see `tile_rotation_period`).
    """
    resp = CarcasumDriver.dump_tiles(binary)
    out: dict[int, list[dict]] = {}
    periods: dict[int, int] = {}
    for t in resp["tiles"]:
        tt = int(t["tile_type"])
        out[tt] = [
            {"i": int(n["i"]), "terrain": str(n["terrain"]), "labels": list(n["labels"])}
            for n in t["nodes"]
        ]
        periods[tt] = tile_rotation_period(t)
    return out, periods, resp


# --------------------------------------------------------------------------- #
# manifest                                                                     #
# --------------------------------------------------------------------------- #
def _git_rev_detail(repo: Path) -> tuple[str | None, str | None]:
    """`(rev, unavailable_reason)` for a checkout. NEVER raises, never invents —
    a rev names a checkout and only means something on a box where that
    checkout exists (same caveat as jcz_match.match._git_rev_detail)."""
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=20)
    except Exception as exc:                                     # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"[:200]
    rev = out.stdout.strip()
    if rev:
        return rev, None
    first = (out.stderr or "").strip().splitlines()
    reason = first[0] if first else f"git rev-parse exited {out.returncode}, no output"
    return None, reason[:200]


def _git_rev(repo: Path) -> str | None:
    return _git_rev_detail(repo)[0]


_FILE_SHA256_CACHE: dict[str, str] = {}


def _sha256_stream(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def binary_sha256(binary: Path) -> str:
    """THE PRIMARY Carcasum provenance witness — full sha256 of the bytes that
    actually ran, cached per process (mirrors `jcz_match.match.jar_sha256`).
    RAISES on a missing/unreadable binary: a record with no readable executable
    behind it is not a record worth writing."""
    key = str(Path(binary))
    got = _FILE_SHA256_CACHE.get(key)
    if got is not None:
        return got
    p = Path(binary)
    if not p.is_file():
        raise FileNotFoundError(
            f"carcasum binary not found at {p} — refusing to stamp a null "
            "provenance witness.")
    got = _sha256_stream(p)
    _FILE_SHA256_CACHE[key] = got
    return got


def _sha256_file(p: Path) -> str | None:
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except Exception:                                            # noqa: BLE001
        return None


def build_manifest(*, binary: Path, tile_mapping_path: Path, driver_ready: dict | None,
                   champ_manifest, execution, sims, k_dets, prof, opponent: dict | None,
                   audit_mode: str | None) -> dict:
    """Everything needed to re-run this game, and everything that could explain it."""
    binary = Path(binary)
    bin_sha = binary_sha256(binary)
    vendor_repo = REPO / "vendor" / "carcasum"
    vendor_rev, vendor_rev_reason = _git_rev_detail(vendor_repo)
    return {
        "schema": SCHEMA,
        "our_git_rev": _git_rev(REPO),
        "vendor_carcasum_git_rev": vendor_rev,
        "vendor_carcasum_git_rev_available": vendor_rev is not None,
        "vendor_carcasum_git_rev_unavailable_reason": vendor_rev_reason,
        "carcasum_binary": str(binary),
        "carcasum_binary_sha256": bin_sha,
        "carcasum_provenance_witness": "binary_sha256",
        "carcasum_driver_revision": (driver_ready or {}).get("revision"),
        "carcasum_driver_patches": (driver_ready or {}).get("patches"),
        "carcasum_driver_players": (driver_ready or {}).get("players"),
        # The HANDSHAKE-REPORTED coordinate frame, verbatim — never a constant
        # this file assumes. See CARCASUM_OFFSET's docstring for why.
        "carcasum_ready_board_size": (driver_ready or {}).get("board_size"),
        "carcasum_ready_start_xy": (driver_ready or {}).get("start_xy"),
        "tile_mapping_tsv": str(tile_mapping_path),
        "tile_mapping_sha256": _sha256_file(tile_mapping_path),
        "rules_profile": prof.name,
        "rules_manifest": prof.as_manifest(),
        "r9_env": os.environ.get("CARCASSONNE_FIX_R9"),
        "r9_note": (
            "R9 is ON here (required — Carcasum's basic.xml carries the same "
            "R9 farm-data divergence as JCZ 5.x, byte-identical text, see "
            "tests/data/carcasum/PROVENANCE.md). Not a PRODUCTION deviation "
            "note the way jcz_match's is: R9 is BUILT, not yet ADOPTED, so "
            "results here are still not comparable to walled elo."),
        "champion_manifest": champ_manifest,
        "execution": dict(execution) if execution is not None else None,
        "sims_override": sims, "k_dets_override": k_dets,
        "opponent": dict(opponent) if opponent else None,
        "audit_mode": audit_mode,
    }


# --------------------------------------------------------------------------- #
# audit-mode policies                                                          #
# --------------------------------------------------------------------------- #
class _GreedyPolicy:
    """`--audit-mode greedy`: `RuleBasedPlayer`, the Tier-1 1-ply policy (NOT a
    `make_production_champion` mode — "tier1-greedy" only ever named a
    tie-arbiter continuation in champion_factory.py's prose). Precedent for
    this exact construction: `scripts/f3_public_state_oracle/mine_roots.py`
    and `scripts/rustport/reconcile_exact_solver.py`.

    ⚠️ Uses the v1 OBJECT leaf, not `flat_leaf` — slower per move than the
    champion. Fine for a rules-coverage gate (we want coverage, not speed);
    never use it to project timing.
    """

    def __init__(self, game, seed: int):
        from carcassonne_ai.rule_based_player import RuleBasedPlayer

        self._game = game
        self._player = RuleBasedPlayer(seed=seed)
        self.manifest = {"audit_mode": "greedy", "seed": seed}

    def choose_action(self, board) -> int:
        valid = self._game.get_valid_moves(board)
        return int(self._player.choose_action(self._game, board, valid))


class _RandomPolicy:
    """`--audit-mode random`: uniform over the legal mask, seeded."""

    def __init__(self, game, seed: int):
        import random

        self._game = game
        self._rng = random.Random(seed)
        self.manifest = {"audit_mode": "random", "seed": seed}

    def choose_action(self, board) -> int:
        valid = self._game.get_valid_moves(board)
        legal = [i for i, v in enumerate(valid) if v]
        return int(self._rng.choice(legal))


def _make_champion(game, seed: int, *, sims, k_dets, execution, audit_mode: str | None,
                   tiearb: dict | None = None):
    if audit_mode is None:
        from carcassonne_ai.champion_factory import make_production_champion

        return make_production_champion("fair", game=game, seed=seed, sims=sims,
                                        k_dets=k_dets, verify=True, tiearb=tiearb,
                                        **execution.factory_kwargs())
    if audit_mode == "greedy":
        return _GreedyPolicy(game, seed)
    if audit_mode == "random":
        return _RandomPolicy(game, seed)
    raise ValueError(f"unknown --audit-mode {audit_mode!r} (want 'greedy' or 'random')")


# --------------------------------------------------------------------------- #
# the tie arbiter (OUR side) — measurement/carcasum_arb_challenge_prep/         #
# Ported field-for-field from scripts/jcz_match/match.py's own                 #
# `_resolve_tiearb`/`_champ_tiearb_telemetry` (that harness's the precedent    #
# for arming the arbiter on an out-of-lineage-match champion at all — this     #
# harness had NO tiearb path before this port). Flags kept `--champ-tiearb-*`  #
# to match that sibling harness's own naming ("our side is the champ").       #
# --------------------------------------------------------------------------- #
def _resolve_tiearb(args) -> dict | None:
    """The ``--champ-tiearb-*`` flags -> the dict ``make_production_champion`` takes,
    or ``None`` when the arbiter was not armed.

    ⚠️ ``None``, not a dict with ``enabled=False``, on the unarmed leg (ARM-OFF) — so
    an unarmed record's manifest carries no ``cand_tiearb`` key at all, byte-identical
    to every Carcasum archive that predates this plumbing (r1, rung 2). Explicit
    arming is required (``--champ-tiearb-enabled``); there is no default-on path.

    ⭐ ``phase_gate`` is ALWAYS in the armed dict, defaulting to ``"all"`` (the ungated
    arbiter — this harness exposes no flag for it, so "all" is the only value it can
    take today). It is NOT decoration: ``FairAgentRs``'s ``search_config.tiearb`` getter
    emits ``phase_gate`` unconditionally since measurement/phasegate_prep, and
    ``_worker_init``'s ``resolved != dict(tiearb)`` probe below is an EXACT dict
    comparison. Omitting it here makes every armed worker die at bootstrap on a
    like-for-unlike compare, which is a false alarm on the guard's part — the guard
    itself stays as-is, because it is the thing that catches a genuinely stale wheel.
    """
    if not bool(getattr(args, "champ_tiearb_enabled", False)):
        return None
    return {"enabled": True,
            "B": int(args.champ_tiearb_b), "J": int(args.champ_tiearb_j),
            "mode": str(args.champ_tiearb_mode),
            "phase_gate": str(getattr(args, "champ_tiearb_phase_gate", "all")),
            "salt": str(args.champ_tiearb_salt),
            "eps": float(args.champ_tiearb_eps)}


def _champ_tiearb_telemetry(champ, tiearb) -> dict | None:
    """TIE-ARBITER per-game liveness read (OUR side). ``None`` unless this game was
    armed with an ENABLED ``tiearb``; an armed game whose champion is NOT a
    rust-backed agent (no ``_rs``/``FairAgentRs``) is a wiring bug and RAISES rather
    than stamping ``None`` — a silent ``None`` would grade a champion-vs-champion null
    wearing the shape of a real ARM-ON cell (the J13 failure mode).

    Field-for-field the same read as ``jcz_match/match.py::_champ_tiearb_telemetry``.
    """
    if not tiearb or not bool(tiearb.get("enabled")):
        return None
    rs = getattr(champ, "_rs", None)
    if rs is None:
        raise RuntimeError(
            "champ_tiearb is armed but the champion has no FairAgentRs (the tie "
            "arbiter is rust-only) — it cannot have run")
    s = rs.stats()
    if not bool(s.get("tiearb_enabled")):
        raise RuntimeError(
            "champ_tiearb is armed but FairAgentRs.stats() reports "
            "tiearb_enabled=False — the knob was dropped between main() and the "
            "rust config (a STALE carc_rs wheel is the usual cause)")
    return {
        "tile_plies": int(s["tiearb_tile_plies"]),
        "fires": int(s["tiearb_fired_plies"]),
        "fired_plies": int(s["tiearb_fired_plies"]),
        "pickchanges": int(s["tiearb_pickchanges"]),
        "arms_total": int(s["tiearb_arms_total"]),
        "playouts_total": int(s["tiearb_playouts_total"]),
        "secs": float(s["tiearb_secs"]),
        "errors": int(s.get("tiearb_errors") or 0),
        "first_error": s.get("tiearb_first_error"),
        "partial_argmax": int(s.get("tiearb_partial_argmax") or 0),
        "max_plies": int(s.get("tiearb_max_plies") or 0),
        "mode": str(s["tiearb_mode"]),
        "B": int(s["tiearb_b"]), "J": int(s["tiearb_j"]),
    }


# --------------------------------------------------------------------------- #
# one match                                                                    #
# --------------------------------------------------------------------------- #
DEFAULT_OPPONENT = {
    "kind": "mcts", "budget_ms": 5000, "playouts": None, "cp": 0.5,
    "reuse_tree": False, "node_priors": False, "progressive_widening": False,
    "progressive_bias": False, "utility": "portion", "playout": "random",
}


def play_one_match(deck_seed: int, champ_seat: int, *, replicate: int = 0,
                   sims=None, k_dets=None, binary=None, opponent: dict | None = None,
                   execution=None, verify_replay: bool = True, max_plies: int = 400,
                   audit_mode: str | None = None, read_timeout_s: float | None = None,
                   node_labels_by_type: dict | None = None,
                   tile_periods: dict | None = None,
                   tiearb: dict | None = None,
                   agent=None, on_apply=None) -> dict:
    """Play ONE champion-vs-Carcasum game. Returns the archive record.

    ⚠️ `agent` / `on_apply` are ADDITIVE injection points, both default-None, and
    when both are None this function is byte-identical to what it was before they
    existed. They exist for ONE caller —
    `scripts/carcasum_remote/server.py`, the phone remote-opponent server — so
    that the coordinate/rotation/meeple maps, the inversion discipline, the void
    taxonomy and the score diffing in this file are REUSED WHOLESALE rather than
    re-implemented against the same binary a second time (a second inverter is a
    second thing that can silently disagree with our engine).

    * `agent` replaces `_make_champion(...)`: any object with
      `choose_action(board) -> int`. `sims`/`k_dets`/`execution`/`audit_mode`/
      `tiearb` are then not used to BUILD anything (they still land in the
      manifest verbatim, which is what a reader of the record wants).
    * `on_apply(action, seat, kind)` is called from `_apply` AFTER the action has
      landed on our board, in ply order, for BOTH seats — including the actions
      this file synthesises itself (the implicit meeple pass, the redraw pass).
      That is the whole authoritative action sequence, which is exactly what a
      remote client needs to stay in lockstep. It must not raise; if it does, the
      game faults like any other harness error.

    Carcasum's `Game::step()` owns the turn loop, so this is "read a driver
    line, react", not a loop we drive — see the module docstring's Protocol
    notes. Never raises for a game-level problem: a fault becomes a `void`
    class on the record, counted, excluded from the win rate, never dropped.
    """
    from carcassonne_ai import mirror_protocol as MP
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    TM = _tile_map_mod()
    tile_map = load_carcasum_tile_mapping()
    if node_labels_by_type is None or tile_periods is None:
        node_labels_by_type, tile_periods, _ready0 = load_carcasum_node_labels(binary)

    prof = rules_profile.activate(PROFILE)
    if not prof.as_manifest()["r9_env_ok"]:
        raise RuntimeError(
            "CARCASSONNE_FIX_R9 is not on: this driver is only sound with R9 "
            "(same divergence Carcasum's basic.xml carries as JCZ). Export it "
            "BEFORE importing carcassonne_ai.")

    class _Div:
        """Minimal counter+samples container, same shape as
        `jcz_oracle.replay_diff.Divergences` (imported, not copied, would be
        redundant here — this file's REAL/CLASSIFIED taxonomy is its own, so a
        bare re-implementation of the two-method container is the honest
        choice rather than importing a class whose OWN `.real()` hardcodes a
        taxonomy this file does not use)."""

        def __init__(self):
            self.counts: dict[str, int] = {}
            self.samples: dict[str, list] = {}

        def add(self, cls: str, ply, detail) -> None:
            self.counts[cls] = self.counts.get(cls, 0) + 1
            lst = self.samples.setdefault(cls, [])
            if len(lst) < 3:
                lst.append({"ply": ply, "detail": detail})

    div = _Div()

    champ_seat = int(champ_seat)
    opp_seat = 1 - champ_seat
    seed = agent_seed(deck_seed, champ_seat, replicate)
    o_seed = opp_seed(deck_seed, champ_seat, replicate)
    opponent = dict(DEFAULT_OPPONENT, **(opponent or {}))

    import random

    random.seed(int(deck_seed))                  # the root_replay contract
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    origin = (game.start_row, game.start_col)

    if execution is None:
        from carcassonne_ai.mirror_protocol import resolve_execution

        execution = resolve_execution("rust", rust_threads=1)
    if agent is not None:
        champ = agent
    else:
        champ = _make_champion(game, seed, sims=sims, k_dets=k_dets, execution=execution,
                               audit_mode=audit_mode, tiearb=tiearb)
    agents = {champ_seat: champ}
    MP.seat(agents, board)                        # mirror: seated once, on the INITIAL board

    st0 = board.state
    dh = deck_hash(st0)
    draw_order = draw_order_for(st0, tile_map)
    if len(draw_order) != CARCASUM_DECK_LEN:
        raise RuntimeError(
            f"draw_order_for produced {len(draw_order)} entries, expected "
            f"{CARCASUM_DECK_LEN} (fixed_v1's [next_tile]+deck) — PROTOCOL.md §3.1")
    start_tile = st0.board[game.start_row][game.start_col]
    start_desc = start_tile.description if start_tile is not None else START_TILE_DESC
    if start_desc != START_TILE_DESC:
        div.add("HARNESS_ERROR", -1, {"unexpected_start_tile": start_desc})

    actions: list[int] = []
    move_log: list[dict] = []
    ms_by_seat = {0: 0.0, 1: 0.0}
    #: Driver-reported opponent cost per TURN (wall ms) and rollouts per turn.
    opp_drv_ms: list[float] = []
    opp_drv_playouts: list[float] = []
    moves_by_seat = {0: 0, 1: 0}
    think_moves_by_seat = {0: 0, 1: 0}
    void: str | None = None
    void_detail: dict | None = None
    last_score_detail: dict | None = None
    prev_score_detail: dict | None = None
    term_prev_board = None
    term_action: int | None = None
    t_start = time.time()

    def _apply(a: int, seat: int, ms: float, what: str, extra=None) -> None:
        nonlocal board, term_prev_board, term_action
        candidate_prev = board
        actions.append(int(a))
        ms_by_seat[seat] += ms
        moves_by_seat[seat] += 1
        if ms > 0.0:
            think_moves_by_seat[seat] += 1
        move_log.append({"ply": len(actions) - 1, "seat": seat, "kind": what,
                         "action": int(a), "ms": round(ms, 2), **(extra or {})})
        board, _ = game.get_next_state(board, int(a))
        MP.advance(agents, int(a))
        if term_prev_board is None and game.get_game_ended(board, 0) != 0:
            term_prev_board, term_action = candidate_prev, int(a)
        if on_apply is not None:
            on_apply(int(a), int(seat), str(what))

    def _void(cls: str, detail: dict) -> None:
        nonlocal void, void_detail
        if void is None:
            void, void_detail = cls, detail

    if read_timeout_s is not None:
        read_timeout_s = float(read_timeout_s)
    elif opponent.get("playouts"):
        # Playout-budget mode (`--opp-playouts`): `main()` always sets
        # `opponent["budget_ms"] = None` in this mode (see the CLI plumbing
        # below), so the OLD formula's `(opponent.get("budget_ms") or 5000)`
        # silently fell through to DEFAULT_OPPONENT's 5000ms every time,
        # giving EVERY playout-mode rung the SAME fixed 35.0s read timeout
        # regardless of how many playouts were actually requested. That is
        # what produced the rung-C (m=262144) 100% VOID_ERROR storm
        # (2026-08-23): the driver's real per-move search time scales
        # ~linearly with playout count (measured on the laptop box,
        # m=131072 -> 22.26s realized, m=262144 -> 44.73s realized, i.e.
        # ~1.70e-4s/playout) and the fixed 35.0s cap killed every opponent
        # move once the budget crossed it. This branch scales the timeout
        # with the actual playout count instead, at ~1.5x the measured slope
        # (2.5e-4 s/playout) plus the same +15.0s fixed overhead the
        # budget_ms branch already used, floored at the same 30.0s.
        read_timeout_s = max(30.0, opponent["playouts"] * 2.5e-4 + 15.0)
    else:
        read_timeout_s = max(30.0, (opponent.get("budget_ms") or 5000) / 1000.0 * 4 + 15.0)
    drv = CarcasumDriver(binary=binary, read_timeout_s=read_timeout_s)
    ready: dict | None = None
    final_msg: dict | None = None
    try:
        drv.send({"t": "new_game", "deck": draw_order, "external_seat": champ_seat,
                 "opponent": opponent, "seed": o_seed})
        ready = drv.recv()
        if ready.get("t") != "ready":
            _void(VOID_ERROR, {"stage": "setup", "reply": ready})
            raise _StopGame()

        # The coordinate ORIGIN comes from THIS handshake, never a hardcoded
        # constant — CARCASUM_OFFSET/CARCASUM_BOARD_SIZE are PROTOCOL.md's
        # stated values, used ONLY as assertion targets — never as a fallback.
        # A wrong offset does not fail loudly on its own: it produces a
        # legal-looking move at the wrong square, which reads back as
        # VOID_UNMAPPABLE on essentially every ply and masquerades as "the two
        # engines disagree on the rules" rather than what it actually is (a
        # coordinate bug). So: derive from the handshake, validate against the
        # stated relation (offset == board_size // 2), and void loudly with a
        # DISTINCT class at ply -1 rather than let it ride.
        reported_size = ready.get("board_size")
        reported_xy = ready.get("start_xy")
        if reported_xy is None:
            # Deliberately NOT a fallback. Guessing an origin is the exact
            # failure mode this whole block exists to prevent.
            div.add("COORD_FRAME_MISMATCH", -1, {
                "ready_missing_start_xy": True,
                "note": "the driver must publish its own coordinate frame; "
                        "refusing to guess an origin."})
            _void(VOID_ERROR, {"stage": "setup", "reason": "ready_missing_start_xy",
                               "ready": ready})
            raise _StopGame()
        offset_xy = (int(reported_xy[0]), int(reported_xy[1]))
        if reported_size is not None:
            expect = int(reported_size) // 2
            if offset_xy != (expect, expect):
                div.add("COORD_FRAME_MISMATCH", -1, {
                    "ready_board_size": reported_size, "ready_start_xy": list(offset_xy),
                    "expected_start_xy_from_board_size": [expect, expect],
                    "note": "PROTOCOL.md states offset = board_size/2 and the start tile "
                            "at (offset, offset); this handshake is internally "
                            "inconsistent with its own stated relation. Refusing to guess "
                            "an origin rather than risk every later ply misreading as a "
                            "rules divergence."})
                _void(VOID_ERROR, {"stage": "setup", "reason": "COORD_FRAME_MISMATCH", "ready": ready})
                raise _StopGame()
        if reported_size is not None and int(reported_size) != CARCASUM_BOARD_SIZE:
            div.add("HARNESS_ERROR", -1, {"board_size_differs_from_protocol_md_stated_value": True,
                                          "ready_board_size": reported_size,
                                          "protocol_md_stated_value": CARCASUM_BOARD_SIZE})
        _c_id, start_type, _rot0 = tile_map[start_desc]
        if int(ready.get("start_tile_type", -1)) != start_type:
            div.add("HARNESS_ERROR", -1, {"unexpected_start_tile_type": ready.get("start_tile_type"),
                                          "expected": start_type})

        while True:
            msg = drv.recv()
            t = msg.get("t")
            ply = int(msg.get("ply", len(actions)))
            if len(actions) >= max_plies:
                div.add("HARNESS_ERROR", ply, f"ply cap {max_plies} hit")
                break

            if t == "fault":
                _void(VOID_ERROR, {"why": msg.get("why"), "detail": msg.get("detail")})
                break

            if t == "game_over":
                final_msg = msg
                break

            if t == "req_tile":
                player = int(msg.get("player", champ_seat))
                if player != champ_seat:
                    div.add("SEAT_DESYNC", ply, {"expected": champ_seat, "got": player})
                    break
                if board.state.phase != GamePhase.TILES:
                    div.add("HARNESS_ERROR", ply, f"req_tile while our phase={board.state.phase}")
                    break
                _c_id, c_type, _rot = tile_map[board.state.next_tile.description]
                if int(msg.get("tile_type", c_type)) != c_type:
                    div.add("HARNESS_ERROR", ply,
                            {"deck_desync": True, "ours": c_type, "carcasum": msg.get("tile_type")})
                    break
                diff_tile_legality(div, ply, game, board, tile_map, origin,
                                   msg.get("placements"), offset_xy, periods=tile_periods)
                t0 = time.perf_counter()
                a = int(champ.choose_action(board))
                ms = (time.perf_counter() - t0) * 1000.0
                reply = forward_tile_action(game, board, tile_map, a, origin, offset_xy,
                                            periods=tile_periods)
                drv.send(reply)
                _apply(a, player, ms, "champ_tile")
                continue

            if t == "req_meeple":
                player = int(msg.get("player", champ_seat))
                if player != champ_seat:
                    div.add("SEAT_DESYNC", ply, {"expected": champ_seat, "got": player})
                    break
                nodes = msg.get("nodes") or []
                diff_meeple_legality(div, ply, game, board, nodes)
                t0 = time.perf_counter()
                a = int(champ.choose_action(board))
                ms = (time.perf_counter() - t0) * 1000.0
                node_idx, offered = forward_meeple_action(game, board, a, nodes)
                if node_idx is None and offered.get("our_choice") != "pass":
                    _void(VOID_UNMAPPABLE, {"ply": ply, "phase": "meeples", "ours": offered})
                    break
                drv.send({"t": "meeple", "i": node_idx})
                _apply(a, player, ms, "champ_meeple",
                       {"n_matching_nodes": offered.get("n_matching_nodes")})
                continue

            if t == "ev_move":
                player = int(msg["player"])
                if player == champ_seat:
                    # our own move, echoed back — assert round-trip, do NOT re-apply,
                    # EXCEPT the implicit meeple-phase pass when req_meeple was never sent.
                    if board.state.phase == GamePhase.MEEPLES:
                        if msg.get("meeple") is not None:
                            div.add("HARNESS_ERROR", ply,
                                    "carcasum reports a meeple for our seat but never "
                                    "sent req_meeple")
                            break
                        a, offered = invert_pass_meeple(game, board)
                        if a is None:
                            _void(VOID_UNMAPPABLE, {"ply": ply, "phase": "meeples", "ours": offered})
                            break
                        _apply(a, player, 0.0, "champ_meeple_pass_implicit")
                else:
                    if board.state.phase != GamePhase.TILES:
                        div.add("HARNESS_ERROR", ply, f"ev_move(opp) while our phase={board.state.phase}")
                        break
                    a, offered = invert_tile_move(game, board, tile_map, x=msg.get("x"),
                                                   y=msg.get("y"), o=msg.get("o"),
                                                   tile_type=msg.get("tile_type"), origin=origin,
                                                   offset_xy=offset_xy, periods=tile_periods)
                    if a is None:
                        _void(VOID_UNMAPPABLE, {"ply": ply, "phase": "tiles",
                                                "carcasum_move": msg, "ours": offered})
                        break
                    # The opponent's cost is measured by the DRIVER, not by us: from
                    # here we only see the wall time of a blocking read, which folds in
                    # our own scheduling. `ms` is the driver's wall clock for the turn
                    # and `playouts` its rollout count -- the two figures that price the
                    # budget knob and let the thesis's 42,879 playouts/turn be checked on
                    # our hardware. Carried onto the move_log and aggregated per game;
                    # `_apply` still receives 0.0 so the CHAMPION's ms/move denominator
                    # stays a pure thinking rate.
                    _cm = msg.get("ms")
                    _cp = msg.get("playouts")
                    if isinstance(_cm, (int, float)) and _cm > 0:
                        opp_drv_ms.append(float(_cm))
                    if isinstance(_cp, (int, float)) and _cp > 0:
                        opp_drv_playouts.append(float(_cp))
                    _apply(a, player, 0.0, "opp_tile",
                          {"carcasum_move": {"x": msg.get("x"), "y": msg.get("y"), "o": msg.get("o")},
                           "carcasum_ms": _cm, "carcasum_playouts": _cp})
                    if board.state.phase == GamePhase.MEEPLES:
                        mv = msg.get("meeple")
                        if mv is None:
                            a2, offered2 = invert_pass_meeple(game, board)
                            what = "opp_meeple_pass"
                        else:
                            a2, offered2 = invert_meeple_move(
                                game, board, node_labels_by_type,
                                tile_type=msg.get("tile_type"), o=msg.get("o"), node_index=mv)
                            what = "opp_meeple"
                        if a2 is None:
                            _void(VOID_UNMAPPABLE, {"ply": ply, "phase": "meeples",
                                                    "carcasum_move": msg, "ours": offered2})
                            break
                        _apply(a2, player, 0.0, what)
                if void is None:
                    diff_running_scores(div, ply, board.state, msg.get("scores"))
                    if msg.get("score_detail") is not None:
                        # `prev_score_detail` deliberately lags ONE ply behind
                        # `last_score_detail`: the TERMINATING ply's own
                        # `ev_move` already carries the fully-swept final
                        # score_detail (the engine runs its endgame sweep
                        # synchronously inside the SAME step that empties the
                        # tile bag — true of our engine's `count_final_scores`
                        # and, per PROTOCOL.md §3.2(c)'s single `Game::step()`,
                        # plausibly true of Carcasum too). So the endgame-only
                        # DELTA this driver wants is
                        # (this ply's detail) - (the PREVIOUS ply's detail),
                        # not (game_over's detail) - (the terminating ply's own
                        # already-final detail), which is always zero by
                        # construction and would silently hide the sweep.
                        prev_score_detail = last_score_detail
                        last_score_detail = msg["score_detail"]
                continue

            if t == "ev_discard":
                player = int(msg["player"])
                if board.state.phase != GamePhase.TILES:
                    div.add("HARNESS_ERROR", ply, f"ev_discard while our phase={board.state.phase}")
                    break
                from carcassonne_ai import action_space as A

                pass_idx = A.tile_pass_index(game.window_size)
                if not game.get_valid_moves(board)[pass_idx]:
                    div.add("HARNESS_ERROR", ply, "ev_discard but our TILES-phase pass is not legal")
                    break
                div.add("UNPLACEABLE_REDRAW", ply,
                        {"tile": board.state.next_tile.description if board.state.next_tile else None})
                _apply(pass_idx, player, 0.0, "redraw_pass")
                continue

            div.add("HARNESS_ERROR", ply, f"unexpected message type {t!r}")
            break

        our_final = list(board.state.scores)
        carcasum_final = (final_msg or {}).get("scores")
        ended = bool(game.get_game_ended(board, 0) != 0)
        agree = (our_final == carcasum_final) if (ended and carcasum_final is not None) else None
        if ended and carcasum_final is not None and not agree:
            div.add("SCORE_FINAL", -1, {"ours": our_final, "carcasum": carcasum_final})
        n_running = div.counts.pop("SCORE_RUNNING", 0)
        if n_running:
            dest = "SCORE_TIMING" if agree else "SCORE_FINAL"
            div.counts[dest] = div.counts.get(dest, 0) + n_running
            div.samples.setdefault(dest, []).extend(div.samples.pop("SCORE_RUNNING", [])[:3])

        farm_points_ours = farm_points_theirs = None
        endgame_ours: dict[str, list[int]] = {}
        endgame_carcasum_delta: dict[str, list[int]] = {}
        if final_msg is not None and term_prev_board is not None:
            try:
                records = compute_endgame_ownership(game, term_prev_board, term_action)
                endgame_ours = endgame_terrain_totals(records, n_players=len(our_final))
                final_detail = final_msg.get("score_detail") or {}
                their_field = [int(v) for v in (final_detail.get("field") or [0] * len(our_final))]
                farm_points_ours, farm_points_theirs = endgame_ours["field"], their_field
                if endgame_ours["field"] != their_field:
                    div.add("FARM_SCORE_FINAL", -1, {"ours": endgame_ours["field"], "carcasum": their_field})
                base_detail = prev_score_detail or {}
                for terr in ("city", "road", "cloister"):
                    base = [int(v) for v in (base_detail.get(terr) or [0] * len(our_final))]
                    fin = [int(v) for v in (final_detail.get(terr) or [0] * len(our_final))]
                    delta = [fin[i] - base[i] for i in range(len(fin))]
                    endgame_carcasum_delta[terr] = delta
                    if endgame_ours[terr] != delta:
                        div.add("ENDGAME_TERRAIN_MISMATCH", -1, {
                            "terrain": terr, "ours": endgame_ours[terr], "carcasum_delta": delta,
                            "carcasum_base": base, "carcasum_final": fin,
                            "note": "TELEMETRY, NOT A RULES FINDING. delta = terminal "
                                    "score_detail minus the score_detail at the ply BEFORE the "
                                    "terminating one, so it also carries that ply's MID-GAME "
                                    "closures; measured against the terminating ply itself the "
                                    "delta is identically zero, because Carcasum runs endGame() "
                                    "inside step(). Neither ply yields the endgame-only quantity, "
                                    "so this class was demoted out of REAL on 2026-08-23 after "
                                    "measuring both. FARM_SCORE_FINAL is the sound per-terrain "
                                    "check. See _ENDGAME_DELTA_UNSOUND in this module."})
            except Exception as e:                              # noqa: BLE001
                div.add("HARNESS_ERROR", -1, f"endgame ownership audit failed: {type(e).__name__}: {e}")
    except _StopGame:
        our_final = list(board.state.scores)
        ended = False
        agree = None
        farm_points_ours = farm_points_theirs = None
        endgame_ours, endgame_carcasum_delta = {}, {}
    except Exception as e:                                       # noqa: BLE001 — a fault is a CLASS, not a crash
        div.add("HARNESS_ERROR", -1, f"{type(e).__name__}: {e}")
        _void(VOID_ERROR, {"error": f"{type(e).__name__}: {e}"})
        our_final, ended, agree = list(board.state.scores), False, None
        farm_points_ours = farm_points_theirs = None
        endgame_ours, endgame_carcasum_delta = {}, {}
    finally:
        drv.close()

    real = {k: v for k, v in div.counts.items() if k in REAL}
    if void is None and real:
        _void(VOID_DIVERGENT, {"real": real})
    if void is None and not ended:
        _void(VOID_ERROR, {"error": "game did not reach a terminal state"})

    champ_score = our_final[champ_seat] if our_final else None
    opp_score = our_final[opp_seat] if our_final else None
    rec = {
        "schema": SCHEMA,
        "deck_seed": int(deck_seed), "champ_seat": champ_seat, "opp_seat": opp_seat,
        "replicate": int(replicate), "agent_seed": seed, "opp_seed": o_seed,
        "actions": actions, "n_actions": len(actions), "deck_hash": dh,
        "scores": our_final, "carcasum_reported_scores": (final_msg or {}).get("scores"),
        "final_agree": agree, "champ_score": champ_score, "opp_score": opp_score,
        "margin_champ_minus_opp": (None if champ_score is None else int(champ_score) - int(opp_score)),
        "winner": (None if champ_score is None else
                  "champ" if champ_score > opp_score else
                  "opp" if opp_score > champ_score else "draw"),
        "void": void, "void_detail": void_detail,
        "counts": dict(div.counts), "real": real, "samples": div.samples,
        "farm_points_ours": farm_points_ours, "farm_points_theirs": farm_points_theirs,
        "endgame_terrain_ours": endgame_ours, "endgame_terrain_carcasum_delta": endgame_carcasum_delta,
        "ms_by_seat": {str(k): round(v, 1) for k, v in ms_by_seat.items()},
        "moves_by_seat": {str(k): v for k, v in moves_by_seat.items()},
        "think_moves_by_seat": {str(k): v for k, v in think_moves_by_seat.items()},
        "ms_per_move_champ": round(ms_by_seat[champ_seat] / max(think_moves_by_seat[champ_seat], 1), 1),
        # ⚠️ ms_per_move_opp is measured from OUR side and is ~0 by construction: we
        # never time the opponent, we block on a read. The opponent's real cost is
        # what the DRIVER reports, below. Kept for symmetry of shape only.
        "ms_per_move_opp": round(ms_by_seat[opp_seat] / max(think_moves_by_seat[opp_seat], 1), 1),
        #: The opponent's realized cost, as measured by the driver. `*_ms` is wall
        #: milliseconds per TURN (their budget is per turn -- getMeepleMove returns the
        #: move getTileMove already cached), `*_playouts` is rollouts per turn. These
        #: are the figures that price the budget knob and let the thesis's
        #: 42,879 playouts/turn be checked against our hardware.
        "opp_driver_ms_per_turn": (round(sum(opp_drv_ms) / len(opp_drv_ms), 1)
                                   if opp_drv_ms else None),
        "opp_driver_playouts_per_turn": (round(sum(opp_drv_playouts) / len(opp_drv_playouts), 1)
                                         if opp_drv_playouts else None),
        "opp_driver_turns": len(opp_drv_ms),
        "wall_secs": round(time.time() - t_start, 2),
        "moves": move_log,
        "finished_at": time.time(),
    }
    # THE TIE ARBITER's per-game liveness witness — added ONLY on an armed game, so an
    # unarmed record carries no `champ_tiearb` key at all and every prior Carcasum
    # archive's schema (r1, rung 2) is unaffected by this port.
    _ta = _champ_tiearb_telemetry(champ, tiearb)
    if _ta is not None:
        rec["champ_tiearb"] = _ta
    if verify_replay:
        rp = replay_actions(deck_seed, actions, PROFILE)
        rec["replay"] = rp
        rec["replay_ok"] = bool(rp["ok"] and rp["scores"] == our_final)
    rec["manifest"] = build_manifest(
        binary=Path(binary) if binary else _default_binary(),
        tile_mapping_path=TILE_MAPPING_TSV, driver_ready=ready,
        champ_manifest=getattr(champ, "manifest", None), execution=execution,
        sims=sims, k_dets=k_dets, prof=prof, opponent=opponent, audit_mode=audit_mode)
    return rec


class _StopGame(Exception):
    """Internal control-flow signal: setup itself failed (bad `ready` reply).
    Distinct from a mid-game fault so the void/detail set by the setup check
    is not clobbered by the generic exception handler."""


# --------------------------------------------------------------------------- #
# fleet driver                                                                 #
# --------------------------------------------------------------------------- #
_W: dict = {}


def _worker_init(rust_threads: int, sims, k_dets, binary, opponent, audit_mode,
                 tiearb=None) -> None:
    """Spawn-worker bootstrap: env FIRST, then the production leaf, then the engine."""
    export_profile_env(PROFILE)
    for p in (str(HUMAN_ANCHOR), str(JCZ_ORACLE), str(HERE)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import env_preamble                        # noqa: F401  leaf env, before carcassonne_ai
    from carcassonne_ai import rules_profile
    from carcassonne_ai.mirror_protocol import resolve_execution

    rules_profile.activate(PROFILE)
    b = Path(binary) if binary else _default_binary()
    binary_sha256(b)                            # once per worker, before game 1
    node_labels, periods, _ready = load_carcasum_node_labels(b)  # once per worker, not per game
    ex = resolve_execution("rust", rust_threads=rust_threads)
    if not ex.is_rust:
        raise RuntimeError(f"backend did not resolve to rust: {ex.describe()}")
    if tiearb and tiearb.get("enabled"):
        # FAIL FAST, once per worker, BEFORE game 1 — not partway through the arm.
        # Ported from jcz_match/match.py's own `_worker_init` probe: a carc_rs wheel
        # predating the arbiter (or one that silently drops the keyword) must kill the
        # pool here, rather than serve an ARM-ON cell whose champion never actually ran
        # the arbiter — which would read as "the arbiter doesn't transfer" instead of
        # "it never ran" (the J13 failure mode `champion_factory.py`'s own docstring
        # names, and the exact reason `G-CHAMP-ON` exists on the analyzer side too).
        from carcassonne_ai.champion_factory import production_prior_cfg
        from carcassonne_ai.rust_agent import search_config_rs

        resolved = dict(search_config_rs(production_prior_cfg(tiearb=tiearb), 8).tiearb)
        if resolved != dict(tiearb):
            raise RuntimeError(
                f"the resolved rust tiearb knob {resolved} does not match the "
                f"requested {dict(tiearb)} — refusing to play (a mismatch here is "
                "exactly what G-CHAMP-ON exists to catch)")
    _W.update(execution=ex, sims=sims, k_dets=k_dets, binary=binary, opponent=opponent,
              audit_mode=audit_mode, node_labels_by_type=node_labels,
              tile_periods=periods, tiearb=tiearb)


def _play_cell(cell: tuple) -> dict:
    deck_seed, champ_seat, replicate = cell
    try:
        return play_one_match(deck_seed, champ_seat, replicate=replicate,
                              sims=_W["sims"], k_dets=_W["k_dets"], binary=_W["binary"],
                              opponent=_W["opponent"], execution=_W["execution"],
                              audit_mode=_W["audit_mode"],
                              node_labels_by_type=_W["node_labels_by_type"],
                              tile_periods=_W["tile_periods"], tiearb=_W.get("tiearb"))
    except Exception as e:                     # noqa: BLE001 — a cell never kills the fleet
        return {"schema": SCHEMA, "deck_seed": int(deck_seed), "champ_seat": int(champ_seat),
                "replicate": int(replicate), "void": VOID_ERROR,
                "void_detail": {"error": f"{type(e).__name__}: {e}"},
                "actions": [], "counts": {}, "real": {}, "finished_at": time.time()}


def load_done(out_path: Path) -> set[tuple[int, int, int]]:
    """Cells already in the output file (`--resume`). A torn last line is skipped."""
    done: set[tuple[int, int, int]] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "deck_seed" in d and "champ_seat" in d:
                done.add((int(d["deck_seed"]), int(d["champ_seat"]), int(d.get("replicate", 0))))
    return done


def build_cells(seeds, champ_seats, repeats: int, done: set) -> list[tuple]:
    """Replicate-major, then deck-paired: every deck gets BOTH seatings before
    any second replicate, so a killed run is still seat-balanced."""
    cells = []
    for rep in range(max(1, repeats)):
        for s in seeds:
            for cs in champ_seats:
                key = (int(s), int(cs), rep)
                if key not in done:
                    cells.append(key)
    return cells


def summarize(records: list[dict]) -> dict:
    """Raw win rate + the DECK-PAIRED margin (the low-variance statistic).
    Void games are reported, never dropped. Same shape as
    `jcz_match.match.summarize` so `scripts/jcz_match/analyze.py` stays nearly
    reusable."""
    ok = [r for r in records if not r.get("void") and r.get("winner")]
    voids: dict[str, int] = {}
    for r in records:
        if r.get("void"):
            voids[r["void"]] = voids.get(r["void"], 0) + 1
    wins = sum(1 for r in ok if r["winner"] == "champ")
    draws = sum(1 for r in ok if r["winner"] == "draw")
    by_deck: dict[int, dict[int, list[int]]] = {}
    for r in ok:
        by_deck.setdefault(int(r["deck_seed"]), {}).setdefault(
            int(r["champ_seat"]), []).append(int(r["margin_champ_minus_opp"]))
    paired = []
    for seats in by_deck.values():
        if len(seats) == 2:
            paired.append(sum(sum(v) / len(v) for v in seats.values()) / 2.0)
    n = len(ok)
    mean_p = sum(paired) / len(paired) if paired else None
    var = (sum((x - mean_p) ** 2 for x in paired) / (len(paired) - 1)
           if paired and len(paired) > 1 else None)
    return {
        "n_records": len(records), "n_scored": n, "voids": voids,
        "wins": wins, "draws": draws, "losses": n - wins - draws,
        "win_rate": (wins + 0.5 * draws) / n if n else None,
        "n_paired_decks": len(paired),
        "paired_margin_mean": mean_p,
        "paired_margin_sem": (var / len(paired)) ** 0.5 if var is not None else None,
        "mean_margin_unpaired": (sum(r["margin_champ_minus_opp"] for r in ok) / n if n else None),
        "elo_from_win_rate": _wr_to_elo((wins + 0.5 * draws) / n) if n else None,
        # Realized cost, both sides. The champion figure is a THINKING rate (our own
        # timer, denominator = plies we were actually asked about); the opponent
        # figures are the DRIVER's, per TURN. Reported together because a strength
        # number against a budgeted opponent is meaningless without them.
        "champ_ms_per_move_mean": _mean([r.get("ms_per_move_champ") for r in ok]),
        "opp_driver_ms_per_turn_mean": _mean([r.get("opp_driver_ms_per_turn") for r in ok]),
        "opp_driver_playouts_per_turn_mean": _mean(
            [r.get("opp_driver_playouts_per_turn") for r in ok]),
        "wall_secs_per_game_mean": _mean([r.get("wall_secs") for r in ok]),
        "replay_failures": [r.get("deck_seed") for r in records if r.get("replay_ok") is False],
    }


def _mean(xs):
    """Mean of the numeric entries, or None. Never raises on a missing field —
    a record written before a telemetry field existed must not break a readout."""
    vals = [float(x) for x in xs if isinstance(x, (int, float))]
    return round(sum(vals) / len(vals), 1) if vals else None


def _wr_to_elo(wr: float) -> float | None:
    import math

    if wr <= 0.0 or wr >= 1.0:
        return None
    return -400.0 * math.log10(1.0 / wr - 1.0)


def determinism_report(records: list[dict]) -> list[dict]:
    """Per cell, did every replicate produce the IDENTICAL action sequence?
    (Carcasum's own MCTS may sample — reported explicitly, not assumed away.)"""
    by_cell: dict[tuple[int, int], list[dict]] = {}
    for r in records:
        by_cell.setdefault((int(r["deck_seed"]), int(r["champ_seat"])), []).append(r)
    out = []
    for (seed, cs), rs in sorted(by_cell.items()):
        if len(rs) < 2:
            continue
        rs.sort(key=lambda r: r.get("replicate", 0))
        base = rs[0].get("actions") or []
        identical = all((r.get("actions") or []) == base for r in rs[1:])
        first_diff = None
        if not identical:
            for r in rs[1:]:
                a = r.get("actions") or []
                for i in range(max(len(a), len(base))):
                    if i >= len(a) or i >= len(base) or a[i] != base[i]:
                        first_diff = i if first_diff is None else min(first_diff, i)
                        break
        out.append({"deck_seed": seed, "champ_seat": cs, "n_replicates": len(rs),
                    "identical": identical, "first_diff_ply": first_diff,
                    "scores": [r.get("scores") for r in rs]})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--decks", type=int, default=1, help="number of deck seeds")
    ap.add_argument("--seed-base", type=int, default=5_100_000)
    ap.add_argument("--champ-seat", default="both", choices=("both", "0", "1"))
    ap.add_argument("--repeats", type=int, default=1,
                    help="replicates per cell; >1 enables the determinism report")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rust-threads", type=int, default=1)
    ap.add_argument("--sims", type=int, default=None, help="SMOKE ONLY: override sims_per_det")
    ap.add_argument("--k-dets", type=int, default=None, help="SMOKE ONLY: override k_dets")
    ap.add_argument("--binary", default=None, help="carcasum_driver (default: $CARCASUM_DRIVER)")
    ap.add_argument("--opp-kind", default=DEFAULT_OPPONENT["kind"],
                    choices=("mcts", "montecarlo", "montecarlo2", "uct", "simple3", "jcz", "random"))
    ap.add_argument("--opp-budget-ms", type=int, default=None)
    ap.add_argument("--opp-playouts", type=int, default=None)
    ap.add_argument("--audit-mode", default=None, choices=("greedy", "random"),
                    help="rules-coverage GATE, not a strength run: swap the champion "
                         "for a cheap policy (greedy=RuleBasedPlayer, random=uniform) "
                         "so a full match runs fast. Does not change the opponent's "
                         "config by itself — pair with --opp-budget-ms/--opp-playouts.")
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after N cells")
    # --- THE TIE ARBITER, on OUR side (measurement/carcasum_arb_challenge_prep/) ----
    # Named `--champ-tiearb-*` to match `scripts/jcz_match/match.py`'s own convention
    # ("our side is the champ"). OFF by default — explicit arming required, same
    # discipline as `play_harness.py`'s own comment: "the harness flag default is
    # still --tiearb-b 16, so --tiearb-b 64 is REQUIRED" for a real production-shape
    # arm. `_resolve_tiearb` returns None (not a dict with enabled=False) when this
    # flag is absent, so an unarmed run's manifest is byte-identical to every prior
    # Carcasum archive (r1, rung 2).
    ap.add_argument("--champ-tiearb-enabled", action="store_true",
                    help="OUR side only, RUST-ONLY: arm the root tie-arbiter exactly "
                         "as governance/PRODUCTION.yaml fair_deploy.tiearb specifies "
                         "(pass -b/-j/-mode/-salt/-eps to match it explicitly — there "
                         "is no default-on production shape). Leaf hash does NOT "
                         "move; the wiring gates are the record's "
                         "manifest.champion_manifest.cand_tiearb dict and the "
                         "per-game champ_tiearb firing telemetry.")
    ap.add_argument("--champ-tiearb-b", type=int, default=16,
                    help="B: CRN determinizations per fired ply. PRODUCTION.yaml's "
                         "deployed value is 64 — pass it explicitly.")
    ap.add_argument("--champ-tiearb-j", type=int, default=4,
                    help="J: cap on the afterstate-deduped tie set. PRODUCTION.yaml's "
                         "deployed value is 4.")
    ap.add_argument("--champ-tiearb-mode", choices=("argmax", "random"),
                    default="argmax",
                    help="argmax = take the world-mean argmax (PRODUCTION.yaml's "
                         "deployed mode). random = a matched-wall-clock control.")
    ap.add_argument("--champ-tiearb-salt", type=str, default="tiearb2-deploy-v1",
                    help="World/selection seed salt. PRODUCTION.yaml's deployed salt "
                         "is 'tiearb2-deploy-v1'; a different salt is a different "
                         "experiment.")
    ap.add_argument("--champ-tiearb-eps", type=float, default=0.0,
                    help="Tie membership tolerance on the outer chain value. "
                         "PRODUCTION.yaml's deployed value is 0.0 (exact f64 "
                         "equality, not a tolerance).")
    # ⚠️ tiearb_threads (PRODUCTION.yaml's deployed value: 8) is NOT wired here. It is
    # a separate, LATENCY-ONLY rust kwarg (rust/carc/carc-py/src/lib.rs
    # SearchConfig::tiearb_threads, default 1) that `make_production_champion`'s
    # current signature does not expose a path for (verified: no `tiearb_threads`
    # parameter on that function, and neither `jcz_match/match.py` nor
    # `play_harness.py` — the two existing tiearb-arming harnesses — wire it either).
    # Per PRODUCTION.yaml's own gate ("BIT-IDENTICAL by gate... NO strength claim
    # owed"), running at threads=1 (the sequential default) plays the IDENTICAL games
    # a threads=8 run would — only wall-clock differs. This cell therefore runs the
    # arbiter sequentially; the wall-clock projection in DESIGN.md §7 is a floor, not
    # a guarantee, because of this. Flagged for orchestrator review, not a correctness
    # gap.
    args = ap.parse_args(argv)

    binary = Path(args.binary) if args.binary else _default_binary()
    # PREFLIGHT, once, before a single worker forks — same reflex as jcz_match's
    # jar/shim preflight. binary_sha256 raises on a missing/unreadable binary.
    bin_sha = binary_sha256(binary)

    opponent = dict(DEFAULT_OPPONENT, kind=args.opp_kind)
    if args.opp_budget_ms is not None:
        opponent["budget_ms"], opponent["playouts"] = int(args.opp_budget_ms), None
    if args.opp_playouts is not None:
        opponent["playouts"], opponent["budget_ms"] = int(args.opp_playouts), None
    if args.audit_mode and args.opp_budget_ms is None and args.opp_playouts is None:
        opponent["budget_ms"] = 200  # the audit gate wants coverage, not strength

    tiearb = _resolve_tiearb(args)
    if tiearb is not None:
        print(f"[carcasum-match] TIE ARBITER LIVE on OUR side: {tiearb} (leaf hash "
              "does NOT move; gates = the record's manifest cand_tiearb + the "
              "per-game champ_tiearb firing telemetry; tiearb_threads NOT wired, "
              "runs sequentially — latency-only, no strength effect)", flush=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seeds = [args.seed_base + i for i in range(max(1, args.decks))]
    champ_seats = [0, 1] if args.champ_seat == "both" else [int(args.champ_seat)]
    done = load_done(out_path) if args.resume else set()
    cells = build_cells(seeds, champ_seats, args.repeats, done)
    if args.limit:
        cells = cells[: args.limit]

    env = export_profile_env(PROFILE)
    print(f"[carcasum-match] profile={PROFILE} {env} decks={len(seeds)} "
          f"seats={champ_seats} repeats={args.repeats} workers={args.workers} "
          f"audit_mode={args.audit_mode} opponent={opponent} "
          f"done={len(done)} todo={len(cells)}", flush=True)
    print(f"[carcasum-match] binary={binary} sha256={bin_sha} "
          "(PRIMARY provenance witness; vendor git rev is secondary/best-effort)", flush=True)
    if not cells:
        print("[carcasum-match] nothing to do — exiting 0", flush=True)
        return 0

    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    t0 = time.time()
    records: list[dict] = []
    with out_path.open("a") as fh:
        with ctx.Pool(processes=max(1, min(args.workers, len(cells))),
                      initializer=_worker_init,
                      initargs=(args.rust_threads, args.sims, args.k_dets, args.binary,
                                opponent, args.audit_mode, tiearb)) as pool:
            for rec in pool.imap_unordered(_play_cell, cells):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
                records.append(rec)
                print(f"[{len(records)}/{len(cells)}] deck={rec['deck_seed']} "
                      f"champ_seat={rec['champ_seat']} rep={rec.get('replicate')} "
                      f"scores={rec.get('scores')} void={rec.get('void')} "
                      f"champ={rec.get('ms_per_move_champ')}ms/mv "
                      f"opp={rec.get('opp_driver_ms_per_turn')}ms/turn "
                      f"({rec.get('opp_driver_playouts_per_turn')} playouts) "
                      f"replay_ok={rec.get('replay_ok')}", flush=True)

    print(f"\n[carcasum-match] DONE {len(records)} games in {(time.time()-t0)/60:.1f} min")
    print(json.dumps(summarize(records), indent=1))
    if args.repeats > 1:
        print("determinism:", json.dumps(determinism_report(records), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
