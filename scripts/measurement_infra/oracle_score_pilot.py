#!/usr/bin/env python3
"""ORACLE-SCORED DISAGREEMENT PILOT — does the deeper pick IMPROVE, or merely MOVE?

STATUS 2026-07-28 (EVENING, supersedes the morning banner below): EXTENDED TO n=100 ON
--resume (100/100 positions, 0 failed, crn_verified_all, M=32, ~81 min at W16) — **THE
QUESTION IS ANSWERED: THE DEEPER PICK IS GENUINELY BETTER.** Mean delta +0.7375 pts per
disagreement (sign = V(11008 pick) - V(2752 pick)); **CITE THE CLUSTER-ROBUST z, NOT the
summary's naive one** — the bank's records are NOT independent (628 records span only 385
distinct roots; this sample of 100 covers 89). Recomputed off the on-disk records:
cluster-robust sandwich on root **z +2.97** (se 0.2486, p 0.0030), naive z +3.07,
conservative root-collapsed +0.5920 / z +2.45; cluster bootstrap of roots 95% CI
[+0.251, +1.226], P(<=0) 0.0014; design effect only 1.067. The morning screen's +1.91 was
REGRESSION TO THE MEAN, not a recompute (resume verified non-recomputing; new-80-only
+0.4434). => 2752 is NOT at the knee, corroborating CL-060's +49.85 elo with an
instrument that has no opponent, no elo and no ruler compression. **THE FULL 628-POSITION
RUN IS NOW UNNECESSARY, not merely unfunded** — it was sized to detect +0.07 pts and the
effect is ~10x that. ⚠️ **UNDERSTANDING, NOT A DEPLOY LEVER: CL-068 stands — 11008 costs
11.2 s/move = 91% of a 15-min sudden-death clock, so the strength is clock-unusable; any
citation of "deeper search finds better moves" must travel with that sentence.**
⚠️ **SOLE REMAINING THREAT TO VALIDITY: same-family self-preference** — the oracle is a
clairvoyant PUCT search on the SAME frozen curve125 leaf as the agents whose picks it
judges. That is a BIAS, so extension cannot shrink it and nothing measured excludes it.
Cheapest discriminator (NAMED, NOT RUN): re-score a ~30-position subset with the
continuation swapped OUT of the family — the Tier-1 greedy RuleBasedPlayer (v1 1-ply
leaf, no search, no curve125), same world seeds and CRN pairing; ~26 ms/move so the whole
rescore is minutes. Read it as a SIGN check only, NEVER a magnitude check. Raising
--oracle-sims addresses only the secondary weak-continuation threat (the family is
unchanged) and is NOT a discriminator. Read-out:
measurement/classical_search/ORACLE_PILOT_EXT_READOUT_20260728.md; DECISIONS 2026-07-28
(evening amendment); log measurement/classical_search/oracle_score_pilot_ext.log.

STATUS 2026-07-28 (MORNING, superseded above on the MEAN; its SD deliverable stands
unchanged at n=100 — 2.406 pts at M=32): PILOT RUN (20/20 positions, 0 failed,
crn_verified_all, ~28 min at W16) — **THE FULL RUN IS NOT FUNDED: it is UNDERPOWERED.**
The deliverable sd landed on
the memo's pessimistic branch: per-position sd of the CRN-paired delta = 2.43 pts at
M=32, with an irreducible between-position floor of ~1.51 pts (within-position noise is
115.9/M, so more worlds cannot rescue it). Implied z for the full 628-position bank at
the pre-registered +0.07 pts assumed effect = 0.72 (M=32) / 0.87 (M=64). The approach is
PARKED with its pilot data attached. Re-open bars (any one): a ~5000-position bank; or
evidence the true per-disagreement effect exceeds ~3x the assumed 0.07 pts [**MET** — the
n=100 extension measured ~10x]; or a
variance-reduction design change attacking the BETWEEN-position term (world-CRN only
touches the within-position part). ⚠️ Read DECISIONS 2026-07-28 item 5 before re-opening:
this pilot's OWN mean delta is +1.91 pts (se 0.54, z +3.53), ~27x the assumed effect —
either the probe is mis-sized or the same-family oracle self-prefers the deeper pick, and
that is unresolved [**RESOLVED in favour of "real, but ~2.5x smaller than the screen
said"; the self-preference half is NOT resolved** — see the evening banner]. Data:
/mnt/c/carc-shared/classical_search/oracle_score_pilot/
{manifest,summary}.json; measurement/classical_search/oracle_score_pilot.log.

PILOT ONLY. Nothing here promotes anything; `governance/PRODUCTION.yaml` is untouched by
construction (this harness never plays a competitive game and never writes a results.csv
row on its own).

WHAT THIS IS
------------
CL-070 established that the deployed champion's pick still CHANGES between the deploy
budget (k4x688 = 2752 total) and 4x deploy (k4x2752 = 11008 total) — but it never measured
whether the change is an IMPROVEMENT. Its own close-out names the successor experiment
(`measurement/classical_search/MOVE_AGREEMENT_PREREG.md`, "The successor experiment this
points at"):

    "take the positions where 2752 and 11008 disagree and score BOTH picks against a
     stronger reference (the exact solver where k_remaining allows, or a much deeper
     search). That converts 'the move changed' into 'the move improved' and prices budget
     directly, sidestepping structural blocker #1 for this one question."

The full probe scores ~652 banked disagreement records. Its power turns on ONE unmeasured
quantity: **the per-position sd of the world-CRN-paired oracle delta.** At sd ~0.5 pts the
full run lands z ~2.2; at sd ~1.5 (i.e. CRN buys nothing) it lands z ~0.75 and is not worth
running. THIS SCRIPT IS THE ~20-POSITION PILOT THAT MEASURES THAT SD, and nothing else.

Read the pilot's output as a VARIANCE measurement. Its own mean delta is a 20-position
screen and is NOT a verdict on whether budget improves the move.

⚠️ THE ORACLE DEFINITION — A PILOT-ONLY CHOICE, MADE HERE, FLAGGED LOUDLY
-------------------------------------------------------------------------
The pre-registration is deliberately ambiguous ("the exact solver ... OR a much deeper
search"). The exact solver only reaches k_remaining <= ~4 (24 of the 652 banked
disagreements), so it cannot be the pilot's instrument. This harness therefore uses:

    V(afterstate | world w) = the FINAL SCORE MARGIN, in engine points, from the root
                              player's perspective, when the game is played out to
                              TERMINAL from `afterstate` under deck completion `w`, with
                              BOTH seats played by the clairvoyant PUCT champion
                              (`HeuristicPriorAgent`, production curve125 leaf) at
                              `--oracle-sims` simulations per move.

    Oracle(pick) = mean over M sampled deck completions of V(afterstate(pick) | w).

Why this and not the alternatives:

  * It is POINTS-VALUED and TERMINAL-GROUNDED. The number that comes out is the engine's
    own `state.scores` differential — the heuristic leaf steers the continuation policy but
    never enters the reported value. That keeps the read-out in the units the memo's
    power arithmetic and the pts->elo exchange rate (`results.csv
    luckfloor_champ_k4x688_vs_greedy_n200_b54e9`: +27.40 pts/deck <-> +478 elo) are
    written in, and makes it the SAME OUTPUT TYPE as the exact solver — so the endgame
    overlap cross-validation the memo asks for is apples-to-apples rather than a units
    conversion.
  * A single clairvoyant search's root Q would be cheaper but returns
    `tanh(score_diff / value_norm)` — leaf-valued, tanh-compressed, and fully inside the
    shared-leaf blind spot.
  * A clairvoyant JUDGEMENT of a single world is the WRONG objective for a PIMC agent (it
    systematically punishes correct hedges). Only the M-world AVERAGE is a valid target,
    which is why M and the CRN pairing, not the per-world search depth, are the design.

  ⚠️ PILOT-ONLY LIMITATIONS OF THIS CHOICE, to be revisited before the full run:
    (a) `--oracle-sims` (default 100 clairvoyant sims/move) is far below the champion's own
        budget. A weak continuation policy biases the value of moves whose payoff needs
        skilled follow-up. Under CRN the bias is largely COMMON to the two picks, which is
        why it is tolerable for a variance pilot; it is NOT obviously tolerable for the
        full run's point estimate. Sweep `--oracle-sims` before committing.
    (b) SHARED-LEAF BLINDNESS (memo Open Risk 1). The continuation policy runs the same
        curve125 leaf as the agent under test. A weakness both share is invisible here.
    (c) No exact-solver tail. Positions with `solver_region` are EXCLUDED by default
        (`--include-solver-region` to keep them), mirroring CL-070's primary readout.

CRN — THE ENTIRE DESIGN, AND HOW IT IS PROVEN RATHER THAN ASSERTED
-------------------------------------------------------------------
Worlds are drawn ONCE PER POSITION and reused verbatim for both picks:

    root board  --reshuffled_determinization(rng=Random(world_seed_j))-->  world board_j
    world board_j --deepcopy--> apply pick A --playout(seed=playout_seed_j)--> V_A_j
    world board_j --deepcopy--> apply pick B --playout(seed=playout_seed_j)--> V_B_j
    delta_j = V_B_j - V_A_j          (paired at the world AND at the policy-seed level)

Both picks place the SAME `next_tile` (they are alternative actions at one root), so the
unseen deck multiset — and therefore the drawn completion — is identical after either.
The harness does not take that on faith: it records, per (pick, world), a hash of the
afterstate deck order and ASSERTS the two picks agree on it for every world, stamping
`crn_verified` into the output. `--strict-crn` (default on) turns a mismatch into a failed
position rather than a silently unpaired row.

Determinism: `world_seed_j` and `playout_seed_j` are SHA-256 derived from
(rid, j, --world-seed-salt) — stable across machines, processes and Python builds (never
`hash()`, which is PYTHONHASHSEED-salted).

READ-OUT
--------
`summary.json` reports, per the memo's power fork:
  * sd_delta_positions       — THE DELIVERABLE. sd of the per-position paired delta.
  * the variance decomposition into BETWEEN-position (irreducible) and WITHIN-position
    (finite-M oracle noise) parts, hence the projected sd at other M.
  * implied z for the full run at the pre-registered assumed effect (+0.07 pts per
    disagreed move <-> ~+50 elo) at N = 265 (the memo's figure) and N = the actual bank.
  * the pilot's own observed mean delta and its z — reported, but explicitly NOT a verdict.

INPUTS (all already on disk; this harness generates no new positions)
---------------------------------------------------------------------
  records dir  /mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/records/
               one JSON per (root, salt); `q_pick_by_level["688"]` is the deploy-2752 pick
               and `q_pick_by_level["2752"]` is the 11008 pick (per-determinization sims
               keys; `total_budgets` maps 688->2752 and 2752->11008).
  roots.jsonl  same run dir; `(deck_seed, actions, ply, checksum)` for lossless replay via
               `scripts/measurement_infra/root_replay.py`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to move_agreement_probe.py / eval_fair_puct's
#     _CANON_ENV. MUST run before importing carcassonne_ai (DEFAULT_CONFIG is import-frozen).
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

REPO = Path(__file__).resolve().parents[2]
# CARC_SRC_ROOT points the import at a PINNED worktree while this harness stays in the
# main tree (the move_agreement_probe convention).
SRC_ROOT = os.environ.get("CARC_SRC_ROOT") or str(REPO / "src")
sys.path.insert(0, SRC_ROOT)
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import argparse            # noqa: E402
import copy                # noqa: E402
import hashlib             # noqa: E402
import json                # noqa: E402
import math                # noqa: E402
import multiprocessing as mp  # noqa: E402
import random              # noqa: E402
import signal              # noqa: E402
import socket              # noqa: E402
import subprocess          # noqa: E402
import time                # noqa: E402

import numpy as np         # noqa: E402

import root_replay as RR   # noqa: E402
from carcassonne_ai import champion_factory as CF          # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent  # noqa: E402

SCHEMA = "carcassonne-oracle-score-pilot/v1"

DEFAULT_RUN_DIR = "/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9"

# Per-determinization sims keys in the CL-070 records, and the total budgets they mean.
# k_dets is fixed at 4 in that run, so total = 4 * level.
LEVEL_A_DEFAULT = 688     # -> 2752 total (the DEPLOY budget)
LEVEL_B_DEFAULT = 2752    # -> 11008 total (4x deploy)

# The memo's pre-registered assumed effect: ~+0.07 pts per disagreed move <-> ~+50 elo.
ASSUMED_EFFECT_DEFAULT = 0.07
MEMO_N_POSITIONS = 265    # the memo's headline full-run N (873 roots x D_cross 0.3039)


# --------------------------------------------------------------------------- #
# Pure helpers — unit-tested in tests/test_oracle_score_pilot.py                #
# --------------------------------------------------------------------------- #
def json_safe(obj):
    """Replace inf/NaN with null so the emitted files are STRICT JSON.

    `json.dump` happily writes bare `Infinity`/`NaN`, which Python re-reads but jq, JS and
    most other consumers reject — a silent trap for anything that reads these artifacts
    later. `crn_var_reduction` is genuinely infinite when a position's two picks are
    value-identical in every world, so this is a real case, not a defensive one."""
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
        return None
    return obj


def _sha_int(*parts) -> int:
    """Stable 31-bit integer from the given parts. NEVER `hash()` (PYTHONHASHSEED-salted),
    so seeds reproduce across machines, processes and Python builds."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFF


def world_seed(rid: str, j: int, salt: str) -> int:
    """Deck-completion seed for world `j` of position `rid`. Depends on NEITHER the pick
    NOR the budget — that is the CRN contract."""
    return _sha_int("world", rid, j, salt)


def playout_seed(rid: str, j: int, salt: str) -> int:
    """Continuation-policy seed for world `j` of position `rid`. Also pick-independent, so
    the two picks are paired at the policy level as well as the world level."""
    return _sha_int("playout", rid, j, salt)


def world_seeds(rid: str, m: int, salt: str) -> list:
    return [world_seed(rid, j, salt) for j in range(int(m))]


def load_disagreements(records_dir, level_a: int, level_b: int,
                       include_solver_region: bool = False) -> list:
    """Every banked (root, salt) record whose deploy pick differs from its 4x pick.

    Returns dicts sorted by (root_id, salt) — a total order independent of filesystem
    listing order, so the downstream sample is reproducible."""
    out = []
    for p in sorted(Path(records_dir).glob("s*.json")):
        try:
            d = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not d.get("ok"):
            continue
        q = d.get("q_pick_by_level") or {}
        a, b = q.get(str(level_a)), q.get(str(level_b))
        if a is None or b is None or int(a) == int(b):
            continue
        if d.get("solver_region") and not include_solver_region:
            continue
        out.append({
            "rid": d["rid"], "root_id": d["root_id"],
            "deck_seed": int(d["deck_seed"]), "ply": int(d["ply"]),
            "salt": int(d["salt"]),
            "pick_a": int(a), "pick_b": int(b),
            "root_player": int(d["root_player"]),
            "k_remaining": d.get("k_remaining"),
            "game_phase": d.get("game_phase"), "phase_bucket": d.get("phase_bucket"),
            "n_legal": d.get("n_legal"),
            "h200_top2_q_gap": d.get("h200_top2_q_gap"),
            "solver_region": bool(d.get("solver_region")),
        })
    out.sort(key=lambda r: (r["root_id"], r["salt"]))
    return out


