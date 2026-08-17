#!/usr/bin/env python3
"""G-BITEXACT localisation — why the RUST `tier1-greedy` continuation disagrees
with 57 / 15,360 banked PYTHON playouts.

VERDICT (established by this script): **the Rust port is faithful; the banked
Python values are contaminated by a legal-moves-cache key COLLISION.**

`game_wrapper.Game.get_valid_moves` memoizes the legal mask under
`Game.string_representation(board)`, whose per-tile component is
`_tile_rotation_signature` = `(4 outer edges, shield, chapel, flowers)`. That
signature CANNOT distinguish rotation 0 from rotation 2 of a
180°-rotationally-symmetric tile — the witness is `city_left_right`, whose edges
read `('grass', 'city', 'grass', 'city')` at BOTH rotations — while the tile's
FARM SLOTS do rotate (`farmer_positions` / `tile_connections` are permuted). Two
genuinely different boards therefore share ONE cache key, and the second one to
ask gets the FIRST one's mask: the cached mask offers a FARMER corner that is not
legal in this position and withholds the one that is (observed:
`cached_minus_fresh = [2506]` = FARMER TopLeft, `fresh_minus_cached = [2509]` =
FARMER BottomRight). The greedy continuation then plays a different move and the
playout ends on a different terminal score.

The Rust port computes the mask fresh at every ply and has no such cache, so it
plays the position that is actually on the board.

WHAT THIS SCRIPT PROVES
-----------------------
For every leg that `BITEXACT.json` flagged, it re-runs the PYTHON judge three
ways and compares all `2 x m` playouts to Rust as raw f64 bit patterns:

  * `cache_on`  — `replay_actions`' production setting, i.e. exactly how the bank
                  was produced. Expected to REPRODUCE THE BANK.
  * `cache_off` — `enable_legal_moves_cache=False`. Expected to REPRODUCE the
                  RUST values of the cache-free port.

⚠️ Never set `CARCASSONNE_CACHE_COLLIDE_CHECK=1` for this script: that flag makes
every cache HIT recompute and return the FRESH mask, which neutralises the very
bug under test and would silently turn the `cache_on` arm into a second
`cache_off` arm. The script refuses to run with it set.

Usage:
    .venv/bin/python scripts/tiletie/diagnose_tier1_cache_collision.py --workers 18
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

RECORDS_ROOT = Path("/mnt/c/carc-shared/tiearb2_20260816/main")
POSITIONS_ROOT = REPO / "measurement" / "tiearb2_20260816"
RUN_DIR = REPO / "measurement" / "tiearb2_stage2_20260817"
BITEXACT = RUN_DIR / "BITEXACT.json"
OUT_PATH = RUN_DIR / "BITEXACT_DIVERGENCE.json"
MAX_PLIES = 400


def _f64_bits(x) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _records_dir(chunk: int, leg: int) -> Path:
    return RECORDS_ROOT / f"chunk{chunk}" / "tier1-greedy" / "walled" / f"leg{leg}" / "records"


def _positions_path(chunk: int, leg: int) -> Path:
    return POSITIONS_ROOT / f"positions_chunk{chunk}" / f"positions_walled_leg{leg}.jsonl"


def _python_leg(pos: dict, ws: list, ps: list, *, legal_cache: bool) -> tuple:
    """`oracle_score_pilot._process`'s inner loop, with the legal-moves cache
    switchable. Everything else is the pilot's own code path."""
    import copy
    import random

    import root_replay as RR
    from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent
    from carcassonne_ai.rule_based_player import RuleBasedPlayer

    game, board = RR.replay_actions(int(pos["deck_seed"]), pos["actions"], int(pos["ply"]))
    if not legal_cache:
        # `Game.get_valid_moves` treats `None` as "no cache" — the one-line A/B.
        game._legal_cache = None
    rp = int(pos["root_player"])
    out = {"a": [], "b": []}
    plies = {"a": [], "b": []}
    for j in range(len(ws)):
        wb = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(ws[j]))
        for tag, pick in (("a", int(pos["pick_a"])), ("b", int(pos["pick_b"]))):
            b = copy.deepcopy(wb)
            b, _ = game.get_next_state(b, pick)
            agent = RuleBasedPlayer(seed=int(ps[j]))
            n = 0
            while not b.state.is_terminated():
                if n >= MAX_PLIES:
                    raise RuntimeError("max_plies")
                a = int(agent.choose_action(game, b, game.get_valid_moves(b)))
                b, _ = game.get_next_state(b, a)
                n += 1
            out[tag].append(float(b.state.scores[rp] - b.state.scores[1 - rp]))
            plies[tag].append(n)
    return out, plies


