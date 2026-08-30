# SETUP — getting the owner in front of Carcasum's GUI, at the T-TRANSFER-matched config

> **Status: PREP, 2026-08-30. Nothing has been built and no game has been played.**
> Everything below marked ✅ VERIFIED was checked on disk or read out of the vendored
> source this sitting. Everything marked ⏳ UNEXECUTED is a recipe that has **not been
> run**, because the local box was under an exclusive-tenancy timing bench
> (`eval_fair_puct … --workers 30`, loadavg 17.9 at 32 cores) for the whole of this
> agent's window and a compiler is exactly the niced DRAM-churner that voids one
> (auto-memory `feedback_no_agent_compute_beside_eval`). **Run the build on a quiet box.**
>
> Companions: [`PROTOCOL.md`](PROTOCOL.md) (the one-pager the owner follows) ·
> [`RULES_DELTA.md`](RULES_DELTA.md) (what differs from his phone games) ·
> [`build_gui.sh`](build_gui.sh) (the unexecuted build recipe, as a script).

---

## 0. What this is, in one paragraph

Carcasum is not a Java program — **it is C++11 / Qt 5**, from Yannick Müller's 2014
master's thesis, vendored at `5f5e365` under AGPL-3.0
([`vendor/README.md`](../../vendor/README.md)). Only the *tile definitions* are
JCloisterZone's (Java) heritage. It ships **three console targets** (`core`,
`tournament`, and our added `driver`) **and a real Qt Widgets GUI** — `carcasum_gui`,
with a human player, a graphical board, a player-configuration dialog, and a move-history
autosave. The engine-vs-engine work used the `driver`; the owner session uses the
**GUI**, which has never been built in this program.

---

## 1. ✅ VERIFIED — the GUI can be configured to the *exact* T-TRANSFER opponent

This was the biggest open risk and it resolves cleanly. `PlayerSelector::createPlayer()`
([`vendor/carcasum/Carcasum/gui/playerselector.cpp:296`](../../vendor/carcasum/Carcasum/gui/playerselector.cpp))
constructs, for the MCTS/Portion/Random selection:

```cpp
return new MCTSPlayer<Utilities::PortionUtility, Playouts::RandomPlayout>(
            tileFactory, /*reuseTree=*/false, limit, useTimeout, Cp);
```

and the remaining constructor parameters default to
`nodePriors=false, progressiveWidening=false, progressiveBias=false`
([`player/mctsplayer.h:216`](../../vendor/carcasum/Carcasum/player/mctsplayer.h)).

Our driver builds the opponent from JSON at
[`driver/main.cpp:456`](../../vendor/carcasum/Carcasum/driver/main.cpp) — **the same
template instantiation, the same five knobs.** So the GUI selection below is not
"similar to" the measured opponent; it is the same object.

| T-TRANSFER `opponent` manifest field | GUI control | default? |
|---|---|---|
| `kind: "mcts"` | Player type list → **MCTS** (last row) | ❌ pick it — the list does not default here |
| `utility: "portion"` | Utility Function → **Portion** | ✅ index 0, already default |
| `playout: "random"` | Playout Policy → **Random** | ✅ index 0, already default |
| `budget_ms: 5000` | **Time Limit** radio + "Limit per ply" = **5000** | ✅ both already default |
| `playouts: null` | i.e. *not* "Fixed Playout Count" | ✅ default |
| `cp: 0.5` | **Cp** spin box = **0.5000** | ✅ already default |
| `reuse_tree: false` | hardcoded `false` in the GUI | ✅ not exposed, cannot be wrong |
| `node_priors / progressive_widening / progressive_bias: false` | constructor defaults | ✅ not exposed, cannot be wrong |

**So the only thing the owner must change in that dialog is picking `MCTS` from the
player-type list.** Everything else is right out of the box. Source of the manifest
being matched: [`../carcasum_arb_challenge_20260824/READOUT.md`](../carcasum_arb_challenge_20260824/READOUT.md)
§2 `G-BUDGET`.

---

## 2. ✅ VERIFIED — where to run it, and why the box choice is load-bearing

**Recommendation: play on the LAPTOP (`ssh laptop-wsl`), not the desktop.**

Three facts force this:

