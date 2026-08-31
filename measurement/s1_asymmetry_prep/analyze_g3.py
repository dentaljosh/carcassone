#!/usr/bin/env python3
"""`analyze_g3` — S1 GATE G3's ADJUDICATOR (the three-arm decomposition cell).

⛔ **THE PAIR IS LAW.** [`DESIGN.md`](DESIGN.md) §6.4 + [`READ_RULE_G3.md`](READ_RULE_G3.md).
If this file disagrees with them, **it is this file that is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 games exist.**

The order of business, which is not negotiable:

  1. **Every gate, per arm.** `ABSENT` is `FAIL`, never a skip and never a
     default. Every gate prints WHICH DOCUMENT and WHICH ADDRESS answered —
     config from `manifest.json`, statistics from `summary.json`, which carries
     no config block at all (IS-D1).
  2. **The DUAL PRIMARY**, each on its OWN REALIZED SE: `P1 = margin(OPP vs
     champion)` and `P2 = margin(OPP) − margin(OWN)` **per deck** on the shared
     set. Holm step-down over the two, family α = 0.05.
  3. **One branch for the ROUND**, from `screen_lib_g3.branch_for_round`.
  4. The companions — the ALL control, elo, saturation, SE anomaly, `N4-COST` —
     each flagged ⛔ NEVER A BRANCH INPUT.

⭐ `--selftest` exercises the arithmetic, the dense branch grid, a shipped
fixture whose JSON is shaped like the **EMITTER's real output** (the PG-A1
lesson: a fixture written to the gate's expectation tests nothing), and one
named DEFECT per gate. It is a PRE-LAUNCH checklist item precisely because a
launcher-side gate that runs once per round is never exercised by the smoke.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_lib():
    """⛔ Loaded BY EXPLICIT PATH under a UNIQUE module name (the 2026-08-30 R2
    fix): three sibling prep dirs ship a `screen_lib`-shaped module and a bare
    import binds whichever one the collection order cached first."""
    spec = importlib.util.spec_from_file_location(
        "s1_g3_screen_lib", HERE / "screen_lib_g3.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["s1_g3_screen_lib"] = mod
    spec.loader.exec_module(mod)
    return mod


L = _load_lib()


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
        except Exception:                                      # noqa: BLE001
            recs.append({"_unreadable": str(p)})
    return {"root": str(root),
            "manifest": json.loads(man.read_text()) if man.is_file() else None,
            "summary": json.loads(summ.read_text()) if summ.is_file() else None,
            "records": recs}


def _docs(cell: dict) -> dict:
    return {"manifest": cell.get("manifest") or {},
            "summary": cell.get("summary") or {}}


# =========================================================================== #
# THE GATES                                                                    #
# =========================================================================== #

def _sides(cell) -> dict:
    """`{alias: {champion, opponent, *_absent, addresses}}` — the RESOLVED
    search config of each side.

    ⚠️ The opponent's knobs live ONE LEVEL DOWN at
    `config.opponent.champ_cfg.*`; a gate written from the design rather than
    from a real manifest voids every healthy cell (the phasegate lesson)."""
    d = _docs(cell)
    rows = {}
    for a in tuple(L.SINGLEVAR_ALIASES) + tuple(L.SINGLEVAR_ONESIDED_DEFAULTS):
        cv, ca = L.resolve(d, f"manifest:config.champion.{a}")
        ov, oa = L.resolve(d, f"manifest:config.opponent.champ_cfg.{a}",
                           f"manifest:config.opponent.{a}")
        rows[a] = {"champion": None if cv is L.MISSING else cv,
                   "opponent": None if ov is L.MISSING else ov,
                   "champion_absent": cv is L.MISSING,
                   "opponent_absent": ov is L.MISSING,
                   "addresses": [ca, oa]}
    return rows


def gate_scope(spec, cell) -> dict:
    d = _docs(cell)
    v, a = L.resolve(d, "manifest:config.cand_jrules_prior",
                     "manifest:cand_jrules_prior")
    ov, oa = L.resolve(d, "manifest:config.opponent.champ_cfg.jrules_prior",
                       "manifest:config.opponent.jrules_prior",
                       "manifest:config.opp_jrules_prior")
    return L.scope_gate(spec, v, a, ov, oa)


def gate_witness(spec, cell) -> dict:
    d = _docs(cell)
    cv, ca = L.resolve(d, *L.WITNESS_ADDRESSES["candidate"])
    ov, oa = L.resolve(d, *L.WITNESS_ADDRESSES["opponent"])
    return L.witness_gate(spec, cv, ca, ov, oa)


def gate_singlevar(spec, cell) -> dict:
    return L.singlevar_gate(spec, _sides(cell))


def gate_arb_off(spec, cell) -> dict:
    return L.arb_off_gate(cell.get("manifest") or {})


def gate_leaf(spec, cell) -> dict:
    d = _docs(cell)
    ch, _ = L.resolve(d, "manifest:config.cand_leaf_hash",
                      "manifest:config.leaf_hash")
    oh, _ = L.resolve(d, "manifest:config.opp_leaf_hash",
                      "manifest:config.opponent.leaf_hash")
    return L.leaf_gate(None if ch is L.MISSING else ch,
                       None if oh is L.MISSING else oh)


def gate_budget(spec, cell) -> dict:
    """`G-BUDGET` — k16 x 1376 = 22016 on BOTH sides, and the product multiplies
    out. An arm that ran the superseded 11008 measures the scope knob against a
    STALE OPPONENT, which is strictly worse than a wrong knob because every
    other gate passes it."""
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
                  "manifest:config.{champion,opponent.champ_cfg}.*",
                  (f"both sides run k{L.K_DETS} x {L.SIMS_PER_DET} = "
                   f"{L.TOTAL_SIMS} (the 2026-08-30 promoted desktop champion)"
                   if not bad else "⛔ G-BUDGET FAILED: " + "; ".join(bad)))


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


def gate_rules(spec, cell) -> dict:
    """`G-RULES` — `fixed_v1` with R9 observed. ⚠️ `rules_profile`'s argparse
    default is `walled` (the pre-F9 engine of record), NOT `fixed_v1` (PG-D8), so
    a launcher that forgets `--rules-profile` voids every arm here."""
    return _simple("G-RULES", cell, [
        (("manifest:rules_profile.name",), L.RULES_PROFILE, "rules_profile.name"),
        (("manifest:rules_profile.r9_env_ok",), True, "r9_env_ok"),
        (("manifest:rules_profile.r9_env_observed",), True, "r9_env_observed"),
    ], "manifest:rules_profile.* (⚠️ R9 is env-latched at IMPORT)")


def gate_backend(spec, cell) -> dict:
    """`G-BACKEND` — rust, both sides, no mixed builds.

    ⚠️ Unlike the FPU knobs, `jrules_prior_*` is **RUST-ONLY**: a nonzero dose
    hard-exits unless the resolved backend is rust
    (`eval_fair_puct.py:4118-4126`), and a `carc_rs` predating S1 rejects
    `scope='opp'` at config construction. Both are fail-closed, which is the good
    case; this gate records that the fail-closed path was not merely untested."""
    return _simple("G-BACKEND", cell, [
        (("manifest:config.backend.name",), L.BACKEND, "name"),
        (("manifest:config.backend.requested",), L.BACKEND, "requested"),
        (("manifest:config.backend.mixed_builds", "manifest:mixed_builds"),
         lambda v: v is False, "mixed_builds"),
    ], "manifest:config.backend.*")


def gate_exact(spec, cell) -> dict:
    return _simple("G-EXACT", cell, [
        (("manifest:config.endgame.exact_k",), L.EXACT_K, "exact_k"),
        (("manifest:config.endgame.mode",), L.EXACT_MODE, "mode"),
    ], "manifest:config.endgame.*")


def gate_wheel(spec, cell) -> dict:
    """`G-TOOL` — the wheel that ran is identified. ⚠️ `carc_rs_version` is
    permanently '0.1.0' and is NOT a discriminator; `carc_rs_build` is a content
    hash. ⭐ Load-bearing here because P2's two arms run on DIFFERENT BOXES."""
    return _simple("G-TOOL", cell, [
        (("manifest:carc_rs_build",),
         lambda v: bool(v) and "unavailable" not in str(v), "carc_rs_build"),
        (("manifest:carc_rs_binary_sha",), lambda v: bool(v),
         "carc_rs_binary_sha"),
        (("manifest:mixed_builds",), lambda v: v is False, "mixed_builds"),
    ], "manifest:carc_rs_*")


