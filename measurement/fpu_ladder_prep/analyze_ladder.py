#!/usr/bin/env python3
"""`analyze_ladder` — THE FPU DOSE-LADDER ROUND'S ADJUDICATOR.

⛔ **THE PAIR IS LAW.** [`DESIGN.md`](DESIGN.md) + [`READ_RULE.md`](READ_RULE.md).
If this file disagrees with them, **it is this file that is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 games exist.**

The order of business, which is not negotiable:

  1. **Every §4 gate, per rung.** `ABSENT` is `FAIL`, never a skip and never a
     default. Every gate prints WHICH DOCUMENT and WHICH ADDRESS answered —
     config from `manifest.json`, statistics from `summary.json`, which carries
     no config block at all (IS-D1).
     ⭐⭐ `G-N` and `G-DECKS` are the `FPU-A1` fix: the 2% failure bar and the
     80% common-deck floor ARE the conditions, exactly as the frozen prose of
     both rounds says. A sub-2% failure is REPORTED, not voided.
  2. **The §5 ladder, PER RUNG, on that rung's own realized SE, against zero.**
     ⛔ Four rungs on four bands: nothing is pooled and NO CROSS-RUNG CONTRAST
     IS A BRANCH INPUT.
  3. **The §5.4 ROUND VERDICT** — `LADDER-LIVE` / `LADDER-DEAD` /
     `LADDER-UNRESOLVED` / `LADDER-VOID`, computed in `screen_lib` so it cannot
     be re-read favourably after the fact.
  4. The companions, each flagged ⛔ NEVER A BRANCH INPUT — including the
     pre-stated 0.2 / 0.4 context rows, which are CROSS-BAND and carry CL-068's
     over-dispersion in full.

⭐ `--selftest` exercises the library's arithmetic, the dense `(M, SE)` branch
grid, the round-verdict table, the shipped fixture, the named DEFECT variants,
and the GOLDEN GATE artefact — and is a PRE-LAUNCH checklist item precisely
because a launcher-side gate that runs once per round is never exercised by the
smoke.
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
    from a real manifest voids every healthy cell."""
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
                  a1, ("the rung is on its OWN frozen band with the frozen deck "
                       "count, 2 seatings per deck" if not bad else
                       "⛔ G-BAND FAILED: " + "; ".join(bad)))


