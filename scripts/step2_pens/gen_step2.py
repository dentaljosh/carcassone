#!/usr/bin/env python3
"""Step-2 "PeNS" scalar-MLP-VALUE self-play GEN driver (MEASUREMENT ONLY).

The thin self-play driver for the weaned flywheel: priors from a base ResNet
(POLICY only), VALUE from the wean-blend of the v2.9 heuristic and a scalar MLP
over 89 live PeNS features (src/carcassonne_ai/step2_leaf.py).

  value = (1 - blend) * tanh(virtual_score_v2/15) + blend * scalar_mlp(feat89)
  (with per-leaf dropout p -> pure scalar-MLP value)

It loads a base policy net (--checkpoint, default RoD2 iter_02) + a ScalarMLP
(--scalar-ckpt, or --random-init for the wiring smoke), builds the wrapped
evaluator, runs N games via the PRODUCTION play_one_selfplay_game, writes
per-game .npz in the GameDataset schema run_selfplay_iter expects (so the
trainer can consume it), and PRINTS the provenance counters + per-game
wall-clock, asserting the scalar path actually fired.

This is WIRING correctness, NOT a strength run. Use --random-init for the smoke
(the real warmstart checkpoint gets swapped in later).

  # WIRING SMOKE (single-proc, random-init MLP):
  python -u scripts/step2_pens/gen_step2.py --random-init \
      --games 8 --sims 50 --blend 0.5 --dropout 0.2 --workers 1 \
      --out /tmp/step2_smoke

  # multi-proc:
  python -u scripts/step2_pens/gen_step2.py --random-init \
      --games 8 --sims 50 --blend 0.5 --dropout 0.2 --workers 8 \
      --out /tmp/step2_smoke
"""
from __future__ import annotations

# NOTE: step2_leaf imports build_dataset, whose import sets the v2.9 GUARD env
# (CARCASSONNE_V25_* / V29_MEEPLE_CURVE / USE_FLAT_LEAF=1 / USE_CY_REPR=1 /
# VALUE_BLEND=0) BEFORE virtual_score_v2.DEFAULT_CONFIG is frozen. We therefore
# import step2_leaf FIRST, before any carcassonne_ai leaf module, so the env is
# in place when DEFAULT_CONFIG is built. (CUDA_VISIBLE_DEVICES/OMP are setdefault
# in that block, so an explicit env still wins.)
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import carcassonne_ai.step2_leaf as step2_leaf  # noqa: E402 (sets guard env)

import argparse  # noqa: E402
import multiprocessing as mp  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from carcassonne_ai.evaluators import make_single_evaluator_policy_only  # noqa: E402
from carcassonne_ai.features import N_SCALAR_FEATURES  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.selfplay import play_one_selfplay_game  # noqa: E402
from carcassonne_ai.warmstart import GameDataset  # noqa: E402

import eval_hybrid_handoff as EH  # noqa: E402

# Import ScalarMLP from THIS package's train_warmstart.py explicitly by path —
# `scripts/train_warmstart.py` (a different file, no ScalarMLP) is also on
# sys.path and shadows a plain `import train_warmstart`.
import importlib.util as _ilu  # noqa: E402

_tw_spec = _ilu.spec_from_file_location(
    "step2_train_warmstart", str(REPO / "scripts" / "step2_pens" / "train_warmstart.py")
)
_tw = _ilu.module_from_spec(_tw_spec)
_tw_spec.loader.exec_module(_tw)
ScalarMLP = _tw.ScalarMLP  # reuse the exact arch the warmstart trainer saves


DEFAULT_BASE_CKPT = "/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt"

# Per-worker globals (spawn context; CUDA can't survive forks).
_W: dict = {}


def _load_base_net(ckpt_path: str, device: torch.device):
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_scalar_features=int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
        value_global_pool=bool(ckpt.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    include_farm_scalars = int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)) > N_SCALAR_FEATURES
    return net, include_farm_scalars


