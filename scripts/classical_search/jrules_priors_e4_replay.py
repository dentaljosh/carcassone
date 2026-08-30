#!/usr/bin/env python3
"""Offline E4-replay read for J-RULES **SURFACE B** — the anchor's rules as
POLICY PRIORS in the champion's PUCT search (measurement/jrules_priors_20260814/
DESIGN.md). The pick-flip rate that gates whether a strength cell is bought.

    scripts/classical_search/jrules_priors_e4_replay.py \
        -o measurement/jrules_priors_20260814/calib \
        [--arm NAME:DOSE[:MASK[:SCOPE]] ...] [--workers 6] \
        [--limit-games 1] [--limit-plies 0] [--archive-dir measurement/e4_games]

Sibling of `jrules_e4_replay.py` (surface A, the static leaf bundle), itself a
sibling of `opencity_e4_replay.py` / `denial_e4_replay.py`. A SIBLING and not a
refactor so **the flip rate stays the SAME STATISTIC** as CL-080's and surface
A's — same corpus, same arithmetic, same budget — and the ladders are directly
comparable (surface A's floor rung 0.25 flipped 23.65% and its deploy cell lost
−2.49 pts/deck confounded by budget).

THE ONE STRUCTURAL DIFFERENCE FROM EVERY PRIOR INSTRUMENT: the arm knobs are
**SEARCH-config knobs** (`HeuristicPriorConfig.jrules_prior_{dose,mask,scope}`),
NOT leaf fields. The candidate's LEAF — and therefore its leaf hash — EQUALS the
champion's `a36d2e15a3b3d71d` **by design**, so the old "candidate hash must
differ" guard is inverted here: every arm's leaf hash is asserted EQUAL to the
champion's, and liveness is proven instead by (1) the fail-closed kwargs probe
(`rust_agent.search_config_rs` raises TypeError on a stale carc_rs wheel), and
(2) a POSITIVE CONTROL search at construction — a pinned midgame root where dose
1.0 / mask 31 is known to move the expansion priors; a wheel or a wiring that
zeroed the dose fails it loudly instead of grading a champion-vs-champion null.

The arm tuple is `name:dose[:mask[:scope]]`:
  * dose  — the calibration axis; each legal child's dleaf gets dose*T(child)
            added before the prior softmax (1.0 == the interview's magnitudes).
  * mask  — per-rule ablation bits over J1|J2|J5|J6|J8, default 31.
  * scope — 'all' (default; every expansion, mover POV), 'own' (root-player
            nodes only, the opponent-model-free ablation) or 'opp' (S1,
            measurement/s1_asymmetry_prep — opponent-mover nodes only).

⚠️ S1 / scope='opp' READS A DIFFERENT STATISTIC. Under 'opp' the ROOT expansion
is byte-identical to the champion's BY DESIGN (the root's mover is the root
player), so E1 — the pick-flip rate — is SEARCH-MEDIATED ONLY and will be
materially lower than the 13.05% surface B read at scope 'all'. Two consequences,
both load-bearing:
  * the positive control is SCOPE-AWARE and INVERTED for 'opp' (root priors must
    NOT move; root VISITS must; the Own/Opp partition must reproduce All) —
    DESIGN §9.2, `_assert_surface_b_live`; and
  * this instrument also reports **E2**, the root visit-distribution TOTAL
    VARIATION distance vs the champion's pooled root: graded rather than
    lumpy, and it cannot be zero if the surface is live.

**The pre-registered ladder** (DESIGN §CALIBRATION; the default when no `--arm`
is passed; all rungs share a single champion search per ply):

    | arm name | dose | mask | scope |
    |----------|------|------|-------|
    | d0p5     | 0.5  | 31   | all   |
    | d1p0     | 1.0  | 31   | all   |
    | d2p0     | 2.0  | 31   | all   |

plus the pre-committed finer rung d0p25 (0.25:31:all), measured only when its
trigger fires — in a FRESH out-dir (resume is per-ply; see
missing_arms_in_resume) merged via merge_calib_dirs.py, exactly as surface A
did and disclosed.

What this does NOT do: play games, measure elo, claim a band, or touch
governance. A flip is not an improvement; a HIGH flip rate is a bigger risk, not
a bigger prize (the CL-080 anchor: 10.09% flip → −53.8 elo).

Design points inherited from ev_loss via the denial/open-city/surface-A
instruments, unchanged: rules profile resolved FROM each archive (one
subprocess per archive for the R9 latch); budget defaults to the archive's own
stamp; exact-tail and forced plies skipped; per-ply resumable jsonl; concurrent
archives as processes; CRN (same seed + same `_move_idx` on every arm, so all
arms search identical worlds and a flip is attributable to the prior surface,
not the draw).

⚠️ Requires a SURFACE-B-CAPABLE carc_rs build. `search_config_rs` forwards the
prior knobs as conditional kwargs; a stale wheel raises TypeError here at arm
construction — fail loud with the rebuild instruction, never a silent
champion-vs-champion null (which would read as "the strategy is worth nothing"
instead of "it never ran").
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

SCHEMA = "carcassonne-jrules-priors-e4-replay/v1"
DEFAULT_ARCHIVE_DIR = REPO / "measurement" / "e4_games"

#: The champion leaf of record (`governance/PRODUCTION.yaml`). Every candidate
#: arm's leaf hash must differ from whatever the running tree resolves as the
#: production leaf; this constant is the pinned expectation for THAT hash.
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

#: Mirror of `flat_leaf.JR_ALL` (J1|J2|J5|J6|J8 == 31), duplicated here so the
#: pure helpers stay free of any `carcassonne_ai` import. `tests/
#: test_jrules_priors_e4_replay.py::test_mask_constants_match_flat_leaf` pins the
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
    "d0p5:0.5:31:all",
    "d1p0:1.0:31:all",
    "d2p0:2.0:31:all",
)

#: The pre-committed finer rung (CALIB_READ_RULE §3.1). NOT in the default
#: ladder: it is measured only when its trigger fires, and then as a named
#: addition, never silently.
FINER_RUNG_ARM_SPEC = "d0p25:0.25:31:all"

#: z for a two-sided 95% interval (the CI the read-rule asks for, by name).
Z95 = 1.959963984540054


# ==========================================================================  #
# PURE HELPERS — importable with no `carcassonne_ai` / `ev_loss` import.      #
# Everything below this banner and above the "arms" banner must stay free of  #
# heavy imports so the unit tests are instant and never latch the leaf env.   #
# ==========================================================================  #
@dataclass(frozen=True)
class Arm:
    """One calibration rung: a name plus the three SEARCH knobs that define it.

    `dose` is the calibration axis. `mask` is an ABLATION surface held at
    JR_ALL in every pre-registered rung. `scope` is 'all' (every expansion,
    mover POV — the primary), 'own' (root-player nodes only — the
    opponent-model-free ablation, a legitimate separate calibration) or 'opp'
    (S1, `measurement/s1_asymmetry_prep/DESIGN.md` — the COMPLEMENT of 'own',
    i.e. opponent-mover nodes only: the opponent-model arm).

    ⚠️ **`scope='opp'` reads a DIFFERENT statistic.** Under 'opp' the root
    expansion is byte-identical to the champion's by design, so E1 (the pick
    flip rate) is search-mediated only and will be materially lower than the
    13.05 % surface B read at scope 'all'. That is why this instrument also
    carries E2 — the root visit-distribution total-variation distance — which
    is graded, cannot be zero if the surface is live, and is immune to the
    argmax quantisation that makes E1 lumpy (DESIGN §6.2)."""

    name: str
    dose: float
    mask: int = DEFAULT_MASK
    scope: str = "all"

    def spec(self) -> str:
        """The `--arm` string that round-trips back to this Arm."""
        return f"{self.name}:{self.dose:g}:{self.mask:d}:{self.scope}"

    def as_dict(self) -> dict:
        return {"name": self.name, "dose": float(self.dose),
                "mask": int(self.mask), "scope": self.scope}


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
        raise ValueError("--arm is empty; expected NAME:DOSE[:MASK[:SCOPE]]")
    parts = raw.split(":")
    if len(parts) not in (2, 3, 4):
        raise ValueError(
            f"--arm {spec!r}: expected NAME:DOSE[:MASK[:SCOPE]] (2-4 "
            f"colon-separated fields), got {len(parts)}")
    name, d_raw = (p.strip() for p in parts[:2])
    m_raw = parts[2].strip() if len(parts) >= 3 else str(DEFAULT_MASK)
    scope = parts[3].strip() if len(parts) == 4 else "all"
    if scope not in ("all", "own", "opp"):
        raise ValueError(
            f"--arm {spec!r}: SCOPE {scope!r} must be 'all', 'own' or 'opp' — an "
            "unknown scope would be silently coerced by nothing; refusing")

    if not name:
        raise ValueError(f"--arm {spec!r}: NAME is empty")
    if any(c.isspace() for c in name):
        raise ValueError(f"--arm {spec!r}: NAME {name!r} may not contain whitespace")

    try:
        dose = float(d_raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: DOSE {d_raw!r} is not a number "
            "(jrules_prior_dose is a float; 1.0 == the interview's own "
            "magnitudes)") from None
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
            f"--arm {spec!r}: MASK {m_raw!r} is not an integer (jrules_prior_mask is a "
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

    return Arm(name=name, dose=dose, mask=mask, scope=scope)


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
        knobs = (arm.dose, arm.mask, arm.scope)
        if knobs in by_knobs:
            raise ValueError(
                f"arm {arm.name!r} duplicates the knobs of {by_knobs[knobs].name!r} "
                f"(dose={arm.dose:g}, mask={arm.mask}, scope={arm.scope}) — two names "
                f"for one cell would "
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
    `tests/test_jrules_priors_e4_replay.py (pins wilson_ci against the surface-A instrument)`)
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


def tv_distance(p, q) -> float:
    """Total-variation distance between two visit distributions — **E2**.

    `p`/`q` are `{action: visits}` maps (the PIMC-pooled root, i.e.
    `RustFairAgent.last_pooled_visits`). Each is normalized over its OWN total,
    then TV = 0.5 * sum |p_a - q_a| over the UNION of actions — so an action
    present in one pool and absent from the other contributes its full mass
    rather than being silently dropped.

    Range [0, 1]. `0.0` means the two searches distributed their root visits
    identically; under `scope='opp'`, where the root priors are identical by
    design, a corpus-wide E2 of 0.0 is the signature of a dead knob.

    An EMPTY pool on either side returns `None` (not 0.0): "no distribution"
    and "identical distributions" are different facts, and conflating them
    would let a forced/solved ply read as perfect agreement."""
    pt = sum(float(v) for v in (p or {}).values())
    qt = sum(float(v) for v in (q or {}).values())
    if pt <= 0.0 or qt <= 0.0:
        return None
    keys = set(p) | set(q)
    return 0.5 * sum(abs(float(p.get(k, 0.0)) / pt - float(q.get(k, 0.0)) / qt)
                     for k in keys)


def mean_tv(values) -> float:
    """Mean of the non-None TV values, or None when there are none."""
    vals = [float(v) for v in values if v is not None]
    return (sum(vals) / len(vals)) if vals else None


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
        # E2 — pooled over games as sum/n, NOT a mean of per-game means: games
        # carry different graded-ply counts, so averaging the means would
        # silently weight a 6-ply game like a 90-ply one.
        tv_n = sum(int(s.get("root_visit_tv_n", {}).get(name, 0)) for s in summaries)
        tv_sum = sum(float(s.get("root_visit_tv_sum", {}).get(name, 0.0))
                     for s in summaries)
        per_arm[name] = {
            "flips_total": flips,
            "n_graded": total,
            "flip_rate": (flips / total if total else None),
            # E2 (DESIGN §6.2): mean root visit-distribution TV vs the
            # champion's pooled root. Reported for every arm; it is the
            # LOAD-BEARING statistic for scope='opp', where E1 is
            # search-mediated only and therefore small by construction.
            "root_visit_tv_mean": (tv_sum / tv_n if tv_n else None),
            "root_visit_tv_n": tv_n,
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
                                         ("dose", "mask", "scope", "rules",
                                          "leaf_hash")})

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
        "root_visit_tv_mean": {n: per_arm[n]["root_visit_tv_mean"] for n in arm_names},
        "root_visit_tv_n": {n: per_arm[n]["root_visit_tv_n"] for n in arm_names},
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
                     "root_visit_tv_mean": s.get("root_visit_tv_mean"),
                     "root_visit_tv_n": s.get("root_visit_tv_n"),
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
        print("[jp_e4] ##############################################################")
        print("[jp_e4] WARNING: replay checksum NOT clean on "
              f"{len(roll['replay_scores_mismatch_archives'])} archive(s): "
              f"{roll['replay_scores_mismatch_archives']}")
        print("[jp_e4] CALIB_READ_RULE §1: any archive that fails its replay "
              "checksum VOIDS the whole calibration — fix and re-run (re-running is "
              "free: no band, no games, deterministic searches).")
        print("[jp_e4] (a partial run, --limit-plies, stamps null here by "
              "construction and is never a calibration.)")
        print("[jp_e4] ##############################################################")

    for name in _arm_order(summaries):
        a = roll["arms"][name]
        lo, hi = a["wilson95"]
        rate = a["flip_rate"]
        tv = a.get("root_visit_tv_mean")
        print(f"[jp_e4] {name:>8}: E1 flips {a['flips_total']:>5}/{a['n_graded']:<5} "
              f"= {'  n/a ' if rate is None else f'{100*rate:6.2f}%'} "
              f"[{100*lo:5.2f}%, {100*hi:5.2f}%]  "
              f"E2 tv {'  n/a ' if tv is None else f'{tv:6.4f}'} "
              f"(n {a.get('root_visit_tv_n', 0)})  "
              f"tiles/meeples {a['phase_split']['tiles']}/{a['phase_split']['meeples']}")
    print(f"[jp_e4] rollup: {roll['n_games']} games, {roll['n_graded_plies']} "
          f"graded plies, profiles={roll['rules_profile_histogram']}, "
          f"masks={roll['jrules_masks']}, "
          f"all_replay_scores_match={roll['all_replay_scores_match']} "
          f"-> {out_dir/'SUMMARY.json'}")
    print("[jp_e4] NOTE: a flip is not an improvement, and per DESIGN §7/CL-080 a "
          "BIGGER flip rate is a bigger risk, not a bigger prize. No elo, no band, no "
          "governance write — read against CALIB_READ_RULE §3, nothing else.")
    return roll


# ==========================================================================  #
# arms (heavy: everything below imports carcassonne_ai)                       #
# ==========================================================================  #
def _make_arms(game, spec, ex, seed, sims, k_dets, arms):
    """The champion arm (verify=True) + one SURFACE-B arm per calibration rung.

    The candidate arms replicate `make_production_champion`'s rust branch —
    RustFairAgent with the SAME game geometry, sims, k_dets, seed, exact
    settings AND THE SAME LEAF — with ONLY the search-config prior knobs set,
    so a pick flip is the prior surface's doing and nothing else's.

    ⚠️ GUARDS ARE INVERTED vs the surface-A instrument: surface B moves NO leaf
    hash, so every arm's leaf hash must EQUAL the champion's, and liveness is
    proven by the fail-closed kwargs probe + a positive-control search (a
    pinned midgame root where dose 1.0 / mask 31 provably moves the expansion
    priors)."""
    import dataclasses as dc

    from carcassonne_ai.champion_factory import (make_production_champion,
                                                 production_leaf_cfg,
                                                 production_prior_cfg)
    from carcassonne_ai.rust_agent import RustFairAgent, search_config_rs

    if not ex.is_rust:
        raise SystemExit(
            f"[jp_e4] execution resolved to backend={ex['backend']!r}; the "
            "J-rules PRIOR arms are rust-only (surface B lives in "
            "carc_core::search). Fix PRODUCTION.yaml resolution or pass a "
            "rust-capable environment.")

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
        print(f"[jp_e4] WARNING: production leaf hashes {champ_hash}, expected "
              f"{LEAF_HASH_OF_RECORD} (governance/PRODUCTION.yaml) — the champion arm "
              "is NOT the leaf of record; do not read this as a calibration.")

    # SCOPE-AWARE positive control (DESIGN §9.2): the legs run depend on which
    # scopes the arms actually use — 'opp' inverts the root-prior assertion.
    _assert_surface_b_live(tuple(a.scope for a in arms))

    agents, hashes = {}, {}
    for arm in arms:
        cfg_a = dc.replace(production_prior_cfg(spec, base_leaf),
                           jrules_prior_dose=float(arm.dose),
                           jrules_prior_mask=int(arm.mask),
                           jrules_prior_scope=str(arm.scope))
        # THE INVERTED HASH GUARD: surface B must NOT move the leaf. An arm
        # whose leaf hash differs from the champion's smuggled a LEAF change
        # into a PRIOR cell — refuse (leaf liveness is not prior liveness).
        h = _leaf_hash_of(cfg_a.resolved_leaf_cfg())
        if h != champ_hash:
            raise SystemExit(
                f"[jp_e4] arm {arm.name!r} ({arm.spec()}) moved the LEAF hash "
                f"({h} != champion {champ_hash}) — surface B is a search-prior "
                "intervention and must leave the leaf byte-identical. Something "
                "wrote a leaf field; refusing to run.")
        # Stale-wheel probe, BEFORE any search: `search_config_rs` forwards the
        # prior knobs as conditional kwargs, so a carc_rs predating surface B
        # raises TypeError here. Fail loud with the fix, never a
        # champion-vs-champion null.
        try:
            search_config_rs(cfg_a, 8)
        except TypeError as e:
            raise SystemExit(
                f"[jp_e4] arm {arm.name!r}: the installed carc_rs build does NOT "
                f"carry the J-rules PRIOR knobs ({e}). Rebuild/install the wheel on "
                "THIS box and re-run — do NOT work around it: exercising the real "
                "Rust prior surface is the entire point of this instrument.") from None
        except ValueError as e:
            # A wheel that HAS surface B but predates S1 rejects the scope
            # STRING (pyo3's parse match), which is a ValueError, not a
            # TypeError — a different stale-wheel shape with the same fix.
            raise SystemExit(
                f"[jp_e4] arm {arm.name!r} ({arm.spec()}): the installed carc_rs "
                f"build rejected scope={arm.scope!r} ({e}). If the scope is 'opp', "
                "this wheel predates S1 (JrPriorScope::Opp) — rebuild/install on "
                "THIS box and re-run.") from None
        agents[arm.name] = RustFairAgent(
            game, cfg_a,
            sims=(spec.sims_per_det if sims is None else int(sims)),
            k_dets=(spec.k_dets if k_dets is None else int(k_dets)),
            seed=int(seed), exact_endgame=True, exact_max_k=spec.exact_max_k,
            threads=(1 if ex["rust_threads"] is None else int(ex["rust_threads"])),
            **_geom(game))
        hashes[arm.name] = h
    return champ, agents, base_leaf, champ_hash, hashes


#: The pinned control root: deck seed 28000000000, 30 centre-policy plies,
#: 22 legal — the same root the rust unit gates pin.
_CONTROL_SEED, _CONTROL_PLIES = "28000000000", 30
#: Sims for the SYMMETRIC legs (root priors move immediately, so 32 suffices).
_CONTROL_SIMS_ROOT = 32
#: Sims for the OPP leg. Under scope='opp' the root is untouched by design, so
#: liveness can only be observed through INTERIOR opponent expansions, which the
#: search must actually REACH and then propagate back from.
#:
#: ⚠️ DEVIATION FROM DESIGN §9.2(b), MEASURED NOT ASSUMED. The design names
#: ">= 256 sims" and "the root VISIT distribution". Measured on the pinned
#: control root (and two siblings), 256 sims leaves this surface *entirely*
#: unexpressed — identical node_count, root_w bits, root visits AND pooled
#: stats — despite the gate firing at hundreds of opponent expansions; and even
#: at 1376 the top-level root VISIT COUNTS move on only 2 of 3 probe roots.
#: What moves on 3 of 3 at 1376 is `pooled_stats`, the deduped/N>0/root-POV
#: surface the PIMC pool actually argmaxes. So the control runs at the DEPLOY
#: sims-per-determinization of record (k16 x 1376 = 22016) and asserts on the
#: decision surface. The rust sibling gates
#: `s1_opp_moves_the_pooled_root_at_the_deploy_sims_per_det` and
#: `s1_opp_is_unexpressed_at_shallow_depth_on_the_control_root` pin both halves.
_CONTROL_SIMS_DEPTH = 1376


def _assert_surface_b_live(scopes=("all",)):
    """POSITIVE CONTROL (once per process), on the pinned midgame root.

    ⚠️ **DESIGN §9.2 — THE TRAP.** The original control asserted that ROOT
    PRIORS move between dose 0 and dose 1.0. That assertion is **wrong for
    `scope='opp'`**: the root's mover IS the root player, so the `opp` gate is
    OFF at the root *by design* and the root priors are identical. The old
    control would therefore fail on a **correctly wired** build, and — worse —
    a naive "fix" that made it pass would mean the scope gate was mis-wired.

    So the control is now SCOPE-AWARE and two-sided:

    * `all` / `own` — root priors MUST move (the original leg, unchanged);
    * `opp` — **(a)** root priors and the root leaf value MUST NOT move
      (a moved root prior is the defect), and **(b)** the POOLED root stats
      MUST move at the deploy sims-per-determinization (a bit-identical
      decision surface means the interior boost is dead-wired);
    * always — **(c)** the decomposition identity `Own ∪ Opp = All`, disjoint,
      read off the per-search expansion census.

    Every leg exists because surface B moves NO leaf hash, so no hash check can
    catch a silently-inert knob; without this the instrument would grade a
    perfect champion-vs-champion null wearing the shape of a calibration."""
    import carc_rs

    from carcassonne_ai.rust_agent import leaf_config_rs
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    if not hasattr(carc_rs.MirrorState, "jrules_prior_probe"):
        raise SystemExit(
            "[jp_e4] installed carc_rs predates J-rules PRIORS surface B "
            "(no MirrorState.jrules_prior_probe). Rebuild the wheel on THIS box "
            "(maturin build in rust/carc/carc-py + reinstall).")
    m = carc_rs.MirrorState.from_seed(_CONTROL_SEED)
    for _ in range(_CONTROL_PLIES):
        la = m.legal_actions()
        m.advance(la[len(la) // 2])
    leaf = leaf_config_rs(DEFAULT_CONFIG)

    def _cfg(sims=_CONTROL_SIMS_ROOT, **jr):
        return carc_rs.SearchConfigRs(leaf, sims, 1.5, 5.0, 15.0, 15.0,
                                      "float", "visits", None, 1.0, True,
                                      "glibc_fma", **jr)

    scopes = tuple(dict.fromkeys(scopes))          # de-dup, order-preserving
    unknown = [s for s in scopes if s not in ("all", "own", "opp")]
    if unknown:
        raise SystemExit(f"[jp_e4] positive control: unknown scope(s) {unknown}")

    # ---- the symmetric legs: root priors MUST move --------------------------
    off = m.search_single(_cfg())
    for scope in [s for s in scopes if s in ("all", "own")]:
        on = m.search_single(_cfg(jrules_prior_dose=1.0, jrules_prior_scope=scope))
        if on["root_priors"] == off["root_priors"]:
            raise SystemExit(
                f"[jp_e4] POSITIVE CONTROL FAILED (scope={scope!r}): dose 1.0 did not "
                "move the expansion priors on the pinned control root. The prior "
                "surface is dead-wired (zeroed dose, dropped kwargs, or a broken "
                "wheel) — refusing to grade, because every arm would read a perfect "
                "champion-vs-champion null.")
        if on["root_leaf_value_bits"] != off["root_leaf_value_bits"]:
            raise SystemExit(
                f"[jp_e4] POSITIVE CONTROL FAILED THE OTHER WAY (scope={scope!r}): "
                "dose 1.0 moved the root LEAF VALUE — surface B must only move "
                "priors. The installed wheel does not implement the surface this "
                "instrument thinks it is measuring; refusing to grade.")

    if "opp" not in scopes:
        return

    # ---- S1: the OPP legs ---------------------------------------------------
    # Stale-wheel gate FIRST: an old wheel rejects the scope string outright
    # (ValueError from the pyo3 parse match), which is fail-loud and correct,
    # but the message should name the fix.
    try:
        opp_root = m.search_single(_cfg(jrules_prior_dose=1.0,
                                        jrules_prior_scope="opp"))
    except ValueError as e:
        raise SystemExit(
            f"[jp_e4] the installed carc_rs build does NOT carry JrPriorScope::Opp "
            f"({e}). Rebuild/install the wheel on THIS box and re-run — do NOT work "
            "around it: exercising the real opponent-node gate is the entire point "
            "of the S1 instrument.") from None
    if "jr_expansions_total" not in opp_root:
        raise SystemExit(
            "[jp_e4] the installed carc_rs build accepts scope='opp' but reports no "
            "expansion census (no `jr_expansions_total` in the search result). That "
            "is a HALF-BUILT wheel: DESIGN §9.2 leg (c) cannot be checked, so the "
            "scope gate cannot be proven to partition anything. Rebuild and re-run.")

    # (a) MUST NOT MOVE — a moved root prior under 'opp' IS the defect.
    if opp_root["root_priors"] != off["root_priors"]:
        raise SystemExit(
            "[jp_e4] S1 CONTROL FAILED, leg (a): scope='opp' MOVED the ROOT priors. "
            "Under 'opp' the root's mover IS the root player, so the boost must be "
            "OFF at the root and the root priors must be byte-identical to the "
            "champion's. A moved root prior means the scope gate is mis-wired "
            "(inverted, or reading a stale root_player latch) — refusing to grade.")
    if opp_root["root_leaf_value_bits"] != off["root_leaf_value_bits"]:
        raise SystemExit(
            "[jp_e4] S1 CONTROL FAILED, leg (a): scope='opp' moved the root LEAF "
            "VALUE — surface B must only move priors; refusing to grade.")

    # (b) MUST MOVE — the root VISIT distribution, at a depth that reaches
    #     interior opponent nodes.
    deep_off = m.search_single(_cfg(sims=_CONTROL_SIMS_DEPTH))
    deep_opp = m.search_single(_cfg(sims=_CONTROL_SIMS_DEPTH,
                                    jrules_prior_dose=1.0,
                                    jrules_prior_scope="opp"))
    if int(deep_opp["jr_expansions_boosted"]) <= 0:
        raise SystemExit(
            f"[jp_e4] S1 CONTROL FAILED, leg (b): at {_CONTROL_SIMS_DEPTH} sims "
            "scope='opp' boosted ZERO expansions — the search never reached an "
            "opponent node, so nothing on this root can speak to liveness.")
    if deep_opp["pooled_stats"] == deep_off["pooled_stats"]:
        raise SystemExit(
            f"[jp_e4] S1 CONTROL FAILED, leg (b): at {_CONTROL_SIMS_DEPTH} sims "
            "scope='opp' left the POOLED ROOT STATS bit-identical to the "
            "champion's. With the root priors identical by design (leg a), a "
            "bit-identical decision surface is the signature of a DEAD knob — "
            "exactly the silently-inert-knob failure class that would grade a "
            "perfect champion-vs-champion null. Refusing to grade.")

    # (c) the decomposition identity, read within each tree (the only exact
    #     form: the three scopes' trees diverge the moment a prior moves).
    census = {}
    for scope in ("all", "own", "opp"):
        r = m.search_single(_cfg(sims=_CONTROL_SIMS_DEPTH, jrules_prior_dose=1.0,
                                 jrules_prior_scope=scope))
        census[scope] = (int(r["jr_expansions_total"]),
                         int(r["jr_expansions_own_mover"]),
                         int(r["jr_expansions_boosted"]))
    want = {"all": lambda t, o: t, "own": lambda t, o: o, "opp": lambda t, o: t - o}
    for scope, (tot, own, boosted) in census.items():
        if boosted != want[scope](tot, own):
            raise SystemExit(
                f"[jp_e4] S1 CONTROL FAILED, leg (c): scope={scope!r} boosted "
                f"{boosted} of {tot} expansions ({own} own-mover); the "
                "Own-and-Opp-partition-All identity does not hold, so the scope "
                "gate is not partitioning the node population it claims to.")
    tot, own, _ = census["opp"]
    if own <= 0 or tot <= own:
        raise SystemExit(
            f"[jp_e4] S1 CONTROL FAILED, leg (c) is VACUOUS: the control root's "
            f"expansion population is one-sided ({own} own-mover of {tot}). The "
            "identity holds trivially and proves nothing — raise the control sims "
            "or pin a different root.")
    # ⚠️ Print the triples PER SCOPE, never `own_boosted + opp_boosted` against
    # `all_total`: the three scopes run three DIFFERENT trees (the boost changes
    # what gets expanded), so the identity is a within-tree fact and a
    # cross-tree sum would not add up and would look like a failure.
    parts = " ".join(f"{sc}={b}/{o}/{t}" for sc, (t, o, b) in census.items())
    print(f"[jp_e4] S1 positive control PASS: (a) root priors + root leaf value "
          f"FROZEN under scope=opp; (b) pooled root stats MOVED at "
          f"{_CONTROL_SIMS_DEPTH} sims ({int(deep_opp['jr_expansions_boosted'])} "
          f"opponent expansions boosted); (c) partition holds within each tree "
          f"[boosted/own_mover/total] {parts}.")



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
        raise SystemExit(f"[jp_e4] {archive_path.name}: archive stamps no budget; "
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
            f"[jp_e4] {stem}: {ply_path.name} already holds graded plies that carry NO "
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
                # E2: the champion's POOLED root visit distribution, read once
                # per ply, immediately after its decision (`last_*` is per
                # decision — reading it later would grade the wrong search).
                champ_visits = dict(champ.last_pooled_visits)
                for name, agent in agents.items():
                    pick = int(agent.choose_action(board))
                    rec[f"pick_{name}"] = pick
                    rec[f"flip_{name}"] = bool(pick != champ_pick)
                    # E2 (DESIGN §6.2): graded, not lumpy — the statistic that
                    # can see a live opponent-node surface even on a ply where
                    # the argmax did not cross a boundary. `None` when either
                    # pool is empty (forced/solved), never 0.0.
                    rec[f"tv_{name}"] = tv_distance(champ_visits,
                                                    dict(agent.last_pooled_visits))
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
        "surface": "prior",   # surface B: SEARCH-prior knobs, leaf UNTOUCHED
        "arms": [{**a.as_dict(), "rules": mask_rules(a.mask),
                  # equal to the champion's BY DESIGN — a moved hash aborts _make_arms
                  "leaf_hash": hashes[a.name]} for a in arms],
        "leaf_hash_production": champ_hash,
        "n_plies_total": len(actions),
        "n_graded": len(recs),
        "n_searched_this_run": n_searched,
        "champ_agrees_archive": sum(1 for r in recs if r["champ_agrees_archive"]),
        "flips": {n: sum(1 for r in recs if r.get(f"flip_{n}")) for n in arm_names},
        # E2 — the root visit-distribution TV vs the champion's pooled root.
        # `tv_n` is how many plies actually carried a comparable pair, so the
        # rollup can weight the per-game means without assuming they match
        # `n_graded` (a forced/solved pool yields None, not 0.0).
        "root_visit_tv_mean": {n: mean_tv(r.get(f"tv_{n}") for r in recs)
                               for n in arm_names},
        "root_visit_tv_n": {n: sum(1 for r in recs if r.get(f"tv_{n}") is not None)
                            for n in arm_names},
        "root_visit_tv_sum": {n: sum(float(r[f"tv_{n}"]) for r in recs
                                     if r.get(f"tv_{n}") is not None)
                              for n in arm_names},
        "flip_plies": {n: [{k: r[k] for k in ("ply", "phase", "k_remaining",
                                              "champ_pick", f"pick_{n}")}
                           for r in recs if r.get(f"flip_{n}")] for n in arm_names},
        "mean_secs_per_graded_ply": (round(sum(r["secs"] for r in recs) / len(recs), 3)
                                     if recs else None),
        "env": env_stamp,
        "wall_secs": round(time.time() - t0, 1),
    }
    (out_dir / f"game_{stem}.json").write_text(json.dumps(summary, indent=1))
    print(f"[jp_e4] {stem}: profile={profile_name} graded={len(recs)} "
          f"flips={summary['flips']} "
          f"agree_archive={summary['champ_agrees_archive']}/{len(recs)} "
          f"mean_secs_per_graded_ply={summary['mean_secs_per_graded_ply']} "
          f"({summary['wall_secs']}s)", flush=True)
    return summary


def write_manifest(out_dir, args, arms, archives) -> dict:
    """Write `MANIFEST.json` — the RESOLVED config — BEFORE the first search.

    IS-D1: **config is read from the manifest, statistics from the summary.**
    Two separate files so a readout can never quote a knob it inferred from a
    directory name (the "dirname archaeology" failure this house has paid for),
    and so the config is on disk *before* any number exists — which is what makes
    a pre-committed read rule checkable after the fact.

    Provenance failures are RECORDED, not raised: the manifest is a stamp, not a
    gate (the gates are the inverted leaf-hash check and the §9.2 positive
    control, both of which run in the grading subprocesses)."""
    prov: dict = {}
    try:
        from carcassonne_ai.rust_agent import (backend_provenance,
                                               carc_rs_binary_sha,
                                               carc_rs_build_id)
        prov = {"carc_rs_binary_sha": carc_rs_binary_sha(),
                "carc_rs_build_id": carc_rs_build_id(),
                "backend": backend_provenance()}
    except Exception as e:                              # noqa: BLE001 - a stamp
        prov = {"error": f"{type(e).__name__}: {e}"}

    man = {
        "schema": SCHEMA + "/manifest",
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "surface": "prior",
        "instrument": str(Path(__file__).resolve().relative_to(REPO)),
        "out_dir": str(Path(out_dir).resolve()),
        # THE ARMS, fully resolved — including SCOPE, which is the only thing
        # separating S1's `opp` cell from surface B's banked `all` null.
        "arms": [{**a.as_dict(), "rules": mask_rules(a.mask), "spec": a.spec()}
                 for a in arms],
        "scopes": sorted({a.scope for a in arms}),
        "budget": {
            "sims_per_det": (int(args.sims) or None),
            "k_dets": (int(args.k_dets) or None),
            "total_per_decision": ((int(args.sims) * int(args.k_dets))
                                   if (args.sims and args.k_dets) else None),
            "source": ("CLI override" if (args.sims or args.k_dets)
                       else "each archive's own stamp"),
        },
        "seed": int(args.seed),
        "workers": int(args.workers),
        "rust_threads": args.rust_threads,
        "limit_games": int(args.limit_games),
        "limit_plies": int(args.limit_plies),
        "partial": bool(args.limit_plies),
        "archive_dir": str(Path(args.archive_dir).resolve()),
        "corpus": [p.name for p in archives],
        "n_archives": len(archives),
        "leaf_hash_expected": LEAF_HASH_OF_RECORD,
        "positive_control": {
            "seed": _CONTROL_SEED,
            "plies": _CONTROL_PLIES,
            "sims_root_leg": _CONTROL_SIMS_ROOT,
            "sims_depth_leg": _CONTROL_SIMS_DEPTH,
            "legs": ("symmetric scopes: root priors MUST move; "
                     "scope=opp: (a) root priors + root leaf value MUST NOT move, "
                     "(b) pooled root stats MUST move at the depth-leg sims, "
                     "(c) Own and Opp partition All within each tree"),
        },
        "provenance": prov,
    }
    (Path(out_dir) / "MANIFEST.json").write_text(json.dumps(man, indent=1))
    return man


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
                    print(f"[jp_e4] FAIL rc={rc} on {label} — no new archives "
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
    ap.add_argument("--arm", action="append", default=None,
                    metavar="NAME:DOSE[:MASK[:SCOPE]]",
                    help="repeatable calibration rung NAME:DOSE[:MASK[:SCOPE]] (MASK "
                         f"defaults to {DEFAULT_MASK} == JR_ALL; SCOPE is "
                         "'all'|'own'|'opp' and defaults to 'all') — "
                         "these are SEARCH-prior knobs, the leaf never moves; default "
                         f"= the pre-registered ladder {list(DEFAULT_ARM_SPECS)}")
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
        raise SystemExit(f"[jp_e4] {e}")

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
    print(f"[jp_e4] {len(archives)} archives, {len(archives)-len(todo)} already "
          f"done, {len(todo)} to grade; workers={args.workers} "
          f"arms={[a.spec() for a in arms]}", flush=True)

    # IS-D1: the RESOLVED config lands on disk BEFORE the first search, so the
    # read rule is checkable against what actually ran rather than what someone
    # remembers launching.
    write_manifest(out_dir, args, arms, archives)

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
            "[jp_e4] subprocess failures on "
            f"{[f'{n} (rc={rc})' for n, rc in failed]} — stopping (fail loud; the "
            "per-ply jsonl is resumable, so re-running after the fix costs only the "
            "ungraded plies)")
    rollup(out_dir)
    return 0


if __name__ == "__main__":
    os.nice(19)
    sys.exit(main() or 0)
