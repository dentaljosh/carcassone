#!/usr/bin/env python3
"""C6 Stage-0 COST SURFACE bench — the go/no-go gate for the alpha-beta gambit.

Pre-registered by measurement/classical_search/C6_ALPHABETA_DESIGN.md §7 ("surface
cost first"). This bench runs BEFORE the AlphaBetaAgent is built; NOTHING else in
C6 is built until this returns GO. It is a standalone measurement script — nothing
in production imports it, PRODUCTION.yaml / the champion are untouched, it writes
no results.csv row (bench, not an experiment).

What it does (all §7):
  1. Loads the SAME 20 fixed deterministic positions as bench_equal_time_cy.py
     (imports build_positions verbatim so the suite matches byte-for-byte).
  2. Micro-measures, bucketed by ply (early/mid/late): the flat float leaf µs,
     get_next_state µs (the copy-state step — THE number this design leans on),
     get_valid_moves µs (tile vs meeple phase), string_representation+blake2b µs,
     and the legal-count (branching) histogram by phase.
  3. Re-measures the CHAMPION for the equal-wall-clock budget: PUCT float @2750,
     reuse OFF, single-thread median ms/move on the 20-position suite. The champion
     is the PRODUCTION.yaml agent shape — HeuristicPriorAgent with the production
     curve125 leaf (via `import env_preamble`, CL-051), c_puct=1.5, tau_p=5,
     leaf_quantize=float, final_select=visits, value_norm=15, reuse_tree=False
     (= eval_puct_priors._champ_puct_cfg with CHAMP_PUCT_* constants).
  4. Runs a throwaway fixed-depth alpha-beta (Δleaf ordering only, NO TT — the
     floor) AND a TT variant (§3: key = blake2b-128 of the memoized
     string_representation; fail-soft EXACT/LOWER/UPPER). NOT naive negamax (§1):
     values are P0-POV, a node is a max-node iff state.current_player==0 (mirrors
     endgame_solver._value_ab); the horizon may only land on a TILES-phase node
     (extend one ply if it hits MEEPLES); terminal nodes return
     flat_base_score(state, 0); WindowOverflowError -> static leaf at that node.
  5. Per position: child-steps + wall to COMPLETE depth d in {2,4,6,8};
     b_eff=(N(d)/N(d-2))**0.5; TT-on vs TT-off step ratio at d=6; cross-parent
     EXACT-hit fraction at d=6 (§3 telemetry); achievable depth = max completed d
     within the champion's measured single-thread budget per position.
  6. Emits ab_cost_raw.json + fills C6_COST_SURFACE.md with the tables + the
     pre-registered verdict (§7): median midgame (plies 30-100) completed depth
     >=6 = GO, <=4 = DECLINE, =5 = GRAY. Prints the verdict to stdout.

Correctness self-test (`--self-test`): a throwaway-αβ terminal-horizon check
against endgame_solver.solve(mode="clairvoyant", alphabeta=True) on near-terminal
positions — guards the mover-convention bug that would make every depth number
garbage. Cheap; run this before funding the full bench.

Usage:
  # correctness self-test only (cheap — RUN THIS to validate the code):
  nice -n 19 .venv/bin/python -u scripts/classical_search/bench_ab_cost.py --self-test

  # the full cost surface (Joshua's launch decision; <1 box-h, single-thread):
  nice -n 19 .venv/bin/python -u scripts/classical_search/bench_ab_cost.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# --- Production leaf env — MUST precede the carcassonne_ai imports ------------ #
# The champion of record (PRODUCTION.yaml) runs the v2.9.2 Bmild_cap8 curve125
# leaf (CL-051, 2026-07-13). `import env_preamble` applies PROD_ENV (curve125,
# cap 8/8, FLAT_LEAF, CY_REPR) via setdefault before carcassonne_ai reads the env.
# env_preamble does NOT set the Cython *leaf* flag or all the BLAS pins, so add
# them here (setdefault — a caller who already exported them wins).
sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))
import env_preamble  # noqa: E402,F401  (applies curve125 PROD_ENV on import)

_EXTRA_ENV = {
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",   # the 23.9 µs Cython float leaf (§7 sanity)
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
for _k, _v in _EXTRA_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import random  # noqa: E402
import socket  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))          # endgame_solver
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))  # bench_equal_time_cy

from carcassonne_ai.action_space import WindowOverflowError  # noqa: E402
from carcassonne_ai.flat_leaf import (  # noqa: E402
    flat_base_score,
    flat_virtual_score_v2_float,
)
from carcassonne_ai.game_wrapper import Board, Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

import endgame_solver as S  # noqa: E402
from bench_equal_time_cy import build_positions, verify_cython_active  # noqa: E402

_TILES = GamePhase.TILES
_MEEPLES = GamePhase.MEEPLES

# Alpha-beta TT fail-soft bound flags — reused verbatim from endgame_solver._value_ab.
_EXACT, _LOWER, _UPPER = 0, 1, 2

# Champion-of-record PUCT config knobs (eval_puct_priors.CHAMP_PUCT_* +
# _champ_puct_cfg; the PRODUCTION.yaml agent, flags OFF, reuse OFF). c_puct/tau_p
# are the production premise values (C6_ALPHABETA_DESIGN §Premise: c_puct=1.5,
# tau_p=5, float leaf, visit-argmax).
CHAMP_C_PUCT = 1.5
CHAMP_TAU_P = 5.0
CHAMP_LEAF_QUANTIZE = "float"
CHAMP_FINAL_SELECT = "visits"
CHAMP_VALUE_NORM = 15.0
CHAMP_C_LCB = 1.0

MID_PLY_LO, MID_PLY_HI = 30, 100  # §7 verdict window (midgame positions)


# --------------------------------------------------------------------------- #
# The throwaway fixed-depth alpha-beta (§1 / §4 — Δleaf ordering; §3 TT variant) #
# --------------------------------------------------------------------------- #
class StepCapExceeded(Exception):
    """Raised when a single fixed-depth search exceeds the child-step safety cap OR
    the per-search wall deadline (keeps the bench bounded; the search is recorded as
    NOT completed for that d — a depth this expensive is beyond the champion budget
    anyway, so it cannot affect the achievable-depth verdict)."""


class AlphaBeta:
    """Fixed-depth alpha-beta minimax, P0-POV (NOT negamax) — the §1 convention:

      * values are always P0-perspective score diffs (points), P0-POV;
      * a node is a MAX node iff state.current_player == 0 (mirrors
        endgame_solver._value_ab), because a Carcassonne turn is two same-mover
        plies (TILES -> MEEPLES) so per-ply negamax sign-flipping is wrong;
      * terminal nodes (next_tile is None) return the exact flat_base_score;
      * the horizon may only land on a TILES-phase node — if depth runs out at a
        MEEPLES node we recurse one more ply (its children are TILES/terminal),
        the game's 1-ply quiescence;
      * WindowOverflowError deep in a line -> return the static leaf at that node.

    Ordering (§4 stage 3): step ALL children (get_next_state), sort by child leaf
    (desc for the max-mover, asc for min) — the same signal the champion's priors
    are built from. The floor uses ordering only; the TT variant adds the §3 table
    (key = blake2b-128 of the memoized string_representation, fail-soft flags).
    """

    def __init__(self, game: Game, cfg, use_tt: bool, step_cap: int,
                 deadline: float | None = None):
        self.game = game
        self.cfg = cfg
        self.use_tt = use_tt
        self.step_cap = int(step_cap)
        self.deadline = deadline   # absolute perf_counter time; None = no wall limit
        self.tt: dict[bytes, tuple] = {}
        # Telemetry.
        self.steps = 0            # get_next_state calls == child-steps == THE budget unit
        self.nodes = 0           # interior expansions (analog of _tick)
        self.leaf_evals = 0
        self.tt_probes = 0
        self.tt_hits = 0         # any usable stored entry found (transposition, §3)
        self.tt_exact_hits = 0   # EXACT flag + sufficient stored depth
        self.window_overflows = 0

    # -- primitives ------------------------------------------------------- #
    def _leaf(self, state) -> float:
        self.leaf_evals += 1
        # bag_close=None -> resolves to cfg.bag_close (production path); P0-POV.
        return flat_virtual_score_v2_float(state, 0, self.cfg, None)

    def _key(self, board: Board) -> bytes:
        # §3: blake2b-128 of the memoized string_representation. Under a fixed deck
        # len(deck) (in the sr) pins the ply and the deck suffix is implied, so sr
        # alone is a valid within-game key.
        sr = self.game.string_representation(board)
        return hashlib.blake2b(sr.encode(), digest_size=16).digest()

    # -- root: returns (value, best_action) ------------------------------- #
    def search(self, board: Board, depth: int) -> tuple[float, int]:
        mover = board.state.current_player
        kids = self._ordered_children(board, mover)
        if kids is None:               # WindowOverflow at the root
            return self._leaf(board.state), -1
        if not kids:
            return self._leaf(board.state), -1
        self.nodes += 1
        best = -math.inf if mover == 0 else math.inf
        best_a = kids[0][0]
        alpha, beta = -math.inf, math.inf
        for a, nb, _ in kids:
            v = self._value(nb, depth - 1, alpha, beta)
            if mover == 0:
                if v > best:
                    best, best_a = v, a
                if best > alpha:
                    alpha = best
            else:
                if v < best:
                    best, best_a = v, a
                if best < beta:
                    beta = best
            if alpha >= beta:
                break
        return best, best_a

    # -- interior node ---------------------------------------------------- #
    def _value(self, board: Board, depth: int, alpha: float, beta: float) -> float:
        st = board.state
        if st.next_tile is None:                    # terminal -> exact final score
            return float(flat_base_score(st, 0))
        if depth <= 0 and st.phase == _TILES:       # horizon (TILES-only) -> static leaf
            return self._leaf(st)
        # (depth<=0 at a MEEPLES node falls through -> recurse one more ply = the
        #  meeple-extension; that child is TILES/terminal so it cuts there.)

        a0, b0 = alpha, beta
        key = None
        if self.use_tt:
            self.tt_probes += 1
            key = self._key(board)
            ent = self.tt.get(key)
            if ent is not None:
                val, flag, sdepth, _sa = ent
                if sdepth >= depth:
                    self.tt_hits += 1
                    if flag == _EXACT:
                        self.tt_exact_hits += 1
                        return val
                    if flag == _LOWER and val > alpha:
                        alpha = val
                    elif flag == _UPPER and val < beta:
                        beta = val
                    if alpha >= beta:
                        return val

        mover = st.current_player
        kids = self._ordered_children(board, mover)
        if kids is None or not kids:                # WindowOverflow / no legal -> static leaf
            return self._leaf(st)
        self.nodes += 1
        best = -math.inf if mover == 0 else math.inf
        best_a = kids[0][0]
        for a, nb, _ in kids:
            v = self._value(nb, depth - 1, alpha, beta)
            if mover == 0:
                if v > best:
                    best, best_a = v, a
                if best > alpha:
                    alpha = best
            else:
                if v < best:
                    best, best_a = v, a
                if best < beta:
                    beta = best
            if alpha >= beta:
                break

        if self.use_tt:
            flag = _UPPER if best <= a0 else (_LOWER if best >= b0 else _EXACT)
            old = self.tt.get(key)
            if old is None or depth >= old[2]:       # depth-preferred replacement (§3)
                self.tt[key] = (best, flag, depth, best_a)
        return best

    def _ordered_children(self, board: Board, mover: int):
        """Step every legal child, sort by child leaf (desc max / asc min). Returns
        a list[(action, child_board, child_leaf)] or None on a root WindowOverflow."""
        try:
            legal = np.flatnonzero(self.game.get_valid_moves(board))
        except WindowOverflowError:
            self.window_overflows += 1
            return None
        kids = []
        for a in legal:
            try:
                nb, _ = self.game.get_next_state(board, int(a))
            except WindowOverflowError:
                self.window_overflows += 1
                continue
            self.steps += 1
            if self.steps > self.step_cap:
                raise StepCapExceeded
            if self.deadline is not None and (self.steps & 0x7FF) == 0 \
                    and time.perf_counter() > self.deadline:
                raise StepCapExceeded   # wall guard (search recorded NOT-completed)
            kids.append((int(a), nb, self._leaf(nb.state)))
        kids.sort(key=lambda t: t[2], reverse=(mover == 0))
        return kids


def plain_minimax(game: Game, board: Board, depth: int, cfg) -> float:
    """No-pruning, no-TT reference with the SAME horizon/leaf/convention — the
    oracle the pruned AlphaBeta must match (self-test only)."""
    st = board.state
    if st.next_tile is None:
        return float(flat_base_score(st, 0))
    if depth <= 0 and st.phase == _TILES:
        return float(flat_virtual_score_v2_float(st, 0, cfg, None))
    try:
        legal = np.flatnonzero(game.get_valid_moves(board))
    except WindowOverflowError:
        return float(flat_virtual_score_v2_float(st, 0, cfg, None))
    vals = []
    for a in legal:
        try:
            nb, _ = game.get_next_state(board, int(a))
        except WindowOverflowError:
            continue
        vals.append(plain_minimax(game, nb, depth - 1, cfg))
    if not vals:
        return float(flat_virtual_score_v2_float(st, 0, cfg, None))
    return max(vals) if st.current_player == 0 else min(vals)


# --------------------------------------------------------------------------- #
# Champion budget re-measure (§7, item 3)                                       #
# --------------------------------------------------------------------------- #
def _champ_cfg() -> HeuristicPriorConfig:
    return HeuristicPriorConfig(
        c_puct=CHAMP_C_PUCT, tau_p=CHAMP_TAU_P, leaf_quantize=CHAMP_LEAF_QUANTIZE,
        final_select=CHAMP_FINAL_SELECT, value_norm=CHAMP_VALUE_NORM,
        c_lcb=CHAMP_C_LCB, reuse_tree=False, root_select="puct",
        leaf_cfg=DEFAULT_CONFIG,
    )


def bench_champion(positions, sims: int) -> list[float]:
    cfg = _champ_cfg()
    ms = []
    for p in positions:
        a = HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                simulations=sims, seed=1)
        a.clear()
        t0 = time.perf_counter()
        a.best_action(p["board"])
        ms.append((time.perf_counter() - t0) * 1e3)
    return ms


# --------------------------------------------------------------------------- #
# Micro-measurements (§7, item 2)                                               #
# --------------------------------------------------------------------------- #
def _median_us(fn, iters: int) -> float:
    xs = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t0) * 1e6)
    return float(np.median(xs))


def _first_meeple_child(game: Game, board: Board):
    """Step `board` (a TILES node) once so we have a MEEPLES-phase board to time."""
    legal = np.flatnonzero(game.get_valid_moves(board))
    for a in legal:
        nb, _ = game.get_next_state(board, int(a))
        if nb.state.phase == _MEEPLES:
            return nb
    return None


def micro_measure(board: Board, iters: int) -> dict:
    g = Game(enable_legal_moves_cache=False)  # no cache -> honest per-call cost
    out = {"phase": board.state.phase.value}

    out["leaf_us"] = round(
        _median_us(lambda: flat_virtual_score_v2_float(board.state, 0, DEFAULT_CONFIG, None), iters), 3)

    legal = np.flatnonzero(g.get_valid_moves(board))
    a0 = int(legal[0])
    out["get_next_state_us"] = round(_median_us(lambda: g.get_next_state(board, a0), iters), 3)

    # get_valid_moves: the current phase + (if the current node is TILES) a MEEPLES child.
    cur_phase = board.state.phase.value
    out[f"get_valid_moves_{cur_phase}_us"] = round(_median_us(lambda: g.get_valid_moves(board), iters), 3)
    if board.state.phase == _TILES:
        mb = _first_meeple_child(g, board)
        if mb is not None:
            out["get_valid_moves_meeples_us"] = round(_median_us(lambda: g.get_valid_moves(mb), iters), 3)

    def _sr_blake():
        board._str_repr_cache = None                 # measure the UNCACHED cost
        sr = g.string_representation(board)
        hashlib.blake2b(sr.encode(), digest_size=16).digest()
    out["string_repr_plus_blake2b_us"] = round(_median_us(_sr_blake, iters), 3)
    board._str_repr_cache = None
    return out


def branching_hist(game: Game, board: Board, depth: int, node_cap: int) -> dict:
    """Collect (phase, n_legal) over a shallow full expansion (branching stats)."""
    counts = {"tiles": [], "meeples": []}
    seen = [0]

    def walk(b: Board, d: int):
        if seen[0] >= node_cap or b.state.next_tile is None:
            return
        try:
            legal = np.flatnonzero(game.get_valid_moves(b))
        except WindowOverflowError:
            return
        counts[b.state.phase.value].append(int(len(legal)))
        seen[0] += 1
        if d <= 0:
            return
        for a in legal:
            if seen[0] >= node_cap:
                break
            try:
                nb, _ = game.get_next_state(b, int(a))
            except WindowOverflowError:
                continue
            walk(nb, d - 1)

    walk(board, depth)
    return counts


def _hist_summary(vals: list[int]) -> dict:
    if not vals:
        return {"n": 0}
    a = np.asarray(vals)
    return {"n": int(a.size), "min": int(a.min()), "p50": int(np.percentile(a, 50)),
            "mean": round(float(a.mean()), 1), "p95": int(np.percentile(a, 95)),
            "max": int(a.max())}


# --------------------------------------------------------------------------- #
# alpha-beta cost surface (§7, items 4-5)                                       #
# --------------------------------------------------------------------------- #
def run_fixed_depth(game: Game, board: Board, depth: int, use_tt: bool,
                    step_cap: int, max_secs: float | None = None) -> dict:
    t0 = time.perf_counter()
    deadline = (t0 + max_secs) if max_secs else None
    ab = AlphaBeta(game, DEFAULT_CONFIG, use_tt=use_tt, step_cap=step_cap, deadline=deadline)
    try:
        val, act = ab.search(board, depth)
        completed = True
    except StepCapExceeded:
        val, act, completed = float("nan"), -1, False
    wall_ms = (time.perf_counter() - t0) * 1e3
    return {
        "depth": depth, "completed": completed, "value": None if math.isnan(val) else round(val, 4),
        "best_action": act, "steps": ab.steps, "nodes": ab.nodes,
        "leaf_evals": ab.leaf_evals, "wall_ms": round(wall_ms, 1),
        "tt_probes": ab.tt_probes, "tt_hits": ab.tt_hits,
        "tt_exact_hits": ab.tt_exact_hits, "window_overflows": ab.window_overflows,
    }


def ab_cost_for_position(board: Board, depths, step_cap: int, max_secs: float,
                         champ_ms: float, escalate_mult: float) -> dict:
    """Fixed-depth alpha-beta at each d, TT-off (floor) and TT-on. Escalation stops
    once a depth fails to complete OR a completed depth's wall already exceeds
    `escalate_mult` × the champion budget (deeper d is beyond budget -> cannot be
    achievable, and its b_eff adds nothing the shallower rungs did not; this bounds
    the deep-search cost so the whole bench stays <1 box-h)."""
    game = Game(enable_legal_moves_cache=False)   # unbounded cache would OOM the search
    res = {"tt_off": {}, "tt_on": {}}
    for variant, use_tt in (("tt_off", False), ("tt_on", True)):
        for d in depths:
            r = run_fixed_depth(game, board, d, use_tt, step_cap, max_secs)
            res[variant][d] = r
            if not r["completed"]:
                break
            if r["wall_ms"] > escalate_mult * champ_ms:
                break
    # b_eff per completed adjacent pair (steps-based) for the TT-off floor.
    for variant in ("tt_off", "tt_on"):
        beff = {}
        for d in depths:
            prev = d - 2
            a, b = res[variant].get(prev), res[variant].get(d)
            if a and b and a["completed"] and b["completed"] and a["steps"] > 0:
                beff[d] = round(math.sqrt(b["steps"] / a["steps"]), 3)
        res[variant + "_b_eff"] = beff
    return res


def achievable_depth(pos_res: dict, depths, champ_ms: float, variant: str) -> int:
    """Max completed d whose wall_ms <= the champion's per-position budget."""
    best = 0
    for d in depths:
        r = pos_res[variant].get(d)
        if r and r["completed"] and r["wall_ms"] <= champ_ms:
            best = d
        else:
            break
    return best


