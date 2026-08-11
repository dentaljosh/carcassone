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

WORKER CAP IS PER-BOX (added after the original run landed on Joshua's
interactive local box only):

    local  (hostname "Doctor")       -> W=14  DRAM-latency-bound AND interactive
    laptop (hostname "laptop-wsl")   -> W=22  see CAVEAT below
    unrecognised hostname            -> fails SAFE to local's W=14, never to
                                         laptop's looser cap

Resolved via `--box {local,laptop,auto}` (default `auto`, from
`socket.gethostname()`; pass `--box local`/`--box laptop` to override). A
`--workers` above the resolved box's cap is clamped with a loud warning that
names the box — never silently honoured and never an error.

⚠️ LAPTOP W=22 PROVENANCE CAVEAT — READ BEFORE TRUSTING IT. The figure comes
from `measurement/classical_search/WSWEEP_F7D_laptop.tsv`, a RUST-backend
sweep (W=26 peaks throughput_idx 7.496; W=22 at 7.219 is within the standing
"smallest W within ~5-10% of peak" settle rule). `oracle_score_pilot.py`
defaults to `--backend python`, and `tier1-greedy` is PYTHON-ONLY by
construction (the out-of-family judge has no Rust RuleBasedPlayer) — so W=22
is an EXTRAPOLATION ACROSS WORKLOAD CLASSES onto this run, unverified for it.
The laptop is also memory-constrained (MemTotal ~12.2 GB, and its WSL VM has
already been force-exited once today under memory pressure —
`reference_wsl2_host_memory_teardown`). Calibrate after the first ~10 records:
check aggregate worker RSS against the ~12.2 GB ceiling and observed
worker-min/position against the 28.7 min/position clair-puct baseline
(farm-war `RUN_MANIFEST.json`, concurrent-legs-corrected). If RSS x W exceeds
~60% of the box, kill (safe: the run is per-position checkpointed,
`--resume` loses nothing) and relaunch at W=16.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
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

#: Hard safety cap, PER BOX. NOT a tuning knob — see module docstring "WORKER
#: CAP IS PER-BOX" and the W=22 provenance caveat directly below it.
MAX_WORKERS_BY_BOX = {"local": 14, "laptop": 22}

#: hostname -> canonical box name. Anything else fails SAFE to "local".
HOSTNAME_TO_BOX = {"Doctor": "local", "laptop-wsl": "laptop"}

#: --out-root default, per box. The share is the SAME physical mount, but the
#: path differs by box (the standing trap — local uses /mnt/c/carc-shared,
#: anything ssh'd into the laptop uses /mnt/carc-shared).
OUT_ROOT_BY_BOX = {
    "local": "/mnt/c/carc-shared/jcz_mining_20260809",
    "laptop": "/mnt/carc-shared/jcz_mining_20260809",
}

#: Printed (not silently applied) whenever a run actually resolves to laptop —
#: see the W=22 provenance caveat in the module docstring.
LAPTOP_W22_CAVEAT = (
    "W=22 from WSWEEP_F7D_laptop.tsv, a RUST-backend sweep, extrapolated to "
    "this PYTHON-backend workload — unverified for this class; calibrate "
    "after 10 records (worker RSS vs ~12.2GB ceiling, worker-min/position vs "
    "the 28.7 clair-puct baseline; if RSS x W exceeds ~60% of the box, kill "
    "and --resume at W=16)."
)

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


def resolve_box(box: str = "auto", hostname: str | None = None) -> str:
    """Resolve `--box` to a canonical box name ("local"/"laptop").

    `box` in {"local", "laptop"} is returned as-is (an explicit override).
    `box == "auto"` (the default) resolves from `socket.gethostname()` (or the
    injected `hostname`, for testability) via HOSTNAME_TO_BOX. An
    UNRECOGNISED hostname fails SAFE to "local" (the TIGHTER W=14 cap), never
    to "laptop" (the looser, unverified-for-this-workload W=22) — printed
    loudly, never silent."""
    if box in MAX_WORKERS_BY_BOX:
        return box
    if box != "auto":
        raise ValueError(f"unknown --box {box!r} (expected local/laptop/auto)")
    hn = hostname if hostname is not None else socket.gethostname()
    resolved = HOSTNAME_TO_BOX.get(hn)
    if resolved is None:
        print(f"[run_mining] WARNING: unrecognised hostname {hn!r} for --box "
              f"auto — failing SAFE to 'local' (W={MAX_WORKERS_BY_BOX['local']}), "
              f"NOT 'laptop' (W={MAX_WORKERS_BY_BOX['laptop']}).", file=sys.stderr)
        return "local"
    return resolved


