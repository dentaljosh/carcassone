"""JSON bridge between the Kotlin/Compose app and the production Carcassonne champion.

This is the ONLY hand-written Python under ``android/``. Everything else in the
on-device bundle is copied verbatim from the repo by ``android/tools/sync_python.py``.

DESIGN CONTRACTS
----------------
1. **Importable on desktop.** No ``android`` / ``java`` / ``com.chaquo`` imports, so the
   whole API is pytest-able (``tests/android/test_bridge.py``) and drivable from
   ``android/tools/smoke_selfplay.py``.
2. **Production leaf env FIRST.** The v2.7/v2.9 leaf reads ``CARCASSONNE_*`` knobs at
   *library import time*; ``champion_factory``'s verify RAISES if they were not set. So
   this module applies them via ``os.environ.setdefault`` at module top, BEFORE the
   first ``carcassonne_ai`` import. The values are a literal copy of
   ``scripts/human_anchor/env_preamble.PROD_ENV`` (that file is not in the on-device
   bundle); ``tests/android/test_bridge.py::test_prod_env_matches_repo_preamble``
   asserts the copy has not drifted.
3. **The YAML is the champion.** No strength knob is hardcoded here.
   ``champion_factory.PRODUCTION_YAML`` is a module global resolved at call time, so we
   point it at the bundled ``carcassonne_ai/data/PRODUCTION.yaml`` when that exists
   (device) and leave the repo's ``governance/PRODUCTION.yaml`` otherwise (desktop).
4. **All in/out is a JSON string** — Chaquopy marshals ``str`` cleanly and nothing else
   needs a type mapping. Every response is a JSON object carrying ``ok``; failures are
   ``{"ok": false, "error": {"code", "message"}}`` and never raise across the bridge.
5. **Determinism / save-restore.** The engine touches the global ``random`` stream in
   exactly one place (the deck shuffle inside ``get_init_board``), so a game is fully
   determined by ``(deck_seed, action_log)`` — the ``root_replay.py`` contract. Restore
   replays the log and re-seats the agent's ``_move_idx`` (its per-move search seeds are
   derived from it) and its exact-endgame latch.

THREADING (what Kotlin must respect)
------------------------------------
``new_game`` / ``apply_action`` / ``ai_move`` / ``save_game`` / ``restore_game`` mutate
the single module session and must all run on ONE thread (the app uses a single-thread
coroutine dispatcher). ``get_progress`` is the sole exception: it reads module-global
ints only and is safe to poll from the UI thread while ``ai_move`` blocks.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. Production leaf env — MUST precede any carcassonne_ai import.             #
#    Literal copy of scripts/human_anchor/env_preamble.PROD_ENV (2026-07-27).  #
# --------------------------------------------------------------------------- #
PROD_ENV: dict[str, str] = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
for _k, _v in PROD_ENV.items():
    os.environ.setdefault(_k, _v)
# The knobs as they stood the instant before carcassonne_ai was first imported — i.e.
# the leaf shape this process actually froze into ``virtual_score_v2.DEFAULT_CONFIG``.
# (A later importer may rewrite os.environ; that no longer changes this process's leaf,
# so RESOLVED_ENV, not os.environ, is the honest record for a manifest or a test.)
RESOLVED_ENV: dict[str, str] = {k: os.environ.get(k, "") for k in PROD_ENV}

# --------------------------------------------------------------------------- #
# 1a. THE FARM DATA RULE (F9 "R9"). ⚠️ PROCESS-GLOBAL, LATCHED AT IMPORT —      #
#     this is the ONE rules lever that is not per-game, and the block below is  #
#     the reason it has to be set here rather than in `_Session`.               #
#                                                                              #
# THE BUG. `city_top_straight_road` (RCr) claims two field half-edges that lie  #
# on its OWN city edge, and every farm traversal in the project crosses a       #
# `tile_connection` unconditionally, so a field walks straight THROUGH a city:  #
# two RCr tiles placed city-to-city have their under-city field strips merged   #
# into one farm. `CARCASSONNE_FIX_R9=1` drops those half-edges (derived by      #
# predicate in `base_deck.r9_farm_override`, not hand-typed).                   #
#                                                                              #
# ⚠️ WHY IT CANNOT BE A `Game(...)` KWARG. `base_deck` rewrites its module-level #
# `base_tiles` dict at IMPORT time, and the Rust registry memoises in a         #
# `OnceLock` — neither engine has a per-Game tile table. So the env var must be #
# set BEFORE the first `carcassonne_ai` / `wingedsheep` import, i.e. here, and  #
# it is then frozen for the life of the process. `rules_profile.fixed_v1` says  #
# the same thing at length: R9 is declared by a profile, never applied by one.  #
#                                                                              #
# ⚠️ IT IS BEHAVIOURAL FOR REPLAY, NOT ONLY FOR SCORING. Measured on this tree  #
# (200 random-legal games, same deck seeds, R9 off vs on): 1/200 diverged in    #
# the LEGAL-MASK stream — farm connectivity decides whether a farmer slot is    #
# still free, so a merged farm removes a legal meeple action. The action log    #
# and the final scores diverged with it ([20,22] -> [17,23] at seed 148). That  #
# is why `farm_rule` travels in the save payload and why a record played under  #
# the other rule is REFUSED rather than replayed (see `_Session`).              #
#                                                                              #
# The app plays "r9". `CARC_ANDROID_FARM_RULE=engine` (or setting               #
# `CARCASSONNE_FIX_R9` directly) pins a process to the legacy data, which is    #
# how the desktop suite replays pre-R9 archives byte-identically.               #
# --------------------------------------------------------------------------- #
FARM_RULE_ENGINE = "engine"             # the vendored farm data, unfixed
FARM_RULE_R9 = "r9"                     # the F9/R9 field-on-city-edge fix
FARM_RULE = FARM_RULE_R9                # what a NEW app game uses
FARM_RULE_LEGACY = FARM_RULE_ENGINE     # what a save with no `farm_rule` means
R9_ENV_VAR = "CARCASSONNE_FIX_R9"
# `setdefault`, so an explicit `CARCASSONNE_FIX_R9` in the environment still wins:
# the escape hatch has to be usable by a harness that does not know this constant.
FARM_RULE_REQUESTED: str = os.environ.get("CARC_ANDROID_FARM_RULE", FARM_RULE)
os.environ.setdefault(
    R9_ENV_VAR, "1" if FARM_RULE_REQUESTED == FARM_RULE_R9 else "0")

# On-device endgame-solver NODE budget (measurement/ANDROID_WALLCLOCK_MEMO_20260728.md,
# lever #1). The desktop default is 2,000,000 nodes; the budget has no wall-clock
# component and PythonBridge.reset() queues BEHIND a running ai_move, so on a phone a
# runaway solve is an uncancellable hang with a progress-less spinner.
#
# Largest solve observed to date: 2,214 nodes across the memo's 9 endgames, and 7,067
# nodes in a 3-position Tier-1-prefix probe run while wiring this up — so the observed
# tail is WIDER than the memo's sample suggested, and 100,000 is ~14x the largest solve
# seen anywhere (not the ~45x the memo estimated off 2,214). Still a bound that should
# never fire (0 budget hits in 400 screen games), but the margin is thinner than it
# looks and is worth re-checking if more endgames are ever sampled. If it DOES fire,
# that ONE decision falls back to fair PIMC (stamped on agent.manifest).
ANDROID_EXACT_BUDGET: int = 100_000

# --------------------------------------------------------------------------- #
# 1b. THE MOBILE BUDGET PROFILE. ⚠️ UNPINNED 2026-08-01 — the phone now plays   #
#     the CHAMPION OF RECORD (k8x1376 = 11008). The carve-out is CLOSED.        #
#                                                                              #
# HISTORY IN TWO LINES. On 2026-07-29 the desktop budget was promoted k4x688    #
# (2752) -> k8x1376 (11008) — +49.85 elo (CL-060, paired z 3.48) — and the      #
# phone was CARVED OUT at 2752, because that budget was only clock-legal via 8  #
# spawn processes and Chaquopy has no `multiprocessing`.                        #
#                                                                              #
# WHAT CHANGED: not the parallelism story, the ENGINE. rustport P7/G7 put a     #
# native `carc_rs` core on the device that folds the k worlds across 4 OS       #
# threads INSIDE one GIL-released call — no processes needed. Measured on the   #
# Pixel 9 Pro: 11008 sims at 1.551 s/move median, thermal 1.007x. That is the   #
# mobile profile's own written UNPIN CONDITION, met literally, so the profile   #
# was unpinned to the champion of record.                                       #
#                                                                              #
# ⚠️ THE BUDGET IS CONDITIONAL ON THE BACKEND — the one invariant to hold in     #
# head here. 11008 sims on the PYTHON path is still ~25 s/move on this device.  #
# So `_build_opponent` resolves backend and budget TOGETHER, and a session that #
# cannot get `carc_rs` degrades BOTH: Python engine AND the k4x688 floor below. #
# Never honour this profile's k_dets/sims_per_det without its `backend`.        #
#                                                                              #
# DESIGN CONTRACT 3 ("the YAML is the champion, no strength knob is hardcoded   #
# here") is preserved: every number still comes from the YAML. The constant     #
# below is a FAIL-CLOSED floor for the two cases the contract cannot cover — a  #
# bundled YAML with no `mobile` profile, and a device with no Rust wheel — both #
# of which would otherwise ship a 25 s/move hang.                               #
#                                                                              #
# E4: because the running budget now EQUALS the champion of record,             #
# `champion_factory` stamps NO `runtime_budget_override`, and the ABSENCE of    #
# that key is the signal that a game was played at full champion strength.      #
# Games archived before this build carry the override naming k4x688 and are     #
# still graded against k4x688.                                                  #
# --------------------------------------------------------------------------- #
ANDROID_DEPLOY_PROFILE: str = "mobile"
ANDROID_FALLBACK_BUDGET: dict[str, int] = {"k_dets": 4, "sims_per_det": 688}
# Threads used when the YAML profile names no `rust_threads`. 4 is the G7-measured
# setting on the Pixel; the YAML is authoritative when it says otherwise.
ANDROID_FALLBACK_RUST_THREADS: int = 4

# --------------------------------------------------------------------------- #
# 1b-2. THE MOBILE TIE-ARBITER. ⭐ ADDED 2026-08-24 — owner ruling, verbatim:    #
#     "so let's default to b32 on phone. but. give me a settings screen where  #
#     I can choose lower options. and there should be a progress indicator     #
#     during the longer thinking turns."                                       #
#                                                                              #
# Same mechanism as the desktop's `fair_deploy.tiearb` (RUST-ONLY post-search  #
# root tie-break: B CRN playout worlds per tied arm, J caps the arm set,       #
# argmax the mean). Desktop runs a FIXED B=64/threads=8; mobile makes B a      #
# SETTINGS-SCREEN CHOICE (B_options below) with a smaller default, because a   #
# B=32 fire measures ~20.8-28.9s at tiearb_threads=2 on the reference device — #
# too long to hardcode without a way to back off. J/mode/salt/eps/threads are  #
# NOT user-selectable: only B moves, exactly like the desktop shape says.      #
#                                                                              #
# FAIL-CLOSED, same discipline as the budget above: `mobile_tiearb()` never    #
# raises and never guesses a B a caller did not ask for. See its docstring.    #
# --------------------------------------------------------------------------- #
TIEARB_LEVEL_OFF = "off"
TIEARB_LEVEL_B8 = "b8"
TIEARB_LEVEL_B16 = "b16"
TIEARB_LEVEL_B32 = "b32"
TIEARB_LEVEL_B64 = "b64"
# Strongest-first, matching B_options. ⚠️ THIS IS THE RESOLVER'S VOCABULARY, NOT THE
# SETTINGS MENU. The menu is Kotlin's `TieArbLevel`, and since 2026-08-29 it offers
# OFF/B8/B16/B64 — b32 is RETIRED FROM THE MENU but stays resolvable here, because a
# save or archive written by the B32 epoch carries `tiearb_level: "b32"` and must
# still restore at B=32 rather than silently degrading to an unarmed game.
TIEARB_LEVELS: tuple[str, ...] = (
    TIEARB_LEVEL_B64, TIEARB_LEVEL_B32, TIEARB_LEVEL_B16, TIEARB_LEVEL_B8,
    TIEARB_LEVEL_OFF)
TIEARB_LEVEL_DEFAULT = TIEARB_LEVEL_B64          # ⭐ RAISED b32 -> b64 2026-08-29 (owner:
# "set phone APK to b64"), licensed by the tier1 flat-score swap making a B=64 fire
# CHEAPER than the B=32 fire it replaces. Kotlin always sends `tiearb_level`
# explicitly, so this default only governs a caller that omits the key.
# A save/archive written before this feature shipped has no `tiearb_level` key at
# all; absent means "played without the arbiter", never a guessed B — the same
# absent-is-legacy contract as start_rule/grid_rule/draw_rule/cloister_rule/farm_rule.
TIEARB_LEVEL_LEGACY = TIEARB_LEVEL_OFF
TIEARB_LEVEL_TO_B: dict[str, int] = {
    TIEARB_LEVEL_B8: 8, TIEARB_LEVEL_B16: 16, TIEARB_LEVEL_B32: 32,
    TIEARB_LEVEL_B64: 64}

# Desktop convenience: when the repo tree is visible above this file and the package is
# not installed, make src/ importable. On device this resolves to a path that does not
# exist and is skipped. (android/app/src/main/python/android_bridge.py -> parents[4] is
# `android`, parents[5] is the repo root.)
_HERE = Path(__file__).resolve()
_MAYBE_REPO = _HERE.parents[5] if len(_HERE.parents) > 5 else None
if _MAYBE_REPO is not None and (_MAYBE_REPO / "src" / "carcassonne_ai").is_dir():
    _src = str(_MAYBE_REPO / "src")
    if _src not in sys.path:
        sys.path.append(_src)   # append, never prepend: an installed copy still wins

# --------------------------------------------------------------------------- #
# 1c. Cython fast paths — republish carc_cy.* under their carcassonne_ai names. #
#                                                                              #
# The compiled extensions ship in a standalone `carc_cy` wheel (see            #
# android/native/carc-cy). They CANNOT ship inside `carcassonne_ai` itself: on  #
# device that package arrives via Chaquopy's *source* asset while pip           #
# requirements arrive via a *separate* asset, and Python binds a package's      #
# __path__ to the first sys.path entry that provides it — so a package split    #
# across the two finders would make `carcassonne_ai.flat_leaf_cy` unimportable. #
#                                                                              #
# Aliasing into sys.modules is what the LAZY `from . import flat_leaf_cy` in    #
# flat_leaf.py (and `from .flat_repr_cy import ...` in board_repr.py) then      #
# resolves against. Must run BEFORE the first leaf evaluation, because both     #
# sites cache a False sentinel on ImportError and never retry.                  #
# No wheel (desktop, or an NDK-less build) -> stays pure Python, which is       #
# correct, just slower.                                                        #
# --------------------------------------------------------------------------- #
CY_MODULES: tuple[str, ...] = ("flat_leaf_cy", "flat_repr_cy")


def _install_cy_aliases() -> dict[str, bool]:
    """Map ``carc_cy.<m>`` onto ``carcassonne_ai.<m>``. Returns which ones loaded."""
    import importlib

    loaded: dict[str, bool] = {}
    for name in CY_MODULES:
        target = f"carcassonne_ai.{name}"
        if target in sys.modules:            # already importable the ordinary way
            loaded[name] = True
            continue
        try:
            mod = importlib.import_module(f"carc_cy.{name}")
        except ImportError:
            loaded[name] = False
            continue
        sys.modules[target] = mod
        loaded[name] = True
    if any(loaded.values()):
        # Also bind on the parent package, so plain attribute access agrees with
        # sys.modules (CPython's IMPORT_FROM falls back to sys.modules, but only
        # after an AttributeError — this keeps the two views consistent).
        try:
            import carcassonne_ai as _ca
            for name, got in loaded.items():
                if got:
                    setattr(_ca, name, sys.modules[f"carcassonne_ai.{name}"])
        except ImportError:
            pass
    return loaded


CY_LOADED: dict[str, bool] = _install_cy_aliases()

import numpy as np  # noqa: E402

from carcassonne_ai import champion_factory  # noqa: E402
from carcassonne_ai.action_space import (  # noqa: E402
    decode,
    meeple_pass_index,
    tile_action_count,
    tile_pass_index,
)
from carcassonne_ai.game_wrapper import (  # noqa: E402
    RETAIL_START_TILE,
    SCORE_NORM_SCALE,
    Board,
    Game,
)
# The intra-tile meeple grouping of record. It USED to be defined in this file; it moved
# into the package (2026-07-27) when the search grew a MEEPLE-DEDUP mode that needs the
# same definition, and a second copy would drift. Re-exported here so `feature_groups`
# stays part of this module's API for existing importers (the census, tests/android).
from carcassonne_ai.meeple_equiv import feature_groups  # noqa: E402,F401
# The F9 profile registry — the ONE vocabulary for a named rules bundle. Imported
# for `rules_profile_name()` below, which LABELS a session's five levers; the
# levers themselves are still resolved here, per-field, so the app never depends on
# a profile being applicable (R9 is not, see block 1a).
from carcassonne_ai import rules_profile as _rules_profile  # noqa: E402
from wingedsheep.carcassonne.tile_sets import base_deck as _base_deck  # noqa: E402
from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction  # noqa: E402
from wingedsheep.carcassonne.objects.actions.tile_action import TileAction  # noqa: E402
from wingedsheep.carcassonne.objects.coordinate import Coordinate  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402

SAVE_SCHEMA = "carcassonne-android-save/v1"
STATE_SCHEMA = "carcassonne-android-state/v1"
# A finished game's permanent record. A SUPERSET of a save: the same restorable
# (deck_seed, actions) core plus the read-only result summary, so `filesDir/games/`
# is both a scoreboard and a replay archive. See `archive_record`.
ARCHIVE_SCHEMA = "carcassonne-android-archive/v1"

# Start-tile convention (2026-07-30, Joshua-approved for the APP ONLY).
#   "engine" — the vendored engine's native rule: the first player draws a RANDOM
#              tile which is auto-placed at starting_position, costing them a turn
#              and giving them a free meeple on it. Every training run, eval and
#              solver measurement to date used this; it stays the library default.
#   "retail" — retail/tournament: a fixed "D" tile (city + straight road) is
#              pre-placed before anyone draws. Nobody spends a turn on it, no
#              meeple goes on it, and the deck is the remaining 71.
# The app plays "retail". This travels in the SAVE PAYLOAD, so a game archived
# under "engine" replays under "engine" forever — the (deck_seed, actions) core is
# only lossless with respect to the rules it was played under.
START_RULE_ENGINE = "engine"
START_RULE_RETAIL = "retail"
START_RULE = START_RULE_RETAIL          # what a NEW app game uses
START_RULE_LEGACY = START_RULE_ENGINE   # what a save with no `start_rule` means

# --------------------------------------------------------------------------- #
# Start-tile GRID position (2026-08-02, Joshua-approved for the APP ONLY).      #
#                                                                              #
# THE BUG. The engine starts the board at row 6 of a 35-row grid — 6 rows of    #
# headroom above, 28 below — and `StateUpdater.play_tile` bounds-checks         #
# `open_positions`, so a rule-legal cell above row 0 is never offered, with no  #
# error and no visual cue. Joshua hit it playing on the Pixel: "an invisible    #
# border to the game". Measured over 400 games: 67.8% of games lose at least    #
# one rule-legal placement, 2.6% of all placements, 100% of them above row 0.   #
# (tests/test_start_tile_grid_bound.py is the executable evidence.)             #
#                                                                              #
#   "engine6"    — the walled engine grid, start (6, 15). What every training   #
#                  run, eval, solver measurement and pre-2026-08-02 app game    #
#                  was played under. Still the LIBRARY default.                 #
#   "centered18" — start (18, 15): 18 rows above / 16 below. What a NEW app     #
#                  game plays.                                                  #
#                                                                              #
# ⚠️ THE SHIFT IS EVEN ON PURPOSE (12 rows, column unmoved). `board_repr`       #
# centres the window with banker's-rounded `round(sum/count)`, which is         #
# equivariant under EVEN translations only — so an even shift is bit-identical  #
# for the trained representation and an odd one silently slips the window by a  #
# cell. `game_wrapper.check_start_position` refuses odd shifts, and so does the #
# Rust `GameConfig::resolve`; row 18 satisfies both.                            #
#                                                                              #
# LIKE `start_rule`, THIS TRAVELS IN THE SAVE PAYLOAD. (deck_seed, actions) is  #
# only lossless with respect to the grid it was played on — the legal-move set  #
# differs, so the same action index decodes a different cell. A save or archive #
# with no `grid_rule` was written before this shipped and means "engine6"       #
# forever; an unrecognised value is refused rather than guessed.                #
# --------------------------------------------------------------------------- #
GRID_RULE_ENGINE6 = "engine6"
GRID_RULE_CENTERED18 = "centered18"
GRID_RULE = GRID_RULE_CENTERED18         # what a NEW app game uses
GRID_RULE_LEGACY = GRID_RULE_ENGINE6     # what a save with no `grid_rule` means
# The one place a grid rule becomes a row. Column is unmoved in both.
GRID_RULE_START: dict[str, tuple[int, int]] = {
    GRID_RULE_ENGINE6: (6, 15),
    GRID_RULE_CENTERED18: (18, 15),
}

# --------------------------------------------------------------------------- #
# The UNPLACEABLE-TILE draw rule (F9/A3). ⚠️ ADOPTED BY THE APP 2026-08-03.     #
#                                                                              #
#   "engine" — the vendored engine's native rule: a TILES-phase PassAction      #
#              discards the unplaceable tile, draws the next AND passes the     #
#              turn, so the drawer forfeits a placement.                        #
#   "redraw" — the retail rule and what a NEW app game plays: set the tile      #
#              GAME), draw again, SAME player continues, repeat while           #
#              unplaceable.                                                     #
#                                                                              #
# LIKE `start_rule` AND `grid_rule`, THIS TRAVELS IN THE SAVE PAYLOAD, and for  #
# the same reason: the same (deck_seed, actions) decodes a DIFFERENT game under #
# the two rules — the rule changes TURN PARITY (who owes the next decision      #
# after a discard) and WHICH TILES EVER ENTER PLAY (a set-aside tile is gone,   #
# so every later draw shifts). A save or archive with no `draw_rule` was        #
# written before this shipped and means "engine" forever; an unrecognised value #
# is refused rather than guessed.                                               #
# --------------------------------------------------------------------------- #
DRAW_RULE_ENGINE = "engine"
DRAW_RULE_REDRAW = "redraw"
DRAW_RULE = DRAW_RULE_REDRAW            # what a NEW app game uses
DRAW_RULE_LEGACY = DRAW_RULE_ENGINE     # what a save with no `draw_rule` means

# --------------------------------------------------------------------------- #
# The CLOISTER SCAN rule (F9/A2). ⚠️ ADOPTED BY THE APP 2026-08-03.             #
#                                                                              #
#   "drifting" — the vendored engine's behaviour: the 3x3 completion scan is    #
#                re-anchored on the tile just played, so the neighbourhood a    #
#                cloister is judged against drifts off the cloister itself.     #
#   "fixed"    — `Game(cloister_scan_fix=True)`: the scan stays anchored on the #
#                CLOISTER'S OWN coordinate. The retail reading, and what a NEW  #
#                app game plays.                                                #
#                                                                              #
# SAME SAVE-PAYLOAD CONTRACT as the three rules above: the fix changes WHEN a   #
# cloister completes, which moves scores and — through the meeple a completion  #
# returns to its owner — which meeple actions are legal later, so the same      #
# (deck_seed, actions) decodes a different game. Absent field == "drifting".    #
# --------------------------------------------------------------------------- #
CLOISTER_RULE_DRIFTING = "drifting"
CLOISTER_RULE_FIXED = "fixed"
CLOISTER_RULE = CLOISTER_RULE_FIXED             # what a NEW app game uses
CLOISTER_RULE_LEGACY = CLOISTER_RULE_DRIFTING   # absent `cloister_rule` means this

# What block 1a's env write ACTUALLY latched, read off the engine rather than off
# our own request — `base_deck` resolved it at ITS import, and an environment that
# already carried `CARCASSONNE_FIX_R9` beat our `setdefault`. THIS, not
# FARM_RULE_REQUESTED, is what a session validates against and what a save stamps.
FARM_RULE_LATCHED: str = (FARM_RULE_R9 if _base_deck.R9_FIELD_ON_CITY_EDGE_FIX
                          else FARM_RULE_ENGINE)

# --------------------------------------------------------------------------- #
# THE PROFILE LABEL. The five rule fields above are the AUTHORITY in a save;    #
# this is the one-word name for the combination, DERIVED from them and stamped  #
# beside them so an archive says what it is without a reader re-deriving it.    #
#                                                                              #
# DERIVED, NEVER TRUSTED. `restore_game` rebuilds the session from the five     #
# fields and then re-derives this name; a blob whose stored label disagrees is  #
# REFUSED, because exactly one of the two is wrong and picking one would be the #
# silent-divergence class F9 exists to kill. A combination `rules_profile` does #
# not name labels as "custom" — legal, just unnamed. Vocabulary comes from      #
# `rules_profile.PROFILES` so the app and the harnesses cannot drift apart.     #
# --------------------------------------------------------------------------- #
PROFILE_CUSTOM = "custom"

# app vocabulary -> rules_profile vocabulary, on the one axis where they differ.
_PROFILE_DRAW = {DRAW_RULE_ENGINE: "next_player", DRAW_RULE_REDRAW: "redraw"}


def _profile_key(prof) -> tuple:
    return (prof.grid_rule, prof.start_rule, prof.cloister_scan,
            prof.unplaceable_tile, bool(prof.r9_env_expected))


_PROFILE_BY_KEY: dict[tuple, str] = {
    _profile_key(p): name for name, p in _rules_profile.PROFILES.items()
}


def rules_profile_name(*, start_rule: str, grid_rule: str, draw_rule: str,
                       cloister_rule: str, farm_rule: str) -> str:
    """The `rules_profile` name for these five levers, or ``"custom"``.

    Pure and total over the validated vocabularies — every caller has already
    refused an unknown value on each axis, so this never has to guess."""
    key = (grid_rule, start_rule, cloister_rule,
           _PROFILE_DRAW[draw_rule], farm_rule == FARM_RULE_R9)
    return _PROFILE_BY_KEY.get(key, PROFILE_CUSTOM)


# The five rule fields as a save blob spells them, with the LEGACY meaning of an
# absent one. One table, so `restore_game` and any reader agree on what "written
# before this field existed" means for each axis.
BLOB_RULE_DEFAULTS: dict[str, str] = {
    "start_rule": START_RULE_LEGACY,
    "grid_rule": GRID_RULE_LEGACY,
    "draw_rule": DRAW_RULE_LEGACY,
    "cloister_rule": CLOISTER_RULE_LEGACY,
    "farm_rule": FARM_RULE_LEGACY,
}

# The accepted value of each. `_Session` re-checks these and owns the error
# messages; this copy exists so a LABEL can be derived without raising.
RULE_VOCABULARY: dict[str, tuple[str, ...]] = {
    "start_rule": (START_RULE_ENGINE, START_RULE_RETAIL),
    "grid_rule": tuple(GRID_RULE_START),
    "draw_rule": (DRAW_RULE_ENGINE, DRAW_RULE_REDRAW),
    "cloister_rule": (CLOISTER_RULE_DRIFTING, CLOISTER_RULE_FIXED),
    "farm_rule": (FARM_RULE_ENGINE, FARM_RULE_R9),
}


def blob_rules(blob: dict) -> dict[str, str]:
    """The five rule levers a save/archive blob was played under."""
    return {k: str(blob.get(k, default))
            for k, default in BLOB_RULE_DEFAULTS.items()}


def _blob_profile_name(blob: dict) -> str | None:
    """`rules_profile_name` for a blob, or ``None`` if a field is out of vocabulary.

    ``None`` is not an error signal to act on — it means "``_Session`` is about to
    raise a field-specific message", which is a better one than anything derivable
    here."""
    rules = blob_rules(blob)
    if any(v not in RULE_VOCABULARY[k] for k, v in rules.items()):
        return None
    return rules_profile_name(**rules)

# --------------------------------------------------------------------------- #
# Agent backend. ⚠️ FLIPPED 2026-08-01 (Joshua: "2 yes"): the DEFAULT IS RUST.  #
#                                                                              #
# "rust" swaps ONLY the opponent's move choice for `carc_rs.FairAgentRs`, the   #
# bit-exact port gated at G1-G7. The Python engine stays authoritative for      #
# everything else — legality, UI, scoring, the save/archive record — so the     #
# switch cannot change what a game IS, only who picks the champion's move.      #
# Behaviour identity, not assertion: G6 = 14,384/14,384 identical actions over  #
# 100 full games; G7 leg 2 = 0/3,165 plies of replay divergence ON THIS DEVICE. #
#                                                                              #
# WHY THE DEFAULT MOVED. The flip is what pays for the mobile UNPIN: the full   #
# champion budget (k8x1376 = 11008) costs 1.551 s/move on the Rust core with 4  #
# threads (G7 leg 3) and ~25 s/move on the Python one. So backend and budget    #
# are COUPLED — `_build_opponent` resolves them together and degrades BOTH if   #
# `carc_rs` is missing. See `mobile_budget()` and PRODUCTION.yaml's mobile note.#
#                                                                              #
# Still selectable per game via new_game's `backend` key, and process-wide via  #
# CARC_ANDROID_BACKEND (a test harness pins "python" that way).                 #
# --------------------------------------------------------------------------- #
BACKEND_PYTHON = "python"
BACKEND_RUST = "rust"
BACKEND_DEFAULT = os.environ.get("CARC_ANDROID_BACKEND", BACKEND_RUST)

# --------------------------------------------------------------------------- #
# REMOTE OPPONENT (2026-08-30) — the owner plays Carcasum from this app          #
#                                                                               #
# `measurement/carcasum_owner_session_prep/` needs the owner to face the         #
# CALIBRATED Carcasum (MCTS/Portion/Random/5000ms/Cp0.5, the PATCHED binary)     #
# under his NORMAL PHONE CONDITIONS. Nothing is ported to Android: the phone     #
# forwards each opponent move over the tailnet to                               #
# `scripts/carcasum_remote/server.py` on the laptop, which wraps the existing    #
# engine-vs-engine Carcasum bridge. This side is a ~60-line HTTP client and one  #
# extra `opponent` kind; the champion path is untouched.                         #
#                                                                               #
# ⛔ THE LABEL IS LOAD-BEARING. A remote game is archived with                   #
# `opponent: "carcasum_remote_5000ms"`, never "champion", so it can never pool   #
# into the owner-vs-CHAMPION E4 anchor — which is the single number the whole    #
# adaptation-share discriminator is chained through. `scripts/e4_archives.py` is #
# the reader-side half of that (absent stamp EXCLUDES, loudly).                  #
# --------------------------------------------------------------------------- #
OPPONENT_CHAMPION = "champion"
OPPONENT_TIER1 = "tier1"
#: Canonical archive label prefix. `opponent_kind` for a remote game is the FULL
#: label including the budget (`carcasum_remote_5000ms`), so the archive says
#: which opponent config was played without a second field to forget.
REMOTE_OPPONENT_PREFIX = "carcasum_remote"
REMOTE_DEFAULT_BUDGET_MS = 5000
#: Generous by design: Carcasum thinks 5 CPU-seconds and the phone may be on a
#: sleepy radio. A timeout is never fatal (the protocol is idempotent), it just
#: costs a retry — so the cost of setting this too LOW (a spurious retry storm)
#: is higher than setting it too high (one slow move).
REMOTE_DEFAULT_TIMEOUT_S = 180.0
#: How many times one move request is retried before the UI is told. Each retry
#: re-sends the IDENTICAL (deck_seed, actions) body, which the server answers
#: from its committed log — so a retry can never produce a second search or a
#: second move (see `scripts/carcasum_remote/server.py::_Session.next_action`).
REMOTE_DEFAULT_RETRIES = 4


def remote_opponent_label(budget_ms: int) -> str:
    """The archive's `opponent` value for a remote game at this budget."""
    return f"{REMOTE_OPPONENT_PREFIX}_{int(budget_ms)}ms"


