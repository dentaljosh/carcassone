"""F9 / D2 — the ``%ai`` / ``%aimove`` client for the champion-vs-JCZ match driver.

``scripts/jcz_oracle/jcz_driver.py`` speaks JCZ 5.x's headless engine protocol: one
line-delimited JSON message in, one full game-state line out. The match driver needs
one thing that protocol does not have — **a JCZ-side player that MOVES BY ITSELF** —
so ``com.jcloisterzone.ai.AiEngine`` (the Java side of this build, under ``java/``)
adds exactly two directives on top of the unchanged wire format:

* ``%ai <playerIndex>`` — 0-based seat that the JCZ AI controls. It is a *directive*
  (like ``%load``): **no reply line**, and it MUST be sent BEFORE ``GAME_SETUP``,
  which is why it cannot live inside ``JczEngine.setup``.
* ``%aimove`` — the AI computes ONE message for the current state, applies it
  internally, and prints ``{"aiMessage": {...}, "state": {...}}``. JCZ's AI returns
  one message at a time out of a buffered chain (place tile, then deploy, then the
  end-of-turn confirm), so this is called **repeatedly** until the active player
  changes.

## Why every field is looked up by PRESENCE, never by position

This module was written against a Java side that did not exist yet, and JCZ's own
message vocabulary is not stable across its serialisers (a message is a class name in
one place and a ``type`` string in another; a payload is sometimes inlined and
sometimes nested under ``payload``). Guessing a spelling and being wrong would show up
as a *rules* finding in the match log — the one failure this whole harness exists to
not have. So:

* ``message_kind()`` normalises any spelling to ``PLACE_TILE`` / ``DEPLOY_MEEPLE`` /
  ``PASS`` / ``COMMIT``, and falls back to **structure** (a ``tileId`` means a tile
  placement; a ``pointer``/``meepleId`` means a deploy) when the name is unknown.
* ``rotation_quarters()`` accepts BOTH spellings of the protocol's worst footgun:
  ``rotation`` is an **int** inside ``action.options`` but the enum string ``"R180"``
  inside a ``PLACE_TILE`` payload (spike A5). Reading is permissive; *writing* is not
  — a payload's rotation is only ever built by ``tile_map.jcz_rotation_str``.

Nothing here interprets a move. Inversion onto our action space happens in
``match.py`` and only ever by matching through the already-verified FORWARD map.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_ORACLE = _HERE.parents[1] / "jcz_oracle"
if str(_ORACLE) not in sys.path:
    sys.path.insert(0, str(_ORACLE))

from jcz_driver import JczEngine, JczError  # noqa: E402,F401  (JczError re-exported)

#: The canonical kinds the match driver reasons about.
PLACE_TILE = "PLACE_TILE"
DEPLOY_MEEPLE = "DEPLOY_MEEPLE"
PASS = "PASS"
COMMIT = "COMMIT"
UNKNOWN = "UNKNOWN"

_KIND_PATTERNS: tuple[tuple[str, str], ...] = (
    (PLACE_TILE, "PLACETILE"),
    (DEPLOY_MEEPLE, "DEPLOYMEEPLE"),
    (DEPLOY_MEEPLE, "DEPLOY"),
    (COMMIT, "COMMIT"),
    (COMMIT, "CONFIRM"),
    (PASS, "PASS"),
)


def message_kind(msg: dict | None) -> str:
    """Normalise an ``aiMessage`` to one of the canonical kinds above.

    Name first (``type`` / ``className`` / ``kind``, stripped of package, case and a
    trailing ``Message``), then STRUCTURE, so an unrecognised spelling still resolves
    correctly rather than voiding a game for a naming difference.
    """
    if not msg:
        return UNKNOWN
    raw = str(msg.get("type") or msg.get("className") or msg.get("kind") or "")
    name = re.sub(r"[^A-Z]", "", raw.rsplit(".", 1)[-1].upper())
    for kind, needle in _KIND_PATTERNS:
        if needle in name:
            return kind
    body = message_body(msg)
    if body.get("tileId") is not None:
        return PLACE_TILE
    if body.get("pointer") is not None or body.get("meepleId") is not None:
        return DEPLOY_MEEPLE
    return UNKNOWN


def message_body(msg: dict | None) -> dict:
    """The message's fields, whether they are inlined or nested under ``payload``.

    Nested wins on a key collision only if the outer level does not carry it, so a
    flat ``{"type":…, "tileId":…}`` and a nested ``{"type":…, "payload":{…}}`` read
    identically.
    """
    if not msg:
        return {}
    inner = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
    out = dict(inner)
    for k, v in msg.items():
        if k != "payload":
            out[k] = v
    return out


def rotation_quarters(value) -> int | None:
    """``"R180"`` or ``180`` or ``2`` -> quarter turns. None if unparsable.

    ⚠️ READ-side only. The int spelling silently no-ops a ``PLACE_TILE`` payload, so
    nothing in this harness ever *writes* rotation except ``jcz_rotation_str``.
    Degrees and quarters are disambiguated by magnitude: JCZ only ever means degrees
    when the number is a multiple of 90 above 3.
    """
    if value is None:
        return None
    if isinstance(value, str):
        m = re.fullmatch(r"R?(\d+)", value.strip().upper())
        if not m:
            return None
        value = int(m.group(1))
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    if v in (0, 1, 2, 3):
        return v % 4
    if v % 90 == 0:
        return (v // 90) % 4
    return None


def pointer_of(msg: dict) -> dict:
    """The ``FeaturePointer`` of a deploy message: ``position``/``location``/``feature``.

    Accepts the pointer nested (``{"pointer": {...}}``) or splatted onto the message,
    because both shapes are legal JCZ serialisations of the same thing.
    """
    body = message_body(msg)
    ptr = body.get("pointer")
    if isinstance(ptr, dict):
        return ptr
    return {k: body[k] for k in ("position", "location", "feature") if k in body}


class JczAiEngine(JczEngine):
    """``JczEngine`` plus the two AI directives. One JVM = one game, as before.

    Deliberately a SUBCLASS: ``jcz_driver.py`` is the validated oracle plumbing
    (``measurement/jcz_oracle_20260803/VALIDATION_REPORT.md``) and is not edited by
    this build.
    """

    #: The Java main class of the AI-aware engine (the other half of this build).
    DEFAULT_MAIN_CLASS = "com.jcloisterzone.ai.AiEngine"

    #: Where ``build_ai_shim.sh`` compiles to. Having a DEFAULT is not cosmetic —
    #: see ``require_ai`` below for why the alternative is a silent hang.
    DEFAULT_AI_CLASSES = Path(os.path.expanduser("~/jcz_spike/ai_classes"))

    #: A stdout line is PROTOCOL (not log noise) iff its JSON object carries one of
    #: these. `players`/`phase` = a game state, `aiMessage` = an %aimove reply,
    #: `error` = AiEngine.aiError.
    PROTOCOL_KEYS = frozenset({"aiMessage", "state", "players", "phase", "error"})

    def __init__(self, *a, ai_classes=None, main_class: str | None = None,
                 require_ai: bool = True, **kw):
        # Set BEFORE super().__init__, which launches the JVM via `_launch_cmd`.
        # `ai_classes` = the directory `build_ai_shim.sh` compiles into.
        #
        # ⚠️ WHY THIS RAISES INSTEAD OF FALLING BACK (fixed 2026-08-09, after it cost
        # a hung 20-game smoke). Falling back to plain `java -jar` does NOT "fail
        # loudly at %ai": `%ai` is a DIRECTIVE, and JCZ's directive parser answers an
        # unknown one with `#unknown directive` on stderr and *no reply line at all*.
        # The next `%aimove` is likewise swallowed, so the driver blocks forever in
        # `readline()` — eight workers sat at `pipe_read` with 0.6% CPU and produced
        # nothing. A missing shim must be an exception at construction, exactly like
        # a missing jar. `require_ai=False` restores the drop-in-JczEngine behaviour
        # for callers that genuinely want the non-AI engine.
        env_classes = os.environ.get("JCZ_AI_CLASSES") or None
        chosen = ai_classes or env_classes or (self.DEFAULT_AI_CLASSES if require_ai else None)
        self.ai_classes = Path(chosen) if chosen else None
        if require_ai and (self.ai_classes is None or not self.ai_classes.exists()):
            raise FileNotFoundError(
                f"JCZ AI shim classes not found at {self.ai_classes}. Build them with:\n"
                "  scripts/jcz_match/build_ai_shim.sh\n"
                "(or pass ai_classes=/--ai-classes, or set JCZ_AI_CLASSES). Without them "
                "the engine has no AI seat and %aimove hangs forever.")
        self.main_class = main_class or os.environ.get(
            "JCZ_AI_MAIN_CLASS", self.DEFAULT_MAIN_CLASS)
        self.log_lines: list[str] = []          # set before super(): __init__ sends %load
        super().__init__(*a, **kw)
        self.ai_seats: list[int] = []
        self.n_ai_moves = 0

    def _launch_cmd(self, java: str) -> list[str]:
        """``java -cp <Engine.jar>:<ai classes> <main class>`` when the shim is built.

        The jar's own manifest main class is the NON-AI engine, so the AI build must
        be launched by classpath + explicit main class. The ``-jar`` fallback below is
        reachable only under ``require_ai=False`` — see ``__init__`` for why it is not
        a safe default."""
        if self.ai_classes is None or not Path(self.ai_classes).exists():
            return super()._launch_cmd(java)
        cp = os.pathsep.join([str(self.jar), str(self.ai_classes)])
        return [java, "-cp", cp, self.main_class]

    # --- plumbing ---------------------------------------------------------- #
    def _recv(self) -> dict:
        """Read one PROTOCOL line, skipping JCZ's log output.

        ⚠️ Found the hard way, 2026-08-08: JCZ's slf4j logger writes to **stdout**,
        not stderr, so a line like ``[main] WARN …GameStatePhaseReducer - Unhandled
        message:`` lands in the middle of the protocol stream and blows up the JSON
        parse. The oracle never saw this because it never provoked a warning. Log
        lines are captured on ``self.log_lines`` rather than dropped — an "Unhandled
        message" warning means the JVM silently ignored a ply, which would otherwise
        desync the two boards invisibly, so the driver must be able to see them.
        """
        assert self._p.stdout is not None
        for _ in range(200):
            line = self._p.stdout.readline()
            if not line:
                break
            s = line.strip()
            if not s:
                continue
            if s.startswith("{"):
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    self.log_lines.append(s[:400])
                    continue
                # ⚠️ The logger's CONTINUATION line is itself valid JSON — slf4j prints
                # "Unhandled message:" and then the message object on the next line — so
                # "starts with {" is NOT enough to identify a protocol line. A protocol
                # line is a game state, an %aimove wrapper, or an error; a bare
                # {"type":…,"payload":…} is the log echoing a message back at us.
                if isinstance(obj, dict) and self.PROTOCOL_KEYS & set(obj):
                    return obj
                self.log_lines.append(s[:400])
                continue
            self.log_lines.append(s[:400])
        raise JczError(
            f"engine emitted no state line (exit={self._p.poll()}); "
            f"log tail: {self.log_lines[-3:]}; stderr tail: {self.stderr_text()[-600:]!r}")

    # --- directives -------------------------------------------------------- #
    def ai_seat(self, idx: int) -> None:
        """Register a 0-based seat as AI-controlled. NO reply line is expected.

        MUST precede ``setup()`` — the Java side reads the directive while building
        the game, and a late ``%ai`` would register a player that is already seated.
        """
        self._send_raw(f"%ai {int(idx)}")
        self.ai_seats.append(int(idx))

    # --- one AI message ---------------------------------------------------- #
    def ai_move(self) -> tuple[dict, dict]:
        """Ask the AI for ONE message. Returns ``(message, state)``.

        The Java side applies the message itself, so the returned state is already
        post-move — there is nothing for the caller to echo back.
        """
        self._send_raw("%aimove")
        obj = self._recv()
        if obj.get("error") is not None:
            # AiEngine.aiError: it applied NOTHING, so this is a driver bug (asking the
            # AI to move on someone else's turn) and must never be swallowed.
            raise JczError(f"%aimove refused: {obj['error']}")
        msg = obj.get("aiMessage") or obj.get("message") or obj.get("ai_message")
        state = obj.get("state") or obj.get("gameState")
        if state is None:
            # A Java side that prints the state at top level with the message beside
            # it is just as valid a reading of the contract; accept it.
            state = obj if "players" in obj else {}
        if msg is None:
            raise JczError(f"%aimove returned no aiMessage: keys={sorted(obj)}")
        self.n_ai_moves += 1
        return msg, state

    def ai_decision(self, want: tuple[str, ...], limit: int = 8) -> tuple[dict, dict, list[str]]:
        """``ai_move()`` until a message of a wanted kind arrives; returns it.

        ⚠️ This is the seam that makes the driver indifferent to WHO answers the
        end-of-turn ``Confirm``. The driver commits/passes protocol acknowledgements
        itself (they are not decisions), but a JCZ AI that buffers its own chain may
        still hand one back; those are absorbed here and reported in the third return
        value so the game record can show they happened rather than hiding them.
        """
        skipped: list[str] = []
        for _ in range(limit):
            msg, state = self.ai_move()
            kind = message_kind(msg)
            if kind in want:
                return msg, state, skipped
            skipped.append(kind)
        raise JczError(
            f"%aimove produced no {want} message in {limit} tries (saw {skipped})")
