"""Joshua-bot — a scripted opponent that plays the OWNER's self-described strategy.

WHAT THIS IS. Every strength number this project owns is measured against agents
this project built. ``measurement/e4_games`` is the one stream measured against a
*human* — and that human (Joshua) is currently ahead of the champion. On
2026-08-12 he described, verbatim, how he plays it (
``measurement/e4_games/ANCHOR_INTERVIEW_2026-08-12.md``). This module encodes the
eight concrete, encodable rules of that interview — **J1..J8** — as a fixed,
deterministic policy, so the strategy can be played at n=400-800 deck-paired
volume instead of one game an evening.

It is NOT a strength lever and NOT a champion candidate. It is an *instrument*:
if a scripted J1..J8 player reproduces even part of the +10 pts/game lean, the
lean has a mechanism; if it reproduces none of it, the lean is not in these rules.

THE SPEC IS THE AUDIT SURFACE. ``measurement/joshuabot_20260812/SPEC.md`` maps
every J-rule to the symbol below that implements it, its parameters, and the
interview sentence it came from. If you change a rule here, change that table —
its whole point is that the owner can check the bot plays HIS strategy.

FAIR INFORMATION ONLY (hard contract, tested).
  * the bot reads the board, both score totals, both meeple RESERVES, and the
    **remaining tile MULTISET** — the last is legal public information (the bag
    contents; pros count it, and the owner explicitly says he does: interview
    §3), and it is what J2's "i look at remaining tiles" means;
  * it NEVER reads draw ORDER. ``remaining_tiles()`` groups the deck by tile
    description and sorts, so order is destroyed by construction, and it
    deliberately excludes ``state.next_tile`` (the one tile whose identity a
    lookahead could otherwise leak into a *future* state). ``k_remaining`` and
    every clock/bag quantity is read from the ROOT state of the decision, never
    from a candidate afterstate, so a lookahead cannot pick up the tile the
    engine happened to draw next.
    ``tests/test_joshua_bot.py::test_deck_permutation_invariance`` shuffles the
    undrawn deck and asserts the chosen action does not move.

DETERMINISTIC. No RNG anywhere. Ties break on the lowest action index, after
rounding scores to ``params.score_round`` decimals. ``seed`` is accepted only so
the constructor matches the other agents' signature; it is unused.

HOW IT DECIDES (see also `SPEC.md` §Precedence):
  0. forced move -> take it.
  1. enumerate the legal actions and score every one:
        value(afterstate) = flat_base_score(afterstate, me)      # the "virtual
                                                                 # score count"
                          + SUM of the J-term potentials below   # the human part
     In the TILES phase the score is a TURN value: the tile placement is scored
     together with the best meeple follow-up it enables (a "sneak a meeple into
     his city" join is a tile move AND a meeple move; scoring the tile alone
     cannot see it).
  2. apply the HARD FILTERS in a fixed order (F-END, F-J10, F-J9, F-J3), each
     skipped if it would empty the candidate set;
  3. argmax, lowest action index wins ties.

TOURNAMENT AXES (2026-08-12 — the owner's answer to the SPEC's open questions was
"test these and see what wins empirically"): ``j7_weight``,
``j8_break_reserve_floor``, ``j9_avoid_cloisters``, on top of ``preset``. Pass them
as ``overrides={...}``; ``JoshuaBot.variant_id`` labels the resulting cell and
``JoshuaBot.manifest`` records the FULL resolved config, so a tournament cell never
needs dirname archaeology. Every variant is separately deterministic.

The J-terms are *potentials of the afterstate*, in POINTS, signed from the
bot's own seat. Because every candidate shares the same "before" state, ranking
on the afterstate potential is identical to ranking on its delta — except for
J5, which is explicitly a before/after term (it prices what a placement FEEDS)
and is handed both states.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

from .action_space import decode, meeple_farmer_base, meeple_pass_index
from .flat_leaf import Decomp, decompose, flat_base_score

__all__ = ["JoshuaParams", "PRESETS", "JoshuaBot", "Position", "remaining_tiles"]

_CLOISTER_TERRAIN = (TerrainType.CHAPEL, TerrainType.FLOWERS)
_FARMER_TYPES = (MeepleType.FARMER, MeepleType.BIG_FARMER)


# --------------------------------------------------------------------------- #
# parameters — one knob per documented degree of freedom, all named for the    #
# J-rule they serve. PRESETS below carry the J10 "early" vs "current" epochs.  #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class JoshuaParams:
    """Every tunable of the bot. Defaults ARE the ``current`` preset (J10's
    later, farm-disciplined epoch); ``PRESETS['early']`` overrides the handful
    of fields that the interview says moved."""

    name: str = "current"

    # --- J1  late majority-steal join into his large open cities ------------ #
    j1_min_city_tiles: int = 5        # "if they are getting on the bigger side"
    j1_min_open_edges: int = 2        # "probably wont close" -> >=2 open ways in
    j1_join_bonus: float = 3.0        # premium over what the naive count already pays
    j1_late_extra: float = 1.0        # "sometimes late in the game": x(1+extra*late_frac)

    # --- J2  deck-counted farm tie/steal, planned 2-4 tiles ahead ----------- #
    j2_steal_w: float = 1.0           # weight on the realized tie/steal
    j2_approach_w: float = 0.15       # weight on keeping a way IN to a target field
    j2_plan_horizon: int = 3          # "2-4 tiles in advance"
    j2_reach_threshold: float = 0.50  # "is it realistic to get there"
    j2_entry_cells_cap: int = 3       # entry-surface saturation point
    j2_min_farm_value: float = 3.0    # below this the field is SURRENDERED (J10 current)
    j2_low_farm_penalty: float = 2.0  # cost of spending a farmer on a sub-threshold field
    j2_unfinished_city_weight: float = 1.0   # how much unclosed adjacent cities count
    j2_city_count_from_k: int = 36    # ...and only once k_remaining <= this ("late game")
    j2_city_close_open_max: int = 2   # an unclosed city counts only if this close to done

    # --- J3  own-reserve floor ---------------------------------------------- #
    j3_reserve_floor: int = 1         # "keep at least 1 meeple in my hand"
    j3_endgame_release_k: int = 8     # ...until the bag is nearly empty; then spend

    # --- J4  opponent-reserve conditioning ---------------------------------- #
    j4_min_urgency: float = 0.35      # urgency when he has NO meeples left
    j4_full_reserve: int = 4          # reserve at which urgency saturates to 1.0

    # --- J5  value-starving throwaway placement ----------------------------- #
    j5_weight: float = 0.5
    j5_value_floor: float = 4.0       # "already worth more than a few points"
    j5_throwaway_gain: float = 1.0    # a placement gaining <= this is a "throwaway tile"

    # --- J6  anchor structure + road policy --------------------------------- #
    j6_anchor_bonus: float = 2.0      # for holding one city anchor and one road anchor
    j6_anchor_city_min: int = 3       # "a big city"
    j6_anchor_road_min: int = 2
    j6_road_join_min_len: int = 4     # "his road is getting long -> tie it up"
    j6_road_join_bonus: float = 2.0
    j6_road_skeptic_max_len: int = 3  # "generally less bullish on roads"
    j6_road_claim_penalty: float = 1.5
    j6_road_anchor_allowance: int = 1  # the anchor road itself is free

    # --- J7  city-close x opponent-farm-majority interaction ---------------- #
    j7_weight: float = 1.0            # 0.0 == "naive"; 1.0 == "hesitate" (see SPEC)
    j7_points_per_field: float = 3.0  # "he gets an easy 3 points there"

    # --- J8  pivotal-feature overcommit ------------------------------------- #
    j8_pivotal_swing: float = 12.0    # a feature worth this much of swing can decide it
    j8_overcommit_bonus: float = 3.0
    j8_value_norm: float = 10.0
    j8_max_city_meeples: int = 2      # "sometimes it takes 2 meeple to secure a city"
    j8_max_farm_meeples: int = 3      # "sometimes 3 for a single farm"
    #: TOURNAMENT AXIS. OFF = J3 wins the J3/J8 conflict (a second meeple onto a
    #: feature you already lead is not a "majority swing", so the reserve floor
    #: refuses it). ON = "you have to take chances": a pivotal-feature overcommit
    #: is exempt from F-J3. See SPEC §7 Q8.
    j8_break_reserve_floor: bool = False

    # --- J9  cloister caution (OPT-IN; his stated adaptation) ---------------- #
    #: TOURNAMENT AXIS, default OFF. "he is good at blocking my cloister
    #: completions. i'm more cautious about grabbing them now."
    j9_avoid_cloisters: bool = False
    j9_cloister_block_frac: float = 0.55  # cautious while k > frac*k0
    j9_min_surrounding: int = 6       # ...unless the 3x3 is already this full (max 9)

    # --- J10  epoch knob that is not one J-rule ------------------------------ #
    early_farm_block_frac: float = 0.55   # no FARMER claim while k > frac*k0

    # --- housekeeping -------------------------------------------------------- #
    score_round: int = 6              # tie-robustness before the deterministic argmax
    tile_lookahead: bool = True       # score a tile move together with its meeple follow-up


#: J10 — "i think i did go less aggressive on farms, especially early on in the
#: game, since my first few games against him." Two epochs of the SAME player.
PRESETS: dict[str, JoshuaParams] = {
    # The later, farm-disciplined Joshua: blocks early farmers, counts city
    # potential late, and surrenders fields worth less than j2_min_farm_value.
    "current": JoshuaParams(name="current"),
    # The first-few-games Joshua: farm-aggressive, contests eagerly, no early
    # block, no surrender bar, and does NOT wait for the late-game city count.
    "early": JoshuaParams(
        name="early",
        j2_steal_w=1.5,
        j2_approach_w=0.30,
        j2_reach_threshold=0.30,
        j2_min_farm_value=0.0,
        j2_low_farm_penalty=0.0,
        j2_unfinished_city_weight=0.5,
        j2_city_count_from_k=999,          # count city potential at ANY point
        early_farm_block_frac=0.0,         # "sometimes i lay down a farm early"
    ),
}


# --------------------------------------------------------------------------- #
# fair-information accessors                                                   #
# --------------------------------------------------------------------------- #
def k_remaining(state) -> int:
    """Tiles left = undrawn deck + the one in hand. The game CLOCK.

    Byte-identical to ``flat_leaf._k_remaining`` / ``fair_agent.k_remaining``.
    Order-free: it is a count, never an identity."""
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def remaining_tiles(state) -> tuple[tuple[str, object, int], ...]:
    """The remaining tile **MULTISET**, with draw order destroyed by construction.

    Returns ``((description, one representative Tile, count), ...)`` sorted by
    description. This is the ONLY function in the module allowed to touch
    ``state.deck``, and it cannot leak order: the deck list is consumed into a
    dict keyed by description and re-emitted in sorted order.

    ``state.next_tile`` is deliberately EXCLUDED (unlike ``flat_leaf._bag_stats``,
    which counts it in the TILES phase): the bot's bag terms are about what is
    still *to come*, and excluding it makes deck-permutation invariance exact for
    lookahead states too, where ``next_tile`` is whatever the engine happened to
    draw."""
    groups: dict[str, list] = {}
    for tile in state.deck:
        g = groups.get(tile.description)
        if g is None:
            groups[tile.description] = [tile, 1]
        else:
            g[1] += 1
    return tuple((d, v[0], v[1]) for d, v in sorted(groups.items()))


def surrounding_count(board, r: int, c: int) -> int:
    """Placed tiles in the 3x3 around (r, c), INCLUDING the centre tile — i.e.
    exactly what a cloister on (r, c) would score if the game ended now, and
    exactly ``flat_leaf._cloister_points``. Max 9. J9 reads this as "completion
    prospects"; a human reads it off the board at a glance."""
    h = len(board)
    w = len(board[0]) if h else 0
    n = 0
    for rr in range(max(r - 1, 0), min(r + 2, h)):
        for cc in range(max(c - 1, 0), min(c + 2, w)):
            if board[rr][cc] is not None:
                n += 1
    return n


