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

# The A2/A3 vocabularies. Left element is the engine of record in both cases, so
# a profile that says nothing new adds no `Game(...)` argument.
_CLOISTER_SCANS = ("drifting", "fixed")          # RF-D-1: drifting == today
_UNPLACEABLE_RULES = ("next_player", "redraw")   # RF-D-2: next_player == today

# R9 is a DATA flag, not a Game kwarg: `base_deck` derives it at IMPORT time from
# the process environment and the Rust registry latches it in a `OnceLock`, so it
# can only be set BEFORE the first import — there is no per-Game seam to thread
# it through (see the D0/R9 merge). The profile therefore cannot *apply* it; it
# can only declare that a leg is expected to carry it, and stamp whether the
# process actually did. Spellings mirror `base_deck._r9_env_on` /
# `carc_rs.r9_enabled`; `test_rules_profile.py` pins them equal.
R9_ENV_VAR = "CARCASSONNE_FIX_R9"
_R9_TRUTHY = ("1", "true", "yes", "on")


def r9_env_on(environ=None) -> bool:
    """Is `CARCASSONNE_FIX_R9` on in this process? (observation, not control)."""
    raw = (os.environ if environ is None else environ).get(R9_ENV_VAR, "")
    return str(raw).strip().lower() in _R9_TRUTHY


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
    # R9 (D0) rides OUTSIDE the profile — env-latched at import, see R9_ENV_VAR.
    # True means "a leg on this profile is expected to export CARCASSONNE_FIX_R9";
    # `as_manifest` stamps expected AND observed so a leg that forgot is visible
    # in the artifact rather than only in the operator's memory.
    r9_env_expected: bool = False
    # WC tie-break (BACKLOG.md 2026-08-03 "WC tie-break rule flag"). OPT-IN,
    # DEFAULT OFF on every shipped profile below, including `fixed_v1` — this
    # is a terminal-scoring-only rule divergence the Phase-B bundle does NOT
    # cover, and folding it into a `fixed_v2` bundle is an explicitly SEPARATE
    # decision (BACKLOG: "would become part of a future fixed_v2 profile
    # bundle, adoption a separate decision"), not made by adding this field.
    wc_tiebreak: bool = False

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
        # A2 (F9) — `Game(cloister_scan_fix=True)`. Named for the kwarg
        # `game_wrapper.Game` actually landed, not for this module's vocabulary.
        if self.cloister_scan == "fixed":
            kw["cloister_scan_fix"] = True
        # A3 (F9) — `Game(draw_rule="redraw")`. `Game` validates the string and
        # raises on anything it does not know, so a typo cannot degrade to the
        # engine rule silently.
        if self.unplaceable_tile == "redraw":
            kw["draw_rule"] = "redraw"
        # WC tie-break — `Game(wc_tiebreak=True)`. No shipped profile sets this
        # today, so this stays the no-op every profile's `game_kwargs()`
        # identity rests on (Gate A0 for `walled`, and the "adopts nothing"
        # contract for every other named profile including `fixed_v1`).
        if self.wc_tiebreak:
            kw["wc_tiebreak"] = True
        return kw

    def as_manifest(self) -> dict:
        d = asdict(self)
        # `wc_tiebreak` is a plain dataclass field (not a derived @property like
        # `fixed_start_tile`/`recentred` above), so `asdict()` already stamps it
        # unconditionally — absent-is-unknown-not-zero holds for free: every
        # manifest states True or False explicitly, never omits the key.
        d["fixed_start_tile"] = self.fixed_start_tile
        d["recentred"] = self.recentred
        # R9 is env-latched and cannot be applied from here, so the manifest
        # carries the CONTRACT and the OBSERVATION side by side: `r9_env_ok`
        # False on a fixed_v1 artifact means the leg ran without the env var and
        # its farm scoring is the unfixed data, whatever the profile name says.
        d["r9_env_var"] = R9_ENV_VAR
        d["r9_env_observed"] = r9_env_on()
        d["r9_env_ok"] = (d["r9_env_observed"] == self.r9_env_expected)
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
    # ----------------------------------------------------------------------- #
    # APP PROVENANCE, not a candidate. `app_aug2` is the rules the 2026-08-02  #
    # Android build actually plays — it exists so pre-fixed_v1 phone archives   #
    # can be graded honestly, and for nothing else.                             #
    # ----------------------------------------------------------------------- #
    "app_aug2": replace(
        _WALLED, name="app_aug2",
        grid_rule="centered18", start_row=18,     # W2 / A1 — the app recentring
        start_rule="retail",                      # A4 — the retail 'D' start tile
        # ...and NOTHING else: drifting cloister scan, next_player on an
        # unplaceable tile, R9 off — all inherited from `_WALLED` on purpose.
        note=(
            "APP PROVENANCE (added 2026-08-05) — the rules the 2026-08-02 Android "
            "build actually plays: centered18 grid + retail start tile ONLY, "
            "WITHOUT the A2 (fixed cloister scan), A3 (redraw) and R9 levers, which "
            "that build does not carry. It is NOT a candidate and ADOPTS NOTHING: no "
            "elo, no eval leg and no default has ever run on it, and none may. It "
            "exists for exactly one reason — an archive from a pre-fixed_v1 phone "
            "build stamps (start_rule=retail, grid_rule=centered18) and NOTHING else, "
            "which used to resolve uniquely to `fixed_v1` and graded such a game with "
            "R9 ON + fixed cloister + redraw, i.e. under different farm adjacency than "
            "it was played under (the 2026-08-05 EV-loss retraction). The registry's "
            "key space could not express a build that exists; this row makes it able "
            "to. The DISCRIMINATOR is the archive's own stamp: the fixed_v1 app build "
            "writes `rules_profile`/`cloister_rule`/`farm_rule` into every archive, so "
            "their ABSENCE means a pre-fixed_v1 build and MUST NOT resolve to "
            "`fixed_v1`. Being non-walled it also refuses a results.csv row unless the "
            "exp_id names it, which is the correct behaviour for a provenance profile."
        ),
    ),
    # ----------------------------------------------------------------------- #
    # THE PHASE-B BUNDLE. All four rules levers at once; adopts nothing.       #
    # ----------------------------------------------------------------------- #
    "fixed_v1": replace(
        _WALLED, name="fixed_v1",
        grid_rule="centered18", start_row=18,     # W2 / A1
        start_rule="retail",                      # A4
        cloister_scan="fixed",                    # A2 (RF-D-1)
        unplaceable_tile="redraw",                # A3 (RF-D-2)
        r9_env_expected=True,                     # D0/R9, env-latched (below)
        note=(
            "PHASE-B BUNDLE (spec J3) — the four rules-fidelity levers composed: "
            "centered18 grid + retail start tile + fixed cloister scan + redraw on "
            "an unplaceable tile. NOT A DEFAULT: every elo of record is a `walled` "
            "number and this profile refuses a results.csv row unless the exp_id "
            "names it. "
            "⚠️ THE BUNDLE IS DELIBERATELY NOT ORTHOGONAL: A3 and A4 interact, and "
            "retail ABSORBS ~5.6x of A3's blast radius (A3's own gate measured the "
            "redraw rate at 7.8/100 games under the engine start rule vs 1.4/100 "
            "under retail — an unplaceable tile is almost purely a first-move "
            "event, so which tile starts the board decides it). Bundling them is "
            "the point here; a SINGLE-FLAG attribution ladder must therefore run "
            "the A3 cell at a STATED start rule, not against this profile. "
            "⚠️ R9 IS NOT IN THIS PROFILE AND CANNOT BE: `base_deck` derives the "
            "farm data at import time and the Rust registry latches a OnceLock, so "
            "CARCASSONNE_FIX_R9 must be exported in the ENVIRONMENT before the "
            "process starts. `r9_env_expected=True` records that a fixed_v1 leg "
            "owes that env var; `as_manifest()` stamps r9_env_observed/r9_env_ok "
            "so an artifact from a leg that forgot it is detectable after the fact."
        ),
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
    # A2 and A3 landed 2026-08-03 (the F9 compose merge) and are honoured by
    # `game_kwargs()` above, so the "not built" refusals are gone. What remains
    # is a VOCABULARY check — an unrecognised value must raise here rather than
    # fall through `game_kwargs`'s equality tests and silently play the engine
    # rule, which is the exact silent class F9 exists to kill.
    if prof.cloister_scan not in _CLOISTER_SCANS:
        raise RulesProfileError(
            f"profile {prof.name!r} asks for cloister_scan={prof.cloister_scan!r}; "
            f"known: {list(_CLOISTER_SCANS)}")
    if prof.unplaceable_tile not in _UNPLACEABLE_RULES:
        raise RulesProfileError(
            f"profile {prof.name!r} asks for unplaceable_tile={prof.unplaceable_tile!r}; "
            f"known: {list(_UNPLACEABLE_RULES)}")
    # `wc_tiebreak` is a plain bool, not a string vocabulary like cloister_scan/
    # unplaceable_tile above — every value a bool can hold (True/False) is
    # honourable end-to-end in `game_wrapper.Game`, so there is no unrecognised
    # value to refuse here. Named explicitly (rather than left unmentioned) so
    # the validator is seen to KNOW about the field, not silently ignore it —
    # if `wc_tiebreak` ever grows a non-bool vocabulary, its check belongs here
    # next to the other two.


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
