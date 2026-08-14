#!/usr/bin/env python3
"""Offline E4-replay read for the OPEN-CITY DISCIPLINE leaf term — the pick-flip
rate that gates whether a strength screen is bought at all.

    scripts/classical_search/opencity_e4_replay.py \
        -o measurement/opencity_term_20260812/calib \
        [--arm NAME:SIZE_MIN:EDGE_MIN:DOSE[:CAP] ...] [--workers 6] \
        [--limit-games 1] [--limit-plies 0] [--archive-dir measurement/e4_games]

Sibling of `scripts/classical_search/denial_e4_replay.py` (the template of
record — same design points, same resumability contract, same CRN discipline).
It is a SIBLING and not an extension because this term's arms vary the
*predicate thresholds* as well as the dose, which changes the arm shape from a
scalar ladder to a 3x2 grid.

Replays the E4 human-vs-champion phone archives and, at every CHAMPION decision
ply, runs the production search once per arm — the production leaf, plus one
open-city leaf per (size_min, edge_min, dose) cell — with CRN determinizations
(SAME agent seed and SAME `_move_idx` on every arm, so all arms search identical
worlds and a pick flip is attributable to the leaf, not the draw). Reports the
pick-flip rate with a per-arm Wilson-95 CI, and exactly WHICH plies flip (game
id, ply, phase, k_remaining).

**The pre-registered ladder** (`measurement/opencity_term_20260812/
CALIB_READ_RULE.md` §1 == `TERM_SPEC.md` §7; this is the default when no `--arm`
is passed, and all six cells run in ONE pass sharing a single champion search per
ply — 7 searches/ply, not 3x3):

    | arm name | opencity_size_min (distinct TILES) | opencity_edge_min | dose |
    |----------|------------------------------------|-------------------|------|
    | A_d0p5   | 4  (production spec)               | 2                 | 0.5  |
    | A_d2p0   | 4  (production spec)               | 2                 | 2.0  |
    | B_d0p5   | 3  (loose)                         | 2                 | 0.5  |
    | B_d2p0   | 3  (loose)                         | 2                 | 2.0  |
    | C_d0p5   | 6  (tight)                         | 3                 | 0.5  |
    | C_d2p0   | 6  (tight)                         | 3                 | 2.0  |

`opencity_symmetric` is held **True** in every arm. CALIB_READ_RULE §1: flipping
it is a *different term*, not a rung, and mixing it into this ladder is the
forking path that document exists to prevent. `--asymmetric` is the explicit
opt-out; it applies to ALL arms at once and is stamped in every summary, so an
asymmetric run can never be mistaken for the pre-registered one.

What this does NOT do: play any games, measure any elo, claim any deck band, or
touch governance. It answers "does the term change the champion's play at all,
at plausible thresholds and doses?" for free, so the screen (TERM_SPEC §8 stage
1) is only bought if some cell clears the resolvable-flip floor. A flip is not
an improvement; nothing this script prints licenses a strength claim.

Design points, all inherited from the ev_loss grader (scripts/analyzer/
ev_loss.py — the archive-replay precedent of record) via the denial instrument:

* **The rules profile is resolved FROM each archive** (`resolve_profile_name`),
  never from a flag — a walled-era archive is graded under `walled` (R9 OFF).
  R9 is import-latched, so the orchestrator mode spawns ONE SUBPROCESS PER
  ARCHIVE (`--single`), each with a fresh latch. Mixed-profile corpora are
  therefore fine, and the rollup carries the realized profile histogram.
* **Budget defaults to the archive's own stamp** (`k_dets_effective` x
  `sims_effective`) — the champion's own opinion at the budget it played;
  --sims/--k-dets override for smokes (and the override is stamped as such).
* **Exact-tail plies are skipped** (k_remaining <= EXACT_MAX_K): the agent
  latches to the marginalized endgame solver there, which scores the TRUE final
  score — the leaf (and hence the open-city term) cannot flip those plies by
  construction. Forced plies (one legal action) are skipped for the same reason.
* **Resumable**: one `plies_<stem>.jsonl` per archive, appended per graded ply;
  on restart, already-graded plies are replayed WITHOUT searching (the arms are
  deterministic given seed+move_idx, so nothing is lost) and grading resumes at
  the first missing ply. A `game_<stem>.json` summary marks a finished archive;
  the orchestrator skips those.
* **Concurrent archives** (`--workers N`, default 1): each archive is still its
  own PROCESS — never a thread — so the R9 import latch stays fresh per archive.
  A non-zero exit stops new launches, drains the in-flight ones, and exits
  non-zero naming the archives that failed.

⚠️ Requires an OPENCITY-CAPABLE carc_rs build (the term ships in the Rust leaf;
`rust_agent.leaf_config_rs` forwards the four knobs as conditional kwargs and a
stale build raises TypeError rather than silently searching an intact leaf —
TERM_SPEC §6's stale-wheel trap). The champion arm is `make_production_champion(
verify=True)`; the candidate arms are the same RustFairAgent construction with
ONLY the leaf replaced, and every candidate's `_leaf_hash` is asserted DIFFERENT
from the champion's at construction — a candidate that hashes to the champion is
the silent-null failure mode this whole campaign guards against.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

SCHEMA = "carcassonne-opencity-e4-replay/v1"
DEFAULT_ARCHIVE_DIR = REPO / "measurement" / "e4_games"

#: The champion leaf of record (`governance/PRODUCTION.yaml`). Every candidate
#: arm's leaf hash must differ from whatever the running tree resolves as the
#: production leaf; this constant is the pinned expectation for THAT hash.
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

#: CALIB_READ_RULE §1 / TERM_SPEC §7, verbatim. Fixed in advance; adding a rung
#: after seeing the ladder is a NEW calibration, not an extension of this one.
DEFAULT_ARM_SPECS = (
    "A_d0p5:4:2:0.5",
    "A_d2p0:4:2:2.0",
    "B_d0p5:3:2:0.5",
    "B_d2p0:3:2:2.0",
    "C_d0p5:6:3:0.5",
    "C_d2p0:6:3:2.0",
)

#: z for a two-sided 95% interval (the CI the read-rule asks for, by name).
Z95 = 1.959963984540054


# ==========================================================================  #
# PURE HELPERS — importable with no `carcassonne_ai` / `ev_loss` import.      #
# Everything below this banner and above the "arms" banner must stay free of  #
# heavy imports so the unit tests are instant and never latch the leaf env.   #
# ==========================================================================  #
@dataclass(frozen=True)
class Arm:
    """One calibration cell: a name plus the three knobs that define it.

    `opencity_symmetric` is deliberately NOT a per-arm field — it is a run-level
    switch (`--asymmetric`) applied to every arm at once, because flipping it is
    a different term rather than a rung (CALIB_READ_RULE §1)."""

    name: str
    size_min: float
    edge_min: int
    dose: float
    #: PER-CITY cap on the raw product contribution (`LeafConfig.opencity_cap`,
    #: added 2026-08-14 for the round-2 capped form). 0.0 == uncapped == the
    #: CL-080-era term bit-exactly. Unlike `opencity_symmetric` this IS a per-arm
    #: field: a capped arm and an uncapped arm are different cells on the same
    #: ladder shape, and the cap rides in the 5th `--arm` field.
    cap: float = 0.0

    def spec(self) -> str:
        """The `--arm` string that round-trips back to this Arm."""
        base = f"{self.name}:{self.size_min:g}:{self.edge_min:d}:{self.dose:g}"
        return base + (f":{self.cap:g}" if self.cap > 0.0 else "")

    def as_dict(self) -> dict:
        return {"name": self.name, "size_min": float(self.size_min),
                "edge_min": int(self.edge_min), "dose": float(self.dose),
                "cap": float(self.cap)}


def parse_arm(spec: str) -> Arm:
    """`NAME:SIZE_MIN:EDGE_MIN:DOSE` -> Arm. Raises ValueError, loudly.

    Every rejection below is a silent-wrong-answer class, not a typo class:
    a dose-0 arm is the champion itself (a guaranteed perfect null), and an
    `edge_min < 1` arm prices EVERY incomplete city, which is a different term.
    """
    if not isinstance(spec, str):
        raise ValueError(f"--arm must be a string, got {type(spec).__name__}")
    raw = spec.strip()
    if not raw:
        raise ValueError("--arm is empty; expected NAME:SIZE_MIN:EDGE_MIN:DOSE")
    parts = raw.split(":")
    if len(parts) not in (4, 5):
        raise ValueError(
            f"--arm {spec!r}: expected 4 or 5 colon-separated fields "
            f"NAME:SIZE_MIN:EDGE_MIN:DOSE[:CAP], got {len(parts)}")
    name, s_raw, e_raw, d_raw = (p.strip() for p in parts[:4])
    c_raw = parts[4].strip() if len(parts) == 5 else "0"

    if not name:
        raise ValueError(f"--arm {spec!r}: NAME is empty")
    if any(c.isspace() for c in name):
        raise ValueError(f"--arm {spec!r}: NAME {name!r} may not contain whitespace")

    try:
        size_min = float(s_raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: SIZE_MIN {s_raw!r} is not a number "
            "(opencity_size_min is a float count of DISTINCT TILES)") from None
    if not math.isfinite(size_min):
        raise ValueError(f"--arm {spec!r}: SIZE_MIN {s_raw!r} is not finite")
    if size_min < 1.0:
        raise ValueError(
            f"--arm {spec!r}: SIZE_MIN {size_min:g} must be >= 1 — a city component "
            "always spans at least one tile, so a sub-1 threshold prices every city "
            "and is a different term, not a rung")

    try:
        edge_min = int(e_raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: EDGE_MIN {e_raw!r} is not an integer "
            "(opencity_edge_min counts distinct open cells; it is an int knob)") from None
    if edge_min < 1:
        raise ValueError(
            f"--arm {spec!r}: EDGE_MIN {edge_min} must be >= 1 — at edge_min < 1 the "
            "predicate fires on EVERY incomplete city, which TERM_SPEC §5 calls a "
            "different term rather than a rung (c5_leaf_override raises on < 1 too)")

    try:
        dose = float(d_raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: DOSE {d_raw!r} is not a number") from None
    if not math.isfinite(dose):
        raise ValueError(f"--arm {spec!r}: DOSE {d_raw!r} is not finite")
    if dose <= 0.0:
        raise ValueError(
            f"--arm {spec!r}: DOSE must be > 0, got {dose:g} — dose 0 IS the champion "
            "arm (the term is early-branched off at dose 0 and the leaf is byte "
            "identical), and the champion already runs as the reference arm on every "
            "ply, so a dose-0 candidate would read a guaranteed perfect null")

    try:
        cap = float(c_raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: CAP {c_raw!r} is not a number (opencity_cap is a "
            "per-city cap on the raw product; 0 == uncapped)") from None
    if not math.isfinite(cap):
        raise ValueError(f"--arm {spec!r}: CAP {c_raw!r} is not finite")
    if cap < 0.0:
        raise ValueError(
            f"--arm {spec!r}: CAP must be >= 0, got {cap:g} — 0 is the explicit "
            "uncapped (CL-080-era) form; a negative per-city cap is undefined "
            "(c5_leaf_override raises on it too)")

    return Arm(name=name, size_min=size_min, edge_min=edge_min, dose=dose, cap=cap)


def parse_arms(specs) -> tuple:
    """A list of `--arm` strings -> a tuple of Arms, with uniqueness enforced."""
    items = list(specs or ())
    if not items:
        raise ValueError(
            "no arms: pass at least one --arm NAME:SIZE_MIN:EDGE_MIN:DOSE, or omit "
            f"--arm entirely for the pre-registered ladder {list(DEFAULT_ARM_SPECS)}")
    arms, by_name, by_knobs = [], {}, {}
    for spec in items:
        arm = parse_arm(spec)
        if arm.name in by_name:
            raise ValueError(
                f"duplicate arm NAME {arm.name!r}: {by_name[arm.name].spec()!r} and "
                f"{arm.spec()!r} — names key every flip column in the rollup, so they "
                "must be unique")
        knobs = (arm.size_min, arm.edge_min, arm.dose, arm.cap)
        if knobs in by_knobs:
            raise ValueError(
                f"arm {arm.name!r} duplicates the knobs of {by_knobs[knobs].name!r} "
                f"(size_min={arm.size_min:g}, edge_min={arm.edge_min}, "
                f"dose={arm.dose:g}, cap={arm.cap:g}) — two names for one cell would "
                "double its search cost and read as two independent measurements")
        by_name[arm.name] = arm
        by_knobs[knobs] = arm
        arms.append(arm)
    return tuple(arms)


def wilson_ci(k: int, n: int, z: float = Z95) -> tuple:
    """Wilson score interval for a binomial proportion — (lo, hi), clamped [0,1].

    The read-rule (CALIB_READ_RULE §1) requires per-arm 95% CIs alongside every
    flip rate, and quotes the expected half-widths at n≈1079 (±1.3pp at f=5%,
    ±1.8pp at f=10%) — `tests/test_opencity_e4_replay.py` pins those.

    Wilson (not Wald) because the interesting arms sit near f=0 (TERM_SPEC §6
    predicts arm C reads ~0), where Wald's interval is degenerate."""
    n = int(n)
    k = int(k)
    if n < 0:
        raise ValueError(f"wilson_ci: n must be >= 0, got {n}")
    if k < 0 or k > n:
        raise ValueError(f"wilson_ci: need 0 <= k <= n, got k={k}, n={n}")
    if n == 0:
        return (0.0, 1.0)
    z2 = z * z
    denom = n + z2
    centre = (k + z2 / 2.0) / denom
    half = (z / denom) * math.sqrt(k * (n - k) / n + z2 / 4.0)
    return (max(0.0, centre - half), min(1.0, centre + half))


