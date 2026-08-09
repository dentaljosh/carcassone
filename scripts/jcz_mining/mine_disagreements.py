#!/usr/bin/env python3
"""JCZ DISAGREEMENT MINING — the extractor + stratifier (PREREG §2, §3, §4).

Pre-registration: ``measurement/jcz_mining_20260809/MINING_PREREG.md`` (committed
BEFORE anything here ran against ``confirm.jsonl``). This module implements the
disagreement SCREEN and the STRATA and nothing else; it does not score, decide, or
promote. House pattern: ``scripts/analyzer/farmwar_stratify.py``.

THE SCREEN IS FREE, AND THAT IS THE DESIGN
------------------------------------------
JCZ's ``LegacyAiPlayer`` is a one-turn breadth-first enumeration of the acting
player's own action chain ranked by ONE static evaluation of the resulting state.
So **JCZ's played move IS its evaluator's argmax**, already stamped in the archive.
We never boot the JVM here — we only compute what *we* prefer at the same state.

Mined plies: every ``moves[i]`` with ``seat == jcz_seat`` and
``kind in {jcz_tile, jcz_meeple, jcz_meeple_pass}``. Excluded by construction:
``jcz_meeple_pass_implicit`` (JCZ had no option — not a decision),
``tile_pass_redraw`` (forced), champion-actor plies (PREREG §2.3), any root whose
legal set has size 1 (forced), and any root whose top-2 leaf values tie exactly
(PREREG §7 rider 9 — "our preferred move" is not well defined there).

THE TWO POSITION CLASSES (PREREG §2.2)
--------------------------------------
==========  ==========================================================
TILE        root = a ``jcz_tile`` ply. ``pick_a = argmax_t [max_m leaf(s∘t∘m)]``
            where the inner max runs over the successor's legal actions ONLY
            when the successor is still ``jcz_seat``'s turn (the meeple
            decision); otherwise the chain value is ``leaf(s∘t)``. This makes
            our tile choice chain-optimal in exactly the sense JCZ's BFS is.
MEEPLE      root = a ``jcz_meeple`` / ``jcz_meeple_pass`` ply. The tile is
            already down; ``pick_a = argmax_a leaf(s∘a)`` over all legal
            actions INCLUDING pass. No instrument asymmetry at all.
==========  ==========================================================

``pick_b = actions[i]`` — their pick. A candidate exists iff ``pick_a != pick_b``.

SIGN CONTRACT (the whole deliverable turns on it). ``pick_a`` is OURS and
``pick_b`` is THEIRS, because ``oracle_score_pilot.position_delta`` returns
``mean(V_B − V_A)`` — so the reported Δ reads "their pick minus our pick" and
**Δ > 0 means their pick was better** (PREREG §5).

THE ALIGNMENT GATE (the free ground truth)
------------------------------------------
Every replayed root is checked three ways before it is used: ``moves[i].action ==
actions[i]``; the replayed state's current player equals ``moves[i].seat``; and —
when the ply carries a ``jcz_message`` — that RAW JCZ WIRE PAYLOAD is re-inverted
through ``match.py``'s own ``invert_tile_message`` / ``invert_meeple_message`` /
``invert_pass`` against OUR replayed position's legal-move set, and must yield the
action int the archive recorded. That proves our replayed position is the same
position JCZ was standing in — for free, with no JVM. A failure is FATAL for the
game (recorded in the meta, the game skipped), never silently continued.

PREREG AMBIGUITIES AND WHAT WAS CHOSEN (stated here, not buried)
----------------------------------------------------------------
1. **Their chain's meeple leg on the TILE class.** §2.2 defines their pick as
   ``actions[ply]`` and leaves the chain's second leg implicit. Roughly 40% of
   JCZ tile plies are followed by ``jcz_meeple_pass_implicit`` (JCZ had no meeple
   option; our engine still owes a pass-only MEEPLES ply). Taking their chain to
   be tile-only there while ours runs to the end of the turn would compare a
   mid-turn state against an end-of-turn state and could make ``our_leaf_gap``
   negative — breaking the §3.3 "≥ 0 by construction" invariant that the CONTROL
   match rests on. So the rule here is STRUCTURAL and symmetric: their chain
   takes ``actions[i+1]`` **iff the replayed successor of ``actions[i]`` is still
   ``jcz_seat``'s turn**, which is exactly the condition our inner max uses. The
   ply's kind is then asserted to be one of the three meeple kinds at that seat.
   Both arms are therefore the same chain space and ``our_leaf_gap >= 0`` holds.
2. **``k_remaining``.** Read as ``fair_agent.k_remaining(state)`` = ``len(deck) +
   (1 if next_tile is not None)`` — undrawn deck PLUS the tile in hand. That is
   the house definition used by every other measurement artifact (L2-3 bands,
   ev_loss, the census), so ``K_LATE`` here is the same axis as everywhere else.
3. **``merge_exposure_differs``** (recorded, never decisive — PREREG §3.4). Exact
   definition: over each arm's successor state, count the distinct EMPTY board
   cells that are adjacent to two or more DISTINCT city components, plus the
   distinct empty cells adjacent to two or more distinct road components (city
   and road counted separately then summed; adjacency = the outward neighbour of
   a component's own edge, i.e. the same ``_OPP`` step ``decompose`` uses for
   ``*_root_open_n``). The boolean is ``count(ours) != count(theirs)``.
4. **``leaf_tie``** is evaluated on the OUTER per-action chain values (the values
   the argmax actually ranks), not on the inner meeple values.
5. **STRATA.json carries no wall-clock timestamp** — ``assign`` is a pure
   deterministic function of its inputs and the test suite pins that byte-exactly.
6. ⚠️ **The live closure schedule is NOT the one §3.0's prose assumes.** §3.0 says
   "the production schedule is ``{1: 0.5, 2: 0.2}`` ⇒ ``open_n >= 3`` is exactly
   0 (the v2.7 ``DROP_THREE_OPEN`` decision)". The actual production leaf resolves
   to ``closure_p == {1: 0.5, 2: 0.2, 3: 0.05}`` — ``env_preamble`` exports
   ``CARCASSONNE_V25_DROP_THREE_OPEN=0``, so a 3-open city/cloister is **LIVE**,
   not DEAD. Nothing here is changed to compensate: §3.0's *rule* is "``DEAD`` iff
   the leaf prices closure at exactly zero, read from the loaded config, never
   hardcoded", and that rule is what is implemented. The prose's worked example is
   simply stale, and this is precisely the silent invalidation the read-from-cfg
   mandate exists to prevent. The resolved table is stamped in the meta as
   ``closure_p`` so the readout reports the schedule it actually ran under.
7. ⚠️ **The CONTROL match is exact on ``(ply_class, phase_bucket)``, where §3.3
   says ``ply_class`` alone.** This is a DELIBERATE AMENDMENT, taken 2026-08-09
   from the full-corpus dry run's PLY COUNTS ALONE — before any world was drawn,
   any deck completed, or any Δ computed — and therefore a decision on the
   sampling frame that cannot bias the effect estimate, exactly as §3.2's
   pre-registered widening ladder is. The reason: STRAT-B is late-deck by
   construction (its gate IS ``k_remaining <= K_LATE``; measured median 9) while
   its unbucketed nearest-neighbour control landed mid-game (median 36, 2 of 80
   at ``k_remaining <= 14``), so the pre-registered B-minus-C contrast was
   confounded with game phase and B could only ever EXONERATE or be
   uninterpretable. See `phase_bucket`. The PREREG carries a stamped note.

Modes
-----
  extract --corpus confirm.jsonl --out cand.jsonl [--limit-games N]
                                                  [--with-search-pick]
        Engine work, under the ``fixed_v1`` + R9 env latch. One row per
        disagreement + a sibling ``.meta.json`` with the agreement rates.
  counts  --candidates cand.jsonl [--k-late 14]
        Pure stdlib DRY RUN. No outcome, no world, no Δ — it reads ply counts
        only, which is what makes the PREREG §3.2 widening ladder an
        unbiased decision on the sampling frame.
  assign  --candidates cand.jsonl --out STRATA.json --positions positions.jsonl
        Pure stdlib. Precedence A > B > pool, ≤1 scored position per game,
        CONTROL by nearest-neighbour ``our_leaf_gap`` matching without
        replacement (exact on ``ply_class`` AND ``phase_bucket`` — see
        amendment 7), then the n≥25 gate.
  search-pick --strata STRATA.json --positions POSITIONS.jsonl [--workers N]
        Engine work, but over the SAMPLED rows only (160, ~3 min) rather than
        every candidate (6,800, ~2 h). Backfills the context-only `search_pick`
        column in place, idempotent + resumable, and asserts the pre-registered
        sampling frame survived byte-for-byte. Run immediately before the scorer.
"""
from __future__ import annotations

