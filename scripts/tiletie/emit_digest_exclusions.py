#!/usr/bin/env python3
"""Emit the layer-(c) rid exclusion list for the tiearb2 corpus — mining only.

WHY THIS EXISTS
    `gate_disjoint.py` proves the fresh tie-arbitration corpus disjoint from the
    SPENT 2026-08-12 corpus on three identities. Layers (a) `root_id` and
    (b) `rid` are guaranteed by the fresh deck-seed band. Layer (c) is
    `sha256(checksum)` — the BOARD — and it is NOT guaranteed by the band,
    because Carcassonne boards TRANSPOSE: two different games (or two plies of
    two different games) can reach a bit-identical board, most commonly in the
    opening, where only a handful of tiles are down.

    So a layer-(c)-only failure is NOT evidence that the band is dirty. Layers
    (a) and (b) at intersection 0 positively exclude that. Regenerating from
    another "clean" band would reproduce the same phenomenon — every fresh band
    shares SOME early board with any other band — at the cost of a full
    generation run. The correct response is to EXCLUDE the handful of offending
    positions and rebuild the plan with the existing, tested instrument.

WHAT IT COMPUTES
    Two rules, unioned:

      (a) SPENT OVERLAP  — every fresh rid whose board digest appears anywhere
                           in the spent corpus's digest set. These are boards the
                           spent corpus already scored; re-scoring one would
                           re-import exactly the winner's curse the successor
                           corpus exists to escape.
      (b) INTERNAL DUPES — within the fresh corpus, a digest carried by more than
                           one rid keeps the LEXICOGRAPHICALLY SMALLEST rid and
                           drops the rest. This matches how the spent corpus was
                           built: 733 rids / 733 distinct checksums, i.e. one rid
                           per board, no internal duplicates.

    After both rules, the fresh corpus's digests are internally distinct AND
    disjoint from the spent set, so layer (c) is 0 by construction.

⚠️ POINT IT AT A SPENT-RID-ONLY BUILD, NEVER AT THE FINAL CORPUS.
    This tool reads the fresh corpus's realized `positions_*_leg1.jsonl` board
    census. If it is pointed at a corpus that was ALREADY built with these
    exclusions applied, it will (correctly) find nothing and emit an EMPTY list —
    which, fed back into a rebuild, would restore the excluded positions and fail
    the gate again. `build_tiearb2_corpus.sh` therefore always derives the list
    from a throwaway PROBE build made with the spent-rid list alone, and keys the
    whole step on `EXCLUDE_RIDS_all.txt` already existing.

DISCLOSURE
    The JSON report is COUNTS ONLY — no rid, checksum or digest value — matching
    `gate_disjoint.py`'s policy, so the fresh corpus's audit trail cannot itself
    leak spent-corpus identities. The `.txt` necessarily carries rids: it is an
    INPUT to `build_positions.py --exclude-rids`, not a report.

This module computes NO strength / headroom / arbitration statistic.

Exit codes
    0   list emitted (possibly empty — an empty list is a legitimate result)
    2   an input is missing / unreadable

Usage:
    python scripts/tiletie/emit_digest_exclusions.py \
      --new-dir   <probe positions dir> \
      --spent-dir measurement/tiletie_pricing_20260812/positions_pooled \
      --out       measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_digest.txt \
      --report    measurement/tiearb2_20260816/DIGEST_EXCLUSIONS.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The digest identity MUST be byte-for-byte the gate's, or an exclusion list
# could "fix" a layer the gate still reads as violated. Import it, don't restate.
from gate_disjoint import (  # noqa: E402
    GateInputError,
    leg_paths,
    sha256_of_ids,
)

REPO = Path(__file__).resolve().parents[2]

DEFAULT_SPENT_DIR = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
DEFAULT_NEW_DIR = REPO / "measurement/tiearb2_20260816/corpus/positions"
DEFAULT_OUT = REPO / "measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_digest.txt"
DEFAULT_REPORT = REPO / "measurement/tiearb2_20260816/DIGEST_EXCLUSIONS.json"

#: leg1 carries every position exactly once, so it is the complete board census
#: of a corpus (higher legs would duplicate checksums). Same glob the gate uses.
LEG_GLOB = "positions_*_leg1.jsonl"


def digest_of(checksum) -> str:
    """`sha256(str(checksum))` — identical to `gate_disjoint.load_digests`."""
    return hashlib.sha256(str(checksum).encode()).hexdigest()


def load_rid_digests(paths) -> list[tuple[str, str]]:
    """[(rid, digest)] over every leg line, in file order.

    Unlike the gate (which only needs the digest SET) the exclusion list has to
    name the rids, so both fields are required on every line."""
    out: list[tuple[str, str]] = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            raise GateInputError(f"leg file not found: {p}")
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateInputError(f"{p}:{i}: not JSON ({exc})") from exc
            for field in ("rid", "checksum"):
                if field not in rec:
                    raise GateInputError(
                        f"{p}:{i}: no {field!r} field — cannot build the "
                        f"layer-(c) exclusion list")
            out.append((str(rec["rid"]), digest_of(rec["checksum"])))
    return out


def compute_exclusions(new_pairs, spent_digests) -> dict:
    """The two rules. Returns a dict carrying the rid sets AND the counts.

    `spent_overlap` and `internal_dupes` can intersect (a duplicated fresh board
    that the spent corpus also holds), which is why `excluded` is their UNION and
    `n_both_rules` is reported separately — the three counts are then unambiguous
    however the input falls."""
    spent_digests = set(spent_digests)

    spent_overlap = {rid for rid, dig in new_pairs if dig in spent_digests}

    by_digest: dict[str, list[str]] = {}
    for rid, dig in new_pairs:
        by_digest.setdefault(dig, []).append(rid)
    internal_dupes: set[str] = set()
    n_dupe_groups = 0
    for rids in by_digest.values():
        uniq = sorted(set(rids))
        if len(uniq) > 1:                       # same board, different positions
            n_dupe_groups += 1
            internal_dupes.update(uniq[1:])     # keep the smallest rid
        elif len(rids) > 1:                     # same rid twice (not expected)
            n_dupe_groups += 1

    excluded = spent_overlap | internal_dupes
    return {
        "spent_overlap": spent_overlap,
        "internal_dupes": internal_dupes,
        "excluded": excluded,
        "n_spent_overlap": len(spent_overlap),
        "n_internal_dupes": len(internal_dupes),
        "n_internal_dupe_digest_groups": n_dupe_groups,
        "n_both_rules": len(spent_overlap & internal_dupes),
        "n_total_excluded": len(excluded),
        "n_new_leg_lines": len(new_pairs),
        "n_new_distinct_rids": len({rid for rid, _ in new_pairs}),
        "n_new_distinct_digests": len(by_digest),
        "n_spent_distinct_digests": len(spent_digests),
        "n_new_distinct_digests_after": len(
            {dig for rid, dig in new_pairs if rid not in excluded}),
        "n_new_lines_after": sum(1 for rid, _ in new_pairs if rid not in excluded),
    }


def write_exclude_file(rids, out_path, *, new_dir, spent_dir) -> list[str]:
    """The newline-delimited rid list `build_positions.py --exclude-rids` parses
    (it strips `#` comments and blank lines, so the header is safe)."""
    rids = sorted(rids)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# tiearb2 layer-(c) BOARD-DIGEST exclusion list — {len(rids)} rid(s)\n"
        f"# emitted by: scripts/tiletie/emit_digest_exclusions.py\n"
        f"# fresh board census: {new_dir}/{LEG_GLOB}\n"
        f"# spent board census: {spent_dir}/{LEG_GLOB}\n"
        f"# rule (a): the fresh board digest appears in the SPENT corpus\n"
        f"# rule (b): the digest is duplicated WITHIN the fresh corpus — the\n"
        f"#           lexicographically smallest rid is KEPT, the rest dropped\n"
        f"# Board transposition is intrinsic to Carcassonne; a layer-(c)-only\n"
        f"# gate failure is NOT a dirty band (layers a/b are 0) and is fixed by\n"
        f"# exclusion, not regeneration. See CORPUS_PIPELINE.md phase 5b.\n")
    out_path.write_text(header + "".join(r + "\n" for r in rids))
    return rids


def build_report(res, *, new_dir, spent_dir, new_legs, spent_legs,
                 out_path) -> dict:
    """COUNTS ONLY — no rid, checksum or digest value, matching the gate."""
    return {
        "tool": "emit_digest_exclusions",
        "purpose": "layer-(c) board-digest exclusions for the tiearb2 corpus "
                   "(board transposition, not band contamination)",
        "disclosure_policy": "COUNTS ONLY — no rid, checksum or digest value "
                             "appears in this report by construction",
        "generated_utc": _dt.datetime.now(_dt.timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {
            "new_dir": str(new_dir), "spent_dir": str(spent_dir),
            "new_legs": [str(p) for p in new_legs],
            "spent_legs": [str(p) for p in spent_legs],
        },
        "rules": {
            "a_spent_overlap": "drop every fresh rid whose sha256(checksum) "
                               "appears in the spent corpus",
            "b_internal_dupes": "within the fresh corpus keep the "
                                "lexicographically smallest rid per digest, "
                                "drop the rest (the spent corpus has 733 rids / "
                                "733 distinct checksums — one rid per board)",
        },
        "n_spent_overlap": res["n_spent_overlap"],
        "n_internal_dupes": res["n_internal_dupes"],
        "n_internal_dupe_digest_groups": res["n_internal_dupe_digest_groups"],
        "n_excluded_by_both_rules": res["n_both_rules"],
        "n_total_excluded": res["n_total_excluded"],
        "n_new_leg_lines": res["n_new_leg_lines"],
        "n_new_distinct_rids": res["n_new_distinct_rids"],
        "n_new_distinct_digests": res["n_new_distinct_digests"],
        "n_spent_distinct_digests": res["n_spent_distinct_digests"],
        "n_new_leg_lines_after_exclusion": res["n_new_lines_after"],
        "n_new_distinct_digests_after_exclusion": res["n_new_distinct_digests_after"],
        "sha256_excluded_rid_list": sha256_of_ids(res["excluded"]),
        "exclude_rids_path": str(out_path),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--new-dir", default=str(DEFAULT_NEW_DIR),
                    help="the FRESH corpus's positions dir (point at a "
                         "spent-rid-only PROBE build, never at a corpus already "
                         "built with these exclusions)")
    ap.add_argument("--spent-dir", default=str(DEFAULT_SPENT_DIR))
    ap.add_argument("--new-leg-glob", default=LEG_GLOB)
    ap.add_argument("--spent-leg-glob", default=LEG_GLOB)
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="the rid list build_positions.py --exclude-rids reads")
    ap.add_argument("--report", default=str(DEFAULT_REPORT),
                    help="counts-only JSON report ('' to skip)")
    a = ap.parse_args(argv)

    new_dir, spent_dir = Path(a.new_dir), Path(a.spent_dir)
    try:
        new_legs = leg_paths(new_dir, a.new_leg_glob)
        spent_legs = leg_paths(spent_dir, a.spent_leg_glob)
        new_pairs = load_rid_digests(new_legs)
        spent_pairs = load_rid_digests(spent_legs)
    except GateInputError as exc:
        print(f"\n{'=' * 70}\n[digest-exclusions] COULD NOT EVALUATE: {exc}\n"
              f"{'=' * 70}", file=sys.stderr)
        return 2

    res = compute_exclusions(new_pairs, {dig for _, dig in spent_pairs})
    write_exclude_file(res["excluded"], a.out, new_dir=new_dir,
                       spent_dir=spent_dir)
    report = build_report(res, new_dir=new_dir, spent_dir=spent_dir,
                          new_legs=new_legs, spent_legs=spent_legs,
                          out_path=a.out)
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(report, indent=2, sort_keys=True))

    print(f"[digest-exclusions] fresh board census: {res['n_new_leg_lines']} "
          f"leg1 line(s), {res['n_new_distinct_digests']} distinct digest(s)")
    print(f"[digest-exclusions] rule (a) spent-overlap  : "
          f"{res['n_spent_overlap']} rid(s)")
    print(f"[digest-exclusions] rule (b) internal dupes : "
          f"{res['n_internal_dupes']} rid(s) over "
          f"{res['n_internal_dupe_digest_groups']} digest group(s)")
    print(f"[digest-exclusions] in BOTH rules           : "
          f"{res['n_both_rules']} rid(s)")
    print(f"[digest-exclusions] TOTAL excluded (union)  : "
          f"{res['n_total_excluded']} rid(s) -> {a.out}")
    print(f"[digest-exclusions] fresh corpus after      : "
          f"{res['n_new_lines_after']} line(s) / "
          f"{res['n_new_distinct_digests_after']} distinct digest(s)")
    print(f"[digest-exclusions] sha256(excluded rid list) = "
          f"{report['sha256_excluded_rid_list']}")
    if a.report:
        print(f"[digest-exclusions] -> {a.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