def gate_host(spec, cell) -> dict:
    d = _docs(cell)
    h, a = L.resolve(d, "manifest:host")
    ok, why = L.host_matches_box(None if h is L.MISSING else h, spec.role)
    return L.gate("G-HOST", ok, {"host": None if h is L.MISSING else h,
                                 "frozen_role": spec.role}, a, why)


def gate_paired(spec, cell) -> dict:
    return L.paired_gate(spec, cell.get("records") or [],
                         cell.get("summary") or {})


def gate_blind(spec, cell) -> dict:
    """`G-BLIND` — the arm carries the freeze commit's 40-hex sha as a stamp.
    ⛔ A read that was not blind is not a read (CL-079 / CL-084)."""
    d = _docs(cell)
    v, a = L.resolve(d, "manifest:stamps.BLIND_COMMIT",
                     "manifest:config.stamps.BLIND_COMMIT",
                     "manifest:BLIND_COMMIT")
    ok = v is not L.MISSING and L.is_hex40(v)
    return L.gate("G-BLIND", ok, {"BLIND_COMMIT": None if v is L.MISSING else v},
                  a, ("the arm is stamped with a 40-hex blind commit" if ok else
                      "⛔ G-BLIND FAILED: the stamp is ABSENT or not a 40-hex "
                      "sha. A commit cannot name its own hash, so the freeze "
                      "commit must be followed by a stamping commit BEFORE any "
                      "real cell launches."))


