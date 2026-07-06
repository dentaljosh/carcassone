#!/usr/bin/env python3
"""Phase 1.1 equal-time normalization bench — CYTHON candidate leaf (re-bench).

Follow-up to scripts/classical_search/bench_equal_time.py after wiring the PUCT
heuristic-prior CANDIDATE leaf to the CYTHON flat leaf (flat_leaf_cy):
  * float candidate -> flat_leaf.flat_virtual_score_v2_float  (pre-round Cython;
    full sub-integer prior resolution)
  * int   candidate -> flat_leaf.flat_virtual_score_v2        (Cython int leaf;
    int-rounds, loses sub-point resolution but cheapest)

The earlier bench capped the candidate at 800 sims because it evaluated the leaf
via the PURE-PYTHON leaf_score_float (~30x slower). This measures the new Cython
candidate: single-thread ms/move for the champion h6400 (re-measured) and for
BOTH candidate variants at a wide sims ladder, and reports the candidate `sims`
that matches h6400 wall-clock within +-10%. Net-free CPU, single OS thread.
MEASUREMENT ONLY — no champion/PRODUCTION change.

Usage:
  nice -n 19 .venv/bin/python -u scripts/classical_search/bench_equal_time_cy.py \
      --n-positions 20 --champ-sims 6400 \
      --cand-sims-float 800,2000,4000,6000,8000,10000 \
      --cand-sims-int   800,2000,4000,6000,8000,10000
"""
from __future__ import annotations

import os

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
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse
import json
import platform
import random
import socket
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.mcts import HeuristicMCTS  # noqa: E402


def verify_cython_active() -> dict:
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

    g = Game()
    random.seed(0)
    b = g.get_init_board()
    _ = virtual_score_v2(b.state, 0, None)
    # fire the float path too so its Cython entry binds
    _ = flat_leaf.flat_virtual_score_v2_float(b.state, 0, None, False)
    curve = DEFAULT_CONFIG.v29_meeple_curve
    active = (
        flat_leaf.USE_FLAT_LEAF
        and flat_leaf.USE_CY_LEAF
        and bool(flat_leaf._CY_FLAT_V2)
        and bool(flat_leaf._CY_FLAT_V2_FLOAT)
        and (curve is None or bool(flat_leaf._CY_SUPPORTS_CURVE))
    )
    info = {
        "use_flat_leaf": bool(flat_leaf.USE_FLAT_LEAF),
        "use_cy_leaf": bool(flat_leaf.USE_CY_LEAF),
        "cy_int_bound": bool(flat_leaf._CY_FLAT_V2),
        "cy_float_bound": bool(flat_leaf._CY_FLAT_V2_FLOAT),
        "cy_supports_v29_curve": bool(flat_leaf._CY_SUPPORTS_CURVE),
        "v29_curve": list(curve) if curve is not None else None,
        "cython_leaf_active": bool(active),
    }
    if not active:
        print(json.dumps(info, indent=2))
        raise SystemExit("FATAL: Cython flat-leaf (int+float) NOT active — ms/move would be garbage.")
    return info


def build_positions(n: int, ply_lo: int = 30, ply_hi: int = 140, seed0: int = 9_100_000):
    out = []
    plies = np.linspace(ply_lo, ply_hi, n).round().astype(int)
    for i, ply in enumerate(plies):
        seed = seed0 + i
        random.seed(seed)
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        depth = 0
        for _ in range(int(ply)):
            if g.get_game_ended(b, 0) != 0.0:
                break
            legal = np.flatnonzero(g.get_valid_moves(b))
            b, _ = g.get_next_state(b, int(random.choice(legal)))
            depth += 1
        if g.get_game_ended(b, 0) == 0.0:
            n_legal = int(g.get_valid_moves(b).sum())
            out.append({"seed": seed, "ply": depth, "n_legal": n_legal, "board": b})
    return out


