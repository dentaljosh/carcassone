#!/usr/bin/env python3
"""Deck-matched k16-vs-k8 width contrast at fixed 22016 budget (both cells band 48e9, vs deploy champion).
Both cells are internally deck-paired vs the SAME deploy champion, so per matched (seed, a_seat) game the
per-game `diff` is candidate-minus-opponent. The diff-of-diffs (diff_k16 - diff_k8) isolates k16 vs k8 on the
same decks (the deploy opponent is the common reference). Game-clustered by deck seed (2 seats/deck).

Usage: python3 curve_k16_vs_k8_paired.py <k8_dir> <k16_dir>
"""
import json, glob, sys, math, os

def load(d):
    out = {}
    for f in glob.glob(os.path.join(d, "seed*_a[01].json")):
        try:
            r = json.load(open(f))
            out[(r["seed"], r["a_seat"])] = r["diff"]   # diff = candidate - opponent
        except Exception:
            pass
    return out

def main():
    k8_dir, k16_dir = sys.argv[1], sys.argv[2]
    k8, k16 = load(k8_dir), load(k16_dir)
    # each cell's own vs-deploy sanity
    for name, c in (("k8x2752", k8), ("k16x1376", k16)):
        v = list(c.values())
        print(f"{name}: n={len(v)} mean vs-deploy diff = {sum(v)/len(v):+.3f}")
    # matched keys
    keys = sorted(set(k8) & set(k16))
    print(f"\nmatched (seed,seat) games in BOTH cells: {len(keys)}")
    # per-game diff-of-diffs, clustered by seed (2 seats/deck)
    by_seed = {}
    for (seed, seat) in keys:
        by_seed.setdefault(seed, []).append(k16[(seed, seat)] - k8[(seed, seat)])
    # per-deck mean (average the 2 seats), then cluster stats over decks
    deck_means = [sum(v)/len(v) for v in by_seed.values()]
    n = len(deck_means)
    mean = sum(deck_means)/n
    var = sum((x-mean)**2 for x in deck_means)/(n-1)
    se = math.sqrt(var/n)
    z = mean/se if se > 0 else float("nan")
    print(f"\n=== DECK-MATCHED k16 - k8 (pts/deck, {n} decks) ===")
    print(f"  mean {mean:+.3f}  se {se:.3f}  z {z:+.2f}")
    print(f"  READ: z>~+2 and mean>~+2 -> k16 >> k8 => k8x2752 was width-starved, gate NOT flat.")
    print(f"        mean ~0 -> k16 ~= k8 (both ~flat vs deploy) => flat CONFIRMED under corrected allocation -> pivot.")

if __name__ == "__main__":
    main()