def gate_recon(spec, cell) -> dict:
    """`RECON` — the summary's own statistics reproduce from the raw records.
    ⚠️ Accumulated with `fsum` on purpose: a witness that shares the emitter's
    code path agrees by construction and witnesses nothing."""
    d = _docs(cell)
    mean, z, n, se, _ = L.paired_margin(cell.get("records") or [])
    we = L.winrate_elo(cell.get("records") or [])
    checks, bad = {}, []
    for label, addr, mine in (
            ("paired_mean_margin", "summary:paired_mean_margin", mean),
            ("paired_z", "summary:paired_z", z),
            ("n_paired", "summary:n_paired", n),
            ("winrate", "summary:winrate", we["winrate"]),
            ("avg_diff", "summary:avg_diff", we["avg_diff"])):
        theirs, a = L.resolve(d, addr)
        theirs = None if theirs is L.MISSING else theirs
        ok = L.recon_close(theirs, mine)
        checks[label] = {"summary": theirs, "recomputed": mine, "ok": ok,
                         "address": a}
        if not ok:
            bad.append(f"{label}: summary {theirs!r} vs recomputed {mine!r}")
    return L.gate("RECON", not bad, checks, "summary:* vs records/*",
                  ("the summary reproduces from the raw records" if not bad else
                   "⛔ RECON FAILED: " + "; ".join(bad)))


#: ⛔ ORDER MATTERS ONLY FOR READABILITY — every gate runs, always. `ABSENT` is
#: `FAIL` at each of them, so an empty archive fails every one rather than
#: skipping to a vacuous pass.
GATES = (gate_scope, gate_witness, gate_singlevar, gate_arb_off, gate_leaf,
         gate_budget, gate_rules, gate_backend, gate_exact, gate_wheel,
         gate_host, gate_paired, gate_blind, gate_recon)


def adjudicate_cell(spec, cell) -> dict:
    gates = [g(spec, cell) for g in GATES]
    failed = [g["gate"] for g in gates if not g["ok"]]
    recs = cell.get("records") or []
    mean, z, n, se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    return {
        "cell": spec.name, "scope": spec.scope, "role": spec.role,
        "purpose": spec.purpose,
        "seed_range": [spec.seed_start, spec.seed_end],
        "frozen": {"dose": spec.dose, "mask": spec.mask, "scope": spec.scope,
                   "n_games": spec.n_games, "n_decks": spec.n_decks},
        "gates": gates, "gates_ok": not failed, "failed_gates": failed,
        "margin": {"mean_pts_per_deck": mean, "z": z, "se": se, "n_decks": n,
                   "footing": "deck-paired, per-deck mean over both seatings"},
        "elo_companion": we,
        "se_anomaly": L.se_anomaly(se, n),
        "saturation": L.saturation(we["winrate"]),
        "n4_cost": L.n4_cost_rider(cell.get("summary") or {}),
    }


#: G3-A1 (2026-08-31, statistics-blind, execution-layer): when set (via
#: --allow-dirty-rev REASON), the manifests' `-dirty` suffix is stripped BEFORE
#: the frozen G-REV gate and the override + reason land in the gate detail.
#: Licensed use ONLY for ground-truthed NON-CODE dirt: run_manifest.code_rev()
#: marks dirty on ANY `git status --porcelain` output — including untracked
#: files and measurement/ churn — while the launcher's own assert_rev
#: (SRC_CLEAN_G3.jsonl) witnessed the CODE paths clean at the pin before and
#: after every cell on both boxes. The frozen verdict is retained beside the
#: amended one; this flag never edits it.
ALLOW_DIRTY_REV_REASON = None