def _time_ms(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1e3


def bench_champion(positions, sims: int, c: float) -> list[float]:
    ms = []
    for p in positions:
        m = HeuristicMCTS(game=Game(enable_legal_moves_cache=True), simulations=sims,
                          c=c, seed=1, heur_leaf="v2_7")
        m.clear()
        ms.append(_time_ms(lambda: m.best_action(p["board"])))
    return ms


def bench_candidate(positions, sims: int, cfg: HeuristicPriorConfig) -> list[float]:
    ms = []
    for p in positions:
        a = HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg, simulations=sims, seed=1)
        a.clear()
        ms.append(_time_ms(lambda: a.best_action(p["board"])))
    return ms


def _median(xs):
    return float(np.median(xs)) if xs else float("nan")


def _match(cand_curve: dict, champ_med: float, tol: float) -> dict:
    lo, hi = champ_med * (1 - tol), champ_med * (1 + tol)
    within = [s for s, m in cand_curve.items() if lo <= m <= hi]
    closest = min(cand_curve, key=lambda s: abs(cand_curve[s] - champ_med))
    sims_sorted = sorted(cand_curve)
    interp = None
    for a, bnd in zip(sims_sorted, sims_sorted[1:]):
        ma, mb = cand_curve[a], cand_curve[bnd]
        if (ma - champ_med) * (mb - champ_med) <= 0 and mb != ma:
            frac = (champ_med - ma) / (mb - ma)
            interp = int(round(a + frac * (bnd - a)))
            break
    chosen = within[0] if within else closest
    return {
        "champ_median_ms": round(champ_med, 1),
        "band_ms": [round(lo, 1), round(hi, 1)],
        "within_band_sims": within,
        "closest_sims": closest,
        "closest_median_ms": round(cand_curve[closest], 1),
        "interp_sims_for_exact_match": interp,
        "chosen_candidate_sims": chosen,
    }