def gate_budget(spec, cell) -> dict:
    """`G-BUDGET` — k16x1376 = 22016 BOTH SIDES (the 2026-08-30 promoted
    champion). A rung that ran the superseded 11008 is measuring the dose
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
    ], "manifest:config.backend.* — ⚠️ fpu_reduction is threaded on BOTH "
       "backends (unlike the J-rules surfaces and the tie arbiter, which are "
       "rust-only), so a python leg would NOT be knob-blind. It is still "
       "refused: the champion of record plays on rust, and a mixed-backend "
       "round is not one round.")


def gate_wheel(spec, cell) -> dict:
    return _simple("G-WHEEL", cell, [
        (("manifest:carc_rs_build",),
         lambda v: bool(v) and "unavailable" not in str(v), "carc_rs_build"),
        (("manifest:carc_rs_binary_sha",), lambda v: bool(v), "carc_rs_binary_sha"),
        (("manifest:mixed_builds",), lambda v: v is False, "mixed_builds"),
    ], "manifest — ⚠️ carc_rs_version is permanently '0.1.0' and is NOT a "
       "discriminator. ⚠️⚠️ UNLIKE THE PARENT ROUND, THE WHEEL HAS MOVED since "
       "its golden gate was banked (the S1 R7/R6 merge touched carc_core::search "
       "and fair::search_worlds). DESIGN §9 states why the parent's "
       "FPU_BITEXACT.json is therefore NOT inherited and a fresh bit-exact run "
       "at the launch wheel is a LAUNCH PRECONDITION.")


def gate_n(spec, cell) -> dict:
    """⭐⭐ `G-N` — delegated to `screen_lib.n_gate`, which IS the frozen prose
    (the `FPU-A1` fix). ⛔ There is no stricter column here."""
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
                   else "⛔ RECON DISAGREES — the rung VOIDS: " + "; ".join(bad)))


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
        # ⚠️ THE SECONDARY, reported beside the primary on EVERY branch and never
        # quoted bare. ⛔ In THIS round the elo is not even a bar: the adoption
        # bar is +1.5 pts/deck and there is no exchange rate into elo that this
        # round measures. R4's paired footing is carried.
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
            "warning": "⚠️⚠️ THIS IS A RESOLUTION, NOT A BAR. The adoption bar "
                       "is +1.5 pts/deck on the deck-paired MARGIN and no "
                       "branch reads this block. elo may never be quoted bare; "
                       "a disagreement between the margin and the elo is "
                       "DISCLOSED, not arbitrated.",
        },
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
    # ⚠️ `carc_rs_binary_sha` is BOX-LOCAL: two boxes compiling identical source
    # produce different bytes. G-WHEEL-SAME is asserted PER BOX; the cross-box
    # build identity is `carc_rs_build`'s job.
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
        ("every rung on a box shares that box's binary sha ⚠️ the sha is "
         "BOX-LOCAL and is never compared ACROSS boxes."
         if not bad_roles and by_role else
         f"⛔ a box ran more than one wheel: {bad_roles or 'no cells'} — "
         "A FAIL ON ANY RUNG VOIDS EVERY RUNG")))

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
         "⛔ BLIND_COMMIT absent, malformed, or disagreeing across rungs — "
         "ABSENT is FAIL; a read that was not blind is not a read")))

    round_ok = all(g["ok"] for g in round_gates)

    # --- the ladder, PER RUNG ---------------------------------------------
    # ⛔ NO POOLING, NO ANCHOR, NO CROSS-RUNG CONTRAST. Four bands, four
    # within-band questions.
    branches = {}
    for name, c in per_cell.items():
        st = c["stats"]
        branches[name] = L.branch_for_cell(
            st["M"], st["se"], st["z"], gates_ok=(c["gates_ok"] and round_ok))
        c["branch"] = branches[name]
        c["riders"] = list(L.RIDERS_ALWAYS) + list(
            L.RIDERS_R_ADOPT if branches[name] == "R-ADOPT-CANDIDATE" else
            L.RIDERS_R_BOUNDED if branches[name] == "R-BOUNDED" else
            L.RIDERS_R_NEGATIVE if branches[name] == "R-NEGATIVE" else
            L.RIDERS_R_UNRESOLVED if branches[name] == "R-UNRESOLVED" else ())

    # --- ⭐⭐ THE ROUND VERDICT (§5.4) --------------------------------------
    verdict = L.round_verdict(branches, round_gates_ok=round_ok,
                              expected_cells=[s.name for s in specs])

    out = {
        "round": "fpu_ladder (4 rungs, 4 bands, one dose each)",
        "pair": ["measurement/fpu_ladder_prep/DESIGN.md",
                 "measurement/fpu_ladder_prep/READ_RULE.md"],
        "smoke_mode": smoke_mode,
        "budget": {"k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
                   "total_sims": L.TOTAL_SIMS,
                   "note": "the 2026-08-30 promoted desktop champion, BOTH sides"},
        "bars": {"BAR_EFFECT": L.BAR_EFFECT,
                 "adopt": "LB95(M) >= +%.3f pts/deck" % L.BAR_EFFECT,
                 "bounded": "UB95(M) < +%.3f pts/deck" % L.BAR_EFFECT,
                 "provenance": "⭐ AN EFFECT SIZE, NOT 2 sigma-hat (owner ruling "
                               "2026-08-30). DESIGN §3 derives it and READ_RULE "
                               "§8 states what it costs."},
        "round_gates": round_gates,
        "round_gates_ok": round_ok,
        "cells": per_cell,
        "branches": branches,
        "round_verdict": verdict,
        "golden_gate": _golden_gate_status(),
        "riders": list(L.RIDERS_ALWAYS),
        "adoption_chain": list(L.ADOPTION_CHAIN),
    }
    if verdict["verdict"] == "LADDER-VOID":
        out["void_banner"] = (
            "⛔ LADDER-VOID — the ROUND discharges nothing. ⚠️ A rung that is "
            "itself U-VOID-INSTRUMENT reports its statistics as a COMPANION "
            "TABLE only, under this banner, and no reading of any kind is taken "
            "from it. ⭐ The rungs that PASSED their gates keep their own "
            "per-rung readings — they are separate questions on separate bands "
            "— but LADDER-DEAD may not be declared, because a voided or absent "
            "rung is not a bound.")

    # --- companions. ⛔ NEVER branch inputs --------------------------------
    comp: dict = {
        "_warning": "⛔ COMPANIONS — NEVER A BRANCH INPUT.",
        "context_rows_0p2_and_0p4": L.CONTEXT_ROWS,
        "context_warning": L.CONTEXT_WARNING,
        "prior_art": L.PRIOR_ART,
        "prior_art_warning":
            "⛔ CROSS-ERA AND CROSS-BAND. Never pooled, never z-combined, never "
            "a gate input. CL-068 measured 1.8-2.2x over-dispersion on merely "
            "CROSS-BAND contrasts; these are also cross-AGENT (neural / "
            "value-blended vs the classical champion) and cross-BUDGET.",
        "dose_response_shape": None,
        "family_wise":
            "⛔ FOUR RUNGS = FOUR COMPARISONS, DISCLOSED NOT CORRECTED. ⭐ At "
            "the LB95 adoption bar the family-wise FALSE-ADOPT rate under a "
            "global null is ~0.006% — this bar cannot fire on noise. ⚠️ The "
            "price of that conservatism is in READ_RULE §8: LADDER-DEAD fires "
            "only ~10% of the time under a true global null at n=400 "
            "decks/rung. A LONE firing rung beside three nulls is still read as "
            "feedback_results_table_source_of_truth's NOISE SIGNATURE.",
        "read_distribution_at_launch_time_model": {
            "delta=0 (true null)": L.read_distribution(0.0),
            "delta=+1.5 (exactly at the bar)": L.read_distribution(L.BAR_EFFECT),
            "delta=+2.951 (a repeat of the incumbent)":
                L.read_distribution(2.95125),
            "note": "⛔ MODELLED at se_model(400)=0.6905, PRE-REGISTERED in "
                    "READ_RULE §8 before game 1. Every BRANCH above is "
                    "adjudicated at the rung's OWN REALIZED SE, never at this.",
        },
    }
    shape = []
    for s in specs:
        c = per_cell.get(s.name)
        if c and c["stats"]["M"] is not None:
            shape.append({"dose": s.value, "band": s.seed_start,
                          "M": c["stats"]["M"], "se": c["stats"]["se"],
                          "LB95": c["stats"]["LB95"], "UB95": c["stats"]["UB95"],
                          "branch": c.get("branch")})
    if len(shape) >= 2:
        shape.sort(key=lambda r: r["dose"])
        comp["dose_response_shape"] = {
            "rungs": shape,
            "context_0.2": L.CONTEXT_ROWS[
                "fpu_reduction=0.2 (fpu_resurrection CELL_FPU02, band 155e9)"],
            "context_0.4": L.CONTEXT_ROWS[
                "fpu_reduction=0.4 (fpu_resurrection CELL_FPU04, band 156e9)"],
            "warning":
                "⛔⛔ A DIRECTION, NOT A CURVE, AND NOT A BRANCH INPUT. Every "
                "rung sits on its OWN band, so EVERY comparison in this table — "
                "rung vs rung AND rung vs context row — is CROSS-BAND, and "
                "CL-068 measured 1.8-2.2x over-dispersion on exactly that class, "
                "in both the elo and the deck-paired-margin statistics. ⛔ No "
                "optimum may be located here, no interpolation is licensed, and "
                "feedback_bracket_hyperparams' >=3-well-spread-points rule is "
                "NOT satisfied by four readings that do not share a footing.",
        }
    out["companions"] = comp
    return out


# =========================================================================== #
# ⭐⭐ THE SMOKE'S OWN SPECS — R1, CARRIED FROM THE PARENT ROUND               #
# =========================================================================== #
# ⛔⛔ THE DEFECT THIS CLOSES (fpu_resurrection pre-launch merge review,
# 2026-08-30). `--smoke-mode` adjudicated ZERO cells, by TWO independent
# mechanisms, and still exited 0 — so `run_cells.sh`'s
# `|| DIE "the smoke adjudication FAILED"` was UNREACHABLE and the smoke's one
# substantive job (read the RESOLVED KNOB back out of the EMITTED manifest)
# silently did nothing:
#
#   (1) the cell scan dropped every dir named `SMOKE_*` (the launcher names them
#       that) — correct for a ROUND read, fatal for a SMOKE read, which
#       adjudicates at the parent `$SHARE/$OUT_TAG`;
#   (2) `adjudicate()` iterates `screen_lib.CELLS`, which names only the ROUND
#       rungs, so a `SMOKE_*` dir had no spec to be adjudicated against.
#
# ⚠️ The identical defect is REALIZED in phasegate's banked `SMOKE_local.json`
# (`"cells": {}`) — `measurement/phasegate_prep/AMENDMENTS.md`, PG-D10/PG-A2.
#
# The smoke's spec cannot come from `L.CELLS` (it is not a round rung) and must
# not be invented here (a restated knob proves nothing about the launcher), so
# `run_cells.sh` PASSES it and the value is then checked against what the
# harness actually EMITTED.

SMOKE_CELL_SYNTAX = "NAME=knob:value:seed_start:n_games:role"


def parse_smoke_cell(text: str) -> "L.CellSpec":
    """`SMOKE_FPU=fpu_reduction:0.05:167999999500:8:local` -> a `CellSpec`.

    ⛔ The NAME must start with `SMOKE_`: only smoke archives are adjudicable in
    `--smoke-mode`, and admitting any other name would let a re-smoke at a root
    that already holds real rungs adjudicate a ROUND rung under smoke rules.
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
        raise ValueError(f"--smoke-cell {text!r}: role must be local|laptop "
                         "— G-HOST proves the smoke ran on the box whose code "
                         "path it was written to exercise")
    if not name.startswith("SMOKE_"):
        raise ValueError(f"--smoke-cell {text!r}: the name must start with "
                         "'SMOKE_' — only smoke archives are adjudicable in "
                         "--smoke-mode, and a round rung must never be")
    if knob != "fpu_reduction":
        raise ValueError(f"--smoke-cell {text!r}: unknown knob {knob!r} — every "
                         "rung of this round owns fpu_reduction and the smoke "
                         "must exercise the code path the round will run")
    n = int(n_games)
    if n < 2 or n % 2:
        raise ValueError(f"--smoke-cell {text!r}: n_games {n} is not an even "
                         "count of deck-paired games")
    return L.CellSpec(name=name, role=role, knob=knob, value=float(value),
                      seed_start=int(seed_start), n_decks=n // 2,
                      purpose="⭐ THE §9 SMOKE — the THROWAWAY sub-range, "
                              "PRODUCTION knobs, only the game count reduced. "
                              "⛔ Buys no deck of the round and claims no band.")


