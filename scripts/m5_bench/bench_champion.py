#!/usr/bin/env python3
"""Single-stream s/move bench for the PRODUCTION champion, from a standalone bundle.

WHAT THIS MEASURES — the wall-clock cost of ONE decision by the champion of record
(``governance/PRODUCTION.yaml`` -> ``puct_priors_v29_bmild_cap8``, deployed as
``FairHeuristicPriorAgent``, PIMC k_dets x sims_per_det), on real mid-game boards the
champion itself reached, with NO parallelism of any kind. One process, one thread,
one decision at a time. This is the number a phone / a laptop / an M5 actually pays.

WHY A BUNDLE — the champion's play path is PURE PYTHON + numpy + pyyaml. No torch, no
Rust, no orchestrator. So it runs anywhere CPython 3.10+ does, from a directory of
files. The bundle is produced by ``scripts/m5_bench/build_bundle.py``, which delegates
the file mapping to ``android/tools/sync_python.py`` — the SAME mapping the Android APK
ships, so a bundle that differs from the measured champion is a build failure, not a
silent drift.

MEASUREMENT ONLY. Nothing here changes a champion, a config, or a claim.

Usage (from the bench directory, after ``setup_m5.sh``)::

    .venv/bin/python bench_champion.py --budgets k1x32                 # smoke, ~1 min
    .venv/bin/python bench_champion.py                                 # full ladder

Output: ``results/bench_champion_<host>_<stamp>.json`` (and a stdout summary).
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# 1. Production leaf env — MUST precede any carcassonne_ai import.             #
#    LITERAL COPY of android_bridge.PROD_ENV (which is itself a literal copy   #
#    of scripts/human_anchor/env_preamble.PROD_ENV). The v2.7/v2.9 leaf reads  #
#    these knobs at LIBRARY IMPORT TIME and champion_factory's verify RAISES   #
#    if they were not set, so this block has to be the first thing that runs.  #
# --------------------------------------------------------------------------- #
PROD_ENV: dict[str, str] = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
for _k, _v in PROD_ENV.items():
    os.environ.setdefault(_k, _v)
# NOT in PROD_ENV and deliberately so: CARCASSONNE_USE_CY_LEAF already defaults ON
# (flat_leaf.py:62, "!= '0'"), so the Cython leaf is used whenever the .so exists and
# the pure-Python path is used when it does not. Both are correct; which one ran is
# MEASURED below (`cython.leaf_active`) rather than assumed.
RESOLVED_ENV: dict[str, str] = {k: os.environ.get(k, "") for k in PROD_ENV}

import argparse  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLE = HERE / "bundle"
# k_dets x sims_per_det. k4x688 = 2752 sims/move = the champion budget of record
# (PRODUCTION.yaml fair_deploy). The three below it are the same WIDTH at 1/4, 1/2 and
# 1/16 depth, so the ladder isolates depth cost; k1x32 is a smoke, not a strength cell.
DEFAULT_BUDGETS = "k1x32,k4x172,k4x344,k4x688"


# --------------------------------------------------------------------------- #
# 2. Bundle wiring — put ONLY the bundle on the path, then PROVE it won.       #
# --------------------------------------------------------------------------- #
def bind_bundle(bundle: Path) -> dict:
    """Make ``bundle`` the import root and point the factory at its bundled YAML.

    The proof at the end is not ceremony: this repo's venv installs
    ``carcassonne_ai`` editable, and an editable install can register a meta-path
    finder that beats ``sys.path``. Benching the repo tree while believing you
    benched the bundle would be a silent, undetectable wrong answer."""
    bundle = bundle.resolve()
    if not (bundle / "carcassonne_ai").is_dir():
        raise SystemExit(f"bench_champion: no carcassonne_ai/ under {bundle}")
    sys.path.insert(0, str(bundle))

    import carcassonne_ai  # noqa: PLC0415

    got = Path(carcassonne_ai.__file__).resolve()
    if bundle not in got.parents:
        raise SystemExit(
            f"bench_champion: FATAL — imported carcassonne_ai from {got}, not from the "
            f"bundle {bundle}. An editable install is shadowing it. Run this from a "
            f"venv that has NOT installed the repo (setup_m5.sh makes one), or unset "
            f"PYTHONPATH.")

    from carcassonne_ai import champion_factory  # noqa: PLC0415

    # The bundled PRODUCTION.yaml is authoritative here: the factory's REPO guess
    # (parents[2] of its own file) points outside the bundle and means nothing.
    bundled_yaml = bundle / "carcassonne_ai" / "data" / "PRODUCTION.yaml"
    if bundled_yaml.is_file():
        champion_factory.PRODUCTION_YAML = bundled_yaml
    # champion_factory._hashers() inserts REPO/scripts/{classical_search,
    # measurement_infra} into sys.path. Those do not exist here; desktop CPython skips
    # a missing path entry silently, and the top-level c5_leaf_override / snapshot
    # modules the bundle ships satisfy the imports. Nothing to shim on macOS/Linux.
    return {
        "bundle": str(bundle),
        "carcassonne_ai": str(got),
        "production_yaml": str(champion_factory.PRODUCTION_YAML),
    }


# --------------------------------------------------------------------------- #
# 3. Provenance — WHICH leaf actually ran (measured, not declared).            #
# --------------------------------------------------------------------------- #
def probe_cython() -> dict:
    """Fire one leaf call through the production dispatch, then report what bound.

    Unlike ``scripts/bench_phone_budget.py`` this does NOT exit on a pure-Python
    fallback: on a fresh M5 with no compiler the pure-Python leaf is a legitimate
    (and interesting) configuration. But the flag is recorded in the output, because
    the two paths differ by ~4.5x (measured 5900XT k1x32, same 6 positions both ways)
    and a number without this flag is uninterpretable."""
    from carcassonne_ai import flat_leaf  # noqa: PLC0415
    from carcassonne_ai.game_wrapper import Game  # noqa: PLC0415
    from carcassonne_ai.virtual_score_v2 import (  # noqa: PLC0415
        DEFAULT_CONFIG,
        virtual_score_v2,
    )

    random.seed(0)
    board = Game().get_init_board()
    virtual_score_v2(board.state, 0, None)      # fires the lazy cy bind

    curve = DEFAULT_CONFIG.v29_meeple_curve
    cy_bound = bool(flat_leaf._CY_FLAT_V2)
    supports_curve = bool(flat_leaf._CY_SUPPORTS_CURVE)
    leaf_active = bool(
        flat_leaf.USE_FLAT_LEAF and flat_leaf.USE_CY_LEAF and cy_bound
        and (curve is None or supports_curve))

    repr_active = False
    try:
        from carcassonne_ai import board_repr  # noqa: PLC0415

        repr_active = bool(board_repr.USE_CY_REPR)
        if repr_active:
            import importlib  # noqa: PLC0415

            importlib.import_module("carcassonne_ai.flat_repr_cy")
    except ImportError:
        repr_active = False

    return {
        "use_flat_leaf": bool(flat_leaf.USE_FLAT_LEAF),
        "use_cy_leaf_flag": bool(flat_leaf.USE_CY_LEAF),
        "cy_module_bound": cy_bound,
        "cy_supports_v29_curve": supports_curve,
        # THE flag to read alongside every s/move number in this file.
        "leaf_active": leaf_active,
        "leaf_path": "cython" if leaf_active else "pure_python",
        # Informational only — the CLASSICAL champion never encodes a board.
        "repr_cy_importable": repr_active,
        "v29_curve": list(curve) if curve is not None else None,
    }


def machine_info() -> dict:
    """Best-effort hardware description. Every probe is guarded; none is required."""
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "system": platform.system(),
        "python": sys.version.split()[0],
        "python_impl": platform.python_implementation(),
        "node": platform.node(),
        "cpu_count": os.cpu_count(),
    }

    def _run(cmd) -> str | None:
        try:
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=10, check=True).stdout.strip()
        except Exception:                          # noqa: BLE001
            return None

    if platform.system() == "Darwin":
        info["cpu_brand"] = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        for key, name in (("hw.memsize", "mem_bytes"),
                          ("hw.perflevel0.physicalcpu", "p_cores"),
                          ("hw.perflevel1.physicalcpu", "e_cores"),
                          ("hw.physicalcpu", "physical_cpus")):
            v = _run(["sysctl", "-n", key])
            if v is not None:
                try:
                    info[name] = int(v)
                except ValueError:
                    info[name] = v
        info["os_version"] = _run(["sw_vers", "-productVersion"])
    else:
        try:
            cpuinfo = Path("/proc/cpuinfo").read_text()
            m = re.search(r"^model name\s*:\s*(.+)$", cpuinfo, re.M)
            if m:
                info["cpu_brand"] = m.group(1).strip()
        except OSError:
            pass
        try:
            m = re.search(r"^MemTotal:\s+(\d+) kB",
                          Path("/proc/meminfo").read_text(), re.M)
            if m:
                info["mem_bytes"] = int(m.group(1)) * 1024
        except OSError:
            pass
        try:
            info["loadavg"] = list(os.getloadavg())
        except OSError:
            pass
    return info


# --------------------------------------------------------------------------- #
# 4. Positions — the root_replay contract, inlined.                           #
# --------------------------------------------------------------------------- #
def load_positions(path: Path, limit: int | None) -> list[dict]:
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    if not rows:
        raise SystemExit(f"bench_champion: empty positions file {path}")
    return rows[:limit] if limit else rows


def replay(Game, row: dict):
    """Reconstruct the board at ``row['ply']``.

    Lossless for ANY policy: the wingedsheep engine consumes the GLOBAL ``random``
    stream in exactly one place — the deck shuffle inside ``get_init_board`` — so
    (deck_seed, action_prefix) determines the position exactly. Contract and proof:
    ``scripts/measurement_infra/root_replay.py``."""
    random.seed(int(row["deck_seed"]))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for a in row["actions"]:
        board, _ = game.get_next_state(board, int(a))
    return game, board


# --------------------------------------------------------------------------- #
# 5. The bench                                                                 #
# --------------------------------------------------------------------------- #
def parse_budgets(spec: str) -> list[tuple[int, int]]:
    out = []
    for tok in spec.split(","):
        tok = tok.strip()
        m = re.fullmatch(r"k(\d+)x(\d+)", tok)
        if not m:
            raise SystemExit(f"bench_champion: bad budget {tok!r}; want e.g. k4x688")
        out.append((int(m.group(1)), int(m.group(2))))
    return out


def _stats(xs: list[float]) -> dict:
    s = sorted(xs)
    n = len(s)

    def q(p: float) -> float:
        # Nearest-rank; n is small (tens) so an interpolating quantile would imply
        # a precision the sample does not have.
        return s[min(n - 1, max(0, int(round(p * n)) - 1))]

    return {
        "n": n,
        "mean_s": sum(s) / n,
        "min_s": s[0],
        "p50_s": q(0.50),
        "p90_s": q(0.90),
        "max_s": s[-1],
    }


def run_budget(k_dets: int, sims: int, positions: list[dict], *, seed: int,
               repeat: int, warmup: int, verify: bool, verbose: bool) -> dict:
    from carcassonne_ai import champion_factory  # noqa: PLC0415
    from carcassonne_ai.game_wrapper import Game  # noqa: PLC0415

    agent_game = Game(enable_legal_moves_cache=True)
    agent = champion_factory.make_production_champion(
        "fair", game=agent_game, seed=seed, sims=sims, k_dets=k_dets,
        exact_endgame=True, verify=verify)

    samples: list[dict] = []
    latched = 0
    todo = [(r, rep) for rep in range(repeat) for r in positions]
    n_warm = min(warmup, len(todo))

    for i, (row, rep) in enumerate(todo):
        _g, board = replay(Game, row)
        # The latch is one-way and per-agent; every bundled position is asserted
        # k_remaining > 2 by make_positions.py, so it must never fire. Clearing it
        # anyway makes that an invariant of the loop rather than of the input file.
        agent._latched = False
        t0 = time.perf_counter()
        action = int(agent.choose_action(board))
        dt = time.perf_counter() - t0
        if getattr(agent, "_latched", False):
            latched += 1
        if i < n_warm:
            continue                       # warm-up: page-in, JIT-free but cache-cold
        samples.append({
            "pos_id": int(row["pos_id"]), "rep": rep, "s": dt,
            "phase": row["phase"], "k_remaining": int(row["k_remaining"]),
            "n_legal": int(row["n_legal"]), "action": action,
        })
        if verbose:
            print(f"    k{k_dets}x{sims} pos {row['pos_id']:>3} "
                  f"{row['phase']:<8} {dt:7.3f}s", flush=True)

    times = [s["s"] for s in samples]
    out = {
        "k_dets": k_dets, "sims_per_det": sims, "total_sims": k_dets * sims,
        # The factory's RESOLVED runtime manifest — hashes and leaf values computed on
        # real boards at construction, not read off a label. main() hoists it out of
        # the first budget (it is identical across budgets) into the top-level result.
        "agent_manifest": getattr(agent, "manifest", None),
        "warmup_discarded": n_warm, "exact_latches": latched,
        "overall": _stats(times),
        "by_phase": {ph: _stats([s["s"] for s in samples if s["phase"] == ph])
                     for ph in sorted({s["phase"] for s in samples})},
        "samples": samples,
    }
    if latched:
        # Loud, because a latched sample is a SOLVER cost mixed into a SEARCH bench.
        out["WARNING"] = (f"{latched} decision(s) latched the exact endgame solver — "
                          f"these are not search samples; the numbers are contaminated.")
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    p.add_argument("--positions", type=Path, default=None,
                   help="default: <bundle>/positions.jsonl")
    p.add_argument("--budgets", default=DEFAULT_BUDGETS,
                   help=f"comma-separated kNxM (default: {DEFAULT_BUDGETS})")
    p.add_argument("--limit", type=int, default=None,
                   help="use only the first N positions")
    p.add_argument("--repeat", type=int, default=1,
                   help="replays of the whole position set per budget")
    p.add_argument("--warmup", type=int, default=2,
                   help="leading decisions discarded per budget (default 2)")
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--no-verify", action="store_true",
                   help="skip champion_factory's runtime leaf proof (NOT recommended)")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--tag", default="", help="free-text label recorded in the JSON")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args(argv)

    binding = bind_bundle(a.bundle)
    positions_path = a.positions or (a.bundle.resolve() / "positions.jsonl")
    if not positions_path.is_file():
        raise SystemExit(f"bench_champion: positions not found: {positions_path}")
    positions = load_positions(positions_path, a.limit)
    budgets = parse_budgets(a.budgets)

    cy = probe_cython()
    mach = machine_info()

    from carcassonne_ai import champion_factory  # noqa: PLC0415

    spec = champion_factory.load_production_spec()

    stamp = time.strftime("%Y%m%dT%H%M%S")
    host = platform.node().split(".")[0] or "unknown"
    out_path = a.out or (HERE / "results" / f"bench_champion_{host}_{stamp}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"bench_champion: {mach.get('cpu_brand') or mach['processor'] or '?'} "
          f"({mach['machine']}, py{mach['python']})")
    print(f"  leaf path : {cy['leaf_path'].upper()}"
          f"{'' if cy['leaf_active'] else '  <-- ~4.5x slower than the Cython path'}")
    print(f"  champion  : {spec.champion_id}  "
          f"(YAML budget k{spec.k_dets}x{spec.sims_per_det})")
    print(f"  positions : {len(positions)} from {positions_path.name}")
    print(f"  budgets   : {a.budgets}  repeat={a.repeat}")
    print(f"  out       : {out_path}")

    result = {
        "schema": "carcassonne-m5-bench/v1",
        "kind": "champion_single_stream_latency",
        "tag": a.tag,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": mach,
        "cython": cy,
        "binding": binding,
        "resolved_env": RESOLVED_ENV,
        "positions_file": str(positions_path),
        "n_positions": len(positions),
        "repeat": a.repeat,
        "seed": a.seed,
        "verify": not a.no_verify,
        "champion": {
            "id": spec.champion_id,
            "yaml_k_dets": spec.k_dets,
            "yaml_sims_per_det": spec.sims_per_det,
            "c_puct": spec.c_puct, "tau_p": spec.tau_p,
            "final_select": spec.final_select, "leaf_quantize": spec.leaf_quantize,
            "value_norm": spec.value_norm,
            "curve": list(spec.curve),
            "bonus_cap": spec.bonus_cap, "opp_bonus_cap": spec.opp_bonus_cap,
            "exact_max_k": spec.exact_max_k,
        },
        "budgets": [],
    }

    def _flush():
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result, indent=2, default=str))
        tmp.replace(out_path)

    _flush()   # harvestable from the first budget onward
    for k_dets, sims in budgets:
        t0 = time.perf_counter()
        print(f"  -> k{k_dets}x{sims} ({k_dets * sims} sims/move) ...", flush=True)
        b = run_budget(k_dets, sims, positions, seed=a.seed, repeat=a.repeat,
                       warmup=a.warmup, verify=not a.no_verify, verbose=a.verbose)
        b["wallclock_s"] = time.perf_counter() - t0
        # The resolved runtime manifest is identical across budgets (same leaf, same
        # config — only the sim counts differ); record it once, at the top level.
        manifest = b.pop("agent_manifest", None)
        result.setdefault("agent_manifest", manifest)
        result["budgets"].append(b)
        o = b["overall"]
        print(f"     mean {o['mean_s']:.3f}s  p50 {o['p50_s']:.3f}s  "
              f"p90 {o['p90_s']:.3f}s  (n={o['n']}, {b['wallclock_s']:.0f}s wall)",
              flush=True)
        _flush()

    print(f"\nbench_champion: wrote {out_path}")
    print(f"  leaf_path={result['cython']['leaf_path']}  "
          f"machine={mach.get('cpu_brand') or mach['machine']}")
    for b in result["budgets"]:
        o = b["overall"]
        print(f"  k{b['k_dets']}x{b['sims_per_det']:<4} "
              f"({b['total_sims']:>5} sims/move): "
              f"mean {o['mean_s']:7.3f} s/move   p90 {o['p90_s']:7.3f} s/move")
    return 0


if __name__ == "__main__":
    sys.exit(main())
