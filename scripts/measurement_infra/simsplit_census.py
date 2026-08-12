#!/usr/bin/env python3
"""PRE-GATE census for the **phase-asymmetric sims split** lever (docs/LEVER_INDEX.md).

WHAT THIS DECIDES
-----------------
Each champion turn runs TWO full fair searches at the SAME budget (k8 x 1376/world):
the tile-placement decision (~17-30 legal actions) and the meeple decision (~3-4
legal actions, measured ~58% of turn time). The lever proposes a per-phase sims
budget (sims_tile / sims_meeple) at fixed total. Its mechanism claim is:

  * the meeple search's pick may SATURATE at a fraction of the production budget
    (its pooled pick already stable at low sims -> budget partly wasted there);
  * the tile search may still be below saturation (its pick still moving with sims),
    so reclaimed meeple sims would buy real tile-decision changes.

This script is that census. It is MEASUREMENT INFRASTRUCTURE, not a strength lever:
it never plays a game, consumes no deck band, and never changes production.

WHAT IT MEASURES (per root, from ONE draw of the champion's k worlds)
---------------------------------------------------------------------
For each replayed root (checksum-verified against the CL-070 bank), draw the
champion's k_dets worlds ONCE (production `reshuffled_determinization` semantics,
dedicated salt), then search EVERY world at each sims rung of the ladder
{ref/8, ref/4, ref/2, ref} (default {172, 344, 688, 1376}) — the SAME worlds at
every rung (CRN by construction: only sims differs; per-world seeds identical).

Per root per rung:
  pick[s]             the production pooled-Q pick over all k worlds at sims=s
  gap[s]              pooled top-2 Q gap at sims=s
  a_best[s]           each world's own pick (argmax visits, alias-deduped)

Primary statistic:  PICK-FLIP RATE vs the reference rung —
  flip[s] = (pick[s] != pick[ref]),  split by DECISION TYPE (TILES vs MEEPLES).
Secondary:          flip rate as a function of the reference-rung top-2 gap
  (fixed pre-registered gap bins), plus each world's own-pick flip fraction.

CONFOUND, stated up front: meeple decisions have ~4 legal actions vs ~28 for
tiles, so their BASE flip probability is mechanically lower. The gate (see
PREREG.md) therefore reads the meeple-saturation half as an ABSOLUTE operational
quantity (flip rate = the fraction of decisions a budget cut would change) and
demotes any tile-vs-meeple COMPARATIVE claim to gap-matched strata; this summary
always reports flip rates alongside n_legal so the readout can't be fooled.

LATCH EXCLUSION (turn-atomic, NOT the blanket k<=2 of the adaptive-k census)
----------------------------------------------------------------------------
`FairHeuristicPriorAgent` latches to the marginalized exact solver ONLY on a
TILES decision with k_remaining <= EXACT_MAX_K, and the latch is turn-atomic:
the boundary tile AND its meeple go to the solver together. During a MEEPLES
decision the engine has ALREADY pre-drawn next turn's tile (verified empirically
on the bank: `next_tile is not None` at every MEEPLES root), so the same turn's
TILES decision saw k_remaining + 1. Solver-owned therefore means:

  TILES  root: k_remaining     <= EXACT_MAX_K       (the latch condition itself)
  MEEPLE root: k_remaining + 1 <= EXACT_MAX_K       (its turn's tile decision latched)

On the CL-070 bank that excludes 20 roots (15 TILES k<=2, 5 MEEPLES k<=1); the
adaptive-k census's blanket `k_remaining <= 2` (25 roots) is ALSO recorded per
row (`latch_owned_blanket`) for joinability.

PROXY / LIMITATIONS (read before quoting a number)
--------------------------------------------------
1. **Seed lineage, not the literal in-game draw** — identical caveat to
   adaptive_k_census.py: the bank records no per-game agent seed, so worlds are a
   distributionally-equivalent redraw (salt=20260811, disjoint from 20260728 and
   the CL-070 tag salts 9000/9001). Only the census is valid, not any single row.
2. **Rules epoch**: the CL-070 bank is walled-era (pre-fixed_v1) self-play at the
   then-deploy k4x688. Replay MUST match the generating rules (checksum enforces
   it). The census contrast is WITHIN-root across sims rungs — both sides of every
   flip see the identical position — so the epoch offsets the position
   distribution, not the contrast. No fixed_v1 root bank exists yet.
3. **k_dets is today's 8** (PRODUCTION.yaml fair_deploy), not the bank era's 4.
   The census measures the CURRENT champion's budget response on those positions.
4. **No re-budgeting**: sims ladders DOWN from production on both decision types;
   the census measures the saturation SIGNAL, it cannot price the reallocation
   trade (a real split would spend the reclaimed sims on the other search).
5. **Flip rate is not regret**: a flip at a tiny top-2 gap may be nearly free in
   EV. The gap-binned split is the guard; pricing flips in points is follow-up
   work (the EV-loss grader exists) and is out of scope for this pre-gate.

DETERMINISM CONTROL (`--determinism-every N`)
---------------------------------------------
Re-searches world 0 at the reference rung on every N-th root and asserts a
bit-identical root-child table. On `--backend python` the re-search uses a
DIFFERENT search seed (the adaptive-k census's control: 898/898 identical). On
`--backend rust` carc_rs has no search seed (audit Gap 1 — seed-invariance
separately proven, GAP1_SEED_INVARIANCE.json), so the control there is a
same-call REPEAT: it verifies run-to-run determinism of the rust search, which
is exactly the property CRN-across-rungs rests on. The manifest records which
flavor ran.

USAGE
-----
    .venv/bin/python -u scripts/measurement_infra/simsplit_census.py \
        --roots /mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl \
        --out-dir measurement/simsplit_census_20260811 \
        --workers 14 --determinism-every 10 --tag main
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# adaptive_k_census owns the shared machinery: it installs the production leaf env
# (_CANON_ENV, BEFORE importing carcassonne_ai), the src/level2 sys.path entries,
# and the pure helpers this census reuses verbatim (phase_bucket, world_seed,
# pooled_pick, dedup_root_children, stratified_sample, _wilson).
import adaptive_k_census as AK  # noqa: E402  (env + paths side effect, deliberate)

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import random  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402

import root_replay as RR  # noqa: E402
import rust_world_search as RWS  # noqa: E402

LATCH_K = FA.EXACT_MAX_K

# Salt for THIS census's world lineage. Disjoint from the adaptive-k census
# (20260728), the CL-070 tag salts (9000/9001) and every move_agreement probe salt.
DEFAULT_SALT = 20260811

# The budget ladder, as divisors of the production per-world budget (ref first
# divisor MUST be such that rungs are distinct and >= 1; ref itself is the last).
RUNG_DIVISORS = (8, 4, 2, 1)

# Pre-registered fixed top-2-gap strata (reference-rung pooled gap). Fixed bins,
# not quantiles, so the PREREG can name them before the data exists.
GAP_BINS = ((0.0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, math.inf))


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested in tests/test_simsplit_census.py)                   #
# --------------------------------------------------------------------------- #
def derive_rungs(sims_ref: int, divisors=RUNG_DIVISORS) -> list:
    """The sims ladder from the production per-world budget. Strictly increasing,
    ends exactly at the reference; raises rather than silently deduping."""
    rungs = [int(sims_ref) // d for d in divisors]
    if rungs[-1] != int(sims_ref):
        raise ValueError(f"divisors must end at 1 (got {divisors})")
    if any(r < 1 for r in rungs):
        raise ValueError(f"sims_ref={sims_ref} too small for divisors {divisors}")
    if sorted(set(rungs)) != rungs:
        raise ValueError(f"rungs not strictly increasing/distinct: {rungs}")
    return rungs


def turn_latch_owned(phase: str, k_remaining: int, latch_k: int = LATCH_K) -> bool:
    """Solver ownership of a replayed root, TURN-ATOMIC (see module docstring).

    TILES: the latch condition itself (k <= latch_k). MEEPLES: the latch can only
    have fired at this turn's TILES decision, which saw k_remaining + 1 (the
    engine pre-draws next turn's tile before the meeple decision — verified on
    the bank). The latch is one-way monotone, so no earlier-turn case is missed:
    an earlier latch implies that turn's tile k <= latch_k implies this k+1 <= latch_k."""
    if phase == "TILES":
        return k_remaining <= latch_k
    if phase == "MEEPLES":
        return (k_remaining + 1) <= latch_k
    raise ValueError(f"unknown phase {phase!r}")


