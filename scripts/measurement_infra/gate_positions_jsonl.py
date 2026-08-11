#!/usr/bin/env python3
"""GATE — the `--positions-jsonl` / `--rules-profile` adapter changes NOTHING it touches.

The precedent is `--oracle-policy`'s own (oracle_score_pilot.py banner, 2026-07-28): the
default construction was not ASSERTED unchanged, it was PROVEN by re-scoring banked
positions with default flags and diffing every value field against the banked records.
This gate does that, and one thing more.

  LEG 1 — DEFAULT PATH UNCHANGED. Re-score the first 2 positions of the banked n=100
          oracle-pilot draw (`--n 100 --head 2`, i.e. a strict prefix subset) with
          DEFAULT flags on today's code, and diff every non-timing field against
          /mnt/c/carc-shared/classical_search/oracle_score_pilot/records/.

  LEG 2 — THE ADAPTER IS THE SAME INSTRUMENT. Feed those SAME two positions through the
          new `--positions-jsonl` input mode, with pick_a/pick_b in the same order, and
          diff against the same banked records. This is the leg that matters: it proves
          the new input path is not a different ruler, only a different way of naming the
          positions. `rid` is carried across verbatim because it seeds the CRN worlds.

Timing fields (`elapsed_secs`, `wall_secs`) and the fields that describe the INPUT MODE
rather than the measurement are excluded — they are meant to differ.

Writes measurement/analyzer_evloss_20260805/farmwar/GATE_POSITIONS_JSONL.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "scripts/measurement_infra/oracle_score_pilot.py"
BANK = Path("/mnt/c/carc-shared/classical_search/oracle_score_pilot")
OUT = REPO / "measurement/analyzer_evloss_20260805/farmwar/GATE_POSITIONS_JSONL.json"

#: Everything a re-score must reproduce EXACTLY. `values_*` are the oracle's raw
#: per-world margins; `delta`/`within_var`/`crn_*` are what the read-out is built from.
VALUE_FIELDS = (
    "values_a", "values_b", "delta", "mean_a", "mean_b", "within_var", "within_se",
    "unpaired_var", "crn_var_reduction", "per_world_delta", "crn_verified",
    "distinct_afterstates", "afterstate_deck_hash_a", "afterstate_deck_hash_b",
    "afterstate_board_key_a", "afterstate_board_key_b", "playout_plies_a",
    "playout_plies_b", "world_seeds", "playout_seeds", "m", "ok", "checksum_ok",
    "pick_a", "pick_b", "root_player", "deck_seed", "ply", "oracle_sims",
    "oracle_policy", "world_seed_salt",
)


def _run(argv: list) -> None:
    print("[gate] $", " ".join(str(a) for a in argv), flush=True)
    r = subprocess.run([sys.executable, str(PILOT)] + [str(a) for a in argv],
                       cwd=str(REPO))
    if r.returncode != 0:
        raise SystemExit(f"[gate] pilot exited {r.returncode}")


def _diff(banked: dict, got: dict, rid: str) -> list:
    out = []
    for f in VALUE_FIELDS:
        if banked.get(f) != got.get(f):
            out.append({"rid": rid, "field": f,
                        "banked": banked.get(f), "got": got.get(f)})
    return out


def main() -> int:
    rids = json.loads((BANK / "manifest.json").read_text())["sampling"]["rids"][:2]
    banked = {r: json.loads((BANK / "records" / f"{r}.json").read_text()) for r in rids}

    tmp = Path(tempfile.mkdtemp(prefix="farmwar_gate_"))
    res = {"gate": "oracle_score_pilot --positions-jsonl adapter", "rids": rids,
           "value_fields_checked": len(VALUE_FIELDS)}

    # ---- LEG 1: default flags, default input mode ------------------------------ #
    _run(["--n", 100, "--head", 2, "--workers", 2,
          "--out-root", tmp, "--out-subdir", "leg1"])
    l1 = [_diff(banked[r], json.loads((tmp / "leg1/records" / f"{r}.json").read_text()), r)
          for r in rids]
    res["leg1_default_path"] = {
        "mode": "default (--run-dir bank), no new flag set",
        "mismatches": [m for d in l1 for m in d],
        "field_checks": len(VALUE_FIELDS) * len(rids),
    }

    # ---- LEG 2: the same two positions through --positions-jsonl ---------------- #
    roots = {}
    for line in (Path(json.loads((BANK / "manifest.json").read_text())
                      ["source"]["roots"])).read_text().splitlines():
        if line.strip():
            o = json.loads(line)
            roots[f"s{int(o['deck_seed'])}_p{int(o['ply'])}"] = o
    pos = tmp / "positions.jsonl"
    with pos.open("w") as fh:
        for r in rids:
            b = banked[r]
            root = roots[b["root_id"]]
            fh.write(json.dumps({
                "rid": r, "root_id": b["root_id"], "deck_seed": b["deck_seed"],
                "ply": b["ply"], "salt": b["salt"],
                "actions": [int(a) for a in root["actions"]],
                "checksum": root.get("checksum"),
                "pick_a": b["pick_a"], "pick_b": b["pick_b"],
                "root_player": b["root_player"],
            }) + "\n")
    _run(["--positions-jsonl", pos, "--workers", 2,
          "--out-root", tmp, "--out-subdir", "leg2"])
    l2 = [_diff(banked[r], json.loads((tmp / "leg2/records" / f"{r}.json").read_text()), r)
          for r in rids]
    res["leg2_positions_jsonl"] = {
        "mode": "--positions-jsonl with the same rids, same arm order",
        "mismatches": [m for d in l2 for m in d],
        "field_checks": len(VALUE_FIELDS) * len(rids),
    }

    res["verdict"] = ("PASS" if not (res["leg1_default_path"]["mismatches"]
                                     or res["leg2_positions_jsonl"]["mismatches"])
                      else "FAIL")
    res["scratch_dir"] = str(tmp)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "scratch_dir"}, indent=2))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
