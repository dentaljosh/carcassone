"""Step-2 "PeNS" scalar-MLP VALUE leaf for self-play (MEASUREMENT ONLY).

The novel core of the weaned flywheel. At each MCTS leaf we:

  1. compute the 89 PeNS scalar features LIVE from the leaf board,
  2. forward a small scalar MLP (`train_warmstart.ScalarMLP`) to get a value,
  3. WEAN-BLEND it with the v2.9 heuristic leaf:
        value = (1 - blend) * h + blend * v_mlp
     where h = tanh(virtual_score_v2(state, current_player, cfg) / 15)
     (blend 0 -> pure heuristic, blend 1 -> pure net; the wean parameter).
     A per-leaf DROPOUT (w.p. p) returns the PURE MLP value (blend forced to 1)
     so the net is exercised even at low blend.

This module does NOT modify any production code. It IMPORTS the production
`virtual_score_v2` for `h` and the build_dataset feature helpers for the 89-vec.
The wrapper structure mirrors `evaluators.make_v25_value_wrapper` but takes the
value from the scalar MLP rather than the ResNet value head, and carries its OWN
provenance counter so a smoke can assert the scalar-MLP path actually fired.

IMPORTANT DESIGN NOTE — the parent/child mismatch (WIRING-smoke approximation).
`build_dataset.py` computes each feature row for a CHILD position relative to its
PARENT (root): ~21 of the 89 features are parent->child deltas / move-semantics
(the 5 Tier-1 `T1_d_*`, the 8 `T2_d_*` + `T2_opp_feature_touched` +
`T2_feature_completed_by_move` + `T2_completed_value_*`, the 8 Tier-2
action/move-semantics `T2_meeple_placed`/`mtype_*`/`net_meeple_delta`/
`imm_score_delta_*`), and the `Fctx` context block reads the PARENT's
scores/meeples. At an MCTS leaf the evaluator receives only ONE board (the leaf
state) with no parent threaded through. For this WIRING smoke we adopt the
SELF-REFERENTIAL mapping: parent == leaf, so every delta / move-semantics
feature is 0 and `Fctx` reads the leaf's own scores/meeples/k/phase. This is a
documented APPROXIMATION, not the final feature semantics — see
extract_step2_features.__doc__ and the task's training-story assessment. A real
pilot must thread the pre-move (parent) board to the leaf to populate the delta
features the warmstart MLP was trained on.
"""
from __future__ import annotations

import math
import os
from typing import Callable

import numpy as np

