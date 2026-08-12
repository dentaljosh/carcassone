#!/usr/bin/env python3
"""E4 AUTOPSY — the scoring-run driver.

Design doc: measurement/e4_autopsy_20260812/DESIGN.md.  Everything about WHAT is scored
was fixed by `autopsy_extract.py sample` before this ran; this file only decides the
order, the worker count, the process split, and it refuses to launch if the instrument
is not the instrument the design assumes.

`oracle_score_pilot.py` IS NOT MODIFIED and IS NOT FORKED — the same discipline the
farm-war and JCZ-mining designs held.  Everything this driver needs is expressible
through `--positions-jsonl`, whose rows already ride the stratum metadata through
`_process` untouched.

WHY IT IS A DRIVER AND NOT A SHELL LOOP.  `CARCASSONNE_FIX_R9` is derived at IMPORT time
by `base_deck` and latched in a Rust `OnceLock`, so the three rules epochs in the 26 E4
games (`walled`, `app_aug2`, `fixed_v1`) cannot share a process.  Each (judge, epoch) leg
is its own subprocess with the latch exported before launch and re-verified inside; a leg
whose latch disagrees with its profile exits 2 rather than grading the wrong farm
adjacency.

PREFLIGHT — the part that is NEW relative to the farm-war driver.  `--backend rust` is
licensed by an IDENTITY gate (`measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json`,
20 positions / 940 field checks / 0 mismatches), and that gate is **cell-and-knob scoped:
it licenses the continuation AT THOSE KNOBS ON THAT REVISION.**  The 2026-08-09
budget-headroom run re-verified it at HEAD before launching (8 positions, 376 field
checks, 0 mismatches, speedup 9.48x) — but did so BY HAND, and because the gate script's
`--out` defaults to the committed record, the re-verification overwrote it and the
20-position record had to be restored afterwards.  Here the re-verification is CODE, it
writes to a RUN-LOCAL path so the committed record is never touched, and any mismatch
aborts the launch instead of being a prose claim.

CRN.  The world seeds are `sha256("world"|rid|j|salt)`, so every arm, every stratum, every
epoch and BOTH judges see the same worlds for a given position — the salt is fixed here,
once, for the whole run.

Per-position checkpointing is the pilot's own (`records/<rid>.json`, written via a tmp +
`os.replace`), and `--resume` skips what exists.  The local box has a history of dirty
reboots; re-running this driver resumes rather than restarts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "scripts/measurement_infra/oracle_score_pilot.py"
GATE = REPO / "scripts/rustport/gate_oracle_pilot_backend.py"
AUT = REPO / "measurement/e4_autopsy_20260812"

#: Fixed once for the whole run so both judges share worlds.  Distinct from the oracle
#: pilot's own salt and from the farm-war salt so the three runs' records can never
#: collide in the shared out-root.
WORLD_SEED_SALT = "e4-autopsy-v1"

#: Production knobs.  The smoke differs from the scoring run ONLY in the position count.
M_WORLDS = 32
ORACLE_SIMS = 100

JUDGES = (
    ("clair-puct", "PRIMARY — in-family clairvoyant PUCT over the champion's own leaf. "
                   "Shares the leaf under test, so it is biased TOWARD the champion's "
                   "picks: a result AGAINST the champion is conservative, a null is weak."),
    ("tier1-greedy", "SECONDARY — out-of-family Tier-1 greedy. SIGN ONLY, never magnitude "
                     "(1.83x noisier, no curve125). Python backend by construction."),
)


def r9_for(profile: str) -> str:
    from carcassonne_ai import rules_profile
    return "1" if rules_profile.resolve(profile).r9_env_expected else "0"


def rust_clair_available(profile: str) -> tuple:
    """Can the RUST clairvoyant continuation run this rules profile?  (ok, reason)

    ⚠️ MEASURED 2026-08-12, and it is the reason this run is python-backed.  The E4 epochs
    carry non-default geometry/rules — `retail` start tile, `centered18` grid, the fixed
    cloister scan, the `redraw` draw rule — and `rust_agent.RustCarryClairvoyantAgent`
    seeds `MirrorState.from_deck()` with NO geometry/rules config (unlike the fair
    `RustFairAgent`, which forwards them).  It fails CLOSED rather than silently running
    engine-default rules against a game that does not use them:

        ValueError: the clairvoyant Rust ruler cannot mirror ['start_row/start_col',
        'fixed_start_tile', 'cloister_scan_fix', 'draw_rule'] ... Build this ruler with
        backend='python' until the forwarding lands.

    A profile whose `game_kwargs()` is EMPTY (`walled`) is unaffected.  The test is that
    dict, so this needs no engine construction and cannot itself fail.

    ⚠️ This does NOT contradict `GATE_ORACLE_PILOT_BACKEND.json`.  That gate is a genuine
    python-vs-rust identity result and it re-verifies PASS at HEAD — but it was taken on
    the CL-070 bank, whose roots are engine-default-rules positions.  The gate's scope
    simply does not extend to a rules profile the rust ruler declines to mirror.
    """
    from carcassonne_ai import rules_profile
    kw = rules_profile.resolve(profile).game_kwargs() or {}
    if kw:
        return False, (f"profile {profile!r} sets {sorted(kw)}, which "
                       "RustCarryClairvoyantAgent cannot mirror (it seeds "
                       "MirrorState.from_deck() with no geometry/rules config)")
    return True, f"profile {profile!r} has empty game_kwargs"


def census_processes() -> None:
    """Pre-launch process census — standing rule, done BY DEFAULT."""
    print("=== process census (python, by age) ===", flush=True)
    subprocess.run(["ps", "-o", "pid,etime,%cpu,comm", "-C", "python", "--sort=-etime"],
                   check=False)
    print("load:", Path("/proc/loadavg").read_text().split()[0:3], flush=True)


def preflight_backend_gate(positions: int, workers: int, out: Path) -> dict:
    """Re-verify the rust-vs-python identity gate AT HEAD.  Returns the verdict dict.

    Writes to `out` (run-local), NOT to the committed
    `measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` — the 2026-08-09 run had to
    hand-restore that file after its re-verification clobbered it.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(GATE), "--positions", str(positions),
           "--workers", str(workers), "--out", str(out)]
    print(f"[preflight] identity gate at HEAD: {' '.join(cmd)}", flush=True)
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=str(REPO)).returncode
    secs = round(time.time() - t0, 1)
    if rc != 0 or not out.exists():
        raise SystemExit(f"[preflight] ABORT: identity gate exited {rc} after {secs}s — "
                         "the rust continuation is NOT licensed at this revision.")
    v = json.loads(out.read_text())
    if v.get("verdict") != "PASS" or v.get("mismatches"):
        raise SystemExit(f"[preflight] ABORT: identity gate verdict={v.get('verdict')!r} "
                         f"with {len(v.get('mismatches') or [])} mismatches. The ruler "
                         "would not be the same ruler; refusing to launch.")
    print(f"[preflight] identity gate PASS: {v.get('positions')} positions, "
          f"{v.get('field_checks')} field checks, 0 mismatches "
          f"(speedup {v.get('speedup')}x, {secs}s)", flush=True)
    return v


