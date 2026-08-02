#!/usr/bin/env python3
"""Shared machinery for hand-rolling Chaquopy-installable Android wheels.

WHY THIS EXISTS
---------------
Chaquopy 17 CANNOT build native code. Its pip wrapper always runs

    pip install --only-binary :all: --platform android_<minSdk>_<abi> --target ...

so ``--only-binary :all:`` rules out sdists and source trees outright, and a local
source directory containing an extension dies with
``error: CCompiler.compile: Chaquopy cannot compile native code``. The ONLY supported
way to get native code into a Chaquopy APK is to hand pip a FINISHED Android wheel.

Two build scripts now do that:

* ``build_cy_wheels.py``    — the Cython fast paths (``carc-cy``), M4/2026-07-27.
* ``build_rust_wheels.py``  — the Rust engine+search core (``carc-rs``), P7/2026-08-01.

Everything they genuinely share lives here: NDK discovery, the
``com.chaquo.python:target`` artifact (Android ``Python.h`` + ``libpython3.12.so``),
the readelf link assertions, and the wheel writer. Anything that is specific to one
toolchain (Cython invocation, cargo invocation) deliberately stays in its own script.

NOTHING IN HERE MAY CHANGE THE BYTES ``build_cy_wheels.py`` PRODUCED BEFORE THE
REFACTOR — the cy wheel is a shipped artefact and its content-addressed version does
not cover the compiler flags.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants shared by every Android wheel this repo builds                     #
# --------------------------------------------------------------------------- #
MAVEN_BASE = "https://repo.maven.apache.org/maven2/com/chaquo/python/target"

# Android ABIs we cross-build, and the clang/rust target triple for each.
# Chaquopy's Python 3.12+ runtime ships 64-bit ABIs only (see app/build.gradle.kts
# `ndk { abiFilters }`): arm64-v8a = phones, x86_64 = emulator.
ABI_TRIPLES: dict[str, str] = {
    "arm64-v8a": "aarch64-linux-android",
    "x86_64": "x86_64-linux-android",
}

# Wheel platform-tag API level. 21 matches Chaquopy's own published wheels
# (e.g. numpy-1.26.2-0-cp312-cp312-android_21_arm64_v8a.whl). pip's
# ``packaging.tags.android_platforms()`` yields every level from the target minSdk
# down to 16, so an android_21 wheel stays installable at minSdk 26.
ANDROID_API = 21

# CPython shipped by Chaquopy 17.0.0, and the artifact we pull Android headers +
# libpython from.
PYTHON_VERSION = "3.12"
TARGET_ARTIFACT_VERSION = "3.12.12-0"

# Android 15+ runs some devices (incl. Pixel 9 / caiman, in its opt-in 16 KiB mode)
# with 16 KiB pages; a shared object whose LOAD segments are only 4 KiB-aligned will
# not load there.
#
# ⚠️ MEASURED 2026-08-01, NOT assumed: NDK r27.3's clang driver does **not** pass this
# by default. A trivial `clang --target=aarch64-linux-android21 -shared` lands at
# p_align 0x1000; adding the flag moves it to 0x4000.
#
# ✅ BOTH WHEELS CARRY IT SINCE 2026-08-01. The Rust wheel had it from the start; the cy
# wheels were left 4 KiB-aligned so the P7 tooling refactor could be proved
# byte-identical, which meant every cy wheel shipped before that date would fail to
# dlopen on a 16 KiB-page device (latent only because the Pixel 9 Pro defaults to 4 KiB
# pages). Adopting the flag CHANGES THE SHIPPED BYTES — a deliberate, approved break of
# that freeze — and `require_page_align` is now hard for both builds.
MAX_PAGE_SIZE = 16384
PAGE_ALIGN_LDFLAG = f"-Wl,-z,max-page-size={MAX_PAGE_SIZE}"


def make_logger(prefix: str):
    def log(msg: str) -> None:
        print(f"[{prefix}] {msg}", flush=True)
    return log


# --------------------------------------------------------------------------- #
# Toolchain discovery                                                          #
# --------------------------------------------------------------------------- #
def find_ndk(sdk_dir: Path | None, explicit: str | None) -> Path:
    """Explicit dir > ANDROID_NDK_HOME/ROOT > highest side-by-side NDK in the SDK."""
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


def ensure_target(abi: str, cache_dir: Path, log=print) -> Path:
    """Download+extract the Chaquopy python-target zip for an ABI (cached).

    Gives us the Android ``include/python3.12`` headers and ``libpython3.12.so`` —
    the host's Python headers are NOT usable (different pyconfig.h), and on Android
    an extension module must name libpython in DT_NEEDED rather than leaving the
    CPython symbols undefined the way a Linux extension does."""
    dest = cache_dir / f"target-{TARGET_ARTIFACT_VERSION}-{abi}"
    marker = dest / ".complete"
    if marker.is_file():
        return dest
    url = (f"{MAVEN_BASE}/{TARGET_ARTIFACT_VERSION}/"
           f"target-{TARGET_ARTIFACT_VERSION}-{abi}.zip")
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / f"target-{TARGET_ARTIFACT_VERSION}-{abi}.zip"
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


def target_paths(target: Path, abi: str) -> tuple[Path, Path]:
    """``(include_dir, lib_dir)`` inside an extracted target artifact, validated."""
    include = target / "include" / f"python{PYTHON_VERSION}"
    libdir = target / "jniLibs" / abi
    if not (include / "Python.h").is_file():
        raise SystemExit(f"Android Python.h missing at {include}")
    if not (libdir / f"libpython{PYTHON_VERSION}.so").is_file():
        raise SystemExit(f"libpython{PYTHON_VERSION}.so missing at {libdir}")
    return include, libdir


# --------------------------------------------------------------------------- #
# ELF assertions — the cheap gate that catches a bad cross-link before a phone  #
# --------------------------------------------------------------------------- #
def _readelf(ndk: Path) -> Path:
    p = ndk_bin(ndk) / "llvm-readelf"
    if not p.is_file():
        raise SystemExit(f"llvm-readelf missing from the NDK: {p}")
    return p


def elf_info(so: Path, ndk: Path) -> dict:
    """DT_NEEDED / SONAME / machine / LOAD alignment, straight out of the ELF."""
    readelf = _readelf(ndk)
    dyn = subprocess.run([str(readelf), "-d", str(so)],
                         capture_output=True, text=True, check=True).stdout
    hdr = subprocess.run([str(readelf), "-h", str(so)],
                         capture_output=True, text=True, check=True).stdout
    seg = subprocess.run([str(readelf), "-l", str(so)],
                         capture_output=True, text=True, check=True).stdout

    needed, soname = [], None
    for line in dyn.splitlines():
        if "(NEEDED)" in line and "[" in line:
            needed.append(line.split("[", 1)[1].split("]", 1)[0])
        elif "(SONAME)" in line and "[" in line:
            soname = line.split("[", 1)[1].split("]", 1)[0]
    machine = ""
    for line in hdr.splitlines():
        if line.strip().startswith("Machine:"):
            machine = line.split(":", 1)[1].strip()

    aligns = _load_aligns(seg)
    return {
        "path": so.name,
        "machine": machine,
        "soname": soname,
        "needed": needed,
        # BOTH, and the GATE reads the min (see assert_links_libpython): one
        # under-aligned LOAD is enough to break dlopen on a 16 KiB-page device.
        "load_align_min": min(aligns) if aligns else 0,
        "load_align_max": max(aligns) if aligns else 0,
        "load_aligns": aligns,
        "size": so.stat().st_size,
    }


def _load_aligns(seg: str) -> list[int]:
    """Align of every LOAD program header in ``llvm-readelf -l`` output.

    ⚠️ FIXED 2026-08-02 (ROUND2 F-9). The previous parse joined each LOAD row with
    ``lines[i+1]`` and scanned the JOINED text backwards for the first ``0x`` token —
    which, in llvm-readelf's ONE-ROW-PER-HEADER format, is the align of the *next*
    program header. Measured against the shipped ``carc_cy/flat_leaf_cy.so``: four
    LOADs all at 0x4000 followed by ``DYNAMIC … RW 0x8`` parsed as
    ``[0x4000, 0x4000, 0x4000, 0x8]`` — LOAD#1's align was never sampled and
    DYNAMIC's leaked in. It only looked right because the caller took ``max()``.

    Both layouts are handled: llvm-readelf prints one row
    (``Type Offset VirtAddr PhysAddr FileSiz MemSiz Flg Align``, >= 8 tokens, Align
    last), GNU readelf wraps it and the align is the last hex token of the
    continuation line — which is recognisable because it starts with a hex offset
    rather than a header Type name.
    """
    out: list[int] = []
    lines = seg.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("LOAD"):
            continue
        toks = line.split()
        if len(toks) < 8 and i + 1 < len(lines):
            nxt = lines[i + 1].split()
            if nxt and nxt[0].startswith("0x"):
                toks = nxt
        for tok in reversed(toks):
            if tok.startswith("0x"):
                try:
                    out.append(int(tok, 16))
                except ValueError:
                    continue
                break
    return out


EXPECTED_MACHINE = {
    "arm64-v8a": "AArch64",
    "x86_64": "Advanced Micro Devices X86-64",
}


def assert_links_libpython(so: Path, ndk: Path, abi: str, log=print,
                           require_page_align: bool = True) -> dict:
    """Hard gate on the cross-link. Four ways this has bitten or could bite:

    1. no ``libpython3.12.so`` in DT_NEEDED -> the module's CPython symbols stay
       undefined and ``dlopen`` fails at import time ON THE PHONE, never here;
    2. ``libc.so`` absent -> a host-libc link leaked in;
    3. wrong ELF machine -> the ABI loop built the same object twice;
    4. LOAD alignment < 16 KiB -> will not load on a 16 KiB-page device
       (Android 15+). Judged on the MINIMUM over LOAD segments, not the max: one
       under-aligned LOAD breaks ``dlopen``, and a max hides it behind its
       best-aligned sibling (ROUND2 F-9). ``require_page_align=False`` downgrades
       this one to a warning — NO CALLER PASSES IT since 2026-08-01; both wheels
       now carry ``PAGE_ALIGN_LDFLAG`` and gate hard on it (see MAX_PAGE_SIZE).
       The parameter survives only so a future third artefact can be onboarded
       loudly rather than by relaxing the shared gate.
    """
    info = elf_info(so, ndk)
    want_machine = EXPECTED_MACHINE.get(abi)
    if want_machine and info["machine"] != want_machine:
        raise SystemExit(f"{so.name}: ELF machine {info['machine']!r} != "
                         f"{want_machine!r} for abi {abi}")
    libpy = f"libpython{PYTHON_VERSION}.so"
    if libpy not in info["needed"]:
        raise SystemExit(
            f"{so.name}: {libpy} is not in DT_NEEDED {info['needed']}.\n"
            f"On Android an extension module must link libpython explicitly "
            f"(-lpython{PYTHON_VERSION} against the com.chaquo.python:target "
            f"jniLibs/{abi}); leaving the symbols undefined only fails on device.")
    if "libc.so" not in info["needed"]:
        raise SystemExit(f"{so.name}: libc.so missing from DT_NEEDED "
                         f"{info['needed']} — this is not a bionic link")
    if info["load_align_min"] < MAX_PAGE_SIZE:
        msg = (f"{so.name}: LOAD alignments "
               f"{[hex(a) for a in info['load_aligns']]} include one below "
               f"0x{MAX_PAGE_SIZE:x}; it will not load on a 16 KiB-page device. "
               f"Add {PAGE_ALIGN_LDFLAG} to the link.")
        if require_page_align:
            raise SystemExit(msg)
        log(f"WARNING: {msg}")
    log(f"readelf {abi}/{so.name}: machine={info['machine']} "
        f"needed={info['needed']} load_align=0x{info['load_align_min']:x}"
        f" (over {len(info['load_aligns'])} LOAD segments)")
    return info


# --------------------------------------------------------------------------- #
# Versioning                                                                   #
# --------------------------------------------------------------------------- #
def content_version(paths: list[Path], extra: bytes = b"") -> str:
    """Content-addressed ``1.<a>.<b>`` from the source bytes, in the given order.

    Gradle asks the build script for this at CONFIGURATION time so the pip
    requirement string itself changes whenever a source does — which invalidates
    Chaquopy's task inputs AND makes a stale wheel in pip's cache unreachable.

    ``extra`` mixes in anything OTHER than source bytes that changes the output
    object — in practice the link flags. ⚠️ ADDED 2026-08-01 because the source-only
    rule had a live hole: adding ``-Wl,-z,max-page-size=16384`` to the cy link changed
    the shipped ``.so`` bytes while leaving the version string identical, so Chaquopy
    re-served the stale 4 KiB-aligned wheel out of pip's cache and the fix would have
    silently not shipped (observed in `app/build/python/pip/debug/*/carc_cy/*.so`).
    A build input that changes the artefact must change the version."""
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    if extra:
        h.update(b"\0extra\0")
        h.update(extra)
    d = h.hexdigest()
    return f"1.{int(d[:4], 16)}.{int(d[4:8], 16)}"


# Directory names that are BUILD OUTPUT, never source, and must not reach a
# content-addressed version. ⚠️ THE GRADLE fileTree EXCLUSIONS MUST MATCH THIS LIST
# EXACTLY (`android/app/build.gradle.kts`, buildRustWheels `sources`), because that
# task claims parity with this rule — the claim was FALSE until 2026-08-02
# (REVIEW.md #8): `rust/carc/target/` holds .rs/.toml/.lock files, including
# per-compilation RANDOMISED names like
# `target/debug/incremental/carc_core-*/s-*-*.lock`, so `carc-rs==X.Y.Z` was not
# reproducible from a clean checkout and moved on every local `cargo build`.
VERSION_EXCLUDE_DIRS: tuple[str, ...] = ("target", ".chaquopy-cache")


def content_version_tree(roots: list[Path], suffixes: tuple[str, ...],
                         exclude_dirs: tuple[str, ...] = VERSION_EXCLUDE_DIRS,
                         extra: bytes = b"") -> str:
    """Content-addressed version over a whole source TREE (the Rust crate case).

    Paths are hashed relative to their root and sorted, so the digest is stable
    across machines and checkout locations. A file's PATH is hashed too, so a pure
    rename still busts the cache.

    ``exclude_dirs`` drops any file with one of those names as a path COMPONENT
    (see VERSION_EXCLUDE_DIRS) — build artefacts are not source, and hashing them
    makes the version unreproducible from a git checkout.

    ``extra`` is the same escape hatch ``content_version`` has: bytes that change the
    emitted object without being source (link flags, the build script itself)."""
    excluded = set(exclude_dirs)
    h = hashlib.sha256()
    for root in roots:
        root = root.resolve()
        files = sorted(
            (p for p in root.rglob("*")
             if p.is_file() and p.suffix in suffixes
             and not (excluded & set(p.relative_to(root).parts[:-1]))),
            key=lambda p: p.relative_to(root).as_posix(),
        )
        for p in files:
            h.update(p.relative_to(root).as_posix().encode())
            h.update(b"\0")
            h.update(p.read_bytes())
    if extra:
        h.update(b"\0extra\0")
        h.update(extra)
    d = h.hexdigest()
    return f"1.{int(d[:4], 16)}.{int(d[4:8], 16)}"


# --------------------------------------------------------------------------- #
# Wheel packaging                                                              #
# --------------------------------------------------------------------------- #
def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def platform_tag(abi: str) -> str:
    return f"android_{ANDROID_API}_{abi.replace('-', '_')}"


def wheel_tag(abi: str, py_tag: str, abi_tag: str | None = None) -> str:
    """``<py>-<abi>-<platform>``. ``abi_tag`` defaults to ``py_tag`` (cp312-cp312).

    Pass ``abi_tag="abi3"`` for a stable-ABI build. See build_rust_wheels.py's
    module docstring for why the Android artefact deliberately does NOT do that."""
    return f"{py_tag}-{abi_tag or py_tag}-{platform_tag(abi)}"


def write_wheel(
    *,
    out_dir: Path,
    dist_name: str,
    version: str,
    tag: str,
    payload: list[tuple[str, bytes]],
    summary: str,
    top_level: list[str],
    generator: str,
    plat: str,
    provenance: dict | None = None,
    log=print,
) -> Path:
    """Hand-roll a wheel. ``payload`` is [(arcname, bytes)] for the code files.

    Deterministic: fixed 1980-01-01 timestamps and fixed mode bits, so two builds
    of identical inputs are byte-identical zips — ``provenance`` included, since it
    is a function of the build inputs and is serialised with sorted keys.

    ``provenance`` (REVIEW.md #9) is written to ``<dist-info>/PROVENANCE.json``:
    WHICH compiler, target triple and profile produced the bytes in this wheel. It
    exists because two ``carc_rs`` builds from different rustc versions were
    otherwise indistinguishable in every record the repo writes, which is what made
    an unpinned cross-compile undetectable after the fact.
    """
    # pip normalises ``a_b`` <-> ``a-b``; Chaquopy's pip_install.py rebuilds the
    # requirement for the 2nd..Nth ABI as ``dist_info_name.replace("_", "-")``,
    # so the dist-info dir must use the underscore spelling.
    dist_dir = dist_name.replace("-", "_")
    wheel_name = f"{dist_dir}-{version}-{tag}.whl"
    dist_info = f"{dist_dir}-{version}.dist-info"
    out_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = out_dir / wheel_name

    files = list(payload)
    metadata = (
        "Metadata-Version: 2.1\n"
        f"Name: {dist_name}\n"
        f"Version: {version}\n"
        f"Summary: {summary}\n"
        f"Platform: {plat}\n"
    ).encode()
    wheel_meta = (
        "Wheel-Version: 1.0\n"
        f"Generator: {generator}\n"
        "Root-Is-Purelib: false\n"
        f"Tag: {tag}\n"
    ).encode()
    files += [
        (f"{dist_info}/METADATA", metadata),
        (f"{dist_info}/WHEEL", wheel_meta),
        (f"{dist_info}/top_level.txt", ("\n".join(top_level) + "\n").encode()),
    ]
    if provenance:
        blob = json.dumps(provenance, indent=2, sort_keys=True).encode()
        files.append((f"{dist_info}/PROVENANCE.json", blob))
        log(f"provenance {dist_name}-{version}: "
            + " ".join(f"{k}={provenance[k]}" for k in sorted(provenance)))
    record_lines = [f"{name},{_record_hash(data)},{len(data)}" for name, data in files]
    # The RECORD row itself carries no hash/size, per the wheel spec.
    record_lines.append(f"{dist_info}/RECORD,,")
    files.append((f"{dist_info}/RECORD", ("\n".join(record_lines) + "\n").encode()))

    if wheel_path.exists():
        wheel_path.unlink()
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    log(f"wheel {wheel_path.name} ({wheel_path.stat().st_size // 1024} KiB)")
    return wheel_path


def clear_stale_wheels(out_dir: Path, dist_prefix: str) -> None:
    """A version bump must never leave two candidates for --find-links to choose."""
    if out_dir.is_dir():
        for old in out_dir.glob(f"{dist_prefix}-*.whl"):
            old.unlink()
