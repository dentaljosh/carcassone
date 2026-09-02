# Carcassonne on Android — build, install, and what the knobs mean

An on-device Compose GUI that plays 2-player Base + Farmers against the **production
champion of record**, with the agent running as embedded CPython (Chaquopy). No server,
no network at play time.

> **Personal sideload only.** The bundled tile art is Hans im Glück's, reused as-is for
> personal use. This is not Play-Store-safe and must not be distributed.

Plan of record: `~/.claude/plans/i-want-am-android-quizzical-dragon.md`.
Milestones: M0 de-risk · M1 bridge · M2 board GUI · **M3 settings/polish** · M4 optional
(arm64 Cython).

---

## 1. Build

### Prerequisites

| Thing | Value used here |
|---|---|
| Android SDK | `android/local.properties` → `sdk.dir=/home/doctor/Android/Sdk` (git-ignored, machine-local — create it if the checkout is fresh) |
| `buildPython` | defaults to `/usr/bin/python3.12`; override per machine with `chaquopy.buildPython=/path/to/python3.12` in `android/local.properties`. Must exist and its **major.minor must match** `chaquopy { defaultConfig { version = "3.12" } }` (a Chaquopy 17 hard requirement). The same interpreter runs `tools/sync_python.py`. |
| JDK | 17 (`compileOptions`/`kotlinOptions` target 17) |
| Android NDK | **optional.** Highest side-by-side NDK under `$sdk.dir/ndk/` (or `ANDROID_NDK_HOME`), used to cross-compile the Cython fast paths. Install with `sdkmanager --install 'ndk;27.3.13750724'`. With no NDK the build still succeeds and the app runs the pure-Python leaf — correct, just slower. |
| Network | first build only, to fetch Gradle/AGP/Compose/Chaquopy, the numpy + pyyaml wheels, and (if the NDK is present) the `com.chaquo.python:target` Android Python headers |

```bash
cd /home/doctor/projects/carcassone/android
./gradlew assembleDebug testDebugUnitTest
# APK: app/build/outputs/apk/debug/app-debug.apk
```

`preBuild` runs `tools/sync_python.py`, which copies `src/carcassonne_ai/`,
`engine/wingedsheep/`, the three top-level script modules and
`governance/PRODUCTION.yaml` into `app/build/generated/pythonBundle/`. **There are no
checked-in copies of repo Python under `android/`** — a stale bundle is the most likely
way an on-device champion could silently differ from the measured one, so the sync
always re-runs (`outputs.upToDateWhen { false }`).

The sync ends with an **import-closure gate**: every module-scope import across the
bundle must resolve to a bundled module, the stdlib, `numpy` or `yaml` — the only things
that exist on the phone. Imports inside function bodies are exempt (that is the lazy
idiom `champion_factory`/`fair_agent` already use). It fails the build with the offending
module named, and prints a warn-list of modules that ship with no import path from
`android_bridge` at all. The torch-importing neural cluster is excluded outright via
`EXCLUDE_MODULES` in `tools/sync_python.py`: the production champion is classical, so
`heuristic_prior_mcts`'s `net is not None` branches are dead on device.

### Cython fast paths (`native/carc-cy/`)

**Chaquopy 17 cannot compile native code.** Its pip wrapper always runs
`pip install --only-binary :all: --platform android_<minSdk>_<abi>`, so a source
directory containing a C/Cython extension fails with
`error: CCompiler.compile: Chaquopy cannot compile native code`. The only supported
route is to hand pip a *finished* Android wheel.

So `preBuild` also runs `buildCyWheels` → `tools/build_cy_wheels.py`, which syncs
`src/carcassonne_ai/{flat_leaf_cy,flat_repr_cy}.pyx` into `native/carc-cy/carc_cy/`
(gitignored copies — the repo keeps one copy of each source), runs Cython, compiles each
module for `arm64-v8a` and `x86_64` with NDK clang against the Android `Python.h` /
`libpython3.12.so` from `com.chaquo.python:target`, and emits one wheel per ABI. Gradle
then feeds them to Chaquopy as `pip { options("--find-links", …); install("carc-cy==<v>") }`.

