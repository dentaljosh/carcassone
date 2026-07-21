#!/usr/bin/env python3
"""Gate B (FAIR-PIMC variant) — fixed-root DEPTH-TRANSFER replay of the DEPLOYED agent.

WHY THIS EXISTS
---------------
`gate_b_depth_transfer.py` (the record of the clairvoyant Gate-B result, 2026-07-21) runs the
CLAIRVOYANT champion core (``HeuristicPriorAgent``) — one deep search on the TRUE deck,
snapshotted at every shallower level. That is the only path that is both snapshot-exact and
cheap, but it is NOT what production plays. The DEPLOYED champion is fair PIMC
(``FairHeuristicPriorAgent``): k_dets reshuffled determinizations, a fresh tree per world, and
a POOLED aggregation across worlds — plus a marginalized K<=2 endgame solver on later plies.

Gate A (CL-059, 2026-07-19/20) showed the clairvoyant->fair change can INVERT a conclusion (a
+78.1/z3.87 clairvoyant oracle-prior screen collapsed to -3.7/z-0.20 under fair PIMC). So a
clairvoyant-only depth-transfer verdict needs a fair replication before it can be believed.
This harness IS that replication: the SAME roots, the SAME depth levels, the SAME metrics, but
each level's root statistics come from the fair PIMC ensemble instead of a single clairvoyant
tree.

WHAT IT DOES (per root, per depth level L)
------------------------------------------
Mirrors ``FairHeuristicPriorAgent._pimc_move`` EXACTLY for a single (root) decision:
  base    = agent.det_seed_base(0)                      # move_idx 0 — a fixed-root probe
  det_rng = random.Random(base + 1)                     # ONE rng, k_dets sequential shuffles
  world i: b_i = reshuffled_determinization(board, det_rng)      # canonical-sort + shuffle
           NeuralMCTS(game, evaluator, sims=max(levels), c_puct, seed=base+100+i).search(b_i)
then pools the deduped root children into (N, W_rootpov) accumulators — ``pool_root_stats``'s
rule, reimplemented here only so it can read a SNAPSHOT instead of a finished tree.

SNAPSHOTTING — WHAT IS AND IS NOT BIT-EXACT
-------------------------------------------
Bit-exactness holds WITHIN a world, not across worlds. Each world's search is an ordinary
serial (batch_size=1, fair_chance=False) ``NeuralMCTS`` on its own fixed reshuffled board with
its own fixed seed — i.e. structurally identical to the clairvoyant snapshot path, just on a
different deck. So the first L sims of that world's max(levels)-sim search ARE bit-exact to a
standalone ``NeuralMCTS(simulations=L, seed=base+100+i).search(b_i)``. We therefore run ONE
deep search PER WORLD and snapshot it at every level (k_dets searches total, not
k_dets x n_levels), then POOL AT EACH LEVEL.

What this does NOT claim: that the k4 worlds themselves are shared across levels in any deeper
sense than "the same k4 reshuffled decks" — they are, by construction (one det_rng stream,
drawn once), which is the right comparison: it isolates DEPTH, holding the sampled worlds fixed.
A production agent at sims=200 would draw the SAME k4 worlds (the rng stream depends only on
the seed and move index, not on the sim budget), so this is production-faithful.
``--verify-bit-exact`` PROVES the within-world claim per run (standalone re-searches at every
level, per world, asserted equal); do not trust the claim without it.

TWO DECISION RULES ARE RECORDED (they differ in fair mode — this matters)
-------------------------------------------------------------------------
  * ``played_action``    = argmax POOLED VISITS. This is NOT the deployed fair rule; it is the
                           direct analogue of the clairvoyant harness's ``played_action``
                           (final_select="visits"), recorded so the two runs are comparable
                           metric-for-metric.
  * ``q_argmax_action``  = ``pooled_q_argmax`` (pooled Q = sum W / sum N, min_pooled_visits
                           floor, (Q,N,-a) tiebreak). This IS the DEPLOYED fair pick.
Every level therefore carries BOTH families, and SUMMARY.json reports both
(``*_by_level`` = the visits rule for comparability; ``*_q_by_level`` = the deployed rule).

ENDGAME SOLVER: the k3 root suite sits at k_remaining=3, ABOVE the fair agent's K<=2
marginalized handoff band, so the solver never fires on these roots — the fair decision under
test is pure PIMC. ``exact_latch`` is recorded per root so this is checked, not assumed.

ROOTS / RESUME / MANIFEST: identical conventions to gate_b_depth_transfer.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to gate_b_depth_transfer.py / eval_fair_puct's
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
sys.path.insert(0, str(REPO / "src"))
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
import gen_endgame_positions as GEP  # noqa: E402  (replay_to)

DEFAULT_LEVELS = (200, 344, 688)   # per-WORLD sim budgets; champion band k4x688 (CL-054)

# per-worker globals (fork-inherited; set in _init_worker)
_CFG = None
_LEVELS = None
_KDETS = None
_WALL = None
_VERIFY = None
_MINPV = None


# --------------------------------------------------------------------------- #
# Snapshot of ONE world's search (bit-exact within the world)                   #
# --------------------------------------------------------------------------- #
def read_children_nw(root, root_player) -> dict:
    """Deduped visited children -> {action: (N, W_rootpov)}.

    Same dedup + sign convention as ``fair_agent.pool_root_stats`` (which pools W, not Q)
    and ``snapshot.read_children`` (which returns Q). We need W to pool correctly across
    worlds, so this returns W; Q is recovered as W/N after pooling."""
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
    """Mirror ``NeuralMCTS.search``'s serial clairvoyant-on-this-world setup, then step
    max(levels) PUCT sims, snapshotting deduped root child (N, W_rootpov) at each level.

    Bit-exact to a standalone ``NeuralMCTS(simulations=L, seed=same).search(board)`` for
    every L (--verify-bit-exact proves it per run). `m` must be freshly constructed."""
    assert m.batch_size == 1, "snapshot path is serial (batch_size=1) only"
    assert not m.fair_chance, ("snapshot path expects fair_chance=False — the fair regime "
                               "comes from the RESHUFFLED BOARD, not from in-search chance "
                               "sampling (that is how FairHeuristicPriorAgent works)")
    assert m._root_prior_override is None, "no root-prior override in the Gate-B fair probe"
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
    root_priors = {int(a): float(p) for a, p in root.priors.items()}
    snaps = {}
    idx = 0
    for i in range(1, levels[-1] + 1):
        m._simulate(board, root)
        if idx < len(levels) and i == levels[idx]:
            snaps[levels[idx]] = read_children_nw(root, root_player)
            idx += 1
    return snaps, root_player, root_priors, float(root.leaf_value)


# --------------------------------------------------------------------------- #
# Pooled decision rules                                                         #
# --------------------------------------------------------------------------- #
def _pooled_visits_best(agg_n: dict, agg_w: dict):
    """(action, N, Q_rootpov) with max POOLED visits; ties -> lowest action id. The
    clairvoyant harness's final_select='visits' rule, lifted to the PIMC ensemble."""
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
# Per-root worker                                                               #
# --------------------------------------------------------------------------- #
def _root_seed(seed: int, ply: int) -> int:
    """IDENTICAL to gate_b_depth_transfer._root_seed, so the fair run's agent seed for a
    given root matches the clairvoyant run's (same root -> same seed lineage)."""
    return (int(seed) * 1_000_003 + int(ply)) & 0x7fffffff


