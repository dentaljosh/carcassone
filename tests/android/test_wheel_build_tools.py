"""The Android wheel build tooling — the parts that decide WHAT SHIPS.

None of this runs a compiler; every case here is a pure function that the 2026-08-02
review found wrong, and each one had the same shape: a rule declared in one place and
silently not applied in another. So the assertions are about the RULE, not about a
built artefact.

* ``content_version_tree`` must hash SOURCE only — a version that moves on every local
  ``cargo build`` is not a source fingerprint (REVIEW.md #8).
* ``_load_aligns`` must read the LOAD segments' own Align column — the old parse read
  the NEXT program header's, and ``max()`` hid it (ROUND2 F-9).
* the toolchain pin must be applied and asserted, not merely declared (REVIEW.md #1).
* the version salts must cover the whole codegen input set, so a flag/compiler change
  cannot be served stale out of pip's cache (REVIEW.md #10, ROUND2 F-3).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import _chaquopy_common as C  # noqa: E402  (conftest puts android/tools on sys.path)
import build_cy_wheels as CY  # noqa: E402
import build_rust_wheels as R  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SUFFIXES = (".rs", ".toml", ".lock")


# --------------------------------------------------------------------------- #
# REVIEW.md #8 — the content-addressed version is a SOURCE fingerprint          #
# --------------------------------------------------------------------------- #
def test_content_version_tree_ignores_build_output(tmp_path: Path):
    """A clean clone and a built tree with identical sources must agree.

    `rust/carc/target/` really does contain `.rs`/`.toml`/`.lock` files, including
    per-compilation RANDOMISED names (`incremental/*/s-*-*.lock`), so hashing it made
    `carc-rs==X.Y.Z` unreproducible and churned it on every dev build."""
    (tmp_path / "src.rs").write_text("fn main() {}")
    clean = C.content_version_tree([tmp_path], SUFFIXES)

    for d in C.VERSION_EXCLUDE_DIRS:
        junk = tmp_path / d / "debug" / "incremental"
        junk.mkdir(parents=True)
        (junk / "s-hkx0qkkttd-1lhkiu7.lock").write_text("randomised")
        (junk / "host.rs").write_text("generated")
    assert C.content_version_tree([tmp_path], SUFFIXES) == clean

    # ...and it must still be a fingerprint of the sources it DOES cover.
    (tmp_path / "src.rs").write_text("fn main() { /* changed */ }")
    assert C.content_version_tree([tmp_path], SUFFIXES) != clean


def test_content_version_tree_extra_salt_moves_the_version(tmp_path: Path):
    (tmp_path / "src.rs").write_text("fn main() {}")
    base = C.content_version_tree([tmp_path], SUFFIXES)
    assert C.content_version_tree([tmp_path], SUFFIXES, extra=b"flag") != base


def test_gradle_excludes_match_the_hashing_rule():
    """The buildRustWheels fileTree CLAIMS parity with the build script. Until
    2026-08-02 the claim was false in the direction that matters (Gradle excluded
    what the script hashed), so it is asserted rather than commented."""
    kts = (REPO / "android" / "app" / "build.gradle.kts").read_text()
    for d in C.VERSION_EXCLUDE_DIRS:
        assert f'exclude("{d}/**"' in kts or f'"{d}/**"' in kts, \
            f"build.gradle.kts does not exclude {d}/** (VERSION_EXCLUDE_DIRS drift)"


# --------------------------------------------------------------------------- #
# ROUND2 F-9 — the 16 KiB page-alignment gate                                   #
# --------------------------------------------------------------------------- #
# Real `llvm-readelf -l` output shape: one row per program header, Align last.
_SEG = """
Program Headers:
  Type           Offset   VirtAddr           PhysAddr           FileSiz  MemSiz   Flg Align
  PHDR           0x000040 0x0000000000000040 0x0000000000000040 0x000230 0x000230 R   0x8
  LOAD           0x000000 0x0000000000000000 0x0000000000000000 0x00fa1c 0x00fa1c R   0x1000
  LOAD           0x00fa20 0x0000000000013a20 0x0000000000013a20 0x037f90 0x037f90 R E 0x4000
  LOAD           0x0479b0 0x000000000004f9b0 0x000000000004f9b0 0x0009d8 0x001650 RW  0x4000
  DYNAMIC        0x047ae8 0x000000000004fae8 0x000000000004fae8 0x0001c0 0x0001c0 RW  0x8
