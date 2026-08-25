#!/usr/bin/env python3
"""OFFLINE meeple-phase tie census (owner-funded, "cheap meeple offline census").

Answers docs/LEVER_INDEX.md's "meeple-phase tie arbitration" entry-fee question:
at meeple-phase decisions, how often does the champion's own pooled_q_argmax hit
(a) an exact Q-tie among top options and (b) a Q+N double-tie (falls to the
lowest-action-index fallback) -- and for double-ties, does the v2.9 leaf value
the tied options differently (leaf-distinguishable) or are they genuinely
equivalent?

METHOD: replays banked E4 archives (measurement/e4_games/, read-only) and
re-runs the CHAMPION'S OWN production search at every ply of the game, exactly
as scripts/analyzer/ev_loss.py::grade_pass does (same champion_factory /
mirror_protocol / fair_agent calls, same env preamble => same leaf hash
a36d2e15a3b3d71d). This is a NEW script (main tree is read-only / latch armed)
but it deliberately mirrors grade_pass's tested logic rather than inventing a
new path, and imports `ev_loss` itself so env_preamble runs first.

At every MEEPLE-phase, non-forced, non-exact ("pimc") ply we additionally:
  - reconstruct the FULL pooled (Q=W/N, N) table (grade_pass only keeps summary
    fields, not the full per-action dict, so this part is new code)
  - replicate fair_agent.pooled_q_argmax's own eligibility + tie-break exactly
    (min_visits filter with all-pool fallback; strict (Q, N, -action) order)
  - detect an exact Q-tie among the eligible set (Python `==` on the same f64
    values the Rust core compares -- both are IEEE754 doubles, no ULP fuzzing)
  - detect a DOUBLE-tie: Q-tied AND N-tied among the Q-tied subset (this is the
    exact subset that falls through to the lowest-action-index fallback)
  - for double-ties (and, for context, all Q-ties), evaluate the production
    v2.9 leaf (`flat_leaf.flat_virtual_score_v2_float`, same env as
    LEAF_HASH_OF_RECORD) directly on each tied option's CHILD board state, from
    the root actor's POV -- this is a single static leaf call per option, cheap,
    and answers "does the champion's own evaluator see these as different
    positions" independent of what the *search* (which just tied) found.

No games are played. No production config, PRODUCTION.yaml, or repo file is
touched. Output is one JSONL row per meeple/pimc ply, written under
--out-dir (scratchpad only).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path("/home/doctor/projects/carcassone")
for sub in ("scripts/analyzer", "scripts/human_anchor", "scripts/level2",
            "scripts/measurement_infra"):
    sys.path.insert(0, str(REPO / sub))

import ev_loss  # noqa: E402  -- MUST be first carcassonne_ai-touching import (env_preamble)

fbits = ev_loss.fbits


def census_one_archive(path, *, seed, sims, k_dets, rust_threads, limit=0,
                       progress=True):
    """Mirrors ev_loss.grade_pass's loop (production champion re-search at
    EVERY ply, same reseat/advance/move_idx discipline) but returns one record
    per MEEPLE/pimc ply with the full pooled table + tie diagnostics + leaf
    values for any tied option, instead of grade_pass's delta_q summary."""
    import random

    import numpy as np
    from carcassonne_ai import fair_agent, flat_leaf, rules_profile
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, reseat, resolve_execution

    arch = ev_loss.load_archive(path)
    profile_name = ev_loss.resolve_profile_name(arch["provenance"])
    ev_loss.prepare_env(profile_name)
    prof = rules_profile.activate(profile_name)
    ex = resolve_execution("inherit", profile="desktop", rust_threads=rust_threads)

    actions = arch["actions"][: limit or None]
    deck_seed = arch["deck_seed"]

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    agent = make_production_champion("fair", game=game, seed=int(seed), sims=sims,
                                     k_dets=k_dets, verify=True, **ex.factory_kwargs())
    reseat(agent, deck_seed=deck_seed, actions=(), move_idx=0)

    min_visits = float(fair_agent.DEFAULT_MIN_POOLED_VISITS)

    rows = []
    n_meeple_total = 0
    n_meeple_pimc = 0
    t0 = time.time()
    for ply, played in enumerate(actions):
        st = board.state
        phase = st.phase.value
        legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        if phase == "meeples":
            n_meeple_total += 1

        agent._move_idx = ply
        chosen = int(agent.choose_action(board))
        lm = agent.last_move()
        forced = bool(lm["forced"]) or len(legal) == 1
        exact = bool(lm["exact"])

        if phase == "meeples" and not forced and not exact:
            n_meeple_pimc += 1
            pool = {int(a): (fbits(n), fbits(w)) for a, n, w in lm["pooled"]}
            agg_n = {a: n for a, (n, _) in pool.items()}
            agg_w = {a: w for a, (_, w) in pool.items()}
            q = {a: agg_w[a] / agg_n[a] for a in agg_n}

            # Exact replica of fair_agent.pooled_q_argmax's eligibility rule.
            eligible = [a for a in agg_n if agg_n[a] >= min_visits]
            if not eligible:
                eligible = list(agg_n)
            best = fair_agent.pooled_q_argmax(agg_n, agg_w, min_visits=min_visits)

            top_q = max(q[a] for a in eligible)
            tied_q = sorted(a for a in eligible if q[a] == top_q)
            q_tie = len(tied_q) > 1
            n_tied = []
            double_tie = False
            fallback_pick = None
            if q_tie:
                max_n = max(agg_n[a] for a in tied_q)
                n_tied = sorted(a for a in tied_q if agg_n[a] == max_n)
                double_tie = len(n_tied) > 1
                if double_tie:
                    fallback_pick = min(n_tied)  # matches (Q,N,-action) strict order

            actor = int(st.current_player)
            rec = {
                "archive": Path(path).name,
                "deck_seed": int(deck_seed),
                "ply": ply,
                "k_remaining": len(st.deck),
                "n_legal": len(legal),
                "n_pooled": len(pool),
                "n_eligible": len(eligible),
                "min_pooled_visits": min_visits,
                "action_played": int(played),
                "actor": actor,
                "q_tie": q_tie,
                "tie_width": len(tied_q),
                "double_tie": double_tie,
                "double_tie_width": len(n_tied),
                "tied_q_actions": tied_q,
                "double_tied_actions": n_tied,
                "fallback_pick": fallback_pick,
                "search_argmax": int(best),
                "top_q": float(top_q),
                "played_is_tied": int(played) in tied_q,
            }

            if q_tie:
                # Static v2.9 leaf value of every Q-tied child, root-actor POV --
                # cheap (one flat_virtual_score_v2_float call per option), and
                # completely independent of what the search's pooled Q found.
                leaf_vals = {}
                for a in tied_q:
                    nb, _ = game.get_next_state(board, int(a))
                    leaf_vals[a] = float(
                        flat_leaf.flat_virtual_score_v2_float(nb.state, actor, None))
                rec["leaf_values_tied_q"] = leaf_vals
                spread_q = max(leaf_vals.values()) - min(leaf_vals.values())
                rec["leaf_spread_tied_q"] = spread_q
                rec["leaf_distinguishable_tied_q"] = spread_q > 1e-9
                if double_tie:
                    dvals = {a: leaf_vals[a] for a in n_tied}
                    spread_d = max(dvals.values()) - min(dvals.values())
                    rec["leaf_values_double_tie"] = dvals
                    rec["leaf_spread_double_tie"] = spread_d
                    rec["leaf_distinguishable_double_tie"] = spread_d > 1e-9

            rows.append(rec)

        out_board, _ = game.get_next_state(board, int(played))
        board = out_board
        advance(agent, int(played))
        if progress and (ply + 1) % 48 == 0:
            print(f"  [{Path(path).name}] ply {ply+1}/{len(actions)} "
                  f"{time.time()-t0:.0f}s", flush=True)

    meta = {
        "archive": Path(path).name,
        "profile_name": profile_name,
        "deck_seed": int(deck_seed),
        "n_plies": len(actions),
        "n_meeple_total": n_meeple_total,
        "n_meeple_pimc": n_meeple_pimc,
        "final_scores": list(board.state.scores),
        "agent_manifest_leaf_hash": agent.manifest.get("leaf_hash")
                                    if hasattr(agent, "manifest") else None,
        "wall_secs": round(time.time() - t0, 2),
    }
    return rows, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archives", nargs="+", help="E4 archive json paths")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--rust-threads", type=int, default=8,
                    help="matches PRODUCTION.yaml desktop profile (8)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_f = (out_dir / "rows.jsonl").open("w")
    meta_f = (out_dir / "meta.jsonl").open("w")

    t0 = time.time()
    for i, path in enumerate(args.archives):
        arch_raw = json.loads(Path(path).read_text())
        sims = int(arch_raw["sims_effective"])
        k_dets = int(arch_raw["k_dets_effective"])
        print(f"[{i+1}/{len(args.archives)}] {Path(path).name} "
              f"sims={sims} k_dets={k_dets} elapsed={time.time()-t0:.0f}s", flush=True)
        rows, meta = census_one_archive(
            path, seed=args.seed, sims=sims, k_dets=k_dets,
            rust_threads=args.rust_threads, limit=args.limit)
        for r in rows:
            rows_f.write(json.dumps(r) + "\n")
        meta_f.write(json.dumps(meta) + "\n")
        rows_f.flush()
        meta_f.flush()
        print(f"    -> meeple_total={meta['n_meeple_total']} "
              f"meeple_pimc={meta['n_meeple_pimc']} "
              f"q_ties={sum(1 for r in rows if r['q_tie'])} "
              f"double_ties={sum(1 for r in rows if r['double_tie'])} "
              f"wall={meta['wall_secs']}s", flush=True)

    rows_f.close()
    meta_f.close()
    print(f"[census] DONE {len(args.archives)} archives in {time.time()-t0:.0f}s "
          f"-> {out_dir}", flush=True)


if __name__ == "__main__":
    main()
