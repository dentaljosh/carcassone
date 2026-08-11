#!/usr/bin/env python3
"""k-WIDTH MOVE-AGREEMENT — does the champion's pick still CHANGE from 11008 to 22016?

STATUS 2026-07-29: PRE-REGISTERED, pick phase of the budget-curve plateau discriminator.
See measurement/classical_search/KWIDTH_22016_PREREG_20260729.md. Emits nothing but PICKS;
the "did it IMPROVE" half is `oracle_score_pilot.py` reading these records.

WHAT THIS IS
------------
The 2026-07-29 promotion made **k8x1376 = 11008** the champion of record, chosen as the
CHEAPEST point on a budget->elo curve that PLATEAUS at ~+40 elo over the old deploy
(PRODUCTION.yaml budget_authorized_by (2): `curve_k16x1376_22016_vs_deploy_k4x688` reads
+35.58/z2.68 at 8x, statistically the same place as the 4x point). That plateau reading
comes from head-to-heads against a ruler, and a 3-sigma cross-band contradiction on the
cliff rows makes head-to-heads suspect. This harness is the pick half of the clean path:
**no opponent, no elo, no bands** -- just "where the two budgets disagree, which pick is
better", judged later by the oracle scorer.

Exactly the CL-070 question (`move_agreement_probe.py`) moved one rung up the ladder:
CL-070 asked it of 2752 vs 11008 and the oracle pilot answered "the deeper pick is
genuinely better" (+0.7375 pts/disagreement, cluster-robust z +2.97). This asks it of
**11008 (k8x1376, the NEW champion) vs 22016 (k16x1376)**.

⚠️ 22016 IS RUN AT THE MEASURED-BEST ALLOCATION k16x1376, NOT AT NAIVE k8x2752.
Width must be re-solved per budget: CL-054's k4 was optimal AT total 2752, k8 is optimal
AT 11008, and `curve_k16x1376` is the measured 22016 cell. Doubling sims_per_det instead
would price a DIFFERENT (and worse) agent and answer a question nobody asked.

THE COST TRICK -- ONE k16 RUN YIELDS BOTH PICKS, AND WHY THAT IS EXACT
-----------------------------------------------------------------------
Naively this costs 11008 + 22016 = 33024 sims per cell. It costs **22016**, because the
k8 pick is a PREFIX of the k16 run. Three facts, each read off `fair_agent._pimc_move`
rather than assumed:

  1. The determinization worlds come from ONE stream: `det_rng = random.Random(base + 1)`,
     consumed by `k_dets` sequential `reshuffled_determinization` calls. `base =
     det_seed_base(move_idx)` depends on (agent seed, move_idx) ONLY -- not on k_dets and
     not on sims. So world i is the same board for k=8 and k=16.
  2. World i's search seed is `base + 100 + i` -- also k_dets-independent. So world i's
     search is the same search.
  3. The pooled accumulators are built by `_merge_root_stats` in world order 0..k-1, and
     the pick is `pooled_q_argmax(agg_n, agg_w, min_pooled_visits)` with
     `min_pooled_visits = DEFAULT_MIN_POOLED_VISITS = 2` -- a CONSTANT, not a function of
     k or of budget.

(1)+(2) => the k16 agent's worlds 0..7 ARE the k8 agent's worlds. (3) => pooling the
first 8 of them reproduces the k8 agent's accumulators through the SAME `+=` sequence, so
even the order-sensitive float addition matches bit-for-bit, and the SAME decision rule
then reads the SAME action. This is the identical argument the k-parallel split rests on
(PRODUCTION.yaml's "KEY LOGICAL STEP"), applied along k instead of across processes.

⚠️ It is PROVEN PER RUN, NOT ASSERTED: `--verify-agent-parity N` builds REAL
`FairHeuristicPriorAgent`s at k8x1376 and k16x1376 on the same root with the same seed,
calls the deployed `_pimc_move`, and asserts both equal the prefix-8 and full-16 picks
this harness reports. Any mismatch fails the cell loudly. Do not trust the trick without
the flag.

FIDELITY: this harness does not MIRROR the deployed search, it CALLS it. Each world runs
through `fair_agent.search_one_world` and pools through `fair_agent._merge_root_stats` --
the same two functions `_pimc_move` calls -- so there is no reimplementation to drift.
(`move_agreement_probe.py` mirrors `_pimc_move` with a raw NeuralMCTS because it needs
mid-search snapshots at 7 levels; this harness needs ONE level, so it can just call the
real thing.)

CELLS, AND WHY (root, salt) AND NOT root
-----------------------------------------
A cell is a (root, salt) pair from the CL-070 bank: 898 replayable roots x 3 seed
lineages. The salt enters the agent seed via `move_agreement_probe.root_seed`, so distinct
salts draw independent worlds at the SAME root. That is deliberately the SAME cell
definition CL-070 banked, so this run's disagreement rate is directly comparable to its
`D_paired(2752, 11008) = 0.2398`. It also means records are NOT INDEPENDENT -- up to 3 per
root -- so every downstream statistic MUST cluster on `root_id`. Do not read a naive z.

`solver_region` cells (k_remaining <= exact_max_k = 2) are EXCLUDED by default: the agent
latches to the marginalized exact solver there, so the pick is budget-independent by
construction and including them would deflate the disagreement rate with structural zeros.
Forced roots (n_legal < 2) were already excluded at CL-070 sample time.

OUTPUT
------
One JSON per cell, in the shape `oracle_score_pilot.load_disagreements` reads:
`q_pick_by_level` keyed by TOTAL BUDGET ("11008" / "22016") rather than by
sims-per-determinization, since the two arms differ in k and not in sims. Score them with:

    oracle_score_pilot.py --records-dir <out>/records --roots <bank>/roots.jsonl \\
        --level-a 11008 --level-b 22016 --alloc-a k8x1376 --alloc-b k16x1376

Sign convention downstream: positive = the 22016 (wider) pick scores better.

2026-08-01 ADDITIVE FLAGS (`--k-a` / `--k-b` / `--sims-per-det`) — DEFAULT-IDENTICAL
------------------------------------------------------------------------------------
The two arms and the sims-per-determinization were module constants (8 / 16 / 1376). They
are now CLI-settable so the SAME harness can run the 10x rung (k8x1376 = 11008 vs
k80x1376 = 110080, measurement/classical_search/KWIDTH_110K_PREREG_20260801.md) without a
fork. **Defaults are unchanged (8 / 16 / 1376), so an unflagged invocation reproduces the
2026-07-29 run byte-for-byte** — the only manifest strings that vary are the two `role`
texts and the `question`, which switch to a generic wording ONLY when the flags are set
off-default. The cost trick's three facts (one det stream, per-world seed `base+100+i`,
world-order pooling with a constant `min_pooled_visits`) are k_dets-independent, so the
prefix argument holds for ANY k_a < k_b at a FIXED sims_per_det — and fixing sims_per_det
is exactly what makes it work, which is a second reason the 10x arm is width-scaled.

2026-08-02 `--backend {python,rust,auto}` — AUDIT ITEM A2, CONVERTED
--------------------------------------------------------------------
`BACKEND_BYPASS_AUDIT_20260801.md` §2 lists this harness as ~100% Python at 12.7 s/move
because it reaches INSIDE the champion (`agent._evaluator`, `agent._c_puct`,
`agent._min_pooled_visits`, `agent.det_seed_base`) and runs the per-world searches
itself — a shape no `backend=` kwarg on the builder can reach.  Its Rust route is the
per-world primitive `MirrorState` + `set_unseen_deck` + `search_single`, wrapped in
`rust_world_search.RustWorldSearcher`.

⚠️ **EXACTLY ONE THING MOVES: the per-world search.**  The determinization draw stays on
the Python `random.Random(det_seed_base(0) + 1)` stream and the pooling stays on
`fair_agent._merge_root_stats` / `pooled_q_argmax`.  That is deliberate — **the cost
trick's three facts are statements about THAT rng stream and THAT accumulation order**,
so leaving both in Python keeps the module docstring above true word-for-word on either
backend, and makes the two backends differ in the search and nothing else.
`FairAgentRs.determinizations()` would have been the "native" route and is NOT used: it
builds its own MT19937 per call and cannot hand the stream back.

`--verify-agent-parity` is re-gated, not inherited: on `--backend rust` it drives the
REAL `RustFairAgent` (mirror seated by `start_game_from_seed` + `advance` over the
recorded prefix) at k_a and k_b and asserts both equal the prefix-pool picks — the same
assertion against the same-backend deployed agent, so the flag still proves the trick
for the engine that actually ran.  Identity against the PYTHON leg is a separate claim,
gated by `scripts/rustport/gate_kwidth_backend.py` (0 mismatches on every non-timing
field, per-world raw f64 bits included).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to move_agreement_probe.py / oracle_score_pilot's
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

import argparse                # noqa: E402
import json                    # noqa: E402
import multiprocessing as mp   # noqa: E402
import random                  # noqa: E402
import signal                  # noqa: E402
import socket                  # noqa: E402
import subprocess              # noqa: E402
import time                    # noqa: E402
from collections import defaultdict  # noqa: E402

import numpy as np             # noqa: E402

import root_replay as RR       # noqa: E402
import rust_world_search as RWS  # noqa: E402
from carcassonne_ai import champion_factory as CF                  # noqa: E402
from carcassonne_ai.fair_agent import (                            # noqa: E402
    FairHeuristicMCTSAgent,
    _merge_root_stats,
    k_remaining as fair_k_remaining,
    pooled_q_argmax,
    search_one_world,
)

SCHEMA = "carcassonne-kwidth-agreement/v1"
DEFAULT_RUN_DIR = "/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9"

# The two arms. sims_per_det is HELD FIXED at the champion's 1376; only the PIMC width
# moves, which is what makes 22016 the measured-best allocation and not a naive doubling.
# Overridable by --sims-per-det / --k-a / --k-b (main() rebinds these before the fork);
# the DEFAULTS are the 2026-07-29 run's arms and must not be changed.
SIMS_PER_DET = 1376
K_A, K_B = 8, 16               # champion (11008) vs 2x (22016)
DEFAULT_ARMS = (8, 16, 1376)   # (k_a, k_b, sims_per_det) — the byte-identity baseline

_G: dict = {}


def root_seed(deck_seed: int, ply: int, salt: int) -> int:
    """Agent seed for one (root, salt) — IDENTICAL to move_agreement_probe.root_seed, so
    a cell here draws the same world lineage CL-070 banked for that cell."""
    return (int(deck_seed) * 1_000_003 + int(ply) * 8191
            + int(salt) * 2_654_435_761) & 0x7FFFFFFF


def load_cells(records_dir, include_solver_region: bool = False) -> list:
    """Every ok (root, salt) cell in the CL-070 bank, sorted by (root_id, salt).

    Metadata (phase, k_remaining, n_legal, h200 gap) is carried through from the banked
    record so the downstream strata are the SAME strata the pilot reported. The banked
    PICKS are not used — this harness recomputes at a different allocation."""
    out = []
    for p in sorted(Path(records_dir).glob("s*.json")):
        try:
            d = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not d.get("ok"):
            continue
        if d.get("solver_region") and not include_solver_region:
            continue
        out.append({
            "rid": d["rid"], "root_id": d["root_id"],
            "deck_seed": int(d["deck_seed"]), "ply": int(d["ply"]),
            "salt": int(d["salt"]),
            "k_remaining": d.get("k_remaining"),
            "game_phase": d.get("game_phase"), "phase_bucket": d.get("phase_bucket"),
            "n_legal": d.get("n_legal"),
            "h200_top2_q_gap": d.get("h200_top2_q_gap"),
            "solver_region": bool(d.get("solver_region")),
            "cl070_q_pick_2752": (d.get("q_pick_by_level") or {}).get("688"),
            "cl070_q_pick_11008": (d.get("q_pick_by_level") or {}).get("2752"),
        })
    out.sort(key=lambda r: (r["root_id"], r["salt"]))
    return out


def order_cells(cells: list, seed: int) -> list:
    """A deterministic PROCESSING ORDER over all cells.

    Not a sample: the adaptive stopping rule (prereg §3) needs to be able to extend N
    without re-drawing, so the run takes a PREFIX of one fixed shuffle. Prefix-stability
    is the whole point — `random.sample` would give unrelated draws at different k."""
    pool = sorted(cells, key=lambda r: (r["root_id"], r["salt"]))
    rng = random.Random(int(seed))
    idx = list(range(len(pool)))
    rng.shuffle(idx)
    return [pool[i] for i in idx]


def picks_from_world_stats(world_stats: list, k_a: int, k_b: int, minpv: int) -> dict:
    """Pool the per-world root stats over the k_a PREFIX and over the k_b full set.

    Both pools run through `_merge_root_stats` in world order — the SAME accumulation the
    deployed `_pimc_move` performs — so the k_a pool is bit-identical to a real k_a
    agent's, order-sensitive float addition included."""
    if len(world_stats) != k_b:
        raise ValueError(f"expected {k_b} worlds, got {len(world_stats)}")
    out = {}
    for tag, k in (("a", k_a), ("b", k_b)):
        agg_n: dict = defaultdict(float)
        agg_w: dict = defaultdict(float)
        for stats in world_stats[:k]:
            _merge_root_stats(stats, agg_n, agg_w)
        pick = pooled_q_argmax(agg_n, agg_w, minpv) if agg_n else None
        qs = sorted((agg_w[a] / agg_n[a] for a in agg_n if agg_n[a] > 0), reverse=True)
        out[tag] = {
            "k_dets": k, "total_budget": k * SIMS_PER_DET,
            "q_argmax_action": (int(pick) if pick is not None else None),
            "pooled_top2_q_gap": ((qs[0] - qs[1]) if len(qs) >= 2 else None),
            "sum_N": sum(agg_n.values()), "n_children": len(agg_n),
        }
    return out


