#!/usr/bin/env python3
"""FAIR-champion DISTILLATION emitter — records the blind-PIMC champion's POOLED
visit distribution (policy target) + game-outcome value, for the distill-flywheel.

Design / spec: measurement/distill_flywheel_20260715/DESIGN_FAIR_ADDENDUM.md
(the FAIR pivot — distil the blind PIMC champion, NOT the clairvoyant one, to avoid
strategy-fusion bias). This is the STAGE-1 emitter (pure fair-champion distillation).

DIFFERS from the sibling value-only emitter `gen_fair_selfplay.py` (which it is copied
from) in five ways (addendum Changes 1-5):
  1. AGENT = the PUCT-priors champion `FairHeuristicPriorAgent` (was the legacy
     random-expansion `FairHeuristicMCTSAgent`), built from the production fair_deploy
     config: HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, value_norm=15.0,
     leaf_quantize="float", final_select="visits"), sims=688, k_dets=4,
     exact_endgame=True, exact_max_k=2 (PRODUCTION.yaml fair_deploy, CL-054/CL-051).
  3. POLICY TARGET = the agent's POOLED root-visit distribution `agent.last_pooled_visits`
     (== agg_n, summed root-child visit counts over the k_dets determinization trees),
     normalized over the legal mask. Trajectory rows -> aux_mask=True; forced moves ->
     a one-hot policy (aux_mask=True, trivial); exact-endgame / pathological rows ->
     value-only (aux_mask=False). NOTE: the champion PLAYS by pooled-Q (`pooled_q_argmax`),
     so argmax(policy) (= pooled-N argmax) is NOT necessarily the played move — the
     recorded policy is the pooled-VISIT target, the pick is pooled-Q.
  4. VALUE TARGET = the game OUTCOME tanh((p0-p1)/15) mover-POV, backfilled from the
     FINAL score (an ABSOLUTE value head at the champion's value_norm=15; distinct from
     the sibling emitter's per-move residual proxy).
  5. LEAF ENV = curve125 (the production champion leaf), NOT the fair scripts' curve100
     default. The `_CANON_ENV` below is curve125 and every gen invocation also sources
     scripts/distill_flywheel/champ_env.sh (belt-and-suspenders). Verify the resolved
     leaf CONFIG VALUES (curve125, cap8, closure_p default) in the manifest; the runtime
     frozen-config-hash is recorded for provenance (the PRODUCTION.yaml fingerprint
     158f17ff is STALE — dataclass drift; verify VALUES not the hash string).

OWNERSHIP: the fair emitter produces NO ownership labels (it does not reconstruct the
terminal feature ownership the way selfplay.py does). Ownership planes are therefore
DUMMY ZEROS on every row; the stage-1 driver trains with `--aux-weight 0` so the
ownership head is never trained on those dummies (policy CE + value MSE only, which is
exactly the distillation-fidelity ruler probe_metrics.py measures).

PARALLELISM / RESUME / DETACH / manifest: verbatim the sibling emitter — one game per
seed -> one `seed_<seed>.npz` shard; `multiprocessing.Pool`; `--shared-claim` O_EXCL
`.claim` work-stealing over the CIFS share; idempotent resume (existing shard skipped).
DETACH any real run (`nohup … & disown` / `setsid`).

Usage:
  # 1-game plumbing smoke (single process):
  scripts/distill_flywheel/gen_fair_distill.py --games 1 --k-dets 2 --sims 32 \
      --workers 1 --out /tmp/fair_distill_smoke
  # production stage-1 (champ gen, both boxes, shared-claim, source champ_env.sh first):
  source scripts/distill_flywheel/champ_env.sh
  nice -n 19 .venv/bin/python -u scripts/distill_flywheel/gen_fair_distill.py \
      --games 600 --k-dets 4 --sims 688 --workers 16 --seed-start 700000000 \
      --out /mnt/c/carc-shared/distill_flywheel_20260715/iter_00 --shared-claim
"""
from __future__ import annotations

import os

