"""Phase 1.1 — PUCT with heuristic-leaf priors (classical-search variant).

Builds "PUCT-with-heuristic-priors" by wiring a HEURISTIC EVALUATOR into the
existing, tested PUCT machinery in ``mcts.NeuralMCTS``. There is NO new
selection loop and NO change to ``HeuristicMCTS`` / ``NeuralMCTS`` — this module
only ADDs. The production ``HeuristicMCTS`` random-expansion UCT path stays
byte-for-byte unchanged (this is a sibling agent behind its own factory).

Pre-registration: ``measurement/classical_search/PLAN.md`` (H1.1).

Design (settled in the build brief):
  * The evaluator conforms to the ``NeuralMCTS`` contract
    ``Callable[[Board], (priors[A], value)]``:

        mover  = board.state.current_player
        leaf_p = leaf(board.state, mover, cfg)      # int- or float-quantized
        value  = tanh(leaf_p / value_norm)          # mover POV — SAME convention
                                                    # as HeuristicMCTS._rollout
        priors = softmax_over_legal(Δleaf(a) / τ_p) scattered into a length-A
                 vector (0 elsewhere), where
                 Δleaf(a) = leaf(child_a.state, mover, cfg) − leaf_p
                 (per-child afterstate eval, from the MOVER's POV).

  * ``NeuralMCTS`` already implements PUCT selection
    ``score = Q + c·P·sqrt(ΣN)/(1+N)`` with expand-all-priors-at-once (all legal
    children receive a prior at expansion and compete immediately), which IS the
    "expand-all replaces one-random-child-per-sim" the plan wants.

  * Config knobs (all recorded in the harness manifest): ``c_puct``, ``τ_p``,
    ``leaf_quantize ∈ {int, float}``, ``final_select ∈ {visits, Q}``,
    ``value_norm``, and the leaf ``LeafConfig``.

Leaf value POV / sign was verified against both the champion and NeuralMCTS:
  * ``HeuristicMCTS._rollout`` (mcts.py:344-356) returns
    ``tanh(virtual_score_v2(state, current_player, cfg) / value_norm)`` — mover POV.
  * ``NeuralMCTS`` expects the evaluator's value in [-1,1] from
    ``board.state.current_player``'s POV (mcts.py:419-421, backprop 1245-1251).
  These agree, so ``value = tanh(leaf(state, current_player)/norm)`` is correct
  with no extra sign flip.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import flat_leaf
from .game_wrapper import Board, Game
from .mcts import DEFAULT_PUCT_C, HEURISTIC_VALUE_NORM, NeuralMCTS
from .virtual_score_v2 import DEFAULT_CONFIG


# --------------------------------------------------------------------------- #
# Leaf — the v2.9 flat leaf, quantized (int) or raw (float).                   #
# --------------------------------------------------------------------------- #
def leaf_score_float(state, player: int, cfg) -> float:
    """The v2.9 flat leaf WITHOUT the final ``int(round(...))``.

    Byte-for-byte the pure-Python path of ``flat_leaf.flat_virtual_score_v2``
    (flat_leaf.py:823-838) with the terminal ``int(round(score))`` removed —
    i.e. the pre-quantization float leaf. ``leaf_quantize="int"`` is exactly
    ``int(round(leaf_score_float(...)))`` so the int/float knob differs ONLY by
    rounding (the plan's stated semantics for ``leaf_quantize``).

    ``bag_close`` is resolved from ``cfg.bag_close`` (production v2.9 Bmild_cap8
    → False); the deck-aware / v2.8 / v2.9-non-curve configs are not reachable
    here (the harness always passes a curve-only Bmild config, which the object
    path also routes through flat). A ``tests`` assertion checks this reproduction
    stays within the known ±1 of the production (Cython) int leaf.
    """
    if state.players != 2:
        raise ValueError(
            f"heuristic-prior leaf is 2-player only; got {state.players}"
        )
    bag_close = bool(getattr(cfg, "bag_close", False))
    decomp = flat_leaf.decompose(state)
    opp = 1 - player
    bag = flat_leaf._bag_stats(state) if bag_close else None
    base = flat_leaf.flat_base_score(state, player, decomp)
    bonus_self = flat_leaf._capped(
        flat_leaf.flat_closure_bonus(state, player, decomp, cfg, bag), cfg.bonus_cap
    )
    bonus_opp = flat_leaf._capped(
        flat_leaf.flat_closure_bonus(state, opp, decomp, cfg, bag), cfg.opp_bonus_cap
    )
    score = base + bonus_self - bonus_opp
    curve = cfg.v29_meeple_curve
    if curve is not None:
        score += (
            flat_leaf._flat_curve_lookup(curve, state.meeples[player])
            - flat_leaf._flat_curve_lookup(curve, state.meeples[opp])
        )
    elif cfg.meeple_k > 0.0:
        score += cfg.meeple_k * (state.meeples[player] - state.meeples[opp])
    return float(score)


# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #
@dataclass
class HeuristicPriorConfig:
    """Resolved knobs for the PUCT-with-heuristic-priors agent.

    c_puct        PUCT exploration constant.
    tau_p         prior softmax temperature over Δleaf (afterstate gains).
    leaf_quantize "int" (round) | "float" (raw pre-round leaf).
    final_select  "Q" (NeuralMCTS.best_action's Q-then-N rule) |
                  "visits" (argmax root visit count) |
                  "lcb" (max of a lower-confidence bound on Q, see c_lcb).
    value_norm    tanh denominator for the leaf value (matches HeuristicMCTS).
    leaf_cfg      virtual_score_v2.LeafConfig; None -> env-built DEFAULT_CONFIG
                  (= the v2.9 Bmild_cap8 leaf when the production env is set).
    c_lcb         LCB exploration penalty coefficient — ONLY read when
                  final_select == "lcb". score(a) = Q(a) - c_lcb * sqrt(ln(ΣN)/N(a)),
                  ΣN = sum of the (deduped) root children's visit counts; children
                  with N(a)==0 score -inf (never selected). Default 1.0 (a standard
                  LCB weight; halfway between greedy Q and pure visits). This ONLY
                  changes the FINAL root move choice — never the search itself.
    reuse_tree    False (default) -> the agent clear()s the tree before every move
                  (byte-for-byte the champion). True -> the agent PERSISTS the PUCT
                  tree across moves and RE-ROOTS into the node for the next board it
                  is asked about, keeping that subtree's statistics (falls back to a
                  fresh clear()ed search when the board isn't in the retained tree,
                  or when a transposition-key collision would serve a wrong-rotation
                  subtree). See HeuristicPriorAgent._reroot_or_clear.
    root_select   "puct" (default) -> the ROOT edge of every simulation is chosen by
                  the SAME PUCT rule as interior nodes (byte-for-byte the champion).
                  "gumbel" -> Gumbel-root / sequential-halving action selection
                  (Danihelka et al. 2022): sample m candidate root actions by
                  Gumbel-top-k on the true logits, then spend the simulation budget
                  via sequential halving with FORCED root actions (interior descent
                  stays PUCT). Simple-regret-correct at the root; gains are largest at
                  LOW budget. Overrides final_select (Gumbel IS the final choice).
    gumbel_m      Gumbel top-m candidate count (clamped to n_legal). Default 16.
    gumbel_c_visit  σ-transform visit constant c_visit. Default 50.0 (mctx default).
    gumbel_c_scale  σ-transform value scale c_scale. Default 1.0 (mctx default).
                  σ(q) = (c_visit + max_b N_b) * c_scale * q — the monotone map that
                  puts the completed-Q on the logit scale.
    gumbel_retain_g  Whether the per-candidate Gumbel noise g is RETAINED through the
                  sequential-halving elimination. True (default, paper-exact /
                  Danihelka 2022) -> each phase keeps the top-half by
                  g + logits + σ(completedQ) using the SAME g drawn for the initial
                  top-m, so the surviving action carries g (a proper Gumbel-top-k
                  argmax over the sampled set). False -> g is used ONLY for the
                  initial top-m draw; halving/elimination ranks by logits +
                  σ(completedQ) without g. A/B'd via --gumbel-retain-g /
                  --no-gumbel-retain-g. Only read when root_select == "gumbel".

    NOTE: c_lcb / reuse_tree / root_select DEFAULT to a no-op (final_select stays
    "Q"/"visits", reuse stays off, root_select stays "puct"); the defaults reproduce
    the champion byte-for-byte
    (tests/test_heuristic_prior_mcts.py::test_bit_exact_all_flags_off).
    """

    c_puct: float = DEFAULT_PUCT_C
    tau_p: float = 5.0
    leaf_quantize: str = "float"
    final_select: str = "Q"
    value_norm: float = HEURISTIC_VALUE_NORM
    leaf_cfg: object = None
    c_lcb: float = 1.0
    reuse_tree: bool = False
    root_select: str = "puct"
    gumbel_m: int = 16
    gumbel_c_visit: float = 50.0
    gumbel_c_scale: float = 1.0
    gumbel_retain_g: bool = True

    def __post_init__(self):
        if self.leaf_quantize not in ("int", "float"):
            raise ValueError(
                f"leaf_quantize must be 'int'|'float'; got {self.leaf_quantize!r}"
            )
        if self.final_select not in ("Q", "visits", "lcb"):
            raise ValueError(
                f"final_select must be 'Q'|'visits'|'lcb'; got {self.final_select!r}"
            )
        if self.root_select not in ("puct", "gumbel"):
            raise ValueError(
                f"root_select must be 'puct'|'gumbel'; got {self.root_select!r}"
            )
        if int(self.gumbel_m) < 1:
            raise ValueError(f"gumbel_m must be >= 1; got {self.gumbel_m!r}")

    def resolved_leaf_cfg(self):
        return self.leaf_cfg if self.leaf_cfg is not None else DEFAULT_CONFIG

    def as_manifest(self) -> dict:
        """JSON-serializable resolved config for a run manifest."""
        import dataclasses as _dc

        lc = self.resolved_leaf_cfg()
        leaf = {
            k: (list(v) if isinstance(v, tuple) else v)
            for k, v in _dc.asdict(lc).items()
        }
        return {
            "c_puct": self.c_puct,
            "tau_p": self.tau_p,
            "leaf_quantize": self.leaf_quantize,
            "final_select": self.final_select,
            "value_norm": self.value_norm,
            "c_lcb": self.c_lcb,
            "reuse_tree": self.reuse_tree,
            "root_select": self.root_select,
            "gumbel_m": self.gumbel_m,
            "gumbel_c_visit": self.gumbel_c_visit,
            "gumbel_c_scale": self.gumbel_c_scale,
            "gumbel_retain_g": self.gumbel_retain_g,
            "leaf_cfg": leaf,
        }


# --------------------------------------------------------------------------- #
# Evaluator                                                                    #
# --------------------------------------------------------------------------- #
def make_heuristic_prior_evaluator(game: Game, cfg: HeuristicPriorConfig):
    """Return a ``Callable[[Board], (priors[A], value)]`` for NeuralMCTS.

    Uses ``game`` to step to each legal child (``get_next_state`` — does NOT
    mutate the input board and does not touch the legal-move cache), so it is
    safe to share the SAME game with the owning NeuralMCTS.
    """
    leaf_cfg = cfg.resolved_leaf_cfg()
    tau = float(cfg.tau_p)
    norm = float(cfg.value_norm)
    action_size = game.get_action_size()
    # bag_close resolved from the leaf cfg (production v2.9 Bmild_cap8 -> False),
    # mirroring leaf_score_float; passed explicitly so the CYTHON leaf takes the
    # same v2.9/v2.10 branch as the pure-Python reference.
    bag_close = bool(getattr(leaf_cfg, "bag_close", False))

    if cfg.leaf_quantize == "int":
        # Cython int leaf via flat_leaf dispatch (== the production v2.9 leaf, the
        # SAME call the champion HeuristicMCTS._rollout makes) — falls back to the
        # pure-Python flat path only if the .so is absent. ~30x faster per leaf
        # than int(round(leaf_score_float(...))); int-rounds so it loses sub-point
        # prior resolution (the reference/quantized cell).
        def leaf(state, player: int) -> float:
            return float(flat_leaf.flat_virtual_score_v2(state, player, leaf_cfg, bag_close))
    else:  # "float" — validated in HeuristicPriorConfig.__post_init__
        # Cython PRE-ROUND float leaf: same v2.9 semantics, full sub-integer
        # resolution for the softmax priors, at Cython speed. `leaf_score_float`
        # (pure-Python) stays as the reference/fallback; flat_virtual_score_v2_float
        # falls back to it automatically when the .so is missing.
        def leaf(state, player: int) -> float:
            return flat_leaf.flat_virtual_score_v2_float(state, player, leaf_cfg, bag_close)

    def _legal_deltas(board: Board):
        """Return (legal_actions, deltas, leaf_parent) for `board`.

        ``deltas[i] = leaf(child_a_i.state, mover) - leaf_parent`` is the per-child
        afterstate leaf gain Δleaf(a) from the MOVER's POV, in ``legal`` order
        (``np.flatnonzero`` ascending). Shared by the softmax-prior evaluator and
        the Gumbel driver's ``root_logits`` so the pre-softmax logits ``z=Δleaf/τ``
        need no re-derivation from log(softmax). Never mutates ``board`` (steps via
        ``game.get_next_state``, which leaves the legal-move cache untouched)."""
        st = board.state
        mover = st.current_player
        leaf_parent = leaf(st, mover)
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        deltas = np.empty(legal.size, dtype=np.float64)
        for i, a in enumerate(legal):
            child, _ = game.get_next_state(board, int(a))
            deltas[i] = leaf(child.state, mover) - leaf_parent
        return legal, deltas, leaf_parent

    def evaluator(board: Board):
        legal, deltas, leaf_parent = _legal_deltas(board)
        value = math.tanh(leaf_parent / norm)

        priors = np.zeros(action_size, dtype=np.float32)
        if legal.size == 0:
            # NeuralMCTS._expand_with_priors handles legal.size==0 itself
            # (leaf_value=0, ignores these priors); return a valid shape anyway.
            return priors, value

        # softmax(Δleaf / τ) over legal actions (numerically stabilized).
        z = deltas / tau
        z -= z.max()
        w = np.exp(z)
        w /= w.sum()
        priors[legal] = w.astype(np.float32)
        return priors, value

    def root_logits(board: Board):
        """Return (legal_actions, z) with z = Δleaf/τ — the TRUE pre-softmax logits.

        The Gumbel-root driver needs the *unnormalized* logits (NOT log(softmax),
        which silently rescales by the softmax normalizer): the completed-Q term
        logits + σ(completedQ) is scale-sensitive, so the constant the softmax
        subtracts would corrupt the improved-policy ranking. Recomputed fresh at the
        root once per move (n_legal extra leaf evals, negligible vs the sim budget)."""
        legal, deltas, _ = _legal_deltas(board)
        return legal, (deltas / tau)

    # Provenance / introspection hooks (mirrors evaluators._V25Wrapped).
    evaluator.heur_prior_cfg = cfg
    evaluator.leaf_cfg = leaf_cfg
    evaluator.leaf_name = f"v29_prior_{cfg.leaf_quantize}"
    evaluator.root_logits = root_logits
    return evaluator


# --------------------------------------------------------------------------- #
# Deck-aware NET-value evaluator (C-cheap) — IDENTICAL heuristic priors, but the #
# leaf value is a learned deck-aware net value on the sighted (81ch/42-scalar)   #
# representation. See docs C_CHEAP spec §3: "the C-cheap swap = replace the value #
# line, keep the priors." The priors path is BYTE-IDENTICAL to                   #
# make_heuristic_prior_evaluator (we reuse it verbatim and discard only its       #
# heuristic value), so a fair A/B isolates the value component.                   #
# --------------------------------------------------------------------------- #
def make_heuristic_prior_evaluator_with_net_value(
    game: Game, cfg: HeuristicPriorConfig, net, sighted_game: Game | None = None,
    device=None,
):
    """Return a ``Callable[[Board], (priors[A], value)]`` whose PRIORS are
    byte-identical to ``make_heuristic_prior_evaluator(game, cfg)`` but whose
    VALUE is the learned deck-aware net value
    ``net_value(sighted_encode(board.state, mover))`` — the mover-POV sighted
    (81ch / 42-scalar) observation fed through ``net``'s value head.

    The priors are guaranteed identical because we build the base heuristic
    evaluator and REUSE its ``(priors, _)`` output verbatim, only substituting
    the value — there is no re-derivation of the softmax(Δleaf/τ) logits, so the
    only measured difference vs the heuristic-value fair champion is the value.

    Parameters
    ----------
    game : Game            the SAME (blind) engine wrapper the owning NeuralMCTS
                           steps children through — passed straight to the base
                           heuristic evaluator (priors path unchanged).
    cfg : HeuristicPriorConfig  champion knobs (c_puct/τ_p/leaf/value_norm).
    net : CarcassonneNet   an 81ch / 42-scalar sighted net (policy+value); only
                           the value head is read. Put it in eval() mode.
    sighted_game : Game    a ``Game(sighted=True)`` used ONLY to encode the board
                           into the deck-aware observation (board.offset/state/
                           total_tiles are on the Board, so a separate encoder
                           Game is correctness-neutral). Built here if None.
    device                 torch device for the forward; defaults to the net's
                           own parameter device (CPU under the eval env, which
                           sets CUDA_VISIBLE_DEVICES="").

    NOTE — the net value is a SINGLE-board eager forward per leaf (the NeuralMCTS
    serial evaluator contract, ``batch_size=1``). For the real n≈100 fair A/B this
    is the perf bottleneck; batching (orch / GPU) is a follow-up, not needed for
    correctness or the plumbing smoke.
    """
    import torch

    if net is None:
        raise ValueError("make_heuristic_prior_evaluator_with_net_value: net is None")

    base = make_heuristic_prior_evaluator(game, cfg)

    if sighted_game is None:
        sighted_game = Game(
            players=game.players,
            tile_sets=list(game.tile_sets),
            supplementary_rules=list(game.supplementary_rules),
            window_size=game.window_size,
            sighted=True,
        )
    if not getattr(sighted_game, "sighted", False):
        raise ValueError(
            "sighted_game must be a Game(sighted=True) — the deck-aware net value "
            "reads the +3 farm planes / +32 bag scalars"
        )

    # Fail loudly on a rep/net dim mismatch rather than a cryptic cat/matmul error.
    exp_ch = sighted_game.get_input_channels()
    exp_scl = sighted_game.get_scalar_feature_size()
    net_ch = int(getattr(net, "stem", [None])[0].in_channels) if hasattr(net, "stem") else None
    if net_ch is not None and net_ch != exp_ch:
        raise ValueError(
            f"net input channels ({net_ch}) != sighted encode channels ({exp_ch}); "
            "the net must be an 81ch sighted net"
        )
    net_scl = int(getattr(net, "value_fc1").in_features) if hasattr(net, "value_fc1") else None
    # value_fc1 in_features = value_flat + n_scalar (+ 2*n_filters if global pool),
    # so we can only *lower-bound* n_scalar from it; assert the exact scalar count
    # via the policy_fc instead (policy_flat + n_scalar), which has no global-pool add.
    if hasattr(net, "policy_fc") and hasattr(net, "policy_project"):
        try:
            pol_project_ch = net.policy_project[0].out_channels
            policy_flat = pol_project_ch * sighted_game.window_size * sighted_game.window_size
            net_scl_exact = int(net.policy_fc.in_features) - policy_flat
            if net_scl_exact != exp_scl:
                raise ValueError(
                    f"net scalar features ({net_scl_exact}) != sighted scalars ({exp_scl}); "
                    "the net must be a 42-scalar sighted net"
                )
        except (AttributeError, IndexError):
            pass

    if device is None:
        try:
            device = next(net.parameters()).device
        except StopIteration:
            device = torch.device("cpu")
    net.eval()

    def _net_value(board: Board) -> float:
        mover = board.state.current_player
        obs, scl = sighted_game.get_canonical_form(board, mover)
        obs_t = torch.from_numpy(np.ascontiguousarray(obs, dtype=np.float32)).unsqueeze(0).to(device)
        scl_t = torch.from_numpy(np.ascontiguousarray(scl, dtype=np.float32)).unsqueeze(0).to(device)
        with torch.no_grad():
            _logits, value = net(obs_t, scl_t)
        return float(value.reshape(-1)[0].item())

    def evaluator(board: Board):
        # Byte-identical priors (base returns (priors, heuristic_value)); we keep
        # the priors and swap ONLY the value.
        priors, _heur_value = base(board)
        return priors, _net_value(board)

    # Provenance / introspection hooks (mirror the heuristic evaluator + expose the
    # net-value wiring for tests). root_logits is inherited so the Gumbel driver
    # keeps working if this evaluator is ever used clairvoyantly.
    evaluator.heur_prior_cfg = cfg
    evaluator.leaf_cfg = base.leaf_cfg
    evaluator.leaf_name = f"{base.leaf_name}_netvalue"
    evaluator.root_logits = base.root_logits
    evaluator.net = net
    evaluator.sighted_game = sighted_game
    evaluator.heuristic_base = base  # tests assert priors == base priors
    return evaluator


# --------------------------------------------------------------------------- #
# C-cheap v2 — sighted mover-POV net VALUE forward, factored out so the         #
# residual evaluator (and the orch/CPU eval harness) build the SAME forward the  #
# replace-mode `_net_value` uses. This does NOT touch                            #
# make_heuristic_prior_evaluator_with_net_value (CL-049 provenance): it is a      #
# byte-identical re-construction of that factory's `_net_value` body, exposed as  #
# a reusable `value_fn(board) -> float`.                                          #
# --------------------------------------------------------------------------- #
def make_sighted_net_value_fn(
    game: Game, net, sighted_game: Game | None = None, device=None,
):
    """Return ``(value_fn, sighted_game)`` where ``value_fn(board) -> float`` is the
    mover-POV sighted (81ch/42-scalar) net value — the SAME forward the replace-mode
    ``make_heuristic_prior_evaluator_with_net_value._net_value`` computes
    (``get_canonical_form(board, mover)`` → net → ``value``). Used to build the
    residual evaluator's ``value_fn`` for the CPU net path (the orch path builds its
    own ``value_fn`` from the SHM handles).
    """
    import torch

    if net is None:
        raise ValueError("make_sighted_net_value_fn: net is None")

    if sighted_game is None:
        sighted_game = Game(
            players=game.players,
            tile_sets=list(game.tile_sets),
            supplementary_rules=list(game.supplementary_rules),
            window_size=game.window_size,
            sighted=True,
        )
    if not getattr(sighted_game, "sighted", False):
        raise ValueError(
            "sighted_game must be a Game(sighted=True) — the deck-aware net value "
            "reads the +3 farm planes / +32 bag scalars"
        )

    # Loud fail on a rep/net channel mismatch (mirrors the replace factory's guard).
    exp_ch = sighted_game.get_input_channels()
    net_ch = int(getattr(net, "stem", [None])[0].in_channels) if hasattr(net, "stem") else None
    if net_ch is not None and net_ch != exp_ch:
        raise ValueError(
            f"net input channels ({net_ch}) != sighted encode channels ({exp_ch}); "
            "the net must be an 81ch sighted net"
        )

    if device is None:
        try:
            device = next(net.parameters()).device
        except StopIteration:
            device = torch.device("cpu")
    net.eval()

    def value_fn(board: Board) -> float:
        mover = board.state.current_player
        obs, scl = sighted_game.get_canonical_form(board, mover)
        obs_t = torch.from_numpy(np.ascontiguousarray(obs, dtype=np.float32)).unsqueeze(0).to(device)
        scl_t = torch.from_numpy(np.ascontiguousarray(scl, dtype=np.float32)).unsqueeze(0).to(device)
        with torch.no_grad():
            _logits, value = net(obs_t, scl_t)
        return float(value.reshape(-1)[0].item())

    value_fn.net = net
    value_fn.sighted_game = sighted_game
    return value_fn, sighted_game


# --------------------------------------------------------------------------- #
# C-cheap v2 — RESIDUAL deck-aware value. Sibling of the CL-049 REPLACE factory   #
# (make_heuristic_prior_evaluator_with_net_value). The priors are BYTE-IDENTICAL  #
# to make_heuristic_prior_evaluator (reused verbatim); the value is the SHARP      #
# heuristic leaf value PLUS a small learned nudge:                                 #
#     v = tanh(leaf/norm) + λ · value_fn(board)     (CLIPPED to [-1,1], NOT re-tanh)#
# Rationale (C_CHEAP v2): v1 REPLACE nuked the local afterstate discrimination the #
# fair pooled-Q agent needs (W0/L100). The RESIDUAL keeps the heuristic's local     #
# ranking and only lets the net move subtree-level Q. λ=0 ⇒ BYTE-IDENTICAL to the  #
# heuristic-value evaluator (value AND priors), so a fair A/B isolates the nudge.   #
# --------------------------------------------------------------------------- #
def make_heuristic_prior_evaluator_with_residual_value(
    game: Game, cfg: HeuristicPriorConfig, value_fn, lam,
):
    """Return a ``Callable[[Board], (priors[A], value)]`` whose PRIORS are
    byte-identical to ``make_heuristic_prior_evaluator(game, cfg)`` and whose VALUE
    is ``heur_value + λ · value_fn(board)``, clipped to [-1, 1] (NOT re-tanh'd).

    Parameters
    ----------
    game : Game            the SAME (blind) engine wrapper the owning NeuralMCTS
                           steps children through (priors path unchanged).
    cfg : HeuristicPriorConfig  champion knobs (c_puct/τ_p/leaf/value_norm).
    value_fn : Callable[[Board], float]  the learned mover-POV nudge — the sighted
                           net value forward (build via make_sighted_net_value_fn for
                           a CPU net, or the orch remote single evaluator's value).
    lam : float            residual blend weight λ (a plain float).

    INVARIANT: with ``lam == 0.0`` the evaluator output is BYTE-IDENTICAL to
    ``make_heuristic_prior_evaluator(game, cfg)`` — value AND priors — because the
    base heuristic value is already in (-1, 1) so the clip is a no-op, and
    ``heur + 0.0 * value_fn(board) == heur`` for any finite forward.
    """
    if value_fn is None:
        raise ValueError(
            "make_heuristic_prior_evaluator_with_residual_value: value_fn is None"
        )

    base = make_heuristic_prior_evaluator(game, cfg)
    lam_f = float(lam)

    def evaluator(board: Board):
        # Byte-identical priors (base returns (priors, heuristic_value)); keep the
        # priors, nudge ONLY the value by λ · value_fn(board), then clip (no re-tanh).
        priors, heur_value = base(board)
        v = heur_value + lam_f * value_fn(board)
        return priors, min(1.0, max(-1.0, v))

    # Provenance / introspection hooks (mirror the net-value evaluator).
    evaluator.heur_prior_cfg = cfg
    evaluator.leaf_cfg = base.leaf_cfg
    evaluator.leaf_name = f"{base.leaf_name}_residual_lam{lam_f:g}"
    evaluator.root_logits = base.root_logits
    evaluator.heuristic_base = base  # tests assert priors == base priors
    evaluator.value_fn = value_fn
    evaluator.net_lambda = lam_f
    if hasattr(value_fn, "net"):
        evaluator.net = value_fn.net
    if hasattr(value_fn, "sighted_game"):
        evaluator.sighted_game = value_fn.sighted_game
    return evaluator


# --------------------------------------------------------------------------- #
# Agent                                                                        #
# --------------------------------------------------------------------------- #
class HeuristicPriorAgent:
    """PUCT-with-heuristic-priors, uniform ``.best_action(board)`` / ``.move``.

    Wraps ``NeuralMCTS`` with the heuristic evaluator. ``final_select`` chooses
    the root move rule: "Q" uses ``NeuralMCTS.best_action`` (Q-then-N tiebreak);
    "visits" uses argmax of the root visit distribution.

    Determinism: given a fixed ``seed`` and a fixed deck (clairvoyant descent of
    the true deck, ``fair_chance=False``), the played move sequence is fixed —
    the leaf and stepping are deterministic and PUCT tie-breaks are index-order.
    """

    def __init__(
        self,
        game: Game,
        cfg: HeuristicPriorConfig,
        simulations: int,
        seed: int | None = None,
        reuse_tree: bool | None = None,
    ):
        self.game = game
        self.cfg = cfg
        self.simulations = int(simulations)
        self._final_select = cfg.final_select
        # reuse_tree resolves from the config unless overridden at construction
        # (the override lets tests / direct callers flip it without a new cfg).
        # Default None -> cfg.reuse_tree (False) -> byte-for-byte the champion.
        self._reuse_tree = bool(cfg.reuse_tree) if reuse_tree is None else bool(reuse_tree)
        self.evaluator = make_heuristic_prior_evaluator(game, cfg)
        self.mcts = NeuralMCTS(
            game=game,
            evaluator=self.evaluator,
            simulations=self.simulations,
            c_puct=cfg.c_puct,
            seed=seed,
        )
        # Harness-symmetry counters (mirror the hybrid/exact agents).
        self.neural_moves = 0
        self.heur_moves = 0
        self.latch_k = None
        # Tree-reuse bookkeeping (introspection / tests): per-move outcome of the
        # re-root attempt. reuse_hits = re-rooted into a retained subtree;
        # reuse_fresh = board absent from the tree -> fresh search; reuse_collide =
        # transposition-key collision (wrong-rotation subtree) -> fresh search.
        self.reuse_hits = 0
        self.reuse_fresh = 0
        self.reuse_collide = 0

    def clear(self) -> None:
        self.mcts.clear()

    def best_action(self, board: Board) -> int:
        if self.cfg.root_select == "gumbel":
            # Gumbel-root / sequential-halving IS the final selection (it overrides
            # final_select) and runs its own forced-root sim budget instead of the
            # PUCT-root self.mcts.search.
            return self._gumbel_root_search(board)
        self.mcts.search(board)  # runs exactly `simulations` PUCT sims
        if self._final_select == "visits":
            counts, actions = self.mcts.root_visit_distribution(board)
            return int(actions[int(np.argmax(counts))])
        if self._final_select == "lcb":
            return self._lcb_action(board)
        return int(self.mcts.best_action(board))

    def _lcb_action(self, board: Board) -> int:
        """Pick the root child maximizing a lower-confidence bound on Q:

            score(a) = Q(a) - c_lcb * sqrt( ln(ΣN) / N(a) )

        where Q(a) is from the ROOT's POV (same flip convention as
        ``NeuralMCTS.best_action``), ΣN is the sum of the deduped root children's
        visit counts, and children with N(a)==0 are excluded (score -inf, never
        selected). Cheap: reads the already-computed root; runs no extra sims and
        cannot affect the tree — LCB only changes the final move choice.
        """
        m = self.mcts
        root_key = m.game.string_representation(board)
        root = m._nodes.get(root_key)
        if root is None or root.N == 0:  # defensive; best_action already searched
            m.search(board)
            root = m._nodes[root_key]
        visited = [(a, c) for a, c in m._deduped_children(root) if c.N > 0]
        if not visited:
            return next(iter(root.children))
        total_n = sum(c.N for _, c in visited)
        log_total = math.log(total_n) if total_n > 0 else 0.0
        c_lcb = float(self.cfg.c_lcb)
        best_a = None
        best_score = -math.inf
        for a, child in visited:
            q = child.Q if child.player_to_move == root.player_to_move else -child.Q
            lcb = q - c_lcb * math.sqrt(log_total / child.N)
            if lcb > best_score:
                best_score = lcb
                best_a = int(a)
        return int(best_a)

    # --- Gumbel root / sequential halving (root_select="gumbel") ----------- #
    def _completed_q(self, root, action: int) -> float:
        """Completed action value q̂(a) from the ROOT / mover POV.

        Visited child -> its Q flipped into the root player's POV (the same flip
        convention as best_action / _lcb_action). Unvisited (child absent or N==0)
        -> the value-approx = ``root.leaf_value`` (already the mover-POV leaf value
        at the root). [Simplification vs the paper's v_mix; unvisited only occurs at
        very low budget — flagged in the build report.]"""
        child = root.children.get(int(action))
        if child is None or child.N == 0:
            return float(root.leaf_value)
        return float(
            child.Q if child.player_to_move == root.player_to_move else -child.Q
        )

    def _gumbel_root_search(self, board: Board) -> int:
        """Gumbel-root / sequential-halving action selection (Track C1).

        Returns the chosen ROOT action. Runs on the SERIAL forced-sim path
        (``_simulate(..., forced_root_action=a)``) — NOT ``_run_batch`` — so the
        root visit count is never double-counted by virtual loss. Composes with
        tree reuse: ``move()`` has already re-rooted/cleared ``_nodes``, so we look
        the root up (or expand it) exactly as ``search()`` would, then add the
        forced budget on top of any retained statistics.

        Algorithm (Danihelka et al. 2022, "Policy improvement by planning with
        Gumbel"), per the C1 build spec:
          * draw g(a)~Gumbel(0,1) per legal root action via the SEEDED
            ``self.mcts._np_rng`` (determinism given seed+deck);
          * candidates = top-m of (g + logits), m = min(gumbel_m, n_legal), where
            logits = the TRUE pre-softmax z = Δleaf/τ (NOT log(softmax));
          * sequential halving over ⌈log₂m⌉ phases: a deterministic integer slice
            of the total sim budget per phase (leftover +1 to the EARLIEST phases),
            split as evenly as possible across the current candidates (leftover +1
            to the earliest in the current order); each sim forces its candidate as
            the root edge and descends with PUCT below;
          * after each phase, re-rank survivors by  [g +] logits + σ(completedQ),
            σ(q)=(c_visit + max_b N_b)·c_scale·q, and keep the top ⌈k/2⌉ — the g
            term is included iff cfg.gumbel_retain_g (True default = paper-exact:
            the SAME per-candidate g from the top-m draw persists through
            elimination; False = g only picks the top-m, elimination drops it);
          * the final single survivor is the winner.

        Budget invariant: the total number of forced sims == ``self.simulations``
        exactly (Σ phase budgets), so on a fresh tree ``root.N == simulations``.
        """
        m_mcts = self.mcts
        game = m_mcts.game

        # 1. Ensure the root exists + is expanded (mirror NeuralMCTS.search's serial
        #    expansion; reuse_tree may already have re-rooted an expanded node here).
        root_key = game.string_representation(board)
        root = m_mcts._nodes.get(root_key)
        if root is None:
            root = m_mcts._create_node(board)
            m_mcts._nodes[root_key] = root
        if not root.expanded and not root.is_terminal:
            priors_b, values_b = m_mcts._eval_boards([board])
            m_mcts._expand_with_priors(root, board, priors_b[0], float(values_b[0]))

        # Degenerate roots: terminal, no legal move, or a forced single move.
        legal = [int(a) for a in root.valid_actions]
        if root.is_terminal or not legal:
            return int(next(iter(root.children))) if root.children else 0
        if len(legal) == 1:
            return int(legal[0])   # 1-legal short-circuit (spec)

        # 2. TRUE pre-softmax logits z = Δleaf/τ (scale-sensitive completed-Q term).
        logit_actions, z = self.evaluator.root_logits(board)
        logits = {int(a): float(zz) for a, zz in zip(logit_actions, z)}
        for a in legal:  # defensive: never KeyError on a legal action
            logits.setdefault(a, 0.0)

        # 3. Gumbel-top-m candidate set (SEEDED RNG; deterministic action-index
        #    tiebreak). g+logits argmax is invariant to the softmax constant, so the
        #    top-m only needs the (constant-shifted) logits — but the halving term
        #    below is scale-sensitive, hence the true z.
        n_legal = len(legal)
        g = m_mcts._np_rng.gumbel(0.0, 1.0, size=n_legal)
        g_by_action = {legal[i]: float(g[i]) for i in range(n_legal)}
        gl = [g_by_action[legal[i]] + logits[legal[i]] for i in range(n_legal)]
        order = sorted(range(n_legal), key=lambda i: (-gl[i], legal[i]))
        m = min(int(self.cfg.gumbel_m), n_legal)
        cand = [legal[i] for i in order[:m]]
        if m == 1:
            return int(cand[0])

        # 4. Sequential halving over ⌈log₂m⌉ phases (budget sums to `simulations`).
        c_visit = float(self.cfg.gumbel_c_visit)
        c_scale = float(self.cfg.gumbel_c_scale)
        retain_g = bool(self.cfg.gumbel_retain_g)   # paper-exact: g rides elimination
        total = int(self.simulations)
        num_phases = max(1, math.ceil(math.log2(m)))
        base, extra = divmod(total, num_phases)   # phase split; sums to total
        A = list(cand)                            # current candidates, ordered
        for phase in range(num_phases):
            phase_budget = base + (1 if phase < extra else 0)
            k = len(A)
            per, rem = divmod(phase_budget, k)    # split across arms; +1 to first rem
            for idx, a in enumerate(A):
                n_sims = per + (1 if idx < rem else 0)
                for _ in range(n_sims):
                    m_mcts._simulate(board, root, forced_root_action=a)
            # re-rank by [g +] logits + σ(completedQ); keep the top ⌈k/2⌉ survivors.
            max_N = max((c.N for c in root.children.values()), default=0)
            sigma_coeff = (c_visit + max_N) * c_scale
            scores = {
                a: (g_by_action[a] if retain_g else 0.0)
                + logits[a]
                + sigma_coeff * self._completed_q(root, a)
                for a in A
            }
            A = sorted(A, key=lambda a: (-scores[a], a))[: math.ceil(k / 2)]
        return int(A[0])

    def move(self, board: Board) -> int:
        if self._reuse_tree:
            self._reroot_or_clear(board)
        else:
            self.clear()
        self.neural_moves += 1
        return self.best_action(board)

    # --- tree reuse (reuse_tree=True) -------------------------------------- #
    def _reroot_or_clear(self, board: Board) -> None:
        """Re-root the persisted PUCT tree into the node for ``board`` (the
        position the agent is now asked about), keeping that subtree's statistics.

        Falls back to a fresh clear()ed search when:
          (b) ``board`` is not in the retained tree (opponent played an
              unsearched/low-visit move) — this is normal, counted in reuse_fresh;
          (a) the retained node under ``board``'s transposition key is a
              wrong-rotation SIBLING (same string_representation key but different
              farmer meeple-action indices — the Phase-0.3 legal-cache rotation
              family). Re-using it would silently descend into a wrong subtree with
              the wrong action indices, so we DON'T — counted in reuse_collide.

        The legal-moves cache is always dropped (correctness-neutral; avoids the
        Phase-0.3 stale cross-ply mask serving). Only the ``_nodes`` search
        statistics are what tree-reuse retains.
        """
        m = self.mcts
        game = m.game
        game.clear_caches()  # drop the legal-moves cache every move (Phase-0.3 safe)
        next_key = game.string_representation(board)
        retained = m._nodes.get(next_key)
        if (
            retained is None
            or not retained.expanded
            or retained.is_terminal
            or retained.N == 0
        ):
            # (b) not usefully in the retained tree -> fresh search
            m._nodes.clear()
            m._noisy_roots.clear()
            self.reuse_fresh += 1
            return
        # (a) COLLISION GUARD: discriminate a wrong-rotation sibling from the true
        # position by the FRESH legal mask (identical iff the same physical board;
        # a rotation-sibling has different farmer meeple indices — test_invalid_
        # visit_clip). retained.valid_actions was frozen from the board that first
        # created this node during the prior search.
        fresh_actions = {int(a) for a in np.flatnonzero(game.get_valid_moves(board))}
        if set(retained.valid_actions) != fresh_actions:
            m._nodes.clear()
            m._noisy_roots.clear()
            self.reuse_collide += 1
            return
        # SAFE: prune _nodes to the subtree reachable from the retained root and
        # re-root there (its accumulated visit stats carry over; the search adds
        # `simulations` more sims on top).
        self._prune_to_subtree(retained)
        # Tripwire: after re-root the root's cached valid_actions MUST equal the
        # board's fresh legal set. Can only fail if a collision slipped past the
        # guard above -> fail loud rather than serve a wrong subtree.
        assert set(retained.valid_actions) == fresh_actions, (
            "tree-reuse re-root would serve a wrong-rotation subtree "
            "(collision guard bypassed) — must never happen"
        )
        self.reuse_hits += 1

    def _prune_to_subtree(self, new_root) -> None:
        """Rebuild ``mcts._nodes`` to hold ONLY the subtree reachable from
        ``new_root`` (drop every other retained node). Bounds memory and makes a
        stale cross-move transposition collision structurally impossible (an
        unrelated stale node can no longer be looked up)."""
        m = self.mcts
        reachable: dict = {}
        stack = [new_root]
        while stack:
            node = stack.pop()
            k = node.state_key
            if k in reachable:
                continue
            reachable[k] = node
            for child in node.children.values():
                if child.state_key not in reachable:
                    stack.append(child)
        m._nodes = reachable
        m._noisy_roots = set()


def make_heuristic_prior_mcts(
    game: Game,
    cfg: HeuristicPriorConfig,
    simulations: int,
    seed: int | None = None,
) -> NeuralMCTS:
    """Thin factory: a ``NeuralMCTS`` wired with the heuristic-prior evaluator
    (no agent wrapper; ``final_select`` not applied — caller reads best_action /
    root_visit_distribution itself)."""
    return NeuralMCTS(
        game=game,
        evaluator=make_heuristic_prior_evaluator(game, cfg),
        simulations=simulations,
        c_puct=cfg.c_puct,
        seed=seed,
    )
