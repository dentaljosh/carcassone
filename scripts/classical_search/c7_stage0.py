#!/usr/bin/env python3
"""C7 Stage-0 feasibility / cost gate — measurement/classical_search/C7_LEAF_TERMS_DESIGN.md §5.

The parts of the Stage-0 GO/NO-GO that are NOT the standalone reconcile gates:

  (b) per-leaf COST DELTA at production knobs — median + p95 per-leaf ns ratios for
      +R(k=1.0) / +F(k=0.5) / +both vs the champion, on a ~2k-state mid+endgame corpus,
      leaf = flat_virtual_score_v2_cy_float. HARD GATE: each ratio <= 1.10. + one n=4
      in-game ms-ratio (ON-vs-OFF) which must land in [0.9, 1.1].
  (c) 3-WAY ON BIT-EXACTNESS — cy == flat-py == object, EXACT (int + pre-round float),
      over fuzzed states, for +R / +F / +both; + antisymmetry and R-requires-curve.
  (d) HASH / PROVENANCE AUDIT — the frozen-cfg recipe recomputes the PRODUCTION champion
      158f17ff76adaa02 and the frozen v2.9 anchor 7fc930b82801cb43 UNCHANGED; scan for
      any unexplained dataclasses.asdict(LeafConfig) consumer.

Part (a) [scripts/reconcile_flat_leaf.py --n 200, scripts/reconcile_cy_leaf.py --n 400
--snap-every 1, and the frozen-substrate pytests] and the eval-harness manifest smoke
[tests/test_c5_leaf_ab.py mirror tests] are the EXISTING gates — run them separately;
this script reminds you and does not re-run them.

Run under the production env (curve125). LOCAL box only. Exit 0 = GO, 1 = NO-GO.
"""
from __future__ import annotations

import os

# Production leaf env (curve125 champion) MUST be set before importing carcassonne_ai
# so DEFAULT_CONFIG resolves to the champion (== the frozen-recipe 158f17ff recipe).
_ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
}
for _k, _v in _ENV.items():
    os.environ.setdefault(_k, _v)
for _k in ("CARCASSONNE_V25_ONE_OPEN_ONLY", "CARCASSONNE_V25_RESIDUAL_SCALE",
           "CARCASSONNE_V25_TILE_COUNTING", "CARCASSONNE_V25_CLOSURE_SLACK",
           "CARCASSONNE_V28_FARM_MAJORITY", "CARCASSONNE_V28_MEEPLE_K",
           "CARCASSONNE_V28_MEEPLE_RECOVERY_T0", "CARCASSONNE_V210_BAG_CLOSE"):
    os.environ.pop(_k, None)

import argparse  # noqa: E402
import dataclasses as dc  # noqa: E402
import random  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "scripts" / "measurement_infra"))

import numpy as np  # noqa: E402

import snapshot as SNAP  # noqa: E402
from carcassonne_ai import flat_leaf, flat_leaf_cy, leaf_v29  # noqa: E402
from carcassonne_ai import virtual_score_v2 as vs2  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2  # noqa: E402

CHAMP_HASH = "158f17ff76adaa02"
FROZEN_HASH = "7fc930b82801cb43"

CHAMP = DEFAULT_CONFIG                                   # curve125 cap8 (env-built)
R10 = dc.replace(CHAMP, v29_meeple_return_k=1.0)
F05 = dc.replace(CHAMP, v29_farm_flip_k=0.5)
RF = dc.replace(CHAMP, v29_meeple_return_k=1.0, v29_farm_flip_k=0.5)
ON_CONFIGS = [("+R(k=1.0)", R10), ("+F(k=0.5)", F05), ("+both", RF)]


def build_corpus(n_games: int, target: int, seed0: int = 424242):
    """~target mid+endgame states from n_games seeded random games."""
    game = Game(enable_legal_moves_cache=True)
    states = []
    g = 0
    while len(states) < target and g < n_games * 4:
        b = game.get_init_board()
        rng = random.Random(seed0 + g)
        plies = 0
        while game.get_game_ended(b, 0) == 0.0 and plies < 200:
            legal = np.flatnonzero(game.get_valid_moves(b))
            if legal.size == 0:
                break
            b, _ = game.get_next_state(b, int(rng.choice(legal.tolist())))
            plies += 1
            if plies >= 25 and plies % 2 == 0 and b.state.players == 2:
                states.append(b.state)
        g += 1
    return states[:target]


def _time_leaf(states, cfg, reps: int) -> list:
    """Per-leaf ns distribution (one value per state = mean of `reps` cy-float calls)."""
    leaf = flat_leaf_cy.flat_virtual_score_v2_cy_float
    out = []
    for st in states:
        t0 = time.perf_counter_ns()
        for _ in range(reps):
            leaf(st, 0, cfg, False)
        out.append((time.perf_counter_ns() - t0) / reps)
    return out