# ⚠️ STDLIB ONLY at module level. `carcassonne_ai` must NOT be imported before
# `CARCASSONNE_FIX_R9` is exported (base_deck latches it at import into a Rust
# OnceLock). `extract` does the export; `counts`/`assign` never import the engine.
import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
JCZ_MATCH = SCRIPTS / "jcz_match"
JCZ_ORACLE = SCRIPTS / "jcz_oracle"          # tile_map / jcz_driver / replay_diff
MEASUREMENT_INFRA = SCRIPTS / "measurement_infra"
HUMAN_ANCHOR = SCRIPTS / "human_anchor"

for _p in (str(SCRIPTS), str(JCZ_MATCH), str(JCZ_ORACLE), str(MEASUREMENT_INFRA),
           str(HUMAN_ANCHOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA_CANDIDATES = "carcassonne-jcz-mining-candidates/v1"
SCHEMA_STRATA = "carcassonne-jcz-mining-strata/v1"
PREREG = "measurement/jcz_mining_20260809/MINING_PREREG.md"

#: NOT a knob. The only rules configuration in which the two engines agree (leg D).
PROFILE = "fixed_v1"

#: The mined kinds (PREREG §2). `jcz_meeple_pass_implicit` and `tile_pass_redraw`
#: are decisions for nobody and are excluded by construction.
TILE_KINDS = ("jcz_tile",)
MEEPLE_KINDS = ("jcz_meeple", "jcz_meeple_pass")
MINED_KINDS = TILE_KINDS + MEEPLE_KINDS
#: Every kind that can legally be the meeple leg of a JCZ turn chain (see docstring
#: ambiguity 1 — the implicit pass IS part of their chain even though it is not a
#: decision, because our engine still owes the ply and the leaf moves across it).
CHAIN_MEEPLE_KINDS = MEEPLE_KINDS + ("jcz_meeple_pass_implicit",)

#: The four feature classes `DEAD` is defined over (PREREG §3.0).
MEEPLE_CLASSES = ("FIELD", "ROAD", "CITY", "CLOISTER")

#: `our_leaf_gap >= 0` is true by construction; this is the float slack allowed.
GAP_EPS = 1e-9

STRAT_A, STRAT_B, STRAT_C = "STRAT_A", "STRAT_B", "STRAT_C"

#: The CONTROL match is EXACT on these fields and nearest on `our_leaf_gap`. Named
#: as data so `STRATA.json` reports how C was actually built and a readout can never
#: misdescribe it. See `phase_bucket` for why the second field is here.
MATCH_KEY = ("ply_class", "phase_bucket")


# --------------------------------------------------------------------------- #
# hashing — house convention (oracle_score_pilot._sha_int), NEVER Python hash()  #
# --------------------------------------------------------------------------- #
def _sha_int(*parts) -> int:
    """Stable 31-bit integer from the given parts. NEVER `hash()` (PYTHONHASHSEED-
    salted), so the within-stratum ordering reproduces across machines, processes
    and Python builds. Byte-identical to `oracle_score_pilot._sha_int` — pinned in
    `tests/test_jcz_mining_extract.py`."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFF


def order_key(row: dict) -> tuple:
    """PREREG §4: "candidates are ordered by a deterministic hash of
    ``(deck_seed, champ_seat, ply)`` — never Python ``hash()``". `rid` breaks the
    (astronomically unlikely) hash collision so the order is a total order."""
    return (_sha_int("jcz_mining_order", row["deck_seed"], row["champ_seat"], row["ply"]),
            str(row["rid"]))


# --------------------------------------------------------------------------- #
# the primitive: DEAD  (PREREG §3.0)  — pure, no engine                         #
# --------------------------------------------------------------------------- #
def closure_p_of(cfg) -> dict:
    """The closure schedule, READ FROM THE LOADED CONFIG. Never hardcoded — a leaf
    change must not be able to silently invalidate the stratifier (PREREG §3.0)."""
    return dict(getattr(cfg, "closure_p", None) or {})


def meeple_is_dead(mclass: str, cfg, *, finished: bool = False,
                   open_n=None, needed=None) -> bool:
    """PREREG §3.0, one row at a time. Pure arithmetic over `cfg.closure_p`.

    FIELD  — always DEAD (farms never close; the leaf's farm-growth block credits
             the adjacent CITY, never the farmer's return).
    ROAD   — always DEAD (open and closed road points are equal ⇒ Δ = 0; roads are
             absent from `flat_closure_bonus` by design).
    CITY   — DEAD iff finished, or `open_n <= 0` (D16 unclosable edge city), or
             the schedule prices `open_n` at exactly zero.
    CLOISTER — `needed = 8 - _surrounding_count(...)`; DEAD iff `needed <= 0` or
             the schedule prices `needed` at exactly zero.
    """
    if mclass not in MEEPLE_CLASSES:
        raise ValueError(f"unknown meeple class {mclass!r}")
    if mclass in ("FIELD", "ROAD"):
        return True
    p = closure_p_of(cfg)
    if mclass == "CITY":
        if finished:
            return True
        if open_n is None or int(open_n) <= 0:
            return True
        return float(p.get(int(open_n), 0.0)) == 0.0
    # CLOISTER
    if needed is None or int(needed) <= 0:
        return True
    return float(p.get(int(needed), 0.0)) == 0.0


# --------------------------------------------------------------------------- #
# strata predicates (PREREG §3.1 / §3.2) — pure, no engine                       #
# --------------------------------------------------------------------------- #
def _norm_dead(vec) -> dict:
    """Zero entries are not information: {FIELD:1, ROAD:0} == {FIELD:1}."""
    return {str(k): int(v) for k, v in dict(vec or {}).items() if int(v)}


def _norm_live(vec) -> dict:
    """Accepts either the in-process Counter keyed by `(class, n)` or the JSON-safe
    `[[[class, n], count], ...]` list a row carries, and returns one canonical
    dict — so the predicate cannot read differently before and after a round-trip
    through disk (the exact silent failure this normalisation exists to stop)."""
    if vec is None:
        return {}
    items = vec.items() if isinstance(vec, dict) else [(k, v) for k, v in vec]
    out = {}
    for k, v in items:
        if not int(v):
            continue
        cls, n = (k[0], k[1]) if isinstance(k, (list, tuple)) else (k, 0)
        out[(str(cls), int(n))] = int(v)
    return out


def dead_vecs_differ(a, b) -> bool:
    return _norm_dead(a) != _norm_dead(b)


def live_vecs_differ(a, b) -> bool:
    return _norm_live(a) != _norm_live(b)


def phase_bucket(row: dict, k_late: int) -> str:
    """``"LATE"`` iff ``k_remaining <= k_late``, else ``"EARLY"``. Same threshold and
    the same inclusive boundary as STRAT-B's own gate, so the bucket is not a new
    axis — it is B's defining axis, made available to the matcher.

    Added 2026-08-09, from PLY COUNTS ALONE, before any world was drawn or any Δ
    computed. The full-corpus dry run showed STRAT-B is late-deck BY CONSTRUCTION
    (median `k_remaining` 9) while its nearest-neighbour control landed mid-game
    (median 36, only 2 of 80 at `k_remaining <= 14`). That makes the B-minus-C
    contrast confounded with game phase: if per-ply Δ is systematically larger late
    — plausible, since fewer tiles left means more decisive positions — B could
    clear CONVICT for phase reasons that have nothing to do with S2's deck-graded
    closure probability, so as built B could only ever EXONERATE or be
    uninterpretable. Matching exactly on the bucket costs no extra positions and no
    extra compute, and because A is mostly EARLY and B is entirely LATE it
    phase-matches BOTH primary strata instead of neither."""
    return "LATE" if int(row["k_remaining"]) <= int(k_late) else "EARLY"


def stratum_for(row: dict, k_late: int):
    """PREREG §3: mutually exclusive, first match wins, A > B > pool.

    Returns ``STRAT_A``, ``STRAT_B`` or ``None`` (the CONTROL pool). ``STRAT_B``'s
    ``k_remaining <= K_LATE`` is inclusive at the boundary — `K_LATE = 14` is
    JCZ's own phase constant (`totalSize > 14` at 2 players), so 14 itself is in
    the region where their phase behaviour differs from ours."""
    if dead_vecs_differ(row.get("dead_vec_ours"), row.get("dead_vec_theirs")):
        return STRAT_A
    if (live_vecs_differ(row.get("live_vec_ours"), row.get("live_vec_theirs"))
            and int(row["k_remaining"]) <= int(k_late)):
        return STRAT_B
    return None


# --------------------------------------------------------------------------- #
# engine-side helpers (imported lazily by `extract`)                             #
# --------------------------------------------------------------------------- #
def prepare_env(profile: str = PROFILE) -> dict:
    """Export the import-latched rules env, THEN the production leaf env, THEN
    return. MUST be called before any `carcassonne_ai` import — the same mechanism
    `match.py` uses, imported rather than re-implemented."""
    import match as JM                                   # stdlib-only at module level
    env = JM.export_profile_env(profile)
    import env_preamble                                  # noqa: F401  leaf env
    return {**env, "leaf_env": dict(env_preamble.RESOLVED)}


def meeple_vectors(state, player: int, cfg, decomp=None):
    """``(dead_vec, live_vec)`` for `player` in `state` — PREREG §3.0/§3.1/§3.2.

    The class discrimination MIRRORS `flat_closure_bonus`'s own meeple loop
    (terrain CITY ⇒ CITY; terrain CHAPEL/FLOWERS ⇒ CLOISTER; meeple_type
    FARMER/BIG_FARMER ⇒ FIELD; everything else ⇒ ROAD), in that order, so the
    stratifier and the leaf can never disagree about what class a meeple is.

    `dead_vec` counts DEAD meeples by class. `live_vec` counts the non-DEAD ones
    by `(class, open_n_or_needed)`.
    """
    from carcassonne_ai import flat_leaf
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    if decomp is None:
        decomp = flat_leaf.decompose(state)
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0

    dead = {c: 0 for c in MEEPLE_CLASSES}
    live: Counter = Counter()
    for mp in state.placed_meeples[player]:
        cws = mp.coordinate_with_side
        r = cws.coordinate.row
        c = cws.coordinate.column
        side = cws.side
        terrain = board[r][c].get_type(side)
        if terrain == TerrainType.CITY:
            root = decomp.city_side_root.get((r, c, side))
            finished = True if root is None else bool(decomp.city_root_finished[root])
            open_n = 0 if root is None else int(decomp.city_root_open_n[root])
            mclass, n = "CITY", open_n
            is_dead = meeple_is_dead("CITY", cfg, finished=finished, open_n=open_n)
        elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
            needed = 8 - flat_leaf._surrounding_count(state, r, c, H, W)
            mclass, n = "CLOISTER", int(needed)
            is_dead = meeple_is_dead("CLOISTER", cfg, needed=needed)
        elif mp.meeple_type == MeepleType.FARMER or mp.meeple_type == MeepleType.BIG_FARMER:
            mclass, n = "FIELD", 0
            is_dead = True
        else:
            mclass, n = "ROAD", 0
            is_dead = True
        if is_dead:
            dead[mclass] += 1
        else:
            live[(mclass, n)] += 1
    return dead, live


def live_vec_json(live) -> list:
    """JSON-safe `live_vec`: a SORTED list of ``[[class, n], count]``. Sorted so the
    on-disk form is canonical and two equal vectors are equal as JSON too."""
    return [[[str(k[0]), int(k[1])], int(v)] for k, v in sorted(live.items())]


def merge_exposure_count(state, decomp=None) -> int:
    """Distinct empty cells exposed to ≥2 distinct components of the SAME class,
    summed over cities and roads. See module docstring ambiguity 3 for the exact
    definition. Cheap covariate for S3 — recorded, never decisive (PREREG §3.4)."""
    from carcassonne_ai import flat_leaf

    if decomp is None:
        decomp = flat_leaf.decompose(state)
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0

    def _count(side_root_map) -> int:
        cells: dict = {}
        for (r, c, side), root in side_root_map.items():
            step = flat_leaf._OPP.get(flat_leaf._SIDE_IX[side])
            if step is None:                       # CENTER / half-sides: no border
                continue
            dr, dc, _o = step
            nr, nc = r + dr, c + dc
            if 0 <= nr < H and 0 <= nc < W and board[nr][nc] is None:
                cells.setdefault((nr, nc), set()).add(root)
        return sum(1 for roots in cells.values() if len(roots) >= 2)

    return _count(decomp.city_side_root) + _count(decomp.road_side_root)


def chain_values(game, board, jcz_seat: int, leaf, ply_class: str) -> list:
    """Every legal outer action's CHAIN value, in ascending action order.

    Returns ``[(action, value, chain), ...]``. On the TILE class the chain runs to
    the end of JCZ's turn: apply `t`, and if the successor is STILL `jcz_seat`'s
    turn (the meeple decision) take the best legal meeple action; otherwise the
    chain is the tile alone. On the MEEPLE class every chain is one action.
    """
    import numpy as np

    out = []
    for a in (int(x) for x in np.flatnonzero(game.get_valid_moves(board))):
        s1, _ = game.get_next_state(board, a)
        if ply_class == "TILE" and int(s1.state.current_player) == int(jcz_seat):
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
    """``(pick, value, chain, leaf_tie)`` from `chain_values`' output.

    Ties on the argmax resolve to the LOWEST action index (the list is already in
    ascending action order and the comparison is strict ``>``). ``leaf_tie`` is
    true iff the top TWO chain values are exactly equal as floats — such a ply is
    excluded from the candidate pool, because "our preferred move" is not well
    defined there and admitting it would manufacture disagreements out of a
    tie-break convention (PREREG §7 rider 9)."""
    best = None
    for a, v, chain in values:
        if best is None or v > best[1]:
            best = (a, v, chain)
    ranked = sorted((v for _a, v, _c in values), reverse=True)
    tie = len(ranked) >= 2 and ranked[0] == ranked[1]
    return best[0], best[1], best[2], tie


def _search_pick(game, board, deck_seed: int, champ_seat: int, actions, ply: int) -> int:
    """The production champion's FULL-SEARCH action at this root (PREREG §2.1).

    CONTEXT ONLY — a third column, never a decision input. It answers the cheap
    version of the sims-washout question (rider R2): "on the plies where their leaf
    beat our leaf, did our search already find their move anyway?"

    The champion answers from JCZ's chair — `choose_action` acts for the board's
    own `current_player`, which at a mined root is always `jcz_seat` — because the
    question is what OUR agent would play from THIS information set. ⚠️ The rust
    mirror cannot be constructed
    from an arbitrary mid-game board — only replayed — so `mirror_protocol.reseat`
    is mandatory here (a direct `start_game` on the root raises "cannot seat a
    mirror on a board with N pre-placed tiles"). `move_idx` is not cosmetic: the
    per-determinization seeds derive from it, so a mirror replayed to ply N with a
    move counter still reading 0 searches DIFFERENT worlds.

    Caller wraps this in try/except: it is strictly best-effort and must never be
    able to abort a run (~1.5 s/root at k8×1376, which is why it is opt-in).
    """
    import match as JM
    from carcassonne_ai import mirror_protocol as MP
    from carcassonne_ai.champion_factory import make_production_champion

    ex = MP.resolve_execution("auto")
    champ = make_production_champion("fair", game=game,
                                     seed=JM.agent_seed(deck_seed, champ_seat),
                                     verify=True, **ex.factory_kwargs())
    MP.reseat(champ, deck_seed=int(deck_seed), actions=[int(a) for a in actions[:ply]],
              move_idx=int(ply))
    return int(champ.choose_action(board))


# --------------------------------------------------------------------------- #
# search-pick — backfill the context-only third column over SAMPLED rows only    #
# --------------------------------------------------------------------------- #
#: The two fields `search-pick` is allowed to write. EVERYTHING else in a sampled
#: row is a pre-registered, committed sampling frame and is asserted unchanged.
BACKFILL_FIELDS = ("search_pick", "search_pick_error")

_SP: dict = {}


def _frame_of(row: dict) -> dict:
    """A row minus the two backfill fields — its sampling-frame fingerprint."""
    return {k: v for k, v in row.items() if k not in BACKFILL_FIELDS}


def assert_frame_unchanged(before: list, after: list, where: str) -> None:
    """Raise unless the ONLY thing the backfill touched is `BACKFILL_FIELDS`.

    Asserted, not trusted, and pulled out as its own function so the guard itself
    is unit-testable. The sampling frame is pre-registered and committed; a
    backfill that silently perturbed it — a reordered row, a coerced int, a dropped
    key — would not look like an error, it would look like a result. That is the
    worst failure available at this point in the pipeline, so it gets a hard stop."""
    if len(before) != len(after):
        raise AssertionError(f"{where}: row count changed {len(before)} -> {len(after)}")
    for i, (b, a) in enumerate(zip(before, after)):
        if b != a:
            keys = sorted(set(b) ^ set(a)) or [k for k in b if b[k] != a.get(k)]
            raise AssertionError(
                f"{where}: the backfill changed a NON-{'/'.join(BACKFILL_FIELDS)} "
                f"field on row {i} (differing keys: {keys}) — the sampling frame is "
                "pre-registered and must survive this rewrite byte-for-byte. STOP.")


def _sp_init() -> None:
    """Spawn-worker bootstrap: rules env, then leaf env, then the engine."""
    prepare_env(PROFILE)
    from carcassonne_ai import rules_profile
    prof = rules_profile.activate(PROFILE)
    if not prof.as_manifest().get("r9_env_ok"):
        raise RuntimeError("CARCASSONNE_FIX_R9 is not on — wrong rules epoch for this corpus")
    _SP["game_kwargs"] = prof.game_kwargs()


def _sp_cell(item: tuple) -> tuple:
    """One root -> ``(rid, search_pick, error)``. Best-effort by contract: a failure
    is a null column plus a string, never an exception that reaches the driver."""
    rid, deck_seed, champ_seat, actions, ply = item
    try:
        import root_replay as RR
        g, board = RR.replay_actions(int(deck_seed), actions, int(ply),
                                     game_kwargs=_SP["game_kwargs"])
        return rid, _search_pick(g, board, int(deck_seed), int(champ_seat), actions,
                                 int(ply)), None
    except Exception as exc:                                     # noqa: BLE001
        return rid, None, f"{type(exc).__name__}: {exc}"


def _atomic_write_json(path: Path, obj) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=False))
    os.replace(tmp, path)


def _atomic_write_jsonl(path: Path, rows: list) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
    os.replace(tmp, path)


def _patch_positions(path: Path, picks: dict) -> dict:
    """Rewrite one positions file in place, touching ONLY the backfill fields.

    The frame is re-asserted per row after patching (not just trusted), because a
    backfill that silently perturbed the sampling frame — a re-ordered row, a
    coerced int, a dropped key — would be the worst available failure here: the
    frame is pre-registered and committed, and a perturbation would not look like
    an error, it would look like a result."""
    rows = [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    before = [_frame_of(r) for r in rows]
    n = 0
    for r in rows:
        got = picks.get(r["rid"])
        if got is not None and r.get("search_pick") is None:
            r["search_pick"], r["search_pick_error"] = got
            n += 1
    assert_frame_unchanged(before, [_frame_of(r) for r in rows], str(path))
    _atomic_write_jsonl(Path(path), rows)
    return {"path": str(path), "n_rows": len(rows), "n_written": n}


def search_pick_backfill(strata_path: Path, positions_path: Path,
                         positions_ab_path: Path | None = None,
                         workers: int = 1) -> dict:
    """Backfill `search_pick` over the SAMPLED rows only (PREREG §2.1 / §3.4).

    WHY A SEPARATE PASS. `extract --with-search-pick` would run the champion over
    every candidate — 6,800 roots at ~1.1 s each, ~2 h — which is not proportionate
    for a column that never enters a decision. The sampled frame is 160 roots,
    ~3 min. So the column is backfilled after `assign`, against the rows that will
    actually be scored, and the roots are rebuilt through the SAME
    `root_replay.replay_actions` + `prof.game_kwargs()` path `extract` uses, so the
    root is bit-identical to the one the scorer will replay.

    WHAT IT BUYS. Rider R2's sims-washout question, cheaply: on the plies where
    their leaf beat our leaf, did our 11008-sim search already find their move
    anyway? It is CONTEXT ONLY and enters no predicate in the decision map.

    IDEMPOTENT AND RESUMABLE: a row that already carries a non-null `search_pick`
    is skipped, so an interrupted run resumes and a second run is a no-op. Writes
    go through tmp + `os.replace`, so a kill can never leave a half-written frame.
    """
    strata_path = Path(strata_path)
    strata = json.loads(strata_path.read_text())
    all_rows = [r for k in (STRAT_A, STRAT_B, STRAT_C) for r in strata["rows"].get(k, [])]
    frame_before = {r["rid"]: _frame_of(r) for r in all_rows}
    todo = [r for r in all_rows if r.get("search_pick") is None]

    print(f"[search-pick] {len(all_rows)} sampled rows, {len(todo)} to compute, "
          f"{len(all_rows) - len(todo)} already done (workers={workers})")

    picks: dict = {}
    t0 = time.time()
    if todo:
        items = [(r["rid"], r["deck_seed"], r["champ_seat"], r["actions"], r["ply"])
                 for r in todo]
        if int(workers) <= 1:
            _sp_init()
            results = [_sp_cell(it) for it in items]
        else:
            import multiprocessing as mp
            ctx = mp.get_context("spawn")
            with ctx.Pool(int(workers), initializer=_sp_init) as pool:
                results = pool.map(_sp_cell, items, chunksize=1)
        for rid, pick, err in results:
            picks[rid] = (pick, err)

    for r in all_rows:
        got = picks.get(r["rid"])
        if got is not None and r.get("search_pick") is None:
            r["search_pick"], r["search_pick_error"] = got

    # THE guard: the frame is pre-registered and committed. Assert it, do not trust it.
    assert_frame_unchanged([frame_before[r["rid"]] for r in all_rows],
                           [_frame_of(r) for r in all_rows], str(strata_path))

    n_ok = sum(1 for r in all_rows if r.get("search_pick") is not None)
    n_err = sum(1 for r in all_rows if r.get("search_pick_error"))
    agree_ours = sum(1 for r in all_rows if r.get("search_pick") == r["pick_a"])
    agree_theirs = sum(1 for r in all_rows if r.get("search_pick") == r["pick_b"])
    summary = {
        "n_sampled": len(all_rows),
        "n_computed_this_run": len(picks),
        "n_with_search_pick": n_ok,
        "n_errors": n_err,
        # The R2 read, per stratum. CONTEXT ONLY — it enters no predicate.
        "search_agrees_with_ours": agree_ours,
        "search_agrees_with_theirs": agree_theirs,
        "search_agrees_with_neither": n_ok - agree_ours - agree_theirs,
        "by_stratum": {
            k: {
                "n": len(strata["rows"].get(k, [])),
                "with_search_pick": sum(1 for r in strata["rows"].get(k, [])
                                        if r.get("search_pick") is not None),
                "agrees_with_ours": sum(1 for r in strata["rows"].get(k, [])
                                        if r.get("search_pick") == r["pick_a"]),
                "agrees_with_theirs": sum(1 for r in strata["rows"].get(k, [])
                                          if r.get("search_pick") == r["pick_b"]),
            } for k in (STRAT_A, STRAT_B, STRAT_C)
        },
        "wall_secs": round(time.time() - t0, 2),
    }
    # Additive TOP-LEVEL metadata only. The byte-identical guarantee this pass owes
    # is about ROWS (the sampling frame); the summary is a new sibling key so a
    # readout never has to recompute the R2 column from the rows.
    strata["search_pick_backfill"] = summary
    _atomic_write_json(strata_path, strata)

    files = [_patch_positions(Path(positions_path), picks)]
    if positions_ab_path is None:
        guess = Path(positions_path)
        guess = guess.with_name(guess.stem + "_AB" + guess.suffix)
        positions_ab_path = guess if guess.exists() else None
    if positions_ab_path is not None:
        files.append(_patch_positions(Path(positions_ab_path), picks))
    summary["positions_files"] = files

    print(f"[search-pick] wrote {n_ok}/{len(all_rows)} picks ({n_err} errors) in "
          f"{summary['wall_secs']}s -> {strata_path}")
    for f in files:
        print(f"[search-pick]   {f['path']}: {f['n_written']} of {f['n_rows']} rows patched")
    print(f"[search-pick] R2 read (CONTEXT ONLY): our search picked OURS "
          f"{agree_ours}, THEIRS {agree_theirs}, neither "
          f"{n_ok - agree_ours - agree_theirs}")
    for k in (STRAT_A, STRAT_B, STRAT_C):
        s = summary["by_stratum"][k]
        print(f"[search-pick]   {k:<8} n={s['n']:>3}  ours={s['agrees_with_ours']:>3}  "
              f"theirs={s['agrees_with_theirs']:>3}")
    print("[search-pick] sampling frame verified UNCHANGED outside "
          f"{list(BACKFILL_FIELDS)}")
    return summary


# --------------------------------------------------------------------------- #
# the alignment gate                                                            #
# --------------------------------------------------------------------------- #
def alignment_check(game, board, move: dict, action: int, tile_map, origin) -> dict:
    """Re-invert JCZ's OWN wire payload in OUR independently replayed position.

    This is the ground-truth check the frame buys for free: if our replayed board
    were a different position from the one JCZ was standing in, its recorded
    `jcz_message` would not invert to the action the archive recorded (or would
    not invert at all). Uses `match.py`'s inverters — the same functions that
    produced the archive — never a private re-implementation.

    Returns ``{"checked", "ok", "inverted", "reason"}``. ``checked`` is False for
    a ply with no `jcz_message` (nothing to re-invert; not a failure).
    """
    import match as JM

    msg = move.get("jcz_message")
    kind = str(move.get("kind"))
    if msg is None and kind != "jcz_meeple_pass":
        return {"checked": False, "ok": True, "inverted": None, "reason": "no jcz_message"}
    try:
        if kind == "jcz_tile":
            got, offered = JM.invert_tile_message(game, board, tile_map, msg, origin)
        elif kind == "jcz_meeple":
            got, offered = JM.invert_meeple_message(game, board, msg)
        elif kind == "jcz_meeple_pass":
            got, offered = JM.invert_pass(game, board)
        else:
            return {"checked": False, "ok": True, "inverted": None,
                    "reason": f"kind {kind} carries no invertible payload"}
    except Exception as exc:                                       # noqa: BLE001
        return {"checked": True, "ok": False, "inverted": None,
                "reason": f"{type(exc).__name__}: {exc}"}
    if got is None:
        return {"checked": True, "ok": False, "inverted": None,
                "reason": f"unmappable in our replayed position: {json.dumps(offered)[:400]}"}
    if int(got) != int(action):
        return {"checked": True, "ok": False, "inverted": int(got),
                "reason": f"re-inverted to {int(got)} but the archive recorded {int(action)}"}
    return {"checked": True, "ok": True, "inverted": int(got), "reason": None}


# --------------------------------------------------------------------------- #
# extract                                                                       #
# --------------------------------------------------------------------------- #
def extract(corpus: Path, out_path: Path, limit_games=None,
            with_search_pick: bool = False) -> dict:
    env = prepare_env(PROFILE)                        # BEFORE any carcassonne_ai import
    import numpy as np                                # noqa: F401  (chain_values uses it)

    import match as JM
    import root_replay as RR
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai import fair_agent, flat_leaf, rules_profile
    from tile_map import load_tile_mapping

    prof = rules_profile.activate(PROFILE)
    manifest = prof.as_manifest()
    if not manifest.get("r9_env_ok"):
        raise RuntimeError(
            "CARCASSONNE_FIX_R9 is not on: the corpus is fixed_v1+R9 and any other "
            "combination is a DIFFERENT rules epoch (VALIDATION_REPORT leg D). Export "
            "it BEFORE importing carcassonne_ai.")
    game_kwargs = prof.game_kwargs()

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)                               # R1/R7-class provenance guard
    leaf_hashes = dict(CF.resolved_manifest("clairvoyant", verify=True)
                       .get("leaf_hashes") or {})
    bag_close = bool(getattr(cfg, "bag_close", False))
    closure_p = closure_p_of(cfg)

    def leaf(state, seat):
        # PRE-ROUND float, always from the ACTING player's point of view, so ties
        # are real ties and not quantisation artifacts (PREREG §2.2).
        return float(flat_leaf.flat_virtual_score_v2_float(state, int(seat), cfg, bag_close))

    tile_map = load_tile_mapping()

    rows: list = []
    stats = {
        "games_seen": 0, "games_used": 0, "games_skipped_alignment": 0,
        "skipped_games": [],
        "plies_inspected": {"TILE": 0, "MEEPLE": 0},
        "agreements": {"TILE": 0, "MEEPLE": 0},
        "disagreements": {"TILE": 0, "MEEPLE": 0},
        "leaf_tie": {"TILE": 0, "MEEPLE": 0},
        "forced_n_legal_1": {"TILE": 0, "MEEPLE": 0},
        "alignment_checked": 0, "alignment_ok": 0, "alignment_failed": 0,
        "alignment_failures": [],
        "search_pick_ok": 0, "search_pick_error": 0,
    }
    t0 = time.time()

    for line in Path(corpus).read_text().splitlines():
        if not line.strip():
            continue
        if limit_games is not None and stats["games_seen"] >= int(limit_games):
            break
        rec = json.loads(line)
        stats["games_seen"] += 1
        if rec.get("void"):
            stats["skipped_games"].append({"deck_seed": rec.get("deck_seed"),
                                           "reason": f"void={rec['void']}"})
            continue
        deck_seed = int(rec["deck_seed"])
        champ_seat = int(rec["champ_seat"])
        jcz_seat = int(rec["jcz_seat"])
        actions = [int(a) for a in rec["actions"]]
        moves = rec["moves"]
        root_id = f"{deck_seed}_{champ_seat}"

        # Per-game counters, folded into `stats` only if the game SURVIVES the
        # alignment gate — a skipped game must not leave half its plies in the meta.
        game_rows: list = []
        game_stats = {k: {"TILE": 0, "MEEPLE": 0} for k in
                      ("plies_inspected", "agreements", "disagreements",
                       "leaf_tie", "forced_n_legal_1")}
        game_align = {"checked": 0, "ok": 0}
        aborted = None

        for i, mv in enumerate(moves):
            kind = str(mv.get("kind"))
            if int(mv.get("seat", -1)) != jcz_seat or kind not in MINED_KINDS:
                continue
            ply_class = "TILE" if kind in TILE_KINDS else "MEEPLE"

            # --- 1. rebuild the root (the SAME function the scorer replays with) ---
            g, board = RR.replay_actions(deck_seed, actions, i, game_kwargs=game_kwargs)
            origin = (g.start_row, g.start_col)

            # --- 2. the alignment gate ---------------------------------------- #
            if int(mv["action"]) != actions[i]:
                aborted = {"ply": i, "reason": f"moves[{i}].action {mv['action']} != "
                                               f"actions[{i}] {actions[i]}"}
                break
            if int(board.state.current_player) != int(mv["seat"]):
                aborted = {"ply": i, "reason": f"replayed current_player "
                                               f"{board.state.current_player} != "
                                               f"moves[{i}].seat {mv['seat']}"}
                break
            chk = alignment_check(g, board, mv, actions[i], tile_map, origin)
            if chk["checked"]:
                game_align["checked"] += 1
                if chk["ok"]:
                    game_align["ok"] += 1
                else:
                    aborted = {"ply": i, "kind": kind, "reason": chk["reason"]}
                    break

            game_stats["plies_inspected"][ply_class] += 1

            # --- 3. forced roots ------------------------------------------------ #
            legal = [int(x) for x in np.flatnonzero(g.get_valid_moves(board))]
            n_legal = len(legal)
            if n_legal <= 1:
                game_stats["forced_n_legal_1"][ply_class] += 1
                continue

            # --- 4. k_remaining -------------------------------------------------- #
            k_remaining = int(fair_agent.k_remaining(board.state))

            # --- 5. our pick ------------------------------------------------------ #
            vals = chain_values(g, board, jcz_seat, lambda st: leaf(st, jcz_seat), ply_class)
            pick_a, leaf_ours, chain_ours, leaf_tie = argmax_chain(vals)
            if leaf_tie:
                game_stats["leaf_tie"][ply_class] += 1
                continue

            # --- 6. their pick + their chain -------------------------------------- #
            pick_b = int(actions[i])
            s1, _ = g.get_next_state(board, pick_b)
            chain_theirs = [pick_b]
            if ply_class == "TILE" and int(s1.state.current_player) == jcz_seat:
                nxt = moves[i + 1] if i + 1 < len(moves) else None
                if (nxt is None or int(nxt.get("seat", -1)) != jcz_seat
                        or str(nxt.get("kind")) not in CHAIN_MEEPLE_KINDS):
                    aborted = {"ply": i, "reason": (
                        "their tile leaves the turn with JCZ but moves[i+1] is not a "
                        f"JCZ meeple leg: {None if nxt is None else nxt.get('kind')}")}
                    break
                chain_theirs.append(int(actions[i + 1]))

            # --- 7. the disagreement screen --------------------------------------- #
            if pick_a == pick_b:
                game_stats["agreements"][ply_class] += 1
                continue
            game_stats["disagreements"][ply_class] += 1

            # --- 8. the two arm successor states ----------------------------------- #
            s_ours = board
            for a in chain_ours:
                s_ours, _ = g.get_next_state(s_ours, int(a))
            s_theirs = board
            for a in chain_theirs:
                s_theirs, _ = g.get_next_state(s_theirs, int(a))
            leaf_theirs = leaf(s_theirs.state, jcz_seat)
            our_leaf_gap = leaf_ours - leaf_theirs
            if our_leaf_gap < -GAP_EPS:
                raise AssertionError(
                    f"{root_id} ply {i}: our_leaf_gap {our_leaf_gap} < 0 — our chain "
                    "argmax lost to their chain, which is impossible if both chains "
                    "live in the same space. The chain-space rule is broken; STOP.")

            # --- 9. strata primitives on BOTH arms ---------------------------------- #
            d_ours = flat_leaf.decompose(s_ours.state)
            d_theirs = flat_leaf.decompose(s_theirs.state)
            dead_ours, live_ours = meeple_vectors(s_ours.state, jcz_seat, cfg, d_ours)
            dead_theirs, live_theirs = meeple_vectors(s_theirs.state, jcz_seat, cfg, d_theirs)
            merge_differs = (merge_exposure_count(s_ours.state, d_ours)
                             != merge_exposure_count(s_theirs.state, d_theirs))

            # --- 10. optional context-only search pick ------------------------------ #
            search_pick, search_err = None, None
            if with_search_pick:
                try:
                    search_pick = _search_pick(g, board, deck_seed, champ_seat,
                                               actions, i)
                    stats["search_pick_ok"] += 1
                except Exception as exc:                            # noqa: BLE001
                    search_err = f"{type(exc).__name__}: {exc}"
                    stats["search_pick_error"] += 1

            game_rows.append({
                "schema": SCHEMA_CANDIDATES,
                "rid": f"{deck_seed}_{champ_seat}_p{i}",
                "root_id": root_id,
                "game_label": root_id,
                "deck_seed": deck_seed,
                "champ_seat": champ_seat,
                "jcz_seat": jcz_seat,
                "ply": int(i),
                "root_player": jcz_seat,
                "actions": actions,
                "ply_class": ply_class,
                "pick_a": int(pick_a),
                "pick_b": int(pick_b),
                "n_legal": int(n_legal),
                "k_remaining": int(k_remaining),
                "leaf_ours": float(leaf_ours),
                "leaf_theirs": float(leaf_theirs),
                "our_leaf_gap": float(our_leaf_gap),
                "leaf_tie": False,
                "dead_vec_ours": dead_ours,
                "dead_vec_theirs": dead_theirs,
                "live_vec_ours": live_vec_json(live_ours),
                "live_vec_theirs": live_vec_json(live_theirs),
                "merge_exposure_differs": bool(merge_differs),
                "chain_ours": [int(a) for a in chain_ours],
                "chain_theirs": [int(a) for a in chain_theirs],
                "rules_profile": PROFILE,
                "search_pick": search_pick,
                "search_pick_error": search_err,
                "stratum": None,
            })

        if aborted is not None:
            # FATAL for this game: the replayed position is not provably the one JCZ
            # stood in, so nothing from it may enter the pool. Recorded, never silent.
            stats["games_skipped_alignment"] += 1
            stats["alignment_failed"] += 1
            stats["alignment_failures"].append({"root_id": root_id, **aborted})
            stats["skipped_games"].append({"root_id": root_id, "reason": "alignment"})
            continue

        stats["games_used"] += 1
        stats["alignment_checked"] += game_align["checked"]
        stats["alignment_ok"] += game_align["ok"]
        for key, sub in game_stats.items():
            for cls, v in sub.items():
                stats[key][cls] += v
        rows.extend(game_rows)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    meta = {
        "schema": SCHEMA_CANDIDATES + "-meta",
        "prereg": PREREG,
        "corpus": str(corpus),
        "limit_games": None if limit_games is None else int(limit_games),
        "with_search_pick": bool(with_search_pick),
        "n_rows": len(rows),
        "rules_profile": PROFILE,
        "rules_manifest": manifest,
        "r9_env": env,
        "leaf_cfg_hash": leaf_hashes.get("harness_leaf_hash"),
        "leaf_hashes": leaf_hashes,
        "closure_p": {str(k): float(v) for k, v in sorted(closure_p.items())},
        "bag_close": bag_close,
        "wall_secs": round(time.time() - t0, 2),
        **stats,
    }
    for cls in ("TILE", "MEEPLE"):
        seen = stats["agreements"][cls] + stats["disagreements"][cls]
        meta.setdefault("agreement_rate", {})[cls] = (
            (stats["agreements"][cls] / seen) if seen else None)
    out_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))

    print(f"[extract] games {stats['games_used']}/{stats['games_seen']} used "
          f"({stats['games_skipped_alignment']} skipped on alignment)")
    for cls in ("TILE", "MEEPLE"):
        print(f"[extract] {cls:<7} inspected {stats['plies_inspected'][cls]:>5} | "
              f"agree {stats['agreements'][cls]:>5} | disagree "
              f"{stats['disagreements'][cls]:>5} | leaf_tie {stats['leaf_tie'][cls]:>4} | "
              f"forced {stats['forced_n_legal_1'][cls]:>4} | "
              f"agreement_rate {meta['agreement_rate'][cls]}")
    print(f"[extract] alignment gate: {stats['alignment_ok']}/{stats['alignment_checked']} "
          f"ok, {stats['alignment_failed']} FAILED")
    print(f"[extract] {len(rows)} candidates -> {out_path} ({meta['wall_secs']}s)")
    return meta


# --------------------------------------------------------------------------- #
# counts — the pure-stdlib dry run (PREREG §3.2 widening ladder)                 #
# --------------------------------------------------------------------------- #
def load_candidates(path) -> list:
    out = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def count_frame(rows: list, k_late: int) -> dict:
    """Counts only — no outcome, no world, no Δ. The BINDING constraint is the
    number of DISTINCT GAMES contributing to a stratum, because sampling takes at
    most one scored position per game (PREREG §4)."""
    buckets = {STRAT_A: [], STRAT_B: [], "POOL": []}
    for r in rows:
        r = dict(r, phase_bucket=phase_bucket(r, k_late))
        buckets[stratum_for(r, k_late) or "POOL"].append(r)
    out = {
        "k_late": int(k_late),
        "n_candidates": len(rows),
        "by_ply_class": dict(Counter(r["ply_class"] for r in rows)),
        "strata": {},
    }
    for name, rs in buckets.items():
        out["strata"][name] = {
            "n": len(rs),
            "n_distinct_games": len({r["root_id"] for r in rs}),
            "by_ply_class": dict(Counter(r["ply_class"] for r in rs)),
            "by_phase_bucket": dict(Counter(r["phase_bucket"] for r in rs)),
            # The CONTROL match is exact on this pair, so the pool's supply per
            # cell is what actually gates C's n — report it, not just the totals.
            "by_match_key": dict(Counter(
                f"{r['ply_class']}/{r['phase_bucket']}" for r in rs)),
            "by_jcz_seat": dict(Counter(str(r["jcz_seat"]) for r in rs)),
        }
    # The pre-registered widening ladder, readable in one shot: STRAT-B steps
    # K_LATE 14 -> 20 -> 28, stopping at the first value clearing 30 games.
    ladder = {}
    for k in (14, 20, 28):
        b = [r for r in rows if stratum_for(r, k) == STRAT_B]
        ladder[str(k)] = {"n": len(b), "n_distinct_games": len({r["root_id"] for r in b})}
    out["strat_b_ladder"] = ladder
    out["strat_b_ladder_choice"] = next(
        (k for k in ("14", "20", "28") if ladder[k]["n_distinct_games"] >= 30), None)
    return out


def counts(candidates: Path, k_late: int, as_json: bool) -> dict:
    rows = load_candidates(candidates)
    frame = count_frame(rows, k_late)
    meta_path = Path(candidates).with_suffix(".meta.json")
    if meta_path.exists():
        m = json.loads(meta_path.read_text())
        frame["extract_meta"] = {k: m.get(k) for k in (
            "games_used", "games_seen", "plies_inspected", "agreements",
            "disagreements", "agreement_rate", "leaf_tie", "forced_n_legal_1",
            "alignment_checked", "alignment_ok", "alignment_failed", "leaf_cfg_hash")}
    if as_json:
        print(json.dumps(frame, indent=2))
        return frame
    print(f"[counts] candidates {frame['n_candidates']} "
          f"({', '.join(f'{k}={v}' for k, v in sorted(frame['by_ply_class'].items()))})")
    for name in (STRAT_A, STRAT_B, "POOL"):
        s = frame["strata"][name]
        print(f"[counts] {name:<8} n={s['n']:>4}  distinct_games={s['n_distinct_games']:>4}"
              f"  {sorted(s['by_match_key'].items())}  "
              f"seats={sorted(s['by_jcz_seat'].items())}")
    print(f"[counts] STRAT-B widening ladder (distinct games is the binding constraint):")
    for k in ("14", "20", "28"):
        L = frame["strat_b_ladder"][k]
        print(f"[counts]   K_LATE={k:>2}  n={L['n']:>4}  distinct_games="
              f"{L['n_distinct_games']:>4}  {'CLEARS 30' if L['n_distinct_games'] >= 30 else ''}")
    print(f"[counts] pre-registered ladder choice: K_LATE="
          f"{frame['strat_b_ladder_choice'] or 'NONE CLEARS 30 (report and stop)'}")
    if "extract_meta" in frame:
        em = frame["extract_meta"]
        print(f"[counts] (extract: {em['games_used']}/{em['games_seen']} games, "
              f"agreement_rate {em['agreement_rate']}, alignment "
              f"{em['alignment_ok']}/{em['alignment_checked']} ok)")
    return frame


# --------------------------------------------------------------------------- #
# assign — strata, sampling, control matching (PREREG §3.3, §4)                  #
# --------------------------------------------------------------------------- #
def _pick_balanced(ordered: list, claimed: set, n_target: int) -> list:
    """Fill toward `n_target` from `ordered`, ≤1 position per game, balancing
    `jcz_seat` to within ±1 (PREREG §4).

    Two passes on purpose: the first accepts only candidates that keep the seat
    split within ±1; the second tops up from the ones that pass deferred, so a
    stratum that is genuinely one-sided still reaches its n instead of silently
    coming in short. Both passes walk the SAME deterministic order."""
    chosen: list = []
    deferred: list = []
    cnt = {0: 0, 1: 0}
    for r in ordered:
        if len(chosen) >= n_target:
            break
        if r["root_id"] in claimed:
            continue
        s = int(r["jcz_seat"])
        if (cnt[s] + 1) - cnt[1 - s] <= 1:
            chosen.append(r)
            claimed.add(r["root_id"])
            cnt[s] += 1
        else:
            deferred.append(r)
    for r in deferred:
        if len(chosen) >= n_target:
            break
        if r["root_id"] in claimed:
            continue
        chosen.append(r)
        claimed.add(r["root_id"])
        cnt[int(r["jcz_seat"])] += 1
    return chosen


def _match_key(row: dict) -> tuple:
    return tuple(row[f] for f in MATCH_KEY)


def match_control(targets: list, pool: list, claimed: set | None = None) -> list:
    """Nearest-neighbour CONTROL matching on `our_leaf_gap`, WITHOUT replacement,
    EXACT on `MATCH_KEY` = `(ply_class, phase_bucket)` (PREREG §3.3).

    Ordering discipline mirrors `farmwar_stratify.match_control` exactly: targets
    are consumed in DESCENDING `our_leaf_gap` (ties broken by `(root_id, ply,
    rid)`), and each takes the still-unused pool member with the SAME match key
    minimising `|gap_target - gap_pool|` (same tie-break). Descending order gives
    the hardest-to-match targets first pick, which is what makes the matched
    distributions closest; taking them last would strand them.

    Both exact fields are load-bearing, and for the same reason — each blocks a way
    for the A/B-minus-C contrast to silently become a contrast about something
    else. Without `ply_class`, a stratum could be all-MEEPLE and its control
    all-TILE and the contrast would read TILE-vs-MEEPLE. Without `phase_bucket`,
    STRAT-B (late-deck by construction) would draw a mid-game control and the
    contrast would read late-vs-mid-game; see `phase_bucket` for the measured
    numbers that forced this. A target with no same-key pool member left is SKIPPED
    (truncation), never matched across the key and never given a reused partner.
    `claimed` (games already holding a scored position) is honoured, and each pick
    claims its own game — the ≤1-per-game rule holds inside C too."""
    used = set(claimed or ())
    remaining = sorted(pool, key=lambda r: (str(r["root_id"]), int(r["ply"]), str(r["rid"])))
    picked: list = []
    for t in sorted(targets, key=lambda r: (-float(r["our_leaf_gap"]), str(r["root_id"]),
                                            int(r["ply"]), str(r["rid"]))):
        want = _match_key(t)
        cands = [i for i, r in enumerate(remaining)
                 if _match_key(r) == want and r["root_id"] not in used]
        if not cands:
            continue
        j = min(cands, key=lambda i: (abs(float(remaining[i]["our_leaf_gap"])
                                          - float(t["our_leaf_gap"])),
                                      str(remaining[i]["root_id"]),
                                      int(remaining[i]["ply"]), str(remaining[i]["rid"])))
        c = dict(remaining.pop(j))
        c["matched_to"] = t["rid"]
        c["match_gap_diff"] = abs(float(c["our_leaf_gap"]) - float(t["our_leaf_gap"]))
        used.add(c["root_id"])
        picked.append(c)
    return picked


def _mean(xs):
    xs = [float(x) for x in xs]
    return (sum(xs) / len(xs)) if xs else None


def _profile(rows: list) -> dict:
    return {
        "n": len(rows),
        "by_ply_class": dict(Counter(r["ply_class"] for r in rows)),
        "by_phase_bucket": dict(Counter(r.get("phase_bucket") for r in rows)),
        "by_ply_class_x_phase": dict(Counter(
            f"{r['ply_class']}/{r.get('phase_bucket')}" for r in rows)),
        "by_jcz_seat": dict(Counter(str(r["jcz_seat"]) for r in rows)),
        "mean_our_leaf_gap": _mean(r["our_leaf_gap"] for r in rows),
        "mean_k_remaining": _mean(r["k_remaining"] for r in rows),
        "n_distinct_games": len({r["root_id"] for r in rows}),
    }


def assign(candidates: Path, out_path: Path, positions_path: Path, *,
           k_late: int, n_target: int, min_n: int) -> dict:
    """PREREG §4. Pure stdlib, no engine, NO outcome — and no wall-clock stamp, so
    the artifact is a deterministic function of its inputs (pinned by the tests)."""
    rows = load_candidates(candidates)
    for r in rows:
        r["stratum"] = None
        # `phase_bucket` is a function of `k_late`, which is an `assign` parameter,
        # so it is stamped HERE (not at extract time) and travels on every emitted
        # row — the matcher reads it, and the readout can see what C was matched on.
        r["phase_bucket"] = phase_bucket(r, k_late)

    eligible = {STRAT_A: [], STRAT_B: [], "POOL": []}
    for r in rows:
        eligible[stratum_for(r, k_late) or "POOL"].append(r)
    for k in eligible:
        eligible[k].sort(key=order_key)

    claimed: set = set()
    a_rows = _pick_balanced(eligible[STRAT_A], claimed, n_target)
    b_rows = _pick_balanced(eligible[STRAT_B], claimed, n_target)
    pool = [r for r in eligible["POOL"] if r["root_id"] not in claimed]
    c_rows = match_control(a_rows + b_rows, pool, claimed)
    for r in c_rows:
        claimed.add(r["root_id"])

    for r in a_rows:
        r["stratum"] = STRAT_A
    for r in b_rows:
        r["stratum"] = STRAT_B
    for r in c_rows:
        r["stratum"] = STRAT_C

    gate_ok = len(a_rows) >= min_n and len(b_rows) >= min_n and len(c_rows) >= min_n
    n_targets = len(a_rows) + len(b_rows)
    strata = {
        "schema": SCHEMA_STRATA,
        "prereg": PREREG,
        "candidates": str(candidates),
        "k_late": int(k_late),
        "n_target": int(n_target),
        "min_n_gate": int(min_n),
        "gate_ok": bool(gate_ok),
        "gate_verdict": ("PROCEED" if gate_ok else
                         f"INCONCLUSIVE-BY-CONSTRUCTION (a stratum is under the "
                         f"pre-registered n>={min_n} floor)"),
        "n_candidates": len(rows),
        "eligible": {k: {"n": len(v), "n_distinct_games": len({r["root_id"] for r in v})}
                     for k, v in eligible.items()},
        "strata": {STRAT_A: _profile(a_rows), STRAT_B: _profile(b_rows),
                   STRAT_C: _profile(c_rows)},
        "control_match": {
            "match_key": list(MATCH_KEY),
            "match_nearest_on": "our_leaf_gap",
            "n_targets": n_targets,
            "n_matched": len(c_rows),
            "truncated": bool(len(c_rows) < n_targets),
            "truncated_by": int(n_targets - len(c_rows)),
            "mean_gap_diff": _mean(r["match_gap_diff"] for r in c_rows),
            "max_gap_diff": max((r["match_gap_diff"] for r in c_rows), default=None),
            "mean_gap_targets": _mean(r["our_leaf_gap"] for r in (a_rows + b_rows)),
            "mean_gap_control": _mean(r["our_leaf_gap"] for r in c_rows),
        },
        "rows": {STRAT_A: a_rows, STRAT_B: b_rows, STRAT_C: c_rows},
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(strata, indent=2, sort_keys=False))

    scored = sorted(a_rows + b_rows + c_rows, key=lambda r: (str(r["root_id"]), str(r["rid"])))
    positions_path = Path(positions_path)
    positions_path.parent.mkdir(parents=True, exist_ok=True)
    with positions_path.open("w") as fh:
        for r in scored:
            fh.write(json.dumps(r) + "\n")
    # A/B only — the Tier-1 sign check is pre-registered to run on A and B, never C.
    ab_path = positions_path.with_name(positions_path.stem + "_AB" + positions_path.suffix)
    with ab_path.open("w") as fh:
        for r in scored:
            if r["stratum"] in (STRAT_A, STRAT_B):
                fh.write(json.dumps(r) + "\n")
    strata["positions_files"] = {"all": str(positions_path), "AB": str(ab_path)}
    out_path.write_text(json.dumps(strata, indent=2, sort_keys=False))

    print(f"[assign] A n={len(a_rows)} | B n={len(b_rows)} | C n={len(c_rows)} "
          f"(pool {len(pool)}, k_late {k_late})")
    print(f"[assign] control match key {list(MATCH_KEY)} (nearest on our_leaf_gap)")
    for name in (STRAT_A, STRAT_B, STRAT_C):
        p = strata["strata"][name]
        print(f"[assign] {name:<8} n={p['n']:>3}  "
              f"{sorted(p['by_ply_class_x_phase'].items())}  "
              f"games={p['n_distinct_games']:>3}  seats={sorted(p['by_jcz_seat'].items())}")
    print(f"[assign] mean our_leaf_gap: targets "
          f"{strata['control_match']['mean_gap_targets']} vs control "
          f"{strata['control_match']['mean_gap_control']} "
          f"(mean matched diff {strata['control_match']['mean_gap_diff']})")
    print(f"[assign] gate(n>={min_n}): {strata['gate_verdict']}")
    print(f"[assign] strata -> {out_path}\n[assign] positions -> {positions_path}"
          f"\n[assign] positions (A+B) -> {ab_path}")
    return strata


# --------------------------------------------------------------------------- #
# cli                                                                           #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    e = sub.add_parser("extract", help="engine pass over the JCZ match corpus")
    e.add_argument("--corpus", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--limit-games", type=int, default=None)
    e.add_argument("--with-search-pick", action="store_true",
                   help="also record the champion's full-search action (context only, "
                        "best-effort, never aborts the run)")

    c = sub.add_parser("counts", help="pure-stdlib dry run: how many, in which stratum")
    c.add_argument("--candidates", required=True)
    c.add_argument("--k-late", type=int, default=14)
    c.add_argument("--json", action="store_true")

    a = sub.add_parser("assign", help="strata + sampling + CONTROL match + the n gate")
    a.add_argument("--candidates", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--positions", required=True)
    a.add_argument("--k-late", type=int, default=14)
    a.add_argument("--n-target", type=int, default=40)
    a.add_argument("--min-n", type=int, default=25)

    s = sub.add_parser("search-pick",
                       help="backfill the context-only search column over SAMPLED rows")
    s.add_argument("--strata", required=True)
    s.add_argument("--positions", required=True)
    s.add_argument("--positions-ab", default=None,
                   help="defaults to <positions stem>_AB<suffix> when that file exists")
    s.add_argument("--workers", type=int, default=1)

    args = ap.parse_args(argv)
    if args.mode == "extract":
        extract(Path(args.corpus), Path(args.out), args.limit_games, args.with_search_pick)
        return 0
    if args.mode == "counts":
        counts(Path(args.candidates), args.k_late, args.json)
        return 0
    if args.mode == "search-pick":
        search_pick_backfill(
            Path(args.strata), Path(args.positions),
            Path(args.positions_ab) if args.positions_ab else None, args.workers)
        return 0
    st = assign(Path(args.candidates), Path(args.out), Path(args.positions),
                k_late=args.k_late, n_target=args.n_target, min_n=args.min_n)
    return 0 if st["gate_ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
