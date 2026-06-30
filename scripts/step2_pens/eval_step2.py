#!/usr/bin/env python3
"""Step-2 "PeNS" candidate vs RoD2 iter_02 — paired net-vs-net SCREEN (MEASUREMENT ONLY).

A cheap, paired, seat-balanced head-to-head screen for the weaned flywheel:

  CANDIDATE  = base POLICY net (--ckpt, the iter's trained ResNet policy) +
               the STEP-2 leaf value = wean-blend of the v2.9 heuristic and the
               iter's scalar MLP (--scalar-ckpt, --blend, --dropout). This is the
               exact play-time evaluator gen_step2.py builds
               (step2_leaf.make_step2_value_wrapper), so the screen measures the
               thing the flywheel is actually producing.
  REFERENCE  = RoD2 iter_02 (--ref-ckpt) as a plain NeuralMCTS: its net policy
               riding on the v2.9 leaf VALUE (make_v25_value_wrapper, v2.9 cfg).
               This is RoD2's native substrate — the same comparison anchor the
               flywheel uses.

Both agents play NeuralMCTS@--sims (default 200, c_puct 3.0). PAIRED (each deck
played both seats), n configurable (~120 for the cheap screen). Prints elo / wr /
winrate-z + paired score-margin z. Reuses eval_hybrid_handoff's paired-z + summary
math byte-for-byte (the canonical Level-2 statistic) so the number sits on the
same ruler as the L2 verdicts.

WHY NOT eval_hybrid_handoff directly: its agents (iter8 / heur@N / hybrid / exact)
all take the value from the ResNet value head via make_v25_value_wrapper; NONE
can take its value from the step2 scalar-MLP wean. So this is a thin purpose-built
net-vs-net runner that uses the step2_leaf wrapper for the candidate and reuses
EH only for the statistics + GameResult container. Net-on-CPU per worker (matches
gen_step2's choice; the scalar-MLP is a tiny per-worker module — orch only batches
the policy forward, not worth the complexity for a 120-game screen).

  # plumbing smoke (single process, random-init MLP via gen_step2's path NOT used here;
  # for the screen we need a real scalar ckpt — use the warmstart.pt):
  python -u scripts/step2_pens/eval_step2.py \
      --ckpt /mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
      --scalar-ckpt /home/doctor/carc_step2_pens/warmstart/warmstart.pt \
      --ref-ckpt /mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
      --blend 0.2 --dropout 0.0 --n 4 --sims 50 --workers 1 --smoke

  # real screen (paired n=120):
  python -u scripts/step2_pens/eval_step2.py \
      --ckpt $CAND --scalar-ckpt $SCALAR --ref-ckpt $ROD2 \
      --blend 0.2 --n 120 --sims 200 --workers 14 \
      --out /mnt/c/carc-shared/step2_pens/eval/iter02
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

# Import step2_leaf FIRST (its build_dataset import sets the FROZEN v2.9 leaf env
# — CAP=8 / V29 curve / FLAT_LEAF=1 / VALUE_BLEND=0 — BEFORE virtual_score_v2's
# DEFAULT_CONFIG is frozen). Both the candidate's step2 leaf AND the reference's
# v2.9 value wrapper then sit on the identical frozen v2.9 substrate.
import carcassonne_ai.step2_leaf as step2_leaf  # noqa: E402 (sets guard env)

import argparse  # noqa: E402
import importlib.util as _ilu  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import socket  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from carcassonne_ai.evaluators import (  # noqa: E402
    make_single_evaluator_policy_only,
    make_single_evaluator,
    make_v25_value_wrapper,
)
from carcassonne_ai.features import N_SCALAR_FEATURES  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.eval_provenance import deck_hash  # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402

import eval_hybrid_handoff as EH  # noqa: E402  (paired-z + summary + GameResult)


def _import_scalar_mlp():
    spec = _ilu.spec_from_file_location(
        "step2_train_warmstart", str(REPO / "scripts" / "step2_pens" / "train_warmstart.py")
    )
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.ScalarMLP


# REF_SIMS removed (BUG-1 fix): the reference now runs at the candidate's --sims
# (matched compute), threaded via _build_reference_mcts(sims=cfg["sims"]).
CPUCT = 3.0

_W: dict = {}


def _load_net(ckpt_path, device):
    ck = torch.load(ckpt_path, map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", N_SCALAR_FEATURES))
    net = CarcassonneNet(
        n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
        n_scalar_features=ns, value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, ns


def _build_candidate_mcts(cfg, base_net, game_farm, seed, device, base_ev=None):
    """RoD2-iter02 POLICY net + step2 weaned scalar-MLP VALUE leaf.

    `base_ev` (priors source) is injected by the caller: net-on-CPU it's the
    local policy-only ResNet evaluator (built here when None); under the orch it's
    a make_remote_single_evaluator over the CANDIDATE's SHM server. Either way the
    wean wrapper KEEPS its priors and DISCARDS its value (value = the v2.9/MLP
    wean), so swapping the priors source to the GPU orchestrator is value-neutral."""
    SMLP = _import_scalar_mlp()
    ck = torch.load(cfg["scalar_ckpt"], map_location=device, weights_only=False)
    mlp = SMLP(int(ck["D"]), hidden=int(ck["hidden"]), blocks=int(ck["blocks"])).to(device)
    mlp.load_state_dict(ck["state_dict"])
    mlp.eval()
    col_mean = np.asarray(ck["col_mean"], np.float32)
    col_std = np.asarray(ck["col_std"], np.float32)
    feat_names = [str(x) for x in ck["feat_names"]]
    if base_ev is None:
        base_ev = make_single_evaluator_policy_only(base_net, device, game_farm)
    leaf_cfg = EH._heur_leaf_cfg(2.0)  # v2.9 cfg (hash-checked in main)
    wrapped = step2_leaf.make_step2_value_wrapper(
        base_ev, mlp, col_mean, col_std, feat_names,
        game=game_farm, leaf_cfg=leaf_cfg,
        blend=cfg["blend"], dropout_p=cfg["dropout"],
        device=device, rng_seed=seed ^ 0x57E92,
        leaf_mode=cfg.get("leaf_mode", "convex"),
    )
    return NeuralMCTS(game=game_farm, evaluator=wrapped, simulations=cfg["sims"],
                      seed=seed, c_puct=CPUCT)


def _build_reference_mcts(base_net, game_farm, seed, device, sims, base_ev=None):
    """RoD2 iter_02 plain: net policy + net value, riding the v2.9 leaf VALUE
    (make_v25_value_wrapper with the v2.9 cfg) — RoD2's native substrate.
    Reference runs at the SAME sims as the candidate (MATCHED COMPUTE). BUG-1 fix:
    a hardcoded 200-sim reference vs an N-sim candidate biased the screen by search
    depth, not value quality (corrupted any non-200-sim eval, e.g. the sims=100 pilot).

    `base_ev` (priors source) is injected by the caller: net-on-CPU it's the local
    ResNet evaluator (built here when None); under the orch it's a
    make_remote_single_evaluator over the REFERENCE's SHM server. make_v25_value_wrapper
    keeps its priors and replaces the value with the v2.9 leaf (value_blend=0, so the
    base value is unused), so the priors-source swap is value-neutral."""
    leaf_cfg = EH._heur_leaf_cfg(2.0)  # v2.9 LeafConfig (DEFAULT_CONFIG already v2.9 via env)
    if base_ev is None:
        base_ev = make_single_evaluator(base_net, device, game_farm)
    leaf = make_v25_value_wrapper(base_ev, leaf_cfg)
    return NeuralMCTS(game=game_farm, evaluator=leaf, simulations=sims,
                      seed=seed, c_puct=CPUCT)


class _CandAgent:
    def __init__(self, cfg, base_net, game_farm, seed, device, base_ev=None):
        self._m = _build_candidate_mcts(cfg, base_net, game_farm, seed, device, base_ev=base_ev)
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None

    def move(self, board):
        self._m.clear()
        self.neural_moves += 1
        return int(self._m.best_action(board))


class _RefAgent:
    def __init__(self, base_net, game_farm, seed, device, sims, base_ev=None):
        self._m = _build_reference_mcts(base_net, game_farm, seed, device, sims, base_ev=base_ev)
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None

    def move(self, board):
        self._m.clear()
        self.neural_moves += 1
        return int(self._m.best_action(board))


def _worker_init(cfg, id_q_cand=None, id_q_ref=None):
    torch.set_num_threads(1)
    device = torch.device("cpu")  # values (wean + v2.9 leaf) + scalar MLP stay on CPU
    orch = bool(cfg.get("shm_cand") and cfg.get("shm_ref"))
    handles_cand = handles_ref = None
    base_net = ref_net = None
    if orch:
        # POLICY priors for BOTH agents come from their OWN carc-orch SHM server
        # (GPU-batched forwards on one shared context per net — the fast path that
        # net-on-CPU was ~85% of eval cost). Two handles in one worker is fine:
        # connect_shm keys on shm_name (same as v28_net_vs_net_orch). The orch VALUE
        # is discarded by both value wrappers; only its priors are used. Each agent's
        # n_scalar must match the net it serves (peeked per-ckpt in main). The id
        # queues are explicit Pool initargs (raw ctx.Queue, NOT a Manager proxy in
        # cfg — that proxy died on the spawn workers: ConnectionRefused), mirroring
        # v28_net_vs_net_orch.
        from carcassonne_ai.shm_eval_handles import connect_shm
        wid_cand = id_q_cand.get()
        wid_ref = id_q_ref.get()
        handles_cand = connect_shm(cfg["shm_cand"], wid_cand, cfg["ns_cand"])
        handles_ref = connect_shm(cfg["shm_ref"], wid_ref, cfg["ns_ref"])
        ns = cfg["ns_cand"]
    else:
        base_net, ns = _load_net(cfg["ckpt"], device)
        ref_net, _ = _load_net(cfg["ref_ckpt"], device)
    _W.update(cfg=cfg, device=device, base_net=base_net, ref_net=ref_net,
              farm=(ns > N_SCALAR_FEATURES), out=cfg["out"],
              shared_claim=cfg["shared_claim"], claim_host=cfg["claim_host"],
              claim_stale=cfg["claim_stale"],
              orch=orch, handles_cand=handles_cand, handles_ref=handles_ref)


def _make_pair(seed):
    cfg = _W["cfg"]
    dev = _W["device"]
    if _W.get("orch"):
        # Per-agent Game at the agent's OWN net scalar width; priors come from the
        # agent's OWN SHM server via a fresh remote evaluator over that Game (the
        # remote evaluator is cheap and Game-scoped, so build per-game like v28).
        from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
        farm_cand = cfg["ns_cand"] > N_SCALAR_FEATURES
        farm_ref = cfg["ns_ref"] > N_SCALAR_FEATURES
        ga = Game(enable_legal_moves_cache=True, include_farm_scalars=farm_cand)
        gb = Game(enable_legal_moves_cache=True, include_farm_scalars=farm_ref)
        ev_cand = make_remote_single_evaluator(_W["handles_cand"], ga)
        ev_ref = make_remote_single_evaluator(_W["handles_ref"], gb)
        cand = _CandAgent(cfg, None, ga, seed, dev, base_ev=ev_cand)
        ref = _RefAgent(None, gb, seed + 1, dev, cfg["sims"], base_ev=ev_ref)
        return cand, ref
    farm = _W["farm"]
    ga = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    gb = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    cand = _CandAgent(cfg, _W["base_net"], ga, seed, dev)
    ref = _RefAgent(_W["ref_net"], gb, seed + 1, dev, cfg["sims"])
    return cand, ref


def _play_seat(seed, a_seat):
    """Play ONE seat of a deck (candidate in seat a_seat) and persist its result
    JSON. Returns the GameResult (or a cached one if the JSON already exists)."""
    out = Path(_W["out"])
    p = EH._result_path(out, seed, a_seat)
    cached = EH._try_load(p)
    if cached is not None:
        return cached
    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    dh = deck_hash(board)
    cand, ref = _make_pair(seed)
    a = cand   # A is always the CANDIDATE; B the reference
    b = ref
    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        agent = a if cur == a_seat else b
        action = agent.move(board)
        mask = game.get_valid_moves(board)
        if not mask[action]:
            raise RuntimeError(f"agent returned illegal action {action}")
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    r = EH.GameResult(
        seed=seed, a_seat=a_seat, agent_a="step2_candidate", agent_b="rod2_iter02",
        score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_a=(diff > 0), drew=(diff == 0), elapsed_s=elapsed, moves=moves,
        deck_hash=dh,
        a_neural_moves=a.neural_moves, b_neural_moves=b.neural_moves,
    )
    EH._save(p, r)
    return r


def _play_one(args):
    """Pool entry. The work unit is one (seed, a_seat) pair, but claiming is at
    DECK granularity (whole pair as a unit) so the two seats of a deck always land
    on the SAME box — PAIRING PRESERVED, no split-deck (one seat on local + the
    other on the laptop) and no same-box double-play.

    On the FIRST seat-unit of a deck that this box wins, the worker atomically
    claims seed_NNNNNNNNNN.deckclaim and plays BOTH seats right here, persisting
    both result JSONs; the partner seat-unit then resolves to cached (or is swept
    by main's final cached-gather). A peer box that lost the deckclaim skips BOTH
    its seat-units. The .npz/.json atomic write stays the real done-marker; the
    .deckclaim is the best-effort cross-box lock (carcassonne_ai.claim). The
    paired-z is statistically unchanged — pairing is per-deck either way — but the
    whole-deck claim keeps the pair physically co-located (no orphaned half-deck if
    a box dies mid-pair)."""
    seed, a_seat = args
    out = Path(_W["out"])
    p = EH._result_path(out, seed, a_seat)
    cached = EH._try_load(p)
    if cached is not None:
        return cached
    if not _W.get("shared_claim"):
        # Legacy single-box behaviour: play just this seat.
        return _play_seat(seed, a_seat)

    from carcassonne_ai.claim import try_claim as _try_claim
    deckclaim = out / f"seed{seed:010d}.deckclaim"
    if not _try_claim(deckclaim, _W["claim_host"], _W["claim_stale"]):
        # A peer box (or a sibling worker on THIS box) already owns the deck.
        # The owner plays BOTH seats, so we skip this seat-unit entirely; the
        # owner's JSON is the result. (Same-box sibling: harmless — the owner is
        # one of our own workers and will write both JSONs.)
        return None
    # We own the whole deck — play BOTH seats here (atomic per-deck), so the pair
    # never splits and the partner seat-unit later returns cached.
    r0 = _play_seat(seed, 0)
    r1 = _play_seat(seed, 1)
    # Return THIS work-unit's seat; the partner lands via main's cached-gather.
    return r0 if a_seat == 0 else r1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval_step2")
    ap.add_argument("--ckpt", required=True, help="Candidate base POLICY net (RoD2 iter_02 by default lineage).")
    ap.add_argument("--scalar-ckpt", required=True, help="Candidate scalar-MLP value ckpt (warmstart format).")
    ap.add_argument("--ref-ckpt", required=True, help="Reference net = RoD2 iter_02 (plays plain v2.9-leaf NeuralMCTS).")
    ap.add_argument("--blend", type=float, default=0.2, help="Wean lambda (convex) / additive coefficient beta (additive) for the candidate value.")
    ap.add_argument("--leaf-mode", choices=("convex", "additive"), default="convex",
                    help="Candidate leaf value combine mode. convex (default): "
                         "(1-blend)*h + blend*v_net (the production wean — heuristic "
                         "weaned DOWN). additive (nail-2 decoupling test): "
                         "clip(h + blend*v_net, -1, 1) — heuristic at FULL weight, net "
                         "added on top. The reference (RoD2 iter_02) is unchanged either way.")
    ap.add_argument("--dropout", type=float, default=0.0, help="Per-leaf pure-MLP-value dropout for the candidate.")
    ap.add_argument("--n", type=int, default=120, help="Game count (paired => even).")
    ap.add_argument("--sims", type=int, default=200, help="Simulations per move for BOTH agents — matched compute (candidate AND reference run at this depth).")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=5_715_000_000)
    ap.add_argument("--out", required=True, help="Output dir for per-game result json + summary.")
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=1800)
    ap.add_argument("--claim-host", default=socket.gethostname())
    ap.add_argument("--shm-eval-server-cand", default=None,
                    help="carc-orch SHM server name for the CANDIDATE policy net "
                         "(GPU-batched priors via the orchestrator — the fast path). "
                         "Must already be running (eval_step2_orch.sh launches it). "
                         "Requires --shm-eval-server-ref too; net-on-CPU is the "
                         "default/fallback when neither is set. The orch VALUE is "
                         "discarded — the candidate value stays the v2.9/MLP wean.")
    ap.add_argument("--shm-eval-server-ref", default=None,
                    help="carc-orch SHM server name for the REFERENCE (RoD2 iter_02) "
                         "policy net. The orch VALUE is discarded — the reference value "
                         "stays the in-worker v2.9 leaf (make_v25_value_wrapper).")
    ap.add_argument("--smoke", action="store_true", help="Single-process tiny paired run, print, exit.")
    ap.add_argument("--summarize-only", action="store_true",
                    help="Skip ALL play (and the orch). Gather every per-game result "
                         "JSON already on disk in --out and (re)write summary.json. "
                         "Used by the 2-box launcher post-drain to fold the laptop's "
                         "decks into the paired-z without re-launching the orchestrator.")
    args = ap.parse_args(argv)

    if bool(args.shm_eval_server_cand) != bool(args.shm_eval_server_ref):
        ap.error("--shm-eval-server-cand and --shm-eval-server-ref must be set TOGETHER "
                 "(one SHM server per policy net) or neither (net-on-CPU).")

    if args.n % 2 != 0:
        ap.error("--n must be even (paired, both seats per deck)")

    # provenance: the candidate's leaf cfg MUST be the frozen v2.9.
    leaf_cfg = EH._heur_leaf_cfg(2.0)
    cfg_hash = step2_leaf._bd._cfg_hash(leaf_cfg)
    frozen = step2_leaf._bd.FROZEN_V29_HASH
    print(f"[provenance] v2.9 leaf config_hash = {cfg_hash} (frozen v2.9 = {frozen})")
    assert cfg_hash == frozen, f"LEAF NOT v2.9 (got {cfg_hash}, want {frozen})"

    # --summarize-only: gather every result JSON on disk and (re)write summary.json,
    # no play, no orch. The launcher's 2-box eval drain uses this to fold the laptop's
    # claimed decks into the paired-z cheaply (the per-game JSONs from both boxes land
    # in the shared --out; pairing is per-deck so the paired-z is exact over whatever
    # decks completed both seats).
    if args.summarize_only:
        out = Path(args.out)
        work = EH._build_work(args.seed_start, args.n, paired=True)
        results = []
        for w in work:
            p = EH._result_path(out, w[0], w[1])
            c = EH._try_load(p)
            if c is not None:
                results.append(c)
        if results:
            summ = EH._summary(results, "step2_candidate", "rod2_iter02")
            summ.update({"blend": args.blend, "dropout": args.dropout, "sims": args.sims,
                         "leaf_mode": args.leaf_mode,
                         "scalar_ckpt": args.scalar_ckpt, "ckpt": args.ckpt,
                         "ref_ckpt": args.ref_ckpt, "priors": "summarize-only"})
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
            print(f"[summarize-only] {len(results)} result JSONs -> {out/'summary.json'}", flush=True)
        else:
            print(f"[summarize-only] no result JSONs found in {out} — nothing to summarize", flush=True)
        return 0

    orch = bool(args.shm_eval_server_cand and args.shm_eval_server_ref)
    ns_cand = ns_ref = None
    if orch:
        # Peek each net's scalar width SEPARATELY (the SHM handle + per-agent Game
        # must match the net the server holds; don't assume the two share a width).
        ns_cand = int(torch.load(args.ckpt, map_location="cpu", weights_only=False)
                      .get("n_scalar_features", N_SCALAR_FEATURES))
        ns_ref = int(torch.load(args.ref_ckpt, map_location="cpu", weights_only=False)
                     .get("n_scalar_features", N_SCALAR_FEATURES))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = {
        "ckpt": args.ckpt, "scalar_ckpt": args.scalar_ckpt, "ref_ckpt": args.ref_ckpt,
        "blend": float(args.blend), "dropout": float(args.dropout), "sims": args.sims,
        "leaf_mode": args.leaf_mode,
        "out": str(out), "shared_claim": bool(args.shared_claim),
        "claim_host": args.claim_host, "claim_stale": args.claim_stale_secs,
        "shm_cand": args.shm_eval_server_cand, "shm_ref": args.shm_eval_server_ref,
        "ns_cand": ns_cand, "ns_ref": ns_ref,
    }
    path_desc = (f"orch (cand-shm={args.shm_eval_server_cand}, ref-shm={args.shm_eval_server_ref})"
                 if orch else "net-on-CPU")
    print(f"[eval] step2 candidate (policy={Path(args.ckpt).name} + scalar="
          f"{Path(args.scalar_ckpt).name}, leaf_mode={args.leaf_mode} blend={args.blend} "
          f"dropout={args.dropout} sims={args.sims}) vs RoD2 iter_02 ({Path(args.ref_ckpt).name}, "
          f"v2.9-leaf @{args.sims}) | paired n={args.n} | priors via {path_desc}", flush=True)

    work = EH._build_work(args.seed_start, args.n, paired=True)

    if args.smoke:
        qc = qr = None
        if orch:
            # Single-process smoke: one worker_id per server (the worker pops 0).
            ctx0 = get_context("spawn")
            qc, qr = ctx0.Queue(), ctx0.Queue()
            qc.put(0); qr.put(0)
        _worker_init(cfg, qc, qr)
        res = [r for a in work[:4] if (r := _play_one(a)) is not None]
        for r in res:
            print(f"[smoke] seed={r.seed} a_seat={r.a_seat} scores={r.score_p0}-{r.score_p1} "
                  f"diff(cand-ref)={r.diff:+d} moves={r.moves} ({r.elapsed_s:.1f}s)")
        if res:
            EH._summary(res, "step2_candidate", "rod2_iter02")
        print("[smoke] OK — candidate-vs-reference plumbing verified", flush=True)
        return 0

    workers = args.workers or min(os.cpu_count() or 1, len(work))
    todo = [w for w in work if not EH._result_path(out, w[0], w[1]).exists()]
    if args.shared_claim:
        # ORPHAN-CLAIM SWEEP (feedback_shared_claim_orphan_stall): a killed
        # --shared-claim eval strands seed_*.deckclaim files with no resulting
        # result JSON. On (re)start a stranded fresh deckclaim would keep every box
        # from re-playing that deck -> the run stalls below n. Sweep deckclaims with
        # NEITHER seat's JSON on disk whose mtime is older than --claim-stale-secs
        # (the same age try_claim judges abandonment by). A completed deck's claim is
        # harmless and left alone.
        from carcassonne_ai.claim import is_stale as _claim_is_stale
        swept = 0
        for seed in {w[0] for w in work}:
            j0 = EH._result_path(out, seed, 0)
            j1 = EH._result_path(out, seed, 1)
            dc = out / f"seed{seed:010d}.deckclaim"
            if j0.exists() or j1.exists():
                continue
            if dc.exists() and _claim_is_stale(dc, args.claim_stale_secs):
                # Atomic rename-aside, NOT unlink (mirrors claim.try_claim's
                # stale-recovery): among multiple boxes sweeping the same shared
                # dir on resume, only ONE rename of a given source wins; the rest
                # get FileNotFoundError (caught). A bare unlink is not race-safe —
                # two sweepers + the .claim being best-effort (the result-JSON
                # rename-into-place is the correctness layer) means the worst case
                # here is a deck replayed = wasted compute, never a split/double-
                # counted pair. See feedback_shared_claim_orphan_stall.
                try:
                    dc.rename(dc.with_suffix(".swept")); swept += 1
                except OSError:
                    pass  # peer already recovered it (rename lost the race)
        if swept:
            print(f"  orphan-claim sweep: removed {swept} stale .deckclaim(s) with no "
                  f"result JSON (re-claimable now).", flush=True)
        # Each box walks the work list in its OWN order (keyed by claim-host) so the
        # boxes start claiming decks from different regions — avoids a startup burst
        # of every worker racing the same low seeds (gen_step2 / run_selfplay_iter
        # pattern). Combined with warm-laptop-first this load-balances the deck pool.
        import random as _r
        _r.Random(__import__("zlib").crc32(args.claim_host.encode())).shuffle(todo)
        print(f"  WORK-STEALING (--shared-claim, whole-deck) host={args.claim_host} "
              f"stale_secs={args.claim_stale_secs} -> shared OUT {out}", flush=True)
    print(f"  {len(work)-len(todo)} cached, {len(todo)} to play, {workers} workers "
          f"({path_desc})", flush=True)
    results = []
    if todo:
        ctx = get_context("spawn")
        # The orch path keys each worker's SHM handle on a unique worker_id PER SERVER.
        # A raw ctx.Queue per server, pre-filled 0..W-1, hands each worker one id at
        # init via explicit Pool initargs (NOT a Manager proxy smuggled through cfg —
        # that proxy was unreachable from the spawn workers: ConnectionRefused).
        # Mirrors v28_net_vs_net_orch. No-op for net-on-CPU (queues are None).
        init_args = (cfg, None, None)
        if orch:
            id_q_cand, id_q_ref = ctx.Queue(), ctx.Queue()
            for w in range(max(1, workers)):
                id_q_cand.put(w); id_q_ref.put(w)
            init_args = (cfg, id_q_cand, id_q_ref)
        t0 = time.perf_counter()
        with ctx.Pool(processes=workers, initializer=_worker_init, initargs=init_args) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)", flush=True)
    # gather cached
    for w in work:
        p = EH._result_path(out, w[0], w[1])
        if p.exists() and not any(r.seed == w[0] and r.a_seat == w[1] for r in results):
            c = EH._try_load(p)
            if c:
                results.append(c)

    if results:
        summ = EH._summary(results, "step2_candidate", "rod2_iter02")
        summ.update({"blend": args.blend, "dropout": args.dropout, "sims": args.sims,
                     "leaf_mode": args.leaf_mode,
                     "scalar_ckpt": args.scalar_ckpt, "ckpt": args.ckpt, "ref_ckpt": args.ref_ckpt,
                     "priors": ("orch" if orch else "net-on-cpu"),
                     "shm_eval_server_cand": args.shm_eval_server_cand,
                     "shm_eval_server_ref": args.shm_eval_server_ref})
        json.dump(summ, open(out / "summary.json", "w"), indent=2)
        print(f"[done] summary -> {out/'summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
