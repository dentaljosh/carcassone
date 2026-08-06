#!/usr/bin/env python3
"""FARM-WAR DISCRIMINATOR — the run driver.

Scores the pre-registered strata with both judges. Everything about WHAT is scored was
fixed by `farmwar_stratify.py` before this ran; this file only decides the order, the
worker count and the process split.

WHY IT IS A DRIVER AND NOT A SHELL LOOP. `CARCASSONNE_FIX_R9` is derived at IMPORT time
by `base_deck` and latched in a Rust `OnceLock`, so the three rules epochs in the six E4
games (`walled`, `app_aug2`, `fixed_v1`) cannot share a process. Each (judge, epoch) leg
is therefore its own `oracle_score_pilot` subprocess with the latch exported before
launch and re-verified inside; a leg whose latch disagrees with its profile exits 2
rather than grading the wrong farm adjacency.

CRN. The world seeds are `sha256("world"|rid|j|salt)`, so every arm, every stratum, every
epoch and BOTH judges see the same worlds for a given position — the salt is fixed here,
once, for the whole run.

Per-position checkpointing is the pilot's own (`records/<rid>.json`, written via a tmp +
`os.replace`), and `--resume` skips what exists. The local box dirty-crashed 3x on
2026-08-04; re-running this driver resumes rather than restarts.
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
FW = REPO / "measurement/analyzer_evloss_20260805/farmwar"

#: Fixed once for the whole run so both judges share worlds. Distinct from the oracle
#: pilot's own salt so the two runs' records can never collide.
WORLD_SEED_SALT = "farmwar-v1"

JUDGES = (
    ("clair-puct", "PRIMARY — in-family clairvoyant PUCT over the champion's own leaf. "
                   "Biased TOWARD the champion's picks, so a positive result is "
                   "conservative and a null is uninformative."),
    ("tier1-greedy", "SECONDARY — out-of-family Tier-1 greedy. SIGN ONLY."),
)


def r9_for(profile: str) -> str:
    from carcassonne_ai import rules_profile
    return "1" if rules_profile.resolve(profile).r9_env_expected else "0"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--strata", default=str(FW / "STRATA.json"))
    ap.add_argument("--out-root", default="/mnt/c/carc-shared/analyzer_farmwar_20260805")
    ap.add_argument("--m", type=int, default=32)
    ap.add_argument("--oracle-sims", type=int, default=100)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--judges", nargs="+", default=[j for j, _ in JUDGES])
    a = ap.parse_args(argv)

    strata = json.loads(Path(a.strata).read_text())
    if not strata.get("gate_ok"):
        print("[run] REFUSING: the pre-registered n>=10 gate did not pass. "
              f"{strata['gate_verdict']}", file=sys.stderr)
        return 3
    files = strata["positions_files"]
    print(f"[run] FARM n={strata['n_farm']} CONTROL n={strata['n_control']} "
          f"across {len(files)} epochs | M={a.m} | W={a.workers} | salt={WORLD_SEED_SALT}")

    legs, t0 = [], time.time()
    for judge in a.judges:
        for profile, pos in sorted(files.items()):
            sub = f"{judge}/{profile}"
            env = dict(os.environ)
            env["CARCASSONNE_FIX_R9"] = r9_for(profile)
            env.setdefault("OPENBLAS_NUM_THREADS", "1")
            env.setdefault("OMP_NUM_THREADS", "1")
            cmd = [sys.executable, str(PILOT),
                   "--positions-jsonl", pos,
                   "--rules-profile", profile,
                   "--oracle-policy", judge,
                   "--m", str(a.m),
                   "--oracle-sims", str(a.oracle_sims),
                   "--world-seed-salt", WORLD_SEED_SALT,
                   "--workers", str(a.workers),
                   "--out-root", a.out_root, "--out-subdir", sub,
                   "--resume"]
            print(f"\n[run] ===== {sub} (R9={env['CARCASSONNE_FIX_R9']}) =====", flush=True)
            t = time.time()
            rc = subprocess.run(cmd, cwd=str(REPO), env=env).returncode
            legs.append({"judge": judge, "profile": profile, "rc": rc,
                         "out": f"{a.out_root}/{sub}",
                         "wall_secs": round(time.time() - t, 1)})
            if rc != 0:
                print(f"[run] leg {sub} exited {rc} — STOPPING", file=sys.stderr)
                break
    manifest = {
        "driver": "run_farmwar",
        "prereg": "measurement/analyzer_evloss_20260805/FARMWAR_PREREG.md",
        "strata": str(a.strata),
        "world_seed_salt": WORLD_SEED_SALT,
        "m_worlds": int(a.m), "oracle_sims": int(a.oracle_sims),
        "workers": int(a.workers),
        "judges": {j: d for j, d in JUDGES},
        "legs": legs,
        "wall_secs": round(time.time() - t0, 1),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    FW.mkdir(parents=True, exist_ok=True)
    (FW / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n[run] {len(legs)} legs in {manifest['wall_secs']}s -> {FW/'RUN_MANIFEST.json'}")
    return 0 if all(l["rc"] == 0 for l in legs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
