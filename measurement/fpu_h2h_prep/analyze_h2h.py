#!/usr/bin/env python3
"""`analyze_h2h` — THE FPU PRODUCTION-H2H ROUND'S ADJUDICATOR.

⛔ **THE PAIR IS LAW.** [`DESIGN.md`](DESIGN.md) + [`READ_RULE.md`](READ_RULE.md).
If this file disagrees with them, **it is this file that is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 games exist.**

The order of business, which is not negotiable:

  1. **Every §4 gate.** `ABSENT` is `FAIL`, never a skip and never a default.
     Every gate prints WHICH DOCUMENT and WHICH ADDRESS answered — config from
     `manifest.json`, statistics from `summary.json`, which carries no config
     block at all (IS-D1).
     ⭐⭐ `G-TIEARB-SIDES` (config) and `G-TIEARB-FIRE` (play) REPLACE the dose
     ladder's `G-ARB-OFF`. They are its inverse and they use the NEW vocabulary
     in `scripts/classical_search/tiearb_gates.py`, never phasegate's
     `G-TIEARB-ARM`, which treats an armed opponent as a defect and would FAIL
     this healthy cell.
     ⭐⭐ `G-N` and `G-DECKS` are the carried `FPU-A1` fix: the 2% failure bar
     and the 80% common-deck floor ARE the conditions.
  2. **The §5 ladder, on the cell's own realized SE, against zero.**
  3. **The §5.4 verdict** — one cell, so the verdict IS the branch, computed in
     `screen_lib.round_verdict` so a round-gate failure still voids it.
  4. The companions, each flagged ⛔ NEVER A BRANCH INPUT — including the
     pre-stated context rows, which are cross-band AND arbiter-off.

⭐ `--selftest` exercises the library's arithmetic, the dense `(M, SE)` branch
grid, the shipped fixture, the named DEFECT variants (including the five that
only exist because the opponent seat can now be armed), the `FPU-A1` regression
pair at the frozen 400-deck scale, and the GOLDEN-GATE INHERITANCE artefact.

⭐ `--ident-mode` adjudicates the launcher's arb-on-both-sides IDENT legs
(`DESIGN.md` §9.3): `A == A2` (the arb-on path REPRODUCES) and `A != B` (the dose
BINDS with the arbiter live). ⛔ Those two propositions are the ones no banked
certificate covers, and they are why `--smoke` costs six extra games.
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
    `config.opponent.champ_cfg.*` and its BUDGET one level UP under
    `config.opponent.*`; a gate written from the design rather than from a real
    emitted manifest voids every healthy cell."""
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


def gate_tiearb_sides(spec, cell) -> dict:
    """⭐⭐ `G-TIEARB-SIDES` — the config half, via the new vocabulary."""
    return L.tiearb_sides_gate(cell.get("manifest") or {})


def gate_tiearb_fire(spec, cell) -> dict:
    """⭐⭐ `G-TIEARB-FIRE` — the PLAY half. ⛔ Reads `summary.json` (IS-D1:
    statistics live there, config in the manifest)."""
    return L.tiearb_fire_gate(cell.get("summary") or {})


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
    """`G-BUDGET` — k16x1376 = 22016 BOTH SIDES (the 2026-08-30 promoted
    champion). A cell that ran the superseded 11008 grades the dose against a
    stale opponent and voids."""
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
            bad.append(f"{side}: {k} x {s} != {t} — the product does not "
                       "multiply out")
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
    ], "manifest:config.backend.* — ⛔⛔ RUST IS NOT OPTIONAL IN THIS ROUND. "
       "`fpu_reduction` is threaded on both backends, but THE TIE ARBITER IS "
       "RUST-ONLY and the harness refuses `--{cand,opp}-tiearb-enabled` on "
       "python. A python leg could not arm either seat, so it would silently be "
       "the ARBITER-OFF cell this round exists to stop being.")


def gate_wheel(spec, cell) -> dict:
    return _simple("G-WHEEL", cell, [
        (("manifest:carc_rs_build",),
         lambda v: bool(v) and "unavailable" not in str(v), "carc_rs_build"),
        (("manifest:carc_rs_binary_sha",), lambda v: bool(v), "carc_rs_binary_sha"),
        (("manifest:mixed_builds",), lambda v: v is False, "mixed_builds"),
    ], "manifest — ⚠️ carc_rs_version is permanently '0.1.0' and is NOT a "
       "discriminator. ⭐ The wheel's IDENTITY to the inherited golden gate is "
       "asserted LAUNCHER-SIDE (run_cells.sh compares the gate artefact's "
       "wheel.binary_sha to this box's installed binary); DESIGN §9 states the "
       "inheritance argument in full.")


def gate_n(spec, cell) -> dict:
    """⭐⭐ `G-N` — delegated to `screen_lib.n_gate`, which IS the frozen prose
    (the carried `FPU-A1` fix). ⛔ There is no stricter column here."""
    d = _docs(cell)
    n, a1 = L.resolve(d, "summary:n")
    nf, a2 = L.resolve(d, "summary:n_failed", "manifest:n_failed")
    nc = len(L.per_deck_margins(cell.get("records") or []))
    return L.n_gate(spec, n, nf, nc, a1, a2)


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
                   "leaf at the same budget with the same arbiter, so this "
                   "means the two sides are not the agents this design says "
                   "they are"))


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


GATES = (gate_knob, gate_twosided, gate_singlevar, gate_tiearb_sides,
         gate_tiearb_fire, gate_leaf, gate_band, gate_budget, gate_exact,
         gate_rules, gate_backend, gate_wheel, gate_n, gate_sat, gate_host,
         gate_recon)


def adjudicate_cell(spec, cell) -> dict:
    gates = [g(spec, cell) for g in GATES]
    gates.append(L.decks_gate(spec, cell.get("records") or []))
    m, z, n, se, per_deck = L.paired_margin(cell.get("records") or [])
    we = L.winrate_elo(cell.get("records") or [])
    dev, dev_addr = L.resolve(
        _docs(cell), "manifest:config.opponent.production_config_deviations")
    return {
        "cell": spec.name, "role": spec.role, "knob": spec.knob,
        "dose": spec.value, "band": spec.seed_start, "purpose": spec.purpose,
        "gates": gates,
        "gates_ok": all(g["ok"] for g in gates),
        "failed_gates": [g["gate"] for g in gates if not g["ok"]],
        "stats": {"M": m, "z": z, "n_paired": n, "se": se,
                  "UB95": None if (m is None or se is None) else m + 2 * se,
                  "LB95": None if (m is None or se is None) else m - 2 * se,
                  "bar_effect": L.BAR_EFFECT,
                  "bar_note": "⭐ ADOPT requires LB95 >= bar; BOUNDED requires "
                              "UB95 < bar. ⛔ The POINT ESTIMATE clears nothing "
                              "on its own — that is the whole difference from a "
                              "2-sigma-hat bar (owner ruling 2026-08-30)."},
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
            "instrument_2sigma_elo_resolution": L.ELO_RESOLUTION_2SIGMA,
            "resolution_footing": "deck-paired 2σ at 800 games / 400 decks — the "
                                  "SAME footing as ci95_elo_paired (R4)",
            "warning": "⚠️⚠️ THIS IS A RESOLUTION, NOT A BAR. The bar is +1.0 "
                       "pts/deck on the deck-paired MARGIN and no branch reads "
                       "this block. elo may never be quoted bare; a "
                       "disagreement between the margin and the elo is "
                       "DISCLOSED, not arbitrated.",
        },
        # ⚠️ REPORTED, NEVER A GATE. `production_config_deviations` is emitted by
        # the harness against governance/PRODUCTION.yaml. It was STALE on
        # 2026-08-31 (a hard-coded k_dets=8 against the promoted 16) and stamped
        # a FALSE deviation on a healthy cell; the loader now reads the YAML. A
        # gate over it would have voided a healthy cell then and could again on
        # the next promotion, so it is surfaced for the reader and adjudicates
        # nothing. G-BUDGET is the gate, and it reads the manifest directly.
        "opponent_production_deviations": {
            "value": None if dev is L.MISSING else dev,
            "address": dev_addr,
            "note": "⚠️ REPORTED, NEVER A BRANCH INPUT. Empty means 'no "
                    "deviation FOUND', which only means 'matches the champion' "
                    "when the YAML loader actually loaded (eval_fair_puct."
                    "_load_prod_knobs says so on stderr when it did not)."},
        "se_anomaly": L.se_anomaly(se, max(1, n)),
        "_per_deck": per_deck,
    }


