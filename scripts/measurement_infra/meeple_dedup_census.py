"""Meeple-slot duplication census — how much of the meeple action space is redundant.

MEASUREMENT INFRASTRUCTURE (not a strength lever). Decides whether the parked
"action-space dedup" search experiment (PROGRAM_ROADMAP parking-lot item 5,
docs/LEVER_INDEX.md 'action-space dedup') is worth funding: if a large share of
meeple-phase decisions offer two or more *game-equivalent* actions, then MCTS is
splitting visits (and the policy head is splitting probability mass) across moves
that lead to literally the same successor state.

## What counts as a duplicate

Two legal meeple actions are duplicates when they claim the SAME on-tile connected
feature -- e.g. a city with two openings (`city=[[TOP, RIGHT]]`) offers a knight
slot on each opening, but either one claims the one city. The grouping is
`carcassonne_ai.meeple_equiv.feature_groups` + `android_bridge._renumber_groups`,
IMPORTED not reimplemented: they are the tested functions the Android UI already uses
to collapse duplicate dots (and, since 2026-07-27, that the flag-gated MEEPLE-DEDUP
search uses to collapse duplicate subtrees); a second copy would drift.

⚠️ **This is a LOWER BOUND on true duplication.** `feature_groups` is a pure read of
ONE tile, so it merges only openings that are already connected *on the placed tile*.
Two sides that are separate on the tile but joined into one feature *through the rest
of the board* (the common case for farms: two distinct on-tile fields that the
neighbouring tiles have already merged) are counted here as distinct. A board-level
union-find census would report >= these numbers, never fewer.

## Data source

Champion-policy games in root_replay `GameRecord` jsonl form -- `{game_id, deck_seed,
actions, ...}`. Default is `measurement/champ_action_logs/champ_games.jsonl` (449
games, PRODUCTION.yaml champion under fair PIMC, k_dets=4 x 688 sims; see that dir's
CORPUS_MANIFEST.json). Replay is lossless for any policy -- the engine draws from the
global RNG only in the deck shuffle -- so stepping `(deck_seed, actions)` reproduces
the exact champion-distribution position at every ply (see root_replay's docstring).

Because the positions come from champion self-play, the phase/frequency weighting is
the *champion's own* distribution of meeple decisions, which is the distribution a
dedup would actually act on. It is NOT a uniform-random-play census.

## Usage

    python3 scripts/measurement_infra/meeple_dedup_census.py \
        --games measurement/champ_action_logs/champ_games.jsonl \
        --limit 449 --workers 8 --out /tmp/meeple_dedup_census.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO), str(_REPO / "android" / "app" / "src" / "main" / "python"),
           str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The grouping logic of record. Imported, never reimplemented (drift risk). It lives in
# the package (2026-07-27) because the MEEPLE-DEDUP search reads the same definition;
# `_renumber_groups` / `meeple_slots_for` stay in the bridge — they are UI slot shapes.
from android_bridge import (  # noqa: E402
    _renumber_groups,
    meeple_slots_for,
)
from carcassonne_ai.action_space import meeple_pass_index, tile_action_count  # noqa: E402
from carcassonne_ai.meeple_equiv import feature_groups  # noqa: E402
from root_replay import load_games  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

DEFAULT_GAMES = "measurement/champ_action_logs/champ_games.jsonl"

# Phase bucketing by tiles placed. The 2-player Base deck places 71 tiles after the
# start tile, so equal thirds are [1,24) / [24,48) / [48,..]. Bucketed by the count
# INCLUDING the tile just placed (a meeple decision always follows a placement).
PHASE_BOUNDS = (24, 48)
PHASE_NAMES = ("early", "mid", "late")


# --------------------------------------------------------------------------- #
# Core counting logic (pure; unit-tested against synthetic tiles)
# --------------------------------------------------------------------------- #

def dense_groups(tile, sides) -> list[int]:
    """Dense feature-group id for each legal meeple `side` (a `Side.value` str) on `tile`.

    Same two-step the UI does: `feature_groups` for the raw per-tile ids, then
    `_renumber_groups` to densify and to give every side the tile model does not
    describe a PRIVATE group (never silently merged). Equal ids == interchangeable.
    """
    raw = feature_groups(tile)
    slots = [{"action_id": i, "side": s, "feature_group": int(raw.get(s, -1))}
             for i, s in enumerate(sides)]
    return [s["feature_group"] for s in _renumber_groups(slots)]


def group_size_histogram(groups) -> Counter:
    """Counter{group_size: n_groups} for a decision's per-action group ids."""
    return Counter(Counter(groups).values())


