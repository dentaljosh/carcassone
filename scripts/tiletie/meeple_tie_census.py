#!/usr/bin/env python3
"""MEEPLE-ply leaf tie kill-census — rung (1) of the tie-arbiter widening campaign.

Spec of record: ``measurement/tiearb_widening_20260817/PLAN_meeple_ties.md`` §4
(the FREE CENSUS) + §5 (the read-rule skeleton whose branches this file's
`MEEPLE_CENSUS.json` feeds), and the orchestrator consolidation
``measurement/tiearb_widening_20260817/CAMPAIGN.md`` sequencing item 0 (this is
the first physical action after the freeze lifts) and its eps-piggyback ruling.

WHAT THIS IS
------------
A CENSUS: deterministic replay of already-banked champion games plus LEAF calls.
No search, no PUCT, no MCTS, no playouts, **no outcome statistic of any kind**.
The source jsonl carries `score_p0`/`score_p1`; this instrument never reads them
(`_GAME_FIELDS_READ` below is the whole contract, and a test pins it). That is
the blind-discipline line for rung (1): the census may count, and may not learn
anything about who won.

⚠️ C5 (the duplicate-invariance CRN-playout check sketched in PLAN §4) is
DELIBERATELY NOT IMPLEMENTED HERE — it needs tier1 playouts and therefore
world-mean margins, which is exactly the outcome-statistic class this instrument
is forbidden to touch. It belongs in its own PASS/FAIL harness.

THE QUESTION
------------
The arbiter's premise is that tied moves are *game-distinct* and the leaf simply
cannot separate them. At MEEPLE plies a whole class of ties is instead
**DUPLICATES**: two legal meeple actions claiming the SAME connected feature (a
city with two openings offers a knight slot on each — either claims the one
city). Those are guaranteed leaf ties, they are never collapsed by the rust arm
builder (`tiearb.rs:275` dedupes on the afterstate repr, and `repr_key.rs:88-107`
writes `(meeple_type, row, col, side)` per placed meeple, so two duplicate slots
produce two DIFFERENT keys and survive as two arms), and arbitration cannot
extract one bit from them.

So the census reports the tied-set composition under THREE groupings, and the
gap between them IS the finding:

1. ``repr_arms``            — distinct afterstate `string_representation` keys.
                              **What `tiearb.rs` would actually build.**
2. ``equiv_groups_intratile``— distinct `meeple_equiv.feature_groups` ids. The
                              July census's key (`meeple_dedup_census.py:86-96`);
                              an explicit LOWER BOUND on duplication because it
                              merges only features connected ON THE PLACED TILE.
3. ``equiv_groups_board``   — distinct BOARD-LEVEL claimed-region ids, from
                              `flat_leaf.decompose`'s whole-board union-find, so
                              farms merged across tiles collapse correctly.
                              **THE ARBITRABLE-CLASS DEFINITION OF RECORD.**

`repr_arms - equiv_groups_board` on a fired ply is the rust arm-dedup
inefficiency the plan flagged (duplicate arms crowd out distinct options against
the `J <= 4` cap and return identical world-means).

THE EPS PIGGYBACK (PLAN_eps_near_ties.md §8)
--------------------------------------------
Rung (4) needs the per-ply scalar `gap = top1 - top2` (top2 = next DISTINCT leaf
value) so its `phi(eps)` becomes an arbitrary-eps CDF instead of 5 grid points.
Both classes get it here, from ONE replay pass:

* every MEEPLE row carries `gap` (free — `tie_report` computes it anyway);
* every TILE ply with `n_legal >= 2` is ALSO censused, via
  `chain_census.chain_values` + `chain_census.tie_report` verbatim, into a slim
  `tile_gap_rows.jsonl`. `--no-tile-gap` turns that leg off.

⚠️ READ-RULE NOTE on the tile leg. `PLAN_meeple_ties.md` §4 records that the
tiearb2 corpus's **TILE** positions are BURNED while its MEEPLE plies have never
been read. The tile-gap leg computes no strength/headroom statistic — it is a
`gap` histogram — but it IS a tile-class read of that corpus. Run it with
`--tile-gap-corpora champ449` (the default is `all`) if the owner wants the
burned corpus's tile plies left alone.

FIDELITY CONTRACT
-----------------
* leaf: `chain_census.build_leaf()` — asserts `a36d2e15a3b3d71d`, refuses otherwise.
* eps grid: `chain_census.TIE_EPS_GRID`, unchanged.
* tie primitive: `chain_census.tie_report`, unchanged (so `by_eps`, `gap`,
  `tie_size_exact` mean bit-for-bit what they mean in the 2026-08-12 tile census).
* MEEPLE chain values: `meeple_chain_values` below is
  `mine_disagreements.chain_values(..., ply_class="MEEPLE")` with the successor
  board retained (so the repr key costs no second `get_next_state`). Equality of
  the `(action, value, chain)` triples is pinned in
  `tests/test_meeple_tie_census.py`.
* phase buckets / terciles: `chain_census.phase_bucket`, unchanged.

Both corpora are `walled`, so unlike `run_census.py` there is no
subprocess-per-rules-profile fan-out: one process latches `CARCASSONNE_FIX_R9`
for `walled`, builds the leaf, and forks ONE `multiprocessing.Pool`.

Usage
-----
  meeple_tie_census.py [--games PATH[,PATH...]] [--workers W]
                       [--out-dir measurement/tiearb_widening_20260817/census]
                       [--limit-games N]        # smoke knob
                       [--no-tile-gap] [--tile-gap-corpora all|champ449|...]

Tests: ``tests/test_meeple_tie_census.py`` (grouping logic + gap emission; no
full-game replay, no leaf).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SCHEMA = "carcassonne-meeple-tie-census/v1"

#: The two corpora PLAN §4 verified on disk. 449 + 850 = 1,299 games, both
#: `walled`, both champion-policy root-replay jsonl. Labels are the corpus axis
#: every table is cut by; they are NEVER pooled silently (the 449-game corpus is
#: k4x688, shallower than today's champion).
DEFAULT_CORPORA = (
    ("champ449", REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"),
    ("tiearb2_850", REPO / "measurement" / "tiearb2_20260816" / "corpus"
                    / "champ_games_tiearb2.jsonl"),
)

OUT_DIR_DEFAULT = REPO / "measurement" / "tiearb_widening_20260817" / "census"

#: BLIND DISCIPLINE. The only keys this instrument may read out of a corpus
#: record. `score_p0` / `score_p1` / `sentinel` are outcome fields and are NOT
#: here; `load_games` enforces the restriction and a test pins the tuple.
_GAME_FIELDS_READ = ("game_id", "deck_seed", "actions", "n_plies")

#: Supply bar from PLAN §5 (derived from the tile rung's own realized transfer),
#: carried here only so `CENSUS.md` can print which branch the numbers land in.
#: The branch is ADJUDICATED by a human against the plan, not by this script.
BRANCH_BARS = {"dead_below": 4.0, "price_at_or_above": 8.0, "arbitrable_fraction": 0.40}

#: Cap on action-id lists written to a row (mirrors `chain_census.TIE_ACTIONS_CAP`).
TIE_ACTIONS_CAP = 12

#: Arm cap the rust arbiter applies (`J <= 4`); the census reports the rate at
#: which the DEDUPED-BY-REPR arm count would exceed it.
J_CAP = 4

# Worker global — set in the parent BEFORE the fork, never pickled (the fork
# carries it for free; mirrors `run_census._LEAF`).
_LEAF = None


# =========================================================================== #
# GROUPING — the testable core. Engine-light: `decompose` + the tile model,    #
# no search, no leaf, no full game.                                           #
# =========================================================================== #
#: Region key returned for the meeple-phase PASS action. Passing is always its
#: own arm under every grouping (it is game-distinct from every placement), so
#: it must never share a key with a placement or with another undescribed slot.
PASS_KEY = ("pass",)


def claimed_region_key(decomp, tile, row: int, col: int, meeple_type, side):
    """BOARD-LEVEL identity of the feature a meeple action would claim.

    ``decomp`` is `flat_leaf.decompose(state)` for the CURRENT (meeple-phase)
    board — the tile is already placed, so the region the meeple joins is fully
    determined. Returns a hashable key, or ``None`` when the tile model does not
    describe the slot (caller must then give it a PRIVATE group — this function
    never claims an equivalence it cannot prove).

    Four cases, in the order the engine itself resolves them:

    * FARMER slot -> ``("farm", root)`` from `decomp.farm_anypos_root`, which is
      keyed by ``(r, c, Side.TOP_LEFT|...)`` exactly as an action decodes.
      **This is the case the intra-tile key gets wrong**: two corners separate on
      the placed tile but already joined through the rest of the board are ONE
      field, and only the union-find sees it.
    * NORMAL on a city side  -> ``("city", root)``.
    * NORMAL on a road side  -> ``("road", root)``.
    * NORMAL on CENTER of a chapel/flowers tile -> ``("cloister", row, col)``
      (a cloister is a one-tile feature, so the tile coordinate IS its region).

    City / road / farm roots come from three independent node-index spaces, so
    the leading tag is load-bearing, not decoration.
    """
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.side import Side

    if meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
        root = decomp.farm_anypos_root.get((row, col, side))
        return None if root is None else ("farm", root)

    root = decomp.city_side_root.get((row, col, side))
    if root is not None:
        return ("city", root)
    root = decomp.road_side_root.get((row, col, side))
    if root is not None:
        return ("road", root)
    if side == Side.CENTER and tile is not None and (
            getattr(tile, "chapel", False) or getattr(tile, "flowers", False)):
        return ("cloister", int(row), int(col))
    return None


def intratile_region_key(tile, meeple_type, side):
    """INTRA-TILE identity — the July census's key (`meeple_equiv.feature_groups`),
    reproduced here as a key function so all three groupings share one dense
    numbering. ``None`` for an undescribed slot (private group), same convention
    as `claimed_region_key`.

    Deliberately a LOWER BOUND on true equivalence: it reads ONE tile, so two
    sides joined only through the rest of the board read as distinct.
    `meeple_equiv` already namespaces farmer ids away from knight ids; the
    `meeple_type` tag here makes that structural rather than incidental.
    """
    from carcassonne_ai import meeple_equiv as ME

    raw = ME.feature_groups(tile)
    gid = raw.get(side.value)
    if gid is None:
        return None
    return ("intratile", str(meeple_type), int(gid))


def dense_group_ids(action_keys: dict) -> dict:
    """``{action: key_or_None}`` -> ``{action: dense group id}``.

    Dense ids assigned in ascending ACTION order (matches
    `meeple_equiv.equivalent_meeple_action_groups`' convention, so a group id
    printed by this census means the same thing as one printed by the search's
    telemetry). A ``None`` key is an undescribed slot and gets a PRIVATE group of
    its own — never merged with another ``None``.
    """
    out: dict = {}
    dense: dict = {}
    for a in sorted(action_keys):
        key = action_keys[a]
        k = ("solo", int(a)) if key is None else key
        if k not in dense:
            dense[k] = len(dense)
        out[int(a)] = dense[k]
    return out


def n_groups(group_ids: dict) -> int:
    """Distinct group count of a `dense_group_ids` map."""
    return len(set(group_ids.values()))


def meeple_action_keys(game, board, actions):
    """The three key maps for one meeple decision, over `actions` (ascending).

    Returns ``(board_keys, intratile_keys)`` — both ``{action: key_or_None}``.
    The repr key needs successor states and is built by `meeple_chain_values`.

    The meeple-phase PASS action gets `PASS_KEY` under both groupings.
    """
    from carcassonne_ai import flat_leaf
    from carcassonne_ai.action_space import decode, meeple_pass_index

    state = board.state
    last = state.last_tile_action
    if last is None:
        raise AssertionError("meeple_action_keys called at a board with no last_tile_action")
    row, col = int(last.coordinate.row), int(last.coordinate.column)
    tile = state.board[row][col]
    decomp = flat_leaf.decompose(state)
    pass_idx = meeple_pass_index(board.offset.size)

    board_keys: dict = {}
    intra_keys: dict = {}
    for a in actions:
        a = int(a)
        if a == pass_idx:
            board_keys[a] = PASS_KEY
            intra_keys[a] = PASS_KEY
            continue
        act = decode(a, off=board.offset, phase="meeples",
                     last_tile_coord=last.coordinate)
        side = act.coordinate_with_side.side
        mt = act.meeple_type
        board_keys[a] = claimed_region_key(decomp, tile, row, col, mt, side)
        intra_keys[a] = intratile_region_key(tile, mt, side)
    return board_keys, intra_keys


# =========================================================================== #
# MEEPLE chain values — mine_disagreements.chain_values(..., "MEEPLE")         #
# =========================================================================== #
def meeple_chain_values(game, board, seat: int, leaf) -> list:
    """``[(action, value, chain, successor_board), ...]`` in ascending action order.

    The MEEPLE branch of `scripts/jcz_mining/mine_disagreements.py:408-432`
    (*"On the MEEPLE class every chain is one action."*) — one `get_next_state`
    and one leaf call per legal action, chain ``[a]``. The only addition is the
    fourth tuple element: the successor board, retained so the afterstate repr
    key (`repr_arms`) costs no second `get_next_state`. Drop it and the first
    three elements are `chain_values(..., ply_class="MEEPLE")` verbatim — pinned
    in `tests/test_meeple_tie_census.py`.

    `leaf` is the 1-arg `state -> float` closure `mine_disagreements` uses.
    """
    import numpy as np

    out = []
    for a in (int(x) for x in np.flatnonzero(game.get_valid_moves(board))):
        s1, _ = game.get_next_state(board, a)
        out.append((a, leaf(s1.state), [a], s1))
    return out


def meeple_census_ply(game, board, seat: int, leaf, *, meta: dict) -> dict:
    """One emitted `meeple_rows.jsonl` row for a meeple decision with >=2 legal
    actions. Leaf calls only.

    Composition is reported over the EXACT-TIED SET (`tie_actions_exact`) — the
    set the arbiter would be handed — and, for context, over the FULL option set
    (`*_all` fields), which is what the July duplicate census counted.
    """
    import chain_census as CC

    t0 = time.time()

    def _bound_leaf(state):
        return leaf(state, seat)

    quad = meeple_chain_values(game, board, seat, _bound_leaf)
    values = [(a, v, c) for a, v, c, _s in quad]
    rep = CC.tie_report(values)

    actions_all = [a for a, _v, _c, _s in quad]
    board_keys, intra_keys = meeple_action_keys(game, board, actions_all)
    repr_keys = {int(a): game.string_representation(s) for a, _v, _c, s in quad}

    tied = list(rep["tie_actions_exact"])
    tied_set = set(tied)

    def _counts(keys, subset):
        sub = {a: keys[a] for a in subset}
        return n_groups(dense_group_ids(sub))

    repr_arms = _counts(repr_keys, tied)
    groups_intratile = _counts(intra_keys, tied)
    groups_board = _counts(board_keys, tied)

    from carcassonne_ai.action_space import meeple_pass_index
    pass_idx = meeple_pass_index(board.offset.size)
    n_nonpass = sum(1 for a in actions_all if a != pass_idx)

    k_remaining = meta.get("k_remaining")
    if k_remaining is None:
        from carcassonne_ai import fair_agent
        k_remaining = int(fair_agent.k_remaining(board.state))

    action_played = meta.get("action_played")
    action_played = None if action_played is None else int(action_played)

    row = {
        "ply_class": "MEEPLE",
        "corpus": meta["corpus"],
        "game_id": meta["game_id"],
        "deck_seed": int(meta["deck_seed"]),
        "ply": int(meta["ply"]),
        "seat": int(seat),
        "k_remaining": int(k_remaining),
        "phase_bucket": CC.phase_bucket(k_remaining),
        "tercile": CC.tercile_of(int(meta["ply"]), int(meta["n_plies"])),
        "n_legal": rep["n_cand"],
        "n_nonpass": n_nonpass,
        "pass_legal": pass_idx in actions_all,
        # --- tie structure (chain_census.tie_report, unchanged) --------------- #
        "top1": rep["top1"],
        "top2": rep["top2"],
        "gap": rep["gap"],                       # <- the eps piggyback scalar
        "tie_exact": rep["tie_exact"],
        "tie_size_exact": rep["tie_size_exact"],
        "tie_actions_exact": tied[:TIE_ACTIONS_CAP],
        "tie_actions_exact_truncated": len(tied) > TIE_ACTIONS_CAP,
        "by_eps": {k: {"tie": v["tie"], "size": v["size"]}
                   for k, v in rep["by_eps"].items()},
        "argmax_action": int(rep["argmax_action"]),
        # --- the three groupings, over the TIED set --------------------------- #
        "repr_arms": repr_arms,
        "equiv_groups_intratile": groups_intratile,
        "equiv_groups_board": groups_board,
        "pass_in_tieset": pass_idx in tied_set,
        # --- the same three over the FULL option set (July-census context) ----- #
        "repr_arms_all": n_groups(dense_group_ids(repr_keys)),
        "equiv_groups_intratile_all": n_groups(dense_group_ids(intra_keys)),
        "equiv_groups_board_all": n_groups(dense_group_ids(board_keys)),
        # --- provenance ------------------------------------------------------- #
        "action_played": action_played,
        "played_in_tieset_exact": (None if action_played is None
                                   else action_played in tied_set),
        "played_is_argmax": (None if action_played is None
                             else action_played == int(rep["argmax_action"])),
        "secs": round(time.time() - t0, 5),
    }
    return row


def tile_gap_ply(game, board, seat: int, leaf, *, meta: dict) -> dict:
    """One slim `tile_gap_rows.jsonl` row — the eps piggyback for the TILE class.

    `chain_census.chain_values` + `chain_census.tie_report` VERBATIM (so `gap`,
    `by_eps` and `tie_size_exact` are the same statistics the 2026-08-12 tile
    census published), minus `census_ply`'s `checksum` field: at ~92k tile plies
    a full `string_representation` per row would be ~0.5 GB of jsonl for a field
    nothing downstream of the gap CDF reads.
    """
    import chain_census as CC

    t0 = time.time()

    def _bound_leaf(state):
        return leaf(state, seat)

    values = CC.chain_values(game, board, seat, _bound_leaf)
    rep = CC.tie_report(values)

    k_remaining = meta.get("k_remaining")
    if k_remaining is None:
        from carcassonne_ai import fair_agent
        k_remaining = int(fair_agent.k_remaining(board.state))

    return {
        "ply_class": "TILE",
        "corpus": meta["corpus"],
        "game_id": meta["game_id"],
        "deck_seed": int(meta["deck_seed"]),
        "ply": int(meta["ply"]),
        "seat": int(seat),
        "k_remaining": int(k_remaining),
        "phase_bucket": CC.phase_bucket(k_remaining),
        "tercile": CC.tercile_of(int(meta["ply"]), int(meta["n_plies"])),
        "n_legal": rep["n_cand"],
        "top1": rep["top1"],
        "top2": rep["top2"],
        "gap": rep["gap"],                       # <- the eps piggyback scalar
        "tie_exact": rep["tie_exact"],
        "tie_size_exact": rep["tie_size_exact"],
        "by_eps": {k: {"tie": v["tie"], "size": v["size"]}
                   for k, v in rep["by_eps"].items()},
        "secs": round(time.time() - t0, 5),
    }


# =========================================================================== #
# corpus loading                                                              #
# =========================================================================== #
def load_games(path: Path, label: str, limit=None) -> list:
    """Corpus jsonl -> the BLIND-SAFE projection of each record.

    Only `_GAME_FIELDS_READ` crosses this boundary. `score_p0`/`score_p1`/
    `sentinel` exist in both files and are dropped here, so no downstream code
    can accidentally condition on an outcome.
    """
    out = []
    with Path(path).open() as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            out.append({
                "corpus": label,
                "game_id": rec["game_id"],
                "deck_seed": int(rec["deck_seed"]),
                "actions": [int(a) for a in rec["actions"]],
                "n_plies": int(rec.get("n_plies", len(rec["actions"]))),
            })
            if limit is not None and len(out) >= int(limit):
                break
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# =========================================================================== #
# the Pool worker — ONE replay pass per game, two counters                     #
# =========================================================================== #
def _process_game(task: dict) -> dict:
    """One banked game -> its meeple rows, its tile-gap rows, and its counters.

    The game is stepped forward ONCE (`root_replay`'s lossless
    (deck_seed, action-sequence) contract, walked manually via
    `game.get_next_state` — the same idiom as `run_census._process_e4_game`).
    Both censuses ride that single pass; nothing is replayed twice.
    """
    import random

    import numpy as np
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    from carcassonne_ai.game_wrapper import Game

    deck_seed = int(task["deck_seed"])
    actions = task["actions"]
    n_plies = int(task["n_plies"])
    corpus = task["corpus"]
    want_tile = bool(task["tile_gap"])

    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True,
                **task.get("game_kwargs", {}))
    board = game.get_init_board()

    meeple_rows: list = []
    tile_rows: list = []
    ctr = Counter()
    t0 = time.time()
    t_meeple = 0.0
    t_tile = 0.0

    for ply, played in enumerate(actions):
        st = board.state
        seat = int(st.current_player)
        meta = {"corpus": corpus, "game_id": task["game_id"], "deck_seed": deck_seed,
                "ply": ply, "n_plies": n_plies, "action_played": int(played)}
        if st.phase == GamePhase.MEEPLES:
            ctr["meeple_plies"] += 1
            n_legal = int(np.count_nonzero(game.get_valid_moves(board)))
            if n_legal >= 2:
                ctr["meeple_plies_ge2"] += 1
                t = time.time()
                row = meeple_census_ply(game, board, seat, _LEAF, meta=meta)
                t_meeple += time.time() - t
                meeple_rows.append(row)
        else:
            ctr["tile_plies"] += 1
            if want_tile:
                n_legal = int(np.count_nonzero(game.get_valid_moves(board)))
                if n_legal >= 2:
                    ctr["tile_plies_ge2"] += 1
                    t = time.time()
                    tile_rows.append(tile_gap_ply(game, board, seat, _LEAF, meta=meta))
                    t_tile += time.time() - t
        board, _ = game.get_next_state(board, int(played))

    ctr["n_plies"] = len(actions)
    ctr["games"] = 1
    return {"corpus": corpus, "game_id": task["game_id"], "deck_seed": deck_seed,
            "meeple_rows": meeple_rows, "tile_rows": tile_rows,
            "counters": dict(ctr),
            "secs": {"total": round(time.time() - t0, 3),
                     "meeple": round(t_meeple, 3), "tile": round(t_tile, 3)}}


# =========================================================================== #
# summary — MEEPLE_CENSUS.json                                                #
# =========================================================================== #
def wilson_ci(k: int, n: int, z: float = 1.959963984540054):
    """95% Wilson score interval (copied from `run_census.wilson_ci`)."""
    if n <= 0:
        return (None, None)
    k = float(k); n = float(n)
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2.0 * n)
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)
    return (max(0.0, (center - margin) / denom), min(1.0, (center + margin) / denom))


def _rate(k: int, n: int) -> dict:
    lo, hi = wilson_ci(k, n)
    return {"k": int(k), "n": int(n), "rate": (k / n) if n else None,
            "ci95_lo": lo, "ci95_hi": hi}


def _hist(values, cap: int = 12) -> dict:
    """Bucketed count histogram; everything above `cap` folds into f"{cap}+"."""
    h: Counter = Counter()
    for v in values:
        h[str(int(v)) if int(v) <= cap else f"{cap}+"] += 1
    return dict(sorted(h.items(), key=lambda kv: (len(kv[0]), kv[0])))


def _mean(vals):
    vals = list(vals)
    return (sum(vals) / len(vals)) if vals else None


def _quantiles(vals, qs=(0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99, 1.0)) -> dict:
    """Linear-interpolated quantiles (copied from `run_census._quantiles`)."""
    if not vals:
        return {str(q): None for q in qs}
    s = sorted(vals)
    n = len(s)
    out = {}
    for q in qs:
        if n == 1:
            out[str(q)] = s[0]
            continue
        pos = q * (n - 1)
        lo = int(math.floor(pos)); hi = int(math.ceil(pos))
        out[str(q)] = s[lo] + (s[hi] - s[lo]) * (pos - lo)
    return out


def gap_cdf(rows: list, eps_points=(0.0, 1e-12, 1e-9, 0.01, 0.05, 0.1, 0.15, 0.2, 0.25,
                                    0.5, 0.75, 1.0, 1.5, 2.0, 3.0)) -> dict:
    """THE EPS PIGGYBACK READ-OUT — `phi(eps)` as an arbitrary-eps CDF.

    `PLAN_eps_near_ties.md` §2.2's table, computed from the per-ply `gap` scalar
    instead of the 5-point `by_eps` grid. `new_plies` counts currently-UNTIED
    rows whose `gap <= eps` (an exact tie already fires at eps=0); `rel_growth`
    is relative to the already-fired tied mass, which is the operative currency.
    """
    n = len(rows)
    tied = sum(1 for r in rows if r["tie_exact"])
    gaps = [r["gap"] for r in rows if not r["tie_exact"] and r.get("gap") is not None]
    out = {"n_rows": n, "n_tied_exact": tied, "n_untied_with_gap": len(gaps),
           "gap_quantiles_untied": _quantiles(gaps),
           # An untied row's gap is > 0 by construction (top2 is the next
           # DISTINCT value), so this is the smallest real quantum the leaf
           # produces — `PLAN_eps_near_ties.md` §2.3's 4.44e-16 ULP question.
           "gap_min_nonzero": (min((g for g in gaps if g > 0), default=None)),
           "gap_top20": [{"gap": g, "count": c}
                         for g, c in Counter(gaps).most_common(20)],
           "phi_of_eps": {}}
    for eps in eps_points:
        new = sum(1 for g in gaps if g <= eps)
        out["phi_of_eps"][repr(eps)] = {
            "new_plies": new,
            "rel_growth_vs_fired": (new / tied) if tied else None,
            "fired_total": tied + new,
            "fired_rate": ((tied + new) / n) if n else None,
        }
    return out


def meeple_group_summary(rows: list, counters: dict, n_games: int) -> dict:
    """Every statistic PLAN §4 "Outputs" asks for, over one slice of meeple rows."""
    n = len(rows)
    tied = [r for r in rows if r["tie_exact"]]
    fired = [r for r in tied if r["repr_arms"] >= 2]
    arbitrable = [r for r in fired if r["equiv_groups_board"] >= 2]

    n_meeple_plies = int(counters.get("meeple_plies", 0))
    n_moves = int(counters.get("tile_plies", 0))     # 1 move == 1 tile ply (~72/game)

    out = {
        "n_games": n_games,
        "n_meeple_plies": n_meeple_plies,
        "n_meeple_plies_censused_ge2": n,
        "n_moves": n_moves,
        # --- phi -------------------------------------------------------------- #
        "phi_meeple_ply": _rate(len(tied), n),
        "phi_meeple_ply_all_denom": _rate(len(tied), n_meeple_plies),
        "phi_meeple_move": _rate(len(tied), n_moves),
        # --- the decision statistics ------------------------------------------ #
        "tied_plies_per_game": (len(tied) / n_games) if n_games else None,
        "fired_meeple_plies_per_game": (len(fired) / n_games) if n_games else None,
        "arbitrable_plies_per_game": (len(arbitrable) / n_games) if n_games else None,
        "arbitrable_fraction": (len(arbitrable) / len(fired)) if fired else None,
        # --- tied-set size distributions, raw and deduped --------------------- #
        "tie_size_hist_raw": _hist(r["tie_size_exact"] for r in tied),
        "tie_size_hist_dedup_repr": _hist(r["repr_arms"] for r in tied),
        "tie_size_hist_dedup_intratile": _hist(r["equiv_groups_intratile"] for r in tied),
        "tie_size_hist_dedup_board": _hist(r["equiv_groups_board"] for r in tied),
        "mean_tie_size_raw": _mean(r["tie_size_exact"] for r in tied),
        "mean_arms_repr": _mean(r["repr_arms"] for r in tied),
        "mean_groups_intratile": _mean(r["equiv_groups_intratile"] for r in tied),
        "mean_groups_board": _mean(r["equiv_groups_board"] for r in tied),
        # --- duplicate vs genuinely tied -------------------------------------- #
        # `pure_duplicate`  : >=2 arms, ONE claimed region -> arbitration decides nothing
        # `mixed`           : >=2 regions but arms > regions -> duplicates crowd the J cap
        # `pure_distinct`   : arms == regions >= 2 -> every arm is a real option
        "split": {
            "n_tied": len(tied),
            "pure_duplicate": sum(1 for r in tied if r["repr_arms"] >= 2
                                  and r["equiv_groups_board"] == 1),
            "mixed": sum(1 for r in tied if r["equiv_groups_board"] >= 2
                         and r["repr_arms"] > r["equiv_groups_board"]),
            "pure_distinct": sum(1 for r in tied if r["equiv_groups_board"] >= 2
                                 and r["repr_arms"] == r["equiv_groups_board"]),
            "single_arm": sum(1 for r in tied if r["repr_arms"] < 2),
        },
        "duplicate_fraction_of_tied": (
            (sum(1 for r in tied if r["repr_arms"] >= 2 and r["equiv_groups_board"] == 1)
             / len(tied)) if tied else None),
        # --- the rust arm-dedup inefficiency the plan flagged ------------------ #
        "redundant_arms": {
            "mean_repr_minus_board": _mean(r["repr_arms"] - r["equiv_groups_board"]
                                           for r in fired),
            "mean_repr_minus_intratile": _mean(r["repr_arms"] - r["equiv_groups_intratile"]
                                               for r in fired),
            "mean_intratile_minus_board": _mean(r["equiv_groups_intratile"]
                                                - r["equiv_groups_board"] for r in fired),
            "pct_fired_with_any_redundancy": (
                (sum(1 for r in fired if r["repr_arms"] > r["equiv_groups_board"])
                 / len(fired)) if fired else None),
            "n_fired": len(fired),
        },
        # --- the J<=4 cap ------------------------------------------------------ #
        "j_cap": {
            "cap": J_CAP,
            "truncation_rate_repr": _rate(sum(1 for r in fired if r["repr_arms"] > J_CAP),
                                          len(fired)),
            "truncation_rate_board": _rate(
                sum(1 for r in fired if r["equiv_groups_board"] > J_CAP), len(fired)),
        },
        # --- eps ladder (grid + full CDF) -------------------------------------- #
        "by_eps": ({k: _rate(sum(1 for r in rows if r["by_eps"][k]["tie"]), n)
                    for k in rows[0]["by_eps"]} if rows else {}),
        "gap_cdf": gap_cdf(rows),
        # --- where the played move sat ----------------------------------------- #
        "played_in_tieset_exact": _rate(
            sum(1 for r in rows if r["played_in_tieset_exact"]),
            sum(1 for r in rows if r["played_in_tieset_exact"] is not None)),
        "pass_in_tieset_rate": _rate(sum(1 for r in tied if r["pass_in_tieset"]), len(tied)),
    }
    return out


def build_summary(meeple_rows: list, tile_rows: list, per_corpus_counters: dict,
                  per_corpus_games: dict) -> dict:
    """`MEEPLE_CENSUS.json`. Pooled read is the adjudicated one (PLAN §5: "The
    census is adjudicated ONCE, on the pooled read, with the per-corpus split
    shown but never used to pick a branch")."""
    pooled_ctr: Counter = Counter()
    for c in per_corpus_counters.values():
        pooled_ctr.update(c)
    n_games_total = sum(per_corpus_games.values())

    groups: dict = {"POOLED": meeple_group_summary(meeple_rows, dict(pooled_ctr),
                                                   n_games_total)}
    for label in sorted(per_corpus_counters):
        rows = [r for r in meeple_rows if r["corpus"] == label]
        groups[label] = meeple_group_summary(rows, per_corpus_counters[label],
                                             per_corpus_games[label])

    # phase cut of the pooled read (PLAN §4: "all cut by phase_bucket and by corpus")
    by_phase: dict = {}
    for bucket in ("early", "mid", "late"):
        rows = [r for r in meeple_rows if r["phase_bucket"] == bucket]
        tied = [r for r in rows if r["tie_exact"]]
        fired = [r for r in tied if r["repr_arms"] >= 2]
        arb = [r for r in fired if r["equiv_groups_board"] >= 2]
        by_phase[bucket] = {
            "n": len(rows),
            "phi_meeple_ply": _rate(len(tied), len(rows)),
            "n_fired": len(fired), "n_arbitrable": len(arb),
            "arbitrable_fraction": (len(arb) / len(fired)) if fired else None,
            "fired_per_game": (len(fired) / n_games_total) if n_games_total else None,
            "arbitrable_per_game": (len(arb) / n_games_total) if n_games_total else None,
        }

    pooled = groups["POOLED"]
    arb_pg = pooled["arbitrable_plies_per_game"]
    fired_pg = pooled["fired_meeple_plies_per_game"]
    arb_frac = pooled["arbitrable_fraction"]
    branch = _branch_hint(arb_pg, fired_pg, arb_frac,
                          {k: g["phi_meeple_ply"]["rate"]
                           for k, g in groups.items() if k != "POOLED"})

    tile: dict = {}
    if tile_rows:
        tile["POOLED"] = {"n_rows": len(tile_rows), **gap_cdf(tile_rows)}
        for label in sorted({r["corpus"] for r in tile_rows}):
            rows = [r for r in tile_rows if r["corpus"] == label]
            tile[label] = {"n_rows": len(rows), **gap_cdf(rows)}

    return {
        "schema": SCHEMA + "-summary",
        "adjudication_note": (
            "PLAN_meeple_ties.md §5: adjudicate ONCE on the POOLED read; the "
            "per-corpus split is shown but never used to pick a branch."),
        "branch_bars": BRANCH_BARS,
        "branch_hint": branch,
        "groups": groups,
        "by_phase_bucket_pooled": by_phase,
        "eps_piggyback_tile": tile,
        "n_meeple_rows": len(meeple_rows),
        "n_tile_rows": len(tile_rows),
    }


def _branch_hint(arb_pg, fired_pg, arb_frac, per_corpus_phi: dict) -> dict:
    """Which PLAN §5 row the pooled numbers land in. ADVISORY — the owner
    adjudicates against the plan; this is a convenience so `CENSUS.md` does not
    have to be read against a table by hand. Ties between branches resolve to the
    more conservative (lower-spend) row, per the plan."""
    phis = [v for v in per_corpus_phi.values() if v]
    if len(phis) >= 2 and min(phis) > 0 and (max(phis) / min(phis)) > 2.0:
        return {"branch": "M-VOID", "why": "phi differs between corpora by > 2x "
                f"({per_corpus_phi}) — no branch is adjudicated (PLAN §5 M-VOID)"}
    if arb_pg is None:
        return {"branch": None, "why": "no fired plies censused"}
    if arb_pg < BRANCH_BARS["dead_below"]:
        return {"branch": "M-DEAD",
                "why": f"arbitrable_plies_per_game {arb_pg:.3f} < "
                       f"{BRANCH_BARS['dead_below']}"}
    if arb_pg < BRANCH_BARS["price_at_or_above"]:
        hint = {"branch": "M-MARGINAL",
                "why": f"{BRANCH_BARS['dead_below']} <= arbitrable_plies_per_game "
                       f"{arb_pg:.3f} < {BRANCH_BARS['price_at_or_above']}"}
    elif arb_frac is not None and arb_frac >= BRANCH_BARS["arbitrable_fraction"]:
        hint = {"branch": "M-PRICE",
                "why": f"arbitrable_plies_per_game {arb_pg:.3f} >= "
                       f"{BRANCH_BARS['price_at_or_above']} and arbitrable_fraction "
                       f"{arb_frac:.3f} >= {BRANCH_BARS['arbitrable_fraction']}"}
    else:
        hint = {"branch": "M-DUP-BOUND",
                "why": f"arbitrable_plies_per_game {arb_pg:.3f} >= "
                       f"{BRANCH_BARS['price_at_or_above']} but arbitrable_fraction "
                       f"{arb_frac} < {BRANCH_BARS['arbitrable_fraction']}"}
    # M-DUP-BOUND can also fire on fired>=8 with a low arbitrable fraction even
    # when arbitrable_per_game is itself small; the plan resolves overlaps to the
    # more conservative row, so record it as a co-firing note rather than replacing.
    if (fired_pg is not None and fired_pg >= BRANCH_BARS["price_at_or_above"]
            and arb_frac is not None and arb_frac < BRANCH_BARS["arbitrable_fraction"]
            and hint["branch"] != "M-DUP-BOUND"):
        hint["also_fires"] = (
            f"M-DUP-BOUND (fired_meeple_plies_per_game {fired_pg:.3f} >= "
            f"{BRANCH_BARS['price_at_or_above']}, arbitrable_fraction {arb_frac:.3f} < "
            f"{BRANCH_BARS['arbitrable_fraction']}) — the plan's hygiene rider")
    return hint


# =========================================================================== #
# CENSUS.md                                                                   #
# =========================================================================== #
def _fmt_rate(d) -> str:
    if not d or d.get("rate") is None:
        return "n/a"
    lo, hi = d.get("ci95_lo"), d.get("ci95_hi")
    if lo is None:
        return f"{d['rate']*100:.2f}% ({d['k']}/{d['n']})"
    return f"{d['rate']*100:.2f}% [{lo*100:.2f}, {hi*100:.2f}] ({d['k']}/{d['n']})"


def _f(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def write_census_md(summary: dict, manifest: dict, path: Path) -> None:
    g = summary["groups"]
    L = []
    L.append("# MEEPLE-ply leaf tie kill-census — CENSUS.md")
    L.append("")
    L.append(f"Generated {manifest['finished_utc']} · git `{manifest['git_rev']}` · leaf "
             f"`{manifest['leaf_hash_of_record']}` "
             f"(assert {'OK' if manifest['leaf_hash_assert_ok'] else 'FAILED'}) · "
             f"{manifest['n_games_total']} games · {summary['n_meeple_rows']} meeple rows · "
             f"{summary['n_tile_rows']} tile rows · {manifest['wall_secs_total']}s wall at "
             f"W={manifest['workers']}.")
    L.append("")
    L.append("Instrument: replay + leaf calls only. **No search, no playouts, no outcome "
             "statistic is read or emitted** (rung-(1) blind discipline; the corpora's "
             "`score_p0`/`score_p1` fields are never loaded).")
    L.append("")
    L.append(f"> **Branch hint (advisory): `{summary['branch_hint'].get('branch')}`** — "
             f"{summary['branch_hint'].get('why')}")
    if summary["branch_hint"].get("also_fires"):
        L.append(f"> Also fires: {summary['branch_hint']['also_fires']}")
    L.append("")
    L.append("Adjudicate against `PLAN_meeple_ties.md` §5 on the **POOLED** row; the "
             "per-corpus split is shown but never picks a branch.")
    L.append("")

    L.append("## 1. phi — the meeple exact-tie rate")
    L.append("")
    L.append("| group | games | meeple plies | censused (n_legal>=2) | phi_meeple_ply | "
             "phi_meeple_move | tied/game |")
    L.append("|---|---:|---:|---:|---|---|---:|")
    for k, s in g.items():
        L.append(f"| {k} | {s['n_games']} | {s['n_meeple_plies']} | "
                 f"{s['n_meeple_plies_censused_ge2']} | {_fmt_rate(s['phi_meeple_ply'])} | "
                 f"{_fmt_rate(s['phi_meeple_move'])} | {_f(s['tied_plies_per_game'], 2)} |")
    L.append("")
    L.append("Prior to beat (PLAN §2): JCZ mining meta read meeple `leaf_tie` at **16.5%** "
             "⇒ 4.82 tied meeple plies/game, vs the tile rung's **22.96** fired plies/game.")
    L.append("")

    L.append("## 2. ⭐ THE DECISION STATISTICS")
    L.append("")
    L.append("| group | fired/game (repr_arms>=2) | arbitrable/game (board_groups>=2) | "
             "**arbitrable_fraction** |")
    L.append("|---|---:|---:|---:|")
    for k, s in g.items():
        L.append(f"| {k} | {_f(s['fired_meeple_plies_per_game'])} | "
                 f"{_f(s['arbitrable_plies_per_game'])} | {_f(s['arbitrable_fraction'])} |")
    L.append("")
    L.append(f"Bars: `M-DEAD` if arbitrable/game < {BRANCH_BARS['dead_below']}; "
             f"`M-PRICE` needs >= {BRANCH_BARS['price_at_or_above']} **and** "
             f"arbitrable_fraction >= {BRANCH_BARS['arbitrable_fraction']}.")
    L.append("")

    L.append("## 3. Tied-set composition — raw vs the three groupings")
    L.append("")
    L.append("| group | mean raw tie size | mean repr arms | mean intra-tile groups | "
             "mean BOARD regions |")
    L.append("|---|---:|---:|---:|---:|")
    for k, s in g.items():
        L.append(f"| {k} | {_f(s['mean_tie_size_raw'], 3)} | {_f(s['mean_arms_repr'], 3)} | "
                 f"{_f(s['mean_groups_intratile'], 3)} | {_f(s['mean_groups_board'], 3)} |")
    L.append("")
    L.append("Size histograms (POOLED, exact-tied plies only):")
    L.append("")
    for name, key in (("raw (`tie_size_exact`)", "tie_size_hist_raw"),
                      ("deduped by afterstate repr (what rust builds)",
                       "tie_size_hist_dedup_repr"),
                      ("deduped by intra-tile feature key (July census)",
                       "tie_size_hist_dedup_intratile"),
                      ("deduped by BOARD claimed-region (definition of record)",
                       "tie_size_hist_dedup_board")):
        L.append(f"- **{name}**: `{g['POOLED'][key]}`")
    L.append("")

    L.append("## 4. Duplicate vs genuinely tied")
    L.append("")
    L.append("| group | tied | pure DUPLICATE (1 region) | mixed | pure DISTINCT | "
             "single-arm | duplicate fraction |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for k, s in g.items():
        sp = s["split"]
        L.append(f"| {k} | {sp['n_tied']} | {sp['pure_duplicate']} | {sp['mixed']} | "
                 f"{sp['pure_distinct']} | {sp['single_arm']} | "
                 f"{_f(s['duplicate_fraction_of_tied'])} |")
    L.append("")
    L.append("## 5. The rust arm-dedup inefficiency, and the `J<=4` cap")
    L.append("")
    L.append("| group | mean (repr − board) | mean (repr − intratile) | "
             "mean (intratile − board) | fired plies with redundancy | repr arms > 4 |")
    L.append("|---|---:|---:|---:|---:|---|")
    for k, s in g.items():
        ra = s["redundant_arms"]
        L.append(f"| {k} | {_f(ra['mean_repr_minus_board'])} | "
                 f"{_f(ra['mean_repr_minus_intratile'])} | "
                 f"{_f(ra['mean_intratile_minus_board'])} | "
                 f"{_f(ra['pct_fired_with_any_redundancy'])} | "
                 f"{_fmt_rate(s['j_cap']['truncation_rate_repr'])} |")
    L.append("")
    L.append("A positive `repr − board` is the plan's §1 claim made quantitative: that many "
             "arms per fired ply are duplicates that consume `J<=4` slots and return "
             "identical world-means.")
    L.append("")

    L.append("## 6. Phase cut (POOLED)")
    L.append("")
    L.append("| phase | n | phi_meeple_ply | fired/game | arbitrable/game | arb. fraction |")
    L.append("|---|---:|---|---:|---:|---:|")
    for b, d in summary["by_phase_bucket_pooled"].items():
        L.append(f"| {b} | {d['n']} | {_fmt_rate(d['phi_meeple_ply'])} | "
                 f"{_f(d['fired_per_game'])} | {_f(d['arbitrable_per_game'])} | "
                 f"{_f(d['arbitrable_fraction'])} |")
    L.append("")

    L.append("## 7. THE EPS PIGGYBACK — `phi(eps)` as a full CDF")
    L.append("")
    L.append("Per `PLAN_eps_near_ties.md` §8: the per-ply scalar `gap = top1 − top2` "
             "(top2 = next DISTINCT leaf value) upgrades rung (4)'s 5-point grid into an "
             "arbitrary-eps CDF, for one extra field and zero extra leaf calls.")
    L.append("")
    for cls, block in (("MEEPLE", {k: v["gap_cdf"] for k, v in g.items()}),
                       ("TILE", summary["eps_piggyback_tile"])):
        if not block:
            continue
        L.append(f"### {cls}")
        L.append("")
        pooled = block.get("POOLED")
        if not pooled:
            L.append("_(not censused)_")
            L.append("")
            continue
        L.append(f"n_rows {pooled['n_rows']} · "
                 f"exact-tied {pooled['n_tied_exact']} · untied-with-gap "
                 f"{pooled['n_untied_with_gap']} · smallest nonzero gap "
                 f"{pooled['gap_min_nonzero']}")
        L.append("")
        L.append("| eps | new plies | rel growth vs fired | fired total | fired rate |")
        L.append("|---:|---:|---:|---:|---:|")
        for eps, d in pooled["phi_of_eps"].items():
            L.append(f"| {eps} | {d['new_plies']} | {_f(d['rel_growth_vs_fired'], 4)} | "
                     f"{d['fired_total']} | {_f(d['fired_rate'], 4)} |")
        L.append("")
        L.append(f"Top gap values: `{pooled['gap_top20'][:10]}`")
        L.append("")

    L.append("## 8. What this census does NOT show")
    L.append("")
    L.append("It counts. It never scores. A meeple leaf tie whose options claim DIFFERENT "
             "board regions is *arbitrable* — the arbiter could in principle separate it — "
             "but this instrument says nothing about whether a playout actually would, and "
             "deliberately reads no outcome. Pricing that (`M-PRICE`) is `PLAN_meeple_ties.md` "
             "§6, on a FRESH corpus with a FRESH read-rule. C5 (duplicate CRN "
             "bit-invariance) is not run here: it needs playouts, which this instrument is "
             "forbidden to take.")
    L.append("")
    path.write_text("\n".join(L))


# =========================================================================== #
# driver                                                                      #
# =========================================================================== #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--games", default=None,
                    help="comma-separated corpus paths, optionally 'label=path'. "
                         "Default: the two PLAN §4 corpora (449 + 850 games).")
    ap.add_argument("--out-dir", default=str(OUT_DIR_DEFAULT))
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--profile", default="walled", help="rules profile (both corpora are walled)")
    ap.add_argument("--limit-games", type=int, default=None,
                    help="smoke knob — first N games PER CORPUS")
    ap.add_argument("--no-tile-gap", dest="tile_gap", action="store_false", default=True,
                    help="skip the TILE-class gap piggyback (PLAN_eps_near_ties §8)")
    ap.add_argument("--tile-gap-corpora", default="all",
                    help="comma-separated corpus labels the tile leg may read, or 'all'. "
                         "Use 'champ449' to leave the tiearb2 corpus's BURNED tile "
                         "positions untouched.")
    ap.add_argument("--abort-wall-mins", type=float, default=30.0,
                    help="PLAN §4 abort bar: report and stop if wall exceeds this. "
                         "0 disables.")
    ap.add_argument("--contention-note", default=None,
                    help="free-text timing caveat recorded verbatim in manifest.json "
                         "(counts are deterministic; only wall-clock would be affected)")
    return ap


def resolve_corpora(spec) -> list:
    if not spec:
        return [(label, Path(p)) for label, p in DEFAULT_CORPORA]
    out = []
    for item in str(spec).split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            label, p = item.split("=", 1)
        else:
            p = item
            label = Path(p).stem
        out.append((label.strip(), Path(p.strip())))
    return out


def main(argv=None) -> int:
    global _LEAF

    ap = build_arg_parser()
    a = ap.parse_args(argv)
    t_start = time.time()

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    corpora = resolve_corpora(a.games)
    missing = [str(p) for _l, p in corpora if not p.exists()]
    if missing:
        raise SystemExit(f"[meeple_tie_census] corpus file(s) not found: {missing}")

    tile_labels = ({l for l, _p in corpora} if a.tile_gap_corpora.strip() == "all"
                   else {s.strip() for s in a.tile_gap_corpora.split(",") if s.strip()})

    # --- env + leaf (BEFORE any carcassonne_ai import, before the Pool fork) --- #
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")

    import chain_census as CC

    # `base_deck` latches CARCASSONNE_FIX_R9 into a Rust OnceLock AT IMPORT, so the
    # rules env must be exported before anything drags `carcassonne_ai` in. The
    # r9_env_ok assert below is the real guard; this one names the cause.
    if "carcassonne_ai" in sys.modules:
        raise RuntimeError(
            "carcassonne_ai was imported before prepare_env() — the CARCASSONNE_FIX_R9 "
            "latch is already set and this leg's rules profile cannot be trusted.")
    env_resolved = CC.prepare_env(a.profile)
    from carcassonne_ai import rules_profile
    prof = rules_profile.activate(a.profile)
    prof_manifest = prof.as_manifest()
    if not prof_manifest["r9_env_ok"]:
        raise RuntimeError(
            f"R9 latch mismatch for profile {a.profile}: expected "
            f"{prof.r9_env_expected}, observed {prof_manifest['r9_env_observed']}. "
            "Export CARCASSONNE_FIX_R9 correctly before launching.")
    leaf, cfg, leaf_hashes, bag_close = CC.build_leaf()
    _LEAF = leaf                                 # set BEFORE the fork
    game_kwargs = prof.game_kwargs()

    # --- tasks ----------------------------------------------------------------- #
    tasks = []
    per_corpus_games: dict = {}
    corpus_meta = []
    for label, path in corpora:
        games = load_games(path, label, a.limit_games)
        per_corpus_games[label] = len(games)
        corpus_meta.append({"label": label, "path": str(path), "n_games": len(games),
                            "sha256": sha256_of(path),
                            "tile_gap_read": label in tile_labels})
        for grec in games:
            tasks.append({**grec, "game_kwargs": game_kwargs,
                          "tile_gap": bool(a.tile_gap and label in tile_labels)})
    print(f"[meeple_tie_census] {len(tasks)} games from {len(corpora)} corpora "
          f"{per_corpus_games}; W={a.workers}; tile_gap={a.tile_gap} on {sorted(tile_labels)}",
          flush=True)

    # --- fan out ---------------------------------------------------------------- #
    ctx = mp.get_context("fork")
    meeple_path = out_dir / "meeple_rows.jsonl"
    tile_path = out_dir / "tile_gap_rows.jsonl"
    meeple_rows: list = []
    tile_rows: list = []
    per_corpus_counters: dict = {l: Counter() for l, _p in corpora}
    per_game_secs: list = []
    aborted = None

    with meeple_path.open("w") as mfh, tile_path.open("w") as tfh:
        with ctx.Pool(max(1, min(int(a.workers), len(tasks)))) as pool:
            done = 0
            for res in pool.imap_unordered(_process_game, tasks, chunksize=1):
                done += 1
                label = res["corpus"]
                per_corpus_counters[label].update(res["counters"])
                per_game_secs.append(res["secs"])
                for row in res["meeple_rows"]:
                    mfh.write(json.dumps(row) + "\n")
                    meeple_rows.append(row)
                for row in res["tile_rows"]:
                    tfh.write(json.dumps(row) + "\n")
                    tile_rows.append(row)
                if done % 100 == 0:
                    print(f"[meeple_tie_census] {done}/{len(tasks)} games "
                          f"({time.time()-t_start:.0f}s)", flush=True)
                if a.abort_wall_mins and (time.time() - t_start) > a.abort_wall_mins * 60:
                    aborted = (f"ABORT BAR: exceeded {a.abort_wall_mins} min wall after "
                               f"{done}/{len(tasks)} games — PLAN §4 says the instrument is "
                               "wrong, not the lever. Partial rows are on disk.")
                    print(f"[meeple_tie_census] {aborted}", flush=True)
                    pool.terminate()
                    break

    per_corpus_counters = {l: dict(c) for l, c in per_corpus_counters.items()}
    summary = build_summary(meeple_rows, tile_rows, per_corpus_counters, per_corpus_games)

    def _git_rev():
        try:
            return subprocess.check_output(
                ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True).strip()
        except Exception as exc:                                    # noqa: BLE001
            return f"UNKNOWN ({exc})"

    total_wall = round(time.time() - t_start, 1)
    worker_s_meeple = sum(d["meeple"] for d in per_game_secs)
    worker_s_tile = sum(d["tile"] for d in per_game_secs)
    worker_s_total = sum(d["total"] for d in per_game_secs)

    manifest = {
        "schema": SCHEMA + "-manifest",
        "goal": ("MEEPLE-ply leaf exact-tie census over banked champion games: replay + "
                 "leaf calls only, no search, no playouts, NO outcome statistic. Rung (1) "
                 "of the tie-arbiter widening campaign."),
        "spec": ["measurement/tiearb_widening_20260817/PLAN_meeple_ties.md",
                 "measurement/tiearb_widening_20260817/CAMPAIGN.md",
                 "measurement/tiearb_widening_20260817/PLAN_eps_near_ties.md"],
        "blind_discipline": {
            "game_fields_read": list(_GAME_FIELDS_READ),
            "note": ("score_p0/score_p1/sentinel are NOT read. C5 (duplicate CRN "
                     "bit-invariance) is deliberately not implemented here — it needs "
                     "playouts."),
        },
        "argv": list(sys.argv),
        "resolved_args": vars(a),
        "git_rev": _git_rev(),
        "python": sys.version,
        "hostname": os.uname().nodename,
        "rules_profile": a.profile,
        "rules_profile_manifest": prof_manifest,
        "game_kwargs": game_kwargs,
        "env_resolved": env_resolved,
        "leaf_hashes": leaf_hashes,
        "leaf_hash_of_record": CC.LEAF_HASH_OF_RECORD,
        "leaf_hash_assert_ok": leaf_hashes.get("harness_leaf_hash") == CC.LEAF_HASH_OF_RECORD,
        "leaf_bag_close": bool(bag_close),
        "tie_eps_grid": list(CC.TIE_EPS_GRID),
        "corpora": corpus_meta,
        "n_games_total": sum(per_corpus_games.values()),
        "per_corpus_games": per_corpus_games,
        "per_corpus_counters": per_corpus_counters,
        "workers": int(a.workers),
        "tile_gap_enabled": bool(a.tile_gap),
        "tile_gap_corpora": sorted(tile_labels),
        "n_meeple_rows": len(meeple_rows),
        "n_tile_rows": len(tile_rows),
        "wall_secs_total": total_wall,
        "worker_secs": {"total": round(worker_s_total, 1),
                        "meeple_census": round(worker_s_meeple, 1),
                        "tile_gap_census": round(worker_s_tile, 1),
                        "replay_residual": round(worker_s_total - worker_s_meeple
                                                 - worker_s_tile, 1)},
        "worker_hours_total": round(worker_s_total / 3600.0, 4),
        "abort_wall_mins": a.abort_wall_mins,
        "aborted": aborted,
        "contention_note": a.contention_note,
        "outputs": {"meeple_rows": str(meeple_path), "tile_gap_rows": str(tile_path),
                    "summary": str(out_dir / "MEEPLE_CENSUS.json"),
                    "census_md": str(out_dir / "CENSUS.md")},
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / "MEEPLE_CENSUS.json").write_text(json.dumps(summary, indent=2))
    write_census_md(summary, manifest, out_dir / "CENSUS.md")

    pooled = summary["groups"]["POOLED"]
    print(f"\n[meeple_tie_census] DONE {total_wall}s wall / "
          f"{manifest['worker_hours_total']} worker-h · "
          f"{len(meeple_rows)} meeple rows, {len(tile_rows)} tile rows", flush=True)
    print(f"[meeple_tie_census] phi_meeple_ply="
          f"{_f(pooled['phi_meeple_ply']['rate'], 4)} · fired/game="
          f"{_f(pooled['fired_meeple_plies_per_game'])} · arbitrable/game="
          f"{_f(pooled['arbitrable_plies_per_game'])} · arbitrable_fraction="
          f"{_f(pooled['arbitrable_fraction'])} · branch hint "
          f"{summary['branch_hint'].get('branch')}", flush=True)
    print(f"[meeple_tie_census] -> {out_dir}", flush=True)
    return 1 if aborted else 0


if __name__ == "__main__":
    raise SystemExit(main())
