#!/usr/bin/env python3
"""rung3_r5 corpus assembler — `G-CORPUS` / `G-INTERNAL-DUPE` / `G-BAND` emitter
(`measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md` §R5-FINAL.i,
`READ_RULE.md` §2, spec commit `bed67165`).

WHAT THIS DOES. `RUN` = `measurement/tiearb_widening_20260817/rung3_r5/`.

DESIGN §R5-FINAL.b2 rules that rung 3's corpus is **R4's POST-EXCLUSION S2 leg
file, ADOPTED AS-IS — not re-mined.** Re-mining would re-admit the 28 rids R4
already excluded and force R5 to re-derive a decision R4 already made. So this
builder:

  1. Reads the physical leg file (default: R4's
     `corpus/positions_s2/positions_walled_leg1.jsonl`, 1,064 rows) and
     verifies its sha256 against the PINNED value, raising on mismatch — the
     "sha-pinned adoption" is a hard check, not a comment.
  2. Loads R4's OWN digest-exclusion list from `shared_run_r4/GATE_DISJOINT.json
     ::digest_exclusions.S2.rids` and computes `r4_exclusion_list_sha256`
     under the EXACT canonical serialization DESIGN §R5-FINAL.j pins:
     `sha256(json.dumps(sorted(rids)))`, default separators, no `sort_keys`
     (the input is a list), UTF-8, no trailing newline. Verified against the
     PINNED value.
  3. Finds which of R4's excluded rids are STILL PHYSICALLY PRESENT in the
     leg (R4 intended to remove all 29; the artifact shows 28 absent, 1
     residual) — computed fresh from source, never hardcoded.
  4. Finds R5's OWN same-checksum internal-duplicate groups within the leg
     (digests reused from `gate_disjoint.load_digest_map` — never
     recomputed here) and excludes the later-ordered (lexicographically
     larger rid) member of each group, keeping one representative per board.
  5. Loads R4's REAL, pre-exclusion S2 `ARMS.json` (`R4_ARMS` — DESIGN ruling
     `a13ed934`), asserts its rid set equals the leg's rid set (the D4
     invariant this ruling exists to restore: the leg files and ARMS must
     enumerate the SAME population), and MATERIALIZES `ARMS_R5.json` — `R4_ARMS`
     restricted to the 1,060 survivors — asserting the survivor rid set equals
     `R4_ARMS.rids − excluded_rids` in BOTH directions. This is the
     **population authority**: every consumer (`gate_disjoint --r5`, staging,
     scoring, the analyzer) reads `ARMS_R5.json`; none re-derives the
     population by subtraction (shape (b) was ruled OUT — "D4 with the
     operands swapped").
  6. Emits `CORPUS_R5.json` (`G-CORPUS` + the `G-BAND` range/mining-ceiling
     conjuncts, now including `arms_r5_sha256`), `GATE_INTERNAL_DUPE.json`
     (`G-INTERNAL-DUPE`), and `ARMS_R5.json`.

Pure counts; no scoring, no oracle, no champ picks — the class
`PREREG_FAILURE.md` §3.3 established as non-leaking.

⚠️ DISCLOSURE (DESIGN §R5-FINAL.h(4), READ_RULE §2.1). The S2 union-plan
pointer defect stands at R4: the physical leg file is complete and
executor-verified, but `POSITIONS_PLAN`'s `files` block is still
extension-only and `CORPUS_UNION` reports S2 `witnessed:false`. S2's *void*
is R4's; **this builder reads the PHYSICAL leg file, not the plan, and says
so explicitly** — reading around a known-defective pointer is licensed only
when disclosed (undisclosed, it is the D4 failure again).

DIGESTS ARE NEVER RE-IMPLEMENTED HERE — every `sha256(checksum)` computation
goes through `gate_disjoint.load_digest_map`.

Usage:
    python scripts/tiletie/build_r5_corpus.py \\
        --leg measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/positions_walled_leg1.jsonl \\
        --r4-gate-disjoint measurement/tiearb_widening_20260817/shared_run_r4/GATE_DISJOINT.json \\
        --corpus-out measurement/tiearb_widening_20260817/rung3_r5/CORPUS_R5.json \\
        --dupe-out measurement/tiearb_widening_20260817/rung3_r5/GATE_INTERNAL_DUPE.json

For a synthetic/test corpus, pass `--expect-leg-sha256 ""` and
`--expect-exclusion-list-sha256 ""` to skip the two pinned-hash checks (the
real run never does this).

Exit codes
    0   both artifacts emitted
    2   an input is missing/malformed, or a pinned-hash check failed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

REPO = Path(__file__).resolve().parents[2]

import gate_disjoint as GD                                          # noqa: E402
import rung3_calibrate as RC5                                       # noqa: E402

RUN = REPO / "measurement/tiearb_widening_20260817/rung3_r5"
DEFAULT_LEG_PATH = (REPO / "measurement/tiearb_widening_20260817/shared_run_r4/"
                    "corpus/positions_s2/positions_walled_leg1.jsonl")
DEFAULT_R4_GATE_DISJOINT = (REPO / "measurement/tiearb_widening_20260817/"
                            "shared_run_r4/GATE_DISJOINT.json")
#: R4's REAL, pre-exclusion S2 `ARMS.json` — DESIGN ruling `a13ed934`'s
#: "R4_ARMS": the materialized population authority `ARMS_R5.json` is
#: computed FROM, never re-derived by a later subtraction.
DEFAULT_R4_ARMS = (REPO / "measurement/tiearb_widening_20260817/shared_run_r4/"
                   "corpus/positions_s2/ARMS.json")
DEFAULT_CORPUS_OUT = RUN / "CORPUS_R5.json"
DEFAULT_DUPE_OUT = RUN / "GATE_INTERNAL_DUPE.json"
#: DESIGN ruling `a13ed934`, shape (a): the materialized population
#: authority for the 1,060 survivors.
DEFAULT_ARMS_R5_OUT = RUN / "ARMS_R5.json"

#: DESIGN §R5-FINAL.b2 / FLOORS_R5.json::corpus_provenance -- PINNED, not
#: re-derived. A mismatch means this is not the corpus R5 was designed
#: against, which must stop the build, not silently proceed.
EXPECTED_LEG_SHA256 = ("92ba1ee2dfbfed91f4853173e16e6e008d430ebf708055f"
                       "4c8a76258eacbb7df")
#: DESIGN §R5-FINAL.j -- the canonical referent, pinned.
EXPECTED_R4_EXCLUSION_LIST_SHA256 = ("76f9ac58e2694a5499966a3b519b11ad4e"
                                    "2e7633fd3ab2ab2acb5767535ddda7")

#: The declared seed -> generation-index ranges, REUSED from
#: `rung3_calibrate.py` (same S2 stratum, same committed ranges) rather than
#: re-typed — the ONE definition, per DECISIONS "point, don't copy".
#: Shape matches `FLOORS_R5.json::seed_ranges` exactly (banked_135e9 /
#: extension_137e9 / released_unused).
SEED_RANGES = {label: [lo, hi] for label, lo, hi, _ in RC5.GENERATED_RANGES_S2}
#: `gate_disjoint.py`'s own RELEASED_BAND -- 136e9, released unused. Reused,
#: not re-typed.
RELEASED_136E9_LO, RELEASED_136E9_HI = GD.RELEASED_BAND
SEED_RANGES["released_unused"] = RELEASED_136E9_LO

#: `band_pairs` uses the SHORT band spelling DESIGN's own prose and
#: `gate_disjoint.BAND_RANGES` use ("135e9", "137e9") — not
#: `rung3_calibrate`'s longer `banked_135e9`/`extension_137e9` labels, which
#: are for `seed_ranges` (matching `FLOORS_R5.json`'s own key spelling there).
SHORT_BAND_LABEL = {"banked_135e9": "135e9", "extension_137e9": "137e9"}


class BuildError(RuntimeError):
    """An input is missing/malformed, or a pinned-hash check failed. Fail
    loud, never silently adopt an unexpected corpus."""


# --------------------------------------------------------------------------- #
# R4's own exclusion list -- the canonical serialization DESIGN §R5-FINAL.j    #
# pins, exactly.                                                               #
# --------------------------------------------------------------------------- #
#: `digest_exclusions.S2.rids` off R4's real `GATE_DISJOINT.json`. This is a
#: DIRECT ALIAS of `gate_disjoint.load_r4_exclusion_rids` — the ONE loader
#: (REVIEW_R4 P1): `--r5`'s `s2_vs_exclude_rids` comparison and this
#: builder's `r4_exclusion_list_sha256` conjunct must read the exact SAME
#: list, never two independently-written loaders that could drift apart.
load_r4_exclusion_rids = GD.load_r4_exclusion_rids


def r4_exclusion_list_sha256(rids) -> str:
    """DESIGN §R5-FINAL.j, EXACT: `sha256(json.dumps(sorted(rids)))`,
    default separators, no `sort_keys` (the input is a list), UTF-8, no
    trailing newline. NOT any `EXCLUDE_RIDS_*.txt` file."""
    serialized = json.dumps(sorted(str(r) for r in rids))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# internal-duplicate groups -- digests reused from gate_disjoint, never        #
# recomputed.                                                                  #
# --------------------------------------------------------------------------- #
def band_of_seed(seed, ranges=RC5.GENERATED_RANGES_S2):
    """Non-raising range lookup (unlike `rung3_calibrate.seed_to_generation_
    index`, which RAISES by design): `G-BAND`'s conjuncts need a COUNT of
    out-of-range seeds, not a hard stop on the first one. Returns the band
    label, or `None` if the seed matches no declared range."""
    seed = int(seed)
    for label, lo, hi, _ in ranges:
        if lo <= seed <= hi:
            return label
    return None


def internal_dupe_groups(meta: dict, rid_digest: dict) -> list:
    """`[[rid, rid, ...], ...]` for every digest shared by >= 2 rids, each
    group sorted ascending (the lexicographically SMALLEST rid is the kept
    representative — the SAME rule `emit_digest_exclusions.py` and
    `rung3_calibrate.collisions_at*` use, so this builder's counts are
    comparable to the rest of the campaign's tooling)."""
    groups: dict = {}
    for rid in meta:
        d = rid_digest.get(rid)
        if d is None:
            continue
        groups.setdefault(d, []).append(rid)
    return [sorted(v) for v in groups.values() if len(v) >= 2]


def band_pair_label(group: list, meta: dict, ranges=RC5.GENERATED_RANGES_S2) -> str:
    """`"bandA<->bandB"` (alphabetical, SHORT band spelling — `"135e9"` /
    `"137e9"`, matching DESIGN's own prose and `gate_disjoint.BAND_RANGES`)
    for one dupe group's member bands — `"X<->X"` when every member shares
    one band, which the real R5 corpus's 3 groups all do (`137e9<->137e9`)."""
    bands = sorted({SHORT_BAND_LABEL.get(band_of_seed(meta[rid]["deck_seed"], ranges),
                                         "unknown")
                    for rid in group})
    if len(bands) == 1:
        return f"{bands[0]}<->{bands[0]}"
    return f"{bands[0]}<->{bands[1]}"


def assert_rid_sets_equal(actual: set, expected: set, *, what: str) -> None:
    """RAISES `BuildError` if `actual != expected` — checked in EITHER
    direction (a rid `expected` but missing from `actual`, or a rid in
    `actual` but not `expected`), so a divergence is caught regardless of
    which side is wrong. DESIGN ruling `a13ed934`: `ARMS_R5.json`'s rid set
    must equal `R4_ARMS.rids - excluded_rids`, "asserted at build time in
    BOTH directions" — a standalone function so that requirement is
    independently testable, not inline logic buried in `build()`."""
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise BuildError(
            f"{what}: {len(missing)} missing (e.g. {sorted(missing)[:3]}), "
            f"{len(extra)} extra (e.g. {sorted(extra)[:3]})")


# --------------------------------------------------------------------------- #
# the build                                                                     #
# --------------------------------------------------------------------------- #
def build(*, leg_path, r4_gate_disjoint_path, r4_arms_path=DEFAULT_R4_ARMS,
         arms_r5_out_path=DEFAULT_ARMS_R5_OUT,
         expect_leg_sha256=EXPECTED_LEG_SHA256,
         expect_exclusion_sha256=EXPECTED_R4_EXCLUSION_LIST_SHA256,
         ranges=RC5.GENERATED_RANGES_S2) -> tuple:
    """Returns `(corpus_report, dupe_report, arms_r5)`. Raises `BuildError` /
    `gate_disjoint.GateInputError` on any input, pinned-hash, or
    population-authority consistency problem. `arms_r5_out_path` is recorded
    in `corpus_report` only — this function does no file writing itself
    (the CLI does), so callers get one complete report without a follow-up
    patch."""
    leg_path = Path(leg_path)
    if not leg_path.is_file():
        raise BuildError(f"leg file not found: {leg_path}")

    leg_sha256 = hashlib.sha256(leg_path.read_bytes()).hexdigest()
    if expect_leg_sha256:
        if leg_sha256 != expect_leg_sha256:
            raise BuildError(
                f"leg sha256 mismatch: got {leg_sha256}, expected "
                f"{expect_leg_sha256} -- this is not the corpus R5 was "
                "designed against (DESIGN R5-FINAL.b2's sha-pinned adoption)")

    digest_map, n_lines = GD.load_digest_map([leg_path])
    meta = RC5.load_meta([leg_path])
    rid_digest = {rid: d for d, rids in digest_map.items() for rid in rids}
    n_in = len(meta)

    r4_rids = load_r4_exclusion_rids(r4_gate_disjoint_path)
    excl_sha = r4_exclusion_list_sha256(r4_rids)
    if expect_exclusion_sha256:
        if excl_sha != expect_exclusion_sha256:
            raise BuildError(
                f"r4_exclusion_list_sha256 mismatch: got {excl_sha}, "
                f"expected {expect_exclusion_sha256} -- R4's GATE_DISJOINT.json "
                "does not match the one R5 was designed against")
    residual = sorted(set(r4_rids) & set(meta))

    dupe_groups = internal_dupe_groups(meta, rid_digest)
    dupe_members = sorted({rid for g in dupe_groups for rid in g})
    # each group is sorted ascending; keep the lexicographically SMALLEST
    # rid as the representative, exclude the rest (matches
    # emit_digest_exclusions.py's / rung3_calibrate's own dupe rule)
    later_members = sorted(rid for g in dupe_groups for rid in g[1:])

    excluded_rids = sorted(set(residual) | set(later_members))
    n_excluded_r5 = len(excluded_rids)
    n_positions = n_in - n_excluded_r5

    # ------------------------------------------------------------------- #
    # ARMS_R5.json -- the materialized population authority (a13ed934)     #
    # ------------------------------------------------------------------- #
    r4_arms = GD._load_arms(r4_arms_path)
    r4_arms_rids = set(r4_arms)
    leg_rids = set(meta)
    if leg_rids != r4_arms_rids:
        only_leg = sorted(leg_rids - r4_arms_rids)
        only_arms = sorted(r4_arms_rids - leg_rids)
        raise BuildError(
            "the leg and R4's ARMS.json do NOT enumerate the same rid set "
            "-- this is the D4 invariant (\"the leg files enumerate exactly "
            "the ARMS rids\") the a13ed934 ruling exists to restore: "
            f"{len(only_leg)} rid(s) only in the leg (e.g. {only_leg[:3]}), "
            f"{len(only_arms)} only in ARMS.json (e.g. {only_arms[:3]})")

    excluded_set = set(excluded_rids)
    # built by filtering r4_arms DIRECTLY (not by pre-computing the
    # survivor set and indexing into it) so the equality check below is an
    # INDEPENDENT cross-check of two separately-derived rid sets, not a
    # tautology over one.
    arms_r5 = {rid: v for rid, v in r4_arms.items() if rid not in excluded_set}
    expected_survivors = r4_arms_rids - excluded_set
    # asserted BOTH directions, explicitly -- not merely trusted from the
    # comprehension above, per the ruling's own wording
    assert_rid_sets_equal(set(arms_r5), expected_survivors,
                          what="ARMS_R5's rid set vs R4_ARMS.rids - excluded_rids")
    if len(arms_r5) != n_positions:
        raise BuildError(
            f"ARMS_R5 has {len(arms_r5)} rid(s) but the leg-derived "
            f"n_positions == {n_positions} -- the population authority and "
            "the leg-derived count disagree")

    arms_r5_serialized = json.dumps(arms_r5, indent=2, sort_keys=True)
    arms_r5_sha256 = hashlib.sha256(arms_r5_serialized.encode("utf-8")).hexdigest()

    seeds = [m["deck_seed"] for m in meta.values()]
    distinct_seeds = set(seeds)
    n_distinct_seeds = len(distinct_seeds)
    seed_counts = Counter(seeds)
    max_positions_per_seed = max(seed_counts.values()) if seed_counts else 0
    out_of_band_seeds = {s for s in distinct_seeds if band_of_seed(s, ranges) is None}
    seeds_136e9 = {s for s in distinct_seeds
                  if RELEASED_136E9_LO <= s <= RELEASED_136E9_HI}

    corpus_report = {
        "schema": "carcassonne-rung3-r5-corpus/v1",
        "design_doc": "measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md",
        "gates": ["G-CORPUS", "G-BAND"],
        "provenance": "R4's POST-EXCLUSION S2 leg file, ADOPTED AS-IS (DESIGN "
                      "R5-FINAL.b2) -- NOT a fresh re-mine",
        "disclosure": "This reads the PHYSICAL leg file directly. The S2 "
                      "union-plan pointer defect stands at R4 (POSITIONS_PLAN "
                      "files-block extension-only, CORPUS_UNION S2 "
                      "witnessed:false) -- S2 is VOID at R4, no repair is "
                      "licensed, and this builder does NOT read the plan.",
        "leg_path": str(leg_path),
        "leg_sha256": leg_sha256,
        "r4_exclusion_list_sha256": excl_sha,
        "n_in": n_in,
        "n_excluded_r5": n_excluded_r5,
        "n_positions": n_positions,
        # ⭐ GATED (REVIEW_R4 P1, G-CORPUS): the exact 4 rids, not just their
        # COUNT — `n_excluded_r5 == 4` alone is satisfied by excluding any
        # four rids, so `G-CORPUS` gates this list's IDENTITY too.
        "excluded_rids": excluded_rids,
        "excluded_rids_detail": {
            "r4_residual": residual,
            "internal_dupe_later_members": later_members,
        },
        "n_distinct_seeds": n_distinct_seeds,
        "max_positions_per_seed": max_positions_per_seed,
        "n_out_of_band": len(out_of_band_seeds),
        "n_seeds_136e9": len(seeds_136e9),
        "seed_ranges": SEED_RANGES,
        # ⭐ DESIGN ruling a13ed934: ARMS_R5.json is the MATERIALIZED
        # POPULATION AUTHORITY. Every consumer reads it; none re-derives the
        # population by subtraction.
        "r4_arms_path": str(r4_arms_path),
        "arms_r5_path": str(arms_r5_out_path),
        "arms_r5_sha256": arms_r5_sha256,
        "arms_r5_n_rids": len(arms_r5),
    }

    ply_hist: Counter = Counter()
    band_pairs = []
    for g in dupe_groups:
        for rid in g:
            ply_hist[meta[rid]["ply"]] += 1
        band_pairs.append(band_pair_label(g, meta, ranges))

    d_internal = (len(dupe_groups) / n_in) if n_in else None
    dupe_report = {
        "schema": "carcassonne-rung3-r5-gate-internal-dupe/v1",
        "design_doc": "measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md",
        "gate": "G-INTERNAL-DUPE",
        "note": "IDENTITY-DERIVED (DESIGN R5-FINAL.b): d_internal is a "
                "deterministic function of the sha-pinned leg and cannot "
                "fail unless G-CORPUS's sha check already has. The "
                "CONSISTENCY conjunct (n_dupe_groups/n_dupe_positions/ply/"
                "band) carries the falsifiable content.",
        "leg_sha256": leg_sha256,
        "n_positions": n_in,
        "n_dupe_groups": len(dupe_groups),
        "n_dupe_positions": len(dupe_members),
        "d_internal": d_internal,
        "saturation_guard": 0.05,
        "saturation_void": bool(d_internal is not None and d_internal > 0.05),
        "ply_histogram": dict(sorted(ply_hist.items())),
        "band_pairs": band_pairs,
    }
    return corpus_report, dupe_report, arms_r5


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--leg", default=str(DEFAULT_LEG_PATH),
                    help="the R4 post-exclusion S2 leg1 jsonl (adopted AS-IS)")
    ap.add_argument("--r4-gate-disjoint", default=str(DEFAULT_R4_GATE_DISJOINT),
                    help="R4's GATE_DISJOINT.json (source of the R4 exclusion list)")
    ap.add_argument("--r4-arms", default=str(DEFAULT_R4_ARMS),
                    help="R4's REAL, pre-exclusion S2 ARMS.json (\"R4_ARMS\" -- "
                         "a13ed934's population authority is computed FROM this)")
    ap.add_argument("--expect-leg-sha256", default=EXPECTED_LEG_SHA256,
                    help="pinned leg sha256; pass '' to skip (synthetic/test "
                         "corpora only)")
    ap.add_argument("--expect-exclusion-list-sha256",
                    default=EXPECTED_R4_EXCLUSION_LIST_SHA256,
                    help="pinned r4_exclusion_list_sha256; pass '' to skip "
                         "(synthetic/test corpora only)")
    ap.add_argument("--corpus-out", default=str(DEFAULT_CORPUS_OUT))
    ap.add_argument("--dupe-out", default=str(DEFAULT_DUPE_OUT))
    ap.add_argument("--arms-r5-out", default=str(DEFAULT_ARMS_R5_OUT),
                    help="a13ed934 shape (a): the materialized population "
                         "authority for the survivors")
    a = ap.parse_args(argv)

    try:
        corpus_report, dupe_report, arms_r5 = build(
            leg_path=a.leg, r4_gate_disjoint_path=a.r4_gate_disjoint,
            r4_arms_path=a.r4_arms, arms_r5_out_path=a.arms_r5_out,
            expect_leg_sha256=a.expect_leg_sha256,
            expect_exclusion_sha256=a.expect_exclusion_list_sha256)
    except (BuildError, GD.GateInputError) as exc:
        print(f"\n{'=' * 70}\n[build-r5-corpus] COULD NOT BUILD: {exc}\n"
              f"{'=' * 70}", file=sys.stderr)
        return 2

    for path, report, label in ((a.corpus_out, corpus_report, "CORPUS_R5"),
                                (a.dupe_out, dupe_report, "GATE_INTERNAL_DUPE")):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"[build-r5-corpus] {label} -> {path}")

    Path(a.arms_r5_out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.arms_r5_out).write_text(json.dumps(arms_r5, indent=2, sort_keys=True))
    print(f"[build-r5-corpus] ARMS_R5 -> {a.arms_r5_out} "
          f"({len(arms_r5)} rids, sha256={corpus_report['arms_r5_sha256']})")

    print(f"[build-r5-corpus] n_in={corpus_report['n_in']} "
          f"n_excluded_r5={corpus_report['n_excluded_r5']} "
          f"n_positions={corpus_report['n_positions']}")
    print(f"[build-r5-corpus] n_dupe_groups={dupe_report['n_dupe_groups']} "
          f"n_dupe_positions={dupe_report['n_dupe_positions']} "
          f"d_internal={dupe_report['d_internal']}")
    if dupe_report["saturation_void"]:
        print(f"\n{'=' * 70}\n[build-r5-corpus] ***** G-INTERNAL-DUPE SATURATION "
              f"GUARD TRIPPED *****\n{'=' * 70}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
