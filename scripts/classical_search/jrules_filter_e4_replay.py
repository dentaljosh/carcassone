#!/usr/bin/env python3
"""Offline E4-replay read for J-RULES **SURFACE C** — the anchor's HARD FILTERS
as ROOT FILTERS on the champion's fair-PIMC root
(measurement/jrules_filters_20260814/DESIGN.md). The exclusion-rate ladder that
gates whether a strength cell is bought.

    scripts/classical_search/jrules_filter_e4_replay.py \
        -o measurement/jrules_filters_20260814/calib \
        [--arm NAME:MASK[:MIN_KEEP] ...] [--workers 6] \
        [--limit-games 1] [--limit-plies 0] [--archive-dir measurement/e4_games]

Sibling of `jrules_priors_e4_replay.py` (surface B) / `jrules_e4_replay.py`
(surface A) — same corpus, same graded-ply rule, same budget source, same
per-ply resumable jsonl, same CRN seed — with ONE structural difference that
makes this ladder far cheaper AND changes what "flip" means:

**A FILTER'S FLIP RATE IS ITS EXCLUSION RATE.** A root filter removes actions
from the root candidate set; when it removes the move the champion would have
played, the filtered agent CANNOT play it — that is a forced pick-flip, and it
is computable from (champion pick, filter decision) WITHOUT searching any
candidate arm. So per graded ply this instrument runs ONE champion search
(same budget/CRN as surface B's champion arm) and then evaluates every arm's
filter as a pure probe (`FairAgentRs.jrules_filter_probe`) on the same root:

    excluded_ARM  = champ_pick in ARM.dropped        (the flip)
    yield_ARM     = any never-empty guard fired      (the SAFETY read)

⚠️ KNOWN LIMIT, disclosed up front: exclusion is a LOWER BOUND on behavioural
change. Filtering non-picked actions reallocates their visits to survivors and
can flip the pick among KEPT actions too; counting those second-order flips
would cost a full k×1376 search per arm per ply (surface B's price) and is
deliberately not bought for a calibration. The read-rule reads the exclusion
rate as THE flip rate and says so.

The arm tuple is `name:mask[:min_keep]`:
  * mask — per-filter bits, 1=F-END, 2=F-J10, 4=F-J9, 8=F-J3; 11 == the bot's
           `current` stack (F-J9 is the bot's opt-in axis, tournament
           no-conviction; 15 adds it for the ablation).
  * min_keep — never-empty guard (default 1 == the bot's own rule).

**The pre-registered ladder** (CALIB_READ_RULE §1; the default when no --arm
is passed; all rungs share the single champion search per ply):

    | arm name | mask | filters                    |
    |----------|------|----------------------------|
    | j10      | 2    | F-J10 only                 |
    | j3       | 8    | F-J3 only                  |
    | current  | 11   | F-END + F-J10 + F-J3       |
    | all      | 15   | + F-J9 (opt-in ablation)   |

What this does NOT do: play games, measure elo, claim a band, or touch
governance. An exclusion is not an improvement; per CL-080 a HIGHER rate is a
bigger risk, not a bigger prize — and for a FILTER an excluded champion move is
evidence thrown away, not outvoted.

⚠️ Requires a SURFACE-C-CAPABLE carc_rs build (`FairAgentRs.jrules_filter_probe`).
A stale wheel fails loudly at construction with the rebuild instruction —
never a silent zero-exclusion null.
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

SCHEMA = "carcassonne-jrules-filter-e4-replay/v1"
DEFAULT_ARCHIVE_DIR = REPO / "measurement" / "e4_games"

#: The champion leaf of record (`governance/PRODUCTION.yaml`). Surface C moves
#: NO leaf — every arm's leaf hash must EQUAL this (the inverted guard, as
#: surface B).
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

#: Mirror of `carcassonne_ai.jrules_filter.JF_*` (pinned by
#: tests/test_jrules_filter_e4_replay.py so a drift can't hide).
JF_END, JF_J10, JF_J9, JF_J3 = 1, 2, 4, 8
JF_ALL = JF_END | JF_J10 | JF_J9 | JF_J3      # == 15
JF_CURRENT = JF_END | JF_J10 | JF_J3          # == 11
JF_FILTER_NAMES = ("f_end", "f_j10", "f_j9", "f_j3")

#: CALIB_READ_RULE §1, verbatim. Fixed in advance; adding a rung after seeing
#: the ladder is a NEW calibration (a filter has no dose, so there is no
#: finer-rung trigger — the mask lattice above IS the whole pre-registered
#: ladder).
DEFAULT_ARM_SPECS = (
    "j10:2",
    "j3:8",
    "current:11",
    "all:15",
)

#: z for a two-sided 95% interval.
Z95 = 1.959963984540054


# ==========================================================================  #
# PURE HELPERS — importable with no `carcassonne_ai` import.                  #
# ==========================================================================  #
@dataclass(frozen=True)
class Arm:
    """One calibration rung: a name plus the two FILTER knobs that define it."""

    name: str
    mask: int
    min_keep: int = 1

    def spec(self) -> str:
        return f"{self.name}:{self.mask:d}:{self.min_keep:d}"

    def as_dict(self) -> dict:
        return {"name": self.name, "mask": int(self.mask),
                "min_keep": int(self.min_keep)}


def mask_filters(mask: int) -> list:
    """`11` -> `['f_end','f_j10','f_j3']` — the filters a mask enables."""
    bits = (JF_END, JF_J10, JF_J9, JF_J3)
    return [n for n, b in zip(JF_FILTER_NAMES, bits) if int(mask) & b]


def parse_arm(spec: str) -> Arm:
    """`NAME:MASK[:MIN_KEEP]` -> Arm. Raises ValueError on every silent-null
    shape: mask 0 IS the champion (the probe would read 0% exclusion forever),
    bits outside JF_ALL are ignored by nothing and must not ride, min_keep < 1
    would defeat the never-empty contract."""
    if not isinstance(spec, str):
        raise ValueError(f"--arm must be a string, got {type(spec).__name__}")
    raw = spec.strip()
    if not raw:
        raise ValueError("--arm is empty; expected NAME:MASK[:MIN_KEEP]")
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(
            f"--arm {spec!r}: expected NAME:MASK[:MIN_KEEP] (2-3 fields), "
            f"got {len(parts)}")
    name = parts[0].strip()
    if not name:
        raise ValueError(f"--arm {spec!r}: NAME is empty")
    if any(c.isspace() for c in name):
        raise ValueError(f"--arm {spec!r}: NAME {name!r} may not contain whitespace")
    try:
        mask = int(parts[1].strip(), 0)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: MASK {parts[1]!r} is not an integer (bits "
            f"1=F-END, 2=F-J10, 4=F-J9, 8=F-J3)") from None
    if mask == 0:
        raise ValueError(
            f"--arm {spec!r}: MASK must be non-zero — mask 0 IS the champion "
            "(the filter never applies), so the arm would read a guaranteed "
            "0.00% exclusion rate wearing the shape of a measurement")
    if mask < 0 or (mask & ~JF_ALL):
        raise ValueError(
            f"--arm {spec!r}: MASK {mask} has bits outside JF_ALL ({JF_ALL} == "
            "F-END|F-J10|F-J9|F-J3) — an unknown bit would make the arm not "
            "the arm you named")
    mk_raw = parts[2].strip() if len(parts) == 3 else "1"
    try:
        min_keep = int(mk_raw, 0)
    except (TypeError, ValueError):
        raise ValueError(
            f"--arm {spec!r}: MIN_KEEP {mk_raw!r} is not an integer") from None
    if min_keep < 1:
        raise ValueError(
            f"--arm {spec!r}: MIN_KEEP must be >= 1 (the never-empty guard; "
            "1 == the bot's own rule)")
    return Arm(name=name, mask=mask, min_keep=min_keep)


def parse_arms(specs) -> tuple:
    items = list(specs or ())
    if not items:
        raise ValueError(
            "no arms: pass at least one --arm NAME:MASK[:MIN_KEEP], or omit "
            f"--arm entirely for the pre-registered ladder {list(DEFAULT_ARM_SPECS)}")
    arms, by_name, by_knobs = [], {}, {}
    for spec in items:
        arm = parse_arm(spec)
        if arm.name in by_name:
            raise ValueError(
                f"duplicate arm NAME {arm.name!r}: {by_name[arm.name].spec()!r} "
                f"and {arm.spec()!r}")
        knobs = (arm.mask, arm.min_keep)
        if knobs in by_knobs:
            raise ValueError(
                f"arm {arm.name!r} duplicates the knobs of "
                f"{by_knobs[knobs].name!r} (mask={arm.mask}, "
                f"min_keep={arm.min_keep})")
        by_name[arm.name] = arm
        by_knobs[knobs] = arm
        arms.append(arm)
    return tuple(arms)


def missing_arms_in_resume(done_records, arms) -> list:
    """Arms the ALREADY-GRADED plies carry no exclusion flag for — the
    late-added-arm trap (identical to surface B's; resume is per-PLY)."""
    records = list(done_records)
    if not records:
        return []
    seen = {k[len("excluded_"):] for r in records for k in r
            if str(k).startswith("excluded_")}
    return sorted({a.name for a in arms} - seen)


def wilson_ci(k: int, n: int, z: float = Z95) -> tuple:
    """Wilson score interval — byte-for-byte the surface-A/B instruments'
    function (pinned by the test), so the ladders are the SAME STATISTIC."""
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
    seen, order = set(), []
    for s in summaries:
        for name in [a["name"] for a in s.get("arms", [])] or list(s.get("exclusions", {})):
            if name not in seen:
                seen.add(name)
                order.append(name)
    return order


def rollup_from_summaries(summaries) -> dict:
    """Per-game summaries -> the corpus rollup CALIB_READ_RULE §1 demands:
    per-arm exclusion (=flip) rate with Wilson-95, the YIELD rate (the SAFETY
    branch's input), the applicable-ply (meeple-root) share, per-filter fire
    histograms, the rules-epoch histogram and the replay checksums."""
    summaries = list(summaries)
    arm_names = _arm_order(summaries)
    total = sum(int(s.get("n_graded", 0)) for s in summaries)

    per_arm = {}
    for name in arm_names:
        excl = sum(int(s.get("exclusions", {}).get(name, 0)) for s in summaries)
        ylds = sum(int(s.get("yields", {}).get(name, 0)) for s in summaries)
        appl = sum(int(s.get("applicable", {}).get(name, 0)) for s in summaries)
        lo, hi = wilson_ci(excl, total)
        ylo, yhi = wilson_ci(ylds, total)
        fires: dict = {}
        for s in summaries:
            for fname, cnt in s.get("filter_fires", {}).get(name, {}).items():
                fires[fname] = fires.get(fname, 0) + int(cnt)
        per_arm[name] = {
            "exclusions_total": excl,
            "n_graded": total,
            "exclusion_rate": (excl / total if total else None),   # THE flip rate
            "wilson95": [lo, hi],
            "wilson95_lo": lo,           # the funding bar is read on THIS
            "yields_total": ylds,
            "yield_rate": (ylds / total if total else None),       # the SAFETY read
            "yield_wilson95": [ylo, yhi],
            "applicable_plies": appl,
            "applicable_share": (appl / total if total else None),
            "filter_fires": fires,       # descriptive only (read-rule §4)
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
                                         ("mask", "min_keep", "filters", "leaf_hash")})

    return {
        "schema": SCHEMA + "/rollup",
        "n_games": len(summaries),
        "n_graded_plies": total,
        "arm_knobs": knobs,
        "arms": per_arm,
        "exclusions_total": {n: per_arm[n]["exclusions_total"] for n in arm_names},
        "exclusion_rate": {n: per_arm[n]["exclusion_rate"] for n in arm_names},
        "yield_rate": {n: per_arm[n]["yield_rate"] for n in arm_names},
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
        "jf_masks": sorted({int(a.get("mask", 0))
                            for s in summaries for a in s.get("arms", [])}),
        "budget_by_archive": {str(s.get("archive")): s.get("budget")
                              for s in summaries},
        "by_game": [{"archive": s.get("archive"), "profile": s.get("rules_profile"),
                     "n_graded": s.get("n_graded"),
                     "exclusions": s.get("exclusions"),
                     "yields": s.get("yields"),
                     "replay_scores_match": s.get("replay_scores_match"),
                     "budget": s.get("budget"),
                     "recorded_scores": s.get("recorded_scores"),
                     "human_player": s.get("human_player"),
                     "exclusion_plies": s.get("exclusion_plies")}
                    for s in summaries],
    }


