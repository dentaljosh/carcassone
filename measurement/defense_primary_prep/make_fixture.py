#!/usr/bin/env python3
"""Bank the pytest fixtures FROM THE REAL EMITTERS (the fixture trap).

A hand-written fixture proves the test agrees with whoever wrote the test.  These
fixtures are the classifier's and the counterfactual stage's own output on two
real archives — one champion game, one Carcasum game — copied verbatim, with a
provenance stamp recording exactly which emitter produced them.

    ./run_fixture.sh          # regenerate (only when the contract legitimately moves)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIX = HERE / "selftest_fixture"

CHAMPION_GAME = "1787835876_219596.json"     # 3 invasions / 3 defense / 1 farm / 3 control
CARCASUM_GAME = "1788178736_589408.json"     # 4 invasions / 4 defense / 1 farm / 4 control


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    FIX.mkdir(parents=True, exist_ok=True)
    games = f"{CHAMPION_GAME},{CARCASUM_GAME}"

    cand = FIX / "candidates_fixture.jsonl"
    ledger = FIX / "ledger_fixture.jsonl"
    man = FIX / "manifest_fixture.json"

    for stage, extra in (("classify", ["--out", str(cand), "--manifest", str(man)]),
                         ("counterfactual", ["--candidates", str(cand),
                                             "--out", str(ledger),
                                             "--manifest", str(FIX / "manifest_cf_fixture.json"),
                                             "--out-dir", str(FIX)])):
        cmd = [str(HERE / "run_census.sh"), stage, "--workers", str(args.workers),
               "--games", games] + extra
        r = subprocess.run(cmd, text=True, capture_output=True)
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            raise SystemExit(f"fixture emitter failed at --stage {stage}")

    prov = {
        "schema": "defense-primary-fixture-provenance/v1",
        "written_at": int(time.time()),
        "how": "emitted by census_new_plies.py --stage classify then --stage "
               "counterfactual on two REAL e4_games archives; copied verbatim. "
               "Never hand-edited — a hand-written fixture only proves the test "
               "agrees with whoever wrote the test.",
        "archives": {
            "champion": {"game": CHAMPION_GAME,
                         "sha256": sha(REPO / "measurement/e4_games" / CHAMPION_GAME)},
            "carcasum": {"game": CARCASUM_GAME,
                         "sha256": sha(REPO / "measurement/e4_games" / CARCASUM_GAME)},
        },
        "outputs": {p.name: sha(p) for p in sorted(FIX.glob("*.jsonl"))},
        "emitter": "measurement/defense_primary_prep/census_new_plies.py",
        "code_commit": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True).stdout.strip() or None,
    }
    (FIX / "FIXTURE_PROVENANCE.json").write_text(json.dumps(prov, indent=1))
    print(json.dumps(prov, indent=1))


if __name__ == "__main__":
    main()