def bag_farm_fraction(state) -> float:
    """Fraction of the remaining MULTISET carrying at least one field segment —
    i.e. tiles that could extend a farm. Deliberately permissive (rotation is
    free), the same spirit as ``flat_leaf._bag_stats``' city-edge proxy."""
    n = ok = 0
    for _desc, tile, count in remaining_tiles(state):
        n += count
        if tile.farms:
            ok += count
    return (ok / n) if n else 0.0


# --------------------------------------------------------------------------- #
# structural analysis of one (after)state                                      #
# --------------------------------------------------------------------------- #
@dataclass
class Position:
    """One board's structure + who owns what. Pure board facts — carries no
    clock and no bag, because those are read from the decision ROOT (see the
    fair-information note in the module docstring)."""

    state: object
    decomp: Decomp
    city_counts: dict          # city root -> [meeples_p0, meeples_p1]
    road_counts: dict          # road root -> [meeples_p0, meeples_p1]
    farm_counts: dict          # farm root -> [meeples_p0, meeples_p1]
    cloister_owner: dict       # (r, c) -> player holding that cloister
    #: per-position memo — every entry is a pure function of this board, so it is
    #: only ever a speed device (a Position is never mutated after `analyze`).
    memo: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.memo is None:
            self.memo = {}

    def base(self, player: int) -> float:
        """``flat_base_score`` for this board — the "virtual score count"."""
        key = ("base", player)
        v = self.memo.get(key)
        if v is None:
            v = float(flat_base_score(self.state, player, self.decomp))
            self.memo[key] = v
        return v

    # --- derived, memoized ------------------------------------------------- #
    def city_value(self, root: int) -> float:
        """Points the component pays its majority holder if scored as it stands
        (``city_root_delta`` is tiles+shields = the 1pt/tile standing value;
        a finished city pays double)."""
        d = self.decomp
        v = float(d.city_root_delta.get(root, 0))
        return 2.0 * v if d.city_root_finished.get(root, False) else v

    def road_value(self, root: int) -> float:
        return float(len(self.decomp.road_root_coords.get(root, ())))

    def farm_coords(self, root: int) -> set:
        return {(r, c) for (r, c, _fc) in self.decomp.farm_root_keys.get(root, ())}

    def farm_entry_cells(self, root: int) -> int:
        """Empty board cells orthogonally adjacent to the field — the permissive
        proxy for "is there still a way in". Rotation is free, so an adjacent
        empty cell is treated as a potential entry."""
        key = ("entry", root)
        v = self.memo.get(key)
        if v is not None:
            return v
        board = self.state.board
        h = len(board)
        w = len(board[0]) if h else 0
        cells = set()
        for (r, c) in self.farm_coords(root):
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w and board[nr][nc] is None:
                    cells.add((nr, nc))
        self.memo[key] = v = len(cells)
        return v

    def city_closable(self, root: int, p: JoshuaParams) -> bool:
        d = self.decomp
        if d.city_root_finished.get(root, False):
            return True
        return d.city_root_open_n.get(root, 99) <= p.j2_city_close_open_max


