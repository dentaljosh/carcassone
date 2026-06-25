"""Re-label the existing 1918-position bank with the STRICT high-precision detectors,
joining the already-harvested per-agent choices (no new agent compute). Emits counts,
a per-motif example dump for human inspection (Part B precision-first), and a CSV/jsonl.

Note: the bank is gated on the BROAD motifs, so strict motifs that fire only outside
broad-opportunity positions are undercounted here -- flagged; topped up by fresh
strong-vs-weak generation (gen_strict.py) if a motif is starved.
"""
import argparse
import glob
import json
import os
import pickle
import sys
from collections import defaultdict

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

from carcassonne_ai.game_wrapper import Game

sys.path.insert(0, os.path.dirname(__file__))
import strict_motifs as S
from roster import PANEL

PANEL_SHOW = ["random", "greedy", "h800", "h3200", "h6400", "rod1"]


def load_bank(bank_dir):
    snaps = []
    for p in sorted(glob.glob(os.path.join(bank_dir, "*.pkl"))):
        with open(p, "rb") as f:
            snaps.extend(pickle.load(f))
    return snaps


def load_harvest(path):
    by_idx = {}
    for l in open(path):
        l = l.strip()
        if l:
            r = json.loads(l)
            by_idx[r["idx"]] = r
    return by_idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default="/mnt/c/carc-shared/strategic_ladder/bank")
    ap.add_argument("--harvest", default="measurement/strategic_behavior_ladder/harvest/local.jsonl")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder")
    ap.add_argument("--examples", type=int, default=10)
    args = ap.parse_args()

    bank = load_bank(args.bank)
    harv = load_harvest(args.harvest)
    game = Game(enable_legal_moves_cache=True)

    counts = defaultdict(int)
    by_regime = defaultdict(lambda: defaultdict(int))
    examples = defaultdict(list)
    rows = []

    for idx, s in enumerate(bank):
        h = harv.get(idx)
        if h is None:
            continue
        board = pickle.loads(s["board_pkl"])
        legal = [int(i) for i in __import__("numpy").flatnonzero(game.get_valid_moves(board))]
        labels = S.label_strict(game, board, legal)
        for m, lab in labels.items():
            if not lab.opportunity:
                continue
            counts[m] += 1
            by_regime[m][s["regime"]] += 1
            choices = {ag: h["choices"].get(ag, -1) for ag in PANEL}
            takes = {ag: (choices[ag] in lab.satisfying) for ag in PANEL}
            margin = s["scores"][s["mover"]] - s["scores"][1 - s["mover"]]
            rec = {
                "idx": idx, "motif": m, "regime": s["regime"], "seed": s["seed"], "g": s["g"],
                "ply": s["ply"], "seat": s["mover"], "mover_spec": s["mover_spec"],
                "opp_spec": s["opp_spec"], "phase": s["phase"], "k": s["k_remaining"],
                "scores": s["scores"], "margin_before": margin, "meeples_free": s["meeples_free"],
                "legal_n": len(legal), "magnitude": lab.magnitude, "threat": lab.threat,
                "detail": lab.detail, "sat_n": len(lab.satisfying),
                "choices": choices, "takes": {k: int(v) for k, v in takes.items()},
                "chosen": s["chosen"], "actual_took": int(s["chosen"] in lab.satisfying),
                "final_margin_mover": s.get("final_margin_mover"), "result_mover": s.get("result_mover"),
            }
            rows.append(rec)
            if len(examples[m]) < args.examples:
                examples[m].append(rec)

    print(f"bank positions: {len(bank)}  | strict opportunities:")
    for m in S.MOTIFS:
        reg = " ".join(f"{k}:{v}" for k, v in sorted(by_regime[m].items(), key=lambda x: -x[1])[:6])
        print(f"  {m:32} {counts[m]:4d}   [{reg}]")

    print("\n" + "=" * 90)
    print("EXAMPLES (inspect for plausibility — if silly, the detector sucks)")
    print("=" * 90)
    for m in S.MOTIFS:
        print(f"\n### {m}  ({counts[m]} opps) ###")
        for e in examples[m]:
            tk = " ".join(f"{ag}={'T' if e['takes'][ag] else '.'}" for ag in PANEL_SHOW)
            print(f"  idx={e['idx']} {e['regime']} seed={e['seed']} seat=P{e['seat']} "
                  f"ply={e['ply']} {e['phase']} k={e['k']} margin={e['margin_before']:+d} "
                  f"mag={e['magnitude']:.0f} legal={e['legal_n']} sat={e['sat_n']}")
            print(f"      threat: {e['threat']}")
            print(f"      takes: {tk}   actual({e['mover_spec']})={'T' if e['actual_took'] else '.'} "
                  f"-> result {e['result_mover']} ({e['final_margin_mover']:+d})")

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "strict_labeled_bank.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(rows)} rows -> strict_labeled_bank.jsonl")


if __name__ == "__main__":
    main()
