#!/usr/bin/env python3
"""Compute the Part C phase-multiplier renormalizer `E[f(k; beta)]`, per beta.

Prereg: `measurement/curve_shape_scope_20260809/PREREG_DRAFT.md` §4 / `SCOPE.md` §1.3.

    f(k; beta) = clip(1 + beta*(k - 35)/35, 0.0, 2.0)          K0 = 35
    f_eff      = f(k; beta) / norm(beta),   norm(beta) := E[f(k; beta)]

so that `E[f_eff] = 1` over a game's empirical `k_remaining` distribution. WITHOUT
this renormalization beta moves the meeple term's mean MAGNITUDE, and the cell
measures scale rather than phase — the exact confound that invalidated the
2026-06-22 `v28_meeple_recovery_t0` kill. The constant is therefore load-bearing,
and this script is the only place it is produced.

======================================================================
WHICH DISTRIBUTION THIS USES — read before quoting a number
======================================================================
The ideal weight is "how often the leaf is evaluated at each k", i.e. the
k-histogram over MCTS **leaf nodes**. Deriving that exactly needs an instrumented
search (the leaf-k depends on the tree shape at every root, and the tree shape
depends on the leaf — circular at the point where the constant is needed).

**THIS SCRIPT USES THE ACCEPTABLE APPROXIMATION NAMED IN THE BRIEF: the k-histogram
over the PLIES OF REAL `fixed_v1` GAMES**, one count per ply actually played
(so a k that spans a tile ply and a meeple ply is counted twice, which is right —
the leaf is consulted from both). Games are played by the production champion
config at a REDUCED search budget (`--sims` / `--k-dets`), which is what keeps this
under the ~2 min compute bar.

Why the approximation is tolerable, stated honestly:
  * `f` is LINEAR in k except where the clip bites, so to first order
    `E[f] = 1 + beta*(E[k] - 35)/35` — only the MEAN of the k-distribution matters,
    not its shape.
  * The leaf-k distribution is the ply-k distribution shifted DOWN by the mean
    search depth d (a leaf sits d plies below its root). That biases `E[f]` by
    `-beta*d/35`: at the ladder's extreme (|beta| = 0.6) and a plausible d ≈ 3 plies
    that is ~5% of the multiplier, i.e. the renormalization removes the ~O(10%)
    magnitude confound and leaves an ~O(0.5%) residue. It does NOT remove it exactly.
  * The residue is SIGNED-SYMMETRIC in beta, so the prereg's primary statistic —
    the fitted slope across the signed ladder {-0.6,-0.3,0,+0.3,+0.6} — is affected
    in its scale, not its sign or its z. The ladder is the instrument; this constant
    de-confounds it to first order.

`--report-ply-lag` prints the mean/median k so a future instrumented measurement can
be compared against this one without re-deriving anything.

beta = 0 comes out at norm = 1.0 EXACTLY (f is identically 1.0; no float path taken).

Usage (defaults are the pre-registered ladder, ~1 min on the local box):

    nice -n 19 python scripts/classical_search/compute_phase_norm.py
    nice -n 19 python scripts/classical_search/compute_phase_norm.py --games 12 --json-out norms.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The leaf env MUST be set before any carcassonne_ai import (DEFAULT_CONFIG is the
# env-resolved singleton, latched at virtual_score_v2 import time), and R9 must be in
# the ENVIRONMENT before the Rust registry latches its OnceLock (see rules_profile
# "fixed_v1": R9 is not in the profile and cannot be).
os.environ.setdefault("CARCASSONNE_FIX_R9", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-10,-5,-1.25,0,2.5,3.75,5,6.25")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

PREREG_BETAS = (-0.6, -0.3, 0.0, 0.3, 0.6)
K0 = 35.0


def f_raw(k: int, beta: float) -> float:
    """`clip(1 + beta*(k - K0)/K0, 0.0, 2.0)` — the UNNORMALIZED phase weight.
    Byte-identical arithmetic to `flat_leaf._phase_mult` with norm = 1.0."""
    f = 1.0 + beta * (k - K0) / K0
    if f < 0.0:
        f = 0.0
    elif f > 2.0:
        f = 2.0
    return f


def k_histogram(n_games: int, sims: int, k_dets: int, seed0: int) -> dict:
    """Play `n_games` `fixed_v1` games with the production champion config at a
    reduced budget; return {k_remaining: ply_count} over every ply actually played."""
    from carcassonne_ai import rules_profile
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.fair_agent import k_remaining
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai import mirror_protocol as MP

    prof = rules_profile.activate("fixed_v1")
    hist: dict[int, int] = {}
    plies_per_game = []
    for gi in range(n_games):
        random.seed(seed0 + gi)          # fixes the engine shuffle (root_replay contract)
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        agents = {
            s: make_production_champion(
                "fair", game=game, seed=seed0 + 1000 * (gi + 1) + s,
                sims=sims, k_dets=k_dets, exact_endgame=True,
                backend="rust", rust_threads=1)
            for s in (0, 1)
        }
        board = game.get_init_board()
        MP.seat(agents, board)
        plies = 0
        while game.get_game_ended(board, 0) == 0.0:
            st = board.state
            k = k_remaining(st)
            hist[k] = hist.get(k, 0) + 1
            plies += 1
            a = int(agents[st.current_player].choose_action(board))
            board, _ = game.get_next_state(board, a)
            MP.advance(agents, a, board)
        plies_per_game.append(plies)
    return {"hist": hist, "plies_per_game": plies_per_game,
            "rules_profile": prof.name, "r9_env_ok": rules_profile.r9_env_on()}


def norms(hist: dict, betas) -> dict:
    total = sum(hist.values())
    out = {}
    for b in betas:
        if b == 0.0:
            out[b] = 1.0            # f == 1.0 identically; no float path taken
            continue
        out[b] = sum(c * f_raw(k, b) for k, c in hist.items()) / total
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=6,
                    help="fixed_v1 games to play for the k-histogram (default 6)")
    ap.add_argument("--sims", type=int, default=48,
                    help="sims per determinization (REDUCED from production 1376 — the "
                         "k-histogram is a game-length property, not a strength one)")
    ap.add_argument("--k-dets", type=int, default=2,
                    help="determinizations (REDUCED from production 8)")
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--betas", default=",".join(str(b) for b in PREREG_BETAS),
                    help="comma-separated beta ladder (default: the pre-registered one)")
    ap.add_argument("--json-out", default=None, help="also write the payload here")
    ap.add_argument("--report-ply-lag", action="store_true",
                    help="print the k-distribution summary (for a future instrumented "
                         "leaf-k measurement to be compared against)")
    args = ap.parse_args(argv)

    betas = [float(x) for x in args.betas.split(",")]
    t0 = time.perf_counter()
    h = k_histogram(args.games, args.sims, args.k_dets, args.seed)
    secs = time.perf_counter() - t0
    hist = h["hist"]
    total = sum(hist.values())
    mean_k = sum(k * c for k, c in hist.items()) / total
    nrm = norms(hist, betas)

    payload = {
        "source": "ply k-histogram over fixed_v1 games (APPROXIMATION — see module "
                  "docstring; the exact object is the MCTS leaf-k histogram)",
        "K0": K0,
        "rules_profile": h["rules_profile"],
        "r9_env_ok": h["r9_env_ok"],
        "games": args.games, "sims": args.sims, "k_dets": args.k_dets, "seed": args.seed,
        "plies_total": total, "plies_per_game": h["plies_per_game"],
        "mean_k": mean_k,
        "k_min": min(hist), "k_max": max(hist),
        "norms": {str(b): nrm[b] for b in betas},
        "secs": round(secs, 1),
    }
    print(json.dumps(payload["norms"], indent=2))
    if args.report_ply_lag:
        print(f"# plies={total} over {args.games} games; mean k={mean_k:.3f} "
              f"(range {min(hist)}..{max(hist)}); {secs:.1f}s", file=sys.stderr)
        print("# NOTE: leaf-k sits BELOW ply-k by the mean search depth; see docstring.",
              file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
