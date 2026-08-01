"""rustport **P3** — the Python side of the per-sim trace harness.

Built *before* k-parallel (P4) on purpose: it is the debugging instrument for
every phase after, and it is what turns "the trees disagree" into "simulation
417 took a different edge out of node ab12cd…".

HOUSE RULE: this module must NOT edit `src/carcassonne_ai/`.  The instrumentation
is a **subclass** — [`TracingNeuralMCTS`] — that overrides three hooks and adds
no semantics of its own:

* ``_select_child_puct``  — records ``(node.state_key, action)`` for every
  descent edge, then returns exactly what the base class returned;
* ``_expand`` / ``_expand_with_priors`` — record a node the first time it is
  expanded (the terminal short-circuit lives in ``_expand``, the ordinary path
  in ``_expand_with_priors``, so both are hooked and neither double-emits);
* ``_simulate`` — brackets ``super()._simulate`` and **reconstructs** the path
  from the recorded edges (``path = [root] + [node.children[a] for a in edges]``).

Reconstruction (rather than re-implementing ``_simulate``) is what keeps this
drift-free: no line of the champion's simulation body is copied here, so the
Python leg of the gate cannot silently diverge from `src/` the way a
copy-pasted loop would.  `tests/rustport/test_p3_search.py` still asserts, on
real positions, that a traced search and an untraced one produce bit-identical
trees — the tracer is proven inert, not assumed inert.

The emitted JSONL is byte-comparable with the Rust
`carc_core::search::trace::JsonlTrace`; `trace_diff.py` bisects the two.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# ⚠️ BEFORE any carcassonne_ai import (see scripts/rustport/prod_leaf_env.py):
# this module resolves the PRODUCTION champion knobs, so a bare DEFAULT_CONFIG
# here would be wrong as well as order-poisoning.
import prod_leaf_env  # noqa: E402,F401

import carc_rs  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402

# The PRODUCTION leaf dispatch, re-derived from the environment exactly as
# `flat_leaf` derives it at ITS import.  Not captured from the live module
# attribute, because `reconcile_leaf` (whose leaf configs + provenance assertions
# P3 reuses) sets `flat_leaf.USE_CY_LEAF = False` at ITS import so its three-leg
# comparison really exercises pure Python — and whether that has already
# happened depends on module import order.
_PROD_USE_CY_LEAF = os.environ.get("CARCASSONNE_USE_CY_LEAF", "1") != "0"

_REC = None


def _rec_mod():
    """`reconcile_leaf`, imported WITHOUT leaking its `USE_CY_LEAF = False`.

    P3 wants the production (Cython) leaf — 62x faster, and G2 proved the two
    paths bit-identical over 3.34M values — but flipping a process-global on
    someone else's behalf is exactly how `tests/rustport/test_p2_leaf.py`
    (which asserts the flag is False) would break depending on collection
    order. So: restore whatever was there, and set the production value only
    for the duration of a search (see `production_leaf_dispatch`).
    """
    global _REC
    if _REC is None:
        prev = flat_leaf.USE_CY_LEAF
        import reconcile_leaf as m
        flat_leaf.USE_CY_LEAF = prev
        _REC = m
    return _REC


@contextlib.contextmanager
def production_leaf_dispatch():
    """Run the block with `flat_leaf` dispatching to the PRODUCTION leaf."""
    prev = flat_leaf.USE_CY_LEAF
    flat_leaf.USE_CY_LEAF = _PROD_USE_CY_LEAF
    try:
        yield
    finally:
        flat_leaf.USE_CY_LEAF = prev


from carcassonne_ai.game_wrapper import SCORE_NORM_SCALE, Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402
from root_replay import replay_actions  # noqa: E402


# --------------------------------------------------------------------------- #
# Raw-float identity                                                           #
# --------------------------------------------------------------------------- #
def bits(x: float) -> str:
    """Raw IEEE-754 bit pattern, 16 lowercase hex digits (Rust: `trace::bits`)."""
    return f"{struct.unpack('<Q', struct.pack('<d', float(x)))[0]:016x}"


def ubits(x: float) -> int:
    """Same, as an int — what `carc_rs` returns for every float in a result."""
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def digest(state_key: str) -> str:
    """Node identity in a trace: `sha256(string_representation)[:16]`."""
    return hashlib.sha256(state_key.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# The champion configuration — read, never hard-coded                          #
# --------------------------------------------------------------------------- #
def production_knobs() -> dict:
    """`governance/PRODUCTION.yaml champion.agent_knobs` + the verified leaf.

    Refuses to run against anything but the leaf of record (`_rec.leaf_provenance`
    asserts the curve VALUES and the `a36d2e15a3b3d71d` fingerprint), and
    cross-checks that PRODUCTION.yaml's own `leaf_config` block agrees with the
    `LeafConfig` we build — a green gate against the wrong champion is worse
    than a red one.
    """
    from carcassonne_ai.champion_factory import load_production_spec

    spec = load_production_spec()
    leaf_prov = _rec_mod().leaf_provenance()
    leaf_cfg = _rec_mod()._cfgs("core")["prod-curve125"]
    if tuple(spec.curve) != tuple(float(x) for x in leaf_cfg.v29_meeple_curve):
        raise SystemExit(
            f"PRODUCTION.yaml curve {tuple(spec.curve)!r} != prod-curve125 "
            f"{tuple(leaf_cfg.v29_meeple_curve)!r}")
    if float(spec.bonus_cap) != float(leaf_cfg.bonus_cap) or \
            float(spec.opp_bonus_cap) != float(leaf_cfg.opp_bonus_cap):
        raise SystemExit("PRODUCTION.yaml caps disagree with prod-curve125")
    return {
        "champion_id": spec.champion_id,
        "c_puct": float(spec.c_puct),
        "tau_p": float(spec.tau_p),
        "final_select": str(spec.final_select),
        "leaf_quantize": str(spec.leaf_quantize),
        "value_norm": float(spec.value_norm),
        # PRODUCTION.yaml carries reuse_tree: true, but it is explicitly a NO-OP
        # in FAIR DEPLOY — `FairHeuristicPriorAgent` has no reuse knob and builds
        # a FRESH tree per determinization (YAML §agent_knobs.reuse_tree, the
        # 2026-07-09 "resolved by mechanism" note; champion_factory calls the
        # same thing `reuse_tree_effective`). P3 ports the SINGLE-WORLD search
        # that P4's k-parallel PIMC drives, so the fresh-tree semantics are the
        # ones under gate. Both values are recorded; only the effective one is
        # used to build the config.
        "reuse_tree_yaml": bool(spec.reuse_tree),
        "reuse_tree": False,
        "score_norm_scale": float(SCORE_NORM_SCALE),
        "sims_per_det": int(spec.sims_per_det),
        "k_dets": int(spec.k_dets),
        "leaf": leaf_prov,
        "leaf_cfg": leaf_cfg,
        "use_cy_leaf": bool(_PROD_USE_CY_LEAF),
    }


def py_config(knobs: dict | None = None, *, final_select: str | None = None,
              leaf_quantize: str | None = None) -> HeuristicPriorConfig:
    """The champion config. The two overrides exist ONLY so the tests can gate
    the non-production `final_select` / `leaf_quantize` branches of the port —
    every gate leg runs with both at their PRODUCTION.yaml values."""
    k = knobs or production_knobs()
    return HeuristicPriorConfig(
        c_puct=k["c_puct"],
        tau_p=k["tau_p"],
        leaf_quantize=leaf_quantize or k["leaf_quantize"],
        final_select=final_select or k["final_select"],
        value_norm=k["value_norm"],
        leaf_cfg=k["leaf_cfg"],
        reuse_tree=k["reuse_tree"],
    )


def rs_config(sims: int, knobs: dict | None = None, *,
              final_select: str | None = None, leaf_quantize: str | None = None,
              collide_check: bool = False):
    """The SAME knobs driven into `carc_rs.SearchConfigRs`."""
    k = knobs or production_knobs()
    return carc_rs.SearchConfigRs(
        _rec_mod()._to_rs(k["leaf_cfg"]),
        int(sims),
        k["c_puct"],
        k["tau_p"],
        k["value_norm"],
        k["score_norm_scale"],
        leaf_quantize or k["leaf_quantize"],
        final_select or k["final_select"],
        None,                       # fpu_reduction: NeuralMCTS default (legacy q=0)
        1.0,                        # c_lcb (inert unless final_select == "lcb")
        True,                       # np.exp float64 == glibc __exp_fma  (G0 §3)
        "glibc_fma",                # math.tanh flavour on x86-64        (G0 §2)
        bool(collide_check),        # diagnostic only; never on for a gate leg
    )


# --------------------------------------------------------------------------- #
# The trace sink                                                               #
# --------------------------------------------------------------------------- #
class JsonlTrace:
    """Byte-compatible with `carc_core::search::trace::JsonlTrace`."""

    def __init__(self, fh, expansions: bool = True):
        self.fh = fh
        self.expansions = expansions

    def expand(self, node) -> None:
        if not self.expansions:
            return
        va = list(node.valid_actions)
        pr = ",".join(f'"{bits(node.priors[a])}"' for a in va)
        self.fh.write(
            '{"t":"exp","node":"%s","p":%d,"term":%d,"tv":"%s","lv":"%s","va":[%s],"pr":[%s]}\n'
            % (digest(node.state_key), int(node.player_to_move),
               1 if node.is_terminal else 0, bits(node.terminal_value),
               bits(node.leaf_value), ",".join(str(int(a)) for a in va), pr)
        )

    def sim(self, i: int, path, actions, leaf_value: float) -> None:
        self.fh.write(
            '{"t":"sim","i":%d,"path":[%s],"acts":[%s],"lv":"%s","nw":[%s]}\n'
            % (i,
               ",".join(f'"{digest(n.state_key)}"' for n in path),
               ",".join(str(int(a)) for a in actions),
               bits(leaf_value),
               ",".join(f'[{int(n.N)},"{bits(n.W)}"]' for n in path))
        )


class _NullTrace:
    expansions = False

    def expand(self, node):
        pass

    def sim(self, i, path, actions, leaf_value):
        pass


# --------------------------------------------------------------------------- #
# The instrumented search                                                      #
# --------------------------------------------------------------------------- #
class TracingNeuralMCTS(NeuralMCTS):
    """`NeuralMCTS` + a per-simulation trace. Semantically inert (tested)."""

    def __init__(self, *args, trace_sink=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._sink = trace_sink or _NullTrace()
        self._edges: list = []
        self._sim_idx = 0

    # -- hooks ------------------------------------------------------------- #
    def _select_child_puct(self, node):
        action = super()._select_child_puct(node)
        self._edges.append((node.state_key, action))
        return action

    def _expand(self, node, board, parent_board=None):
        was = node.expanded
        super()._expand(node, board, parent_board)
        # The terminal short-circuit returns from `_expand` WITHOUT reaching
        # `_expand_with_priors`; every other path emits there.
        if not was and node.expanded and node.is_terminal:
            self._sink.expand(node)

    def _expand_with_priors(self, node, board, priors, value):
        was = node.expanded
        super()._expand_with_priors(node, board, priors, value)
        if not was and node.expanded:
            self._sink.expand(node)

    def _simulate(self, root_board, root, forced_root_action=None):
        if forced_root_action is not None:
            raise NotImplementedError(
                "the P3 tracer covers the PUCT-root path only (root_select='puct')")
        self._edges = []
        super()._simulate(root_board, root, forced_root_action)
        path = [root]
        node = root
        for key, action in self._edges:
            if node.state_key != key:
                raise AssertionError(
                    "trace path reconstruction desynchronised: expected node "
                    f"{key[:40]!r}, walked to {node.state_key[:40]!r}")
            node = node.children[action]
            path.append(node)
        self._sink.sim(self._sim_idx, path, [a for _, a in self._edges],
                       path[-1].leaf_value)
        self._sim_idx += 1


# --------------------------------------------------------------------------- #
# One single-world search, Python side                                         #
# --------------------------------------------------------------------------- #
def py_search_single(game: Game, board, cfg: HeuristicPriorConfig, sims: int,
                     trace_path: str | Path | None = None,
                     trace_expansions: bool = True) -> dict:
    """Run the PRODUCTION agent for one move and return the comparable surface.

    Drives the real `HeuristicPriorAgent` (so `final_select` / `clear()` /
    `best_action` are the champion's own code) with its `NeuralMCTS` swapped for
    the tracing subclass.  Returns the same keys `MirrorState.search_single`
    does, with every float as a raw-bit `int`.
    """
    agent = HeuristicPriorAgent(game=game, cfg=cfg, simulations=int(sims), seed=None)
    fh = open(trace_path, "w") if trace_path is not None else None
    sink = JsonlTrace(fh, expansions=trace_expansions) if fh is not None else None
    agent.mcts = TracingNeuralMCTS(
        game=game, evaluator=agent.evaluator, simulations=int(sims),
        c_puct=cfg.c_puct, seed=None, trace_sink=sink,
    )
    try:
        with production_leaf_dispatch():
            chosen = int(agent.move(board))
        root = agent.mcts._nodes[game.string_representation(board)]
        children = sorted(root.children.items())
        deduped = agent.mcts._deduped_children(root)
        return {
            "chosen_action": chosen,
            "root_children": [(int(a), int(c.N), ubits(c.W)) for a, c in children],
            "deduped": [(int(a), int(c.N), ubits(c.W)) for a, c in deduped],
            "root_n": int(root.N),
            "root_w_bits": ubits(root.W),
            "root_leaf_value_bits": ubits(root.leaf_value),
            "root_priors": [(int(a), ubits(root.priors[a])) for a in root.valid_actions],
            "node_count": len(agent.mcts._nodes),
            "legal_cache_hits": int(game._legal_cache_hits),
            "legal_cache_misses": int(game._legal_cache_misses),
        }
    finally:
        if fh is not None:
            fh.close()


def rs_state(deck_seed: int, actions, ply: int):
    """The Rust mirror driven to the same ply by the same action ints."""
    ms = carc_rs.MirrorState.from_seed(str(int(deck_seed)))
    for a in actions[:ply]:
        ms.advance(int(a))
    return ms


def py_state(deck_seed: int, actions, ply: int):
    return replay_actions(int(deck_seed), list(actions), int(ply))


# --------------------------------------------------------------------------- #
# CLI — dump a matched pair of traces for one position                         #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--deck-seed", type=int, required=True)
    ap.add_argument("--actions", default="", help="comma-separated action ints")
    ap.add_argument("--ply", type=int, default=0)
    ap.add_argument("--sims", type=int, default=64)
    ap.add_argument("--out", default="/tmp/p3_trace")
    ap.add_argument("--no-expansions", action="store_true")
    a = ap.parse_args(argv)

    actions = [int(x) for x in a.actions.split(",") if x.strip()]
    knobs = production_knobs()
    cfg = py_config(knobs)
    game, board = py_state(a.deck_seed, actions, a.ply)
    ms = rs_state(a.deck_seed, actions, a.ply)

    py_out = Path(f"{a.out}_py.jsonl")
    rs_out = Path(f"{a.out}_rs.jsonl")
    py = py_search_single(game, board, cfg, a.sims, trace_path=py_out,
                          trace_expansions=not a.no_expansions)
    rs = ms.search_single(rs_config(a.sims, knobs), str(rs_out),
                          not a.no_expansions)
    print(json.dumps({"python": py["chosen_action"], "rust": rs["chosen_action"],
                      "py_trace": str(py_out), "rs_trace": str(rs_out),
                      "agree": py["chosen_action"] == rs["chosen_action"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