def _worker_init(cfg: dict) -> None:
    global _W
    # CPU-only (net-on-CPU): the base net is a tiny 7M and we want determinism +
    # no per-worker CUDA context for a wiring smoke. Matches the desktop-friendly
    # self-play recipe (CUDA_VISIBLE_DEVICES already "" via the guard env).
    device = torch.device("cpu")
    leaf_cfg = EH._heur_leaf_cfg(2.0)  # the v2.9 dataset config (hash-checked below)
    game = Game(
        enable_legal_moves_cache=True,
        include_farm_scalars=cfg["include_farm_scalars"],
    )
    mlp, col_mean, col_std, feat_names = _build_scalar_mlp_from_cfg(cfg, device)
    handles = None
    if cfg.get("shm_eval_server"):
        # POLICY priors come from the carc-orch SHM orchestrator (GPU-batched
        # forwards on one shared context — the fast path; net-on-CPU was the
        # 145s/game-at-sims50 blocker). The orch value is discarded by the wean
        # wrapper; only its priors are used. The SHM server must already be
        # running (scripts/heuristic_v28/v28_net_vs_net_orch.sh or the step2
        # launcher).
        from carcassonne_ai.shm_eval_handles import connect_shm
        from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
        handles = connect_shm(
            cfg["shm_eval_server"], cfg["_id_q"].get(), cfg["include_farm_scalars"] and 12 or 10
        )
        base_ev = make_remote_single_evaluator(handles, game)
    else:
        base_net, _ = _load_base_net(cfg["checkpoint"], device)
        base_ev = make_single_evaluator_policy_only(base_net, device, game)
    _W.update(
        game=game,
        device=device,
        leaf_cfg=leaf_cfg,
        base_ev=base_ev,
        mlp=mlp,
        col_mean=col_mean,
        col_std=col_std,
        feat_names=feat_names,
        cfg=cfg,
        handles=handles,
    )


def _build_scalar_mlp_from_cfg(cfg, device):
    """Worker-side ScalarMLP build from the serialized cfg (so the Pool doesn't
    pickle a torch module)."""
    D = step2_leaf.N_FEAT
    if cfg["random_init"]:
        torch.manual_seed(cfg["seed"])
        mlp = ScalarMLP(D, hidden=cfg["hidden"], blocks=cfg["blocks"]).to(device)
        mlp.eval()
        return mlp, np.zeros(D, np.float32), np.ones(D, np.float32), list(step2_leaf.FEAT_NAMES)
    ck = torch.load(cfg["scalar_ckpt"], map_location=device, weights_only=False)
    mlp = ScalarMLP(int(ck["D"]), hidden=int(ck["hidden"]), blocks=int(ck["blocks"])).to(device)
    mlp.load_state_dict(ck["state_dict"])
    mlp.eval()
    return (mlp, np.asarray(ck["col_mean"], np.float32),
            np.asarray(ck["col_std"], np.float32), [str(x) for x in ck["feat_names"]])


