#!/usr/bin/env python3
"""IDENTITY GATE for `adaptive_k_census --backend rust` — audit item A8.

WHY.  A8's row is the PRE-GATE that killed the phase-adaptive-k lever (2026-07-28), and
the audit calls its infra reusable.  Moving the per-world search onto carc_rs must
therefore be a no-op on the CENSUS ROW, not just on some other harness's action stream:
the row's decision-bearing fields (`v_std`, `v_range`, `changed_k2_vs_k4`,
`pooled_top2_gap_by_k`) are functions of every visited child's pooled Q, so a 1-ulp
divergence anywhere in any world moves them.

WHAT IS COMPARED.  The census's own worker (`adaptive_k_census._census_root`) is run
twice per root — `_BACKEND = "python"` then `"rust"` — and the two rows are diffed FIELD
BY FIELD with floats canonicalised to raw f64 BIT patterns.  Excluded: `secs` (wall
clock) and `backend` (the thing under test).  Everything else is in scope, including the
duplicate-census block (`dup`, `dup_rep`) — which is the check that the Python
determinization stream really was left untouched, since `dup_rep` is drawn from the
CONTINUING rng after the k searched worlds and would decorrelate instantly if the draw
had been handed to `FairAgentRs.determinizations()`.

`--noise-control` is NOT exercised here: it is python-only by construction (carc_rs has
no search seed), which the census refuses at argparse time.

    .venv/bin/python scripts/rustport/gate_adaptive_k_backend.py --games 3
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

# MUST precede any carcassonne_ai import (import-frozen DEFAULT_CONFIG).
import adaptive_k_census as A  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GATE_ADAPTIVE_K_BACKEND.json"

SKIP_FIELDS = {"secs", "backend"}


def canon(x):
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        return ("f64", struct.unpack("<Q", struct.pack("<d", x))[0])
    if isinstance(x, dict):
        return {k: canon(v) for k, v in sorted(x.items())}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    return repr(x)


def run_leg(root: dict, *, backend: str, cfg, sims: int, k_dets: int, salt: int,
            reps: int) -> dict:
    A._init(cfg, sims, k_dets, salt, reps, False, backend, 1)
    return A._census_root(dict(root))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_adaptive_k_backend")
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--plies", default="12,40,72,104")
    ap.add_argument("--sims", type=int, default=344,
                    help="screen budget; --prod-roots run at PRODUCTION.yaml sims_per_det")
    ap.add_argument("--k-dets", type=int, default=4)
    ap.add_argument("--prod-roots", type=int, default=2,
                    help="roots re-run at the PRODUCTION per-world budget and k_dets")
    ap.add_argument("--dup-replicates", type=int, default=8)
    ap.add_argument("--salt", type=int, default=A.DEFAULT_SALT)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    spec = CF.load_production_spec()
    cfg = CF.production_prior_cfg(spec)
    plies = [int(x) for x in args.plies.split(",")]

    recs = [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()][:args.games]
    roots = []
    for g in recs:
        acts = [int(a) for a in g["actions"]]
        for p in plies:
            if p < len(acts):
                roots.append({"deck_seed": int(g["deck_seed"]), "ply": int(p),
                              "actions": acts, "checksum": None,
                              "phase": None, "phase_bucket": None})

    legs = [("screen", int(args.sims), int(args.k_dets), roots)]
    if args.prod_roots > 0:
        legs.append(("production", int(spec.sims_per_det), int(spec.k_dets),
                     roots[:int(args.prod_roots)]))

    mismatches, rows, skipped, checks = [], [], [], 0
    for leg, sims, k_dets, leg_roots in legs:
        for root in leg_roots:
            py = run_leg(root, backend="python", cfg=cfg, sims=sims, k_dets=k_dets,
                         salt=int(args.salt), reps=int(args.dup_replicates))
            rs = run_leg(root, backend="rust", cfg=cfg, sims=sims, k_dets=k_dets,
                         salt=int(args.salt), reps=int(args.dup_replicates))
            rid = f"s{root['deck_seed']}_p{root['ply']}"
            if not (py.get("ok") and rs.get("ok")):
                agree = (bool(py.get("ok")) == bool(rs.get("ok"))
                         and py.get("error") == rs.get("error"))
                if not agree:
                    mismatches.append({"leg": leg, "rid": rid, "field": "<ok>",
                                       "python": str(py.get("error"))[:300],
                                       "rust": str(rs.get("error"))[:300]})
                skipped.append({"leg": leg, "rid": rid, "error": py.get("error"),
                                "same_on_both": agree})
                print(f"  [{leg}] {rid} SKIPPED ({py.get('error')}) "
                      f"{'same on both' if agree else 'DIVERGENT REFUSAL'}", flush=True)
                continue
            n = 0
            for f in sorted((set(py) | set(rs)) - SKIP_FIELDS):
                n += 1
                if canon(py.get(f, "<absent>")) != canon(rs.get(f, "<absent>")):
                    mismatches.append({"leg": leg, "rid": rid, "field": f,
                                       "python": str(py.get(f))[:300],
                                       "rust": str(rs.get(f))[:300]})
            checks += n
            same = not any(m.get("rid") == rid and m.get("leg") == leg
                           for m in mismatches)
            rows.append({"leg": leg, "rid": rid, "sims": sims, "k_dets": k_dets,
                         "fields": n, "v_std": py.get("v_std"),
                         "n_distinct_argmax": py.get("n_distinct_argmax"),
                         "changed_k2_vs_k4": py.get(f"changed_k2_vs_k{k_dets}"),
                         "identical": same})
            print(f"  [{leg}] {rid} k{k_dets}x{sims} v_std={py.get('v_std')} "
                  f"distinct_argmax={py.get('n_distinct_argmax')} {n} fields "
                  f"{'IDENTICAL' if same else 'MISMATCH'}", flush=True)

    ok = bool(rows) and not mismatches
    out = {
        "gate": "rustport A8 — adaptive_k_census python vs rust per-world search",
        "why": "A8's census row is the pre-gate evidence that killed the adaptive-k "
               "lever and the audit calls the infra reusable; its decision fields "
               "(v_std, v_range, changed_kX, pooled_top2_gap_by_k) are functions of "
               "every visited child's pooled Q, so they move on a 1-ulp divergence.",
        "champion_id": getattr(spec, "champion_id", None),
        "seam": "the k per-world searches only (MirrorState.set_unseen_deck + "
                "search_single). The determinization DRAW and the duplicate census stay "
                "on the Python rng stream — dup_rep is drawn from the CONTINUING stream "
                "and is compared here precisely to prove that.",
        "surface": "every row field except " + str(sorted(SKIP_FIELDS)) +
                   ", floats canonicalised to raw f64 bit patterns",
        "noise_control": "not exercised — python-only by construction (carc_rs has no "
                         "search seed; the census refuses the combination at argparse "
                         "time rather than reporting a vacuous True)",
        "roots": len(rows),
        "field_checks": checks,
        "skipped": skipped,
        "mismatches": mismatches,
        "verdict": "PASS" if ok else "FAIL",
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(rows)} roots, {checks} field checks, "
          f"{len(mismatches)} mismatches -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
