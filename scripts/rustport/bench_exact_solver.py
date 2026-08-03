#!/usr/bin/env python3
"""Cost bench for the Rust deep exact-K endgame solver (`carc_core::endgame`).

Measures, on REAL corpus endgame positions, what a solve costs by K and mode:
per-solve wall ms (median / p90 / max), node counts, transposition-table
entries, and PEAK PROCESS RSS — the memory figure that decides how many workers
a box can carry.

Method (the bits that make the numbers mean something):

* **One solve per child process.**  Each measurement forks, seats the position,
  solves once and reports; the parent never accumulates a solved TT.  So the
  RSS figure is `ru_maxrss(child) - ru_maxrss(child before the solve)` — the
  solver's own footprint, not the harness's.
* **Single-threaded per solve.**  The solver is serial; `--workers` only runs
  several *positions* side by side.  Keep it low — a GPU run may own the box.
* **Replay is timed separately** and excluded.  Seating a greedy-suite position
  replays ~140 plies of `RuleBasedPlayer`, which costs far more than the solve
  and has nothing to do with the solver.
* **`RLIMIT_AS` per child** so an uncapped TT at K=6 fails its own child instead
  of taking the box down.  A child that dies on the limit is reported as
  `oom`, never silently dropped.
* **The Python leg runs the same positions in the same harness**, so the
  speedup is a like-for-like ratio and not two different benches divided.

Usage:
  python scripts/rustport/bench_exact_solver.py --n 20 --workers 3 \\
      --out measurement/rust_solver_bench_20260803
"""
from __future__ import annotations

import argparse
import json
import os
import random
import resource
import signal
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

for _k, _v in {
    "CARCASSONNE_V25_CAP": "12",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "1",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "OMP_NUM_THREADS": "1",
    "CUDA_VISIBLE_DEVICES": "",
}.items():
    os.environ.setdefault(_k, _v)

for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "level2",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import carc_rs  # noqa: E402

from reconcile_exact_solver import (  # noqa: E402
    F3_CHAMP, L23_K4_MULTI, L23_POSITIONS, S, k_remaining, load_jsonl,
    seat_actions, seat_greedy,
)

MB = 1024 * 1024


# --------------------------------------------------------------------------
# position selection
# --------------------------------------------------------------------------

def pick_positions(k: int, n: int, seed: int = 4242) -> list[dict]:
    """`n` corpus rows at `k_remaining == k`, cheapest-to-replay first.

    Rows carrying an ACTION SEQUENCE replay in milliseconds; the greedy-suite
    rows need a ~140-ply `RuleBasedPlayer` walk.  Both produce the same class of
    position (the suites are drawn from the same greedy band), so preferring the
    cheap ones costs nothing but wall clock.
    """
    fast: list[dict] = []
    slow: list[dict] = []
    for path, src in ((L23_K4_MULTI, "l23_k4_multisource"),
                      (F3_CHAMP, "f3_roots_k3_champion")):
        for r in load_jsonl(path):
            if int(r["k_remaining"]) == k:
                fast.append({**r, "_source": src})
    for r in load_jsonl(L23_POSITIONS):
        if int(r["k_remaining"]) == k:
            slow.append({**r, "_source": "l23_positions"})
    rng = random.Random(seed + k)
    rng.shuffle(fast)
    rng.shuffle(slow)
    return (fast + slow)[:n]


def seat(rec: dict):
    src = rec["_source"]
    if src == "l23_k4_multisource":
        return seat_actions(rec["seed"], rec["actions"], None)
    if src == "f3_roots_k3_champion":
        return seat_actions(rec["deck_seed"], rec["actions"], rec["ply"])
    return seat_greedy(rec["seed"], rec["ply"])


def pos_id(rec: dict) -> str:
    return f"{rec['_source']}:seed{rec.get('seed', rec.get('deck_seed'))}_ply{rec['ply']}"


# --------------------------------------------------------------------------
# one measurement, in its own process
# --------------------------------------------------------------------------

