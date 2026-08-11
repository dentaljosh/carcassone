"""Pure-replay descriptive statistics for a single Carcassonne game.

PHASE-5 ANALYZER, SLICE 1. This module owns the *definitions*; `corpus_stats.py`
aggregates them over a corpus and `e4_diff.py` diffs one human game against that
aggregate. Nothing here searches — every number is a deterministic function of
`(deck_seed, actions)` via the `root_replay` contract, so a game's stats are
reproducible bit-for-bit from its two-field archive record.

## What is measured (Joshua's seed list, BACKLOG 2026-07-30)

* **phase-dependent play** — move-type mix segmented two ways (turn terciles AND
  absolute `k_remaining` bands), reported side by side because they disagree
  whenever a game ends early.
* **completed-feature sizes** — every city / road / cloister that closes *during
  play*, with its tile count, points and whether anyone was on it.
* **meeple economy** — meeples-in-hand per turn, per seat.
* **stranding** — meeples that go down and never come back (see below).
* **farm timing** — the turn of every farmer placement, and how long it sits.
* **score flow** — during-play vs unfinished-feature vs farm points, per seat.
* **openness** — how many features are still open at each turn.

## Definitions that needed a judgment call

`RETURNED` — a meeple is *returned* when it leaves `state.placed_meeples` during
play, which the engine does only via `remove_meeples_and_collect_points`, i.e.
exactly when its feature completes and scores. So "returned" == "scored during
play" and the two never disagree.

`STRANDED` — placed and still on the board in the meeple-intact terminal state.
Reported **two ways**, because the honest answer differs by meeple kind:

* `stranded_nonfarmer` — the interesting one. A normal meeple on a city / road /
  cloister that never closed. This is the "wasted capital" Joshua means, and it
  is what the leaf's meeple curve prices.
* `stranded_all` — includes farmers. **Farmers are stranded by design** (a farmer
  is never recoverable in Base+Farmers; that is the cost of the claim), so this
  figure is a board-occupancy measure, not a mistake measure. Never quote it as
  an error rate.

The **during-play cost of stranding** is reported as `meeple_turns_locked` — the
sum over stranded non-farmer meeples of `(n_turns - placement_turn)`, i.e. how
many turns of meeple capital were tied up in features that never paid during
play. Converting that to points requires a rate, which is a corpus-level
quantity, so the conversion lives in `corpus_stats.py` (`points_per_meeple_turn`)
and never in a per-game record.

`TERMINAL SCORE SPLIT` — the engine runs `count_final_scores` *inside* the
terminating move and that pass consumes the placed meeples, so a plain replay
cannot see who owned what at the end. This module replays with
`PointsCollector.count_final_scores` stubbed out for the duration, which leaves
the meeple-intact terminal state that `aux_targets.extract_terminal_ownership`
documents as its input; the split is then reconciled against the true final
scores from an unstubbed replay and the game is marked `split_ok=False` if it
does not add up. Same reconstruction the Android bridge's `_final_breakdown`
uses. `engine/` is not touched.

`k_remaining` — `len(state.deck)` measured at the *start* of a turn, i.e. the
number of tiles that will still be drawn after this one. Bands are absolute
(`>=48` / `24..47` / `<24`) so they mean the same thing across games of
different length, unlike terciles.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.flat_leaf import decompose, _city_points, _road_points, _cloister_points

# Absolute k_remaining band edges (tiles still to be drawn at the start of a turn).
K_BAND_EARLY_MIN = 48
K_BAND_MID_MIN = 24
PHASES = ("early", "mid", "late")
TERRAINS = ("city", "road", "farm", "cloister")


def k_band(k_remaining: int) -> str:
    if k_remaining >= K_BAND_EARLY_MIN:
        return "early"
    if k_remaining >= K_BAND_MID_MIN:
        return "mid"
    return "late"


def tercile(turn: int, n_turns: int) -> str:
    """Turn index -> early/mid/late by thirds of *this game's* length."""
    if n_turns <= 0:
        return "early"
    f = turn / n_turns
    if f < 1.0 / 3.0:
        return "early"
    if f < 2.0 / 3.0:
        return "mid"
    return "late"


