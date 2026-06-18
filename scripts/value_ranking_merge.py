"""Merge value-ranking dataset shards (Phase 4B) into one, offsetting group_id so groups
stay unique while game_seed (the leakage-split key) is preserved verbatim. Shards must come
from DIFFERENT --seed bands (distinct games) so the by-game split stays clean.

  python scripts/value_ranking_merge.py OUT_DIR SHARD1 SHARD2 [SHARD3 ...]
"""
import json, sys
from pathlib import Path
import numpy as np

out = Path(sys.argv[1]); shards = [Path(p) for p in sys.argv[2:]]
out.mkdir(parents=True, exist_ok=True)
A = {k: [] for k in ("child_obs", "child_scalars", "oracle_q", "group_id", "game_seed", "ply", "k")}
gid_off = 0; metas = []
for sh in shards:
    z = np.load(sh / "rows.npz"); metas.append(json.loads((sh / "meta.json").read_text()))
    for k in A:
        v = z["group_id"] + gid_off if k == "group_id" else z[k]
        A[k].append(v)
    gid_off = int(np.concatenate(A["group_id"]).max()) + 1
M = {k: np.concatenate(v) for k, v in A.items()}
np.savez_compressed(out / "rows.npz", **M)
meta = {
    "merged_from": [str(s) for s in shards],
    "n_rows": int(M["oracle_q"].shape[0]),
    "n_groups": int(len(np.unique(M["group_id"]))),
    "n_games": int(len(np.unique(M["game_seed"]))),
    "obs_shape": list(M["child_obs"].shape[1:]), "n_scalar": int(M["child_scalars"].shape[1]),
    "checkpoint_sha256": metas[0].get("checkpoint_sha256"),
    "shard_metas": metas,
    "leakage_policy": "split by game_seed; shards from distinct seed bands; group_id offset per shard",
}
(out / "meta.json").write_text(json.dumps(meta, indent=2))
print(f"merged {len(shards)} shards -> {meta['n_rows']} rows / {meta['n_groups']} groups / "
      f"{meta['n_games']} games -> {out}/rows.npz")