def humanise_playouts(n: int) -> str:
    """`103500` -> `"103.5k"`, `2000` -> `"2k"`, `900` -> `"900"`."""
    n = int(n)
    if n < 1000:
        return str(n)
    k = n / 1000.0
    return (f"{k:.1f}".rstrip("0").rstrip(".") if n % 1000 else f"{n // 1000}") + "k"


def remote_display_name(health: dict | None, budget_ms: int | None) -> str:
    """The SHORT, player-facing name of the remote opponent — from the SERVER.

    ⚠️ Why this is not `f"Carcasum {budget_ms // 1000}s"` any more (2026-09-02
    text audit): the server grew a fixed-PLAYOUT mode (`server.py --playouts`),
    and in that mode `budget_ms` is *None* on its side while the phone still
    carries the 5000 ms default it was configured with. The old string therefore
    printed "Carcasum 5s" over an opponent that was not running on a time budget
    at all. The server already self-describes — `/health` returns
    `opponent_label` (e.g. ``carcasum_remote_p103500``) and an `opponent` dict —
    so the display name is DERIVED from what it says, and only falls back to the
    locally-configured budget when the health ping told us nothing.

    Shape is `Name(detail)` on purpose: `MoveText.shortOpponent` cuts at the
    parenthesis, so the HUD chip reads "Carcasum" while the status bar and the
    end-of-game dialog keep the detail.
    """
    opp = (health or {}).get("opponent") or {}
    playouts = opp.get("playouts")
    ms = opp.get("budget_ms", budget_ms)
    if playouts:
        return f"Carcasum({humanise_playouts(playouts)} playouts)"
    if ms:
        ms = int(ms)
        secs = f"{ms / 1000:g}"
        return f"Carcasum({secs}s/turn)"
    label = str((health or {}).get("opponent_label") or "").strip()
    return f"Carcasum({label})" if label else "Carcasum"


def is_remote_opponent(kind: str) -> bool:
    """True for every remote-opponent spelling, labelled or bare.

    Accepts the bare `"carcasum_remote"` (what the app's settings send) AND the
    labelled `"carcasum_remote_5000ms"` (what the archive/save records), because
    `restore_game` feeds the RECORDED value straight back in as the kind.
    """
    return str(kind).startswith(REMOTE_OPPONENT_PREFIX)


