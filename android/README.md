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
| `buildPython` | `/usr/bin/python3.12` — must exist and its **major.minor must match** `chaquopy { defaultConfig { version = "3.12" } }` (a Chaquopy 17 hard requirement) |
| JDK | 17 (`compileOptions`/`kotlinOptions` target 17) |
| Network | first build only, to fetch Gradle/AGP/Compose/Chaquopy and the numpy + pyyaml wheels |

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

ABIs are `arm64-v8a` (phone) + `x86_64` (emulator); Chaquopy's 3.12 runtime is 64-bit
only.

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

```bash
# On the phone: Developer options -> Wireless debugging -> Pair device with pairing code
adb pair 192.168.0.NN:PPPPP        # the PAIRING port + 6-digit code (one time per phone)
adb connect 192.168.0.NN:QQQQQ     # the (different) CONNECT port shown on the main screen
adb devices                        # expect: <ip>:<port>  device

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

| Stop | `opponent` | `k_dets` | `sims` | total sims/move | est. phone s/move |
|---|---|---|---|---|---|
| Instant | `tier1` | — | — | (no search) | <0.1 |
| Fast | `champion` | 2 | 172 | 344 | ~1–2 |
| Medium | `champion` | 4 | 172 | 688 | ~2–4 |
| Strong | `champion` | 4 | 344 | 1376 | ~4–8 |
| **Champion** (default) | `champion` | *omitted* | *omitted* | from `PRODUCTION.yaml` | ~8–15 |

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

---

## 5. Desktop test commands

Nothing here needs a device:

```bash
# The bridge suite: imports without Android, plays scripted games at k1x8,
# save/restore round trip, parity vs a direct make_production_champion() call,
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

---

## 6. Layout

```
android/
  app/src/main/java/com/jishal/carcassonne/
    MainActivity.kt      state-based nav: HOME | GAME | SETTINGS | DEBUG
    HomeScreen.kt        seat, seed, difficulty chip, resume
    SettingsScreen.kt    difficulty slider, AI-manifest dialog, About
    Difficulty.kt        the 5 presets + the DataStore SettingsStore
    GameScreen.kt        HUD, overlays, thinking banner (rolling ETA), result dialog
    BoardCanvas.kt       tiles, meeple dots, ghost, gestures
    BoardGeometry.kt     board<->screen transform (unit-tested)
    GameViewModel.kt     session state machine; one op in flight; epoch guard
    PythonBridge.kt      Chaquopy call surface; one bridge thread + one poll thread
    GameModels.kt        org.json parsers for every bridge response
    SaveStore.kt         the single-slot autosave
  app/src/main/python/android_bridge.py    the ONLY hand-written Python here
  app/src/main/res/                        icon vectors, strings, theme
  tools/                sync_python.py · prepare_assets.py · smoke_selfplay.py
```

The launcher icon is a vector adaptive icon (`res/drawable/ic_launcher_{foreground,
background}.xml`): a cream meeple silhouette on a two-tone green field, drawn as path
geometry so no licensed art ends up in a launcher.