def adjudicate(cells_by_name: dict, pins_by_role: dict | None = None,
               smoke_mode: bool = False, specs=None,
               signature_bar_met=None) -> dict:
    specs = tuple(specs) if specs is not None else L.CELLS
    out_cells, revs, decks = {}, {}, {}
    for spec in specs:
        cell = cells_by_name.get(spec.name)
        if cell is None:
            cell = {"root": "<absent>", "manifest": None, "summary": None,
                    "records": []}
        out_cells[spec.name] = adjudicate_cell(spec, cell)
        d = _docs(cell)
        rev, _ = L.resolve(d, "manifest:config.code_rev", "manifest:code_rev")
        revs[spec.name] = (None if rev is L.MISSING else rev, spec.role)
        decks[spec.name] = sorted(L.per_deck_margins(cell.get("records") or []))

    if ALLOW_DIRTY_REV_REASON:
        revs = {n: ((None if r is None else L.split_dirty(r)[0]), role)
                for n, (r, role) in revs.items()}
    _grev = L.cross_box_rev_gate(revs, pins_by_role or {})
    if ALLOW_DIRTY_REV_REASON:
        _grev.setdefault("detail", {})["_dirty_override"] = {
            "applied": True, "reason": ALLOW_DIRTY_REV_REASON,
            "amendment": "G3-A1",
            "receipts": "SRC_CLEAN_G3.jsonl (both boxes, before+after every cell)"}
    round_gates = [_grev]
    if not smoke_mode:
        round_gates.append(L.crn_gate(decks, specs))
        # ⭐ the arms must differ in SCOPE AND NOTHING ELSE
        blocks, bad = {}, []
        for spec in specs:
            c = cells_by_name.get(spec.name) or {}
            v, _ = L.resolve(_docs(c), "manifest:config.cand_jrules_prior",
                             "manifest:cand_jrules_prior")
            blocks[spec.name] = None if v is L.MISSING else v
        doses = {n: (b or {}).get("dose") for n, b in blocks.items()
                 if isinstance(b, dict)}
        masks = {n: (b or {}).get("mask") for n, b in blocks.items()
                 if isinstance(b, dict)}
        scopes = {n: (b or {}).get("scope") for n, b in blocks.items()
                  if isinstance(b, dict)}
        if len(doses) != len(specs) or len(set(doses.values())) > 1:
            bad.append(f"the arms do not share ONE dose: {doses}")
        if len(masks) != len(specs) or len(set(masks.values())) > 1:
            bad.append(f"the arms do not share ONE mask: {masks}")
        if len(set(scopes.values())) != len(specs):
            bad.append(f"the arms do not carry DISTINCT scopes: {scopes}")
        round_gates.append(L.gate(
            "G-ARMS", not bad,
            {"doses": doses, "masks": masks, "scopes": scopes},
            "manifest:config.cand_jrules_prior (all arms)",
            ("⭐ dose and mask are identical across the arms and SCOPE is the "
             "only mover — the decomposition's single variable"
             if not bad else "⛔ G-ARMS FAILED: " + "; ".join(bad))))

    round_ok = all(g["ok"] for g in round_gates)
    cells_ok = all(c["gates_ok"] for c in out_cells.values())
    gates_ok = round_ok and cells_ok

    # ------------------------------------------------------------------ #
    # THE DUAL PRIMARY                                                     #
    # ------------------------------------------------------------------ #
    def _recs(name):
        return (cells_by_name.get(name) or {}).get("records") or []

    p1 = out_cells.get("CELL_G3_OPP", {}).get("margin", {})
    p2 = L.paired_contrast(_recs("CELL_G3_OPP"), _recs("CELL_G3_OWN"))
    branch, holm = L.branch_for_round(
        gates_ok=gates_ok, z_p1=p1.get("z"), z_p2=p2.get("z"),
        signature_bar_met=signature_bar_met)

    n_opp = L.cell_by_name("CELL_G3_OPP").n_decks
    return {
        "pair": ["measurement/s1_asymmetry_prep/DESIGN.md §6.4",
                 "measurement/s1_asymmetry_prep/READ_RULE_G3.md"],
        "round_gates": round_gates, "round_gates_ok": round_ok,
        "cells": out_cells, "cells_gates_ok": cells_ok, "gates_ok": gates_ok,
        "primary": {
            "P1": {"what": "margin(OPP vs the unmodified champion), pts/deck, "
                           "deck-paired", **p1},
            "P2": {"what": "D = margin(OPP) − margin(OWN), PER DECK on the "
                           "shared set (CRN preserved)", **p2},
            "holm": holm,
            "modelled_se_for_reference": {
                "P1": L.se_model(n_opp),
                "P2_at_rho_frozen": L.se_model_contrast(n_opp),
                "rho_frozen": L.RHO_FROZEN,
                "note": "⛔ POWER ARITHMETIC ONLY. Every branch above reads the "
                        "REALIZED se, which prices the true correlation."},
        },
        "control_ALL": {
            "what": "the in-band symmetric control — 'is this just another "
                    "dose?'. ⛔ OUTSIDE the Holm family; no branch reads it.",
            **out_cells.get("CELL_G3_ALL", {}).get("margin", {}),
        },
        "g2_signature": {
            "bar_met": signature_bar_met,
            "note": "⛔ `None` == the census was UNAVAILABLE and can never read "
                    "as met. `S1-FIRES` requires True (DESIGN §6.3/§6.4); "
                    "without it the best reachable branch is S1-MARGIN-ONLY."},
        "branch": branch,
        "consequence": L.BRANCH_CONSEQUENCE[branch],
        "riders": list(L.RIDERS_ALWAYS),
        "n4_fired_on": sorted(n for n, c in out_cells.items()
                              if (c.get("n4_cost") or {}).get("fired")),
    }


# =========================================================================== #
# SMOKE MODE                                                                   #
# =========================================================================== #
# The smoke's spec cannot come from `L.CELLS` (it is not a round arm) and must
# not be invented here (a restated knob proves nothing about the launcher), so
# `run_g3.sh` PASSES it and the value is then checked against what the harness
# actually EMITTED.

SMOKE_CELL_SYNTAX = "NAME=scope:seed_start:n_games:role"