def _arm_order(summaries) -> list:
    """Arm names in first-seen order across the per-game summaries."""
    seen, order = set(), []
    for s in summaries:
        for name in [a["name"] for a in s.get("arms", [])] or list(s.get("flips", {})):
            if name not in seen:
                seen.add(name)
                order.append(name)
    return order


def rollup_from_summaries(summaries) -> dict:
    """Per-game summary dicts -> the corpus rollup the read-rule demands.

    Pure: no filesystem, no imports beyond the stdlib. Everything
    CALIB_READ_RULE §1 says must be reported *with* the rate lands here —
    realized n, per-arm Wilson-95, the per-archive rules epoch histogram, and
    `replay_scores_match` for EVERY archive with a single aggregate boolean,
    because one failing checksum voids the whole calibration."""
    summaries = list(summaries)
    arm_names = _arm_order(summaries)
    total = sum(int(s.get("n_graded", 0)) for s in summaries)

    per_arm = {}
    for name in arm_names:
        flips = sum(int(s.get("flips", {}).get(name, 0)) for s in summaries)
        lo, hi = wilson_ci(flips, total)
        phases: dict = {}
        for s in summaries:
            for rec in s.get("flip_plies", {}).get(name, []):
                ph = str(rec.get("phase", "unknown"))
                phases[ph] = phases.get(ph, 0) + 1
        n_tiles, n_meeples = phases.get("tiles", 0), phases.get("meeples", 0)
        per_arm[name] = {
            "flips_total": flips,
            "n_graded": total,
            "flip_rate": (flips / total if total else None),
            "wilson95": [lo, hi],
            "wilson95_half_width": (hi - lo) / 2.0,
            # Descriptive only — CALIB_READ_RULE §4 bars "where the flips land"
            # from the funding decision. Mirrors the denial readout §5.
            "phase_split": {"tiles": n_tiles, "meeples": n_meeples,
                            "other": {k: v for k, v in phases.items()
                                      if k not in ("tiles", "meeples")},
                            "tile_share": (n_tiles / flips if flips else None)},
        }

    profile_hist: dict = {}
    for s in summaries:
        p = str(s.get("rules_profile", "unknown"))
        profile_hist[p] = profile_hist.get(p, 0) + 1

    replay = {str(s.get("archive")): s.get("replay_scores_match") for s in summaries}
    bad = sorted(a for a, v in replay.items() if v is not True)

    knobs = {}
    for s in summaries:
        for a in s.get("arms", []):
            knobs.setdefault(a["name"], {k: a.get(k) for k in
                                         ("size_min", "edge_min", "dose", "cap",
                                          "symmetric", "leaf_hash")})

    return {
        "schema": SCHEMA + "/rollup",
        "n_games": len(summaries),
        "n_graded_plies": total,
        "arm_knobs": knobs,
        "arms": per_arm,
        # Flat mirrors so a grep/jq of the rollup finds the headline numbers
        # without walking into `arms`.
        "flips_total": {n: per_arm[n]["flips_total"] for n in arm_names},
        "flip_rate": {n: per_arm[n]["flip_rate"] for n in arm_names},
        "wilson95": {n: per_arm[n]["wilson95"] for n in arm_names},
        "champ_agrees_archive": sum(int(s.get("champ_agrees_archive", 0))
                                    for s in summaries),
        "champ_agrees_archive_rate": (sum(int(s.get("champ_agrees_archive", 0))
                                          for s in summaries) / total
                                      if total else None),
        "rules_profile_histogram": profile_hist,
        "replay_scores_match": replay,
        "all_replay_scores_match": (bool(summaries) and not bad),
        "replay_scores_mismatch_archives": bad,
        "opencity_symmetric": sorted({bool(s.get("opencity_symmetric", True))
                                      for s in summaries}),
        "budget_by_archive": {str(s.get("archive")): s.get("budget")
                              for s in summaries},
        "by_game": [{"archive": s.get("archive"), "profile": s.get("rules_profile"),
                     "n_graded": s.get("n_graded"), "flips": s.get("flips"),
                     "replay_scores_match": s.get("replay_scores_match"),
                     "budget": s.get("budget"),
                     "recorded_scores": s.get("recorded_scores"),
                     "human_player": s.get("human_player"),
                     "flip_plies": s.get("flip_plies")} for s in summaries],
    }