def _init(cfg_kw: dict) -> None:
    _G.update(cfg_kw)
    _G["cfg"] = CF.production_prior_cfg()


def _process(item: dict) -> dict:
    rid = item["rid"]
    rec = {k: item[k] for k in (
        "rid", "root_id", "deck_seed", "ply", "salt", "k_remaining", "game_phase",
        "phase_bucket", "n_legal", "h200_top2_q_gap", "solver_region",
        "cl070_q_pick_2752", "cl070_q_pick_11008")}
    rec.update({
        "schema": SCHEMA, "sims_per_det": SIMS_PER_DET,
        "k_dets_a": K_A, "k_dets_b": K_B,
        "total_budget_a": K_A * SIMS_PER_DET, "total_budget_b": K_B * SIMS_PER_DET,
        "alloc_a": f"k{K_A}x{SIMS_PER_DET}", "alloc_b": f"k{K_B}x{SIMS_PER_DET}",
    })
    t0 = time.time()

    def _on_alarm(signum, frame):
        raise TimeoutError("per-cell wall cap")
    old = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(int(_G["wall_cap"]))
    try:
        game, board = RR.replay_actions(item["deck_seed"], item["actions"], item["ply"])
        cks = game.string_representation(board)
        rec["checksum_ok"] = bool(item.get("checksum") is None or cks == item["checksum"])
        if not rec["checksum_ok"]:
            rec.update(ok=False, error="checksum_mismatch")
            return rec

        legal = np.flatnonzero(game.get_valid_moves(board))
        rec["n_legal_now"] = int(legal.size)
        if legal.size < 2:
            rec.update(ok=False, error="forced_move")
            return rec

        rseed = root_seed(item["deck_seed"], item["ply"], item["salt"])
        rec["agent_seed"] = rseed
        backend = _G["backend"]
        rec["backend"] = backend
        # The k_b agent. Its worlds 0..k_a-1 ARE the k_a agent's worlds (module docstring).
        # On the rust backend this object is a RustFairAgent and is used ONLY as the
        # config oracle (`det_seed_base`, `_min_pooled_visits`, the exact-latch band) —
        # the per-world searches go through RustWorldSearcher below.
        agent = CF.build_fair_champion(
            game, sims=SIMS_PER_DET, k_dets=K_B, seed=rseed, cfg=_G["cfg"],
            **({"backend": "rust", "rust_threads": _G["rust_threads"]}
               if backend == "rust" else {}))
        # Fidelity guard: the prefix argument reads `_pimc_move` as it is TODAY. If a
        # later rev turned on a per-world knob, the prefix identity could silently break.
        for attr in ("_meeple_dedup", "_intra_reuse", "_parallel_workers"):
            if getattr(agent, attr, None):
                raise AssertionError(
                    f"agent has {attr} enabled — the k-prefix argument assumes the plain "
                    f"sequential world loop; refusing to run")
        k_rem = fair_k_remaining(board.state)
        rec["k_remaining_now"] = int(k_rem)
        rec["solver_region_now"] = bool(agent._exact_endgame and k_rem <= agent._exact_max_k)

        base = agent.det_seed_base(0)          # fixed-root probe -> move_idx 0
        rec["det_seed_base"] = int(base)
        det_rng = random.Random(base + 1)      # ONE stream, k_dets sequential shuffles
        root_key = game.string_representation(board)

        world_stats = []
        # The determinization DRAW is identical on both backends (same rng stream, same
        # `reshuffled_determinization`); only who searches the drawn world changes.
        ws = None
        if backend == "rust":
            ws = RWS.RustWorldSearcher(game, _G["cfg"], sims=SIMS_PER_DET,
                                       deck_seed=item["deck_seed"],
                                       prefix=item["actions"][:item["ply"]])
            ws.check_sync(board, "kwidth-root")
        for i in range(K_B):
            b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
            if ws is not None:
                world_stats.append(ws.search_world(b))
                continue
            m, stats, _telem = search_one_world(
                game, agent._evaluator, b, root_key,
                sims=SIMS_PER_DET, c_puct=agent._c_puct, seed=base + 100 + i)
            world_stats.append(stats)
            m.clear()

        arms = picks_from_world_stats(world_stats, K_A, K_B, agent._min_pooled_visits)
        pa = arms["a"]["q_argmax_action"]
        pb = arms["b"]["q_argmax_action"]
        rec["arms"] = arms
        # oracle_score_pilot.load_disagreements reads THIS, keyed by TOTAL budget.
        rec["q_pick_by_level"] = {str(K_A * SIMS_PER_DET): pa,
                                  str(K_B * SIMS_PER_DET): pb}
        rec["disagree"] = bool(pa is not None and pb is not None and int(pa) != int(pb))
        rec["root_player"] = int(board.state.current_player)

        if _G["verify_parity"]:
            # PROVE the prefix trick on this cell: the DEPLOYED decision at each width,
            # on the SAME backend that produced the prefix pools. The python leg calls
            # `_pimc_move` (which bypasses the exact latch); the rust agent's
            # `choose_action` IS the latching decision, so the two are the same function
            # only OUTSIDE the solver band — which is why a solver-region cell refuses
            # the check instead of quietly comparing two different rules.
            if backend == "rust" and rec["solver_region_now"]:
                raise AssertionError(
                    "agent-parity on backend=rust is not defined inside the solver band: "
                    "RustFairAgent.choose_action latches to the marginalized solver while "
                    "the prefix pools are pure PIMC. Run this cell without "
                    "--include-solver-region, or verify parity on --backend python.")
            for k, want in ((K_A, pa), (K_B, pb)):
                if backend == "rust":
                    ag = CF.build_fair_champion(
                        game, sims=SIMS_PER_DET, k_dets=k, seed=rseed, cfg=_G["cfg"],
                        backend="rust", rust_threads=_G["rust_threads"])
                    ag.start_game_from_seed(item["deck_seed"])
                    for a in item["actions"][:item["ply"]]:
                        ag.advance(int(a))
                    got = int(ag.choose_action(board, move_idx=0))
                else:
                    ag = CF.build_fair_champion(game, sims=SIMS_PER_DET, k_dets=k,
                                                seed=rseed, cfg=_G["cfg"])
                    got = int(ag._pimc_move(board, 0))
                if want is None or got != int(want):
                    raise AssertionError(
                        f"AGENT PARITY FAILED at k={k} (backend={backend}): deployed "
                        f"agent chose {got}, prefix-pool reported {want}")
            rec["agent_parity_verified"] = True

        rec["ok"] = True
        return rec
    except Exception as exc:                                   # noqa: BLE001
        rec.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        return rec
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        rec["elapsed_secs"] = round(time.time() - t0, 3)


