#!/usr/bin/env python3
"""JCZ DISAGREEMENT MINING — the scoring driver.

Pre-registration: measurement/jcz_mining_20260809/MINING_PREREG.md (committed
BEFORE any extraction or scoring code ran). This driver ONLY decides worker
split, judge order and the process/env split; WHAT gets scored was fixed by the
(sibling) extractor `mine_disagreements.py` before this ever runs — this file
never edits STRATA.json / POSITIONS*.jsonl, only reads them.

SIGN CONVENTION (load-bearing, repeated everywhere it matters): every mined
position's `pick_a` is OUR leaf-argmax pick and `pick_b` is JCZ's played pick.
`oracle_score_pilot.position_delta` returns ``delta = mean(V_B - V_A)``, so
**``delta > 0`` means JCZ's pick was better.** `analyze_mining.py`'s entire
decision map assumes this sign; nothing in this driver may reorder pick_a/pick_b
in any position source.

RULES EPOCH. Single epoch, `fixed_v1` — ONE leg per judge (not per-epoch like the
farm-war discriminator's three-epoch split), because `CARCASSONNE_FIX_R9` is an
import-time latch and this run only ever needs it set once, correctly, before
either judge's subprocess starts (mirrors `run_farmwar.r9_for`).

JUDGE ORDER. Judges run SEQUENTIALLY, primary (`clair-puct`) first, so the
deciding statistic (primary, scores ALL strata via POSITIONS.jsonl) lands before
the sign-only secondary (`tier1-greedy`, A+B only via POSITIONS_AB.jsonl per
PREREG §5) even starts, and the box is never oversubscribed by two legs at once.
A failed leg (`rc != 0`) STOPS the run before the next judge.

WORKER CAP. --workers is HARD-CAPPED at 14 — the box is DRAM-latency-bound
(W* ~= 14-16 regardless of the 16C/32T core count) AND it is Joshua's
interactive machine. This is a safety invariant, not a tuning knob: a value
above 14 is clamped with a loud warning, never silently honoured and never an
error.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "scripts/measurement_infra/oracle_score_pilot.py"
MINING = REPO / "measurement/jcz_mining_20260809/mining"
PREREG = "measurement/jcz_mining_20260809/MINING_PREREG.md"

#: Fixed for the whole run — distinct from the pilot's own default salt so records
#: from this run can never collide with another harness's, and every judge/leg
#: shares the same CRN worlds for a given position.
WORLD_SEED_SALT = "jcz-mining-v1"

#: Hard safety cap. NOT a tuning knob — see module docstring "WORKER CAP".
MAX_WORKERS = 14

#: (judge, {description, positions_attr}) — the CANONICAL order. Always iterated in
#: this order regardless of what order --judges lists, so the primary judge runs
#: first even if a caller passes them reversed.
JUDGES = (
    ("clair-puct", {
        "description": "PRIMARY — in-family clairvoyant PUCT over the champion's "
                       "own curve125 leaf (champion_factory.build_clairvoyant_"
                       "champion). Scores ALL strata (A, B, C) via POSITIONS.jsonl. "
                       "The deciding statistic.",
        "positions_attr": "positions",
    }),
    ("tier1-greedy", {
        "description": "SECONDARY — out-of-family Tier-1 greedy RuleBasedPlayer "
                       "(no search, v1 OBJECT leaf). SIGN ONLY, never a magnitude "
                       "comparison. Scores STRAT-A and STRAT-B only via "
                       "POSITIONS_AB.jsonl (PREREG §5) — C's control role does not "
                       "need a second judge.",
        "positions_attr": "positions_ab",
    }),
)


def clamp_workers(w: int) -> int:
    """Hard-cap at MAX_WORKERS, warning loudly on a larger request. Never errors —
    a caller asking for more just gets less, same as the box would give them
    anyway once DRAM latency saturates (and this is Joshua's interactive
    machine, so "less" is also the considerate answer)."""
    w = int(w)
    if w > MAX_WORKERS:
        print(f"[run_mining] WARNING: --workers {w} exceeds the hard cap "
              f"{MAX_WORKERS} (the box is DRAM-latency-bound, W* ~14-16 "
              "regardless of core count, AND this is Joshua's interactive "
              f"machine) — clamping to {MAX_WORKERS}.", file=sys.stderr)
        return MAX_WORKERS
    return w


def r9_env_for_fixed_v1() -> str:
    """`CARCASSONNE_FIX_R9` is import-time latched, so it must be resolved and set
    in the CHILD env before the subprocess imports carcassonne_ai — never inferred
    after the fact. Mirrors `run_farmwar.r9_for`, reading the expectation off the
    rules_profile registry rather than hardcoding it, so a profile change cannot
    silently desync this launcher from the engine."""
    from carcassonne_ai import rules_profile
    return "1" if rules_profile.resolve("fixed_v1").r9_env_expected else "0"


def _count_lines(path) -> int:
    return sum(1 for line in Path(path).read_text().splitlines() if line.strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="JCZ disagreement-mining scoring driver — runs the "
                    "clair-puct (primary, all strata) and tier1-greedy "
                    "(secondary, sign-only, A+B) legs of oracle_score_pilot.py "
                    "sequentially. See module docstring for the sign convention "
                    "and the worker-cap rationale.")
    ap.add_argument("--strata", default=str(MINING / "STRATA.json"))
    ap.add_argument("--positions", default=str(MINING / "POSITIONS.jsonl"))
    ap.add_argument("--positions-ab", default=str(MINING / "POSITIONS_AB.jsonl"))
    ap.add_argument("--out-root", default="/mnt/c/carc-shared/jcz_mining_20260809")
    ap.add_argument("--m", type=int, default=32)
    ap.add_argument("--oracle-sims", type=int, default=100)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--judges", nargs="+", default=[j for j, _ in JUDGES],
                    choices=[j for j, _ in JUDGES],
                    help="which judges to run (canonical order is always "
                         "enforced: clair-puct before tier1-greedy)")
    a = ap.parse_args(argv)

    strata_path = Path(a.strata)
    if not strata_path.exists():
        print(f"[run_mining] REFUSING: strata file not found: {strata_path}",
              file=sys.stderr)
        return 3
    strata = json.loads(strata_path.read_text())
    if not strata.get("gate_ok"):
        print("[run_mining] REFUSING: strata['gate_ok'] is not true — the "
              "pre-registered n>=min_n_gate sampling gate did not pass. "
              f"{strata.get('gate_verdict', '')}", file=sys.stderr)
        return 3

    workers = clamp_workers(a.workers)
    k_late = strata.get("k_late")

    MINING.mkdir(parents=True, exist_ok=True)
    positions_by_attr = {"positions": a.positions, "positions_ab": a.positions_ab}

    judge_order = [j for j, _ in JUDGES if j in a.judges]
    print(f"[run_mining] gate_ok={strata['gate_ok']} k_late={k_late} M={a.m} "
          f"oracle_sims={a.oracle_sims} W={workers} (requested {a.workers}) "
          f"salt={WORLD_SEED_SALT} judges={judge_order}")

    r9 = r9_env_for_fixed_v1()
    print(f"[run_mining] rules_profile=fixed_v1 CARCASSONNE_FIX_R9={r9}")

    legs = []
    t0 = time.time()
    for judge in judge_order:
        meta = dict(JUDGES)[judge]
        pos_file = positions_by_attr[meta["positions_attr"]]
        if not Path(pos_file).exists():
            print(f"[run_mining] REFUSING leg {judge}: positions file not "
                  f"found: {pos_file}", file=sys.stderr)
            return 3
        n_positions = _count_lines(pos_file)

        env = dict(os.environ)
        env["CARCASSONNE_FIX_R9"] = r9
        env.setdefault("OPENBLAS_NUM_THREADS", "1")
        env.setdefault("OMP_NUM_THREADS", "1")
        env.setdefault("MKL_NUM_THREADS", "1")

        log = MINING / f"leg_{judge}.log"
        cmd = ["nice", "-n", "19", sys.executable, str(PILOT),
               "--positions-jsonl", str(pos_file),
               "--rules-profile", "fixed_v1",
               "--oracle-policy", judge,
               "--m", str(a.m),
               "--oracle-sims", str(a.oracle_sims),
               "--world-seed-salt", WORLD_SEED_SALT,
               "--workers", str(workers),
               "--out-root", a.out_root, "--out-subdir", judge,
               "--resume"]
        print(f"[run_mining] ===== launch {judge} ({meta['positions_attr']}, "
              f"n={n_positions}) -> {log.name}", flush=True)
        print(f"[run_mining]       {' '.join(cmd)}", flush=True)

        t1 = time.time()
        with log.open("w") as fh:
            rc = subprocess.run(cmd, cwd=str(REPO), env=env,
                                stdout=fh, stderr=subprocess.STDOUT).returncode
        wall = round(time.time() - t1, 1)
        legs.append({"judge": judge, "rc": rc, "n_positions": n_positions,
                     "positions_file": str(pos_file),
                     "out": f"{a.out_root}/{judge}",
                     "log": str(log), "wall_secs": wall})
        print(f"[run_mining] ===== done {judge} rc={rc} ({wall}s)", flush=True)
        if rc != 0:
            print(f"[run_mining] leg {judge} FAILED (rc={rc}) — STOPPING before "
                  "the next judge", file=sys.stderr)
            break

    manifest = {
        "driver": "run_mining",
        "prereg": PREREG,
        "strata": str(a.strata),
        "world_seed_salt": WORLD_SEED_SALT,
        "m_worlds": int(a.m), "oracle_sims": int(a.oracle_sims),
        "workers": workers, "workers_requested": int(a.workers),
        "k_late": k_late,
        "judges": {j: d["description"] for j, d in JUDGES},
        "judges_positions_file": {
            j: positions_by_attr[dict(JUDGES)[j]["positions_attr"]] for j, _ in JUDGES},
        "legs": legs,
        "wall_secs": round(time.time() - t0, 1),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (MINING / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n[run_mining] {len(legs)} leg(s) in {manifest['wall_secs']}s -> "
          f"{MINING / 'RUN_MANIFEST.json'}")
    return 0 if legs and all(leg["rc"] == 0 for leg in legs) else (1 if legs else 3)


if __name__ == "__main__":
    raise SystemExit(main())