# curve125 champion leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Mirrors scripts/distill_flywheel/champ_env.sh VERBATIM so the
# script is correct even when champ_env.sh was not sourced; `setdefault` means an
# already-exported champ_env.sh value (also curve125) wins, never curve100.
_CANON_ENV = {
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",   # curve125 (CRITICAL)
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
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse
import json
import math
import multiprocessing as mp
import random
import socket
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

from carcassonne_ai.aux_targets import OWNERSHIP_PLANES  # noqa: E402
from carcassonne_ai.claim import try_claim as _try_claim  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_fair_net_prior_batch_evaluator,
    make_fair_net_prior_evaluator,
)
from carcassonne_ai.run_manifest import code_rev, game_tag, write_manifest  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
from carcassonne_ai.warmstart import GameDataset  # noqa: E402

# Champion value_norm (HEURISTIC_VALUE_NORM). The game OUTCOME value target is
# tanh((p0-p1)/15) — the graded margin at the champion's scale, mover-POV. Same
# convention/scale as selfplay.py's "score_diff" value_target.
_OUTCOME_NORM = 15.0


def _resolved_leaf_hash() -> str | None:
    """The runtime frozen-config-hash of the resolved champion leaf — PROVENANCE
    ONLY (do NOT gate on it: the PRODUCTION.yaml fingerprint 158f17ff is stale from
    LeafConfig dataclass drift). Best-effort; None if the snapshot helper is absent."""
    try:
        from snapshot import _frozen_config_hash  # scripts/measurement_infra
        return _frozen_config_hash(DEFAULT_CONFIG)
    except Exception:
        return None


def _champion_cfg(c_puct: float, tau_p: float, value_norm: float) -> HeuristicPriorConfig:
    """The production fair_deploy champion knobs (leaf_cfg=None -> env-built curve125
    DEFAULT_CONFIG)."""
    return HeuristicPriorConfig(
        c_puct=c_puct, tau_p=tau_p, value_norm=value_norm,
        leaf_quantize="float", final_select="visits", leaf_cfg=None,
    )


