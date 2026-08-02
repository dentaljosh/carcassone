#!/usr/bin/env python3
"""IDENTITY GATE for `kwidth_agreement_probe --backend rust` — audit item A2.

WHY.  A2 is a PICK-PRODUCING probe: its records are read by `oracle_score_pilot` and its
disagreement rate is quoted against CL-070's `D_paired = 0.2398`.  Moving its per-world
search onto carc_rs must therefore be provably a no-op on the RECORD, not merely "the
engine is bit-exact somewhere else" — G4/G6 gated the whole-agent PIMC champion, and this
harness does not run that agent, it borrows one function from it.

WHAT IS COMPARED.  The probe's own worker (`kwidth_agreement_probe._process`) is run
TWICE per cell — once with `_G["backend"] = "python"`, once with `"rust"` — and the two
records are diffed FIELD BY FIELD with every float canonicalised to its raw f64 BIT
pattern.  Only genuinely time-valued keys are excluded:

    elapsed_secs   wall clock
    backend        the thing under test

Everything else is in scope, including the nested `arms` block (`sum_N`,
`pooled_top2_q_gap`, `n_children` per arm), both picks in `q_pick_by_level`, `disagree`,
`det_seed_base` and `agent_seed`.  `pooled_top2_q_gap` is the sharpest of these: it is a
difference of pooled means over every visited child, so it moves on a 1-ulp divergence
anywhere in either arm's tree.

`--parity-cells N` additionally turns on the probe's own `--verify-agent-parity` for the
first N cells of BOTH legs, so the rust leg's re-gated assertion (RustFairAgent driven
over the mirror at k_a and k_b) actually fires inside the gate rather than being trusted.

    .venv/bin/python scripts/rustport/gate_kwidth_backend.py --games 3 --prod-cells 2
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

# MUST precede any carcassonne_ai import: the probe module installs the production leaf
# env at import time and `virtual_score_v2.DEFAULT_CONFIG` is import-frozen from it.
import kwidth_agreement_probe as K  # noqa: E402

import root_replay as RR  # noqa: E402
from carcassonne_ai import champion_factory as CF  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GATE_KWIDTH_BACKEND.json"

SKIP_FIELDS = {"elapsed_secs", "backend"}


def canon(x):
    """Canonicalise a record for comparison: floats -> raw f64 bits, dicts/lists walked."""
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        return ("f64", struct.unpack("<Q", struct.pack("<d", x))[0])
    if isinstance(x, dict):
        return {k: canon(v) for k, v in sorted(x.items())}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    return repr(x)


def run_leg(item: dict, *, backend: str, verify: bool, rust_threads: int = 1) -> dict:
    K._G.clear()
    K._G.update(wall_cap=3600, backend=backend, rust_threads=int(rust_threads),
                verify_parity=bool(verify), cfg=CF.production_prior_cfg())
    return K._process(dict(item))


def make_item(deck_seed: int, ply: int, actions: list, salt: int) -> dict:
    """The item shape `main()` hands the pool (metadata keys are copied verbatim)."""
    return {
        "rid": f"s{deck_seed}_p{ply}_r{salt}", "root_id": f"s{deck_seed}_p{ply}",
        "deck_seed": int(deck_seed), "ply": int(ply), "salt": int(salt),
        "k_remaining": None, "game_phase": None, "phase_bucket": None,
        "n_legal": None, "h200_top2_q_gap": None, "solver_region": False,
        "cl070_q_pick_2752": None, "cl070_q_pick_11008": None,
        "actions": [int(a) for a in actions], "checksum": None,
    }


def compare(py: dict, rs: dict, ctx: dict, mismatches: list) -> int:
    keys = (set(py) | set(rs)) - SKIP_FIELDS
    checks = 0
    for f in sorted(keys):
        checks += 1
        a, b = canon(py.get(f, "<absent>")), canon(rs.get(f, "<absent>"))
        if a != b:
            mismatches.append({**ctx, "field": f,
                               "python": str(py.get(f))[:300],
                               "rust": str(rs.get(f))[:300]})
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_kwidth_backend")
    ap.add_argument("--games", type=int, default=3, help="recorded games supplying roots")
    ap.add_argument("--plies", default="12,40,72,104",
                    help="opening/mid/late spread (tree shape tracks placed meeples)")
    ap.add_argument("--salts", default="0,1")
    ap.add_argument("--k-a", type=int, default=2)
    ap.add_argument("--k-b", type=int, default=4)
    ap.add_argument("--sims-per-det", type=int, default=344,
                    help="screen budget for the breadth cells; --prod-cells run at the "
                         "champion's own arms regardless")
    ap.add_argument("--prod-cells", type=int, default=2,
                    help="cells re-run at the PRODUCTION arms (k8 vs k16 x sims_per_det "
                         "from PRODUCTION.yaml). 0 disables.")
    ap.add_argument("--parity-cells", type=int, default=1,
                    help="cells on which BOTH legs also run --verify-agent-parity")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    spec = CF.load_production_spec()
    plies = [int(x) for x in args.plies.split(",")]
    salts = [int(x) for x in args.salts.split(",")]

    recs = [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()][:args.games]
    cells = []
    for g in recs:
        acts = [int(a) for a in g["actions"]]
        for p in plies:
            if p < len(acts):
                for s in salts:
                    cells.append(make_item(int(g["deck_seed"]), p, acts, s))

    mismatches, rows, skipped, checks = [], [], [], 0
    legs = [("screen", int(args.k_a), int(args.k_b), int(args.sims_per_det), cells)]
    if args.prod_cells > 0:
        legs.append(("production", 8, 16, int(spec.sims_per_det),
                     cells[:int(args.prod_cells)]))

    for leg, k_a, k_b, spd, leg_cells in legs:
        K.K_A, K.K_B, K.SIMS_PER_DET = k_a, k_b, spd
        for i, item in enumerate(leg_cells):
            verify = i < int(args.parity_cells)
            py = run_leg(item, backend="python", verify=verify)
            rs = run_leg(item, backend="rust", verify=verify)
            if not (py.get("ok") and rs.get("ok")):
                # A cell the PROBE ITSELF refuses (forced move, checksum) is not a gate
                # failure — but the two backends must refuse it for the SAME reason, or
                # the record set would differ in membership.
                agree = (bool(py.get("ok")) == bool(rs.get("ok"))
                         and py.get("error") == rs.get("error"))
                if not agree:
                    mismatches.append({"leg": leg, "rid": item["rid"], "field": "<ok>",
                                       "python": str(py.get("error"))[:300],
                                       "rust": str(rs.get("error"))[:300]})
                skipped.append({"leg": leg, "rid": item["rid"],
                                "error": py.get("error"), "same_on_both": agree})
                print(f"  [{leg}] {item['rid']} SKIPPED-BY-PROBE ({py.get('error')}) "
                      f"{'same on both backends' if agree else 'DIVERGENT REFUSAL'}",
                      flush=True)
                continue
            n = compare(py, rs, {"leg": leg, "rid": item["rid"]}, mismatches)
            checks += n
            same = not any(m.get("rid") == item["rid"] and m.get("leg") == leg
                           for m in mismatches)
            rows.append({"leg": leg, "rid": item["rid"], "k_a": k_a, "k_b": k_b,
                         "sims_per_det": spd, "fields": n,
                         "pick_a": py["q_pick_by_level"][str(k_a * spd)],
                         "pick_b": py["q_pick_by_level"][str(k_b * spd)],
                         "disagree": py["disagree"],
                         "parity_verified": bool(py.get("agent_parity_verified")),
                         "identical": same})
            print(f"  [{leg}] {item['rid']} k{k_a}x{spd} vs k{k_b}x{spd} "
                  f"a={rows[-1]['pick_a']} b={rows[-1]['pick_b']} "
                  f"disagree={py['disagree']} parity={rows[-1]['parity_verified']} "
                  f"{n} fields {'IDENTICAL' if same else 'MISMATCH'}", flush=True)

    ok = bool(rows) and not mismatches
    out = {
        "gate": "rustport A2 — kwidth_agreement_probe python vs rust per-world search",
        "why": "A2 produces the PICKS oracle_score_pilot scores and the disagreement rate "
               "quoted against CL-070's D_paired 0.2398. The backend must be provably a "
               "no-op on the record, not inherited from the whole-agent G4/G6 gates.",
        "champion_id": getattr(spec, "champion_id", None),
        "seam": "fair_agent.search_one_world -> MirrorState.set_unseen_deck + "
                "search_single (rust_world_search.RustWorldSearcher). Determinization "
                "draw, pooling and decision rule stay PYTHON on both legs.",
        "surface": "every record field except " + str(sorted(SKIP_FIELDS)) +
                   ", floats canonicalised to raw f64 bit patterns (nested arms block "
                   "included: sum_N, pooled_top2_q_gap, n_children per arm)",
        "cells": len(rows),
        "field_checks": checks,
        "parity_cells": sum(1 for r in rows if r["parity_verified"]),
        "disagreement_cells": sum(1 for r in rows if r["disagree"]),
        "skipped_by_probe": skipped,
        "mismatches": mismatches,
        "verdict": "PASS" if ok else "FAIL",
        "scope": "the per-world PUCT search at these knobs, net-free, fresh-tree. Says "
                 "nothing about reuse_tree (Gap 2) or evaluator injection (Gap 3) — "
                 "search_config_rs refuses both.",
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(rows)} cells, {checks} field checks, "
          f"{len(mismatches)} mismatches -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
