"""Quick preliminary analysis of the bank-relabel strict rows (cross-check vs the
fresh strict_bank). Per-motif-row schema (takes pre-computed)."""
import json
import sys
from collections import defaultdict

LADDER = ["random", "greedy", "h800", "h3200", "h6400", "rod1"]
WEAK = {"random"}
STRONG = {"h3200", "h6400", "rod1", "iter08"}
PATH = sys.argv[1] if len(sys.argv) > 1 else "measurement/strategic_behavior_ladder/strict_labeled_bank.jsonl"


def opp_class(s):
    return "weak" if s in WEAK else ("strong" if s in STRONG else "mid")


rows = [json.loads(l) for l in open(PATH) if l.strip()]
bym = defaultdict(list)
for r in rows:
    bym[r["motif"]].append(r)

print(f"bank strict rows: {len(rows)}\n")
for m, rs in bym.items():
    games = {(r["regime"], r["seed"], r["g"]) for r in rs}
    byc = defaultdict(int)
    for r in rs:
        byc[opp_class(r["opp_spec"])] += 1
    print(f"## {m}: {len(rs)} opps, {len(games)} distinct games "
          f"(weak/mid/strong {byc['weak']}/{byc['mid']}/{byc['strong']})")
    # take rate by agent: all / competitive(|m|<=20) / vs weak
    print(f"  {'agent':8} {'all':>14} {'competitive':>16} {'vs_weak':>14} {'vs_strong':>14}")
    for ag in LADDER:
        def tr(sub):
            n = len(sub)
            k = sum(r["takes"].get(ag, 0) for r in sub)
            return f"{(100*k/n):.0f}% ({k}/{n})" if n else "--"
        comp = [r for r in rs if abs(r["margin_before"]) <= 20]
        weak = [r for r in rs if opp_class(r["opp_spec"]) == "weak"]
        strong = [r for r in rs if opp_class(r["opp_spec"]) == "strong"]
        print(f"  {ag:8} {tr(rs):>14} {tr(comp):>16} {tr(weak):>14} {tr(strong):>14}")
    # rod1 vs h6400 disagreements
    dis = [r for r in rs if r["takes"].get("h6400") and not r["takes"].get("rod1")]
    dis_c = sum(1 for r in dis if abs(r["margin_before"]) <= 20)
    rev = [r for r in rs if r["takes"].get("rod1") and not r["takes"].get("h6400")]
    print(f"  rod1-vs-h6400: h6400-take/rod1-miss={len(dis)} ({dis_c} competitive) ; rod1-take/h6400-miss={len(rev)}")
    # pre-move-controlled outcome (actual took vs miss)
    out = [r for r in rs if r.get("result_mover") in ("W", "L", "D")]
    for lab, f in [("all", lambda r: True), ("even(-4..4)", lambda r: -4 <= r["margin_before"] <= 4),
                   ("vs_weak", lambda r: opp_class(r["opp_spec"]) == "weak")]:
        sub = [r for r in out if f(r)]
        tk = [r for r in sub if r["actual_took"]]
        ms = [r for r in sub if not r["actual_took"]]
        def w(x):
            return (len(x), sum(1 for r in x if r["result_mover"] == "W") / len(x) if x else float("nan"))
        nt, pt = w(tk)
        nm, pm = w(ms)
        d = (pt - pm) * 100 if (nt and nm) else float("nan")
        print(f"    outcome[{lab:11}] take {pt*100:.0f}%({nt}) miss {pm*100:.0f}%({nm}) Δwin {d:+.0f}pp")
    print()
