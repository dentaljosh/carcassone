#!/usr/bin/env python3
"""Cluster status reader — Tier A (table) + Tier B (live web page).

Reads the per-box heartbeats at <share>/status/*.json (written by
cluster_heartbeat.py) and renders them. STDLIB ONLY.

  # Tier A — one-shot consolidated table (deterministic status check):
  python3 scripts/cluster_status.py --share /mnt/c/carc-shared

  # Tier B — live auto-refreshing web page (serve on the 5800x):
  nohup python3 scripts/cluster_status.py --share /mnt/c/carc-shared \
      --serve 8765 > /tmp/dashboard.log 2>&1 & disown
  # then open http://<5800x-LAN-or-tailscale-ip>:8765/
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

STALE_S = 15.0  # heartbeat older than this -> box considered stale/offline


def load_statuses(share: str) -> list[dict]:
    d = Path(share) / "status"
    out = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except Exception:
            continue
    return out


def _gpu_short(g: dict | None) -> tuple[str, str, str]:
    if not g:
        return ("-", "-", "-")
    name = g["name"].replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
    util = f"{name} {g['util']:.0f}%"
    p, pl = g.get("power"), g.get("power_limit")
    pwr = (f"{p:.0f}/{pl:.0f}W" if p is not None and pl is not None
           else (f"{p:.0f}W" if p is not None else "-"))
    vu, vt = g.get("vram_used"), g.get("vram_total")
    vram = f"{vu/1024:.1f}/{vt/1024:.1f}G" if vu is not None and vt else "-"
    return (util, pwr, vram)


def _job_str(s: dict) -> str:
    jobs = s.get("jobs") or {}
    if not jobs:
        return "idle"
    return ", ".join(f"{lbl} x{n}" for lbl, n in jobs.items())


# ---------- Tier A: text ----------
def format_text(statuses: list[dict], now: float) -> str:
    hdr = f"{'HOST':<10} {'CPU%':>5} {'LOAD':>10} {'GPU':<16} {'PWR':>10} {'VRAM':>11}  {'JOB':<28} {'PY':>3} {'AGE':>6}"
    lines = [f"CLUSTER @ {time.strftime('%H:%M:%S', time.localtime(now))}", hdr, "-" * len(hdr)]
    for s in statuses:
        age = now - s.get("ts", 0)
        load = s.get("loadavg", [0])[0]
        ncpu = s.get("ncpu", 0)
        util, pwr, vram = _gpu_short(s.get("gpu"))
        if age > STALE_S:
            lines.append(f"{s.get('host','?'):<10} {'--':>5} {'--':>10} {'--':<16} {'--':>10} {'--':>11}  {'STALE':<28} {'--':>3} {age:>5.0f}s")
            continue
        lines.append(
            f"{s.get('host','?'):<10} {s.get('cpu_pct',0):>5.0f} {f'{load:.1f}/{ncpu}':>10} "
            f"{util:<16} {pwr:>10} {vram:>11}  {_job_str(s):<28} {s.get('py_procs',0):>3} {age:>5.0f}s"
        )
    if not statuses:
        lines.append("(no heartbeats found — are the writers running?)")
    return "\n".join(lines)


# ---------- Tier B: html ----------
def _bar(pct: float, color: str) -> str:
    pct = max(0.0, min(100.0, pct))
    return (f"<div class='bar'><div class='fill' style='width:{pct:.0f}%;"
            f"background:{color}'></div><span>{pct:.0f}%</span></div>")


def format_html(statuses: list[dict], now: float) -> str:
    rows = []
    for s in statuses:
        age = now - s.get("ts", 0)
        host = s.get("host", "?")
        if age > STALE_S:
            rows.append(f"<tr class='stale'><td>{host}</td><td colspan='6'>"
                        f"STALE — last seen {age:.0f}s ago</td></tr>")
            continue
        ncpu = s.get("ncpu", 0)
        load = s.get("loadavg", [0])[0]
        cpu = s.get("cpu_pct", 0)
        g = s.get("gpu")
        gcell = "-"
        if g:
            name = g["name"].replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
            gutil = _bar(g["util"], "#4ea1ff")
            p, pl = g.get("power"), g.get("power_limit")
            pwr = (f"{p:.0f}/{pl:.0f}W" if p is not None and pl is not None
                   else (f"{p:.0f}W" if p is not None else "?W"))
            vu, vt = g.get("vram_used"), g.get("vram_total")
            if vu is not None and vt:
                vram = f"VRAM {vu/1024:.1f}/{vt/1024:.1f}G ({100.0*vu/vt:.0f}%)"
            else:
                vram = "VRAM ?"
            gcell = f"<b>{name}</b><br>{gutil}<small>{pwr} · {vram}</small>"
        cpu_color = "#39d353" if cpu < 70 else ("#e3b341" if cpu < 90 else "#f85149")
        rows.append(
            f"<tr><td><b>{host}</b></td>"
            f"<td>{_bar(cpu, cpu_color)}</td>"
            f"<td>{load:.1f}/{ncpu}</td>"
            f"<td>{gcell}</td>"
            f"<td>{_job_str(s)}</td>"
            f"<td>{s.get('py_procs',0)}</td>"
            f"<td>{age:.0f}s</td></tr>"
        )
    body = "\n".join(rows) or "<tr><td colspan='7'>no heartbeats found</td></tr>"
    ts = time.strftime("%H:%M:%S", time.localtime(now))
    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta http-equiv="refresh" content="3">
<title>carc cluster</title>
<style>
 body{{background:#0d1117;color:#c9d1d9;font:14px/1.5 ui-monospace,Menlo,monospace;margin:24px}}
 h1{{font-size:16px;color:#8b949e;font-weight:600}}
 table{{border-collapse:collapse;width:100%;max-width:1100px}}
 th,td{{padding:8px 12px;border-bottom:1px solid #21262d;text-align:left;vertical-align:top}}
 th{{color:#8b949e;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}}
 tr.stale td{{color:#f85149}}
 small{{color:#8b949e}}
 .bar{{position:relative;background:#21262d;border-radius:4px;height:18px;width:130px;overflow:hidden}}
 .fill{{height:100%}}
 .bar span{{position:absolute;left:8px;top:0;font-size:12px;line-height:18px;color:#fff;text-shadow:0 0 2px #000}}
</style></head><body>
<h1>carcassonne cluster · {ts} · refreshes every 3s</h1>
<table><tr><th>host</th><th>cpu</th><th>load</th><th>gpu</th><th>job</th><th>py</th><th>age</th></tr>
{body}
</table></body></html>"""


def serve(share: str, port: int) -> int:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/index.html"):
                self.send_response(404); self.end_headers(); return
            html = format_html(load_statuses(share), time.time()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, *a):  # quiet
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    print(f"dashboard serving on http://0.0.0.0:{port}/  (share={share})", flush=True)
    srv.serve_forever()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cluster_status")
    ap.add_argument("--share", required=True)
    ap.add_argument("--serve", type=int, metavar="PORT",
                    help="run the live web dashboard on this port (Tier B)")
    args = ap.parse_args(argv)
    if args.serve:
        return serve(args.share, args.serve)
    print(format_text(load_statuses(args.share), time.time()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