#: The gates the smoke EXISTS to run. ⛔ A smoke archive legitimately fails gates
#: about the ROUND (`G-BLIND` — stamped with no blind commit; `G-REV` — it runs
#: at the PRE-LAUNCH commit by design; `G-N` — 8 games, not 800), so "all gates
#: ok" is the wrong bar and would make the smoke unusable. These two are the
#: ones whose failure means the LAUNCHER is wrong:
#:   * `G-FPU`      — the dose was REQUESTED and the emitted manifest says so;
#:   * `G-TWOSIDED` — it BOUND, and bound on the CANDIDATE side ONLY.
SMOKE_REQUIRED_GATES = ("G-FPU", "G-TWOSIDED")


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
        elif k.get("requested_fpu_reduction") is None:
            probs.append(f"⛔ {name}: the emitted manifest requested NO "
                         "fpu_reduction — the launcher did not put the dose on "
                         "the wire, and every rung of this round is an "
                         "fpu_reduction rung")
    for name, c in cells.items():
        by_id = {g["gate"]: g["ok"] for g in c.get("gates", [])}
        ran = [g for g in SMOKE_REQUIRED_GATES if g in by_id]
        if not ran:
            probs.append(f"⛔ {name}: none of {SMOKE_REQUIRED_GATES} executed")
        for gid in ran:
            if not by_id[gid]:
                probs.append(
                    f"⛔ {name}: {gid} FAILED. " + (
                        "The dose did not BIND on the candidate, or it bound on "
                        "the OPPONENT TOO. A round launched over this is "
                        "champion-vs-champion and EVERY other gate passes it."
                        if gid == "G-TWOSIDED" else
                        "The emitted manifest does not carry the dose this box "
                        "was told to smoke."))
    return probs


