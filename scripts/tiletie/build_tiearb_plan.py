#!/usr/bin/env python3
"""Build the TERMINAL-GROUNDED TIE ARBITRATION plan (measurement/tiearb_20260816).

Pure plan surgery -- it scores nothing and reads no oracle VALUE. It:

  1. selects the HOLDOUT slice of the pricing corpus's pooled plan (root_id IN
     ``tiletie_mining_20260814/HOLDOUT_ROOTS.json``) -- DESIGN §3.1 says that is
     exactly 211 positions over 120 roots, and this refuses to run otherwise;
  2. draws the committed seeded permutation ONCE
     (``random.Random(20260816).shuffle(sorted(holdout_rids))``) and writes it to
     ``POSITION_ORDER.json`` BEFORE anything is launched (DESIGN §5);
  3. cuts that order into ``--chunks`` near-equal sequential chunks (DESIGN §5 --
     ``oracle_score_pilot.load_positions_jsonl`` sorts by ``root_id``, so a
     partial run is only an unbiased subsample at CHUNK granularity, never at
     line granularity);
  4. writes one ``run_tiletie``-shaped plan dir per chunk, plus
     ``positions_holdout`` (all 211, for the analyser) and ``positions_pilot``
     (the 20 DEV rids of ``tiletie_oof_20260814/PILOT_RIDS.json``, DESIGN §5).

Guards asserted BEFORE any file is written:

  * ``G-SLICE``  -- every rid in a holdout plan dir has ``root_id`` IN the
    holdout set;
  * the pilot dir contains NO holdout root (it is the DEV cost pilot);
  * the chunks partition the 211 exactly -- no overlap, no loss.

Nothing here reads a record, a value, or a statistic.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
DEFAULT_HOLDOUT = REPO / "measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json"
DEFAULT_PILOT_RIDS = REPO / "measurement/tiletie_oof_20260814/PILOT_RIDS.json"
DEFAULT_OUT = REPO / "measurement/tiearb_20260816"

PERMUTATION_SEED = 20260816          # DESIGN §5 -- committed, one seed, one shuffle
EXPECT_HOLDOUT_POSITIONS = 211       # DESIGN §3.1 -- mechanically re-verified
EXPECT_HOLDOUT_ROOTS = 120
SCHEMA = "carcassonne-tiearb-plan/v1"
# DESIGN §5: the OOF cost pilot MEASURED c_tier1 = 2.1783 worker-s/playout for
# this judge on this corpus. It sizes the ETA print ONLY -- no estimate uses it.
C_TIER1 = 2.1783
ETA_WORKERS = (20, 30)


# --------------------------------------------------------------------------- #
# slice                                                                        #
# --------------------------------------------------------------------------- #
def load_holdout_roots(path) -> set:
    d = json.loads(Path(path).read_text())
    return set(d["holdout_roots"])


def load_pilot_rids(path) -> list:
    """The OOF run's own 20 DEV cost-pilot rids (DESIGN §5)."""
    d = json.loads(Path(path).read_text())
    return list(d["rids"])


def holdout_rids(arms: dict, holdout: set) -> list:
    """Sorted holdout rids. Sorted FIRST so the shuffle is reproducible."""
    return sorted(r for r, v in arms.items() if v["root_id"] in holdout)


def committed_order(rids: list, seed: int = PERMUTATION_SEED) -> list:
    """ONE shuffle, seed 20260816, of the SORTED rid list. Nothing else."""
    order = sorted(rids)
    random.Random(seed).shuffle(order)
    return order


