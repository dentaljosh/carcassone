"""Phase-B: tests for the training-provenance stamp (governance/CHECKPOINT_LINEAGE gap fix)."""
from __future__ import annotations

from carcassonne_ai.train_provenance import (
    TRAIN_PROVENANCE_SCHEMA_ID,
    UNKNOWN,
    build_training_provenance,
    dataset_fingerprint,
)


def _mk(tmp_path, name, nbytes):
    p = tmp_path / name
    p.write_bytes(b"x" * nbytes)
    return p


def test_dataset_fingerprint_deterministic_and_order_independent(tmp_path):
    a = _mk(tmp_path, "iter_01_g0.npz", 10)
    b = _mk(tmp_path, "iter_02_g1.npz", 20)
    f1 = dataset_fingerprint([a, b])
    f2 = dataset_fingerprint([b, a])  # different order, same set
    assert f1["fingerprint"] == f2["fingerprint"]
    assert f1["n_files"] == 2
    assert f1["total_bytes"] == 30
    assert f1["replay_iters"] == [1, 2]


def test_dataset_fingerprint_changes_with_content_set(tmp_path):
    a = _mk(tmp_path, "iter_01_g0.npz", 10)
    b = _mk(tmp_path, "iter_01_g1.npz", 20)
    c = _mk(tmp_path, "iter_01_g1.npz".replace("g1", "g2"), 20)
    assert dataset_fingerprint([a, b])["fingerprint"] != dataset_fingerprint([a, c])["fingerprint"]


def test_replay_iters_parsed_from_paths(tmp_path):
    files = [_mk(tmp_path, f"iter_{i:02d}_g.npz", 5) for i in (3, 7, 3, 11)]
    assert dataset_fingerprint(files)["replay_iters"] == [3, 7, 11]


def test_build_provenance_captures_trainer_visible_fields(tmp_path):
    parent = _mk(tmp_path, "warm.pt", 100)
    files = [_mk(tmp_path, "iter_05_g0.npz", 10), _mk(tmp_path, "iter_05_g1.npz", 10)]
    prov = build_training_provenance(
        out_path=tmp_path / "iter_06.pt",
        warm_from=parent,
        file_list=files,
        buffer_files=files,  # no warmstart mix
        n_filters=96, n_blocks=6, value_global_pool=False, n_scalar_features=12,
        iter_idx=6,
        argv=["--iter", "6", "--warm-from", str(parent)],
        loss_weights={"value": 3.0, "aux": 0.15, "rank": 0.0, "center": 0.0},
        aux_heads=["ownership"],
    )
    assert prov["schema"] == TRAIN_PROVENANCE_SCHEMA_ID
    assert prov["created_iter"] == 6
    assert prov["code_commit"]  # a real sha or "unknown"
    assert isinstance(prov["dirty"], bool)
    assert prov["parent_ckpt"]["path"] == str(parent)
    assert len(prov["parent_ckpt"]["sha256"]) == 64  # real file -> real hash
    assert prov["arch"] == {"n_filters": 96, "n_blocks": 6,
                            "value_global_pool": False, "n_scalar_features": 12}
    assert prov["train_command"] == ["--iter", "6", "--warm-from", str(parent)]
    assert prov["dataset"]["replay_iters"] == [5]
    assert prov["dataset"]["n_warmstart_files"] == 0
    assert prov["loss_weights"]["value"] == 3.0
    assert prov["aux_heads"] == ["ownership"]


def test_selfplay_only_fields_default_to_unknown_at_train(tmp_path):
    files = [_mk(tmp_path, "iter_00_g.npz", 4)]
    prov = build_training_provenance(
        out_path=tmp_path / "o.pt", warm_from=None, file_list=files, buffer_files=files,
        n_filters=96, n_blocks=6, value_global_pool=False, n_scalar_features=12,
        iter_idx=0, argv=[], loss_weights={},
    )
    assert prov["value_target"] == UNKNOWN
    assert prov["selfplay_leaf"] == UNKNOWN
    assert prov["selfplay_seed_range"] == UNKNOWN
    assert prov["parent_ckpt"]["path"] is None
    assert prov["parent_ckpt"]["sha256"] is None  # no parent -> no hash


def test_passed_through_selfplay_tags_are_recorded(tmp_path):
    files = [_mk(tmp_path, "iter_00_g.npz", 4)]
    prov = build_training_provenance(
        out_path=tmp_path / "o.pt", warm_from=None, file_list=files, buffer_files=files,
        n_filters=96, n_blocks=6, value_global_pool=False, n_scalar_features=12,
        iter_idx=0, argv=[], loss_weights={},
        value_target="residual", selfplay_leaf="v2_7+residual",
        selfplay_seed_range="0-399", run_tag="flywheel_residual",
    )
    assert prov["value_target"] == "residual"
    assert prov["selfplay_leaf"] == "v2_7+residual"
    assert prov["selfplay_seed_range"] == "0-399"
    assert prov["run_tag"] == "flywheel_residual"
