"""Generate one iteration's worth of self-play games for Phase 4.

Per-game `.npz` checkpointing under `data/selfplay/<run>/iter_NN/seed_NNNNNN.npz`
— same schema as warmstart, so the streaming dataset / IO machinery is
reused unchanged.

Resumable: rerunning with the same args skips already-cached seeds. To
wipe and start over: `--reset`.

Workers default to 7 to leave SMT headroom for other workloads on the 5800X.

Usage:
  python -u scripts/run_selfplay_iter.py \\
      --checkpoint checkpoints/warmstart_canonical.pt \\
      --output-root data/selfplay/calibration \\
      --iter 0 --games 10 --sims 25 --workers 7

Detached (recommended for long iters):
  nohup python -u scripts/run_selfplay_iter.py [...] \\
      > /tmp/selfplay_iter00.log 2>&1 & disown
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import random
import shutil
import signal
import socket
import sys
import time
import zlib
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.claim import (
    claim_body as _claim_body,
    is_stale as _claim_is_stale,
    try_claim as _try_claim,
)
from carcassonne_ai.eval_server import (
    ServerHandles,
    shutdown_server,
    start_server,
)
from carcassonne_ai.eval_server_pool import (
    shutdown_server_pool,
    start_server_pool,
)
from carcassonne_ai.evaluators import (
    make_batch_evaluator,
    make_batch_evaluator_policy_only,
    make_single_evaluator,
    make_single_evaluator_policy_only,
    make_v25_batch_value_wrapper,
    make_v25_value_wrapper,
)
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.remote_eval_bridge import (
    BridgeServer,
    start_bridge,
    stop_bridge,
)
from carcassonne_ai.remote_evaluators import (
    make_remote_batch_evaluator,
    make_remote_single_evaluator,
)
from carcassonne_ai.remote_socket_handles import (
    SocketServerHandles,
    connect_remote,
)
from carcassonne_ai.selfplay import play_one_selfplay_game
import dataclasses
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
from carcassonne_ai.warmstart import GameDataset


REPO_ROOT = Path(__file__).resolve().parent.parent


# Per-worker globals. CUDA can't survive forks, so the Pool uses 'spawn'
# context and each worker re-loads the checkpoint exactly once on init.
# In orchestrator mode `_worker_net` stays None and `_worker_handles` holds
# the IPC bundle pointing at the shared server process.
_worker_net: CarcassonneNet | None = None
_worker_device: torch.device | None = None
_worker_cfg: dict | None = None
_worker_handles: ServerHandles | SocketServerHandles | None = None
_worker_anchor_net: CarcassonneNet | None = None
_worker_anchor_handles: ServerHandles | SocketServerHandles | None = None


def _parse_host_port(s: str) -> tuple[str, int]:
    """argparse type for HOST:PORT flags."""
    if ":" not in s:
        raise argparse.ArgumentTypeError(
            f"expected HOST:PORT, got {s!r}"
        )
    host, port_s = s.rsplit(":", 1)
    try:
        port = int(port_s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"port in {s!r} is not an integer"
        ) from e
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            f"port {port} out of range 1-65535"
        )
    return host, port


def _worker_init(checkpoint_path: str, cfg: dict) -> None:
    """Pool initializer. In orchestrator mode the worker skips the net load
    entirely; the server process owns the only copy of the weights and
    workers talk to it via IPC handles passed through `cfg`.

    Each worker claims a unique worker_id by popping from cfg["orch_id_q"]
    (an mp.Queue pre-seeded with 0..N-1). This is the standard way to give
    each Pool worker a stable index, since Pool itself doesn't expose one.
    """
    global _worker_net, _worker_device, _worker_cfg, _worker_handles
    global _worker_anchor_net, _worker_anchor_handles
    _worker_cfg = cfg
    if cfg.get("orchestrator"):
        # CPU-only worker. No torch.cuda, no checkpoint load.
        _worker_device = torch.device("cpu")
        _worker_net = None
        # Each pool worker picks a unique global worker_id off the id_q
        # (mp.Queue seeded with 0..N-1).
        global_worker_id = cfg["orch_id_q"].get()
        remote_addr = cfg.get("remote_eval_server")
        if remote_addr:
            # Network mode: open a TCP connection to the remote bridge. The
            # SocketServerHandles exposes the same .request_q.put() /
            # .response_q.get() API as the local IPC ServerHandles, so the
            # make_remote_*_evaluator factories below work unchanged.
            host, port = remote_addr
            _worker_handles = connect_remote(host, port, global_worker_id)
        else:
            # Local IPC: look up the per-worker routing bundle in
            # cfg["orch_handles_by_worker"][worker_id] — already encodes
            # which shard's request_q/response_q to talk to.
            _worker_handles = cfg["orch_handles_by_worker"][global_worker_id]
        # Anchor pool: a second set of per-worker handles backed by an
        # independent server-pool running the anchor checkpoint. Only some
        # games use it (see anchor_fraction); workers always hold the
        # handle ready so anchor games don't pay setup cost mid-pool.
        anchor_handles_by_worker = cfg.get("orch_anchor_handles_by_worker")
        if anchor_handles_by_worker is not None:
            _worker_anchor_handles = anchor_handles_by_worker[global_worker_id]
        return
    _worker_device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    ckpt = torch.load(
        checkpoint_path, map_location=_worker_device, weights_only=False
    )
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_scalar_features=int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
        value_global_pool=bool(ckpt.get("value_global_pool", False)),
    ).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net
    # Per-worker anchor net (non-orchestrator path). Loaded once per worker;
    # same CUDA device as the learner net (acceptable VRAM cost for our 30 MB
    # nets — the orchestrator path is the production one anyway).
    anchor_ckpt_path = cfg.get("anchor_checkpoint")
    if anchor_ckpt_path:
        a_ckpt = torch.load(
            anchor_ckpt_path, map_location=_worker_device, weights_only=False
        )
        a_net = CarcassonneNet(
            n_filters=a_ckpt["n_filters"],
            n_blocks=a_ckpt["n_blocks"],
            n_scalar_features=int(a_ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
            value_global_pool=bool(a_ckpt.get("value_global_pool", False)),
        ).to(_worker_device)
        a_net.load_state_dict(a_ckpt["model_state"])
        a_net.train(False)
        _worker_anchor_net = a_net


def _seed_for(iter_idx: int, game_idx: int) -> int:
    # Reproducible seeds; iter_idx * 10_000 leaves room for 10K games/iter.
    return iter_idx * 10_000 + game_idx


def _result_path(out_dir: Path, seed: int) -> Path:
    return out_dir / f"seed_{seed:06d}.npz"


# Work-stealing claim primitive: see `carcassonne_ai.claim`. Imported above as
# `_try_claim` / `_claim_is_stale` / `_claim_body` for back-compat (the
# `test_selfplay_claim` suite imports the underscored names from this module).
def _claim_path(out_dir: Path, seed: int) -> Path:
    return out_dir / f"seed_{seed:06d}.claim"


def _play_one_pool(args: tuple[int, str]) -> tuple[int, str, int]:
    """Worker entry: skip if cached, else play one self-play game and save."""
    seed, out_dir_str = args
    out_dir = Path(out_dir_str)
    path = _result_path(out_dir, seed)
    if path.exists():
        try:
            ds = GameDataset.load(path)
            return seed, "cached", len(ds)
        except Exception:
            path.unlink(missing_ok=True)

    cfg = _worker_cfg
    assert cfg is not None

    # Work-stealing: atomically claim this seed before playing it. If another
    # worker — on this box or the other — already owns it, skip; the pool will
    # hand us the next task. Legacy (non-shared) runs skip this entirely.
    if cfg.get("shared_claim"):
        if not _try_claim(
            _claim_path(out_dir, seed),
            cfg["claim_host"],
            cfg["claim_stale_secs"],
        ):
            return seed, "skipped", 0

    game = Game(
        enable_legal_moves_cache=True,
        include_farm_scalars=cfg.get("include_farm_scalars", False),
    )
    use_fp16 = cfg.get("use_fp16", False)
    # If the v2.5 leaf is going to override the value anyway, we can skip the
    # value-head forward in both the per-worker and orchestrator paths.
    # Orchestrator's policy_only flag was set at server startup (cfg.get
    # ("policy_only")); per-worker path uses the policy-only factory here.
    # Exception (Option 2): value_blend > 0 blends the NN value head into the
    # leaf, so the value head must be computed — no policy-only fast path.
    def _build_evaluators(handles, net, blend=None):
        """Build (evaluator, batch_evaluator) for one net.

        `blend` is the value_blend λ for THIS evaluator's leaf; None → the
        learner's cfg value. The anchor passes blend=0.0 so the fixed reference
        (iter_11, trained with the value head OUT of the search loop) plays
        exactly as it was trained — NOT with the learner's mid-ramp blend
        (G-S1 plan risk #4). With the v2_5 leaf, leaf_cfg's value_blend=0.0
        makes the wrapper discard any NN value, so the anchor stays pure v2.7
        even on the orchestrator path (where the server may still compute it)."""
        eff_blend = cfg.get("value_blend", 0.0) if blend is None else blend
        # Skip the value-head forward only when the v2_5 leaf fully overrides the
        # value (blend == 0). blend > 0 needs the NN value head computed.
        po = (cfg.get("leaf_eval", "nn") != "nn" and eff_blend == 0.0)
        if cfg.get("orchestrator"):
            assert handles is not None
            ev = make_remote_single_evaluator(handles, game)
            bev = None
            if cfg["batch_size"] > 1:
                bev = make_remote_batch_evaluator(handles, game)
        else:
            assert net is not None and _worker_device is not None
            if po:
                ev = make_single_evaluator_policy_only(
                    net, _worker_device, game, use_fp16=use_fp16
                )
            else:
                ev = make_single_evaluator(
                    net, _worker_device, game, use_fp16=use_fp16
                )
            bev = None
            if cfg["batch_size"] > 1:
                if po:
                    bev = make_batch_evaluator_policy_only(
                        net, _worker_device, game, use_fp16=use_fp16
                    )
                else:
                    bev = make_batch_evaluator(
                        net, _worker_device, game, use_fp16=use_fp16
                    )
        if cfg.get("leaf_eval") == "v2_5":
            # G-S1: per-iter value_blend overrides import-time DEFAULT_CONFIG so the
            # ramp reaches the worker leaf. Other LeafConfig fields (cap, etc.) still
            # come from env via DEFAULT_CONFIG.
            leaf_cfg = dataclasses.replace(DEFAULT_CONFIG, value_blend=eff_blend)
            ev = make_v25_value_wrapper(ev, cfg=leaf_cfg)
            if bev is not None:
                bev = make_v25_batch_value_wrapper(bev, cfg=leaf_cfg)
        return ev, bev

    evaluator, batch_evaluator = _build_evaluators(_worker_handles, _worker_net)

    # Anchor-fraction: decide per-seed whether this game is a learner-vs-anchor
    # mixed game and which side the learner plays. XOR the seed with a constant
    # so this RNG decorrelates from any other per-seed RNG use downstream.
    anchor_fraction = float(cfg.get("anchor_fraction", 0.0))
    anchor_evaluator = None
    anchor_batch_evaluator = None
    learner_player_idx = 0
    if anchor_fraction > 0.0 and (
        _worker_anchor_handles is not None or _worker_anchor_net is not None
    ):
        seed_rng = random.Random(seed ^ 0xA1B2C3D4)
        if seed_rng.random() < anchor_fraction:
            anchor_evaluator, anchor_batch_evaluator = _build_evaluators(
                _worker_anchor_handles, _worker_anchor_net, blend=0.0
            )
            learner_player_idx = seed_rng.randint(0, 1)

    try:
        ds = play_one_selfplay_game(
            game=game,
            evaluator=evaluator,
            sims=cfg["sims"],
            c_puct=cfg["c_puct"],
            dirichlet_alpha=cfg["dirichlet_alpha"],
            dirichlet_eps=cfg["dirichlet_eps"],
            temp_threshold=cfg["temp_threshold"],
            seed=seed,
            batch_size=cfg["batch_size"],
            batch_evaluator=batch_evaluator,
            virtual_loss=cfg["virtual_loss"],
            value_target=cfg["value_target"],
            interior_min_visits=cfg["interior_min_visits"],
            interior_max_per_move=cfg["interior_max_per_move"],
            anchor_evaluator=anchor_evaluator,
            anchor_batch_evaluator=anchor_batch_evaluator,
            learner_player_idx=learner_player_idx,
        )
    except Exception as e:
        # Engine edge cases (e.g. farm_util IndexError seen 2026-05-10) shouldn't
        # nuke the whole iter. Log + skip; a missing seed file just means less
        # training data for this iter, not a corrupt buffer.
        import traceback
        sys.stderr.write(
            f"\n[seed {seed}] selfplay FAILED: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}\n"
        )
        sys.stderr.flush()
        return seed, "failed", 0
    ds.save(path)
    return seed, "fresh", len(ds)


def main(argv: list[str] | None = None) -> int:
    # Run teardown on SIGTERM *and* SIGHUP (review R2-B1 + R3-B1): the cluster loop
    # stops workers with `pkill -TERM`, and a dropped held-ssh (Mac sleep, network
    # flap) delivers SIGHUP to the remote worker. Python's default disposition for
    # BOTH exits WITHOUT unwinding, so the try/finally that calls
    # shutdown_server_pool / stop_bridge never runs and the non-daemon eval-server
    # (spawn_main) children orphan, each holding a CUDA context — a VRAM leak per
    # box. The local 5800X is shielded by `nohup` (ignores SIGHUP), but the Xeon
    # and laptop python procs are started fresh by the remote sshd with the default
    # SIGHUP disposition, so local-side nohup does NOT cover them. Translate both
    # signals into a normal SystemExit so the finally-block teardown executes.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
    p = argparse.ArgumentParser(prog="run_selfplay_iter")
    p.add_argument("--checkpoint", type=Path, required=False, default=None,
                   help="Network checkpoint to use as the self-play opponent. "
                        "Required unless --remote-eval-server is set (a remote "
                        "client doesn't load the model — the server does).")
    p.add_argument("--output-root", type=Path, required=True,
                   help="Root dir for self-play data; per-iter subdirs created.")
    p.add_argument("--iter", type=int, required=True, dest="iter_idx",
                   help="Iteration index (used in the seed prefix and subdir name).")
    p.add_argument("--games", type=int, default=25,
                   help="Number of self-play games to generate (default 25).")
    p.add_argument("--seed-start", type=int, default=0,
                   help="Offset added to the per-game index before computing "
                        "seeds (default 0). Splits one logical iter across "
                        "machines with disjoint seed ranges: box A --seed-start "
                        "0 --games 740, box B --seed-start 740 --games 460 → "
                        "1200 disjoint seeds under the same --iter. Stay well "
                        "under the 10_000 per-iter seed stride.")
    p.add_argument("--sims", type=int, default=25,
                   help="NeuralMCTS simulations per move (default 25).")
    p.add_argument("--c-puct", type=float, default=3.0,
                   help="PUCT exploration constant in self-play tree search. "
                        "Bumped 2026-05-27 ALONGSIDE the eval-side bump, but "
                        "ONLY EVAL-SIDE IS VALIDATED (Phase 2b +47.2 elo at "
                        "sims=200, J4 +39.3 at sims=800 — both head-to-head "
                        "with iter_B1 as the player, different c each side). "
                        "Self-play-side c=3 is a hypothesis: deeper exploration "
                        "during self-play SHOULD yield more diverse training "
                        "data and stronger checkpoints, but no A/B has been "
                        "done (train iter with c=1.5 self-play vs c=3 self-play, "
                        "then eval head-to-head). Was 1.5 until 2026-05-27.")
    p.add_argument("--dirichlet-alpha", type=float, default=0.3)
    p.add_argument("--dirichlet-eps", type=float, default=0.25)
    p.add_argument("--temp-threshold", type=int, default=15)
    p.add_argument(
        "--value-target",
        choices=["score_diff", "score_diff_wide", "wl", "search_value",
                 "search_value_tree", "v2_7", "search_value_rank", "residual"],
        default="score_diff",
        help="Per-position value target encoding. 'score_diff' (default) = "
             "tanh((p0-p1)/15), the graded margin in the same currency as the "
             "v2.7 heuristic leaf (Option 2, 2026-05-17 — so a value head "
             "blended into the leaf predicts a like-for-like quantity). "
             "'score_diff_wide' = tanh((p0-p1)/40), the C6 de-saturated target "
             "(/15 pins to ±1 for 30-80pt margins → MSE kills mid-range "
             "calibration; use at the Stage-B retrain). "
             "'wl' = ±1/0, the AlphaZero-canonical win/loss target. "
             "'search_value' = per-position MCTS root.Q (current-player POV) — "
             "the overfitting fix (DECISIONS 2026-06-04): ~100× more independent "
             "value labels than the one-per-game outcome z. Use at sims≥200 so "
             "root.Q exceeds v2.7; warm from iter_01 with --leaf-eval v2_5 "
             "--value-blend 0. "
             "'search_value_tree' = search_value PLUS value-only rows harvested "
             "from the search TREE INTERIOR (flywheel step 1, DECISIONS "
             "2026-06-04) — the fix for the −576 pure-NN-leaf distribution "
             "mismatch; the value head sees the off-trajectory positions search "
             "actually queries (tune via --interior-min-visits/-max-per-move). "
             "'v2_7' = MIMIC-V2.7 diagnostic (STEP B.0, DECISIONS 2026-06-05 "
             "pm-2): target = the v2.7 leaf value tanh(vs2/15) at each trajectory "
             "+ interior position (NOT outcome/Q). Tests whether a 7M head can "
             "represent v2.7's sibling-ranking under MSE (STEP A: the search-Q "
             "head ranks siblings at ~chance τ=0.08 vs v2.7's 0.58).",
    )
    p.add_argument(
        "--interior-min-visits", type=int, default=8,
        help="search_value_tree only: keep an interior node as a value target "
             "only if its visit count N >= this (a converged Q, not N=1 noise).",
    )
    p.add_argument(
        "--interior-max-per-move", type=int, default=16,
        help="search_value_tree only: cap interior value-only rows kept per move "
             "(top-N by visits), to bound dataset blow-up.",
    )
    p.add_argument(
        "--batch-size", type=int, default=1,
        help="NeuralMCTS batch size for virtual-loss / batched-eval mode. "
             "1 (default) = serial. >1 = collect K leaves per batch and "
             "evaluate them in a single GPU forward pass. Typical: 8.",
    )
    p.add_argument(
        "--virtual-loss", type=float, default=1.0,
        help="PUCT W-penalty applied to in-flight nodes during batched "
             "selection. Only matters when --batch-size > 1.",
    )
    p.add_argument(
        "--workers", type=int, default=8,
        help="Pool workers. Default 8 leaves SMT headroom for other "
             "workloads on a 5800X. For dedicated runs, W=16 is the "
             "empirical local optimum (1 worker per SMT thread; saturates "
             "GPU queue without CPU-side preemption — measured 2026-05-09 "
             "on RTX 5060 Ti, ~20%% faster than W=8).",
    )
    p.add_argument(
        "--fp16", action="store_true",
        help="Run network forward passes under torch.amp.autocast(fp16) on "
             "CUDA. Master weights stay fp32 (inference-only autocast). "
             "Typical 1.5-2× speedup on Blackwell/Ada Tensor Cores. "
             "No-op on CPU. Default off for backward compat.",
    )
    p.add_argument(
        "--orchestrator", action="store_true",
        help="GPU inference-server mode. One dedicated server process owns "
             "the net and CUDA context; workers are CPU-only and send "
             "(board, scalars, mask) over IPC. Lets the GPU batch across "
             "workers (higher utilization) and slashes per-worker VRAM "
             "(unlocks W=96+ on big-CPU boxes). Default off; numerically "
             "identical to the per-worker path within float32 noise.",
    )
    p.add_argument(
        "--orch-max-batch", type=int, default=256,
        help="Max batch the orchestrator stacks per forward pass. "
             "Only used with --orchestrator.",
    )
    p.add_argument(
        "--orch-batch-timeout-ms", type=float, default=2.0,
        help="Max time orchestrator waits to accumulate more requests "
             "before forwarding a partial batch. Only used with --orchestrator.",
    )
    p.add_argument(
        "--orch-shards", type=int, default=1,
        help="Number of parallel eval-server processes (sharded by "
             "worker_id %% N). Default 1 = single server (back-compat). "
             ">1 cracks the GIL bottleneck of the single-server Python "
             "dispatch loop; each shard owns its own net copy on the GPU "
             "(~2 GB per shard for 96x6 net). Only used with --orchestrator. "
             "Per-shard sweep (2026-05-13) finds the empirical optimum; "
             "see DECISIONS.md.",
    )
    p.add_argument(
        "--leaf-eval", choices=["nn", "v2_5"], default="nn",
        help="Source of the leaf VALUE during self-play MCTS. "
             "'nn' (default, back-compat with v1-v6) uses the network's "
             "value head. 'v2_5' uses tanh(virtual_score_v2/15), which beat "
             "v1 by 6.6pp at sims=400 (DECISIONS.md 2026-05-14). Priors "
             "always come from the network — only the leaf value source "
             "changes.",
    )
    p.add_argument(
        "--value-blend", type=float, default=0.0,
        help="Stage B (G-S1): blend weight λ for the NN value head into the "
             "v2_5 leaf: (1-λ)*tanh(vs2/15) + λ*v_nn. 0.0 (default) = pure "
             "v2.7 leaf (value head NOT in the search loop — the F-B1 failure). "
             "λ>0 puts the learned value INTO the loop; ramp over iters via "
             "run_pathb_cluster_loop.sh blend_for_iter(). Requires --leaf-eval v2_5.",
    )
    p.add_argument(
        "--shared-claim", action="store_true",
        help="Work-stealing mode. Before playing a seed, atomically claim it "
             "via an O_EXCL `seed_NNNNNN.claim` sidecar file. Lets multiple "
             "machines run the SAME --seed-start/--games range against ONE "
             "shared --output-root and load-balance automatically — each game "
             "goes to whichever worker claims it first. Default off "
             "(byte-identical legacy behavior).",
    )
    p.add_argument(
        "--claim-stale-secs", type=int, default=5400,
        help="Only with --shared-claim. A claim with no resulting .npz whose "
             "timestamp is older than this is treated as abandoned and may be "
             "re-claimed (default 5400 = 90 min, well over one game).",
    )
    p.add_argument(
        "--claim-host", type=str, default=socket.gethostname(),
        help="Only with --shared-claim. Identity recorded in claim files "
             "(default: this machine's hostname). Override to force distinct "
             "identities when stress-testing the claim race on one box.",
    )
    p.add_argument(
        "--serve-on", type=_parse_host_port, default=None,
        metavar="HOST:PORT",
        help="Server mode: in addition to local workers, start a TCP bridge "
             "on HOST:PORT exposing --serve-slots eval-server slots to "
             "remote machines. Requires --orchestrator. The local pool is "
             "started with (--workers + --serve-slots) slots total — local "
             "workers claim the first --workers, remote clients claim the "
             "rest. Default off.",
    )
    p.add_argument(
        "--serve-slots", type=int, default=0,
        help="Only with --serve-on. Slots reserved for remote workers. "
             "Set >= the total worker count across all remote clients.",
    )
    p.add_argument(
        "--remote-eval-server", type=_parse_host_port, default=None,
        metavar="HOST:PORT",
        help="Client mode: do not start a local eval-server. Each local "
             "worker opens a TCP connection to the remote bridge at "
             "HOST:PORT and ships eval requests over the network. Implies "
             "--orchestrator. Mutually exclusive with --serve-on.",
    )
    p.add_argument(
        "--anchor-checkpoint", type=Path, default=None,
        help="Anchor-fraction self-play: fixed strong-opponent checkpoint. "
             "When set, a fraction of games (see --anchor-fraction) are played "
             "as learner-vs-anchor (alternating side); only the learner's "
             "moves are recorded. Breaks the rock-paper-scissors drift that "
             "killed the Option B chain (2026-05-24 — DECISIONS.md). "
             "Mutually exclusive with --serve-on / --remote-eval-server.",
    )
    p.add_argument(
        "--anchor-fraction", type=float, default=0.0,
        help="Fraction of self-play games played against --anchor-checkpoint "
             "(default 0.0 → legacy behavior). 0.3 is the recommended starting "
             "point — keeps 70%% pure self-play while exposing the learner to "
             "a different opponent distribution.",
    )
    p.add_argument("--reset", action="store_true",
                   help="Wipe the iter subdir before starting.")
    p.add_argument("--summary-only", action="store_true",
                   help="Just count what's on disk; do not play.")
    args = p.parse_args(argv)

    if args.reset and args.shared_claim:
        p.error(
            "--reset with --shared-claim would wipe a directory other "
            "machines are writing to. Refusing."
        )

    if args.remote_eval_server and args.serve_on:
        p.error("--remote-eval-server and --serve-on are mutually exclusive")
    if args.serve_on and not args.orchestrator:
        p.error("--serve-on requires --orchestrator")
    if args.serve_on and args.serve_slots <= 0:
        p.error("--serve-on requires --serve-slots > 0")
    if args.remote_eval_server:
        # Remote mode is an orchestrator client; the remote box owns the
        # server pool. Force the orchestrator code path on so _worker_init
        # takes the orchestrator branch.
        args.orchestrator = True
    if not args.remote_eval_server and args.checkpoint is None:
        p.error("--checkpoint is required (only optional with --remote-eval-server)")
    if args.anchor_fraction < 0.0 or args.anchor_fraction > 1.0:
        p.error(f"--anchor-fraction must be in [0, 1]; got {args.anchor_fraction}")
    if args.anchor_fraction > 0.0 and args.anchor_checkpoint is None:
        p.error("--anchor-fraction > 0 requires --anchor-checkpoint")
    if args.anchor_checkpoint and (args.serve_on or args.remote_eval_server):
        p.error(
            "--anchor-checkpoint is not supported with --serve-on or "
            "--remote-eval-server (single-host only for now)"
        )

    iter_dir = args.output_root / f"iter_{args.iter_idx:02d}"

    if args.summary_only:
        if not iter_dir.exists():
            print(f"No data at {iter_dir}")
            return 0
        files = sorted(iter_dir.glob("seed_*.npz"))
        n_pos = 0
        for f in files:
            try:
                ds = GameDataset.load(f)
                n_pos += len(ds)
            except Exception as e:
                print(f"  load failed: {f.name}: {e}")
        print(f"{iter_dir}: {len(files)} games, {n_pos} positions")
        return 0

    if args.reset and iter_dir.exists():
        shutil.rmtree(iter_dir)
        print(f"Wiped {iter_dir}")
    iter_dir.mkdir(parents=True, exist_ok=True)

    seeds = [
        _seed_for(args.iter_idx, args.seed_start + i)
        for i in range(args.games)
    ]
    pool_args = [(s, str(iter_dir)) for s in seeds]
    if args.shared_claim:
        # Each box walks the seed list in its own order (keyed by claim-host)
        # so the two boxes start claiming in different regions — avoids a
        # brief startup burst of every worker racing for the same low seeds.
        random.Random(zlib.crc32(args.claim_host.encode())).shuffle(pool_args)
    already = sum(1 for s in seeds if _result_path(iter_dir, s).exists())
    remaining = args.games - already

    # Auto-cap removed 2026-05-09: empirical bench (W={4,8,12,16,20}) on
    # RTX 5060 Ti showed W=16 actually beats W=4 by ~2× (vs. the old cap
    # logic which forced W≤4 for "GPU thrash safety"). The driver-level
    # GPU queue self-regulates — more workers fill the queue more cleanly,
    # they don't thrash. Cap your workers explicitly via --workers if you
    # need to leave CPU/GPU headroom for other workloads.
    #
    # Shared-claim mode never caps at `remaining`: that count is racy across
    # boxes (the other box finishes seeds mid-run), and an under-count would
    # starve this box of workers. Skip-scanning a claimed seed is cheap.
    n_workers = (
        args.workers if args.shared_claim
        else min(args.workers, remaining or 1)
    )

    # Path B Step E: derive the farm-scalar shape from the learner checkpoint so
    # workers build a Game whose get_canonical_form emits the matching scalar
    # width (the server net is sized from the same checkpoint in eval_server).
    # Off (10-scalar) for pre-Step-E checkpoints and remote-server mode.
    include_farm_scalars = False
    learner_ns = N_SCALAR_FEATURES
    if args.checkpoint is not None:
        _peek = torch.load(str(args.checkpoint), map_location="cpu", weights_only=False)
        learner_ns = int(_peek.get("n_scalar_features", N_SCALAR_FEATURES))
        include_farm_scalars = learner_ns > N_SCALAR_FEATURES
        del _peek

    # Defense-in-depth (pre-launch review B1, 2026-05-31): the anchor and learner
    # MUST share scalar width. A single learner-width Game feeds BOTH evaluators,
    # so a mismatched anchor net (e.g. a 10-scalar legacy anchor + a 12-scalar
    # Path-B learner) receives wrong-width scalars -> the anchor forward crashes ->
    # the server returns uniform stub priors -> the learner silently trains against
    # a RANDOM opponent (poisoned games recorded unflagged), defeating the entire
    # point of anchor-fraction. Fail loud instead of corrupting the run.
    if getattr(args, "anchor_checkpoint", None) is not None:
        _peek_a = torch.load(str(args.anchor_checkpoint), map_location="cpu", weights_only=False)
        anchor_ns = int(_peek_a.get("n_scalar_features", N_SCALAR_FEATURES))
        del _peek_a
        if anchor_ns != learner_ns:
            raise SystemExit(
                f"FATAL: --anchor-checkpoint n_scalar_features ({anchor_ns}) != "
                f"--checkpoint n_scalar_features ({learner_ns}). Mixing 10/12-scalar "
                f"lineages in anchor-fraction is unsupported (a single learner-width "
                f"Game feeds both nets; the mismatched anchor would emit uniform stub "
                f"priors). Use same-lineage checkpoints for learner and anchor."
            )

    cfg = {
        "include_farm_scalars": include_farm_scalars,
        "sims": args.sims,
        "c_puct": args.c_puct,
        "dirichlet_alpha": args.dirichlet_alpha,
        "dirichlet_eps": args.dirichlet_eps,
        "temp_threshold": args.temp_threshold,
        "batch_size": args.batch_size,
        "virtual_loss": args.virtual_loss,
        "use_fp16": args.fp16,
        "orchestrator": args.orchestrator,
        "leaf_eval": args.leaf_eval,
        "value_target": args.value_target,
        "interior_min_visits": args.interior_min_visits,
        "interior_max_per_move": args.interior_max_per_move,
        "shared_claim": args.shared_claim,
        "claim_stale_secs": args.claim_stale_secs,
        "claim_host": args.claim_host,
        "anchor_checkpoint": str(args.anchor_checkpoint) if args.anchor_checkpoint else None,
        "anchor_fraction": float(args.anchor_fraction),
        "value_blend": float(args.value_blend),
    }
    print(
        f"selfplay iter={args.iter_idx}: {args.games} games "
        f"(sims={args.sims}, c_puct={args.c_puct}, "
        f"alpha={args.dirichlet_alpha}, eps={args.dirichlet_eps}, "
        f"temp_thresh={args.temp_threshold}, "
        f"batch_size={args.batch_size}, vloss={args.virtual_loss}, "
        f"leaf_eval={args.leaf_eval}, value_target={args.value_target}), "
        f"{n_workers} workers, {already} cached, {remaining} to play, "
        f"out={iter_dir}, orchestrator={args.orchestrator}"
    )
    sys.stdout.flush()

    if remaining == 0:
        print("All games cached; nothing to do.")
        return 0

    t0 = time.perf_counter()
    fresh = 0
    cached = 0
    skipped = 0
    failed = 0
    n_pos_total = 0
    first_fresh_t: float | None = None
    ctx = mp.get_context("spawn")

    # Orchestrator: start the server pool before pool spawn. Servers run
    # on GPU; workers stay CPU-only and receive their routing bundle via
    # cfg. n_shards=1 is single-server (back-compat); n_shards>1 cracks
    # the GIL bottleneck (DECISIONS.md 2026-05-13).
    server_pool = None
    anchor_server_pool = None
    bridge: BridgeServer | None = None
    if args.orchestrator:
        if args.remote_eval_server:
            host, port = args.remote_eval_server
            print(
                f"  remote eval-server mode: connecting to "
                f"{host}:{port} from {n_workers} local workers"
            )
            sys.stdout.flush()
            id_q = ctx.Queue()
            for w in range(n_workers):
                id_q.put(w)
            cfg["remote_eval_server"] = (host, port)
            cfg["orch_id_q"] = id_q
        else:
            # Local server. If --serve-on is set, oversize the pool by
            # serve_slots so the bridge has slots for remote clients.
            local_total = n_workers + max(0, args.serve_slots)
            print(
                f"  starting eval-server pool "
                f"(shards={args.orch_shards}, "
                f"max_batch={args.orch_max_batch}, "
                f"timeout={args.orch_batch_timeout_ms}ms, "
                f"fp16={args.fp16}, slots={local_total} = "
                f"{n_workers} local + {max(0, args.serve_slots)} remote)…"
            )
            sys.stdout.flush()
            server_pool = start_server_pool(
                checkpoint_path=str(args.checkpoint or ""),
                n_workers=local_total,
                n_shards=args.orch_shards,
                max_batch=args.orch_max_batch,
                batch_timeout_ms=args.orch_batch_timeout_ms,
                use_fp16=args.fp16,
                policy_only=(args.leaf_eval != "nn" and args.value_blend == 0.0),
            )
            id_q = ctx.Queue()
            for w in range(n_workers):
                id_q.put(w)
            # Local workers claim the first n_workers slots; any remaining
            # slots (when --serve-slots > 0) go to the bridge.
            cfg["orch_handles_by_worker"] = server_pool.handles_by_worker[:n_workers]
            cfg["orch_id_q"] = id_q
            shard_pids = [p.pid for p in server_pool.procs if p is not None]
            print(f"  eval-server pool ready (shard pids={shard_pids})")
            sys.stdout.flush()

            # Anchor-fraction: second independent server pool running the
            # anchor checkpoint. Workers hold handles to both pools; the
            # per-game routing in `_play_one_pool` picks which to use.
            if args.anchor_checkpoint:
                print(
                    f"  starting ANCHOR eval-server pool "
                    f"({args.anchor_checkpoint.name}) — same shard/batch/timeout "
                    f"as learner pool"
                )
                sys.stdout.flush()
                # Guard (review R3-N1): this anchor pool starts OUTSIDE the main
                # try/finally (at the `try:` below), and the LEARNER pool above is
                # already running + holding VRAM. If anchor init raises — a
                # realistic CUDA OOM loading the 2nd net on the 8GB Xeon/laptop —
                # the exception would bypass teardown and leak (or hang on
                # atexit-join of) the learner pool. Tear it down explicitly first.
                try:
                    anchor_server_pool = start_server_pool(
                        checkpoint_path=str(args.anchor_checkpoint),
                        n_workers=n_workers,
                        n_shards=args.orch_shards,
                        max_batch=args.orch_max_batch,
                        batch_timeout_ms=args.orch_batch_timeout_ms,
                        use_fp16=args.fp16,
                        # Anchor always plays blend=0.0 (pure v2.7), so its server can
                        # always skip the value-head forward — independent of the
                        # learner's --value-blend. Saves VRAM/compute on the 8GB orch
                        # box during Stage B (review Issue 1; OOM-risk margin).
                        policy_only=(args.leaf_eval != "nn"),
                    )
                except BaseException:
                    shutdown_server_pool(server_pool)
                    raise
                cfg["orch_anchor_handles_by_worker"] = (
                    anchor_server_pool.handles_by_worker[:n_workers]
                )
                a_pids = [p.pid for p in anchor_server_pool.procs if p is not None]
                print(f"  anchor eval-server pool ready (shard pids={a_pids})")
                sys.stdout.flush()

            if args.serve_on:
                bridge_handles = server_pool.handles_by_worker[n_workers:]
                bhost, bport = args.serve_on
                bridge = start_bridge(bridge_handles, host=bhost, port=bport)
                print(
                    f"  remote-eval bridge listening on "
                    f"{bridge.host}:{bridge.port} "
                    f"({args.serve_slots} slots for remote workers)"
                )
                sys.stdout.flush()

    try:
        with ctx.Pool(
            processes=n_workers,
            initializer=_worker_init,
            initargs=(str(args.checkpoint or ""), cfg),
        ) as pool:
            for done, (seed, status, n_positions) in enumerate(
                pool.imap_unordered(_play_one_pool, pool_args, chunksize=1), 1
            ):
                n_pos_total += n_positions
                if status == "fresh":
                    fresh += 1
                    if first_fresh_t is None:
                        first_fresh_t = time.perf_counter()
                        elapsed = first_fresh_t - t0
                        eta_min = (remaining * elapsed / n_workers) / 60.0
                        print(
                            f"  [ETA] first fresh game took {elapsed:.0f}s; "
                            f"~{eta_min:.1f} min for {remaining} fresh"
                        )
                        sys.stdout.flush()
                elif status == "failed":
                    failed += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    cached += 1
                if done % max(1, args.games // 10) == 0 or done == args.games:
                    print(
                        f"  ... {done}/{args.games} examined "
                        f"(fresh={fresh}, cached={cached}, "
                        f"skipped={skipped}, failed={failed})"
                    )
                    sys.stdout.flush()
    finally:
        # Stop the bridge BEFORE the server pool so any in-flight remote
        # workers see EOF cleanly before their backing slots disappear.
        if bridge is not None:
            stop_bridge(bridge)
        if server_pool is not None:
            shutdown_server_pool(server_pool)
        if anchor_server_pool is not None:
            shutdown_server_pool(anchor_server_pool)
    elapsed = time.perf_counter() - t0
    print(
        f"\nDone iter={args.iter_idx}: {fresh} fresh + {cached} cached + "
        f"{skipped} skipped + {failed} failed, "
        f"{n_pos_total} positions, {elapsed:.1f}s wallclock"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
