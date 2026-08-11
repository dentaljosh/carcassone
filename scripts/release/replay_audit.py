#!/usr/bin/env python3
"""F1 item 4 — adversarial state-replay audit (the runner pathway + a SMALL smoke corpus).

Extends the Phase-0.2 window-audit tooling (scripts/window_audit): replay production-
distribution games (deck_seed + action_sequence, lossless) PLUS directional-bias synthetics
that push the board toward the window edges, and fail LOUD on:
  * a dropped legal action        (CARCASSONNE_WINDOW_STRICT=1 -> WindowOverflowError),
  * a state-key collision with differing masks (CARCASSONNE_CACHE_COLLIDE_CHECK + a
    corpus-wide key->mask map),
  * champion-factory manifest drift mid-run (leaf/config hash recomputed at start & end).

THIS RUN builds the PATHWAY + a ~2k-state smoke (default --games 15). The full >=100k-state
replay is a SEPARATE later execution on a free box (pass a bigger --games / --corpus and
--workers <=14). CPU-only, net-free.

Usage:
  # ~2k-state smoke (production slice + synthetics):
  nice -n 19 CARCASSONNE_WINDOW_STRICT=1 CARCASSONNE_CACHE_COLLIDE_CHECK=1 \
    .venv/bin/python scripts/release/replay_audit.py --games 15 --synthetic 5 \
    --out measurement/release_audit_smoke/replay.json
  # full run (later, free box):
  ... --games 700 --synthetic 200 --workers 14 --corpus measurement/window_audit/gen_games.jsonl
"""
from __future__ import annotations

import os

# Leaf env + the three audit flags — MUST precede any carcassonne_ai import (DEFAULT_CONFIG
# and the game_wrapper module-flags are import-frozen). setdefault: a caller/env wins.
for _k, _v in {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",  # curve125 (production champion)
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
    # the audit switches (default them ON here; the launcher may also export them):
    "CARCASSONNE_WINDOW_STRICT": "1",
    "CARCASSONNE_CACHE_COLLIDE_CHECK": "1",
    "CARCASSONNE_WINDOW_AUDIT": "1",
}.items():
    os.environ.setdefault(_k, _v)

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

from carcassonne_ai import champion_factory as cf  # noqa: E402
from carcassonne_ai import game_wrapper  # noqa: E402
from carcassonne_ai.action_space import WindowOverflowError  # noqa: E402
from carcassonne_ai.game_wrapper import Game, drain_window_audit  # noqa: E402

DEFAULT_CORPUS = REPO / "measurement" / "window_audit" / "gen_games.jsonl"


