#!/usr/bin/env python3
"""PRE-GATE census for the **phase-adaptive k schedule** lever (docs/LEVER_INDEX.md).

WHAT THIS DECIDES
-----------------
The lever ("adaptive-k") proposes varying the PIMC determinization width `k` by game
phase at a FIXED total budget (k x sims = 2752). Its pre-registered mechanism claim is:

  * k should track ACROSS-WORLD VALUE DISAGREEMENT, not branching factor;
  * late-but-pre-latch, the small remaining bag makes a fixed k=4 sample DUPLICATE deck
    orderings (pure waste — the same world searched twice — so depth would be free);
  * early-game across-world disagreement may be small (substitutable tiles).

The row pre-registers a PRE-GATE **before** any build: replay archived champion games
and census, by phase, (a) the across-world disagreement the champion's own k=4 draw
actually faces and (b) the duplicate-world rate. If disagreement is flat across phases
and duplication is negligible, the lever has no mechanism and dies free.

This script is that census. It is MEASUREMENT INFRASTRUCTURE, not a strength lever: it
never plays a game and never changes production.

WHAT IT MEASURES (per root, from ONE draw of the champion's 4 worlds)
---------------------------------------------------------------------
(a) ACROSS-WORLD DISAGREEMENT — from 4 per-world searches at the PRODUCTION per-world
    budget (`--sims`, default = PRODUCTION.yaml sims_per_det) with the production
    evaluator/config, i.e. the same searches the champion itself runs on that move:

      v_best[w]        world w's root-POV best-child Q (its own valuation of the move)
      v_std / v_range  spread of v_best across the 4 worlds        <- the "value spread"
      a_best[w]        world w's own pick (argmax visits, alias-deduped)
      n_distinct_argmax, argmax_all_agree                           <- decision-relevant
      pick_k2/k3/k4    the POOLED-Q pick using the first 2 / 3 / 4 worlds
      changed_k2_vs_k4 / changed_k3_vs_k4                           <- MARGINAL world value
      pooled_top2_gap  pooled-Q top-2 margin at k=4

    `changed_kX_vs_k4` is the quantity the lever actually needs: it is the rate at which
    the 3rd/4th world CHANGES the decision. A phase where it is ~0 is a phase where
    those worlds bought nothing.

(b) DUPLICATE-WORLD RATE — exact and free. `reshuffled_determinization` canonically
    sorts the unseen deck and shuffles it, so a world IS its deck-description ordering.
    Two worlds are identical iff those orderings are equal. Also reported at
    PREFIX depth N=1,2,3 (the engine draws with `deck.pop(0)`, so the first N entries
    are the next N tiles any search actually sees first).

    Duplicates are censused over `--dup-replicates` independent groups of 4 drawn from
    the SAME continuing seed lineage (group 0 is the searched group) — a low-variance
    estimate of the per-decision duplication probability at no search cost. The cheap
    groups shuffle a list of *descriptions* rather than deepcopying the board;
    `random.Random.shuffle` is content-independent (Fisher-Yates over indices), so a
    same-length shuffle consumes the identical rng stream and yields the identical
    permutation. `tests/test_adaptive_k_census.py` pins that equivalence.

PROXY / LIMITATION (read before quoting a number)
-------------------------------------------------
1. **Seed lineage, not the literal in-game draw.** The archived games
   (`champ_games.jsonl`) do not record the agent's per-game seed, so the champion's
   actual 4 worlds for a given ply are not reconstructible. We redraw 4 worlds with the
   champion's EXACT `reshuffled_determinization` semantics from a dedicated per-root
   seed lineage (`--salt`, disjoint from the CL-070 tag/probe salts). Because the
   canonicalized reshuffle makes a world a pure function of (unseen multiset, rng), the
   redraw is distributionally the champion's own draw — but it is not the identical
   sample, so per-root numbers are not "what happened", only the census is valid.
2. **Nested prefixes, not independent k-ensembles.** `pick_k2` pools worlds {0,1} of the
   SAME 4-draw. It measures the MARGINAL information of adding worlds 3-4, which is the
   lever's mechanism — it is NOT a k2-vs-k4 strength comparison (that is CL-054, already
   measured, z=1.33).
3. **No re-budgeting.** Sims/world is held FIXED at the production value. A real
   phase-varying k at fixed TOTAL budget would give each world proportionally MORE sims
   where k is smaller; this census does not simulate that deeper search. So it can show
   whether the disagreement SIGNAL varies by phase; it cannot price the trade.
4. Per-world searches are deterministic (`NeuralMCTS`'s rng is only consumed by
   `_reshuffled_root`/`sample_action`, neither of which runs on this path), so there is
   no search-noise floor to subtract: all observed spread is world-induced. Verified by
   `--noise-control`, which re-searches world 0 under a different seed and asserts an
   identical result.

USAGE
-----
    .venv/bin/python -u scripts/measurement_infra/adaptive_k_census.py \
        --roots /mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl \
        --out-dir /mnt/c/carc-shared/classical_search/adaptive_k_census \
        --workers 16
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to sample_agreement_roots.py / eval_fair_puct's
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
SRC_ROOT = os.environ.get("CARC_SRC_ROOT") or str(REPO / "src")
sys.path.insert(0, SRC_ROOT)
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import random  # noqa: E402
import time  # noqa: E402
import zlib  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402

import root_replay as RR  # noqa: E402

# Phase strata — VERBATIM the CL-070 root-bank cuts (sample_agreement_roots.PHASE_CUTS),
# so this census is directly joinable to the bank's own phase_bucket column.
PHASE_CUTS = {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}

# The fair exact-endgame latch band (fair_agent.EXACT_MAX_K): at or below this
# k_remaining the marginalized solver owns the decision and NO determinization is drawn,
# so these roots are outside any k schedule by construction.
LATCH_K = FA.EXACT_MAX_K

# Salt for THIS census's world lineage. Disjoint from the CL-070 tag salt (9000/9001)
# and from every move_agreement probe salt, so the redrawn worlds are independent of
# the picks recorded in the bank.
DEFAULT_SALT = 20260728


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested in tests/test_adaptive_k_census.py)                 #
# --------------------------------------------------------------------------- #
def phase_bucket(k_remaining: int) -> str:
    """Phase stratum from tiles-remaining. Same cuts as the CL-070 root bank."""
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k_remaining < hi:
            return name
    return "late"


def world_seed(deck_seed: int, ply: int, salt: int) -> int:
    """Per-root seed lineage. Same shape as sample_agreement_roots.tag_seed; the salt
    keeps it disjoint from the bank's tag/probe lineages."""
    return (int(deck_seed) * 1_000_003 + int(ply) * 8191
            + int(salt) * 2_654_435_761) & 0x7FFFFFFF


