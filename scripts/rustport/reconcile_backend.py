"""rustport **P6 / gate G6** — the DESKTOP BACKEND SWAP: `rust_agent.RustFairAgent`
vs the deployed Python champion, 100% action agreement + the honest speed multiplier.

    .venv/bin/python scripts/rustport/reconcile_backend.py --help

G4 gated the Rust CORE against the Python champion by driving `carc_rs.FairAgentRs`
directly.  G6 gates the thing a caller actually gets: the ADAPTER
(`src/carcassonne_ai/rust_agent.py`) built through
`champion_factory.make_production_champion(..., backend="rust")` — the same entry
point production and the phone use — against
`make_production_champion(..., parallel_workers=None)`, the sequential k-loop that
is byte-for-byte the deployed champion.  What is new versus G4 is everything
between the harness and the core: config translation, the mirror lifecycle, the
`advance` choke point, the latch/solver counters, and the factory's own semantic
guards run against `carc_rs` outputs.

LEGS (`--leg`, repeatable, or `all`):

  agree   DECK-PAIRED full games at the champion budget (k8x1376).  One deck per
          game, BOTH agents answer EVERY ply from the same position, the PYTHON
          action drives the timeline.  Compared per decision: the action, the
          pooled `(N, W)` accumulators as raw f64 bits in pool insertion order,
          and the forced/exact/latched/timeout flags + solver node count; then
          the end-of-game latch counters.  `--reconcile-games N` runs the first
          N games with `CARC_RS_RECONCILE=1`, which additionally hard-asserts the
          Rust mirror's `string_repr()` against `game.string_representation()`
          BEFORE every decision and AFTER every applied action — so a mirror
          drift is a raised `MirrorDesync`, never a silent one.

  bench   THE DEPLOY-PATH MULTIPLIER.  The comparison that answers "how much
          faster is every eval from now on" is against the path evals actually
          run today: the Cython-leaf Python champion (`CARCASSONNE_USE_CY_LEAF=1`,
          flat leaf, Cython repr), NOT pure Python.  Two regimes, same positions
          and same config both sides:
            * SINGLE-STREAM  — one decision at a time, py-sequential vs rust t1
              (and any other `--threads-list` value);
            * GAME-PARALLEL  — `--bench-workers` (default 8) concurrent game
              workers, which is how an eval is really run; measured as aggregate
              decisions/s, because that is the quantity a 400-game eval divides
              its wall clock by.

DECK SEEDS.  `--deck-base 98000000000` + i.  This is a THROWAWAY FUZZ RANGE, not
a registered claim band (`governance/BAND_REGISTRY.csv`): G6 is an identity gate,
it produces no strength number, and nothing here may ever be quoted as an elo.
The whole point of the gate is that the Rust backend owes NO elo — CL-071's
precedent — because it plays the identical move.

Artifacts land in `measurement/rustport_p6/`.
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

# ⚠️ fair_common applies the production leaf env and MUST precede carcassonne_ai
# (the P4 war story: `production_leaf_cfg` starts from an import-frozen
# DEFAULT_CONFIG, so without this the "oracle" is a cap-5 leaf).
import fair_common as F  # noqa: E402

import carc_rs  # noqa: E402
import trace_search as T  # noqa: E402
from _g0_common import environment  # noqa: E402
from carcassonne_ai import rust_agent  # noqa: E402
from carcassonne_ai.champion_factory import make_production_champion  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p6"
LEGS = ["agree", "bench"]

# The fuzz-only deck range. NOT a band in governance/BAND_REGISTRY.csv.
DECK_BASE = 98_000_000_000


# --------------------------------------------------------------------------- #
# Leg construction                                                             #
# --------------------------------------------------------------------------- #
def rs_agent(game, *, sims: int, k_dets: int, seed: int, threads: int = 1):
    """The RUST champion THROUGH THE FACTORY — the surface a caller gets.

    `verify=True` runs the factory's semantic guards, and with `backend="rust"`
    the leaf VALUE PANEL is re-evaluated through `carc_rs` (champion_factory
    `verify_leaf(..., backend="rust")`), so a wrong Rust leaf raises here rather
    than quietly playing."""
    agent = make_production_champion(
        "fair", game=game, seed=int(seed), sims=int(sims), k_dets=int(k_dets),
        exact_endgame=True, verify=True, exact_budget=F.EXACT_BUDGET,
        backend="rust", rust_threads=int(threads))
    if agent.manifest.get("backend", {}).get("name") != "rust":
        raise SystemExit("factory did not stamp the rust backend on the manifest")
    return agent


def rs_decision(agent, board) -> dict:
    """One ADAPTER decision, reduced to `fair_common`'s comparable record."""
    action = int(agent.choose_action(board))
    m = agent.last_move()
    return {
        "action": action,
        "pooled": [(int(a), int(n), int(w)) for a, n, w in m["pooled"]],
        "forced": bool(m["forced"]),
        "exact": bool(m["exact"]),
        "latched": bool(m["latched"]),
        "timeout": bool(m["timeout"]),
        "solver_nodes": int(m["solver_nodes"]),
        "last_pooled_visits": [],
    }


def _blank() -> dict:
    return {"games": 0, "plies": 0, "decisions": 0, "checks": 0,
            "action_checks": 0, "action_agree": 0,
            "py_secs": 0.0, "rs_secs": 0.0, "py_moves": 0, "rs_moves": 0,
            "exact_moves": 0, "solver_nodes": 0, "reconcile_asserts": 0,
            "mismatches": []}


def _merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if k == "mismatches":
            dst[k].extend(v)
        elif isinstance(v, (int, float)) and k in dst:
            dst[k] += v


# --------------------------------------------------------------------------- #
# The agreement leg — one deck-paired full game                                #
# --------------------------------------------------------------------------- #
def _agree_job(job: dict) -> dict:
    """One deck. Both champions answer every ply; the PYTHON action drives.

    Applying the Python action (rather than each side its own) keeps the two
    timelines provably identical even when a mismatch is only recorded — and the
    loop breaks on the first action disagreement, because past a fork the two
    agents are no longer answering the same question."""
    out = _blank()
    sims, k = int(job["sims"]), int(job["k_dets"])
    aseed, dseed = int(job["agent_seed"]), int(job["deck_seed"])
    reconcile = bool(job["reconcile"])
    if reconcile:
        os.environ[rust_agent.RECONCILE_ENV] = "1"
    else:
        os.environ.pop(rust_agent.RECONCILE_ENV, None)

    random.seed(dseed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    pa = F.py_agent(game, sims=sims, k_dets=k, seed=aseed)
    ra = rs_agent(Game(enable_legal_moves_cache=True), sims=sims, k_dets=k,
                  seed=aseed, threads=int(job["threads"]))
    # The mirror is seated from the REAL deck this board was dealt — no RNG
    # assumption, and it is digest-checked immediately under reconcile mode.
    ra.start_game(board)
    if reconcile:
        ra.check_sync(board, "start")
        out["reconcile_asserts"] += 1

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
            r = rs_decision(ra, board)
            out["rs_secs"] += time.perf_counter() - t1
            out["py_moves"] += 1
            out["rs_moves"] += 1
            out["decisions"] += 1
            out["checks"] += len(F.DECISION_FIELDS)
            out["action_checks"] += 1
            out["action_agree"] += int(p["action"] == r["action"])
            out["mismatches"].extend(
                F.compare_decision(p, r, f"{job['label']}@ply{n}"))
            if p["action"] != r["action"]:
                break                       # forked; the rest is not comparable
            board, _ = game.get_next_state(board, p["action"])
            # THE choke point. Under reconcile mode the post-state is checked too,
            # so both "before I think" and "after I move" are asserted.
            ra.advance(p["action"], board_after=board if reconcile else None)
            if reconcile:
                out["reconcile_asserts"] += 2   # pre-decision + post-advance
            n += 1

    s = ra.stats()
    out["checks"] += 4
    for name, a, b in (("exact_moves", int(pa.exact_moves), int(s["exact_moves"])),
                       ("latch_k", pa.latch_k, s["latch_k"]),
                       ("n_timeouts", int(pa.n_timeouts), int(s["n_timeouts"])),
                       ("solver_nodes", int(pa.solver_nodes), int(s["solver_nodes"]))):
        if a != b:
            out["mismatches"].append({"tag": job["label"], "field": f"counter/{name}",
                                      "py": a, "rs": b})
    # The prefix clock the eval harness reads off the agent (champ_prefix_ms_per_move).
    out["exact_moves"] = int(pa.exact_moves)
    out["solver_nodes"] = int(pa.solver_nodes)
    out["games"] = 1
    out["plies"] = n
    out["game"] = {
        "label": job["label"], "deck_seed": dseed, "agent_seed": aseed,
        "plies": n, "reconcile": reconcile,
        "terminal": bool(game.get_game_ended(board, 0)) or max_moves is not None,
        "scores": [int(x) for x in board.state.scores],
        "action_agree": out["action_agree"], "action_checks": out["action_checks"],
        "py_s_per_move": out["py_secs"] / max(1, out["py_moves"]),
        "rs_s_per_move": out["rs_secs"] / max(1, out["rs_moves"]),
        "rs_prefix_moves": int(s["prefix_moves"]),
        "rs_prefix_s_per_move": (s["prefix_secs"] / s["prefix_moves"]
                                 if s["prefix_moves"] else 0.0),
        "py_prefix_moves": int(pa.heur_moves),
        "exact_moves": out["exact_moves"], "solver_nodes": out["solver_nodes"],
        "n_mismatches": len(out["mismatches"]),
    }
    ra.close()
    pa.close()
    game.clear_caches()
    return out


def run_job(job: dict) -> dict:
    out = _agree_job(job)
    out["leg"] = job["leg"]
    return out


# --------------------------------------------------------------------------- #
# The bench leg — the DEPLOY-PATH multiplier                                   #
# --------------------------------------------------------------------------- #
def _bench_positions(n: int, deck_base: int, plies: list[int]) -> list[dict]:
    """`(deck_seed, ply)` roots: a mix of opening/mid/late boards, since per-leaf
    cost grows with placed meeples and an all-opening bench flatters both legs."""
    return [{"deck_seed": deck_base + 900_000 + i, "ply": p}
            for i in range(n) for p in plies]


def _seat_py(deck_seed: int, ply: int):
    """Replay `ply` GREEDY-free plies by taking the first legal action — a cheap,
    deterministic way to reach a realistic board without needing a record."""
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    actions = []
    rng = random.Random(int(deck_seed) ^ 0x5EED)
    for _ in range(ply):
        if game.get_game_ended(board, 0):
            break
        legal = [i for i, v in enumerate(game.get_valid_moves(board)) if v]
        a = int(rng.choice(legal))
        actions.append(a)
        board, _ = game.get_next_state(board, a)
    return game, board, actions


def _bench_one(payload: dict) -> dict:
    """`--bench-moves` decisions from one root on ONE leg. Runs in a worker for
    the game-parallel regime and inline for the single-stream regime."""
    leg = payload["leg"]
    sims, k = int(payload["sims"]), int(payload["k_dets"])
    n_moves = int(payload["moves"])
    game, board, actions = _seat_py(payload["deck_seed"], payload["ply"])
    t_setup = time.perf_counter()
    if leg == "py":
        agent = F.py_agent(game, sims=sims, k_dets=k, seed=7)
        agent._move_idx = payload["ply"]
    else:
        agent = rs_agent(Game(enable_legal_moves_cache=True), sims=sims, k_dets=k,
                         seed=7, threads=int(payload["threads"]))
        random.seed(int(payload["deck_seed"]))
        g0 = Game(enable_legal_moves_cache=True)
        agent.start_game(g0.get_init_board())
        for a in actions:
            agent.advance(int(a))
        g0.clear_caches()
        # Same move counter both legs: the determinization seeds derive from it,
        # so an unseated Rust agent would draw different worlds and the timing
        # comparison would not be like-for-like.
        agent._move_idx = int(payload["ply"])
    setup_s = time.perf_counter() - t_setup

    moves = 0
    t0 = time.perf_counter()
    if leg == "py":
        with F.PoolSpy() as spy:
            while moves < n_moves and not game.get_game_ended(board, 0):
                p = F.py_decision(agent, board, spy)
                board, _ = game.get_next_state(board, p["action"])
                moves += 1
    else:
        while moves < n_moves and not game.get_game_ended(board, 0):
            a = int(agent.choose_action(board))
            board, _ = game.get_next_state(board, a)
            agent.advance(a)
            moves += 1
    secs = time.perf_counter() - t0
    agent.close()
    game.clear_caches()
    return {"leg": leg, "threads": payload.get("threads", 0),
            "deck_seed": payload["deck_seed"], "ply": payload["ply"],
            "moves": moves, "secs": secs, "setup_s": setup_s,
            "s_per_move": secs / max(1, moves)}


def _deploy_dispatch_probe() -> dict:
    """PROVE, at runtime, that the Python leg really is the DEPLOYED path.

    "X times faster than the deployed path" is only honest if the leg we timed
    dispatched to the compiled leaf. A label is not evidence (the R1/R7 lesson),
    so this reads the live module attributes inside `production_leaf_dispatch()`
    — the context every timed Python decision runs in — and records whether the
    Cython extensions actually imported."""
    from carcassonne_ai import board_repr, flat_leaf

    try:
        from carcassonne_ai import flat_leaf_cy  # noqa: F401
        cy_leaf_importable = True
    except Exception as e:                        # pragma: no cover - build issue
        cy_leaf_importable = f"NOT IMPORTABLE: {e}"
    with T.production_leaf_dispatch():
        effective = bool(flat_leaf.USE_CY_LEAF)
    probe = {
        "flat_leaf.USE_CY_LEAF (inside production_leaf_dispatch)": effective,
        "flat_leaf.USE_FLAT_LEAF": bool(flat_leaf.USE_FLAT_LEAF),
        "board_repr.USE_CY_REPR": bool(board_repr.USE_CY_REPR),
        "flat_leaf_cy importable": cy_leaf_importable,
        "CARCASSONNE_USE_CY_LEAF": os.environ.get("CARCASSONNE_USE_CY_LEAF",
                                                  "(unset -> default ON)"),
        "CARCASSONNE_USE_FLAT_LEAF": os.environ.get("CARCASSONNE_USE_FLAT_LEAF"),
        "CARCASSONNE_USE_CY_REPR": os.environ.get("CARCASSONNE_USE_CY_REPR"),
    }
    if not (effective and cy_leaf_importable is True):
        raise SystemExit(
            "the PYTHON bench leg is NOT the deployed Cython path — a multiplier "
            f"measured against it would overstate the win: {probe}")
    return probe


def bench(args) -> dict:
    """Single-stream AND game-parallel, both legs, same roots and same config.

    The Python leg is the DEPLOYED path — `make_production_champion` with
    `parallel_workers=None` under the production leaf env, i.e. the Cython flat
    leaf and Cython repr — because "X times faster" is only an honest answer if
    X is measured against what we run today."""
    dispatch = _deploy_dispatch_probe()      # refuses to time a non-deployed leg
    roots = _bench_positions(args.bench_roots, args.deck_base,
                             [int(x) for x in args.bench_plies.split(",")])
    tlist = [int(x) for x in args.threads_list.split(",")]

    single = []
    for root in roots:
        single.append(_bench_one({"leg": "py", "sims": args.sims,
                                  "k_dets": args.k_dets, "moves": args.bench_moves,
                                  **root}))
        for t in tlist:
            single.append(_bench_one({"leg": "rs", "threads": t, "sims": args.sims,
                                      "k_dets": args.k_dets,
                                      "moves": args.bench_moves, **root}))

    def _mean(leg, threads=None):
        rows = [r for r in single if r["leg"] == leg
                and (threads is None or r["threads"] == threads)]
        if not rows:
            return 0.0
        return sum(r["secs"] for r in rows) / max(1, sum(r["moves"] for r in rows))

    py_single = _mean("py")
    rs_single = {str(t): _mean("rs", t) for t in tlist}

    # --- game-parallel: W concurrent workers, aggregate decisions/s ---------- #
    par = {}
    if args.bench_workers > 0:
        W = int(args.bench_workers)
        pw_roots = _bench_positions(1, args.deck_base + 1,
                                    [int(x) for x in args.bench_plies.split(",")])
        jobs_py, jobs_rs = [], []
        for i in range(W):
            root = dict(pw_roots[i % len(pw_roots)])
            root["deck_seed"] = int(root["deck_seed"]) + i
            jobs_py.append({"leg": "py", "sims": args.sims, "k_dets": args.k_dets,
                            "moves": args.bench_par_moves, **root})
            jobs_rs.append({"leg": "rs", "threads": 1, "sims": args.sims,
                            "k_dets": args.k_dets, "moves": args.bench_par_moves,
                            **root})
        ctx = mp.get_context("fork")
        for name, jobs in (("py", jobs_py), ("rs", jobs_rs)):
            t0 = time.perf_counter()
            with ctx.Pool(W) as pool:
                rows = list(pool.map(_bench_one, jobs))
            wall = time.perf_counter() - t0
            n = sum(r["moves"] for r in rows)
            par[name] = {"workers": W, "wall_secs": wall, "decisions": n,
                         "decisions_per_s": n / wall if wall else 0.0,
                         "wall_s_per_decision": wall / max(1, n),
                         "rows": rows}
        if par["rs"]["decisions_per_s"] > 0 and par["py"]["decisions_per_s"] > 0:
            par["speedup_rs_over_py"] = (par["rs"]["decisions_per_s"]
                                         / par["py"]["decisions_per_s"])

    return {
        "config": {"sims_per_det": args.sims, "k_dets": args.k_dets,
                   "total_sims": args.sims * args.k_dets,
                   "roots": roots, "moves_per_root": args.bench_moves,
                   "python_leg": "make_production_champion(parallel_workers=None) "
                                 "under the production leaf env = the DEPLOYED "
                                 "Cython-leaf path",
                   "leaf_dispatch": dispatch},
        "single_stream": {
            "rows": single,
            "py_s_per_move": py_single,
            "rs_s_per_move": rs_single,
            "speedup_rs_over_py": {t: (py_single / v) for t, v in rs_single.items()
                                   if v > 0},
        },
        "game_parallel": par,
    }


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--leg", action="append", default=None,
                    help=f"repeatable; one of {LEGS} or 'all'")
    ap.add_argument("--sims", type=int, default=1376, help="sims PER determinization")
    ap.add_argument("--k-dets", type=int, default=8)
    ap.add_argument("--threads", type=int, default=1,
                    help="Rust world threads inside the agreement leg")
    ap.add_argument("--threads-list", default="1,8",
                    help="Rust thread counts for the single-stream bench")
    ap.add_argument("--games", type=int, default=100, help="agreement-leg games")
    ap.add_argument("--reconcile-games", type=int, default=10,
                    help="how many of them run with CARC_RS_RECONCILE=1")
    ap.add_argument("--deck-base", type=int, default=DECK_BASE,
                    help="THROWAWAY fuzz deck seeds; not a registered band")
    ap.add_argument("--agent-seed-base", type=int, default=101)
    ap.add_argument("--max-moves", type=int, default=None,
                    help="cap plies per game (None = play to termination)")
    ap.add_argument("--workers", type=int, default=14, help="game-level fork pool")
    ap.add_argument("--bench-roots", type=int, default=2)
    ap.add_argument("--bench-plies", default="0,40,80")
    ap.add_argument("--bench-moves", type=int, default=3)
    ap.add_argument("--bench-workers", type=int, default=8)
    ap.add_argument("--bench-par-moves", type=int, default=3)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--max-mismatch-report", type=int, default=200)
    args = ap.parse_args(argv)
    args.leg = args.leg or ["all"]
    legs = LEGS if "all" in args.leg else args.leg

    t_start = time.time()
    k = F.knobs()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    progress = OUTDIR / f"G6_progress_{args.tag}.jsonl"

    jobs = []
    if "agree" in legs:
        for i in range(args.games):
            jobs.append({
                "fn": "agree", "leg": "agree", "label": f"agree/{i:03d}",
                "deck_seed": args.deck_base + i,
                "agent_seed": args.agent_seed_base + i,
                "sims": args.sims, "k_dets": args.k_dets,
                "threads": args.threads, "max_moves": args.max_moves,
                "reconcile": i < args.reconcile_games,
            })

    print(f"[G6] {len(jobs)} agreement games (reconcile on {args.reconcile_games}) "
          f"k{args.k_dets}x{args.sims}={args.k_dets * args.sims} "
          f"workers={args.workers} rust_threads={args.threads}", flush=True)

    totals = _blank()
    games: list[dict] = []
    done = 0
    if jobs:
        with progress.open("a") as fh:
            if args.workers > 1:
                ctx = mp.get_context("fork")
                with ctx.Pool(args.workers) as pool:
                    for out in pool.imap_unordered(run_job, jobs, chunksize=1):
                        done += 1
                        out.pop("leg")
                        g = out.pop("game")
                        games.append(g)
                        fh.write(json.dumps(g, default=str) + "\n")
                        fh.flush()
                        _merge(totals, out)
                        print(f"  {done}/{len(jobs)} games, "
                              f"{totals['action_agree']}/{totals['action_checks']} "
                              f"actions agree, {len(totals['mismatches'])} mismatches "
                              f"({time.time() - t_start:.0f}s)", flush=True)
            else:
                for job in jobs:
                    out = run_job(job)
                    done += 1
                    out.pop("leg")
                    g = out.pop("game")
                    games.append(g)
                    fh.write(json.dumps(g, default=str) + "\n")
                    fh.flush()
                    _merge(totals, out)
                    print(f"  {done}/{len(jobs)} games, "
                          f"{totals['action_agree']}/{totals['action_checks']} agree",
                          flush=True)

    bench_out = bench(args) if "bench" in legs else None

    n_bad = len(totals["mismatches"])
    agree_rate = (totals["action_agree"] / totals["action_checks"]
                  if totals["action_checks"] else None)
    ok = (n_bad == 0
          and (agree_rate == 1.0 if totals["action_checks"] else True))
    payload = {
        "gate": "G6/backend",
        "verdict": "PASS" if ok else "FAIL",
        "env": environment(),
        "carc_rs": rust_agent.backend_provenance(),
        "knobs": {kk: vv for kk, vv in k.items() if kk != "leaf_cfg"},
        "leaf_env": {kk: os.environ.get(kk) for kk in (
            "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP",
            "CARCASSONNE_V25_DROP_THREE_OPEN", "CARCASSONNE_V29_MEEPLE_CURVE",
            "CARCASSONNE_V25_MEEPLE_K", "CARCASSONNE_USE_FLAT_LEAF",
            "CARCASSONNE_USE_CY_LEAF", "CARCASSONNE_USE_CY_REPR")},
        "deck_range": {
            "base": args.deck_base, "n": args.games,
            "note": "THROWAWAY FUZZ SEEDS — not a registered claim band "
                    "(governance/BAND_REGISTRY.csv). G6 is an identity gate and "
                    "produces no strength number.",
        },
        "args": vars(args),
        "wall_secs": time.time() - t_start,
        "n_games": len(games),
        "totals": {kk: vv for kk, vv in totals.items() if kk != "mismatches"},
        "action_agreement": agree_rate,
        "reconcile_games": sum(1 for g in games if g["reconcile"]),
        "reconcile_asserts": totals["reconcile_asserts"],
        "n_mismatches": n_bad,
        "mismatches": totals["mismatches"][:args.max_mismatch_report],
        "games": games,
        "bench": bench_out,
    }
    path = OUTDIR / f"G6_backend_{args.tag}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))

    print(f"\n[G6] {payload['verdict']}: {n_bad} mismatches over {totals['checks']} "
          f"checks / {totals['decisions']} decisions / {len(games)} games "
          f"in {payload['wall_secs']:.0f}s -> {path}")
    if totals["action_checks"]:
        print(f"    action agreement: {totals['action_agree']}/"
              f"{totals['action_checks']} = {100.0 * agree_rate:.4f}%")
        print(f"    reconcile: {payload['reconcile_games']} games, "
              f"{totals['reconcile_asserts']} digest asserts, 0 raised")
    for m in totals["mismatches"][:10]:
        print("   !", json.dumps(m, default=str)[:300])
    if bench_out:
        ss = bench_out["single_stream"]
        print(f"    single-stream: py(deployed cython) {ss['py_s_per_move']:.3f} s/move"
              + "".join(f" | rust t{t} {v:.3f}s ({ss['speedup_rs_over_py'][t]:.2f}x)"
                        for t, v in ss["rs_s_per_move"].items()))
        gp = bench_out["game_parallel"]
        if gp:
            print(f"    W{gp['py']['workers']} game-parallel: py "
                  f"{gp['py']['decisions_per_s']:.4f} dec/s | rust "
                  f"{gp['rs']['decisions_per_s']:.4f} dec/s "
                  f"({gp.get('speedup_rs_over_py', 0):.2f}x)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
