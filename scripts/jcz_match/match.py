#!/usr/bin/env python3
"""F9 / D2 — champion vs the JCloisterZone AI: the match driver.

THE POINT. Every strength number this project owns is self-anchored: the champion is
measured against its own lineage, so elo can climb while absolute strength does not
(CLAUDE.md, blocker #1 — "no strong non-saturated reference exists"). JCloisterZone's
AI is an INDEPENDENT implementation of an independent player. This driver plays our
champion against it under rules the two engines are *provably* agreed on, and diffs
the two boards at every ply while doing it, so a win rate can never quietly be a
rules artefact.

## The configuration is not negotiable: ``fixed_v1`` + ``CARCASSONNE_FIX_R9=1``

Leg D of ``measurement/jcz_oracle_20260803/VALIDATION_REPORT.md`` is the only
configuration in which our engine and JCZ are rules-identical: 20/20 games, **exact**
final scores, **zero divergences of any class**. Under any other combination the two
engines genuinely disagree (start-tile meeple, turn loss on an unplaceable tile, and
with R9 off, farm partitions that merge through a city) and a match result would be
partly a rules result.

⚠️ **R9-on is a deliberate deviation from the PRODUCTION default.** R9 is built but
NOT adopted (``rules_profile.fixed_v1`` declares ``r9_env_expected=True``; production
elo is a ``walled``, R9-off number). Running this driver R9-OFF would reintroduce
genuine farm-partition divergences and void the games, so the env var is exported by
the driver before any ``carcassonne_ai`` import and stamped in every manifest
(``rules_manifest.r9_env_ok``). Games from here are NOT comparable to walled elo.

## Who is the game of record

**Our engine is**, exactly as in the oracle's ``replay_one``:

* the champion's chosen action int is applied to OUR board and MIRRORED into JCZ
  through the verified forward map (``to_jcz_position`` / ``jcz_rotation_str`` /
  ``jcz_location_for``);
* the JCZ AI's move arrives as an ``aiMessage`` and is INVERTED onto our action space
  by enumerating OUR legal moves and forward-mapping each one until one matches. There
  is deliberately **no inverse map anywhere in this file** — matching through the map
  that 100/100 mapping rows already certified is the whole point.
* if no legal action of ours matches, the game is ``VOID_UNMAPPABLE`` and the message
  plus our full offered set are recorded verbatim. That is a free rules-fidelity
  finding: JCZ played something our representation cannot express (a wall escape, a
  25x25 action-window escape, or a real bug).

## Every game is also an oracle run

The per-ply legality + score + partition diff of ``replay_diff`` runs on EVERY game
(imported, never copied). Any class in ``replay_diff.REAL`` makes the game
``VOID_DIVERGENT``: recorded with its counts and samples, counted in the report, and
EXCLUDED from the win rate. Void games are never silently dropped.

## Protocol notes that cost time if you rediscover them

* ``%ai`` must precede ``GAME_SETUP``; ``JczEngine.setup`` sends ``GAME_SETUP``.
* A ``Confirm`` LOOKS like plumbing but is not: JCZ's AI player is stateful and holds
  its own message chain for the turn, so confirming the AI's turn from outside leaves
  that chain stale and the next ``%aimove`` returns a ``COMMIT`` that ``TilePhase``
  refuses. ``ack_confirm()`` therefore routes by ACTIVE PLAYER — the AI confirms its
  own turns via ``%aimove``, the driver confirms the champion's.
* JCZ logs to **stdout**, in the middle of the protocol stream, and the continuation
  line of an "Unhandled message" warning is itself valid JSON. ``JczAiEngine._recv``
  keeps only objects carrying a protocol key, and retains the rest as ``log_lines``.
* An unplaceable tile has exactly ONE legal action on our side (the TILES-phase pass)
  and NO ply at all on JCZ's, which redraws internally under A3. The driver detects
  that by legal-set size and advances our board without sending anything.

## Usage

    # gates (this is what must pass before any match volume)
    .venv/bin/python scripts/jcz_match/match.py --decks 1 --champ-seat 0 \\
        --sims 100 --k-dets 2 --out /tmp/gate.jsonl --repeats 2

    # a real match, detached
    setsid nohup nice -n 19 .venv/bin/python scripts/jcz_match/match.py \\
        --decks 50 --champ-seat both --workers 8 \\
        --out measurement/jcz_match/games.jsonl --resume >> driver.log 2>&1 & disown
"""
from __future__ import annotations

# ⚠️ STDLIB ONLY at module level. `carcassonne_ai` must NOT be imported before
# `CARCASSONNE_FIX_R9` is exported (base_deck latches it at import into a Rust
# OnceLock), and this module is re-imported by every spawn worker.
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRIPTS = REPO / "scripts"
JCZ_ORACLE = SCRIPTS / "jcz_oracle"
HUMAN_ANCHOR = SCRIPTS / "human_anchor"

SCHEMA = "carcassonne-jcz-match/v1"

#: NOT a knob. The only rules configuration in which the two engines agree (leg D).
PROFILE = "fixed_v1"

#: Agent-seed base. Cell (deck_seed, champ_seat, replicate) -> a deterministic seed,
#: so a replicate is a genuine re-run of the SAME player, which is what makes the
#: determinism gate meaningful.
SEED_BASE = 9_100_000

#: The retail start tile `fixed_v1` pre-places; asserted against the board, not trusted.
START_TILE_DESC = "city_top_straight_road"

VOID_UNMAPPABLE = "VOID_UNMAPPABLE"
VOID_DIVERGENT = "VOID_DIVERGENT"
VOID_ERROR = "VOID_ERROR"

_RD = None


def agent_seed(deck_seed: int, champ_seat: int, replicate: int = 0) -> int:
    """Deterministic champion seed for a cell.

    ⚠️ ``replicate`` is deliberately NOT in the formula. A replicate is a pure RE-RUN
    of the identical cell — same deck, same seat, same agent seed — because that is
    the only thing that makes the determinism gate mean anything: any difference
    between two replicates is then attributable to the JCZ side (or to us), not to a
    seed we changed ourselves. The parameter is kept so callers can pass it without
    caring, and the value is stamped on every record.
    """
    del replicate
    return SEED_BASE + (int(deck_seed) % 1_000_000) * 8 + int(champ_seat) * 4


