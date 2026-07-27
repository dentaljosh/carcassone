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
import ast
import shutil
import sys
from pathlib import Path

# android/tools/sync_python.py -> parents[0]=tools, [1]=android, [2]=<repo root>
DEFAULT_REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT_REL = Path("android") / "app" / "build" / "python"

# The hand-written bridge lives in the Chaquopy `main` source set, NOT in <out>; the
# APK merges the two. The import gate must see both to have the real closure.
BRIDGE_SRC_REL = Path("android") / "app" / "src" / "main" / "python"

# The ONLY third-party distributions the APK installs (app/build.gradle.kts `pip`).
#
# `carc_cy` (the prebuilt Cython fast-path wheels) is deliberately NOT listed, and adding
# it would be dead weight. The gate only ever reports on MODULE-SCOPE imports
# (`_ImportVisitor._record` records into `required` only at `_depth == 0`), and every
# reference to the compiled modules is inside a function body:
#   * flat_leaf.py   `from . import flat_leaf_cy`        -> inside flat_virtual_score_v2
#   * board_repr.py  `from .flat_repr_cy import ...`     -> inside encode_board
#   * android_bridge `importlib.import_module("carc_cy.…")` -> inside _install_cy_aliases
# So the closure never sees them and the gate cannot fail on them. That is the correct
# outcome for a genuinely OPTIONAL accelerator: both call sites catch ImportError and
# cache a pure-Python fallback, so a build with no wheels is still correct.
ALLOWED_EXTERNAL = {"numpy", "yaml"}

# The entry point the on-device app actually imports. Reachability is computed from it.
BUNDLE_ENTRY = "android_bridge"

# The neural cluster: every module that needs torch, plus everything that imports one
# of them at module scope (the set is closed under that relation — the import gate
# below fails loudly if it stops being).
#
# Excluded because the production champion is CLASSICAL. The only paths that reach
# these modules are `heuristic_prior_mcts`'s `elif net is not None:` / `handles is not
# None:` branches, and the bridge never supplies a net or SHM handles, so they are dead
# on device. Shipping them was ~8 modules of latent `ImportError: torch` waiting for
# the first code change that made one reachable.
#
# This list is deliberately HAND-DECLARED rather than inferred. The justification is
# semantic ("no net is ever passed"), not structural: `fair_agent` — which the champion
# absolutely needs — is *also* only reached through a lazy import, so "unreachable at
# module scope" is not on its own a safe licence to delete anything.
EXCLUDE_MODULES = (
    "eval_server.py",
    "eval_server_pool.py",
    "evaluators.py",
    "network.py",
    "remote_eval_bridge.py",
    "remote_evaluators.py",
    "remote_socket_handles.py",
    "shm_eval_handles.py",
    "step2_leaf.py",
)

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
    # The data/ dir is generated below and must not be shadowed by a repo file of the
    # same name; EXCLUDE_MODULES is the torch cluster (see its comment).
    if rel.parts[:1] == ("data",):
        return True
    return len(rel.parts) == 1 and rel.name in EXCLUDE_MODULES


def _skip_wingedsheep(rel: Path) -> bool:
    if rel.name == "carcassonne_visualiser.py":
        return True          # tkinter + PIL; only reachable via visualize=True
    parts = rel.parts
    for i in range(len(parts) - 1):
        if parts[i] == "resources" and parts[i + 1] == "images":
            return True      # ~2 MB of tile art; the app ships upscaled copies
    return False


# --------------------------------------------------------------------------- #
# Import-closure gate                                                           #
#                                                                               #
# The failure it exists to catch: a module reaches the APK whose MODULE-SCOPE   #
# imports cannot be satisfied on device (torch, matplotlib, ...). Desktop tests #
# stay green because the repo venv has those installed; the phone does not, and #
# the ImportError only appears the first time something imports it for real.    #
#                                                                               #
# Imports inside function bodies are exempt by design — that is precisely the   #
# lazy-import idiom the library already uses (`fair_agent._import_solver`), and #
# such an import costs nothing unless the code path runs.                       #
# --------------------------------------------------------------------------- #
def _module_name(rel: Path) -> str:
    """Bundle-relative .py path -> dotted module name."""
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _bundle_modules(roots: list[Path]) -> dict[str, Path]:
    """Every importable module across the bundle roots: dotted name -> file."""
    mods: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root)
            if _skip_dir(rel.parent):
                continue
            name = _module_name(rel)
            if name:
                mods.setdefault(name, path)
    return mods