def rollup(out_dir) -> dict:
    """Read every `game_*.json` in `out_dir`, write `SUMMARY.json`, return it."""
    out_dir = Path(out_dir)
    games = sorted(out_dir.glob("game_*.json"))
    if not games:
        return {}
    summaries = [json.loads(p.read_text()) for p in games]
    roll = rollup_from_summaries(summaries)
    (out_dir / "SUMMARY.json").write_text(json.dumps(roll, indent=1))

    if not roll["all_replay_scores_match"]:
        print("[opencity_e4] ############################################################")
        print("[opencity_e4] WARNING: replay checksum NOT clean on "
              f"{len(roll['replay_scores_mismatch_archives'])} archive(s): "
              f"{roll['replay_scores_mismatch_archives']}")
        print("[opencity_e4] CALIB_READ_RULE §1: any archive that fails its replay "
              "checksum VOIDS the whole calibration — fix and re-run (re-running is "
              "free: no band, no games, deterministic searches).")
        print("[opencity_e4] (a partial run, --limit-plies, stamps null here by "
              "construction and is never a calibration.)")
        print("[opencity_e4] ############################################################")

    for name in _arm_order(summaries):
        a = roll["arms"][name]
        lo, hi = a["wilson95"]
        rate = a["flip_rate"]
        print(f"[opencity_e4] {name:>8}: flips {a['flips_total']:>5}/{a['n_graded']:<5} "
              f"= {'  n/a ' if rate is None else f'{100*rate:6.2f}%'} "
              f"[{100*lo:5.2f}%, {100*hi:5.2f}%]  "
              f"tiles/meeples {a['phase_split']['tiles']}/{a['phase_split']['meeples']}")
    print(f"[opencity_e4] rollup: {roll['n_games']} games, {roll['n_graded_plies']} "
          f"graded plies, profiles={roll['rules_profile_histogram']}, "
          f"all_replay_scores_match={roll['all_replay_scores_match']} "
          f"-> {out_dir/'SUMMARY.json'}")
    print("[opencity_e4] NOTE: a flip is not an improvement. No elo, no band, no "
          "governance write — read against CALIB_READ_RULE §3, nothing else.")
    return roll