1. **The anchor was measured on the laptop.** Both the gate-6 timing smoke
   ([`../carcasum_smoke_20260823/SMOKE_READOUT.md`](../carcasum_smoke_20260823/SMOKE_READOUT.md))
   and the T-TRANSFER cell
   ([`../carcasum_arb_challenge_20260824/READOUT.md`](../carcasum_arb_challenge_20260824/READOUT.md) §8)
   ran there.
2. **Carcasum's budget is thread CPU-time, not wall time** (`USE_BOOST_THREAD_TIMER 1`,
   [`Carcasum/static.h:65`](../../vendor/carcasum/Carcasum/static.h)). That is good news
   for contention — a descheduled Carcasum still gets its full 5 CPU-seconds, so **load
   cannot quietly weaken it**. But it makes the opponent's *search size* a function of
   **single-core speed**: 5 CPU-seconds on a 5900XT buys more playouts than 5 CPU-seconds
   on the laptop. A different box is a *different-strength opponent*.
3. The laptop already carries the exact anchor artefacts — ✅ verified this sitting:
   `/home/doctor/opt/carcasum-toolchain` present, `vendor/carcasum/build-driver/carcasum_driver`
   present and `sha256 = c090847e1befa007e9b3b3031a9c880a60915e36f143aa6c3c30691599792968`,
   **byte-identical to the binary named in the T-TRANSFER provenance table.**

The reference throughput the owner's opponent should be reproducing (laptop, 5000 ms,
n=142 turns): **median 46,332 playouts/turn**, opening plies 0–9 **27,915**, 35–36
opponent turns/game ([`SMOKE_READOUT.md`](../carcasum_smoke_20260823/SMOKE_READOUT.md) §1–2).
Quote the **median**; the mean (163,786) is a skew artefact of near-free endgame rollouts.

**If the desktop is used instead**, say so in the log and carry this caveat: the opponent
is *stronger* than the anchor by an unmeasured amount, which pushes the owner's observed
margin **down**, which looks like *more adaptation*. That is the direction that would
manufacture the headline result, so it is the wrong box to be casual about.

⏳ Optional de-risk (not required, ~15 min on a quiet box): run
`scripts/carcasum_match/match.py` for 2 games on the play box and compare its realized
`opp_driver_playouts_per_turn` **median** against 46,332.

## 2b. ✅ VERIFIED — a headed Qt app can run from WSL on both boxes

WSLg is live on both. Local box: `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0`,
`/tmp/.X11-unix/X0` socket present, `/mnt/wslg` populated. Laptop (`laptop-wsl`):
`/tmp/.X11-unix/X0` present, `/mnt/wslg` populated. So **no Windows-side fallback is
needed** — the answer to "can a human play it from WSL" is yes, subject only to the
build.

If the xcb platform plugin misbehaves, force it explicitly:
`QT_QPA_PLATFORM=xcb DISPLAY=:0 ./carcasum_gui`.

---

## 3. ⛔ DO NOT use the upstream Windows binary

Upstream's README offers `Carcasum-win32.zip` ("Binary Download (Windows only)"). **That
build is unpatched** and therefore plays a *different game* from both our champion and
our measured Carcasum: it keeps the **original-2000 tiny-city exception** — a completed
two-tile city scores **2, not 4**
([`CARCASUM_PATCHES.md`](../../vendor/carcasum/CARCASUM_PATCHES.md) R1). A session played
against it is a rules result wearing a strength result's costume, and is unreadable
against the anchor. Build from the vendored tree or do not play.

---

## 4. ⏳ UNEXECUTED — the build recipe

### 4.1 What the GUI needs that the driver build did not

Read out of [`Carcasum/Carcasum.pro`](../../vendor/carcasum/Carcasum/Carcasum.pro) (the
`else {}` branch is the GUI target) and the top-level
[`Carcasum.pro`](../../vendor/carcasum/Carcasum.pro):

* `QT += gui svg widgets network` — so **QtSvg** (`#include <QtSvg/QSvgRenderer>` in
  `gui/tileimagefactory.cpp`), QtWidgets and QtNetwork on top of the driver's core+gui.
* **quazip**, built from the vendored `vendor/carcasum/quazip/` as a sibling subdir
  target (`SUBDIRS += quazip; Carcasum.depends = quazip`). Needs zlib — ✅ `zlib1g-dev`
  is already installed system-wide on the local box.
