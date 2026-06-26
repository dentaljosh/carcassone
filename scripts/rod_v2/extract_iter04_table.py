#!/usr/bin/env python3
"""Unified iter04-interrogation table: WR | Elo | paired margin pts/game | paired z.
Parses both tally formats (net-vs-heur eval_hybrid_handoff + net-vs-net v28_net_vs_net_orch).
Missing cells show '-'. Run anytime to see partial progress."""
import re, os

EVAL = "/mnt/c/carc-shared/rod_v2_flywheel/evals"
LOGS = f"{EVAL}/logs"


def _g(t, p, d=None):
    m = re.search(p, t, re.I)
    return m.group(1) if m else d


def heur(f):
    t = open(f).read()
    return dict(n=_g(t, r"games:\s*(\d+)"), wr=_g(t, r"winrate\s+([\d.]+)"),
                elo=_g(t, r"ELO \(A vs B\):\s*([-+]?[\d.]+)"),
                mar=_g(t, r"mean seat-balanced margin\s+([-+]?[\d.]+)"),
                z=_g(t, r"margin[^z]*z\s*=\s*([-+]?[\d.]+)"))


def nvn(f):
    t = open(f).read()
    wdl = re.search(r"(\d+)\s*W\s*/\s*(\d+)\s*D\s*/\s*(\d+)\s*L", t, re.I)
    n = str(sum(int(x) for x in wdl.groups())) if wdl else None
    return dict(n=n, wr=_g(t, r"\bwr\s+([\d.]+)"),
                elo=_g(t, r"ELO\s+([-+]?[\d.]+)"),
                mar=_g(t, r"paired:\s*mean\s+([-+]?[\d.]+)"),
                z=_g(t, r"paired_z\s+([-+]?[\d.]+)"))


ROWS = [
    ("iter04 vs h6400_v2.9 (top-up)", "heur", f"{LOGS}/rod2_iter04_vs_heur6400_v29_tally.log"),
    ("iter04 vs RoD1_v29 (head-to-head)", "nvn", f"{LOGS}/iter04_vs_rod1_v29.log"),
    ("iter04 vs h3200_v2.9 (compression)", "heur", f"{LOGS}/rod2_iter04_vs_heur3200_v29_tally.log"),
    ("iter06 vs iter04 (regression)", "nvn", f"{LOGS}/iter06_vs_iter04_v29.log"),
]

print("| matchup | n | WR | Elo | margin pt/game | paired z |")
print("|---|--:|--:|--:|--:|--:|")
for name, kind, f in ROWS:
    if not os.path.exists(f) or os.path.getsize(f) == 0:
        print(f"| {name} | - | - | - | - | - |"); continue
    try:
        d = heur(f) if kind == "heur" else nvn(f)
    except Exception:
        print(f"| {name} | (parse err) | - | - | - | - |"); continue
    f_ = lambda k: d.get(k) or "?"
    print(f"| {name} | {f_('n')} | {f_('wr')} | {f_('elo')} | {f_('mar')} | {f_('z')} |")
