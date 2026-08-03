#!/usr/bin/env python3
"""Render the exact-solver bench artifacts into the results block of BENCH.md.

Reads every `BENCH*.json` in a directory and splices a markdown table into
`BENCH.md` between the `<!--RESULTS-->` marker and the `## Caveats` heading, so
the prose is written once and the numbers are never hand-copied.

Usage:
  python scripts/rustport/render_solver_bench.py measurement/rust_solver_bench_20260803
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CELL_ORDER = ["rust_clairvoyant_ab_k4", "rust_clairvoyant_ab_k5",
              "rust_clairvoyant_ab_k6", "rust_marginalized_k3",
              "rust_marginalized_k4", "rust_marginalized_k5",
              "rust_marginalized_k5_probe", "py_clairvoyant_ab_k4"]


def fmt_ms(v):
    if v is None:
        return "—"
    return f"{v / 1000:.2f} s" if v >= 1000 else f"{v:.1f} ms"


def fmt_n(v):
    return "—" if v is None else f"{v:,}"


def pair_speedups(rows: list[dict]) -> dict:
    """Rust-vs-Python wall ratio, paired POSITION BY POSITION.

    Pairing matters more than the aggregate here: endgame difficulty at a fixed
    K spans orders of magnitude, so an unpaired ratio of two medians would be
    comparing different searches.
    """
    import statistics
    ok = [r for r in rows if r.get("status") == "ok"]
    out = {}
    ks = {r["k"] for r in ok}
    for k in sorted(ks):
        rmap = {r["pos"]: r for r in ok
                if r["k"] == k and r["engine"] == "rust"
                and r["mode"] == "clairvoyant" and r["alphabeta"]}
        pmap = {r["pos"]: r for r in ok
                if r["k"] == k and r["engine"] == "python"
                and r["mode"] == "clairvoyant" and r["alphabeta"]}
        shared = sorted(set(rmap) & set(pmap))
        if not shared:
            continue
        ratios = [pmap[p]["wall_ms"] / rmap[p]["wall_ms"] for p in shared]
        out[f"k{k}"] = {
            "n_paired": len(shared),
            "median_x": round(statistics.median(ratios), 2),
            "min_x": round(min(ratios), 2),
            "max_x": round(max(ratios), 2),
            "aggregate_x": round(sum(pmap[p]["wall_ms"] for p in shared)
                                 / sum(rmap[p]["wall_ms"] for p in shared), 2),
            "node_count_agreement":
                f"{sum(1 for p in shared if pmap[p]['nodes'] == rmap[p]['nodes'])}"
                f"/{len(shared)}",
            "value_agreement":
                f"{sum(1 for p in shared if pmap[p]['value'] == rmap[p]['value'])}"
                f"/{len(shared)}",
        }
    return out


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from bench_exact_solver import summarize  # noqa: E402

    d = Path(sys.argv[1])
    payloads = {}
    for p in sorted(d.glob("BENCH*.json")):
        payloads[p.name] = json.loads(p.read_text())

    cells: dict[str, dict] = {}
    speedups: dict[str, dict] = {}
    meta = {}
    for name, pay in payloads.items():
        for cell, s in pay["summary"].items():
            cells[cell] = {**s, "_artifact": name}
        speedups.update(pay.get("speedup_rust_vs_python", {}))
        meta.setdefault("host", pay.get("host"))
        meta.setdefault("carc_rs_version", pay.get("carc_rs_version"))

    # An INTERRUPTED run leaves only its incremental rows file; summarize that
    # too, so a cell that cost hours is never thrown away for want of a clean
    # exit.  A finished `.json` for the same cell wins.
    raw_rows: list[dict] = []
    for p in sorted(d.glob("BENCH*_rows.jsonl")):
        rows_by_cell: dict[str, list[dict]] = {}
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            raw_rows.append(r)
            rows_by_cell.setdefault(r["cell"], []).append(r)
        for cell, rows in rows_by_cell.items():
            if cell not in cells:
                cells[cell] = {**summarize(rows), "_artifact": p.name + " (partial)"}
    payloads.update({p.name: None for p in sorted(d.glob("BENCH*_rows.jsonl"))})

    # position-paired speedup from the raw rows, for cells that never got a
    # finished payload
    if raw_rows and not speedups:
        speedups.update(pair_speedups(raw_rows))

    lines = []
    lines.append(f"Host `{meta.get('host')}`, `carc_rs` {meta.get('carc_rs_version')}. "
                 f"Artifacts: {', '.join(f'`{n}`' for n in sorted(payloads))}.")
    lines.append("")
    lines.append("| cell | n ok / n | wall median | wall p90 | wall max | "
                 "nodes median | nodes max | TT entries max | peak RSS max | "
                 "timeouts |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    ordered = [c for c in CELL_ORDER if c in cells]
    ordered += [c for c in sorted(cells) if c not in CELL_ORDER]
    for c in ordered:
        s = cells[c]
        lines.append(
            f"| `{c}` | {s['n_ok']}/{s['n']} | {fmt_ms(s.get('wall_ms_median'))} | "
            f"{fmt_ms(s.get('wall_ms_p90'))} | {fmt_ms(s.get('wall_ms_max'))} | "
            f"{fmt_n(s.get('nodes_median'))} | {fmt_n(s.get('nodes_max'))} | "
            f"{fmt_n(s.get('tt_entries_max'))} | "
            f"{s.get('rss_peak_mb_max', '—')} MB | {s['n_timeout']} |")
    lines.append("")

    if speedups:
        lines.append("### Rust vs Python, position-paired")
        lines.append("")
        lines.append("| K | paired n | median × | min × | max × | aggregate × | "
                     "node-count agreement | value agreement |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for k, s in sorted(speedups.items()):
            lines.append(
                f"| {k} | {s['n_paired']} | {s['median_x']}× | {s['min_x']}× | "
                f"{s['max_x']}× | {s['aggregate_x']}× | "
                f"{s['node_count_agreement']} | {s['value_agreement']} |")
        lines.append("")

    md = d / "BENCH.md"
    text = md.read_text()
    head, _, rest = text.partition("<!--RESULTS-->")
    _, _, tail = rest.partition("## Caveats")
    md.write_text(head + "<!--RESULTS-->\n\n" + "\n".join(lines) + "\n## Caveats" + tail)
    print("\n".join(lines))
    print(f"-> {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