# Reuse build_dataset's per-child feature computation verbatim (the 50 CL-034
# helpers, the 7 deck-odds, the 32-bag histogram, the FEAT_NAMES ordering). The
# import has the side effect of running build_dataset's GUARD env block at module
# import time (CARCASSONNE_V25_* / V29_MEEPLE_CURVE / USE_FLAT_LEAF=1 /
# USE_CY_REPR=1 / VALUE_BLEND=0), which is exactly the v2.9 leaf provenance the
# dataset was built under. We rely on that env being set BEFORE virtual_score_v2's
# DEFAULT_CONFIG is frozen, so import order matters (see make_step2_value_wrapper).
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
for _p in (
    str(_REPO / "scripts" / "step2_pens"),
    str(_REPO / "scripts" / "level2"),
    str(_REPO / "scripts" / "feature_planes_gate"),
    str(_REPO / "scripts"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_dataset as _bd  # noqa: E402  (runs the guard-env block at import)
from carcassonne_ai.flat_leaf import decompose  # noqa: E402
from carcassonne_ai.leaf_v29 import decompose_v29  # noqa: E402
from carcassonne_ai.virtual_score_v2 import virtual_score_v2  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

FEAT_NAMES = list(_bd.FEAT_NAMES)
N_FEAT = _bd.N_FEAT  # 89
PHASES = _bd.PHASES


def _k_remaining(state) -> int:
    """Tiles still to draw = deck + the drawn-but-unplaced tile (TILES phase)."""
    return len(state.deck) + (
        1 if (getattr(state, "next_tile", None) is not None
              and state.phase == GamePhase.TILES) else 0
    )


def _phase_of(k: int) -> str:
    """k_remaining -> phase string, matching gen_multiphase_positions.phase_of
    (the exact bucketing the dataset's `phase` column uses)."""
    if k <= 6:
        return "endgame"
    if k <= 14:
        return "pre_endgame"
    if k <= 28:
        return "late_mid"
    if k <= 46:
        return "midgame"
    return "opening"


def extract_step2_features(game, board, cfg, parent_board=None) -> np.ndarray:
    """Compute the 89-vec PeNS scalar features for a LIVE leaf board.

    Returns an (89,) float32 array in the SAME column order as
    build_dataset.FEAT_NAMES (== dataset meta.json `feat_names`).

    PARENT-THREADED (the Step-2 "Path A" fix, 2026-06-30). `board` is the CHILD
    (the leaf state being evaluated); `parent_board` is the TREE-PARENT (the
    position one move back, the board the MCTS descent created `board` from).
    When `parent_board` is supplied, the ~16 parent->child DELTA / move-semantics
    features (`T1_d_*`, `T2_d_*`, `T2_meeple_placed`, `T2_mtype_*`,
    `T2_net_meeple_delta_self`, `T2_imm_score_delta_*`, `T2_opp_feature_touched`,
    `T2_feature_completed_by_move`, `T2_completed_value_*`) and the `Fctx` context
    block (which reads the PARENT's scores/meeples — the *decision-time* context,
    matching build_dataset) are computed EXACTLY as build_dataset._process does
    (child − parent), so the live 89-vec is bit-faithful to the dataset row that
    trained the warmstart MLP. This recovers the full offline signal (+43%) that
    degraded to +22.4% when those 16 columns were zeroed.

    SELF-REFERENTIAL fallback (`parent_board is None`, e.g. the search ROOT which
    has no tree-parent): the leaf is treated as both parent and child, so every
    delta / move-semantics feature is 0 and `Fctx` reads the leaf's OWN
    scores/meeples/k/phase. The root is one leaf per search (negligible) and the
    warmstart MLP is robust to it; the bulk of the tree gets the real deltas.

    `cfg` is the v2.9 LeafConfig (EH._heur_leaf_cfg(2.0)). Cost: the parent's
    decompose/decompose_v29/_struct_summary are computed once here per leaf (the
    child's decompositions are the SAME passes the v2.9 heuristic `h` already
    runs — see make_step2_value_wrapper for the shared-decompose handoff).
    """
    state = board.state
    have_parent = parent_board is not None

    # build_dataset keys EVERYTHING — both parent AND child decompositions, the
    # leaf_q, every delta — to the PARENT's current_player (== root_player there).
    # Mirror that exactly: when a parent is threaded, root_player is the parent's
    # current_player (NOT the child's, which may have advanced a turn). At the
    # root (no parent) we use the leaf's own current_player (self-referential).
    if have_parent:
        pstate = parent_board.state
        root_player = pstate.current_player
    else:
        pstate = state
        root_player = state.current_player
    opp = 1 - root_player

    # ---- child (== leaf) structural decompositions (parent-POV root_player) - #
    cdec = decompose(state)
    cv29 = decompose_v29(state, root_player, cfg)
    cstruct = _bd._struct_summary(state, cdec, root_player)
    c_meeple_contrib = cv29["meeple_flat"] + cv29["meeple_curve_delta"]

    if have_parent:
        pdec = decompose(pstate)
        pv29 = decompose_v29(pstate, root_player, cfg)
        pstruct = _bd._struct_summary(pstate, pdec, root_player)
        p_scores = pstate.scores
        p_meeples_free = pstate.meeples
        p_meeple_contrib = pv29["meeple_flat"] + pv29["meeple_curve_delta"]
    else:
        p_scores = state.scores
        p_meeples_free = state.meeples
        pv29 = cv29
        pstruct = cstruct
        p_meeple_contrib = c_meeple_contrib

    # ---- Fctx: reads the PARENT's (decision-time) scores/meeples/k/phase ---- #
    # build_dataset computes k_remaining/phase/score_margin from the PARENT
    # (root) state; mirror that when a parent is present, else from the leaf.
    ctx_state = pstate
    k_remaining = float(_k_remaining(ctx_state))
    phase = _phase_of(int(k_remaining))
    score_margin_signed = float(p_scores[root_player] - p_scores[opp])
    ph_onehot = [1.0 if phase == p else 0.0 for p in PHASES]
    Fctx = ph_onehot + [
        k_remaining / 10.0,
        score_margin_signed / 10.0,
        float(p_meeples_free[root_player]),
        float(p_meeples_free[opp]),
    ]

    # ---- Tier-1 leaf value components (the CHILD == leaf state) ------------- #
    ended = game.get_game_ended(board, root_player)
    terminal = 1.0 if ended != 0 else 0.0
    if ended != 0:
        leaf_total_raw = None
        leaf_q = max(-1.0, min(1.0, float(ended)))
    else:
        vs = float(virtual_score_v2(state, root_player, cfg))
        leaf_total_raw = vs
        leaf_q = math.tanh(vs / 15.0)
    leaf_total_div15 = (leaf_total_raw / 15.0) if leaf_total_raw is not None else leaf_q

    # ---- Tier-2 action/move semantics (child − parent) --------------------- #
    if have_parent:
        net_meeple_delta_self = float(state.meeples[root_player] - p_meeples_free[root_player])
        imm_score_delta_self = float(state.scores[root_player] - p_scores[root_player])
        imm_score_delta_opp = float(state.scores[opp] - p_scores[opp])
        n_placed_parent = len(pstate.placed_meeples[root_player])
        n_placed_child = len(state.placed_meeples[root_player])
        meeple_placed = 1.0 if n_placed_child > n_placed_parent else 0.0
        mtype_city = mtype_road = mtype_farm = mtype_monastery = 0.0
        if meeple_placed:
            pset = set(
                (mp.coordinate_with_side.coordinate.row,
                 mp.coordinate_with_side.coordinate.column,
                 mp.coordinate_with_side.side, mp.meeple_type)
                for mp in pstate.placed_meeples[root_player]
            )
            newmp = None
            for mp in state.placed_meeples[root_player]:
                key = (mp.coordinate_with_side.coordinate.row,
                       mp.coordinate_with_side.coordinate.column,
                       mp.coordinate_with_side.side, mp.meeple_type)
                if key not in pset:
                    newmp = mp
                    break
            if newmp is not None:
                cws = newmp.coordinate_with_side
                terr = state.board[cws.coordinate.row][cws.coordinate.column].get_type(cws.side)
                if newmp.meeple_type in _bd._FARMER_TYPES:
                    mtype_farm = 1.0
                elif terr == _bd.TerrainType.CITY:
                    mtype_city = 1.0
                elif terr == _bd.TerrainType.ROAD:
                    mtype_road = 1.0
                elif terr in (_bd.TerrainType.CHAPEL, _bd.TerrainType.FLOWERS):
                    mtype_monastery = 1.0
        # Tier-2 structural deltas
        d_total_city_open_edges = float(cstruct["total_city_open_edges"] - pstruct["total_city_open_edges"])
        d_n_open_cities = float(cstruct["n_open_cities"] - pstruct["n_open_cities"])
        d_meeples_locked_self = float(cstruct["n_meeples_locked_self"] - pstruct["n_meeples_locked_self"])
        d_n_contested = float(cstruct["n_cities_contested"] - pstruct["n_cities_contested"])
        opp_touched = float(_bd._opp_feature_touched(pstruct, cstruct, root_player))
        csv, cov, feat_completed = _bd._completed_value(pstruct, cdec, cstruct, state, root_player)
        # Tier-1 leaf-component deltas
        d_base = cv29["base"] - pv29["base"]
        d_closure_self = cv29["closure_self"] - pv29["closure_self"]
        d_closure_opp = cv29["closure_opp"] - pv29["closure_opp"]
        d_meeple = c_meeple_contrib - p_meeple_contrib
        d_pretransform = cv29["pretransform_total"] - pv29["pretransform_total"]
    else:
        net_meeple_delta_self = imm_score_delta_self = imm_score_delta_opp = 0.0
        meeple_placed = mtype_city = mtype_road = mtype_farm = mtype_monastery = 0.0
        d_total_city_open_edges = d_n_open_cities = d_meeples_locked_self = d_n_contested = 0.0
        opp_touched = 0.0
        csv = cov = 0.0
        feat_completed = 0
        d_base = d_closure_self = d_closure_opp = d_meeple = d_pretransform = 0.0

    cl034_row = list(Fctx) + [
        # Tier-1 (13)
        leaf_total_div15,
        leaf_q,
        cv29["base"] / 15.0,
        cv29["closure_self"] / 8.0,
        cv29["closure_opp"] / 8.0,
        c_meeple_contrib,
        cv29["pretransform_total"] / 15.0,
        terminal,
        d_base, d_closure_self, d_closure_opp, d_meeple, d_pretransform,
        # Tier-2 action/move (8)
        meeple_placed, mtype_city, mtype_road, mtype_farm, mtype_monastery,
        net_meeple_delta_self, imm_score_delta_self, imm_score_delta_opp,
        # Tier-2 child structural (12) — from the leaf state itself
        float(cstruct["n_open_cities"]),
        float(cstruct["n_open_roads"]),
        float(cstruct["n_open_farms"]),
        float(cstruct["total_city_open_edges"]),
        float(cstruct["n_cities_self"]),
        float(cstruct["n_cities_opp"]),
        float(cstruct["n_cities_contested"]),
        float(cstruct["n_meeples_locked_self"]),
        float(cstruct["n_meeples_locked_opp"]),
        float(cstruct["max_open_city_value_self"]) / 8.0,
        float(cstruct["n_farms_self"]),
        float(cstruct["n_farms_contested"]),
        # Tier-2 structural deltas (8)
        d_total_city_open_edges, d_n_open_cities, d_meeples_locked_self,
        d_n_contested, opp_touched, float(feat_completed),
        csv / 8.0, cov / 8.0,
    ]
    assert len(cl034_row) == 50

    # bag histogram (32) — pure function of the leaf's (child) remaining multiset.
    bag = _bd.bag_histogram(state).astype(np.float32).tolist()

    # deck-odds (7) — placed_tile = the tile placed by the move that produced
    # this child (parent→child), so #54 (placed_tile_remaining_count) populates;
    # None at the root degrades #54 to log1p(0)=0.
    placed_tile = _bd._placed_tile(pstate, state) if have_parent else None
    do_row = _bd._deck_odds(state, cdec, cstruct, root_player, placed_tile)

    row = cl034_row + bag + do_row
    out = np.asarray(row, dtype=np.float32)
    assert out.shape == (N_FEAT,), out.shape
    return out


class _Step2Counters:
    """Provenance counter for the scalar-MLP value path (mirrors evaluators.
    _RuntimeCounters but for THIS leaf). `scalar_path` = a blended/pure-MLP
    value that consumed the scalar-MLP output; `plain_path` = the value fell
    back to pure heuristic (blend==0 and not dropped); `dropout_path` = the
    leaf-dropout fired (pure MLP value). A smoke asserts scalar_path > 0 so we
    KNOW the MLP value actually entered the search, not merely the heuristic."""

    __slots__ = ("calls", "scalar_path", "plain_path", "dropout_path", "terminal_path")

    def __init__(self):
        self.calls = 0
        self.scalar_path = 0     # value consumed the scalar-MLP output (blend>0 or dropout)
        self.plain_path = 0      # pure heuristic (blend==0, not dropped)
        self.dropout_path = 0    # leaf-dropout fired -> pure MLP value
        self.terminal_path = 0   # terminal leaf -> exact terminal value (no MLP/heuristic)

    def as_dict(self) -> dict:
        return {
            "calls": self.calls,
            "scalar_path": self.scalar_path,
            "plain_path": self.plain_path,
            "dropout_path": self.dropout_path,
            "terminal_path": self.terminal_path,
        }


class _Step2Wrapped:
    """Callable `(priors, value)` evaluator. Exposes `.counters` (a
    `_Step2Counters`), `.leaf_cfg`, `.blend`, `.dropout_p` for introspection;
    drop-in for any NeuralMCTS `evaluator=` slot."""

    leaf_name = "step2_pens_scalar"
    is_batch = False

    # Tell NeuralMCTS to call us as evaluator(child_board, parent_board): we need
    # the tree-parent board to compute the parent->child delta features (the 16
    # cols that recover the full +43% offline signal). NeuralMCTS only threads the
    # parent when this attribute is truthy; absent on every other evaluator.
    wants_parent = True

    def __init__(self, fn, leaf_cfg, counters, blend, dropout_p, leaf_mode="convex"):
        self._fn = fn
        self.leaf_cfg = leaf_cfg
        self.counters = counters
        self.blend = blend
        self.dropout_p = dropout_p
        self.leaf_mode = leaf_mode

    def __call__(self, board, parent_board=None):
        return self._fn(board, parent_board)


def make_step2_value_wrapper(
    base_policy_evaluator: Callable[[object], tuple[np.ndarray, float]],
    scalar_mlp,
    col_mean: np.ndarray,
    col_std: np.ndarray,
    feat_names: list[str],
    *,
    game,
    leaf_cfg,
    blend: float,
    dropout_p: float = 0.0,
    device=None,
    rng_seed: int = 0,
    counters: "_Step2Counters | None" = None,
    leaf_mode: "str | None" = None,
) -> "_Step2Wrapped":
    """Wrap a POLICY-ONLY evaluator: keep its priors, replace its value with the
    v2.9 heuristic combined with the scalar-MLP value. Two leaf MODES:

    CONVEX (default — the production wean leaf, UNCHANGED):
      - terminal leaf: exact terminal value (clipped to +-1); no MLP/heuristic.
      - leaf-dropout fires (prob dropout_p): value = scalar_mlp_value (pure net).
      - else: value = (1 - blend) * h + blend * scalar_mlp_value.
      Heuristic is weaned DOWN as `blend` rises (the heuristic structural eval is
      SUBTRACTED while the net is added).

    ADDITIVE (opt-in, the "nail 2" decoupling test — MEASUREMENT ONLY):
      - terminal leaf: identical exact terminal value (clipped); no MLP/heuristic.
      - leaf-dropout fires (prob dropout_p): value = scalar_mlp_value (pure net) —
        IDENTICAL to convex (the dropout path exercises the pure net either way).
      - else: value = clip(h + beta * scalar_mlp_value, -1, 1).
      Heuristic stays at FULL weight 1.0; the net is ADDED on top with coefficient
      beta (= `blend`, reused as the additive coefficient). This decouples the two
      effects the convex wean conflates: ADDING the net value vs SUBTRACTING the
      heuristic's structural eval. beta=0 -> clip(h, -1, 1) == pure v2.9 h (h is
      already in [-1,1] from tanh, so the clip is a no-op there) -> a clean
      pure-heuristic anchor.

    `h = tanh(virtual_score_v2(state, current_player, leaf_cfg) / 15)` — BYTE-
    IDENTICAL in both modes. The scalar-MLP value is the MLP forward over the
    z-scored 89-vec (`(feat - col_mean) / col_std`), already tanh-bounded by
    ScalarMLP, then flipped to leaf-POV by `_v_mlp_leafpov` (identical in both
    modes). The mode is selected by the `leaf_mode` arg, or (when None) by the env
    var CARCASSONNE_STEP2_LEAF_MODE (default "convex"). Only "convex"/"additive"
    are valid.

    `base_policy_evaluator` supplies ONLY priors (its value is discarded) — use a
    policy-only ResNet evaluator (make_single_evaluator_policy_only) for the base.
    `leaf_cfg` is the v2.9 LeafConfig (EH._heur_leaf_cfg(2.0)). `feat_names` is
    asserted to match build_dataset's ordering so the col_mean/col_std align.
    """
    import torch

    if leaf_mode is None:
        leaf_mode = os.environ.get("CARCASSONNE_STEP2_LEAF_MODE", "convex")
    leaf_mode = str(leaf_mode).strip().lower()
    if leaf_mode not in ("convex", "additive"):
        raise ValueError(
            f"CARCASSONNE_STEP2_LEAF_MODE / leaf_mode must be 'convex' or "
            f"'additive' (got {leaf_mode!r})"
        )
    # One-line provenance so a run's log shows which leaf mode + coefficient fired.
    if leaf_mode == "additive":
        print(f"[step2_leaf] LEAF MODE = additive (heuristic FULL weight 1.0 + "
              f"beta={blend} * v_net, clipped to [-1,1]); dropout_p={dropout_p}",
              flush=True)
    else:
        print(f"[step2_leaf] LEAF MODE = convex (wean: (1-blend)*h + blend*v_net, "
              f"blend={blend}); dropout_p={dropout_p}", flush=True)

    if list(feat_names) != FEAT_NAMES:
        raise ValueError(
            "feat_names mismatch: the scalar MLP was trained on a different "
            "feature ordering than build_dataset.FEAT_NAMES — column "
            "normalization would be misaligned. "
            f"(got {len(feat_names)} names; expected {len(FEAT_NAMES)})"
        )

    if counters is None:
        counters = _Step2Counters()
    dev = device if device is not None else torch.device("cpu")
    scalar_mlp = scalar_mlp.to(dev)
    scalar_mlp.eval()
    cmean = np.asarray(col_mean, dtype=np.float32)
    cstd = np.asarray(col_std, dtype=np.float32)
    cstd = np.where(cstd < 1e-6, 1.0, cstd).astype(np.float32)
    _rng = np.random.default_rng(rng_seed)

    def _mlp_value(board, parent_board, feat=None) -> float:
        if feat is None:
            feat = extract_step2_features(game, board, leaf_cfg, parent_board)
        x = (feat - cmean) / cstd
        xt = torch.from_numpy(x.astype(np.float32)).unsqueeze(0).to(dev)
        with torch.no_grad():
            # ScalarMLP uses BatchNorm1d -> .eval() makes it use running stats;
            # a batch of 1 is therefore safe.
            v = scalar_mlp(xt)
        return float(v.reshape(-1)[0].item())

    def _v_mlp_leafpov(board, parent_board) -> float:
        """The MLP value, in the LEAF player-to-move POV.

        POV FIX (2026-06-30): extract_step2_features keys EVERYTHING to the PARENT
        (root) player's POV — matching build_dataset's oracle_q convention the
        warmstart MLP was trained under — so `_mlp_value` is a PARENT-POV value.
        But NeuralMCTS interprets a leaf's value in the LEAF's player-to-move POV
        (and `h` below is leaf-POV). On the player-flip transitions (MEEPLE->TILES,
        ~half the tree) parent_player != leaf_player, so the parent-POV MLP value
        must be NEGATED to become leaf-POV. Without this, the blend mixes h and
        v_mlp with OPPOSITE signs on ~half the leaves (a real value corruption)."""
        v = _mlp_value(board, parent_board)
        if parent_board is not None and parent_board.state.current_player != board.state.current_player:
            v = -v
        return v

    def wrapped(board, parent_board=None) -> tuple[np.ndarray, float]:
        st = board.state
        priors, _v_unused = base_policy_evaluator(board)
        counters.calls += 1

        # Terminal leaf: exact value, no model.
        ended = game.get_game_ended(board, st.current_player)
        if ended != 0:
            counters.terminal_path += 1
            return priors, max(-1.0, min(1.0, float(ended)))

        if dropout_p > 0.0 and _rng.random() < dropout_p:
            counters.dropout_path += 1
            counters.scalar_path += 1
            return priors, _v_mlp_leafpov(board, parent_board)

        h = math.tanh(virtual_score_v2(st, st.current_player, leaf_cfg) / 15.0)
        if leaf_mode == "additive":
            # ADDITIVE (nail 2): heuristic at FULL weight + net added with coeff
            # beta (= blend), then clipped. At beta=0 this is clip(h, -1, 1) == h
            # (a clean pure-heuristic anchor — counted as plain_path so the
            # provenance distinguishes it from the value-consuming path).
            if blend > 0.0:
                counters.scalar_path += 1
                v = h + blend * _v_mlp_leafpov(board, parent_board)
                return priors, max(-1.0, min(1.0, v))
            counters.plain_path += 1
            return priors, max(-1.0, min(1.0, h))
        # CONVEX (default — UNCHANGED).
        if blend > 0.0:
            counters.scalar_path += 1
            return priors, (1.0 - blend) * h + blend * _v_mlp_leafpov(board, parent_board)
        counters.plain_path += 1
        return priors, h

    return _Step2Wrapped(wrapped, leaf_cfg, counters, blend, dropout_p, leaf_mode=leaf_mode)
