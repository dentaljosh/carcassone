"""Luck-floor read-out: tier1 (greedy) steal-rate vs the production fair champion.

Reads the per-game JSONs written by eval_fair_puct.py --opponent greedy and reports:
  * champion W/D/L and winrate, from the CANDIDATE's perspective
  * the LUCK FLOOR = fraction of games tier1 did NOT lose (tier1 wins + draws)
  * Wilson 95% CI on that floor
  * the deck-paired margin (seat-balanced, the sharper statistic)
  * per-box game attribution (work-stealing evidence)
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

D = Path(sys.argv[1] if len(sys.argv) > 1
         else "/mnt/c/carc-shared/luckfloor_champ_k4x688_vs_greedy_b54e9")


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


games = []
for f in sorted(D.glob("*.json")):
    if f.name == "manifest.json" or f.name.startswith("summary"):
        continue
    try:
        games.append(json.loads(f.read_text()))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] unreadable {f.name}: {e}", file=sys.stderr)

n = len(games)
if n == 0:
    sys.exit("no games found in " + str(D))

# won_by_champ / drew are the authoritative outcome flags (diff is candidate - opponent).
W = sum(1 for g in games if g["won_by_champ"])
Dr = sum(1 for g in games if g["drew"])
L = n - W - Dr

steals = L + Dr                      # games tier1 did NOT lose = the luck floor
lo, hi = wilson(steals, n)
wl, wh = wilson(W + 0.5 * Dr, n)     # champion winrate CI (draws half-weighted)

wr = (W + 0.5 * Dr) / n
elo = -400 * math.log10(1 / wr - 1) if 0 < wr < 1 else float("inf")
sig = 695 * math.sqrt(0.25 / n)

print(f"games            : {n}")
print(f"champion W/D/L   : {W}/{Dr}/{L}")
print(f"champion winrate : {wr:.4f}   elo {elo:+.1f} +/- {sig:.1f} (1sigma, unpaired)")
print()
print(f"*** LUCK FLOOR  : tier1 took {steals}/{n} = {steals/n:.4f} "
      f"({L} wins + {Dr} draws)")
print(f"    Wilson 95%CI: [{lo:.4f}, {hi:.4f}]")
print(f"    champion wr Wilson 95%CI: [{wl:.4f}, {wh:.4f}]")
print()

# Deck-paired, seat-balanced margin: average the two seats of each deck.
by_deck = {}
for g in games:
    by_deck.setdefault(g["seed"], []).append(g)
pairs = [v for v in by_deck.values() if len(v) == 2]
if pairs:
    ds = [(p[0]["diff"] + p[1]["diff"]) / 2 for p in pairs]
    m = sum(ds) / len(ds)
    sd = math.sqrt(sum((x - m) ** 2 for x in ds) / max(1, len(ds) - 1))
    se = sd / math.sqrt(len(ds))
    print(f"PAIRED           : {len(pairs)} complete decks   "
          f"mean seat-balanced margin {m:+.2f} pts/deck   z {m/se:+.2f}")
print(f"incomplete decks : {sum(1 for v in by_deck.values() if len(v) != 2)}")

# ms/move + timeouts
cm = sum(g.get("champ_prefix_secs", 0) for g in games)
cmv = sum(g.get("champ_prefix_moves", 0) for g in games)
rm = sum(g.get("rung_secs", 0) for g in games)
rmv = sum(g.get("rung_moves", 0) for g in games)
if cmv and rmv:
    print(f"prefix ms/move   : champion {cm/cmv*1e3:.0f}  tier1 {rm/rmv*1e3:.0f} "
          f"(ratio {(cm/cmv)/(rm/rmv):.1f}x)")
print(f"solver timeouts  : {sum(g.get('champ_timeouts', 0) for g in games)}")

# Per-box attribution: the game JSONs carry no host, so read it off the .claim locks
# (content "host:pid:timestamp"), which persist after the game completes.
hosts = Counter()
for c in D.glob("*.claim"):
    try:
        hosts[c.read_text().split(":")[0]] += 1
    except Exception:  # noqa: BLE001
        hosts["?"] += 1
if hosts:
    print(f"per-box claims   : {dict(hosts)}  (work-stealing evidence)")
else:
    print("per-box claims   : none on disk (claims cleaned post-run — the b54e9 cell's "
          "attribution was local 92 / laptop 108, recorded in the results.csv note)")
