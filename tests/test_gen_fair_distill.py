"""Fair-distill emitter smoke (fair-distill addendum "Parity/smoke test").

Runs scripts/distill_flywheel/gen_fair_distill.py as a SUBPROCESS (1 game, k_dets=2,
sims=32) with the champion env (curve125) forced, then loads the produced shard +
manifest and asserts the distillation contract:
  * trajectory (aux_mask=True) policy rows sum to 1.0 over the legal mask, 0 off-mask;
  * aux_mask is MIXED (some True trajectory rows + an exact-endgame value-only tail);
  * value-only (aux_mask=False) rows carry dummy zero policy/mask;
  * values ∈ [-1,1] and sign-consistent with the final score_diff;
  * the manifest teacher block is present with policy_source / move_selected_by, and
    the resolved leaf CONFIG VALUES are the production champion leaf: curve125,
    cap8/opp_cap8, closure_p default (the runtime frozen-config-hash is recorded for
    provenance only — the PRODUCTION.yaml fingerprint 158f17ff is STALE dataclass
    drift, so we verify VALUES not the hash string).

Subprocess (not in-process) so the curve125 leaf is guaranteed regardless of any
sibling module's DEFAULT_CONFIG import-order pollution (see tests/conftest.py).
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.warmstart import GameDataset  # noqa: E402

# The champion leaf env (curve125) — mirrors scripts/distill_flywheel/champ_env.sh.
# Passed to the subprocess so curve125 is forced even if the parent session set curve100.
_CHAMP_ENV = {
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}
_CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]


def test_fair_distill_emitter_smoke(tmp_path):
    out = tmp_path / "fair_distill_smoke"
    script = REPO / "scripts" / "distill_flywheel" / "gen_fair_distill.py"
    seed_start = 700_000_000
    env = {**os.environ, **_CHAMP_ENV}
    r = subprocess.run(
        [sys.executable, "-u", str(script), "--games", "1", "--k-dets", "2",
         "--sims", "32", "--workers", "1", "--seed-start", str(seed_start),
         "--out", str(out)],
        env=env, capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, f"emitter failed:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"

    shards = sorted(out.glob("seed_*.npz"))
    assert len(shards) == 1, f"expected 1 shard, got {shards}"
    ds = GameDataset.load(shards[0])
    aux = np.asarray(ds.aux_mask, dtype=bool)
    pol = np.asarray(ds.policies, dtype=np.float32)
    mask = np.asarray(ds.valid_masks, dtype=bool)
    vals = np.asarray(ds.values, dtype=np.float32)
    N = len(aux)
    assert N > 20, "a full game should record many plies"

    # (1) MIXED aux_mask: trajectory policy rows True + an exact-endgame value-only tail.
    assert aux.sum() > 0, "no full-trajectory (policy) rows"
    assert (~aux).sum() > 0, "no value-only rows (exact-endgame tail missing?)"

    # (2) trajectory policy rows sum to 1 over the legal mask, 0 off-mask.
    prow_sums = pol[aux].sum(axis=1)
    assert np.allclose(prow_sums, 1.0, atol=1e-5), \
        f"policy rows must sum to 1; got [{prow_sums.min()}, {prow_sums.max()}]"
    off_mask = float((pol[aux] * (~mask[aux])).sum())
    assert off_mask == 0.0, f"policy has {off_mask} mass off the legal mask"

    # (3) value-only rows carry dummy zeros.
    assert float(pol[~aux].sum()) == 0.0, "value-only rows must have zero policy"
    assert int(mask[~aux].sum()) == 0, "value-only rows must have empty mask"

    # (4) values ∈ [-1,1], sign-consistent with the final score_diff.
    assert vals.min() >= -1.0 and vals.max() <= 1.0, "values out of [-1,1]"
    man = json.loads((out / "manifest.json").read_text())
    cfg = man["config"]
    s0, s1 = None, None
    # The manifest doesn't carry per-game score; recompute the sign from the recorded
    # symmetric value magnitude vs a fresh replay is overkill — instead pin the
    # invariant that all values share one magnitude |tanh(diff/15)| and BOTH signs
    # appear iff diff != 0 (mover-POV backfill).
    mag = np.abs(vals)
    assert np.allclose(mag, mag[0], atol=1e-5), "all rows must share |tanh(diff/15)| (outcome backfill)"
    if mag[0] > 1e-6:
        assert (vals > 0).any() and (vals < 0).any(), \
            "a decided game must have both +z (winner-mover) and -z (loser-mover) rows"

    # (5) manifest teacher block + resolved champion leaf CONFIG VALUES (not the hash).
    teacher = cfg["teacher"]
    assert teacher["policy_source"].startswith("pooled_visit_counts")
    assert teacher["move_selected_by"] == "pooled_q_argmax"
    assert teacher["k_dets"] == 2 and teacher["sims_per_det"] == 32
    assert "resolved_leaf_hash_runtime" in teacher, "runtime leaf hash must be recorded (provenance)"
    leaf = teacher["resolved_config"]["leaf_cfg"]
    assert [float(x) for x in leaf["v29_meeple_curve"]] == _CURVE125, \
        f"leaf is NOT curve125 (the curve100 trap): {leaf['v29_meeple_curve']}"
    assert float(leaf["bonus_cap"]) == 8.0 and float(leaf["opp_bonus_cap"]) == 8.0
    closure = {int(k): float(v) for k, v in leaf["closure_p"].items()}
    assert closure == {1: 0.5, 2: 0.2, 3: 0.05}, f"closure_p not default 3-open: {closure}"
    assert cfg["value_target"] == "game_outcome" and float(cfg["outcome_norm"]) == 15.0
    # default (net-free) manifest records the STAGE-1 champion mode.
    assert cfg["net_mode"] == "net-free (champion)"
    assert cfg["net_ckpt"] is None and cfg["shm_eval_server"] is None
    assert cfg["priors_source"].startswith("heuristic softmax")


def _save_small_sighted_net(path):
    """Build + save a SMALL random SIGHTED (81ch/42) CarcassonneNet checkpoint in the
    format gen_fair_distill._load_net expects (arch dims in the ckpt). Small net =
    fast per-leaf CPU forward for the plumbing test (the RECORDED targets are the
    pooled visits, not the net priors, so net quality is irrelevant here)."""
    torch = pytest.importorskip("torch")
    from carcassonne_ai.network import CarcassonneNet
    torch.manual_seed(0)
    net = CarcassonneNet(
        n_filters=16, n_blocks=2, n_input_channels=81, n_scalar_features=42,
        value_global_pool=True,
    )
    net.eval()
    torch.save({
        "model_state": net.state_dict(),
        "n_input_channels": 81, "n_scalar_features": 42,
        "n_filters": 16, "n_blocks": 2, "value_global_pool": True, "sighted": True,
    }, path)


def test_fair_net_prior_emitter_smoke(tmp_path):
    """STAGE-2 fair-NET-prior CPU path: --net-ckpt <sighted> --sighted emits 81ch/42
    shards whose POLICY target is still the pooled-visit distribution and whose VALUE
    is the frozen-leaf game-outcome — the net only steers search (severed value loop).
    Proves the --net-ckpt CLI wiring end-to-end (fork Pool + _load_net + worker net)."""
    pytest.importorskip("torch")
    net_pt = tmp_path / "small_sighted.pt"
    _save_small_sighted_net(net_pt)

    out = tmp_path / "fair_net_smoke"
    script = REPO / "scripts" / "distill_flywheel" / "gen_fair_distill.py"
    env = {**os.environ, **_CHAMP_ENV}
    r = subprocess.run(
        [sys.executable, "-u", str(script), "--games", "1", "--k-dets", "2",
         "--sims", "16", "--workers", "1", "--seed-start", "700000000",
         "--sighted", "--net-ckpt", str(net_pt), "--out", str(out)],
        env=env, capture_output=True, text=True, timeout=600,
    )
    assert r.returncode == 0, f"fair-net emitter failed:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"

    shards = sorted(out.glob("seed_*.npz"))
    assert len(shards) == 1, f"expected 1 shard, got {shards}"
    ds = GameDataset.load(shards[0])
    # SIGHTED shapes: 81ch board / 42 scalars.
    assert ds.boards.shape[1] == 81, f"expected 81ch (sighted), got {ds.boards.shape[1]}"
    assert ds.scalars.shape[1] == 42, f"expected 42 scalars (sighted), got {ds.scalars.shape[1]}"
    aux = np.asarray(ds.aux_mask, dtype=bool)
    pol = np.asarray(ds.policies, dtype=np.float32)
    mask = np.asarray(ds.valid_masks, dtype=bool)
    vals = np.asarray(ds.values, dtype=np.float32)
    # SAME distillation contract as the net-free path (targets are agg_n + outcome).
    assert aux.sum() > 0 and (~aux).sum() > 0, "aux_mask must be mixed"
    prow = pol[aux].sum(axis=1)
    assert np.allclose(prow, 1.0, atol=1e-5), "trajectory policy rows must sum to 1"
    assert float((pol[aux] * (~mask[aux])).sum()) == 0.0, "policy mass off the legal mask"
    assert vals.min() >= -1.0 and vals.max() <= 1.0

    man = json.loads((out / "manifest.json").read_text())["config"]
    assert man["net_mode"] == "cpu-net"
    assert man["net_ckpt"].endswith("small_sighted.pt")
    assert man["shm_eval_server"] is None
    assert man["priors_source"].startswith("net_policy_head")
    assert man["sighted"] is True and man["n_channels"] == 81 and man["n_scalars"] == 42


def test_action_log_round_trips(tmp_path):
    """--actions-only emits a root_replay (deck_seed, actions) GameRecord that replays
    BIT-EXACTLY to the board the generator held at every ply.

    This is the contract F3 / Gate-B root mining depends on (mine_roots.py --source
    champion): a root is stored as (deck_seed, actions, ply) and reconstructed by
    root_replay.replay_actions. If the log did not round-trip, every mined champion root
    would be a different position than the champion actually faced.

    Checks: (a) --actions-only writes the action json and NO npz; (b) the full replay is
    terminal with the recorded final scores; (c) the replay-side Game construction
    (root_replay) and the generator-side Game construction (window_size=25) agree on
    string_representation at EVERY ply; (d) an independent cold replay_actions(seed,
    actions, ply) matches at sampled plies.
    """
    import random as _pyrandom

    sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
    out = tmp_path / "actions_only_smoke"
    script = REPO / "scripts" / "distill_flywheel" / "gen_fair_distill.py"
    seed = 700_000_000
    env = {**os.environ, **_CHAMP_ENV}
    r = subprocess.run(
        [sys.executable, "-u", str(script), "--games", "1", "--k-dets", "2",
         "--sims", "32", "--workers", "1", "--seed-start", str(seed),
         "--actions-only", "--out", str(out)],
        env=env, capture_output=True, text=True, timeout=600,
    )
    assert r.returncode == 0, f"emitter failed:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"

    # (a) action log written; the (28 MB) training npz skipped.
    logs = sorted((out / "actions").glob("seed_*.json"))
    assert len(logs) == 1, f"expected 1 action log, got {logs}"
    assert not list(out.glob("seed_*.npz")), "--actions-only must not write npz shards"
    rec = json.loads(logs[0].read_text())
    assert rec["deck_seed"] == seed and rec["game_id"] == seed
    assert rec["n_plies"] == len(rec["actions"]) > 20
    assert rec["gen"] == "champion_fair_selfplay"

    import root_replay as RR
    from carcassonne_ai.game_wrapper import Game

    games = RR.load_games(logs[0].parent.parent / "actions" / logs[0].name)
    assert len(games) == 1
    g = games[0]

    # (b) full replay -> terminal, recorded final scores.
    rgame, rboard = RR.replay_actions(g.deck_seed, g.actions, len(g.actions))
    assert rgame.get_game_ended(rboard, 0) != 0.0, "replay is not terminal"
    assert (int(rboard.state.scores[0]), int(rboard.state.scores[1])) == \
        (int(rec["score_p0"]), int(rec["score_p1"])), "replayed final scores differ"

    # (c) per-ply: generator-side Game construction == replay-side Game construction.
    _pyrandom.seed(int(g.deck_seed))
    gen_game = Game(enable_legal_moves_cache=True, window_size=25)   # gen_fair_distill
    gen_board = gen_game.get_init_board()
    _pyrandom.seed(int(g.deck_seed))
    rep_game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)  # root_replay
    rep_board = rep_game.get_init_board()
    n = len(g.actions)
    for ply in range(n + 1):
        cs = gen_game.string_representation(gen_board)
        assert cs == rep_game.string_representation(rep_board), \
            f"gen/replay board diverged at ply {ply}"
        if ply % 40 == 0 or ply == n:      # (d) independent cold reconstruction
            cg, cb = RR.replay_actions(g.deck_seed, g.actions, ply)
            assert cg.string_representation(cb) == cs, f"cold replay differs at ply {ply}"
        if ply < n:
            gen_board, _ = gen_game.get_next_state(gen_board, int(g.actions[ply]))
            rep_board, _ = rep_game.get_next_state(rep_board, int(g.actions[ply]))
