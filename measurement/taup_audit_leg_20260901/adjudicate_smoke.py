#!/usr/bin/env python3
"""Adjudicate a SMOKE_ cell FROM ITS OWN EMITTED MANIFEST.

⛔⛔ THE R1 DEFECT CLASS THIS EXISTS TO PREVENT. A smoke that prints "looks fine"
without reading what the harness actually WROTE proves nothing: the whole point of
a pre-launch smoke on a candidate-only knob is that the knob leaves no other
trace — no leaf hash moves, no elo is read, and a dose parsed and dropped on the
floor produces a perfectly healthy-looking run. So this reads the SMOKE_ cell's
`manifest.json` and runs the SAME `leg_lib` gates the real cells will face.

⛔ NONZERO EXIT ON EMPTY. A missing out-dir, a missing manifest, a manifest that
parses to nothing, or a cell with zero played games all EXIT NONZERO. An
adjudicator that exits 0 because it found nothing to adjudicate is the defect
wearing a green light — `run_cells.sh` treats this script's exit code as the
launch gate, so silence here must never read as consent.

⛔ THE SMOKE EMITS NO OUTCOME KEY. Nothing in the JSON this writes is a result:
it carries structural keys only (which gates passed, at which addresses, with
which resolved values). n=8 games decides nothing and must never be read.

USAGE
    python adjudicate_smoke.py --root <OUT_ROOT> --cell SMOKE_CELL_TAU3_laptop \
        --dose 3.0 --out SMOKE_CELL_TAU3.json [--allow-smoke-budget]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leg_lib as L  # noqa: E402


def _fail(msg: str) -> int:
    print(f"⛔⛔ SMOKE ADJUDICATION FAILED: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--cell", required=True, help="the SMOKE_ cell dir name")
    # ⚠️ NAMED `--dose`, NOT `--tau-p`, deliberately: `run_cells.sh` is grepped
    # (by readers and by test_taup_leg.py) for the SHARED flags `--tau-p` /
    # `--c-puct`, which must appear NOWHERE in it. An adjudicator flag spelled
    # the same way would be a permanent false positive on that invariant.
    ap.add_argument("--dose", dest="tau_p", type=float, required=True,
                    help="the candidate-side tau_p this smoke was launched with")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--allow-smoke-budget", action="store_true",
                    help="⚠️ SKIP G-BUDGET only. For a BUILD-TIME dry cell at a "
                         "tiny budget; a real pre-launch smoke runs PRODUCTION "
                         "knobs (only the game count is reduced) and must NOT "
                         "pass this.")
    a = ap.parse_args()

    if not a.cell.startswith("SMOKE_"):
        return _fail(f"--cell {a.cell!r} is not a SMOKE_ cell. This adjudicator "
                     "reads structural keys only and must never be pointed at a "
                     "real cell, whose read-out is the PREREG's branch map.")

    d = a.root / a.cell
    if not d.is_dir():
        return _fail(f"{d} does not exist — the smoke emitted NOTHING")
    man_p = d / "manifest.json"
    if not man_p.is_file():
        return _fail(f"{man_p} does not exist. eval_fair_puct writes the manifest "
                     "at run START, so a cell dir with no manifest means the "
                     "harness died before it began.")
    try:
        man = json.loads(man_p.read_text())
    except Exception as e:                                     # noqa: BLE001
        return _fail(f"{man_p} does not parse: {e}")
    if not isinstance(man, dict) or not man:
        return _fail(f"{man_p} parsed to an EMPTY document")

    games = sorted(d.glob("game_*.json"))
    if not games:
        # ⛔ THE EMPTY-CELL CASE, NAMED. A manifest with no per-game records is a
        # harness that started and played nothing, and it is exactly the shape a
        # "the smoke passed" report is most likely to be believed about.
        games = [p for p in d.glob("*.json")
                 if p.name not in ("manifest.json", "summary.json")]
    if not games:
        return _fail(f"{d} has a manifest but ZERO per-game records — the cell "
                     "played nothing. NONZERO EXIT (the R1 defect class).")

    results = {}
    for name, fn in L.ALL_GATES.items():
        if name == "G-BUDGET" and a.allow_smoke_budget:
            results[name] = {"ok": None, "skipped": "--allow-smoke-budget"}
            continue
        bad = fn(man, a.tau_p) if name == "G-TAUP" else fn(man)
        results[name] = {"ok": not bad, "findings": bad}

    resolved = {
        "config.cand_search": L.dig(man, "config.cand_search"),
        "config.champion.tau_p": L.dig(man, "config.champion.tau_p"),
        "config.opponent.champ_cfg.tau_p":
            L.dig(man, "config.opponent.champ_cfg.tau_p"),
        "config.cand_tiearb": L.dig(man, "config.cand_tiearb"),
        "config.opp_tiearb": L.dig(man, "config.opp_tiearb"),
    }
    resolved = {k: (None if v is L.MISSING else v) for k, v in resolved.items()}

    failed = [k for k, v in results.items() if v["ok"] is False]
    out = {
        "kind": "SMOKE ADJUDICATION — STRUCTURAL KEYS ONLY",
        "cell": a.cell,
        "requested_tau_p": a.tau_p,
        "n_game_records": len(games),
        "manifest_host": man.get("host"),
        "manifest_code_rev": man.get("code_rev"),
        "gates": results,
        "resolved": resolved,
        "verdict": "PASS" if not failed else "FAIL",
        "failed": failed,
        "riders": [
            "⛔ NO OUTCOME KEY. This document carries no winrate, elo, margin or "
            "z, deliberately — a smoke decides nothing and its n cannot be "
            "pooled with the round.",
            "⭐ Its substantive job is to return the RESOLVED dose and the "
            "RESOLVED arbiter dict FOR BOTH SEATS as the harness actually wrote "
            "them, on the box that will play.",
        ],
    }
    a.out.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    for k, v in results.items():
        tag = "SKIP" if v["ok"] is None else ("PASS" if v["ok"] else "FAIL")
        print(f"  [{tag}] {k}" + ("" if v["ok"] is not False
                                  else "  " + "; ".join(v["findings"])))
    print(f"{out['verdict']} ({len(games)} game records) -> {a.out}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