def decision_stats(groups, chosen_group=None) -> dict:
    """Duplication stats for ONE meeple decision.

    `groups` is the dense group id of every legal NON-PASS meeple action.
    `chosen_group` is the group of the action actually taken, or None if the mover
    passed (or the choice is unknown).
    """
    hist = group_size_histogram(groups)
    n_actions = len(groups)
    n_distinct = len(set(groups))
    sizes = Counter(groups)
    return {
        "n_actions": n_actions,
        "n_distinct_features": n_distinct,
        "n_redundant": n_actions - n_distinct,
        "has_duplicate": any(k >= 2 for k in hist),
        "max_group_size": max(hist) if hist else 0,
        "size_hist": {int(k): int(v) for k, v in hist.items()},
        "chose_duplicate": (chosen_group is not None
                            and sizes.get(chosen_group, 0) >= 2),
        "chose_group_size": (int(sizes.get(chosen_group, 0))
                             if chosen_group is not None else 0),
    }


def phase_bucket(tiles_placed: int) -> str:
    lo, hi = PHASE_BOUNDS
    if tiles_placed < lo:
        return PHASE_NAMES[0]
    if tiles_placed < hi:
        return PHASE_NAMES[1]
    return PHASE_NAMES[2]


# --------------------------------------------------------------------------- #
# Per-game replay
# --------------------------------------------------------------------------- #

