#!/usr/bin/env python3
"""Offline E4-replay read for the J-RULES ON SEARCH leaf bundle — the pick-flip
rate that gates whether a strength cell is bought at all (DESIGN §11 gate **G5**).

    scripts/classical_search/jrules_e4_replay.py \
        -o measurement/jrules_on_search_20260813/calib \
        [--arm NAME:DOSE[:MASK] ...] [--workers 6] \
        [--limit-games 1] [--limit-plies 0] [--archive-dir measurement/e4_games]

Sibling of `scripts/classical_search/opencity_e4_replay.py` (itself a sibling of
`denial_e4_replay.py`, the template of record). It is a SIBLING and not an
extension because this bundle's arms vary a **dose and a rule bitmask**, not the
open-city predicate thresholds — the arm tuple is `name:dose:mask`, so the shape
of `--arm` differs even though every statistic below is deliberately IDENTICAL.

**The flip rate this script prints is the SAME STATISTIC as the open-city
instrument's**, computed by the same arithmetic on the same corpus at the same
budget, so it is directly comparable to the CL-080 anchor (open-city flipped
**10.09%** and **18.89%** of champion picks and then cost **−53.8** and
**−190.3 elo** at the deploy budget; DESIGN §7). `tests/test_jrules_e4_replay.py`
pins `wilson_ci` against the open-city module's, value for value, so the two
rates can never drift into being different statistics.

Replays the E4 human-vs-champion phone archives and, at every CHAMPION decision
ply, runs the production search once per arm — the production leaf, plus one
J-rules leaf per (dose, mask) cell — with CRN determinizations (SAME agent seed
and SAME `_move_idx` on every arm, so all arms search identical worlds and a pick
flip is attributable to the leaf, not the draw). Reports the pick-flip rate with
a per-arm Wilson-95 CI, and exactly WHICH plies flip (game id, ply, phase,
k_remaining).

**The pre-registered ladder** (`measurement/jrules_on_search_20260813/
CALIB_READ_RULE.md` §1 == `DESIGN.md` §7; the default when no `--arm` is passed,
and all three rungs run in ONE pass sharing a single champion search per ply —
4 searches/ply, not 6):

    | arm name | jrules_dose | jrules_mask |
    |----------|-------------|-------------|
    | d0p5     | 0.5         | 31 (JR_ALL) |
    | d1p0     | 1.0         | 31 (JR_ALL) |
    | d2p0     | 2.0         | 31 (JR_ALL) |

The mask is held at **31 == `flat_leaf.JR_ALL` == J1|J2|J5|J6|J8** in every
pre-registered rung. A per-rule ablation mask is a *different question* (which
rule bites), not a rung on this ladder — it is supported by `--arm` so an
ablation can be run and named as its own calibration, and every mask actually
used is stamped in every summary so an ablation run can never be mistaken for
the pre-registered one.

There is deliberately **no `--asymmetric` flag** (the open-city instrument's one
run-level switch has no analogue here): DESIGN §12 Q1 rules that the J-rules
term stays antisymmetric and that an own-side-only variant is a NEW TERM needing
its own pre-registration, not a switch on this one.

What this does NOT do: play any games, measure any elo, claim any deck band, or
touch governance. It answers "does the bundle change the champion's play at all,
at plausible doses?" for free, so the deploy cell (DESIGN §8) is only bought if
some rung clears the resolvable-flip floor. A flip is not an improvement; nothing
this script prints licenses a strength claim, and per DESIGN §7 a HIGH flip rate
is a bigger risk, not a bigger prize.

Design points, all inherited from the ev_loss grader (scripts/analyzer/
ev_loss.py — the archive-replay precedent of record) via the denial/open-city
instruments:

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
  score — the leaf (and hence the J-rules bundle) cannot flip those plies by
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

⚠️ Requires a JRULES-CAPABLE carc_rs build (the bundle ships in the Rust leaf;
`rust_agent.leaf_config_rs` forwards the two knobs as conditional kwargs and a
stale build raises TypeError rather than silently searching an intact leaf —
DESIGN §11 G3's stale-wheel trap, which would read as "the anchor's strategy is
worth nothing" instead of "it never ran"). This script probes that capability
explicitly at arm construction and dies with a stale-wheel message. The champion
arm is `make_production_champion(verify=True)`; the candidate arms are the same
RustFairAgent construction with ONLY the leaf replaced, and every candidate's
`_leaf_hash` is asserted DIFFERENT from the champion's at construction — a
candidate that hashes to the champion is the silent-null failure mode this whole
campaign guards against.
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

SCHEMA = "carcassonne-jrules-e4-replay/v1"
DEFAULT_ARCHIVE_DIR = REPO / "measurement" / "e4_games"

#: The champion leaf of record (`governance/PRODUCTION.yaml`). Every candidate
#: arm's leaf hash must differ from whatever the running tree resolves as the
#: production leaf; this constant is the pinned expectation for THAT hash.
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

#: Mirror of `flat_leaf.JR_ALL` (J1|J2|J5|J6|J8 == 31), duplicated here so the
#: pure helpers stay free of any `carcassonne_ai` import. `tests/
#: test_jrules_e4_replay.py::test_mask_constants_match_flat_leaf` pins the
#: mirror against the real bits, so a rule added to the bundle can never leave
#: this validator silently rejecting a legitimate mask.
JR_J1, JR_J2, JR_J5, JR_J6, JR_J8 = 1, 2, 4, 8, 16
JR_ALL = JR_J1 | JR_J2 | JR_J5 | JR_J6 | JR_J8   # == 31
DEFAULT_MASK = JR_ALL

#: CALIB_READ_RULE §1 / DESIGN §7, verbatim. Fixed in advance; adding a rung
#: after seeing the ladder is a NEW calibration, not an extension of this one —
#: with ONE pre-committed exception, the dose-0.25 rung, whose trigger is a hard
#: number written down before any arm was read (CALIB_READ_RULE §3.1).
DEFAULT_ARM_SPECS = (
    "d0p5:0.5:31",
    "d1p0:1.0:31",
    "d2p0:2.0:31",
)

#: The pre-committed finer rung (CALIB_READ_RULE §3.1). NOT in the default
#: ladder: it is measured only when its trigger fires, and then as a named
#: addition, never silently.
FINER_RUNG_ARM_SPEC = "d0p25:0.25:31"

#: z for a two-sided 95% interval (the CI the read-rule asks for, by name).
Z95 = 1.959963984540054


# ==========================================================================  #
# PURE HELPERS — importable with no `carcassonne_ai` / `ev_loss` import.      #
# Everything below this banner and above the "arms" banner must stay free of  #
# heavy imports so the unit tests are instant and never latch the leaf env.   #
# ==========================================================================  #
@dataclass(frozen=True)
class Arm:
    """One calibration rung: a name plus the two knobs that define it.

    `dose` is the single calibration axis (DESIGN §7). `mask` is an ABLATION
    surface held at JR_ALL in every pre-registered rung; it is a per-arm field
    (unlike open-city's run-level `--asymmetric`) because a mask ablation is a
    legitimate separate calibration that wants several masks in one pass."""

    name: str
    dose: float
    mask: int = DEFAULT_MASK

    def spec(self) -> str:
        """The `--arm` string that round-trips back to this Arm."""
        return f"{self.name}:{self.dose:g}:{self.mask:d}"

    def as_dict(self) -> dict:
        return {"name": self.name, "dose": float(self.dose), "mask": int(self.mask)}


def mask_rules(mask: int) -> list:
    """`31` -> `['J1','J2','J5','J6','J8']` — the rules a mask enables, for stamps."""
    names = (("J1", JR_J1), ("J2", JR_J2), ("J5", JR_J5), ("J6", JR_J6), ("J8", JR_J8))
    return [n for n, bit in names if int(mask) & bit]


def parse_arm(spec: str) -> Arm:
    """`NAME:DOSE[:MASK]` -> Arm (MASK defaults to 31 == JR_ALL). Raises ValueError.

    Every rejection below is a silent-wrong-answer class, not a typo class: a
    dose-0 arm is the champion itself (the bundle early-branches off at dose 0, a
    guaranteed perfect null), and a mask-0 arm enables NO rule, so the term
    evaluates to exactly 0.0 at every leaf while the leaf HASH still differs from
    the champion's — i.e. it defeats the hash guard below and reads as a perfect
    null that looks like a real measurement. That is the worst outcome available
    from this script, so it is rejected here."""
    if not isinstance(spec, str):
        raise ValueError(f"--arm must be a string, got {type(spec).__name__}")
    raw = spec.strip()
    if not raw:
        raise ValueError("--arm is empty; expected NAME:DOSE[:MASK]")
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(
            f"--arm {spec!r}: expected NAME:DOSE or NAME:DOSE:MASK (2 or 3 "
            f"colon-separated fields), got {len(parts)}")
    name, d_raw = (p.strip() for p in parts[:2])
    m_raw = parts[2].strip() if len(parts) == 3 else str(DEFAULT_MASK)

    if not name:
        raise ValueError(f"--arm {spec!r}: NAME is empty")
    if any(c.isspace() for c in name):
        raise ValueError(f"--arm {spec!r}: NAME {name!r} may not contain whitespace")

    try:
        dose = float(d_raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: DOSE {d_raw!r} is not a number "
            "(jrules_dose is a float; 1.0 == the interview's own magnitudes)") from None
    if not math.isfinite(dose):
        raise ValueError(f"--arm {spec!r}: DOSE {d_raw!r} is not finite")
    if dose <= 0.0:
        raise ValueError(
            f"--arm {spec!r}: DOSE must be > 0, got {dose:g} — dose 0 IS the champion "
            "arm (the bundle is early-branched off at dose 0 and the leaf is byte "
            "identical), and the champion already runs as the reference arm on every "
            "ply, so a dose-0 candidate would read a guaranteed perfect null")

    if m_raw == "":
        m_raw = str(DEFAULT_MASK)
    try:
        mask = int(m_raw, 0)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: MASK {m_raw!r} is not an integer (jrules_mask is a "
            f"bitmask over J1|J2|J5|J6|J8; default {DEFAULT_MASK} == JR_ALL)") from None
    if mask == 0:
        raise ValueError(
            f"--arm {spec!r}: MASK must be non-zero — mask 0 enables NO rule, so the "
            "term is exactly 0.0 at every leaf while the leaf HASH still differs from "
            "the champion's. It slips past the hash guard and reads a perfect null "
            "that looks like a measurement")
    if mask < 0 or (mask & ~JR_ALL):
        raise ValueError(
            f"--arm {spec!r}: MASK {mask} has bits outside JR_ALL ({JR_ALL} == "
            f"J1|J2|J5|J6|J8) — an unknown bit is silently ignored by the leaf, so the "
            "arm would not be the arm you named")

    return Arm(name=name, dose=dose, mask=mask)


def parse_arms(specs) -> tuple:
    """A list of `--arm` strings -> a tuple of Arms, with uniqueness enforced."""
    items = list(specs or ())
    if not items:
        raise ValueError(
            "no arms: pass at least one --arm NAME:DOSE[:MASK], or omit --arm "
            f"entirely for the pre-registered ladder {list(DEFAULT_ARM_SPECS)}")
    arms, by_name, by_knobs = [], {}, {}
    for spec in items:
        arm = parse_arm(spec)
        if arm.name in by_name:
            raise ValueError(
                f"duplicate arm NAME {arm.name!r}: {by_name[arm.name].spec()!r} and "
                f"{arm.spec()!r} — names key every flip column in the rollup, so they "
                "must be unique")
        knobs = (arm.dose, arm.mask)
        if knobs in by_knobs:
            raise ValueError(
                f"arm {arm.name!r} duplicates the knobs of {by_knobs[knobs].name!r} "
                f"(dose={arm.dose:g}, mask={arm.mask}) — two names for one cell would "
                "double its search cost and read as two independent measurements")
        by_name[arm.name] = arm
        by_knobs[knobs] = arm
        arms.append(arm)
    return tuple(arms)


def missing_arms_in_resume(done_records, arms) -> list:
    """Arms that the ALREADY-GRADED plies carry no pick for — the late-added-arm trap.

    ⚠️ RESUME IS PER-PLY, NOT PER-ARM: an already-graded ply is never re-searched, so
    ADDING an `--arm` to an existing out-dir would leave the new arm with no pick on any
    resumed ply and it would roll up as **0.00%** — a perfect silent null wearing the shape
    of a real measurement, which is exactly what this instrument exists to prevent.
    (CALIB_READ_RULE §3.1's "added --arm over the same output directory" is unsound for
    that reason; measure a late-added rung in a FRESH out-dir, where the champion arm is
    re-run identically under the same seed/budget so the statistic is unchanged, and merge
    with `measurement/jrules_on_search_20260813/merge_calib_dirs.py`, which proves CRN
    identity by diffing the champion's own pick ply-by-ply.)

    An EMPTY resume set is not a violation — that is a fresh directory."""
    records = list(done_records)
    if not records:
        return []
    seen = {k[len("pick_"):] for r in records for k in r if str(k).startswith("pick_")}
    return sorted({a.name for a in arms} - seen)


def wilson_ci(k: int, n: int, z: float = Z95) -> tuple:
    """Wilson score interval for a binomial proportion — (lo, hi), clamped [0,1].

    Byte-for-byte the open-city instrument's function (pinned value-for-value by
    `tests/test_jrules_e4_replay.py::test_wilson_matches_the_opencity_instrument`)
    so this ladder's rates and the CL-080 anchor's are the SAME STATISTIC.

    The read-rule (CALIB_READ_RULE §1) requires per-arm 95% CIs alongside every
    flip rate, and the funding bar is read on the Wilson **lower** bound.

    Wilson (not Wald) because a rung can sit near f=0, where Wald's interval is
    degenerate."""
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
            "wilson95_lo": lo,          # the bar is read on THIS (CALIB_READ_RULE §2)
            "wilson95_half_width": (hi - lo) / 2.0,
            # Descriptive only — CALIB_READ_RULE §4 bars "where the flips land"
            # from the funding decision. Mirrors the open-city readout §5.
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
                                         ("dose", "mask", "rules", "leaf_hash")})

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
        "jrules_masks": sorted({int(a.get("mask", DEFAULT_MASK))
                                for s in summaries for a in s.get("arms", [])}),
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
        print("[jrules_e4] ##############################################################")
        print("[jrules_e4] WARNING: replay checksum NOT clean on "
              f"{len(roll['replay_scores_mismatch_archives'])} archive(s): "
              f"{roll['replay_scores_mismatch_archives']}")
        print("[jrules_e4] CALIB_READ_RULE §1: any archive that fails its replay "
              "checksum VOIDS the whole calibration — fix and re-run (re-running is "
              "free: no band, no games, deterministic searches).")
        print("[jrules_e4] (a partial run, --limit-plies, stamps null here by "
              "construction and is never a calibration.)")
        print("[jrules_e4] ##############################################################")

    for name in _arm_order(summaries):
        a = roll["arms"][name]
        lo, hi = a["wilson95"]
        rate = a["flip_rate"]
        print(f"[jrules_e4] {name:>8}: flips {a['flips_total']:>5}/{a['n_graded']:<5} "
              f"= {'  n/a ' if rate is None else f'{100*rate:6.2f}%'} "
              f"[{100*lo:5.2f}%, {100*hi:5.2f}%]  "
              f"tiles/meeples {a['phase_split']['tiles']}/{a['phase_split']['meeples']}")
    print(f"[jrules_e4] rollup: {roll['n_games']} games, {roll['n_graded_plies']} "
          f"graded plies, profiles={roll['rules_profile_histogram']}, "
          f"masks={roll['jrules_masks']}, "
          f"all_replay_scores_match={roll['all_replay_scores_match']} "
          f"-> {out_dir/'SUMMARY.json'}")
    print("[jrules_e4] NOTE: a flip is not an improvement, and per DESIGN §7/CL-080 a "
          "BIGGER flip rate is a bigger risk, not a bigger prize. No elo, no band, no "
          "governance write — read against CALIB_READ_RULE §3, nothing else.")
    return roll


# ==========================================================================  #
# arms (heavy: everything below imports carcassonne_ai)                       #
# ==========================================================================  #
def _make_arms(game, spec, ex, seed, sims, k_dets, arms):
    """The champion arm (verify=True) + one J-rules arm per calibration rung.

    The candidate arms replicate `make_production_champion`'s rust branch —
    RustFairAgent with the SAME game geometry, sims, k_dets, seed, exact
    settings — with ONLY the embedded leaf replaced, so a pick flip is the
    leaf's doing and nothing else's."""
    import dataclasses as dc

    from carcassonne_ai.champion_factory import (make_production_champion,
                                                 production_leaf_cfg,
                                                 production_prior_cfg)
    from carcassonne_ai.rust_agent import RustFairAgent, leaf_config_rs

    if not ex.is_rust:
        raise SystemExit(
            f"[jrules_e4] execution resolved to backend={ex['backend']!r}; the "
            "J-rules arms are rust-only (the bundle's production backend). Fix "
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
        print(f"[jrules_e4] WARNING: production leaf hashes {champ_hash}, expected "
              f"{LEAF_HASH_OF_RECORD} (governance/PRODUCTION.yaml) — the champion arm "
              "is NOT the leaf of record; do not read this as a calibration.")

    agents, hashes = {}, {}
    for arm in arms:
        leaf_a = dc.replace(base_leaf,
                            jrules_dose=float(arm.dose),
                            jrules_mask=int(arm.mask))
        h = _leaf_hash_of(leaf_a)
        # THE silent-null guard: a candidate that hashes to the champion is a
        # champion-vs-champion cell that reads as a perfect null.
        if h == champ_hash:
            raise SystemExit(
                f"[jrules_e4] arm {arm.name!r} ({arm.spec()}) hashes to the CHAMPION "
                f"leaf ({h}) — the bundle did not take. That is the silent-null failure "
                "mode this calibration exists to avoid (stale carc_rs wheel, dropped "
                "kwargs, or a dose that early-branches off). Refusing to run.")
        # Stale-wheel probe, BEFORE any search: `leaf_config_rs` forwards the
        # jrules knobs as conditional kwargs, so a carc_rs predating the bundle
        # raises TypeError here (DESIGN §11 G3). Fail loud with the fix, never a
        # champion-vs-champion null.
        try:
            leaf_config_rs(leaf_a)
        except TypeError as e:
            raise SystemExit(
                f"[jrules_e4] arm {arm.name!r}: the installed carc_rs build does NOT "
                f"carry the J-rules knobs ({e}). Rebuild/install the wheel on THIS box "
                "(DESIGN §11 G3) and re-run — do NOT work around it: exercising the "
                "real Rust term is the entire point of this instrument.") from None
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
        raise SystemExit(f"[jrules_e4] distinct arms share a leaf hash {sorted(dupes)}"
                         " — two cells would be one measurement. Refusing to run.")
    return champ, agents, base_leaf, champ_hash, hashes


def _leaf_hash_of(cfg) -> str:
    """The a36d2e15 harness dialect (provenance stamp)."""
    from carcassonne_ai.alphabeta_agent import _leaf_hash
    return _leaf_hash(cfg)


# ==========================================================================  #
# one archive                                                                 #
# ==========================================================================  #
def grade_archive(archive_path: Path, out_dir: Path, *, arms,
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
        raise SystemExit(f"[jrules_e4] {archive_path.name}: archive stamps no budget; "
                         "pass --sims/--k-dets")

    actions = arch["actions"][: limit_plies or None]
    deck_seed = arch["deck_seed"]
    champ_seat = 1 - arch["human_player"]

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    champ, agents, base_leaf, champ_hash, hashes = _make_arms(
        game, spec, ex, seed, sims_eff, k_eff, arms)
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
    missing = missing_arms_in_resume(done_plies.values(), arms)
    if missing:
        raise SystemExit(
            f"[jrules_e4] {stem}: {ply_path.name} already holds graded plies that carry NO "
            f"pick for arm(s) {missing}. Resume is per-PLY, so those plies would never be "
            "searched for the new arm and it would roll up as a 0.00% flip rate — a silent "
            "null. Run the new arm in a FRESH --out-dir (same corpus/seed/budget = same "
            "statistic; the champion arm is re-run there and its picks can be diffed "
            "ply-by-ply against this directory to prove CRN identity), or delete this "
            "directory and re-grade every arm together.")

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
        "arms": [{**a.as_dict(), "rules": mask_rules(a.mask),
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
    print(f"[jrules_e4] {stem}: profile={profile_name} graded={len(recs)} "
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
                    print(f"[jrules_e4] FAIL rc={rc} on {label} — no new archives "
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
    ap.add_argument("--arm", action="append", default=None, metavar="NAME:DOSE[:MASK]",
                    help="repeatable calibration rung NAME:DOSE[:MASK] (MASK defaults "
                         f"to {DEFAULT_MASK} == JR_ALL); default = the pre-registered "
                         f"ladder {list(DEFAULT_ARM_SPECS)}")
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
        raise SystemExit(f"[jrules_e4] {e}")

    if args.single:
        grade_archive(Path(args.single), out_dir, arms=arms,
                      seed=args.seed, sims=args.sims, k_dets=args.k_dets,
                      rust_threads=args.rust_threads, limit_plies=args.limit_plies)
        return 0

    archives = sorted(Path(args.archive_dir).glob("*.json"),
                      key=lambda p: p.name, reverse=True)
    if args.limit_games:
        archives = archives[: args.limit_games]
    todo = [p for p in archives if not (out_dir / f"game_{p.stem}.json").exists()]
    print(f"[jrules_e4] {len(archives)} archives, {len(archives)-len(todo)} already "
          f"done, {len(todo)} to grade; workers={args.workers} "
          f"arms={[a.spec() for a in arms]}", flush=True)

    jobs = []
    for p in todo:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--single", str(p),
               "-o", str(out_dir), "--seed", str(args.seed), "--sims", str(args.sims),
               "--k-dets", str(args.k_dets)]
        for a in arms:
            cmd += ["--arm", a.spec()]
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
            "[jrules_e4] subprocess failures on "
            f"{[f'{n} (rc={rc})' for n, rc in failed]} — stopping (fail loud; the "
            "per-ply jsonl is resumable, so re-running after the fix costs only the "
            "ungraded plies)")
    rollup(out_dir)
    return 0


if __name__ == "__main__":
    os.nice(19)
    sys.exit(main() or 0)