def gap_bin(gap) -> str:
    """Fixed pre-registered stratum label for a reference-rung top-2 gap."""
    if gap is None:
        return "na"
    g = float(gap)
    for lo, hi in GAP_BINS:
        if lo <= g < hi:
            return f"[{lo:g},{hi:g})" if hi != math.inf else f"[{lo:g},inf)"
    return "na"   # negative gap cannot happen (sorted desc), but never crash


def flips_vs_ref(picks: dict, ref_rung: int) -> dict:
    """{rung: pick != pick[ref]} for every non-reference rung. None picks compare
    unequal to a real pick (a rung that found no pooled action IS a decision change)."""
    ref = picks[ref_rung]
    return {s: bool(p != ref) for s, p in picks.items() if s != ref_rung}


def world_flip_frac(a_ref: list, a_s: list):
    """Fraction of worlds whose OWN pick at rung s differs from their own pick at
    the reference rung. Pairs with any None dropped; None if nothing comparable."""
    pairs = [(x, y) for x, y in zip(a_ref, a_s) if x is not None and y is not None]
    if not pairs:
        return None
    return sum(1 for x, y in pairs if x != y) / len(pairs)


def two_prop_z(k1: int, n1: int, k2: int, n2: int):
    """Pooled two-proportion z for rate1 - rate2. None if undefined (empty cell
    or both rates degenerate 0/1 so the pooled variance is 0)."""
    if n1 <= 0 or n2 <= 0:
        return None
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    var = p * (1 - p) * (1 / n1 + 1 / n2)
    if var <= 0:
        return None
    return (p1 - p2) / math.sqrt(var)


