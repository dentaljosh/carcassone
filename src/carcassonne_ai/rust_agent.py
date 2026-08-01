"""Desktop adapter for the Rust fair champion (`carc_rs.FairAgentRs`) — rustport P6.

ONE object that presents the Rust k-parallel PIMC agent through the surface the
Python fair champion already exposes to its callers, so a harness can swap
backends without learning a second shape:

    agent = RustFairAgent(game, cfg, sims=1376, k_dets=8, seed=101)
    agent.start_game(board)                 # seat the mirror on the real deck
    while not game.get_game_ended(board, 0):
        a = agent.choose_action(board) if my_turn else opponent.move(board)
        board, _ = game.get_next_state(board, a)
        agent.advance(a)                    # EVERY applied action, BOTH seats

WHY A MIRROR AT ALL.  The Rust core owns its own game state (the FFI contract is
"mirror state advanced by action ints" — build spec §Architecture); the Python
engine stays authoritative for UI / legality / save.  That is two copies of the
same game, and two copies drift.  Three things keep them honest:

  1. **A single choke point.**  `advance()` is the ONLY way the mirror moves, and
     it must be called for every applied action of BOTH seats.  There is no
     "sync from a board" path, because the Rust state cannot be constructed from
     an arbitrary position — only replayed — so a silent resync is impossible by
     construction and a desync can only ever be an error.
  2. **`start_game(board)` reads the REAL deck** out of the caller's initial
     board (`[next_tile] + deck` in draw order) rather than re-deriving it from
     an RNG seed.  The adapter therefore never assumes how the caller seeded
     `random`, and works for the phone/save path where there is no seed at all.
  3. **Reconcile mode** (`CARC_RS_RECONCILE=1`): every decision hard-asserts the
     mirror's `string_repr()` against `game.string_representation(board)` — the
     byte-equal node key G1 gated — and raises `MirrorDesync`.  Drift can never
     be silent.  It costs one repr per own-move, so it is a gate/CI mode, not a
     production one.

COUNTERS.  `stats()` carries BOTH shapes the eval harness reads:

  * the AGENT shape (`fair_agent.FairHeuristicPriorAgent`): `heur_moves`,
    `exact_moves`, `n_timeouts`, `solver_secs`, `solver_nodes`, `max_solve_secs`,
    `latch_k`, `last_pooled_visits`, `neural_moves` (always 0, harness symmetry);
  * the HARNESS-WRAPPER shape (`eval_fair_puct._MarginalizedHandoff`):
    `prefix_moves` / `prefix_secs` — the search-only clock that feeds
    `champ_prefix_ms_per_move`.

`prefix_secs` is computed TRUTHFULLY, not copied: the wall clock is taken around
the FFI call (so it includes the FFI hop the caller actually pays) and the
solver's own time — measured inside Rust, the same `solver_secs` accumulator the
Python agent keeps — is subtracted.  A latched decision that the solver owned
contributes ZERO prefix time and does not increment `prefix_moves`, exactly as
`_MarginalizedHandoff` does; a `BudgetExceeded` decision contributes its PIMC
fallback to the prefix and its dead solve to `solver_secs`, again exactly as the
Python path does.

NOT IN SCOPE.  This adapter does not decide anything: `governance/PRODUCTION.yaml`
still names the Python champion, and `champion_factory.make_production_champion`
still defaults to `backend="python"`.  G6 delivers the capability and the
evidence; the flip is Joshua's.
"""
from __future__ import annotations

import os
import time

# The panel `champion_factory._LEAF_VALUE_PANEL` pins, evaluated through carc_rs.
# Kept here (not in the factory) so the factory keeps ONE import of this module.
RECONCILE_ENV = "CARC_RS_RECONCILE"


class MirrorDesync(RuntimeError):
    """The Rust mirror and the Python board disagree. Never recoverable."""


def reconcile_enabled(explicit: bool | None = None) -> bool:
    """Resolve reconcile mode: explicit kwarg wins, else ``CARC_RS_RECONCILE=1``."""
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(RECONCILE_ENV, "0") == "1"