def _golden_gate_status() -> dict:
    """⭐ The GOLDEN GATE artefact, surfaced in every read-out.

    ⚠️⚠️ **THIS ROUND OWES A FRESH ONE.** The parent's `FPU_BITEXACT.json` was
    banked on wheel `f6316d42838574de`; the S1 `R7`/`R6` merge (2026-08-30) has
    since changed `carc_core::search` and `fair::search_worlds` and the installed
    binary has moved. `DESIGN.md` §9 states the inheritance question and its
    answer. This function reads `FPU_BITEXACT_LADDER.json` — the artefact
    `golden_gate/run_golden_gate.sh` produces AT THE LAUNCH WHEEL — and falls
    back to naming the parent's as INHERITED-BUT-INSUFFICIENT."""
    p = HERE / "FPU_BITEXACT_LADDER.json"
    if not p.is_file():
        parent = (HERE.parent / "fpu_resurrection_prep" / "FPU_BITEXACT.json")
        return {
            "verdict": "ABSENT", "ok": False,
            "inherited_parent_artifact": str(parent) if parent.is_file() else None,
            "why": "⛔⛔ FPU_BITEXACT_LADDER.json ABSENT — ABSENT is FAIL. The "
                   "parent round's FPU_BITEXACT.json is NOT a substitute: it "
                   "was adjudicated on carc_rs binary f6316d42838574de under a "
                   "ONE-WHEEL check, and the S1 R7/R6 merge has since changed "
                   "carc_core::search and fair::search_worlds — the exact "
                   "modules that implement the FPU rule and the PIMC descent "
                   "this round plays on. ⭐ Run "
                   "golden_gate/run_golden_gate.sh ON THE LAUNCH BOX AT THE "
                   "LAUNCH REV. It is a LAUNCH PRECONDITION (DESIGN §9), not a "
                   "nicety: a dose that never bound plays "
                   "champion-vs-champion, moves no leaf hash, sits inside "
                   "G-SAT's rail and reads as a clean, credible null."}
    v = json.loads(p.read_text())
    return {"verdict": v.get("verdict"), "ok": v.get("verdict") == "PASS",
            "failed": v.get("failed"),
            "wheel": v.get("wheel"),
            "checks": {c["check"]: c["ok"] for c in v.get("checks", [])},
            "why": "⭐ bit-exact at fpu=None (the DEFAULT path is unmoved on THIS "
                   "wheel) AND every rung's dose BINDS — including 0.05, the "
                   "smallest, which is the one a dose-blind build would be "
                   "hardest to distinguish from the champion. Without the "
                   "positive half the first is worth nothing: the hard-coded "
                   "None this family removed would have passed IDENTITY "
                   "perfectly."}


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


