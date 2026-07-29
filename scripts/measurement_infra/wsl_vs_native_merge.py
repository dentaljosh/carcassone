#!/usr/bin/env python3
"""Merge + audit the per-cell JSONs from ``wsl_vs_native_ab.sh`` (project "eff_linus").

MEASUREMENT INFRASTRUCTURE. Called by the driver; not meant to be run by hand
(it takes its configuration from the environment the driver exports).

Three jobs, in order of importance:

1. **Audit the A/B's validity BEFORE reporting any delta.** An A/B between two
   arms is only a virtualisation measurement if everything except the
   virtualisation is equal. This asserts, per cell and per arm:
     * the Cython leaf did NOT bind on either arm (``cython.leaf_active`` false)
       — otherwise a ~4.5x compiled-vs-interpreted gap would be reported as a
       hypervisor tax;
     * the CPython minor matches across arms;
     * for the net cells, the torch version and the checkpoint sha match.
   Any failure lands in ``audit.failures`` and sets ``ab_valid: false``. The
   deltas are still emitted (they are useful for debugging) but flagged.

2. **Pair the arms.** Per cell, take each arm's per-rep central statistic, use
   the MEDIAN across reps (n=3 — a mean would hand one contended rep the
   verdict), and report ``ratio = win / wsl``. ratio < 1 means native Windows is
   faster, i.e. a real WSL2 tax.

3. **Refuse to over-claim.** With reps=3 there is no interesting confidence
   interval, so none is printed: the JSON carries every per-rep sample and the
   spread (min/max across reps) so a reader can see whether the arm gap clears
   the run-to-run noise. A ratio inside the per-arm spread is NOT a finding.
"""
from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def load(path: str) -> dict | None:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def central_stat(cell: str, child: dict) -> tuple[float | None, str]:
    """The one number this cell contributes, and its unit-bearing name.

    champion cells -> p50 seconds per decision (p50, not mean: the champion's
    per-move cost is right-skewed by position complexity and we compare the same
    positions on both arms anyway).
    net cells      -> p50 ms of the FORWARD timing (the transport price), which
    is the row net_transport_bench.py calls ``forward``.
    """
    if cell.startswith("champ_"):
        buds = child.get("budgets") or []
        if not buds:
            return None, "p50_s_per_move"
        return float(buds[0]["overall"]["p50_s"]), "p50_s_per_move"
    rows = child.get("rows") or []
    if not rows:
        return None, "forward_p50_ms"
    tim = (rows[0].get("timings") or {}).get("forward")
    if not tim:
        return None, "forward_p50_ms"
    return float(tim["p50_ms"]), "forward_p50_ms"


def arm_facts(cell: str, child: dict) -> dict:
    """The equality-of-conditions facts the audit compares across arms."""
    if cell.startswith("champ_"):
        cy = child.get("cython") or {}
        return {
            "python": (child.get("machine") or {}).get("python"),
            "platform": (child.get("machine") or {}).get("platform"),
            "leaf_active": cy.get("leaf_active"),
            "leaf_path": cy.get("leaf_path"),
            "use_cy_leaf_flag": cy.get("use_cy_leaf_flag"),
            "use_flat_leaf": cy.get("use_flat_leaf"),
            "champion_id": (child.get("champion") or {}).get("id"),
            "n_positions": child.get("n_positions"),
        }
    man = child.get("manifest") or {}
    rows = child.get("rows") or []
    row0 = rows[0] if rows else {}
    return {
        "python": man.get("python"),
        "platform": man.get("platform"),
        "torch_version": man.get("torch_version"),
        "torch_cuda_version": man.get("torch_cuda_version"),
        "cuda_available": man.get("cuda_available"),
        "cuda_device_names": man.get("cuda_device_names"),
        "ckpt_sha256": man.get("ckpt_sha256"),
        "skipped": row0.get("skipped"),
        "n_params": (row0.get("rep") or {}).get("n_params"),
        "torch_num_threads": row0.get("torch_num_threads"),
    }


