#!/usr/bin/env python3
"""IDENT-BITEXACT — the phase fire-gate's identity fixture (DESIGN.md §7.5).

⭐ THE PROOF, NOT THE ASSERTION. The whole `IDENT` premise is that

    phase_gate = "all"   is TODAY'S UNGATED ARBITER, bit for bit
    phase_gate = "none"  is THE UNMODIFIED CHAMPION, bit for bit

and the only honest way to show it is to play the SAME seeded games under the
PRE-CHANGE wheel and under the POST-CHANGE wheel and compare the emitted action
sequences byte for byte. This script emits one leg; `identity_check.sh` runs it
under both wheels and diffs.

⚠️ The pre-change wheel does NOT accept `tiearb_phase_gate`, so the two legs
necessarily ask for different things:

    OLD wheel  ->  `--arms champ,arb`          (no gate kwarg exists)
    NEW wheel  ->  `--arms champ,arb,all,none` (adds the two gated arms)

and the identity claims are the CROSS-WHEEL ones:

    NEW.all  == OLD.arb     (the gate at "all" changed no played action)
    NEW.none == OLD.champ   (the armed-but-inert gate is the champion)

plus the within-leg controls `NEW.arb == NEW.all` (an explicitly-set default is
the default) and `NEW.none == NEW.champ`.

⛔ Everything emitted here is STRUCTURAL — action sequences, final scores and
fire counters. No margin, no elo, no outcome statistic: this is a build gate,
not a cell, and it plays throwaway seeds outside every claimed band.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys

# Throwaway seeds. ⛔ NOT in band 154e9 or any registered band — this fixture
# plays no cell and claims no decks.
SEEDS = [f"9{i:011d}" for i in range(1, 41)]


def _agent(carc_rs, *, arbiter: bool, gate: str | None, sims: int, k_dets: int,
           b: int, seed: int):
    """Build a FairAgentRs. `gate is None` => do not pass the kwarg at all (the
    only shape the pre-change wheel accepts)."""
    kw = {}
    if arbiter:
        kw.update(tiearb_enabled=True, tiearb_b=b, tiearb_j=4,
                  tiearb_mode="argmax", tiearb_salt="tiearb2-deploy-v1",
                  tiearb_eps=0.0)
        if gate is not None:
            kw["tiearb_phase_gate"] = gate
    elif gate is not None:
        # champion + an armed-but-gated-off arbiter is `IDENT`'s own shape and
        # is exercised by the "none" arm; a gate on a DISABLED arbiter is
        # meaningless and never built here.
        raise ValueError("gate on a disabled arbiter")
    leaf = carc_rs.LeafConfigRs.curve125()
    sc = carc_rs.SearchConfigRs(leaf, sims, 1.5, 5.0, 15.0, **kw)
    return carc_rs.FairAgentRs(sc, k_dets, seed, exact_endgame=False)


def _play(carc_rs, arm: str, deck_seed: str, *, sims: int, k_dets: int, b: int,
          seed: int, max_plies: int) -> dict:
    arbiter = arm != "champ"
    gate = {"champ": None, "arb": None, "all": "all", "none": "none",
            "early": "early", "mid": "mid", "late": "late"}[arm]
    if arm == "champ":
        gate = None
    a = _agent(carc_rs, arbiter=arbiter, gate=gate, sims=sims, k_dets=k_dets,
               b=b, seed=seed)
    a.start_game_from_seed(deck_seed)
    acts: list[int] = []
    for _ in range(max_plies):
        if a.is_terminal():
            break
        act = a.choose_action()
        acts.append(int(act))
        a.advance(act)
    s = a.stats()
    return {
        "actions": acts,
        "scores": list(a.scores()),
        "terminal": bool(a.is_terminal()),
        "fired_plies": int(s.get("tiearb_fired_plies") or 0),
        "tile_plies": int(s.get("tiearb_tile_plies") or 0),
        "pickchanges": int(s.get("tiearb_pickchanges") or 0),
        "errors": int(s.get("tiearb_errors") or 0),
        # Absent on the PRE-CHANGE wheel by construction — recorded as None so
        # the diff can say WHICH wheel a leg came from without trusting a flag.
        "phase_gate": s.get("tiearb_phase_gate"),
        "fired_early": s.get("tiearb_fired_early"),
        "fired_mid": s.get("tiearb_fired_mid"),
        "fired_late": s.get("tiearb_fired_late"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", default="champ,arb",
                    help="comma list of champ|arb|all|none|early|mid|late")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--sims", type=int, default=64)
    ap.add_argument("--k-dets", type=int, default=2)
    ap.add_argument("--tiearb-b", type=int, default=4)
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import carc_rs
    arms = [x.strip() for x in args.arms.split(",") if x.strip()]
    legs: dict[str, dict] = {}
    for arm in arms:
        per_game = {}
        for ds in SEEDS[: args.games]:
            per_game[ds] = _play(carc_rs, arm, ds, sims=args.sims,
                                 k_dets=args.k_dets, b=args.tiearb_b,
                                 seed=args.seed, max_plies=args.max_plies)
        blob = json.dumps({k: v["actions"] for k, v in per_game.items()},
                          sort_keys=True).encode()
        legs[arm] = {
            "games": per_game,
            # A single number a human can compare across two terminals.
            "action_sha256": hashlib.sha256(blob).hexdigest(),
            "fired_plies_total": sum(v["fired_plies"] for v in per_game.values()),
        }
        print(f"[fixture] arm={arm:5s} sha={legs[arm]['action_sha256'][:16]} "
              f"fired={legs[arm]['fired_plies_total']}", flush=True)

    out = {
        "carc_rs_file": carc_rs.__file__,
        "python": sys.version.split()[0],
        "config": {"games": args.games, "sims": args.sims, "k_dets": args.k_dets,
                   "tiearb_b": args.tiearb_b, "seed": args.seed,
                   "max_plies": args.max_plies},
        "seeds": SEEDS[: args.games],
        "legs": legs,
    }
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(f"[fixture] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
