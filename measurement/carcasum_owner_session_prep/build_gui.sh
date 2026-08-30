#!/usr/bin/env bash
#
# build_gui.sh — build Carcasum's human-playable Qt GUI (`carcasum_gui`) for the
# owner session, WITHOUT sudo, reusing the rootless prefix that
# scripts/carcasum_match/bootstrap_toolchain.sh already creates for the driver.
#
# ⏳ STATUS 2026-08-30: THIS SCRIPT HAS NEVER BEEN RUN. It is a recipe assembled by
#    reading vendor/carcasum/Carcasum/Carcasum.pro, vendor/carcasum/Carcasum.pro and
#    bootstrap_toolchain.sh, plus an apt-cache availability check on all four added
#    packages. The build could not be executed because the local box was under an
#    exclusive-tenancy timing bench for the whole window (see SETUP.md banner).
#
# ⭐ PREFER `sudo apt-get install` IF YOU HAVE THE PASSWORD — see SETUP.md §4.2.
#    The rootless dance exists because an unattended agent has no sudo password, not
#    because it is better. Its one known residual gap is the Qt **xcb platform
#    plugin** and its libxcb-* client libs, which are not in the prefix and which
#    apt-get install would pull in transitively. If the built binary dies with
#    "could not load the Qt platform plugin \"xcb\"", that is this gap — use §4.2.
#
# ⚠️ DO NOT RUN THIS WHILE A TIMING BENCH OR EVAL IS LIVE ON THE BOX.
#    Census first (`ps -eo args | grep -E 'eval_fair_puct|match\.py'`), and remember a
#    compiler is exactly the niced DRAM-churner that voided a saturated eval once
#    (auto-memory feedback_no_agent_compute_beside_eval).
#
# Usage:
#   measurement/carcasum_owner_session_prep/build_gui.sh
#
set -euo pipefail

REPO="${REPO:-/home/doctor/projects/carcassone}"
TOOLCHAIN_PREFIX="${TOOLCHAIN_PREFIX:-/home/doctor/opt/carcasum-toolchain}"
DEB_CACHE="${DEB_CACHE:-/home/doctor/opt/carcasum-toolchain-cache}"
JOBS="${JOBS:-8}"

LIBDIR="$TOOLCHAIN_PREFIX/usr/lib/x86_64-linux-gnu"
QMAKE_BIN="$TOOLCHAIN_PREFIX/usr/lib/qt5/bin/qmake"
BUILD_DIR="$REPO/vendor/carcasum/build-gui"     # gitignored via vendor/carcasum/build-*/

# --------------------------------------------------------------------------- #
# 1. The driver's toolchain, unchanged. Idempotent; safe to re-run.
# --------------------------------------------------------------------------- #
echo "== Step 1: base toolchain (bootstrap_toolchain.sh) =="
"$REPO/scripts/carcasum_match/bootstrap_toolchain.sh"

# --------------------------------------------------------------------------- #
# 2. The GUI-only additions.
#
#    Read out of Carcasum/Carcasum.pro's GUI branch:  QT += gui svg  and
#    greaterThan(QT_MAJOR_VERSION,4): QT += widgets network
#
#    qtbase5-dev (already in the base bootstrap) supplies the Widgets/Network
#    *headers*; what the base list is missing is (a) QtSvg entirely and (b) the
#    Widgets/Network *runtime* libs, since the driver only ever needed Core+Gui.
#
#    quazip is NOT a package: it is vendored at vendor/carcasum/quazip and built
#    as a sibling SUBDIRS target by the top-level .pro. It needs zlib headers,
#    which are already installed system-wide (zlib1g-dev).
# --------------------------------------------------------------------------- #
GUI_PACKAGES=(
    libqt5svg5-dev          # QT += svg  ->  #include <QtSvg/QSvgRenderer>
    libqt5svg5              #   its runtime lib
    libqt5widgets5t64       # QT += widgets  (runtime; headers come from qtbase5-dev)
    libqt5network5t64       # QT += network  (gui/downloader.cpp)
)

echo "== Step 2: downloading GUI .debs into $DEB_CACHE =="
mkdir -p "$DEB_CACHE"
for pkg in "${GUI_PACKAGES[@]}"; do
    if compgen -G "$DEB_CACHE/${pkg}_*.deb" > /dev/null; then
        echo "  cached: $pkg"
        continue
    fi
    echo "  downloading: $pkg"
    ( cd "$DEB_CACHE" && apt-get download "$pkg" )
done

echo "== Extracting GUI .debs into $TOOLCHAIN_PREFIX =="
for pkg in "${GUI_PACKAGES[@]}"; do
    for deb in "$DEB_CACHE/${pkg}"_*.deb; do
        [[ -e "$deb" ]] || continue
        dpkg-deb -x "$deb" "$TOOLCHAIN_PREFIX"
    done
done

# --------------------------------------------------------------------------- #
# 3. Build. TOP-LEVEL .pro, not Carcasum/Carcasum.pro:
#
#      TEMPLATE = subdirs ; SUBDIRS = Carcasum
#      ... else { classicTiles {} else { SUBDIRS += quazip ; Carcasum.depends = quazip } }
#
#    i.e. with no CONFIG flag it builds quazip first and then the GUI target, in
#    that dependency order. CONFIG+=classicTiles is DELIBERATELY NOT USED: it
#    swaps in jcz/jczTilesClassic.qrc, whose tile JPGs are NOT vendored (verified:
#    only 4 XML files under jcz/resources/plugins/classic) and rcc would fail.
#
#    The four qmake overrides are the driver build's, verbatim. -Wl,--disable-new-dtags
#    is REQUIRED, not cosmetic: without it ld emits DT_RUNPATH, which does not cover
#    the *transitive* deps (libpcre2-16, libdouble-conversion, libmd4c) that are only
#    present inside the prefix. See bootstrap_toolchain.sh's closing notes.
# --------------------------------------------------------------------------- #
echo "== Step 3: qmake + make into $BUILD_DIR =="
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

"$QMAKE_BIN" \
    "INCLUDEPATH+=$TOOLCHAIN_PREFIX/usr/include" \
    "QMAKE_LIBDIR+=$LIBDIR" \
    "QMAKE_RPATHDIR+=$LIBDIR" \
    "QMAKE_LFLAGS+=-Wl,--disable-new-dtags" \
    "$REPO/vendor/carcasum/Carcasum.pro"

make "-j$JOBS"

BIN="$BUILD_DIR/Carcasum/carcasum_gui"
if [[ ! -x "$BIN" ]]; then
    echo "FAIL: $BIN not produced" >&2
    exit 1
fi

echo
echo "== Built =="
sha256sum "$BIN"
echo
cat <<EOF
Launch it (WSLg is live on both boxes; /tmp/.X11-unix/X0 verified present):

  QT_QPA_PLATFORM=xcb DISPLAY=:0 $BIN

First run:
  * "Download JCloisterZone-2.6.zip?"  ->  answer **No**. The vendored PNGs in
    gui/tilesJczf.qrc are the fallback and the GUI is fully playable offline.
  * Note the "QStandardPaths::DataLocation:" line it prints — your per-game move
    histories autosave under <that>/games/<epoch>.
  * Then follow PROTOCOL.md §8.
EOF