def canonical_deck_descriptions(deck) -> list:
    """The unseen deck as the canonically-SORTED description list that
    `FairHeuristicMCTSAgent.reshuffled_determinization` shuffles (audit hardening:
    sort-then-shuffle, so a world is a pure function of the multiset + rng)."""
    return sorted(t.description for t in deck)


def draw_world_signature(canon: list, rng: random.Random) -> tuple:
    """One world's deck ordering, drawn from `rng` EXACTLY as the agent draws it.

    `random.Random.shuffle` is Fisher-Yates over indices and never inspects the
    elements, so shuffling this description list consumes the identical rng stream and
    produces the identical permutation as shuffling the real Tile list of the same
    length. That equivalence is what lets the duplicate census run at zero search cost.
    """
    lst = list(canon)
    rng.shuffle(lst)
    return tuple(lst)


def duplicate_stats(sigs, prefixes=(1, 2, 3)) -> dict:
    """Duplicate/near-duplicate structure of one group of k world signatures.

    Returns n_distinct at full depth and at each prefix depth N (the next N tiles the
    search draws, since the engine pops from the FRONT of the deck), plus `dup_any`
    (2+ of the k worlds are identical) and `n_wasted` (worlds that are a repeat of an
    earlier one — the count that would be pure waste at fixed k).
    """
    sigs = [tuple(s) for s in sigs]
    k = len(sigs)
    out = {
        "k": k,
        "n_distinct_full": len(set(sigs)),
        "dup_any": len(set(sigs)) < k,
        "n_wasted_full": k - len(set(sigs)),
    }
    for n in prefixes:
        pre = {s[:n] for s in sigs}
        out[f"n_distinct_p{n}"] = len(pre)
        out[f"dup_any_p{n}"] = len(pre) < k
        out[f"n_wasted_p{n}"] = k - len(pre)
    return out


def dedup_root_children(root):
    """Deduped root-child (N, W-in-root-POV) maps for ONE world's tree.

    Identical convention to `fair_agent.pool_root_stats` (dedup by child object
    identity, lowest action index kept) so per-world stats and the pooled stats agree
    on the action space."""
    n: dict = {}
    w: dict = {}
    seen: set = set()
    for a in sorted(root.children):
        ch = root.children[a]
        if ch.N <= 0 or id(ch) in seen:
            continue
        seen.add(id(ch))
        sw = ch.W if ch.player_to_move == root.player_to_move else -ch.W
        n[int(a)] = float(ch.N)
        w[int(a)] = float(sw)
    return n, w


