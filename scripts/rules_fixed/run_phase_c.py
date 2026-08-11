#!/usr/bin/env python3
"""F9 Phase C runner — the three fixed-rules descriptives, walled vs fixed, one document.

    scripts/rules_fixed/run_phase_c.py REF_CORPUS NEW_CORPUS \
        [--ref-label walled449] [--new-label fixed_v1] [--ref-profile walled] \
        [-o measurement/f9_phase_c] [--workers 4]

REF_CORPUS / NEW_CORPUS are each either a `gen_fair_distill.py --actions-only`
DIR or a games JSONL; both shapes are read by `descriptives.load_corpus`.

Runs the three C-full descriptives of docs/F9_BUILD_SPEC_20260802.md §3 side by
side and writes ONE document, `PHASE_C_DESCRIPTIVES.md`, plus the raw JSONs:

  1. **luck floor** — the σ_game slice obtainable from an unpaired champion-play
     corpus, using `scripts/human_anchor/luck_floor.py`'s own sizing math (that
     module is imported, not reimplemented, so the definitions cannot drift).
     ⚠️ The ICC / σ_pair / paired required-n half of LUCK_FLOOR.md needs a
     SEAT-SWAP PAIRED archive (`seedNNN_a0.json` + `_a1.json`), which a
     self-play champion corpus is not. That half is reported as NOT DERIVABLE
     here, with what it would take, rather than approximated.
  2. **decision density** — `scripts/rules_fixed/descriptives.py` (this program's
     own instrument; the spec's "no instrument exists" row).
  3. **farm-economy norms** — `scripts/analyzer/corpus_stats.py`, run per corpus.

## Why each leg is a SUBPROCESS

`CARCASSONNE_FIX_R9` latches at `base_deck` import (and in a Rust `OnceLock`), so
one process cannot replay a `walled` corpus (R9 off) and a `fixed_v1` corpus
(R9 on). Each corpus therefore gets its own interpreter with the profile and the
R9 flag published in its environment; this runner only orchestrates and
assembles. Same reason `corpus_stats.py` needs no `--rules-profile` of its own —
`game_wrapper.Game` resolves `rules_profile.active()` from the environment.

## Gate C — anti-cherry-pick

The metric set is fixed by the spec BEFORE any corpus was looked at, and every
metric is printed for both profiles regardless of which direction it moves. No
claim id, no band retirement, no `experiments/results.csv` row, no
`governance/PRODUCTION.yaml` touch. Descriptives only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))

import descriptives as dd  # noqa: E402  (json-only at import; no engine)
import luck_floor as lf    # noqa: E402  (stdlib-only at import)

GATE_C_HEADER = """\
> **Gate C (anti-cherry-pick).** The descriptive set below is PRE-REGISTERED by
> [docs/F9_BUILD_SPEC_20260802.md](../../docs/F9_BUILD_SPEC_20260802.md) §3 —
> luck floor, decision density, farm-economy norms — and was fixed before either
> corpus was looked at. **Every metric is reported for both profiles regardless
> of direction.** Descriptives carry no claim id, retire no band, write no
> `experiments/results.csv` row, and touch no `governance/PRODUCTION.yaml`.
> A descriptive selected *after* seeing it would be a finding laundered as a
> fact; that is what this gate exists to prevent.
"""

CROSS_BAND_RIDER = """\
> ⚠️ **These two corpora are on DIFFERENT deck bands** (different seed ranges), so
> every Δ column below is a CROSS-BAND contrast. CLAUDE.md's standing rule applies:
> cross-band dispersion is 1.8–2.2× the within-band figure, so a Δ here is a
> descriptive difference, not a measured effect. Phase B's transfer-bound cell —
> deck-paired, one fresh band — is the instrument that prices a contrast; this
> document is not.
"""

TARGET_WRS = (0.55, 0.60, 0.65)


# --------------------------------------------------------------------------- #
# leg 1 — the luck-floor slice                                                  #
# --------------------------------------------------------------------------- #
def luck_slice(corpus: dict, label: str) -> dict:
    """σ_game and the seat advantage from a champion-play corpus's own scores.

    Reuses `luck_floor.norm_ppf` / `required_n` so the sizing definitions are the
    ones LUCK_FLOOR.md already publishes. What is NOT derivable from an unpaired
    self-play corpus is returned as None with a reason, never approximated.
    """
    margins, totals, wins = [], [], []
    for g in corpus["games"]:
        if "score_p0" not in g or "score_p1" not in g:
            continue
        s0, s1 = int(g["score_p0"]), int(g["score_p1"])
        margins.append(s0 - s1)
        totals.append(s0 + s1)
        wins.append(0.5 if s0 == s1 else (1.0 if s0 > s1 else 0.0))
    if len(margins) < 2:
        raise dd.CorpusFormatError(
            f"{label}: fewer than 2 games carry recorded scores — no σ_game")
    sigma_game = statistics.pstdev(margins)
    mean_margin = statistics.fmean(margins)
    n = len(margins)
    sizing = {}
    for p in TARGET_WRS:
        n_unpaired, _n_paired, edge = lf.required_n(p, sigma_game, sigma_game)
        sizing[f"{p:.2f}"] = {
            "edge_points_implied": edge,
            "n_games_unpaired_test": n_unpaired,
            "n_games_paired_test": None,
        }
    return {
        "label": label,
        "n_games": n,
        "sigma_game": sigma_game,
        "sigma_game_sem": sigma_game / math.sqrt(2 * (n - 1)),
        "mean_seat0_margin": mean_margin,
        "mean_seat0_margin_sem": sigma_game / math.sqrt(n),
        "seat0_win_rate": statistics.fmean(wins),
        "mean_total_points": statistics.fmean(totals),
        "abs_margin_mean": statistics.fmean([abs(m) for m in margins]),
        "sizing_unpaired": sizing,
        "not_derivable": {
            "luck_share_icc": "needs a SEAT-SWAP PAIRED archive (same deck, both "
                              "seatings, two agents) — a self-play champion corpus "
                              "has one seating per deck.",
            "sigma_pair": "same reason; the paired-margin statistic does not exist "
                          "without the second seating.",
            "n_games_paired_test": "follows from sigma_pair.",
        },
        "how_to_complete": (
            "generate a seat-swap paired eval archive under this rules profile "
            "(the `seedNNN_a0.json` / `_a1.json` shape luck_floor.load_pairs reads) "
            "and add its directory to luck_floor.NEAR_EQUAL, then re-run "
            "scripts/human_anchor/luck_floor.py."),
    }


# --------------------------------------------------------------------------- #
# leg 2/3 — subprocess drivers                                                  #
# --------------------------------------------------------------------------- #
def corpus_env(prof_info: dict) -> dict:
    env = dict(os.environ)
    env["CARCASSONNE_RULES_PROFILE"] = prof_info["name"]
    env["CARCASSONNE_FIX_R9"] = "1" if dd.r9_env_value(prof_info) else "0"
    pp = [str(REPO / "src"), str(REPO / "engine"),
          str(REPO / "scripts" / "measurement_infra")]
    if env.get("PYTHONPATH"):
        pp.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pp)
    return env


def _run(cmd, env, tag):
    print(f"[phase_c] {tag}: {' '.join(str(c) for c in cmd)}", flush=True)
    r = subprocess.run([str(c) for c in cmd], env=env, cwd=str(REPO))
    if r.returncode != 0:
        raise SystemExit(f"[phase_c] {tag} FAILED (rc={r.returncode})")


def decision_density(path, label, prof_info, out_dir, workers, limit) -> dict:
    out = Path(out_dir) / f"DECISION_DENSITY_{label}.json"
    cmd = [sys.executable, REPO / "scripts/rules_fixed/descriptives.py", path,
           "--label", label, "-o", out, "--workers", workers]
    if not (prof_info.get("manifest_block") or {}).get("name"):
        cmd += ["--rules-profile", prof_info["name"]]
    if limit:
        cmd += ["--limit", limit]
    _run(cmd, corpus_env(prof_info), f"decision density [{label}]")
    return json.loads(out.read_text())


def materialize_jsonl(corpus: dict, out_path: Path) -> Path:
    """corpus_stats.py takes a games jsonl; a --actions-only DIR becomes one here."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for g in corpus["games"]:
            fh.write(json.dumps(g) + "\n")
    return out_path


