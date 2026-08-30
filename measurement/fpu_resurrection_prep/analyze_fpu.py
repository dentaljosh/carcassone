#!/usr/bin/env python3
"""`analyze_fpu` — THE FPU-RESURRECTION ROUND'S ADJUDICATOR.

⛔ **THE PAIR IS LAW.** [`DESIGN.md`](DESIGN.md) + [`READ_RULE.md`](READ_RULE.md).
If this file disagrees with them, **it is this file that is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 games exist.**

The order of business, which is not negotiable:

  1. **Every §4 gate, per cell.** `ABSENT` is `FAIL`, never a skip and never a
     default. Every gate prints WHICH DOCUMENT and WHICH ADDRESS answered —
     config from `manifest.json`, statistics from `summary.json`, which carries
     no config block at all (IS-D1).
  2. **The §5 ladder, PER CELL, on that cell's own realized SE, against zero.**
     ⛔ There is no anchor cell and no hard ordering in this round: the three
     cells are three independent questions on three separate bands. Nothing is
     pooled and no cross-cell contrast is a branch input.
  3. **§6's tau trigger**, evaluated in code from `CELL_CPUCT10` alone.
  4. The companions, each flagged ⛔ NEVER A BRANCH INPUT.

⭐ `--selftest` exercises the library's arithmetic, the dense `(M, SE)` branch
grid, the shipped fixture, the named DEFECT variants, and the GOLDEN GATE
artefact — and is a PRE-LAUNCH checklist item precisely because a launcher-side
gate that runs once per round is never exercised by the smoke.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import screen_lib as L  # noqa: E402


# =========================================================================== #
# LOADING                                                                      #
# =========================================================================== #

def load_cell(root: Path) -> dict:
    """Read one archive. ⛔ Missing documents are recorded as `None` and reach
    the gates as ABSENT — this never raises past a gate."""
    man, summ = root / "manifest.json", root / "summary.json"
    recs = []
    for p in sorted(root.glob("seed*_a*.json")):
        try:
            recs.append(json.loads(p.read_text()))
        except Exception:                                     # noqa: BLE001
            recs.append({"_unreadable": str(p)})
    return {"root": str(root),
            "manifest": json.loads(man.read_text()) if man.is_file() else None,
            "summary": json.loads(summ.read_text()) if summ.is_file() else None,
            "records": recs}


def _docs(cell: dict) -> dict:
    return {"manifest": cell.get("manifest") or {},
            "summary": cell.get("summary") or {}}


# =========================================================================== #
# THE GATES — READ_RULE.md §4                                                  #
# =========================================================================== #

def _sides(cell) -> dict:
    """`{alias: {champion, opponent, champion_absent, opponent_absent,
    addresses}}` — the RESOLVED config of each side.

    ⚠️ The opponent's search knobs live ONE LEVEL DOWN under
    `config.opponent.champ_cfg.*`; a gate written from the design rather than
    from a real manifest voids every healthy cell (the phasegate `G-SINGLEVAR`
    lesson, carried)."""
    d = _docs(cell)
    rows = {}
    for a in L.SINGLEVAR_ALIASES:
        cv, ca = L.resolve(d, f"manifest:config.champion.{a}")
        ov, oa = L.resolve(d, f"manifest:config.opponent.champ_cfg.{a}",
                           f"manifest:config.opponent.{a}")
        rows[a] = {"champion": None if cv is L.MISSING else cv,
                   "opponent": None if ov is L.MISSING else ov,
                   "champion_absent": cv is L.MISSING,
                   "opponent_absent": ov is L.MISSING,
                   "addresses": [ca, oa]}
    return rows


def gate_knob(spec, cell) -> dict:
    d = _docs(cell)
    fpu, fa = L.resolve(d, "manifest:config.cand_search.fpu_reduction")
    cp, ca = L.resolve(d, "manifest:config.cand_search.c_puct")
    sc, _ = L.resolve(d, "manifest:config.cand_search.shared_c_puct")
    return L.knob_gate(spec, fpu, cp, fa, ca, sc)


def gate_twosided(spec, cell) -> dict:
    return L.twosided_gate(spec, _sides(cell))


def gate_singlevar(spec, cell) -> dict:
    return L.singlevar_gate(spec, _sides(cell))


def gate_arb_off(spec, cell) -> dict:
    return L.arb_off_gate(cell.get("manifest") or {})


def gate_leaf(spec, cell) -> dict:
    d = _docs(cell)
    ch, _ = L.resolve(d, "manifest:config.cand_leaf_hash")
    oh, _ = L.resolve(d, "manifest:config.opp_leaf_hash",
                      "manifest:config.opponent.leaf_hash")
    cv, _ = L.resolve(d, "manifest:config.cand_leaf_cfg.v29_meeple_curve")
    return L.leaf_gate(None if ch is L.MISSING else ch,
                       None if oh is L.MISSING else oh,
                       None if cv is L.MISSING else cv)


def gate_band(spec, cell) -> dict:
    d = _docs(cell)
    start, a1 = L.resolve(d, "manifest:config.band_seed_start",
                          "manifest:band_seed_start")
    ndecks, a2 = L.resolve(d, "manifest:config.n_decks", "manifest:n_decks")
    seat, a3 = L.resolve(d, "manifest:config.seatings_per_deck",
                         "manifest:seatings_per_deck")
    bad = []
    if start is L.MISSING:
        bad.append("band_seed_start ABSENT")
    elif int(start) != spec.seed_start:
        bad.append(f"band_seed_start {start} != frozen {spec.seed_start}")
    if ndecks is not L.MISSING and int(ndecks) != spec.n_decks:
        bad.append(f"n_decks {ndecks} != frozen {spec.n_decks}")
    if seat is not L.MISSING and int(seat) != 2:
        bad.append(f"seatings_per_deck {seat} != 2")
    return L.gate("G-BAND", not bad,
                  {"band_seed_start": None if start is L.MISSING else start,
                   "n_decks": None if ndecks is L.MISSING else ndecks,
                   "seatings_per_deck": None if seat is L.MISSING else seat,
                   "frozen_band": spec.seed_start, "addresses": [a1, a2, a3]},
                  a1, ("the cell is on its OWN frozen band with the frozen deck "
                       "count, 2 seatings per deck" if not bad else
                       "⛔ G-BAND FAILED: " + "; ".join(bad)))


def gate_budget(spec, cell) -> dict:
    """`G-BUDGET` — ⭐ RE-FROZEN 2026-08-30 at the promoted champion k16x1376 =
    22016 BOTH SIDES. A cell that ran the superseded 11008 is measuring the knob
    against a stale opponent and voids."""
    d = _docs(cell)
    rows, bad = {}, []
    for side, base in (("champion", "config.champion"),
                       ("opponent", "config.opponent.champ_cfg")):
        k, _ = L.resolve(d, f"manifest:{base}.k_dets",
                         "manifest:config.opponent.k_dets")
        s, _ = L.resolve(d, f"manifest:{base}.sims_per_det",
                         "manifest:config.opponent.sims_per_det")
        t, _ = L.resolve(d, f"manifest:{base}.total_sims",
                         "manifest:config.opponent.total_sims")
        rows[side] = {"k_dets": None if k is L.MISSING else k,
                      "sims_per_det": None if s is L.MISSING else s,
                      "total_sims": None if t is L.MISSING else t}
        if L.MISSING in (k, s, t):
            bad.append(f"{side}: a budget field is ABSENT")
            continue
        if (int(k), int(s), int(t)) != (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS):
            bad.append(f"{side}: ({k},{s},{t}) != "
                       f"({L.K_DETS},{L.SIMS_PER_DET},{L.TOTAL_SIMS})")
        elif int(k) * int(s) != int(t):
            bad.append(f"{side}: {k} x {s} != {t} — the product does not multiply out")
    return L.gate("G-BUDGET", not bad, rows,
                  "manifest:config.{champion,opponent}.*",
                  (f"both sides run k{L.K_DETS} x {L.SIMS_PER_DET} = "
                   f"{L.TOTAL_SIMS} (the 2026-08-30 promoted desktop champion) "
                   "and the product multiplies out" if not bad else
                   "⛔ G-BUDGET FAILED: " + "; ".join(bad)))


def _simple(gid, cell, checks, address_note) -> dict:
    d = _docs(cell)
    rows, bad = {}, []
    for alias, want, label in checks:
        v, a = L.resolve(d, *alias)
        rows[label] = {"value": None if v is L.MISSING else v, "address": a}
        if v is L.MISSING:
            bad.append(f"{label} ABSENT")
        elif callable(want):
            if not want(v):
                bad.append(f"{label} = {v!r}")
        elif v != want:
            bad.append(f"{label} = {v!r}, want {want!r}")
    return L.gate(gid, not bad, rows, address_note,
                  "ok" if not bad else f"⛔ {gid} FAILED: " + "; ".join(bad))


def gate_exact(spec, cell) -> dict:
    return _simple("G-EXACT", cell, [
        (("manifest:config.endgame.exact_k",), L.EXACT_K, "exact_k"),
        (("manifest:config.endgame.mode",), L.EXACT_MODE, "mode"),
    ], "manifest:config.endgame.*")


def gate_rules(spec, cell) -> dict:
    return _simple("G-RULES", cell, [
        (("manifest:rules_profile.name",), L.RULES_PROFILE, "rules_profile.name"),
        (("manifest:rules_profile.r9_env_ok",), True, "r9_env_ok"),
        (("manifest:rules_profile.r9_env_observed",), True, "r9_env_observed"),
    ], "manifest:rules_profile.* (⚠️ R9 is env-latched at IMPORT)")


def gate_backend(spec, cell) -> dict:
    return _simple("G-BACKEND", cell, [
        (("manifest:config.backend.name",), L.BACKEND, "name"),
        (("manifest:config.backend.requested",), L.BACKEND, "requested"),
        (("manifest:config.backend.mixed_builds", "manifest:mixed_builds"),
         lambda v: v is False, "mixed_builds"),
        (("manifest:config.backend.converted_sides",),
         lambda v: sorted(v) == ["candidate", "opponent"], "converted_sides"),
    ], "manifest:config.backend.* — ⚠️ BOTH knobs are threaded on BOTH backends "
       "(unlike the J-rules surfaces and the tie arbiter, which are rust-only), "
       "so a python leg would NOT be knob-blind. It is still refused: the "
       "champion of record plays on rust, and a mixed-backend round is not one "
       "round.")


def gate_wheel(spec, cell) -> dict:
    return _simple("G-WHEEL", cell, [
        (("manifest:carc_rs_build",),
         lambda v: bool(v) and "unavailable" not in str(v), "carc_rs_build"),
        (("manifest:carc_rs_binary_sha",), lambda v: bool(v), "carc_rs_binary_sha"),
        (("manifest:mixed_builds",), lambda v: v is False, "mixed_builds"),
    ], "manifest — ⚠️ carc_rs_version is permanently '0.1.0' and is NOT a "
       "discriminator. ⭐ THIS ROUND MAKES NO RUST CHANGE: `carc_rs` already "
       "accepted Option<f64> in the fpu slot and carc_core::search already "
       "implemented the rule, so the wheel is a CONSTANT here and the risk that "
       "phasegate's IDENT cell existed for does not arise. The live risk is the "
       "PYTHON rev (G-REV), not the binary.")


def gate_n(spec, cell) -> dict:
    d = _docs(cell)
    n, a1 = L.resolve(d, "summary:n")
    nf, a2 = L.resolve(d, "summary:n_failed", "manifest:n_failed")
    nc = len(L.per_deck_margins(cell.get("records") or []))
    bad, notes = [], []
    if n is L.MISSING:
        bad.append("summary.n ABSENT")
    elif int(n) != spec.n_games:
        bad.append(f"n {n} != frozen {spec.n_games} games")
    if nf is L.MISSING:
        bad.append("n_failed ABSENT")
    else:
        rate = float(nf) / max(1, spec.n_games)
        if float(nf) > 0:
            notes.append(f"⚠️ n_failed = {nf} ({rate:.4%}) — REPORTED, never "
                         "silently absorbed (the b32v64 0.100% rust-panic "
                         "precedent)")
        if rate >= L.FAILURE_RATE_VOID:
            bad.append(f"failure rate {rate:.4%} >= {L.FAILURE_RATE_VOID:.0%}")
    floor = L.N_COMMON_FLOOR_FRACTION * spec.n_decks
    if nc < floor:
        bad.append(f"n_common {nc} < 80% of {spec.n_decks} ({floor:.0f})")
    return L.gate("G-N", not bad,
                  {"n": None if n is L.MISSING else n,
                   "frozen_n_games": spec.n_games,
                   "n_failed": None if nf is L.MISSING else nf, "n_common": nc,
                   "n_common_floor": floor, "notes": notes,
                   "addresses": [a1, a2]},
                  "summary.json",
                  ("; ".join(notes) or "n, n_failed and n_common are at the "
                   "frozen plan") if not bad else
                  "⛔ G-N FAILED: " + "; ".join(bad))


def gate_sat(spec, cell) -> dict:
    d = _docs(cell)
    wr, a = L.resolve(d, "summary:winrate")
    if wr is L.MISSING:
        return L.gate("G-SAT", False, {"winrate": None}, None,
                      "⛔ winrate ABSENT — ABSENT is FAIL")
    lo, hi = L.SAT_BAND
    ok = lo <= float(wr) <= hi
    return L.gate("G-SAT", ok, {"winrate": wr, "band": list(L.SAT_BAND)}, a,
                  ("inside the rail" if ok else
                   f"⛔ winrate {wr} outside {L.SAT_BAND} — a RAIL check, not a "
                   "strength bar: both sides run the same search on the same "
                   "leaf at the same budget, so this means the two sides are "
                   "not the agents this design says they are"))


def gate_host(spec, cell) -> dict:
    v, a = L.resolve(_docs(cell), "manifest:host")
    ok, why = L.host_matches_box(None if v is L.MISSING else v, spec.role)
    return L.gate("G-HOST", ok, {"host": None if v is L.MISSING else v,
                                 "frozen_role": spec.role}, a, why)


def gate_recon(spec, cell) -> dict:
    """`RECON` — the witness. ⛔ It can only VOID, never move, a number."""
    recs = cell.get("records") or []
    m, z, n, se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    d = _docs(cell)
    rows, bad = {}, []
    for label, mine, aliases in (
        ("paired_mean_margin", m, ("summary:paired_mean_margin",)),
        ("paired_z", z, ("summary:paired_z",)),
        ("n_paired", n, ("summary:n_paired",)),
        ("winrate", we["winrate"], ("summary:winrate",)),
        ("elo", we["elo"], ("summary:elo",)),
    ):
        theirs, a = L.resolve(d, *aliases)
        t = None if theirs is L.MISSING else theirs
        agree = L.recon_close(mine, t)
        rows[label] = {"witness": mine, "summary": t, "agree": agree, "address": a}
        if not agree:
            bad.append(f"{label}: witness {mine!r} vs summary {t!r}")
    return L.gate("RECON", not bad, rows, "summary.json vs the raw records",
                  ("the fsum witness agrees on all five statistics" if not bad
                   else "⛔ RECON DISAGREES — the cell VOIDS: " + "; ".join(bad)))


GATES = (gate_knob, gate_twosided, gate_singlevar, gate_arb_off, gate_leaf,
         gate_band, gate_budget, gate_exact, gate_rules, gate_backend,
         gate_wheel, gate_n, gate_sat, gate_host, gate_recon)


def adjudicate_cell(spec, cell) -> dict:
    gates = [g(spec, cell) for g in GATES]
    gates.append(L.decks_gate(spec, cell.get("records") or []))
    m, z, n, se, per_deck = L.paired_margin(cell.get("records") or [])
    we = L.winrate_elo(cell.get("records") or [])
    return {
        "cell": spec.name, "role": spec.role, "knob": spec.knob,
        "value": spec.value, "band": spec.seed_start, "purpose": spec.purpose,
        "gates": gates,
        "gates_ok": all(g["ok"] for g in gates),
        "failed_gates": [g["gate"] for g in gates if not g["ok"]],
        "stats": {"M": m, "z": z, "n_paired": n, "se": se,
                  "UB95": None if (m is None or se is None) else m + 2 * se,
                  "LB95": None if (m is None or se is None) else m - 2 * se,
                  "bar_M": L.BAR_M},
        # ⚠️ THE SECONDARY, reported beside the primary on EVERY branch and never
        # quoted bare. READ_RULE §5: the MARGIN carries the branch.
        # ⭐ R4 (pre-launch merge review): the CI is built on the DECK-PAIRED
        # sigma, which is the footing BAR_ELO is stated on. The unpaired
        # binomial figure is carried beside it so the correction is auditable,
        # and every field NAMES its footing.
        "secondary_elo": {
            "elo": we["elo"],
            "footing": we["elo_footing"],
            "sigma_1_paired": we["elo_sig_1sigma_paired"],
            "sigma_1_unpaired": we["elo_sig_1sigma_unpaired"],
            "pairing_factor": we.get("elo_pairing_factor", L.PAIRING_FACTOR),
            "winrate": we["winrate"], "W": we["W"], "D": we["D"], "L": we["L"],
            "ci95_elo_paired": (
                None if we["elo"] is None or we["elo_sig_1sigma_paired"] is None
                else [we["elo"] - 2 * we["elo_sig_1sigma_paired"],
                      we["elo"] + 2 * we["elo_sig_1sigma_paired"]]),
            "bar_elo": L.BAR_ELO,
            "bar_elo_footing": "deck-paired 2σ at 800 games / 400 decks — the "
                               "SAME footing as ci95_elo_paired (R4)",
            "warning": "⚠️ elo may NEVER be quoted bare. It is the SECONDARY; "
                       "the deck-paired MARGIN carries the branch. A "
                       "disagreement between the two is DISCLOSED, not "
                       "arbitrated. ⛔ NO branch reads this block.",
        },
        "se_anomaly": L.se_anomaly(se, max(1, n)),
        "_per_deck": per_deck,
    }


# =========================================================================== #
# THE ROUND                                                                    #
# =========================================================================== #

def adjudicate(cells_by_name: dict, pins_by_role: dict | None = None,
               smoke_mode: bool = False, specs=None) -> dict:
    """⚠️ `specs` exists ONLY for the selftest fixture, which is the same round
    at a tiny deck scale. A real read passes nothing and gets `screen_lib.CELLS`
    — the frozen plan. `selftest()` additionally asserts the fixture's specs
    differ from the frozen ones in `seed_start`/`n_decks` and NOTHING else."""
    specs = tuple(specs or L.CELLS)
    per_cell = {}
    for spec in specs:
        if spec.name in cells_by_name:
            per_cell[spec.name] = adjudicate_cell(spec, cells_by_name[spec.name])

    # --- round-level gates -------------------------------------------------
    round_gates = []
    shas = {n: (c.get("manifest") or {}).get("carc_rs_binary_sha")
            for n, c in cells_by_name.items()}
    # ⚠️ `carc_rs_binary_sha` is BOX-LOCAL: two boxes compiling the identical
    # source produce different bytes. G-WHEEL-SAME is therefore asserted PER BOX;
    # the cross-box build identity is `carc_rs_build`'s job.
    by_role: dict[str, set] = {}
    for n, s in shas.items():
        spec = next((c for c in specs if c.name == n), None)
        if spec:
            by_role.setdefault(spec.role, set()).add(s)
    bad_roles = {r: sorted(map(str, v)) for r, v in by_role.items() if len(v) > 1}
    round_gates.append(L.gate(
        "G-WHEEL-SAME", not bad_roles and bool(by_role),
        {"binary_sha_by_cell": shas,
         "by_role": {k: sorted(map(str, v)) for k, v in by_role.items()}},
        "manifest:carc_rs_binary_sha",
        ("every cell on a box shares that box's binary sha ⚠️ the sha is "
         "BOX-LOCAL and is never compared ACROSS boxes. ⭐ This round makes NO "
         "rust change, so the wheel should not move at all mid-round."
         if not bad_roles and by_role else
         f"⛔ a box ran more than one wheel: {bad_roles or 'no cells'} — "
         "A FAIL ON ANY CELL VOIDS EVERY CELL")))

    revs = {n: (c.get("manifest") or {}).get("code_rev")
            for n, c in cells_by_name.items()}
    rg = L.cross_box_rev_gate(revs, pins_by_role or {})
    round_gates.append(L.gate("G-REV", rg["ok"], rg,
                              "manifests + each box's PINNED_SRC_REV", rg["why"]))

    blinds = {n: (c.get("manifest") or {}).get("BLIND_COMMIT")
              for n, c in cells_by_name.items()}
    distinct_blind = sorted({b for b in blinds.values() if b})
    blind_ok = (len(distinct_blind) == 1 and L.is_hex40(distinct_blind[0])
                and all(blinds.values()))
    round_gates.append(L.gate(
        "G-BLIND", blind_ok, {"BLIND_COMMIT_by_cell": blinds},
        "manifest:BLIND_COMMIT",
        ("one 40-hex BLIND_COMMIT stamped into every adjudicated manifest"
         if blind_ok else
         "⛔ BLIND_COMMIT absent, malformed, or disagreeing across cells — "
         "ABSENT is FAIL; a read that was not blind is not a read")))

    round_ok = all(g["ok"] for g in round_gates)

    # --- the ladder, PER CELL ---------------------------------------------
    # ⛔ NO ANCHOR, NO POOLING, NO HARD ORDERING. Three bands, three questions.
    branches = {}
    for name, c in per_cell.items():
        st = c["stats"]
        branches[name] = L.branch_for_cell(
            st["M"], st["se"], st["z"], gates_ok=(c["gates_ok"] and round_ok))
        c["branch"] = branches[name]
        c["riders"] = list(L.RIDERS_ALWAYS) + list(
            L.RIDERS_F_RESURRECT if branches[name] == "F-RESURRECT" else
            L.RIDERS_F_REKILL if branches[name] == "F-REKILL" else
            L.RIDERS_F_NEGATIVE if branches[name] == "F-NEGATIVE" else
            L.RIDERS_F_UNRESOLVED if branches[name] == "F-UNRESOLVED" else ())

    tau = L.tau_trigger(per_cell.get("CELL_CPUCT10"))

    out = {
        "round": "fpu_resurrection (3 cells, 3 bands)",
        "pair": ["measurement/fpu_resurrection_prep/DESIGN.md",
                 "measurement/fpu_resurrection_prep/READ_RULE.md"],
        "smoke_mode": smoke_mode,
        "budget": {"k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
                   "total_sims": L.TOTAL_SIMS,
                   "note": "the 2026-08-30 promoted desktop champion, BOTH sides"},
        "round_gates": round_gates,
        "round_gates_ok": round_ok,
        "cells": per_cell,
        "branches": branches,
        "tau_conditionality": tau,
        "golden_gate": _golden_gate_status(),
        "riders": list(L.RIDERS_ALWAYS),
    }
    if any(b == "U-VOID-INSTRUMENT" for b in branches.values()):
        out["void_banner"] = ("⛔ at least one cell is U-VOID-INSTRUMENT — the "
                              "instrument, not the world. That cell's statistics "
                              "are printed as a COMPANION TABLE only, and no "
                              "reading of any kind is taken from it. ⚠️ The other "
                              "cells are UNAFFECTED: they are separate questions "
                              "on separate bands.")

    # --- companions. ⛔ NEVER branch inputs --------------------------------
    comp: dict = {
        "_warning": "⛔ COMPANIONS — NEVER A BRANCH INPUT.",
        "prior_art": L.PRIOR_ART,
        "prior_art_warning":
            "⛔ CROSS-ERA AND CROSS-BAND. Never pooled, never z-combined, never "
            "a gate input. CL-068 measured 1.8-2.2x over-dispersion on merely "
            "CROSS-BAND contrasts; these are also cross-AGENT (neural / "
            "value-blended vs the classical champion) and cross-BUDGET.",
        "fpu_dose_direction": None,
        "family_wise":
            "⛔ THREE CELLS = THREE COMPARISONS. Family-wise false-fire rate "
            "under a global null at the 2-sigma bar is ~7%. No correction is "
            "applied (the bars are pre-registered and each cell is its own "
            "question) but a LONE firing cell beside two nulls is a NOISE "
            "SIGNATURE, not a peak.",
    }
    f2, f4 = per_cell.get("CELL_FPU02"), per_cell.get("CELL_FPU04")
    if f2 and f4 and f2["stats"]["M"] is not None and f4["stats"]["M"] is not None:
        comp["fpu_dose_direction"] = {
            "M_at_0.2": f2["stats"]["M"], "M_at_0.4": f4["stats"]["M"],
            "direction": ("rising with dose" if f4["stats"]["M"] > f2["stats"]["M"]
                          else "falling with dose"),
            "warning": "⛔⛔ NOT A BRACKET AND NOT A BRANCH INPUT. Two points do "
                       "not locate an optimum, the two cells are on DIFFERENT "
                       "BANDS (so CL-068's 1.8-2.2x over-dispersion applies to "
                       "any contrast between them), and no interpolation "
                       "between 0.2 and 0.4 is licensed "
                       "(feedback_bracket_hyperparams).",
        }
    out["companions"] = comp
    return out


# =========================================================================== #
# ⭐⭐ R1 — THE SMOKE'S OWN SPECS (pre-launch merge review, 2026-08-30)         #
# =========================================================================== #
# ⛔⛔ THE DEFECT THIS CLOSES. `--smoke-mode` adjudicated ZERO cells, by TWO
# independent mechanisms, and still exited 0 — so `run_cells.sh`'s
# `|| DIE "the smoke adjudication FAILED"` was UNREACHABLE and the smoke's one
# substantive job (read the RESOLVED KNOB back out of the EMITTED manifest)
# silently did nothing:
#
#   (1) the cell scan dropped every dir named `SMOKE_*` (the launcher names them
#       `SMOKE_FPU` / `SMOKE_CPUCT`) — correct for a ROUND read, fatal for a
#       SMOKE read, which adjudicates at the parent `$SHARE/$OUT_TAG`;
#   (2) `adjudicate()` iterates `screen_lib.CELLS`, which names only the three
#       ROUND cells, so a `SMOKE_*` dir had no spec to be adjudicated against.
#
# ⚠️ The identical defect is REALIZED in phasegate's banked `SMOKE_local.json`
# (`"cells": {}`) — see `measurement/phasegate_prep/AMENDMENTS.md` (PG-D10, and
# the PG-A2 candidate note appended 2026-08-30).
#
# The smoke's spec cannot come from `L.CELLS` (it is not a round cell) and must
# not be invented here (a restated knob proves nothing about the launcher), so
# `run_cells.sh` PASSES it and the value is then checked against what the
# harness actually EMITTED.

SMOKE_CELL_SYNTAX = "NAME=knob:value:seed_start:n_games:role"


def parse_smoke_cell(text: str) -> "L.CellSpec":
    """`SMOKE_FPU=fpu_reduction:0.2:157999999500:8:local` -> a `CellSpec`.

    ⛔ The NAME must start with `SMOKE_`: only smoke archives are adjudicable in
    `--smoke-mode`, and admitting any other name would let a re-smoke at a root
    that already holds real cells adjudicate a ROUND cell under smoke rules.
    ⛔ The knob and value are the LAUNCHER'S REQUEST. They are not trusted — they
    become `G-FPU`/`G-CPUCT`'s frozen expectation, which is then checked against
    `manifest.json`'s `config.cand_search.*`, i.e. against what was EMITTED.
    """
    name, sep, rest = text.partition("=")
    if not sep:
        raise ValueError(f"--smoke-cell {text!r}: expected {SMOKE_CELL_SYNTAX}")
    parts = rest.split(":")
    if len(parts) != 5:
        raise ValueError(f"--smoke-cell {text!r}: expected {SMOKE_CELL_SYNTAX} "
                         f"(got {len(parts)} field(s) after '=')")
    knob, value, seed_start, n_games, role = parts
    if role not in ("local", "laptop"):
        raise ValueError(f"--smoke-cell {text!r}: role must be local|laptop "
                         "— G-HOST proves the smoke ran on the box whose code "
                         "path it was written to exercise")
    if not name.startswith("SMOKE_"):
        raise ValueError(f"--smoke-cell {text!r}: the name must start with "
                         "'SMOKE_' — only smoke archives are adjudicable in "
                         "--smoke-mode, and a round cell must never be")
    if knob not in ("fpu_reduction", "c_puct"):
        raise ValueError(f"--smoke-cell {text!r}: unknown knob {knob!r}")
    n = int(n_games)
    if n < 2 or n % 2:
        raise ValueError(f"--smoke-cell {text!r}: n_games {n} is not an even "
                         "count of deck-paired games")
    return L.CellSpec(name=name, role=role, knob=knob, value=float(value),
                      seed_start=int(seed_start), n_decks=n // 2,
                      purpose="⭐ THE §9 SMOKE — the THROWAWAY sub-range, "
                              "PRODUCTION knobs, only the game count reduced. "
                              "⛔ Buys no deck of the round and claims no band.")


#: The gates the smoke EXISTS to run. ⛔ A smoke archive legitimately fails
#: gates about the ROUND (`G-BLIND` — it is stamped with no blind commit;
#: `G-REV` — it runs at the PRE-LAUNCH commit by design; `G-N` — 8 games, not
#: 800), so "all gates ok" is the wrong bar and would make the smoke unusable.
#: These three are the ones whose failure means the LAUNCHER is wrong:
#:   * `G-FPU`/`G-CPUCT` — the knob was REQUESTED, at the right dose, and the
#:     emitted manifest says so;
#:   * `G-TWOSIDED`      — it BOUND, and bound on the CANDIDATE side ONLY. This
#:     is the `--c-puct` both-sides trap (run_cells.sh:288-291): the shared flag
#:     builds the opponent too, so a cell built on it is champion-vs-champion
#:     and every other gate passes it.
SMOKE_REQUIRED_GATES = ("G-FPU", "G-CPUCT", "G-TWOSIDED")


def smoke_problems(v: dict) -> list[str]:
    """⛔ NON-EMPTY == the smoke FAILED == a non-zero exit, which is what makes
    `run_cells.sh`'s `|| DIE "the smoke adjudication FAILED"` REACHABLE."""
    probs: list[str] = []
    cells = v.get("cells") or {}
    knobs = v.get("resolved_knobs") or {}
    if not cells:
        probs.append(
            "⛔⛔ THE SMOKE ADJUDICATED ZERO CELLS. Nothing was read, so nothing "
            "was proven — and an exit 0 here is exactly the R1 defect (an "
            "unreachable `|| DIE` in the launcher). Check that the smoke "
            "archive exists under --root, is named SMOKE_*, carries a "
            "manifest.json, and that its name matches a --smoke-cell "
            f"({SMOKE_CELL_SYNTAX}).")
    if not knobs:
        probs.append("⛔ resolved_knobs is EMPTY — the smoke's one substantive "
                     "job is to return the knob AS THE HARNESS WROTE IT, read "
                     "off the emitted manifest.json. Nothing was read.")
    for name in cells:
        k = knobs.get(name)
        if not k:
            probs.append(f"⛔ {name}: no resolved knob could be read from its "
                         "manifest.json — ABSENT is FAIL")
        elif k.get("requested_fpu_reduction") is None and \
                k.get("requested_c_puct_override") is None:
            probs.append(f"⛔ {name}: the emitted manifest requested NEITHER a "
                         "fpu_reduction NOR a c_puct override — the launcher "
                         "did not put the knob on the wire")
    for name, c in cells.items():
        by_id = {g["gate"]: g["ok"] for g in c.get("gates", [])}
        ran = [g for g in SMOKE_REQUIRED_GATES if g in by_id]
        if not ran:
            probs.append(f"⛔ {name}: none of {SMOKE_REQUIRED_GATES} executed")
        for gid in ran:
            if not by_id[gid]:
                probs.append(
                    f"⛔ {name}: {gid} FAILED. " + (
                        "The knob did not BIND on the candidate, or it bound on "
                        "the OPPONENT TOO — the `--c-puct` both-sides trap "
                        "(run_cells.sh:288-291). A round launched over this is "
                        "champion-vs-champion."
                        if gid == "G-TWOSIDED" else
                        "The emitted manifest does not carry the knob this box "
                        "was told to smoke."))
    return probs


