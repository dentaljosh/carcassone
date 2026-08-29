#!/usr/bin/env python3
"""`analyze_phasegate` — THE PHASE-GATE ROUND'S ADJUDICATOR.

⛔ **THE PAIR IS LAW.** [`DESIGN.md`](DESIGN.md) + [`READ_RULE.md`](READ_RULE.md).
If this file disagrees with them, **it is this file that is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 games exist.**

The order of business, which is not negotiable:

  1. **Every §4 gate, per cell.** `ABSENT` is `FAIL`, never a skip and never a
     default. Every gate prints WHICH DOCUMENT and WHICH ADDRESS answered —
     config from `manifest.json`, statistics from `summary.json`, which carries
     no config block at all (IS-D1: a precheck that read `config` off
     `summary.json` got `{}`, failed closed on one conjunct and passed
     **vacuously** on another).
  2. **`G-ANCHOR` — the HARD ORDERING** (`READ_RULE.md` §4.0). `ARB_FULL` must
     pass every gate AND read `z >= +2.0` **against zero**. ⛔ Never an equality
     test against `+3.07`: that is a cross-band comparison and CL-068 forbids it.
     ⛔ **If the anchor fails, the gated cells' statistics are NOT PRINTED.**
  3. **The §5 ladder on `ARB_EARLY`** (pooled over `_L` + `_R`), in order, first
     match wins.
  4. The companions, each flagged ⛔ NEVER A BRANCH INPUT.

⭐ `--selftest` exercises the library's arithmetic, the dense `(M, SE)` branch
grid, and the shipped fixture — and is a PRE-LAUNCH checklist item precisely
because a launcher-side gate that runs once per round is never exercised by the
smoke (IS-D1's instrument-hardening note).
"""
from __future__ import annotations

import argparse
import json
import math
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
    man = root / "manifest.json"
    summ = root / "summary.json"
    recs = []
    for p in sorted(root.glob("seed*_a*.json")):
        try:
            recs.append(json.loads(p.read_text()))
        except Exception:
            recs.append({"_unreadable": str(p)})
    return {
        "root": str(root),
        "manifest": json.loads(man.read_text()) if man.is_file() else None,
        "summary": json.loads(summ.read_text()) if summ.is_file() else None,
        "records": recs,
    }


def _docs(cell: dict) -> dict:
    return {"manifest": cell.get("manifest") or {},
            "summary": cell.get("summary") or {}}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# =========================================================================== #
# THE GATES — READ_RULE.md §4                                                  #
# =========================================================================== #

def gate_gate(spec, cell) -> dict:
    """⭐⭐ `G-GATE` — THE INVERTED-LIVENESS GATE.

    A silently-defaulted `all` makes `ARB_EARLY` **BE** `ARB_FULL` and the
    round's primary a guaranteed-meaningless duplicate of its own anchor that
    looks perfectly healthy on every other gate. `ABSENT` is `FAIL`: a build
    whose telemetry omits the key **cannot be adjudicated**."""
    v, addr = L.resolve(_docs(cell),
                        "manifest:config.cand_tiearb.phase_gate",
                        "manifest:cand_tiearb.phase_gate")
    if v is L.MISSING:
        return L.gate("G-GATE", False, {"want": spec.phase_gate}, None,
                      "⛔ config.cand_tiearb.phase_gate ABSENT — ABSENT is FAIL. "
                      "A wheel/harness predating the gate served an UNGATED "
                      "arbiter, which on ARB_EARLY *is* ARB_FULL.")
    ok = str(v) == spec.phase_gate
    return L.gate("G-GATE", ok, {"phase_gate": v, "want": spec.phase_gate}, addr,
                  (f"phase_gate == {spec.phase_gate!r}, this cell's frozen window"
                   if ok else
                   f"⛔ phase_gate is {v!r}, this cell is frozen at "
                   f"{spec.phase_gate!r} — the cell is not the cell it claims"))


