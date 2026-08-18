#!/usr/bin/env python3
"""DESIGN §7's `c`-REMEASURE OBLIGATION, made an artifact instead of a promise.

§7 binds the run to re-measure the per-playout cost of BOTH judges (four smokes:
{S1 `--m 128`, S2 `--m 32`} x {`clair-puct`, `tier1-greedy`}) and the per-game
cost of the GENERATION leg (a separate timed 10-game smoke), and says
"realized-vs-committed for all three legs is written to
`RUN/RUN_MANIFEST_S1.json`". It does not name a key, so this module defines and
emits one: **`RUN_MANIFEST_S1.json::c_remeasure`**, merged into the manifest
non-destructively (and created as a stub when the manifest does not exist yet —
the obligation is discharged BEFORE the S1 IF leg starts, hence before
`run_tiletie` writes that manifest).

Three rules, implemented literally:

  1. The figure of record is **`c_worker_secs_per_playout`** (Σ`elapsed_secs` /
     playouts). ⚠️ **NEVER `worker_secs_per_playout`**, the wall x W figure the
     emitter's own banner says not to cost from (inflated ~1.9x): a healthy
     smoke read at that key would HALT a healthy run (REVIEW_R1 §5).
  2. `c_worker_secs_per_playout` `null` or `0` is a **FAILED SMOKE** — not a
     cheap leg, not a HALT. Re-run the smoke; the long leg does not start until
     a real number exists (REVIEW_R2 §N10).
  3. **HALT IS ONE-SIDED.** Halt and re-price only when a realized `c` is
     **> 25% COSTLIER** than committed. Cheaper is recorded, never a halt.

This module computes NO strength statistic and reads NO outcome: a smoke
manifest is outcome-free by construction (verified field-by-field in REVIEW_R1).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --- the committed DESIGN §7 budget ----------------------------------------- #
COMMITTED = {
    "arb": {"c_worker_secs_per_playout": 0.178232,
            "unit": "worker-s/playout", "judge": "tier1-greedy",
            "note": "rust, W30 contended"},
    "if": {"c_worker_secs_per_playout": 2.35,
           "unit": "worker-s/playout", "judge": "clair-puct",
           "smoke_indicated": 1.2313,
           "note": "banked elapsed_secs, PLAUSIBLY THE W30-CONTENDED RUST "
                   "PRICE. The smoke-indicated 1.2313 (idle box, M=32, "
                   "sims=100) is 1.91x cheaper; that gap is NOT resolved here "
                   "and NOT guessed at — the pre-run remeasure settles it. The "
                   "ETA is sized off the COMMITTED figure, which cannot "
                   "undershoot the envelope (R4-5)"},
    "generation": {"worker_secs_per_game": 372.0,
                   "unit": "worker-s/game",
                   "measured": 297.6,
                   "note": "R4-5, RE-BASED ON MEASUREMENT: 297.6 measured by "
                           "the fresh same-config GEN smoke, x1.25 margin in "
                           "the direction that cannot under-commit. R3 carried "
                           "990 inherited; the one-sided HALT now trips above "
                           "465.0 worker-s/game (~1.56x the measured rate) — a "
                           "real trigger, not a formality. Carrying 990 forward "
                           "would have re-manufactured exactly the "
                           "cost-model-miss disclosure this campaign has "
                           "already written twice"},
}
HALT_RATIO = 1.25            # >25% COSTLIER, one-sided
TOTAL_COMMITTED_WORKER_H = 1174.0
REPRICE_AUTHORIZATION_WORKER_H = 1500.0


def _judge_of(manifest: dict, path: Path) -> str:
    """`arb` or `if`, from the smoke manifest's own judge field, else the
    filename (`SMOKE_MANIFEST_S1_tier1-greedy.json`)."""
    j = (manifest.get("judge") or manifest.get("smoke_judge")
         or "").strip().lower()
    if not j:
        j = path.stem.split("_")[-1].lower()
    return "arb" if "tier1" in j else ("if" if "clair" in j else j)


def read_smoke(path) -> dict:
    """One smoke manifest -> the §7 reading. Presence and shape only."""
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "present": False, "failed_smoke": True,
                "reason": "smoke manifest absent"}
    man = json.loads(path.read_text())
    c = man.get("c_worker_secs_per_playout")
    failed = c is None or (isinstance(c, (int, float)) and float(c) == 0.0)
    return {
        "path": str(path), "present": True,
        "judge": _judge_of(man, path),
        "stratum": "S2" if "_S2_" in path.name else "S1",
        "c_worker_secs_per_playout": c,
        "m_worlds": man.get("m_worlds"),
        "arb_backend": man.get("arb_backend"),
        "failed_smoke": bool(failed),
        "reason": ("c_worker_secs_per_playout is null/0 — a FAILED SMOKE "
                   "(no per-position elapsed_secs collected); re-run it. "
                   "NOT a cheap leg and NOT a HALT." if failed else None),
        # recorded so a later reader can SEE that the inflated key was not used
        "worker_secs_per_playout_NOT_COSTED_FROM": man.get("worker_secs_per_playout"),
    }


def read_gen_smoke(path) -> dict:
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "present": False, "failed_smoke": True,
                "reason": "GEN_SMOKE.json absent"}
    man = json.loads(path.read_text())
    w = man.get("worker_secs_per_game")
    failed = w is None or (isinstance(w, (int, float)) and float(w) == 0.0)
    return {"path": str(path), "present": True,
            "worker_secs_per_game": w,
            "n_games": man.get("n_games"),
            "failed_smoke": bool(failed),
            "reason": ("worker_secs_per_game is null/0 — a FAILED generation "
                       "smoke; re-run it." if failed else None)}


def _leg(name: str, realized, committed_key: str) -> dict:
    committed = COMMITTED[name][committed_key]
    ratio = (float(realized) / committed
             if realized not in (None, 0) and committed else None)
    halt = bool(ratio is not None and ratio > HALT_RATIO)
    return {
        "committed": committed, "realized": realized, "ratio": ratio,
        "unit": COMMITTED[name]["unit"],
        "halt_fired": halt,
        "direction": (None if ratio is None else
                      ("COSTLIER" if ratio > 1.0 else "cheaper")),
        "rule": "HALT IS ONE-SIDED — halt only when realized/committed > 1.25; "
                "cheaper is recorded, never a halt",
    }


def build_block(smokes, gen_smoke) -> dict:
    """The `c_remeasure` block: all three legs, realized vs committed."""
    reads = [read_smoke(p) for p in smokes]
    gen = read_gen_smoke(gen_smoke) if gen_smoke else {
        "present": False, "failed_smoke": True,
        "reason": "no --gen-smoke given"}

    per_judge = {}
    for r in reads:
        if not r.get("present") or r.get("failed_smoke"):
            continue
        key = r["judge"]
        # the COSTLIEST realized reading across strata governs (one-sided)
        cur = per_judge.get(key)
        if cur is None or float(r["c_worker_secs_per_playout"]) > float(cur):
            per_judge[key] = r["c_worker_secs_per_playout"]

    legs = {
        "arb": _leg("arb", per_judge.get("arb"), "c_worker_secs_per_playout"),
        "if": _leg("if", per_judge.get("if"), "c_worker_secs_per_playout"),
        "generation": _leg("generation", gen.get("worker_secs_per_game"),
                           "worker_secs_per_game"),
    }
    failed = [r["path"] for r in reads if r.get("failed_smoke")]
    if gen.get("failed_smoke"):
        failed.append(str(gen.get("path", "GEN_SMOKE.json")))
    halt = any(v["halt_fired"] for v in legs.values())
    return {
        "figure_of_record": "c_worker_secs_per_playout (Σ elapsed_secs / "
                            "playouts) — NOT worker_secs_per_playout",
        "smokes": reads,
        "generation_smoke": gen,
        "legs": legs,
        "failed_smokes": failed,
        "n_smokes_expected": 4,
        "n_smokes_read": sum(1 for r in reads if r.get("present")),
        "halt_fired": bool(halt),
        "ok": bool(not failed and not halt),
        "total_committed_worker_h": TOTAL_COMMITTED_WORKER_H,
        "reprice_authorization_worker_h": REPRICE_AUTHORIZATION_WORKER_H,
    }


def merge_into_manifest(manifest_path, block: dict) -> dict:
    """Non-destructive merge of `c_remeasure` into `RUN_MANIFEST_S1.json`."""
    p = Path(manifest_path)
    doc = {}
    if p.is_file():
        doc = json.loads(p.read_text())
        if not isinstance(doc, dict):
            raise SystemExit(f"REFUSING: {p} is not a JSON object")
    else:
        doc = {"stub": "created by c_remeasure.py before the S1 leg launched; "
                       "run_tiletie merges its own keys in at launch"}
    doc["c_remeasure"] = block
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True))
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--smoke", action="append", default=None, required=True,
                    help="SMOKE_MANIFEST_{S1,S2}_<judge>.json (repeat x4)")
    ap.add_argument("--gen-smoke", default=None,
                    help="RUN/corpus/GEN_SMOKE.json")
    ap.add_argument("--manifest", required=True,
                    help="RUN/RUN_MANIFEST_S1.json — merged into, not replaced")
    a = ap.parse_args(argv)

    block = build_block(a.smoke, a.gen_smoke)
    merge_into_manifest(a.manifest, block)
    for name, leg in sorted(block["legs"].items()):
        print(f"[c-remeasure] {name:11s} committed={leg['committed']} "
              f"realized={leg['realized']} ratio={leg['ratio']} "
              f"halt={leg['halt_fired']}")
    print(f"[c-remeasure] -> {a.manifest}::c_remeasure")
    if block["failed_smokes"]:
        print(f"\n{'=' * 70}\n[c-remeasure] ***** FAILED SMOKE(S) *****\n"
              f"[c-remeasure] {len(block['failed_smokes'])} smoke(s) produced no "
              f"c_worker_secs_per_playout / worker_secs_per_game.\n"
              f"[c-remeasure] This is NOT a cheap leg and NOT a HALT — RE-RUN "
              f"the smoke. The long leg does not start until a real number "
              f"exists.\n{'=' * 70}", file=sys.stderr)
        return 2
    if block["halt_fired"]:
        print(f"\n{'=' * 70}\n[c-remeasure] ***** HALT — RE-PRICE REQUIRED *****\n"
              f"[c-remeasure] a realized c is >25% COSTLIER than committed.\n"
              f"[c-remeasure] A re-priced run above "
              f"{REPRICE_AUTHORIZATION_WORKER_H} worker-h needs FRESH OWNER "
              f"AUTHORIZATION.\n{'=' * 70}", file=sys.stderr)
        return 1
    print("[c-remeasure] PASS — no leg is >25% costlier than committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
