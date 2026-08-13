#!/usr/bin/env python3
"""Merge two J-rules E4-replay output directories into ONE rollup, with a CRN identity proof.

    merge_calib_dirs.py --dir calib --dir calib_d0p25 -o calib_merged

Why this exists: CALIB_READ_RULE §3.1 says the pre-committed dose-0.25 rung is measured by
"an added `--arm` over the same output directory". **That mechanism is unsound and the
instrument now refuses it**: resume is per-PLY, not per-arm, so an already-graded ply is
never re-searched and a late-added arm would carry no pick on any of them — rolling up as a
0.00% flip rate, a perfect silent null wearing the shape of a real measurement. The rung is
therefore measured in a FRESH output directory (same corpus, same seed, same budget, the
champion arm re-run there) and merged here.

The substance of §3.1 is preserved exactly, and this script PROVES it rather than asserting
it: for every archive it diffs the two runs ply-by-ply and requires

  * the same graded plies (same `ply` set),
  * the same `champ_pick` on every one of them  <- the CRN identity proof,
  * the same `phase`, `k_remaining`, `n_legal`, `action_played`,
  * the same deck seed, rules profile, budget and replay checksum.

Any disagreement aborts: two runs that disagree on the champion's own pick are not the same
determinized worlds, and merging them would silently compare arms across different searches.

Merges nothing else. No games, no band, no governance write.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_INSTRUMENT = REPO / "scripts" / "classical_search" / "jrules_e4_replay.py"

#: Per-ply fields that must agree between runs (beyond the champion's pick).
PLY_INVARIANTS = ("phase", "k_remaining", "n_legal", "action_played")
#: Per-game fields that must agree between runs.
GAME_INVARIANTS = ("deck_seed", "rules_profile", "human_player", "champion_seat",
                   "n_graded", "n_plies_total", "recorded_scores", "replay_scores_match",
                   "leaf_hash_production", "seed", "partial")


def load_instrument():
    spec = importlib.util.spec_from_file_location("jrules_e4_replay", _INSTRUMENT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def read_dir(d: Path) -> tuple:
    """-> ({stem: game_summary}, {stem: {ply: ply_record}})"""
    games = {p.name[len("game_"):-len(".json")]: json.loads(p.read_text())
             for p in sorted(d.glob("game_*.json"))}
    plies = {}
    for stem in games:
        pp = d / f"plies_{stem}.jsonl"
        recs = {}
        if pp.exists():
            for line in pp.open():
                if line.strip():
                    r = json.loads(line)
                    recs[int(r["ply"])] = r
        plies[stem] = recs
    return games, plies


def check_crn(stems, plies_by_dir, labels) -> dict:
    """Prove the runs searched identical worlds. Raises SystemExit on any disagreement."""
    base_lbl, base = labels[0], plies_by_dir[0]
    proof = {"archives": len(stems), "plies_compared": 0, "champ_picks_compared": 0}
    for stem in stems:
        b = base[stem]
        for lbl, other in zip(labels[1:], plies_by_dir[1:]):
            o = other[stem]
            if set(b) != set(o):
                raise SystemExit(
                    f"CRN PROOF FAILED on {stem}: {base_lbl} graded plies {sorted(set(b)-set(o))[:5]}"
                    f" that {lbl} did not (or vice versa: {sorted(set(o)-set(b))[:5]}). The two "
                    "runs did not grade the same decisions; refusing to merge.")
            for ply, rb in b.items():
                ro = o[ply]
                if int(rb["champ_pick"]) != int(ro["champ_pick"]):
                    raise SystemExit(
                        f"CRN PROOF FAILED on {stem} ply {ply}: champion picked "
                        f"{rb['champ_pick']} in {base_lbl} and {ro['champ_pick']} in {lbl}. "
                        "The runs are not the same determinized worlds; a merged flip rate "
                        "would compare arms across DIFFERENT searches. Refusing to merge.")
                for f in PLY_INVARIANTS:
                    if rb.get(f) != ro.get(f):
                        raise SystemExit(
                            f"CRN PROOF FAILED on {stem} ply {ply}: {f} = {rb.get(f)!r} in "
                            f"{base_lbl} but {ro.get(f)!r} in {lbl}. Refusing to merge.")
                proof["champ_picks_compared"] += 1
            proof["plies_compared"] += len(b)
    return proof


def merge_games(stems, games_by_dir, labels) -> list:
    merged = []
    for stem in stems:
        base = dict(games_by_dir[0][stem])
        for lbl, other in zip(labels[1:], games_by_dir[1:]):
            g = other[stem]
            for f in GAME_INVARIANTS:
                if base.get(f) != g.get(f):
                    raise SystemExit(
                        f"MERGE ABORTED on {stem}: {f} = {base.get(f)!r} vs {g.get(f)!r} "
                        f"({labels[0]} vs {lbl}). The runs are not the same measurement.")
            if base.get("budget") != g.get("budget"):
                raise SystemExit(f"MERGE ABORTED on {stem}: budgets differ "
                                 f"{base.get('budget')} vs {g.get('budget')}")
            names = {a["name"] for a in base["arms"]}
            for a in g["arms"]:
                if a["name"] in names:
                    raise SystemExit(
                        f"MERGE ABORTED on {stem}: arm {a['name']!r} appears in BOTH "
                        f"{labels[0]} and {lbl}. Merging would double-count it.")
            base["arms"] = base["arms"] + g["arms"]
            base["flips"] = {**base["flips"], **g["flips"]}
            base["flip_plies"] = {**base["flip_plies"], **g["flip_plies"]}
        base["merged_from"] = list(labels)
        merged.append(base)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", action="append", required=True,
                    help="repeatable: an instrument output directory to merge")
    ap.add_argument("-o", "--out-dir", required=True)
    a = ap.parse_args()

    dirs = [Path(d) for d in a.dir]
    if len(dirs) < 2:
        raise SystemExit("pass at least two --dir")
    labels = [d.name for d in dirs]
    games_by_dir, plies_by_dir = [], []
    for d in dirs:
        g, p = read_dir(d)
        if not g:
            raise SystemExit(f"{d}: no game_*.json — nothing to merge")
        games_by_dir.append(g)
        plies_by_dir.append(p)

    stems = sorted(set(games_by_dir[0]))
    for lbl, g in zip(labels[1:], games_by_dir[1:]):
        if set(g) != set(stems):
            raise SystemExit(
                f"MERGE ABORTED: {labels[0]} covers {len(stems)} archives and {lbl} covers "
                f"{len(g)}; the corpora differ ({sorted(set(stems) ^ set(g))[:5]}).")

    proof = check_crn(stems, plies_by_dir, labels)
    merged = merge_games(stems, games_by_dir, labels)

    inst = load_instrument()
    roll = inst.rollup_from_summaries(merged)
    roll["merged_from"] = labels
    roll["crn_proof"] = proof

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for g in merged:
        (out / f"game_{Path(g['archive']).stem}.json").write_text(json.dumps(g, indent=1))
    (out / "SUMMARY.json").write_text(json.dumps(roll, indent=1))
    print(f"[merge] CRN proof: {proof['champ_picks_compared']} champion picks identical "
          f"across {labels} on {proof['archives']} archives")
    for n in roll["flip_rate"]:
        lo, hi = roll["wilson95"][n]
        print(f"[merge] {n:>8}: {roll['flips_total'][n]:>5}/{roll['n_graded_plies']} = "
              f"{100*roll['flip_rate'][n]:6.2f}%  [{100*lo:5.2f}%, {100*hi:5.2f}%]")
    print(f"[merge] wrote {out/'SUMMARY.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
