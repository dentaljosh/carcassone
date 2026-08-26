#!/usr/bin/env python3
"""F4 JUDGE LEG RUNNER — the R1 leg machinery with the JUDGE swapped, nothing else.

F4_PREREG.md §2. This is `run/04_run_r1.sh` re-expressed in python so it can live
self-contained in `/home/doctor/evloss_autopsy/run/f4/` on the laptop without pulling in
`common.sh` / `config.env` (which carry R0/R1 state markers this leg must not touch).

Every knob that is not the judge is copied from the R1 launcher verbatim:

    positions   <share>/positions/positions_<leg>.jsonl   (the byte-identical R1 files)
    M           32
    salt        evloss-autopsy-20260824-v1                (⚠️ CRN: identical to R1)
    profile     walled
    --strict-crn, --resume, nice 19, wall cap 7200

and exactly two things change:

    --oracle-policy  clair-puct  ->  tier1-greedy     (the OUT-OF-FAMILY judge)
    --backend        rust        ->  python           (forced: there is no Rust
                                                       RuleBasedPlayer, and porting one
                                                       would destroy the point)
    --out-root       <share>/judge -> <share>/judge_f4_tier1greedy   (a NEW tree; the R1
                                                       tree is never written to)

`--oracle-sims` is NOT passed: `ORACLE_POLICIES["tier1-greedy"]["uses_oracle_sims"]` is
False — the greedy continuation has no search.

⚠️ RESUME TRAP, handled exactly as R1 handled it: the pilot writes a record for a FAILED
position too and `--resume` skips on file existence alone, so every non-success record is
quarantined before each leg (the `run/r1_resume_clean.py` rule, re-implemented here to keep
this file self-contained).

⚠️ RULES PROFILE: `CARCASSONNE_FIX_R9` is import-latched. `walled` expects it
UNSET/0 (`rules_profile.walled.r9_env_expected = False`) — the launcher shell sources
`champ_env.sh` and then unsets it, exactly as `run/common.sh` does. This script re-asserts
that the environment is correct before spawning anything, and refuses otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

# ---- copied from the R1 launcher (config.env / config.local.env) ------------ #
R1_SALT = "evloss-autopsy-20260824-v1"
R1_M_WORLDS = 32
PROFILE = "walled"
WALL_CAP_SECS = 7200
NICE = 19
ORACLE_POLICY = "tier1-greedy"
BACKEND = "python"
OUT_SUBTREE = "judge_f4_tier1greedy"

# The cost ladder of F4_PREREG.md §2.1. First rung whose projected wall fits the budget.
RUNGS = {
    "L1": ("leaf", "sib2", "sib3", "sib4", "rnd"),
    "L2": ("leaf", "sib2", "sib3", "sib4"),
    "L3": ("argmax",),
}


# --------------------------------------------------------------------------- #
def resume_clean(leg_dir: Path) -> dict:
    """run/r1_resume_clean.py's rule: a record is a success iff `ok is True` and
    `crn_verified is not False`. Everything else is moved aside so --resume re-queues it."""
    recs = leg_dir / "records"
    if not recs.is_dir():
        return {"leg": leg_dir.name, "records": 0, "quarantined": 0, "errors": {}}
    qroot = leg_dir / "quarantine" / time.strftime("%Y%m%dT%H%M%S")
    errs, n, q = Counter(), 0, 0
    for p in sorted(recs.glob("*.json")):
        n += 1
        try:
            d = json.loads(p.read_text())
        except Exception as exc:                                       # noqa: BLE001
            d, errs[f"unparseable:{type(exc).__name__}"] = None, 1
        bad = None
        if d is None:
            bad = "unparseable"
        elif d.get("ok") is not True:
            bad = str(d.get("error") or "ok_false")
        elif d.get("crn_verified") is False:
            bad = "crn_verified_false"
        if bad:
            errs[bad.split(":")[0][:60]] += 1
            qroot.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(qroot / p.name))
            q += 1
    return {"leg": leg_dir.name, "records": n, "quarantined": q, "errors": dict(errs)}


def gate_leg(pos_path: Path, leg_dir: Path) -> dict:
    """04_run_r1.sh's post-leg gate, verbatim in behaviour."""
    rids = [json.loads(l)["rid"] for l in pos_path.read_text().splitlines() if l.strip()]
    recs = leg_dir / "records"
    missing, bad, capped, nocrn = [], [], [], []
    for rid in rids:
        p = recs / f"{rid}.json"
        if not p.exists():
            missing.append(rid)
            continue
        d = json.loads(p.read_text())
        if d.get("ok") is not True:
            bad.append((rid, d.get("error")))
            if "wall cap" in str(d.get("error")):
                capped.append(rid)
        if d.get("crn_verified") is not True:
            nocrn.append(rid)
    return {"leg": leg_dir.name, "n": len(rids), "missing": len(missing),
            "failed": len(bad), "wall_capped": len(capped),
            "not_crn_verified": len(nocrn),
            "examples": [{"rid": r, "error": str(e)[:200]} for r, e in bad[:5]],
            "ok": not (missing or bad or nocrn)}