# =========================================================================== #
# THE ROUND                                                                    #
# =========================================================================== #

def adjudicate(cells_by_name: dict, pins_by_role: dict | None = None,
               smoke_mode: bool = False, specs=None) -> dict:
    """⚠️ `specs` exists ONLY for the selftest fixture (the same round at a tiny
    deck scale) and for `--smoke-mode`. A real read passes nothing and gets
    `screen_lib.CELLS` — the frozen plan. `selftest()` additionally asserts the
    fixture's specs differ from the frozen ones in `seed_start`/`n_decks` and
    NOTHING else."""
    specs = tuple(specs or L.CELLS)
    per_cell = {}
    for spec in specs:
        if spec.name in cells_by_name:
            per_cell[spec.name] = adjudicate_cell(spec, cells_by_name[spec.name])

    # --- round-level gates -------------------------------------------------
    round_gates = []
    shas = {n: (c.get("manifest") or {}).get("carc_rs_binary_sha")
            for n, c in cells_by_name.items()}
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
         "BOX-LOCAL and is never compared ACROSS boxes."
         if not bad_roles and by_role else
         f"⛔ a box ran more than one wheel: {bad_roles or 'no cells'} — "
         "A FAIL HERE VOIDS THE ROUND")))

    revs = {n: (c.get("manifest") or {}).get("code_rev")
            for n, c in cells_by_name.items()}
    rg = L.cross_box_rev_gate(revs, pins_by_role or {})
    round_gates.append(L.gate("G-REV", rg["ok"], rg,
                              "manifests + the box's PINNED_SRC_REV", rg["why"]))

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
         "⛔ BLIND_COMMIT absent, malformed, or disagreeing — ABSENT is FAIL; a "
         "read that was not blind is not a read")))

    round_ok = all(g["ok"] for g in round_gates)

    branches = {}
    for name, c in per_cell.items():
        st = c["stats"]
        branches[name] = L.branch_for_cell(
            st["M"], st["se"], st["z"], gates_ok=(c["gates_ok"] and round_ok))
        c["branch"] = branches[name]
        c["riders"] = list(L.RIDERS_ALWAYS) + list(
            L.RIDERS_H_ADOPT if branches[name] == "H-ADOPT" else
            L.RIDERS_H_BOUNDED if branches[name] == "H-BOUNDED" else
            L.RIDERS_H_NEGATIVE if branches[name] == "H-NEGATIVE" else
            L.RIDERS_H_UNRESOLVED if branches[name] == "H-UNRESOLVED" else ())

    verdict = L.round_verdict(branches, round_gates_ok=round_ok,
                              expected_cells=[s.name for s in specs])

    out = {
        "round": "fpu_h2h (ONE cell, ONE band — step 2 of the adoption chain)",
        "pair": ["measurement/fpu_h2h_prep/DESIGN.md",
                 "measurement/fpu_h2h_prep/READ_RULE.md"],
        "smoke_mode": smoke_mode,
        "budget": {"k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
                   "total_sims": L.TOTAL_SIMS,
                   "note": "the 2026-08-30 promoted desktop champion, BOTH sides"},
        "deployed_tiearb_both_seats": dict(L.DEPLOYED_TIEARB),
        "bars": {"BAR_EFFECT": L.BAR_EFFECT,
                 "adopt": "LB95(M) >= +%.3f pts/deck" % L.BAR_EFFECT,
                 "bounded": "UB95(M) < +%.3f pts/deck" % L.BAR_EFFECT,
                 "provenance": "⭐ AN EFFECT SIZE, NOT 2 sigma-hat (owner ruling "
                               "2026-08-30) — and the CONFIRMATION bar, "
                               "deliberately below the ladder's +1.5 SCREEN bar. "
                               "DESIGN §3 derives it from the two production "
                               "folds this program has accepted (+1.229 and "
                               "+1.7167 pts). READ_RULE §8 states what it costs."},
        "round_gates": round_gates,
        "round_gates_ok": round_ok,
        "cells": per_cell,
        "branches": branches,
        "verdict": verdict,
        "golden_gate_inheritance": golden_gate_status(),
        "riders": list(L.RIDERS_ALWAYS),
        "adoption_chain": list(L.ADOPTION_CHAIN),
    }
    if verdict["verdict"] == "H-VOID-INSTRUMENT":
        out["void_banner"] = (
            "⛔ H-VOID-INSTRUMENT — THE ROUND DISCHARGES NOTHING. The cell's "
            "statistics print as a COMPANION TABLE only, under this banner, and "
            "no reading of any kind is taken from them. ⛔ A voided cell is NOT "
            "a bound: neither H-ADOPT nor H-BOUNDED may be declared over it, "
            "and step 2 of the adoption chain remains UNPRICED.")

    comp: dict = {
        "_warning": "⛔ COMPANIONS — NEVER A BRANCH INPUT.",
        "context_rows": L.CONTEXT_ROWS,
        "context_warning": L.CONTEXT_WARNING,
        "ladder_verdict": L.LADDER_VERDICT,
        "production_fold_precedents": L.PRODUCTION_FOLD_PRECEDENTS,
        "production_fold_note":
            "⭐ These are what the bar is DERIVED FROM (DESIGN §3), and they are "
            "a DESIGN act spent before any number of this round exists. ⛔ They "
            "are not comparanda: both are cross-band and neither measures this "
            "knob.",
        "sizing_siblings": L.REALIZED_SIGMA_D_SIBLINGS,
        "sizing_siblings_warning":
            "⛔ ALL SEVEN ARE ARBITER-OFF CELLS. They corroborate sigma_D = "
            "13.81 for the arb-off agent pair; this round's pair is arb-ON on "
            "both seats and its dispersion could be wider. That costs POWER, "
            "never VALIDITY — every branch is adjudicated at the cell's OWN "
            "realized SE (READ_RULE §1). se_anomaly REPORTS the ratio.",
        "read_distribution_at_launch_time_model": {
            "delta=0 (true null)": L.read_distribution(0.0),
            "delta=+1.0 (exactly at the bar)": L.read_distribution(L.BAR_EFFECT),
            "delta=+1.835 (the ladder's largest point estimate)":
                L.read_distribution(1.835),
            "delta=+2.951 (a repeat of the incumbent)":
                L.read_distribution(2.95125),
            "n_decks_for_adopt_power(+2.951, 0.80)":
                L.n_decks_for_adopt_power(2.95125, 0.80),
            "n_decks_for_adopt_power(+1.835, 0.80)":
                L.n_decks_for_adopt_power(1.835, 0.80),
            "n_decks_for_bounded_power(0.80)": L.n_decks_for_bounded_power(0.80),
            "note": "⛔ MODELLED at se_model(400)=0.6905, PRE-REGISTERED in "
                    "READ_RULE §8 before game 1. Every BRANCH above is "
                    "adjudicated at the cell's OWN REALIZED SE, never at this.",
        },
    }
    out["companions"] = comp
    return out


