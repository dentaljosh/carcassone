#!/usr/bin/env python3
"""k_dets bracket reader: per-cell absolute (vs frozen h800) + the deck-matched
delta-vs-k8 (double-CRN, the bracket verdict). Works on partial data (mid-run).

Usage: python kdets_delta.py [share_root]   # default /mnt/c/carc-shared
"""
import json, os, sys, glob, math

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/c/carc-shared"
MODE = sys.argv[2] if len(sys.argv) > 2 else "screen"   # "screen" (n=150) | "confirm" (n=400)
if MODE == "confirm":
    SUFFIX = "confirm_b17001"; CELLS = [(8, 344), (4, 688), (2, 1376)]   # k8 anchor + k4 winner + k2
else:
    SUFFIX = "b17e9"; CELLS = [(8, 344), (4, 688), (16, 172), (32, 86)]  # k8 first = anchor
def cell_dir(k, s):
    return os.path.join(ROOT, f"kdets_k{k}x{s}_tot2752_curve125champ_vs_h800_k2_{SUFFIX}")

def load_games(d):
    """seed -> {seat: (diff, won, drew)}; only fully-paired seeds kept for margins."""
    by_seed = {}
    for g in glob.glob(os.path.join(d, "seed*_a*.json")):
        try:
            j = json.load(open(g))
        except Exception:
            continue
        by_seed.setdefault(int(j["seed"]), {})[int(j["a_seat"])] = (
            float(j["diff"]), bool(j["won_by_champ"]), bool(j["drew"]))
    return by_seed

def cell_stats(by_seed):
    """Return per-deck seat-balanced margins (paired decks only) + game-level W/D/L."""
    margins = {}   # seed -> (diff_a0 + diff_a1)/2
    W = D = L = 0
    for seed, seats in by_seed.items():
        for _seat, (diff, won, drew) in seats.items():
            if drew: D += 1
            elif won: W += 1
            else: L += 1
        if 0 in seats and 1 in seats:
            margins[seed] = (seats[0][0] + seats[1][0]) / 2.0
    return margins, W, D, L

def elo_from_wr(wr):
    wr = min(max(wr, 1e-6), 1 - 1e-6)
    return -400.0 * math.log10(1.0 / wr - 1.0)

def mean_se_z(xs):
    n = len(xs)
    if n < 2: return (float("nan"), float("nan"), float("nan"), n)
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return (m, se, (m / se if se > 0 else float("nan")), n)

# --- load all cells ---
data = {}
for k, s in CELLS:
    bs = load_games(cell_dir(k, s))
    data[k] = cell_stats(bs)

print("=" * 92)
print("k_dets BRACKET @ fixed total 2752 — curve125 champion vs FROZEN curve100 h800 (config B)")
print("  band 17e9, K=2, CRN.  k8 anchor sanity ~+118.7 vs h800 (c5_confirm).  RUN k8 FIRST.")
print("=" * 92)
print(f"  {'cell':<10} {'decks':>6} {'W/D/L':>12} {'wr':>6} {'margin pts/deck':>16} {'elo':>8}")
for k, s in CELLS:
    margins, W, Dr, L = data[k]
    n_games = W + Dr + L
    if n_games == 0:
        print(f"  k{k}x{s:<6} {'--':>6}   (not started)"); continue
    wr = (W + 0.5 * Dr) / n_games
    m, se, _z, nd = mean_se_z(list(margins.values()))
    tag = "  <-anchor" if k == 8 else ""
    mstr = f"{m:+.2f}+-{se:.2f}" if nd >= 2 else "n<2"
    print(f"  k{k}x{s:<6} {nd:>6} {f'{W}/{Dr}/{L}':>12} {wr:>6.3f} {mstr:>16} {elo_from_wr(wr):>+8.1f}{tag}")

# --- the bracket verdict: deck-matched delta vs k8 (double-CRN) ---
print()
print("=" * 92)
print("DELTA vs k8 (deck-matched, double-CRN) — the bracket verdict. >0 = beats k8.")
print("  a cell must clear ~+20 elo-equiv / margin-z>=~1.5 at n=150 to advance to an n=400 confirm.")
print("=" * 92)
k8_margins = data[8][0]
print(f"  {'cell':<10} {'shared decks':>12} {'delta pts/deck':>16} {'z':>7}")
for k, s in CELLS:
    if k == 8: continue
    cm = data[k][0]
    shared = sorted(set(cm) & set(k8_margins))
    if len(shared) < 2:
        print(f"  k{k}x{s:<6} {len(shared):>12}   (need >=2 shared decks)"); continue
    deltas = [cm[sd] - k8_margins[sd] for sd in shared]
    m, se, z, nd = mean_se_z(deltas)
    flag = "  ** beats k8 **" if (z == z and z >= 1.5) else ""
    print(f"  k{k}x{s:<6} {nd:>12} {f'{m:+.2f}+-{se:.2f}':>16} {z:>+7.2f}{flag}")
print()
print("Note: margin pts/deck delta is the tightest read (cancels deck variance twice). Report point+-se,")
print("not just z (magnitude vs noise). Screen resolves ~>=+30-elo cell gaps at ~1sigma @ n=150.")
