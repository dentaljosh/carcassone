"""rustport **P4** shared plumbing — build the two fair-agent legs from ONE set
of knobs and reduce a decision to a comparable, raw-float record.

Imported by ``scripts/rustport/reconcile_fair.py`` and
``tests/rustport/test_p4_fair.py``; it holds nothing gate-specific so the two
cannot drift apart in how they construct the champion.

The PYTHON leg is the oracle and is built through
``champion_factory.make_production_champion("fair", ...)`` — the same entry point
production and the phone use — with ``parallel_workers=None``, i.e. the
SEQUENTIAL k-loop, which is byte-for-byte the deployed champion and the world
order the Rust merge is defined against.

The comparable surface per decision:

  action · the pooled ``(N, W)`` accumulators as RAW f64 bits, in pool insertion
  order · forced / exact / latched / timeout flags · the solver's node count,
  value and optimal-action set when the solver owned the move.

`agg_w` is not a public attribute of the Python agent (`last_pooled_visits` is
only `agg_n`), so it is captured by monkeypatching `fair_agent.pooled_q_argmax` —
the `_PoolSpy` pattern `tests/test_kparallel.py` already uses.
"""
from __future__ import annotations

import contextlib
import os
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "level2", REPO / "scripts" / "human_anchor",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ⚠️ THE PRODUCTION LEAF ENV MUST PRECEDE ANY `carcassonne_ai` IMPORT.
# `virtual_score_v2.DEFAULT_CONFIG` is IMPORT-FROZEN from these knobs, and
# `champion_factory.production_leaf_cfg` is "DEFAULT_CONFIG with only the curve
# replaced" — so without the preamble the oracle silently builds a cap-5 /
# meeple_k-0 leaf while the Rust leg gets the cap-8 leaf of record.  (That is
# not hypothetical: it is exactly how this file's first draft mis-built the
# champion, and it survived because `verify=False` disarmed the guard.  Both the
# preamble and `verify=True` are load-bearing; so is `assert_same_leaf` below.)
#
# The guard checks the REAL invariant, not the proxy "was carcassonne_ai imported
# first" (P6, 2026-08-01).  What actually matters is that the import-frozen knobs
# ALREADY held their production values when the freeze happened — if some other
# module (an android bridge test, a sibling harness) applied the same preamble
# first, importing after it is perfectly safe, and refusing there only made this
# module unusable inside a full-tree pytest.  When the freeze happened against a
# DIFFERENT environment it is still a hard RuntimeError, because that is the
# silent-wrong-champion case.
_ENV_BEFORE = dict(os.environ)

import env_preamble  # noqa: E402,F401  (applies PROD_ENV on import)

# The subset of PROD_ENV that `carcassonne_ai` freezes AT ITS IMPORT: the leaf
# SHAPE (virtual_score_v2.DEFAULT_CONFIG) and the two dispatch flags read at
# module scope (flat_leaf.USE_FLAT_LEAF, board_repr.USE_CY_REPR). The threading /
# CUDA knobs are not frozen and are deliberately not checked.
IMPORT_FROZEN_KNOBS = (
    "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP",
    "CARCASSONNE_V25_DROP_THREE_OPEN", "CARCASSONNE_V29_MEEPLE_CURVE",
    "CARCASSONNE_V25_MEEPLE_K", "CARCASSONNE_V25_VALUE_BLEND",
    "CARCASSONNE_USE_FLAT_LEAF", "CARCASSONNE_USE_CY_REPR",
)
_LATE = [k for k in IMPORT_FROZEN_KNOBS
         if _ENV_BEFORE.get(k) != env_preamble.PROD_ENV[k]]
if "carcassonne_ai" in sys.modules and _LATE:  # pragma: no cover - import-order guard
    raise RuntimeError(
        "fair_common must be imported BEFORE carcassonne_ai — the production leaf "
        "env is frozen into virtual_score_v2.DEFAULT_CONFIG (and the flat-leaf / "
        "cython-repr dispatch flags) at ITS import. Knobs that were not already at "
        f"their production values when the freeze happened: {_LATE}")

import carc_rs  # noqa: E402

import trace_search as T  # noqa: E402
from carcassonne_ai import fair_agent  # noqa: E402
from carcassonne_ai.champion_factory import make_production_champion  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

