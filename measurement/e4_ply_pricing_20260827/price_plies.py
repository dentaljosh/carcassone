#!/usr/bin/env python3
"""E4 PLY-PRICING — price the target plies. **NO SEARCH-FAMILY JUDGE ANYWHERE.**

What prices a move here:

  * `exact_marginalized`  — `carc_core::endgame` / `endgame_solver.solve(mode="marginalized")`.
    Expectiminimax over the real remaining bag. The value IS the true final-score
    differential (P0 - P1). No clairvoyance gap, no evaluation function, no search
    heuristic. This is GROUND TRUTH.
  * `exact_clairvoyant_M`  — the clairvoyant exact solver run over M resampled deck
    orders and averaged per root action. Still solver-exact per world, but it is a
    PIMC-style read and carries the CLAIRVOYANCE GAP (each world's optimal line
    knows the future), so it is an OPTIMISTIC bound on both sides, not a calibrated
    price. Labeled as such on every row it produces.
  * `realized`  — pure archive arithmetic: the realized score swing over the next
    `REALIZED_WINDOW_PLIES` plies and to the end of the game, plus the Stage A
    feature-attributed gross. DESCRIPTIVE, wide error bars, never an EV.

The champion COUNTERFACTUAL is the production champion's own move at the same
state (governance/PRODUCTION.yaml `champion.fair_deploy`: k_dets 8 x sims_per_det
1376, leaf a36d2e15a3b3d71d, exact-K<=2, backend rust). The champion is used ONLY
to NAME a move; it never scores one. Determinism is pinned by `seed=0` and
`move_idx=<archive ply>` (see PREREG.md).

Per-solve isolation reuses `reconcile_exact_solver`'s pattern: every solve runs in
its own forked child under RLIMIT_AS + RLIMIT_CPU. A job over either cap is
recorded as a SKIP row (never a price, never a mismatch), so a pathological
position cannot take the run down or be silently dropped.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import resource
import signal
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

ARCHIVES = REPO / "measurement" / "e4_games"

# --- pre-registered constants (frozen; see PREREG.md) ----------------------- #
REALIZED_WINDOW_PLIES = 20
COUNTERFACTUAL_SEED = 0
CLAIR_WORLD_SEED = 20260827
CPU_HARD_GRACE_S = 30
WALL_GRACE_S = 120


def fbits(bits: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", int(bits)))[0]


# --------------------------------------------------------------------------- #
# isolated solve (RLIMIT_AS + RLIMIT_CPU), reconcile_exact_solver's pattern      #
# --------------------------------------------------------------------------- #
def _solve_child(payload, mem_bytes, cpu_cap_s, conn):
    try:
        if mem_bytes > 0:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        if cpu_cap_s > 0:
            # SIGXCPU left at its DEFAULT disposition on purpose: a Python-level
            # handler only runs at a bytecode boundary and would be ignored for
            # the whole duration of a long RUST solve.
            resource.setrlimit(resource.RLIMIT_CPU,
                               (cpu_cap_s, cpu_cap_s + CPU_HARD_GRACE_S))
        conn.send(("OK", _do_solve(payload)))
    except MemoryError:
        conn.send(("OOM", None))
    except BaseException as e:                        # noqa: BLE001
        conn.send(("EXC", f"{type(e).__name__}: {e}"))
    finally:
        conn.close()


def _seat_mirror(profile_name, deck_seed, actions, ply):
    import carc_rs
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import mirror_geometry_kwargs

    prof = rules_profile.resolve(profile_name)
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    ms = carc_rs.MirrorState.from_seed(str(int(deck_seed)),
                                       **mirror_geometry_kwargs(game))
    for a in actions[:ply]:
        board, _ = game.get_next_state(board, int(a))
        ms.advance(int(a))
    if game.string_representation(board) != ms.string_repr():
        raise RuntimeError("replay_desync: rust mirror != python board")
    return game, board, ms


def _do_solve(p):
    """Run inside the isolated child. Returns a plain dict (picklable)."""
    t0 = time.time()
    _, _, ms = _seat_mirror(p["profile"], p["deck_seed"], p["actions"], p["ply"])
    seat_s = time.time() - t0

    if p["mode"] == "exact_marginalized":
        t0 = time.time()
        rs = ms.solve_endgame(mode="marginalized", budget=p["budget"],
                              alphabeta=False)
        if rs is None:
            return {"status": "BUDGET_EXCEEDED", "seat_s": seat_s}
        return {"status": "OK", "seat_s": seat_s,
                "solve_s": time.time() - t0,
                "nodes": int(rs["nodes"]),
                "value": fbits(int(rs["value_bits"])),
                "to_move": int(rs["to_move"]),
                "optimal_actions": [int(a) for a in rs["optimal_actions"]],
                "child_values": {int(a): fbits(int(v)) for a, v in rs["child_values"]}}

    if p["mode"] == "exact_clairvoyant_world":
        # ONE world, so the RLIMIT cap applies PER WORLD: a single pathological
        # deck order is skipped alone instead of voiding the whole ply's average.
        # World -1 is the archive's TRUE future deck order and is reported
        # SEPARATELY — it is one sample, not the price. The price is the mean over
        # `m_worlds` INDEPENDENTLY RESAMPLED orders of the same remaining bag, so
        # the estimator does not silently double-weight the realized world.
        base = list(ms.unseen_deck())
        w = int(p["world"])
        if w >= 0:
            # Seeded per (deck_seed, ply) and advanced w+1 times, so world w is the
            # same permutation regardless of which worlds ran before it.
            rng = random.Random(CLAIR_WORLD_SEED ^ (p["deck_seed"] * 1000003)
                                ^ (p["ply"] * 7919) ^ (w * 104729))
            rng.shuffle(base)
            ms.set_unseen_deck(base)
        t0 = time.time()
        rs = ms.solve_endgame(mode="clairvoyant", budget=p["budget"], alphabeta=True)
        if rs is None:
            return {"status": "BUDGET_EXCEEDED", "seat_s": seat_s, "world": w}
        return {"status": "OK", "seat_s": seat_s, "solve_s": time.time() - t0,
                "world": w, "nodes": int(rs["nodes"]),
                "value": fbits(int(rs["value_bits"])),
                "to_move": int(rs["to_move"]),
                "child_values": {int(a): fbits(int(v)) for a, v in rs["child_values"]}}

    raise ValueError(f"unknown solve mode {p['mode']!r}")


def solve_clairvoyant_M(base_payload, m_worlds, mem_cap_gb, cpu_cap_s):
    """`m_worlds` INDEPENDENTLY isolated clairvoyant solves, averaged per action.

    ⚠️ CLAIRVOYANCE GAP: each world's optimal line sees that world's future, so the
    mean is an OPTIMISTIC bound for BOTH seats, not a calibrated EV. Never pooled
    with `exact_marginalized`.
    """
    acc, n_ok, nodes, to_move, worlds = {}, 0, 0, None, []
    true_future, t0 = None, time.time()
    for w in range(-1, m_worlds):
        res = solve_isolated({**base_payload, "mode": "exact_clairvoyant_world",
                              "world": w}, mem_cap_gb, cpu_cap_s)
        if res.get("status") != "OK":
            worlds.append({"world": w, "status": res.get("status"),
                           "kill_reason": res.get("kill_reason")})
            continue
        nodes += res["nodes"]
        to_move = res["to_move"]
        if w < 0:
            true_future = res["value"]
            worlds.append({"world": w, "status": "OK", "true_future": True,
                           "value": res["value"], "solve_s": res["solve_s"]})
            continue
        n_ok += 1
        for a, v in res["child_values"].items():
            acc[a] = acc.get(a, 0.0) + v
        worlds.append({"world": w, "status": "OK", "value": res["value"],
                       "solve_s": res["solve_s"]})
    if n_ok == 0:
        return {"status": "ALL_WORLDS_SKIPPED", "worlds": worlds,
                "elapsed_s": time.time() - t0}
    return {"status": "OK", "solve_s": time.time() - t0, "nodes": nodes,
            "m_worlds_ok": n_ok, "m_worlds_requested": m_worlds, "to_move": to_move,
            "child_values": {a: s / n_ok for a, s in acc.items()},
            "true_future_value": true_future, "worlds": worlds,
            "caveat": "CLAIRVOYANCE GAP — per-world optimal play sees the future; "
                      "an OPTIMISTIC bound for BOTH seats, not a calibrated EV. "
                      "Never pooled with exact_marginalized."}


def solve_isolated(payload, mem_cap_gb: float, cpu_cap_s: int) -> dict:
    mem_bytes = int(mem_cap_gb * (1 << 30)) if mem_cap_gb > 0 else 0
    if mem_bytes <= 0 and cpu_cap_s <= 0:
        return _do_solve(payload)
    ctx = mp.get_context("fork")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_solve_child,
                       args=(payload, mem_bytes, int(cpu_cap_s), child))
    t0 = time.time()
    proc.start()
    child.close()
    wall_cap = (cpu_cap_s + WALL_GRACE_S) if cpu_cap_s > 0 else None
    status, out, wall_timeout = None, None, False
    try:
        if parent.poll(timeout=wall_cap):
            try:
                status, out = parent.recv()
            except EOFError:
                status = "EOF"
        elif wall_cap is not None:
            wall_timeout = True
    finally:
        parent.close()
    if wall_timeout:
        try:
            proc.kill()
        except Exception:                             # noqa: BLE001
            pass
    proc.join(timeout=60)
    elapsed = time.time() - t0
    if wall_timeout:
        return {"status": "TIME_SKIPPED", "kill_reason": "wall", "elapsed_s": elapsed}
    if status == "OK":
        out["elapsed_s"] = elapsed
        return out
    if proc.exitcode == -signal.SIGXCPU:
        return {"status": "TIME_SKIPPED", "kill_reason": "rlimit_cpu",
                "exitcode": proc.exitcode, "elapsed_s": elapsed}
    if status == "OOM" or (proc.exitcode is not None and proc.exitcode < 0) \
            or status == "EOF":
        return {"status": "OOM_SKIPPED", "exitcode": proc.exitcode,
                "elapsed_s": elapsed}
    return {"status": "ERROR", "detail": out, "elapsed_s": elapsed}


# --------------------------------------------------------------------------- #
# the pricing pass                                                              #
# --------------------------------------------------------------------------- #
def price_from_child_values(cv: dict, played: int, counterfactual, actor: int) -> dict:
    """The pricing arithmetic, isolated so it can be unit-tested on fixtures.

    `cv` maps root action -> the EXACT final-score differential (P0 - P1) that
    follows it under optimal play. P0 maximizes and P1 minimizes at every depth
    (`endgame_solver.solve`), so:

      * `price_best` is max(cv) for the P0 mover and min(cv) for the P1 mover;
      * `delta_pts_mover` is positive iff the PLAYED move is better FOR THE MOVER
        than the counterfactual — i.e. (played - counterfactual) for P0 and its
        negation for P1.

    Every returned value is in TRUE final-score points.
    """
    out = {"n_root_actions": len(cv),
           "price_played": cv.get(played),
           "price_counterfactual": (cv.get(counterfactual)
                                    if counterfactual is not None else None),
           "price_best": None, "delta_pts_mover": None,
           "regret_pts_mover": None}
    if not cv:
        return out
    out["price_best"] = max(cv.values()) if actor == 0 else min(cv.values())
    vp, vc = out["price_played"], out["price_counterfactual"]
    if vp is not None and vc is not None:
        d = vp - vc
        out["delta_pts_mover"] = d if actor == 0 else -d
    if vp is not None:
        r = out["price_best"] - vp
        out["regret_pts_mover"] = r if actor == 0 else -r
    return out


def mode_for_k(k: int, cut: dict) -> str:
    if k <= cut["k_marginalized_max"]:
        return "exact_marginalized"
    if k <= cut["k_clairvoyant_max"]:
        return "exact_clairvoyant_M"
    return "realized"


def price_game(stem, profile, targets, cut, args, fh, log):
    """Walk one archive, name the champion counterfactual, price the flagged plies.

    Construction follows `analyzer/ev_loss.grade_archive` exactly — the ONE
    audited path that builds the production champion under a resolved rules
    profile and drives its Rust mirror: `rules_profile.activate` ->
    `resolve_execution` -> `make_production_champion("fair", ...)` -> `seat` ->
    per-ply `agent._move_idx = ply` -> `choose_action` -> `advance`.
    """
    from carcassonne_ai import rules_profile
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    arc = json.loads((ARCHIVES / stem).read_text())
    seed = int(arc["deck_seed"])
    actions = [int(x) for x in arc["actions"]]
    final_scores = [int(x) for x in arc["scores"]]
    prof = rules_profile.activate(profile)
    ex = resolve_execution("inherit", profile="desktop", rust_threads=args.threads)

    want = {t["ply"]: t for t in targets}
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    champ = make_production_champion("fair", game=game, seed=COUNTERFACTUAL_SEED,
                                     verify=True, **ex.factory_kwargs())
    seat(champ, board)

    scores_at = {}
    for i, a in enumerate(actions):
        st = board.state
        scores_at[i] = [int(x) for x in st.scores]
        if i in want:
            t = want[i]
            row = dict(t)
            row["pricing_mode"] = mode_for_k(t["k"], cut)
            row["scores_at_ply"] = scores_at[i]
            row["execution"] = dict(ex)
            # --- counterfactual: the champion's own move at this exact state --
            t0 = time.time()
            try:
                champ._move_idx = i          # mirror_protocol: caller owns the timeline
                cf = int(champ.choose_action(board))
                row["counterfactual_action"] = cf
                row["counterfactual_s"] = round(time.time() - t0, 3)
                row["counterfactual_agrees"] = (cf == t["played_action"])
                lm = champ.last_move()
                row["counterfactual_flags"] = {
                    k: lm[k] for k in ("forced", "exact", "latched", "timeout")
                    if k in lm}
            except Exception as e:                    # noqa: BLE001
                row["counterfactual_action"] = None
                row["counterfactual_error"] = f"{type(e).__name__}: {e}"
                row["counterfactual_agrees"] = None
            # --- price -------------------------------------------------------
            if row["pricing_mode"].startswith("exact"):
                payload = {"profile": profile, "deck_seed": seed,
                           "actions": actions, "ply": i, "budget": args.budget}
                if row["pricing_mode"] == "exact_marginalized":
                    res = solve_isolated({**payload, "mode": "exact_marginalized"},
                                         args.job_mem_cap_gb, args.job_time_cap_secs)
                else:
                    res = solve_clairvoyant_M(payload, cut["m_worlds"],
                                              args.job_mem_cap_gb,
                                              args.job_time_cap_secs)
                row["solve"] = {k: v for k, v in res.items()
                                if k not in ("child_values",)}
                cv = res.get("child_values") or {}
                if res.get("status") == "OK" and cv:
                    row.update(price_from_child_values(
                        cv, t["played_action"], row.get("counterfactual_action"),
                        t["actor"]))
                else:
                    row["price_played"] = row["price_counterfactual"] = None
                    row["delta_pts_mover"] = None
            else:
                row["solve"] = {"status": "NOT_SOLVED", "reason": "K above the cut"}
                row["price_played"] = row["price_counterfactual"] = None
                row["delta_pts_mover"] = None
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            log(f"  ply {i:3d} K={t['k']:2d} {t['stratum']:12s} "
                f"{row['pricing_mode']:20s} "
                f"cf_agree={row.get('counterfactual_agrees')} "
                f"delta={row.get('delta_pts_mover')} "
                f"solve={row['solve'].get('status')}")
        board, _ = game.get_next_state(board, a)
        advance(champ, a)
    scores_at[len(actions)] = [int(x) for x in board.state.scores]
    return scores_at, final_scores


def attach_realized(rows_path, scores_by_game, finals_by_game):
    """Second pass — the judge-free realized-outcome arithmetic."""
    out = []
    for line in Path(rows_path).open():
        r = json.loads(line)
        sc, fin = scores_by_game[r["game"]], finals_by_game[r["game"]]
        p, n = r["ply"], r["n_plies"]
        here = sc.get(p) or [0, 0]
        w = min(n, p + REALIZED_WINDOW_PLIES)
        there = sc.get(w) or sc.get(n) or here
        r["realized"] = {
            "margin_at_ply": here[0] - here[1],
            "margin_at_ply_plus_W": there[0] - there[1],
            "realized_swing_W": (there[0] - there[1]) - (here[0] - here[1]),
            "realized_swing_end": (fin[0] - fin[1]) - (here[0] - here[1]),
            "window_plies": REALIZED_WINDOW_PLIES,
            "feature_gross_gain": (r.get("notes") or {}).get("invader_gain"),
            "feature_gross_denied": (r.get("notes") or {}).get("incumbent_denied"),
            "caveat": "DESCRIPTIVE archive arithmetic, not an EV. In-play scores "
                      "only (farms score at the end), no counterfactual, wide "
                      "error bars. Never quote as a price.",
        }
        out.append(r)
    with Path(rows_path).open("w") as fh:
        for r in out:
            fh.write(json.dumps(r) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--mode-cut", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", default=None)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--budget", type=int, default=200_000_000)
    ap.add_argument("--job-mem-cap-gb", type=float, default=8.0)
    ap.add_argument("--job-time-cap-secs", type=int, default=1800)
    ap.add_argument("--games", default=None, help="comma-separated stems (a shard)")
    ap.add_argument("--limit-plies", type=int, default=0, help="smoke: stop after N")
    ap.add_argument("--done-sentinel", default=None)
    args = ap.parse_args()

    from analyzer.ev_loss import prepare_env
    env = prepare_env(args.profile)
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    cut = json.loads(Path(args.mode_cut).read_text())
    rows = [json.loads(l) for l in Path(args.targets).open()
            if json.loads(l)["profile"] == args.profile]
    if args.games:
        keep = set(args.games.split(","))
        rows = [r for r in rows if r["game"] in keep]
    if args.limit_plies:
        # A smoke must exercise BOTH paths at PRODUCTION knobs, so it takes half
        # its rows from the cheapest exact-solvable end and half spread evenly over
        # the rest (the `realized` bulk). Sorting by K alone would smoke only the
        # solver and never touch the arithmetic that 90 % of the run uses.
        ordered = sorted(rows, key=lambda r: (r["k"], r["game"], r["ply"]))
        half = max(1, args.limit_plies // 2)
        low = ordered[:half]
        rest = ordered[half:]
        step = max(1, len(rest) // max(1, args.limit_plies - half))
        rows = low + rest[::step][:args.limit_plies - half]

    by_game = {}
    for r in rows:
        by_game.setdefault(r["game"], []).append(r)

    logf = open(args.log, "a", buffering=1) if args.log else None

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        if logf:
            logf.write(line + "\n")

    log(f"START profile={args.profile} games={len(by_game)} plies={len(rows)} "
        f"cut={cut} env={env} threads={args.threads}")

    scores_by_game, finals_by_game = {}, {}
    t_start = time.time()
    with open(args.out, "w") as fh:
        for gi, (stem, ts) in enumerate(sorted(by_game.items()), 1):
            log(f"[{gi}/{len(by_game)}] {stem} ({len(ts)} plies)")
            sc, fin = price_game(stem, args.profile, ts, cut, args, fh, log)
            scores_by_game[stem], finals_by_game[stem] = sc, fin
    attach_realized(args.out, scores_by_game, finals_by_game)
    dt = time.time() - t_start
    log(f"DONE {len(rows)} plies in {dt:.1f}s (mean {dt/max(1,len(rows)):.2f}s/ply)")
    if args.done_sentinel:
        Path(args.done_sentinel).write_text(json.dumps({
            "profile": args.profile, "n_plies": len(rows), "elapsed_s": dt,
            "finished_at": time.time(), "out": str(args.out)}, indent=1))


if __name__ == "__main__":
    main()
