#!/usr/bin/env python3
"""S0v2 — THE SCRIPTED EXPLOITER.  ⛔ MEASUREMENT INSTRUMENT, NEVER A CANDIDATE.

An opponent agent that CARRIES the owner's multi-ply invasion plan explicitly
instead of hoping PUCT finds it.  It wraps a base agent (the champion of record)
and overrides its move only when the plan module fires; every other ply is the
base agent's own move, byte for byte.

⛔ **S0v2 MUST NEVER BE ADOPTED INTO PRODUCTION.**  See DESIGN.md §0.  It is
built to express ONE mechanism, not to play well; its margin against the
champion is not evidence about any leaf term or any search knob.

THE MECHANISM (measurement/e4_exploit_grading_20260825/, Stage-A census)
-----------------------------------------------------------------------
A "deliberate invasion" is a *census event*, and this module targets that exact
definition rather than a paraphrase of it.  From ``s0_signature.py`` +
``stage_a_census.py`` §H2, an event is counted for player P iff, at the ply P
moved:

  * a feature component becomes contested for the FIRST time (both seats hold
    meeples on one component);
  * the pre-ply split of that component into meepled sub-components has >= 2
    occupied parts, with P's parts holding STRICTLY FEWER tiles than the
    opponent's parts (ties -> ``merge_equal`` -> invader is None -> NOT counted);
  * the actor of that ply is P.

Because a meeple may only be placed on the tile just played, and the engine
forbids claiming an occupied feature, the ONLY way to author that event is:

    1. FOOTHOLD  — claim a small (<= stub_max_tiles) component of your own that
                   sits one empty cell away from a larger opponent-held one;
    2. MERGE     — later, place the tile that joins them.

and, because step 1 can only happen on a tile you just played:

    0. SETUP     — play a tile whose own fresh, unclaimed segment is that small
                   component next to the victim.

The three fires below are exactly those three steps.  Step 2 is the one the
config-only S0 could not buy: its plans STARTED (47 onsets at alpha 0.90) but
COMPLETED at 28/47, because a depth-0 leaf term makes the first move attractive
and never carries the plan.  A script carries it by construction.

DETERMINISM.  Every plan decision is a pure function of the engine state and the
frozen ``PlanConfig`` — candidate ordering is by (score, action index) with the
lowest action index winning ties, and no RNG is consulted anywhere in this
module.  ``seed`` is carried for provenance and for the base agent only.  A pure
function of state is a fortiori a function of (state, seed);
``test_s0v2_agent.py::test_determinism_*`` pins it.

NO src/ OR engine/ FILE IS TOUCHED.  Everything here reads the production
structural kernel (``flat_leaf.decompose``) and the production leaf
(``flat_leaf.flat_virtual_score_v2_float``) through their public entry points.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np

from carcassonne_ai import action_space, flat_leaf
from wingedsheep.carcassonne.objects.game_phase import GamePhase
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType

_DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))

CLS_CITY = "city"
CLS_ROAD = "road"
CLS_FARM = "farm"


# --------------------------------------------------------------------------- #
# configuration                                                                 #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PlanConfig:
    """The scripted plan's knobs.  Defaults are read off the Stage-A anatomy.

    ``stub_max_tiles`` 3        owner's measured mean foothold is 2.75 tiles
    ``victim_min_tiles`` 5      owner's measured mean victim is 8.29 tiles; 5 is
                                the floor at which a merge is worth authoring
    ``victim_min_pts`` 4        a cosmetic invasion (a stub merged onto something
                                worth nothing) is what G-DAMAGE exists to catch
    ``*_leaf_tolerance``        max depth-0 production-leaf points the fire may
                                give up against the BASE AGENT'S OWN move.  The
                                foothold tolerance is deliberately generous: the
                                leaf DEMOTING the stub claim is the documented
                                reason the champion never learned this (DESIGN
                                §1 of measurement/s0_exploiter_prep), so a tight
                                tolerance would veto exactly the target move.
                                MERGE is never leaf-filtered — it IS the exploit.
    ``ply_frac_*``              the owner merges at mean ply fraction 0.47; the
                                window keeps the script out of the opening (where
                                a wasted meeple is most expensive) and out of the
                                dead endgame (where a claim cannot pay).
    """

    stub_max_tiles: int = 3
    victim_min_tiles: int = 5
    victim_min_pts: int = 4

    merge_enabled: bool = True
    foothold_enabled: bool = True
    setup_enabled: bool = True

    # The PRIMARY competitiveness gate: a SETUP/FOOTHOLD override must be a move
    # the base agent's OWN search took seriously — at least this share of the
    # top action's pooled root visits.  0.0 disables.  Measured 2026-08-28: the
    # depth-0 leaf tolerance alone is NOT a competitiveness gate against a
    # searching base (the champion's chosen move often has a LOW depth-0 leaf,
    # which makes `base_leaf` a weak bar and lets bad overrides through) — an
    # 8-game calibration read -27.1 pts/game with the leaf gate alone.
    min_visit_share: float = 0.10
    # SECONDARY sanity bound, in depth-0 production-leaf points, against the base
    # agent's own move.  Deliberately generous: the leaf DEMOTING the stub claim
    # is the documented reason the champion never learned this mechanism
    # (measurement/s0_exploiter_prep/DESIGN.md §1), so a tight leaf bar would
    # veto exactly the target move.  MERGE is never gated at all — it IS the
    # exploit, and the merge-only arm measured FREE (+8.4 pts/game, n=8).
    setup_leaf_tolerance: float = 6.0
    foothold_leaf_tolerance: float = 8.0

    ply_frac_min: float = 0.10
    ply_frac_max: float = 0.92

    # SETUP is the expensive fire (it overrides a TILE choice, the
    # highest-leverage decision on the board) and the 8-game calibration priced
    # it at ~14 pts/game for ~+0.25 merges/game.  These three knobs exist to buy
    # the same opportunities more cheaply: only set up against a WORTHWHILE
    # victim, only when the stub would have more than one cell to merge through,
    # and never more than a bounded number of times per game.
    setup_victim_min_pts: int = 6
    setup_min_merge_cells: int = 2
    max_setup_fires: int = 6

    # ---- the MAJORITY fire (AMENDMENT 2026-08-28, DESIGN.md §4.1) ----------- #
    # The first smoke's finding: S0v2's invasions TIE and the owner's take a
    # MAJORITY (owner `invader_took_all` 28.9 % vs S0V2-F 9.3 %; owner
    # out-numbers the incumbent in 26 of 90 invasions, S0V2-F in 5 of 54).
    # Because the engine forbids placing a meeple on an OCCUPIED feature, a
    # majority can only be built by merging a SECOND owned part into the
    # contested one — so MAJORITY is a tile-phase fire, fed by a REINFORCE
    # foothold/setup that claims that second part.
    majority_enabled: bool = True
    reinforce_enabled: bool = True
    majority_min_pts: int = 4        # never flip a worthless feature (G-DAMAGE's
                                     # own caveat, applied to this fire)
    # Meeple economy.  A reinforcement spends a SECOND meeple on a feature
    # already committed — the exact trade H3' is about — so it keeps the
    # search-grounded gate AND two scarcity guards the other fires do not have.
    max_open_reinforcements: int = 2
    min_meeples_for_reinforce: int = 2   # never spend the LAST meeple reinforcing
    reinforce_stub_max_tiles: int = 3

    farm_pref: float = 1.5          # rank farms first (owner's steal is farm-heavy)
    min_meeples_for_foothold: int = 1
    max_scan_actions: int = 128     # hard cost guard on the tile-phase scan

    seed: int = 0                   # provenance / base agent only; unused here

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def parse_overrides(pairs, base: dict | None = None) -> PlanConfig:
    """``["stub_max_tiles=4", "setup_enabled=false"]`` -> PlanConfig.

    Types come from the dataclass's own field types, so a typo in a name or a
    value fails loudly instead of being silently ignored."""
    types = {f.name: f.type for f in dataclasses.fields(PlanConfig)}
    kw = dict(base or {})
    for p in pairs or ():
        if "=" not in p:
            raise ValueError(f"expected key=value, got {p!r}")
        k, v = p.split("=", 1)
        k = k.strip()
        if k not in types:
            raise ValueError(f"unknown PlanConfig field {k!r}")
        t = types[k]
        tn = t if isinstance(t, str) else getattr(t, "__name__", str(t))
        if tn.startswith("bool"):
            kw[k] = str(v).strip().lower() in ("1", "true", "yes", "on")
        elif tn.startswith("int"):
            kw[k] = int(v)
        elif tn.startswith("float"):
            kw[k] = float(v)
        else:
            kw[k] = v
    return PlanConfig(**kw)


# --------------------------------------------------------------------------- #
# structural helpers — all reads, all off the production kernel                  #
# --------------------------------------------------------------------------- #
def _farm_coords(decomp) -> dict:
    """farm root -> set of distinct (r, c).  Mirrors stage_a_census.snapshot's
    farm_coords, which is built from ``farm_anypos_root``."""
    out: dict = {}
    for (r, c, _pos), root in decomp.farm_anypos_root.items():
        s = out.get(root)
        if s is None:
            out[root] = s = set()
        s.add((r, c))
    return out


class Structure:
    """One ply's structural view: components, their sizes/values, meeple counts.

    A component KEY is ``(cls, root)``.  Roots are per-decomposition integers and
    are NOT stable across plies — every cross-ply comparison in this module goes
    through positional meeple keys, never through roots.
    """

    __slots__ = ("state", "board", "decomp", "farm_coords", "counts",
                 "members", "of_meeple", "_adj_empty", "H", "W")

    def __init__(self, state, decomp=None):
        self.state = state
        self.board = state.board
        self.H = len(self.board)
        self.W = len(self.board[0]) if self.H else 0
        self.decomp = decomp if decomp is not None else flat_leaf.decompose(state)
        self.farm_coords = _farm_coords(self.decomp)
        self.counts: dict = {}      # key -> [w0, w1]
        self.members: dict = {}     # key -> [meeple positional key, ...]
        self.of_meeple: dict = {}   # meeple positional key -> key
        self._adj_empty: dict = {}
        self._index_meeples()

    # -- meeples ----------------------------------------------------------- #
    def _index_meeples(self) -> None:
        d = self.decomp
        board = self.board
        for player in range(self.state.players):
            for mp in self.state.placed_meeples[player]:
                cws = mp.coordinate_with_side
                r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
                tile = board[r][c]
                terrain = tile.get_type(side)
                key = None
                if terrain == TerrainType.CITY:
                    root = d.city_side_root.get((r, c, side))
                    key = None if root is None else (CLS_CITY, root)
                elif terrain == TerrainType.ROAD:
                    root = d.road_side_root.get((r, c, side))
                    key = None if root is None else (CLS_ROAD, root)
                elif terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                    key = None          # cloister: never a contestable component
                elif mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                    root = d.farm_anypos_root.get((r, c, side))
                    key = None if root is None else (CLS_FARM, root)
                if key is None:
                    continue
                mkey = (player, r, c, getattr(side, "name", str(side)),
                        mp.meeple_type.name)
                w = flat_leaf._meeple_weight(mp.meeple_type)
                cnt = self.counts.get(key)
                if cnt is None:
                    self.counts[key] = cnt = [0, 0]
                cnt[player] += w
                self.members.setdefault(key, []).append(mkey)
                self.of_meeple[mkey] = key

    # -- component facts ---------------------------------------------------- #
    def coords(self, key) -> set:
        cls, root = key
        if cls == CLS_CITY:
            return self.decomp.city_root_coords.get(root, set())
        if cls == CLS_ROAD:
            return self.decomp.road_root_coords.get(root, set())
        return self.farm_coords.get(root, set())

    def n_tiles(self, key) -> int:
        return len(self.coords(key))

    def finished(self, key) -> bool:
        cls, root = key
        if cls == CLS_CITY:
            return bool(self.decomp.city_root_finished.get(root, False))
        if cls == CLS_ROAD:
            return bool(self.decomp.road_root_finished.get(root, False))
        return False                       # a field is never "finished"

    def potential_pts(self, key) -> int:
        """What the feature is worth to whoever holds it when it finally scores.

        city/road: the closed value (== census `pts_if_closed`).
        farm:      3 x the number of DISTINCT adjacent city components, finished
                   or not — the field's potential, not its value today.
        """
        cls, root = key
        if cls == CLS_CITY:
            return flat_leaf._city_points(
                self.decomp.city_root_coords.get(root, set()), True, self.board)
        if cls == CLS_ROAD:
            return flat_leaf._road_points(
                self.decomp.road_root_coords.get(root, set()), True, self.board)
        return 3 * len(self.decomp.farm_root_adj_city_roots.get(root, ()))

    def adj_empty(self, key) -> set:
        """Empty board cells orthogonally adjacent to a tile of the component.

        A single tile placement can only join two components if it lands in a
        cell adjacent to a tile of each — so the intersection of two components'
        ``adj_empty`` sets is exactly the set of cells where a one-tile merge
        could happen.  Necessary, not sufficient (the tile must also carry the
        right terrain), which is why the MERGE fire re-derives the event exactly
        from the child decomposition rather than trusting this.
        """
        got = self._adj_empty.get(key)
        if got is not None:
            return got
        board, H, W = self.board, self.H, self.W
        out = set()
        for (r, c) in self.coords(key):
            for dr, dc in _DIRS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < H and 0 <= nc < W and board[nr][nc] is None:
                    out.add((nr, nc))
        self._adj_empty[key] = out
        return out

    # -- roles -------------------------------------------------------------- #
    def held_by(self, key, player: int) -> bool:
        c = self.counts.get(key)
        return bool(c) and c[player] > 0

    def exclusively(self, key, player: int) -> bool:
        c = self.counts.get(key)
        return bool(c) and c[player] > 0 and c[1 - player] == 0

    def victims_of(self, opp: int, cfg: PlanConfig) -> list:
        """Opponent-held components that are worth invading."""
        out = []
        for key in self.counts:
            if not self.exclusively(key, opp):
                continue
            if self.finished(key):
                continue
            if self.n_tiles(key) < cfg.victim_min_tiles:
                continue
            if self.potential_pts(key) < cfg.victim_min_pts:
                continue
            out.append(key)
        return out

    def majority_targets(self, me: int, cfg: PlanConfig) -> list:
        """CONTESTED components where I am TIED OR BEHIND — the MAJORITY fire's
        targets.

        Under the vendored full-points-on-tie rule a 1-v-1 tie pays the incumbent
        in FULL, so an invasion that only ties denies nothing; the census's
        `farmer-deployment-scores-ZERO` counter (G-DAMAGE's statistic) moves only
        when the incumbent LOSES the majority.  These are the features where one
        more of my meeples would flip that."""
        opp = 1 - me
        out = []
        for key, c in self.counts.items():
            if c[me] <= 0 or c[opp] <= 0:
                continue
            if c[me] > c[opp]:
                continue                       # already mine on majority
            if self.finished(key):
                continue
            if self.potential_pts(key) < cfg.majority_min_pts:
                continue
            out.append(key)
        return out


def kind_tel(kind: str) -> str:
    """Telemetry prefix for a meeple-phase candidate kind."""
    return "reinforce" if kind == "reinforce" else "foothold"


def _share(visits, action: int) -> float:
    """The base search's visit share for `action`, 0.0 when the gate is off."""
    if not visits:
        return 0.0
    vmax = max(visits.values())
    return (visits.get(int(action), 0.0) / vmax) if vmax > 0 else 0.0


def victim_rank(struct: Structure, key, cfg: PlanConfig) -> float:
    """Ranking score for a victim: its potential points, farms preferred."""
    pts = float(struct.potential_pts(key))
    if key[0] == CLS_FARM:
        pts *= cfg.farm_pref
    return pts


def merge_plausible(struct: Structure, a_key, b_key) -> bool:
    """Is there a single empty cell that touches both components?"""
    if a_key[0] != b_key[0]:
        return False
    return bool(struct.adj_empty(a_key) & struct.adj_empty(b_key))


# --------------------------------------------------------------------------- #
# the census event, re-derived exactly                                          #
# --------------------------------------------------------------------------- #
def invasion_events(pre: Structure, post: Structure) -> list:
    """Deliberate-invasion events created between `pre` and `post`.

    Returns a list of dicts ``{invader, incumbent, cls, invader_tiles,
    incumbent_tiles, victim_pts, post_key, parts}``.  This reproduces
    ``stage_a_census.py`` H2's ``mech == "merge"`` branch and
    ``s0_signature.py``'s DELIBERATE test (actor == invader) — the caller
    supplies the actor by only ever evaluating its OWN candidate moves.

    Note on "first time contested": the census keys on a global union-find id
    and skips a feature it has already seen contested.  Components only ever
    grow or merge, so a feature that was contested earlier still contains both
    seats' meeples in ONE pre-component — which the ``both seats in one part``
    guard below rejects.  The two conditions are therefore equivalent.
    """
    events = []
    for key, counts in post.counts.items():
        if counts[0] <= 0 or counts[1] <= 0:
            continue
        parts: dict = {}
        for mkey in post.members.get(key, ()):
            pkey = pre.of_meeple.get(mkey)
            if pkey is None:
                continue
            parts[pkey] = pre.counts.get(pkey, [0, 0])
        if len(parts) < 2:
            continue
        if any(c[0] > 0 and c[1] > 0 for c in parts.values()):
            continue                       # already contested before this ply
        s0 = [k for k, c in parts.items() if c[0] > 0 and c[1] == 0]
        s1 = [k for k, c in parts.items() if c[1] > 0 and c[0] == 0]
        if not s0 or not s1:
            continue
        t0 = sum(pre.n_tiles(k) for k in s0)
        t1 = sum(pre.n_tiles(k) for k in s1)
        if t0 == t1:
            continue                       # census `merge_equal`: invader is None
        invader, incumbent = (0, 1) if t0 < t1 else (1, 0)
        events.append({
            "invader": invader,
            "incumbent": incumbent,
            "cls": key[0],
            "invader_tiles": min(t0, t1),
            "incumbent_tiles": max(t0, t1),
            "victim_pts": post.potential_pts(key),
            "post_key": key,
            "invader_parts": [list(k) for k in (s0 if invader == 0 else s1)],
            "stub_meeples": sorted(
                mkey for k in (s0 if invader == 0 else s1)
                for mkey in pre.members.get(k, ())),
        })
    return events


def majority_events(pre: Structure, post: Structure, me: int) -> list:
    """MAJORITY events created for `me` between `pre` and `post`.

    A majority event is a merge after which **I strictly out-number the opponent
    on a contested component, and did not already out-number them on any of its
    parts.**  Two sub-kinds, both counted, distinguished by ``from_tie``:

      * ``from_tie=True``  — a part was already contested with me TIED OR BEHIND
        and the merge flips it.  This is the conversion the first smoke's
        finding (1) named: a `shared_tie` becomes an `invader_took_all`.
      * ``from_tie=False`` — two of my own parts and one of theirs join in the
        same ply, landing 2-v-1 immediately.  The census also counts this as a
        deliberate INVASION, so the two telemetry counters overlap by
        construction and the read-out says so.

    Why this is the only route: the engine forbids placing a meeple on a feature
    the opponent already occupies, so a second meeple can NEVER be added to a
    contested feature by placement — only by merging a separately-claimed part
    in.  ``s0v2_agent`` therefore has no "reinforce in place" fire and cannot
    have one.
    """
    opp = 1 - me
    events = []
    for key, counts in post.counts.items():
        if counts[me] <= counts[opp] or counts[opp] <= 0:
            continue
        parts: dict = {}
        for mkey in post.members.get(key, ()):
            pkey = pre.of_meeple.get(mkey)
            if pkey is None:
                continue
            parts[pkey] = pre.counts.get(pkey, [0, 0])
        if len(parts) < 2:
            continue                           # no merge happened this ply
        if any(c[me] > c[opp] and c[opp] > 0 for c in parts.values()):
            continue                           # I already held the majority
        contested_pre = [c for c in parts.values() if c[me] > 0 and c[opp] > 0]
        events.append({
            "cls": key[0],
            "post_key": key,
            "me_after": counts[me], "opp_after": counts[opp],
            "from_tie": bool(contested_pre),
            "victim_pts": post.potential_pts(key),
            # MY meeples only — a part that was already contested carries the
            # opponent's meeple too, and the ledger matches plans on the
            # FOOTHOLD meeple, which is always one of mine.
            "my_meeples": sorted(
                mkey for k, c in parts.items() if c[me] > 0
                for mkey in pre.members.get(k, ()) if mkey[0] == me),
        })
    return events


# --------------------------------------------------------------------------- #
# the plan ledger (the state machine the tests pin)                             #
# --------------------------------------------------------------------------- #
@dataclass
class Plan:
    pid: int
    ply: int
    cls: str
    stub_meeple: tuple            # positional key of the claiming meeple
    victim_meeple: tuple          # positional key of one incumbent meeple
    victim_tiles: int
    victim_pts: int
    kind: str = "invade"          # invade (foothold -> merge) | reinforce
                                  #                             (2nd part -> majority)
    status: str = "open"          # open | completed | abandoned
    closed_ply: int | None = None
    reason: str | None = None


class PlanLedger:
    """Tracks foothold -> merge.  ``completion_rate`` is the number the config-only
    S0 could not move (its plans started at 47/game-set and completed at 28)."""

    def __init__(self):
        self.plans: list = []
        self._next = 0

    def open_plans(self) -> list:
        return [p for p in self.plans if p.status == "open"]

    def start(self, ply: int, cls: str, stub_meeple, victim_meeple,
              victim_tiles: int, victim_pts: int, kind: str = "invade") -> Plan:
        p = Plan(pid=self._next, ply=ply, cls=cls, stub_meeple=tuple(stub_meeple),
                 victim_meeple=tuple(victim_meeple), victim_tiles=int(victim_tiles),
                 victim_pts=int(victim_pts), kind=kind)
        self._next += 1
        self.plans.append(p)
        return p

    def open_of_kind(self, kind: str) -> list:
        return [p for p in self.plans if p.status == "open" and p.kind == kind]

    def complete(self, ply: int, stub_meeples) -> list:
        """Close every open plan whose foothold meeple took part in this merge."""
        s = {tuple(m) for m in stub_meeples}
        hit = []
        for p in self.open_plans():
            if p.stub_meeple in s:
                p.status, p.closed_ply, p.reason = "completed", ply, "merged"
                hit.append(p)
        return hit

    def refresh(self, ply: int, struct: Structure, me: int) -> None:
        """Abandon plans whose foothold or victim no longer exists."""
        for p in self.open_plans():
            if p.stub_meeple not in struct.of_meeple:
                p.status, p.closed_ply, p.reason = "abandoned", ply, "stub_gone"
            elif p.victim_meeple not in struct.of_meeple:
                p.status, p.closed_ply, p.reason = "abandoned", ply, "victim_gone"
            elif struct.of_meeple[p.stub_meeple] == struct.of_meeple[p.victim_meeple]:
                # merged by someone/something else — not OUR deliberate invasion
                p.status, p.closed_ply, p.reason = "abandoned", ply, "merged_not_by_plan"

    def summary(self) -> dict:
        started = len(self.plans)
        done = sum(1 for p in self.plans if p.status == "completed")
        aband = sum(1 for p in self.plans if p.status == "abandoned")
        out = {
            "plans_started": started,
            "plans_completed": done,
            "plans_abandoned": aband,
            "plans_open_at_end": started - done - aband,
            "plan_completion_rate": (done / started) if started else None,
        }
        for kind in ("invade", "reinforce"):
            ks = [p for p in self.plans if p.kind == kind]
            kd = sum(1 for p in ks if p.status == "completed")
            out[f"{kind}_plans_started"] = len(ks)
            out[f"{kind}_plans_completed"] = kd
            out[f"{kind}_plan_completion_rate"] = (kd / len(ks)) if ks else None
        return out


# --------------------------------------------------------------------------- #
# the agent                                                                     #
# --------------------------------------------------------------------------- #
class ScriptedExploiter:
    """``base`` agent, overridden by the plan module.  Mirror-protocol compatible.

    The harness contract (``eval_fair_puct._drives_mirror``) is ``start_game`` +
    ``advance``; both forward to the base agent, so the base's rust mirror is
    advanced with the action actually PLAYED — including on plies this class
    overrode.  ``move`` is the only method with behaviour of its own.
    """

    def __init__(self, base, game, cfg: PlanConfig | None = None,
                 leaf_cfg=None, seed: int = 0, label: str = "S0v2"):
        self.base = base
        self.game = game
        self.cfg = cfg or PlanConfig()
        self.leaf_cfg = leaf_cfg
        self.seed = int(seed)
        self.label = label
        self.ledger = PlanLedger()
        self.fires: list = []
        self.tel = {
            "plies_seen": 0, "base_moves": 0,
            "merge_fires": 0, "merge_candidates_seen": 0,
            "setup_fires": 0, "setup_candidates_seen": 0, "setup_vetoed_by_leaf": 0,
            "foothold_fires": 0, "foothold_candidates_seen": 0,
            "foothold_vetoed_by_leaf": 0,
            "setup_vetoed_by_visits": 0, "foothold_vetoed_by_visits": 0,
            "override_declined_no_visits": 0,
            "scan_plies": 0, "leaf_evals": 0,
            # ---- the MAJORITY fire (amendment 2026-08-28) ------------------- #
            "majority_fires": 0, "majority_candidates_seen": 0,
            "majority_from_tie": 0,
            "reinforce_foothold_fires": 0, "reinforce_candidates_seen": 0,
            "reinforce_vetoed_by_visits": 0, "reinforce_vetoed_by_leaf": 0,
            "reinforce_setup_fires": 0,
            "meeples_spent_on_reinforcement": 0,
        }
        self._ply = 0

    # -- mirror protocol (pure forwarding) --------------------------------- #
    # Forwarded only when the base OWNS a mirror.  A mirror-free base (the dev
    # harness's greedy leaf) needs neither call, but this class must still
    # expose both so `eval_fair_puct._drives_mirror` sees the rust champion
    # underneath and the harness advances it on EVERY applied action, including
    # the plies this class overrode.
    def start_game(self, board) -> None:
        if hasattr(self.base, "start_game"):
            self.base.start_game(board)

    def advance(self, action: int, board_after=None) -> None:
        self._ply += 1
        if not hasattr(self.base, "advance"):
            return
        if board_after is not None:
            self.base.advance(int(action), board_after)
        else:
            self.base.advance(int(action))

    def close(self) -> None:
        if hasattr(self.base, "close"):
            self.base.close()

    # -- search-grounded plausibility gate ---------------------------------- #
    def _visits(self):
        """The base agent's pooled ROOT VISITS for the decision it just made.

        ``RustFairAgent.last_pooled_visits`` is ``{action: visits}`` for the last
        ``choose_action``; it is EMPTY when the exact endgame solver owned the
        move (there was no PIMC search to read).  A base with no such property
        (the dev harness's greedy leaf) returns None == gate off."""
        v = getattr(self.base, "last_pooled_visits", None)
        if v is None:
            return None
        try:
            return {int(a): float(n) for a, n in dict(v).items()}
        except Exception:
            return None

    def _visit_ok(self, visits, action: int) -> bool:
        if not self.cfg.min_visit_share or visits is None:
            return True
        if not visits:
            return False                   # solver-owned decision: never override
        vmax = max(visits.values())
        if vmax <= 0:
            return False
        return (visits.get(int(action), 0.0) / vmax) >= self.cfg.min_visit_share

    # -- leaf helper -------------------------------------------------------- #
    def _leaf(self, board, action: int, me: int) -> float:
        child, _ = self.game.get_next_state(board, int(action))
        self.tel["leaf_evals"] += 1
        return flat_leaf.flat_virtual_score_v2_float(child.state, me, self.leaf_cfg)

    # -- the decision ------------------------------------------------------- #
    def move(self, board) -> int:
        st = board.state
        me = int(st.current_player)
        self.tel["plies_seen"] += 1
        cfg = self.cfg

        pre = Structure(st)
        self.ledger.refresh(self._ply, pre, me)

        frac = self._ply_frac(board)
        in_window = cfg.ply_frac_min <= frac <= cfg.ply_frac_max

        if st.phase == GamePhase.TILES:
            act = self._tile_move(board, st, pre, me, in_window)
        else:
            act = self._meeple_move(board, st, pre, me, in_window)
        if act is None:
            self.tel["base_moves"] += 1
            return int(self.base.move(board))
        return int(act)

    def _ply_frac(self, board) -> float:
        """Fraction of the game's tiles already on the board.

        ``board.total_tiles`` is the game's tile TOTAL (72 in base) and
        ``board.tile_count`` the number placed, so this is the natural analogue
        of the census's ``ply_frac`` (the owner's mean merge lands at 0.47)."""
        tot = max(1, int(board.total_tiles))
        return min(1.0, int(board.tile_count) / float(tot))

    # ---------------------------------------------------------------- TILES #
    def _tile_move(self, board, st, pre: Structure, me: int, in_window: bool):
        cfg = self.cfg
        opp = 1 - me
        if not (cfg.merge_enabled or cfg.majority_enabled
                or (cfg.setup_enabled and in_window)):
            return None

        victims = pre.victims_of(opp, cfg)
        majors = pre.majority_targets(me, cfg) if cfg.majority_enabled else []
        # The MERGE scan uses a WIDER victim set than the plan does.  The plan's
        # `victims_of` bar (>= victim_min_tiles) decides where it is worth
        # SPENDING a meeple; a merge spends nothing but the tile, and the census
        # counts the event whenever my parts hold strictly fewer tiles — so any
        # opponent-exclusive, unfinished, non-cosmetic component is a target, and
        # any of my own components (not only stubs) can be the smaller side.
        merge_targets = [k for k in pre.counts
                         if pre.exclusively(k, opp) and not pre.finished(k)
                         and pre.potential_pts(k) >= cfg.victim_min_pts]
        my_comps = [k for k in pre.counts if pre.exclusively(k, me)]
        merge_cells: set = set()
        if cfg.merge_enabled:
            for sk in my_comps:
                sn = pre.n_tiles(sk)
                for vk in merge_targets:
                    if vk[0] != sk[0] or pre.n_tiles(vk) <= sn:
                        continue
                    merge_cells |= (pre.adj_empty(sk) & pre.adj_empty(vk))
        # MAJORITY cells: any of my EXCLUSIVE components (tile count irrelevant —
        # the majority is a meeple count, not a tile count) that could merge into
        # a contested component where I am tied or behind.
        major_cells: set = set()
        for sk in my_comps:
            for mk in majors:
                if mk[0] != sk[0]:
                    continue
                major_cells |= (pre.adj_empty(sk) & pre.adj_empty(mk))

        setup_on = (cfg.setup_enabled and in_window
                    and st.meeples[me] >= cfg.min_meeples_for_foothold
                    and self.tel["setup_fires"] < cfg.max_setup_fires)
        setup_cells: set = set()
        if setup_on:
            for vk in victims:
                if pre.potential_pts(vk) >= cfg.setup_victim_min_pts:
                    setup_cells |= pre.adj_empty(vk)
            # REINFORCE-SETUP: a tile whose fresh unclaimed segment could become
            # the SECOND part that later flips a tie.  Same gate, same cap.
            if cfg.reinforce_enabled and st.meeples[me] >= cfg.min_meeples_for_reinforce \
                    and len(self.ledger.open_of_kind("reinforce")) < cfg.max_open_reinforcements:
                for mk in majors:
                    if pre.potential_pts(mk) >= cfg.setup_victim_min_pts:
                        setup_cells |= pre.adj_empty(mk)

        want = merge_cells | major_cells | setup_cells
        if not want:
            return None

        idxs = self._legal(board)
        scan = []
        for a in idxs:
            act = self._decode(board, a)
            co = getattr(act, "coordinate", None)
            if co is None:
                continue
            if (co.row, co.column) in want:
                scan.append(a)
        if not scan:
            return None
        scan = scan[:cfg.max_scan_actions]
        self.tel["scan_plies"] += 1

        best_merge = None
        best_major = None
        setup_cands = []
        for a in scan:
            child, _ = self.game.get_next_state(board, a)
            post = Structure(child.state)
            if cfg.majority_enabled:
                for ev in majority_events(pre, post, me):
                    if ev["victim_pts"] < cfg.majority_min_pts:
                        continue
                    self.tel["majority_candidates_seen"] += 1
                    # A majority is worth ~2x a tie: I take the feature AND the
                    # incumbent loses it, where a tie pays both in full.
                    rank = 2.0 * ev["victim_pts"] * (cfg.farm_pref
                                                     if ev["cls"] == CLS_FARM else 1.0)
                    if best_major is None or rank > best_major[0]:
                        best_major = (rank, a, ev)
            if best_major is None and cfg.merge_enabled:
                for ev in invasion_events(pre, post):
                    if ev["invader"] != me or ev["victim_pts"] < cfg.victim_min_pts:
                        continue
                    self.tel["merge_candidates_seen"] += 1
                    rank = ev["victim_pts"] * (cfg.farm_pref if ev["cls"] == CLS_FARM else 1.0)
                    if best_merge is None or rank > best_merge[0]:
                        best_merge = (rank, a, ev)
            if best_major is None and best_merge is None and setup_on:
                s = self._setup_score(child, post, me, opp, a)
                if s is not None:
                    self.tel["setup_candidates_seen"] += 1
                    setup_cands.append(s)

        # MAJORITY outranks MERGE: it converts a `shared_tie` (which denies the
        # incumbent NOTHING under full-points-on-tie) into an `invader_took_all`,
        # roughly twice the swing of authoring a fresh tie.  Like MERGE it is
        # UNGATED — it spends only a tile choice, no meeple, and gating the
        # measured mechanism on the champion's own preferences would re-import
        # exactly the "the champion doesn't value this" bias the instrument
        # exists to escape.
        if best_major is not None:
            _, a, ev = best_major
            self.tel["majority_fires"] += 1
            self.tel["majority_from_tie"] += int(ev["from_tie"])
            closed = self.ledger.complete(self._ply, ev["my_meeples"])
            self._record("majority", a, ply=self._ply, cls=ev["cls"],
                         victim_pts=ev["victim_pts"], from_tie=ev["from_tie"],
                         me_after=ev["me_after"], opp_after=ev["opp_after"],
                         plans_closed=[p.pid for p in closed])
            return a

        if best_merge is not None:
            _, a, ev = best_merge
            self.tel["merge_fires"] += 1
            closed = self.ledger.complete(self._ply, ev["stub_meeples"])
            self._record("merge", a, ply=self._ply, cls=ev["cls"],
                         victim_pts=ev["victim_pts"],
                         invader_tiles=ev["invader_tiles"],
                         incumbent_tiles=ev["incumbent_tiles"],
                         plans_closed=[p.pid for p in closed])
            return a

        if not setup_cands:
            return None
        setup_cands.sort(key=lambda s: (-s["rank"], s["action"]))
        base_action = int(self.base.move(board))
        visits = self._visits()
        if visits is not None and not visits:
            self.tel["override_declined_no_visits"] += 1
            self.tel["base_moves"] += 1
            return base_action
        base_leaf = self._leaf(board, base_action, me)
        for s in setup_cands:
            if s["action"] == base_action:
                self._fire_setup(s, base_action, 0.0, None,
                                 note="base agent already plays it")
                return base_action
            if not self._visit_ok(visits, s["action"]):
                self.tel["setup_vetoed_by_visits"] += 1
                continue
            cost = base_leaf - self._leaf(board, s["action"], me)
            if cost > self.cfg.setup_leaf_tolerance:
                self.tel["setup_vetoed_by_leaf"] += 1
                continue
            self._fire_setup(s, s["action"], cost, visits)
            return s["action"]
        self.tel["base_moves"] += 1
        return base_action

    def _fire_setup(self, s, action: int, cost: float, visits, note=None) -> None:
        """Book a SETUP fire.  A setup aimed at a MAJORITY target is counted
        separately (`reinforce_setup_fires`) but is the same override: it only
        chooses where the tile goes, and spends no meeple."""
        self.tel["setup_fires"] += 1
        if s.get("kind") == "reinforce":
            self.tel["reinforce_setup_fires"] += 1
        self._record("setup", action, ply=self._ply, cls=s["cls"],
                     target=s.get("kind", "invade"), victim_pts=s["victim_pts"],
                     leaf_cost=round(float(cost), 3),
                     visit_share=round(_share(visits, action), 4),
                     **({"note": note} if note else {}))

    def _setup_score(self, child, post: Structure, me: int, opp: int, action: int):
        """Does this tile placement create a fresh, claimable stub next to a victim?"""
        cfg = self.cfg
        st2 = child.state
        la = st2.last_tile_action
        if la is None:
            return None
        r, c = la.coordinate.row, la.coordinate.column
        tile = st2.board[r][c]
        if tile is None:
            return None
        best = None
        for key in _tile_slot_components(post, r, c, tile):
            if key in post.counts:              # already claimed by someone
                continue
            if post.n_tiles(key) > cfg.stub_max_tiles:
                continue
            for vk in post.counts:
                if vk[0] != key[0] or not post.exclusively(vk, opp):
                    continue
                if post.finished(vk) or post.n_tiles(vk) < cfg.victim_min_tiles:
                    continue
                if post.n_tiles(vk) <= post.n_tiles(key):
                    continue
                pts = post.potential_pts(vk)
                if pts < cfg.setup_victim_min_pts:
                    continue
                if len(post.adj_empty(key) & post.adj_empty(vk)) < cfg.setup_min_merge_cells:
                    continue
                rank = pts * (cfg.farm_pref if vk[0] == CLS_FARM else 1.0)
                if best is None or rank > best["rank"]:
                    best = {"rank": rank, "action": int(action), "cls": key[0],
                            "victim_pts": int(pts), "kind": "invade"}
            # REINFORCE-SETUP: the same fresh stub, but beside a CONTESTED
            # feature where I am tied or behind.  No tile-count comparison here —
            # a majority is a meeple count, so a 1-tile stub flips a 12-tile
            # field just as well.
            if not (cfg.reinforce_enabled and cfg.majority_enabled):
                continue
            for mk in post.majority_targets(me, cfg):
                if mk[0] != key[0]:
                    continue
                pts = post.potential_pts(mk)
                if pts < cfg.setup_victim_min_pts:
                    continue
                if len(post.adj_empty(key) & post.adj_empty(mk)) < cfg.setup_min_merge_cells:
                    continue
                rank = 2.0 * pts * (cfg.farm_pref if mk[0] == CLS_FARM else 1.0)
                if best is None or rank > best["rank"]:
                    best = {"rank": rank, "action": int(action), "cls": key[0],
                            "victim_pts": int(pts), "kind": "reinforce"}
        return best

    # -------------------------------------------------------------- MEEPLES #
    def _meeple_move(self, board, st, pre: Structure, me: int, in_window: bool):
        cfg = self.cfg
        if not in_window:
            return None
        opp = 1 - me
        # REINFORCE is allowed only with a meeple to spare and under the
        # concurrency cap — it commits a SECOND meeple to a feature already
        # committed, which is the meeple-scarcity trade H3' is about.
        reinforce_on = (cfg.reinforce_enabled and cfg.majority_enabled
                        and st.meeples[me] >= cfg.min_meeples_for_reinforce
                        and len(self.ledger.open_of_kind("reinforce"))
                        < cfg.max_open_reinforcements)
        foothold_on = (cfg.foothold_enabled
                       and st.meeples[me] >= cfg.min_meeples_for_foothold)
        if not (reinforce_on or foothold_on):
            return None
        victims = pre.victims_of(opp, cfg) if foothold_on else []
        majors = pre.majority_targets(me, cfg) if reinforce_on else []
        if not victims and not majors:
            return None

        cands = []
        for a in self._legal(board):
            act = self._decode(board, a)
            cws = getattr(act, "coordinate_with_side", None)
            if cws is None:
                continue                        # the meeple-phase pass
            r, c = cws.coordinate.row, cws.coordinate.column
            side = cws.side
            key = _slot_component(pre, r, c, side, act.meeple_type)
            if key is None or key in pre.counts:
                continue
            common = {"action": int(a), "cls": key[0], "side": side, "rc": (r, c),
                      "mtype": act.meeple_type}
            # REINFORCE-FOOTHOLD first: it is worth ~2x an invasion foothold
            # (majority denies; a tie does not), and it is ranked that way.
            for mk in majors:
                if mk[0] != key[0] or pre.n_tiles(key) > cfg.reinforce_stub_max_tiles:
                    continue
                if not merge_plausible(pre, key, mk):
                    continue
                pts = pre.potential_pts(mk)
                cands.append(dict(common, kind="reinforce",
                                  rank=2.0 * pts * (cfg.farm_pref
                                                    if mk[0] == CLS_FARM else 1.0),
                                  victim_key=mk, victim_pts=int(pts)))
            if pre.n_tiles(key) > cfg.stub_max_tiles:
                continue
            for vk in victims:
                if vk[0] != key[0] or pre.n_tiles(vk) <= pre.n_tiles(key):
                    continue
                if not merge_plausible(pre, key, vk):
                    continue
                pts = pre.potential_pts(vk)
                rank = pts * (cfg.farm_pref if vk[0] == CLS_FARM else 1.0)
                cands.append(dict(common, kind="invade", rank=rank,
                                  victim_key=vk, victim_pts=int(pts)))
        if not cands:
            return None
        self.tel["foothold_candidates_seen"] += sum(
            1 for s in cands if s["kind"] == "invade")
        self.tel["reinforce_candidates_seen"] += sum(
            1 for s in cands if s["kind"] == "reinforce")
        cands.sort(key=lambda s: (-s["rank"], s["action"]))

        base_action = int(self.base.move(board))
        visits = self._visits()
        if visits is not None and not visits:
            self.tel["override_declined_no_visits"] += 1
            self.tel["base_moves"] += 1
            return base_action
        base_leaf = self._leaf(board, base_action, me)
        for s in cands:
            kind = s["kind"]
            if s["action"] != base_action:
                if not self._visit_ok(visits, s["action"]):
                    self.tel[f"{kind_tel(kind)}_vetoed_by_visits"] += 1
                    continue
                cost = base_leaf - self._leaf(board, s["action"], me)
                if cost > cfg.foothold_leaf_tolerance:
                    self.tel[f"{kind_tel(kind)}_vetoed_by_leaf"] += 1
                    continue
            else:
                cost = 0.0
            r, c = s["rc"]
            stub_meeple = (me, r, c, getattr(s["side"], "name", str(s["side"])),
                           s["mtype"].name)
            # For a REINFORCE plan the "victim" meeple is one of the OPPONENT's
            # on the contested target, so `refresh` abandons the plan if they
            # pull out of it.
            members = sorted(pre.members.get(s["victim_key"], ()))
            if kind == "reinforce":
                opp_members = [m for m in members if m[0] == opp]
                members = opp_members or members
            victim_meeple = members[0]
            plan = self.ledger.start(self._ply, s["cls"], stub_meeple, victim_meeple,
                                     pre.n_tiles(s["victim_key"]), s["victim_pts"],
                                     kind=kind)
            if kind == "reinforce":
                self.tel["reinforce_foothold_fires"] += 1
                self.tel["meeples_spent_on_reinforcement"] += 1
            else:
                self.tel["foothold_fires"] += 1
            self._record("reinforce_foothold" if kind == "reinforce" else "foothold",
                         s["action"], ply=self._ply, cls=s["cls"],
                         victim_pts=s["victim_pts"], leaf_cost=round(cost, 3),
                         visit_share=round(_share(visits, s["action"]), 4),
                         meeples_left=int(st.meeples[me]), plan=plan.pid)
            return s["action"]
        self.tel["base_moves"] += 1
        return base_action

    # -- plumbing ----------------------------------------------------------- #
    def _legal(self, board) -> list:
        return [int(i) for i in np.flatnonzero(self.game.get_valid_moves(board))]

    def _decode(self, board, a: int):
        st = board.state
        return action_space.decode(
            int(a), off=board.offset, phase=st.phase.value,
            next_tile=st.next_tile,
            last_tile_coord=(st.last_tile_action.coordinate
                             if st.last_tile_action is not None else None))

    def _record(self, kind: str, action: int, **kw) -> None:
        rec = {"kind": kind, "action": int(action)}
        rec.update(kw)
        self.fires.append(rec)

    # -- read-out ------------------------------------------------------------ #
    def telemetry(self) -> dict:
        out = dict(self.tel)
        out.update(self.ledger.summary())
        out["label"] = self.label
        out["cfg"] = self.cfg.as_dict()
        return out


# --------------------------------------------------------------------------- #
# slot -> component                                                             #
# --------------------------------------------------------------------------- #
def _slot_component(struct: Structure, r: int, c: int, side, meeple_type):
    """The component a meeple placed at (r, c, side) would join, or None."""
    tile = struct.board[r][c]
    if tile is None:
        return None
    if meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
        root = struct.decomp.farm_anypos_root.get((r, c, side))
        return None if root is None else (CLS_FARM, root)
    terrain = tile.get_type(side)
    if terrain == TerrainType.CITY:
        root = struct.decomp.city_side_root.get((r, c, side))
        return None if root is None else (CLS_CITY, root)
    if terrain == TerrainType.ROAD:
        root = struct.decomp.road_side_root.get((r, c, side))
        return None if root is None else (CLS_ROAD, root)
    return None                                # cloister or nothing


def _tile_slot_components(struct: Structure, r: int, c: int, tile) -> list:
    """Every distinct component a meeple on the tile at (r, c) could join."""
    out = []
    seen = set()
    for side in action_space.NORMAL_SIDES:
        if side == Side.CENTER:
            continue
        key = _slot_component(struct, r, c, side, MeepleType.NORMAL)
        if key is not None and key not in seen:
            seen.add(key)
            out.append(key)
    for side in action_space.FARMER_SIDES:
        key = _slot_component(struct, r, c, side, MeepleType.FARMER)
        if key is not None and key not in seen:
            seen.add(key)
            out.append(key)
    return out
