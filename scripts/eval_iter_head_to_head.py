"""Phase 4 head-to-head: iter_N vs iter_(N-1) with NeuralMCTS each side.

Both checkpoints run NeuralMCTS at the same simulation budget (eval-only,
no Dirichlet noise). Alternates which side plays first; per-game JSON
checkpointing so reruns skip cached games.

Output: writes a single ELO-log entry to `<output-root>/elo_log.json`
(appends if the file already exists). Per-game results live under
`<output-root>/eval/iter_<NN>_vs_<MM>/`.

Usage:
  python -u scripts/eval_iter_head_to_head.py \\
      --new-checkpoint checkpoints/selfplay/iter_01.pt \\
      --old-checkpoint checkpoints/selfplay/iter_00.pt \\
      --output-root data/selfplay/calibration \\
      --iter 1 --vs-iter 0 --games 10 --sims 50 --workers 4
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai import eval_provenance as ep
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.elo import update_pair
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
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.remote_evaluators import (
    make_remote_batch_evaluator,
    make_remote_single_evaluator,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class GameResult:
    seed: int
    new_player: int
    sims: int
    score_p0: int
    score_p1: int
    diff: int  # new - old
    won_by_new: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""        # 16-hex deck identity (default keeps old JSON loadable)


# Per-worker globals — both checkpoints loaded once per process in the
# default (no-orchestrator) path. In orchestrator mode `_worker_new` and
# `_worker_old` stay None and the corresponding `_worker_*_handles` point
# at the two server processes (one per net).
_worker_new: CarcassonneNet | None = None
_worker_old: CarcassonneNet | None = None
_worker_device: torch.device | None = None
_worker_sims: int = 0       # new side
_worker_old_sims: int = 0   # old side; == _worker_sims unless an asymmetric-sims A/B
_worker_c_puct: float = 1.5     # symmetric default
_worker_new_c_puct: float = 1.5  # NEW side's c_puct (= _worker_c_puct unless overridden)
_worker_old_c_puct: float = 1.5  # OLD side's c_puct (= _worker_c_puct unless overridden)
_worker_new_fpu: float | None = None  # NEW side FPU reduction (None = legacy q=0)
_worker_old_fpu: float | None = None  # OLD side FPU reduction (None = legacy q=0)
_worker_eval_dir: str = ""
_worker_batch_size: int = 1
_worker_virtual_loss: float = 1.0
_worker_use_fp16: bool = False
_worker_leaf_eval: str = "nn"  # "nn" or "v2_5" — see DECISIONS.md 2026-05-14
# Per-side LeafConfig (used only when leaf_eval == "v2_5"). None → the
# env-built DEFAULT_CONFIG (v2.7). Distinct new/old configs let a single
# head-to-head A/B two leaf variants — e.g. tile-counting vs v2.7.
_worker_new_leaf_cfg = None
_worker_old_leaf_cfg = None
_worker_new_handles: ServerHandles | None = None
_worker_old_handles: ServerHandles | None = None
_worker_new_farm: bool = False  # Path B Step E: new side's Game emits farm scalars
_worker_old_farm: bool = False
# Work-stealing claim (only used with --shared-claim). See carcassonne_ai.claim.
_worker_shared_claim: bool = False
_worker_claim_host: str = ""
_worker_claim_stale_secs: int = 5400


def _result_path(
    eval_dir: str, sims: int, old_sims: int, seed: int, new_player: int
) -> Path:
    # Symmetric runs (old side at the same sims) keep the legacy filename so
    # their cached results stay valid. An asymmetric --old-sims run gets a
    # distinct `o<old_sims>` tag — without it an asymmetric and a symmetric run
    # write the SAME filename, and one would load the other's games as a cache
    # hit, silently feeding the anchor-gate results played at the wrong depth.
    if old_sims == sims:
        return Path(eval_dir) / f"s{sims:04d}_seed{seed:06d}_p{new_player}.json"
    return Path(eval_dir) / (
        f"s{sims:04d}o{old_sims:04d}_seed{seed:06d}_p{new_player}.json"
    )


def _build_work(seed_start: int, games: int, paired: bool) -> list[tuple[int, int]]:
    """The (deck_seed, new_player) list to play.

    Unpaired (default, legacy): game i = deck `seed_start+i`, net color `i%2` —
    net-as-p0 and net-as-p1 use DIFFERENT decks, so first-player advantage is
    averaged over different decks instead of cancelled (round-2 audit G-M2).

    Paired (--paired): each deck is played BOTH ways (same seed, p0 AND p1), so
    within a pair the net sees both sides of the identical deck → first-player
    advantage cancels exactly and variance ~halves. `_result_path` keys on
    (seed, new_player) so the two orientations write distinct files.
    """
    if not paired:
        return [(seed_start + i, i % 2) for i in range(games)]
    work: list[tuple[int, int]] = []
    for d in range(games // 2):
        base = seed_start + d
        work.append((base, 0))
        work.append((base, 1))
    if games % 2:  # odd count → one leftover unpaired game
        work.append((seed_start + games // 2, 0))
    return work


def _try_load(path: Path) -> GameResult | None:
    if not path.exists():
        return None
    try:
        with path.open() as fh:
            return GameResult(**json.load(fh))
    except Exception:
        return None


def _save(eval_dir: str, result: GameResult) -> None:
    path = _result_path(
        eval_dir, result.sims, _worker_old_sims, result.seed, result.new_player
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    # dot-prefixed + host/pid-unique temp (no glob-count, no cross-box collision). Shell-audit #3/#10.
    tmp = path.with_name(f".{path.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    with tmp.open("w") as fh:
        json.dump(asdict(result), fh)
    tmp.replace(path)


def _load_net(path: str, device: torch.device) -> CarcassonneNet:
    ckpt = torch.load(path, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_scalar_features=int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net


def _ckpt_uses_farm_scalars(path: str) -> bool:
    """Peek a checkpoint's n_scalar_features (Path B Step E) → whether its Game
    must emit the 2 farm-control scalars (12-scalar net) to match."""
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    return int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)) > N_SCALAR_FEATURES


def _leaf_config_for(variant: str):
    """Map a --{new,old}-leaf-variant name to a LeafConfig (or None).

    'v2_7' → None (the worker falls back to the env-built DEFAULT_CONFIG).
    'tile_counting' → DEFAULT_CONFIG with the hard deck-aware closure gate on.
    'tile_counting_cont' → DEFAULT_CONFIG with the continuous deck-aware
        closure ramp on (slack=3.0).
    """
    if variant == "v2_7":
        return None
    from dataclasses import replace
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    if variant == "tile_counting":
        return replace(DEFAULT_CONFIG, tile_counting_closure=True)
    if variant == "tile_counting_cont":
        return replace(DEFAULT_CONFIG, closure_continuous_slack=3.0)
    raise ValueError(f"unknown leaf variant: {variant}")


def _apply_value_blend(cfg, blend: float):
    """Set `LeafConfig.value_blend` on `cfg` for Option-2 leaf-value blending.
    `cfg` may be None (the 'v2_7' variant) — then build from DEFAULT_CONFIG.
    blend <= 0 is a no-op (returns `cfg` unchanged, possibly None)."""
    if blend <= 0.0:
        return cfg
    from dataclasses import replace
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    return replace(cfg if cfg is not None else DEFAULT_CONFIG, value_blend=blend)


def _apply_residual_scale(cfg, scale: float):
    """Set `LeafConfig.residual_scale` on `cfg` for the Lever-1 residual leaf
    (leaf = clip(v2.7 + scale·Δ, ±1), Δ = net value head residual). `cfg` may be
    None ('v2_7') — then build from DEFAULT_CONFIG. scale <= 0 is a no-op (returns
    `cfg` unchanged). PER-SIDE so a residual net (scale 0.25) can be compared to a
    pure-policy net (scale 0) in one head-to-head — the value heads differ
    (residual-trained vs outcome-trained), so a global scale would be unfair."""
    if scale <= 0.0:
        return cfg
    from dataclasses import replace
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    return replace(cfg if cfg is not None else DEFAULT_CONFIG, residual_scale=scale)


def _apply_leaf_cap(cfg, cap: float | None):
    """Override `LeafConfig.bonus_cap` and `opp_bonus_cap` (kept symmetric) on
    `cfg`. `cfg` may be None — then build from DEFAULT_CONFIG. `cap` None or
    <= 0 is a no-op (returns `cfg` unchanged, possibly None). Used for the
    per-side cap A/B sweep — same checkpoint, same leaf variant, but each
    side caps the closure-anticipation bonus at a different value."""
    if cap is None or cap <= 0:
        return cfg
    from dataclasses import replace
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    return replace(
        cfg if cfg is not None else DEFAULT_CONFIG,
        bonus_cap=float(cap), opp_bonus_cap=float(cap),
    )


def _effective_blend(leaf_cfg) -> float:
    """The value-head blend λ in force for a side: the LeafConfig's own
    `value_blend` if it has one, else DEFAULT_CONFIG's (env-built) value —
    so a blend set via the CARCASSONNE_V25_VALUE_BLEND env var is honored
    even when no `--leaf-value-blend` flag was passed (e.g. an anchor-gate
    h2h launched by run_phase4_smoke). This must agree with what
    `make_v25_value_wrapper` actually uses, so the server's policy_only
    decision matches whether the value head is needed."""
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    return leaf_cfg.value_blend if leaf_cfg is not None else DEFAULT_CONFIG.value_blend


def _value_head_needed(leaf_cfg) -> bool:
    """True if a side CONSUMES the NN value head: value_blend>0 (Option-2 blend)
    OR residual_scale>0 (Lever-1 residual). The server/leaf must then compute the
    value head for that side.

    R7 fix (outside-review 2026-06-07): the policy_only decision used to key on
    `_effective_blend(...) == 0.0`, which only saw `value_blend` — a residual eval
    (residual_scale>0, value_blend=0) was misclassified as 'no value head needed',
    so the server ran policy_only and the residual leaf silently fell back to
    pure v2.7 with v_nn=0. Counting residual_scale here closes that."""
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    cfg = leaf_cfg if leaf_cfg is not None else DEFAULT_CONFIG
    return cfg.value_blend > 0.0 or cfg.residual_scale > 0.0


def _h2h_side_spec(side, ckpt, leaf_cfg, *, leaf_eval, sims, c_puct, fpu,
                   paired, seed_range, argv):
    """Declared EvaluatorSpec for one NeuralMCTS side of a head-to-head, built
    from the resolved per-side LeafConfig (records the cap/fpu/per-side-c_puct
    that the manifest used to drop). leaf_eval='nn' = raw net value head leaf;
    otherwise the v2.7 wrapper."""
    sched = getattr(leaf_cfg, "closure_p", None) if leaf_cfg is not None else None
    drop3 = isinstance(sched, dict) and 3 not in sched and set(sched) == {1, 2}
    rs = float(getattr(leaf_cfg, "residual_scale", 0.0) or 0.0) if leaf_cfg is not None else 0.0
    vb = float(getattr(leaf_cfg, "value_blend", 0.0) or 0.0) if leaf_cfg is not None else 0.0
    leaf_name = "nn" if leaf_eval == "nn" else "v2_7"
    commit, dirty = ep.git_commit_and_dirty()
    return ep.EvaluatorSpec(
        side=side, agent_class="NeuralMCTS", search_impl="NeuralMCTS",
        leaf_name=leaf_name, leaf_version=("2.7" if leaf_name == "v2_7" else None),
        policy_source="network", sims=sims, c_puct=c_puct, fpu=fpu,
        residual_scale=rs, value_blend=vb,
        cap=getattr(leaf_cfg, "bonus_cap", None) if leaf_cfg is not None else None,
        opp_cap=getattr(leaf_cfg, "opp_bonus_cap", None) if leaf_cfg is not None else None,
        drop_three_open=(drop3 if leaf_cfg is not None else None),
        closure_schedule=(dict(sched) if isinstance(sched, dict) else None),
        checkpoint_path=str(ckpt), checkpoint_sha256=ep.sha256_file(ckpt),
        code_commit=commit, dirty=dirty, seed_range=seed_range, paired=paired,
        eval_script="eval_iter_head_to_head.py", argv=argv)


def _worker_init(
    new_path: str, old_path: str, sims: int, c_puct: float, eval_dir: str,
    batch_size: int, virtual_loss: float, use_fp16: bool = False,
    orch_cfg: dict | None = None, leaf_eval: str = "nn",
    new_leaf_cfg=None, old_leaf_cfg=None, old_sims: int | None = None,
    shared_claim: bool = False, claim_host: str = "",
    claim_stale_secs: int = 5400,
    new_c_puct: float | None = None, old_c_puct: float | None = None,
    new_fpu: float | None = None, old_fpu: float | None = None,
) -> None:
    """Pool initializer.

    Default (no-orchestrator) mode: load both checkpoints into per-worker
    VRAM and store on globals.

    Orchestrator mode (orch_cfg is not None): skip both checkpoint loads;
    pop a worker_id from the shared id_q and build two ServerHandles
    (one per server process) pointing at the per-worker response queues.

    `new_leaf_cfg` / `old_leaf_cfg` are optional `virtual_score_v2.LeafConfig`
    objects (used only under leaf_eval="v2_5"); None → DEFAULT_CONFIG.
    """
    global _worker_new, _worker_old, _worker_device, _worker_sims, _worker_old_sims, _worker_c_puct, _worker_eval_dir
    global _worker_batch_size, _worker_virtual_loss, _worker_use_fp16, _worker_leaf_eval
    global _worker_new_leaf_cfg, _worker_old_leaf_cfg
    global _worker_new_handles, _worker_old_handles
    global _worker_shared_claim, _worker_claim_host, _worker_claim_stale_secs
    global _worker_new_c_puct, _worker_old_c_puct
    global _worker_new_fpu, _worker_old_fpu
    global _worker_new_farm, _worker_old_farm

    # Path B Step E: each side's Game must emit the scalar width its net/server
    # expects. Peek the checkpoints (cheap, once per worker) in BOTH modes —
    # orchestrator workers still build the encode-side Games locally.
    _worker_new_farm = _ckpt_uses_farm_scalars(new_path)
    _worker_old_farm = _ckpt_uses_farm_scalars(old_path)

    _worker_sims = sims
    _worker_old_sims = old_sims if old_sims is not None else sims
    _worker_c_puct = c_puct
    _worker_new_c_puct = new_c_puct if new_c_puct is not None else c_puct
    _worker_old_c_puct = old_c_puct if old_c_puct is not None else c_puct
    _worker_new_fpu = new_fpu
    _worker_old_fpu = old_fpu
    _worker_eval_dir = eval_dir
    _worker_batch_size = batch_size
    _worker_virtual_loss = virtual_loss
    _worker_use_fp16 = use_fp16
    _worker_leaf_eval = leaf_eval
    _worker_new_leaf_cfg = new_leaf_cfg
    _worker_old_leaf_cfg = old_leaf_cfg
    _worker_shared_claim = shared_claim
    _worker_claim_host = claim_host
    _worker_claim_stale_secs = claim_stale_secs

    if orch_cfg is not None:
        _worker_device = torch.device("cpu")
        _worker_new = None
        _worker_old = None
        # Pull global worker_id, then look up the per-pool routing bundle.
        # Pool layer (eval_server_pool.start_server_pool) has already done
        # the worker_id % n_shards math; we just dereference.
        worker_id = orch_cfg["id_q"].get()
        _worker_new_handles = orch_cfg["new_handles_by_worker"][worker_id]
        _worker_old_handles = orch_cfg["old_handles_by_worker"][worker_id]
        return

    if torch.cuda.is_available():
        _worker_device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        _worker_device = torch.device("mps")
    else:
        _worker_device = torch.device("cpu")
    _worker_new = _load_net(new_path, _worker_device)
    _worker_old = _load_net(old_path, _worker_device)


def _play_one(args: tuple[int, int]) -> GameResult | None:
    """None return = work-stealing skip (another box owns this seed). The
    caller filters Nones out of the results aggregation."""
    seed, new_player = args
    result_path = _result_path(
        _worker_eval_dir, _worker_sims, _worker_old_sims, seed, new_player
    )
    cached = _try_load(result_path)
    if cached is not None:
        return cached

    # Work-stealing: atomically claim this (seed, player) before any expensive
    # setup. If another worker — on this box or the other — already owns it,
    # skip; the pool will hand us the next task. Legacy (non-shared) runs skip
    # this entirely. The `.claim` sits next to the eventual `.json`; the
    # already-passed exists-check above is the permanent done-marker.
    if _worker_shared_claim:
        claim_path = result_path.with_suffix(".claim")
        if not _try_claim(
            claim_path, _worker_claim_host, _worker_claim_stale_secs
        ):
            return None

    import random
    random.seed(seed)

    game_new = Game(enable_legal_moves_cache=True, include_farm_scalars=_worker_new_farm)
    game_old = Game(enable_legal_moves_cache=True, include_farm_scalars=_worker_old_farm)
    if _worker_new_handles is not None:
        # Orchestrator mode: two remote evaluators talking to two servers.
        assert _worker_old_handles is not None
        new_eval = make_remote_single_evaluator(_worker_new_handles, game_new)
        old_eval = make_remote_single_evaluator(_worker_old_handles, game_old)
        new_batch_eval = None
        old_batch_eval = None
        if _worker_batch_size > 1:
            new_batch_eval = make_remote_batch_evaluator(
                _worker_new_handles, game_new
            )
            old_batch_eval = make_remote_batch_evaluator(
                _worker_old_handles, game_old
            )
    else:
        assert _worker_new is not None and _worker_old is not None
        # A side that consumes the NN value head (value_blend>0 OR residual_scale>0)
        # needs it computed — R7: residual was previously misclassified policy_only.
        use_policy_only = (
            _worker_leaf_eval != "nn"
            and not _value_head_needed(_worker_new_leaf_cfg)
            and not _value_head_needed(_worker_old_leaf_cfg)
        )
        single_factory = (
            make_single_evaluator_policy_only if use_policy_only
            else make_single_evaluator
        )
        new_eval = single_factory(
            _worker_new, _worker_device, game_new, use_fp16=_worker_use_fp16
        )
        old_eval = single_factory(
            _worker_old, _worker_device, game_old, use_fp16=_worker_use_fp16
        )
        new_batch_eval = None
        old_batch_eval = None
        if _worker_batch_size > 1:
            batch_factory = (
                make_batch_evaluator_policy_only if use_policy_only
                else make_batch_evaluator
            )
            new_batch_eval = batch_factory(
                _worker_new, _worker_device, game_new, use_fp16=_worker_use_fp16
            )
            old_batch_eval = batch_factory(
                _worker_old, _worker_device, game_old, use_fp16=_worker_use_fp16
            )

    # v2.5 leaf-eval swap: replace each side's NN value with virtual_score_v2.
    # Each side carries its own LeafConfig — normally identical (apples-to-
    # apples), but a leaf A/B run gives them different configs. See
    # DECISIONS.md 2026-05-14 + the 2026-05-17 Option-1 plan.
    if _worker_leaf_eval == "v2_5":
        new_eval = make_v25_value_wrapper(new_eval, _worker_new_leaf_cfg)
        old_eval = make_v25_value_wrapper(old_eval, _worker_old_leaf_cfg)
        if new_batch_eval is not None:
            new_batch_eval = make_v25_batch_value_wrapper(new_batch_eval, _worker_new_leaf_cfg)
        if old_batch_eval is not None:
            old_batch_eval = make_v25_batch_value_wrapper(old_batch_eval, _worker_old_leaf_cfg)

    new_mcts = NeuralMCTS(
        game=game_new, evaluator=new_eval, simulations=_worker_sims,
        seed=seed, c_puct=_worker_new_c_puct, fpu_reduction=_worker_new_fpu,
        batch_size=_worker_batch_size, batch_evaluator=new_batch_eval,
        virtual_loss=_worker_virtual_loss,
    )
    old_mcts = NeuralMCTS(
        game=game_old, evaluator=old_eval, simulations=_worker_old_sims,
        seed=seed + 1, c_puct=_worker_old_c_puct, fpu_reduction=_worker_old_fpu,
        batch_size=_worker_batch_size, batch_evaluator=old_batch_eval,
        virtual_loss=_worker_virtual_loss,
    )

    board = game_new.get_init_board()
    dh = deck_hash(board)  # deck identity BEFORE any tile is drawn
    moves = 0
    t0 = time.perf_counter()
    while game_new.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == new_player:
            new_mcts.clear()
            action = new_mcts.best_action(board)
        else:
            old_mcts.clear()
            action = old_mcts.best_action(board)
        board, _ = game_new.get_next_state(board, action)
        moves += 1

    s0, s1 = board.state.scores
    diff = (s0 - s1) if new_player == 0 else (s1 - s0)
    result = GameResult(
        seed=seed, new_player=new_player, sims=_worker_sims,
        score_p0=s0, score_p1=s1, diff=diff,
        won_by_new=(diff > 0), drew=(diff == 0),
        elapsed_s=time.perf_counter() - t0, moves=moves, deck_hash=dh,
    )
    _save(_worker_eval_dir, result)
    return result


def _append_elo_log(
    output_root: Path, iter_n: int, iter_prev: int,
    wins: int, losses: int, draws: int,
) -> dict:
    log_path = output_root / "elo_log.json"
    entries: list[dict]
    if log_path.exists():
        with log_path.open() as fh:
            entries = json.load(fh)
    else:
        entries = []

    # Anchor: previous iter's ELO is whatever the latest log entry recorded
    # for it. iter_-1 baseline is 0.
    prev_elo = 0.0
    for e in entries:
        if e["iter"] == iter_prev:
            prev_elo = float(e["elo_estimate"])
    new_elo, delta = update_pair(
        iter_n_elo_estimate=0.0,
        iter_prev_elo=prev_elo,
        wins=wins, losses=losses, draws=draws,
    )
    entry = {
        "iter": iter_n,
        "vs_iter": iter_prev,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "elo_delta": round(delta, 1),
        "elo_estimate": round(new_elo, 1),
    }
    # Drop any prior entry for this same (iter, vs_iter) pair so a rerun
    # replaces rather than duplicates it — mirrors _append_anchor_gate_log.
    entries = [
        e for e in entries
        if not (e.get("iter") == iter_n and e.get("vs_iter") == iter_prev)
    ]
    entries.append(entry)
    with log_path.open("w") as fh:
        json.dump(entries, fh, indent=2)
    return entry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval_iter_head_to_head")
    p.add_argument("--new-checkpoint", type=Path, required=True)
    p.add_argument("--old-checkpoint", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--iter", type=int, required=True, dest="iter_idx")
    p.add_argument("--vs-iter", type=int, required=True)
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--sims", type=int, default=50,
                   help="MCTS sims/move for the NEW side (and the OLD side "
                        "unless --old-sims is set).")
    p.add_argument("--old-sims", type=int, default=None,
                   help="MCTS sims/move for the OLD side; default = --sims. "
                        "Set different to A/B search depth on the SAME "
                        "checkpoint, e.g. --sims 800 --old-sims 200.")
    p.add_argument("--c-puct", type=float, default=3.0,
                   help="PUCT exploration constant. 2026-05-26 sweep at iter_B1 "
                        "found c=3.0 wins +47.2 elo vs c=1.5 at sims=200 (Phase 2a/2b), "
                        "and J4 confirmed +39.3 elo at sims=800. Was 1.5 until 2026-05-27.")
    p.add_argument(
        "--new-c-puct", type=float, default=None,
        help="Per-side override for c_puct on the NEW side. Defaults to "
             "--c-puct. Use with --old-c-puct + same checkpoint both sides "
             "to A/B PUCT exploration constants (e.g. c=2.0 vs c=1.5).",
    )
    p.add_argument(
        "--old-c-puct", type=float, default=None,
        help="Per-side override for c_puct on the OLD side (see --new-c-puct).",
    )
    p.add_argument(
        "--new-fpu", type=float, default=None,
        help="FPU reduction for the NEW side (round-2 audit F-D-FPU). None "
             "(default) = legacy optimistic-zero (unvisited child q=0). A float r "
             "uses q = parent.Q - r. A/B vs --old-fpu with same checkpoint both "
             "sides to test FPU (e.g. --new-fpu 0.2 --old-fpu none-equivalent).",
    )
    p.add_argument(
        "--old-fpu", type=float, default=None,
        help="FPU reduction for the OLD side (see --new-fpu). Default None = "
             "legacy q=0 (the current production behavior).",
    )
    p.add_argument("--workers", type=int, default=8,
                   help="Pool workers. Default 8 leaves SMT headroom for "
                        "other workloads on a 5800X. For dedicated runs, "
                        "W=16 is the empirical local optimum (measured "
                        "2026-05-09 on RTX 5060 Ti).")
    p.add_argument("--seed-start", type=int, default=1_000_000_000,
                   help="Eval seed base. Default 1e9 keeps it FAR above self-play "
                        "seeds (iter*10_000+game_idx) — round-2 audit G-M6 found "
                        "the old 900k floor collides with self-play at iter>=80, "
                        "contaminating evals with trained-on decks.")
    p.add_argument("--paired", action="store_true",
                   help="G-M2: play each deck BOTH colors (seed,p0)+(seed,p1) so "
                        "first-player advantage cancels within the pair and "
                        "variance ~halves. --games is the TOTAL (= 2 x decks); "
                        "use an even number. Strongly preferred for verdicts.")
    p.add_argument(
        "--batch-size", type=int, default=1,
        help="NeuralMCTS batch size for virtual-loss / batched-eval mode "
             "during head-to-head. 1 (default) = serial.",
    )
    p.add_argument(
        "--virtual-loss", type=float, default=1.0,
        help="W-penalty for in-flight nodes; only matters when --batch-size > 1.",
    )
    p.add_argument(
        "--fp16", action="store_true",
        help="Run network forward passes under torch.amp.autocast(fp16) on "
             "CUDA. Default off.",
    )
    p.add_argument(
        "--no-elo-log", action="store_true",
        help="Skip writing to elo_log.json. Use for ad-hoc anchor evals "
             "(e.g. iter_29 vs warmstart_canonical) that shouldn't pollute "
             "the chained ELO record.",
    )
    p.add_argument(
        "--orchestrator", action="store_true",
        help="GPU inference-server mode (2 servers, one per net). Workers "
             "are CPU-only and send requests over IPC. Default off; "
             "numerically identical to per-worker path within float32 noise.",
    )
    p.add_argument(
        "--leaf-eval", choices=["nn", "v2_5"], default="nn",
        help="Source of the leaf VALUE during MCTS (applied to BOTH sides "
             "for apples-to-apples comparison). 'nn' (default) uses each "
             "net's value head. 'v2_5' uses tanh(virtual_score_v2/15) for "
             "both sides, matching local production (DECISIONS.md 2026-05-14). "
             "Priors always come from the network — only the leaf value "
             "source changes.",
    )
    p.add_argument(
        "--new-leaf-variant",
        choices=["v2_7", "tile_counting", "tile_counting_cont"], default="v2_7",
        help="LeafConfig variant for the NEW side (only under --leaf-eval v2_5). "
             "'v2_7' = the env-built default. 'tile_counting' = v2.7 + the hard "
             "deck-aware closure gate. 'tile_counting_cont' = v2.7 + the "
             "continuous deck-aware closure ramp (Option-1 plan, 2026-05-17). "
             "Set this different from --old-leaf-variant to A/B two leaves "
             "in one run.",
    )
    p.add_argument(
        "--old-leaf-variant",
        choices=["v2_7", "tile_counting", "tile_counting_cont"], default="v2_7",
        help="LeafConfig variant for the OLD side. See --new-leaf-variant.",
    )
    p.add_argument(
        "--new-leaf-value-blend", type=float, default=0.0,
        help="Option 2 (2026-05-17): blend the NN value head into the NEW "
             "side's v2.5 leaf — leaf = (1-λ)·tanh(vs2/15) + λ·v_nn. "
             "0.0 = pure heuristic leaf. λ>0 forces the NEW server pool to "
             "compute the value head (no policy-only fast path).",
    )
    p.add_argument(
        "--old-leaf-value-blend", type=float, default=0.0,
        help="Value-head blend λ for the OLD side. See --new-leaf-value-blend.",
    )
    p.add_argument(
        "--new-leaf-residual-scale", type=float, default=0.0,
        help="Lever-1 residual scale for the NEW side: leaf = clip(v2.7 + scale·Δ, "
             "±1), Δ = the NN value-head residual. 0.0 = pure v2.7 leaf. PER-SIDE so "
             "a residual net (e.g. 0.25) can be compared to a pure-policy net (0.0) "
             "in one head-to-head. Forces the NEW server to compute the value head.",
    )
    p.add_argument(
        "--old-leaf-residual-scale", type=float, default=0.0,
        help="Residual scale for the OLD side. See --new-leaf-residual-scale.",
    )
    p.add_argument(
        "--new-leaf-cap", type=float, default=None,
        help="Override `LeafConfig.bonus_cap` / `opp_bonus_cap` for the NEW "
             "side (only under --leaf-eval v2_5). None (default) = use the "
             "variant's built-in cap (env-built DEFAULT_CONFIG). Set this "
             "different from --old-leaf-cap to A/B the cap with the same "
             "checkpoint both sides.",
    )
    p.add_argument(
        "--old-leaf-cap", type=float, default=None,
        help="Override the leaf cap for the OLD side. See --new-leaf-cap.",
    )
    p.add_argument("--orch-max-batch", type=int, default=256)
    p.add_argument("--orch-batch-timeout-ms", type=float, default=2.0)
    p.add_argument(
        "--shared-claim", action="store_true",
        help="Work-stealing mode: both boxes run the SAME command pointed at "
             "ONE --output-root on a shared filesystem (CIFS/NFS); each worker "
             "atomically claims (O_CREAT|O_EXCL on a .claim sidecar next to "
             "the per-game JSON) the next unplayed (seed, player) before "
             "playing it. Auto load-balances + crash-tolerant. See "
             "carcassonne_ai.claim and run_selfplay_iter.py.",
    )
    p.add_argument(
        "--claim-stale-secs", type=int, default=5400,
        help="A claim with mtime older than this is re-claimable (default 90 "
             "min — comfortably > a sims=800 game). Flag is exposed so tests "
             "can lower it.",
    )
    p.add_argument(
        "--claim-host", type=str, default=socket.gethostname(),
        help="Identity written into the claim body (host:pid:unix_ts). Default "
             "is the local hostname; override on tests / single-host smokes "
             "to force distinct identities.",
    )
    p.add_argument(
        "--orch-shards", type=int, default=1,
        help="Number of parallel eval-server processes per net (new+old "
             "each get their own pool of N shards). Default 1 = single "
             "server per net (back-compat). VRAM cost ~2 GB × N × 2 nets; "
             "watch the VRAM budget at high shard counts.",
    )
    args = p.parse_args(argv)

    eval_dir = (
        args.output_root / "eval" /
        f"iter_{args.iter_idx:02d}_vs_{args.vs_iter:02d}"
    )
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Resolve per-side leaf configs up-front so the manifest can record the FULL
    # effective config (cap/value-blend/residual) — previously dropped (R1/R7).
    new_leaf_cfg = _apply_leaf_cap(
        _apply_residual_scale(
            _apply_value_blend(_leaf_config_for(args.new_leaf_variant), args.new_leaf_value_blend),
            args.new_leaf_residual_scale),
        args.new_leaf_cap)
    old_leaf_cfg = _apply_leaf_cap(
        _apply_residual_scale(
            _apply_value_blend(_leaf_config_for(args.old_leaf_variant), args.old_leaf_value_blend),
            args.old_leaf_residual_scale),
        args.old_leaf_cap)

    _eff_old_sims = args.old_sims or args.sims
    _eff_new_c = args.new_c_puct if args.new_c_puct is not None else args.c_puct
    _eff_old_c = args.old_c_puct if args.old_c_puct is not None else args.c_puct
    # R5-fix: paired+odd games plays a leftover unpaired seed at seed_start+games//2,
    # so the half-open [start,end) record needs (games+1)//2 to cover it (even counts unchanged).
    _seed_range = [args.seed_start,
                   args.seed_start + ((args.games + 1) // 2 if args.paired else args.games)]

    # NOTE: no hard seed-floor guard here — this harness is also invoked by
    # in-training anchor gates that legitimately reuse self-play decks. The
    # default --seed-start is already 1e9 (G-M6); clean reruns pass 1e9+.

    _new_spec = _h2h_side_spec("A_new", args.new_checkpoint, new_leaf_cfg,
                               leaf_eval=args.leaf_eval, sims=args.sims, c_puct=_eff_new_c,
                               fpu=args.new_fpu, paired=args.paired, seed_range=_seed_range,
                               argv=sys.argv[1:])
    _old_spec = _h2h_side_spec("B_old", args.old_checkpoint, old_leaf_cfg,
                               leaf_eval=args.leaf_eval, sims=_eff_old_sims, c_puct=_eff_old_c,
                               fpu=args.old_fpu, paired=args.paired, seed_range=_seed_range,
                               argv=sys.argv[1:])
    _ev_block = ep.build_eval_provenance([_new_spec, _old_spec],
                                         kind="eval_iter_head_to_head", argv=sys.argv[1:])

    # self-describing run manifest (provenance: game/code_rev/leaf-env + the
    # both-sides evaluator block with the dropped cap/fpu/per-side-c_puct) — D21 + R1/R7.
    write_manifest(eval_dir, kind="eval_iter_head_to_head", game=game_tag(Game()),
                   config={"new_checkpoint": str(args.new_checkpoint),
                           "old_checkpoint": str(args.old_checkpoint),
                           "iter": args.iter_idx, "vs_iter": args.vs_iter,
                           "games": args.games, "sims": args.sims,
                           "old_sims": _eff_old_sims,
                           "c_puct": args.c_puct,
                           "new_c_puct": _eff_new_c, "old_c_puct": _eff_old_c,
                           "new_fpu": args.new_fpu, "old_fpu": args.old_fpu,
                           "new_leaf_cap": args.new_leaf_cap, "old_leaf_cap": args.old_leaf_cap,
                           "paired": args.paired,
                           "seed_start": args.seed_start, "leaf_eval": args.leaf_eval,
                           "new_leaf_variant": args.new_leaf_variant,
                           "old_leaf_variant": args.old_leaf_variant,
                           "new_leaf_value_blend": args.new_leaf_value_blend,
                           "old_leaf_value_blend": args.old_leaf_value_blend},
                   evaluator=_ev_block)

    # Auto-cap removed 2026-05-09 (see run_selfplay_iter.py for rationale).
    # Note: head-to-head loads TWO networks per worker (2× GPU memory vs
    # self-play). Should still be fine on 16GB cards at W=16 (~200MB ×
    # 16 × 2 = 6.4GB), but watch nvidia-smi if you scale up.
    n_workers = min(args.workers, args.games)

    pool_args = _build_work(args.seed_start, args.games, args.paired)
    print(
        f"head-to-head: iter_{args.iter_idx:02d} vs iter_{args.vs_iter:02d}, "
        f"{args.games} games at sims={args.sims} (old side: {args.old_sims or args.sims}), "
        f"c_puct={args.c_puct}"
        + (f" (new={args.new_c_puct} old={args.old_c_puct})"
           if (args.new_c_puct is not None or args.old_c_puct is not None) else "")
        + ", "
        f"{n_workers} workers, eval_dir={eval_dir}, "
        f"orchestrator={args.orchestrator}, leaf_eval={args.leaf_eval}"
        + (
            f", value_blend new/old="
            f"{args.new_leaf_value_blend}/{args.old_leaf_value_blend}"
            if (args.new_leaf_value_blend or args.old_leaf_value_blend) else ""
        )
    )
    sys.stdout.flush()

    # (new_leaf_cfg / old_leaf_cfg were resolved above for the manifest.)

    t0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    results: list[GameResult] = []

    # Orchestrator: two server pools (one per net). Each pool can be sharded
    # for GIL bypass; routing is by worker_id % n_shards within each pool.
    new_pool = None
    old_pool = None
    orch_cfg: dict | None = None
    if args.orchestrator:
        print(
            f"  starting eval-server pools "
            f"(shards={args.orch_shards}, "
            f"max_batch={args.orch_max_batch}, "
            f"timeout={args.orch_batch_timeout_ms}ms, fp16={args.fp16})…"
        )
        sys.stdout.flush()
        # Per-side policy_only: a side that blends the NN value head into its
        # leaf (value_blend > 0) needs the server to compute the value head.
        new_pool = start_server_pool(
            checkpoint_path=str(args.new_checkpoint),
            n_workers=n_workers,
            n_shards=args.orch_shards,
            max_batch=args.orch_max_batch,
            batch_timeout_ms=args.orch_batch_timeout_ms,
            use_fp16=args.fp16,
            policy_only=(args.leaf_eval != "nn" and not _value_head_needed(new_leaf_cfg)),
        )
        old_pool = start_server_pool(
            checkpoint_path=str(args.old_checkpoint),
            n_workers=n_workers,
            n_shards=args.orch_shards,
            max_batch=args.orch_max_batch,
            batch_timeout_ms=args.orch_batch_timeout_ms,
            use_fp16=args.fp16,
            policy_only=(args.leaf_eval != "nn" and not _value_head_needed(old_leaf_cfg)),
        )
        id_q = ctx.Queue()
        for w in range(n_workers):
            id_q.put(w)
        orch_cfg = {
            "new_handles_by_worker": new_pool.handles_by_worker,
            "old_handles_by_worker": old_pool.handles_by_worker,
            "id_q": id_q,
        }
        new_pids = [p.pid for p in new_pool.procs if p is not None]
        old_pids = [p.pid for p in old_pool.procs if p is not None]
        print(
            f"  eval-server pools ready "
            f"(new pids={new_pids}, old pids={old_pids})"
        )
        sys.stdout.flush()

    try:
        with ctx.Pool(
            processes=n_workers,
            initializer=_worker_init,
            initargs=(
                str(args.new_checkpoint), str(args.old_checkpoint),
                args.sims, args.c_puct, str(eval_dir),
                args.batch_size, args.virtual_loss, args.fp16,
                orch_cfg, args.leaf_eval,
                new_leaf_cfg, old_leaf_cfg, args.old_sims,
                args.shared_claim, args.claim_host, args.claim_stale_secs,
                args.new_c_puct, args.old_c_puct,
                args.new_fpu, args.old_fpu,
            ),
        ) as pool:
            scanned = 0
            for r in pool.imap_unordered(_play_one, pool_args, chunksize=1):
                scanned += 1
                if r is None:
                    # Work-stealing skip: another box owns this seed. Don't
                    # inflate the running tally.
                    continue
                results.append(r)
                played = len(results)
                wins_so_far = sum(1 for x in results if x.won_by_new)
                if played % max(1, args.games // 5) == 0 or scanned == args.games:
                    print(
                        f"  ... scanned {scanned}/{args.games}, "
                        f"this box played {played}, new wins {wins_so_far}/{played}"
                    )
                    sys.stdout.flush()
    finally:
        if new_pool is not None:
            shutdown_server_pool(new_pool)
        if old_pool is not None:
            shutdown_server_pool(old_pool)
    elapsed = time.perf_counter() - t0

    # Shared-claim: this box only played its claimed share of the seed range,
    # but the other box wrote the rest to the same eval_dir. Re-load all
    # on-disk JSONs for the expected seed range so the final summary reflects
    # the CONSOLIDATED cross-box outcome, not just this box's contribution.
    if args.shared_claim:
        consolidated = []
        for seed, new_player in _build_work(args.seed_start, args.games, args.paired):
            on_disk = _try_load(_result_path(
                str(eval_dir), args.sims,
                args.old_sims if args.old_sims is not None else args.sims,
                seed, new_player,
            ))
            if on_disk is not None:
                consolidated.append(on_disk)
        results = consolidated

    n_played = len(results)
    wins = sum(1 for r in results if r.won_by_new)
    draws = sum(1 for r in results if r.drew)
    losses = n_played - wins - draws
    avg_diff = (sum(r.diff for r in results) / n_played) if n_played else 0.0

    if args.no_elo_log:
        # Compute the standalone delta (anchor at 0) for reporting only;
        # don't touch the chain log.
        from carcassonne_ai.elo import update_pair
        _new_elo, delta = update_pair(
            iter_n_elo_estimate=0.0, iter_prev_elo=0.0,
            wins=wins, losses=losses, draws=draws,
        )
        print(
            f"\nANCHOR EVAL ({args.new_checkpoint.name} vs {args.old_checkpoint.name}): "
            f"{wins}W/{draws}D/{losses}L, avg diff {avg_diff:+.1f}, "
            f"elo_delta {delta:+.1f} (no log entry written), "
            f"wallclock {elapsed:.1f}s"
        )
    else:
        entry = _append_elo_log(
            args.output_root, args.iter_idx, args.vs_iter, wins, losses, draws
        )
        print(
            f"\niter_{args.iter_idx:02d} vs iter_{args.vs_iter:02d}: "
            f"{wins}W/{draws}D/{losses}L, avg diff {avg_diff:+.1f}, "
            f"elo_delta {entry['elo_delta']:+.1f} → elo_estimate {entry['elo_estimate']:+.1f}, "
            f"wallclock {elapsed:.1f}s"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
