"""rustport **P4 / gate G4** — the FAIR AGENT: Rust vs Python, 0 mismatches.

    .venv/bin/python scripts/rustport/reconcile_fair.py --help

The phase that reproduces the deployed champion (`governance/PRODUCTION.yaml`
`champion.fair_deploy`: `k_dets=8`, `sims_per_det=1376`, exact-K<=2 marginalized
handoff).  The Python oracle is
`champion_factory.make_production_champion("fair", parallel_workers=None)` —
the SEQUENTIAL k-loop, byte-for-byte the deployed agent and the world order the
Rust merge is defined against.

WHAT IS COMPARED, per DECISION (all RAW-FLOAT, never decimal):

  * the chosen action;
  * the pooled `(N, W)` accumulators as raw `f64` bits, **in pool insertion
    order** — the half of the gate action identity alone would not catch, since
    two different pools can pick the same move.  `agg_w` is captured by
    monkeypatching `fair_agent.pooled_q_argmax` (the `tests/test_kparallel.py`
    `_PoolSpy` pattern);
  * the forced / exact / latched / timeout flags;
  * the solver's node count on every exact decision.

LEGS (`--leg`, repeatable, or `all`):

  latch    the one-way latch TRAJECTORY (ply, k_remaining, latched) over every
           recorded game — pure engine, no search, so it runs the FULL corpus
  solver   marginalized expectiminimax parity: value bits + optimal-action set +
           node count, against (a) the 14 solver blocks FROZEN on disk in
           `tests/golden/golden_fixture.json`, (b) the live Python solver on the
           same positions, (c) every K<=2 decision of the recorded games — the
           deployed band — and (d) the 354 K=3 suite roots (above the band)
  game     FULL-GAME lockstep, the `tests/test_kparallel.py` template
           re-instantiated against `FairAgentRs`: both agents step the same
           game, every decision compared, then the latch counters
           (`exact_moves` / `latch_k` / `n_timeouts` / `solver_nodes`) at the end
  pos      move-by-move `choose_action` identity at sampled plies of the
           recorded corpora (champ / e4 / golden), both legs seated onto the
           same `_move_idx` and latch state
  threads  thread-count invariance: the Rust leg at threads = 1, 4, 8 must be
           BIT-identical (deterministic-by-construction merge)
  bench    s/move on both legs

Artifacts land in `measurement/rustport_p4/`.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "rustport"))

# ⚠️ fair_common applies the production leaf env and MUST precede carcassonne_ai.
import fair_common as F  # noqa: E402

import carc_rs  # noqa: E402
import trace_search as T  # noqa: E402
from _g0_common import environment  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p4"
GOLDEN = REPO / "tests" / "golden" / "golden_fixture.json"
CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
E4DIR = REPO / "measurement" / "e4_games"
K3 = REPO / "measurement" / "f3_public_state_oracle" / "roots_k3_suite.jsonl"

LEGS = ["latch", "solver", "game", "pos", "threads", "bench"]

# Per-worker singletons (forked once, reused for every job in that worker).
_KNOBS = None


def knobs():
    global _KNOBS
    if _KNOBS is None:
        _KNOBS = T.production_knobs()
    return _KNOBS


# --------------------------------------------------------------------------- #
# Corpus loading                                                               #
# --------------------------------------------------------------------------- #
def champ_games(limit: int | None = None) -> list[dict]:
    recs = [json.loads(l) for l in CHAMP.open() if l.strip()]
    return recs[:limit] if limit else recs


def e4_games() -> list[dict]:
    out = []
    for path in sorted(E4DIR.glob("*.json")):
        d = json.loads(path.read_text())
        if d.get("schema") != "carcassonne-android-archive/v1":
            raise SystemExit(f"{path}: unexpected schema {d.get('schema')!r}")
        out.append({"game_id": path.stem, "deck_seed": int(d["deck_seed"]),
                    "actions": [int(a) for a in d["actions"]]})
    return out


def golden_games() -> list[dict]:
    gf = json.loads(GOLDEN.read_text())
    return [{"game_id": s, "deck_seed": int(g["deck_seed"]),
             "actions": [int(a) for a in g["actions"]]}
            for s, g in sorted(gf["games"].items(), key=lambda kv: int(kv[0]))]


def golden_solver_positions() -> list[dict]:
    """The fixture positions carrying a frozen MARGINALIZED solve (k<=2)."""
    gf = json.loads(GOLDEN.read_text())
    games = gf["games"]
    out = []
    for p in gf["positions"]:
        if not p.get("solver"):
            continue
        g = games[str(p["seed"])]
        out.append({"label": f"golden/{p['seed']}@{p['ply']}#{p['id']}",
                    "deck_seed": int(p["deck_seed"]),
                    "actions": [int(a) for a in g["actions"]],
                    "ply": int(p["ply"]),
                    "frozen": p["solver"]})
    return out


# --------------------------------------------------------------------------- #
# Replay helpers                                                               #
# --------------------------------------------------------------------------- #
def _seat(deck_seed: int, actions, ply: int):
    """`(game, board, rs_agent_state)` at `ply`, plus the latch state a fair agent
    would carry INTO that ply's decision.

    The latch is a function of the game's HISTORY (first TILES decision with
    `k_remaining <= EXACT_MAX_K`, one-way), so a harness that jumps onto a
    mid-game position has to derive it — and hand the SAME answer to both legs.
    """
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    latched, latch_k = False, None
    for i in range(ply):
        k = F.k_remaining_py(board)
        if not latched and board.state.phase == GamePhase.TILES and k <= F.EXACT_MAX_K:
            latched, latch_k = True, k
        board, _ = game.get_next_state(board, int(actions[i]))
    return game, board, latched, latch_k


def _rs_seat(agent, deck_seed: int, actions, ply: int, latched: bool,
             latch_k, move_idx: int):
    agent.start_game_from_seed(str(int(deck_seed)))
    for a in actions[:ply]:
        agent.advance(int(a))
    agent.set_latched(bool(latched), latch_k)
    agent.set_move_idx(int(move_idx))


def _blank() -> dict:
    return {"checks": 0, "mismatches": [], "decisions": 0, "plies": 0,
            "games": 0, "solves": 0, "solver_nodes": 0, "exact_moves": 0,
            "py_secs": 0.0, "rs_secs": 0.0, "py_moves": 0, "rs_moves": 0}


def _merge(a: dict, b: dict) -> dict:
    for k, v in b.items():
        if k == "mismatches":
            a[k].extend(v)
        elif k in a:
            a[k] += v
        else:
            a[k] = v
    return a


# --------------------------------------------------------------------------- #
# Jobs                                                                         #
# --------------------------------------------------------------------------- #
def _latch_job(job: dict) -> dict:
    """The latch state machine over a whole recorded game — pure engine."""
    out = _blank()
    random.seed(int(job["deck_seed"]))
    game = Game(enable_legal_moves_cache=True)
    py = F.latch_trajectory_py(game, job["actions"])
    rs = F.latch_trajectory_rs(job["deck_seed"], job["actions"])
    out["plies"] = len(py)
    out["games"] = 1
    out["checks"] = len(py) * 3
    if py != rs:
        diffs = [(p, q) for p, q in zip(py, rs) if p != q]
        out["mismatches"].append({
            "tag": job["label"], "field": "latch_trajectory",
            "n_plies": [len(py), len(rs)], "n_diffs": len(diffs),
            "diffs": diffs[:8]})
    game.clear_caches()
    return out


def _solver_job(job: dict) -> dict:
    """Marginalized-solver parity at one position (+ the frozen disk values)."""
    out = _blank()
    game, board, _latched, _lk = _seat(job["deck_seed"], job["actions"], job["ply"])
    ra = F.rs_agent(sims=1, k_dets=1, seed=0, threads=1, knobs=knobs())
    ra.start_game_from_seed(str(int(job["deck_seed"])))
    for a in job["actions"][:job["ply"]]:
        ra.advance(int(a))
    if game.string_representation(board) != ra.string_repr():
        out["mismatches"].append({"tag": job["label"], "field": "replay_desync"})
        return out

    budget = int(job.get("budget", F.EXACT_BUDGET))
    t0 = time.perf_counter()
    py = F.py_solve(game, board, budget)
    out["py_secs"] += time.perf_counter() - t0
    t1 = time.perf_counter()
    rs = F.rs_solve(ra, budget)
    out["rs_secs"] += time.perf_counter() - t1
    out["solves"] = 1
    out["checks"] += len(F.SOLVER_FIELDS)
    out["mismatches"].extend(F.compare_solve(py, rs, job["label"]))
    if rs is not None:
        out["solver_nodes"] = int(rs["nodes"])

    frozen = job.get("frozen")
    if frozen is not None:
        # Re-judge the values FROZEN ON DISK, not a live Python recomputation.
        out["checks"] += 3
        if rs is None:
            out["mismatches"].append({"tag": job["label"], "field": "frozen_vs_rust",
                                      "note": "rust hit the budget; disk has a value"})
        else:
            want = (F.ubits(float(frozen["value"])),
                    [int(a) for a in frozen["optimal_actions"]],
                    int(frozen["nodes"]))
            got = (rs["value_bits"], rs["optimal_actions"], rs["nodes"])
            if want != got:
                out["mismatches"].append({
                    "tag": job["label"], "field": "frozen_vs_rust",
                    "disk": want, "rust": got})
    game.clear_caches()
    return out


def _k3_job(job: dict) -> dict:
    """A K=3 suite root: replay the deterministic greedy generator policy
    (`gen_endgame_positions.replay_to`), then solve both ways.  ABOVE the
    deployed K<=2 band, so it is breadth, not the deployed contract."""
    import gen_endgame_positions as GEP
    from carcassonne_ai.rule_based_player import RuleBasedPlayer

    out = _blank()
    seed, ply = int(job["deck_seed"]), int(job["ply"])
    random.seed(seed)
    game = GEP._new_game()
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEP.GEN_PLAYER_SEED)
    ra = F.rs_agent(sims=1, k_dets=1, seed=0, threads=1, knobs=knobs())
    ra.start_game_from_seed(str(seed))
    for _ in range(ply):
        mask = game.get_valid_moves(board)
        a = int(player.choose_action(game, board, mask))
        board, _ = game.get_next_state(board, a)
        ra.advance(a)
        out["plies"] += 1
    if game.string_representation(board) != ra.string_repr():
        out["mismatches"].append({"tag": job["label"], "field": "greedy_replay_desync"})
        return out
    budget = int(job.get("budget", F.EXACT_BUDGET))
    t0 = time.perf_counter()
    py = F.py_solve(game, board, budget)
    out["py_secs"] += time.perf_counter() - t0
    t1 = time.perf_counter()
    rs = F.rs_solve(ra, budget)
    out["rs_secs"] += time.perf_counter() - t1
    out["solves"] = 1
    out["checks"] += len(F.SOLVER_FIELDS)
    out["mismatches"].extend(F.compare_solve(py, rs, job["label"]))
    if rs is not None:
        out["solver_nodes"] = int(rs["nodes"])
    game.clear_caches()
    return out


def _game_job(job: dict) -> dict:
    """FULL-GAME lockstep — the `tests/test_kparallel.py` template vs Rust.

    Both agents play their OWN move from the same position; the PYTHON action is
    applied to both (they must agree, so the choice of which to apply is
    cosmetic — but applying one keeps the two timelines provably identical even
    if a mismatch is only reported rather than raised)."""
    out = _blank()
    sims, k, seed = int(job["sims"]), int(job["k_dets"]), int(job["agent_seed"])
    random.seed(int(job["deck_seed"]))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    pa = F.py_agent(game, sims=sims, k_dets=k, seed=seed)
    ra = F.rs_agent(sims=sims, k_dets=k, seed=seed, threads=int(job["threads"]),
                    knobs=knobs())
    ra.start_game_from_seed(str(int(job["deck_seed"])))
    max_moves = job.get("max_moves")
    n = 0
    with F.PoolSpy() as spy:
        while not game.get_game_ended(board, 0):
            if max_moves is not None and n >= max_moves:
                break
            t0 = time.perf_counter()
            p = F.py_decision(pa, board, spy)
            out["py_secs"] += time.perf_counter() - t0
            t1 = time.perf_counter()
            r = F.rs_decision(ra)
            out["rs_secs"] += time.perf_counter() - t1
            out["py_moves"] += 1
            out["rs_moves"] += 1
            out["decisions"] += 1
            out["checks"] += len(F.DECISION_FIELDS)
            bad = F.compare_decision(p, r, f"{job['label']}@ply{n}")
            out["mismatches"].extend(bad)
            if p["action"] != r["action"]:
                break               # the timelines have forked; stop this game
            board, _ = game.get_next_state(board, p["action"])
            ra.advance(p["action"])
            n += 1
    # The end-of-game latch counters (the `test_kparallel` (c)+(d) assertions).
    s = ra.stats()
    out["checks"] += 4
    counters = [("exact_moves", int(pa.exact_moves), int(s["exact_moves"])),
                ("latch_k", pa.latch_k, s["latch_k"]),
                ("n_timeouts", int(pa.n_timeouts), int(s["n_timeouts"])),
                ("solver_nodes", int(pa.solver_nodes), int(s["solver_nodes"]))]
    for name, a, b in counters:
        if a != b:
            out["mismatches"].append({"tag": job["label"], "field": f"counter/{name}",
                                      "py": a, "rs": b})
    out["exact_moves"] = int(pa.exact_moves)
    out["solver_nodes"] = int(pa.solver_nodes)
    out["games"] = 1
    out["plies"] = n
    game.clear_caches()
    return out


def _pos_job(job: dict) -> dict:
    """One DECISION at a recorded ply: both legs seated identically, compared."""
    out = _blank()
    sims, k, seed = int(job["sims"]), int(job["k_dets"]), int(job["agent_seed"])
    ply = int(job["ply"])
    game, board, latched, latch_k = _seat(job["deck_seed"], job["actions"], ply)
    pa = F.py_agent(game, sims=sims, k_dets=k, seed=seed)
    pa._move_idx = ply
    pa._latched = bool(latched)
    pa.latch_k = latch_k
    ra = F.rs_agent(sims=sims, k_dets=k, seed=seed, threads=int(job["threads"]),
                    knobs=knobs())
    _rs_seat(ra, job["deck_seed"], job["actions"], ply, latched, latch_k, ply)
    if game.string_representation(board) != ra.string_repr():
        out["mismatches"].append({"tag": job["label"], "field": "replay_desync"})
        return out
    with F.PoolSpy() as spy:
        t0 = time.perf_counter()
        p = F.py_decision(pa, board, spy)
        out["py_secs"] += time.perf_counter() - t0
    t1 = time.perf_counter()
    r = F.rs_decision(ra)
    out["rs_secs"] += time.perf_counter() - t1
    out["py_moves"] = out["rs_moves"] = 1
    out["decisions"] = 1
    out["checks"] = len(F.DECISION_FIELDS)
    out["mismatches"].extend(F.compare_decision(p, r, job["label"]))
    game.clear_caches()
    return out


def _threads_job(job: dict) -> dict:
    """Thread-count invariance: bit-identical Rust results at 1 / 4 / 8 threads.

    The merge is a sequential fold over an index-addressed result vector done
    AFTER every join, so this is invariance BY CONSTRUCTION — the test exists to
    keep it that way."""
    out = _blank()
    sims, k, seed = int(job["sims"]), int(job["k_dets"]), int(job["agent_seed"])
    ply = int(job["ply"])
    _g, _b, latched, latch_k = _seat(job["deck_seed"], job["actions"], ply)
    ref = None
    for t in job["threads_list"]:
        ra = F.rs_agent(sims=sims, k_dets=k, seed=seed, threads=int(t), knobs=knobs())
        _rs_seat(ra, job["deck_seed"], job["actions"], ply, latched, latch_k, ply)
        t0 = time.perf_counter()
        rec = F.rs_decision(ra)
        out["rs_secs"] += time.perf_counter() - t0
        out["rs_moves"] += 1
        if ref is None:
            ref = (rec, int(t))
            continue
        out["checks"] += len(F.DECISION_FIELDS)
        bad = F.compare_decision(ref[0], rec, f"{job['label']}/threads{ref[1]}vs{t}")
        for b in bad:
            b["leg"] = "threads"
        out["mismatches"].extend(bad)
    out["decisions"] = 1
    return out


_DISPATCH = {"latch": _latch_job, "solver": _solver_job, "k3": _k3_job,
             "game": _game_job, "pos": _pos_job, "threads": _threads_job}


def run_job(job: dict) -> dict:
    try:
        out = _DISPATCH[job["fn"]](job)
    except Exception as e:                      # never let one job kill a batch
        import traceback
        out = _blank()
        out["mismatches"].append({"tag": job.get("label", "?"), "field": "EXCEPTION",
                                  "error": f"{type(e).__name__}: {e}",
                                  "tb": traceback.format_exc()[-1200:]})
    out["leg"] = job["leg"]
    return out


# --------------------------------------------------------------------------- #
# Job construction                                                             #
# --------------------------------------------------------------------------- #
def _plies_for(n: int, stride: int, per_game: int | None) -> list[int]:
    plies = list(range(0, n, max(1, stride)))
    if per_game:
        plies = plies[:per_game]
    return plies


def build_jobs(args) -> list[dict]:
    legs = LEGS if "all" in args.leg else args.leg
    jobs: list[dict] = []
    champ = champ_games(args.limit)
    e4 = e4_games()
    golden = golden_games()

    if "latch" in legs:
        for src, recs in (("champ", champ), ("e4", e4), ("golden", golden)):
            for g in recs:
                jobs.append({"fn": "latch", "leg": "latch",
                             "label": f"latch/{src}/{g['game_id']}",
                             "deck_seed": g["deck_seed"], "actions": g["actions"]})

    if "solver" in legs:
        for p in golden_solver_positions():
            jobs.append({"fn": "solver", "leg": "solver", **p})
        # every K<=2 DECISION of the recorded games — the deployed band
        n_end = 0
        for src, recs in (("champ", champ), ("e4", e4), ("golden", golden)):
            for g in recs:
                traj = F.latch_trajectory_rs(g["deck_seed"], g["actions"])
                for ply, k, _lat in traj:
                    if k > F.EXACT_MAX_K:
                        continue
                    if args.endgame_limit and n_end >= args.endgame_limit:
                        break
                    n_end += 1
                    jobs.append({"fn": "solver", "leg": "solver",
                                 "label": f"endgame/{src}/{g['game_id']}@{ply}",
                                 "deck_seed": g["deck_seed"],
                                 "actions": g["actions"], "ply": ply})
        if args.k3:
            recs = [json.loads(l) for l in K3.open() if l.strip()][:args.k3]
            for r in recs:
                jobs.append({"fn": "k3", "leg": "solver",
                             "label": f"k3/{r['seed']}@{r['ply']}",
                             "deck_seed": int(r["seed"]), "ply": int(r["ply"]),
                             "budget": args.k3_budget})

    if "game" in legs:
        for i, g in enumerate(golden[:args.n_games]):
            jobs.append({"fn": "game", "leg": "game", "label": f"game/golden/{g['game_id']}",
                         "deck_seed": g["deck_seed"], "agent_seed": 101 + i,
                         "sims": args.sims, "k_dets": args.k_dets,
                         "threads": args.threads, "max_moves": args.max_moves})
        for i, g in enumerate(e4):
            jobs.append({"fn": "game", "leg": "game", "label": f"game/e4/{g['game_id']}",
                         "deck_seed": g["deck_seed"], "agent_seed": 202 + i,
                         "sims": args.sims, "k_dets": args.k_dets,
                         "threads": args.threads, "max_moves": args.max_moves})

    if "pos" in legs:
        srcs = [("champ", champ), ("e4", e4), ("golden", golden)]
        for src, recs in srcs:
            for i, g in enumerate(recs):
                for ply in _plies_for(len(g["actions"]), args.stride, args.per_game):
                    jobs.append({
                        "fn": "pos", "leg": "pos",
                        "label": f"pos/{src}/{g['game_id']}@{ply}",
                        "deck_seed": g["deck_seed"], "actions": g["actions"],
                        "ply": ply, "agent_seed": 303 + i, "sims": args.sims,
                        "k_dets": args.k_dets, "threads": 1})

    if "threads" in legs:
        tl = [int(x) for x in args.threads_list.split(",")]
        for i, g in enumerate(golden[:args.n_thread_games]):
            for ply in _plies_for(len(g["actions"]), args.thread_stride, args.per_game):
                jobs.append({
                    "fn": "threads", "leg": "threads",
                    "label": f"threads/golden/{g['game_id']}@{ply}",
                    "deck_seed": g["deck_seed"], "actions": g["actions"],
                    "ply": ply, "agent_seed": 404 + i, "sims": args.sims,
                    "k_dets": args.k_dets, "threads_list": tl})

    return jobs


# --------------------------------------------------------------------------- #
# Bench                                                                        #
# --------------------------------------------------------------------------- #
def bench(args) -> dict:
    """s/move on both legs at the champion budget, over midgame positions of one
    recorded game (a realistic board-size mix, not all-opening)."""
    g = champ_games(1)[0]
    plies = [30, 60, 90, 120]
    plies = [p for p in plies if p < len(g["actions"])][:args.bench_positions]
    rows = []
    for ply in plies:
        game, board, latched, latch_k = _seat(g["deck_seed"], g["actions"], ply)
        pa = F.py_agent(game, sims=args.sims, k_dets=args.k_dets, seed=7)
        pa._move_idx, pa._latched = ply, latched
        t0 = time.perf_counter()
        with F.PoolSpy() as spy:
            F.py_decision(pa, board, spy)
        py_s = time.perf_counter() - t0
        row = {"ply": ply, "py_secs": py_s, "rs": {}}
        for t in [int(x) for x in args.threads_list.split(",")]:
            ra = F.rs_agent(sims=args.sims, k_dets=args.k_dets, seed=7, threads=t,
                            knobs=knobs())
            _rs_seat(ra, g["deck_seed"], g["actions"], ply, latched, latch_k, ply)
            t1 = time.perf_counter()
            F.rs_decision(ra)
            row["rs"][str(t)] = time.perf_counter() - t1
        rows.append(row)
        game.clear_caches()
    n = max(1, len(rows))
    out = {"positions": rows,
           "sims_per_move": args.sims * args.k_dets,
           "py_mean_s_per_move": sum(r["py_secs"] for r in rows) / n,
           "rs_mean_s_per_move": {
               t: sum(r["rs"][t] for r in rows) / n for t in rows[0]["rs"]} if rows else {}}
    out["speedup_vs_py"] = {t: out["py_mean_s_per_move"] / v
                            for t, v in out["rs_mean_s_per_move"].items() if v > 0}
    return out


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--leg", action="append", default=None,
                    help=f"repeatable; one of {LEGS} or 'all'")
    ap.add_argument("--sims", type=int, default=1376, help="sims PER determinization")
    ap.add_argument("--k-dets", type=int, default=8)
    ap.add_argument("--threads", type=int, default=1, help="Rust world threads per job")
    ap.add_argument("--threads-list", default="1,4,8",
                    help="the thread counts the `threads` leg and `bench` sweep")
    ap.add_argument("--workers", type=int, default=8, help="job-level fork pool")
    ap.add_argument("--stride", type=int, default=12, help="`pos` leg ply stride")
    ap.add_argument("--per-game", type=int, default=None,
                    help="cap sampled plies per game")
    ap.add_argument("--limit", type=int, default=None, help="cap champ games")
    ap.add_argument("--n-games", type=int, default=4, help="`game` leg golden games")
    ap.add_argument("--max-moves", type=int, default=None,
                    help="cap plies per full-game job (None = to termination)")
    ap.add_argument("--n-thread-games", type=int, default=2)
    ap.add_argument("--thread-stride", type=int, default=25)
    ap.add_argument("--endgame-limit", type=int, default=None,
                    help="cap the K<=2 solver positions")
    ap.add_argument("--k3", type=int, default=0,
                    help="how many K=3 suite roots to solve (0 = skip; expensive)")
    ap.add_argument("--k3-budget", type=int, default=F.EXACT_BUDGET)
    ap.add_argument("--bench-positions", type=int, default=3)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--max-mismatch-report", type=int, default=200)
    args = ap.parse_args(argv)
    args.leg = args.leg or ["all"]

    t_start = time.time()
    k = knobs()
    jobs = build_jobs(args)
    legs = LEGS if "all" in args.leg else args.leg
    print(f"[G4] {len(jobs)} jobs over legs={legs} "
          f"k{args.k_dets}x{args.sims}={args.k_dets * args.sims} "
          f"workers={args.workers} rust_threads={args.threads}", flush=True)

    totals = _blank()
    per_leg: dict[str, dict] = {}
    done = 0
    if jobs:
        if args.workers > 1:
            ctx = mp.get_context("fork")
            with ctx.Pool(args.workers) as pool:
                it = pool.imap_unordered(run_job, jobs, chunksize=1)
                for out in it:
                    done += 1
                    leg = out.pop("leg")
                    per_leg.setdefault(leg, _blank())
                    _merge(per_leg[leg], dict(out))
                    _merge(totals, out)
                    if done % 25 == 0:
                        print(f"  {done}/{len(jobs)} jobs, "
                              f"{len(totals['mismatches'])} mismatches "
                              f"({time.time() - t_start:.0f}s)", flush=True)
        else:
            for job in jobs:
                out = run_job(job)
                done += 1
                leg = out.pop("leg")
                per_leg.setdefault(leg, _blank())
                _merge(per_leg[leg], dict(out))
                _merge(totals, out)
                if done % 5 == 0:
                    print(f"  {done}/{len(jobs)} jobs, "
                          f"{len(totals['mismatches'])} mismatches", flush=True)

    bench_out = bench(args) if "bench" in legs else None

    n_bad = len(totals["mismatches"])
    ok = n_bad == 0
    payload = {
        "gate": "G4/fair",
        "verdict": "PASS" if ok else "FAIL",
        "env": environment(),
        "knobs": {kk: vv for kk, vv in k.items() if kk != "leaf_cfg"},
        "leaf_env": {kk: os.environ.get(kk) for kk in (
            "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP",
            "CARCASSONNE_V25_DROP_THREE_OPEN", "CARCASSONNE_V29_MEEPLE_CURVE",
            "CARCASSONNE_V25_MEEPLE_K", "CARCASSONNE_USE_FLAT_LEAF",
            "CARCASSONNE_USE_CY_LEAF", "CARCASSONNE_USE_CY_REPR")},
        "args": vars(args),
        "wall_secs": time.time() - t_start,
        "n_jobs": len(jobs),
        "totals": {kk: vv for kk, vv in totals.items() if kk != "mismatches"},
        "n_mismatches": n_bad,
        "mismatches": totals["mismatches"][:args.max_mismatch_report],
        "per_leg": {lg: {kk: vv for kk, vv in st.items() if kk != "mismatches"}
                    | {"n_mismatches": len(st["mismatches"])}
                    for lg, st in sorted(per_leg.items())},
        "bench": bench_out,
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"G4_fair_{args.tag}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))

    print(f"\n[G4] {payload['verdict']}: {n_bad} mismatches over "
          f"{totals['checks']} checks / {totals['decisions']} decisions / "
          f"{totals['solves']} solves / {totals['plies']} plies "
          f"in {payload['wall_secs']:.0f}s -> {path}")
    for lg, st in sorted(payload["per_leg"].items()):
        print(f"    {lg:8} checks={st['checks']:<9} decisions={st['decisions']:<7} "
              f"solves={st['solves']:<6} mismatches={st['n_mismatches']}")
    for m in totals["mismatches"][:10]:
        print("   !", json.dumps(m, default=str)[:300])
    if bench_out:
        print(f"    bench: py {bench_out['py_mean_s_per_move']:.3f} s/move | rust "
              + " | ".join(f"t{t} {v:.3f}s ({bench_out['speedup_vs_py'][t]:.1f}x)"
                           for t, v in bench_out["rs_mean_s_per_move"].items()))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
