#!/usr/bin/env python3
"""Step-2 PeNS DEPTH-STRATIFIED interior-tau probe (MEASUREMENT ONLY).

THE QUESTION. The Step-2 warmstart ScalarMLP value ranks sibling moves well
OFFLINE (net-alone Kendall-tau ~ 0.43, measured on DEPTH-1 root siblings — the
children of each move-root, ranked by their backed-up search-Q). Yet in-game
play craters monotonically as the wean `blend` rises. A reviewer's point: tau
measured at DEPTH-1 root siblings does NOT certify the value on the DEEP INTERIOR
nodes the search visits during its 100-sim descent. This probe measures the same
sibling-ranking tau but STRATIFIED BY SEARCH-TREE NODE DEPTH:

  - tau HOLDS (~flat across depth) -> the value is good where search uses it
    (strengthens "value object can't drive search").
  - tau COLLAPSES (monotonically down with depth) -> train/serve distribution
    mismatch: the value ranks the shallow distribution it was trained on but is
    bad on the deep distribution, and weighting it up amplifies those errors ->
    the monotonic crater. (recoverable)

  >>> This script ONLY emits the depth-stratified tau table + a HOLD/COLLAPSE
  >>> verdict heuristic. The orchestrator draws the final Gate-B conclusion.

HOW. Run PRODUCTION step2-wean self-play (blend=0.27 = the decisive crater
blend, frozen warmstart value, sims=100 = play config, iter_02 policy net-on-CPU
for priors, record_boards so the whole tree's boards are stored). After EACH
learner search (on_ply_search), traverse the LIVE search tree from the root by
BFS, assigning each node its tree DEPTH (plies from the search root). For every
INTERIOR node with >=2 visited children (each N >= min_child_visits), form that
node's sibling group exactly like mcts.root_sibling_group does — but with
parent = the interior node (not the root). For each group:

  net_value(child) = ScalarMLP( z-score( extract_step2_features(
                       game, child_board, leaf_cfg, parent_board=node_board) ) )
       -- this is the PARENT-POV value the leaf actually consumes (the
          `_mlp_value` in step2_leaf, BEFORE the `_v_mlp_leafpov` POV flip).
  target(child)    = backed-up search-Q (child.Q), flipped to the PARENT-NODE POV
                       (q if child_player == parent_player else -q) -- mirrors the
                       rank-emit (`child_q if child_player==root_player else -child_q`,
                       root=parent here) and the warmstart oracle_q convention.

  tau_group = kendall_tau_b(net_values, targets)   # same fn warmstart used.

Both net_value and target live in the SAME parent-POV frame, so this is the
EXACT measurement the warmstart's net-alone tau made (parent-POV net pred vs
parent-POV oracle_q), just extended from the root parent to every interior parent.

DEPTH BUCKETS: 1, 2-3, 4-7, 8+. depth-1 is the SANITY ANCHOR (should reproduce
the warmstart's ~0.43 net-alone tau; if it doesn't, that itself is informative).

Usage (net-on-CPU, parallel over games; detach for long runs):
  python -u scripts/step2_pens/interior_tau_probe.py \
      --scalar-ckpt /home/doctor/carc_step2_pens/warmstart/warmstart.pt \
      --checkpoint /mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt \
      --games 40 --sims 100 --blend 0.27 --workers 12 \
      --out measurement/step2_pens/interior_tau
"""
from __future__ import annotations

# step2_leaf imports build_dataset, which sets the v2.9 GUARD env
# (CARCASSONNE_V25_* / V29_MEEPLE_CURVE / USE_FLAT_LEAF=1 / USE_CY_REPR=1 /
# VALUE_BLEND=0 + CUDA_VISIBLE_DEVICES="" / OMP=1) BEFORE virtual_score_v2's
# DEFAULT_CONFIG is frozen. Import it FIRST (mirrors gen_step2.py).
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import carcassonne_ai.step2_leaf as step2_leaf  # noqa: E402 (sets guard env)

import argparse  # noqa: E402
import importlib.util as _ilu  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
from value_ranking_train import kendall_tau_b  # noqa: E402

from carcassonne_ai.evaluators import make_single_evaluator_policy_only  # noqa: E402
from carcassonne_ai.features import N_SCALAR_FEATURES  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.selfplay import play_one_selfplay_game  # noqa: E402

import eval_hybrid_handoff as EH  # noqa: E402