def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def measure_child(rec: dict, engine: str, mode: str, alphabeta: bool,
                  budget: int, tt_cap: int, as_limit_mb: int, timeout_s: int) -> dict:
    """Runs INSIDE a forked child.  Returns a plain dict through a pipe."""
    out = {"pos": pos_id(rec), "engine": engine, "mode": mode,
           "alphabeta": alphabeta, "k": int(rec["k_remaining"])}
    try:
        resource.setrlimit(resource.RLIMIT_AS, (as_limit_mb * MB, as_limit_mb * MB))
    except (ValueError, OSError):
        pass
    t_replay = time.perf_counter()
    try:
        game, board, ms = seat(rec)
    except MemoryError:
        return {**out, "status": "oom", "phase": "replay"}
    out["replay_ms"] = (time.perf_counter() - t_replay) * 1e3
    if game.string_representation(board) != rec["checksum"]:
        return {**out, "status": "replay_checksum"}
    if game.string_representation(board) != ms.string_repr():
        return {**out, "status": "replay_desync"}

    # SIGALRM covers the PYTHON solve only.  A Rust solve runs under
    # `allow_threads` with the GIL dropped, so a Python-level signal handler
    # cannot run until the FFI call returns — the wall cap for the Rust leg is
    # enforced by the PARENT, which SIGKILLs this child (see `measure`).
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(timeout_s)
    rss0 = _rss_mb()
    t0 = time.perf_counter()
    try:
        if engine == "rust":
            r = ms.solve_endgame(mode=mode, budget=budget, alphabeta=alphabeta,
                                 tt_cap=tt_cap)
            if r is None:
                return {**out, "status": "budget"}
            nodes, tt_entries, value = int(r["nodes"]), int(r["tt_entries"]), r["value"]
            n_opt = len(r["optimal_actions"])
        else:
            if tt_cap:
                os.environ["CARCASSONNE_TT_CAP"] = str(tt_cap)
            r = S.solve(game, board, mode, budget=budget, alphabeta=alphabeta)
            nodes, tt_entries, value = int(r.nodes), None, float(r.value)
            n_opt = len(r.optimal_actions)
    except TimeoutError:
        return {**out, "status": "timeout", "timeout_s": timeout_s}
    except S.BudgetExceeded:
        return {**out, "status": "budget"}
    except MemoryError:
        return {**out, "status": "oom", "phase": "solve"}
    finally:
        signal.alarm(0)
    wall_ms = (time.perf_counter() - t0) * 1e3
    return {**out, "status": "ok", "wall_ms": wall_ms, "nodes": nodes,
            "tt_entries": tt_entries, "value": value, "n_optimal": n_opt,
            "rss_before_mb": rss0, "rss_peak_mb": _rss_mb(),
            "rss_delta_mb": _rss_mb() - rss0}


def measure(job: dict) -> dict:
    """Fork, run `measure_child`, and never let a child failure kill the run.

    The PARENT owns the wall cap: it selects on the result pipe with a deadline
    and SIGKILLs a child that overruns.  This is the only thing that can stop a
    Rust solve — it holds no GIL, so an in-child Python alarm would not fire
    until it had already returned.  The deadline is `timeout_s` plus a small
    allowance for the replay, which is timed but not capped.
    """
    import select

    label = {"pos": pos_id(job["rec"]), "engine": job["engine"],
             "mode": job["mode"], "alphabeta": job["alphabeta"],
             "k": int(job["rec"]["k_remaining"])}
    rfd, wfd = os.pipe()
    pid = os.fork()
    if pid == 0:                                   # child
        os.close(rfd)
        try:
            res = measure_child(**job)
        except BaseException as exc:               # noqa: BLE001
            res = {"status": "EXCEPTION", "error": f"{type(exc).__name__}: {exc}",
                   **label}
        try:
            with os.fdopen(wfd, "w") as fh:
                json.dump(res, fh)
        finally:
            os._exit(0)
    os.close(wfd)
    deadline = time.monotonic() + job["timeout_s"] + 120   # +replay allowance
    chunks: list[bytes] = []
    killed = False
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            os.kill(pid, signal.SIGKILL)
            killed = True
            break
        ready, _, _ = select.select([rfd], [], [], min(left, 5.0))
        if not ready:
            continue
        buf = os.read(rfd, 65536)
        if not buf:
            break
        chunks.append(buf)
    os.close(rfd)
    _, status = os.waitpid(pid, 0)
    raw = b"".join(chunks).decode() or ""
    if killed:
        return {"status": "timeout", "timeout_s": job["timeout_s"],
                "killed_by": "parent_deadline", **label}
    if not raw:
        return {"status": "child_died", "exit_status": status, **label}
    return json.loads(raw)