def sample_positions(population: list, n: int, seed: int) -> list:
    """Deterministic seeded sample, returned in the population's own sorted order.

    Determinism contract (asserted in tests): same population + same seed => same rids,
    regardless of listing order upstream, and a prefix-stable order downstream."""
    pop = sorted(population, key=lambda r: (r["root_id"], r["salt"]))
    n = int(n)
    if n >= len(pop):
        return list(pop)
    idx = sorted(random.Random(int(seed)).sample(range(len(pop)), n))
    return [pop[i] for i in idx]


def _finite(x) -> bool:
    """True only for a real, finite number. Records are re-read from disk where json_safe
    has mapped inf/NaN to None, and `None == None` defeats the usual `x == x` NaN test."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _var(xs, ddof=1):
    xs = list(xs)
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    mu = _mean(xs)
    return sum((x - mu) ** 2 for x in xs) / (n - ddof)


def _crn_ratio(unpaired_var, within_var):
    """unpaired/paired variance ratio, with the degenerate cases named rather than NaN'd."""
    if unpaired_var != unpaired_var or within_var != within_var:
        return float("nan")
    if within_var <= 0.0:
        return float("inf") if unpaired_var > 0.0 else float("nan")
    return unpaired_var / within_var


def position_delta(values_a: list, values_b: list) -> dict:
    """The world-paired per-position statistic.

    delta_j = V_B_j - V_A_j over the SHARED worlds; the position's delta is their mean.
    `within_var` is the variance of delta_j across worlds — the finite-M oracle noise —
    and is what makes the M-projection in `summarize` possible. The UNPAIRED variance is
    also returned so the run can report how much the CRN pairing actually bought."""
    if len(values_a) != len(values_b) or not values_a:
        raise ValueError("values_a and values_b must be equal-length and non-empty")
    per_world = [float(b) - float(a) for a, b in zip(values_a, values_b)]
    m = len(per_world)
    var_a, var_b = _var(values_a), _var(values_b)
    unpaired_var = (var_a + var_b) if m > 1 else float("nan")
    within = _var(per_world) if m > 1 else float("nan")
    return {
        "m": m,
        "per_world_delta": per_world,
        "mean_a": _mean(values_a), "mean_b": _mean(values_b),
        "delta": _mean(per_world),
        "within_var": within,
        "within_se": (math.sqrt(within / m) if within == within else float("nan")),
        "unpaired_var": unpaired_var,
        # >1 means the pairing removed variance; this is the CRN efficiency the pilot exists
        # to measure, read at the WITHIN-position level. within_var == 0 (the two picks are
        # value-identical in every world, e.g. a transposition) is PERFECT pairing -> inf.
        "crn_var_reduction": _crn_ratio(unpaired_var, within),
    }