def parse_smoke_cell(text: str) -> "L.CellSpec":
    """`SMOKE_OPP=opp:161999999500:8:local` -> a `CellSpec`.

    ⛔ The NAME must start with `SMOKE_`: only smoke archives are adjudicable in
    `--smoke-mode`, and admitting any other name would let a re-smoke at a root
    that already holds real arms adjudicate a ROUND arm under smoke rules.
    ⛔ The scope is the LAUNCHER'S REQUEST. It is not trusted — it becomes
    `G-SCOPE`'s frozen expectation, which is then checked against the EMITTED
    `manifest.json`, and `G-WITNESS`'s, which is checked against the EMITTED
    `summary.json`."""
    name, sep, rest = text.partition("=")
    if not sep:
        raise ValueError(f"--smoke-cell {text!r}: expected {SMOKE_CELL_SYNTAX}")
    parts = rest.split(":")
    if len(parts) != 4:
        raise ValueError(f"--smoke-cell {text!r}: expected {SMOKE_CELL_SYNTAX} "
                         f"(got {len(parts)} field(s) after '=')")
    scope, seed_start, n_games, role = parts
    if not name.startswith("SMOKE_"):
        raise ValueError(f"--smoke-cell {text!r}: the name must start with "
                         "'SMOKE_' — only smoke archives are adjudicable in "
                         "--smoke-mode, and a round arm must never be")
    if scope not in L.SCOPES:
        raise ValueError(f"--smoke-cell {text!r}: scope must be one of "
                         f"{L.SCOPES}")
    if role not in ("local", "laptop"):
        raise ValueError(f"--smoke-cell {text!r}: role must be local|laptop — "
                         "G-HOST proves the smoke ran on the box whose scope it "
                         "was written to exercise")
    n = int(n_games)
    if n < 2 or n % 2:
        raise ValueError(f"--smoke-cell {text!r}: n_games {n} is not an even "
                         "count of deck-paired games")
    return L.CellSpec(name=name, role=role, scope=scope,
                      seed_start=int(seed_start), n_decks=n // 2,
                      purpose="⭐ THE SMOKE — the THROWAWAY sub-range, "
                              "PRODUCTION knobs, only the game count reduced. "
                              "⛔ Buys no deck of the round and claims no band.")


#: The gates the smoke EXISTS to run. ⛔ A smoke archive legitimately fails gates
#: about the ROUND (`G-BLIND` — it is stamped with no blind commit; `G-REV` — it
#: runs at the PRE-LAUNCH commit by design; `G-PAIRED` — 8 games on the throwaway
#: range, not 1,200 on the band), so "all gates ok" is the wrong bar and would
#: make the smoke unusable. These three are the ones whose failure means the
#: LAUNCHER or the BOX is wrong:
#:   * `G-SCOPE`     — the scope was REQUESTED at the frozen dose/mask and the
#:                     emitted manifest says so, on the CANDIDATE side only;
#:   * `G-WITNESS`   — ⭐⭐ it BOUND IN PLAY, and only on the candidate. This is
#:                     the R7 witness that G1's verdict made a pre-launch
#:                     condition, and it is the whole reason the smoke is not
#:                     merely a liveness check;
#:   * `G-SINGLEVAR` — nothing else moved with it.
SMOKE_REQUIRED_GATES = ("G-SCOPE", "G-WITNESS", "G-SINGLEVAR")


def smoke_problems(v: dict) -> list[str]:
    """⛔ NON-EMPTY == the smoke FAILED == a non-zero exit, which is what makes
    `run_g3.sh`'s `|| DIE "the smoke adjudication FAILED"` REACHABLE."""
    probs: list[str] = []
    cells = v.get("cells") or {}
    knobs = v.get("resolved_scopes") or {}
    if not cells:
        probs.append(
            "⛔⛔ THE SMOKE ADJUDICATED ZERO CELLS. Nothing was read, so nothing "
            "was proven — and an exit 0 here is exactly the FPU R1 defect (an "
            "unreachable `|| DIE` in the launcher). Check that the smoke "
            "archive exists under --root, is named SMOKE_*, carries a "
            "manifest.json, and that its name matches a --smoke-cell "
            f"({SMOKE_CELL_SYNTAX}).")
    if not knobs:
        probs.append("⛔ resolved_scopes is EMPTY — the smoke's one substantive "
                     "job is to return the scope AS THE HARNESS WROTE IT, read "
                     "off the emitted manifest.json. Nothing was read.")
    for name in cells:
        k = knobs.get(name)
        if not k:
            probs.append(f"⛔ {name}: no resolved cand_jrules_prior could be "
                         "read from its manifest.json — ABSENT is FAIL")
        elif not (k.get("resolved") or {}).get("scope"):
            probs.append(f"⛔ {name}: the emitted manifest carries NO resolved "
                         "scope — the launcher did not put the knob on the wire")
    for name, c in cells.items():
        by_id = {g["gate"]: g["ok"] for g in c.get("gates", [])}
        ran = [g for g in SMOKE_REQUIRED_GATES if g in by_id]
        if not ran:
            probs.append(f"⛔ {name}: none of {SMOKE_REQUIRED_GATES} executed")
        for gid in ran:
            if not by_id[gid]:
                probs.append(
                    f"⛔ {name}: {gid} FAILED. " + {
                        "G-WITNESS":
                            "⛔⛔ THE SCOPE KNOB DID NOT BIND IN PLAY on the "
                            "candidate, or it bound on the OPPONENT TOO, or the "
                            "R7 expansion-census witness is not emitted by this "
                            "box's build. A round launched over this is "
                            "champion-vs-champion wearing a candidate's name.",
                        "G-SCOPE":
                            "The emitted manifest does not carry the scope this "
                            "box was told to smoke, at the frozen dose/mask.",
                    }.get(gid, "Something else moved alongside the scope."))
    return probs


# =========================================================================== #
# SELFTEST                                                                     #
# =========================================================================== #

FIXTURE = HERE / "selftest_fixture_g3"


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
        if not isinstance(cur, dict):
            return
    cur.pop(parts[-1], None)


