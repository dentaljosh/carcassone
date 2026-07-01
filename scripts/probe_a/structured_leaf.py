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


class GThetaStub:
    """Per-component value head g_theta: (n_comp, FEAT_DIM) -> (n_comp,), aggregated
    by SUM to a scalar leaf value. NUMPY (see module docstring on why not torch).

    A 2-layer tanh MLP (FEAT_DIM -> H -> 1). RANDOM weights for milestone 1
    (`from_random`); milestone 2 loads TRAINED weights via `from_trained_npz`.

    LEAF AGGREGATION (milestone 2, matches the trainer + the heuristic's shape):

        v_leaf = tanh( (running_diff + sum_i g_theta(comp_i)) / tanh_scale )

    where `running_diff` is the exact points-already-scored offset (from
    state.scores; NOT learned — the closed features that produced them are off
    the board and carry no component features) and tanh_scale defaults to 15.0
    (== the heuristic's tanh(vs/15)). The trained weights are exported with the
    z-score NORMALIZATION FOLDED INTO the first layer, so the leaf feeds the head
    RAW Cython features (no per-node normalization work on the hot path).

    Milestone-1 back-compat: `out_scale` + `aggregate(X)` (no running offset,
    tanh(out_scale*sum)) are retained for the random stub / old smoke.
    """

    def __init__(self, W1, b1, W2, b2, out_scale=1.0, tanh_scale=15.0):
        self.W1 = W1.astype(np.float32)
        self.b1 = b1.astype(np.float32)
        self.W2 = W2.astype(np.float32)
        self.b2 = b2.astype(np.float32)
        self.out_scale = float(out_scale)
        self.tanh_scale = float(tanh_scale)
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
        scripts/probe_a/export_gtheta.py. Feeds RAW features; adds the running
        offset via `aggregate_with_offset`."""
        z = np.load(str(path))
        g = cls(W1=z["W1"], b1=z["b1"], W2=z["W2"], b2=z["b2"],
                tanh_scale=float(z["tanh_scale"]))
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

    def aggregate(self, X: np.ndarray) -> float:
        """MILESTONE-1 stub aggregation: v = tanh(out_scale * sum). No running
        offset (kept for the random-stub smoke / old speed benches)."""
        return math.tanh(self.out_scale * self.component_sum(X))

    def aggregate_with_offset(self, X: np.ndarray, running_diff: float) -> float:
        """MILESTONE-2 leaf value: tanh((running_diff + sum_i g(comp_i))/tanh_scale),
        the drop-in that reproduces the heuristic's own structure at leaf speed."""
        s = self.component_sum(X)
        return math.tanh((running_diff + s) / self.tanh_scale)


def structured_value(board, root_player: int, g_theta: GThetaStub,
                     closure_p=None) -> float:
    """Board-POV structured leaf value.

    Trained head (`_is_stub` False): tanh((running_diff + sum g_theta)/tanh_scale),
    running_diff = state.scores[root]-state.scores[opp] (the exact already-scored
    offset). Random stub: the milestone-1 tanh(out_scale*sum) (no offset), so old
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
    return g_theta.aggregate_with_offset(X, running_diff)


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
        # board, unlike the parent-POV-trained scalar MLP).
        return structured_value(board, board.state.current_player, g_theta, closure_p)

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
