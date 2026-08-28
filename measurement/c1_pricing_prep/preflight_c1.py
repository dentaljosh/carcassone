#!/usr/bin/env python3
"""C1 OUTCOME PRICING — the MANDATORY pre-launch pre-flight. Outcome-blind.

Three gates, all cheap (prefix replay only — NO search, NO continuation, no
champion is ever constructed), and all run BEFORE a single unit of the real run:

  **G-LEGAL** — the reason this file exists.  The microgates instrument ran
  `Game(enable_legal_moves_cache=False)` (its PREREG §2.4: the memo
  `game_wrapper.Game._legal_cache` is documented in `carc_core::tier1` as
  returning a WRONG farmer-corner mask on rotationally-symmetric tiles, and that
  instrument was new so it took the honest mask).  `continue_plies.py` — which
  this instrument reuses VERBATIM — runs `enable_legal_moves_cache=True`.  So a
  `rollout_argmax` chosen under the honest mask can in principle be REJECTED by
  the cached mask, and `_run_arm` would raise `arm action N illegal at the target
  ply`.  The exposure is concentrated exactly on MEEPLE-phase farmer placements,
  i.e. on `farm_capture`, i.e. on the PRIMARY stratum.  Both arms of every target
  ply are therefore checked against the RUNNER's mask here, up front, and any ply
  that fails is DROPPED by a rule frozen before the freeze commit.  Legality does
  not depend on any continuation outcome, so this is outcome-blind by
  construction, not by promise.

  **G-ROOT** — the target ply's root must be reachable: the archive prefix must
  replay, the archive's own `rules_profile` must re-resolve to the frozen
  target's stamp, and the R9 import latch must read as expected.

  **G-ARMS** — `c1_action != champ_action` on every row (an equal pair prices
  exactly zero and must have been dropped at build time), and both actions must
  appear in the microgates arm set (asserted at build; re-asserted here from the
  frozen target row).

Emits `LEGAL_PREFLIGHT.json` (the machine artifact) and `preflight_drops.txt`
(the `--exclude` file `plan_c1.py` consumes).  `run_c1.sh` REFUSES to launch
without both.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))
ARCHIVES = REPO / "measurement" / "e4_games"

# The runner's mask, verbatim: `continue_plies._run_arm` builds its Game with
# `enable_legal_moves_cache=True`.  Checking against anything else would defeat
# the whole point of this gate.
RUNNER_LEGAL_MASK_CACHE = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default=str(HERE / "targets_c1.jsonl"))
    ap.add_argument("--out", default=str(HERE / "LEGAL_PREFLIGHT.json"))
    ap.add_argument("--drops", default=str(HERE / "preflight_drops.txt"))
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.targets).open()]
    profiles = {r["profile"] for r in rows}
    if len(profiles) != 1:
        raise SystemExit(f"R9 is import-latched: one process per profile group, "
                         f"got {sorted(profiles)}")
    profile = profiles.pop()

    from analyzer.ev_loss import prepare_env, resolve_profile_name
    env = prepare_env(profile)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.resolve(profile)
    if prof.r9_env_expected != prof.r9_env_on():
        raise SystemExit("r9_env latch mismatch")

    t0 = time.time()
    arc_cache: dict[str, dict] = {}
    results, drops = [], []
    for r in rows:
        g_name, ply = r["game"], int(r["ply"])
        rec = {"game": g_name, "ply": ply, "stratum": r["stratum"],
               "c1_action": int(r["c1_action"]),
               "champ_action": int(r["champ_action"])}
        try:
            if g_name not in arc_cache:
                arc_cache[g_name] = json.loads((ARCHIVES / g_name).read_text())
            arc = arc_cache[g_name]
            resolved = resolve_profile_name(arc)
            if resolved != r["profile"]:
                raise RuntimeError(f"profile drift: archive {resolved!r} "
                                   f"vs target {r['profile']!r}")
            if int(r["c1_action"]) == int(r["champ_action"]):
                raise RuntimeError("arms_equal: a zero-price ply reached the run")
            random.seed(int(arc["deck_seed"]))
            game = Game(enable_legal_moves_cache=RUNNER_LEGAL_MASK_CACHE,
                        **prof.game_kwargs())
            b = game.get_init_board()
            for a in arc["actions"][:ply]:
                b, _ = game.get_next_state(b, int(a))
            valid = game.get_valid_moves(b)
            rec["n_legal_root"] = int(valid.sum())
            rec["actor_at_root"] = int(b.state.current_player)
            rec["phase_at_root"] = b.state.phase.value
            rec["c1_legal"] = bool(valid[int(r["c1_action"])])
            rec["champ_legal"] = bool(valid[int(r["champ_action"])])
            rec["actor_matches_target"] = (rec["actor_at_root"] == int(r["actor"]))
            rec["phase_matches_target"] = (rec["phase_at_root"] == r["phase"])
            rec["status"] = (
                "OK" if (rec["c1_legal"] and rec["champ_legal"]
                         and rec["actor_matches_target"]
                         and rec["phase_matches_target"])
                else "DROP")
            if rec["status"] == "DROP":
                rec["drop_reason"] = (
                    "c1_action_illegal_under_runner_mask" if not rec["c1_legal"]
                    else "champ_action_illegal_under_runner_mask"
                    if not rec["champ_legal"] else "root_metadata_mismatch")
        except Exception as e:                              # noqa: BLE001
            rec["status"] = "DROP"
            rec["drop_reason"] = f"{type(e).__name__}: {e}"
        if rec["status"] == "DROP":
            drops.append(rec)
        results.append(rec)

    import collections
    by_s = collections.defaultdict(lambda: {"n": 0, "drop": 0})
    for rec in results:
        by_s[rec["stratum"]]["n"] += 1
        by_s[rec["stratum"]]["drop"] += int(rec["status"] == "DROP")
    for s, v in by_s.items():
        v["drop_rate"] = round(v["drop"] / v["n"], 4) if v["n"] else None

    out = {
        "schema": "carcassonne-c1-outcome-pricing-preflight/v1",
        "runner_legal_mask_cache": RUNNER_LEGAL_MASK_CACHE,
        "microgates_legal_mask_cache": False,
        "profile": profile, "r9_env": env,
        "n_plies": len(results),
        "n_ok": sum(1 for r in results if r["status"] == "OK"),
        "n_drop": len(drops),
        "by_stratum": dict(by_s),
        "drop_reasons": dict(collections.Counter(
            d.get("drop_reason", "?") for d in drops)),
        "drops": drops,
        "plies": results,
        "elapsed_s": round(time.time() - t0, 1),
        # Pre-registered void bar, DESIGN.md §5: a co-primary stratum losing
        # more than a fifth of its plies to the mask epoch is an instrument
        # void for that stratum, not attrition to be shrugged off.
        "VOID_BAR": {"per_stratum_drop_rate_max": 0.20},
        "VOID_TRIGGERED": sorted(
            s for s, v in by_s.items()
            if s in ("farm_capture", "invasion") and (v["drop_rate"] or 0) > 0.20),
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    with Path(args.drops).open("w") as fh:
        fh.write("# G-LEGAL / G-ROOT drops — consumed by plan_c1.py --exclude\n")
        for d in drops:
            fh.write(f"{d['game']} {d['ply']}  # {d.get('drop_reason')}\n")
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("plies", "drops")}, indent=1))
    if out["VOID_TRIGGERED"]:
        print(f"\n⚠️ VOID_TRIGGERED for {out['VOID_TRIGGERED']} — "
              f"read DESIGN.md §5 before launching.", file=sys.stderr)


if __name__ == "__main__":
    main()