def _git_rev(path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                     # noqa: BLE001
        return "unknown"


def build_manifest(args, n_pool: int, chosen: list) -> dict:
    default_arms = (K_A, K_B, SIMS_PER_DET) == DEFAULT_ARMS
    if default_arms:
        status = ("PRE-REGISTERED — pick phase of the 11008-vs-22016 plateau discriminator "
                  "(measurement/classical_search/KWIDTH_22016_PREREG_20260729.md).")
        question = ("Where the champion (k8x1376 = 11008) and 2x at the measured-best "
                    "allocation (k16x1376 = 22016) DISAGREE, is the deeper pick better? "
                    "This harness produces the disagreements; oracle_score_pilot.py judges "
                    "them.")
        role_b = ("2x budget at the MEASURED-BEST allocation "
                  "(results.csv curve_k16x1376_22016_vs_deploy_k4x688), NOT the "
                  "naive k8x2752")
    else:
        mult = (K_B * SIMS_PER_DET) / float(K_A * SIMS_PER_DET)
        status = ("PRE-REGISTERED — pick phase of an oracle-scored budget-disagreement "
                  "probe at off-default arms (see the run's own pre-registration).")
        question = (f"Where arm A (k{K_A}x{SIMS_PER_DET} = {K_A * SIMS_PER_DET}) and arm B "
                    f"(k{K_B}x{SIMS_PER_DET} = {K_B * SIMS_PER_DET}) DISAGREE, is the "
                    f"deeper pick better? This harness produces the disagreements; "
                    f"oracle_score_pilot.py judges them.")
        role_b = (f"{mult:g}x arm A's budget, WIDTH-SCALED at fixed sims_per_det="
                  f"{SIMS_PER_DET} — the allocation the world-prefix cost trick requires "
                  f"and the direction the 2026-07-29 22016 arm measured")
    return {
        "schema": SCHEMA,
        "harness": "kwidth_agreement_probe",
        "status": status,
        "question": question,
        "arms": {
            "a": {"k_dets": K_A, "sims_per_det": SIMS_PER_DET,
                  "total": K_A * SIMS_PER_DET,
                  "role": "THE CHAMPION OF RECORD (promoted 2026-07-29)"},
            "b": {"k_dets": K_B, "sims_per_det": SIMS_PER_DET,
                  "total": K_B * SIMS_PER_DET,
                  "role": role_b},
        },
        "cost_trick": {
            "claim": "one k16x1376 run yields BOTH picks; the k8 pick is the world-0..7 "
                     "PREFIX pool, bit-identical to a real k8 agent",
            "why": "det_rng = Random(det_seed_base(move_idx)+1) is one stream consumed in "
                   "world order; world i's search seed is base+100+i; both are "
                   "k_dets-independent; _merge_root_stats pools in world order and "
                   "min_pooled_visits is the constant 2",
            "cost_per_cell_sims": K_B * SIMS_PER_DET,
            "naive_cost_per_cell_sims": (K_A + K_B) * SIMS_PER_DET,
            "verify_agent_parity_cells": int(args.verify_parity),
            "proof": "--verify-agent-parity runs the DEPLOYED _pimc_move at k8 and k16 and "
                     "asserts both equal the reported picks; a mismatch fails the cell",
        },
        "source": {"run_dir": str(args.run_dir), "records_dir": str(args.records_dir),
                   "roots": str(args.roots),
                   "cells": "(root, salt) — SAME cell definition CL-070 banked, so the "
                            "disagreement rate is comparable to its D_paired 0.2398",
                   "claim": "CL-070 / measurement/classical_search/MOVE_AGREEMENT_PREREG.md"},
        "decision_rule": "q_argmax_action (pooled_q_argmax, min_pooled_visits=2) — the "
                         "DEPLOYED fair pick",
        "sampling": {"pool_cells": n_pool, "n_requested": int(args.n),
                     "n_chosen": len(chosen), "order_seed": int(args.order_seed),
                     "order": "fixed shuffle, PREFIX taken — extending N never re-draws",
                     "include_solver_region": bool(args.include_solver_region)},
        "workers": int(args.workers), "wall_cap_secs": int(args.wall_cap),
        "execution": RWS.backend_manifest(
            args.resolved_backend, rust_threads=int(args.rust_threads),
            extra={"identity_gate": "scripts/rustport/gate_kwidth_backend.py -> "
                                    "measurement/rustport_p6/GATE_KWIDTH_BACKEND.json",
                   "per_world_seed": "det_seed_base+100+i — passed on both backends; "
                                     "INERT (GAP1_SEED_INVARIANCE.json)"}),
        "env": dict(_CANON_ENV), "src_root": SRC_ROOT, "code_rev": _git_rev(REPO),
        "host": socket.gethostname(),
        "champion_manifest": CF.resolved_manifest("fair", verify=True),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", default=DEFAULT_RUN_DIR)
    ap.add_argument("--records-dir", default=None)
    ap.add_argument("--roots", default=None)
    ap.add_argument("--n", type=int, default=200, help="cells to process (prefix of the order)")
    ap.add_argument("--order-seed", type=int, default=20260729)
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--wall-cap", type=int, default=3600, help="per-cell seconds")
    ap.add_argument("--include-solver-region", action="store_true")
    ap.add_argument("--verify-agent-parity", dest="verify_parity", type=int, default=0,
                    help="run the DEPLOYED _pimc_move at k_a and k_b on the first N cells "
                         "and assert it agrees with the prefix pools. PROVES the cost "
                         "trick. Costs ~1.5x on the verified cells.")
    ap.add_argument("--k-a", dest="k_a", type=int, default=DEFAULT_ARMS[0],
                    help="PIMC width of arm A (the prefix arm). DEFAULT 8 = the champion.")
    ap.add_argument("--k-b", dest="k_b", type=int, default=DEFAULT_ARMS[1],
                    help="PIMC width of arm B (the wider arm). DEFAULT 16. Must exceed "
                         "--k-a; arm A is arm B's world-0..k_a-1 PREFIX.")
    ap.add_argument("--sims-per-det", dest="sims_per_det", type=int,
                    default=DEFAULT_ARMS[2],
                    help="simulations per determinization, HELD FIXED across both arms "
                         "(the prefix identity requires it). DEFAULT 1376.")
    ap.add_argument("--backend", default="python", choices=list(RWS.BACKENDS),
                    help="which ENGINE runs the per-world searches. 'python' (default) "
                         "is byte-identical to before this flag existed; 'auto' resolves "
                         f"from PRODUCTION.yaml. Escape hatch: {RWS.FORCE_PYTHON_ENV}=1 "
                         "forces python without editing a launcher.")
    ap.add_argument("--rust-threads", type=int, default=1,
                    help="carc_rs threads for the WHOLE-AGENT parity check only (the "
                         "per-world search_single is single-threaded). MUST stay 1 in a "
                         "game-parallel farm: W x t is the documented failure mode.")
    ap.add_argument("--out-root", default="/mnt/c/carc-shared/oracle_22016_20260729")
    ap.add_argument("--out-subdir", default="picks")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    # Arms are module-level because `_process` runs in FORKED workers, which inherit
    # module globals at fork time. Rebinding here (before the Pool is created) is
    # therefore the whole mechanism. Defaults leave them exactly as declared.
    global K_A, K_B, SIMS_PER_DET
    if args.k_a < 1 or args.k_b <= args.k_a:
        print(f"[fatal] need 1 <= --k-a < --k-b, got {args.k_a} / {args.k_b}",
              file=sys.stderr)
        return 2
    if args.sims_per_det < 1:
        print(f"[fatal] --sims-per-det must be >= 1, got {args.sims_per_det}",
              file=sys.stderr)
        return 2
    K_A, K_B, SIMS_PER_DET = int(args.k_a), int(args.k_b), int(args.sims_per_det)

    args.resolved_backend = RWS.resolve_backend(args.backend)
    if args.rust_threads != 1:
        if args.resolved_backend != "rust":
            print(f"[fatal] --rust-threads is a backend=rust knob (resolved backend is "
                  f"{args.resolved_backend})", file=sys.stderr)
            return 2
        if args.workers > 1:
            print(f"[fatal] --rust-threads {args.rust_threads} with --workers "
                  f"{args.workers}: this is a GAME-PARALLEL farm and W x t hot threads is "
                  f"the documented failure mode. Keep rust_threads=1.", file=sys.stderr)
            return 2

    run_dir = Path(args.run_dir)
    args.records_dir = Path(args.records_dir) if args.records_dir else run_dir / "records"
    args.roots = Path(args.roots) if args.roots else run_dir / "roots.jsonl"

    out_dir = Path(args.out_root) / args.out_subdir
    (out_dir / "records").mkdir(parents=True, exist_ok=True)

    pool = load_cells(args.records_dir, args.include_solver_region)
    if not pool:
        print("[fatal] no cells found — check --records-dir", file=sys.stderr)
        return 2
    ordered = order_cells(pool, args.order_seed)
    chosen = ordered[:int(args.n)]

    roots = {}
    for line in Path(args.roots).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        roots[f"s{int(o['deck_seed'])}_p{int(o['ply'])}"] = o
    items = []
    for c in chosen:
        r = roots.get(c["root_id"])
        if r is None:
            print(f"[fatal] root {c['root_id']} missing from {args.roots}", file=sys.stderr)
            return 2
        it = dict(c)
        it["actions"] = [int(a) for a in r["actions"]]
        it["checksum"] = r.get("checksum")
        items.append(it)

    manifest = build_manifest(args, len(pool), chosen)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[kwidth] pool={len(pool)} cells | chosen n={len(items)} | "
          f"k{K_A}x{SIMS_PER_DET}={K_A * SIMS_PER_DET} vs k{K_B}x{SIMS_PER_DET}="
          f"{K_B * SIMS_PER_DET} | W={args.workers} | parity-verify={args.verify_parity} "
          f"| backend={args.resolved_backend}")
    print(f"[kwidth] out -> {out_dir}")
    if args.dry_run:
        print("[kwidth] --dry-run: manifest written, nothing computed")
        return 0

    todo = items
    if args.resume:
        todo = [it for it in items
                if not (out_dir / "records" / f"{it['rid']}.json").exists()]
        print(f"[kwidth] resume: {len(items) - len(todo)} already done, {len(todo)} to go")

    # Parity verification is applied to the first `--verify-agent-parity` cells of the
    # PROCESSING ORDER, so a resumed run does not silently skip the proof.
    verify_rids = {it["rid"] for it in items[:int(args.verify_parity)]}

    t0 = time.time()
    if todo:
        w = max(1, min(int(args.workers), len(todo)))
        ctx = mp.get_context("fork")
        base_kw = dict(wall_cap=int(args.wall_cap),
                       backend=args.resolved_backend,
                       rust_threads=int(args.rust_threads))
        with ctx.Pool(w, initializer=_init,
                      initargs=({**base_kw, "verify_parity": False},)) as pool_:
            payload = [dict(it, _verify=(it["rid"] in verify_rids)) for it in todo]
            for i, rec in enumerate(pool_.imap_unordered(_process_dispatch, payload), 1):
                p = out_dir / "records" / f"{rec['rid']}.json"
                tmp = p.with_suffix(".tmp")
                tmp.write_text(json.dumps(rec))
                os.replace(tmp, p)
                flag = "ok" if rec.get("ok") else f"FAIL {rec.get('error')}"
                print(f"[{i}/{len(todo)}] {rec['rid']} {flag} "
                      f"a={rec.get('q_pick_by_level', {}).get(str(K_A * SIMS_PER_DET))} "
                      f"b={rec.get('q_pick_by_level', {}).get(str(K_B * SIMS_PER_DET))} "
                      f"disagree={rec.get('disagree')} "
                      f"parity={rec.get('agent_parity_verified', '-')} "
                      f"{rec.get('elapsed_secs')}s", flush=True)

    rows = []
    for it in items:
        p = out_dir / "records" / f"{it['rid']}.json"
        if p.exists():
            rows.append(json.loads(p.read_text()))
    ok = [r for r in rows if r.get("ok")]
    dis = [r for r in ok if r.get("disagree")]
    roots_ok = {r["root_id"] for r in ok}
    summary = {
        "schema": SCHEMA,
        "backend": args.resolved_backend,
        "n_attempted": len(items), "n_ok": len(ok),
        "n_failed": sum(1 for r in rows if not r.get("ok")),
        "n_disagreements": len(dis),
        "n_distinct_roots_ok": len(roots_ok),
        "n_distinct_roots_disagree": len({r["root_id"] for r in dis}),
        "disagreement_rate": (len(dis) / len(ok) if ok else None),
        "cl070_D_paired_2752_vs_11008": 0.2398,
        "n_parity_verified": sum(1 for r in ok if r.get("agent_parity_verified")),
        "wall_secs": round(time.time() - t0, 1),
        "manifest": str(out_dir / "manifest.json"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n=== k-WIDTH AGREEMENT SUMMARY ===")
    print(json.dumps(summary, indent=2))
    return 0


def _process_dispatch(item: dict) -> dict:
    """Per-cell entry point that honours the per-cell parity flag (the pool initializer
    cannot know which cells are in the verified prefix)."""
    _G["verify_parity"] = bool(item.pop("_verify", False))
    return _process(item)


if __name__ == "__main__":
    raise SystemExit(main())