def _meeple_key(player: int, mp) -> tuple:
    """Stable identity for a placed meeple. (row, col, side) is unique on a board:
    the engine never allows two meeples on the same tile side."""
    cws = mp.coordinate_with_side
    return (player, mp.meeple_type.value, cws.coordinate.row, cws.coordinate.column,
            cws.side.value)


def _meeple_set(state) -> dict:
    out = {}
    for p, ms in enumerate(state.placed_meeples):
        for mp in ms:
            out[_meeple_key(p, mp)] = p
    return out


def _terrain_of(state, key) -> str:
    """city / road / farm / cloister for a placed-meeple key."""
    _p, mtype, r, c, side_val = key
    if mtype in ("farmer", "big_farmer"):
        return "farm"
    tile = state.get_tile(r, c)
    if tile is None:
        return "unknown"
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    t = tile.get_type(Side(side_val))
    if t == TerrainType.CITY:
        return "city"
    if t == TerrainType.ROAD:
        return "road"
    if t in (TerrainType.CHAPEL, TerrainType.FLOWERS):
        return "cloister"
    return "unknown"


def _cloister_cells(state):
    """(row, col) of every placed cloister tile."""
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType
    out = []
    for coord in state.placed_coords:
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        t = tile.get_type(Side.CENTER)
        if t in (TerrainType.CHAPEL, TerrainType.FLOWERS):
            out.append((coord.row, coord.column))
    return out


@dataclass
class GameStats:
    """Everything `corpus_stats` and `e4_diff` need from one replayed game."""
    game_id: object
    deck_seed: int
    n_plies: int
    n_turns: int
    n_players: int
    final_scores: list
    replay_scores_match: object = None     # vs the archive's recorded scores, if present
    split_ok: bool = True
    meta: dict = field(default_factory=dict)

    turns: list = field(default_factory=list)        # per-turn records
    completions: list = field(default_factory=list)  # during-play feature closures
    meeples: list = field(default_factory=list)      # the full meeple ledger
    score_flow: list = field(default_factory=list)   # per seat: during/incomplete/farms/total


