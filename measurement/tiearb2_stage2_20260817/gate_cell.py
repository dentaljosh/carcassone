#!/usr/bin/env python
"""tiearb2 STAGE 2 PHASE B — THE PER-CELL WIRING GATES. PASS/FAIL ONLY.

Called by `run_cells.sh` once per cell, entirely through the environment, and it
writes `verdicts/GATES_<cell>.json`. It reads NO strength statistic, by design:
`measurement/tiearb2_stage2_20260817/READ_RULE.md` §3 must be checkable before
any number is opened, and the adjudicator
(`scripts/tiletie/analyze_tiearb2_stage2.py`) is the only thing that touches
`paired_z`.

⚠️ **J1 IS AN EQUALITY GATE.** The arbiter's knobs live on `SearchConfig`, not
`LeafConfig`, so a LIVE arbiter moves NO leaf hash: the candidate's hash must
EQUAL the champion's `a36d2e15a3b3d71d`, and a MOVED hash is a DEFECT (a leaf
change smuggled into an arbiter cell), not evidence. This is inverted relative to
every leaf-term cell and is not a typo.

⚠️ **`cand_tiearb` is checked at BOTH addresses.** The pre-registration
disagrees with itself about where it lives: DESIGN §4 / READ_RULE §3 first said
`config.cand_tiearb`, and READ_RULE §0.C.2 "corrected" it to top level. The
harness writes it to BOTH (see `eval_fair_puct.py`'s `patch_manifest` call), and
this gate accepts either while REPORTING which addresses carried it, so the
discrepancy is on the record rather than adjudicated by whoever reads first.
"""
from __future__ import annotations

import glob
import json
import os
import sys

g: list[dict] = []
res = True


def chk(name, ok, got, note=None):
    global res
    res &= bool(ok)
    row = {"gate": name, "ok": bool(ok), "observed": got}
    if note:
        row["note"] = note
    g.append(row)


