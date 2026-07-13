"""C6 — full-game iterative-deepening alpha-beta agent (the "clairvoyant
chess-engine gambit"). Pre-registered design:
``measurement/classical_search/C6_ALPHABETA_DESIGN.md`` (Stage-0 = GO,
``C6_COST_SURFACE.md``, median midgame depth 6 within the champion budget).

This is a NEW sibling agent class to ``heuristic_prior_mcts.HeuristicPriorAgent``:
flag-gated, default-OFF, and nothing in ``mcts.py`` / ``heuristic_prior_mcts.py`` /
``fair_agent.py`` is touched. ``governance/PRODUCTION.yaml`` and the champion are
untouched — an A/B cell only ever constructs this agent when the harness is asked
for ``--candidate ab``.

Algorithm (design §1/§4), ported from the validated throwaway core in
``scripts/classical_search/bench_ab_cost.py`` (whose mover convention is proven
EXACT against ``endgame_solver`` by the bench self-test), then extended:

  * **Mover convention — NOT naive negamax.** A Carcassonne turn is two same-mover
    plies (TILES -> MEEPLES), so per-ply sign-flipping is wrong. Values are always
    P0-POV score-diffs (points); a node is a MAX node iff ``state.current_player==0``
    (mirrors ``endgame_solver._value_ab``).
  * **Horizon rule:** the search horizon may only land on a TILES-phase node — if the
    depth limit hits at phase==MEEPLES we recurse one more ply (the game's 1-ply
    quiescence: never evaluate a state where a tile was just placed but the free
    meeple option was not yet taken).
  * **Terminal** nodes (``next_tile is None``) return the exact ``flat_base_score``.
  * **Leaf** at the horizon = ``flat_virtual_score_v2_float`` (Cython float), P0-POV,
    raw points (NOT tanh — design §1: a monotone transform is decision-neutral for
    minimax and point-space keeps aspiration/futility margins position-independent).
  * **Iterative deepening** by +2 plies/iter (one full turn): d = 2, 4, 6, …
  * **PVS** (principal-variation search) with null windows (ε = ``pvs_eps``).
  * **Aspiration** windows from ID depth >= ``asp_min_depth`` (default 6): root window
    = previous-iteration value ± ``asp``; fail -> widen ×``asp_widen`` once, then full.
  * **Move ordering** (staged, cheapest-first): TT best move -> killers -> Δleaf.
  * **Killers:** 2 slots per ply level (β-cutoff moves), tried after the TT move.
  * **LMR + futility:** flag-gated, DEFAULT OFF (move-changing — excluded from the
    correctness gauntlet's value-preservation path).
  * **Budget = child-steps** (``get_next_state`` calls), calibrated once to equal the
    champion's per-move wall-clock (design §1/§7). Deterministic; the tie-break is the
    lowest action index (mirrors ``_ExactHandoff``'s ``min(res.optimal_actions)``).

The **root** evaluates every legal child under the current (aspiration) window with
NO cross-sibling cutoff (mirrors ``endgame_solver.solve`` — which scores every root
action exactly so the optimal SET is knowable), so on the final/full-window pass the
returned action is ``min`` over the exact optimal set — bit-exact with the solver on
a terminal-only horizon. Interior nodes use full αβ + PVS cutoffs (the √b saver).

Transposition table (design §3): key = ``blake2b-128(string_representation)`` (memoized
per Board), entries ``(value, flag, remaining_depth, best_action, move_no, parent_sig)``
with fail-soft EXACT/LOWER/UPPER bound flags (reused verbatim from the solver),
depth-preferred replacement with a move-age override, and a freeze-at-cap memory valve
(``CARCASSONNE_AB_TT_CAP``). Cleared per game (``.clear()``), PERSISTED across a game's
moves (the αβ analog of the champion's reuse_tree; §3). ``parent_sig`` (8 bytes of the
parent key) drives the informational ``tt_cross_parent_hits`` telemetry — a hit whose
stored parent differs from the current parent is a true transposition (design §3
expects < 10% under a fixed deck; the cost surface measured 0.22%).
"""
from __future__ import annotations