def pooled_pick(per_world, upto: int, min_visits: int = FA.DEFAULT_MIN_POOLED_VISITS):
    """The production pooled-Q pick over the FIRST `upto` worlds of `per_world`
    (a list of (n_map, w_map)). Returns (action, top2_q_gap or None)."""
    agg_n: dict = defaultdict(float)
    agg_w: dict = defaultdict(float)
    for n, w in per_world[:upto]:
        for a, v in n.items():
            agg_n[a] += v
            agg_w[a] += w[a]
    if not agg_n:
        return None, None
    action = FA.pooled_q_argmax(agg_n, agg_w, min_visits)
    qs = sorted((agg_w[a] / agg_n[a] for a in agg_n if agg_n[a] > 0), reverse=True)
    gap = float(qs[0] - qs[1]) if len(qs) >= 2 else None
    return int(action), gap


def stratified_sample(rows, n: int, seed: int, key="phase_bucket"):
    """Deterministic sample of `n` rows, proportionally stratified on `key`.

    Sorted-then-shuffled within stratum so the result depends only on (rows content,
    n, seed) — not on input order. Returns rows sorted by (deck_seed, ply)."""
    if n <= 0 or n >= len(rows):
        return sorted(rows, key=lambda r: (r["deck_seed"], r["ply"]))
    by: dict = defaultdict(list)
    for r in rows:
        by[r.get(key)].append(r)
    picked = []
    total = len(rows)
    for name in sorted(by, key=lambda x: str(x)):
        grp = sorted(by[name], key=lambda r: (r["deck_seed"], r["ply"]))
        # zlib.crc32, NOT hash(): builtin hash of a str is PYTHONHASHSEED-salted, so it
        # would make the "deterministic" sample differ between processes/runs.
        rng = random.Random(seed + zlib.crc32(str(name).encode()))
        rng.shuffle(grp)
        take = int(round(n * len(by[name]) / total))
        picked.extend(grp[:take])
    # rounding can over/undershoot: trim or top up deterministically
    if len(picked) > n:
        picked = picked[:n]
    elif len(picked) < n:
        chosen = {(r["deck_seed"], r["ply"]) for r in picked}
        rest = sorted((r for r in rows if (r["deck_seed"], r["ply"]) not in chosen),
                      key=lambda r: (r["deck_seed"], r["ply"]))
        random.Random(seed + 7).shuffle(rest)
        picked.extend(rest[: n - len(picked)])
    return sorted(picked, key=lambda r: (r["deck_seed"], r["ply"]))


# --------------------------------------------------------------------------- #
# Worker                                                                        #
# --------------------------------------------------------------------------- #
_CFG = None
_SIMS = None
_KDETS = None
_SALT = None
_REPS = None
_NOISE = False


def _init(cfg, sims, k_dets, salt, reps, noise):
    global _CFG, _SIMS, _KDETS, _SALT, _REPS, _NOISE
    _CFG, _SIMS, _KDETS, _SALT = cfg, int(sims), int(k_dets), int(salt)
    _REPS, _NOISE = int(reps), bool(noise)


