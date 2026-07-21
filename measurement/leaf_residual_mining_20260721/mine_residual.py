#!/usr/bin/env python3
"""Leaf residual-mining — the LABELING harness.

For each sampled midgame root it records

    V_leaf   = tanh( flat_virtual_score_v2_float(root, mover, champ_cfg) / 15 )
    V_deep(L)= pooled root value of the DEPLOYED fair-PIMC champion at k_dets=4,
               sims_per_det=L  ==  sum_a W_pooled(a) / sum_a N_pooled(a)
    resid(L) = V_deep(L) - V_leaf                       (mover POV, units of value)

plus the pre-registered feature dictionary (``leaf_features.py``).

The search is the SAME machinery as ``scripts/measurement_infra/gate_b_fair_pimc.py``
(imported, not re-implemented): k_dets reshuffled determinizations, one deep search
per world snapshotted at every level (bit-exact WITHIN a world), pooled at each
level.  ONE deep search per world therefore yields all levels for the price of the
deepest.

See PREREG.md for the pre-registered definitions, the feature dictionary, the
split, the multiple-comparisons correction and the gate.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# --- Production leaf env — byte-identical to gate_b_fair_pimc.py / eval_fair_puct's
#     _CANON_ENV.  MUST run before importing carcassonne_ai (DEFAULT_CONFIG is
#     import-frozen).  curve125 is injected in-process by champion_factory. ------- #
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

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402
from multiprocessing import get_context  # noqa: E402

from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.fair_agent import (  # noqa: E402
    FairHeuristicMCTSAgent,
    k_remaining as fair_k_remaining,
)
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402

import gate_b_fair_pimc as GBF  # noqa: E402  (snapshot_world_search, read_children_nw)
import root_replay as RR  # noqa: E402
import leaf_features as LF  # noqa: E402

DEFAULT_LEVELS = (200, 344, 688, 1376)  # per-world; totals k4x{...} = 800/1376/2752/5504
PRIMARY_LEVEL = 688                     # == the DEPLOYED champion budget (CL-054 k4x688)

_CFG = None
_LEVELS = None
_KDETS = None
_WALL = None


# --------------------------------------------------------------------------- #
# Root sampling (deterministic, seeded by deck_seed)                            #
# --------------------------------------------------------------------------- #
def sample_roots(games, per_game: int, tiles_lo: int, tiles_hi: int, corpus: str,
                 corpus_champ125: int):
    """Pick `per_game` TILES-phase midgame plies per game, uniformly without
    replacement, RNG seeded by the game's deck_seed (so the sample is a pure
    function of the corpus + the pre-registered band, reproducible anywhere).

    TILES-phase plies are the EVEN indices of the action sequence (the engine
    alternates tile-placement / meeple-placement); at even ply p the number of
    tiles remaining (deck + the in-hand next_tile) is 72 - p//2.
    """
    out = []
    for g in games:
        n = len(g.actions)
        elig = [p for p in range(0, n, 2) if tiles_lo <= (72 - p // 2) <= tiles_hi]
        if not elig:
            continue
        rng = random.Random(int(g.deck_seed) * 7919 + 11)
        k = min(per_game, len(elig))
        for ply in sorted(rng.sample(elig, k)):
            out.append({"corpus": corpus, "corpus_champ125": corpus_champ125,
                        "game_id": int(g.game_id), "deck_seed": int(g.deck_seed),
                        "ply": int(ply), "actions": g.actions})
    return out


# --------------------------------------------------------------------------- #
def _root_seed(deck_seed: int, ply: int) -> int:
    """Same lineage rule as gate_b_{depth_transfer,fair_pimc}._root_seed."""
    return (int(deck_seed) * 1_000_003 + int(ply)) & 0x7fffffff


def _process_root(r: dict) -> dict:
    root_id = f"{r['corpus']}_s{r['deck_seed']}_p{r['ply']}"
    rec = {"root_id": root_id, "corpus": r["corpus"], "game_id": r["game_id"],
           "deck_seed": r["deck_seed"], "ply": r["ply"],
           "levels": list(_LEVELS), "k_dets": int(_KDETS), "info_mode": "fair_pimc"}
    t0 = time.time()

    def _on_alarm(signum, frame):
        raise TimeoutError("per-root wall cap")
    old = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(int(_WALL))
    try:
        game, board = RR.replay_actions(int(r["deck_seed"]), r["actions"], int(r["ply"]))
        st = board.state
        assert st.phase == GamePhase.TILES, f"root is not TILES phase: {st.phase}"
        mover = int(st.current_player)
        rec["mover"] = mover
        rec["tiles_remaining"] = int(len(st.deck) + 1)

        rseed = _root_seed(r["deck_seed"], r["ply"])
        rec["mcts_seed"] = rseed
        max_L = max(_LEVELS)
        agent = CF.build_fair_champion(game, sims=max_L, k_dets=int(_KDETS),
                                       seed=rseed, cfg=_CFG)

        k_rem = fair_k_remaining(st)
        rec["k_remaining"] = int(k_rem)
        rec["exact_latch"] = bool(agent._exact_endgame and st.phase == GamePhase.TILES
                                  and k_rem <= agent._exact_max_k)
        if rec["exact_latch"]:
            # Out of the pre-registered midgame band by construction, but assert
            # rather than assume: a latched root's decision is the solver's, not the
            # leaf-driven PIMC search's, so its residual would not be comparable.
            rec["error"] = "exact_latch_in_midgame_band"
            rec["ok"] = False
            return rec

        base = agent.det_seed_base(0)
        det_rng = random.Random(base + 1)
        evaluator = agent._evaluator
        c_puct = agent._c_puct

        world_snaps = []
        root_player = None
        n_legal = None
        for i in range(_KDETS):
            b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            m = NeuralMCTS(game=game, evaluator=evaluator, simulations=max_L,
                           c_puct=c_puct, seed=base + 100 + i)
            snaps, rp, priors, _lv = GBF.snapshot_world_search(m, b, _LEVELS)
            if root_player is None:
                root_player, n_legal = rp, len(priors)
            elif rp != root_player:
                raise AssertionError("root player differs across determinizations")
            world_snaps.append(snaps)
            m.clear()
        assert root_player == mover, "root_player != state.current_player"
        rec["n_legal"] = int(n_legal)

        # --- V_leaf + the pre-registered features (leaf is deck-blind, so it is
        #     identical on the true board and on every determinization) ---------- #
        feats, aux = LF.root_features(st, mover, _CFG.leaf_cfg, root_id,
                                      int(n_legal), int(r["corpus_champ125"]))
        rec["features"] = feats
        rec["aux"] = aux
        rec["v_leaf"] = aux["v_leaf"]

        # --- pooled root value per level --------------------------------------- #
        vdeep, extras = {}, {}
        for L in _LEVELS:
            agg_n, agg_w = defaultdict(float), defaultdict(float)
            for snaps in world_snaps:
                for a, (n, w) in snaps[L].items():
                    agg_n[a] += n
                    agg_w[a] += w
            sumN = sum(agg_n.values())
            sumW = sum(agg_w.values())
            vdeep[str(L)] = (sumW / sumN) if sumN else None
            qs = sorted((agg_w[a] / agg_n[a] for a in agg_n if agg_n[a] > 0), reverse=True)
            extras[str(L)] = {
                "sum_N": sumN,
                "n_children": len(agg_n),
                "max_child_q": (qs[0] if qs else None),
                "top2_q_gap": ((qs[0] - qs[1]) if len(qs) >= 2 else None),
            }
        rec["v_deep"] = vdeep
        rec["resid"] = {k: (v - aux["v_leaf"]) if v is not None else None
                        for k, v in vdeep.items()}
        rec["level_extras"] = extras
        rec["ok"] = True
    except TimeoutError:
        rec["error"] = "wall_hit"
        rec["ok"] = False
    except Exception as e:  # noqa - fail loud per root, never kill the pool
        import traceback
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-1500:]
        rec["ok"] = False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    rec["elapsed_secs"] = round(time.time() - t0, 3)
    return rec


def _init_worker(cfg, levels, k_dets, wall):
    global _CFG, _LEVELS, _KDETS, _WALL
    _CFG, _LEVELS, _KDETS, _WALL = cfg, tuple(levels), int(k_dets), int(wall)


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Leaf residual-mining labeler")
    ap.add_argument("--corpora", default="windowaudit,champ125",
                    help="comma list of registered corpus tags (see CORPORA)")
    ap.add_argument("--per-game", type=int, default=2)
    ap.add_argument("--tiles-lo", type=int, default=20)
    ap.add_argument("--tiles-hi", type=int, default=55)
    ap.add_argument("--levels", default="200,344,688,1376")
    ap.add_argument("--k-dets", type=int, default=4)
    ap.add_argument("--n", type=int, default=0, help="cap total roots (0 = all)")
    ap.add_argument("--shard", default="0/1", help="i/N — take every Nth root")
    ap.add_argument("--roots-file", default=None,
                    help="FREE-PASS mode: label an explicit roots jsonl in the gate_b schema "
                         "({deck_seed, actions, ply, ...}) instead of sampling a corpus. These "
                         "sets are ENDGAME-BOUNDED (k_remaining=3) — hypothesis generation "
                         "ONLY, never a verdict (PREREG.md §8).")
    ap.add_argument("--roots-tag", default="freepass")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--wall-cap-secs", type=int, default=900)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "records.jsonl"))
    args = ap.parse_args(argv)

    CORPORA = {
        "windowaudit": (REPO / "measurement/window_audit/gen_games.jsonl", 0),
        "champ125": (REPO / "measurement/utility_calibration_20260721/gen_games_champ125.jsonl", 1),
        "champion": (REPO / "measurement/champ_action_logs/champ_games.jsonl", 0),
    }
    levels = tuple(int(x) for x in args.levels.split(","))
    assert list(levels) == sorted(levels), "--levels must be ascending"

    roots = []
    corpus_meta = {}
    if args.roots_file:
        for line in Path(args.roots_file).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "ply" not in d or not d.get("actions"):
                continue
            roots.append({"corpus": args.roots_tag, "corpus_champ125": 1,
                          "game_id": int(d.get("game_id", d["deck_seed"])),
                          "deck_seed": int(d["deck_seed"]), "ply": int(d["ply"]),
                          "actions": d["actions"]})
        corpus_meta[args.roots_tag] = {
            "path": args.roots_file, "n_roots": len(roots), "corpus_champ125": 1,
            "scope": "FREE PASS — ENDGAME-BOUNDED (k_remaining=3). Hypothesis generation "
                     "ONLY; can never pass or fail the PREREG §5 gate."}
    else:
        for tag in args.corpora.split(","):
            tag = tag.strip()
            path, ind = CORPORA[tag]
            games = RR.load_games(str(path))
            rs = sample_roots(games, args.per_game, args.tiles_lo, args.tiles_hi, tag, ind)
            corpus_meta[tag] = {"path": str(path), "n_games": len(games), "n_roots": len(rs),
                                "corpus_champ125": ind}
            roots.extend(rs)
    roots.sort(key=lambda r: (r["corpus"], r["deck_seed"], r["ply"]))
    if args.n > 0:
        roots = roots[: args.n]
    si, sn = (int(x) for x in args.shard.split("/"))
    if sn > 1:
        roots = [r for i, r in enumerate(roots) if i % sn == si]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    done.add(json.loads(line)["root_id"])
                except Exception:
                    pass
    todo = [r for r in roots
            if f"{r['corpus']}_s{r['deck_seed']}_p{r['ply']}" not in done]

    cfg = CF.production_prior_cfg()
    champ_manifest = CF.resolved_manifest("fair", verify=True)

    try:
        rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        rev = "unknown"
    manifest = {
        "harness": "leaf_residual_mining",
        "schema": "carcassonne-leaf-residual/v1",
        "prereg": "measurement/leaf_residual_mining_20260721/PREREG.md",
        "goal": "error-guided leaf-term discovery: regress (deep pooled-Q minus shallow "
                "leaf value) on a pre-registered dictionary of cheap board features",
        "residual_definition":
            "resid(L) = V_deep(L) - V_leaf ; V_leaf = tanh(flat_virtual_score_v2_float("
            "root, mover, champion_leaf)/15) ; V_deep(L) = sum_a W_pooled(a)/sum_a N_pooled(a) "
            "over the k_dets pooled root children at per-world budget L. Mover POV. "
            "Positive = search likes the position MORE than the leaf does.",
        "primary_level": PRIMARY_LEVEL,
        "levels": list(levels),
        "level_semantics": f"per-world PUCT sim budgets; total = k_dets x level. "
                           f"k{args.k_dets}x{max(levels)} = the deployed champion budget "
                           f"(CL-054). ONE deep search per world, snapshotted at every "
                           f"level (bit-exact WITHIN a world), pooled at each level.",
        "agent": "FairHeuristicPriorAgent via champion_factory.build_fair_champion "
                 "(PRODUCTION.yaml knobs, curve125 v2.9 Bmild_cap8 leaf)",
        "k_dets": int(args.k_dets),
        "root_sampling": {
            "phase": "TILES only (even action indices)",
            "tiles_remaining_band": [args.tiles_lo, args.tiles_hi],
            "per_game": args.per_game,
            "rule": "uniform without replacement over eligible plies, "
                    "random.Random(deck_seed*7919+11)",
        },
        "corpora": corpus_meta,
        "n_roots_selected": len(roots),
        "n_todo": len(todo),
        "n_resumed": len(roots) - len(todo),
        "shard": args.shard,
        "workers": args.workers,
        "wall_cap_secs": args.wall_cap_secs,
        "feature_dictionary": {
            "controls": list(LF.CONTROLS),
            "candidates": [{"name": n, "tier": t, "hypothesis": h} for n, t, h in LF.CANDIDATES],
            "neg_control": LF.NEG_CONTROL,
            "pos_ref": LF.POS_REF,
            "n_candidates_in_family": len(LF.CANDIDATES),
        },
        "code_rev": rev,
        "host": os.uname().nodename,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "champion_manifest": champ_manifest,
    }
    mpath = out_path.with_name(f"manifest_{out_path.stem}.json")
    mpath.write_text(json.dumps(manifest, indent=2))
    print(f"[mine] roots={len(roots)} todo={len(todo)} resumed={len(roots)-len(todo)} "
          f"levels={levels} k_dets={args.k_dets} W={args.workers} -> {out_path}",
          flush=True)

    if not todo:
        return 0
    t0 = time.time()
    n_ok = n_bad = 0
    ctx = get_context("fork")
    with open(out_path, "a") as fh:
        with ctx.Pool(args.workers, initializer=_init_worker,
                      initargs=(cfg, levels, args.k_dets, args.wall_cap_secs)) as pool:
            for i, rec in enumerate(pool.imap_unordered(_process_root, todo, chunksize=1)):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                n_ok += bool(rec.get("ok"))
                n_bad += (not rec.get("ok"))
                if (i + 1) % 50 == 0 or i == 0:
                    el = time.time() - t0
                    rate = (i + 1) / el
                    print(f"  {i+1}/{len(todo)}  ok={n_ok} bad={n_bad}  "
                          f"{el:.0f}s  {rate:.2f} roots/s  "
                          f"eta {(len(todo)-i-1)/max(rate,1e-9)/60:.0f}min", flush=True)
    print(f"[mine] done ok={n_ok} bad={n_bad} in {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