def _play_one(args_tuple):
    """Worker entry: play one game with the step2-wean evaluator, save .npz.
    Returns (seed, status, n_positions, wallclock, counters_dict)."""
    seed, out_dir_str = args_tuple
    out_dir = Path(out_dir_str)
    path = out_dir / f"seed_{seed:06d}.npz"
    cfg = _W["cfg"]

    # Fresh per-game counter so the returned counts are per-game (we sum in main).
    counters = step2_leaf._Step2Counters()
    wrapped = step2_leaf.make_step2_value_wrapper(
        _W["base_ev"],
        _W["mlp"],
        _W["col_mean"],
        _W["col_std"],
        _W["feat_names"],
        game=_W["game"],
        leaf_cfg=_W["leaf_cfg"],
        blend=cfg["blend"],
        dropout_p=cfg["dropout"],
        device=_W["device"],
        rng_seed=seed ^ 0x5715B2,
        counters=counters,
    )

    # In-loop feature harvest: per recorded trajectory ply, compute the live
    # PARENT-THREADED 89-vec (the SAME extraction used at the leaf). The on_ply
    # callback fires in lock-step with the GameDataset trajectory rows, so the
    # i-th 89-vec aligns row-for-row with ds.boards[i] / ds.values[i] (the
    # score_diff_wide target). Reuse the wrapper's leaf_cfg so the cfg is identical.
    pens_feats: list[np.ndarray] = []
    pens_flip: list[float] = []   # +1 if parent_player==leaf_player else -1 (target -> parent-POV)

    def _harvest(parent_board, board, cur_player, ply):
        pens_feats.append(
            step2_leaf.extract_step2_features(
                _W["game"], board, _W["leaf_cfg"], parent_board
            )
        )
        # The 89-vec is in PARENT(root)-player POV (extract_step2_features keys to
        # parent_board.current_player — the build_dataset/+43%-gate convention). The
        # value_target (score_diff_wide) is in the LEAF current_player POV, so flip
        # it to PARENT-POV below; else the in-loop retrain learns a mixed-POV mapping
        # (parent-POV features -> leaf-POV target) that corrupts as blend rises.
        if parent_board is not None and parent_board.state.current_player != board.state.current_player:
            pens_flip.append(-1.0)
        else:
            pens_flip.append(1.0)

    t0 = time.perf_counter()
    try:
        ds = play_one_selfplay_game(
            game=_W["game"],
            evaluator=wrapped,
            sims=cfg["sims"],
            c_puct=cfg["c_puct"],
            dirichlet_alpha=cfg["dirichlet_alpha"],
            dirichlet_eps=cfg["dirichlet_eps"],
            temp_threshold=cfg["temp_threshold"],
            seed=seed,
            batch_size=1,
            value_target=cfg["value_target"],
            on_ply=_harvest,
        )
    except Exception as e:
        import traceback
        return (seed, "failed", 0, time.perf_counter() - t0,
                counters.as_dict(), f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
    dt = time.perf_counter() - t0
    ds.save(path)

    # Persist the in-loop trainers' inputs. Two trainable views over ONE game:
    #   * the GameDataset .npz (seed_NNNNNN.npz)        -> ResNet POLICY (train_iter.py)
    #   * the PeNS companion .npz (seed_NNNNNN_pens.npz) -> ScalarMLP VALUE (train_warmstart)
    # The PeNS file carries the per-ply 89-vec + the score_diff_wide value target
    # (read from ds.values for the aux_mask=True trajectory rows) so the value
    # head retrains on (89-vec -> score_diff_wide). Row-aligned to the GameDataset
    # trajectory rows by construction (same is_learner_move guard / order).
    n_traj = int(np.count_nonzero(ds.aux_mask)) if ds.aux_mask is not None else len(ds)
    pens_arr = (np.stack(pens_feats).astype(np.float16)
                if pens_feats else np.empty((0, step2_leaf.N_FEAT), np.float16))
    # Defensive alignment check: one 89-vec per trajectory row.
    if pens_arr.shape[0] != n_traj:
        return (seed, "failed", 0, dt, counters.as_dict(),
                f"pens/traj misalignment: {pens_arr.shape[0]} feats vs {n_traj} trajectory rows")
    # score_diff_wide is in the LEAF current-player POV; flip per ply to PARENT
    # (root)-player POV so it matches the parent-POV 89-vec features + the warmstart
    # convention (POV FIX 2026-06-30 — else the retrain mixes POVs on flip plies).
    traj_values = ds.values[:n_traj].astype(np.float32)
    pov_flip = np.asarray(pens_flip[:n_traj], dtype=np.float32)
    if pov_flip.shape[0] != traj_values.shape[0]:
        return (seed, "failed", 0, dt, counters.as_dict(),
                f"pov_flip/traj misalignment: {pov_flip.shape[0]} vs {traj_values.shape[0]}")
    traj_values = traj_values * pov_flip
    traj_policies = ds.policies[:n_traj].astype(np.float32)
    pens_path = out_dir / f"seed_{seed:06d}_pens.npz"
    partial = pens_path.with_name(f".{pens_path.stem}.{os.getpid()}.partial.npz")
    np.savez_compressed(
        partial,
        pens_features=pens_arr,                                  # (T, 89) f16
        value_target=traj_values,                                # (T,) f32 score_diff_wide
        policy_target=traj_policies,                             # (T, A) f32 MCTS visit dist
        seed=np.int64(seed),
        feat_names=np.array(step2_leaf.FEAT_NAMES, dtype="<U64"),
        value_target_kind=np.array(cfg["value_target"], dtype="<U24"),
        blend=np.float32(cfg["blend"]),
    )
    partial.replace(pens_path)
    return (seed, "fresh", len(ds), dt, counters.as_dict(), None)


def main(argv=None):
    p = argparse.ArgumentParser(prog="gen_step2")
    p.add_argument("--checkpoint", default=DEFAULT_BASE_CKPT,
                   help="Base ResNet checkpoint for the POLICY (priors only). "
                        "Value comes from the scalar-MLP wean. Strength irrelevant "
                        "for a wiring smoke; default RoD2 iter_02.")
    p.add_argument("--scalar-ckpt", default=None,
                   help="train_warmstart.warmstart.pt for the ScalarMLP value. "
                        "Omit + pass --random-init for the wiring smoke.")
    p.add_argument("--random-init", action="store_true",
                   help="Use a fresh random-init ScalarMLP (identity normalization) "
                        "as the value stand-in. WIRING SMOKE only.")
    p.add_argument("--out", required=True, help="Output dir for per-game .npz.")
    p.add_argument("--games", type=int, default=8)
    p.add_argument("--sims", type=int, default=50)
    p.add_argument("--blend", type=float, default=0.5,
                   help="Wean parameter lambda: value=(1-lambda)*h + lambda*mlp. "
                        "0=pure heuristic, 1=pure scalar MLP.")
    p.add_argument("--dropout", type=float, default=0.0,
                   help="Per-leaf probability of returning the PURE scalar-MLP "
                        "value (forces the net path even at low blend).")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--c-puct", type=float, default=3.0)
    p.add_argument("--dirichlet-alpha", type=float, default=0.3)
    p.add_argument("--dirichlet-eps", type=float, default=0.25)
    p.add_argument("--temp-threshold", type=int, default=15)
    p.add_argument("--value-target", default="score_diff_wide",
                   choices=["score_diff", "score_diff_wide", "wl"],
                   help="Per-position value target for the produced .npz "
                        "(the scalar MLP retrains on these in-loop). "
                        "score_diff_wide = tanh(margin/40), the C6 de-sat target.")
    p.add_argument("--hidden", type=int, default=256)
    p.add_argument("--blocks", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--iter", type=int, default=0,
                   help="Iter index for the seed prefix (iter*10000 + game_idx).")
    p.add_argument("--shm-eval-server", default=None,
                   help="carc-orch SHM server name for the POLICY net (GPU-batched "
                        "priors via the orchestrator — the production fast path). "
                        "Must already be running (v28_net_vs_net_orch.sh launches "
                        "one). When set, --checkpoint is ignored for the priors "
                        "(the orch serves them); net-on-CPU is the fallback when "
                        "omitted. The orch VALUE is discarded — value = the wean.")
    args = p.parse_args(argv)

    if not args.random_init and not args.scalar_ckpt:
        p.error("provide --scalar-ckpt or --random-init")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Provenance: verify the leaf cfg matches the FROZEN v2.9 the dataset used.
    leaf_cfg = EH._heur_leaf_cfg(2.0)
    cfg_hash = step2_leaf._bd._cfg_hash(leaf_cfg)
    frozen = step2_leaf._bd.FROZEN_V29_HASH
    print(f"[provenance] v2.9 leaf config_hash = {cfg_hash} (frozen v2.9 = {frozen})")
    assert cfg_hash == frozen, f"LEAF NOT v2.9 (got {cfg_hash}, want {frozen})"

    # Peek the base net's scalar width so the worker Game emits matching scalars.
    _peek = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    ns = int(_peek.get("n_scalar_features", N_SCALAR_FEATURES))
    include_farm_scalars = ns > N_SCALAR_FEATURES
    del _peek

    cfg = {
        "checkpoint": args.checkpoint,
        "scalar_ckpt": args.scalar_ckpt,
        "random_init": bool(args.random_init),
        "include_farm_scalars": include_farm_scalars,
        "sims": args.sims,
        "blend": float(args.blend),
        "dropout": float(args.dropout),
        "c_puct": args.c_puct,
        "dirichlet_alpha": args.dirichlet_alpha,
        "dirichlet_eps": args.dirichlet_eps,
        "temp_threshold": args.temp_threshold,
        "value_target": args.value_target,
        "hidden": args.hidden,
        "blocks": args.blocks,
        "seed": args.seed,
        "shm_eval_server": args.shm_eval_server,
    }
    print(f"[gen] step2 PeNS wean self-play: games={args.games} sims={args.sims} "
          f"blend={args.blend} dropout={args.dropout} value_target={args.value_target} "
          f"workers={args.workers} base={Path(args.checkpoint).name} "
          f"scalar={'RANDOM-INIT' if args.random_init else Path(args.scalar_ckpt).name} "
          f"D={step2_leaf.N_FEAT} farm_scalars={include_farm_scalars}", flush=True)

    seeds = [args.iter * 10_000 + i for i in range(args.games)]
    pool_args = [(s, str(out_dir)) for s in seeds]

    fresh = failed = n_pos = 0
    durs: list[float] = []
    agg = {"calls": 0, "scalar_path": 0, "plain_path": 0,
           "dropout_path": 0, "terminal_path": 0}
    t0 = time.perf_counter()

    # The orch path needs a unique worker_id per worker (the SHM handle is keyed
    # on it). A Manager queue pre-filled with 0..W-1 hands each worker one id at
    # init (same pattern as v28_net_vs_net_orch). No-op when not using the orch.
    mgr = None
    if cfg["shm_eval_server"]:
        ctx0 = mp.get_context("spawn")
        mgr = ctx0.Manager()
        id_q = mgr.Queue()
        for w in range(max(1, args.workers)):
            id_q.put(w)
        cfg["_id_q"] = id_q

    if args.workers <= 1:
        _worker_init(cfg)
        results = [_play_one(a) for a in pool_args]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=args.workers, initializer=_worker_init,
                      initargs=(cfg,)) as pool:
            results = list(pool.imap_unordered(_play_one, pool_args, chunksize=1))
    if mgr is not None:
        mgr.shutdown()

    for seed, status, npos, dt, cd, err in results:
        if status == "fresh":
            fresh += 1
            n_pos += npos
            durs.append(dt)
        else:
            failed += 1
            print(f"  [seed {seed}] FAILED in {dt:.1f}s: {err}", flush=True)
        for k in agg:
            agg[k] += cd.get(k, 0)

    wall = time.perf_counter() - t0
    print(f"\n[done] {fresh} fresh + {failed} failed, {n_pos} positions, {wall:.1f}s wallclock")
    if durs:
        durs_s = sorted(durs)
        print(f"[per-game wallclock @ sims={args.sims}] "
              f"mean={np.mean(durs):.2f}s median={durs_s[len(durs_s)//2]:.2f}s "
              f"min={durs_s[0]:.2f}s max={durs_s[-1]:.2f}s (n={len(durs)})")
    print(f"[provenance counters] {agg}")

    # The wiring assertion: the scalar-MLP value path MUST have fired, and it
    # must not be ALL plain-heuristic. (terminal-path leaves are exact-value and
    # legitimately bypass both, so we assert on the non-terminal split.)
    nonterminal = agg["scalar_path"] + agg["plain_path"]
    assert agg["scalar_path"] > 0, (
        f"WIRING FAILURE: scalar_path=0 — the scalar-MLP value NEVER fired "
        f"(counters={agg})"
    )
    if args.blend > 0.0 or args.dropout > 0.0:
        frac = agg["scalar_path"] / max(1, nonterminal)
        print(f"[wiring OK] scalar-MLP value fired on {agg['scalar_path']}/"
              f"{nonterminal} non-terminal leaves ({100*frac:.1f}%); "
              f"net-value path genuinely active (not pure heuristic).")

    # Confirm the .npz is train-consumable (GameDataset.load round-trips + the
    # arrays the trainer reads are present and shaped right).
    files = sorted(out_dir.glob("seed_*.npz"))
    if files:
        ds = GameDataset.load(files[0])
        print(f"[npz] wrote {len(files)} files to {out_dir}")
        print(f"[npz] {files[0].name}: boards={ds.boards.shape} scalars={ds.scalars.shape} "
              f"policies={ds.policies.shape} values={ds.values.shape} "
              f"masks={ds.valid_masks.shape} -> train-consumable "
              f"(GameDataset.load OK, value_target={args.value_target})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