# --------------------------------------------------------------------------- #
# lazy imports                                                                 #
# --------------------------------------------------------------------------- #
def export_profile_env(profile: str = PROFILE) -> dict:
    """Export the import-latched env this profile owes (R9). House pattern, REUSED
    from ``scripts/e4_deck_baseline.py`` rather than re-implemented."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from e4_deck_baseline import export_profile_env as _export
    return _export(profile)


def oracle():
    """``scripts/jcz_oracle/replay_diff`` — the differ, imported not copied.

    ⚠️ Two import hazards absorbed here. (1) It imports ``carcassonne_ai``, so it may
    only be imported AFTER ``export_profile_env``. (2) At import time it re-execs
    ITSELF via ``os.execv`` if it sees ``--r9`` anywhere in ``sys.argv`` — harmless
    for its own CLI, fatal for ours — so argv is masked across the import.
    """
    global _RD
    if _RD is None:
        for p in (str(JCZ_ORACLE), str(HERE), str(HUMAN_ANCHOR)):
            if p not in sys.path:
                sys.path.insert(0, p)
        saved = sys.argv[:]
        sys.argv = saved[:1]
        try:
            import replay_diff as RD
        finally:
            sys.argv = saved
        _RD = RD
    return _RD


# --------------------------------------------------------------------------- #
# the inversion: JCZ aiMessage -> OUR action int, THROUGH the forward map        #
# --------------------------------------------------------------------------- #
def invert_tile_message(game, board, tile_map, msg, origin) -> tuple[int | None, dict]:
    """A JCZ tile placement -> our action int (or ``None`` = unmappable).

    Enumerates OUR legal tile actions and forward-maps each through
    ``to_jcz_position`` + ``jcz_rotation_quarters`` — the same two functions the
    oracle used to certify 100/100 mapping rows — and returns the one whose image is
    JCZ's move. Never inverts a coordinate or a rotation by arithmetic.
    """
    from carcassonne_ai import action_space as A
    from ai_engine import message_body, rotation_quarters
    from tile_map import jcz_rotation_quarters, to_jcz_position

    body = message_body(msg)
    pos = body.get("position")
    want_pos = [int(pos[0]), int(pos[1])] if pos is not None else None
    want_rot = rotation_quarters(body.get("rotation"))
    st = board.state
    tile = st.next_tile
    offered = {"jcz_tile": body.get("tileId"), "position": want_pos,
               "rotation_quarters": want_rot,
               "our_tile": tile.description if tile is not None else None}
    if tile is None or want_pos is None or want_rot is None:
        return None, offered
    jcz_id, rot_cw90 = tile_map[tile.description]
    offered["our_tile_as_jcz"] = jcz_id
    if body.get("tileId") not in (None, jcz_id):
        return None, offered          # JCZ placed a tile we do not hold -> deck desync

    valid = game.get_valid_moves(board)
    W = game.window_size
    off = board.offset
    ours: list[list] = []
    for idx in range(A.tile_action_count(W)):
        if not valid[idx]:
            continue
        cell, rot = divmod(idx, A.N_ROTATIONS)
        wr, wc = divmod(cell, W)
        coord = off.to_engine(wr, wc)
        img = (to_jcz_position(coord, *origin), jcz_rotation_quarters(rot, rot_cw90))
        ours.append([img[0], img[1], idx])
        if img[0] == want_pos and img[1] == want_rot:
            return idx, offered
    offered["our_legal_images"] = sorted([p, r] for p, r, _ in ours)
    return None, offered


def invert_meeple_message(game, board, msg) -> tuple[int | None, dict]:
    """A JCZ deploy -> our action int (or ``None`` = unmappable).

    ⚠️ OUR SLOTS ARE FINER THAN JCZ'S (VALIDATION_REPORT §3): a city spanning two
    edges is one JCZ option and two of our slots; a 3-corner field is one option and
    three slots. So the match is NOT unique by construction — every matching slot
    encodes the SAME deploy (same feature, same meeple), and the driver takes the
    first in canonical slot order and records the multiplicity. This is the one place
    the brief's "unique action" is arithmetically impossible; it is an encoding
    difference, not a rules one.
    """
    from carcassonne_ai import action_space as A
    from ai_engine import pointer_of
    from tile_map import jcz_location_for, parse_location

    ptr = pointer_of(msg)
    st = board.state
    coord = st.last_tile_action.coordinate if st.last_tile_action else None
    offered = {"pointer": ptr, "our_last_tile": None}
    if coord is None or ptr.get("location") is None:
        return None, offered
    tile = st.board[coord.row][coord.column]
    offered["our_last_tile"] = tile.description if tile is not None else None
    try:
        want = (ptr.get("feature"), parse_location(ptr["location"]))
    except ValueError as exc:                       # an unparsable JCZ location
        offered["parse_error"] = str(exc)
        return None, offered

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
            got = jcz_location_for(tile, side)
            ours.append([str(side), None if got is None else [got[0], sorted(got[1])]])
            if got == want:
                matches.append(idx)
    offered["our_legal_slots"] = ours
    offered["n_matching_slots"] = len(matches)
    if not matches:
        return None, offered
    return matches[0], offered


def invert_pass(game, board) -> tuple[int | None, dict]:
    """A JCZ pass in its meeple phase -> our meeple-phase pass action int."""
    from carcassonne_ai import action_space as A
    idx = A.meeple_pass_index(game.window_size)
    if game.get_valid_moves(board)[idx]:
        return idx, {}
    return None, {"reason": "meeple-phase pass is not legal for us"}


# --------------------------------------------------------------------------- #
# the archive contract                                                         #
# --------------------------------------------------------------------------- #
def replay_actions(deck_seed: int, actions, profile: str = PROFILE) -> dict:
    """Replay an archived ``(deck_seed, actions)`` pair through OUR engine.

    THE archive contract (``scripts/measurement_infra/root_replay.py``): re-seed
    ``random``, rebuild the same ``Game``, and apply the ints. Returns the final
    scores and a per-ply legality verdict — a record that does not replay is a broken
    archive, and this is the check the replay gate runs on every finished game.
    """
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
            return {"ok": False, "illegal_at": i, "action": a, "scores": None,
                    "n_actions": i}
        board, _ = game.get_next_state(board, a)
    return {"ok": bool(game.get_game_ended(board, 0) != 0),
            "illegal_at": None, "scores": list(board.state.scores),
            "n_actions": len(actions),
            "ended": bool(game.get_game_ended(board, 0) != 0)}


def deck_hash(state) -> str:
    """Order-sensitive digest of the dealt deck (``play_harness.deck_hash``'s rule)."""
    tiles = ([state.next_tile] if state.next_tile is not None else []) + list(state.deck)
    h = hashlib.sha256()
    h.update("\x1f".join(t.description for t in tiles).encode())
    return h.hexdigest()[:16]


def draw_order_for(state, tile_map) -> list[str]:
    """Our dealt deck as JCZ tile ids, in draw order (``ForcedDrawTilePack``).

    Under ``fixed_v1`` the start tile is already ON the board, so everything still to
    come is ``[next_tile] + deck`` — the same construction the oracle's fixed-start
    leg uses, and the reason no RNG matching is needed anywhere.
    """
    upcoming = ([state.next_tile] if state.next_tile is not None else []) + list(state.deck)
    return [tile_map[t.description][0] for t in upcoming]


# --------------------------------------------------------------------------- #
# manifest                                                                     #
# --------------------------------------------------------------------------- #
def _git_rev(repo: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or None
    except Exception:                                        # noqa: BLE001
        return None


def _sha256_file(p: Path) -> str | None:
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    except Exception:                                        # noqa: BLE001
        return None


def build_manifest(*, jar: Path, tiles: Path, ai_class: str, ai_config: dict,
                   champ_manifest, execution, sims, k_dets, prof,
                   ai_classes=None, ai_cmd=None) -> dict:
    """Everything needed to re-run this game, and everything that could explain it."""
    jar = Path(jar)
    jcz_repo = jar.parents[1] if len(jar.parents) > 1 else jar.parent
    return {
        "schema": SCHEMA,
        "our_git_rev": _git_rev(REPO),
        "jcz_git_rev": _git_rev(jcz_repo),
        "jcz_repo": str(jcz_repo),
        "jcz_jar": str(jar),
        "jcz_jar_sha256_16": _sha256_file(jar),
        "jcz_ai_class": ai_class,
        "jcz_ai_classes_dir": None if ai_classes is None else str(ai_classes),
        "jcz_ai_cmd": list(ai_cmd) if ai_cmd else None,
        "jcz_ai_config": dict(ai_config or {}),
        "tiles_xml": str(tiles),
        "tiles_sha256_16": _sha256_file(tiles),
        "tile_set": "basic:2",                    # the JczEngine.setup `sets` key
        "rules_profile": prof.name,
        "rules_manifest": prof.as_manifest(),
        "r9_env": os.environ.get("CARCASSONNE_FIX_R9"),
        # Say it in the artifact, not only in the docstring: this is a deviation from
        # the PRODUCTION default, made because it is the only rules-clean cross-engine
        # configuration (VALIDATION_REPORT leg D).
        "r9_deviation_note": (
            "R9 is ON here and is NOT the PRODUCTION default (built, not adopted). It "
            "is required for a rules-clean cross-engine match: with R9 off our farm "
            "partitions genuinely diverge from JCZ and games would void. Results here "
            "are NOT comparable to walled elo."),
        "champion_manifest": champ_manifest,
        "execution": dict(execution) if execution is not None else None,
        "sims_override": sims, "k_dets_override": k_dets,
    }


# --------------------------------------------------------------------------- #
# the tie arbiter (OUR side)                                                    #
# --------------------------------------------------------------------------- #
def _resolve_tiearb(args) -> dict | None:
    """The ``--champ-tiearb-*`` flags -> the dict ``make_production_champion`` takes,
    or ``None`` when the arbiter was not armed.

    ⚠️ ``None``, not a dict with ``enabled=False``, on the unarmed leg — deliberately
    UNLIKE ``eval_fair_puct``, whose READ_RULE `G-J4` demands an explicit off-record in
    every summary.json. This harness's archive is a per-GAME jsonl with a frozen schema
    (measurement/jcz_match_20260809/confirm.jsonl), so an unarmed run must produce a
    record byte-identical to the pre-arbiter one — CELL A of the two-cell design is the
    plain champion, and it is only a control if nothing about it moved.
    """
    if not bool(getattr(args, "champ_tiearb_enabled", False)):
        return None
    return {"enabled": True,
            "B": int(args.champ_tiearb_b), "J": int(args.champ_tiearb_j),
            "mode": str(args.champ_tiearb_mode), "salt": str(args.champ_tiearb_salt),
            "eps": float(args.champ_tiearb_eps)}


def _champ_tiearb_telemetry(champ, tiearb) -> dict | None:
    """TIE-ARBITER per-game liveness read (OUR side). ``None`` unless this game was
    armed with an ENABLED ``tiearb``; an armed game whose champion is NOT a
    ``RustFairAgent`` is a wiring bug and RAISES rather than stamping ``None`` (the
    arbiter is rust-only, and a silent ``None`` would grade a champion-vs-champion
    null wearing the shape of a real cell — the J13 lesson).

    Field-for-field the same read as ``eval_fair_puct._cand_tiearb_telemetry``, so the
    two harnesses' cells are comparable without a translation table. ``fired_plies`` is
    the numerator of READ_RULE §2's ``phi``; ``pickchanges`` is the §4.3 companion;
    ``secs`` is the arbiter's own share of our clock, reported so the ms/move in this
    record can be ATTRIBUTED rather than inferred.
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
        # `fires` and `fired_plies` are THE SAME NUMBER under two names, on purpose:
        # the adjudicator's `G-FIRE` reads `fires` fail-closed (an absent witness is a
        # FAIL) while `fired_plies` is what the summary blocks aggregate. Emitting one
        # and not the other would void a perfectly good cell on a key spelling.
        "fires": int(s["tiearb_fired_plies"]),
        "fired_plies": int(s["tiearb_fired_plies"]),
        "pickchanges": int(s["tiearb_pickchanges"]),
        "arms_total": int(s["tiearb_arms_total"]),
        "playouts_total": int(s["tiearb_playouts_total"]),
        "secs": float(s["tiearb_secs"]),
        # FAIL-SOFT counter: a tier1 continuation can hit the engine's window refusal
        # or the ply ceiling deep in a determinized world, which falls back to the
        # champion's own pick rather than killing the GAME. Nonzero is REPORTABLE, not
        # fatal, and it must never be invisible.
        "errors": int(s.get("tiearb_errors") or 0),
        "first_error": s.get("tiearb_first_error"),
        # READ_RULE §0.F `G-PLY`: plies that took an argmax over FEWER than B completed
        # worlds. 0 by construction (a playout failure aborts the WHOLE ply, because a
        # partial world set breaks the CRN pairing across arms).
        # ⚠️ Non-zero OR ABSENT => U-UNREADABLE (absent is unknown-not-zero).
        "partial_argmax": int(s.get("tiearb_partial_argmax") or 0),
        "max_plies": int(s.get("tiearb_max_plies") or 0),
        "mode": str(s["tiearb_mode"]),
        "B": int(s["tiearb_b"]), "J": int(s["tiearb_j"]),
    }


# --------------------------------------------------------------------------- #
# one match                                                                    #
# --------------------------------------------------------------------------- #
def play_one_match(deck_seed: int, champ_seat: int, *, replicate: int = 0,
                   sims=None, k_dets=None, jar=None, tiles=None, ai_classes=None,
                   ai_class: str = "com.jcloisterzone.ai.AiEngine",
                   ai_config: dict | None = None, execution=None,
                   verify_replay: bool = True, max_plies: int = 400,
                   tiearb: dict | None = None) -> dict:
    """Play ONE champion-vs-JCZ-AI game. Returns the archive record.

    Lockstep, per ply: compare the legal sets, act on whichever side owns the move,
    mirror/invert it onto the other, then diff scores and the whole feature partition.
    Never raises for a game-level problem — a fault becomes a ``void`` class on the
    record, because a crashed game that vanishes is the one outcome that could bias a
    win rate.
    """
    RD = oracle()
    import random
    from carcassonne_ai import action_space as A
    from carcassonne_ai import mirror_protocol as MP
    from carcassonne_ai import rules_profile
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    from ai_engine import (COMMIT, DEPLOY_MEEPLE, JczAiEngine, JczError, PASS,
                           PLACE_TILE, message_body, message_kind)
    from jcz_driver import (free_meeple_id, is_over, meeple_options,
                            scores as jcz_scores, tile_options, wants_confirm)
    from tile_map import (jcz_location_for, jcz_rotation_quarters, jcz_rotation_str,
                          load_tile_mapping, parse_location, to_jcz_position)

    prof = rules_profile.activate(PROFILE)
    if not prof.as_manifest()["r9_env_ok"]:
        raise RuntimeError(
            "CARCASSONNE_FIX_R9 is not on: this driver is only sound on fixed_v1+R9 "
            "(VALIDATION_REPORT leg D). Export it BEFORE importing carcassonne_ai.")
    tile_map = load_tile_mapping()
    div = RD.Divergences()

    champ_seat = int(champ_seat)
    jcz_seat = 1 - champ_seat
    seed = agent_seed(deck_seed, champ_seat, replicate)

    random.seed(int(deck_seed))                  # the root_replay contract
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    origin = (game.start_row, game.start_col)
    W = game.window_size

    if execution is None:
        from carcassonne_ai.mirror_protocol import resolve_execution
        execution = resolve_execution("rust", rust_threads=1)
    # `tiearb=None` (CELL A, and every pre-arbiter run) passes no arbiter keyword
    # through the factory at all, so the champion — and its manifest, hashes included
    # — is byte-identical to before this plumbing existed.
    champ = make_production_champion("fair", game=game, seed=seed, sims=sims,
                                     k_dets=k_dets, verify=True, tiearb=tiearb,
                                     **execution.factory_kwargs())
    agents = {champ_seat: champ}
    MP.seat(agents, board)                       # mirror: seated once, on the INITIAL board

    st0 = board.state
    dh = deck_hash(st0)
    draw_order = draw_order_for(st0, tile_map)
    start_tile = st0.board[game.start_row][game.start_col]
    start_desc = start_tile.description if start_tile is not None else START_TILE_DESC
    if start_desc != START_TILE_DESC:
        div.add("HARNESS_ERROR", -1, {"unexpected_start_tile": start_desc})
    start_id, start_cw90 = tile_map[start_desc]
    start_deg = jcz_rotation_quarters(0, start_cw90) * 90

    actions: list[int] = []
    move_log: list[dict] = []
    ms_by_seat = {0: 0.0, 1: 0.0}
    moves_by_seat = {0: 0, 1: 0}
    think_moves_by_seat = {0: 0, 1: 0}
    void: str | None = None
    void_detail: dict | None = None
    ai_skipped_kinds: list[str] = []
    t_start = time.time()

    def _apply(a: int, seat: int, ms: float, what: str, extra=None) -> None:
        """The ONE place our board moves: record, advance the board, advance the mirror."""
        nonlocal board
        actions.append(int(a))
        ms_by_seat[seat] += ms
        moves_by_seat[seat] += 1
        if ms > 0.0:
            # ms/move is a THINKING rate, so its denominator counts only plies a
            # player was actually asked about. The synthetic ones — the A3 redraw
            # pass, and the meeple pass we apply when JCZ has no meeple ply — cost
            # nobody anything and would silently deflate the rate by ~10%.
            think_moves_by_seat[seat] += 1
        move_log.append({"ply": len(actions) - 1, "seat": seat, "kind": what,
                         "action": int(a), "ms": round(ms, 2), **(extra or {})})
        board, _ = game.get_next_state(board, int(a))
        MP.advance(agents, int(a))               # every applied action, BOTH seats

    def _void(cls: str, detail: dict) -> None:
        nonlocal void, void_detail
        if void is None:
            void, void_detail = cls, detail

    eng = JczAiEngine(jar=jar, tiles=tiles, ai_classes=ai_classes, main_class=ai_class)
    try:
        eng.ai_seat(jcz_seat)                    # MUST precede GAME_SETUP
        jst = eng.setup(draw_order, start_id, start_deg)

        def jcz_active() -> int | None:
            p = (jst.get("action") or {}).get("player")
            return None if p is None else int(p)

        def ack_confirm() -> None:
            """Answer a pending ``Confirm``, ROUTED BY ACTIVE PLAYER.

            ⚠️ Found the hard way, 2026-08-08: a ``Confirm`` looks like pure plumbing,
            but JCZ's AI player is STATEFUL — it holds its own message chain for the
            turn. Confirming the AI's turn from outside leaves that chain out of sync,
            and the next ``%aimove`` hands back the stale ``COMMIT``, which ``TilePhase``
            then refuses (``MessageNotHandledException``) — 22 plies in, with the JVM
            printing the refusal to STDOUT as a log line. So the AI confirms its own
            turns; the driver only confirms the champion's.
            """
            nonlocal jst
            if jcz_active() == jcz_seat:
                _, jst, sk = eng.ai_decision((COMMIT,))
                ai_skipped_kinds.extend(sk)
            else:
                jst = eng.commit()

        def drain_to_tile_phase(ply: int) -> bool:
            """Answer everything JCZ owes before its next TilePhase. False = stop.

            Our engine only enters MEEPLES when a slot exists; JCZ always runs an
            ActionPhase and always ends a turn with a Confirm. Neither is a decision,
            so the driver answers them — EXCEPT that if JCZ is offering the AI seat
            real meeple options while our board has no meeple ply at all, the legal
            sets have genuinely parted and that is a finding, not plumbing.
            """
            nonlocal jst
            for _ in range(8):
                if is_over(jst) or tile_options(jst)[0] is not None:
                    return True
                if wants_confirm(jst):
                    ack_confirm()
                    continue
                opts = meeple_options(jst)
                if opts:
                    div.add("MEEPLE_LEGALITY", ply, {
                        "ours_only": [], "jcz_only": [[o["feature"], o["location"]]
                                                      for o in opts],
                        "note": "JCZ offered meeple options where our engine has no "
                                "MEEPLES ply"})
                    return False
                if (jst.get("action") or {}).get("canPass"):
                    if jcz_active() == jcz_seat:
                        _, jst, sk = eng.ai_decision((PASS, COMMIT))
                        ai_skipped_kinds.extend(sk)
                    else:
                        jst = eng.pass_()
                    continue
                return True
            div.add("HARNESS_ERROR", ply, "JCZ would not advance to a TilePhase")
            return False

        while game.get_game_ended(board, 0) == 0 and void is None:
            ply = len(actions)
            if ply >= max_plies:
                div.add("HARNESS_ERROR", ply, f"ply cap {max_plies} hit")
                break
            st = board.state
            seat = int(st.current_player)
            phase = st.phase

            # ------------------------------------------------------------- #
            # TILES                                                          #
            # ------------------------------------------------------------- #
            if phase == GamePhase.TILES:
                valid = game.get_valid_moves(board)
                legal = [i for i in range(len(valid)) if valid[i]]
                # A3 redraw: an unplaceable tile is ONE legal action for us (the
                # TILES-phase pass) and NO message at all for JCZ, which redraws
                # internally. Advance our side; say nothing on the wire.
                if legal == [A.tile_pass_index(W)]:
                    div.add("UNPLACEABLE_REDRAW", ply, {
                        "tile": st.next_tile.description if st.next_tile else None})
                    _apply(legal[0], seat, 0.0, "tile_pass_redraw")
                    continue

                if not drain_to_tile_phase(ply):
                    break
                if is_over(jst):
                    div.add("HARNESS_ERROR", ply, "JCZ ended early")
                    break

                j_tile, j_opts = tile_options(jst)
                our_id, our_opts, _ = RD.our_tile_options(game, board, tile_map)
                if j_tile != our_id:
                    div.add("HARNESS_ERROR", ply,
                            {"deck_desync": True, "ours": our_id, "jcz": j_tile})
                    break
                if our_opts != j_opts:
                    extra, missing = our_opts - j_opts, j_opts - our_opts
                    if extra:
                        div.add("LEGALITY_OURS_EXTRA", ply,
                                {"tile": our_id, "extra": sorted(extra)[:8]})
                    if missing:
                        div.add("WALL_LEGALITY", ply,
                                {"tile": our_id, "jcz_only": sorted(missing)[:8],
                                 "n": len(missing)})
                jp = jcz_active()
                if jp is not None and jp != seat:
                    div.add("SEAT_DESYNC", ply, {"ours": seat, "jcz": jp})
                    break

                if seat == champ_seat:
                    t0 = time.perf_counter()
                    a = int(champ.choose_action(board))
                    ms = (time.perf_counter() - t0) * 1000.0
                    decoded = game._decode_for(st, board.offset, a)
                    rot_cw90 = tile_map[st.next_tile.description][1]
                    try:
                        jst = eng.place_tile(
                            tile_map[st.next_tile.description][0],
                            jcz_rotation_str(decoded.tile_rotations, rot_cw90),
                            to_jcz_position(decoded.coordinate, *origin))
                    except JczError as e:
                        div.add("JCZ_REJECT", ply, str(e)[:300])
                        break
                    _apply(a, seat, ms, "champ_tile")
                else:
                    t0 = time.perf_counter()
                    try:
                        msg, jst, sk = eng.ai_decision((PLACE_TILE,))
                    except JczError as e:
                        _void(VOID_ERROR, {"ply": ply, "error": str(e)[:400]})
                        break
                    ms = (time.perf_counter() - t0) * 1000.0
                    ai_skipped_kinds.extend(sk)
                    a, offered = invert_tile_message(game, board, tile_map, msg, origin)
                    if a is None:
                        _void(VOID_UNMAPPABLE, {"ply": ply, "phase": "tiles",
                                                "ai_message": msg, "ours": offered})
                        break
                    _apply(a, seat, ms, "jcz_tile", {"jcz_message": message_body(msg)})

                RD._diff_partitions(div, ply, board.state, origin, jst)
                RD._diff_scores(div, ply, board.state, jst, 0, [])
                continue

            # ------------------------------------------------------------- #
            # MEEPLES                                                        #
            # ------------------------------------------------------------- #
            if phase == GamePhase.MEEPLES:
                our_keys, unmapped = RD.our_meeple_options(game, board)
                if unmapped:
                    div.add("MEEPLE_SLOT_UNMAPPED", ply,
                            {"legal_slots_with_no_jcz_feature": [str(s) for s in unmapped]})
                j_keys = RD.jcz_meeple_keys(jst)
                if our_keys != j_keys:
                    div.add(RD._meeple_class(our_keys - j_keys, j_keys - our_keys,
                                             None, True), ply, {
                        "ours_only": sorted((f, sorted(t)) for f, t in our_keys - j_keys),
                        "jcz_only": sorted((f, sorted(t)) for f, t in j_keys - our_keys)})
                jp = jcz_active()
                if jp is not None and jp != seat:
                    div.add("SEAT_DESYNC", ply, {"ours": seat, "jcz": jp})
                    break

                if seat == champ_seat:
                    t0 = time.perf_counter()
                    a = int(champ.choose_action(board))
                    ms = (time.perf_counter() - t0) * 1000.0
                    decoded = game._decode_for(st, board.offset, a)
                    if isinstance(decoded, PassAction):
                        if not wants_confirm(jst) and (jst.get("action") or {}).get("canPass"):
                            jst = eng.pass_()
                        _apply(a, seat, ms, "champ_meeple_pass")
                    else:
                        cws = decoded.coordinate_with_side
                        want = jcz_location_for(
                            st.board[cws.coordinate.row][cws.coordinate.column], cws.side)
                        opt = next((o for o in meeple_options(jst)
                                    if want and (o["feature"],
                                                 parse_location(o["location"])) == want), None)
                        if opt is None:
                            # We would spend a follower JCZ has no option for: the two
                            # supplies would part company here. Void rather than play on.
                            div.add("MEEPLE_DEPLOY_UNMIRRORED", ply, {
                                "side": str(cws.side),
                                "wanted": [want[0], sorted(want[1])] if want else None,
                                "jcz_offered": [[o["feature"], o["location"]]
                                                for o in meeple_options(jst)]})
                            _void(VOID_DIVERGENT, {"ply": ply,
                                                   "cause": "MEEPLE_DEPLOY_UNMIRRORED"})
                            break
                        mid = free_meeple_id(jst, seat)
                        if mid is None:
                            div.add("HARNESS_ERROR", ply, "JCZ has no free follower")
                            break
                        try:
                            jst = eng.deploy_meeple(opt, mid)
                        except JczError as e:
                            div.add("JCZ_REJECT", ply, str(e)[:300])
                            break
                        _apply(a, seat, ms, "champ_meeple")
                elif wants_confirm(jst):
                    # JCZ SKIPPED its ActionPhase (no meeple option on that tile) and
                    # is already asking to confirm, while our engine still owes a
                    # pass-only MEEPLES ply. Symmetric to the champion branch, which
                    # likewise withholds its PASS when JCZ wants a confirm. Asking the
                    # AI here would pull its end-of-turn COMMIT forward and desync its
                    # chain — the failure this cost 51 plies to find.
                    a, offered = invert_pass(game, board)
                    if a is None:
                        _void(VOID_UNMAPPABLE, {"ply": ply, "phase": "meeples",
                                                "ai_message": None, "ours": offered,
                                                "note": "JCZ has no meeple ply; our "
                                                        "meeple-phase pass is illegal"})
                        break
                    _apply(a, seat, 0.0, "jcz_meeple_pass_implicit")
                else:
                    t0 = time.perf_counter()
                    try:
                        msg, jst, sk = eng.ai_decision((DEPLOY_MEEPLE, PASS))
                    except JczError as e:
                        _void(VOID_ERROR, {"ply": ply, "error": str(e)[:400]})
                        break
                    ms = (time.perf_counter() - t0) * 1000.0
                    ai_skipped_kinds.extend(sk)
                    kind = message_kind(msg)
                    if kind == PASS:
                        a, offered = invert_pass(game, board)
                        what = "jcz_meeple_pass"
                    else:
                        a, offered = invert_meeple_message(game, board, msg)
                        what = "jcz_meeple"
                    if a is None:
                        _void(VOID_UNMAPPABLE, {"ply": ply, "phase": "meeples",
                                                "ai_message": msg, "ours": offered})
                        break
                    _apply(a, seat, ms, what, {"jcz_message": message_body(msg),
                                               "n_matching_slots":
                                                   offered.get("n_matching_slots")})
                if wants_confirm(jst):
                    ack_confirm()

                RD._diff_partitions(div, ply, board.state, origin, jst)
                RD._diff_scores(div, ply, board.state, jst, 0, [])
                continue

            div.add("HARNESS_ERROR", ply, f"unexpected phase {phase}")
            break

        # --- terminal ------------------------------------------------------ #
        # Drain JCZ's last Confirm so its terminal scoring runs — but NOT after a void:
        # once the two boards have parted, driving JCZ further only manufactures a
        # second, derivative error on top of the one worth reporting.
        for _ in range(8):
            if void is not None or not wants_confirm(jst) or is_over(jst):
                break
            ack_confirm()
        our_final = list(board.state.scores)
        jcz_final = jcz_scores(jst)
        ended = bool(game.get_game_ended(board, 0) != 0)
        agree = (our_final == jcz_final) if ended else None
        if ended and not agree:
            causes = sorted(RD.SCORE_MOVING & set(div.counts))
            div.add("SCORE_FINAL_EXPLAINED" if causes else "SCORE_FINAL", -1,
                    {"ours": our_final, "jcz": jcz_final, "classified_causes": causes})
        # A running-score gap that reconciles by the terminal is the A2 timing class;
        # one that does not is part of the final gap. (`fixed_v1` should have neither.)
        n_running = div.counts.pop("SCORE_RUNNING", 0)
        if n_running:
            dest = "SCORE_TIMING" if agree else "SCORE_FINAL"
            div.counts[dest] += n_running
            div.samples.setdefault(dest, []).extend(div.samples.pop("SCORE_RUNNING", [])[:3])
    except Exception as e:                       # noqa: BLE001 — a fault is a CLASS, not a crash
        div.add("HARNESS_ERROR", -1, f"{type(e).__name__}: {e}")
        _void(VOID_ERROR, {"error": f"{type(e).__name__}: {e}"})
        our_final, jcz_final, ended, agree = list(board.state.scores), None, False, None
    finally:
        eng.close()

    real = dict(div.real())
    if void is None and real:
        _void(VOID_DIVERGENT, {"real": real})
    if void is None and not ended:
        _void(VOID_ERROR, {"error": "game did not reach a terminal state"})

    champ_score = our_final[champ_seat] if our_final else None
    jcz_score = our_final[jcz_seat] if our_final else None
    rec = {
        "schema": SCHEMA,
        "deck_seed": int(deck_seed), "champ_seat": champ_seat, "jcz_seat": jcz_seat,
        "replicate": int(replicate), "agent_seed": seed,
        # THE root_replay contract: these ints replay through our engine under PROFILE.
        "actions": actions, "n_actions": len(actions),
        "deck_hash": dh,
        "scores": our_final, "jcz_reported_scores": jcz_final, "final_agree": agree,
        "champ_score": champ_score, "jcz_score": jcz_score,
        "margin_champ_minus_jcz": (None if champ_score is None
                                   else int(champ_score) - int(jcz_score)),
        "winner": (None if champ_score is None else
                   "champ" if champ_score > jcz_score else
                   "jcz" if jcz_score > champ_score else "draw"),
        "void": void, "void_detail": void_detail,
        "counts": dict(div.counts), "real": real, "samples": div.samples,
        "ai_absorbed_kinds": ai_skipped_kinds,
        "ms_by_seat": {str(k): round(v, 1) for k, v in ms_by_seat.items()},
        "moves_by_seat": {str(k): v for k, v in moves_by_seat.items()},
        "think_moves_by_seat": {str(k): v for k, v in think_moves_by_seat.items()},
        "ms_per_move_champ": round(
            ms_by_seat[champ_seat] / max(think_moves_by_seat[champ_seat], 1), 1),
        "ms_per_move_jcz": round(
            ms_by_seat[jcz_seat] / max(think_moves_by_seat[jcz_seat], 1), 1),
        "wall_secs": round(time.time() - t_start, 2),
        "moves": move_log,
        "finished_at": time.time(),
    }
    # THE TIE ARBITER's per-game liveness witness — added ONLY on an armed game, so an
    # unarmed record carries no `champ_tiearb` key at all and the frozen archive schema
    # (measurement/jcz_match_20260809/confirm.jsonl) still parses unchanged. A `null`
    # here would be a schema change AND an ambiguity (absent vs. off vs. never-ran).
    _ta = _champ_tiearb_telemetry(champ, tiearb)
    if _ta is not None:
        rec["champ_tiearb"] = _ta
    if verify_replay:
        # THE REPLAY GATE, run on every game: the archived ints must reproduce this
        # exact game through our engine alone.
        rp = replay_actions(deck_seed, actions, PROFILE)
        rec["replay"] = rp
        rec["replay_ok"] = bool(rp["ok"] and rp["scores"] == our_final)
    rec["manifest"] = build_manifest(
        jar=Path(jar) if jar else _default_jar(), tiles=_tiles_path(tiles),
        ai_class=ai_class, ai_classes=eng.ai_classes, ai_cmd=list(eng.cmd),
        ai_config=ai_config or {},
        champ_manifest=getattr(champ, "manifest", None), execution=execution,
        sims=sims, k_dets=k_dets, prof=prof)
    return rec


def _default_jar() -> Path:
    from jcz_driver import DEFAULT_JAR
    return Path(os.environ.get("JCZ_JAR", DEFAULT_JAR))


def _tiles_path(tiles) -> Path:
    if tiles:
        return Path(tiles)
    from jcz_driver import DEFAULT_TILES
    return Path(DEFAULT_TILES)


# --------------------------------------------------------------------------- #
# fleet driver                                                                 #
# --------------------------------------------------------------------------- #
_W: dict = {}


def _worker_init(rust_threads: int, sims, k_dets, jar, tiles, ai_classes, ai_class,
                 ai_config, tiearb=None) -> None:
    """Spawn-worker bootstrap: env FIRST, then the production leaf, then the engine."""
    export_profile_env(PROFILE)
    for p in (str(HUMAN_ANCHOR), str(JCZ_ORACLE), str(HERE)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import env_preamble                       # noqa: F401  leaf env, before carcassonne_ai
    from carcassonne_ai import rules_profile
    from carcassonne_ai.mirror_protocol import resolve_execution

    rules_profile.activate(PROFILE)
    ex = resolve_execution("rust", rust_threads=rust_threads)
    if not ex.is_rust:
        raise RuntimeError(f"backend did not resolve to rust: {ex.describe()}")
    if tiearb and tiearb.get("enabled"):
        # FAIL FAST, once per worker, BEFORE game 1 — not 20 minutes into it. The
        # parent cannot do this probe: it must not import carcassonne_ai (the R9 env
        # latches into a Rust OnceLock at engine import, which is the whole reason this
        # bootstrap exists), so the earliest honest place is here. A carc_rs wheel
        # predating the arbiter raises TypeError on the keyword and kills the pool,
        # rather than serving a silently arbiter-free champion — which would read as
        # "terminal grounding at ties is worth nothing against JCZ" instead of "it
        # never ran" (the J13 failure mode).
        from carcassonne_ai.champion_factory import production_prior_cfg
        from carcassonne_ai.rust_agent import search_config_rs

        resolved = dict(search_config_rs(production_prior_cfg(tiearb=tiearb), 8).tiearb)
        if resolved != dict(tiearb):
            raise RuntimeError(
                f"the resolved rust tiearb knob {resolved} does not match the "
                f"requested {dict(tiearb)} — refusing to play (a mismatch here is "
                "exactly what READ_RULE G-J4 exists to catch)")
    _W.update(execution=ex, sims=sims, k_dets=k_dets, jar=jar, tiles=tiles,
              ai_classes=ai_classes, ai_class=ai_class, ai_config=ai_config,
              tiearb=tiearb)


def _play_cell(cell: tuple) -> dict:
    deck_seed, champ_seat, replicate = cell
    try:
        return play_one_match(deck_seed, champ_seat, replicate=replicate,
                              sims=_W["sims"], k_dets=_W["k_dets"], jar=_W["jar"],
                              tiles=_W["tiles"], ai_classes=_W["ai_classes"],
                              ai_class=_W["ai_class"], ai_config=_W["ai_config"],
                              execution=_W["execution"], tiearb=_W.get("tiearb"))
    except Exception as e:                     # noqa: BLE001 — a cell never kills the fleet
        return {"schema": SCHEMA, "deck_seed": int(deck_seed),
                "champ_seat": int(champ_seat), "replicate": int(replicate),
                "void": VOID_ERROR, "void_detail": {"error": f"{type(e).__name__}: {e}"},
                "actions": [], "counts": {}, "real": {}, "finished_at": time.time()}


def load_done(out_path: Path) -> set[tuple[int, int, int]]:
    """Cells already in the output file (``--resume``). A torn last line is skipped."""
    done: set[tuple[int, int, int]] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:       # a torn last line from a dirty crash
                continue
            if "deck_seed" in d and "champ_seat" in d:
                done.add((int(d["deck_seed"]), int(d["champ_seat"]),
                          int(d.get("replicate", 0))))
    return done


def build_cells(seeds, champ_seats, repeats: int, done: set) -> list[tuple]:
    """Replicate-major, then deck-paired: every deck gets BOTH seatings before any
    second replicate, so a killed run is still seat-balanced."""
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

    Paired = per deck, the mean of ``champ_score - jcz_score`` over the two seatings;
    only decks with both seatings scored (and neither void) contribute. Void games are
    reported, never dropped.
    """
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
            int(r["champ_seat"]), []).append(int(r["margin_champ_minus_jcz"]))
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
        "paired_margin_sem": ((var / len(paired)) ** 0.5
                              if var is not None else None),
        "mean_margin_unpaired": (sum(r["margin_champ_minus_jcz"] for r in ok) / n
                                 if n else None),
        "replay_failures": [r.get("deck_seed") for r in records
                            if r.get("replay_ok") is False],
    }


