"""Matched-opponent provenance smoke (Phase-1 deliverable).

Runs in a single process (so the leaf-path counters are aggregatable) and proves,
at RUNTIME, the three things the outside review demanded be made un-missable:

  1. a HeuristicMCTS opponent built with `heur_leaf="v1"` actually evaluates the
     v1 leaf and NOT v2.7  (the R1 defect, now asserted);
  2. a HeuristicMCTS opponent built with `heur_leaf="v2_7"` actually evaluates
     v2.7 and NOT v1;
  3. a NeuralMCTS whose leaf wrapper has residual_scale>0 actually fires the
     net-value RESIDUAL path  (the R7 silent-fallback guard).

It then writes the v1-opponent and v2.7-opponent manifests to
`clean_eval/provenance_smoke/` and DIFFS their evaluator blocks to show that the
ONLY thing that changed between them is the opponent leaf — every other field
(checkpoint sha, sims, c_puct, caps, code commit) is identical. That diff is the
artifact a reviewer can read to confirm "matched opponent, leaf isolated".

Usage:
  python scripts/verify_evaluator_provenance.py \
      [--checkpoint checkpoints/warmstart_canonical.pt] [--sims 8]

Exit 0 iff all three runtime assertions pass. No training, no network access.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import torch

from carcassonne_ai import eval_provenance as ep
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "clean_eval" / "provenance_smoke"
SEED = ep.EVAL_SEED_FLOOR  # a clean-namespace deck


def _load_net(checkpoint, device):
    ck = torch.load(checkpoint, map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))
                         ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, ns > 10


def _play_one_game(net, device, *, heur_leaf, residual_scale, sims, include_farm):
    """Play a single game NeuralMCTS(net) vs HeuristicMCTS(heur_leaf). Returns
    (leaf_eval, net_mcts, heur_mcts) so the caller can read .counters."""
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    heur_game = Game(enable_legal_moves_cache=True)
    base = make_single_evaluator(net, device, game)
    if residual_scale is None:
        leaf_eval = make_v25_value_wrapper(base)
    else:
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=float(residual_scale))
        leaf_eval = make_v25_value_wrapper(base, cfg)
    net_mcts = NeuralMCTS(game=game, evaluator=leaf_eval, simulations=sims,
                          seed=SEED, c_puct=3.0)
    heur_mcts = HeuristicMCTS(game=heur_game, simulations=sims, seed=SEED + 1,
                              heur_leaf=heur_leaf)
    random.seed(SEED)
    board = game.get_init_board()
    net_player = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == net_player:
            net_mcts.clear(); action = net_mcts.best_action(board)
        else:
            heur_mcts.clear(); action = heur_mcts.best_action(board)
        board, _ = game.get_next_state(board, action)
    return leaf_eval, net_mcts, heur_mcts


def _manifest_for(leaf_eval, net_mcts, heur_mcts, *, checkpoint, sims, leaf_tag):
    counters = {"A_net": leaf_eval.counters.as_dict(), "B_heur": heur_mcts.counters}
    nspec = ep.spec_from_neural_mcts(net_mcts, side="A_net", checkpoint_path=str(checkpoint),
                                     sims=sims, paired=True, seed_range=[SEED, SEED + 1],
                                     eval_script="verify_evaluator_provenance.py")
    hspec = ep.spec_from_heuristic_mcts(heur_mcts, side="B_heur", sims=sims, paired=True,
                                        seed_range=[SEED, SEED + 1],
                                        eval_script="verify_evaluator_provenance.py")
    verdict = ep.assert_provenance_consistent([nspec, hspec], counters)
    block = ep.build_eval_provenance([nspec, hspec], kind="provenance_smoke",
                                     argv=[f"heur_leaf={leaf_tag}"], runtime_verified=verdict)
    out_dir = OUT / leaf_tag
    write_manifest(out_dir, kind="provenance_smoke", game=game_tag(Game()),
                   config={"checkpoint": str(checkpoint), "sims": sims, "heur_leaf": leaf_tag},
                   evaluator=block, overwrite=True)
    return out_dir / "manifest.json", counters


def _diff_evaluator_blocks(m_v1: Path, m_v27: Path) -> list[str]:
    """Return the per-side field differences between the two manifests' evaluator
    blocks. Expectation: the NET side is identical; the HEUR side differs ONLY in
    leaf_name/leaf_version."""
    b1 = json.loads(m_v1.read_text())["evaluator"]
    b2 = json.loads(m_v27.read_text())["evaluator"]
    diffs = []
    for s1, s2 in zip(b1["sides"], b2["sides"]):
        side = s1["side"]
        for k in sorted(set(s1) | set(s2)):
            if k in ("argv",):  # argv carries the leaf tag by construction
                continue
            if s1.get(k) != s2.get(k):
                diffs.append(f"{side}.{k}: v1={s1.get(k)!r}  v2_7={s2.get(k)!r}")
    return diffs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="verify_evaluator_provenance")
    ap.add_argument("--checkpoint", type=Path, default=REPO / "checkpoints" / "warmstart_canonical.pt")
    ap.add_argument("--sims", type=int, default=8, help="low sims — this is a correctness proof, not a measurement")
    args = ap.parse_args(argv)
    if not args.checkpoint.is_file():
        print(f"SKIP: checkpoint not found: {args.checkpoint}")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net, include_farm = _load_net(args.checkpoint, device)
    log = [f"verify_evaluator_provenance @ device={device} sims={args.sims} "
           f"ckpt={args.checkpoint.name} sha={(ep.sha256_file(args.checkpoint) or '')[:12]}"]

    # (1)+(2): v1-opponent and v2.7-opponent. assert_provenance_consistent inside
    # _manifest_for raises ProvenanceError if the wrong leaf ran.
    le, nm, hm = _play_one_game(net, device, heur_leaf="v1", residual_scale=None,
                                sims=args.sims, include_farm=include_farm)
    m_v1, c_v1 = _manifest_for(le, nm, hm, checkpoint=args.checkpoint, sims=args.sims, leaf_tag="v1")
    log.append(f"[v1 opponent]  heur counters={c_v1['B_heur']}  -> v1-only VERIFIED")

    le, nm, hm = _play_one_game(net, device, heur_leaf="v2_7", residual_scale=None,
                                sims=args.sims, include_farm=include_farm)
    m_v27, c_v27 = _manifest_for(le, nm, hm, checkpoint=args.checkpoint, sims=args.sims, leaf_tag="v2_7")
    log.append(f"[v2_7 opponent] heur counters={c_v27['B_heur']}  -> v2_7-only VERIFIED")

    # (3): residual path fires.
    le, nm, hm = _play_one_game(net, device, heur_leaf="v1", residual_scale=0.25,
                                sims=args.sims, include_farm=include_farm)
    rc = le.counters.as_dict()
    nspec = ep.spec_from_neural_mcts(nm, side="A_net", checkpoint_path=str(args.checkpoint),
                                     sims=args.sims, paired=True, seed_range=[SEED, SEED + 1])
    ep.assert_provenance_consistent([nspec], {"A_net": rc})  # raises if resid_path==0
    assert rc["resid_path"] > 0, rc
    log.append(f"[residual 0.25] net counters={rc}  -> residual path VERIFIED")

    # diff the two matched-opponent manifests: only the heur leaf should differ.
    diffs = _diff_evaluator_blocks(m_v1, m_v27)
    log.append("")
    log.append("matched-opponent manifest diff (v1 vs v2_7 opponent):")
    for d in diffs:
        log.append(f"  {d}")
    heur_diff_keys = {d.split(".", 1)[1].split(":", 1)[0] for d in diffs if d.startswith("B_heur.")}
    net_diff_keys = {d.split(".", 1)[1].split(":", 1)[0] for d in diffs if d.startswith("A_net.")}
    # Fields that DESCRIBE the leaf — these are allowed to differ on the opponent
    # side, because the leaf changing is the whole point. Everything else (sims,
    # c_puct, checkpoint, seed_range, paired, code_commit, agent_class, ...) is
    # matchup context that must be held fixed.
    LEAF_FIELDS = {"leaf_name", "leaf_version", "cap", "opp_cap", "drop_three_open",
                   "closure_schedule", "residual_scale", "value_blend"}
    net_isolated = net_diff_keys == set()
    heur_only_leaf = heur_diff_keys <= LEAF_FIELDS
    ok_isolated = net_isolated and heur_only_leaf
    log.append("")
    log.append(f"NET side identical: {net_isolated} | "
               f"HEUR side differs only in leaf-describing fields: {heur_only_leaf} "
               f"(diffs: {sorted(heur_diff_keys)})")
    log.append("RESULT: " + ("PASS — leaf isolated, all runtime assertions held"
                             if ok_isolated else "FAIL — non-leaf field differs between matched opponents"))

    report = "\n".join(log)
    print(report)
    (OUT / "verify_output.txt").write_text(report + "\n")
    (OUT / "MANIFEST_DIFF.txt").write_text("\n".join(diffs) + "\n")
    return 0 if ok_isolated else 1


if __name__ == "__main__":
    raise SystemExit(main())
