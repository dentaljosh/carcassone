#!/usr/bin/env python3
"""IDENTITY GATE for the `--backend rust` wiring of `eval_fair_puct.py`.

WHAT THIS GATES, AND WHAT IT DOES NOT.  rustport G4/G6 already proved the ENGINE
bit-exact (0/305,515 leaf checks; 14,384/14,384 identical actions over 100 full
games).  This gate proves something different and narrower: that the WIRING added
on 2026-08-02 — the `--backend` switch, the `_MarginalizedHandoff` replacement,
and the `start_game()` / `advance()` mirror protocol threaded through `_play_one`
— did not change what the flagship elo harness plays.  A correct engine reached
through a wrong harness is still a wrong number, and every elo row we own comes
out of this file.

METHOD.  Run the SAME deck-paired seeds through the SAME harness twice, changing
exactly one flag, and require the two runs' `GameResult` records to be identical
on every play-determined field:

    score_p0 / score_p1 / diff / moves   -> the game itself
    deck_hash                            -> the two legs really saw the same decks
    champ_prefix_moves / champ_exact_moves / latch_k
                                         -> the SAME search/solve split, i.e. the
                                            endgame latched at the same ply and
                                            the solver owned the same decisions
    rung_moves                           -> the frozen Python rung is untouched

Two full games that end on identical scores after an identical number of moves,
with an identical prefix/exact split and an identical latch ply, cannot have
diverged in an action — a single different action reshapes the rest of the game.
Timing fields (`elapsed_s`, `*_secs`) are DELIBERATELY excluded: they are the
thing that is supposed to differ.

`--backend python` is the reference leg, so this gate also proves the escape
hatch still works.

    .venv/bin/python scripts/rustport/gate_eval_fair_puct_backend.py \
        --games 10 --sims 344 --k-dets 4 --workers 10
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"
OUT = REPO / "measurement" / "rustport_p6" / "G6_eval_fair_puct_wiring.json"

# Play-determined fields. Anything timing-shaped is excluded on purpose.
IDENTITY_FIELDS = ("score_p0", "score_p1", "diff", "moves", "deck_hash",
                   "champ_prefix_moves", "champ_exact_moves", "latch_k",
                   "rung_moves", "won_by_champ", "drew", "a_seat", "seed")


def _run_leg(backend: str, args, root: Path) -> list[dict]:
    root.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-u", str(EVAL),
           "--info", "fair", "--opponent", args.opponent,
           "--sims", str(args.sims), "--k-dets", str(args.k_dets),
           "--exact-k", str(args.exact_k), "--rung-sims", str(args.rung_sims),
           "--n", str(args.games), "--paired",
           "--seed-start", str(args.seed_start),
           "--workers", str(args.workers),
           "--backend", backend,
           "--out-root", str(root), "--out-subdir", "leg"]
    print(f"\n[{backend}] {' '.join(cmd[2:])}", flush=True)
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    dt = time.perf_counter() - t0
    if p.returncode != 0:
        print(p.stdout[-4000:]); print(p.stderr[-4000:])
        raise SystemExit(f"{backend} leg failed rc={p.returncode}")
    print(f"[{backend}] leg finished in {dt:.1f}s", flush=True)
    rows = []
    for f in sorted((root / "leg").glob("*.json")):
        if f.name in ("summary.json", "manifest.json"):
            continue
        rows.append(json.loads(f.read_text()))
    summ = json.loads((root / "leg" / "summary.json").read_text())
    return rows, summ, dt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_eval_fair_puct_backend")
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--sims", type=int, default=344)
    ap.add_argument("--k-dets", type=int, default=4)
    ap.add_argument("--exact-k", type=int, default=2)
    ap.add_argument("--rung-sims", type=int, default=800)
    ap.add_argument("--opponent", default="h800")
    ap.add_argument("--seed-start", type=int, default=98000000000)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--scratch", default="/tmp/gate_eval_fair_puct")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    scratch = Path(args.scratch)
    if scratch.exists():
        shutil.rmtree(scratch)

    py_rows, py_summ, py_dt = _run_leg("python", args, scratch / "py")
    rs_rows, rs_summ, rs_dt = _run_leg("rust", args, scratch / "rs")

    py_by = {(r["seed"], r["a_seat"]): r for r in py_rows}
    rs_by = {(r["seed"], r["a_seat"]): r for r in rs_rows}
    keys = sorted(set(py_by) | set(rs_by))

    mismatches, compared = [], 0
    for k in keys:
        a, b = py_by.get(k), rs_by.get(k)
        if a is None or b is None:
            mismatches.append({"key": list(k), "missing_in":
                               "rust" if b is None else "python"})
            continue
        for f in IDENTITY_FIELDS:
            compared += 1
            if a.get(f) != b.get(f):
                mismatches.append({"key": list(k), "field": f,
                                   "python": a.get(f), "rust": b.get(f)})

    ok = bool(keys) and not mismatches
    # The realised end-to-end multiplier ON THIS CELL, measured rather than modelled.
    py_champ = py_summ.get("champ_prefix_ms_per_move")
    rs_champ = rs_summ.get("champ_prefix_ms_per_move")
    rung_ms = py_summ.get("rung_ms_per_move")
    out = {
        "gate": "G6/eval_fair_puct wiring identity",
        "question": "does routing the flagship elo harness through --backend rust "
                    "change what it PLAYS? (the engine is already G4/G6-gated; this "
                    "gates the harness wiring and the mirror protocol)",
        "config": {"games": args.games, "paired": True, "sims": args.sims,
                   "k_dets": args.k_dets, "exact_k": args.exact_k,
                   "rung_sims": args.rung_sims, "opponent": args.opponent,
                   "seed_start": args.seed_start, "workers": args.workers},
        "identity_fields": list(IDENTITY_FIELDS),
        "excluded": "every timing field (elapsed_s, *_secs) — those are meant to differ",
        "games_compared": len(keys),
        "field_checks": compared,
        "mismatches": mismatches,
        "verdict": "PASS" if ok else "FAIL",
        "timing": {
            "python_leg_wall_s": round(py_dt, 1),
            "rust_leg_wall_s": round(rs_dt, 1),
            "wall_speedup": round(py_dt / rs_dt, 2) if rs_dt else None,
            "champ_prefix_ms_per_move_python": py_champ,
            "champ_prefix_ms_per_move_rust": rs_champ,
            "champ_side_speedup": (round(py_champ / rs_champ, 2)
                                   if py_champ and rs_champ else None),
            "rung_ms_per_move": rung_ms,
            "note": "wall_speedup is the FARM-REALISED number for this cell and is "
                    "smaller than champ_side_speedup because the frozen Python rung "
                    "does not convert. Both legs ran at the same --workers.",
        },
        "python_summary": {k: py_summ.get(k) for k in
                           ("n", "W", "D", "L", "winrate", "elo", "avg_diff",
                            "paired_mean_margin")},
        "rust_summary": {k: rs_summ.get(k) for k in
                         ("n", "W", "D", "L", "winrate", "elo", "avg_diff",
                          "paired_mean_margin")},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(keys)} deck-paired games, {compared} field "
          f"checks, {len(mismatches)} mismatches")
    print(f"  champ ms/move python {py_champ} -> rust {rs_champ} "
          f"({out['timing']['champ_side_speedup']}x) | rung {rung_ms} ms/move")
    print(f"  farm wall {py_dt:.1f}s -> {rs_dt:.1f}s "
          f"({out['timing']['wall_speedup']}x realised at W{args.workers})")
    print(f"  -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
