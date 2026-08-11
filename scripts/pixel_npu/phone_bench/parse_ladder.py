#!/usr/bin/env python3
"""Parse `run_ladder.sh`'s raw benchmark_model logs into JSON + a markdown table.

    python3 scripts/pixel_npu/phone_bench/parse_ladder.py \
        --results-dir /mnt/c/carc-shared/pixel_npu_20260729/phone_results

Exists so that no latency number ever reaches a document by being retyped from a terminal. Every
figure in `measurement/PIXEL_NPU_PREP_20260729.md` is produced here, from a log file on disk.

THE THING THIS PARSER IS REALLY FOR: benchmark_model will happily print a beautiful latency after
a delegate SILENTLY FELL BACK TO CPU. On a Pixel 9 Pro that is not hypothetical -- the
`google-edgetpu` NNAPI driver refuses this model and the tool quietly runs XNNPACK instead, at a
CPU speed that looks perfectly plausible next to the other rows. So every row is tagged with the
delegate that ACTUALLY executed the graph, parsed from the tool's own statements:

    "Explicitly applied <X> delegate, and the model graph will be completely executed by the
     delegate."                                            -> executed_by = X
    "Though <X> delegate is explicitly applied, the model graph will not be executed by the
     delegate."                                            -> requested X, FELL BACK
    "Replacing N out of M node(s) with delegate (<Kernel>)" -> the kernel that really ran, + N/M

A row whose `executed_by` differs from its `requested` is a fallback and is labelled as one.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
from pathlib import Path

# "INFO: count=200 first=.. curr=.. min=19918 max=46079 avg=22493.8 std=2717 p5=.. median=21899 p95=25453"
RE_COUNT = re.compile(
    r"count=(?P<count>\d+)\s+first=(?P<first>[\d.]+)\s+curr=(?P<curr>[\d.]+)\s+"
    r"min=(?P<min>[\d.]+)\s+max=(?P<max>[\d.]+)\s+avg=(?P<avg>[\d.]+)\s+std=(?P<std>[\d.]+)\s+"
    r"p5=(?P<p5>[\d.]+)\s+median=(?P<median>[\d.]+)\s+p95=(?P<p95>[\d.]+)")
RE_TIMINGS = re.compile(
    r"Inference timings in us: Init: (?P<init>[\d.]+), First inference: (?P<first>[\d.]+), "
    r"Warmup \(avg\): (?P<warmup>[\d.]+), Inference \(avg\): (?P<avg>[\d.]+)")
RE_APPLIED = re.compile(
    r"Explicitly applied (?P<who>[\w ]+?) delegate, and the model graph will be completely "
    r"executed by the delegate")
RE_NOTAPPLIED = re.compile(
    r"Though (?P<who>[\w ]+?) delegate is explicitly applied, the model graph will not be "
    r"executed by the delegate")
RE_REPLACING = re.compile(
    r"Replacing (?P<n>\d+) out of (?P<m>\d+) node\(s\) with delegate \((?P<kernel>[\w]+)\)")
RE_PEAK = re.compile(r"Overall peak memory footprint \(MB\) via periodic monitoring: ([\d.]+)")
RE_ACCEL = re.compile(r"NNAPI accelerators available: \[(?P<list>[^\]]*)\]")
RE_ERROR = re.compile(r"^ERROR: (?P<msg>.+)$", re.M)

KERNEL_LABEL = {
    "TfLiteXNNPackDelegate": "XNNPACK (CPU)",
    "TfLiteGpuDelegateV2": "GPU",
    "TfLiteNnapiDelegate": "NNAPI",
}


def parse_log(path: Path) -> dict:
    text = path.read_text(errors="replace")
    head = {}
    for line in text.splitlines():
        if line.startswith("### "):
            k, _, v = line[4:].partition("=")
            head[k.strip()] = v.strip()

    row: dict = {"label": path.stem, "model": head.get("model"), "flags": head.get("flags"),
                 "cmd": head.get("cmd")}

    # Which delegate was asked for? Resolve this BEFORE the hard-failure early return, so a
    # rejected cell still records what it was asking for -- that is the whole content of the
    # result ("the EdgeTPU refused this graph"), and dropping it would waste the row.
    flags = head.get("flags") or ""
    if "--use_gpu=true" in flags:
        requested = "GPU"
    elif "--use_nnapi=true" in flags:
        requested = "NNAPI"
    elif "--use_xnnpack=true" in flags:
        requested = "XNNPACK (CPU)"
    else:
        requested = "CPU (builtin kernels)"
    row["requested"] = requested

    errors = [m.group("msg") for m in RE_ERROR.finditer(text)]
    if errors:
        row["errors"] = errors
    if "Benchmarking failed" in text:
        row["ok"] = False
        row["outcome"] = f"HARD FAILURE -- the {requested} delegate refused the graph"
        row["executed_by"] = None
        return row

    fellback = RE_NOTAPPLIED.search(text)
    replacings = list(RE_REPLACING.finditer(text))
    last = replacings[-1] if replacings else None
    if last:
        row["executed_by"] = KERNEL_LABEL.get(last.group("kernel"), last.group("kernel"))
        row["nodes_delegated"] = f"{last.group('n')}/{last.group('m')}"
    elif RE_APPLIED.search(text):
        row["executed_by"] = requested
    else:
        row["executed_by"] = "CPU (builtin kernels)"
        row["nodes_delegated"] = None

    row["fellback"] = bool(fellback)
    if fellback:
        row["outcome"] = (f"{fellback.group('who')} delegate REFUSED the graph; "
                          f"ran on {row['executed_by']} instead")
    else:
        row["outcome"] = "ok"
    row["ok"] = True

    accel = RE_ACCEL.search(text)
    if accel:
        row["nnapi_accelerators_available"] = [s.strip() for s in accel.group("list").split(",")]

    t = RE_TIMINGS.search(text)
    if t:
        row["init_ms"] = float(t.group("init")) / 1000.0
        row["first_inference_ms"] = float(t.group("first")) / 1000.0
        row["avg_ms"] = float(t.group("avg")) / 1000.0
    # The LAST count= block is the measured run; earlier ones are warmup.
    counts = list(RE_COUNT.finditer(text))
    if counts:
        c = counts[-1]
        row["n_runs"] = int(c.group("count"))
        for k in ("min", "max", "std", "p5", "median", "p95"):
            row[f"{k}_ms"] = float(c.group(k)) / 1000.0
    peak = RE_PEAK.search(text)
    if peak:
        row["peak_mem_mb"] = float(peak.group(1))
    return row


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--results-dir", type=Path, required=True)
    p.add_argument("--baseline", default="cpu1_fp32",
                   help="label whose avg is the 1.00x reference for the speedup column")
    a = p.parse_args(argv)

    logs = sorted(a.results_dir.glob("*.log"))
    if not logs:
        raise SystemExit(f"parse_ladder: no *.log under {a.results_dir}; run run_ladder.sh first")
    rows = [parse_log(x) for x in logs]
    by_label = {r["label"]: r for r in rows}

    base = by_label.get(a.baseline, {}).get("avg_ms")
    for r in rows:
        if base and r.get("avg_ms"):
            r["speedup_vs_baseline"] = round(base / r["avg_ms"], 2)

    dev_file = a.results_dir / "device_state_before.txt"
    device = {}
    if dev_file.is_file():
        for line in dev_file.read_text(errors="replace").splitlines():
            for key in ("ro.product.model", "ro.soc.model", "ro.build.version.release"):
                if line.startswith(key + "="):
                    device[key] = line.split("=", 1)[1]
            s = line.strip()
            for key, name in (("level:", "battery_level"), ("temperature:", "battery_temp_dC"),
                              ("AC powered:", "ac_powered")):
                if s.startswith(key) and name not in device:
                    device[name] = s.split(":", 1)[1].strip()

    report = {
        "schema": "carcassonne-pixel-npu/v1",
        "kind": "on_device_delegate_ladder",
        "claim": "CL-067",
        "stage": "Eff Jensen",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": platform.node(),
        "device": device,
        "baseline_label": a.baseline,
        "baseline_avg_ms": base,
        "measurement_note": (
            "batch-1 forward latency only. num_runs=200 after warmup_runs=50. 'executed_by' is "
            "parsed from benchmark_model's own delegate statements; rows where it differs from "
            "'requested' are silent CPU fallbacks and their latency is a CPU number."),
        "rows": rows,
    }
    out = a.results_dir / "LADDER.json"
    out.write_text(json.dumps(report, indent=2))

    # markdown
    md = ["| config | model | requested | actually executed by | nodes | avg ms | median ms "
          "| min ms | vs base |",
          "|---|---|---|---|---|---:|---:|---:|---:|"]
    order = ["cpu1_fp32", "xnn1_fp32", "xnn4_fp32", "xnn1_fp32_forcefp16",
             "gpu_fp16", "gpu_fp32_exact", "gpu_fp32_lossy",
             "nnapi_default_fp32", "nnapi_edgetpu_fp32", "nnapi_reference_fp32",
             "xnn1_int8dyn", "xnn4_int8dyn", "gpu_int8dyn", "nnapi_edgetpu_int8dyn",
             "xnn1_int8full", "gpu_int8full", "nnapi_edgetpu_int8full"]
    for lbl in order + [r["label"] for r in rows if r["label"] not in order]:
        r = by_label.get(lbl)
        if not r:
            continue
        if not r.get("ok"):
            md.append(f"| `{lbl}` | {r.get('model')} | {r.get('requested', '?')} | "
                      f"**REJECTED — hard failure** | — | — | — | — | — |")
            continue
        exec_by = r.get("executed_by") or "?"
        if r.get("fellback"):
            exec_by = f"**{exec_by} (FELL BACK)**"
        md.append(
            f"| `{lbl}` | {r.get('model')} | {r.get('requested')} | {exec_by} | "
            f"{r.get('nodes_delegated') or '—'} | {r.get('avg_ms', float('nan')):.2f} | "
            f"{r.get('median_ms', float('nan')):.2f} | {r.get('min_ms', float('nan')):.2f} | "
            f"{r.get('speedup_vs_baseline', float('nan')):.2f}× |")
    (a.results_dir / "LADDER.md").write_text("\n".join(md) + "\n")

    print("\n".join(md))
    print(f"\nparse_ladder: wrote {out} and {a.results_dir / 'LADDER.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
