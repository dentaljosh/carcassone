#!/usr/bin/env python3
"""C-cheap — net-free FAIR self-play emitter for deck-aware VALUE labels.

Pre-registration / design: C_CHEAP_SPEC.md §2 ("Data") + §7 (the file list).

WHY: C-cheap trains a deck-aware value head on FAIR (blind-determinization) self-play
OUTCOME labels, on the SIGHTED (81ch/42-scalar) representation — the one regime the
value-inertness ledger never tested (removes the F-B2 clairvoyant train/serve
mismatch: the value learns the fair value function under the SAME information it is
deployed with). `selfplay.py` is clairvoyant/net-driven and cannot do this, so this
is the one new artifact C-cheap needs.

WHAT IT DOES: the production HEURISTIC fair champion `FairHeuristicMCTSAgent` plays
itself (NET-FREE — pure CPU heuristic v2.9 leaf → laptop+xeon fan-out eligible,
`nice -n 19`). Per ply it records, from the MOVER's POV:
  * the SIGHTED observation  (Game(sighted=True).get_canonical_form → 81ch board)
  * the SIGHTED scalars+bag  (42 scalars: 10 base + 32 bag histogram)
  * the FAIR game OUTCOME as `score_diff_wide` = tanh((p0-p1)/40)  (C6 de-saturated,
    exactly selfplay.py:544), mover-POV-signed per ply.
The rows are emitted as a `warmstart.GameDataset` .npz shard (one per game) with
`aux_mask=False` (VALUE-ONLY rows — dummy policy/ownership/mask, so the existing
value-only trainer trains ONLY the value head; the policy priors stay the heuristic
softmax at play time and are never learned here).

POV / target convention MATCHES the eval-time net value
(`make_heuristic_prior_evaluator_with_net_value`): both encode the board from the
MOVER (= board.state.current_player) POV, and the net value is that mover's expected
score_diff_wide. So train-time obs == eval-time obs (an encode-parity test pins it).

ENDGAME: default `--no-exact-endgame` (pure fair PIMC to the terminal) so gen stays
net-free, CPU-parallel, and RAM-light (no marginalized solver). `--exact-endgame`
turns on the K<=2 marginalized handoff (more faithful fair outcomes, ~+10s/game).

PARALLELISM / RESUME / DETACH: one game per seed → one `seed_<seed>.npz` shard;
`multiprocessing.Pool` fans out; `--shared-claim` uses the same O_EXCL `.claim`
protocol as the self-play/eval launchers (cross-box work-stealing over the CIFS
share); an existing shard is skipped (idempotent resume). DETACH any real run
(`nohup … & disown` / `setsid`) — Mac-sleep SIGHUP + WSL teardown both kill tty jobs.

Recommended CHEAP first-head config (C_CHEAP_SPEC §4): --k-dets 4 --sims 128,
~1–2k games, split laptop+xeon.

Usage:
  # 2-game plumbing smoke (single process, writes a valid npz):
  .venv/bin/python scripts/canonical_az/gen_fair_selfplay.py \
      --games 2 --k-dets 4 --sims 32 --workers 1 --out /tmp/fair_gen_smoke

  # cheap first head (local; split across boxes by seed range for the cluster):
  nice -n 19 .venv/bin/python -u scripts/canonical_az/gen_fair_selfplay.py \
      --games 1500 --k-dets 4 --sims 128 --workers 14 --seed-start 40000000000 \
      --out /mnt/c/carc-shared/fair_value_gen/head1 --shared-claim
"""
from __future__ import annotations

import os

# v2.9 Bmild_cap8 leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Verbatim from eval_fair_puct.py so the fair self-play leaf
# is the production v2.9 leaf. Net-free → CUDA hidden, single-thread BLAS.
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse
import random
import socket
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.aux_targets import OWNERSHIP_PLANES  # noqa: E402
from carcassonne_ai.claim import try_claim as _try_claim  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.run_manifest import code_rev, game_tag, write_manifest  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
from carcassonne_ai.warmstart import GameDataset  # noqa: E402