def analyze(state) -> Position:
    """Decompose the board and attribute every placed meeple to its component.

    The attribution mirrors ``flat_leaf._final_scores`` exactly (terrain of the
    meeple's own side; FARMER type -> ``farm_pos0_root``) so "who has the
    majority" here is the same question the scorer answers."""
    d = decompose(state)
    board = state.board
    n = state.players
    city: dict = {}
    road: dict = {}
    farm: dict = {}
    cloister: dict = {}
    for player in range(n):
        for mp in state.placed_meeples[player]:
            cws = mp.coordinate_with_side
            r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
            tile = board[r][c]
            if tile is None:
                continue
            terrain = tile.get_type(side)
            w = 2 if mp.meeple_type in (MeepleType.BIG, MeepleType.BIG_FARMER) else 1
            if terrain == TerrainType.CITY:
                root = d.city_side_root.get((r, c, side))
                if root is not None:
                    city.setdefault(root, [0] * n)[player] += w
            elif terrain == TerrainType.ROAD:
                root = d.road_side_root.get((r, c, side))
                if root is not None:
                    road.setdefault(root, [0] * n)[player] += w
            elif terrain in _CLOISTER_TERRAIN:
                cloister[(r, c)] = player
            elif mp.meeple_type in _FARMER_TYPES:
                root = d.farm_pos0_root.get((r, c, side))
                if root is not None:
                    farm.setdefault(root, [0] * n)[player] += w
    return Position(state=state, decomp=d, city_counts=city, road_counts=road,
                    farm_counts=farm, cloister_owner=cloister)


@dataclass(frozen=True)
class Clock:
    """The decision's clock + bag, read ONCE from the root state and reused for
    every candidate. Keeping this off the candidate afterstates is what makes the
    bot blind to the tile the engine draws inside a lookahead."""

    k: int                 # tiles remaining at the root
    k0: int                # tiles remaining at the bot's first move (the full bag)
    bag_farm_frac: float
    my_reserve: int
    opp_reserve: int
    margin: float          # flat_base_score at the root, from the bot's seat

    @property
    def late_frac(self) -> float:
        """0.0 at the start of the game, 1.0 at the last tile."""
        if self.k0 <= 0:
            return 1.0
        f = 1.0 - (self.k / self.k0)
        return 0.0 if f < 0.0 else (1.0 if f > 1.0 else f)


# --------------------------------------------------------------------------- #
# the J-rules                                                                  #
# --------------------------------------------------------------------------- #
def j4_urgency(clock: Clock, p: JoshuaParams) -> float:
    """J4 — "if i see he is out of meeple, i am more okay with leaving a
    something juicy unclaimed". A multiplier in ``[j4_min_urgency, 1.0]`` on
    every CONTEST/CLAIM term (J1, J2, J5, J6b, J8): full urgency while he can
    still answer, relaxed once he cannot."""
    r = clock.opp_reserve
    frac = min(1.0, r / float(max(p.j4_full_reserve, 1)))
    return p.j4_min_urgency + (1.0 - p.j4_min_urgency) * frac


