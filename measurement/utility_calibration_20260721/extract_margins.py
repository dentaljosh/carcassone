#!/usr/bin/env python3
"""F0b' STEP 1 — extract RAW and v2.9 LEAF margins for a replayable game corpus.

WHY THIS EXISTS (the F0b' feasibility finding):
The 2026-07-19 utility-calibration audit ran on the self-play npz shards under
`/mnt/c/carc-shared/distill_flywheel_sighted_20260716/`. Those shards store
    boards (144,81,25,25) | scalars (144,42) | policies | values | valid_masks | ownership
— i.e. ENCODED PLANES + scalars only. They store NO action sequence, and the repo
has no planes->engine-state decoder. The v2.9 leaf needs a real
`CarcassonneGameState` (it walks the tile/meeple/deck structure), so the LEAF
margin is NOT recoverable from that corpus.

So F0b' uses a FRESH but REPLAYABLE corpus: `measurement/window_audit/gen_games.jsonl`
(1400 complete games, `(deck_seed, action_sequence)`, losslessly replayable via
`scripts/measurement_infra/root_replay.py`). Every ply is reconstructed exactly and
BOTH margins are logged on the SAME positions, so the raw-vs-leaf contrast is not
confounded by a corpus change (the raw-margin calibration is recomputed here as the
control).

Per recorded ply (mover POV, mover = state.current_player):
  m_raw   = state.scores[mover] - state.scores[opp]
            == 50 * encode_scalars(...)[4]  (the EXACT quantity the 07-19 audit used)
  m_leaf  = flat_virtual_score_v2_float(state, mover, champion_leaf_cfg)
            == the value the search feeds to tanh(./value_norm)
  tiles   = tiles_remaining == 72 * encode_scalars(...)[5]
  y       = win label from the game's FINAL score (mover POV), 1/0/0.5

Champion leaf env (curve125 / cap8 / flat+cy) is set BEFORE importing carcassonne_ai
(the leaf config is built from env at import time). Verified by asserting the
resolved LeafConfig values, not a hash string (see scripts/distill_flywheel/champ_env.sh).
"""
from __future__ import annotations

import os

# --- champion leaf env, VERBATIM from scripts/distill_flywheel/champ_env.sh -------
# MUST be set before any carcassonne_ai import (DEFAULT_CONFIG is env-built at import).
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-10,-5,-1.25,0,2.5,3.75,5,6.25")
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(_REPO / "src"))

from carcassonne_ai import flat_leaf                      # noqa: E402
from carcassonne_ai.features import encode_scalars        # noqa: E402
from carcassonne_ai.game_wrapper import Game              # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
from root_replay import load_games                        # noqa: E402

SCORE_DIFF_NORM = 50.0    # features.SCORE_DIFF_NORM  (scalars[4])
DECK_NORM = 72.0          # features.DECK_NORM        (scalars[5])

CHAMP_CURVE = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)


def assert_champion_leaf(cfg) -> dict:
    """Fail loud if the resolved leaf is not the champion v2.9 curve125/cap8 leaf.
    We verify VALUES (champ_env.sh: the PRODUCTION.yaml hash string is stale)."""
    curve = tuple(float(x) for x in cfg.v29_meeple_curve) if cfg.v29_meeple_curve else None
    assert curve == CHAMP_CURVE, f"leaf curve is {curve}, expected curve125 {CHAMP_CURVE}"
    assert float(cfg.bonus_cap) == 8.0, f"bonus_cap={cfg.bonus_cap}, expected 8.0"
    assert float(cfg.opp_bonus_cap) == 8.0, f"opp_bonus_cap={cfg.opp_bonus_cap}, expected 8.0"
    assert dict(cfg.closure_p) == {1: 0.5, 2: 0.2, 3: 0.05}, f"closure_p={cfg.closure_p}"
    assert float(cfg.residual_scale) == 0.0 and float(cfg.value_blend) == 0.0
    assert not bool(getattr(cfg, "bag_close", False)), "bag_close must be OFF (v2.9)"
    desc = dict(
        v29_meeple_curve=list(curve), bonus_cap=float(cfg.bonus_cap),
        opp_bonus_cap=float(cfg.opp_bonus_cap), closure_p={str(k): v for k, v in cfg.closure_p.items()},
        meeple_k=float(cfg.meeple_k), bag_close=bool(getattr(cfg, "bag_close", False)),
        v29_punish_k=float(getattr(cfg, "v29_punish_k", 0.0)),
        v29_farm_access_k=float(getattr(cfg, "v29_farm_access_k", 0.0)),
        v29_meeple_return_k=float(getattr(cfg, "v29_meeple_return_k", 0.0)),
        v29_farm_flip_k=float(getattr(cfg, "v29_farm_flip_k", 0.0)),
    )
    try:  # best-effort frozen-config hash (champ_env expects 6dfffd57051690f2)
        from carcassonne_ai.champion_factory import _hashers
        _lh, _fch = _hashers()
        desc["frozen_config_hash"] = _fch(cfg)
    except Exception as exc:                                    # pragma: no cover
        desc["frozen_config_hash"] = f"unavailable ({type(exc).__name__})"
    return desc