def _synthetic_round(template_manifest: dict, failed_decks: int = 0) -> dict:
    """⭐⭐ A synthetic round AT THE FROZEN SCALE (400 decks/rung), built from a
    REAL EMITTED manifest shape.

    ⛔⛔ **THIS EXISTS BECAUSE THE 2% BAR IS NOT TESTABLE AT FIXTURE SCALE.**
    The shipped fixture's biggest rung is 12 decks, and `int(0.02 * 12) = 0`, so
    no whole number of failed decks lands strictly BELOW the bar there. The
    `FPU-A1` regression — *a sub-2% failure is REPORTED and the rung still
    READS* — is the single most important property of this instrument, and a
    test that could not express it would be a test of nothing. At 400 decks,
    `7/400 = 1.75%` is below the bar and `8/400 = 2.00%` is at it.

    `failed_decks` decks are played at ONE SEAT ONLY, exactly as a per-game
    failure appears on disk (the emitter records EXCLUSIONS, not zeros), and
    `summary.n_failed` is moved to match so the accounting identity holds.
    """
    import math as _m
    import random as _r
    rng = _r.Random(7)
    cells = {}
    for spec in L.CELLS:
        man = json.loads(json.dumps(template_manifest))
        man["host"] = ("laptop-wsl" if spec.role == "laptop" else "Doctor")
        man["code_rev"] = SYNTH_PIN[:9]
        man["BLIND_COMMIT"] = SYNTH_BLIND
        man["carc_rs_binary_sha"] = ("2222222222222222" if spec.role == "laptop"
                                     else "1111111111111111")
        man["n_failed"] = failed_decks
        cfg = man["config"]
        cfg["band_seed_start"] = spec.seed_start
        cfg["seed_start"] = spec.seed_start
        cfg["n_decks"] = spec.n_decks
        cfg["n"] = spec.n_games
        cfg["cand_search"]["fpu_reduction"] = spec.value
        cfg["champion"]["fpu_reduction"] = spec.value
        # a small, healthy, BOUNDED shape: M ~ +0.2, sd 13.8 -> se 0.69
        recs = []
        for i in range(spec.n_decks):
            seed = spec.seed_start + i
            d = 0.2 + rng.gauss(0.0, 13.8)
            spread = rng.gauss(0.0, 30.0)
            seats = (0, 1)
            if i < failed_decks:
                seats = (0,)          # ⛔ the failed seating is ABSENT, not zero
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
        cells[spec.name] = {
            "root": f"<synthetic:{spec.name}>", "manifest": man,
            "summary": {"n": len(recs), "n_failed": failed_decks,
                        "n_paired": len(ds), "paired_mean_margin": mean,
                        "paired_z": mean / se if se else float("nan"),
                        "winrate": wr,
                        "elo": (400.0 * _m.log10(wr / (1 - wr))
                                if 0 < wr < 1 else 800.0)},
            "records": recs}
    return cells


