#!/usr/bin/env python3
"""C1 MICRO-GATES — G1 contest realization + G2 disagreement, on banked plies.

Design and every constant: `PREREG.md` (frozen BEFORE any gate statistic).

Zero new games. The only compute is tier1-greedy (`RuleBasedPlayer`) rollouts to
terminal from the 290 banked crux plies of `e4_ply_pricing_20260827`, censused
with the `e4_exploit_grading_20260825` Stage-A contest definitions (PREREG §2.2
names the two adaptations, A1 and A2, and nothing else is adapted).

R9 is IMPORT-LATCHED, so this script runs ONE PROFILE PER PROCESS (`--profile`)
and calls `analyzer.ev_loss.prepare_env` before any `carcassonne_ai` import.

Stages:
  gates      G-DETECT (the detector must reproduce a KNOWN banked invasion) and
             G-REPEAT (determinism), PREREG §4.
  g1         the played-action arm over M_WORLDS CRN worlds  (PRIMARY)
  g1ext      worlds M_WORLDS..M_WORLDS_EXT on the same arm    (conditional)
  g2         <=K_MAX arms over the SAME M_WORLDS worlds       (secondary)
  aggregate  every stage's units -> MICROGATES.json

Every stage is resumable: a unit whose output file exists is skipped, and units
are written atomically (`.tmp` + rename), so `--budget-s` can stop a pass at any
point without losing more than nothing.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))

ARCHIVES = REPO / "measurement" / "e4_games"
BANKED_ROWS = "/mnt/c/carc-shared/e4_ply_pricing_20260827/rows_*.jsonl"

# --- pre-registered constants (PREREG §1.2; frozen) ------------------------- #
WORLD_SEED = 20260828          # IDENTICAL to e4_continuation_20260828
PLAYOUT_SALT = 20260829
M_WORLDS = 16
M_WORLDS_EXT = 64
K_MAX = 8
MAX_PLIES = 400
LEGAL_MASK_CACHE = False       # the HONEST mask (PREREG §2.4)

GATE_R_DEAD = 0.10
GATE_R_LIVE = 0.35
GATE_D_LIVE = 0.15
P_REF = 0.7394                 # 1 - exp(-0.01873 * 71.8)   banked, PREREG §3.1
P_REF_FARM = 0.4658            # 1 - exp(-0.00873 * 71.8)
GATE_EXT_LO, GATE_EXT_HI = 0.005, 0.20
VOID_ATTRITION = 0.05
VOID_GUARD = 0.01
G_DETECT_MIN = 0.95


def world_rng(deck_seed: int, ply: int, world: int) -> random.Random:
    """The e4_continuation_20260828 world generator, verbatim. NO ARM TERM."""
    return random.Random(WORLD_SEED ^ (int(deck_seed) * 1000003)
                         ^ (int(ply) * 7919) ^ (int(world) * 104729))


def playout_seed(deck_seed: int, ply: int, world: int) -> int:
    """The rollout policy's seed. Also arm-independent (tier1_leg's convention)."""
    return (PLAYOUT_SALT ^ (int(deck_seed) * 1000003)
            ^ (int(ply) * 7919) ^ (int(world) * 104729)) & 0x7FFFFFFF


# --------------------------------------------------------------------------- #
# the banked target set                                                         #
# --------------------------------------------------------------------------- #
def load_targets() -> list:
    rows = []
    for p in sorted(glob.glob(BANKED_ROWS)):
        for line in open(p):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if len(rows) != 290:
        raise RuntimeError(f"expected 290 banked rows, found {len(rows)}")
    rows.sort(key=lambda r: (r["game"], int(r["ply"])))
    return rows


# --------------------------------------------------------------------------- #
# Stage-A detector, ported (PREREG §2.2)                                        #
# --------------------------------------------------------------------------- #
class UF:
    """Plain union-find over hashable keys — `stage_a_census.UF`, verbatim."""

    def __init__(self):
        self.p = {}

    def find(self, x):
        p = self.p
        if x not in p:
            p[x] = x
            return x
        root = x
        while p[root] != root:
            root = p[root]
        while p[x] != root:
            p[x], x = root, p[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra
        return ra


def _sname(side) -> str:
    return getattr(side, "name", str(side))


#: This census keys components `("C"|"R"|"F", ...)`; the BANKED Stage-A rows spell
#: the same classes `city`/`road`/`farm`. One vocabulary, two spellings — the map
#: is here so G-DETECT compares like with like.
CLS_LONG = {"city": "C", "road": "R", "farm": "F"}


def tagged_classes(row: dict) -> set:
    """The class(es) the BANKED row tags at this ply, as this census spells them.

    `notes.cls` is a plain string on a single-event ply and a LIST on a
    multi-event one, and `notes.events[*].cls` carries the same information per
    event — so both are read and unioned. G-DETECT then asks whether the census
    fired ANY of the tagged classes at the arm ply, which is exactly the
    multi-event allowance PREREG §4 reserved.
    """
    notes = row.get("notes") or {}
    raw = []
    c = notes.get("cls")
    if isinstance(c, list):
        raw.extend(c)
    elif c is not None:
        raw.append(c)
    for e in notes.get("events") or []:
        if e.get("cls") is not None:
            raw.append(e["cls"])
    return {CLS_LONG[x] for x in raw if x in CLS_LONG}


class Census:
    """Streaming Stage-A contest census over ONE rollout.

    Seeded at the crux root: the root's components enter the union-find and every
    component already contested THERE is pre-loaded into `contested_seen`, so only
    NEW onsets are recorded (adaptation A1). `n_tiles` is the count of distinct
    (row, col) among a component's positional keys (adaptation A2).
    """

    def __init__(self, flat_leaf):
        self.fl = flat_leaf
        self.uf = UF()
        self.contested_seen = set()
        self.prev = None                 # (reps -> record) of the previous ply
        self.onsets = []

    # -- one ply's structure ------------------------------------------------- #
    def _scan(self, state):
        fl = self.fl
        decomp = fl.decompose(state)
        groups = []
        key_to_rep = {}
        rec = {}
        for cls, mapping in (("C", decomp.city_side_root),
                             ("R", decomp.road_side_root),
                             ("F", decomp.farm_anypos_root)):
            byroot = defaultdict(list)
            for (r, c, side), root in mapping.items():
                byroot[root].append((cls, r, c, _sname(side)))
            for root, keys in byroot.items():
                kk = sorted(keys)
                groups.append(kk)
                rep = kk[0]
                for k in kk:
                    key_to_rep[k] = rep
                rec[rep] = {"cls": cls, "rep": rep,
                            "n_tiles": len({(k[1], k[2]) for k in kk}),
                            "counts": [0, 0]}
        for pl in range(state.players):
            for mp in state.placed_meeples[pl]:
                fk = _meeple_key(mp, state)
                if fk is None:
                    continue
                rep = key_to_rep.get(fk)
                if rep is None:
                    continue
                rec[rep]["counts"][pl] += fl._meeple_weight(mp.meeple_type)
        return decomp, groups, rec

    def seed_root(self, state):
        decomp, groups, rec = self._scan(state)
        for kk in groups:
            base = kk[0]
            for k in kk[1:]:
                self.uf.union(base, k)
        for rep, cm in rec.items():
            if cm["counts"][0] > 0 and cm["counts"][1] > 0:
                self.contested_seen.add(self.uf.find(rep))
        self.prev = rec
        return decomp, rec

    def step(self, state, ply, actor, phase, placed_meeple: bool):
        """Census one post-action state; append any NEW contest onset."""
        decomp, groups, rec = self._scan(state)
        for kk in groups:
            base = kk[0]
            for k in kk[1:]:
                self.uf.union(base, k)
        for rep, cm in rec.items():
            if cm["counts"][0] <= 0 or cm["counts"][1] <= 0:
                continue
            f = self.uf.find(rep)
            if f in self.contested_seen:
                continue
            self.contested_seen.add(f)
            # --- mechanism, from the PREVIOUS ply's parts of the same fid ---- #
            pre_parts = []
            for prep, pcm in (self.prev or {}).items():
                if self.uf.find(prep) != f:
                    continue
                pre_parts.append({"n_tiles": pcm["n_tiles"],
                                  "m0": pcm["counts"][0], "m1": pcm["counts"][1]})
            occ = [p for p in pre_parts if p["m0"] or p["m1"]]
            mech, invader, incumbent = "unknown", None, None
            inv_tiles = inc_tiles = None
            if len(occ) >= 2:
                mech = "merge"
                s0 = [p for p in occ if p["m0"] and not p["m1"]]
                s1 = [p for p in occ if p["m1"] and not p["m0"]]
                if s0 and s1:
                    t0 = sum(p["n_tiles"] for p in s0)
                    t1 = sum(p["n_tiles"] for p in s1)
                    if t0 < t1:
                        invader, incumbent, inv_tiles, inc_tiles = 0, 1, t0, t1
                    elif t1 < t0:
                        invader, incumbent, inv_tiles, inc_tiles = 1, 0, t1, t0
                    else:
                        mech = "merge_equal"
                        inv_tiles = inc_tiles = t0
            elif len(occ) == 1 and phase == "meeples" and placed_meeple:
                mech = "placement"
                invader, incumbent = actor, 1 - actor
                inc_tiles, inv_tiles = occ[0]["n_tiles"], 0
            elif not pre_parts:
                mech = "born_contested"
            self.onsets.append({
                "ply": ply, "cls": rec[rep]["cls"], "mech": mech,
                "actor": actor, "phase": phase,
                "invader": invader, "incumbent": incumbent,
                "invader_tiles_pre": inv_tiles, "incumbent_tiles_pre": inc_tiles,
                "n_tiles_at_contest": rec[rep]["n_tiles"],
            })
        self.prev = rec
        return decomp


def _meeple_key(mp, state):
    """`stage_a_census.meeple_component_key`, verbatim (cloisters -> None)."""
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    cws = mp.coordinate_with_side
    r, c, side = cws.coordinate.row, cws.coordinate.column, cws.side
    terrain = state.board[r][c].get_type(side)
    if terrain == TerrainType.CITY:
        return ("C", r, c, _sname(side))
    if terrain == TerrainType.ROAD:
        return ("R", r, c, _sname(side))
    if terrain in (TerrainType.CHAPEL, TerrainType.FLOWERS):
        return None
    if mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
        return ("F", r, c, _sname(side))
    return None


# --- farm control / farmer invalidation (PREREG §2.2) ----------------------- #
def farm_view(state, decomp, flat_leaf, extra_farmer=None):
    """root -> {counts, finished_cities, control}, plus farmer meeple rows.

    Farm meeples map through `farm_pos0_root`, the key the SCORING path uses.

    `extra_farmer` = `(player, row, col, side, meeple_type)` injects one farmer
    that is NOT in `state.placed_meeples`. It exists for exactly one case: the
    game-ending transition performs final scoring and RETURNS EVERY MEEPLE, so a
    terminal state carries none and the pre-scoring state has to be read instead
    — and if the game's very last action was a farmer PLACEMENT, that farmer is
    in neither. See `terminal_farm_view`.
    """
    counts = defaultdict(lambda: [0, 0])
    farmers = []
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    rows = [(pl, mp.coordinate_with_side.coordinate.row,
             mp.coordinate_with_side.coordinate.column,
             mp.coordinate_with_side.side, mp.meeple_type)
            for pl in range(state.players) for mp in state.placed_meeples[pl]]
    if extra_farmer is not None:
        rows.append(tuple(extra_farmer))
    for pl, r, c, side, mtype in rows:
        if mtype not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
            continue
        if state.board[r][c].get_type(side) in (TerrainType.CITY, TerrainType.ROAD,
                                                TerrainType.CHAPEL, TerrainType.FLOWERS):
            continue
        root = decomp.farm_pos0_root.get((r, c, side))
        if root is None:
            continue
        counts[root][pl] += flat_leaf._meeple_weight(mtype)
        farmers.append({"player": pl, "pos": [r, c, _sname(side)], "root": root})
    out = {}
    for root, cnt in counts.items():
        if cnt[0] > cnt[1]:
            ctl = 0
        elif cnt[1] > cnt[0]:
            ctl = 1
        else:
            ctl = "shared"
        out[root] = {"counts": list(cnt), "control": ctl,
                     "finished_cities": int(decomp.farm_root_finished_cities.get(root, 0))}
    return out, farmers


def _farm_rep_keys(decomp):
    """root -> a stable positional key (min of its anypos keys)."""
    byroot = defaultdict(list)
    for (r, c, side), root in decomp.farm_anypos_root.items():
        byroot[root].append((r, c, _sname(side)))
    return {root: min(ks) for root, ks in byroot.items()}


def _farm_key_to_root(decomp):
    return {(r, c, _sname(side)): root
            for (r, c, side), root in decomp.farm_anypos_root.items()}


def terminal_farm_view(g, prev_board, term_board, last_action, last_phase, flat_leaf):
    """The farm structure of the FINISHED position, WITH its farmers still on it.

    ⚠️ The game-ending transition runs final scoring and returns every meeple, so
    `term_board.state.placed_meeples` is EMPTY and reading farms off it yields a
    structurally-zero answer (measured: 2,416/2,416 root farm components read as
    control -> "none"). The pre-scoring position is `prev_board`, and because the
    terminating action is a MEEPLES-phase action in the ordinary case, its farm
    GEOMETRY is already the terminal geometry. The one thing `prev_board` can
    miss is a farmer placed BY that final action, which is injected via
    `extra_farmer`.

    Returns `(view, farmers, key_to_root, flags)`; `flags.scoring_state` says
    which board was read and `flags.injected_final_farmer` whether the edge case
    fired, so neither is invisible in the artifact.
    """
    from carcassonne_ai.action_space import decode, meeple_pass_index

    st_term = term_board.state
    n_term = sum(len(st_term.placed_meeples[p]) for p in range(st_term.players))
    flags = {"scoring_state": "terminal", "injected_final_farmer": False,
             "last_action_phase": last_phase}
    if n_term > 0 or prev_board is None:
        st = st_term
        extra = None
    else:
        st = prev_board.state
        flags["scoring_state"] = "pre_scoring"
        extra = None
        if last_phase == "meeples" and last_action is not None:
            pass_idx = meeple_pass_index(prev_board.offset.size)
            if int(last_action) != pass_idx:
                act = decode(int(last_action), off=prev_board.offset, phase="meeples",
                             last_tile_coord=st.last_tile_action.coordinate)
                cws = act.coordinate_with_side
                extra = (int(st.current_player), cws.coordinate.row,
                         cws.coordinate.column, cws.side, act.meeple_type)
                flags["injected_final_farmer"] = True
    decomp = flat_leaf.decompose(st)
    view, farmers = farm_view(st, decomp, flat_leaf, extra_farmer=extra)
    return view, farmers, _farm_key_to_root(decomp), flags


# --------------------------------------------------------------------------- #
# the world + the rollout                                                       #
# --------------------------------------------------------------------------- #
def build_world_root(g, prof, deck_seed: int, actions: list, ply: int, world: int):
    """`continue_plies._run_arm`'s world installation, with all three guards.

    `world < 0` means the TRUE deck (no permutation) — used by G-DETECT.
    Returns (board_at_ply, world_order_descriptions, n_drawn, true_repr).
    """
    from carcassonne_ai.game_wrapper import Game

    random.seed(int(deck_seed))
    g1 = Game(enable_legal_moves_cache=LEGAL_MASK_CACHE, **prof.game_kwargs())
    b = g1.get_init_board()
    full = [b.state.next_tile] + list(b.state.deck)
    for a in actions[:ply]:
        b, _ = g1.get_next_state(b, int(a))
    unseen = list(b.state.deck)
    n_drawn = len(full) - len(unseen)
    if [t.description for t in full[n_drawn:]] != [t.description for t in unseen]:
        raise RuntimeError("deck_tail_mismatch")
    true_repr = g1.string_representation(b)

    perm = list(unseen)
    if world >= 0:
        world_rng(deck_seed, ply, world).shuffle(perm)
    world_order = [t.description for t in perm]

    random.seed(int(deck_seed))
    g2 = Game(enable_legal_moves_cache=LEGAL_MASK_CACHE, **prof.game_kwargs())
    b2 = g2.get_init_board()
    new_full = list(full[:n_drawn]) + perm
    if [t.description for t in new_full[:n_drawn]] != [t.description for t in full[:n_drawn]]:
        raise RuntimeError("world_prefix_mutated")
    if sorted(t.description for t in new_full) != sorted(t.description for t in full):
        raise RuntimeError("world_not_a_permutation")
    b2.state.next_tile = new_full[0]
    b2.state.deck = list(new_full[1:])
    for a in actions[:ply]:
        b2, _ = g2.get_next_state(b2, int(a))
    if g2.string_representation(b2) != true_repr:
        raise RuntimeError("root_state_diverged")
    return g2, b2, world_order, n_drawn, true_repr


def run_arm(g, root_board, arm_action: int, root_ply: int, seed: int, flat_leaf,
            forced_actions=None):
    """Apply `arm_action`, play both seats tier1-greedy to terminal, censusing.

    `forced_actions` (G-DETECT only) replays a fixed continuation instead of the
    policy — same census, same code path.
    """
    import copy
    from carcassonne_ai.rule_based_player import RuleBasedPlayer

    b = copy.deepcopy(root_board)
    cen = Census(flat_leaf)
    root_decomp, _ = cen.seed_root(b.state)
    root_farms, root_farmers = farm_view(b.state, root_decomp, flat_leaf)
    root_farm_rep = _farm_rep_keys(root_decomp)
    scores_at_root = [int(x) for x in b.state.scores]

    st = b.state
    actor0, phase0 = int(st.current_player), st.phase.value
    b, _ = g.get_next_state(b, int(arm_action))
    cen.step(b.state, root_ply, actor0, phase0, placed_meeple=(phase0 == "meeples"))
    n_arm_onsets = len(cen.onsets)
    arm_onsets = list(cen.onsets)

    pl = RuleBasedPlayer(seed=int(seed))
    n = 0
    prev_b, last_action, last_phase = None, None, None
    while not b.state.is_terminated():
        if n >= MAX_PLIES:
            raise RuntimeError("playout exceeded MAX_PLIES")
        st = b.state
        actor, phase = int(st.current_player), st.phase.value
        if forced_actions is not None:
            if n >= len(forced_actions):
                break
            a = int(forced_actions[n])
        else:
            a = int(pl.choose_action(g, b, g.get_valid_moves(b)))
        # `get_next_state` never mutates its input, so keeping the previous board
        # is a free reference — and it is the only pre-scoring position there is.
        prev_b, last_action, last_phase = b, a, phase
        b, _ = g.get_next_state(b, a)
        placed = (phase == "meeples")
        cen.step(b.state, root_ply + 1 + n, actor, phase, placed_meeple=placed)
        n += 1

    term_farms, _tf, term_key_to_root, term_flags = terminal_farm_view(
        g, prev_b, b, last_action, last_phase, flat_leaf)

    # --- farm control change: root component -> its (unique) terminal component
    control_changed = []
    for root, rec in root_farms.items():
        if rec["control"] not in (0, 1):
            continue
        k = root_farm_rep.get(root)
        troot = term_key_to_root.get(k) if k is not None else None
        if troot is None:
            control_changed.append({"root_control": rec["control"],
                                    "term_control": "MISSING", "changed": None})
            continue
        tctl = term_farms.get(troot, {}).get("control", "none")
        if tctl != rec["control"]:
            control_changed.append({"root_control": rec["control"],
                                    "term_control": tctl, "changed": True,
                                    "term_finished_cities":
                                        term_farms.get(troot, {}).get("finished_cities", 0)})

    # --- root farmers zeroed at terminal
    zero_no_cities = zero_lost_majority = 0
    for f in root_farmers:
        k = root_farm_rep.get(f["root"])
        troot = term_key_to_root.get(k) if k is not None else None
        if troot is None:
            continue
        t = term_farms.get(troot)
        if t is None:
            continue
        if t["finished_cities"] == 0:
            zero_no_cities += 1
        elif t["control"] != "shared" and t["control"] != f["player"]:
            zero_lost_majority += 1

    roll = [o for o in cen.onsets if o["ply"] > root_ply]
    s0, s1 = (int(x) for x in b.state.scores)
    return {
        "status": "OK",
        "arm_action": int(arm_action),
        "final_scores": [s0, s1],
        "margin_p0_minus_p1": s0 - s1,
        "scores_at_root": scores_at_root,
        "n_continuation_plies": n,
        "arm_ply_onsets": arm_onsets,
        "n_arm_ply_onsets": n_arm_onsets,
        "rollout_onsets": roll,
        "n_rollout_onsets": len(roll),
        "rollout_onset_cls": sorted({o["cls"] for o in roll}),
        "rollout_onset_invaders": sorted({str(o["invader"]) for o in roll}),
        "n_root_farm_components": len(root_farms),
        "n_root_farm_controlled": sum(1 for v in root_farms.values()
                                      if v["control"] in (0, 1)),
        "farm_control_changed": control_changed,
        "n_farm_control_changed": sum(1 for c in control_changed if c["changed"]),
        "n_root_farmers": len(root_farmers),
        "n_root_farmer_zero_no_cities": zero_no_cities,
        "n_root_farmer_zero_lost_majority": zero_lost_majority,
        "n_term_farm_components_with_farmers": len(term_farms),
        "terminal_farm_flags": term_flags,
    }


# --------------------------------------------------------------------------- #
# candidate set (G2)                                                            #
# --------------------------------------------------------------------------- #
def champion_leaf_topk(g, board, k: int, leaf_cfg, flat_leaf):
    """Legal actions ranked by the CHAMPION LEAF on the afterstate, mover POV."""
    import copy
    import numpy as np
    from carcassonne_ai.action_space import decode
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater

    valid = g.get_valid_moves(board)
    legal = [int(a) for a in np.flatnonzero(valid)]
    st = board.state
    player = int(st.current_player)
    phase = st.phase.value
    ltc = st.last_tile_action.coordinate if st.last_tile_action is not None else None
    scored = []
    for a in legal:
        act = decode(a, off=board.offset, phase=phase,
                     next_tile=st.next_tile, last_tile_coord=ltc)
        scratch = copy.deepcopy(st)
        StateUpdater.apply_action_inplace(game_state=scratch, action=act)
        v = float(flat_leaf.flat_virtual_score_v2_float(scratch, player, leaf_cfg))
        scored.append((-v, a))
    scored.sort()
    return legal, [a for _, a in scored][:k]


# --------------------------------------------------------------------------- #
# the worker                                                                    #
# --------------------------------------------------------------------------- #
_G = {}


def _init(profile: str):
    from carcassonne_ai import flat_leaf, rules_profile
    _G["flat_leaf"] = flat_leaf
    _G["prof"] = rules_profile.resolve(profile)
    _G["rules_profile"] = rules_profile


def _leaf_cfg():
    if "leaf_cfg" not in _G:
        from carcassonne_ai.champion_factory import production_leaf_cfg
        _G["leaf_cfg"] = production_leaf_cfg()
    return _G["leaf_cfg"]


def do_unit(job: dict) -> dict:
    """One (game, ply, world): build the world once, run every arm from it."""
    t0 = time.time()
    from analyzer import ev_loss
    fl = _G["flat_leaf"]
    prof = _G["prof"]
    out = {k: job[k] for k in ("game", "ply", "world", "stratum", "profile",
                               "played_action", "counterfactual_action",
                               "counterfactual_agrees", "actor", "phase",
                               "n_legal", "n_plies")}
    try:
        arch = ev_loss.load_archive(ARCHIVES / job["game"])
        resolved = ev_loss.resolve_profile_name(arch)
        if resolved != job["profile"]:
            raise RuntimeError(f"profile drift {resolved} != {job['profile']}")
        out["r9_env"] = {"expected": prof.r9_env_expected,
                         "observed": _G["rules_profile"].r9_env_on()}
        if out["r9_env"]["expected"] != out["r9_env"]["observed"]:
            raise RuntimeError("r9_env latch mismatch")
        deck_seed = int(arch["deck_seed"])
        actions = arch["actions"]
        ply = int(job["ply"])
        g, root, world_order, n_drawn, _ = build_world_root(
            None, prof, deck_seed, actions, ply, int(job["world"]))
        out["witness"] = {"world_deck_len": len(world_order), "n_drawn_prefix": n_drawn}

        if job.get("arms") == "K":
            legal, top = champion_leaf_topk(g, root, K_MAX, _leaf_cfg(), fl)
            forced = [int(job["played_action"]), int(job["counterfactual_action"])]
            arms = []
            for a in forced:
                if a in legal and a not in arms:
                    arms.append(a)
            for a in top:
                if len(arms) >= min(K_MAX, len(legal)):
                    break
                if a not in arms:
                    arms.append(a)
            out["n_legal_root"] = len(legal)
            out["leaf_top"] = top
        else:
            arms = [int(job["played_action"])]

        seed = playout_seed(deck_seed, ply, int(job["world"]))
        out["playout_seed"] = seed
        out["arms"] = {}
        for a in arms:
            out["arms"][str(a)] = run_arm(g, root, a, ply, seed, fl,
                                          forced_actions=job.get("forced_actions"))
        out["status"] = "OK"
    except Exception as e:                                  # noqa: BLE001
        out["status"] = "ERROR"
        out["detail"] = f"{type(e).__name__}: {e}"
    out["elapsed_s"] = round(time.time() - t0, 3)
    return out


def unit_path(outdir: Path, stage: str, job: dict) -> Path:
    return (outdir / stage /
            f"{Path(job['game']).stem}_p{job['ply']}_w{job['world']}.json")


def write_atomic(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj))
    tmp.rename(p)


def run_pool(jobs: list, outdir: Path, stage: str, workers: int, budget_s: float,
             profile: str) -> dict:
    import multiprocessing as mp
    todo = [j for j in jobs if not unit_path(outdir, stage, j).exists()]
    print(f"[{stage}/{profile}] {len(todo)} units to run "
          f"({len(jobs) - len(todo)} already on disk), W={workers}", flush=True)
    if not todo:
        return {"ran": 0, "left": 0}
    t0 = time.time()
    done = 0
    ctx = mp.get_context("fork")
    with ctx.Pool(workers, initializer=_init, initargs=(profile,)) as pool:
        for job, res in zip(todo, pool.imap(do_unit, todo, chunksize=1)):
            write_atomic(unit_path(outdir, stage, job), res)
            done += 1
            if done % 50 == 0:
                el = time.time() - t0
                print(f"  {done}/{len(todo)}  {el:.0f}s  "
                      f"{el / done:.2f}s/unit", flush=True)
            if budget_s and (time.time() - t0) > budget_s:
                print(f"  budget {budget_s}s reached at {done}/{len(todo)}; "
                      f"terminating pool (resumable)", flush=True)
                pool.terminate()
                break
    return {"ran": done, "left": len(todo) - done,
            "elapsed_s": round(time.time() - t0, 1)}


# --------------------------------------------------------------------------- #
# job builders                                                                  #
# --------------------------------------------------------------------------- #
def base_job(r: dict, world: int) -> dict:
    return {"game": r["game"], "ply": int(r["ply"]), "world": world,
            "stratum": r["stratum"], "profile": r["profile"],
            "played_action": int(r["played_action"]),
            "counterfactual_action": int(r["counterfactual_action"]),
            "counterfactual_agrees": bool(r["counterfactual_agrees"]),
            "actor": int(r["actor"]), "phase": r["phase"],
            "n_legal": int(r["n_legal"]), "n_plies": int(r["n_plies"])}


def jobs_for(stage: str, rows: list, profile: str) -> list:
    rs = [r for r in rows if r["profile"] == profile]
    out = []
    if stage == "g1":
        for r in rs:
            for w in range(M_WORLDS):
                out.append(base_job(r, w))
    elif stage == "g1ext":
        for r in rs:
            for w in range(M_WORLDS, M_WORLDS_EXT):
                out.append(base_job(r, w))
    elif stage == "g2":
        for r in rs:
            for w in range(M_WORLDS):
                j = base_job(r, w)
                j["arms"] = "K"
                out.append(j)
    else:
        raise ValueError(stage)
    return out


# --------------------------------------------------------------------------- #
# instrument gates (PREREG §4)                                                  #
# --------------------------------------------------------------------------- #
def stage_gates(rows: list, outdir: Path, profile: str, workers: int) -> dict:
    from analyzer import ev_loss
    _init(profile)
    fl = _G["flat_leaf"]
    prof = _G["prof"]

    # --- G-DETECT ---------------------------------------------------------- #
    inv = [r for r in rows if r["profile"] == profile and r["stratum"] == "invasion"]
    hits, misses = 0, []
    rec_ok, rec_cmp, rec_bad = 0, 0, []
    for r in inv:
        arch = ev_loss.load_archive(ARCHIVES / r["game"])
        ply = int(r["ply"])
        g, root, _, _, _ = build_world_root(None, prof, int(arch["deck_seed"]),
                                            arch["actions"], ply, -1)
        res = run_arm(g, root, int(r["played_action"]), ply, 0, fl,
                      forced_actions=[int(a) for a in arch["actions"][ply + 1:]])
        want = tagged_classes(r)
        got = [o["cls"] for o in res["arm_ply_onsets"]]
        if want and (want & set(got)):
            hits += 1
        else:
            misses.append({"game": r["game"], "ply": ply,
                           "want": sorted(want),
                           "got_at_arm_ply": got,
                           "n_events": (r.get("notes") or {}).get("n_events"),
                           "got_in_rollout": [o["cls"] for o in res["rollout_onsets"]]})
        # --- G-REPLAY: the archive's own continuation must reproduce its score
        if arch.get("recorded_scores"):
            rec_cmp += 1
            if list(res["final_scores"]) == list(arch["recorded_scores"]):
                rec_ok += 1
            else:
                rec_bad.append({"game": r["game"], "ply": ply,
                                "replayed": res["final_scores"],
                                "recorded": arch["recorded_scores"]})
    rate = hits / len(inv) if inv else 1.0
    gdetect = {"n_invasion_plies": len(inv), "n_hit": hits, "rate": rate,
               "required": G_DETECT_MIN, "pass": rate >= G_DETECT_MIN,
               "misses": misses}
    greplay = {"n_compared": rec_cmp, "n_identical": rec_ok,
               "rate": (rec_ok / rec_cmp) if rec_cmp else 1.0,
               "pass": rec_cmp > 0 and rec_ok == rec_cmp, "mismatches": rec_bad[:20]}
    print(f"[G-DETECT/{profile}] {hits}/{len(inv)} = {rate:.3f} "
          f"(need >= {G_DETECT_MIN}) -> {'PASS' if gdetect['pass'] else 'FAIL'}",
          flush=True)
    print(f"[G-REPLAY/{profile}] {rec_ok}/{rec_cmp} archive replays reproduce the "
          f"recorded final score -> {'PASS' if greplay['pass'] else 'FAIL'}", flush=True)

    # --- G-REPEAT ---------------------------------------------------------- #
    rs = [r for r in rows if r["profile"] == profile][:5]
    reps = []
    for r in rs:
        j = base_job(r, 0)
        a = do_unit(j)
        b = do_unit(j)
        for x in (a, b):
            x.pop("elapsed_s", None)
        reps.append({"game": r["game"], "ply": r["ply"],
                     "identical": json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True),
                     "status": a["status"]})
    grepeat = {"units": reps, "pass": all(x["identical"] for x in reps)}
    print(f"[G-REPEAT/{profile}] {sum(x['identical'] for x in reps)}/{len(reps)} "
          f"identical -> {'PASS' if grepeat['pass'] else 'FAIL'}", flush=True)

    out = {"profile": profile, "G_DETECT": gdetect, "G_REPLAY": greplay,
           "G_REPEAT": grepeat}
    write_atomic(outdir / "gates" / f"GATES_{profile}.json", out)
    return out


# --------------------------------------------------------------------------- #
# aggregate                                                                     #
# --------------------------------------------------------------------------- #
def _cluster_se(by_game: dict) -> float:
    """SE of a pooled mean, clustered on GAME (per-game influence contributions)."""
    n_tot = sum(v[1] for v in by_game.values())
    if n_tot == 0 or len(by_game) < 2:
        return float("nan")
    mu = sum(v[0] for v in by_game.values()) / n_tot
    G = len(by_game)
    s = sum(((v[0] - mu * v[1]) / n_tot) ** 2 for v in by_game.values())
    return math.sqrt(s * G / max(G - 1, 1))


def aggregate(outdir: Path, rows: list) -> dict:
    units = defaultdict(list)
    for stage in ("g1", "g1ext", "g2"):
        for p in sorted((outdir / stage).glob("*.json")) if (outdir / stage).is_dir() else []:
            units[stage].append(json.loads(p.read_text()))
    res = {"n_units": {k: len(v) for k, v in units.items()},
           "constants": {"WORLD_SEED": WORLD_SEED, "PLAYOUT_SALT": PLAYOUT_SALT,
                         "M_WORLDS": M_WORLDS, "M_WORLDS_EXT": M_WORLDS_EXT,
                         "K_MAX": K_MAX, "LEGAL_MASK_CACHE": LEGAL_MASK_CACHE},
           "floors": {"GATE_R_DEAD": GATE_R_DEAD, "GATE_R_LIVE": GATE_R_LIVE,
                      "GATE_D_LIVE": GATE_D_LIVE, "P_REF": P_REF,
                      "P_REF_FARM": P_REF_FARM}}

    # ---------- G1 --------------------------------------------------------- #
    g1 = units["g1"] + units["g1ext"]
    res["G1"] = g1_readout(g1, rows)
    # ---------- G2 --------------------------------------------------------- #
    res["G2"] = g2_readout(units["g2"], rows) if units["g2"] else None
    # ---------- cross-stage determinism ------------------------------------ #
    if units["g2"]:
        key = {(u["game"], u["ply"], u["world"]): u for u in units["g1"]
               if u["status"] == "OK"}
        n_cmp = n_ok = 0
        for u in units["g2"]:
            if u["status"] != "OK":
                continue
            a = key.get((u["game"], u["ply"], u["world"]))
            if a is None:
                continue
            pa = str(u["played_action"])
            if pa in a["arms"] and pa in u["arms"]:
                n_cmp += 1
                n_ok += int(json.dumps(a["arms"][pa], sort_keys=True)
                            == json.dumps(u["arms"][pa], sort_keys=True))
        res["G_CROSS_STAGE"] = {"n_compared": n_cmp, "n_identical": n_ok,
                                "pass": n_cmp > 0 and n_cmp == n_ok}
    res["BRANCH"] = decide(res)
    return res


def g1_readout(units: list, rows: list) -> dict:
    ok = [u for u in units if u["status"] == "OK"]
    bad = [u for u in units if u["status"] != "OK"]
    out = {"n_units": len(units), "n_ok": len(ok), "n_bad": len(bad),
           "attrition": (len(bad) / len(units)) if units else 0.0,
           "bad_detail": [{"game": u["game"], "ply": u["ply"], "world": u["world"],
                           "detail": u.get("detail")} for u in bad[:20]]}
    prim = [u for u in ok if u["profile"] == "fixed_v1"]

    def rates(pool, label):
        if not pool:
            return {"n": 0}
        def arm(u):
            return u["arms"][str(u["played_action"])]
        n = len(pool)
        r = {"n_playouts": n,
             "n_plies": len({(u["game"], u["ply"]) for u in pool})}
        r["R_contest"] = sum(arm(u)["n_rollout_onsets"] > 0 for u in pool) / n
        for cls, tag in (("F", "farm"), ("C", "city"), ("R", "road")):
            r[f"R_{tag}"] = sum(cls in arm(u)["rollout_onset_cls"] for u in pool) / n
        r["R_farm_control"] = sum(arm(u)["n_farm_control_changed"] > 0 for u in pool) / n
        r["R_farmer_zeroed_lost_majority"] = sum(
            arm(u)["n_root_farmer_zero_lost_majority"] > 0 for u in pool) / n
        r["R_farmer_zeroed_no_cities"] = sum(
            arm(u)["n_root_farmer_zero_no_cities"] > 0 for u in pool) / n
        r["mean_onsets_per_playout"] = sum(arm(u)["n_rollout_onsets"] for u in pool) / n
        r["mean_continuation_plies"] = sum(arm(u)["n_continuation_plies"] for u in pool) / n
        # by invader seat
        for seat in ("0", "1", "None"):
            r[f"R_contest_invader_{seat}"] = sum(
                seat in arm(u)["rollout_onset_invaders"] for u in pool) / n
        # mechanism histogram
        mech = defaultdict(int)
        for u in pool:
            for o in arm(u)["rollout_onsets"]:
                mech[o["mech"]] += 1
        r["mech_hist"] = dict(mech)
        # cluster-robust SE on R_contest, clustered on GAME
        by_game = defaultdict(lambda: [0.0, 0])
        for u in pool:
            by_game[u["game"]][0] += float(arm(u)["n_rollout_onsets"] > 0)
            by_game[u["game"]][1] += 1
        r["R_contest_se_cluster_game"] = _cluster_se(by_game)
        r["n_games"] = len(by_game)
        r["label"] = label
        return r

    out["primary_fixed_v1"] = rates(prim, "fixed_v1 pool (PRIMARY)")
    for pname in ("walled", "app_aug2"):
        sub = [u for u in ok if u["profile"] == pname]
        if sub:
            out[f"aside_{pname}"] = rates(sub, f"{pname} (reported apart, never pooled)")
    # per stratum, and per position
    out["by_stratum"] = {}
    for s in sorted({u["stratum"] for u in prim}):
        out["by_stratum"][s] = rates([u for u in prim if u["stratum"] == s], s)
    per_pos = {}
    byply = defaultdict(list)
    for u in prim:
        byply[(u["game"], u["ply"])].append(u)
    hist = defaultdict(int)
    for k, us in byply.items():
        f = sum(u["arms"][str(u["played_action"])]["n_rollout_onsets"] > 0
                for u in us) / len(us)
        per_pos[f"{k[0]}:{k[1]}"] = round(f, 4)
        hist[round(f, 2)] += 1
    out["per_position_R_contest"] = per_pos
    out["per_position_hist"] = {str(k): v for k, v in sorted(hist.items())}
    out["n_positions_zero"] = sum(1 for v in per_pos.values() if v == 0.0)
    out["n_positions"] = len(per_pos)
    return out


def g2_readout(units: list, rows: list) -> dict:
    ok = [u for u in units if u["status"] == "OK"]
    bad = [u for u in units if u["status"] != "OK"]
    byply = defaultdict(list)
    for u in ok:
        byply[(u["game"], u["ply"])].append(u)
    plies = []
    for (game, ply), us in sorted(byply.items()):
        if len(us) < M_WORLDS:
            continue
        u0 = us[0]
        arms = set(us[0]["arms"])
        for u in us:
            arms &= set(u["arms"])
        if not arms:
            continue
        actor = int(u0["actor"])
        vals = {}
        for a in arms:
            m = [u["arms"][a]["margin_p0_minus_p1"] for u in us]
            d = [x if actor == 0 else -x for x in m]
            vals[a] = sum(d) / len(d)
        best = max(sorted(vals, key=lambda a: int(a)), key=lambda a: vals[a])
        plies.append({"game": game, "ply": ply, "stratum": u0["stratum"],
                      "profile": u0["profile"],
                      "n_arms": len(arms), "n_worlds": len(us),
                      "rollout_argmax": int(best),
                      "played_action": int(u0["played_action"]),
                      "counterfactual_action": int(u0["counterfactual_action"]),
                      "counterfactual_agrees": bool(u0["counterfactual_agrees"]),
                      "spread_pts": round(max(vals.values()) - min(vals.values()), 3),
                      "arm_values": {a: round(v, 3) for a, v in vals.items()}})
    prim = [p for p in plies if p["profile"] == "fixed_v1"]

    def dstats(pool, label):
        if not pool:
            return {"n": 0, "label": label}
        n = len(pool)
        return {"label": label, "n_plies": n,
                "D_champ": sum(p["rollout_argmax"] != p["counterfactual_action"]
                               for p in pool) / n,
                "D_owner": sum(p["rollout_argmax"] != p["played_action"]
                               for p in pool) / n,
                "mean_spread_pts": sum(p["spread_pts"] for p in pool) / n,
                "mean_n_arms": sum(p["n_arms"] for p in pool) / n}

    out = {"n_units": len(units), "n_ok": len(ok), "n_bad": len(bad),
           "attrition": (len(bad) / len(units)) if units else 0.0,
           "pooled": dstats(prim, "fixed_v1 all crux plies"),
           "contested": dstats([p for p in prim if p["stratum"] in
                                ("invasion", "farm_capture")],
                               "contested = invasion + farm_capture (THE GATE CUT)"),
           "by_stratum": {s: dstats([p for p in prim if p["stratum"] == s], s)
                          for s in sorted({p["stratum"] for p in prim})},
           "plies": plies}
    return out


def decide(res: dict) -> dict:
    g1 = res.get("G1") or {}
    prim = g1.get("primary_fixed_v1") or {}
    R = prim.get("R_contest")
    voids = []
    if g1.get("attrition", 0) > VOID_ATTRITION:
        voids.append(f"G1 attrition {g1['attrition']:.3f} > {VOID_ATTRITION}")
    if res.get("G2") and res["G2"].get("attrition", 0) > VOID_ATTRITION:
        voids.append(f"G2 attrition {res['G2']['attrition']:.3f} > {VOID_ATTRITION}")
    xs = res.get("G_CROSS_STAGE")
    if xs and not xs["pass"]:
        voids.append("cross-stage determinism failed")
    if voids:
        return {"branch": "VOID", "why": voids}
    if R is None:
        return {"branch": "INCOMPLETE", "why": ["no G1 units"]}
    if R < GATE_R_DEAD:
        return {"branch": "GATE-DEAD", "R_contest": R,
                "why": [f"R_contest {R:.4f} < {GATE_R_DEAD} "
                        f"(= {R / P_REF:.3f} x the banked p_ref {P_REF})"]}
    d = ((res.get("G2") or {}).get("contested") or {}).get("D_champ")
    if R >= GATE_R_LIVE and d is not None and d >= GATE_D_LIVE:
        return {"branch": "GATE-LIVE", "R_contest": R, "D_champ": d}
    return {"branch": "GATE-MIXED", "R_contest": R, "D_champ": d,
            "why": ([f"R_contest {R:.4f} < {GATE_R_LIVE}"] if R < GATE_R_LIVE else []) +
                   ([f"D_champ {d:.4f} < {GATE_D_LIVE}"]
                    if d is not None and d < GATE_D_LIVE else []) +
                   (["G2 not run"] if d is None else [])}


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=("gates", "g1", "g1ext", "g2", "aggregate", "plan"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", default="fixed_v1")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--budget-s", type=float, default=0.0)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    outdir = Path(args.out)
    rows = load_targets()

    if args.stage == "plan":
        by = defaultdict(int)
        for r in rows:
            by[r["profile"]] += 1
        rem = sum(r["n_plies"] - r["ply"] for r in rows)
        print(json.dumps({"n_rows": len(rows), "by_profile": dict(by),
                          "sum_remaining_plies": rem}, indent=2))
        return 0

    if args.stage == "aggregate":
        res = aggregate(outdir, rows)
        txt = json.dumps(res, indent=2, default=str)
        if args.json:
            Path(args.json).write_text(txt)
        print(json.dumps(res["BRANCH"], indent=2, default=str))
        print(json.dumps({k: v for k, v in
                          (res["G1"].get("primary_fixed_v1") or {}).items()
                          if k != "mech_hist"}, indent=2, default=str))
        return 0

    # --- compute stages: one profile per process (R9 is import-latched) ----- #
    from analyzer import ev_loss
    ev_loss.prepare_env(args.profile)
    import carcassonne_ai
    if str(REPO) not in carcassonne_ai.__file__:
        raise RuntimeError(f"carcassonne_ai resolved OUTSIDE the worktree: "
                           f"{carcassonne_ai.__file__}")
    print(f"[env] profile={args.profile} carcassonne_ai={carcassonne_ai.__file__} "
          f"R9={os.environ.get('CARCASSONNE_FIX_R9')}", flush=True)

    if args.stage == "gates":
        g = stage_gates(rows, outdir, args.profile, args.workers)
        return 0 if (g["G_DETECT"]["pass"] and g["G_REPEAT"]["pass"]) else 2

    jobs = jobs_for(args.stage, rows, args.profile)
    st = run_pool(jobs, outdir, args.stage, args.workers, args.budget_s, args.profile)
    print(json.dumps(st), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
