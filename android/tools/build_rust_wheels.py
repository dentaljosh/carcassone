#!/usr/bin/env python3
"""Cross-compile ``carc-py`` (the PyO3 module ``carc_rs``) into Android wheels.

WHY THIS EXISTS
---------------
Same reason as ``build_cy_wheels.py``: Chaquopy 17 CANNOT build native code — its
pip wrapper always runs ``pip install --only-binary :all: --platform
android_<minSdk>_<abi>``, so the only supported route into the APK is a FINISHED
Android wheel. maturin's own ``--target`` support is not used here for two reasons:
the wheel tag it emits (``android_21_*`` is not in its platform table) and the
explicit ``-lpython3.12`` link Android requires. Both are easier to state directly
than to talk maturin into. maturin stays the DESKTOP dev-wheel tool.

WHAT IT DOES
------------
1. Resolves the NDK and the Chaquopy ``com.chaquo.python:target`` artifact for each
   ABI (Android ``Python.h`` + ``libpython3.12.so``) — shared with the cy build via
   ``_chaquopy_common``.
2. Runs ``cargo build --release --target <triple> -p carc-py`` with the NDK linker
   and ``PYO3_CROSS_LIB_DIR`` pointed at that artifact's ``jniLibs/<abi>``.
3. Asserts the resulting ELF with readelf: ``libpython3.12.so`` in DT_NEEDED,
   bionic ``libc.so``, right machine, 16 KiB LOAD alignment.
4. Packages ``carc_rs.so`` as a TOP-LEVEL extension module, one wheel per ABI.

WHEEL NAMING DECISION (2026-08-01) — cp312-cp312, NOT abi3
----------------------------------------------------------
The desktop dev wheel maturin builds is ``abi3-py312``, and ``carc-py``'s Cargo.toml
does enable pyo3's ``abi3-py312`` feature, so the object in THIS wheel is in fact
stable-ABI-clean and *could* honestly be tagged ``cp312-abi3-android_21_<abi>``.
It is deliberately tagged ``cp312-cp312-android_21_<abi>`` anyway:

* Chaquopy 17 bundles exactly one interpreter (CPython 3.12). There is no second
  version for abi3's forward compatibility to serve.
* The wheel version is content-addressed off the Rust sources and rebuilt per APK,
  so nothing is gained by making the artefact outlive a source change.
* ``cp312-cp312-android_21_<abi>`` is the exact shape of Chaquopy's own published
  wheels and of the already-shipping ``carc-cy`` wheel — i.e. the tag path that is
  known to resolve through Chaquopy's pip wrapper on this project. abi3 + the
  ``android_*`` platform tag is a combination nothing here has exercised.

A cp312 tag on an abi3-clean object is a NARROWER claim than the truth, so it is
always correct; the reverse would not be. If Chaquopy ever ships two interpreter
versions, flip ``ABI_TAG`` to ``"abi3"`` — the readelf assertions and the Chaquopy
install are the gates that decide whether it worked, and both run either way.

STANDALONE USE
--------------
    python3 android/tools/build_rust_wheels.py --print-version
    python3 android/tools/build_rust_wheels.py --out /tmp/wheels --version 1.2.3
    python3 android/tools/build_rust_wheels.py --out /tmp/wheels --abis arm64-v8a
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # android/tools
ANDROID_DIR = HERE.parent                          # android
REPO = ANDROID_DIR.parent                          # repo root

sys.path.insert(0, str(HERE))
import _chaquopy_common as C  # noqa: E402

# --------------------------------------------------------------------------- #
# What this wheel is                                                           #
# --------------------------------------------------------------------------- #
CRATE_DIR = REPO / "rust" / "carc"
CARGO_TOML = CRATE_DIR / "Cargo.toml"
CARGO_PACKAGE = "carc-py"
# [lib] name in carc-py/Cargo.toml -> cargo emits `libcarc_rs.so`; Python must see
# it as `carc_rs.so`.
MODULE = "carc_rs"
DIST_NAME = "carc-rs"

# A TOP-LEVEL extension module, not a package. The `carc_cy` split-finder problem
# (a package whose __path__ would have to span Chaquopy's source asset and its
# requirements asset) simply does not arise for a single module: a module has no
# __path__ to bind. So no aliasing shim is needed either — `import carc_rs` is the
# real name on desktop and on device.
PY_TAG = "cp" + C.PYTHON_VERSION.replace(".", "")
ABI_TAG = PY_TAG                                   # see the naming decision above

# Everything whose bytes change the compiled module. rust-toolchain.toml is in here
# on purpose: a toolchain bump invalidates the G0 bit-exactness evidence, so it must
# also invalidate the wheel.
VERSION_ROOTS = [CRATE_DIR]
VERSION_SUFFIXES = (".rs", ".toml", ".lock")

CACHE_DIR = CRATE_DIR / ".chaquopy-cache"

log = C.make_logger("build_rust_wheels")


def source_version() -> str:
    """Content-addressed version over the Rust tree (fallback when --version absent).

    Gradle normally asks for this at CONFIGURATION time so the pip requirement string
    itself changes whenever a ``.rs`` does — which invalidates Chaquopy's task inputs
    AND makes a stale wheel in pip's cache unreachable."""
    return C.content_version_tree(VERSION_ROOTS, VERSION_SUFFIXES)