def gate_phi(spec, cell) -> dict:
    d = _docs(cell)
    fired = {}
    addrs = []
    for k, aliases in (
        ("early", ("summary:tiearb_fired_early_total",
                   "manifest:cand_tiearb.fired_early")),
        ("mid", ("summary:tiearb_fired_mid_total",
                 "manifest:cand_tiearb.fired_mid")),
        ("late", ("summary:tiearb_fired_late_total",
                  "manifest:cand_tiearb.fired_late")),
        ("total", ("summary:tiearb_fired_plies_total",
                   "manifest:cand_tiearb.fired_plies")),
    ):
        v, a = L.resolve(d, *aliases)
        fired[k] = None if v is L.MISSING else v
        addrs.append(f"{k}<-{a}")
    out = L.phi_gate(spec, fired)
    out["address"] = "; ".join(addrs)
    return out


def gate_tiearb_arm(spec, cell) -> dict:
    """`G-TIEARB-ARM` — the candidate is at the frozen rung and the opponent is
    STRUCTURALLY DISARMED.

    ⚠️ Scan **container** segments only for the opponent clause: a healthy
    archive emits a TERMINAL `config.opponent.tiearb_enabled = false`, and a gate
    that scanned terminals would void every healthy cell."""
    d = _docs(cell)
    want = {"enabled": True, "B": L.ARB_B, "J": L.ARB_J, "mode": L.ARB_MODE,
            "salt": L.ARB_SALT, "eps": L.ARB_EPS}
    got, addrs, bad = {}, {}, []
    for k, w in want.items():
        v, a = L.resolve(d, f"manifest:config.cand_tiearb.{k}",
                         f"manifest:cand_tiearb.{k}")
        got[k] = None if v is L.MISSING else v
        addrs[k] = a
        if v is L.MISSING:
            bad.append(f"{k} ABSENT")
        elif isinstance(w, float):
            if _num(v) != w:
                bad.append(f"{k}={v!r} want {w!r}")
        elif v != w:
            bad.append(f"{k}={v!r} want {w!r}")
    if not spec.arb_enabled and got.get("enabled") is False:
        bad = [b for b in bad if not b.startswith("enabled")]

    stray, armed = [], []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{path}.{k}" if path else k
                last = p.split(".")[-1]
                if isinstance(v, dict):
                    if "tiearb" in last and last != "cand_tiearb":
                        stray.append(p)
                    walk(v, p)
                else:
                    if last == "tiearb_enabled" and v is True and "opponent" in p:
                        armed.append(p)
    walk(cell.get("manifest") or {}, "")
    if stray:
        bad.append(f"stray tiearb CONTAINER(s): {stray}")
    if armed:
        bad.append(f"the OPPONENT is ARMED at {armed}")
    return L.gate("G-TIEARB-ARM", not bad,
                  {"resolved": got, "addresses": addrs,
                   "stray_tiearb_containers": stray,
                   "armed_opponent_leaves": armed},
                  "manifest",
                  ("the candidate is at B=16 J=4 argmax eps=0.0 on the salt of "
                   "record and the opponent carries no tiearb container"
                   if not bad else "⛔ G-TIEARB-ARM FAILED: " + "; ".join(bad)))


def gate_leaf(spec, cell) -> dict:
    d = _docs(cell)
    ch, _ = L.resolve(d, "manifest:config.cand_leaf_hash")
    oh, _ = L.resolve(d, "manifest:config.opp_leaf_hash")
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
                   "addresses": [a1, a2, a3]},
                  a1, ("the cell is on its frozen seed_start with the frozen "
                       "deck count, 2 seatings per deck" if not bad else
                       "⛔ G-BAND FAILED: " + "; ".join(bad)))