import dataclasses as dc
import hashlib
import json
import math
import os
from dataclasses import dataclass, field

import numpy as np

from carcassonne_ai.action_space import WindowOverflowError
from carcassonne_ai.flat_leaf import flat_base_score, flat_virtual_score_v2_float
from carcassonne_ai.game_wrapper import Board, Game
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

try:
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    _TILES = GamePhase.TILES
    _MEEPLES = GamePhase.MEEPLES
except Exception:  # pragma: no cover
    _TILES = _MEEPLES = None

# Alpha-beta TT fail-soft bound flags — reused verbatim from endgame_solver._value_ab.
_EXACT, _LOWER, _UPPER = 0, 1, 2

_INF = math.inf


class BudgetExceeded(Exception):
    """Raised when a single decision hits its child-step budget (the current ID
    iteration is abandoned; the deepest COMPLETED iteration's move is played)."""


def _leaf_hash(cfg) -> str:
    """Stable 16-hex-char hash of a resolved LeafConfig (provenance). Byte-identical
    recipe to ``scripts/classical_search/c5_leaf_override._leaf_hash`` so the agent's
    ``as_manifest`` leaf_hash matches the per-side leaf_hash the harness records."""
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()}
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def _default_tt_cap() -> int:
    return int(os.environ.get("CARCASSONNE_AB_TT_CAP", "2000000"))


# --------------------------------------------------------------------------- #
# Config (design §6)                                                          #
# --------------------------------------------------------------------------- #
@dataclass
class AlphaBetaConfig:
    """Resolved knobs for the ID-alpha-beta agent (design §6 table).

    step_budget   child-step (`get_next_state`) budget per DECISION — the
                  equal-wall-clock normalizer (calibrated in Stage 0; there is no
                  sims axis for αβ). Required.
    max_depth     ID ply safety cap; the budget binds first in practice.
    asp           aspiration half-width in POINTS (0 = off). Applied from
                  ``asp_min_depth``. Fail -> widen ×``asp_widen`` once, then full.
    pvs           principal-variation search (null-window probes). Value-preserving.
    tt_cap        TT entry cap (freeze-at-cap valve); env CARCASSONNE_AB_TT_CAP.
    killers       killer slots per ply level (0 = off).
    lmr           late-move reductions — DEFAULT OFF (move-changing; swept, not
                  defaulted). Reduce 2 plies on moves ranked >= 5 at remaining-depth
                  >= 4, re-search on fail.
    futility      frontier (remaining-depth == 2, TILES) futility margin in POINTS
                  (0 = off). DEFAULT OFF (move-changing).
    leaf_cfg      virtual_score_v2.LeafConfig; None -> env DEFAULT_CONFIG (the
                  production curve125 leaf under the standard exports).
    pvs_eps       null-window epsilon (float leaf -> no integer granularity; §1).
    asp_widen     aspiration widen multiplier (design: ×4 then full).
    asp_min_depth ID depth at/after which aspiration engages (design: 6).
    tt_age_moves  age override for depth-preferred TT replacement (design: 4 moves).
    use_tt        transposition table on/off. Default True; exposed for the
                  value-preservation gauntlet's "all OFF" arm (not a CLI knob).

    NOTE: lmr / futility DEFAULT to a no-op (OFF); with pvs/tt/killers/asp the agent
    is a pure exact minimax (value-preserving) — the correctness gauntlet asserts
    ON == OFF at fixed depth.
    """

    step_budget: int
    max_depth: int = 64
    asp: float = 3.0
    pvs: bool = True
    tt_cap: int = field(default_factory=_default_tt_cap)
    killers: int = 2
    lmr: bool = False
    futility: float = 0.0
    leaf_cfg: object = None
    pvs_eps: float = 1e-4
    asp_widen: float = 4.0
    asp_min_depth: int = 6
    tt_age_moves: int = 4
    use_tt: bool = True

    def __post_init__(self):
        if int(self.step_budget) <= 0:
            raise ValueError(f"step_budget must be > 0; got {self.step_budget!r}")
        if int(self.max_depth) < 2:
            raise ValueError(f"max_depth must be >= 2; got {self.max_depth!r}")
        if int(self.killers) < 0:
            raise ValueError(f"killers must be >= 0; got {self.killers!r}")
        if float(self.asp) < 0 or float(self.futility) < 0:
            raise ValueError("asp / futility must be >= 0")

    def resolved_leaf_cfg(self):
        return self.leaf_cfg if self.leaf_cfg is not None else DEFAULT_CONFIG

    def as_manifest(self) -> dict:
        """JSON-serializable resolved config for a run manifest (mirrors
        HeuristicPriorConfig.as_manifest; carries the resolved leaf + leaf_hash)."""
        lc = self.resolved_leaf_cfg()
        leaf = {
            k: (list(v) if isinstance(v, tuple) else v)
            for k, v in dc.asdict(lc).items()
        }
        return {
            "agent": "AlphaBetaAgent",
            "step_budget": int(self.step_budget),
            "max_depth": int(self.max_depth),
            "asp": float(self.asp),
            "pvs": bool(self.pvs),
            "tt_cap": int(self.tt_cap),
            "killers": int(self.killers),
            "lmr": bool(self.lmr),
            "futility": float(self.futility),
            "pvs_eps": float(self.pvs_eps),
            "asp_widen": float(self.asp_widen),
            "asp_min_depth": int(self.asp_min_depth),
            "tt_age_moves": int(self.tt_age_moves),
            "use_tt": bool(self.use_tt),
            "leaf_cfg": leaf,
            "leaf_hash": _leaf_hash(lc),
        }


