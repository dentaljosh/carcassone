#!/usr/bin/env python3
"""CENSUS 1 (GT-M1 world-spread) + CENSUS 3 (SA-M1 contested-seed reachability).

ONE pass over the 290-ply crux corpus produces both censuses' raw inputs:

  * per-world root statistics for the champion's k=8 PIMC determinization worlds
    at deploy budget (1376 sims/world, 11008 total)  -> Census 1
  * the pooled root visit distribution from those same worlds                -> Census 3
  * a contested-seed tag over every legal action at the root                 -> Census 3

Definitions and kill bars are FROZEN in PREREG.md, committed before this file ran.

FIDELITY: this does not mirror the deployed search, it CALLS it --
`fair_agent.search_one_world` per world, pooled through `fair_agent._merge_root_stats`
and decided by `fair_agent.pooled_q_argmax`, exactly the seam
`scripts/measurement_infra/kwidth_agreement_probe.py` uses. The world lineage is the
deployed one: ONE `random.Random(det_seed_base(0)+1)` stream, k sequential
`reshuffled_determinization` calls, world i searched at `det_seed_base + 100 + i`.

R9 is import-latched, so ONE PROFILE PER PROCESS: `--profile` is applied via
`e4_deck_baseline.export_profile_env` BEFORE any `carcassonne_ai` import.

Emits one JSONL row per (ply, salt) to --out.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

#: The repo this census reads from. Overridable so the script can be SHIPPED to a box
#: (share / stdin) without being written into that box's pinned checkout.
REPO = Path(os.environ.get("CARC_REPO") or Path(__file__).resolve().parents[2])
SCRIPTS = REPO / "scripts"
for _p in (str(REPO / "src"), str(REPO / "engine"), str(SCRIPTS),
           str(SCRIPTS / "measurement_infra"), str(SCRIPTS / "human_anchor"),
           str(SCRIPTS / "classical_search"),
           str(REPO / "measurement" / "e4_exploit_grading_20260825")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- canonical single-thread env (house pattern; a game-parallel farm owns the cores)
for _k, _v in {
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
    "CUDA_VISIBLE_DEVICES": "",
}.items():
    os.environ.setdefault(_k, _v)

SCHEMA = "carcassonne-cl083-census13/v1"
SIMS_PER_DET = 1376
K_DETS = 8
TOTAL_BUDGET = SIMS_PER_DET * K_DETS          # 11008, PRODUCTION.yaml fair_deploy
M_VISITS = 110                                 # PREREG census 3: 1% of TOTAL_BUDGET
ALPHAS = (0.25, 0.50, 0.75, 1.00)              # PREREG census 1 CVaR grid
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

_G: dict = {}


def root_seed(deck_seed: int, ply: int, salt: int) -> int:
    """The CL-070 / kwidth convention, unchanged."""
    return (int(deck_seed) * 1_000_003 + int(ply) * 8191
            + int(salt) * 2_654_435_761) & 0x7FFFFFFF


# --------------------------------------------------------------------------- #
# contested-seed tagging (PREREG census 3)                                     #
# --------------------------------------------------------------------------- #
def contest_view(state, SAC, flat_leaf):
    """The contest structure of one state.

    Returns ``(all_keys, bp_keys, rep_to_keys, key_to_rep)`` where a key is a
    positional feature-side key (`("C"|"R"|"F", row, col, side)`) and `bp_keys` are
    the keys sitting inside a BOTH-PLAYER component -- Stage-A's `contested`
    predicate: a connected city/road/farm component carrying >=1 meeple of EACH
    player.
    """
    from collections import defaultdict
    decomp = flat_leaf.decompose(state)
    _comps, _key_groups, key_to_rep = SAC.snapshot(state, decomp, flat_leaf)

    owners: dict = {}
    for p in range(state.players):
        for mp in state.placed_meeples[p]:
            fk = SAC.meeple_component_key(mp, state, decomp, flat_leaf)
            if fk is None:          # cloister meeple -- no component
                continue
            rep = key_to_rep.get(fk)
            if rep is None:
                continue
            owners.setdefault(rep, set()).add(p)

    bp_reps = {rep for rep, ps in owners.items() if len(ps) >= 2}
    bp_keys = {k for k, rep in key_to_rep.items() if rep in bp_reps}
    rep_to_keys = defaultdict(set)
    for k, rep in key_to_rep.items():
        rep_to_keys[rep].add(k)
    return set(key_to_rep), bp_keys, rep_to_keys, key_to_rep


def tag_contested_seeds(game, board, legal, SAC, flat_leaf):
    """Tag every legal action as onset / extend / neither -- PREREG census 3, verbatim.

    ONSET  = "a component that is a both-player component AFTER was not one BEFORE".
             Tested on the keys that EXIST IN THE PRE-STATE, so the brand-new keys the
             placed tile itself contributes cannot manufacture an onset. A pre-existing
             feature-side that was not contested and now is  =>  a genuine new contest
             (Stage-A's `merge` / `born_contested` / claim).
    EXTEND = "a increases the tile count of a component that was ALREADY a both-player
             component". Tested as: a key NEW in the post-state joins a component that
             also contains a key which was ALREADY contested pre-action.
    """
    pre_all, pre_bp, _pre_r2k, _pre_k2r = contest_view(board.state, SAC, flat_leaf)
    onset, extend = [], []
    for a in legal:
        nb, _ = game.get_next_state(board, int(a))
        post_all, post_bp, post_r2k, post_k2r = contest_view(nb.state, SAC, flat_leaf)

        # ONSET -- restricted to keys that already existed before the action.
        if (post_bp & pre_all) - pre_bp:
            onset.append(int(a))
            continue

        # EXTEND -- a newly created key joined an already-contested component.
        new_keys = post_all - pre_all
        hit = False
        for k in (new_keys & post_bp):
            if post_r2k[post_k2r[k]] & pre_bp:
                hit = True
                break
        if hit:
            extend.append(int(a))
    return onset, extend, len(pre_bp)


# --------------------------------------------------------------------------- #
# per-world search (PREREG shared inputs)                                      #
# --------------------------------------------------------------------------- #
def _init(cfg_kw: dict) -> None:
    from carcassonne_ai import champion_factory as CF
    _G.update(cfg_kw)
    _G["cfg"] = CF.production_prior_cfg()      # tiearb OFF: the unmodified champion


def _process(item: dict) -> dict:
    import random
    import time

    import root_replay as RR
    from carcassonne_ai import champion_factory as CF, flat_leaf
    from carcassonne_ai import rules_profile
    from carcassonne_ai.fair_agent import (
        FairHeuristicMCTSAgent, _merge_root_stats, k_remaining as fair_k_remaining,
        pooled_q_argmax, search_one_world,
    )
    import stage_a_census as SAC

    rec = {k: item[k] for k in ("game", "ply", "salt", "stratum", "profile",
                               "actor", "phase", "played_action", "deck_seed")}
    rec.update(schema=SCHEMA, sims_per_det=SIMS_PER_DET, k_dets=K_DETS,
               total_budget=TOTAL_BUDGET, ok=False)
    t0 = time.time()
    try:
        prof = rules_profile.resolve(item["profile"])
        game, board = RR.replay_actions(item["deck_seed"], item["actions"], item["ply"],
                                        game_kwargs=prof.game_kwargs())
        import numpy as np
        legal = [int(a) for a in np.flatnonzero(game.get_valid_moves(board))]
        rec["n_legal"] = len(legal)
        if len(legal) < 2:
            rec["error"] = "forced_move"
            return rec

        rseed = root_seed(item["deck_seed"], item["ply"], item["salt"])
        rec["agent_seed"] = rseed
        agent = CF.build_fair_champion(game, sims=SIMS_PER_DET, k_dets=K_DETS,
                                       seed=rseed, cfg=_G["cfg"])
        for attr in ("_meeple_dedup", "_intra_reuse", "_parallel_workers"):
            if getattr(agent, attr, None):
                raise AssertionError(f"agent has {attr} enabled -- refusing to run")
        k_rem = fair_k_remaining(board.state)
        rec["k_remaining"] = int(k_rem)
        rec["exact_region"] = bool(agent._exact_endgame and k_rem <= agent._exact_max_k)

        # ---- CENSUS 3: tag the legal actions ------------------------------- #
        onset, extend, n_pre_bp_keys = tag_contested_seeds(
            game, board, legal, SAC, flat_leaf)
        rec["seeds_onset"] = onset
        rec["seeds_extend"] = extend
        rec["n_pre_bothplayer_keys"] = n_pre_bp_keys

        # ---- the deployed world lineage ------------------------------------ #
        base = agent.det_seed_base(0)
        rec["det_seed_base"] = int(base)
        det_rng = random.Random(base + 1)
        root_key = game.string_representation(board)

        world_stats = []
        for i in range(K_DETS):
            b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            m, stats, _t = search_one_world(
                game, agent._evaluator, b, root_key,
                sims=SIMS_PER_DET, c_puct=agent._c_puct, seed=base + 100 + i)
            world_stats.append([(int(a), float(n), float(w)) for a, n, w in stats])
            m.clear()

        # ---- pooled (the deployed decision) -------------------------------- #
        agg_n: dict = {}
        agg_w: dict = {}
        from collections import defaultdict
        agg_n, agg_w = defaultdict(float), defaultdict(float)
        for stats in world_stats:
            _merge_root_stats(stats, agg_n, agg_w)
        rec["pooled_argmax"] = int(pooled_q_argmax(agg_n, agg_w,
                                                   agent._min_pooled_visits))
        rec["min_pooled_visits"] = int(agent._min_pooled_visits)
        rec["pooled_n"] = {str(a): float(n) for a, n in agg_n.items()}
        rec["pooled_w"] = {str(a): float(w) for a, w in agg_w.items()}
        rec["world_stats"] = world_stats
        rec["ok"] = True
    except Exception as exc:                              # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rec["elapsed_s"] = round(time.time() - t0, 3)
    return rec


def load_items(profile: str, salts) -> list:
    targets = REPO / "measurement" / "e4_ply_pricing_20260827" / "targets.jsonl"
    games_dir = REPO / "measurement" / "e4_games"
    arch_cache: dict = {}
    out = []
    for line in targets.read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        if t["profile"] != profile:
            continue
        stem = t["game"]
        if stem not in arch_cache:
            arch_cache[stem] = json.loads((games_dir / stem).read_text())
        arch = arch_cache[stem]
        for salt in salts:
            out.append({
                "game": stem, "ply": int(t["ply"]), "salt": int(salt),
                "stratum": t["stratum"], "profile": t["profile"],
                "actor": int(t["actor"]), "phase": t["phase"],
                "played_action": int(t["played_action"]),
                "deck_seed": int(arch["deck_seed"]), "actions": arch["actions"],
            })
    out.sort(key=lambda r: (r["game"], r["ply"], r["salt"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--salts", default="0,1")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    # R9 + leaf env MUST be exported before any carcassonne_ai import.
    from e4_deck_baseline import export_profile_env
    r9 = export_profile_env(a.profile)
    import env_preamble                                       # noqa: F401  leaf env

    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai import rules_profile
    prof = rules_profile.resolve(a.profile)
    assert rules_profile.r9_env_on() == prof.r9_env_expected, "R9 latch mismatch"

    # PREREG instrument-fault trigger: the leaf must be the champion of record.
    from c5_leaf_override import _leaf_hash
    lh = _leaf_hash(CF.production_leaf_cfg(CF.load_production_spec()))
    assert lh == LEAF_HASH_OF_RECORD, f"leaf hash {lh} != {LEAF_HASH_OF_RECORD}"
    print(f"[census13] leaf_hash={lh} OK", flush=True)

    salts = [int(s) for s in a.salts.split(",")]
    items = load_items(a.profile, salts)
    if a.limit:
        items = items[:a.limit]
    print(f"[census13] profile={a.profile} r9={r9} items={len(items)} "
          f"W={a.workers}", flush=True)

    import multiprocessing as mp
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    with outp.open("w") as fh, mp.Pool(a.workers, initializer=_init, initargs=({},)) as pool:
        for i, rec in enumerate(pool.imap_unordered(_process, items, chunksize=1), 1):
            rec.pop("actions", None)
            fh.write(json.dumps(rec) + "\n")
            n_ok += int(bool(rec.get("ok")))
            if i % 25 == 0:
                fh.flush()
                print(f"[census13] {i}/{len(items)} ok={n_ok}", flush=True)
    print(f"[census13] DONE {n_ok}/{len(items)} ok -> {outp}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
