#!/usr/bin/env python3
"""pilot_report.py — DESIGN §10 cost/integrity pilot report for tiearb2_20260816.

⚠️ DISCLOSURE DISCIPLINE, ENFORCED BY CONSTRUCTION.
This script reads ONLY: `elapsed_secs`, `ok`, `crn_verified`, `checksum_ok`,
`pick_a`, `pick_b`, `m`, `rid`, `world_seeds`, `playout_seeds` — plus a **sha256
over (values_a, values_b, world_seeds, playout_seeds)** for the `G-REPRO`
bit-reproduction check, of which **only the COUNT of matching legs is emitted**.

`values_a`, `values_b` and `per_world_delta` are consumed ONLY inside
`_repro_digest()`, which returns a hex digest and nothing else; every other
value-bearing field (`delta`, `mean_a`, `mean_b`, `within_var`, `within_se`,
`unpaired_var`, `crn_var_reduction`, `sd_*`, `z_*`) is in `FORBIDDEN` and is
asserted absent from the emitted JSON before the file is written. The leg
`summary.json` files — which DO carry `mean_delta_pts`, `sd_delta_positions` and
`z_pilot_observed` — are **never opened**.

Its outputs are the abort decision and `c_tier1`, which fixes `B*` by the
mechanical cost-only rule of DESIGN §7.2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

# ---- DESIGN §7.1 constants (published, not measured by this run) ----------- #
T_CHAMP_SECS = 13.7552      # champion k8x1376 = 11008 sims, SEQUENTIAL, this box
T_PHONE_SECS = 1.551        # the shipped phone champion, for Stage-1 comparability
RHO_BAR = 1.20              # the N4 trigger currency
B_LADDER = (1, 2, 4, 8, 16)
TIED_PLIES_PER_GAME = 22.96
MOVES_PER_GAME = 72.0

#: The 2026-08-14 OOF cost pilot's realized leg count — the G-REPRO denominator.
#: VERIFIED ON DISK, not assumed:
#:   /mnt/c/carc-shared/tiletie_oof_20260814/pilot/tier1-greedy/
#:     fixed_v1/leg{1,2,3,4} = 2+1+1+1,  walled/leg{1,2,3,4} = 18+11+8+1  => 43
#: (20 pilot rids, 2.15 legs each; Stage 1 read 43/43 against the same reference.)
#:
#: ⚠️ IT MUST BE A COMMITTED CONSTANT, NOT `len(new)`. If G-REPRO's expected count
#: were taken from the number of records this run happened to write, a TRUNCATED
#: pilot would satisfy `repro == expected` trivially and the gate would wave
#: through a run that never scored its legs. The report also emits the count
#: actually found on the reference root, so a drift is visible rather than
#: assumed away.
EXPECT_LEGS = 43

#: value-bearing keys that must never reach the emitted report
FORBIDDEN = {
    "values_a", "values_b", "per_world_delta", "delta", "mean_a", "mean_b",
    "within_var", "within_se", "unpaired_var", "crn_var_reduction",
    "mean_delta_pts", "sd_delta_positions", "z_pilot_observed",
    "se_mean_delta", "var_between_positions_est", "mean_within_position_var",
}


def _repro_digest(rec: dict) -> str:
    """sha256 over (values_a, values_b, world_seeds, playout_seeds).

    The ONLY place a value list is touched. Returns a hex digest; the caller
    compares digests and emits a COUNT. No value escapes this function.
    """
    h = hashlib.sha256()
    for key in ("values_a", "values_b", "world_seeds", "playout_seeds"):
        h.update(key.encode())
        h.update(repr(rec.get(key)).encode())
    return h.hexdigest()


def load_records(root: Path) -> dict[str, dict]:
    """rid+leg -> record, over <judge>/<profile>/leg<r>/records/<rid>.json."""
    out: dict[str, dict] = {}
    for p in sorted(root.rglob("records/*.json")):
        leg = p.parent.parent.name          # "leg3"
        rec = json.loads(p.read_text())
        out[f"{rec['rid']}::{leg}"] = rec
    return out


def b_star_block(a_bar: float, c_tier1: float) -> dict:
    """DESIGN §7.2, mechanical and cost-only.

        rho_wall(B) = A_bar * B * c_tier1 / T_CHAMP
        B* = max{B in ladder : rho_wall(B) <= 1.20}, else 1
    """
    ladder = {}
    for b in B_LADDER:
        cost = a_bar * b * c_tier1
        ladder[str(b)] = {
            "playouts_per_tied_ply": round(a_bar * b, 4),
            "worker_secs_per_tied_ply": round(cost, 4),
            "rho_wall": round(cost / T_CHAMP_SECS, 4),
            "rho_amortized": round(cost / T_CHAMP_SECS
                                   * TIED_PLIES_PER_GAME / MOVES_PER_GAME, 4),
            "rho_phone": round(cost / T_PHONE_SECS, 4),
            "deployable": bool(cost / T_CHAMP_SECS <= RHO_BAR),
        }
    ok = [b for b in B_LADDER if ladder[str(b)]["deployable"]]
    b_star = max(ok) if ok else 1
    return {
        "rule": ("B* = max{B in {1,2,4,8,16} : rho_wall(B) <= 1.20}, else 1. "
                 "rho_wall(B) = A_bar * B * c_tier1 / 13.7552. COST ONLY — no "
                 "arbitration, headroom or pricing statistic enters it."),
        "A_bar": a_bar,
        "c_tier1_worker_s_per_playout": c_tier1,
        "t_champ_secs": T_CHAMP_SECS,
        "rho_bar": RHO_BAR,
        "ladder": ladder,
        "any_deployable": bool(ok),
        "B_star": b_star,
        "rho_wall_bstar": ladder[str(b_star)]["rho_wall"],
        "DEPLOY": bool(ladder[str(b_star)]["deployable"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    ap.add_argument("--new-root", default="/mnt/c/carc-shared/tiearb2_20260816/pilot")
    ap.add_argument("--primary-root", default="/mnt/c/carc-shared/tiletie_oof_20260814/pilot",
                    help="the adjudicated 2026-08-14 OOF pilot records G-REPRO compares "
                         "against — Stage 1 used exactly this reference and read 43/43")
    ap.add_argument("--if-root", default="/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct",
                    help="the PRIMARY clair-puct records. The CROSS-JUDGE seed/arm "
                         "witness: it proves these tier1-greedy legs share CRN worlds "
                         "with the pricing judge, which a same-judge comparison cannot. "
                         "Pass '' to skip it (recorded as skipped).")
    ap.add_argument("--plan", default=str(here / "corpus/positions/POSITIONS_PLAN.json"),
                    help="the FRESH corpus plan, for A_bar")
    ap.add_argument("--expect-legs", type=int, default=EXPECT_LEGS,
                    help="G-REPRO's committed expected leg count (default 43, the "
                         "realized OOF pilot leg count verified on disk)")
    ap.add_argument("--out", default=str(here / "PILOT.json"))
    a = ap.parse_args()

    new = load_records(Path(a.new_root))
    pri = load_records(Path(a.primary_root))
    ifr = load_records(Path(a.if_root)) if a.if_root else {}
    if not new:
        print(f"[pilot_report] FATAL: no records under {a.new_root}", file=sys.stderr)
        return 2

    n_ok = n_failed = n_crn = n_ck = 0
    world_id = playout_id = arm_id = 0
    repro = 0
    missing: list[str] = []
    elapsed: list[float] = []
    playouts = 0
    if_world_id = if_playout_id = if_arm_id = 0
    if_missing: list[str] = []

    for key, rec in sorted(new.items()):
        n_ok += 1 if rec.get("ok") else 0
        n_failed += 0 if rec.get("ok") else 1
        n_crn += 1 if rec.get("crn_verified") else 0
        n_ck += 1 if rec.get("checksum_ok") else 0
        elapsed.append(float(rec.get("elapsed_secs") or 0.0))
        playouts += 2 * int(rec.get("m") or 0)          # two arms per leg

        # CROSS-JUDGE witness: same rid+leg under the PRIMARY clair-puct run.
        # DESIGN §4.5 -- world_seed(rid, j, salt) is keyed on the rid and the salt
        # and NEVER on the judge, so these must be bit-identical across judges.
        if ifr:
            q = ifr.get(key)
            if q is None:
                if_missing.append(key)
            else:
                if_world_id += 1 if rec.get("world_seeds") == q.get("world_seeds") else 0
                if_playout_id += 1 if rec.get("playout_seeds") == q.get("playout_seeds") else 0
                if_arm_id += 1 if (rec.get("pick_a"), rec.get("pick_b")) == (
                    q.get("pick_a"), q.get("pick_b")) else 0

        p = pri.get(key)
        if p is None:
            missing.append(key)
            continue
        world_id += 1 if rec.get("world_seeds") == p.get("world_seeds") else 0
        playout_id += 1 if rec.get("playout_seeds") == p.get("playout_seeds") else 0
        arm_id += 1 if (rec.get("pick_a"), rec.get("pick_b")) == (p.get("pick_a"),
                                                                 p.get("pick_b")) else 0
        repro += 1 if _repro_digest(rec) == _repro_digest(p) else 0

    n = len(new)
    n_expect = int(a.expect_legs)
    n_ref_on_disk = len(pri)
    c_tier1 = round(sum(elapsed) / playouts, 4) if playouts else None

    plan_path = Path(a.plan)
    if not plan_path.is_file():
        print(f"[pilot_report] FATAL: the FRESH corpus plan {plan_path} does not "
              f"exist, so A_bar is unavailable and B* cannot be frozen.",
              file=sys.stderr)
        return 2
    a_bar = json.loads(plan_path.read_text())["mean_arms"]

    abort = []
    if n != n_expect:
        abort.append(f"expected {n_expect} pilot legs, found {n}")
    if n_failed:
        abort.append(f"n_failed={n_failed} > 0")
    if n_crn != n:
        abort.append(f"crn_verified {n_crn}/{n}")
    if n_ck != n:
        abort.append(f"checksum_ok {n_ck}/{n}")
    if world_id != n or playout_id != n or arm_id != n:
        abort.append(f"seed/arm identity world={world_id} playout={playout_id} arm={arm_id} of {n}")
    # ⚠️ graded against the COMMITTED constant, never against len(new) -- a
    # truncated pilot must FAIL this, not satisfy it trivially.
    if repro != n_expect:
        abort.append(f"G-REPRO {repro}/{n_expect} bit-identical")
    if missing:
        abort.append(f"{len(missing)} record(s) with no OOF-pilot counterpart")
    if ifr and (if_world_id != n or if_playout_id != n or if_arm_id != n):
        abort.append(f"CROSS-JUDGE seed/arm identity vs clair-puct: world={if_world_id} "
                     f"playout={if_playout_id} arm={if_arm_id} of {n}")
    if ifr and if_missing:
        abort.append(f"{len(if_missing)} record(s) with no clair-puct counterpart")

    report = {
        "schema": "carcassonne-tiearb2-pilot/v1",
        "design_doc": "measurement/tiearb2_20260816/DESIGN.md",
        "scope": ("DESIGN §10 COST/INTEGRITY PILOT on SPENT-corpus positions. Reads ONLY "
                  "wall/elapsed/integrity and the G-REPRO bit-reproduction COUNT. No value, "
                  "mean, sd or delta was read from any record; the leg summary.json files "
                  "were never opened. Its only outputs are the abort decision and c_tier1, "
                  "which fixes B* by the cost-only rule of DESIGN §7.2."),
        "judge": "tier1-greedy",
        "backend": "python",
        "world_seed_salt": "tiletie-v1",
        "m": 32,
        "n_legs_records": n,
        "playouts": playouts,
        "integrity": {
            "records": n, "ok": n_ok, "n_failed": n_failed,
            "crn_verified": n_crn, "checksum_ok": n_ck,
            "world_seed_identical_to_primary": world_id,
            "playout_seed_identical_to_primary": playout_id,
            "arm_identical_to_primary": arm_id,
            "G_REPRO_bit_identical": repro,
            "G_REPRO_expected": n_expect,
            "G_REPRO_reference_records_found_on_disk": n_ref_on_disk,
            "G_REPRO_expected_matches_disk": bool(n_ref_on_disk == n_expect),
            "G_REPRO_missing_counterpart": missing,
            "cross_judge_witness": {
                "if_root": str(a.if_root) if a.if_root else None,
                "evaluated": bool(ifr),
                "world_seed_identical_to_clair_puct": if_world_id if ifr else None,
                "playout_seed_identical_to_clair_puct": if_playout_id if ifr else None,
                "arm_identical_to_clair_puct": if_arm_id if ifr else None,
                "missing_counterpart": if_missing,
                "why": ("DESIGN §4.5 -- world_seed(rid, j, salt) is keyed on the rid "
                        "and the salt and NEVER on the judge, so a tier1-greedy leg "
                        "and the clair-puct record for the same rid+leg must carry "
                        "bit-identical seed lists. A same-judge reproduction check "
                        "cannot show that; this one can."),
            },
            "note": ("G-REPRO compares a sha256 over (values_a, values_b, world_seeds, "
                     "playout_seeds) against the adjudicated 2026-08-14 OOF pilot "
                     "records for the same rid+leg. ONLY THE COUNT is reported -- a "
                     "digest is not a value and is not invertible. `G_REPRO_expected` "
                     "is the COMMITTED constant 43 (the realized OOF leg count, "
                     "verified on disk), never len(new): grading against len(new) "
                     "would let a truncated pilot satisfy the gate trivially. "
                     "`G_REPRO_reference_records_found_on_disk` reports what was "
                     "actually found, so a drift is visible rather than assumed away."),
        },
        "cost": {
            "sum_elapsed_secs": round(sum(elapsed), 2),
            "c_tier1_worker_s_per_playout": c_tier1,
            "median_record_secs": round(statistics.median(elapsed), 2) if elapsed else None,
            "max_record_secs": round(max(elapsed), 2) if elapsed else None,
            "stage1_pilot_c": 2.1236,
            "oof_pilot_c": 2.1783,
        },
        "b_star": b_star_block(a_bar, c_tier1),
        # ⚠️ MIRRORED AT TOP LEVEL ON PURPOSE. `analyze_tiearb2.read_pilot` looks
        # for `B_star` / `c_tier1_worker_s_per_playout` / `rho_wall_bstar` in
        # exactly three places -- the top level, `cost`, and `mechanical_rule` --
        # and NOT inside a `b_star` sub-block. Without these three keys the
        # analyser silently RE-DERIVES B* and stamps the read-out "⚠️ PILOT.json
        # carried no `B_star`", which would defeat the whole point of freezing it
        # here. Same values, one source: b_star_block().
        "B_star": b_star_block(a_bar, c_tier1)["B_star"],
        "rho_wall_bstar": b_star_block(a_bar, c_tier1)["rho_wall_bstar"],
        "c_tier1_worker_s_per_playout": c_tier1,
        "A_bar": a_bar,
        "abort": {
            "rule": ("DESIGN §10: n_failed>0 OR any crn_verified false OR any seed/arm "
                     "mismatch OR G-REPRO short of expected => ABORT; the fresh corpus is "
                     "not scored."),
            "triggered": bool(abort),
            "reasons": abort,
        },
    }

    leaked = FORBIDDEN & set(json.dumps(report).split('"'))
    if leaked:
        print(f"[pilot_report] FATAL: forbidden key(s) in report: {sorted(leaked)}",
              file=sys.stderr)
        return 3

    Path(a.out).write_text(json.dumps(report, indent=1, sort_keys=False))
    print(json.dumps(report, indent=1, sort_keys=False))
    if abort:
        print("\n" + "=" * 70)
        print("[pilot] ***** ABORT ***** " + "; ".join(abort))
        print("[pilot] The fresh corpus must NOT be scored.")
        print("=" * 70)
        return 1
    print(f"\n[pilot] PASS — {n}/{n} clean, c_tier1={c_tier1}, "
          f"A_bar={a_bar:.4f}, B*={report['b_star']['B_star']}, "
          f"rho_wall(B*)={report['b_star']['rho_wall_bstar']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
