#!/usr/bin/env python3
"""Cross-compile the repo's Cython fast paths into Android wheels for Chaquopy.

WHY THIS EXISTS (read before "simplifying" it into a pip call)
--------------------------------------------------------------
Chaquopy 17 CANNOT build native code. Its pip wrapper (``chaquopy/pip_install.py``,
inside ``gradle-17.0.0.jar`` -> ``build-packages.zip``) always runs:

    pip install --only-binary :all: --platform android_<minSdk>_<abi> --target ...

``--only-binary :all:`` rules out sdists and source directories outright; a local
source tree containing an extension still dies with
``error: CCompiler.compile: Chaquopy cannot compile native code``. This was tightened,
not relaxed, in v17. The ONLY supported way to get a C extension into a Chaquopy APK is
to hand pip a finished Android wheel, which is what this script produces.

WHAT IT DOES
------------
1. Syncs ``src/carcassonne_ai/{flat_leaf_cy,flat_repr_cy}.pyx`` into
   ``android/native/carc-cy/carc_cy/`` (gitignored copies -> no source drift).
2. Runs Cython to emit ``.c`` (architecture-independent).
3. Compiles each module for each ABI with NDK clang, against the Android
   ``Python.h`` / ``libpython3.12.so`` from the ``com.chaquo.python:target`` artifact.
4. Packages one wheel per ABI, tagged ``cp312-cp312-android_21_<abi>``.

The wheels are dropped in ``--out``, which Gradle passes to Chaquopy as
``pip { options("--find-links", <out>); install("carc-cy==<version>") }``.

SHARED MACHINERY
----------------
NDK discovery, the ``com.chaquo.python:target`` artifact, the readelf link
assertions and the wheel writer live in ``_chaquopy_common.py``, shared with
``build_rust_wheels.py``. This script keeps only what is Cython-specific.

⚠️ The link flags here are FROZEN. This wheel is a shipped artefact whose
content-addressed version covers the ``.pyx`` bytes and nothing else, so a flag
change would ship silently. In particular the 16 KiB page-alignment flag that
``build_rust_wheels.py`` passes is deliberately NOT passed here: it would change
these bytes. Consequence, measured 2026-08-01 and worth a decision of its own:
**the cy extensions are 4 KiB-aligned and would not load on a 16 KiB-page
device.** The Pixel 9 Pro runs 4 KiB pages by default, so this is latent, not
live. ``assert_links_libpython(..., require_page_align=False)`` reports it on
every build instead of hiding it.

VERSION / CACHE BUSTING
-----------------------
``--version`` is content-addressed from the .pyx bytes by the Gradle task, so any edit
to a .pyx yields a new version, which changes the pip requirement string, which
invalidates Chaquopy's task inputs AND cannot hit a stale wheel in pip's cache.

STANDALONE USE
--------------
    python3 android/tools/build_cy_wheels.py --sync-only
    python3 android/tools/build_cy_wheels.py --out /tmp/wheels --version 1.2.3
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # android/tools
ANDROID_DIR = HERE.parent                          # android
REPO = ANDROID_DIR.parent                          # repo root
PKG_DIR = ANDROID_DIR / "native" / "carc-cy"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PKG_DIR))
import _chaquopy_common as C  # noqa: E402
from build_config import (  # noqa: E402
    ABI_TRIPLES,
    DIST_NAME,
    MODULES,
    PACKAGE,
    PYTHON_VERSION,
    PYX_SOURCE_DIR,
)

CACHE_DIR = PKG_DIR / ".cache"
# cp312: matches Chaquopy 17's bundled CPython. Wheels are interpreter-specific.
PY_TAG = "cp" + PYTHON_VERSION.replace(".", "")

log = C.make_logger("build_cy_wheels")

# build_config.py stays the single source of truth for what THIS wheel contains;
# the values it shares with the Rust wheel must agree with the common module or
# the two artefacts could disagree about what "android_21" means.
assert ABI_TRIPLES == C.ABI_TRIPLES, "ABI table drift between build_config and _chaquopy_common"
assert PYTHON_VERSION == C.PYTHON_VERSION, "python version drift"


# --------------------------------------------------------------------------- #
# 1. Source sync                                                               #
# --------------------------------------------------------------------------- #
def sync_sources() -> list[Path]:
    """Copy the canonical .pyx into the package dir. Returns the destinations."""
    src_dir = REPO / PYX_SOURCE_DIR
    dest_dir = PKG_DIR / PACKAGE
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for mod in MODULES:
        src = src_dir / f"{mod}.pyx"
        if not src.is_file():
            raise SystemExit(f"missing canonical source: {src}")
        dest = dest_dir / f"{mod}.pyx"
        data = src.read_bytes()
        # Only rewrite on change, so Cython's own timestamp check stays useful.
        if not dest.is_file() or dest.read_bytes() != data:
            dest.write_bytes(data)
            log(f"synced {src.relative_to(REPO)} -> {dest.relative_to(REPO)}")
        out.append(dest)
    return out


def source_version() -> str:
    """Content-addressed version from the .pyx bytes (fallback when --version absent).

    Gradle normally computes this itself so it is known at CONFIGURATION time; this
    keeps standalone runs consistent with it."""
    return C.content_version([REPO / PYX_SOURCE_DIR / f"{mod}.pyx" for mod in MODULES])


# --------------------------------------------------------------------------- #
# 2. Toolchain discovery (shared: see _chaquopy_common)                        #
# --------------------------------------------------------------------------- #
def find_cython() -> list[str]:
    """An interpreter that can run ``-m cython``. Prefers the current one."""
    cands = [[sys.executable], [str(REPO / ".venv" / "bin" / "python")], ["cython"]]
    for c in cands:
        exe = c[0]
        if exe != "cython" and not Path(exe).exists():
            continue
        cmd = c + (["-m", "cython", "--version"] if exe != "cython" else ["--version"])
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (subprocess.CalledProcessError, OSError):
            continue
        return c + (["-m", "cython"] if exe != "cython" else [])
    raise SystemExit(
        "Cython not available. Install it into the build interpreter:\n"
        f"    {sys.executable} -m pip install 'Cython>=3.0'"
    )


# --------------------------------------------------------------------------- #
# 3. Compile                                                                   #
# --------------------------------------------------------------------------- #
def cythonize(build_dir: Path) -> dict[str, Path]:
    cy = find_cython()
    out = {}
    for mod in MODULES:
        pyx = PKG_DIR / PACKAGE / f"{mod}.pyx"
        c_file = build_dir / f"{mod}.c"
        cmd = cy + [
            "-3",
            "--module-name", f"{PACKAGE}.{mod}",
            "-o", str(c_file),
            str(pyx),
        ]
        log(f"cython {mod}")
        subprocess.run(cmd, check=True)
        out[mod] = c_file
    return out


def compile_abi(abi: str, c_files: dict[str, Path], ndk: Path, build_dir: Path) -> dict[str, Path]:
    triple = ABI_TRIPLES[abi]
    bindir = C.ndk_bin(ndk)
    clang = bindir / "clang"
    strip = bindir / "llvm-strip"
    target = C.ensure_target(abi, CACHE_DIR, log)
    include, libdir = C.target_paths(target, abi)

    out_dir = build_dir / abi / PACKAGE
    out_dir.mkdir(parents=True, exist_ok=True)
    built = {}
    for mod, c_file in c_files.items():
        so = out_dir / f"{mod}.so"
        # ⚠️ FROZEN FLAGS — see the module docstring. Notably NO
        # C.PAGE_ALIGN_LDFLAG: adding it would change these shipped bytes.
        cmd = [
            str(clang),
            f"--target={triple}{C.ANDROID_API}",
            "-shared", "-fPIC", "-O3", "-DNDEBUG",
            # The Android include dir comes FIRST so its pyconfig.h shadows any host one.
            "-I", str(include),
            "-o", str(so),
            str(c_file),
            "-L", str(libdir), f"-lpython{PYTHON_VERSION}",
            f"-Wl,-soname,{mod}.so",
        ]
        log(f"clang {abi}/{mod}.so")
        subprocess.run(cmd, check=True)
        subprocess.run([str(strip), "--strip-unneeded", str(so)], check=True)
        # Catches a bad cross-link here instead of at dlopen time on the phone.
        C.assert_links_libpython(so, ndk, abi, log, require_page_align=False)
        built[mod] = so
    return built


# --------------------------------------------------------------------------- #
# 4. Wheel packaging (writer shared: see _chaquopy_common.write_wheel)          #
# --------------------------------------------------------------------------- #
def build_wheel(abi: str, sos: dict[str, Path], version: str, out_dir: Path) -> Path:
    payload: list[tuple[str, bytes]] = [
        (f"{PACKAGE}/__init__.py", (PKG_DIR / PACKAGE / "__init__.py").read_bytes())
    ]
    for mod in MODULES:
        payload.append((f"{PACKAGE}/{mod}.so", sos[mod].read_bytes()))
    return C.write_wheel(
        out_dir=out_dir,
        dist_name=DIST_NAME,
        version=version,
        tag=C.wheel_tag(abi, PY_TAG),
        payload=payload,
        summary="Cython fast paths (flat leaf + board encoder) for Carcassonne AI",
        top_level=[PACKAGE],
        generator="carc-cy build_cy_wheels.py",
        plat=C.platform_tag(abi),
        log=log,
    )


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, help="directory to write wheels into")
    ap.add_argument("--version", help="wheel version (default: content hash of the .pyx)")
    ap.add_argument("--sdk-dir", type=Path, help="Android SDK root (for NDK discovery)")
    ap.add_argument("--ndk-dir", help="explicit NDK directory")
    ap.add_argument("--abis", nargs="+", default=list(ABI_TRIPLES),
                    choices=list(ABI_TRIPLES))
    ap.add_argument("--sync-only", action="store_true",
                    help="only copy the .pyx into the package dir, then exit")
    ap.add_argument("--print-version", action="store_true")
    args = ap.parse_args()

    if args.print_version:
        print(source_version())
        return 0

    sync_sources()
    if args.sync_only:
        log("sync complete")
        return 0

    if args.out is None:
        ap.error("--out is required unless --sync-only/--print-version is given")

    version = args.version or source_version()
    ndk = C.find_ndk(args.sdk_dir, args.ndk_dir)
    log(f"NDK {ndk.name}  version {version}  abis {' '.join(args.abis)}")

    build_dir = PKG_DIR / "build" / "android"
    build_dir.mkdir(parents=True, exist_ok=True)
    c_files = cythonize(build_dir)

    # Clear stale wheels so a version bump can never leave two candidates behind for
    # pip's --find-links resolution to choose between.
    C.clear_stale_wheels(args.out, PACKAGE)

    for abi in args.abis:
        sos = compile_abi(abi, c_files, ndk, build_dir)
        build_wheel(abi, sos, version, args.out)

    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