def _load_net(path, device="cpu"):
    """Load a SIGHTED (81ch/42-scalar) CarcassonneNet checkpoint for the fair-net
    PRIORS path (per-worker CPU net — the non-orch net mode). Mirrors
    eval_fair_puct._load_net / verify_sighted_orch_parity (arch dims live in the
    ckpt). torch + CarcassonneNet are imported lazily so the net-free champion path
    (the default) stays torch-free at startup."""
    import torch

    from carcassonne_ai.network import CarcassonneNet
    ck = torch.load(path, map_location=device, weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78))
    n_scalar = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(
        n_filters=ck.get("n_filters", 96), n_blocks=ck.get("n_blocks", 6),
        n_input_channels=n_ch, n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.eval()
    if n_ch != 81 or n_scalar != 42 or not bool(ck.get("sighted", False)):
        print(f"[warn] --net-ckpt is not an 81ch/42-scalar sighted net "
              f"(n_ch={n_ch} n_scalar={n_scalar} sighted={ck.get('sighted')}); "
              "the fair-net-prior path expects the sighted rep.", file=sys.stderr)
    return net


def _shard_path(out: Path, seed: int) -> Path:
    return out / f"seed_{seed:012d}.npz"


def _actions_path(out: Path, seed: int) -> Path:
    """Per-game ACTION LOG shard (2026-07-20). One json per game keeps the writers
    lock-free over the CIFS share (a shared jsonl would interleave); merge with
    scripts/distill_flywheel/collect_action_logs.py into a root_replay games jsonl."""
    return out / "actions" / f"seed_{seed:012d}.json"


def _done_path(out: Path, seed: int, actions_only: bool) -> Path:
    """The resume/claim key: the npz shard normally, the action log in --actions-only."""
    return _actions_path(out, seed) if actions_only else _shard_path(out, seed)


def play_fair_distill_game_to_dataset(
    seed: int, *, k_dets: int, sims: int,
    c_puct: float = 1.5, tau_p: float = 5.0, value_norm: float = 15.0,
    exact_endgame: bool = True, exact_max_k: int = 2,
    sighted: bool = False,
    net=None, handles=None, eval_sighted_game=None,
    window_size: int = 25, max_plies: int = 400,
    batch_size: int = 1,
) -> tuple[GameDataset | None, dict]:
    """Play ONE FAIR champion self-play game (FairHeuristicPriorAgent vs itself) and
    return (GameDataset, info).

    STAGE-1 (default, net=None and handles=None): the NET-FREE champion — the fair
    PIMC agent with the FROZEN v2.9 heuristic priors + heuristic leaf value (byte-
    unchanged from the pure-distillation emitter). STAGE-2 (net or handles given):
    the SEVERED-VALUE-LOOP fair-net agent — the trained net's POLICY head supplies the
    PUCT priors while the value stays the frozen champion leaf
    (make_fair_net_prior_evaluator, passed via `evaluator=`). Only the SEARCH priors
    change; the RECORDED targets (pooled-visit policy + game-outcome value) and the
    whole agg_n / value-backfill path are IDENTICAL to stage 1.

    One row per ply:
      * obs + scalars from the encoder: DEFAULT non-sighted (78ch/10, matches
        warmstart_canonical.pt); with sighted=True bag-aware (81ch/42, matches
        m2_sighted/warmstart_sighted.pt) — ONLY the obs encoding changes,
      * policies = normalized pooled root-visit distribution (aux_mask=True rows);
        forced -> one-hot; exact-endgame/pathological -> zeros (aux_mask=False),
      * valid_masks = the legal mask (aux rows) / zeros (value-only rows),
      * values = mover-POV game OUTCOME tanh((p0-p1)/15) backfilled from the FINAL score,
      * ownership = DUMMY zeros (the fair emitter has no ownership labels; the driver
        trains --aux-weight 0),
      * aux_mask = True for full-trajectory (policy) rows, False for value-only rows.
    """
    random.seed(seed)  # seeds the deck shuffle (get_init_board uses the global RNG)
    game = Game(enable_legal_moves_cache=True, window_size=window_size)   # referee / deck driver
    # OBS encoder. DEFAULT (sighted=False): NON-sighted 78ch board / 10 base scalars —
    # matches the warm-from net checkpoints/warmstart_canonical.pt (stem in_channels=78)
    # and the 96x6 production representation. With sighted=True: bag-aware 81ch / 42
    # scalars — matches m2_sighted/warmstart_sighted.pt. ONLY the observation encoding
    # changes; the referee `game` (deck driver) and the champion `agent` (below) are
    # identical, so the recorded policy/value TARGETS are byte-identical either way
    # (fair-safe — the sighted extras are the order-agnostic public bag + board-derived
    # farm planes, no deck-order/future-draw leak). See SIGHTED_SCOPE.md.
    encoder = Game(sighted=sighted, window_size=window_size)             # 78ch/10 or (sighted) 81ch/42
    champ_cfg = _champion_cfg(c_puct, tau_p, value_norm)
    agent_game = Game(enable_legal_moves_cache=True, window_size=window_size)
    # STAGE-2 fair-net-prior evaluator (severed value loop): net POLICY -> priors,
    # FROZEN champion leaf -> value. Built ONLY when a net/orch handle is supplied;
    # default (both None) keeps the byte-for-byte net-free champion agent below.
    fair_net_evaluator = None
    fair_net_batch_evaluator = None
    if net is not None or handles is not None:
        fair_net_evaluator = make_fair_net_prior_evaluator(
            champ_cfg, net=net, handles=handles, sighted_game=eval_sighted_game,
        )
        # LATENCY (2026-07-16): batch_size>1 collects that many leaves under virtual
        # loss and evaluates them in ONE forward instead of one blocking IPC+GPU
        # round-trip per expansion. Only built when batching is actually requested —
        # batch_size=1 keeps the byte-for-byte serial path (and FairHeuristicPriorAgent
        # rejects a batch_evaluator at batch_size=1 rather than silently ignoring it).
        # The NET-FREE champion (stage-1, net=None+handles=None) NEVER batches: its
        # leaf is in-process Cython with no round-trip to amortize, and it must stay
        # byte-identical (it is the teacher AND the ruler).
        if batch_size > 1:
            fair_net_batch_evaluator = make_fair_net_prior_batch_evaluator(
                champ_cfg, net=net, handles=handles, sighted_game=eval_sighted_game,
            )
    agent = FairHeuristicPriorAgent(
        agent_game,
        cfg=champ_cfg,
        sims=sims, k_dets=k_dets, seed=seed,
        exact_endgame=exact_endgame, exact_max_k=exact_max_k,
        evaluator=fair_net_evaluator,
        batch_size=(batch_size if fair_net_evaluator is not None else 1),
        batch_evaluator=fair_net_batch_evaluator,
    )

    board = game.get_init_board()
    A = game.get_action_size()
    obs_list: list[np.ndarray] = []
    scl_list: list[np.ndarray] = []
    mover_list: list[int] = []
    policy_list: list[np.ndarray] = []
    mask_list: list[np.ndarray] = []
    aux_list: list[bool] = []
    action_list: list[int] = []      # ACTION LOG (2026-07-20): (deck_seed, actions) root_replay contract
    n_aux = n_valonly = 0
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mover = board.state.current_player
        obs, scl = encoder.get_canonical_form(board, mover)   # NEVER mutates board
        action = agent.move(board)                            # deepcopies internally; board unmutated
        pv = agent.last_pooled_visits                         # pooled root-visit dict (or {} / None)

        policy = np.zeros(A, dtype=np.float32)
        valid = np.zeros(A, dtype=bool)
        aux = False
        if pv:  # non-empty dict -> full-trajectory (or forced one-hot) POLICY row
            for a, n in pv.items():
                policy[int(a)] = float(n)
            s = float(policy.sum())
            if s > 0.0:
                policy /= s
                valid = game.get_valid_moves(board).astype(bool)
                aux = True
        if aux:
            n_aux += 1
        else:
            policy = np.zeros(A, dtype=np.float32)   # value-only: dummy policy/mask
            valid = np.zeros(A, dtype=bool)
            n_valonly += 1

        obs_list.append(obs)
        scl_list.append(scl)
        mover_list.append(mover)
        policy_list.append(policy)
        mask_list.append(valid)
        aux_list.append(aux)
        action_list.append(int(action))

        board, _ = game.get_next_state(board, action)
        plies += 1

    s0, s1 = int(board.state.scores[0]), int(board.state.scores[1])
    terminated = game.get_game_ended(board, 0) != 0.0
    info = {"seed": seed, "plies": plies, "score_p0": s0, "score_p1": s1,
            "diff": s0 - s1, "terminated": terminated,
            "n_aux": n_aux, "n_valonly": n_valonly,
            "exact_moves": agent.exact_moves, "heur_moves": agent.heur_moves,
            "n_timeouts": agent.n_timeouts,
            # ACTION LOG (2026-07-20): the complete move sequence from the seeded init
            # board. With `seed` (= the deck seed) this is the root_replay lossless
            # contract — replay_actions(seed, actions, ply) reconstructs ANY position the
            # champion actually reached. Recorded unconditionally (a few KB); WRITTEN to
            # disk only under --log-actions.
            "actions": action_list}
    if not terminated:
        info["error"] = f"game did not terminate in {max_plies} plies"
        return None, info
    if not obs_list:
        info["error"] = "no plies recorded"
        return None, info

    # value = mover-POV game OUTCOME tanh((p0-p1)/15) backfilled from the FINAL score.
    z_p0 = math.tanh((s0 - s1) / _OUTCOME_NORM)
    values = np.array([z_p0 if m == 0 else -z_p0 for m in mover_list], dtype=np.float32)

    N = len(obs_list)
    W = window_size
    ds = GameDataset(
        boards=np.stack(obs_list).astype(np.float32, copy=False),      # (N,C,W,W) C=78 (or 81 sighted)
        scalars=np.stack(scl_list).astype(np.float32, copy=False),     # (N,S) S=10 (or 42 sighted)
        policies=np.stack(policy_list).astype(np.float32, copy=False), # (N,A) pooled-visit / one-hot / dummy
        values=values,                                                 # (N,) mover-POV outcome
        valid_masks=np.stack(mask_list),                               # (N,A) legal (aux) / zeros
        ownership=np.zeros((N, OWNERSHIP_PLANES, W, W), dtype=np.float32),  # DUMMY (driver aux-weight 0)
        aux_mask=np.array(aux_list, dtype=bool),                       # mixed: True=policy row, False=value-only
    )
    info["rows"] = N
    return ds, info


_W: dict = {}


def _worker_init(k_dets, sims, c_puct, tau_p, value_norm, exact_endgame, exact_max_k,
                 sighted, window_size, shared_claim, claim_host, claim_stale,
                 net_ckpt=None, shm_eval_server="", id_q=None, batch_size=1,
                 log_actions=False, actions_only=False, action_meta=None):
    _W.update(k_dets=k_dets, sims=sims, c_puct=c_puct, tau_p=tau_p,
              value_norm=value_norm, exact_endgame=exact_endgame,
              exact_max_k=exact_max_k, sighted=sighted, window_size=window_size,
              shared_claim=shared_claim, claim_host=claim_host, claim_stale=claim_stale,
              batch_size=batch_size, log_actions=log_actions,
              actions_only=actions_only, action_meta=(action_meta or {}))
    # STAGE-2 fair-net-prior wiring (default net-free: both stay None). Set up ONCE per
    # worker, reused across every game the worker plays.
    _W["net"] = None
    _W["handles"] = None
    _W["sighted_game"] = None
    if shm_eval_server:
        # carc-orch SHM: the GPU server owns the only sighted (81ch/42) net; this CPU
        # worker reads masked-softmax PRIORS over shared memory. Each worker pops a
        # unique SHM slot from id_q (mirrors eval_fair_puct / clairvoyance_gap). CUDA
        # stays hidden (the module _CANON_ENV sets CUDA_VISIBLE_DEVICES="").
        from carcassonne_ai.shm_eval_handles import connect_shm
        _W["handles"] = connect_shm(shm_eval_server, id_q.get(), 42, 81)
        _W["sighted_game"] = Game(sighted=True)
    elif net_ckpt:
        # per-worker net-on-CPU copy (the gen env hides CUDA; a 7M net ~30MB/worker),
        # loaded once per process, reused across games.
        _W["net"] = _load_net(net_ckpt, device="cpu")
        _W["sighted_game"] = Game(sighted=True)


def _write_action_log(out: Path, seed: int, info: dict, meta: dict) -> None:
    """Write the per-game action log (root_replay GameRecord json). Atomic
    (tmp + os.replace) so a torn CIFS write can never masquerade as a done shard."""
    p = _actions_path(out, seed)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"game_id": int(seed), "deck_seed": int(seed),
           "actions": [int(a) for a in info["actions"]],
           "n_plies": int(info["plies"]),
           "score_p0": int(info["score_p0"]), "score_p1": int(info["score_p1"])}
    rec.update(meta)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec) + "\n")
    os.replace(tmp, p)