* The `.ui` forms and `.qrc` resources, which `uic`/`rcc` from `qtbase5-dev-tools`
  already in the prefix will handle.

✅ Availability checked in the noble archive: `libqt5svg5-dev` 5.15.13-1,
`libqt5svg5` 5.15.13-1, `libqt5widgets5t64`, `libqt5network5t64` — all present, so the
same rootless `apt-get download` + `dpkg-deb -x` trick that
[`bootstrap_toolchain.sh`](../../scripts/carcasum_match/bootstrap_toolchain.sh) uses
extends to them.

### 4.2 ⭐ The simple path — the owner has sudo, the agent did not

The whole rootless-prefix apparatus exists for one reason: `sudo` needs a password that
an unattended agent does not have (`bootstrap_toolchain.sh` header). **That is not a
constraint on Joshua.** On the play box:

```bash
sudo apt-get install -y qtbase5-dev qtbase5-dev-tools qt5-qmake \
                        libqt5svg5-dev libboost-system-dev libboost-chrono-dev zlib1g-dev
mkdir -p /home/doctor/projects/carcassone/vendor/carcasum/build-gui
cd       /home/doctor/projects/carcassone/vendor/carcasum/build-gui
qmake ../Carcasum.pro          # top-level: builds quazip, then carcasum_gui
make -j8
./Carcasum/carcasum_gui
```

`apt-get install` also pulls the xcb platform plugin and its client libs transitively,
which is the one part of the rootless prefix that is fiddly. **Prefer this path.**

### 4.3 The rootless path, if sudo is unwanted

