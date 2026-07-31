"""rustport **P3 / gate G3** — single-world PUCT: Rust vs Python, 0 mismatches.

    .venv/bin/python scripts/rustport/reconcile_search.py --help

WHAT IS COMPARED, per searched position (all RAW-FLOAT, never decimal):

  * the CHOSEN root action (`final_select` from `governance/PRODUCTION.yaml`);
  * `root.children` — every `(action, N, W)` pair, `W` as raw `f64` bits;
  * the deduped root children (`_deduped_children`, the transposition-collapse);
  * `root.N` / `root.W` / `root.leaf_value` (which carries the ROOT-ONLY
    `float32` round-trip that `_eval_boards` imposes and `_expand` does not);
  * the root prior vector, action by action, as raw bits (this is the
    `np.exp` x `numpy-pairwise-sum` x `float32` chain in one number);
  * the node count — a structural check that the two trees have the same SHAPE,
    not merely the same root statistics.

CORPORA (`--corpus`, repeatable, or `all`):

  golden   the 12 golden-fixture games, searched every `--stride` plies
  midgame  measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl
  champ    measurement/champ_action_logs/champ_games.jsonl
  distill  measurement/utility_calibration_20260721/gen_games_champ125.jsonl
  e4       both on-device archives (measurement/e4_games/*.json)
  det      champ positions with the UNSEEN DECK PERMUTED — the single-world
           surface P4's PIMC will drive; both legs get the SAME permutation
  games    FULL self-play games: BOTH seats searched every ply with a fresh
           tree, the chosen action applied, to termination

`--sims` may be repeated (the gate runs 1376 for the verdict and a cheaper 344
for breadth). `--bench` measures sims/s on both legs over the same positions.

Artifacts land in `measurement/rustport_p3/`.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
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

import carc_rs  # noqa: E402

import trace_search as T  # noqa: E402
from _g0_common import environment  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p3"
GOLDEN = REPO / "tests" / "golden" / "golden_fixture.json"
CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
E4DIR = REPO / "measurement" / "e4_games"
MIDGAME = REPO / "measurement" / "midgame_reference" / "MIDGAME_POSITION_SAMPLE.jsonl"
DISTILL = REPO / "measurement" / "utility_calibration_20260721" / "gen_games_champ125.jsonl"

CORPORA = ["golden", "midgame", "champ", "distill", "e4", "det", "games"]

# Per-worker singletons (forked once, reused for every job).
_KNOBS = None
_PYCFG = None
_RSCFG: dict[int, object] = {}


def _knobs():
    global _KNOBS, _PYCFG
    if _KNOBS is None:
        _KNOBS = T.production_knobs()
        _PYCFG = T.py_config(_KNOBS)
    return _KNOBS


_COLLIDE = False


def _rscfg(sims: int):
    if sims not in _RSCFG:
        _RSCFG[sims] = T.rs_config(sims, _knobs(), collide_check=_COLLIDE)
    return _RSCFG[sims]


# --------------------------------------------------------------------------- #
# Comparison                                                                   #
# --------------------------------------------------------------------------- #
_FIELDS = ("chosen_action", "root_children", "deduped", "root_n", "root_w_bits",
           "root_leaf_value_bits", "root_priors", "node_count")


def compare(py: dict, rs: dict, tag: str) -> list[dict]:
    """Field-by-field; returns a (possibly empty) list of mismatch records."""
    bad = []
    for f in _FIELDS:
        a, b = py[f], rs[f]
        if f in ("root_children", "deduped", "root_priors"):
            a = [tuple(x) for x in a]
            b = [tuple(x) for x in b]
        if a != b:
            rec = {"tag": tag, "field": f}
            if f in ("root_children", "deduped"):
                da = dict((x[0], x[1:]) for x in a)
                db = dict((x[0], x[1:]) for x in b)
                diffs = [(k, da.get(k), db.get(k))
                         for k in sorted(set(da) | set(db)) if da.get(k) != db.get(k)]
                rec["n_actions"] = [len(a), len(b)]
                rec["diffs"] = diffs[:12]
                rec["n_diffs"] = len(diffs)
            elif f == "root_priors":
                diffs = [(x[0], x[1], y[1]) for x, y in zip(a, b) if x != y] \
                    if len(a) == len(b) else []
                rec["n_actions"] = [len(a), len(b)]
                rec["diffs"] = diffs[:12]
                rec["n_diffs"] = len(diffs)
            else:
                rec["python"] = a
                rec["rust"] = b
            bad.append(rec)
    return bad


def _blank() -> dict:
    return {"positions": 0, "sims_run": 0, "checks": 0, "mismatches": [],
            "plies": 0, "games": 0, "py_secs": 0.0, "rs_secs": 0.0,
            "py_sims": 0, "rs_sims": 0, "cache_hits": 0, "cache_collisions": 0}


def _merge(a: dict, b: dict) -> None:
    for k in ("positions", "sims_run", "checks", "plies", "games", "py_sims",
              "rs_sims", "cache_hits", "cache_collisions"):
        a[k] += b[k]
    for k in ("py_secs", "rs_secs"):
        a[k] += b[k]
    a["mismatches"].extend(b["mismatches"])


# --------------------------------------------------------------------------- #
# Jobs                                                                         #
# --------------------------------------------------------------------------- #
def _permute_deck(board, ms, perm_seed: int) -> int:
    """Install the SAME deck permutation on both legs. Returns the deck length.

    The permutation is over indices (not a `shuffle` of tile objects) so the two
    legs are driven from ONE list; the descriptions are cross-checked first, so a
    deck-order mismatch is caught here rather than surfacing as a search
    divergence 400 sims later.
    """
    src = list(board.state.deck)
    py_desc = [t.description for t in src]
    rs_desc = list(ms.unseen_deck())
    if py_desc != rs_desc:
        raise AssertionError(
            f"unseen deck disagrees before permutation: "
            f"py[:5]={py_desc[:5]} rs[:5]={rs_desc[:5]} (len {len(py_desc)}/{len(rs_desc)})")
    if not src:
        return 0
    perm = list(range(len(src)))
    random.Random(perm_seed).shuffle(perm)
    board.state.deck[:] = [src[i] for i in perm]
    board._str_repr_cache = None
    ms.set_unseen_deck([py_desc[i] for i in perm])
    return len(src)


def _position_job(job: dict) -> dict:
    """Search ONE position on both legs at each requested sim level."""
    out = _blank()
    _knobs()
    seed, actions = int(job["deck_seed"]), [int(a) for a in job["actions"]]
    for ply in job["plies"]:
        game, board = T.py_state(seed, actions, ply)
        ms = T.rs_state(seed, actions, ply)
        if board.state.is_terminated():
            continue
        if job.get("perm_seed") is not None:
            _permute_deck(board, ms, int(job["perm_seed"]) + ply)
        # Guard the substrate before grading the search: a repr/deck disagreement
        # would otherwise be reported as a PUCT divergence.
        if game.string_representation(board) != ms.string_repr():
            out["mismatches"].append({"tag": f"{job['label']}@{ply}",
                                      "field": "string_representation"})
            continue
        for sims in job["sims"]:
            tag = f"{job['label']}@{ply}/s{sims}"
            t0 = time.perf_counter()
            py = T.py_search_single(game, board, _PYCFG, sims)
            t1 = time.perf_counter()
            rs = ms.search_single(_rscfg(sims))
            t2 = time.perf_counter()
            out["py_secs"] += t1 - t0
            out["rs_secs"] += t2 - t1
            out["py_sims"] += sims
            out["rs_sims"] += sims
            out["cache_hits"] += int(rs["legal_cache_hits"])
            out["cache_collisions"] += int(rs["legal_cache_collisions"])
            out["positions"] += 1
            out["sims_run"] += sims
            out["checks"] += len(_FIELDS)
            out["mismatches"].extend(compare(py, rs, tag))
        game.clear_caches()
    return out


def _game_job(job: dict) -> dict:
    """A FULL game: both seats searched every ply, the action applied, to end."""
    out = _blank()
    _knobs()
    seed = int(job["deck_seed"])
    sims = int(job["sims"])
    cap = int(job.get("max_plies", 400))
    game, board = T.py_state(seed, [], 0)
    ms = carc_rs.MirrorState.from_seed(str(seed))
    ply = 0
    diverged = False
    while not board.state.is_terminated() and ply < cap:
        if game.string_representation(board) != ms.string_repr():
            out["mismatches"].append({"tag": f"{job['label']}@{ply}",
                                      "field": "string_representation"})
            break
        tag = f"{job['label']}@{ply}/s{sims}"
        t0 = time.perf_counter()
        py = T.py_search_single(game, board, _PYCFG, sims)
        t1 = time.perf_counter()
        rs = ms.search_single(_rscfg(sims))
        t2 = time.perf_counter()
        out["py_secs"] += t1 - t0
        out["rs_secs"] += t2 - t1
        out["py_sims"] += sims
        out["rs_sims"] += sims
        out["cache_hits"] += int(rs["legal_cache_hits"])
        out["cache_collisions"] += int(rs["legal_cache_collisions"])
        bad = compare(py, rs, tag)
        out["mismatches"].extend(bad)
        out["positions"] += 1
        out["plies"] += 1
        out["sims_run"] += sims
        out["checks"] += len(_FIELDS)
        if bad:
            diverged = True
        # Drive BOTH legs with the Python choice so a single divergence does not
        # fork the game and turn one mismatch into a hundred.
        a = int(py["chosen_action"])
        board, _ = game.get_next_state(board, a)
        ms.advance(a)
        ply += 1
    out["games"] = 1
    if not diverged and not board.state.is_terminated() and ply >= cap:
        out["mismatches"].append({"tag": job["label"], "field": "did_not_terminate",
                                  "python": ply, "rust": ply})
    game.clear_caches()
    return out


_DISPATCH = {"position": _position_job, "game": _game_job}


def run_job(job: dict) -> dict:
    try:
        out = _DISPATCH[job["fn"]](job)
    except Exception as exc:  # a crash IS a gate failure; keep the label
        import traceback
        out = _blank()
        out["mismatches"].append({"tag": job.get("label", "?"), "field": "EXCEPTION",
                                  "python": f"{type(exc).__name__}: {exc}",
                                  "rust": traceback.format_exc()[-1500:]})
    out["corpus"] = job["corpus"]
    return out


# --------------------------------------------------------------------------- #
# Corpus -> jobs                                                               #
# --------------------------------------------------------------------------- #
def _plies_for(n: int, stride: int, per_game: int | None) -> list[int]:
    plies = list(range(0, n, max(1, stride)))
    if per_game is not None and len(plies) > per_game:
        step = len(plies) / per_game
        plies = [plies[int(i * step)] for i in range(per_game)]
    return plies


def build_jobs(args) -> list[dict]:
    jobs: list[dict] = []
    sims = list(args.sims)
    corpora = args.corpus

    if "golden" in corpora:
        fx = json.loads(GOLDEN.read_text())
        for seed_s, g in sorted(fx["games"].items(), key=lambda kv: int(kv[0])):
            seed = int(g.get("deck_seed", seed_s))
            acts = [int(a) for a in g["actions"]]
            jobs.append({"fn": "position", "corpus": "golden", "label": f"golden/{seed}",
                         "deck_seed": seed, "actions": acts,
                         "plies": _plies_for(len(acts), args.stride, args.per_game),
                         "sims": sims})

    if "midgame" in corpora:
        recs = [json.loads(l) for l in MIDGAME.open() if l.strip()]
        recs = recs[:args.limit] if args.limit else recs
        for r in recs:
            pre = [int(a) for a in r["prefix"]]
            jobs.append({"fn": "position", "corpus": "midgame",
                         "label": f"midgame/{r['position_id']}",
                         "deck_seed": int(r["source_game_seed"]), "actions": pre,
                         "plies": [len(pre)], "sims": sims})

    if "champ" in corpora:
        recs = [json.loads(l) for l in CHAMP.open() if l.strip()]
        recs = recs[:args.limit] if args.limit else recs
        for g in recs:
            acts = [int(a) for a in g["actions"]]
            jobs.append({"fn": "position", "corpus": "champ",
                         "label": f"champ/{g['game_id']}",
                         "deck_seed": int(g["deck_seed"]), "actions": acts,
                         "plies": _plies_for(len(acts), args.stride, args.per_game),
                         "sims": sims})

    if "distill" in corpora:
        recs = [json.loads(l) for l in DISTILL.open() if l.strip()]
        recs = recs[:args.limit] if args.limit else recs
        for r in recs:
            acts = [int(a) for a in r["actions"]]
            jobs.append({"fn": "position", "corpus": "distill",
                         "label": f"distill/{r['game_id']}",
                         "deck_seed": int(r["deck_seed"]), "actions": acts,
                         "plies": _plies_for(len(acts), args.stride, args.per_game),
                         "sims": sims})

    if "e4" in corpora:
        for path in sorted(E4DIR.glob("*.json")):
            d = json.loads(path.read_text())
            if d.get("schema") != "carcassonne-android-archive/v1":
                raise SystemExit(f"{path}: unexpected schema {d.get('schema')!r}")
            acts = [int(a) for a in d["actions"]]
            jobs.append({"fn": "position", "corpus": "e4", "label": f"e4/{path.stem}",
                         "deck_seed": int(d["deck_seed"]), "actions": acts,
                         "plies": _plies_for(len(acts), args.stride, args.per_game),
                         "sims": sims})

    if "det" in corpora:
        recs = [json.loads(l) for l in CHAMP.open() if l.strip()]
        recs = recs[:args.det_games]
        for i, g in enumerate(recs):
            acts = [int(a) for a in g["actions"]]
            jobs.append({"fn": "position", "corpus": "det",
                         "label": f"det/{g['game_id']}",
                         "deck_seed": int(g["deck_seed"]), "actions": acts,
                         "plies": _plies_for(len(acts), args.stride,
                                             args.per_game or 4),
                         "perm_seed": 900000 + i, "sims": sims})

    if "games" in corpora:
        recs = [json.loads(l) for l in CHAMP.open() if l.strip()][:args.n_games]
        for s in sims:
            for g in recs:
                jobs.append({"fn": "game", "corpus": f"games/s{s}",
                             "label": f"game/{g['deck_seed']}",
                             "deck_seed": int(g["deck_seed"]), "sims": s})

    return jobs


# --------------------------------------------------------------------------- #
# Driver                                                                       #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", action="append", default=None,
                    help=f"one of {CORPORA} or 'all' (repeatable)")
    ap.add_argument("--sims", type=int, action="append", default=None,
                    help="sim budget (repeatable; default 344 and 1376)")
    ap.add_argument("--stride", type=int, default=16, help="plies between searched positions")
    ap.add_argument("--per-game", type=int, default=None, help="cap positions per game")
    ap.add_argument("--limit", type=int, default=None, help="cap records per corpus")
    ap.add_argument("--n-games", type=int, default=20, help="full games (corpus 'games')")
    ap.add_argument("--det-games", type=int, default=12, help="games for corpus 'det'")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--tag", default="main")
    ap.add_argument("--max-mismatch-report", type=int, default=200)
    ap.add_argument("--collide-check", action="store_true",
                    help="DIAGNOSTIC: count legal-move-cache hits whose recomputed "
                         "mask disagrees (two boards sharing one repr key). Costs a "
                         "full enumeration per hit; behaviour is unchanged.")
    a = ap.parse_args(argv)

    a.corpus = a.corpus or ["golden"]
    if "all" in a.corpus:
        a.corpus = list(CORPORA)
    a.sims = a.sims or [344, 1376]

    global _COLLIDE
    _COLLIDE = bool(a.collide_check)
    knobs = T.production_knobs()
    jobs = build_jobs(a)
    if not jobs:
        raise SystemExit("no jobs built")
    print(f"G3: {len(jobs)} jobs over {a.corpus} at sims={a.sims}, "
          f"workers={a.workers}", flush=True)

    total = _blank()
    per_corpus: dict[str, dict] = {}
    t0 = time.perf_counter()
    if a.workers > 1:
        ctx = mp.get_context("fork")
        with ctx.Pool(a.workers) as pool:
            it = pool.imap_unordered(run_job, jobs, chunksize=1)
            for i, out in enumerate(it, 1):
                _merge(total, out)
                _merge(per_corpus.setdefault(out["corpus"], _blank()), out)
                if i % 25 == 0 or i == len(jobs):
                    print(f"  {i}/{len(jobs)} jobs | {total['positions']} searches | "
                          f"{len(total['mismatches'])} mismatches | "
                          f"{time.perf_counter() - t0:.0f}s", flush=True)
    else:
        for i, job in enumerate(jobs, 1):
            out = run_job(job)
            _merge(total, out)
            _merge(per_corpus.setdefault(out["corpus"], _blank()), out)
            if i % 5 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} jobs | {total['positions']} searches | "
                      f"{len(total['mismatches'])} mismatches | "
                      f"{time.perf_counter() - t0:.0f}s", flush=True)
    wall = time.perf_counter() - t0

    ok = not total["mismatches"]
    payload = {
        "gate": "G3/search",
        "verdict": "PASS" if ok else "FAIL",
        "env": environment(),
        "knobs": {k: v for k, v in knobs.items() if k != "leaf_cfg"},
        "args": vars(a),
        "wall_secs": wall,
        "totals": {k: v for k, v in total.items() if k != "mismatches"},
        "n_mismatches": len(total["mismatches"]),
        "mismatches": total["mismatches"][:a.max_mismatch_report],
        "per_corpus": {
            c: {**{k: v for k, v in d.items() if k != "mismatches"},
                "n_mismatches": len(d["mismatches"])}
            for c, d in sorted(per_corpus.items())
        },
        "throughput": {
            "python_sims_per_sec": (total["py_sims"] / total["py_secs"]
                                    if total["py_secs"] else None),
            "rust_sims_per_sec": (total["rs_sims"] / total["rs_secs"]
                                  if total["rs_secs"] else None),
            "speedup": (total["py_secs"] / total["rs_secs"]
                        if total["rs_secs"] else None),
            "note": "in-process, single worker each; sum over all searched positions",
        },
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"G3_search_{a.tag}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))

    tp = payload["throughput"]
    print(f"G3/search: {payload['verdict']}  "
          f"{total['positions']} searches / {total['sims_run']} sims / "
          f"{total['checks']} field checks / {total['games']} full games "
          f"({total['plies']} plies) | {len(total['mismatches'])} mismatches")
    if tp["python_sims_per_sec"]:
        print(f"G3/search: throughput py={tp['python_sims_per_sec']:.0f} sims/s  "
              f"rs={tp['rust_sims_per_sec']:.0f} sims/s  "
              f"({tp['speedup']:.2f}x)")
    if a.collide_check:
        print(f"G3/search: legal-cache collide-check: "
              f"{total['cache_collisions']} disagreeing hits / "
              f"{total['cache_hits']} hits")
    for m in total["mismatches"][:10]:
        print(f"  MISMATCH {m['tag']} [{m['field']}] "
              f"{ {k: v for k, v in m.items() if k not in ('tag', 'field')} }")
    print(f"G3/search: result -> {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
