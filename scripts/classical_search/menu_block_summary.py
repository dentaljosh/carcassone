#!/usr/bin/env python3
"""Extract a lever-menu block's numbers + wiring provenance into ONE JSON.

Spec: docs/LEVER_MENU_PLAN_20260810.md.

THIS ADJUDICATES NOTHING. It reads `summary.json` and `manifest.json` off a finished cell
and writes a machine-readable extract so the orchestrating session can close out without
dirname archaeology. It computes no verdict, promotes nothing, and touches no governance
file. The one boolean it does emit -- `topup_triggered` -- is a PRE-REGISTERED arithmetic
condition (1.5 <= |margin z| < 2.0 on item 3), not a judgement: the plan puts the decision
to SPEND the top-up with Joshua (section 6.6), so the chain records the trigger and stops.

Wiring fields are carried alongside every number for a standing reason: a cell's numbers are
not readable until its manifest proves the knobs were applied. `rules_profile`, `r9_env_ok`
and the per-side leaf hashes are the gates that catch a silently-dropped knob (the
clairvoyant-rust-mirror failure mode).
"""
import argparse
import json
import os
import sys

CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"


def _g(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="the cell's shared-claim output dir")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--topup-trigger", action="store_true",
                    help="item 3 only: also evaluate the pre-registered 1.5<=|z|<2.0 top-up trigger")
    ap.add_argument("--expected-rules-profile", default="fixed_v1",
                    help=("the rules_profile.name this cell is REQUIRED to have run under. "
                          "Defaults to fixed_v1 (current behavior, unchanged for every existing "
                          "caller). Pass the epoch's actual profile for a cell that is legitimately "
                          "on a different one -- e.g. CL-072's n->800 extension (block E) runs "
                          "under `walled` on purpose, to match the ORIGINAL n=400 cell's epoch so "
                          "the two are poolable; fixed_v1 would be the wrong gate for that cell, "
                          "not the right default."))
    ap.add_argument("--expect-cand-leaf-hash", default=None,
                    help=("the CANDIDATE leaf hash this cell is REQUIRED to have run under, "
                          "computed from the cell's knob spec BEFORE game 1 (added 2026-08-12 "
                          "for the denial screen). This is the gate that catches the campaign's "
                          "worst failure mode: a knob the loaded native build does not "
                          "implement runs a candidate arm that IS the champion, completes "
                          "cleanly and reads as a beautiful, meaningless null. If the manifest's "
                          "cand_leaf_hash equals the champion's, or differs from the expected "
                          "value, the cell is UNREADABLE, not merely suspicious. Omitted -> "
                          "unchanged behaviour for every pre-existing caller."))
    a = ap.parse_args()

    out = {"label": a.label, "dir": a.dir, "adjudicated": False,
           "expected_rules_profile": a.expected_rules_profile,
           "note": ("Extract only. No verdict, no promotion, no governance touch. "
                    "The orchestrating session reads this and closes out.")}

    sp = os.path.join(a.dir, "summary.json")
    mp = os.path.join(a.dir, "manifest.json")
    n_records = len([f for f in os.listdir(a.dir)
                     if f.startswith("seed") and f.endswith(".json")]) if os.path.isdir(a.dir) else 0
    out["records_on_disk"] = n_records

    if os.path.exists(sp):
        s = json.load(open(sp))
        for k in ("n", "n_paired", "W", "D", "L", "elo", "elo_sig_1sigma", "paired_z",
                  "paired_mean_margin", "paired_se_margin", "wr",
                  "cand_prefix_ms_per_move", "champ_prefix_ms_per_move"):
            if k in s:
                out[k] = s[k]
        # ⚠️ FIELD-NAME TRAP, recorded because it has bitten three times: in this harness
        # `champ_prefix_*` is the CANDIDATE side's cost (the harness names the candidate
        # "champ"). Read the emitter before trusting the name.
        cm, chm = s.get("cand_prefix_ms_per_move"), s.get("champ_prefix_ms_per_move")
        if cm and chm:
            out["ms_ratio_cand_over_opp"] = cm / chm
            out["ms_ratio_caveat"] = (
                "Ratio only. NEVER quote an absolute ms/move from a shared-tenancy run; a "
                "ratio of two arms sharing one process pool is first-order insensitive to "
                "contention, an absolute is not. Also: `champ_prefix_*` is the CANDIDATE's "
                "cost in this harness -- read the emitter, not the field name.")
    else:
        out["summary_missing"] = sp

    if os.path.exists(mp):
        m = json.load(open(mp))
        out["wiring"] = {
            "code_rev": m.get("code_rev"),
            "rules_profile": _g(m, "rules_profile", "name"),
            "r9_env_ok": _g(m, "rules_profile", "r9_env_ok"),
            "cand_leaf_hash": _g(m, "config", "cand_leaf_hash"),
            # Two harnesses, two names for the same field: eval_fair_puct writes
            # `opp_leaf_hash`, eval_puct_priors (the 2750 ablation instrument) writes
            # `champ_leaf_hash`. Reading only the first silently made the opponent-side
            # gate VACUOUS on every ablation-class cell (it recorded null and passed).
            # Fall back, and record which name supplied the value.
            "opp_leaf_hash": (_g(m, "config", "opp_leaf_hash")
                              if _g(m, "config", "opp_leaf_hash") is not None
                              else _g(m, "config", "champ_leaf_hash")),
            "opp_leaf_hash_field": ("opp_leaf_hash"
                                    if _g(m, "config", "opp_leaf_hash") is not None
                                    else "champ_leaf_hash"),
            "cand_leaf_json": _g(m, "config", "cand_leaf_json"),
            "cand_curve_drift_allowed": _g(m, "config", "cand_curve_drift_allowed"),
            "cand_k_dets": _g(m, "config", "champion", "k_dets"),
            "cand_sims_per_det": _g(m, "config", "champion", "sims_per_det"),
            "cand_total_sims": _g(m, "config", "champion", "total_sims"),
            "opp_k_dets": _g(m, "config", "opponent", "k_dets"),
            "opp_sims_per_det": _g(m, "config", "opponent", "sims_per_det"),
            "opp_total_sims": _g(m, "config", "opponent", "total_sims"),
            "band_seed_start": _g(m, "config", "band_seed_start"),
            "n_decks": _g(m, "config", "n_decks"),
            "paired": _g(m, "config", "paired"),
        }
        w = out["wiring"]
        gates = []
        # Epoch-aware: compare against the CALLER-DECLARED expected profile, not a hardcoded
        # "fixed_v1". Most callers want fixed_v1 (the default preserves that), but a cell that
        # is deliberately pinned to a different epoch (e.g. block E / CL-072's n->800 extension,
        # which must run under `walled` to match its n=400 sibling's epoch for pooling) needs
        # its OWN expected value or this gate false-fires on a correct-by-design cell.
        if w["rules_profile"] != a.expected_rules_profile:
            gates.append(f"rules_profile is {w['rules_profile']!r}, not {a.expected_rules_profile!r}")
        if w["r9_env_ok"] is not True:
            gates.append(f"r9_env_ok is {w['r9_env_ok']!r}, not true")
        if w["opp_leaf_hash"] not in (None, CHAMP_LEAF_HASH):
            gates.append(f"opponent leaf hash {w['opp_leaf_hash']!r} != {CHAMP_LEAF_HASH}")
        if a.expect_cand_leaf_hash:
            out["expected_cand_leaf_hash"] = a.expect_cand_leaf_hash
            if w["cand_leaf_hash"] != a.expect_cand_leaf_hash:
                gates.append(
                    f"candidate leaf hash {w['cand_leaf_hash']!r} != expected "
                    f"{a.expect_cand_leaf_hash!r}"
                    + (" -- IT IS THE CHAMPION'S HASH: the candidate arm ran the UNMODIFIED "
                       "champion leaf, i.e. the knob never reached the leaf. This cell's null "
                       "is an artifact, not a measurement."
                       if w["cand_leaf_hash"] == CHAMP_LEAF_HASH else ""))
        out["wiring_gate_failures"] = gates
        out["wiring_gates_clean"] = not gates
        if gates:
            out["READ_BLOCK"] = ("WIRING GATES FAILED - do NOT read this cell's numbers. "
                                 "Verify wiring from the manifest BEFORE any number is read.")
    else:
        out["manifest_missing"] = mp

    if a.topup_trigger:
        z = out.get("paired_z")
        out["topup_triggered"] = bool(z is not None and 1.5 <= abs(z) < 2.0)
        out["topup_note"] = (
            "PRE-REGISTERED trigger only (1.5 <= |margin z| < 2.0 => extend item 3 to n=1600 "
            "on FRESH decks of band 1.19e11, seeds 119000000400..119000000799). The chain does "
            "NOT run it: the +1.5 h spend is Joshua's call (plan section 6.6).")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
