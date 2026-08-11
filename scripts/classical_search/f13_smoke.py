#!/usr/bin/env python3
"""F13 pre-flight smokes — the two the prereg names, at PRODUCTION knobs.

Prereg: measurement/exact_k_ladder_20260803/PREREG_DRAFT.md
  * "Identity smoke before the ladder: K=4-vs-K=4, 20 games, must be 100% identical
    actions."  -> `--mode identity`
  * "Bench-then-commit rider: run 10 games of the K=6 arm first and check the realized
    cap-hit rate before launching the full rung."  -> `--mode k6`

WHAT `identity` ACTUALLY ASSERTS (the reading, stated so it can be argued with).
Both arms of a K=4-vs-K=4 cell are the same configuration at different RNG seeds, so
"identical actions" cannot mean "the two arms agree move for move". It means the F13
MACHINERY IS A NO-OP AT K<=4: this mode plays each game TWICE from the same deck seed —
once with the F13 tail (`--exact-solver`, the wall-cap map, the fallback ladder) and once
with the pre-F13 inline Python tail — and requires the two full action sequences to be
IDENTICAL, ply for ply, both seats. That is the property the ladder rests on: the
incumbent arm must be the incumbent, byte for byte, or every rung is measured against a
moved goalpost. It also incidentally re-checks rust-vs-python exact-solver agreement on
every solved endgame position it touches (a divergence there SHOULD fail this smoke).

Exits NONZERO on any divergence. Prints a per-game diff site (ply, both actions).

`k6` plays the real candidate arm (K=6 vs the K=4 incumbent) under the pre-registered
caps and reports the realized cap-hit rate, per-game wall, and peak RSS — the three
numbers the "bench, then extrapolate, then commit" rider needs.

NEITHER MODE writes results.csv, a manifest, a band claim, or anything under
measurement/. Smokes are throwaway by construction.
"""

from __future__ import annotations

import argparse
import os
import random
import resource
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from carcassonne_ai import rules_profile as _rules_profile  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

import exact_tail as _et  # noqa: E402
import eval_puct_priors as H  # noqa: E402


def _peak_rss_mb() -> float:
    """ru_maxrss is KiB on Linux; include reaped children (the capped-solve forks)."""
    return (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            + resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss) / 1024.0


def _prefix(cfg, sims, seed, backend):
    if backend == "rust":
        return H._rust_clairvoyant(cfg, sims, seed)
    return HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                               simulations=int(sims), seed=seed)


def play(seed: int, a_seat: int, args, *, cand_k: int, opp_k: int,
         solver: str, caps: dict, k_floor: int):
    """One full game. Returns (actions, cand_tail, champ_tail, wall_secs)."""
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    cand_cfg = HeuristicPriorConfig(
        c_puct=args.c_puct, tau_p=args.tau_p, leaf_quantize=args.leaf_quantize,
        final_select=args.final_select, value_norm=15.0, leaf_cfg=DEFAULT_CONFIG)
    opp_cfg = H._champ_puct_cfg(
        {"c_puct": args.c_puct, "tau_p": args.tau_p,
         "leaf_quantize": args.leaf_quantize}, reuse=False, pin_champion=False)

    cand_prefix = _prefix(cand_cfg, args.cand_sims, seed, args.backend)
    champ_prefix = _prefix(opp_cfg, args.champ_sims, seed + 1, args.backend)
    tail_kw = dict(caps=caps, solver=solver, k_floor=k_floor)
    cand = H._ExactHandoff(cand_prefix, Game(enable_legal_moves_cache=True), cand_k,
                           mirror_agent=cand_prefix, **tail_kw)
    champ = H._ExactHandoff(champ_prefix, Game(enable_legal_moves_cache=True), opp_k,
                            mirror_agent=champ_prefix, **tail_kw)

    mirrors = [p for p in (cand_prefix, champ_prefix) if hasattr(p, "advance")]
    for m in mirrors:
        m.start_game(board)

    actions: list[int] = []
    t0 = time.perf_counter()
    while game.get_game_ended(board, 0) == 0.0:
        agent = cand if board.state.current_player == a_seat else champ
        act = int(agent.move(board))
        board, _ = game.get_next_state(board, act)
        for m in mirrors:
            m.advance(act)
        actions.append(act)
    return actions, cand.tail, champ.tail, time.perf_counter() - t0


# --------------------------------------------------------------------------- #
def mode_identity(args) -> int:
    caps = _et.parse_wall_caps(args.exact_wall_caps)
    n_decks = args.n // 2
    bad = 0
    print(f"[f13-identity] {args.n} games ({n_decks} decks x 2 seats) at K=4 vs K=4 — "
          f"F13 tail (solver={args.exact_solver}, caps={_et.fmt_wall_caps(caps) or 'none'}) "
          f"vs the pre-F13 inline python tail. Any divergence FAILS.", flush=True)
    for i in range(n_decks):
        seed = args.seed_start + i
        for a_seat in (0, 1):
            a, ta, _, wa = play(seed, a_seat, args, cand_k=4, opp_k=4,
                                solver=args.exact_solver, caps=caps,
                                k_floor=args.exact_k_floor)
            b, _, _, wb = play(seed, a_seat, args, cand_k=4, opp_k=4,
                               solver="python", caps={}, k_floor=0)
            if a == b:
                print(f"  seed={seed} a_seat={a_seat} OK  {len(a)} plies identical "
                      f"({wa:.1f}s / {wb:.1f}s), latch solves={ta.latch_solves}", flush=True)
                continue
            bad += 1
            ply = next((j for j in range(min(len(a), len(b))) if a[j] != b[j]),
                       min(len(a), len(b)))
            print(f"  seed={seed} a_seat={a_seat} DIVERGED at ply {ply}: "
                  f"f13={a[ply] if ply < len(a) else 'END'} vs "
                  f"legacy={b[ply] if ply < len(b) else 'END'} "
                  f"(len {len(a)} vs {len(b)})", flush=True)
    if bad:
        print(f"[f13-identity] FAIL — {bad}/{args.n} games diverged. The F13 tail is NOT "
              f"a no-op at K<=4; do NOT launch the ladder.", flush=True)
        return 1
    print(f"[f13-identity] PASS — {args.n}/{args.n} games 100% action-identical.", flush=True)
    return 0


