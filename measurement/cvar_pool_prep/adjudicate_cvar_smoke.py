#!/usr/bin/env python3
"""Adjudicate ONE pre-launch smoke from its OWN emitted manifest AND summary.

⛔⛔ IT EXITS NONZERO on a missing dir, a missing/unparseable manifest, ZERO
per-game records, a missing summary, or any gate failure. That list is not
decorative: the FPU round's smoke and the phasegate round's banked
`SMOKE_local.json` BOTH "passed" over ZERO adjudicated cells (the R1 defect,
filed twice in the 2026-08-30 merge review). A smoke that ran and produced
nothing must never read as a green light.

⭐ THIS ROUND'S SMOKE ADJUDICATES THE **SUMMARY** TOO, which its three
predecessors could not. `G-REACH` reads `summary.pool.candidate.pickchanges` —
the play-derived witness that the pooling rule actually DIFFERED from the
champion. Eight games at ~140 plies is ample: at a per-ply reach of even 0.02
the probability of zero pick changes is negligible, so a smoke that reports zero
is telling you the dispatch never ran, and it says so before a band is spent.

⛔ THE SMOKE EMITS NO OUTCOME KEY. Its 8 games decide nothing, may never be
pooled, and `test_cvar_pool.py` asserts the absence of every outcome-shaped key
in this document.

    python adjudicate_cvar_smoke.py --root <OUT_ROOT> --cell SMOKE_CELL_CVAR25_laptop \\
        --alpha 0.25 --out SMOKE_CELL_CVAR25.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cvar_lib as L  # noqa: E402


def adjudicate(root: Path, cell: str, alpha: float) -> dict:
    d = root / cell
    out: dict = {
        "instrument": "measurement/cvar_pool_prep smoke adjudicator",
        "cell": cell, "dir": str(d), "alpha": alpha,
        "riders": [
            "⛔ THE SMOKE EMITS NO OUTCOME KEY. Its games are on the THROWAWAY "
            "sub-range, they decide nothing, and they may never be pooled with "
            "any cell.",
            "⛔ Structural keys only: this document says the box CAN express the "
            "cell, never that the cell is good.",
        ],
    }
    fatal: list[str] = []

    if not d.is_dir():
        fatal.append(f"the smoke out-dir {d} DOES NOT EXIST — the run never "
                     "started, or --out-subdir disagrees with this adjudicator")
        out["fatal"] = fatal
        out["verdict"] = "FAIL"
        return out

    records = sorted(d.glob("seed*_a*.json"))
    out["n_records"] = len(records)
    if not records:
        fatal.append(
            f"ZERO per-game records in {d} — ⛔ THE R1 DEFECT, REALIZED TWICE IN "
            "THIS PROGRAM (the FPU smoke and phasegate's banked SMOKE_local.json "
            "both 'passed' over zero cells). A smoke that produced nothing is a "
            "FAIL, never a default.")

    mpath = d / "manifest.json"
    manifest = None
    if not mpath.is_file():
        fatal.append(f"{mpath} is MISSING — eval_fair_puct writes the manifest at "
                     "run START, so its absence means the run never got that far")
    else:
        try:
            manifest = json.loads(mpath.read_text())
        except Exception as e:                                 # noqa: BLE001
            fatal.append(f"{mpath} is UNPARSEABLE: {type(e).__name__}: {e}")

    spath = d / "summary.json"
    summary = None
    if not spath.is_file():
        fatal.append(
            f"{spath} is MISSING — eval_fair_puct writes the summary at run END, "
            "so a manifest WITHOUT a summary is a run that was KILLED mid-flight. "
            "⛔ This round cannot pass a smoke without it: `G-REACH`, the only "
            "gate that reads PLAY rather than config, lives there.")
    else:
        try:
            summary = json.loads(spath.read_text())
        except Exception as e:                                 # noqa: BLE001
            fatal.append(f"{spath} is UNPARSEABLE: {type(e).__name__}: {e}")

    gates: dict[str, list[str]] = {}
    if manifest is not None:
        gates["G-POOL"] = L.gate_pool(manifest, alpha)
        gates["G-SINGLEVAR"] = L.gate_singlevar(manifest)
        gates["G-BUDGET"] = L.gate_budget(manifest)
        gates["G-ARB"] = L.gate_arbiter(manifest)
    if summary is not None:
        gates["G-REACH"] = L.gate_reach(summary)
    out["gates"] = {k: {"ok": not v, "problems": v} for k, v in gates.items()}
    out["gates_missing"] = sorted(set(L.ALL_GATES) - set(gates))

    # The resolved surfaces, echoed so a reader does not have to open the
    # manifest. ⛔ Echoes, never the gate: the gates above are the gate.
    if manifest is not None:
        out["resolved"] = {
            "cand_search": L.dig(manifest, "config.cand_search"),
            "champion_pool": {
                "mode": L.dig(manifest, "config.champion.pool_mode"),
                "alpha": L.dig(manifest, "config.champion.pool_alpha")},
            "opponent_pool": {
                "mode": L.dig(manifest, "config.opponent.champ_cfg.pool_mode"),
                "alpha": L.dig(manifest, "config.opponent.champ_cfg.pool_alpha")},
            "cand_tiearb": L.dig(manifest, "config.cand_tiearb"),
            "opp_tiearb": L.dig(manifest, "config.opp_tiearb"),
            "cand_leaf_hash": L.dig(manifest, "cand_leaf_hash"),
            "rules_profile": L.dig(manifest, "rules_profile.name"),
            "host": L.dig(manifest, "host"),
        }
        out["resolved"] = json.loads(
            json.dumps(out["resolved"],
                       default=lambda o: "MISSING" if o is L.MISSING else str(o)))
    if summary is not None:
        cand = L.dig(summary, "pool.candidate")
        opp = L.dig(summary, "pool.opponent")
        out["play_witness"] = json.loads(json.dumps(
            {"candidate": cand, "opponent": opp},
            default=lambda o: "MISSING" if o is L.MISSING else str(o)))

    failed = [k for k, v in gates.items() if v]
    if failed:
        fatal.append(f"gate failures: {failed}")
    out["fatal"] = fatal
    out["verdict"] = "PASS" if not fatal else "FAIL"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--cell", required=True)
    ap.add_argument("--alpha", type=float, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    v = adjudicate(a.root, a.cell, a.alpha)
    a.out.write_text(json.dumps(v, indent=2, ensure_ascii=False))
    for name, g in (v.get("gates") or {}).items():
        print(f"  [{'PASS' if g['ok'] else 'FAIL'}] {name}"
              + ("" if g["ok"] else f"  {g['problems']}"))
    for f in v.get("fatal", []):
        print(f"  ⛔ {f}")
    print(f"{v['verdict']} -> {a.out}")
    return 0 if v["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