"""


def test_load_aligns_reads_the_load_rows_own_align():
    """THE BUG: the old parse joined each LOAD row with the NEXT line and took that
    line's align, so the FIRST LOAD was never sampled and DYNAMIC's 0x8 leaked in."""
    assert C._load_aligns(_SEG) == [0x1000, 0x4000, 0x4000]


def test_load_aligns_handles_the_wrapped_gnu_layout():
    wrapped = """
  LOAD           0x0000000000000000 0x0000000000000000 0x0000000000000000
                 0x000000000000fa1c 0x000000000000fa1c  R      0x4000
  DYNAMIC        0x0000000000047ae8 0x000000000004fae8 0x000000000004fae8
                 0x00000000000001c0 0x00000000000001c0  RW     0x8
"""
    assert C._load_aligns(wrapped) == [0x4000]


def test_page_align_gate_reads_the_minimum(monkeypatch, tmp_path: Path):
    """One under-aligned LOAD breaks dlopen on a 16 KiB-page device, so a sibling's
    good alignment must not mask it. `max()` did exactly that."""
    so = tmp_path / "carc_rs.so"
    so.write_bytes(b"")
    aligns = C._load_aligns(_SEG)
    info = {"path": so.name, "machine": "AArch64", "soname": so.name,
            "needed": [f"libpython{C.PYTHON_VERSION}.so", "libc.so"],
            "load_aligns": aligns, "load_align_min": min(aligns),
            "load_align_max": max(aligns), "size": 0}
    monkeypatch.setattr(C, "elf_info", lambda *a, **k: dict(info))
    with pytest.raises(SystemExit) as exc:
        C.assert_links_libpython(so, tmp_path, "arm64-v8a", log=lambda *_: None)
    assert "16 KiB-page device" in str(exc.value)

    ok = {**info, "load_aligns": [0x4000] * 3, "load_align_min": 0x4000,
          "load_align_max": 0x4000}
    monkeypatch.setattr(C, "elf_info", lambda *a, **k: dict(ok))
    C.assert_links_libpython(so, tmp_path, "arm64-v8a", log=lambda *_: None)


# --------------------------------------------------------------------------- #
# REVIEW.md #1 / #9 — the toolchain pin is applied, asserted and recorded        #
# --------------------------------------------------------------------------- #
def test_pinned_toolchain_is_read_from_the_crate_and_not_guessed():
    chan = R.pinned_toolchain()
    assert chan and chan in R.TOOLCHAIN_TOML.read_text()


def test_toolchain_env_forces_the_pin_regardless_of_cwd():
    """rustup resolves rust-toolchain.toml from the CWD upward, and neither Gradle
    (`android/`) nor the documented standalone usage (repo root) has `rust/carc` as an
    ancestor — so the pin must travel as RUSTUP_TOOLCHAIN, not as a cwd assumption."""
    assert R.toolchain_env()["RUSTUP_TOOLCHAIN"] == R.pinned_toolchain()


def test_a_toolchain_mismatch_fails_the_build_loudly(monkeypatch):
    monkeypatch.setattr(R, "pinned_toolchain", lambda: "9.99.9")
    with pytest.raises(SystemExit) as exc:
        R.assert_pinned_toolchain()
    msg = str(exc.value)
    assert "9.99.9" in msg and ("MISMATCH" in msg or "cannot resolve" in msg)


@pytest.mark.skipif(not __import__("shutil").which("rustc"),
                    reason="no rust toolchain on this box")
def test_wheel_provenance_records_compiler_target_and_profile():
    tc = R.assert_pinned_toolchain()
    prov = R.wheel_provenance("arm64-v8a", C.ABI_TRIPLES["arm64-v8a"], tc, "1.2.3")
    assert prov["target_triple"] == "aarch64-linux-android"
    assert prov["cargo_profile"] == R.CARGO_PROFILE
    assert prov["toolchain_channel"] == R.pinned_toolchain()
    assert prov["rustc"].startswith(R.pinned_toolchain()[:1])
    assert prov["wheel_version"] == "1.2.3"
    # Readable ON THE DEVICE: carc_rs.__version__ is a frozen 0.1.0 literal, so the
    # sidecar module is what carries a version that means something.
    ns: dict = {}
    exec(R._provenance_module(prov).decode(), ns)          # noqa: S102
    assert ns["PROVENANCE"] == prov and ns["__version__"] == "1.2.3"


def test_wheel_provenance_carries_no_timestamp():
    """`write_wheel` promises byte-identical zips for identical inputs."""
    tc = {"toolchain_channel": "1.96.0", "rustc": "1.96.0", "rustc_verbose": "rustc"}
    a = R.wheel_provenance("x86_64", "x86_64-linux-android", tc, "1.0.0")
    b = R.wheel_provenance("x86_64", "x86_64-linux-android", tc, "1.0.0")
    assert a == b


# --------------------------------------------------------------------------- #
# REVIEW.md #10 / ROUND2 F-3 — the version salts cover the codegen inputs        #
# --------------------------------------------------------------------------- #
def test_rust_version_salt_covers_the_link_flags(monkeypatch):
    before = R.source_version()
    monkeypatch.setattr(C, "PAGE_ALIGN_LDFLAG", "-Wl,-z,max-page-size=65536")
    assert R.source_version() != before, \
        "a link-flag change must move carc-rs's version or pip re-serves the stale wheel"


def test_rust_version_salt_covers_the_shared_build_script(tmp_path, monkeypatch):
    """F-4's stale-wheel path, closed on the version side as well as the task side."""
    before = R.link_signature()
    fake = tmp_path / "_chaquopy_common.py"
    fake.write_bytes(Path(C.__file__).read_bytes() + b"\n# changed\n")
    monkeypatch.setattr(C, "__file__", str(fake))
    assert R.link_signature() != before