def _golden_gate_status() -> dict:
    """⭐ The GOLDEN GATE artefact, surfaced in every read-out.

    A round whose knob was never proven to BIND is not a round. `FPU_BITEXACT`
    is that proof and it is carried in-tree, so the read-out states its verdict
    rather than assuming it."""
    p = HERE / "FPU_BITEXACT.json"
    if not p.is_file():
        return {"verdict": "ABSENT", "ok": False,
                "why": "⛔ FPU_BITEXACT.json ABSENT — ABSENT is FAIL. The knob "
                       "is not proven to bind and the default path is not "
                       "proven unmoved."}
    v = json.loads(p.read_text())
    return {"verdict": v.get("verdict"), "ok": v.get("verdict") == "PASS",
            "failed": v.get("failed"),
            "checks": {c["check"]: c["ok"] for c in v.get("checks", [])},
            "why": "⭐ bit-exact at fpu=None (the DEFAULT path is unmoved) AND "
                   "the knob BINDS at 0.2 (the positive control). Without the "
                   "second half the first is worth nothing: the hard-coded None "
                   "this round removes would have passed it perfectly."}


# =========================================================================== #
# SELFTEST                                                                     #
# =========================================================================== #

def fixture_specs(fx: Path):
    return tuple(L.CellSpec(**s) for s in json.loads((fx / "SPECS.json").read_text()))


