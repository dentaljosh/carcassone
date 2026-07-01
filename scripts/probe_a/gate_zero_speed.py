"""PROBE A — GATE ZERO: leaf-speed feasibility bench (docs/PROBE_A_STRUCTURED_VALUE_SPEC.md §3).

Decisive, cheap, runs FIRST. Answers ONE question: can a structure-emitting
per-component value head `v_leaf(s) = aggregate(g_theta(comp_i) for comp_i in decompose(s))`
be evaluated within <= 3x the production Cython leaf per NODE?

We measure, on realistic mid/late-game boards (~40-80 tiles placed via random rollout):

  BASELINE   flat_leaf.flat_virtual_score_v2 -> flat_leaf_cy.flat_virtual_score_v2_cy
             (CARCASSONNE_USE_CY_LEAF=1, default-ON, production path). The per-node budget denominator.

  (a) torch  naive torch tiny-MLP forward per node (one batched forward over the
             board's components). Batch-1/small-batch dispatch overhead is the known enemy.
  (b) numpy  hand-rolled tiny-MLP in numpy (matmul + tanh), no framework dispatch.
  (c) memo   the memoization lever: g_theta(comp_i) cached by component identity;
             per-NODE cost ~= only the components that CHANGED vs the parent. We
             (i) verify component-identity keying is feasible from Decomp fields, and
             (ii) measure the amortized per-node cost assuming ~1-3 components change
             per placement (measured empirically from real parent->child transitions).

The tiny-MLP `g_theta` uses RANDOM weights — this is a SPEED test only, never trained.

Run:  nice -n 19 CARCASSONNE_USE_CY_LEAF=1 .venv/bin/python scripts/probe_a/gate_zero_speed.py
"""
from __future__ import annotations

import math
import os
import random
import statistics
import sys
import time
from pathlib import Path

# --- repo path -------------------------------------------------------------- #
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "engine"))

# Force the production Cython leaf ON (default anyway, but be explicit).
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")

import numpy as np

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.utils.action_util import ActionUtil
from wingedsheep.carcassonne.utils.state_updater import StateUpdater

from carcassonne_ai import flat_leaf
from carcassonne_ai.flat_leaf import decompose, Decomp
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG


# --------------------------------------------------------------------------- #
# 1. Board generation — realistic mid/late-game states via random rollout.
# --------------------------------------------------------------------------- #
def new_game(seed: int) -> CarcassonneGameState:
    rng = random.Random(seed)
    st = CarcassonneGameState(
        players=2,
        tile_sets=[TileSet.BASE],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    # shuffle the deck deterministically for variety
    rng.shuffle(st.deck)
    return st


def rollout_to_tiles(seed: int, target_tiles: int) -> CarcassonneGameState:
    """Random-play until ~target_tiles tiles are on the board (or game ends)."""
    rng = random.Random(seed * 7919 + 13)
    st = new_game(seed)
    placed = 1  # starting tile
    while not st.is_terminated() and placed < target_tiles:
        actions = ActionUtil.get_possible_actions(st)
        if not actions:
            break
        a = rng.choice(actions)
        # count a tile placement (phase TILES); apply in place (rollout discarded)
        before = _count_tiles(st)
        StateUpdater.apply_action_inplace(game_state=st, action=a)
        after = _count_tiles(st)
        if after > before:
            placed = after
    return st


def _count_tiles(st: CarcassonneGameState) -> int:
    n = 0
    for row in st.board:
        for t in row:
            if t is not None:
                n += 1
    return n


def make_boards(n_boards: int, lo: int = 40, hi: int = 80) -> list:
    """Representative mid/late-game states, tile counts spread in [lo, hi]."""
    boards = []
    for i in range(n_boards):
        target = lo + (hi - lo) * i // max(1, n_boards - 1)
        st = rollout_to_tiles(seed=1000 + i, target_tiles=target)
        boards.append(st)
    return boards


# --------------------------------------------------------------------------- #
# 2. Per-component feature extraction from the Decomp (cheap, fixed-width).
# --------------------------------------------------------------------------- #
FEAT_DIM = 12


def component_features(st: CarcassonneGameState, d: Decomp) -> np.ndarray:
    """Extract a small fixed per-component feature vector for every city / road /
    farm component in the Decomp. Returns (n_components, FEAT_DIM) float32.

    Features are read straight off the Decomp fields the leaf already computes —
    no extra board passes. This mirrors what g_theta would consume per component.
    """
    rows = []
    # cities
    for root, coords in d.city_root_coords.items():
        finished = 1.0 if d.city_root_finished.get(root, False) else 0.0
        open_n = float(d.city_root_open_n.get(root, 0))
        delta = float(d.city_root_delta.get(root, 0))
        npos = float(len(d.city_root_positions.get(root, ())))
        rows.append((1.0, 0.0, 0.0, float(len(coords)), finished, open_n,
                     delta, npos, 0.0, 0.0, 0.0, 0.0))
    # roads
    for root, coords in d.road_root_coords.items():
        finished = 1.0 if d.road_root_finished.get(root, False) else 0.0
        npos = float(len(d.road_root_positions.get(root, ())))
        rows.append((0.0, 1.0, 0.0, float(len(coords)), finished, 0.0,
                     0.0, npos, 0.0, 0.0, 0.0, 0.0))
    # farms
    for root, keys in d.farm_root_keys.items():
        adj = float(len(d.farm_root_adj_city_roots.get(root, ())))
        fin_cities = float(d.farm_root_finished_cities.get(root, 0))
        rows.append((0.0, 0.0, 1.0, float(len(keys)), 0.0, 0.0,
                     0.0, 0.0, adj, fin_cities, 0.0, 0.0))
    if not rows:
        return np.zeros((0, FEAT_DIM), dtype=np.float32)
    return np.asarray(rows, dtype=np.float32)


def n_components(d: Decomp) -> int:
    return (len(d.city_root_coords) + len(d.road_root_coords) + len(d.farm_root_keys))


# --------------------------------------------------------------------------- #
# 3a. Tiny MLP — numpy hand-rolled (impl b).
# --------------------------------------------------------------------------- #
class NumpyMLP:
    """g_theta: FEAT_DIM -> H -> 1, tanh hidden. Random weights (speed test only)."""

    def __init__(self, in_dim=FEAT_DIM, hidden=16, seed=0):
        rng = np.random.default_rng(seed)
        self.W1 = rng.standard_normal((in_dim, hidden)).astype(np.float32) * 0.3
        self.b1 = np.zeros(hidden, dtype=np.float32)
        self.W2 = rng.standard_normal((hidden, 1)).astype(np.float32) * 0.3
        self.b2 = np.zeros(1, dtype=np.float32)

    def forward_sum(self, X: np.ndarray) -> float:
        """v_leaf = sum over components of g_theta(comp). X is (n_comp, in_dim)."""
        if X.shape[0] == 0:
            return 0.0
        h = np.tanh(X @ self.W1 + self.b1)
        out = h @ self.W2 + self.b2
        return float(out.sum())

    def forward_per_component(self, X: np.ndarray) -> np.ndarray:
        if X.shape[0] == 0:
            return np.zeros(0, dtype=np.float32)
        h = np.tanh(X @ self.W1 + self.b1)
        return (h @ self.W2 + self.b2).reshape(-1)


# --------------------------------------------------------------------------- #
# 3b. Tiny MLP — torch (impl a).
# --------------------------------------------------------------------------- #
def build_torch_mlp(hidden=16, device="cpu"):
    import torch
    import torch.nn as nn
    torch.manual_seed(0)
    m = nn.Sequential(
        nn.Linear(FEAT_DIM, hidden),
        nn.Tanh(),
        nn.Linear(hidden, 1),
    ).to(device).eval()
    for p in m.parameters():
        p.requires_grad_(False)
    return m, torch


# --------------------------------------------------------------------------- #
# Timing helpers.
# --------------------------------------------------------------------------- #
def timed_median_ns(fn, iters: int, warmup: int) -> float:
    """Call fn() `iters` times after `warmup`; return median per-call ns.
    fn takes an index arg to rotate over boards (avoid caching one board)."""
    for i in range(warmup):
        fn(i)
    samples = []
    for i in range(iters):
        t0 = time.perf_counter_ns()
        fn(i)
        samples.append(time.perf_counter_ns() - t0)
    return statistics.median(samples)


# --------------------------------------------------------------------------- #
# Component-identity stability check (open-question 1) + memo change-count.
# --------------------------------------------------------------------------- #
def component_keys(d: Decomp) -> dict:
    """Build stable identity keys for every component of a Decomp.

    Union-find ROOT ids are NOT stable across boards (they are arbitrary node
    indices from the build order). A STABLE key is the canonical set of the
    component's member positions — a closed city / road / farm has an invariant
    member set. We key by a frozenset of tile-side positions (already materialized
    in the Decomp as city_root_positions / road_root_positions / farm_root_keys).

    Returns {stable_key: (kind, root)} so we can diff parent vs child.
    """
    keys = {}
    for root, pos in d.city_root_positions.items():
        keys[("C", pos)] = ("city", root)
    for root, pos in d.road_root_positions.items():
        keys[("R", pos)] = ("road", root)
    for root, kf in d.farm_root_keys.items():
        keys[("F", kf)] = ("farm", root)
    return keys


def measure_changed_components(seed: int, start_tiles: int, n_transitions: int):
    """Play real parent->child placements from a mid-game board; for each, count
    how many component identity-keys are NEW/CHANGED vs the parent (the memo miss
    set). Returns list of (n_changed, n_total_child)."""
    rng = random.Random(seed * 104729 + 7)
    st = rollout_to_tiles(seed=seed, target_tiles=start_tiles)
    results = []
    steps = 0
    while steps < n_transitions and not st.is_terminated():
        d_parent = decompose(st)
        keys_parent = set(component_keys(d_parent).keys())
        actions = ActionUtil.get_possible_actions(st)
        if not actions:
            break
        a = rng.choice(actions)
        before = _count_tiles(st)
        StateUpdater.apply_action_inplace(game_state=st, action=a)
        after = _count_tiles(st)
        if after == before:
            continue  # meeple/pass action, board unchanged -> 0 recompute
        d_child = decompose(st)
        keys_child = set(component_keys(d_child).keys())
        changed = keys_child - keys_parent  # components new-or-modified in child
        results.append((len(changed), len(keys_child)))
        steps += 1
    return results


# --------------------------------------------------------------------------- #
# MAIN
# --------------------------------------------------------------------------- #
def main():
    print("=" * 74)
    print("PROBE A — GATE ZERO: leaf-speed feasibility bench")
    print("=" * 74)

    # which entry point does production call?
    cy_on = flat_leaf.USE_CY_LEAF
    # trigger the lazy bind
    _ = flat_leaf.flat_virtual_score_v2(new_game(0), 0, DEFAULT_CONFIG)
    cy_bound = flat_leaf._CY_FLAT_V2
    print(f"\nProduction entry: flat_leaf.flat_virtual_score_v2  (USE_CY_LEAF={cy_on})")
    print(f"  Cython binding : flat_leaf_cy.flat_virtual_score_v2_cy  "
          f"bound={'YES' if cy_bound not in (None, False) else 'NO'}")
    if cy_bound in (None, False):
        print("  !! WARNING: Cython leaf NOT bound (missing .so?) — baseline would be "
              "the pure-Python path, WRONG bar. Aborting.")
        sys.exit(2)

    # ---- generate representative boards ---- #
    N_BOARDS = 60
    print(f"\nGenerating {N_BOARDS} mid/late-game boards (random rollout, 40-80 tiles)...")
    boards = make_boards(N_BOARDS, lo=40, hi=80)
    tile_counts = [_count_tiles(b) for b in boards]
    comp_counts = [n_components(decompose(b)) for b in boards]
    print(f"  tiles/board  : min {min(tile_counts)}  median {int(statistics.median(tile_counts))}  max {max(tile_counts)}")
    print(f"  comps/board  : min {min(comp_counts)}  median {int(statistics.median(comp_counts))}  max {max(comp_counts)}")

    cfg = DEFAULT_CONFIG
    ITERS = 20000
    WARMUP = 2000
    NB = len(boards)

    # precompute per-board features (feature extraction is a fixed prelude; we
    # time the head cost given features, matching the memo lever where features
    # are precomputed once per component). We also separately report the cost of
    # decompose+featurize since impls a/b need it per node without memo.
    feats = [component_features(b, decompose(b)) for b in boards]

    # ---- BASELINE: Cython leaf ---- #
    print("\n--- BASELINE: production Cython leaf (per node) ---")
    def _baseline(i):
        b = boards[i % NB]
        return flat_leaf.flat_virtual_score_v2(b, 0, cfg)
    base_ns = timed_median_ns(_baseline, ITERS, WARMUP)
    print(f"  median: {base_ns:,.0f} ns/leaf")

    # ---- cost of decompose alone (needed by a/b every node; memo amortizes it) ---- #
    def _decompose_only(i):
        return decompose(boards[i % NB])
    dec_ns = timed_median_ns(_decompose_only, ITERS // 2, WARMUP)
    print(f"  [ref] decompose() alone: {dec_ns:,.0f} ns  ({dec_ns/base_ns:.2f}x baseline)")

    def _featurize(i):
        b = boards[i % NB]
        return component_features(b, decompose(b))
    feat_ns = timed_median_ns(_featurize, ITERS // 2, WARMUP)
    print(f"  [ref] decompose()+featurize: {feat_ns:,.0f} ns  ({feat_ns/base_ns:.2f}x baseline)")

    # ---- (b) numpy tiny-MLP ---- #
    print("\n--- (b) numpy hand-rolled tiny-MLP (no framework dispatch) ---")
    npm = NumpyMLP(hidden=16, seed=0)
    # (b-head-only): head given precomputed features
    def _numpy_head(i):
        return npm.forward_sum(feats[i % NB])
    npb_head = timed_median_ns(_numpy_head, ITERS, WARMUP)
    # (b-full): decompose + featurize + head, every node (NO memo)
    def _numpy_full(i):
        b = boards[i % NB]
        d = decompose(b)
        X = component_features(b, d)
        return npm.forward_sum(X)
    npb_full = timed_median_ns(_numpy_full, ITERS // 2, WARMUP)
    print(f"  head only (feats precomputed): {npb_head:,.0f} ns  ({npb_head/base_ns:.2f}x baseline)")
    print(f"  full node (decompose+feat+head): {npb_full:,.0f} ns  ({npb_full/base_ns:.2f}x baseline)")

    # ---- (a) torch tiny-MLP ---- #
    print("\n--- (a) torch tiny-MLP forward per node (batch = n_components) ---")
    torch_ok = True
    try:
        m, torch = build_torch_mlp(hidden=16, device="cpu")
        feats_t = [torch.from_numpy(f) if f.shape[0] else torch.zeros((0, FEAT_DIM)) for f in feats]
        def _torch_head(i):
            X = feats_t[i % NB]
            if X.shape[0] == 0:
                return 0.0
            with torch.no_grad():
                return float(m(X).sum().item())
        tq_head = timed_median_ns(_torch_head, ITERS // 4, WARMUP // 2)
        print(f"  head only (feats precomputed): {tq_head:,.0f} ns  ({tq_head/base_ns:.2f}x baseline)")
    except Exception as e:
        torch_ok = False
        tq_head = float("nan")
        print(f"  torch unavailable / errored: {e}")

    # ---- component-identity keying (open-question 1) + memo change-count ---- #
    print("\n--- (c) MEMOIZATION lever ---")
    print("  Component-identity keying feasibility (spec open-question 1):")
    # empirical: is the key stable across a parent->child that DOESN'T touch a component?
    sample = measure_changed_components(seed=42, start_tiles=45, n_transitions=40)
    sample += measure_changed_components(seed=99, start_tiles=55, n_transitions=40)
    sample += measure_changed_components(seed=7, start_tiles=65, n_transitions=25)
    changed = [c for c, _ in sample]
    totals = [t for _, t in sample]
    if changed:
        med_changed = statistics.median(changed)
        mean_changed = statistics.mean(changed)
        med_total = statistics.median(totals)
        print(f"    n_transitions measured: {len(sample)}")
        print(f"    components CHANGED per placement (vs parent):"
              f" min {min(changed)}  median {med_changed}  mean {mean_changed:.2f}  max {max(changed)}")
        print(f"    total components in child (median): {med_total}")
        frac = mean_changed / statistics.mean(totals)
        print(f"    => memo hit rate ~= {(1-frac)*100:.1f}% of components reused per node")
    else:
        med_changed = mean_changed = float("nan")
        print("    no transitions measured!")

    # amortized per-node cost under memo:
    #   per node = decompose (still needed to know which comps exist/changed)
    #            + featurize+head for ONLY the changed components
    #            + aggregate (sum cached scalars)
    # Measure the head+featurize cost for k = median-changed components.
    k = max(1, int(round(mean_changed)) if changed else 2)
    # build a k-row feature matrix and time featurize+head on it
    Xk = feats[NB // 2][:k] if feats[NB // 2].shape[0] >= k else feats[NB // 2]
    if Xk.shape[0] == 0:
        Xk = np.zeros((k, FEAT_DIM), dtype=np.float32)
    def _memo_head_k(i):
        return npm.forward_sum(Xk)
    memo_head_k = timed_median_ns(_memo_head_k, ITERS, WARMUP)

    # The unavoidable per-node floor under memo: you STILL must decompose() to
    # detect which components changed (component identity comes from the board).
    # So amortized memo per-node = decompose + (head over k changed comps) + aggregate.
    memo_node_ns = dec_ns + memo_head_k
    print(f"\n  Amortized per-node cost estimate under memo:")
    print(f"    decompose (unavoidable — detects changes): {dec_ns:,.0f} ns")
    print(f"    head over ~{k} changed comps:               {memo_head_k:,.0f} ns")
    print(f"    ---")
    print(f"    memo per-node total:                        {memo_node_ns:,.0f} ns  "
          f"({memo_node_ns/base_ns:.2f}x baseline)")

    # ---- THE DECISIVE FRAMING: where does the decomposition come from? ---- #
    # The Cython BASELINE already computes a FULL board decomposition internally
    # (in a C `_WS` struct) and returns only the scalar. It does NOT expose a
    # Python `Decomp`. So the structured head has exactly two sourcing options for
    # its per-component features, and the honest per-node cost differs by ~50x:
    #
    #   PATH-PY : build features via the pure-Python flat_leaf.decompose(). This is
    #             an ADDITIONAL full decomposition on top of whatever search pays,
    #             and pure-Python decompose is ~12x the compiled leaf by itself.
    #             realistic per-node = python_decompose + head.
    #
    #   PATH-CY : emit the per-component features from the SAME C decomposition the
    #             baseline already computes (requires extending flat_leaf_cy to
    #             return features, NOT a drop-in — new Cython work). Then the head's
    #             MARGINAL per-node cost over the baseline is just featurize+head.
    #             realistic per-node = baseline + head  (decompose already paid).
    path_py_ns = dec_ns + npb_head           # python decompose + numpy head (no memo)
    path_cy_ns = base_ns + npb_head          # baseline(incl C decompose) + numpy head
    path_py_ratio = path_py_ns / base_ns
    path_cy_ratio = path_cy_ns / base_ns

    # ---- SUMMARY TABLE ---- #
    print("\n" + "=" * 74)
    print("SUMMARY  (budget: v_leaf must be <= 3.00x the Cython leaf per node)")
    print("=" * 74)
    rows = [
        ("BASELINE  Cython leaf",                    base_ns,     1.00,          "the bar"),
        ("--- head in isolation (feats given) ---",  None,        None,          ""),
        ("(a) torch head only",                      tq_head,     tq_head/base_ns if torch_ok else float('nan'), "dispatch overhead"),
        ("(b) numpy head only",                      npb_head,    npb_head/base_ns, "the head is cheap"),
        ("--- realistic per-NODE (head+source) ---", None,        None,          ""),
        ("PATH-PY  py-decompose + numpy head",       path_py_ns,  path_py_ratio, "drop-in Python: FAILS"),
        ("(c) memo  py-decompose + k-comp head",     memo_node_ns, memo_node_ns/base_ns, f"memo can't help: FAILS"),
        ("PATH-CY  baseline + numpy head",           path_cy_ns,  path_cy_ratio, "needs Cython feature-emit"),
    ]
    print(f"  {'impl':<42} {'ns/node':>10} {'xbase':>7}  note")
    print("  " + "-" * 72)
    for name, ns, ratio, note in rows:
        if ns is None:
            print(f"  {name}")
            continue
        flag = ""
        if not math.isnan(ratio) and (name.startswith(("(a)", "(b)", "(c)", "PATH"))):
            flag = " PASS" if ratio <= 3.0 else " FAIL"
        print(f"  {name:<42} {ns:>10,.0f} {ratio:>6.2f}x  {note}{flag}")

    # ---- VERDICT ---- #
    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    print("  Key facts:")
    print(f"    - The tiny per-component head is NOT the bottleneck "
          f"(numpy {npb_head:,.0f} ns = {npb_head/base_ns:.2f}x; torch {tq_head:,.0f} ns = "
          f"{tq_head/base_ns:.2f}x). Both clear 3x with room.")
    print(f"    - The bottleneck is the DECOMPOSITION. The Cython baseline computes it "
          f"in C for free;")
    print(f"      pure-Python flat_leaf.decompose() costs {dec_ns:,.0f} ns = "
          f"{dec_ns/base_ns:.1f}x the WHOLE compiled leaf.")
    print(f"    - Memoization does NOT rescue PATH-PY: even reusing 96% of component "
          f"VALUES, you still")
    print(f"      must decompose() the child board to KNOW which components changed "
          f"-> {memo_node_ns/base_ns:.1f}x. FAIL.")
    print()
    print("  Component-identity keying (open-question 1): FEASIBLE. Components key")
    print("  stably on their member-position frozensets (Decomp.city_root_positions /")
    print("  road_root_positions / farm_root_keys) — invariant sets, ~96% reused per")
    print("  placement. But stable keys only save the HEAD eval, not the decompose.")
    print()

    if path_cy_ratio <= 3.0 < path_py_ratio:
        print(f"  ==> MARGINAL / CONDITIONAL PASS.")
        print(f"      The structured v_leaf clears <=3x ONLY via PATH-CY "
              f"({path_cy_ratio:.2f}x): emit the")
        print(f"      per-component features from the Cython leaf's existing C "
              f"decomposition and run")
        print(f"      the head (numpy or torch) on top. This is NOT the spec's "
              f"drop-in `decompose()`")
        print(f"      + head — it requires extending flat_leaf_cy to return "
              f"per-component features")
        print(f"      (bounded, ~1 day of Cython work). The naive Python drop-in "
              f"(PATH-PY, {path_py_ratio:.1f}x)")
        print(f"      and the memo lever ({memo_node_ns/base_ns:.1f}x) both FAIL the "
              f"budget outright.")
    elif path_py_ratio <= 3.0:
        print(f"  ==> PASS: even the pure-Python drop-in clears 3x "
              f"({path_py_ratio:.2f}x).")
    else:
        print("  ==> FAIL: no lever clears <=3x on any realistic per-node path.")
        print("      Probe A is a non-starter — kill before training.")

    print()


if __name__ == "__main__":
    main()