# ScalarMLP from THIS package's train_warmstart.py (scripts/train_warmstart.py
# shadows a plain import — load by path, exactly like gen_step2.py does).
_tw_spec = _ilu.spec_from_file_location(
    "step2_train_warmstart", str(REPO / "scripts" / "step2_pens" / "train_warmstart.py")
)
_tw = _ilu.module_from_spec(_tw_spec)
_tw_spec.loader.exec_module(_tw)
ScalarMLP = _tw.ScalarMLP

DEFAULT_BASE_CKPT = "/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt"
DEFAULT_SCALAR_CKPT = "/home/doctor/carc_step2_pens/warmstart/warmstart.pt"

# Depth buckets (plies from the search root). 1 = root siblings (the anchor).
BUCKETS = [("d1", 1, 1), ("d2_3", 2, 3), ("d4_7", 4, 7), ("d8p", 8, 10**9)]

_W: dict = {}


def _bucket_of(depth: int) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= depth <= hi:
            return name
    return "dUNK"


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


def _build_scalar_mlp(scalar_ckpt: str, device):
    ck = torch.load(scalar_ckpt, map_location=device, weights_only=False)
    mlp = ScalarMLP(int(ck["D"]), hidden=int(ck["hidden"]), blocks=int(ck["blocks"])).to(device)
    mlp.load_state_dict(ck["state_dict"])
    mlp.eval()
    cmean = np.asarray(ck["col_mean"], np.float32)
    cstd = np.asarray(ck["col_std"], np.float32)
    cstd = np.where(cstd < 1e-6, 1.0, cstd).astype(np.float32)
    feat_names = [str(x) for x in ck["feat_names"]]
    return mlp, cmean, cstd, feat_names


def _worker_init(cfg: dict) -> None:
    global _W
    device = torch.device("cpu")  # net-on-CPU, matches the play recipe
    torch.set_num_threads(1)
    leaf_cfg = EH._heur_leaf_cfg(2.0)
    base_net, include_farm = _load_base_net(cfg["checkpoint"], device)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    base_ev = make_single_evaluator_policy_only(base_net, device, game)
    mlp, cmean, cstd, feat_names = _build_scalar_mlp(cfg["scalar_ckpt"], device)
    if list(feat_names) != list(step2_leaf.FEAT_NAMES):
        raise ValueError("feat_names mismatch with build_dataset.FEAT_NAMES")
    _W.update(
        device=device, leaf_cfg=leaf_cfg, game=game, base_ev=base_ev,
        mlp=mlp, cmean=cmean, cstd=cstd, feat_names=feat_names, cfg=cfg,
    )


def _net_value_parent_pov(child_board, parent_board) -> float:
    """The ScalarMLP value over the parent-threaded 89-vec for `child_board`.

    This is the PARENT-POV value (extract_step2_features keys to
    parent_board.current_player) — exactly `step2_leaf._mlp_value`, the value the
    leaf consumes BEFORE the `_v_mlp_leafpov` leaf-POV flip. We compare it against
    a target ALSO put in parent-POV, so no flip is applied here (the warmstart's
    net-alone tau compared parent-POV pred vs parent-POV oracle_q identically)."""
    feat = step2_leaf.extract_step2_features(_W["game"], child_board, _W["leaf_cfg"], parent_board)
    x = (feat - _W["cmean"]) / _W["cstd"]
    xt = torch.from_numpy(x.astype(np.float32)).unsqueeze(0)
    with torch.no_grad():
        v = _W["mlp"](xt)
    return float(v.reshape(-1)[0].item())


def _traverse_tree_groups(mcts, root_board, min_child_visits, max_children):
    """BFS the LIVE search tree from the root. Yield (depth, parent_node, [children]).

    depth = plies from the search root (root=0; its children=depth-1 nodes whose
    sibling GROUP is bucketed as depth 1). A node is an interior PARENT iff it has
    >=2 deduped, non-terminal, board-recorded children each with N>=min_child_visits.

    The tree is a DAG (transpositions share a node); we assign each node the depth
    at which it is FIRST reached in BFS (shortest path from root) and visit each
    node once. record_boards=True guarantees expanded non-terminal nodes carry
    `.board`. Children are read via the SAME _deduped_children the gen uses so
    transposition rotations are collapsed (no double-counted child)."""
    root_key = mcts.game.string_representation(root_board)
    root = mcts._nodes.get(root_key)
    if root is None:
        return
    # BFS with first-seen depth. A node's GROUP is bucketed by the node's depth+1
    # (its children are one ply deeper); we report depth-of-children == node_depth+1.
    seen = {id(root)}
    frontier = [(root, 0)]  # (node, node_depth_from_root)
    while frontier:
        nxt = []
        for node, ndepth in frontier:
            if (not node.expanded) or node.is_terminal or node.board is None:
                continue
            kids = []
            for _a, child in mcts._deduped_children(node):
                if child.board is None or child.is_terminal or child.N < min_child_visits:
                    continue
                kids.append(child)
            # children's sibling-group depth = node_depth + 1 (root's kids => 1)
            child_group_depth = ndepth + 1
            if len(kids) >= 2:
                kids_sorted = sorted(kids, key=lambda c: c.N, reverse=True)[:max_children]
                yield child_group_depth, node, kids_sorted
            # enqueue children for further descent (use ALL deduped children, not
            # just the >=min_visits ones, so we don't prune the tree's deep spine)
            for _a, child in mcts._deduped_children(node):
                if id(child) in seen:
                    continue
                seen.add(id(child))
                nxt.append((child, ndepth + 1))
        frontier = nxt


