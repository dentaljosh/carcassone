#!/usr/bin/env python3
"""Deck-paired odometer tally: compare a NEW net's out-of-lineage odometer vs the
iter0 baseline on the SAME decks (same --seed-start → identical decks → paired).

Reads eval_net_vs_heuristic JSONs (fields: seed, net_player, won_by_net, drew).
Prints absolute elo for each side AND the deck-paired (B-A) win-rate delta + z —
the rigorous test for "did the flywheel improve out-of-lineage vs iter0 (+52.5)".

Usage: odo_paired_tally.py <A_dir=iter0 baseline> <B_dir=new net>
"""
import json, glob, math, sys, collections, statistics as st


def load(d):
    by = collections.defaultdict(dict)  # seed -> {net_player(seat): net_score}
    for jf in glob.glob(f"{d}/*seed*.json"):
        if jf.endswith(".partial.json"):
            continue
        try:
            r = json.load(open(jf))
        except Exception:
            continue
        s = r.get("seed")
        seat = r.get("net_player")
        v = 0.5 if r.get("drew") else (1.0 if r.get("won_by_net") else 0.0)
        by[s][seat] = v
    return by


def elo_of(by):
    decks = [sum(v.values()) / len(v) for v in by.values() if v]
    n = sum(len(v) for v in by.values())
    nd = len(decks)
    wr = sum(decks) / nd if nd else 0.0
    if 0 < wr < 1 and nd > 1:
        se = st.pstdev(decks) / math.sqrt(nd)
        elo = 400 * math.log10(wr / (1 - wr))
        sig = (400 / (math.log(10) * wr * (1 - wr))) * se
        z = elo / sig if sig else 0.0
    else:
        elo = sig = z = float("nan")
    return wr, elo, sig, z, n, nd


A_dir, B_dir = sys.argv[1], sys.argv[2]
A, B = load(A_dir), load(B_dir)

print(f"A (baseline) = {A_dir}")
print(f"B (new net)  = {B_dir}")
for label, by in (("A iter0   ", A), ("B new     ", B)):
    wr, elo, sig, z, n, nd = elo_of(by)
    print(f"  {label}: wr={wr:.4f}  elo={elo:+6.1f} ± {sig:4.1f}  (z={z:+.2f})  n={n} decks={nd}")

# deck-paired delta on common decks (both seats present on each side)
dA = {s: sum(A[s].values()) / len(A[s]) for s in A if A[s]}
dB = {s: sum(B[s].values()) / len(B[s]) for s in B if B[s]}
# R5-fix: pair only on seat-count-matched decks — never difference a 1-game strand
# (orphan-stall) against a 2-game mean. Even/odd-out decks drop loudly (no silent cap).
common = sorted(set(dA) & set(dB))
cc = [s for s in common if len(A[s]) == len(B[s])]
_dropped = len(common) - len(cc)
if _dropped:
    print(f"  [warn] dropped {_dropped} seat-imbalanced deck(s) from the paired delta (orphan-stall strand?)")
deltas = [dB[s] - dA[s] for s in cc]
if len(deltas) > 1:
    md = sum(deltas) / len(deltas)
    se = st.pstdev(deltas) / math.sqrt(len(deltas))
    z = md / se if se else 0.0
    wrA = sum(dA[s] for s in cc) / len(cc)
    wrB = sum(dB[s] for s in cc) / len(cc)
    eloA = 400 * math.log10(wrA / (1 - wrA)) if 0 < wrA < 1 else float("nan")
    eloB = 400 * math.log10(wrB / (1 - wrB)) if 0 < wrB < 1 else float("nan")
    verdict = ("B>A SIGNIFICANT (out-of-lineage gain real)" if z >= 2 else
               "B>A weak (within noise)" if z > 0 else
               "NO out-of-lineage gain (B<=A)")
    print(f"PAIRED (B-A) on {len(cc)} common decks:")
    print(f"  Δwr = {md:+.4f} ± {se:.4f}   z = {z:+.2f}")
    print(f"  elo: A={eloA:+.1f}  B={eloB:+.1f}  Δelo≈{eloB-eloA:+.1f}")
    print(f"  → {verdict}")
else:
    print(f"PAIRED: only {len(cc)} common decks — cannot pair")