def rollup(out_dir) -> dict:
    out_dir = Path(out_dir)
    games = sorted(out_dir.glob("game_*.json"))
    if not games:
        return {}
    summaries = [json.loads(p.read_text()) for p in games]
    roll = rollup_from_summaries(summaries)
    (out_dir / "SUMMARY.json").write_text(json.dumps(roll, indent=1))

    if not roll["all_replay_scores_match"]:
        print("[jf_e4] ##############################################################")
        print("[jf_e4] WARNING: replay checksum NOT clean on "
              f"{len(roll['replay_scores_mismatch_archives'])} archive(s): "
              f"{roll['replay_scores_mismatch_archives']}")
        print("[jf_e4] CALIB_READ_RULE §1: a failing replay checksum VOIDS the "
              "whole calibration — fix and re-run (free: no band, no games).")
        print("[jf_e4] ##############################################################")

    for name in _arm_order(summaries):
        a = roll["arms"][name]
        lo, hi = a["wilson95"]
        rate = a["exclusion_rate"]
        yrate = a["yield_rate"]
        print(f"[jf_e4] {name:>8}: excluded {a['exclusions_total']:>4}/{a['n_graded']:<5}"
              f" = {'  n/a ' if rate is None else f'{100*rate:6.2f}%'} "
              f"[{100*lo:5.2f}%, {100*hi:5.2f}%]  "
              f"yield {'  n/a ' if yrate is None else f'{100*yrate:5.2f}%'}  "
              f"applicable {a['applicable_plies']}/{a['n_graded']}")
    print(f"[jf_e4] rollup: {roll['n_games']} games, {roll['n_graded_plies']} "
          f"graded plies, profiles={roll['rules_profile_histogram']}, "
          f"masks={roll['jf_masks']}, "
          f"all_replay_scores_match={roll['all_replay_scores_match']} "
          f"-> {out_dir/'SUMMARY.json'}")
    print("[jf_e4] NOTE: an exclusion is not an improvement — it is the champion's "
          "move THROWN AWAY. Read against CALIB_READ_RULE §3 (incl. the SAFETY "
          "branch on the yield rate), nothing else. No elo, no band, no governance "
          "write.")
    return roll