#: ⭐ THE NAMED DEFECTS — one per gate whose failure would otherwise never be
#: observed. Each must (a) fire its own gate and (b) drive its rung to a VOID.
#: ⛔⛔ The first three are this design's most dangerous failure mode, in its
#: three disguises: a rung whose dose NEVER BOUND is champion-vs-champion, moves
#: no leaf hash, sits inside G-SAT's rail, and reads as a clean credible null.
FIXTURE_DEFECTS = (
    ("hardcoded_none_defect_dose_never_bound",
     lambda c: _set(c["CELL_FPU005"]["manifest"],
                    "config.champion.fpu_reduction", None),
     "G-TWOSIDED"),
    ("harness_predates_the_round_cand_search_absent",
     lambda c: _del(c["CELL_FPU005"]["manifest"], "config.cand_search"),
     "G-FPU"),
    ("wrong_dose_on_the_wire",
     lambda c: _set(c["CELL_FPU010"]["manifest"],
                    "config.cand_search.fpu_reduction", 0.05),
     "G-FPU"),
    ("a_stray_cand_c_puct_override",
     lambda c: _set(c["CELL_FPU015"]["manifest"],
                    "config.cand_search.c_puct", 1.0),
     "G-FPU"),
    ("opponent_carries_a_dose",
     lambda c: _set(c["CELL_FPU030"]["manifest"],
                    "config.opponent.champ_cfg.fpu_reduction", 0.3),
     "G-TWOSIDED"),
    ("a_second_variable_moved",
     lambda c: _set(c["CELL_FPU005"]["manifest"], "config.champion.tau_p", 8.0),
     "G-SINGLEVAR"),
    ("tie_arbiter_left_armed",
     lambda c: _set(c["CELL_FPU010"]["manifest"],
                    "config.cand_tiearb.enabled", True),
     "G-ARB-OFF"),
    ("stale_budget_11008",
     lambda c: (_set(c["CELL_FPU005"]["manifest"], "config.champion.k_dets", 8),
                _set(c["CELL_FPU005"]["manifest"], "config.champion.total_sims",
                     11008)),
     "G-BUDGET"),
    ("leaf_hashes_differ_across_the_two_sides",
     lambda c: _set(c["CELL_FPU010"]["manifest"], "config.opp_leaf_hash",
                    "deadbeef"),
     "G-LEAF"),
    ("mixed_rev_round",
     lambda c: _set(c["CELL_FPU030"]["manifest"], "code_rev", "cccccccc"),
     "G-REV"),
    ("recon_disagrees_with_the_summary",
     lambda c: _set(c["CELL_FPU005"]["summary"], "paired_mean_margin", 99.0),
     "RECON"),
    ("rung_ran_on_the_wrong_box",
     lambda c: _set(c["CELL_FPU030"]["manifest"], "host", "Doctor"),
     "G-HOST"),
    ("seed_outside_the_rungs_own_band",
     lambda c: c["CELL_FPU010"]["records"].append(
         {"seed": 999999999999, "a_seat": 0, "diff": 1.0,
          "won_by_champ": True, "drew": False}),
     "G-DECKS"),
    # ⚠️ AT FIXTURE SCALE one lost seating is 1/12 = 8.3%, which is ABOVE the 2%
    # bar and therefore MUST void. The sub-bar direction — the FPU-A1 property
    # itself — is untestable at 12 decks and is tested at the FROZEN 400-deck
    # scale by `_synthetic_round`; see `selftest()`.
    ("a_deck_was_played_at_one_seat_only_ABOVE_the_bar",
     lambda c: c["CELL_FPU005"]["records"].pop(),
     "G-DECKS"),
    # ⛔ AND THE ACCOUNTING IDENTITY: games that vanished WITHOUT being recorded
    # as failures. A denominator nobody knows is a strictly worse defect than a
    # recorded failure, and it is NOT the case the 2% bar absorbs.
    ("games_vanished_without_a_failure_record",
     lambda c: c["CELL_FPU010"]["summary"].__setitem__("n", 15),
     "G-N"),
)


