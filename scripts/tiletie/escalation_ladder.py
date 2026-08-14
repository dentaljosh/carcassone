#!/usr/bin/env python3
"""TIE-TRIGGERED SEARCH ESCALATION — the pre-gate ladder
(measurement/tieescalation_20260814/DESIGN.md + READ_RULE.md, committed BEFORE
this ran; Joshua 2026-08-14: "if theres a tie at search 11k, search like 10x
in those cases?").

At every pricing-corpus leaf-tied position, run the production champion search
(fair PIMC, rust, k = 8 from PRODUCTION.yaml) at escalation rungs
sims/det ∈ {1376, 2752, 4×, 10×} — sims-per-det scaled, k FIXED, so the 8
dealt worlds are identical across rungs (`det_seed_base(seed, move_idx)` does
not depend on sims) and any pick change is attributable to per-world depth
alone. Join each rung's pick onto the corpus's own CRN deep scores (M=32
worlds per arm) and measure how much of the base rung's honest oracle regret
escalation captures.

Search conventions are champ_picks.py's, clone-for-clone (which are
mine_disagreements._search_pick's): `make_production_champion("fair", ...,
seed=match.agent_seed(deck_seed, seat), verify=True)` with `sims=<rung>` the
only override; `mirror_protocol.reseat(..., move_idx=ply)` mandatory;
`resolve_execution("inherit", profile="desktop", rust_threads=1)`; root
replayed via `root_replay.replay_actions` and checksum-asserted BEFORE any
search. One process per rules profile (CARCASSONNE_FIX_R9 is import-latched).

Phases:
  --search --profile P [--slice dev|holdout] [--rungs 1376,2752,...]
      per-position records -> measurement/tieescalation_20260814/records/
      (resume-able; best-effort per position, never takes the pool down)
  --analyze [--slice dev]
      the READ_RULE §2 statistics + §4 branch -> LADDER_READOUT.{md,json}
  --analyze --slice holdout --named-rung R
      the one-shot confirm -> HOLDOUT_CONFIRM.{md,json}. REFUSES to run
      unless LADDER_READOUT.json exists with branch E-FUND-DEV naming R.

Dev/holdout discipline: the holdout roots of
measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json are excluded from every
dev phase; the holdout search/analyze runs only the branch the read-rule
fires. The analyzer asserts the dev table contains no holdout rid.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
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

import term_gate as TG  # noqa: E402  (corpus paths, cluster_se — no engine import)

SCHEMA = "carcassonne-tieescalation-ladder/v1"
MEAS = REPO / "measurement" / "tieescalation_20260814"
RECORDS_DIR = MEAS / "records"
HOLDOUT_PATH = REPO / "measurement" / "tiletie_mining_20260814" / "HOLDOUT_ROOTS.json"
AFTERSTATE_MAP_DIR = TG.PRICING / "census"

RUNGS = (1376, 2752, 5504, 13760)
BASE_RUNG = 1376

#: READ_RULE §3 bars — frozen here, committed before any number existed.
BAR_CAPTURE_RATIO = 0.35
BAR_Z = 2.0
BAR_COVERAGE = 0.85
BAR_ERROR_FRAC = 0.05

#: DESIGN §6 deploy-multiplier constants (census-realized trigger rate; the
#: tile-share-of-turn-search assumption is stated in the readout).
TRIGGER_RATE = 0.660
TILE_SEARCH_SHARE = 0.5


# --------------------------------------------------------------------------- #
# slices                                                                       #
# --------------------------------------------------------------------------- #
def load_holdout_roots() -> set:
    return set(json.loads(HOLDOUT_PATH.read_text())["holdout_roots"])


def slice_rids(per: dict, which: str) -> list:
    """rids of one slice, sorted. `per` = term_gate.load_per_position()."""
    hold = load_holdout_roots()
    if which == "dev":
        keep = [r for r, row in per.items() if row["root_id"] not in hold]
    elif which == "holdout":
        keep = [r for r, row in per.items() if row["root_id"] in hold]
    else:
        raise ValueError(f"slice must be dev|holdout, got {which!r}")
    return sorted(keep)


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
        for s in rungs:
            t0 = time.time()
            champ = make_production_champion(
                "fair", game=game, seed=seed, verify=True, sims=int(s),
                **ex.factory_kwargs())
            MP.reseat(champ, deck_seed=int(deck_seed),
                      actions=[int(a) for a in actions[:ply]], move_idx=int(ply))
            action = int(champ.choose_action(board))
            fd = champ.manifest.get("runtime_budget_override") \
                or champ.manifest.get("fair_deploy", {})
            rec["picks"][str(int(s))] = {
                "action": action, "secs": round(time.time() - t0, 3),
                "k_dets": int(fd.get("k_dets", 0)),
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
    return all(str(int(s)) in rec.get("picks", {}) for s in rungs)


def cmd_search(profile: str, workers: int, which: str, rungs, limit: int,
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
    rids = [r for r in slice_rids(per, which)
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
                     row["checksum"], tuple(int(s) for s in rungs)))
    if limit and int(limit) > 0:
        jobs = jobs[: int(limit)]
    print(f"[escalation:{profile}:{which}] {len(rids)} rids in slice, "
          f"{len(jobs)} to search (rungs {list(rungs)})", flush=True)

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
        "schema": SCHEMA, "phase": "search", "profile": profile, "slice": which,
        "rungs": [int(s) for s in rungs], "workers": int(workers),
        "n_slice_rids": len(rids), "n_searched": len(jobs), "n_error": n_err,
        "wall_secs": round(time.time() - t0, 1),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (MEAS / f"manifest_search_{profile}_{which}.json").write_text(
        json.dumps(manifest, indent=2))
    print(f"[escalation:{profile}:{which}] done, {n_err} errors, "
          f"{manifest['wall_secs']}s", flush=True)
    return 1 if n_err else 0


# --------------------------------------------------------------------------- #
# oracle values (full per-world lists) + transposition maps                    #
# --------------------------------------------------------------------------- #
def load_oracle_values(rids, arms: dict):
    """rid -> list-of-lists: per arm, the 32 CRN world values, aligned with
    arms[rid]['arms']. Same integrity contract as term_gate.load_oracle_means
    (every leg present, pick_a/pick_b aligned) but keeps the raw lists so the
    parity-split honest regret can be computed. Record files whose rid is not
    in `rids` are NEVER PARSED (the holdout firewall by filename)."""
    want = set(rids)
    recs = defaultdict(dict)
    for f in glob.glob(f"{TG.RECORDS_ROOT}/*/*/records/*.json"):
        rid = Path(f).stem
        if rid not in want:
            continue
        leg = f.split("/")[-3]
        recs[rid][leg] = json.loads(Path(f).read_text())
    out, problems = {}, []
    for rid in sorted(want):
        a = arms[rid]["arms"]
        got = recs.get(rid, {})
        if len(got) != len(a) - 1:
            problems.append((rid, "missing_legs"))
            continue
        ok = all(got[f"leg{i}"]["pick_b"] == a[i] and got[f"leg{i}"]["pick_a"] == a[0]
                 for i in range(1, len(a)))
        if not ok:
            problems.append((rid, "arm_mismatch"))
            continue
        vals = [[float(v) for v in got["leg1"]["values_a"]]]
        for i in range(1, len(a)):
            vals.append([float(v) for v in got[f"leg{i}"]["values_b"]])
        out[rid] = vals
    return out, problems


def load_action_repr_maps() -> dict:
    """bp_rid -> {action: representative_action} from the census afterstate
    transposition maps (all profiles). A pick that is a board-duplicate of a
    scored arm has the scored arm's oracle value BY IDENTITY."""
    out = {}
    for f in sorted(glob.glob(str(AFTERSTATE_MAP_DIR / "afterstate_map_*.json"))):
        d = json.loads(Path(f).read_text())
        for row in d.get("rows", []):
            m = {}
            for group, rep in zip(row.get("action_groups", []),
                                  row.get("repr_actions", [])):
                for act in group:
                    m[int(act)] = int(rep)
            out[row["bp_rid"]] = m
    return out


