#!/usr/bin/env python3
"""The phone REMOTE-OPPONENT server — Carcasum@5000ms, over the tailnet.

WHY THIS EXISTS. `measurement/carcasum_owner_session_prep/PROTOCOL.md` needs the
owner to play the CALIBRATED Carcasum opponent (MCTS / Portion / Random /
5000 ms / Cp 0.5, the PATCHED build) under **his normal phone conditions** — the
same app, the same board UI, the same archive. Building a Qt GUI session on a
laptop changes the conditions; porting Carcasum to Android is not on the table.
So the phone forwards each opponent move over the tailnet to this daemon, which
wraps the EXISTING engine-vs-engine bridge and hands the move back.

## What is reused, and why that matters more than it looks

**Everything about the game.** `scripts/carcasum_match/match.py` already owns the
whole correspondence between our engine and Carcasum: the 145x145/offset-72
coordinate frame taken live from the handshake, the rotation-period reduction,
the meeple half-edge label rotation, the forward-map-and-match inversion
discipline (there is no inverse map anywhere), the void taxonomy, the per-ply and
farm score diffing. This file re-implements NONE of it: it injects an agent and a
per-ply callback into `play_one_match` (the two additive parameters `agent=` /
`on_apply=`) and otherwise stays out of the way. A second inverter would be a
second thing that can silently disagree with our engine about what a Carcasum
move means, and that disagreement would arrive dressed as a rules finding.

## The protocol, and the one honest limit

Requests are **stateless per move**: every `POST /move` carries the FULL
`(deck_seed, actions)` root-replay pair — the same lossless representation the
phone archives already use. So a dropped connection, a backgrounded app, a phone
that sleeps mid-search: the client just re-sends, and the server answers from the
authoritative log it already holds. Retry is idempotent by construction (see
`_Session.next_action`), which is the property that makes "network failure must
never corrupt a game" true rather than aspirational.

⚠️ **The limit, stated plainly: a Carcasum game cannot be RECONSTRUCTED from the
log.** Carcasum's RNG seed is compile-time only (`static.h RANDOM_SEED`), and the
driver protocol has no way to force the internal player's move — `new_game` takes
a forced *deck*, never a forced *history*. So replaying `(deck_seed, actions)`
into a FRESH Carcasum process would produce a different opponent from the one
that actually played. The server therefore keeps the live driver session for the
duration of a game and treats the client's log as a CONSISTENCY KEY, not as a
reconstruction recipe. Consequence: if this daemon dies mid-game, that game is
gone — the client is told so explicitly (`session_lost`), and the protocol's
answer is to log it as `abandoned` per PROTOCOL.md §3, never to silently start a
second opponent inside one game. Fixing this properly means teaching the C++
driver to load a `MoveHistory`, which would change the binary and therefore break
the `G-BINARY` anchor identity — deliberately not done.

## Gates it refuses to start without (PROTOCOL.md §7 `G-BINARY`)

1. **sha256 of the binary** == the anchor binary named in the prep's provenance
   table (`--expect-sha`, default `ANCHOR_SHA256`; `--allow-any-binary` to
   override, which stamps `binary_gate: "OVERRIDDEN"` into every response and the
   health endpoint so a session played against an unvetted build can never be
   mistaken for an anchored one).
2. **A live scoring probe**: a constructed plain two-tile city must score **4**,
   not upstream's original-2000 **2**. Same construction as
   `tests/test_carcasum_rules_patch.py::test_plain_two_tile_city_scores_four_not_two`
   — a patch that compiles is not a patch that is live in the binary.

Both run at startup, before the socket is bound. A failure exits non-zero.

## Security posture

**None beyond the tailnet.** The server binds the tailnet address you give it and
speaks plain HTTP with no auth. That is a deliberate choice for a private
tailnet between two of the owner's own devices, and it is why `--host` has no
default of `0.0.0.0`: pointing this at a public interface would expose an
unauthenticated endpoint that spawns processes. Don't.

## Launch (laptop, the box the anchor was measured on)

    ssh laptop-wsl 'bash -s' < scripts/carcasum_remote/launch_laptop.sh

which is the `systemd-run --user --scope` + linger recipe — see that script and
`scripts/carcasum_remote/README.md`.

Endpoints
---------
    GET  /health                      liveness + gate state + session census
    GET  /sessions                    one line per live session
    POST /move    {game_id, deck_seed, human_seat, actions:[...], opponent?}
                                   -> {action, seat, index} | {game_over, scores}
    POST /end     {game_id}           tear the session down, return the record
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

#: The binary named in the T-TRANSFER provenance table and re-verified on the
#: laptop by `measurement/carcasum_owner_session_prep/SETUP.md` §2. This is an
#: IDENTITY, not a version floor: a different hash means a different opponent,
#: and the session's `B` anchor (champion - Carcasum) was measured against THIS
#: one. Never "update" it to whatever is on disk.
ANCHOR_SHA256 = "c090847e1befa007e9b3b3031a9c880a60915e36f143aa6c3c30691599792968"

#: Carcasum tileTypes used by the R1 scoring probe (from TILE_MAPPING.tsv, and
#: named here exactly as `tests/test_carcasum_rules_patch.py` names them).
T_RCR = 2    # the start tile: city N, roads W/E, field S
T_C = 17     # "C" / CFFF: city on N only

SCHEMA = "carcassonne-carcasum-remote/v1"

#: The archive label this server's games must carry. The phone stamps it into
#: `opponent`; `scripts/e4_archives.py` excludes anything that is not exactly
#: `"champion"` from the E4 champion anchor. Both halves are needed: the label
#: alone protects nothing if the readers do not condition on it.
OPPONENT_LABEL = "carcasum_remote_5000ms"

_MATCH = None


def match_module():
    """`scripts/carcasum_match/match.py`, imported once, R9-latched first.

    The env preamble MUST run before anything imports `carcassonne_ai` (R9 is
    latched at import, into a Rust `OnceLock`), and `match.py` already owns the
    "which env does this profile owe" question — so we call its exporter rather
    than re-deriving it. One import point, so a test and the daemon cannot end up
    holding two different `match` modules.
    """
    global _MATCH
    if _MATCH is None:
        for p in (SCRIPTS, SCRIPTS / "carcasum_match"):
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
        import match as _m                                        # noqa: PLC0415

        _m.export_profile_env()
        _MATCH = _m
    return _MATCH


# --------------------------------------------------------------------------- #
# gates                                                                        #
# --------------------------------------------------------------------------- #
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _mapping_pool() -> list[int]:
    """The 72-tile pack as Carcasum tileTypes, from the committed mapping."""
    import csv

    path = REPO / "tests" / "data" / "carcasum" / "TILE_MAPPING.tsv"
    with path.open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    pool: list[int] = []
    for r in rows:
        pool += [int(r["carcasum_tile_type"])] * int(r["deck_count"])
    if len(pool) != 72:
        raise RuntimeError(f"TILE_MAPPING.tsv deck_count sums to {len(pool)}, expected 72")
    return pool


def probe_tiny_city_scores_four(binary: Path, *, budget_ms: int = 20) -> dict:
    """PROTOCOL.md §7 `G-BINARY`, observed live in THIS binary.

    Upstream Carcasum keeps the original-2000 exception and scores a completed
    plain two-tile city **2**; patch R1 (`vendor/carcasum/CARCASUM_PATCHES.md`)
    makes it **4**, which is what `fixed_v1` and every modern edition say. A
    session played against an unpatched build is "a rules result wearing a
    strength result's costume" (`RULES_DELTA.md` §2.1) and is unreadable against
    the anchor, so this runs before the socket is bound.

    Deliberately speaks the protocol itself rather than going through
    `CarcasumDriver` — this checks the BINARY, and routing it through the
    production harness would let a harness bug mask a rules bug. Same reasoning,
    same construction and same tile ids as
    `tests/test_carcasum_rules_patch.py`, which is the source of truth for it.
    """
    pool = _mapping_pool()
    pool.remove(T_RCR)          # consumed by setStartTile before any ply
    pool.remove(T_C)
    deck = [T_C] + pool
    p = subprocess.Popen(                                        # noqa: S603
        [str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def send(o):
        p.stdin.write(json.dumps(o) + "\n")
        p.stdin.flush()

    def recv():
        line = p.stdout.readline()
        if not line:
            raise RuntimeError("driver closed stdout during the R1 scoring probe")
        return json.loads(line)

    try:
        send({"t": "new_game", "deck": deck, "external_seat": 0,
              "opponent": {"kind": "mcts", "budget_ms": budget_ms, "cp": 0.5},
              "seed": 1})
        ready = recv()
        if ready.get("t") != "ready":
            raise RuntimeError(f"probe handshake failed: {ready!r}")
        bs, sxy = int(ready["board_size"]), list(ready["start_xy"])
        if bs % 2 != 1 or sxy != [bs // 2, bs // 2]:
            raise RuntimeError(f"probe: incoherent coordinate frame {bs} / {sxy}")
        ox, oy = sxy
        target = [ox, oy - 1, 2]        # north of start, city facing south
        m = recv()
        if m.get("t") != "req_tile" or int(m.get("tile_type", -1)) != T_C:
            raise RuntimeError(f"probe: expected req_tile for tile {T_C}, got {m!r}")
        if target not in [list(z) for z in m["placements"]]:
            raise RuntimeError(f"probe construction invalid: {target} not offered")
        send({"t": "tile", "x": target[0], "y": target[1], "o": target[2]})
        m = recv()
        if m.get("t") != "req_meeple":
            raise RuntimeError(f"probe: expected req_meeple, got {m!r}")
        city = [n for n in m["nodes"] if n["terrain"] == "city"]
        if len(city) != 1 or city[0]["labels"] != ["S"]:
            raise RuntimeError(f"probe: unexpected city node {city!r}")
        send({"t": "meeple", "i": city[0]["i"]})
        m = recv()
        if m.get("t") != "ev_move":
            raise RuntimeError(f"probe: expected ev_move, got {m!r}")
        scored = max(m["score_detail"]["city"])
        if scored != 4:
            raise RuntimeError(
                f"R1 GATE FAILED: a plain two-tile city scored {scored}, expected 4. "
                "This binary still carries upstream's original-2000 tiny-city "
                "exception (or the patch did not make it in). Refusing to start: a "
                "session played against it is a RULES result wearing a strength "
                "result's costume. See RULES_DELTA.md 2.1.")
        return {"tiny_city_score": scored, "revision": ready.get("revision"),
                "patches": ready.get("patches"), "board_size": bs,
                "start_xy": sxy, "players": ready.get("players")}
    finally:
        try:
            send({"t": "quit"})
            p.wait(timeout=10)
        except Exception:                                        # noqa: BLE001
            p.kill()


# --------------------------------------------------------------------------- #
# one game                                                                     #
# --------------------------------------------------------------------------- #

def _count_opponent_plies(deck_seed: int, actions, human_seat: int) -> int:
    """How many plies in this log were played by the seat Carcasum occupies.

    The one signal that separates "the human opened and it is now my turn" (a
    brand-new game, human on seat 0, perfectly resumable-as-fresh) from "this
    game already has Carcasum moves in it" (unresumable — a fresh Carcasum
    process would be a different opponent inside one game). Replayed with OUR
    engine, which is the game of record on both ends, under the same rules
    profile and the same `random.seed(deck_seed)` root_replay contract the phone
    archives use.

    Never raises on a bad log: an unreplayable log is reported as "opponent has
    moved", which fails CLOSED — refusing a resumable game is a nuisance,
    accepting an unresumable one silently swaps the opponent mid-game.
    """
    acts = [int(a) for a in (actions or [])]
    if not acts:
        return 0
    M = match_module()
    import random                                                 # noqa: PLC0415

    from carcassonne_ai import rules_profile                      # noqa: PLC0415
    from carcassonne_ai.game_wrapper import Game                  # noqa: PLC0415

    try:
        prof = rules_profile.activate(M.PROFILE)
        random.seed(int(deck_seed))
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        n = 0
        for a in acts:
            if int(board.state.current_player) != int(human_seat):
                n += 1
            board, _ = game.get_next_state(board, int(a))
        return n
    except Exception:                                             # noqa: BLE001
        return len(acts)


class SessionError(RuntimeError):
    """A client-visible session fault; `code` is the machine-readable reason."""

    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.extra = extra


class _LogAgent:
    """The external (human) seat, driven by the phone's action log.

    ⚠️ POSITIONAL, NOT A QUEUE, and that distinction is load-bearing. The answer
    to "what did the human play next" is always
    `client_log[len(server_log)]` — the entry at the ply the game has actually
    reached — never "the next thing the client pushed".

    A queue is wrong here because `play_one_match` SYNTHESISES actions of its
    own on the external seat: the implicit meeple pass it applies when Carcasum
    never sent `req_meeple` (`possibleMeeples.size() <= 1`), and the TILES-phase
    pass on `ev_discard`. The phone applies those same forced passes locally and
    sends them in its log, so a queue would be left holding an orphan pass that
    the NEXT `req_tile` would swallow — silently playing the wrong move and
    desyncing every ply after it. Indexing by ply cannot do that: both sides name
    the same position.

    It has no `start_game`/`advance`, so `mirror_protocol.seat/advance` correctly
    skip it (same shape as `JoshuaBot` in the h2h driver).
    """

    def __init__(self, session: "_Session"):
        self._s = session

    def choose_action(self, board) -> int:                        # noqa: ARG002
        return self._s._pull_external_action()


class _Session:
    """One live game: a `play_one_match` thread plus the authoritative log.

    THREADING. The game runs on its own thread because `play_one_match` owns the
    loop (Carcasum's `Game::step()` drives it) and cannot be pumped a move at a
    time from outside. Everything shared with the HTTP handlers lives under
    `self._cv`; the handlers never touch the engine.
    """

    def __init__(self, *, game_id: str, deck_seed: int, human_seat: int,
                 binary: Path, opponent: dict, node_labels, periods,
                 verify_replay: bool, max_wait_s: float,
                 records_dir: Path | None = None):
        self.game_id = str(game_id)
        self.deck_seed = int(deck_seed)
        self.human_seat = int(human_seat)
        self.opponent = dict(opponent)
        self.created_at = time.time()
        self.last_seen = time.time()
        self.max_wait_s = float(max_wait_s)
        self.records_dir = records_dir

        self._cv = threading.Condition()
        #: The authoritative action sequence, in ply order, BOTH seats. Appended
        #: only by the game thread, via `play_one_match`'s `on_apply` hook.
        self.actions: list[int] = []
        self.seats: list[int] = []
        self.kinds: list[str] = []
        self.finished = False
        self.record: dict | None = None
        self.error: str | None = None
        #: True while the game thread is blocked wanting an external action.
        self.needs_input = False

        #: The longest client-supplied action log seen so far, always
        #: prefix-consistent with `self.actions` (checked in `submit`).
        self.client_log: list[int] = []
        self._stop = threading.Event()

        self._match = match_module()
        self._thread = threading.Thread(
            target=self._run, name=f"carcasum-{self.game_id}", daemon=True,
            kwargs={"binary": binary, "node_labels": node_labels,
                    "periods": periods, "verify_replay": verify_replay})
        self._thread.start()

    # -- the game thread ---------------------------------------------------- #
    def _run(self, *, binary, node_labels, periods, verify_replay) -> None:
        try:
            rec = self._match.play_one_match(
                self.deck_seed, self.human_seat,
                binary=binary, opponent=self.opponent,
                node_labels_by_type=node_labels, tile_periods=periods,
                verify_replay=verify_replay,
                agent=_LogAgent(self), on_apply=self._on_apply)
        except BaseException as exc:                              # noqa: BLE001
            with self._cv:
                self.error = f"{type(exc).__name__}: {exc}"
                self.finished = True
                self._cv.notify_all()
            return
        with self._cv:
            self.record = rec
            self.finished = True
            self._cv.notify_all()
        if self.records_dir is not None:
            try:
                self.records_dir.mkdir(parents=True, exist_ok=True)
                path = self.records_dir / f"{self.game_id}.json"
                path.write_text(json.dumps(
                    {"schema": SCHEMA, "game_id": self.game_id,
                     "opponent_label": OPPONENT_LABEL, "record": rec}, indent=1))
            except Exception:                                     # noqa: BLE001
                pass

    def _on_apply(self, action: int, seat: int, kind: str) -> None:
        with self._cv:
            self.actions.append(int(action))
            self.seats.append(int(seat))
            self.kinds.append(str(kind))
            self._cv.notify_all()

    def _pull_external_action(self) -> int:
        """The human's action at the ply the game has reached, waiting for it.

        Publishes `needs_input` while it waits so the HTTP side can answer "you
        owe me a move" rather than hanging until the driver's 35 s read timeout
        kills a live game.
        """
        while not self._stop.is_set():
            with self._cv:
                i = len(self.actions)
                if i < len(self.client_log):
                    self.needs_input = False
                    return int(self.client_log[i])
                if not self.needs_input:
                    self.needs_input = True
                    self._cv.notify_all()
                self._cv.wait(timeout=0.25)
        raise SessionError("session_closed", "the session was torn down")

    # -- the HTTP side ------------------------------------------------------ #
    def submit(self, client_actions: list[int]) -> None:
        """Feed the client's log forward. Raises on divergence.

        The client's log must be prefix-compatible with ours in BOTH directions:
        shorter means it simply has not applied a move we already decided (the
        retry case), longer means it has played moves we have not seen yet.
        Anything else is a real disagreement about the game and must be loud.
        """
        with self._cv:
            for name, ours in (("server", self.actions), ("client", self.client_log)):
                n = min(len(client_actions), len(ours))
                if list(client_actions[:n]) != list(ours[:n]):
                    bad = next(i for i in range(n) if client_actions[i] != ours[i])
                    raise SessionError(
                        "divergence",
                        f"client action log diverges from the {name}'s at ply {bad}",
                        ply=bad, against=name, client=int(client_actions[bad]),
                        server=int(ours[bad]), server_len=len(self.actions),
                        client_len=len(client_actions))
            if len(client_actions) > len(self.client_log):
                self.client_log = [int(a) for a in client_actions]
            self._cv.notify_all()

    def next_action(self, index: int) -> dict:
        """The action at ply `index`, waiting for it if it has not happened yet.

        ⚠️ THIS is what makes a retry idempotent, and it is worth being explicit
        about why: the answer is a pure function of `(session, index)`. A client
        that never received the response re-sends the identical request, we read
        the SAME entry out of the log we already committed, and no second search
        is run, no second move is applied, and the two sides cannot drift.
        """
        deadline = time.time() + self.max_wait_s
        with self._cv:
            while True:
                if index < len(self.actions):
                    return {"ok": True, "action": int(self.actions[index]),
                            "seat": int(self.seats[index]), "kind": self.kinds[index],
                            "index": index, "n_actions": len(self.actions),
                            "game_over": self.finished and index == len(self.actions) - 1}
                if self.error is not None:
                    raise SessionError("game_error", self.error, n_actions=len(self.actions))
                if self.finished:
                    rec = self.record or {}
                    return {"ok": True, "game_over": True, "action": None,
                            "index": index, "n_actions": len(self.actions),
                            "scores": rec.get("scores"),
                            "carcasum_reported_scores": rec.get("carcasum_reported_scores"),
                            "final_agree": rec.get("final_agree"),
                            "void": rec.get("void"), "void_detail": rec.get("void_detail"),
                            "real": rec.get("real"), "replay_ok": rec.get("replay_ok")}
                if self.needs_input and len(self.client_log) <= len(self.actions):
                    raise SessionError(
                        "needs_more_actions",
                        "the opponent is waiting on a move from your seat; send the "
                        "full action log including it",
                        n_actions=len(self.actions))
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise SessionError("timeout",
                                       f"no move within {self.max_wait_s:.0f}s",
                                       n_actions=len(self.actions))
                self._cv.wait(timeout=min(remaining, 0.5))

    def wait_finished(self, timeout: float = 30.0) -> bool:
        """Block until the game thread has published its record.

        `play_one_match` does real work AFTER the last action lands — the
        endgame farm/terrain audit, the `(deck_seed, actions)` replay check, the
        manifest. A client whose own board has terminated will call `/end`
        immediately, and without this wait it would get `record: null` and think
        the game produced nothing.
        """
        deadline = time.time() + float(timeout)
        with self._cv:
            while not self.finished:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self._cv.wait(timeout=min(remaining, 0.25))
        return True

    def close(self) -> None:
        self._stop.set()
        with self._cv:
            self._cv.notify_all()

    def info(self) -> dict:
        with self._cv:
            return {"game_id": self.game_id, "deck_seed": self.deck_seed,
                    "human_seat": self.human_seat, "n_actions": len(self.actions),
                    "finished": self.finished, "error": self.error,
                    "needs_input": self.needs_input,
                    "n_client_actions": len(self.client_log),
                    "age_s": round(time.time() - self.created_at, 1),
                    "idle_s": round(time.time() - self.last_seen, 1),
                    "scores": (self.record or {}).get("scores")}


# --------------------------------------------------------------------------- #
# the daemon                                                                   #
# --------------------------------------------------------------------------- #
class RemoteOpponentServer:
    """Session registry + the two gates. Held by the HTTP handler class."""

    def __init__(self, *, binary: Path, opponent: dict, gate: dict,
                 verify_replay: bool, max_wait_s: float, records_dir: Path | None,
                 max_sessions: int = 8, session_ttl_s: float = 6 * 3600):
        self.binary = Path(binary)
        self.opponent = dict(opponent)
        self.gate = dict(gate)
        self.verify_replay = bool(verify_replay)
        self.max_wait_s = float(max_wait_s)
        self.records_dir = records_dir
        self.max_sessions = int(max_sessions)
        self.session_ttl_s = float(session_ttl_s)
        self.started_at = time.time()
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}
        # One `--dump-tiles` per PROCESS, not per game (match.py's own caching
        # rule): the node-label and rotation-period tables are static.
        self.node_labels, self.periods, self.tiles_ready = \
            match_module().load_carcasum_node_labels(self.binary)

    # -- registry ----------------------------------------------------------- #
    def _reap(self) -> None:
        now = time.time()
        for gid, s in list(self._sessions.items()):
            if now - s.last_seen > self.session_ttl_s or (
                    s.finished and now - s.last_seen > 600):
                s.close()
                self._sessions.pop(gid, None)

    def get_or_create(self, *, game_id: str, deck_seed: int, human_seat: int,
                      opponent: dict | None, client_actions) -> _Session:
        with self._lock:
            self._reap()
            s = self._sessions.get(game_id)
            if s is not None:
                if s.deck_seed != int(deck_seed) or s.human_seat != int(human_seat):
                    raise SessionError(
                        "session_mismatch",
                        f"game_id {game_id!r} is already bound to deck_seed "
                        f"{s.deck_seed} seat {s.human_seat}",
                        server_deck_seed=s.deck_seed, server_human_seat=s.human_seat)
                s.last_seen = time.time()
                return s
            # A NON-EMPTY log on a fresh session is NOT automatically a resume:
            # when the human has seat 0 he plays ply 0 (and possibly his meeple)
            # before the opponent is ever asked, so the FIRST request of a brand
            # new game legitimately carries a few actions. What cannot be picked
            # up is a game the opponent has already moved in — see the module
            # docstring's "one honest limit". So ask the engine which it is, on
            # the one signal that actually distinguishes them: has any ply in the
            # client's log belonged to the OPPONENT seat.
            n_opp = _count_opponent_plies(deck_seed, client_actions, human_seat)
            if n_opp:
                raise SessionError(
                    "session_lost",
                    "no live session for this game_id, and the client's log "
                    f"already contains {n_opp} opponent move(s). Carcasum cannot be "
                    "replayed into a position (compile-time RNG, no history-load in "
                    "the driver), so a fresh process would be a DIFFERENT opponent "
                    "inside one game. This game cannot be resumed; log it as "
                    "abandoned (PROTOCOL.md 3).",
                    n_client_actions=len(client_actions), n_opponent_plies=int(n_opp))
            if len(self._sessions) >= self.max_sessions:
                raise SessionError("too_many_sessions",
                                   f"{len(self._sessions)} live sessions (cap "
                                   f"{self.max_sessions})")
            s = _Session(game_id=game_id, deck_seed=deck_seed, human_seat=human_seat,
                         binary=self.binary, opponent=dict(self.opponent, **(opponent or {})),
                         node_labels=self.node_labels, periods=self.periods,
                         verify_replay=self.verify_replay, max_wait_s=self.max_wait_s,
                         records_dir=self.records_dir)
            self._sessions[game_id] = s
            return s

    def end(self, game_id: str, *, wait_s: float = 30.0) -> dict:
        with self._lock:
            s = self._sessions.pop(game_id, None)
        if s is None:
            raise SessionError("unknown_session", f"no session {game_id!r}")
        # Wait BEFORE closing: closing tears the game thread down mid-audit and
        # the record would come back void.
        finished = s.wait_finished(timeout=float(wait_s))
        s.close()
        return {"ok": True, "game_id": game_id, "finished": finished,
                "record": s.record, "info": s.info()}

    def health(self) -> dict:
        with self._lock:
            sessions = [s.info() for s in self._sessions.values()]
        return {"ok": True, "schema": SCHEMA, "opponent_label": OPPONENT_LABEL,
                "uptime_s": round(time.time() - self.started_at, 1),
                "binary": str(self.binary), "gate": self.gate,
                "opponent": self.opponent, "profile": self._match_profile(),
                "n_sessions": len(sessions), "sessions": sessions}

    @staticmethod
    def _match_profile() -> dict:
        return {"rules_profile": match_module().PROFILE,
                "r9_env": os.environ.get("CARCASSONNE_FIX_R9")}


class _Handler(BaseHTTPRequestHandler):
    server_version = "CarcasumRemote/1"
    srv: RemoteOpponentServer = None                              # set by main()

    def log_message(self, fmt, *args):                            # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _reply(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode())

    def do_GET(self):                                             # noqa: N802
        if self.path.split("?")[0] == "/health":
            return self._reply(200, self.srv.health())
        if self.path.split("?")[0] == "/sessions":
            return self._reply(200, {"ok": True,
                                     "sessions": self.srv.health()["sessions"]})
        return self._reply(404, {"ok": False, "error": "not_found", "path": self.path})

    def do_POST(self):                                            # noqa: N802
        path = self.path.split("?")[0]
        try:
            body = self._body()
        except Exception as exc:                                  # noqa: BLE001
            return self._reply(400, {"ok": False, "error": "bad_json",
                                     "message": str(exc)})
        try:
            if path == "/move":
                return self._reply(200, self._move(body))
            if path == "/end":
                return self._reply(200, self._end(body))
            return self._reply(404, {"ok": False, "error": "not_found", "path": path})
        except SessionError as exc:
            code = 409 if exc.code in ("divergence", "session_mismatch",
                                       "session_lost") else 503
            return self._reply(code, {"ok": False, "error": exc.code,
                                      "message": str(exc), **exc.extra})
        except Exception as exc:                                  # noqa: BLE001
            return self._reply(500, {"ok": False, "error": "internal",
                                     "message": f"{type(exc).__name__}: {exc}"})

    def _end(self, body: dict) -> dict:
        """Finish a game and hand back the full match record.

        ⚠️ `actions` is not optional in practice. When the HUMAN plays the
        terminating ply there is no further `/move`, so the server has never been
        told about that last action and its Carcasum session is still sitting in
        the loop waiting for it — the record would come back `null` and the
        endgame farm/terrain audit would never run. So `/end` submits the
        client's final log first, exactly the way `/move` does, and only then
        waits for the record.
        """
        game_id = str(body.get("game_id") or "")
        actions = body.get("actions")
        if actions is not None:
            with self.srv._lock:
                s = self.srv._sessions.get(game_id)
            if s is not None:
                s.submit([int(a) for a in actions])
        return self.srv.end(game_id, wait_s=float(body.get("wait_s", 60.0)))

    def _move(self, body: dict) -> dict:
        game_id = str(body.get("game_id") or "")
        if not game_id:
            raise SessionError("bad_request", "game_id is required")
        actions = [int(a) for a in (body.get("actions") or [])]
        s = self.srv.get_or_create(
            game_id=game_id, deck_seed=int(body["deck_seed"]),
            human_seat=int(body["human_seat"]), opponent=body.get("opponent"),
            client_actions=actions)
        s.last_seen = time.time()
        s.submit(actions)
        out = s.next_action(len(actions))
        out.update({"game_id": game_id, "opponent_label": OPPONENT_LABEL,
                    "binary_gate": self.srv.gate.get("state")})
        return out


# --------------------------------------------------------------------------- #
# entry point                                                                  #
# --------------------------------------------------------------------------- #
def build_gate(binary: Path, *, expect_sha: str | None, allow_any: bool) -> dict:
    got = sha256_file(binary)
    gate = {"sha256": got, "expect_sha256": expect_sha, "state": "ANCHOR"}
    if expect_sha and got != expect_sha:
        if not allow_any:
            raise SystemExit(
                f"G-BINARY FAILED: {binary} has sha256 {got}, expected {expect_sha} "
                "(the anchor binary named in measurement/carcasum_owner_session_prep/"
                "SETUP.md 2). A different binary is a DIFFERENT OPPONENT and the "
                "session's B anchor does not apply to it. Re-point --binary, or pass "
                "--allow-any-binary if you genuinely mean to play an unvetted build.")
        gate["state"] = "OVERRIDDEN"
    elif not expect_sha:
        gate["state"] = "UNCHECKED"
    gate["probe"] = probe_tiny_city_scores_four(binary)
    return gate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", required=True,
                    help="address to bind — the TAILNET address of this box. "
                         "There is no default on purpose (see the security note).")
    ap.add_argument("--port", type=int, default=8971)
    ap.add_argument("--binary", default=str(
        REPO / "vendor" / "carcasum" / "build-driver" / "carcasum_driver"))
    ap.add_argument("--expect-sha", default=ANCHOR_SHA256,
                    help="sha256 the binary must have (default: the anchor binary)")
    ap.add_argument("--allow-any-binary", action="store_true",
                    help="do not refuse a hash mismatch (stamps binary_gate=OVERRIDDEN)")
    ap.add_argument("--budget-ms", type=int, default=5000,
                    help="Carcasum's per-turn CPU-time budget (the calibrated 5000)")
    ap.add_argument("--cp", type=float, default=0.5)
    ap.add_argument("--max-wait-s", type=float, default=90.0,
                    help="how long a /move may block before answering 'timeout'")
    ap.add_argument("--no-verify-replay", action="store_true",
                    help="skip the end-of-game (deck_seed, actions) replay check")
    ap.add_argument("--records-dir", default=None,
                    help="write each finished game's full match record here")
    ap.add_argument("--probe-only", action="store_true",
                    help="run the gates, print them, and exit without binding")
    args = ap.parse_args(argv)

    binary = Path(args.binary)
    if not binary.is_file():
        raise SystemExit(f"carcasum_driver not found at {binary}")

    # R9 must be exported BEFORE anything imports carcassonne_ai (it is
    # import-latched into a Rust OnceLock). match.py owns that preamble; we reuse
    # it rather than re-deriving which env var this profile owes.
    match_mod = match_module()

    gate = build_gate(binary, expect_sha=(args.expect_sha or None),
                      allow_any=args.allow_any_binary)
    opponent = dict(match_mod.DEFAULT_OPPONENT,
                    budget_ms=int(args.budget_ms), cp=float(args.cp))
    if args.probe_only:
        print(json.dumps({"ok": True, "gate": gate, "opponent": opponent}, indent=1))
        return 0

    srv = RemoteOpponentServer(
        binary=binary, opponent=opponent, gate=gate,
        verify_replay=not args.no_verify_replay, max_wait_s=args.max_wait_s,
        records_dir=(Path(args.records_dir) if args.records_dir else None))
    _Handler.srv = srv
    httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
    sys.stderr.write(
        f"carcasum remote-opponent server on http://{args.host}:{args.port}\n"
        f"  binary   {binary} ({gate['sha256'][:12]}, gate {gate['state']})\n"
        f"  probe    plain 2-tile city scores {gate['probe']['tiny_city_score']} (want 4)\n"
        f"  opponent {opponent['kind']}/{opponent['utility']}/{opponent['playout']} "
        f"{opponent['budget_ms']}ms cp={opponent['cp']}\n"
        f"  label    {OPPONENT_LABEL}\n")
    sys.stderr.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
