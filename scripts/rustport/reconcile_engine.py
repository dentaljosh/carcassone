"""G1 — the rustport engine gate.  0 mismatches, full stop.

Replays every game in the record through **both** engines in lockstep and
compares, at **every ply**:

  1. `Game.string_representation(board)` — byte equality (this string is the
     MCTS node key, so equality of *bytes* is the contract, not equality of
     information);
  2. `sha256(get_valid_moves(board).tobytes())` — the legal mask;
  3. `state.scores` — the running score;
  4. `flat_leaf.flat_base_score(state, 0)` — the exact terminal leaf, evaluated
     at every ply (not just at the end), which makes the whole farm/city/road
     scorer a per-ply invariant rather than an end-of-game one;
  5. the terminal scores, once the bag is empty.

Corpora (`--corpus`):

  golden  `tests/golden/golden_fixture.json` — the 12 recorded games replayed
          per-ply, PLUS the 56 frozen positions re-checked against the values
          on disk (mask sha256, flat_base_score, phase, current player).  The
          fixture check is the stronger one: it does not trust the live Python.
  champ   all 449 games of `measurement/champ_action_logs/champ_games.jsonl`.
  e4      both `measurement/e4_games/*.json` phone archives
          (schema `carcassonne-android-archive/v1`: deck_seed + actions), whose
          recorded final scores are also asserted.

Throughput (`--bench`) times each engine replaying the same games alone, so the
plies/s figures are not contaminated by the comparison itself.

Usage:
    .venv/bin/python scripts/rustport/reconcile_engine.py --corpus all --workers 8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# ⚠️ BEFORE any carcassonne_ai import — freezes DEFAULT_CONFIG at the production
# leaf SHAPE so a full-tree pytest that collects this module first cannot leave
# the session default bare (see scripts/rustport/prod_leaf_env.py). Inert here:
# this leg compares base scores and repr keys, which take no leaf config.
import prod_leaf_env  # noqa: E402,F401

import numpy as np  # noqa: E402

import carc_rs  # noqa: E402
from _g0_common import environment  # noqa: E402
from carcassonne_ai.flat_leaf import flat_base_score  # noqa: E402
from root_replay import replay_actions  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p1"
CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
E4DIR = REPO / "measurement" / "e4_games"
GOLDEN = REPO / "tests" / "golden" / "golden_fixture.json"


# ---------------------------------------------------------------------------
# Corpus loading -> a uniform list of jobs
# ---------------------------------------------------------------------------
def load_jobs(corpus: str, limit: int | None) -> list[dict]:
    jobs: list[dict] = []

    if corpus in ("champ", "all"):
        with CHAMP.open() as fh:
            for line in fh:
                if not line.strip():
                    continue
                g = json.loads(line)
                jobs.append({
                    "corpus": "champ",
                    "label": f"champ/{g['game_id']}",
                    "deck_seed": int(g["deck_seed"]),
                    "actions": [int(a) for a in g["actions"]],
                    "expect_scores": [int(g["score_p0"]), int(g["score_p1"])],
                })

    if corpus in ("e4", "all"):
        for path in sorted(E4DIR.glob("*.json")):
            d = json.loads(path.read_text())
            if d.get("schema") != "carcassonne-android-archive/v1":
                raise SystemExit(f"{path}: unexpected schema {d.get('schema')!r}")
            jobs.append({
                "corpus": "e4",
                "label": f"e4/{path.stem}",
                "deck_seed": int(d["deck_seed"]),
                "actions": [int(a) for a in d["actions"]],
                "expect_scores": [int(x) for x in d["result"]["scores"]],
            })

    if corpus in ("golden", "all"):
        fx = json.loads(GOLDEN.read_text())
        positions_by_seed: dict[int, list[dict]] = {}
        for p in fx["positions"]:
            positions_by_seed.setdefault(int(p["deck_seed"]), []).append(p)
        for seed_s, g in sorted(fx["games"].items(), key=lambda kv: int(kv[0])):
            seed = int(g.get("deck_seed", seed_s))
            jobs.append({
                "corpus": "golden",
                "label": f"golden/{seed}",
                "deck_seed": seed,
                "actions": [int(a) for a in g["actions"]],
                "expect_scores": [int(x) for x in g["terminal_scores"]]
                if "terminal_scores" in g else None,
                "expect_final_diff_p0": g.get("engine_final_diff_p0"),
                "frozen_positions": positions_by_seed.get(seed, []),
            })

    if limit is not None:
        jobs = jobs[:limit]
    return jobs


# ---------------------------------------------------------------------------
# One game, both engines, in lockstep
# ---------------------------------------------------------------------------
def check_game(job: dict) -> dict:
    seed = job["deck_seed"]
    actions = job["actions"]
    frozen = {int(p["ply"]): p for p in job.get("frozen_positions", [])}

    game, board = replay_actions(seed, actions, 0)
    ms = carc_rs.MirrorState.from_seed(str(seed))

    res = {
        "label": job["label"],
        "corpus": job["corpus"],
        "plies": 0,
        "compared": 0,
        "frozen_checked": 0,
        "mismatches": [],
    }

    def fail(kind: str, ply: int, py, rs, extra=None):
        rec = {"kind": kind, "label": job["label"], "deck_seed": seed, "ply": ply,
               "python": py, "rust": rs}
        if extra:
            rec.update(extra)
        res["mismatches"].append(rec)

    for i in range(len(actions) + 1):
        st = board.state
        terminal = st.is_terminated()

        # 1. string_representation — byte equality
        pr = game.string_representation(board)
        rr = ms.string_repr()
        if pr != rr:
            fail("string_representation", i, pr, rr)
            return res

        # 2. legal mask sha256 (undefined at terminal: the Python enumerator
        #    dereferences `next_tile`, which is None there)
        if not terminal:
            mask = np.asarray(game.get_valid_moves(board), dtype=bool)
            ph = hashlib.sha256(mask.tobytes()).hexdigest()
            rh = ms.legal_mask_sha256()
            if ph != rh:
                fail("legal_mask_sha256", i, ph, rh,
                     {"python_legal": np.flatnonzero(mask).tolist()[:40],
                      "rust_legal": ms.legal_actions()[:40]})
                return res

        # 3. running scores
        py_scores = [int(x) for x in st.scores]
        rs_scores = list(ms.scores())
        if py_scores != rs_scores:
            fail("scores", i, py_scores, rs_scores)
            return res

        # 4. flat_base_score (both POVs)
        for p in (0, 1):
            pb, rb = int(flat_base_score(st, p)), int(ms.flat_base_score(p))
            if pb != rb:
                fail(f"flat_base_score[p{p}]", i, pb, rb)
                return res

        # 5. cheap structural agreement
        if (st.current_player, st.phase.value, len(st.deck), bool(terminal)) != (
            ms.current_player(), ms.phase(), ms.deck_len(), ms.is_terminal()
        ):
            fail("state_scalars", i,
                 [st.current_player, st.phase.value, len(st.deck), bool(terminal)],
                 [ms.current_player(), ms.phase(), ms.deck_len(), ms.is_terminal()])
            return res

        # 6. frozen golden position, if this ply has one on disk
        fp = frozen.get(i)
        if fp is not None:
            got = {
                "legal_mask_sha256": ms.legal_mask_sha256(),
                "flat_base_score": [ms.flat_base_score(0), ms.flat_base_score(1)],
                "current_player": ms.current_player(),
                "phase": ms.phase(),
                "window_size": ms.window_offset()[2],
                "action_size": len(ms.legal_mask_bytes()),
                "legal_count": len(ms.legal_actions()),
            }
            want = {k: fp[k] for k in got}
            want["flat_base_score"] = [int(x) for x in want["flat_base_score"]]
            if got != want:
                fail("frozen_golden_position", i, want, got, {"position_id": fp["id"]})
                return res
            res["frozen_checked"] += 1

        res["compared"] += 1
        if i < len(actions):
            board, _ = game.get_next_state(board, int(actions[i]))
            ms.advance(int(actions[i]))
            res["plies"] += 1

    # terminal expectations from the record itself
    if not board.state.is_terminated():
        fail("not_terminal_after_replay", len(actions), False, False)
        return res
    if job.get("expect_scores") is not None:
        rec = [int(x) for x in job["expect_scores"]]
        if [int(x) for x in board.state.scores] != rec:
            fail("recorded_terminal_scores_python", len(actions), rec,
                 [int(x) for x in board.state.scores])
        if list(ms.scores()) != rec:
            fail("recorded_terminal_scores_rust", len(actions), rec, list(ms.scores()))
    if job.get("expect_final_diff_p0") is not None:
        want = int(job["expect_final_diff_p0"])
        if int(ms.flat_base_score(0)) != want:
            fail("golden_engine_final_diff_p0", len(actions), want, int(ms.flat_base_score(0)))
    return res


# ---------------------------------------------------------------------------
# Throughput
# ---------------------------------------------------------------------------
def bench(jobs: list[dict]) -> dict:
    """Time each engine replaying the same games on its own.  The per-ply work
    is the same on both sides: apply, repr, mask, flat_base_score."""
    def py_leg():
        plies = 0
        t0 = time.perf_counter()
        for job in jobs:
            game, board = replay_actions(job["deck_seed"], job["actions"], 0)
            for a in job["actions"]:
                game.string_representation(board)
                if not board.state.is_terminated():
                    game.get_valid_moves(board)
                flat_base_score(board.state, 0)
                board, _ = game.get_next_state(board, int(a))
                plies += 1
            game.clear_caches()
        return plies, time.perf_counter() - t0

    def rs_leg():
        plies = 0
        t0 = time.perf_counter()
        for job in jobs:
            ms = carc_rs.MirrorState.from_seed(str(job["deck_seed"]))
            for a in job["actions"]:
                ms.string_repr()
                if not ms.is_terminal():
                    ms.legal_mask_sha256()
                ms.flat_base_score(0)
                ms.advance(int(a))
                plies += 1
        return plies, time.perf_counter() - t0

    rp, rt = rs_leg()
    pp, pt = py_leg()
    return {
        "games": len(jobs),
        "python_plies": pp, "python_seconds": pt, "python_plies_per_s": pp / pt,
        "rust_plies": rp, "rust_seconds": rt, "rust_plies_per_s": rp / rt,
        "speedup": (rp / rt) / (pp / pt),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="all", choices=["all", "golden", "champ", "e4"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--bench", type=int, default=0,
                    help="also time N games through each engine alone")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    jobs = load_jobs(args.corpus, args.limit)
    t0 = time.perf_counter()

    if args.workers > 1:
        import multiprocessing as mp

        with mp.get_context("spawn").Pool(args.workers) as pool:
            results = pool.map(check_game, jobs, chunksize=1)
    else:
        results = [check_game(j) for j in jobs]

    elapsed = time.perf_counter() - t0

    per_corpus: dict[str, dict] = {}
    mismatches: list[dict] = []
    for r in results:
        c = per_corpus.setdefault(
            r["corpus"], {"games": 0, "plies": 0, "positions_compared": 0,
                          "frozen_positions_checked": 0, "mismatches": 0})
        c["games"] += 1
        c["plies"] += r["plies"]
        c["positions_compared"] += r["compared"]
        c["frozen_positions_checked"] += r["frozen_checked"]
        c["mismatches"] += len(r["mismatches"])
        mismatches.extend(r["mismatches"])

    ok = not mismatches
    payload = {
        "gate": "G1/engine",
        "verdict": "PASS" if ok else "FAIL",
        "env": environment(),
        "args": vars(args),
        "per_corpus": per_corpus,
        "total_games": sum(c["games"] for c in per_corpus.values()),
        "total_plies": sum(c["plies"] for c in per_corpus.values()),
        "total_positions_compared": sum(c["positions_compared"] for c in per_corpus.values()),
        "total_frozen_positions_checked":
            sum(c["frozen_positions_checked"] for c in per_corpus.values()),
        "per_ply_checks": ["string_representation(bytes)", "legal_mask_sha256",
                           "scores", "flat_base_score[p0]", "flat_base_score[p1]",
                           "state_scalars"],
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "wallclock_s": elapsed,
    }
    if args.bench:
        payload["throughput"] = bench(jobs[: args.bench])

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else OUTDIR / f"G1_engine_{args.corpus}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))

    for name, c in sorted(per_corpus.items()):
        print(f"G1/engine[{name}]: {c['games']} games, {c['plies']} plies, "
              f"{c['positions_compared']} positions compared, "
              f"{c['frozen_positions_checked']} frozen positions re-checked, "
              f"{c['mismatches']} mismatches")
    if "throughput" in payload:
        t = payload["throughput"]
        print(f"G1/engine: throughput over {t['games']} games — "
              f"python {t['python_plies_per_s']:.1f} plies/s, "
              f"rust {t['rust_plies_per_s']:.1f} plies/s "
              f"({t['speedup']:.1f}x)")
    print(f"G1/engine: {'PASS' if ok else 'FAIL'}  "
          f"{payload['total_positions_compared']} positions x "
          f"{len(payload['per_ply_checks'])} checks, "
          f"{len(mismatches)} mismatches, {elapsed:.1f}s")
    print(f"G1/engine: result -> {out}")
    for m in mismatches[:5]:
        print("  MISMATCH", json.dumps(m)[:600])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