def resolve_pick(pick, arm_actions: list, repr_map: dict | None):
    """action -> index into arm_actions, via exact membership then the
    transposition map. None = unresolved (outside the scored set)."""
    if pick is None:
        return None
    pick = int(pick)
    if pick in arm_actions:
        return arm_actions.index(pick)
    if repr_map:
        rep = repr_map.get(pick)
        if rep is not None and rep in arm_actions:
            return arm_actions.index(rep)
    return None


# --------------------------------------------------------------------------- #
# statistics (READ_RULE §2)                                                    #
# --------------------------------------------------------------------------- #
def _mean(vals) -> float:
    return math.fsum(vals) / len(vals)


def honest_regret(values: list, base_idx: int) -> float:
    """Symmetrized parity-split honest regret of the base pick [pts, unscaled]:
    split the M worlds by index parity; on each direction select the argmax
    arm on the selection half and price (selected − base) on the evaluation
    half; average both directions. Symmetric in the halves, so the pricing
    run's I1 parity-base ambiguity cannot matter."""
    halves = ([j for j in range(len(values[0])) if j % 2 == 0],
              [j for j in range(len(values[0])) if j % 2 == 1])
    out = []
    for sel, ev in (halves, halves[::-1]):
        sel_means = [_mean([v[j] for j in sel]) for v in values]
        a_star = max(range(len(values)), key=lambda i: sel_means[i])
        out.append(_mean([values[a_star][j] for j in ev])
                   - _mean([values[base_idx][j] for j in ev]))
    return (out[0] + out[1]) / 2.0