def replay_game_stats(deck_seed: int, actions, recorded_scores=None, game_id=None,
                      meta=None) -> GameStats:
    """Replay one game and emit its descriptive stats. Deterministic, no search."""
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector
    from carcassonne_ai.aux_targets import extract_terminal_ownership

    actions = [int(a) for a in actions]

    # ---- pass 1: the true terminal scores (unstubbed) ----------------------- #
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=False)
    board = game.get_init_board()
    for a in actions:
        board, _ = game.get_next_state(board, a)
    final_scores = [int(x) for x in board.state.scores]

    # ---- pass 2: the walk, with final scoring stubbed so meeples survive ---- #
    # `count_final_scores` fires only on the terminating move, so the stub is a
    # no-op everywhere else and the during-play walk is unaffected.
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=False)
    board = game.get_init_board()
    n_players = board.state.players

    gs = GameStats(game_id=game_id, deck_seed=int(deck_seed), n_plies=len(actions),
                   n_turns=0, n_players=n_players, final_scores=final_scores,
                   meta=dict(meta or {}))

    ledger = {}                      # meeple key -> ledger record
    seen_city, seen_road = set(), set()
    seen_cloister = set()
    turn = 0

    orig_cfs = PointsCollector.count_final_scores
    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
    try:
        i = 0
        while i < len(actions):
            state = board.state
            # A turn starts in the TILES phase. Snapshot the pre-turn view.
            k_rem = len(state.deck)
            actor = int(state.current_player)
            meeples_in_hand = [int(x) for x in state.meeples]
            scores_before = [int(x) for x in state.scores]
            before = _meeple_set(state)

            # Consume plies until the turn hands off (current_player changes) or
            # the actions run out. Handles both the normal tile+meeple pair and
            # the tile-phase PassAction path (no legal placement -> no meeple ply).
            plies_this_turn = 0
            while i < len(actions):
                board, _ = game.get_next_state(board, actions[i])
                i += 1
                plies_this_turn += 1
                if board.state.current_player != actor or board.state.is_terminated():
                    break
                if board.state.phase == GamePhase.TILES:
                    break

            state = board.state
            after = _meeple_set(state)
            scores_after = [int(x) for x in state.scores]

            # --- what the actor did with a meeple this turn ------------------ #
            placed_keys = [k for k in after if k not in before]
            returned_keys = [k for k in before if k not in after]
            if placed_keys:
                pk = placed_keys[0]
                terrain = _terrain_of(state, pk)
                move_type = terrain
                ledger[pk] = {
                    "player": pk[0], "terrain": terrain, "meeple_type": pk[1],
                    "place_turn": turn, "place_k_remaining": k_rem,
                    "place_tercile": None,   # filled once n_turns is known
                    "place_k_band": k_band(k_rem),
                    "return_turn": None, "points_earned": 0,
                }
            else:
                move_type = "pass"

            for rk in returned_keys:
                rec = ledger.get(rk)
                if rec is not None and rec["return_turn"] is None:
                    rec["return_turn"] = turn

            # --- features that closed this turn ------------------------------ #
            closed = _detect_completions(state, seen_city, seen_road, seen_cloister,
                                         before, returned_keys, turn, k_rem, n_players)
            gs.completions.extend(closed)
            # Attribute the points back to the meeples that came home.
            for ev in closed:
                for rk in ev["returned_keys"]:
                    rec = ledger.get(rk)
                    if rec is not None and rk[0] in ev["winners"]:
                        rec["points_earned"] += ev["points"]

            # --- openness ---------------------------------------------------- #
            d = decompose(state)
            open_city = sum(1 for root, fin in d.city_root_finished.items() if not fin)
            open_road = sum(1 for root, fin in d.road_root_finished.items() if not fin)
            H, W = len(state.board), len(state.board[0])
            open_clo = sum(1 for (r, c) in _cloister_cells(state)
                           if _cloister_points(r, c, state.board, H, W) < 9)

            gs.turns.append({
                "turn": turn,
                "player": actor,
                "k_remaining": k_rem,
                "k_band": k_band(k_rem),
                "plies": plies_this_turn,
                "move_type": move_type,
                "closed_here": len(closed),
                "meeples_in_hand": meeples_in_hand,
                "scores": scores_before,
                "score_delta": [scores_after[p] - scores_before[p] for p in range(n_players)],
                "open_city": open_city,
                "open_road": open_road,
                "open_cloister": open_clo,
                "meeples_on_board": len(after),
            })
            turn += 1

        gs.n_turns = turn
        term_state = board.state

        # --- terminal split: during play / unfinished features / farms ------- #
        stranded_keys = set(_meeple_set(term_state))
        own_state = copy.deepcopy(term_state)   # extract_terminal_ownership mutates
        during = [int(x) for x in term_state.scores][:n_players]
        farms = [0] * n_players
        incomplete = [0] * n_players
        farm_records, incomplete_records = [], []
        for r in extract_terminal_ownership(own_state):
            row = {"terrain": r.terrain, "size": len(r.coords), "finished": bool(r.finished),
                   "winners": list(r.winners), "points": int(r.points)}
            if r.terrain == "farm":
                farm_records.append(row)
            else:
                incomplete_records.append(row)
            bucket = farms if r.terrain == "farm" else incomplete
            for w in r.winners:
                if 0 <= w < n_players:
                    bucket[w] += int(r.points)
        gs.score_flow = [{"during_play": during[p], "incomplete": incomplete[p],
                          "farms": farms[p],
                          "total": during[p] + incomplete[p] + farms[p]}
                         for p in range(n_players)]
        gs.split_ok = all(gs.score_flow[p]["total"] == final_scores[p]
                          for p in range(n_players))
        gs.meta["terminal_farm_features"] = farm_records
        gs.meta["terminal_incomplete_features"] = incomplete_records
    finally:
        PointsCollector.count_final_scores = orig_cfs

    # ---- finish the meeple ledger ------------------------------------------ #
    for k, rec in ledger.items():
        rec["place_tercile"] = tercile(rec["place_turn"], gs.n_turns)
        rec["stranded"] = k in stranded_keys
        rec["locked_turns"] = ((gs.n_turns if rec["return_turn"] is None
                                else rec["return_turn"]) - rec["place_turn"])
        gs.meeples.append(rec)

    if recorded_scores is not None:
        gs.replay_scores_match = ([int(x) for x in recorded_scores] == final_scores)
    return gs