class RemoteOpponent:
    """Carcasum over the tailnet: one HTTP round-trip per opponent action.

    Stateless per move by construction — every request carries the FULL
    `(deck_seed, action_log)` root-replay pair, the same lossless representation
    this app already archives. The server holds the live Carcasum process and
    answers from its own committed log, so **a retry is idempotent**: a dropped
    response costs one re-request and cannot produce a second search, a second
    move, or a divergent board.

    Shaped like every other agent here (`choose_action(board) -> int`), with no
    `start_game`/`advance`, so the mirror protocol correctly ignores it.
    """

    def __init__(self, *, url: str, session, budget_ms: int = REMOTE_DEFAULT_BUDGET_MS,
                 timeout_s: float = REMOTE_DEFAULT_TIMEOUT_S,
                 retries: int = REMOTE_DEFAULT_RETRIES):
        self.url = str(url).rstrip("/")
        self.budget_ms = int(budget_ms)
        self.timeout_s = float(timeout_s)
        self.retries = int(retries)
        self._session = session
        self.last_response: dict | None = None
        self.finish_response: dict | None = None
        self.health: dict | None = None
        self.n_calls = 0
        self.n_retries = 0

    # -- transport ---------------------------------------------------------- #
    def _post(self, path: str, body: dict) -> tuple[int, dict]:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            self.url + path, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as fh:
                return int(fh.status), json.loads(fh.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return int(e.code), json.loads(e.read().decode() or "{}")
            except Exception:                             # noqa: BLE001
                return int(e.code), {}

    def check_health(self) -> dict:
        """Ping `/health` once at game start so a mistyped address or a dead
        daemon fails BEFORE the first move rather than three plies in."""
        import urllib.request

        with urllib.request.urlopen(self.url + "/health", timeout=20) as fh:
            self.health = json.loads(fh.read().decode())
        gate = (self.health or {}).get("gate") or {}
        if gate.get("state") not in ("ANCHOR", "OVERRIDDEN", "UNCHECKED"):
            raise RuntimeError(f"remote opponent reports no binary gate: {gate!r}")
        return self.health

    # -- the agent face ----------------------------------------------------- #
    def choose_action(self, board) -> int:                        # noqa: ARG002
        s = self._session
        body = {"game_id": self.game_id, "deck_seed": int(s.seed),
                "human_seat": int(s.human_player),
                "actions": [int(a) for a in s.action_log],
                "opponent": {"budget_ms": self.budget_ms}}
        last: dict = {}
        for attempt in range(max(1, self.retries)):
            if attempt:
                self.n_retries += 1
                time.sleep(min(2.0 * attempt, 8.0))
            try:
                code, resp = self._post("/move", body)
            except Exception as exc:                      # noqa: BLE001 — retry
                last = {"error": "transport", "message": f"{type(exc).__name__}: {exc}"}
                continue
            if code == 200:
                self.last_response = resp
                self.n_calls += 1
                if resp.get("action") is None:
                    raise RuntimeError(
                        "the remote opponent says the game is over but our board "
                        f"is not: {json.dumps(resp)[:400]}")
                return int(resp["action"])
            last = dict(resp, http_status=code)
            if code == 409:
                # A real disagreement about the game (divergence / lost session).
                # Retrying cannot help and would only paper over it.
                break
        raise RuntimeError(
            "the remote Carcasum opponent could not be reached or refused the "
            f"position after {max(1, self.retries)} attempts: {json.dumps(last)[:600]}")

    def finish(self) -> dict | None:
        """Tell the server the game is over, and hand it the final log.

        ⚠️ Not optional, and not merely tidy. When the HUMAN plays the
        terminating ply there is no further move request, so without this the
        server has never been told about that last action: its Carcasum session
        sits in the loop waiting for it, the endgame farm/terrain audit never
        runs, and a full core leaks for the session TTL. Best-effort — a failure
        here must never stop the phone from writing ITS archive, which is the
        record that actually matters.
        """
        try:
            code, resp = self._post("/end", {
                "game_id": self.game_id,
                "actions": [int(a) for a in self._session.action_log]})
            self.finish_response = resp if code == 200 else {"http_status": code, **resp}
        except Exception as exc:                          # noqa: BLE001
            self.finish_response = {"error": f"{type(exc).__name__}: {exc}"}
        return self.finish_response

    @property
    def game_id(self) -> str:
        """One id per (deck_seed, seat) game — stable across retries and across
        an app restart, so a resumed request finds the same live session."""
        return f"phone-{int(self._session.seed)}-{int(self._session.human_player)}"

    def manifest_block(self) -> dict:
        """What the archive records about WHICH opponent actually played."""
        gate = (self.health or {}).get("gate") or {}
        return {
            "url": self.url,
            "budget_ms": self.budget_ms,
            # THE SERVER'S OWN LABEL (added 2026-09-02). `budget_ms` above and the
            # session's `opponent_kind` are both derived from OUR config, which is
            # stale the moment the daemon is launched in fixed-playout mode
            # (`server.py --playouts` sets `OPPONENT_LABEL` to
            # `carcasum_remote_p<N>` and nulls `budget_ms` on its side). This is
            # what the server says it is, so an archive is auditable without
            # trusting the phone's copy of the launch flags.
            "opponent_label": (self.health or {}).get("opponent_label"),
            "opponent": (self.health or {}).get("opponent"),
            "binary_sha256": gate.get("sha256"),
            "binary_gate": gate.get("state"),
            "tiny_city_probe": (gate.get("probe") or {}).get("tiny_city_score"),
            "server_profile": (self.health or {}).get("profile"),
            "calls": self.n_calls, "retries": self.n_retries,
            # What the server said when the game ended: its own final scores and
            # its divergence audit. A DISAGREEMENT here is the loudest signal we
            # have that a remote game is not what it looks like, so it is stamped
            # rather than logged.
            "server_final": {
                k: (self.finish_response or {}).get("record", {}).get(k)
                for k in ("scores", "carcasum_reported_scores", "final_agree",
                          "void", "real", "replay_ok",
                          "opp_driver_playouts_per_turn", "opp_driver_ms_per_turn")
            } if (self.finish_response or {}).get("record") else self.finish_response,
        }

# The reason the last `rust_available()` said no — folded into the session's
# `backend_note` so a degraded game can say WHY on screen, not just that it did.
_RUST_IMPORT_ERROR: str | None = None


def rust_available() -> bool:
    """Is the `carc_rs` wheel importable in THIS process?

    Deliberately NOT cached: `tests/android/test_bridge_backend.py` proves the
    degrade path by monkeypatching `__import__`, and a cached answer would make
    that test assert against a stale probe. The import itself is a `sys.modules`
    hit after the first call, so re-asking is free.

    Answered BEFORE the champion is built, because since the 2026-08-01 unpin the
    on-device BUDGET is conditional on this being true (11008 sims is 1.551 s/move
    on the Rust core and ~25 s/move on the Python one)."""
    global _RUST_IMPORT_ERROR
    try:
        import carc_rs  # noqa: F401
    except ImportError as exc:
        _RUST_IMPORT_ERROR = str(exc)
        return False
    _RUST_IMPORT_ERROR = None
    return True


def rust_build_provenance() -> dict:
    """WHICH carc_rs is running — compiler, target triple, profile, real version.

    ⚠️ ``carc_rs.__version__`` IS NOT AN ANSWER (REVIEW.md #9/#10). It is
    ``carc_core::VERSION`` = the workspace ``0.1.0`` that has never been bumped, so it
    distinguishes nothing — two builds from different rustc versions were identical in
    every record the repo wrote. ``android/tools/build_rust_wheels.py`` now ships a
    generated ``carc_rs_build`` sidecar alongside the extension carrying the real
    content-addressed wheel version and the toolchain that produced it; a desktop
    maturin wheel has no sidecar, so the installed distribution's metadata is the
    fallback and the frozen literal is the last resort (and is labelled as such).
    """
    out: dict = {}
    try:
        import carc_rs_build

        out.update(dict(getattr(carc_rs_build, "PROVENANCE", {}) or {}))
        out.setdefault("wheel_version", getattr(carc_rs_build, "__version__", None))
        out["source"] = "wheel_sidecar"
        return out
    except ImportError:
        pass
    try:
        import importlib.metadata as _md

        out["wheel_version"] = _md.version("carc-rs")
        out["source"] = "dist_metadata"
        return out
    except BaseException:                         # noqa: BLE001 — provenance only
        pass
    try:
        import carc_rs

        out["wheel_version"] = getattr(carc_rs, "__version__", None)
        out["source"] = "carc_rs.__version__ (frozen literal — see #9)"
    except BaseException:                         # noqa: BLE001
        pass
    return out


def _rust_wheel_version() -> str | None:
    return rust_build_provenance().get("wheel_version")

# The libm configuration Android actually needs, MEASURED at G7 leg 1
# (measurement/rustport_p7/G7_REPORT.md; raw in device/p7/libm_chaquopy.json).
#
# `tanh`/`expm1`: **msun** on every Android ABI measured — exact on the 214,333-arg
# production corpus AND on fuzz. It differs from the desktop (glibc_fma, G0 §2),
# which is exactly why the flavour is a config knob and not a compile-time
# constant. ⚠️ `glibc` is bit-exact on the whole tanh CORPUS and fails the fuzz,
# so never re-derive this flavour from a corpus-only run.
ANDROID_TANH_FLAVOR = "msun"

# ⚠️ `np.exp` (the softmax-prior site) is numpy's own SIMD kernel, not libm, and
# it is **ABI-DEPENDENT WITHIN ANDROID** — found by the x86_64 emulator leg,
# same numpy build (1.26.2) on both:
#     arm64-v8a  -> exp64_fma   (0/201,525 corpus, 0/2e6 fuzz; exp64 fails)
#     x86_64     -> exp64       (0/201,525 corpus, 0/2e6 fuzz; exp64_fma fails)
# So a single constant would be wrong on one of the two ABIs the APK ships.
# Consistent with G0 §3 ("np.exp float64 bits differ across ISA").
_EXP_FMA_BY_MACHINE = {"aarch64": True, "arm64": True, "x86_64": False}


def android_exp_fma() -> bool:
    """Whether `compat::exp64` needs FMA contraction on THIS device's ABI.

    Unknown machine -> True (the arm64 answer), because arm64 is what ships to
    phones; the emulator is the only x86_64 target and it is named here.
    """
    return _EXP_FMA_BY_MACHINE.get(platform.machine(), True)


ANDROID_EXP_FMA = android_exp_fma()

# Per-ply mirror assertion. Off by default (it renders the board twice per
# action); the game-start check runs unconditionally either way.
_RS_RECONCILE = os.environ.get("CARC_RS_RECONCILE", "") == "1"

# Meeple-dot placement, as RATIOS of the tile size, lifted from
# CarcassonneVisualiser.meeple_position_offsets (tile_size=60, meeple_size=~21). The
# visualiser itself is excluded from the bundle (tkinter/PIL), so the numbers travel
# here and the Compose canvas multiplies them by its own tile size.
MEEPLE_OFFSET_RATIO: dict[str, tuple[float, float]] = {
    "top": (0.5, 0.175),
    "right": (0.825, 0.5),
    "bottom": (0.5, 0.825),
    "left": (0.175, 0.5),
    "center": (0.5, 0.5),
    "top_left": (0.25, 0.175),
    "top_right": (0.75, 0.175),
    "bottom_left": (0.25, 0.825),
    "bottom_right": (0.75, 0.825),
}


# --------------------------------------------------------------------------- #
# 2. Bundled PRODUCTION.yaml                                                    #
# --------------------------------------------------------------------------- #
def _resolve_production_yaml() -> str:
    """Point ``champion_factory.PRODUCTION_YAML`` at the bundled YAML when present.

    On device the package lives at ``<bundle>/carcassonne_ai/`` and the factory's
    ``REPO = parents[2]`` guess is meaningless, so the bundled copy at
    ``carcassonne_ai/data/PRODUCTION.yaml`` is authoritative. On desktop that file does
    not exist and the factory's repo path is already correct."""
    import carcassonne_ai

    bundled = Path(carcassonne_ai.__file__).resolve().parent / "data" / "PRODUCTION.yaml"
    if bundled.is_file():
        champion_factory.PRODUCTION_YAML = bundled
        return str(bundled)
    return str(champion_factory.PRODUCTION_YAML)


PRODUCTION_YAML_PATH = _resolve_production_yaml()


def mobile_budget(spec=None) -> dict:
    """The per-move budget THIS PLATFORM runs — the YAML's ``mobile`` deploy profile.

    Returns ``{"k_dets", "sims_per_det", "total_sims", "backend", "rust_threads",
    "profile", "from_yaml"}``.

    FAIL-CLOSED, and that is the whole point of the function: if the bundled YAML has no
    ``mobile`` profile (an old bundle, a hand-edited file), we fall back to
    ``ANDROID_FALLBACK_BUDGET`` — **never** to ``spec.k_dets``/``spec.sims_per_det``.
    ``from_yaml=False`` in the response says the fallback fired.

    ⚠️ ``backend`` IS PART OF THE BUDGET, not decoration (2026-08-01 unpin). The profile
    now names the CHAMPION-OF-RECORD budget, which is 1.551 s/move on ``carc_rs`` and
    ~25 s/move on the Python engine. A caller that takes ``total_sims`` from here and
    ignores ``backend`` reintroduces exactly the hang the carve-out existed to prevent.
    ``budget_for_backend()`` is the one place that resolves the pair; prefer it."""
    spec = spec or champion_factory.load_production_spec()
    prof = champion_factory.deploy_profile(ANDROID_DEPLOY_PROFILE, spec)
    if prof["found"]:
        k, s = int(prof["k_dets"]), int(prof["sims_per_det"])
        backend = str(prof["backend"])
        threads = prof["rust_threads"]
    else:
        k = int(ANDROID_FALLBACK_BUDGET["k_dets"])
        s = int(ANDROID_FALLBACK_BUDGET["sims_per_det"])
        backend, threads = BACKEND_PYTHON, None
    if backend == BACKEND_RUST and threads in (None, ""):
        threads = ANDROID_FALLBACK_RUST_THREADS
    return {"k_dets": k, "sims_per_det": s, "total_sims": k * s,
            "backend": backend,
            "rust_threads": (None if threads in (None, "") else int(threads)),
            "profile": ANDROID_DEPLOY_PROFILE, "from_yaml": bool(prof["found"])}


def budget_for_backend(backend: str, spec=None) -> dict:
    """The budget actually payable on ``backend`` — ``mobile_budget()`` gated by it.

    The YAML profile's budget is the champion of record and is priced for the Rust
    core. If this session is running the Python engine — because the wheel is absent,
    the ABI is unknown, the mirror failed to start, or the caller simply asked for
    ``backend: "python"`` — that budget is ~25 s/move here, so the honest answer is the
    ``ANDROID_FALLBACK_BUDGET`` floor rather than the profile. This is the ONE function
    that couples the two, and it is why unpinning the profile could not be done by
    editing the YAML alone. Same shape as ``mobile_budget()`` plus ``floored``."""
    mob = mobile_budget(spec)
    if backend == BACKEND_RUST or mob["backend"] != BACKEND_RUST:
        return {**mob, "floored": False}
    k = int(ANDROID_FALLBACK_BUDGET["k_dets"])
    s = int(ANDROID_FALLBACK_BUDGET["sims_per_det"])
    return {**mob, "k_dets": k, "sims_per_det": s, "total_sims": k * s,
            "backend": BACKEND_PYTHON, "rust_threads": None, "floored": True}


def _tiearb_off(level: str, *, from_yaml: bool, reason: str | None) -> dict:
    return {"enabled": False, "B": 0, "J": 0, "mode": "", "salt": "", "eps": 0.0,
            "threads": 0, "level": str(level), "from_yaml": bool(from_yaml),
            "reason": reason}


def mobile_tiearb(level: str, spec=None) -> dict:
    """The tie-arbiter config THIS PLATFORM runs for a Settings-screen ``level``.

    ``level`` is one of ``TIEARB_LEVELS`` — what the Settings screen persists and
    ``new_game``'s ``tiearb_level`` key carries. Returns ``{"enabled", "B", "J",
    "mode", "salt", "eps", "threads", "level", "from_yaml", "reason"}``.

    FAIL-CLOSED on every axis, the same discipline as ``mobile_budget()``: an
    unknown level, a bundled YAML with no ``mobile.tiearb`` block, or a B this
    build's ``B_options`` does not list all resolve to ``enabled=False`` rather
    than raising or guessing a B nobody asked for. ``reason`` explains why
    whenever ``enabled`` is False for anything other than an explicit
    ``"off"`` request, so a degraded game can say why on screen.

    Reads ``spec.deploy_profiles`` directly rather than going through
    ``champion_factory.deploy_profile()`` — that function's return shape is a
    fixed set of budget/execution keys shared with every caller (desktop
    included) and does not carry a nested ``tiearb`` block; extending it would
    widen a shared contract for a mobile-only field. ``ProductionSpec.
    deploy_profiles`` already exposes the raw per-profile dict, which is all
    this needs.

    ⚠️ DOES NOT CHECK THE BACKEND. The tie arbiter is RUST-ONLY
    (``champion_factory.make_production_champion``: "tiearb is RUST-ONLY"); the
    backend gate belongs to the caller, which alone knows whether the Rust
    mirror actually started — ``_Session._build_opponent`` forces
    ``enabled=False`` here whenever its own resolved ``backend`` is not
    ``"rust"``, and ``_start_rust_mirror`` re-confirms the arbiter went live
    against ``FairAgentRs.stats()`` before trusting it for the manifest.
    """
    if level not in TIEARB_LEVELS:
        return _tiearb_off(
            level, from_yaml=False,
            reason=f"unknown tiearb level {level!r}; expected one of {TIEARB_LEVELS}")
    if level == TIEARB_LEVEL_OFF:
        return _tiearb_off(level, from_yaml=True, reason=None)
    spec = spec or champion_factory.load_production_spec()
    mobile_prof = dict((spec.deploy_profiles or {}).get(ANDROID_DEPLOY_PROFILE) or {})
    ta = mobile_prof.get("tiearb")
    if not isinstance(ta, dict) or not ta.get("enabled"):
        return _tiearb_off(
            level, from_yaml=False,
            reason="no mobile tiearb profile in the bundled PRODUCTION.yaml")
    b_options = [int(b) for b in (ta.get("B_options") or [])]
    b = TIEARB_LEVEL_TO_B.get(level)
    if b is None or b not in b_options:
        return _tiearb_off(
            level, from_yaml=True,
            reason=(f"level {level!r} (B={b}) is not in this build's "
                    f"B_options {b_options}"))
    return {"enabled": True, "B": int(b), "J": int(ta.get("J", 4)),
            "mode": str(ta.get("mode", "argmax")),
            "salt": str(ta.get("salt", "tiearb2-deploy-v1")),
            "eps": float(ta.get("eps", 0.0)), "threads": int(ta.get("threads", 2)),
            "level": level, "from_yaml": True, "reason": None}


def _shim_factory_repo() -> str | None:
    """Make ``champion_factory._hashers()``'s sys.path inserts harmless on device.

    The factory inserts ``REPO/scripts/classical_search`` and
    ``REPO/scripts/measurement_infra`` at ``sys.path[0]`` before importing the hash
    dialects. On device REPO resolves inside Chaquopy's AssetFinder tree where those
    dirs don't exist — and Chaquopy's path hook RAISES FileNotFoundError for a missing
    path entry (desktop CPython silently skips it), so the insert poisons the very next
    import and the champion can never construct. Worse, the entry stays in sys.path, so
    one failed construction poisons every import after it.

    Fix: when the real repo layout is absent, point REPO at a scratch dir that really
    contains those two (empty) subdirs. The inserted entries then exist and are
    harmlessly empty; the bundled top-level ``c5_leaf_override``/``snapshot`` modules
    satisfy the imports. Must run at import time, before the first construction.
    """
    if (champion_factory.REPO / "scripts" / "classical_search").is_dir():
        return None  # desktop checkout — leave it alone
    import tempfile

    shim = Path(tempfile.mkdtemp(prefix="carc_repo_shim_"))
    for rel in ("scripts/classical_search", "scripts/measurement_infra"):
        (shim / rel).mkdir(parents=True, exist_ok=True)
    champion_factory.REPO = shim
    return str(shim)


FACTORY_REPO_SHIM = _shim_factory_repo()


# --------------------------------------------------------------------------- #
# 3. Pure helpers (ported from scripts/play_vs_tier1_gui.py:118-188, no tkinter) #
# --------------------------------------------------------------------------- #
def legal_rotations_at_cell(game: Game, board: Board, row: int, col: int) -> list[int]:
    off = board.offset
    win = off.to_window(Coordinate(row=row, column=col))
    if win is None:
        return []
    wr, wc = win
    base = (wr * off.size + wc) * 4
    mask = game.get_valid_moves(board)
    return [r for r in range(4) if mask[base + r]]


def tile_action_index(off, row: int, col: int, rot: int) -> int:
    win = off.to_window(Coordinate(row=row, column=col))
    if win is None:
        raise ValueError(f"cell ({row},{col}) is outside the action window")
    wr, wc = win
    return (wr * off.size + wc) * 4 + rot


def all_legal_tile_cells(game: Game, board: Board) -> set[tuple[int, int]]:
    mask = game.get_valid_moves(board)
    off = board.offset
    n_tile = tile_action_count(off.size)
    cells: set[tuple[int, int]] = set()
    for idx in np.flatnonzero(mask[:n_tile]):
        cell, _rot = divmod(int(idx), 4)
        wr, wc = divmod(cell, off.size)
        coord = off.to_engine(wr, wc)
        cells.add((coord.row, coord.column))
    return cells


def legal_meeple_indices(game: Game, board: Board) -> list[int]:
    mask = game.get_valid_moves(board)
    off = board.offset
    n_tile = tile_action_count(off.size)
    pass_idx = meeple_pass_index(off.size)
    return [int(i) for i in np.flatnonzero(mask)
            if int(i) >= n_tile and int(i) != pass_idx]


def _terrain_name(tile, side: Side) -> str:
    t = tile.get_type(side)
    return t.name if t is not None else "GRASS"


def format_action(idx: int, board: Board) -> str:
    """Human-readable string for a flat action index in the board's current phase."""
    phase = board.state.phase.value
    if phase == "tiles":
        if idx == tile_pass_index(board.offset.size):
            return "pass (no legal placement)"
        action = decode(idx, off=board.offset, phase="tiles",
                        next_tile=board.state.next_tile)
        assert isinstance(action, TileAction)
        c = action.coordinate
        return f"tile @ ({c.row:+d}, {c.column:+d}) rot={action.tile_rotations}"
    if idx == meeple_pass_index(board.offset.size):
        return "skip meeple"
    last = board.state.last_tile_action
    last_coord = last.coordinate if last is not None else None
    action = decode(idx, off=board.offset, phase="meeples", last_tile_coord=last_coord)
    assert isinstance(action, MeepleAction)
    return f"{action.meeple_type.name} on {action.coordinate_with_side.side.name}"


def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand (the fair_agent.k_remaining band)."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


# --------------------------------------------------------------------------- #
# 3b. What just happened — the last-move event summary                          #
# --------------------------------------------------------------------------- #
def _meeple_key(player: int, mp) -> tuple:
    cws = mp.coordinate_with_side
    return (int(player), int(cws.coordinate.row), int(cws.coordinate.column),
            str(cws.side.value), str(mp.meeple_type.value))


def _meeple_index(state) -> dict:
    """``{key: (player, MeeplePosition)}`` for every meeple standing on the board."""
    out = {}
    for player, positions in enumerate(state.placed_meeples):
        for mp in positions:
            out[_meeple_key(player, mp)] = (int(player), mp)
    return out


def scoring_events(prev_state, new_state, human_player: int, opponent_name: str,
                   claims: list | None = None) -> list[dict]:
    """What the just-applied action(s) actually paid, itemised.

    The board only *tells* you a score changed; it does not say why, and Base+Farmers
    pays in lumps large enough that "11 -> 17" with no explanation is the single most
    confusing thing about watching the champion play. This is the explanation.

    METHOD — a meeple leaving the board is the signal. The engine returns a meeple to
    its owner's hand exactly when the feature it was standing on completes and scores
    (``PointsCollector.remove_meeples_and_collect_points``, run at the END of the
    meeple sub-phase), so the meeples in ``prev_state`` but not in ``new_state`` are
    precisely the features that just paid out. Each one is re-found in the NEW state —
    ``find_city``/``find_road`` take a ``CoordinateWithSide`` and do not need a meeple,
    and the feature is *complete* there, so ``count_*_points`` returns the finished
    rate rather than the reduced one the previous state would have given.

    ``claims`` closes the one hole in that diff. A player may claim a feature the tile
    they just laid ALREADY completed — the meeple is placed and collected inside the
    same ``get_next_state``, so it is in neither state and the plain diff reports a
    score out of nowhere. The caller therefore passes the ``(player, MeeplePosition)``
    this decision placed, and it is treated as having been on the board. (Only the
    primary action can claim: ``auto_pass_forced`` applies passes, which never place
    a meeple.)

    Farmers are deliberately not handled: farms score only in the final pass, which
    this function refuses outright (see below).

    THREE HONESTY RULES, in the spirit of ``_final_breakdown``:

    * **A terminated state yields nothing.** The engine's endgame pass consumes EVERY
      remaining meeple inside the terminating action, so the diff would report the
      whole board closing at once. The result dialog's breakdown is the right surface
      for that, and it already exists.
    * **The itemisation must reconcile.** The per-player sum of what these events
      claim was paid is checked against the real score delta; if they disagree the
      whole list is replaced by a bare "+N" event. A wrong itemisation is worse than a
      coarse one.
    * **Nothing is mutated.** Both states are read; the meeple-consuming walk that
      ``aux_targets.extract_terminal_ownership`` needs a deepcopy for is not used here.
    """
    if new_state.is_terminated():
        return []
    prev_scores = [int(x) for x in prev_state.scores]
    new_scores = [int(x) for x in new_state.scores]
    n = min(len(prev_scores), len(new_scores))
    delta = [new_scores[p] - prev_scores[p] for p in range(n)]
    if not any(d > 0 for d in delta):
        return []

    def _who(winners: list[int]) -> str:
        names = [("You" if w == human_player else opponent_name) for w in winners]
        return " and ".join(names) if names else "nobody"

    def _generic() -> list[dict]:
        out = []
        for p in range(n):
            if delta[p] <= 0:
                continue
            out.append({
                "kind": "score", "points": delta[p], "winners": [p],
                "meeples_returned": 0,
                "text": f"{_who([p])} +{delta[p]}",
            })
        return out

    try:
        from wingedsheep.carcassonne.objects.meeple_type import MeepleType
        from wingedsheep.carcassonne.objects.terrain_type import TerrainType
        from wingedsheep.carcassonne.utils.city_util import CityUtil
        from wingedsheep.carcassonne.utils.points_collector import PointsCollector
        from wingedsheep.carcassonne.utils.road_util import RoadUtil

        before = _meeple_index(prev_state)
        for player, mp in (claims or []):
            before[_meeple_key(player, mp)] = (int(player), mp)
        after = _meeple_index(new_state)
        gone = [before[k] for k in before.keys() - after.keys()]
        if not gone:
            return _generic()

        # feature key -> {"kind", "points", "cells", "counts"}
        features: dict = {}
        for player, mp in gone:
            if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                return _generic()      # a farm paid out mid-game: not a thing we model
            cws = mp.coordinate_with_side
            coord = cws.coordinate
            tile = new_state.board[coord.row][coord.column]
            if tile is None:
                return _generic()
            terrain = tile.get_type(cws.side)
            if terrain == TerrainType.CITY:
                feat = CityUtil.find_city(new_state, cws)
                kind, cells = "city", frozenset(feat.city_positions)
                points = int(PointsCollector.count_city_points(new_state, feat))
            elif terrain == TerrainType.ROAD:
                feat = RoadUtil.find_road(new_state, cws)
                kind, cells = "road", frozenset(feat.road_positions)
                points = int(PointsCollector.count_road_points(new_state, feat))
            elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                kind = "cloister"
                cells = frozenset({(int(coord.row), int(coord.column))})
                points = int(PointsCollector.chapel_or_flowers_points(new_state, coord))
            else:
                return _generic()
            entry = features.setdefault(
                (kind, cells), {"kind": kind, "points": points, "counts": [0] * n})
            if 0 <= player < n:
                entry["counts"][player] += 1

        events: list[dict] = []
        implied = [0] * n
        for entry in features.values():
            winners = [int(w) for w in
                       PointsCollector.get_winning_players(entry["counts"])]
            for w in winners:
                if 0 <= w < n:
                    implied[w] += entry["points"]
            returned = sum(entry["counts"])
            label = {"city": "City completed", "road": "Road completed",
                     "cloister": "Cloister completed"}[entry["kind"]]
            paid = ", ".join(
                f"{'You' if w == human_player else opponent_name} +{entry['points']}"
                for w in winners) or f"+{entry['points']}"
            back = (f", {returned} meeple{'' if returned == 1 else 's'} back"
                    if returned else "")
            events.append({
                "kind": entry["kind"],
                "points": entry["points"],
                "winners": winners,
                "meeples_returned": returned,
                "text": f"{label} — {paid}{back}",
            })

        if implied != delta[:n]:
            # The parts do not add up to the whole; say the honest coarse thing.
            return _generic()
        # Biggest payout first: the one line a glance catches should be the one that
        # moved the game most.
        events.sort(key=lambda e: -e["points"])
        return events
    except Exception:                             # noqa: BLE001 — never break a move
        return _generic()


# --------------------------------------------------------------------------- #
# 4. Progress counters — module globals, read WITHOUT the session lock.         #
# --------------------------------------------------------------------------- #
_prog_leaf_calls = 0        # cumulative evaluator calls for the CURRENT ai_move
_prog_expected = 0          # k_dets * sims (the nominal leaf budget)
_prog_t0 = 0.0              # perf_counter at ai_move entry; 0.0 == idle
_prog_thinking = False
_prog_tiearb_armed = False  # was the tie arbiter RESOLVED enabled for this session?
_agent_ref = None           # the live agent, for a lock-free `_latched` read

# get_progress()'s "arbiter" phase is a HEURISTIC, not a live signal: `arbitrate`
# (rust/carc/carc-core/src/tiearb.rs) exposes no mid-search arm x playout counter
# over the PyO3 boundary — the whole search+arbitration runs inside one blocking,
# GIL-released `choose_action` call. What IS known: the champion's own un-arbitrated
# move resolves in ~1.5-2.2s on this budget (PRODUCTION.yaml mobile.measured_s_per_move),
# while a tiearb fire adds seconds to tens of seconds on top (mobile.tiearb.
# measured_per_fire_s). So once a THINKING, tiearb-armed session's elapsed time
# crosses this bound, an in-progress fire is the likely explanation — an honest
# estimate, not a proof, which is why the UI label stays generic ("likely
# arbitrating") rather than a bare assertion.
TIEARB_PROGRESS_HEURISTIC_S = 2.0


def _wrap_evaluator_with_counter(agent) -> None:
    """Wrap ``agent._evaluator`` in a counting closure (the cheapest honest seam).

    ``FairHeuristicPriorAgent`` reads ``self._evaluator`` afresh on every
    ``NeuralMCTS`` construction inside ``_pimc_move``, so wrapping AFTER construction
    is picked up by every subsequent search. The wrapper forwards ``*args`` because
    ``NeuralMCTS`` calls ``evaluator(board)`` or ``evaluator(board, parent)`` depending
    on the evaluator's ``wants_parent`` flag (absent on the production evaluator)."""
    inner = getattr(agent, "_evaluator", None)
    if inner is None:                     # tier1 (RuleBasedPlayer) has no evaluator
        return

    def counting(*args):
        global _prog_leaf_calls
        _prog_leaf_calls += 1
        return inner(*args)

    if getattr(inner, "wants_parent", False):
        counting.wants_parent = True
    agent._evaluator = counting


def _expected_leaf_calls(s) -> int:
    """The nominal leaf budget for the progress bar, or 0 meaning "indeterminate".

    The counter above wraps the PYTHON evaluator. When the Rust mirror is the move
    chooser (the default since 2026-08-01) the whole search runs inside `carc_rs` and
    never touches that closure, so a nonzero expectation would render a progress bar
    frozen at 0% for the entire move and then jump to done. Returning 0 makes
    `get_progress` report `fraction: null` instead, which the UI shows as an
    indeterminate spinner — honest rather than stuck. `elapsed_s` and the `search`/
    `exact` phase still work, and at 1.551 s/move there is little to fill anyway."""
    if s is not None and getattr(s, "rs", None) is not None \
            and s.opponent_kind == "champion":
        return 0
    return max(0, s.eff_sims * s.eff_k_dets)


# --------------------------------------------------------------------------- #
# 5. The session                                                                #
# --------------------------------------------------------------------------- #
class _Session:
    """Everything one game needs. One instance lives in the module global ``_S``."""

    def __init__(self, *, seed: int, human_player: int, opponent: str,
                 sims: int | None, k_dets: int | None, verify: bool,
                 generation: int, start_rule: str = START_RULE,
                 grid_rule: str = GRID_RULE,
                 draw_rule: str = DRAW_RULE,
                 cloister_rule: str = CLOISTER_RULE,
                 farm_rule: str = FARM_RULE,
                 cross_rule_replay: bool = False,
                 backend: str = BACKEND_DEFAULT,
                 played_backend: str | None = None,
                 played_sims: int | None = None,
                 played_k_dets: int | None = None,
                 tiearb_level: str = TIEARB_LEVEL_DEFAULT,
                 remote_url: str | None = None,
                 remote_budget_ms: int = REMOTE_DEFAULT_BUDGET_MS,
                 remote_timeout_s: float = REMOTE_DEFAULT_TIMEOUT_S):
        # Remote-opponent wiring (see `RemoteOpponent`). Inert unless `opponent`
        # names the remote kind, so a champion game is unaffected by their
        # presence — the golden-gate property the app's JVM test pins.
        self.remote_url = (str(remote_url) if remote_url else None)
        self.remote_budget_ms = int(remote_budget_ms)
        self.remote_timeout_s = float(remote_timeout_s)
        self.remote: RemoteOpponent | None = None
        self.seed = int(seed)
        # Which start-tile convention this session plays under. New games use the
        # app default (retail); a RESTORE passes whatever the save recorded, so a
        # game archived before the retail start shipped still replays exactly.
        # Reject anything else rather than defaulting: silently picking a rule
        # would decode a DIFFERENT game from the same (deck_seed, actions).
        if start_rule not in (START_RULE_ENGINE, START_RULE_RETAIL):
            raise ValueError(
                f"unknown start_rule {start_rule!r}; expected "
                f"{START_RULE_ENGINE!r} or {START_RULE_RETAIL!r}")
        self.start_rule = str(start_rule)
        # Which GRID this session plays on. Same contract as start_rule, and
        # refused the same way: a save's (deck_seed, actions) decodes a different
        # game on a different grid, so guessing would silently replay the wrong
        # one. `grid_row`/`grid_col` are the resolved engine coordinates.
        if grid_rule not in GRID_RULE_START:
            raise ValueError(
                f"unknown grid_rule {grid_rule!r}; expected one of "
                f"{tuple(GRID_RULE_START)}")
        self.grid_rule = str(grid_rule)
        self.grid_row, self.grid_col = GRID_RULE_START[self.grid_rule]
        # What happens to an UNPLACEABLE tile. Same contract as the two above and
        # refused the same way: the rule flips turn parity after a discard and
        # changes which tiles ever enter play, so the same (deck_seed, actions)
        # decodes a different game and guessing would replay the wrong one.
        if draw_rule not in (DRAW_RULE_ENGINE, DRAW_RULE_REDRAW):
            raise ValueError(
                f"unknown draw_rule {draw_rule!r}; expected "
                f"{DRAW_RULE_ENGINE!r} or {DRAW_RULE_REDRAW!r}")
        self.draw_rule = str(draw_rule)
        # Which CLOISTER SCAN this session plays under. Same contract again: the
        # fix moves when a cloister completes, so the meeple it returns comes back
        # at a different ply and the same log decodes a different game.
        if cloister_rule not in (CLOISTER_RULE_DRIFTING, CLOISTER_RULE_FIXED):
            raise ValueError(
                f"unknown cloister_rule {cloister_rule!r}; expected "
                f"{CLOISTER_RULE_DRIFTING!r} or {CLOISTER_RULE_FIXED!r}")
        self.cloister_rule = str(cloister_rule)
        # WHICH FARM DATA. Validated like the others, and then checked against the
        # PROCESS — because unlike the others this one cannot be honoured per game
        # (block 1a: `base_deck` rewrote its tile table at import and the Rust
        # registry is a OnceLock). A record played under the other farm rule is
        # REFUSED, not replayed: 1/200 measured games diverge in the legal-mask
        # stream, so replaying one here would silently be a different game while
        # the record still claimed the old one.
        if farm_rule not in (FARM_RULE_ENGINE, FARM_RULE_R9):
            raise ValueError(
                f"unknown farm_rule {farm_rule!r}; expected "
                f"{FARM_RULE_ENGINE!r} or {FARM_RULE_R9!r}")
        if str(farm_rule) != FARM_RULE_LATCHED and not cross_rule_replay:
            raise ValueError(
                f"farm_rule {str(farm_rule)!r} cannot be honoured: this process "
                f"latched {FARM_RULE_LATCHED!r} at import ({R9_ENV_VAR}="
                f"{os.environ.get(R9_ENV_VAR, '')!r}). The farm tile data is "
                "process-global — `base_deck` rewrites its table at import and the "
                "Rust registry memoises in a OnceLock — so this game cannot be "
                f"played or replayed here. Restart with {R9_ENV_VAR}="
                f"{'1' if farm_rule == FARM_RULE_R9 else '0'} "
                f"(or CARC_ANDROID_FARM_RULE={str(farm_rule)!r}).")
        # The rule the RECORD was played under, which is what a re-save must keep
        # saying. When it differs from the latch this session is a CROSS-RULE
        # REPLAY: the boards below are built on the process's farm data, and it is
        # `restore_game`'s job to prove — from the record's own stored outcome —
        # that the two rules decode this particular game identically. Until that
        # proof lands the session is not installed, so nothing observes a half-
        # verified replay. See `restore_game`.
        self.farm_rule = str(farm_rule)
        self.cross_rule_replay = bool(self.farm_rule != FARM_RULE_LATCHED)
        # Filled in by `restore_game` once the cross-rule replay has been proved
        # against the record's own outcome; surfaced in the restore response.
        self.rules_note: str | None = None
        # The one-word name for the five levers. Derived, never an input.
        self.rules_profile = rules_profile_name(
            start_rule=self.start_rule, grid_rule=self.grid_rule,
            draw_rule=self.draw_rule, cloister_rule=self.cloister_rule,
            farm_rule=self.farm_rule)
        self.human_player = int(human_player)
        self.opponent_kind = str(opponent)
        self.req_sims = None if sims is None else int(sims)
        self.req_k_dets = None if k_dets is None else int(k_dets)
        self.verify = bool(verify)
        self.generation = int(generation)
        if backend not in (BACKEND_PYTHON, BACKEND_RUST):
            raise ValueError(f"unknown backend {backend!r}; expected "
                             f"{BACKEND_PYTHON!r} or {BACKEND_RUST!r}")
        self.backend = str(backend)
        # What this game was ACTUALLY PLAYED ON before it was saved — the sticky
        # half of the resolution (ROUND2 F-2). `None` for a new game; set from the
        # save blob by `restore_game`. `_build_opponent` reproduces this budget
        # instead of re-resolving, PROVIDED the backend still resolves the same way;
        # if it does not, the pin is dropped (a rust-priced budget on the Python
        # engine is a ~25 s/move hang) and `resume_note` says the game changed
        # engines mid-way.
        self.played_backend = (None if played_backend is None
                               else str(played_backend))
        self.played_sims = None if played_sims is None else int(played_sims)
        self.played_k_dets = None if played_k_dets is None else int(played_k_dets)
        self.resume_note: str | None = None
        # What was ASKED FOR, kept apart from what was RESOLVED: `self.backend` is
        # rewritten in place when the wheel is missing, and the two cases must not
        # produce the same on-screen claim (ROUND2 F-7).
        self.backend_requested = str(backend)
        # The Rust mirror, or None. `apply()` is the ONE place it is advanced.
        self.rs = None
        self.rs_note: str | None = None
        # OS threads the mirror folds its k worlds across; resolved from the YAML
        # profile by `_build_opponent` (None until then, and for tier1).
        self.rust_threads: int | None = None
        # THE TIE-ARBITER LEVEL. Which Settings-screen tier this session asked for
        # ("b32"/"b16"/"b8"/"off") — validated like the other rule/backend levers,
        # never guessed. ⚠️ UNLIKE `backend`/`sims`/`k_dets`, this is deliberately
        # NOT sticky across a restore (no `played_tiearb_level`): the arbiter is a
        # pure search-QUALITY knob — it changes no legality, no RNG stream, no
        # replay determinism (`arbitrate` is a post-search root tie-break; the
        # `(deck_seed, actions)` contract is unaffected either way) — so resuming
        # a save at the user's CURRENT setting is safe by construction, unlike
        # resuming at a different BUDGET, which the sticky fields exist to
        # prevent because it would misrepresent what a resumed E4 game ran at.
        # "Next game" (task requirement 2) is read as "next session build";
        # restore_game builds one too, so a setting change takes effect there as
        # well as at new_game — never mid-search inside a live `ai_move` call.
        if tiearb_level not in TIEARB_LEVELS:
            raise ValueError(
                f"unknown tiearb_level {tiearb_level!r}; expected one of "
                f"{TIEARB_LEVELS}")
        self.tiearb_level = str(tiearb_level)
        # Safe default until `_build_opponent` resolves it; also what a tier1
        # session (no search at all) keeps. Never crash on a missing/malformed
        # profile — this dict staying `{"enabled": False, ...}` IS the fail-closed
        # behaviour requirement 1 asks for.
        self.tiearb: dict = _tiearb_off(self.tiearb_level, from_yaml=False,
                                        reason=None)

        self.game = self.rules_game()
        # The agent gets its OWN Game (mirrors play_vs_tier1_gui.build_opponent): the
        # UI-side Game carries a legal-moves cache and the agent may run on another
        # thread, so private Games remove any chance of a cross-thread cache race.
        # Same rules on both, from the same builder — a lever that reached one Game
        # and not the other would have the agent searching a different game than the
        # one on screen (`draw_rule` and `cloister_scan_fix` both reach the search;
        # `fixed_start_tile` only affects get_init_board, which this one never calls).
        self.ai_game = self.rules_game()

        self.agent = None
        self.pick = None
        self.manifest = None
        self.budget_note = None
        self.opponent_name = ""
        self.eff_sims = 0
        self.eff_k_dets = 0
        self._build_opponent()

        # Deck seeding must be the LAST thing before get_init_board: the engine draws
        # its shuffle from the GLOBAL random stream there and nowhere else, which is
        # what makes (deck_seed, action_log) a lossless save (root_replay contract).
        random.seed(self.seed)
        self.board: Board = self.game.get_init_board()

        # Opt-in only; a failure here degrades to the Python path with a note
        # rather than killing the game (the wheel may simply be absent).
        if self.backend == BACKEND_RUST:
            self._start_rust_mirror()

        self.action_log: list[int] = []
        self.turn = 0
        self.ai_last_tile: tuple[int, int] | None = None
        self.ai_last_move: dict | None = None
        # One record per AI decision: {"ply", "elapsed_s"}. Live play only — a
        # RESTORED game replays its log without searching, so the timings of the
        # original session are simply not reconstructable and the list starts empty
        # rather than carrying invented numbers. Two floats a move; the archive
        # record is the only reader.
        self.ai_elapsed: list[dict] = []

        # HOW MANY TIMES THE NEXT-TILE PEEK WAS SERVED in this game (the M3 UI
        # feature "let me see my next one also"). Counted rather than flagged so
        # the stamp cannot be a claim about a setting that was toggled off before
        # it was ever used: `preview_next_tile` in the archive is exactly
        # `peek_count > 0`, i.e. "the human was shown the upcoming tile at least
        # once in this game". Carried across a restore through the save payload,
        # so resuming does not launder the peek out of the record. The E4 ledger
        # conditions on the archive field; nothing on the DECISION path reads this.
        self.peek_count: int = 0

        # The position BEFORE the most recent action, kept solely so the end-of-game
        # breakdown can be reconstructed (see `_final_breakdown`). Free: the engine's
        # `get_next_state` already deepcopies, so the previous Board was going to be
        # discarded anyway — this just holds the reference instead of dropping it.
        self.prev_board: Board | None = None
        self.last_action: int | None = None
        # Memoised `_final_breakdown` (the terminal `_state_dict` is rebuilt on
        # every `get_state`, and the reconstruction is a deepcopy + a full
        # feature traversal — not something to repeat on a poll).
        self.breakdown: list[dict] | None = None
        self.breakdown_done: bool = False

        # What the most recent DECISION paid out (see `scoring_events`). Replaced
        # wholesale by `apply_and_collect`, so it always describes exactly one
        # decision — never an accumulation across a turn.
        self.last_events: list[dict] = []

    # -- the rules, in ONE place -------------------------------------------- #
    def rules_game(self, *, cache: bool = True) -> Game:
        """A ``Game`` carrying THIS session's four per-game rule levers.

        The single constructor for every ``Game`` a session builds — the UI one,
        the agent's private one, and the throwaway one ``preview_meeple_slots``
        drives. A lever that reached one and not another is the half-applied
        profile F9 exists to detect, and the only defence against it is that
        there is exactly one call site.

        The FIFTH lever, ``farm_rule``, is deliberately absent: it is not a
        ``Game`` kwarg and cannot be (block 1a). ``__init__`` has already proved
        the session agrees with the process latch, so every ``Game`` built here
        is on the session's farm data by construction.
        """
        return Game(
            enable_legal_moves_cache=cache,
            fixed_start_tile=(self.start_rule == START_RULE_RETAIL),
            # `start_row`/`start_col` are opt-in on `Game`; with the legacy grid
            # they are the engine's own values and `Game` makes the byte-identical
            # call it always did (game_wrapper.check_start_position / `recentred`).
            start_row=self.grid_row, start_col=self.grid_col,
            draw_rule=self.draw_rule,
            # Spelled False rather than omitted for the drifting rule: `Game`'s own
            # default is False, so the two are the same call, and naming it keeps
            # the levers visible together at the one place they are applied.
            cloister_scan_fix=(self.cloister_rule == CLOISTER_RULE_FIXED),
        )

    # -- opponent construction (mirrors play_vs_tier1_gui.build_opponent) ----
    def _build_opponent(self) -> None:
        if self.opponent_kind == "tier1":
            from carcassonne_ai.rule_based_player import RuleBasedPlayer

            tier1 = RuleBasedPlayer(seed=self.seed)
            self.agent = tier1
            self.pick = lambda board: int(
                tier1.choose_action(self.ai_game, board,
                                    self.ai_game.get_valid_moves(board)))
            self.opponent_name = "Tier-1"
            self.budget_note = None
            self.eff_sims = 0
            self.eff_k_dets = 0
            return

        if is_remote_opponent(self.opponent_kind):
            # REMOTE CARCASUM. No search happens on this device: `pick` is one
            # HTTP round-trip to `scripts/carcasum_remote/server.py`, which owns
            # the live Carcasum process and the whole coordinate/meeple/inversion
            # correspondence (reused from `scripts/carcasum_match/match.py`).
            #
            # `opponent_kind` is NORMALISED to the labelled form here so the save
            # and the archive both record WHICH budget played — and so that a
            # reader conditioning on `opponent == "champion"` can never mistake
            # this game for an anchor game.
            if not self.remote_url:
                raise ValueError(
                    "the remote opponent needs `remote_url` in new_game's config "
                    "(the tailnet address of the laptop running "
                    "scripts/carcasum_remote/server.py)")
            self.opponent_kind = remote_opponent_label(self.remote_budget_ms)
            remote = RemoteOpponent(url=self.remote_url, session=self,
                                    budget_ms=self.remote_budget_ms,
                                    timeout_s=self.remote_timeout_s)
            # Fail at game start, not three plies in, if the daemon is not there.
            remote.check_health()
            self.remote = remote
            self.agent = remote
            self.pick = lambda board: int(remote.choose_action(board))
            self.manifest = None
            # NAMED BY THE SERVER, not by our copy of its config — see
            # `remote_display_name`. `check_health` has already run, so
            # `remote.health` is the daemon's own self-description.
            self.opponent_name = remote_display_name(remote.health,
                                                     self.remote_budget_ms)
            # The remote opponent is OUT OF LINEAGE, and the app renders
            # `budget_note` wherever it needs to warn about what is playing. It was
            # None, which left every remote game presenting itself with no caveat
            # at all in the status bar, the end-of-game dialog and Past games.
            self.budget_note = (
                f"REMOTE OPPONENT — {self.opponent_name} is Carcasum (2014 MCTS), "
                f"running on another machine and reached over the network. It is "
                f"NOT the champion and NOT in its lineage; this game is archived "
                f"as {self.opponent_kind!r} and is deliberately excluded from the "
                f"champion record.")
            self.eff_sims = 0
            self.eff_k_dets = 0
            return

        if self.opponent_kind != "champion":
            raise ValueError(f"opponent must be 'champion'|'tier1'|"
                             f"'{REMOTE_OPPONENT_PREFIX}...'; got "
                             f"{self.opponent_kind!r}")

        spec = champion_factory.load_production_spec()
        # BACKEND FIRST, BUDGET SECOND — they are one decision (2026-08-01 unpin). The
        # mobile profile now names the CHAMPION-OF-RECORD budget, which is only payable
        # on `carc_rs`; if the wheel cannot be imported we must demote the budget too,
        # not just the engine, or the phone inherits a ~25 s/move hang.
        if self.backend == BACKEND_RUST and not rust_available():
            self.backend = BACKEND_PYTHON
            self.rs_note = (f"carc_rs unavailable ({_RUST_IMPORT_ERROR}); using the "
                            f"Python backend at the k"
                            f"{ANDROID_FALLBACK_BUDGET['k_dets']}x"
                            f"{ANDROID_FALLBACK_BUDGET['sims_per_det']} floor")
        mob = budget_for_backend(self.backend, spec)
        # STICKY PER GAME (ROUND2 F-2). A resumed game keeps the budget it was PLAYED
        # at rather than re-resolving against today's device answer — before the
        # 2026-08-01 unpin the mobile profile was pinned unconditionally, so a restore
        # always reproduced the played budget by construction; once the budget became
        # conditional on the backend resolving to rust, "played at 11008, resumed at
        # 2752" needed no code change to happen, and the archive recorded only the
        # post-restore half. The pin is DROPPED if the backend itself resolved
        # differently — the budget is priced for the engine, so carrying it across an
        # engine change would be the ~25 s/move hang, not fidelity.
        pinned = (self.played_sims is not None and self.played_k_dets is not None)
        if pinned and self.played_backend == self.backend:
            eff_sims, eff_k = int(self.played_sims), int(self.played_k_dets)
        else:
            eff_sims, eff_k = mob["sims_per_det"], mob["k_dets"]
            if pinned:
                self.resume_note = (
                    f"RESUMED ON A DIFFERENT ENGINE — this game was played on the "
                    f"{self.played_backend!r} backend at k{self.played_k_dets}x"
                    f"{self.played_sims}={self.played_k_dets * self.played_sims}; "
                    f"this device resolved {self.backend!r}, so the rest of it runs "
                    f"k{eff_k}x{eff_sims}={eff_k * eff_sims}. The two halves were not "
                    f"played against the same opponent — grade them separately.")
        # An explicit request always wins: it is a deliberate act by the caller
        # (a debug screen, a difficulty tier, a test), not a resolution.
        if self.req_sims is not None:
            eff_sims = int(self.req_sims)
        if self.req_k_dets is not None:
            eff_k = int(self.req_k_dets)
        self.rust_threads = mob["rust_threads"]
        # THE TIE ARBITER — resolved AFTER backend, for the same reason budget is:
        # it is RUST-ONLY (champion_factory: "tiearb is RUST-ONLY"), so a request
        # against a backend that just demoted to python must fail closed here, not
        # crash later inside `_start_rust_mirror`. `mobile_tiearb` itself never
        # raises; this is the one place its answer can still be overridden to OFF.
        self.tiearb = mobile_tiearb(self.tiearb_level, spec)
        if self.tiearb["enabled"] and self.backend != BACKEND_RUST:
            self.tiearb = _tiearb_off(
                self.tiearb_level, from_yaml=self.tiearb["from_yaml"],
                reason=(f"backend resolved to {self.backend!r}; the tie arbiter "
                        "is rust-only"))
        # parallel_workers is deliberately NEVER passed here: the fair agent's split uses
        # spawn processes, which Chaquopy cannot provide. Omitting it is the byte-identical
        # sequential path — the SAME player, just slower, not a different agent.
        #
        # backend=BACKEND_PYTHON is passed EXPLICITLY, and that is deliberate even though
        # the session may be running Rust. This agent is the bridge's Python anchor — it
        # owns the manifest, the progress evaluator and the `_move_idx` a restore reseats
        # — while the Rust move CHOOSER is the separate `self.rs` mirror, advanced at
        # `apply()`. `champion_factory.RustFairAgent` is NOT a drop-in for that role: its
        # mirror only moves on an explicit `.advance()`, so pinning the engine here keeps
        # a future factory-default flip from silently swapping the anchor underneath us.
        agent = champion_factory.make_production_champion(
            "fair", game=self.ai_game, seed=self.seed, sims=eff_sims, k_dets=eff_k,
            exact_endgame=True, verify=self.verify, backend=BACKEND_PYTHON,
            # Bound the endgame solver on-device: the desktop default is 2,000,000
            # nodes with no wall-clock component and no mid-search cancel, so a bad
            # board is an unbounded hang on a phone. 100k is ~45x the largest solve
            # ever observed (2,214 nodes across 9 real endgames) — it should never
            # fire; if it does, that one move is the documented PIMC fallback.
            # See measurement/ANDROID_WALLCLOCK_MEMO_20260728.md (lever #1).
            exact_budget=ANDROID_EXACT_BUDGET,
        )
        _wrap_evaluator_with_counter(agent)
        self.agent = agent
        self.pick = lambda board: int(agent.choose_action(board))
        self.manifest = getattr(agent, "manifest", None)
        self.eff_sims, self.eff_k_dets = eff_sims, eff_k

        self.opponent_name = "Champion"
        self.budget_note = None
        full = spec.k_dets * spec.sims_per_det
        requested = self.req_sims is not None or self.req_k_dets is not None
        resumed_at_played = (pinned and self.played_backend == self.backend
                             and not requested)
        if (eff_sims, eff_k) != (mob["sims_per_det"], mob["k_dets"]):
            if resumed_at_played:
                # RESUMED AT ITS OWN BUDGET, which happens to differ from what this
                # device would resolve today. Deliberate: the game keeps the opponent
                # it was played against (ROUND2 F-2).
                self.budget_note = (
                    f"RESUMED AT THE BUDGET THIS GAME WAS PLAYED AT — k{eff_k}x"
                    f"{eff_sims}={eff_k * eff_sims} sims/move on the "
                    f"{self.backend!r} backend, vs the k{mob['k_dets']}x"
                    f"{mob['sims_per_det']}={mob['total_sims']} this device would "
                    f"resolve now. The whole game is one opponent; grade it at this "
                    f"budget.")
                self.opponent_name = f"Champion(resumed k{eff_k}x{eff_sims})"
            else:
                # The user (or a debug screen) asked for LESS than the device profile.
                self.budget_note = (
                    f"BELOW CHAMPION BUDGET — running k{eff_k}x{eff_sims}="
                    f"{eff_k * eff_sims} sims/move vs this device's "
                    f"k{mob['k_dets']}x{mob['sims_per_det']}="
                    f"{mob['total_sims']} (champion of record: "
                    f"k{spec.k_dets}x{spec.sims_per_det}={full}). This is a WEAKENED "
                    f"agent; beating it is not beating the champion.")
                self.opponent_name = f"Champion(weakened k{eff_k}x{eff_sims})"
        elif mob.get("floored"):
            # DEGRADED: the profile named the champion budget on the Rust core, but this
            # session is running the Python one, so both the engine and the budget
            # dropped to the floor. The game is playable; it is not the champion of
            # record, and an E4 archive from it must be graded at the floor.
            #
            # ⚠️ TWO CAUSES, TWO SENTENCES (ROUND2 F-7). `floored` only says "python
            # here, rust in the profile" — it cannot tell a MISSING WHEEL from a caller
            # that asked for `backend: "python"`. Keying the note purely on it asserted
            # a hardware fact ("no Rust core on this device") that was simply false for
            # the requested case, and `archive_record` persists that sentence into the
            # permanent E4 record.
            if self.backend_requested == BACKEND_PYTHON:
                self.budget_note = (
                    f"REDUCED — this game was started on the Python backend by "
                    f"request, and the champion budget k{spec.k_dets}x"
                    f"{spec.sims_per_det}={full} is not payable there (~25 s/move). "
                    f"Running the k{mob['k_dets']}x{mob['sims_per_det']}="
                    f"{mob['total_sims']} floor instead. Same agent, same leaf, "
                    f"smaller search — grade results against this budget, not the "
                    f"champion's. (This says nothing about the device: the Rust core "
                    f"was not asked for.)")
            else:
                self.budget_note = (
                    f"REDUCED — no Rust core on this device, so the champion budget "
                    f"k{spec.k_dets}x{spec.sims_per_det}={full} is not payable here "
                    f"(it is ~25 s/move on the Python engine). Running the "
                    f"k{mob['k_dets']}x{mob['sims_per_det']}={mob['total_sims']} floor "
                    f"instead. Same agent, same leaf, smaller search — grade results "
                    f"against this budget, not the champion's.")
            self.opponent_name = f"Champion(reduced k{eff_k}x{eff_sims})"
        elif mob["total_sims"] != full:
            # Running exactly the device profile, and the profile DIFFERS from the
            # champion of record.
            #
            # ⚠️ DIRECTION-AWARE SINCE 2026-08-25, and that is not cosmetic. This branch
            # used to hardcode the word BELOW, because for its whole life the phone could
            # only ever be the WEAKER side: it was the 2026-07-29 .. 2026-08-01 k4x688
            # carve-out's normal state, and after the unpin it was reachable only by a
            # hand-edited YAML. The owner's k16x1376 = 22016 mobile fold inverted it — the
            # phone is now the first deploy profile in the program to run ABOVE the
            # champion of record — and this string is BOTH rendered in the app (status
            # bar, end-of-game dialog, Settings) AND persisted verbatim into the permanent
            # E4 archive by `archive_record`. Left hardcoded it would have written
            # "BELOW ... smaller search" onto every game played at TWICE the champion
            # budget: a false sentence on screen and a false sentence in the record.
            # Honest, and archived with the game — E4 must grade against THIS budget.
            above = mob["total_sims"] > full
            self.budget_note = (
                f"MOBILE PROFILE — k{mob['k_dets']}x{mob['sims_per_det']}="
                f"{mob['total_sims']} sims/move, the on-device budget, "
                f"{'ABOVE' if above else 'BELOW'} the champion "
                f"of record k{spec.k_dets}x{spec.sims_per_det}={full}. Same agent, same "
                f"leaf, {'larger' if above else 'smaller'} search — grade results against "
                f"this budget, not the champion's.")

    # -- the Rust mirror (P7, opt-in) ---------------------------------------
    def _full_deck_descriptions(self) -> list[str]:
        """The shuffled deck in DRAW order, as descriptions.

        ``FairAgentRs.start_game_from_deck`` is the phone path precisely because
        it carries no RNG dependence: the deck crosses the FFI as data, so the
        mirror cannot drift by reproducing a shuffle slightly differently.

        Reconstructing that order from the LIVE state is not possible — the state
        has already popped ``next_tile``, and the retail rule additionally removes
        the D tile from an unrecorded position in the pool. So a throwaway state
        is built under the same seed and read BEFORE either of those happens.
        ``random.seed`` is re-primed afterwards so the real board draws exactly
        the same deck; ``_assert_mirror`` then proves it did.
        """
        from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState

        # Hermetic: the probe re-seeds and consumes the same draws the real board
        # already made, so the global stream is put back exactly as found. The
        # board is built by the time this runs, so nothing downstream is known to
        # depend on it — but "known" is doing too much work in a bridge that
        # opted into an extra RNG consumer, and restoring costs one tuple.
        saved = random.getstate()
        try:
            random.seed(self.seed)
            probe = CarcassonneGameState(
                players=self.game.players,
                tile_sets=list(self.game.tile_sets),
                supplementary_rules=list(self.game.supplementary_rules),
            )
            # __init__ pops next_tile off the front, so the pool is next_tile + deck.
            pool = [probe.next_tile] + list(probe.deck)
            return [t.description for t in pool if t is not None]
        finally:
            random.setstate(saved)

    def _assert_mirror(self, where: str, board: Board | None = None) -> None:
        """The mirror must render the SAME board bytes as the Python engine.

        `string_representation` is the node key the whole port is gated on (G1),
        so equality here is the same claim the desktop gates make — checked at
        game start always, before EVERY decision (see `_rust_pick`), and after
        every action when CARC_RS_RECONCILE=1.
        """
        board = self.board if board is None else board
        want = self.game.string_representation(board)
        got = self.rs.string_repr()
        if want != got:
            raise RuntimeError(
                f"rust mirror diverged at {where}: repr differs "
                f"(python {len(want)}B, rust {len(got)}B)")

    def _rust_pick(self, board) -> int:
        """The champion's decision, taken by the Rust mirror.

        ⚠️ THE SYNC CHECK IS UNCONDITIONAL, not reconcile-gated (REVIEW.md C-i,
        CONFIRMED 2026-08-02). This used to be
        `lambda board: int(self.rs.choose_action())` — which ignored its `board`
        argument entirely, so the one surface a human plays against was the only
        caller in the repo with NO mirror guard at all: `_assert_mirror` ran at game
        start and then per-ply only under `CARC_RS_RECONCILE`, a module constant read
        once at import and off on the phone. A mirror that went stale for any reason
        would go on answering, with a move computed for a position the game had left.
        `RustFairAgent.choose_action` was given exactly this guard, unconditionally,
        on 2026-08-01 (`rust_agent.py`) at a measured 0.005% of a decision; the phone
        pays proportionally less, because its decision is longer, not shorter.
        """
        self._assert_mirror("choose_action", board)
        return int(self.rs.choose_action())

    def _degrade_to_python(self, note: str) -> None:
        """Lose the speedup AND the budget it bought — never the game.

        Since the 2026-08-01 unpin the on-device budget is the champion of record,
        priced for the Rust core (1.551 s/move) and unplayable on the Python one
        (~25 s/move). So a failed mirror cannot just swap the engine and keep the
        budget: `_build_opponent` is re-run, which re-resolves through
        `budget_for_backend()` and lands on the k4x688 floor. Safe to rebuild here
        because the mirror starts before any action is applied — the agent has no
        state to lose."""
        self.rs = None
        self.backend = BACKEND_PYTHON
        self._build_opponent()
        self.rs_note = note          # after the rebuild, which may set its own note

    def _degrade_mid_game(self, note: str) -> None:
        """The same demotion, but with a game already in progress (REVIEW.md C-i).

        `_degrade_to_python` is explicitly documented as safe only BEFORE any action
        is applied, because rebuilding the opponent resets the agent's move counter.
        Mid-game there are two extra jobs:

        * re-seat `_move_idx` to the number of AI decisions already taken, exactly as
          `restore_game` does — the per-move search seeds derive from it, so a fresh
          zero would make the rest of the game a different champion;
        * repoint the module-level `_agent_ref`, which `get_progress` reads.

        The budget still drops to the floor, which is the point: continuing at a
        rust-priced 11008 on the Python engine is a ~25 s/move phone hang."""
        global _agent_ref
        decisions = len(self.ai_elapsed)
        self._degrade_to_python(note)
        if hasattr(self.agent, "_move_idx"):
            self.agent._move_idx = decisions
        if _S is self:
            _agent_ref = self.agent

    def _start_rust_mirror(self) -> None:
        try:
            import carc_rs
        except ImportError as exc:
            self._degrade_to_python(
                f"carc_rs unavailable ({exc}); using the Python backend")
            return
        # ⚠️ THE TWO ENGINES MUST BE ON THE SAME FARM DATA, and neither of them can
        # be told which after the fact: `base_deck` rewrote its tile table at ITS
        # import and `carc_rs`'s registry memoises in a `OnceLock` the first time
        # anything asks for it. Normally both read the same `CARCASSONNE_FIX_R9`
        # that block 1a set before either import and they agree by construction —
        # but "before either import" is an ORDERING claim, and the one process
        # where it can fail is the instrumented-test process, where another test
        # class may have built a Rust game (latching the registry) before this
        # module was ever imported. That divergence would surface as a mirror
        # mismatch several plies later, blamed on the search. Check it here, where
        # the answer is one call and the fix is a degrade to a single engine.
        rust_farm = FARM_RULE_R9 if carc_rs.r9_enabled() else FARM_RULE_ENGINE
        if rust_farm != FARM_RULE_LATCHED:
            self._degrade_to_python(
                f"carc_rs latched farm_rule={rust_farm!r} but this process is on "
                f"{FARM_RULE_LATCHED!r} — the Rust tile registry was built before "
                f"{R9_ENV_VAR} was set, so the two engines would score farms "
                "differently. Using the Python backend.")
            return
        # The mirror is a state mirror FIRST and a move chooser second. Against
        # tier1 the session has no search budget at all (eff_sims/eff_k_dets are
        # 0), but the mirror is still worth building — it is what proves the
        # bridge's deck harvest and choke point are right — so fall back to this
        # device's champion profile for a config that is valid and never searched.
        mob = mobile_budget()
        sims = int(self.eff_sims) or int(mob["sims_per_det"])
        k_dets = int(self.eff_k_dets) or int(mob["k_dets"])
        # The k worlds fold across OS threads INSIDE one GIL-released call — the
        # mechanism that made the unpin possible, since Chaquopy has no processes.
        # From the YAML profile (rust_threads: 4), never hardcoded here.
        threads = int(self.rust_threads or mob["rust_threads"]
                      or ANDROID_FALLBACK_RUST_THREADS)
        try:
            # THE LEAF THAT WILL PLAY, DERIVED FROM THE YAML — not a preset.
            #
            # This used to be `carc_rs.LeafConfigRs.curve125()`, whose own docstring
            # says it is "a convenience for tests only" and which hard-codes the leaf
            # shape on the Rust side. Using it here broke DESIGN CONTRACT 3 in the way
            # that matters most: every save and archive stamps the YAML's `leaf_hash`
            # (`_spec_fingerprint`), so the record asserted a leaf the executed engine
            # was never checked against — a LABEL, not the function. Exactly the
            # R1/R7 failure `champion_factory` exists to prevent.
            #
            # Now: `production_leaf_cfg(spec)` resolves the leaf from PRODUCTION.yaml +
            # the PROD_ENV set at the top of this module, `leaf_config_rs` translates it
            # field-for-field (the mapping G2 gated bit-exact over 3,341,772 values in
            # all 12 config dialects), and `verify_leaf(..., backend="rust")` proves it
            # on real boards through carc_rs BEFORE a move is played or archived.
            from carcassonne_ai.rust_agent import leaf_config_rs

            spec = champion_factory.load_production_spec()
            leaf_cfg = champion_factory.production_leaf_cfg(spec)
            if self.verify:
                # Raises ProvenanceError unless BOTH panels (python and rust) equal the
                # golden AND the three leaf-hash dialects match. Fail loud, never warn.
                champion_factory.verify_leaf(leaf_cfg, spec, backend="rust")
            leaf = leaf_config_rs(leaf_cfg)
            # THE TIE ARBITER — conditional-keyword, same discipline as the desktop's
            # `rust_agent.search_config_rs()`: omit every `tiearb_*` kwarg entirely
            # when disarmed, so a `carc_rs` wheel built before the arbiter existed
            # still constructs this exact call unchanged. `self.tiearb["enabled"]`
            # is the RESOLVED answer from `_build_opponent` (`mobile_tiearb()`),
            # already fail-closed against a missing YAML block, an unknown level, a
            # B this build does not offer, and a backend that is not rust.
            tiearb_kw = {}
            if self.tiearb.get("enabled"):
                tiearb_kw = dict(
                    tiearb_enabled=True,
                    tiearb_b=int(self.tiearb["B"]), tiearb_j=int(self.tiearb["J"]),
                    tiearb_mode=str(self.tiearb["mode"]),
                    tiearb_salt=str(self.tiearb["salt"]),
                    tiearb_eps=float(self.tiearb["eps"]),
                    tiearb_threads=int(self.tiearb["threads"]),
                )
            search = carc_rs.SearchConfigRs(
                leaf, sims,
                float(self.spec_knob("c_puct")), float(self.spec_knob("tau_p")),
                float(self.spec_knob("value_norm")), SCORE_NORM_SCALE,
                str(self.spec_knob("leaf_quantize")), str(self.spec_knob("final_select")),
                None, 1.0,
                ANDROID_EXP_FMA, ANDROID_TANH_FLAVOR,
                **tiearb_kw,
            )
            self.rs = carc_rs.FairAgentRs(
                search, k_dets=k_dets, seed=int(self.seed),
                min_pooled_visits=2.0, exact_endgame=True, exact_max_k=2,
                exact_budget=ANDROID_EXACT_BUDGET, tt_cap=0, chance_drop="type",
                threads=threads,
                # Start-rule semantics are preserved EXACTLY: the mirror is told
                # the session's own rule, and "engine" is spelled None on the FFI
                # (the P5 flag default), matching what a save with no `start_rule`
                # means on this side.
                start_rule=(None if self.start_rule == START_RULE_ENGINE
                            else self.start_rule),
                # SAME GRID, or the champion searches a different game than the
                # one on screen. The P5 flags surface takes the resolved engine
                # coordinates and applies the same EVEN-shift refusal as
                # `game_wrapper.check_start_position`; the legacy grid is spelled
                # None, matching what a save with no `grid_rule` means here.
                start_row=(None if self.grid_rule == GRID_RULE_ENGINE6
                           else self.grid_row),
                start_col=(None if self.grid_rule == GRID_RULE_ENGINE6
                           else self.grid_col),
                # SAME UNPLACEABLE-TILE RULE, or the mirror diverges the first
                # time a tile cannot be placed — a different player would owe the
                # next decision and a different tile would be drawn. "engine" is
                # spelled None on the FFI (the flag default), matching what a save
                # with no `draw_rule` means on this side.
                draw_rule=(None if self.draw_rule == DRAW_RULE_ENGINE
                           else self.draw_rule),
                # SAME CLOISTER SCAN, or the mirror scores a cloister on a
                # different ply and returns its meeple at a different ply — the
                # `_assert_mirror` board-bytes check would catch it, but only
                # after the search had already been run on the wrong rules. The
                # drifting rule is spelled None (the P5 flag default), matching
                # what a save with no `cloister_rule` means on this side.
                cloister_scan_fix=(None if self.cloister_rule == CLOISTER_RULE_DRIFTING
                                   else True),
                # ⚠️ NO `farm_rule` HERE, and none is possible: the Rust tile
                # registry is a `OnceLock` keyed off the same CARCASSONNE_FIX_R9
                # this process set in block 1a, so the mirror is ALREADY on the
                # session's farm data by construction. `_Session.__init__` is
                # what guarantees the session agrees with the latch.
            )
            self.rs.start_game_from_deck(self._full_deck_descriptions())
            self._assert_mirror("game start")
            if self.tiearb.get("enabled"):
                # "CANNOT SILENTLY NO-OP" (PRODUCTION.yaml fair_deploy.tiearb): the
                # desktop harness RAISES if it armed the arbiter but the champion's
                # own telemetry disagrees (`play_harness._champ_tiearb_telemetry`).
                # The app's fail-closed contract forbids the raise — so instead the
                # ARCHIVE'S claim is downgraded to match reality, never the other
                # way around, and never silently: `rs_note` says so on screen.
                try:
                    live = self.rs.stats()
                except Exception:                  # noqa: BLE001 — telemetry only
                    live = None
                if not (isinstance(live, dict) and bool(live.get("tiearb_enabled"))):
                    self.tiearb = {**self.tiearb, "enabled": False,
                                   "reason": "armed but FairAgentRs.stats() did not "
                                             "confirm tiearb_enabled=True"}
                    self.rs_note = ((self.rs_note + "; " if self.rs_note else "")
                                    + "tie arbiter requested but not confirmed live")
        except BaseException as exc:              # noqa: BLE001
            # ⚠️ BaseException, not Exception (REVIEW.md C-a): this IS the degrade
            # net, and the failure it exists to absorb — a Rust panic — arrives as
            # `pyo3_runtime.PanicException`, which does not derive from `Exception`.
            # A safety net whose stated job is to keep the app playable when the Rust
            # core misbehaves cannot be scoped to the misbehaviours already known.
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            self._degrade_to_python(
                f"rust backend failed to start ({type(exc).__name__}: {exc})")
            return
        # Only the CHAMPION's move choice moves to Rust. Tier-1 is a different
        # agent entirely (RuleBasedPlayer, no search) and has no Rust port; its
        # session keeps the mirror for state, not for picking.
        if self.opponent_kind == "champion":
            self.pick = self._rust_pick
        else:
            self.rs_note = ("mirror only: the rust backend replaces the CHAMPION's "
                            f"move choice, and this game's opponent is "
                            f"{self.opponent_kind!r}")
        self._stamp_backend_on_manifest()

    def _stamp_backend_on_manifest(self) -> None:
        """Record IN THE MANIFEST that `carc_rs` is the one playing (ROUND2 F-8).

        `get_manifest()`'s docstring says it returns "the manifest of the agent that
        is ACTUALLY playing", but the manifest comes from the bridge's PYTHON anchor,
        built with `backend=BACKEND_PYTHON` on purpose — and `champion_factory` stamps
        its backend block "ONLY when it is not the python default". So under the
        2026-08-01 rust default the phone carried a byte-identical pure-Python
        manifest while `self.rs` was the move chooser: the Settings "resolved AI
        manifest" sheet asserted Python about a game Rust was playing. The archive got
        `backend` for exactly this reason (2ca65c0); this is the same fact in the other
        record. `champion_factory`'s own rationale for the block is "a log records
        which engine played"."""
        if self.rs is None or not isinstance(self.manifest, dict):
            return
        module = None
        version = None
        try:
            import carc_rs

            module = getattr(carc_rs, "__file__", None)
            version = _rust_wheel_version()
        except BaseException:                     # noqa: BLE001 — provenance only
            pass
        # A COPY: `agent.manifest` belongs to champion_factory and other readers.
        self.manifest = {
            **self.manifest,
            "backend": {
                "name": BACKEND_RUST,
                # The mirror is a state mirror first; against tier1 it never picks.
                "role": ("move_chooser" if self.opponent_kind == "champion"
                         else "state_mirror_only"),
                "anchor": BACKEND_PYTHON,
                "rust_threads": self.rust_threads,
                "module": module,
                "wheel_version": version,
                "note": ("carc_rs picks the champion's moves; the Python anchor in "
                         "this session owns the manifest, the progress evaluator and "
                         "the legality/scoring/save record."),
            },
        }

    def spec_knob(self, name: str):
        """One champion knob from PRODUCTION.yaml (no strength number is ever
        hardcoded here — DESIGN CONTRACT 3)."""
        return getattr(champion_factory.load_production_spec(), name)

    # -- board mechanics ----------------------------------------------------
    @property
    def ai_player(self) -> int:
        return 1 - self.human_player

    def legal_mask(self):
        return self.game.get_valid_moves(self.board)

    def legal_ids(self) -> list[int]:
        return [int(i) for i in np.flatnonzero(self.legal_mask())]

    def _pass_index(self) -> int:
        size = self.board.offset.size
        return (tile_pass_index(size) if self.board.state.phase == GamePhase.TILES
                else meeple_pass_index(size))

    def apply(self, action_id: int) -> None:
        """Apply one action to the engine AND the mirror, or to neither.

        ⚠️ FAILURE-ATOMIC since 2026-08-02 (REVIEW.md C-i). It used to mutate the
        Python side first and then call `self.rs.advance(...)` with no rollback, so
        any FFI failure left Python one ply ahead of a mirror that then stayed
        permanently stale — `apply_action` caught it, returned an error JSON, and
        KEPT `_S` live with the mirror still seated as the move chooser. Nothing
        detected it afterwards, because the per-ply reconcile is off on the phone.
        Now the Python half is snapshotted and rolled back, the mirror is dropped,
        and the game continues on the Python engine at the floor budget."""
        snapshot = (self.prev_board, self.board, self.last_action, self.turn)
        self.prev_board = self.board
        self.last_action = int(action_id)
        self.board, _ = self.game.get_next_state(self.board, int(action_id))
        self.action_log.append(int(action_id))
        self.turn += 1
        # THE single step choke point: every applied action, both seats, exactly
        # once. The mirror is advanced here and nowhere else — that is what keeps
        # it from drifting, and it is why `undo_last_tile` / `restore_game` (which
        # rebuild the session by replaying the log) need no mirror-specific code.
        if self.rs is None:
            return
        try:
            self.rs.advance(int(action_id))
            if _RS_RECONCILE:
                self._assert_mirror(f"ply {self.turn}")
        except BaseException as exc:              # noqa: BLE001
            # BaseException for the C-a reason: `advance` is one of the two public
            # FFI entry points a Rust panic is reachable through today.
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            ply = self.turn
            (self.prev_board, self.board, self.last_action, self.turn) = snapshot
            self.action_log.pop()
            self._degrade_mid_game(
                f"rust mirror failed at ply {ply} ({type(exc).__name__}: {exc}); "
                f"the rest of this game is played by the Python engine at the "
                f"k{ANDROID_FALLBACK_BUDGET['k_dets']}x"
                f"{ANDROID_FALLBACK_BUDGET['sims_per_det']} floor")
            # `self.rs` is None now, so this re-applies on the Python path only.
            self.apply(int(action_id))

    def _claim_of(self, action_id: int) -> tuple | None:
        """``(player, MeeplePosition)`` if ``action_id`` puts a meeple down here.

        Needed because a meeple can be placed AND collected inside one engine call —
        see ``scoring_events``' ``claims``. Read-only, and best-effort: anything it
        cannot decode simply yields ``None`` and the diff falls back to its coarse
        answer rather than the move failing."""
        try:
            state = self.board.state
            if state.phase != GamePhase.MEEPLES:
                return None
            if int(action_id) == meeple_pass_index(self.board.offset.size):
                return None
            last = state.last_tile_action
            if last is None:
                return None
            act = decode(int(action_id), off=self.board.offset, phase="meeples",
                         last_tile_coord=last.coordinate)
            if not isinstance(act, MeepleAction) or getattr(act, "remove", False):
                return None
            from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition

            return (int(state.current_player),
                    MeeplePosition(meeple_type=act.meeple_type,
                                   coordinate_with_side=act.coordinate_with_side))
        except Exception:                         # noqa: BLE001
            return None

    def apply_and_collect(self, action_id: int) -> None:
        """Apply one decision (plus any forced human pass it triggers) and record
        what it paid out in ``last_events``.

        The reference to the pre-action board is taken by hand rather than reusing
        ``prev_board``: ``auto_pass_forced`` can apply further actions, each of which
        moves ``prev_board`` on, and the events must describe the whole decision.
        Keeping the reference is free — ``get_next_state`` deepcopies, so that board
        was going to be discarded anyway and is guaranteed not to be mutated."""
        before = self.board
        claim = self._claim_of(action_id)
        self.apply(action_id)
        self.auto_pass_forced()
        self.last_events = scoring_events(
            before.state, self.board.state, self.human_player, self.opponent_name,
            claims=[claim] if claim is not None else None)
        # END OF A REMOTE GAME. Told exactly once, from the one place a REAL
        # decision lands (a replayed restore goes through `apply`, not here, so a
        # restore cannot re-fire it). The server needs the final log because the
        # terminating ply is often the HUMAN's, in which case no move request
        # ever carries it — see `RemoteOpponent.finish`. Best-effort by
        # construction: this must never stop the phone writing its own archive.
        if (self.remote is not None and self.remote.finish_response is None
                and self.board.state.is_terminated()):
            self.remote.finish()

    def auto_pass_forced(self) -> int:
        """Auto-apply a forced pass on the HUMAN seat so the UI never renders a phase
        whose only legal action is 'pass'. Mirrors ``play_vs_tier1_gui._advance``.

        The AI seat is deliberately NOT auto-passed: the agent handles a forced move
        internally and must still burn one ``choose_action`` so its ``_move_idx`` (and
        therefore every per-move search seed) stays aligned with a replayed restore."""
        n = 0
        while not self.board.state.is_terminated():
            if self.board.state.current_player != self.human_player:
                break
            legal = self.legal_ids()
            if legal != [self._pass_index()]:
                break
            self.apply(legal[0])
            n += 1
        return n


_S: _Session | None = None
_GENERATION = 0


# --------------------------------------------------------------------------- #
# 6. State serialisation                                                        #
# --------------------------------------------------------------------------- #
def _tile_json(tile) -> dict:
    return {"image": getattr(tile, "image", None),
            "turns": int(getattr(tile, "turns", 0)),
            "description": getattr(tile, "description", "")}


def _board_tiles(state) -> list[dict]:
    out = []
    for coord in sorted(state.placed_coords, key=lambda c: (c.row, c.column)):
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        d = _tile_json(tile)
        d["row"], d["col"] = int(coord.row), int(coord.column)
        out.append(d)
    return out


def _placed_meeples(state) -> list[dict]:
    out = []
    for player, positions in enumerate(state.placed_meeples):
        for mp in positions:
            cws = mp.coordinate_with_side
            side = cws.side.value
            out.append({
                "player": int(player),
                "row": int(cws.coordinate.row),
                "col": int(cws.coordinate.column),
                "side": side,
                "type": mp.meeple_type.value,
                "offset_ratio": list(MEEPLE_OFFSET_RATIO.get(side, (0.5, 0.5))),
            })
    return out


def meeple_slots_for(game: Game, board: Board) -> list[dict]:
    """The meeple slots offered on ``board``'s just-placed tile, UI-shaped.

    Shared by the live legal block and by ``preview_meeple_slots`` (which runs it
    against a throwaway copy of the board), so the two can never drift apart —
    the preview dots are the same objects the real sub-phase will offer.

    Each slot carries ``feature_group``: slots with the same group claim the SAME
    on-tile feature and are therefore interchangeable (see ``feature_groups``).
    Nothing is filtered here — the champion's action space and every test see the
    full list; grouping is advice for the renderer only.
    """
    state = board.state
    last = state.last_tile_action
    if last is None:
        return []
    coord = last.coordinate
    tile = state.board[coord.row][coord.column]
    groups = feature_groups(tile)
    slots = []
    for idx in legal_meeple_indices(game, board):
        action = decode(idx, off=board.offset, phase="meeples", last_tile_coord=coord)
        assert isinstance(action, MeepleAction)
        side = action.coordinate_with_side.side
        slots.append({
            "action_id": int(idx),
            "side": side.value,
            "type": action.meeple_type.value,
            "terrain": _terrain_name(tile, side) if tile is not None else "GRASS",
            "offset_ratio": list(MEEPLE_OFFSET_RATIO.get(side.value, (0.5, 0.5))),
            "describe": format_action(idx, board),
            "feature_group": int(groups.get(side.value, -1)),
        })
    return _renumber_groups(slots)


def _renumber_groups(slots: list[dict]) -> list[dict]:
    """Make ``feature_group`` dense (0,1,2,…) over the slots actually offered, and
    give every ungrouped slot (``-1``) a private group of its own.

    Two reasons this is not just ``feature_groups``' raw numbering: the raw ids are
    per-tile and include features whose slots are not legal here (a city already
    claimed elsewhere), and a side the tile model does not describe must never be
    silently merged with another. A private group is the safe default — it renders
    as its own dot, i.e. exactly today's behaviour."""
    dense: dict = {}
    nxt = 0
    for slot in slots:
        raw = slot["feature_group"]
        # -1 (unknown) is deliberately never shared: key it by identity instead.
        key = raw if raw >= 0 else ("solo", slot["action_id"])
        if key not in dense:
            dense[key] = nxt
            nxt += 1
        slot["feature_group"] = dense[key]
    return slots


def _legal_block(s: _Session) -> dict:
    """Legal moves for whoever is on turn, shaped for the Compose UI."""
    state = s.board.state
    empty = {"tile_cells": [], "meeple_slots": [], "meeple_target": None,
             "tile_pass_id": None, "meeple_pass_id": None, "action_ids": []}
    if state.is_terminated():
        return empty
    size = s.board.offset.size
    mask = s.legal_mask()
    ids = [int(i) for i in np.flatnonzero(mask)]
    block = dict(empty)
    block["action_ids"] = ids

    if state.phase == GamePhase.TILES:
        tp = tile_pass_index(size)
        block["tile_pass_id"] = tp if tp in ids else None
        cells = []
        for (row, col) in sorted(all_legal_tile_cells(s.game, s.board)):
            rots = legal_rotations_at_cell(s.game, s.board, row, col)
            cells.append({
                "row": row, "col": col, "rotations": rots,
                "action_ids": [tile_action_index(s.board.offset, row, col, r)
                               for r in rots],
            })
        block["tile_cells"] = cells
        return block

    mp = meeple_pass_index(size)
    block["meeple_pass_id"] = mp if mp in ids else None
    last = state.last_tile_action
    if last is None:
        return block
    coord = last.coordinate
    block["meeple_target"] = {"row": int(coord.row), "col": int(coord.column)}
    block["meeple_slots"] = meeple_slots_for(s.game, s.board)
    return block


def _final_breakdown(s: _Session, final_scores: list[int]) -> list[dict] | None:
    """Split each seat's final score into (banked during play, unfinished, farms).

    Base+Farmers pays most of its points in one lump on the last tile — farms
    settle, and every still-open city/road pays a reduced rate — so the scoreboard
    jumps (11-56 to 15-106 in the round-2 playtest) with nothing on screen to
    explain it. This is that jump, itemised.

    Why it needs the PREVIOUS board rather than the terminal one: the engine runs
    the endgame pass *inside* the terminating move
    (``StateUpdater._apply_action_to`` -> ``PointsCollector.count_final_scores``),
    and that pass CONSUMES the placed meeples. By the time the bridge sees the
    terminal state there is nothing left to attribute the points to. So the last
    action is re-applied to a copy of the previous board with the final-scoring
    pass stubbed for that one call, which leaves the meeple-intact terminal state
    that ``aux_targets.extract_terminal_ownership`` documents as its input. Same
    reconstruction ``selfplay`` already uses for its ownership labels; ``engine/``
    is untouched and nothing here can reach the live session's board.

    Best-effort by construction: anything unexpected — no previous board (a save
    restored directly onto a terminal position), a reconstruction that does not
    land terminal, or a split that does not add up — returns ``None`` and the
    dialog simply omits the block. A breakdown that does not reconcile with the
    score the player can see would be worse than no breakdown at all.
    """
    if s.prev_board is None or s.last_action is None:
        return None
    try:
        import copy

        from carcassonne_ai.aux_targets import extract_terminal_ownership
        from wingedsheep.carcassonne.utils.points_collector import PointsCollector

        term = copy.deepcopy(s.prev_board)
        # A private, cache-free Game: `apply_action_inplace` mutates the board it
        # is given, and the session's Games carry a legal-moves cache that has no
        # business seeing a throwaway state.
        replay_game = Game()
        orig_cfs = PointsCollector.count_final_scores
        PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
        try:
            replay_game.apply_action_inplace(term, int(s.last_action))
        finally:
            PointsCollector.count_final_scores = orig_cfs
        if not term.state.is_terminated():
            return None

        n = len(final_scores)
        during = [int(x) for x in term.state.scores][:n]
        if len(during) != n:
            return None
        farms = [0] * n
        incomplete = [0] * n
        for r in extract_terminal_ownership(term.state):
            bucket = farms if r.terrain == "farm" else incomplete
            for w in r.winners:
                if 0 <= w < n:
                    bucket[w] += int(r.points)

        rows = []
        for p in range(n):
            if during[p] + incomplete[p] + farms[p] != int(final_scores[p]):
                return None
            rows.append({"during_play": during[p], "incomplete": incomplete[p],
                         "farms": farms[p], "total": int(final_scores[p])})
        return rows
    except Exception:
        return None


def _state_dict(s: _Session) -> dict:
    state = s.board.state
    terminated = bool(state.is_terminated())
    scores = [int(x) for x in state.scores]
    d = {
        "ok": True,
        "schema": STATE_SCHEMA,
        "generation": s.generation,
        "phase": state.phase.value,
        "turn": int(s.turn),
        "current_player": int(state.current_player),
        "human_player": int(s.human_player),
        "ai_player": int(s.ai_player),
        "is_human_turn": (not terminated
                          and int(state.current_player) == int(s.human_player)),
        "scores": scores,
        "meeples_free": [int(x) for x in state.meeples],
        "deck_remaining": int(len(state.deck)),
        "tiles_remaining": int(k_remaining(state)),
        "next_tile": _tile_json(state.next_tile) if state.next_tile is not None else None,
        "board": _board_tiles(state),
        "meeples": _placed_meeples(state),
        "legal": _legal_block(s),
        "opponent": s.opponent_kind,
        "opponent_name": s.opponent_name,
        "budget_note": s.budget_note,
        # Which implementation is picking the champion's move (P7). Always
        # present, always "python" unless a caller opted in; `backend_note`
        # carries the reason when a requested "rust" fell back.
        "backend": s.backend,
        "backend_note": s.rs_note,
        # Set only when a RESUME resolved differently from the session that played
        # the earlier half — i.e. the game changed opponents mid-way (ROUND2 F-2).
        # Null for every game played and resumed on the same resolution.
        "resume_note": s.resume_note,
        "ai_last_tile": ({"row": s.ai_last_tile[0], "col": s.ai_last_tile[1]}
                         if s.ai_last_tile is not None else None),
        "ai_last_move": s.ai_last_move,
        "is_terminated": terminated,
        "n_actions": len(s.action_log),
        # What the LAST decision paid out (see `scoring_events`). A list, because one
        # tile can close two features at once. Empty for a move that scored nothing —
        # which is most moves — and empty on a freshly restored session, whose
        # decisions were replayed rather than played.
        "events": list(s.last_events),
    }
    if terminated:
        diff = scores[0] - scores[1]
        if diff == 0:
            verdict, winner = "Tie!", None
        else:
            winner = 0 if diff > 0 else 1
            verdict = ("You win!" if winner == s.human_player
                       else f"{s.opponent_name} wins.")
        if not s.breakdown_done:
            s.breakdown = _final_breakdown(s, scores)
            s.breakdown_done = True
        d["result"] = {"scores": scores, "diff": abs(diff), "winner": winner,
                       "verdict": verdict, "budget_note": s.budget_note,
                       "breakdown": s.breakdown}
    return d


# --------------------------------------------------------------------------- #
# 7. Response plumbing                                                          #
# --------------------------------------------------------------------------- #
def _err(code: str, message: str, **extra) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message}}
    payload.update(extra)
    return json.dumps(payload)