def farm_economy(corpus: dict, label, prof_info, out_dir, workers, limit) -> dict:
    src = Path(corpus["path"])
    if corpus["kind"] != "games_jsonl" or limit:
        src = materialize_jsonl(corpus, Path(out_dir) / f"corpus_{label}.jsonl")
    cmd = [sys.executable, REPO / "scripts/analyzer/corpus_stats.py", src,
           "-o", out_dir, "--label", label, "--workers", workers,
           "--corpus-note",
           f"F9 Phase C · rules_profile={prof_info['name']} · "
           f"R9={'on' if dd.r9_env_value(prof_info) else 'off'} · {corpus['path']}"]
    _run(cmd, corpus_env(prof_info), f"farm economy [{label}]")
    return json.loads((Path(out_dir) / f"CORPUS_STATS_{label}.json").read_text())


# --------------------------------------------------------------------------- #
# the document                                                                  #
# --------------------------------------------------------------------------- #
def _n(x, nd=2):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, str):
        return x
    return f"{x:.{nd}f}"


def _delta(a, b, nd=2):
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return "—"
    return f"{b - a:+.{nd}f}"


def _row(name, a, b, nd=2):
    return f"| {name} | {_n(a, nd)} | {_n(b, nd)} | {_delta(a, b, nd)} |"