# `fair_agent.DEFAULT_EXACT_BUDGET`; re-read rather than re-typed.
EXACT_BUDGET = int(fair_agent.DEFAULT_EXACT_BUDGET)
EXACT_MAX_K = int(fair_agent.EXACT_MAX_K)
MIN_POOLED_VISITS = float(fair_agent.DEFAULT_MIN_POOLED_VISITS)


def ubits(x: float) -> int:
    """Raw IEEE-754 bits of a float as an unsigned int (Rust: `f64::to_bits`)."""
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


# --------------------------------------------------------------------------- #
# Leg construction                                                             #
# --------------------------------------------------------------------------- #
def py_agent(game: Game, *, sims: int, k_dets: int, seed: int,
             exact_endgame: bool = True, exact_max_k: int = EXACT_MAX_K):
    """The ORACLE: the production fair champion, sequential k-loop.

    `verify=True` runs the R1/R7-class provenance guard (curve values, caps,
    `_LEAF_VALUE_PANEL` on real boards) at construction — the thing that catches
    a missing leaf-env preamble instead of silently gating the wrong champion.

    ⚠️ `backend="python"` is PINNED, not omitted (2026-08-03). This function is the
    PYTHON leg of every rustport gate — the thing the Rust leg is compared AGAINST —
    and `make_production_champion`'s default flipped to `"auto"`, i.e. to the yaml's
    `backend: rust`. Omitting it would have made every reconcile/identity gate compare
    Rust against Rust and report a green it had not earned (it does not even get that
    far: the oracle is driven without a mirror, so it raises `MirrorDesync` at ply 0)."""
    agent = make_production_champion(
        "fair", game=game, seed=int(seed), sims=int(sims), k_dets=int(k_dets),
        exact_endgame=bool(exact_endgame), verify=True, backend="python",
        exact_budget=EXACT_BUDGET, parallel_workers=None)
    assert_same_leaf(agent)
    return agent


_KNOBS = None


def knobs() -> dict:
    """`trace_search.production_knobs()`, memoized per process (it re-reads
    PRODUCTION.yaml and re-hashes the leaf on every call)."""
    global _KNOBS
    if _KNOBS is None:
        _KNOBS = T.production_knobs()
    return _KNOBS


def assert_same_leaf(agent, knobs: dict | None = None) -> None:
    """Prove the ORACLE's resolved leaf IS the one driven into Rust.

    `champion_factory` resolves the leaf from the import-frozen env; the Rust leg
    is driven from `trace_search.production_knobs()`'s `prod-curve125`.  Those are
    two independent paths to the same object, so equality is a real check — and a
    green gate against two different leaves would be worse than a red one."""
    k = knobs or globals()["knobs"]()
    got = agent._cfg.resolved_leaf_cfg()
    want = k["leaf_cfg"]
    fields = ("closure_p", "bonus_cap", "opp_bonus_cap", "meeple_k",
              "v29_meeple_curve", "soft_cap_slope", "opp_soft_cap_slope",
              "v29_meeple_return_k", "v29_farm_flip_k", "bag_close",
              "tile_counting_closure", "closure_continuous_slack")
    bad = {f: (getattr(got, f, None), getattr(want, f, None))
           for f in fields
           if _norm(getattr(got, f, None)) != _norm(getattr(want, f, None))}
    if bad:
        raise SystemExit(
            f"fair oracle leaf != the leaf driven into Rust (field: (oracle, rust)): {bad}")


