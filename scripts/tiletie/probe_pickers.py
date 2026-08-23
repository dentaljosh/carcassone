#!/usr/bin/env python3
"""THREE-PICKER OFFLINE PROBE — grade alternative tie-break PICKERS on the SPENT
tie-arbitration corpora with the tiearb_20260816 capture machinery, UNCHANGED.

    ⚠️  BUILD/READ HARNESS. 0 games. No band. No `experiments/results.csv` row.
    ⚠️  No claim id. `governance/PRODUCTION.yaml` and `BAND_REGISTRY.csv` are
    ⚠️  untouched on every path through this file.

WHAT THIS IS
------------
`measurement/tiearb_20260816` priced ONE picker — the deployed arbiter's
`tier1-greedy` argmax — against the clair-puct oracle's own argmax, and read

    arb = +0.2065 pts/tied ply (z +3.75)   ora = +0.2545   F = 0.811  CI [0.450, 1.320]

This harness generalises exactly one line of that pipeline — *which arm the
picker chooses* — and leaves every estimator, every scaling, every integrity
gate and the whole bootstrap alone. Three pickers:

  1. ``tier1``  the deployed arbiter's own cross-fit argmax over the
                `tier1-greedy` rollout matrix. **This reproduces `arb` BIT-FOR-BIT,
                and that is the harness's known-good gate** (`knowngood` mode).
  2. ``v29``    NEW python continuation policy: 1-ply argmax over the PRODUCTION
                flat leaf (curve125, `a36d2e15a3b3d71d`), played by BOTH seats to
                terminal on the SAME CRN worlds/playout seeds as `tier1-greedy`
                (roadmap "v2.9-GREEDY OFFLINE JUDGE LEG", queued 2026-08-21).
  3. ``net``    stage-0 learned tie-breaker: a PAIRWISE-RANKING model over the
                arms' afterstate features, trained on the spent corpora's own
                CRN arm-margin labels, split by `root_id`
                (roadmap "LEARNED TIE-BREAKER NET, STAGE-0", queued 2026-08-21).

HONESTY RAILS — carried from the two `docs/LEVER_INDEX.md` rows, enforced in code
--------------------------------------------------------------------------------
* **The `tier1` known-good MUST pass before any other number is looked at.**
  `grade` runs it first and ABORTS on failure. There is no flag to skip it.
* **`F_picker = arb_picker / ora` is the headline statistic**, with its root
  bootstrap CI (`analyze_tiearb.paired_ratio_bootstrap`, unmodified).
* **The CEILING CAVEAT is printed beside every result**: the ENTIRE judge-quality
  ceiling measured on this corpus is `ora - arb = +0.048 pts/tied ply` at the
  point estimate and **`F`'s CI [0.450, 1.320] includes 1**, i.e. includes ZERO
  headroom. A v2.9-greedy (or a net) can only buy an unknown fraction of that.
* **The net's capture is NEVER reported alone** — `grade --picker net` always
  prints `tier1` (and `v29` when its records exist) in the same table.
* ⚠️ **A declared asymmetry, stated because it flatters the net.** `tier1`/`v29`
  select on M/2 worlds and are priced on the disjoint M/2 (DESIGN §4.1's cross-fit,
  which is what makes them winner's-curse-clean). The net's pick does not depend on
  worlds at all, so its two folds agree and its `arb` is a FULL-M difference —
  unbiased for the same estimand but LESS noisy. Its winner's-curse protection is
  the root split, not the world split. Never read a net-vs-rollout `F` gap of
  order the noise as a strength difference.
* The design holdout is **SPENT** (tiearb READOUT, 2026-08-16). Nothing here
  re-opens a blind slice; the net's leakage control is a fresh root-level split
  (k-fold by `root_id` cross-fit, every root graded by a model that never saw it).

REUSE, NOT REIMPLEMENTATION
---------------------------
Imported and used unmodified (`tests/test_probe_pickers.py` asserts the imports):

  `analyze_tiletie`  : parity_indices, crossfit_regret, _sub_mean, aggregate,
                       cluster_robust, bootstrap_roots, zero_rates, load_plan,
                       discover_records, pts_to_elo
  `analyze_tiearb`   : build_positions (the join + every integrity gate + the
                       accepted-position set), merge_arb_records,
                       resolve_records_root, paired_ratio_bootstrap, rnd_arm_position
  `oracle_score_pilot`: world_seed / playout_seed / world_seeds (the CRN
                       derivation — IMPORTED, never re-derived), `_playout_value`,
                       `_process`, `main` (the whole record-writing leg)
  `run_tiletie`      : WORLD_SEED_SALT, _r9_for, verify_leg_records
  `build_tiearb_plan`: committed_order, chunk_slices (the chunk shape)

The v2.9 policy is injected at `oracle_score_pilot.build_continuation_agent` —
the seam that function's own docstring names ("The ONLY thing `--oracle-policy`
changes"). **`oracle_score_pilot.py` is not edited on disk**; the registration is
additive and process-local, so the ruler stays byte-identical for every other
caller (`tests/test_probe_pickers.py::test_oracle_score_pilot_unmodified`).

MODES
-----
    score-v29 --chunk k/N     score the v2.9-greedy leg (chunkable; writes
                              run_tiletie-shaped records + per-record elapsed_s)
    train-net                 build features/labels and fit the stage-0 ranker
    grade --picker {tier1,v29,net}    the capture read
    knowngood                 reproduce arb=0.2065 on the tier1 picker

USAGE
    python3 scripts/tiletie/probe_pickers.py knowngood
    python3 scripts/tiletie/probe_pickers.py price --playouts 20
    python3 scripts/tiletie/probe_pickers.py score-v29 --chunk 1/8 --workers 16
    python3 scripts/tiletie/probe_pickers.py train-net --build-features
    python3 scripts/tiletie/probe_pickers.py grade --picker net
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(HERE), str(REPO / "scripts" / "measurement_infra"),
           str(REPO / "measurement" / "gatec_c0_20260723")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ⚠️ ORDER IS LOAD-BEARING. `oracle_score_pilot` applies its `_CANON_ENV` (the
# production-leaf env) at import time and MUST land before `carcassonne_ai` is
# imported anywhere in this process — DEFAULT_CONFIG is import-frozen.
#
# ⚠️ AND A TRAP THAT IS *NOT* A TRAP HERE, checked at runtime: that `_CANON_ENV`
# pins `CARCASSONNE_V29_MEEPLE_CURVE` to the OLD frozen-anchor curve100
# (-8,-4,-1,0,2,3,4,5), NOT production's curve125. It does not matter for this
# harness because `champion_factory.production_leaf_cfg()` REPLACES the curve
# from `governance/PRODUCTION.yaml`'s own spec, so the resolved leaf hashes to
# `a36d2e15a3b3d71d` regardless of the ambient curve. `verify_leaf` proves it,
# loudly, before a single playout runs — see `register_v29_policy`.
import oracle_score_pilot as OSP                                   # noqa: E402
import analyze_tiletie as AT                                       # noqa: E402
import analyze_tiearb as ATB                                       # noqa: E402
import run_tiletie as RT                                           # noqa: E402
import build_tiearb_plan as BTP                                    # noqa: E402
from carcassonne_ai import champion_factory as CF                  # noqa: E402

SCHEMA = "carcassonne-tiletie-probe/v1"

# --- the corpus of record ---------------------------------------------------- #
#: The FULL 733-position / 1468-leg pooled plan. Its `positions_*.jsonl` are the
#: only complete on-disk copy of the corpus's move sequences (the tiearb/OOF
#: chunk dirs hold slices; the OOF dev leg files were written inside a since-
#: deleted agent worktree and are GONE — see PRICE.md "shape mismatches").
DEFAULT_PLAN_DIR = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
DEFAULT_IF_RECORDS = "/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct"
DEFAULT_ARB_ROOTS = list(ATB.DEFAULT_ARB_ROOTS)
DEFAULT_V29_ROOT = "/mnt/c/carc-shared/tiletie_probe_20260822"
DEFAULT_HOLDOUT = REPO / "measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json"
DEFAULT_OUT_DIR = REPO / "measurement/tiletie_probe_20260822"
TIEARB_READOUT = REPO / "measurement/tiearb_20260816/READOUT.json"

V29_POLICY = "v29-greedy"
PROBE_SEED = 20260822          # chunk permutation + net root split. One seed.
KNOWNGOOD_TOL = 1e-9           # tier1 must be BIT-equal, not merely close
#: DESIGN §3.1 — the accepted set the published numbers were read on. If this
#: harness sees a different one the gate FAILS rather than silently re-scoping.
N_POSITIONS_OF_RECORD = 733
N_ROOTS_OF_RECORD = 399

CEILING_CAVEAT = (
    "CEILING CAVEAT (LEVER_INDEX 'arbiter playout-policy upgrade', verbatim): on "
    "THIS corpus the entire judge-quality ceiling is ora - arb = +0.048 pts/tied "
    "ply at the point estimate, and F = 0.811 has CI95 [0.450, 1.320] — the CI "
    "INCLUDES 1, i.e. includes ZERO remaining headroom. Any picker's gain here is "
    "an unknown fraction of an effect that is itself consistent with zero. This is "
    "an OFFLINE probe of a B=16-grade selection; the DEPLOYED arbiter is B=64 and "
    "captures more, so the residual gap at deploy is plausibly smaller still.")

NET_ASYMMETRY_CAVEAT = (
    "NET FOLD ASYMMETRY: tier1/v29 select on M/2 worlds and are priced on the "
    "disjoint M/2; the net's pick is world-independent, so its two folds agree and "
    "its arb is a FULL-M difference — same estimand, LESS noise. Its winner's-curse "
    "control is the ROOT split, not the world split. Do not read a net-vs-rollout "
    "gap of order the noise as a strength difference.")


# =========================================================================== #
# 1. THE v2.9-GREEDY CONTINUATION POLICY                                       #
# =========================================================================== #
class V29GreedyPlayer:
    """1-ply argmax over the PRODUCTION flat leaf — the v2.9 curve125 leaf.

    Deliberately the SAME SHAPE as `RuleBasedPlayer._best_by_virtual_score`
    (materialise every legal child, score it from the MOVER's seat, take the
    exact-max set, break the tie with a seeded RNG) with exactly one thing
    changed: the leaf.

        RuleBasedPlayer : `virtual_score_inplace`  -- the v1 OBJECT leaf
        this            : `flat_leaf.flat_virtual_score_v2_float(child, mover,
                           production_leaf_cfg(), bag_close)`

    which is bit-for-bit the child evaluation the production MCTS prior uses
    (`heuristic_prior_mcts.make_heuristic_prior_evaluator._legal_deltas`); since
    the parent leaf is constant across siblings, argmax of the leaf == argmax of
    the prior's Δleaf logits.

    ⚠️ DECLARED DIFFERENCE, not hidden: RuleBasedPlayer's hand rules 2 and 3
    (endgame force-place, no-early-farmers — `_choose_meeple`) are NOT applied.
    They are hand rules, not the leaf, and the estimand the roadmap row names is
    "greedy over the production flat leaf". So `v29-greedy` differs from
    `tier1-greedy` in TWO declared ways — the leaf AND the absence of the two
    meeple hand-rules — and a leg that moves the number does not by itself say
    which of the two moved it. `--meeple-rules` is deliberately NOT a flag: a
    half-tested second policy variant would be worse than a stated caveat.

    ⚠️ Ties are compared on FLOATS by exact equality (RuleBasedPlayer compares
    ints). Exact-equal float leaves at sibling afterstates are rare but real; the
    seeded RNG resolves them, and the seed is the pick-independent `playout_seed`,
    so the CRN policy-level pairing is preserved exactly as `_GreedyContinuation`
    preserves it.
    """

    def __init__(self, game, seed: int = 0, leaf_cfg=None):
        from carcassonne_ai import flat_leaf                        # noqa: PLC0415

        self._game = game
        self._flat = flat_leaf
        self._cfg = leaf_cfg if leaf_cfg is not None else CF.production_leaf_cfg()
        self._bag_close = bool(getattr(self._cfg, "bag_close", False))
        self._rng = random.Random(int(seed))

    def choose_action(self, board) -> int:
        legal = np.flatnonzero(self._game.get_valid_moves(board))
        if legal.size == 0:
            raise RuntimeError("no legal moves — game should have ended")
        if legal.size == 1:                       # rule 1: forced move
            return int(legal[0])
        mover = int(board.state.current_player)
        scores = np.empty(legal.size, dtype=np.float64)
        for i, a in enumerate(legal):
            child, _ = self._game.get_next_state(board, int(a))
            scores[i] = self._flat.flat_virtual_score_v2_float(
                child.state, mover, self._cfg, self._bag_close)
        best_local = np.flatnonzero(scores == scores.max())
        return int(legal[int(self._rng.choice(best_local.tolist()))])


class V29GreedyContinuation:
    """`oracle_score_pilot`'s (`best_action`, `clear`) continuation shape.

    IN-FAMILY with the agents under test (it is the champion's own leaf), which is
    the opposite of `_GreedyContinuation`'s out-of-family design property — stated
    here because it is the one thing a reader must not carry over silently: this
    judge CAN express same-family self-preference where tier1-greedy could not.
    """

    def __init__(self, game, seed: int, leaf_cfg=None):
        self._p = V29GreedyPlayer(game, seed=seed, leaf_cfg=leaf_cfg)

    def best_action(self, board) -> int:
        return int(self._p.choose_action(board))

    def clear(self) -> None:
        return None


_V29_META = {
    "continuation_agent": "probe_pickers.V29GreedyContinuation",
    "family": "IN-FAMILY with the agents under test: no search (1-ply argmax) but "
              "the PRODUCTION curve125 flat leaf (a36d2e15a3b3d71d), i.e. the same "
              "leaf the champion is steered by. NOT the out-of-family discriminator "
              "tier1-greedy is — a positive sign here CAN be same-family "
              "self-preference, and must be read as such.",
    "uses_oracle_sims": False,
    "registered_by": "scripts/tiletie/probe_pickers.register_v29_policy "
                     "(process-local; oracle_score_pilot.py is NOT edited on disk)",
}


def register_v29_policy(osp=None, *, verify: bool = True):
    """Install `v29-greedy` at `oracle_score_pilot`'s documented dispatch seam.

    Additive and idempotent. Returns the resolved provenance dict. Raises
    `eval_provenance.ProvenanceError` (loudly, before any playout) if the leaf this
    process resolves is not the production champion leaf.
    """
    osp = osp or OSP
    leaf_cfg = CF.production_leaf_cfg()
    prov = CF.verify_leaf(leaf_cfg) if verify else {"hashes": {}}
    got = (prov.get("hashes") or {}).get("harness_leaf_hash")
    if verify and got != CF.LEAF_HASH_HARNESS:
        raise SystemExit(f"REFUSING: leaf hash {got!r} != {CF.LEAF_HASH_HARNESS!r}")

    osp.ORACLE_POLICIES.setdefault(V29_POLICY, dict(_V29_META))
    if getattr(osp.build_continuation_agent, "_probe_pickers_v29", False):
        return prov
    original = osp.build_continuation_agent

    def _dispatch(game, *, policy: str, sims: int, seed: int,
                  backend: str = "python", seat=None):
        if policy == V29_POLICY:
            if backend != "python":
                raise ValueError(
                    "v29-greedy is python-only: there is no rust port and none is "
                    "gated. Porting one is a separate, prereg-owing piece of work.")
            return V29GreedyContinuation(game, int(seed), leaf_cfg=leaf_cfg)
        return original(game, policy=policy, sims=sims, seed=seed,
                        backend=backend, seat=seat)

    _dispatch._probe_pickers_v29 = True
    _dispatch._wrapped_original = original
    osp.build_continuation_agent = _dispatch
    return prov


# =========================================================================== #
# 2. THE v2.9 LEG — score-v29 / leg-worker                                     #
# =========================================================================== #
def read_plan_legs(plan_dir) -> dict:
    """{"<profile>/leg<r>": [(rid, raw_json_line), ...]} from a run_tiletie plan.

    `build_tiearb_plan.read_leg_files` verbatim — same fallback for repo-relative
    paths, same line-count assertion against the plan.
    """
    plan_dir = Path(plan_dir)
    plan = json.loads((plan_dir / "POSITIONS_PLAN.json").read_text())
    return BTP.read_leg_files(plan_dir, plan)


def chunk_rids(rids, chunk: int, chunks: int, seed: int = PROBE_SEED) -> list:
    """The tiearb chunk shape, reused: ONE committed permutation, then contiguous
    slices — so a rid's every leg lands in the same chunk and no chunk can be a
    biased slice of the corpus."""
    order = BTP.committed_order(sorted(set(rids)), seed=seed)
    slices = BTP.chunk_slices(order, int(chunks))
    if not 1 <= int(chunk) <= int(chunks):
        raise SystemExit(f"REFUSING: --chunk {chunk}/{chunks} out of range")
    return list(slices[int(chunk) - 1])


def parse_chunk(s: str) -> tuple:
    try:
        k, n = str(s).split("/")
        return int(k), int(n)
    except Exception as exc:                                       # noqa: BLE001
        raise SystemExit(f"REFUSING: --chunk must look like 'k/N', got {s!r} ({exc})")


def write_chunk_legs(leg_rows: dict, keep: set, out_dir: Path) -> list:
    """Write the chunk's own run_tiletie-shaped leg files. Returns leg descriptors."""
    out_dir.mkdir(parents=True, exist_ok=True)
    legs = []
    for key, rows in sorted(leg_rows.items()):
        profile, legtag = key.split("/")
        lines = [ln for rid, ln in rows if rid in keep]
        if not lines:
            continue
        path = out_dir / f"positions_{profile}_{legtag}.jsonl"
        path.write_text("\n".join(lines) + "\n")
        legs.append({"key": key, "profile": profile, "leg": legtag,
                     "positions_path": str(path), "n": len(lines)})
    return legs


def leg_worker(argv) -> int:
    """SUBPROCESS entry point: register v29, then hand off to `oracle_score_pilot.main`.

    ⚠️ WHY A SUBPROCESS AND NOT AN IN-PROCESS CALL. `CARCASSONNE_FIX_R9` is an
    IMPORT-TIME LATCH and the corpus spans rules profiles that disagree on it, so
    the leg must be one process per (profile, leg) with R9 exported by the parent —
    exactly `run_tiletie`'s own discipline. Everything after registration is
    `oracle_score_pilot`'s unmodified code: its pool, its per-position wall cap, its
    records/, its manifest, its `elapsed_secs` stamp.
    """
    register_v29_policy()
    return int(OSP.main(list(argv)))


def leg_command(leg: dict, *, out_root: Path, workers: int, m: int, salt: str,
                oracle_sims: int, wall_cap: int, max_plies: int,
                resume: bool) -> list:
    return [sys.executable, str(Path(__file__).resolve()), "leg-worker",
            "--positions-jsonl", str(leg["positions_path"]),
            "--rules-profile", str(leg["profile"]),
            "--oracle-policy", V29_POLICY,
            "--m", str(int(m)),
            "--oracle-sims", str(int(oracle_sims)),
            "--world-seed-salt", str(salt),
            "--workers", str(int(workers)),
            "--n", str(int(leg["n"])),           # ALWAYS explicit — never subsample
            "--wall-cap", str(int(wall_cap)),
            "--max-plies", str(int(max_plies)),
            "--out-root", str(out_root),
            "--out-subdir", f"{V29_POLICY}/{leg['profile']}/{leg['leg']}",
            "--backend", "python"] + (["--resume"] if resume else [])


def cmd_score_v29(args) -> int:
    chunk, chunks = parse_chunk(args.chunk)
    prov = register_v29_policy()
    leg_rows = read_plan_legs(args.plan_dir)
    all_rids = {rid for rows in leg_rows.values() for rid, _ in rows}
    keep = set(chunk_rids(all_rids, chunk, chunks))
    out_root = Path(args.out_root) / f"chunk{chunk}"
    legs = write_chunk_legs(leg_rows, keep, out_root / "legs")
    n_legs = sum(l["n"] for l in legs)

    manifest = {
        "schema": SCHEMA, "mode": "score-v29", "generated_utc": _utc(),
        "policy": V29_POLICY, "policy_meta": _V29_META,
        "leaf_provenance": prov.get("hashes"),
        "plan_dir": str(args.plan_dir), "chunk": f"{chunk}/{chunks}",
        "chunk_seed": PROBE_SEED, "n_positions": len(keep), "n_legs": n_legs,
        "m": args.m, "world_seed_salt": args.salt, "workers": args.workers,
        "out_root": str(out_root), "legs": legs,
        "crn_note": "world_seed/playout_seed come from oracle_score_pilot, IMPORTED "
                    "and never re-derived; salt and M are FORCED by the existing "
                    "clair-puct records (tiearb DESIGN §3.3) and are not a choice.",
        "governance": "0 games, no band, no results.csv row, no claim id.",
        "git": _git_rev(),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"[plan] chunk {chunk}/{chunks}: {len(keep)} positions, {n_legs} legs, "
          f"{len(legs)} leg files -> {out_root}")
    if args.dry_run:
        print("[dry-run] nothing scored.")
        return 0

    t0 = time.time()
    problems = []
    for leg in legs:
        env = dict(os.environ)
        env["CARCASSONNE_FIX_R9"] = RT._r9_for(leg["profile"])
        cmd = leg_command(leg, out_root=out_root, workers=args.workers, m=args.m,
                          salt=args.salt, oracle_sims=args.oracle_sims,
                          wall_cap=args.wall_cap, max_plies=args.max_plies,
                          resume=args.resume)
        print(f"[leg] {leg['key']} n={leg['n']} R9={env['CARCASSONNE_FIX_R9']}")
        rc = subprocess.run(cmd, cwd=str(REPO), env=env).returncode
        leg["out"] = str(out_root / V29_POLICY / leg["profile"] / leg["leg"])
        v = RT.verify_leg_records(leg)
        leg["rc"], leg["verify"] = rc, v
        if rc != 0 or not v["ok"]:
            problems.append(leg["key"])
    manifest["legs"] = legs
    manifest["wall_secs"] = round(time.time() - t0, 1)
    manifest["problems"] = problems
    manifest["cost"] = cost_from_records(out_root / V29_POLICY, m=args.m)
    (out_root / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    if problems:
        print(f"[FAIL] legs with problems: {problems}")
        return 1
    print(f"[done] chunk {chunk}/{chunks} in {manifest['wall_secs']}s  "
          f"cost={json.dumps(manifest['cost'])}")
    (out_root / f"DONE_CHUNK{chunk}").write_text(_utc() + "\n")
    return 0


def cost_from_records(records_root, *, m: int) -> dict:
    """THE COST FIGURE OF RECORD: sum(elapsed_secs)/playouts, not wall-clock.

    `run_tiletie.run_smoke`'s own convention — wall-clock is inflated by the
    slowest position in the pool and must not be used for costing.
    """
    tot, n, rids = 0.0, 0, set()
    for p in Path(records_root).rglob("records/*.json"):
        try:
            rec = json.loads(p.read_text())
        except Exception:                                          # noqa: BLE001
            continue
        if rec.get("elapsed_secs") is None:
            continue
        tot += float(rec["elapsed_secs"])
        n += 1
        rids.add(rec.get("rid"))
    playouts = n * int(m) * 2                     # M worlds x {pick_a, pick_b}
    return {"n_records": n, "n_rids": len(rids), "worker_secs": round(tot, 1),
            "playouts": playouts,
            "worker_secs_per_playout": (round(tot / playouts, 4) if playouts else None)}


# =========================================================================== #
# 3. THE CAPTURE READ — grade / knowngood                                      #
# =========================================================================== #
def load_grade_inputs(args) -> dict:
    """Load every record set + the plan, and build the ACCEPTED position set by
    calling `analyze_tiearb.build_positions` — so the acceptance rules (G-ARMSET,
    partial-arm exclusion, champ-arm presence) and every integrity counter are the
    tiearb run's own, not a re-statement of them."""
    plan_bundle = AT.load_plan(Path(args.plan_dir))
    rates = AT.zero_rates(plan_bundle, getattr(args, "full_supply_plan", None))
    holdout = set(json.loads(Path(args.holdout_roots).read_text())["holdout_roots"])
    if_by_rid, if_present, if_not_ok = AT.discover_records(
        ATB.resolve_records_root(args.if_records))
    arb_by_rid, arb_present, arb_not_ok, arb_roots = ATB.merge_arb_records(args.arb_records)
    rows, integ, cross, counts = ATB.build_positions(
        plan_bundle["arms"], if_by_rid, arb_by_rid, rates, holdout,
        args.rnd_seed, parity_base=ATB.PARITY_BASE)
    return {"plan": plan_bundle, "rates": rates, "holdout": holdout,
            "if_by_rid": if_by_rid, "arb_by_rid": arb_by_rid, "rows": rows,
            "integrity": integ, "cross": cross, "counts": counts,
            "arb_roots": arb_roots,
            "present": {"if": if_present, "arb": arb_present},
            "not_ok": {"if": if_not_ok, "arb": arb_not_ok}}


def matrix_for(legs: dict, arm_order: list) -> list:
    """The A x M value matrix for one position from its per-leg records.

    `analyze_tiearb.build_positions`'s own assembly, verbatim:
    `[values_a of the first scored leg] + [values_b of each scored leg]`. Arm 0 is
    `pick_a`, shared by every leg of the rid (its `values_a` drift is an integrity
    counter the tiearb join already computes and reports)."""
    have = list(arm_order[1:])
    return [list(legs[have[0]]["values_a"])] + [list(legs[r]["values_b"]) for r in have]


def crn_cross_witness(a_by_rid: dict, b_by_rid: dict, rows: list) -> dict:
    """G-CRN across two judges — `world_seeds`/`playout_seeds`/(pick_a,pick_b) must
    be bit-identical leg for leg. Same witness `analyze_tiearb.build_positions`
    computes for (IF, ARB); recomputed here for (IF, V29)."""
    w = {"compared_legs": 0, "crn_cross_mismatch": 0, "seed_cross_mismatch": 0,
         "arm_cross_mismatch": 0, "missing_rids": 0, "examples": []}
    for row in rows:
        rid = row["rid"]
        la, lb = a_by_rid.get(rid), b_by_rid.get(rid)
        if not la or not lb:
            w["missing_rids"] += 1
            continue
        for r in row["arm_order"][1:]:
            ra, rb = la.get(r), lb.get(r)
            if ra is None or rb is None:
                w["missing_rids"] += 1
                continue
            w["compared_legs"] += 1
            if list(ra["world_seeds"]) != list(rb["world_seeds"]):
                w["crn_cross_mismatch"] += 1
                if len(w["examples"]) < 5:
                    w["examples"].append(f"{rid} leg{r} world_seeds")
            if list(ra["playout_seeds"]) != list(rb["playout_seeds"]):
                w["seed_cross_mismatch"] += 1
                if len(w["examples"]) < 5:
                    w["examples"].append(f"{rid} leg{r} playout_seeds")
            if (ra.get("pick_a"), ra.get("pick_b")) != (rb.get("pick_a"), rb.get("pick_b")):
                w["arm_cross_mismatch"] += 1
    return w


def price_picks(rows: list, if_by_rid: dict, picks_for) -> list:
    """Price a picker's arms with the IF (clair-puct) oracle on the EVALUATION
    worlds — the tiearb §4.1 line, with only `a_arb` generalised.

    `picks_for(row, matrix_if, fold_index, sel, eva) -> arm_position`. Everything
    else — the parity folds, the sub-means, the symmetrisation over folds — is
    `analyze_tiletie`'s, imported.
    """
    out = []
    for row in rows:
        legs = if_by_rid[row["rid"]]
        matrix_if = matrix_for(legs, row["arm_order"])
        m = len(matrix_if[0])
        champ_pos = row["champ_pos"]
        folds = (AT.parity_indices(m, base=ATB.PARITY_BASE, swap=False),
                 AT.parity_indices(m, base=ATB.PARITY_BASE, swap=True))
        vals, picks = [], []
        for fi, (sel, eva) in enumerate(folds):
            a = picks_for(row, matrix_if, fi, sel, eva)
            if a is None:
                vals, picks = None, None
                break
            eva_champ = AT._sub_mean(matrix_if[champ_pos], eva)
            vals.append(AT._sub_mean(matrix_if[a], eva) - eva_champ)
            picks.append(int(a))
        new = dict(row)
        if vals is None:
            new["arb"] = None
            new["picker_arms"] = None
        else:
            new["arb"] = (vals[0] + vals[1]) / 2.0
            new["picker_arms"] = picks
            new["pickchg"] = bool(any(a != champ_pos for a in picks))
            new["sel_agree"] = bool(all(a == b for a, b in
                                        zip(picks, row["a_ora_folds"])))
        out.append(new)
    return out


def picker_tier1(arb_by_rid: dict):
    """The DEPLOYED arbiter's picker: cross-fit argmax over the tier1-greedy matrix.
    `AT.crossfit_regret` returns (headroom, a_plus) and `a_plus` IS the pick."""
    def _pick(row, matrix_if, fi, sel, eva):
        legs = arb_by_rid.get(row["rid"])
        if not legs:
            return None
        mat = matrix_for(legs, row["arm_order"])
        return AT.crossfit_regret(mat, sel, eva, row["champ_pos"])[1]
    return _pick


def picker_v29(v29_by_rid: dict):
    """Identical selection rule, different continuation policy — that is the whole
    contrast the roadmap leg buys."""
    def _pick(row, matrix_if, fi, sel, eva):
        legs = v29_by_rid.get(row["rid"])
        if not legs:
            return None
        have = row["arm_order"][1:]
        if any(r not in legs for r in have):
            return None                            # G-ARMSET: partial arms excluded
        mat = matrix_for(legs, row["arm_order"])
        return AT.crossfit_regret(mat, sel, eva, row["champ_pos"])[1]
    return _pick


def picker_net(scores_by_rid: dict):
    """argmax of the learned score over the SCORED arm set. World-independent, so
    both folds return the same arm — see NET_ASYMMETRY_CAVEAT."""
    def _pick(row, matrix_if, fi, sel, eva):
        s = scores_by_rid.get(row["rid"])
        if s is None or len(s) != len(row["arm_order"]):
            return None
        return int(max(range(len(s)), key=lambda i: (s[i], -i)))
    return _pick


def aggregate_picker(rows: list, ora_rows: list, seed: int) -> dict:
    """AT.aggregate for arb and ora + ATB.paired_ratio_bootstrap for F. Imports only."""
    use = [r for r in rows if r.get("arb") is not None]
    rid_ok = {r["rid"] for r in use}
    den_rows = [r for r in ora_rows if r["rid"] in rid_ok]
    arb = AT.aggregate(use, "arb", "scale_all", seed=seed)
    ora = AT.aggregate(den_rows, "ora", "scale_all", seed=seed)
    num = [r["arb"] * r["scale_all"] for r in use]
    den = [r["ora"] * r["scale_all"] for r in den_rows]
    roots = [r["root_id"] for r in use]
    f_med, f_lo, f_hi, f_fin, g_boot = ATB.paired_ratio_bootstrap(
        num, den, roots, n_boot=ATB.BOOT_REPS, seed=seed)
    point = (arb["mean"] / ora["mean"]) if (ora["mean"] not in (None, 0)) else None
    return {
        "n": arb["n"], "n_roots": arb["n_roots"], "n_dropped": len(rows) - len(use),
        "arb": arb, "ora": ora,
        "F": point, "F_boot_median": f_med, "F_lo": f_lo, "F_hi": f_hi,
        "F_finite_reps": f_fin, "G-BOOT": g_boot,
        "G-BOOT_fired": bool(g_boot == g_boot and g_boot > ATB.GBOOT_BAR),
        "F_fixed": (arb["mean"] / ATB.FIXED_DENOM) if arb["mean"] is not None else None,
        "pickchg": (sum(1 for r in use if r.get("pickchg")) / len(use)) if use else None,
        "sel_agree": (sum(1 for r in use if r.get("sel_agree")) / len(use)) if use else None,
        "elo_arb": (AT.pts_to_elo(arb["mean"]) if arb["mean"] is not None else None),
    }


def run_knowngood(inp: dict, seed: int) -> dict:
    """THE GATE. The tier1 picker re-derives `arb` through this harness's own
    `price_picks`; it must equal the tiearb run's published pooled `arb`/`ora`
    BIT-FOR-BIT (the selection rule and the pricing are the same imported calls on
    the same records, so 'within bootstrap noise' would already be a bug).

    ⛔ Nothing else in this harness may be read until this passes.
    """
    rows = inp["rows"]
    priced = price_picks(rows, inp["if_by_rid"], picker_tier1(inp["arb_by_rid"]))
    # (a) per-position identity against the tiearb join's own `arb`.
    worst, worst_rid = 0.0, None
    for a, b in zip(rows, priced):
        if b["arb"] is None:
            continue
        d = abs(a["arb"] - b["arb"])
        if d > worst:
            worst, worst_rid = d, a["rid"]
    # (b) pooled identity against the published READOUT.
    got = aggregate_picker(priced, rows, seed)
    pub = json.loads(TIEARB_READOUT.read_text())["primary"]
    d_arb = abs(got["arb"]["mean"] - pub["arb"])
    d_ora = abs(got["ora"]["mean"] - pub["ora"])
    d_f = abs(got["F"] - pub["F"])
    ok = (worst <= KNOWNGOOD_TOL and d_arb <= KNOWNGOOD_TOL
          and d_ora <= KNOWNGOOD_TOL and d_f <= KNOWNGOOD_TOL
          and got["n"] == N_POSITIONS_OF_RECORD and got["n_roots"] == N_ROOTS_OF_RECORD)
    return {"schema": SCHEMA, "gate": "KNOWNGOOD", "ok": bool(ok),
            "tol": KNOWNGOOD_TOL,
            "published": {"arb": pub["arb"], "ora": pub["ora"], "F": pub["F"]},
            "reproduced": {"arb": got["arb"]["mean"], "ora": got["ora"]["mean"],
                           "F": got["F"], "n": got["n"], "n_roots": got["n_roots"]},
            "max_abs_position_delta": worst, "worst_rid": worst_rid,
            "delta": {"arb": d_arb, "ora": d_ora, "F": d_f},
            "n_of_record": [N_POSITIONS_OF_RECORD, N_ROOTS_OF_RECORD],
            "source_readout": str(TIEARB_READOUT.relative_to(REPO)),
            "generated_utc": _utc()}


def require_knowngood(inp: dict, seed: int, out_dir: Path) -> dict:
    kg = run_knowngood(inp, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "KNOWNGOOD.json").write_text(json.dumps(kg, indent=2))
    print(fmt_knowngood(kg))
    if not kg["ok"]:
        raise SystemExit(
            "⛔ KNOWNGOOD FAILED — the harness does not reproduce arb=0.2065 on the "
            "tier1 picker. NO OTHER NUMBER IN THIS HARNESS MAY BE READ. Fix the "
            "harness (or the record roots) before looking at v29 or net.")
    return kg


def fmt_knowngood(kg: dict) -> str:
    r, p = kg["reproduced"], kg["published"]
    tag = "PASS ✅" if kg["ok"] else "FAIL ⛔"
    return (f"\n=== KNOWNGOOD GATE (tier1 picker vs {kg['source_readout']}) — {tag} ===\n"
            f"  arb  published {p['arb']:.10f}  reproduced {r['arb']:.10f}  "
            f"Δ {kg['delta']['arb']:.3e}\n"
            f"  ora  published {p['ora']:.10f}  reproduced {r['ora']:.10f}  "
            f"Δ {kg['delta']['ora']:.3e}\n"
            f"  F    published {p['F']:.10f}  reproduced {r['F']:.10f}  "
            f"Δ {kg['delta']['F']:.3e}\n"
            f"  n={r['n']} positions / {r['n_roots']} roots   "
            f"max per-position Δ {kg['max_abs_position_delta']:.3e} "
            f"(tol {kg['tol']:.0e})\n")


def _fx(x, n=4, sign=True):
    if x is None or x != x:
        return "None"
    return f"{x:+.{n}f}" if sign else f"{x:.{n}f}"


def fmt_block(name: str, b: dict) -> str:
    a, o = b["arb"], b["ora"]
    return (f"  {name:<7} n={b['n']:<4} roots={b['n_roots']:<4} "
            f"dropped={b['n_dropped']:<4}\n"
            f"          arb {_fx(a['mean'])}  se {_fx(a['se_cluster'], sign=False)}  "
            f"z {_fx(a['z'], 2)}  boot [{_fx(a['boot_lo'])}, {_fx(a['boot_hi'])}]\n"
            f"          ora {_fx(o['mean'])}  z {_fx(o['z'], 2)}\n"
            f"          F = {_fx(b['F'])}  CI95 [{_fx(b['F_lo'])}, {_fx(b['F_hi'])}]  "
            f"F_fixed {_fx(b['F_fixed'])}  (F=1 means 'captures the whole headroom')\n"
            f"          pick≠champ {_fx(b['pickchg'], 3, sign=False)}  "
            f"agrees-with-oracle {_fx(b['sel_agree'], 3, sign=False)}  "
            f"G-BOOT {_fx(b['G-BOOT'], 4, sign=False)}"
            f"{'  ⚠️ FIRED' if b['G-BOOT_fired'] else ''}")


def cmd_grade(args) -> int:
    out_dir = Path(args.out_dir)
    inp = load_grade_inputs(args)
    kg = require_knowngood(inp, args.boot_seed, out_dir)     # ⛔ THE GATE, always first

    rows = inp["rows"]
    blocks, witnesses = {}, {}

    # tier1 is ALWAYS computed and ALWAYS printed — no picker is ever read alone.
    t1 = price_picks(rows, inp["if_by_rid"], picker_tier1(inp["arb_by_rid"]))
    blocks["tier1"] = aggregate_picker(t1, rows, args.boot_seed)

    v29_by_rid = None
    if args.picker in ("v29", "net", "all"):
        v29_by_rid, v29_present, v29_not_ok, v29_roots = _load_v29(args)
        if v29_by_rid:
            witnesses["G-CRN_if_vs_v29"] = crn_cross_witness(
                inp["if_by_rid"], v29_by_rid, rows)
            witnesses["v29_roots"] = v29_roots
            witnesses["v29_not_ok"] = v29_not_ok
            v = price_picks(rows, inp["if_by_rid"], picker_v29(v29_by_rid))
            blocks["v29"] = aggregate_picker(v, rows, args.boot_seed)
        elif args.picker == "v29":
            raise SystemExit(f"REFUSING: no v29-greedy records under {args.v29_records}. "
                             f"Run `score-v29` first.")

    if args.picker in ("net", "all"):
        scores = load_net_scores(args)
        n = price_picks(rows, inp["if_by_rid"], picker_net(scores["scores_by_rid"]))
        blocks["net"] = aggregate_picker(n, rows, args.boot_seed)
        witnesses["net_model"] = scores["meta"]

    report = {
        "schema": SCHEMA, "mode": "grade", "picker": args.picker,
        "generated_utc": _utc(), "git": _git_rev(),
        "knowngood": kg, "blocks": blocks, "witnesses": witnesses,
        "integrity": inp["integrity"], "cross_if_vs_tier1": inp["cross"],
        "completion": inp["counts"], "arb_roots": inp["arb_roots"],
        "ceiling_caveat": CEILING_CAVEAT,
        "net_asymmetry_caveat": NET_ASYMMETRY_CAVEAT,
        "governance": "0 games, no band, no results.csv row, no claim id. "
                      "The tiearb holdout is SPENT; nothing here re-opens a blind slice.",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"GRADE_{args.picker}.json").write_text(json.dumps(report, indent=2,
                                                                 default=str))
    print(f"\n=== CAPTURE (pts/tied ply, scale_all currency; "
          f"F = arb_picker / ora, same positions, same oracle) ===")
    for name in ("tier1", "v29", "net"):
        if name in blocks:
            print(fmt_block(name, blocks[name]))
    print(f"\n⚠️  {CEILING_CAVEAT}")
    if "net" in blocks:
        print(f"\n⚠️  {NET_ASYMMETRY_CAVEAT}")
    print(f"\n[wrote] {out_dir / f'GRADE_{args.picker}.json'}")
    return 0


def _load_v29(args):
    roots = []
    base = Path(args.v29_records)
    if (base / V29_POLICY).is_dir():
        roots = [base / V29_POLICY]
    else:
        roots = sorted(p / V29_POLICY for p in base.glob("chunk*")
                       if (p / V29_POLICY).is_dir())
    if not roots:
        return None, {}, [], []
    by_rid, present, not_ok, resolved = ATB.merge_arb_records([str(r) for r in roots])
    return by_rid, present, not_ok, resolved


# =========================================================================== #
# 4. STAGE-0 LEARNED TIE-BREAKER                                               #
# =========================================================================== #
#
# MODEL CHOICE, justified (roadmap "LEARNED TIE-BREAKER NET, STAGE-0").
#   * The label budget is the binding constraint, not capacity: ~3K tied plies
#     across the schema-matching corpora, ~1.5 usable sibling PAIRS per ply after
#     the root split. CL-064 already showed the learned-track failures are NOT a
#     capacity problem, so buying capacity first would re-run a settled question.
#   * So the default is a PAIRWISE LOGISTIC RANKER over the 84-dim
#     `c0_features.emit_features_dict` afterstate vector: fit on antisymmetrised
#     within-position difference vectors (x_i - x_j, y = 1[label_i > label_j]),
#     no intercept, L2 with C chosen by an INNER root-grouped CV inside the
#     training folds only. It is the direct antidote CL-073 names — a sibling
#     RANKING objective, not an outcome regressor.
#   * `--model gbdt` (sklearn HistGradientBoostingClassifier on the same pairwise
#     rows) is the capacity check. xgboost/lightgbm are NOT installed in the venv;
#     torch is, but a tiny MLP at this label count buys variance, not signal.
#   * Features are the CHEAP scalar path on purpose: one `flat_leaf.decompose` per
#     child, no 78-plane `board_repr.encode_board`, no deepcopy of the engine's
#     object graph.

FEATURE_MODULE = "measurement/gatec_c0_20260723/c0_features.py"


def _c0():
    import c0_features                                            # noqa: PLC0415
    return c0_features


def build_features(args) -> dict:
    """(rid, arm_position) -> 84-dim afterstate feature vector.

    ⚠️ ONE RULES PROFILE PER PROCESS. `CARCASSONNE_FIX_R9` is an import-time latch
    (`oracle_score_pilot.main`'s own check), so this refuses to mix profiles and
    must be invoked once per profile with R9 exported. The profile is stamped in
    the cache so `train-net` can refuse a mixed cache.
    """
    import root_replay as RR                                       # noqa: PLC0415
    from carcassonne_ai import rules_profile as RP                 # noqa: PLC0415

    c0 = _c0()
    cfg = CF.production_leaf_cfg()
    prof = RP.activate(args.rules_profile)
    if RP.r9_env_on() != prof.r9_env_expected:
        raise SystemExit(
            f"REFUSING: profile {args.rules_profile!r} expects "
            f"{RP.R9_ENV_VAR}={int(prof.r9_env_expected)} but this process is latched "
            f"at {int(RP.r9_env_on())}. Export it in the launcher; ONE PROCESS PER EPOCH.")
    game_kwargs = prof.game_kwargs() or None

    leg_rows = read_plan_legs(args.plan_dir)
    by_rid = defaultdict(dict)                     # rid -> {arm_action: line}
    meta = {}
    for key, rows in leg_rows.items():
        if not key.startswith(f"{args.rules_profile}/"):
            continue
        for rid, line in rows:
            d = json.loads(line)
            by_rid[rid][int(d["pick_a"])] = d
            by_rid[rid][int(d["pick_b"])] = d
            meta[rid] = d

    arms_index = json.loads(Path(args.plan_dir, "ARMS.json").read_text())
    order = c0.feature_order(cfg)
    feats, skipped = {}, []
    t0 = time.time()
    for i, rid in enumerate(sorted(by_rid)):
        row = meta[rid]
        if rid not in arms_index:
            skipped.append({"rid": rid, "error": "KeyError: absent from ARMS.json"})
            continue
        arms = [int(a) for a in arms_index[rid]["arms"]]
        try:
            actions = row.get("actions")
            if not actions:
                actions = _actions_from_archive(row["archive_path"])
            game, board = RR.replay_actions(row["deck_seed"], actions, row["ply"],
                                            game_kwargs=game_kwargs)
            seat = int(row["root_player"])
            vecs = []
            for a in arms:
                child, _ = game.get_next_state(board, int(a))
                fd = c0.emit_features_dict(child.state, seat, cfg)
                vecs.append([float(fd[k]) for k in order])
            feats[rid] = vecs
        except Exception as exc:                                   # noqa: BLE001
            skipped.append({"rid": rid, "error": f"{type(exc).__name__}: {exc}"})
        if args.limit and len(feats) >= args.limit:
            break
        if (i + 1) % 25 == 0:
            print(f"  [feat] {i+1}/{len(by_rid)}  {time.time()-t0:.0f}s", flush=True)
    return {"schema": SCHEMA, "kind": "features", "rules_profile": args.rules_profile,
            "feature_order": order, "feature_module": FEATURE_MODULE,
            "leaf_hash": CF.LEAF_HASH_HARNESS, "n": len(feats),
            "skipped": skipped, "features": feats,
            "elapsed_secs": round(time.time() - t0, 1)}


def _actions_from_archive(path) -> list:
    d = json.loads(Path(path).read_text())
    for k in ("actions", "action_sequence", "moves"):
        if k in d:
            return [int(a) for a in d[k]]
    raise KeyError(f"no action sequence in {path}")


def collect_labels(args) -> dict:
    """(rid, arm_position) -> the CRN world-mean margin under the ARBITER's judge.

    The label is the *arbiter's* value, not the oracle's: stage-0 DISTILS the
    arbiter (LEVER_INDEX row: "train a net to reproduce the tie arbiter's CRN
    world-mean margins ... at leaf-tied plies"). Pricing it with the oracle later
    is therefore not circular.
    """
    arb_by_rid, _, _, roots = ATB.merge_arb_records(args.arb_records)
    arms_index = json.loads(Path(args.plan_dir, "ARMS.json").read_text())
    out = labels_from_records(arb_by_rid, arms_index)
    out["roots"] = roots
    return out


def labels_from_records(by_rid: dict, arms_index: dict, *, allow_m=(None,),
                        subset_worlds: int = 0) -> dict:
    """`collect_labels`' body, factored so a SECOND judge's records can reuse it
    verbatim (P3 needs the `clair-puct` oracle's own arm order through the exact
    same shape gates) and so the stage-1 auxiliary corpora can be admitted with an
    EXPLICIT `m` waiver instead of a silent coercion.

    `allow_m=(None,)` means "the stage-0 rule": `m` must equal `ATB.M_EXPECTED`
    (32) or the rid is refused and counted under `shape_problems`. Passing e.g.
    `allow_m=(32, 128), subset_worlds=32` admits an `m=128` corpus by taking the
    FIRST 32 CRN worlds — an exact estimand match, because the world seeds are
    ordered and the salt is identical (PLAN.md §3.1). The waiver is recorded on
    every affected rid so the witness can never lose it.
    """
    labels, shape_problems = {}, []
    n_subset = 0
    for rid, legs in by_rid.items():
        meta = arms_index.get(rid)
        if meta is None:
            shape_problems.append({"rid": rid, "why": "absent from ARMS.json"})
            continue
        need = list(range(1, len(meta["arms"])))
        have = sorted(k for k in legs if k in need)
        if have != need:
            shape_problems.append({"rid": rid, "why": f"partial arms {have} != {need}"})
            continue
        ref = legs[have[0]]
        m_rec = int(ref.get("m") or 0)
        ok_m = (m_rec == ATB.M_EXPECTED) if allow_m == (None,) else (m_rec in allow_m)
        if not ok_m:
            shape_problems.append({"rid": rid, "why": f"m={ref.get('m')} != "
                                                      f"{ATB.M_EXPECTED}"})
            continue
        if ref.get("world_seed_salt") != RT.WORLD_SEED_SALT:
            shape_problems.append({"rid": rid, "why": f"salt={ref.get('world_seed_salt')}"})
            continue
        cut = int(subset_worlds) if (subset_worlds and m_rec > int(subset_worlds)) else 0
        if cut:
            n_subset += 1
        mat = matrix_for(legs, [0] + have)
        if cut:
            mat = [row[:cut] for row in mat]
        vals = [float(np.mean(row)) for row in mat]
        labels[rid] = {"root_id": meta["root_id"], "arm_order": [0] + have,
                       "labels": vals, "m": (cut or m_rec),
                       "m_record": m_rec, "worlds_subset": bool(cut),
                       "n_arms_planned": len(meta["arms"]),
                       "rules_profile": meta.get("rules_profile"),
                       "se_pairs": se_pairs_for(mat)}
    return {"labels": labels, "shape_problems": shape_problems, "roots": [],
            "n_rids": len(labels), "n_subset_worlds": n_subset,
            "n_arm_labels": sum(len(v["labels"]) for v in labels.values())}


def se_pairs_for(matrix) -> dict:
    """`se_pair` for every unordered sibling pair, CRN-PAIRED (PLAN.md §6.4).

    The arms of one rid are scored on the SAME ordered CRN worlds, so the honest
    standard error of `margin_i − margin_j` is the sd of the per-world DIFFERENCE
    over √m — not `sd·√2/√m`, which is the unpaired form the plan writes beside
    its own "CRN-paired ⇒ use the paired sd" instruction. The paired form is used;
    it is smaller wherever the CRN pairing works, so it is the CONSERVATIVE choice
    for a near-tie filter (it declares FEWER pairs to be coin flips).

    Keys are `"i,j"` strings so the dict survives a JSON round-trip.
    """
    out = {}
    n = len(matrix)
    m = len(matrix[0]) if n else 0
    if m < 2:
        return out
    arr = np.asarray(matrix, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            d = arr[i] - arr[j]
            out[f"{i},{j}"] = float(np.std(d, ddof=1) / np.sqrt(m))
    return out


def pairwise_rows(feats: dict, labels: dict, rids, *, kappa: float = 0.0) -> tuple:
    """Antisymmetrised sibling pairs: (x_i - x_j, 1) and (x_j - x_i, 0).

    `kappa` is the PLAN.md §6.4 PRE-REGISTERED NEAR-TIE FILTER: a pair is kept only
    if `|margin_i − margin_j| >= kappa · se_pair`. **`kappa=0.0` reproduces stage-0
    EXACTLY** — it drops only *exact* ties, which is what stage-0 did, i.e. it fed
    the ranker every pair whose margin difference was smaller than its own standard
    error (coin-flip labels presented as data). The filter is a TRAINING-set filter
    only; every accuracy in the free tier is graded on the UNFILTERED pair set so
    the kappa arms share one test set.
    """
    X, y, grp = [], [], []
    kappa = float(kappa)
    for rid in rids:
        f, lb = feats.get(rid), labels.get(rid)
        if f is None or lb is None or len(f) != len(lb["labels"]):
            continue
        v = lb["labels"]
        sep = lb.get("se_pairs") or {}
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                if v[i] == v[j]:
                    continue                       # a tie carries no order
                if kappa > 0.0:
                    se = sep.get(f"{i},{j}")
                    if se is not None and abs(v[i] - v[j]) < kappa * se:
                        continue                   # a coin flip carries no order
                d = np.asarray(f[i], dtype=np.float64) - np.asarray(f[j], dtype=np.float64)
                X.append(d); y.append(1 if v[i] > v[j] else 0); grp.append(lb["root_id"])
                X.append(-d); y.append(0 if v[i] > v[j] else 1); grp.append(lb["root_id"])
    if not X:
        return np.zeros((0, 1)), np.zeros(0), []
    return np.vstack(X), np.asarray(y), grp


def fit_ranker(X, y, groups, *, model: str, seed: int):
    from sklearn.linear_model import LogisticRegression            # noqa: PLC0415
    from sklearn.model_selection import GroupKFold                 # noqa: PLC0415
    from sklearn.preprocessing import StandardScaler               # noqa: PLC0415

    sc = StandardScaler(with_mean=False).fit(X)     # difference vectors are centred
    Xs = sc.transform(X)
    if model == "gbdt":
        from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: PLC0415
        clf = HistGradientBoostingClassifier(max_depth=3, max_iter=200,
                                             random_state=seed).fit(Xs, y)
        return {"scaler": sc, "clf": clf, "kind": "gbdt", "C": None}
    ng = len(set(groups))
    best, best_c = None, None
    for C in (0.003, 0.01, 0.03, 0.1, 0.3, 1.0):
        if ng >= 3:
            gkf = GroupKFold(n_splits=min(4, ng))
            acc = []
            for tr, te in gkf.split(Xs, y, groups=groups):
                m = LogisticRegression(C=C, fit_intercept=False, max_iter=2000,
                                       random_state=seed).fit(Xs[tr], y[tr])
                acc.append(float(m.score(Xs[te], y[te])))
            s = float(np.mean(acc))
        else:
            s = 0.0
        if best is None or s > best:
            best, best_c = s, C
    clf = LogisticRegression(C=best_c, fit_intercept=False, max_iter=2000,
                             random_state=seed).fit(Xs, y)
    return {"scaler": sc, "clf": clf, "kind": "pairwise-logistic", "C": best_c,
            "inner_cv_acc": best}


def score_arms(model, feats: dict, rids) -> dict:
    out = {}
    for rid in rids:
        f = feats.get(rid)
        if f is None:
            continue
        X = model["scaler"].transform(np.asarray(f, dtype=np.float64))
        if model["kind"] == "gbdt":
            # score(arm) = mean over siblings of P(arm beats sibling); rank-equivalent
            n = X.shape[0]
            s = np.zeros(n)
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    d = (X[i] - X[j]).reshape(1, -1)
                    s[i] += float(model["clf"].predict_proba(d)[0, 1])
            out[rid] = (s / max(1, X.shape[0] - 1)).tolist()
        else:
            out[rid] = (X @ model["clf"].coef_.ravel()).tolist()
    return out


def root_folds(roots, kfold: int, seed: int) -> list:
    """Partition ROOTS (never positions) into k folds. Deterministic in `seed`.

    THE LEAKAGE GUARD lives here and is asserted, not assumed: every root lands in
    exactly one fold, so a model graded on a root has never seen ANY position of
    that root — the tied plies of one game are not independent draws.
    """
    roots = sorted(set(roots))
    rng = random.Random(int(seed))
    shuffled = list(roots)
    rng.shuffle(shuffled)
    folds = [shuffled[i::int(kfold)] for i in range(int(kfold))]
    seen = [r for f in folds for r in f]
    assert len(seen) == len(roots) == len(set(seen)), "root split is not a partition"
    return folds


def cmd_train_net(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = Path(args.features)
    if args.build_features:
        fb = build_features(args)
        prev = json.loads(cache.read_text()) if cache.is_file() else None
        if prev and prev.get("rules_profile") != fb["rules_profile"]:
            merged = dict(prev)
            merged["features"].update(fb["features"])
            merged["rules_profile"] = f"{prev['rules_profile']}+{fb['rules_profile']}"
            merged["n"] = len(merged["features"])
            merged["skipped"] = (prev.get("skipped") or []) + fb["skipped"]
            fb = merged
        cache.write_text(json.dumps(fb))
        print(f"[features] {fb['n']} rids ({fb['rules_profile']}), "
              f"{len(fb['skipped'])} skipped -> {cache}")
        if args.features_only:
            return 0
    if not cache.is_file():
        raise SystemExit(f"REFUSING: no feature cache at {cache}. Run with "
                         f"--build-features (one process per --rules-profile).")
    fb = json.loads(cache.read_text())
    feats = fb["features"]
    lab = collect_labels(args)
    rids = sorted(set(feats) & set(lab["labels"]))
    if not rids:
        raise SystemExit("REFUSING: no rid has BOTH features and labels.")

    # --- the split. BY ROOT, never by position. -----------------------------
    holdout_roots = set(json.loads(Path(args.holdout_roots).read_text())["holdout_roots"])
    roots = sorted({lab["labels"][r]["root_id"] for r in rids})
    folds = root_folds(roots, args.kfold, args.split_seed)

    scores_by_rid, fold_meta = {}, []
    for k, te_roots in enumerate(folds):
        te = set(te_roots)
        tr_rids = [r for r in rids if lab["labels"][r]["root_id"] not in te]
        te_rids = [r for r in rids if lab["labels"][r]["root_id"] in te]
        # LEAKAGE GUARD, asserted not assumed.
        assert not ({lab["labels"][r]["root_id"] for r in tr_rids} & te)
        X, y, g = pairwise_rows(feats, lab["labels"], tr_rids)
        if X.shape[0] < args.min_pairs:
            fold_meta.append({"fold": k, "skipped": True, "n_pairs": int(X.shape[0])})
            continue
        model = fit_ranker(X, y, g, model=args.model, seed=args.split_seed + k)
        scores_by_rid.update(score_arms(model, feats, te_rids))
        fold_meta.append({"fold": k, "n_train_rids": len(tr_rids),
                          "n_train_roots": len(roots) - len(te),
                          "n_test_rids": len(te_rids), "n_pairs": int(X.shape[0]),
                          "kind": model["kind"], "C": model.get("C"),
                          "inner_cv_acc": model.get("inner_cv_acc")})
    meta = {
        "schema": SCHEMA, "kind": "net-scores", "generated_utc": _utc(),
        "model": args.model, "split": "k-fold BY root_id (cross-fit); every root is "
                                      "graded by a model that never saw it",
        "kfold": args.kfold, "split_seed": args.split_seed,
        "n_rids_scored": len(scores_by_rid), "n_roots": len(roots),
        "n_arm_labels": lab["n_arm_labels"], "n_shape_problems": len(lab["shape_problems"]),
        "shape_problems_sample": lab["shape_problems"][:20],
        "feature_module": FEATURE_MODULE, "n_features": len(fb["feature_order"]),
        "rules_profile": fb["rules_profile"], "folds": fold_meta,
        "design_holdout_roots_in_scored": len(
            holdout_roots & {lab["labels"][r]["root_id"] for r in scores_by_rid}),
        "caveat": NET_ASYMMETRY_CAVEAT,
    }
    (out_dir / "NET_SCORES.json").write_text(json.dumps(
        {"meta": meta, "scores_by_rid": scores_by_rid}, indent=2))
    print(json.dumps(meta, indent=2)[:2000])
    print(f"[wrote] {out_dir / 'NET_SCORES.json'}")
    return 0


def load_net_scores(args) -> dict:
    p = Path(args.net_scores or Path(args.out_dir) / "NET_SCORES.json")
    if not p.is_file():
        raise SystemExit(f"REFUSING: no net scores at {p}. Run `train-net` first.")
    return json.loads(p.read_text())


# =========================================================================== #
# 4b. STAGE-1 FREE TIER — P1 / P2 / P3 (PLAN.md §9.2)                          #
# =========================================================================== #
#
# ⚠️ ZERO WORKER-HOURS. Every number in this section is computed from records
# ALREADY ON DISK. No leg is scored, no position is generated, no graded position
# is bought. The read rule for P3 is pre-registered in
# `measurement/tienet_stage1_plan_20260823/P3_RULE.md`, committed BEFORE the first
# fit — that commit, not this code, is what makes P3 a test rather than a story.

FREE_TIER_PLAN = "measurement/tienet_stage1_plan_20260823/PLAN.md"
P3_RULE_DOC = "measurement/tienet_stage1_plan_20260823/P3_RULE.md"

#: PLAN.md §9.2 P3 — the boundary between "the features cannot rank even a perfect
#: target" and "the features carry real signal". Declared, not negotiable.
P3_ALIVE_BAR = 0.55
#: PLAN.md §7.1 — the committed fraction of `arb` a tie-net must reproduce.
GATE_FRACTION = 0.50

R1_COLLINEARITY_NOTE = (
    "R1 COLLINEARITY (PLAN.md §5): for a LINEAR pairwise ranker on x_a - x_b the "
    "afterstate-minus-ROOT diff features CANCEL EXACTLY — (x_a-x_r)-(x_b-x_r) = "
    "x_a-x_b. R1 is perfectly collinear with R0 in a linear model and adds "
    "literally nothing; it is a rung ONLY paired with M2/M3.")

FREE_TIER_PRIOR = (
    "PRIOR, stated in PLAN.md §8 before any number was bought: ~10-15% that any "
    "stage-1 tier clears §7.1. The free tier is designed to be worth running AT "
    "that prior because its primary deliverable is a POWERED KILL, not a win.")


def pair_agreement(pred, target, *, target_ties="drop"):
    """(agree, n_pairs) over unordered sibling pairs of one position.

    Mirrors `pairwise_rows`' convention exactly so the numbers are commensurable:
    a pair whose TARGET values are equal carries no order and is not counted.

    ⚠️ A pair on which the PREDICTOR ties scores 0.5, not 1.0 — at pick time it is
    a coin flip, and scoring it as a win would flatter the predictor. This matters:
    a degenerate all-constant model would otherwise read 1.000.
    """
    n = len(target)
    agree, tot = 0.0, 0
    for i in range(n):
        for j in range(i + 1, n):
            if target[i] == target[j]:
                continue
            tot += 1
            d = pred[i] - pred[j]
            if d == 0:
                agree += 0.5
            elif (d > 0) == (target[i] > target[j]):
                agree += 1.0
    return agree, tot


def _means(matrix, idx=None):
    if idx is None:
        return [float(np.mean(r)) for r in matrix]
    return [float(AT._sub_mean(r, idx)) for r in matrix]


def graded_matrices(inp: dict) -> dict:
    """rid -> the two banked value matrices for the ACCEPTED graded corpus.

    Built from `analyze_tiearb.build_positions`' own accepted rows and its own
    `arm_order`, so this cannot silently re-scope the 733.
    """
    out = {}
    for row in inp["rows"]:
        rid = row["rid"]
        out[rid] = {
            "if": matrix_for(inp["if_by_rid"][rid], row["arm_order"]),
            "arb": matrix_for(inp["arb_by_rid"][rid], row["arm_order"]),
            "arm_order": row["arm_order"], "root_id": row["root_id"],
            "champ_pos": row["champ_pos"], "m": row["m"],
            "scale_all": row["scale_all"], "stratum": row["stratum"],
        }
    return out


# --------------------------------------------------------------------------- #
# P1 — calibrate rank accuracy -> capture                                       #
# --------------------------------------------------------------------------- #
def p1_calibration(inp: dict, mats: dict, seed: int) -> dict:
    """PLAN.md §9.2 P1. The ARBITER's own sibling-rank accuracy against the
    `clair-puct` ORACLE order, on the graded 733 — both orderings are banked.

    Without this the whole accuracy axis of the label sweep is uninterpretable:
    it is what converts "rank accuracy 0.53" into "capture X pts/tied ply".

    Two accuracies are reported and they are NOT interchangeable:

    * ``full`` — the arbiter's full-M mean order vs the oracle's full-M mean
      order. This is the estimand the NET is graded on (its pick is
      world-independent), so it is the one to read a net accuracy against.
    * ``crossfit`` — the arbiter's order from the SELECTION half vs the oracle's
      order on the disjoint EVALUATION half, symmetrised over the two parity
      folds. This is the estimand `arb = +0.2065` was actually priced on, so it is
      the honest anchor for the accuracy->capture map. It is LOWER than `full` by
      construction (half the worlds, plus the winner's-curse control) — that gap
      is the NET FOLD ASYMMETRY caveat showing up as a number.
    """
    acc = {"full": [0.0, 0], "crossfit": [0.0, 0]}
    top1 = {"full": [0, 0], "crossfit": [0, 0]}
    per_arms = defaultdict(lambda: [0.0, 0])
    for row in inp["rows"]:
        d = mats[row["rid"]]
        mi, ma = d["if"], d["arb"]
        ora_full, arb_full = _means(mi), _means(ma)
        a, t = pair_agreement(arb_full, ora_full)
        acc["full"][0] += a; acc["full"][1] += t
        per_arms[len(ora_full)][0] += a; per_arms[len(ora_full)][1] += t
        if t:
            top1["full"][1] += 1
            top1["full"][0] += int(max(range(len(arb_full)),
                                       key=lambda i: (arb_full[i], -i))
                                   == max(range(len(ora_full)),
                                          key=lambda i: (ora_full[i], -i)))
        folds = (AT.parity_indices(d["m"], base=ATB.PARITY_BASE, swap=False),
                 AT.parity_indices(d["m"], base=ATB.PARITY_BASE, swap=True))
        for sel, eva in folds:
            pa, ta = pair_agreement(_means(ma, sel), _means(mi, eva))
            acc["crossfit"][0] += pa; acc["crossfit"][1] += ta
            if ta:
                top1["crossfit"][1] += 1
                p, q = _means(ma, sel), _means(mi, eva)
                top1["crossfit"][0] += int(
                    max(range(len(p)), key=lambda i: (p[i], -i))
                    == max(range(len(q)), key=lambda i: (q[i], -i)))

    rows = inp["rows"]
    cap = {k: AT.aggregate(rows, k, "scale_all", seed=seed)
           for k in ("arb", "ora", "rnd")}
    a_cf = acc["crossfit"][0] / acc["crossfit"][1]
    a_full = acc["full"][0] / acc["full"][1]

    # The accuracy -> capture map. Two empirical anchors bracket the arbiter:
    #   (0.5, rnd)  a coin-flip ranker picks a uniformly random arm, and
    #   (a_cf, arb) the arbiter's realized accuracy at its realized capture.
    # Linear interpolation between them is the honest local calibration; the
    # (1.0, ora) anchor is reported as the far end but NOT used for the slope,
    # because the map is not linear all the way to a perfect ranker.
    rnd_c, arb_c, ora_c = cap["rnd"]["mean"], cap["arb"]["mean"], cap["ora"]["mean"]
    slope = (arb_c - rnd_c) / (a_cf - 0.5) if a_cf != 0.5 else None

    def acc_for(c):
        return None if not slope else 0.5 + (c - rnd_c) / slope

    def cap_for(a):
        return None if not slope else rnd_c + (a - 0.5) * slope

    stage0_acc = 0.5211                      # GRADE_net.json inner-CV mean
    return {
        "what": "PLAN.md §9.2 P1 — arbiter sibling-rank accuracy vs the clair-puct "
                "oracle order on the graded 733; calibrates accuracy -> capture.",
        "n_positions": len(rows), "n_roots": cap["arb"]["n_roots"],
        "acc_full": a_full, "acc_full_pairs": acc["full"][1],
        "acc_crossfit": a_cf, "acc_crossfit_pairs": acc["crossfit"][1],
        "top1_full": top1["full"][0] / max(1, top1["full"][1]),
        "top1_crossfit": top1["crossfit"][0] / max(1, top1["crossfit"][1]),
        "acc_by_n_arms": {str(k): {"acc": v[0] / v[1], "pairs": v[1]}
                          for k, v in sorted(per_arms.items()) if v[1]},
        "capture": {k: {"mean": v["mean"], "se_cluster": v["se_cluster"],
                        "z": v["z"], "n": v["n"], "n_roots": v["n_roots"]}
                    for k, v in cap.items()},
        "calibration": {
            "anchors": [[0.5, rnd_c], [a_cf, arb_c], [1.0, ora_c]],
            "slope_pts_per_acc": slope,
            "acc_needed_for_half_arb": acc_for(GATE_FRACTION * arb_c),
            "acc_needed_for_full_arb": acc_for(arb_c),
            "predicted_capture_at_stage0_acc": cap_for(stage0_acc),
            "stage0_measured_capture": -0.04510,
            "stage0_inner_cv_acc": stage0_acc,
            "note": "Slope is fitted on (0.5, rnd) and (acc_crossfit, arb) ONLY. "
                    "The (1.0, ora) anchor is printed for scale and is NOT on the "
                    "line — a perfect ranker is not reachable by extrapolating a "
                    "local slope. `predicted_capture_at_stage0_acc` is what the "
                    "calibration says stage-0's 0.5211 should have been worth; "
                    "compare it to the MEASURED -0.0451 before trusting either.",
        },
        "asymmetry_caveat": NET_ASYMMETRY_CAVEAT,
    }


# --------------------------------------------------------------------------- #
# P2 — label-noise audit (the B-vs-n decision)                                  #
# --------------------------------------------------------------------------- #
def p2_label_noise(mats: dict, kappas=(0.5, 1.0, 2.0)) -> dict:
    """PLAN.md §9.2 P2. Distribution of `|Δ margin| / se_pair` over the graded
    corpus's sibling pairs, per judge.

    The decision it buys: stage-0 dropped only EXACT ties, so it fed the ranker
    every pair whose margin difference was smaller than its own standard error —
    coin-flip labels presented as data. If a large fraction of pairs sit below
    1 `se_pair`, the EFFECTIVE stage-0 label count was far below its nominal
    count, and route (b) should buy **B** (deeper labels, `se ∝ 1/√B`) rather than
    **n** (more plies) at the same worker-seconds.
    """
    out = {}
    for judge, name in (("arb", "tier1-greedy (the TRAINING label of record)"),
                        ("if", "clair-puct (the P3 noiseless-target arm)")):
        ts, exact = [], 0
        for d in mats.values():
            mat = d[judge]
            v = _means(mat)
            sep = se_pairs_for(mat)
            n = len(v)
            for i in range(n):
                for j in range(i + 1, n):
                    if v[i] == v[j]:
                        exact += 1
                        continue
                    se = sep.get(f"{i},{j}")
                    if not se:
                        continue
                    ts.append(abs(v[i] - v[j]) / se)
        arr = np.asarray(ts, dtype=np.float64)
        n_pairs = int(arr.size)
        out[judge] = {
            "judge": name, "n_pairs_non_exact_tie": n_pairs,
            "n_exact_ties_dropped_by_stage0": exact,
            "t_quantiles": {q: float(np.percentile(arr, q))
                            for q in (5, 10, 25, 50, 75, 90, 95)} if n_pairs else {},
            "t_mean": float(arr.mean()) if n_pairs else None,
            "frac_below": {str(k): float((arr < k).mean()) for k in kappas},
            "effective_pairs_at_kappa": {
                str(k): int((arr >= k).sum()) for k in kappas},
            "kappa0_pairs": n_pairs,
        }
    return {
        "what": "PLAN.md §9.2 P2 — label-noise audit; the B-vs-n decision.",
        "se_pair_definition": "CRN-PAIRED: sd over worlds of (margin_i - margin_j) "
                              "/ sqrt(m). Smaller than the unpaired sd*sqrt(2)/sqrt(m) "
                              "wherever the CRN pairing works, so it declares FEWER "
                              "pairs to be coin flips — the conservative choice.",
        "by_judge": out,
    }


# --------------------------------------------------------------------------- #
# P3 — feature informativeness against a NOISELESS target                       #
# --------------------------------------------------------------------------- #
def crossfit_ranker(feats: dict, labels: dict, rids, *, kfold: int, split_seed: int,
                    model: str, min_pairs: int, kappa: float = 0.0) -> dict:
    """`cmd_train_net`'s cross-fit, factored out so P3 and the label sweep run the
    IDENTICAL estimator with only the label source / pool changed.

    Returns the held-out scores, the per-fold witness, and BOTH accuracies:

    * ``inner_cv_acc_mean`` — the statistic stage-0 published (0.5211). It is a
      TRAINING-ADJACENT number (the inner root-grouped CV inside the training
      folds), and it is the one `P3_RULE.md` pre-registered the branch on, purely
      so the comparison to stage-0 is apples-to-apples.
    * ``oof_acc`` — the honest out-of-fold accuracy: every root scored by a model
      that never saw it, graded on the UNFILTERED pair set. Reported beside, never
      substituted for, the branch statistic.
    """
    roots = sorted({labels[r]["root_id"] for r in rids})
    folds = root_folds(roots, kfold, split_seed)
    scores_by_rid, fold_meta = {}, []
    for k, te_roots in enumerate(folds):
        te = set(te_roots)
        tr_rids = [r for r in rids if labels[r]["root_id"] not in te]
        te_rids = [r for r in rids if labels[r]["root_id"] in te]
        assert not ({labels[r]["root_id"] for r in tr_rids} & te), "root leak"
        X, y, g = pairwise_rows(feats, labels, tr_rids, kappa=kappa)
        if X.shape[0] < min_pairs:
            fold_meta.append({"fold": k, "skipped": True, "n_pairs": int(X.shape[0])})
            continue
        mdl = fit_ranker(X, y, g, model=model, seed=split_seed + k)
        scores_by_rid.update(score_arms(mdl, feats, te_rids))
        fold_meta.append({"fold": k, "n_train_rids": len(tr_rids),
                          "n_train_roots": len(roots) - len(te),
                          "n_test_rids": len(te_rids), "n_pairs": int(X.shape[0]),
                          "kind": mdl["kind"], "C": mdl.get("C"),
                          "inner_cv_acc": mdl.get("inner_cv_acc")})
    ag, tot, npos = 0.0, 0, 0
    for rid, s in scores_by_rid.items():
        lb = labels.get(rid)
        if lb is None or len(s) != len(lb["labels"]):
            continue
        a, t = pair_agreement(s, lb["labels"])
        ag += a; tot += t; npos += 1
    inner = [f.get("inner_cv_acc") for f in fold_meta if f.get("inner_cv_acc") is not None]
    return {
        "scores_by_rid": scores_by_rid, "folds": fold_meta,
        "n_rids": len(rids), "n_roots": len(roots),
        "n_train_pairs_total": sum(f.get("n_pairs", 0) for f in fold_meta),
        "inner_cv_acc_mean": (float(np.mean(inner)) if inner else None),
        "inner_cv_acc_folds": inner,
        "oof_acc": (ag / tot) if tot else None, "oof_pairs": tot,
        "oof_positions": npos, "model": model, "kappa": kappa,
        "kfold": kfold, "split_seed": split_seed,
    }


def p3_feature_informativeness(inp: dict, mats: dict, feats: dict, args) -> dict:
    """PLAN.md §9.2 P3 — THE DECISIVE PRE-FLIGHT. Read rule: `P3_RULE.md`.

    Same 84 features, same estimator, same 5-fold root cross-fit, same seed, same
    label COUNT — only the label NOISE is removed, by swapping the arbiter's noisy
    CRN margins for the `clair-puct` oracle's own arm order (banked for all 733).

    ⚠️ RAIL (PLAN.md §9.2, verbatim): P3 trains against the same oracle quantity
    used to grade. It is a DIAGNOSTIC OF FEATURE INFORMATIVENESS ONLY and MUST
    NEVER be reported as capture. No `arb`, no `F`, no capture CI comes out of it.
    """
    arms_index = json.loads(Path(args.plan_dir, "ARMS.json").read_text())
    arb = labels_from_records(inp["arb_by_rid"], arms_index)
    ora = labels_from_records(inp["if_by_rid"], arms_index)
    # P3 is scoped to the ACCEPTED graded corpus and to rids the oracle arm also
    # covers, so the two arms differ in label NOISE and in nothing else.
    keep = sorted(set(feats) & set(arb["labels"]) & set(ora["labels"]) & set(mats))
    same_order = [r for r in keep
                  if arb["labels"][r]["arm_order"] == ora["labels"][r]["arm_order"]]
    arms = {
        "arbiter": crossfit_ranker(feats, arb["labels"], same_order,
                                   kfold=args.kfold, split_seed=args.split_seed,
                                   model=args.model, min_pairs=args.min_pairs),
        "oracle": crossfit_ranker(feats, ora["labels"], same_order,
                                  kfold=args.kfold, split_seed=args.split_seed,
                                  model=args.model, min_pairs=args.min_pairs),
    }
    for a in arms.values():
        a.pop("scores_by_rid", None)
    published = [0.5285, 0.5251, 0.5212, 0.5229, 0.5080]
    got = arms["arbiter"]["inner_cv_acc_folds"]
    ctrl_ok = (len(got) == len(published)
               and all(abs(a - b) <= 5e-4 for a, b in zip(sorted(got), sorted(published))))
    p3 = arms["oracle"]["inner_cv_acc_mean"]
    branch = "ALIVE" if (p3 is not None and p3 >= P3_ALIVE_BAR) else "DEAD"
    return {
        "what": "PLAN.md §9.2 P3 — feature informativeness against a NOISELESS "
                "target. Read rule pre-registered at " + P3_RULE_DOC + ".",
        "n_rids": len(same_order), "n_roots": arms["oracle"]["n_roots"],
        "arms": arms,
        "control": {
            "published_stage0_inner_cv_folds": published,
            "reproduced": got, "ok": bool(ctrl_ok), "tol": 5e-4,
            "why": "the arbiter-label arm re-runs stage-0's own fit; if it does not "
                   "reproduce GRADE_net.json's per-fold inner-CV accuracies, P3 is "
                   "VOID and no branch fires.",
        },
        "p3_acc": p3, "alive_bar": P3_ALIVE_BAR, "branch": branch,
        "branch_meaning": (
            "DEAD: the 84 features cannot rank siblings even against a perfect, "
            "noiseless target => the label routes are ARITHMETICALLY dead; run the "
            "free A1-A3 sweep to convert the §7.2 kill into a LABEL-SCALED kill, "
            "then STOP."
            if branch == "DEAD" else
            "ALIVE: the features carry real signal => proceed to the full free "
            "tier; P2 then decides depth-vs-breadth for any future funded route."),
        "rail": "DIAGNOSTIC ONLY — must never be reported as capture.",
    }


def cmd_preflight(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    inp = load_grade_inputs(args)
    kg = require_knowngood(inp, args.boot_seed, out_dir)     # ⛔ THE GATE, always first
    mats = graded_matrices(inp)
    parts = [p.strip().lower() for p in str(args.parts).split(",") if p.strip()]

    rep = {"schema": SCHEMA, "mode": "preflight", "generated_utc": _utc(),
           "git": _git_rev(), "knowngood": kg, "plan": FREE_TIER_PLAN,
           "read_rule": P3_RULE_DOC, "parts": parts,
           "n_positions": len(inp["rows"]),
           "governance": "0 games, no band, no results.csv row, no claim id, no "
                         "RUN_LIVE.json. ZERO worker-hours: every number is computed "
                         "from records already on disk.",
           "ceiling_caveat": CEILING_CAVEAT,
           "net_asymmetry_caveat": NET_ASYMMETRY_CAVEAT,
           "r1_collinearity_note": R1_COLLINEARITY_NOTE,
           "prior": FREE_TIER_PRIOR}

    if "p1" in parts:
        rep["P1"] = p1_calibration(inp, mats, args.boot_seed)
        c = rep["P1"]
        print(f"\n=== P1 — arbiter rank accuracy vs the clair-puct oracle order ===")
        print(f"  acc (full-M, the NET's estimand)      {c['acc_full']:.4f}  "
              f"over {c['acc_full_pairs']} pairs")
        print(f"  acc (cross-fit, arb=+0.2065's own)    {c['acc_crossfit']:.4f}  "
              f"over {c['acc_crossfit_pairs']} pairs")
        print(f"  top-1 agreement  full {c['top1_full']:.4f}   "
              f"cross-fit {c['top1_crossfit']:.4f}")
        cal = c["calibration"]
        print(f"  capture anchors: rnd {c['capture']['rnd']['mean']:+.5f}  "
              f"arb {c['capture']['arb']['mean']:+.5f}  "
              f"ora {c['capture']['ora']['mean']:+.5f}")
        print(f"  slope {cal['slope_pts_per_acc']:.4f} pts per unit accuracy  =>  "
              f"acc needed for 0.50*arb = {cal['acc_needed_for_half_arb']:.4f}")
        print(f"  calibration says stage-0's acc 0.5211 is worth "
              f"{cal['predicted_capture_at_stage0_acc']:+.5f}; MEASURED "
              f"{cal['stage0_measured_capture']:+.5f}")

    if "p2" in parts:
        rep["P2"] = p2_label_noise(mats)
        print(f"\n=== P2 — label-noise audit (|Δ margin| / se_pair) ===")
        for j, b in rep["P2"]["by_judge"].items():
            q = b["t_quantiles"]
            print(f"  [{j}] {b['judge']}")
            print(f"        pairs {b['n_pairs_non_exact_tie']}  exact ties dropped "
                  f"{b['n_exact_ties_dropped_by_stage0']}  median t {q.get(50, 0):.3f}")
            print(f"        frac below 0.5 se {b['frac_below']['0.5']:.3f}   "
                  f"below 1 se {b['frac_below']['1.0']:.3f}   "
                  f"below 2 se {b['frac_below']['2.0']:.3f}")
            print(f"        effective pairs  k=0.5 {b['effective_pairs_at_kappa']['0.5']}"
                  f"   k=1.0 {b['effective_pairs_at_kappa']['1.0']}"
                  f"   (k=0 -> {b['kappa0_pairs']})")

    if "p3" in parts:
        fb = json.loads(Path(args.features).read_text())
        rep["P3"] = p3_feature_informativeness(inp, mats, fb["features"], args)
        p3 = rep["P3"]
        print(f"\n=== P3 — ⭐ THE GATE: feature informativeness vs a NOISELESS target ===")
        print(f"  read rule (pre-registered, committed before this fit): {P3_RULE_DOC}")
        print(f"  control — stage-0 arbiter-label arm reproduces: "
              f"{'PASS ✅' if p3['control']['ok'] else 'FAIL ⛔'}")
        print(f"      published {['%.4f' % x for x in p3['control']['published_stage0_inner_cv_folds']]}")
        print(f"      reproduced {['%.4f' % x for x in p3['control']['reproduced']]}")
        for name, a in p3["arms"].items():
            print(f"  [{name:<7}] inner-CV acc {a['inner_cv_acc_mean']:.4f}  "
                  f"folds {['%.4f' % x for x in a['inner_cv_acc_folds']]}")
            print(f"            OOF acc {a['oof_acc']:.4f} over {a['oof_pairs']} "
                  f"held-out pairs / {a['oof_positions']} positions   "
                  f"train pairs {a['n_train_pairs_total']}")
        print(f"\n  ⭐ p3_acc = {p3['p3_acc']:.4f}   bar = {P3_ALIVE_BAR}   "
              f"=> BRANCH: {p3['branch']}")
        print(f"  {p3['branch_meaning']}")
        print(f"  ⚠️ {p3['rail']}")

    (out_dir / "PREFLIGHT.json").write_text(json.dumps(rep, indent=2, default=str))
    print(f"\n⚠️  {CEILING_CAVEAT}")
    print(f"\n⚠️  {R1_COLLINEARITY_NOTE}")
    print(f"\n[wrote] {out_dir / 'PREFLIGHT.json'}")
    return 0


# =========================================================================== #
# 4c. STAGE-1 FREE TIER — A1/A2/A3 THE LABEL SWEEP (PLAN.md §3.1, §6.3, §9.3)  #
# =========================================================================== #
#
# The "L" design's LABEL ARM: features fixed at R0, model fixed at M0, the pair
# pool swept T0 -> T1 -> T2 -> T3 for ZERO compute by unifying the banked
# auxiliary corpora. Its primary readout is RANK ACCURACY (PLAN.md §9.1: capture's
# se is 0.0552 FOREVER at n=733, but accuracy's error bar shrinks with labels);
# capture is a diagnostic at every rung and the headline at the top rung only
# (§7.4's anti-shopping rail).

#: P1's realized calibration, read off PREFLIGHT.json and reused so the sweep can
#: print "what capture SHOULD this accuracy be worth" beside what it measured.
#: Anchors: (0.5, rnd = +0.015115) and (acc_crossfit = 0.537902, arb = +0.206459).
P1_RND_CAPTURE = 0.015115114814570356
P1_SLOPE = 5.048383165777653

AUX_TRAIN = "aux-train"
CROSS_FIT = "cross-fit"

AUX_TRAIN_NOTE = (
    "AUX-TRAIN / GRADE-733 (PLAN.md §6.3): trained ONLY on auxiliary corpora, "
    "graded on all 733. The auxiliaries are disjoint seed BANDS with 0 rid overlap "
    "(G-DISJOINT, asserted in code), so there is no leakage channel, the cross-fit "
    "disappears and the full 733 is a pure out-of-sample holdout — no 1/5 shrinkage "
    "of the graded n, and the winner's-curse control strengthens from 'a root split' "
    "to 'a different band entirely'. ⚠️ This makes the TRAINING set out-of-band; the "
    "GRADING is entirely within the graded corpus's own band, so CLAUDE.md's "
    "'inflate sigma 1.5-2x on cross-band CONTRASTS' does NOT bite the error bar. "
    "What bites is DISTRIBUTION SHIFT IN THE MODEL — a bias risk on the estimate, "
    "not a variance risk on the interval. The stage-0 root cross-fit is retained "
    "beside it as the conservative consistency check; if the two disagree by more "
    "than ~1 sigma the shift is doing real work and the CROSS-FIT is the headline.")


def _repo_path(p) -> Path:
    """Registry paths are repo-relative by convention; absolute ones pass through."""
    q = Path(p)
    return q if q.is_absolute() else (REPO / q)


def load_corpus_pool(name: str, spec: dict) -> dict:
    """One auxiliary corpus -> its labels + features, through the SAME shape gates.

    `allow_m` / `subset_worlds` are the PLAN.md §3.1 explicit `m=128` waiver; they
    default to the stage-0 refusal. Nothing is coerced silently.
    """
    by_rid, _present, _not_ok, _roots = ATB.merge_arb_records(list(spec["records"]))
    arms_index = json.loads((_repo_path(spec["plan_dir"]) / "ARMS.json").read_text())
    lab = labels_from_records(
        by_rid, arms_index,
        allow_m=tuple(spec.get("allow_m") or (None,)),
        subset_worlds=int(spec.get("subset_worlds") or 0))
    fb = json.loads(_repo_path(spec["features"]).read_text())
    feats = fb["features"]
    rids = sorted(set(feats) & set(lab["labels"]))
    labels = {r: lab["labels"][r] for r in rids}
    pairs = sum(sum(1 for i in range(len(v["labels"]))
                    for j in range(i + 1, len(v["labels"]))
                    if v["labels"][i] != v["labels"][j]) for v in labels.values())
    return {
        "name": name, "labels": labels, "feats": {r: feats[r] for r in rids},
        "meta": {
            "name": name, "tier": spec.get("tier"), "plan_dir": spec["plan_dir"],
            "records": list(spec["records"]), "features_cache": spec["features"],
            "rules_profiles": fb.get("rules_profile"),
            "allow_m": spec.get("allow_m"), "subset_worlds": spec.get("subset_worlds"),
            "n_rids": len(rids), "n_roots": len({v["root_id"] for v in labels.values()}),
            "n_arm_labels": sum(len(v["labels"]) for v in labels.values()),
            "n_pairs_non_tied": pairs,
            "n_worlds_subset": sum(1 for v in labels.values() if v.get("worlds_subset")),
            "n_shape_problems": len(lab["shape_problems"]),
            "shape_problems_sample": lab["shape_problems"][:10],
            "n_no_features": len(set(lab["labels"]) - set(feats)),
            "declared_shift": spec.get("declared_shift"),
            "arm_count_hist": _hist(len(v["labels"]) for v in labels.values()),
        },
    }


def _hist(it) -> dict:
    h = defaultdict(int)
    for x in it:
        h[int(x)] += 1
    return {str(k): v for k, v in sorted(h.items())}


def assert_disjoint(graded_labels: dict, pools: list) -> dict:
    """⛔ G-DISJOINT, THE LOAD-BEARING GATE for AUX-TRAIN/GRADE-733.

    If any auxiliary rid or root also appears in the graded corpus, the 733 is NOT
    a pure holdout and the whole design collapses into a leak. This REFUSES rather
    than reports — a silent overlap would make every accuracy in the sweep a lie.
    """
    g_rids = set(graded_labels)
    g_roots = {v["root_id"] for v in graded_labels.values()}
    w = {"graded_rids": len(g_rids), "graded_roots": len(g_roots), "by_corpus": {}}
    for p in pools:
        rid_ov = sorted(g_rids & set(p["labels"]))
        root_ov = sorted(g_roots & {v["root_id"] for v in p["labels"].values()})
        w["by_corpus"][p["name"]] = {"rid_overlap": len(rid_ov),
                                     "root_overlap": len(root_ov),
                                     "examples": (rid_ov[:5] + root_ov[:5])}
        if rid_ov or root_ov:
            raise SystemExit(
                f"⛔ G-DISJOINT FAILED for {p['name']}: {len(rid_ov)} rid / "
                f"{len(root_ov)} root overlap with the graded 733 (e.g. "
                f"{(rid_ov[:3] + root_ov[:3])}). AUX-TRAIN/GRADE-733 requires ZERO "
                f"overlap — the 733 would not be a holdout. REFUSING.")
    return w


def acc_bootstrap_se(per_root: dict, seed: int, reps: int = 2000) -> dict:
    """Root-CLUSTERED bootstrap se on a pair accuracy.

    PLAN.md §9.1 prices the accuracy axis with an assumed cluster design-effect of
    ~3. This measures it instead: resample ROOTS with replacement, recompute
    agree/total inside each replicate. `deff` is the realized ratio to the nominal
    sqrt(0.25/pairs), reported so the plan's assumption can be checked rather than
    inherited.
    """
    roots = sorted(per_root)
    if not roots:
        return {}
    ag = np.asarray([per_root[r][0] for r in roots], dtype=np.float64)
    tot = np.asarray([per_root[r][1] for r in roots], dtype=np.float64)
    n_pairs = float(tot.sum())
    if n_pairs <= 0:
        return {}
    rng = np.random.default_rng(int(seed))
    idx = rng.integers(0, len(roots), size=(int(reps), len(roots)))
    num, den = ag[idx].sum(axis=1), tot[idx].sum(axis=1)
    ok = den > 0
    draws = num[ok] / den[ok]
    se = float(draws.std(ddof=1))
    nominal = float(np.sqrt(0.25 / n_pairs))
    return {"acc": float(ag.sum() / n_pairs), "n_pairs": int(n_pairs),
            "n_roots": len(roots), "se_boot_cluster": se,
            "se_nominal": nominal, "deff": (se / nominal if nominal else None),
            "ci95": [float(np.percentile(draws, 2.5)),
                     float(np.percentile(draws, 97.5))], "reps": int(reps)}


def grade_scores_on_733(scores: dict, inp: dict, graded_labels: dict,
                        oracle_labels: dict, boot_seed: int) -> dict:
    """One scored arm set -> rank accuracy against BOTH targets, plus capture.

    ⚠️ THE TWO ACCURACIES ARE NOT INTERCHANGEABLE and conflating them is the single
    easiest way to misread this whole sweep:

    * ``rank_accuracy`` (vs the ARBITER's CRN margins) is the training objective's
      own test statistic — "did the net learn what it was taught". It is the number
      commensurable with stage-0's published 0.5211 and with §7.2's bar.
    * ``rank_accuracy_oracle`` (vs the `clair-puct` ORACLE order) is "did the net
      learn the TRUTH". **This is the one P1's accuracy->capture calibration is
      keyed to**, because capture is priced by the oracle. Comparing the net's
      arbiter-target accuracy to P1's 0.5379 would be comparing two different
      quantities and would license a conclusion the data does not support.

    Both are graded on the UNFILTERED pair set so every kappa arm shares one test
    set. Capture goes through `price_picks` + `aggregate_picker`, unchanged.
    """
    def _acc(target):
        per_root = defaultdict(lambda: [0.0, 0])
        for rid, s in scores.items():
            lb = target.get(rid)
            if lb is None or len(s) != len(lb["labels"]):
                continue
            a, t = pair_agreement(s, lb["labels"])
            per_root[lb["root_id"]][0] += a
            per_root[lb["root_id"]][1] += t
        pr = {k: (float(v[0]), int(v[1])) for k, v in per_root.items()}
        return acc_bootstrap_se(pr, boot_seed), {k: list(v) for k, v in pr.items()}

    acc_arb, pr_arb = _acc(graded_labels)
    acc_ora, pr_ora = _acc(oracle_labels)
    priced = price_picks(inp["rows"], inp["if_by_rid"], picker_net(scores))
    block = aggregate_picker(priced, inp["rows"], boot_seed)
    return {"rank_accuracy": acc_arb, "rank_accuracy_oracle": acc_ora,
            "capture": block, "n_scored_rids": len(scores),
            "per_root_acc": pr_arb, "per_root_acc_oracle": pr_ora}


def paired_acc_contrast(a: dict, b: dict, seed: int, reps: int = 4000,
                        key: str = "per_root_acc",
                        acc_key: str = "rank_accuracy") -> dict:
    """acc(a) − acc(b) with the SAME resampled roots in every replicate.

    ⚠️ Load-bearing: every cell of the label sweep is graded on the IDENTICAL 2,458
    pairs of the graded 733, so the two accuracies are strongly positively
    correlated. Treating them as independent (adding the marginal se's in
    quadrature) OVERSTATES the error on their difference — i.e. it would understate
    a real trend. The paired bootstrap is the correct instrument and is what the
    trend claim is read on.
    """
    pa, pb = a.get(key) or {}, b.get(key) or {}
    roots = sorted(set(pa) & set(pb))
    if not roots:
        return {}
    A = np.asarray([pa[r] for r in roots], dtype=np.float64)
    B = np.asarray([pb[r] for r in roots], dtype=np.float64)
    rng = np.random.default_rng(int(seed))
    idx = rng.integers(0, len(roots), size=(int(reps), len(roots)))
    da = A[:, 0][idx].sum(axis=1) / A[:, 1][idx].sum(axis=1)
    db = B[:, 0][idx].sum(axis=1) / B[:, 1][idx].sum(axis=1)
    d = da - db
    point = float(A[:, 0].sum() / A[:, 1].sum() - B[:, 0].sum() / B[:, 1].sum())
    se = float(d.std(ddof=1))
    return {"target": ("oracle" if "oracle" in key else "arbiter"),
            "delta_acc": point, "se_paired": se,
            "z": (point / se) if se else None,
            "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
            "n_roots": len(roots), "reps": int(reps),
            "se_unpaired_quadrature": float(np.sqrt(
                (a[acc_key]["se_boot_cluster"] ** 2)
                + (b[acc_key]["se_boot_cluster"] ** 2)))}


def run_label_tier(inp: dict, graded_feats: dict, graded_labels: dict,
                   graded_rids: list, pools: list, *, design: str, model: str,
                   kappa: float, args, oracle_labels: dict) -> dict:
    """One cell of the label arm: a pair pool x a split design -> scores on the 733."""
    feats = dict(graded_feats)
    labels = dict(graded_labels)
    for p in pools:
        feats.update(p["feats"])
        labels.update(p["labels"])
    aux_rids = [r for p in pools for r in sorted(p["labels"])]

    if design == AUX_TRAIN:
        if not aux_rids:
            return {"design": design, "skipped": "no auxiliary corpus at this tier"}
        X, y, g = pairwise_rows(feats, labels, aux_rids, kappa=kappa)
        mdl = fit_ranker(X, y, g, model=model, seed=args.split_seed)
        scores = score_arms(mdl, graded_feats, graded_rids)
        fitmeta = {"n_train_pairs_rows": int(X.shape[0]),
                   "n_train_rids": len(aux_rids),
                   "n_train_roots": len(set(g)), "C": mdl.get("C"),
                   "kind": mdl["kind"], "inner_cv_acc": mdl.get("inner_cv_acc")}
    else:
        roots = sorted({graded_labels[r]["root_id"] for r in graded_rids})
        folds = root_folds(roots, args.kfold, args.split_seed)
        scores, fm = {}, []
        for k, te_roots in enumerate(folds):
            te = set(te_roots)
            tr = [r for r in graded_rids if graded_labels[r]["root_id"] not in te]
            teg = [r for r in graded_rids if graded_labels[r]["root_id"] in te]
            assert not ({graded_labels[r]["root_id"] for r in tr} & te), "root leak"
            X, y, g = pairwise_rows(feats, labels, tr + aux_rids, kappa=kappa)
            mdl = fit_ranker(X, y, g, model=model, seed=args.split_seed + k)
            scores.update(score_arms(mdl, graded_feats, teg))
            fm.append({"fold": k, "n_pairs_rows": int(X.shape[0]), "C": mdl.get("C"),
                       "inner_cv_acc": mdl.get("inner_cv_acc")})
        inner = [f["inner_cv_acc"] for f in fm if f.get("inner_cv_acc") is not None]
        fitmeta = {"folds": fm, "n_train_pairs_rows": sum(f["n_pairs_rows"] for f in fm),
                   "inner_cv_acc": (float(np.mean(inner)) if inner else None),
                   "kind": model}
    out = grade_scores_on_733(scores, inp, graded_labels, oracle_labels,
                              args.boot_seed)
    out.update({"design": design, "model": model, "kappa": kappa, "fit": fitmeta,
                "corpora": [p["name"] for p in pools]})
    return out


def cmd_sweep(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    inp = load_grade_inputs(args)
    kg = require_knowngood(inp, args.boot_seed, out_dir)     # ⛔ THE GATE, always first

    arms_index = json.loads(Path(args.plan_dir, "ARMS.json").read_text())
    graded_labels = labels_from_records(inp["arb_by_rid"], arms_index)["labels"]
    #: the clair-puct ORACLE arm order on the same graded corpus. Used ONLY as a
    #: second grading target for rank accuracy — never as a training label in the
    #: sweep, and never as a capture statistic (that is P3's rail, and it holds
    #: here too: the sweep's models are trained on ARBITER margins throughout).
    oracle_labels = labels_from_records(inp["if_by_rid"], arms_index)["labels"]
    graded_feats = json.loads(Path(args.features).read_text())["features"]
    accepted = {r["rid"] for r in inp["rows"]}
    graded_rids = sorted(set(graded_feats) & set(graded_labels) & accepted)

    registry = {k: v for k, v in json.loads(_repo_path(args.corpora).read_text()).items()
                if not k.startswith("_") and isinstance(v, dict)}
    order = [n for n in sorted(registry, key=lambda k: registry[k].get("tier", 99))
             if not registry[n].get("disabled")]
    pools = [load_corpus_pool(n, registry[n]) for n in order]
    disjoint = assert_disjoint(graded_labels, pools)          # ⛔ G-DISJOINT

    tiers = [{"tier": "T0", "pools": [], "label": "stage-0 (incumbent)"}]
    for i, p in enumerate(pools):
        tiers.append({"tier": f"T{i+1}", "pools": pools[:i + 1],
                      "label": "+" + p["name"]})

    cells = []
    for t in tiers:
        for design in (CROSS_FIT, AUX_TRAIN):
            r = run_label_tier(inp, graded_feats, graded_labels, graded_rids,
                               t["pools"], design=design, model=args.model,
                               kappa=0.0, args=args, oracle_labels=oracle_labels)
            r.update({"tier": t["tier"], "tier_label": t["label"], "arm": "label"})
            cells.append(r)
            _print_cell(r)

    # the pre-registered near-tie sweep, at the TOP label rung (PLAN.md §6.4)
    top = tiers[-1]
    for kap in [float(k) for k in str(args.kappas).split(",") if k.strip()]:
        if kap == 0.0:
            continue
        for design in (CROSS_FIT, AUX_TRAIN):
            r = run_label_tier(inp, graded_feats, graded_labels, graded_rids,
                               top["pools"], design=design, model=args.model,
                               kappa=kap, args=args, oracle_labels=oracle_labels)
            r.update({"tier": top["tier"], "tier_label": top["label"] + f" k={kap}",
                      "arm": "kappa"})
            cells.append(r)
            _print_cell(r)

    # --- paired contrasts: the label TREND, the kappa curve, the design check ---
    def cell(t, design, kap=0.0, arm=None):
        for c in cells:
            if (c.get("tier") == t and c.get("design") == design
                    and c.get("kappa") == kap and not c.get("skipped")):
                return c
        return None

    top_t = tiers[-1]["tier"]
    want = [("label_trend_T0_to_top__crossfit", cell(top_t, CROSS_FIT),
             cell("T0", CROSS_FIT)),
            ("label_trend_T0_to_top__auxtrain_vs_stage0", cell(top_t, AUX_TRAIN),
             cell("T0", CROSS_FIT)),
            ("design_check_auxtrain_minus_crossfit_at_top", cell(top_t, AUX_TRAIN),
             cell(top_t, CROSS_FIT)),
            ("kappa_1.0_minus_0_at_top__crossfit", cell(top_t, CROSS_FIT, 1.0),
             cell(top_t, CROSS_FIT)),
            ("kappa_0.5_minus_0_at_top__crossfit", cell(top_t, CROSS_FIT, 0.5),
             cell(top_t, CROSS_FIT))]
    contrasts = {}
    for name, a, b in want:
        if not (a and b):
            continue
        contrasts[name] = paired_acc_contrast(a, b, args.boot_seed)
        contrasts[name + "__vs_ORACLE_order"] = paired_acc_contrast(
            a, b, args.boot_seed, key="per_root_acc_oracle",
            acc_key="rank_accuracy_oracle")
    print("\n=== PAIRED accuracy contrasts (same graded pairs, root-clustered) ===")
    for name, c in contrasts.items():
        if c:
            print(f"  [{c['target']:<8}] {name:<58} Δacc {c['delta_acc']:+.4f} ± "
                  f"{c['se_paired']:.4f} (z {c['z']:+.2f})  "
                  f"CI95 [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"
                  f"   [unpaired se would be {c['se_unpaired_quadrature']:.4f}]")

    rep = {
        "schema": SCHEMA, "mode": "sweep", "generated_utc": _utc(), "git": _git_rev(),
        "contrasts": contrasts,
        "knowngood": kg, "plan": FREE_TIER_PLAN, "read_rule": P3_RULE_DOC,
        "design_note": AUX_TRAIN_NOTE, "g_disjoint": disjoint,
        "corpora": [p["meta"] for p in pools],
        "graded": {"n_rids": len(graded_rids),
                   "n_roots": len({graded_labels[r]["root_id"] for r in graded_rids}),
                   "n_pairs_non_tied": sum(
                       sum(1 for i in range(len(graded_labels[r]["labels"]))
                           for j in range(i + 1, len(graded_labels[r]["labels"]))
                           if graded_labels[r]["labels"][i] != graded_labels[r]["labels"][j])
                       for r in graded_rids)},
        "cells": cells, "model": args.model, "kappas": args.kappas,
        "anti_shopping": "PLAN.md §7.4: stage-1 is licensed ONE headline capture read "
                         "against the spent 733 — the TOP label rung. Every other cell "
                         "here is a DIAGNOSTIC and its capture may NOT be quoted as a "
                         "result.",
        "ceiling_caveat": CEILING_CAVEAT,
        "net_asymmetry_caveat": NET_ASYMMETRY_CAVEAT,
        "r1_collinearity_note": R1_COLLINEARITY_NOTE,
        "prior": FREE_TIER_PRIOR,
        "governance": "0 games, no band, no results.csv row, no claim id, no "
                      "RUN_LIVE.json. ZERO worker-hours.",
    }
    (out_dir / "SWEEP.json").write_text(json.dumps(rep, indent=2, default=str))
    print(f"\n⚠️  {AUX_TRAIN_NOTE}")
    print(f"\n[wrote] {out_dir / 'SWEEP.json'}")
    return 0


def _print_cell(r: dict) -> None:
    if r.get("skipped"):
        print(f"  [{r.get('tier')}/{r['design']}] SKIPPED — {r['skipped']}")
        return
    a, o, c = r["rank_accuracy"], r["rank_accuracy_oracle"], r["capture"]
    # P1's calibration maps ORACLE-target accuracy -> capture; apply it to the
    # oracle-target number and print the gap to what was actually measured.
    pred = P1_RND_CAPTURE + (o["acc"] - 0.5) * P1_SLOPE
    print(f"  [{r['tier']:<3} {r['design']:<9} k={r['kappa']:<4}] "
          f"train_rows {r['fit']['n_train_pairs_rows']:>7}  "
          f"acc/arb {a['acc']:.4f} ± {a['se_boot_cluster']:.4f} "
          f"(deff {a['deff']:.2f})  acc/ora {o['acc']:.4f} ± {o['se_boot_cluster']:.4f}  "
          f"capture {c['arb']['mean']:+.5f} ± {c['arb']['se_cluster']:.4f} "
          f"boot [{c['arb']['boot_lo']:+.4f}, {c['arb']['boot_hi']:+.4f}]  "
          f"(P1 would predict {pred:+.4f} from acc/ora)")


# =========================================================================== #
# 5. PRICING PROBE                                                             #
# =========================================================================== #
def cmd_price(args) -> int:
    """Time N v2.9-greedy playouts on REAL corpus positions. Short, sequential,
    niced by the launcher — never run beside a timing bench that owns the box."""
    import root_replay as RR                                       # noqa: PLC0415
    from carcassonne_ai import rules_profile as RP                 # noqa: PLC0415
    from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent    # noqa: PLC0415

    prov = register_v29_policy()
    prof = RP.activate(args.rules_profile)
    if RP.r9_env_on() != prof.r9_env_expected:
        raise SystemExit(f"REFUSING: R9 latch mismatch for {args.rules_profile!r}")
    game_kwargs = prof.game_kwargs() or None

    leg_rows = read_plan_legs(args.plan_dir)
    rows = [json.loads(ln) for key, rr in sorted(leg_rows.items())
            if key.startswith(f"{args.rules_profile}/") for _rid, ln in rr]
    rows = [r for r in rows if r.get("actions") or r.get("archive_path")]
    rng = random.Random(PROBE_SEED)
    rng.shuffle(rows)

    per_policy = {}
    for policy in args.policies:
        times, plies, done = [], [], 0
        for row in rows:
            if done >= args.playouts:
                break
            try:
                actions = row.get("actions") or _actions_from_archive(row["archive_path"])
                game, board = RR.replay_actions(row["deck_seed"], actions, row["ply"],
                                                game_kwargs=game_kwargs)
                rid = row["rid"]
                for j in range(args.worlds):
                    if done >= args.playouts:
                        break
                    ws = OSP.world_seed(rid, j, args.salt)
                    ps = OSP.playout_seed(rid, j, args.salt)
                    wb = FairHeuristicMCTSAgent.reshuffled_determinization(
                        board, random.Random(ws))
                    t0 = time.perf_counter()
                    _m, _dh, _bk, npl = OSP._playout_value(
                        game, wb, int(row["pick_a"]), int(row["root_player"]),
                        ps, 100, 400, policy, None)
                    times.append(time.perf_counter() - t0)
                    plies.append(npl)
                    done += 1
            except Exception as exc:                               # noqa: BLE001
                print(f"  [skip] {row.get('rid')}: {type(exc).__name__}: {exc}")
        arr = np.asarray(times)
        per_policy[policy] = {
            "n_playouts": int(arr.size),
            "mean_s": float(arr.mean()) if arr.size else None,
            "median_s": float(np.median(arr)) if arr.size else None,
            "p90_s": float(np.percentile(arr, 90)) if arr.size else None,
            "min_s": float(arr.min()) if arr.size else None,
            "max_s": float(arr.max()) if arr.size else None,
            "mean_plies": float(np.mean(plies)) if plies else None,
        }
        print(f"[{policy}] {json.dumps(per_policy[policy])}")

    legs_total = sum(len(v) for v in leg_rows.values())
    out = {"schema": SCHEMA, "mode": "price", "generated_utc": _utc(),
           "rules_profile": args.rules_profile,
           "leaf_provenance": prov.get("hashes"),
           "per_policy": per_policy,
           "corpus": {"legs": legs_total, "m": args.worlds_full,
                      "playouts_full_leg": legs_total * args.worlds_full * 2},
           "host": os.uname().nodename,
           "warning": "SEQUENTIAL single-thread timings. A W-parallel box is "
                      "DRAM-latency-bound; divide by W only after a real bench."}
    p = Path(args.out_dir) / "PRICE.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
    print(f"[wrote] {p}")
    return 0


# =========================================================================== #
# helpers / CLI                                                                #
# =========================================================================== #
def _utc() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _git_rev() -> str:
    return OSP._git_rev(REPO)


def _add_grade_args(ap):
    ap.add_argument("--if-records", default=DEFAULT_IF_RECORDS)
    ap.add_argument("--arb-records", action="append", default=None)
    ap.add_argument("--v29-records", default=DEFAULT_V29_ROOT)
    ap.add_argument("--plan-dir", default=str(DEFAULT_PLAN_DIR))
    ap.add_argument("--full-supply-plan", default=None)
    ap.add_argument("--holdout-roots", default=str(DEFAULT_HOLDOUT))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    #: the tiearb run's own committed bootstrap seed — reused so the CI on `tier1`
    #: is the published CI, not a re-drawn one.
    ap.add_argument("--boot-seed", type=int, default=20260816)
    ap.add_argument("--rnd-seed", type=int, default=20260816)


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    s = sub.add_parser("score-v29", help="score the v2.9-greedy continuation leg")
    s.add_argument("--chunk", default="1/1")
    s.add_argument("--plan-dir", default=str(DEFAULT_PLAN_DIR))
    s.add_argument("--out-root", default=DEFAULT_V29_ROOT)
    s.add_argument("--workers", type=int, default=16)
    s.add_argument("--m", type=int, default=ATB.M_EXPECTED)
    s.add_argument("--salt", default=RT.WORLD_SEED_SALT)
    s.add_argument("--oracle-sims", type=int, default=100)
    s.add_argument("--wall-cap", type=int, default=7200)
    s.add_argument("--max-plies", type=int, default=400)
    s.add_argument("--resume", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_score_v29)

    s = sub.add_parser("leg-worker", help="(internal) one oracle_score_pilot leg")
    s.set_defaults(func=None)

    s = sub.add_parser("knowngood", help="reproduce arb=0.2065 on the tier1 picker")
    _add_grade_args(s)
    s.set_defaults(func=lambda a: (require_knowngood(load_grade_inputs(a), a.boot_seed,
                                                     Path(a.out_dir)) and 0) or 0)

    s = sub.add_parser("grade", help="the capture read")
    s.add_argument("--picker", default="tier1", choices=("tier1", "v29", "net", "all"))
    s.add_argument("--net-scores", default=None)
    _add_grade_args(s)
    s.set_defaults(func=cmd_grade)

    s = sub.add_parser("train-net", help="stage-0 learned tie-breaker")
    _add_grade_args(s)
    s.add_argument("--features", default=str(DEFAULT_OUT_DIR / "features.json"))
    s.add_argument("--build-features", action="store_true")
    s.add_argument("--features-only", action="store_true")
    s.add_argument("--rules-profile", default="walled")
    s.add_argument("--model", default="pairwise-logistic",
                   choices=("pairwise-logistic", "gbdt"))
    s.add_argument("--kfold", type=int, default=5)
    s.add_argument("--split-seed", type=int, default=PROBE_SEED)
    s.add_argument("--min-pairs", type=int, default=50)
    s.add_argument("--limit", type=int, default=0)
    s.set_defaults(func=cmd_train_net)

    s = sub.add_parser("preflight", help="stage-1 FREE TIER pre-flights P1/P2/P3 "
                                         "(PLAN.md §9.2; ZERO worker-hours)")
    _add_grade_args(s)
    s.add_argument("--parts", default="p1,p2,p3")
    s.add_argument("--features", default=str(DEFAULT_OUT_DIR / "features.json"))
    s.add_argument("--model", default="pairwise-logistic",
                   choices=("pairwise-logistic", "gbdt"))
    s.add_argument("--kfold", type=int, default=5)
    s.add_argument("--split-seed", type=int, default=PROBE_SEED)
    s.add_argument("--min-pairs", type=int, default=50)
    s.set_defaults(func=cmd_preflight)

    s = sub.add_parser("sweep", help="stage-1 FREE TIER label sweep A1/A2/A3 + the "
                                     "pre-registered near-tie kappa curve "
                                     "(PLAN.md §9.3; ZERO worker-hours)")
    _add_grade_args(s)
    s.add_argument("--corpora", default=str(REPO / "measurement"
                                            / "tienet_stage1_plan_20260823"
                                            / "CORPORA.json"))
    s.add_argument("--features", default=str(DEFAULT_OUT_DIR / "features.json"))
    s.add_argument("--model", default="pairwise-logistic",
                   choices=("pairwise-logistic", "gbdt"))
    s.add_argument("--kfold", type=int, default=5)
    s.add_argument("--split-seed", type=int, default=PROBE_SEED)
    s.add_argument("--min-pairs", type=int, default=50)
    s.add_argument("--kappas", default="0,0.5,1.0")
    s.set_defaults(func=cmd_sweep)

    s = sub.add_parser("price", help="time N v2.9-greedy playouts on real positions")
    s.add_argument("--playouts", type=int, default=20)
    s.add_argument("--worlds", type=int, default=2)
    s.add_argument("--worlds-full", type=int, default=ATB.M_EXPECTED)
    s.add_argument("--policies", nargs="+", default=[V29_POLICY])
    s.add_argument("--plan-dir", default=str(DEFAULT_PLAN_DIR))
    s.add_argument("--rules-profile", default="walled")
    s.add_argument("--salt", default=RT.WORLD_SEED_SALT)
    s.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    s.set_defaults(func=cmd_price)
    return ap


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "leg-worker":
        return leg_worker(argv[1:])
    args = build_parser().parse_args(argv)
    if getattr(args, "arb_records", None) is None and hasattr(args, "if_records"):
        args.arb_records = list(DEFAULT_ARB_ROOTS)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
