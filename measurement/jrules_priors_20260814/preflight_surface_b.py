#!/usr/bin/env python
"""J-RULES SURFACE B — PER-BOX PRE-FLIGHT. Run BEFORE game 1, on every box that plays.

⚠️ WHY THIS EXISTS AND WHY NO HASH CHECK REPLACES IT (DESIGN.md §4, DEPLOY_PREREG.md gate 13).
Surface B's knobs live on `SearchConfig`, NOT `LeafConfig`, so a LIVE term moves **no leaf
hash**: the candidate's `cand_leaf_hash` EQUALS the champion's `a36d2e15a3b3d71d`. Every
moved-hash wiring gate from the surface-A / opencity / denial campaigns is therefore INERT
here. A stale `carc_rs`, a dropped kwarg, or a zeroed dose would grade a perfect
champion-vs-champion null wearing the exact shape of a real cell — and nothing in the
manifest's hash fields would show it. The two things that CAN show it are:

  (1) the RESOLVED `cand_jrules_prior.dose` in the cell's manifest (the driver's gate J4), and
  (2) THIS positive control: on a pinned midgame root, dose 1.0 must provably move the
      expansion priors vs dose 0 (`jrules_priors_e4_replay._assert_surface_b_live`).

Emits a JSON verdict on stdout; exits nonzero on any failure. ADJUDICATES NOTHING, plays no
game, reads no strength number.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import traceback

REPO = "/home/doctor/projects/carcassone"
sys.path.insert(0, os.path.join(REPO, "scripts", "classical_search"))

CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"
EXPECT_DOSE = float(os.environ.get("PREFLIGHT_DOSE", "0.5"))
EXPECT_MASK = int(os.environ.get("PREFLIGHT_MASK", "31"))
EXPECT_SCOPE = os.environ.get("PREFLIGHT_SCOPE", "all")

checks: list[dict] = []
ok_all = True


def chk(name, ok, observed):
    global ok_all
    ok_all &= bool(ok)
    checks.append({"check": name, "ok": bool(ok), "observed": observed})


def main() -> int:
    import carc_rs

    from carcassonne_ai.rust_agent import search_config_rs
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    # --- W1: the installed wheel carries the surface-B parity/probe surface at all.
    chk("W1_wheel_has_jrules_prior_probe",
        hasattr(carc_rs.MirrorState, "jrules_prior_probe"),
        {"carc_rs": getattr(carc_rs, "__file__", None)})

    # --- W2: SearchConfigRs accepts the three trailing kwargs (validated even at dose 0).
    #     A wheel predating surface B raises TypeError here — the fail-closed stale-wheel
    #     probe that `rust_agent.search_config_rs` relies on.
    from carcassonne_ai.rust_agent import leaf_config_rs
    try:
        carc_rs.SearchConfigRs(leaf_config_rs(DEFAULT_CONFIG), 32, 1.5, 5.0, 15.0, 15.0,
                               "float", "visits", None, 1.0, True, "glibc_fma",
                               jrules_prior_dose=EXPECT_DOSE,
                               jrules_prior_mask=EXPECT_MASK,
                               jrules_prior_scope=EXPECT_SCOPE)
        chk("W2_SearchConfigRs_accepts_prior_kwargs", True,
            f"dose={EXPECT_DOSE} mask={EXPECT_MASK} scope={EXPECT_SCOPE}")
    except TypeError as e:
        chk("W2_SearchConfigRs_accepts_prior_kwargs", False, f"TypeError: {e}")

    # --- W3/W4/W5: the PRODUCTION construction path, exactly as eval_fair_puct builds the
    #     candidate side: production prior cfg + dc.replace of the three surface-B knobs.
    try:
        import dataclasses as dc

        from carcassonne_ai.alphabeta_agent import _leaf_hash
        from carcassonne_ai.champion_factory import (load_production_spec,
                                                     production_leaf_cfg,
                                                     production_prior_cfg)
        spec = load_production_spec()
        base_leaf = production_leaf_cfg(spec)
        champ_hash = _leaf_hash(base_leaf)
        chk("W3_production_champion_leaf_hash_of_record",
            champ_hash == CHAMP_LEAF_HASH, champ_hash)

        cand = dc.replace(production_prior_cfg(spec, base_leaf),
                          jrules_prior_dose=EXPECT_DOSE,
                          jrules_prior_mask=EXPECT_MASK,
                          jrules_prior_scope=EXPECT_SCOPE)
        # ⚠️ INVERTED HASH EXPECTATION: setting the prior knobs must leave the leaf
        # byte-identical. A MOVED hash here means a leaf field was written — a DEFECT,
        # the exact opposite of every leaf-term cell's gate.
        cand_hash = _leaf_hash(cand.resolved_leaf_cfg())
        chk("W4_INVERTED_leaf_hash_UNMOVED_equals_champion",
            cand_hash == CHAMP_LEAF_HASH and cand_hash == champ_hash, cand_hash)

        # the fail-closed stale-wheel probe on the REAL production call site
        sc = search_config_rs(cand, 8)
        chk("W5_search_config_rs_forwards_at_funded_dose", sc is not None, repr(sc)[:300])
    except Exception as e:
        chk("W3_W5_production_path", False,
            f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")

    # --- P1: THE POSITIVE CONTROL. The only liveness proof available on this surface.
    try:
        from jrules_priors_e4_replay import _assert_surface_b_live
        _assert_surface_b_live()
        chk("P1_assert_surface_b_live", True,
            "PASSED: dose 1.0 moved the expansion priors on the pinned control root "
            "(deck seed 28000000000, 30 plies) and left the root leaf value bits intact")
    except SystemExit as e:
        chk("P1_assert_surface_b_live", False, f"SystemExit: {e}")
    except Exception as e:
        chk("P1_assert_surface_b_live", False,
            f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")

    out = {
        "kind": "jrules_surface_b_preflight",
        "host": platform.node(),
        "python": sys.executable,
        "expected": {"dose": EXPECT_DOSE, "mask": EXPECT_MASK, "scope": EXPECT_SCOPE,
                     "champion_leaf_hash": CHAMP_LEAF_HASH},
        "all_preflight_pass": bool(ok_all),
        "checks": checks,
        "note": "WIRING ONLY. No game played, no strength number read. Gate 13 of "
                "measurement/jrules_priors_20260814/DEPLOY_PREREG.md.",
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