# --------------------------------------------------------------------------- #
# Toolchain                                                                    #
# --------------------------------------------------------------------------- #
def _env_triple(triple: str) -> str:
    """``aarch64-linux-android`` -> ``AARCH64_LINUX_ANDROID`` (cargo's env spelling)."""
    return triple.upper().replace("-", "_")


def ensure_rust_target(triple: str) -> None:
    installed = subprocess.run(["rustup", "target", "list", "--installed"],
                               capture_output=True, text=True, check=True).stdout
    if triple in installed.split():
        return
    log(f"rustup target add {triple}")
    subprocess.run(["rustup", "target", "add", triple], check=True)


def cargo_env(abi: str, triple: str, ndk: Path, libdir: Path, jobs: int) -> dict:
    bindir = C.ndk_bin(ndk)
    clang = bindir / f"{triple}{C.ANDROID_API}-clang"
    if not clang.is_file():
        raise SystemExit(f"NDK clang wrapper missing: {clang}")
    ar = bindir / "llvm-ar"
    et = _env_triple(triple)

    env = dict(os.environ)
    env.update({
        # cargo's linker for the TARGET (build scripts still build for the host).
        f"CARGO_TARGET_{et}_LINKER": str(clang),
        f"CC_{triple.replace('-', '_')}": str(clang),
        f"AR_{triple.replace('-', '_')}": str(ar),
        # PyO3 cross-compilation, in its abi3 "no target interpreter" mode.
        #
        # ⚠️ PYO3_CROSS_LIB_DIR is deliberately NOT set, and that is a correction to
        # the build spec's P7 line rather than an omission. MEASURED 2026-08-01:
        # setting it makes pyo3's build script fail with
        #     error: Could not find _sysconfigdata*.py in <jniLibs/<abi>>
        # because the `com.chaquo.python:target` artifact ships only
        # include/python3.12, jniLibs/ and lib-dynload/ — there is no stdlib and
        # therefore no sysconfigdata in it at all. The flag's PURPOSE (resolve
        # against the TARGET's libpython, never the host's) is carried instead by
        # the explicit -L<libdir> -lpython3.12 below, pointed at exactly the
        # directory PYO3_CROSS_LIB_DIR would have named, and enforced afterwards by
        # the readelf DT_NEEDED assertion. PYO3_CROSS + the pinned version are what
        # stop pyo3 from probing the host interpreter.
        "PYO3_CROSS": "1",
        "PYO3_CROSS_PYTHON_VERSION": C.PYTHON_VERSION,
        "CARGO_BUILD_JOBS": str(jobs),
    })
    env.pop("PYO3_CROSS_LIB_DIR", None)

    # pyo3's `extension-module` feature deliberately does NOT emit a link directive
    # for libpython: on Linux/macOS an extension resolves CPython symbols from the
    # already-loaded interpreter. ANDROID IS DIFFERENT — the dynamic linker will not
    # resolve undefined symbols against an unrelated library, so the module must
    # name libpython in DT_NEEDED or `dlopen` fails at import time on the phone.
    # Hence the explicit -L/-lpython3.12 here (and the readelf assertion after).
    link_args = [
        f"-L{libdir}",
        f"-lpython{C.PYTHON_VERSION}",
        f"-Wl,-soname,{MODULE}.so",
        C.PAGE_ALIGN_LDFLAG,
    ]
    rustflags = " ".join(f"-C link-arg={a}" for a in link_args)
    prev = env.get("RUSTFLAGS", "").strip()
    env["RUSTFLAGS"] = f"{prev} {rustflags}".strip()
    return env