#: ⭐ THE NAMED DEFECTS — one per gate whose failure would otherwise never be
#: observed. Each must (a) fire its own gate and (b) void the round.
#: ⛔⛔ The first three are this design's most dangerous failure mode in its three
#: disguises: an arm whose scope knob NEVER BOUND is champion-vs-champion, moves
#: no leaf hash, sits inside every rail, and reads as a clean credible null.
FIXTURE_DEFECTS = (
    # ⚠️ BOTH emitted addresses must go: the R7 build writes the block twice, and
    # a defect that removes only one proves the FALLBACK works, not the gate.
    ("witness_absent_r7_build_not_on_this_box",
     lambda c: [_del(c["CELL_G3_OPP"]["summary"], k) for k in
                ("jr_expansions", "cand_jr_expansions", "opp_jr_expansions")],
     "G-WITNESS"),
    ("knob_never_bound_candidate_boosted_zero",
     lambda c: _set(c["CELL_G3_OPP"]["summary"],
                    "jr_expansions.candidate.boosted", 0),
     "G-WITNESS"),
    ("knob_bound_on_BOTH_sides",
     lambda c: _set(c["CELL_G3_OWN"]["summary"],
                    "jr_expansions.opponent.boosted", 4211),
     "G-WITNESS"),
    ("boost_escaped_its_scope",
     lambda c: _set(c["CELL_G3_OPP"]["summary"],
                    "jr_expansions.candidate.boosted",
                    c["CELL_G3_OPP"]["summary"]["jr_expansions"]["candidate"]
                    ["total"] + 1),
     "G-WITNESS"),
    ("config_echo_only_cand_jrules_prior_null",
     lambda c: _set(c["CELL_G3_ALL"]["manifest"],
                    "config.cand_jrules_prior", None),
     "G-SCOPE"),
    ("wrong_dose_on_the_wire",
     lambda c: _set(c["CELL_G3_OWN"]["manifest"],
                    "config.cand_jrules_prior.dose", 0.5),
     "G-SCOPE"),
    ("scope_silently_defaulted_to_all",
     lambda c: _set(c["CELL_G3_OPP"]["manifest"],
                    "config.cand_jrules_prior.scope", "all"),
     "G-SCOPE"),
    ("a_second_variable_moved",
     lambda c: _set(c["CELL_G3_OPP"]["manifest"], "config.champion.tau_p", 8.0),
     "G-SINGLEVAR"),
    ("tie_arbiter_left_armed",
     lambda c: _set(c["CELL_G3_ALL"]["manifest"], "config.cand_tiearb",
                    {"enabled": True, "mode": "b64", "B": 64, "J": 4}),
     "G-ARB-OFF"),
    ("stale_budget_11008",
     lambda c: (_set(c["CELL_G3_OPP"]["manifest"], "config.champion.k_dets", 8),
                _set(c["CELL_G3_OPP"]["manifest"], "config.champion.total_sims",
                     11008)),
     "G-BUDGET"),
    ("a_leaf_change_was_smuggled_in",
     lambda c: _set(c["CELL_G3_OWN"]["manifest"], "config.cand_leaf_hash",
                    "deadbeefdeadbeef"),
     "G-LEAF"),
    ("rules_profile_defaulted_to_walled",
     lambda c: _set(c["CELL_G3_ALL"]["manifest"], "rules_profile.name",
                    "walled"),
     "G-RULES"),
    ("mixed_rev_round",
     lambda c: (_set(c["CELL_G3_OWN"]["manifest"], "config.code_rev", "cccccccc"),
                _set(c["CELL_G3_OWN"]["manifest"], "code_rev", "cccccccc")),
     "G-REV"),
    ("arm_ran_on_the_wrong_box",
     lambda c: _set(c["CELL_G3_OWN"]["manifest"], "host", "Doctor"),
     "G-HOST"),
    ("recon_disagrees_with_the_summary",
     lambda c: _set(c["CELL_G3_OPP"]["summary"], "paired_mean_margin", 99.0),
     "RECON"),
    ("a_deck_was_played_at_one_seat_only",
     lambda c: c["CELL_G3_OPP"]["records"].pop(),
     "G-PAIRED"),
    ("crn_broken_own_walked_a_different_range",
     lambda c: [r.__setitem__("seed", r["seed"] + 10_000)
                for r in c["CELL_G3_OWN"]["records"]],
     "G-CRN"),
    ("the_blind_stamp_is_missing",
     lambda c: [_del(c["CELL_G3_ALL"]["manifest"], k) for k in
                ("stamps", "config.stamps")],
     "G-BLIND"),
)


