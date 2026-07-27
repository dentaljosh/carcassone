#!/usr/bin/env python3
"""Sync the on-device Python bundle from the repo into a destination directory.

ONE source of truth: there are NO checked-in copies of ``src/carcassonne_ai`` or
``engine/wingedsheep`` under ``android/``. The Gradle build invokes this script as a
``preBuild`` dependency so the APK always packages the CURRENT repo code — a stale
bundle is the single most likely way an on-device champion would silently differ from
the measured one.

Layout produced (the plan's table)::

    <out>/carcassonne_ai/**.py           <- src/carcassonne_ai   (no .pyx/.c/.so/__pycache__)
    <out>/carcassonne_ai/data/PRODUCTION.yaml
                                         <- governance/PRODUCTION.yaml
    <out>/wingedsheep/**                 <- engine/wingedsheep
                                            (no carcassonne_visualiser.py — it imports
                                             tkinter/PIL; no resources/images/** — the
                                             app ships its own upscaled assets)
    <out>/endgame_solver.py              <- scripts/level2/endgame_solver.py
    <out>/c5_leaf_override.py            <- scripts/classical_search/c5_leaf_override.py
    <out>/snapshot.py                    <- scripts/measurement_infra/snapshot.py

The three script modules are bundled TOP-LEVEL because that is exactly how the library
imports them: ``fair_agent._import_solver()`` does ``import endgame_solver`` and
``champion_factory._hashers()`` does ``from c5_leaf_override import _leaf_hash`` /
``from snapshot import _frozen_config_hash``. Their repo-path fallbacks (a
``sys.path.insert`` of a ``scripts/...`` dir that does not exist on device) are
harmless no-ops once the top-level modules resolve.

Idempotent: every destination entry this script owns is removed before the copy, so a
file deleted from the repo cannot survive in the bundle.

    python3 sync_python.py --repo <repo_root> --out <dest>
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# android/tools/sync_python.py -> parents[0]=tools, [1]=android, [2]=<repo root>
DEFAULT_REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT_REL = Path("android") / "app" / "build" / "python"

# Suffixes never copied (build artefacts / native extensions: Chaquopy cannot use a
# desktop-linux .so, and the .pyx/.c sources are dead weight).
EXCLUDE_SUFFIXES = {".pyx", ".c", ".so", ".pyc", ".pyd", ".o"}
EXCLUDE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".git", ".mypy_cache", "build", "dist"}

# Everything below <out> that this script owns (removed before each sync).
OWNED_ENTRIES = (
    "carcassonne_ai",
    "wingedsheep",
    "endgame_solver.py",
    "c5_leaf_override.py",
    "snapshot.py",
)

TOP_LEVEL_MODULES = (
    ("scripts/level2/endgame_solver.py", "endgame_solver.py"),
    ("scripts/classical_search/c5_leaf_override.py", "c5_leaf_override.py"),
    ("scripts/measurement_infra/snapshot.py", "snapshot.py"),
)

PRODUCTION_YAML_SRC = "governance/PRODUCTION.yaml"
PRODUCTION_YAML_DEST = Path("carcassonne_ai") / "data" / "PRODUCTION.yaml"


def _skip_dir(rel: Path) -> bool:
    return any(part in EXCLUDE_DIR_NAMES for part in rel.parts)


def _copy_tree(src: Path, dest: Path, *, skip: callable) -> int:
    """Copy ``src`` -> ``dest`` recursively; ``skip(rel_path)`` decides exclusions.

    Returns the number of files written."""
    n = 0
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if _skip_dir(rel.parent) or (path.is_dir() and _skip_dir(rel)):
            continue
        if path.is_dir():
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        if skip(rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
    return n


def _skip_carcassonne_ai(rel: Path) -> bool:
    # Nothing extra beyond the global suffix/dir rules; the data/ dir is generated
    # below and must not be shadowed by a repo file of the same name.
    return rel.parts[:1] == ("data",)


def _skip_wingedsheep(rel: Path) -> bool:
    if rel.name == "carcassonne_visualiser.py":
        return True          # tkinter + PIL; only reachable via visualize=True
    parts = rel.parts
    for i in range(len(parts) - 1):
        if parts[i] == "resources" and parts[i + 1] == "images":
            return True      # ~2 MB of tile art; the app ships upscaled copies
    return False


def sync(repo: Path, out: Path) -> dict:
    """Do the sync. Returns a summary dict (also used by tests)."""
    repo = Path(repo).resolve()
    out = Path(out).resolve()

    src_pkg = repo / "src" / "carcassonne_ai"
    engine_pkg = repo / "engine" / "wingedsheep"
    prod_yaml = repo / PRODUCTION_YAML_SRC
    missing = [str(p) for p in (src_pkg, engine_pkg, prod_yaml) if not p.exists()]
    for rel, _ in TOP_LEVEL_MODULES:
        if not (repo / rel).exists():
            missing.append(str(repo / rel))
    if missing:
        raise SystemExit(
            "sync_python: missing repo source(s):\n  " + "\n  ".join(missing) +
            f"\n(--repo resolved to {repo})")

    if out == repo:
        raise SystemExit("sync_python: refusing to sync into the repo root")

    # Idempotency: drop only what we own, so a hand-written file next to the bundle
    # (or the Kotlin build's own outputs) survives.
    for entry in OWNED_ENTRIES:
        target = out / entry
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    out.mkdir(parents=True, exist_ok=True)

    n_ai = _copy_tree(src_pkg, out / "carcassonne_ai", skip=_skip_carcassonne_ai)
    n_engine = _copy_tree(engine_pkg, out / "wingedsheep", skip=_skip_wingedsheep)

    n_top = 0
    for rel, name in TOP_LEVEL_MODULES:
        shutil.copy2(repo / rel, out / name)
        n_top += 1

    yaml_dest = out / PRODUCTION_YAML_DEST
    yaml_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prod_yaml, yaml_dest)
    # `carcassonne_ai.data` is a plain data dir, but shipping an __init__.py keeps
    # Chaquopy's extractPackages/importer from treating it as a namespace oddity.
    (yaml_dest.parent / "__init__.py").write_text(
        '"""Bundled data (PRODUCTION.yaml) — written by android/tools/sync_python.py."""\n')

    n_files = n_ai + n_engine + n_top + 2
    n_bytes = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    return {
        "out": str(out), "repo": str(repo),
        "carcassonne_ai": n_ai, "wingedsheep": n_engine,
        "top_level": n_top, "files": n_files, "bytes": n_bytes,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sync_python",
        description="Copy the on-device Python bundle from the repo into <out>.")
    p.add_argument("--repo", type=Path, default=DEFAULT_REPO,
                   help=f"repo root (default: {DEFAULT_REPO})")
    p.add_argument("--out", type=Path, default=None,
                   help=f"destination dir (default: <repo>/{DEFAULT_OUT_REL})")
    a = p.parse_args(argv)
    out = a.out if a.out is not None else Path(a.repo) / DEFAULT_OUT_REL
    s = sync(a.repo, out)
    print(f"sync_python: {s['files']} files, {s['bytes'] / 1e6:.2f} MB -> {s['out']} "
          f"(carcassonne_ai={s['carcassonne_ai']}, wingedsheep={s['wingedsheep']}, "
          f"top_level={s['top_level']}, PRODUCTION.yaml=1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
