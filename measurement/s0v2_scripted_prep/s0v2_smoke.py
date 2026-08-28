#!/usr/bin/env python3
"""S0v2 SCRIPTED EXPLOITER — SIGNATURE SMOKE DRIVER.  ⛔ SMOKE ONLY, NOT A CELL.

The instrument is ``measurement/s0_exploiter_prep/s0_smoke.py`` reused as close
to verbatim as a different agent allows: the same ``INSTRUMENT`` dict (the r3
screening instrument), the same ``eval_fair_puct`` worker plumbing, the same
E4-android-archive output schema so ``stage_a_census.py --games-dir <out>``
grades it unmodified, the same resumable/time-budgeted pool.

THE ONE DIFFERENCE.  S0's candidate side was the champion with a LEAF OVERRIDE.
S0v2's candidate side is the champion with NO leaf override, WRAPPED in
``s0v2_agent.ScriptedExploiter`` — the leaf hash on both sides is the champion's
``a36d2e15a3b3d71d`` and the only thing that differs is the python-side plan
module.  That is the point: S0's finding was that no leaf dose carries the
multi-ply plan, so S0v2 stops trying to buy the plan with a leaf term.

⛔ **NOT A MEASUREMENT CELL.**  No band claimed (throwaway seed range
``900000010000``+, deliberately DISJOINT from the ``900000000000``-area range
``s0_smoke.py`` burned), no ``results.csv`` row, no gate ladder, no claim, no
adoption chain.  Every artifact is stamped ``"smoke": true``.

Usage:
    PYTHONPATH=<tree>/src:<tree>/engine python s0v2_smoke.py \
        --label S0V2_F --plan full --decks 24 --seed-start 900000010000 \
        --workers 8 --out <dir> --time-budget 400
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# --------------------------------------------------------------------------- #
# ⛔ THE ENV GOES IN BEFORE ANY carcassonne_ai IMPORT (s0_smoke.py's rule,       #
# verbatim): R9 is import-latched and DEFAULT_CONFIG — which IS both sides'     #
# leaf here — is resolved from the environment at virtual_score_v2 import time. #
# --------------------------------------------------------------------------- #
os.environ["CARCASSONNE_FIX_R9"] = "1"
for _v in ("CARCASSONNE_INVASION_ALPHA", "CARCASSONNE_INVASION_ALPHA_CAP",
           "CARCASSONNE_INVASION_BETA", "CARCASSONNE_INVASION_GAMMA",
           "CARCASSONNE_INVASION_DELTA_FARM", "CARCASSONNE_JRULES_DOSE"):
    os.environ[_v] = "0.0"
os.environ["CARCASSONNE_INVASION_STUB_MAX_TILES"] = "2"

sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
sys.path.insert(0, str(HERE))

import eval_fair_puct as H                          # noqa: E402
from carcassonne_ai import rules_profile as RP      # noqa: E402
from carcassonne_ai.game_wrapper import Game        # noqa: E402
from s0v2_agent import (PlanConfig, ScriptedExploiter,  # noqa: E402
                        parse_overrides)

# The screening instrument, verbatim from s0_smoke.py (itself verbatim from
# measurement/invasion_screen_r3_prep/WORKERS.conf).  NOT a free choice: the
# smoke exists to be readable next to the S0 smoke and the invasion screens.
INSTRUMENT = {
    "info": "fair",
    "opponent": "fair-champion",
    "backend": "rust",
    "rust_threads": 1,
    "exact_k": 2,
    "k_dets": 4,
    "sims": 688,          # per determinization -> 4 x 688 = 2752 total
    "rung_sims": 800,
    "c_puct": 1.5,
    "tau_p": 5,
    "leaf_quantize": "float",
    "final_select": "visits",
    "value_norm": 15.0,
    "rules_profile": "fixed_v1",
    "total_sims": 2752,
}

# The pre-registered plan profiles.  Frozen here, in the file the smoke runs
# from, so the READ-OUT can never be re-cut against a knob the games never used.
PROFILES = {
    # the CONTROL: champion vs champion, no plan module at all.  Same instrument
    # and same seed range as the arms, so G-EXPRESS(b) is a within-range contrast.
    "off": None,
    # MERGE-ONLY: the script authors the census event whenever one is available
    # and never spends a meeple or a tile choice on setting one up.
    "merge": dict(setup_enabled=False, foothold_enabled=False,
                  victim_min_pts=3, majority_enabled=False,
                  reinforce_enabled=False),
    # FULL PLAN: setup -> foothold -> merge, at the dev-calibrated dose.
    # MAJORITY is OFF here, so this is the SAME agent the 2026-08-28 smoke ran —
    # it is re-run on the new seed range purely as the deck-matched control for
    # the MAJORITY amendment.
    "full": dict(victim_min_pts=3, victim_min_tiles=4, stub_max_tiles=6,
                 majority_enabled=False, reinforce_enabled=False,
                 hold_enabled=False),
    # FULL PLAN + MAJORITY (the 2026-08-28 amendment): identical to `full`, plus
    # the fourth fire and the REINFORCE foothold/setup that feeds it.
    # ⚠️ ROUND-3 NOTE: `full_major` is NOT bit-identical to the arm round 2 ran.
    # Round 2's fire priority was MAJORITY > MERGE, which SMOKE_READOUT §6.3
    # identified as the mechanical cause of that arm's expression miss; round 3
    # fixes the order to MERGE > MAJORITY for BOTH arms, so that the FMH − FM
    # contrast isolates HOLD and nothing else.
    "full_major": dict(victim_min_pts=3, victim_min_tiles=4, stub_max_tiles=6,
                       majority_enabled=True, reinforce_enabled=True,
                       hold_enabled=False),
    # FULL PLAN + MAJORITY + HOLD (the round-3 amendment): all four fires.
    "full_major_hold": dict(victim_min_pts=3, victim_min_tiles=4,
                            stub_max_tiles=6, majority_enabled=True,
                            reinforce_enabled=True, hold_enabled=True),
}


def _plan_cfg(name: str, overrides=None):
    """Resolve a profile.  ``--set`` overrides are a CALIBRATION affordance only:
    the smoke of record runs a bare ``--plan``, and the resolved config is written
    into the manifest either way, so a read-out can never be re-cut against a
    knob the games never used."""
    if name not in PROFILES:
        raise SystemExit(f"unknown --plan {name!r}; have {sorted(PROFILES)}")
    spec = PROFILES[name]
    if spec is None:
        if overrides:
            raise SystemExit("--set has no meaning with --plan off")
        return None
    return parse_overrides(overrides, spec)


# --------------------------------------------------------------------------- #
# the worker                                                                    #
# --------------------------------------------------------------------------- #
def _init(plan_cfg):
    RP.activate(INSTRUMENT["rules_profile"])
    globals()["_PLAN_CFG"] = plan_cfg
    H._worker_init(
        INSTRUMENT["info"],
        {"c_puct": INSTRUMENT["c_puct"], "tau_p": INSTRUMENT["tau_p"],
         "leaf_quantize": INSTRUMENT["leaf_quantize"],
         "final_select": INSTRUMENT["final_select"],
         "value_norm": INSTRUMENT["value_norm"]},
        INSTRUMENT["sims"], INSTRUMENT["k_dets"], INSTRUMENT["exact_k"],
        INSTRUMENT["rung_sims"],
        False, "", 0,                       # shared_claim, claim_host, claim_stale
        cand_leaf_cfg=None,                 # ⭐ NO leaf override: same leaf both sides
        opponent=INSTRUMENT["opponent"],
        opp_leaf_cfg=H._curve125_leaf_cfg(),
        backend=INSTRUMENT["backend"],
        rust_threads=INSTRUMENT["rust_threads"])


def _play_recorded(job):
    """One game with the ACTION SEQUENCE recorded.

    The loop is ``eval_fair_puct._play_one_inner``'s loop verbatim plus
    ``actions.append``; the CANDIDATE agent is that module's own champion
    factory, wrapped by ScriptedExploiter when a plan profile is active."""
    import random

    seed, a_seat, out_path = job
    p = Path(out_path)
    if p.exists():
        return None

    plan_cfg = globals().get("_PLAN_CFG")
    t0 = time.perf_counter()
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    cfg = H._cfg_from_dict(H._W["champ_cfg_dict"], None)
    champ = H._make_champion(H._W["info"], cfg, H._W["sims"], H._W["k_dets"],
                             H._W["exact_k"], seed,
                             Game(enable_legal_moves_cache=True),
                             backend=H._W["backend"],
                             rust_threads=H._W["rust_threads"])
    if plan_cfg is not None:
        champ = ScriptedExploiter(champ, game, plan_cfg,
                                  leaf_cfg=H._curve125_leaf_cfg(),
                                  seed=seed, label="S0v2")
    rung = H._make_opponent(H._W["opponent"], H._W["champ_cfg_dict"],
                            H._W["sims"], H._W["k_dets"], H._W["exact_k"],
                            H._W["rung_sims"], seed,
                            opp_leaf_cfg=H._W.get("opp_leaf_cfg"),
                            backend=H._W["backend"],
                            rust_threads=H._W["rust_threads"])
    H._start_mirrors(board, champ, rung)

    actions: list[int] = []
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        action = champ.move(board) if cur == a_seat else rung.move(board)
        actions.append(int(action))
        board, _ = game.get_next_state(board, action)
        H._advance_mirrors(action, champ, rung)

    s0, s1 = (int(x) for x in board.state.scores)
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    prov = {
        "smoke": True,
        "cand_seat": int(a_seat),
        "cand_leaf_hash": H._leaf_hash(H._curve125_leaf_cfg()),
        "opp_leaf_hash": H._leaf_hash(H._W["opp_leaf_cfg"]),
        "instrument": dict(INSTRUMENT),
        "moves": len(actions),
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "host": socket.gethostname(),
    }
    if plan_cfg is not None:
        prov["telemetry"] = champ.telemetry()
        prov["fires"] = champ.fires
        prov["plans"] = [vars(pl) for pl in champ.ledger.plans]
    rec = {
        "schema": "carcassonne-android-archive/v1",
        "ok": True,
        "deck_seed": int(seed),
        "actions": actions,
        # ⭐ the S0v2 (candidate) seat, so s0_signature.py aggregates by AGENT
        # across the seat-swapped pair.  NOT "a human played here".
        "human_player": int(a_seat),
        "scores": [s0, s1],
        "rules_profile": INSTRUMENT["rules_profile"],
        "result": {"scores": [s0, s1], "diff": int(diff),
                   "winner": (None if s0 == s1 else (0 if s0 > s1 else 1))},
        "s0v2": prov,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{os.getpid()}.partial")
    tmp.write_text(json.dumps(rec))
    tmp.replace(p)
    tel = prov.get("telemetry") or {}
    return {"seed": int(seed), "a_seat": int(a_seat), "diff": int(diff),
            "scores": [s0, s1], "elapsed_s": prov["elapsed_s"],
            "moves": len(actions),
            "merge": tel.get("merge_fires", 0),
            "major": tel.get("majority_fires", 0),
            "hold": tel.get("hold_fires", 0),
            "foothold": tel.get("foothold_fires", 0),
            "setup": tel.get("setup_fires", 0),
            "plans": (tel.get("plans_started", 0), tel.get("plans_completed", 0))}


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--plan", required=True, choices=sorted(PROFILES))
    ap.add_argument("--decks", type=int, required=True)
    ap.add_argument("--seed-start", type=int, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--time-budget", type=float, default=0.0,
                    help="stop dispatching new games after this many seconds (0 = no bound)")
    ap.add_argument("--nice", type=int, default=19)
    ap.add_argument("--set", action="append", default=[],
                    help="CALIBRATION ONLY: PlanConfig override on top of the "
                         "profile, e.g. --set min_visit_share=0.3 (repeatable)")
    args = ap.parse_args()

    try:
        os.nice(args.nice)
    except OSError:
        pass

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan_cfg = _plan_cfg(args.plan, args.set)
    leaf_hash = H._leaf_hash(H._curve125_leaf_cfg())

    manifest = {
        "smoke": True,
        "kind": "s0v2_scripted_exploiter_signature_smoke",
        "not_a_cell": ("NO band claimed, NO results.csv row, NO gate ladder, NO "
                       "adoption chain. Throwaway seed range, DISJOINT from the "
                       "900000000000-area range s0_smoke.py used."),
        "label": args.label,
        "plan": args.plan,
        "plan_overrides": list(args.set),
        "plan_cfg": (plan_cfg.as_dict() if plan_cfg is not None else None),
        "cand_leaf_hash": leaf_hash,
        "opp_leaf_hash": leaf_hash,
        "leaf_override": None,
        "seed_start": args.seed_start,
        "decks": args.decks,
        "instrument": dict(INSTRUMENT),
        "workers": args.workers,
        "host": socket.gethostname(),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"[s0v2-smoke] {args.label}: plan={args.plan} leaf={leaf_hash} (BOTH sides) "
          f"seeds {args.seed_start}..{args.seed_start + args.decks - 1} "
          f"x2 seats, W={args.workers}", flush=True)

    jobs = []
    for i in range(args.decks):
        seed = args.seed_start + i
        for a_seat in (0, 1):
            p = out / f"seed{seed}_a{a_seat}.json"
            if not p.exists():
                jobs.append((seed, a_seat, str(p)))
    print(f"[s0v2-smoke] {len(jobs)} games to play "
          f"({2 * args.decks - len(jobs)} already on disk)", flush=True)
    if not jobs:
        return 0

    import multiprocessing as mp
    t0 = time.time()
    done = 0
    ctx = mp.get_context("fork")
    with ctx.Pool(processes=args.workers, initializer=_init,
                  initargs=(plan_cfg,)) as pool:
        it = pool.imap_unordered(_play_recorded, jobs, chunksize=1)
        for r in it:
            if r is None:
                continue
            done += 1
            print(f"  [{done}/{len(jobs)}] seed={r['seed']} a{r['a_seat']} "
                  f"diff={r['diff']:+d} moves={r['moves']} "
                  f"merge={r['merge']} maj={r['major']} hold={r['hold']} "
                  f"fh={r['foothold']} su={r['setup']} "
                  f"plans={r['plans'][0]}/{r['plans'][1]} "
                  f"{r['elapsed_s']:.1f}s  (wall {time.time() - t0:.0f}s)",
                  flush=True)
            if args.time_budget and (time.time() - t0) > args.time_budget:
                print(f"[s0v2-smoke] time budget {args.time_budget:.0f}s reached — "
                      f"terminating the pool at a game boundary; re-run to resume.",
                      flush=True)
                pool.terminate()
                break
    print(f"[s0v2-smoke] {args.label}: {done} games this pass, "
          f"{time.time() - t0:.0f}s wall", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