# --------------------------------------------------------------------------

def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("status") == "ok"]
    out = {
        "n": len(rows), "n_ok": len(ok),
        "n_timeout": sum(1 for r in rows if r.get("status") == "timeout"),
        "n_budget": sum(1 for r in rows if r.get("status") == "budget"),
        "n_oom": sum(1 for r in rows if r.get("status") == "oom"),
        "n_other": sum(1 for r in rows
                       if r.get("status") not in ("ok", "timeout", "budget", "oom")),
    }
    if not ok:
        return out

    def q(vals, p):
        vals = sorted(vals)
        if len(vals) == 1:
            return vals[0]
        i = min(len(vals) - 1, max(0, int(round(p * (len(vals) - 1)))))
        return vals[i]

    ms = [r["wall_ms"] for r in ok]
    nodes = [r["nodes"] for r in ok]
    out.update({
        "wall_ms_median": round(statistics.median(ms), 3),
        "wall_ms_p90": round(q(ms, 0.9), 3),
        "wall_ms_max": round(max(ms), 3),
        "nodes_median": int(statistics.median(nodes)),
        "nodes_p90": int(q(nodes, 0.9)),
        "nodes_max": int(max(nodes)),
        "replay_ms_median": round(statistics.median([r["replay_ms"] for r in ok]), 1),
        "rss_peak_mb_median": round(statistics.median([r["rss_peak_mb"] for r in ok]), 1),
        "rss_peak_mb_max": round(max(r["rss_peak_mb"] for r in ok), 1),
        "rss_delta_mb_median": round(statistics.median([r["rss_delta_mb"] for r in ok]), 1),
        "rss_delta_mb_max": round(max(r["rss_delta_mb"] for r in ok), 1),
    })
    tt = [r["tt_entries"] for r in ok if r.get("tt_entries") is not None]
    if tt:
        out["tt_entries_median"] = int(statistics.median(tt))
        out["tt_entries_max"] = int(max(tt))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=20, help="positions per cell")
    ap.add_argument("--k-clair", type=int, nargs="*", default=[4, 5, 6])
    ap.add_argument("--k-marg", type=int, nargs="*", default=[3, 4])
    ap.add_argument("--k-marg-probe", type=int, nargs="*", default=[5],
                    help="marginalized K run only as a 1-position probe (report "
                         "the timeout if it does not finish)")
    ap.add_argument("--python-k-clair", type=int, nargs="*", default=[4],
                    help="K at which the Python oracle is benched too (the "
                         "rust-vs-python speedup)")
    ap.add_argument("--budget", type=int, default=200_000_000)
    ap.add_argument("--tt-cap", type=int, default=0)
    ap.add_argument("--timeout-s", type=int, default=600)
    ap.add_argument("--as-limit-mb", type=int, default=6000)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tag", default=None,
                    help="names the artifact BENCH_<tag>.json, so a run split "
                         "into cheap and expensive passes does not overwrite itself")
    args = ap.parse_args()

    jobs: list[dict] = []
    cells: list[tuple[str, str, bool, int, int]] = []   # (cell, mode, ab, k, n)
    for k in args.k_clair:
        cells.append((f"rust_clairvoyant_ab_k{k}", "clairvoyant", True, k, args.n))
    for k in args.k_marg:
        cells.append((f"rust_marginalized_k{k}", "marginalized", False, k, args.n))
    for k in args.k_marg_probe:
        cells.append((f"rust_marginalized_k{k}_probe", "marginalized", False, k, 1))
    for k in args.python_k_clair:
        cells.append((f"py_clairvoyant_ab_k{k}", "clairvoyant", True, k, args.n))

    pos_cache: dict[tuple[int, int], list[dict]] = {}
    for cell, mode, ab, k, n in cells:
        key = (k, n)
        if key not in pos_cache:
            pos_cache[key] = pick_positions(k, n)
        engine = "python" if cell.startswith("py_") else "rust"
        for rec in pos_cache[key]:
            jobs.append({"cell": cell, "rec": rec, "engine": engine, "mode": mode,
                         "alphabeta": ab, "budget": args.budget,
                         "tt_cap": args.tt_cap, "as_limit_mb": args.as_limit_mb,
                         "timeout_s": args.timeout_s})

    print(f"[bench_exact_solver] cells={len(cells)} jobs={len(jobs)} "
          f"workers={args.workers} timeout={args.timeout_s}s", flush=True)

    t0 = time.time()
    results: list[dict] = []
    # A tiny hand-rolled scheduler: `measure` forks, so a mp.Pool would nest
    # forks for nothing.  At most `workers` children are alive at once.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(measure, {k: v for k, v in j.items() if k != "cell"}): j
                for j in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            j = futs[fut]
            r = fut.result()
            r["cell"] = j["cell"]
            results.append(r)
            if i % 10 == 0 or r.get("status") != "ok":
                print(f"  {i}/{len(jobs)} {r['cell']} {r.get('status')} "
                      f"{r.get('wall_ms', '')} ({time.time() - t0:.0f}s)", flush=True)

    by_cell: dict[str, list[dict]] = {}
    for r in results:
        by_cell.setdefault(r["cell"], []).append(r)
    summary = {c: summarize(rows) for c, rows in sorted(by_cell.items())}

    # rust-vs-python speedup, position-matched (paired on the same solves)
    speedup = {}
    for k in args.python_k_clair:
        rc, pc = f"rust_clairvoyant_ab_k{k}", f"py_clairvoyant_ab_k{k}"
        rmap = {r["pos"]: r for r in by_cell.get(rc, []) if r.get("status") == "ok"}
        pmap = {r["pos"]: r for r in by_cell.get(pc, []) if r.get("status") == "ok"}
        shared = sorted(set(rmap) & set(pmap))
        if not shared:
            continue
        ratios = [pmap[p]["wall_ms"] / rmap[p]["wall_ms"] for p in shared]
        node_eq = sum(1 for p in shared if pmap[p]["nodes"] == rmap[p]["nodes"])
        val_eq = sum(1 for p in shared if pmap[p]["value"] == rmap[p]["value"])
        speedup[f"k{k}"] = {
            "n_paired": len(shared),
            "median_x": round(statistics.median(ratios), 2),
            "min_x": round(min(ratios), 2),
            "max_x": round(max(ratios), 2),
            "total_py_ms": round(sum(pmap[p]["wall_ms"] for p in shared), 1),
            "total_rs_ms": round(sum(rmap[p]["wall_ms"] for p in shared), 1),
            "aggregate_x": round(sum(pmap[p]["wall_ms"] for p in shared)
                                 / sum(rmap[p]["wall_ms"] for p in shared), 2),
            "node_count_agreement": f"{node_eq}/{len(shared)}",
            "value_agreement": f"{val_eq}/{len(shared)}",
        }

    payload = {
        "bench": "rust_exact_endgame_solver",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
        "carc_rs_version": carc_rs.__version__,
        "host": os.uname().nodename,
        "args": vars(args),
        "summary": summary,
        "speedup_rust_vs_python": speedup,
        "raw": sorted(results, key=lambda r: (r["cell"], r["pos"])),
    }
    out_dir = Path(args.out) if args.out else REPO / "measurement" / "rust_solver_bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"BENCH_{args.tag}.json" if args.tag else "BENCH.json"
    (out_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(json.dumps({"summary": summary, "speedup": speedup}, indent=2))
    print(f"-> {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