def build_table(which: str, rungs) -> dict:
    """Join search records + arms + oracle values + per_position for one slice.
    Returns the analysis table plus integrity counters."""
    per = TG.load_per_position()
    arms = json.loads(TG.ARMS_JSON.read_text())
    rids = slice_rids(per, which)
    hold = load_holdout_roots()
    if which == "dev":
        assert not any(per[r]["root_id"] in hold for r in rids), \
            "holdout rid leaked into the dev table"
    oracle, problems = load_oracle_values(rids, arms)
    repr_maps = load_action_repr_maps()

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
        picks, idxs = {}, {}
        for s in rungs:
            entry = rec["picks"].get(str(int(s)))
            if entry is None:
                counters[f"missing_rung_{s}"] += 1
                continue
            picks[int(s)] = int(entry["action"])
            idxs[int(s)] = resolve_pick(entry["action"], a, rmap)
        rows.append({
            "rid": rid, "root_id": per[rid]["root_id"],
            "stratum": per[rid]["stratum"],
            "profile": per[rid]["rules_profile"],
            "phase": per[rid]["phase_bucket"],
            "scale_all": float(per[rid]["scale_all"]),
            "arms": a, "values": oracle[rid],
            "champ_action": arms[rid].get("champ_action"),
            "picks": picks, "idxs": idxs,
            "secs": {int(s): rec["picks"][str(int(s))]["secs"]
                     for s in rungs if str(int(s)) in rec["picks"]},
        })
    counters["oracle_integrity_problems"] = len(problems)
    return {"rows": rows, "counters": dict(counters), "n_slice": len(rids),
            "problems": problems}


