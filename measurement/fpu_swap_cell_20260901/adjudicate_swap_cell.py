#!/usr/bin/env python3
"""`adjudicate_swap_cell` — THE FPU-SWAP CELL's ADJUDICATOR.

⛔ **THE PAIR IS LAW.** [`PREREG.md`](PREREG.md). If this file disagrees with
it, **this file is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 games exist at freeze.**

The order of business:

  1. Every gate in `GATES`, on the ONE cell (`PREREG.md` §5). `ABSENT` is
     `FAIL`, never a skip and never a default. Every gate prints WHICH
     DOCUMENT and WHICH ADDRESS answered.
  2. The branch ladder (`PREREG.md` §4.2), on the cell's own realized SE.
  3. `--smoke-mode`: adjudicate a throwaway `SMOKE_*` archive against the four
     required gates only (`SMOKE_REQUIRED_GATES`) and exit NONZERO on an empty
     read — the `fpu_resurrection_prep` R1 defect (an unreachable `|| DIE`
     because `--smoke-mode` silently adjudicated zero cells) is guarded
     against explicitly rather than assumed inherited.
  4. `--selftest`: the library's own arithmetic, the branch grid, the shipped
     REAL-EMITTER fixture, and the named DEFECT variants.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import screen_lib as L  # noqa: E402


# =========================================================================== #
# LOADING                                                                      #
# =========================================================================== #

def load_cell(root: Path) -> dict:
    """Read one archive. Missing documents are recorded as `None` and reach the
    gates as ABSENT — this never raises past a gate."""
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


def read_claimed_band() -> int | None:
    """The band the ORCHESTRATOR claimed, parsed from the sibling
    `BAND_CLAIMED` file (no extension — the placeholder is `.placeholder`).
    `None` if that file does not exist yet (pre-launch state, or `--smoke`)."""
    p = HERE / "BAND_CLAIMED"
    if not p.is_file():
        return None
    m = re.search(r"BAND CLAIMED:\s*(\d+)", p.read_text())
    return int(m.group(1)) if m else None


# =========================================================================== #
# THE GATES — PREREG.md §5                                                    #
# =========================================================================== #

def gate_fpu(cell) -> dict:
    return L.fpu_knob_gate(cell.get("manifest") or {})


def gate_fpu_twosided(cell) -> dict:
    return L.fpu_twosided_gate(cell.get("manifest") or {})


def gate_arb_asym(cell) -> dict:
    return L.arb_asymmetry_gate(cell.get("manifest") or {})


def gate_arb_fired(cell) -> dict:
    return L.arb_fired_gate(cell.get("summary") or {})


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


def gate_budget(cell) -> dict:
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
            bad.append(f"{side}: {k} x {s} != {t}")
    return L.gate("G-BUDGET", not bad, rows,
                  "manifest:config.{champion,opponent}.*",
                  (f"both sides run k{L.K_DETS} x {L.SIMS_PER_DET} = "
                   f"{L.TOTAL_SIMS}" if not bad else
                   "⛔ G-BUDGET FAILED: " + "; ".join(bad)))


def gate_exact(cell) -> dict:
    return _simple("G-EXACT", cell, [
        (("manifest:config.endgame.exact_k",), L.EXACT_K, "exact_k"),
        (("manifest:config.endgame.mode",), L.EXACT_MODE, "mode"),
    ], "manifest:config.endgame.*")


def gate_rules(cell) -> dict:
    return _simple("G-RULES", cell, [
        (("manifest:rules_profile.name",), L.RULES_PROFILE, "rules_profile.name"),
        (("manifest:rules_profile.r9_env_ok",), True, "r9_env_ok"),
        (("manifest:rules_profile.r9_env_observed",), True, "r9_env_observed"),
    ], "manifest:rules_profile.* (⚠️ R9 is env-latched at IMPORT)")


def gate_backend(cell) -> dict:
    return _simple("G-BACKEND", cell, [
        (("manifest:config.backend.name",), L.BACKEND, "name"),
        (("manifest:config.backend.requested",), L.BACKEND, "requested"),
        (("manifest:config.backend.mixed_builds", "manifest:mixed_builds"),
         lambda v: v is False, "mixed_builds"),
    ], "manifest:config.backend.*")


def gate_wheel(cell) -> dict:
    return _simple("G-WHEEL", cell, [
        (("manifest:carc_rs_build",),
         lambda v: bool(v) and "unavailable" not in str(v), "carc_rs_build"),
        (("manifest:carc_rs_binary_sha",), lambda v: bool(v), "carc_rs_binary_sha"),
        (("manifest:mixed_builds",), lambda v: v is False, "mixed_builds"),
    ], "manifest — carc_rs_version is a constant, not a discriminator")


def gate_leaf(cell) -> dict:
    d = _docs(cell)
    ch, ca = L.resolve(d, "manifest:config.cand_leaf_hash")
    oh, oa = L.resolve(d, "manifest:config.opp_leaf_hash",
                       "manifest:config.opponent.leaf_hash")
    same = (ch is not L.MISSING and ch == oh)
    right = ch == L.LEAF_HASH
    ok = same and right
    return L.gate("G-LEAF", ok,
                  {"cand_leaf_hash": None if ch is L.MISSING else ch,
                   "opp_leaf_hash": None if oh is L.MISSING else oh,
                   "expected": L.LEAF_HASH},
                  ca or oa,
                  ("both sides carry the same leaf" if ok else
                   f"⛔ G-LEAF FAILED: cand={ch!r} opp={oh!r} expected {L.LEAF_HASH!r}"))


def gate_band(cell, claimed_band: int | None) -> dict:
    d = _docs(cell)
    start, a1 = L.resolve(d, "manifest:config.band_seed_start",
                          "manifest:band_seed_start")
    ndecks, a2 = L.resolve(d, "manifest:config.n_decks", "manifest:n_decks")
    seat, a3 = L.resolve(d, "manifest:config.seatings_per_deck",
                         "manifest:seatings_per_deck")
    bad = []
    if claimed_band is None:
        bad.append("no BAND_CLAIMED file found — the round has not been "
                   "claimed yet; a real cell may not be adjudicated as such")
    if start is L.MISSING:
        bad.append("band_seed_start ABSENT")
    elif claimed_band is not None and int(start) != claimed_band:
        bad.append(f"band_seed_start {start} != claimed {claimed_band}")
    if ndecks is not L.MISSING and int(ndecks) != 400:
        bad.append(f"n_decks {ndecks} != frozen 400")
    if seat is not L.MISSING and int(seat) != 2:
        bad.append(f"seatings_per_deck {seat} != 2")
    return L.gate("G-BAND", not bad,
                  {"band_seed_start": None if start is L.MISSING else start,
                   "claimed_band": claimed_band,
                   "n_decks": None if ndecks is L.MISSING else ndecks,
                   "seatings_per_deck": None if seat is L.MISSING else seat},
                  a1, ("on the claimed band with 400 decks x 2 seatings"
                       if not bad else "⛔ G-BAND FAILED: " + "; ".join(bad)))


def gate_decks(cell, claimed_band: int | None) -> dict:
    recs = cell.get("records") or []
    by_deck = L._by_deck(recs)
    seeds = sorted(by_deck)
    half = sorted(s for s, v in by_deck.items() if not (0 in v and 1 in v))
    n_common = len(L.per_deck_margins(recs))
    out_of_range = []
    if claimed_band is not None:
        lo, hi = claimed_band, claimed_band + 399
        out_of_range = [s for s in seeds if not (lo <= s <= hi)]
    bad = []
    if half:
        bad.append(f"{len(half)} deck(s) played at ONE seat only")
    if n_common != 400:
        bad.append(f"n_common {n_common} != frozen 400")
    if out_of_range:
        bad.append(f"{len(out_of_range)} seed(s) outside the claimed range")
    return L.gate("G-DECKS", not bad,
                  {"n_seeds": len(seeds), "n_common": n_common,
                   "half_played_decks": half[:20],
                   "out_of_range": out_of_range[:20]},
                  "raw seed*_a*.json",
                  ("every seed inside range, both seatings present, "
                   "n_common == 400" if not bad else
                   "⛔ G-DECKS FAILED: " + "; ".join(bad)))


def gate_n(cell) -> dict:
    d = _docs(cell)
    n, a1 = L.resolve(d, "summary:n")
    nf, a2 = L.resolve(d, "summary:n_failed", "manifest:n_failed")
    nc = len(L.per_deck_margins(cell.get("records") or []))
    bad, notes = [], []
    if n is L.MISSING:
        bad.append("summary.n ABSENT")
    elif int(n) != 800:
        bad.append(f"n {n} != frozen 800 games")
    if nf is L.MISSING:
        bad.append("n_failed ABSENT")
    else:
        rate = float(nf) / 800.0
        if float(nf) > 0:
            notes.append(f"⚠️ n_failed = {nf} ({rate:.4%}) — REPORTED, never "
                         "silently absorbed")
        if rate >= L.FAILURE_RATE_VOID:
            bad.append(f"failure rate {rate:.4%} >= {L.FAILURE_RATE_VOID:.0%}")
    floor = L.N_COMMON_FLOOR_FRACTION * 400
    if nc < floor:
        bad.append(f"n_common {nc} < 80% of 400 ({floor:.0f})")
    return L.gate("G-N", not bad,
                  {"n": None if n is L.MISSING else n, "frozen_n_games": 800,
                   "n_failed": None if nf is L.MISSING else nf, "n_common": nc,
                   "n_common_floor": floor, "notes": notes},
                  "summary.json",
                  ("; ".join(notes) or "n, n_failed, n_common at the frozen plan")
                  if not bad else "⛔ G-N FAILED: " + "; ".join(bad))


def gate_sat(cell) -> dict:
    d = _docs(cell)
    wr, a = L.resolve(d, "summary:winrate")
    if wr is L.MISSING:
        return L.gate("G-SAT", False, {"winrate": None}, None,
                      "⛔ winrate ABSENT — ABSENT is FAIL")
    lo, hi = L.SAT_BAND
    ok = lo <= float(wr) <= hi
    return L.gate("G-SAT", ok, {"winrate": wr, "band": list(L.SAT_BAND)}, a,
                  ("inside the rail" if ok else
                   f"⛔ winrate {wr} outside {L.SAT_BAND}"))


def gate_host(cell) -> dict:
    v, a = L.resolve(_docs(cell), "manifest:host")
    ok, why = L.host_matches_box(None if v is L.MISSING else v, "laptop")
    return L.gate("G-HOST", ok, {"host": None if v is L.MISSING else v,
                                 "frozen_role": "laptop"}, a, why)


def gate_rev(cell, pinned_src_rev: str | None) -> dict:
    v, a = L.resolve(_docs(cell), "manifest:code_rev")
    if v is L.MISSING:
        return L.gate("G-REV", False, {"code_rev": None,
                                       "PINNED_SRC_REV": pinned_src_rev},
                      a, "⛔ code_rev ABSENT — ABSENT is FAIL")
    ok, why = L.rev_matches(v, pinned_src_rev)
    return L.gate("G-REV", ok, {"code_rev": v, "PINNED_SRC_REV": pinned_src_rev},
                  a, why)


def gate_recon(cell) -> dict:
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


#: Gates that need no extra context beyond the loaded cell.
_PLAIN_GATES = (gate_fpu, gate_fpu_twosided, gate_arb_asym, gate_arb_fired,
                gate_budget, gate_exact, gate_rules, gate_backend, gate_wheel,
                gate_leaf, gate_n, gate_sat, gate_host, gate_recon)


def adjudicate_cell(cell: dict, claimed_band: int | None,
                     pinned_src_rev: str | None) -> dict:
    gates = [g(cell) for g in _PLAIN_GATES]
    gates.append(gate_band(cell, claimed_band))
    gates.append(gate_decks(cell, claimed_band))
    gates.append(gate_rev(cell, pinned_src_rev))
    blind, ba = L.resolve(_docs(cell), "manifest:BLIND_COMMIT")
    gates.append(L.gate("G-BLIND", blind is not L.MISSING and L.is_hex40(blind),
                        {"BLIND_COMMIT": None if blind is L.MISSING else blind},
                        ba, "a single 40-hex BLIND_COMMIT is stamped into the "
                            "manifest — a read that was not blind is not a read"
                            if blind is not L.MISSING and L.is_hex40(blind) else
                            "⛔ G-BLIND FAILED: BLIND_COMMIT absent or malformed"))

    gates_ok = all(g["ok"] for g in gates)
    m, z, n, se, per_deck = L.paired_margin(cell.get("records") or [])
    we = L.winrate_elo(cell.get("records") or [])
    branch = L.branch_for_cell(m, se, gates_ok=gates_ok)
    riders = list(L.RIDERS_ALWAYS) + list(
        L.RIDERS_SWAP_KILLED if branch == "SWAP-KILLED" else
        L.RIDERS_SWAP_SURPRISE if branch == "SWAP-SURPRISE" else
        L.RIDERS_SWAP_UNRESOLVED if branch == "SWAP-UNRESOLVED" else ())

    out = {
        "cell": "SWAP", "gates": gates, "gates_ok": gates_ok,
        "failed_gates": [g["gate"] for g in gates if not g["ok"]],
        "stats": {"M": m, "z": z, "n_paired": n, "se": se,
                  "UB95_M": None if (m is None or se is None) else m + 2 * se,
                  "LB95_M": None if (m is None or se is None) else m - 2 * se,
                  "arb_advantage": None if m is None else -m,
                  "LB95_arb_advantage": None if (m is None or se is None)
                                        else -(m + 2 * se),
                  "UB95_arb_advantage": None if (m is None or se is None)
                                        else -(m - 2 * se),
                  "bar_swap": L.BAR_SWAP},
        "secondary_elo": {
            "elo": we["elo"], "footing": we["elo_footing"],
            "sigma_1_paired": we["elo_sig_1sigma_paired"],
            "winrate": we["winrate"], "W": we["W"], "D": we["D"], "L": we["L"],
            "warning": "⛔ NEVER quoted bare; the deck-paired MARGIN carries "
                       "the branch, this is the SECONDARY only.",
        },
        "se_anomaly": L.se_anomaly(se, max(1, n)),
        "branch": branch, "riders": riders,
        "_per_deck": per_deck,
    }
    if branch == "U-VOID-INSTRUMENT":
        out["void_banner"] = ("⛔ U-VOID-INSTRUMENT — the instrument, not the "
                              "world. Statistics above are a COMPANION TABLE "
                              "only; no reading is taken.")
    return out


def adjudicate(cell: dict, claimed_band: int | None = None,
               pinned_src_rev: str | None = None) -> dict:
    result = adjudicate_cell(cell, claimed_band, pinned_src_rev)
    return {
        "round": "fpu_swap_cell (1 cell, 1 band)",
        "pair": ["measurement/fpu_swap_cell_20260901/PREREG.md"],
        "budget": {"k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
                   "total_sims": L.TOTAL_SIMS},
        "bar_swap": L.BAR_SWAP,
        "power_table": {
            str(d): L.power_at(d, L.SE_400) for d in
            (L.BAR_SWAP, L.FUNDING_BRIEF_ARB_ADVANTAGE_PRIOR, 2.0,
             L.ARITHMETIC_RECONSTRUCTION_ARB_ADVANTAGE, 3.0)
        },
        "result": result,
        "prior_art": L.PRIOR_ART,
    }


# =========================================================================== #
# SMOKE MODE                                                                   #
# =========================================================================== #

#: The gates the smoke exists to run — failure of any means the LAUNCHER, not
#: the world, is wrong. ⛔ A smoke archive legitimately fails gates about the
#: REAL ROUND (G-BLIND — unstamped by design; G-N — 8 games not 800; G-BAND/
#: G-DECKS — the throwaway range, not the claimed band), so "all gates ok" is
#: the wrong bar for a smoke.
SMOKE_REQUIRED_GATES = ("G-FPU", "G-FPU-TWOSIDED", "G-ARB-ASYM", "G-ARB-FIRED")


def smoke_problems(cell: dict) -> list[str]:
    """Non-empty == the smoke FAILED == a nonzero exit."""
    probs: list[str] = []
    if not cell.get("manifest"):
        probs.append("⛔⛔ NO manifest.json FOUND — nothing was read, so "
                     "nothing was proven. Check --root and that the harness "
                     "actually ran.")
        return probs
    gates = [g(cell) for g in _PLAIN_GATES]
    by_id = {g["gate"]: g for g in gates}
    ran = [gid for gid in SMOKE_REQUIRED_GATES if gid in by_id]
    if not ran:
        probs.append(f"⛔ none of {SMOKE_REQUIRED_GATES} executed — the "
                     "adjudicator's gate wiring itself is broken")
    for gid in ran:
        g = by_id[gid]
        if not g["ok"]:
            probs.append(f"⛔ {gid} FAILED: {g['why']}")
    if not any(gid in by_id for gid in SMOKE_REQUIRED_GATES):
        probs.append("⛔⛔ THE SMOKE ADJUDICATED ZERO REQUIRED GATES — the "
                     "fpu_resurrection_prep R1 defect (an unreachable "
                     "|| DIE because the smoke silently adjudicated nothing).")
    return probs


# =========================================================================== #
# SELFTEST                                                                     #
# =========================================================================== #

FIXTURE_DEFECTS = (
    ("cand_arb_also_armed",
     lambda m: m["manifest"].setdefault("cand_tiearb", {}).update(enabled=True,
        B=64, J=4, mode="argmax", salt="tiearb2-deploy-v1", eps=0.0,
        phase_gate="all"),
     "G-ARB-ASYM"),
    ("opp_arb_wrong_B",
     lambda m: m["manifest"]["opp_tiearb"].update(B=32),
     "G-ARB-ASYM"),
    ("opp_arb_never_fired",
     lambda m: m["summary"].update(opp_tiearb_fired_plies_total=0),
     "G-ARB-FIRED"),
    ("cand_arb_fired_in_play",
     lambda m: m["summary"].update(tiearb_fired_plies_total=3, tiearb_games=8),
     "G-ARB-FIRED"),
    ("fpu_never_requested",
     lambda m: m["manifest"]["config"]["cand_search"].pop("fpu_reduction", None),
     "G-FPU"),
    ("fpu_wrong_dose",
     lambda m: m["manifest"]["config"]["cand_search"].update(fpu_reduction=0.4),
     "G-FPU"),
    ("fpu_never_bound",
     lambda m: m["manifest"]["config"]["champion"].update(fpu_reduction=None),
     "G-FPU-TWOSIDED"),
    ("opp_carries_fpu_too",
     lambda m: m["manifest"]["config"]["opponent"]["champ_cfg"].update(
         fpu_reduction=0.2),
     "G-FPU-TWOSIDED"),
    ("stale_budget",
     lambda m: (m["manifest"]["config"]["champion"].update(k_dets=8,
                                                            total_sims=11008)),
     "G-BUDGET"),
    ("leaf_hashes_differ",
     lambda m: m["manifest"]["config"].update(opp_leaf_hash="deadbeef"),
     "G-LEAF"),
    ("wrong_host",
     lambda m: m["manifest"].update(host="Doctor"),
     "G-HOST"),
    ("recon_disagrees",
     lambda m: m["summary"].update(paired_mean_margin=99.0),
     "RECON"),
    ("a_deck_played_one_seat_only",
     lambda m: m["records"].pop(),
     "G-DECKS"),
)


def _deep_copy_cell(cell: dict) -> dict:
    return json.loads(json.dumps(cell))


def selftest() -> int:
    problems = list(L.sanity_check())
    grid_ok = True
    for m10 in range(-500, 501, 5):
        M = m10 / 100.0
        for se10 in (10, 30, 50, 69, 90, 140):
            se = se10 / 100.0
            b = L.branch_for_cell(M, se, gates_ok=True)
            ub95 = M + 2 * se
            lb95 = M - 2 * se
            expect = ("SWAP-KILLED" if ub95 <= -L.BAR_SWAP else
                      "SWAP-SURPRISE" if lb95 > 0 else "SWAP-UNRESOLVED")
            if b != expect:
                grid_ok = False
                problems.append(f"branch({M},{se}) = {b}, expected {expect}")
    if not grid_ok:
        problems.append("branch grid disagreed with its own closed-form re-derivation")

    # ABSENT is FAIL on an empty archive
    empty = {"root": "<empty>", "manifest": None, "summary": None, "records": []}
    r = adjudicate_cell(empty, claimed_band=None, pinned_src_rev=None)
    if r["gates_ok"]:
        problems.append("an EMPTY archive passed the gates — ABSENT must be FAIL")
    for g in r["gates"]:
        if g["ok"]:
            problems.append(f"{g['gate']}: passed on an EMPTY archive (vacuous pass)")
    if r["branch"] != "U-VOID-INSTRUMENT":
        problems.append(f"an empty cell read {r['branch']}, not U-VOID-INSTRUMENT")

    # -------------------------------------------------------------------- #
    # THE SHIPPED FIXTURE — a REAL emitter's smoke output, healthy + defects #
    # -------------------------------------------------------------------- #
    fx = HERE / "selftest_fixture"
    report: dict = {}
    if fx.is_dir() and (fx / "manifest.json").is_file():
        pin_file = fx / "PINNED_SRC_REV"
        pin = pin_file.read_text().strip() if pin_file.is_file() else None
        band_file = fx / "CLAIMED_BAND"
        band = int(band_file.read_text().strip()) if band_file.is_file() else None
        healthy = load_cell(fx)
        v = adjudicate_cell(healthy, claimed_band=band, pinned_src_rev=pin)
        report["healthy"] = {"branch": v["branch"],
                             "failed_gates": v["failed_gates"]}
        # the fixture is a TINY real smoke (few games), so G-N/G-BAND/G-DECKS
        # are EXPECTED to fail on game-count/range grounds alone — only the
        # four SMOKE_REQUIRED_GATES are asserted healthy here.
        by_id = {g["gate"]: g["ok"] for g in v["gates"]}
        for gid in SMOKE_REQUIRED_GATES:
            if gid not in by_id:
                problems.append(f"the healthy fixture never ran {gid}")
            elif not by_id[gid]:
                problems.append(f"the healthy fixture FAILED {gid} — it is "
                                "supposed to be a clean, real emitter output")

        for name, mutate, expect_gate in FIXTURE_DEFECTS:
            broken = _deep_copy_cell(healthy)
            try:
                mutate(broken)
            except Exception as e:                              # noqa: BLE001
                problems.append(f"fixture defect {name!r} could not be applied: {e}")
                continue
            bv = adjudicate_cell(broken, claimed_band=band, pinned_src_rev=pin)
            by_id2 = {g["gate"]: g["ok"] for g in bv["gates"]}
            if by_id2.get(expect_gate, True):
                problems.append(f"defect {name!r} did NOT fail its own gate "
                                f"{expect_gate!r} (gates: {bv['failed_gates']})")
            if bv["gates_ok"]:
                problems.append(f"defect {name!r} left gates_ok True")
    else:
        problems.append("selftest_fixture/ is missing manifest.json — the "
                        "FIXTURE-TRAP: fixtures must come from a REAL "
                        "emitter's smoke output, not be hand-authored. Run "
                        "`launch_swap_cell.sh --smoke` once and copy its "
                        "SMOKE_laptop archive here (see selftest_fixture/README.md).")

    if problems:
        print(f"⛔ SELFTEST FAILED ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("selftest OK:", json.dumps(report, default=str))
    return 0


# =========================================================================== #
# CLI                                                                          #
# =========================================================================== #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default=None,
                    help="the ONE cell's out-dir (manifest.json/summary.json/"
                         "seed*_a*.json)")
    ap.add_argument("--smoke-mode", action="store_true")
    ap.add_argument("--pinned-src-rev", type=str, default=None)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.root:
        print("⛔ --root is required outside --selftest", file=sys.stderr)
        return 2
    cell = load_cell(Path(args.root))

    if args.smoke_mode:
        probs = smoke_problems(cell)
        v = {"smoke_mode": True, "root": args.root, "problems": probs,
             "resolved_knobs": {
                 "cand_fpu_reduction": L.resolve(_docs(cell),
                     "manifest:config.cand_search.fpu_reduction")[0],
                 "cand_tiearb": L.resolve(_docs(cell), "manifest:cand_tiearb",
                     "manifest:config.cand_tiearb")[0],
                 "opp_tiearb": L.resolve(_docs(cell), "manifest:opp_tiearb",
                     "manifest:config.opp_tiearb")[0],
             },
             "gates": [g(cell) for g in _PLAIN_GATES if g.__name__.startswith(
                 ("gate_fpu", "gate_arb"))]}
        v["resolved_knobs"] = {k: (None if val is L.MISSING else val)
                               for k, val in v["resolved_knobs"].items()}
        if args.out:
            Path(args.out).write_text(json.dumps(v, indent=2, default=str))
        print(json.dumps(v, indent=2, default=str))
        return 0 if not probs else 1

    claimed_band = read_claimed_band()
    v = adjudicate(cell, claimed_band=claimed_band,
                   pinned_src_rev=args.pinned_src_rev)
    if args.out:
        Path(args.out).write_text(json.dumps(v, indent=2, default=str))
    print(json.dumps(v, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