class _ImportVisitor(ast.NodeVisitor):
    """Collect imports, split by whether they execute at module import time.

    Module scope includes class bodies and module-level ``try``/``if`` blocks (all of
    which run on import); it excludes function bodies and ``if TYPE_CHECKING:`` guards
    (which do not).

    Two sets are kept per scope because they answer different questions:

    ``required``   targets that MUST be importable — the full dotted name of an
                   ``import a.b.c``, and the ``X`` of ``from X import ...``.
    ``candidates`` dotted names that MIGHT name a module, used for the dependency
                   graph. ``from X import n`` is ambiguous in the AST — ``n`` may be a
                   submodule or just a name — so ``X.n`` is a candidate edge but never
                   a requirement.
    """

    def __init__(self, module: str) -> None:
        self.module = module
        self.pkg = module.rsplit(".", 1)[0] if "." in module else ""
        self.required: set[str] = set()
        self.candidates: set[str] = set()
        self.any_candidates: set[str] = set()
        self._depth = 0                       # >0 == inside a function body

    # Function bodies are deferred: descend, but record only into `any_candidates`.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef   # type: ignore[assignment]

    def visit_If(self, node: ast.If) -> None:
        # `if TYPE_CHECKING:` bodies never execute at runtime; the orelse still does.
        if _is_type_checking_test(node.test):
            self._depth += 1
            for child in node.body:
                self.visit(child)
            self._depth -= 1
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def _record(self, target: str, *, required: bool) -> None:
        if not target:
            return
        self.any_candidates.add(target)
        if self._depth == 0:
            self.candidates.add(target)
            if required:
                self.required.add(target)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name, required=True)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            base = self.pkg.split(".") if self.pkg else []
            # level 1 == current package; each extra level strips one more component.
            trimmed = base[: len(base) - (node.level - 1)] if node.level > 1 else base
            target = ".".join([*trimmed, node.module] if node.module else trimmed)
        else:
            target = node.module or ""
        self._record(target, required=True)
        for alias in node.names:
            if alias.name != "*":
                self._record(f"{target}.{alias.name}", required=False)


def _is_type_checking_test(test: ast.expr) -> bool:
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _resolves(target: str, mods: dict[str, Path]) -> bool:
    """Is this import target satisfiable on device?

    Strict inside the bundle: once the ROOT package is one we ship, the FULL dotted
    name has to be a module we ship. (A lenient root-only check would happily pass
    ``from carcassonne_ai.network import ...`` after network.py had been excluded —
    exactly the class of breakage this gate exists to catch.)"""
    if target in mods:
        return True
    root = target.split(".")[0]
    if root in mods:
        return False
    return root in ALLOWED_EXTERNAL or root in sys.stdlib_module_names