# ==========================================================================  #
# arms (heavy: everything below imports carcassonne_ai)                       #
# ==========================================================================  #
def _make_arms(game, spec, ex, seed, sims, k_dets, arms, symmetric):
    """The champion arm (verify=True) + one open-city arm per calibration cell.

    The candidate arms replicate `make_production_champion`'s rust branch —
    RustFairAgent with the SAME game geometry, sims, k_dets, seed, exact
    settings — with ONLY the embedded leaf replaced, so a pick flip is the
    leaf's doing and nothing else's."""
    import dataclasses as dc

    from carcassonne_ai.champion_factory import (make_production_champion,
                                                 production_leaf_cfg,
                                                 production_prior_cfg)
    from carcassonne_ai.rust_agent import RustFairAgent

    if not ex.is_rust:
        raise SystemExit(
            f"[opencity_e4] execution resolved to backend={ex['backend']!r}; the "
            "open-city arms are rust-only (the term's production backend). Fix "
            "PRODUCTION.yaml resolution or pass a rust-capable environment.")

    champ = make_production_champion("fair", game=game, seed=int(seed), sims=sims,
                                     k_dets=k_dets, verify=True, **ex.factory_kwargs())

    def _geom(g):
        geom: dict = {"window_size": int(getattr(g, "window_size", 25))}
        if getattr(g, "recentred", False):
            geom["start_row"] = int(g.start_row)
            geom["start_col"] = int(g.start_col)
        if getattr(g, "fixed_start_tile", False):
            geom["start_rule"] = "retail"
        if getattr(g, "cloister_scan_fix", False):
            geom["cloister_scan_fix"] = True
        dr = getattr(g, "draw_rule", None)
        if dr is not None and dr != "engine":
            geom["draw_rule"] = str(dr)
        return geom

    base_leaf = production_leaf_cfg(spec)
    champ_hash = _leaf_hash_of(base_leaf)
    if champ_hash != LEAF_HASH_OF_RECORD:
        print(f"[opencity_e4] WARNING: production leaf hashes {champ_hash}, expected "
              f"{LEAF_HASH_OF_RECORD} (governance/PRODUCTION.yaml) — the champion arm "
              "is NOT the leaf of record; do not read this as a calibration.")

    agents, hashes = {}, {}
    for arm in arms:
        leaf_a = dc.replace(base_leaf,
                            opencity_dose=float(arm.dose),
                            opencity_size_min=float(arm.size_min),
                            opencity_edge_min=int(arm.edge_min),
                            opencity_symmetric=bool(symmetric),
                            opencity_cap=float(arm.cap))
        h = _leaf_hash_of(leaf_a)
        # THE silent-null guard: a candidate that hashes to the champion is a
        # champion-vs-champion cell that reads as a perfect null.
        if h == champ_hash:
            raise SystemExit(
                f"[opencity_e4] arm {arm.name!r} ({arm.spec()}) hashes to the CHAMPION "
                f"leaf ({h}) — the term did not take. That is the silent-null failure "
                "mode this calibration exists to avoid (stale carc_rs wheel, dropped "
                "kwargs, or a dose that early-branches off). Refusing to run.")
        cfg_a = production_prior_cfg(spec, leaf_a)
        agents[arm.name] = RustFairAgent(
            game, cfg_a,
            sims=(spec.sims_per_det if sims is None else int(sims)),
            k_dets=(spec.k_dets if k_dets is None else int(k_dets)),
            seed=int(seed), exact_endgame=True, exact_max_k=spec.exact_max_k,
            threads=(1 if ex["rust_threads"] is None else int(ex["rust_threads"])),
            **_geom(game))
        hashes[arm.name] = h
    dupes = {h for h in hashes.values() if list(hashes.values()).count(h) > 1}
    if dupes:
        raise SystemExit(f"[opencity_e4] distinct arms share a leaf hash {sorted(dupes)}"
                         " — two cells would be one measurement. Refusing to run.")
    return champ, agents, base_leaf, champ_hash, hashes


