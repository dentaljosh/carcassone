#!/usr/bin/env python3
"""OM-D2 — adjudicate the four pre-registered gates against the honest-mask rerun.

Read-only. Joins the banked (memoised-mask) census against the fixed-key rerun on
`(corpus, deck_seed, ply)` and grades `G-HONEST` / `G-DIRECTION` / `G-TOP1` /
`G-RATE` exactly as `FINDING.md` §5 pre-registered them.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

BANK = REPO / "measurement" / "tiearb_widening_20260817" / "census"
RERUN = Path("/home/doctor/projects/carcassone/.claude/worktrees/"
             "agent-abfe6c58e4ad5ba70/measurement/legal_cache_key_20260830/rerun_tiletie")


def wilson(k: int, n: int, z: float = 1.959963984540054):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, c - h, c + h)


def load_rows(path: Path, corpus: str | None = None) -> dict:
    out = {}
    with path.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            d = json.loads(line)
            if corpus is not None and d.get("corpus") != corpus:
                continue
            out[(d["corpus"], d["deck_seed"], d["ply"])] = d
    return out


def compare(bank: dict, rerun: dict, fields: tuple) -> dict:
    keys = set(bank) & set(rerun)
    res = {
        "n_bank": len(bank), "n_rerun_same_corpus": len(rerun),
        "n_joined": len(keys),
        "bank_only": len(set(bank) - set(rerun)),
        "rerun_only": len(set(rerun) - set(bank)),
        "rows_moved": 0, "tie_exact_moved": 0,
        "false_untied": 0, "false_tied": 0,
        "top1_moved": 0, "gap_moved": 0, "tie_size_moved": 0,
        "n_legal_moved": 0,
        "tie_size_delta_hist": {},
        "moved_examples": [],
    }
    for k in keys:
        b, r = bank[k], rerun[k]
        if any(b.get(f) != r.get(f) for f in fields):
            res["rows_moved"] += 1
            if len(res["moved_examples"]) < 8:
                res["moved_examples"].append({
                    "key": list(k),
                    "bank": {f: b.get(f) for f in fields},
                    "rerun": {f: r.get(f) for f in fields},
                })
        if b.get("tie_exact") != r.get("tie_exact"):
            res["tie_exact_moved"] += 1
            if not b.get("tie_exact") and r.get("tie_exact"):
                res["false_untied"] += 1
            else:
                res["false_tied"] += 1
        if b.get("top1") != r.get("top1"):
            res["top1_moved"] += 1
        if b.get("gap") != r.get("gap"):
            res["gap_moved"] += 1
        if b.get("tie_size_exact") != r.get("tie_size_exact"):
            res["tie_size_moved"] += 1
            d = int(r.get("tie_size_exact", 0)) - int(b.get("tie_size_exact", 0))
            res["tie_size_delta_hist"][str(d)] = res["tie_size_delta_hist"].get(str(d), 0) + 1
        if b.get("n_legal") != r.get("n_legal"):
            res["n_legal_moved"] += 1
    res["top1_unmoved_fraction"] = (
        1.0 - res["top1_moved"] / res["n_joined"] if res["n_joined"] else 1.0)
    return res


def main() -> int:
    out = {"schema": "carcassonne-omd2-rerun-adjudication/v1",
           "bank": str(BANK), "rerun": str(RERUN)}

    # ---------------- TILE ---------------------------------------------------
    tb = load_rows(BANK / "tile_gap_rows.jsonl")
    tr = load_rows(RERUN / "tile_gap_rows.jsonl", corpus="champ449")
    tf = ("tie_exact", "tie_size_exact", "top1", "top2", "gap", "n_legal")
    tile = compare(tb, tr, tf)
    out["tile"] = tile

    # rates, banked vs rerun (champ449, the comparable population)
    def rate(rows):
        n = len(rows)
        k = sum(1 for r in rows.values() if r["tie_exact"])
        p, lo, hi = wilson(k, n)
        return {"n_rows": n, "n_tied": k, "frac": p, "wilson_lo": lo, "wilson_hi": hi,
                "per_game_449": k / 449.0}

    out["tile_rate_bank_champ449"] = rate(tb)
    out["tile_rate_rerun_champ449"] = rate(tr)

    # pooled rerun (both corpora) — reported, not compared
    tr_all = load_rows(RERUN / "tile_gap_rows.jsonl")
    n_all = len(tr_all)
    k_all = sum(1 for r in tr_all.values() if r["tie_exact"])
    p, lo, hi = wilson(k_all, n_all)
    out["tile_rate_rerun_pooled_1299"] = {
        "n_rows": n_all, "n_tied": k_all, "frac": p, "wilson_lo": lo, "wilson_hi": hi,
        "per_game_1299": k_all / 1299.0}
    del tr_all

    # ---------------- the 10 OM-D2 witnesses ---------------------------------
    wd = json.loads((HERE / "WITNESS_DIFFS.json").read_text())
    wit = []
    for w in wd["witnesses"]:
        k = ("champ449", w["deck_seed"], w["ply"])
        r = tr.get(k)
        wit.append({
            "deck_seed": w["deck_seed"], "ply": w["ply"],
            "bank_tie_exact": w["banked_census_tie_exact"],
            "rerun_tie_exact": None if r is None else r["tie_exact"],
            "rerun_tie_size": None if r is None else r["tie_size_exact"],
            "honest_replay_tie_exact": w["py_nocache_tie_exact"],
            "honest_replay_top1": w["py_nocache_top1"],
            "rerun_top1": None if r is None else r["top1"],
            "top1_matches_honest_replay": (
                r is not None and r["top1"] == w["py_nocache_top1"]),
            "rust_fired": w["rust_fired"],
        })
    out["witnesses"] = wit
    out["witnesses_all_tied_in_rerun"] = all(x["rerun_tie_exact"] for x in wit)
    out["witnesses_top1_match"] = all(x["top1_matches_honest_replay"] for x in wit)

    # ---------------- the 9 witness games, row for row -----------------------
    dr = json.loads((HERE / "DEFECT_RATE.json").read_text())
    pred_ok = pred_bad = 0
    mism = []
    for g in dr["per_game"]:
        s = g["deck_seed"]
        for m in g["moved"]:
            r = tr.get(("champ449", s, m["ply"]))
            h = m["honest"]
            if r is not None and r["tie_exact"] == h["tie_exact"] \
                    and r["tie_size_exact"] == h["tie_size_exact"] \
                    and r["top1"] == h["top1"] and r["gap"] == h["gap"]:
                pred_ok += 1
            else:
                pred_bad += 1
                if len(mism) < 5:
                    mism.append({"deck_seed": s, "ply": m["ply"], "predicted": h,
                                 "rerun": None if r is None else
                                 {k2: r[k2] for k2 in ("tie_exact", "tie_size_exact",
                                                       "top1", "gap")}})
    out["honest_replay_prediction"] = {
        "n_predicted_moved_rows": pred_ok + pred_bad,
        "reproduced": pred_ok, "mismatched": pred_bad, "mismatches": mism}

    # ---------------- MEEPLE -------------------------------------------------
    mb = load_rows(BANK / "meeple_rows.jsonl")
    mr = load_rows(RERUN / "meeple_rows.jsonl")
    mf = ("tie_exact", "tie_size_exact", "top1", "top2", "gap", "n_legal",
          "argmax_action", "played_is_argmax")
    out["meeple"] = compare(mb, mr, mf)
    out["meeple_rate_bank"] = rate(mb)
    out["meeple_rate_rerun"] = rate(mr)

    # headline JSONs
    for label, p2 in (("bank", BANK / "MEEPLE_CENSUS.json"),
                      ("rerun", RERUN / "MEEPLE_CENSUS.json")):
        d = json.loads(p2.read_text())
        out[f"census_json_{label}"] = {
            "n_meeple_rows": d.get("n_meeple_rows"),
            "n_tile_rows": d.get("n_tile_rows"),
            "branch_hint": d.get("branch_hint"),
            "eps_piggyback_tile": d.get("eps_piggyback_tile"),
            "groups_keys": sorted(d.get("groups", {}).keys())[:20],
        }

    (HERE / "RERUN_ADJUDICATION.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("witnesses", "census_json_bank",
                                   "census_json_rerun")}, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