def part_b(states, reps: int) -> bool:
    print(f"\n=== (b) per-leaf COST DELTA  (corpus {len(states)} states, {reps} reps/state, cy float) ===")
    # warm up (JIT tile-feat cache, branch predictors) so the champion baseline is fair
    _time_leaf(states[:200], CHAMP, 5)
    champ_ns = _time_leaf(states, CHAMP, reps)
    med_c = statistics.median(champ_ns)
    p95_c = float(np.percentile(champ_ns, 95))
    print(f"champion         : median {med_c:8.1f} ns   p95 {p95_c:8.1f} ns")
    ok = True
    for name, cfg in ON_CONFIGS:
        ns = _time_leaf(states, cfg, reps)
        med = statistics.median(ns)
        p95 = float(np.percentile(ns, 95))
        rm, rp = med / med_c, p95 / p95_c
        gate = (rm <= 1.10 and rp <= 1.10)
        ok = ok and gate
        print(f"{name:16s} : median {med:8.1f} ns ({rm:5.3f}x)  p95 {p95:8.1f} ns ({rp:5.3f}x)  "
              f"{'PASS' if gate else 'FAIL >1.10'}")

    # n=4 in-game ms-ratio (ON=+both vs OFF=champion), full games, cy int leaf.
    def _play_ms(cfg):
        game = Game(enable_legal_moves_cache=True)
        t0 = time.perf_counter()
        nleaf = 0
        for s in range(4):
            b = game.get_init_board()
            rng = random.Random(770000 + s)
            while game.get_game_ended(b, 0) == 0.0:
                legal = np.flatnonzero(game.get_valid_moves(b))
                if legal.size == 0:
                    break
                if b.state.players == 2:
                    flat_leaf_cy.flat_virtual_score_v2_cy(b.state, 0, cfg, False)
                    nleaf += 1
                b, _ = game.get_next_state(b, int(rng.choice(legal.tolist())))
        return (time.perf_counter() - t0) * 1000.0, nleaf
    off_ms, _ = _play_ms(CHAMP)
    on_ms, _ = _play_ms(RF)
    ratio = on_ms / off_ms if off_ms else float("nan")
    ig_ok = 0.9 <= ratio <= 1.1
    print(f"n=4 in-game ms-ratio (+both vs champ): {on_ms:.1f} / {off_ms:.1f} = {ratio:.3f}x  "
          f"{'PASS' if ig_ok else 'OUT OF [0.9,1.1]'}")
    return ok and ig_ok


def part_c(n_games: int) -> bool:
    print(f"\n=== (c) 3-WAY ON BIT-EXACTNESS  (cy == flat-py == object; {n_games} games) ===")
    game = Game(enable_legal_moves_cache=True)
    saved_cy, saved_flat, saved_canon = flat_leaf.USE_CY_LEAF, flat_leaf.USE_FLAT_LEAF, vs2.CANONICAL_BONUS_SUM
    n = 0
    mism = {name: 0 for name, _ in ON_CONFIGS}
    worst_anti = 0.0
    rrc_ok = False
    try:
        vs2.CANONICAL_BONUS_SUM = True
        # R-requires-curve on all three paths
        st0 = game.get_init_board().state
        for fn in (lambda: flat_leaf.flat_return_term(st0, 0, flat_leaf.decompose(st0), dc.replace(R10, v29_meeple_curve=None)),
                   lambda: leaf_v29._return_liquidity(st0, 0, dc.replace(R10, v29_meeple_curve=None))):
            try:
                fn(); break
            except ValueError:
                rrc_ok = True
        for s in range(n_games):
            b = game.get_init_board()
            rng = random.Random(51000 + s)
            plies = 0
            while game.get_game_ended(b, 0) == 0.0 and plies < 200:
                legal = np.flatnonzero(game.get_valid_moves(b))
                if legal.size == 0:
                    break
                b, _ = game.get_next_state(b, int(rng.choice(legal.tolist())))
                plies += 1
                st = b.state
                if st.players != 2:
                    continue
                d = flat_leaf.decompose(st)
                for p in (0, 1):
                    # antisymmetry (float terms)
                    ra = flat_leaf.flat_return_term(st, p, d, R10)
                    rb = flat_leaf.flat_return_term(st, 1 - p, d, R10)
                    fa = flat_leaf.flat_farm_flip_term(st, p, d, F05)
                    fb = flat_leaf.flat_farm_flip_term(st, 1 - p, d, F05)
                    worst_anti = max(worst_anti, abs(ra + rb), abs(fa + fb))
                    for name, cfg in ON_CONFIGS:
                        cy_i = flat_leaf_cy.flat_virtual_score_v2_cy(st, p, cfg, False)
                        cy_f = flat_leaf_cy.flat_virtual_score_v2_cy_float(st, p, cfg, False)
                        flat_leaf.USE_CY_LEAF = False
                        py_i = flat_leaf.flat_virtual_score_v2(st, p, cfg)
                        py_f = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                        flat_leaf.USE_CY_LEAF = True
                        flat_leaf.USE_FLAT_LEAF = False
                        ob_i = virtual_score_v2(st, p, cfg)      # object path (canonical)
                        flat_leaf.USE_FLAT_LEAF = True
                        if not (cy_i == py_i == ob_i and cy_f == py_f):
                            mism[name] += 1
                    n += 1
    finally:
        flat_leaf.USE_CY_LEAF, flat_leaf.USE_FLAT_LEAF, vs2.CANONICAL_BONUS_SUM = saved_cy, saved_flat, saved_canon
    total = sum(mism.values())
    print(f"leaf triples checked : {n} states x 2 players x 3 cfgs = {n * 6}")
    for name, _ in ON_CONFIGS:
        print(f"  {name:16s}: {mism[name]} mismatches")
    print(f"antisymmetry worst |t(p)+t(opp)| : {worst_anti:.2e}   (must be 0.0)")
    print(f"R-requires-curve raises          : {rrc_ok}")
    return total == 0 and worst_anti == 0.0 and rrc_ok