def mode_k6(args) -> int:
    caps = _et.parse_wall_caps(args.exact_wall_caps or "default")
    n_decks = args.n // 2
    tot_latch = tot_capped = tot_hits = tot_fb = 0
    walls: list[float] = []
    print(f"[f13-k6] {args.n} games ({n_decks} decks x 2 seats) — candidate K={args.cand_k} "
          f"vs incumbent K={args.opp_k}, caps={_et.fmt_wall_caps(caps)}, "
          f"floor={args.exact_k_floor}, solver={args.exact_solver}. "
          f"BENCH ONLY — no row, no band, no manifest.", flush=True)
    for i in range(n_decks):
        seed = args.seed_start + i
        for a_seat in (0, 1):
            _, ta, tc, w = play(seed, a_seat, args, cand_k=args.cand_k,
                                opp_k=args.opp_k, solver=args.exact_solver,
                                caps=caps, k_floor=args.exact_k_floor)
            walls.append(w)
            tot_latch += ta.latch_solves
            tot_capped += ta.capped_attempts
            tot_hits += ta.cap_hits
            tot_fb += ta.fallback_depth
            print(f"  seed={seed} a_seat={a_seat} {w:7.1f}s  cand latch={ta.latch_solves} "
                  f"capped={ta.capped_attempts} hits={ta.cap_hits} "
                  f"by_k={ta.cap_hits_by_k} fallback={ta.fallback_depth} "
                  f"eff_k={ta.eff_k} | opp hits={tc.cap_hits}  rss={_peak_rss_mb():.0f}MB",
                  flush=True)
    rate = _et.censored_rate(tot_hits, tot_latch)
    rate_c = _et.censored_rate_capped(tot_hits, tot_capped)
    walls.sort()
    mean_w = sum(walls) / max(1, len(walls))
    print(f"\n[f13-k6] REALIZED over {len(walls)} games:")
    print(f"  latch solves {tot_latch} | capped attempts {tot_capped} | cap hits {tot_hits} "
          f"| fallback steps {tot_fb}")
    print(f"  censored_rate {rate:.3f} (prereg denominator = latch solves; "
          f"threshold {_et.CENSOR_THRESHOLD:.2f})   conditional {rate_c:.3f}")
    print(f"  wall/game mean {mean_w:.1f}s  median {walls[len(walls)//2]:.1f}s  "
          f"max {walls[-1]:.1f}s   peak RSS {_peak_rss_mb():.0f} MB")
    if _et.is_censored(rate):
        print(f"  ⚠️ realized rate {rate:.3f} ALREADY exceeds the {_et.CENSOR_THRESHOLD:.2f} "
              f"censoring threshold on the smoke — a full rung would be NOT-A-VERDICT. "
              f"Raise the cap (prereg branch 3) or drop the rung BEFORE launching.")
    else:
        print(f"  cap-hit rate is under the censoring threshold on this sample "
              f"(n={args.n} is a bench, not a guarantee).")
    print(f"  ETA for a 400-game rung at this mean, 1 box: "
          f"{400 * mean_w / 3600.0:.1f} box-hours of serial work "
          f"(/W workers).", flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("identity", "k6"), required=True)
    ap.add_argument("--n", type=int, default=20, help="games (even; decks x 2 seats)")
    ap.add_argument("--seed-start", type=int, required=True,
                    help="THROWAWAY seeds — must NOT be the ladder's claimed band")
    ap.add_argument("--cand-k", type=int, default=6)
    ap.add_argument("--opp-k", type=int, default=4)
    ap.add_argument("--exact-wall-caps", default="")
    ap.add_argument("--exact-k-floor", type=int, default=4)
    ap.add_argument("--exact-solver", choices=("python", "rust"), default="rust")
    ap.add_argument("--backend", choices=("python", "rust"), default="rust")
    ap.add_argument("--cand-sims", type=int, default=2750)
    ap.add_argument("--champ-sims", type=int, default=2750)
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--leaf-quantize", choices=("int", "float"), default="float")
    ap.add_argument("--final-select", choices=("Q", "visits", "lcb"), default="visits")
    _rules_profile.add_argument(ap)
    args = ap.parse_args(argv)
    if args.n % 2:
        ap.error("--n must be even (deck-paired: decks x 2 seats)")
    if args.exact_solver == "rust" and args.backend != "rust":
        ap.error("--exact-solver rust requires --backend rust (the tail solves on the "
                 "PREFIX's live MirrorState)")
    _rules_profile.activate(args.rules_profile)
    rp = _rules_profile.active().as_manifest()
    print(f"[f13-smoke] rules_profile={rp['name']} r9_env_observed={rp['r9_env_observed']} "
          f"r9_env_ok={rp['r9_env_ok']}  ({os.environ.get('CARCASSONNE_FIX_R9', 'unset')=})",
          flush=True)
    if not rp["r9_env_ok"]:
        print("[f13-smoke] FATAL: r9_env_ok is False — CARCASSONNE_FIX_R9 must be exported "
              "BEFORE this process starts (it is env-latched at import).", flush=True)
        return 3
    return mode_identity(args) if args.mode == "identity" else mode_k6(args)


if __name__ == "__main__":
    raise SystemExit(main())