# --------------------------------------------------------------------------- #
# Worker                                                                        #
# --------------------------------------------------------------------------- #
_CFG = None
_RUNGS = None
_REF = None
_KDETS = None
_SALT = None
_BACKEND = "python"
_RUST_THREADS = 1
_SCFG_CACHE: dict = {}


def _init(cfg, rungs, k_dets, salt, backend="python", rust_threads=1):
    global _CFG, _RUNGS, _REF, _KDETS, _SALT, _BACKEND, _RUST_THREADS, _SCFG_CACHE
    _CFG, _RUNGS, _KDETS, _SALT = cfg, [int(s) for s in rungs], int(k_dets), int(salt)
    _REF = _RUNGS[-1]
    _BACKEND, _RUST_THREADS = str(backend), int(rust_threads)
    _SCFG_CACHE = {}


def _scfg_for(sims: int):
    """Per-rung SearchConfigRs, built lazily IN the worker (carc_rs objects don't
    cross the fork as initargs)."""
    if sims not in _SCFG_CACHE:
        from carcassonne_ai.rust_agent import search_config_rs
        _SCFG_CACHE[sims] = search_config_rs(_CFG, int(sims))
    return _SCFG_CACHE[sims]


def _harvest(n_map: dict, w_map: dict):
    """(own-pick, per-world stats tuple) from one world's deduped root table.
    Own pick = production final_select 'visits' with the (N, Q, -a) tiebreak."""
    if not n_map:
        return None
    return int(max(n_map, key=lambda a: (n_map[a], w_map[a] / n_map[a], -a)))


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
        phase = board.state.phase.name.upper()   # "TILES" / "MEEPLES"
        if r.get("phase") and phase != r["phase"]:
            raise AssertionError(f"replayed phase {phase} != bank phase {r['phase']}")
        out["phase"] = phase
        k_rem = int(FA.k_remaining(board.state))
        out["k_remaining"] = k_rem
        out["phase_bucket"] = AK.phase_bucket(k_rem)
        out["deck_size"] = int(len(board.state.deck))
        out["tile_in_hand"] = bool(board.state.next_tile is not None)
        out["latch_owned"] = turn_latch_owned(phase, k_rem)
        out["latch_owned_blanket"] = bool(k_rem <= LATCH_K)   # adaptive-k census rule
        legal = np.flatnonzero(game.get_valid_moves(board))
        out["n_legal"] = int(legal.size)
        out["backend"] = _BACKEND
        if out["latch_owned"]:
            out["ok"] = True          # solver-owned: censused for the count, not searched
            out["secs"] = round(time.time() - t0, 3)
            return out

        # On the rust backend this agent is a RustFairAgent used ONLY as the config
        # oracle (det_seed_base + construction-time leaf verification); the per-world
        # searches go through RustWorldSearcher (same pattern as adaptive_k_census).
        agent = CF.build_fair_champion(
            game, sims=_REF, k_dets=_KDETS,
            seed=AK.world_seed(r["deck_seed"], r["ply"], _SALT), cfg=_CFG,
            **({"backend": "rust", "rust_threads": _RUST_THREADS}
               if _BACKEND == "rust" else {}))
        base = agent.det_seed_base(0)
        det_rng = random.Random(base + 1)      # the agent's own deck-reshuffle stream

        # --- the k worlds, drawn ONCE and reused at every rung (CRN) -------------
        worlds = [FA.FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
                  for _ in range(_KDETS)]

        ws = None
        if _BACKEND == "rust":
            ws = RWS.RustWorldSearcher(game, _CFG, sims=_REF,
                                       deck_seed=int(r["deck_seed"]),
                                       prefix=r["actions"][:int(r["ply"])])
            ws.check_sync(board, "simsplit-root")

        def search_world(i: int, sims: int, seed_off: int = 100):
            """One world at one rung -> (n_map, w_map). Per-world seed base+off+i is
            IDENTICAL across rungs (CRN); on rust it is inert (Gap 1, proven)."""
            b = worlds[i]
            if ws is not None:
                stats = ws.search_world(b, scfg=_scfg_for(sims))
                return ({int(a): float(n) for a, n, _w in stats},
                        {int(a): float(w) for a, _n, w in stats})
            m = NeuralMCTS(game=game, evaluator=agent._evaluator, simulations=int(sims),
                           c_puct=agent._c_puct, seed=base + seed_off + i)
            m.search(b)
            root = m._nodes.get(key) or m._nodes[game.string_representation(b)]
            n_map, w_map = AK.dedup_root_children(root)
            m.clear()
            return n_map, w_map

        picks: dict = {}
        gaps: dict = {}
        a_best: dict = {}
        per_world_ref = None
        for s in _RUNGS:                        # ascending; worlds 0..k-1 within rung
            per_world = [search_world(i, s) for i in range(_KDETS)]
            picks[s], gaps[s] = AK.pooled_pick(per_world, _KDETS)
            a_best[s] = [_harvest(n, w) for n, w in per_world]
            if s == _REF:
                per_world_ref = per_world

        out["pick_by_sims"] = {str(s): picks[s] for s in _RUNGS}
        out["gap_by_sims"] = {str(s): gaps[s] for s in _RUNGS}
        out["a_best_by_sims"] = {str(s): a_best[s] for s in _RUNGS}
        out["ref_gap"] = gaps[_REF]
        out["ref_gap_bin"] = gap_bin(gaps[_REF])
        out["flip_by_sims"] = {str(s): v for s, v in flips_vs_ref(picks, _REF).items()}
        out["world_flip_frac_by_sims"] = {
            str(s): world_flip_frac(a_best[_REF], a_best[s])
            for s in _RUNGS if s != _REF}

        if r.get("_det_check"):
            # Reference-rung determinism control on world 0 (see module docstring:
            # different-seed on python, same-call repeat on rust).
            n2, w2 = search_world(0, _REF, seed_off=999 if _BACKEND == "python" else 100)
            out["determinism_identical"] = bool(n2 == per_world_ref[0][0]
                                                and w2 == per_world_ref[0][1])
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
def summarize(rows, rungs) -> dict:
    rungs = [int(s) for s in rungs]
    ref = rungs[-1]
    low = [s for s in rungs if s != ref]
    ok = [r for r in rows if r.get("ok")]
    live = [r for r in ok if not r.get("latch_owned")]
    summ = {"n_rows": len(rows), "n_ok": len(ok),
            "n_latch_owned_turn_atomic": len(ok) - len(live),
            "n_latch_owned_blanket": sum(1 for r in ok if r.get("latch_owned_blanket")),
            "n_live": len(live), "rungs": rungs, "ref_rung": ref}

    def block(sub):
        if not sub:
            return {"n": 0}
        d = {"n": len(sub),
             "n_legal_mean": float(np.mean([r["n_legal"] for r in sub])),
             "n_legal_median": float(np.median([r["n_legal"] for r in sub])),
             "k_remaining_median": float(np.median([r["k_remaining"] for r in sub]))}
        gaps = [r["ref_gap"] for r in sub if r.get("ref_gap") is not None]
        d["ref_gap_median"] = float(np.median(gaps)) if gaps else None
        for s in low:
            fl = sum(1 for r in sub if r["flip_by_sims"].get(str(s)))
            d[f"flip_{s}_rate"] = fl / len(sub)
            d[f"flip_{s}_n_flips"] = fl
            d[f"flip_{s}_ci68"] = AK._wilson(fl, len(sub), z=1.0)[1:]
            d[f"flip_{s}_ci95"] = AK._wilson(fl, len(sub), z=1.96)[1:]
            wf = [r["world_flip_frac_by_sims"].get(str(s)) for r in sub]
            wf = [x for x in wf if x is not None]
            d[f"world_flip_frac_{s}_mean"] = float(np.mean(wf)) if wf else None
        return d

    summ["overall"] = block(live)
    summ["by_decision_type"] = {ph: block([r for r in live if r["phase"] == ph])
                                for ph in ("TILES", "MEEPLES")}
    summ["by_phase_bucket"] = {pb: block([r for r in live if r["phase_bucket"] == pb])
                               for pb in ("early", "mid", "late")}
    # secondary: flip rate vs reference top-2 gap, within decision type
    bins = [gap_bin(lo) for lo, _hi in GAP_BINS]
    summ["by_gap_bin"] = {
        ph: {b: block([r for r in live
                       if r["phase"] == ph and r.get("ref_gap_bin") == b])
             for b in bins}
        for ph in ("TILES", "MEEPLES")}
    # the tile-vs-meeple contrast, raw and gap-matched (the confound guard)
    contrast = {}
    tiles = [r for r in live if r["phase"] == "TILES"]
    meeps = [r for r in live if r["phase"] == "MEEPLES"]
    for s in low:
        kt = sum(1 for r in tiles if r["flip_by_sims"].get(str(s)))
        km = sum(1 for r in meeps if r["flip_by_sims"].get(str(s)))
        c = {"raw_z": two_prop_z(kt, len(tiles), km, len(meeps)),
             "tiles": [kt, len(tiles)], "meeples": [km, len(meeps)]}
        for b in bins:
            tb = [r for r in tiles if r.get("ref_gap_bin") == b]
            mb = [r for r in meeps if r.get("ref_gap_bin") == b]
            ktb = sum(1 for r in tb if r["flip_by_sims"].get(str(s)))
            kmb = sum(1 for r in mb if r["flip_by_sims"].get(str(s)))
            c[f"gapbin_{b}_z"] = two_prop_z(ktb, len(tb), kmb, len(mb))
            c[f"gapbin_{b}_tiles"] = [ktb, len(tb)]
            c[f"gapbin_{b}_meeples"] = [kmb, len(mb)]
        contrast[str(s)] = c
    summ["tiles_vs_meeples_flip_contrast"] = contrast
    dc = [r["determinism_identical"] for r in ok if "determinism_identical" in r]
    if dc:
        summ["determinism_n"] = len(dc)
        summ["determinism_all_identical"] = bool(all(dc))
    secs = [r["secs"] for r in ok if not r.get("latch_owned")]
    if secs:
        summ["per_root_secs_mean"] = float(np.mean(secs))
        summ["per_root_secs_p90"] = float(np.percentile(secs, 90))
    return summ


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--roots", default="/mnt/c/carc-shared/classical_search/"
                                       "move_agreement_k4_b28e9/roots.jsonl")
    ap.add_argument("--out-dir", default=str(REPO / "measurement" / "simsplit_census_20260811"))
    ap.add_argument("--n", type=int, default=0,
                    help="0 = all roots; else stratified sample (on decision type)")
    ap.add_argument("--sample-seed", type=int, default=20260811)
    ap.add_argument("--sims-ref", type=int, default=0,
                    help="reference per-world budget; 0 = PRODUCTION.yaml sims_per_det")
    ap.add_argument("--k-dets", type=int, default=0, help="0 = PRODUCTION.yaml k_dets")
    ap.add_argument("--salt", type=int, default=DEFAULT_SALT)
    ap.add_argument("--determinism-every", type=int, default=10,
                    help="re-search world 0 at the reference rung on every N-th root "
                         "and assert bit-identity; 0 = off")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--tag", default="main")
    ap.add_argument("--backend", default="auto", choices=list(RWS.BACKENDS),
                    help="which ENGINE runs the per-world searches. Default 'auto' = "
                         "PRODUCTION.yaml fair_deploy backend (rust). Escape hatch: "
                         f"{RWS.FORCE_PYTHON_ENV}=1.")
    ap.add_argument("--rust-threads", type=int, default=1,
                    help="MUST stay 1 in this game-parallel census (W x t hot threads "
                         "is the documented failure mode; search_single is "
                         "single-threaded anyway).")
    args = ap.parse_args(argv)

    backend = RWS.resolve_backend(args.backend)
    if args.rust_threads != 1:
        if backend != "rust":
            ap.error(f"--rust-threads is a backend=rust knob (resolved: {backend})")
        if args.workers > 1:
            ap.error("keep rust_threads=1 in a game-parallel census")

    spec = CF.load_production_spec()
    cfg = CF.production_prior_cfg(spec)
    sims_ref = args.sims_ref or spec.sims_per_det
    k_dets = args.k_dets or spec.k_dets
    rungs = derive_rungs(sims_ref)

    rows = [json.loads(l) for l in Path(args.roots).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("ok", True)]
    print(f"[simsplit] roots={len(rows)} from {args.roots} | backend={backend} "
          f"| rungs={rungs} x k={k_dets}", flush=True)
    print(f"[simsplit] decision-type mix: {Counter(r['phase'] for r in rows)}", flush=True)
    if args.n:
        rows = AK.stratified_sample(rows, args.n, args.sample_seed, key="phase")
        print(f"[simsplit] stratified sample (on phase) -> {len(rows)} "
              f"({Counter(r['phase'] for r in rows)})", flush=True)
    for i, r in enumerate(rows):
        r["_det_check"] = bool(args.determinism_every
                               and i % args.determinism_every == 0)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.tag or "main"

    t0 = time.time()
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_init,
                  initargs=(cfg, rungs, k_dets, args.salt, backend,
                            int(args.rust_threads))) as pool:
        done = []
        for i, res in enumerate(pool.imap_unordered(_census_root, rows, chunksize=1), 1):
            done.append(res)
            if i % 50 == 0:
                print(f"[simsplit] {i}/{len(rows)}  {time.time()-t0:.0f}s", flush=True)
    dt = time.time() - t0
    done.sort(key=lambda r: (r["deck_seed"], r["ply"]))
    bad = [r for r in done if not r.get("ok")]
    print(f"[simsplit] {len(done)} roots in {dt:.0f}s ({len(bad)} failures)", flush=True)
    if bad:
        print(f"[simsplit] first failure: {bad[0].get('error')}", flush=True)

    rows_path = out_dir / f"rows_{tag}.jsonl"
    with rows_path.open("w") as fh:
        for r in done:
            fh.write(json.dumps(r) + "\n")

    summ = summarize(done, rungs)
    (out_dir / f"summary_{tag}.json").write_text(json.dumps(summ, indent=2))

    manifest = {
        "kind": "simsplit_pregate_census",
        "lever": "phase-asymmetric sims split (tile vs meeple budget within a turn) "
                 "— docs/LEVER_INDEX.md",
        "prereg": "measurement/simsplit_census_20260811/PREREG.md",
        "roots_source": args.roots,
        "n_roots_censused": len(done),
        "n_failures": len(bad),
        "sample": {"n": args.n or "all", "sample_seed": args.sample_seed,
                   "stratified_on": "phase (decision type)"},
        "world_draw": {
            "semantics": "fair_agent.FairHeuristicMCTSAgent.reshuffled_determinization "
                         "(canonical sort of the UNSEEN deck + rng.shuffle; next_tile untouched)",
            "seed_lineage": "adaptive_k_census.world_seed(deck_seed, ply, salt) -> agent seed; "
                            "det_rng = Random(agent.det_seed_base(0)+1); worlds drawn ONCE, "
                            "reused at every rung (CRN)",
            "salt": args.salt,
            "salt_note": "disjoint from the adaptive-k census (20260728) and the CL-070 "
                         "tag/probe salts (9000/9001)",
            "limitation": "distributionally-equivalent redraw, not the literal in-game worlds "
                          "(the bank records no per-game agent seed)",
        },
        "search": {"rungs_sims_per_world": rungs, "ref_rung": rungs[-1],
                   "k_dets": k_dets, "c_puct": spec.c_puct, "tau_p": spec.tau_p,
                   "note": "reference rung = PRODUCTION per-world budget; the ladder is "
                           "the SAME k worlds searched at each rung (only sims differ)"},
        "latch_band": {
            "exact_max_k": LATCH_K,
            "rule": "TURN-ATOMIC: TILES k<=K solver-owned; MEEPLES k+1<=K (its turn's "
                    "tile decision latched; engine pre-draws next tile during MEEPLES). "
                    "Blanket k<=K also recorded per row for adaptive-k joinability."},
        "rules_epoch_note": "bank is walled-era self-play (pre-fixed_v1); replay matches "
                            "the generating rules (checksum-enforced). The sims contrast "
                            "is within-root, so the epoch offsets the position "
                            "distribution, not the contrast.",
        "phase_cuts_k_remaining": AK.PHASE_CUTS,
        "gap_bins": [list(b) for b in GAP_BINS[:-1]] + [[GAP_BINS[-1][0], "inf"]],
        "execution": RWS.backend_manifest(
            backend, rust_threads=int(args.rust_threads),
            extra={"determinism_control":
                       (f"every {args.determinism_every} roots" if args.determinism_every
                        else "off") +
                       " — python: different-seed re-search (adaptive-k control); "
                       "rust: same-call repeat (run-to-run determinism; carc_rs has no "
                       "search seed, seed-invariance proven in "
                       "measurement/rustport_p6/GAP1_SEED_INVARIANCE.json)"}),
        "env": AK._CANON_ENV,
        "src_root": AK.SRC_ROOT,
        "fair_agent_file": FA.__file__,
        "champion_id": spec.champion_id,
        "workers": args.workers,
        "wall_secs": round(dt, 1),
        "rows_file": str(rows_path),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / f"manifest_{tag}.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: summ[k] for k in
                      ("overall", "by_decision_type", "tiles_vs_meeples_flip_contrast")
                      if k in summ}, indent=2), flush=True)
    print(f"[simsplit] wrote {rows_path} + summary_{tag}.json + manifest_{tag}.json",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