def build_argmax_positions(share: Path, out_path: Path) -> int:
    """Rung L3 only: one row per rid whose `pick_b` is the position's BANKED clair-puct
    argmax arm. Reads `<share>/judge/<arm>/records` (read-only) and
    `<share>/positions/positions_meta.jsonl`; writes a NEW positions file.

    The row is otherwise copied from that arm's own R1 positions row, so every
    pass-through field (checksum, actions, root_player, stratum, …) is byte-identical to
    what R1 fed the harness — only `stratifier_rule` is restamped.
    """
    arms = ("leaf", "sib2", "sib3", "sib4")
    deltas: dict[str, dict[str, float]] = {}
    for arm in arms:
        d = share / "judge" / arm / "records"
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            rec = json.loads(p.read_text())
            if rec.get("ok") is True and rec.get("crn_verified") is True:
                deltas.setdefault(rec["rid"], {})[arm] = float(rec["delta"])
    rows_by_arm: dict[str, dict[str, dict]] = {}
    for arm in arms:
        f = share / "positions" / f"positions_{arm}.jsonl"
        if not f.exists():
            continue
        rows_by_arm[arm] = {}
        for line in f.read_text().splitlines():
            if line.strip():
                o = json.loads(line)
                rows_by_arm[arm][o["rid"]] = o
    n = 0
    with out_path.open("w") as fh:
        for rid in sorted(deltas):
            arm = max(deltas[rid].items(), key=lambda kv: kv[1])[0]
            row = rows_by_arm.get(arm, {}).get(rid)
            if row is None:
                continue
            row = dict(row)
            row["stratifier_rule"] = f"evloss-autopsy-f4|arm=argmax({arm})"
            row["f4_argmax_arm"] = arm
            fh.write(json.dumps(row) + "\n")
            n += 1
    return n


