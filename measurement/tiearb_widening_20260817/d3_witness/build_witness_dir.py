#!/usr/bin/env python3
"""D3-WITNESS step 1 — build the N=16 positions dir.

Selection spec, AMENDED by the drafter (commit 751bdd12), verbatim:

  "The first 16 rids in POSITION_ORDER.json order among rids possessing
   laptop-produced clair-puct records"

Deterministic and non-empty by construction (314 such rids exist). If fewer than
16 qualify, take all and record the realized N.

(The earlier §D3.5 wording — "first 16 by sorted rid" — selected band-135e9
retained rids, which possess no leg lines and were never scored by either box.
That refusal is what surfaced the union leg-file defect; this amendment routes
around it by keying on rids that demonstrably HAVE laptop records.)

The plan dir is built by REUSING `stage_chunks.write_chunk_dir` against the full
S1 corpus, so the witness dir's shape is identical-by-construction to the chunk
dirs that were actually scored — not identical-by-reimplementation.

Writes ONLY under d3_witness/. Never into chunks/, shared_run/ or shared_run_r4/.
"""
from __future__ import annotations
import glob
import json
import os
import sys
from pathlib import Path

CAMPAIGN = Path("/home/doctor/projects/carcassone/measurement/tiearb_widening_20260817")
sys.path.insert(0, str(CAMPAIGN))
import stage_chunks as SC  # noqa: E402

N_WITNESS = 16
LAPTOP_CHUNKS = (6, 7, 8)      # ALLOCATION.conf: ALLOC_s1_laptop_side_clair_puct
SHARE_CHUNKS = Path("/mnt/c/carc-shared/tiearb_widening_20260817/chunks/s1")  # allow-path
OUT = CAMPAIGN / "d3_witness" / "positions"


def laptop_recorded_rids() -> set:
    """rids with a laptop-PRODUCED clair-puct record, read off the share."""
    rids = set()
    for k in LAPTOP_CHUNKS:
        for p in glob.glob(str(SHARE_CHUNKS / f"chunk{k}/clair-puct/walled/leg*/records/*.json")):
            rids.add(os.path.basename(p)[:-5])
    return rids


def main() -> int:
    order = json.loads((CAMPAIGN / "POSITION_ORDER.json").read_text())
    st = order["strata"]["s1"]

    lap = laptop_recorded_rids()
    chosen = [r for r in st["order"] if r in lap][:N_WITNESS]   # POSITION_ORDER ORDER
    if not chosen:
        raise SystemExit("FATAL: no rid possesses a laptop-produced clair-puct record")

    src = Path(SC.corpus_dir("s1"))
    source_plan, source_arms, dropped = SC.load_plan_dir(src)
    leg_rows = SC.read_leg_files(src, source_plan)

    missing = [r for r in chosen if r not in source_arms]
    if missing:
        raise SystemExit(f"FATAL: rid(s) absent from the S1 corpus ARMS: {missing}")

    plan = SC.write_chunk_dir(
        OUT, set(chosen), source_dir=src, source_plan=source_plan,
        source_arms=source_arms, dropped=dropped, leg_rows=leg_rows,
        label="d3_witness", chunk_index=1, n_chunks=1,
        order_sha256=st["sha256_order"],
    )

    sel = {
        "n_rids_requested": N_WITNESS,
        "n_rids_realized": len(chosen),
        "rids": chosen,
        "selection_rule": ("DEVIATIONS (drafter 751bdd12), verbatim: 'The first 16 rids "
                           "in POSITION_ORDER.json order among rids possessing "
                           "laptop-produced clair-puct records'. Deterministic; no "
                           "cherry-picking; realized N recorded."),
        "n_laptop_recorded_rids_total": len(lap),
        "laptop_chunks": list(LAPTOP_CHUNKS),
        "source_corpus": str(src),
        "positions_dir": str(OUT),
        "order_sha256": st["sha256_order"],
        "legs": {k: v["n"] for k, v in sorted(plan["files"].items())},
        "m_plan_cost_metadata": plan.get("m_plan_cost_metadata"),
    }
    (CAMPAIGN / "d3_witness" / "SELECTION.json").write_text(json.dumps(sel, indent=1) + "\n")
    print(json.dumps({k: v for k, v in sel.items() if k != "rids"}, indent=1))
    print(f"rids ({len(chosen)}): {chosen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