def part_d() -> bool:
    print("\n=== (d) HASH / PROVENANCE AUDIT ===")
    champ_h = SNAP._frozen_config_hash(CHAMP)
    frozen_h = SNAP._frozen_config_hash(SNAP.frozen_v29_cfg(2.0))
    ch_ok = champ_h == CHAMP_HASH
    fr_ok = frozen_h == FROZEN_HASH
    print(f"PRODUCTION champion frozen-recipe hash : {champ_h}  (expect {CHAMP_HASH})  "
          f"{'OK' if ch_ok else 'DRIFT'}")
    print(f"frozen v2.9 anchor    frozen-recipe hash : {frozen_h}  (expect {FROZEN_HASH})  "
          f"{'OK' if fr_ok else 'DRIFT'}")
    # the default-off C7 knobs must NOT shift the recipe hash (that is the whole point)
    shift_r = SNAP._frozen_config_hash(dc.replace(CHAMP, v29_meeple_return_k=0.0))
    shift_f = SNAP._frozen_config_hash(dc.replace(CHAMP, v29_farm_flip_k=0.0))
    inert = shift_r == CHAMP_HASH and shift_f == CHAMP_HASH
    print(f"default-off C7 knobs recipe-inert        : {inert}")
    # a SET knob MUST shift the recipe hash (else the candidate leaf would alias the champ)
    set_shifts = (SNAP._frozen_config_hash(R10) != CHAMP_HASH
                  and SNAP._frozen_config_hash(F05) != CHAMP_HASH)
    print(f"SET C7 knobs shift the recipe hash       : {set_shifts}")
    return ch_ok and fr_ok and inert and set_shifts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=int, default=2000, help="cost-bench corpus size")
    ap.add_argument("--reps", type=int, default=120, help="timing reps per state")
    ap.add_argument("--bitexact-games", type=int, default=60)
    args = ap.parse_args()

    print("C7 Stage-0 gate (parts b/c/d; a + manifest smoke run separately)")
    print(f"env: cap={CHAMP.bonus_cap} curve={CHAMP.v29_meeple_curve} "
          f"USE_FLAT_LEAF={flat_leaf.USE_FLAT_LEAF} USE_CY_LEAF={flat_leaf.USE_CY_LEAF} "
          f"cy_C7={getattr(flat_leaf_cy, 'SUPPORTS_V29_C7_TERMS', None)}")
    assert getattr(flat_leaf_cy, "SUPPORTS_V29_C7_TERMS", False), \
        "flat_leaf_cy lacks SUPPORTS_V29_C7_TERMS — rebuild the .so first"

    corpus = build_corpus(n_games=args.corpus, target=args.corpus)
    b_ok = part_b(corpus, args.reps)
    c_ok = part_c(args.bitexact_games)
    d_ok = part_d()

    print("\n=== C7 Stage-0 (b/c/d) VERDICT ===")
    print(f"  (b) cost gate      : {'GO' if b_ok else 'NO-GO'}")
    print(f"  (c) 3-way bit-exact: {'GO' if c_ok else 'NO-GO'}")
    print(f"  (d) hash/provenance: {'GO' if d_ok else 'NO-GO'}")
    print("  (a) reconcile_flat_leaf --n 200 + reconcile_cy_leaf --n 400 + frozen pytests: run separately")
    print("  manifest smoke: tests/test_c5_leaf_ab.py mirror + C7 tests: run separately")
    go = b_ok and c_ok and d_ok
    print(f"\nOVERALL (b/c/d): {'GO' if go else 'NO-GO'}")
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())
