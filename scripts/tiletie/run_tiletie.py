#!/usr/bin/env python3
"""TILE-TIE PRICING — the scoring launcher (DESIGN.md §2, §5, §7.4; house pattern:
`scripts/analyzer/run_farmwar.py`).

PREREGISTRATION STATUS: this launcher is DESIGNED, BUILT and PRICED ONLY, per
`measurement/tiletie_pricing_20260812/DESIGN.md` line 6 ("NOT LAUNCHED. The box
and the funding decision belong to Joshua."). `--yes` is the one flag that turns
a dry plan into a real launch; everything else runs whether or not `--yes` is
given, INCLUDING the preflight gate re-verification and the ETA arithmetic, so
the run can be priced without being started.

PLAIN SCRIPT (see `build_positions.py`'s module docstring for why): works
whether or not `scripts/tiletie/__init__.py` exists.

PREFLIGHT — refuses to launch on ANY failure (all checks always run and are all
printed, not short-circuited, so one `--dry`/no-`--yes` invocation reports every
problem at once):
  1. re-verify the rust identity gate AT HEAD (`gate_oracle_pilot_backend.py`),
     writing to a FRESH path -- NEVER the committed
     `measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json`.
  2. the production leaf hash (`a36d2e15a3b3d71d`) resolves and verifies.
  3. a process census (`ps` + `/proc/loadavg`) -- printed, informational only,
     never itself a refusal (the standing "census before any cluster launch"
     rule, not a pass/fail gate).
  4. `git rev-parse` + refuse if `git status --porcelain` shows modifications
     under `src/carcassonne_ai/` or `engine/` (mixed-rev protection -- the
     worktree-isolation rule).
  5. every positions file named in `POSITIONS_PLAN.json` exists, its line count
     matches the plan, and every rid in it appears in `ARMS.json`.

LEGS. One `oracle_score_pilot.py` subprocess per (judge, rules_profile, leg
index r) -- `CARCASSONNE_FIX_R9` exported per profile (import-latched), thread
envs pinned to 1, `--world-seed-salt` FIXED ONCE for the whole run (this is what
makes every arm of a position and both judges share the same CRN worlds -- see
`build_positions.py`'s module docstring and DESIGN §2.1). `clair-puct` runs
`--backend rust`; `tier1-greedy` runs `--backend python` UNLESS `--arb-backend
rust` is given, in which case its legs are run by
`scripts/tiletie/tier1_rust_leg.py` (`carc_rs.tier1_leg`, the Phase-A port --
`G-BITEXACT` 15,360/15,360, ~12.2x cheaper) instead of by the pilot, which has no
rust tier1 path. This is campaign work item **W1**
(`measurement/tiearb_widening_20260817/PLAN_B_gt_16.md` §0.3/§3, `CAMPAIGN.md`
ruling 2). ⚠️ THE DEFAULT IS UNCHANGED (`python`) so every pre-existing
invocation produces byte-identical legs; and `--arb-backend rust` FAILS the
preflight if the wheel cannot do the job -- it never falls back silently.
`--m` is likewise a real flag now, bounded at 128 (the campaign's shared run;
usable `B` is `M/2` because the estimator cross-fits on parity halves).
Judges run sequentially (primary first); profiles+legs of
one judge run CONCURRENTLY with a proportional worker split
(`run_farmwar.split_workers`, imported -- not re-implemented). `--n` is ALWAYS
passed explicitly as the leg's own line count (`oracle_score_pilot` defaults
`--n` to 20 and would silently subsample otherwise, and a DIFFERENT subsample
per leg would destroy the cross-leg CRN pairing this whole design rests on).

⚠️ DESIGN §5 restricts `tier1-greedy` to a seeded n=80 SIGN-ONLY subset run
AFTER the primary, and only if the primary is not already branch-1-closed at
Stage A -- that gating is an ANALYSIS-STAGE decision this launcher does not
make for you (it has no verdict to gate on; it only prices and runs whatever
positions files exist). `--judges` therefore defaults to `clair-puct` alone;
pass `--judges clair-puct tier1-greedy` explicitly once that gate is cleared,
against a `tier1-greedy`-scoped n=80 positions subset built separately.

`--smoke`: 5 positions (or however many multi-leg positions exist, whichever is
fewer), production knobs otherwise unchanged (M=32, oracle-sims=100, backend
rust, clair-puct only), run over >=2 legs so it can prove -- not merely
assume -- DESIGN §2.1's CRN claim: every leg of a position, scored by a
SEPARATE `oracle_score_pilot` invocation but under the SAME rid, must produce
BIT-IDENTICAL `values_a` (raw f64 bit patterns), identical world_seeds /
playout_seeds, identical `afterstate_deck_hash_a`, and `crn_verified=True` in
every leg. See `check_crn_cross_leg` -- a reusable, pure function so it can be
unit-tested against synthetic records and re-applied by the post-run analyser.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

for _p in (str(HERE),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA = "carcassonne-tiletie-run/v1"
DESIGN_DOC = "measurement/tiletie_pricing_20260812/DESIGN.md"

PILOT = REPO / "scripts" / "measurement_infra" / "oracle_score_pilot.py"
#: W1 (PLAN_B_gt_16 §3): the rust ARB leg runner. Reached ONLY via
#: `--arb-backend rust`; the default is unchanged python.
TIER1_RUST_LEG = HERE / "tier1_rust_leg.py"
GATE_SCRIPT = REPO / "scripts" / "rustport" / "gate_oracle_pilot_backend.py"
#: ⚠️ NEVER write here -- the budget-headroom run's 20-position record is
#: committed and load-bearing for other harnesses' provenance.
COMMITTED_GATE = REPO / "measurement" / "rustport_p6" / "GATE_ORACLE_PILOT_BACKEND.json"

PRICING_ROOT = REPO / "measurement" / "tiletie_pricing_20260812"
DEFAULT_POSITIONS_DIR = PRICING_ROOT / "positions"
DEFAULT_LOGS_DIR = PRICING_ROOT / "logs"
DEFAULT_GATE_RECHECK_OUT = PRICING_ROOT / "GATE_BACKEND_RECHECK.json"
DEFAULT_MANIFEST = PRICING_ROOT / "RUN_MANIFEST.json"
DEFAULT_SMOKE_MANIFEST = PRICING_ROOT / "SMOKE_MANIFEST.json"

EXPECTED_LEAF_HASH = "a36d2e15a3b3d71d"

#: Fixed once for the whole run -- distinct from every other harness's own salt
#: (farm-war's is "farmwar-v1", the pilot's own default is "oracle-pilot-v1") so
#: records can never collide across harnesses.
WORLD_SEED_SALT = "tiletie-v1"

JUDGE_BACKEND = {"clair-puct": "rust", "tier1-greedy": "python"}

#: PLAN_B_gt_16 §0.2 — the cross-fit parity halves cap usable `B` at `M/2`, so
#: the campaign's `B in {16,32,64}` needs `M = 128`. Nothing asks for more, and a
#: typo'd `--m` must not silently buy a 10x run.
M_MAX = 128

#: ⭐ W1 (PLAN_B_gt_16 §0.3 / CAMPAIGN.md ruling 2). The ARB judge
#: (`tier1-greedy`) was priced in PYTHON for Stage 1b at c = 2.18-2.73
#: worker-s/playout. Phase A's rust port is `G-BITEXACT` 15,360/15,360 at
#: c = 0.178232 -- 12.2x -- and is already in the installed `carc_rs` wheel.
#: `--arb-backend rust` routes the `tier1-greedy` legs through
#: `scripts/tiletie/tier1_rust_leg.py` instead of `oracle_score_pilot`.
#:
#: ⚠️ DEFAULT IS `python`, deliberately: every pre-existing invocation of this
#: launcher must keep producing byte-identical legs. Opting in is one flag.
ARB_BACKENDS = ("python", "rust")

#: Rules profiles the RUST clairvoyant continuation can actually mirror.
#:
#: ⚠️ DISCOVERED BY THE 2026-08-12 SMOKE, not by reading: on `fixed_v1` every
#: position fails with
#:   "the clairvoyant Rust ruler cannot mirror ['start_row/start_col',
#:    'fixed_start_tile', 'cloister_scan_fix', 'draw_rule']:
#:    RustCarryClairvoyantAgent seeds MirrorState.from_deck() with no
#:    geometry/rules config (unlike the fair RustFairAgent, which forwards
#:    them), so it would run the engine-default rules against a game that does
#:    not. Build this ruler with backend='python' until the forwarding lands."
#: The harness FAILS LOUD rather than silently grading under the wrong rules —
#: which is the correct behaviour and is why this was caught in a 5-position
#: smoke instead of in a 6-hour run.
#:
#: Consequence: only `walled` (whose `game_kwargs()` is `{}` by construction —
#: the engine of record) may use rust. Every other profile runs python, at
#: roughly 7-9x the cost (the committed identity gate measures the rust speedup
#: at 9.41-9.48x). This is also why `run_farmwar.py` never passes `--backend`
#: at all: its E4 epochs could not have used rust either.
RUST_OK_PROFILES = frozenset({"walled"})


def backend_for(judge: str, profile: str, arb_backend: str = "python") -> str:
    """Backend for one (judge, profile) leg. Rust requires BOTH a rust-gated
    judge AND a profile the rust mirror can represent.

    `arb_backend` promotes the ARB judge (`tier1-greedy`) from its python-era
    default to the Phase-A rust port (W1). It is subject to the SAME profile
    restriction: `carc_rs.tier1_leg` replays under the default `GameConfig`, so
    only `walled` may use it."""
    want = JUDGE_BACKEND[judge]
    if judge == "tier1-greedy" and arb_backend == "rust":
        want = "rust"
    if want == "rust" and profile not in RUST_OK_PROFILES:
        return "python"
    return want


def check_arb_backend(args) -> dict:
    """`--arb-backend rust` means the wheel MUST be able to do the job.

    THE J13 LESSON, applied: a missing/stale wheel must FAIL the preflight, never
    quietly fall back to the python continuation while the manifest says 'rust'
    (that is a 12.2x cost surprise wearing the wrong label). Inert -- and always
    PASS -- when `--arb-backend python`, which is the default."""
    want = getattr(args, "arb_backend", "python")
    if want not in ARB_BACKENDS:
        return {"ok": False, "problems": [f"--arb-backend must be one of "
                                          f"{list(ARB_BACKENDS)}, got {want!r}"]}
    if want == "python":
        return {"ok": True, "arb_backend": "python",
                "note": "python-era ARB judge (behaviour-preserving default)"}
    if "tier1-greedy" not in getattr(args, "judges", []):
        return {"ok": True, "arb_backend": "rust",
                "note": "no tier1-greedy leg in --judges; the flag is inert"}
    if not TIER1_RUST_LEG.is_file():
        return {"ok": False, "problems": [f"missing {TIER1_RUST_LEG}"]}
    sys.path.insert(0, str(HERE))
    try:
        import tier1_rust_leg as TRL  # noqa: PLC0415

        wheel = TRL.preflight_wheel()
        seeds = TRL.preflight_seeds(WORLD_SEED_SALT, int(args.m))
    except SystemExit as exc:                                      # fail-loud path
        return {"ok": False, "arb_backend": "rust", "problems": [str(exc)]}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "arb_backend": "rust",
                "problems": [f"{type(exc).__name__}: {exc}"]}
    return {"ok": True, "arb_backend": "rust", "wheel": wheel, "seeds": seeds,
            "runner": str(TIER1_RUST_LEG)}


def check_m(args) -> dict:
    """`--m` is a flag now (the campaign runs M=128). Bound it loudly."""
    m = int(args.m)
    if not (1 <= m <= M_MAX):
        return {"ok": False, "m": m,
                "problems": [f"--m {m} out of range 1..{M_MAX} "
                             "(PLAN_B_gt_16 §0.2 sizes the campaign at M=128; "
                             "the parity halves cap usable B at M/2)"]}
    return {"ok": True, "m": m, "m_max": M_MAX,
            "b_ceiling": m // 2,
            "note": "usable B is capped by the SELECTION parity half = M/2 "
                    "(PLAN_B_gt_16 §0.2), not by M"}


# --------------------------------------------------------------------------- #
# preflight checks -- each one small, pure-ish, and independently                #
# monkeypatchable so tests never run a real gate/pilot/git/champion               #
# --------------------------------------------------------------------------- #
def check_gate(args) -> dict:
    """Re-verify the rust identity gate AT HEAD. NEVER writes to the committed
    gate path -- refuses outright if `--gate-out` is ever pointed at it."""
    out_path = Path(args.gate_out)
    if out_path.resolve() == COMMITTED_GATE.resolve():
        return {"ok": False, "problems": [f"--gate-out must never be the committed "
                                          f"gate {COMMITTED_GATE}"]}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(GATE_SCRIPT), "--positions", "8", "--m", "2",
          "--workers", str(max(1, int(args.workers))), "--out", str(out_path)]
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if not out_path.is_file():
        return {"ok": False, "problems": [f"gate did not write {out_path} "
                                          f"(rc={proc.returncode})"],
                "cmd": cmd, "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}
    data = json.loads(out_path.read_text())
    ok = data.get("verdict") == "PASS" and data.get("mismatches") == []
    return {"ok": ok, "verdict": data.get("verdict"), "mismatches": data.get("mismatches"),
           "positions": data.get("positions"), "field_checks": data.get("field_checks"),
           "path": str(out_path), "cmd": cmd, "returncode": proc.returncode}


def check_leaf_hash() -> dict:
    """Assert the production leaf hash resolves to the champion of record."""
    _apply_canon_env()
    sys.path.insert(0, str(REPO / "src"))
    try:
        from carcassonne_ai import champion_factory as CF  # noqa: PLC0415

        cfg = CF.production_leaf_cfg()
        CF.verify_leaf(cfg)
        manifest = CF.resolved_manifest("clairvoyant", verify=True)
        got = (manifest.get("leaf_hashes") or {}).get("harness_leaf_hash")
        ok = got == EXPECTED_LEAF_HASH
        return {"ok": ok, "harness_leaf_hash": got, "expected": EXPECTED_LEAF_HASH}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
}


def _apply_canon_env() -> None:
    """Byte-identical to `oracle_score_pilot._CANON_ENV` -- MUST run before any
    `carcassonne_ai` import (DEFAULT_CONFIG is import-frozen)."""
    for k, v in _CANON_ENV.items():
        os.environ.setdefault(k, v)


def check_process_census() -> dict:
    """Standing rule: census what's already running before any cluster launch.
    Informational ONLY -- never gates the launch by itself."""
    out = {"ok": True}
    try:
        ps = subprocess.run(["ps", "-o", "pid,etime,%cpu,comm", "-C", "python",
                             "--sort=-etime"], capture_output=True, text=True)
        out["ps_head"] = "\n".join(ps.stdout.splitlines()[:15])
    except Exception as exc:                                      # noqa: BLE001
        out["ps_error"] = f"{type(exc).__name__}: {exc}"
    try:
        out["loadavg"] = Path("/proc/loadavg").read_text().strip()
    except Exception as exc:                                      # noqa: BLE001
        out["loadavg_error"] = f"{type(exc).__name__}: {exc}"
    return out


def check_git_clean(args) -> dict:
    """Mixed-rev protection: refuse if src/engine are dirty in the main tree."""
    rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.splitlines()
    # porcelain v1: 2-char status + 1 space + path, always column 3.
    dirty = [ln for ln in status if ln[3:].startswith(("src/carcassonne_ai/", "engine/"))]
    return {"ok": not dirty, "git_rev": rev, "dirty_paths": dirty}


def check_positions(args) -> dict:
    """Every positions file the plan names exists, its line count matches, and
    every rid in it appears in ARMS.json."""
    pos_dir = Path(args.positions_dir)
    plan_path = pos_dir / "POSITIONS_PLAN.json"
    arms_path = pos_dir / "ARMS.json"
    if not plan_path.is_file():
        return {"ok": False, "problems": [f"missing {plan_path}"]}
    if not arms_path.is_file():
        return {"ok": False, "problems": [f"missing {arms_path}"]}
    plan = json.loads(plan_path.read_text())
    arms = json.loads(arms_path.read_text())
    problems = []
    # DESIGN §6 threat 3: ~26% of the tie sets are transpositions, i.e. rows
    # whose delta is 0 BY IDENTITY. Scoring them buys nothing, so a plan built
    # before the dedupe landed (or with --no-dedupe) must not be launched.
    dedupe = plan.get("afterstate_dedupe") or {}
    if dedupe.get("applied") is not True:
        problems.append(
            "POSITIONS_PLAN.json was built WITHOUT the DESIGN §6 threat-3 "
            "afterstate dedupe (afterstate_dedupe.applied is not True) -- "
            "~26% of its budget would buy known-zero transposition rows. "
            "Rebuild with scripts/tiletie/build_positions.py --afterstate-map.")
    files = plan.get("files") or {}
    if not files:
        problems.append("POSITIONS_PLAN.json names zero leg files")
    for key, info in sorted(files.items()):
        p = Path(info["path"])
        if not p.is_file():
            problems.append(f"missing positions file for leg {key}: {p}")
            continue
        lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
        if len(lines) != info["n"]:
            problems.append(f"{p}: line count {len(lines)} != plan n={info['n']} "
                            f"for leg {key}")
        for ln in lines:
            rid = json.loads(ln)["rid"]
            if rid not in arms:
                problems.append(f"{p}: rid {rid!r} missing from ARMS.json")
    return {"ok": not problems, "problems": problems, "n_leg_files": len(files),
           "plan_path": str(plan_path), "arms_path": str(arms_path)}


def preflight(args) -> dict:
    """Run every check (never short-circuits), print nothing itself -- see
    `print_preflight`. `ok` is False if ANY gating check fails; the process
    census is informational and never gates."""
    checks = {
        "gate": check_gate(args),
        "leaf_hash": check_leaf_hash(),
        "process_census": check_process_census(),
        "git_clean": check_git_clean(args),
        "positions": check_positions(args),
        "m": check_m(args),
        "arb_backend": check_arb_backend(args),
    }
    ok = all(c.get("ok", False) for name, c in checks.items() if name != "process_census")
    return {"ok": ok, "checks": checks}


def print_preflight(report: dict) -> None:
    for name, c in report["checks"].items():
        if name == "process_census":
            print(f"[preflight] process census (informational):")
            print(f"  loadavg: {c.get('loadavg', c.get('loadavg_error'))}")
            print(f"  ps (top 15 by etime):\n{c.get('ps_head', c.get('ps_error', ''))}")
            continue
        status = "PASS" if c.get("ok") else "FAIL"
        print(f"[preflight] {name}: {status}")
        for k, v in c.items():
            if k == "ok":
                continue
            print(f"    {k}: {v}")


# --------------------------------------------------------------------------- #
# ETA printing (DESIGN §7.1, re-using build_positions' own arithmetic)          #
# --------------------------------------------------------------------------- #
def print_eta(plan: dict) -> None:
    print(f"[run_tiletie] plan: n_positions={plan['n_positions']} "
         f"(e4={plan['n_e4']} selfplay={plan['n_selfplay']}) max_arms="
         f"{plan['max_arms']} mean_arms={plan['mean_arms']:.2f} "
         f"cap_j={plan['cap_j']} capped={plan['n_positions_capped']}")
    print(f"[run_tiletie] total_arm_playouts={plan['total_arm_playouts']} "
         f"oracle_worker_secs={plan['oracle_worker_secs']:.1f} "
         f"champ_pick_secs={plan['champ_pick_secs']:.1f}")
    for w, eta in sorted(plan["eta_by_workers"].items()):
        print(f"[run_tiletie] ETA at {w}: {eta['wall_hours']:.3f} h "
             f"({eta['wall_secs']:.0f} s)")


# --------------------------------------------------------------------------- #
# legs                                                                          #
# --------------------------------------------------------------------------- #
def _split_workers(counts: dict, total: int) -> dict:
    """`run_farmwar.split_workers`, imported not re-implemented (house pattern:
    proportional shares, largest-remainder apportionment, never more workers
    than a leg has positions)."""
    sys.path.insert(0, str(REPO / "scripts" / "analyzer"))
    import run_farmwar as RFW  # noqa: PLC0415

    return RFW.split_workers(counts, total)


def _r9_for(profile: str) -> str:
    from carcassonne_ai import rules_profile  # noqa: PLC0415

    return "1" if rules_profile.resolve(profile).r9_env_expected else "0"


def leg_command(*, positions_path, profile, judge, m, oracle_sims, workers, n,
                out_root, out_subdir, resume, arb_backend="python",
                legal_mask_cache=True) -> list:
    """The subprocess for one leg.

    ⭐ W1: when `judge == "tier1-greedy"` and `arb_backend == "rust"` this is
    `scripts/tiletie/tier1_rust_leg.py`, NOT `oracle_score_pilot.py` -- the pilot
    has no rust tier1 path (`build_continuation_agent` raises
    `BACKEND_UNAVAILABLE_REASON` for it) and the Phase-A port is a whole-leg FFI
    call, not a per-ply agent. Every other leg is byte-identical to before."""
    resolved = backend_for(judge, profile, arb_backend)
    if judge == "tier1-greedy" and resolved == "rust":
        cmd = [sys.executable, str(TIER1_RUST_LEG),
              "--positions-jsonl", str(positions_path),
              "--rules-profile", str(profile),
              "--m", str(int(m)),
              "--oracle-sims", str(int(oracle_sims)),
              "--world-seed-salt", WORLD_SEED_SALT,
              "--workers", str(int(workers)),
              "--n", str(int(n)),
              "--out-root", str(out_root),
              "--out-subdir", str(out_subdir)]
        cmd.append("--legal-mask-cache" if legal_mask_cache
                   else "--no-legal-mask-cache")
        cmd.append("--resume" if resume else "--no-resume")
        return cmd
    cmd = [sys.executable, str(PILOT),
          "--positions-jsonl", str(positions_path),
          "--rules-profile", str(profile),
          "--oracle-policy", str(judge),
          "--m", str(int(m)),
          "--oracle-sims", str(int(oracle_sims)),
          "--world-seed-salt", WORLD_SEED_SALT,
          "--workers", str(int(workers)),
          "--n", str(int(n)),                # ALWAYS explicit -- see module docstring
          "--out-root", str(out_root),
          "--out-subdir", str(out_subdir),
          "--backend", resolved]
    if resume:
        cmd.append("--resume")
    return cmd


def select_files(plan: dict, only_profiles=None) -> dict:
    """The plan's leg files, optionally narrowed to `only_profiles`.

    ⚠️ WHY THIS EXISTS. `split_workers` apportions the pool by POSITION COUNT,
    which is only a good proxy for work when every leg costs the same per
    position. After the §2.0 backend split they do NOT: a python leg costs ~8x
    a rust leg per playout (9.85 vs the measured rust `c`). On the Stage A plan
    the python legs are ~17% of the lines but ~half the worker-seconds, so a
    count-proportional split starves them and the wall becomes the python leg
    running nearly alone. DESIGN §7.4 prices the two arms SEPARATELY and sums
    them ("Stage A TOTAL, one box"), i.e. each arm gets the whole box — so run
    them as two invocations, `--only-profiles walled` then
    `--only-profiles fixed_v1 app_aug2`, rather than one mixed launch."""
    files = plan["files"]
    if not only_profiles:
        return dict(files)
    keep = set(only_profiles)
    out = {k: v for k, v in files.items() if k.split("/leg")[0] in keep}
    if not out:
        raise SystemExit(
            f"--only-profiles {sorted(keep)} matches no leg file in the plan "
            f"(present: {sorted({k.split('/leg')[0] for k in files})})")
    return out


def launch_legs(args, plan: dict) -> list:
    """One subprocess per (judge, profile, leg r). Judges sequential, one
    judge's (profile, leg) legs concurrent, proportional worker split."""
    logs_dir = Path(args.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    files = select_files(plan, getattr(args, "only_profiles", None))

    results = []
    for judge in args.judges:
        counts = {key: info["n"] for key, info in files.items()}
        assert counts, "launch_legs called with zero leg files"
        shares = _split_workers(counts, args.workers)
        procs = []
        for key, info in sorted(files.items()):
            profile, leg_tag = key.split("/leg")
            sub = f"{judge}/{profile}/leg{leg_tag}"
            env = dict(os.environ)
            env["CARCASSONNE_FIX_R9"] = _r9_for(profile)
            env.setdefault("OPENBLAS_NUM_THREADS", "1")
            env.setdefault("OMP_NUM_THREADS", "1")
            env.setdefault("MKL_NUM_THREADS", "1")
            log = logs_dir / f"leg_{judge}_{profile}_leg{leg_tag}.log"
            cmd = leg_command(positions_path=info["path"], profile=profile, judge=judge,
                              m=args.m, oracle_sims=args.oracle_sims,
                              workers=shares[key], n=info["n"], out_root=args.out_root,
                              out_subdir=sub, resume=args.resume,
                              arb_backend=getattr(args, "arb_backend", "python"),
                              legal_mask_cache=getattr(
                                  args, "arb_legal_mask_cache", True))
            print(f"[run_tiletie] ===== launch {sub} "
                 f"(backend={backend_for(judge, profile, getattr(args, 'arb_backend', 'python'))}, "
                 f"R9={env['CARCASSONNE_FIX_R9']}, "
                 f"W={shares[key]}, n={info['n']}) -> {log.name}", flush=True)
            fh = log.open("w")
            procs.append((judge, profile, leg_tag, key, sub, info, time.time(), fh,
                         subprocess.Popen(cmd, cwd=str(REPO), env=env,
                                          stdout=fh, stderr=subprocess.STDOUT)))
        for judge_, profile, leg_tag, key, sub, info, t0, fh, pr in procs:
            rc = pr.wait()
            fh.close()
            results.append({"judge": judge_, "profile": profile, "leg": int(leg_tag),
                            "backend": backend_for(
                                judge_, profile,
                                getattr(args, "arb_backend", "python")),
                            "rc": rc, "n": info["n"], "workers": shares[key],
                            "positions_path": info["path"],
                            "out": f"{args.out_root}/{sub}",
                            "log": str(logs_dir / f"leg_{judge_}_{profile}_leg{leg_tag}.log"),
                            "wall_secs": round(time.time() - t0, 1)})
        if any(r["rc"] != 0 for r in results if r["judge"] == judge):
            print(f"[run_tiletie] a {judge} leg failed -- STOPPING before the next judge",
                 file=sys.stderr)
            break
    return results


def verify_leg_records(leg: dict) -> dict:
    """Assert a leg produced records/ for EXACTLY the rids in its input."""
    rids_in = set()
    for ln in Path(leg["positions_path"]).read_text().splitlines():
        if ln.strip():
            rids_in.add(json.loads(ln)["rid"])
    records_dir = Path(leg["out"]) / "records"
    rids_out = ({p.stem for p in records_dir.glob("*.json")}
               if records_dir.is_dir() else set())
    missing = sorted(rids_in - rids_out)
    extra = sorted(rids_out - rids_in)
    return {"ok": not missing and not extra, "missing": missing, "extra": extra}


# --------------------------------------------------------------------------- #
# CRN cross-leg witness -- DESIGN §2.1's whole claim, checked not assumed        #
# (reusable: called by --smoke here, and re-appliable by the post-run analyser) #
# --------------------------------------------------------------------------- #
def _f64_bits(x) -> int:
    """Raw f64 bit pattern -- the rustport gate's own comparison currency
    (`gate_oracle_pilot_backend.canon`). NEVER `==`/approx on the float itself."""
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def load_leg_records(out_dir, rids) -> dict:
    """rid -> the pilot's own `records/<rid>.json` record, for one leg's out-dir."""
    recs = {}
    for rid in rids:
        p = Path(out_dir) / "records" / f"{rid}.json"
        if not p.is_file():
            raise FileNotFoundError(f"no record for rid={rid!r} at {p}")
        recs[rid] = json.loads(p.read_text())
    return recs


def world_witness_key(rec: dict) -> str:
    """Which per-world CRN witness this record carries.

    The python leg (`oracle_score_pilot`) records `afterstate_deck_hash_a` -- the
    deck AFTER the pick, hashed off the engine's object graph. The rust ARB leg
    (W1, `tier1_rust_leg`) cannot produce that across the FFI, so it records
    `world_deck_hash` -- the determinized world's own unseen deck -- and does NOT
    fabricate the python field. Both are per-world lists that must be identical
    across legs of one position; they are simply not the SAME quantity, so a set
    of legs that mixes them is a harness error, not a CRN failure."""
    if "afterstate_deck_hash_a" in rec:
        return "afterstate_deck_hash_a"
    if "world_deck_hash" in rec:
        return "world_deck_hash"
    return ""


def check_crn_cross_leg(records_by_leg: dict) -> dict:
    """DESIGN §2.1's CRN claim, CHECKED, not assumed: because the world/playout
    seeds are `sha256(tag|rid|j|salt)` -- keyed on rid+salt, never on the arms --
    every leg of one position (scored by a SEPARATE leg invocation, but under the
    SAME rid) must see the SAME M CRN worlds. That means, across every leg of a
    position:
      1. `values_a` is BIT-IDENTICAL (raw f64 bit patterns, never `==`/approx)
      2. `world_seeds` and `playout_seeds` are identical
      3. the per-world deck witness is identical -- `afterstate_deck_hash_a` on
         a python leg, `world_deck_hash` on a rust ARB leg (W1). Legs that carry
         DIFFERENT witness kinds are a hard error (see `world_witness_key`).
      4. `crn_verified` is True in every leg

    `records_by_leg`: {leg_index: {rid: record_dict}} -- one `records/<rid>.json`
    each, loaded by `load_leg_records`. All legs must share the exact same rid
    set (asserted -- a differing set means the smoke/run built its legs wrong,
    which is a harder failure than a CRN mismatch and is reported as such).

    Returns {"ok": bool, "legs_checked": [...], "rids_checked": [...],
    "n_rids": int, "n_ok": int, "per_rid": {rid: {"ok": bool, "problems": [...]}}}.
    """
    legs = sorted(records_by_leg)
    if len(legs) < 2:
        raise ValueError("check_crn_cross_leg needs >= 2 legs to compare")
    rid_sets = [frozenset(records_by_leg[leg]) for leg in legs]
    if len(set(rid_sets)) != 1:
        raise ValueError(f"legs do not share the same rid set: "
                         f"{dict(zip(legs, (sorted(s) for s in rid_sets)))}")
    rids = sorted(rid_sets[0])

    per_rid = {}
    base_leg = legs[0]
    witnesses = set()
    for rid in rids:
        problems = []
        base = records_by_leg[base_leg][rid]
        wkey = world_witness_key(base)
        witnesses.add(wkey)
        if not wkey:
            problems.append(f"leg{base_leg}: no per-world deck witness "
                            "(neither afterstate_deck_hash_a nor world_deck_hash)")
        if not base.get("crn_verified"):
            problems.append(f"leg{base_leg}: crn_verified is not True")
        base_bits = [_f64_bits(v) for v in base["values_a"]]
        for leg in legs[1:]:
            rec = records_by_leg[leg][rid]
            rkey = world_witness_key(rec)
            witnesses.add(rkey)
            if not rec.get("crn_verified"):
                problems.append(f"leg{leg}: crn_verified is not True")
            bits = [_f64_bits(v) for v in rec["values_a"]]
            if bits != base_bits:
                problems.append(f"leg{leg}: values_a raw-f64-bit MISMATCH vs leg{base_leg}")
            if rec.get("world_seeds") != base.get("world_seeds"):
                problems.append(f"leg{leg}: world_seeds differ vs leg{base_leg}")
            if rec.get("playout_seeds") != base.get("playout_seeds"):
                problems.append(f"leg{leg}: playout_seeds differ vs leg{base_leg}")
            if rkey != wkey:
                # MIXED BACKENDS in one witness set: the two fields are different
                # quantities, so comparing them would either pass vacuously or
                # fail for the wrong reason. Report it as what it is.
                problems.append(
                    f"leg{leg}: per-world deck witness is {rkey or 'ABSENT'!r} but "
                    f"leg{base_leg} carries {wkey or 'ABSENT'!r} -- these legs were "
                    "scored by DIFFERENT backends and are not comparable on this "
                    "field")
            elif wkey and rec.get(wkey) != base.get(wkey):
                problems.append(f"leg{leg}: {wkey} differs vs leg{base_leg}")
        per_rid[rid] = {"ok": not problems, "problems": problems}
    ok = all(v["ok"] for v in per_rid.values())
    return {"ok": ok, "legs_checked": legs, "rids_checked": rids, "per_rid": per_rid,
           "world_witness_kinds": sorted(w for w in witnesses if w),
           "n_rids": len(rids), "n_ok": sum(1 for v in per_rid.values() if v["ok"])}


# --------------------------------------------------------------------------- #
# --smoke                                                                       #
# --------------------------------------------------------------------------- #
def select_smoke_positions(positions_dir: Path, *, profile: str | None = None,
                           stratum: str | None = None, min_arms: int = 3,
                           n: int = 5) -> dict:
    """Positions with an arm at leg index 2 (`len(arms) >= 3`), so leg1 AND
    leg2 both exist -- the minimum needed to de-risk the CRN claim, not just
    measure throughput.

    ⚠️ MUST be filtered to `profile`. The leg files are written PER RULES
    PROFILE (R9 is import-latched, so a profile cannot share a process), but
    `ARMS.json` is global. Selecting the globally-first rids and then filtering
    one profile's leg file yields an EMPTY smoke whenever those rids belong to a
    different profile -- which is exactly what happened on the first two smoke
    attempts (2026-08-12): `app_aug2` and then `fixed_v1` both produced 0-line
    inputs because the alphabetically-first eligible rids are `walled` E4 games.

    `stratum` narrows further. `walled` carries BOTH strata (2 E4 games + the
    self-play bank), and cost is a function of the position mix (DESIGN §7.4:
    ~9x across phase), so a smoke that is meant to price the Stage A RUST arm
    must draw from the stratum that arm actually scores -- `selfplay` -- and not
    from whichever rids sort first.
    """
    arms = json.loads((Path(positions_dir) / "ARMS.json").read_text())
    eligible = sorted(
        rid for rid, info in arms.items()
        if len(info["arms"]) >= min_arms
        and (profile is None or info.get("rules_profile") == profile)
        and (stratum is None or info.get("stratum") == stratum))
    chosen = eligible[:n]
    note = None
    if len(chosen) < n:
        note = (f"only {len(chosen)} position(s) with >= {min_arms} arms available "
               f"(wanted {n}); using all of them" if chosen else
               f"NO positions with >= {min_arms} arms available -- cannot smoke the "
               "CRN cross-leg witness for real")
    return {"rids": chosen, "n_eligible": len(eligible), "note": note,
           "synthesized": len(chosen) < n}


def build_smoke_positions(positions_dir: Path, rids: list, profile: str,
                          legs=(1, 2)) -> dict:
    """Filter the already-built leg files down to the smoke's chosen rids."""
    out = {}
    for r in legs:
        src = Path(positions_dir) / f"positions_{profile}_leg{r}.jsonl"
        if not src.is_file():
            raise FileNotFoundError(f"no leg{r} positions file for profile "
                                    f"{profile!r}: {src}")
        chosen = [json.loads(ln) for ln in src.read_text().splitlines()
                 if ln.strip() and json.loads(ln)["rid"] in rids]
        out_path = Path(positions_dir) / "smoke" / f"smoke_{profile}_leg{r}.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("".join(json.dumps(x) + "\n" for x in chosen))
        out[r] = {"path": str(out_path), "n": len(chosen),
                 "rids": sorted(x["rid"] for x in chosen)}
    return out


def run_smoke(args, report: dict, plan: dict) -> int:
    """5 positions (or fewer, if that many multi-leg positions don't exist),
    production knobs, ONE judge (`--smoke-judge`, default `clair-puct`), run over
    >= 2 legs, then the CRN cross-leg witness. Exits non-zero on FAIL.

    `--smoke-judge tier1-greedy --arb-backend rust` is the W1 smoke: it exercises
    the rust ARB leg end to end and proves its cross-leg CRN witness, on the same
    5 positions and the same `--m` the run will use."""
    positions_dir = Path(args.positions_dir)
    profiles_present = sorted({k.split("/leg")[0] for k in plan.get("files", {})})
    profile = args.smoke_profile or (profiles_present[0] if profiles_present else None)
    if profile is None:
        print("[smoke] no rules profile present in POSITIONS_PLAN.json -- nothing "
             "to smoke", file=sys.stderr)
        return 3

    sel = select_smoke_positions(positions_dir, profile=profile,
                                 stratum=getattr(args, "smoke_stratum", None),
                                 min_arms=3, n=int(getattr(args, "smoke_n", 5) or 5))
    if sel["note"]:
        print(f"[smoke] NOTE: {sel['note']}")
    if not sel["rids"]:
        return 3
    built = build_smoke_positions(positions_dir, sel["rids"], profile, legs=(1, 2))

    t0 = time.time()
    logs_dir = Path(args.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["CARCASSONNE_FIX_R9"] = _r9_for(profile)
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")

    leg_out = {}
    for r, info in sorted(built.items()):
        sub = f"smoke/{args.smoke_judge}/{profile}/leg{r}"
        # profile-scoped: a second smoke on another profile must not overwrite
        # the log of the one DESIGN/SMOKE.md cites. Judge-scoped for the same
        # reason once --smoke-judge tier1-greedy exists (the W1 parity smoke).
        log = logs_dir / (f"smoke_{profile}_leg{r}.log"
                          if args.smoke_judge == "clair-puct" else
                          f"smoke_{args.smoke_judge}_{args.arb_backend}_{profile}"
                          f"_leg{r}.log")
        # W2: `--m` is a FLAG now (the campaign runs M=128) and the smoke must
        # follow it, not a hard-coded 32 -- a smoke at a different M than the run
        # it is pricing is exactly the "cheap-smoke extrapolation" the house rule
        # forbids. Defaults are unchanged (m=32, oracle_sims=100).
        cmd = leg_command(positions_path=info["path"], profile=profile,
                          judge=args.smoke_judge,
                          m=args.m, oracle_sims=args.oracle_sims,
                          workers=args.workers, n=info["n"],
                          out_root=args.out_root, out_subdir=sub,
                          arb_backend=args.arb_backend,
                          legal_mask_cache=args.arb_legal_mask_cache,
                          # Honour --resume/--no-resume. The smoke is NOT cheap on the
                          # python backend (measured ~20 min per leg at 5 workers on
                          # fixed_v1, SMOKE.md #3), and an interrupted smoke that has to
                          # redo completed positions is how a 40-minute job becomes an
                          # 80-minute one. Per-position records are written via tmp +
                          # os.replace by the pilot, so resuming is safe.
                          resume=bool(getattr(args, "resume", True)))
        fh = log.open("w")
        rc = subprocess.run(cmd, cwd=str(REPO), env=env, stdout=fh,
                            stderr=subprocess.STDOUT).returncode
        fh.close()
        leg_out[r] = {"rc": rc, "out": f"{args.out_root}/{sub}", "log": str(log),
                     "n": info["n"], "cmd": cmd}
    wall = time.time() - t0

    ok_launch = all(leg["rc"] == 0 for leg in leg_out.values())
    witness = None
    if ok_launch:
        records_by_leg = {r: load_leg_records(info["out"], sel["rids"])
                          for r, info in leg_out.items()}
        witness = check_crn_cross_leg(records_by_leg)

    n_positions = len(sel["rids"])
    n_legs = len(leg_out)
    n_playouts = max(1, n_positions * n_legs * 2 * args.m)
    worker_secs = wall * args.workers
    worker_secs_per_position = worker_secs / max(1, n_positions)
    worker_secs_per_playout = worker_secs / n_playouts

    # ⚠️ THE COST FIGURE OF RECORD (DESIGN §7.4 / SMOKE.md §3): Σ per-position
    # `elapsed_secs`, NOT wall x W. The pool's wall is set by its SLOWEST
    # position and these positions differ ~9x by game phase, so the wall-based
    # number is inflated (measured 1.9x on the python smoke: 18.75 vs 9.85).
    # Both are printed; only this one is costed from.
    elapsed_sum = 0.0
    per_position_secs = {}
    n_elapsed = 0
    if ok_launch:
        for r, info in sorted(leg_out.items()):
            for rid, rec in load_leg_records(info["out"], sel["rids"]).items():
                secs = float(rec.get("elapsed_secs") or 0.0)
                elapsed_sum += secs
                n_elapsed += 1
                per_position_secs.setdefault(rid, {})[f"leg{r}"] = secs
    c_sum = (elapsed_sum / n_playouts) if n_elapsed else None
    c_cost = c_sum if c_sum else worker_secs_per_playout

    eta = {}
    if plan.get("total_arm_playouts") is not None:
        sys.path.insert(0, str(REPO / "scripts" / "tiletie"))
        import build_positions as BP  # noqa: PLC0415

        for w in (14, 22):
            eta[f"W={w}"] = BP.full_run_eta_secs(plan, c_cost, w)

    print(f"\n[smoke] positions={n_positions} legs={n_legs} playouts={n_playouts} "
         f"wall_secs={wall:.1f} workers={args.workers}")
    print(f"[smoke] c (Σ elapsed_secs / playouts) = {c_sum if c_sum is None else round(c_sum, 4)} "
         f"worker-s/playout   <- COST FROM THIS "
         f"(Σ elapsed_secs = {elapsed_sum:.1f} over {n_elapsed} records)")
    print(f"[smoke] c (wall x W / playouts)       = {worker_secs_per_playout:.4f} "
         f"<- inflated by the slowest position, do NOT cost from this")
    for w, e in sorted(eta.items()):
        print(f"[smoke] extrapolated full-run ETA at {w} (from Σ elapsed_secs): "
             f"{e['wall_hours']:.3f} h ({e['wall_secs']:.0f} s)")

    if witness is not None:
        print(f"\nCRN CROSS-LEG WITNESS: {'PASS' if witness['ok'] else 'FAIL'} "
             f"({witness['n_ok']}/{witness['n_rids']} rids)")
        for rid, v in witness["per_rid"].items():
            if not v["ok"]:
                print(f"  FAIL {rid}: {v['problems']}")
    else:
        print("\nCRN CROSS-LEG WITNESS: NOT RUN (a leg subprocess failed)")

    manifest = {
        "schema": SCHEMA, "driver": "run_tiletie --smoke", "design_doc": DESIGN_DOC,
        "preflight": report, "profile": profile, "positions_selected": sel,
        "legs": leg_out, "wall_secs": round(wall, 1), "workers": args.workers,
        "n_positions": n_positions, "n_legs": n_legs,
        "m_worlds": args.m, "oracle_sims": args.oracle_sims,
        "judge": args.smoke_judge,
        "backend": backend_for(args.smoke_judge, profile, args.arb_backend),
        "arb_backend": args.arb_backend,
        "arb_legal_mask_cache": bool(args.arb_legal_mask_cache),
        "stratum": getattr(args, "smoke_stratum", None),
        "n_playouts": n_playouts,
        "elapsed_secs_sum": round(elapsed_sum, 3),
        "elapsed_secs_by_position": per_position_secs,
        "c_worker_secs_per_playout": c_sum,
        "c_worker_secs_per_playout_wall_based": worker_secs_per_playout,
        "c_note": "cost from c_worker_secs_per_playout (Σ elapsed_secs / playouts); "
                  "the wall-based figure is inflated by the slowest position "
                  "(DESIGN §7.4)",
        "worker_secs_per_position": worker_secs_per_position,
        "worker_secs_per_playout": worker_secs_per_playout, "eta": eta,
        "crn_cross_leg_identical": (witness["ok"] if witness else None),
        "crn_cross_leg_checked_rids": (witness["rids_checked"] if witness else []),
        "crn_cross_leg_detail": witness,
    }
    Path(args.smoke_manifest).write_text(json.dumps(manifest, indent=2))
    print(f"[smoke] manifest -> {args.smoke_manifest}")

    if not ok_launch:
        return 1
    return 0 if witness["ok"] else 1


# --------------------------------------------------------------------------- #
# manifest.json (written even on failure)                                       #
# --------------------------------------------------------------------------- #
def _sha256_file(path) -> str | None:
    p = Path(path)
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_manifest(args, report: dict | None, legs: list, path: Path, *,
                   error: str | None = None) -> dict:
    plan_path = Path(args.positions_dir) / "POSITIONS_PLAN.json"
    arms_path = Path(args.positions_dir) / "ARMS.json"
    manifest = {
        "schema": SCHEMA, "driver": "run_tiletie", "design_doc": DESIGN_DOC,
        "git_rev": ((report or {}).get("checks", {}).get("git_clean") or {}).get("git_rev"),
        "python": sys.executable,
        "preflight": report,
        "r9_by_profile": {p: _r9_for(p) for p in
                          sorted({leg["profile"] for leg in legs})} if legs else {},
        "judges": list(args.judges),
        # The DECLARED default map, and the RESOLVED per-(judge, profile) backend
        # that actually ran. They differ whenever --arb-backend rust is given or a
        # profile the rust mirror cannot represent forces a python fallback, and
        # confusing the two is how a manifest ends up claiming a backend the legs
        # did not use.
        "judge_backend": {j: JUDGE_BACKEND[j] for j in args.judges},
        "arb_backend": getattr(args, "arb_backend", "python"),
        "arb_legal_mask_cache": bool(getattr(args, "arb_legal_mask_cache", True)),
        "resolved_backend_by_leg": {
            f"{leg['judge']}/{leg['profile']}/leg{leg['leg']}": leg.get("backend")
            for leg in legs},
        "world_seed_salt": WORLD_SEED_SALT, "m_worlds": args.m,
        "m_max": M_MAX, "b_ceiling_from_m": int(args.m) // 2,
        "oracle_sims": args.oracle_sims, "workers": args.workers,
        "resume": bool(args.resume),
        "positions_plan_path": str(plan_path), "arms_path": str(arms_path),
        "positions_plan_sha256": _sha256_file(plan_path),
        "arms_sha256": _sha256_file(arms_path),
        "legs": legs,
        "error": error,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))
    return manifest


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--positions-dir", default=str(DEFAULT_POSITIONS_DIR))
    ap.add_argument("--out-root", default="/mnt/c/carc-shared/tiletie_pricing_20260812")
    ap.add_argument("--logs-dir", default=str(DEFAULT_LOGS_DIR))
    ap.add_argument("--gate-out", default=str(DEFAULT_GATE_RECHECK_OUT))
    ap.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--smoke-manifest", default=str(DEFAULT_SMOKE_MANIFEST))
    ap.add_argument("--judges", nargs="+", default=["clair-puct"],
                    choices=sorted(JUDGE_BACKEND),
                    help="default clair-puct ONLY -- see module docstring for why "
                         "tier1-greedy is not on by default")
    ap.add_argument("--m", type=int, default=32,
                    help=f"CRN worlds per position (1..{M_MAX}; default 32 = "
                         "Stage 1b). The widening campaign's shared run is "
                         "M=128: the estimator cross-fits on PARITY HALVES, so "
                         "usable B is capped at M/2, and B=64 needs M=128 "
                         "(PLAN_B_gt_16 §0.2). World seeds are prefix-stable in "
                         "M, so worlds 0..31 of an M=128 run are bit-identical "
                         "to a banked M=32 run.")
    ap.add_argument("--oracle-sims", type=int, default=100)
    ap.add_argument("--workers", "-W", type=int, default=14)
    ap.add_argument("--arb-backend", default="python", choices=list(ARB_BACKENDS),
                    help="engine for the ARB judge (`tier1-greedy`). DEFAULT "
                         "`python` = behaviour-preserving. `rust` routes those "
                         "legs through scripts/tiletie/tier1_rust_leg.py "
                         "(carc_rs.tier1_leg, Phase-A G-BITEXACT 15,360/15,360, "
                         "12.2x cheaper -- PLAN_B_gt_16 §0.3, work item W1). "
                         "Preflight FAILS if the wheel cannot do the job; there "
                         "is no silent fallback.")
    ap.add_argument("--arb-legal-mask-cache", action="store_true", default=True,
                    help="rust ARB legs reproduce the python judge's per-record "
                         "legal-mask memo (Game._legal_cache), collisions "
                         "included. REQUIRED for python/rust bit-comparability.")
    ap.add_argument("--no-arb-legal-mask-cache", dest="arb_legal_mask_cache",
                    action="store_false",
                    help="rust ARB legs use the HONEST recomputed legal mask. "
                         "NOT bit-comparable with the python judge.")
    ap.add_argument("--smoke-judge", default="clair-puct", choices=sorted(JUDGE_BACKEND),
                    help="judge to smoke (default clair-puct). Use "
                         "`--smoke-judge tier1-greedy --arb-backend rust` for the "
                         "W1 ARB-leg smoke.")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    ap.add_argument("--yes", action="store_true",
                    help="required to actually launch legs; without it the plan "
                         "and ETA are printed and the process exits 0 with "
                         "nothing launched")
    ap.add_argument("--smoke", action="store_true",
                    help="5-position production-knob smoke incl. the CRN "
                         "cross-leg witness, for --smoke-judge (default "
                         "clair-puct)")
    ap.add_argument("--smoke-profile", default=None,
                    help="rules profile to smoke (default: the first one present "
                         "in POSITIONS_PLAN.json)")
    ap.add_argument("--smoke-stratum", default=None, choices=["e4", "selfplay"],
                    help="restrict the smoke to one stratum. Required to price a "
                         "specific Stage A arm: `walled` carries both strata and "
                         "cost varies ~9x with the position mix (DESIGN §7.4).")
    ap.add_argument("--smoke-n", type=int, default=5,
                    help="number of smoke positions (default 5)")
    ap.add_argument("--only-profiles", nargs="+", default=None,
                    help="launch only these rules profiles' legs. Use it to run "
                         "the RUST arm (`walled`) and the PYTHON arm "
                         "(`fixed_v1 app_aug2`) as separate full-box "
                         "invocations -- which is how DESIGN §7.4 prices them. "
                         "A single mixed launch splits workers by position "
                         "COUNT and starves the ~8x-costlier python legs.")
    return ap


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    manifest_path = Path(args.manifest_out)
    report = None
    try:
        report = preflight(args)
        print_preflight(report)
        if not report["ok"]:
            print("\n[run_tiletie] PREFLIGHT FAILED -- refusing to launch.",
                 file=sys.stderr)
            write_manifest(args, report, [], manifest_path, error="preflight_failed")
            return 2

        plan = json.loads((Path(args.positions_dir) / "POSITIONS_PLAN.json").read_text())
        print()
        print_eta(plan)

        if args.smoke:
            return run_smoke(args, report, plan)

        if not args.yes:
            print("\n[run_tiletie] --yes not given: plan printed, NOT launching. "
                 "exit 0.")
            write_manifest(args, report, [], manifest_path)
            return 0

        legs = launch_legs(args, plan)
        for leg in legs:
            leg["records_verified"] = verify_leg_records(leg)
        write_manifest(args, report, legs, manifest_path)
        ok = bool(legs) and all(
            leg["rc"] == 0 and leg["records_verified"]["ok"] for leg in legs)
        return 0 if ok else 1
    except Exception as exc:                                       # noqa: BLE001
        write_manifest(args, report, [], manifest_path, error=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