def j1_majority_steal(pos: Position, me: int, clock: Clock, p: JoshuaParams,
                      urg: float) -> float:
    """J1 — "i notice he tends to build large cities that probably wont close.
    if they are getting on the bigger side, i will attempt to sneak a meeple in,
    sometimes late in hte game."

    Fires on an UNFINISHED city that HE has a meeple on, that is big
    (>= ``j1_min_city_tiles``) and still open (>= ``j1_min_open_edges`` empty
    adjacent cells), and on which the bot now holds a TIE or better. Ties pay all
    tied players in full, so a tie is the whole prize.

    The naive count already pays for the join; this is the PREMIUM that makes the
    bot spend a meeple on it in preference to equally-scored alternatives, and it
    grows as the game gets late."""
    d = pos.decomp
    opp = 1 - me
    total = 0.0
    for root, cnt in pos.city_counts.items():
        if d.city_root_finished.get(root, False):
            continue
        if cnt[me] < 1 or cnt[opp] < 1:
            continue                                  # not a JOIN into his city
        if cnt[me] < cnt[opp]:
            continue                                  # not a tie/majority
        if len(d.city_root_coords.get(root, ())) < p.j1_min_city_tiles:
            continue
        if d.city_root_open_n.get(root, 0) < p.j1_min_open_edges:
            continue
        total += p.j1_join_bonus * (1.0 + p.j1_late_extra * clock.late_frac) * urg
    return total


def farm_potential_value(pos: Position, root: int, clock: Clock,
                         p: JoshuaParams) -> float:
    """The part of a field's worth the naive count CANNOT see: 3 points for each
    adjacent city that is not finished yet but is plausibly closable.

    ``flat_base_score`` already pays 3 per *finished* adjacent city, so counting
    those here would double-count. J10's "current" epoch only counts the unclosed
    ones from ``j2_city_count_from_k`` tiles remaining onward ("i started to count
    the cities, especially late in game")."""
    if clock.k > p.j2_city_count_from_k:
        return 0.0
    d = pos.decomp
    n = 0
    for croot in d.farm_root_adj_city_roots.get(root, ()):
        if d.city_root_finished.get(croot, False):
            continue                                   # already priced by the base
        if pos.city_closable(croot, p):
            n += 1
    return 3.0 * n * p.j2_unfinished_city_weight


def farm_total_value(pos: Position, root: int, clock: Clock,
                     p: JoshuaParams) -> float:
    """Everything the field is worth right now: 3 per finished adjacent city
    (what the base already pays) plus the potential above. This is the quantity
    the J10-"current" SURRENDER bar (``j2_min_farm_value``) is read against."""
    finished = 3.0 * pos.decomp.farm_root_finished_cities.get(root, 0)
    return finished + farm_potential_value(pos, root, clock, p)


def j2_reach(pos: Position, root: int, clock: Clock, p: JoshuaParams) -> float:
    """J2's planning test — "sometimes this requires planning 2-4 tiles in
    advance, so i look at remaining tiles and try to see if its realistic to get
    there."

    A deliberately simple, deck-counted model of "can I still get in":
      * how many of MY turns are left (``k // 2``) — 0 turns => 0;
      * is there still a way in (``farm_entry_cells``) — 0 cells => 0;
      * does the bag still hold tiles that can carry a field
        (``bag_farm_fraction``, order-free).
    Combined as ``1 - (1 - per_turn)^h`` over a horizon of ``j2_plan_horizon``
    of my own turns. Permissive by construction — see SPEC OPEN QUESTION 2."""
    my_turns = clock.k // 2
    if my_turns < 1:
        return 0.0
    cells = pos.farm_entry_cells(root)
    if cells == 0:
        return 0.0
    h = min(p.j2_plan_horizon, my_turns)
    if h < 1:
        return 0.0
    cap = max(p.j2_entry_cells_cap, 1)
    per_turn = min(1.0, clock.bag_farm_frac * min(cells, cap) / cap)
    return 1.0 - (1.0 - per_turn) ** h


def j2_farm_attack(pos: Position, me: int, clock: Clock, p: JoshuaParams,
                   urg: float) -> float:
    """J2 — "if i see a farm is valuable, i will try to tie it or steal from him."

    Two pieces, both gated by the planning test above:
      * REALIZED (``j2_steal_w``): the bot holds a tie-or-better on a field HE has
        a meeple on, and the field clears the value bar.
      * APPROACH (``j2_approach_w``): a valuable field he holds and the bot does
        NOT, on which a way in still exists — this is what makes tile placements
        that keep/grow an entry surface next to a target field preferable, i.e.
        the "2-4 tiles in advance" part.
    Plus the J10-"current" SURRENDER penalty: spending a farmer on a field worth
    less than ``j2_min_farm_value`` is charged ``j2_low_farm_penalty``."""
    opp = 1 - me
    total = 0.0
    for root, cnt in pos.farm_counts.items():
        value = farm_total_value(pos, root, clock, p)
        mine, his = cnt[me], cnt[opp]
        if mine >= 1 and his >= 1 and mine >= his:
            # REALIZED: the tie/steal already happened, so no reach test is owed
            # (the planning test gates the APPROACH loop below, which is where
            # "2-4 tiles in advance" actually lives).
            if value >= p.j2_min_farm_value:
                total += p.j2_steal_w * farm_potential_value(pos, root, clock, p) * urg
        if mine >= 1 and value < p.j2_min_farm_value:
            total -= p.j2_low_farm_penalty * mine        # SURRENDER low-value fields
    # approach: his valuable fields that are still enterable
    for root, cnt in pos.farm_counts.items():
        if cnt[me] >= 1 or cnt[opp] < 1:
            continue
        value = farm_total_value(pos, root, clock, p)
        if value < p.j2_min_farm_value:
            continue
        reach = j2_reach(pos, root, clock, p)
        if reach < p.j2_reach_threshold:
            continue
        total += p.j2_approach_w * value * reach * urg
    return total