def build_abi(abi: str, ndk: Path, jobs: int) -> Path:
    triple = C.ABI_TRIPLES[abi]
    ensure_rust_target(triple)
    target = C.ensure_target(abi, CACHE_DIR, log)
    _include, libdir = C.target_paths(target, abi)

    env = cargo_env(abi, triple, ndk, libdir, jobs)
    cmd = ["cargo", "build", "--release", "--target", triple,
           "-p", CARGO_PACKAGE, "--manifest-path", str(CARGO_TOML)]
    log(f"cargo {abi} ({triple}, -j{jobs})")
    subprocess.run(cmd, check=True, env=env)

    built = CRATE_DIR / "target" / triple / "release" / f"lib{MODULE}.so"
    if not built.is_file():
        raise SystemExit(f"cargo produced no {built}")
    staged = CRATE_DIR / "target" / triple / "release" / f"{MODULE}.so"
    shutil.copy2(built, staged)
    subprocess.run([str(C.ndk_bin(ndk) / "llvm-strip"), "--strip-unneeded",
                    str(staged)], check=True)
    C.assert_links_libpython(staged, ndk, abi, log, require_page_align=True)
    return staged


def build_wheel(abi: str, so: Path, version: str, out_dir: Path) -> Path:
    return C.write_wheel(
        out_dir=out_dir,
        dist_name=DIST_NAME,
        version=version,
        tag=C.wheel_tag(abi, PY_TAG, ABI_TAG),
        payload=[(f"{MODULE}.so", so.read_bytes())],
        summary="Rust engine + PUCT search core (carc-core) for Carcassonne AI",
        top_level=[MODULE],
        generator="carc-rs build_rust_wheels.py",
        plat=C.platform_tag(abi),
        log=log,
    )


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-compile carc_rs into Android wheels.")
    ap.add_argument("--out", type=Path, help="directory to write wheels into")
    ap.add_argument("--version", help="wheel version (default: content hash of rust/carc)")
    ap.add_argument("--sdk-dir", type=Path, help="Android SDK root (for NDK discovery)")
    ap.add_argument("--ndk-dir", help="explicit NDK directory")
    ap.add_argument("--abis", nargs="+", default=list(C.ABI_TRIPLES),
                    choices=list(C.ABI_TRIPLES))
    ap.add_argument("--jobs", type=int, default=4,
                    help="cargo -j (default 4: this box shares CPU with gate runs)")
    ap.add_argument("--print-version", action="store_true")
    args = ap.parse_args()

    if args.print_version:
        print(source_version())
        return 0
    if args.out is None:
        ap.error("--out is required unless --print-version is given")

    version = args.version or source_version()
    ndk = C.find_ndk(args.sdk_dir, args.ndk_dir)
    log(f"NDK {ndk.name}  version {version}  abis {' '.join(args.abis)}")

    C.clear_stale_wheels(args.out, MODULE)
    for abi in args.abis:
        so = build_abi(abi, ndk, args.jobs)
        build_wheel(abi, so, version, args.out)
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
