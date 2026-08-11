#!/usr/bin/env python3
"""Encode real Carcassonne positions into (board, scalars) arrays for LiteRT verification.

WHY A SEPARATE SCRIPT: ``verify_agreement.py`` runs inside the LiteRT converter venv,
which has torch + ai-edge-litert but NOT the game engine. Encoding needs the engine
(replay + ``Game(sighted=True).get_canonical_form``). Rather than install the engine into
the converter venv — or, worse, import the LIVE tree while cluster runs are re-importing
from disk — this step runs against the **frozen M5 bundle** (a standalone copy of the
champion code + ``positions.jsonl``, built 2026-07-28) and dumps a plain ``.npz``.

The npz is the only thing that crosses the venv boundary. Nothing here imports
``/home/doctor/projects/carcassone/src`` or ``engine/``.

Usage (system python3 with numpy; NOT the project .venv, NOT the converter venv):

    PYTHONPATH=/mnt/c/carc-shared/m5_bench_20260728/bundle \
      python3 scripts/pixel_npu/encode_positions.py \
        --out /mnt/c/carc-shared/pixel_npu_20260729/positions_encoded.npz

Position replay contract (inlined from ``scripts/measurement_infra/root_replay.py``, and
identical to the copy in the M5 ``bench_champion.py``): the wingedsheep engine touches the
global ``random`` stream in exactly one place — the deck shuffle inside ``get_init_board``
— so ``(deck_seed, action_prefix)`` reconstructs a position exactly and losslessly, for any
policy that generated it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import sys
import time
from pathlib import Path

import numpy as np

DEFAULT_BUNDLE = Path("/mnt/c/carc-shared/m5_bench_20260728/bundle")


def load_positions(path: Path, limit: int | None) -> list[dict]:
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    if not rows:
        raise SystemExit(f"encode_positions: empty positions file {path}")
    return rows[:limit] if limit else rows


def replay(Game, row: dict):
    """Reconstruct the board at ``row['ply']``. See module docstring for the contract."""
    random.seed(int(row["deck_seed"]))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for a in row["actions"]:
        board, _ = game.get_next_state(board, int(a))
    return board


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE,
                   help="frozen M5 bundle (standalone champion code + positions.jsonl)")
    p.add_argument("--positions", type=Path, default=None,
                   help="default: <bundle>/positions.jsonl")
    p.add_argument("--limit", type=int, default=None, help="first N positions only")
    p.add_argument("--out", type=Path, required=True, help="output .npz")
    a = p.parse_args(argv)

    bundle = a.bundle.resolve()
    if not bundle.is_dir():
        raise SystemExit(f"encode_positions: no bundle at {bundle}")
    sys.path.insert(0, str(bundle))

    positions_path = a.positions or (bundle / "positions.jsonl")
    rows = load_positions(positions_path, a.limit)

    from carcassonne_ai.game_wrapper import Game  # noqa: PLC0415

    # The sighted (81ch / 42-scalar) encoder — the representation the CL-067 distilled
    # net was trained on. Construction mirrors make_heuristic_prior_evaluator_with_net_value
    # in carcassonne_ai/heuristic_prior_mcts.py, which is the deployed call site.
    sighted_game = Game(sighted=True)
    n_ch = sighted_game.get_input_channels()
    n_scl = sighted_game.get_scalar_feature_size()
    W = sighted_game.window_size
    if (n_ch, n_scl) != (81, 42):
        raise SystemExit(
            f"encode_positions: sighted encoder gave {n_ch}ch/{n_scl} scalars, expected 81/42.\n"
            "  The bundle's representation does not match the CL-067 net. Refusing to emit\n"
            "  arrays that would silently produce a meaningless agreement number.")

    action_size = sighted_game.get_action_size()
    boards = np.zeros((len(rows), n_ch, W, W), dtype=np.float32)
    scalars = np.zeros((len(rows), n_scl), dtype=np.float32)
    # The LEGAL-MOVE MASK is why this file is worth more than random inputs. A policy head has
    # 2511 logits but only a handful are ever reachable; "argmax over all 2511" can agree while
    # the move the agent would actually play disagrees, and vice versa. Carrying the mask lets
    # verify_agreement.py score argmax over the LEGAL set -- the decision that matters.
    legal = np.zeros((len(rows), action_size), dtype=bool)
    meta = []
    t0 = time.perf_counter()
    for i, row in enumerate(rows):
        board = replay(Game, row)
        mover = board.state.current_player      # the POV the deployed evaluator uses
        obs, scl = sighted_game.get_canonical_form(board, mover)
        boards[i] = np.ascontiguousarray(obs, dtype=np.float32)
        scalars[i] = np.ascontiguousarray(scl, dtype=np.float32)
        mask = np.asarray(sighted_game.get_valid_moves(board)).astype(bool)
        legal[i] = mask
        n_legal_actual = int(mask.sum())
        if n_legal_actual != int(row["n_legal"]):
            # The positions file records n_legal at capture time; a mismatch means the replay
            # landed somewhere else. Fail rather than emit a mislabelled position.
            raise SystemExit(
                f"encode_positions: pos_id {row['pos_id']} replayed to {n_legal_actual} legal "
                f"moves but positions.jsonl says {row['n_legal']}. The replay contract is "
                "broken for this bundle; refusing to emit.")
        meta.append({"pos_id": int(row["pos_id"]), "ply": int(row["ply"]),
                     "phase": row["phase"], "k_remaining": int(row["k_remaining"]),
                     "n_legal": n_legal_actual, "mover": int(mover)})
    dt = time.perf_counter() - t0

    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        a.out, boards=boards, scalars=scalars, legal=legal,
        meta=np.array(json.dumps(meta)),
        provenance=np.array(json.dumps({
            "bundle": str(bundle),
            "positions": str(positions_path),
            "positions_sha256": hashlib.sha256(positions_path.read_bytes()).hexdigest(),
            "n": len(rows), "n_channels": n_ch, "n_scalars": n_scl, "window": W,
            "action_size": int(action_size),
            "use_cy_repr": os.environ.get("CARCASSONNE_USE_CY_REPR", "(unset)"),
            "python": sys.version.split()[0], "platform": platform.platform(),
            "numpy": np.__version__,
            "encoded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })),
    )
    print(f"encode_positions: {len(rows)} positions -> {a.out}")
    print(f"  boards {boards.shape} {boards.dtype}   scalars {scalars.shape}")
    print(f"  encode wall {dt:.2f}s   board nonzero-frac "
          f"{float((boards != 0).mean()):.4f}   scalar absmax {float(np.abs(scalars).max()):.4f}")
    nl = legal.sum(axis=1)
    print(f"  legal mask {legal.shape}   legal moves per position: "
          f"min {int(nl.min())}  median {int(np.median(nl))}  max {int(nl.max())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
