#!/usr/bin/env python3
"""E1 win-objective 0-game pre-gate (measurement/e1_winobj_20260814/DESIGN.md §4).

Over the banked corpora — the champion self-play bank
(measurement/champ_action_logs/champ_games.jsonl, 449 games, `walled`) and the
E4 archives (measurement/e4_games/*.json, rules profile resolved FROM each
archive) — replay every game losslessly, simulate the deployed exact-K latch
(first TILES ply with k_remaining <= 2, one-way), and at EVERY champion
exact-K-solved ply solve the position under BOTH objectives (margin = the
incumbent; win = lexicographic (E[outcome], E[margin])). Report the divergence
rate of the picks (min(optimal_actions), the deployed selection rule), the
optimal-SET divergence rate, per-solve wall times (the cost bench), and — on
divergent plies, if any — the realized-outcome bookkeeping with its
selection-effect label.

Solver: the RUST production solver (carc_rs FairAgentRs mirror +
solve_marginalized(objective=...)), i.e. the deployed engine itself — the
E1-extended wheel must be importable (--wheel-dir prepends a directory built
from this worktree, keeping the shared venv untouched).

The read-rule (DESIGN §4) was committed before any number:
  divergence < 1%  -> branch K (dies free, cell NOT owed)
  1% .. 10%        -> branch F (fund the cell)
  > 10%            -> branch F+ (fund + flag: the §2 proposition failed)
The §2 proposition predicts EXACTLY 0; any nonzero rate must be root-caused
before a branch is read.

Usage:
  e1_pregate.py [--wheel-dir DIR] [--workers 8] [--limit-games N]
                [--limit-e4 N] [--budget 2000000] [--integrity-only]
                [--out-dir DIR]

0 games played. Local CPU only.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "engine"))

CHAMPGAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
E4_DIR = REPO / "measurement" / "e4_games"
OUT_DIR_DEFAULT = REPO / "measurement" / "e1_winobj_20260814"

SCHEMA = "carcassonne-e1-winobj-pregate/v1"
EXACT_MAX_K = 2                      # the deployed latch (PRODUCTION.yaml fair_deploy)
DEFAULT_BUDGET = 2_000_000           # fair_agent.DEFAULT_EXACT_BUDGET

# pre-registered read-rule bars (DESIGN.md §4; do not tune after the fact)
KILL_BAR = 0.01
FLAG_BAR = 0.10

_WHEEL_DIR = None                    # set in workers via initializer


def _init_worker(wheel_dir):
    global _WHEEL_DIR
    _WHEEL_DIR = wheel_dir
    if wheel_dir:
        sys.path.insert(0, wheel_dir)


def _resolve_profile_name(archive: dict) -> str:
    """E4 rules-profile resolution, ev_loss.py convention: an explicit
    `rules_profile` stamp wins; an archive with NO stamp is from a
    pre-fixed_v1 build => `walled`."""
    from carcassonne_ai import rules_profile

    stamped = archive.get("rules_profile")
    if stamped is not None:
        if stamped not in rules_profile.known():
            raise AssertionError(
                f"archive stamps rules_profile={stamped!r} not in the registry "
                f"({rules_profile.known()}) — failing closed")
        return str(stamped)
    return "walled"


def _grade_game(task):
    """Replay ONE archived game; solve both objectives at every champion
    exact-K-solved ply on the RUST mirror. Returns per-ply records."""
    import random

    import numpy as np

    corpus, rec, profile_name, budget = task

    from carcassonne_ai import fair_agent, rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import _draw_order_for_mirror, mirror_geometry_kwargs
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    import carc_rs
    assert (_WHEEL_DIR is None) or carc_rs.__file__.startswith(_WHEEL_DIR), \
        f"stale carc_rs resolved: {carc_rs.__file__} (wanted {_WHEEL_DIR})"

    prof = rules_profile.activate(profile_name)
    if rules_profile.r9_env_on() != prof.r9_env_expected:
        raise AssertionError(
            f"R9 env latched wrong for profile {profile_name} — run this corpus "
            "group in a fresh worker pool")

    deck_seed = int(rec["deck_seed"])
    actions = [int(a) for a in rec["actions"]]
    # champion seats: both for self-play; the non-human seat for E4
    if corpus == "selfplay":
        champ_seats = {0, 1}
        rec_final = [int(rec["score_p0"]), int(rec["score_p1"])]
    else:
        champ_seats = {1 - int(rec["human_player"])}
        rec_final = [int(x) for x in rec["scores"]]

    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True,
                **prof.game_kwargs())
    board = game.get_init_board()

    # Seat the rust mirror on this exact deck under this exact geometry.
    geo = mirror_geometry_kwargs(game)
    mirror_preplaces = geo.get("start_rule") == "retail"
    descs = _draw_order_for_mirror(board.state, mirror_preplaces)

    # A minimal FairAgentRs purely as (mirror + solver); its search config is
    # never exercised (we call solve_marginalized directly, latch ignored).
    from carcassonne_ai.champion_factory import production_prior_cfg
    from carcassonne_ai.rust_agent import search_config_rs
    rs = carc_rs.FairAgentRs(
        search_config_rs(production_prior_cfg(), 1), k_dets=1, seed=0,
        exact_endgame=True, exact_max_k=EXACT_MAX_K, exact_budget=int(budget),
        window_size=int(getattr(game, "window_size", 25)), **geo)
    rs.start_game_from_deck(descs)

    rows = []
    latched = False
    ply = 0
    for a in actions:
        st = board.state
        k = int(fair_agent.k_remaining(st))
        if (not latched and st.phase == GamePhase.TILES and k <= EXACT_MAX_K):
            latched = True
        if latched and int(st.current_player) in champ_seats:
            # this is an exact-K-solved ply for the deployed champion
            t0 = time.perf_counter()
            rm = rs.solve_marginalized(objective="margin")
            t_m = time.perf_counter() - t0
            t0 = time.perf_counter()
            rw = rs.solve_marginalized(objective="win")
            t_w = time.perf_counter() - t0
            if rm is None or rw is None:
                rows.append({"ply": ply, "k": k, "budget_exceeded": True})
            else:
                assert rw["win_value"] is not None and rm["win_value"] is None, \
                    "objective liveness discriminator broken"
                pick_m = int(min(rm["optimal_actions"]))
                pick_w = int(min(rw["optimal_actions"]))
                rows.append({
                    "ply": ply, "k": k, "phase": str(st.phase),
                    "mover": int(st.current_player),
                    "pick_margin": pick_m, "pick_win": pick_w,
                    "diverged": pick_m != pick_w,
                    "sets_differ": (sorted(rm["optimal_actions"])
                                    != sorted(rw["optimal_actions"])),
                    "archived_action": int(a),
                    "archived_matches_margin": int(a) == pick_m,
                    "t_margin": t_m, "t_win": t_w,
                    "nodes_margin": int(rm["nodes"]), "nodes_win": int(rw["nodes"]),
                    "budget_exceeded": False,
                })
        board, _ = game.get_next_state(board, int(a))
        rs.advance(int(a))
        ply += 1

    final = [int(x) for x in board.state.scores]
    if final != rec_final:
        raise AssertionError(
            f"replay final scores {final} != recorded {rec_final} for "
            f"{corpus} deck_seed={deck_seed} — lossless-replay contract broken, STOP")
    outcome_p0 = 1.0 if final[0] > final[1] else (0.5 if final[0] == final[1] else 0.0)
    return {"corpus": corpus, "deck_seed": deck_seed, "profile": profile_name,
            "rows": rows, "outcome_p0": outcome_p0,
            "replay_scores_match": True}


def load_selfplay(limit=None):
    out = []
    with open(CHAMPGAMES) as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    out.sort(key=lambda r: int(r["deck_seed"]))
    return out[:limit] if limit else out


def load_e4(limit=None):
    recs = []
    for p in sorted(E4_DIR.glob("*.json")):
        with open(p) as fh:
            d = json.load(fh)
        if not d.get("ok"):
            continue
        d["_file"] = p.name
        recs.append(d)
    return recs[:limit] if limit else recs


def _git_head():
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel-dir", default=None,
                    help="directory holding the E1-extended carc_rs package "
                         "(prepended to sys.path in every worker)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-games", type=int, default=None)
    ap.add_argument("--limit-e4", type=int, default=None)
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--integrity-only", action="store_true")
    ap.add_argument("--out-dir", default=str(OUT_DIR_DEFAULT))
    args = ap.parse_args(argv)

    t_start = time.time()
    selfplay = load_selfplay(args.limit_games)
    e4 = load_e4(args.limit_e4)

    # group E4 by resolved profile; each profile group gets its OWN pool so the
    # R9 env latch can never straddle profiles inside one process
    sys.path.insert(0, str(REPO / "src"))
    from carcassonne_ai import rules_profile  # noqa: F401  (import check only)
    e4_by_prof = {}
    for rec in e4:
        e4_by_prof.setdefault(_resolve_profile_name(rec), []).append(rec)

    results = []
    task_groups = [[("selfplay", r, "walled", args.budget) for r in selfplay]]
    for prof, recs in sorted(e4_by_prof.items()):
        task_groups.append([("e4", r, prof, recs and prof and args.budget or args.budget)
                            for r in recs])
        # (keep it simple: budget is the same for every group)
        task_groups[-1] = [("e4", r, prof, args.budget) for r in recs]

    for tasks in task_groups:
        if not tasks:
            continue
        with mp.Pool(args.workers, initializer=_init_worker,
                     initargs=(args.wheel_dir,)) as pool:
            for out in pool.imap_unordered(_grade_game, tasks, chunksize=1):
                results.append(out)
                if len(results) % 50 == 0:
                    print(f"  {len(results)} games graded", flush=True)

    # ---- aggregate ---------------------------------------------------------
    all_rows = [r for g in results for r in g["rows"]]
    solved = [r for r in all_rows if not r.get("budget_exceeded")]
    n_to = sum(1 for r in all_rows if r.get("budget_exceeded"))
    diverged = [r for r in solved if r["diverged"]]
    sets_differ = sum(1 for r in solved if r["sets_differ"])
    n = len(solved)

    integrity = {
        "schema": SCHEMA, "git_head": _git_head(),
        "selfplay_games": len(selfplay),
        "selfplay_replayed_ok": sum(1 for g in results
                                    if g["corpus"] == "selfplay"),
        "e4_games": len(e4),
        "e4_replayed_ok": sum(1 for g in results if g["corpus"] == "e4"),
        "e4_by_profile": {k: len(v) for k, v in e4_by_prof.items()},
        "solved_plies": n, "budget_exceeded_plies": n_to,
        "exact_max_k": EXACT_MAX_K, "budget": args.budget,
        "wall_secs": round(time.time() - t_start, 1),
    }
    print(json.dumps(integrity, indent=1))
    if args.integrity_only:
        return 0

    # 95% upper bound on a binomial 0/n (rule of three) or Wilson otherwise
    import math
    if n:
        if not diverged:
            ci95_up = 3.0 / n
        else:
            p = len(diverged) / n
            z = 1.959963984540054
            den = 1 + z * z / n
            ci95_up = (p + z * z / (2 * n)
                       + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / den
    else:
        ci95_up = float("nan")

    div_rate = (len(diverged) / n) if n else float("nan")
    branch = ("K" if div_rate < KILL_BAR
              else ("F" if div_rate <= FLAG_BAR else "F+"))

    tm = [r["t_margin"] for r in solved]
    tw = [r["t_win"] for r in solved]
    ratios = [w / m for m, w in zip(tm, tw) if m > 0]
    cost = {
        "t_margin_total_s": round(sum(tm), 3), "t_win_total_s": round(sum(tw), 3),
        "ratio_total": round(sum(tw) / sum(tm), 4) if sum(tm) else None,
        "ratio_median": round(statistics.median(ratios), 4) if ratios else None,
        "ratio_p90": (round(sorted(ratios)[int(0.9 * len(ratios))], 4)
                      if ratios else None),
        "t_margin_median_ms": round(1e3 * statistics.median(tm), 3) if tm else None,
        "t_win_median_ms": round(1e3 * statistics.median(tw), 3) if tw else None,
        "t_margin_p90_ms": (round(1e3 * sorted(tm)[int(0.9 * len(tm))], 3)
                            if tm else None),
        "t_win_p90_ms": (round(1e3 * sorted(tw)[int(0.9 * len(tw))], 3)
                         if tw else None),
    }

    # realized-outcome bookkeeping on divergent plies (descriptive only —
    # archived continuations followed the MARGIN policy; selection effect)
    div_detail = []
    by_game = {(g["corpus"], g["deck_seed"]): g for g in results}
    for r in diverged:
        for g in results:
            if r in g["rows"]:
                div_detail.append({**{k: r[k] for k in
                                      ("ply", "k", "pick_margin", "pick_win")},
                                   "corpus": g["corpus"],
                                   "deck_seed": g["deck_seed"],
                                   "outcome_p0": g["outcome_p0"]})
                break

    archived_match = [r["archived_matches_margin"] for r in solved
                      if r.get("mover") is not None]
    verdict = {
        **integrity,
        "divergence_rate": div_rate, "n_diverged": len(diverged),
        "divergence_ci95_upper": ci95_up,
        "set_divergence_rate": (sets_differ / n) if n else float("nan"),
        "archived_matches_margin_rate": (sum(archived_match) / len(archived_match)
                                         if archived_match else None),
        "cost": cost,
        "read_rule": {"kill_bar": KILL_BAR, "flag_bar": FLAG_BAR,
                      "branch_fired": branch},
        "divergent_plies": div_detail,
        "selection_effect_label": (
            "realized outcomes on divergent plies condition on the archived "
            "(margin-policy) continuation; descriptive only, not causal"),
    }
    out_dir = Path(args.out_dir)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    with open(out_dir / "VERDICT.json", "w") as fh:
        json.dump(verdict, fh, indent=1)
    with open(out_dir / "raw" / "per_ply_rows.json", "w") as fh:
        json.dump([{**r} for g in results for r in
                   [dict(r, corpus=g["corpus"], deck_seed=g["deck_seed"])
                    for r in g["rows"]]], fh)
    print(json.dumps({k: v for k, v in verdict.items()
                      if k not in ("divergent_plies",)}, indent=1))
    print(f"BRANCH {branch} fired -> {out_dir / 'VERDICT.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