The wheel version is **content-addressed from the `.pyx` bytes**, so any source edit
changes the pip requirement string — which is what stops a stale wheel being served from
pip's cache or Chaquopy's up-to-date checks.

The extensions ship as a standalone `carc_cy` package rather than inside
`carcassonne_ai`, because on device `carcassonne_ai` arrives via Chaquopy's *source*
asset while pip requirements arrive via a *separate* asset, and a package cannot span the
two finders. `android_bridge._install_cy_aliases()` republishes them in `sys.modules`
under the `carcassonne_ai.*` names that `flat_leaf.py` / `board_repr.py` lazily import.
Call `runtime_info()` to see what a given device actually resolved.

`preBuild` also runs **`checkTileAssets`**, which fails the build if
`app/src/main/assets/tiles/base_game` does not hold all 32 tile PNGs. Those assets are
git-ignored, so without the gate a clean clone silently produces a tile-less APK. It
prints the exact command to run; it does *not* invoke Python itself (that needs Pillow in
a venv Gradle knows nothing about).

ABIs are `arm64-v8a` (phone) + `x86_64` (emulator) for **both** build types; Chaquopy's
3.12 runtime is 64-bit only. Dropping x86_64 from `release` would save ~8 MB but is not
currently possible: AGP unions `defaultConfig` and buildType `abiFilters` (never
subtracts), and inverting it — narrow default, `debug` widens — silently breaks the debug
APK, because Chaquopy resolves its wheels and `assets/chaquopy/bootstrap-native/` from
`defaultConfig` alone. Chaquopy accepts ABI overrides only per product *flavour*, and a
flavour dimension would rename every Gradle task. See the comment in `app/build.gradle.kts`.

### numpy version skew (known, tested-tolerable)

Chaquopy installs the numpy **wheel it has for Android** — currently 1.26.2 — while the
repo `.venv` runs a newer 2.x. The bridge and the engine were patched for numpy 2.x and
use only long-stable API (`flatnonzero`, boolean masks, `int64` arrays), so the two agree
on every value that reaches a decision; `tests/android/test_bridge.py` proves bridge/champion
parity on the desktop version and the on-device `verify=True` leaf fingerprint re-proves
the leaf itself on the phone. Treat a numpy bump on either side as something to re-check,
not as something guaranteed to be free.

### Regenerating the tile art

The assets are **git-ignored** (`android/app/src/main/assets/tiles/`), so a fresh
checkout must regenerate them once. Needs Pillow on the desktop Python only — it is
never imported on device.

```bash
.venv/bin/python android/tools/prepare_assets.py            # --size 416 by default
```

It reads the engine's ~104 px base-game PNGs plus the meeple sprites, forces each tile
square, Lanczos-upscales, and writes them under the relative paths the bridge reports
(`base_game/Base_Game_C2_Tile_A.png`, …).

---

## 2. Install from WSL2

USB passthrough is awkward from WSL2; **wireless adb is the practical path** (outbound
NAT works fine).

The connect port **drifts every time wireless debugging restarts**, so don't hunt for it
by hand — [`tools/adb_connect.sh`](tools/adb_connect.sh) finds it (cached port → mDNS →
bounded TCP scan of the tailnet IP) and connects:

```bash
android/tools/adb_connect.sh            # defaults to the Pixel at 100.64.4.100
android/tools/adb_connect.sh --help     # flags + the exit-code contract
```

It is idempotent (exit 0 if already connected) and, crucially, tells the two failure
modes apart: **exit 3** = no open port (phone asleep, or wireless debugging off) vs
**exit 4** = the device answered but rejected this host's client certificate, which only
the on-device pairing flow fixes. On exit 4 it prints the exact remedy. Pairing is
one-time per host and needs someone at the phone:

```bash
# On the phone: Settings -> System -> Developer options -> Wireless debugging
#               -> "Pair device with pairing code"
adb pair 100.64.4.100:PPPPP        # the PAIRING port + 6-digit code (one time per host)
android/tools/adb_connect.sh       # then this handles the drifting CONNECT port forever

adb install -r app/build/outputs/apk/debug/app-debug.apk
adb logcat -s CarcApp GameVM PythonBridge python.stdout python.stderr
```

Fallbacks if wireless debugging is unavailable: `usbipd-win` to attach the phone's USB
device into WSL, or run Windows-side `adb.exe` against the same APK path via `/mnt/c`.

---

## 3. Difficulty → `sims` / `k_dets`

Set in **Settings → Difficulty** (5-stop slider), persisted in Preferences DataStore, and
applied to the **next** game — a game in progress keeps the budget it was started with,
because that budget is part of the save file.

| Stop | `opponent` | `k_dets` | `sims` | total sims/move |
|---|---|---|---|---|
| Instant | `tier1` | — | — | (no search) |
| Fast | `champion` | 2 | 172 | 344 |
| Medium | `champion` | 4 | 172 | 688 |
| Strong | `champion` | 4 | 344 | 1376 |
| **Champion** (default) | `champion` | *omitted* | *omitted* | from `PRODUCTION.yaml` |

> ⚠️ **The per-move second estimates are gone (2026-09-02).** The column used to
> read `<0.1 / ~1–2 / ~2–4 / ~4–8 / ~8–15`, which were the 2026-07 plan's guesses
> for the **Python** search. The phone has run the Rust core since 2026-08-01 and a
> doubled mobile budget since 2026-08-25, so every one of those figures was wrong,
> and they were on screen in two places. `Difficulty.searchLabel` now prints the
> exact search SIZE (derived from `kDets`/`sims`, so it cannot drift), and the
> honest duration is the measured rolling mean the thinking banner already shows.

Two rules this table encodes, both load-bearing:

1. **Champion sends no budget keys at all.** Not `null`, not `688` — the keys are
   absent, so `android_bridge.new_game` falls through to
   `champion_factory.load_production_spec()` and the YAML remains the only place a
   strength knob lives. The app reads the numbers *back* via `production_budget()` for
   display. `DifficultyTest."champion omits the budget keys entirely"` pins this.
2. **Instant is a different agent, not a weak champion.** It is `RuleBasedPlayer`
   (Tier-1). It is labelled as such and deliberately carries **no** budget warning,
   because "BELOW CHAMPION BUDGET" would imply a weakened champion.

Fast/Medium/Strong do get the warning — the bridge stamps `budget_note` on the session
(`_Session._build_opponent`) and it is rendered in the in-game status bar, in the
end-of-game dialog, and on Home/Settings before the game starts. `exact_endgame=True`
stays on at every stop.

Source of truth for the mapping: `app/src/main/java/com/jishal/carcassonne/Difficulty.kt`.

---

## 4. Where state lives on the device

| What | Path (app-private, `filesDir`) |
|---|---|
| Autosave (single slot) | `/data/data/com.jishal.carcassonne/files/current_game.json` |
| Finished-game archive | `/data/data/com.jishal.carcassonne/files/games/<finished_at>_<seed>.json` |
| Difficulty preference | `/data/data/com.jishal.carcassonne/files/datastore/carc_settings.preferences_pb` |
| Chaquopy-extracted Python | `.../files/chaquopy/` (managed by Chaquopy; do not edit) |

The save is `{deck_seed, actions[], human_player, opponent, sims, k_dets, verify}` — a
few hundred ints, **not** a board snapshot — and `restore_game` replays it, re-seating the
agent's `_move_idx` so every per-move search seed matches the original game. It is
rewritten after every applied action, and always *before* an `ai_move` is launched, so an
abandoned search resumes from the human position that preceded it.

```bash
adb shell run-as com.jishal.carcassonne cat files/current_game.json
adb shell run-as com.jishal.carcassonne rm files/current_game.json   # forget the save
```

### The finished-game archive (`files/games/`)

