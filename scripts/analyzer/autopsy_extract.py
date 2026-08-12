#!/usr/bin/env python3
"""E4 AUTOPSY — the extraction + stratification stage.

Design doc: measurement/e4_autopsy_20260812/DESIGN.md (written BEFORE any scoring cell
runs).  Cloned from the farm-war discriminator (`farmwar_stratify.py`), with the three
changes the farm-war readout asked for:

  1. **No selection on ΔQ.**  The farm-war population was `bucket in {inaccuracy,
     blunder}` — the tail where the champion disagrees hardest.  Regression to the mean
     then pushes Δ toward 0 on re-scoring, which the readout listed as a threat.  Here
     the population is EVERY disagreement ply of Joshua's seat, and |ΔQ| is a recorded
     covariate rather than a filter.
  2. **DEGENERATE plies are a stratum, not a drop.**  The farm-war run silently dropped
     15 of 70 candidates (21%) because "farm share of the leaf difference" is 0/0 when
     the champion's leaf values the two successors identically.  Those are exactly the
     plies where the disagreement lives in the SEARCH rather than in the leaf, so they
     are the most interesting cell in a discovery design, not the least.
  3. **Structure, not just farms.**  Every arm is tagged with the feature types it
     touches (city / road / cloister / farm), so the census can say WHERE his
     disagreements concentrate before anything is scored.

This module does not score, decide, or promote.  It reads EV-loss artifacts, replays the
archives, tags plies, and writes the census + the position files the scorer consumes.

MIXED RULES EPOCHS.  `CARCASSONNE_FIX_R9` is import-latched (rules_profile.R9_ENV_VAR),
so `emit` handles ONE profile per process and refuses artifacts belonging to another.
`census` and `sample` are pure stdlib and merge the per-epoch files with no engine import.

Modes
-----
  emit    --profile NAME --artifact-dir DIR --out plies_NAME.jsonl
          Engine work.  One rules profile per process.
  census  --inputs plies_*.jsonl --out CENSUS.json [--md CENSUS.md]
          Pure stdlib.  Counts by stratum; no sampling, no scoring.
  sample  --census CENSUS.json --inputs plies_*.jsonl --out SAMPLE.json
          --positions positions.jsonl [--target-effect 1.25] [--sd-points 4.445]
          Pure stdlib.  Power-based per-stratum n, proportional sub-allocation on
          (phase_third x decision_type), deterministic seeded draw.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "human_anchor"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "measurement_infra"))

# MUST precede any `carcassonne_ai` import — same first-import discipline as ev_loss.py.
import env_preamble  # noqa: E402,F401

SCHEMA = "carcassonne-analyzer-e4-autopsy/v1"
DESIGN = "measurement/e4_autopsy_20260812/DESIGN.md"

#: |L_full(S_played) - L_full(S_best)| at or below this makes the ply DEGENERATE: the
#: champion's own leaf cannot tell the two successors apart, so the disagreement is a
#: property of the SEARCH, not of the leaf.  Same epsilon the farm-war stratifier used to
#: DROP such plies (`farmwar_stratify.DEGENERATE_EPS`); here it defines a stratum.
DEGENERATE_EPS = 1e-9

#: The tercile cuts on `k_remaining` (tiles left in the bag).  k_remaining is 70 at ply 0
#: in every archive, so [48,70] / [24,47] / [0,23] splits the 71-tile deck into thirds.
K_OPENING_MIN = 48
K_MIDDLE_MIN = 24

FEATURE_TYPES = ("farm", "cloister", "city", "road")

#: Priority for collapsing a multi-label touch set to ONE disjoint sampling stratum.
#: farm first because it is the standing (unresolved) hypothesis and the only leaf term
#: that is severable; cloister next because it is rare and would otherwise never form a
#: cell; then city, then road.  Stated here, before any result, because the choice
#: determines the cell sizes.
STRUCTURE_PRIORITY = ("farm", "cloister", "city", "road")
NEUTRAL = "neutral"

#: Primary strata, in report order.  DEG is taken FIRST — a degenerate ply is assigned to
#: DEG whatever it touches, because "the leaf is indifferent" is a stronger statement
#: about the instrument than any structural tag.
PRIMARY_STRATA = ("DEG", "FARM", "CLOISTER", "CITY", "ROAD", "NEUTRAL")


# --------------------------------------------------------------------------- #
# Pure helpers — unit-tested in tests/test_e4_autopsy.py                        #
# --------------------------------------------------------------------------- #
def phase_third(k_remaining) -> str:
    """Game phase by tiles remaining in the bag.  Terciles of the 71-tile deck."""
    k = int(k_remaining)
    if k >= K_OPENING_MIN:
        return "opening"
    if k >= K_MIDDLE_MIN:
        return "middle"
    return "endgame"


def is_degenerate(leaf_played: float, leaf_best: float, eps: float = DEGENERATE_EPS) -> bool:
    """True iff the production leaf values the two successors identically.

    Both arguments are the FULL production leaf read from Joshua's seat, so the leaf is
    already a differential (player minus opponent) and the subtraction is like-for-like.
    """
    return abs(float(leaf_played) - float(leaf_best)) <= float(eps)


def collapse_structure(touch_best, touch_played) -> str:
    """One disjoint structural label from the two arms' touch sets.

    The SYMMETRIC DIFFERENCE first: when the arms touch different things, the thing they
    differ ON is what the disagreement is about.  Only when they touch the same set (a
    "where exactly" disagreement rather than a "what kind" one) does the union decide.
    Within either set, `STRUCTURE_PRIORITY` breaks ties.  `neutral` means both arms touch
    nothing scoring-relevant — an empty-board-ish placement, not a missing tag.
    """
    b, p = set(touch_best or ()), set(touch_played or ())
    for pool in (b ^ p, b | p):
        for t in STRUCTURE_PRIORITY:
            if t in pool:
                return t
    return NEUTRAL


def commit_direction(decision_type: str, kind_best: str, kind_played: str) -> str:
    """The meeple-economy axis of a ply: who spends a meeple and who keeps it.

    `n/a` on tile plies (no meeple is at stake).  This is a SECONDARY axis — it does not
    define primary cells — but it is a sub-allocation key, so the scored sample preserves
    its marginals and each direction lands powered rather than incidental.
    """
    if str(decision_type) != "meeple":
        return "n/a"
    b, p = str(kind_best), str(kind_played)
    if b != "pass" and p == "pass":
        return "hold"            # the champion commits a meeple, he keeps his
    if b == "pass" and p != "pass":
        return "spend"           # he commits a meeple, the champion keeps its
    if b != "pass" and p != "pass":
        return "swap"            # both commit, different targets
    return "both_pass"           # both pass, different afterstates (tile-rotation alias)


#: Cuts on the running score differential (F6).  "level" is the +-5 band the pro-strategy
#: scan named; outside it the mover is materially behind or ahead.
SCORE_LEVEL_BAND = 5


def score_diff_bucket(score_diff) -> str:
    """F6 — running margin from the MOVER's seat at decision time.

    Hypothesis under test: his deviations concentrate where the differential is extreme,
    because the leaf maximises margin-EV with no win-probability awareness (a player who
    is 30 ahead should trade margin for certainty; a margin-EV leaf will not).
    """
    d = float(score_diff)
    if d < -SCORE_LEVEL_BAND:
        return "behind"
    if d > SCORE_LEVEL_BAND:
        return "ahead"
    return "level"


def primary_stratum(degenerate: bool, structure: str) -> str:
    """The disjoint primary cell.  DEG dominates; otherwise the structural label."""
    if degenerate:
        return "DEG"
    s = str(structure)
    return "NEUTRAL" if s == NEUTRAL else s.upper()


def size_stratum(n_pop: int, sd_points: float, target_effect: float,
                 z: float = 2.0, n_max: int | None = None) -> dict:
    """Positions to score in one stratum for a |z| >= `z` read on `target_effect` points.

    se = sd/sqrt(n) and we want z*se <= target_effect, so n >= (z*sd/target_effect)^2.
    `sd_points` is the MEASURED per-position spread of Δ from the farm-war run
    (se 0.970 cluster-robust at n=21, M=32 => sd = 0.970*sqrt(21) = 4.445 pts); it is a
    measurement, not an assumption, and it is stamped in the output so a later run can
    re-price against its own realised sd.

    Returns the arithmetic AND the cap that bound it, so an under-powered cell is visible
    as under-powered rather than silently small.
    """
    need = int(math.ceil((float(z) * float(sd_points) / float(target_effect)) ** 2))
    caps = {"n_needed": need, "n_population": int(n_pop)}
    n = min(need, int(n_pop))
    if n_max is not None:
        caps["n_max"] = int(n_max)
        n = min(n, int(n_max))
    binding = ("population" if n == int(n_pop) and n < need
               else "n_max" if n_max is not None and n == int(n_max) and n < need
               else "power")
    return dict(caps, n=int(n), binding=binding,
                se_at_n=(float(sd_points) / math.sqrt(n) if n > 0 else None),
                mde_at_n=(float(z) * float(sd_points) / math.sqrt(n) if n > 0 else None))


def allocate_proportional(counts: dict, total: int) -> dict:
    """Largest-remainder apportionment of `total` across sub-cells, capped by supply.

    Same shape as `run_farmwar.split_workers`, for the same reason: an exact-sum integer
    split that never hands a sub-cell more than it has.
    """
    keys = sorted(counts)
    supply = sum(int(counts[k]) for k in keys)
    total = min(int(total), supply)
    if total <= 0 or supply <= 0:
        return {k: 0 for k in keys}
    exact = {k: total * int(counts[k]) / supply for k in keys}
    share = {k: min(int(counts[k]), int(exact[k])) for k in keys}
    left = total - sum(share.values())
    order = sorted(keys, key=lambda k: (-(exact[k] - int(exact[k])), k))
    i = 0
    while left > 0:
        k = order[i % len(order)]
        if share[k] < int(counts[k]):
            share[k] += 1
            left -= 1
        elif all(share[j] >= int(counts[j]) for j in keys):
            break
        i += 1
    return share


def candidate_plies(artifact: dict) -> list:
    """Joshua's DISAGREEMENT plies — the whole population, unselected on ΔQ.

    Every condition below removes plies for which Δ = V(played) − V(best) is undefined
    rather than small:

      * `actor == human_player` — his seat, read from the artifact, never assumed.
      * NOT `forced` — one legal action, no alternative to score.
      * NOT `exact` — the endgame solver latched (k_remaining <= 2); that tail is already
        graded in true final-score points by a different instrument and must not be
        pooled with a PIMC-root statistic (EV-loss D3).
      * `action_best` / `action_played` present, and `delta_q` present (`played_eligible`).
      * NOT `agrees` — the two arms must be different afterstates.  `agrees` is the
        artifact's own alias-aware test (`action_played_rep` vs `action_best`), so a
        rotation of a symmetric tile that transposes to the champion's own pick is
        correctly NOT a disagreement.
    """
    hp = int(artifact.get("human_player", 0))
    out = []
    for p in artifact.get("plies", []):
        if int(p.get("actor", -1)) != hp:
            continue
        if p.get("forced") or p.get("exact"):
            continue
        if p.get("action_best") is None or p.get("action_played") is None:
            continue
        if p.get("delta_q") is None or not p.get("played_eligible", True):
            continue
        if p.get("agrees"):
            continue
        out.append(p)
    return out


# --------------------------------------------------------------------------- #
# Structural tagging — needs the engine                                         #
# --------------------------------------------------------------------------- #
def _placed_coord(before_state, after_state):
    """The (row, col) the tile landed on, by diffing the boards.  None on a meeple ply."""
    bb, ab = before_state.board, after_state.board
    for r in range(len(ab)):
        for c in range(len(ab[r])):
            if ab[r][c] is not None and bb[r][c] is None:
                return r, c
    return None


def _meeple_touch(root_state, window_size: int, idx: int) -> tuple:
    """(touch set, explicit label) for a meeple arm, DECODED FROM THE ACTION INDEX.

    ⚠️ This deliberately does NOT diff `placed_meeples` before/after.  The first version
    did, and it was WRONG on exactly the plies that matter most: when a meeple placement
    COMPLETES the feature it claims, the engine scores it and RETURNS the meeple in the
    same transition, so the successor's `placed_meeples` is unchanged and the diff reads
    `pass`.  That mislabelled 4 scoring meeple placements as passes (rids
    `g2_161583_p41`, `1785984310_1698417952_p121`, `1786076853_2116173857_p73`,
    `1786511848_634689_p41` — each with a 2-4 point leaf swing, so plainly not passes).
    The action index is exact and immune to it.

    `pass` is a first-class label, not an absence: "the champion places a meeple here and
    he does not" is one of the two things a meeple disagreement can be, and reading it off
    an empty touch set would confuse it with "placed something untaggable".

    There is no `contested` for meeple plies: the rules forbid claiming an occupied
    feature (fields included), so a meeple placement is always on a free region.  Contest
    happens at TILE placements, which merge regions — see `_tile_touch`.
    """
    from carcassonne_ai.action_space import (
        NORMAL_SIDES, meeple_farmer_base, meeple_normal_base, meeple_pass_index,
    )
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    W = int(window_size)
    idx = int(idx)
    if idx == meeple_pass_index(W):
        return set(), "pass"
    if meeple_farmer_base(W) <= idx < meeple_pass_index(W):
        return {"farm"}, "farm"
    nb = meeple_normal_base(W)
    if not (nb <= idx < meeple_farmer_base(W)):
        raise ValueError(f"action {idx} is not a meeple-phase index for window {W}")
    side = NORMAL_SIDES[idx - nb]
    if side == Side.CENTER:
        return {"cloister"}, "cloister"
    lta = getattr(root_state, "last_tile_action", None)
    tile = getattr(lta, "tile", None)
    t = tile.get_type(side) if tile is not None else None
    if t == TerrainType.CITY:
        return {"city"}, "city"
    if t == TerrainType.ROAD:
        return {"road"}, "road"
    return set(), "other"


def _tile_touch(before_state, after_state, coord, mover: int) -> tuple:
    """Feature types a TILE placement engages, plus whether each is already contested.

    Per type, `touch` means the placement is scoring-relevant for that type NOW:

      * **city / road** — the placed tile's side joins a component spanning more than the
        placed tile itself (it extended or merged an existing region), or the component
        it belongs to is FINISHED in the successor (the placement closed it).  A tile
        cannot abut an open city/road edge without supplying the matching edge, so this
        catches every placement that changes an existing region of that type.
      * **cloister** — the placed tile is a chapel, or it fills a cell in the
        8-neighbourhood of an existing chapel tile (the canonical completion condition;
        a structural descriptor, NOT a scoring claim, so it is epoch-independent even
        though `cloister_rule` differs across the three epochs).
      * **farm** — the placed tile's farm component in the successor carries a farmer
        meeple of either player, i.e. the placement grew a field somebody has claimed.
        (Every tile has fields, so an unclaimed field is not a "touch"; without this
        condition the tag would be constant.)

    `contested` records, per touched type, whether the region already carries a meeple of
    either player — the covariate that separates "he builds" from "he fights".
    """
    from carcassonne_ai import flat_leaf
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.side import Side

    touch, contested = set(), set()
    flags = {"reinforce_losing_contest": False, "tie_force_join": False,
             "contest_detail": []}
    if coord is None:
        return touch, contested, flags
    r, c = coord
    d_a = flat_leaf.decompose(after_state)
    tile = after_state.board[r][c]
    opp = 1 - int(mover)

    def _bump(d, root, pl):
        if root is not None:
            d.setdefault(root, [0, 0])[int(pl)] += 1

    # --- meeple -> component root maps, PER PLAYER counts -------------------- #
    city_cnt, road_cnt, farm_cnt = {}, {}, {}
    for pl, lst in enumerate(getattr(after_state, "placed_meeples", None) or []):
        for m in (lst or []):
            cws = getattr(m, "coordinate_with_side", None)
            if cws is None:
                continue
            mr, mc, ms = cws.coordinate.row, cws.coordinate.column, cws.side
            mt = getattr(m, "meeple_type", None)
            if mt in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                _bump(farm_cnt, d_a.farm_pos0_root.get((mr, mc, ms)), pl)
            elif ms != Side.CENTER:
                _bump(city_cnt, d_a.city_side_root.get((mr, mc, ms)), pl)
                _bump(road_cnt, d_a.road_side_root.get((mr, mc, ms)), pl)

    def _note(kind, root, counts, joined):
        """F9 / F2 majority tags for one component the placement engages.

        `reinforce_losing_contest` (F9): the mover adds to a structure whose majority it
        is LOSING OR TIED on — own <= opp with opp > 0.
        `tie_force_join` (F2): the placement NEWLY CONNECTS into a structure where the
        opponent holds SOLE majority — the late majority-steal move class.  `joined` is
        what makes it "newly connects": the component reaches beyond the placed tile.
        """
        own_n, opp_n = counts.get(root, [0, 0])[int(mover)], counts.get(root, [0, 0])[opp]
        if opp_n > 0 and own_n <= opp_n:
            flags["reinforce_losing_contest"] = True
        if joined and opp_n > own_n:
            flags["tie_force_join"] = True
        if own_n or opp_n:
            flags["contest_detail"].append(
                {"kind": kind, "own": own_n, "opp": opp_n, "joined": bool(joined)})

    # --- city / road --------------------------------------------------------- #
    for kind, side_root, root_coords, root_finished, counts in (
            ("city", d_a.city_side_root, d_a.city_root_coords, d_a.city_root_finished,
             city_cnt),
            ("road", d_a.road_side_root, d_a.road_root_coords, d_a.road_root_finished,
             road_cnt)):
        roots = {root for (rr, cc, _s), root in side_root.items() if (rr, cc) == (r, c)}
        for root in roots:
            joined = len(root_coords.get(root, ())) > 1
            if joined or root_finished.get(root):
                touch.add(kind)
                if sum(counts.get(root, [0, 0])) > 0:
                    contested.add(kind)
                _note(kind, root, counts, joined)

    # --- cloister ------------------------------------------------------------ #
    if getattr(tile, "chapel", False):
        touch.add("cloister")
    else:
        board = after_state.board
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < len(board) and 0 <= cc < len(board[rr]):
                    nb = board[rr][cc]
                    if nb is not None and getattr(nb, "chapel", False):
                        touch.add("cloister")
                        for lst in (getattr(after_state, "placed_meeples", None) or []):
                            for m in (lst or []):
                                cws = getattr(m, "coordinate_with_side", None)
                                if (cws is not None and cws.side == Side.CENTER
                                        and (cws.coordinate.row, cws.coordinate.column)
                                        == (rr, cc)):
                                    contested.add("cloister")

    # --- farm ---------------------------------------------------------------- #
    farm_roots = {d_a.farm_anypos_root.get((r, c, pos))
                  for fc in (getattr(tile, "farms", None) or [])
                  for pos in (getattr(fc, "farmer_positions", None) or [])}
    for root in farm_roots - {None}:
        if sum(farm_cnt.get(root, [0, 0])) > 0:
            touch.add("farm")
            contested.add("farm")
            # a field always reaches beyond the placed tile if somebody has claimed it
            # elsewhere, so the join test is the claim itself.
            _note("farm", root, farm_cnt, True)
    return touch, contested, flags


# --------------------------------------------------------------------------- #
# emit — one rules profile per process                                          #
# --------------------------------------------------------------------------- #
def emit(profile_name: str, artifact_paths: list, out_path: Path) -> dict:
    import ev_loss as EV

    env = EV.prepare_env(profile_name)                    # BEFORE carcassonne_ai
    from dataclasses import replace

    import numpy as np
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai import flat_leaf, rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.activate(profile_name)
    leaf_full = CF.production_leaf_cfg()
    CF.verify_leaf(leaf_full)                             # R1/R7-class provenance guard
    leaf_nofarm = replace(leaf_full, farm_base_off=True, farm_growth_off=True)
    bag_close = bool(getattr(leaf_full, "bag_close", False))
    if float(getattr(leaf_full, "v29_farm_flip_k", 0.0)) != 0.0:
        raise RuntimeError(
            "production leaf has v29_farm_flip_k != 0: the F7b knockouts no longer sever "
            "every farm term, so `farm_share` is ill-defined. STOP and re-read DESIGN.md.")

    def leaf(state, player, cfg):
        return float(flat_leaf.flat_virtual_score_v2_float(state, player, cfg, bag_close))

    rows, t0 = [], time.time()
    for ap_ in artifact_paths:
        art = json.loads(Path(ap_).read_text())
        arch_path = resolve_archive_path(art)
        arch = EV.load_archive(arch_path)
        got = EV.resolve_profile_name(arch)
        if got != profile_name:
            raise ValueError(
                f"{ap_}: archive resolves to profile {got!r} but this process is latched "
                f"to {profile_name!r}. R9 is import-latched — run one process per epoch.")

        random.seed(int(arch["deck_seed"]))               # root_replay contract
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        cands = {int(p["ply"]): p for p in candidate_plies(art)}
        label = str(art.get("label"))
        hp = int(art.get("human_player", 0))

        for ply, played in enumerate(arch["actions"]):
            p = cands.get(ply)
            if p is not None:
                st = board.state
                if int(st.current_player) != int(p["actor"]):
                    raise AssertionError(
                        f"{label} ply {ply}: replay actor {st.current_player} != artifact "
                        f"actor {p['actor']} — the replay is not the graded timeline")
                legal = set(int(x) for x in np.flatnonzero(game.get_valid_moves(board)))
                a_played, a_best = int(p["action_played"]), int(p["action_best"])
                if a_played not in legal or a_best not in legal:
                    raise AssertionError(f"{label} ply {ply}: an arm is illegal at the root")
                s_played, _ = game.get_next_state(board, a_played)
                s_best, _ = game.get_next_state(board, a_best)
                rp = int(p["actor"])

                lf_p = leaf(s_played.state, rp, leaf_full)
                lf_b = leaf(s_best.state, rp, leaf_full)
                ln_p = leaf(s_played.state, rp, leaf_nofarm)
                ln_b = leaf(s_best.state, rp, leaf_nofarm)
                degenerate = is_degenerate(lf_p, lf_b)
                total_diff = lf_p - lf_b
                farm_diff = (lf_p - ln_p) - (lf_b - ln_b)

                touch, contested, move_kind, cflags = {}, {}, {}, {}
                for tag, succ, act in (("best", s_best, a_best),
                                       ("played", s_played, a_played)):
                    if p["phase"] == "tiles":
                        coord = _placed_coord(board.state, succ.state)
                        tt, ct, fl = _tile_touch(board.state, succ.state, coord, rp)
                        lab = "tile"
                    else:
                        tt, lab = _meeple_touch(board.state, game.window_size, act)
                        # a meeple may only claim a FREE feature, so a meeple ply can
                        # never reinforce or steal a contested majority.
                        ct, fl = set(), {"reinforce_losing_contest": False,
                                         "tie_force_join": False, "contest_detail": []}
                    touch[tag], contested[tag] = sorted(tt), sorted(ct)
                    move_kind[tag], cflags[tag] = lab, fl

                structure = collapse_structure(touch["best"], touch["played"])
                rows.append({
                    "rid": f"{label}_p{ply}",
                    "root_id": f"{label}_p{ply}",
                    "game_label": label,
                    "rules_profile": profile_name,
                    "archive_path": str(arch_path),
                    "deck_seed": int(arch["deck_seed"]),
                    "ply": int(ply),
                    "root_player": rp,
                    "human_player": hp,
                    # --- EV-loss covariates (recorded, NOT selected on) -------- #
                    "bucket": p["bucket"],
                    "phase": p["phase"],
                    "k_remaining": p.get("k_remaining"),
                    "n_legal": p.get("n_legal"),
                    "alias_group_size": p.get("alias_group_size"),
                    "delta_q": float(p["delta_q"]),
                    "abs_delta_q": abs(float(p["delta_q"])),
                    "delta_points_tanh_est": p.get("delta_points_tanh_est"),
                    "pooled_top2_q_gap": p.get("pooled_top2_q_gap"),
                    # --- strata ------------------------------------------------ #
                    "phase_third": phase_third(p.get("k_remaining")),
                    "decision_type": ("tile" if p["phase"] == "tiles" else "meeple"),
                    "structure": structure,
                    "degenerate": bool(degenerate),
                    "stratum": primary_stratum(degenerate, structure),
                    "touch_best": touch["best"],
                    "touch_played": touch["played"],
                    "contested_best": contested["best"],
                    "contested_played": contested["played"],
                    "move_kind_best": move_kind["best"],
                    "move_kind_played": move_kind["played"],
                    # --- pro-strategy mechanism tags (offline; no extra search) ----- #
                    # F6: running margin from HIS seat at decision time.
                    "score_diff": int(st.scores[rp]) - int(st.scores[1 - rp]),
                    "score_diff_bucket": score_diff_bucket(
                        int(st.scores[rp]) - int(st.scores[1 - rp])),
                    "own_score": int(st.scores[rp]),
                    "opp_score": int(st.scores[1 - rp]),
                    # F3: unplaced-meeple reserves at decision time, both seats.
                    "own_reserve": int(st.meeples[rp]),
                    "opp_reserve": int(st.meeples[1 - rp]),
                    "reserve_diff": int(st.meeples[rp]) - int(st.meeples[1 - rp]),
                    # F9 / F2: majority-contest flags, per arm.
                    "reinforce_losing_contest_best":
                        bool(cflags["best"]["reinforce_losing_contest"]),
                    "reinforce_losing_contest_played":
                        bool(cflags["played"]["reinforce_losing_contest"]),
                    "tie_force_join_best": bool(cflags["best"]["tie_force_join"]),
                    "tie_force_join_played": bool(cflags["played"]["tie_force_join"]),
                    "contest_detail_best": cflags["best"]["contest_detail"],
                    "contest_detail_played": cflags["played"]["contest_detail"],
                    # F7: NOT COMPUTABLE OFFLINE. `ev_loss.grade_pass` reads
                    # `last_move()["pooled"]`, which is ALREADY summed across the k=8
                    # determinizations, so no per-world root value or per-world argmax
                    # survives into the artifact. Recovering cross-world spread would
                    # need a re-search, which this design explicitly does not buy. The
                    # nearest retained quantity is `pooled_top2_q_gap` (top-2 gap WITHIN
                    # the pool) — carried as a covariate and NOT a substitute.
                    "cross_world_spread": None,
                    "cross_world_spread_status": "unavailable_pooled_only",
                    # the meeple-economy axis: who commits a meeple and who declines.
                    "meeple_axis": (None if p["phase"] == "tiles"
                                    else f"{move_kind['best']}->{move_kind['played']}"),
                    "commit_direction": commit_direction(
                        "tile" if p["phase"] == "tiles" else "meeple",
                        move_kind["best"], move_kind["played"]),
                    # --- leaf evidence ----------------------------------------- #
                    "leaf_full_played": lf_p, "leaf_full_best": lf_b,
                    "leaf_nofarm_played": ln_p, "leaf_nofarm_best": ln_b,
                    "total_leaf_diff": total_diff,
                    "farm_leaf_diff": farm_diff,
                    "farm_share": (None if degenerate
                                   else abs(farm_diff) / abs(total_diff)),
                    # --- the scorer's contract --------------------------------- #
                    # A = the champion's pick, B = Joshua's.  position_delta returns
                    # B - A, so `delta` IS the pre-registered Δ = V(played) − V(best).
                    "pick_a": a_best,
                    "pick_b": a_played,
                    "action_best": a_best,
                    "action_played": a_played,
                    "stratifier_rule": "autopsy_v1",
                })
            board, _ = game.get_next_state(board, int(played))

        if arch.get("recorded_scores") and list(board.state.scores) != list(arch["recorded_scores"]):
            print(f"[warn] {label}: replayed scores {list(board.state.scores)} != archived "
                  f"{arch['recorded_scores']}", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    meta = {
        "schema": SCHEMA, "design": DESIGN, "mode": "emit",
        "profile": profile_name,
        "rules_profile_manifest": prof.as_manifest(),
        "r9_env": env,
        "artifacts": [str(a) for a in artifact_paths],
        "n_games": len(artifact_paths),
        "n_disagreements": len(rows),
        "n_degenerate": sum(1 for r in rows if r["degenerate"]),
        "leaf_cfg_hash": CF.resolved_manifest("clairvoyant", verify=True).get("leaf_hash"),
        "v29_farm_flip_k": float(getattr(leaf_full, "v29_farm_flip_k", 0.0)),
        "degenerate_eps": DEGENERATE_EPS,
        "wall_secs": round(time.time() - t0, 2),
    }
    out_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[emit] {profile_name}: {len(rows)} disagreement plies from "
          f"{len(artifact_paths)} games ({meta['n_degenerate']} degenerate) -> {out_path}")
    return meta


#: Where the archives live in-repo, for the non-portable-path fallback below.
E4_GAMES = Path(__file__).resolve().parents[2] / "measurement/e4_games"


def resolve_archive_path(artifact: dict, games_dir: Path = E4_GAMES) -> Path:
    """The archive an EV-loss artifact graded, made portable.

    ⚠️ FOUND 2026-08-12.  `EV_LOSS_1786337185_638286.json` stamps
    ``/home/doctor/e4_run_20260810/deckdir/1786337185_638286.json`` — an absolute path on
    a scratch directory of the LAPTOP, where that game was graded (E4 README: "graded on
    the laptop, pre-seam checkout").  The path does not exist on this box, so any consumer
    that trusts `archive_path` verbatim dies on that one artifact.

    The fallback is by BASENAME into `measurement/e4_games/`, and it is VERIFIED, not
    assumed: the candidate archive's `deck_seed` and final `scores` must match what the
    artifact itself recorded (`plies`/`integrity.recorded_scores`).  A basename collision
    with a different game therefore raises instead of silently grading the wrong archive
    — the same fail-closed posture `ev_loss.resolve_profile_name` takes on rules.
    """
    p = Path(artifact["archive_path"])
    if p.exists():
        return p
    cand = Path(games_dir) / p.name
    if not cand.exists():
        raise FileNotFoundError(
            f"artifact archive_path {p} does not exist and no fallback at {cand}")
    a = json.loads(cand.read_text())
    want_scores = (artifact.get("integrity") or {}).get("recorded_scores")
    got_scores = a.get("scores")
    stem_seed = p.stem.split("_")[-1]
    if str(a.get("deck_seed")) != stem_seed:
        raise ValueError(
            f"fallback archive {cand} has deck_seed {a.get('deck_seed')} but the artifact's "
            f"path stem says {stem_seed} — refusing to grade a different game")
    if want_scores is not None and list(want_scores) != list(got_scores or []):
        raise ValueError(
            f"fallback archive {cand} has scores {got_scores} but the artifact recorded "
            f"{want_scores} — refusing to grade a different game")
    print(f"[emit] NOTE: artifact archive_path {p} is not portable; resolved to {cand} "
          f"(deck_seed + final scores verified)", file=sys.stderr)
    return cand


def artifacts_for_profile(artifact_dir: Path, profile_name: str) -> list:
    """Every EV_LOSS_*.json in `artifact_dir` whose archive resolves to `profile_name`.

    Resolved from each artifact's own stamped `provenance`, never from the filename —
    the 2026-08-05 retraction (ev_loss.resolve_profile_name) is exactly about that.
    """
    import ev_loss as EV
    out = []
    for p in sorted(Path(artifact_dir).glob("EV_LOSS_*.json")):
        art = json.loads(p.read_text())
        if EV.resolve_profile_name(art.get("provenance") or {}) == profile_name:
            out.append(p)
    return out


# --------------------------------------------------------------------------- #
# census — pure stdlib                                                          #
# --------------------------------------------------------------------------- #
def _load(inputs) -> list:
    rows = []
    for p in inputs:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _tab(rows, key) -> dict:
    out = {}
    for r in rows:
        out[str(r.get(key))] = out.get(str(r.get(key)), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _mean(xs):
    xs = [float(x) for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else None


def census(inputs: list, out_path: Path, md_path: Path | None = None) -> dict:
    rows = _load(inputs)
    by_stratum = {}
    for s in PRIMARY_STRATA:
        sub = [r for r in rows if r["stratum"] == s]
        by_stratum[s] = {
            "n": len(sub),
            "n_games": len({r["game_label"] for r in sub}),
            "mean_abs_delta_q": _mean(r["abs_delta_q"] for r in sub),
            "by_phase_third": _tab(sub, "phase_third"),
            "by_decision_type": _tab(sub, "decision_type"),
            "by_bucket": _tab(sub, "bucket"),
            "by_epoch": _tab(sub, "rules_profile"),
            # mechanism-tag crosstabs, so the census can say WHERE each hypothesis's
            # plies live before anything is scored.
            "by_score_diff_bucket": _tab(sub, "score_diff_bucket"),
            "by_commit_direction": _tab(sub, "commit_direction"),
            "mean_own_reserve": _mean(r.get("own_reserve") for r in sub),
            "mean_opp_reserve": _mean(r.get("opp_reserve") for r in sub),
            "n_reinforce_champion": sum(
                1 for r in sub if r.get("reinforce_losing_contest_best")),
            "n_reinforce_human": sum(
                1 for r in sub if r.get("reinforce_losing_contest_played")),
            "n_tie_force_join_champion": sum(
                1 for r in sub if r.get("tie_force_join_best")),
            "n_tie_force_join_human": sum(
                1 for r in sub if r.get("tie_force_join_played")),
        }
    # touch marginals: a ply counts once per type EITHER arm touches
    marg = {t: 0 for t in FEATURE_TYPES}
    marg_contested = {t: 0 for t in FEATURE_TYPES}
    for r in rows:
        for t in set(r["touch_best"]) | set(r["touch_played"]):
            marg[t] += 1
        for t in set(r["contested_best"]) | set(r["contested_played"]):
            marg_contested[t] += 1
    rep = {
        "schema": SCHEMA, "design": DESIGN, "mode": "census",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": [str(p) for p in inputs],
        "n_disagreements": len(rows),
        "n_games": len({r["game_label"] for r in rows}),
        "by_stratum": by_stratum,
        "touch_marginals": marg,
        "contested_marginals": marg_contested,
        "by_phase_third": _tab(rows, "phase_third"),
        "by_decision_type": _tab(rows, "decision_type"),
        "by_bucket": _tab(rows, "bucket"),
        "by_epoch": _tab(rows, "rules_profile"),
        "by_structure": _tab(rows, "structure"),
        # meeple economy: `best->played`, e.g. `road->pass` = the champion commits a
        # meeple to a road and he keeps it in hand.
        "meeple_axis": _tab([r for r in rows if r["decision_type"] == "meeple"],
                            "meeple_axis"),
        "meeple_commit": {
            "champion_places_he_passes": sum(
                1 for r in rows if r["decision_type"] == "meeple"
                and r["move_kind_best"] != "pass" and r["move_kind_played"] == "pass"),
            "he_places_champion_passes": sum(
                1 for r in rows if r["decision_type"] == "meeple"
                and r["move_kind_best"] == "pass" and r["move_kind_played"] != "pass"),
            "both_place_different_targets": sum(
                1 for r in rows if r["decision_type"] == "meeple"
                and r["move_kind_best"] != "pass" and r["move_kind_played"] != "pass"),
        },
        # --- pro-strategy mechanism tags (F6 / F3 / F9 / F2) ------------------- #
        "by_score_diff_bucket": _tab(rows, "score_diff_bucket"),
        "mean_reserve": {
            "own": _mean(r.get("own_reserve") for r in rows),
            "opp": _mean(r.get("opp_reserve") for r in rows),
            "diff": _mean(r.get("reserve_diff") for r in rows),
        },
        "by_own_reserve": _tab(rows, "own_reserve"),
        "by_opp_reserve": _tab(rows, "opp_reserve"),
        "contest_flags": {
            # counted per ARM, because the hypothesis is about WHO reinforces / steals.
            "reinforce_losing_contest_champion":
                sum(1 for r in rows if r.get("reinforce_losing_contest_best")),
            "reinforce_losing_contest_human":
                sum(1 for r in rows if r.get("reinforce_losing_contest_played")),
            "tie_force_join_champion":
                sum(1 for r in rows if r.get("tie_force_join_best")),
            "tie_force_join_human":
                sum(1 for r in rows if r.get("tie_force_join_played")),
            "either_arm_reinforce": sum(
                1 for r in rows if r.get("reinforce_losing_contest_best")
                or r.get("reinforce_losing_contest_played")),
            "either_arm_tie_force_join": sum(
                1 for r in rows if r.get("tie_force_join_best")
                or r.get("tie_force_join_played")),
        },
        "cross_world_spread_status": (
            "UNAVAILABLE — ev_loss.grade_pass reads last_move()['pooled'], already summed "
            "across the k=8 determinizations, so no per-world root value or per-world "
            "argmax survives into the artifact. Recovering it needs a re-search, which "
            "this design does not buy. Nearest retained covariate: pooled_top2_q_gap "
            "(top-2 gap WITHIN the pool), which is NOT cross-world spread."),
        "degenerate_frac": (sum(1 for r in rows if r["degenerate"]) / len(rows)
                            if rows else None),
        "per_game": {g: sum(1 for r in rows if r["game_label"] == g)
                     for g in sorted({r["game_label"] for r in rows})},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rep, indent=2))
    if md_path is not None:
        Path(md_path).write_text(census_markdown(rep))
    print(f"[census] {rep['n_disagreements']} disagreement plies over {rep['n_games']} games")
    for s in PRIMARY_STRATA:
        d = by_stratum[s]
        print(f"[census]   {s:<9} n={d['n']:<5} games={d['n_games']:<3} "
              f"mean|dQ|={d['mean_abs_delta_q']}")
    print(f"[census] -> {out_path}")
    return rep


def _f2(x, nd: int = 2, sign: bool = False) -> str:
    """Format a possibly-absent statistic. An empty stratum yields None, not 0.0, and the
    markdown must say so rather than raise (or, worse, print a fabricated zero)."""
    if x is None:
        return "—"
    return f"{float(x):+.{nd}f}" if sign else f"{float(x):.{nd}f}"


def census_markdown(rep: dict) -> str:
    L = [f"# E4 autopsy — disagreement census", "",
         f"Generated {rep['generated_at']} · design: [DESIGN.md](DESIGN.md)", "",
         f"**{rep['n_disagreements']} disagreement plies** over **{rep['n_games']} games** "
         f"(Joshua's seat; forced, exact-tail and agreeing plies excluded).", "",
         "## Primary strata", "",
         "| stratum | n | games | mean \\|ΔQ\\| | opening/mid/end | tile/meeple | "
         "F6 behind/level/ahead | F9 champ/his | F2 champ/his |",
         "|---|---:|---:|---:|---|---|---|---|---|"]
    for s in PRIMARY_STRATA:
        d = rep["by_stratum"][s]
        ph = d["by_phase_third"]
        dt = d["by_decision_type"]
        mq = "—" if d["mean_abs_delta_q"] is None else f"{d['mean_abs_delta_q']:.4f}"
        sd = d["by_score_diff_bucket"]
        L.append(f"| {s} | {d['n']} | {d['n_games']} | {mq} | "
                 f"{ph.get('opening',0)}/{ph.get('middle',0)}/{ph.get('endgame',0)} | "
                 f"{dt.get('tile',0)}/{dt.get('meeple',0)} | "
                 f"{sd.get('behind',0)}/{sd.get('level',0)}/{sd.get('ahead',0)} | "
                 f"{d['n_reinforce_champion']}/{d['n_reinforce_human']} | "
                 f"{d['n_tie_force_join_champion']}/{d['n_tie_force_join_human']} |")
    L += ["", "## Marginals (a ply counts once per type EITHER arm touches)", "",
          "| type | touched | of which contested |", "|---|---:|---:|"]
    for t in FEATURE_TYPES:
        L.append(f"| {t} | {rep['touch_marginals'][t]} | {rep['contested_marginals'][t]} |")
    mc = rep["meeple_commit"]
    L += ["", "## Meeple economy (meeple plies only, `champion -> Joshua`)", "",
          f"- champion commits a meeple, he passes: **{mc['champion_places_he_passes']}**",
          f"- he commits a meeple, champion passes: **{mc['he_places_champion_passes']}**",
          f"- both commit, different targets: **{mc['both_place_different_targets']}**",
          "", f"Full axis table: `{rep['meeple_axis']}`",
          "", "## Mechanism tags (pro-strategy scan F6 / F3 / F9 / F2)", "",
          f"- **F6** running score differential, his seat: `{rep['by_score_diff_bucket']}`",
          f"- **F3** mean unplaced-meeple reserve — his {_f2(rep['mean_reserve']['own'])} · "
          f"champion {_f2(rep['mean_reserve']['opp'])} · "
          f"diff {_f2(rep['mean_reserve']['diff'], sign=True)}",
          f"- **F9** reinforces a losing/tied majority — champion arm "
          f"**{rep['contest_flags']['reinforce_losing_contest_champion']}** vs his arm "
          f"**{rep['contest_flags']['reinforce_losing_contest_human']}**",
          f"- **F2** newly joins a structure where the opponent holds sole majority — "
          f"champion arm **{rep['contest_flags']['tie_force_join_champion']}** vs his arm "
          f"**{rep['contest_flags']['tie_force_join_human']}**",
          "- **F7** cross-world spread: **UNAVAILABLE** (pooled-only artifacts; "
          "see DESIGN.md §5.4)",
          "", "## Covariates", "",
          f"- phase third: `{rep['by_phase_third']}`",
          f"- decision type: `{rep['by_decision_type']}`",
          f"- EV-loss bucket: `{rep['by_bucket']}`",
          f"- rules epoch: `{rep['by_epoch']}`",
          f"- degenerate fraction: **{_f2(rep['degenerate_frac'], nd=3)}**",
          ""]
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# sample — pure stdlib                                                          #
# --------------------------------------------------------------------------- #
def sample(inputs: list, out_path: Path, positions_path: Path, *,
           target_effect: float, sd_points: float, z: float, n_max: int | None,
           seed: int, min_n: int) -> dict:
    rows = _load(inputs)
    chosen, sizing = [], {}
    for s in PRIMARY_STRATA:
        pool = sorted((r for r in rows if r["stratum"] == s),
                      key=lambda r: (r["game_label"], r["ply"]))
        size = size_stratum(len(pool), sd_points, target_effect, z=z, n_max=n_max)
        size["underpowered"] = bool(size["n"] < min_n)
        sizing[s] = size
        if not pool or size["n"] <= 0:
            continue
        # Proportional sub-allocation so the SECONDARY marginals of the scored sample
        # match the stratum's own, then a seeded draw inside each sub-cell.  The key is
        # three-part — (phase third, decision type, commit direction) — so the
        # meeple-economy axis is preserved by construction and each of hold / spend /
        # swap lands with a usable n instead of whatever the draw happened to give.
        sub = {}
        for r in pool:
            sub.setdefault((r["phase_third"], r["decision_type"],
                            r.get("commit_direction", "n/a"),
                            r.get("score_diff_bucket", "level")), []).append(r)
        alloc = allocate_proportional({k: len(v) for k, v in sub.items()}, size["n"])
        rng = random.Random(f"{seed}:{s}")
        for k in sorted(sub):
            take = alloc.get(k, 0)
            if take <= 0:
                continue
            picks = sorted(rng.sample(range(len(sub[k])), take))
            for i in picks:
                rec = dict(sub[k][i])
                # "|" not "/": the commit_direction level for tile plies is literally
                # "n/a", so a "/" join produces an ambiguous, unsplittable label.
                rec["sample_subcell"] = "|".join(k)
                chosen.append(rec)
    ordered = sorted(chosen, key=lambda r: (r["rules_profile"], r["rid"]))
    rep = {
        "schema": SCHEMA, "design": DESIGN, "mode": "sample",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": [str(p) for p in inputs],
        "sizing_rule": {
            "formula": "n >= (z * sd_points / target_effect)^2",
            "z": float(z), "target_effect_points": float(target_effect),
            "sd_points": float(sd_points),
            "sd_source": ("farm-war READOUT: cluster-robust se 0.970 pts at n=21, M=32 "
                          "=> sd = 0.970*sqrt(21) = 4.445 pts/position"),
            "n_max": n_max, "min_n_floor": int(min_n), "sample_seed": int(seed),
        },
        "sizing": sizing,
        "n_selected": len(ordered),
        "underpowered_strata": [s for s in PRIMARY_STRATA if sizing[s]["underpowered"]],
        "per_epoch": {p: sum(1 for r in ordered if r["rules_profile"] == p)
                      for p in sorted({r["rules_profile"] for r in ordered})},
        "per_stratum": {s: sum(1 for r in ordered if r["stratum"] == s)
                        for s in PRIMARY_STRATA},
        # SECONDARY axes: same scored positions, no extra compute. The 2σ MDE is stamped
        # per level so an under-powered secondary read is visible before it is quoted.
        "secondary_power": {
            axis: {
                lvl: {"n": n,
                      "mde_2sigma_points": (z * sd_points / math.sqrt(n)) if n else None}
                for lvl, n in sorted(
                    ((v, sum(1 for r in ordered if str(r.get(axis)) == v))
                     for v in {str(r.get(axis)) for r in ordered}),
                    key=lambda kv: -kv[1])
            }
            for axis in ("commit_direction", "phase_third", "decision_type",
                         "bucket", "rules_profile", "score_diff_bucket",
                         "reinforce_losing_contest_played", "tie_force_join_played",
                         "reinforce_losing_contest_best", "tie_force_join_best")
        },
        "per_game": {g: sum(1 for r in ordered if r["game_label"] == g)
                     for g in sorted({r["game_label"] for r in ordered})},
    }
    positions_path.parent.mkdir(parents=True, exist_ok=True)
    with positions_path.open("w") as fh:
        for r in ordered:
            fh.write(json.dumps(r) + "\n")
    # ...and one file PER EPOCH: `CARCASSONNE_FIX_R9` is an import-time latch, so the
    # scorer must run one process per rules profile.  Splitting here keeps that split in
    # the artifact rather than in a launcher's shell loop (the farm-war convention).
    files = {}
    for prof in sorted({r["rules_profile"] for r in ordered}):
        p = positions_path.with_name(f"{positions_path.stem}_{prof}.jsonl")
        with p.open("w") as fh:
            for r in ordered:
                if r["rules_profile"] == prof:
                    fh.write(json.dumps(r) + "\n")
        files[prof] = str(p)
    rep["positions_files"] = files
    rep["positions"] = str(positions_path)
    out_path.write_text(json.dumps(rep, indent=2))
    print(f"[sample] {len(ordered)} positions across {len(files)} epochs")
    for s in PRIMARY_STRATA:
        d = sizing[s]
        flag = "  ⚠ UNDERPOWERED" if d["underpowered"] else ""
        mde = "—" if d["mde_at_n"] is None else f"{d['mde_at_n']:.2f}"
        print(f"[sample]   {s:<9} n={d['n']:<4} (need {d['n_needed']}, pop {d['n_population']}, "
              f"binding={d['binding']}) 2σ-MDE={mde} pts{flag}")
    print(f"[sample] -> {out_path} / {positions_path}")
    return rep


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    e = sub.add_parser("emit", help="engine pass, ONE rules profile per process")
    e.add_argument("--profile", required=True)
    e.add_argument("--artifact-dir", default="measurement/analyzer_evloss_20260805")
    e.add_argument("--artifact", action="append", default=None,
                   help="explicit EV_LOSS_*.json (repeatable); default = every artifact "
                        "in --artifact-dir that resolves to --profile")
    e.add_argument("--out", required=True)

    c = sub.add_parser("census", help="counts by stratum; no sampling, no scoring")
    c.add_argument("--inputs", nargs="+", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--md", default=None)

    s = sub.add_parser("sample", help="power-based per-stratum draw -> positions jsonl")
    s.add_argument("--inputs", nargs="+", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--positions", required=True)
    s.add_argument("--target-effect", type=float, default=1.25,
                   help="points/ply the design is powered to see at |z|>=z (default 1.25, "
                        "the midpoint of the +1.0..+1.5 range the design targets)")
    s.add_argument("--sd-points", type=float, default=4.445,
                   help="MEASURED per-position sd of Δ (farm-war: se 0.970 at n=21)")
    s.add_argument("--z", type=float, default=2.0)
    s.add_argument("--n-max", type=int, default=None,
                   help="hard cap per stratum (compute budget), applied after power")
    s.add_argument("--min-n", type=int, default=15,
                   help="below this a stratum is flagged underpowered-by-construction")
    s.add_argument("--seed", type=int, default=20260812)

    a = ap.parse_args(argv)
    if a.mode == "emit":
        arts = ([Path(x) for x in a.artifact] if a.artifact
                else artifacts_for_profile(Path(a.artifact_dir), a.profile))
        if not arts:
            print(f"[emit] no artifacts resolve to profile {a.profile!r}", file=sys.stderr)
            return 3
        emit(a.profile, arts, Path(a.out))
        return 0
    if a.mode == "census":
        census([Path(p) for p in a.inputs], Path(a.out),
               Path(a.md) if a.md else None)
        return 0
    rep = sample([Path(p) for p in a.inputs], Path(a.out), Path(a.positions),
                 target_effect=a.target_effect, sd_points=a.sd_points, z=a.z,
                 n_max=a.n_max, seed=a.seed, min_n=a.min_n)
    return 0 if rep["n_selected"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