def unclaimed_value(pos: Position, p: JoshuaParams) -> float:
    """Total value sitting on features NOBODY has a meeple on, counting only the
    excess over ``j5_value_floor`` ("already worth more than a few points").
    Cities, roads and cloisters."""
    memo_key = ("unclaimed", p.j5_value_floor)
    cached = pos.memo.get(memo_key)
    if cached is not None:
        return cached
    d = pos.decomp
    total = 0.0
    for root in d.city_root_coords:
        if pos.city_counts.get(root):
            continue
        total += max(0.0, pos.city_value(root) - p.j5_value_floor)
    for root in d.road_root_coords:
        if pos.road_counts.get(root):
            continue
        total += max(0.0, pos.road_value(root) - p.j5_value_floor)
    board = pos.state.board
    h = len(board)
    w = len(board[0]) if h else 0
    # `placed_coords` is a set of engine Coordinate objects; only summed over, so
    # its (hash) iteration order can never reach the decision.
    for coord in getattr(pos.state, "placed_coords", ()):
        r, c = coord.row, coord.column
        if (r, c) in pos.cloister_owner:
            continue
        tile = board[r][c]
        if tile is None or tile.get_type(Side.CENTER) not in _CLOISTER_TERRAIN:
            continue
        total += max(0.0, surrounding_count(board, r, c) - p.j5_value_floor)
    pos.memo[memo_key] = total
    return total


def j5_dump(before: Position, after: Position, me: int, clock: Clock,
            p: JoshuaParams, urg: float) -> float:
    """J5 — "if he has meeple and i have a throwaway tile, i will place it
    somewhere where it doesn't add to anything unclaimed that is already worth
    more than a few points."

    The ONE before/after term. A placement is a "throwaway" when it gains the bot
    at most ``j5_throwaway_gain`` points of naive count; for those and only those,
    every point of UNCLAIMED value it feeds (above the floor) is charged. Off
    entirely when he has no meeples left to grab that value with."""
    if clock.opp_reserve <= 0:
        return 0.0
    d_base = after.base(me) - before.base(me)
    if d_base > p.j5_throwaway_gain:
        return 0.0                                    # not a throwaway: take the points
    fed = unclaimed_value(after, p) - unclaimed_value(before, p)
    return -p.j5_weight * max(0.0, fed) * urg


def j6_anchor_and_roads(pos: Position, me: int, clock: Clock, p: JoshuaParams,
                        urg: float) -> float:
    """J6 — "i learned from him to keep a big city and road as mine, even if
    there is no plan to close it... sometimes i see his road is getting long and
    thats my signal to tie it up. but i'm generally less bullish on roads."

    Three pieces:
      a. ANCHOR: a bonus for holding exactly one unfinished city anchor and one
         unfinished road anchor — the endgame-points home and the tile dump.
      b. ROAD JOIN: tie-or-better on an unfinished road of his that has got long.
      c. ROAD SKEPTICISM: a charge on every SOLO short road claim past the one
         anchor road."""
    d = pos.decomp
    opp = 1 - me
    total = 0.0

    has_city_anchor = False
    for root, cnt in pos.city_counts.items():
        if d.city_root_finished.get(root, False) or cnt[me] <= cnt[opp]:
            continue
        if len(d.city_root_coords.get(root, ())) >= p.j6_anchor_city_min:
            has_city_anchor = True
            break
    has_road_anchor = False
    n_short_solo_roads = 0
    for root, cnt in pos.road_counts.items():
        if d.road_root_finished.get(root, False):
            continue
        length = len(d.road_root_coords.get(root, ()))
        if cnt[me] >= 1 and cnt[opp] >= 1 and cnt[me] >= cnt[opp] \
                and length >= p.j6_road_join_min_len:
            total += p.j6_road_join_bonus * urg                       # (b)
        if cnt[me] > cnt[opp]:
            if length >= p.j6_anchor_road_min:
                has_road_anchor = True
            if cnt[opp] == 0 and length <= p.j6_road_skeptic_max_len:
                n_short_solo_roads += 1
    total += p.j6_anchor_bonus * (int(has_city_anchor) + int(has_road_anchor))  # (a)
    total -= p.j6_road_claim_penalty * max(
        0, n_short_solo_roads - p.j6_road_anchor_allowance)                     # (c)
    return total


def j7_close_vs_farm(pos: Position, me: int, p: JoshuaParams) -> float:
    """J7 — "its hard for me to pass up on closing unclaimed cities. i hesistate
    if I've already surrendered the farm to him because he gets an easy 3 points
    there."

    A charge of ``j7_points_per_field`` for every field on which HE holds a strict
    farm majority that borders a FINISHED city the bot does not own.

    ⚠️ ``flat_base_score`` ALREADY pays him those 3 points once (a finished city
    is what a field counts). So ``j7_weight=1.0`` deliberately prices it TWICE:
    that IS the "i hesitate" — a human over-weighting a cost his own arithmetic
    already contains. ``j7_weight=0.0`` recovers the naive count. SPEC OPEN
    QUESTION 3 asks the owner which he means."""
    d = pos.decomp
    opp = 1 - me
    total = 0.0
    for froot, adj in d.farm_root_adj_city_roots.items():
        fc = pos.farm_counts.get(froot)
        if not fc or fc[opp] <= fc[me]:
            continue                                   # he has not taken this field
        for croot in adj:
            if not d.city_root_finished.get(croot, False):
                continue
            cc = pos.city_counts.get(croot)
            if cc and cc[me] > cc[opp]:
                continue                               # my own city: no hesitation
            total -= p.j7_weight * p.j7_points_per_field
    return total