def selftest() -> int:
    problems = list(L.sanity_check())
    grid = L.branch_grid(step=0.02)
    if not grid["all_reachable"]:
        problems.append(f"branch grid: only {grid['reachable']} reachable")

    gg = _golden_gate_status()
    if not gg["ok"]:
        # ⚠️ REPORTED, NOT FATAL TO THE SELFTEST — and it IS fatal to the
        # LAUNCHER (`run_cells.sh` refuses without a PASS). The instrument must
        # be testable before the gate has been run, or the build could never
        # reach the point of running it; the launcher is where it becomes a hard
        # abort. `tests/test_fpu_ladder_instrument.py` pins that asymmetry.
        problems_note = (
            f"⚠️ the GOLDEN GATE is {gg['verdict']} — this is EXPECTED at build "
            "time and is a LAUNCH PRECONDITION, not a build failure. "
            "run_cells.sh REFUSES a real rung without a PASS.")
    else:
        problems_note = "⭐ the GOLDEN GATE reads PASS at this wheel."

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
    if v["round_verdict"]["verdict"] != "LADDER-VOID":
        problems.append("an all-empty round did not read LADDER-VOID")

    # ------------------------------------------------------------------ #
    # THE SHIPPED FIXTURE — a shaped, HEALTHY round, plus the named defects #
    # ------------------------------------------------------------------ #
    fx = HERE / "selftest_fixture"
    report: dict = {}
    if fx.is_dir() and (fx / "SPECS.json").is_file():
        specs = fixture_specs(fx)
        frozen = {c.name: c for c in L.CELLS}
        if sorted(s.name for s in specs) != sorted(frozen):
            problems.append("the fixture's rung NAMES differ from the frozen plan")
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
            "round_verdict": v["round_verdict"]["verdict"],
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
        # ⭐ the fixture is SHAPED so every branch that matters is exercised at
        # once, and so the ROUND verdict is the interesting one.
        want = {"CELL_FPU005": "R-BOUNDED", "CELL_FPU010": "R-UNRESOLVED",
                "CELL_FPU015": "R-ADOPT-CANDIDATE", "CELL_FPU030": "R-NEGATIVE"}
        if v["branches"] != want:
            problems.append(f"the HEALTHY fixture read {v['branches']}, want {want}")
        if v["round_verdict"]["verdict"] != "LADDER-LIVE":
            problems.append("the HEALTHY fixture's adopting rung did not drive "
                            "LADDER-LIVE")

        # ------------------------------------------------------------- #
        # ⭐⭐ THE FPU-A1 REGRESSION PAIR — AT THE FROZEN 400-DECK SCALE   #
        # ------------------------------------------------------------- #
        # ⛔⛔ THE SINGLE MOST IMPORTANT PROPERTY OF THIS INSTRUMENT, tested in
        # BOTH directions on a synthetic round built from a REAL manifest shape.
        # It is done at 400 decks and NOT at fixture scale for an arithmetic
        # reason: `int(0.02 * 12) = 0`, so no whole number of failed decks lands
        # strictly BELOW the bar in a 12-deck fixture, and the test would be
        # vacuous. ⭐ The bar's denominator is GAMES (a one-seat-only deck is one
        # failed GAME — the same quantity G-N reads out of summary.n_failed), so
        # at the frozen 800-game rung 15 failures = 1.875% (below) and 16 = 2.00%
        # (at). ⛔ BOTH G-N and G-DECKS must agree on both sides of the bar: the
        # first draft of decks_gate used a DECKS denominator and the two gates
        # then disagreed by a factor of two on the same archive — caught here,
        # in build, before game 1.
        template = cells["CELL_FPU005"]["manifest"]
        synth_pins = {"local": SYNTH_PIN, "laptop": SYNTH_PIN}
        # ⭐ first: a CLEAN synthetic round must read cleanly, or the two cases
        # below would be testing the synthesizer.
        clean = adjudicate(_synthetic_round(template, 0),
                           pins_by_role=synth_pins)
        report["synthetic_clean_round"] = {
            "branches": clean["branches"],
            "round_verdict": clean["round_verdict"]["verdict"],
            "failed": {n: c["failed_gates"] for n, c in clean["cells"].items()
                       if c["failed_gates"]}}
        if any(c["failed_gates"] for c in clean["cells"].values()):
            problems.append("the CLEAN synthetic 400-deck round failed gates: "
                            f"{report['synthetic_clean_round']['failed']} — the "
                            "FPU-A1 cases below would be testing the "
                            "synthesizer, not the bar")
        # (a) a SUB-2% failure must be REPORTED and every rung must still READ.
        n_sub = int(L.FAILURE_RATE_VOID * 800) - 1        # 15 games = 1.875%
        sub = adjudicate(_synthetic_round(template, n_sub), pins_by_role=synth_pins)
        report["fpu_a1_sub_bar_failure_is_REPORTED_not_void"] = {
            "failed_games": n_sub, "rate_of_games": n_sub / 800.0,
            "failed_gates": {n: c["failed_gates"] for n, c in sub["cells"].items()},
            "branches": sub["branches"],
            "round_verdict": sub["round_verdict"]["verdict"],
            "g_n_note": next((g["why"] for g in
                              sub["cells"]["CELL_FPU005"]["gates"]
                              if g["gate"] == "G-N"), None)}
        for n, c in sub["cells"].items():
            if c["failed_gates"]:
                problems.append(
                    "⛔⛔ FPU-A1 REGRESSION: a failure rate STRICTLY BELOW the "
                    f"2% bar ({n_sub}/800 games = {n_sub / 8:.3f}%) voided {n} on "
                    f"{c['failed_gates']}. The frozen prose of BOTH rounds says "
                    "such a rate is REPORTED, never silently absorbed — and "
                    "never voiding. This is the exact defect "
                    "measurement/fpu_resurrection_prep/AMENDMENTS.md FPU-A1 had "
                    "to amend AFTER THE FACT, with the statistics visible.")
            if c["branch"] == "U-VOID-INSTRUMENT":
                problems.append(f"FPU-A1 REGRESSION: sub-bar rung {n} voided")
        if sub["round_verdict"]["verdict"] == "LADDER-VOID":
            problems.append("FPU-A1 REGRESSION: a sub-bar failure rate voided "
                            "the whole ROUND")
        # ⭐ and the failure must be REPORTED, not silently absorbed.
        gn = next(g for g in sub["cells"]["CELL_FPU005"]["gates"]
                  if g["gate"] == "G-N")
        if "REPORTED" not in (gn.get("why") or ""):
            problems.append("the sub-bar failure passed G-N SILENTLY — the "
                            "b32v64 precedent requires it be REPORTED")
        gd = next(g for g in sub["cells"]["CELL_FPU005"]["gates"]
                  if g["gate"] == "G-DECKS")
        if "ONE SEAT ONLY" not in (gd.get("why") or ""):
            problems.append("G-DECKS did not report the one-seat-only decks")
        # (b) a failure rate AT OR ABOVE the bar must VOID.
        n_over = int(L.FAILURE_RATE_VOID * 800)           # 16 games = 2.00%
        over = adjudicate(_synthetic_round(template, n_over), pins_by_role=synth_pins)
        c0 = over["cells"]["CELL_FPU005"]
        report["fpu_a1_at_or_above_bar_VOIDS"] = {
            "failed_games": n_over, "rate_of_games": n_over / 800.0,
            "failed_gates": c0["failed_gates"], "branch": c0["branch"],
            "round_verdict": over["round_verdict"]["verdict"]}
        if "G-N" not in c0["failed_gates"] or "G-DECKS" not in c0["failed_gates"]:
            problems.append(f"a failure rate AT the 2% bar ({n_over}/800) did "
                            f"not void on BOTH G-N and G-DECKS: "
                            f"{c0['failed_gates']}")
        if c0["branch"] != "U-VOID-INSTRUMENT":
            problems.append("an at-the-bar failure rate did not void the rung")
        if over["round_verdict"]["verdict"] != "LADDER-VOID":
            problems.append("a voided rung did not force LADDER-VOID")

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
                             "voided": voided,
                             "round_verdict": vv["round_verdict"]["verdict"]}
            if want_gate and want_gate not in fired:
                problems.append(f"defect {label!r} did NOT fire {want_gate} "
                                f"(fired: {fired})")
            if not voided:
                problems.append(f"defect {label!r} voided NO rung")
            if vv["round_verdict"]["verdict"] != "LADDER-VOID":
                problems.append(f"defect {label!r} did not force LADDER-VOID")
    else:
        problems.append("⚠️ selftest_fixture/ is not populated — the adjudicator "
                        "has never been run against a shaped archive. This is a "
                        "BUILD DEBT, and it is reported rather than hidden.")

    se0 = L.se_model(400)
    print(json.dumps({
        "problems": problems,
        "golden_gate_note": problems_note,
        "fixture": report,
        "branch_grid": grid,
        "golden_gate": gg,
        "bars": {"BAR_EFFECT": L.BAR_EFFECT, "BRANCH_Z": L.BRANCH_Z,
                 "ELO_RESOLUTION_2SIGMA": L.ELO_RESOLUTION_2SIGMA},
        "read_distribution": {
            "delta=0": L.read_distribution(0.0, se0),
            "delta=BAR": L.read_distribution(L.BAR_EFFECT, se0),
            "delta=2.951": L.read_distribution(2.95125, se0)},
        "n_decks_for_ladder_dead(0.80)": L.n_decks_for_ladder_dead(0.80),
        "n_decks_for_adopt_power(2.951,0.80)":
            L.n_decks_for_adopt_power(2.95125, 0.80),
        "budget": [L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS]}, indent=2))
    print(f"\nSELFTEST: {'PASS' if not problems else 'FAIL'} "
          f"({len(problems)} problem(s))")
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", type=Path,
                    help="directory holding one subdir per rung")
    ap.add_argument("--pin-local", type=Path, help="local box's PINNED_SRC_REV")
    ap.add_argument("--pin-laptop", type=Path, help="laptop's PINNED_SRC_REV")
    ap.add_argument("--smoke-mode", action="store_true",
                    help="structural keys ONLY — ⛔ the smoke emits NO outcome key")
    ap.add_argument("--smoke-cell", action="append", default=[],
                    metavar=SMOKE_CELL_SYNTAX,
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
    # ⛔ The real (non-smoke) branch must never adjudicate a smoke archive, which
    # runs at the PRE-LAUNCH commit by design, and `_VOID_*` is quarantine.
    specs = None
    if args.smoke_mode:
        # ⛔ THE MIRROR IMAGE, and it is the load-bearing half: a smoke read
        # adjudicates ONLY `SMOKE_*`. A re-smoke at a root that already holds
        # the round's real rungs must never touch them — otherwise a stale
        # rung's knobs would be reported as a smoke PASS.
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
                      if g["gate"] == "G-FPU"), None)
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
                     "returns the RESOLVED DOSE as the harness actually wrote "
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
        print(f"[analyze_ladder] wrote {args.out}")
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