# ==========================================================================  #
# arms (heavy: everything below imports carcassonne_ai)                       #
# ==========================================================================  #
def _assert_surface_c_live():
    """POSITIVE CONTROL (once per process): on a pinned early meeple root
    (deck seed 28000000000, centre policy) the F-J10 probe at mask 2 must DROP
    at least one farmer action within the first 60 plies, and mask 0 must be
    inapplicable everywhere. Because surface C moves no leaf hash, NO hash
    check can catch a dead-wired filter — this control is the liveness proof,
    exactly as `_assert_surface_b_live` is for the prior surface."""
    import carc_rs

    if not hasattr(carc_rs.MirrorState, "jrules_filter_probe"):
        raise SystemExit(
            "[jf_e4] installed carc_rs predates J-rules root filters surface C "
            "(no MirrorState.jrules_filter_probe). Rebuild the wheel on THIS "
            "box (maturin build --release in rust/carc/carc-py + reinstall).")
    m = carc_rs.MirrorState.from_seed("28000000000")
    dropped_somewhere = False
    for _ in range(60):
        p = m.jrules_filter_probe(JF_J10)
        if p["applicable"] and list(p["dropped"]):
            dropped_somewhere = True
            break
        la = m.legal_actions()
        m.advance(la[len(la) // 2])
    if not dropped_somewhere:
        raise SystemExit(
            "[jf_e4] POSITIVE CONTROL FAILED: the F-J10 probe (mask 2) dropped "
            "nothing in 60 centre-policy plies of the pinned control game. The "
            "filter surface is dead-wired (broken wheel or zeroed mask) — "
            "refusing to grade, because every arm would read a perfect 0% "
            "exclusion null.")


def _leaf_hash_of(cfg) -> str:
    from carcassonne_ai.alphabeta_agent import _leaf_hash
    return _leaf_hash(cfg)


def _make_champ(game, spec, ex, seed, sims, k_dets, arms):
    """ONE champion (verify=True) — the only agent that searches. Every arm is
    a pure probe against the champion's own mirror. Guards: rust-only; the
    champion leaf must be the leaf of record; the stale-wheel kwargs probe must
    raise on a pre-C wheel; the positive control must pass."""
    from carcassonne_ai.champion_factory import (make_production_champion,
                                                 production_leaf_cfg,
                                                 production_prior_cfg)
    from carcassonne_ai.rust_agent import search_config_rs

    if not ex.is_rust:
        raise SystemExit(
            f"[jf_e4] execution resolved to backend={ex['backend']!r}; the "
            "J-rules FILTER probe is rust-only (surface C lives in "
            "carc_core::fair). Fix PRODUCTION.yaml resolution or pass a "
            "rust-capable environment.")

    champ = make_production_champion("fair", game=game, seed=int(seed), sims=sims,
                                     k_dets=k_dets, verify=True, **ex.factory_kwargs())
    if not hasattr(getattr(champ, "_rs", None), "jrules_filter_probe"):
        raise SystemExit(
            "[jf_e4] the champion's FairAgentRs has no jrules_filter_probe — "
            "installed carc_rs predates surface C. Rebuild the wheel on THIS box.")

    base_leaf = production_leaf_cfg(spec)
    champ_hash = _leaf_hash_of(base_leaf)
    if champ_hash != LEAF_HASH_OF_RECORD:
        print(f"[jf_e4] WARNING: production leaf hashes {champ_hash}, expected "
              f"{LEAF_HASH_OF_RECORD} (governance/PRODUCTION.yaml) — do not read "
              "this as a calibration.")

    # Stale-wheel fail-closed probe per arm (TypeError on a pre-C wheel), and
    # the INVERTED hash guard: a filter arm may not move the leaf.
    import dataclasses as dc
    for arm in arms:
        cfg_a = dc.replace(production_prior_cfg(spec, base_leaf),
                           jrules_filter_mask=int(arm.mask),
                           jrules_filter_min_keep=int(arm.min_keep))
        h = _leaf_hash_of(cfg_a.resolved_leaf_cfg())
        if h != champ_hash:
            raise SystemExit(
                f"[jf_e4] arm {arm.name!r} moved the LEAF hash ({h} != champion "
                f"{champ_hash}) — surface C must leave the leaf byte-identical.")
        try:
            search_config_rs(cfg_a, 8)
        except TypeError as e:
            raise SystemExit(
                f"[jf_e4] arm {arm.name!r}: the installed carc_rs build does NOT "
                f"carry the J-rules FILTER knobs ({e}). Rebuild/install the wheel "
                "on THIS box and re-run.") from None

    _assert_surface_c_live()
    return champ, champ_hash


# ==========================================================================  #
# one archive                                                                 #
# ==========================================================================  #
def grade_archive(archive_path: Path, out_dir: Path, *, arms,
                  seed, sims, k_dets, rust_threads, limit_plies=0) -> dict:
    import random

    import numpy as np

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
        raise SystemExit(f"[jf_e4] {archive_path.name}: archive stamps no budget; "
                         "pass --sims/--k-dets")

    actions = arch["actions"][: limit_plies or None]
    deck_seed = arch["deck_seed"]
    champ_seat = 1 - arch["human_player"]

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    champ, champ_hash = _make_champ(game, spec, ex, seed, sims_eff, k_eff, arms)
    reseat(champ, deck_seed=deck_seed, actions=(), move_idx=0)

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
            f"[jf_e4] {stem}: {ply_path.name} already holds graded plies with NO "
            f"exclusion flag for arm(s) {missing}. Resume is per-PLY; a late-added "
            "arm would roll up as a 0.00% silent null. Run the new arm in a FRESH "
            "--out-dir, or delete this directory and re-grade every arm together.")

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
                champ._move_idx = ply                    # CRN: same worlds as B's ladder
                s0 = time.time()
                champ_pick = int(champ.choose_action(board))
                rec["champ_pick"] = champ_pick
                rec["champ_agrees_archive"] = bool(champ_pick == int(played))
                for arm in arms:
                    p = champ._rs.jrules_filter_probe(int(arm.mask),
                                                      int(arm.min_keep))
                    dropped = [int(x) for x in p["dropped"]]
                    fires = dict(p["fires"])
                    ylds = dict(p["yields"])
                    rec[f"applicable_{arm.name}"] = bool(p["applicable"])
                    rec[f"excluded_{arm.name}"] = bool(champ_pick in dropped)
                    rec[f"yield_{arm.name}"] = bool(any(ylds.values()))
                    rec[f"dropped_{arm.name}"] = dropped
                    rec[f"fires_{arm.name}"] = [n for n, v in fires.items() if v]
                rec["secs"] = round(time.time() - s0, 3)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                recs.append(rec)
                n_searched += 1
                if n_searched % 8 == 0:
                    print(f"  [{stem}] ply {ply}/{len(actions)} graded={n_searched} "
                          f"{time.time()-t0:.0f}s", flush=True)
            board, _ = game.get_next_state(board, int(played))
            advance([champ], int(played))

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
        "replay_scores_match": (None if partial else
                                (arch["recorded_scores"] is not None
                                 and list(board.state.scores) == arch["recorded_scores"])),
        "partial": partial,
        "budget": {"sims_per_det": sims_eff, "k_dets": k_eff,
                   "total_per_decision": sims_eff * k_eff,
                   "source": ("archive" if not (sims or k_dets) else "CLI override")},
        "seed": int(seed),
        "surface": "root_filter",   # surface C: fair-agent root, leaf UNTOUCHED
        "arms": [{**a.as_dict(), "filters": mask_filters(a.mask),
                  # equal to the champion's BY DESIGN — a moved hash aborts _make_champ
                  "leaf_hash": champ_hash} for a in arms],
        "leaf_hash_production": champ_hash,
        "n_plies_total": len(actions),
        "n_graded": len(recs),
        "n_searched_this_run": n_searched,
        "champ_agrees_archive": sum(1 for r in recs if r["champ_agrees_archive"]),
        "exclusions": {n: sum(1 for r in recs if r.get(f"excluded_{n}"))
                       for n in arm_names},
        "yields": {n: sum(1 for r in recs if r.get(f"yield_{n}"))
                   for n in arm_names},
        "applicable": {n: sum(1 for r in recs if r.get(f"applicable_{n}"))
                       for n in arm_names},
        "filter_fires": {n: {fn: sum(1 for r in recs
                                     if fn in r.get(f"fires_{n}", []))
                             for fn in JF_FILTER_NAMES} for n in arm_names},
        "exclusion_plies": {n: [{k: r[k] for k in
                                 ("ply", "phase", "k_remaining", "champ_pick",
                                  f"dropped_{n}", f"fires_{n}")}
                                for r in recs if r.get(f"excluded_{n}")]
                            for n in arm_names},
        "mean_secs_per_graded_ply": (round(sum(r["secs"] for r in recs) / len(recs), 3)
                                     if recs else None),
        "env": env_stamp,
        "wall_secs": round(time.time() - t0, 1),
    }
    (out_dir / f"game_{stem}.json").write_text(json.dumps(summary, indent=1))
    print(f"[jf_e4] {stem}: profile={profile_name} graded={len(recs)} "
          f"exclusions={summary['exclusions']} yields={summary['yields']} "
          f"agree_archive={summary['champ_agrees_archive']}/{len(recs)} "
          f"({summary['wall_secs']}s)", flush=True)
    return summary