def determinism_report(records: list[dict]) -> list[dict]:
    """Per cell, did every replicate produce the IDENTICAL action sequence?

    A stochastic JCZ AI is a real possibility (JCZ's own AI samples), so this is
    reported explicitly rather than assumed away.
    """
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
    ap.add_argument("--seed-base", type=int, default=4_100_000)
    ap.add_argument("--champ-seat", default="both", choices=("both", "0", "1"))
    ap.add_argument("--repeats", type=int, default=1,
                    help="replicates per cell; >1 enables the determinism report")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rust-threads", type=int, default=1)
    ap.add_argument("--sims", type=int, default=None, help="SMOKE ONLY: override sims_per_det")
    ap.add_argument("--k-dets", type=int, default=None, help="SMOKE ONLY: override k_dets")
    ap.add_argument("--jar", default=None, help="JCZ Engine.jar (default: $JCZ_JAR)")
    ap.add_argument("--ai-classes", default=None,
                    help="directory of compiled AiEngine classes; prepended to -cp")
    ap.add_argument("--tiles", default=None, help="tiles xml (default: the spike's)")
    ap.add_argument("--ai-class", default="com.jcloisterzone.ai.AiEngine")
    ap.add_argument("--ai-config", default="{}", help="JSON, stamped in the manifest")
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after N cells")
    # --- THE TIE ARBITER, on OUR side (measurement/tiearb2_stage2_20260817) -----
    # Named `--champ-tiearb-*` because in THIS harness our side is the "champ"; the
    # knobs and their defaults are otherwise eval_fair_puct's `--cand-tiearb-*`
    # verbatim, so the two-cell design here is the same surface graded out of
    # lineage: CELL A = plain champion vs JCZ, CELL B = champion+arbiter vs JCZ.
    ap.add_argument("--champ-tiearb-enabled", action="store_true",
                    help="OUR side only, RUST-ONLY: re-decide an exactly-tied TILE "
                         "ply with terminal-grounded `tier1-greedy` playouts. The "
                         "trigger is the CORPUS predicate: TILES phase, own seat, "
                         "n_legal>=2, and >=2 legal tile actions sharing the top "
                         "OUTER CHAIN value at EXACT f64 equality. ⚠️ The leaf hash "
                         "does NOT move, so the wiring gates are the record's "
                         "manifest.champion_manifest.cand_tiearb dict (G-J4) and the "
                         "per-game champ_tiearb firing telemetry (G-FIRE).")
    ap.add_argument("--champ-tiearb-b", type=int, default=16,
                    help="B: CRN determinizations per fired ply, SHARED by every arm "
                         "(16 = the funded rung). READ_RULE G-J4 voids at B != 16.")
    ap.add_argument("--champ-tiearb-j", type=int, default=4,
                    help="J: the cap on the afterstate-deduped tie set, applied by a "
                         "SEEDED DRAW (never index truncation); the champion's own "
                         "pooled_q_argmax pick is appended when the cap excluded it. "
                         "READ_RULE G-J4 voids at J != 4.")
    ap.add_argument("--champ-tiearb-mode", choices=("argmax", "random"),
                    default="argmax",
                    help="argmax = the ARB cell (take the world-mean argmax). "
                         "random = the RND cell: run the IDENTICAL playouts, DISCARD "
                         "the values, and return a seeded draw over the same arm set "
                         "— the matched-wall-clock control.")
    ap.add_argument("--champ-tiearb-salt", type=str, default="tiearb2-deploy-v1",
                    help="World/selection seed salt. The salt of record is "
                         "'tiearb2-deploy-v1'; a different salt is a different "
                         "experiment.")
    ap.add_argument("--champ-tiearb-eps", type=float, default=0.0,
                    help="Tie membership tolerance on the outer chain value. 0.0 is "
                         "the COMMITTED setting — exact f64 equality, NOT a tolerance.")
    args = ap.parse_args(argv)

    # The AI build is launched as `java -cp <Engine.jar>:<ai_classes> <ai_class>` —
    # see `JczAiEngine._launch_cmd`. Exported too, so a worker that is handed nothing
    # still finds it (the env is the spawn-safe channel, as with the rules profile).
    # PREFLIGHT, not a worker-time discovery: without the shim every `%aimove` is an
    # unknown directive that JCZ answers with silence, so the fleet hangs rather than
    # failing (this is exactly how the 2026-08-09 smoke was lost). Resolve and CHECK
    # here, once, before a single worker forks.
    from ai_engine import JczAiEngine
    ai_classes = str(Path(args.ai_classes).resolve()) if args.ai_classes else str(
        Path(os.environ.get("JCZ_AI_CLASSES") or JczAiEngine.DEFAULT_AI_CLASSES))
    if not Path(ai_classes).is_dir():
        ap.error(f"JCZ AI shim classes not found at {ai_classes} — run "
                 "scripts/jcz_match/build_ai_shim.sh (or pass --ai-classes)")
    os.environ["JCZ_AI_CLASSES"] = ai_classes

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seeds = [args.seed_base + i for i in range(max(1, args.decks))]
    champ_seats = [0, 1] if args.champ_seat == "both" else [int(args.champ_seat)]
    done = load_done(out_path) if args.resume else set()
    cells = build_cells(seeds, champ_seats, args.repeats, done)
    if args.limit:
        cells = cells[: args.limit]

    tiearb = _resolve_tiearb(args)

    env = export_profile_env(PROFILE)           # inherited by every spawn worker
    print(f"[jcz-match] profile={PROFILE} {env} decks={len(seeds)} "
          f"seats={champ_seats} repeats={args.repeats} workers={args.workers} "
          f"done={len(done)} todo={len(cells)}", flush=True)
    if tiearb is not None:
        # The rust-wheel probe runs in each worker's `_worker_init` (the parent must
        # not import carcassonne_ai — the R9 env latches at engine import).
        print(f"[jcz-match] TIE ARBITER LIVE on OUR side: {tiearb} (leaf hash does "
              "NOT move; gates = the record's manifest cand_tiearb + the per-game "
              "champ_tiearb firing telemetry)", flush=True)
    if not cells:
        print("[jcz-match] nothing to do — exiting 0", flush=True)
        return 0

    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    t0 = time.time()
    records: list[dict] = []
    with out_path.open("a") as fh:
        with ctx.Pool(processes=max(1, min(args.workers, len(cells))),
                      initializer=_worker_init,
                      initargs=(args.rust_threads, args.sims, args.k_dets, args.jar,
                                args.tiles, ai_classes, args.ai_class,
                                json.loads(args.ai_config), tiearb)) as pool:
            for rec in pool.imap_unordered(_play_cell, cells):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                os.fsync(fh.fileno())           # per-GAME checkpoint (dirty-reboot safe)
                records.append(rec)
                print(f"[{len(records)}/{len(cells)}] deck={rec['deck_seed']} "
                      f"champ_seat={rec['champ_seat']} rep={rec.get('replicate')} "
                      f"scores={rec.get('scores')} void={rec.get('void')} "
                      f"champ={rec.get('ms_per_move_champ')}ms/mv "
                      f"jcz={rec.get('ms_per_move_jcz')}ms/mv "
                      f"replay_ok={rec.get('replay_ok')}", flush=True)

    print(f"\n[jcz-match] DONE {len(records)} games in {(time.time()-t0)/60:.1f} min")
    print(json.dumps(summarize(records), indent=1))
    if args.repeats > 1:
        print("determinism:", json.dumps(determinism_report(records), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
