"""F-c — the Python end of the fail-loud action-window diagnostic.

`measurement/window_truncation_20260813/DESIGN.md` §7 F-c: the Rust
`Game::legal_mask` drops out-of-window legal actions silently, so a node whose
WHOLE legal move list falls outside the 25x25 window is expanded with an empty
action set and the next descent through it dies on a bare

    RuntimeError: PUCT reached a node with no valid actions (Python IndexError)

which says nothing about the cause and cannot be told apart from any other
empty-action-set bug.  §6-P3 fired by OCCURRENCE in production on 2026-08-13
(deck 126000000135, seat 0 -- `measurement/joshuabot_20260812/
CONFIRM_EXCLUSIONS.md`), which is what licenses this fix.  F-c does not make the
search stronger and is not claimed to: it converts a silent, unattributable
failure into a typed, reconstructable one.

THREE PIECES, and this module is the third:

1. `carc_core::search::window_diag` builds the diagnosis on the ERROR PATH ONLY
   (mask counters, window, phase, depth, the descent that reached the node, the
   dropped placements in engine coordinates, and the CAUSE).
2. `carc_rs.WindowTruncationError` -- a `RuntimeError` SUBCLASS, so every
   existing `except RuntimeError` / `except BaseException` guard is unaffected --
   is raised only when the cause is `window_truncation`.  Other empty-mask causes
   stay a plain `RuntimeError` and carry `cause` in their payload.  The TYPE is
   the discriminator (requirement 3).
3. This module joins on what the search cannot know -- the DECK SEED, the SEAT
   and the GLOBAL PLY -- and writes a record in the schema
   `scripts/measurement_infra/reconstruct_crash_root.py` emits and
   `scripts/measurement_infra/window_truncation_census.py` consumes, so a live
   crash lands as a census root with no archaeology.

⚠️ **`move_idx` IS NOT THE PLY.**  The determinization stream is seeded from
`det_seed_base(seed, move_idx)`, where `move_idx` counts THE AGENT'S OWN
decisions; the 2026-08-13 crash is at global ply 119 = the champion's
`move_idx` 59.  Feeding the ply as `move_idx` draws eight different worlds and
does not reproduce the crash.  So this module NEVER derives one from the other:
`crash_root_record` takes `move_idx` explicitly, records `move_idx_source`, and
writes `move_idx: None` when the caller genuinely does not know it (which the
census reports as a `ply` fallback -- valid for a rate, invalid for reproducing
a named decision).

Default-safe: nothing here runs unless the search has already raised.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

__all__ = [
    "DIAG_MARKER",
    "SCHEMA",
    "capture",
    "crash_root_record",
    "diag_cause",
    "emit_crash_root",
    "is_empty_mask_error",
    "is_window_truncation",
    "note_sentinel",
    "parse_diag",
    "sink_path",
    "window_truncation_error_type",
]

REPO = Path(__file__).resolve().parents[2]

#: The token `carc_core::search::EMPTY_MASK_DIAG_MARKER` writes.  A RECORDED
#: CONTRACT -- both sides must move together.
DIAG_MARKER = "EMPTY_MASK_DIAG="

#: Same family string `reconstruct_crash_root.py` roots are read under.
SCHEMA = "window_truncation/crash_root/v1"

#: Where a live crash root is appended when no `CARCASSONNE_WINDOW_DIAG_DIR` is
#: set.  Under the census's own directory, since that is the reader.
DEFAULT_SINK_DIR = REPO / "measurement" / "window_truncation_20260813" / "live"
SINK_FILE = "crash_roots.jsonl"


def window_truncation_error_type():
    """`carc_rs.WindowTruncationError`, or `None` on a pre-F-c wheel.

    Import-guarded on purpose: this module must stay usable (message-based) when
    `carc_rs` is absent or older than the fix -- e.g. a box whose wheel has not
    been rebuilt yet.
    """
    try:
        import carc_rs
    except Exception:                                    # pragma: no cover
        return None
    return getattr(carc_rs, "WindowTruncationError", None)


def parse_diag(exc) -> dict | None:
    """The machine payload carried by an empty-mask error, or `None`.

    Accepts the exception or its message.  Message-based rather than
    attribute-based so a record written by one build is readable by any other.
    """
    text = exc if isinstance(exc, str) else str(exc)
    i = text.find(DIAG_MARKER)
    if i < 0:
        return None
    try:
        return json.loads(text[i + len(DIAG_MARKER):])
    except Exception:                                    # pragma: no cover
        return None


def diag_cause(exc) -> str | None:
    """`"window_truncation"` | `"no_engine_actions"` | `"mask_not_empty"` | None."""
    d = parse_diag(exc)
    return None if d is None else d.get("cause")


def is_empty_mask_error(exc) -> bool:
    """Did the search die on a node with an empty encoded action set?"""
    return parse_diag(exc) is not None


def is_window_truncation(exc) -> bool:
    """Is this the DEFECT -- an empty action set the WINDOW caused?

    Type first (the wheel's own verdict), payload second (so a record replayed
    out of a log, or an error crossing a process boundary as a plain
    `RuntimeError`, still classifies).
    """
    et = window_truncation_error_type()
    if et is not None and isinstance(exc, et):
        return True
    return diag_cause(exc) == "window_truncation"


def sink_path(sink=None) -> Path:
    """Resolve the crash-root sink.

    ⚠️ NO `[ -d ]` PROBING.  `window_truncation_census`'s laptop dispatch died
    `rc=13` because both `/mnt/c/carc-shared` and `/mnt/carc-shared` EXIST there
    and are different filesystems, so directory existence cannot pick between
    candidates.  This resolves from an explicit argument, else one env var, else
    one repo-relative default -- never by probing alternatives.
    """
    if sink is not None:
        return Path(sink)
    env = os.environ.get("CARCASSONNE_WINDOW_DIAG_DIR")
    base = Path(env) if env else DEFAULT_SINK_DIR
    return base / SINK_FILE


def _diag_enabled() -> bool:
    return os.environ.get("CARCASSONNE_WINDOW_DIAG", "1") not in ("0", "false", "no")


def crash_root_record(
    exc,
    *,
    deck_seed,
    ply: int,
    actions,
    player_to_move,
    move_idx,
    move_idx_source: str,
    champion_seed=None,
    rules_profile=None,
    checksum=None,
    raiser_is_champion=None,
    seats=None,
    extra=None,
) -> dict:
    """Build a census-ready root from a live empty-mask raise.

    The field set is `reconstruct_crash_root.py`'s output verbatim -- `rid`,
    `deck_seed`, `ply`, `actions`, `player_to_move`, `move_idx`,
    `champion_seed`, `raised`, `raiser_is_champion`, `exc_type`, `exc`,
    `traceback`, `rules_profile`, `checksum` -- so
    `window_truncation_census.py --roots <this file>` reads it directly
    (`deck_seed`/`ply`/`actions` required, `checksum` gates fidelity,
    `move_idx` seeds the determinizations).  `window_diag` is additive.

    `ply` is the GLOBAL ply (`len(actions)`); `move_idx` is the AGENT's own
    decision counter.  Passing the ply as `move_idx` is the recorded trap -- so
    it is not defaulted here, and `move_idx_source` states where it came from.
    """
    actions = [int(a) for a in actions]
    if int(ply) != len(actions):
        raise ValueError(
            f"ply {ply} != len(actions) {len(actions)} -- `ply` is the GLOBAL ply, "
            "i.e. exactly the length of the applied-action prefix; the census "
            "slices actions[:ply] and would seat a different position.")
    if move_idx is not None and move_idx_source not in ("agent", "caller"):
        raise ValueError("a known move_idx must say where it came from "
                         "('agent' | 'caller')")
    if move_idx is None and move_idx_source != "unavailable":
        raise ValueError("move_idx_source must be 'unavailable' when move_idx is None "
                         "-- NEVER substitute the ply (det_seed_base(seed, move_idx))")
    diag = parse_diag(exc)
    rec = {
        "schema": SCHEMA,
        "rid": f"crash_{deck_seed}_p{int(ply)}",
        "deck_seed": int(deck_seed),
        "ply": int(ply),
        "actions": actions,
        "player_to_move": None if player_to_move is None else int(player_to_move),
        "move_idx": None if move_idx is None else int(move_idx),
        "move_idx_source": move_idx_source,
        "champion_seed": None if champion_seed is None else int(champion_seed),
        "rules_profile": rules_profile,
        "checksum": checksum,
        "raised": True,
        "raiser_is_champion": raiser_is_champion,
        "exc_type": type(exc).__name__ if isinstance(exc, BaseException) else "str",
        "exc": str(exc)[:4000],
        "window_truncation": is_window_truncation(exc),
        "window_diag": diag,
        "recorded_at": time.time(),
    }
    if seats:
        rec["seats"] = dict(seats)
    if isinstance(exc, BaseException):
        rec["traceback"] = "".join(traceback.format_exception(exc))[-3000:]
    if extra:
        rec.update(extra)
    return rec


def emit_crash_root(rec: dict, sink=None) -> Path | None:
    """Append one root to the sink.  Never raises -- a diagnostic that can kill
    the run it is diagnosing is worse than no diagnostic.  Returns the path, or
    `None` when disabled or when the write failed (a warning goes to stderr).
    """
    if not _diag_enabled():
        return None
    path = sink_path(sink)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(rec, default=str) + "\n"
        # One O_APPEND write: concurrent cells (h2h runs a pool) interleave
        # whole lines rather than fragments.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode())
        finally:
            os.close(fd)
        return path
    except Exception as e:                               # pragma: no cover
        print(f"[window_truncation] FAILED to record the crash root at {path}: "
              f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return None


def note_sentinel(sentinel, ply: int, exc) -> bool:
    """Feed `wall_sentinel`'s FACE 5 from a rust-search truncation.

    DESIGN §7 F-c: "the clean version of F-c is 'give `wall_sentinel` a face-5
    counter that the Rust search feeds'".  `wall_sentinel` already counts face 5
    for the Python engine's `WindowOverflowError`; this routes the Rust
    search-internal event into the same counter, so one number covers both
    engines.  Returns whether it fired.
    """
    if sentinel is None or not is_empty_mask_error(exc):
        return False
    d = parse_diag(exc) or {}
    sentinel.note_window_overflow(
        int(ply),
        f"rust search: cause={d.get('cause')} n_total={d.get('n_total')} "
        f"n_overflow={d.get('n_overflow')} depth={d.get('depth')} "
        f"window={d.get('window_offset')}")
    return True


@contextlib.contextmanager
def capture(
    *,
    deck_seed,
    ply: int,
    actions,
    player_to_move=None,
    agent=None,
    move_idx=None,
    champion_seed=None,
    rules_profile=None,
    checksum=None,
    raiser_is_champion=None,
    seats=None,
    sentinel=None,
    extra=None,
    sink=None,
):
    """Wrap one `choose_action` call so an empty-mask raise lands reconstructable.

    ALWAYS re-raises -- this is fail-LOUD, not fail-soft.  On the way out it
    attaches `exc.window_root_record` (the census root) and
    `exc.window_root_path` (where it was written), so a caller that already has
    an exception handler can record the cause without re-parsing.

    `move_idx` is read off the agent (`RustFairAgent.move_idx`, which is the
    Rust-side counter) when not passed; if neither is available the record says
    so rather than substituting the ply.
    """
    try:
        yield
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:                          # noqa: BLE001
        if not is_empty_mask_error(exc):
            raise
        mi, src = move_idx, "caller"
        if mi is None:
            mi = getattr(agent, "move_idx", None)
            src = "agent" if mi is not None else "unavailable"
        try:
            rec = crash_root_record(
                exc, deck_seed=deck_seed, ply=ply, actions=actions,
                player_to_move=player_to_move,
                move_idx=None if mi is None else int(mi), move_idx_source=src,
                champion_seed=champion_seed, rules_profile=rules_profile,
                checksum=checksum, raiser_is_champion=raiser_is_champion,
                seats=seats, extra=extra)
            path = emit_crash_root(rec, sink=sink)
            exc.window_root_record = rec
            exc.window_root_path = None if path is None else str(path)
            note_sentinel(sentinel, ply, exc)
            print(f"[window_truncation] {rec['rid']} cause="
                  f"{diag_cause(exc)} -> {path}", file=sys.stderr, flush=True)
        except Exception as e:                            # pragma: no cover
            print(f"[window_truncation] could not build the crash root: "
                  f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise
