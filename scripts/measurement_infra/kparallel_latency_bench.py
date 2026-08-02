"""k-PARALLEL latency bench (G6 stage 1) — s/move, sequential vs k-process split.

MEASUREMENT INFRASTRUCTURE, not a strength lever. The split is BEHAVIOR-IDENTICAL
(tests/test_kparallel.py proves the chosen action and the pooled root stats match
move-for-move), so the ONLY question it can answer is wall-clock: how much
single-GAME latency does spreading the k determinization worlds over W processes
actually buy? The prize is CL-068's clock closure, which was decided under an
unstated SINGLE-STREAM assumption: k8x1376 = 11008 sims costs ~91% of the clock
sequentially, but a ~3x split would make the strongest measured config
tournament-legal through engineering alone. "~3x not 4x" is the DRAM-latency
prior — this bench exists because that prior must be measured, not assumed.

WHAT IT MEASURES
  For each row (k_dets x sims_per_det, mode) it times ``agent.choose_action(board)``
  on N replayed MID-GAME roots and reports mean + p90 seconds/move. Rows default to
  the production budget k4x688 at workers {seq, 2, 4} plus the CL-068 k8x1376 shape
  at {seq, 4, 8}.

  Roots come from REAL champion games via the lossless (deck_seed, action_sequence)
  replay (``root_replay``) — not synthetic boards — because per-leaf cost grows with
  the number of placed meeples, so an early-game board understates production cost.

  Every row also records the ACTION it chose per root. The parallel rows are asserted
  equal to their sequential sibling's action at the same budget: a latency number
  from a row that played differently would be meaningless, and this makes the
  behavior-identity claim re-verified at production budget on every bench run.

⚠️ RUN IT ALONE. It is a LATENCY measurement on a DRAM-latency-bound workload — a
box with other self-play/eval workers on it will report contention, not the lever.
Census the box first (see CLAUDE.md "Pre-launch process census").

USAGE
  # 2-minute smoke at tiny sims (safe on a busy box — proves the harness, NOT the lever)
  python scripts/measurement_infra/kparallel_latency_bench.py --smoke --out DIR

  # the real thing, on a quiet box
  python scripts/measurement_infra/kparallel_latency_bench.py --out DIR

Writes ``manifest.json`` (fully resolved config — results-discipline rule) and
``rows.csv`` / ``rows.json`` into --out.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "scripts" / "human_anchor"))
sys.path.insert(0, str(_REPO / "scripts" / "measurement_infra"))

import env_preamble  # noqa: E402  MUST precede carcassonne_ai (production leaf env)

import numpy as np  # noqa: E402

from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.champion_factory import make_production_champion  # noqa: E402
from root_replay import replay_actions  # noqa: E402

DEFAULT_GAMES = _REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"

# (k_dets, sims_per_det, [worker counts]) — None in the worker list = SEQUENTIAL.
DEFAULT_ROWS = [
    (4, 688, [None, 2, 4]),      # the production budget (k4x688 = 2752, CL-054)
    (8, 1376, [None, 4, 8]),     # the CL-068 clock-closure shape (11008, CL-060 +49.9)
]
SMOKE_ROWS = [
    (4, 8, [None, 2, 4]),
    (8, 8, [None, 4, 8]),
]


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "-C", str(_REPO), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                   # pragma: no cover
        return "unknown"


def _reseat(agent, meta: dict) -> None:
    """Seat a MIRRORED (Rust) agent on this root, by replay. No-op on Python.

    F-3. The Rust state cannot be built from an arbitrary board — only replayed — so a
    bench whose roots are recorded mid-game positions must reconstruct each one: seat
    on the game's deck, advance the recorded prefix. Outside the timed region.

    ``_move_idx`` stays 0 here, deliberately and unlike ``m5_bench/bench_champion.py``:
    this bench's whole design is a FRESH agent per root so that ``move_idx`` — and
    therefore every per-world determinization seed — is 0 at every root in every row
    (see time_row's docstring). Seating it to the ply would search different worlds
    than the sequential row it is asserted identical to."""
    from carcassonne_ai.mirror_protocol import reseat

    reseat(agent, deck_seed=meta["deck_seed"], actions=meta["prefix"], move_idx=0)


def load_roots(games_path: Path, n_roots: int, ply_lo: float, ply_hi: float,
               stride: int):
    """Replay REAL champion games and return mid-game (game, board, meta) roots.

    ``ply_lo``/``ply_hi`` are FRACTIONS of each game's ply count, so "mid-game" means
    the same phase of play regardless of game length."""
    games = []
    with open(games_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                games.append(json.loads(line))
    if not games:
        raise SystemExit(f"no games in {games_path}")
    roots = []
    gi = 0
    while len(roots) < n_roots and gi < len(games):
        g = games[gi]
        gi += 1
        actions = g["actions"]
        n = len(actions)
        lo, hi = int(n * ply_lo), int(n * ply_hi)
        for ply in range(lo, hi, stride):
            if len(roots) >= n_roots:
                break
            game, board = replay_actions(g["deck_seed"], actions, ply,
                                         include_farm_scalars=False)
            # A forced move never runs a search — it would time a no-op.
            if int(np.flatnonzero(game.get_valid_moves(board)).size) < 2:
                continue
            roots.append((game, board, {"game_id": g.get("game_id"),
                                        "deck_seed": g["deck_seed"], "ply": ply,
                                        "n_plies": n,
                                        # the action prefix, so a Rust mirror can be
                                        # replayed onto this exact root (F-3)
                                        "prefix": [int(x) for x in actions[:ply]]}))
    if len(roots) < n_roots:
        raise SystemExit(f"only found {len(roots)} usable roots (wanted {n_roots})")
    return roots


def time_row(roots, k_dets: int, sims: int, workers, seed_base: int,
             backend: str = "python"):
    """Time one (budget, mode) row over every root.

    Returns ``(secs[], actions[], telem)``. A FRESH agent per root (so ``move_idx``
    — and therefore every per-world seed — is 0 at every root in every row, and the
    modes search identical worlds), but ONE pool for the whole row: the spawn cost is
    a per-GAME cost, not a per-move one, and paying it 30 times would swamp the bench
    with a number the deployed agent never pays.

    ⚠️ ``backend`` CHANGES WHAT ``workers`` MEANS, and that is the F-3 decision this
    bench needed rather than a patch (BACKEND_BYPASS_AUDIT_20260801 §6 F-3). The whole
    point of the bench is the cost of splitting the k determinization worlds — but the
    Rust core splits them across OS THREADS inside one GIL-released call, not across
    SPAWN PROCESSES, and the factory raises on the pair. So on ``backend="rust"`` the
    worker list is read as a THREAD count (``None`` = 1 = the sequential fold), no pool
    is created, and the transport telemetry (a parent-side pickle/dispatch tax that
    does not exist for threads) is simply absent. A rust row and a python row measure
    two different splits of the same worlds: report both, never divide one by the
    other and call it a speedup."""
    secs, actions = [], []
    telem = {"prep_s": 0.0, "dispatch_s": 0.0, "worker_s": 0.0, "moves": 0}
    pool = None
    pool_w = None
    rust = backend == "rust"
    try:
        for i, (game, board, meta) in enumerate(roots):
            agent = make_production_champion(
                "fair", game=game, seed=seed_base + i, sims=sims, k_dets=k_dets,
                verify=False, backend=backend,
                # backend is passed EXPLICITLY in both directions (never omitted on the
                # python leg): omitting it would mean "whatever the factory defaults
                # to", so a flipped default would turn a python row into a rust one.
                **({"rust_threads": workers} if rust
                   else {"parallel_workers": workers}))
            if rust:
                # THE MIRROR PROTOCOL: this root is a recorded mid-game position, so
                # the Rust mirror is replayed onto it (the agent is fresh, so there is
                # nothing to unwind). choose_action hard-raises MirrorDesync if this
                # were skipped — the bench cannot silently time the wrong position.
                _reseat(agent, meta)
            if workers is not None and not rust:
                w = min(workers, k_dets)
                if pool is None:
                    pool, pool_w = agent._ensure_pool(w), w
                else:
                    # Same game_spec/cfg/world_kw across roots in a row, so the
                    # worker state is valid for this agent too.
                    agent._pool, agent._pool_workers = pool, pool_w
            t0 = time.perf_counter()
            a = agent.choose_action(board)
            secs.append(time.perf_counter() - t0)
            actions.append(int(a))
            if workers is not None and not rust:
                telem["prep_s"] += agent.kparallel_prep_secs
                telem["dispatch_s"] += agent.kparallel_dispatch_secs
                telem["worker_s"] += agent.kparallel_worker_secs
                telem["moves"] += agent.kparallel_moves
                agent._pool = None      # the row owns the pool, not the agent
    finally:
        if pool is not None:
            FA._KP_LIVE_POOLS.discard(pool)
            pool.terminate()
            pool.join()
    return secs, actions, telem


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--games-jsonl", default=str(DEFAULT_GAMES),
                   help="root_replay games jsonl (real champion games)")
    p.add_argument("--n-moves", type=int, default=30,
                   help="roots timed per row (>=30 for the mean/p90 to mean anything)")
    p.add_argument("--ply-lo", type=float, default=0.35)
    p.add_argument("--ply-hi", type=float, default=0.70)
    p.add_argument("--stride", type=int, default=11,
                   help="plies between sampled roots within one game (decorrelate)")
    p.add_argument("--seed-base", type=int, default=90_000,
                   help="agent seed for root i is seed_base + i (same in every row)")
    p.add_argument("--backend", choices=("inherit", "python", "rust", "auto"),
                   default="inherit",
                   help="which ENGINE runs the search, and therefore WHAT THE WORKER "
                        "COUNTS MEAN. inherit (DEFAULT) = champion_factory's own "
                        "default, today python. python: workers = SPAWN "
                        "PROCESSES. rust (carc_rs): workers = OS THREADS folded inside "
                        "one GIL-released call, no pool, no transport tax — the Rust "
                        "core has no process split and the factory raises on the pair. "
                        "auto = the PRODUCTION.yaml fair_deploy backend. The two "
                        "backends are two different splits: label the rows, never "
                        "divide one by the other.")
    p.add_argument("--smoke", action="store_true",
                   help="tiny sims + few roots: proves the harness, NOT the lever")
    p.add_argument("--rows", default=None,
                   help="override rows as 'k:sims:w1,w2,...;k:sims:...' (w=0 => sequential)")
    args = p.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # One resolution for the whole run (rows must not disagree about the engine).
    from carcassonne_ai.mirror_protocol import resolve_execution
    backend = resolve_execution(args.backend)["backend"]

    if args.rows:
        rows_spec = []
        for chunk in args.rows.split(";"):
            k, s, ws = chunk.split(":")
            rows_spec.append((int(k), int(s),
                              [None if int(w) == 0 else int(w) for w in ws.split(",")]))
    else:
        rows_spec = SMOKE_ROWS if args.smoke else DEFAULT_ROWS
    n_moves = 4 if (args.smoke and args.n_moves == 30) else args.n_moves

    roots = load_roots(Path(args.games_jsonl), n_moves,
                       args.ply_lo, args.ply_hi, args.stride)

    results = []
    for k_dets, sims, worker_list in rows_spec:
        baseline_actions = None
        for workers in worker_list:
            if backend == "rust":
                label = f"rust_t{1 if workers is None else workers}"
            else:
                label = "sequential" if workers is None else f"parallel_w{workers}"
            t_row = time.perf_counter()
            secs, actions, telem = time_row(roots, k_dets, sims, workers,
                                            args.seed_base, backend=backend)
            arr = np.asarray(secs, dtype=float)
            rec = {
                "k_dets": k_dets, "sims_per_det": sims,
                "total_sims": k_dets * sims,
                "mode": label,
                "backend": backend,
                # PROCESSES on python, OS THREADS on rust — see time_row's docstring.
                "split_unit": "os_threads" if backend == "rust" else "spawn_processes",
                "workers": workers,
                "worlds_per_worker": (None if workers is None
                                      else -(-k_dets // min(workers, k_dets))),
                "n_moves": int(arr.size),
                "mean_s_per_move": float(arr.mean()),
                "p90_s_per_move": float(np.percentile(arr, 90)),
                "median_s_per_move": float(np.median(arr)),
                "min_s_per_move": float(arr.min()),
                "max_s_per_move": float(arr.max()),
                "row_wall_s": time.perf_counter() - t_row,
                "secs": [float(x) for x in arr],
                "actions": actions,
            }
            if workers is not None and backend != "rust":
                # parent-side prep + (dispatch - slowest in-worker chunk) = the
                # transport + scheduling tax the split has to pay for itself against.
                moves = max(1, telem["moves"])
                rec["searched_moves"] = telem["moves"]
                rec["transport_ms_per_move"] = 1000.0 * (
                    telem["prep_s"] + telem["dispatch_s"] - telem["worker_s"]) / moves
                rec["worker_s_per_move"] = telem["worker_s"] / moves
            if baseline_actions is None:
                baseline_actions = actions
            else:
                # BEHAVIOR IDENTITY, re-verified at THIS budget on THESE roots.
                rec["actions_match_sequential"] = (actions == baseline_actions)
                if actions != baseline_actions:
                    bad = [i for i, (x, y) in enumerate(zip(actions, baseline_actions))
                           if x != y]
                    raise SystemExit(
                        f"FAIL — {label} at k{k_dets}x{sims} disagreed with the "
                        f"sequential row at root(s) {bad}. The split is supposed to be "
                        f"behavior-identical; a latency number from a row that played "
                        f"differently is meaningless.")
            seqrec = next((r for r in results
                           if r["k_dets"] == k_dets and r["sims_per_det"] == sims
                           and r["workers"] is None), None)
            if seqrec is not None and workers is not None:
                rec["speedup_vs_sequential_mean"] = (
                    seqrec["mean_s_per_move"] / rec["mean_s_per_move"])
                rec["speedup_vs_sequential_p90"] = (
                    seqrec["p90_s_per_move"] / rec["p90_s_per_move"])
            results.append(rec)
            print(f"{label:>14s}  k{k_dets}x{sims:<5d} "
                  f"mean {rec['mean_s_per_move']:.3f}s  p90 {rec['p90_s_per_move']:.3f}s"
                  + (f"  speedup {rec.get('speedup_vs_sequential_mean', 1.0):.2f}x"
                     if workers is not None else "")
                  + (f"  transport {rec['transport_ms_per_move']:.1f}ms"
                     if "transport_ms_per_move" in rec else ""),
                  flush=True)

    probe = make_production_champion("fair", seed=0, verify=False, backend=backend)
    manifest = {
        "bench": "kparallel_latency_bench",
        "purpose": "single-GAME latency of the behavior-identical k-process split "
                   "of the fair champion's determinized search (G6 stage 1)",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_rev": _git_rev(),
        "host": platform.node(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "smoke": bool(args.smoke),
        "smoke_note": ("SMOKE — tiny sims, few roots. Proves the harness only; the "
                       "numbers are NOT a latency verdict." if args.smoke else None),
        "leaf_env": dict(env_preamble.RESOLVED),
        "champion_manifest": probe.manifest,
        "roots": {
            "source": str(args.games_jsonl),
            "recipe": "root_replay.replay_actions (lossless deck_seed+action_sequence)",
            "n_moves": n_moves,
            "ply_fraction_window": [args.ply_lo, args.ply_hi],
            "stride": args.stride,
            "forced_moves_skipped": True,
            # the action prefix is carried on each root for the Rust mirror replay; it
            # is reconstructible from (deck_seed, ply) and would bloat the manifest
            "refs": [{k: v for k, v in m.items() if k != "prefix"}
                     for _g, _b, m in roots],
        },
        "agent": {
            "builder": "champion_factory.make_production_champion('fair', verify=False)",
            "backend": backend,
            "backend_requested": args.backend,
            "split_unit": ("os_threads (rust_threads) — the Rust core has no spawn "
                           "split" if backend == "rust" else
                           "spawn_processes (parallel_workers)"),
            "mirror_protocol": ("start_game_from_seed + advance(prefix) per root, "
                                "move_idx seated to 0" if backend == "rust" else None),
            "seed_rule": "seed_base + root_index (identical across rows)",
            "seed_base": args.seed_base,
            "fresh_agent_per_root": True,
            "pool_prewarmed_before_the_clock": True,
            "exact_endgame": True,
        },
        "rows_requested": [{"k_dets": k, "sims_per_det": s, "workers": w}
                           for k, s, w in rows_spec],
        "results": results,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (out / "rows.json").write_text(json.dumps(results, indent=2))
    with open(out / "rows.csv", "w") as fh:
        cols = ["k_dets", "sims_per_det", "total_sims", "mode", "workers",
                "worlds_per_worker", "n_moves", "mean_s_per_move", "p90_s_per_move",
                "median_s_per_move", "speedup_vs_sequential_mean",
                "speedup_vs_sequential_p90", "transport_ms_per_move",
                "actions_match_sequential"]
        fh.write(",".join(cols) + "\n")
        for r in results:
            fh.write(",".join("" if r.get(c) is None else str(r.get(c, ""))
                              for c in cols) + "\n")
    print(f"\nwrote {out}/manifest.json, rows.csv, rows.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