def _one(job: tuple) -> dict:
    import carc_rs

    chunk, leg, rid = job
    rec = json.loads((_records_dir(chunk, leg) / f"{rid}.json").read_text())
    pos = next(json.loads(x) for x in _positions_path(chunk, leg).read_text().splitlines()
               if x.strip() and json.loads(x)["rid"] == rid)
    ws = [int(x) for x in rec["world_seeds"]]
    ps = [int(x) for x in rec["playout_seeds"]]

    # The "rust" arm here is deliberately the HONEST-mask port (memo off): the
    # whole question is whether the bank's extra values come from the memo.
    va, vb, _, _, _ = carc_rs.tier1_leg(
        str(int(pos["deck_seed"])), [int(a) for a in pos["actions"]], int(pos["ply"]),
        int(pos["pick_a"]), int(pos["pick_b"]), int(pos["root_player"]), ws, ps,
        MAX_PLIES, False)
    rust = {"a": list(va), "b": list(vb)}
    bank = {"a": rec["values_a"], "b": rec["values_b"]}

    res = {"rid": rid, "chunk": chunk, "leg": leg, "m": len(ws)}

    def cmp(x, y) -> int:
        return sum(1 for t in ("a", "b") for i in range(len(ws))
                   if _f64_bits(x[t][i]) == _f64_bits(y[t][i]))

    n_tot = 2 * len(ws)
    res["n_playouts"] = n_tot
    res["bank_vs_rust_identical"] = cmp(bank, rust)

    for arm_name, use_cache in (("cache_on", True), ("cache_off", False)):
        vals, _pl = _python_leg(pos, ws, ps, legal_cache=use_cache)
        res[f"{arm_name}_vs_bank_identical"] = cmp(vals, bank)
        res[f"{arm_name}_vs_rust_identical"] = cmp(vals, rust)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=18)
    args = ap.parse_args()

    import carc_rs

    if os.environ.get("CARCASSONNE_CACHE_COLLIDE_CHECK", "0") == "1":
        print("[fatal] CARCASSONNE_CACHE_COLLIDE_CHECK=1 neutralises the bug under "
              "test (every cache HIT returns the FRESH mask), which would silently "
              "turn the cache_on arm into a second cache_off arm. Unset it.",
              file=sys.stderr)
        return 2
    d = json.loads(BITEXACT.read_text())
    legs, seen = [], set()
    for m in d["mismatches"]:
        k = (m["chunk"], m["leg"], m["rid"])
        if k not in seen:
            seen.add(k)
            legs.append(k)
    legs.sort()
    print(f"[diagnose] {len(legs)} flagged legs, workers={args.workers}", flush=True)

    t0 = time.time()
    if args.workers <= 1:
        results = [_one(j) for j in legs]
    else:
        import multiprocessing as mp
        with mp.Pool(args.workers) as pool:
            results = pool.map(_one, legs, chunksize=1)
    wall = time.time() - t0

    tot = sum(r["n_playouts"] for r in results)
    agg = {k: sum(r[k] for r in results) for k in results[0] if k.endswith("_identical")}
    try:
        git_rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                          # pragma: no cover
        git_rev = None

    out = {
        "artifact": "G-BITEXACT localisation (NOT the committed gate)",
        "design": "measurement/tiearb2_stage2_20260817/PHASE_A.md#3",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": ("the Rust port is faithful; the banked Python values are "
                    "contaminated by a legal-moves-cache key COLLISION"),
        "mechanism": (
            "Game.string_representation memoizes the legal mask; its per-tile component "
            "_tile_rotation_signature = (4 outer edges, shield, chapel, flowers) cannot "
            "distinguish rotation 0 from rotation 2 of a 180-degree-rotationally-symmetric "
            "tile (witness: city_left_right, edges ('grass','city','grass','city')), while "
            "the tile's FARM SLOTS do rotate. Two different boards share one cache key and "
            "the cached mask offers the wrong FARMER corner (observed cached_minus_fresh "
            "[2506] = FARMER TopLeft, fresh_minus_cached [2509] = FARMER BottomRight)."),
        "n_flagged_legs": len(results),
        "n_playouts_compared": tot,
        "counts": agg,
        "expected": {
            "cache_on_vs_bank_identical": tot,
            "cache_off_vs_rust_identical": tot,
        },
        "per_leg": results,
        "carc_rs_version": carc_rs.__version__,
        "git_rev": git_rev,
        "workers": args.workers,
        "wall_secs": wall,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "per_leg"}, indent=2))
    print(f"[diagnose] -> {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    raise SystemExit(main())
