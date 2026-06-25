"""Validation audit: is `farm_claim` genuinely diagnostic/actionable, or a proxy for
already-good positions? Computes confound-controlled stratifications from the harvest.

Methodology notes (surfaced in the output):
- score_margin_before (smb) = scores[mover]-scores[opp] is a PRE-move covariate (clean).
- final_margin / 'close game' is a POST-move OUTCOME; conditioning on it is conditioning
  on a consequence (collider risk). We report the UNCONDITIONED analysis as primary and
  flag the close-game framing as secondary.
- True matched-pair on identical positions is impossible (one real outcome per game), so the
  control is stratification on pre-move covariates + within-agent self-play (mover==opp agent).
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from roster import PANEL

H = "measurement/strategic_behavior_ladder/harvest/local.jsonl"
WEAK = {"random"}
STRONG = {"h3200", "h6400", "rod1", "iter08"}
SELFPLAY = {"greedy:greedy", "rod1:rod1", "h800:h800", "random:random"}


def opp_class(s):
    return "weak" if s in WEAK else ("strong" if s in STRONG else "mid")


def load():
    return [json.loads(l) for l in open(H) if l.strip()]


def smb(r):
    return r["scores"][r["mover"]] - r["scores"][1 - r["mover"]]


def took(r, ag, m="farm_claim"):
    if m not in r["labels"]:
        return None
    sat = set(r["labels"][m]["sat"])
    a = r["chosen"] if ag == "ACTUAL" else r["choices"].get(ag, -2)
    return a in sat


def wr(rs):
    n = len(rs)
    if not n:
        return (0, 0, float("nan"), float("nan"))
    w = sum(1 for r in rs if r["result_mover"] == "W")
    mar = sum(r["final_margin_mover"] for r in rs) / n
    return (w, n, w / n, mar)


def line(name, t, m):
    wt, nt, pt, mt = wr(t)
    wm, nm, pm, mm = wr(m)
    d = (pt - pm) if (nt and nm) else float("nan")
    dm = (mt - mm) if (nt and nm) else float("nan")
    flag = " ⚠thin" if (nt < 20 or nm < 20) else ""
    print(f"  {name:28} take {pt*100:4.0f}% (n={nt:4d}, mar{mt:+5.1f}) | "
          f"miss {pm*100:4.0f}% (n={nm:4d}, mar{mm:+5.1f}) | Δwin {d*100:+4.0f}pp Δmar {dm:+4.1f}{flag}")


def main():
    recs = load()
    farm = [r for r in recs if "farm_claim" in r["labels"] and r.get("result_mover") in ("W", "L", "D")]
    T = lambda rs: [r for r in rs if took(r, "ACTUAL")]
    M = lambda rs: [r for r in rs if took(r, "ACTUAL") is False]

    print("=" * 78)
    print("Q2 — CELL SIZES (farm_claim opportunities; ACTUAL mover took vs missed)")
    print("=" * 78)
    print(f"total farm_claim opps with outcome: {len(farm)}  (took {len(T(farm))}, miss {len(M(farm))})")
    print("\nby mover_spec:")
    for sp in ["random", "greedy", "h200", "h800", "h3200", "h6400", "rod1", "iter08"]:
        rs = [r for r in farm if r["mover_spec"] == sp]
        print(f"  {sp:10} n={len(rs):4d}  took={len(T(rs)):4d} miss={len(M(rs)):4d}")
    print("\nby opp_class:")
    for c in ("weak", "mid", "strong"):
        rs = [r for r in farm if opp_class(r["opp_spec"]) == c]
        print(f"  {c:8} n={len(rs):4d}  took={len(T(rs)):4d} miss={len(M(rs)):4d}")
    print("\nby phase:")
    for ph in ("opening", "midgame", "late_mid", "pre_endgame", "endgame"):
        rs = [r for r in farm if r["phase"] == ph]
        print(f"  {ph:12} n={len(rs):4d}  took={len(T(rs)):4d} miss={len(M(rs)):4d}")
    close = [r for r in farm if abs(r["final_margin_mover"]) <= 5]
    print(f"\nclose-game subset (|final margin|<=5): n={len(close)} took={len(T(close))} miss={len(M(close))}  ⚠ small")

    print("\n" + "=" * 78)
    print("Q3 — FARM_CLAIM CAUSALITY (confound controls). win% = P(mover wins)")
    print("=" * 78)
    print("\n[A] UNCONDITIONED (full sample, NOT conditioning on close games):")
    line("all farm_claim", T(farm), M(farm))

    print("\n[B] CONFOUND: is taking associated with ALREADY LEADING (pre-move margin)?")
    st, sm = [smb(r) for r in T(farm)], [smb(r) for r in M(farm)]
    print(f"  mean pre-move score margin:  took {sum(st)/len(st):+.2f}  vs  miss {sum(sm)/len(sm):+.2f}")
    print("  (if took >> miss, the win effect is partly 'already ahead')")

    print("\n[C] STRATIFY by pre-move score margin bucket (controls for leading state):")
    for lab, lo, hi in [("behind (<=-5)", -999, -5), ("even (-4..4)", -4, 4), ("ahead (>=5)", 5, 999)]:
        rs = [r for r in farm if lo <= smb(r) <= hi]
        line(lab, T(rs), M(rs))

    print("\n[D] STRATIFY by mover agent (controls for who-is-the-mover):")
    for sp in ["greedy", "h800", "h3200", "h6400", "rod1", "iter08"]:
        rs = [r for r in farm if r["mover_spec"] == sp]
        line(sp, T(rs), M(rs))

    print("\n[E] WITHIN-AGENT SELF-PLAY (mover==opp agent; cleanest agent control):")
    for rg in sorted(SELFPLAY):
        rs = [r for r in farm if r["regime"] == rg]
        line(rg, T(rs), M(rs))

    print("\n[F] STRATIFY by phase / opp_class / farm value / legal_n:")
    for ph in ("opening", "midgame", "late_mid", "pre_endgame", "endgame"):
        line(f"phase={ph}", T([r for r in farm if r["phase"] == ph]), M([r for r in farm if r["phase"] == ph]))
    for c in ("weak", "mid", "strong"):
        rs = [r for r in farm if opp_class(r["opp_spec"]) == c]
        line(f"opp={c}", T(rs), M(rs))
    for lab, lo, hi in [("farm proj=6", 6, 6), ("farm proj=9", 9, 9), ("farm proj>=12", 12, 999)]:
        rs = [r for r in farm if lo <= r["labels"]["farm_claim"]["mag"] <= hi]
        line(lab, T(rs), M(rs))

    print("\n[G] COMBINED control (EVEN pre-move margin AND non-weak opp): does it survive?")
    rs = [r for r in farm if -4 <= smb(r) <= 4 and opp_class(r["opp_spec"]) != "weak"]
    line("even+nonweak", T(rs), M(rs))

    print("\n" + "=" * 78)
    print("Q4 — h6400 vs RoD1 on identical positions (counterfactual)")
    print("=" * 78)
    fc = [r for r in recs if "farm_claim" in r["labels"]]
    def cf(ag, r): return took(r, ag)
    h_take = sum(1 for r in fc if cf("h6400", r))
    r_take = sum(1 for r in fc if cf("rod1", r))
    print(f"farm opps (both evaluated): {len(fc)}  | h6400 take {h_take} ({h_take/len(fc)*100:.0f}%)  "
          f"rod1 take {r_take} ({r_take/len(fc)*100:.0f}%)  Δ {(h_take-r_take)/len(fc)*100:+.0f}pp")
    dis = [r for r in fc if cf("h6400", r) and not cf("rod1", r)]
    rev = [r for r in fc if cf("rod1", r) and not cf("h6400", r)]
    print(f"disagreements: h6400-take/rod1-miss = {len(dis)} ; rod1-take/h6400-miss = {len(rev)}")
    print("h6400-take/rod1-miss by phase:")
    for ph in ("opening", "midgame", "late_mid", "pre_endgame", "endgame"):
        n = sum(1 for r in dis if r["phase"] == ph)
        print(f"    {ph:12} {n}")
    print("h6400-take/rod1-miss by opp_class:")
    for c in ("weak", "mid", "strong"):
        print(f"    {c:8} {sum(1 for r in dis if opp_class(r['opp_spec'])==c)}")
    print("  (outcome caveat: final_margin is the ACTUAL mover's, NOT h6400's/rod1's — observational only)")
    print("  top h6400-take/rod1-miss by magnitude (examples):")
    for r in sorted(dis, key=lambda r: -r["labels"]["farm_claim"]["mag"])[:6]:
        d = r["labels"]["farm_claim"]["detail"]
        print(f"    regime={r['regime']} seed={r['seed']} ply={r['ply']} mover={r['mover_spec']} "
              f"phase={r['phase']} k={r['k_remaining']} mag={r['labels']['farm_claim']['mag']} "
              f"adj_n={d['adj_n']} fin_adj={d['finished_adj']} smb={smb(r):+d}")

    print("\n" + "=" * 78)
    print("Q5 — ARE KILLED MOTIFS TRULY DEAD?")
    print("=" * 78)
    for m in ("block", "avoid_feeding"):
        mm = [r for r in recs if m in r["labels"]]
        agree = sum(1 for r in mm if took(r, "random", m) == took(r, "h6400", m))
        print(f"\n{m}: {len(mm)} opps; random & h6400 choose ALIKE on {agree} ({agree/len(mm)*100:.0f}%) "
              f"-> detector does not separate them")
        # example positions where random==h6400 (both same)
        ex = [r for r in mm if took(r, "random", m) == took(r, "h6400", m)][:3]
        for r in ex:
            print(f"    e.g. regime={r['regime']} seed={r['seed']} ply={r['ply']} phase={r['phase']} "
                  f"mag={r['labels'][m]['mag']} random={took(r,'random',m)} h6400={took(r,'h6400',m)} (same)")
    # contest_merge behind-confound
    cm = [r for r in recs if "contest_merge" in r["labels"] and r.get("result_mover") in ("W", "L", "D")]
    ct = [r for r in cm if took(r, "ACTUAL", "contest_merge")]
    cmi = [r for r in cm if took(r, "ACTUAL", "contest_merge") is False]
    print(f"\ncontest_merge behind-confound: mean pre-move margin "
          f"took {sum(smb(r) for r in ct)/max(1,len(ct)):+.2f} vs miss {sum(smb(r) for r in cmi)/max(1,len(cmi)):+.2f}")
    print("  (if took < miss, contesting happens when BEHIND -> the -11pp is a behind-signal, not 'contesting is bad')")


if __name__ == "__main__":
    main()