def _census_root(r: dict) -> dict:
    out = {k: r[k] for k in ("deck_seed", "ply", "phase", "k_remaining", "n_legal",
                             "player_to_move") if k in r}
    for k in ("h200_top2_q_gap", "blind_top2_q_gap"):
        if k in r:
            out[k] = r[k]
    t0 = time.time()
    try:
        game, board = RR.replay_actions(int(r["deck_seed"]), r["actions"], int(r["ply"]))
        key = game.string_representation(board)
        if r.get("checksum") is not None and key != r["checksum"]:
            raise AssertionError("replay checksum mismatch — the roots bank does not "
                                 "reconstruct against this src tree")
        k_rem = int(FA.k_remaining(board.state))
        out["k_remaining"] = k_rem
        out["phase_bucket"] = phase_bucket(k_rem)
        out["deck_size"] = int(len(board.state.deck))
        out["latch_owned"] = bool(k_rem <= LATCH_K)
        legal = np.flatnonzero(game.get_valid_moves(board))
        out["n_legal"] = int(legal.size)

        agent = CF.build_fair_champion(game, sims=_SIMS, k_dets=_KDETS,
                                       seed=world_seed(r["deck_seed"], r["ply"], _SALT),
                                       cfg=_CFG)
        base = agent.det_seed_base(0)
        det_rng = random.Random(base + 1)      # the agent's own deck-reshuffle stream
        canon = canonical_deck_descriptions(board.state.deck)

        # --- group 0: the REAL worlds (deepcopied boards) — searched -------------
        worlds = []
        sigs0 = []
        for i in range(_KDETS):
            b = FA.FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            worlds.append(b)
            sigs0.append(tuple(t.description for t in b.state.deck))
        # --- groups 1..R-1: signature-only replicates on the SAME rng stream -----
        rep_groups = [sigs0]
        for _g in range(1, _REPS):
            rep_groups.append([draw_world_signature(canon, det_rng) for _ in range(_KDETS)])

        d0 = duplicate_stats(sigs0)
        out["dup"] = d0
        agg = {k: 0.0 for k in d0 if k != "k"}
        for g in rep_groups:
            dg = duplicate_stats(g)
            for k in agg:
                agg[k] += float(dg[k])
        out["dup_rep"] = {k: agg[k] / len(rep_groups) for k in agg}
        out["dup_replicates"] = len(rep_groups)

        # --- the 4 production-budget per-world searches --------------------------
        per_world = []
        v_best = []
        a_best = []
        for i, b in enumerate(worlds):
            m = NeuralMCTS(game=game, evaluator=agent._evaluator, simulations=_SIMS,
                           c_puct=agent._c_puct, seed=base + 100 + i)
            m.search(b)
            root = m._nodes.get(key) or m._nodes[game.string_representation(b)]
            n_map, w_map = dedup_root_children(root)
            per_world.append((n_map, w_map))
            if n_map:
                v_best.append(max(w_map[a] / n_map[a] for a in n_map))
                # production final_select = "visits"; (N, Q, -a) deterministic tiebreak
                a_best.append(int(max(n_map, key=lambda a: (n_map[a], w_map[a] / n_map[a], -a))))
            else:
                v_best.append(None)
                a_best.append(None)
            m.clear()

        if _NOISE and worlds:
            m = NeuralMCTS(game=game, evaluator=agent._evaluator, simulations=_SIMS,
                           c_puct=agent._c_puct, seed=base + 999)
            m.search(worlds[0])
            root = m._nodes.get(key) or m._nodes[game.string_representation(worlds[0])]
            n2, w2 = dedup_root_children(root)
            out["noise_control_identical"] = bool(n2 == per_world[0][0] and w2 == per_world[0][1])
            m.clear()

        vs = [v for v in v_best if v is not None]
        out["v_best"] = [None if v is None else round(float(v), 6) for v in v_best]
        out["v_mean"] = float(np.mean(vs)) if vs else None
        out["v_std"] = float(np.std(vs, ddof=1)) if len(vs) >= 2 else None
        out["v_range"] = float(max(vs) - min(vs)) if len(vs) >= 2 else None
        out["a_best"] = a_best
        good_a = [a for a in a_best if a is not None]
        out["n_distinct_argmax"] = len(set(good_a))
        out["argmax_all_agree"] = bool(len(set(good_a)) <= 1)

        picks = {}
        gaps = {}
        for kk in (1, 2, 3, _KDETS):
            if kk <= _KDETS:
                picks[kk], gaps[kk] = pooled_pick(per_world, kk)
        out["pick_by_k"] = {str(k): v for k, v in picks.items()}
        out["pooled_top2_gap"] = gaps.get(_KDETS)
        out["pooled_top2_gap_by_k"] = {str(k): v for k, v in gaps.items()}
        for kk in (1, 2, 3):
            if kk < _KDETS:
                out[f"changed_k{kk}_vs_k{_KDETS}"] = bool(picks[kk] != picks[_KDETS])
        out["ok"] = True
    except Exception as e:  # noqa: BLE001
        import traceback
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-1500:]
    out["secs"] = round(time.time() - t0, 3)
    return out