def _build_agent(game, sims, seed):
    """The DEPLOYED fair champion, constructed through champion_factory (no hand-rolled
    config): PRODUCTION.yaml knobs + curve125 leaf + exact_max_k from the spec."""
    return CF.build_fair_champion(game, sims=int(sims), k_dets=int(_KDETS),
                                  seed=int(seed), cfg=_CFG)


def _process_root(r: dict) -> dict:
    seed, ply = _root_ids(r)
    root_id = f"s{seed}_p{ply}"
    rec = {"root_id": root_id, "seed": seed, "ply": ply,
           "k_remaining": int(r.get("k_remaining", -1)),
           "source_agent": r.get("source_agent"),
           "levels": list(_LEVELS), "k_dets": int(_KDETS), "info_mode": "fair_pimc"}
    t0 = time.time()

    def _on_alarm(signum, frame):
        raise TimeoutError("per-root wall cap")
    old = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(int(_WALL))
    try:
        game, board = _reconstruct(r)
        cksum = game.string_representation(board)
        rec["checksum_ok"] = bool(cksum == r.get("checksum"))
        if not rec["checksum_ok"]:
            rec["error"] = "checksum_mismatch"
            rec["ok"] = False
            return rec
        rseed = _root_seed(seed, ply)
        rec["mcts_seed"] = rseed
        max_L = max(_LEVELS)
        agent = _build_agent(game, max_L, rseed)

        # Would the DEPLOYED agent hand this root to the marginalized solver instead of
        # PIMC? (k3 suite: never. Recorded, not assumed.)
        k_rem = fair_k_remaining(board.state)
        rec["k_remaining_runtime"] = int(k_rem)
        rec["exact_latch"] = bool(agent._exact_endgame
                                  and board.state.phase == GamePhase.TILES
                                  and k_rem <= agent._exact_max_k)
        rec["exact_max_k"] = int(agent._exact_max_k)

        base = agent.det_seed_base(0)          # fixed-root probe -> move_idx 0
        rec["det_seed_base"] = int(base)
        det_rng = random.Random(base + 1)      # ONE stream, k_dets sequential shuffles
        evaluator = agent._evaluator
        c_puct = agent._c_puct

        world_snaps = []
        world_priors = []
        world_boards = []
        root_player = None
        for i in range(_KDETS):
            b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            world_boards.append(b)
            m = NeuralMCTS(game=game, evaluator=evaluator, simulations=max_L,
                           c_puct=c_puct, seed=base + 100 + i)
            snaps, rp, priors, _lv = snapshot_world_search(m, b, _LEVELS)
            if root_player is None:
                root_player = rp
            elif rp != root_player:
                raise AssertionError("root player differs across determinizations")
            world_snaps.append(snaps)
            world_priors.append(priors)
            m.clear()
        rec["root_player"] = int(root_player)

        # --- prior-favored action. The heuristic prior is a function of the BOARD (the
        # softmax of per-child Delta-leaf), so it should be identical across worlds; we
        # verify rather than assume, and use the world-mean if it ever is not.
        rec["prior_worlds_identical"] = bool(
            all(wp == world_priors[0] for wp in world_priors[1:]))
        acts = sorted(set().union(*[set(wp) for wp in world_priors])) if world_priors else []
        mean_prior = {a: float(np.mean([wp.get(a, 0.0) for wp in world_priors]))
                      for a in acts}
        if mean_prior:
            pf = min(mean_prior, key=lambda a: (-mean_prior[a], a))
            rec["prior_favored"] = int(pf)
            rec["prior_favored_p"] = float(mean_prior[pf])
            ps = np.array([mean_prior[a] for a in acts], dtype=float)
            s = ps.sum()
            if s > 0:
                ps = ps / s
                rec["prior_entropy"] = float(-(ps * np.log(ps + 1e-12)).sum())
            rec["n_legal"] = int(len(mean_prior))
        else:
            rec["prior_favored"] = None

        # --- pool per level, then read off both decision rules --------------------
        per_level = {}
        played_by_level = {}
        qpick_by_level = {}
        for L in _LEVELS:
            agg_n: dict[int, float] = defaultdict(float)
            agg_w: dict[int, float] = defaultdict(float)
            n_worlds_visiting: dict[int, int] = defaultdict(int)
            for snaps in world_snaps:
                for a, (n, w) in snaps[L].items():
                    agg_n[a] += n
                    agg_w[a] += w
                    n_worlds_visiting[a] += 1
            vb = _pooled_visits_best(agg_n, agg_w)                       # comparability rule
            qa = pooled_q_argmax(agg_n, agg_w, _MINPV) if agg_n else None  # DEPLOYED rule
            sumN = sum(agg_n.values())
            top = sorted(((int(a), agg_n[a], agg_w[a] / agg_n[a]) for a in agg_n if agg_n[a] > 0),
                         key=lambda t: (-t[1], t[0]))[:3]
            top3 = [{"action": a, "N": n, "visit_share": (n / sumN if sumN else 0.0), "Q": q,
                     "n_worlds": int(n_worlds_visiting[a])}
                    for a, n, q in top]
            qs_all = sorted((agg_w[a] / agg_n[a] for a in agg_n if agg_n[a] > 0), reverse=True)
            q_gap = (qs_all[0] - qs_all[1]) if len(qs_all) >= 2 else None
            qs_elig = sorted((agg_w[a] / agg_n[a] for a in agg_n if agg_n[a] >= _MINPV),
                             reverse=True)
            q_gap_elig = (qs_elig[0] - qs_elig[1]) if len(qs_elig) >= 2 else None
            played = vb[0] if vb else None
            played_by_level[L] = played
            qpick_by_level[L] = (int(qa) if qa is not None else None)
            pf = rec.get("prior_favored")
            per_level[str(L)] = {
                "played_action": played,                       # pooled-VISITS argmax
                "played_N": (vb[1] if vb else 0),
                "played_visit_share": (vb[1] / sumN if (vb and sumN) else 0.0),
                "played_Q": (vb[2] if vb else None),
                "q_argmax_action": qpick_by_level[L],          # pooled-Q = DEPLOYED pick
                "played_eq_q_argmax": bool(vb and qa is not None and vb[0] == qa),
                "played_eq_prior_favored": bool(vb and pf is not None and vb[0] == pf),
                "q_argmax_eq_prior_favored": bool(qa is not None and pf is not None
                                                  and int(qa) == pf),
                "top2_q_gap": q_gap,
                "top2_q_gap_eligible": q_gap_elig,
                "sum_N": sumN,
                "n_children": len(agg_n),
                "n_children_eligible": int(sum(1 for a in agg_n if agg_n[a] >= _MINPV)),
                "top3": top3,
            }
        rec["per_level"] = per_level

        Ls = list(_LEVELS)
        pairs, pairs_q = {}, {}
        for i in range(len(Ls)):
            for j in range(i + 1, len(Ls)):
                a, b_ = Ls[i], Ls[j]
                pairs[f"{a}v{b_}"] = bool(played_by_level[a] is not None
                                          and played_by_level[a] == played_by_level[b_])
                pairs_q[f"{a}v{b_}"] = bool(qpick_by_level[a] is not None
                                            and qpick_by_level[a] == qpick_by_level[b_])
        rec["agreement"] = {
            "played_by_level": {str(L): played_by_level[L] for L in Ls},
            "q_pick_by_level": {str(L): qpick_by_level[L] for L in Ls},
            "pairwise": pairs,
            "pairwise_q": pairs_q,
            "all_agree": bool(len(set(played_by_level.values())) == 1
                              and None not in played_by_level.values()),
            "all_agree_q": bool(len(set(qpick_by_level.values())) == 1
                                and None not in qpick_by_level.values()),
            "shallowest_vs_deepest": pairs.get(f"{Ls[0]}v{Ls[-1]}"),
            "shallowest_vs_deepest_q": pairs_q.get(f"{Ls[0]}v{Ls[-1]}"),
        }

        if _VERIFY:
            # WITHIN-WORLD bit-exactness: re-run each world standalone at each level and
            # assert the visit vectors match the snapshot. Uses the SAME reshuffled boards
            # (world_boards) so only the sim budget differs.
            be = {}
            for L in _LEVELS:
                match = True
                for i, b in enumerate(world_boards):
                    g2, _b2 = _reconstruct(r)
                    ag2 = _build_agent(g2, L, rseed)
                    m2 = NeuralMCTS(game=g2, evaluator=ag2._evaluator, simulations=L,
                                    c_puct=ag2._c_puct, seed=base + 100 + i)
                    m2.search(b)
                    rr = m2._nodes[g2.string_representation(b)]
                    ref = {a: n for a, (n, w) in read_children_nw(rr, rr.player_to_move).items()}
                    snapN = {a: n for a, (n, w) in world_snaps[i][L].items()}
                    match = match and (ref == snapN)
                    m2.clear()
                be[str(L)] = {"match": bool(match)}
            rec["bit_exact_within_world"] = be
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


