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
import base64
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent            # android/tools
ANDROID_DIR = HERE.parent                          # android
REPO = ANDROID_DIR.parent                          # repo root
PKG_DIR = ANDROID_DIR / "native" / "carc-cy"

sys.path.insert(0, str(PKG_DIR))
from build_config import (  # noqa: E402
    ABI_TRIPLES,
    ANDROID_API,
    DIST_NAME,
    MODULES,
    PACKAGE,
    PYTHON_VERSION,
    PYX_SOURCE_DIR,
    TARGET_ARTIFACT_VERSION,
)

MAVEN_BASE = "https://repo.maven.apache.org/maven2/com/chaquo/python/target"
CACHE_DIR = PKG_DIR / ".cache"
# cp312: matches Chaquopy 17's bundled CPython. Wheels are interpreter-specific.
PY_TAG = "cp" + PYTHON_VERSION.replace(".", "")


def log(msg: str) -> None:
    print(f"[build_cy_wheels] {msg}", flush=True)


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
    h = hashlib.sha256()
    for mod in MODULES:
        h.update((REPO / PYX_SOURCE_DIR / f"{mod}.pyx").read_bytes())
    d = h.hexdigest()
    return f"1.{int(d[:4], 16)}.{int(d[4:8], 16)}"


# --------------------------------------------------------------------------- #
# 2. Toolchain discovery                                                       #
# --------------------------------------------------------------------------- #
def find_ndk(sdk_dir: Path | None, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_dir():
            raise SystemExit(f"--ndk-dir does not exist: {p}")
        return p
    for env in ("ANDROID_NDK_HOME", "ANDROID_NDK_ROOT"):
        v = os.environ.get(env)
        if v and Path(v).is_dir():
            return Path(v)
    if sdk_dir is None:
        sdk_dir = Path(os.environ.get("ANDROID_HOME", Path.home() / "Android" / "Sdk"))
    ndk_root = sdk_dir / "ndk"
    if ndk_root.is_dir():
        # Highest installed version wins.
        cands = sorted(
            (d for d in ndk_root.iterdir() if d.is_dir()),
            key=lambda d: [int(x) for x in d.name.split(".") if x.isdigit()],
        )
        if cands:
            return cands[-1]
    raise SystemExit(
        f"No Android NDK found under {ndk_root}. Install one with:\n"
        f"    {sdk_dir}/cmdline-tools/latest/bin/sdkmanager --install 'ndk;27.3.13750724'"
    )


def ndk_bin(ndk: Path) -> Path:
    host = {"Linux": "linux-x86_64", "Darwin": "darwin-x86_64"}.get(platform.system())
    if host is None:
        raise SystemExit(f"unsupported build host: {platform.system()}")
    p = ndk / "toolchains" / "llvm" / "prebuilt" / host / "bin"
    if not p.is_dir():
        raise SystemExit(f"NDK toolchain missing: {p}")
    return p


def ensure_target(abi: str) -> Path:
    """Download+extract the Chaquopy python-target zip for an ABI (cached).

    Gives us the Android ``include/python3.12`` headers and ``libpython3.12.so`` —
    the host's Python headers are NOT usable (different pyconfig.h)."""
    dest = CACHE_DIR / f"target-{TARGET_ARTIFACT_VERSION}-{abi}"
    marker = dest / ".complete"
    if marker.is_file():
        return dest
    url = (
        f"{MAVEN_BASE}/{TARGET_ARTIFACT_VERSION}/"
        f"target-{TARGET_ARTIFACT_VERSION}-{abi}.zip"
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE_DIR / f"target-{TARGET_ARTIFACT_VERSION}-{abi}.zip"
    if not zip_path.is_file():
        log(f"downloading {url}")
        try:
            with urllib.request.urlopen(url, timeout=180) as r, open(zip_path, "wb") as f:
                shutil.copyfileobj(r, f)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"failed to download Python target for {abi}: {exc}")
    if dest.is_dir():
        shutil.rmtree(dest)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    marker.write_text("ok")
    return dest


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
    bindir = ndk_bin(ndk)
    clang = bindir / "clang"
    strip = bindir / "llvm-strip"
    target = ensure_target(abi)
    include = target / "include" / f"python{PYTHON_VERSION}"
    libdir = target / "jniLibs" / abi
    if not (include / "Python.h").is_file():
        raise SystemExit(f"Android Python.h missing at {include}")
    if not (libdir / f"libpython{PYTHON_VERSION}.so").is_file():
        raise SystemExit(f"libpython{PYTHON_VERSION}.so missing at {libdir}")

    out_dir = build_dir / abi / PACKAGE
    out_dir.mkdir(parents=True, exist_ok=True)
    built = {}
    for mod, c_file in c_files.items():
        so = out_dir / f"{mod}.so"
        cmd = [
            str(clang),
            f"--target={triple}{ANDROID_API}",
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
        built[mod] = so
    return built


# --------------------------------------------------------------------------- #
# 4. Wheel packaging                                                           #
# --------------------------------------------------------------------------- #
def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_wheel(abi: str, sos: dict[str, Path], version: str, out_dir: Path) -> Path:
    abi_tag = abi.replace("-", "_")
    plat = f"android_{ANDROID_API}_{abi_tag}"
    tag = f"{PY_TAG}-{PY_TAG}-{plat}"
    wheel_name = f"{PACKAGE}-{version}-{tag}.whl"
    dist_info = f"{PACKAGE}-{version}.dist-info"
    out_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = out_dir / wheel_name

    init_src = (PKG_DIR / PACKAGE / "__init__.py").read_bytes()

    payload: list[tuple[str, bytes]] = [(f"{PACKAGE}/__init__.py", init_src)]
    for mod in MODULES:
        payload.append((f"{PACKAGE}/{mod}.so", sos[mod].read_bytes()))

    metadata = (
        "Metadata-Version: 2.1\n"
        f"Name: {DIST_NAME}\n"
        f"Version: {version}\n"
        "Summary: Cython fast paths (flat leaf + board encoder) for Carcassonne AI\n"
        f"Platform: {plat}\n"
    ).encode()
    wheel_meta = (
        "Wheel-Version: 1.0\n"
        "Generator: carc-cy build_cy_wheels.py\n"
        "Root-Is-Purelib: false\n"
        f"Tag: {tag}\n"
    ).encode()
    top_level = f"{PACKAGE}\n".encode()

    payload += [
        (f"{dist_info}/METADATA", metadata),
        (f"{dist_info}/WHEEL", wheel_meta),
        (f"{dist_info}/top_level.txt", top_level),
    ]

    record_lines = [f"{name},{_record_hash(data)},{len(data)}" for name, data in payload]
    # The RECORD row itself carries no hash/size, per the wheel spec.
    record_lines.append(f"{dist_info}/RECORD,,")
    payload.append((f"{dist_info}/RECORD", ("\n".join(record_lines) + "\n").encode()))

    if wheel_path.exists():
        wheel_path.unlink()
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in payload:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    log(f"wheel {wheel_path.name} ({wheel_path.stat().st_size // 1024} KiB)")
    return wheel_path


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
    ndk = find_ndk(args.sdk_dir, args.ndk_dir)
    log(f"NDK {ndk.name}  version {version}  abis {' '.join(args.abis)}")

    build_dir = PKG_DIR / "build" / "android"
    build_dir.mkdir(parents=True, exist_ok=True)
    c_files = cythonize(build_dir)

    # Clear stale wheels so a version bump can never leave two candidates behind for
    # pip's --find-links resolution to choose between.
    if args.out.is_dir():
        for old in args.out.glob(f"{PACKAGE}-*.whl"):
            old.unlink()

    for abi in args.abis:
        sos = compile_abi(abi, c_files, ndk, build_dir)
        build_wheel(abi, sos, version, args.out)

    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