def _ok(d: dict) -> str:
    return json.dumps(d, default=str)


def _jni_err(exc: BaseException) -> str:
    """Turn ANY failure into the JSON error envelope — the JNI boundary's one net.

    ⚠️ CATCHES ``BaseException``, DELIBERATELY (REVIEW.md C-a, CONFIRMED 2026-08-02).
    pyo3 maps a Rust panic to ``pyo3_runtime.PanicException``, whose MRO is
    ``[PanicException, BaseException, object]`` — it does NOT derive from
    ``Exception``. Every ``except Exception`` at an entry point documented as "never
    raise across JNI" was therefore blind to exactly the failure class the Rust core
    introduced, and a panic would have crossed into Kotlin as an unhandled Python
    exception. Verified against the built wheel in this checkout:
    ``carc_rs.MirrorState.from_seed('abc')`` panics, and two public FFI entry points
    reach a panic today (`advance` on an out-of-range decode, `from_seed` on a
    non-decimal seed).

    ``KeyboardInterrupt``/``SystemExit`` are re-raised: those are interpreter control
    flow, never a bridge result, and swallowing them would make a desktop test run
    uninterruptible. Nothing on the device raises either.
    """
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc
    return _err(type(exc).__name__, str(exc))


def _require_session() -> _Session:
    if _S is None:
        raise RuntimeError("no active game — call new_game() first")
    return _S


