#!/usr/bin/env python3
"""Phase-5 analyzer, slice 2a: the offline per-move EV-loss grader.

    scripts/analyzer/ev_loss.py measurement/e4_games/XXXX.json \
        -o measurement/analyzer_evloss_20260805 --label g1 --calibration-seed 777

Replays one archived game and, at EVERY ply of BOTH seats, re-runs the champion's
own search on that position and prices the action actually played against the
search's best action. Pre-registered spec (binding):
`measurement/analyzer_evloss_20260805/EVLOSS_SPEC.md` — D1 units, D2 measured
buckets, D3 exact-tail carve-out, D4 confounds.

The JSON is the source of truth; every number in EVLOSS_READOUT.md must cite a
field of it. Definitions are copied verbatim into the artifact's `definitions`
block so a reader of the artifact alone can interpret it.

Three things this file is careful about, all of which are silent-wrong-answer
classes if got wrong:

* **The rules profile is resolved FROM THE ARCHIVE**, not from a flag. A
  pre-2026-08-01 archive (null `start_rule`/`grid_rule`) is a `walled` game and
  must be graded under `walled`; a `retail`+`centered18` archive is `fixed_v1`.
  Anything else fails closed. `root_replay.replay_actions` has no rules-profile
  seam, so the board walk is built here with `Game(**profile.game_kwargs())`.
* **Alias dedup.** `fair_agent.root_stats_list` dedups root children by node
  identity (rotations of a symmetric tile share one child, lowest action kept),
  so the pool is keyed by the *representative* of an alias group and the action
  actually played is frequently absent from it. Q for the played action is read
  off its group representative, computed here by grouping legal actions on the
  successor `string_representation`.
* **The best action is `fair_agent.pooled_q_argmax`**, the production decision
  rule, not a naive max — otherwise the grader disagrees with the agent's own
  pick and every ΔQ is measured against a move the champion would not play.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "human_anchor"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "level2"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "measurement_infra"))

# MUST precede any `carcassonne_ai` import: `virtual_score_v2.DEFAULT_CONFIG` is
# frozen from the environment at ITS first import, so a module that pulls the
# leaf in before this (a sibling test, an interactive session) bakes in the wrong
# caps and `verify=True` then raises. Same first-import discipline as every
# `scripts/human_anchor/` entry point. It does NOT set CARCASSONNE_FIX_R9 — that
# is the profile's business and is handled by `prepare_env` below.
import env_preamble  # noqa: E402,F401

SCHEMA = "carcassonne-analyzer-ev-loss/v1"

# The leaf of record. Checked against the running agent's manifest AND against
# the archive's own stamp; a mismatch is an integrity failure, not a warning.
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

# D1: the leaf handed to MCTS is tanh(virtual_score / VALUE_NORM). Read off
# champion_factory's manifest at runtime too (`integrity.value_norm_manifest`);
# this constant is the pinned expectation.
VALUE_NORM = 15.0
TANH_CLIP = 0.999

# D2 bucket names, in increasing severity. Thresholds are MEASURED (the
# calibration null), never chosen — see DEFINITIONS["buckets"].
BUCKETS = ("agree", "within_noise", "inaccuracy", "blunder")

# Null quantiles used as the two bucket cut points.
NULL_Q_INACCURACY = 0.95
NULL_Q_BLUNDER = 0.99

DEFINITIONS = {
    "what_is_graded": "Every ply of BOTH seats of one archived game. The champion's "
                      "own search is re-run on the position the archive records, and "
                      "the action actually played is priced against the search's best "
                      "action. Forced plies (one legal action) are counted and excluded "
                      "from every readout.",
    "D1_units": "Q IS NOT IN POINTS. The leaf handed to MCTS is "
                "tanh(flat_virtual_score_v2_float(...) / value_norm) with value_norm = "
                "15.0 (heuristic_prior_mcts.py), and MCTS backs up the SQUASHED value, "
                "so pooled W is a sum of tanh-squashed values and Q = W/N is "
                "dimensionless in (-1, 1). The PRIMARY statistic is therefore raw "
                "delta_q = Q(best) - Q(played). `delta_points_tanh_est` = "
                "15 * (atanh(clip(Q_best)) - atanh(clip(Q_played))), clip |Q| <= 0.999, "
                "is a MONOTONE RE-SCALING FOR READABILITY, NOT A CALIBRATED EV: the "
                "inverse tanh blows up near |Q| -> 1 and the leaf's points scale is "
                "virtual score, not final margin. Never quote it as 'you lost N points' "
                "without this caveat. (This retracts BACKLOG.md:591 / ANALYZER_REPORT.md, "
                "which both assert Q is natively in expected-margin points.)",
    "D2_buckets": "Thresholds are MEASURED, not invented. A calibration pass re-grades "
                  "every ply with a DIFFERENT agent seed; for each ply the two passes' "
                  "delta_q for the SAME played action differ only by the instrument's own "
                  "noise, so the distribution of |delta_q_A - delta_q_B| is the null. "
                  "Buckets: `agree` (the search's best action IS the played action, "
                  "delta_q == 0) / `within_noise` (delta_q <= p95 of the null) / "
                  "`inaccuracy` (p95 < delta_q <= p99) / `blunder` (delta_q > p99). The "
                  "null quantiles ship in `buckets.thresholds` and are pinned by a test. "
                  "BUCKET LABELS ARE NOT PORTABLE across calibrations or across grading "
                  "epochs: re-measured null => re-stamped buckets.",
    "D3_exact_tail": "When k_remaining <= exact_max_k (=2) the agent latches to the "
                     "marginalized endgame solver and the MCTS pool is empty "
                     "(last_move()['exact'] is true). Those plies are graded separately "
                     "with endgame_solver.solve(mode='marginalized') -> regret_of(), which "
                     "is a TRUE EV loss in FINAL-SCORE POINTS. They live in `exact_tail` "
                     "with their own counters and are NEVER pooled into a delta_q or "
                     "delta_points_tanh_est mean — the two are different instruments on "
                     "different scales.",
    "best_action": "fair_agent.pooled_q_argmax(agg_n, agg_w, min_visits=2): argmax over "
                   "(Q=W/N, N, -action) restricted to pooled N >= min_visits (falling back "
                   "to all visited actions if none qualify). THE production decision rule; "
                   "a naive max over Q would disagree with the agent's own pick.",
    "alias_dedup": "fair_agent.root_stats_list dedups root children by node identity "
                   "(rotations of a symmetric tile share one child node; the LOWEST action "
                   "is kept), so the pool is keyed by an alias group's representative and "
                   "the played action is often absent from it verbatim. Legal actions are "
                   "grouped here by the successor board's string_representation and the "
                   "played action's Q is read off min(group). `alias_group_size` records "
                   "how many legal actions collapsed onto the played action's entry.",
    "eligibility_censoring": "An action the search gave fewer than min_visits=2 pooled "
                             "visits is NOT eligible for the production argmax, so its Q is "
                             "an unreliable read and it cannot be guaranteed delta_q >= 0. "
                             "Such plies are marked `played_eligible: false`, carry "
                             "`delta_q = null` and `delta_q_raw` (which MAY be negative), "
                             "and are excluded from the primary readout and counted in "
                             "`n_unrated`. THIS CENSORS DOWNWARD: a move so bad the priors "
                             "starve it is exactly the move that goes unrated, so the "
                             "reported mean EV loss is a LOWER read for both seats. The "
                             "unrated rate is reported per seat so the size of the hole is "
                             "visible.",
    "rules_profile_epoch": "The rules profile is resolved FROM THE ARCHIVE, never from a "
                           "flag: (start_rule, grid_rule) = (null/'engine', null/'engine6') "
                           "=> `walled` (the engine of record: engine6 grid, engine random "
                           "start tile), ('retail','centered18') => `fixed_v1`, "
                           "('engine','centered18') => `centered18`, ('retail','engine6') => "
                           "`retail`. Any other combination FAILS CLOSED. Grading an "
                           "archive under the wrong profile is a silent wrong answer; "
                           "`integrity.replay_scores_match` is the independent check that "
                           "the profile chosen reproduces the archive's recorded scores. "
                           "CARCASSONNE_FIX_R9 is set iff the resolved profile expects it "
                           "(it is import-latched and has no per-Game seam).",
    "budget": "By DEFAULT the grading budget is the archive's OWN stamped budget "
              "(k_dets_effective x sims_effective), so the grader is the opponent's own "
              "opinion and the champion seat's residual loss is pure instrument noise. "
              "Grading at a different budget is legal (--sims/--k-dets) but must then be "
              "read as 'a stronger (or weaker) reader's opinion', not the opponent's.",
    "acceptance_gate": "Spec 'What would make this wrong': if the CHAMPION seat's own mean "
                       "delta_q is not near the calibration null, the instrument scores the "
                       "agent that generated the moves as materially lossy and is mis-wired "
                       "(wrong profile, wrong seeding, mirror drift). The criterion shipped "
                       "here is champion_mean_delta_q <= null p95. `acceptance_gate.pass` "
                       "false means NO human number from this artifact is reportable.",
    "pooled_top2_q_gap": "Q(best) - Q(second best) among the ELIGIBLE pooled actions at "
                         "this ply: how decided the search was, independent of what was "
                         "played. null when fewer than 2 eligible actions.",
    "phase": "The engine's GamePhase at the ply: 'tiles' (place a tile) or 'meeples' "
             "(place / decline a meeple on the tile just placed).",
    "k_remaining": "len(state.deck) at the ply = tiles still to be drawn. The latch to the "
                   "exact solver fires at k_remaining <= 2.",
}

CONFOUNDS = [
    "SAME-FAMILY SELF-PREFERENCE. The grading agent IS the agent that played the game — "
    "same leaf, same search family, same budget. It structurally prefers its own moves. "
    "This is why the champion seat is graded as a built-in paired control and why the "
    "human's absolute EV loss is NEVER reportable on its own, only paired against the "
    "champion seat on the same board.",
    "GRADING EPOCH. The rules profile is resolved from the archive and stamped in "
    "`integrity.rules_profile`. Bucket thresholds are calibrated on THIS corpus at THIS "
    "budget and are not portable to another epoch (a fixed_v1 / k8x1376 archive needs its "
    "own calibration before its buckets mean anything).",
    "n = 2 HUMAN GAMES. Everything this artifact says about a human's play is a "
    "description of one game (or two, pooled) — not an estimate of a player's strength.",
    "BUDGET. The grading budget is stamped per artifact (`budget`). Graded at the "
    "archive's own budget it is the opponent's own opinion; graded higher it is a stronger "
    "reader's opinion and the champion seat will show real, non-noise loss.",
    "ELIGIBILITY CENSORING IS DOWNWARD. Moves the search starved of visits (pooled N < 2) "
    "are unrated and dropped, and a bad move is exactly the move the priors starve. Both "
    "seats' mean EV loss is therefore a LOWER read; see `summary.*.n_unrated`.",
    "EXACT-TAIL POINTS ARE A DIFFERENT SCALE. `exact_tail.*.regret_points` are true "
    "final-score points from the marginalized solver; `delta_points_tanh_est` is a "
    "readability rescaling of a dimensionless Q. Do not add, average, or compare them.",
]


# --------------------------------------------------------------------------- #
# bits <-> float. Inverse of `scripts/rustport/fair_common.ubits` (which is
# imported nowhere here: that module pulls in prod_leaf_env, which refuses to
# load after carcassonne_ai). `tests/test_analyzer_evloss.py` pins the round trip.
# --------------------------------------------------------------------------- #
def fbits(bits: int) -> float:
    """Raw IEEE-754 f64 bits (Rust `f64::to_bits`) -> float."""
    import struct
    return struct.unpack("<d", struct.pack("<Q", int(bits)))[0]


def ubits(x: float) -> int:
    """float -> raw IEEE-754 f64 bits. Verbatim `fair_common.ubits`."""
    import struct
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


# --------------------------------------------------------------------------- #
# D4.2 — the archive's epoch decides the rules profile. Fail closed.            #
# --------------------------------------------------------------------------- #
# (start_rule, grid_rule) -> profile name. `None` in an archive means the field
# predates the 2026-08-01 build, i.e. the engine defaults.
_ARCHIVE_START_DEFAULT = "engine"
_ARCHIVE_GRID_DEFAULT = "engine6"


def resolve_profile_name(start_rule, grid_rule) -> str:
    """The rules profile an archive was PLAYED under. Raises on anything unknown."""
    from carcassonne_ai import rules_profile

    s = _ARCHIVE_START_DEFAULT if start_rule in (None, "") else str(start_rule)
    g = _ARCHIVE_GRID_DEFAULT if grid_rule in (None, "") else str(grid_rule)
    hits = [n for n, p in rules_profile.PROFILES.items()
            if (p.start_rule, p.grid_rule) == (s, g)]
    if len(hits) != 1:
        raise ValueError(
            f"cannot resolve a rules profile for archive (start_rule={start_rule!r}, "
            f"grid_rule={grid_rule!r}) -> ({s!r}, {g!r}); candidates {hits}. "
            "FAILING CLOSED: grading under the wrong profile is a silent wrong answer.")
    return hits[0]


def prepare_env(profile_name: str) -> dict:
    """Set the import-latched env this profile owes, BEFORE carcassonne_ai loads.

    R9 (`CARCASSONNE_FIX_R9`) is derived at import time by `base_deck` and latched
    in a Rust OnceLock, so it can only be set here. Raises if `carcassonne_ai` is
    already imported with the wrong latch rather than grading the wrong farms."""
    from carcassonne_ai import rules_profile          # cheap: no engine import

    prof = rules_profile.resolve(profile_name)
    want = "1" if prof.r9_env_expected else "0"
    already = "carcassonne_ai.base_deck" in sys.modules
    if already and rules_profile.r9_env_on() != prof.r9_env_expected:
        raise RuntimeError(
            f"CARCASSONNE_FIX_R9 is latched at {rules_profile.r9_env_on()} but profile "
            f"{prof.name!r} expects {prof.r9_env_expected} — restart the process.")
    os.environ["CARCASSONNE_FIX_R9"] = want
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    return {"CARCASSONNE_FIX_R9": want,
            "r9_env_expected": prof.r9_env_expected,
            "r9_env_observed": rules_profile.r9_env_on()}


# --------------------------------------------------------------------------- #
# the archive                                                                   #
# --------------------------------------------------------------------------- #
def load_archive(path) -> dict:
    """An Android archive -> the fields the grader needs. Mirrors `e4_diff.load_e4`."""
    a = json.loads(Path(path).read_text())
    if a.get("schema") not in (None, "carcassonne-android-archive/v1"):
        print(f"[ev_loss] WARNING: unexpected schema {a.get('schema')!r}")
    return {
        "path": str(path),
        "deck_seed": int(a["deck_seed"]),
        "actions": [int(x) for x in a["actions"]],
        "human_player": int(a.get("human_player", 0)),
        "recorded_scores": [int(x) for x in a.get("scores", [])] or None,
        "sims_effective": a.get("sims_effective"),
        "k_dets_effective": a.get("k_dets_effective"),
        "provenance": {k: a.get(k) for k in
                       ("champion_id", "leaf_hash", "sims_effective", "k_dets_effective",
                        "opponent", "opponent_name", "finished_at", "start_rule",
                        "grid_rule", "budget_note", "verify", "coached")},
    }


# --------------------------------------------------------------------------- #
# the grading pass                                                              #
# --------------------------------------------------------------------------- #
def _alias_groups(game, board, legal):
    """legal action -> representative action of its alias group.

    Two legal actions alias iff they lead to the SAME successor state, which is
    exactly when MCTS gives them one child node; `root_stats_list` keeps the
    lowest action of the group, so the representative is min(group)."""
    groups: dict[str, list[int]] = {}
    for a in legal:
        nb, _ = game.get_next_state(board, int(a))
        groups.setdefault(game.string_representation(nb), []).append(int(a))
    rep = {}
    for members in groups.values():
        r = min(members)
        for a in members:
            rep[a] = r
    sizes = {a: len(members) for members in groups.values() for a in members}
    return rep, sizes


def _tanh_points(q_best: float, q_played: float) -> float:
    """D1: the readability-only points rescaling. NOT a calibrated EV."""
    c = lambda q: max(-TANH_CLIP, min(TANH_CLIP, float(q)))  # noqa: E731
    return VALUE_NORM * (math.atanh(c(q_best)) - math.atanh(c(q_played)))


def grade_pass(arch, profile_name, *, seed, sims, k_dets, rust_threads,
               exact_tail=True, limit=0, progress=True):
    """One full grading pass over one archive. Returns (plies, meta).

    `plies` is one record per ply (including forced and exact ones, flagged);
    `meta` carries the agent manifest, the execution, and the final board scores."""
    import random

    import numpy as np
    from carcassonne_ai import fair_agent, rules_profile
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, reseat, resolve_execution

    prof = rules_profile.activate(profile_name)
    ex = resolve_execution("inherit", profile="desktop", rust_threads=rust_threads)

    actions = arch["actions"][: limit or None]
    deck_seed = arch["deck_seed"]

    random.seed(int(deck_seed))                 # root_replay contract: fixes the shuffle
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    agent = make_production_champion("fair", game=game, seed=int(seed), sims=sims,
                                     k_dets=k_dets, verify=True, **ex.factory_kwargs())
    # Seat the mirror on the deck this board was dealt (ply 0, move_idx 0).
    reseat(agent, deck_seed=deck_seed, actions=(), move_idx=0)

    min_visits = float(fair_agent.DEFAULT_MIN_POOLED_VISITS)
    exact_max_k = int(fair_agent.EXACT_MAX_K)

    out = []
    t0 = time.time()
    for ply, played in enumerate(actions):
        st = board.state
        legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        rec = {
            "ply": ply,
            "actor": int(st.current_player),
            "phase": st.phase.value,
            "k_remaining": len(st.deck),
            "n_legal": len(legal),
            "action_played": int(played),
        }
        if played not in legal:
            raise ValueError(f"archive action {played} illegal at ply {ply}")

        # `_move_idx` owns the per-determinization seeds; the caller owns the
        # move timeline, so it is seated explicitly at every ply (mirror_protocol).
        agent._move_idx = ply
        chosen = int(agent.choose_action(board))
        lm = agent.last_move()
        rec["agent_action"] = chosen
        rec["forced"] = bool(lm["forced"])
        rec["exact"] = bool(lm["exact"])
        rec["latched"] = bool(lm["latched"])
        rec["timeout"] = bool(lm["timeout"])
        rec["secs"] = float(lm["secs"])

        # FORCED WINS OVER EXACT. The latched solver still "decides" a ply with one
        # legal action and the agent reports it as exact, but a move with no
        # alternative carries no EV loss by anyone — it belongs in the forced count,
        # not in the exact-tail regret block (spec D3: forced plies are excluded from
        # EVERY readout).
        if rec["forced"] or len(legal) == 1:
            rec["kind"] = "forced"
            rec["forced"] = True
        elif rec["exact"]:
            rec["kind"] = "exact"
            rec["solver_nodes"] = int(lm["solver_nodes"])
            if exact_tail:
                from endgame_solver import regret_of, solve
                res = solve(game, board, mode="marginalized")
                rec["regret_points"] = float(regret_of(res, int(played)))
                rec["solver_optimal_actions"] = [int(a) for a in res.optimal_actions]
                rec["solver_value"] = float(res.value)
                rec["solver_child_value_played"] = float(
                    res.child_values.get(int(played), float("nan")))
                rec["solver_nodes_regrade"] = int(res.nodes)
                rec["played_is_optimal"] = int(played) in res.optimal_actions
        else:
            rec["kind"] = "pimc"
            pool = {int(a): (fbits(n), fbits(w)) for a, n, w in lm["pooled"]}
            rep, sizes = _alias_groups(game, board, legal)
            agg_n = {a: n for a, (n, _) in pool.items()}
            agg_w = {a: w for a, (_, w) in pool.items()}
            best = fair_agent.pooled_q_argmax(agg_n, agg_w, min_visits=min_visits)
            q = {a: agg_w[a] / agg_n[a] for a in agg_n}
            eligible = sorted((a for a in agg_n if agg_n[a] >= min_visits),
                              key=lambda a: -q[a])
            rec["n_pooled"] = len(pool)
            rec["n_alias_groups"] = len(set(rep.values()))
            rec["alias_group_size"] = int(sizes.get(int(played), 1))
            rec["pool_total_visits"] = sum(agg_n.values())
            rec["action_best"] = int(best)
            rec["q_best"] = float(q[best])
            rec["n_visits_best"] = float(agg_n[best])
            rec["pooled_top2_q_gap"] = (float(q[eligible[0]] - q[eligible[1]])
                                        if len(eligible) >= 2 else None)
            # THE alias step: the played action's Q lives on its group's rep.
            prep = rep.get(int(played), int(played))
            rec["action_played_rep"] = prep
            if prep in agg_n:
                rec["q_played"] = float(q[prep])
                rec["n_visits_played"] = float(agg_n[prep])
                rec["played_eligible"] = bool(agg_n[prep] >= min_visits)
                rec["delta_q_raw"] = float(q[best] - q[prep])
                rec["delta_q"] = (rec["delta_q_raw"] if rec["played_eligible"] else None)
                rec["delta_points_tanh_est"] = (
                    _tanh_points(q[best], q[prep]) if rec["played_eligible"] else None)
                rec["agrees"] = bool(prep == int(best))
            else:                      # the search never visited it at all
                rec["q_played"] = None
                rec["n_visits_played"] = 0.0
                rec["played_eligible"] = False
                rec["delta_q_raw"] = None
                rec["delta_q"] = None
                rec["delta_points_tanh_est"] = None
                rec["agrees"] = False
            # The agent's own pick must be the pooled-Q argmax, always.
            if chosen != best:
                raise AssertionError(
                    f"ply {ply}: agent chose {chosen} but pooled_q_argmax says {best} — "
                    "the grader's best-action rule disagrees with the agent's own pick")

        out.append(rec)
        board, _ = game.get_next_state(board, int(played))
        advance(agent, int(played))
        if progress and (ply + 1) % 24 == 0:
            print(f"  [seed {seed}] ply {ply+1}/{len(actions)}  "
                  f"{time.time()-t0:.0f}s", flush=True)

    meta = {
        "final_scores": list(board.state.scores),
        "agent_manifest": agent.manifest,
        "execution": dict(ex),
        "rules_profile": prof.as_manifest(),
        "min_pooled_visits": min_visits,
        "exact_max_k": exact_max_k,
        "seed": int(seed),
        "wall_secs": round(time.time() - t0, 2),
    }
    return out, meta


# --------------------------------------------------------------------------- #
# D2 — the measured null and the buckets                                        #
# --------------------------------------------------------------------------- #
def _quantile(xs_sorted, f):
    if not xs_sorted:
        return None
    if len(xs_sorted) == 1:
        return xs_sorted[0]
    i = f * (len(xs_sorted) - 1)
    lo, hi = int(i), min(int(i) + 1, len(xs_sorted) - 1)
    return xs_sorted[lo] + (xs_sorted[hi] - xs_sorted[lo]) * (i - lo)


def _dist(xs):
    xs = sorted(float(x) for x in xs if x is not None)
    if not xs:
        return None
    return {"n": len(xs), "mean": statistics.fmean(xs),
            "sd": statistics.stdev(xs) if len(xs) > 1 else 0.0,
            "min": xs[0], "p50": _quantile(xs, .50), "p90": _quantile(xs, .90),
            "p95": _quantile(xs, .95), "p99": _quantile(xs, .99), "max": xs[-1]}


def build_null(plies_a, plies_b):
    """D2: |delta_q_A - delta_q_B| over every ply BOTH passes rated. The null."""
    b = {r["ply"]: r for r in plies_b}
    diffs, diffs_disagree = [], []
    for ra in plies_a:
        rb = b.get(ra["ply"])
        if rb is None or ra["kind"] != "pimc" or rb["kind"] != "pimc":
            continue
        if ra.get("delta_q") is None or rb.get("delta_q") is None:
            continue
        d = abs(float(ra["delta_q"]) - float(rb["delta_q"]))
        diffs.append(d)
        if not (ra["agrees"] and rb["agrees"]):
            diffs_disagree.append(d)
    sd = sorted(diffs)
    return {
        "definition": "|delta_q(pass A) - delta_q(pass B)| for the SAME played action, "
                      "over every ply both passes rated (pimc, played_eligible).",
        "n": len(diffs),
        "dist": _dist(diffs),
        "dist_disagree_only": _dist(diffs_disagree),
        "n_disagree_only": len(diffs_disagree),
        "best_action_agreement_between_passes": (
            statistics.fmean([1.0 if (b[r["ply"]]["agrees"] == r["agrees"]
                                      and b[r["ply"]].get("action_best")
                                      == r.get("action_best")) else 0.0
                              for r in plies_a
                              if r["kind"] == "pimc"
                              and b.get(r["ply"], {}).get("kind") == "pimc"])
            if any(r["kind"] == "pimc" for r in plies_a) else None),
        "samples_sorted": sd,
    }


def bucket_of(rec, thr_inaccuracy, thr_blunder):
    """D2 bucket for one rated pimc ply. `None` for unrated / forced / exact."""
    if rec["kind"] != "pimc" or rec.get("delta_q") is None:
        return None
    if rec["agrees"]:
        return "agree"
    d = float(rec["delta_q"])
    if thr_inaccuracy is None:
        return None
    if d <= thr_inaccuracy:
        return "within_noise"
    if thr_blunder is not None and d <= thr_blunder:
        return "inaccuracy"
    return "blunder"


# --------------------------------------------------------------------------- #
# assembly                                                                      #
# --------------------------------------------------------------------------- #
def build_report(arch, profile_name, plies_a, meta_a, plies_b, meta_b, *,
                 label, budget, env_stamp, top_n=3):
    null = build_null(plies_a, plies_b) if plies_b else {
        "definition": "no calibration pass was run", "n": 0, "dist": None,
        "dist_disagree_only": None, "n_disagree_only": 0,
        "best_action_agreement_between_passes": None, "samples_sorted": []}
    nd = null["dist"] or {}
    thr_in = nd.get("p95")
    thr_bl = nd.get("p99")

    for r in plies_a:
        r["bucket"] = bucket_of(r, thr_in, thr_bl)

    hp = arch["human_player"]
    seats = {"human": hp, "champion": 1 - hp}

    summary, exact_tail, top = {}, {}, {}
    for name, seat in seats.items():
        mine = [r for r in plies_a if r["actor"] == seat]
        pimc = [r for r in mine if r["kind"] == "pimc"]
        rated = [r for r in pimc if r.get("delta_q") is not None]
        summary[name] = {
            "seat": seat,
            "n_plies": len(mine),
            "n_forced": sum(1 for r in mine if r["kind"] == "forced"),
            "n_exact": sum(1 for r in mine if r["kind"] == "exact"),
            "n_pimc": len(pimc),
            "n_rated": len(rated),
            "n_unrated": len(pimc) - len(rated),
            "unrated_frac": (len(pimc) - len(rated)) / len(pimc) if pimc else None,
            "agree_rate": (statistics.fmean([1.0 if r["agrees"] else 0.0 for r in rated])
                           if rated else None),
            "mean_delta_q": statistics.fmean([r["delta_q"] for r in rated]) if rated else None,
            "sd_delta_q": (statistics.stdev([r["delta_q"] for r in rated])
                           if len(rated) > 1 else None),
            "sem_delta_q": (statistics.stdev([r["delta_q"] for r in rated]) / len(rated) ** .5
                            if len(rated) > 1 else None),
            "delta_q_dist": _dist([r["delta_q"] for r in rated]),
            "mean_delta_points_tanh_est": (
                statistics.fmean([r["delta_points_tanh_est"] for r in rated])
                if rated else None),
            "delta_points_tanh_est_dist": _dist([r["delta_points_tanh_est"] for r in rated]),
            "buckets": {b: sum(1 for r in rated if r["bucket"] == b) for b in BUCKETS},
            "bucket_frac": {b: (sum(1 for r in rated if r["bucket"] == b) / len(rated)
                                if rated else None) for b in BUCKETS},
            "mean_pooled_top2_q_gap": (
                statistics.fmean([r["pooled_top2_q_gap"] for r in pimc
                                  if r.get("pooled_top2_q_gap") is not None])
                if any(r.get("pooled_top2_q_gap") is not None for r in pimc) else None),
        }
        ex = [r for r in mine if r["kind"] == "exact" and "regret_points" in r]
        exact_tail[name] = {
            "n": len(ex),
            "n_optimal": sum(1 for r in ex if r.get("played_is_optimal")),
            "mean_regret_points": (statistics.fmean([r["regret_points"] for r in ex])
                                   if ex else None),
            "max_regret_points": max([r["regret_points"] for r in ex], default=None),
            "total_regret_points": sum(r["regret_points"] for r in ex) if ex else None,
            "regret_dist": _dist([r["regret_points"] for r in ex]),
            "plies": [{k: r[k] for k in ("ply", "k_remaining", "n_legal", "action_played",
                                         "regret_points", "played_is_optimal",
                                         "solver_optimal_actions", "solver_nodes_regrade")}
                      for r in ex],
        }
        top[name] = sorted(rated, key=lambda r: -r["delta_q"])[:top_n]

    # --- the acceptance gate (spec "What would make this wrong") ------------- #
    champ_mean = summary["champion"]["mean_delta_q"]
    gate = {
        "criterion": "champion seat mean delta_q <= p95 of the calibration null "
                     "(|delta_q_A - delta_q_B| for the same played action)",
        "champion_mean_delta_q": champ_mean,
        "champion_sem_delta_q": summary["champion"]["sem_delta_q"],
        "null_p95": thr_in,
        "null_p99": thr_bl,
        "null_mean": nd.get("mean"),
        "null_n": null["n"],
        "human_mean_delta_q": summary["human"]["mean_delta_q"],
        "pass": (champ_mean is not None and thr_in is not None
                 and champ_mean <= thr_in),
        "note": "pass=false => the grader is mis-wired (wrong rules profile, wrong "
                "seeding, mirror drift) and NO human number from this artifact is "
                "reportable. Runs BEFORE any headline.",
    }

    lm = meta_a["agent_manifest"]["leaf_hashes"]["harness_leaf_hash"]
    integrity = {
        "replay_scores_match": (arch["recorded_scores"] is not None
                                and list(meta_a["final_scores"]) == arch["recorded_scores"]),
        "final_scores_replayed": meta_a["final_scores"],
        "recorded_scores": arch["recorded_scores"],
        "n_plies_total": len(plies_a),
        "n_plies_graded": sum(1 for r in plies_a if r["kind"] == "pimc"
                              and r.get("delta_q") is not None),
        "n_latched_exact": sum(1 for r in plies_a if r["kind"] == "exact"),
        "n_forced_skipped": sum(1 for r in plies_a if r["kind"] == "forced"),
        "n_unrated_pimc": sum(1 for r in plies_a if r["kind"] == "pimc"
                              and r.get("delta_q") is None),
        "mirror_desync_events": 0,      # MirrorDesync propagates; a run that finishes had none
        "leaf_hash_runtime": lm,
        "leaf_hash_of_record": LEAF_HASH_OF_RECORD,
        "leaf_hash_ok": lm == LEAF_HASH_OF_RECORD,
        "leaf_hash_archive": arch["provenance"].get("leaf_hash"),
        "leaf_hash_matches_archive": (arch["provenance"].get("leaf_hash") in
                                      (None, LEAF_HASH_OF_RECORD)),
        "value_norm_manifest": meta_a["agent_manifest"]["search"]["value_norm"],
        "value_norm_pinned": VALUE_NORM,
        "rules_profile": meta_a["rules_profile"],
        "rules_profile_name": profile_name,
        "rules_profile_source": "resolved from the archive's start_rule/grid_rule",
        "env": env_stamp,
        "execution": meta_a["execution"],
        "min_pooled_visits": meta_a["min_pooled_visits"],
        "exact_max_k": meta_a["exact_max_k"],
        "pool_total_visits_always_full_budget": all(
            r.get("pool_total_visits") == budget["total_sims_per_move"]
            for r in plies_a if r["kind"] == "pimc"),
    }

    return {
        "schema": SCHEMA,
        "label": label,
        "archive_path": arch["path"],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "spec": "measurement/analyzer_evloss_20260805/EVLOSS_SPEC.md",
        "human_player": hp,
        "provenance": arch["provenance"],
        "budget": budget,
        "definitions": DEFINITIONS,
        "confounds": CONFOUNDS,
        "integrity": integrity,
        "acceptance_gate": gate,
        "buckets": {
            "names": list(BUCKETS),
            "thresholds": {"inaccuracy_gt": thr_in, "blunder_gt": thr_bl,
                           "from_quantiles": [NULL_Q_INACCURACY, NULL_Q_BLUNDER],
                           "calibration_seed": meta_b["seed"] if meta_b else None},
            "null": null,
        },
        "summary": summary,
        "exact_tail": exact_tail,
        "top_losses": top,
        "plies": plies_a,
        "calibration_plies": [
            {k: r.get(k) for k in ("ply", "actor", "kind", "action_played",
                                   "action_best", "q_best", "q_played", "delta_q",
                                   "agrees")}
            for r in plies_b] if plies_b else [],
        "timing": {"pass_a_secs": meta_a["wall_secs"],
                   "pass_b_secs": meta_b["wall_secs"] if meta_b else None},
    }


def to_markdown(rep) -> str:
    L = []
    A = L.append
    itg, gate, b = rep["integrity"], rep["acceptance_gate"], rep["buckets"]
    A(f"# Per-move EV loss — `{Path(rep['archive_path']).name}` (`{rep['label']}`)")
    A("")
    A(f"**Spec:** `{rep['spec']}` · schema `{rep['schema']}` · generated "
      f"{rep['generated_at']}  ")
    A(f"**Archive:** human = seat {rep['human_player']} · recorded scores "
      f"{itg['recorded_scores']} · replayed {itg['final_scores_replayed']} · "
      f"replay match `{itg['replay_scores_match']}`  ")
    A(f"**Rules profile:** `{itg['rules_profile_name']}` "
      f"({itg['rules_profile_source']}) · grid `{itg['rules_profile']['grid_rule']}` · "
      f"start `{itg['rules_profile']['start_rule']}` · "
      f"R9 expected `{itg['rules_profile']['r9_env_expected']}` / observed "
      f"`{itg['rules_profile']['r9_env_observed']}`  ")
    bg = rep["budget"]
    A(f"**Grading budget:** k{bg['k_dets']}x{bg['sims_per_det']} = "
      f"{bg['total_sims_per_move']}/move ({bg['source']}) · seed {bg['seed']} · "
      f"calibration seed {b['thresholds']['calibration_seed']} · "
      f"{rep['integrity']['execution']['backend']} · leaf `{itg['leaf_hash_runtime']}` "
      f"(ok `{itg['leaf_hash_ok']}`)  ")
    A("")

    A("## Acceptance gate")
    A("")
    A(f"**{'PASS' if gate['pass'] else 'FAIL'}** — {gate['criterion']}.")
    A("")
    A(f"- champion seat mean ΔQ = **{_f(gate['champion_mean_delta_q'])}** "
      f"(sem {_f(gate['champion_sem_delta_q'])})")
    A(f"- calibration null p95 = **{_f(gate['null_p95'])}** "
      f"(p99 {_f(gate['null_p99'])}, mean {_f(gate['null_mean'])}, n {gate['null_n']})")
    A(f"- human seat mean ΔQ = {_f(gate['human_mean_delta_q'])}")
    A("")
    A(gate["note"])
    A("")

    A("## Read this first")
    A("")
    for c in rep["confounds"]:
        A(f"- {c}")
    A("")

    A("## Integrity")
    A("")
    A("| field | value |")
    A("|---|---|")
    for k in ("replay_scores_match", "n_plies_total", "n_plies_graded",
              "n_latched_exact", "n_forced_skipped", "n_unrated_pimc",
              "mirror_desync_events", "leaf_hash_runtime", "leaf_hash_ok",
              "value_norm_manifest", "min_pooled_visits", "exact_max_k",
              "pool_total_visits_always_full_budget"):
        A(f"| `{k}` | {itg[k]} |")
    A("")

    A("## Paired EV loss (same board, same deck, same budget)")
    A("")
    A("ΔQ is dimensionless (D1). `pts (tanh est)` is a readability rescaling, **not** "
      "points you can add to a score.")
    A("")
    A("| seat | plies | forced | exact | rated | unrated | agree rate | mean ΔQ | sd | "
      "p95 ΔQ | max ΔQ | mean pts (tanh est) |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name in ("human", "champion"):
        s = rep["summary"][name]
        d = s["delta_q_dist"] or {}
        A(f"| {name} (seat {s['seat']}) | {s['n_plies']} | {s['n_forced']} | "
          f"{s['n_exact']} | {s['n_rated']} | {s['n_unrated']} | "
          f"{_f(s['agree_rate'])} | **{_f(s['mean_delta_q'])}** | {_f(s['sd_delta_q'])} | "
          f"{_f(d.get('p95'))} | {_f(d.get('max'))} | "
          f"{_f(s['mean_delta_points_tanh_est'])} |")
    A("")

    A("## Bucket census (thresholds MEASURED from the calibration null)")
    A("")
    A(f"`within_noise` ≤ **{_f(b['thresholds']['inaccuracy_gt'])}** (null p95) < "
      f"`inaccuracy` ≤ **{_f(b['thresholds']['blunder_gt'])}** (null p99) < `blunder`. "
      f"Null n = {b['null']['n']}; the two passes picked the same best action on "
      f"{_f(b['null']['best_action_agreement_between_passes'])} of shared pimc plies.")
    A("")
    A("| seat | agree | within_noise | inaccuracy | blunder |")
    A("|---|---:|---:|---:|---:|")
    for name in ("human", "champion"):
        s = rep["summary"][name]["buckets"]
        f = rep["summary"][name]["bucket_frac"]
        A(f"| {name} | {s['agree']} ({_f(f['agree'])}) | "
          f"{s['within_noise']} ({_f(f['within_noise'])}) | "
          f"{s['inaccuracy']} ({_f(f['inaccuracy'])}) | "
          f"{s['blunder']} ({_f(f['blunder'])}) |")
    A("")

    A("## Exact tail (k_remaining ≤ 2 — TRUE final-score points, a different instrument)")
    A("")
    A("| seat | plies | played optimally | mean regret (pts) | max | total |")
    A("|---|---:|---:|---:|---:|---:|")
    for name in ("human", "champion"):
        e = rep["exact_tail"][name]
        A(f"| {name} | {e['n']} | {e['n_optimal']} | {_f(e['mean_regret_points'])} | "
          f"{_f(e['max_regret_points'])} | {_f(e['total_regret_points'])} |")
    A("")

    A("## Worst moves")
    A("")
    A("| seat | ply | k left | phase | n legal | played | best | ΔQ | pts (tanh est) | bucket |")
    A("|---|---:|---:|---|---:|---:|---:|---:|---:|---|")
    for name in ("human", "champion"):
        for r in rep["top_losses"][name]:
            A(f"| {name} | {r['ply']} | {r['k_remaining']} | {r['phase']} | "
              f"{r['n_legal']} | {r['action_played']} | {r['action_best']} | "
              f"{_f(r['delta_q'])} | {_f(r['delta_points_tanh_est'])} | {r['bucket']} |")
    A("")
    return "\n".join(L)


def _f(x, nd=4):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}g}"
    return str(x)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive", help="an E4 phone archive json")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--label", required=True, help="short output label, e.g. g1")
    ap.add_argument("--limit", type=int, default=0, help="first N plies only (debug)")
    ap.add_argument("--seed", type=int, default=12345, help="grading agent seed (pass A)")
    ap.add_argument("--calibration-seed", type=int, default=0,
                    help="D2: second-pass agent seed; 0 = skip calibration (then no "
                         "bucket thresholds and no acceptance gate)")
    ap.add_argument("--sims", type=int, default=0,
                    help="sims per determinization (0 = the archive's own sims_effective)")
    ap.add_argument("--k-dets", type=int, default=0,
                    help="determinizations (0 = the archive's own k_dets_effective)")
    ap.add_argument("--rust-threads", type=int, default=None,
                    help="OS threads the Rust core folds the k worlds across "
                         "(default: the desktop deploy profile). Latency only.")
    ap.add_argument("--no-exact-tail", action="store_true",
                    help="skip the D3 endgame-solver regrade of latched plies")
    args = ap.parse_args()

    arch = load_archive(args.archive)
    profile_name = resolve_profile_name(arch["provenance"].get("start_rule"),
                                        arch["provenance"].get("grid_rule"))
    env_stamp = dict(prepare_env(profile_name),
                     **{"prod_leaf_env": env_preamble.RESOLVED})

    sims = args.sims or int(arch["sims_effective"] or 0) or None
    k_dets = args.k_dets or int(arch["k_dets_effective"] or 0) or None
    if sims is None or k_dets is None:
        raise SystemExit("[ev_loss] archive stamps no budget; pass --sims/--k-dets")
    budget = {
        "sims_per_det": sims, "k_dets": k_dets,
        "total_sims_per_move": sims * k_dets,
        "source": ("archive sims_effective/k_dets_effective"
                   if not (args.sims or args.k_dets) else "CLI override"),
        "archive_sims_effective": arch["sims_effective"],
        "archive_k_dets_effective": arch["k_dets_effective"],
        "seed": args.seed,
    }
    print(f"[ev_loss] {Path(args.archive).name}: profile={profile_name} "
          f"budget=k{k_dets}x{sims} ({sims*k_dets}/move) seed={args.seed} "
          f"cal_seed={args.calibration_seed or None}", flush=True)

    plies_a, meta_a = grade_pass(arch, profile_name, seed=args.seed, sims=sims,
                                 k_dets=k_dets, rust_threads=args.rust_threads,
                                 exact_tail=not args.no_exact_tail, limit=args.limit)
    plies_b, meta_b = ([], None)
    if args.calibration_seed:
        plies_b, meta_b = grade_pass(arch, profile_name, seed=args.calibration_seed,
                                     sims=sims, k_dets=k_dets,
                                     rust_threads=args.rust_threads,
                                     exact_tail=False, limit=args.limit)

    rep = build_report(arch, profile_name, plies_a, meta_a, plies_b, meta_b,
                       label=args.label, budget=budget, env_stamp=env_stamp)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"EV_LOSS_{args.label}"
    (out / f"{stem}.json").write_text(json.dumps(rep, indent=1, default=str))
    (out / f"{stem}.md").write_text(to_markdown(rep))
    print(f"[ev_loss] wrote {out/stem}.json / .md")
    g = rep["acceptance_gate"]
    print(f"[ev_loss] ACCEPTANCE GATE {'PASS' if g['pass'] else 'FAIL'}: "
          f"champion mean dQ={_f(g['champion_mean_delta_q'])} vs null p95="
          f"{_f(g['null_p95'])} (human mean dQ={_f(g['human_mean_delta_q'])})")
    i = rep["integrity"]
    print(f"[ev_loss] integrity: replay_scores_match={i['replay_scores_match']} "
          f"graded={i['n_plies_graded']} exact={i['n_latched_exact']} "
          f"forced={i['n_forced_skipped']} unrated={i['n_unrated_pimc']} "
          f"leaf_ok={i['leaf_hash_ok']}")
    if not g["pass"]:
        print("[ev_loss] WARNING: gate FAILED — no human number here is reportable.")


if __name__ == "__main__":
    os.nice(19)
    main()
