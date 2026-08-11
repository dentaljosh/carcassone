#!/usr/bin/env python3
"""Stage 4c probe: is numba-compiling `_label_components` worth it at the leaf's
actual problem sizes?

_label_components (union-find) is only ~10% of decompose; numba could shrink it,
but at these small n (hundreds of nodes/edges) the per-call np.array conversion
overhead may eat the win. This MEASURES it rather than assuming, and gates the
compiled kernel against the pure-Python one for exact-partition equality.

Two phases (decoupled because numba lives in an ISOLATED venv with no torch):
  --capture : run under the SHARED venv (has torch/engine). Plays real games,
              records every (n, edges_u, edges_v) _label_components is called with
              (city/road/farm union-finds), dumps to a corpus file.
  (default) : run under the ISOLATED numba venv. Loads the corpus, benches
              pure-Python _label_components vs an @njit kernel (with AND without
              the list->ndarray conversion), and asserts identical labels.

Usage:
  # 1) capture corpus (shared venv):
  PYTHONPATH=.../src:.../engine CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \
    .venv/bin/python scripts/prototype_numba_labels.py --capture --n 30 --out /tmp/label_corpus.pkl
  # 2) bench (isolated numba venv):
  /tmp/numba_proto_venv/bin/python scripts/prototype_numba_labels.py --corpus /tmp/label_corpus.pkl
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _label_components_py(n, edges_u, edges_v):
    """Pure-Python reference (copy of flat_leaf._label_components)."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(edges_u)):
        a = find(edges_u[i])
        b = find(edges_v[i])
        if a != b:
            parent[a] = b
    return [find(x) for x in range(n)]


def capture(args):
    os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
    os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "engine"))
    import random

    import numpy as np

    from carcassonne_ai import flat_leaf
    from carcassonne_ai.game_wrapper import Game

    corpus = []
    orig = flat_leaf._label_components

    def rec(n, eu, ev):
        corpus.append((n, list(eu), list(ev)))
        return orig(n, eu, ev)

    flat_leaf._label_components = rec
    g = Game()
    for gi in range(args.n):
        random.seed(args.seed + gi)
        b = g.get_init_board()
        plies = 0
        while g.get_game_ended(b, 0) == 0.0 and plies < 400:
            legal = np.flatnonzero(g.get_valid_moves(b))
            if legal.size == 0:
                break
            b, _ = g.get_next_state(b, int(random.choice(legal.tolist())))
            plies += 1
            if plies % 5 == 0 and g.get_game_ended(b, 0) == 0.0 and b.state.players == 2:
                flat_leaf.decompose(b.state)
        if b.state.players == 2:
            flat_leaf.decompose(b.state)
    flat_leaf._label_components = orig
    with open(args.out, "wb") as f:
        pickle.dump(corpus, f)
    ns = [c[0] for c in corpus]
    es = [len(c[1]) for c in corpus]
    print(f"captured {len(corpus)} union-find calls -> {args.out}")
    print(f"  n nodes:  min={min(ns)} max={max(ns)} mean={sum(ns)/len(ns):.1f}")
    print(f"  n edges:  min={min(es)} max={max(es)} mean={sum(es)/len(es):.1f}")
    return 0


def bench(args):
    import numpy as np
    from numba import njit

    @njit(cache=True)
    def _label_numba(n, eu, ev):
        parent = np.arange(n)
        m = eu.shape[0]
        for i in range(m):
            a = eu[i]
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            b = ev[i]
            while parent[b] != b:
                parent[b] = parent[parent[b]]
                b = parent[b]
            if a != b:
                parent[a] = b
        out = np.empty(n, dtype=parent.dtype)
        for x in range(n):
            rr = x
            while parent[rr] != rr:
                parent[rr] = parent[parent[rr]]
                rr = parent[rr]
            out[x] = rr
        return out

    with open(args.corpus, "rb") as f:
        corpus = pickle.load(f)
    print(f"loaded {len(corpus)} union-find calls from {args.corpus}")

    # Pre-convert arrays once, so we can bench kernel-only vs kernel+conversion.
    arrs = [(n, np.asarray(eu, dtype=np.int64), np.asarray(ev, dtype=np.int64))
            for (n, eu, ev) in corpus]

    # warm + correctness gate (exact label equality: same union order -> same roots)
    mism = 0
    for (n, eu, ev), (n2, au, av) in zip(corpus, arrs):
        py = _label_components_py(n, eu, ev)
        nb = list(_label_numba(n, au, av))
        if py != nb:
            mism += 1
    print(f"correctness: {len(corpus)} calls, label mismatches = {mism}")
    if mism:
        print("FAIL: numba kernel labels differ from pure-Python — not a drop-in.")
        return 1

    reps = args.reps

    def best(fn):
        b = float("inf")
        for _ in range(reps):
            t = time.perf_counter()
            fn()
            b = min(b, time.perf_counter() - t)
        return b

    t_py = best(lambda: [_label_components_py(n, eu, ev) for (n, eu, ev) in corpus])
    t_nb_conv = best(lambda: [_label_numba(n, np.asarray(eu, dtype=np.int64),
                                           np.asarray(ev, dtype=np.int64))
                              for (n, eu, ev) in corpus])
    t_nb_pre = best(lambda: [_label_numba(n, au, av) for (n, au, av) in arrs])

    k = len(corpus)
    print("\n=== _label_components: pure-Python vs numba (min of reps) ===")
    print(f"  pure-Python            : {t_py * 1e6 / k:8.3f} us/call  (total {t_py*1e3:.2f} ms)")
    print(f"  numba + list->ndarray  : {t_nb_conv * 1e6 / k:8.3f} us/call  (total {t_nb_conv*1e3:.2f} ms)  "
          f"-> {'FASTER' if t_nb_conv < t_py else 'SLOWER'} ({t_py/t_nb_conv:.2f}x)")
    print(f"  numba (arrays prebuilt): {t_nb_pre * 1e6 / k:8.3f} us/call  (total {t_nb_pre*1e3:.2f} ms)  "
          f"-> {'FASTER' if t_nb_pre < t_py else 'SLOWER'} ({t_py/t_nb_pre:.2f}x)")
    print("\nverdict:")
    if t_nb_conv < t_py:
        print("  numba-the-core is a net win as a drop-in (conversion paid for itself).")
    elif t_nb_pre < t_py:
        print("  numba kernel IS faster, but the list->ndarray conversion eats it at these")
        print("  sizes -> only worth it if decompose keeps data in ndarrays end-to-end")
        print("  (the array-based decompose rewrite), not as a localized drop-in.")
    else:
        print("  numba does NOT help even kernel-only at these sizes (n too small / call")
        print("  overhead dominates) -> compiling _label_components is not the lever.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260609)
    ap.add_argument("--out", default="/tmp/label_corpus.pkl")
    ap.add_argument("--corpus", default="/tmp/label_corpus.pkl")
    ap.add_argument("--reps", type=int, default=8)
    args = ap.parse_args()
    return capture(args) if args.capture else bench(args)


if __name__ == "__main__":
    raise SystemExit(main())