def _init_worker(cfg, levels, k_dets, wall, verify, minpv):
    global _CFG, _LEVELS, _KDETS, _WALL, _VERIFY, _MINPV
    _CFG, _LEVELS, _KDETS = cfg, tuple(levels), int(k_dets)
    _WALL, _VERIFY, _MINPV = wall, verify, int(minpv)


# --------------------------------------------------------------------------- #
def _root_ids(r: dict) -> tuple[int, int]:
    """(seed, ply) for a root record. GREEDY roots carry `seed`; CHAMPION action-log roots
    (mine_roots.py --source champion) carry `deck_seed` + the full `actions` sequence."""
    return int(r.get("seed", r.get("deck_seed"))), int(r["ply"])


def _reconstruct(r: dict):
    """Rebuild (game, board) for a root record — SOURCE-AGNOSTIC (2026-07-21).

    * greedy roots   -> gen_endgame_positions.replay_to(seed, ply)
    * champion roots -> root_replay.replay_actions(deck_seed, actions, ply) — the lossless
      (deck_seed, action_sequence) contract, so roots mined from the CHAMPION'S OWN play
      distribution work here without the greedy proxy. Checksum-verified by the caller.
    """
    if r.get("actions"):
        import root_replay as RR
        return RR.replay_actions(int(r["deck_seed"]), r["actions"], int(r["ply"]))
    return GEP.replay_to(int(r["seed"]), int(r["ply"]))