def census_game(rec) -> dict:
    """Replay one recorded game, censusing every meeple-phase decision it contained.

    Returns a flat accumulator dict (see `_new_acc`) so results merge trivially
    across worker processes.
    """
    import random

    from carcassonne_ai.game_wrapper import Game

    random.seed(int(rec.deck_seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=False)
    board = game.get_init_board()

    acc = _new_acc()
    acc["games"] = 1
    size = board.offset.size
    n_tile = tile_action_count(size)
    pass_idx = meeple_pass_index(size)
    tiles_placed = 0

    for a in rec.actions:
        a = int(a)
        state = board.state
        if state.phase == GamePhase.MEEPLES:
            slots = meeple_slots_for(game, board)
            groups = [int(s["feature_group"]) for s in slots]
            by_action = {int(s["action_id"]): int(s["feature_group"]) for s in slots}
            chosen_group = by_action.get(a) if a != pass_idx else None
            st = decision_stats(groups, chosen_group)
            pass_legal = bool(game.get_valid_moves(board)[pass_idx])
            _record(acc, st, phase_bucket(tiles_placed),
                    passed=(a == pass_idx), pass_legal=pass_legal)
        elif a < n_tile:
            tiles_placed += 1
        board, _ = game.get_next_state(board, a)

    acc["plies"] = len(rec.actions)
    return acc


def _new_acc() -> dict:
    acc = {
        "games": 0, "plies": 0,
        "decisions": 0, "decisions_with_dup": 0,
        "decisions_actionable": 0, "decisions_actionable_with_dup": 0,
        "decisions_no_options": 0,
        "actions_nonpass": 0, "distinct_features": 0,
        "pass_legal": 0,
        "placed": 0, "placed_chose_dup": 0,
        "max_group_hist": {}, "group_size_hist": {}, "n_actions_hist": {},
    }
    for name in PHASE_NAMES:
        acc[f"phase_{name}"] = {"decisions": 0, "decisions_with_dup": 0,
                                "actions_nonpass": 0, "distinct_features": 0,
                                "placed": 0, "placed_chose_dup": 0}
    return acc


def _bump(d: dict, key, n: int = 1) -> None:
    k = str(key)
    d[k] = d.get(k, 0) + n


def _record(acc: dict, st: dict, bucket: str, passed: bool, pass_legal: bool) -> None:
    acc["decisions"] += 1
    acc["decisions_with_dup"] += int(st["has_duplicate"])
    # A dedup can only ever matter where the mover had >=2 placement options.
    if st["n_actions"] >= 2:
        acc["decisions_actionable"] += 1
        acc["decisions_actionable_with_dup"] += int(st["has_duplicate"])
    if st["n_actions"] == 0:
        acc["decisions_no_options"] += 1
    acc["actions_nonpass"] += st["n_actions"]
    acc["distinct_features"] += st["n_distinct_features"]
    acc["pass_legal"] += int(pass_legal)
    _bump(acc["max_group_hist"], st["max_group_size"])
    _bump(acc["n_actions_hist"], st["n_actions"])
    for sz, n in st["size_hist"].items():
        _bump(acc["group_size_hist"], sz, n)
    if not passed:
        acc["placed"] += 1
        acc["placed_chose_dup"] += int(st["chose_duplicate"])
    p = acc[f"phase_{bucket}"]
    p["decisions"] += 1
    p["decisions_with_dup"] += int(st["has_duplicate"])
    p["actions_nonpass"] += st["n_actions"]
    p["distinct_features"] += st["n_distinct_features"]
    if not passed:
        p["placed"] += 1
        p["placed_chose_dup"] += int(st["chose_duplicate"])


def merge(a: dict, b: dict) -> dict:
    for k, v in b.items():
        if isinstance(v, dict):
            if k.startswith("phase_"):
                for kk, vv in v.items():
                    a[k][kk] += vv
            else:
                for kk, vv in v.items():
                    _bump(a[k], kk, vv)
        else:
            a[k] += v
    return a


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

def _pct(num, den):
    return round(100.0 * num / den, 2) if den else 0.0


def summarize(acc: dict) -> dict:
    dec = acc["decisions"]
    npa = acc["actions_nonpass"]
    distinct = acc["distinct_features"]
    redundant = npa - distinct
    # With the pass action in the denominator: pass is legal at `pass_legal`
    # decisions and is never redundant.
    total_with_pass = npa + acc["pass_legal"]
    out = {
        "games": acc["games"],
        "plies": acc["plies"],
        "meeple_decisions": dec,
        "meeple_decisions_no_options": acc["decisions_no_options"],
        "meeple_decisions_actionable": acc["decisions_actionable"],
        "pct_decisions_with_duplicate": _pct(acc["decisions_with_dup"], dec),
        "pct_actionable_decisions_with_duplicate":
            _pct(acc["decisions_actionable_with_dup"], acc["decisions_actionable"]),
        "nonpass_actions_total": npa,
        "distinct_features_total": distinct,
        "redundant_actions_total": redundant,
        "pct_actions_redundant_nonpass": _pct(redundant, npa),
        "pct_actions_redundant_incl_pass": _pct(redundant, total_with_pass),
        "mean_nonpass_actions_per_decision": round(npa / dec, 3) if dec else 0.0,
        "mean_distinct_features_per_decision": round(distinct / dec, 3) if dec else 0.0,
        "max_group_size_distribution": {
            k: {"decisions": v, "pct": _pct(v, dec)}
            for k, v in sorted(acc["max_group_hist"].items(), key=lambda x: int(x[0]))
        },
        "group_size_distribution": {
            k: {"groups": v} for k, v in
            sorted(acc["group_size_hist"].items(), key=lambda x: int(x[0]))
        },
        "meeple_placed_decisions": acc["placed"],
        "pct_placed_choice_was_in_duplicate_group":
            _pct(acc["placed_chose_dup"], acc["placed"]),
        "by_phase": {},
    }
    for name in PHASE_NAMES:
        p = acc[f"phase_{name}"]
        red = p["actions_nonpass"] - p["distinct_features"]
        out["by_phase"][name] = {
            "decisions": p["decisions"],
            "pct_decisions_with_duplicate": _pct(p["decisions_with_dup"], p["decisions"]),
            "nonpass_actions": p["actions_nonpass"],
            "pct_actions_redundant_nonpass": _pct(red, p["actions_nonpass"]),
            "mean_nonpass_actions_per_decision":
                round(p["actions_nonpass"] / p["decisions"], 3) if p["decisions"] else 0.0,
            "pct_placed_choice_was_in_duplicate_group":
                _pct(p["placed_chose_dup"], p["placed"]),
        }
    return out


def human_summary(s: dict, source: str) -> str:
    L = []
    A = L.append
    A("=" * 72)
    A("MEEPLE-SLOT DUPLICATION CENSUS")
    A("=" * 72)
    A(f"source            : {source}")
    A(f"games / plies     : {s['games']} / {s['plies']}")
    A(f"meeple decisions  : {s['meeple_decisions']}"
      f"   ({s['meeple_decisions_no_options']} had NO non-pass option;"
      f" {s['meeple_decisions_actionable']} had >=2)")
    A("")
    A("-- duplication --")
    A(f"decisions with >=1 duplicate group : {s['pct_decisions_with_duplicate']}%"
      f"  (of the >=2-option ones: {s['pct_actionable_decisions_with_duplicate']}%)")
    A(f"redundant / non-pass actions       : {s['redundant_actions_total']}"
      f" / {s['nonpass_actions_total']} = {s['pct_actions_redundant_nonpass']}%")
    A(f"redundant / all actions (+pass)    : {s['pct_actions_redundant_incl_pass']}%")
    A(f"mean non-pass actions per decision : {s['mean_nonpass_actions_per_decision']}"
      f"  ->  {s['mean_distinct_features_per_decision']} distinct features")
    A("")
    A("-- largest duplicate group per decision --")
    for k, v in s["max_group_size_distribution"].items():
        label = "no duplicates (all singletons)" if int(k) <= 1 else f"{k}-way duplicate"
        A(f"  max group = {k:>2}  {label:<32} {v['decisions']:>7}  {v['pct']:>6}%")
    A("")
    A("-- duplicate groups by size (over all decisions) --")
    for k, v in s["group_size_distribution"].items():
        A(f"  size {k:>2}: {v['groups']:>8} groups")
    A("")
    A("-- by game phase (tiles placed) --")
    A(f"  {'phase':<8}{'decisions':>10}{'%w/dup':>9}{'%redundant':>12}{'mean acts':>11}"
      f"{'%chosen dup':>13}")
    for name, p in s["by_phase"].items():
        A(f"  {name:<8}{p['decisions']:>10}{p['pct_decisions_with_duplicate']:>9}"
          f"{p['pct_actions_redundant_nonpass']:>12}"
          f"{p['mean_nonpass_actions_per_decision']:>11}"
          f"{p['pct_placed_choice_was_in_duplicate_group']:>13}")
    A("")
    A("-- champion's actual choice --")
    A(f"decisions where a meeple was placed : {s['meeple_placed_decisions']}")
    A(f"  ... chosen action was in a duplicate group : "
      f"{s['pct_placed_choice_was_in_duplicate_group']}%")
    A("")
    A("NOTE: intra-tile grouping only -> a LOWER BOUND on true duplication "
      "(board-level\n      feature merges, esp. farms, are not counted).")
    A("=" * 72)
    return "\n".join(L)


# --------------------------------------------------------------------------- #

def _worker(rec):
    return census_game(rec)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--games", default=DEFAULT_GAMES,
                    help=f"root_replay GameRecord jsonl (default: {DEFAULT_GAMES})")
    ap.add_argument("--limit", type=int, default=0, help="max games (0 = all)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="", help="write the JSON report here")
    args = ap.parse_args(argv)

    path = Path(args.games)
    if not path.is_absolute():
        path = _REPO / path
    games = load_games(path)
    if args.limit:
        games = games[:args.limit]
    if not games:
        print(f"no games in {path}", file=sys.stderr)
        return 1

    acc = _new_acc()
    if args.workers > 1:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(args.workers) as pool:
            for i, r in enumerate(pool.imap_unordered(_worker, games, chunksize=2), 1):
                merge(acc, r)
                if i % 50 == 0:
                    print(f"  [{i}/{len(games)}] games", file=sys.stderr, flush=True)
    else:
        for i, g in enumerate(games, 1):
            merge(acc, census_game(g))
            if i % 25 == 0:
                print(f"  [{i}/{len(games)}] games", file=sys.stderr, flush=True)

    s = summarize(acc)
    report = {
        "kind": "meeple_slot_duplication_census",
        "grouping": "android_bridge.feature_groups + _renumber_groups (imported)",
        "grouping_scope": "INTRA-TILE ONLY -- lower bound on true duplication",
        "source_games": str(path),
        "n_games_requested": args.limit or len(games),
        "phase_bounds_tiles_placed": list(PHASE_BOUNDS),
        "summary": s,
        "raw_accumulator": acc,
    }
    print(human_summary(s, str(path)))
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(report, indent=2, sort_keys=False))
        print(f"\nJSON -> {op}")
    return 0


if __name__ == "__main__":
    os.nice(19)
    raise SystemExit(main())