def _leaf_hash_of(cfg) -> str:
    """The a36d2e15 harness dialect (provenance stamp)."""
    from carcassonne_ai.alphabeta_agent import _leaf_hash
    return _leaf_hash(cfg)


# ==========================================================================  #
# one archive                                                                 #
# ==========================================================================  #
def grade_archive(archive_path: Path, out_dir: Path, *, arms, symmetric,
                  seed, sims, k_dets, rust_threads, limit_plies=0) -> dict:
    import random

    import numpy as np

    # Deferred so the pure helpers above import clean: `ev_loss` pulls in
    # env_preamble (production leaf env) and MUST precede any carcassonne_ai
    # import, which nothing at module scope performs.
    sys.path.insert(0, str(REPO / "scripts" / "analyzer"))
    import ev_loss

    arch = ev_loss.load_archive(archive_path)
    profile_name = ev_loss.resolve_profile_name(arch["provenance"])
    env_stamp = ev_loss.prepare_env(profile_name)

    from carcassonne_ai import fair_agent, rules_profile
    from carcassonne_ai.champion_factory import load_production_spec
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, reseat, resolve_execution

    prof = rules_profile.activate(profile_name)
    spec = load_production_spec()
    ex = resolve_execution("inherit", profile="desktop", rust_threads=rust_threads)

    sims_eff = sims or int(arch["sims_effective"] or 0) or None
    k_eff = k_dets or int(arch["k_dets_effective"] or 0) or None
    if sims_eff is None or k_eff is None:
        raise SystemExit(f"[opencity_e4] {archive_path.name}: archive stamps no budget; "
                         "pass --sims/--k-dets")

    actions = arch["actions"][: limit_plies or None]
    deck_seed = arch["deck_seed"]
    champ_seat = 1 - arch["human_player"]

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    champ, agents, base_leaf, champ_hash, hashes = _make_arms(
        game, spec, ex, seed, sims_eff, k_eff, arms, symmetric)
    all_agents = [champ, *agents.values()]
    for a in all_agents:
        reseat(a, deck_seed=deck_seed, actions=(), move_idx=0)

    stem = archive_path.stem
    ply_path = out_dir / f"plies_{stem}.jsonl"
    done_plies = {}
    if ply_path.exists():
        for line in ply_path.open():
            if line.strip():
                r = json.loads(line)
                done_plies[int(r["ply"])] = r

    exact_max_k = int(fair_agent.EXACT_MAX_K)
    recs = list(done_plies.values())
    t0 = time.time()
    n_searched = 0
    with ply_path.open("a") as fh:
        for ply, played in enumerate(actions):
            st = board.state
            legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
            if played not in legal:
                raise ValueError(f"archive action {played} illegal at ply {ply}")
            graded = (st.current_player == champ_seat and len(legal) > 1
                      and len(st.deck) > exact_max_k)
            if graded and ply not in done_plies:
                rec = {"ply": ply, "phase": st.phase.value,
                       "k_remaining": len(st.deck), "n_legal": len(legal),
                       "action_played": int(played)}
                for a in all_agents:
                    a._move_idx = ply                    # CRN: same worlds every arm
                s0 = time.time()
                champ_pick = int(champ.choose_action(board))
                rec["champ_pick"] = champ_pick
                rec["champ_agrees_archive"] = bool(champ_pick == int(played))
                for name, agent in agents.items():
                    pick = int(agent.choose_action(board))
                    rec[f"pick_{name}"] = pick
                    rec[f"flip_{name}"] = bool(pick != champ_pick)
                rec["secs"] = round(time.time() - s0, 3)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                recs.append(rec)
                n_searched += 1
                if n_searched % 8 == 0:
                    print(f"  [{stem}] ply {ply}/{len(actions)} graded={n_searched} "
                          f"{time.time()-t0:.0f}s", flush=True)
            board, _ = game.get_next_state(board, int(played))
            advance(all_agents, int(played))

    recs.sort(key=lambda r: r["ply"])
    arm_names = [a.name for a in arms]
    partial = bool(limit_plies)
    summary = {
        "schema": SCHEMA,
        "archive": archive_path.name,
        "deck_seed": deck_seed,
        "rules_profile": profile_name,
        "human_player": arch["human_player"],
        "champion_seat": champ_seat,
        "recorded_scores": arch["recorded_scores"],
        "replayed_scores": ([int(x) for x in board.state.scores]
                            if not partial else None),
        # `null` on a partial run: the checksum is not CHECKABLE, which the rollup
        # reports as "not clean" rather than silently passing it.
        "replay_scores_match": (None if partial else
                                (arch["recorded_scores"] is not None
                                 and list(board.state.scores) == arch["recorded_scores"])),
        "partial": partial,
        "budget": {"sims_per_det": sims_eff, "k_dets": k_eff,
                   "total_per_decision": sims_eff * k_eff,
                   "source": ("archive" if not (sims or k_dets) else "CLI override")},
        "seed": int(seed),
        "opencity_symmetric": bool(symmetric),
        "arms": [{**a.as_dict(), "symmetric": bool(symmetric),
                  "leaf_hash": hashes[a.name]} for a in arms],
        "leaf_hash_production": champ_hash,
        "n_plies_total": len(actions),
        "n_graded": len(recs),
        "n_searched_this_run": n_searched,
        "champ_agrees_archive": sum(1 for r in recs if r["champ_agrees_archive"]),
        "flips": {n: sum(1 for r in recs if r.get(f"flip_{n}")) for n in arm_names},
        "flip_plies": {n: [{k: r[k] for k in ("ply", "phase", "k_remaining",
                                              "champ_pick", f"pick_{n}")}
                           for r in recs if r.get(f"flip_{n}")] for n in arm_names},
        "mean_secs_per_graded_ply": (round(sum(r["secs"] for r in recs) / len(recs), 3)
                                     if recs else None),
        "env": env_stamp,
        "wall_secs": round(time.time() - t0, 1),
    }
    (out_dir / f"game_{stem}.json").write_text(json.dumps(summary, indent=1))
    print(f"[opencity_e4] {stem}: profile={profile_name} graded={len(recs)} "
          f"flips={summary['flips']} "
          f"agree_archive={summary['champ_agrees_archive']}/{len(recs)} "
          f"mean_secs_per_graded_ply={summary['mean_secs_per_graded_ply']} "
          f"({summary['wall_secs']}s)", flush=True)
    return summary


