#!/usr/bin/env python3
"""Build the OUT-OF-FAMILY re-pricing plan (measurement/tiletie_oof_20260814).

Pure plan surgery -- it scores nothing and reads no oracle VALUE. It:

  1. splits the pricing corpus's pooled plan into the DEV slice (root_id not in
     ``tiletie_mining_20260814/HOLDOUT_ROOTS.json``) -- 522 positions / 279 roots;
  2. draws the committed seeded permutation (seed 20260814) once: the LAST
     ``--pilot-n`` entries are the §6 cost pilot (EXCLUDED from the main read),
     the rest is the main read in committed order;
  3. cuts the main order into ``--chunks`` equal sequential chunks (DESIGN §0.A --
     ``load_positions_jsonl`` sorts by ``root_id``, so a partial run is only
     unbiased at CHUNK granularity, never at line granularity);
  4. writes one ``run_tiletie``-shaped plan dir per chunk (+ ``positions_main``
     for the analyser, + ``positions_pilot``);
  5. stages the IN-FAMILY (``clair-puct``) records for the main read into a
     separate root by copying ONLY files whose stem is a main-read rid -- the
     mining firewall idiom, so no holdout record is ever opened (DESIGN §0.B).

Every output is asserted holdout-free (``G-HOLDOUT``) and pilot-free
(``G-PILOT``) before it is written.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
DEFAULT_HOLDOUT = REPO / "measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json"
DEFAULT_OUT = REPO / "measurement/tiletie_oof_20260814"
DEFAULT_IF_RECORDS = "/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct"

PERMUTATION_SEED = 20260814          # DESIGN §6 -- committed, one seed, one shuffle
EXPECT_DEV_POSITIONS = 522           # DESIGN §5 -- mechanically re-verified
EXPECT_DEV_ROOTS = 279
SCHEMA = "carcassonne-tiletie-oof-plan/v1"
# DESIGN §2.4 PRE-PILOT transplant: the autopsy measured tier1-greedy at 0.534x
# the primary judge, and the pricing run measured c_python = 9.85 worker-s/playout.
# It sizes the ETA print ONLY -- the §6 pilot replaces it and no estimate uses it.
C_TIER1_PREPILOT = 0.534 * 9.85


# --------------------------------------------------------------------------- #
# split                                                                        #
# --------------------------------------------------------------------------- #
def load_holdout_roots(path) -> set:
    d = json.loads(Path(path).read_text())
    return set(d["holdout_roots"])


def dev_rids(arms: dict, holdout: set) -> list:
    """Sorted dev rids. Sorted first so the shuffle is reproducible."""
    return sorted(r for r, v in arms.items() if v["root_id"] not in holdout)


def committed_order(rids: list, pilot_n: int, seed: int = PERMUTATION_SEED):
    """ONE shuffle, seed 20260814. Tail = pilot, head = main read, in order.

    Both slices are therefore uniform draws from the dev slice, from a single
    committed permutation -- no second seed, nothing to shop.
    """
    order = list(rids)
    random.Random(seed).shuffle(order)
    if pilot_n:
        return order[:-pilot_n], order[-pilot_n:]
    return order, []


def chunk_slices(order: list, chunks: int) -> list:
    """`chunks` near-equal contiguous slices of the committed order."""
    if chunks < 1:
        raise ValueError("chunks must be >= 1")
    n = len(order)
    out, start = [], 0
    for i in range(chunks):
        stop = ((i + 1) * n) // chunks
        out.append(order[start:stop])
        start = stop
    if sum(len(c) for c in out) != n:
        raise AssertionError("chunking lost positions")
    return out


# --------------------------------------------------------------------------- #
# plan dirs                                                                    #
# --------------------------------------------------------------------------- #
def read_leg_files(source_dir: Path, plan: dict) -> dict:
    """{"<profile>/leg<r>": [ (rid, raw_line), ... ]} from the source plan."""
    out = {}
    for key, info in sorted((plan.get("files") or {}).items()):
        p = Path(info["path"])
        if not p.is_file():                       # pooled jsonl are gitignored
            p = source_dir / Path(info["path"]).name
        if not p.is_file():
            raise SystemExit(f"REFUSING: missing source leg file for {key}: {info['path']}")
        rows = []
        for line in p.read_text().splitlines():
            if line.strip():
                rows.append((json.loads(line)["rid"], line))
        if len(rows) != int(info["n"]):
            raise SystemExit(f"REFUSING: {p} has {len(rows)} lines, plan says {info['n']}")
        out[key] = rows
    return out


def write_plan_dir(out_dir: Path, keep: set, *, source_plan: dict, source_arms: dict,
                   dropped: dict, leg_rows: dict, label: str, holdout: set,
                   forbidden: set = frozenset()) -> dict:
    """Write a run_tiletie-shaped plan dir restricted to `keep`."""
    bad_h = sorted(r for r in keep if source_arms[r]["root_id"] in holdout)
    if bad_h:
        raise SystemExit(f"G-HOLDOUT VIOLATION in {label}: {bad_h[:5]}")
    bad_p = sorted(keep & set(forbidden))
    if bad_p:
        raise SystemExit(f"G-PILOT VIOLATION in {label}: {bad_p[:5]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    files, counts, total_legs = {}, {}, 0
    for key, rows in sorted(leg_rows.items()):
        sel = [line for rid, line in rows if rid in keep]
        if not sel:
            continue
        path = out_dir / f"positions_{key.replace('/', '_')}.jsonl"
        path.write_text("".join(ln + "\n" for ln in sel))
        files[key] = {"n": len(sel), "path": str(path)}
        counts[key] = len(sel)
        total_legs += len(sel)

    arms = {r: source_arms[r] for r in sorted(keep)}
    strata = {}
    for v in arms.values():
        strata[v["stratum"]] = strata.get(v["stratum"], 0) + 1

    plan = {
        "schema": SCHEMA,
        "label": label,
        "design_doc": "measurement/tiletie_oof_20260814/DESIGN.md",
        "read_rule": "measurement/tiletie_oof_20260814/READ_RULE.md",
        # carried VERBATIM from the pricing plan: the dedupe is a property of how
        # the arms were built, and run_tiletie refuses a plan without it.
        "afterstate_dedupe": source_plan["afterstate_dedupe"],
        "cap_j": source_plan["cap_j"],
        "m_worlds": source_plan["m_worlds"],
        "max_arms": source_plan["max_arms"],
        "judge": "tier1-greedy",
        "world_seed_salt": "tiletie-v1",
        "permutation_seed": PERMUTATION_SEED,
        "source_plan_dir": str(source_plan.get("out_dir", "")),
        "n_positions": len(keep),
        "n_roots": len({v["root_id"] for v in arms.values()}),
        # run_tiletie.print_eta's required shape. c_tier1 is the DESIGN §2.4
        # PRE-PILOT transplant (autopsy 0.534x on the pricing run's measured
        # c_python 9.85); the pilot replaces it and it prices NOTHING but the ETA.
        "n_e4": strata.get("e4", 0),
        "n_selfplay": strata.get("selfplay", 0),
        "n_positions_capped": sum(1 for v in arms.values() if v.get("capped")),
        "mean_arms": (sum(len(v["arms"]) for v in arms.values()) / len(arms)) if arms else 0.0,
        "champ_pick_secs": 0.0,          # champion arm is already scored in ARMS.json
        "playout_secs": C_TIER1_PREPILOT,
        "oracle_worker_secs": total_legs * 2 * int(source_plan["m_worlds"]) * C_TIER1_PREPILOT,
        "eta_by_workers": {
            str(w): {
                "wall_secs": total_legs * 2 * int(source_plan["m_worlds"])
                * C_TIER1_PREPILOT / w,
                "wall_hours": total_legs * 2 * int(source_plan["m_worlds"])
                * C_TIER1_PREPILOT / (3600.0 * w),
            } for w in (14, 30)
        },
        "counts_by_stratum": strata,
        "counts_by_profile_leg": counts,
        "total_legs": total_legs,
        "total_arm_playouts": total_legs * 2 * int(source_plan["m_worlds"]),
        "files": files,
        "out_dir": str(out_dir),
    }
    (out_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=1))
    (out_dir / "ARMS.json").write_text(json.dumps(arms, indent=1))
    # copied WHOLE: the analytic-zero population is a property of the full supply
    # (INTERPRETATIONS I2), and zero_rates reads its counts from --full-supply-plan.
    (out_dir / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps(dropped, indent=1))
    return plan


# --------------------------------------------------------------------------- #
# in-family record staging (DESIGN §0.B -- filename-only firewall)             #
# --------------------------------------------------------------------------- #
def stage_if_records(src_root: Path, dst_root: Path, keep: set) -> dict:
    """Copy ONLY <profile>/leg<r>/records/<rid>.json whose stem is in `keep`.

    Selection is by FILENAME. A holdout record is never opened, parsed or read --
    the same firewall `mine_oracle_sep.load_oracle_means_slice` uses.
    """
    src_root, dst_root = Path(src_root), Path(dst_root)
    if not src_root.is_dir():
        raise SystemExit(f"REFUSING: in-family records root missing: {src_root}")
    copied, skipped = 0, 0
    for rec in sorted(src_root.glob("*/leg*/records/*.json")):
        if rec.stem in keep:
            rel = rec.relative_to(src_root)
            dst = dst_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(rec, dst)             # content-blind copy
            copied += 1
        else:
            skipped += 1
    leaked = sorted(p.stem for p in dst_root.glob("*/leg*/records/*.json")
                    if p.stem not in keep)
    if leaked:
        raise SystemExit(f"G-HOLDOUT VIOLATION staging in-family records: {leaked[:5]}")
    return {"src_root": str(src_root), "dst_root": str(dst_root),
            "copied": copied, "skipped_not_in_slice": skipped}


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source-dir", default=str(DEFAULT_SOURCE),
                    help="pricing pooled plan dir (POSITIONS_PLAN/ARMS/DROPPED + leg jsonl)")
    ap.add_argument("--holdout", default=str(DEFAULT_HOLDOUT))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--pilot-n", type=int, default=20)
    ap.add_argument("--chunks", type=int, default=4)
    ap.add_argument("--if-records", default=DEFAULT_IF_RECORDS,
                    help="live clair-puct records root to stage the dev slice from")
    ap.add_argument("--stage-if", action="store_true",
                    help="also stage the in-family dev records (DESIGN §0.B)")
    ap.add_argument("--no-expect", action="store_true",
                    help="skip the 522/279 dev-slice assertion (tests only)")
    a = ap.parse_args(argv)

    src = Path(a.source_dir)
    out = Path(a.out_dir)
    source_plan = json.loads((src / "POSITIONS_PLAN.json").read_text())
    source_arms = json.loads((src / "ARMS.json").read_text())
    dropped = json.loads((src / "DROPPED_ALL_TRANSPOSITION.json").read_text())
    holdout = load_holdout_roots(a.holdout)

    dev = dev_rids(source_arms, holdout)
    n_roots = len({source_arms[r]["root_id"] for r in dev})
    if not a.no_expect and (len(dev) != EXPECT_DEV_POSITIONS or n_roots != EXPECT_DEV_ROOTS):
        raise SystemExit(f"REFUSING: dev slice is {len(dev)} positions / {n_roots} roots, "
                         f"DESIGN §5 says {EXPECT_DEV_POSITIONS}/{EXPECT_DEV_ROOTS}")

    main_order, pilot = committed_order(dev, a.pilot_n)
    chunks = chunk_slices(main_order, a.chunks)
    leg_rows = read_leg_files(src, source_plan)

    (out).mkdir(parents=True, exist_ok=True)
    (out / "PILOT_RIDS.json").write_text(json.dumps(
        {"schema": SCHEMA, "seed": PERMUTATION_SEED, "n": len(pilot),
         "note": "DESIGN §6 cost pilot -- EXCLUDED from the main read. Tail of the "
                 "single committed permutation of the 522-position dev slice.",
         "rids": pilot}, indent=1))
    (out / "POSITION_ORDER.json").write_text(json.dumps(
        {"schema": SCHEMA, "seed": PERMUTATION_SEED, "n_dev": len(dev),
         "n_main": len(main_order), "n_pilot": len(pilot), "chunks": a.chunks,
         "chunk_sizes": [len(c) for c in chunks],
         "note": "DESIGN §0.A -- load_positions_jsonl sorts by root_id, so partial "
                 "completion is unbiased at CHUNK granularity only.",
         "order": main_order}, indent=1))

    pilot_set = set(pilot)
    written = {}
    written["pilot"] = write_plan_dir(
        out / "positions_pilot", set(pilot), source_plan=source_plan,
        source_arms=source_arms, dropped=dropped, leg_rows=leg_rows,
        label="pilot", holdout=holdout)
    written["main"] = write_plan_dir(
        out / "positions_main", set(main_order), source_plan=source_plan,
        source_arms=source_arms, dropped=dropped, leg_rows=leg_rows,
        label="main", holdout=holdout, forbidden=pilot_set)
    for i, ch in enumerate(chunks, 1):
        written[f"chunk{i}"] = write_plan_dir(
            out / f"positions_chunk{i}", set(ch), source_plan=source_plan,
            source_arms=source_arms, dropped=dropped, leg_rows=leg_rows,
            label=f"chunk{i}", holdout=holdout, forbidden=pilot_set)

    staged = None
    if a.stage_if:
        staged = stage_if_records(Path(a.if_records),
                                  Path("/mnt/c/carc-shared/tiletie_oof_20260814/"
                                       "if_dev/clair-puct"),
                                  set(main_order))

    summary = {
        "schema": SCHEMA,
        "dev_positions": len(dev), "dev_roots": n_roots,
        "pilot_n": len(pilot), "main_n": len(main_order),
        "chunks": [{"name": f"chunk{i}", "n": len(c),
                    "legs": written[f'chunk{i}']["total_legs"],
                    "playouts": written[f'chunk{i}']["total_arm_playouts"]}
                   for i, c in enumerate(chunks, 1)],
        "main_legs": written["main"]["total_legs"],
        "main_playouts": written["main"]["total_arm_playouts"],
        "pilot_legs": written["pilot"]["total_legs"],
        "pilot_playouts": written["pilot"]["total_arm_playouts"],
        "if_staging": staged,
    }
    (out / "PLAN_SUMMARY.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
