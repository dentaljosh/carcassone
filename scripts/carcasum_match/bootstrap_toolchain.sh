#!/usr/bin/env bash
#
# bootstrap_toolchain.sh — rootless Qt5 + Boost toolchain for building the
# Carcasum `tournament` binary, without sudo/apt-get install.
#
# Strategy: `apt-get download` works rootless on this box even though
# `apt-get install` does not (no sudo password available). So we download the
# .debs we need into a cache dir and `dpkg-deb -x` (extract, no scripts run)
# them into a local prefix that qmake/g++ are pointed at explicitly via
# qt.conf + command-line INCLUDEPATH/QMAKE_LIBDIR/QMAKE_RPATHDIR overrides.
#
# Idempotent: safe to re-run. Downloads are skipped if the .deb is already in
# the cache; extraction always re-runs (dpkg-deb -x just overwrites, which is
# fine and keeps this script self-healing if the prefix gets partially wiped).
#
# Usage:
#   scripts/carcasum_match/bootstrap_toolchain.sh
#
# Override locations if needed:
#   TOOLCHAIN_PREFIX=/some/other/prefix DEB_CACHE=/some/other/cache \
#     scripts/carcasum_match/bootstrap_toolchain.sh

set -euo pipefail

TOOLCHAIN_PREFIX="${TOOLCHAIN_PREFIX:-/home/doctor/opt/carcasum-toolchain}"
DEB_CACHE="${DEB_CACHE:-/home/doctor/opt/carcasum-toolchain-cache}"

# Ubuntu noble (24.04). Names include the t64 64-bit-time_t renames that
# happened for noble. If these package names 404, run
#   apt-cache search libqt5<module>
# and adjust — the *-dev / qmake / qtchooser names are stable across the
# t64 transition, only the runtime lib packages got renamed.
QT_PACKAGES=(
    qtbase5-dev
    qtbase5-dev-tools
    qtchooser
    qt5-qmake
    qt5-qmake-bin
    libqt5core5t64
    libqt5gui5t64
)

# boost/lexical_cast.hpp is header-only (from libboost1.83-dev).
# boost::chrono::thread_clock needs the compiled libs (system+chrono).
BOOST_PACKAGES=(
    libboost1.83-dev
    libboost-system1.83-dev
    libboost-chrono1.83-dev
    libboost-system1.83.0
    libboost-chrono1.83.0t64
)

# Link-time only: Debian's libQt5Gui.so.prl pulls in -lGL unconditionally
# (QtGui was built with desktop GL/GLX support) even though the tournament
# target never calls into GL itself. libgl1 (the runtime .so.1) is assumed
# already present system-wide (it is, on this box, as a transitive dep of
# the desktop stack) — these two packages just provide the unversioned
# libGL.so / libGLX.so *dev* symlinks qmake's linker line needs.
GL_PACKAGES=(
    libgl-dev
    libglx-dev
)

# Direct link-time NEEDED entries of libQt5Core.so / libQt5Gui.so on this
# Qt build that are NOT part of the base system image (verified empirically
# by linking and then `ldd`ing the result — do not assume, re-check if the
# Qt/Ubuntu version changes).
EXTRA_RUNTIME_PACKAGES=(
    libpcre2-16-0
    libdouble-conversion3
    libmd4c0
)

ALL_PACKAGES=(
    "${QT_PACKAGES[@]}"
    "${BOOST_PACKAGES[@]}"
    "${GL_PACKAGES[@]}"
    "${EXTRA_RUNTIME_PACKAGES[@]}"
)

mkdir -p "$TOOLCHAIN_PREFIX" "$DEB_CACHE"

echo "== Downloading .debs into $DEB_CACHE (skipping ones already cached) =="
for pkg in "${ALL_PACKAGES[@]}"; do
    if compgen -G "$DEB_CACHE/${pkg}_*.deb" > /dev/null; then
        echo "  cached: $pkg"
        continue
    fi
    echo "  downloading: $pkg"
    ( cd "$DEB_CACHE" && apt-get download "$pkg" )
done

