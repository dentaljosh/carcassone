#!/usr/bin/env python3
"""Assemble the self-contained M5 bench directory on the share.

    python3 scripts/m5_bench/build_bundle.py \
        --out /mnt/c/carc-shared/m5_bench_20260728

Produces::

    <out>/README_M5.md          run instructions (copied from scripts/m5_bench/)
    <out>/setup_m5.sh           macOS/Linux venv + optional native Cython build
    <out>/bench_champion.py     the must-work bench (pure python + numpy + pyyaml)
    <out>/bench_ane_forward.py  the optional CoreML/ANE probe (torch + coremltools)
    <out>/MANIFEST.json         build provenance (git rev, hashes, file counts)
    <out>/bundle/               the champion, importable standalone:
        carcassonne_ai/**            <- src/carcassonne_ai  (+ the two .pyx sources)
        carcassonne_ai/data/PRODUCTION.yaml
        wingedsheep/**               <- engine/wingedsheep (minus visualiser + art)
        endgame_solver.py, c5_leaf_override.py, snapshot.py
        setup_cy.py                  optional in-place arm64 Cython build
        positions.jsonl              60 mid-game roots the champion itself reached
        net/<CL-067 checkpoint>.pt   for bench_ane_forward.py only

ONE SOURCE OF TRUTH for the file mapping: this script IMPORTS and calls
``android/tools/sync_python.py``. The Android APK and this bundle therefore ship
byte-identical champion code by construction, and sync_python's import-closure gate
(nothing reaches the bundle whose module-scope imports cannot resolve) runs here too.

Everything below ``<out>`` is GENERATED. Do not edit it in place and do not commit it;
edit ``scripts/m5_bench/*`` and re-run. Re-running is idempotent.

⚠️ Re-running AFTER ``setup_m5.sh`` deletes the compiled ``.so`` files: sync_python
removes every entry it owns (including the whole ``carcassonne_ai/`` dir) before
copying, which is exactly the property that stops a deleted repo file surviving in the
bundle. Just re-run ``setup_m5.sh`` afterwards — it rebuilds them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent
DEFAULT_OUT = Path("/mnt/c/carc-shared/m5_bench_20260728")

# Copied verbatim into <out>/ (the things Joshua runs over ssh).
TOP_LEVEL_FILES = ("README_M5.md", "LOCAL_REFERENCE.md", "setup_m5.sh",
                   "bench_champion.py", "bench_ane_forward.py", "w_ladder.py")

# Copied into <out>/bundle/ (things the bundle needs but sync_python excludes).
PYX_SOURCES = ("flat_leaf_cy.pyx", "flat_repr_cy.pyx")

# Re-added AFTER sync_python's import gate, which drops the whole torch cluster
# (EXCLUDE_MODULES) because the Android APK has no torch. Here torch is a legitimate
# OPTIONAL dep of bench_ane_forward.py, and network.py is the only member of that
# cluster it needs. Nothing on the champion's play path imports it — the champion is
# classical — so bench_champion.py is unaffected whether or not torch exists.
TORCH_MODULES = ("network.py",)

# The CL-067 distilled net — policy-prior distillation of the 4x teacher, iter_03.
# Path + sha256 from measurement/distill_strong_20260723/CHECKPOINT_MANIFEST.json
# (claim CL-067, governance/CLAIM_REGISTRY.csv). Used ONLY by bench_ane_forward.py;
# the champion is classical and never loads it.
CKPT_MANIFEST = REPO / "measurement" / "distill_strong_20260723" / "CHECKPOINT_MANIFEST.json"
CKPT_ITER = 3


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_rev() -> dict:
    def _run(*args) -> str | None:
        try:
            return subprocess.run(["git", "-C", str(REPO), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        except Exception:                          # noqa: BLE001
            return None

    return {"rev": _run("rev-parse", "HEAD"),
            "branch": _run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_run("status", "--porcelain", "--", "src", "engine"))}


def resolve_ckpt() -> dict | None:
    """The CL-067 checkpoint entry, verified on disk (sha256 checked, not trusted)."""
    if not CKPT_MANIFEST.is_file():
        print(f"build_bundle: no checkpoint manifest at {CKPT_MANIFEST}", file=sys.stderr)
        return None
    doc = json.loads(CKPT_MANIFEST.read_text())
    entry = next((c for c in doc["checkpoints"] if int(c["iter"]) == CKPT_ITER), None)
    if entry is None:
        print(f"build_bundle: iter {CKPT_ITER} absent from {CKPT_MANIFEST}",
              file=sys.stderr)
        return None
    path = Path(entry["path_local"])
    if not path.is_file():
        print(f"build_bundle: checkpoint missing on disk: {path}", file=sys.stderr)
        return None
    return {"entry": entry, "path": path}


SETUP_CY = '''#!/usr/bin/env python3
"""Build the two Cython fast paths IN PLACE inside this bundle.

    python setup_cy.py build_ext --inplace