def _set(cell: dict, dotted: str, value) -> None:
    cur = cell
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _del(cell: dict, dotted: str) -> None:
    cur = cell
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur.get(p, {})
    cur.pop(parts[-1], None)


#: ⭐ THE NAMED DEFECTS — one per gate whose failure would otherwise never be
#: observed. Each must (a) fire its own gate and (b) drive its cell to a VOID.
#: ⛔⛔ The first three are this design's most dangerous failure mode, in its
#: three disguises: a cell whose knob NEVER BOUND is champion-vs-champion, moves
#: no leaf hash, sits inside G-SAT's rail, and reads as a clean credible null.
FIXTURE_DEFECTS = (
    ("hardcoded_none_defect_knob_never_bound",
     lambda c: _set(c["CELL_FPU02"]["manifest"],
                    "config.champion.fpu_reduction", None),
     "G-TWOSIDED"),
    ("harness_predates_the_round_cand_search_absent",
     lambda c: _del(c["CELL_FPU02"]["manifest"], "config.cand_search"),
     "G-FPU"),
    ("wrong_dose_on_the_wire",
     lambda c: _set(c["CELL_FPU04"]["manifest"],
                    "config.cand_search.fpu_reduction", 0.2),
     "G-CPUCT" if False else "G-FPU"),
    ("shared_c_puct_moved_BOTH_sides",
     lambda c: _set(c["CELL_CPUCT10"]["manifest"],
                    "config.opponent.champ_cfg.c_puct", 1.0),
     "G-TWOSIDED"),
    ("opponent_carries_an_fpu",
     lambda c: _set(c["CELL_FPU02"]["manifest"],
                    "config.opponent.champ_cfg.fpu_reduction", 0.2),
     "G-TWOSIDED"),
    ("a_second_variable_moved",
     lambda c: _set(c["CELL_FPU02"]["manifest"], "config.champion.tau_p", 8.0),
     "G-SINGLEVAR"),
    ("tie_arbiter_left_armed",
     lambda c: _set(c["CELL_FPU04"]["manifest"],
                    "config.cand_tiearb.enabled", True),
     "G-ARB-OFF"),
    ("stale_budget_11008",
     lambda c: (_set(c["CELL_FPU02"]["manifest"], "config.champion.k_dets", 8),
                _set(c["CELL_FPU02"]["manifest"], "config.champion.total_sims",
                     11008)),
     "G-BUDGET"),
    ("leaf_hashes_differ_across_the_two_sides",
     lambda c: _set(c["CELL_FPU04"]["manifest"], "config.opp_leaf_hash", "deadbeef"),
     "G-LEAF"),
    ("mixed_rev_round",
     lambda c: _set(c["CELL_CPUCT10"]["manifest"], "code_rev", "cccccccc"),
     "G-REV"),
    ("recon_disagrees_with_the_summary",
     lambda c: _set(c["CELL_FPU02"]["summary"], "paired_mean_margin", 99.0),
     "RECON"),
    ("a_deck_was_played_at_one_seat_only",
     lambda c: c["CELL_FPU02"]["records"].pop(),
     "G-DECKS"),
    ("cell_ran_on_the_wrong_box",
     lambda c: _set(c["CELL_CPUCT10"]["manifest"], "host", "Doctor"),
     "G-HOST"),
)