def check_imports(roots: list[Path]) -> dict:
    """Analyse the bundle's import closure. Pure — makes no changes.

    Returns ``{modules, reachable, violations, unreachable, prunable}`` where
    ``violations`` maps a module to the module-scope imports that cannot resolve."""
    mods = _bundle_modules(roots)
    parsed: dict[str, _ImportVisitor] = {}
    for name, path in mods.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue                          # not importable anyway; nothing to gate
        v = _ImportVisitor(name)
        v.visit(tree)
        parsed[name] = v

    # Reachable set: BFS from the entry point over MODULE-SCOPE imports only.
    # `import a.b.c` executes a and a.b too, so every prefix is an edge.
    def _edges(targets: set[str]) -> set[str]:
        out: set[str] = set()
        for target in targets:
            parts = target.split(".")
            for i in range(1, len(parts) + 1):
                prefix = ".".join(parts[:i])
                if prefix in parsed:
                    out.add(prefix)
        return out

    def _bfs(attr: str) -> set[str]:
        seen: set[str] = set()
        queue = [BUNDLE_ENTRY] if BUNDLE_ENTRY in parsed else []
        while queue:
            cur = queue.pop()
            if cur in seen:
                continue
            seen.add(cur)
            queue.extend(_edges(getattr(parsed[cur], attr)) - seen)
        return seen

    # Two reachability notions, and the difference between them matters:
    #   reachable      — module-scope imports only == what actually runs on `import
    #                    android_bridge`. This is the set the gate reports on.
    #   reachable_any  — lazy imports included == what could EVER be needed. Used for
    #                    the warn-list, because plenty of load-bearing modules
    #                    (`fair_agent`, `endgame_solver`) are only ever imported
    #                    inside a function and must not be mistaken for dead weight.
    reachable = _bfs("candidates")
    reachable_any = _bfs("any_candidates")

    violations = {
        name: sorted(t for t in v.required if not _resolves(t, mods))
        for name, v in parsed.items()
    }
    violations = {k: v for k, v in violations.items() if v}

    return {
        "modules": sorted(mods),
        "reachable": sorted(reachable),
        "reachable_any": sorted(reachable_any),
        "violations": violations,
        "unreachable": sorted(set(mods) - reachable_any),
        "paths": mods,
    }


def enforce_imports(roots: list[Path], **_ignored) -> dict:
    """Run the gate: raise SystemExit unless the whole bundle's module-scope import
    closure resolves to {bundle modules, stdlib} | ALLOWED_EXTERNAL.

    A pure check — it never deletes anything. Deciding that a module is dead weight is
    a semantic judgement (see EXCLUDE_MODULES), not something reachability can settle:
    ``fair_agent`` is unreachable at module scope and utterly essential."""
    report = check_imports(roots)
    bad = report["violations"]
    if bad:
        live = set(report["reachable"])
        lines = [
            "sync_python: import-closure gate FAILED.",
            "",
            "These bundled modules import something at MODULE SCOPE that will not",
            "exist on device (allowed: bundle modules, stdlib, "
            f"{', '.join(sorted(ALLOWED_EXTERNAL))}):",
            "",
        ]
        for name in sorted(bad):
            where = ("imported on start-up" if name in live
                     else "not imported on start-up, but shipped")
            lines.append(f"  {name}  [{where}]")
            for target in bad[name]:
                lines.append(f"      import {target}")
        lines += [
            "",
            "Fix by making the import lazy (move it inside the function that needs",
            "it), adding the module to EXCLUDE_MODULES in this file, or adding the",
            "dependency to the chaquopy `pip` block in android/app/build.gradle.kts.",
        ]
        raise SystemExit("\n".join(lines))
    return report


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

    # Post-sync gate: nothing reaches the APK whose module-scope imports cannot be
    # satisfied on device. Runs against the bundle AS SHIPPED (generated dir + the
    # hand-written bridge source set), and may delete unreferenced dead modules.
    gate = enforce_imports([out, repo / BRIDGE_SRC_REL])
    n_files = n_ai + n_engine + n_top + 2
    n_bytes = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    return {
        "out": str(out), "repo": str(repo),
        "carcassonne_ai": n_ai, "wingedsheep": n_engine,
        "top_level": n_top, "files": n_files, "bytes": n_bytes,
        "reachable": len(gate["reachable"]),
        "unreachable": gate["unreachable"],
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
    print(f"sync_python: import gate OK — {s['reachable']} modules imported on "
          f"start-up from {BUNDLE_ENTRY}")
    unreachable = s["unreachable"]
    if unreachable:
        # Advisory only: dead weight in the APK, not a correctness problem. Anything
        # here is unreachable even counting lazy imports.
        print(f"sync_python: {len(unreachable)} module(s) ship without any import path "
              f"from {BUNDLE_ENTRY}:\n  " + "\n  ".join(unreachable))
    return 0


if __name__ == "__main__":
    sys.exit(main())