def _detect_completions(state, seen_city, seen_road, seen_cloister,
                        meeples_before, returned_keys, turn, k_rem, n_players):
    """Features that became finished on this turn.

    Identity is the component's frozen coordinate set, not the union-find root id
    (root ids are not stable across `decompose` calls). A finished city or road
    can never grow, so first-sighting == closure turn.
    """
    d = decompose(state)
    board = state.board
    H, W = len(board), len(board[0])
    out = []

    def _owners(positions, coord_only=None):
        """Which returned meeples sat on this feature, and who won it."""
        hits = []
        for rk in returned_keys:
            _p, _mt, r, c, side = rk
            if coord_only is not None:
                if (r, c) == coord_only:
                    hits.append(rk)
            elif (r, c, side) in positions:
                hits.append(rk)
        counts = [0] * n_players
        for rk in hits:
            counts[rk[0]] += 1
        m = max(counts) if counts else 0
        winners = [p for p, v in enumerate(counts) if v == m and m > 0]
        return hits, winners

    for root, finished in d.city_root_finished.items():
        if not finished:
            continue
        coords = frozenset(d.city_root_coords[root])
        if coords in seen_city:
            continue
        seen_city.add(coords)
        pos = {(r, c, s.value) for (r, c, s) in d.city_root_positions[root]}
        hits, winners = _owners(pos)
        pts = _city_points(coords, True, board)
        shields = sum(1 for (r, c) in coords if board[r][c].shield)
        out.append({"terrain": "city", "size": len(coords), "shields": shields,
                    "points": pts, "turn": turn, "k_remaining": k_rem,
                    "k_band": k_band(k_rem), "winners": winners,
                    "scored": bool(winners), "returned_keys": hits})

    for root, finished in d.road_root_finished.items():
        if not finished:
            continue
        coords = frozenset(d.road_root_coords[root])
        if coords in seen_road:
            continue
        seen_road.add(coords)
        pos = {(r, c, s.value) for (r, c, s) in d.road_root_positions[root]}
        hits, winners = _owners(pos)
        pts = _road_points(coords, True, board)
        out.append({"terrain": "road", "size": len(coords), "shields": 0,
                    "points": pts, "turn": turn, "k_remaining": k_rem,
                    "k_band": k_band(k_rem), "winners": winners,
                    "scored": bool(winners), "returned_keys": hits})

    for (r, c) in _cloister_cells(state):
        if (r, c) in seen_cloister:
            continue
        if _cloister_points(r, c, board, H, W) < 9:
            continue
        seen_cloister.add((r, c))
        hits, winners = _owners(None, coord_only=(r, c))
        out.append({"terrain": "cloister", "size": 9, "shields": 0, "points": 9,
                    "turn": turn, "k_remaining": k_rem, "k_band": k_band(k_rem),
                    "winners": winners, "scored": bool(winners), "returned_keys": hits})
    return out


# ---------------------------------------------------------------------------- #
# Per-game scalar summary — the vector that `e4_diff` percentile-ranks a human
# game against. Two levels: `game` scalars (whole-game) and `seat` scalars (one
# per player, so a human seat can be ranked against the champion seat pool).
# ---------------------------------------------------------------------------- #

def game_scalars(gs: GameStats) -> dict:
    comp = gs.completions
    cities = [e for e in comp if e["terrain"] == "city"]
    roads = [e for e in comp if e["terrain"] == "road"]
    clo = [e for e in comp if e["terrain"] == "cloister"]
    return {
        "n_turns": gs.n_turns,
        "n_completions": len(comp),
        "n_cities_closed": len(cities),
        "n_roads_closed": len(roads),
        "n_cloisters_closed": len(clo),
        "mean_city_size": _mean([e["size"] for e in cities]),
        "mean_road_size": _mean([e["size"] for e in roads]),
        "max_city_size": max([e["size"] for e in cities], default=0),
        "score_margin_abs": abs(gs.final_scores[0] - gs.final_scores[1])
        if len(gs.final_scores) == 2 else 0,
        "total_points": sum(gs.final_scores),
    }