def _median_int(xs):
    return int(np.median(xs)) if xs else 0


# --------------------------------------------------------------------------- #
# Correctness self-test (mover-convention guard)                                #
# --------------------------------------------------------------------------- #
def _near_terminal(seed: int, k_target: int):
    """Play a deterministic random game; stop at the first TILES-phase, non-terminal
    node with `k_target` tiles remaining (in-hand + deck)."""
    random.seed(seed)
    g = Game(enable_legal_moves_cache=False)
    b = g.get_init_board()
    while b.state.next_tile is not None:
        if b.state.phase == _TILES and (1 + len(b.state.deck)) == k_target:
            return g, b
        legal = np.flatnonzero(g.get_valid_moves(b))
        b, _ = g.get_next_state(b, int(random.choice(legal)))
    return None, None


def _play_to_terminal(g: Game, board: Board) -> Board:
    b = board
    random.seed(12345)
    while b.state.next_tile is not None:
        legal = np.flatnonzero(g.get_valid_moves(b))
        b, _ = g.get_next_state(b, int(random.choice(legal)))
    return b


def self_test() -> bool:
    print("[self-test] mover-convention guard: throwaway αβ vs "
          "endgame_solver.solve(clairvoyant, alphabeta=True)\n")
    ok = True
    cases = [(9_200_001, 2), (9_200_017, 3)]
    BIG = 1_000_000  # effectively unlimited depth -> terminal-only horizon
    CAP = 50_000_000

    for seed, k in cases:
        g, b = _near_terminal(seed, k)
        if b is None:
            print(f"[self-test] seed={seed} k={k}: could not build position — SKIP")
            continue
        gt = S.solve(g, b, mode="clairvoyant", alphabeta=True)
        gt_opt = set(int(a) for a in gt.optimal_actions)

        for use_tt in (False, True):
            ab = AlphaBeta(g, DEFAULT_CONFIG, use_tt=use_tt, step_cap=CAP)
            val, act = ab.search(b, BIG)
            v_ok = (val == gt.value)
            a_ok = (int(act) in gt_opt)
            tag = "TT-on " if use_tt else "TT-off"
            status = "PASS" if (v_ok and a_ok) else "FAIL"
            ok = ok and v_ok and a_ok
            print(f"[self-test] seed={seed} k={k} {tag}: αβ value={val} (gt {gt.value}) "
                  f"value_match={v_ok} | action={act} in optimal_set({len(gt_opt)})={a_ok} "
                  f"| nodes={ab.nodes} steps={ab.steps} -> {status}")

        # (2) pruning + TT fail-soft soundness + leaf-horizon: αβ == plain minimax
        for d in (2, 4):
            ref = plain_minimax(g, b, d, DEFAULT_CONFIG)
            v_off, _ = AlphaBeta(g, DEFAULT_CONFIG, use_tt=False, step_cap=CAP).search(b, d)
            v_on, _ = AlphaBeta(g, DEFAULT_CONFIG, use_tt=True, step_cap=CAP).search(b, d)
            m = (v_off == ref) and (v_on == ref)
            ok = ok and m
            print(f"[self-test] seed={seed} k={k} depth={d}: plain-minimax={ref} "
                  f"αβ_off={v_off} αβ_on={v_on} match={m} -> {'PASS' if m else 'FAIL'}")

    # (3) terminal-value path == flat_base_score
    g, b = _near_terminal(9_200_001, 2)
    if b is not None:
        tb = _play_to_terminal(g, b)
        ab = AlphaBeta(g, DEFAULT_CONFIG, use_tt=False, step_cap=CAP)
        tv = ab._value(tb, 5, -math.inf, math.inf)
        exp = float(flat_base_score(tb.state, 0))
        m = (tv == exp)
        ok = ok and m
        print(f"[self-test] terminal-value path: αβ={tv} flat_base_score={exp} "
              f"match={m} -> {'PASS' if m else 'FAIL'}")

    # (4) explicit 1-ply P0-POV max/min selection on a MEEPLES node (depth=1 ->
    #     children are TILES leaves, no extension): value == mover's max/min over
    #     child leaves.
    g, b = _near_terminal(9_200_033, 4)
    if b is not None:
        mb = _first_meeple_child(g, b)
        if mb is not None:
            legal = np.flatnonzero(g.get_valid_moves(mb))
            child_leaves = []
            for a in legal:
                nb, _ = g.get_next_state(mb, int(a))
                if nb.state.next_tile is None:
                    child_leaves.append(float(flat_base_score(nb.state, 0)))
                elif nb.state.phase == _TILES:
                    child_leaves.append(float(flat_virtual_score_v2_float(nb.state, 0, DEFAULT_CONFIG, None)))
                else:  # would extend — exclude from the clean 1-ply manual check
                    child_leaves = None
                    break
            if child_leaves:
                mover = mb.state.current_player
                exp = max(child_leaves) if mover == 0 else min(child_leaves)
                val, _ = AlphaBeta(g, DEFAULT_CONFIG, use_tt=False, step_cap=CAP).search(mb, 1)
                m = (val == exp)
                ok = ok and m
                print(f"[self-test] 1-ply MEEPLES node mover={mover}: "
                      f"manual {'max' if mover == 0 else 'min'}={exp} αβ={val} "
                      f"match={m} -> {'PASS' if m else 'FAIL'}")

    print("\n[self-test] RESULT:", "ALL PASS" if ok else "FAILURE(S) — DO NOT TRUST DEPTH NUMBERS")
    return ok