# ==========================================================================  #
# orchestrator                                                                #
# ==========================================================================  #
def _run_pool(jobs, workers: int, poll: float = 0.2) -> list:
    """[(label, argv), ...] as at most `workers` CONCURRENT SUBPROCESSES —
    byte-for-byte the surface-B pool (fresh R9 latch per archive; drain on
    first failure; report all)."""
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
                    print(f"[jf_e4] FAIL rc={rc} on {label} — no new archives "
                          f"will launch; draining {len(running)} in flight",
                          flush=True)
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR))
    ap.add_argument("--single", default=None,
                    help="grade ONE archive in THIS process (internal)")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--arm", action="append", default=None,
                    metavar="NAME:MASK[:MIN_KEEP]",
                    help="repeatable calibration rung (bits 1=F-END, 2=F-J10, "
                         "4=F-J9, 8=F-J3; MIN_KEEP defaults to 1) — SEARCH-config "
                         "knobs, the leaf never moves; default = the pre-registered "
                         f"ladder {list(DEFAULT_ARM_SPECS)}")
    ap.add_argument("--workers", type=int, default=1)
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
        raise SystemExit(f"[jf_e4] {e}")

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
    print(f"[jf_e4] {len(archives)} archives, {len(archives)-len(todo)} already "
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
        raise SystemExit(
            "[jf_e4] subprocess failures on "
            f"{[f'{n} (rc={rc})' for n, rc in failed]} — stopping (fail loud; the "
            "per-ply jsonl is resumable)")
    rollup(out_dir)
    return 0


if __name__ == "__main__":
    os.nice(19)
    sys.exit(main() or 0)