def test_cy_version_salt_covers_the_cython_version(monkeypatch):
    before = CY.source_version()
    monkeypatch.setattr(CY, "cython_signature", lambda: "cython=0.0.0-fake")
    assert CY.source_version() != before, \
        "`pip install -U Cython` changes the emitted .c, so it must move the version"


def test_cython_signature_degrades_instead_of_raising(monkeypatch):
    """`--print-version` runs at Gradle CONFIGURATION time; a missing Cython must fail
    at `cythonize()` with its actionable message, not while Gradle configures."""
    def boom():
        raise SystemExit("Cython not available")

    monkeypatch.setattr(CY, "find_cython", boom)
    assert CY.cython_signature() == "cython=UNAVAILABLE"
    assert CY.source_version()


def test_cy_link_signature_reports_a_real_cython_version():
    sig = CY.cython_signature()
    assert sig.startswith("cython=")
    if sig != "cython=UNAVAILABLE":
        assert any(ch.isdigit() for ch in sig)


# --------------------------------------------------------------------------- #
# ROUND2 F-10 — the device build is hermetic                                     #
# --------------------------------------------------------------------------- #
def test_ambient_rustflags_never_reach_the_device_build(monkeypatch, tmp_path):
    """Ambient RUSTFLAGS are a codegen input invisible to the version hash, to every
    Gradle input and to every provenance record; CARGO_ENCODED_RUSTFLAGS is worse
    still, because cargo PREFERS it and would drop the -L/-l/soname/page-align args."""
    ndk = tmp_path / "ndk"
    bindir = ndk / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    bindir.mkdir(parents=True)
    triple = C.ABI_TRIPLES["arm64-v8a"]
    (bindir / f"{triple}{C.ANDROID_API}-clang").write_text("#!/bin/sh\n")
    (bindir / "llvm-ar").write_text("")

    monkeypatch.setenv("RUSTFLAGS", "-C target-feature=+neon -C opt-level=1")
    monkeypatch.setenv("CARGO_ENCODED_RUSTFLAGS", "-C\x1fopt-level=0")
    env = R.cargo_env("arm64-v8a", triple, ndk, tmp_path / "libs", jobs=1)
    assert "CARGO_ENCODED_RUSTFLAGS" not in env
    assert "target-feature" not in env["RUSTFLAGS"]
    assert "opt-level" not in env["RUSTFLAGS"]
    assert C.PAGE_ALIGN_LDFLAG in env["RUSTFLAGS"]
    assert env["RUSTUP_TOOLCHAIN"] == R.pinned_toolchain()


def test_the_build_scripts_are_importable_without_a_toolchain():
    """Both are run by Gradle's buildPython (`/usr/bin/python3.12` by default), which
    has no repo venv behind it — import + `--print-version` must not need one."""
    for script in ("build_rust_wheels.py", "build_cy_wheels.py"):
        out = subprocess.run(
            ["/usr/bin/env", "python3", str(REPO / "android" / "tools" / script),
             "--print-version"],
            capture_output=True, text=True, check=True)
        assert out.stdout.strip().startswith("1.")
