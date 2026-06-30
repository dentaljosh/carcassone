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


REF_SIMS = 200
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


def _build_candidate_mcts(cfg, base_net, game_farm, seed, device):
    """RoD2-iter02 POLICY net + step2 weaned scalar-MLP VALUE leaf."""
    SMLP = _import_scalar_mlp()
    ck = torch.load(cfg["scalar_ckpt"], map_location=device, weights_only=False)
    mlp = SMLP(int(ck["D"]), hidden=int(ck["hidden"]), blocks=int(ck["blocks"])).to(device)
    mlp.load_state_dict(ck["state_dict"])
    mlp.eval()
    col_mean = np.asarray(ck["col_mean"], np.float32)
    col_std = np.asarray(ck["col_std"], np.float32)
    feat_names = [str(x) for x in ck["feat_names"]]
    base_ev = make_single_evaluator_policy_only(base_net, device, game_farm)
    leaf_cfg = EH._heur_leaf_cfg(2.0)  # v2.9 cfg (hash-checked in main)
    wrapped = step2_leaf.make_step2_value_wrapper(
        base_ev, mlp, col_mean, col_std, feat_names,
        game=game_farm, leaf_cfg=leaf_cfg,
        blend=cfg["blend"], dropout_p=cfg["dropout"],
        device=device, rng_seed=seed ^ 0x57E92,
    )
    return NeuralMCTS(game=game_farm, evaluator=wrapped, simulations=cfg["sims"],
                      seed=seed, c_puct=CPUCT)


def _build_reference_mcts(base_net, game_farm, seed, device, sims):
    """RoD2 iter_02 plain: net policy + net value, riding the v2.9 leaf VALUE
    (make_v25_value_wrapper with the v2.9 cfg) — RoD2's native substrate.
    Reference runs at the SAME sims as the candidate (MATCHED COMPUTE). BUG-1 fix:
    a hardcoded 200-sim reference vs an N-sim candidate biased the screen by search
    depth, not value quality (corrupted any non-200-sim eval, e.g. the sims=100 pilot)."""
    leaf_cfg = EH._heur_leaf_cfg(2.0)  # v2.9 LeafConfig (DEFAULT_CONFIG already v2.9 via env)
    base_ev = make_single_evaluator(base_net, device, game_farm)
    leaf = make_v25_value_wrapper(base_ev, leaf_cfg)
    return NeuralMCTS(game=game_farm, evaluator=leaf, simulations=sims,
                      seed=seed, c_puct=CPUCT)


class _CandAgent:
    def __init__(self, cfg, base_net, game_farm, seed, device):
        self._m = _build_candidate_mcts(cfg, base_net, game_farm, seed, device)
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None

    def move(self, board):
        self._m.clear()
        self.neural_moves += 1
        return int(self._m.best_action(board))


class _RefAgent:
    def __init__(self, base_net, game_farm, seed, device, sims):
        self._m = _build_reference_mcts(base_net, game_farm, seed, device, sims)
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None

    def move(self, board):
        self._m.clear()
        self.neural_moves += 1
        return int(self._m.best_action(board))


def _worker_init(cfg):
    torch.set_num_threads(1)
    device = torch.device("cpu")  # net-on-CPU (matches gen_step2; scalar MLP is per-worker)
    base_net, ns = _load_net(cfg["ckpt"], device)
    ref_net, _ = _load_net(cfg["ref_ckpt"], device)
    _W.update(cfg=cfg, device=device, base_net=base_net, ref_net=ref_net,
              farm=(ns > N_SCALAR_FEATURES), out=cfg["out"],
              shared_claim=cfg["shared_claim"], claim_host=cfg["claim_host"],
              claim_stale=cfg["claim_stale"])


def _make_pair(seed):
    cfg = _W["cfg"]
    dev = _W["device"]
    farm = _W["farm"]
    ga = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    gb = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    cand = _CandAgent(cfg, _W["base_net"], ga, seed, dev)
    ref = _RefAgent(_W["ref_net"], gb, seed + 1, dev, cfg["sims"])
    return cand, ref


def _play_one(args):
    seed, a_seat = args
    out = Path(_W["out"])
    p = EH._result_path(out, seed, a_seat)
    cached = EH._try_load(p)
    if cached is not None:
        return cached
    if _W.get("shared_claim"):
        from carcassonne_ai.claim import try_claim as _try_claim
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None

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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval_step2")
    ap.add_argument("--ckpt", required=True, help="Candidate base POLICY net (RoD2 iter_02 by default lineage).")
    ap.add_argument("--scalar-ckpt", required=True, help="Candidate scalar-MLP value ckpt (warmstart format).")
    ap.add_argument("--ref-ckpt", required=True, help="Reference net = RoD2 iter_02 (plays plain v2.9-leaf NeuralMCTS).")
    ap.add_argument("--blend", type=float, default=0.2, help="Wean lambda for the candidate value.")
    ap.add_argument("--dropout", type=float, default=0.0, help="Per-leaf pure-MLP-value dropout for the candidate.")
    ap.add_argument("--n", type=int, default=120, help="Game count (paired => even).")
    ap.add_argument("--sims", type=int, default=200, help="Candidate NeuralMCTS sims (reference fixed at 200).")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=5_715_000_000)
    ap.add_argument("--out", required=True, help="Output dir for per-game result json + summary.")
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=1800)
    ap.add_argument("--claim-host", default=socket.gethostname())
    ap.add_argument("--smoke", action="store_true", help="Single-process tiny paired run, print, exit.")
    args = ap.parse_args(argv)

    if args.n % 2 != 0:
        ap.error("--n must be even (paired, both seats per deck)")

    # provenance: the candidate's leaf cfg MUST be the frozen v2.9.
    leaf_cfg = EH._heur_leaf_cfg(2.0)
    cfg_hash = step2_leaf._bd._cfg_hash(leaf_cfg)
    frozen = step2_leaf._bd.FROZEN_V29_HASH
    print(f"[provenance] v2.9 leaf config_hash = {cfg_hash} (frozen v2.9 = {frozen})")
    assert cfg_hash == frozen, f"LEAF NOT v2.9 (got {cfg_hash}, want {frozen})"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = {
        "ckpt": args.ckpt, "scalar_ckpt": args.scalar_ckpt, "ref_ckpt": args.ref_ckpt,
        "blend": float(args.blend), "dropout": float(args.dropout), "sims": args.sims,
        "out": str(out), "shared_claim": bool(args.shared_claim),
        "claim_host": args.claim_host, "claim_stale": args.claim_stale_secs,
    }
    print(f"[eval] step2 candidate (policy={Path(args.ckpt).name} + scalar="
          f"{Path(args.scalar_ckpt).name}, blend={args.blend} dropout={args.dropout} "
          f"sims={args.sims}) vs RoD2 iter_02 ({Path(args.ref_ckpt).name}, v2.9-leaf @200) "
          f"| paired n={args.n}", flush=True)

    work = EH._build_work(args.seed_start, args.n, paired=True)

    if args.smoke:
        _worker_init(cfg)
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
    print(f"  {len(work)-len(todo)} cached, {len(todo)} to play, {workers} workers (net-on-CPU)",
          flush=True)
    results = []
    if todo:
        ctx = get_context("spawn")
        t0 = time.perf_counter()
        with ctx.Pool(processes=workers, initializer=_worker_init, initargs=(cfg,)) as pool:
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
                     "scalar_ckpt": args.scalar_ckpt, "ckpt": args.ckpt, "ref_ckpt": args.ref_ckpt})
        json.dump(summ, open(out / "summary.json", "w"), indent=2)
        print(f"[done] summary -> {out/'summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