def gate_singlevar(spec, cell) -> dict:
    """`G-SINGLEVAR` — the ONLY candidate/opponent difference is `cand_tiearb`.

    ⚠️ The opponent's search knobs live ONE LEVEL DOWN under
    `config.opponent.champ_cfg.*`. A gate written from the design rather than
    from a real manifest voids every healthy cell — so both spellings resolve."""
    d = _docs(cell)
    aliases = ("k_dets", "sims_per_det", "total_sims", "c_puct", "tau_p",
               "value_norm", "leaf_quantize", "final_select")
    rows, bad = {}, []
    for a in aliases:
        cv, ca = L.resolve(d, f"manifest:config.champion.{a}")
        ov, oa = L.resolve(d, f"manifest:config.opponent.champ_cfg.{a}",
                           f"manifest:config.opponent.{a}")
        rows[a] = {"champion": None if cv is L.MISSING else cv,
                   "opponent": None if ov is L.MISSING else ov,
                   "addresses": [ca, oa]}
        if cv is L.MISSING or ov is L.MISSING:
            bad.append(f"{a} ABSENT on one side")
        elif repr(cv) != repr(ov):
            bad.append(f"{a}: champion {cv!r} vs opponent {ov!r}")
    return L.gate("G-SINGLEVAR", not bad, rows,
                  "manifest:config.champion.* vs config.opponent.champ_cfg.*",
                  ("the two sides' search knobs are identical across every "
                   "frozen alias — the arbiter is the single variable"
                   if not bad else "⛔ G-SINGLEVAR FAILED: " + "; ".join(bad)))


def gate_budget(spec, cell) -> dict:
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
    return L.gate("G-BUDGET", not bad, rows, "manifest:config.{champion,opponent}.*",
                  ("both sides run k8 x 1376 = 11008 and the product multiplies out"
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
    ], "manifest:config.backend.* — ⛔ the arbiter is RUST-ONLY; a python leg "
       "serves an arbiter-BLIND candidate that reads as a clean null")


def gate_wheel(spec, cell) -> dict:
    return _simple("G-WHEEL", cell, [
        (("manifest:carc_rs_build",), lambda v: bool(v) and "unavailable" not in str(v),
         "carc_rs_build"),
        (("manifest:carc_rs_binary_sha",), lambda v: bool(v), "carc_rs_binary_sha"),
        (("manifest:mixed_builds",), lambda v: v is False, "mixed_builds"),
    ], "manifest — ⚠️ carc_rs_version is permanently '0.1.0' and is NOT a "
       "discriminator; a STALE wheel serves a GATE-BLIND arbiter, i.e. "
       "ARB_EARLY == ARB_FULL")


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
                  {"n": None if n is L.MISSING else n, "frozen_n_games": spec.n_games,
                   "n_failed": None if nf is L.MISSING else nf, "n_common": nc,
                   "n_common_floor": floor, "notes": notes,
                   "addresses": [a1, a2]},
                  "summary.json",
                  ("; ".join(notes) or "n, n_failed and n_common are at the frozen "
                   "plan") if not bad else "⛔ G-N FAILED: " + "; ".join(bad))


def gate_failsoft(spec, cell) -> dict:
    """`G-FAILSOFT` — ⚠️ REPORT-ONLY above the floor.

    ⛔ A gated-out ply is **not** an error and must not appear here. Fail-soft is
    NOT symmetric across cells by construction — once cells diverge they are on
    different boards — so it is disclosed per cell, never assumed away."""
    d = _docs(cell)
    tot, a1 = L.resolve(d, "summary:tiearb_errors_total",
                        "manifest:cand_tiearb.tiearb_errors_total")
    rate, a2 = L.resolve(d, "summary:tiearb_error_rate_on_fired",
                         "manifest:cand_tiearb.tiearb_error_rate_on_fired")
    first, _ = L.resolve(d, "summary:tiearb_first_error")
    if L.MISSING in (tot, rate):
        return L.gate("G-FAILSOFT", False,
                      {"errors_total": None, "error_rate_on_fired": None}, None,
                      "⛔ the fail-soft block is ABSENT — ABSENT is FAIL "
                      "(unknown is not zero)")
    r = float(rate)
    ok = r < L.FAILSOFT_MAX_RATE
    return L.gate("G-FAILSOFT", ok,
                  {"errors_total": tot, "error_rate_on_fired": r,
                   "first_error": None if first is L.MISSING else first,
                   "addresses": [a1, a2]},
                  a1, (f"error rate {r:.5f} < {L.FAILSOFT_MAX_RATE} (a gated-out "
                       "ply is NOT an error and must not appear here)" if ok else
                       f"⛔ error rate {r:.5f} >= {L.FAILSOFT_MAX_RATE}"))


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
                   "leaf, so this means the two sides are not the agents this "
                   "design says they are"))


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