def _play_one(args) -> dict | None:
    out_str, seed = args
    out = Path(out_str)
    actions_only = bool(_W.get("actions_only"))
    p = _shard_path(out, seed)
    done = _done_path(out, seed, actions_only)
    if done.exists():
        return {"seed": seed, "cached": True}
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None
    ds, info = play_fair_distill_game_to_dataset(
        seed, k_dets=_W["k_dets"], sims=_W["sims"], c_puct=_W["c_puct"],
        tau_p=_W["tau_p"], value_norm=_W["value_norm"],
        exact_endgame=_W["exact_endgame"], exact_max_k=_W["exact_max_k"],
        sighted=_W["sighted"], window_size=_W["window_size"],
        batch_size=_W.get("batch_size", 1),
        net=_W.get("net"), handles=_W.get("handles"),
        eval_sighted_game=_W.get("sighted_game"),
    )
    if ds is None:
        info["skipped"] = True
        return info
    if not actions_only:
        ds.save(p)
    if _W.get("log_actions"):
        _write_action_log(out, seed, info, _W.get("action_meta", {}))
    info.pop("actions", None)     # keep the Pool return payload small
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gen_fair_distill")
    ap.add_argument("--games", type=int, required=True, help="number of games (= seeds)")
    ap.add_argument("--k-dets", type=int, default=4, help="determinizations per move (fair PIMC; champion=4)")
    ap.add_argument("--sims", type=int, default=688, help="PUCT sims per determinization (champion k4x688=2752)")
    ap.add_argument("--c-puct", type=float, default=1.5, help="champion PUCT c (fair_deploy)")
    ap.add_argument("--tau-p", type=float, default=5.0, help="champion prior softmax temperature")
    ap.add_argument("--value-norm", type=float, default=15.0, help="champion leaf value tanh norm")
    ap.add_argument("--exact-endgame", dest="exact_endgame", action="store_true", default=True,
                    help="K<=exact_max_k marginalized endgame handoff (champion default ON)")
    ap.add_argument("--no-exact-endgame", dest="exact_endgame", action="store_false",
                    help="pure fair PIMC to the terminal (no marginalized solver)")
    ap.add_argument("--exact-max-k", type=int, default=2, help="fair endgame handoff depth K (champion=2)")
    ap.add_argument("--sighted", action="store_true", default=False,
                    help="use the bag-aware SIGHTED encoder (81ch board / 42 scalars) "
                         "instead of the DEFAULT non-sighted (78ch / 10); ONLY the obs "
                         "encoding changes (policy/value TARGETS identical) — the "
                         "warm-from net must be built for the chosen dims")
    ap.add_argument("--window-size", type=int, default=25)
    ap.add_argument("--workers", type=int, default=None, help="Pool size (default min(cpu,games))")
    ap.add_argument("--seed-start", type=int, default=700_000_000,
                    help="first seed; games use seed_start..seed_start+games-1")
    ap.add_argument("--out", type=str, required=True, help="output dir for seed_*.npz shards")
    ap.add_argument("--shared-claim", action="store_true", help="O_EXCL .claim work-stealing")
    ap.add_argument("--claim-stale-secs", type=int, default=7200)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    # STAGE-2 fair-net-prior mode (additive; default OFF = byte-for-byte net-free champion).
    ap.add_argument("--net-ckpt", type=str, default=None,
                    help="STAGE-2 fair-net-prior mode: path to the SIGHTED (81ch/42) net "
                         "checkpoint whose POLICY head supplies the PUCT priors (the value stays "
                         "the FROZEN champion leaf = severed value loop). Loads a per-worker CPU "
                         "net. Requires --sighted. Prefer --shm-eval-server for GPU-batched "
                         "forwards; when both are given the ckpt is recorded for provenance only.")
    ap.add_argument("--shm-eval-server", type=str, default=None,
                    help="STAGE-2 fair-net-prior mode (PRODUCTION): connect workers to a running "
                         "carc-orch SHM eval-server (GPU-batched sighted 81ch/42 forwards) for the "
                         "net PRIORS instead of a per-worker CPU net. The server (started separately: "
                         "run_server.sh --transport shm --shm-name <name> --n-ch 81 --n-scalar 42) "
                         "owns the only net. Requires --sighted.")
    ap.add_argument("--batch-size", type=int, default=1,
                    help="STAGE-2 within-search leaf batching (LATENCY fix, 2026-07-16). >1 makes "
                         "each per-determinization NeuralMCTS collect this many leaves under virtual "
                         "loss and evaluate them in ONE forward instead of one blocking IPC+GPU "
                         "round-trip per expansion. Default 1 = the byte-for-byte serial path. IGNORED "
                         "in net-free (stage-1 champion) mode — the champion leaf is in-process Cython "
                         "with no round-trip to amortize and must stay byte-identical. NOTE the SHM "
                         "protocol caps a single request at MAX_K=8 boards, so batch_size>8 chunks into "
                         "ceil(N/8) round-trips (no extra transport win). The gen path already uses 8.")
    # ACTION LOG (2026-07-20) — emit the (deck_seed, action_sequence) root_replay record
    # per game so downstream root miners (F3 / Gate-B) can reconstruct ANY position the
    # CHAMPION actually reached, instead of falling back to a greedy-self-play proxy.
    ap.add_argument("--log-actions", action="store_true", default=False,
                    help="also write out/actions/seed_<seed>.json — the root_replay "
                         "(deck_seed, actions) GameRecord for each game. Free (a few KB/game).")
    ap.add_argument("--actions-only", action="store_true", default=False,
                    help="skip the training-data npz shard entirely and emit ONLY the action "
                         "log (implies --log-actions). ~28 MB/game of obs tensors saved when "
                         "the consumer is a root miner, not a trainer. Resume/caching keys on "
                         "the action json instead of the npz.")
    args = ap.parse_args(argv)
    if args.actions_only:
        args.log_actions = True

    net_mode = bool(args.net_ckpt) or bool(args.shm_eval_server)
    if net_mode and not args.sighted:
        ap.error("--net-ckpt / --shm-eval-server (fair-net-prior mode) require --sighted "
                 "(the net is an 81ch/42-scalar sighted net; the recorded obs must match)")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seeds = [args.seed_start + i for i in range(args.games)]

    # Self-describing manifest (results discipline). teacher block = fair champion cfg
    # + resolved leaf provenance + policy/value semantics (addendum "Manifest").
    cfg = _champion_cfg(args.c_puct, args.tau_p, args.value_norm)
    resolved_hash = _resolved_leaf_hash()
    # Resolved observation dims from the (sighted-aware) encoder — recorded in the
    # manifest so the rep never needs dirname archaeology (non-sighted 78/10; sighted 81/42).
    _enc = Game(sighted=args.sighted, window_size=args.window_size)
    n_channels = _enc.get_input_channels()
    n_scalars = _enc.get_scalar_feature_size()
    _net_mode_str = ("orch-shm(" + args.shm_eval_server + ")" if args.shm_eval_server
                     else ("cpu-net" if args.net_ckpt else "net-free (champion)"))
    man = {
        "generator": (
            "FairHeuristicPriorAgent self-play — DISTILLATION emitter | "
            + ("STAGE-2 fair-NET-prior (severed value loop: net POLICY head -> priors, "
               "FROZEN champion leaf -> value; blind PIMC)" if net_mode
               else "STAGE-1 net-free fair-CHAMPION (heuristic priors + heuristic leaf value; blind PIMC)")
        ),
        "net_mode": _net_mode_str,
        "net_ckpt": args.net_ckpt,
        "shm_eval_server": args.shm_eval_server,
        "priors_source": (
            "net_policy_head (masked-softmax over legal, SIGHTED 81ch/42 forward)" if net_mode
            else "heuristic softmax(Δleaf/τ) [net-free champion]"),
        "search_value_source": (
            "FROZEN champion v2.9 leaf tanh(flat_virtual_score_v2_float/value_norm) "
            "[severed value loop — the learned value head never steers search]"),
        "teacher": {
            "fair_agent": "FairHeuristicPriorAgent",
            "kind": ("net-priors + frozen-leaf-value blind PIMC (fair-net flywheel)" if net_mode
                     else "classical PUCT-with-heuristic-priors, blind PIMC (non-clairvoyant)"),
            "k_dets": args.k_dets,
            "sims_per_det": args.sims,
            "total_budget_per_move": args.k_dets * args.sims,
            "c_puct": args.c_puct,
            "tau_p": args.tau_p,
            "value_norm": args.value_norm,
            "leaf_quantize": "float",
            "final_select": "visits",
            "exact_endgame": args.exact_endgame,
            "exact_max_k": args.exact_max_k,
            "resolved_config": cfg.as_manifest(),
            "resolved_leaf_hash_runtime": resolved_hash,   # PROVENANCE ONLY — not gated (158f17ff is stale)
            "leaf_env": {k: os.environ.get(k) for k in _CANON_ENV},
            "policy_source": "pooled_visit_counts(agg_n, summed over k_dets)",
            "move_selected_by": "pooled_q_argmax",
            "policy_vs_pick_note": "argmax(policy)=pooled-N argmax is NOT necessarily the played move (pooled-Q pick)",
        },
        "value_target": "game_outcome",
        "value_target_desc": f"mover-POV tanh((p0-p1)/{_OUTCOME_NORM:g}) backfilled from the FINAL score",
        "outcome_norm": _OUTCOME_NORM,
        "sighted": args.sighted,
        "n_channels": n_channels,
        "n_scalars": n_scalars,
        "representation": (
            f"{n_channels}ch board / {n_scalars} scalars "
            + ("(SIGHTED bag-aware; matches m2_sighted/warmstart_sighted.pt)"
               if args.sighted
               else "(NON-sighted; matches warmstart_canonical.pt + the 96x6 net)")
        ),
        "row_kind": "mixed (trajectory aux_mask=True incl. forced one-hot; exact-endgame/pathological value-only aux_mask=False)",
        "ownership": "DUMMY zeros (no fair ownership labels; driver trains --aux-weight 0)",
        "games": args.games, "seed_start": args.seed_start,
        "leaf": "v2.9 Bmild_cap8 curve125 (DEFAULT_CONFIG under champ_env.sh)",
        "batch_size": args.batch_size,   # within-search leaf batching (1 = serial; net-mode only)
        "code_rev": code_rev(),
        "log_actions": args.log_actions,
        "actions_only": args.actions_only,
        "action_log": (
            "out/actions/seed_<seed>.json — root_replay GameRecord "
            "{game_id, deck_seed, actions, n_plies, ...meta}; losslessly replayable via "
            "scripts/measurement_infra/root_replay.replay_actions(deck_seed, actions, ply). "
            "Merge to a games jsonl with scripts/distill_flywheel/collect_action_logs.py."
            if args.log_actions else None),
    }
    _code_rev = code_rev()
    action_meta = {
        "gen": ("champion_fair_selfplay" if not net_mode else "fair_net_prior_selfplay"),
        "k_dets": args.k_dets, "sims_per_det": args.sims,
        "total_budget_per_move": args.k_dets * args.sims,
        "exact_max_k": args.exact_max_k,
        "leaf": "v2_9_2_Bmild_cap8_curve125",
        "leaf_hash_runtime": resolved_hash,
        "code_rev": _code_rev,
    }
    write_manifest(out, kind="gen_fair_distill", game=game_tag(Game()),
                   config=man, overwrite=True)

    todo = [(str(out), s) for s in seeds
            if not _done_path(out, s, args.actions_only).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"gen_fair_distill: games={args.games} k_dets={args.k_dets} sims={args.sims} "
          f"(budget={args.k_dets*args.sims}) exact_endgame={args.exact_endgame} "
          f"exact_max_k={args.exact_max_k} sighted={args.sighted} batch_size={args.batch_size} "
          f"rep={n_channels}ch/{n_scalars}sc leaf_hash={resolved_hash} net_mode={_net_mode_str} | "
          f"{len(seeds)-len(todo)} cached, {len(todo)} to play, {workers} workers, out={out}",
          flush=True)

    if not todo:
        print("nothing to do (all shards present)")
        return 0

    # Pool: default (net-free / CPU-net) uses the fork Pool. The carc-orch SHM path uses
    # a SPAWN context + a worker-id Queue so each CPU worker pops a unique SHM slot
    # (mirrors eval_fair_puct's orch launch); spawn keeps the forked-after-torch hazards
    # out of the GPU-server-attached workers.
    orch = bool(args.shm_eval_server)
    if orch:
        _ctx = mp.get_context("spawn")
        _id_q = _ctx.Queue()
        for _w in range(workers):
            _id_q.put(_w)
        print(f"  [orch] SHM eval-server '{args.shm_eval_server}': {workers} CPU workers attach to "
              f"/dev/shm/carc_{args.shm_eval_server} (81ch/42-scalar sighted net PRIORS)", flush=True)
        _pool_cm = _ctx.Pool(
            processes=workers, initializer=_worker_init,
            initargs=(args.k_dets, args.sims, args.c_puct, args.tau_p,
                      args.value_norm, args.exact_endgame, args.exact_max_k,
                      args.sighted, args.window_size, args.shared_claim, args.claim_host,
                      args.claim_stale_secs, args.net_ckpt, args.shm_eval_server, _id_q,
                      args.batch_size, args.log_actions, args.actions_only, action_meta))
    else:
        _pool_cm = Pool(
            processes=workers, initializer=_worker_init,
            initargs=(args.k_dets, args.sims, args.c_puct, args.tau_p,
                      args.value_norm, args.exact_endgame, args.exact_max_k,
                      args.sighted, args.window_size, args.shared_claim, args.claim_host,
                      args.claim_stale_secs, args.net_ckpt, "", None,
                      args.batch_size, args.log_actions, args.actions_only, action_meta))

    t0 = time.perf_counter()
    played = skipped = rows = aux_rows = val_rows = 0
    with _pool_cm as pool:
        for r in pool.imap_unordered(_play_one, todo, chunksize=1):
            if r is None or r.get("cached"):
                continue
            if r.get("skipped"):
                skipped += 1
                print(f"  [skip] seed={r['seed']}: {r.get('error')}", flush=True)
                continue
            played += 1
            rows += r.get("rows", 0)
            aux_rows += r.get("n_aux", 0)
            val_rows += r.get("n_valonly", 0)
            if played % 10 == 0 or played == len(todo):
                el = time.perf_counter() - t0
                print(f"  {played}/{len(todo)} games ({el/played:.1f}s/game, "
                      f"{rows} rows [{aux_rows} policy / {val_rows} value-only], "
                      f"~{(len(todo)-played)*el/played/60:.0f} min left)", flush=True)

    el = time.perf_counter() - t0
    print(f"[done] {played} games, {rows} rows ({aux_rows} policy / {val_rows} value-only), "
          f"{skipped} skipped ({el:.1f}s). shards in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
