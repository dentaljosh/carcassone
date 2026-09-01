#!/usr/bin/env python3
"""DEFENSE-PRIMARY accrual check — RUN THIS AT EVERY E4 PULL.

This is the standing prereg's trigger reader (`PREREG.md` §5).  It brings the
NEW-PLIES ledger up to date with whatever archives the pull added, prints the
running defense accrual against the frozen trigger, and exits with a status a
runbook or a heartbeat can branch on.

    ./run_accrual_check.sh                # update the ledger, then report
    ./run_accrual_check.sh --no-update    # report the banked ledger only

EXIT CODES  (frozen in PREREG_CONSTANTS.json)
    0   TRIGGER FIRED  -> the pre-registered DEFENSE-PRIMARY read is authorized.
                          A fired prereg branch IS the authorization: launch it.
    1   not yet        -> report the count and the gap. No action.
    3   ERROR/refusal  -> a gate refused. Fix it; never interpret a refusal as
                          "not yet".

⛔ It reads no price and computes no price.  The trigger must not be a selection
on the outcome, so nothing on this path may look at one.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import census_new_plies as C                                     # noqa: E402
from summarize_ledger import budget_epoch                        # noqa: E402

CONST = json.loads((HERE / "PREREG_CONSTANTS.json").read_text())
LEDGER = HERE / "NEW_PLIES.jsonl"
CANDIDATES = HERE / "candidates_fixed_v1.jsonl"


def divergence_generator(row: dict) -> str:
    """Which mechanism produced this ply's divergence — a DECLARED stratifier.

    `same_budget_rebuild`   the archive's mover WAS the champion at the pinned
                            budget, so a disagreement is a rebuild/era artefact
                            (E-1a's own generator).
    `cross_budget_champion` the mover was the champion at a DIFFERENT budget
                            (and possibly with the tie arbiter armed), so the
                            disagreement carries a budget term E-1a's did not.
    `cross_agent`           the mover was not the champion at all (Carcasum), so
                            the disagreement is between two different agents.
    """
    if row["corpus"] != "champion_game":
        return "cross_agent"
    era = row.get("archive_era") or {}
    k = era.get("played_k_dets_effective") or era.get("k_dets_effective")
    s = era.get("played_sims_effective") or era.get("sims_effective")
    arb = bool(era.get("tiearb_enabled"))
    pin = C.PINNED_K_DETS * C.PINNED_SIMS_PER_DET
    if k and s and int(k) * int(s) == pin and not arb:
        return "same_budget_rebuild"
    return "cross_budget_champion"


def run_census(stage: str, workers: int, games: list[str] | None) -> None:
    cmd = [str(HERE / "run_census.sh"), stage, "--workers", str(workers)]
    if games:
        cmd += ["--games", ",".join(games)]
    if stage == "counterfactual":
        cmd += ["--candidates", str(CANDIDATES)]
    r = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise C.Refusal(f"census --stage {stage} exited {r.returncode}")


def load_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.open() if l.strip()]


def report(rows: list[dict], trigger: int, champ_leg: int) -> dict:
    div = [r for r in rows if r.get("divergent")]
    d = [r for r in div if r["stratum"] == "defense"]
    n = len(d)
    by_corpus = Counter(r["corpus"] for r in d)
    n_champ = by_corpus.get("champion_game", 0)
    out = {
        "schema": "defense-primary-accrual/v1",
        "checked_at": int(time.time()),
        "ledger": str(LEDGER.relative_to(REPO)),
        "n_games_in_ledger": len({r["game"] for r in rows}),
        "n_censused_plies": len(rows),
        "n_divergent_plies": len(div),
        "DEFENSE_ACCRUAL": n,
        "TRIGGER_N_DEFENSE": trigger,
        "REMAINING": max(0, trigger - n),
        "FIRED": n >= trigger,
        "by_corpus": dict(by_corpus),
        "champion_leg": {"n": n_champ, "threshold": champ_leg,
                         "reads_own_branch": n_champ >= champ_leg},
        "by_budget_epoch": dict(Counter(budget_epoch(r) for r in d)),
        "by_divergence_generator": dict(Counter(divergence_generator(r) for r in d)),
        "n_game_clusters": len({r["game"] for r in d}),
        "divergent_by_corpus_stratum": {
            f"{c}/{s}": k for (c, s), k in
            sorted(Counter((r["corpus"], r["stratum"]) for r in div).items())},
        "all_strata_divergent_available_to_price": {
            s: k for s, k in sorted(Counter(r["stratum"] for r in div).items())},
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-update", action="store_true",
                    help="report the banked ledger without censusing new archives")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=str(HERE / "ACCRUAL.json"))
    ap.add_argument("--ledger-only-count", action="store_true",
                    help="print just the integer accrual and exit 0")
    args = ap.parse_args()

    try:
        rows = load_ledger()
        have = {r["game"] for r in rows}
        kept, _rejected, _prov = C.eligible_archives(REPO)
        missing = sorted({p.name for p in kept} - have)

        if missing and not args.no_update:
            print(f"[accrual] {len(missing)} eligible archive(s) not in the ledger "
                  f"— censusing: {missing}", flush=True)
            run_census("classify", args.workers, None)
            run_census("counterfactual", args.workers, None)
            rows = load_ledger()
            have = {r["game"] for r in rows}
            still = sorted({p.name for p in kept} - have)
            if still:
                raise C.Refusal(f"G-LEDGER: {still} still absent after the census")
        elif missing:
            print(f"[accrual] ⚠️ {len(missing)} eligible archive(s) NOT in the ledger "
                  f"and --no-update was given: {missing}", flush=True)

        C.check_no_price(rows)
        rep = report(rows, int(CONST["TRIGGER_N_DEFENSE"]),
                     int(CONST["TRIGGER_N_DEFENSE_CHAMPION_LEG"]))
        if args.ledger_only_count:
            print(rep["DEFENSE_ACCRUAL"])
            return 0
        Path(args.out).write_text(json.dumps(rep, indent=1))
        print(json.dumps(rep, indent=1))
        n, t = rep["DEFENSE_ACCRUAL"], rep["TRIGGER_N_DEFENSE"]
        if rep["FIRED"]:
            print(f"\n⭐ TRIGGER FIRED — {n}/{t} new divergent defense plies. "
                  "The DEFENSE-PRIMARY read (PREREG.md §4) is AUTHORIZED; a fired "
                  "prereg branch is the authorization — run it.")
            return 0
        print(f"\nnot yet — {n}/{t} new divergent defense plies "
              f"({rep['REMAINING']} to go, over {rep['n_game_clusters']} game "
              f"clusters). No action.")
        return 1
    except C.Refusal as e:
        print(f"\n⛔ REFUSAL — {e}\nA refusal is NOT 'not yet'. Fix it.",
              file=sys.stderr)
        return 3
    except Exception as e:                                       # noqa: BLE001
        print(f"\n⛔ ERROR — {type(e).__name__}: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
