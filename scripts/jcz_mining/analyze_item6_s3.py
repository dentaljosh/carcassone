#!/usr/bin/env python3
"""ITEM 6 (JCZ S3 cut) — analysis, using the mining analyzer's OWN statistic.

Pre-registration: measurement/jcz_mining_20260809/MINING_PREREG.md §5 ("Statistic")
and §6 (branch language); docs/LEVER_MENU_PLAN_20260810.md §4.6 (item 6's own
branches, which mirror the mining decision map without adjudicating beyond it).

Reuses `cluster_se` / `stratum_stats` from `analyze_mining.py` VERBATIM (imported,
not reimplemented) so the cluster-robust z matches the mining analyzer's own
convention exactly, per the task brief. Does not reuse `join_records` /
`index_strata_rows` because THIS build's stratum labels (`ITEM6_S3` /
`ITEM6_S3_CONTROL`) are not in that module's A/B/C label map by design (S3 is not
an A/B/C axis) — so the STRATA_S3.json join here is a small compatible
reimplementation of the SAME join-by-rid idea, not a new statistic.

SIGN CONVENTION — inherited unchanged from the mining prereg: every position's
`pick_a` = OUR leaf-argmax pick, `pick_b` = JCZ's played pick.
`oracle_score_pilot.position_delta` returns `delta = mean(V_B - V_A)`, so
`delta > 0` means JCZ's pick was better than ours (their evaluator out-earns
ours); `delta < 0` vindicates our leaf on that ply.

Governance: measurement only. Mints no claim id, claims no band. Exploratory by
construction (PREREG §7 rider 6 / item 6 riders).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "jcz_mining"))

import analyze_mining as AM  # noqa: E402  (reuse cluster_se / stratum_stats verbatim)

SCHEMA = "carcassonne-lever-menu-item6-s3-cut/v1"
PREREG = "measurement/jcz_mining_20260809/MINING_PREREG.md"
PLAN = "docs/LEVER_MENU_PLAN_20260810.md#4.6"
Z_GATE = AM.Z_GATE  # 2.0, two-sided
MIN_N_GATE = 25  # PREREG §4 gate, restated in the plan's §4.6 sizing note
POWERED_BAR_N = 74  # PREREG §4 re-open bar, 80% power at +1.4 pts/ply


def _load_position_index(path: Path) -> dict:
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["rid"]] = r
    return out


def _load_records(records_dir: Path) -> list:
    found = sorted(Path(records_dir).glob("*.json"))
    if not found:
        raise SystemExit(f"[analyze_item6_s3] no records in {records_dir} — has the "
                          "scoring leg finished a single position yet?")
    return [json.loads(f.read_text()) for f in found]


def join(records: list, pos_index: dict, label: str) -> tuple[list, list]:
    """rid-join oracle_score_pilot records back to this build's own position rows,
    recovering `ply_class` / `phase_bucket` / `our_leaf_gap` / `merge_exposure_differs`
    / `stratum` (fields `_process`'s allowlist does not carry through). Mirrors
    `analyze_mining.join_records`'s discipline: drop+report `ok=false`, and a
    matched-by-rid record that has no position row is a hard error, never silent."""
    joined, unmatched = [], []
    for r in records:
        if not r.get("ok"):
            continue
        prow = pos_index.get(r.get("rid"))
        if prow is None:
            unmatched.append(r.get("rid"))
            continue
        j = dict(r)
        for k in ("ply_class", "phase_bucket", "our_leaf_gap", "k_remaining",
                  "merge_exposure_differs", "jcz_seat", "stratum", "root_id"):
            if k in prow:
                j[k] = prow[k]
        joined.append(j)
    if unmatched:
        raise SystemExit(f"[analyze_item6_s3] {label}: {len(unmatched)} ok record(s) "
                          f"with no matching position row (by rid) — partial join, "
                          f"refusing. rids: {unmatched[:10]}")
    return joined, unmatched


def sizing_note(n: int) -> str:
    if n < MIN_N_GATE:
        return (f"n={n} < {MIN_N_GATE} (PREREG §4 gate) -> INCONCLUSIVE BY "
                f"CONSTRUCTION, not merely underpowered.")
    if n < POWERED_BAR_N:
        return (f"n={n} clears the n>={MIN_N_GATE} gate but sits BELOW the n={POWERED_BAR_N} "
                f"re-open bar (80% power at +1.4 pts/ply). Read as a coarse screen, not a "
                f"powered verdict, per the pre-registered power table.")
    return f"n={n} clears the n>={POWERED_BAR_N} powered bar (80% at +1.4 pts/ply)."


def decide_item6(s3_stats: dict, ctrl_stats: dict) -> dict:
    """docs/LEVER_MENU_PLAN_20260810.md §4.6 branches, evaluated in the stated order,
    mirroring (not extending) the mining decision map. This function ADJUDICATES
    NOTHING beyond the three named branches."""
    z_s3 = s3_stats.get("z_two_sided", float("nan"))
    z_ctrl = ctrl_stats.get("z_two_sided", float("nan"))
    mean_s3 = s3_stats.get("mean_delta_pts", float("nan"))

    def sig(z):
        return z == z and abs(z) >= Z_GATE

    if s3_stats.get("n", 0) < MIN_N_GATE:
        return {"branch": "GATE FAIL",
                "detail": "S3 stratum n below the PREREG §4 floor — "
                          "INCONCLUSIVE BY CONSTRUCTION, not reinterpreted."}

    if sig(z_s3) and mean_s3 > 0 and not sig(z_ctrl):
        return {"branch": "LOCALIZED CONVICTION",
                "detail": "S3 z >= +2.0 (their evaluator out-earns ours on "
                          "merge-exposure plies) AND the matched control is null. "
                          "Any downstream play gate MUST use a fresh band; funding "
                          "is Joshua's call."}

    if sig(z_s3) and sig(z_ctrl) and (mean_s3 > 0) == (ctrl_stats.get("mean_delta_pts", 0) > 0):
        return {"branch": "BACKGROUND, NOT S3-SPECIFIC",
                "detail": "S3 and its matched control move together (same shape "
                          "that killed stratum B: -0.904 vs its control -0.903) — "
                          "not a localized merge-exposure effect."}

    if not sig(z_s3):
        return {"branch": "NO CONVICTION",
                "detail": "|z_S3| < 2.0 -> the JCZ steal file CLOSES on S3 and the "
                          "native-term build stays unfunded."}

    return {"branch": "AMBIGUOUS",
            "detail": "S3 is significant but does not cleanly match either named "
                      "branch (e.g. S3 significant and negative, or S3 significant "
                      "positive with a control that is significant but opposite "
                      "sign) — report the raw numbers, do not force a label."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--s3-positions", default=str(
        REPO / "measurement/lever_menu_20260810/item6_s3/S3_stratum.jsonl"))
    ap.add_argument("--control-positions", default=str(
        REPO / "measurement/lever_menu_20260810/item6_s3/S3_control.jsonl"))
    ap.add_argument("--s3-records", required=True,
                    help="oracle_score_pilot out_dir/S3_stratum/records")
    ap.add_argument("--control-records", required=True,
                    help="oracle_score_pilot out_dir/S3_control/records")
    ap.add_argument("--out-json", default=str(
        REPO / "measurement/lever_menu_20260810/ITEM6_S3_CUT.json"))
    ap.add_argument("--out-md", default=str(
        REPO / "measurement/lever_menu_20260810/ITEM6_S3_CUT.md"))
    args = ap.parse_args(argv)

    s3_pos = _load_position_index(Path(args.s3_positions))
    ctrl_pos = _load_position_index(Path(args.control_positions))

    s3_records = _load_records(Path(args.s3_records))
    ctrl_records = _load_records(Path(args.control_records))

    s3_joined, _ = join(s3_records, s3_pos, "S3")
    ctrl_joined, _ = join(ctrl_records, ctrl_pos, "control")

    n_s3_failed = sum(1 for r in s3_records if not r.get("ok"))
    n_ctrl_failed = sum(1 for r in ctrl_records if not r.get("ok"))

    s3_stats = AM.stratum_stats(s3_joined, "S3")
    ctrl_stats = AM.stratum_stats(ctrl_joined, "S3_CONTROL")
    s3_ply = AM.ply_class_breakdown(s3_joined)
    ctrl_ply = AM.ply_class_breakdown(ctrl_joined)

    decision = decide_item6(s3_stats, ctrl_stats)

    out = {
        "schema": SCHEMA,
        "prereg": PREREG,
        "plan": PLAN,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "governance": "measurement only; governance/PRODUCTION.yaml untouched; "
                      "plays zero games; mints no claim id unless the decision map "
                      "says otherwise; band 1.08e11 stays retired from confirmatory "
                      "use and this reuse does not un-retire it.",
        "sign_convention": "delta = mean(V(pick_b) - V(pick_a)); pick_a = our "
                           "leaf-argmax, pick_b = JCZ's played pick. delta > 0 "
                           "means JCZ's pick was better.",
        "s3": {**s3_stats, "n_failed": n_s3_failed, "ply_class_breakdown": s3_ply,
               "sizing": sizing_note(s3_stats.get("n", 0))},
        "control": {**ctrl_stats, "n_failed": n_ctrl_failed, "ply_class_breakdown": ctrl_ply,
                    "sizing": sizing_note(ctrl_stats.get("n", 0))},
        "decision": decision,
        "min_n_gate": MIN_N_GATE,
        "powered_bar_n": POWERED_BAR_N,
    }
    Path(args.out_json).write_text(json.dumps(out, indent=2, sort_keys=False))

    md = f"""# ITEM 6 — JCZ S3 cut (merge-exposure) — readout

Generated {out['generated_utc']}. Prereg: `{PREREG}`. Plan: `{PLAN}`.

Oracle-replay instrument. Plays **zero games**. Claims **no band**. Does not touch
`governance/PRODUCTION.yaml`.

## Sign convention
`delta = mean(V(pick_b) - V(pick_a))`; `pick_a` = our leaf-argmax pick, `pick_b` =
JCZ's played pick. `delta > 0` means JCZ's pick was better than ours.

## Per-stratum statistics (cluster-robust z on `root_id`, CR1)

| stratum | n (ok) | n (failed) | mean delta_Q (pts/ply) | se_cluster_root | z | 95% CI | sizing |
|---|---:|---:|---:|---:|---:|---|---|
| S3 (merge_exposure_differs) | {s3_stats.get('n')} | {n_s3_failed} | {s3_stats.get('mean_delta_pts'):.4f} | {s3_stats.get('se_cluster_root'):.4f} | {s3_stats.get('z_two_sided'):.3f} | [{s3_stats.get('ci95_lo'):.3f}, {s3_stats.get('ci95_hi'):.3f}] | {sizing_note(s3_stats.get('n', 0))} |
| matched control | {ctrl_stats.get('n')} | {n_ctrl_failed} | {ctrl_stats.get('mean_delta_pts'):.4f} | {ctrl_stats.get('se_cluster_root'):.4f} | {ctrl_stats.get('z_two_sided'):.3f} | [{ctrl_stats.get('ci95_lo'):.3f}, {ctrl_stats.get('ci95_hi'):.3f}] | {sizing_note(ctrl_stats.get('n', 0))} |

Ply-class breakdown — S3: {s3_ply}; control: {ctrl_ply}.

## Branch fired

**{decision['branch']}** — {decision['detail']}

## Riders (restated, do not drop from any downstream citation)
- Exploratory by construction — no strength claim, no band claimed; band 1.08e11
  stays retired from confirmatory use and this reuse does not un-retire it.
- The oracle prices with a reference that is NOT the leaf under suspicion (clairvoyant
  PUCT continuation on the production curve125 leaf) — that is the point; the leaf
  under suspicion was never substituted in.
- Sizing honesty: PREREG §4's gate is n>=25 scored per stratum or the stratum is
  INCONCLUSIVE BY CONSTRUCTION; the re-open bar for 80% power at +1.4 pts/ply is
  n=74. n=50 sits BETWEEN the gate and the powered bar.
"""
    Path(args.out_md).write_text(md)
    print(f"[analyze_item6_s3] S3 n={s3_stats.get('n')} mean={s3_stats.get('mean_delta_pts')} "
          f"z={s3_stats.get('z_two_sided')}")
    print(f"[analyze_item6_s3] control n={ctrl_stats.get('n')} "
          f"mean={ctrl_stats.get('mean_delta_pts')} z={ctrl_stats.get('z_two_sided')}")
    print(f"[analyze_item6_s3] branch: {decision['branch']}")
    print(f"[analyze_item6_s3] wrote {args.out_json}\n[analyze_item6_s3] wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