def max_workers_for(box: str) -> int:
    return MAX_WORKERS_BY_BOX[box]


def clamp_workers(w: int, box: str = "local") -> int:
    """Hard-cap at the resolved box's MAX_WORKERS, warning loudly (and naming
    the box) on a larger request. Never errors — a caller asking for more just
    gets less, same as the box would give them anyway once it saturates."""
    w = int(w)
    cap = MAX_WORKERS_BY_BOX.get(box, MAX_WORKERS_BY_BOX["local"])
    if w > cap:
        print(f"[run_mining] WARNING: --workers {w} exceeds the {box} box's "
              f"hard cap {cap} — clamping to {cap}.", file=sys.stderr)
        return cap
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
                    "and the per-box worker-cap rationale.")
    ap.add_argument("--strata", default=str(MINING / "STRATA.json"))
    ap.add_argument("--positions", default=str(MINING / "POSITIONS.jsonl"))
    ap.add_argument("--positions-ab", default=str(MINING / "POSITIONS_AB.jsonl"))
    ap.add_argument("--box", choices=["local", "laptop", "auto"], default="auto",
                    help="which box's worker cap / out-root defaults to use "
                         "(default: auto-detect from hostname, fail-safe to "
                         "local on an unrecognised host)")
    ap.add_argument("--out-root", default=None,
                    help="default follows --box: /mnt/c/carc-shared/... "
                         "(local) or /mnt/carc-shared/... (laptop)")
    ap.add_argument("--m", type=int, default=32)
    ap.add_argument("--oracle-sims", type=int, default=100)
    ap.add_argument("--workers", type=int, default=None,
                    help="default is the resolved box's cap (local=14, "
                         "laptop=22, see the W=22 provenance caveat in the "
                         "module docstring). A value above the cap is "
                         "clamped with a warning.")
    ap.add_argument("--judges", nargs="+", default=[j for j, _ in JUDGES],
                    choices=[j for j, _ in JUDGES],
                    help="which judges to run (canonical order is always "
                         "enforced: clair-puct before tier1-greedy)")
    a = ap.parse_args(argv)

    box = resolve_box(a.box)
    cap = max_workers_for(box)
    out_root = a.out_root or OUT_ROOT_BY_BOX[box]

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

    requested = a.workers if a.workers is not None else cap
    workers = clamp_workers(requested, box)
    k_late = strata.get("k_late")

    MINING.mkdir(parents=True, exist_ok=True)
    positions_by_attr = {"positions": a.positions, "positions_ab": a.positions_ab}

    judge_order = [j for j, _ in JUDGES if j in a.judges]
    print(f"[run_mining] box={box} (cap W={cap}) gate_ok={strata['gate_ok']} "
          f"k_late={k_late} M={a.m} oracle_sims={a.oracle_sims} W={workers} "
          f"(requested {requested}) out_root={out_root} salt={WORLD_SEED_SALT} "
          f"judges={judge_order}")
    if box == "laptop":
        print(f"[run_mining] CAVEAT: {LAPTOP_W22_CAVEAT}")

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
               "--out-root", out_root, "--out-subdir", judge,
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
                     "out": f"{out_root}/{judge}",
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
        "box": box, "box_worker_cap": cap,
        "box_caveats": ([LAPTOP_W22_CAVEAT] if box == "laptop" else []),
        "world_seed_salt": WORLD_SEED_SALT,
        "m_worlds": int(a.m), "oracle_sims": int(a.oracle_sims),
        "workers": workers, "workers_requested": int(requested),
        "out_root": out_root,
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