def rung_stats(rows: list, rung: int, base: int = BASE_RUNG) -> dict:
    """READ_RULE §2 statistics for one escalation rung vs base."""
    num, clusters = [], []
    n_pair = n_base_res = n_rung_unres = n_change_arm = n_change_act = 0
    secs = []
    for r in rows:
        bi = r["idxs"].get(base)
        ri = r["idxs"].get(rung)
        if rung in r["secs"]:
            secs.append(r["secs"][rung])
        if bi is None:
            continue
        n_base_res += 1
        if ri is None:
            n_rung_unres += 1
            continue
        n_pair += 1
        means = [_mean(v) for v in r["values"]]
        num.append((means[ri] - means[bi]) * r["scale_all"])
        clusters.append(r["root_id"])
        if ri != bi:
            n_change_arm += 1
        if r["picks"].get(rung) != r["picks"].get(base):
            n_change_act += 1
    n_rows = len(rows)
    mean_capture = _mean(num) if num else float("nan")
    se = TG.cluster_se(num, clusters) if len(set(clusters)) > 1 else float("nan")
    secs_sorted = sorted(secs)
    return {
        "rung": rung, "n_pairs": n_pair, "n_base_resolved": n_base_res,
        "coverage": (n_pair / n_rows) if n_rows else float("nan"),
        "mean_capture": mean_capture, "se": se,
        "z": (mean_capture / se) if (num and se and se == se and se > 0)
             else float("nan"),
        "pick_change_rate_arm": (n_change_arm / n_pair) if n_pair else float("nan"),
        "pick_change_rate_action": (n_change_act / n_pair) if n_pair else float("nan"),
        "outside_scored_rate": (n_rung_unres / n_base_res) if n_base_res
                               else float("nan"),
        "secs_mean": _mean(secs) if secs else float("nan"),
        "secs_median": (secs_sorted[len(secs_sorted) // 2] if secs
                        else float("nan")),
    }


def denom_stats(rows: list, base: int = BASE_RUNG) -> dict:
    """The honest base-rung regret (READ_RULE §2 `denom`) over the
    base-resolved population."""
    vals, clusters = [], []
    for r in rows:
        bi = r["idxs"].get(base)
        if bi is None:
            continue
        vals.append(honest_regret(r["values"], bi) * r["scale_all"])
        clusters.append(r["root_id"])
    m = _mean(vals) if vals else float("nan")
    se = TG.cluster_se(vals, clusters) if len(set(clusters)) > 1 else float("nan")
    return {"mean": m, "se": se, "n": len(vals)}


def base_agreement(rows: list, base: int = BASE_RUNG) -> dict:
    """Integrity witness: base-rung fresh pick vs the corpus champ arm, on the
    selfplay stratum (same seed convention => expected ~1.0 modulo code-rev
    drift). Reported, never a gate."""
    n = agree = 0
    for r in rows:
        if r["stratum"] != "selfplay" or r["champ_action"] is None:
            continue
        pb = r["picks"].get(base)
        if pb is None:
            continue
        n += 1
        agree += int(int(pb) == int(r["champ_action"]))
    return {"n": n, "agree": agree,
            "rate": (agree / n) if n else float("nan")}


# --------------------------------------------------------------------------- #
# adjudication (READ_RULE §4)                                                  #
# --------------------------------------------------------------------------- #
def adjudicate(stats_by_rung: dict, counters: dict, n_slice: int,
               denom: float) -> dict:
    """First match wins: E-0 -> E-HARMFUL -> E-FLAT / E-FUND-DEV."""
    esc = [s for r, s in sorted(stats_by_rung.items()) if r != BASE_RUNG]
    err_frac = counters.get("search_error", 0) / max(n_slice, 1)
    base_cov = (stats_by_rung[BASE_RUNG]["n_base_resolved"] / n_slice
                if n_slice else 0.0)
    if counters.get("checksum_error", 0) > 0 or err_frac > BAR_ERROR_FRAC \
            or base_cov < BAR_COVERAGE:
        return {"branch": "E-0 UNREADABLE",
                "why": {"checksum_errors": counters.get("checksum_error", 0),
                        "error_frac": err_frac, "base_resolution": base_cov}}
    if any(s["z"] == s["z"] and s["z"] <= -BAR_Z for s in esc):
        return {"branch": "E-HARMFUL"}
    passing = [s for s in esc
               if s["z"] == s["z"] and s["z"] >= BAR_Z
               and denom == denom and denom > 0
               and (s["mean_capture"] / denom) >= BAR_CAPTURE_RATIO
               and s["coverage"] >= BAR_COVERAGE]
    if not passing:
        return {"branch": "E-FLAT"}
    named = min(p["rung"] for p in passing)          # SMALLEST, never argmax
    return {"branch": "E-FUND-DEV", "named_rung": named}


def adjudicate_holdout(z_hold: float) -> str:
    if z_hold >= BAR_Z:
        return "E-CONFIRMED"
    if z_hold > 0:
        return "E-WEAK"
    return "E-REFUTED"


def deploy_multiplier(rung: int, base: int = BASE_RUNG) -> float:
    return 1.0 + TRIGGER_RATE * TILE_SEARCH_SHARE * (rung / base - 1.0)


# --------------------------------------------------------------------------- #
# analyze drivers                                                              #
# --------------------------------------------------------------------------- #
def cmd_analyze_dev(rungs) -> dict:
    t = build_table("dev", rungs)
    rows = t["rows"]
    stats = {int(s): rung_stats(rows, int(s)) for s in rungs}
    dn = denom_stats(rows)
    verdict = adjudicate(stats, t["counters"], t["n_slice"], dn["mean"])
    out = {
        "schema": SCHEMA, "phase": "analyze", "slice": "dev",
        "read_rule": "measurement/tieescalation_20260814/READ_RULE.md",
        "bars": {"capture_ratio": BAR_CAPTURE_RATIO, "z": BAR_Z,
                 "coverage": BAR_COVERAGE, "error_frac": BAR_ERROR_FRAC},
        "n_slice": t["n_slice"], "n_rows": len(rows),
        "counters": t["counters"],
        "denom": dn,
        "rungs": {str(r): {**s, "capture_ratio":
                           (s["mean_capture"] / dn["mean"])
                           if dn["mean"] == dn["mean"] and dn["mean"] > 0
                           else float("nan"),
                           "deploy_multiplier_est": deploy_multiplier(r)}
                  for r, s in stats.items()},
        "base_agreement_selfplay": base_agreement(rows),
        "verdict": verdict,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (MEAS / "LADDER_READOUT.json").write_text(json.dumps(out, indent=2))
    _write_md(out, MEAS / "LADDER_READOUT.md")
    print(f"[analyze:dev] branch {verdict['branch']}"
          + (f", named rung {verdict.get('named_rung')}"
             if "named_rung" in verdict else ""))
    return out


def cmd_analyze_holdout(named_rung: int) -> dict:
    dev_path = MEAS / "LADDER_READOUT.json"
    if not dev_path.is_file():
        raise SystemExit("REFUSING: no dev LADDER_READOUT.json — the holdout "
                         "confirm is licensed only by a dev E-FUND-DEV.")
    dev = json.loads(dev_path.read_text())
    v = dev.get("verdict", {})
    if v.get("branch") != "E-FUND-DEV" or int(v.get("named_rung", -1)) != int(named_rung):
        raise SystemExit(f"REFUSING: dev verdict is {v} — it does not name "
                         f"rung {named_rung}.")
    rungs = (BASE_RUNG, int(named_rung))
    t = build_table("holdout", rungs)
    rows = t["rows"]
    s = rung_stats(rows, int(named_rung))
    dn = denom_stats(rows)
    branch = adjudicate_holdout(s["z"]) if s["z"] == s["z"] else "E-0 UNREADABLE"
    out = {
        "schema": SCHEMA, "phase": "analyze", "slice": "holdout",
        "named_rung": int(named_rung), "n_slice": t["n_slice"],
        "n_rows": len(rows), "counters": t["counters"],
        "stats": {**s, "capture_ratio": (s["mean_capture"] / dn["mean"])
                  if dn["mean"] == dn["mean"] and dn["mean"] > 0 else float("nan")},
        "denom": dn, "verdict": {"branch": branch},
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (MEAS / "HOLDOUT_CONFIRM.json").write_text(json.dumps(out, indent=2))
    _write_md_holdout(out, MEAS / "HOLDOUT_CONFIRM.md")
    print(f"[analyze:holdout] branch {branch}: capture "
          f"{s['mean_capture']:+.4f} ± {s['se']:.4f} (z {s['z']:+.2f})")
    return out


def _fmt(x, nd=4):
    return "nan" if x != x else f"{x:+.{nd}f}"


def _write_md(r: dict, path: Path) -> None:
    L = [
        "# TIE-TRIGGERED SEARCH ESCALATION — DEV LADDER READOUT",
        "",
        f"Read-rule: [READ_RULE.md](READ_RULE.md) (committed before the run). "
        f"Generated {r['generated_utc']}.",
        "",
        f"- slice positions: **{r['n_slice']}** · analyzed rows: "
        f"**{r['n_rows']}** · counters: `{json.dumps(r['counters'])}`",
        f"- honest base-rung regret (denominator): "
        f"**{_fmt(r['denom']['mean'])} ± {_fmt(r['denom']['se'])} pts/ply** "
        f"(n={r['denom']['n']})",
        f"- base-pick vs corpus champ-pick agreement (selfplay, witness): "
        f"{r['base_agreement_selfplay']['agree']}/{r['base_agreement_selfplay']['n']}",
        "",
        "| rung (sims/det) | capture [pts/ply] | se | z | capture ratio | "
        "coverage | pick-change (arm) | outside-scored | median s/pos | "
        "deploy mult est |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for k in sorted(r["rungs"], key=int):
        s = r["rungs"][k]
        if int(k) == BASE_RUNG:
            L.append(f"| {k} (base) | — | — | — | — | "
                     f"{s['coverage']:.3f} | — | — | {s['secs_median']:.1f} | 1.00 |")
            continue
        L.append(
            f"| {k} | {_fmt(s['mean_capture'])} | {_fmt(s['se'])} | "
            f"{_fmt(s['z'], 2)} | {_fmt(s['capture_ratio'], 3)} | "
            f"{s['coverage']:.3f} | {s['pick_change_rate_arm']:.3f} | "
            f"{s['outside_scored_rate']:.3f} | {s['secs_median']:.1f} | "
            f"{s['deploy_multiplier_est']:.2f} |")
    L += ["", f"## Verdict: **{r['verdict']['branch']}**", ""]
    if r["verdict"]["branch"] == "E-FLAT":
        L.append("Mandatory sentence (READ_RULE §4): *neither static "
                 "afterstate functions (two failed menus + the 38% reach "
                 "bound) nor deeper same-shape search expresses the oracle "
                 "spread* — which points at the ORACLE's in-family bias, or "
                 "at k-width/determinization, as the remaining explanations "
                 "of the +0.252 pts/ply.")
    if "named_rung" in r["verdict"]:
        L.append(f"Named rung (SMALLEST clearing the bars): "
                 f"**{r['verdict']['named_rung']} sims/det**. One-shot "
                 f"holdout confirm licensed.")
    L += ["", "⚠️ Wall-clock measured on a contended box (see DESIGN §7); "
          "ratios indicative, absolutes are not a bench.", ""]
    path.write_text("\n".join(L))


def _write_md_holdout(r: dict, path: Path) -> None:
    s = r["stats"]
    path.write_text("\n".join([
        "# TIE-TRIGGERED SEARCH ESCALATION — ONE-SHOT HOLDOUT CONFIRM",
        "",
        f"Named rung: **{r['named_rung']} sims/det** (fired by the dev "
        f"E-FUND-DEV). Generated {r['generated_utc']}.",
        "",
        f"- holdout positions: {r['n_slice']} · analyzed rows: {r['n_rows']} "
        f"· counters: `{json.dumps(r['counters'])}`",
        f"- capture: **{_fmt(s['mean_capture'])} ± {_fmt(s['se'])} pts/ply "
        f"(z {_fmt(s['z'], 2)})** · ratio {_fmt(s['capture_ratio'], 3)} of "
        f"the holdout honest regret {_fmt(r['denom']['mean'])}",
        f"- coverage {s['coverage']:.3f} · pick-change "
        f"{s['pick_change_rate_arm']:.3f} · outside-scored "
        f"{s['outside_scored_rate']:.3f}",
        "",
        f"## Verdict: **{r['verdict']['branch']}**",
        "",
        "The holdout is now BURNED for this program either way.",
        "",
    ]))


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--profile", choices=("walled", "fixed_v1", "app_aug2"))
    ap.add_argument("--slice", default="dev", choices=("dev", "holdout"))
    ap.add_argument("--rungs", default=",".join(str(s) for s in RUNGS))
    ap.add_argument("--named-rung", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--nice", type=int, default=19)
    args = ap.parse_args(argv)
    rungs = tuple(int(x) for x in str(args.rungs).split(",") if x.strip())
    assert BASE_RUNG in rungs, "the base rung 1376 must always be searched"

    if args.search:
        if not args.profile:
            raise SystemExit("--search needs --profile")
        if args.slice == "holdout" and set(rungs) - {BASE_RUNG} \
                and len(set(rungs)) > 2:
            raise SystemExit("holdout search runs {base, named rung} only")
        return cmd_search(args.profile, args.workers, args.slice, rungs,
                          args.limit, args.nice)
    if args.analyze:
        if args.slice == "dev":
            cmd_analyze_dev(rungs)
        else:
            if not args.named_rung:
                raise SystemExit("--analyze --slice holdout needs --named-rung")
            cmd_analyze_holdout(args.named_rung)
        return 0
    raise SystemExit("pass --search or --analyze")


if __name__ == "__main__":
    raise SystemExit(main())
