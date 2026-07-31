"""Shared plumbing for the G0 reconcile scripts (rustport phase P0).

Every gate script writes a self-describing JSON result next to
``measurement/rustport_p0/`` and prints ONE verdict line of the form::

    G0/<primitive>: PASS  ... details ...
    G0/<primitive>: FAIL  ... details ...

so a `grep '^G0/'` over the logs reconstructs the gate without re-running it.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUTDIR = REPO / "measurement" / "rustport_p0"


def _git_rev() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=20,
        )
        rev = out.stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(REPO), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return rev + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def environment() -> dict:
    """The provenance block every G0 result carries."""
    env = {
        "host": platform.node(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "python_impl": platform.python_implementation(),
        "git_rev": _git_rev(),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        import numpy as np

        env["numpy"] = np.__version__
    except Exception:
        env["numpy"] = None
    try:
        import carc_rs

        env["carc_rs"] = carc_rs.__version__
        env["carc_rs_file"] = getattr(carc_rs, "__file__", None)
    except Exception as exc:  # pragma: no cover
        env["carc_rs"] = f"IMPORT FAILED: {exc}"
    try:
        env["libc"] = " ".join(platform.libc_ver())
    except Exception:
        env["libc"] = None
    return env


def write_result(name: str, payload: dict) -> Path:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    payload = {"gate": f"G0/{name}", "env": environment(), **payload}
    path = OUTDIR / f"G0_{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=False, default=str))
    return path


def verdict(name: str, ok: bool, detail: str, path: Path) -> int:
    print(f"G0/{name}: {'PASS' if ok else 'FAIL'}  {detail}")
    print(f"G0/{name}: result -> {path}")
    return 0 if ok else 1


def require_carc_rs():
    try:
        import carc_rs  # noqa: F401
    except ImportError:
        sys.exit(
            "carc_rs is not importable. Build the dev wheel first:\n"
            "  .venv/bin/maturin develop --release "
            "--manifest-path rust/carc/carc-py/Cargo.toml"
        )
    return sys.modules["carc_rs"]