def seat_scalars(gs: GameStats, p: int) -> dict:
    """The per-seat vector. Every field is defined for a human seat too, so the
    same code ranks an E4 human against the champion-seat pool."""
    mine = [m for m in gs.meeples if m["player"] == p]
    farmers = [m for m in mine if m["terrain"] == "farm"]
    nonfarm = [m for m in mine if m["terrain"] != "farm"]
    stranded_nf = [m for m in nonfarm if m["stranded"]]
    turns = [t for t in gs.turns if t["player"] == p]
    flow = gs.score_flow[p] if p < len(gs.score_flow) else {
        "during_play": 0, "incomplete": 0, "farms": 0, "total": 0}
    won = [e for e in gs.completions if p in e["winners"]]
    cities_won = [e for e in won if e["terrain"] == "city"]
    roads_won = [e for e in won if e["terrain"] == "road"]

    # move-type mix, both segmentations
    mix = {}
    for seg, keyfn in (("tercile", lambda t: tercile(t["turn"], gs.n_turns)),
                       ("kband", lambda t: t["k_band"])):
        for ph in PHASES:
            sel = [t for t in turns if keyfn(t) == ph]
            n = len(sel)
            for mt in TERRAINS + ("pass",):
                mix[f"{seg}_{ph}_frac_{mt}"] = (
                    sum(1 for t in sel if t["move_type"] == mt) / n if n else None)
            mix[f"{seg}_{ph}_n_turns"] = n
            mix[f"{seg}_{ph}_deploy_rate"] = (
                sum(1 for t in sel if t["move_type"] != "pass") / n if n else None)

    total_pts = flow["total"]
    d = {
        "final_score": gs.final_scores[p] if p < len(gs.final_scores) else 0,
        "during_play": flow["during_play"],
        "incomplete_pts": flow["incomplete"],
        "farm_pts": flow["farms"],
        "during_play_frac": flow["during_play"] / total_pts if total_pts else None,
        "farm_pts_frac": flow["farms"] / total_pts if total_pts else None,
        "incomplete_frac": flow["incomplete"] / total_pts if total_pts else None,

        "n_meeples_placed": len(mine),
        "n_farmers_placed": len(farmers),
        "n_nonfarm_placed": len(nonfarm),
        "deploy_rate": len(mine) / len(turns) if turns else None,

        # --- stranding ---
        "stranded_nonfarmer": len(stranded_nf),
        "stranding_rate_nonfarmer": len(stranded_nf) / len(nonfarm) if nonfarm else None,
        "stranded_all": sum(1 for m in mine if m["stranded"]),
        "meeple_turns_locked": sum(m["locked_turns"] for m in stranded_nf),
        "mean_locked_turns_returned": _mean(
            [m["locked_turns"] for m in nonfarm if not m["stranded"]]),

        # --- farm timing ---
        "first_farm_turn": min([m["place_turn"] for m in farmers], default=None),
        "first_farm_k_remaining": max([m["place_k_remaining"] for m in farmers],
                                      default=None),
        "mean_farm_turn": _mean([m["place_turn"] for m in farmers]),
        "farm_meeple_turns_locked": sum(m["locked_turns"] for m in farmers),
        "farm_pts_per_farmer": flow["farms"] / len(farmers) if farmers else None,
        "n_farmers_early": sum(1 for m in farmers if m["place_k_band"] == "early"),
        "n_farmers_mid": sum(1 for m in farmers if m["place_k_band"] == "mid"),
        "n_farmers_late": sum(1 for m in farmers if m["place_k_band"] == "late"),

        # --- capital efficiency ---
        "mean_meeples_in_hand": _mean([t["meeples_in_hand"][p] for t in gs.turns]),
        "min_meeples_in_hand": min([t["meeples_in_hand"][p] for t in gs.turns],
                                   default=None),
        "n_features_won": len(won),
        "mean_city_size_won": _mean([e["size"] for e in cities_won]),
        "mean_road_size_won": _mean([e["size"] for e in roads_won]),
        "pts_per_meeple_placed": total_pts / len(mine) if mine else None,
    }
    d.update(mix)
    return d


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