# --------------------------------------------------------------------------- #
# Aggregation                                                                   #
# --------------------------------------------------------------------------- #
def _wilson(k: int, n: int, z: float = 1.0):
    """Wilson interval half-width helper -> (p, lo, hi). z=1 => ~68%."""
    if n == 0:
        return None, None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def summarize(rows, k_dets: int) -> dict:
    ok = [r for r in rows if r.get("ok")]
    live = [r for r in ok if not r.get("latch_owned")]   # decisions a k schedule owns
    summ = {"n_rows": len(rows), "n_ok": len(ok), "n_latch_owned": len(ok) - len(live),
            "n_live": len(live)}

    def block(sub):
        if not sub:
            return {"n": 0}
        vstd = [r["v_std"] for r in sub if r.get("v_std") is not None]
        vrng = [r["v_range"] for r in sub if r.get("v_range") is not None]
        nda = [r["n_distinct_argmax"] for r in sub]
        dis = sum(1 for r in sub if not r["argmax_all_agree"])
        ch2 = sum(1 for r in sub if r.get(f"changed_k2_vs_k{k_dets}"))
        ch3 = sum(1 for r in sub if r.get(f"changed_k3_vs_k{k_dets}"))
        ch1 = sum(1 for r in sub if r.get(f"changed_k1_vs_k{k_dets}"))
        dup = sum(1 for r in sub if r["dup"]["dup_any"])
        dupr = float(np.mean([r["dup_rep"]["dup_any"] for r in sub]))
        wast = float(np.mean([r["dup_rep"]["n_wasted_full"] for r in sub]))
        pre = {f"dup_p{n}_rep": float(np.mean([r["dup_rep"][f"dup_any_p{n}"] for r in sub]))
               for n in (1, 2, 3)}
        gaps = [r["pooled_top2_gap"] for r in sub if r.get("pooled_top2_gap") is not None]
        d = {
            "n": len(sub),
            "k_remaining_median": float(np.median([r["k_remaining"] for r in sub])),
            "n_legal_median": float(np.median([r["n_legal"] for r in sub])),
            "v_std_mean": float(np.mean(vstd)) if vstd else None,
            "v_std_median": float(np.median(vstd)) if vstd else None,
            "v_range_median": float(np.median(vrng)) if vrng else None,
            "v_range_mean": float(np.mean(vrng)) if vrng else None,
            "n_distinct_argmax_mean": float(np.mean(nda)),
            "argmax_disagree_rate": dis / len(sub),
            "argmax_disagree_ci68": _wilson(dis, len(sub))[1:],
            "changed_k1_rate": ch1 / len(sub),
            "changed_k2_rate": ch2 / len(sub),
            "changed_k3_rate": ch3 / len(sub),
            "changed_k2_ci68": _wilson(ch2, len(sub))[1:],
            "changed_k3_ci68": _wilson(ch3, len(sub))[1:],
            "dup_any_rate_group0": dup / len(sub),
            "dup_any_rate_rep": dupr,
            "dup_wasted_worlds_mean_rep": wast,
            "pooled_top2_gap_median": float(np.median(gaps)) if gaps else None,
        }
        d.update(pre)
        return d

    summ["overall"] = block(live)
    summ["by_phase"] = {ph: block([r for r in live if r["phase_bucket"] == ph])
                        for ph in ("early", "mid", "late")}
    summ["by_game_phase"] = {gp: block([r for r in live if r["phase"] == gp])
                             for gp in ("TILES", "MEEPLES")}
    # finer late-game slicing: duplication is a function of the BAG SIZE, not the third
    bands = [(3, 6), (6, 10), (10, 16), (16, 24), (24, 36), (36, 48), (48, 100)]
    summ["by_k_band"] = {}
    for lo, hi in bands:
        sub = [r for r in live if lo <= r["k_remaining"] < hi]
        summ["by_k_band"][f"{lo}-{hi-1}"] = block(sub)
    summ["latch_band"] = block([r for r in ok if r.get("latch_owned")])
    nc = [r["noise_control_identical"] for r in ok if "noise_control_identical" in r]
    if nc:
        summ["noise_control_n"] = len(nc)
        summ["noise_control_all_identical"] = bool(all(nc))
    return summ


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--roots", default="/mnt/c/carc-shared/classical_search/"
                                       "move_agreement_k4_b28e9/roots.jsonl")
    ap.add_argument("--out-dir", default="/mnt/c/carc-shared/classical_search/adaptive_k_census")
    ap.add_argument("--n", type=int, default=0, help="0 = all roots; else stratified sample")
    ap.add_argument("--sample-seed", type=int, default=20260728)
    ap.add_argument("--sims", type=int, default=0, help="0 = PRODUCTION.yaml sims_per_det")
    ap.add_argument("--k-dets", type=int, default=0, help="0 = PRODUCTION.yaml k_dets")
    ap.add_argument("--salt", type=int, default=DEFAULT_SALT)
    ap.add_argument("--dup-replicates", type=int, default=8)
    ap.add_argument("--noise-control", action="store_true",
                    help="re-search world 0 under a different seed (determinism check)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--tag", default="")
    args = ap.parse_args(argv)

    spec = CF.load_production_spec()
    cfg = CF.production_prior_cfg(spec)
    sims = args.sims or spec.sims_per_det
    k_dets = args.k_dets or spec.k_dets

    rows = [json.loads(l) for l in Path(args.roots).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("ok", True)]
    print(f"[census] roots={len(rows)} from {args.roots}", flush=True)
    if args.n:
        rows = stratified_sample(rows, args.n, args.sample_seed)
        print(f"[census] stratified sample -> {len(rows)} "
              f"({Counter(r['phase_bucket'] for r in rows)})", flush=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.tag or "main"

    t0 = time.time()
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_init,
                  initargs=(cfg, sims, k_dets, args.salt, args.dup_replicates,
                            args.noise_control)) as pool:
        done = []
        for i, res in enumerate(pool.imap_unordered(_census_root, rows, chunksize=1), 1):
            done.append(res)
            if i % 50 == 0:
                print(f"[census] {i}/{len(rows)}  {time.time()-t0:.0f}s", flush=True)
    dt = time.time() - t0
    done.sort(key=lambda r: (r["deck_seed"], r["ply"]))
    bad = [r for r in done if not r.get("ok")]
    print(f"[census] {len(done)} roots in {dt:.0f}s ({len(bad)} failures)", flush=True)
    if bad:
        print(f"[census] first failure: {bad[0].get('error')}", flush=True)

    rows_path = out_dir / f"rows_{tag}.jsonl"
    with rows_path.open("w") as fh:
        for r in done:
            fh.write(json.dumps(r) + "\n")

    summ = summarize(done, k_dets)
    (out_dir / f"summary_{tag}.json").write_text(json.dumps(summ, indent=2))

    from carcassonne_ai import fair_agent as _fa
    manifest = {
        "kind": "adaptive_k_pregate_census",
        "lever": "phase-adaptive k schedule (docs/LEVER_INDEX.md)",
        "roots_source": args.roots,
        "n_roots_in_bank": None,
        "n_roots_censused": len(done),
        "n_failures": len(bad),
        "sample": {"n": args.n or "all", "sample_seed": args.sample_seed,
                   "stratified_on": "phase_bucket"},
        "world_draw": {
            "semantics": "fair_agent.FairHeuristicMCTSAgent.reshuffled_determinization "
                         "(canonical sort of the UNSEEN deck + rng.shuffle; next_tile untouched)",
            "seed_lineage": "world_seed(deck_seed, ply, salt) -> agent seed; "
                            "det_rng = Random(agent.det_seed_base(0)+1)",
            "salt": args.salt,
            "salt_note": "disjoint from the CL-070 tag salt (9000/9001) and probe salts",
            "limitation": "the archived games do not record the agent's per-game seed, so "
                          "these are a DISTRIBUTIONALLY equivalent redraw, not the literal "
                          "worlds the champion sampled in that game",
        },
        "search": {"sims_per_world": sims, "k_dets": k_dets,
                   "c_puct": spec.c_puct, "tau_p": spec.tau_p,
                   "note": "PRODUCTION per-world budget and evaluator — not a shallow proxy; "
                           "the proxy elements are the seed redraw, the NESTED k2/k3 prefixes, "
                           "and the absence of re-budgeting (sims/world held fixed)"},
        "duplicate_census": {"replicates": args.dup_replicates,
                             "prefix_depths": [1, 2, 3],
                             "note": "group 0 = the searched worlds; groups 1..R-1 are "
                                     "signature-only draws off the SAME rng stream "
                                     "(content-independent Fisher-Yates)"},
        "latch_band": {"exact_max_k": LATCH_K,
                       "note": "k_remaining<=K is owned by the marginalized solver — "
                               "no determinization is drawn there"},
        "phase_cuts_k_remaining": PHASE_CUTS,
        "env": _CANON_ENV,
        "src_root": SRC_ROOT,
        "fair_agent_file": _fa.__file__,
        "champion_id": spec.champion_id,
        "workers": args.workers,
        "wall_secs": round(dt, 1),
        "rows_file": str(rows_path),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / f"manifest_{tag}.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(summ["overall"], indent=2), flush=True)
    print(f"[census] wrote {rows_path} + summary_{tag}.json + manifest_{tag}.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