# --------------------------------------------------------------------------- #
# 8. Public API — every function takes/returns JSON strings                     #
# --------------------------------------------------------------------------- #
def new_game(config_json: str = "{}") -> str:
    """Start a game. ``config_json`` keys (all optional):

        seed          int, default 0     — deck seed AND agent seed
        human_player  0|1, default 0     — which seat the human plays
        opponent      "champion"|"tier1"|"carcasum_remote", default "champion"
        remote_url    str, required for "carcasum_remote" — e.g.
                      "http://100.109.88.103:8971", the tailnet address of the
                      laptop running scripts/carcasum_remote/server.py. ⛔ A
                      remote game archives `opponent: "carcasum_remote_<ms>ms"`
                      and is therefore EXCLUDED from the owner-vs-champion E4
                      anchor by scripts/e4_archives.py — that exclusion is the
                      whole point of the mode being a separate opponent kind
                      rather than a champion variant.
        remote_budget_ms  int, default 5000 — Carcasum's per-turn CPU budget (the
                      CALIBRATED value; changing it changes the opponent and
                      voids the session's `B` anchor)
        remote_timeout_s  float, default 180 — per-request HTTP timeout
        sims          int|null           — per-determinization sims (null = YAML budget)
        k_dets        int|null           — determinizations   (null = YAML budget)
        verify        bool, default true — champion_factory's runtime leaf proof
        start_rule    "retail"|"engine", default "retail" — start-tile convention
                      (see START_RULE; the app plays retail, the library default
                      stays "engine" so evals are unaffected)
        grid_rule     "centered18"|"engine6", default "centered18" — where the
                      start tile sits on the 35x35 grid (see GRID_RULE; the app
                      plays centered18, which removes the invisible top border,
                      and the library default stays engine6)
        draw_rule     "engine"|"redraw", default "redraw" — what happens to an
                      UNPLACEABLE tile (see DRAW_RULE; the app plays the retail
                      set-aside-and-redraw, the library default stays "engine")
        cloister_rule "drifting"|"fixed", default "fixed" — where the 3x3
                      completion scan is anchored (see CLOISTER_RULE; the app
                      plays the fix, the library default stays "drifting")
        farm_rule     "engine"|"r9", default "r9" — which farm tile data (see
                      block 1a). ⚠️ PROCESS-GLOBAL: this key can only NAME what
                      the process already latched from CARCASSONNE_FIX_R9; a
                      value that disagrees is refused, not applied.
        backend       "python"|"rust", default "python" — who picks the CHAMPION's
                      move. "rust" mirrors the game into `carc_rs.FairAgentRs`;
                      the Python engine stays authoritative for legality, UI,
                      scoring and the save record either way. Opt-in (P7).
        tiearb_level  "b64"|"b32"|"b16"|"b8"|"off", default TIEARB_LEVEL_DEFAULT
                      ("b64" since 2026-08-29; "b32" is still ACCEPTED so an older
                      save resumes at the level it was played at, but the Settings
                      menu no longer offers it) — the Settings-screen
                      tie-arbiter tier (see TIEARB_LEVELS). RUST-ONLY: on a
                      "python"-resolved backend this is fail-closed to no
                      arbiter, never an error. An unknown value is refused.

    Returns the full state object (see ``get_state``)."""
    global _S, _GENERATION, _prog_leaf_calls, _prog_expected, _prog_t0
    global _prog_thinking, _agent_ref
    try:
        cfg = json.loads(config_json) if config_json else {}
        if not isinstance(cfg, dict):
            return _err("bad_config", "config_json must be a JSON object")
        human_player = int(cfg.get("human_player", 0))
        if human_player not in (0, 1):
            return _err("bad_config", "human_player must be 0 or 1")
        _GENERATION += 1
        s = _Session(
            seed=int(cfg.get("seed", 0)),
            human_player=human_player,
            opponent=str(cfg.get("opponent", "champion")),
            sims=cfg.get("sims"),
            k_dets=cfg.get("k_dets"),
            verify=bool(cfg.get("verify", True)),
            generation=_GENERATION,
            start_rule=str(cfg.get("start_rule", START_RULE)),
            grid_rule=str(cfg.get("grid_rule", GRID_RULE)),
            draw_rule=str(cfg.get("draw_rule", DRAW_RULE)),
            cloister_rule=str(cfg.get("cloister_rule", CLOISTER_RULE)),
            # ⚠️ Defaults to what the PROCESS LATCHED, not to `FARM_RULE`. The app's
            # intent (`FARM_RULE` = "r9") is expressed by block 1a's env write, which
            # is the only place it CAN be expressed; by the time a game is started
            # the latch is the fact. A process pinned to the legacy data therefore
            # starts legacy games and stamps `farm_rule: "engine"` on them — which
            # also drops `rules_profile` off "fixed_v1", so the record still says so.
            # An EXPLICIT `farm_rule` that disagrees with the latch is still refused.
            farm_rule=str(cfg.get("farm_rule", FARM_RULE_LATCHED)),
            backend=str(cfg.get("backend", BACKEND_DEFAULT)),
            tiearb_level=str(cfg.get("tiearb_level", TIEARB_LEVEL_DEFAULT)),
            # Inert for every champion/tier1 game — see `_Session.__init__`.
            remote_url=cfg.get("remote_url"),
            remote_budget_ms=int(cfg.get("remote_budget_ms", REMOTE_DEFAULT_BUDGET_MS)),
            remote_timeout_s=float(cfg.get("remote_timeout_s", REMOTE_DEFAULT_TIMEOUT_S)),
        )
        _S = s
        _agent_ref = s.agent
        _prog_leaf_calls = 0
        _prog_expected = _expected_leaf_calls(s)
        _prog_t0 = 0.0
        _prog_thinking = False
        s.auto_pass_forced()
        return _ok(_state_dict(s))
    except BaseException as exc:                  # noqa: BLE001 — never raise
        return _jni_err(exc)                      # across JNI; see _jni_err


