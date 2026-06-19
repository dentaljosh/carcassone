#!/usr/bin/env python3
"""Aggregate the L2-1 adjacent-rung matrix into LADDER_RESULTS.json + verdicts.

Reads each comparison's summary.json (written by ladder_rung_eval.py) from the
share, orders them R1vR0..R5vR4, and applies the PRE-REGISTERED decision rules
from measurement/level2/LEVEL2_LADDER_PROTOCOL.md:

  V4 monotonicity : each rung beats the one below with elo>0 AND paired z>=2.
  Saturation gate : R5 (heur@1600) beats R4 (heur@800) iff elo>0 AND z>=2; else
                    the full-game ruler is SATURATED at R4 = heur@800-v2.7.

Pure reader — re-runnable, never mutates the run. Usage:
  python scripts/level2/aggregate_l2_ladder.py <SHARE_ROOT>
    [--out measurement/level2/LADDER_RESULTS.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ladder order: (label, higher_rung_token, lower_rung_token, role)
LADDER = [
    ("R1vR0", "greedy", "random", "monotone"),
    ("R2vR1", "heur_v1@200", "greedy", "monotone"),
    ("R3vR2", "heur_v2_7@200", "heur_v1@200", "monotone"),
    ("R4vR3", "heur_v2_7@800", "heur_v2_7@200", "monotone"),
    ("R5vR4", "heur_v2_7@1600", "heur_v2_7@800", "saturation"),
]


def _san(s: str) -> str:
    return s.replace("@", "").replace("_", "")


def _dir(root: Path, a: str, b: str) -> Path:
    return root / f"{_san(a)}__vs__{_san(b)}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("share_root", help="e.g. /mnt/c/carc-shared/level2_ladder")
    ap.add_argument("--out", default="measurement/level2/LADDER_RESULTS.json")
    args = ap.parse_args(argv)
    root = Path(args.share_root)

    comparisons = []
    for label, a, b, role in LADDER:
        d = _dir(root, a, b)
        sp = d / "summary.json"
        if not sp.exists():
            comparisons.append({"label": label, "rung_a": a, "rung_b": b,
                                "role": role, "status": "MISSING", "dir": str(d)})
            continue
        s = json.load(open(sp))
        elo = s.get("elo")
        z = s.get("paired_z")
        # monotone step is clean iff higher rung wins with z>=2
        clean = (elo is not None and elo > 0 and z is not None and z >= 2.0)
        inverted = (z is not None and z <= -2.0)
        comparisons.append({
            "label": label, "rung_a": a, "rung_b": b, "role": role,
            "status": "DONE",
            "n": s.get("n"), "W": s.get("W"), "D": s.get("D"), "L": s.get("L"),
            "winrate": s.get("winrate"), "elo": elo,
            "elo_sig_1sigma": s.get("elo_sig_1sigma"),
            "paired_mean_margin": s.get("paired_mean_margin"),
            "paired_z": z, "n_paired": s.get("n_paired"),
            "n_deck_hashes": s.get("n_deck_hashes"),
            "step_clean_zge2": clean, "step_inverted_zle_neg2": inverted,
            "dir": str(d),
        })

    mono_steps = [c for c in comparisons if c["role"] == "monotone"]
    done_mono = [c for c in mono_steps if c["status"] == "DONE"]
    monotone_ok = bool(done_mono) and all(c["step_clean_zge2"] for c in done_mono)
    inverted_any = [c["label"] for c in comparisons
                    if c.get("step_inverted_zle_neg2")]
    compressed = [c["label"] for c in done_mono if not c["step_clean_zge2"]
                  and not c["step_inverted_zle_neg2"]]

    sat = next((c for c in comparisons if c["role"] == "saturation"), None)
    if sat is None or sat["status"] != "DONE":
        saturation_verdict = "PENDING"
    elif sat["elo"] is not None and sat["elo"] > 0 and sat["paired_z"] is not None and sat["paired_z"] >= 2.0:
        saturation_verdict = "REFUTED (R5 beats R4 — ruler has headroom above heur@800)"
    else:
        saturation_verdict = "SATURATED (R5 does not beat R4 — ruler tops out at heur@800-v2.7)"

    out = {
        "experiment": "Level-2 L2-1 adjacent-rung ladder",
        "share_root": str(root),
        "comparisons": comparisons,
        "monotonicity_V4": {
            "all_done_steps_clean_zge2": monotone_ok,
            "inverted_steps_zle_neg2": inverted_any,
            "compressed_ties_abs_z_lt2": compressed,
        },
        "saturation_gate": {
            "verdict": saturation_verdict,
            "comparison": sat["label"] if sat else None,
        },
    }
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(outp, "w"), indent=2)

    # human-readable
    print(f"\n{'step':7} {'higher vs lower':34} {'W/D/L':>11} {'elo':>9} {'z':>7}  flag")
    for c in comparisons:
        if c["status"] != "DONE":
            print(f"{c['label']:7} {c['rung_a']+' vs '+c['rung_b']:34} {c['status']:>11}")
            continue
        flag = "clean" if c["step_clean_zge2"] else ("INVERTED" if c["step_inverted_zle_neg2"] else "compressed")
        wdl = f"{c['W']}/{c['D']}/{c['L']}"
        print(f"{c['label']:7} {c['rung_a']+' vs '+c['rung_b']:34} {wdl:>11} "
              f"{c['elo']:+9.1f} {c['paired_z']:+7.2f}  {flag}")
    print(f"\nV4 monotonicity (all done steps z>=2): {monotone_ok}"
          + (f"  | INVERTED: {inverted_any}" if inverted_any else "")
          + (f"  | compressed: {compressed}" if compressed else ""))
    print(f"Saturation gate (R5 vs R4): {saturation_verdict}")
    print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