# --------------------------------------------------------------------------- #
# Config translation — Python LeafConfig / HeuristicPriorConfig -> carc_rs      #
# --------------------------------------------------------------------------- #
def leaf_config_rs(leaf_cfg):
    """`carcassonne_ai.virtual_score_v2.LeafConfig` -> ``carc_rs.LeafConfigRs``.

    Field-for-field, with `closure_p` sorted by open-count — the same mapping
    `scripts/rustport/reconcile_leaf._to_rs` drove through all 12 config dialects
    of G2 (3,341,772 bit-exact leaf values). Kept in src/ so a production caller
    never has to import a gate script."""
    import carc_rs

    curve = leaf_cfg.v29_meeple_curve
    return carc_rs.LeafConfigRs(
        sorted((int(k), float(v)) for k, v in leaf_cfg.closure_p.items()),
        float(leaf_cfg.bonus_cap),
        float(leaf_cfg.opp_bonus_cap),
        float(leaf_cfg.meeple_k),
        [float(x) for x in curve] if curve else None,
        float(getattr(leaf_cfg, "soft_cap_slope", 0.0)),
        float(getattr(leaf_cfg, "opp_soft_cap_slope", 0.0)),
        float(leaf_cfg.v29_meeple_return_k),
        float(leaf_cfg.v29_farm_flip_k),
        bool(getattr(leaf_cfg, "bag_close", False)),
        bool(leaf_cfg.tile_counting_closure),
        float(leaf_cfg.closure_continuous_slack),
    )


def search_config_rs(cfg, sims: int):
    """`HeuristicPriorConfig` + a sim budget -> ``carc_rs.SearchConfigRs``.

    `exp_fma=True` / `tanh_flavor="glibc_fma"` are the G0 findings for x86-64
    desktop (`np.exp` float64 == glibc `__exp_fma`; `math.tanh` likewise); they
    are what makes the Rust priors bit-identical here. `fpu_reduction=None` is
    the NeuralMCTS legacy `q=0` for unvisited children, and `c_lcb` is inert
    unless `final_select == "lcb"`."""
    import carc_rs

    from .game_wrapper import SCORE_NORM_SCALE

    return carc_rs.SearchConfigRs(
        leaf_config_rs(cfg.leaf_cfg),
        int(sims),
        float(cfg.c_puct),
        float(cfg.tau_p),
        float(cfg.value_norm),
        float(SCORE_NORM_SCALE),
        str(cfg.leaf_quantize),
        str(cfg.final_select),
        None,
        1.0,
        True,
        "glibc_fma",
        False,
    )


def leaf_value_panel_rs(leaf_cfg) -> dict:
    """`champion_factory._leaf_value_panel`, evaluated by the RUST leaf.

    The factory's deepest guard is a panel of leaf OUTPUTS on canonical boards.
    When the champion runs on the Rust backend those outputs are produced by
    `carc_core::leaf`, so the guard has to be evaluated THERE or it proves
    nothing about the agent that will actually play. `MirrorState.
    make_empty_panel_state` builds the identical board the Python panel does
    (empty 35x35, no meeples placed, scores 0, no next tile, hand counts set)."""
    import carc_rs

    from .champion_factory import _LEAF_VALUE_PANEL

    rcfg = leaf_config_rs(leaf_cfg)
    ms = carc_rs.MirrorState.from_seed("0")
    out = {}
    for label, (meeples, kind, _golden) in _LEAF_VALUE_PANEL.items():
        ms.make_empty_panel_state(int(meeples[0]), int(meeples[1]))
        out[label] = (float(ms.leaf_value_float(0, rcfg)) if kind == "float"
                      else int(ms.leaf_value(0, rcfg)))
    return out


def backend_provenance() -> dict:
    """Which carc_rs build is executing — the Rust half of the fingerprint guard."""
    import carc_rs

    tiles_src, tiles_sem = carc_rs.tile_data_digests()
    return {
        "carc_rs_version": str(carc_rs.__version__),
        "carc_rs_path": str(carc_rs.__file__),
        "tile_data_source_sha256": tiles_src,
        "tile_data_semantic_digest": tiles_sem,
    }


