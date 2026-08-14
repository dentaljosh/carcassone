#!/usr/bin/env python3
"""k-WIDTH / DETERMINIZATION AT TIED PLIES — the pre-gate ladder ("the wart")
(measurement/kwidth_ties_20260814/DESIGN.md + READ_RULE.md, both committed
BEFORE this file; this file committed BEFORE any search ran).

The sibling of `escalation_ladder.py` (the vart), which scaled sims/det at
FIXED k = 8 and closed E-FLAT. This ladder changes exactly ONE axis: it scales
**k at fixed sims/det**, and adds the design's load-bearing feature — two
**ISO-BUDGET** rungs that buy worlds by SELLING depth at the champion's own
11,008 sims:

    R0  k8  x 1376 =  11,008   base = production champion of record
    R1  k16 x 1376 =  22,016   EXPANSION
    R2  k32 x 1376 =  44,032   EXPANSION
    R3  k64 x 1376 =  88,064   EXPANSION
    C1  k16 x  688 =  11,008   ISO-BUDGET  (bracket for C2)
    C2  k32 x  344 =  11,008   ISO-BUDGET  (the pre-named attribution rung)

WHY THE ISO-BUDGET RUNGS DECIDE THE READING: the vart already priced "more
budget via depth" as flat, so a capture confined to R1-R3 is a BUDGET
statement in width's clothing. C1/C2 are pure reallocation — deployable at
1.00x wall-clock — so only a capture there is an allocation mechanism.
READ_RULE §5 encodes exactly that: W-FUND-WORLDS needs an ISO-BUDGET rung to
clear; otherwise W-BUDGET-ONLY funds nothing.

CRN ALONG k (exact, read off fair_agent._pimc_move, not assumed): the worlds
come from ONE stream seeded by `det_seed_base(move_idx)+1`, and world i's
search seed is `det_seed_base+100+i` — both independent of k_dets AND of sims.
So at fixed sims/det the k16/k32/k64 runs contain the base's 8 worlds as an
exact PREFIX, and any pick change is attributable to the ADDED worlds alone.
C1/C2 hold the same world stream but search each world shallower — that
confound IS the trade being priced (DESIGN §3.1).

Search conventions are the vart's, clone-for-clone (which are
champ_picks.py's, which are mine_disagreements._search_pick's):
`make_production_champion("fair", ..., seed=match.agent_seed(deck_seed, seat),
verify=True)` with `sims=` AND `k_dets=` the only overrides;
`mirror_protocol.reseat(..., move_idx=ply)` mandatory;
`resolve_execution("inherit", profile="desktop", rust_threads=1)`; root
replayed via `root_replay.replay_actions` and checksum-asserted BEFORE any
search. One process per rules profile (CARCASSONNE_FIX_R9 is import-latched).

STATISTICS ARE IMPORTED FROM escalation_ladder, NOT RE-DERIVED, so the two
programs' numbers are commensurable by construction: pick resolution (exact
arm membership -> census afterstate transposition map -> unresolved), the
oracle per-world value loader, the symmetrized parity-split honest regret
denominator, and TG.cluster_se on root_id.

⚠️ THERE IS NO HOLDOUT CODE PATH IN THIS FILE, BY DESIGN. The 211-position /
120-root holdout of measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json is
excluded from every phase and is NOT opened by this program under any branch
(READ_RULE §1); it survived the vart unburned and it survives this run
unburned.

Phases:
  --search --profile P [--rungs R0,R1,...]
      per-position records -> measurement/kwidth_ties_20260814/records/
      (resume-able; best-effort per position, never takes the pool down)
  --analyze
      the READ_RULE §3 statistics + §5 branch -> LADDER_READOUT.{md,json}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(HERE), str(REPO / "scripts" / "measurement_infra"),
           str(REPO / "scripts" / "jcz_match")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import term_gate as TG                # noqa: E402  (corpus paths, cluster_se, elo_chain)
import escalation_ladder as EL        # noqa: E402  (the vart's statistics, reused verbatim)

SCHEMA = "carcassonne-kwidth-ladder/v1"
MEAS = REPO / "measurement" / "kwidth_ties_20260814"
RECORDS_DIR = MEAS / "records"
VART_RECORDS = REPO / "measurement" / "tieescalation_20260814" / "records"

#: READ_RULE §2 — frozen before any number. (id, k_dets, sims_per_det, class)
RUNGS = (
    ("R0", 8, 1376, "base"),
    ("R1", 16, 1376, "expansion"),
    ("R2", 32, 1376, "expansion"),
    ("R3", 64, 1376, "expansion"),
    ("C1", 16, 688, "isobudget"),
    ("C2", 32, 344, "isobudget"),
)
BASE_ID = "R0"
BASE_TOTAL = 8 * 1376                       # 11,008 — the champion of record

#: READ_RULE §4 bars — the vart's, unchanged, committed before any number.
BAR_CAPTURE_RATIO = 0.35
BAR_Z = 2.0
BAR_COVERAGE = 0.85
BAR_ERROR_FRAC = 0.05
#: READ_RULE §5 — the W-FUND-AMBIG / W-BUDGET-ONLY split on the iso-budget rungs.
BAR_AMBIG_Z = 1.0

#: DESIGN §6 deploy-multiplier constants (census-realized trigger rate).
TRIGGER_RATE = 0.660
TILE_SEARCH_SHARE = 0.5


def rung_by_id(rid_: str) -> tuple:
    for r in RUNGS:
        if r[0] == rid_:
            return r
    raise KeyError(rid_)


def rung_key(k: int, sims: int) -> str:
    """The per-record key. Encodes the FULL config, not an index, so a record
    can never be misread as a different rung."""
    return f"k{int(k)}x{int(sims)}"


def rung_total(rid_: str) -> int:
    _, k, s, _ = rung_by_id(rid_)
    return int(k) * int(s)


def deploy_multiplier(rid_: str) -> float:
    """DESIGN §6. Exactly 1.00 for the iso-budget rungs, by construction."""
    return 1.0 + TRIGGER_RATE * TILE_SEARCH_SHARE * (rung_total(rid_) / BASE_TOTAL - 1.0)


# --------------------------------------------------------------------------- #
# search phase (one process per rules profile)                                 #
# --------------------------------------------------------------------------- #
_G: dict = {}


def _init(game_kwargs: dict) -> None:
    _G["game_kwargs"] = dict(game_kwargs or {})


def _cell(job: tuple) -> dict:
    """(rid, root_id, deck_seed, ply, seat, actions, checksum, rungs) -> one
    record. Best-effort: NEVER raises out of this function."""
    rid, root_id, deck_seed, ply, seat, actions, checksum, rungs = job
    rec = {"rid": rid, "root_id": root_id, "deck_seed": int(deck_seed),
           "ply": int(ply), "seat": int(seat), "picks": {}, "error": None}
    try:
        import match as JM
        import root_replay as RR
        from carcassonne_ai import mirror_protocol as MP
        from carcassonne_ai.champion_factory import make_production_champion

        game, board = RR.replay_actions(int(deck_seed), actions, int(ply),
                                        game_kwargs=_G.get("game_kwargs"))
        cks = game.string_representation(board)
        if checksum is not None and cks != checksum:
            raise ValueError("checksum_mismatch")
        ex = MP.resolve_execution("inherit", profile="desktop", rust_threads=1)
        seed = JM.agent_seed(int(deck_seed), int(seat))
        for rid_, k, sims, klass in rungs:
            t0 = time.time()
            champ = make_production_champion(
                "fair", game=game, seed=seed, verify=True,
                sims=int(sims), k_dets=int(k), **ex.factory_kwargs())
            MP.reseat(champ, deck_seed=int(deck_seed),
                      actions=[int(a) for a in actions[:ply]], move_idx=int(ply))
            action = int(champ.choose_action(board))
            fd = champ.manifest.get("runtime_budget_override") \
                or champ.manifest.get("fair_deploy", {})
            rec["picks"][rung_key(k, sims)] = {
                "rung_id": rid_, "action": action,
                "secs": round(time.time() - t0, 3),
                "k_dets": int(fd.get("k_dets", 0)),
                "sims_per_det": int(fd.get("sims_per_det", 0)),
                "total_sims": int(fd.get("total_sims", 0)),
                "backend": ex.backend}
    except Exception as exc:                                    # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def _record_complete(path: Path, rungs) -> bool:
    if not path.is_file():
        return False
    try:
        rec = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    if rec.get("error"):
        return False
    return all(rung_key(k, s) in rec.get("picks", {}) for _, k, s, _ in rungs)


def cmd_search(profile: str, workers: int, rungs, limit: int,
               nice_val: int = 19) -> int:
    import chain_census as CC
    CC.prepare_env(profile)                    # BEFORE any carcassonne_ai import
    from carcassonne_ai import rules_profile as RP
    prof = RP.activate(profile)
    gk = prof.game_kwargs() or None
    try:
        os.nice(int(nice_val))
    except OSError:
        pass

    per = TG.load_per_position()
    arms = json.loads(TG.ARMS_JSON.read_text())
    rids = [r for r in EL.slice_rids(per, "dev")            # dev ONLY — no holdout path
            if per[r]["rules_profile"] == profile]
    acts = TG.load_actions_index(set(rids))

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    for rid in rids:
        if _record_complete(RECORDS_DIR / f"{rid}.json", rungs):
            continue
        row = acts[rid]
        if "actions" in row:
            actions = [int(x) for x in row["actions"]]
        else:
            actions = [int(x) for x in
                       json.loads(Path(row["archive_path"]).read_text())["actions"]]
        jobs.append((rid, per[rid]["root_id"], int(row["deck_seed"]),
                     int(row["ply"]), int(arms[rid]["seat"]), actions,
                     row["checksum"], tuple(rungs)))
    if limit and int(limit) > 0:
        jobs = jobs[: int(limit)]
    print(f"[kwidth:{profile}] {len(rids)} dev rids in slice, {len(jobs)} to "
          f"search (rungs {[r[0] for r in rungs]})", flush=True)

    t0 = time.time()
    n_err = 0
    if jobs:
        from multiprocessing import get_context
        w = max(1, min(int(workers), len(jobs)))
        with get_context("fork").Pool(w, initializer=_init, initargs=(gk,)) as pool:
            for i, rec in enumerate(pool.imap_unordered(_cell, jobs), 1):
                p = RECORDS_DIR / f"{rec['rid']}.json"
                tmp = p.with_suffix(".tmp")
                tmp.write_text(json.dumps(rec))
                os.replace(tmp, p)
                if rec.get("error"):
                    n_err += 1
                print(f"[{i}/{len(jobs)}] {rec['rid']} "
                      f"{'ok' if not rec.get('error') else 'FAIL ' + rec['error']}",
                      flush=True)
    manifest = {
        "schema": SCHEMA, "phase": "search", "profile": profile, "slice": "dev",
        "rungs": [{"id": r[0], "k_dets": r[1], "sims_per_det": r[2],
                   "total_sims": r[1] * r[2], "class": r[3]} for r in rungs],
        "workers": int(workers), "n_slice_rids": len(rids),
        "n_searched": len(jobs), "n_error": n_err,
        "wall_secs": round(time.time() - t0, 1),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (MEAS / f"manifest_search_{profile}_dev.json").write_text(
        json.dumps(manifest, indent=2))
    print(f"[kwidth:{profile}] done, {n_err} errors, "
          f"{manifest['wall_secs']}s", flush=True)
    return 1 if n_err else 0


# --------------------------------------------------------------------------- #
# analysis table                                                               #
# --------------------------------------------------------------------------- #
def build_table(rungs) -> dict:
    """Join search records + arms + oracle values + per_position, dev slice."""
    per = TG.load_per_position()
    arms = json.loads(TG.ARMS_JSON.read_text())
    rids = EL.slice_rids(per, "dev")
    hold = EL.load_holdout_roots()
    assert not any(per[r]["root_id"] in hold for r in rids), \
        "holdout rid leaked into the dev table"
    oracle, problems = EL.load_oracle_values(rids, arms)
    repr_maps = EL.load_action_repr_maps()

    rows, counters = [], defaultdict(int)
    for rid in rids:
        p = RECORDS_DIR / f"{rid}.json"
        if not p.is_file():
            counters["missing_record"] += 1
            continue
        rec = json.loads(p.read_text())
        if rec.get("error"):
            counters["search_error"] += 1
            if "checksum" in rec["error"]:
                counters["checksum_error"] += 1
            continue
        if rid not in oracle:
            counters["oracle_problem"] += 1
            continue
        a = arms[rid]["arms"]
        rmap = repr_maps.get(rid)
        picks, idxs, secs = {}, {}, {}
        for rid_, k, sims, _klass in rungs:
            entry = rec["picks"].get(rung_key(k, sims))
            if entry is None:
                counters[f"missing_rung_{rid_}"] += 1
                continue
            picks[rid_] = int(entry["action"])
            idxs[rid_] = EL.resolve_pick(entry["action"], a, rmap)
            secs[rid_] = float(entry["secs"])
        rows.append({
            "rid": rid, "root_id": per[rid]["root_id"],
            "stratum": per[rid]["stratum"],
            "profile": per[rid]["rules_profile"],
            "phase": per[rid]["phase_bucket"],
            "scale_all": float(per[rid]["scale_all"]),
            "arms": a, "values": oracle[rid],
            "champ_action": arms[rid].get("champ_action"),
            "picks": picks, "idxs": idxs, "secs": secs,
        })
    counters["oracle_integrity_problems"] = len(problems)
    return {"rows": rows, "counters": dict(counters), "n_slice": len(rids),
            "problems": problems}


def rung_stats(rows: list, rid_: str, base: str = BASE_ID) -> dict:
    """READ_RULE §3 statistics for one rung vs the base rung."""
    num, clusters = [], []
    n_pair = n_base_res = n_rung_unres = n_change_arm = n_change_act = 0
    secs = []
    for r in rows:
        bi = r["idxs"].get(base)
        ri = r["idxs"].get(rid_)
        if rid_ in r["secs"]:
            secs.append(r["secs"][rid_])
        if bi is None:
            continue
        n_base_res += 1
        if rid_ not in r["idxs"]:
            continue
        if ri is None:
            n_rung_unres += 1
            continue
        n_pair += 1
        means = [EL._mean(v) for v in r["values"]]
        num.append((means[ri] - means[bi]) * r["scale_all"])
        clusters.append(r["root_id"])
        if ri != bi:
            n_change_arm += 1
        if r["picks"].get(rid_) != r["picks"].get(base):
            n_change_act += 1
    n_rows = len(rows)
    mean_capture = EL._mean(num) if num else float("nan")
    se = TG.cluster_se(num, clusters) if len(set(clusters)) > 1 else float("nan")
    secs_sorted = sorted(secs)
    _, k, sims, klass = rung_by_id(rid_)
    return {
        "id": rid_, "k_dets": k, "sims_per_det": sims, "total_sims": k * sims,
        "class": klass,
        "n_pairs": n_pair, "n_base_resolved": n_base_res,
        "coverage": (n_pair / n_rows) if n_rows else float("nan"),
        "mean_capture": mean_capture, "se": se,
        "z": (mean_capture / se) if (num and se and se == se and se > 0)
             else float("nan"),
        "pick_change_rate_arm": (n_change_arm / n_pair) if n_pair else float("nan"),
        "pick_change_rate_action": (n_change_act / n_pair) if n_pair else float("nan"),
        "outside_scored_rate": (n_rung_unres / n_base_res) if n_base_res
                               else float("nan"),
        "secs_mean": EL._mean(secs) if secs else float("nan"),
        "secs_median": (secs_sorted[len(secs_sorted) // 2] if secs
                        else float("nan")),
        "deploy_multiplier_est": deploy_multiplier(rid_),
    }


def denom_stats(rows: list, base: str = BASE_ID) -> dict:
    """The honest base-rung regret (READ_RULE §3 `denom`) — the vart's
    symmetrized parity-split estimator, imported unchanged."""
    vals, clusters = [], []
    for r in rows:
        bi = r["idxs"].get(base)
        if bi is None:
            continue
        vals.append(EL.honest_regret(r["values"], bi) * r["scale_all"])
        clusters.append(r["root_id"])
    m = EL._mean(vals) if vals else float("nan")
    se = TG.cluster_se(vals, clusters) if len(set(clusters)) > 1 else float("nan")
    return {"mean": m, "se": se, "n": len(vals)}


# --------------------------------------------------------------------------- #
# integrity witnesses (reported, never gates)                                  #
# --------------------------------------------------------------------------- #
def base_agreement(rows: list, base: str = BASE_ID) -> dict:
    """Witness (i): base pick vs the corpus champ arm on the selfplay stratum."""
    n = agree = 0
    for r in rows:
        if r["stratum"] != "selfplay" or r["champ_action"] is None:
            continue
        pb = r["picks"].get(base)
        if pb is None:
            continue
        n += 1
        agree += int(int(pb) == int(r["champ_action"]))
    return {"n": n, "agree": agree, "rate": (agree / n) if n else float("nan")}


def vart_base_agreement(rows: list, base: str = BASE_ID) -> dict:
    """Witness (ii): this run's base pick vs THE VART's own base record for the
    same rid (identical code path, identical seeds, identical k8x1376 budget —
    so any disagreement is a harness alarm, not a finding)."""
    n = agree = 0
    missing = 0
    for r in rows:
        pb = r["picks"].get(base)
        if pb is None:
            continue
        p = VART_RECORDS / f"{r['rid']}.json"
        if not p.is_file():
            missing += 1
            continue
        try:
            vrec = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            missing += 1
            continue
        entry = (vrec.get("picks") or {}).get("1376")
        if vrec.get("error") or entry is None:
            missing += 1
            continue
        n += 1
        agree += int(int(entry["action"]) == int(pb))
    return {"n": n, "agree": agree, "missing": missing,
            "rate": (agree / n) if n else float("nan")}


# --------------------------------------------------------------------------- #
# adjudication (READ_RULE §5) — first match wins                               #
# --------------------------------------------------------------------------- #
def clears(s: dict, denom: float) -> bool:
    """B1 ∧ B2 ∧ B3."""
    if s["z"] != s["z"] or denom != denom or denom <= 0:
        return False
    return (s["z"] >= BAR_Z
            and (s["mean_capture"] / denom) >= BAR_CAPTURE_RATIO
            and s["coverage"] >= BAR_COVERAGE)


def adjudicate(stats_by_id: dict, counters: dict, n_slice: int,
               denom: float) -> dict:
    """W-0 -> W-HARMFUL -> W-FLAT -> W-FUND-WORLDS / W-FUND-AMBIG /
    W-BUDGET-ONLY."""
    esc = [s for i, s in stats_by_id.items() if i != BASE_ID]
    err_frac = counters.get("search_error", 0) / max(n_slice, 1)
    base_cov = (stats_by_id[BASE_ID]["n_base_resolved"] / n_slice
                if n_slice else 0.0)
    if counters.get("checksum_error", 0) > 0 or err_frac > BAR_ERROR_FRAC \
            or base_cov < BAR_COVERAGE:
        return {"branch": "W-0 UNREADABLE",
                "why": {"checksum_errors": counters.get("checksum_error", 0),
                        "error_frac": err_frac, "base_resolution": base_cov}}
    if any(s["z"] == s["z"] and s["z"] <= -BAR_Z for s in esc):
        return {"branch": "W-HARMFUL",
                "why": {"harmful_rungs": [s["id"] for s in esc
                                          if s["z"] == s["z"] and s["z"] <= -BAR_Z]}}
    passing = [s for s in esc if clears(s, denom)]
    if not passing:
        return {"branch": "W-FLAT"}
    # smallest TOTAL budget clears; ties broken toward the smaller k (READ_RULE §4)
    named = min(passing, key=lambda s: (s["total_sims"], s["k_dets"]))["id"]
    iso = [s for s in esc if s["class"] == "isobudget"]
    iso_clear = [s["id"] for s in iso if clears(s, denom)]
    iso_z = [s["z"] for s in iso if s["z"] == s["z"]]
    best_iso_z = max(iso_z) if iso_z else float("nan")
    if iso_clear:
        return {"branch": "W-FUND-WORLDS", "named_rung": named,
                "iso_budget_clearing": iso_clear, "best_iso_z": best_iso_z,
                "attribution": "WORLDS"}
    if best_iso_z == best_iso_z and best_iso_z > BAR_AMBIG_Z:
        return {"branch": "W-FUND-AMBIG", "named_rung": named,
                "best_iso_z": best_iso_z, "attribution": "UNSEPARATED"}
    return {"branch": "W-BUDGET-ONLY", "named_rung": named,
            "best_iso_z": best_iso_z, "attribution": "BUDGET"}


# --------------------------------------------------------------------------- #
# analyze driver                                                               #
# --------------------------------------------------------------------------- #
def cmd_analyze(rungs) -> dict:
    t = build_table(rungs)
    rows = t["rows"]
    stats = {r[0]: rung_stats(rows, r[0]) for r in rungs}
    dn = denom_stats(rows)
    verdict = adjudicate(stats, t["counters"], t["n_slice"], dn["mean"])
    two_sigma = {}
    for i, s in stats.items():
        if i == BASE_ID or s["se"] != s["se"]:
            continue
        two_sigma[i] = {"pts": 2.0 * s["se"],
                        "elo": TG.elo_chain(2.0 * s["se"]),
                        "elo_low_end_divisor": TG.elo_chain(2.0 * s["se"]) * 3.2 / 5.23}
    out = {
        "schema": SCHEMA, "phase": "analyze", "slice": "dev",
        "read_rule": "measurement/kwidth_ties_20260814/READ_RULE.md",
        "bars": {"capture_ratio": BAR_CAPTURE_RATIO, "z": BAR_Z,
                 "coverage": BAR_COVERAGE, "error_frac": BAR_ERROR_FRAC,
                 "ambig_iso_z": BAR_AMBIG_Z},
        "n_slice": t["n_slice"], "n_rows": len(rows),
        "counters": t["counters"],
        "denom": dn,
        "rungs": {i: {**s, "capture_ratio":
                      (s["mean_capture"] / dn["mean"])
                      if dn["mean"] == dn["mean"] and dn["mean"] > 0
                      else float("nan")}
                  for i, s in stats.items()},
        "two_sigma_resolution": two_sigma,
        "base_agreement_selfplay": base_agreement(rows),
        "base_agreement_vs_vart": vart_base_agreement(rows),
        "verdict": verdict,
        "holdout": "NOT OPENED — this program has no holdout code path "
                   "(READ_RULE §1); the 211-position slice stays unburned.",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (MEAS / "LADDER_READOUT.json").write_text(json.dumps(out, indent=2))
    _write_md(out, MEAS / "LADDER_READOUT.md")
    print(f"[analyze:dev] branch {verdict['branch']}"
          + (f", named rung {verdict.get('named_rung')}"
             if "named_rung" in verdict else ""))
    return out


def _fmt(x, nd=4):
    return "nan" if x != x else f"{x:+.{nd}f}"


FLAT_SENTENCE = (
    "Neither static afterstate functions (two failed menus + the 38% reach "
    "bound), nor deeper same-shape search (the vart, E-FLAT), nor wider "
    "determinization — at increased budget OR at the champion's own budget — "
    "expresses the +0.252 pts/ply oracle spread at leaf-tied plies. With all "
    "three named mechanisms closed, the leading remaining explanation of the "
    "tile-tie signal is a **judge artifact**: the in-family `clair-puct` "
    "oracle's own bias, which only an out-of-family re-pricing can settle.")


def _write_md(r: dict, path: Path) -> None:
    L = [
        "# k-WIDTH / DETERMINIZATION AT TIED PLIES — DEV LADDER READOUT",
        "",
        f"Read-rule: [READ_RULE.md](READ_RULE.md) · design: [DESIGN.md](DESIGN.md) "
        f"(both committed before the run). Generated {r['generated_utc']}.",
        "",
        f"- dev slice positions: **{r['n_slice']}** · analyzed rows: "
        f"**{r['n_rows']}** · counters: `{json.dumps(r['counters'])}`",
        f"- honest base-rung regret (denominator): "
        f"**{_fmt(r['denom']['mean'])} ± {_fmt(r['denom']['se'])} pts/ply** "
        f"(n={r['denom']['n']})",
        f"- witness (i) base pick vs corpus champ pick (selfplay): "
        f"{r['base_agreement_selfplay']['agree']}/{r['base_agreement_selfplay']['n']}",
        f"- witness (ii) base pick vs the VART's own k8x1376 records: "
        f"{r['base_agreement_vs_vart']['agree']}/{r['base_agreement_vs_vart']['n']} "
        f"(missing {r['base_agreement_vs_vart']['missing']})",
        f"- holdout: {r['holdout']}",
        "",
        "| rung | k × sims/det (total) | class | capture [pts/ply] | se | z | "
        "capture ratio | coverage | pick-change (arm) | outside-scored | "
        "median s/pos | deploy mult |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    order = [x[0] for x in RUNGS if x[0] in r["rungs"]]
    for i in order:
        s = r["rungs"][i]
        cfg = f"{s['k_dets']} × {s['sims_per_det']} ({s['total_sims']:,})"
        if i == BASE_ID:
            L.append(f"| **{i}** | {cfg} | base | — | — | — | — | "
                     f"{s['coverage']:.3f} | — | — | {s['secs_median']:.1f} | 1.00 |")
            continue
        star = "**" if s["class"] == "isobudget" else ""
        L.append(
            f"| {star}{i}{star} | {cfg} | {s['class']} | "
            f"{_fmt(s['mean_capture'])} | {_fmt(s['se'])} | {_fmt(s['z'], 2)} | "
            f"{_fmt(s['capture_ratio'], 3)} | {s['coverage']:.3f} | "
            f"{s['pick_change_rate_arm']:.3f} | {s['outside_scored_rate']:.3f} | "
            f"{s['secs_median']:.1f} | {s['deploy_multiplier_est']:.2f} |")
    v = r["verdict"]
    L += ["", f"## Verdict: **{v['branch']}**", ""]
    if v["branch"] == "W-FLAT":
        L += ["Mandatory sentence (READ_RULE §6): *" + FLAT_SENTENCE + "*", ""]
    if "attribution" in v:
        L += [f"**Attribution: {v['attribution']}** — named rung "
              f"`{v.get('named_rung')}`; iso-budget rungs clearing: "
              f"`{v.get('iso_budget_clearing', [])}`; best iso-budget z "
              f"{_fmt(v.get('best_iso_z', float('nan')), 2)}.", ""]
    if r["two_sigma_resolution"]:
        L += ["### Realized 2σ resolution (READ_RULE §7)", "",
              "| rung | 2σ [pts/ply] | 2σ [elo, ÷3.2] | 2σ [elo, ÷5.23 low-end] |",
              "|---|---|---|---|"]
        for i in order:
            if i in r["two_sigma_resolution"]:
                t = r["two_sigma_resolution"][i]
                L.append(f"| {i} | {t['pts']:.4f} | {t['elo']:+.1f} | "
                         f"{t['elo_low_end_divisor']:+.1f} |")
        L.append("")
    L += ["⚠️ Wall-clock ratios are indicative only (DESIGN §7.7); absolutes "
          "are not a bench.",
          "",
          "⚠️ World duplication (DESIGN §7.3): late positions cannot deal 64 "
          "distinct worlds from a small unseen deck, so R3 (and to a lesser "
          "extent R2/C2) is a weakly-increasing evidence set late — a bias "
          "toward FLAT at the top of the ladder.",
          ""]
    path.write_text("\n".join(L))


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--profile", choices=("walled", "fixed_v1", "app_aug2"))
    ap.add_argument("--rungs", default=",".join(r[0] for r in RUNGS),
                    help="rung ids, comma separated (default all)")
    ap.add_argument("--workers", type=int, default=22)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--nice", type=int, default=19)
    args = ap.parse_args(argv)
    ids = [x.strip() for x in str(args.rungs).split(",") if x.strip()]
    assert BASE_ID in ids, "the base rung R0 must always be present"
    rungs = tuple(rung_by_id(i) for i in ids)

    if args.search:
        if not args.profile:
            raise SystemExit("--search needs --profile")
        return cmd_search(args.profile, args.workers, rungs, args.limit,
                          args.nice)
    if args.analyze:
        cmd_analyze(rungs)
        return 0
    raise SystemExit("pass --search or --analyze")


if __name__ == "__main__":
    raise SystemExit(main())