def win_side_probe() -> dict:
    """Ask the WINDOWS side what it sees — this is a reported deliverable.

    nvidia-smi.exe is the native-Windows driver's own view of the GPU; if the
    native arm could not see the device this is where it shows.
    """
    out: dict = {}
    try:
        r = subprocess.run(
            ["nvidia-smi.exe", "--query-gpu=name,driver_version,power.draw,"
             "utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30)
        out["nvidia_smi_exe"] = r.stdout.strip().replace("\r", "") or None
        out["nvidia_smi_exe_rc"] = r.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        out["nvidia_smi_exe"] = None
        out["nvidia_smi_exe_error"] = f"{type(exc).__name__}: {exc}"
    return out


def main() -> int:
    ndjson = Path(env("NDJSON"))
    merged_path = Path(env("MERGED"))
    smoke = env("SMOKE") == "1"

    runs = [json.loads(ln) for ln in ndjson.read_text().splitlines() if ln.strip()]
    for r in runs:
        r["child"] = load(r["child_json"])
        if r["child"] is None:
            tail = ""
            try:
                tail = Path(r["log"]).read_text(errors="replace")[-2000:]
            except OSError:
                pass
            r["child_missing"] = True
            r["log_tail"] = tail

    # ---- per cell / per arm -------------------------------------------------
    cells: dict[str, dict] = {}
    failures: list[str] = []
    for r in runs:
        cell, arm = r["cell"], r["arm"]
        c = cells.setdefault(cell, {"wsl": {"samples": [], "facts": []},
                                    "win": {"samples": [], "facts": []}})
        if r.get("child_missing") or r["rc"] != 0:
            failures.append(f"{cell}/{arm}/rep{r['rep']}: rc={r['rc']} "
                            f"child_json={'missing' if r.get('child_missing') else 'present'}")
            continue
        val, unit = central_stat(cell, r["child"])
        c["unit"] = unit
        if val is None:
            failures.append(f"{cell}/{arm}/rep{r['rep']}: no timing in child JSON")
            continue
        c[arm]["samples"].append(val)
        c[arm]["facts"].append(arm_facts(cell, r["child"]))

    for cell, c in cells.items():
        for arm in ("wsl", "win"):
            s = c[arm]["samples"]
            if s:
                c[arm]["median"] = statistics.median(s)
                c[arm]["min"] = min(s)
                c[arm]["max"] = max(s)
                c[arm]["spread_pct"] = (
                    100.0 * (max(s) - min(s)) / statistics.median(s)
                    if statistics.median(s) else None)
        # --- audit: the conditions that must be equal --------------------------
        f_wsl = c["wsl"]["facts"][0] if c["wsl"]["facts"] else {}
        f_win = c["win"]["facts"][0] if c["win"]["facts"] else {}
        if cell.startswith("champ_"):
            for arm, f in (("wsl", f_wsl), ("win", f_win)):
                if f and f.get("leaf_active"):
                    failures.append(
                        f"{cell}/{arm}: CYTHON LEAF BOUND (leaf_active=true). This "
                        "cell compares a compiled leaf against an interpreted one; "
                        "the delta is NOT a virtualisation measurement.")
                if f and f.get("use_cy_leaf_flag"):
                    failures.append(
                        f"{cell}/{arm}: CARCASSONNE_USE_CY_LEAF was not 0 "
                        "(use_cy_leaf_flag=true) — parity flag did not take.")
        else:
            if f_wsl and f_win and f_wsl.get("torch_version") != f_win.get("torch_version"):
                failures.append(
                    f"{cell}: torch version differs across arms "
                    f"({f_wsl.get('torch_version')} vs {f_win.get('torch_version')}) "
                    "— that is a torch A/B, not a virtualisation A/B.")
            if f_wsl and f_win and f_wsl.get("ckpt_sha256") != f_win.get("ckpt_sha256"):
                failures.append(f"{cell}: checkpoint sha differs across arms.")
            for arm, f in (("wsl", f_wsl), ("win", f_win)):
                if f and f.get("skipped"):
                    failures.append(f"{cell}/{arm}: row skipped — {f['skipped']}")
        if f_wsl and f_win:
            pw, pn = (f_wsl.get("python") or ""), (f_win.get("python") or "")
            if pw.split(".")[:2] != pn.split(".")[:2]:
                failures.append(
                    f"{cell}: CPython minor differs across arms ({pw} vs {pn}) — "
                    "this is a CPython release comparison, not a hypervisor one.")
        # --- the pairing -------------------------------------------------------
        mw, mn = c["wsl"].get("median"), c["win"].get("median")
        if mw and mn:
            c["ratio_win_over_wsl"] = mn / mw
            c["wsl_tax_pct"] = 100.0 * (mw - mn) / mn
            worst_spread = max(c["wsl"].get("spread_pct") or 0.0,
                               c["win"].get("spread_pct") or 0.0)
            c["gap_exceeds_run_spread"] = (
                abs(100.0 * (mw - mn) / mw) > worst_spread)

    result = {
        "manifest": {
            "project": "eff_linus",
            "script": "scripts/measurement_infra/wsl_vs_native_ab.sh",
            "merger": "scripts/measurement_infra/wsl_vs_native_merge.py",
            "purpose": ("price the WSL2 virtualisation tax on this box: nested-paging "
                        "cost on the pointer-chasing search (champ cells) and "
                        "/dev/dxg GPU-PV cost on batch-1 forwards (net cells)"),
            "not_a_strength_measurement": True,
            "roadmap": "G3 (per-move cost reduction), stage Eff Jensen",
            "stamp": env("STAMP"),
            "git_rev": env("GIT_REV"),
            "smoke": smoke,
            "smoke_is_not_a_measurement": smoke,
            "forced_despite_loadavg": env("FORCE") == "1",
            "reps": int(env("REPS", "0") or 0),
            "cells_requested": env("CELLS").split(","),
            "champ_limit_positions": int(env("CHAMP_LIMIT", "0") or 0),
            "net_calls": int(env("NET_CALLS", "0") or 0),
            "net_warmup": int(env("NET_WARMUP", "0") or 0),
            "arms": {
                "wsl": {"python_exe": env("WSL_PY"), "kind": "WSL2 guest (Hyper-V, "
                        "nested paging, GPU via /dev/dxg paravirtualisation)"},
                "win": {"python_exe": env("WIN_PY"), "kind": "native Windows NT "
                        "process (no guest kernel, native CUDA driver)"},
            },
            "stage_dir": env("STAGE_WSL"),
            "ckpt": env("CKPT"),
            "driver_host": platform.node(),
            "merged_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "windows_side_probe": win_side_probe(),
        "audit": {
            "ab_valid": not failures,
            "failures": failures,
            "note": ("ab_valid=false means the two arms did not differ ONLY by "
                     "virtualisation; any ratio below is a debugging aid, not a "
                     "measurement."),
        },
        "cells": cells,
        "runs": runs,
    }
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text(json.dumps(result, indent=2, default=str))

    # ---- stdout summary -----------------------------------------------------
    print()
    print("== eff_linus A/B summary ==")
    if smoke:
        print("   ⚠️  SMOKE RUN — tiny scale on a CONTENDED box.")
        print("   ⚠️  Every number below is plumbing evidence, NOT a measurement.")
    for cell, c in cells.items():
        unit = c.get("unit", "?")
        mw, mn = c["wsl"].get("median"), c["win"].get("median")
        if mw is None or mn is None:
            print(f"   {cell:<14} INCOMPLETE  wsl={mw} win={mn}")
            continue
        print(f"   {cell:<14} {unit:<18} wsl={mw:.4f}  win={mn:.4f}  "
              f"ratio(win/wsl)={c['ratio_win_over_wsl']:.3f}  "
              f"[spread wsl {c['wsl'].get('spread_pct', 0):.1f}% / "
              f"win {c['win'].get('spread_pct', 0):.1f}%]")
    if failures:
        print()
        print("   AUDIT FAILURES (the A/B is NOT valid as a virtualisation test):")
        for f in failures:
            print(f"     - {f}")
    else:
        print("   audit: OK — arms differ only by virtualisation.")

    # ---- ETA for the quiet-window run, derived from THIS run -----------------
    if smoke:
        per = {}
        for r in runs:
            per.setdefault(r["cell"], []).append(float(r["wallclock_s"]))
        print()
        print("   EST for the full quiet-window run, scaled from this smoke:")
        total = 0.0
        for cell, secs in per.items():
            s = statistics.mean(secs)
            if cell.startswith("champ_"):
                # smoke ran 3 positions; the full run does CHAMP_LIMIT
                scale = int(env("CHAMP_LIMIT_FULL", "12")) / 3.0
            else:
                scale = 2000.0 / 100.0
            est = s * scale * 2 * int(env("REPS_FULL", "3"))   # 2 arms x reps
            total += est
            print(f"     {cell:<14} ~{est / 60:.1f} min  (both arms, "
                  f"{env('REPS_FULL', '3')} reps)")
        print(f"     {'TOTAL':<14} ~{total / 60:.0f} min")
        print("     NOTE: smoke ran on a LOADED box, so this is an UPPER bound "
              "for the champ cells and a rough one for the net cells.")

    print(f"\n   merged -> {merged_path}")
    return 0 if not failures else 0   # never fail the driver on audit; report it


if __name__ == "__main__":
    sys.exit(main())
