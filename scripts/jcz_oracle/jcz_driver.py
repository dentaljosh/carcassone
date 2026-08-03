"""F9 / D1 — subprocess driver for the headless JCloisterZone engine.

JCZ 5.x ships ``com.jcloisterzone.engine.Engine``, a line-delimited JSON
stdin/stdout REPL. The contract (spike Q1, re-verified here):

* ``%load <abs path to tiles.xml>``   — directive, no reply
* ``{"type":"GAME_SETUP","payload":…}`` — one line; the engine replies with a
  full game-state line, and does so after **every** subsequent message
* ``{"type":"PLACE_TILE"|"DEPLOY_MEEPLE"|"PASS"|"COMMIT","payload":…}``

The emitted state carries all three oracle signals at once::

    action           -> the LEGAL move set for the player to act
    players[].points -> running score
    features         -> every City/Road/Field/Monastery with its tile-places

``gameAnnotations.tilePack = com.jcloisterzone.debug.ForcedDrawTilePack`` takes an
explicit ``drawOrder``, so our ``(deck_seed, actions)`` archives replay with **no
RNG matching at all** — the single biggest unpriced risk in the spec, and it does
not exist.

Two protocol footguns this module exists to absorb:

* ``rotation`` is an **int** in ``action.options`` but the enum string ``"R180"``
  in a ``PLACE_TILE`` payload. Sending an int silently no-ops the ply.
* a ``FeaturePointer`` needs all three of ``position``/``location``/``feature``;
  omitting ``feature`` throws a bare NPE on stderr and emits **no state line**
  (``MessageParser.java:50``). ``deploy_meeple`` therefore takes JCZ's own option
  dict verbatim.

The jar is NOT vendored into the repo (28 MB, shaded). It lives under
``~/jcz_spike`` per the spike's build steps; ``JCZ_JAR`` overrides.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

DEFAULT_JAR = Path(os.path.expanduser("~/jcz_spike/JCloisterZone/build/Engine.jar"))
DEFAULT_TILES = (
    Path(__file__).resolve().parents[2]
    / "measurement" / "jcz_spike_20260803" / "jcz_basic_5x.xml"
)


class JczError(RuntimeError):
    """The engine emitted no state line (a parse/rules refusal). Carries stderr."""


class JczEngine:
    """One JVM = one game. Context manager; always terminates the child."""

    def __init__(self, jar: Path | str | None = None, tiles: Path | str | None = None,
                 java: str = "java"):
        self.jar = Path(jar) if jar else Path(os.environ.get("JCZ_JAR", DEFAULT_JAR))
        self.tiles = Path(tiles) if tiles else DEFAULT_TILES
        if not self.jar.exists():
            raise FileNotFoundError(
                f"JCZ Engine.jar not found at {self.jar}. Build it with the spike's steps:\n"
                "  git clone --depth 1 https://github.com/farin/JCloisterZone.git ~/jcz_spike/JCloisterZone\n"
                "  ~/jcz_spike/apache-maven-3.9.9/bin/mvn -q -B -DskipTests package "
                "-f ~/jcz_spike/JCloisterZone/pom.xml"
            )
        # stderr goes to a real file, not a pipe: the JVM writes a bare stack trace
        # and NO state line when it refuses a message, and a blocking pipe read at
        # that point would deadlock. A file lets JczError quote the trace.
        self._err = tempfile.NamedTemporaryFile(  # noqa: SIM115 — closed in close()
            prefix="jcz_stderr_", suffix=".log", mode="w+", delete=False)
        self._p = subprocess.Popen(
            [java, "-jar", str(self.jar)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._err,
            text=True, bufsize=1,
        )
        self._send_raw(f"%load {self.tiles}")

    # --- plumbing ---------------------------------------------------------- #
    def _send_raw(self, line: str) -> None:
        assert self._p.stdin is not None
        self._p.stdin.write(line + "\n")
        self._p.stdin.flush()

    def _recv(self) -> dict:
        assert self._p.stdout is not None
        line = self._p.stdout.readline()
        if not line.strip():
            raise JczError(
                f"engine emitted no state line (exit={self._p.poll()}); "
                f"stderr tail: {self.stderr_text()[-600:]!r}")
        return json.loads(line)

    def send(self, mtype: str, payload: dict | None = None) -> dict:
        """Send one message, return the resulting full game state."""
        self._send_raw(json.dumps({"type": mtype, "payload": payload or {}}))
        try:
            return self._recv()
        except JczError as e:
            raise JczError(f"{e} after {mtype} {json.dumps(payload)}") from None

    # --- game lifecycle ---------------------------------------------------- #
    def setup(self, draw_order: list[str], start_tile: str, start_rotation: int = 0,
              players: int = 2, farmers: bool = True, followers: int = 7) -> dict:
        """Begin a game with a forced deck.

        ``draw_order`` is the tile sequence AFTER the start tile, as JCZ ids; the
        driver appends the ``"#END"`` sentinel. ``start_tile`` is pre-placed at
        ``[0,0]`` (JCZ's origin), which is also our ``starting_position``.
        """
        payload = {
            "players": int(players),
            "initialRandom": 0.5,
            "sets": {"basic:2": 1},
            "elements": {"small-follower": int(followers), "farmers": bool(farmers)},
            "rules": {},
            "start": [{"tile": start_tile, "x": 0, "y": 0, "rotation": int(start_rotation)}],
            "gameAnnotations": {"tilePack": {
                "className": "com.jcloisterzone.debug.ForcedDrawTilePack",
                "params": {"drawOrder": list(draw_order) + ["#END"]},
            }},
        }
        return self.send("GAME_SETUP", payload)

    def place_tile(self, tile_id: str, rotation_str: str, position: list[int]) -> dict:
        return self.send("PLACE_TILE", {"tileId": tile_id, "rotation": rotation_str,
                                        "position": list(position)})

    def deploy_meeple(self, option: dict, meeple_id: str) -> dict:
        """``option`` is one entry of a ``Meeple`` action item, passed through whole
        (it already has the position/location/feature triple the parser demands)."""
        return self.send("DEPLOY_MEEPLE", {
            "pointer": {"position": option["position"], "location": option["location"],
                        "feature": option["feature"]},
            "meepleId": meeple_id,
        })

    def pass_(self) -> dict:
        return self.send("PASS", {})

    def commit(self) -> dict:
        return self.send("COMMIT", {})

    # --- teardown ---------------------------------------------------------- #
    def close(self) -> None:
        try:
            if self._p.stdin:
                self._p.stdin.close()
        except Exception:
            pass
        try:
            self._p.terminate()
            self._p.wait(timeout=5)
        except Exception:
            self._p.kill()
        try:
            self._err.close()
            os.unlink(self._err.name)
        except Exception:
            pass

    def stderr_text(self) -> str:
        """Whatever the JVM has written to stderr so far (stack traces on refusal)."""
        try:
            self._err.flush()
            with open(self._err.name) as fh:
                return fh.read()
        except Exception:
            return ""

    def __enter__(self) -> "JczEngine":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# state accessors — thin, so the differ reads intent not JSON paths             #
# --------------------------------------------------------------------------- #
def scores(state: dict) -> list[int]:
    return [int(p.get("points", 0)) for p in state.get("players", [])]


def free_meeple_id(state: dict, player: int) -> str | None:
    """``[count, next_id]`` for the player's SmallFollower supply; None if empty."""
    try:
        cnt, mid = state["players"][player]["meeples"]["SmallFollower"]
    except (KeyError, IndexError, ValueError):
        return None
    return mid if int(cnt) > 0 else None


def action_items(state: dict, kind: str) -> list[dict]:
    act = state.get("action") or {}
    return [it for it in (act.get("items") or []) if it.get("type") == kind]


def wants_confirm(state: dict) -> bool:
    return bool(action_items(state, "Confirm"))


def tile_options(state: dict) -> tuple[str | None, set[tuple[int, int, int]]]:
    """``(tileId, {(x, y, rotation_degrees)})`` for the pending TilePlacement."""
    items = action_items(state, "TilePlacement")
    if not items:
        return None, set()
    it = items[0]
    opts = {(o["position"][0], o["position"][1], int(r))
            for o in it.get("options", []) for r in o.get("rotations", [])}
    return it.get("tileId"), opts


def meeple_options(state: dict) -> list[dict]:
    out: list[dict] = []
    for it in action_items(state, "Meeple"):
        out.extend(it.get("options", []))
    return out


def is_over(state: dict) -> bool:
    return str(state.get("phase", "")).startswith("GameOver")
