"""Self-describing run manifests + provenance stamps for eval/self-play runs.

Closes REVIEW_LOG D21 ("no manifests"): every eval writes a `manifest.json` into its
output dir capturing the *resolved* config + provenance (game ruleset, git code-rev,
host, timestamp, relevant CARCASSONNE_V25_* leaf knobs). This is what lets a
results.csv row be GENERATED from the manifest (see scripts/append_result_row.py)
instead of hand-typed — so a row can never drift from the era/code that produced it
(the +181.7-River vs +25.2-base conflation that motivated this).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# leaf/scoring knobs that change results and so belong in provenance.
# (Expanded 2026-06-07 for the clean-eval audit: RESIDUAL_SCALE/OPP_CAP/etc. were
# silent before, so a residual run left no env trace — see outside-review R1/R7.)
_LEAF_ENV_KEYS = (
    "CARCASSONNE_V25_CAP",
    "CARCASSONNE_V25_DROP_THREE_OPEN",
    "CARCASSONNE_V25_VALUE_BLEND",
    "CARCASSONNE_V25_RESIDUAL_SCALE",
    "CARCASSONNE_V25_OPP_CAP",
    "CARCASSONNE_V25_MEEPLE_K",
    "CARCASSONNE_V25_TILE_COUNTING",
    "CARCASSONNE_V25_CLOSURE_SLACK",
    "CARCASSONNE_V25_ONE_OPEN_ONLY",
    "CARC_RUN",
)


def code_rev() -> str:
    """git short hash of the working tree, or 'unknown' if git is unavailable."""
    try:
        repo = Path(__file__).resolve().parents[2]
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        rev = out.stdout.strip()
        if rev and out.returncode == 0:
            # mark dirty trees so a row can't claim a clean commit it wasn't run at
            dirty = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            return rev + ("-dirty" if dirty else "")
    except Exception:
        pass
    return "unknown"


def game_tag(tile_sets) -> str:
    """'river' if THE_RIVER is in the ruleset, else 'base'. Accepts a Game, a tuple
    of TileSet, or an iterable of names."""
    if hasattr(tile_sets, "tile_sets"):  # a Game object
        tile_sets = tile_sets.tile_sets
    names = []
    for t in tile_sets:
        names.append(getattr(t, "name", str(t)).upper())
    return "river" if any("RIVER" in n for n in names) else "base"


def leaf_env() -> dict:
    return {k: os.environ.get(k) for k in _LEAF_ENV_KEYS if os.environ.get(k) is not None}


def rules_profile_block() -> dict:
    """The resolved F9 rules profile in force in THIS process (spec A0)."""
    from .rules_profile import active

    return active().as_manifest()


def write_manifest(out_dir, *, kind: str, game: str, config: dict,
                   overwrite: bool = False, evaluator: dict | None = None) -> Path:
    """Write <out_dir>/manifest.json with resolved config + provenance.

    Skips if a manifest already exists (so racing multi-box --shared-claim workers
    don't clobber each other) unless overwrite=True. Returns the manifest path.

    `evaluator` (optional): the structured both-sides provenance block from
    `eval_provenance.build_eval_provenance` (checkpoint SHA256, full commit, argv,
    per-side leaf/value config, runtime-verified counters). Stored verbatim under
    manifest["evaluator"]. Absent for legacy callers (back-compat).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mpath = out_dir / "manifest.json"
    if mpath.exists() and not overwrite:
        return mpath
    manifest = {
        "kind": kind,
        "game": game,
        "code_rev": code_rev(),
        "host": socket.gethostname(),
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "leaf_env": leaf_env(),
        # F9 A0: the resolved rules profile, verbatim, in EVERY manifest — the
        # spec's fail-loud requirement (an unstamped or partially-applied profile
        # is precisely the failure F9 exists to detect). Under the default this
        # reads `walled`, which is what makes "every elo we have measured is a
        # walled number" a machine-checkable statement instead of a remembered one.
        "rules_profile": rules_profile_block(),
        "config": config,
    }
    if evaluator is not None:
        manifest["evaluator"] = evaluator
    tmp = out_dir / f".manifest.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(manifest, indent=2, default=str))
    tmp.replace(mpath)  # atomic
    return mpath


def patch_manifest(out_dir, key: str, value) -> Path | None:
    """Merge one top-level key into an EXISTING manifest, atomically.

    Written for the F9 W4 sentinel aggregate, which only exists once the games
    have been played, while the manifest is (correctly) written before the first
    one. Read-modify-write of a single key, never a rewrite of the config block —
    so a racing ``--shared-claim`` peer can at worst lose its own aggregate, and
    can never corrupt the provenance the manifest was written for.

    Returns the path, or None if there is no manifest to patch.
    """
    out_dir = Path(out_dir)
    mpath = out_dir / "manifest.json"
    if not mpath.exists():
        return None
    try:
        manifest = json.loads(mpath.read_text())
    except Exception:
        return None
    manifest[key] = value
    tmp = out_dir / f".manifest.{os.getpid()}.patch.tmp"
    tmp.write_text(json.dumps(manifest, indent=2, default=str))
    tmp.replace(mpath)
    return mpath
