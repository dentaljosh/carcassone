#!/usr/bin/env python3
"""IDENTITY GATE for `gate_b_depth_transfer.py --backend rust` (audit item B4).

⚠️ WHY THIS GATE IS NOT OPTIONAL — the argument `scripts/rustport/gate_clairvoyant.py`
makes, applied to an instrument. G4/G6 gated the champion as a PLAYER: same moves, same
elo. None of that transfers to a RULER. Gate B uses the champion's clairvoyant core as a
COMPONENT — it steps the search itself and reads the root between simulations — so
converting it converts code G4/G6 never touched, and its output is a *measurement other
conclusions are priced against*. A converted instrument that is merely "also correct" is
still a NEW instrument.

⚠️ AND THIS CONVERSION CHANGES THE MECHANISM, not just the engine. Python snapshots ONE
deep search at every level; `carc_rs` has no per-sim hook (`snapshot.RUST_BACKEND_GAP`), so
the rust path runs ONE STANDALONE SEARCH PER LEVEL. That is legitimate only because
snapshot-at-L == standalone-at-L, which the harness proves separately with
`--verify-bit-exact`. This gate closes the other half: that the rust standalone search
equals the python one, bit for bit, at every level.

THREE LEGS, all on RAW f64 BIT PATTERNS (the G3 pattern — a decimal comparison hides the
1-ulp divergence a reconcile gate exists to catch):

  identity   per root: every level's FULL deduped child map `{action: (N, Q_rootpov)}`, the
             root priors, the root leaf value — then the whole emitted record, run through
             the harness's own `_process_root` on each backend. Comparing only the played
             action would pass a search that got the right answer for the wrong reasons;
             the full child map makes the two engines prove they ran the same search.

  seed       `SearchConfigRs` has no seed field, and this harness passes a real one
             (`_root_seed(seed, ply)`). GAP1_SEED_INVARIANCE closed that question at the
             CHAMPION's per-world budget; this leg re-closes it at THIS harness's ladder
             (200 / 344 / 688), because "inert at one knob set" is not "inert".

  clair      B2 (`eval_fair_puct --info clair`) — checks the two facts behind the decision
             to leave it on Python, rather than restating them. It edits nothing.

    .venv/bin/python scripts/rustport/gate_depth_transfer_backend.py --roots 3
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to gate_b_depth_transfer._CANON_ENV. MUST run
#     before importing carcassonne_ai (DEFAULT_CONFIG is import-frozen); the harness sets
#     the same block on import and `setdefault` makes the two agree.
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

import argparse   # noqa: E402
import json       # noqa: E402
import struct     # noqa: E402
import time       # noqa: E402

import gate_b_depth_transfer as GB    # noqa: E402
import root_replay as RR              # noqa: E402
import rust_world_search as RWS       # noqa: E402
from carcassonne_ai import champion_factory as CF   # noqa: E402

OUT = REPO / "measurement" / "rustport_p6" / "GATE_DEPTH_TRANSFER_BACKEND.json"
CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
DEFAULT_ROOTS = REPO / "measurement" / "f3_public_state_oracle" / "roots_k3_suite.jsonl"

SEED_SET = (None, 0, 7, 101, 12345)


# --------------------------------------------------------------------------- #
# Raw-bit comparison — the currency                                            #
# --------------------------------------------------------------------------- #
def _bits(x) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def bitify(obj):
    """Every float -> its raw f64 bit pattern, recursively.

    `bool` is tested before `int` because `isinstance(True, int)` is True in Python, and a
    silently coerced flag is exactly what a gate must not paper over."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return ["f64", _bits(obj)]
    if isinstance(obj, dict):
        return {k: bitify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [bitify(v) for v in obj]
    return obj


def _clip(v, n: int = 6):
    if isinstance(v, list) and len(v) > n:
        return v[:n] + [f"... (+{len(v) - n} more)"]
    return v


def diff_records(a: dict, b: dict, ignore=()) -> list:
    ig = set(ignore)
    out = []
    for k in sorted(set(a) | set(b)):
        if k in ig:
            continue
        va, vb = bitify(a.get(k, "<missing>")), bitify(b.get(k, "<missing>"))
        if va != vb:
            out.append({"field": k, "python": _clip(va), "rust": _clip(vb)})
    return out


# --------------------------------------------------------------------------- #
# Roots                                                                        #
# --------------------------------------------------------------------------- #
def load_roots(path: Path, n: int) -> list:
    """`n` roots the harness itself would accept.

    Prefers the harness's own `--roots` file so the gate grades the SAME positions Gate B
    runs on; falls back to the recorded champion games when that suite is absent, because a
    gate that only runs on one box is a gate nobody runs."""
    out = []
    if path.is_file():
        out = GB._load_roots(str(path))[:n]
    if out:
        return out
    if not CHAMP_GAMES.is_file():
        return []
    recs = [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()]
    for g in recs:
        acts = [int(a) for a in g["actions"]]
        for ply in (40, 72, 104):
            if ply < len(acts) and len(out) < n:
                out.append({"deck_seed": int(g["deck_seed"]), "actions": acts,
                            "ply": int(ply), "k_remaining": -1,
                            "source_agent": "champion"})
        if len(out) >= n:
            break
    return out


def _seat(r: dict):
    """(game, board, r-with-checksum) — the harness's own reconstruction, checksum filled
    in when the root record carries none (the champion-games fallback)."""
    game, board = GB._reconstruct(r)
    if not r.get("checksum"):
        r = dict(r, checksum=game.string_representation(board))
    return game, board, r


# --------------------------------------------------------------------------- #
# LEG 1 — identity                                                             #
# --------------------------------------------------------------------------- #
def leg_identity(roots, levels, cfg) -> dict:
    levels = tuple(sorted(int(x) for x in levels))
    rows, mism, checks = [], [], 0
    t_py = t_rs = 0.0
    for r0 in roots:
        game, board, r = _seat(r0)
        rid = "s%d_p%d" % GB._root_ids(r)
        rseed = GB._root_seed(*GB._root_ids(r))

        t0 = time.perf_counter()
        agent = GB.HeuristicPriorAgent(game, cfg, simulations=max(levels), seed=rseed)
        py_snaps, py_rp, py_priors, py_leaf = GB.snapshot_prior_search(agent, board, levels)
        dt_py = time.perf_counter() - t0

        game2, board2 = GB._reconstruct(r)
        t0 = time.perf_counter()
        rs_snaps, rs_rp, rs_priors, rs_leaf = GB.rust_prior_levels(
            r, game2, board2, levels, cfg)
        dt_rs = time.perf_counter() - t0
        t_py += dt_py
        t_rs += dt_rs

        for name, a, b in (("root_player", py_rp, rs_rp),
                           ("root_priors", py_priors, rs_priors),
                           ("root_leaf_value", py_leaf, rs_leaf)):
            checks += 1
            if bitify(a) != bitify(b):
                mism.append({"root_id": rid, "leg": name,
                             "python": _clip(bitify(a)), "rust": _clip(bitify(b))})
        for L in levels:
            checks += 1
            if bitify(py_snaps[L]) != bitify(rs_snaps[L]):
                mism.append({"root_id": rid, "leg": f"children@{L}",
                             "python": _clip(sorted(bitify(py_snaps[L]).items())),
                             "rust": _clip(sorted(bitify(rs_snaps[L]).items()))})

        # The RECORD leg: the harness's own per-root entry point, on both backends.
        recs = {}
        for backend in ("python", "rust"):
            GB._init_worker(cfg, levels, 3600, False, "clairvoyant", backend)
            recs[backend] = GB._process_root(dict(r))
        checks += 1
        d = diff_records(recs["python"], recs["rust"], ignore=("elapsed_secs", "backend"))
        if d:
            mism.append({"root_id": rid, "leg": "record", "fields": d})
        if not recs["python"].get("ok") or not recs["rust"].get("ok"):
            mism.append({"root_id": rid, "leg": "root_failed",
                         "python": recs["python"].get("error"),
                         "rust": recs["rust"].get("error")})

        rows.append({"root_id": rid, "levels": list(levels),
                     "n_children_deepest": len(py_snaps[levels[-1]]),
                     "played_by_level":
                         recs["python"].get("agreement", {}).get("played_by_level"),
                     "python_secs": round(dt_py, 3), "rust_secs": round(dt_rs, 3),
                     "speedup": (round(dt_py / dt_rs, 2) if dt_rs > 0 else None)})
        print(f"  [identity] {rid:<20} levels={levels} py={dt_py:.2f}s rs={dt_rs:.2f}s "
              f"x{dt_py / max(dt_rs, 1e-9):.2f} "
              f"{'IDENTICAL' if not d else 'MISMATCH'}", flush=True)

    return {"leg": "identity", "levels": list(levels), "roots": len(rows),
            "surface": "every level's FULL deduped child map {action: (N, Q-bits)}, the "
                       "root priors, the root leaf value, then the whole emitted record — "
                       "raw f64 bit patterns, never decimals",
            "mechanism_note": "python snapshots ONE deep search (max(levels) sims); rust "
                              "runs ONE STANDALONE SEARCH PER LEVEL (sum(levels) sims). "
                              "The speedup below is NET of that "
                              f"{sum(levels) / max(levels):.2f}x work penalty.",
            "sims_per_root": {"python": max(levels), "rust": sum(levels)},
            "checks": checks, "mismatches": mism, "rows": rows,
            "python_secs": round(t_py, 2), "rust_secs": round(t_rs, 2),
            "speedup": (round(t_py / t_rs, 2) if t_rs > 0 else None)}


# --------------------------------------------------------------------------- #
# LEG 2 — seed invariance at THIS harness's ladder                             #
# --------------------------------------------------------------------------- #
def leg_seed(roots, levels, cfg) -> dict:
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent

    mism, comparisons, rows = [], 0, []
    for r0 in roots[:1]:
        game, board, r = _seat(r0)
        rid = "s%d_p%d" % GB._root_ids(r)
        for sims in sorted(int(x) for x in levels):
            ref = None
            for seed in SEED_SET:
                g2, b2 = GB._reconstruct(r)
                ag = HeuristicPriorAgent(g2, cfg, simulations=int(sims), seed=seed)
                chosen = int(ag.move(b2))
                root = ag.mcts._nodes[g2.string_representation(b2)]
                surf = {"chosen": chosen, "n": int(root.N),
                        "children": sorted((int(a), int(c.N), _bits(c.W))
                                           for a, c in root.children.items())}
                if ref is None:
                    ref = surf
                    continue
                comparisons += 1
                if surf != ref:
                    mism.append({"root_id": rid, "sims": int(sims), "seed": seed,
                                 "chosen_ref": ref["chosen"], "chosen_got": surf["chosen"],
                                 "children_equal":
                                     surf["children"] == ref["children"]})
            rows.append({"root_id": rid, "sims": int(sims),
                         "chosen": ref["chosen"], "root_n": ref["n"]})
            print(f"  [seed]     {rid:<20} sims={sims:<5} action={ref['chosen']:<5} "
                  f"{len(SEED_SET)} seeds identical", flush=True)
    return {"leg": "seed invariance at THIS harness's ladder",
            "why": "GAP1_SEED_INVARIANCE closed the seed question at the CHAMPION's "
                   "per-world budget only; carc_rs SearchConfigRs still has no seed field, "
                   "so gate_b's own levels need their own evidence",
            "sim_levels": sorted(int(x) for x in levels),
            "seeds": ["None" if s is None else s for s in SEED_SET],
            "comparisons": comparisons, "mismatches": mism, "rows": rows}


# --------------------------------------------------------------------------- #
# LEG 3 — B2: eval_fair_puct --info clair                                      #
# --------------------------------------------------------------------------- #
def leg_clair(cfg) -> dict:
    """B2 stays Python — the two facts that decision rests on, CHECKED not asserted.

    `eval_fair_puct --info clair` builds ONE `HeuristicPriorAgent` prefix and calls
    `.move(board)` every ply of a full game, so it hits the same tree carry-over that
    blocks `oracle_score_pilot` (measurement/rustport_p6/GAP2_ORACLE_CONTINUATION_TREE.json)
    — here through mechanism (b), `reuse_tree`, because this caller DOES go through
    `move()`, which re-roots rather than clears. `carc_rs.MirrorState.search_single` is
    fresh-tree only, so a converted clair arm would be a different ruler.

    This leg touches no code in `eval_fair_puct`, deliberately: that harness ALREADY fails
    closed on `--backend rust --info clair`, so the correct outcome for B2 is a recorded,
    checkable reason — not an edit."""
    from carcassonne_ai.game_wrapper import Game

    game = Game(enable_legal_moves_cache=True)
    agent = CF.build_clairvoyant_champion(game, cfg=cfg, simulations=64, seed=1)
    reuse = bool(getattr(agent, "_reuse_tree", False))
    refused, refusal = False, None
    try:
        CF.build_clairvoyant_champion(game, cfg=cfg, simulations=64, seed=1, backend="rust")
    except Exception as exc:                                    # noqa: BLE001
        refused, refusal = True, f"{type(exc).__name__}: {exc}"
    mism = []
    if not reuse:
        mism.append({"leg": "clair",
                     "error": "the clair agent reports _reuse_tree=False — re-derive "
                              "whether B2 is still blocked; the block rests on tree "
                              "carry-over across the plies of a full game"})
    if not refused:
        mism.append({"leg": "clair",
                     "error": "champion_factory.build_clairvoyant_champion ACCEPTED "
                              "backend='rust' — the fail-closed posture this leg "
                              "documents is gone"})
    print(f"  [clair]    _reuse_tree={reuse}  factory refuses rust={refused}", flush=True)
    return {"leg": "B2 — eval_fair_puct --info clair",
            "status": "STAYS PYTHON. Blocked by the same tree carry-over as the oracle "
                      "pilot, and already failing closed. No code change made.",
            "clair_agent_reuse_tree": reuse,
            "mechanism": "eval_fair_puct builds ONE HeuristicPriorAgent prefix and calls "
                         ".move(board) every ply of a full game; move() re-roots the tree "
                         "when reuse_tree is set, and resolved_manifest marks reuse_tree "
                         "EFFECTIVE in clairvoyant mode. search_single is fresh-tree only.",
            "cross_reference": "measurement/rustport_p6/GAP2_ORACLE_CONTINUATION_TREE.json "
                               "— the same gap, measured on the oracle continuation",
            "factory_refuses_rust": refused, "factory_refusal": refusal,
            "checks": 2, "mismatches": mism,
            "unblocks_when": "carc_core::search grows a persistent / re-rootable tree"}


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_depth_transfer_backend",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("--roots-file", default=str(DEFAULT_ROOTS))
    ap.add_argument("--roots", type=int, default=3)
    ap.add_argument("--levels", default="200,344,688",
                    help="the harness's own ladder; default = its production default")
    ap.add_argument("--leg", default="all",
                    choices=["all", "identity", "seed", "clair"])
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    levels = tuple(int(x) for x in args.levels.split(","))
    want = {"identity", "seed", "clair"} if args.leg == "all" else {args.leg}
    cfg = CF.production_prior_cfg()
    # R1/R7: prove the curve125 leaf on real boards through the RUST engine before any
    # comparison, so a leaf drift can never be mistaken for a search divergence.
    champ_manifest = CF.resolved_manifest("clairvoyant", verify=True, backend="rust")

    roots = load_roots(Path(args.roots_file), args.roots)
    legs = {}
    t0 = time.time()
    if "identity" in want:
        legs["identity"] = leg_identity(roots, levels, cfg)
    if "seed" in want:
        legs["seed"] = leg_seed(roots, levels, cfg)
    if "clair" in want:
        legs["clair"] = leg_clair(cfg)

    # A leg that compared NOTHING is a FAILURE, not a pass — vacuous green (no roots
    # resolved, an empty fallback) is the classic way a gate stops gating.
    for name, leg in legs.items():
        n = leg.get("roots", leg.get("comparisons", leg.get("checks", 0)))
        if not n:
            leg.setdefault("mismatches", []).append(
                {"leg": name, "error": "VACUOUS — this leg compared nothing; a gate that "
                                       "ran on an empty set has not gated anything"})

    n_mism = sum(len(v.get("mismatches", [])) for v in legs.values())
    ok = bool(legs) and n_mism == 0
    out = {
        "gate": "rustport Class-B / audit B4 — gate_b_depth_transfer on the rust backend",
        "why": "converting an instrument CHANGES the instrument; G4/G6 gated the champion "
               "as a PLAYER and does not transfer to a ruler",
        "conversion": "ONE STANDALONE SEARCH PER LEVEL replaces ONE SNAPSHOTTED DEEP "
                      "SEARCH (carc_rs has no per-sim hook — snapshot.RUST_BACKEND_GAP). "
                      "Legitimate only because snapshot-at-L == standalone-at-L, which the "
                      "harness proves separately with --verify-bit-exact; this gate closes "
                      "the other half.",
        "surface": "raw f64 BIT PATTERNS throughout (the G3 pattern) — never decimals",
        "roots_file": str(args.roots_file), "n_roots": len(roots),
        "legs": legs,
        "total_mismatches": n_mism,
        "verdict": "PASS" if ok else "FAIL",
        "scope": "these levels, this code revision, fresh-tree, net-free. Says NOTHING "
                 "about evaluator injection (Gap 3), about snapshot.py (no rust UCT and no "
                 "per-sim hook), or about any caller that carries a tree across plies "
                 "(Gap 2 — see the clair leg).",
        "env": dict(_CANON_ENV),
        "champion_manifest": champ_manifest,
        "wall_secs": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print(f"\n{out['verdict']}: {n_mism} mismatches over legs {sorted(legs)} -> {args.out}")
    idn = legs.get("identity")
    if idn and idn.get("speedup"):
        print(f"  identity: python {idn['python_secs']}s -> rust {idn['rust_secs']}s = "
              f"{idn['speedup']}x  ({idn['checks']} field checks over "
              f"{idn['roots']} roots)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