def get_state() -> str:
    """The full UI state object for the live game."""
    try:
        return _ok(_state_dict(_require_session()))
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def apply_action(action_id) -> str:
    """Apply a HUMAN action. Validates against the legal mask, appends to the action
    log, then auto-applies any forced pass. Returns the new state (or a JSON error)."""
    try:
        s = _require_session()
        try:
            idx = int(action_id)
        except (TypeError, ValueError):
            return _err("illegal_action", f"action_id {action_id!r} is not an int")
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("illegal_action",
                        f"action {idx} is not legal in phase "
                        f"{s.board.state.phase.value}",
                        legal_action_ids=s.legal_ids())
        describe = format_action(idx, s.board)
        s.apply_and_collect(idx)
        out = _state_dict(s)
        out["applied"] = {"action_id": idx, "describe": describe}
        return _ok(out)
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def ai_move(generation=None) -> str:
    """Run ONE AI decision (blocking; seconds at champion budget) and apply it.

    ``generation`` is the session generation Kotlin believes is current. A mismatch on
    entry is refused; a mismatch on EXIT (the user reset mid-search) discards the move
    instead of applying it to a board it was never computed for. The echoed
    ``generation`` lets the caller drop a stale result unconditionally."""
    global _prog_leaf_calls, _prog_t0, _prog_thinking, _prog_expected
    global _prog_tiearb_armed
    try:
        s = _require_session()
        gen = s.generation if generation is None else int(generation)
        if gen != s.generation:
            return _err("stale_generation",
                        f"generation {gen} != current {s.generation}",
                        generation=gen, current_generation=s.generation, stale=True)
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        if s.board.state.current_player == s.human_player:
            return _err("not_ai_turn", "it is the human's turn")

        board = s.board
        t0 = time.perf_counter()
        _prog_leaf_calls = 0
        _prog_expected = _expected_leaf_calls(s)
        _prog_t0 = t0
        _prog_thinking = True
        _prog_tiearb_armed = bool(s.tiearb.get("enabled"))
        try:
            idx = int(s.pick(board))
        finally:
            _prog_thinking = False
            _prog_t0 = 0.0
        elapsed_s = time.perf_counter() - t0

        if _S is not s or s.generation != gen:
            # Reset landed while we were thinking: the answer belongs to a board that
            # no longer exists. Drop it — never apply a move computed for another game.
            return _ok({"ok": True, "stale": True, "generation": gen,
                        "current_generation": (_S.generation if _S else None),
                        "action_id": idx})

        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("agent_illegal_action",
                        f"agent returned illegal action {idx}")
        describe = format_action(idx, s.board)
        if (s.board.state.phase == GamePhase.TILES
                and idx != tile_pass_index(s.board.offset.size)):
            act = decode(idx, off=s.board.offset, phase="tiles",
                         next_tile=s.board.state.next_tile)
            s.ai_last_tile = (int(act.coordinate.row), int(act.coordinate.column))
        s.ai_last_move = {"action_id": idx, "describe": describe,
                          "elapsed_s": round(elapsed_s, 4)}
        s.ai_elapsed.append({"ply": len(s.action_log),
                             "elapsed_s": round(elapsed_s, 4)})
        s.apply_and_collect(idx)

        out = _state_dict(s)
        out.update({"action_id": idx, "describe": describe,
                    "elapsed_s": round(elapsed_s, 4), "generation": gen,
                    "stale": False, "leaf_calls": _prog_leaf_calls})
        return _ok(out)
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def get_progress() -> str:
    """Cheap, lock-free progress poll — the ONLY function safe to call while
    ``ai_move`` is blocking. Reads module-global ints and one agent bool.

    ``phase`` gained a fourth value, ``"arbiter"``, alongside ``idle``/``search``/
    ``exact``. ⚠️ IT IS A HEURISTIC, not a live signal — see
    ``TIEARB_PROGRESS_HEURISTIC_S``'s comment for why no true one exists. It fires
    only when THIS session actually armed the tie arbiter (``_prog_tiearb_armed``,
    set from the RESOLVED ``s.tiearb`` in ``ai_move``, never the mere request) and
    the think has run long enough that an ordinary un-arbitrated move would already
    be done. ``fraction`` stays ``null`` in this phase — there is nothing to make it
    determinate with — so the UI's contract (requirement 3: determinate when
    queryable, else an indeterminate spinner with a label) is met honestly rather
    than by inventing a number."""
    try:
        t0 = _prog_t0
        thinking = bool(_prog_thinking)
        leaf_calls = int(_prog_leaf_calls)
        expected = int(_prog_expected)
        latched = bool(getattr(_agent_ref, "_latched", False))
        elapsed = (time.perf_counter() - t0) if (thinking and t0) else 0.0
        if not thinking:
            phase = "idle"
        elif latched:
            phase = "exact"     # exact-endgame solve: leaf counter does not move
        elif bool(_prog_tiearb_armed) and elapsed >= TIEARB_PROGRESS_HEURISTIC_S:
            phase = "arbiter"   # heuristic — see docstring
        else:
            phase = "search"
        frac = (min(1.0, leaf_calls / expected) if (expected > 0 and phase == "search")
                else None)
        return _ok({"ok": True, "leaf_calls": leaf_calls, "expected": expected,
                    "elapsed_s": round(elapsed, 3), "phase": phase,
                    "fraction": frac})
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def _spec_fingerprint() -> dict:
    """``{champion_id, leaf_hash}`` for the CURRENT PRODUCTION.yaml, or empty strings.

    Recorded in every save and re-checked on restore (see ``restore_game``'s
    ``save_mismatch``). The leaf hash matters for BOTH opponents, not just the
    champion: ``RuleBasedPlayer`` ranks its candidates with ``virtual_score``, so a
    leaf change moves tier-1's play too."""
    try:
        spec = champion_factory.load_production_spec()
        return {"champion_id": str(spec.champion_id),
                "leaf_hash": str(spec.yaml_leaf_hash)}
    except Exception:                             # noqa: BLE001 — never break a save
        return {"champion_id": "", "leaf_hash": ""}


def _save_payload(s: _Session) -> dict:
    """The restorable core of a save. Shared by ``save_game`` and ``archive_record``
    so an archived game is replayable by exactly the same contract as the autosave."""
    out = {
        "ok": True,
        "schema": SAVE_SCHEMA,
        "deck_seed": s.seed,
        "actions": list(s.action_log),
        "human_player": s.human_player,
        # ⛔ THE OPPONENT LABEL. "champion" | "tier1" | "carcasum_remote_<ms>ms".
        # For a remote game this is the LABELLED form (`_build_opponent`
        # normalises it), so the record names the budget that played and
        # `scripts/e4_archives.py` can keep it out of the champion anchor.
        "opponent": s.opponent_kind,
        # Where the remote opponent lived, so a RESTORE can reconnect to the same
        # live session (`game_id` is derived from (deck_seed, seat), so an app
        # restart mid-game resumes as long as the daemon is still up). None for
        # every champion/tier1 game.
        "remote_url": s.remote_url if is_remote_opponent(s.opponent_kind) else None,
        "remote_budget_ms": (s.remote_budget_ms
                             if is_remote_opponent(s.opponent_kind) else None),
        "sims": s.req_sims,
        "k_dets": s.req_k_dets,
        "verify": s.verify,
        # Load-bearing for replay: (deck_seed, actions) only reproduces the game
        # under the SAME start-tile rule. Saves written before this field existed
        # are read as START_RULE_LEGACY.
        "start_rule": s.start_rule,
        # Load-bearing for the same reason as start_rule, and for a sharper one:
        # an action index is a WINDOW cell, so the identical log decodes different
        # board cells on a differently-placed grid. Saves written before this
        # field existed are read as GRID_RULE_LEGACY.
        "grid_rule": s.grid_rule,
        # Load-bearing for the same reason again: the unplaceable-tile rule decides
        # who owes the next decision after a discard and which tiles ever enter
        # play, so the identical log decodes a different game under the other rule.
        # Saves written before this field existed are read as DRAW_RULE_LEGACY.
        "draw_rule": s.draw_rule,
        # Load-bearing for the same reason a fourth time: the cloister scan fix
        # moves the ply a cloister completes on, hence the ply its meeple comes
        # back, hence the later legal meeple set. Absent == CLOISTER_RULE_LEGACY.
        "cloister_rule": s.cloister_rule,
        # Load-bearing AND process-global (block 1a). Measured: 1/200 games
        # diverge in the legal-mask stream between the two farm rules, so this is
        # a replay input, not a footnote. Absent == FARM_RULE_LEGACY, which is
        # what every record written before 2026-08-03 was played under. Unlike
        # the four above, a mismatch here cannot be honoured by rebuilding the
        # session — `restore_game` surfaces `_Session`'s refusal.
        "farm_rule": s.farm_rule,
        # THE LABEL for the five fields above, derived from them by
        # `rules_profile_name` (never read back as authority — restore re-derives
        # it and refuses a blob whose stored label disagrees). "fixed_v1" is the
        # F9 Phase-B bundle; "walled" is the engine of record; a combination
        # `rules_profile` does not name reads "custom".
        "rules_profile": s.rules_profile,
        # The tiles that LEFT THE GAME unplaced, in removal order. NOT needed to
        # replay — the removal is deterministic given the seed and the rule — but
        # the record of which faces went away is what makes an archived game
        # auditable, and it is what `get_bag` needs to stay honest (a set-aside
        # tile is neither on the board nor in hand).
        "set_aside_tiles": [t.description for t in s.board.state.set_aside_tiles],
        # WHAT THIS GAME WAS PLAYED ON — the sticky resolution (ROUND2 F-2). `sims`
        # and `k_dets` above are what was REQUESTED (both null for the champion), so
        # before these fields existed a Resume after an app restart re-resolved the
        # backend from BACKEND_DEFAULT and re-budgeted from today's device answer —
        # and since the 2026-08-01 unpin made the budget conditional on that
        # resolution, the same saved game could continue at a different sims/move
        # than it was played at, with the archive stamping only the post-restore
        # half. `restore_game` reads these back and reproduces them.
        "backend": s.backend,
        "sims_effective": s.eff_sims,
        "k_dets_effective": s.eff_k_dets,
        # THE TIE-ARBITER LEVEL REQUESTED at session start (one of TIEARB_LEVELS —
        # "b64"/"b32"/"b16"/"b8"/"off"; the menu offers b64/b16/b8/off and "b32" is
        # retained only so a pre-2026-08-29 save resumes at its own level). Carried forward on restore so a RESUMED unfinished
        # game continues at the level it was SAVED with — the same per-game-
        # invariant contract as the five rule fields above, not the current
        # ambient Settings value (which only takes effect at the next `new_game`).
        # Absent on any save written before this feature shipped == TIEARB_LEVEL_LEGACY
        # ("off") — a pre-arbiter save resumes without the arbiter, never a guess.
        "tiearb_level": s.tiearb_level,
        # HOW MANY TIMES THE NEXT-TILE PEEK WAS SERVED (see `_Session.peek_count`).
        # Purely a record of what the HUMAN was shown; it is not a replay input and
        # nothing reads it back as authority. Carried in the save so a resumed game
        # cannot launder an earlier half's peeks out of the archive. Absent on any
        # save written before the feature shipped == 0, which is literally true of
        # every one of those games.
        "preview_next_tile_peeks": int(s.peek_count),
    }
    out.update(_spec_fingerprint())
    return out