Drops ``carcassonne_ai/flat_leaf_cy.cpython-3xx-<arch>.so`` (and the board-encoder
sibling) next to their .py callers, which is exactly where the LAZY imports in
``flat_leaf.py`` (`from . import flat_leaf_cy`) and ``board_repr.py``
(`from .flat_repr_cy import ...`) look. No aliasing needed: unlike the Android APK,
this bundle is one plain directory on sys.path, so the package is not split across
two finders and the extensions can live inside ``carcassonne_ai`` itself.

OPTIONAL. Both call sites catch ImportError and fall back to pure Python, so a
bundle with no .so is CORRECT, just SLOWER -- measured 4.5x per decision on the
5900XT at k1x32 (2026-07-28, same 6 positions both ways). ``bench_champion.py``
measures which path bound and records it as ``cython.leaf_active``.

Sibling of the repo's setup_flat_leaf_cy.py / setup_flat_repr_cy.py; the only
difference is package_dir (here the package is at the bundle root, not under src/).
"""
from Cython.Build import cythonize
from setuptools import Extension, setup

MODULES = ("flat_leaf_cy", "flat_repr_cy")

setup(
    name="carc_bundle_cy",
    ext_modules=cythonize(
        [
            Extension(
                f"carcassonne_ai.{m}",
                [f"carcassonne_ai/{m}.pyx"],
                extra_compile_args=["-O3"],
            )
            for m in MODULES
        ],
        compiler_directives={"language_level": "3"},
    ),
    zip_safe=False,
)
'''


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("-n", "--n-positions", type=int, default=60)
    p.add_argument("--no-ckpt", action="store_true",
                   help="skip the 30 MB CL-067 checkpoint (champion bench does not need it)")
    a = p.parse_args(argv)

    out = a.out.resolve()
    bundle = out / "bundle"
    out.mkdir(parents=True, exist_ok=True)

    # ---- 0. drop the extras WE own, before sync_python's gate sees them -----
    #
    # sync_python removes only ITS OWNED_ENTRIES, so anything this script adds to the
    # bundle root survives into the next build — and setup_cy.py is a .py file inside
    # the bundle, which means the import-closure gate scans it and fails on its
    # (entirely correct) module-scope `import Cython.Build`. The gate is right; the
    # file simply has no business being in the closure. Removing our own extras first
    # is what makes a rebuild idempotent rather than a second-run failure.
    for extra in ("setup_cy.py", "positions.jsonl"):
        p = bundle / extra
        if p.exists():
            p.unlink()
    build_dir = bundle / "build"          # setuptools scratch from a previous --inplace
    if build_dir.is_dir():
        shutil.rmtree(build_dir)

    # ---- 1. the champion bundle, via the Android sync (one file mapping) ----
    sys.path.insert(0, str(REPO / "android" / "tools"))
    import sync_python  # noqa: PLC0415

    summary = sync_python.sync(REPO, bundle)
    print(f"build_bundle: sync_python -> {summary['files']} files, "
          f"{summary['bytes'] / 1e6:.2f} MB, import gate OK "
          f"({summary['reachable']} modules reachable from android_bridge)")

    # ---- 2. the .pyx sources sync_python excludes (EXCLUDE_SUFFIXES) --------
    for name in PYX_SOURCES:
        src = REPO / "src" / "carcassonne_ai" / name
        if not src.is_file():
            raise SystemExit(f"build_bundle: missing {src}")
        shutil.copy2(src, bundle / "carcassonne_ai" / name)
    (bundle / "setup_cy.py").write_text(SETUP_CY)
    for name in TORCH_MODULES:
        src = REPO / "src" / "carcassonne_ai" / name
        if not src.is_file():
            raise SystemExit(f"build_bundle: missing {src}")
        shutil.copy2(src, bundle / "carcassonne_ai" / name)
    print(f"build_bundle: +{len(PYX_SOURCES)} .pyx sources + setup_cy.py "
          f"+ {len(TORCH_MODULES)} torch module(s) for the ANE probe")

    # ---- 3. positions ------------------------------------------------------
    sys.path.insert(0, str(SRC))
    import make_positions  # noqa: PLC0415

    rc = make_positions.main(["--out", str(bundle / "positions.jsonl"),
                              "-n", str(a.n_positions)])
    if rc != 0:
        raise SystemExit("build_bundle: make_positions failed")

    # ---- 4. the CL-067 checkpoint (optional-deps bench only) ---------------
    ckpt_record = None
    if not a.no_ckpt:
        found = resolve_ckpt()
        if found is not None:
            dest_dir = bundle / "net"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{found['entry']['id']}.pt"
            if not dest.is_file() or sha256(dest) != found["entry"]["sha256"]:
                shutil.copy2(found["path"], dest)
            got = sha256(dest)
            if got != found["entry"]["sha256"]:
                raise SystemExit(
                    f"build_bundle: checkpoint sha256 mismatch after copy\n"
                    f"  expected {found['entry']['sha256']}\n  got      {got}")
            ckpt_record = {
                "id": found["entry"]["id"],
                "claim": "CL-067",
                "source": str(found["path"]),
                "bundled_as": str(dest.relative_to(out)),
                "sha256": got,
                "sha256_verified": True,
                "arch": found["entry"]["arch"],
                "manifest": str(CKPT_MANIFEST.relative_to(REPO)),
            }
            print(f"build_bundle: +checkpoint {dest.name} "
                  f"({dest.stat().st_size / 1e6:.1f} MB, sha256 verified)")

    # ---- 5. the runnable scripts ------------------------------------------
    for name in TOP_LEVEL_FILES:
        src = SRC / name
        if not src.is_file():
            raise SystemExit(f"build_bundle: missing {src}")
        shutil.copy2(src, out / name)
        if name.endswith(".sh"):
            (out / name).chmod(0o755)
    (out / "results").mkdir(exist_ok=True)

    # ---- 6. provenance -----------------------------------------------------
    # Count only what SHIPS. A local verify run leaves a .venv and a results/ dir in
    # here; including them would make the manifest quote a ~235 MB payload for a
    # ~31 MB one, and the rsync in README_M5 excludes them for the same reason.
    skip_top = {".venv", "results", "results_m5", "__pycache__"}

    def _ships(q: Path) -> bool:
        rel = q.relative_to(out).parts
        return q.is_file() and not (set(rel) & skip_top)

    shipped = [q for q in out.rglob("*") if _ships(q)]
    n_files = len(shipped)
    n_bytes = sum(q.stat().st_size for q in shipped)
    manifest = {
        "schema": "carcassonne-m5-bench-build/v1",
        "built_from_repo": str(REPO),
        "git": git_rev(),
        "out": str(out),
        "sync_python": summary,
        "pyx_sources": list(PYX_SOURCES),
        "torch_modules_readded": list(TORCH_MODULES),
        "positions": {
            "file": "bundle/positions.jsonl",
            "n": a.n_positions,
            "corpus": str(make_positions.DEFAULT_CORPUS.relative_to(REPO)),
            "corpus_sha256": sha256(make_positions.DEFAULT_CORPUS),
        },
        "checkpoint": ckpt_record,
        "top_level_files": list(TOP_LEVEL_FILES),
        "totals": {"files": n_files, "bytes": n_bytes},
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"build_bundle: {n_files} files, {n_bytes / 1e6:.1f} MB total -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