def summarize(rows: list, *, m: int, assumed_effect: float,
              full_n_bank: int, project_m=(8, 16, 32, 64)) -> dict:
    """The pilot's deliverable: the sd of the per-position paired delta, its decomposition,
    and the implied z for the full run."""
    deltas = [r["delta"] for r in rows if r.get("ok")]
    n = len(deltas)
    if n < 2:
        return {"n_positions": n, "error": "need >= 2 completed positions"}
    sd_pos = math.sqrt(_var(deltas))
    mean_delta = _mean(deltas)
    se_mean = sd_pos / math.sqrt(n)

    # NB: rows are re-read from disk, where json_safe has already mapped inf/NaN to None
    # (strict JSON). `None == None` is True, so the usual `x == x` NaN test would let a
    # None through and blow up the arithmetic — filter on finiteness, not self-equality.
    withins = [r["within_var"] for r in rows if r.get("ok") and _finite(r.get("within_var"))]
    mean_within_var = _mean(withins) if withins else float("nan")
    # var(delta_i) = var_between_true + within_var / M  =>  peel off the finite-M part.
    var_between = float("nan")
    if mean_within_var == mean_within_var:
        var_between = max(sd_pos ** 2 - mean_within_var / m, 0.0)

    def sd_at(mm):
        if var_between != var_between or mean_within_var != mean_within_var:
            return float("nan")
        return math.sqrt(var_between + mean_within_var / mm)

    def z_at(sd, nn):
        return (assumed_effect * math.sqrt(nn) / sd) if (sd and sd == sd) else float("nan")

    # `crn_var_reduction` is None on disk when a position paired PERFECTLY (within_var 0 ->
    # inf). Dropping those would bias the median DOWNWARD, so count them separately.
    crn = [r["crn_var_reduction"] for r in rows
           if r.get("ok") and _finite(r.get("crn_var_reduction"))]
    n_perfect_pairing = sum(1 for r in rows if r.get("ok")
                            and r.get("crn_var_reduction") is None
                            and _finite(r.get("within_var")) and r["within_var"] == 0.0)
    n_identical_afterstates = sum(1 for r in rows if r.get("ok")
                                  and r.get("distinct_afterstates") == 0)

    out = {
        "n_positions": n,
        "m_worlds": m,
        "sd_delta_positions": sd_pos,                 # <-- THE DELIVERABLE
        "mean_delta_pts": mean_delta,
        "se_mean_delta": se_mean,
        "z_pilot_observed": (mean_delta / se_mean) if se_mean else float("nan"),
        "mean_within_position_var": mean_within_var,
        "var_between_positions_est": var_between,
        "sd_delta_projected_by_m": {str(mm): sd_at(mm) for mm in project_m},
        "median_crn_var_reduction": (sorted(crn)[len(crn) // 2] if crn else float("nan")),
        "n_positions_perfect_pairing": n_perfect_pairing,
        # >0 here means some sampled pairs of "different" actions transpose to the SAME
        # afterstate — a zero delta there is an identity, not evidence about budget.
        "n_positions_identical_afterstates": n_identical_afterstates,
        "assumed_effect_pts": assumed_effect,
        "implied_z_full_run": {
            f"N={MEMO_N_POSITIONS}_at_M={m}": z_at(sd_pos, MEMO_N_POSITIONS),
            f"N={full_n_bank}_at_M={m}": z_at(sd_pos, full_n_bank),
            **{f"N={full_n_bank}_at_M={mm}": z_at(sd_at(mm), full_n_bank)
               for mm in project_m},
        },
        "memo_power_fork": {
            "note": ("memo §4.2: sd ~0.5 pts => z ~2.2 (fund the full run); "
                     "sd ~1.5 pts => z ~0.75 (do not). Read sd_delta_positions against this."),
            "z_if_sd_0.5": z_at(0.5, MEMO_N_POSITIONS),
            "z_if_sd_1.5": z_at(1.5, MEMO_N_POSITIONS),
        },
        "caveat": ("The pilot's own mean_delta is a 20-position SCREEN, NOT a verdict on "
                   "whether budget improves the move. The deliverable is the sd."),
    }
    return out


# --------------------------------------------------------------------------- #
# Worker globals (set once per process by _init)                                #
# --------------------------------------------------------------------------- #
_G = {}


def _init(cfg_kw: dict) -> None:
    _G.update(cfg_kw)
    _G["cfg"] = CF.production_prior_cfg()


def _deck_hash(board) -> str:
    """Order-sensitive hash of a board's deck — the CRN witness. Two picks applied to the
    SAME determinized world must agree on this."""
    h = hashlib.sha256()
    for t in board.state.deck:
        h.update(str(t.description).encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def _playout_value(game, world_board, action: int, root_player: int,
                   seed: int, sims: int, max_plies: int):
    """Apply `action` to a COPY of `world_board`, play to terminal with the clairvoyant
    champion on both seats, and return (margin_pts, afterstate_deck_hash,
    afterstate_board_key, n_plies)."""
    b = copy.deepcopy(world_board)
    b, _ = game.get_next_state(b, int(action))
    dh = _deck_hash(b)
    bk = hashlib.sha256(game.string_representation(b).encode()).hexdigest()[:16]
    agent = CF.build_clairvoyant_champion(game, cfg=_G["cfg"], simulations=int(sims),
                                          seed=int(seed))
    plies = 0
    while not b.state.is_terminated():
        if plies >= max_plies:
            raise RuntimeError(f"playout exceeded max_plies={max_plies}")
        a = agent.best_action(b)
        b, _ = game.get_next_state(b, int(a))
        plies += 1
    agent.clear()
    opp = 1 - int(root_player)
    margin = float(b.state.scores[int(root_player)] - b.state.scores[opp])
    return margin, dh, bk, plies


def _process(item: dict) -> dict:
    """Score ONE banked disagreement position under M CRN-shared deck completions."""
    rid = item["rid"]
    rec = {k: item[k] for k in (
        "rid", "root_id", "deck_seed", "ply", "salt", "pick_a", "pick_b",
        "root_player", "k_remaining", "game_phase", "phase_bucket", "n_legal",
        "h200_top2_q_gap", "solver_region")}
    rec.update({
        "schema": SCHEMA,
        "level_a": _G["level_a"], "level_b": _G["level_b"],
        "total_budget_a": 4 * _G["level_a"], "total_budget_b": 4 * _G["level_b"],
        "m": _G["m"], "oracle_sims": _G["oracle_sims"],
        "world_seed_salt": _G["world_seed_salt"],
    })
    t0 = time.time()

    def _on_alarm(signum, frame):
        raise TimeoutError("per-position wall cap")
    old = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(int(_G["wall_cap"]))
    try:
        game, board = RR.replay_actions(item["deck_seed"], item["actions"], item["ply"])
        cks = game.string_representation(board)
        rec["checksum_ok"] = bool(item.get("checksum") is None or cks == item["checksum"])
        if not rec["checksum_ok"]:
            rec.update(ok=False, error="checksum_mismatch")
            return rec

        legal = set(int(x) for x in np.flatnonzero(game.get_valid_moves(board)))
        for tag in ("pick_a", "pick_b"):
            if int(item[tag]) not in legal:
                rec.update(ok=False, error=f"{tag}_illegal_at_root")
                return rec

        ws = world_seeds(rid, _G["m"], _G["world_seed_salt"])
        ps = [playout_seed(rid, j, _G["world_seed_salt"]) for j in range(_G["m"])]
        rec["world_seeds"] = ws
        rec["playout_seeds"] = ps

        va, vb, dh_a, dh_b, bk_a, bk_b, plies_a, plies_b = [], [], [], [], [], [], [], []
        for j in range(_G["m"]):
            # ONE determinization per world, SHARED by both picks. This is the CRN.
            wb = FairHeuristicMCTSAgent.reshuffled_determinization(
                board, random.Random(ws[j]))
            ma, ha, ka, pa = _playout_value(game, wb, item["pick_a"], item["root_player"],
                                            ps[j], _G["oracle_sims"], _G["max_plies"])
            mb, hb, kb, pb = _playout_value(game, wb, item["pick_b"], item["root_player"],
                                            ps[j], _G["oracle_sims"], _G["max_plies"])
            va.append(ma); vb.append(mb)
            dh_a.append(ha); dh_b.append(hb)
            bk_a.append(ka); bk_b.append(kb)
            plies_a.append(pa); plies_b.append(pb)

        rec["values_a"] = va
        rec["values_b"] = vb
        rec["afterstate_deck_hash_a"] = dh_a
        rec["afterstate_deck_hash_b"] = dh_b
        rec["afterstate_board_key_a"] = bk_a
        rec["afterstate_board_key_b"] = bk_b
        rec["playout_plies_a"] = plies_a
        rec["playout_plies_b"] = plies_b
        # CRN WITNESS: same world => same completed deck after either pick. If this ever
        # fails the two arms are NOT paired and the whole design is void for that position.
        rec["crn_verified"] = bool(dh_a == dh_b)
        # NO-OP WITNESS: the two picks must land on DIFFERENT afterstates, otherwise a zero
        # delta means "the harness did nothing", not "the moves are equivalent". Recorded
        # rather than asserted, because two actions CAN legitimately transpose to the same
        # board key (e.g. a rotationally symmetric tile) — a real equivalence, worth seeing.
        rec["distinct_afterstates"] = int(sum(1 for x, y in zip(bk_a, bk_b) if x != y))
        if not rec["crn_verified"] and _G["strict_crn"]:
            rec.update(ok=False, error="crn_deck_hash_mismatch")
            return rec

        rec.update(position_delta(va, vb))
        rec["ok"] = True
        return rec
    except Exception as exc:                                   # noqa: BLE001
        # A single bad position must not take the pool down (the engine can raise
        # WindowOverflowError, the solver can raise, the wall cap raises TimeoutError).
        # It is recorded as a failed row and excluded from the summary, never silently
        # counted as a zero delta.
        rec.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        return rec
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        rec["elapsed_secs"] = round(time.time() - t0, 3)


# --------------------------------------------------------------------------- #
# Driver                                                                        #
# --------------------------------------------------------------------------- #
def _git_rev(path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                     # noqa: BLE001
        return "unknown"


def build_manifest(args, population_n: int, chosen: list) -> dict:
    return {
        "schema": SCHEMA,
        "harness": "oracle_score_pilot",
        "status": "PILOT — measures the per-position sd of the CRN-paired oracle delta. "
                  "Its own mean delta is NOT a verdict.",
        "goal": "Convert CL-070's 'the move changed' into 'the move improved' on a "
                "20-position pilot, and measure the world-CRN variance reduction that "
                "decides whether the full ~652-position probe is powered.",
        "oracle": {
            "definition": "mean over M sampled deck completions of the TERMINAL engine "
                          "score margin (root-player POV, points) after playing the "
                          "afterstate out with the clairvoyant PUCT champion on both seats",
            "continuation_agent": "HeuristicPriorAgent via "
                                  "champion_factory.build_clairvoyant_champion",
            "oracle_sims": int(args.oracle_sims),
            "value_units": "engine points (final score differential)",
            "pilot_only_caveats": [
                "oracle_sims is far below the champion's own budget — weak-continuation bias",
                "shared curve125 leaf with the agent under test (shared-leaf blindness)",
                "no exact-solver tail; solver_region positions excluded by default",
            ],
        },
        "crn": {
            "level": "world (deck completion) AND continuation-policy seed",
            "seed_derivation": "sha256(tag|rid|j|world_seed_salt) -> 31-bit; "
                               "independent of pick and of budget",
            "witness": "afterstate deck-order hash asserted equal across the two picks "
                       "for every world (crn_verified)",
            "strict": bool(args.strict_crn),
        },
        "source": {
            "run_dir": str(args.run_dir),
            "records_dir": str(args.records_dir),
            "roots": str(args.roots),
            "claim": "CL-070 / measurement/classical_search/MOVE_AGREEMENT_PREREG.md",
        },
        "levels": {
            "level_a_sims_per_det": int(args.level_a), "total_budget_a": 4 * int(args.level_a),
            "level_b_sims_per_det": int(args.level_b), "total_budget_b": 4 * int(args.level_b),
            "k_dets": 4,
            "decision_rule": "q_argmax_action (pooled_q_argmax) — the DEPLOYED fair pick",
        },
        "sampling": {
            "population_disagreements": population_n,
            "n_requested": int(args.n), "n_chosen": len(chosen),
            "sample_seed": int(args.sample_seed),
            "include_solver_region": bool(args.include_solver_region),
            "rids": [c["rid"] for c in chosen],
        },
        "m_worlds": int(args.m),
        "workers": int(args.workers),
        "wall_cap_secs": int(args.wall_cap),
        "max_plies": int(args.max_plies),
        "assumed_effect_pts": float(args.assumed_effect),
        "env": dict(_CANON_ENV),
        "src_root": SRC_ROOT,
        "code_rev": _git_rev(REPO),
        "host": socket.gethostname(),
        # verify=True PROVES the curve125 leaf on real boards and RAISES on mismatch —
        # the R1/R7-class provenance guard, run once in the parent before any worker forks.
        "champion_manifest": CF.resolved_manifest("clairvoyant", verify=True),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", default=DEFAULT_RUN_DIR,
                    help="CL-070 run dir holding records/ and roots.jsonl")
    ap.add_argument("--records-dir", default=None)
    ap.add_argument("--roots", default=None)
    ap.add_argument("--level-a", type=int, default=LEVEL_A_DEFAULT)
    ap.add_argument("--level-b", type=int, default=LEVEL_B_DEFAULT)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--sample-seed", type=int, default=20260728)
    ap.add_argument("--m", type=int, default=32, help="deck completions per position")
    ap.add_argument("--oracle-sims", type=int, default=100,
                    help="clairvoyant sims/move for the continuation policy")
    ap.add_argument("--world-seed-salt", default="oracle-pilot-v1")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--wall-cap", type=int, default=7200, help="per-position seconds")
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--include-solver-region", action="store_true")
    ap.add_argument("--assumed-effect", type=float, default=ASSUMED_EFFECT_DEFAULT)
    ap.add_argument("--strict-crn", dest="strict_crn", action="store_true", default=True)
    ap.add_argument("--no-strict-crn", dest="strict_crn", action="store_false")
    ap.add_argument("--out-root", default="/mnt/c/carc-shared/classical_search")
    ap.add_argument("--out-subdir", default="oracle_score_pilot")
    ap.add_argument("--resume", action="store_true",
                    help="skip positions that already have a record on disk")
    ap.add_argument("--dry-run", action="store_true",
                    help="sample + write the manifest, score nothing")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    records_dir = Path(args.records_dir) if args.records_dir else run_dir / "records"
    roots_path = Path(args.roots) if args.roots else run_dir / "roots.jsonl"
    args.records_dir, args.roots = records_dir, roots_path

    out_dir = Path(args.out_root) / args.out_subdir
    (out_dir / "records").mkdir(parents=True, exist_ok=True)

    pop = load_disagreements(records_dir, args.level_a, args.level_b,
                             args.include_solver_region)
    if not pop:
        print("[fatal] no disagreement records found — check --records-dir / --level-*",
              file=sys.stderr)
        return 2
    chosen = sample_positions(pop, args.n, args.sample_seed)

    # Join the sampled positions back to their replay sequences.
    roots = {}
    for line in roots_path.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        roots[f"s{int(o['deck_seed'])}_p{int(o['ply'])}"] = o
    items = []
    for c in chosen:
        r = roots.get(c["root_id"])
        if r is None:
            print(f"[fatal] root {c['root_id']} missing from {roots_path}", file=sys.stderr)
            return 2
        it = dict(c)
        it["actions"] = [int(a) for a in r["actions"]]
        it["checksum"] = r.get("checksum")
        items.append(it)

    manifest = build_manifest(args, len(pop), chosen)
    (out_dir / "manifest.json").write_text(
        json.dumps(json_safe(manifest), indent=2, allow_nan=False))
    print(f"[pilot] population={len(pop)} disagreements | sampled n={len(items)} "
          f"| M={args.m} | oracle_sims={args.oracle_sims} | W={args.workers}")
    print(f"[pilot] out -> {out_dir}")
    if args.dry_run:
        print("[pilot] --dry-run: manifest written, nothing scored")
        return 0

    todo = items
    if args.resume:
        todo = [it for it in items if not (out_dir / "records" / f"{it['rid']}.json").exists()]
        print(f"[pilot] resume: {len(items) - len(todo)} already done, {len(todo)} to go")

    cfg_kw = dict(level_a=int(args.level_a), level_b=int(args.level_b), m=int(args.m),
                  oracle_sims=int(args.oracle_sims), world_seed_salt=args.world_seed_salt,
                  wall_cap=int(args.wall_cap), max_plies=int(args.max_plies),
                  strict_crn=bool(args.strict_crn))

    t0 = time.time()
    results = []
    if todo:
        w = max(1, min(int(args.workers), len(todo)))
        ctx = mp.get_context("fork")
        with ctx.Pool(w, initializer=_init, initargs=(cfg_kw,)) as pool:
            for i, rec in enumerate(pool.imap_unordered(_process, todo), 1):
                p = out_dir / "records" / f"{rec['rid']}.json"
                tmp = p.with_suffix(".tmp")
                tmp.write_text(json.dumps(json_safe(rec), allow_nan=False))
                os.replace(tmp, p)
                results.append(rec)
                flag = "ok" if rec.get("ok") else f"FAIL {rec.get('error')}"
                print(f"[{i}/{len(todo)}] {rec['rid']} {flag} "
                      f"delta={rec.get('delta', float('nan')):+.3f} "
                      f"crn={rec.get('crn_verified')} {rec.get('elapsed_secs')}s",
                      flush=True)

    # Re-read every record so --resume runs summarize over the full sample.
    rows = []
    for it in items:
        p = out_dir / "records" / f"{it['rid']}.json"
        if p.exists():
            rows.append(json.loads(p.read_text()))

    summary = summarize(rows, m=int(args.m), assumed_effect=float(args.assumed_effect),
                        full_n_bank=len(pop))
    summary.update({
        "schema": SCHEMA,
        "n_attempted": len(items),
        "n_failed": sum(1 for r in rows if not r.get("ok")),
        "crn_verified_all": all(r.get("crn_verified") for r in rows if r.get("ok")),
        "population_disagreements": len(pop),
        "wall_secs": round(time.time() - t0, 1),
        "manifest": str(out_dir / "manifest.json"),
    })
    (out_dir / "summary.json").write_text(
        json.dumps(json_safe(summary), indent=2, allow_nan=False))

    print("\n=== ORACLE-SCORE PILOT SUMMARY ===")
    print(json.dumps(json_safe(summary), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