def selftest() -> int:
    problems = list(L.sanity_check())
    grid = L.branch_grid(step=0.02)
    if not grid["all_reachable"]:
        problems.append(f"branch grid: only {grid['reachable']} reachable")

    gg = _golden_gate_status()
    if not gg["ok"]:
        problems.append(f"⛔ the GOLDEN GATE is {gg['verdict']} — the knob is not "
                        "proven to bind and the default path is not proven "
                        "unmoved. No cell may be played over this.")

    # ABSENT is FAIL, at every gate, on an EMPTY archive
    empty = {"root": "<empty>", "manifest": None, "summary": None, "records": []}
    for spec in L.CELLS:
        r = adjudicate_cell(spec, empty)
        if r["gates_ok"]:
            problems.append(f"{spec.name}: an EMPTY archive passed the gates — "
                            "ABSENT must be FAIL")
        for g in r["gates"]:
            if g["ok"]:
                problems.append(f"{spec.name}/{g['gate']}: passed on an EMPTY "
                                "archive (vacuous pass — the IS-D1 class)")

    v = adjudicate({c.name: empty for c in L.CELLS}, pins_by_role={})
    if set(v["branches"].values()) != {"U-VOID-INSTRUMENT"}:
        problems.append(f"an all-empty round read {v['branches']}, not all-void")
    if v["tau_conditionality"]["triggered"]:
        problems.append("an all-empty round TRIGGERED the tau pair")

    # ------------------------------------------------------------------ #
    # THE SHIPPED FIXTURE — a shaped, HEALTHY round, plus the named defects #
    # ------------------------------------------------------------------ #
    fx = HERE / "selftest_fixture"
    report: dict = {}
    if fx.is_dir() and (fx / "SPECS.json").is_file():
        specs = fixture_specs(fx)
        frozen = {c.name: c for c in L.CELLS}
        if sorted(s.name for s in specs) != sorted(frozen):
            problems.append("the fixture's cell NAMES differ from the frozen plan")
        for s in specs:
            f = frozen.get(s.name)
            if f is None:
                continue
            for field in ("role", "knob", "value"):
                if getattr(s, field) != getattr(f, field):
                    problems.append(f"fixture {s.name}.{field} = "
                                    f"{getattr(s, field)!r} != frozen "
                                    f"{getattr(f, field)!r} — a fixture may "
                                    "differ from the round in SCALE ONLY")
        cells = {p.name: load_cell(p) for p in sorted(fx.iterdir())
                 if p.is_dir() and (p / "manifest.json").is_file()}
        pin = (fx / "PINNED_SRC_REV").read_text().strip()
        v = adjudicate(cells, pins_by_role={"local": pin, "laptop": pin},
                       specs=specs)
        report["healthy"] = {
            "branches": v["branches"],
            "failed_round_gates": [g["gate"] for g in v["round_gates"]
                                   if not g["ok"]],
            "failed_cell_gates": {n: c["failed_gates"]
                                  for n, c in v["cells"].items()
                                  if c["failed_gates"]},
            "tau": v["tau_conditionality"]["triggered"],
        }
        if report["healthy"]["failed_round_gates"]:
            problems.append("the HEALTHY fixture failed round gate(s): "
                            f"{report['healthy']['failed_round_gates']}")
        if report["healthy"]["failed_cell_gates"]:
            problems.append("the HEALTHY fixture failed cell gate(s): "
                            f"{report['healthy']['failed_cell_gates']}")
        # the fixture is SHAPED so all three branches that matter are exercised
        want = {"CELL_FPU02": "F-RESURRECT", "CELL_FPU04": "F-REKILL",
                "CELL_CPUCT10": "F-UNRESOLVED"}
        if v["branches"] != want:
            problems.append(f"the HEALTHY fixture read {v['branches']}, want {want}")
        # ⭐ and the funded conditionality must fire correctly on it
        if v["tau_conditionality"]["triggered"]:
            problems.append("the HEALTHY fixture's F-UNRESOLVED CELL_CPUCT10 "
                            "TRIGGERED the tau pair — it must RE-KILL it")

        # ⭐ THE DEFECT VARIANTS — a gate nobody has seen FAIL is untested.
        for label, mutate, want_gate in FIXTURE_DEFECTS:
            mut = {n: json.loads(json.dumps(c, default=str))
                   for n, c in cells.items()}
            mutate(mut)
            vv = adjudicate(mut, pins_by_role={"local": pin, "laptop": pin},
                            specs=specs)
            fired = ([g["gate"] for g in vv["round_gates"] if not g["ok"]]
                     + sorted({x for c in vv["cells"].values()
                               for x in c["failed_gates"]}))
            voided = [n for n, b in vv["branches"].items()
                      if b == "U-VOID-INSTRUMENT"]
            report[label] = {"branches": vv["branches"], "failed": fired,
                             "voided": voided}
            if want_gate not in fired:
                problems.append(f"defect {label!r} did NOT fire {want_gate} "
                                f"(fired: {fired})")
            if not voided:
                problems.append(f"defect {label!r} voided NO cell")
    else:
        problems.append("⚠️ selftest_fixture/ is not populated — the adjudicator "
                        "has never been run against a shaped archive. This is a "
                        "BUILD DEBT, and it is reported rather than hidden.")

    print(json.dumps({"problems": problems, "fixture": report,
                      "branch_grid": grid, "golden_gate": gg,
                      "bars": {"BAR_M": L.BAR_M, "BAR_ELO": L.BAR_ELO,
                               "BRANCH_Z": L.BRANCH_Z},
                      "budget": [L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS]},
                     indent=2))
    print(f"\nSELFTEST: {'PASS' if not problems else 'FAIL'} "
          f"({len(problems)} problem(s))")
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", type=Path,
                    help="directory holding one subdir per cell")
    ap.add_argument("--pin-local", type=Path, help="local box's PINNED_SRC_REV")
    ap.add_argument("--pin-laptop", type=Path, help="laptop's PINNED_SRC_REV")
    ap.add_argument("--smoke-mode", action="store_true",
                    help="structural keys ONLY — ⛔ the smoke emits NO outcome key")
    ap.add_argument("--smoke-cell", action="append", default=[], metavar=SMOKE_CELL_SYNTAX,
                    help="⭐ R1: the §9 smoke's own synthetic cell spec, PASSED "
                         "BY run_cells.sh. Required by (and only legal with) "
                         "--smoke-mode. Repeatable.")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.root:
        ap.error("--root or --selftest")
    if args.smoke_cell and not args.smoke_mode:
        ap.error("--smoke-cell is only legal with --smoke-mode")

    # ⭐⭐ R1 — THE TWO SCANS ARE DISJOINT BY CONSTRUCTION.
    # ⛔ The real (non-smoke) branch is UNCHANGED, byte for byte: a round read
    # must never adjudicate a smoke archive, which runs at the PRE-LAUNCH commit
    # by design, and `_VOID_*` is quarantine.
    specs = None
    if args.smoke_mode:
        # ⛔ THE MIRROR IMAGE, and it is the load-bearing half: a smoke read
        # adjudicates ONLY `SMOKE_*`. A re-smoke at a root that already holds
        # the round's real cells must never touch them — otherwise a stale
        # round cell's knobs would be reported as a smoke PASS.
        if not args.smoke_cell:
            ap.error("--smoke-mode requires at least one --smoke-cell "
                     f"{SMOKE_CELL_SYNTAX} — without a spec there is nothing to "
                     "adjudicate the smoke archive AGAINST, and the read would "
                     "vacuously exit 0 (the R1 defect)")
        try:
            specs = tuple(parse_smoke_cell(s) for s in args.smoke_cell)
        except ValueError as e:
            ap.error(str(e))
        cells = {p.name: load_cell(p) for p in sorted(args.root.iterdir())
                 if p.is_dir() and (p / "manifest.json").is_file()
                 and p.name.startswith("SMOKE_")}
    else:
        cells = {p.name: load_cell(p) for p in sorted(args.root.iterdir())
                 if p.is_dir() and (p / "manifest.json").is_file()
                 # smoke/quarantine archives are not round cells — they run at
                 # the pre-launch commit by design.
                 and not p.name.startswith(("SMOKE_", "_VOID_"))}
    pins = {}
    if args.pin_local and args.pin_local.is_file():
        pins["local"] = args.pin_local.read_text().strip()
    if args.pin_laptop and args.pin_laptop.is_file():
        pins["laptop"] = args.pin_laptop.read_text().strip()
    v = adjudicate(cells, pins_by_role=pins, smoke_mode=args.smoke_mode,
                   specs=specs)

    if args.smoke_mode:
        # ⛔⛔ THE SMOKE EMITS NO OUTCOME KEY. The emitter whitelist is a WRITE
        # surface; the gate is a READ surface firing on forbidden OUTCOME keys
        # at ANY DEPTH (the Stage-2 `G-SMOKE` ruling).
        #
        # ⚠️ "AT ANY DEPTH" IS THE WHOLE POINT: a gate's `detail` and `why` carry
        # the values that gate READ, and `RECON`'s detail is literally the five
        # outcome statistics under their own names. So a smoke record keeps only
        # `{gate, ok, address}` per gate — plus the RESOLVED KNOB, which is a
        # CONFIG value and is the smoke's whole substantive job.
        def _bare(g):
            return {"gate": g["gate"], "ok": g["ok"], "address": g["address"]}

        def _knob(c):
            d = next((g["detail"] for g in c["gates"]
                      if g["gate"] in ("G-FPU", "G-CPUCT")), None)
            if not isinstance(d, dict):
                return None
            out = {k: d.get(k) for k in ("requested_fpu_reduction",
                                         "requested_c_puct_override",
                                         "shared_c_puct", "frozen")}
            # ⭐ R1(c) — THE CANDIDATE-SIDE-ONLY WITNESS, surfaced for the
            # by-hand review the launcher demands. `G-TWOSIDED`'s detail is the
            # two sides' RESOLVED config: pure CONFIG, no outcome key.
            t = next((g["detail"] for g in c["gates"]
                      if g["gate"] == "G-TWOSIDED"), None)
            if isinstance(t, dict):
                out["resolved_two_sided"] = t.get("resolved")
            return out

        v = {"smoke_mode": True,
             "round_gates": [_bare(g) for g in v["round_gates"]],
             "round_gates_ok": v["round_gates_ok"],
             "golden_gate": v["golden_gate"],
             "cells": {n: {"gates": [_bare(g) for g in c["gates"]],
                           "gates_ok": c["gates_ok"],
                           "failed_gates": c["failed_gates"]}
                       for n, c in v["cells"].items()},
             "resolved_knobs": {n: _knob(c) for n, c in v["cells"].items()},
             "smoke_specs": [{"name": s.name, "knob": s.knob, "value": s.value,
                              "seed_start": s.seed_start,
                              "n_games": s.n_games} for s in (specs or ())],
             "note": "⭐ the smoke's one substantive job beyond liveness: it "
                     "returns the RESOLVED KNOB as the harness actually wrote "
                     "it, on the real argparse, on this box — the PG-D7..D9 "
                     "lesson that a smoke which does not exercise the real CLI "
                     "proves nothing about the launcher."}
        # ⭐⭐ R1(c) — THE EXIT CODE. Zero cells or an empty/rejected knob is a
        # FAILED smoke, and it exits non-zero so run_cells.sh's
        # `|| DIE "the smoke adjudication FAILED"` is REACHABLE.
        v["smoke_problems"] = smoke_problems(v)
        v["smoke_ok"] = not v["smoke_problems"]

    txt = json.dumps(v, indent=2, default=str)
    if args.out:
        args.out.write_text(txt)
        print(f"[analyze_fpu] wrote {args.out}")
    else:
        print(txt)
    if args.smoke_mode and v.get("smoke_problems"):
        print("\n⛔ SMOKE ADJUDICATION FAILED:", file=sys.stderr)
        for pr in v["smoke_problems"]:
            print(f"  {pr}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
