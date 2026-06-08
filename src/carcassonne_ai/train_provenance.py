"""Training-time provenance stamp — the Phase-B fix for the ``unknown@train`` gap.

The checkpoint-lineage audit (governance/CHECKPOINT_LINEAGE.csv) found that NO
checkpoint persisted its training dataset, code commit, or seed ranges — they were
unrecoverable after the fact. This module builds a ``provenance`` dict that is
stamped INTO the checkpoint .pt (and its .metrics.json) at save time, so every
future checkpoint carries its own lineage. The dict mirrors the lineage-CSV
columns so `governance/CHECKPOINT_LINEAGE.csv` can be auto-appended from a ckpt.

Pure metadata: importing/using this NEVER changes training behavior. Fields that
are genuinely a self-play (generation-side) property and not visible to the
trainer are marked ``unknown@train`` unless the caller passes them through (the
cluster loop knows them); the load-bearing trainer-visible fields (code commit,
dirty, parent checkpoint + sha, the exact train command, the dataset file set +
fingerprint, replay iters, loss weights, arch) are always captured.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .eval_provenance import git_commit_and_dirty, sha256_file

TRAIN_PROVENANCE_SCHEMA_ID = "carcassonne-training-provenance/v1"
UNKNOWN = "unknown@train"

_ITER_RE = re.compile(r"iter[_-]?(\d+)")


def _iter_of(path) -> int | None:
    m = _ITER_RE.search(str(path))
    return int(m.group(1)) if m else None


def dataset_fingerprint(files) -> dict:
    """Cheap, deterministic identity of a training dataset (NO content read).

    Uses each file's basename + byte size — uniquely identifies the dataset set
    without hashing GBs of .npz (content-hashing is the stronger, optional upgrade
    noted in TRAINING_OBSERVABILITY_SPEC.md). Returns the fingerprint, file count,
    total bytes, the (capped) basename list, and the replay iter indices present.
    """
    items = []
    total = 0
    iters: set[int] = set()
    for f in files:
        p = Path(f)
        try:
            size = p.stat().st_size
        except OSError:
            size = -1
        total += max(size, 0)
        items.append((p.name, size))
        it = _iter_of(p)
        if it is not None:
            iters.add(it)
    items.sort()
    h = hashlib.sha256()
    for name, size in items:
        h.update(f"{name}:{size}\n".encode())
    return {
        "fingerprint": h.hexdigest()[:16],
        "n_files": len(items),
        "total_bytes": total,
        "replay_iters": sorted(iters),
        "files": [n for n, _ in items[:64]],  # cap the list; fingerprint covers all
        "files_truncated": len(items) > 64,
    }


def build_training_provenance(
    *,
    out_path,
    warm_from,
    file_list,
    buffer_files,
    n_filters: int,
    n_blocks: int,
    value_global_pool: bool,
    n_scalar_features: int,
    iter_idx: int,
    argv,
    loss_weights: dict,
    aux_heads: list | None = None,
    ruleset: str = "base",
    value_target: str | None = None,
    selfplay_leaf: str | None = None,
    selfplay_seed_range: str | None = None,
    run_tag: str | None = None,
) -> dict:
    """Assemble the provenance block stamped into a training checkpoint.

    Trainer-visible fields are captured directly; self-play-only fields
    (value_target, selfplay_leaf, selfplay_seed_range) fall back to ``unknown@train``
    unless the caller passes them (the cluster loop does).
    """
    commit, dirty = git_commit_and_dirty()
    ds = dataset_fingerprint(file_list)
    n_warmstart = max(len(file_list) - len(buffer_files), 0)
    return {
        "schema": TRAIN_PROVENANCE_SCHEMA_ID,
        "created_iter": iter_idx,
        "code_commit": commit,
        "dirty": dirty,
        "ruleset": ruleset,
        "parent_ckpt": {
            "path": str(warm_from) if warm_from else None,
            "sha256": sha256_file(warm_from),
        },
        "arch": {
            "n_filters": n_filters,
            "n_blocks": n_blocks,
            "value_global_pool": bool(value_global_pool),
            "n_scalar_features": n_scalar_features,
        },
        "train_command": list(argv) if argv is not None else None,
        "dataset": {**ds, "n_warmstart_files": n_warmstart},
        "policy_target": "mcts_visit_distribution",
        "value_target": value_target or UNKNOWN,
        "loss_weights": dict(loss_weights),
        "aux_heads": list(aux_heads or []),
        "selfplay_leaf": selfplay_leaf or UNKNOWN,
        "selfplay_seed_range": selfplay_seed_range or UNKNOWN,
        "run_tag": run_tag,
    }


# Provenance-only CLI flags a trainer can expose so the cluster loop can pass the
# self-play-side facts through. Kept here so train_iter.py and train_warmstart.py
# add an identical, behavior-free set.
def add_provenance_args(parser) -> None:
    g = parser.add_argument_group("provenance (metadata only; no behavior change)")
    g.add_argument("--prov-value-target", default=None,
                   help="Self-play value target tag (e.g. wl/score_diff/residual/search_value). "
                        "Recorded in the checkpoint provenance; unknown@train if omitted.")
    g.add_argument("--prov-selfplay-leaf", default=None,
                   help="Leaf evaluator used during the self-play that produced this data "
                        "(e.g. v2_7, v2_7+residual). Provenance only.")
    g.add_argument("--prov-seed-range", default=None,
                   help="Self-play seed range that generated the training data, e.g. '0-399'. "
                        "Provenance only (the trainer cannot see it).")
    g.add_argument("--prov-run-tag", default=None,
                   help="Free-form run label (e.g. flywheel_residual). Provenance only.")