The autosave is **deleted** at termination. Before that happens, `archive_record()` writes
one permanent file per finished game — which is the only thing that keeps the
`(deck_seed, action_log)` pair of a completed game from being thrown away.

An archive record is a **superset of a save**: the same restorable core, plus a read-only
summary (`result` with the end-of-game breakdown, `scores`, `opponent_name`,
`finished_at`, `tiles_placed`, `ai_elapsed` per AI decision). The summary is what the
**Home → Past games** list renders, so drawing 200 rows costs 200 file reads and *zero*
replays. Nothing is capped or rotated: a record is a few hundred ints.

Because the core is unchanged, `restore_game` accepts the archive schema directly — a
finished game can be reloaded on the phone, and replayed on the desktop by the ordinary
[`root_replay`](../scripts/measurement_infra/root_replay.py) contract (that module's
docstring is the authority on *why* `(deck_seed, actions)` is lossless for any policy).

```bash
# connect first (finds the drifting wireless-debug port); see section 2
android/tools/adb_connect.sh

# pull one game off the phone
adb shell run-as com.jishal.carcassonne ls files/games/
adb shell run-as com.jishal.carcassonne cat files/games/1785171903_25080.json > game.json

# replay it on the desktop and check it reproduces the score the phone reported
.venv/bin/python - <<'PY'
import json, sys
sys.path.insert(0, "scripts/measurement_infra")
from root_replay import RootRef

rec = json.load(open("game.json"))
ref = RootRef(rec["deck_seed"], tuple(rec["actions"]), len(rec["actions"]))
_game, board = ref.replay()
print("terminal:", board.state.is_terminated())
print("replayed:", list(board.state.scores), "archived:", rec["scores"])
PY
```

`RootRef(deck_seed, actions, ply)` also reconstructs any *intermediate* position — pass a
smaller `ply` to land mid-game and hand the board to a solver or a stronger agent to ask
what the better move was.

---

## 5. Presentation helpers (read-only bridge additions)

Five functions added for the round-3 playtest findings. **Every one of them is a pure
read**: none touches the champion's search, its action space, or `PRODUCTION.yaml`
semantics, and none is on the move-decision path.

| Bridge | Returns | Used by |
|---|---|---|
| `archive_record()` | the save payload + result/breakdown/`ai_elapsed`; refuses a live game | the finished-game archive (§4) |
| `preview_meeple_slots(action_id)` | `{slots:[…]}` for a *prospective* tile action | the faint dots on the ghost |
| `get_ownership()` | per claimed feature: `{kind, cells, owners, meeple_count_per_player, finished, points}` | the ownership overlay |
| `get_bag()` | `{faces:[{description, image, remaining, total, type_key}], total_remaining}` | the tile-bag dialog |
| `peek_next_tile()` | `{tile, provisional, deck_remaining, peeks}`; refuses the human's own turn | the "you draw next" panel |
| `debug_fast_forward(confirm)` | plays the game out; **debug console only** | reaching a finished state in tests |

Three things worth knowing about them:

- **`preview_meeple_slots` cannot mutate the session.** It drives `Game.get_next_state`
  (documented to leave its input board unmodified — it is MCTS's tree-expansion path) on a
  *private, cache-free* `Game`, so the live board and its legal-moves cache never see the
  throwaway state. It shares its slot builder with the real legal block, so the ghost's
  dots and the sub-phase's dots cannot drift apart.
- **`get_bag()` never reads `state.deck`.** The deck is a shuffled *list*, so its order is
  the future draw sequence. The counts are derived as
  `base_tile_counts − on the board − in hand`, which is strictly the public information
  the fair champion's determinizations already work from. The invariant
  `total_remaining == len(deck)` is asserted at every ply by
  `test_bag_remaining_tracks_the_deck_without_ever_reading_it`.
- **Meeple-slot grouping is advice, not filtering.** The engine offers one meeple action
  per *side*, so a city spanning two edges arrives as two actions claiming the same city.
  `feature_group` marks them equivalent and the UI draws one dot per group — but **every
  slot stays in the JSON** and the dot carries a real `action_id`. The champion and the
  tests see an unchanged action space; only the rendering collapses.

## 6. Desktop test commands

Nothing here needs a device:

```bash
# The bridge suite: imports without Android, plays scripted games at k1x8,
# save/restore round trip (including tier-1 RNG-stream determinism), the
# import-closure gate, parity vs a direct make_production_champion() call,
# and a subprocess run of the SYNCED bundle with src/ absent from sys.path.
.venv/bin/python -m pytest tests/android/ -q

# Bridge-vs-bridge full game (wiring, not strength). Keep the budget tiny.
.venv/bin/python android/tools/smoke_selfplay.py
.venv/bin/python android/tools/smoke_selfplay.py --opponent champion --sims 16 --k-dets 1

# JVM unit tests: board<->screen geometry + the difficulty mapping.
cd android && ./gradlew testDebugUnitTest
```

On-device, the **Debug console** (Home → Debug console) is the M0 harness: it runs the
bridge directly and prints per-move latency, which is how the difficulty estimates above
were sized.

**Battery A/B bench (debug builds only):** [`tools/BATTERY_BENCH.md`](tools/BATTERY_BENCH.md)
— measures joules/move across `rust_threads` arms via the debug-sourceset `BenchService`
+ `tools/battery_bench.sh`, gated on a move-hash witness that the arms did identical work.
Additive and debug-gated: release builds contain none of it, and it never touches
`files/games/` or the autosave.

---

## 7. Layout

```
android/
  app/src/main/java/com/jishal/carcassonne/
    MainActivity.kt      state-based nav: HOME | GAME | SETTINGS | DEBUG | PAST_GAMES
    HomeScreen.kt        seat, seed, difficulty chip, resume, past-games entry
    SettingsScreen.kt    difficulty slider, AI-manifest dialog, About
    Difficulty.kt        the 5 presets + the DataStore SettingsStore
    GameScreen.kt        HUD (fit/overlay/bag), banners, bag dialog, result dialog
    PastGamesScreen.kt   the archive list + per-game summary (no replay)
    BoardCanvas.kt       tiles, meeple dots, ghost + preview, ownership tint, gestures
    BoardGeometry.kt     board<->screen transform (unit-tested)
    GameViewModel.kt     session state machine; one op in flight; epoch guard
    PythonBridge.kt      Chaquopy call surface; one bridge thread + one poll thread
    GameModels.kt        org.json parsers for every bridge response + the bag grouping
    SaveStore.kt         the single-slot autosave
    ArchiveStore.kt      files/games/ — one file per finished game
    ThinkingService.kt   foreground service held for the opponent's turn (§8)
  app/src/main/python/android_bridge.py    the ONLY hand-written Python here
  app/src/main/res/                        icon vectors, strings, theme
  app/src/debug/        BenchService.kt + carc_bench.py — the battery A/B bench
                        (debug-only; see tools/BATTERY_BENCH.md)
  tools/                sync_python.py · prepare_assets.py · smoke_selfplay.py
                        battery_bench.sh · battery_bench_lib.py · BATTERY_BENCH.md
```

The launcher icon is a vector adaptive icon (`res/drawable/ic_launcher_{foreground,
background}.xml`): a cream meeple silhouette on a two-tone green field, drawn as path
geometry so no licensed art ends up in a launcher.

---

## 8. What is on screen during the opponent's turn (2026-09-02, `0.1-m3-ui`)

Three things the app can do while it is not your move. **None of them is a strength
change**: the champion, its budget, the rules profile and the tie-arbiter config are
untouched by this build, and `Difficulty.newGameConfig` still emits the
byte-identical champion JSON (`OpponentModeTest` pins it literally).

### The opponent's tile — always on

A drawn tile is face-up from the moment it is drawn. That is the retail rule, and it
is information the fair champion's own determinizations already work from; the app
simply had nowhere to show it, because the HUD thumbnail is gated on *your* tile
phase. `GameScreen.OpponentTurnTiles` shows it for the whole of the opponent's turn.

### Your next tile — opt-out, and **stamped**

`peek_next_tile()` reports the front of the deck — the tile
`StateUpdater.draw_tile` would pop — during the **opponent's turn only**. It is a
peek, never an early draw: nothing is consumed, and the real draw still happens on
your turn through the engine under this game's `draw_rule`. Under the retail redraw
rule the opponent's move can leave nowhere to put it, in which case a different tile
arrives — the panel is captioned "may change" rather than quietly being wrong.

It is decision-neutral by construction (you have no legal action while the opponent
is deciding), so it defaults **on** — but it changes what you *knew*, so it is
recorded rather than inferred from a build date:

| archive field | meaning |
|---|---|
| `preview_next_tile` | `true` iff the peek was served at least once in this game |
| `preview_next_tile_peeks` | how many times |

The count is carried through `save_game`/`restore_game`, so a Resume cannot launder
an earlier half's peeks out of the record. Both fields are **absent** on every
archive written before this build, which reads correctly as "no peek".
`measurement/e4_games` analysis must condition on `preview_next_tile` exactly as it
already conditions on `rules_profile` and the budget epoch.

⚠️ `peek_next_tile` is the **only** bridge read that touches `state.deck` — `get_bag`
documents at length why it must not. That is the point of the feature, which is why
it is gated to the opponent's turn, opt-out in Settings, and counted.

### Thinking in the background — opt-out

`ThinkingService` is a `dataSync` foreground service (plus a partial wakelock) held
for the whole opponent leg — both decisions of a champion turn, and the open HTTP
request of a remote one. It exists so backgrounding the app does not move the process
out of the **top-app cpuset**, which is what makes a move take many times longer on
the little cores.

It is a scheduling aid, never the correctness story: the autosave is written *before*
every `ai_move`, so a process killed mid-search resumes from the human position that
preceded it and the opponent thinks again — deterministically for the champion
(`_move_idx` is re-seated by the replay) and idempotently for the remote server
(an identical `(deck_seed, actions)` request is answered from its committed log, never
searched twice). Manifest cost: `WAKE_LOCK`, `FOREGROUND_SERVICE`,
`FOREGROUND_SERVICE_DATA_SYNC`, `POST_NOTIFICATIONS`. A denied `POST_NOTIFICATIONS`
hides the notification but does not stop the service.

**Manual check (cannot be unit-tested):** start a Champion game, make a move, and
while the banner says the opponent is thinking press Home. The notification should
read "*Champion* thinking…" (or "*Carcasum* thinking…"). Return to the app: the move
should already have landed, or land in about the time it would have on screen. With
the setting off, the same move typically takes noticeably longer.

### The tile bag groups by what a tile DOES

`get_bag()` stamps each face with `type_key` — `tile_type_key`, which canonicalises
the engine's own tile data (outer edges, city segments, road connections, farm slots,
pennant, cloister) over the four `Tile.turn` rotations. `groupBagFaces` collapses on
it, so the engine's 32 art files read as the base game's **24 actual tiles**, counts
still summing to 72. The eight collapsed pairs are exactly the `*_flowers` garden
variants — decoration under the locked no-Abbots scope.

⛔ **A pennant is never merged away**: `shield` is in the key, because a pennanted
city tile scores differently. If Abbots ever enter scope, `flowers` must go back into
the key too. Tapping an entry rotates it 90° clockwise, which is view state only —
it lives in the dialog and reaches no save. Pinned by
`tests/android/test_bridge_m3_ui.py` (the engine half) and `BagGroupingTest` (the
phone half).

### The asset loader fails loud

`TileAssets.load` used to enumerate `assets/tiles/base_game/` and accept whatever was
there; a build that copied only that directory shipped with **every meeple sprite
missing** and nothing failed until the APK was on the phone. It now checks a named
manifest — 24 lettered faces + 8 garden variants + 6 meeples + `Empty.png` = **39** —
and throws with the missing filenames and the regeneration command. `TileAssetsTest`
pins the manifest; `unzip -l app-debug.apk | grep -c assets/tiles/` must print 39.