# ==========================================================================  #
# orchestrator                                                                #
# ==========================================================================  #
def _run_pool(jobs, workers: int, poll: float = 0.2) -> list:
    """Run `[(label, argv), ...]` as at most `workers` CONCURRENT SUBPROCESSES.

    Processes, never threads: each archive needs its own fresh R9 import latch,
    which is process-global and set once. On the first non-zero exit we stop
    LAUNCHING but still drain everything already in flight (their jsonl is
    resumable and killing them would strand partial plies), then report every
    failure. Returns `[(label, rc), ...]` — empty means all clean."""
    pending = list(jobs)
    running: dict = {}
    failed: list = []
    stop = False
    while pending or running:
        while not stop and pending and len(running) < max(1, int(workers)):
            label, argv = pending.pop(0)
            running[subprocess.Popen(argv)] = label
        if not running:
            break
        time.sleep(poll)
        for proc in list(running):
            rc = proc.poll()
            if rc is None:
                continue
            label = running.pop(proc)
            if rc != 0:
                failed.append((label, rc))
                if not stop:
                    stop = True
                    print(f"[opencity_e4] FAIL rc={rc} on {label} — no new archives "
                          f"will launch; draining {len(running)} in flight",
                          flush=True)
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR))
    ap.add_argument("--single", default=None,
                    help="grade ONE archive in THIS process (internal: the "
                         "orchestrator spawns one subprocess per archive so each "
                         "gets a fresh R9 import latch)")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--arm", action="append", default=None, metavar="N:S:E:D[:C]",
                    help="repeatable calibration cell NAME:SIZE_MIN:EDGE_MIN:DOSE[:CAP] "
                         "(CAP = opencity_cap, per-city cap on the raw product; omitted "
                         "or 0 == uncapped, the CL-080-era form); "
                         f"default = the pre-registered ladder {list(DEFAULT_ARM_SPECS)}")
    ap.add_argument("--asymmetric", action="store_true",
                    help="run ALL arms with opencity_symmetric=False (own-side-only "
                         "penalty). NOT the pre-registered ladder — CALIB_READ_RULE §1 "
                         "holds symmetric=True because flipping it is a different term. "
                         "Stamped in every summary.")
    ap.add_argument("--workers", type=int, default=1,
                    help="archives graded CONCURRENTLY, one subprocess each (default 1)")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--sims", type=int, default=0,
                    help="sims per determinization (0 = the archive's own stamp)")
    ap.add_argument("--k-dets", type=int, default=0,
                    help="determinizations (0 = the archive's own stamp)")
    ap.add_argument("--rust-threads", type=int, default=None)
    ap.add_argument("--limit-games", type=int, default=0,
                    help="grade only the N NEWEST archives (smoke)")
    ap.add_argument("--limit-plies", type=int, default=0,
                    help="first N plies only (wiring smoke; summary marked partial)")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        arms = parse_arms(args.arm if args.arm else DEFAULT_ARM_SPECS)
    except ValueError as e:
        raise SystemExit(f"[opencity_e4] {e}")
    symmetric = not args.asymmetric

    if args.single:
        grade_archive(Path(args.single), out_dir, arms=arms, symmetric=symmetric,
                      seed=args.seed, sims=args.sims, k_dets=args.k_dets,
                      rust_threads=args.rust_threads, limit_plies=args.limit_plies)
        return 0

    archives = sorted(Path(args.archive_dir).glob("*.json"),
                      key=lambda p: p.name, reverse=True)
    if args.limit_games:
        archives = archives[: args.limit_games]
    todo = [p for p in archives if not (out_dir / f"game_{p.stem}.json").exists()]
    print(f"[opencity_e4] {len(archives)} archives, {len(archives)-len(todo)} already "
          f"done, {len(todo)} to grade; workers={args.workers} symmetric={symmetric} "
          f"arms={[a.spec() for a in arms]}", flush=True)

    jobs = []
    for p in todo:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--single", str(p),
               "-o", str(out_dir), "--seed", str(args.seed), "--sims", str(args.sims),
               "--k-dets", str(args.k_dets)]
        for a in arms:
            cmd += ["--arm", a.spec()]
        if args.asymmetric:
            cmd += ["--asymmetric"]
        if args.rust_threads is not None:
            cmd += ["--rust-threads", str(args.rust_threads)]
        if args.limit_plies:
            cmd += ["--limit-plies", str(args.limit_plies)]
        jobs.append((p.name, cmd))

    failed = _run_pool(jobs, args.workers)
    if failed:
        # Deliberately NO rollup on failure: a SUMMARY.json written over a partial
        # corpus is exactly the artifact someone would later mistake for the
        # calibration. Fix, re-run (resumable), and the rollup lands then.
        raise SystemExit(
            "[opencity_e4] subprocess failures on "
            f"{[f'{n} (rc={rc})' for n, rc in failed]} — stopping (fail loud; the "
            "per-ply jsonl is resumable, so re-running after the fix costs only the "
            "ungraded plies)")
    rollup(out_dir)
    return 0


if __name__ == "__main__":
    os.nice(19)
    sys.exit(main() or 0)
