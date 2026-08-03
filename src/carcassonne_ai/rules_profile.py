"""F9 A0 — the ONE resolved rules profile, threaded to every ``Game(...)``.

Why this module exists (docs/F9_BUILD_SPEC_20260802.md §A0). The two n=400 elo
harnesses and the gen emitter build ~40 ``Game(...)`` objects between them and
**could not express a rules flag at all** — every call rode the defaults, so a
fixed-rules cell was unrunnable and, worse, a *partially* applied one would have
been unnoticeable. F9's whole subject matter is silent rule divergence, so the
plumbing is built the way the spec demands:

  * **named profiles only** — never a loose pile of independent CLI flags, because
    an unstamped or half-applied profile is precisely the failure being measured;
  * **resolved once per run** in ``main()`` and published through the process
    environment, so ``multiprocessing`` spawn children inherit the SAME profile
    (a worker that re-resolved from argv could disagree with the manifest — the
    identical trap the ``--backend auto`` resolution already documents);
  * **stamped verbatim into every ``manifest.json``** by ``run_manifest``;
  * **fail-loud at the results.csv boundary** (``scripts/append_result_row.py``):
    a non-``walled`` profile refuses a row unless the profile name is in the
    ``exp_id``, so a fixed-rules number cannot silently enter the walled record.

DEFAULT-OFF CONTRACT. ``walled`` is today's engine of record — engine6 grid, the
engine's random start-tile convention, 35x35, window 25 — and resolves to the
*absence* of every optional argument, so with no ``--rules-profile`` the harnesses
construct exactly the calls they always did. That identity is what Gate A0 checks;
it is a property of ``_UNSET``-shaped fields here, not of an assertion elsewhere.

Building a profile ADOPTS NOTHING (spec §7). ``centered18`` exists so the A1-a
probe can generate an *uncensored* champion-play trajectory to price the wall
from; the global engine default stays ``walled`` until J5 says otherwise.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace

# The environment channel. Set by `activate()`; read by `active()`. Chosen over a
# module global because `mp.Pool` on spawn re-imports this module in a fresh
# interpreter — env survives that, a global does not.
ENV_VAR = "CARCASSONNE_RULES_PROFILE"

DEFAULT_PROFILE = "walled"

# The engine of record's geometry (mirrors game_wrapper.ENGINE_* / the Rust
# GameConfig defaults; duplicated here only to keep this module import-cycle free
# — `test_rules_profile.py` pins them equal).
_ENGINE_START_ROW, _ENGINE_START_COL = 6, 15
_ENGINE_BOARD_ROWS, _ENGINE_BOARD_COLS = 35, 35
_DEFAULT_WINDOW = 25


@dataclass(frozen=True)
class RulesProfile:
    """A fully resolved rules profile. Every field is stamped in the manifest.

    ``start_row``/``start_col``/``fixed_start_tile`` are deliberately shaped as
    "say nothing to the engine" when they match the engine default: ``Game`` only
    forwards them when they differ, which is what keeps the ``walled`` path
    byte-identical to the pre-F9 code.
    """

    name: str
    # --- A1 the wall -------------------------------------------------------- #
    grid_rule: str            # "engine6" | "centered18" (the android_bridge vocabulary)
    start_row: int
    start_col: int
    board_rows: int
    board_cols: int
    # --- A4 retail start tile ----------------------------------------------- #
    start_rule: str           # "engine" | "retail" (the android_bridge / Rust vocabulary)
    # --- J4, a SEPARATE decision (spec §A1): representation cap, not a rules cap #
    window_size: int
    # --- A2 / A3, built later; carried now so a profile is never half-shaped -- #
    cloister_scan: str        # "drifting" (today, RF-D-1) | "fixed" (A2)
    unplaceable_tile: str     # "next_player" (today, RF-D-2) | "redraw" (A3)
    # Free-text: why this profile exists / what it is NOT. Manifest-visible.
    note: str = ""

    # --- derived ------------------------------------------------------------ #
    @property
    def is_walled(self) -> bool:
        """True only for the engine of record. The results.csv guard keys on this."""
        return self.name == DEFAULT_PROFILE

    @property
    def fixed_start_tile(self) -> bool:
        return self.start_rule == "retail"

    @property
    def recentred(self) -> bool:
        return (self.start_row, self.start_col) != (_ENGINE_START_ROW, _ENGINE_START_COL)

    def game_kwargs(self) -> dict:
        """The ``Game(...)`` kwargs this profile implies — EMPTY for ``walled``.

        Empty is the point: ``Game`` applies these only where the caller said
        nothing, so under ``walled`` no argument is added and the constructed
        state is the same object graph the pre-F9 harness built.
        """
        kw: dict = {}
        if self.recentred:
            kw["start_row"] = self.start_row
            kw["start_col"] = self.start_col
        if self.fixed_start_tile:
            kw["fixed_start_tile"] = True
        if self.window_size != _DEFAULT_WINDOW:
            kw["window_size"] = self.window_size
        return kw

    def as_manifest(self) -> dict:
        d = asdict(self)
        d["fixed_start_tile"] = self.fixed_start_tile
        d["recentred"] = self.recentred
        return d


# --------------------------------------------------------------------------- #
# The registry. Named profiles ONLY. Adding a row here is a build step; adopting #
# one for the eval/desktop path is J5 and is not this file's business.          #
# --------------------------------------------------------------------------- #
_WALLED = RulesProfile(
    name="walled",
    grid_rule="engine6",
    start_row=_ENGINE_START_ROW, start_col=_ENGINE_START_COL,
    board_rows=_ENGINE_BOARD_ROWS, board_cols=_ENGINE_BOARD_COLS,
    start_rule="engine",
    window_size=_DEFAULT_WINDOW,
    cloister_scan="drifting",
    unplaceable_tile="next_player",
    note="the engine of record — every elo ever measured is a walled number",
)

PROFILES: dict[str, RulesProfile] = {
    "walled": _WALLED,
    # W2 candidate (spec §A1). Already built, G5-gated and app-shipped; NOT
    # adopted for eval. Its reason to exist today is the A1-a probe: a champion
    # trajectory generated at row 18 is UNCENSORED by the wall, so re-pricing the
    # row-6 grid from it answers "would champion play have hit the wall" honestly,
    # where a row-6 trajectory can only answer it after the wall already bent it.
    "centered18": replace(
        _WALLED, name="centered18", grid_rule="centered18", start_row=18,
        note="W2 candidate (spec A1) — recentre only, EVEN shift; probe-only, adopts nothing",
    ),
    # A4 (retail start tile) — already built and G5-gated; in or out of the
    # Phase-B bundle is J3.
    "retail": replace(
        _WALLED, name="retail", start_rule="retail",
        note="A4 candidate (spec A1/A4) — retail fixed 'D' start tile; costs CRN deck pairing",
    ),
}


class RulesProfileError(ValueError):
    """A profile that cannot be honoured. Always raised, never warned."""


def known() -> list[str]:
    return sorted(PROFILES)


def resolve(name: str | None) -> RulesProfile:
    """Name -> resolved profile. ``None`` means the default (``walled``).

    Raises rather than guessing: an unrecognised profile is exactly the silent
    class F9 exists to kill.
    """
    key = DEFAULT_PROFILE if name is None or name == "" else str(name)
    try:
        prof = PROFILES[key]
    except KeyError:
        raise RulesProfileError(
            f"unknown rules_profile {key!r}; known: {known()}") from None
    _check_supported(prof)
    return prof


def _check_supported(prof: RulesProfile) -> None:
    """Refuse a profile whose fields the CODE cannot yet honour end to end.

    A profile that is only *partly* applied is worse than no profile at all, so
    every field not yet wired fails loud here instead of being ignored. These
    lift as A1-b/A2/A3 land.
    """
    if (prof.board_rows, prof.board_cols) != (_ENGINE_BOARD_ROWS, _ENGINE_BOARD_COLS):
        raise RulesProfileError(
            f"profile {prof.name!r} asks for a {prof.board_rows}x{prof.board_cols} "
            "board: runtime board size is W3 (spec A1-b) and is NOT built — the "
            "Rust BOARD_ROWS/COLS are compile-time consts and N_CELLS is on the "
            "leaf hot path. Refusing rather than silently playing 35x35.")
    if prof.cloister_scan != "drifting":
        raise RulesProfileError(
            f"profile {prof.name!r} asks for cloister_scan={prof.cloister_scan!r}: "
            "the A2 fix is not built. Refusing rather than silently deferring.")
    if prof.unplaceable_tile != "next_player":
        raise RulesProfileError(
            f"profile {prof.name!r} asks for unplaceable_tile={prof.unplaceable_tile!r}: "
            "the A3 redraw is not built. Refusing rather than silently passing the turn.")


# --------------------------------------------------------------------------- #
# Process-wide activation. `main()` calls `activate()` ONCE; workers inherit via #
# the environment, so the manifest and every worker cannot disagree.            #
# --------------------------------------------------------------------------- #
_cache: RulesProfile | None = None
_cache_key: str | None = None


def activate(name: str | None) -> RulesProfile:
    """Resolve `name`, publish it to the environment, and return it."""
    prof = resolve(name)
    os.environ[ENV_VAR] = prof.name
    global _cache, _cache_key
    _cache, _cache_key = prof, prof.name
    return prof


def active() -> RulesProfile:
    """The profile in force in THIS process (env-backed; spawn-safe)."""
    global _cache, _cache_key
    key = os.environ.get(ENV_VAR) or DEFAULT_PROFILE
    if _cache is None or _cache_key != key:
        _cache = resolve(key)
        _cache_key = key
    return _cache


def reset() -> None:
    """Test helper: drop the activation (back to the default)."""
    os.environ.pop(ENV_VAR, None)
    global _cache, _cache_key
    _cache = _cache_key = None


def add_argument(ap, *, flag: str = "--rules-profile") -> None:
    """Add the ONE CLI entry point. Named choices only — no loose flags."""
    ap.add_argument(
        flag, choices=known(), default=DEFAULT_PROFILE,
        help="F9 A0 resolved rules profile, stamped in manifest.json. "
             "'walled' (default) = the engine of record and byte-identical to "
             "pre-F9. A non-walled profile REFUSES an experiments/results.csv row "
             "unless the profile name is in the exp_id (spec A0).")