echo "== Extracting .debs into $TOOLCHAIN_PREFIX (dpkg-deb -x, no root, no maintainer scripts) =="
for deb in "$DEB_CACHE"/*.deb; do
    dpkg-deb -x "$deb" "$TOOLCHAIN_PREFIX"
done

LIBDIR="$TOOLCHAIN_PREFIX/usr/lib/x86_64-linux-gnu"

# libgl-dev / libglx-dev ship libGL.so -> libGL.so.1 and libGLX.so ->
# libGLX.so.0 as *relative* symlinks. Those versioned targets live in the
# system-wide libgl1 package (/usr/lib/x86_64-linux-gnu), not in our prefix
# (we deliberately did not vendor libgl1 — it's a base-system package that
# was already installed). Re-point the symlinks at the real absolute system
# path so they resolve instead of dangling inside the prefix.
for pair in "libGL.so:libGL.so.1" "libGLX.so:libGLX.so.0"; do
    link_name="${pair%%:*}"
    target_name="${pair##*:}"
    link_path="$LIBDIR/$link_name"
    system_target="/usr/lib/x86_64-linux-gnu/$target_name"
    if [[ -L "$link_path" ]] && [[ ! -e "$link_path" ]]; then
        if [[ -e "$system_target" ]]; then
            rm "$link_path"
            ln -s "$system_target" "$link_path"
            echo "  re-pointed dangling $link_name -> $system_target"
        else
            echo "  WARNING: $link_path is dangling and $system_target does not exist on this box." >&2
            echo "           Is libgl1 installed system-wide? (dpkg -s libgl1)" >&2
        fi
    fi
done

QT_BIN_DIR="$TOOLCHAIN_PREFIX/usr/lib/qt5/bin"
QT_CONF="$QT_BIN_DIR/qt.conf"

echo "== Writing $QT_CONF =="
mkdir -p "$QT_BIN_DIR"
cat > "$QT_CONF" <<EOF
[Paths]
Prefix=$TOOLCHAIN_PREFIX/usr
ArchData=lib/x86_64-linux-gnu/qt5
Binaries=lib/qt5/bin
Data=share/qt5
Documentation=share/qt5/doc
Examples=lib/x86_64-linux-gnu/qt5/examples
Headers=include/x86_64-linux-gnu/qt5
HostBinaries=lib/qt5/bin
HostData=lib/x86_64-linux-gnu/qt5
HostLibraries=lib/x86_64-linux-gnu
Imports=lib/x86_64-linux-gnu/qt5/imports
Libraries=lib/x86_64-linux-gnu
LibraryExecutables=lib/x86_64-linux-gnu/qt5/libexec
Plugins=lib/x86_64-linux-gnu/qt5/plugins
Qml2Imports=lib/x86_64-linux-gnu/qt5/qml
Settings=$TOOLCHAIN_PREFIX/etc/xdg
Translations=share/qt5/translations
EOF

QMAKE_BIN="$QT_BIN_DIR/qmake"

echo "== Verifying qmake -query resolves into the prefix, not /usr =="
QUERY_OUT="$("$QMAKE_BIN" -query)"
echo "$QUERY_OUT"
if echo "$QUERY_OUT" | grep -q "QT_INSTALL_HEADERS:$TOOLCHAIN_PREFIX" \
   && echo "$QUERY_OUT" | grep -q "QT_INSTALL_LIBS:$TOOLCHAIN_PREFIX"; then
    echo "OK: QT_INSTALL_HEADERS / QT_INSTALL_LIBS resolve inside $TOOLCHAIN_PREFIX"
else
    echo "FAIL: qmake -query did not resolve into the prefix — check $QT_CONF" >&2
    exit 1
fi

cat <<EOF

== Toolchain ready ==
Prefix:  $TOOLCHAIN_PREFIX
qmake:   $QMAKE_BIN

To build the tournament target out-of-tree:
  mkdir -p vendor/carcasum/build-tournament
  ( cd vendor/carcasum/build-tournament && \\
    $QMAKE_BIN CONFIG+=tournament \\
      "INCLUDEPATH+=$TOOLCHAIN_PREFIX/usr/include" \\
      "QMAKE_LIBDIR+=$LIBDIR" \\
      "QMAKE_RPATHDIR+=$LIBDIR" \\
      "QMAKE_LFLAGS+=-Wl,--disable-new-dtags" \\
      ../Carcasum/Carcasum.pro && \\
    make -j8 )

Notes:
  - INCLUDEPATH/QMAKE_LIBDIR/QMAKE_RPATHDIR are passed on the qmake command
    line (not baked into Carcasum.pro) so the vendored source tree stays
    untouched by toolchain-location concerns.
  - QMAKE_LFLAGS+=-Wl,--disable-new-dtags is required: without it, ld emits
    a DT_RUNPATH (new-style) on the executable, which only applies to the
    executable's own *direct* NEEDED libs (libQt5Core.so, libQt5Gui.so,
    libboost_*.so). It is NOT inherited when the dynamic linker then
    resolves *their* transitive deps (libpcre2-16, libdouble-conversion,
    libmd4c — none of which are installed system-wide) and those lookups
    fail at runtime. --disable-new-dtags makes ld emit the old-style
    DT_RPATH instead, which the dynamic linker treats as part of the global
    search path for the whole process, so it also covers transitive deps.
  - REVISION in Carcasum.pro must be patched to a literal commit hash before
    running qmake — \$\$system(git rev-parse HEAD) fails once the vendored
    tree's .git is removed. Already applied for the current vendor snapshot.
EOF