def _load_roots(path: str) -> list:
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if "ply" not in d:
            continue
        # greedy (seed+ply) OR champion action-log (deck_seed+actions+ply) roots
        if "seed" in d or ("deck_seed" in d and d.get("actions")):
            out.append(d)
    out.sort(key=lambda r: (int(r.get("k_remaining", 0)), *_root_ids(r)))
    return out


def _subset(roots: list, n: int, seed: int) -> list:
    """PRE-REGISTERED random subset (state n + seed BEFORE looking at results). Keeps the
    canonical sort order so records/resume are stable."""
    rng = random.Random(int(seed))
    idx = sorted(rng.sample(range(len(roots)), min(int(n), len(roots))))
    return [roots[i] for i in idx]


def _summary(records: list) -> dict:
    ok = [r for r in records if r.get("ok")]
    Ls = ok[0]["levels"] if ok else list(DEFAULT_LEVELS)
    n = len(ok)
    s = {"n_records": len(records), "n_ok": n, "levels": Ls,
         "k_dets": (ok[0].get("k_dets") if ok else None),
         "regime": "fair_pimc"}
    if not n:
        return s
    L0, Ld = Ls[0], Ls[-1]
    s["agree_shallowest_vs_deepest"] = round(
        sum(1 for r in ok if r["agreement"]["pairwise"].get(f"{L0}v{Ld}")) / n, 4)
    s["agree_shallowest_vs_deepest_q"] = round(
        sum(1 for r in ok if r["agreement"]["pairwise_q"].get(f"{L0}v{Ld}")) / n, 4)
    s["all_agree_frac"] = round(sum(1 for r in ok if r["agreement"]["all_agree"]) / n, 4)
    s["all_agree_frac_q"] = round(sum(1 for r in ok if r["agreement"]["all_agree_q"]) / n, 4)
    for key in ("prior_survival_by_level", "prior_survival_q_by_level",
                "played_eq_q_argmax_by_level", "mean_top2_q_gap_by_level",
                "mean_top2_q_gap_eligible_by_level", "mean_played_visit_share_by_level"):
        s[key] = {}
    for L in Ls:
        k = str(L)
        s["prior_survival_by_level"][k] = round(
            sum(1 for r in ok if r["per_level"][k]["played_eq_prior_favored"]) / n, 4)
        s["prior_survival_q_by_level"][k] = round(
            sum(1 for r in ok if r["per_level"][k]["q_argmax_eq_prior_favored"]) / n, 4)
        s["played_eq_q_argmax_by_level"][k] = round(
            sum(1 for r in ok if r["per_level"][k]["played_eq_q_argmax"]) / n, 4)
        for field, out_key in (("top2_q_gap", "mean_top2_q_gap_by_level"),
                               ("top2_q_gap_eligible", "mean_top2_q_gap_eligible_by_level")):
            gaps = [r["per_level"][k][field] for r in ok if r["per_level"][k][field] is not None]
            s[out_key][k] = round(float(np.mean(gaps)), 5) if gaps else None
        shares = [r["per_level"][k]["played_visit_share"] for r in ok]
        s["mean_played_visit_share_by_level"][k] = round(float(np.mean(shares)), 5)
    s["n_exact_latch"] = int(sum(1 for r in ok if r.get("exact_latch")))
    s["prior_worlds_identical_frac"] = round(
        sum(1 for r in ok if r.get("prior_worlds_identical")) / n, 4)
    if any("bit_exact_within_world" in r for r in ok):
        s["bit_exact_within_world_all_match"] = all(
            all(v["match"] for v in r.get("bit_exact_within_world", {}).values())
            for r in ok if "bit_exact_within_world" in r)
        s["n_bit_exact_checked"] = int(sum(1 for r in ok if "bit_exact_within_world" in r))
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Gate B FAIR-PIMC fixed-root depth-transfer replay (deployed agent)")
    ap.add_argument("--roots", default=str(
        REPO / "measurement" / "f3_public_state_oracle" / "roots_k3_suite.jsonl"))
    ap.add_argument("--out-dir", default=str(
        REPO / "measurement" / "gate_b_fair_pimc" / "records"))
    ap.add_argument("--levels", default="200,344,688",
                    help="comma-separated PER-WORLD sim depth levels (ascending)")
    ap.add_argument("--k-dets", type=int, default=0,
                    help="PIMC determinizations per decision (0 = PRODUCTION.yaml k_dets)")
    ap.add_argument("--n", type=int, default=0, help="limit to first N roots (0 = all)")
    ap.add_argument("--subset-n", type=int, default=0,
                    help="PRE-REGISTERED random subset size (0 = all roots)")
    ap.add_argument("--subset-seed", type=int, default=20260721,
                    help="seed for --subset-n (declare it BEFORE running)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--wall-cap-secs", type=int, default=900, help="per-root SIGALRM cap")
    ap.add_argument("--verify-bit-exact", action="store_true",
                    help="also re-run each world standalone per level; assert snapshot==standalone")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    args = ap.parse_args(argv)

    levels = tuple(int(x) for x in args.levels.split(","))
    assert list(levels) == sorted(levels), "--levels must be ascending"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = CF.load_production_spec()
    k_dets = int(args.k_dets) if args.k_dets > 0 else int(spec.k_dets)

    roots = _load_roots(args.roots)
    n_total_available = len(roots)
    subset_note = None
    if args.subset_n > 0 and args.subset_n < len(roots):
        roots = _subset(roots, args.subset_n, args.subset_seed)
        subset_note = {"kind": "pre-registered uniform random subset without replacement",
                       "n": len(roots), "seed": int(args.subset_seed),
                       "population": n_total_available,
                       "note": "chosen from the canonical-sorted root list BEFORE any result "
                               "was inspected; the complement is simply not run (logged in "
                               "dropped_root_ids)."}
    if args.n > 0:
        roots = roots[:args.n]

    # Build + VERIFY the production champion leaf (F1 runtime guard; raises on drift).
    cfg = CF.production_prior_cfg(spec)
    manifest_champ = CF.resolved_manifest("fair", spec, verify=True)

    todo, skipped = [], 0
    for r in roots:
        rid = ("s%d_p%d" % _root_ids(r))
        if args.resume and (out_dir / f"{rid}.json").exists():
            skipped += 1
            continue
        todo.append(r)

    kept_ids = {("s%d_p%d" % _root_ids(r)) for r in roots}
    all_ids = [("s%d_p%d" % _root_ids(r)) for r in _load_roots(args.roots)]
    dropped = [i for i in all_ids if i not in kept_ids]

    manifest = {
        "harness": "gate_b_fair_pimc",
        "schema": "carcassonne-gate-b/v1-fair",
        "sibling": "scripts/measurement_infra/gate_b_depth_transfer.py (clairvoyant record)",
        "goal": "fixed-root depth-transfer replay of the DEPLOYED fair-PIMC champion — does "
                "the prior/selection channel's influence decay with depth in the FAIR regime "
                "(the clairvoyant Gate-B replication demanded by CL-059)",
        "levels": list(levels),
        "level_semantics": "PER-WORLD PUCT sim budgets; total = k_dets x level. Champion band "
                           f"k{k_dets}x688 (CL-054). ONE deep search per world, snapshotted "
                           "at every level (bit-exact WITHIN a world), pooled at each level.",
        "info_mode": "fair_pimc",
        "agent": "FairHeuristicPriorAgent via champion_factory.build_fair_champion "
                 "(root-determinization PIMC, canonical-sorted reshuffle, fresh tree per "
                 "world, pooled aggregation; curve125 v2.9 Bmild_cap8 leaf)",
        "k_dets": k_dets,
        "min_pooled_visits": int(__import__("carcassonne_ai.fair_agent", fromlist=["x"])
                                 .DEFAULT_MIN_POOLED_VISITS),
        "decision_rules": {
            "played_action": "argmax POOLED VISITS — the clairvoyant harness's rule, recorded "
                             "for metric-for-metric comparability (NOT the deployed fair rule)",
            "q_argmax_action": "pooled_q_argmax (pooled Q, min_pooled_visits floor, (Q,N,-a) "
                               "tiebreak) — THE DEPLOYED fair pick",
        },
        "determinization_rng": "random.Random(det_seed_base(0)+1), k_dets sequential shuffles "
                               "— production-identical; per-world search seed = base+100+i. "
                               "Fixed per (root, world index).",
        "endgame_solver": f"fair marginalized K<={spec.exact_max_k} handoff; the k3 root suite "
                          "is at k_remaining=3 so it NEVER fires here (per-root exact_latch "
                          "records this).",
        "roots_source": str(args.roots),
        "n_roots_population": n_total_available,
        "n_roots_selected": len(roots),
        "subset": subset_note,
        "dropped_root_ids": dropped,
        "n_todo": len(todo),
        "n_skipped_resume": skipped,
        "wall_cap_secs": args.wall_cap_secs,
        "workers": args.workers,
        "verify_bit_exact": bool(args.verify_bit_exact),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "champion_manifest": manifest_champ,
    }
    (out_dir.parent / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[gate_b_fair] roots={len(roots)}/{n_total_available} todo={len(todo)} "
          f"skipped(resume)={skipped} levels={levels} k_dets={k_dets} "
          f"workers={args.workers} verify={args.verify_bit_exact}", flush=True)

    from carcassonne_ai.fair_agent import DEFAULT_MIN_POOLED_VISITS as _MPV

    records = []
    if args.resume:
        for r in roots:
            rid = ("s%d_p%d" % _root_ids(r))
            fp = out_dir / f"{rid}.json"
            if fp.exists() and r not in todo:
                try:
                    records.append(json.loads(fp.read_text()))
                except Exception:
                    pass

    if todo:
        ctx = get_context("fork")
        with ctx.Pool(args.workers, initializer=_init_worker,
                      initargs=(cfg, levels, k_dets, args.wall_cap_secs,
                                args.verify_bit_exact, _MPV)) as pool:
            for rec in pool.imap_unordered(_process_root, todo, chunksize=1):
                (out_dir / f"{rec['root_id']}.json").write_text(json.dumps(rec))
                records.append(rec)
                flag = "" if rec.get("ok") else f"  !! {rec.get('error')}"
                print(f"  {rec['root_id']:>20}  {rec.get('elapsed_secs')}s"
                      f"  agree(sh/deep)={rec.get('agreement', {}).get('shallowest_vs_deepest')}"
                      f"  agreeQ={rec.get('agreement', {}).get('shallowest_vs_deepest_q')}"
                      f"{flag}", flush=True)

    summary = _summary(records)
    # SUMMARY belongs BESIDE the records: out_dir.parent only when out_dir is the
    # conventional records/ subdir, else out_dir itself. The unconditional .parent
    # meant a TOP-LEVEL --out-dir wrote the summary into the parent tree (e.g.
    # measurement/SUMMARY.json), where two concurrent runs silently clobbered each
    # other and each run's own dir was left with no canonical artifact (2026-07-21).
    summary_dir = out_dir.parent if out_dir.name == "records" else out_dir
    (summary_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print("[gate_b_fair] SUMMARY:", json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
