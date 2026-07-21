#!/usr/bin/env python3
"""Gate B — fixed-root DEPTH-TRANSFER replay (measurement infrastructure).

GOAL (pre-registered Gate B, REVIEW_ADOPTION_20260719 item 6 / PROGRAM_ROADMAP_2026-07-07):
measure whether a POLICY / SELECTION signal transfers as MCTS search depth grows — i.e.
separate the "shallow gain washes out at depth" mechanism into its candidate causes
(early discovery vs Q convergence vs selector).

WHAT IT DOES
------------
For each fixed root (a genuinely-hidden late board, reconstructed deterministically), run the
production champion's clairvoyant PUCT-with-heuristic-priors search core ONCE at the deepest
budget, snapshotting the root's child statistics at every requested depth level. Because the
serial NeuralMCTS path is incremental+deterministic, the first L sims of an N-sim search are
BIT-EXACT to a standalone L-sim search (the snapshot.py guarantee, here extended to the
prior-PUCT agent — proven per-run by --verify-bit-exact). So ONE deep search yields all three
depth levels for ~the cost of the deepest alone.

Per root, per depth level, it records:
  * played_action        = argmax root VISITS (the champion's final_select="visits" rule)
  * q_argmax_action      = argmax root Q      (the selector-mechanism probe: visits vs Q)
  * top3                 = top-3 actions by visits with (N, visit_share, Q_rootpov)
  * top2_q_gap           = Q(top1) - Q(top2)  (the Q-convergence-mechanism probe)
  * played_eq_prior_favored  = did the search KEEP the heuristic prior's top pick?
And cross-depth: pairwise top-action agreement (shallow vs deep) + all_agree.

THE SIGNAL UNDER TEST is the heuristic PRIOR's top choice (prior_favored = argmax root.priors).
The washout question: does the prior's pick survive as depth grows, and does the played action
stay stable across depth?  See "how to read" at the bottom of this docstring.

AGENT: the production CLAIRVOYANT champion core — HeuristicPriorAgent (PUCT priors + curve125
v2.9 Bmild_cap8 leaf), built + leaf-verified through champion_factory (F1). This is the cheap,
snapshot-exact core of the deployable fair-PIMC champion (which marginalizes K determinizations
+ a K<=2 endgame solver on top — a documented layer-on, NOT built here; see the report).

ROOTS: F3 mined roots (scripts/f3_public_state_oracle/mine_roots.py), EITHER source, checksum-
verified on reconstruction:
  * GREEDY   (`seed` + `ply`)                  -> gen_endgame_positions.replay_to
  * CHAMPION (`deck_seed` + `actions` + `ply`) -> root_replay.replay_actions  [added 2026-07-21]
The greedy suite (measurement/f3_public_state_oracle/roots_k3_suite.jsonl) was the fallback used
while no champion action logs existed; champion-distribution roots are now minable from a
`gen_fair_distill.py --log-actions` run and are a drop-in for --roots.

Resumable (skips roots with an existing record), wall-capped per root (SIGALRM), emits a
resolved manifest.json + one JSON record per root, same style as the other measurement/ dirs.

HOW TO READ (GO / NULL for depth-transfer):
  * shallowest_vs_deepest agreement HIGH (played same at 200 and 688) + played_eq_prior_favored
    roughly FLAT across depth  ->  the selection is depth-STABLE: a prior/policy improvement that
    moves the shallow top action would PERSIST at depth (transfers; less washout).
  * agreement LOW and/or played_eq_prior_favored DECLINES sharply with depth  ->  deeper search
    actively OVERTURNS the shallow / prior pick: shallow gains WASH OUT. The mechanism split:
      - played_eq_q_argmax flips with depth      -> SELECTOR (visits vs Q disagree, resolve late)
      - top2_q_gap widens with depth             -> Q CONVERGENCE (a late-favored move pulls ahead)
      - a top-3 non-top-1 move overtakes by 688  -> EARLY DISCOVERY (deep search finds it itself)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env — byte-identical to scripts/f3_public_state_oracle/env_preamble.py
#     CANON_ENV and eval_fair_puct._CANON_ENV: cap8 / curve100 BASE leaf + flat+Cython path +
#     single-thread pins. The champion's curve125 is injected IN-PROCESS by
#     champion_factory.production_prior_cfg (dc.replace on the meeple curve) and VERIFIED on
#     real boards at build. This block MUST run before importing carcassonne_ai
#     (virtual_score_v2.DEFAULT_CONFIG is import-frozen). setdefault: an orchestrator that
#     already exported these wins. ---
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
import signal  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent  # noqa: E402
import gen_endgame_positions as GEP  # noqa: E402  (replay_to, k_remaining)
import snapshot as SNAP  # noqa: E402  (read_children, best_action_from)

DEFAULT_LEVELS = (200, 344, 688)   # k4×{200,344,688} per-world sim budgets (CL-054 champion band)

# per-worker globals (fork-inherited; set in _init_worker)
_CFG = None
_LEVELS = None
_WALL = None
_VERIFY = None
_INFO = None


# --------------------------------------------------------------------------- #
# The snapshot search for the prior-PUCT agent (the champion's clairvoyant core) #
# --------------------------------------------------------------------------- #
def snapshot_prior_search(agent: HeuristicPriorAgent, board, levels):
    """Mirror NeuralMCTS.search's SERIAL (batch_size=1) CLAIRVOYANT setup, then step
    max(levels) PUCT sims, snapshotting deduped root child stats {action:(N,Q_rootpov)}
    at each level. Bit-exact to a standalone HeuristicPriorAgent(sims=L).mcts.search for
    every L (--verify-bit-exact proves it per-run). `agent` must be freshly constructed
    (fresh _nodes, seeded rng) — do NOT reuse across roots."""
    m = agent.mcts
    assert m.batch_size == 1, "snapshot path is serial (batch_size=1) only"
    assert not m.fair_chance, "snapshot path is clairvoyant (fair_chance=False) only"
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
    root_priors = {int(a): float(p) for a, p in root.priors.items()}   # legal-only softmax priors
    root_leaf_value = float(root.leaf_value)
    snaps = {}
    idx = 0
    for i in range(1, levels[-1] + 1):
        m._simulate(board, root)
        if idx < len(levels) and i == levels[idx]:
            snaps[levels[idx]] = SNAP.read_children(root, root_player)
            idx += 1
    return snaps, root_player, root_priors, root_leaf_value


def _visits_best(levelmap):
    """(action, N, Q_rootpov) with max visits; ties -> lowest action id. Mirrors the
    champion's final_select='visits' (root_visit_distribution + np.argmax over
    action-sorted deduped children)."""
    items = sorted(((int(a), n, q) for a, (n, q) in levelmap.items() if n > 0),
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
    return (int(seed) * 1_000_003 + int(ply)) & 0x7fffffff


def _root_ids(r: dict) -> tuple[int, int]:
    """(seed, ply) for a root record. GREEDY roots carry `seed`; CHAMPION action-log roots
    (mine_roots.py --source champion) carry `deck_seed` + the full `actions` sequence."""
    return int(r.get("seed", r.get("deck_seed"))), int(r["ply"])


def _reconstruct(r: dict):
    """Rebuild (game, board) for a root record — SOURCE-AGNOSTIC.

    * greedy roots   -> gen_endgame_positions.replay_to(seed, ply)  (greedy self-play replay)
    * champion roots -> root_replay.replay_actions(deck_seed, actions, ply), the lossless
      (deck_seed, action_sequence) contract, so roots mined from the CHAMPION'S OWN play
      distribution work here without a greedy proxy. Both are checksum-verified by the caller.
    """
    if r.get("actions"):
        import root_replay as RR
        return RR.replay_actions(int(r["deck_seed"]), r["actions"], int(r["ply"]))
    return GEP.replay_to(int(r["seed"]), int(r["ply"]))


def _process_root(r: dict) -> dict:
    seed, ply = _root_ids(r)
    root_id = f"s{seed}_p{ply}"
    rec = {"root_id": root_id, "seed": seed, "ply": ply,
           "k_remaining": int(r.get("k_remaining", -1)),
           "source_agent": r.get("source_agent"),
           "levels": list(_LEVELS), "info_mode": _INFO}
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
        agent = HeuristicPriorAgent(game, _CFG, simulations=max_L, seed=rseed)
        snaps, root_player, root_priors, root_leaf_value = snapshot_prior_search(
            agent, board, _LEVELS)
        rec["root_player"] = int(root_player)
        rec["root_leaf_value"] = root_leaf_value

        # prior-favored action = argmax root softmax prior (tie -> lowest action id)
        if root_priors:
            pf = min(root_priors, key=lambda a: (-root_priors[a], a))
            rec["prior_favored"] = int(pf)
            rec["prior_favored_p"] = float(root_priors[pf])
            ps = np.array([root_priors[a] for a in sorted(root_priors)], dtype=float)
            s = ps.sum()
            if s > 0:
                ps = ps / s
                rec["prior_entropy"] = float(-(ps * np.log(ps + 1e-12)).sum())
            rec["n_legal"] = int(len(root_priors))
        else:
            rec["prior_favored"] = None

        per_level = {}
        played_by_level = {}
        for L in _LEVELS:
            lm = snaps[L]
            vb = _visits_best(lm)                 # champion rule (visits)
            qb = SNAP.best_action_from(lm)        # (action, Q, N)
            sumN = sum(n for n, _ in lm.values())
            top = sorted(((int(a), n, q) for a, (n, q) in lm.items() if n > 0),
                         key=lambda t: (-t[1], t[0]))[:3]
            top3 = [{"action": a, "N": n,
                     "visit_share": (n / sumN if sumN else 0.0), "Q": q}
                    for a, n, q in top]
            qs = sorted((q for _, (n, q) in lm.items() if n > 0), reverse=True)
            q_gap = (qs[0] - qs[1]) if len(qs) >= 2 else None
            played = vb[0] if vb else None
            played_by_level[L] = played
            per_level[str(L)] = {
                "played_action": played,
                "played_N": (vb[1] if vb else 0),
                "played_visit_share": (vb[1] / sumN if (vb and sumN) else 0.0),
                "played_Q": (vb[2] if vb else None),
                "q_argmax_action": (qb[0] if qb else None),
                "played_eq_q_argmax": bool(vb and qb and vb[0] == qb[0]),
                "played_eq_prior_favored": bool(
                    vb and rec.get("prior_favored") is not None
                    and vb[0] == rec["prior_favored"]),
                "top2_q_gap": q_gap,
                "sum_N": sumN,
                "n_children": len(lm),
                "top3": top3,
            }
        rec["per_level"] = per_level

        Ls = list(_LEVELS)
        pairs = {}
        for i in range(len(Ls)):
            for j in range(i + 1, len(Ls)):
                a, b = Ls[i], Ls[j]
                pairs[f"{a}v{b}"] = bool(
                    played_by_level[a] is not None
                    and played_by_level[a] == played_by_level[b])
        rec["agreement"] = {
            "played_by_level": {str(L): played_by_level[L] for L in Ls},
            "pairwise": pairs,
            "all_agree": bool(len(set(played_by_level.values())) == 1
                              and None not in played_by_level.values()),
            "shallowest_vs_deepest": pairs.get(f"{Ls[0]}v{Ls[-1]}"),
        }

        if _VERIFY:
            be = {}
            for L in _LEVELS:
                g2, b2 = _reconstruct(r)
                ag = HeuristicPriorAgent(g2, _CFG, simulations=L, seed=rseed)
                ag.clear()
                ag.mcts.search(b2)
                rroot = ag.mcts._nodes[ag.mcts.game.string_representation(b2)]
                ref = {a: n for a, (n, q)
                       in SNAP.read_children(rroot, rroot.player_to_move).items()}
                snapN = {a: n for a, (n, q) in snaps[L].items()}
                be[str(L)] = {"match": bool(ref == snapN),
                              "sum_ref": int(sum(ref.values())),
                              "sum_snap": int(sum(snapN.values()))}
            rec["bit_exact"] = be
        rec["ok"] = True
    except TimeoutError:
        rec["error"] = "wall_hit"
        rec["ok"] = False
    except Exception as e:  # noqa - fail loud per root, never kill the pool
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["ok"] = False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    rec["elapsed_secs"] = round(time.time() - t0, 3)
    return rec


def _init_worker(cfg, levels, wall, verify, info):
    global _CFG, _LEVELS, _WALL, _VERIFY, _INFO
    _CFG, _LEVELS, _WALL, _VERIFY, _INFO = cfg, tuple(levels), wall, verify, info


# --------------------------------------------------------------------------- #
def _load_roots(path: str) -> list:
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if "ply" not in d:
            continue
        # greedy (seed+ply) OR champion action-log (deck_seed+actions+ply) reconstructable roots
        if "seed" in d or ("deck_seed" in d and d.get("actions")):
            out.append(d)
    out.sort(key=lambda r: (int(r.get("k_remaining", 0)), *_root_ids(r)))
    return out


def _summary(records: list) -> dict:
    ok = [r for r in records if r.get("ok")]
    Ls = ok[0]["levels"] if ok else list(DEFAULT_LEVELS)
    n = len(ok)
    s = {"n_records": len(records), "n_ok": n, "levels": Ls}
    if not n:
        return s
    L0, Ld = Ls[0], Ls[-1]
    s["agree_shallowest_vs_deepest"] = round(
        sum(1 for r in ok if r["agreement"]["pairwise"].get(f"{L0}v{Ld}")) / n, 4)
    s["all_agree_frac"] = round(sum(1 for r in ok if r["agreement"]["all_agree"]) / n, 4)
    s["prior_survival_by_level"] = {}
    s["played_eq_q_argmax_by_level"] = {}
    s["mean_top2_q_gap_by_level"] = {}
    for L in Ls:
        k = str(L)
        s["prior_survival_by_level"][k] = round(
            sum(1 for r in ok if r["per_level"][k]["played_eq_prior_favored"]) / n, 4)
        s["played_eq_q_argmax_by_level"][k] = round(
            sum(1 for r in ok if r["per_level"][k]["played_eq_q_argmax"]) / n, 4)
        gaps = [r["per_level"][k]["top2_q_gap"] for r in ok
                if r["per_level"][k]["top2_q_gap"] is not None]
        s["mean_top2_q_gap_by_level"][k] = round(float(np.mean(gaps)), 5) if gaps else None
    if any("bit_exact" in r for r in ok):
        s["bit_exact_all_match"] = all(
            all(v["match"] for v in r.get("bit_exact", {}).values())
            for r in ok if "bit_exact" in r)
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gate B fixed-root depth-transfer replay")
    ap.add_argument("--roots", default=str(
        REPO / "measurement" / "f3_public_state_oracle" / "roots_k3_suite.jsonl"))
    ap.add_argument("--out-dir", default=str(
        REPO / "measurement" / "gate_b_depth_transfer" / "records"))
    ap.add_argument("--levels", default="200,344,688",
                    help="comma-separated per-world sim depth levels (ascending)")
    ap.add_argument("--n", type=int, default=0, help="limit to first N roots (0 = all)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--wall-cap-secs", type=int, default=180, help="per-root SIGALRM cap")
    ap.add_argument("--info", choices=["clairvoyant"], default="clairvoyant",
                    help="agent info mode (v1 = clairvoyant prior core; fair-PIMC is a layer-on)")
    ap.add_argument("--verify-bit-exact", action="store_true",
                    help="also run standalone searches per level and assert snapshot==standalone")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    args = ap.parse_args(argv)

    levels = tuple(int(x) for x in args.levels.split(","))
    assert list(levels) == sorted(levels), "--levels must be ascending"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    roots = _load_roots(args.roots)
    if args.n > 0:
        roots = roots[:args.n]

    # Build + VERIFY the production champion leaf (F1 runtime guard; raises on drift).
    cfg = CF.production_prior_cfg()
    manifest_champ = CF.resolved_manifest("clairvoyant", verify=True)

    todo = []
    skipped = 0
    for r in roots:
        rid = "s%d_p%d" % _root_ids(r)
        if args.resume and (out_dir / f"{rid}.json").exists():
            skipped += 1
            continue
        todo.append(r)

    manifest = {
        "harness": "gate_b_depth_transfer",
        "schema": "carcassonne-gate-b/v1",
        "goal": "fixed-root depth-transfer replay: does a policy/selection signal survive as "
                "MCTS depth grows (separates the shallow-washout mechanism)",
        "levels": list(levels),
        "level_semantics": "per-world PUCT sim budgets; champion band k4×{200,344,688} (CL-054). "
                           "One deep search snapshotted -> bit-exact at every level.",
        "info_mode": args.info,
        "agent": "HeuristicPriorAgent (clairvoyant PUCT-priors core of the deployable "
                 "fair-PIMC champion; curve125 v2.9 Bmild_cap8 leaf)",
        "final_select": "visits (played_action); q_argmax also recorded (selector probe)",
        "roots_source": str(args.roots),
        "n_roots_total": len(roots),
        "n_todo": len(todo),
        "n_skipped_resume": skipped,
        "wall_cap_secs": args.wall_cap_secs,
        "workers": args.workers,
        "verify_bit_exact": bool(args.verify_bit_exact),
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "champion_manifest": manifest_champ,
    }
    (out_dir.parent / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[gate_b] roots={len(roots)} todo={len(todo)} skipped(resume)={skipped} "
          f"levels={levels} workers={args.workers} verify={args.verify_bit_exact}")

    records = []
    # read back any already-completed records so the summary covers the full set
    if args.resume:
        for r in roots:
            rid = "s%d_p%d" % _root_ids(r)
            fp = out_dir / f"{rid}.json"
            if fp.exists() and r not in todo:
                try:
                    records.append(json.loads(fp.read_text()))
                except Exception:
                    pass

    if todo:
        ctx = get_context("fork")
        with ctx.Pool(args.workers, initializer=_init_worker,
                      initargs=(cfg, levels, args.wall_cap_secs, args.verify_bit_exact,
                                args.info)) as pool:
            for rec in pool.imap_unordered(_process_root, todo, chunksize=1):
                (out_dir / f"{rec['root_id']}.json").write_text(json.dumps(rec))
                records.append(rec)
                flag = "" if rec.get("ok") else f"  !! {rec.get('error')}"
                print(f"  {rec['root_id']:>20}  {rec.get('elapsed_secs')}s"
                      f"  agree(sh/deep)={rec.get('agreement', {}).get('shallowest_vs_deepest')}"
                      f"{flag}")

    summary = _summary(records)
    (out_dir.parent / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print("[gate_b] SUMMARY:", json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
