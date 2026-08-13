#!/usr/bin/env python3
"""Leaf top-2 tie-structure census — the shared library.

Builds a CENSUS of how often, and how, the production leaf (hash
``a36d2e15a3b3d71d``) fails to discriminate the best TILE placement: the exact-tie
rate on the outer chain value, the SIZE of the tied set, the gap to the runner-up
when there is no tie, and how the tie structure varies with game phase. Leaf
evaluations only — NO search, NO oracle scoring.

Companion driver (corpus loading, sampling, subprocess-per-rules-profile
orchestration): ``scripts/tiletie/run_census.py``.
Tests: ``tests/test_tiletie_census.py``.

FIDELITY CONTRACT
------------------
This module MUST reproduce ``scripts/jcz_mining/mine_disagreements.py``'s leaf
construction and chain enumeration exactly, so the tie rates measured here are
comparable BY CONSTRUCTION to that script's reported 55.1% top-2 exact-tie rate
on the JCloisterZone corpus. Two functions below (`chain_values`, `argmax_chain`)
are COPIED from ``scripts/jcz_mining/mine_disagreements.py`` lines 408-451 (bar a
cosmetic rename / TILE-only specialisation noted in each docstring) — the body of
each is otherwise byte-identical. Do NOT import ``mine_disagreements`` here (it
has heavy import-time side effects and a different CLI contract); fidelity is
instead proven bit-for-bit in ``tests/test_tiletie_census.py`` (imports
``mine_disagreements`` locally, inside the test only).

Import discipline (mirrors ``mine_disagreements.py``): STDLIB (+ numpy, which
carries no import-time env dependency) ONLY at module level. ``carcassonne_ai``
must never be imported before ``CARCASSONNE_FIX_R9`` is exported (see
`prepare_env`) — ``base_deck`` latches it at import into a Rust ``OnceLock``.
Every function that needs the engine imports it lazily, inside the function body.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# `match` (scripts/jcz_match) and `env_preamble` (scripts/human_anchor) are
# siblings under scripts/, not packages; both are needed by `prepare_env` below.
# Mirrors scripts/jcz_mining/mine_disagreements.py lines 141-151.
for _rel in ("scripts/jcz_match", "scripts/human_anchor"):
    _p = str(REPO / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The leaf of record (`ev_loss.LEAF_HASH_OF_RECORD`; `mine_disagreements.extract`
#: asserts the same value implicitly by construction). A leg whose resolved leaf
#: does not hash to this is refused, never silently graded under a different leaf.
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

#: eps=0.0 is the EXACT tie (bit-identical floats, no quantisation). The rest of
#: the grid characterises how much the tie rate depends on a discrimination
#: threshold an epsilon would have to be justified from (GOAL table 3).
TIE_EPS_GRID = (0.0, 0.05, 0.2, 0.5, 1.0)

#: Project-standard phase cuts on `k_remaining` — copied from
#: scripts/measurement_infra/sample_agreement_roots.py `PHASE_CUTS` (lines
#: 94-103), NOT redefined independently, so a census phase bucket is always the
#: same axis as every other measurement artifact in the repo (e.g. the CL-070
#: root bank's own `phase_bucket` field, reproduced by this same function).
PHASE_CUTS = {"early": (48, 1e9), "mid": (24, 48), "late": (-1, 24)}

#: Cap on `tie_actions_exact` written to a census row — `n_legal` (and so the
#: worst-case tie size) can run into the 30s; a 12-cap bounds row size on disk
#: without losing the SIZE, which is what the summary tables key on.
TIE_ACTIONS_CAP = 12

#: The full documented key set of a `census_ply` row (GOAL spec + this module).
#: Used by the driver and by tests/test_tiletie_census.py to assert schema
#: completeness. Order is cosmetic. `h200_top2_q_gap` / `bank_phase_bucket` are
#: populated only on `selfplay/bank` rows and `None` elsewhere, so every row
#: shares one schema regardless of stratum/source.
ROW_SCHEMA_KEYS = (
    "n_cand", "top1", "top2", "gap", "tie_exact", "tie_size_exact",
    "tie_actions_exact", "tie_actions_exact_truncated", "by_eps", "argmax_action",
    "stratum", "source", "rules_profile", "game_label", "root_id", "deck_seed",
    "ply", "seat", "k_remaining", "phase_bucket", "tercile", "n_legal", "checksum",
    "action_played", "played_in_tieset_exact", "played_is_argmax", "secs",
    "h200_top2_q_gap", "bank_phase_bucket",
)


def phase_bucket(k_remaining: int) -> str:
    """`"early"|"mid"|"late"` from `k_remaining`, using the project-standard cuts
    (`PHASE_CUTS`). Identical logic to
    `sample_agreement_roots.phase_bucket` (strict inequalities on both ends;
    falls through to `"late"` if nothing else matches, which only fires at the
    `k_remaining <= -1` edge — i.e. never for a real board)."""
    k = int(k_remaining)
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k < hi:
            return name
    return "late"


def tercile_of(ply: int, n_plies: int) -> int:
    """Which third of the SOURCE GAME this ply falls in (0/1/2) — read the other
    way from `phase_bucket`: a fixed fraction of this game's own length, rather
    than an absolute `k_remaining` cut, so the phase trend can be read two ways
    (GOAL table 4). `n_plies` <= 0 degenerates to tercile 0."""
    n = int(n_plies)
    if n <= 0:
        return 0
    idx = int((int(ply) / n) * 3)
    return min(max(idx, 0), 2)


# --------------------------------------------------------------------------- #
# env + leaf construction                                                       #
# --------------------------------------------------------------------------- #
def prepare_env(profile: str) -> dict:
    """Export the import-latched rules env, THEN the production leaf env, THEN
    return. MUST be called before any `carcassonne_ai` import.

    Mirror of ``scripts/jcz_mining/mine_disagreements.prepare_env`` (lines
    313-320): the same two-step order (rules env via `match.export_profile_env`,
    then `env_preamble` for the leaf env), generalised to take `profile` as an
    argument instead of that module's hardcoded ``PROFILE = "fixed_v1"`` — this
    census runs three profile legs (`walled`, `fixed_v1`, `app_aug2`), not one.
    """
    import match as JM                                   # stdlib-only at module level
    env = JM.export_profile_env(profile)
    import env_preamble                                  # noqa: F401  leaf env
    return {**env, "leaf_env": dict(env_preamble.RESOLVED)}


def build_leaf():
    """The exact leaf construction idiom of `mine_disagreements.extract()` (lines
    756-767). Returns ``(leaf, cfg, leaf_hashes, bag_close)`` where
    ``leaf(state, seat) -> float``. Raises ``AssertionError`` if the resolved
    leaf does not hash to `LEAF_HASH_OF_RECORD`. Call only AFTER `prepare_env()`
    (the production leaf env must already be exported — `champion_factory`'s
    `DEFAULT_CONFIG`-adjacent state is import-frozen)."""
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai import flat_leaf

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)                                   # R1/R7-class provenance guard
    leaf_hashes = dict(CF.resolved_manifest("clairvoyant", verify=True)
                       .get("leaf_hashes") or {})
    got = leaf_hashes.get("harness_leaf_hash")
    if got != LEAF_HASH_OF_RECORD:
        raise AssertionError(
            f"leaf hash mismatch: resolved harness_leaf_hash={got!r}, expected "
            f"{LEAF_HASH_OF_RECORD!r} -- this census would not be comparable to "
            "the JCZ 55.1% figure under a different leaf.")
    bag_close = bool(getattr(cfg, "bag_close", False))

    def leaf(state, seat):
        # PRE-ROUND float, always from the ACTING player's point of view — same
        # contract as mine_disagreements.extract's `leaf()`.
        return float(flat_leaf.flat_virtual_score_v2_float(state, int(seat), cfg, bag_close))

    return leaf, cfg, leaf_hashes, bag_close


# --------------------------------------------------------------------------- #
# chain_values / argmax_chain — COPIED from scripts/jcz_mining/mine_disagreements.py
# lines 408-451 (`chain_values`, `argmax_chain`). `chain_values` here is
# specialised to `ply_class="TILE"` (this census only ever runs the TILE
# instrument — the original's `ply_class` branch is inlined rather than
# threaded through as a parameter) and `jcz_seat` is renamed `seat`; the body is
# otherwise byte-identical. Bit-for-bit fidelity against the original — called
# with `ply_class="TILE"` — is proven in tests/test_tiletie_census.py.
# --------------------------------------------------------------------------- #
def chain_values(game, board, seat: int, leaf) -> list:
    """Every legal outer (tile) action's CHAIN value, in ascending action order.

    Returns ``[(action, value, chain), ...]``. Apply `t`; if the successor is
    STILL `seat`'s turn (the meeple decision) take the best legal meeple action
    (ties resolve to the lowest action index — ascending iteration, strict `>`);
    otherwise the chain is the tile alone. `leaf` is a 1-arg callable
    `state -> float`, already closed over the acting seat (matches
    `mine_disagreements.extract`'s ``lambda st: leaf(st, jcz_seat)`` idiom).
    """
    import numpy as np

    out = []
    for a in (int(x) for x in np.flatnonzero(game.get_valid_moves(board))):
        s1, _ = game.get_next_state(board, a)
        if int(s1.state.current_player) == int(seat):
            legal2 = [int(x) for x in np.flatnonzero(game.get_valid_moves(s1))]
            if legal2:
                best_v, best_m = None, None
                for m in legal2:                    # ascending -> lowest index wins ties
                    s2, _ = game.get_next_state(s1, m)
                    v = leaf(s2.state)
                    if best_v is None or v > best_v:
                        best_v, best_m = v, m
                out.append((a, best_v, [a, best_m]))
                continue
        out.append((a, leaf(s1.state), [a]))
    return out


def argmax_chain(values: list):
    """``(pick, value, chain, leaf_tie)`` from `chain_values`' output. COPIED
    VERBATIM from `mine_disagreements.argmax_chain` (lines 436-451). Ties on the
    argmax resolve to the LOWEST action index (the list is already in ascending
    action order and the comparison is strict `>`). `leaf_tie` is true iff the
    top TWO chain values are exactly equal as floats."""
    best = None
    for a, v, chain in values:
        if best is None or v > best[1]:
            best = (a, v, chain)
    ranked = sorted((v for _a, v, _c in values), reverse=True)
    tie = len(ranked) >= 2 and ranked[0] == ranked[1]
    return best[0], best[1], best[2], tie


# --------------------------------------------------------------------------- #
# tie_report — the census primitive                                             #
# --------------------------------------------------------------------------- #
def tie_report(values: list, eps_grid=TIE_EPS_GRID) -> dict:
    """The per-ply tie structure from `chain_values`' output.

    Ties are on the OUTER chain value — the value `argmax_chain` actually ranks
    — matching `mine_disagreements`' own `leaf_tie` semantics (its docstring
    ambiguity 4: "evaluated on the OUTER per-action chain values ... not on the
    inner meeple values"). Membership at `eps` is `top1 - value <= eps`
    (inclusive); `eps=0.0` reproduces the exact-tie case bit-for-bit because
    subtracting two bit-identical floats is exactly `0.0 <= 0.0`.

    Action-id lists are always returned in ascending order, independent of the
    input list's order (defensive: this census's own callers always pass
    `chain_values`' already-ascending output, but a caller must not have to
    trust that to get a correct `tie_actions_exact`).
    """
    if not values:
        raise ValueError("tie_report: empty values (chain_values returned nothing)")

    vals_desc = sorted((float(v) for _a, v, _c in values), reverse=True)
    top1 = vals_desc[0]
    top2 = next((v for v in vals_desc[1:] if v != top1), None)
    gap = None if top2 is None else (top1 - top2)

    tie_actions_exact = sorted(int(a) for a, v, _c in values if v == top1)
    tie_size_exact = len(tie_actions_exact)
    tie_exact = tie_size_exact >= 2
    argmax_action = tie_actions_exact[0]           # lowest index among the top1 set

    by_eps = {}
    for eps in eps_grid:
        members = sorted(int(a) for a, v, _c in values if (top1 - float(v)) <= eps)
        by_eps[str(eps)] = {"tie": len(members) >= 2, "size": len(members),
                            "actions": members}

    return {
        "n_cand": len(values),
        "top1": top1,
        "top2": top2,
        "gap": gap,
        "tie_exact": tie_exact,
        "tie_size_exact": tie_size_exact,
        "tie_actions_exact": tie_actions_exact,
        "by_eps": by_eps,
        "argmax_action": argmax_action,
    }


# --------------------------------------------------------------------------- #
# census_ply — one emitted jsonl row                                            #
# --------------------------------------------------------------------------- #
def census_ply(game, board, seat: int, leaf, *, meta: dict) -> dict:
    """One flat jsonl row: `tie_report`'s fields (trimmed for disk — see below)
    plus positional/provenance metadata from `meta`.

    `leaf` is the natural 2-arg `leaf(state, seat) -> float` callable
    `build_leaf()` returns. `census_ply` binds `seat` itself before handing a
    1-arg closure down to `chain_values` (which keeps the exact 1-arg contract
    `mine_disagreements.chain_values` uses, since that is what fidelity is
    proven against) — callers of `census_ply` never have to remember to close
    over the seat themselves. `meta` MUST supply: `stratum`, `source`,
    `rules_profile`, `game_label`, `root_id`, `deck_seed`, `ply`, `n_plies` (the
    SOURCE game's total ply count, for `tercile`). MAY supply: `action_played`
    (int or None — the action actually taken at this ply in the source game),
    `k_remaining` (int; computed via `fair_agent.k_remaining` off `board.state`
    if absent), `h200_top2_q_gap`, `bank_phase_bucket` (both passed straight
    through, `None` if absent — populated on `selfplay/bank` rows only, so
    every row still shares one schema).

    Trims `tie_report`'s output for disk: `by_eps` keeps only `tie`/`size` per
    epsilon (drops the per-eps action lists — reconstructable from
    `tie_actions_exact` at eps=0, and not needed at other eps for the summary
    tables), and `tie_actions_exact` is capped at `TIE_ACTIONS_CAP` entries with
    a `tie_actions_exact_truncated` flag.
    """
    t0 = time.time()
    # Checksum FIRST, before `chain_values` walks `game.get_next_state` over every
    # legal action from `board`. `get_next_state` is documented + tested not to
    # mutate its input board (`game_wrapper.Game.get_next_state`: "Safe — input
    # board is unmodified"), but `checksum` is the field a later oracle-scoring
    # run leans on to prove lossless replay — take it before, not after, so a
    # regression in that guarantee corrupts nothing silently (it would instead
    # show up as `checksum` disagreeing with the source bank's own recorded one).
    checksum = game.string_representation(board)

    def _bound_leaf(state):
        return leaf(state, seat)

    values = chain_values(game, board, seat, _bound_leaf)
    rep = tie_report(values)

    k_remaining = meta.get("k_remaining")
    if k_remaining is None:
        from carcassonne_ai import fair_agent
        k_remaining = int(fair_agent.k_remaining(board.state))
    else:
        k_remaining = int(k_remaining)

    action_played = meta.get("action_played")
    action_played = None if action_played is None else int(action_played)
    top1 = rep["top1"]
    played_in_tieset_exact = None
    played_is_argmax = None
    if action_played is not None:
        top1_actions = {int(a) for a, v, _c in values if v == top1}
        played_in_tieset_exact = action_played in top1_actions
        played_is_argmax = (action_played == int(rep["argmax_action"]))

    tie_actions_exact_full = rep["tie_actions_exact"]
    tie_actions_exact = tie_actions_exact_full[:TIE_ACTIONS_CAP]
    truncated = len(tie_actions_exact_full) > TIE_ACTIONS_CAP

    by_eps_row = {k: {"tie": v["tie"], "size": v["size"]} for k, v in rep["by_eps"].items()}

    ply = int(meta["ply"])
    n_plies = int(meta["n_plies"])

    row = {
        "n_cand": rep["n_cand"],
        "top1": rep["top1"],
        "top2": rep["top2"],
        "gap": rep["gap"],
        "tie_exact": rep["tie_exact"],
        "tie_size_exact": rep["tie_size_exact"],
        "tie_actions_exact": tie_actions_exact,
        "tie_actions_exact_truncated": truncated,
        "by_eps": by_eps_row,
        "argmax_action": int(rep["argmax_action"]),
        "stratum": meta["stratum"],
        "source": meta["source"],
        "rules_profile": meta["rules_profile"],
        "game_label": meta["game_label"],
        "root_id": meta["root_id"],
        "deck_seed": int(meta["deck_seed"]),
        "ply": ply,
        "seat": int(seat),
        "k_remaining": k_remaining,
        "phase_bucket": phase_bucket(k_remaining),
        "tercile": tercile_of(ply, n_plies),
        "n_legal": rep["n_cand"],
        "checksum": checksum,
        "action_played": action_played,
        "played_in_tieset_exact": played_in_tieset_exact,
        "played_is_argmax": played_is_argmax,
        "secs": round(time.time() - t0, 4),
        "h200_top2_q_gap": meta.get("h200_top2_q_gap"),
        "bank_phase_bucket": meta.get("bank_phase_bucket"),
    }
    assert set(row) == set(ROW_SCHEMA_KEYS), (
        f"census_ply row schema drift: {set(row) ^ set(ROW_SCHEMA_KEYS)}")
    return row