def _play_one(args_tuple):
    seed, = args_tuple
    cfg = _W["cfg"]
    counters = step2_leaf._Step2Counters()
    wrapped = step2_leaf.make_step2_value_wrapper(
        _W["base_ev"], _W["mlp"], _W["cmean"], _W["cstd"], _W["feat_names"],
        game=_W["game"], leaf_cfg=_W["leaf_cfg"], blend=cfg["blend"],
        dropout_p=0.0, device=_W["device"], rng_seed=seed ^ 0x5715B2,
        counters=counters,
    )

    # Per-game accumulator: bucket -> list of (tau, n_children)
    rows = {name: [] for name, _, _ in BUCKETS}
    rows["dUNK"] = []

    def _on_ply_search(mcts, parent_board, board, cur_player, ply):
        # `board` is the search root for the search that just ran; tree is live.
        for cdepth, parent_node, kids in _traverse_tree_groups(
            mcts, board, cfg["min_child_visits"], cfg["max_children"]
        ):
            parent_b = parent_node.board
            parent_player = parent_node.player_to_move
            net_vals, targets = [], []
            for child in kids:
                net_vals.append(_net_value_parent_pov(child.board, parent_b))
                q = float(child.Q)
                # flip child-own-POV Q to parent-node POV (matches rank-emit + oracle_q)
                targets.append(q if child.player_to_move == parent_player else -q)
            tau = kendall_tau_b(np.asarray(net_vals), np.asarray(targets))
            if tau == tau:  # not NaN
                rows[_bucket_of(cdepth)].append((float(tau), len(kids)))

    t0 = time.perf_counter()
    try:
        play_one_selfplay_game(
            game=_W["game"], evaluator=wrapped,
            sims=cfg["sims"], c_puct=cfg["c_puct"],
            dirichlet_alpha=cfg["dirichlet_alpha"], dirichlet_eps=cfg["dirichlet_eps"],
            temp_threshold=cfg["temp_threshold"], seed=seed, batch_size=1,
            value_target=cfg["value_target"],
            on_ply_search=_on_ply_search,
            record_boards_override=True,  # store every expanded node's board
        )
    except Exception as e:
        import traceback
        return (seed, "failed", None, time.perf_counter() - t0,
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}", counters.as_dict())
    dt = time.perf_counter() - t0
    # serialize per-bucket tau lists (mean computed in main over all games)
    out = {b: rows[b] for b in rows}
    return (seed, "ok", out, dt, None, counters.as_dict())