def j8_city_term(pos: Position, root, cnt, me: int, clock: Clock,
                 p: JoshuaParams, urg: float) -> float:
    """J8 on ONE city component. Non-zero == "this is a pivotal-feature
    overcommit" — which is also exactly the predicate the ``j8_break_reserve_floor``
    exemption reads, so the rule and its exemption can never drift apart."""
    d = pos.decomp
    opp = 1 - me
    if d.city_root_finished.get(root, False):
        return 0.0
    if d.city_root_open_n.get(root, 0) < 1:
        return 0.0                                     # he can no longer get in
    value = pos.city_value(root)
    swing = 2.0 * value
    if swing < p.j8_pivotal_swing or swing < abs(clock.margin):
        return 0.0
    if cnt[me] - cnt[opp] < 2 or cnt[me] > p.j8_max_city_meeples:
        return 0.0
    return p.j8_overcommit_bonus * min(1.0, value / p.j8_value_norm) * urg


def j8_farm_term(pos: Position, root, cnt, me: int, clock: Clock,
                 p: JoshuaParams, urg: float) -> float:
    """J8 on ONE field. Same contract as :func:`j8_city_term`."""
    opp = 1 - me
    if pos.farm_entry_cells(root) < 1:
        return 0.0
    value = farm_total_value(pos, root, clock, p)
    swing = 2.0 * value
    if swing < p.j8_pivotal_swing or swing < abs(clock.margin):
        return 0.0
    if cnt[me] - cnt[opp] < 2 or cnt[me] > p.j8_max_farm_meeples:
        return 0.0
    return p.j8_overcommit_bonus * min(1.0, value / p.j8_value_norm) * urg


def j8_overcommit(pos: Position, me: int, clock: Clock, p: JoshuaParams,
                  urg: float) -> float:
    """J8 — "sometimes it takes 2 meeple to secure a city. sometimes 3 for a
    single farm. you can sometimes see that the game will turn on a single large
    feature, and in those cases, you have to take chances."

    A feature is PIVOTAL when its swing (2x its value — he gains it, I lose it)
    clears ``j8_pivotal_swing`` AND is big enough to flip the current margin. On a
    pivotal, still-enterable feature the bot is paid for holding a 2-meeple lead
    (3 on a field), which the naive count values at exactly zero — the extra
    meeple buys insurance against a later tie, not points."""
    return (sum(j8_city_term(pos, r, c, me, clock, p, urg)
                for r, c in pos.city_counts.items())
            + sum(j8_farm_term(pos, r, c, me, clock, p, urg)
                  for r, c in pos.farm_counts.items()))


# --------------------------------------------------------------------------- #
# the agent                                                                    #
# --------------------------------------------------------------------------- #
@dataclass
class _Cand:
    """One scored candidate action, with everything the hard filters need."""
    action: int
    score: float
    terms: dict
    after: Position
    is_meeple_place: bool = False
    is_farmer: bool = False
    closes_own: bool = False       # the meeple lands on a feature finished THIS turn
    swings_majority: bool = False  # the meeple ties/takes a contested feature
    is_cloister: bool = False      # the meeple lands on a cloister (J9)
    cloister_strong: bool = False  # ...and its 3x3 is already j9_min_surrounding full
    is_pivotal_overcommit: bool = False   # J8 fires on the feature this meeple joins


