#!/usr/bin/env python
"""TIE ARBITER — PER-BOX PRE-FLIGHT. Run BEFORE game 1, on every box that plays.

`measurement/tiearb2_stage2_20260817/DESIGN.md` §4, `READ_RULE.md` §3
(`G-J1` / `G-J4` / `G-J13` / `G-TOOL`). Templated on
`measurement/jrules_priors_20260814/preflight_surface_b.py`.

⚠️ WHY THIS EXISTS AND WHY NO HASH CHECK REPLACES IT. The arbiter's knobs live on
`SearchConfig`, NOT `LeafConfig`, so a LIVE arbiter moves **no leaf hash**: the
candidate's `cand_leaf_hash` must EQUAL the champion's `a36d2e15a3b3d71d`.
`J1` is therefore an **EQUALITY** gate and a *difference* is an ABORT, not a
finding. Every moved-hash wiring gate from the surface-A / opencity / denial
campaigns is INERT here. The three things that CAN show a live arbiter are:

  (1) the RESOLVED `config.cand_tiearb` dict in the cell's manifest (`G-J4`),
  (2) `summary.json::tiearb_phi`, the realized firing rate (`G-FIRE`), and
  (3) THIS **two-sided** positive control (`G-J13`) — the arbiter must CHANGE
      the pick at a constructed tied ply AND leave `root_leaf_value_bits`
      unchanged.

The J13 lesson, verbatim: *"Without this a zeroed dose grades a perfect
champion-vs-champion null wearing the shape of a real cell."*

Emits a JSON verdict on stdout; exits nonzero on any failure. ADJUDICATES
NOTHING, plays no game, reads no strength number.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import traceback

REPO = "/home/doctor/projects/carcassone"
sys.path.insert(0, os.path.join(REPO, "scripts", "classical_search"))

CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"
EXPECT_B = int(os.environ.get("PREFLIGHT_TIEARB_B", "16"))
EXPECT_J = int(os.environ.get("PREFLIGHT_TIEARB_J", "4"))
EXPECT_SALT = os.environ.get("PREFLIGHT_TIEARB_SALT", "tiearb2-deploy-v1")
EXPECT_EPS = float(os.environ.get("PREFLIGHT_TIEARB_EPS", "0.0"))
# The two-sided control's own budget. It is a WIRING probe: the arbiter runs at
# the funded B/J, the SEARCH runs cheap (a pick change at 11,008 sims proves
# nothing more than one at 64, and costs 170x).
PF_SIMS = int(os.environ.get("PREFLIGHT_TIEARB_SIMS", "64"))
PF_KDETS = int(os.environ.get("PREFLIGHT_TIEARB_KDETS", "4"))
PF_MAX_FIRED = int(os.environ.get("PREFLIGHT_TIEARB_MAX_FIRED", "12"))

checks: list[dict] = []
ok_all = True


def chk(name, ok, observed):
    global ok_all
    ok_all &= bool(ok)
    checks.append({"check": name, "ok": bool(ok), "observed": observed})


def _toolchain() -> dict:
    def run(*cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=30).stdout.strip()
        except Exception as e:                      # noqa: BLE001
            return f"<{type(e).__name__}: {e}>"
    return {
        "RUSTUP_TOOLCHAIN": os.environ.get("RUSTUP_TOOLCHAIN"),
        "rustc": run("rustc", "--version"),
        "cargo": run("cargo", "--version"),
        "code_rev": run("git", "-C", REPO, "rev-parse", "HEAD"),
        "code_rev_short": run("git", "-C", REPO, "rev-parse", "--short", "HEAD"),
        "dirty": bool(run("git", "-C", REPO, "status", "--porcelain")),
    }


def main() -> int:
    import carc_rs

    from carcassonne_ai.rust_agent import (backend_provenance, leaf_config_rs,
                                           search_config_rs)
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    prov = backend_provenance()

    # --- W1: the installed wheel carries the arbiter surface AT ALL.
    chk("W1_wheel_has_tiearb_probe",
        hasattr(carc_rs.MirrorState, "tiearb_probe"),
        {"carc_rs": prov["carc_rs_path"], "version": prov["carc_rs_version"]})

    # --- W2: SearchConfigRs accepts the six trailing kwargs (validated even when
    #     disabled). A wheel predating the arbiter raises TypeError here — the
    #     fail-closed stale-wheel probe `rust_agent.search_config_rs` relies on.
    try:
        sc = carc_rs.SearchConfigRs(leaf_config_rs(DEFAULT_CONFIG), 32, 1.5, 5.0, 15.0,
                                    tiearb_enabled=True, tiearb_b=EXPECT_B,
                                    tiearb_j=EXPECT_J, tiearb_mode="argmax",
                                    tiearb_salt=EXPECT_SALT, tiearb_eps=EXPECT_EPS)
        chk("W2_SearchConfigRs_accepts_tiearb_kwargs", True, dict(sc.tiearb))
    except TypeError as e:
        chk("W2_SearchConfigRs_accepts_tiearb_kwargs", False, f"TypeError: {e}")

    # --- W3/W4/W5/J4: the PRODUCTION construction path, exactly as
    #     eval_fair_puct builds the candidate side.
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

        for mode in ("argmax", "random"):
            cand = dc.replace(production_prior_cfg(spec, base_leaf),
                              tiearb_enabled=True, tiearb_b=EXPECT_B,
                              tiearb_j=EXPECT_J, tiearb_mode=mode,
                              tiearb_salt=EXPECT_SALT, tiearb_eps=EXPECT_EPS)
            # ⚠️ INVERTED HASH EXPECTATION: arming the arbiter must leave the
            # leaf byte-identical. A MOVED hash here means a leaf field was
            # written — a DEFECT, the exact opposite of every leaf-term gate.
            cand_hash = _leaf_hash(cand.resolved_leaf_cfg())
            chk(f"J1_INVERTED_leaf_hash_UNMOVED_equals_champion_{mode}",
                cand_hash == CHAMP_LEAF_HASH and cand_hash == champ_hash, cand_hash)
            resolved = dict(search_config_rs(cand, 8).tiearb)
            want = {"enabled": True, "B": EXPECT_B, "J": EXPECT_J, "mode": mode,
                    "salt": EXPECT_SALT, "eps": EXPECT_EPS}
            chk(f"J4_resolved_knob_reaches_rust_{mode}", resolved == want,
                {"resolved": resolved, "expected": want})
            man = cand.as_manifest()
            chk(f"J4_resolved_knob_in_as_manifest_{mode}",
                (man["tiearb_enabled"], man["tiearb_b"], man["tiearb_j"],
                 man["tiearb_mode"], man["tiearb_salt"], man["tiearb_eps"])
                == (True, EXPECT_B, EXPECT_J, mode, EXPECT_SALT, EXPECT_EPS),
                {k: man[k] for k in man if k.startswith("tiearb")})
    except Exception as e:                          # noqa: BLE001
        chk("W3_W5_production_path", False,
            f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")

    # --- J13: THE TWO-SIDED POSITIVE CONTROL. The only liveness proof available
    #     on this surface, and BOTH sides are required.
    witness = None
    try:
        from tiearb_live import _assert_surface_tiearb_live
        witness = _assert_surface_tiearb_live(b=EXPECT_B, j=EXPECT_J, sims=PF_SIMS,
                                              k_dets=PF_KDETS,
                                              max_fired=PF_MAX_FIRED,
                                              salt=EXPECT_SALT)
        pos = witness["positive_side"]
        chk("J13_POSITIVE_arbiter_changes_the_pick", True,
            {"ply": pos["changed_at_ply"], "champ_pick": pos["champ_pick"],
             "arbiter_pick": pos["arbiter_pick"], "arms": pos["arms"],
             "fired_plies_examined": pos["fired_plies_examined"]})
        chk("J13_NEGATIVE_root_leaf_value_bits_UNCHANGED", True,
            witness["negative_side"])
    except AssertionError as e:
        chk("J13_two_sided_positive_control", False, str(e)[:2000])
    except Exception as e:                          # noqa: BLE001
        chk("J13_two_sided_positive_control", False,
            f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")

    # ⚠️ THE `G-J13` ARTIFACT CONTRACT, emitted under the exact key names the
    # adjudicator reads FAIL-CLOSED: an absent witness is a FAIL, not a pass, so
    # a spelling difference here would void a perfectly good run at
    # `U-UNREADABLE`. Both booleans are required and neither defaults to True.
    _pos = next((c for c in checks if c["check"].startswith("J13_POSITIVE")), None)
    _neg = next((c for c in checks if c["check"].startswith("J13_NEGATIVE")), None)
    two_sided = {
        "pick_changed": bool(_pos and _pos.get("ok")),
        "root_leaf_value_bits_unchanged": bool(_neg and _neg.get("ok")),
        "pick_change_witness": (_pos or {}).get("observed"),
        "root_leaf_value_bits_witness": (_neg or {}).get("observed"),
    }
    out = {
        "kind": "tiearb2_stage2_preflight",
        "host": platform.node(),
        "python": sys.executable,
        "expected": {"B": EXPECT_B, "J": EXPECT_J, "salt": EXPECT_SALT,
                     "eps": EXPECT_EPS, "champion_leaf_hash": CHAMP_LEAF_HASH},
        "toolchain": _toolchain(),
        "backend_provenance": prov,
        # `G-TOOL` witnesses, hoisted to the TOP LEVEL of this verdict so the
        # cross-box comparison never has to reach into a nested block. ⚠️
        # `carc_rs_version` is the CARGO version and does NOT move between
        # builds; `carc_rs_build` is a CONTENT hash of the installed extension,
        # and it is the one that can actually catch a stale wheel on one box.
        "rust_toolchain": (os.environ.get("RUSTUP_TOOLCHAIN")
                           or prov.get("rust_toolchain")),
        "carc_rs_build": prov.get("carc_rs_build"),
        "carc_rs_version": prov.get("carc_rs_version"),
        "all_preflight_pass": bool(ok_all),
        "checks": checks,
        "two_sided": two_sided,
        "j13_witness": witness,
        "note": "WIRING ONLY. No game played, no strength number read. "
                "measurement/tiearb2_stage2_20260817/READ_RULE.md §3 "
                "G-J1/G-J4/G-J13/G-TOOL. ⚠️ J1 is an EQUALITY gate: this surface "
                "moves no leaf hash, so a MOVED candidate hash is a DEFECT, not "
                "evidence.",
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