def _sig(key: bytes) -> int:
    """8-byte parent signature for the cross-parent (transposition) telemetry."""
    return int.from_bytes(key[:8], "little")


# --------------------------------------------------------------------------- #
# Agent                                                                       #
# --------------------------------------------------------------------------- #
class AlphaBetaAgent:
    """Iterative-deepening alpha-beta agent. ``.move(board) -> int`` returns the
    chosen action; ``.clear()`` drops the TT (game start). Fully deterministic
    (``seed`` is accepted-and-unused, for constructor symmetry with the PUCT agent).

    Telemetry (read by the harness into per-game results / the manifest, §8):
      steps_used, nodes                          cumulative
      tt_probes, tt_exact_hits, tt_cross_parent_hits
      depth_completed                            per-move list (deepest COMPLETED ID
                                                 iteration) -> median/p10 gate (§9)
      last_root_value                            last decision's root value
    """

    def __init__(self, game: Game, cfg: AlphaBetaConfig, seed=None):
        # Own search game: NO legal-moves cache (that cache is a game-global dict
        # keyed by string_representation -> it would grow unboundedly across a deep
        # search and OOM; the bench uses enable_legal_moves_cache=False for exactly
        # this reason). string_representation stays memoized per-Board regardless.
        if game is not None and getattr(game, "_legal_cache", None) is None:
            self.game = game
        else:
            self.game = Game(enable_legal_moves_cache=False)
        self.cfg = cfg
        self.leaf_cfg = cfg.resolved_leaf_cfg()
        # bag_close resolved from the leaf cfg exactly as make_heuristic_prior_evaluator
        # does (production curve125 -> False) so both A/B sides take the same cy branch.
        self.bag_close = bool(getattr(self.leaf_cfg, "bag_close", False))
        self.use_tt = bool(cfg.use_tt)
        self._eps = float(cfg.pvs_eps)
        self.tt: dict[bytes, tuple] = {}
        self._reset_telemetry()

    def _reset_telemetry(self) -> None:
        self.steps_used = 0
        self.nodes = 0
        self.leaf_evals = 0
        self.tt_probes = 0
        self.tt_exact_hits = 0
        self.tt_cross_parent_hits = 0
        self.window_overflows = 0
        self.horizon_tiles = 0
        self.horizon_meeple_hits = 0   # MUST stay 0 (horizon never lands on MEEPLES)
        self.extensions = 0            # meeple-extension recursions taken
        self.depth_completed: list[int] = []
        self.last_root_value: float | None = None
        self.move_no = 0

    def clear(self) -> None:
        """Drop the TT (called once at game start; the TT PERSISTS across the game's
        moves — §3). Also resets telemetry so counters are per-game."""
        self.tt.clear()
        self._reset_telemetry()

    # -- leaf / key primitives (bit-exact with bench_ab_cost.AlphaBeta) ------- #
    def _leaf(self, state) -> float:
        self.leaf_evals += 1
        return flat_virtual_score_v2_float(state, 0, self.leaf_cfg, self.bag_close)

    def _horizon_leaf(self, state) -> float:
        """Depth-cutoff (horizon) evaluation. Instrumented: the horizon must only ever
        be a TILES-phase node (the caller guards this) — horizon_meeple_hits proves it."""
        if _MEEPLES is not None and state.phase == _MEEPLES:
            self.horizon_meeple_hits += 1
        else:
            self.horizon_tiles += 1
        return self._leaf(state)

    def _key(self, board: Board) -> bytes:
        sr = self.game.string_representation(board)
        return hashlib.blake2b(sr.encode(), digest_size=16).digest()

    def _step(self, board: Board, a: int) -> Board:
        """Step ONE child (a child-step = the budget unit); enforce the per-move
        child-step deadline. Raises BudgetExceeded when the budget is hit."""
        nb, _ = self.game.get_next_state(board, int(a))
        self.steps_used += 1
        if self.steps_used > self._deadline_steps:
            raise BudgetExceeded
        return nb

    # -- staged move ordering (design §4: tt -> killers -> Δleaf) ------------ #
    def _gen_children(self, board, legal, tt_move, killers, mover):
        """Yield (action, child_board) in staged order, stepping children LAZILY so a
        TT/killer cutoff avoids stepping the rest. Stage 3 steps all remaining children
        and sorts by child leaf (desc for a max-mover, asc for min) — the same Δleaf
        signal the champion's priors are built from. Deterministic: stage-3 ties keep
        ascending action order (stable sort over ascending ``legal``)."""
        legal_set = {int(a) for a in legal}
        tried: set[int] = set()
        # stage 1: TT best move
        if self.use_tt and tt_move is not None and tt_move >= 0 and tt_move in legal_set:
            tried.add(tt_move)
            yield tt_move, self._step(board, tt_move)
        # stage 2: killers (legality = mask membership only)
        if killers is not None:
            for k in killers:
                if k >= 0 and k not in tried and k in legal_set:
                    tried.add(k)
                    yield k, self._step(board, k)
        # stage 3: Δleaf full ordering over the remaining children
        kids = []
        for a in legal:
            ai = int(a)
            if ai in tried:
                continue
            nb = self._step(board, ai)
            kids.append((ai, nb, self._leaf(nb.state)))
        kids.sort(key=lambda t: t[2], reverse=(mover == 0))
        for ai, nb, _l in kids:
            yield ai, nb

    def _add_killer(self, ply: int, a: int) -> None:
        if ply >= len(self._killers):
            return
        ks = self._killers[ply]
        if ks and ks[0] != a:
            for i in range(len(ks) - 1, 0, -1):
                ks[i] = ks[i - 1]
            ks[0] = a

    def _store(self, key, best, flag, depth, best_a, parent_sig) -> None:
        old = self.tt.get(key)
        if old is not None:
            # depth-preferred replacement with a move-age override (§3).
            if depth >= old[2] or old[4] < self.move_no - self.cfg.tt_age_moves:
                self.tt[key] = (best, flag, depth, best_a, self.move_no, parent_sig)
        elif not self.cfg.tt_cap or len(self.tt) < self.cfg.tt_cap:
            # freeze-at-cap: new keys only inserted while under the cap (memory valve).
            self.tt[key] = (best, flag, depth, best_a, self.move_no, parent_sig)

    # -- interior node: fail-soft P0-POV alpha-beta + PVS -------------------- #
    def _ab(self, board: Board, depth: int, alpha: float, beta: float,
            ply: int, parent_sig: int) -> float:
        st = board.state
        if st.next_tile is None:                      # terminal -> exact final score
            return float(flat_base_score(st, 0))
        if depth <= 0:
            if st.phase != _MEEPLES:                   # horizon (TILES) -> static leaf
                return self._horizon_leaf(st)
            self.extensions += 1                       # MEEPLES horizon -> extend one ply

        a0, b0 = alpha, beta
        key = None
        tt_move = None
        if self.use_tt:
            self.tt_probes += 1
            key = self._key(board)
            ent = self.tt.get(key)
            if ent is not None:
                val, flag, sdepth, sa, _smove, spar = ent
                tt_move = sa
                if sdepth >= depth:
                    cross = (spar != parent_sig)
                    if flag == _EXACT:
                        self.tt_exact_hits += 1
                        if cross:
                            self.tt_cross_parent_hits += 1
                        return val
                    if flag == _LOWER and val > alpha:
                        alpha = val
                    elif flag == _UPPER and val < beta:
                        beta = val
                    if alpha >= beta:
                        if cross:
                            self.tt_cross_parent_hits += 1
                        return val

        mover = st.current_player
        child_sig = _sig(key) if key is not None else parent_sig
        try:
            legal = np.flatnonzero(self.game.get_valid_moves(board))
        except WindowOverflowError:                    # board drifted to the window edge
            self.window_overflows += 1
            return self._leaf(st)
        if legal.size == 0:
            return self._leaf(st)
        self.nodes += 1

        futile = (self.cfg.futility > 0.0 and depth == 2 and st.phase == _TILES)
        node_leaf = self._leaf(st) if futile else None

        killers = self._killers[ply] if (self.cfg.killers > 0
                                         and ply < len(self._killers)) else None
        best = -_INF if mover == 0 else _INF
        best_a = -1
        first = True
        rank = 0
        for a, nb in self._gen_children(board, legal, tt_move, killers, mover):
            # futility (frontier TILES nodes only; flag-gated OFF by default).
            if futile and not first:
                if mover == 0 and node_leaf + self.cfg.futility <= alpha:
                    rank += 1
                    continue
                if mover == 1 and node_leaf - self.cfg.futility >= beta:
                    rank += 1
                    continue
            cd = depth - 1
            red = 2 if (self.cfg.lmr and not first and rank >= 4 and cd >= 4) else 0
            if mover == 0:                             # MAX node
                if first or not self.cfg.pvs:
                    v = self._ab(nb, cd, alpha, beta, ply + 1, child_sig)
                else:
                    hi = alpha + self._eps
                    if hi > beta:
                        hi = beta
                    v = self._ab(nb, cd - red, alpha, hi, ply + 1, child_sig)
                    if red and v > alpha:              # LMR fail-high -> full depth
                        v = self._ab(nb, cd, alpha, hi, ply + 1, child_sig)
                    if alpha < v < beta and hi < beta:  # PVS fail-high -> full re-search
                        v = self._ab(nb, cd, alpha, beta, ply + 1, child_sig)
                if v > best or (v == best and a < best_a):
                    best, best_a = v, a
                if best > alpha:
                    alpha = best
            else:                                      # MIN node
                if first or not self.cfg.pvs:
                    v = self._ab(nb, cd, alpha, beta, ply + 1, child_sig)
                else:
                    lo = beta - self._eps
                    if lo < alpha:
                        lo = alpha
                    v = self._ab(nb, cd - red, lo, beta, ply + 1, child_sig)
                    if red and v < beta:               # LMR fail-low -> full depth
                        v = self._ab(nb, cd, lo, beta, ply + 1, child_sig)
                    if alpha < v < beta and lo > alpha:  # PVS fail-low -> full re-search
                        v = self._ab(nb, cd, alpha, beta, ply + 1, child_sig)
                if v < best or (v == best and a < best_a):
                    best, best_a = v, a
                if best < beta:
                    beta = best
            first = False
            rank += 1
            if alpha >= beta:                          # β/α cutoff -> killer
                if killers is not None:
                    self._add_killer(ply, a)
                break

        if self.use_tt:
            flag = _UPPER if best <= a0 else (_LOWER if best >= b0 else _EXACT)
            self._store(key, best, flag, depth, best_a, parent_sig)
        return best

    # -- root: evaluate every child under (lo,hi), no cross-sibling cutoff --- #
    def _search_root(self, board: Board, depth: int, lo: float, hi: float):
        """Return (best_value, best_action). Mirrors endgame_solver.solve: every legal
        root action is scored under the SAME window (no cross-sibling narrowing), so the
        best over exact child values yields the true optimal SET on the full-window pass
        -> tie-break = lowest action index == solver's min(optimal_actions)."""
        st = board.state
        mover = st.current_player
        key = self._key(board) if self.use_tt else None
        root_sig = _sig(key) if key is not None else 0
        tt_move = None
        if self.use_tt:
            ent = self.tt.get(key)
            if ent is not None:
                tt_move = ent[3]
        legal = np.flatnonzero(self.game.get_valid_moves(board))
        killers = self._killers[0] if (self.cfg.killers > 0 and self._killers) else None
        best = -_INF if mover == 0 else _INF
        best_a = int(legal[0])
        for a, nb in self._gen_children(board, legal, tt_move, killers, mover):
            v = self._ab(nb, depth - 1, lo, hi, 1, root_sig)
            if mover == 0:
                if v > best or (v == best and a < best_a):
                    best, best_a = v, a
            else:
                if v < best or (v == best and a < best_a):
                    best, best_a = v, a
        if self.use_tt:
            flag = _EXACT if (lo < best < hi) else (_LOWER if best >= hi else _UPPER)
            # root parent_sig = 0 (no parent); best_a feeds next-iteration ordering.
            self._store(key, best, flag, depth, best_a, 0)
        return best, best_a

    def _aspiration_search(self, board: Board, depth: int, prev_v):
        """Root search with an aspiration window from depth >= asp_min_depth: try
        ±asp, then ±(asp×asp_widen), then full. Returns (value, action) from the first
        window that contains the value (or the full window)."""
        if self.cfg.asp <= 0 or depth < self.cfg.asp_min_depth or prev_v is None:
            return self._search_root(board, depth, -_INF, _INF)
        asp = float(self.cfg.asp)
        windows = [
            (prev_v - asp, prev_v + asp),
            (prev_v - asp * self.cfg.asp_widen, prev_v + asp * self.cfg.asp_widen),
            (-_INF, _INF),
        ]
        v, a = prev_v, -1
        for lo, hi in windows:
            v, a = self._search_root(board, depth, lo, hi)
            if (lo == -_INF and hi == _INF) or (lo < v < hi):
                break
        return v, a

    def _greedy(self, board: Board) -> int:
        """1-ply greedy fallback (best child leaf, lowest-index tie-break). Only used
        if the budget is too small to complete even ID depth 2 — never in practice at a
        calibrated budget. Does NOT count against the (already-spent) child-step budget."""
        mover = board.state.current_player
        legal = np.flatnonzero(self.game.get_valid_moves(board))
        best_a = int(legal[0])
        best_l = None
        for a in legal:
            nb, _ = self.game.get_next_state(board, int(a))
            l = self._leaf(nb.state)
            if best_l is None or (mover == 0 and l > best_l) or (mover == 1 and l < best_l):
                best_l, best_a = l, int(a)
        return best_a

    # -- public API --------------------------------------------------------- #
    def move(self, board: Board) -> int:
        self.move_no += 1
        self._killers = [[-1] * self.cfg.killers
                         for _ in range(self.cfg.max_depth + 8)] if self.cfg.killers > 0 else []
        move_start = self.steps_used
        self._deadline_steps = self.steps_used + int(self.cfg.step_budget)
        best_action = -1
        prev_v = None
        completed = 0
        depth = 2
        while depth <= self.cfg.max_depth:
            # don't START a new iteration once > ~50% of the budget is spent (§1).
            if depth > 2 and (self.steps_used - move_start) > 0.5 * self.cfg.step_budget:
                break
            try:
                v, a = self._aspiration_search(board, depth, prev_v)
            except BudgetExceeded:
                break                                  # partial iteration discarded
            if a < 0:
                break
            best_action, prev_v, completed = a, v, depth
            depth += 2
        if best_action < 0:                            # budget < ID depth 2 -> greedy
            best_action = self._greedy(board)
            completed = 0
        self.depth_completed.append(completed)
        self.last_root_value = prev_v
        return int(best_action)
