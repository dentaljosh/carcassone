"""Track-F Gate A oracle-prior extraction helpers (F2, 2026-07-19).

SINGLE SOURCE OF TRUTH for the "root MCTS visit distribution -> root-prior override"
conversion used by BOTH Gate A harnesses:

  * the CLAIRVOYANT screen ``scripts/classical_search/eval_puct_priors.py`` (which
    re-exports these under the private names ``_root_action_groups`` /
    ``_oracle_prior_from_visits`` / ``_LeafCounter``), and
  * the FAIR confirm ``scripts/classical_search/eval_fair_puct.py`` via the library
    ``FairHeuristicPriorAgent`` (which imports them here for its per-world pre-search).

Lifted verbatim from eval_puct_priors.py (commit 038f5dd) so the clairvoyant and fair
oracle probes can NEVER diverge on the alias-folding / epsilon-floor / renormalization
semantics — the same "reuse, don't duplicate" discipline as ``c5_leaf_override``. A
release test asserts the identity (tests/test_fair_oracle_prior.py::
test_extraction_reuse_no_divergence).

These are pure functions over a ``Game`` wrapper + a visit distribution; the module
imports nothing heavy (numpy only), so both the library agent and the scripts can
depend on it without an import cycle."""
from __future__ import annotations

import numpy as np


def root_action_groups(game, board) -> dict:
    """Group the legal ROOT actions by the child board they lead to (== the
    search's transposition key), returning {repr_action: [members]} with the repr
    the lowest-index member. Symmetric-tile rotations that step to the IDENTICAL
    child board collide onto ONE node in the PUCT tree; this reproduces that
    grouping EXACTLY (same string_representation key) so the oracle prior folds
    rotation aliases the way the search already does. Cheap: n_legal get_next_state
    steps (no board mutation, no legal-cache touch), negligible vs the sim budget."""
    mask = game.get_valid_moves(board)
    legal = [int(a) for a in np.flatnonzero(mask)]
    by_key: dict[str, list[int]] = {}
    for a in legal:
        child, _ = game.get_next_state(board, a)
        key = game.string_representation(child)
        by_key.setdefault(key, []).append(a)
    return {min(members): sorted(members) for members in by_key.values()}


def oracle_prior_from_visits(groups: dict, counts_by_action: dict,
                             eps_coef: float) -> dict:
    """Convert a pre-search root visit distribution into a prior over legal root
    actions (Gate A). ``groups`` = {repr_action: [members]} from
    ``root_action_groups``; ``counts_by_action`` = {action: visit_count} from the
    deduped pre-search root distribution (only ONE member per group carries the
    combined visit count). Returns {action: prior} over ALL legal actions.

    Mechanics (documented for the writeup):
      * group_mass(g) = summed pre-search visits of g's members (= the group's
        combined child-node visit count).
      * prior(g) = group_mass / total_visits.
      * epsilon floor: eps = eps_coef / n_groups (a 1e-3/n_actions-style floor);
        floor each GROUP's prior at eps so a move the pre-search never visited
        still gets a live PUCT exploration term, then renormalize over groups.
      * scatter: the whole group prior sits on the group's repr (lowest-index)
        action; other members get 0.0 — their mass is folded back onto whatever
        action the main search picks as the transposition representative via
        NeuralMCTS._link_child's ``prior_bonus``, so the group competes once with
        the summed mass (invariant to which member is the main-search repr).
      * degenerate all-zero pre-search (no visits at all) → uniform over groups.
    """
    n_groups = len(groups)
    if n_groups == 0:
        return {}
    group_mass = {r: sum(counts_by_action.get(m, 0.0) for m in members)
                  for r, members in groups.items()}
    total = sum(group_mass.values())
    eps = float(eps_coef) / n_groups
    if total <= 0.0:
        raw = {r: 1.0 / n_groups for r in group_mass}
    else:
        raw = {r: m / total for r, m in group_mass.items()}
    floored = {r: max(p, eps) for r, p in raw.items()}
    z = sum(floored.values())
    gp = {r: p / z for r, p in floored.items()}
    override: dict[int, float] = {}
    for repr_a, members in groups.items():
        override[int(repr_a)] = gp[repr_a]
        for m in members:
            if m != repr_a:
                override[int(m)] = 0.0
    return override


class LeafCounter:
    """Wrap a NeuralMCTS evaluator callable to COUNT invocations (= per-node leaf/
    root expansions) for the Gate A cost accounting, forwarding every attribute
    (wants_parent / root_logits / heur_prior_cfg / leaf_name) so the search is
    otherwise byte-identical. Reset ``.n = 0`` around a phase to count it."""

    def __init__(self, fn):
        object.__setattr__(self, "_fn", fn)
        object.__setattr__(self, "n", 0)

    def __call__(self, *a):
        self.n += 1
        return self._fn(*a)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_fn"), name)