GATES = (gate_gate, gate_phi, gate_tiearb_arm, gate_leaf, gate_band,
         gate_singlevar, gate_budget, gate_exact, gate_rules, gate_backend,
         gate_wheel, gate_n, gate_failsoft, gate_sat, gate_host, gate_recon)


def adjudicate_cell(spec, cell) -> dict:
    gates = [g(spec, cell) for g in GATES]
    gates.append(L.decks_gate(spec, cell.get("records") or []))
    m, z, n, se, per_deck = L.paired_margin(cell.get("records") or [])
    return {
        "cell": spec.name, "role": spec.role, "phase_gate": spec.phase_gate,
        "purpose": spec.purpose,
        "gates": gates,
        "gates_ok": all(g["ok"] for g in gates),
        "failed_gates": [g["gate"] for g in gates if not g["ok"]],
        "stats": {"M": m, "z": z, "n_paired": n, "se": se,
                  "UB95": None if (m is None or se is None) else m + 2 * se,
                  "LB95": None if (m is None or se is None) else m - 2 * se},
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
    differ from the frozen ones in `seed_start`/`n_decks` and NOTHING else, so a
    fixture can never silently redefine the round it is supposed to exercise."""
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
    # source produce different bytes. G-WHEEL-SAME is therefore asserted PER
    # BOX -- the cross-box build identity is `carc_rs_build`'s job.
    by_role: dict[str, set] = {}
    for n, s in shas.items():
        spec = next((c for c in specs if c.name == n), None)
        if spec:
            by_role.setdefault(spec.role, set()).add(s)
    bad_roles = {r: sorted(map(str, v)) for r, v in by_role.items() if len(v) > 1}
    round_gates.append(L.gate(
        "G-WHEEL-SAME", not bad_roles and bool(by_role),
        {"binary_sha_by_cell": shas, "by_role": {k: sorted(map(str, v))
                                                 for k, v in by_role.items()}},
        "manifest:carc_rs_binary_sha",
        ("every cell on a box shares that box's binary sha ⚠️ the sha is "
         "BOX-LOCAL and is never compared ACROSS boxes (carc_rs_build is the "
         "cross-box witness). ⚠️ THIS ROUND BUILDS A NEW WHEEL, so it carries "
         "its OWN IDENT cell and inherits none." if not bad_roles and by_role else
         f"⛔ a box ran more than one wheel: {bad_roles or 'no cells'} — "
         "A FAIL ON ANY CELL VOIDS EVERY CELL")))

    revs = {n: (c.get("manifest") or {}).get("code_rev")
            for n, c in cells_by_name.items()}
    rg = L.cross_box_rev_gate(revs, pins_by_role or {})
    round_gates.append(L.gate("G-REV", rg["ok"], rg,
                              "manifests + each box's PINNED_SRC_REV", rg["why"]))

    round_gates.append(L.subpool_gate(
        {n: (c.get("manifest") or {}) for n, c in cells_by_name.items()}))

    blinds = {n: (c.get("manifest") or {}).get("BLIND_COMMIT")
              for n, c in cells_by_name.items()}
    distinct_blind = sorted({b for b in blinds.values() if b})
    blind_ok = (len(distinct_blind) == 1 and L.is_hex40(distinct_blind[0])
                and all(blinds.values()))
    round_gates.append(L.gate(
        "G-BLIND", blind_ok, {"BLIND_COMMIT_by_cell": blinds}, "manifest:BLIND_COMMIT",
        ("one 40-hex BLIND_COMMIT stamped into every adjudicated manifest"
         if blind_ok else
         "⛔ BLIND_COMMIT absent, malformed, or disagreeing across cells — "
         "ABSENT is FAIL; a read that was not blind is not a read")))

    round_ok = all(g["ok"] for g in round_gates)

    # --- G-ANCHOR: the HARD ORDERING --------------------------------------
    anchor = per_cell.get("ARB_FULL")
    if anchor is None:
        anchor_gate = L.gate("G-ANCHOR", False, {"reason": "ARB_FULL absent"}, None,
                             "⛔ the anchor cell is ABSENT — ABSENT is FAIL")
    else:
        z = anchor["stats"]["z"]
        ok = bool(anchor["gates_ok"] and round_ok and z is not None
                  and z >= L.ANCHOR_Z)
        anchor_gate = L.gate(
            "G-ANCHOR", ok,
            {"z": z, "M": anchor["stats"]["M"], "bar": L.ANCHOR_Z,
             "anchor_gates_ok": anchor["gates_ok"],
             "prior_band_context": L.PRIOR_BANDS},
            "summary/records via RECON",
            (f"the anchor convicts against ZERO (z = {z:.3f} >= {L.ANCHOR_Z}). "
             "⛔ This is a SIGN-AND-SIGNIFICANCE test, NOT an equality test "
             "against +3.07 — a cross-band equality test is exactly what "
             "CL-068 forbids. 'Reproduces +3.07' is a NARRATIVE reading."
             if ok else
             "⛔ G-ANCHOR FAILED — the round's branch is U-VOID-ANCHOR and the "
             "gated cells' statistics are NOT PRINTED. ⭐ This is a FULLY "
             "ACCEPTABLE OUTCOME and a finding in its own right: a "
             "non-replicating arbiter on a fresh band and a new wheel would be "
             "MORE decision-relevant than any phase slice, and would "
             "immediately impugn a production knob."))
    round_gates.append(anchor_gate)

    # --- the primary, pooled over the sub-cells ---------------------------
    pool_early = [c for c in specs if c.pool_key == "ARB_EARLY"]
    early = [per_cell[c.name] for c in pool_early
             if c.name in per_cell]
    pooled_deck = [d for c in early for d in c["_per_deck"]]
    n_pool = len(pooled_deck)
    if n_pool >= 2:
        mp = math.fsum(pooled_deck) / n_pool
        vp = math.fsum((d - mp) ** 2 for d in pooled_deck) / (n_pool - 1)
        sep = math.sqrt(vp / n_pool)
        zp = mp / sep if sep > 0 else float("nan")
    else:
        mp = sep = zp = None
    gated_ok = bool(early) and all(c["gates_ok"] for c in early) and round_ok
    ident = per_cell.get("IDENT")
    if ident is not None:
        iz = ident["stats"]["z"]
        ident_ok = ident["gates_ok"] and iz is not None and abs(iz) <= 2.0
        gated_ok = gated_ok and ident_ok

    branch = L.branch_for_cell(mp, sep, zp, gates_ok=gated_ok,
                               anchor_ok=anchor_gate["ok"])

    out = {
        "round": "phasegate A1",
        "pair": ["measurement/phasegate_prep/DESIGN.md",
                 "measurement/phasegate_prep/READ_RULE.md"],
        "smoke_mode": smoke_mode,
        "round_gates": round_gates,
        "round_gates_ok": round_ok,
        "cells": per_cell,
        "branch": branch,
        "primary": {
            "cell": "ARB_EARLY (pooled over _L + _R)",
            "M": mp, "se": sep, "z": zp, "n_paired": n_pool,
            "UB95": None if (mp is None or sep is None) else mp + 2 * sep,
            "LB95": None if (mp is None or sep is None) else mp - 2 * sep,
            "bar": L.BAR,
        },
        "riders": list(L.RIDERS_ALWAYS) + (
            list(L.RIDERS_E_LIVE) if branch.startswith("E-LIVE") else
            list(L.RIDERS_E_DEAD) if branch.startswith("E-DEAD") else []),
    }

    # ⛔ THE HARD ORDERING, ENFORCED IN THE OUTPUT ITSELF.
    if branch == "U-VOID-ANCHOR":
        out["primary"] = {"WITHHELD": "⛔ G-ANCHOR failed — READ_RULE §4.0 "
                                      "forbids printing any gated-cell statistic."}
        for name, c in out["cells"].items():
            if name != "ARB_FULL":
                c["stats"] = {"WITHHELD": "⛔ U-VOID-ANCHOR"}
                c.pop("_per_deck", None)
    if branch == "U-VOID-INSTRUMENT":
        out["void_banner"] = ("⛔ U-VOID-INSTRUMENT — the instrument, not the "
                              "world. NO phase reading of any kind. Statistics "
                              "below are a COMPANION TABLE only.")

    # --- companions. ⛔ NEVER branch inputs --------------------------------
    full = per_cell.get("ARB_FULL")
    comp: dict = {"_warning": "⛔ COMPANIONS — NEVER A BRANCH INPUT."}
    if full and mp is not None and branch not in ("U-VOID-ANCHOR",):
        common = (set(L.per_deck_margins([]).keys()),)  # placeholder for clarity
        del common
        fd = {}
        # (the FULL-EARLY companion is built from the pool below)
        # deck-paired FULL - EARLY over the decks both cells played
        e_by_deck: dict = {}
        for c in pool_early:
            if c.name in cells_by_name:
                e_by_deck.update(L.per_deck_margins(
                    cells_by_name[c.name].get("records") or []))
        f_by_deck = L.per_deck_margins(
            cells_by_name["ARB_FULL"].get("records") or [])
        shared = sorted(set(f_by_deck) & set(e_by_deck))
        if len(shared) >= 2:
            diffs = [f_by_deck[s] - e_by_deck[s] for s in shared]
            dm = math.fsum(diffs) / len(diffs)
            dv = math.fsum((x - dm) ** 2 for x in diffs) / (len(diffs) - 1)
            dse = math.sqrt(dv / len(diffs))
            fd = {"D_full_minus_early": dm, "se": dse,
                  "z": (dm / dse if dse > 0 else float("nan")),
                  "n_common": len(shared),
                  "se_model_18_28_over_sqrt_n": L.se_cross_cell(len(shared))}
        comp["full_minus_early"] = fd or {"n_common": len(shared)}
        comp["proportional_share_expectation"] = L.PROPORTIONAL_COMPANION
        comp["elo"] = {n: L.winrate_elo(cells_by_name[n].get("records") or [])
                       for n in per_cell if n in cells_by_name}
        comp["elo_warning"] = ("⚠️ elo may NEVER be quoted bare — Stage 2's own "
                               "secondary did not convict (+23.92, CI "
                               "[-0.21, +48.06], winrate z +1.94) and a phase "
                               "SLICE of it is weaker still. The MARGIN is the "
                               "statistic.")
    out["companions"] = comp
    return out


# =========================================================================== #
# SELFTEST                                                                     #
# =========================================================================== #

def fixture_specs(fx: Path):
    """The fixture's own `CellSpec` table — the SAME round at a tiny deck
    scale. `selftest()` asserts it differs from the frozen plan in `seed_start`
    and `n_decks` ONLY."""
    return tuple(L.CellSpec(**s) for s in json.loads((fx / "SPECS.json").read_text()))


def _set(cell: dict, dotted: str, value) -> None:
    cur = cell
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


#: ⭐ THE NAMED DEFECTS — one per gate whose failure would otherwise never be
#: observed. Each must (a) fire its own gate and (b) drive the round to a VOID.
#: ⛔⛔ The first one is the design's single most dangerous failure mode: an
#: `ARB_EARLY` cell whose gate silently defaulted to `all` IS `ARB_FULL`, and it
#: looks perfectly healthy on every other gate.
FIXTURE_DEFECTS = (
    ("inverted_liveness_gate_defaulted_to_all",
     lambda c: (_set(c["ARB_EARLY_L"]["manifest"],
                     "config.cand_tiearb.phase_gate", "all"),
                _set(c["ARB_EARLY_L"]["manifest"],
                     "cand_tiearb.phase_gate", "all")),
     "G-GATE"),
    ("stale_wheel_no_phase_counters",
     lambda c: [c["ARB_EARLY_L"]["summary"].pop(k, None)
                for k in ("tiearb_fired_early_total", "tiearb_fired_mid_total",
                          "tiearb_fired_late_total")]
     + [c["ARB_EARLY_L"]["manifest"]["cand_tiearb"].pop(k, None)
        for k in ("fired_early", "fired_mid", "fired_late")],
     "G-PHI"),
    ("gate_bound_the_wrong_window",
     lambda c: _set(c["ARB_EARLY_L"]["summary"], "tiearb_fired_mid_total", 9),
     "G-PHI"),
    ("leaf_hashes_differ_across_the_two_sides",
     lambda c: _set(c["ARB_FULL"]["manifest"], "config.opp_leaf_hash", "deadbeef"),
     "G-LEAF"),
    ("opponent_arbiter_armed",
     lambda c: _set(c["ARB_FULL"]["manifest"], "config.opponent.tiearb_enabled",
                    True),
     "G-TIEARB-ARM"),
    ("subcells_are_not_the_same_cell",
     lambda c: (_set(c["ARB_EARLY_R"]["manifest"], "config.cand_tiearb.B", 64),
                _set(c["ARB_EARLY_R"]["manifest"], "cand_tiearb.B", 64)),
     "G-SUBPOOL"),
    ("mixed_rev_round",
     lambda c: _set(c["ARB_EARLY_R"]["manifest"], "code_rev", "cccccccc"),
     "G-REV"),
    ("anchor_does_not_convict",
     lambda c: [r.update(diff=r["diff"] - 3.2)
                for r in c["ARB_FULL"]["records"]],
     "G-ANCHOR"),
    ("recon_disagrees_with_the_summary",
     lambda c: _set(c["ARB_EARLY_L"]["summary"], "paired_mean_margin", 99.0),
     "RECON"),
    ("a_deck_was_played_at_one_seat_only",
     lambda c: c["ARB_EARLY_L"]["records"].pop(),
     "G-DECKS"),
    ("ident_cell_actually_fired",
     lambda c: _set(c["IDENT"]["summary"], "tiearb_fired_early_total", 4),
     "G-PHI"),
)


def selftest() -> int:
    problems = list(L.sanity_check())
    grid = L.branch_grid(step=0.02)
    if not grid["all_reachable"]:
        problems.append(f"branch grid: only {grid['reachable']} reachable")

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

    # the hard ordering: a failed anchor withholds every gated statistic
    fake = {"ARB_FULL": empty, "ARB_EARLY_L": empty, "ARB_EARLY_R": empty}
    v = adjudicate(fake, pins_by_role={})
    if v["branch"] not in ("U-VOID-INSTRUMENT", "U-VOID-ANCHOR"):
        problems.append(f"an all-empty round read {v['branch']}, not a void")

    # ------------------------------------------------------------------ #
    # THE SHIPPED FIXTURE — a shaped, HEALTHY round, plus the named defects #
    # ------------------------------------------------------------------ #
    fx = HERE / "selftest_fixture"
    fixture_report: dict = {}
    if fx.is_dir() and (fx / "SPECS.json").is_file():
        specs = fixture_specs(fx)
        # ⛔ THE FIXTURE MAY NOT REDEFINE THE ROUND. Only the deck SCALE may
        # differ from the frozen plan.
        frozen = {c.name: c for c in L.CELLS}
        if sorted(s.name for s in specs) != sorted(frozen):
            problems.append("the fixture's cell NAMES differ from the frozen plan")
        for s in specs:
            f = frozen.get(s.name)
            if f is None:
                continue
            for field in ("role", "phase_gate", "arb_enabled", "pool_key"):
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
        fixture_report["healthy"] = {
            "branch": v["branch"],
            "failed_round_gates": [g["gate"] for g in v["round_gates"]
                                   if not g["ok"]],
            "failed_cell_gates": {n: c["failed_gates"]
                                  for n, c in v["cells"].items()
                                  if c["failed_gates"]},
            "primary": v["primary"],
        }
        if fixture_report["healthy"]["failed_round_gates"]:
            problems.append("the HEALTHY fixture failed round gate(s): "
                            f"{fixture_report['healthy']['failed_round_gates']}")
        if fixture_report["healthy"]["failed_cell_gates"]:
            problems.append("the HEALTHY fixture failed cell gate(s): "
                            f"{fixture_report['healthy']['failed_cell_gates']}")
        if v["branch"] != "E-LIVE":
            problems.append(f"the HEALTHY fixture read {v['branch']}, want E-LIVE")

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
            fixture_report[label] = {"branch": vv["branch"], "failed": fired}
            if want_gate not in fired:
                problems.append(f"defect {label!r} did NOT fire {want_gate} "
                                f"(fired: {fired})")
            if not vv["branch"].startswith("U-VOID"):
                problems.append(f"defect {label!r} read {vv['branch']}, not a void")
    else:
        problems.append("⚠️ selftest_fixture/ is not populated — the adjudicator "
                        "has never been run against a shaped archive. This is a "
                        "BUILD DEBT, and it is reported rather than hidden.")

    print(json.dumps({"problems": problems, "fixture": fixture_report,
                      "branch_grid": grid,
                      "phase_windows": {k: [v[0], v[-1]]
                                        for k, v in L.phase_windows().items()},
                      "golden_table": [[k, L.phase_bucket(k)]
                                       for k, _ in L.PHASE_GOLDEN]}, indent=2))
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
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.root:
        ap.error("--root or --selftest")

    cells = {p.name: load_cell(p) for p in sorted(args.root.iterdir())
             if p.is_dir() and (p / "manifest.json").is_file()
             # PG-A1 defect 2: smoke/quarantine archives are not round cells —
             # they run at the pre-launch commit by design (AMENDMENTS.md).
             and not p.name.startswith(("SMOKE_", "_VOID_"))}
    pins = {}
    if args.pin_local and args.pin_local.is_file():
        pins["local"] = args.pin_local.read_text().strip()
    if args.pin_laptop and args.pin_laptop.is_file():
        pins["laptop"] = args.pin_laptop.read_text().strip()
    v = adjudicate(cells, pins_by_role=pins, smoke_mode=args.smoke_mode)

    if args.smoke_mode:
        # ⛔⛔ THE SMOKE EMITS NO OUTCOME KEY. The emitter whitelist is a WRITE
        # surface; the gate is a READ surface firing on forbidden OUTCOME keys
        # at ANY DEPTH (the Stage-2 `G-SMOKE` ruling).
        #
        # ⚠️ AND "AT ANY DEPTH" IS THE WHOLE POINT: a gate's `detail` and `why`
        # carry the values that gate READ, and `RECON`'s detail is literally the
        # five outcome statistics under their own names. So a smoke record keeps
        # only `{gate, ok, address}` per gate, and the per-phase fire block —
        # which is a FIRE COUNT, not an outcome. (This test caught a real leak:
        # the first draft emitted the full gate records and shipped
        # `paired_mean_margin` straight into the smoke.)
        def _bare(g):
            return {"gate": g["gate"], "ok": g["ok"], "address": g["address"]}

        def _fires(c):
            d = next((g["detail"] for g in c["gates"] if g["gate"] == "G-PHI"), None)
            if not isinstance(d, dict):
                return None
            return {k: d.get(k) for k in ("phase_gate", "fired_early", "fired_mid",
                                          "fired_late", "fired_plies", "shares")}

        v = {"smoke_mode": True,
             "round_gates": [_bare(g) for g in v["round_gates"]],
             "round_gates_ok": v["round_gates_ok"],
             "cells": {n: {"gates": [_bare(g) for g in c["gates"]],
                           "gates_ok": c["gates_ok"],
                           "failed_gates": c["failed_gates"]}
                       for n, c in v["cells"].items()},
             "per_phase_fires": {n: _fires(c) for n, c in v["cells"].items()},
             "note": "⭐ the smoke's one substantive job beyond liveness: it "
                     "returns the REALIZED per-phase fired counts, the first "
                     "real measurement of DESIGN §6.2's proxy — so a materially "
                     "different early share revises the ETA BEFORE the round "
                     "starts rather than inside it."}

    txt = json.dumps(v, indent=2, default=str)
    if args.out:
        args.out.write_text(txt)
        print(f"[analyze_phasegate] wrote {args.out}")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
