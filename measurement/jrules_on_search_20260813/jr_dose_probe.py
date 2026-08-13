"""Indicative dose readout for the J-rules leaf bundle: greedy argmax flip rate
vs jrules_dose on a random-play position corpus. NOT a verdict — a calibration aid
so the DESIGN's dose ladder is not arbitrary (the opencity term's calib readout
pattern, measurement/opencity_term_20260812/make_calib_readout.py).
"""
import dataclasses as dc
import random
import statistics
import sys

import numpy as np

from carcassonne_ai import flat_leaf
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
CHAMP = dc.replace(DEFAULT_CONFIG, meeple_k=2.0, bonus_cap=8.0, opp_bonus_cap=8.0,
                   closure_p={1: 0.5, 2: 0.2, 3: 0.05}, v29_meeple_curve=CURVE125)
DOSES = [0.1, 0.25, 0.5, 1.0]
N_SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 4
EVERY = 9


def corpus():
    out = []
    for s in range(N_SEEDS):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = random.Random(31337 + s)
        ply = 0
        while g.get_game_ended(b, 0) == 0.0 and ply < 140:
            legal = np.flatnonzero(g.get_valid_moves(b))
            if ply >= 12 and ply % EVERY == 0:
                out.append((g, b))
            b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
            ply += 1
    return out


def main():
    pos = corpus()
    flips = {d: 0 for d in DOSES}
    gaps = []
    n = 0
    for g, b in pos:
        legal = [int(i) for i in np.flatnonzero(g.get_valid_moves(b))]
        if len(legal) < 2:
            continue
        mover = int(b.state.current_player)
        base_v, jr_t = [], []
        for a in legal:
            nb, _ = g.get_next_state(b, a)
            st = nb.state
            d = flat_leaf.decompose(st)
            base_v.append(flat_leaf.flat_virtual_score_v2_float(st, mover, CHAMP))
            jr_t.append(flat_leaf.flat_jrules_term(st, mover, d, CHAMP))
        n += 1
        b0 = int(np.argmax(base_v))
        srt = sorted(base_v, reverse=True)
        gaps.append(srt[0] - srt[1])
        for dose in DOSES:
            v = [base_v[i] + dose * jr_t[i] for i in range(len(legal))]
            if int(np.argmax(v)) != b0:
                flips[dose] += 1
    print(f"positions scored: {n}  (mean legal moves {statistics.fmean(len(g.get_valid_moves(b).nonzero()[0]) for g, b in pos):.1f})")
    print(f"mean champion top-2 leaf gap: {statistics.fmean(gaps):.3f}")
    for dose in DOSES:
        print(f"  dose {dose:<5} greedy argmax flip rate {flips[dose]}/{n} = {flips[dose]/max(n,1):.1%}")


if __name__ == "__main__":
    main()