[`build_gui.sh`](build_gui.sh) in this directory does it end to end: it re-runs the
existing bootstrap, adds the four GUI packages to the prefix, then out-of-tree qmakes and
makes the top-level project with the same
`INCLUDEPATH` / `QMAKE_LIBDIR` / `QMAKE_RPATHDIR` / `-Wl,--disable-new-dtags`
overrides the driver build needed (the `--disable-new-dtags` flag is **not** optional —
see the bootstrap script's closing note on DT_RUNPATH vs DT_RPATH and transitive deps).

⏳ **It has not been run.** Its known residual risk is exactly the one `apt-get install`
removes: the Qt **xcb platform plugin** and its `libxcb-*` client libraries are not in
the current prefix and are not in `QT_PACKAGES`. If `carcasum_gui` dies with
*"could not load the Qt platform plugin xcb"*, that is this gap — fall back to §4.2.

---

## 5. ✅ VERIFIED — first-run behaviour and the artwork question

On first start the GUI looks for `JCloisterZone-2.6.zip` beside the binary and, if
missing, offers to download it from `http://jcloisterzone.com/builds/JCloisterZone-2.6.zip`
([`gui/main.cpp:59-80`](../../vendor/carcasum/Carcasum/gui/main.cpp)).

**Answer "No".** That URL is 2014-era and the file is optional — its own dialog says it is
"needed for better looking tiles". `TileImageFactory::loadImage` tries the zip first and
then falls back to `:/tiles/BA/<id>` from the compiled-in
[`gui/tilesJczf.qrc`](../../vendor/carcasum/Carcasum/gui/tilesJczf.qrc), whose PNGs **are**
vendored (`gui/img/jczf/BA/`, ✅ present). Meeple-position data comes from the vendored
`:/jcz/defaults/points.xml` and `:/jcz/resources/plugins/classic/tiles/points.xml`.
**The GUI is fully playable offline.**

⚠️ Do **not** try `CONFIG+=classicTiles`: it swaps in
[`jcz/jczTilesClassic.qrc`](../../vendor/carcasum/Carcasum/jcz/jczTilesClassic.qrc), which
references `jcz/resources/plugins/classic/tiles/BA/*.jpg` — ✅ verified **absent** from
the vendored tree (only 4 XML files are there). `rcc` will fail.

---

## 6. ✅ VERIFIED — how to start a matched human-vs-AI game

1. **Game ▸ Random Tiles** must be ticked. The Game menu also offers **Choose Tiles**,
   which lets the human pick which tile is drawn. That is a cheat switch; leave it off.
2. **File/Game ▸ New Game** → the New Game page. It is a per-seat table (`#`, Color,
   Type, Name). Configure **exactly two** seats; leave the rest as type `—`.
   * One seat → type **"Human"** (`MainWindow` itself is the `Player`;
     `game->addPlayer(this)`).
   * The other seat → the type entry that opens **PlayerSelector**; configure as §1 and
     accept. The dialog's chosen name appears in the seat's type box.
3. **Alternate who is seat 0 between games** (see [`PROTOCOL.md`](PROTOCOL.md)) — the
   engine-side anchor is seat-balanced (200 decks × 2 seats), so the human side should be
   too.
4. **Help ▸ Controls** opens the how-to-place dialog; it auto-opens on very first start.
5. `Tile::BaseGame` is hardcoded at `game->newGame(...)` — base game only, no expansion
   selector to get wrong. `MEEPLE_COUNT 7` (`static.h:32`), as retail.
6. There is **no human clock**. Carcasum thinks 5 CPU-seconds per turn, ~35–36 turns per
   game ⇒ **≈3 minutes of AI thinking per game**; the rest of the wall is the owner's own.

---

## 7. ✅ VERIFIED — Carcasum DOES produce a machine-readable game archive

This is better than the brief assumed. `MainWindow` autosaves the **complete move
history** after *every* move (and after every undo) via
`game->storeToFile(...)` ([`gui/mainwindow.cpp:237-254`](../../vendor/carcasum/Carcasum/gui/mainwindow.cpp)):

```
$XDG_DATA_HOME/YMSolutions/Carcasum/games/<gameStartTimestamp>
   i.e. ~/.local/share/YMSolutions/Carcasum/games/<epoch-seconds>
```

(`APP_ORGANIZATION "YMSolutions"`, `APP_NAME "Carcasum"`, `static.h:25-26`; Qt5
`QStandardPaths::DataLocation`.) The GUI also prints the resolved path to stderr at
startup (`qDebug() << "QStandardPaths::DataLocation:"`), so the owner can confirm it
rather than trust this doc. **File ▸ Store board… (Ctrl+S)** writes the same structure
anywhere by hand.

The file is a `std::vector<MoveHistoryEntry>` — tile id, x, y, orientation, meeple node
index per ply — the same format `Game::loadFromFile` and `HistoryProvider` consume, i.e.
**losslessly replayable inside Carcasum**.

⚠️ **Honest limit: an importer into our harness does not exist.** The pieces are all
present ([`scripts/carcasum_match/match.py`](../../scripts/carcasum_match/match.py)
already owns the tile-id mapping, the rotation-period reduction, and the 145×145/offset-72
coordinate inversion), but nobody has written the file→our-actions adapter. So:

* **Guaranteed today:** final scores per game, plus a lossless per-ply archive on disk
  that can be replayed *in Carcasum* and rendered (`File ▸ Render to file`).
* **Needs an adapter first:** anything our judges do — EV-loss grading, per-ply
  continuation pricing, the agreement gradient. Do not promise those off this session
  until the adapter is written and gated.

So the capture plan in [`PROTOCOL.md`](PROTOCOL.md) is: the tally CSV is what the read
depends on; the autosave directory is the option value we bank for free.

---

## 8. Summary — works end-to-end vs needs the owner

| item | state |
|---|---|
| Carcasum has a human-playable GUI | ✅ verified in source |
| GUI can express the exact T-TRANSFER opponent | ✅ verified — one dropdown, rest are defaults |
| WSL can display it (both boxes) | ✅ verified — WSLg sockets live |
| Anchor binary + toolchain on the laptop | ✅ verified — sha256 matches T-TRANSFER provenance |
| Offline artwork, no network needed | ✅ verified — vendored PNGs, answer "No" to the download |
| Machine-readable per-game archive | ✅ verified — autosave, lossless move history |
| **`carcasum_gui` compiled** | ⏳ **NOT DONE** — box was under an exclusive timing bench |
| **A human game actually played through** | ⏳ **NOT DONE** — no build to play |
| Qt xcb platform plugin in the rootless prefix | ⏳ unresolved; `sudo apt-get install` (§4.2) removes the question |
| Carcasum-archive → our-harness importer | ❌ does not exist; out of scope here |
