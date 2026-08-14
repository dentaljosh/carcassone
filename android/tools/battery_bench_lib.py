#!/usr/bin/env python3
"""Host-side math + report engine for the on-device battery A/B bench.

``android/tools/battery_bench.sh`` owns everything adb; this module owns
everything testable: the ABAB schedule, current/voltage sign+unit
normalization, trapezoid energy integration, the move-hash identity gate, and
the per-arm summary/report. Pure functions throughout — the pytest suite is
``tests/android/test_battery_bench_lib.py``.

Sampler line format (written by the shell driver, device clock):

    <epoch_ms> <current_now_raw> <voltage_now_raw>

Sign convention: ``current_now`` polarity DIFFERS BY DEVICE (many report
negative while discharging, some positive). The bench runs strictly unplugged,
so discharge is known; the convention is detected from the median sample sign
and normalized so discharge power is positive. Units are assumed µA / µV
(the Pixel kernel convention) and sanity-checked: a voltage median outside
2.5–5.5 V at µV scale fails loudly rather than silently mis-scaling by 1000x.

CLI subcommands (used by the driver):
    schedule      print the interleaved run plan, one "rep arm tag" per line
    report        integrate + summarize; ABORTS (exit 2) on move-hash mismatch
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

SCHEMA = "carc-battery-bench-report/v1"

# µA * µV -> W
_UAUV_TO_W = 1e-12
# Voltage sanity window at µV scale (a Li-ion cell is ~3.0-4.5 V).
_V_LO_UV, _V_HI_UV = 2.5e6, 5.5e6
# Max tolerated gap between the window edge and the nearest sample (ms) before
# the integration is considered untrustworthy.
_MAX_EDGE_GAP_MS = 5000.0
_MIN_WINDOW_SAMPLES = 3


# --------------------------------------------------------------------------- #
# schedule
# --------------------------------------------------------------------------- #
def abab_schedule(arms: list[int], reps: int) -> list[tuple[int, int, str]]:
    """Interleaved (ABAB / ABCABC) plan: every rep cycles through ALL arms.

    Interleaving is the point: thermal drift, battery-SoC drift and background
    noise land on every arm rather than on whichever ran last.
    Returns ``[(rep, arm, tag), ...]`` in run order; tags are unique and
    filesystem-safe (``t<arm>_r<rep>``).
    """
    if reps < 1:
        raise ValueError(f"reps must be >= 1, got {reps}")
    if not arms:
        raise ValueError("arm list is empty")
    if len(set(arms)) != len(arms):
        raise ValueError(f"duplicate arms in {arms}")
    if any(a < 1 for a in arms):
        raise ValueError(f"arms must be >= 1 threads, got {arms}")
    return [(rep, arm, f"t{arm}_r{rep}")
            for rep in range(1, reps + 1) for arm in arms]


# --------------------------------------------------------------------------- #
# samples
# --------------------------------------------------------------------------- #
def parse_samples(text: str) -> list[tuple[float, float, float]]:
    """Parse sampler lines to ``[(t_ms, current_raw, voltage_raw)]``.

    Malformed lines (adb hiccups, partial writes) are skipped; order is
    enforced by sorting on the timestamp.
    """
    out: list[tuple[float, float, float]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            t, i, v = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        out.append((t, i, v))
    out.sort(key=lambda s: s[0])
    return out


def detect_sign(samples: list[tuple[float, float, float]]) -> int:
    """+1 if current_now is already positive while discharging, else -1.

    The bench refuses to run plugged in, so every sample is a discharge
    sample; the median sign IS the device's convention. A median of exactly 0
    (dead sampler) is refused.
    """
    if not samples:
        raise ValueError("no samples")
    med = statistics.median(s[1] for s in samples)
    if med == 0:
        raise ValueError("median current is 0 — sampler dead or device idle-clamped")
    return 1 if med > 0 else -1


def check_units(samples: list[tuple[float, float, float]]) -> None:
    """Fail loudly if voltage_now does not look like µV."""
    if not samples:
        raise ValueError("no samples")
    v_med = statistics.median(s[2] for s in samples)
    if not (_V_LO_UV <= v_med <= _V_HI_UV):
        raise ValueError(
            f"voltage_now median {v_med:g} is outside the µV sanity window "
            f"[{_V_LO_UV:g}, {_V_HI_UV:g}] — this device likely reports mV or "
            f"V; teach the normalizer its scale before trusting any joules")


def power_series(samples: list[tuple[float, float, float]],
                 sign: int) -> list[tuple[float, float]]:
    """``[(t_ms, watts)]`` with discharge power normalized positive."""
    return [(t, (sign * i) * v * _UAUV_TO_W) for (t, i, v) in samples]


def integrate_joules(power: list[tuple[float, float]],
                     t0_ms: float, t1_ms: float) -> float:
    """Trapezoid-integrate watts over [t0_ms, t1_ms] -> joules.

    Uses linear interpolation at the window edges when a neighbouring sample
    exists outside the window; refuses windows with too few samples or with an
    edge gap over ``_MAX_EDGE_GAP_MS`` (a died sampler must not silently
    under-report energy).
    """
    if t1_ms <= t0_ms:
        raise ValueError(f"bad window [{t0_ms}, {t1_ms}]")
    pts = [(t, w) for (t, w) in power if t0_ms <= t <= t1_ms]
    if len(pts) < _MIN_WINDOW_SAMPLES:
        raise ValueError(
            f"only {len(pts)} samples inside [{t0_ms:.0f}, {t1_ms:.0f}] "
            f"(need >= {_MIN_WINDOW_SAMPLES}) — sampler gap?")

    def _interp(ta: float, wa: float, tb: float, wb: float, t: float) -> float:
        if tb == ta:
            return wa
        return wa + (wb - wa) * (t - ta) / (tb - ta)

    before = [(t, w) for (t, w) in power if t < t0_ms]
    after = [(t, w) for (t, w) in power if t > t1_ms]
    if before:
        tb, wb = before[-1]
        pts.insert(0, (t0_ms, _interp(tb, wb, pts[0][0], pts[0][1], t0_ms)))
    elif pts[0][0] - t0_ms > _MAX_EDGE_GAP_MS:
        raise ValueError(
            f"first sample {pts[0][0] - t0_ms:.0f} ms after window start "
            f"(> {_MAX_EDGE_GAP_MS:.0f} ms) — sampler started late?")
    if after:
        ta, wa = after[0]
        pts.append((t1_ms, _interp(pts[-1][0], pts[-1][1], ta, wa, t1_ms)))
    elif t1_ms - pts[-1][0] > _MAX_EDGE_GAP_MS:
        raise ValueError(
            f"last sample {t1_ms - pts[-1][0]:.0f} ms before window end "
            f"(> {_MAX_EDGE_GAP_MS:.0f} ms) — sampler died?")

    joules = 0.0
    for (ta, wa), (tb, wb) in zip(pts, pts[1:]):
        joules += 0.5 * (wa + wb) * (tb - ta) / 1000.0
    return joules


def mean_watts(power: list[tuple[float, float]],
               t0_ms: float, t1_ms: float) -> float:
    return integrate_joules(power, t0_ms, t1_ms) / ((t1_ms - t0_ms) / 1000.0)


# --------------------------------------------------------------------------- #
# identity gate
# --------------------------------------------------------------------------- #
def check_hashes(runs: list[dict]) -> tuple[bool, dict[str, str]]:
    """The play-identity witness across arms.

    Every run of the SAME (seed, n_moves, budget) must report the same
    ``move_hash`` regardless of ``rust_threads`` — thread-count invariance of
    the rust search is proven upstream, so a mismatch means the arms did
    DIFFERENT WORK and the energy comparison is void. Returns
    ``(ok, {tag: hash})``.
    """
    by_tag = {str(r.get("tag")): str(r.get("move_hash")) for r in runs}
    if not by_tag:
        return False, by_tag
    if any(h in ("None", "") for h in by_tag.values()):
        return False, by_tag
    return len(set(by_tag.values())) == 1, by_tag


def _fail_runs(runs: list[dict]) -> list[dict]:
    return [r for r in runs if not r.get("ok")]


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #
def _mean_sd(xs: list[float]) -> tuple[float, float]:
    m = statistics.fmean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else float("nan")
    return m, sd


def summarize(runs: list[dict], power: list[tuple[float, float]],
              baseline_w: float | None) -> dict:
    """Per-arm energy/latency summary. Assumes hashes were already gated."""
    arms: dict[int, dict] = {}
    for r in sorted(runs, key=lambda r: (int(r["rust_threads"]), str(r["tag"]))):
        arm = int(r["rust_threads"])
        t0, t1 = float(r["t_start_ms"]), float(r["t_end_ms"])
        joules = integrate_joules(power, t0, t1)
        n = int(r["n_moves"])
        dur_s = (t1 - t0) / 1000.0
        rec = {
            "tag": r["tag"],
            "joules": joules,
            "j_per_move": joules / n,
            "watts_mean": joules / dur_s,
            "s_per_move": float(r["s_per_move_mean"]),
            "window_s": dur_s,
        }
        if baseline_w is not None:
            rec["j_per_move_net"] = (joules - baseline_w * dur_s) / n
        arms.setdefault(arm, {"runs": []})["runs"].append(rec)

    for arm, blob in arms.items():
        rr = blob["runs"]
        for key in ("j_per_move", "s_per_move", "watts_mean", "j_per_move_net"):
            vals = [r[key] for r in rr if key in r]
            if vals:
                m, sd = _mean_sd(vals)
                blob[f"{key}_mean"] = m
                blob[f"{key}_sd"] = sd
        blob["n_reps"] = len(rr)
    return arms


def _fmt(x: float, digits: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:.{digits}f}"


def markdown_table(arms: dict, baseline_w: float | None) -> str:
    lines = [
        "| rust_threads | reps | J/move (mean ± sd) | s/move (mean ± sd) | mean W |"
        + (" net J/move |" if baseline_w is not None else ""),
        "|---|---|---|---|---|" + ("---|" if baseline_w is not None else ""),
    ]
    for arm in sorted(arms):
        b = arms[arm]
        row = (f"| {arm} | {b['n_reps']} "
               f"| {_fmt(b['j_per_move_mean'])} ± {_fmt(b.get('j_per_move_sd'))} "
               f"| {_fmt(b['s_per_move_mean'])} ± {_fmt(b.get('s_per_move_sd'))} "
               f"| {_fmt(b['watts_mean_mean'], 2)} |")
        if baseline_w is not None:
            row += f" {_fmt(b.get('j_per_move_net_mean'))} |"
        lines.append(row)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# report (the driver's single analysis entry point)
# --------------------------------------------------------------------------- #
def build_report(runs: list[dict], samples_text: str,
                 baseline: tuple[float, float] | None) -> tuple[dict, str]:
    """(report_dict, markdown). Raises SystemExit(2) on any identity failure —
    deliberately BEFORE any energy number is computed or printed."""
    bad = _fail_runs(runs)
    if bad:
        raise SystemExit(
            "ABORT — failed bench runs (no energy numbers will be printed):\n"
            + "\n".join(f"  {r.get('tag')}: {r.get('error')}" for r in bad))
    ok, by_tag = check_hashes(runs)
    if not ok:
        detail = "\n".join(f"  {t}: {h}" for t, h in sorted(by_tag.items()))
        raise SystemExit(
            "ABORT — move_hash DIFFERS across runs. The arms did not do "
            "identical work, so an energy comparison is meaningless. This "
            "contradicts the proven thread-count invariance of the rust "
            "search — investigate before re-running (mixed app builds? a "
            "run that degraded to the python floor?).\n"
            "No energy numbers were computed.\n" + detail)

    samples = parse_samples(samples_text)
    check_units(samples)
    sign = detect_sign(samples)
    power = power_series(samples, sign)

    baseline_w = None
    if baseline is not None:
        baseline_w = mean_watts(power, baseline[0], baseline[1])

    arms = summarize(runs, power, baseline_w)
    report = {
        "schema": SCHEMA,
        "move_hash": next(iter(by_tag.values())),
        "hash_identical_across_runs": True,
        "sign_convention": ("current_now positive on discharge" if sign == 1
                            else "current_now negative on discharge (normalized)"),
        "n_samples": len(samples),
        "baseline_watts": baseline_w,
        "workload": {k: runs[0][k] for k in
                     ("n_moves", "seed", "k_dets", "sims_per_det",
                      "total_sims", "rules_profile", "backend")},
        "arms": arms,
        "runs_order": [r["tag"] for r in runs],
    }

    md = (
        "# Battery A/B bench — results\n\n"
        f"Workload: {runs[0]['n_moves']} champion moves/run, seed "
        f"{runs[0]['seed']}, budget k{runs[0]['k_dets']}x"
        f"{runs[0]['sims_per_det']}={runs[0]['total_sims']}, rules "
        f"`{runs[0]['rules_profile']}`, backend `{runs[0]['backend']}`.\n\n"
        f"Identity gate: PASS — all {len(runs)} runs report move_hash "
        f"`{report['move_hash'][:16]}…` (identical play across arms).\n\n"
        + (f"Idle baseline: {baseline_w:.2f} W (subtracted in the net column).\n\n"
           if baseline_w is not None else "")
        + markdown_table(arms, baseline_w)
        + "\n\n*J/move integrates the whole workload window (search + engine "
          "bookkeeping between moves). The J/move-vs-latency trade is the "
          "owner's call — see android/tools/BATTERY_BENCH.md.*\n"
    )
    return report, md


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cmd_schedule(args) -> int:
    arms = [int(a) for a in args.arms.replace(",", " ").split()]
    for rep, arm, tag in abab_schedule(arms, args.reps):
        print(f"{rep} {arm} {tag}")
    return 0


def _cmd_report(args) -> int:
    runs = []
    run_files = sorted(Path(args.runs_dir).glob("*.json"))
    if not run_files:
        print(f"no run JSONs under {args.runs_dir}", file=sys.stderr)
        return 2
    for p in run_files:
        runs.append(json.loads(p.read_text()))
    samples_text = Path(args.samples).read_text()
    baseline = None
    if args.baseline:
        lo, hi = args.baseline.split(":")
        baseline = (float(lo), float(hi))
    report, md = build_report(runs, samples_text, baseline)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(report, indent=1))
    (out / "results.md").write_text(md)
    print(md)
    print(f"\nwrote {out / 'results.json'} and {out / 'results.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="battery_bench_lib")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("schedule", help="print the interleaved run plan")
    s.add_argument("--arms", required=True, help='e.g. "4,2,1"')
    s.add_argument("--reps", type=int, default=3)
    s.set_defaults(fn=_cmd_schedule)

    r = sub.add_parser("report", help="integrate, gate on hashes, summarize")
    r.add_argument("--runs-dir", required=True,
                   help="directory of per-run result JSONs pulled off the phone")
    r.add_argument("--samples", required=True,
                   help="sampler file: '<epoch_ms> <current_now> <voltage_now>' lines")
    r.add_argument("--baseline", default=None,
                   help="idle-baseline window 'T0MS:T1MS' (device epoch ms)")
    r.add_argument("--out-dir", required=True)
    r.set_defaults(fn=_cmd_report)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