def build_smoke(positions_jsonl: Path, per_third: int, out: Path) -> dict:
    """A phase-stratified subset of the SAME positions, at the SAME knobs.

    Not a cheaper configuration: `M`, `--oracle-sims`, the policy and the backend are the
    production ones and only the COUNT differs, per the house pre-flight rule.  Phase
    stratified because the continuation runs to terminal, so an opening position costs
    several times an endgame one and a blind average would misprice the run (the
    2026-08-09 anchor spans 6.6s .. 163.2s per position).

    Its records land in the SAME out-dir under the SAME salt, so `--resume` folds them
    into the scoring run instead of throwing the work away.
    """
    rows = [json.loads(x) for x in positions_jsonl.read_text().splitlines() if x.strip()]
    by = {}
    for r in rows:
        by.setdefault(r["phase_third"], []).append(r)
    picked = []
    for third in ("opening", "middle", "endgame"):
        pool = sorted(by.get(third, []), key=lambda r: r["rid"])
        # EVENLY SPACED, not the first N: rids are game-prefixed, so `pool[:N]` would draw
        # every smoke position from ONE game and price the run off one deck's positions.
        if not pool:
            continue
        n = min(per_third, len(pool))
        picked += [pool[(i * len(pool)) // n] for i in range(n)]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for r in picked:
            fh.write(json.dumps(r) + "\n")
    counts = {t: sum(1 for r in picked if r["phase_third"] == t)
              for t in ("opening", "middle", "endgame")}
    print(f"[smoke] {len(picked)} positions -> {out}  {counts}")
    return {"n": len(picked), "by_phase_third": counts, "path": str(out),
            "epochs": sorted({r["rules_profile"] for r in picked})}


def price_from_records(records_dir: Path, positions_jsonl: Path) -> dict:
    """Per-position seconds by phase third, and the resulting run price at W."""
    idx = {json.loads(x)["rid"]: json.loads(x)
           for x in positions_jsonl.read_text().splitlines() if x.strip()}
    per, capped = {}, {}
    for p in sorted(Path(records_dir).glob("*.json")):
        rec = json.loads(p.read_text())
        rid = rec.get("rid")
        if rid not in idx or rec.get("elapsed_secs") is None:
            continue
        third = idx[rid]["phase_third"]
        # A wall-capped position is a LOWER BOUND on its cost, not a measurement of it.
        # Pooling the two would silently understate the price of exactly the positions
        # that dominate it, so they are kept apart.
        bucket = capped if str(rec.get("error", "")).startswith("TimeoutError") else per
        bucket.setdefault(third, []).append(float(rec["elapsed_secs"]))

    def _stat(d):
        return {t: {"n": len(v), "mean_secs": (sum(v) / len(v) if v else None),
                    "min_secs": (min(v) if v else None), "max_secs": (max(v) if v else None)}
                for t, v in sorted(d.items())}

    allv = [x for v in per.values() for x in v]
    out = {"completed": _stat(per), "wall_capped_lower_bounds": _stat(capped),
           "n_completed": len(allv),
           "n_wall_capped": sum(len(v) for v in capped.values()),
           "ALL_completed": {
               "n": len(allv), "mean_secs": (sum(allv) / len(allv) if allv else None),
               "min_secs": (min(allv) if allv else None),
               "max_secs": (max(allv) if allv else None)}}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sample", default=str(AUT / "SAMPLE.json"))
    ap.add_argument("--out-root", default="/mnt/c/carc-shared/analyzer_e4_autopsy_20260812")
    ap.add_argument("--m", type=int, default=M_WORLDS)
    ap.add_argument("--oracle-sims", type=int, default=ORACLE_SIMS)
    ap.add_argument("--workers", type=int, default=14,
                    help="local 5900XT default 14; the laptop's measured cap is 22")
    ap.add_argument("--judges", nargs="+", default=[j for j, _ in JUDGES])
    ap.add_argument("--backend", default="rust",
                    help="continuation engine for the PRIMARY judge; tier1-greedy is "
                         "python-only by construction and the pilot enforces that")
    ap.add_argument("--smoke", type=int, default=0,
                    help="price only: score N positions PER PHASE THIRD at production "
                         "knobs, write SMOKE.json, and stop")
    ap.add_argument("--gate-positions", type=int, default=8,
                    help="identity-gate re-verification size (2026-08-09 precedent: 8)")
    ap.add_argument("--gate-workers", type=int, default=8)
    ap.add_argument("--wall-cap", type=int, default=7200,
                    help="per-position seconds; the pilot records a TimeoutError row "
                         "rather than taking the pool down")
    ap.add_argument("--skip-gate", action="store_true",
                    help="ONLY for a python-backend run — the gate licenses rust")
    a = ap.parse_args(argv)

    samp = json.loads(Path(a.sample).read_text())
    files = dict(samp["positions_files"])
    print(f"[run] {samp['n_selected']} positions | strata {samp['per_stratum']} | "
          f"M={a.m} | W={a.workers} | salt={WORLD_SEED_SALT}")
    if samp.get("underpowered_strata"):
        print(f"[run] ⚠ underpowered-by-construction strata (pre-registered, will be "
              f"reported as no-conviction): {samp['underpowered_strata']}")

    census_processes()

    # ---- backend resolution ---------------------------------------------------------- #
    # If ANY epoch cannot run the rust clairvoyant, the WHOLE run drops to python.  Mixing
    # backends across epochs would make the epochs different instruments, and read rule 4
    # already forbids pooling epochs whose signs disagree — a per-epoch engine split would
    # make even the per-epoch reads incomparable.  One ruler, all epochs.
    backend = a.backend
    probes = {p: rust_clair_available(p) for p in sorted(files)}
    blockers = {p: why for p, (ok, why) in probes.items() if not ok}
    if backend != "python" and blockers:
        print("[run] ⚠ RUST CLAIRVOYANT UNAVAILABLE for this corpus — falling back to "
              "python for EVERY epoch (one ruler, all epochs):", flush=True)
        for p, why in blockers.items():
            print(f"[run]     {p}: {why}", flush=True)
        backend = "python"

    manifest = {
        "driver": "run_autopsy",
        "design": "measurement/e4_autopsy_20260812/DESIGN.md",
        "sample": str(a.sample),
        "world_seed_salt": WORLD_SEED_SALT,
        "m_worlds": int(a.m), "oracle_sims": int(a.oracle_sims),
        "workers": int(a.workers), "backend_requested": a.backend,
        "backend_resolved": backend,
        "rust_clair_probe": {k: {"ok": v[0], "reason": v[1]} for k, v in probes.items()},
        "judges": {j: d for j, d in JUDGES},
        "smoke": None, "preflight": None, "legs": [],
    }

    if backend != "python" and not a.skip_gate:
        manifest["preflight"] = preflight_backend_gate(
            a.gate_positions, a.gate_workers, AUT / "PREFLIGHT_GATE_AT_HEAD.json")

    # ---- smoke: production knobs, fewer positions, records reusable by the real run --- #
    if a.smoke:
        sm = build_smoke(Path(samp["positions"]), a.smoke, AUT / "positions_smoke.jsonl")
        legs = []
        for profile in sm["epochs"]:
            rows = [json.loads(x) for x in
                    (AUT / "positions_smoke.jsonl").read_text().splitlines() if x.strip()]
            sub = AUT / f"positions_smoke_{profile}.jsonl"
            with sub.open("w") as fh:
                for r in rows:
                    if r["rules_profile"] == profile:
                        fh.write(json.dumps(r) + "\n")
            n = sum(1 for r in rows if r["rules_profile"] == profile)
            env = dict(os.environ, CARCASSONNE_FIX_R9=r9_for(profile))
            env.setdefault("OPENBLAS_NUM_THREADS", "1")
            env.setdefault("OMP_NUM_THREADS", "1")
            log = AUT / f"logs/smoke_{profile}.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(PILOT),
                   "--positions-jsonl", str(sub), "--rules-profile", profile,
                   "--oracle-policy", "clair-puct", "--backend", backend,
                   "--m", str(a.m), "--oracle-sims", str(a.oracle_sims),
                   "--world-seed-salt", WORLD_SEED_SALT,
                   "--workers", str(min(n, a.workers)),
                   "--wall-cap", str(a.wall_cap),
                   "--out-root", a.out_root, "--out-subdir", f"clair-puct/{profile}",
                   "--resume"]
            t = time.time()
            print(f"[smoke] launch {profile} n={n} -> {log.name}", flush=True)
            with log.open("w") as fh:
                rc = subprocess.run(cmd, cwd=str(REPO), env=env,
                                    stdout=fh, stderr=subprocess.STDOUT).returncode
            legs.append({"profile": profile, "n": n, "rc": rc,
                         "wall_secs": round(time.time() - t, 1), "log": str(log)})
            print(f"[smoke] done {profile} rc={rc} ({legs[-1]['wall_secs']}s)", flush=True)
        price = {p: price_from_records(Path(a.out_root) / f"clair-puct/{p}/records",
                                       AUT / "positions_smoke.jsonl")
                 for p in sm["epochs"]}
        manifest["smoke"] = {"spec": sm, "legs": legs, "per_position_secs": price,
                             "knobs_note": "production knobs; only the position count "
                                           "differs from the scoring run"}
        (AUT / "SMOKE.json").write_text(json.dumps(manifest, indent=2))
        print(f"\n[smoke] -> {AUT/'SMOKE.json'}")
        return 0 if all(l["rc"] == 0 for l in legs) else 1

    # ---- the scoring run ------------------------------------------------------------- #
    from run_farmwar import split_workers            # reuse, unmodified

    counts = {prof: sum(1 for line in Path(p).read_text().splitlines() if line.strip())
              for prof, p in files.items()}
    shares = split_workers(counts, a.workers)
    print(f"[run] epoch legs run CONCURRENTLY (one process per epoch is forced anyway — "
          f"R9 is import-latched); worker split {shares} of {a.workers} over {counts}")

    t0 = time.time()
    for judge in a.judges:
        # All epochs of one judge at once; judges stay sequential so the box is never
        # oversubscribed and the Tier-1 leg cannot steal width from the primary.
        procs = []
        for profile, pos in sorted(files.items()):
            sub = f"{judge}/{profile}"
            env = dict(os.environ, CARCASSONNE_FIX_R9=r9_for(profile))
            env.setdefault("OPENBLAS_NUM_THREADS", "1")
            env.setdefault("OMP_NUM_THREADS", "1")
            log = AUT / f"logs/leg_{judge}_{profile}.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(PILOT),
                   "--positions-jsonl", pos, "--rules-profile", profile,
                   "--oracle-policy", judge,
                   # the pilot REFUSES a non-python backend for tier1-greedy; asking for
                   # it here would abort the leg, so the out-of-family judge stays python.
                   "--backend", (backend if judge == "clair-puct" else "python"),
                   "--m", str(a.m), "--oracle-sims", str(a.oracle_sims),
                   "--world-seed-salt", WORLD_SEED_SALT,
                   "--workers", str(shares[profile]),
                   "--wall-cap", str(a.wall_cap),
                   "--out-root", a.out_root, "--out-subdir", sub, "--resume"]
            print(f"[run] ===== launch {sub} (R9={env['CARCASSONNE_FIX_R9']}, "
                  f"W={shares[profile]}, n={counts[profile]}) -> {log.name}", flush=True)
            fh = log.open("w")
            procs.append((judge, profile, sub, time.time(), fh,
                          subprocess.Popen(cmd, cwd=str(REPO), env=env,
                                           stdout=fh, stderr=subprocess.STDOUT)))
        for judge_, profile, sub, t, fh, pr in procs:
            rc = pr.wait()
            fh.close()
            manifest["legs"].append({
                "judge": judge_, "profile": profile, "rc": rc,
                "workers": shares[profile], "n_positions": counts[profile],
                "out": f"{a.out_root}/{sub}",
                "log": str(AUT / f"logs/leg_{judge_}_{profile}.log"),
                "wall_secs": round(time.time() - t, 1)})
            print(f"[run] ===== done {sub} rc={rc} "
                  f"({manifest['legs'][-1]['wall_secs']}s)", flush=True)
        if any(l["rc"] != 0 for l in manifest["legs"] if l["judge"] == judge):
            print(f"[run] a {judge} leg failed — STOPPING before the next judge",
                  file=sys.stderr)
            break

    manifest["wall_secs"] = round(time.time() - t0, 1)
    manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    AUT.mkdir(parents=True, exist_ok=True)
    (AUT / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n[run] {len(manifest['legs'])} legs in {manifest['wall_secs']}s "
          f"-> {AUT/'RUN_MANIFEST.json'}")
    return 0 if all(l["rc"] == 0 for l in manifest["legs"]) else 1


if __name__ == "__main__":
    os.nice(19)
    raise SystemExit(main())