def _shard_path(out: Path, seed: int) -> Path:
    return out / f"seed_{seed:012d}.npz"


def play_fair_game_to_dataset(
    seed: int, *, k_dets: int, sims: int, c_puct: float = 3.0,
    exact_endgame: bool = False, window_size: int = 25, max_plies: int = 400,
) -> tuple[GameDataset | None, dict]:
    """Play ONE net-free fair self-play game (FairHeuristicMCTSAgent vs itself) and
    return (value-only GameDataset, info). The dataset holds one row per ply:
    sighted obs + scalars, `values` = mover-POV score_diff_wide of the FINAL score,
    policies/ownership/valid_masks dummy, aux_mask=False (value-only)."""
    random.seed(seed)  # seeds the deck shuffle (get_init_board uses the global RNG)
    game = Game(enable_legal_moves_cache=True, window_size=window_size)   # referee / deck driver
    encoder = Game(sighted=True, window_size=window_size)                 # sighted obs encoder
    agent = FairHeuristicMCTSAgent(
        Game(enable_legal_moves_cache=True, window_size=window_size),
        sims=sims, k_dets=k_dets, c_puct=c_puct, seed=seed,
        leaf_cfg=DEFAULT_CONFIG, exact_endgame=exact_endgame,
    )

    board = game.get_init_board()
    obs_list: list[np.ndarray] = []
    scl_list: list[np.ndarray] = []
    mover_list: list[int] = []
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mover = board.state.current_player
        obs, scl = encoder.get_canonical_form(board, mover)   # NEVER mutates board
        obs_list.append(obs)
        scl_list.append(scl)
        mover_list.append(mover)
        action = agent.move(board)   # deepcopies internally; board unmutated
        board, _ = game.get_next_state(board, action)
        plies += 1

    s0, s1 = int(board.state.scores[0]), int(board.state.scores[1])
    terminated = game.get_game_ended(board, 0) != 0.0
    info = {"seed": seed, "plies": plies, "score_p0": s0, "score_p1": s1,
            "diff": s0 - s1, "terminated": terminated,
            "exact_moves": agent.exact_moves, "n_timeouts": agent.n_timeouts}
    if not terminated:
        # Refuse to emit a shard with mid-game value targets (selfplay.py discipline).
        info["error"] = f"game did not terminate in {max_plies} plies"
        return None, info
    if not obs_list:
        info["error"] = "no plies recorded"
        return None, info

    # C6-de-saturated outcome, mover-POV-signed (== selfplay.py score_diff_wide).
    z_p0 = float(np.tanh((s0 - s1) / 40.0))
    values = np.array([z_p0 if m == 0 else -z_p0 for m in mover_list], dtype=np.float32)

    N = len(obs_list)
    A = game.get_action_size()
    W = window_size
    ds = GameDataset(
        boards=np.stack(obs_list).astype(np.float32, copy=False),      # (N,81,W,W)
        scalars=np.stack(scl_list).astype(np.float32, copy=False),     # (N,42)
        policies=np.zeros((N, A), dtype=np.float32),                   # value-only dummy
        values=values,                                                 # (N,) mover-POV
        valid_masks=np.zeros((N, A), dtype=bool),                      # value-only dummy
        ownership=np.zeros((N, OWNERSHIP_PLANES, W, W), dtype=np.float32),
        aux_mask=np.zeros(N, dtype=bool),   # every row is VALUE-ONLY (aux_mask=False)
    )
    return ds, info


_W: dict = {}


def _worker_init(k_dets, sims, c_puct, exact_endgame, window_size,
                 shared_claim, claim_host, claim_stale):
    _W.update(k_dets=k_dets, sims=sims, c_puct=c_puct, exact_endgame=exact_endgame,
              window_size=window_size, shared_claim=shared_claim,
              claim_host=claim_host, claim_stale=claim_stale)