def save_game() -> str:
    """Serialise the game to ``{deck_seed, actions, human_player, opponent, sims,
    k_dets, verify}`` — a few hundred ints. Losslessly restorable via
    ``restore_game`` (the root_replay contract).

    Also stamps the champion identity (``champion_id`` + the YAML ``leaf_hash``) so a
    save written by an older build can be RECOGNISED as such on restore. The stamp is
    advisory: ``restore_game`` warns, never refuses.

    Works at a TERMINATED state too — nothing here reads the phase — which is what
    lets ``archive_record`` build on it after the last tile lands."""
    try:
        return _ok(_save_payload(_require_session()))
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def archive_record() -> str:
    """The permanent record of a FINISHED game, for ``filesDir/games/``.

    The autosave is deleted at termination, which threw away the one artefact worth
    keeping: the ``(deck_seed, action_log)`` pair that reproduces the game exactly.
    This is that pair — the full ``save_game`` payload, restorable by the same
    ``restore_game`` contract and replayable on the desktop by ``root_replay`` — plus
    the read-only summary the Past-games list needs so it never has to replay 150
    plies just to print a score line.

    Refuses a game that is not over: an archive entry is a *result*, and a
    half-finished one would show up in the list as a game the player never lost.
    """
    try:
        s = _require_session()
        if not s.board.state.is_terminated():
            return _err("not_terminated",
                        "archive_record is only for a finished game")
        st = _state_dict(s)
        out = _save_payload(s)
        out.update({
            "schema": ARCHIVE_SCHEMA,
            "save_schema": SAVE_SCHEMA,
            "finished_at": int(time.time()),
            "opponent_name": s.opponent_name,
            "budget_note": s.budget_note,
            "sims_effective": s.eff_sims,
            "k_dets_effective": s.eff_k_dets,
            # WHICH ENGINE PLAYED (added 2026-08-01 with the rust flip). Behaviour-
            # identical by gate, so this changes no result — but the archive is a
            # permanent record and "a log records which engine played" is the same
            # rule `champion_factory` follows when it stamps `parallel_workers` and
            # `backend`. Without it, a future reader cannot tell a rust-era game from
            # a python-era one, and the two eras straddle a budget change.
            "backend": s.backend,
            "backend_note": s.rs_note,
            "rust_threads": (s.rust_threads if s.backend == BACKEND_RUST else None),
            # WHICH REMOTE OPPONENT ACTUALLY PLAYED (2026-08-30). Present only on
            # a remote game, absent on every champion/tier1 archive — so no
            # existing archive's schema changes. It carries the server's own
            # binary sha256, its `G-BINARY` gate state and the live tiny-city
            # scoring probe, which is what makes a remote game auditable against
            # `measurement/carcasum_owner_session_prep/RULES_DELTA.md` §2.1
            # without trusting a note somebody typed.
            "remote": (s.remote.manifest_block() if s.remote is not None else None),
            # THE TIE ARBITER, AS RESOLVED at game start (mandatory E4 archive
            # discipline — CLAUDE.md "manifest stamping"). `s.tiearb` is the FINAL
            # answer after every fail-closed gate (missing YAML block, unsupported
            # level, non-rust backend, and the post-construction `stats()` liveness
            # check in `_start_rust_mirror`) — never the mere request. Four fields,
            # exactly what the task calls for: enabled, B, threads, and the salt.
            # Absent on any archive written before this feature shipped, which is
            # the correct backward-compatible reading — "absent == no arbiter" is
            # also literally true of every one of those games. `tiearb_level` (the
            # Settings-screen choice) rides in `_save_payload` above; these are what
            # it actually resolved to, which is what E4 trend analysis conditions
            # on — the same "condition on the resolved epoch" contract CLAUDE.md
            # already uses for rules_profile/cloister_rule/farm_rule.
            "tiearb_enabled": bool(s.tiearb.get("enabled")),
            "tiearb_b": int(s.tiearb["B"]) if s.tiearb.get("enabled") else None,
            "tiearb_threads": (int(s.tiearb["threads"])
                               if s.tiearb.get("enabled") else None),
            "tiearb_salt": (str(s.tiearb["salt"]) if s.tiearb.get("enabled")
                            else None),
            # BOTH SIDES OF A RESUME (ROUND2 F-2). The three `*_effective`/`backend`
            # fields above describe THIS session; if the game was resumed and the
            # resolution changed under it, `played_*` is what the earlier half ran
            # and `resume_note` says so in words. Equal to the current values for a
            # game played in one sitting, and null for a save written before the
            # sticky fields existed. E4 grades off these (measurement/e4_games).
            #
            # ONE LEVEL DEEP, deliberately: a re-save carries the CURRENT session's
            # values forward, so a game resumed twice records its most recent change,
            # not a full chain. `resume_note` is the human-readable audit trail.
            "played_backend": (s.played_backend or s.backend),
            "played_sims_effective": (s.played_sims
                                      if s.played_sims is not None else s.eff_sims),
            "played_k_dets_effective": (s.played_k_dets
                                        if s.played_k_dets is not None
                                        else s.eff_k_dets),
            "resume_note": s.resume_note,
            # ⛔ THE PEEK STAMP (M3 UI build, 2026-09-02). True iff the human was
            # shown the upcoming tile at least once in this game — the "next"
            # panel that appears during the opponent's turn only. It is a pure
            # INFORMATION change (the deck is not touched, the real draw still
            # happens at the human's turn under the `draw_rule` of record, and the
            # champion never sees it), but it is still a change to what the human
            # knew, so the E4 ledger must be able to condition on it rather than
            # infer it from a build date. `preview_next_tile_peeks` is the count
            # behind the flag. ABSENT on every archive written before this build,
            # which reads correctly as "no peek".
            "preview_next_tile": bool(s.peek_count > 0),
            "preview_next_tile_peeks": int(s.peek_count),
            "result": st.get("result"),
            "scores": st["scores"],
            "n_actions": len(s.action_log),
            "tiles_placed": len(st["board"]),
            "ai_elapsed": list(s.ai_elapsed),
        })
        return _ok(out)
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def preview_meeple_slots(action_id) -> str:
    """What meeple options a PROSPECTIVE tile placement would open.

    Applies ``action_id`` to a COPY of the live board and reads the meeple slots off
    the result, so the ghost can show its consequences before the player commits.
    Same shape as ``legal.meeple_slots`` (``feature_group`` and ``offset_ratio``
    included) because it is literally the same builder.

    Read-only by construction, twice over: ``Game.get_next_state`` is documented to
    leave its input board unmodified (it is MCTS's tree-expansion path), and the copy
    is driven by a PRIVATE cache-free ``Game`` so the session's legal-moves cache
    never sees the throwaway state. Nothing here touches ``_S``.
    """
    try:
        s = _require_session()
        try:
            idx = int(action_id)
        except (TypeError, ValueError):
            return _err("illegal_action", f"action_id {action_id!r} is not an int")
        if s.board.state.is_terminated():
            return _err("game_over", "the game has ended")
        if s.board.state.phase != GamePhase.TILES:
            return _err("not_tile_phase",
                        "preview_meeple_slots takes a TILE action")
        mask = s.legal_mask()
        if not (0 <= idx < len(mask)) or not bool(mask[idx]):
            return _err("illegal_action", f"action {idx} is not legal here")
        if idx == tile_pass_index(s.board.offset.size):
            # A pass places no tile, so there is nothing to put a meeple on.
            return _ok({"ok": True, "action_id": idx, "slots": []})

        # Built with the SESSION'S rules, not the library defaults. The cloister
        # scan already rides on the board's own state (`get_init_board` stamps it
        # there), so this is belt-and-braces for that lever — but `draw_rule` and
        # the grid live on the `Game`, and a preview is not the place to discover
        # that a lever grew a `get_next_state` dependency.
        preview_game = s.rules_game(cache=False)
        next_board, _ = preview_game.get_next_state(s.board, idx)
        slots = ([] if next_board.state.phase != GamePhase.MEEPLES
                 else meeple_slots_for(preview_game, next_board))
        return _ok({"ok": True, "action_id": idx, "slots": slots,
                    "generation": s.generation})
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def _replays_rng(agent) -> bool:
    """Does this agent need its RNG rebuilt by REPLAYING decisions?

    True for a stream-random agent (``RuleBasedPlayer``: one ``_rng`` advanced by every
    tie-break, no per-move seed). False for the champion, whose search seeds are derived
    from ``_move_idx`` — re-seating that integer is exact and free, and replaying its
    decisions would cost a full search per ply."""
    return hasattr(agent, "_rng") and not hasattr(agent, "_move_idx")


def _save_mismatch(blob: dict) -> dict | None:
    """Compare the save's champion stamp with the running one; ``None`` if they agree.

    Saves written before the stamp existed carry no fields and are treated as matching
    — an absent stamp is not evidence of a difference."""
    cur = _spec_fingerprint()
    fields = {}
    for key in ("champion_id", "leaf_hash"):
        was = str(blob.get(key, "") or "")
        now = str(cur.get(key, "") or "")
        if was and now and was != now:
            fields[key] = {"saved": was, "current": now}
    if not fields:
        return None
    return {
        "fields": fields,
        "message": ("This game was saved against a different champion build; the "
                    "opponent may now play differently from here on."),
    }


def restore_game(json_str: str) -> str:
    """Rebuild a session from ``save_game``'s payload and return the state.

    Replays the action log from the seeded init board, then re-seats the agent:
    ``_move_idx`` = the number of AI *decisions* replayed (its per-move search seeds
    derive from it, ``fair_agent.det_seed_base``) and ``_latched`` = whether the
    exact-endgame latch would already have fired. Without both, a restored game would
    silently play a different champion than the one that was saved.

    An agent whose randomness lives in a *stream* rather than a per-move seed —
    ``RuleBasedPlayer._rng``, which breaks virtual-score ties — cannot be re-seated by
    an index: ``Random.choice`` consumes a data-dependent number of ``getrandbits``
    calls (rejection sampling over ``len(best_local)``, the count of TIED-best actions,
    which is unknowable without scoring the position). So its stream is rebuilt the only
    exact way there is — by replaying the decisions themselves (see ``_replays_rng``).
    Measured before this was added: 12/12 seeds diverged after a mid-game restore."""
    global _S, _GENERATION, _prog_leaf_calls, _prog_expected, _prog_t0
    global _prog_thinking, _agent_ref
    try:
        blob = json.loads(json_str) if isinstance(json_str, str) else dict(json_str)
        if not isinstance(blob, dict):
            return _err("bad_save", "save payload must be a JSON object")
        # An ARCHIVE record is a superset of a save — same `deck_seed` + `actions`
        # core, extra read-only summary fields that replay simply ignores — so a
        # finished game in `filesDir/games/` is replayable by the same call. Refusing
        # it on the schema string alone would make the archive write-only.
        schema = blob.get("schema", SAVE_SCHEMA)
        if schema not in (SAVE_SCHEMA, ARCHIVE_SCHEMA):
            return _err("bad_save", f"unknown save schema {schema!r}")
        actions = [int(a) for a in blob.get("actions", [])]
        human_player = int(blob.get("human_player", 0))
        if human_player not in (0, 1):
            return _err("bad_save", "human_player must be 0 or 1")

        # THE RESOLUTION IS STICKY PER GAME (ROUND2 F-2). A save written since
        # 2026-08-02 records the backend and the effective budget it was PLAYED at;
        # those are reproduced rather than re-resolved, so a Resume after an app
        # restart cannot silently continue the same game at a different sims/move.
        # A save with no `backend` key predates the sticky fields (all shipped E4
        # archives are in that class) and keeps the old behaviour — an ABSENT stamp
        # is not evidence about what it ran, and inventing one would be worse.
        played_backend = blob.get("backend")
        played_backend = str(played_backend) if played_backend else None
        played_sims = blob.get("sims_effective") if played_backend else None
        played_k = blob.get("k_dets_effective") if played_backend else None
        # A tier1 game has no search budget (both 0) — nothing to pin.
        if not played_sims or not played_k:
            played_sims = played_k = None

        # THE TIE-ARBITER LEVEL is carried forward the same per-game-invariant way
        # as the five rule fields below (see `_save_payload`'s comment): a resumed
        # game continues at the level it was SAVED with, not today's Settings
        # value. Absent == TIEARB_LEVEL_LEGACY ("off") — a save written before this
        # feature shipped resumes without the arbiter, matching the archive's own
        # "absent == no arbiter" contract.
        tiearb_level = str(blob.get("tiearb_level", TIEARB_LEVEL_LEGACY))

        # VOCABULARY FIRST, so an unknown value is reported as itself. Both checks
        # that follow are downstream of "these five strings mean something" — the
        # label derivation and the farm-rule gate would otherwise turn a typo'd
        # `draw_rule` into a confusing complaint about a profile or a latch.
        # `_Session` re-checks all five; this only decides which error comes out.
        for _field, _value in blob_rules(blob).items():
            if _value not in RULE_VOCABULARY[_field]:
                raise ValueError(
                    f"unknown {_field} {_value!r}; expected one of "
                    f"{tuple(RULE_VOCABULARY[_field])}")

        # THE FIVE RULE FIELDS ARE THE AUTHORITY; `rules_profile` is their LABEL.
        # A blob carrying both must have them agree — if it does not, exactly one
        # of the two is wrong about what was played, and there is no principled
        # way to pick, so refuse. (An absent label is not a disagreement: every
        # record written before 2026-08-03 has none.)
        want_profile = blob.get("rules_profile")
        got_profile = _blob_profile_name(blob)
        # `got_profile is None` means a rule field is outside its vocabulary. That
        # is a real error, but `_Session` raises a field-specific message for it a
        # few lines below — so say nothing here and let the better error win.
        if want_profile is not None and got_profile is not None:
            if got_profile != str(want_profile):
                return _err(
                    "bad_save",
                    f"save says rules_profile={str(want_profile)!r} but its rule "
                    f"fields resolve to {got_profile!r}; refusing to guess which "
                    "describes the game that was played")

        # ------------------------------------------------------------------ #
        # THE FARM RULE IS PROCESS-GLOBAL (block 1a), so a record played under  #
        # the other one cannot simply be rebuilt the way the four per-game      #
        # levers are. It is also not automatically a different game: the two    #
        # rules only diverge when a field actually runs under a city, which     #
        # measured at 1/200 random games. So rather than guess in either        #
        # direction, this REPLAYS ACROSS THE RULE AND THEN PROVES IT.           #
        #                                                                      #
        # The proof is the record's own outcome. A finished game carries the    #
        # scores it ended on; if the replay reaches termination on the same     #
        # log with the same scores, then every observable this record makes a   #
        # claim about is reproduced, and the replay is faithful TO THE RECORD.  #
        # If anything differs the restore is refused — that is the 1/200.       #
        #                                                                      #
        # An UNFINISHED save has no outcome to check against, so there is       #
        # nothing to prove with and it is refused outright. In practice that is #
        # an autosave written by a pre-2026-08-03 build, which the app replaces #
        # the moment a new game starts.                                         #
        # ------------------------------------------------------------------ #
        record_farm = str(blob.get("farm_rule", FARM_RULE_LEGACY))
        cross_rule = (record_farm in (FARM_RULE_ENGINE, FARM_RULE_R9)
                      and record_farm != FARM_RULE_LATCHED)
        record_scores = blob.get("scores")
        if cross_rule and not isinstance(record_scores, list):
            return _err(
                "rules_unavailable",
                f"this save was played with farm_rule={record_farm!r} and this "
                f"process latched {FARM_RULE_LATCHED!r} ({R9_ENV_VAR}="
                f"{os.environ.get(R9_ENV_VAR, '')!r}). The farm tile data is "
                "process-global, and an unfinished save carries no result to "
                "check a cross-rule replay against. Relaunch with "
                f"{R9_ENV_VAR}={'1' if record_farm == FARM_RULE_R9 else '0'} to "
                "replay it exactly.")

        _GENERATION += 1
        s = _Session(
            seed=int(blob.get("deck_seed", 0)),
            human_player=human_player,
            opponent=str(blob.get("opponent", "champion")),
            # A remote game resumes against the SAME daemon: `game_id` is derived
            # from (deck_seed, seat), so if the laptop session is still alive the
            # opponent picks up exactly where it left off. If it is not, the first
            # move request returns `session_lost` and the UI says so — Carcasum
            # cannot be replayed into a position (compile-time RNG, no history
            # load), so silently starting a SECOND opponent inside one game is the
            # one thing that must not happen. Absent for every non-remote save.
            remote_url=blob.get("remote_url"),
            remote_budget_ms=int(blob.get("remote_budget_ms")
                                 or REMOTE_DEFAULT_BUDGET_MS),
            sims=blob.get("sims"),
            k_dets=blob.get("k_dets"),
            verify=bool(blob.get("verify", True)),
            generation=_GENERATION,
            # Absent field == written before the retail start shipped.
            start_rule=str(blob.get("start_rule", START_RULE_LEGACY)),
            # Absent field == written before the recentring shipped, i.e. the
            # walled engine grid. Never the CURRENT default: the action log
            # decodes different cells on a different grid.
            grid_rule=str(blob.get("grid_rule", GRID_RULE_LEGACY)),
            # Absent field == written before the redraw rule shipped, i.e. the
            # engine's discard-and-pass. Never the CURRENT default by accident:
            # the log decodes a different game under the other rule.
            draw_rule=str(blob.get("draw_rule", DRAW_RULE_LEGACY)),
            # Absent field == written before the cloister scan fix shipped, i.e.
            # the drifting scan. Never the CURRENT default by accident: a cloister
            # that completes on a different ply returns its meeple on a different
            # ply, and the log decodes a different game from there on.
            cloister_rule=str(blob.get("cloister_rule", CLOISTER_RULE_LEGACY)),
            # Absent field == written before the R9 farm fix shipped, i.e. the
            # vendored farm data. Kept on the session so a re-save keeps saying
            # what the RECORD was played under; the boards are built on the
            # process's own farm data either way, which is what `cross_rule`
            # licenses and what the outcome check below proves.
            farm_rule=record_farm,
            cross_rule_replay=cross_rule,
            # ⚠️ WAS "a RUNTIME choice, not a property of the saved game" — true of
            # the ENGINE, and false of everything downstream of it since the
            # 2026-08-01 unpin coupled the budget to it. The saved answer wins; the
            # live session (undo_last_tile rebuilds through here) and then the
            # process default are the fallbacks for a save that carries none.
            backend=(played_backend
                     or (_S.backend if _S is not None else BACKEND_DEFAULT)),
            played_backend=played_backend,
            played_sims=played_sims,
            played_k_dets=played_k,
            tiearb_level=tiearb_level,
        )

        # Replay. Whose decision each logged action was is decided by the board it was
        # played on — human auto-passes are logged too but never consume an AI decision.
        exact_max_k = int(getattr(s.agent, "_exact_max_k", 2))
        exact_on = bool(getattr(s.agent, "_exact_endgame", False))
        replay_rng = _replays_rng(s.agent)
        ai_decisions = 0
        latched = False
        for a in actions:
            st = s.board.state
            if st.is_terminated():
                return _err("bad_save",
                            f"action log is longer than the game ({len(actions)} "
                            f"actions, terminated after {ai_decisions} AI decisions)")
            is_ai_turn = int(st.current_player) != s.human_player
            if is_ai_turn:
                if exact_on and not latched:
                    if st.phase == GamePhase.TILES and k_remaining(st) <= exact_max_k:
                        latched = True
                ai_decisions += 1
            mask = s.game.get_valid_moves(s.board)
            if not (0 <= a < len(mask)) or not bool(mask[a]):
                return _err("bad_save",
                            f"replay hit an illegal action {a} at ply "
                            f"{len(s.action_log)}")
            if is_ai_turn and replay_rng:
                # Burn the agent's RNG stream exactly as live play did: same board,
                # same rng state in, therefore identical consumption out. The RETURNED
                # action is discarded — the log is authoritative — but it should equal
                # `a`, and a mismatch means the save predates a strength change (the
                # `save_mismatch` warning below is the user-visible half of that).
                s.pick(s.board)
            # Cosmetic parity with live play: rebuild the AI's last-move highlight so a
            # restored state deep-compares equal to the state that was saved (only the
            # un-reconstructable wall-clock is left None).
            if is_ai_turn:
                s.ai_last_move = {"action_id": int(a),
                                  "describe": format_action(a, s.board),
                                  "elapsed_s": None}
                if (st.phase == GamePhase.TILES
                        and a != tile_pass_index(s.board.offset.size)):
                    act = decode(a, off=s.board.offset, phase="tiles",
                                 next_tile=st.next_tile)
                    if isinstance(act, TileAction):
                        s.ai_last_tile = (int(act.coordinate.row),
                                          int(act.coordinate.column))
            s.apply(a)

        # THE CROSS-RULE PROOF (see the block above `_Session`). Nothing has been
        # installed yet — `_S` is still the previous session — so a failure here
        # leaves the app exactly as it was.
        if cross_rule:
            replayed = [int(x) for x in s.board.state.scores]
            want = [int(x) for x in record_scores]
            if not s.board.state.is_terminated() or replayed != want:
                return _err(
                    "rules_unavailable",
                    f"this record was played with farm_rule={record_farm!r}, this "
                    f"process latched {FARM_RULE_LATCHED!r}, and the two decode "
                    f"this game differently (replayed scores {replayed} vs the "
                    f"record's {want}"
                    f"{'' if s.board.state.is_terminated() else '; replay did not terminate'}"
                    f"). Refusing to show it as the game that was played. Relaunch "
                    f"with {R9_ENV_VAR}="
                    f"{'1' if record_farm == FARM_RULE_R9 else '0'} to replay it "
                    "exactly.")
            s.rules_note = (
                f"replayed under farm_rule={FARM_RULE_LATCHED!r}; the record was "
                f"played under {record_farm!r}. Verified identical: same action "
                f"log, same final scores {want}.")

        if hasattr(s.agent, "_move_idx"):
            s.agent._move_idx = ai_decisions
        if hasattr(s.agent, "_latched"):
            s.agent._latched = latched
        # THE MIRROR NEEDS THE SAME TWO SEATS (2026-08-01, with the rust default).
        # The replay above reaches the position with `advance()` only, and `advance()`
        # runs neither the search nor the latch trigger — so the Rust agent's own move
        # counter is still 0 and its latch still false, exactly the case
        # `FairAgentRs.set_latched`'s docstring names. Leaving them unseated would make
        # a RESUMED game derive different per-move search seeds than the live game did
        # (and skip the endgame handoff), i.e. a silently different champion from a
        # restore — the very thing this function's `_move_idx` line exists to prevent.
        if s.rs is not None:
            s.rs.set_move_idx(ai_decisions)
            s.rs.set_latched(latched)

        # The peek record is carried across the rebuild for the same reason
        # `ai_elapsed` is (see `undo_last_tile`): no decision was removed, so the
        # earlier half's peeks still describe the game that is being resumed, and
        # dropping them would let a Resume launder the stamp out of the archive.
        # Absent field == a save written before the peek shipped == 0.
        s.peek_count = int(blob.get("preview_next_tile_peeks", 0) or 0)

        _S = s
        _agent_ref = s.agent
        _prog_leaf_calls = 0
        _prog_expected = _expected_leaf_calls(s)
        _prog_t0 = 0.0
        _prog_thinking = False
        s.auto_pass_forced()
        out = _state_dict(s)
        out["restored"] = {"actions": len(actions), "ai_decisions": ai_decisions,
                           "latched": latched, "rng_replayed": replay_rng}
        if s.rules_note is not None:
            out["restored"]["rules_note"] = s.rules_note
        # Advisory, never fatal: an old save still restores and still plays.
        mismatch = _save_mismatch(blob)
        if mismatch is not None:
            out["save_mismatch"] = mismatch
        return _ok(out)
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def undo_last_tile() -> str:
    """Take the human's just-placed tile back, returning to the tile decision point.

    Only legal in the HUMAN's meeple sub-phase — i.e. the tile is down, its meeple is
    not yet chosen, and *nothing else has happened*. That window is what makes the
    undo exact rather than approximate:

    * **No AI decision sits inside it.** ``auto_pass_forced`` only auto-passes the
      HUMAN seat, and the champion never moves between a human tile and its meeple.
      So dropping the last action removes a human decision and nothing else.
    * **The rebuild is the ordinary restore.** A game is fully determined by
      ``(deck_seed, action_log)`` (the ``root_replay`` contract), so this is literally
      ``restore_game`` on the save payload with the last action sliced off. That
      re-seats the champion's ``_move_idx`` / exact-endgame latch and replays a
      stream-random Tier-1's RNG, exactly as a Resume does — the opponent that plays
      on is bit-identical to the one that would have played had the tile never been
      placed. Nothing here needs its own determinism argument.
    * **The undone action leaves no trace.** The new session's log is the truncated
      one, so the autosave written after this call, and any archive built from it
      later, replay the game the player actually played.

    Two deliberate non-defaults on the rebuilt session:

    ``generation`` is carried over rather than bumped. The UI keys its opening
    camera fit on it, and an undo is not a new game — bumping would yank the board
    back to a whole-board fit mid-turn. Staleness is still sound: ``ai_move``'s guard
    is ``_S is not s`` *or* a generation mismatch, and the identity half catches this
    (the session object is new). Nothing can be in flight anyway — it is the human's
    turn on a single-threaded bridge.

    ``ai_elapsed`` is carried over. A restore cannot reconstruct the original
    session's wall-clock, but no AI decision was removed, so those timings all still
    describe moves that are still in the log; dropping them would silently blank the
    archive's timing record for the whole game.
    """
    try:
        s = _require_session()
        state = s.board.state
        if state.is_terminated():
            return _err("game_over", "the game has ended")
        if state.phase != GamePhase.MEEPLES:
            return _err("not_meeple_phase",
                        "undo_last_tile only applies during the meeple sub-phase")
        if int(state.current_player) != s.human_player:
            return _err("not_human_turn", "it is not the human's turn")
        if not s.action_log:
            return _err("nothing_to_undo", "no action has been played yet")

        undone = int(s.action_log[-1])
        keep_generation = s.generation
        carry_elapsed = list(s.ai_elapsed)
        payload = _save_payload(s)
        payload["actions"] = [int(a) for a in s.action_log[:-1]]

        raw = restore_game(json.dumps(payload))
        out = json.loads(raw)
        if not out.get("ok"):
            return raw                     # the rebuild failed; _S is now the rebuilt
                                           # session or the old one, either way honest
        new_s = _require_session()
        # The truncation must land exactly where the player was standing when they
        # chose the tile. Anything else means the log was not what this function
        # assumed, and silently handing back a different position would be worse
        # than refusing.
        if (new_s.board.state.phase != GamePhase.TILES
                or int(new_s.board.state.current_player) != new_s.human_player):
            return _err("undo_failed",
                        "undoing did not land on the human's tile decision")
        # `_GENERATION` (the monotonic counter) keeps the value restore_game bumped
        # it to; only the SESSION's label is rolled back, so a later new_game still
        # hands out an id nothing has seen.
        new_s.generation = keep_generation
        new_s.ai_elapsed = carry_elapsed
        out = _state_dict(new_s)
        out["undone"] = {"action_id": undone, "n_actions": len(new_s.action_log)}
        return _ok(out)
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def get_ownership() -> str:
    """Every CLAIMED feature on the board: kind, the cells it covers, and who owns it.

    Feeds the always-on ownership shading. Read-only — the UI calls it after each
    state change, never in the search hot path.

    Two levels of geometry are reported and they are NOT redundant:

    ``cells``    the tile coordinates the feature touches. Coarse; a whole-tile mark.
    ``regions``  ``[row, col, side]`` triples — the *part* of each tile the feature
                 actually occupies, which is what the overlay draws. ``side`` is the
                 engine's own ``Side`` value, so it is one of the four edges (a city
                 band or a road band, rendered as a triangle from that edge to the
                 tile centre), ``center`` (a monastery), or one of the four farmer
                 corners ``top_left``/``top_right``/``bottom_left``/``bottom_right``
                 (rendered as that quadrant).

    The tile art is a raster scan with no vector mask, so a region is an
    APPROXIMATION of the painted feature, not its outline — see the renderer's note
    in ``BoardCanvas.drawOwnership``. It is nonetheless the engine's own topology:
    every triple comes from the same ``city_positions`` / ``road_positions`` /
    ``farmer_positions`` the scoring pass walks, never from a guess about the art.

    The walk is ``aux_targets.extract_terminal_ownership``'s, with one deliberate
    difference: that function CONSUMES each feature's meeples (via
    ``MeepleUtil.remove_meeples``) to avoid double-counting, which is why it must
    deepcopy the state first. Two meeples in one city would otherwise be reported as
    two cities. Here the same job is done by keying features on
    ``(kind, frozenset(cells))`` — the engine's own BFS returns the identical cell set
    from either meeple, so the second one dedupes away. Nothing is mutated, so no copy
    is needed and the live session is untouchable by construction.

    ``owners`` is the majority rule the engine actually scores by
    (``PointsCollector.get_winning_players``): empty for nobody, one seat for a sole
    owner, and BOTH seats on a tie — which is what the UI renders as contested.
    """
    try:
        s = _require_session()
        from wingedsheep.carcassonne.objects.meeple_type import MeepleType
        from wingedsheep.carcassonne.objects.terrain_type import TerrainType
        from wingedsheep.carcassonne.utils.city_util import CityUtil
        from wingedsheep.carcassonne.utils.farm_util import FarmUtil
        from wingedsheep.carcassonne.utils.points_collector import PointsCollector
        from wingedsheep.carcassonne.utils.road_util import RoadUtil

        state = s.board.state
        n_players = len(state.placed_meeples)
        seen: dict = {}
        out: list[dict] = []

        def _cells(positions) -> list[tuple[int, int]]:
            uniq = {(int(p.coordinate.row), int(p.coordinate.column)) for p in positions}
            return sorted(uniq)

        def _side_regions(positions) -> list[tuple[int, int, str]]:
            """``CoordinateWithSide`` list -> the (row, col, side) triples it covers."""
            return sorted({
                (int(p.coordinate.row), int(p.coordinate.column), str(p.side.value))
                for p in positions
            })

        for player, positions in enumerate(state.placed_meeples):
            for mp in positions:
                cws = mp.coordinate_with_side
                coord = cws.coordinate
                tile = state.board[coord.row][coord.column]
                if tile is None:
                    continue
                kind, cells, finished, points, meeples = None, [], None, 0, None
                regions: list[tuple[int, int, str]] = []
                try:
                    if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                        farm = FarmUtil.find_farm_by_coordinate(state, position=cws)
                        kind = "farm"
                        cells = sorted({
                            (int(f.coordinate.row), int(f.coordinate.column))
                            for f in farm.farmer_connections_with_coordinate
                        })
                        # A farm occupies the CORNERS of a tile, not its edges: one
                        # tile can carry two different fields split by a road, and
                        # `farmer_positions` is exactly which corners this one holds.
                        regions = sorted({
                            (int(f.coordinate.row), int(f.coordinate.column),
                             str(side.value))
                            for f in farm.farmer_connections_with_coordinate
                            for side in f.farmer_connection.farmer_positions
                        })
                        meeples = FarmUtil.find_meeples(state, farm)
                        points = int(PointsCollector.count_farm_points(state, farm))
                    else:
                        terrain = tile.get_type(cws.side)
                        if terrain == TerrainType.CITY:
                            city = CityUtil.find_city(state, cws)
                            kind = "city"
                            cells = _cells(city.city_positions)
                            regions = _side_regions(city.city_positions)
                            finished = bool(city.finished)
                            meeples = CityUtil.find_meeples(state, city)
                            points = int(PointsCollector.count_city_points(state, city))
                        elif terrain == TerrainType.ROAD:
                            road = RoadUtil.find_road(state, cws)
                            kind = "road"
                            cells = _cells(road.road_positions)
                            regions = _side_regions(road.road_positions)
                            finished = bool(road.finished)
                            meeples = RoadUtil.find_meeples(state, road)
                            points = int(PointsCollector.count_road_points(state, road))
                        elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                            kind = "chapel"
                            cells = [(int(coord.row), int(coord.column))]
                            regions = [(int(coord.row), int(coord.column), "center")]
                            points = int(
                                PointsCollector.chapel_or_flowers_points(state, coord))
                except Exception:                 # noqa: BLE001 — one odd feature must
                    continue                      # not cost the whole overlay
                if kind is None or not cells:
                    continue
                key = (kind, frozenset(cells))
                if key in seen:
                    continue
                seen[key] = True

                if meeples is not None:
                    counts = [int(c) for c in
                              PointsCollector.get_meeple_counts_per_player(meeples)]
                else:
                    # A monastery holds exactly the one meeple that is standing on it.
                    counts = [0] * n_players
                    counts[player] = 1
                while len(counts) < n_players:
                    counts.append(0)
                owners = [int(w) for w in
                          PointsCollector.get_winning_players(counts)]
                out.append({
                    "kind": kind,
                    "cells": [[r, c] for (r, c) in cells],
                    "regions": [[r, c, side] for (r, c, side) in regions],
                    "owners": owners,
                    "meeple_count_per_player": counts,
                    "finished": finished,
                    "points": points,
                })

        return _ok({"ok": True, "generation": s.generation, "features": out})
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def _oriented_tile_key(tile) -> tuple:
    """One ORIENTATION's full functional identity, read off the engine's own data.

    Everything that decides what a tile DOES, and nothing that decides what it
    looks like:

    ``edges``   the four outer ``TerrainType`` values (``Tile.get_type``), which is
                what ``TilePositionFinder`` matches on;
    ``city``    which sides belong to one city segment (``Tile.city``) — a tile with
                two city edges plays completely differently joined vs split;
    ``road``    the road ``Connection`` pairs (``Tile.road``);
    ``farms``   each ``FarmerConnection``'s slots / tile connections / city sides,
                as a SET — the same data ``game_wrapper._farm_slot_signature``
                folds into the legal-cache key;
    ``shield``  ⛔ NEVER dropped: a pennant is +1 point per tile in that city, so a
                pennanted and an unpennanted face are different tiles;
    ``chapel``  the monastery.

    ⚠️ ``flowers`` is deliberately NOT in the key. A "garden" is decorative under
    the LOCKED SCOPE (2p Base + Farmers, no Abbots — see CLAUDE.md): nothing in the
    engine's scoring or legality reads it, so ``straight_road_flowers`` is the same
    tile as ``straight_road`` with a flowerbed drawn on it. If Abbots ever enter
    scope, ``flowers`` must be added back to this key and the bag will split again.

    ``farms`` is a SET rather than a sequence on purpose. ``Tile.turn`` permutes
    each connection's ``farmer_positions`` list, so two genuinely identical faces
    (``city_left_right`` and a 90-degree-rotated ``city_top_bottom``) differ only in
    slot ORDER — an action-emission detail, not a functional one.
    """
    from wingedsheep.carcassonne.objects.side import Side

    def sv(s):
        return getattr(s, "value", str(s))

    edges = tuple(tile.get_type(s).value
                  for s in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT))
    city = tuple(sorted(tuple(sorted(sv(x) for x in grp))
                        for grp in (tile.city or ())))
    road = tuple(sorted(tuple(sorted((sv(c.a), sv(c.b))))
                        for c in (tile.road or ())))
    farms = tuple(sorted(
        (tuple(sorted(sv(x) for x in fc.farmer_positions)),
         tuple(sorted(sv(x) for x in fc.tile_connections)),
         tuple(sorted(sv(x) for x in fc.city_sides)))
        for fc in (tile.farms or ())))
    return (edges, city, road, farms, bool(tile.shield), bool(tile.chapel))