def selftest() -> int:
    problems = list(L.sanity_check())
    grid = L.branch_grid(step=0.05)
    if not grid["all_reachable"]:
        problems.append(f"branch grid: unreachable {grid['unreachable']}")

    # ⛔ ABSENT is FAIL, at every gate, on an EMPTY archive.
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
    if v["branch"] != "S1-VOID-INSTRUMENT":
        problems.append(f"an all-empty round read {v['branch']}, not a void")

    # Holm's own arithmetic
    h = L.holm(3.0, 1.0)
    if not h["P1_clears"] or h["P2_clears"]:
        problems.append(f"holm(3.0, 1.0) misread: {h['P1_clears']}/"
                        f"{h['P2_clears']}")
    h = L.holm(2.1, 2.1)
    if h["P1_clears"] or h["P2_clears"]:
        problems.append("holm(2.1, 2.1): both legs cleared, but 2.1 < 2.2414 "
                        "and Holm is STEP-DOWN — the ladder must stop at step 1")
    h = L.holm(2.3, 2.0)
    if not (h["P1_clears"] and h["P2_clears"]):
        problems.append("holm(2.3, 2.0): step 1 clears at 2.2414 and step 2 at "
                        "1.96, so BOTH legs should clear")

    report: dict = {}
    fx = FIXTURE
    if fx.is_dir() and (fx / "SPECS.json").is_file():
        specs = fixture_specs(fx)
        frozen = {c.name: c for c in L.CELLS}
        if sorted(s.name for s in specs) != sorted(frozen):
            problems.append("the fixture's arm NAMES differ from the frozen plan")
        for s in specs:
            f = frozen.get(s.name)
            if f is None:
                continue
            for field in ("role", "scope"):
                if getattr(s, field) != getattr(f, field):
                    problems.append(f"fixture {s.name}.{field} = "
                                    f"{getattr(s, field)!r} != frozen "
                                    f"{getattr(f, field)!r} — a fixture may "
                                    "differ from the round in SCALE ONLY")
        cells = {p.name: load_cell(p) for p in sorted(fx.iterdir())
                 if p.is_dir() and (p / "manifest.json").is_file()}
        pin = (fx / "PINNED_SRC_REV").read_text().strip()
        pins = {"local": pin, "laptop": pin}
        vv = adjudicate(cells, pins_by_role=pins, specs=specs,
                        signature_bar_met=True)
        report["healthy"] = {
            "branch": vv["branch"],
            "failed_round_gates": [g["gate"] for g in vv["round_gates"]
                                   if not g["ok"]],
            "failed_cell_gates": {n: c["failed_gates"]
                                  for n, c in vv["cells"].items()
                                  if c["failed_gates"]},
            "P1_z": vv["primary"]["P1"].get("z"),
            "P2_z": vv["primary"]["P2"].get("z"),
        }
        if report["healthy"]["failed_round_gates"]:
            problems.append("the HEALTHY fixture failed round gate(s): "
                            f"{report['healthy']['failed_round_gates']}")
        if report["healthy"]["failed_cell_gates"]:
            problems.append("the HEALTHY fixture failed cell gate(s): "
                            f"{report['healthy']['failed_cell_gates']}")
        # ⭐ the fixture is SHAPED so the round FIRES — and the same records read
        # with an unavailable G2 census must fall to S1-MARGIN-ONLY, which is the
        # DESIGN §10.4 rule and the one most likely to be quietly skipped.
        if vv["branch"] != "S1-FIRES":
            problems.append(f"the HEALTHY fixture read {vv['branch']}, want "
                            "S1-FIRES")
        vno = adjudicate(cells, pins_by_role=pins, specs=specs,
                         signature_bar_met=None)
        if vno["branch"] != "S1-MARGIN-ONLY":
            problems.append("with the G2 census UNAVAILABLE the healthy fixture "
                            f"read {vno['branch']}, want S1-MARGIN-ONLY")
        report["g2_unavailable"] = {"branch": vno["branch"]}

        # ⭐ THE DEFECT VARIANTS — a gate nobody has seen FAIL is untested.
        for label, mutate, want_gate in FIXTURE_DEFECTS:
            mut = {n: json.loads(json.dumps(c, default=str))
                   for n, c in cells.items()}
            mutate(mut)
            m = adjudicate(mut, pins_by_role=pins, specs=specs,
                           signature_bar_met=True)
            fired = ([g["gate"] for g in m["round_gates"] if not g["ok"]]
                     + sorted({x for c in m["cells"].values()
                               for x in c["failed_gates"]}))
            report[label] = {"branch": m["branch"], "failed": fired}
            if want_gate not in fired:
                problems.append(f"defect {label!r} did NOT fire {want_gate} "
                                f"(fired: {fired})")
            if m["branch"] != "S1-VOID-INSTRUMENT":
                problems.append(f"defect {label!r} did not VOID the round "
                                f"(read {m['branch']})")
    else:
        problems.append("⚠️ selftest_fixture_g3/ is not populated — the "
                        "adjudicator has never been run against a shaped "
                        "archive. This is a BUILD DEBT, and it is reported "
                        "rather than hidden.")

    print(json.dumps({
        "problems": problems, "fixture": report, "branch_grid": grid,
        "frozen": {"band": L.BAND, "dose": L.JR_DOSE, "mask": L.JR_MASK,
                   "budget": [L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS],
                   "holm_z": list(L.HOLM_Z), "leaf": L.LEAF_HASH},
        "power": {
            "P1_2sigma_bar_pts_per_deck": 2 * L.se_model(600),
            "P1_holm_bar_pts_per_deck": L.HOLM_Z[0] * L.se_model(600),
            "P2_2sigma_bar_pts_per_deck": 2 * L.se_model_contrast(600),
            "ALL_2sigma_bound_pts_per_deck": 2 * L.se_model(400),
            "sigma_elo_1200": L.sigma_elo(1200),
            "sigma_elo_800": L.sigma_elo(800),
            "power_P1_at_plus1": L.power_at(1.0, L.se_model(600)),
            "power_P2_at_plus2": L.power_at(2.0, L.se_model_contrast(600)),
        }}, indent=2, default=str))
    print(f"\nSELFTEST: {'PASS' if not problems else 'FAIL'} "
          f"({len(problems)} problem(s))")
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", type=Path,
                    help="directory holding one subdir per arm")
    ap.add_argument("--pin-local", type=Path, help="local box's PINNED_SRC_REV")
    ap.add_argument("--pin-laptop", type=Path, help="laptop's PINNED_SRC_REV")
    ap.add_argument("--g2-signature", choices=("met", "not-met", "unavailable"),
                    default="unavailable",
                    help="G2's verdict (DESIGN §6.3). ⛔ DEFAULT IS "
                         "'unavailable', which can never read as met: "
                         "`S1-FIRES` requires the census in hand, and an "
                         "absent census must not silently license the "
                         "mechanism story (DESIGN §10.4).")
    ap.add_argument("--smoke-mode", action="store_true",
                    help="structural keys ONLY — ⛔ the smoke emits NO outcome key")
    ap.add_argument("--smoke-cell", action="append", default=[],
                    metavar=SMOKE_CELL_SYNTAX,
                    help="⭐ the smoke's own synthetic cell spec, PASSED BY "
                         "run_g3.sh. Required by (and only legal with) "
                         "--smoke-mode. Repeatable.")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--allow-dirty-rev", default=None, metavar="REASON",
                    help="G3-A1: strip -dirty from manifest code_revs before "
                         "G-REV, recording REASON in the gate detail. ONLY for "
                         "ground-truthed non-code dirt with SRC_CLEAN receipts.")
    args = ap.parse_args()
    global ALLOW_DIRTY_REV_REASON
    ALLOW_DIRTY_REV_REASON = args.allow_dirty_rev

    if args.selftest:
        return selftest()
    if not args.root:
        ap.error("--root or --selftest")
    if args.smoke_cell and not args.smoke_mode:
        ap.error("--smoke-cell is only legal with --smoke-mode")

    # ⭐⭐ THE TWO SCANS ARE DISJOINT BY CONSTRUCTION (the FPU R1 shape).
    specs = None
    if args.smoke_mode:
        if not args.smoke_cell:
            ap.error("--smoke-mode requires at least one --smoke-cell "
                     f"{SMOKE_CELL_SYNTAX} — without a spec there is nothing to "
                     "adjudicate the smoke archive AGAINST, and the read would "
                     "vacuously exit 0 (the FPU R1 defect)")
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

    sig = {"met": True, "not-met": False, "unavailable": None}[args.g2_signature]
    v = adjudicate(cells, pins_by_role=pins, smoke_mode=args.smoke_mode,
                   specs=specs, signature_bar_met=sig)

    if args.smoke_mode:
        # ⛔⛔ THE SMOKE EMITS NO OUTCOME KEY. The gate is a READ surface firing on
        # forbidden OUTCOME keys AT ANY DEPTH — a gate's `detail` and `why` carry
        # the values it read, and `RECON`'s detail is literally the five outcome
        # statistics under their own names. So a smoke record keeps only
        # `{gate, ok, address}` per gate, plus the RESOLVED SCOPE and the
        # WITNESS CENSUS, which are CONFIG and PLUMBING respectively and are the
        # smoke's whole substantive job.
        def _bare(g):
            return {"gate": g["gate"], "ok": g["ok"], "address": g["address"]}

        def _scope(c):
            d = next((g["detail"] for g in c["gates"]
                      if g["gate"] == "G-SCOPE"), None)
            if not isinstance(d, dict):
                return None
            out = {k: d.get(k) for k in ("resolved", "frozen",
                                         "opponent_jrules_prior")}
            w = next((g["detail"] for g in c["gates"]
                      if g["gate"] == "G-WITNESS"), None)
            if isinstance(w, dict):
                out["jr_expansions"] = {k: w.get(k) for k in
                                        ("candidate", "opponent", "coverage",
                                         "scope_denominator", "addresses")}
            return out

        v = {"smoke_mode": True,
             "round_gates": [_bare(g) for g in v["round_gates"]],
             "round_gates_ok": v["round_gates_ok"],
             "cells": {n: {"gates": [_bare(g) for g in c["gates"]],
                           "gates_ok": c["gates_ok"],
                           "failed_gates": c["failed_gates"]}
                       for n, c in v["cells"].items()},
             "resolved_scopes": {n: _scope(c) for n, c in v["cells"].items()},
             "smoke_specs": [{"name": s.name, "scope": s.scope,
                              "seed_start": s.seed_start,
                              "n_games": s.n_games} for s in (specs or ())],
             "note": "⭐ the smoke's two substantive jobs: it returns the "
                     "RESOLVED SCOPE as the harness actually wrote it (the "
                     "PG-D7..D9 lesson), and the PLAY-DERIVED jr_expansions "
                     "census proving the scope BOUND on the candidate and NOT "
                     "on the opponent (the R7 witness G1's verdict made a "
                     "pre-launch condition)."}
        v["smoke_problems"] = smoke_problems(v)
        v["smoke_ok"] = not v["smoke_problems"]

    txt = json.dumps(v, indent=2, default=str)
    if args.out:
        args.out.write_text(txt)
        print(f"[analyze_g3] wrote {args.out}")
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