def chunk_slices(order: list, chunks: int) -> list:
    """`chunks` near-equal contiguous slices of the committed order.

    Copied verbatim from build_oof_plan.chunk_slices -- same partition property.
    """
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
        if not p.is_file():                       # pooled jsonl paths are repo-relative
            p = Path(source_dir) / Path(info["path"]).name
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
                   require_holdout: bool) -> dict:
    """Write a run_tiletie-shaped plan dir restricted to `keep`.

    `require_holdout=True`  -> G-SLICE: every kept rid MUST be a holdout root.
    `require_holdout=False` -> the mirror guard: no kept rid may be a holdout
                               root (the DEV cost pilot).
    Both are asserted BEFORE a single byte is written.
    """
    missing = sorted(r for r in keep if r not in source_arms)
    if missing:
        raise SystemExit(f"REFUSING: unknown rid(s) in {label}: {missing[:5]}")
    if require_holdout:
        bad = sorted(r for r in keep if source_arms[r]["root_id"] not in holdout)
        if bad:
            raise SystemExit(f"G-SLICE VIOLATION in {label}: non-holdout rid(s) {bad[:5]}")
    else:
        bad = sorted(r for r in keep if source_arms[r]["root_id"] in holdout)
        if bad:
            raise SystemExit(f"G-SLICE VIOLATION in {label}: holdout rid(s) leaked into a "
                             f"DEV dir: {bad[:5]}")

    out_dir = Path(out_dir)
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

    m = int(source_plan["m_worlds"])
    playouts = total_legs * 2 * m
    plan = {
        "schema": SCHEMA,
        "label": label,
        "design_doc": "measurement/tiearb_20260816/DESIGN.md",
        "read_rule": "measurement/tiearb_20260816/READ_RULE.md",
        # carried VERBATIM from the pricing plan: the dedupe is a property of how
        # the arms were built, and run_tiletie refuses a plan without it.
        "afterstate_dedupe": source_plan["afterstate_dedupe"],
        "cap_j": source_plan["cap_j"],
        "m_worlds": m,
        "max_arms": source_plan["max_arms"],
        "judge": "tier1-greedy",
        "world_seed_salt": "tiletie-v1",        # DESIGN §3.3 -- forced, not chosen
        "permutation_seed": PERMUTATION_SEED,
        "source_plan_dir": str(source_plan.get("out_dir", "")),
        "slice": "holdout" if require_holdout else "dev",
        "n_positions": len(keep),
        "n_roots": len({v["root_id"] for v in arms.values()}),
        # run_tiletie.print_eta's required shape. c_tier1 is the OOF pilot's
        # MEASURED 2.1783 worker-s/playout; it prices NOTHING but the ETA.
        "n_e4": strata.get("e4", 0),
        "n_selfplay": strata.get("selfplay", 0),
        "n_positions_capped": sum(1 for v in arms.values() if v.get("capped")),
        "mean_arms": (sum(len(v["arms"]) for v in arms.values()) / len(arms)) if arms else 0.0,
        "champ_pick_secs": 0.0,          # champion arm is already scored in ARMS.json
        "playout_secs": C_TIER1,
        "oracle_worker_secs": playouts * C_TIER1,
        "eta_by_workers": {
            str(w): {"wall_secs": playouts * C_TIER1 / w,
                     "wall_hours": playouts * C_TIER1 / (3600.0 * w)}
            for w in ETA_WORKERS
        },
        "counts_by_stratum": strata,
        "counts_by_profile_leg": counts,
        "total_legs": total_legs,
        "total_arm_playouts": playouts,
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
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source-dir", default=str(DEFAULT_SOURCE),
                    help="pricing pooled plan dir (POSITIONS_PLAN/ARMS/DROPPED + leg jsonl)")
    ap.add_argument("--holdout", default=str(DEFAULT_HOLDOUT))
    ap.add_argument("--pilot-rids", default=str(DEFAULT_PILOT_RIDS),
                    help="the OOF run's DEV cost-pilot rids (DESIGN §5)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--chunks", type=int, default=4)
    ap.add_argument("--no-expect", action="store_true",
                    help="skip the 211/120 holdout-slice assertion (tests only)")
    a = ap.parse_args(argv)

    src = Path(a.source_dir)
    out = Path(a.out_dir)
    source_plan = json.loads((src / "POSITIONS_PLAN.json").read_text())
    source_arms = json.loads((src / "ARMS.json").read_text())
    dropped = json.loads((src / "DROPPED_ALL_TRANSPOSITION.json").read_text())
    holdout = load_holdout_roots(a.holdout)

    hold = holdout_rids(source_arms, holdout)
    n_roots = len({source_arms[r]["root_id"] for r in hold})
    if not a.no_expect and (len(hold) != EXPECT_HOLDOUT_POSITIONS
                            or n_roots != EXPECT_HOLDOUT_ROOTS):
        raise SystemExit(
            f"REFUSING: holdout slice is {len(hold)} positions / {n_roots} roots, "
            f"DESIGN §3.1 says {EXPECT_HOLDOUT_POSITIONS}/{EXPECT_HOLDOUT_ROOTS}")

    order = committed_order(hold)
    chunks = chunk_slices(order, a.chunks)
    # chunks partition the slice EXACTLY -- asserted before anything is written.
    flat = [r for c in chunks for r in c]
    if sorted(flat) != sorted(hold) or len(flat) != len(set(flat)):
        raise SystemExit("REFUSING: chunks do not partition the holdout slice exactly")

    pilot = load_pilot_rids(a.pilot_rids)
    pilot_leak = sorted(r for r in pilot if source_arms[r]["root_id"] in holdout)
    if pilot_leak:
        raise SystemExit(f"G-SLICE VIOLATION: pilot rids are holdout roots: {pilot_leak[:5]}")

    leg_rows = read_leg_files(src, source_plan)

    out.mkdir(parents=True, exist_ok=True)
    (out / "POSITION_ORDER.json").write_text(json.dumps(
        {"schema": SCHEMA, "seed": PERMUTATION_SEED,
         "n": len(order), "n_roots": n_roots, "chunks": a.chunks,
         "chunk_sizes": [len(c) for c in chunks],
         "note": "DESIGN §5 -- ONE committed shuffle of the SORTED holdout rid list, "
                 "written BEFORE launch. load_positions_jsonl sorts by root_id, so "
                 "partial completion is unbiased at CHUNK granularity only.",
         "order": order}, indent=1))

    written = {}
    written["holdout"] = write_plan_dir(
        out / "positions_holdout", set(order), source_plan=source_plan,
        source_arms=source_arms, dropped=dropped, leg_rows=leg_rows,
        label="holdout", holdout=holdout, require_holdout=True)
    for i, ch in enumerate(chunks, 1):
        written[f"chunk{i}"] = write_plan_dir(
            out / f"positions_chunk{i}", set(ch), source_plan=source_plan,
            source_arms=source_arms, dropped=dropped, leg_rows=leg_rows,
            label=f"chunk{i}", holdout=holdout, require_holdout=True)
    written["pilot"] = write_plan_dir(
        out / "positions_pilot", set(pilot), source_plan=source_plan,
        source_arms=source_arms, dropped=dropped, leg_rows=leg_rows,
        label="pilot", holdout=holdout, require_holdout=False)

    def eta(playouts, w=30):
        return {"playouts": playouts,
                "worker_hours": playouts * C_TIER1 / 3600.0,
                f"wall_hours_at_W{w}": playouts * C_TIER1 / (3600.0 * w),
                f"wall_minutes_at_W{w}": playouts * C_TIER1 / (60.0 * w)}

    summary = {
        "schema": SCHEMA,
        "design_doc": "measurement/tiearb_20260816/DESIGN.md",
        "read_rule": "measurement/tiearb_20260816/READ_RULE.md",
        "permutation_seed": PERMUTATION_SEED,
        "c_tier1_worker_s_per_playout": C_TIER1,
        "c_tier1_provenance": ("MEASURED by the 2026-08-14 OOF cost pilot on this judge and "
                               "this corpus (PILOT.json cost.c_tier1_worker_s_per_playout). "
                               "It sizes the ETA ONLY."),
        "holdout_positions": len(order), "holdout_roots": n_roots,
        "pilot_n": len(pilot),
        "dirs": {
            name: {
                "n_positions": p["n_positions"], "n_roots": p["n_roots"],
                "legs": p["total_legs"], "playouts": p["total_arm_playouts"],
                "counts_by_stratum": p["counts_by_stratum"],
                "counts_by_profile_leg": p["counts_by_profile_leg"],
                "eta": eta(p["total_arm_playouts"]),
                "out_dir": p["out_dir"],
            } for name, p in written.items()
        },
        "chunks": [{"name": f"chunk{i}", "n": len(c),
                    "legs": written[f"chunk{i}"]["total_legs"],
                    "playouts": written[f"chunk{i}"]["total_arm_playouts"]}
                   for i, c in enumerate(chunks, 1)],
        "totals": {
            "holdout_legs": written["holdout"]["total_legs"],
            "holdout_playouts": written["holdout"]["total_arm_playouts"],
            "holdout_eta": eta(written["holdout"]["total_arm_playouts"]),
            "pilot_legs": written["pilot"]["total_legs"],
            "pilot_playouts": written["pilot"]["total_arm_playouts"],
            "pilot_eta": eta(written["pilot"]["total_arm_playouts"], 20),
        },
        "governance": ("⚠️ THIS PLAN SPENDS THE HOLDOUT (DESIGN §3.1). Measurement only, "
                       "0 games on every branch."),
    }
    (out / "PLAN_SUMMARY.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