def main(argv=None):
    p = argparse.ArgumentParser(prog="interior_tau_probe")
    p.add_argument("--checkpoint", default=DEFAULT_BASE_CKPT)
    p.add_argument("--scalar-ckpt", default=DEFAULT_SCALAR_CKPT)
    p.add_argument("--out", default="measurement/step2_pens/interior_tau")
    p.add_argument("--games", type=int, default=40)
    p.add_argument("--sims", type=int, default=100)
    p.add_argument("--blend", type=float, default=0.27)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--c-puct", type=float, default=3.0)
    p.add_argument("--dirichlet-alpha", type=float, default=0.3)
    p.add_argument("--dirichlet-eps", type=float, default=0.25)
    p.add_argument("--temp-threshold", type=int, default=15)
    p.add_argument("--value-target", default="score_diff_wide")
    p.add_argument("--min-child-visits", type=int, default=3,
                   help="min MCTS visits for a child to enter its parent's group "
                        "(matches gen's --rank-min-child-visits default 3).")
    p.add_argument("--max-children", type=int, default=16)
    p.add_argument("--seed-base", type=int, default=900000)
    args = p.parse_args(argv)

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Provenance: confirm the v2.9 leaf cfg matches the frozen hash the dataset used.
    leaf_cfg = EH._heur_leaf_cfg(2.0)
    cfg_hash = step2_leaf._bd._cfg_hash(leaf_cfg)
    frozen = step2_leaf._bd.FROZEN_V29_HASH
    print(f"[provenance] v2.9 leaf config_hash = {cfg_hash} (frozen v2.9 = {frozen})", flush=True)
    assert cfg_hash == frozen, f"LEAF NOT v2.9 (got {cfg_hash}, want {frozen})"

    cfg = dict(
        checkpoint=args.checkpoint, scalar_ckpt=args.scalar_ckpt,
        sims=args.sims, blend=args.blend, c_puct=args.c_puct,
        dirichlet_alpha=args.dirichlet_alpha, dirichlet_eps=args.dirichlet_eps,
        temp_threshold=args.temp_threshold, value_target=args.value_target,
        min_child_visits=args.min_child_visits, max_children=args.max_children,
    )
    seeds = [(args.seed_base + i,) for i in range(args.games)]

    print(f"[run] {args.games} games sims={args.sims} blend={args.blend} "
          f"workers={args.workers} scalar={args.scalar_ckpt}", flush=True)
    t0 = time.perf_counter()

    # bucket -> list of (tau, n_children) across ALL games
    agg = {name: [] for name, _, _ in BUCKETS}
    agg["dUNK"] = []
    counters_sum = {"calls": 0, "scalar_path": 0, "plain_path": 0, "dropout_path": 0, "terminal_path": 0}
    n_done = n_fail = 0

    def _absorb(res):
        nonlocal n_done, n_fail
        seed, status, out, dt, err, cnt = res
        for k in counters_sum:
            counters_sum[k] += cnt.get(k, 0)
        if status != "ok":
            n_fail += 1
            print(f"[game {seed}] FAILED in {dt:.1f}s: {err}", flush=True)
            return
        n_done += 1
        for b, lst in out.items():
            agg.setdefault(b, []).extend([tuple(x) for x in lst])
        ng = sum(len(v) for v in out.values())
        print(f"[game {seed}] ok {dt:.1f}s  groups={ng}  "
              f"(scalar_path={cnt['scalar_path']})", flush=True)

    ctx = mp.get_context("spawn")
    if args.workers <= 1:
        _worker_init(cfg)
        for s in seeds:
            _absorb(_play_one(s))
    else:
        with ctx.Pool(args.workers, initializer=_worker_init, initargs=(cfg,)) as pool:
            for res in pool.imap_unordered(_play_one, seeds):
                _absorb(res)

    elapsed = time.perf_counter() - t0

    # --- aggregate: mean tau (unweighted over groups) + n_groups per bucket --- #
    table = {}
    for name, _, _ in BUCKETS:
        lst = agg.get(name, [])
        taus = np.asarray([t for (t, _n) in lst], dtype=np.float64)
        nchild = np.asarray([n for (_t, n) in lst], dtype=np.float64)
        n_groups = len(taus)
        mean_tau = float(np.mean(taus)) if n_groups else float("nan")
        sd_tau = float(np.std(taus, ddof=1)) if n_groups > 1 else float("nan")
        se_tau = (sd_tau / np.sqrt(n_groups)) if n_groups > 1 else float("nan")
        table[name] = {
            "mean_tau": mean_tau,
            "n_groups": n_groups,
            "sd_tau": sd_tau,
            "se_tau": float(se_tau) if se_tau == se_tau else float("nan"),
            "mean_children_per_group": float(np.mean(nchild)) if n_groups else float("nan"),
        }
    # dUNK (out-of-range depths) reported for completeness if non-empty
    if agg.get("dUNK"):
        taus = np.asarray([t for (t, _n) in agg["dUNK"]], dtype=np.float64)
        table["dUNK"] = {"mean_tau": float(np.mean(taus)), "n_groups": len(taus)}

    # --- HOLD vs COLLAPSE heuristic (the orchestrator makes the FINAL call) --- #
    seq = [table[name]["mean_tau"] for name, _, _ in BUCKETS
           if table[name]["n_groups"] > 0]
    bnames = [name for name, _, _ in BUCKETS if table[name]["n_groups"] > 0]
    verdict = "INSUFFICIENT_DATA"
    if len(seq) >= 3:
        d1 = table["d1"]["mean_tau"] if table["d1"]["n_groups"] > 0 else float("nan")
        deepest = seq[-1]
        drop = (d1 - deepest) if d1 == d1 else float("nan")
        monotone = all(seq[i] >= seq[i + 1] - 0.03 for i in range(len(seq) - 1))
        if drop == drop and drop > 0.12 and monotone:
            verdict = "COLLAPSE"
        elif drop == drop and abs(drop) <= 0.10:
            verdict = "HOLD"
        else:
            verdict = "MIXED"

    result = {
        "probe": "step2_pens_interior_tau_depth_stratified",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "scalar_ckpt": args.scalar_ckpt,
            "policy_checkpoint": args.checkpoint,
            "blend": args.blend,
            "sims": args.sims,
            "c_puct": args.c_puct,
            "dirichlet_alpha": args.dirichlet_alpha,
            "dirichlet_eps": args.dirichlet_eps,
            "temp_threshold": args.temp_threshold,
            "value_target": args.value_target,
            "min_child_visits": args.min_child_visits,
            "max_children": args.max_children,
            "games_requested": args.games,
            "games_ok": n_done,
            "games_failed": n_fail,
            "workers": args.workers,
            "net_on_cpu": True,
            "v29_leaf_hash": cfg_hash,
        },
        "method": {
            "tau_variant": "kendall_tau_b (value_ranking_train.kendall_tau_b)",
            "pov": "net_value parent-POV (extract_step2_features keyed to parent.current_player == _mlp_value, the pre-flip value the leaf consumes) vs backed-up child.Q flipped to parent-node POV (q if child_player==parent_player else -q). Same frame as warmstart net-alone tau.",
            "depth_def": "plies from the search root; sibling GROUP depth = parent_node_depth + 1 (root's children = depth 1).",
            "node_filter": "interior parent: expanded, non-terminal, board recorded, >=2 deduped non-terminal children each with N>=min_child_visits.",
            "buckets": {name: [lo, hi] for name, lo, hi in BUCKETS},
            "warmstart_net_alone_tau_anchor_overall": 0.42692801505810024,
            "warmstart_net_alone_tau_anchor_endgame": 0.35287901602861116,
        },
        "depth_table": table,
        "depth_anchor_d1_should_approx": 0.427,
        "verdict_heuristic": verdict,
        "elapsed_sec": elapsed,
        "counters_sum": counters_sum,
    }

    (out_dir / "interior_tau_results.json").write_text(json.dumps(result, indent=2))

    # also a flat CSV for quick eyeballing
    csv_lines = ["bucket,depth_lo,depth_hi,mean_tau,sd_tau,se_tau,n_groups,mean_children_per_group"]
    for name, lo, hi in BUCKETS:
        t = table[name]
        csv_lines.append(
            f"{name},{lo},{hi if hi < 10**8 else 'inf'},{t['mean_tau']:.4f},"
            f"{t.get('sd_tau', float('nan'))},{t.get('se_tau', float('nan'))},"
            f"{t['n_groups']},{t.get('mean_children_per_group', float('nan'))}"
        )
    (out_dir / "interior_tau_table.csv").write_text("\n".join(csv_lines) + "\n")

    # console summary
    print("\n==== STEP-2 PeNS INTERIOR-TAU DEPTH STRATIFICATION ====", flush=True)
    print(f"games ok={n_done} failed={n_fail}  elapsed={elapsed:.1f}s  "
          f"blend={args.blend} sims={args.sims}", flush=True)
    print(f"{'bucket':<8}{'depth':<10}{'mean_tau':>10}{'se':>8}{'n_groups':>10}{'kids/grp':>10}", flush=True)
    for name, lo, hi in BUCKETS:
        t = table[name]
        drng = f"{lo}" if lo == hi else (f"{lo}+" if hi >= 10**8 else f"{lo}-{hi}")
        se = t.get("se_tau", float("nan"))
        print(f"{name:<8}{drng:<10}{t['mean_tau']:>10.3f}"
              f"{(se if se == se else float('nan')):>8.3f}"
              f"{t['n_groups']:>10}{t.get('mean_children_per_group', float('nan')):>10.2f}",
              flush=True)
    print(f"\nd1 anchor (should ~0.427 warmstart net-alone): {table['d1']['mean_tau']:.3f} "
          f"(n={table['d1']['n_groups']})", flush=True)
    print(f"VERDICT HEURISTIC: {verdict}  "
          f"(orchestrator makes the final Gate-B call)", flush=True)
    print(f"-> {out_dir}/interior_tau_results.json", flush=True)
    print(f"-> {out_dir}/interior_tau_table.csv", flush=True)


if __name__ == "__main__":
    main()
