#!/usr/bin/env python3
"""G-PIN — prove the pinned counterfactual IS E-1a's counterfactual.

The whole cross-read rests on one claim: the champion this census builds at the
PINNED k8 x 1376 / exact-K 2 budget names the SAME move that E-1a's ply-pricing
run banked, so a new defense ply and an E-1a defense ply were selected by the
same divergence test.  That claim is checkable, and this script checks it: it
replays E-1a's OWN frozen target plies and asserts our `build_pinned_champion`
reproduces the banked `counterfactual_action` bit-for-bit.

⛔ It reads only `played_action` / `counterfactual_action` from the frozen E-1a
target file.  It reads NO price, computes NO price, and touches no E-1b output.
Those old plies are excluded from the new ledger at game level regardless
(PREREG §2.1) — this is a wiring proof, not a data source.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ARCHIVES = REPO / "measurement" / "e4_games"
E1A_TARGETS = REPO / "measurement" / "e1b_armed_continuation_20260901" / \
    "targets_continuation.jsonl"

sys.path.insert(0, str(HERE))
import census_new_plies as C                                     # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="fixed_v1")
    ap.add_argument("--n", type=int, default=8, help="plies to re-derive")
    ap.add_argument("--stratum", default="defense",
                    help="'all' or one of invasion/defense/farm_capture/control")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--out", default=str(HERE / "PIN_VERIFICATION.json"))
    args = ap.parse_args()

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    for sub in ("scripts/analyzer", "scripts"):
        d = str(REPO / sub)
        if d not in sys.path:
            sys.path.insert(0, d)
    import ev_loss                                               # noqa: PLC0415
    env = ev_loss.prepare_env(args.profile)

    rows = [json.loads(l) for l in E1A_TARGETS.open() if l.strip()]
    rows = [r for r in rows if r["profile"] == args.profile]
    if args.stratum != "all":
        rows = [r for r in rows if r["stratum"] == args.stratum]
    rows.sort(key=lambda r: (r["game"], r["ply"]))
    rows = rows[: args.n]
    if not rows:
        raise SystemExit("G-PIN: no E-1a rows selected — nothing to verify")

    by_game: dict[str, list] = {}
    for r in rows:
        by_game.setdefault(r["game"], []).append(r)

    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    prof = rules_profile.activate(args.profile)
    ex = resolve_execution("rust", profile="desktop", rust_threads=args.threads)
    checks, t0 = [], time.time()
    for stem, want_rows in sorted(by_game.items()):
        arc = json.loads((ARCHIVES / stem).read_text())
        actions = [int(x) for x in arc["actions"]]
        want = {int(r["ply"]): r for r in want_rows}
        random.seed(int(arc["deck_seed"]))
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        champ = C.build_pinned_champion(game, args.threads)
        cfg = C.resolved_config(champ)
        C.gate_budget(cfg)
        seat(champ, board)
        for i, a in enumerate(actions):
            if i in want:
                r = want[i]
                champ._move_idx = i
                got = int(champ.choose_action(board))
                checks.append({
                    "game": stem, "ply": i, "stratum": r["stratum"],
                    "banked_counterfactual": int(r["counterfactual_action"]),
                    "rederived_counterfactual": got,
                    "match": got == int(r["counterfactual_action"]),
                    "played_action": int(r["played_action"]),
                    "banked_divergent": bool(not r["counterfactual_agrees"]),
                    "rederived_divergent": got != int(r["played_action"]),
                })
                c = checks[-1]
                print(f"  {stem} #{i:3d} {r['stratum']:13s} banked="
                      f"{c['banked_counterfactual']:5d} got={got:5d} "
                      f"{'OK' if c['match'] else 'MISMATCH'}", flush=True)
            board, _ = game.get_next_state(board, a)
            advance(champ, a)
        if hasattr(champ, "close"):
            champ.close()

    n_ok = sum(c["match"] for c in checks)
    n_div_ok = sum(c["banked_divergent"] == c["rederived_divergent"] for c in checks)
    out = {
        "schema": "defense-primary-pin-verification/v1",
        "env": env, "execution": dict(ex),
        "budget_pin": {"k_dets": C.PINNED_K_DETS,
                       "sims_per_det": C.PINNED_SIMS_PER_DET,
                       "exact_max_k": C.PINNED_EXACT_K,
                       "seed": C.COUNTERFACTUAL_SEED},
        "resolved": cfg,
        "source": str(E1A_TARGETS.relative_to(REPO)),
        "n_checked": len(checks),
        "n_action_match": n_ok,
        "n_divergence_verdict_match": n_div_ok,
        "by_stratum": dict(Counter(c["stratum"] for c in checks)),
        "PASS": (n_ok == len(checks) and n_div_ok == len(checks)),
        "wall_s": round(time.time() - t0, 1),
        "checks": checks,
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=1))
    if not out["PASS"]:
        raise SystemExit("G-PIN FAILED: the pinned champion does not reproduce "
                         "E-1a's banked counterfactual — the cross-read is not "
                         "licensed until this is explained.")
    print("G-PIN PASS")


if __name__ == "__main__":
    main()