# =========================================================================== #
# ⭐⭐ THE SMOKE'S OWN SPECS — R1, CARRIED FROM THE PARENT ROUNDS              #
# =========================================================================== #
# ⛔⛔ THE DEFECT THIS CLOSES. `--smoke-mode` used to adjudicate ZERO cells, by
# TWO independent mechanisms, and still exit 0 — so `run_cells.sh`'s
# `|| DIE "the smoke adjudication FAILED"` was UNREACHABLE and the smoke's one
# substantive job (read the RESOLVED CONFIG back out of the EMITTED manifest)
# silently did nothing. The identical defect is REALIZED in phasegate's banked
# `SMOKE_local.json` (`"cells": {}`).

SMOKE_CELL_SYNTAX = "NAME=knob:value:seed_start:n_games:role"


def parse_smoke_cell(text: str) -> "L.CellSpec":
    """`SMOKE_H2H=fpu_reduction:0.2:168999999500:8:laptop` -> a `CellSpec`.

    ⛔ The NAME must start with `SMOKE_`: only smoke archives are adjudicable in
    `--smoke-mode`, and admitting any other name would let a re-smoke at a root
    that already holds the real cell adjudicate it under smoke rules.
    ⛔ The knob and value are the LAUNCHER'S REQUEST. They are not trusted — they
    become `G-FPU`'s frozen expectation, which is then checked against
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
        raise ValueError(f"--smoke-cell {text!r}: role must be local|laptop")
    if not name.startswith("SMOKE_"):
        raise ValueError(f"--smoke-cell {text!r}: the name must start with "
                         "'SMOKE_' — only smoke archives are adjudicable in "
                         "--smoke-mode, and the round's cell must never be")
    if knob != "fpu_reduction":
        raise ValueError(f"--smoke-cell {text!r}: unknown knob {knob!r} — this "
                         "round owns fpu_reduction and the smoke must exercise "
                         "the code path the cell will run")
    n = int(n_games)
    if n < 2 or n % 2:
        raise ValueError(f"--smoke-cell {text!r}: n_games {n} is not an even "
                         "count of deck-paired games")
    return L.CellSpec(name=name, role=role, knob=knob, value=float(value),
                      seed_start=int(seed_start), n_decks=n // 2,
                      purpose="⭐ THE §9.2 SMOKE — the THROWAWAY sub-range, "
                              "PRODUCTION knobs (arbiter ARMED on both seats), "
                              "only the game count reduced. ⛔ Buys no deck of "
                              "the round and claims no band.")


#: The gates the smoke EXISTS to run. ⛔ A smoke archive legitimately fails gates
#: about the ROUND (`G-BLIND` — no blind commit; `G-REV` — it runs at the
#: PRE-LAUNCH commit by design; `G-N` — 8 games, not 800), so "all gates ok" is
#: the wrong bar and would make the smoke unusable. These are the ones whose
#: failure means the LAUNCHER is wrong:
#:   * `G-FPU`           — the dose was REQUESTED and the emitted manifest says so;
#:   * `G-TWOSIDED`      — it BOUND, and bound on the CANDIDATE side ONLY;
#:   * ⭐⭐ `G-TIEARB-SIDES` — BOTH SEATS carry the deployed arbiter dict. ⛔ THIS
#:     IS THE NEW ONE AND IT IS THE WHOLE REASON THE SMOKE IS RE-RUN FOR THIS
#:     ROUND: until 2026-08-31 the opponent seat could not be armed at all, and a
#:     launcher that silently armed only the candidate would produce a CONFOUNDED
#:     arb+fpu cell claiming a single variable — with every other gate passing.
#:   * ⭐⭐ `G-TIEARB-FIRE` — and it FIRED on both seats, in play.
SMOKE_REQUIRED_GATES = ("G-FPU", "G-TWOSIDED", "G-TIEARB-SIDES",
                        "G-TIEARB-FIRE")


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
                     "job is to return the config AS THE HARNESS WROTE IT, read "
                     "off the emitted manifest.json. Nothing was read.")
    for name in cells:
        k = knobs.get(name)
        if not k:
            probs.append(f"⛔ {name}: no resolved config could be read from its "
                         "manifest.json — ABSENT is FAIL")
            continue
        if k.get("requested_fpu_reduction") is None:
            probs.append(f"⛔ {name}: the emitted manifest requested NO "
                         "fpu_reduction — the launcher did not put the dose on "
                         "the wire")
        ta = k.get("tiearb_sides") or {}
        for side in ("candidate", "opponent"):
            spec_ = (ta.get(side) or {}).get("spec")
            if not spec_ or spec_.get("enabled") is not True:
                probs.append(
                    f"⛔⛔ {name}: the emitted manifest does NOT arm the "
                    f"{side.upper()} seat's tie arbiter. A cell launched over "
                    "this is a CONFOUNDED arb+fpu cell claiming one variable — "
                    "the exact failure the 2026-08-31 opponent-side plumbing "
                    "was funded to end, and every other gate passes it.")
    for name, c in cells.items():
        by_id = {g["gate"]: g["ok"] for g in c.get("gates", [])}
        ran = [g for g in SMOKE_REQUIRED_GATES if g in by_id]
        if not ran:
            probs.append(f"⛔ {name}: none of {SMOKE_REQUIRED_GATES} executed")
        for gid in ran:
            if not by_id[gid]:
                probs.append(
                    f"⛔ {name}: {gid} FAILED. " + {
                        "G-TWOSIDED":
                            "The dose did not BIND on the candidate, or it "
                            "bound on the OPPONENT TOO.",
                        "G-FPU":
                            "The emitted manifest does not carry the dose this "
                            "box was told to smoke.",
                        "G-TIEARB-SIDES":
                            "The two seats do not both carry the DEPLOYED "
                            "arbiter dict (B=64, J=4, argmax, "
                            "tiearb2-deploy-v1, eps 0.0, phase_gate all). A "
                            "MISSING phase_gate means a stale wheel whose "
                            "arbiter ran UNGATED.",
                        "G-TIEARB-FIRE":
                            "A seat was armed and never arbitrated. Armed-and-"
                            "silent is a ONE-SIDED cell wearing a symmetric "
                            "cell's name.",
                    }[gid])
    return probs


# =========================================================================== #
# ⭐⭐ THE IDENT LEGS — DESIGN §9.3                                            #
# =========================================================================== #
# ⛔⛔ WHAT NO BANKED CERTIFICATE COVERS, STATED AS TWO PROPOSITIONS:
#
#   IDENT-REPRODUCES   two runs of the SAME arb-on-both-seats configuration on
#                      the SAME seeds produce byte-identical game outcomes. The
#                      arbiter is a STOCHASTIC root hook driven by a CRN salt;
#                      if it does not reproduce across processes, the cell's
#                      numbers are not reproducible either and no gate downstream
#                      would notice.
#   POSITIVE-ARB-ON    dropping the dose, at the same seeds with the arbiter
#                      still live on both seats, CHANGES PLAY. ⛔ THIS IS THE
#                      ONE THE INHERITED GATE CANNOT GIVE: FPU_BITEXACT_LADDER's
#                      positive controls are at 0.05/0.1/0.15/0.3 (not 0.2) and
#                      all of them are ARBITER-OFF. A build in which the arbiter
#                      overrode the dose's effect at the root would pass every
#                      inherited check and flatten this cell into
#                      champion-vs-champion.
#
# ⚠️ THE LEGS RUN AT THE GOLDEN GATE'S TINY BUDGET (k2 x 96), deliberately. The
# proposition is about a CODE PATH, not a budget, and `fpu_reduction` is read on
# EVERY unvisited-child PUCT score. ⛔ NO NUMBER IN THEM IS A STRENGTH
# MEASUREMENT and none may be quoted as one.

#: The per-game fields an IDENT comparison reads. ⚠️ `elapsed_s` and the
#: `*_secs` fields are DELIBERATELY EXCLUDED: they are wall-clock and differ
#: between two identical runs by construction. A comparison that included them
#: would fail every healthy leg.
IDENT_FIELDS = ("seed", "a_seat", "diff", "score_p0", "score_p1",
                "won_by_champ", "drew", "moves", "deck_hash")


def _ident_fingerprint(cell: dict) -> dict:
    out = {}
    for r in cell.get("records") or []:
        if not isinstance(r, dict) or "seed" not in r or "a_seat" not in r:
            continue
        out[f"{r['seed']}_a{r['a_seat']}"] = {k: r.get(k) for k in IDENT_FIELDS}
    return out


def adjudicate_ident(a: dict, a2: dict, b: dict) -> dict:
    """`A == A2` and `A != B`. ⛔ Both propositions are HARD; either one failing
    is a launch-blocking finding, not a warning."""
    fa, fa2, fb = (_ident_fingerprint(a), _ident_fingerprint(a2),
                   _ident_fingerprint(b))
    probs = []
    if not fa:
        probs.append("⛔⛔ leg A produced NO parseable records — ABSENT is FAIL")
    if not fa2:
        probs.append("⛔⛔ leg A2 produced NO parseable records — ABSENT is FAIL")
    if not fb:
        probs.append("⛔⛔ leg B produced NO parseable records — ABSENT is FAIL")

    same_keys = sorted(set(fa) & set(fa2))
    ident_diffs = [k for k in same_keys if fa[k] != fa2[k]]
    if set(fa) != set(fa2):
        probs.append(f"⛔ A and A2 played different games: A has {sorted(fa)}, "
                     f"A2 has {sorted(fa2)}")
    if ident_diffs:
        probs.append(
            "⛔⛔ IDENT-REPRODUCES FAILED: the SAME arb-on-both-seats "
            f"configuration on the SAME seeds produced DIFFERENT outcomes at "
            f"{ident_diffs}. The tie arbiter is a stochastic root hook driven by "
            "a CRN salt; if it does not reproduce across processes, this cell's "
            "numbers are not reproducible and NO downstream gate would notice. "
            "⛔ DO NOT LAUNCH.")

    b_keys = sorted(set(fa) & set(fb))
    pos_diffs = [k for k in b_keys if fa[k] != fb[k]]
    if fa and fb and not pos_diffs:
        probs.append(
            "⛔⛔ POSITIVE-ARB-ON FAILED: dropping `--cand-fpu-reduction` "
            "changed NOTHING on the same seeds with the arbiter live on both "
            "seats. Either the dose does not bind through the arbiter path, or "
            "the arbiter is overriding it at the root. ⛔ THE INHERITED GOLDEN "
            "GATE CANNOT SEE THIS: its positive controls are at 0.05/0.1/0.15/"
            "0.3 and ALL of them are ARBITER-OFF. A cell launched over this "
            "would be champion-vs-champion with every gate passing. "
            "⚠️ It is also the ONE leg with a false-alarm mode: at "
            f"{len(b_keys)} game(s) two shallow searches CAN coincide. Re-run "
            "with more IDENT_GAMES before concluding the wiring is broken — but "
            "DO NOT LAUNCH on this result.")

    def _arb(cell, label):
        m = (cell.get("manifest") or {})
        s = (cell.get("summary") or {})
        return {"sides_gate": L.tiearb_sides_gate(m)["ok"],
                "fire_gate": L.tiearb_fire_gate(s)["ok"],
                "fired": {"candidate": s.get("tiearb_fired_plies_total"),
                          "opponent": s.get("opp_tiearb_fired_plies_total")},
                "leg": label}
    arb = [_arb(a, "A"), _arb(a2, "A2"), _arb(b, "B")]
    for row in arb:
        if not row["sides_gate"]:
            probs.append(f"⛔ leg {row['leg']}: the arbiter is not armed at the "
                         "deployed spec on BOTH seats — the IDENT legs exist to "
                         "exercise the arb-on path and this one did not")
        if not row["fire_gate"]:
            probs.append(f"⛔ leg {row['leg']}: a seat never arbitrated "
                         f"(fired {row['fired']}). ⚠️ At the IDENT legs' tiny "
                         "budget and game count a seat CAN legitimately see no "
                         "exact tie — if that is the finding, raise IDENT_GAMES "
                         "rather than launching over an unexercised path.")
    return {
        "ident_mode": True,
        "propositions": {
            "IDENT-REPRODUCES": {"ok": not ident_diffs and bool(fa) and bool(fa2),
                                 "compared": len(same_keys),
                                 "differing": ident_diffs},
            "POSITIVE-ARB-ON": {"ok": bool(pos_diffs), "compared": len(b_keys),
                                "differing": pos_diffs},
        },
        "fields_compared": list(IDENT_FIELDS),
        "fields_excluded": ["elapsed_s", "*_secs (wall clock — differs between "
                            "two identical runs by construction)"],
        "arbiter_per_leg": arb,
        "budget_note": "⚠️ THE LEGS RUN AT k2 x 96, the golden gate's budget. "
                       "⛔ NO NUMBER IN THEM IS A STRENGTH MEASUREMENT.",
        "ident_problems": probs,
        "ident_ok": not probs,
    }


def golden_gate_status() -> dict:
    """⭐⭐ THE GOLDEN-GATE INHERITANCE, SURFACED IN EVERY READ-OUT.

    ⛔ THIS ROUND DOES NOT BUILD A NEW GOLDEN GATE, AND `DESIGN.md` §9 STATES THE
    ARGUMENT RATHER THAN ASSUMING IT. In short:

      * `../fpu_ladder_prep/FPU_BITEXACT_LADDER.json` is `PASS` on wheel
        `a9bb2311ab9a635d`, ran ~14 h ago, and proves `fpu=None` is the champion
        BIT-FOR-BIT on that wheel plus a POSITIVE control at each of
        `0.05/0.1/0.15/0.3` plus `DOSE-DISTINCT`. `run_cells.sh` re-asserts the
        artefact's `wheel.binary_sha` against THIS BOX's installed binary, so the
        inheritance is MECHANICALLY CHECKED and not asserted.
      * The ARBITER path rode the b64-era certificates — `tiearb_widening_
        20260817/b64_cell/GATE_NEST.json` (`G-NEST`: the CRN cap draw, world
        seeds, playout seeds and world bytes are identical at B16 ⊂ B64) — plus
        this morning's wiring smoke, which drove the real argparse and read the
        resolved arbiter dict back out of an EMITTED manifest.
      * ⛔⛔ **TWO GAPS REMAIN, AND THEY ARE NAMED:** (1) no certificate has ever
        exercised `fpu` AND the arbiter TOGETHER, and (2) `0.2` is not one of the
        ladder gate's four control doses (its own control lives in the parent
        round's `FPU_BITEXACT.json`, on a wheel that no longer exists).
      * ⭐ THE GAPS ARE PAID BY `--smoke`'s IDENT LEGS (`--ident-mode`), which
        are `POSITIVE-0.2-WITH-THE-ARBITER-LIVE` and a cross-process
        reproducibility check, at the golden gate's own budget.
    """
    p = HERE.parent / "fpu_ladder_prep" / "FPU_BITEXACT_LADDER.json"
    common = {
        "inherited_from": str(p),
        "argument": golden_gate_status.__doc__,
        "gaps_paid_by": "the launcher's --smoke IDENT legs, adjudicated by "
                        "`analyze_h2h.py --ident-mode` into IDENT_<role>.json",
        "arbiter_prior_certificates": [
            "measurement/tiearb_widening_20260817/b64_cell/GATE_NEST.json "
            "(G-NEST, 2026-08-20) — CRN nesting B16 ⊂ B64, PRE-a9bb2311 wheel, "
            "CANDIDATE seat only",
            "/mnt/c/carc-shared/fpu_ladder/SMOKE_ARBON_H2H (2026-08-31 wiring "
            "smoke, n=4 THROWAWAY) — the resolved arbiter dict incl. "
            "phase_gate read back off an EMITTED manifest, CANDIDATE seat only "
            "(the opponent seat could not be armed until that afternoon)",
        ],
    }
    if not p.is_file():
        return {**common, "verdict": "ABSENT", "ok": False,
                "why": "⛔⛔ FPU_BITEXACT_LADDER.json ABSENT ON THIS BOX — "
                       "ABSENT is FAIL. ⚠️ THE ARTEFACT IS BOX-LOCAL AND "
                       "GITIGNORED (`carc_rs_binary_sha` differs between boxes "
                       "compiling identical source), so a box that ran the dose "
                       "ladder HAS one and a box that did not MUST run "
                       "`measurement/fpu_ladder_prep/golden_gate/"
                       "run_golden_gate.sh` before this round. `run_cells.sh` "
                       "REFUSES a real cell without it."}
    v = json.loads(p.read_text())
    return {**common, "verdict": v.get("verdict"),
            "ok": v.get("verdict") == "PASS",
            "failed": v.get("failed"), "wheel": v.get("wheel"),
            "checks": {c["check"]: c["ok"] for c in v.get("checks", [])},
            "why": "⭐ INHERITED, WITH THE WHEEL RE-ASSERTED AT LAUNCH. ⛔ The "
                   "two named gaps (fpu x arbiter together; a 0.2 control on "
                   "this wheel) are NOT covered by it and are paid by the IDENT "
                   "legs."}


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


SYNTH_PIN = "f" * 40
SYNTH_BLIND = "e" * 40


def _synthetic_round(template_manifest: dict, template_summary: dict,
                     failed_decks: int = 0) -> dict:
    """⭐⭐ A synthetic cell AT THE FROZEN SCALE (400 decks), built from a REAL
    EMITTED manifest shape.

    ⛔⛔ **THIS EXISTS BECAUSE THE 2% BAR IS NOT TESTABLE AT FIXTURE SCALE.** The
    shipped fixture is 12 decks and `int(0.02 * 12) = 0`, so no whole number of
    failed decks lands strictly BELOW the bar there. The `FPU-A1` regression —
    *a sub-2% failure is REPORTED and the cell still READS* — is the single most
    important property of this instrument, and a test that could not express it
    would be a test of nothing. At the frozen 800-game cell, `15/800 = 1.875%` is
    below the bar and `16/800 = 2.000%` is at it.
    """
    import math as _m
    import random as _r
    rng = _r.Random(7)
    cells = {}
    spec = L.CELLS[0]
    man = json.loads(json.dumps(template_manifest))
    man["host"] = "laptop-wsl"
    man["code_rev"] = SYNTH_PIN[:9]
    man["BLIND_COMMIT"] = SYNTH_BLIND
    man["carc_rs_binary_sha"] = "2222222222222222"
    man["n_failed"] = failed_decks
    cfg = man["config"]
    cfg["band_seed_start"] = spec.seed_start
    cfg["seed_start"] = spec.seed_start
    cfg["n_decks"] = spec.n_decks
    cfg["n"] = spec.n_games
    cfg["cand_search"]["fpu_reduction"] = spec.value
    cfg["champion"]["fpu_reduction"] = spec.value
    recs = []
    for i in range(spec.n_decks):
        seed = spec.seed_start + i
        d = 0.2 + rng.gauss(0.0, 13.8)
        spread = rng.gauss(0.0, 30.0)
        seats = (0,) if i < failed_decks else (0, 1)
        for a in seats:
            diff = d + (spread if a == 0 else -spread)
            recs.append({"seed": seed, "a_seat": a, "diff": diff,
                         "won_by_champ": diff > 0, "drew": False})
    per = L.per_deck_margins(recs)
    ds = list(per.values())
    mean = _m.fsum(ds) / len(ds)
    var = _m.fsum((x - mean) ** 2 for x in ds) / (len(ds) - 1)
    se = _m.sqrt(var / len(ds))
    w = sum(1 for r in recs if r["won_by_champ"])
    wr = w / len(recs)
    summ = json.loads(json.dumps(template_summary))
    summ.update({"n": len(recs), "n_failed": failed_decks, "n_paired": len(ds),
                 "paired_mean_margin": mean,
                 "paired_z": mean / se if se else float("nan"),
                 "winrate": wr,
                 "elo": (400.0 * _m.log10(wr / (1 - wr)) if 0 < wr < 1
                         else 800.0)})
    cells[spec.name] = {"root": f"<synthetic:{spec.name}>", "manifest": man,
                        "summary": summ, "records": recs}
    return cells


#: ⭐ THE NAMED DEFECTS — one per gate whose failure would otherwise never be
#: observed. Each must (a) fire its own gate and (b) drive the cell to a VOID.
#: ⛔⛔ THE FIRST SEVEN ARE THIS DESIGN'S MOST DANGEROUS FAILURE MODE IN ITS
#: SEVEN DISGUISES: a cell that is secretly champion-vs-champion, or secretly
#: two-variable, moves no leaf hash, sits inside `G-SAT`'s rail, and reads as a
#: clean credible number.
FIXTURE_DEFECTS = (
    # --- the dose --------------------------------------------------------- #
    ("hardcoded_none_defect_dose_never_bound",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"],
                    "config.champion.fpu_reduction", None),
     "G-TWOSIDED"),
    ("harness_predates_the_round_cand_search_absent",
     lambda c: _del(c["CELL_H2H_FPU02"]["manifest"], "config.cand_search"),
     "G-FPU"),
    ("wrong_dose_on_the_wire",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"],
                    "config.cand_search.fpu_reduction", 0.15),
     "G-FPU"),
    ("a_stray_cand_c_puct_override",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"],
                    "config.cand_search.c_puct", 1.0),
     "G-FPU"),
    ("opponent_carries_the_dose_too",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"],
                    "config.opponent.champ_cfg.fpu_reduction", 0.2),
     "G-TWOSIDED"),
    # --- ⭐⭐ THE ARBITER, ON BOTH SEATS — THE NEW FAMILY ------------------ #
    # ⛔⛔ THE HEADLINE ONE. Before 2026-08-31 this was not a defect but the ONLY
    # expressible shape, and a prereg claiming "arb on both sides" over it would
    # have shipped a CONFOUNDED arb+fpu cell claiming a single variable.
    ("opponent_seat_never_armed_the_confounded_cell",
     lambda c: (_del(c["CELL_H2H_FPU02"]["manifest"], "opp_tiearb"),
                _del(c["CELL_H2H_FPU02"]["manifest"], "config.opp_tiearb"),
                _del(c["CELL_H2H_FPU02"]["manifest"], "config.opponent.tiearb")),
     "G-TIEARB-SIDES"),
    ("opponent_seat_present_but_disabled",
     lambda c: (_set(c["CELL_H2H_FPU02"]["manifest"], "opp_tiearb.enabled", False),
                _set(c["CELL_H2H_FPU02"]["manifest"],
                     "config.opp_tiearb.enabled", False),
                _set(c["CELL_H2H_FPU02"]["manifest"],
                     "config.opponent.tiearb.enabled", False)),
     "G-TIEARB-SIDES"),
    ("the_two_seats_ran_different_B",
     lambda c: (_set(c["CELL_H2H_FPU02"]["manifest"], "opp_tiearb.B", 16),
                _set(c["CELL_H2H_FPU02"]["manifest"], "config.opp_tiearb.B", 16),
                _set(c["CELL_H2H_FPU02"]["manifest"],
                     "config.opponent.tiearb.B", 16)),
     "G-TIEARB-SIDES"),
    # ⛔ A STALE WHEEL WHOSE ARBITER RAN UNGATED. `phase_gate` ABSENT is FAIL and
    # never a default — a silently-defaulted "all" makes a gated cell BE the
    # ungated cell, which is phasegate's entire lesson.
    ("phase_gate_key_missing_stale_wheel",
     lambda c: (_del(c["CELL_H2H_FPU02"]["manifest"], "opp_tiearb.phase_gate"),
                _del(c["CELL_H2H_FPU02"]["manifest"],
                     "config.opp_tiearb.phase_gate"),
                _del(c["CELL_H2H_FPU02"]["manifest"],
                     "config.opponent.tiearb.phase_gate")),
     "G-TIEARB-SIDES"),
    ("candidate_seat_disarmed",
     lambda c: (_set(c["CELL_H2H_FPU02"]["manifest"], "cand_tiearb.enabled", False),
                _set(c["CELL_H2H_FPU02"]["manifest"],
                     "config.cand_tiearb.enabled", False)),
     "G-TIEARB-SIDES"),
    # ⛔⛔ AND THE PLAY-DERIVED HALF: armed in config, dead in play.
    ("opponent_seat_armed_but_never_arbitrated",
     lambda c: c["CELL_H2H_FPU02"]["summary"].update(
         {"opp_tiearb_games": 0, "opp_tiearb_fired_plies_total": 0}),
     "G-TIEARB-FIRE"),
    ("candidate_seat_armed_but_never_fired",
     lambda c: c["CELL_H2H_FPU02"]["summary"].update(
         {"tiearb_fired_plies_total": 0}),
     "G-TIEARB-FIRE"),
    ("a_seat_reported_a_partial_argmax",
     lambda c: c["CELL_H2H_FPU02"]["summary"].update(
         {"opp_tiearb_partial_argmax_total": 3}),
     "G-TIEARB-FIRE"),
    ("the_cell_mixed_two_arbiter_phase_gates",
     lambda c: c["CELL_H2H_FPU02"]["summary"].update(
         {"tiearb_phase_gates": ["all", "early"]}),
     "G-TIEARB-FIRE"),
    # --- the rest of the instrument --------------------------------------- #
    ("a_second_variable_moved",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"], "config.champion.tau_p", 8.0),
     "G-SINGLEVAR"),
    ("stale_budget_11008",
     lambda c: (_set(c["CELL_H2H_FPU02"]["manifest"], "config.champion.k_dets", 8),
                _set(c["CELL_H2H_FPU02"]["manifest"],
                     "config.champion.total_sims", 11008)),
     "G-BUDGET"),
    ("leaf_hashes_differ_across_the_two_sides",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"], "config.opp_leaf_hash",
                    "deadbeef"),
     "G-LEAF"),
    ("mixed_rev_round",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"], "code_rev", "cccccccc"),
     "G-REV"),
    ("recon_disagrees_with_the_summary",
     lambda c: _set(c["CELL_H2H_FPU02"]["summary"], "paired_mean_margin", 99.0),
     "RECON"),
    ("cell_ran_on_the_wrong_box",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"], "host", "Doctor"),
     "G-HOST"),
    ("seed_outside_the_cells_own_band",
     lambda c: c["CELL_H2H_FPU02"]["records"].append(
         {"seed": 999999999999, "a_seat": 0, "diff": 1.0,
          "won_by_champ": True, "drew": False}),
     "G-DECKS"),
    # ⚠️ AT FIXTURE SCALE one lost seating is 1/24 = 4.2%, ABOVE the 2% bar, so
    # it MUST void. The sub-bar direction is tested at the FROZEN 400-deck scale
    # by `_synthetic_round`.
    ("a_deck_was_played_at_one_seat_only_ABOVE_the_bar",
     lambda c: c["CELL_H2H_FPU02"]["records"].pop(),
     "G-DECKS"),
    ("games_vanished_without_a_failure_record",
     lambda c: c["CELL_H2H_FPU02"]["summary"].__setitem__("n", 15),
     "G-N"),
    ("python_backend_could_not_have_armed_either_seat",
     lambda c: _set(c["CELL_H2H_FPU02"]["manifest"], "config.backend.name",
                    "python"),
     "G-BACKEND"),
)


def selftest() -> int:
    problems = list(L.sanity_check())
    grid = L.branch_grid(step=0.02)
    if not grid["all_reachable"]:
        problems.append(f"branch grid: only {grid['reachable']} reachable")

    gg = golden_gate_status()
    gg_note = (
        f"⚠️ the INHERITED GOLDEN GATE reads {gg['verdict']} on this box — "
        "REPORTED, not fatal to the selftest, because the instrument must be "
        "testable on a box that has not run it. ⛔ It IS fatal to the LAUNCHER: "
        "run_cells.sh refuses a real cell unless the artefact reads PASS AND "
        "its wheel.binary_sha equals this box's installed binary."
        if not gg["ok"] else
        "⭐ the INHERITED GOLDEN GATE reads PASS on this box "
        f"(wheel {(gg.get('wheel') or {}).get('binary_sha')}). ⛔ Its two named "
        "gaps — fpu x arbiter together, and a 0.2 control on this wheel — are "
        "paid by the --smoke IDENT legs, not by it.")

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
    if set(v["branches"].values()) != {"H-VOID-INSTRUMENT"}:
        problems.append(f"an all-empty round read {v['branches']}, not void")
    if v["verdict"]["verdict"] != "H-VOID-INSTRUMENT":
        problems.append("an all-empty round did not read H-VOID-INSTRUMENT")

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
        v = adjudicate(cells, pins_by_role={"laptop": pin}, specs=specs)
        report["healthy"] = {
            "branches": v["branches"],
            "verdict": v["verdict"]["verdict"],
            "failed_round_gates": [g["gate"] for g in v["round_gates"]
                                   if not g["ok"]],
            "failed_cell_gates": {n: c["failed_gates"]
                                  for n, c in v["cells"].items()
                                  if c["failed_gates"]},
        }
        if report["healthy"]["failed_round_gates"]:
            problems.append("the HEALTHY fixture failed round gate(s): "
                            f"{report['healthy']['failed_round_gates']}")
        if report["healthy"]["failed_cell_gates"]:
            problems.append("the HEALTHY fixture failed cell gate(s): "
                            f"{report['healthy']['failed_cell_gates']}")
        want = {"CELL_H2H_FPU02": "H-ADOPT"}
        if v["branches"] != want:
            problems.append(f"the HEALTHY fixture read {v['branches']}, want {want}")

        # ------------------------------------------------------------- #
        # ⭐⭐ THE FPU-A1 REGRESSION PAIR — AT THE FROZEN 400-DECK SCALE   #
        # ------------------------------------------------------------- #
        template = cells["CELL_H2H_FPU02"]["manifest"]
        t_summ = cells["CELL_H2H_FPU02"]["summary"]
        synth_pins = {"laptop": SYNTH_PIN}
        clean = adjudicate(_synthetic_round(template, t_summ, 0),
                           pins_by_role=synth_pins)
        report["synthetic_clean_round"] = {
            "branches": clean["branches"],
            "verdict": clean["verdict"]["verdict"],
            "failed": {n: c["failed_gates"] for n, c in clean["cells"].items()
                       if c["failed_gates"]}}
        if any(c["failed_gates"] for c in clean["cells"].values()):
            problems.append("the CLEAN synthetic 400-deck cell failed gates: "
                            f"{report['synthetic_clean_round']['failed']} — the "
                            "FPU-A1 cases below would be testing the "
                            "synthesizer, not the bar")
        n_sub = int(L.FAILURE_RATE_VOID * 800) - 1        # 15 games = 1.875%
        sub = adjudicate(_synthetic_round(template, t_summ, n_sub),
                         pins_by_role=synth_pins)
        report["fpu_a1_sub_bar_failure_is_REPORTED_not_void"] = {
            "failed_games": n_sub, "rate_of_games": n_sub / 800.0,
            "failed_gates": {n: c["failed_gates"] for n, c in sub["cells"].items()},
            "branches": sub["branches"],
            "verdict": sub["verdict"]["verdict"]}
        for n, c in sub["cells"].items():
            if c["failed_gates"]:
                problems.append(
                    "⛔⛔ FPU-A1 REGRESSION: a failure rate STRICTLY BELOW the "
                    f"2% bar ({n_sub}/800 games = {n_sub / 8:.3f}%) voided {n} "
                    f"on {c['failed_gates']}. The frozen prose says such a rate "
                    "is REPORTED, never voiding.")
            if c["branch"] == "H-VOID-INSTRUMENT":
                problems.append(f"FPU-A1 REGRESSION: sub-bar cell {n} voided")
        gn = next(g for g in sub["cells"]["CELL_H2H_FPU02"]["gates"]
                  if g["gate"] == "G-N")
        if "REPORTED" not in (gn.get("why") or ""):
            problems.append("the sub-bar failure passed G-N SILENTLY — the "
                            "b32v64 precedent requires it be REPORTED")
        gd = next(g for g in sub["cells"]["CELL_H2H_FPU02"]["gates"]
                  if g["gate"] == "G-DECKS")
        if "ONE SEAT ONLY" not in (gd.get("why") or ""):
            problems.append("G-DECKS did not report the one-seat-only decks")
        n_over = int(L.FAILURE_RATE_VOID * 800)           # 16 games = 2.00%
        over = adjudicate(_synthetic_round(template, t_summ, n_over),
                          pins_by_role=synth_pins)
        c0 = over["cells"]["CELL_H2H_FPU02"]
        report["fpu_a1_at_or_above_bar_VOIDS"] = {
            "failed_games": n_over, "rate_of_games": n_over / 800.0,
            "failed_gates": c0["failed_gates"], "branch": c0["branch"],
            "verdict": over["verdict"]["verdict"]}
        if "G-N" not in c0["failed_gates"] or "G-DECKS" not in c0["failed_gates"]:
            problems.append(f"a failure rate AT the 2% bar ({n_over}/800) did "
                            f"not void on BOTH G-N and G-DECKS: "
                            f"{c0['failed_gates']}")
        if c0["branch"] != "H-VOID-INSTRUMENT":
            problems.append("an at-the-bar failure rate did not void the cell")

        # ⭐ THE DEFECT VARIANTS — a gate nobody has seen FAIL is untested.
        for label, mutate, want_gate in FIXTURE_DEFECTS:
            mut = {n: json.loads(json.dumps(c, default=str))
                   for n, c in cells.items()}
            mutate(mut)
            vv = adjudicate(mut, pins_by_role={"laptop": pin}, specs=specs)
            fired = ([g["gate"] for g in vv["round_gates"] if not g["ok"]]
                     + sorted({x for c in vv["cells"].values()
                               for x in c["failed_gates"]}))
            voided = [n for n, b in vv["branches"].items()
                      if b == "H-VOID-INSTRUMENT"]
            report[label] = {"branches": vv["branches"], "failed": fired,
                             "voided": voided,
                             "verdict": vv["verdict"]["verdict"]}
            if want_gate and want_gate not in fired:
                problems.append(f"defect {label!r} did NOT fire {want_gate} "
                                f"(fired: {fired})")
            if not voided:
                problems.append(f"defect {label!r} voided NO cell")
            if vv["verdict"]["verdict"] != "H-VOID-INSTRUMENT":
                problems.append(f"defect {label!r} did not force a VOID verdict")

        # ------------------------------------------------------------- #
        # ⭐ THE IDENT ADJUDICATOR — its own three propositions, tested   #
        # ------------------------------------------------------------- #
        base = cells["CELL_H2H_FPU02"]
        a = json.loads(json.dumps(base, default=str))
        a2 = json.loads(json.dumps(base, default=str))
        b = json.loads(json.dumps(base, default=str))
        b["records"][0]["diff"] = b["records"][0]["diff"] + 7.0
        good = adjudicate_ident(a, a2, b)
        report["ident_healthy"] = {
            "propositions": good["propositions"], "ok": good["ident_ok"]}
        if not good["ident_ok"]:
            problems.append(f"the HEALTHY ident triple failed: "
                            f"{good['ident_problems']}")
        drift = json.loads(json.dumps(base, default=str))
        drift["records"][1]["moves"] = 999
        bad1 = adjudicate_ident(a, drift, b)
        if bad1["propositions"]["IDENT-REPRODUCES"]["ok"]:
            problems.append("a NON-REPRODUCING ident pair passed "
                            "IDENT-REPRODUCES")
        report["ident_nonreproducing_detected"] = not bad1["ident_ok"]
        bad2 = adjudicate_ident(a, a2, json.loads(json.dumps(base, default=str)))
        if bad2["propositions"]["POSITIVE-ARB-ON"]["ok"]:
            problems.append("an ident triple whose B leg is IDENTICAL to A "
                            "passed POSITIVE-ARB-ON — the dose-binds-under-the-"
                            "arbiter check is the one no inherited certificate "
                            "gives, and it must fire here")
        report["ident_dose_did_not_bind_detected"] = not bad2["ident_ok"]
    else:
        problems.append("⚠️ selftest_fixture/ is not populated — the adjudicator "
                        "has never been run against a shaped archive. This is a "
                        "BUILD DEBT, and it is reported rather than hidden.")

    se0 = L.se_model(400)
    print(json.dumps({
        "problems": problems,
        "golden_gate_note": gg_note,
        "fixture": report,
        "branch_grid": grid,
        "golden_gate_inheritance": gg,
        "bars": {"BAR_EFFECT": L.BAR_EFFECT, "BRANCH_Z": L.BRANCH_Z,
                 "ELO_RESOLUTION_2SIGMA": L.ELO_RESOLUTION_2SIGMA},
        "read_distribution": {
            "delta=0": L.read_distribution(0.0, se0),
            "delta=BAR": L.read_distribution(L.BAR_EFFECT, se0),
            "delta=1.835": L.read_distribution(1.835, se0),
            "delta=2.951": L.read_distribution(2.95125, se0)},
        "n_decks_for_adopt_power(2.951,0.80)":
            L.n_decks_for_adopt_power(2.95125, 0.80),
        "n_decks_for_bounded_power(0.80)": L.n_decks_for_bounded_power(0.80),
        "budget": [L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS]}, indent=2))
    print(f"\nSELFTEST: {'PASS' if not problems else 'FAIL'} "
          f"({len(problems)} problem(s))")
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", type=Path,
                    help="directory holding one subdir per cell")
    ap.add_argument("--pin-laptop", type=Path, help="the laptop's PINNED_SRC_REV")
    ap.add_argument("--pin-local", type=Path,
                    help="⚠️ accepted for shape parity with the sibling rounds; "
                         "this round is LAPTOP ONLY (the owner holds local)")
    ap.add_argument("--smoke-mode", action="store_true",
                    help="structural keys ONLY — ⛔ the smoke emits NO outcome key")
    ap.add_argument("--smoke-cell", action="append", default=[],
                    metavar=SMOKE_CELL_SYNTAX,
                    help="⭐ R1: the §9.2 smoke's own synthetic cell spec, "
                         "PASSED BY run_cells.sh. Required by (and only legal "
                         "with) --smoke-mode. Repeatable.")
    ap.add_argument("--ident-mode", action="store_true",
                    help="⭐⭐ adjudicate the §9.3 arb-on-both-seats IDENT legs")
    ap.add_argument("--ident-a", type=Path, help="IDENT leg A directory")
    ap.add_argument("--ident-a2", type=Path,
                    help="IDENT leg A2 — same flags, same seeds as A")
    ap.add_argument("--ident-b", type=Path,
                    help="IDENT leg B — same seeds as A, dose DROPPED")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    # --------------------------------------------------------------------- #
    # ⭐⭐ IDENT MODE                                                        #
    # --------------------------------------------------------------------- #
    if args.ident_mode:
        missing = [f"--ident-{n}" for n, p in
                   (("a", args.ident_a), ("a2", args.ident_a2),
                    ("b", args.ident_b)) if p is None]
        if missing:
            ap.error("--ident-mode requires " + ", ".join(missing)
                     + " — with fewer than three legs neither proposition is "
                       "expressible and the read would vacuously exit 0")
        for p in (args.ident_a, args.ident_a2, args.ident_b):
            if not (p / "manifest.json").is_file():
                ap.error(f"⛔ {p} carries no manifest.json — ABSENT is FAIL")
        v = adjudicate_ident(load_cell(args.ident_a), load_cell(args.ident_a2),
                             load_cell(args.ident_b))
        v["legs"] = {"A": str(args.ident_a), "A2": str(args.ident_a2),
                     "B": str(args.ident_b)}
        v["golden_gate_inheritance"] = golden_gate_status()
        txt = json.dumps(v, indent=2, default=str)
        if args.out:
            args.out.write_text(txt)
            print(f"[analyze_h2h] wrote {args.out}")
        else:
            print(txt)
        if v["ident_problems"]:
            print("\n⛔ IDENT ADJUDICATION FAILED:", file=sys.stderr)
            for pr in v["ident_problems"]:
                print(f"  {pr}", file=sys.stderr)
            return 1
        return 0

    if not args.root:
        ap.error("--root, --ident-mode or --selftest")
    if args.smoke_cell and not args.smoke_mode:
        ap.error("--smoke-cell is only legal with --smoke-mode")

    # ⭐⭐ R1 — THE TWO SCANS ARE DISJOINT BY CONSTRUCTION.
    specs = None
    if args.smoke_mode:
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
                 and not p.name.startswith(("SMOKE_", "_VOID_"))}
    pins = {}
    if args.pin_laptop and args.pin_laptop.is_file():
        pins["laptop"] = args.pin_laptop.read_text().strip()
    if args.pin_local and args.pin_local.is_file():
        pins["local"] = args.pin_local.read_text().strip()
    v = adjudicate(cells, pins_by_role=pins, smoke_mode=args.smoke_mode,
                   specs=specs)

    if args.smoke_mode:
        # ⛔⛔ THE SMOKE EMITS NO OUTCOME KEY. The gate is a READ surface firing
        # on forbidden OUTCOME keys at ANY DEPTH (the Stage-2 `G-SMOKE` ruling):
        # a gate's `detail` and `why` carry the values it READ, and `RECON`'s
        # detail is literally the five outcome statistics under their own names.
        # So a smoke record keeps only `{gate, ok, address}` per gate — plus the
        # RESOLVED CONFIG, which is the smoke's whole substantive job.
        # ⚠️ THE ARBITER'S FIRE COUNTERS ARE **NOT** OUTCOME KEYS: `fired_plies`
        # / `phi` / `pickchanges` are instrument telemetry about a code path,
        # carry no W/D/L, no margin and no elo, and the smoke's second
        # substantive job is to prove BOTH SEATS arbitrated. They are kept, and
        # this comment is why.
        def _bare(g):
            return {"gate": g["gate"], "ok": g["ok"], "address": g["address"]}

        def _knob(c):
            d = next((g["detail"] for g in c["gates"]
                      if g["gate"] == "G-FPU"), None)
            out = {}
            if isinstance(d, dict):
                out = {k: d.get(k) for k in ("requested_fpu_reduction",
                                             "requested_c_puct_override",
                                             "shared_c_puct", "frozen")}
            t = next((g["detail"] for g in c["gates"]
                      if g["gate"] == "G-TWOSIDED"), None)
            if isinstance(t, dict):
                out["resolved_two_sided"] = t.get("resolved")
            ts = next((g["detail"] for g in c["gates"]
                       if g["gate"] == "G-TIEARB-SIDES"), None)
            if isinstance(ts, dict):
                out["tiearb_sides"] = ts.get("resolved")
                out["tiearb_expected_both_seats"] = ts.get("expected_both_seats")
            tf = next((g["detail"] for g in c["gates"]
                       if g["gate"] == "G-TIEARB-FIRE"), None)
            if isinstance(tf, dict):
                out["tiearb_fires"] = tf.get("sides")
            return out or None

        v = {"smoke_mode": True,
             "round_gates": [_bare(g) for g in v["round_gates"]],
             "round_gates_ok": v["round_gates_ok"],
             "golden_gate_inheritance": v["golden_gate_inheritance"],
             "cells": {n: {"gates": [_bare(g) for g in c["gates"]],
                           "gates_ok": c["gates_ok"],
                           "failed_gates": c["failed_gates"]}
                       for n, c in v["cells"].items()},
             "resolved_knobs": {n: _knob(c) for n, c in v["cells"].items()},
             "smoke_specs": [{"name": s.name, "knob": s.knob, "value": s.value,
                              "seed_start": s.seed_start,
                              "n_games": s.n_games} for s in (specs or ())],
             "note": "⭐ the smoke's TWO substantive jobs beyond liveness: it "
                     "returns the RESOLVED DOSE and the RESOLVED ARBITER DICT "
                     "FOR BOTH SEATS as the harness actually wrote them, on the "
                     "real argparse, on this box — the PG-D7..D9 lesson, plus "
                     "the 2026-08-31 one (a launcher that armed only the "
                     "candidate would ship a confounded arb+fpu cell claiming "
                     "one variable)."}
        v["smoke_problems"] = smoke_problems(v)
        v["smoke_ok"] = not v["smoke_problems"]

    txt = json.dumps(v, indent=2, default=str)
    if args.out:
        args.out.write_text(txt)
        print(f"[analyze_h2h] wrote {args.out}")
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
