"""PROBE A — structured-leaf wrapper skeleton (spec §1 / task 5).

    v_leaf(state) = aggregate( g_theta(component_i) for component_i in decompose(state) )

with aggregate = SUM (matched to virtual_score's own aggregation, so v_leaf is a
drop-in leaf at every MCTS node — spec §1). This module provides:

  * `GThetaStub` — a numpy hand-rolled per-component head (FEAT_DIM -> H -> 1),
    RANDOM weights for milestone 1 (the wiring/speed skeleton). Milestone 2 trains
    g_theta and loads its weights here. NOTE: the head is deliberately NUMPY, not a
    torch nn.Module — the enriched-speed bench (scripts/probe_a/enriched_speed.py)
    showed a torch batch-1 forward's dispatch overhead pushes the additive arm to
    3.7x (FAIL), while the numpy head keeps it at 2.56x (PASS). Train in torch,
    EXPORT the weights to this numpy head for the leaf hot path.

  * `structured_value(board, root_player)` — the board-POV structured leaf value,
    computed from the Cython feature emit (`component_features_cy`, same C
    decomposition the scalar leaf already runs — no second decompose).

  * `make_probe_a_value_wrapper(...)` — a drop-in for
    `step2_leaf.make_step2_value_wrapper`: same `_Step2Wrapped` return type,
    same wants_parent / leaf-POV sign convention, same convex/additive leaf_mode
    semantics, but the value comes from `structured_value` instead of the scalar
    MLP. This lets scripts/step2_pens/eval_step2.py's additive path (§4 pre-gate)
    consume the structured leaf with NO changes to eval_step2 itself.

POV CONVENTION (matches step2_leaf._v_mlp_leafpov):
  `structured_value` is keyed to a `root_player` POV (board-POV). NeuralMCTS
  interprets a leaf's value in the LEAF player-to-move POV, and `h` (the heuristic)
  is leaf-POV. So we compute the structured value at the LEAF's current_player POV
  directly (root_player = board.state.current_player), which is already leaf-POV —
  no sign flip needed. (The step2 scalar MLP needed a flip only because it was
  trained parent-POV; the structured head here is evaluated fresh per board at the
  leaf's own POV, so it is leaf-POV by construction.)

Milestone-1 scope: the wiring COMPILES and RUNS at the measured speed with a
random-weight stub. Do NOT train here (milestone 2).
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "engine"),
           str(_REPO / "scripts" / "probe_a"), str(_REPO / "scripts" / "step2_pens")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import carcassonne_ai.flat_leaf_cy as _cy
import component_features as cf
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2
from carcassonne_ai.flat_leaf import (
    decompose as _decompose, _cloister_points, _surrounding_count,
)
from wingedsheep.carcassonne.objects.terrain_type import TerrainType as _TT

# The 32-dim bag/deck-composition histogram — REUSED verbatim from the frozen
# Step-1 census (step2_leaf's build_dataset.bag_histogram is itself imported from
# here); we do NOT rebuild it.
sys.path.insert(0, str(_REPO / "scripts" / "feature_planes_gate"))
from step1_planes import bag_histogram as _bag_histogram, N_BAG as _N_BAG  # noqa: E402


def cloister_offset(state, root_player: int, cfg=None) -> float:
    """The heuristic's OWN cloister/monastery value as an EXACT board-level offset
    (self-minus-opp, root-POV): cloister base (surrounding-tile count when meepled)
    + cloister closure-anticipation (P[8-n_surround] * (8-n_surround)).

    BIT-IDENTICAL to build_component_dataset._attribute's `cloister_slice`
    (econ_base_extra + econ_closure_extra) — the same v2.9 leaf path — so the
    dataset's stored `cloister_slice` and this leaf-time offset agree to fp. This
    is added at leaf time the SAME way running_diff is; it is NOT learned (the
    cloister feature columns are reserved-0, so g_theta structurally cannot see
    it). Cloisters are not union-find components, so this needs no decompose — a
    single pass over placed cloister meeples.
    """
    if cfg is None:
        cfg = DEFAULT_CONFIG
    closure_p = cfg.closure_p
    board = state.board
    H = len(board); W = len(board[0]) if H else 0
    opp = 1 - root_player
    base = 0.0
    clo = 0.0
    for pl in range(state.players):
        sgn = 1.0 if pl == root_player else -1.0
        for mp in state.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r = cws.coordinate.row; c = cws.coordinate.column; side = cws.side
            terr = board[r][c].get_type(side)
            if terr == _TT.CHAPEL or terr == _TT.FLOWERS:
                base += sgn * _cloister_points(r, c, board, H, W)
                n_sur = _surrounding_count(state, r, c, H, W)
                needed = 8 - n_sur
                if needed > 0:
                    p = closure_p.get(needed, 0.0)
                    if p > 0:
                        clo += sgn * (p * needed)
    return float(base + clo)


class GThetaStub:
    """Per-component value head g_theta: (n_comp, FEAT_DIM) -> (n_comp,), aggregated
    by SUM to a scalar leaf value. NUMPY (see module docstring on why not torch).

    A 2-layer tanh MLP (FEAT_DIM -> H -> 1). RANDOM weights for milestone 1
    (`from_random`); milestone 2 loads TRAINED weights via `from_trained_npz`.

    LEAF AGGREGATION (milestone 2.5, matches the trainer + the heuristic's shape):

        v_leaf = tanh( ( running_diff + cloister_offset
                         + sum_i g_theta(comp_i) + bag_head(bag_hist) ) / tanh_scale )

    where:
      * `running_diff`     = exact points-already-scored offset (state.scores diff;
                             NOT learned — the closed features that produced them are
                             off the board and carry no component features).
      * `cloister_offset`  = the heuristic's OWN cloister/monastery value
                             (base + closure, self-minus-opp, root-POV) — an EXACT
                             board-level offset (milestone-2.5), because cloisters
                             are not union-find components and their slice (abs-mean
                             7.52 on 84% of these boards) cannot be reconstructed
                             from the zero cloister-feature columns. Same pattern as
                             running_diff: computed from the v2.9 leaf, not learned.
      * `bag_head(bag)`    = a small board-level forward on the 32-dim bag/deck
                             histogram (the axis CL-037 showed EXCEEDS the v2.9
                             ceiling). One forward per node. `None` on heads trained
                             without a bag input (bag scalar = 0).
    tanh_scale defaults to 15.0 (== the heuristic's tanh(vs/15)). The trained
    weights are exported with the z-score NORMALIZATION FOLDED INTO the first
    layer(s), so the leaf feeds RAW Cython features + RAW bag (no per-node
    normalization work on the hot path). The aggregate stays a PURE SUM so v_leaf
    is a drop-in leaf.

    Milestone-1 back-compat: `out_scale` + `aggregate(X)` (no running/cloister/bag
    offset, tanh(out_scale*sum)) are retained for the random stub / old smoke.
    """

    def __init__(self, W1, b1, W2, b2, out_scale=1.0, tanh_scale=15.0,
                 bag_W1=None, bag_b1=None, bag_W2=None, bag_b2=None):
        self.W1 = W1.astype(np.float32)
        self.b1 = b1.astype(np.float32)
        self.W2 = W2.astype(np.float32)
        self.b2 = b2.astype(np.float32)
        self.out_scale = float(out_scale)
        self.tanh_scale = float(tanh_scale)
        # optional board-level bag head (32 -> H_bag -> 1); None == no bag input.
        self.has_bag = bag_W1 is not None
        if self.has_bag:
            self.bag_W1 = bag_W1.astype(np.float32)
            self.bag_b1 = bag_b1.astype(np.float32)
            self.bag_W2 = bag_W2.astype(np.float32)
            self.bag_b2 = bag_b2.astype(np.float32)
        self._is_stub = True

    @classmethod
    def from_random(cls, in_dim=cf.FEAT_DIM, hidden=32, seed=0, out_scale=1.0):
        rng = np.random.default_rng(seed)
        return cls(
            W1=rng.standard_normal((in_dim, hidden)) * 0.3,
            b1=np.zeros(hidden),
            W2=rng.standard_normal((hidden, 1)) * 0.3,
            b2=np.zeros(1),
            out_scale=out_scale,
        )

    @classmethod
    def from_trained_npz(cls, path):
        """Load the exported (normalization-folded) numpy head produced by
        scripts/probe_a/export_gtheta.py. Feeds RAW features + RAW bag; adds the
        running + cloister offsets via `aggregate_with_offset`. Bag head weights
        (bag_W1/…) are present iff the head was trained WITH the bag input."""
        z = np.load(str(path))
        kw = {}
        if "bag_W1" in z.files:
            kw = dict(bag_W1=z["bag_W1"], bag_b1=z["bag_b1"],
                      bag_W2=z["bag_W2"], bag_b2=z["bag_b2"])
        g = cls(W1=z["W1"], b1=z["b1"], W2=z["W2"], b2=z["b2"],
                tanh_scale=float(z["tanh_scale"]), **kw)
        g._is_stub = False
        return g

    def per_component(self, X: np.ndarray) -> np.ndarray:
        """g_theta over each row. X is (n_comp, FEAT_DIM) float32 -> (n_comp,)."""
        if X.shape[0] == 0:
            return np.zeros(0, dtype=np.float32)
        h = np.tanh(X @ self.W1 + self.b1)
        return (h @ self.W2 + self.b2).reshape(-1)

    def component_sum(self, X: np.ndarray) -> float:
        return float(self.per_component(X).sum())

    def bag_scalar(self, bag: np.ndarray) -> float:
        """Board-level bag-head forward (32 -> H_bag -> 1) -> scalar. 0.0 if the
        head carries no bag input (bag axis absent). ONE tiny forward per node."""
        if not self.has_bag or bag is None:
            return 0.0
        h = np.tanh(bag.astype(np.float32) @ self.bag_W1 + self.bag_b1)
        return float((h @ self.bag_W2 + self.bag_b2).reshape(-1)[0])

    def aggregate(self, X: np.ndarray) -> float:
        """MILESTONE-1 stub aggregation: v = tanh(out_scale * sum). No offsets
        (kept for the random-stub smoke / old speed benches)."""
        return math.tanh(self.out_scale * self.component_sum(X))

    def aggregate_with_offset(self, X: np.ndarray, running_diff: float,
                              cloister_offset: float = 0.0,
                              bag: np.ndarray | None = None) -> float:
        """MILESTONE-2.5 leaf value (the drop-in reproducing the heuristic's own
        structure at leaf speed):

            tanh( (running_diff + cloister_offset
                   + sum_i g(comp_i) + bag_head(bag)) / tanh_scale )

        `cloister_offset` and `running_diff` are EXACT board-level offsets (not
        learned); `bag` is the raw 32-dim histogram (None -> 0 bag scalar)."""
        s = self.component_sum(X)
        bs = self.bag_scalar(bag)
        return math.tanh((running_diff + cloister_offset + s + bs) / self.tanh_scale)


def structured_value(board, root_player: int, g_theta: GThetaStub,
                     closure_p=None, cfg=None) -> float:
    """Board-POV structured leaf value (milestone 2.5).

    Trained head (`_is_stub` False):
        tanh((running_diff + cloister_offset + sum g_theta + bag_head(bag))/tanh_scale)
      running_diff    = state.scores[root]-state.scores[opp] (exact already-scored)
      cloister_offset = the v2.9 leaf's cloister value (exact, not learned)
      bag             = the 32-dim bag histogram (fed to bag_head iff the head has
                        a bag input; else the bag scalar is 0).
    Random stub: the milestone-1 tanh(out_scale*sum) (no offsets), so old
    smokes/benches are unchanged.
    """
    if closure_p is None:
        closure_p = DEFAULT_CONFIG.closure_p
    st = board.state
    X = _cy.component_features_cy(st, root_player, closure_p)
    if getattr(g_theta, "_is_stub", True):
        return g_theta.aggregate(X)
    opp = 1 - root_player
    running_diff = float(int(st.scores[root_player]) - int(st.scores[opp]))
    clo = cloister_offset(st, root_player, cfg)
    bag = _bag_histogram(st) if getattr(g_theta, "has_bag", False) else None
    return g_theta.aggregate_with_offset(X, running_diff, clo, bag)


def make_probe_a_value_wrapper(
    base_policy_evaluator,
    g_theta: GThetaStub,
    *,
    game,
    leaf_cfg,
    blend: float,
    dropout_p: float = 0.0,
    rng_seed: int = 0,
    counters=None,
    leaf_mode=None,
):
    """Structured-leaf analog of step2_leaf.make_step2_value_wrapper.

    Returns a `_Step2Wrapped` (same type step2/eval_step2 already consume) whose
    value is the STRUCTURED leaf `structured_value` instead of the scalar MLP.
    convex / additive modes and the terminal/dropout paths are IDENTICAL to
    step2_leaf so the §4 additive pre-gate protocol is inherited unchanged.

    `leaf_cfg` is the v2.9 LeafConfig (EH._heur_leaf_cfg(2.0)); its closure_p is
    the schedule fed to the feature emit (so the emit matches the heuristic h).
    `base_policy_evaluator` supplies ONLY priors (its value is discarded).
    `blend` is the wean/additive coefficient (beta). `g_theta` is the (random-stub
    for now) per-component head.
    """
    from carcassonne_ai.step2_leaf import _Step2Counters, _Step2Wrapped  # reuse the exact glue

    if leaf_mode is None:
        leaf_mode = os.environ.get("CARCASSONNE_STEP2_LEAF_MODE", "convex")
    leaf_mode = str(leaf_mode).strip().lower()
    if leaf_mode not in ("convex", "additive"):
        raise ValueError(f"leaf_mode must be 'convex' or 'additive' (got {leaf_mode!r})")

    closure_p = leaf_cfg.closure_p if leaf_cfg is not None else DEFAULT_CONFIG.closure_p
    if counters is None:
        counters = _Step2Counters()
    _rng = np.random.default_rng(rng_seed)

    print(f"[probe_a_leaf] STRUCTURED leaf, mode={leaf_mode}, "
          f"blend/beta={blend}, dropout_p={dropout_p}, FEAT_DIM={cf.FEAT_DIM} "
          f"(g_theta={'RANDOM STUB' if getattr(g_theta, '_is_stub', True) else 'trained'})",
          flush=True)

    def _v_struct_leafpov(board) -> float:
        # Evaluate at the LEAF's own current_player POV == leaf-POV directly
        # (no parent-POV flip needed; the structured head is computed fresh per
        # board, unlike the parent-POV-trained scalar MLP). leaf_cfg drives the
        # exact cloister closure schedule.
        return structured_value(board, board.state.current_player, g_theta,
                                closure_p, cfg=leaf_cfg)

    def wrapped(board, parent_board=None):
        st = board.state
        priors, _v_unused = base_policy_evaluator(board)
        counters.calls += 1

        ended = game.get_game_ended(board, st.current_player)
        if ended != 0:
            counters.terminal_path += 1
            return priors, max(-1.0, min(1.0, float(ended)))

        if dropout_p > 0.0 and _rng.random() < dropout_p:
            counters.dropout_path += 1
            counters.scalar_path += 1
            return priors, _v_struct_leafpov(board)

        h = math.tanh(virtual_score_v2(st, st.current_player, leaf_cfg) / 15.0)
        if leaf_mode == "additive":
            if blend > 0.0:
                counters.scalar_path += 1
                v = h + blend * _v_struct_leafpov(board)
                return priors, max(-1.0, min(1.0, v))
            counters.plain_path += 1
            return priors, max(-1.0, min(1.0, h))
        # convex wean
        if blend > 0.0:
            counters.scalar_path += 1
            return priors, (1.0 - blend) * h + blend * _v_struct_leafpov(board)
        counters.plain_path += 1
        return priors, h

    w = _Step2Wrapped(wrapped, leaf_cfg, counters, blend, dropout_p, leaf_mode=leaf_mode)
    w.leaf_name = "probe_a_structured"
    return w


# ---- self-check (milestone-1 wiring smoke) -------------------------------- #
def _smoke():
    """Prove the wiring compiles + runs and produces a bounded leaf value on a
    real board with a random-weight g_theta. NOT a training run."""
    import random
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
    from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
    from wingedsheep.carcassonne.utils.action_util import ActionUtil
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater

    rng = random.Random(7)
    st = CarcassonneGameState(players=2, tile_sets=[TileSet.BASE],
                              supplementary_rules=[SupplementaryRule.FARMERS])
    rng.shuffle(st.deck)
    placed = 1
    while not st.is_terminated() and placed < 55:
        acts = ActionUtil.get_possible_actions(st)
        if not acts:
            break
        StateUpdater.apply_action_inplace(game_state=st, action=rng.choice(acts))
        placed = sum(1 for row in st.board for t in row if t is not None)

    class _BoardShim:
        def __init__(self, state):
            self.state = state

    g = GThetaStub.from_random(seed=1, out_scale=0.05)
    v = structured_value(_BoardShim(st), st.current_player, g)
    print(f"[smoke] structured_value = {v:+.4f}  (bounded in [-1,1]: {-1.0 <= v <= 1.0})")
    assert -1.0 <= v <= 1.0
    n = _cy.component_features_cy(st, st.current_player, DEFAULT_CONFIG.closure_p).shape[0]
    print(f"[smoke] n_components (incl econ row) = {n}")
    print("[smoke] OK — structured leaf wiring compiles and runs.")


if __name__ == "__main__":
    _smoke()
