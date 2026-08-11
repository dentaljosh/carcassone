#!/usr/bin/env python3
"""Sampling frame + difficulty tags for the MOVE-AGREEMENT-vs-BUDGET probe.

WHAT THIS DOES
--------------
Builds the pre-registered root sample for `move_agreement_probe.py` from the champion's
OWN play distribution — `measurement/champ_action_logs/champ_games.jsonl`, 449 complete
fair-PIMC k4x688 (= the deploy budget) self-play games with full `(deck_seed, actions)`
action logs, round-trip proven lossless (CORPUS_MANIFEST.json).

Two passes:

  PASS 1 (census, no search).  Replay every game ply-by-ply and record, for each ply,
  the properties that decide ELIGIBILITY and STRATUM: n_legal, phase, k_remaining
  (= undrawn deck + tile in hand, fair_agent.k_remaining), tiles_placed. Eligibility:
  non-terminal AND n_legal >= 2 (a forced move is trivially in agreement at every
  budget and would dilute the headline — fair_agent._pimc_move short-circuits it
  without searching at all).

  PASS 2 (tags).  For each SAMPLED root, compute two independent difficulty tags:
    * `h200_top2_q_gap` — the measurement-infra standard (tagging.py): HeuristicMCTS(200)
      on the TRUE board, top-2 backed-up Q gap. CLAIRVOYANT (it sees the real deck) and
      from a DIFFERENT search family (random-expansion UCT) than the agent under test,
      which is exactly why it is usable as an exogenous stratifier: it cannot be a
      restatement of the fair-PIMC quantity whose stability we are measuring.
    * `blind_top2_q_gap` — a cheap BLIND alternative: fair PIMC k4x86 (total 344, the
      curve's bottom rung) pooled top-2 Q gap, drawn on a DEDICATED tag seed lineage
      (`--tag-salt`, disjoint from every salt the probe uses) so it is independent of
      the picks being compared.

  Neither tag is ever shown to the agent under test. Both are recorded; which one is the
  PRIMARY stratifier is fixed in the pre-registration, not here.

Output: one JSONL row per root, in the schema `move_agreement_probe.py` consumes
(`deck_seed` + `actions` + `ply`, the root_replay lossless contract).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to gate_b_fair_pimc.py / eval_fair_puct's
#     _CANON_ENV. MUST run before importing carcassonne_ai (DEFAULT_CONFIG is import-frozen).
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

REPO = Path(__file__).resolve().parents[2]
# CARC_SRC_ROOT lets the probe run against the PINNED worktree's src (the tree verified
# byte-identical to what produced the blind curve) while the harness itself stays
# committed in the main tree. Recorded + asserted in the manifest.
SRC_ROOT = os.environ.get("CARC_SRC_ROOT") or str(REPO / "src")
sys.path.insert(0, SRC_ROOT)
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import argparse  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402

import root_replay as RR  # noqa: E402
import snapshot as SNAP  # noqa: E402
import tagging as TAG  # noqa: E402

# Game-phase strata. FIXED cut points (not sample quantiles) so the boundaries cannot
# drift with the sample: base deck is 72 tiles, so these are ~thirds of the game.
PHASE_CUTS = {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}


def phase_bucket(k_remaining: int) -> str:
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k_remaining < hi:
            return name
    return "late"


# --------------------------------------------------------------------------- #
# PASS 1 — per-game ply census (no search)                                      #
# --------------------------------------------------------------------------- #
def _census_game(rec: dict) -> list:
    """Replay one game and describe every ply. Pure engine, no search."""
    deck_seed = int(rec["deck_seed"])
    actions = [int(a) for a in rec["actions"]]
    out = []
    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    # Every recorded ply is non-terminal by construction (an action was played from it),
    # so no get_game_ended probe is needed — we only describe what was actually reached.
    for ply, a in enumerate(actions):
        legal = int(np.count_nonzero(game.get_valid_moves(board)))
        k_rem = FA.k_remaining(board.state)
        out.append({
            "deck_seed": deck_seed, "ply": ply,
            "n_legal": legal,
            "phase": ("TILES" if board.state.phase == GamePhase.TILES else "MEEPLES"),
            "k_remaining": int(k_rem),
            "phase_bucket": phase_bucket(int(k_rem)),
            "player_to_move": int(board.state.current_player),
        })
        board, _ = game.get_next_state(board, a)
    return out


# --------------------------------------------------------------------------- #
# PASS 2 — difficulty tags for a sampled root                                   #
# --------------------------------------------------------------------------- #
_CFG = None
_TAG_SALT = None
_TAG_KDETS = None
_TAG_SIMS = None


def _init_tag(cfg, tag_salt, k_dets, sims):
    global _CFG, _TAG_SALT, _TAG_KDETS, _TAG_SIMS
    _CFG, _TAG_SALT, _TAG_KDETS, _TAG_SIMS = cfg, int(tag_salt), int(k_dets), int(sims)


def tag_seed(deck_seed: int, ply: int, salt: int) -> int:
    """Seed lineage for a (root, salt). Shared with move_agreement_probe.root_seed —
    the tag salt must be DISJOINT from every probe salt or the tag stops being
    independent of the picks it stratifies."""
    return (int(deck_seed) * 1_000_003 + int(ply) * 8191
            + int(salt) * 2_654_435_761) & 0x7FFFFFFF


def _tag_root(r: dict) -> dict:
    out = dict(r)
    t0 = time.time()
    try:
        game, board = RR.replay_actions(int(r["deck_seed"]), r["actions"], int(r["ply"]))
        out["checksum"] = game.string_representation(board)
        legal = np.flatnonzero(game.get_valid_moves(board))
        out["n_legal"] = int(legal.size)

        # --- tag A: h200 clairvoyant top-2 Q gap (measurement_infra standard) ------
        # make_heuristic_agent wants the LeafConfig, not the HeuristicPriorConfig wrapper.
        ag = SNAP.make_heuristic_agent(200, _CFG.leaf_cfg,
                                       seed=tag_seed(r["deck_seed"], r["ply"], 9001))
        ag.clear()
        ag.rng = random.Random(tag_seed(r["deck_seed"], r["ply"], 9001))
        t = TAG.tag_root(ag, board, sims=200)
        out["h200_top2_q_gap"] = float(t["top2_q_gap"])
        out["h200_entropy"] = float(t["entropy"])
        out["h200_top_share"] = float(t["top_share"])
        out["h200_n_visited"] = int(t["n_visited"])

        # --- tag B: BLIND fair-PIMC k4x{sims} pooled top-2 Q gap, dedicated salt ---
        agent = CF.build_fair_champion(game, sims=_TAG_SIMS, k_dets=_TAG_KDETS,
                                       seed=tag_seed(r["deck_seed"], r["ply"], _TAG_SALT),
                                       cfg=_CFG)
        base = agent.det_seed_base(0)
        det_rng = random.Random(base + 1)
        root_key = game.string_representation(board)
        agg_n: dict = {}
        agg_w: dict = {}
        from collections import defaultdict
        agg_n, agg_w = defaultdict(float), defaultdict(float)
        for i in range(_TAG_KDETS):
            b = FA.FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            m = NeuralMCTS(game=game, evaluator=agent._evaluator, simulations=_TAG_SIMS,
                           c_puct=agent._c_puct, seed=base + 100 + i)
            m.search(b)
            root = m._nodes.get(root_key) or m._nodes[game.string_representation(b)]
            FA.pool_root_stats(root, agg_n, agg_w)
            m.clear()
        qs = sorted((agg_w[a] / agg_n[a] for a in agg_n if agg_n[a] > 0), reverse=True)
        out["blind_top2_q_gap"] = float(qs[0] - qs[1]) if len(qs) >= 2 else None
        out["blind_n_children"] = int(len(agg_n))
        out["ok"] = True
    except Exception as e:  # noqa
        import traceback
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-1500:]
    out["tag_secs"] = round(time.time() - t0, 3)
    return out


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sample + tag roots for the move-agreement probe")
    ap.add_argument("--games", default=str(REPO / "measurement" / "champ_action_logs"
                                           / "champ_games.jsonl"))
    ap.add_argument("--out", default=str(REPO / "measurement" / "classical_search"
                                         / "data" / "move_agreement_roots.jsonl"))
    ap.add_argument("--n", type=int, default=600, help="roots to sample (PRE-REGISTER THIS)")
    ap.add_argument("--sample-seed", type=int, default=20260727,
                    help="sampling seed (PRE-REGISTER THIS)")
    ap.add_argument("--max-per-game", type=int, default=2,
                    help="cap roots drawn from any one game (within-game correlation)")
    ap.add_argument("--tag-salt", type=int, default=9000,
                    help="seed lineage for the BLIND tag; MUST be disjoint from probe salts")
    ap.add_argument("--tag-kdets", type=int, default=4)
    ap.add_argument("--tag-sims", type=int, default=86, help="per-world sims for the blind tag")
    ap.add_argument("--workers", type=int, default=14)
    args = ap.parse_args(argv)

    from carcassonne_ai import fair_agent as _fa
    print(f"[sample] carcassonne_ai.fair_agent -> {_fa.__file__}", flush=True)

    games = [json.loads(l) for l in Path(args.games).read_text().splitlines() if l.strip()]
    print(f"[sample] games={len(games)} from {args.games}", flush=True)

    ctx = get_context("fork")
    t0 = time.time()
    with ctx.Pool(args.workers) as pool:
        per_game = pool.map(_census_game, games, chunksize=4)
    plies = [p for g in per_game for p in g]
    print(f"[sample] census: {len(plies)} plies in {time.time()-t0:.1f}s", flush=True)

    eligible = [p for p in plies if p["n_legal"] >= 2]
    print(f"[sample] eligible (n_legal>=2): {len(eligible)} "
          f"({100*len(eligible)/max(1,len(plies)):.1f}%)", flush=True)

    # --- PRE-REGISTERED sample: uniform over eligible plies, capped per game -------
    rng = random.Random(args.sample_seed)
    order = list(range(len(eligible)))
    rng.shuffle(order)
    per_game_count: Counter = Counter()
    picked = []
    for i in order:
        p = eligible[i]
        if per_game_count[p["deck_seed"]] >= args.max_per_game:
            continue
        per_game_count[p["deck_seed"]] += 1
        picked.append(p)
        if len(picked) >= args.n:
            break
    picked.sort(key=lambda p: (p["deck_seed"], p["ply"]))
    print(f"[sample] picked {len(picked)} roots from {len(per_game_count)} games", flush=True)

    actions_by_seed = {int(g["deck_seed"]): [int(a) for a in g["actions"]] for g in games}
    roots = [dict(p, actions=actions_by_seed[p["deck_seed"]]) for p in picked]

    spec = CF.load_production_spec()
    cfg = CF.production_prior_cfg(spec)

    t0 = time.time()
    with ctx.Pool(args.workers, initializer=_init_tag,
                  initargs=(cfg, args.tag_salt, args.tag_kdets, args.tag_sims)) as pool:
        tagged = pool.map(_tag_root, roots, chunksize=1)
    print(f"[sample] tagged {len(tagged)} roots in {time.time()-t0:.1f}s", flush=True)

    bad = [t for t in tagged if not t.get("ok")]
    if bad:
        print(f"[sample] !! {len(bad)} tag failures; first: {bad[0].get('error')}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for t in tagged:
            fh.write(json.dumps(t) + "\n")

    ok = [t for t in tagged if t.get("ok")]
    gaps = sorted(t["h200_top2_q_gap"] for t in ok)
    bgaps = sorted(t["blind_top2_q_gap"] for t in ok if t.get("blind_top2_q_gap") is not None)
    manifest = {
        "kind": "move_agreement_root_sample",
        "games_source": args.games,
        "n_games": len(games),
        "n_plies_total": len(plies),
        "n_plies_eligible": len(eligible),
        "eligibility_rule": "non-terminal AND n_legal >= 2 (forced moves excluded: "
                            "fair_agent._pimc_move short-circuits them without searching)",
        "sampling_rule": "uniform without replacement over eligible plies, "
                         f"max {args.max_per_game} per game, seed {args.sample_seed}",
        "n_sampled": len(picked),
        "n_source_games_used": len(per_game_count),
        "src_root": SRC_ROOT,
        "fair_agent_file": _fa.__file__,
        "phase_cuts_k_remaining": {k: list(v) for k, v in PHASE_CUTS.items()},
        "phase_bucket_counts": dict(Counter(t["phase_bucket"] for t in ok)),
        "game_phase_counts": dict(Counter(t["phase"] for t in ok)),
        "n_legal_median": float(np.median([t["n_legal"] for t in ok])) if ok else None,
        "h200_top2_q_gap_median": (gaps[len(gaps) // 2] if gaps else None),
        "blind_top2_q_gap_median": (bgaps[len(bgaps) // 2] if bgaps else None),
        "tag_salt": args.tag_salt, "tag_kdets": args.tag_kdets, "tag_sims": args.tag_sims,
        "n_tag_failures": len(bad),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "leaf_manifest": CF.resolved_manifest("fair", spec, verify=True),
    }
    (out.parent / "move_agreement_roots_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("[sample] MANIFEST:", json.dumps(
        {k: v for k, v in manifest.items() if k != "leaf_manifest"}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
