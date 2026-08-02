#!/usr/bin/env python3
"""WIRING IDENTITY GATE for `--backend rust` in `scripts/classical_search/eval_puct_priors.py`
— BOTH SIDES on the Rust clairvoyant engine.

WHAT THIS GATES, AND WHAT IT DOES NOT.  The SEARCH is already gated bit-exact by
`gate_clairvoyant.py` (candidate knobs) and `gate_clairvoyant_opponent.py`
(champion flag-OFF knobs, this harness's own leaf).  This gate proves the narrower
and different thing: that the HARNESS WIRING — the `--backend` switch on both
prefixes, and the two-mirror `start_game()` / `advance()` protocol threaded through
`_play_one` — did not change what the harness PLAYS.  A correct engine reached
through a wrong harness is still a wrong number.

The specific hazard it exists for: `_play_one` used to track a SINGLE mirror (the
candidate).  With the opponent converted there are TWO, and each must see EVERY
applied action of BOTH seats.  A mirror that only saw its own moves would answer
from a stale board — `check_sync` turns that into a hard `MirrorDesync`, but only
a full-game run exercises it.

METHOD.  The SAME deck-paired seeds through the SAME harness twice, changing
exactly one flag, requiring identical `GameResult` records on every play-determined
field:

    score_p0 / score_p1 / diff / moves        the game itself
    deck_hash                                 both legs really saw the same decks
    cand_/champ_prefix_moves, _exact_moves    the SAME search/solve split per side
    latch_k                                   the endgame latched at the same ply
    cand_/champ_timeouts, game_timeout        no leg silently degraded

Two full games ending on identical scores after an identical number of moves, with
an identical per-side prefix/exact split and an identical latch ply, cannot have
diverged in an action — one different action reshapes the rest of the game.
Timing fields (`elapsed_s`, `*_secs`) are excluded: they are what is supposed to
differ, and they are read out separately as the realised speedup.

`--backend python` is the reference leg, so this also proves the escape hatch.

    .venv/bin/python scripts/rustport/gate_eval_puct_priors_backend.py \
        --games 4 --cand-sims 2750 --opp-sims 2750 --workers 4
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
EVAL = REPO / "scripts" / "classical_search" / "eval_puct_priors.py"
OUT = REPO / "measurement" / "rustport_p6" / "G6_eval_puct_priors_wiring.json"

# Play-determined fields. Anything timing-shaped is excluded on purpose.
IDENTITY_FIELDS = ("seed", "a_seat", "cand_sims", "champ_sims",
                   "score_p0", "score_p1", "diff", "won_by_cand", "drew",
                   "moves", "deck_hash",
                   "cand_prefix_moves", "cand_exact_moves", "cand_timeouts",
                   "champ_prefix_moves", "champ_exact_moves", "champ_timeouts",
                   "latch_k", "game_timeout")


def _run_leg(backend: str, args, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-u", str(EVAL),
           "--candidate", "puct", "--opponent", "puct",
           "--cand-sims", str(args.cand_sims),
           "--champ-sims", str(args.opp_sims),
           "--exact-k", str(args.exact_k),
           "--n", str(args.games), "--paired",
           "--seed-start", str(args.seed_start),
           "--workers", str(args.workers),
           "--backend", backend,
           "--out-root", str(root), "--out-subdir", "leg",
           "--no-results-csv"]
    print(f"\n[{backend}] {' '.join(cmd[2:])}", flush=True)
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    dt = time.perf_counter() - t0
    if p.returncode != 0:
        print(p.stdout[-4000:])
        print(p.stderr[-4000:])
        raise SystemExit(f"{backend} leg failed rc={p.returncode}")
    print(f"[{backend}] leg finished in {dt:.1f}s", flush=True)
    rows = []
    for f in sorted((root / "leg").glob("*.json")):
        if f.name in ("summary.json", "manifest.json"):
            continue
        rows.append(json.loads(f.read_text()))
    summ = json.loads((root / "leg" / "summary.json").read_text())
    man = json.loads((root / "leg" / "manifest.json").read_text())
    return rows, summ, man, dt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_eval_puct_priors_backend")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--cand-sims", type=int, default=2750)
    ap.add_argument("--opp-sims", type=int, default=2750)
    ap.add_argument("--exact-k", type=int, default=2)
    ap.add_argument("--seed-start", type=int, default=96950000000,
                    help="THROWAWAY band — this is a wiring gate, not a strength "
                         "measurement; it writes no results.csv row and claims no "
                         "band in governance/BAND_REGISTRY.csv")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--scratch", default="/tmp/gate_eval_puct_priors")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    scratch = Path(args.scratch)
    if scratch.exists():
        shutil.rmtree(scratch)

    py_rows, py_summ, py_man, py_dt = _run_leg("python", args, scratch / "py")
    rs_rows, rs_summ, rs_man, rs_dt = _run_leg("rust", args, scratch / "rs")

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

    # The manifests must AGREE with what actually ran — a rust leg whose manifest
    # says the opponent stayed python is a provenance bug even if play is identical.
    py_be, rs_be = py_man["config"]["backend"], rs_man["config"]["backend"]
    prov_ok = (py_be["candidate_engine"] == py_be["opponent_engine"] == "python"
               and rs_be["candidate_engine"] == rs_be["opponent_engine"] == "rust")
    if not prov_ok:
        mismatches.append({"field": "manifest.backend", "python": py_be,
                           "rust": rs_be})

    ok = bool(keys) and not mismatches
    c_py = py_summ.get("cand_prefix_ms_per_move")
    c_rs = rs_summ.get("cand_prefix_ms_per_move")
    o_py = py_summ.get("champ_prefix_ms_per_move")
    o_rs = rs_summ.get("champ_prefix_ms_per_move")
    out = {
        "gate": "eval_puct_priors --backend rust wiring identity (BOTH SIDES)",
        "question": "does routing BOTH clairvoyant PUCT prefixes through "
                    "--backend rust change what the ablation harness PLAYS? (the "
                    "searches are already gated bit-exact; this gates the harness "
                    "wiring and the TWO-mirror protocol)",
        "search_gates": ["measurement/rustport_p6/GATE_CLAIRVOYANT.json",
                         "measurement/rustport_p6/GATE_CLAIRVOYANT_OPPONENT.json"],
        "config": {"games": args.games, "paired": True,
                   "candidate": "puct", "opponent": "puct",
                   "cand_sims": args.cand_sims, "opp_sims": args.opp_sims,
                   "exact_k": args.exact_k, "seed_start": args.seed_start,
                   "workers": args.workers},
        "identity_fields": list(IDENTITY_FIELDS),
        "excluded": "every timing field (elapsed_s, *_secs) — those are meant to "
                    "differ",
        "manifest_provenance_ok": prov_ok,
        "games_compared": len(keys),
        "field_checks": compared,
        "mismatches": mismatches,
        "verdict": "PASS" if ok else "FAIL",
        "timing": {
            "python_leg_wall_s": round(py_dt, 1),
            "rust_leg_wall_s": round(rs_dt, 1),
            "wall_speedup": round(py_dt / rs_dt, 2) if rs_dt else None,
            "cand_prefix_ms_per_move_python": c_py,
            "cand_prefix_ms_per_move_rust": c_rs,
            "cand_side_speedup": round(c_py / c_rs, 2) if c_py and c_rs else None,
            "opp_prefix_ms_per_move_python": o_py,
            "opp_prefix_ms_per_move_rust": o_rs,
            "opp_side_speedup": round(o_py / o_rs, 2) if o_py and o_rs else None,
            "solver_secs_per_game_python": py_summ.get("solver_secs_per_game"),
            "solver_secs_per_game_rust": rs_summ.get("solver_secs_per_game"),
            "note": "wall_speedup is the FARM-REALISED number for this cell and is "
                    "smaller than the per-side search speedups because the exact-K "
                    "clairvoyant tail stays Python on BOTH sides (carc_rs exposes "
                    "only the FAIR marginalized solve). Both legs ran at the same "
                    "--workers.",
        },
        "python_summary": {k: py_summ.get(k) for k in
                           ("n", "W", "D", "L", "winrate", "elo", "avg_diff",
                            "paired_mean_margin")},
        "rust_summary": {k: rs_summ.get(k) for k in
                         ("n", "W", "D", "L", "winrate", "elo", "avg_diff",
                          "paired_mean_margin")},
        "band_note": "THROWAWAY seed band, --no-results-csv: a wiring gate, not a "
                     "strength measurement. No results.csv row, no claim id, no "
                     "band consumed.",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(keys)} deck-paired games, {compared} field "
          f"checks, {len(mismatches)} mismatches")
    print(f"  candidate ms/move python {c_py} -> rust {c_rs} "
          f"({out['timing']['cand_side_speedup']}x)")
    print(f"  opponent  ms/move python {o_py} -> rust {o_rs} "
          f"({out['timing']['opp_side_speedup']}x)")
    print(f"  farm wall {py_dt:.1f}s -> {rs_dt:.1f}s "
          f"({out['timing']['wall_speedup']}x realised at W{args.workers})")
    print(f"  -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
