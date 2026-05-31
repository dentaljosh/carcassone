"""Authoritative Step 9 go/no-go tally.

Under --shared-claim, each box's stdout only sees the games IT played, so no
single per-box log has the full record. This reads EVERY result JSON in the eval
dir and computes the true W/L/D + elo from the NEW side's perspective.

NEW = pure NN-value leaf (value_blend=1.0); OLD = pure v2.7 heuristic leaf
(value_blend=0.0); same policy net both sides. GO if NEW beats OLD by > +15 elo.

Result-JSON schema (from eval_iter_head_to_head):
  seed, new_player(0/1), sims, score_p0, score_p1, diff, won_by_new, drew, moves

Usage:
  python scripts/tally_step9.py [eval_dir]
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from carcassonne_ai.elo import elo_delta_from_winrate  # noqa: E402

DEFAULT_DIR = "/mnt/c/carc-shared/step9_iter11/eval/iter_11_vs_11"
GO_THRESHOLD = 15.0


def main(argv: list[str]) -> int:
    eval_dir = argv[1] if len(argv) > 1 else DEFAULT_DIR
    files = [f for f in glob.glob(os.path.join(eval_dir, "*.json"))
             if not f.endswith("elo_log.json")]
    if not files:
        print(f"NO RESULT FILES in {eval_dir}")
        return 1

    wins = draws = losses = 0
    bad = 0
    margin_sum = 0.0
    p0 = p1 = 0  # NEW-side player-slot balance (sanity: should be ~half/half)
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            bad += 1
            continue
        if d.get("drew"):
            draws += 1
        elif d.get("won_by_new"):
            wins += 1
        else:
            losses += 1
        # NEW-side score margin: diff is already (new - old) signed per the
        # writer; fall back to score_p{new_player} if absent.
        if "diff" in d:
            margin_sum += d["diff"]
        else:
            npl = d.get("new_player", 0)
            mine = d["score_p0"] if npl == 0 else d["score_p1"]
            opp = d["score_p1"] if npl == 0 else d["score_p0"]
            margin_sum += (mine - opp)
        if d.get("new_player") == 0:
            p0 += 1
        else:
            p1 += 1

    n = wins + draws + losses
    elo = elo_delta_from_winrate(wins, losses, draws)
    wr = (wins + 0.5 * draws) / n if n else 0.0
    # binomial 1-sigma on winrate -> elo sigma via local slope (400/ln10 / (p(1-p)n))
    if 0 < wr < 1 and n > 0:
        wr_sigma = math.sqrt(wr * (1 - wr) / n)
        elo_sigma = (400.0 / math.log(10)) * wr_sigma / (wr * (1 - wr))
    else:
        elo_sigma = float("nan")
    avg_margin = margin_sum / n if n else 0.0

    print(f"=== STEP 9 TALLY  ({eval_dir}) ===")
    print(f"games:        {n}   (corrupt/skipped: {bad})")
    print(f"NEW-side slot balance:  p0={p0}  p1={p1}  (want ~50/50)")
    print(f"record (NEW): {wins}W / {draws}D / {losses}L   winrate {wr:.3f}")
    print(f"avg score margin (NEW-OLD): {avg_margin:+.2f}")
    print(f"ELO (NEW vs OLD): {elo:+.1f}  (+/- {elo_sigma:.1f} 1sigma)")
    if elo_sigma == elo_sigma and elo_sigma > 0:  # not nan
        print(f"significance: {elo / elo_sigma:.1f} sigma from 0")
    print()
    if elo > GO_THRESHOLD:
        print(f"VERDICT: *** GO ***  (NN-value leaf beats v2.7 by {elo:+.1f} > +{GO_THRESHOLD:.0f} elo)")
    elif elo <= 0:
        print(f"VERDICT: NO-GO  (NN-value leaf does not beat v2.7: {elo:+.1f} elo)")
    else:
        print(f"VERDICT: WEAK / inconclusive  ({elo:+.1f} elo, below +{GO_THRESHOLD:.0f} GO bar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