# --------------------------------------------------------------------------- #
# Emit                                                                          #
# --------------------------------------------------------------------------- #
def _verdict(median_depth: int) -> tuple[str, str]:
    if median_depth >= 6:
        return "GO", ("median midgame completed depth >= 6 plies (3 full turns) within "
                      "the champion budget — proceed to the Stage-1 agent build (§8).")
    if median_depth <= 4:
        return "DECLINE", ("median midgame completed depth <= 4 plies — full-width exact "
                           "search 2 turns deep cannot beat a 2750-sim prior-guided tree "
                           "whose leaf already encodes 1-turn tactics; make/unmake's "
                           "+0.7-1.0 ply cannot reach 6 from 4. C6 CLOSED on cost (§9 K0).")
    return "GRAY", ("median midgame completed depth = 5 plies — attended decision for "
                    "Joshua with the §2 make/unmake escalation arithmetic (would put ~6 "
                    "in reach; is a 3-5d build worth a coin-flip screen?).")


def write_markdown(md_path: Path, payload: dict) -> None:
    p = payload
    depths = p["depths"]
    lines = []
    lines.append("# C6 Stage-0 — COST SURFACE (the go/no-go gate)")
    lines.append("")
    lines.append(f"> **STATUS: RUN COMPLETE {p['finished_utc']}** — auto-generated by "
                 "`scripts/classical_search/bench_ab_cost.py`. Pre-registered by "
                 "[C6_ALPHABETA_DESIGN.md](C6_ALPHABETA_DESIGN.md) §7. Raw numbers: "
                 "`ab_cost_raw.json`. No `results.csv` row (bench, not an experiment).")
    lines.append("")
    verdict, why = p["verdict"], p["verdict_reason"]
    lines.append(f"## VERDICT: **{verdict}**")
    lines.append("")
    lines.append(f"Median midgame (plies {MID_PLY_LO}-{MID_PLY_HI}) achievable depth "
                 f"(TT-on, within the champion's per-position budget) = "
                 f"**{p['median_midgame_depth_tt_on']} plies** "
                 f"(TT-off floor: {p['median_midgame_depth_tt_off']}). {why}")
    lines.append("")
    lines.append("Pre-registered rule (§7): depth >=6 = GO, <=4 = DECLINE, =5 = GRAY.")
    lines.append("")
    lines.append(f"- host: `{p['host']}` · cpu: `{p['cpu']}` · python {p['python']}")
    lines.append(f"- Cython leaf active (int+float): `{p['provenance']['cython_leaf_active']}` · "
                 f"leaf curve125: `{p['leaf_curve']}`")
    lines.append(f"- champion: PUCT float @{p['champ_sims']} sims, reuse OFF "
                 f"(HeuristicPriorAgent, curve125 leaf) — median **{p['champ_median_ms']} ms/move** "
                 f"(the equal-wall-clock budget)")
    lines.append("")

    lines.append("## Champion budget (§7 item 3)")
    lines.append("")
    lines.append("| stat | ms/move |")
    lines.append("|---|---|")
    lines.append(f"| median | {p['champ_median_ms']} |")
    lines.append(f"| mean | {p['champ_mean_ms']} |")
    lines.append(f"| p10 | {p['champ_p10_ms']} |")
    lines.append(f"| p90 | {p['champ_p90_ms']} |")
    lines.append("")

    lines.append("## Micro-measurements by ply bucket (§7 item 2)")
    lines.append("")
    lines.append("Median µs per call (single-thread, uncached).")
    lines.append("")
    lines.append("| bucket | plies | leaf | get_next_state | gvm(tiles) | gvm(meeples) | sr+blake2b |")
    lines.append("|---|---|---|---|---|---|---|")
    for bkt in p["micro"]:
        m = bkt["agg"]
        lines.append(f"| {bkt['bucket']} | {bkt['ply_lo']}-{bkt['ply_hi']} | "
                     f"{m.get('leaf_us','-')} | {m.get('get_next_state_us','-')} | "
                     f"{m.get('get_valid_moves_tiles_us','-')} | "
                     f"{m.get('get_valid_moves_meeples_us','-')} | "
                     f"{m.get('string_repr_plus_blake2b_us','-')} |")
    lines.append("")

    lines.append("## Branching (legal-count) histogram by phase (§7 item 2)")
    lines.append("")
    lines.append("| phase | n | min | p50 | mean | p95 | max |")
    lines.append("|---|---|---|---|---|---|---|")
    for phase in ("tiles", "meeples"):
        h = p["branching"][phase]
        lines.append(f"| {phase} | {h.get('n',0)} | {h.get('min','-')} | {h.get('p50','-')} | "
                     f"{h.get('mean','-')} | {h.get('p95','-')} | {h.get('max','-')} |")
    lines.append("")

    lines.append("## alpha-beta cost surface (§7 items 4-5, midgame positions)")
    lines.append("")
    lines.append("Median over midgame positions (plies 30-100). N(d) = child-steps to "
                 "COMPLETE depth d; b_eff = (N(d)/N(d-2))^0.5; wall = ms to complete.")
    lines.append("")
    lines.append("| d | N(d) steps (TT-off) | wall ms (TT-off) | b_eff | N(d) steps (TT-on) | wall ms (TT-on) |")
    lines.append("|---|---|---|---|---|---|")
    agg = p["ab_agg_midgame"]
    for d in depths:
        row = agg.get(str(d), {})
        lines.append(f"| {d} | {row.get('steps_tt_off','-')} | {row.get('wall_tt_off','-')} | "
                     f"{row.get('b_eff_tt_off','-')} | {row.get('steps_tt_on','-')} | "
                     f"{row.get('wall_tt_on','-')} |")
    lines.append("")
    lines.append(f"- TT-on vs TT-off step ratio at d=6 (midgame median): "
                 f"**{p['tt_step_ratio_d6']}** (>1 => TT saved steps; §3 expects ~1 under a fixed deck)")
    lines.append(f"- cross-parent EXACT-hit fraction at d=6 (§3 telemetry, midgame median): "
                 f"**{p['tt_exact_hit_frac_d6']}** (pre-registered expectation < 10%)")
    lines.append("")
    lines.append("## Achievable depth within budget (§7 item 5)")
    lines.append("")
    lines.append("Per midgame position: max completed d whose wall <= that position's "
                 "champion ms/move.")
    lines.append("")
    lines.append("| statistic | TT-off | TT-on |")
    lines.append("|---|---|---|")
    lines.append(f"| median (midgame) | {p['median_midgame_depth_tt_off']} | "
                 f"{p['median_midgame_depth_tt_on']} |")
    lines.append(f"| p10 (midgame) | {p['p10_midgame_depth_tt_off']} | "
                 f"{p['p10_midgame_depth_tt_on']} |")
    lines.append("")
    lines.append("## Notes / operationalization")
    lines.append("")
    lines.append("- The cost bench is FIXED-DEPTH (design §7 'throwaway fixed-depth αβ'); the "
                 "Stage-1 agent adds ID re-search + aspiration + killers, so achievable depth "
                 "here is an *upper bound* on a single decision's reach (ID re-search adds "
                 "overhead the TT is meant to absorb, §3).")
    lines.append("- Within one fixed-depth pass under a fixed deck the same key implies the "
                 "same ply/remaining-depth, so any TT hit is a genuine cross-path "
                 "transposition (no ID re-search inside a single pass) — that is what the "
                 "d=6 EXACT-hit fraction measures.")
    lines.append("- A per-search child-step safety cap keeps the bench bounded; a depth that "
                 "hits the cap is recorded NOT-completed and escalation for that position stops.")
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true",
                    help="run ONLY the mover-convention correctness check and exit (cheap)")
    ap.add_argument("--n-positions", type=int, default=20)
    ap.add_argument("--champ-sims", type=int, default=2750)
    ap.add_argument("--depths", default="2,4,6,8")
    ap.add_argument("--micro-iters", type=int, default=400)
    ap.add_argument("--branch-depth", type=int, default=3, help="plies for the branching histogram walk")
    ap.add_argument("--branch-node-cap", type=int, default=4000)
    ap.add_argument("--step-cap", type=int, default=int(os.environ.get("CARCASSONNE_AB_STEP_CAP", "20000000")),
                    help="per-search child-step safety cap (a search past it is NOT-completed)")
    ap.add_argument("--max-search-secs", type=float, default=90.0,
                    help="per-search wall deadline (a search past it is NOT-completed; bounds total cost)")
    ap.add_argument("--escalate-budget-mult", type=float, default=6.0,
                    help="stop escalating d once a completed depth's wall > mult × the champion budget")
    ap.add_argument("--out-json", default=str(
        REPO / "measurement" / "classical_search" / "ab_cost_raw.json"))
    ap.add_argument("--out-md", default=str(
        REPO / "measurement" / "classical_search" / "C6_COST_SURFACE.md"))
    args = ap.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    depths = [int(x) for x in args.depths.split(",") if x]
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    print(f"[ab-cost] host={socket.gethostname()} cpu={platform.processor() or platform.machine()}")
    prov = verify_cython_active()
    print(f"[ab-cost] cython leaf ACTIVE (int+float): {prov['cython_leaf_active']}")

    positions = build_positions(args.n_positions)
    plies = [p["ply"] for p in positions]
    print(f"[ab-cost] {len(positions)} positions (plies {min(plies)}-{max(plies)})", flush=True)

    payload = {
        "kind": "c6_ab_cost_surface",
        "host": socket.gethostname(),
        "cpu": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "env": {k: os.environ.get(k) for k in ("CARCASSONNE_V29_MEEPLE_CURVE",
                "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP", "CARCASSONNE_USE_CY_LEAF",
                "CARCASSONNE_USE_CY_REPR", "CARCASSONNE_USE_FLAT_LEAF")},
        "provenance": prov,
        "leaf_curve": list(DEFAULT_CONFIG.v29_meeple_curve) if DEFAULT_CONFIG.v29_meeple_curve else None,
        "champ_sims": args.champ_sims,
        "depths": depths,
        "step_cap": args.step_cap,
        "max_search_secs": args.max_search_secs,
        "escalate_budget_mult": args.escalate_budget_mult,
        "positions": [{"seed": p["seed"], "ply": p["ply"], "n_legal": p["n_legal"]} for p in positions],
    }

    # --- champion budget -------------------------------------------------- #
    t0 = time.perf_counter()
    champ_ms = bench_champion(positions, args.champ_sims)
    payload["champ_median_ms"] = round(float(np.median(champ_ms)), 1)
    payload["champ_mean_ms"] = round(float(np.mean(champ_ms)), 1)
    payload["champ_p10_ms"] = round(float(np.percentile(champ_ms, 10)), 1)
    payload["champ_p90_ms"] = round(float(np.percentile(champ_ms, 90)), 1)
    payload["champ_per_pos_ms"] = [round(x, 1) for x in champ_ms]
    print(f"[ab-cost] champion PUCT@{args.champ_sims} reuse-off: median "
          f"{payload['champ_median_ms']} ms/move [{time.perf_counter()-t0:.0f}s]", flush=True)
    out_json.write_text(json.dumps(payload, indent=2))

    # --- micro-measurements by bucket ------------------------------------- #
    n = len(positions)
    bucket_bounds = [("early", 0, n // 3), ("mid", n // 3, 2 * n // 3), ("late", 2 * n // 3, n)]
    micro = []
    for name, lo, hi in bucket_bounds:
        sub = positions[lo:hi]
        if not sub:
            continue
        per = [micro_measure(p["board"], args.micro_iters) for p in sub]
        keys = set().union(*[set(d) for d in per]) - {"phase"}
        agg = {k: round(float(np.median([d[k] for d in per if k in d])), 3) for k in keys}
        micro.append({"bucket": name, "ply_lo": min(p["ply"] for p in sub),
                      "ply_hi": max(p["ply"] for p in sub), "agg": agg, "per_pos": per})
        print(f"[ab-cost] micro {name} (plies {micro[-1]['ply_lo']}-{micro[-1]['ply_hi']}): "
              f"leaf={agg.get('leaf_us')}us next_state={agg.get('get_next_state_us')}us", flush=True)
    payload["micro"] = micro
    out_json.write_text(json.dumps(payload, indent=2))

    # --- branching histogram ---------------------------------------------- #
    tiles_all, meeples_all = [], []
    for p in positions:
        h = branching_hist(Game(enable_legal_moves_cache=False), p["board"],
                           args.branch_depth, args.branch_node_cap)
        tiles_all += h["tiles"]
        meeples_all += h["meeples"]
    payload["branching"] = {"tiles": _hist_summary(tiles_all), "meeples": _hist_summary(meeples_all)}
    print(f"[ab-cost] branching: tiles p50={payload['branching']['tiles'].get('p50')} "
          f"meeples p50={payload['branching']['meeples'].get('p50')}", flush=True)
    out_json.write_text(json.dumps(payload, indent=2))

    # --- alpha-beta cost surface per position ----------------------------- #
    per_pos_ab = []
    for i, p in enumerate(positions):
        t0 = time.perf_counter()
        r = ab_cost_for_position(p["board"], depths, args.step_cap,
                                 args.max_search_secs, champ_ms[i], args.escalate_budget_mult)
        r["seed"] = p["seed"]
        r["ply"] = p["ply"]
        r["champ_ms"] = champ_ms[i]
        r["achievable_tt_off"] = achievable_depth(r, depths, champ_ms[i], "tt_off")
        r["achievable_tt_on"] = achievable_depth(r, depths, champ_ms[i], "tt_on")
        per_pos_ab.append(r)
        deepest_off = max((d for d in depths if r["tt_off"].get(d, {}).get("completed")), default=0)
        print(f"[ab-cost] pos {i+1}/{n} ply={p['ply']}: deepest-completed(TT-off)={deepest_off} "
              f"achievable(TT-on)={r['achievable_tt_on']} champ={champ_ms[i]:.0f}ms "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
        payload["ab_per_position"] = per_pos_ab
        out_json.write_text(json.dumps(payload, indent=2))

    # --- aggregate over midgame positions --------------------------------- #
    mid = [r for r in per_pos_ab if MID_PLY_LO <= r["ply"] <= MID_PLY_HI]
    payload["n_midgame"] = len(mid)
    ab_agg = {}
    for d in depths:
        def _steps(variant):
            return [r[variant][d]["steps"] for r in mid
                    if r[variant].get(d, {}).get("completed")]

        def _wall(variant):
            return [r[variant][d]["wall_ms"] for r in mid
                    if r[variant].get(d, {}).get("completed")]

        def _beff(variant):
            return [r[variant + "_b_eff"][d] for r in mid if d in r.get(variant + "_b_eff", {})]

        off_s, on_s = _steps("tt_off"), _steps("tt_on")
        off_w, on_w = _wall("tt_off"), _wall("tt_on")
        bo = _beff("tt_off")
        ab_agg[str(d)] = {
            "n_completed_tt_off": len(off_s), "n_completed_tt_on": len(on_s),
            "steps_tt_off": _median_int(off_s), "steps_tt_on": _median_int(on_s),
            "wall_tt_off": round(float(np.median(off_w)), 1) if off_w else None,
            "wall_tt_on": round(float(np.median(on_w)), 1) if on_w else None,
            "b_eff_tt_off": round(float(np.median(bo)), 3) if bo else None,
        }
    payload["ab_agg_midgame"] = ab_agg

    # d=6 TT telemetry (midgame medians)
    ratios, exact_fracs = [], []
    for r in mid:
        off6, on6 = r["tt_off"].get(6), r["tt_on"].get(6)
        if off6 and on6 and off6["completed"] and on6["completed"] and on6["steps"] > 0:
            ratios.append(off6["steps"] / on6["steps"])
        if on6 and on6["completed"] and on6["tt_probes"] > 0:
            exact_fracs.append(on6["tt_exact_hits"] / on6["tt_probes"])
    payload["tt_step_ratio_d6"] = round(float(np.median(ratios)), 3) if ratios else None
    payload["tt_exact_hit_frac_d6"] = round(float(np.median(exact_fracs)), 4) if exact_fracs else None

    off_depths = [r["achievable_tt_off"] for r in mid]
    on_depths = [r["achievable_tt_on"] for r in mid]
    payload["median_midgame_depth_tt_off"] = _median_int(off_depths)
    payload["median_midgame_depth_tt_on"] = _median_int(on_depths)
    payload["p10_midgame_depth_tt_off"] = int(np.percentile(off_depths, 10)) if off_depths else 0
    payload["p10_midgame_depth_tt_on"] = int(np.percentile(on_depths, 10)) if on_depths else 0

    verdict, why = _verdict(payload["median_midgame_depth_tt_on"])
    payload["verdict"] = verdict
    payload["verdict_reason"] = why
    payload["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out_json.write_text(json.dumps(payload, indent=2))
    write_markdown(out_md, payload)

    print("\n=== C6 STAGE-0 COST SURFACE ===")
    print(f"champion budget: {payload['champ_median_ms']} ms/move (median)")
    print(f"median midgame achievable depth: TT-off={payload['median_midgame_depth_tt_off']} "
          f"TT-on={payload['median_midgame_depth_tt_on']}")
    print(f"d=6 TT step ratio={payload['tt_step_ratio_d6']} "
          f"exact-hit frac={payload['tt_exact_hit_frac_d6']}")
    print(f"\nVERDICT (§7): {verdict} — {why}")
    print(f"[ab-cost] DONE -> {out_json}\n              -> {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