def _norm(v):
    if isinstance(v, dict):
        return tuple(sorted((int(k), float(x)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return tuple(float(x) for x in v)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


def rs_agent(*, sims: int, k_dets: int, seed: int, threads: int = 1,
             exact_endgame: bool = True, exact_max_k: int = EXACT_MAX_K,
             knobs=None):
    """The Rust leg, driven from the SAME `governance/PRODUCTION.yaml` knobs
    `trace_search.production_knobs()` resolves (which asserts the leaf of
    record's curve values and `a36d2e15a3b3d71d` fingerprint before returning)."""
    k = knobs or globals()["knobs"]()
    return carc_rs.FairAgentRs(
        T.rs_config(int(sims), k),
        k_dets=int(k_dets),
        seed=int(seed),
        min_pooled_visits=MIN_POOLED_VISITS,
        exact_endgame=bool(exact_endgame),
        exact_max_k=int(exact_max_k),
        exact_budget=EXACT_BUDGET,
        tt_cap=0,
        chance_drop="type",
        threads=int(threads),
    )


# --------------------------------------------------------------------------- #
# Capturing one PYTHON decision                                                #
# --------------------------------------------------------------------------- #
class PoolSpy:
    """Record every `(agg_n, agg_w)` handed to `fair_agent.pooled_q_argmax`.

    The agent holds no reference to `agg_w`, so this is the only way to compare
    the pooled floats — which is the half of the gate that action identity alone
    would not catch (two different pools can pick the same move)."""

    def __init__(self):
        self.calls: list[tuple[dict, dict]] = []
        self._orig = None

    def __enter__(self):
        self._orig = fair_agent.pooled_q_argmax

        def spy(agg_n, agg_w, min_visits=MIN_POOLED_VISITS):
            self.calls.append((dict(agg_n), dict(agg_w)))
            return self._orig(agg_n, agg_w, min_visits)

        fair_agent.pooled_q_argmax = spy
        return self

    def __exit__(self, *exc):
        fair_agent.pooled_q_argmax = self._orig
        return False


def _counters(agent) -> dict:
    return {
        "heur_moves": int(agent.heur_moves),
        "exact_moves": int(agent.exact_moves),
        "n_timeouts": int(agent.n_timeouts),
        "solver_nodes": int(agent.solver_nodes),
    }


def py_decision(agent, board, spy: PoolSpy) -> dict:
    """Run ONE `choose_action` on the Python oracle and reduce it to the
    comparable record.  `spy` must already be active."""
    before = _counters(agent)
    n_calls = len(spy.calls)
    was_latched = bool(agent._latched)
    with T.production_leaf_dispatch():
        action = int(agent.choose_action(board))
    after = _counters(agent)
    calls = spy.calls[n_calls:]

    exact = after["exact_moves"] > before["exact_moves"]
    timeout = after["n_timeouts"] > before["n_timeouts"]
    searched = after["heur_moves"] > before["heur_moves"]
    lpv = agent.last_pooled_visits or {}
    # A forced move increments heur_moves, pools NOTHING, and stamps a one-hot
    # policy; the "nothing visited" pathological branch stamps an EMPTY one.
    forced = searched and not calls and bool(lpv)
    pooled: list[tuple[int, int, int]] = []
    if calls:
        agg_n, agg_w = calls[-1]
        pooled = [(int(a), ubits(agg_n[a]), ubits(agg_w[a])) for a in agg_n]
    return {
        "action": action,
        "pooled": pooled,
        "forced": bool(forced),
        "exact": bool(exact),
        "latched": bool(was_latched or exact or timeout),
        "timeout": bool(timeout),
        "solver_nodes": after["solver_nodes"] - before["solver_nodes"],
        "last_pooled_visits": [(int(a), ubits(v)) for a, v in lpv.items()],
    }


def rs_decision(agent, move_idx: int | None = None) -> dict:
    """The same record from the Rust leg."""
    action = int(agent.choose_action(move_idx))
    m = agent.last_move()
    return {
        "action": action,
        "pooled": [(int(a), int(n), int(w)) for a, n, w in m["pooled"]],
        "forced": bool(m["forced"]),
        "exact": bool(m["exact"]),
        "latched": bool(m["latched"]),
        "timeout": bool(m["timeout"]),
        "solver_nodes": int(m["solver_nodes"]),
        "last_pooled_visits": [],   # filled by the caller when compared
    }


DECISION_FIELDS = ("action", "forced", "exact", "latched", "timeout",
                   "solver_nodes", "pooled")


def compare_decision(py: dict, rs: dict, tag: str) -> list[dict]:
    """Field-by-field; returns a (possibly empty) list of mismatch records."""
    bad = []
    for f in DECISION_FIELDS:
        a, b = py[f], rs[f]
        if f == "pooled":
            a = [tuple(x) for x in a]
            b = [tuple(x) for x in b]
        if a != b:
            rec = {"tag": tag, "field": f}
            if f == "pooled":
                da = {x[0]: x[1:] for x in a}
                db = {x[0]: x[1:] for x in b}
                diffs = [(k, da.get(k), db.get(k))
                         for k in sorted(set(da) | set(db)) if da.get(k) != db.get(k)]
                rec["n_actions"] = [len(a), len(b)]
                rec["order_py"] = [x[0] for x in a][:16]
                rec["order_rs"] = [x[0] for x in b][:16]
                rec["diffs"] = diffs[:8]
                rec["n_diffs"] = len(diffs)
            else:
                rec["py"], rec["rs"] = a, b
            bad.append(rec)
    return bad


# --------------------------------------------------------------------------- #
# The exact solver                                                             #
# --------------------------------------------------------------------------- #
def solver_module():
    import endgame_solver as S
    return S


def py_solve(game: Game, board, budget: int = EXACT_BUDGET) -> dict | None:
    """`endgame_solver.solve(mode="marginalized", alphabeta=False)` — the oracle.
    `None` on `BudgetExceeded`, exactly what the agent sees."""
    S = solver_module()
    try:
        with T.production_leaf_dispatch():
            r = S.solve(game, board, mode="marginalized", budget=int(budget),
                        alphabeta=False)
    except S.BudgetExceeded:
        return None
    return {
        "value_bits": ubits(r.value),
        "to_move": int(r.to_move),
        "optimal_actions": [int(a) for a in r.optimal_actions],
        "child_values": [(int(a), ubits(v)) for a, v in r.child_values.items()],
        "nodes": int(r.nodes),
    }


def rs_solve(agent, budget: int = EXACT_BUDGET) -> dict | None:
    d = agent.solve_marginalized(int(budget))
    if d is None:
        return None
    return {
        "value_bits": int(d["value_bits"]),
        "to_move": int(d["to_move"]),
        "optimal_actions": [int(a) for a in d["optimal_actions"]],
        "child_values": [(int(a), int(v)) for a, v in d["child_values"]],
        "nodes": int(d["nodes"]),
    }


SOLVER_FIELDS = ("value_bits", "to_move", "optimal_actions", "child_values", "nodes")


def compare_solve(py, rs, tag: str) -> list[dict]:
    if (py is None) != (rs is None):
        return [{"tag": tag, "field": "budget_exceeded",
                 "py": py is None, "rs": rs is None}]
    if py is None:
        return []
    bad = []
    for f in SOLVER_FIELDS:
        a, b = py[f], rs[f]
        if f == "child_values":
            a = [tuple(x) for x in a]
            b = [tuple(x) for x in b]
        if a != b:
            rec = {"tag": tag, "field": f}
            if f == "child_values":
                da = {x[0]: x[1] for x in a}
                db = {x[0]: x[1] for x in b}
                rec["diffs"] = [(k, da.get(k), db.get(k))
                                for k in sorted(set(da) | set(db))
                                if da.get(k) != db.get(k)][:8]
            else:
                rec["py"], rec["rs"] = a, b
            bad.append(rec)
    return bad


# --------------------------------------------------------------------------- #
# Latch trajectory (pure engine — no search)                                   #
# --------------------------------------------------------------------------- #
def k_remaining_py(board) -> int:
    return fair_agent.k_remaining(board.state)


def latch_trajectory_py(game: Game, actions) -> list[tuple[int, int, bool]]:
    """`[(ply, k_remaining, latched_at_entry)]` over a whole recorded game,
    replaying `actions`.  `latched` is the agent's one-way state as it would be
    on ENTRY to that ply's `choose_action`."""
    board = game.get_init_board()
    latched = False
    out = []
    for i, a in enumerate(actions):
        k = k_remaining_py(board)
        if not latched and board.state.phase == GamePhase.TILES and k <= EXACT_MAX_K:
            latched = True
        out.append((i, int(k), bool(latched)))
        board, _ = game.get_next_state(board, int(a))
    return out


def latch_trajectory_rs(deck_seed: int, actions) -> list[tuple[int, int, bool]]:
    ms = carc_rs.MirrorState.from_seed(str(int(deck_seed)))
    latched = False
    out = []
    for i, a in enumerate(actions):
        k = ms.deck_len() + (0 if ms.is_terminal() else 1)
        if not latched and ms.phase() == "tiles" and k <= EXACT_MAX_K:
            latched = True
        out.append((i, int(k), bool(latched)))
        ms.advance(int(a))
    return out


@contextlib.contextmanager
def closing_agent(agent):
    try:
        yield agent
    finally:
        with contextlib.suppress(Exception):
            agent.close()