def _get(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def build_document(res, ref_label, new_label) -> str:
    A = []
    P = A.append
    P("# F9 Phase C — fixed-rules descriptives (walled vs fixed)")
    P("")
    P(f"*Generated {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())} by "
      "`scripts/rules_fixed/run_phase_c.py`.*")
    P("")
    P(GATE_C_HEADER)
    P("")
    P(CROSS_BAND_RIDER)
    P("")

    # ---- provenance ------------------------------------------------------- #
    P("## 0. Corpora")
    P("")
    P("| | reference | new |")
    P("|---|---|---|")
    P(f"| label | `{ref_label}` | `{new_label}` |")
    for key, get in (
        ("path", lambda c: c["path"]),
        ("format", lambda c: c["kind"]),
        ("games", lambda c: str(c["n_games"])),
        ("rules_profile", lambda c: f"**{c['profile']}**"),
        ("profile source", lambda c: c["profile_source"]),
        ("R9 farm fix", lambda c: "ON" if c["r9"] else "off"),
        ("generator", lambda c: c["gen_note"]),
    ):
        P(f"| {key} | {get(res['ref']['meta'])} | {get(res['new']['meta'])} |")
    P("")
    if res["ref"]["meta"]["profile"] == "walled" and not res["ref"]["meta"]["manifest_profile"]:
        P("⚠️ **Assumption stated:** the reference corpus predates F9 A0 profile "
          "stamping, so its manifest carries no `rules_profile`. It is replayed as "
          "`walled` — the engine of record, and the only rules the pre-F9 generator "
          "could have played (every elo of record is a walled number). The "
          "assumption is checked, not just asserted: all games replay to the "
          "generator's own recorded terminal scores under `walled`, which a wrong "
          "profile would break.")
        P("")

    # ---- 1. luck floor ---------------------------------------------------- #
    a, b = res["ref"]["luck"], res["new"]["luck"]
    P("## 1. Luck floor (σ_game slice)")
    P("")
    P("The spec calls this *the highest-stakes descriptive in F9* — it sizes the "
      "whole E4/human program. What a champion self-play corpus can price is "
      "σ_game (the per-game score-margin SD) and the seat-0 advantage; the ICC / "
      "σ_pair half needs a seat-swap paired archive per profile and is reported "
      "as NOT DERIVABLE rather than approximated.")
    P("")
    P(f"| metric | {ref_label} | {new_label} | Δ |")
    P("|---|---:|---:|---:|")
    P(_row("games with scores", a["n_games"], b["n_games"], 0))
    P(_row("σ_game (margin SD, pts)", a["sigma_game"], b["sigma_game"]))
    P(_row("σ_game SEM", a["sigma_game_sem"], b["sigma_game_sem"]))
    P(_row("mean seat-0 margin (pts)", a["mean_seat0_margin"], b["mean_seat0_margin"]))
    P(_row("  ± SEM", a["mean_seat0_margin_sem"], b["mean_seat0_margin_sem"]))
    P(_row("seat-0 win rate", a["seat0_win_rate"], b["seat0_win_rate"], 3))
    P(_row("mean abs margin (pts)", a["abs_margin_mean"], b["abs_margin_mean"]))
    P(_row("mean total points/game", a["mean_total_points"], b["mean_total_points"]))
    P("")
    P("**Implied sizing** (`luck_floor.required_n`, unpaired win-rate test):")
    P("")
    P(f"| target win-rate vs an equal | edge needed, {ref_label} (pts) | "
      f"edge needed, {new_label} (pts) | n games (unpaired, either) |")
    P("|---|---:|---:|---:|")
    for p in TARGET_WRS:
        k = f"{p:.2f}"
        P(f"| {p:.0%} | {_n(a['sizing_unpaired'][k]['edge_points_implied'])} | "
          f"{_n(b['sizing_unpaired'][k]['edge_points_implied'])} | "
          f"{a['sizing_unpaired'][k]['n_games_unpaired_test']} |")
    P("")
    P("NOT DERIVABLE from these corpora (both profiles alike): "
      + "; ".join(f"**{k}** — {v}" for k, v in a["not_derivable"].items()))
    P("")
    P(f"To complete the descriptive: {a['how_to_complete']}")
    P("")

    # ---- 2. decision density ---------------------------------------------- #
    a, b = res["ref"]["density"], res["new"]["density"]
    P("## 2. Decision density")
    P("")
    P("Instrument: `scripts/rules_fixed/descriptives.py` (built for this gate — "
      "the spec's *no instrument exists* row). Pure replay under each corpus's own "
      "rules profile. `searched` = the ply had ≥2 legal actions; `forced` = exactly "
      "one legal action existed.")
    P("")
    P(f"| per game | {ref_label} | {new_label} | Δ |")
    P("|---|---:|---:|---:|")
    for m in dd.GAME_METRICS:
        da, db = _get(a, "per_game", m, default={}), _get(b, "per_game", m, default={})
        if not da.get("n") and not db.get("n"):
            continue
        P(_row(m, da.get("mean"), db.get("mean")))
    P("")
    P("**Branching (legal actions) by ply kind and phase tercile**")
    P("")
    P(f"| ply kind | phase | mean {ref_label} | mean {new_label} | Δ mean | "
      f"median {ref_label} | median {new_label} | p90 {ref_label} | p90 {new_label} | "
      f"forced% {ref_label} | forced% {new_label} |")
    P("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for kind in dd.PLY_KINDS:
        for t in ("all",) + dd.TERCILES:
            da = _get(a, "branching", kind, t, default={})
            db = _get(b, "branching", kind, t, default={})
            if not da.get("n") and not db.get("n"):
                continue
            fa, fb = da.get("forced_frac"), db.get("forced_frac")
            P(f"| {kind} | {t} | {_n(da.get('mean'))} | {_n(db.get('mean'))} | "
              f"{_delta(da.get('mean'), db.get('mean'))} | {_n(da.get('median'), 1)} | "
              f"{_n(db.get('median'), 1)} | {_n(da.get('p90'), 1)} | {_n(db.get('p90'), 1)} | "
              f"{'—' if fa is None else f'{100*fa:.1f}%'} | "
              f"{'—' if fb is None else f'{100*fb:.1f}%'} |")
    P("")
    P("**Meeples committed by phase tercile** (per game)")
    P("")
    P(f"| phase | slot | {ref_label} | {new_label} | Δ |")
    P("|---|---|---:|---:|---:|")
    for t in dd.TERCILES:
        for slot in ("normal", "monk", "farmer", "pass"):
            va = _get(a, "meeple_commits_by_band", t, "per_game", slot)
            vb = _get(b, "meeple_commits_by_band", t, "per_game", slot)
            P(f"| {t} | {slot} | {_n(va)} | {_n(vb)} | {_delta(va, vb)} |")
        va = _get(a, "meeples_free_mean_by_band", t, "mean")
        vb = _get(b, "meeples_free_mean_by_band", t, "mean")
        P(f"| {t} | *free meeples (both seats)* | {_n(va)} | {_n(vb)} | {_delta(va, vb)} |")
    P("")
    P(f"Replay integrity: {ref_label} "
      f"{_get(a, 'integrity', 'replay_scores_match')}/{_get(a, 'corpus', 'n_games')} "
      f"terminal scores reproduced · {new_label} "
      f"{_get(b, 'integrity', 'replay_scores_match')}/{_get(b, 'corpus', 'n_games')}. "
      "(A single mismatch aborts the leg — a wrong profile shows up here first.)")
    P("")

    # ---- 3. farm economy --------------------------------------------------- #
    a, b = res["ref"].get("farm"), res["new"].get("farm")
    P("## 3. Farm-economy norms")
    P("")
    if not a or not b:
        P("*(skipped — run without `--skip-farm` to produce this leg)*")
        P("")
    else:
        P("Instrument: `scripts/analyzer/corpus_stats.py` (existing), one run per "
          "corpus under its own profile/R9 environment. Per-seat distributions "
          "unless stated.")
        P("")
        P(f"| metric | {ref_label} | {new_label} | Δ |")
        P("|---|---:|---:|---:|")
        for name, path in (
            ("farm_pts (mean)", ("seat_dist", "farm_pts", "mean")),
            ("farm_pts (median)", ("seat_dist", "farm_pts", "p50")),
            ("farm_pts_frac (mean)", ("seat_dist", "farm_pts_frac", "mean")),
            ("farm_pts_per_farmer (mean)", ("seat_dist", "farm_pts_per_farmer", "mean")),
            ("first_farm_turn (mean)", ("seat_dist", "first_farm_turn", "mean")),
            ("first_farm_turn (median)", ("seat_dist", "first_farm_turn", "p50")),
            ("first_farm_k_remaining (mean)", ("seat_dist", "first_farm_k_remaining", "mean")),
            ("farm_meeple_turns_locked (mean)", ("seat_dist", "farm_meeple_turns_locked", "mean")),
            ("farmers per seat (mean)", ("farm_timing", "per_seat_mean")),
            ("seats with no farmer", ("farm_timing", "seats_with_no_farmer")),
            ("farmers placed, total", ("farm_timing", "n_farmers_total")),
            ("placement k-band frac: early", ("farm_timing", "placement_k_band_frac", "early")),
            ("placement k-band frac: mid", ("farm_timing", "placement_k_band_frac", "mid")),
            ("placement k-band frac: late", ("farm_timing", "placement_k_band_frac", "late")),
            ("final_score (mean)", ("seat_dist", "final_score", "mean")),
            ("during_play_frac (mean)", ("seat_dist", "during_play_frac", "mean")),
            ("incomplete_pts (mean)", ("seat_dist", "incomplete_pts", "mean")),
            ("stranding rate, non-farmer", ("stranding", "rate_nonfarmer")),
            ("n_turns (mean)", ("game_dist", "n_turns", "mean")),
            ("n_completions (mean)", ("game_dist", "n_completions", "mean")),
            ("n_cloisters_closed (mean)", ("game_dist", "n_cloisters_closed", "mean")),
            ("n_cities_closed (mean)", ("game_dist", "n_cities_closed", "mean")),
            ("n_roads_closed (mean)", ("game_dist", "n_roads_closed", "mean")),
            ("total_points (mean)", ("game_dist", "total_points", "mean")),
        ):
            P(_row(name, _get(a, *path), _get(b, *path), 3))
        P("")

    # ---- artifacts --------------------------------------------------------- #
    P("## 4. Artifacts")
    P("")
    for f in res["artifacts"]:
        P(f"- `{f}`")
    P("")
    P("Reproduce:")
    P("")
    P("```")
    P(res["cmdline"])
    P("```")
    P("")
    return "\n".join(A)


# --------------------------------------------------------------------------- #
def one_corpus(path, label, cli_profile, out_dir, workers, limit, skip_farm) -> dict:
    corpus = dd.load_corpus(path, limit=limit)
    prof = dd.resolve_corpus_profile(corpus, cli_profile)
    meta = {
        "path": corpus["path"], "kind": corpus["kind"], "n_games": len(corpus["games"]),
        "profile": prof["name"], "profile_source": prof["source"],
        "manifest_profile": bool((prof.get("manifest_block") or {}).get("name")),
        "r9": dd.r9_env_value(prof),
        "gen_note": str((corpus["games"][0] or {}).get("gen", "?")) + " · budget "
                    + str((corpus["games"][0] or {}).get("total_budget_per_move", "?"))
                    + " · code_rev " + str((corpus["games"][0] or {}).get("code_rev", "?")),
    }
    out = {"meta": meta, "luck": luck_slice(corpus, label)}
    out["density"] = decision_density(path, label, prof, out_dir, workers, limit)
    if not skip_farm:
        out["farm"] = farm_economy(corpus, label, prof, out_dir, workers, limit)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="F9 Phase C descriptives, two corpora side by side")
    ap.add_argument("ref_corpus", help="walled-era reference corpus (dir or jsonl)")
    ap.add_argument("new_corpus", help="fixed-rules corpus (dir or jsonl)")
    ap.add_argument("--ref-label", default="walled")
    ap.add_argument("--new-label", default="fixed_v1")
    ap.add_argument("--ref-profile", default=None,
                    help="profile for the reference corpus when its manifest carries "
                         "none (pre-F9 corpora: `walled`)")
    ap.add_argument("--new-profile", default=None, help="same, for the new corpus")
    ap.add_argument("-o", "--out-dir", default=str(REPO / "measurement/f9_phase_c"))
    ap.add_argument("--workers", type=int, default=4, help="replay workers (cap 6)")
    ap.add_argument("--limit", type=int, default=0, help="first N games of each (debug)")
    ap.add_argument("--skip-farm", action="store_true",
                    help="skip the corpus_stats leg (it is the slow one)")
    args = ap.parse_args(argv)

    if args.workers > 6:
        print("[phase_c] refusing --workers > 6 (the box is shared)", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    res = {
        "ref": one_corpus(args.ref_corpus, args.ref_label, args.ref_profile, out_dir,
                          args.workers, args.limit, args.skip_farm),
        "new": one_corpus(args.new_corpus, args.new_label, args.new_profile, out_dir,
                          args.workers, args.limit, args.skip_farm),
    }
    luck_path = out_dir / "LUCK_SLICE.json"
    luck_path.write_text(json.dumps(
        {"schema": "carcassonne-f9-phase-c-luck-slice/v1",
         "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
         "note": "unpaired self-play slice; ICC/sigma_pair NOT derivable — see "
                 "not_derivable/how_to_complete",
         args.ref_label: res["ref"]["luck"], args.new_label: res["new"]["luck"]}, indent=1))

    arts = [str(luck_path.relative_to(REPO)) if luck_path.is_relative_to(REPO) else str(luck_path)]
    for lbl in (args.ref_label, args.new_label):
        for pat in (f"DECISION_DENSITY_{lbl}.json", f"CORPUS_STATS_{lbl}.json",
                    f"CORPUS_STATS_{lbl}.md", f"corpus_{lbl}.jsonl"):
            p = out_dir / pat
            if p.exists():
                arts.append(str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p))
    res["artifacts"] = arts
    res["cmdline"] = "scripts/rules_fixed/run_phase_c.py " + " ".join(
        f"'{a}'" if " " in str(a) else str(a) for a in (argv or sys.argv[1:]))

    doc = build_document(res, args.ref_label, args.new_label)
    doc_path = out_dir / "PHASE_C_DESCRIPTIVES.md"
    doc_path.write_text(doc)
    print(f"[phase_c] wrote {doc_path}  ({time.time()-t0:.0f}s total)")
    for a in arts:
        print(f"[phase_c]   + {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