def run_ladder(positions, sims_list, quantize, c_puct, tau_p, champ_med, payload, out):
    cfg = HeuristicPriorConfig(c_puct=c_puct, tau_p=tau_p,
                               leaf_quantize=quantize, final_select="Q")
    curve = {}
    for sims in sims_list:
        t0 = time.perf_counter()
        ms = bench_candidate(positions, sims, cfg)
        med = _median(ms)
        curve[sims] = med
        payload["results"][f"candidate_{quantize}_s{sims}"] = {
            "sims": sims, "median_ms": round(med, 1),
            "mean_ms": round(float(np.mean(ms)), 1),
            "p90_ms": round(float(np.percentile(ms, 90)), 1),
            "ratio_to_champ": round(med / champ_med, 3),
            "per_pos_ms": [round(x, 1) for x in ms],
        }
        print(f"[cy-equal-time] candidate {quantize} sims={sims}: median {med:.0f} ms/move "
              f"(ratio {med/champ_med:.2f}x champ) [{time.perf_counter()-t0:.0f}s]", flush=True)
        out.write_text(json.dumps(payload, indent=2))
    return curve


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-positions", type=int, default=20)
    ap.add_argument("--champ-sims", type=int, default=6400)
    ap.add_argument("--champ-c", type=float, default=3.0)
    ap.add_argument("--cand-sims-float", default="800,2000,4000,6000,8000,10000")
    ap.add_argument("--cand-sims-int", default="800,2000,4000,6000,8000,10000")
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--tol", type=float, default=0.10)
    ap.add_argument("--skip-int", action="store_true")
    ap.add_argument("--out", default=str(
        Path(__file__).resolve().parent.parent.parent
        / "measurement" / "classical_search" / "equal_time_raw_cy.json"))
    args = ap.parse_args()

    sims_float = [int(x) for x in args.cand_sims_float.split(",") if x]
    sims_int = [int(x) for x in args.cand_sims_int.split(",") if x]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"[cy-equal-time] host={socket.gethostname()} cpu={platform.processor() or platform.machine()}")
    prov = verify_cython_active()
    print(f"[cy-equal-time] cython leaf ACTIVE (int+float): {prov['cython_leaf_active']}")

    positions = build_positions(args.n_positions)
    print(f"[cy-equal-time] {len(positions)} positions "
          f"(plies {min(p['ply'] for p in positions)}-{max(p['ply'] for p in positions)}, "
          f"legal {min(p['n_legal'] for p in positions)}-{max(p['n_legal'] for p in positions)})")

    payload = {
        "kind": "equal_time_bench_cython",
        "host": socket.gethostname(),
        "cpu": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "provenance": prov,
        "note": "candidate leaf now runs the CYTHON flat leaf (float=pre-round, int=rounded)",
        "champion": {"agent": "HeuristicMCTS", "leaf": "v2.9 Bmild_cap8 (cython)",
                     "sims": args.champ_sims, "c": args.champ_c},
        "candidate": {"agent": "HeuristicPriorAgent (PUCT+heur priors, CYTHON leaf)",
                      "c_puct": args.c_puct, "tau_p": args.tau_p, "final_select": "Q"},
        "n_positions": len(positions),
        "positions": [{"seed": p["seed"], "ply": p["ply"], "n_legal": p["n_legal"]} for p in positions],
        "results": {},
    }

    # champion (re-measure)
    t0 = time.perf_counter()
    champ_ms = bench_champion(positions, args.champ_sims, args.champ_c)
    champ_med = _median(champ_ms)
    payload["results"][f"champion_h{args.champ_sims}"] = {
        "sims": args.champ_sims, "median_ms": round(champ_med, 1),
        "mean_ms": round(float(np.mean(champ_ms)), 1),
        "p90_ms": round(float(np.percentile(champ_ms, 90)), 1),
        "per_pos_ms": [round(x, 1) for x in champ_ms],
    }
    print(f"[cy-equal-time] champion h{args.champ_sims}: median {champ_med:.0f} ms/move "
          f"(mean {np.mean(champ_ms):.0f}, p90 {np.percentile(champ_ms, 90):.0f}) "
          f"[{time.perf_counter()-t0:.0f}s]", flush=True)
    out.write_text(json.dumps(payload, indent=2))

    # candidate float ladder
    curve_float = run_ladder(positions, sims_float, "float", args.c_puct, args.tau_p,
                             champ_med, payload, out)
    payload["match_float"] = _match(curve_float, champ_med, args.tol)
    out.write_text(json.dumps(payload, indent=2))

    curve_int = {}
    if not args.skip_int:
        curve_int = run_ladder(positions, sims_int, "int", args.c_puct, args.tau_p,
                               champ_med, payload, out)
        payload["match_int"] = _match(curve_int, champ_med, args.tol)
        out.write_text(json.dumps(payload, indent=2))

    print("\n=== CY EQUAL-TIME MATCH ===")
    lo, hi = champ_med * (1 - args.tol), champ_med * (1 + args.tol)
    print(f"champion h{args.champ_sims}: {champ_med:.0f} ms/move (band {lo:.0f}-{hi:.0f})")
    for label, curve, match in (("float", curve_float, payload.get("match_float")),
                                ("int", curve_int, payload.get("match_int"))):
        if not curve:
            continue
        print(f"-- candidate {label} (cython) --")
        for s in sorted(curve):
            flag = " <= within band" if s in match["within_band_sims"] else (
                " <= closest" if s == match["closest_sims"] else "")
            print(f"  s={s}: {curve[s]:.0f} ms/move ({curve[s]/champ_med:.2f}x){flag}")
        if match["interp_sims_for_exact_match"]:
            print(f"  interpolated exact-match sims ~ {match['interp_sims_for_exact_match']}")
        print(f"  CHOSEN candidate sims = {match['chosen_candidate_sims']} "
              f"({curve[match['chosen_candidate_sims']]:.0f} ms/move)")
    print(f"[cy-equal-time] DONE -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