def _play_one(args) -> dict | None:
    out_str, seed = args
    out = Path(out_str)
    p = _shard_path(out, seed)
    if p.exists():
        return {"seed": seed, "cached": True}
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None
    ds, info = play_fair_game_to_dataset(
        seed, k_dets=_W["k_dets"], sims=_W["sims"], c_puct=_W["c_puct"],
        exact_endgame=_W["exact_endgame"], window_size=_W["window_size"],
    )
    if ds is None:
        info["skipped"] = True
        return info
    ds.save(p)
    info["rows"] = len(ds)
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gen_fair_selfplay")
    ap.add_argument("--games", type=int, required=True, help="number of games (= seeds)")
    ap.add_argument("--k-dets", type=int, default=4, help="determinizations per move (fair PIMC)")
    ap.add_argument("--sims", type=int, default=128, help="HeuristicMCTS sims per determinization")
    ap.add_argument("--c-puct", type=float, default=3.0, help="HeuristicMCTS UCT c (champion 3.0)")
    ap.add_argument("--exact-endgame", dest="exact_endgame", action="store_true", default=False,
                    help="use the K<=2 marginalized endgame handoff (default OFF: pure fair PIMC, "
                         "cheaper/RAM-light net-free gen)")
    ap.add_argument("--no-exact-endgame", dest="exact_endgame", action="store_false")
    ap.add_argument("--window-size", type=int, default=25)
    ap.add_argument("--workers", type=int, default=None, help="Pool size (default min(cpu,games))")
    ap.add_argument("--seed-start", type=int, default=40_000_000_000,
                    help="first seed; games use seed_start..seed_start+games-1")
    ap.add_argument("--out", type=str, required=True, help="output dir for seed_*.npz shards")
    ap.add_argument("--shared-claim", action="store_true", help="O_EXCL .claim work-stealing")
    ap.add_argument("--claim-stale-secs", type=int, default=7200)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seeds = [args.seed_start + i for i in range(args.games)]

    # Self-describing manifest (results discipline: every gen writes one).
    man = {
        "generator": "FairHeuristicMCTSAgent self-play (net-free)",
        "value_target": "score_diff_wide = tanh((p0-p1)/40), mover-POV-signed",
        "representation": "sighted 81ch board / 42-scalar (10 base + 32 bag histogram)",
        "row_kind": "value-only (aux_mask=False; dummy policy/ownership/mask)",
        "k_dets": args.k_dets, "sims": args.sims, "c_puct": args.c_puct,
        "exact_endgame": args.exact_endgame, "window_size": args.window_size,
        "games": args.games, "seed_start": args.seed_start,
        "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)", "code_rev": code_rev(),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
    }
    write_manifest(out, kind="gen_fair_selfplay", game=game_tag(Game()),
                   config=man, overwrite=True)

    todo = [(str(out), s) for s in seeds if not _shard_path(out, s).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"gen_fair_selfplay: games={args.games} k_dets={args.k_dets} sims={args.sims} "
          f"exact_endgame={args.exact_endgame} | {len(seeds)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}", flush=True)

    if not todo:
        print("nothing to do (all shards present)")
        return 0

    t0 = time.perf_counter()
    played = skipped = rows = 0
    with Pool(processes=workers, initializer=_worker_init,
              initargs=(args.k_dets, args.sims, args.c_puct, args.exact_endgame,
                        args.window_size, args.shared_claim, args.claim_host,
                        args.claim_stale_secs)) as pool:
        for r in pool.imap_unordered(_play_one, todo, chunksize=1):
            if r is None or r.get("cached"):
                continue
            if r.get("skipped"):
                skipped += 1
                print(f"  [skip] seed={r['seed']}: {r.get('error')}", flush=True)
                continue
            played += 1
            rows += r.get("rows", 0)
            if played % 10 == 0 or played == len(todo):
                el = time.perf_counter() - t0
                print(f"  {played}/{len(todo)} games ({el/played:.1f}s/game, "
                      f"{rows} rows, ~{(len(todo)-played)*el/played/60:.0f} min left)",
                      flush=True)

    print(f"[done] {played} games, {rows} value rows, {skipped} skipped "
          f"({time.perf_counter()-t0:.1f}s). shards in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