# --------------------------------------------------------------------------- #
# The adapter                                                                  #
# --------------------------------------------------------------------------- #
class RustFairAgent:
    """`carc_rs.FairAgentRs` behind the `FairHeuristicPriorAgent` surface.

    Construction mirrors `champion_factory.build_fair_champion`: the caller
    hands the same `game` and `HeuristicPriorConfig` it would hand the Python
    agent, and every knob that changes PLAY (`sims`, `k_dets`, `seed`,
    `exact_endgame`, `exact_max_k`, `min_pooled_visits`, `exact_budget`) has the
    same meaning and the same default. `threads` is the ONE extra knob, and it
    is execution-only: G4 proved the merge bit-identical at threads {1, 4, 8}.
    """

    # Harness symmetry with the Python agent (`neural_moves` is always 0 there).
    neural_moves = 0

    def __init__(self, game, cfg, *, sims: int, k_dets: int, seed: int = 0,
                 exact_endgame: bool = True, exact_max_k: int | None = None,
                 min_pooled_visits: float | None = None,
                 exact_budget: int | None = None, threads: int = 1,
                 window_size: int = 25, start_rule: str | None = None,
                 start_row: int | None = None, start_col: int | None = None,
                 reconcile: bool | None = None):
        import carc_rs

        from . import fair_agent as _fa

        self._game = game
        self._cfg = cfg
        self._sims = int(sims)
        self._k_dets = int(k_dets)
        self._seed = int(seed)
        self._threads = int(threads)
        self._reconcile = reconcile_enabled(reconcile)
        # Defaults READ from fair_agent (point-don't-copy), so the adapter can
        # never quote a budget the Python champion has since moved off.
        self._exact_max_k = int(_fa.EXACT_MAX_K if exact_max_k is None else exact_max_k)
        self._min_pooled_visits = float(
            _fa.DEFAULT_MIN_POOLED_VISITS if min_pooled_visits is None
            else min_pooled_visits)
        self._exact_budget = int(
            _fa.DEFAULT_EXACT_BUDGET if exact_budget is None else exact_budget)
        self._exact_endgame = bool(exact_endgame)

        self._rs = carc_rs.FairAgentRs(
            search_config_rs(cfg, self._sims),
            k_dets=self._k_dets,
            seed=self._seed,
            min_pooled_visits=self._min_pooled_visits,
            exact_endgame=self._exact_endgame,
            exact_max_k=self._exact_max_k,
            exact_budget=self._exact_budget,
            tt_cap=0,
            chance_drop="type",
            threads=self._threads,
            window_size=int(window_size),
            start_rule=start_rule,
            start_row=start_row,
            start_col=start_col,
        )
        self._started = False
        self._plies = 0
        # The harness-wrapper clock (`_MarginalizedHandoff`), computed here.
        self.prefix_moves = 0
        self.prefix_secs = 0.0
        self.total_secs = 0.0
        self.manifest: dict | None = None

    # --- lifecycle ---------------------------------------------------------- #
    def start_game(self, board) -> None:
        """Seat the mirror on the deck THIS board was dealt.

        `[next_tile] + deck` is the engine's draw order (`get_init_board` pops
        the first tile into `next_tile`), so it reconstructs the game exactly —
        with no dependence on how the caller seeded `random`. Verified against
        `start_game_from_seed` on construction when reconcile mode is on."""
        st = board.state
        if st.next_tile is None:
            raise ValueError("start_game needs an INITIAL board (next_tile is None)")
        if self._plies:
            raise RuntimeError(
                "start_game after the mirror has advanced — build a fresh agent "
                "(or call start_game before the first advance)")
        descs = [st.next_tile.description] + [t.description for t in st.deck]
        self._rs.start_game_from_deck(descs)
        self._started = True
        self._plies = 0
        self.prefix_moves = 0
        self.prefix_secs = 0.0
        self.total_secs = 0.0
        self._check_sync(board, "start_game")

    def start_game_from_seed(self, deck_seed: int | str) -> None:
        """`random.seed(deck_seed); Game().get_init_board()` — the farms/tests path."""
        self._rs.start_game_from_seed(str(deck_seed))
        self._started = True
        self._plies = 0
        self.prefix_moves = 0
        self.prefix_secs = 0.0
        self.total_secs = 0.0

    def close(self) -> None:
        """No-op — the Rust agent owns no processes (the Python k-parallel
        champion's spawn pool is what `close()` exists for there). Present so
        the adapter is drop-in for `contextlib.closing`-style callers."""

    def __del__(self):                      # pragma: no cover - teardown
        try:
            self.close()
        except Exception:
            pass

    # --- the single mirror choke point -------------------------------------- #
    def advance(self, action: int, board_after=None) -> None:
        """Apply ONE action to the mirror. Call for EVERY applied action, BOTH seats.

        `board_after` is optional and only read in reconcile mode, where it is
        asserted equal to the post-action mirror."""
        if not self._started:
            raise RuntimeError("advance before start_game()")
        self._rs.advance(int(action))
        self._plies += 1
        if board_after is not None:
            self._check_sync(board_after, f"advance({action})")

    # --- the decision ------------------------------------------------------- #
    def choose_action(self, board, move_idx: int | None = None) -> int:
        """Pick the fair move for `board`. Never mutates the caller's board.

        The mirror must already BE at `board` (see `advance`). `move_idx`
        defaults to the agent's own counter, which always advances — the same
        contract `FairHeuristicPriorAgent._move_idx` has."""
        if not self._started:
            # A caller that only ever calls choose_action/advance still gets a
            # correctly seated mirror instead of a RuntimeError.
            self.start_game(board)
        self._check_sync(board, "choose_action")
        solver_before = float(self._rs.stats()["solver_secs"])
        t0 = time.perf_counter()
        action = int(self._rs.choose_action(None if move_idx is None else int(move_idx)))
        dt = time.perf_counter() - t0
        self.total_secs += dt
        m = self._rs.last_move()
        # The `_MarginalizedHandoff` split: a decision the SOLVER owned costs no
        # prefix time and is not a prefix move; anything else ran a PIMC search
        # (including the BudgetExceeded fallback, whose dead solve is subtracted).
        if not bool(m["exact"]):
            solver_delta = float(self._rs.stats()["solver_secs"]) - solver_before
            self.prefix_secs += max(0.0, dt - solver_delta)
            self.prefix_moves += 1
        return action

    move = choose_action

    # --- reconcile ---------------------------------------------------------- #
    def _check_sync(self, board, where: str) -> None:
        if not self._reconcile:
            return
        self.check_sync(board, where)

    def check_sync(self, board, where: str = "check_sync") -> None:
        """Hard-assert the mirror equals `board`, unconditionally.

        Compares the byte-exact `string_representation` — the node key G1 gated,
        which encodes board, phase, scores, meeples, next tile and the last tile
        action. A digest is compared too so the failure message can say WHICH."""
        want = self._game.string_representation(board)
        got = self._rs.string_repr()
        if want == got:
            return
        raise MirrorDesync(
            f"rust mirror desync at {where} (ply {self._plies}, "
            f"move_idx {self.move_idx}): python digest "
            f"{_short(want)} != rust digest {_short(got)}\n"
            f"  python: {want[:400]}\n"
            f"  rust  : {got[:400]}")

    # --- read-off ----------------------------------------------------------- #
    @property
    def move_idx(self) -> int:
        return int(self._rs.stats()["move_idx"])

    @property
    def _move_idx(self) -> int:
        """`FairHeuristicPriorAgent._move_idx` — the same counter, same name."""
        return self.move_idx

    @_move_idx.setter
    def _move_idx(self, value: int) -> None:
        # Seatable, like the Python attribute: a harness that drops the agent
        # onto a recorded ply owns the move timeline (and the det seeds derive
        # from it), so it must be able to say which move this is.
        self._rs.set_move_idx(int(value))

    @property
    def _latched(self) -> bool:
        return bool(self._rs.stats()["latched"])

    @_latched.setter
    def _latched(self, value: bool) -> None:
        # The latch is a function of the game's HISTORY, so a harness that jumps
        # the agent onto a mid-game position via advance() alone — never running
        # choose_action, hence never evaluating the trigger — must seat it.
        self._rs.set_latched(bool(value), self._rs.stats()["latch_k"])

    @property
    def latch_k(self):
        return self._rs.stats()["latch_k"]

    @latch_k.setter
    def latch_k(self, value) -> None:
        self._rs.set_latched(bool(self._rs.stats()["latched"]),
                             None if value is None else int(value))

    @property
    def heur_moves(self) -> int:
        return int(self._rs.stats()["heur_moves"])

    @property
    def forced_moves(self) -> int:
        return int(self._rs.stats()["forced_moves"])

    @property
    def exact_moves(self) -> int:
        return int(self._rs.stats()["exact_moves"])

    @property
    def n_timeouts(self) -> int:
        return int(self._rs.stats()["n_timeouts"])

    @property
    def solver_secs(self) -> float:
        return float(self._rs.stats()["solver_secs"])

    @property
    def solver_nodes(self) -> int:
        return int(self._rs.stats()["solver_nodes"])

    @property
    def max_solve_secs(self) -> float:
        return float(self._rs.stats()["max_solve_secs"])

    @property
    def last_pooled_visits(self) -> dict:
        """`{action: visits}` in POOL INSERTION order (dicts keep it)."""
        return {int(a): float(v) for a, v in self._rs.stats()["last_pooled_visits"]}

    def det_seed_base(self, move_idx: int) -> int:
        return int(self._rs.det_seed_base(int(move_idx)))

    def det_search_seed(self, move_idx: int, det_idx: int) -> int:
        return int(self._rs.det_search_seed(int(move_idx), int(det_idx)))

    def last_move(self) -> dict:
        """The last decision's raw record (pooled floats as raw f64 BITS)."""
        return dict(self._rs.last_move())

    def string_repr(self) -> str:
        return self._rs.string_repr()

    def state_digest(self) -> str:
        return self._rs.state_digest()

    def stats(self) -> dict:
        """Every counter the eval harness reads, in BOTH shapes.

        Agent shape (`FairHeuristicPriorAgent`) and wrapper shape
        (`eval_fair_puct._MarginalizedHandoff`: `prefix_moves`/`prefix_secs`),
        plus the resolved config so a manifest never has to guess which budget
        and which execution mode produced a number."""
        s = self._rs.stats()
        return {
            # --- FairHeuristicPriorAgent ---
            "neural_moves": 0,
            "heur_moves": int(s["heur_moves"]),
            "forced_moves": int(s["forced_moves"]),
            "exact_moves": int(s["exact_moves"]),
            "n_timeouts": int(s["n_timeouts"]),
            "solver_secs": float(s["solver_secs"]),
            "solver_nodes": int(s["solver_nodes"]),
            "max_solve_secs": float(s["max_solve_secs"]),
            "latched": bool(s["latched"]),
            "latch_k": s["latch_k"],
            "move_idx": int(s["move_idx"]),
            "last_pooled_visits": self.last_pooled_visits,
            # --- _MarginalizedHandoff (the champ_prefix_ms_per_move clock) ---
            "prefix_moves": int(self.prefix_moves),
            "prefix_secs": float(self.prefix_secs),
            "total_secs": float(self.total_secs),
            "ms_per_move": (1e3 * self.total_secs / self.move_idx
                            if self.move_idx else 0.0),
            # --- resolved config ---
            "backend": "rust",
            "sims_per_det": int(s["sims_per_det"]),
            "k_dets": int(s["k_dets"]),
            "threads": int(s["threads"]),
            "seed": int(s["seed"]),
            "exact_max_k": int(s["exact_max_k"]),
            "exact_budget": int(s["exact_budget"]),
            "min_pooled_visits": float(s["min_pooled_visits"]),
            "reconcile": bool(self._reconcile),
            "plies_advanced": int(self._plies),
        }

    def __repr__(self) -> str:
        return (f"RustFairAgent(k{self._k_dets}x{self._sims}, seed={self._seed}, "
                f"threads={self._threads}, exact_max_k={self._exact_max_k}, "
                f"reconcile={self._reconcile})")


def _short(s: str) -> str:
    import hashlib

    return hashlib.sha256(s.encode()).hexdigest()[:16]