def extract_one(rec_tuple):
    """Replay one game ply-by-ply, logging (raw, leaf, tiles) at every decision.

    Returns (game_id, raw[], leaf[], tiles[], ply[], mover[], y[], final_diff_p0)
    or None if the replay does not reach a terminal state (fail loud upstream)."""
    game_id, deck_seed, actions = rec_tuple
    cfg = DEFAULT_CONFIG
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    raw, leaf, tiles, plies, movers = [], [], [], [], []
    for i, a in enumerate(actions):
        st = board.state
        mover = int(st.current_player)
        sc = encode_scalars(st, mover, board.total_tiles)
        # rint: scalars are float32, so 50*sc[4] carries ~1e-6 error on a value that
        # is an INTEGER by construction. Rounding removes bucket-edge flips at the
        # multiples-of-5 histogram edges. (The 07-19 audit kept the float32 residue;
        # it moves no T* but can misfile an exact-edge row.)
        raw.append(float(np.rint(float(sc[4]) * SCORE_DIFF_NORM)))
        tiles.append(int(round(float(sc[5]) * DECK_NORM)))
        leaf.append(float(flat_leaf.flat_virtual_score_v2_float(st, mover, cfg, False)))
        movers.append(mover)
        plies.append(i)
        board, _ = game.get_next_state(board, int(a))

    if not board.state.is_terminated():
        return None
    final_p0 = int(board.state.scores[0]) - int(board.state.scores[1])
    mv = np.asarray(movers, dtype=np.int8)
    fd_mover = np.where(mv == 0, final_p0, -final_p0).astype(np.float64)
    y = np.where(fd_mover > 0, 1.0, np.where(fd_mover < 0, 0.0, 0.5))
    return (int(game_id), np.asarray(raw, np.float64), np.asarray(leaf, np.float64),
            np.asarray(tiles, np.int32), np.asarray(plies, np.int32), mv, y, final_p0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", default=str(_REPO / "measurement/window_audit/gen_games.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="0 = all games")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "margins.npz"))
    args = ap.parse_args()

    leaf_desc = assert_champion_leaf(DEFAULT_CONFIG)
    print(f"[leaf] champion v2.9 leaf verified: {json.dumps(leaf_desc)}", flush=True)
    print(f"[leaf] USE_CY_LEAF={flat_leaf.USE_CY_LEAF} USE_FLAT_LEAF={os.environ.get('CARCASSONNE_USE_FLAT_LEAF')}",
          flush=True)

    games = load_games(args.games)
    if args.limit:
        games = games[: args.limit]
    todo = [(g.game_id, g.deck_seed, g.actions) for g in games]
    print(f"[corpus] {len(todo)} games from {args.games}", flush=True)

    t0 = time.time()
    if args.workers <= 1:
        out = [extract_one(t) for t in todo]
    else:
        from multiprocessing import Pool
        with Pool(args.workers) as pool:
            out = []
            for i, r in enumerate(pool.imap_unordered(extract_one, todo, chunksize=4)):
                out.append(r)
                if (i + 1) % 100 == 0:
                    el = time.time() - t0
                    print(f"  {i+1}/{len(todo)} games  {el:.0f}s  "
                          f"(eta {el/(i+1)*(len(todo)-i-1):.0f}s)", flush=True)
    n_bad = sum(1 for r in out if r is None)
    out = [r for r in out if r is not None]
    if n_bad:
        print(f"[WARN] {n_bad} games did not reach a terminal state — DROPPED", flush=True)

    # stable game index (0..G-1) for the game-clustered bootstrap
    out.sort(key=lambda r: r[0])
    gid = np.concatenate([np.full(len(r[1]), i, np.int64) for i, r in enumerate(out)])
    data = dict(
        raw=np.concatenate([r[1] for r in out]),
        leaf=np.concatenate([r[2] for r in out]),
        tiles=np.concatenate([r[3] for r in out]),
        ply=np.concatenate([r[4] for r in out]),
        mover=np.concatenate([r[5] for r in out]),
        y=np.concatenate([r[6] for r in out]),
        gid=gid,
        game_id=np.asarray([r[0] for r in out], np.int64),
        final_diff_p0=np.asarray([r[7] for r in out], np.int64),
    )
    np.savez_compressed(args.out, **data)
    dt = time.time() - t0
    print(f"[done] {len(out)} games / {len(data['raw'])} positions in {dt:.1f}s -> {args.out}",
          flush=True)

    try:
        rev = subprocess.run(["git", "-C", str(_REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        rev = "unknown"
    man = dict(
        kind="f0b_prime_margin_extract",
        utc=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        code_rev=rev, host=os.uname().nodename,
        corpus=dict(path=args.games, n_games=len(out), n_games_dropped=n_bad,
                    n_positions=int(len(data["raw"])),
                    generator=games[0].meta if games else {},
                    replay="scripts/measurement_infra/root_replay.py (deck_seed + action seq, lossless)"),
        leaf=dict(fn="carcassonne_ai.flat_leaf.flat_virtual_score_v2_float",
                  cy=bool(flat_leaf.USE_CY_LEAF), config=leaf_desc),
        raw_margin="encode_scalars(state, mover, total_tiles)[4] * 50 "
                   "== state.scores[mover]-state.scores[opp] (identical to the 07-19 audit column)",
        tiles_remaining="encode_scalars(...)[5] * 72",
        win_label="sign(final score diff, mover POV); draws -> 0.5",
        env={k: os.environ.get(k) for k in
             ("CARCASSONNE_V29_MEEPLE_CURVE", "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP",
              "CARCASSONNE_USE_FLAT_LEAF", "CARCASSONNE_USE_CY_LEAF", "CARCASSONNE_USE_CY_REPR")},
        elapsed_s=dt, workers=args.workers,
    )
    mp = Path(args.out).with_name(f"manifest_extract_{Path(args.out).stem}.json")
    mp.write_text(json.dumps(man, indent=2))
    print(f"[done] wrote {mp.name}", flush=True)


if __name__ == "__main__":
    main()