class JoshuaBot:
    """The scripted owner-strategy opponent.

    Interface: ``choose_action(board) -> int`` plus the telemetry attributes
    ``scripts/human_anchor/play_harness.py`` snapshots, so it drops into
    ``play_game`` / ``play_paired`` with no harness change. It has no
    ``start_game``/``advance``, so ``mirror_protocol.seat``/``advance`` skip it.

    Args:
        game: the ``Game`` this bot will be asked to move in (needed for the
            legal-move mask and the turn lookahead).
        preset: ``"current"`` (default) or ``"early"`` — the J10 epochs.
        params: an explicit :class:`JoshuaParams`, overriding ``preset``.
        overrides: knob-name -> value applied on top of the preset. THE
            TOURNAMENT SURFACE — any field of :class:`JoshuaParams` is sweepable
            this way, and the resolved set is recorded in ``manifest`` so a cell
            is self-describing. An unknown knob name raises rather than being
            silently ignored (a typo'd axis would otherwise read as a null).
        seed: accepted for constructor compatibility ONLY. The bot is
            deterministic; no RNG is consulted.
        explain: keep the full term breakdown of the chosen action in
            ``self.last_breakdown``.
    """

    #: telemetry the play harness snapshots per move (this bot has no search)
    _TELEMETRY = ("heur_moves", "exact_moves", "n_timeouts", "solver_secs",
                  "solver_nodes", "neural_moves")

    #: the three axes the 2026-08-12 tournament varies (the owner's answer to the
    #: SPEC's open questions was "test these and see what wins empirically").
    TOURNAMENT_AXES = ("j7_weight", "j8_break_reserve_floor", "j9_avoid_cloisters")

    def __init__(self, game, preset: str = "current",
                 params: JoshuaParams | None = None, seed: int = 0,
                 explain: bool = False, overrides: dict | None = None):
        if params is None:
            if preset not in PRESETS:
                raise ValueError(f"unknown preset {preset!r}; have {sorted(PRESETS)}")
            params = PRESETS[preset]
        self.overrides = dict(overrides or {})
        if self.overrides:
            params = replace(params, **self.overrides)   # raises on an unknown knob
        self.game = game
        self.params = params
        self.preset = params.name
        self.explain = bool(explain)
        del seed                                        # deterministic: never used
        self.latch_k = None
        for k in self._TELEMETRY:
            setattr(self, k, 0)
        self._k0: int | None = None
        #: audit counter — how often each J-term / hard filter actually moved a
        #: decision. `j*` keys count moves where the chosen action carried a
        #: non-zero term; `f_*` keys count moves where a hard filter really cut
        #: the candidate set. J4 is a multiplier and never "fires": read
        #: `last_urgency` instead.
        self.rule_fires: dict[str, int] = {}
        self.last_breakdown: dict | None = None
        self.last_urgency: float | None = None

    # -- manifest ---------------------------------------------------------- #
    @property
    def variant_id(self) -> str:
        """Short, stable label for this variant — the cell name in a tournament.
        Reads the RESOLVED params, so it cannot disagree with what was played."""
        p = self.params
        bits = [p.name, f"j7w{p.j7_weight:g}"]
        if p.j8_break_reserve_floor:
            bits.append("j8brk")
        if p.j9_avoid_cloisters:
            bits.append(f"j9avoid{p.j9_cloister_block_frac:g}"
                        f"s{p.j9_min_surrounding}")
        return "+".join(bits)

    @property
    def manifest(self) -> dict:
        """Recorded verbatim into every ``play_harness`` game log and every H2H
        record. Carries the FULL resolved config (house rule) — never just the
        overrides, so a cell never needs dirname archaeology to interpret."""
        from dataclasses import asdict
        p = self.params
        return {"agent": "joshua_bot", "preset": self.preset,
                "variant_id": self.variant_id, "deterministic": True,
                "axes": {k: getattr(p, k) for k in self.TOURNAMENT_AXES},
                "overrides": dict(self.overrides),
                "params": asdict(p)}

    # -- the decision ------------------------------------------------------- #
    def choose_action(self, board) -> int:
        game = self.game
        state = board.state
        me = int(state.current_player)
        valid = game.get_valid_moves(board)
        legal = [int(i) for i in range(len(valid)) if valid[i]]
        if not legal:
            raise RuntimeError("no legal moves — the game should have ended")
        if self._k0 is None:
            self._k0 = k_remaining(state)
        if len(legal) == 1:                             # PRECEDENCE 0: forced
            return legal[0]

        root_pos = analyze(state)
        clock = Clock(
            k=k_remaining(state), k0=int(self._k0),
            bag_farm_frac=bag_farm_fraction(state),
            my_reserve=int(state.meeples[me]),
            opp_reserve=int(state.meeples[1 - me]),
            margin=float(flat_base_score(state, me, root_pos.decomp)),
        )

        if state.phase.value == "meeples":
            cands = [self._score_meeple(board, root_pos, a, me, clock) for a in legal]
            cands = self._apply_filters(cands, clock)
        else:
            cands = [self._score_tile(board, root_pos, a, me, clock) for a in legal]

        best = self._argmax(cands)
        if self.explain:
            self.last_breakdown = {"action": best.action, "score": best.score,
                                   "terms": dict(best.terms)}
        for name, v in best.terms.items():
            if name != "base" and abs(v) > 1e-9:
                self.rule_fires[name] = self.rule_fires.get(name, 0) + 1
        return best.action

    # -- scoring ------------------------------------------------------------ #
    def _value(self, before: Position, after: Position, me: int,
               clock: Clock) -> dict:
        """``base + SUM(J-terms)`` for one afterstate. Returns the breakdown; the
        caller sums it. Every term is in POINTS from the bot's seat."""
        p = self.params
        urg = j4_urgency(clock, p)
        self.last_urgency = urg          # J4 is a multiplier, not a firing rule
        return {
            "base": after.base(me),
            "j1_majority_steal": j1_majority_steal(after, me, clock, p, urg),
            "j2_farm_attack": j2_farm_attack(after, me, clock, p, urg),
            "j5_dump": j5_dump(before, after, me, clock, p, urg),
            "j6_anchor_roads": j6_anchor_and_roads(after, me, clock, p, urg),
            "j7_close_vs_farm": j7_close_vs_farm(after, me, p),
            "j8_overcommit": j8_overcommit(after, me, clock, p, urg),
        }

    def _score_meeple(self, board, before: Position, action: int, me: int,
                      clock: Clock) -> _Cand:
        game = self.game
        nb, _ = game.get_next_state(board, action)
        after = analyze(nb.state)
        terms = self._value(before, after, me, clock)
        cand = _Cand(action=action, score=sum(terms.values()), terms=terms,
                     after=after)
        self._tag_meeple(cand, board, action, me, clock)
        return cand

    def _score_tile(self, board, before: Position, action: int, me: int,
                    clock: Clock) -> _Cand:
        """A TILE move is scored as a whole TURN: the placement PLUS the best
        meeple follow-up it enables. Without this the bot cannot see a J1 join or
        a J2 farm entry, because both are a tile move and a meeple move.

        The follow-up is scored against the SAME ``before`` (the root, pre-tile
        position), so J5 — the one before/after term — prices the whole turn:
        what the TILE fed, not what the meeple did."""
        game = self.game
        nb, _ = game.get_next_state(board, action)
        after = analyze(nb.state)
        terms = self._value(before, after, me, clock)
        score = sum(terms.values())
        if self.params.tile_lookahead and nb.state.phase.value == "meeples" \
                and int(nb.state.current_player) == me:
            follow = self._best_meeple_followup(nb, before, me, clock)
            if follow is not None:
                terms, score = follow.terms, follow.score
                after = follow.after
        return _Cand(action=action, score=score, terms=terms, after=after)

    def _best_meeple_followup(self, nb, before: Position, me: int,
                              clock: Clock) -> _Cand | None:
        game = self.game
        try:
            valid = game.get_valid_moves(nb)
        except Exception:                               # noqa: BLE001 window overflow
            return None
        legal = [int(i) for i in range(len(valid)) if valid[i]]
        if not legal:
            return None
        cands = [self._score_meeple(nb, before, a, me, clock) for a in legal]
        cands = self._apply_filters(cands, clock, count=False)
        return self._argmax(cands)

    # -- candidate tagging (what the hard filters need to know) -------------- #
    def _tag_meeple(self, cand: _Cand, board, action: int, me: int,
                    clock: Clock) -> None:
        """Decode the meeple action and record everything the hard filters ask:
        is it a placement at all, is it a FARMER (F-J10), is it a CLOISTER and are
        its completion prospects strong (F-J9), does the feature it lands on
        finish this turn / tie-or-take a feature he already holds (F-J3), and is
        it a pivotal-feature overcommit (F-J3's ``j8_break_reserve_floor``
        exemption — decided by J8's OWN per-component predicate, never by a
        re-statement of it)."""
        state = board.state
        w = self.game.window_size
        if action >= meeple_pass_index(w):
            return                                      # PASS
        cand.is_meeple_place = True
        cand.is_farmer = meeple_farmer_base(w) <= action < meeple_pass_index(w)
        act = decode(action, off=board.offset, phase=state.phase.value,
                     next_tile=state.next_tile,
                     last_tile_coord=(state.last_tile_action.coordinate
                                      if state.last_tile_action is not None else None))
        cws = getattr(act, "coordinate_with_side", None)
        if cws is None:
            return
        r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
        d = cand.after.decomp
        opp = 1 - me
        tile = cand.after.state.board[r][c]
        if tile is None:
            return
        terrain = tile.get_type(side)
        p = self.params
        pivotal = None
        if terrain == TerrainType.CITY:
            root = d.city_side_root.get((r, c, side))
            counts, finished = cand.after.city_counts, d.city_root_finished
            pivotal = j8_city_term
        elif terrain == TerrainType.ROAD:
            root = d.road_side_root.get((r, c, side))
            counts, finished = cand.after.road_counts, d.road_root_finished
        elif terrain in _CLOISTER_TERRAIN:
            # A cloister has no majority contest, but it IS the J9 decision.
            cand.is_cloister = True
            cand.cloister_strong = (
                surrounding_count(cand.after.state.board, r, c) >= p.j9_min_surrounding)
            return
        else:
            root = d.farm_pos0_root.get((r, c, side))
            counts, finished = cand.after.farm_counts, {}
            pivotal = j8_farm_term
        if root is None:
            return
        cand.closes_own = bool(finished.get(root, False))
        cnt = counts.get(root)
        if cnt and cnt[opp] >= 1 and cnt[me] >= cnt[opp]:
            cand.swings_majority = True
        if pivotal is not None and cnt:
            # urg is a strictly positive multiplier, so it cannot change the sign;
            # 1.0 keeps the tag a pure predicate.
            cand.is_pivotal_overcommit = pivotal(
                cand.after, root, cnt, me, clock, p, 1.0) > 0.0

    # -- hard filters (PRECEDENCE 2) ----------------------------------------- #
    def _apply_filters(self, cands: list[_Cand], clock: Clock,
                       count: bool = True) -> list[_Cand]:
        """Applied IN THIS ORDER; a filter that would empty the set is skipped.

        F-END  endgame deployment — with ``k_remaining <= my reserve`` an unplaced
               meeple is wasted points, so PASS is dropped. **Overrides J3.**
        F-J10  early-farmer block — no FARMER claim while more than
               ``early_farm_block_frac`` of the bag is left (the J10 "current"
               epoch's stated adaptation; ``early`` sets the fraction to 0).
        F-J9   cloister caution (OPT-IN, ``j9_avoid_cloisters``) — no CLOISTER
               claim while more than ``j9_cloister_block_frac`` of the bag is
               left, UNLESS its 3x3 already holds ``j9_min_surrounding`` tiles
               (strong completion prospects). "he is good at blocking my cloister
               completions. i'm more cautious about grabbing them now."
        F-J3   own-reserve floor — do not spend down to below
               ``j3_reserve_floor`` unless the meeple comes straight back
               (a closure) or the placement is a majority swing — or, when
               ``j8_break_reserve_floor`` is ON, unless it is a pivotal-feature
               overcommit ("you have to take chances").
        """
        p = self.params
        out = cands
        endgame = clock.k <= clock.my_reserve

        def _keep(name: str, kept: list[_Cand], out: list[_Cand]) -> list[_Cand]:
            """Apply a filter unless it would empty the set; count real bites.

            ``count`` is False inside the tile-phase lookahead — that call runs
            once per candidate tile, so counting there would report hundreds of
            "fires" per move and make the audit counter meaningless."""
            if kept and len(kept) < len(out):
                if count:
                    self.rule_fires[name] = self.rule_fires.get(name, 0) + 1
                return kept
            return out

        if endgame:                                                        # F-END
            out = _keep("f_end_deploy", [c for c in out if c.is_meeple_place], out)
        # frac <= 0 means the block is OFF entirely (the "early" epoch), NOT
        # "block always": `k > 0` is true on every turn of the game.
        if (p.early_farm_block_frac > 0.0
                and clock.k > p.early_farm_block_frac * max(clock.k0, 1)):  # F-J10
            out = _keep("f_j10_early_farm_block",
                        [c for c in out if not c.is_farmer], out)
        if (p.j9_avoid_cloisters
                and clock.k > p.j9_cloister_block_frac * max(clock.k0, 1)):  # F-J9
            out = _keep("f_j9_cloister_caution",
                        [c for c in out
                         if (not c.is_cloister) or c.cloister_strong], out)
        if (not endgame and clock.k > p.j3_endgame_release_k
                and clock.my_reserve <= p.j3_reserve_floor):               # F-J3
            out = _keep("f_j3_reserve_floor",
                        [c for c in out if (not c.is_meeple_place)
                         or c.closes_own or c.swings_majority
                         or (p.j8_break_reserve_floor and c.is_pivotal_overcommit)],
                        out)
        return out

    # -- deterministic argmax (PRECEDENCE 3) --------------------------------- #
    def _argmax(self, cands: Iterable[_Cand]) -> _Cand:
        """Highest rounded score; ties break on the LOWEST action index. No RNG."""
        nd = self.params.score_round
        best = None
        best_key = None
        for c in cands:
            key = (round(c.score, nd), -c.action)
            if best_key is None or key > best_key:
                best, best_key = c, key
        if best is None:
            raise RuntimeError("no candidate actions to choose from")
        return best


def make_joshua_bot(game, preset: str = "current", **kw) -> JoshuaBot:
    """Factory mirroring ``champion_factory.make_production_champion``'s shape so
    a harness can build either from the same call site."""
    return JoshuaBot(game, preset=preset, **kw)


def with_overrides(preset: str, **overrides) -> JoshuaParams:
    """A preset with named knobs replaced — for sweeps and for the tests that
    need one rule isolated (e.g. every weight but J1 zeroed)."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; have {sorted(PRESETS)}")
    return replace(PRESETS[preset], **overrides)