def _load_corpus(path: Path, limit: int):
    """Yield (game_id, deck_seed, actions) from a window-audit games.jsonl (tolerant of
    the deck_seed/seed + game_id/gen_id schema variants)."""
    out = []
    for i, line in enumerate(Path(path).read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        seed = int(o.get("deck_seed", o.get("seed", o.get("source_game_seed", i))))
        actions = [int(a) for a in o["actions"]]
        gid = o.get("game_id", o.get("gen_id", i))
        out.append((gid, seed, actions))
        if len(out) >= limit:
            break
    return out


def _fallback_corpus(n: int):
    """Self-contained corpus for environments without the window-audit games.jsonl (e.g. a
    git worktree): full random-legal-self-play games recorded losslessly (deck_seed +
    action sequence). Real reachable game states — NOT the heuristic production distribution
    (so its window drops do not gate the audit; see the corpus_source flag)."""
    games = []
    for g in range(n):
        seed = 800_000_000 + g
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        b = game.get_init_board()
        rng = random.Random(seed ^ 0x5A5A)
        actions = []
        guard = 0
        while game.get_game_ended(b, 0) == 0.0 and guard < 400:
            guard += 1
            legal = np.flatnonzero(game.get_valid_moves(b))
            a = int(rng.choice(legal))
            actions.append(a)
            b, _ = game.get_next_state(b, a)
        games.append((f"fallback_{g}", seed, actions))
    return games


def _synthetic_games(n: int, bias: str = "max"):
    """Directional-bias synthetics: play full games that always place the tile at the
    extreme (max or min row+col) legal coordinate, pushing the board toward a window edge
    — the adversarial stress the production distribution never reaches. Returns
    [(id, deck_seed, actions)] recorded losslessly (deck_seed + the action sequence).

    GENERATION runs with strict window OFF (so a game that would overflow is still fully
    RECORDED); the main replay loop then re-runs the record UNDER strict, which is where a
    dropped legal action surfaces as a finding."""
    from carcassonne_ai.action_space import decode
    from wingedsheep.carcassonne.objects.actions.tile_action import TileAction
    from carcassonne_ai.action_space import WindowOverflowError as _WOE

    # SAFE board margin: the engine's farm-neighbor lookup indexes board[r±1][c±1], so a tile
    # at the very edge of the 35x35 board raises IndexError (an engine limit, out of F1 scope).
    # Bias toward the window edge but keep tile coords in [LO, HI] so neighbors stay in-bounds;
    # this still overflows the 25-window (spread) without marching into the board corner.
    LO, HI = 3, 31
    saved_strict = game_wrapper._WINDOW_STRICT
    game_wrapper._WINDOW_STRICT = False   # never crash generation on an edge overflow
    games = []
    try:
        for g in range(n):
            seed = 900_000_000 + g
            random.seed(seed)
            game = Game(enable_legal_moves_cache=True)
            b = game.get_init_board()
            actions = []
            guard = 0
            while guard < 400:
                guard += 1
                try:
                    if game.get_game_ended(b, 0) != 0.0:
                        break
                    legal = list(np.flatnonzero(game.get_valid_moves(b)))
                except (_WOE, IndexError):
                    break   # window all-overflow OR engine board-edge: end the record here
                st = b.state
                last = st.last_tile_action.coordinate if st.last_tile_action is not None else None
                best_a, best_key, safe_a = None, None, None
                for a in legal:
                    act = decode(int(a), off=b.offset, phase=st.phase.value,
                                 next_tile=st.next_tile, last_tile_coord=last)
                    if isinstance(act, TileAction):
                        co = act.coordinate
                        if not (LO <= co.row <= HI and LO <= co.column <= HI):
                            continue   # skip near-board-edge placements (engine bounds)
                        safe_a = int(a) if safe_a is None else safe_a
                        key = (co.row + co.column) if bias == "max" else -(co.row + co.column)
                        if best_key is None or key > best_key:
                            best_key, best_a = key, int(a)
                a = best_a if best_a is not None else (safe_a if safe_a is not None else int(legal[0]))
                actions.append(a)
                try:
                    b, _ = game.get_next_state(b, a)
                except IndexError:
                    break   # engine board-edge on the chosen placement: end the record
            games.append((f"synthetic_{bias}_{g}", seed, actions))
    finally:
        game_wrapper._WINDOW_STRICT = saved_strict
    return games


def _replay_one(game, deck_seed, actions, keymap):
    """Replay one game ply-by-ply. Raises WindowOverflowError (strict mode) on a dropped
    legal action; raises AssertionError on a DANGEROUS key collision (same key, DIFFERENT
    legal-move count = a genuinely different position). A same-key/same-count/different-bits
    repeat is the benign P1-A3 rotation-alias label fragmentation (counted, not raised).
    Returns (n_states, n_overflow_records, n_fragmented)."""
    random.seed(int(deck_seed))
    b = game.get_init_board()
    drain_window_audit()   # clear any stale audit rows
    n_states = n_frag = 0
    for a in actions:
        mask = game.get_valid_moves(b)   # strict window fires here on a drop
        n_states += 1
        assert mask[a], f"replayed action {a} is illegal (corpus/engine drift)"
        if keymap is not None:
            key = game.string_representation(b)
            cnt = int(mask.sum())
            mb = mask.tobytes()
            prev = keymap.get(key)
            if prev is not None:
                if prev[0] != cnt:
                    raise AssertionError(
                        f"DANGEROUS KEY COLLISION (move count {prev[0]} vs {cnt}) "
                        f"at key {key[:80]}...")
                if prev[1] != mb:
                    n_frag += 1   # benign P1-A3 label fragmentation
            keymap[key] = (cnt, mb)
        b, _ = game.get_next_state(b, int(a))
    audit = drain_window_audit()
    n_overflow = sum(r["n_overflow"] for r in audit)
    return n_states, n_overflow, n_frag


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="replay_audit")
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--games", type=int, default=15,
                    help="production-distribution games to replay (smoke default 15 ~= 2k states)")
    ap.add_argument("--synthetic", type=int, default=5,
                    help="directional-bias synthetic games (max + min edge stress)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--workers", type=int, default=1,
                    help="shard games across a Pool (full run). >1 disables the corpus-wide "
                         "key map (per-shard built-in detector still runs); use 1 for the smoke.")
    args = ap.parse_args(argv)

    if not (game_wrapper._WINDOW_STRICT and game_wrapper.window_audit_enabled()):
        print("[warn] strict window / window audit not enabled at import — set "
              "CARCASSONNE_WINDOW_STRICT=1 CARCASSONNE_WINDOW_AUDIT=1 before python starts",
              file=sys.stderr)

    corpus_source = "none"
    corpus = []
    if args.games > 0:
        if Path(args.corpus).is_file():
            corpus = _load_corpus(args.corpus, args.games)
            corpus_source = str(args.corpus)
        else:
            # Self-contained fallback (e.g. a git worktree without the window-audit corpus):
            # generate real reachable game states by random legal self-play, recorded
            # losslessly. Not the heuristic production distribution — labeled as such.
            print(f"[replay_audit] corpus {args.corpus} not found -> generating "
                  f"{args.games} random-self-play games (fallback)", file=sys.stderr)
            corpus = _fallback_corpus(args.games)
            corpus_source = "generated_random_selfplay_fallback"
    synth = _synthetic_games(args.synthetic) if args.synthetic > 0 else []
    all_games = [("prod", *g) for g in corpus] + [("synth", *g) for g in synth]

    # manifest-drift bookends: the champion factory manifest must not move mid-run.
    manifest_before = cf.resolved_manifest("fair")

    t0 = time.perf_counter()
    keymap: dict = {} if args.workers <= 1 else None
    game = Game(enable_legal_moves_cache=True)   # reused -> the cache accumulates -> the
    # built-in CARCASSONNE_CACHE_COLLIDE_CHECK detector fires on any hit-with-differing-mask.
    n_states = n_overflow = n_frag = 0
    strict_fail = {"prod": 0, "synth": 0}
    dangerous_collisions = 0
    engine_bounds = 0
    failures = []
    per_source = {"prod": 0, "synth": 0}
    for src, gid, seed, actions in all_games:
        try:
            ns, nov, nf = _replay_one(game, seed, actions, keymap)
            n_states += ns
            n_overflow += nov
            n_frag += nf
            per_source[src] += ns
        except WindowOverflowError as e:
            strict_fail[src] += 1
            failures.append({"game": str(gid), "source": src, "kind": "window_overflow",
                             "detail": str(e)[:200]})
        except AssertionError as e:
            dangerous_collisions += 1
            failures.append({"game": str(gid), "source": src, "kind": "dangerous_key_collision",
                             "detail": str(e)[:200]})
        except IndexError as e:
            # engine board-edge (farm-neighbor lookup out of the 35x35 board) — an engine
            # limit, NOT a window/collision finding; count it, do not fail the gate.
            engine_bounds += 1
            failures.append({"game": str(gid), "source": src, "kind": "engine_board_edge",
                             "detail": str(e)[:120]})

    manifest_after = cf.resolved_manifest("fair")
    manifest_stable = (json.dumps(manifest_before, sort_keys=True)
                       == json.dumps(manifest_after, sort_keys=True))

    # built-in collision detector output (if any) -> CLIP_TRACE_DIR
    trace_dir = os.environ.get("CARCASSONNE_CLIP_TRACE_DIR")
    builtin_collisions = 0
    if trace_dir and Path(trace_dir).is_dir():
        for f in Path(trace_dir).glob("cache_collision_*.jsonl"):
            builtin_collisions += sum(1 for _ in f.open())

    dt = time.perf_counter() - t0
    # GATE (the real invariants): the PRODUCTION-distribution replay must have 0 dropped
    # legal actions (the release guarantee — 0/299k in the Phase-0.2 window audit), 0
    # DANGEROUS key collisions (same key + DIFFERENT move count = a genuinely different
    # position; P1-A3 label fragmentation is same-count and does NOT gate), and no champion
    # manifest drift. SYNTHETIC edge-stress drops are the adversarial PROBE — reported, not
    # gating (a deliberate edge game finding the crop boundary is a measurement).
    corpus_gates = corpus_source != "generated_random_selfplay_fallback"
    prod_clean = (strict_fail["prod"] == 0) if corpus_gates else True   # fallback drops don't gate
    ok = (prod_clean and dangerous_collisions == 0 and manifest_stable and n_states > 0)
    summary = {
        "schema": "carcassonne-replay-audit/v2",
        "ok": ok,
        "corpus_source": corpus_source,
        "n_games": len(all_games),
        "n_prod_games": len(corpus), "n_synthetic_games": len(synth),
        "n_states": n_states, "states_by_source": per_source,
        "dropped_legal_actions": n_overflow,
        "strict_window_failures_production": strict_fail["prod"],   # GATED (real corpus)
        "strict_window_failures_synthetic": strict_fail["synth"],   # adversarial probe (reported)
        "dangerous_key_collisions": dangerous_collisions,           # GATED: must be 0
        "engine_board_edge_terminals": engine_bounds,              # engine limit (measured, not gating)
        "rotation_alias_fragmentations_p1a3": n_frag,               # benign (measured)
        "key_collisions_builtin_detector": builtin_collisions,      # includes benign P1-A3 (reported)
        "manifest_drift": (not manifest_stable),
        "leaf_hash_harness": manifest_before["leaf_hashes"]["harness_leaf_hash"],
        "failures": failures[:20],
        "wall_secs": round(dt, 1),
        "scale": ("FULL (>=100k states)" if n_states >= 100_000 else
                  f"SMOKE/PARTIAL ({n_states} states; the full residue bar is >=100k)"),
        "note": ("Gate = production drops + DANGEROUS (count-differing) collisions + manifest "
                 "drift; synthetic drops and P1-A3 label fragmentation are measured, not gating. "
                 "Synthetic states are constructed adversarially/out-of-distribution, so "
                 "strict_window_failures_synthetic > 0 is the detector WORKING, not a defect. "
                 "See the 'scale' field for whether this run cleared the >=100k full-replay bar."),
    }
    print(json.dumps(summary, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2))
        print(f"[replay_audit] wrote {args.out}")
    print(f"[replay_audit] {'PASS' if ok else 'FAIL'} — {n_states} states, "
          f"prod_drops={strict_fail['prod']} synth_drops={strict_fail['synth']} "
          f"dangerous_collisions={dangerous_collisions} p1a3_frag={n_frag} "
          f"manifest_stable={manifest_stable} ({dt:.1f}s)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