# --------------------------------------------------------------------------- #
def assert_env() -> dict:
    """The rules-profile env contract R1 ran under, re-asserted before anything spawns."""
    r9 = os.environ.get("CARCASSONNE_FIX_R9")
    if r9 not in (None, "", "0"):
        raise SystemExit(
            f"[F4-BROKEN] CARCASSONNE_FIX_R9={r9!r} but rules profile {PROFILE!r} expects it "
            f"UNSET/0 (rules_profile.walled.r9_env_expected=False). Source champ_env.sh and "
            f"`unset CARCASSONNE_FIX_R9` before launching, exactly as run/common.sh does.")
    need = {"CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
            "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
            "CARCASSONNE_USE_FLAT_LEAF": "1"}
    missing = {k: os.environ.get(k) for k, v in need.items() if os.environ.get(k) != v}
    if missing:
        raise SystemExit(f"[F4-BROKEN] champ_env.sh not sourced (or wrong): {missing}")
    return {"CARCASSONNE_FIX_R9": r9, **{k: os.environ.get(k) for k in need}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--share", required=True,
                    help="e.g. /mnt/carc-shared/evloss_autopsy_20260824 (laptop spelling)")
    ap.add_argument("--repo", default="/home/doctor/projects/carcassone")
    ap.add_argument("--python", default=None, help="interpreter (default: this one)")
    ap.add_argument("--workers", type=int, required=True)
    ap.add_argument("--rung", choices=sorted(RUNGS), default="L1")
    ap.add_argument("--legs", default=None,
                    help="explicit comma list, overrides --rung (smoke use)")
    ap.add_argument("--head", type=int, default=0,
                    help="SMOKE ONLY: score just the first N rows of each leg's positions "
                         "file (written to a temp positions file; the real leg is untouched)")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--sentinel", default=None,
                    help="path of the completion sentinel JSON (default <share>/F4_DONE.json)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    share = Path(args.share)
    py = args.python or sys.executable
    pilot = Path(args.repo) / "scripts/measurement_infra/oracle_score_pilot.py"
    if not pilot.exists():
        raise SystemExit(f"[F4-BROKEN] pilot not found: {pilot}")
    out_root = Path(args.out_root) if args.out_root else share / OUT_SUBTREE
    out_root.mkdir(parents=True, exist_ok=True)
    env_stamp = assert_env()

    legs = ([s.strip() for s in args.legs.split(",") if s.strip()]
            if args.legs else list(RUNGS[args.rung]))

    started = time.time()
    report = {"schema": "carcassonne-evloss-autopsy-f4-leg/v1",
              "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
              "share": str(share), "out_root": str(out_root), "rung": args.rung,
              "legs": legs, "workers": args.workers, "head": args.head,
              "judge": {"oracle_policy": ORACLE_POLICY, "backend": BACKEND,
                        "m": R1_M_WORLDS, "salt": R1_SALT, "rules_profile": PROFILE},
              "env": env_stamp, "host": os.uname().nodename,
              "legs_run": [], "ok": None}

    for leg in legs:
        if leg == "argmax":
            pos = share / "positions" / "positions_f4_argmax.jsonl"
            if not pos.exists():
                n = build_argmax_positions(share, pos)
                print(f"[f4] built {pos} with {n} rows", flush=True)
        else:
            pos = share / "positions" / f"positions_{leg}.jsonl"
        if not pos.exists():
            raise SystemExit(f"[F4-BROKEN] missing positions file {pos}")

        if args.head:
            head_pos = out_root / f"positions_{leg}_head{args.head}.jsonl"
            lines = [l for l in pos.read_text().splitlines() if l.strip()][:args.head]
            head_pos.write_text("\n".join(lines) + "\n")
            pos = head_pos

        leg_dir = out_root / leg
        leg_dir.mkdir(parents=True, exist_ok=True)
        rc_info = resume_clean(leg_dir)
        print(f"[f4] resume-clean {leg}: {rc_info}", flush=True)

        cmd = ["nice", "-n", str(NICE), py, "-u", str(pilot),
               "--positions-jsonl", str(pos),
               "--backend", BACKEND,
               "--rules-profile", PROFILE,
               "--oracle-policy", ORACLE_POLICY,
               "--m", str(R1_M_WORLDS),
               "--world-seed-salt", R1_SALT,
               "--strict-crn",
               "--workers", str(args.workers),
               "--wall-cap", str(WALL_CAP_SECS),
               "--resume",
               "--out-root", str(out_root),
               "--out-subdir", leg]
        print(f"[f4] leg {leg}: {' '.join(cmd)}", flush=True)
        if args.dry_run:
            report["legs_run"].append({"leg": leg, "dry_run": True, "cmd": cmd})
            continue

        t0 = time.time()
        rc = subprocess.call(cmd)
        wall = time.time() - t0
        gate = gate_leg(pos, leg_dir)
        entry = {"leg": leg, "returncode": rc, "wall_secs": round(wall, 1),
                 "resume_clean": rc_info, "gate": gate,
                 "positions_file": str(pos)}
        # per-position worker-seconds, from the records themselves (never the first
        # completions — the ORDER-STATISTIC trap; this is the mean over ALL records)
        es = []
        for p in (leg_dir / "records").glob("*.json"):
            d = json.loads(p.read_text())
            if d.get("ok") and d.get("elapsed_secs"):
                es.append(float(d["elapsed_secs"]))
        if es:
            es.sort()
            entry["elapsed_secs"] = {
                "n": len(es), "mean": round(sum(es) / len(es), 2),
                "median": round(es[len(es) // 2], 2), "max": round(es[-1], 2)}
        report["legs_run"].append(entry)
        print(f"[f4] leg {leg} done rc={rc} wall={wall:.0f}s gate={gate}", flush=True)
        if rc != 0 or not gate["ok"]:
            report["ok"] = False
            report["failed_leg"] = leg
            break
    else:
        report["ok"] = True

    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["total_wall_secs"] = round(time.time() - started, 1)
    sent = Path(args.sentinel) if args.sentinel else share / "F4_DONE.json"
    if args.head:                      # a smoke never stamps the real sentinel
        sent = out_root / f"F4_SMOKE_head{args.head}.json"
    sent.write_text(json.dumps(report, indent=2))
    print(f"[f4] sentinel -> {sent}", flush=True)
    print(json.dumps({k: report[k] for k in ("ok", "rung", "legs", "total_wall_secs")}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