def main() -> int:
    global res
    man_path = os.environ["MANIFEST"]
    m = json.load(open(man_path))
    c = m.get("config", {}) or {}
    rp = m.get("rules_profile") or {}
    le = m.get("leaf_env") or {}
    cl = c.get("cand_leaf_cfg") or {}
    ch = c.get("champion") or {}
    op = c.get("opponent") or {}
    eg = c.get("endgame") or {}
    be = c.get("backend") or {}
    CHAMP = os.environ["CHAMP_HASH"]

    # ---- J1: ⚠️ INVERTED. EQUALITY, not inequality.
    chk("J1_INVERTED_cand_leaf_hash_EQUALS_champion",
        c.get("cand_leaf_hash") == CHAMP, c.get("cand_leaf_hash"),
        "EQUALITY GATE. A MOVED hash is a DEFECT on this surface, not evidence "
        "of a live arbiter.")
    chk("J2_opp_leaf_hash_EQUALS_champion",
        c.get("opp_leaf_hash") == CHAMP, c.get("opp_leaf_hash"))
    chk("J3_cand_leaf_json_is_null", c.get("cand_leaf_json") is None,
        c.get("cand_leaf_json"))

    # ---- J4: THE LIVENESS GATE. The RESOLVED knob dict, at either address.
    top = m.get("cand_tiearb")
    nested = c.get("cand_tiearb")
    found = [k for k, v in (("cand_tiearb", top), ("config.cand_tiearb", nested))
             if v is not None]
    ta = top if top is not None else nested
    want = {"enabled": True,
            "B": int(os.environ["EXPECT_B"]), "J": int(os.environ["EXPECT_J"]),
            "mode": os.environ["EXPECT_MODE"],
            "salt": os.environ["EXPECT_SALT"],
            "eps": float(os.environ["EXPECT_EPS"])}
    ok4 = bool(ta) and all(
        (float(ta.get(k)) == float(v)) if isinstance(v, float)
        else (ta.get(k) == v) for k, v in want.items())
    if top is not None and nested is not None and top != nested:
        ok4 = False
    chk("J4_LIVENESS_resolved_cand_tiearb",
        ok4, {"resolved": ta, "expected": want, "found_at": found},
        "THE liveness gate. No hash on this surface can substitute for it (see "
        "also J13 and FIRE). READ_RULE G-J4 voids the run on B != 16, J != 4, or "
        "the wrong mode for the cell.")
    chk("J4b_cand_tiearb_present_at_both_addresses",
        len(found) == 2, found,
        "REPORTED, and gated only because the harness writes both: DESIGN §4 "
        "said config.cand_tiearb, READ_RULE §0.C.2 said top-level. Both are "
        "written so the run is readable under either.")

    # ---- FIRE: the realized firing rate. READ_RULE G-FIRE voids below 1.0.
    summ_path = os.environ.get("SUMMARY", "")
    summ = {}
    if summ_path and os.path.exists(summ_path):
        try:
            summ = json.load(open(summ_path))
        except Exception as e:                      # noqa: BLE001
            summ = {"_unreadable": f"{type(e).__name__}: {e}"}
    phi = summ.get("tiearb_phi")
    chk("FIRE_tiearb_phi_at_least_1_per_game",
        phi is not None and float(phi) >= 1.0,
        {"tiearb_phi": phi,
         "tiearb_fired_plies_total": summ.get("tiearb_fired_plies_total"),
         "tiearb_tile_plies_total": summ.get("tiearb_tile_plies_total"),
         "tiearb_games": summ.get("tiearb_games"),
         "tiearb_pickchange_rate": summ.get("tiearb_pickchange_rate"),
         "tiearb_mean_arms": summ.get("tiearb_mean_arms"),
         "offline_prior": 22.96},
        "READ_RULE G-FIRE: below 1.0 the arbitration surface is effectively "
        "inert and the cell is U-UNREADABLE. ⚠️ The offline 22.96 is a PRIOR, "
        "not a prediction (DESIGN §2.1's two runtime-vs-corpus mismatches).")
    chk("FIRE_mode_matches_the_cell",
        summ.get("tiearb_modes") == [os.environ["EXPECT_MODE"]],
        {"tiearb_modes": summ.get("tiearb_modes"),
         "expected": os.environ["EXPECT_MODE"]})

    # ---- J5: no tiearb_* key rode into the candidate LEAF (it is a SEARCH knob).
    cand_leaf_ta = {k: v for k, v in cl.items() if "tiearb" in k}
    chk("J5_no_tiearb_key_on_the_candidate_leaf", not cand_leaf_ta, cand_leaf_ta)

    # ---- J8: budget on BOTH sides, read as NUMBERS (never the prose note).
    chk("J8_both_budgets_8x1376_11008",
        (ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")) == (8, 1376, 11008)
        and (op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")) == (8, 1376, 11008),
        {"champion": [ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")],
         "opponent": [op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")]})

    chk("J9_rules_fixed_v1_R9",
        rp.get("name") == "fixed_v1" and rp.get("r9_env_expected") is True
        and le.get("CARCASSONNE_FIX_R9") == "1",
        {"name": rp.get("name"), "r9_env_expected": rp.get("r9_env_expected"),
         "r9_env_observed": rp.get("r9_env_observed"), "r9_env_ok": rp.get("r9_env_ok"),
         "leaf_env.CARCASSONNE_FIX_R9": le.get("CARCASSONNE_FIX_R9")})

    chk("J10_backend_rust", be.get("requested") == "rust",
        {"requested": be.get("requested"), "name": be.get("name"),
         "converted_sides": be.get("converted_sides")})

    # ---- J11: n records, n unique (deck seed, seat), fully paired, in-band.
    recs, bad = [], []
    for p in glob.glob(os.path.join(os.environ["RECDIR"], "seed*.json")):
        try:
            recs.append(json.load(open(p)))
        except Exception as e:                      # noqa: BLE001
            bad.append(f"{os.path.basename(p)}: {type(e).__name__}")
    band0 = int(os.environ["EXPECT_SEED"])
    exp_n = int(os.environ["EXPECT_N"])
    exp_decks = exp_n // 2
    pairs: dict = {}
    for r in recs:
        k = (r.get("seed"), r.get("a_seat"))
        pairs[k] = pairs.get(k, 0) + 1
    seat_count: dict = {}
    for (s, _a) in pairs:
        seat_count[s] = seat_count.get(s, 0) + 1
    expected_pairs = {(band0 + i, a) for i in range(exp_decks) for a in (0, 1)}
    missing = expected_pairs - set(pairs)
    extra = set(pairs) - expected_pairs
    dups = [k for k, v in pairs.items() if v > 1]
    fully = sum(1 for v in seat_count.values() if v == 2)
    chk("J11_records_unique_pairs_fully_paired_in_band",
        len(recs) == exp_n and len(pairs) == exp_n and not missing and not extra
        and not dups and not bad and fully == exp_decks,
        {"records": len(recs), "unique_pairs": len(pairs), "missing": len(missing),
         "extra": len(extra), "dup_keys": len(dups), "unreadable": bad[:5],
         "fully_paired_decks": fully, "band": [band0, band0 + exp_decks - 1]})

    # ---- J12: SURROGATE variant-id. ONE manifest, records agreeing on identity.
    AGREE = ("sims", "k_dets", "exact_k", "opponent", "info", "rung_sims")
    tuples = {tuple(r.get(k) for k in AGREE) for r in recs}
    n_manifests = len(glob.glob(os.path.join(os.environ["RECDIR"], "manifest*.json")))
    chk("J12_one_manifest_and_records_agree",
        n_manifests == 1 and len(tuples) == 1,
        {"n_manifests": n_manifests, "distinct_identity_tuples": len(tuples),
         "keys": list(AGREE), "tuples": [list(t) for t in sorted(tuples, key=str)[:4]]})

    # ---- J13: the TWO-SIDED positive control, passed on THIS box BEFORE game 1.
    pf_path = os.environ["PREFLIGHT"]
    try:
        pf = json.load(open(pf_path))
        pf_ok = bool(pf.get("all_preflight_pass"))
        pos = next((x for x in pf.get("checks", []) if x["check"].startswith("J13_POSITIVE")), None)
        neg = next((x for x in pf.get("checks", []) if x["check"].startswith("J13_NEGATIVE")), None)
        both = bool(pos and pos.get("ok")) and bool(neg and neg.get("ok"))
        rec_files = glob.glob(os.path.join(os.environ["RECDIR"], "seed*.json"))
        before = bool(rec_files) and os.path.getmtime(pf_path) <= min(
            os.path.getmtime(f) for f in rec_files)
        chk("J13_TWO_SIDED_positive_control_before_game1",
            pf_ok and both and before,
            {"preflight": os.path.basename(pf_path),
             "all_preflight_pass": pf.get("all_preflight_pass"),
             "POSITIVE": (pos or {}).get("observed"),
             "NEGATIVE": (neg or {}).get("observed"),
             "predates_first_record": before, "host": pf.get("host")},
            "BOTH sides required: the arbiter must CHANGE the pick at a "
            "constructed tied ply AND leave root_leaf_value_bits UNCHANGED. "
            "Without this a zeroed dose grades a perfect champion-vs-champion "
            "null wearing the shape of a real cell.")
        chk("TOOL_toolchain_and_build_stamped",
            bool((pf.get("toolchain") or {}).get("rustc"))
            and bool((pf.get("backend_provenance") or {}).get("carc_rs_version")),
            {"toolchain": pf.get("toolchain"),
             "backend_provenance": pf.get("backend_provenance")},
            "READ_RULE G-TOOL is a CROSS-BOX gate: the read-out compares this "
            "stamp against the other box's PREFLIGHT_*_FIRST.json.")
    except Exception as e:                          # noqa: BLE001
        chk("J13_TWO_SIDED_positive_control_before_game1", False,
            f"{type(e).__name__}: {e}")

    # ---- REPORTED, NOT GATED.
    n_failed = int(m.get("n_failed") or 0)
    observed = {
        "n_failed": n_failed,
        "failure_rate": m.get("failure_rate"),
        "failed_by_seat": m.get("failed_by_seat"),
        "N5_trigger_0p5pct_exceeded": bool(n_failed > 0.005 * exp_n),
        "band_seed_start": c.get("band_seed_start"),
        "n_decks": c.get("n_decks"),
        "seatings_per_deck": c.get("seatings_per_deck"),
        "endgame": {"exact_k": eg.get("exact_k"),
                    "shared_by_both_arms": eg.get("shared_by_both_arms")},
        "code_rev": m.get("code_rev"),
        "host": m.get("host"),
        "box": os.environ["BOX"],
        "workers": int(os.environ["WORKERS"]),
        "elapsed_s": int(os.environ["ELAPSED"]),
        # ⚠️ THE FIELD-NAME TRAP, restated wherever the number appears:
        # `champ_prefix_ms_per_move` IS THE CANDIDATE SIDE in eval_fair_puct
        # (the opposite of eval_puct_priors). A read-out that swaps them
        # inverts the N4 cost verdict.
        "champ_prefix_ms_per_move_IS_THE_CANDIDATE": summ.get("champ_prefix_ms_per_move"),
        "rung_ms_per_move_IS_THE_OPPONENT": summ.get("rung_ms_per_move"),
        "ms_ratio_cand_over_opp": (
            (summ.get("champ_prefix_ms_per_move") / summ["rung_ms_per_move"])
            if summ.get("rung_ms_per_move") else None),
        "N4_trigger": 1.20,
        "tiearb_secs_per_game": summ.get("tiearb_secs_per_game"),
    }

    json.dump({"cell": os.environ["SUB"],
               "prereg": "measurement/tiearb2_stage2_20260817/READ_RULE.md",
               "all_gates_pass": res,
               "records": f"{int(os.environ['GOT_N'])}/{exp_n}",
               "gates": g,
               "observed_not_gated": observed,
               "note": "WIRING ONLY -- contains no strength statistic by design. "
                       "⚠️ J1 is an EQUALITY gate: this surface moves no leaf hash, "
                       "so a MOVED candidate hash is a DEFECT, not evidence. "
                       "⚠️ ms_ratio is a DOWNGRADE trigger (READ_RULE §4.2), NEVER "
                       "a branch input."},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