def tile_type_key(tile) -> str:
    """A stable, ROTATION-INVARIANT id for a tile's functional type.

    The canonical form is the smallest ``_oriented_tile_key`` over the tile's own
    four rotations — rotated by ``Tile.turn``, the ENGINE's rotation, so no edge or
    farm-slot permutation is hand-written here. Hashed to 12 hex chars because the
    only consumer is a grouping key crossing the JNI boundary as JSON.

    Over the base deck this collapses the engine's 32 tile DESCRIPTIONS to the 24
    distinct types of the retail base game (the 8 collapsed pairs are exactly the
    8 ``*_flowers`` garden variants), with the counts still summing to 72 and every
    shielded face still on its own. ``tests/android/test_bridge.py`` pins that.
    """
    canon = min(_oriented_tile_key(tile.turn(n)) for n in range(4))
    return hashlib.sha256(repr(canon).encode()).hexdigest()[:12]


def get_bag() -> str:
    """What is still UNSEEN, per tile face — the bag viewer's data.

    Strictly public information, and computed so that it cannot be anything else:
    ``remaining = total_in_the_base_distribution - already_on_the_board - the tile in
    hand - the tiles SET ASIDE``. ``state.deck`` is never read. That matters — the
    deck is a shuffled LIST, so its contents in order are the future draws, and
    reading it would hand the player knowledge the fair champion's determinizations
    deliberately do not have.

    The third term is the one that is easy to miss. A tile that was drawn and could
    not be placed LEAVES THE GAME without ever reaching the board (it is appended to
    ``state.set_aside_tiles`` under BOTH draw rules — ``"engine"`` discards it and
    passes the turn, ``"redraw"`` discards it and redraws for the same player). It is
    therefore neither on the board nor in hand, and without subtracting it the face
    would be reported as still unseen forever, breaking ``total_remaining ==
    len(deck)`` for the rest of the game.

    Faces are counted by ``tile.description``, the key ``base_tile_counts`` itself is
    indexed by and the one field ``Tile.turn(n)`` preserves — so a rotated tile on the
    board still counts against the face it came from.
    """
    try:
        s = _require_session()
        from wingedsheep.carcassonne.tile_sets.base_deck import (
            base_tile_counts,
            base_tiles,
        )

        state = s.board.state
        placed: dict[str, int] = {}
        for coord in state.placed_coords:
            tile = state.board[coord.row][coord.column]
            if tile is None:
                continue
            desc = str(getattr(tile, "description", ""))
            placed[desc] = placed.get(desc, 0) + 1
        # ONLY in the tile phase. The engine does not clear `next_tile` when a tile
        # is played (`StateUpdater.play_tile`); it is replaced later, by `draw_tile`,
        # at the END of the meeple sub-phase. So for the whole meeple phase the tile
        # just placed is BOTH on the board and still "in hand", and subtracting it
        # here as well would count it gone twice — the bag read one short of the deck
        # for half of every turn. Same trap `GameState.tilesLeft` documents on the
        # Kotlin side.
        in_hand = (str(getattr(state.next_tile, "description", ""))
                   if (state.next_tile is not None
                       and state.phase == GamePhase.TILES) else None)
        # Tiles that left the game unplaced (see the docstring's third term).
        set_aside: dict[str, int] = {}
        for tile in state.set_aside_tiles:
            desc = str(getattr(tile, "description", ""))
            set_aside[desc] = set_aside.get(desc, 0) + 1

        faces = []
        total_remaining = 0
        for desc, total in sorted(base_tile_counts.items()):
            proto = base_tiles.get(desc)
            gone = (placed.get(desc, 0) + (1 if in_hand == desc else 0)
                    + set_aside.get(desc, 0))
            left = max(0, int(total) - int(gone))
            total_remaining += left
            faces.append({
                "description": desc,
                "image": getattr(proto, "image", None),
                "remaining": left,
                "total": int(total),
                # FUNCTIONAL identity (see `tile_type_key`). Faces sharing this
                # are the same tile with different art, and the bag view collapses
                # them into one entry. Additive: every pre-existing field above is
                # untouched, and a reader that ignores this key sees the old
                # per-DESCRIPTION list exactly as before.
                "type_key": (tile_type_key(proto) if proto is not None else desc),
            })

        return _ok({"ok": True, "generation": s.generation, "faces": faces,
                    "total_remaining": total_remaining,
                    "in_hand": in_hand,
                    "deck_remaining": int(len(state.deck))})
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def peek_next_tile() -> str:
    """PEEK at the tile the human is next in line to draw — never a draw.

    The M3 "let me see my next one also" feature. It reports ``state.deck[0]`` —
    the front of the deck, which is exactly what ``StateUpdater.draw_tile`` pops —
    and it does not touch the deck, the board, the action log or the agent. The
    REAL draw still happens where it always did: at the end of the opponent's
    meeple sub-phase, through the engine, under this session's ``draw_rule``.

    ## Three deliberate constraints

    **Opponent's turn only.** Refused on the human's own turn (there is nothing to
    peek at then — the tile is already in hand — and answering would hand over the
    draw *after* the one being played, which is a different and much larger
    information change). Refused at a terminated state.

    **Decision-neutral by construction.** The human has no legal action while it is
    the opponent's turn, so nothing they can do with this before their own turn
    starts differs from what they could do without it. What it DOES change is how
    early they can start planning, which is why it is stamped rather than assumed
    invisible: see ``preview_next_tile`` in ``archive_record``.

    **Provisional, and says so.** Under ``draw_rule == "redraw"`` (the ``fixed_v1``
    profile the app plays) an unplaceable draw is set aside and the player redraws.
    The opponent is still to move, so its tile can close the board against this
    face and make the real draw a different one. ``provisional`` is therefore True
    whenever the redraw rule is live; the UI labels the panel accordingly.

    ⚠️ This is the ONE bridge read that looks at ``state.deck`` — ``get_bag``
    documents at length why it must not. The difference is the point of the
    feature: the bag is public information, this is not, so it is (a) gated to the
    opponent's turn, (b) opt-in from Settings, and (c) counted into the archive.
    Nothing here reaches the champion: the agent's determinizations are built from
    its own ``ai_game``/board and never call this.
    """
    try:
        s = _require_session()
        state = s.board.state
        if state.is_terminated():
            return _err("game_over", "the game has ended")
        if int(state.current_player) == int(s.human_player):
            return _err("not_opponent_turn",
                        "the next-tile peek is only served during the "
                        "opponent's turn")
        deck = state.deck
        if not deck:
            return _ok({"ok": True, "generation": s.generation, "tile": None,
                        "provisional": False, "deck_remaining": 0,
                        "draw_rule": s.draw_rule, "peeks": int(s.peek_count)})
        s.peek_count += 1
        return _ok({
            "ok": True,
            "generation": s.generation,
            "tile": _tile_json(deck[0]),
            # True == "the opponent's move may make this unplaceable, in which case
            # the retail rule sets it aside and you draw again".
            "provisional": (s.draw_rule == DRAW_RULE_REDRAW),
            "deck_remaining": int(len(deck)),
            "draw_rule": s.draw_rule,
            "peeks": int(s.peek_count),
        })
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def get_manifest() -> str:
    """The champion's resolved runtime manifest (Settings sheet). ``null`` for Tier-1.

    With a live session this is the manifest of the agent that is ACTUALLY playing,
    budget override included. With no session — Settings opened before any game — it
    falls back to ``resolved_manifest("fair")``, the deterministic spec-derived
    manifest for the champion of record, so the sheet is never empty.
    ``manifest_source`` says which one you are looking at; never read a budget out of
    the ``spec`` variant and assume a game is running at it."""
    try:
        s = _S
        if s is None:
            return _ok({"ok": True, "manifest_source": "spec",
                        "manifest": champion_factory.resolved_manifest("fair"),
                        "production_yaml": PRODUCTION_YAML_PATH,
                        "opponent_name": "Champion (no game in progress)",
                        "budget_note": None})
        return _ok({"ok": True, "manifest_source": "session", "manifest": s.manifest,
                    "production_yaml": PRODUCTION_YAML_PATH,
                    "opponent_name": s.opponent_name,
                    "budget_note": s.budget_note})
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def production_budget() -> str:
    """The budget THIS DEVICE runs, so the UI never hardcodes a strength knob.

    ``k_dets``/``sims_per_det``/``total_sims`` are what the on-device agent actually
    searches, because those are the fields the UI prints and it must never advertise a
    budget the phone does not run. The champion of record is carried alongside under
    ``champion_of_record_*``.

    ⚠️ BACKEND-AWARE SINCE 2026-08-02 (ROUND2 F-6). It used to call ``mobile_budget()``
    directly, whose own docstring warns that "a caller that takes total_sims from here
    and ignores backend reintroduces exactly the hang the carve-out existed to
    prevent" — so on a device without ``carc_rs`` the Home and Settings screens
    advertised 11008 sims/move while every game actually started at the k4x688 floor.
    ``budget_for_backend()`` is the one function that resolves the pair, and the
    backend used here is the LIVE session's when there is one (that is the budget being
    printed alongside a running game) and otherwise the default gated on whether the
    wheel is importable in this process at all."""
    try:
        spec = champion_factory.load_production_spec()
        s = _S
        if s is not None:
            backend = s.backend
        elif BACKEND_DEFAULT == BACKEND_RUST and not rust_available():
            backend = BACKEND_PYTHON
        else:
            backend = BACKEND_DEFAULT
        prof = mobile_budget(spec)
        mob = budget_for_backend(backend, spec)
        return _ok({"ok": True, "champion_id": spec.champion_id,
                    "sims_per_det": mob["sims_per_det"], "k_dets": mob["k_dets"],
                    "total_sims": mob["total_sims"],
                    "profile": mob["profile"],
                    "profile_from_yaml": mob["from_yaml"],
                    # What the numbers above are CONDITIONAL ON — never print one
                    # without being able to answer "on which engine?".
                    "backend": backend,
                    "floored": bool(mob.get("floored")),
                    "session_backend": (None if s is None else s.backend),
                    # The unconditional YAML profile, for the debug view — NOT the
                    # headline, which is what this device can actually pay.
                    "profile_k_dets": prof["k_dets"],
                    "profile_sims_per_det": prof["sims_per_det"],
                    "champion_of_record_k_dets": spec.k_dets,
                    "champion_of_record_sims_per_det": spec.sims_per_det,
                    "champion_of_record_total_sims": spec.k_dets * spec.sims_per_det,
                    "exact_max_k": spec.exact_max_k,
                    "production_yaml": PRODUCTION_YAML_PATH})
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def runtime_info() -> str:
    """What the Python layer actually resolved to at runtime — for the About/Debug view.

    Answers the question the APK alone cannot: did the compiled Cython fast paths make
    it onto THIS device, or is the champion running the pure-Python leaf?

    Per module, three distinct facts (do not collapse them):
      ``enabled``  the env toggle (``flat_leaf.USE_CY_LEAF`` / ``board_repr.USE_CY_REPR``)
      ``loaded``   the .so genuinely imported and dlopened
      ``bound``    the lazy binding state inside the consuming module —
                   ``active`` (calls go to Cython), ``pure_python`` (import failed, a
                   False sentinel is cached and will not be retried), or ``unbound``
                   (nothing has evaluated a leaf yet, so it has not tried).

    ``bound == "unbound"`` before the first move is normal, not a fault."""
    try:
        import importlib.util

        from carcassonne_ai import board_repr, flat_leaf

        def _state(sentinel) -> str:
            if sentinel is None:
                return "unbound"
            return "active" if sentinel else "pure_python"

        cython = {
            "flat_leaf_cy": {
                "enabled": bool(flat_leaf.USE_CY_LEAF),
                "loaded": bool(CY_LOADED.get("flat_leaf_cy", False))
                or importlib.util.find_spec("carcassonne_ai.flat_leaf_cy") is not None,
                "bound": _state(flat_leaf._CY_FLAT_V2),
            },
            "flat_repr_cy": {
                "enabled": bool(board_repr.USE_CY_REPR),
                "loaded": bool(CY_LOADED.get("flat_repr_cy", False))
                or importlib.util.find_spec("carcassonne_ai.flat_repr_cy") is not None,
                "bound": _state(board_repr._CY_ENCODE),
            },
        }
        # The Rust core (P7). Shipped in the APK but INERT unless a game opts in,
        # so `available` and `active` are deliberately two different facts.
        try:
            import carc_rs

            prov = rust_build_provenance()
            rust = {"available": True,
                    # ⚠️ `carc_rs.__version__` is `carc_core::VERSION`, the workspace
                    # "0.1.0" that has never been bumped — it distinguishes nothing
                    # (REVIEW.md #9/#10). Kept under its own name because it is what
                    # the module reports; `wheel_version` and `build` are the fields
                    # that identify WHICH carc_rs this is.
                    "version": getattr(carc_rs, "__version__", None),
                    "wheel_version": prov.get("wheel_version"),
                    "build": prov,
                    "module": getattr(carc_rs, "__file__", None),
                    "tanh_flavor": ANDROID_TANH_FLAVOR,
                    "exp_fma": ANDROID_EXP_FMA}
        except ImportError as exc:
            rust = {"available": False, "error": str(exc)}
        rust["default_backend"] = BACKEND_DEFAULT
        rust["active"] = bool(_S is not None and _S.rs is not None)

        return _ok({
            "ok": True,
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy": np.__version__,
            "cython": cython,
            "rust": rust,
            "flat_leaf": bool(flat_leaf.USE_FLAT_LEAF),
            "spec": _spec_fingerprint(),
            "env": RESOLVED_ENV,
            # THE RULES THIS PROCESS CAN PLAY. Four of the five are per-game and
            # are reported as the NEW-GAME default; `farm_rule` is the latched
            # one (block 1a) and is reported as requested-vs-latched, because
            # they can differ — an environment that already carried
            # CARCASSONNE_FIX_R9 beat our `setdefault`, and a phone whose games
            # are quietly on the other farm data is exactly the thing worth
            # being able to read off a diagnostics screen.
            "rules": {
                "new_game_profile": rules_profile_name(
                    start_rule=START_RULE, grid_rule=GRID_RULE,
                    draw_rule=DRAW_RULE, cloister_rule=CLOISTER_RULE,
                    farm_rule=FARM_RULE_LATCHED),
                "start_rule": START_RULE,
                "grid_rule": GRID_RULE,
                "draw_rule": DRAW_RULE,
                "cloister_rule": CLOISTER_RULE,
                "farm_rule_requested": FARM_RULE_REQUESTED,
                "farm_rule_latched": FARM_RULE_LATCHED,
                "farm_rule_ok": FARM_RULE_REQUESTED == FARM_RULE_LATCHED,
                R9_ENV_VAR: os.environ.get(R9_ENV_VAR, ""),
            },
        })
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def debug_fast_forward(confirm: str = "", max_plies=600) -> str:
    """DEBUG ONLY — play the current game out to termination, both seats.

    Exists so a finished game can be reached in one call while testing the archive
    and the end-of-game dialog; a real Instant game is ~150 taps. Reachable only from
    the Debug console, and it additionally demands ``confirm`` be the exact token
    below so no ordinary code path can trip it.

    NOT a strength tool and never on the play path: the AI seat still uses the
    session's real agent (``s.pick``), but the HUMAN seat just takes its first legal
    action, so the resulting game is legal and replayable but the human side is
    arbitrary. The action log stays a valid ``(deck_seed, actions)`` record, so the
    archive entry it produces restores exactly like any other.
    """
    try:
        s = _require_session()
        if confirm != "yes-destroy-this-game":
            return _err("not_confirmed",
                        "debug_fast_forward needs confirm='yes-destroy-this-game'")
        limit = int(max_plies)
        plies = 0
        # This drives many decisions in one call, so "what the last move paid" has no
        # meaning afterwards; leaving the previous one would be a lie.
        s.last_events = []
        while not s.board.state.is_terminated():
            plies += 1
            if plies > limit:
                return _err("too_long", f"did not terminate within {limit} plies")
            if int(s.board.state.current_player) == s.human_player:
                legal = s.legal_ids()
                if not legal:
                    return _err("stuck", "no legal action for the human seat")
                s.apply(legal[0])
            else:
                t0 = time.perf_counter()
                idx = int(s.pick(s.board))
                s.ai_elapsed.append({"ply": len(s.action_log),
                                     "elapsed_s": round(time.perf_counter() - t0, 4)})
                s.apply(idx)
            s.auto_pass_forced()
        out = _state_dict(s)
        out["fast_forwarded"] = {"plies": plies}
        return _ok(out)
    except BaseException as exc:                  # noqa: BLE001 — see _jni_err
        return _jni_err(exc)


def reset() -> str:
    """Drop the session (bumps the generation so an in-flight ai_move is discarded)."""
    global _S, _GENERATION, _agent_ref, _prog_thinking, _prog_t0
    _GENERATION += 1
    _S = None
    _agent_ref = None
    _prog_thinking = False
    _prog_t0 = 0.0
    return _ok({"ok": True, "generation": _GENERATION})
