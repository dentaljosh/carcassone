#!/usr/bin/env python3
"""MOVE-AGREEMENT vs BUDGET — does the deployed champion stop changing its move?

THE QUESTION
------------
The blind budget curve (7 rungs, n=200, band 70e9, vs sighted RoD-v2 iter_02) rises to
~2064 sims then goes FLAT: every deck-matched step above 2752 is null on BOTH statistics.
Two hypotheses are indistinguishable from any game-playing experiment against that ruler:

  H1 GENUINE CONVERGENCE   — above ~2064 the search stops changing its chosen move, so
                             extra sims CANNOT buy strength.
  H2 INSTRUMENT COMPRESSION — the champion keeps improving but RoD2 (a ~h3200-tier
                             yardstick) is too weak to register it.

H1 is directly measurable with NO OPPONENT AT ALL: does the FINAL SELECTED ACTION stop
changing as budget grows? That is what this harness measures.

THE DESIGN POINT THAT MAKES IT INTERPRETABLE — THE SAME-BUDGET NOISE FLOOR
--------------------------------------------------------------------------
The champion is STOCHASTIC: `FairHeuristicPriorAgent` samples k_dets determinizations per
move (blind PIMC), so two runs at the SAME budget with different RNG disagree at some
nonzero rate. A raw cross-budget disagreement number is therefore uninterpretable alone.

`det_seed_base(move_idx) = (seed*1_000_003 + move_idx*8191) & 0x7FFFFFFF` and
`det_search_seed = base + 100 + det_idx` depend ONLY on (agent seed, move index) — NOT on
the sim budget. So at a fixed agent seed, an agent at ANY budget draws the SAME k_dets
worlds with the SAME per-world search seeds. That gives two cleanly separated contrasts,
and this harness produces BOTH by running each root under R independent seed lineages
("salts"):

  D_paired(L1,L2)  same salt, different budget.  Worlds AND search seeds held fixed, so
                   ONLY depth varies. Its same-budget null is EXACTLY 0 by construction
                   (a salt replayed at the same budget is bit-identical). Maximum power
                   to detect "depth changes the move at all".

  D_same(L)        different salt, SAME budget.  THE NOISE FLOOR: the agent's own
                   run-to-run churn from resampled determinizations.

  D_cross(L1,L2)   different salt, different budget.  Matched to the floor — both worlds
                   and depth vary — so D_cross vs D_same is an apples-to-apples contrast.

  NULL for the floor comparison: if the per-position move DISTRIBUTIONS at L1 and L2 are
  identical (i.e. budget changed nothing about what the agent plays), then for independent
  reseeds D_cross = 1 - sum_i p_i q_i with p == q, so

        D_cross_null(L1,L2) = 1 - sqrt( (1-D_same(L1)) * (1-D_same(L2)) )

  (Cauchy-Schwarz makes this the exact equality case, and a lower bound otherwise.) The
  decision-bearing statistic is the EXCESS  Delta = D_cross - D_cross_null, tested by a
  position-level bootstrap. Delta ~ 0 => the budgets are drawing from the same move
  distribution => convergence. Delta > 0 => budget still moves the choice.

HOW IT IS CHEAP — SNAPSHOTTING, AND WHAT IS/IS NOT BIT-EXACT
-------------------------------------------------------------
Bit-exactness holds WITHIN a world, not across worlds. Each world's search is an ordinary
serial (batch_size=1, fair_chance=False) `NeuralMCTS` on its own fixed reshuffled board
with its own fixed seed, so the first L sims of a max(levels)-sim search ARE bit-exact to a
standalone L-sim search on that world. We therefore run ONE deep search PER WORLD and
snapshot it at every level (k_dets searches per salt, NOT k_dets x n_levels), then POOL AT
EACH LEVEL. The whole 7-rung ladder costs what its DEEPEST rung alone would.

⚠️ This is the same argument `snapshot.py` makes for the CLAIRVOYANT `HeuristicMCTS` path,
but it is NOT inherited — `snapshot.py`'s guarantee does not cover per-determinization PIMC.
It is re-established here for the fair agent and PROVEN per run by two flags:
  --verify-bit-exact   re-runs every world standalone at every level; asserts visit vectors
                       match the snapshot.
  --verify-agent-parity runs the REAL `FairHeuristicPriorAgent._pimc_move` at the deepest
                       budget and asserts it returns the action this harness reports as the
                       deepest level's deployed pick. This is the strongest check: it proves
                       the reimplementation reproduces the DEPLOYED decision exactly.
Do not trust either claim without the flags.

DECISION RULE
-------------
`q_argmax_action` = `pooled_q_argmax` (pooled Q = sum W / sum N, min_pooled_visits floor,
(Q,N,-a) tiebreak) — THIS IS THE DEPLOYED FAIR PICK and the primary metric. `played_action`
(argmax pooled VISITS) is also recorded, for comparability with the Gate-B harnesses only.

ENDGAME SOLVER: `choose_action` LATCHES to the marginalized exact solver at
k_remaining <= exact_max_k (2) and stays latched. Those roots are budget-independent by
construction; `solver_region` is recorded per root and they are EXCLUDED from the primary
readout (reported separately) rather than silently inflating agreement.

Derived from `gate_b_fair_pimc.py` (the fair-PIMC snapshot record), which is left untouched.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to gate_b_fair_pimc.py / eval_fair_puct's
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
# CARC_SRC_ROOT points the import at the PINNED worktree (verified byte-identical to the
# tree that produced the blind curve) while this harness stays committed in the main tree.
SRC_ROOT = os.environ.get("CARC_SRC_ROOT") or str(REPO / "src")
sys.path.insert(0, SRC_ROOT)
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import argparse  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import signal  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.fair_agent import (  # noqa: E402
    FairHeuristicMCTSAgent,
    k_remaining as fair_k_remaining,
    pooled_q_argmax,
)
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402

import root_replay as RR  # noqa: E402

# PER-WORLD sim levels. At k_dets=4 the TOTAL budgets are 4x these:
#   86->344  172->688  344->1376  516->2064  688->2752  1376->5504  2752->11008
# i.e. the blind curve's seven rungs, at the fixed k4 allocation.
DEFAULT_LEVELS = (86, 172, 344, 516, 688, 1376, 2752)

# per-worker globals (fork-inherited; set in _init_worker)
_CFG = None
_LEVELS = None
_KDETS = None
_WALL = None
_VERIFY_BE = None
_VERIFY_PARITY = None
_MINPV = None
_OUT = None


# --------------------------------------------------------------------------- #
# Seeds                                                                         #
# --------------------------------------------------------------------------- #
def root_seed(deck_seed: int, ply: int, salt: int) -> int:
    """Agent seed for one (root, salt). Distinct salts => independent world draws AND
    independent per-world search seeds; identical salt => bit-identical replay."""
    return (int(deck_seed) * 1_000_003 + int(ply) * 8191
            + int(salt) * 2_654_435_761) & 0x7FFFFFFF


# --------------------------------------------------------------------------- #
# Snapshot of ONE world's search (bit-exact WITHIN the world)                    #
# --------------------------------------------------------------------------- #
def read_children_nw(root, root_player) -> dict:
    """Deduped visited children -> {action: (N, W_rootpov)}. Same dedup + sign convention
    as `fair_agent.pool_root_stats` (which pools W, not Q). Q = W/N after pooling."""
    seen: set[int] = set()
    out: dict[int, tuple[int, float]] = {}
    for a in sorted(root.children):
        ch = root.children[a]
        if ch.N <= 0 or id(ch) in seen:
            continue
        seen.add(id(ch))
        w = ch.W if ch.player_to_move == root_player else -ch.W
        out[int(a)] = (int(ch.N), float(w))
    return out


def snapshot_world_search(m: NeuralMCTS, board, levels):
    """Mirror `NeuralMCTS.search`'s serial setup, then step max(levels) PUCT sims,
    snapshotting deduped root child (N, W_rootpov) at each level. `m` must be fresh."""
    assert m.batch_size == 1, "snapshot path is serial (batch_size=1) only"
    assert not m.fair_chance, ("snapshot path expects fair_chance=False — the fair regime "
                               "comes from the RESHUFFLED BOARD, not in-search chance sampling")
    assert m._root_prior_override is None, "no root-prior override in the agreement probe"
    levels = sorted(int(x) for x in levels)
    root_key = m.game.string_representation(board)
    root = m._nodes.get(root_key)
    if root is None:
        root = m._create_node(board)
        m._nodes[root_key] = root
    if not root.expanded and not root.is_terminal:
        priors_b, values_b = m._eval_boards([board])
        m._expand_with_priors(root, board, priors_b[0], float(values_b[0]))
    root_player = root.player_to_move
    snaps = {}
    idx = 0
    for i in range(1, levels[-1] + 1):
        m._simulate(board, root)
        if idx < len(levels) and i == levels[idx]:
            snaps[levels[idx]] = read_children_nw(root, root_player)
            idx += 1
    return snaps, root_player


def _pooled_visits_best(agg_n: dict, agg_w: dict):
    """(action, N, Q_rootpov) with max POOLED visits; ties -> lowest action id."""
    items = sorted(((int(a), agg_n[a], agg_w[a] / agg_n[a]) for a in agg_n if agg_n[a] > 0),
                   key=lambda t: t[0])
    if not items:
        return None
    best = items[0]
    for it in items[1:]:
        if it[1] > best[1]:
            best = it
    return best


# --------------------------------------------------------------------------- #
# Per-(root, salt) worker                                                       #
# --------------------------------------------------------------------------- #
def _rid(r: dict) -> str:
    return f"s{int(r['deck_seed'])}_p{int(r['ply'])}_r{int(r['salt'])}"


def _process(r: dict) -> dict:
    deck_seed, ply, salt = int(r["deck_seed"]), int(r["ply"]), int(r["salt"])
    rec = {"root_id": f"s{deck_seed}_p{ply}", "rid": _rid(r),
           "deck_seed": deck_seed, "ply": ply, "salt": salt,
           "levels": list(_LEVELS), "k_dets": int(_KDETS),
           "total_budgets": [int(_KDETS) * L for L in _LEVELS],
           "phase_bucket": r.get("phase_bucket"), "game_phase": r.get("phase"),
           "h200_top2_q_gap": r.get("h200_top2_q_gap"),
           "blind_top2_q_gap": r.get("blind_top2_q_gap"),
           "info_mode": "fair_pimc"}
    t0 = time.time()

    def _on_alarm(signum, frame):
        raise TimeoutError("per-root wall cap")
    old = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(int(_WALL))
    try:
        game, board = RR.replay_actions(deck_seed, r["actions"], ply)
        cksum = game.string_representation(board)
        rec["checksum_ok"] = bool(r.get("checksum") is None or cksum == r["checksum"])
        if not rec["checksum_ok"]:
            rec["error"] = "checksum_mismatch"
            rec["ok"] = False
            return rec

        legal = np.flatnonzero(game.get_valid_moves(board))
        rec["n_legal"] = int(legal.size)
        if legal.size < 2:
            rec["error"] = "forced_move"      # must have been filtered at sample time
            rec["ok"] = False
            return rec

        rseed = root_seed(deck_seed, ply, salt)
        rec["agent_seed"] = rseed
        max_L = max(_LEVELS)
        agent = CF.build_fair_champion(game, sims=max_L, k_dets=int(_KDETS),
                                       seed=rseed, cfg=_CFG)
        # Fidelity guard: this harness mirrors the PINNED _pimc_move, which constructs its
        # per-world NeuralMCTS with no meeple_dedup / intra_reuse. If a later rev added
        # those knobs ON, the mirror would silently diverge from the deployed agent.
        for attr in ("_meeple_dedup", "_intra_reuse"):
            if getattr(agent, attr, False):
                raise AssertionError(
                    f"agent has {attr} enabled — this harness mirrors the PINNED "
                    f"_pimc_move which has no such knob; the mirror would diverge")

        k_rem = fair_k_remaining(board.state)
        rec["k_remaining"] = int(k_rem)
        rec["exact_max_k"] = int(agent._exact_max_k)
        # `choose_action` latches at k<=exact_max_k in TILES and STAYS latched, so any root
        # at or below the band is solver-decided in production regardless of phase.
        rec["solver_region"] = bool(agent._exact_endgame and k_rem <= agent._exact_max_k)
        rec["solver_latch_now"] = bool(agent._exact_endgame
                                       and board.state.phase == GamePhase.TILES
                                       and k_rem <= agent._exact_max_k)

        base = agent.det_seed_base(0)          # fixed-root probe -> move_idx 0
        rec["det_seed_base"] = int(base)
        det_rng = random.Random(base + 1)      # ONE stream, k_dets sequential shuffles
        evaluator = agent._evaluator
        c_puct = agent._c_puct

        world_snaps, world_boards = [], []
        root_player = None
        for i in range(int(_KDETS)):
            b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            world_boards.append(b)
            m = NeuralMCTS(game=game, evaluator=evaluator, simulations=max_L,
                           c_puct=c_puct, seed=base + 100 + i)
            snaps, rp = snapshot_world_search(m, b, _LEVELS)
            if root_player is None:
                root_player = rp
            elif rp != root_player:
                raise AssertionError("root player differs across determinizations")
            world_snaps.append(snaps)
            m.clear()
        rec["root_player"] = int(root_player)

        # --- pool per level, read off both decision rules --------------------------
        per_level, qpick, vpick = {}, {}, {}
        for L in _LEVELS:
            agg_n: dict = defaultdict(float)
            agg_w: dict = defaultdict(float)
            for snaps in world_snaps:
                for a, (n, w) in snaps[L].items():
                    agg_n[a] += n
                    agg_w[a] += w
            vb = _pooled_visits_best(agg_n, agg_w)
            qa = pooled_q_argmax(agg_n, agg_w, _MINPV) if agg_n else None
            sumN = sum(agg_n.values())
            qs = sorted((agg_w[a] / agg_n[a] for a in agg_n if agg_n[a] > 0), reverse=True)
            qpick[L] = int(qa) if qa is not None else None
            vpick[L] = vb[0] if vb else None
            per_level[str(L)] = {
                "total_budget": int(_KDETS) * L,
                "q_argmax_action": qpick[L],            # DEPLOYED pick (primary)
                "played_action": vpick[L],              # visits rule (comparability only)
                "played_visit_share": (vb[1] / sumN if (vb and sumN) else 0.0),
                "pooled_top2_q_gap": (qs[0] - qs[1]) if len(qs) >= 2 else None,
                "sum_N": sumN,
                "n_children": len(agg_n),
            }
        rec["per_level"] = per_level
        rec["q_pick_by_level"] = {str(L): qpick[L] for L in _LEVELS}
        rec["v_pick_by_level"] = {str(L): vpick[L] for L in _LEVELS}
        rec["all_agree_q"] = bool(len(set(qpick.values())) == 1 and None not in qpick.values())

        # --- OPTIONAL PROOF 1: snapshot == standalone, WITHIN each world -----------
        if _VERIFY_BE:
            be = {}
            for L in _LEVELS:
                match = True
                for i, b in enumerate(world_boards):
                    g2, _b2 = RR.replay_actions(deck_seed, r["actions"], ply)
                    ag2 = CF.build_fair_champion(g2, sims=L, k_dets=int(_KDETS),
                                                 seed=rseed, cfg=_CFG)
                    m2 = NeuralMCTS(game=g2, evaluator=ag2._evaluator, simulations=L,
                                    c_puct=ag2._c_puct, seed=base + 100 + i)
                    m2.search(b)
                    rr = m2._nodes[g2.string_representation(b)]
                    ref = {a: n for a, (n, w) in read_children_nw(rr, rr.player_to_move).items()}
                    snapN = {a: n for a, (n, w) in world_snaps[i][L].items()}
                    match = match and (ref == snapN)
                    m2.clear()
                be[str(L)] = bool(match)
            rec["bit_exact_within_world"] = be
            rec["bit_exact_all"] = bool(all(be.values()))

        # --- OPTIONAL PROOF 2: the REAL deployed agent picks what we report --------
        if _VERIFY_PARITY:
            g3, b3 = RR.replay_actions(deck_seed, r["actions"], ply)
            ag3 = CF.build_fair_champion(g3, sims=max_L, k_dets=int(_KDETS),
                                         seed=rseed, cfg=_CFG)
            real = int(ag3._pimc_move(b3, 0))
            rec["agent_parity_action"] = real
            rec["agent_parity_ok"] = bool(real == qpick[max(_LEVELS)])

        rec["ok"] = True
    except TimeoutError:
        rec["error"] = "wall_hit"
        rec["ok"] = False
    except Exception as e:  # noqa - fail loud per root, never kill the pool
        import traceback
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-2000:]
        rec["ok"] = False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    rec["elapsed_secs"] = round(time.time() - t0, 3)
    return rec


def _claim_and_process(r: dict) -> dict | None:
    """Work-stealing across boxes: atomically claim on the SHARE, then compute.

    ⚠️ A killed run strands `.claim` files with no `.json`; a resume then stalls forever.
    Clean claims-without-records before resuming (see --clean-stale-claims)."""
    rid = _rid(r)
    out = Path(_OUT)
    jf, cf = out / f"{rid}.json", out / f"{rid}.claim"
    if jf.exists():
        return None
    try:
        fd = os.open(str(cf), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.uname().nodename}:{os.getpid()}:{time.time()}".encode())
        os.close(fd)
    except FileExistsError:
        return None
    rec = _process(r)
    tmp = out / f".{rid}.tmp"
    tmp.write_text(json.dumps(rec))
    tmp.replace(jf)
    return rec


def _init_worker(cfg, levels, k_dets, wall, verify_be, verify_parity, minpv, out):
    global _CFG, _LEVELS, _KDETS, _WALL, _VERIFY_BE, _VERIFY_PARITY, _MINPV, _OUT
    _CFG, _LEVELS, _KDETS = cfg, tuple(levels), int(k_dets)
    _WALL, _VERIFY_BE, _VERIFY_PARITY = wall, verify_be, verify_parity
    _MINPV, _OUT = int(minpv), str(out)


# --------------------------------------------------------------------------- #
def _load_roots(path: str) -> list:
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get("ok") is False:
            continue
        if "deck_seed" in d and d.get("actions") and "ply" in d:
            out.append(d)
    out.sort(key=lambda r: (int(r["deck_seed"]), int(r["ply"])))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Move-agreement-vs-budget probe (fair PIMC)")
    ap.add_argument("--roots", default=str(REPO / "measurement" / "classical_search" / "data"
                                           / "move_agreement_roots.jsonl"))
    ap.add_argument("--out-dir", required=True, help="SHARE dir (work-stealing across boxes)")
    ap.add_argument("--levels", default=",".join(str(x) for x in DEFAULT_LEVELS),
                    help="comma-separated PER-WORLD sim levels (ascending)")
    ap.add_argument("--k-dets", type=int, default=4)
    ap.add_argument("--replicates", type=int, default=3,
                    help="independent seed lineages per root (the NOISE FLOOR needs >=2)")
    ap.add_argument("--salt-base", type=int, default=1,
                    help="salts are salt-base .. salt-base+replicates-1; keep DISJOINT from "
                         "the sampler's --tag-salt")
    ap.add_argument("--n", type=int, default=0, help="limit to first N roots (0 = all)")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--wall-cap-secs", type=int, default=3600)
    ap.add_argument("--verify-bit-exact", action="store_true")
    ap.add_argument("--verify-agent-parity", action="store_true")
    ap.add_argument("--clean-stale-claims", action="store_true",
                    help="delete .claim files with no matching .json before starting")
    ap.add_argument("--tag", default="", help="free-text label recorded in the manifest")
    args = ap.parse_args(argv)

    levels = tuple(int(x) for x in args.levels.split(","))
    assert list(levels) == sorted(levels), "--levels must be ascending"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.clean_stale_claims:
        n = 0
        for cf in out_dir.glob("*.claim"):
            if not cf.with_suffix(".json").exists():
                cf.unlink()
                n += 1
        print(f"[agree] cleaned {n} stale claims", flush=True)

    from carcassonne_ai import fair_agent as _fa
    from carcassonne_ai import mcts as _mcts
    print(f"[agree] carcassonne_ai.fair_agent -> {_fa.__file__}", flush=True)
    print(f"[agree] carcassonne_ai.mcts       -> {_mcts.__file__}", flush=True)
    if os.environ.get("CARC_REQUIRE_SRC_ROOT"):
        want = os.environ["CARC_REQUIRE_SRC_ROOT"]
        for mod in (_fa, _mcts):
            assert mod.__file__.startswith(want), (
                f"ISOLATION FAILURE: {mod.__name__} -> {mod.__file__}, want prefix {want}")
        print(f"[agree] isolation VERIFIED against {want}", flush=True)

    roots = _load_roots(args.roots)
    if args.n > 0:
        roots = roots[:args.n]
    salts = list(range(args.salt_base, args.salt_base + args.replicates))
    # Interleave salts so a partial run still has >=2 salts on the roots it finished
    # (a floor needs pairs; salt-major order would leave every root with only salt 1).
    jobs = [dict(r, salt=s) for r in roots for s in salts]

    spec = CF.load_production_spec()
    cfg = CF.production_prior_cfg(spec)
    manifest_champ = CF.resolved_manifest("fair", spec, verify=True)
    from carcassonne_ai.fair_agent import DEFAULT_MIN_POOLED_VISITS as _MPV

    todo = [j for j in jobs if not (out_dir / f"{_rid(j)}.json").exists()]

    manifest = {
        "harness": "move_agreement_probe",
        "schema": "carcassonne-move-agreement/v1",
        "tag": args.tag,
        "goal": "separate GENUINE CONVERGENCE from INSTRUMENT COMPRESSION as the "
                "explanation for the flat top of the blind budget curve, by measuring "
                "whether the DEPLOYED fair-PIMC champion's selected move stops changing "
                "as budget grows — against its own same-budget reseed noise floor.",
        "levels_per_world": list(levels),
        "total_budgets": [args.k_dets * L for L in levels],
        "k_dets": args.k_dets,
        "replicates": args.replicates, "salts": salts,
        "salt_semantics": "independent agent-seed lineages; det_seed_base and per-world "
                          "search seeds depend only on (seed, move_idx), NOT on sims, so a "
                          "fixed salt draws the SAME worlds at every level (pure-depth "
                          "contrast) and distinct salts draw independent worlds (floor).",
        "decision_rule_primary": "q_argmax_action = pooled_q_argmax (THE DEPLOYED FAIR PICK)",
        "decision_rule_secondary": "played_action = argmax pooled visits (comparability only)",
        "min_pooled_visits": int(_MPV),
        "agent": "FairHeuristicPriorAgent via champion_factory.build_fair_champion",
        "snapshot_claim": "ONE deep search per world, snapshotted at every level; bit-exact "
                          "WITHIN a world only. NOT inherited from snapshot.py (which covers "
                          "the clairvoyant HeuristicMCTS path); re-established here and "
                          "proven by --verify-bit-exact / --verify-agent-parity.",
        "roots_source": args.roots,
        "n_roots": len(roots), "n_jobs": len(jobs), "n_todo": len(todo),
        "workers": args.workers, "wall_cap_secs": args.wall_cap_secs,
        "verify_bit_exact": bool(args.verify_bit_exact),
        "verify_agent_parity": bool(args.verify_agent_parity),
        "src_root": SRC_ROOT,
        "fair_agent_file": _fa.__file__, "mcts_file": _mcts.__file__,
        "code_rev": os.popen(f"git -C {REPO} rev-parse --short HEAD").read().strip(),
        "src_rev": os.popen(
            f"git -C {Path(SRC_ROOT).parent} rev-parse --short HEAD").read().strip(),
        "host": os.uname().nodename,
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "champion_manifest": manifest_champ,
    }
    mpath = out_dir / f"manifest_{os.uname().nodename}.json"
    mpath.write_text(json.dumps(manifest, indent=2))
    print(f"[agree] roots={len(roots)} salts={salts} jobs={len(jobs)} todo={len(todo)} "
          f"levels={levels} (totals {[args.k_dets*L for L in levels]}) "
          f"workers={args.workers}", flush=True)

    done = 0
    t0 = time.time()
    if todo:
        ctx = get_context("fork")
        with ctx.Pool(args.workers, initializer=_init_worker,
                      initargs=(cfg, levels, args.k_dets, args.wall_cap_secs,
                                args.verify_bit_exact, args.verify_agent_parity,
                                _MPV, str(out_dir))) as pool:
            for rec in pool.imap_unordered(_claim_and_process, todo, chunksize=1):
                if rec is None:
                    continue
                done += 1
                flag = "" if rec.get("ok") else f"  !! {rec.get('error')}"
                extra = ""
                if "bit_exact_all" in rec:
                    extra += f" BE={rec['bit_exact_all']}"
                if "agent_parity_ok" in rec:
                    extra += f" PARITY={rec['agent_parity_ok']}"
                rate = done / max(1e-9, time.time() - t0)
                print(f"  {rec['rid']:>26} {rec.get('elapsed_secs')}s "
                      f"agreeQ_all={rec.get('all_agree_q')}{extra} "
                      f"[{done}/{len(todo)} {rate*3600:.0f}/h]{flag}", flush=True)
    print(f"[agree] done={done} elapsed={time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
