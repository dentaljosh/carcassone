#!/usr/bin/env python3
"""TILE-TIE PRICING — split Stage B into CUMULATIVE execution cells.

DESIGN.md §7.3's Stage B is *"a pure extension of the same records directory:
no re-scoring, no new ruler"*. Two facts about the existing tooling force the
shape of this splitter, and neither is a design change:

1. **The records root must stay ONE root.** `analyze_tiletie.py` takes a single
   `--records-root`, and the pooled Stage A + Stage B estimate is the
   pre-registered deliverable — so Stage B's records land beside Stage A's, in
   `<out_root>/<judge>/<profile>/leg<r>/records/`.
2. **`run_tiletie.verify_leg_records` asserts a leg produced records for
   EXACTLY the rids in its input** — `extra` is a failure, not a warning. A
   plan dir naming only the NEW rids would therefore fail that check against a
   records dir that already holds Stage A's.

⇒ each cell's plan dir is CUMULATIVE: Stage A's leg files **plus** the Stage B
chunks up to and including that cell. `oracle_score_pilot --resume` skips any
rid whose record already exists (`--resume` is "skip if the record file is
there", verified in the pilot source), so the already-scored lines cost a
`Path.exists()` each and nothing more, and the integrity check sees exactly the
rid set it should. The LAST cell's plan dir is, by construction, the **pooled
Stage A + Stage B plan** the analyser wants.

Cells exist so the launcher can re-pick `W` by wall-clock at each cell start
(the owner's box grant: W30 until 11:00 local, then W14) without any cell
straddling the boundary. They are an EXECUTION device only: every cell scores
the same positions in the same order-independent way, and the analysis pools
all of them into one estimate.

Chunking is phase-stratified round-robin (DESIGN §7.4: *"cost per position
varies ~9x with game phase … the sampler must not be allowed to drift
phase-wise"*), so every cell carries the same early/mid/late mix and its ETA is
a scaled copy of every other cell's rather than a lottery.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_positions as BP  # noqa: E402


def read_legs(plan_dir: Path) -> dict:
    """{'profile/legR': [raw jsonl lines]} for a built plan dir."""
    plan = json.loads((plan_dir / "POSITIONS_PLAN.json").read_text())
    out = {}
    for key, info in plan["files"].items():
        p = Path(info["path"])
        if not p.is_file():                       # plan may carry a relative path
            p = plan_dir / Path(info["path"]).name
        lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
        if len(lines) != info["n"]:
            raise SystemExit(f"{p}: {len(lines)} lines != plan n={info['n']}")
        out[key] = lines
    return out


def chunk_rids(arms: dict, n_cells: int) -> list:
    """Phase-stratified round-robin over rid-sorted order -> n_cells rid sets."""
    cells = [set() for _ in range(n_cells)]
    i = 0
    for phase in ("early", "mid", "late", None):
        for rid in sorted(r for r, v in arms.items() if v.get("phase_bucket") == phase):
            cells[i % n_cells].add(rid)
            i += 1
    return cells


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stage-a", required=True)
    ap.add_argument("--stage-b", required=True)
    ap.add_argument("--out-dir", required=True, help="cells are written to <out>/cellNN")
    ap.add_argument("--pooled-dir", default=None,
                    help="also write the full pooled plan here (= the last cell)")
    ap.add_argument("--cells", type=int, default=4)
    ap.add_argument("--playout-secs", type=float, default=1.5999,
                    help="REALIZED Stage A rust worker-s/playout (sum(elapsed_secs)"
                         "/playouts), not the planning constant")
    args = ap.parse_args(argv)

    a_dir, b_dir = Path(args.stage_a), Path(args.stage_b)
    out = Path(args.out_dir)
    a_arms = json.loads((a_dir / "ARMS.json").read_text())
    b_arms = json.loads((b_dir / "ARMS.json").read_text())
    overlap = set(a_arms) & set(b_arms)
    if overlap:
        raise SystemExit(f"REFUSING: Stage A and Stage B share {len(overlap)} rid(s), "
                         f"e.g. {sorted(overlap)[:5]} — Stage B must be DISJOINT "
                         "(DESIGN §7.3: an extension, not a re-draw).")

    a_legs, b_legs = read_legs(a_dir), read_legs(b_dir)
    cells = chunk_rids(b_arms, args.cells)
    assert sum(len(c) for c in cells) == len(b_arms)
    assert not set.intersection(*cells) if args.cells > 1 else True

    dropped = (a_dir / "DROPPED_ALL_TRANSPOSITION.json").read_text()
    a_plan = json.loads((a_dir / "POSITIONS_PLAN.json").read_text())

    targets = [(out / f"cell{i + 1:02d}", set().union(*cells[:i + 1]))
               for i in range(args.cells)]
    if args.pooled_dir:
        targets.append((Path(args.pooled_dir), set(b_arms)))

    summary = []
    for tgt, rids in targets:
        tgt.mkdir(parents=True, exist_ok=True)
        files, arms = {}, dict(a_arms)
        for key in sorted(set(a_legs) | set(b_legs)):
            lines = list(a_legs.get(key, []))
            lines += [ln for ln in b_legs.get(key, [])
                      if json.loads(ln)["rid"] in rids]
            if not lines:
                continue
            profile, leg = key.split("/leg")
            p = tgt / f"positions_{profile}_leg{leg}.jsonl"
            p.write_text("".join(ln + "\n" for ln in lines))
            files[key] = {"path": str(p), "n": len(lines)}
        arms.update({r: v for r, v in b_arms.items() if r in rids})
        (tgt / "ARMS.json").write_text(json.dumps(arms, indent=2, sort_keys=True))
        (tgt / "DROPPED_ALL_TRANSPOSITION.json").write_text(dropped)

        plan = BP.cost_plan(list(arms.values()), cap_j=a_plan["cap_j"],
                            sample_seed=a_plan["sample_seed"],
                            playout_secs=args.playout_secs,
                            t_champ_secs=0.0, workers=(14, 30))
        plan["files"] = files
        plan["afterstate_dedupe"] = a_plan["afterstate_dedupe"]
        plan["allow_missing_champ_picks"] = a_plan["allow_missing_champ_picks"]
        plan["n_positions_champ_pick_missing"] = 0
        plan["census_rows_n"] = a_plan["census_rows_n"]
        plan["census_qualifying_n"] = a_plan["census_qualifying_n"]
        plan["out_dir"] = str(tgt)
        plan["stage_b_cell"] = {
            "cumulative": True,
            "n_stage_a": len(a_arms), "n_stage_b_here": len(rids),
            "n_stage_b_total": len(b_arms),
            "playout_secs_source": "REALIZED Stage A rust arm: sum(elapsed_secs)"
                                   "/playouts over the walled leg records",
            "note": "CUMULATIVE plan: Stage A + Stage B chunks up to this cell. "
                    "Already-scored rids are skipped by oracle_score_pilot "
                    "--resume; they are present so run_tiletie's "
                    "verify_leg_records sees the exact rid set of the shared "
                    "records root. The analysis pools every cell into ONE "
                    "estimate (DESIGN §7.3).",
        }
        (tgt / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=2, sort_keys=True))

        recs = sum(info["n"] for k, info in files.items() if k.startswith("walled/"))
        summary.append((tgt.name, len(rids), plan["n_positions"], recs))
        print(f"[cells] {tgt} | stage_b_here={len(rids):4d} | cumulative "
              f"positions={plan['n_positions']:4d} | walled leg-records={recs:4d} | "
              f"legs={sorted(files)}")

    per_cell = [len(c) for c in cells]
    print(f"\n[cells] stage-B chunk sizes: {per_cell} (sum {sum(per_cell)})")
    for i, c in enumerate(cells, 1):
        mix = defaultdict(int)
        for r in c:
            mix[b_arms[r]["phase_bucket"]] += 1
        print(f"[cells] cell{i:02d} phase mix: {dict(sorted(mix.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
