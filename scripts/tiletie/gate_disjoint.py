#!/usr/bin/env python3
"""G-DISJOINT — hard gate: the FRESH tie-arbitration corpus must not touch the
SPENT one on ANY identity.

The tiearb2_20260816 corpus exists because the 2026-08-12 tile-tie corpus
(733 positions / 399 roots) is SPENT: it selected the read rule, so re-using any
of its positions in the confirmatory corpus would re-import the winner's curse
the successor run is built to escape. "Fresh deck-seed band" is the mechanism;
this gate is the PROOF, and it is deliberately over-determined — three
independent identities, any overlap fails the run:

  a. `root_id`   — the GAME. Two plies of the same game are not independent
                   draws, so a shared root contaminates even at distinct plies.
                   Read from `ARMS.json` values' `root_id` on both sides.
  b. `rid`       — the (game, ply) POSITION identity `build_positions.rid_for`
                   assigns. Read from `ARMS.json` KEYS on both sides.
  c. `sha256(checksum)` — the BOARD. `checksum` is
                   `game.string_representation(board)` at the tied root, carried
                   verbatim on every leg jsonl line. This is the strongest layer:
                   it catches the same board reached from a DIFFERENT game or a
                   different ply, which neither (a) nor (b) can see.

The gate REPORTS COUNTS ONLY — never a rid, a root_id, a checksum or a digest.
A gate that printed the overlapping values would leak spent-corpus identities
into the fresh corpus's own audit trail; the count is the whole finding, and the
two rid-list sha256s let a later reader prove which two sets were compared
without either set being reproducible from the report.

Exit codes
    0   all three intersections empty
    1   ANY intersection non-empty (loud banner on stderr)
    2   an input is missing / unreadable (the gate could not be evaluated)

Usage (defaults are the tiearb2 vs 2026-08-12 pairing):
    python scripts/tiletie/gate_disjoint.py
    python scripts/tiletie/gate_disjoint.py --new-dir <dir> --spent-dir <dir> --out <json>

──────────────────────────────────────────────────────────────────────────────
W5 — the MERGED mode (`--merged`), for the tie-arbiter widening run (rev R2)
──────────────────────────────────────────────────────────────────────────────
The pairwise mode above compares exactly TWO `ARMS.json` corpora and writes
`layers` / `passed` at the top level. The widening run's `G-DISJOINT`
(`READ_RULE.md` §2) needs **one** report covering **FIVE** committed
comparisons, at these exact names:

    s1_vs_tiletie0812     s1_vs_tiearb2_0816     (three layers each)
    s2_vs_tiletie0812     s2_vs_tiearb2_0816     (three layers each)
    s1s2_vs_exclude_rids  — the RID LAYER ONLY, against
                            `measurement/tiearb2_20260816/corpus/
                             EXCLUDE_RIDS_all.txt`, a rid TEXT file with no
                            root and no board layer, which the stock
                            `load_rids` RAISES on

— plus the STRATA cross-check `strata_root_overlap` (`S1 ∩ S2` on `root_id`).
`--merged` therefore emits

    {passed, strata_root_overlap,
     comparisons: {<name>: {passed, layers: {<layer>: {n_intersection, …}}}}}

`passed` is the AND over every comparison's every layer **and**
`strata_root_overlap == 0`. `G-DISJOINT` has **no fallback** (READ_RULE §1.3):
a missing gate file is simply a FAIL.

The pairwise mode's behaviour, output shape, CLI defaults and exit codes are
unchanged — `--merged` is purely additive, so the banked `DISJOINTNESS.json` of
the tiearb2 run stays reproducible byte-for-byte.

Merged usage (the five committed comparisons are the defaults):
    python scripts/tiletie/gate_disjoint.py --merged \
        --s1-dir RUN/corpus/positions_s1 --s2-dir RUN/corpus/positions_s2 \
        --out RUN/GATE_DISJOINT.json

W5 also owns `gate_draw.py` (`GATE_DRAW.json`) — DESIGN §8 builder delta 2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEFAULT_SPENT_DIR = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
DEFAULT_NEW_DIR = REPO / "measurement/tiearb2_20260816/corpus/positions"
DEFAULT_OUT = REPO / "measurement/tiearb2_20260816/DISJOINTNESS.json"

# --- W5 merged mode: the committed comparison set (READ_RULE §2) ------------- #
#: The two BANKED ARMS.json references, at the committed comparison-name stems.
DEFAULT_REFS = {
    "tiletie0812": REPO / "measurement/tiletie_pricing_20260812/positions_pooled",
    "tiearb2_0816": REPO / "measurement/tiearb2_20260816/corpus/positions",
}
#: The fifth comparison's reference: a rid TEXT file. No root layer, no board
#: layer — `s1s2_vs_exclude_rids` is deliberately RID-LAYER ONLY.
DEFAULT_EXCLUDE_RIDS = (REPO / "measurement/tiearb2_20260816/corpus/"
                        "EXCLUDE_RIDS_all.txt")
EXCLUDE_COMPARISON = "s1s2_vs_exclude_rids"
DEFAULT_MERGED_OUT = (REPO / "measurement/tiearb_widening_20260817/shared_run/"
                      "GATE_DISJOINT.json")

#: leg1 carries EVERY position exactly once (leg r exists only for positions
#: with >= r+1 arms, and every scoreable position has at least 2), so leg1 is the
#: complete board census of a corpus. Higher legs would duplicate checksums.
SPENT_LEG_GLOB = "positions_*_leg1.jsonl"
NEW_LEG_GLOB = "positions_*_leg1.jsonl"


class GateInputError(RuntimeError):
    """An input the gate needs is missing or malformed (exit 2, not a failure of
    disjointness — the gate simply could not be evaluated)."""


# --------------------------------------------------------------------------- #
# loaders                                                                       #
# --------------------------------------------------------------------------- #
def _load_arms(path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise GateInputError(f"ARMS.json not found: {path}")
    try:
        arms = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise GateInputError(f"{path}: not JSON ({exc})") from exc
    if not isinstance(arms, dict):
        raise GateInputError(f"{path}: expected a rid-keyed object, got "
                             f"{type(arms).__name__}")
    return arms


def load_rids(arms_path) -> set[str]:
    """The corpus's rid set — the KEYS of ARMS.json."""
    return set(_load_arms(arms_path))


def load_root_ids(arms_path) -> set[str]:
    """The corpus's root (game) set — `root_id` off every ARMS.json value."""
    arms = _load_arms(arms_path)
    missing = [k for k, v in arms.items() if "root_id" not in v]
    if missing:
        raise GateInputError(f"{arms_path}: {len(missing)} entr(ies) carry no "
                             f"'root_id' — cannot evaluate layer (a)")
    return {str(v["root_id"]) for v in arms.values()}


def leg_paths(directory, glob_pat) -> list[Path]:
    paths = sorted(Path(directory).glob(glob_pat))
    if not paths:
        raise GateInputError(f"no leg files matching {glob_pat!r} under "
                             f"{directory}")
    return paths


def load_digests(paths) -> tuple[set[str], int]:
    """`sha256(checksum)` over every leg line. Returns (digest set, n_lines).

    A collision between the set size and the line count is NOT an error here
    (the caller reports both); within one corpus leg1 they should be equal."""
    digests: set[str] = set()
    n_lines = 0
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
            if "checksum" not in rec:
                raise GateInputError(f"{p}:{i}: no 'checksum' field — cannot "
                                     f"evaluate layer (c)")
            n_lines += 1
            digests.add(hashlib.sha256(str(rec["checksum"]).encode()).hexdigest())
    return digests, n_lines


def sha256_of_ids(ids) -> str:
    """A stable fingerprint of an id SET: sha256 over the sorted ids, one per
    line, trailing newline included. Lets a later reader prove WHICH two sets
    were compared without this report making either set reproducible."""
    return hashlib.sha256(
        "".join(str(i) + "\n" for i in sorted(ids)).encode()).hexdigest()


# --------------------------------------------------------------------------- #
# the gate                                                                      #
# --------------------------------------------------------------------------- #
def run_gate(*, spent_arms, new_arms, spent_legs, new_legs) -> dict:
    """Evaluate the three layers. Returns the report dict (counts only).
    Raises `GateInputError` if an input is missing."""
    spent_rids, new_rids = load_rids(spent_arms), load_rids(new_arms)
    spent_roots, new_roots = load_root_ids(spent_arms), load_root_ids(new_arms)
    spent_dig, spent_lines = load_digests(spent_legs)
    new_dig, new_lines = load_digests(new_legs)

    layers = {
        "a_root_id": {
            "identity": "root_id (the GAME) from ARMS.json values",
            "n_spent": len(spent_roots), "n_new": len(new_roots),
            "n_intersection": len(spent_roots & new_roots),
        },
        "b_rid": {
            "identity": "rid (the (game, ply) POSITION) from ARMS.json keys",
            "n_spent": len(spent_rids), "n_new": len(new_rids),
            "n_intersection": len(spent_rids & new_rids),
        },
        "c_position_digest": {
            "identity": "sha256(checksum) where checksum = "
                        "game.string_representation(board) at the tied root",
            "n_spent": len(spent_dig), "n_new": len(new_dig),
            "n_intersection": len(spent_dig & new_dig),
            "n_spent_leg_lines": spent_lines, "n_new_leg_lines": new_lines,
        },
    }
    n_bad = sum(1 for L in layers.values() if L["n_intersection"])
    report = {
        "gate": "G-DISJOINT",
        "goal": "the fresh tie-arbitration corpus shares NO game, NO position "
                "and NO board with the spent 2026-08-12 corpus",
        "disclosure_policy": "COUNTS ONLY — no rid, root_id, checksum or digest "
                             "value appears in this report by construction",
        "inputs": {
            "spent_arms": str(spent_arms), "new_arms": str(new_arms),
            "spent_legs": [str(p) for p in spent_legs],
            "new_legs": [str(p) for p in new_legs],
        },
        "layers": layers,
        "sha256_spent_rid_list": sha256_of_ids(spent_rids),
        "sha256_new_rid_list": sha256_of_ids(new_rids),
        "n_layers_violated": n_bad,
        "passed": n_bad == 0,
    }
    return report


# --------------------------------------------------------------------------- #
# W5 — the merged, four-comparison gate                                         #
# --------------------------------------------------------------------------- #
def load_rid_txt(path) -> set[str]:
    """Rids from a newline-delimited txt (the `build_positions.py --exclude-rids`
    format: `#` comments and blank lines stripped).

    `load_rids` reads `ARMS.json` and RAISES on a txt (REVIEW_R1 defect 1); this
    is the reader that makes `EXCLUDE_RIDS_all.txt` a first-class layer-(b)
    identity instead of an unreadable input."""
    path = Path(path)
    if not path.is_file():
        raise GateInputError(f"rid list not found: {path}")
    out = set()
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def _corpus_identities(arms_path, legs) -> dict:
    """The three identity SETS of one corpus, loaded once and reused across the
    comparisons that name it (so a reference is never parsed twice)."""
    return {
        "roots": load_root_ids(arms_path),
        "rids": load_rids(arms_path),
        "digests": load_digests(legs),
    }


def compare_identities(new_ids: dict, ref_ids: dict, *, inputs=None) -> dict:
    """ONE full comparison of a new corpus against one ARMS.json reference —
    all three layers. Counts only; the pairwise gate's disclosure policy is
    inherited verbatim."""
    new_dig, new_lines = new_ids["digests"]
    ref_dig, ref_lines = ref_ids["digests"]
    layers = {
        "a_root_id": {
            "identity": "root_id (the GAME) from ARMS.json values",
            "n_new": len(new_ids["roots"]), "n_ref": len(ref_ids["roots"]),
            "n_intersection": len(new_ids["roots"] & ref_ids["roots"]),
        },
        "b_rid": {
            "identity": "rid (the (game, ply) POSITION) from ARMS.json keys",
            "n_new": len(new_ids["rids"]), "n_ref": len(ref_ids["rids"]),
            "n_intersection": len(new_ids["rids"] & ref_ids["rids"]),
        },
        "c_position_digest": {
            "identity": "sha256(checksum) where checksum = "
                        "game.string_representation(board) at the tied root",
            "n_new": len(new_dig), "n_ref": len(ref_dig),
            "n_intersection": len(new_dig & ref_dig),
            "n_new_leg_lines": new_lines, "n_ref_leg_lines": ref_lines,
        },
    }
    n_bad = sum(1 for L in layers.values() if L["n_intersection"])
    return {"inputs": inputs or {}, "layers": layers,
            "n_layers_violated": n_bad, "passed": n_bad == 0}


def compare_rid_list(new_rids: set, ref_rids: set, *, inputs=None) -> dict:
    """The FIFTH comparison — `s1s2_vs_exclude_rids`, RID LAYER ONLY.

    `EXCLUDE_RIDS_all.txt` is a rid text file: it carries no `root_id` and no
    board checksum, so layers (a) and (c) do not exist for it and are
    deliberately ABSENT rather than faked as zero (a fabricated `0` would read
    as a proof that was never performed)."""
    layers = {
        "b_rid": {
            "identity": "rid, S1 ∪ S2 against a rid TEXT list",
            "n_new": len(new_rids), "n_ref": len(ref_rids),
            "n_intersection": len(new_rids & ref_rids),
        },
    }
    n_bad = sum(1 for L in layers.values() if L["n_intersection"])
    return {"inputs": inputs or {},
            "layers": layers,
            "layers_absent": ["a_root_id", "c_position_digest"],
            "layers_absent_reason": "a rid TEXT list has no root and no board "
                                    "identity; the missing layers are ABSENT, "
                                    "never fabricated as zero",
            "n_layers_violated": n_bad, "passed": n_bad == 0}


def run_merged_gate(*, strata: dict, refs: dict, exclude_rids=None) -> dict:
    """The W5 report: FIVE comparisons + `strata_root_overlap`, one file.

    `strata`       = `{"S1": {"arms": path, "legs": [paths]}, "S2": {...}}`
    `refs`         = `{"<stem>": {"arms": path, "legs": [paths]}, ...}`
    `exclude_rids` = path(s) to the rid TXT of the fifth comparison

    Comparison keys are `"<stratum lowered>_vs_<stem>"` — `s1_vs_tiletie0812`,
    `s1_vs_tiearb2_0816`, `s2_vs_tiletie0812`, `s2_vs_tiearb2_0816` — plus
    `s1s2_vs_exclude_rids`. These spellings are load-bearing: `READ_RULE` §2
    reads `comparisons.<name>.layers.<layer>.n_intersection` for every one.
    """
    if not strata:
        raise GateInputError("merged gate needs at least one stratum")
    if not refs:
        raise GateInputError("merged gate needs at least one reference corpus")

    strat_ids = {s: _corpus_identities(v["arms"], v["legs"])
                 for s, v in sorted(strata.items())}
    ref_ids = {name: _corpus_identities(v["arms"], v["legs"])
               for name, v in sorted(refs.items())}

    comparisons = {}
    for s, sv in sorted(strata.items()):
        for name, rv in sorted(refs.items()):
            comparisons[f"{s.lower()}_vs_{name}"] = compare_identities(
                strat_ids[s], ref_ids[name],
                inputs={"new_arms": str(sv["arms"]),
                        "new_legs": [str(p) for p in sv["legs"]],
                        "ref_arms": str(rv["arms"]),
                        "ref_legs": [str(p) for p in rv["legs"]]})

    txts = [Path(p) for p in (exclude_rids or ())]
    if txts:
        excl: set[str] = set()
        for t in txts:
            excl |= load_rid_txt(t)
        union = set().union(*(v["rids"] for v in strat_ids.values()))
        comparisons[EXCLUDE_COMPARISON] = compare_rid_list(
            union, excl,
            inputs={"new_strata": sorted(strat_ids),
                    "ref_rid_txts": [str(p) for p in txts]})

    # The strata cross-check: S1 and S2 are root-disjoint BY BAND SPLIT, so this
    # is the proof of the DESIGN §3 split, not a restatement of it. With a single
    # stratum there is nothing to intersect and the count is 0 by definition.
    names = sorted(strat_ids)
    overlap = 0
    if len(names) >= 2:
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                overlap += len(strat_ids[names[i]]["roots"]
                               & strat_ids[names[j]]["roots"])

    n_bad = sum(1 for c in comparisons.values() if not c["passed"])
    return {
        "gate": "G-DISJOINT",
        "mode": "merged",
        "goal": "every widening stratum shares NO game, NO position and NO "
                "board with any banked corpus, and the two strata share no game",
        "disclosure_policy": "COUNTS ONLY — no rid, root_id, checksum or digest "
                             "value appears in this report by construction",
        "strata": {s: {"arms": str(v["arms"]),
                       "legs": [str(p) for p in v["legs"]],
                       "n_roots": len(strat_ids[s]["roots"]),
                       "n_rids": len(strat_ids[s]["rids"]),
                       "n_position_digests": len(strat_ids[s]["digests"][0])}
                   for s, v in sorted(strata.items())},
        "sha256_rid_list_by_stratum": {s: sha256_of_ids(strat_ids[s]["rids"])
                                       for s in names},
        "comparisons": comparisons,
        "strata_root_overlap": overlap,
        "n_comparisons_violated": n_bad,
        "passed": n_bad == 0 and overlap == 0,
    }


def _kv(spec: str, what: str) -> tuple:
    """`name=value` for the repeatable merged-mode reference flags."""
    if "=" not in spec:
        raise GateInputError(f"--{what} expects NAME=PATH, got {spec!r}")
    name, _, val = spec.partition("=")
    name, val = name.strip(), val.strip()
    if not name or not val:
        raise GateInputError(f"--{what} expects NAME=PATH, got {spec!r}")
    return name, val


def _merged_from_args(a) -> dict:
    """Resolve the merged-mode CLI into `run_merged_gate` inputs."""
    strata = {}
    for tag, d, arms, glob_pat in (("S1", a.s1_dir, a.s1_arms, a.s1_leg_glob),
                                   ("S2", a.s2_dir, a.s2_arms, a.s2_leg_glob)):
        if not d:
            continue
        d = Path(d)
        strata[tag] = {"arms": Path(arms) if arms else d / "ARMS.json",
                       "legs": leg_paths(d, glob_pat)}
    if not strata:
        raise GateInputError("--merged needs --s1-dir and/or --s2-dir")

    if a.ref:
        dirs = dict(_kv(spec, "ref") for spec in a.ref)
    else:
        dirs = {n: str(p) for n, p in DEFAULT_REFS.items()}

    out = {}
    for name, d in dirs.items():
        d = Path(d)
        out[name] = {"arms": d / "ARMS.json", "legs": leg_paths(d, a.ref_leg_glob)}

    excl = ([Path(p) for p in a.exclude_rids] if a.exclude_rids
            else [DEFAULT_EXCLUDE_RIDS])
    return {"strata": strata, "refs": out, "exclude_rids": excl}


def _print_merged(report: dict, out_path) -> None:
    for cname, c in sorted(report["comparisons"].items()):
        for lname, L in sorted(c["layers"].items()):
            print(f"[G-DISJOINT] {cname:34s} {lname:18s} "
                  f"new={L['n_new']:6d} ref={L['n_ref']:6d} "
                  f"intersection={L['n_intersection']:6d}")
    print(f"[G-DISJOINT] strata_root_overlap = {report['strata_root_overlap']}")
    if out_path:
        print(f"[G-DISJOINT] -> {out_path}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spent-dir", default=str(DEFAULT_SPENT_DIR))
    ap.add_argument("--new-dir", default=str(DEFAULT_NEW_DIR))
    ap.add_argument("--spent-arms", default=None,
                    help="default: <spent-dir>/ARMS.json")
    ap.add_argument("--new-arms", default=None,
                    help="default: <new-dir>/ARMS.json")
    ap.add_argument("--spent-leg-glob", default=SPENT_LEG_GLOB)
    ap.add_argument("--new-leg-glob", default=NEW_LEG_GLOB)
    ap.add_argument("--out", default=None,
                    help=f"default: {DEFAULT_OUT} (pairwise) / "
                         f"{DEFAULT_MERGED_OUT} (--merged)")

    m = ap.add_argument_group(
        "W5 merged mode — ONE report, four comparisons + strata_root_overlap")
    m.add_argument("--merged", action="store_true",
                   help="emit the merged report READ_RULE §2's G-DISJOINT reads")
    m.add_argument("--s1-dir", default=None, help="S1 positions dir")
    m.add_argument("--s2-dir", default=None, help="S2 positions dir")
    m.add_argument("--s1-arms", default=None, help="default: <s1-dir>/ARMS.json")
    m.add_argument("--s2-arms", default=None, help="default: <s2-dir>/ARMS.json")
    m.add_argument("--s1-leg-glob", default=NEW_LEG_GLOB)
    m.add_argument("--s2-leg-glob", default=NEW_LEG_GLOB)
    m.add_argument("--ref-leg-glob", default=SPENT_LEG_GLOB)
    m.add_argument("--ref", action="append", default=None, metavar="NAME=DIR",
                   help="banked reference corpus (repeatable). Omit for the two "
                        "committed defaults: "
                        + ", ".join(sorted(DEFAULT_REFS)))
    m.add_argument("--exclude-rids", action="append", default=None,
                   metavar="FILE",
                   help=f"rid TXT for the {EXCLUDE_COMPARISON} comparison "
                        f"(rid layer only). Default: {DEFAULT_EXCLUDE_RIDS}")
    a = ap.parse_args(argv)

    if a.merged:
        out = a.out or str(DEFAULT_MERGED_OUT)
        try:
            report = run_merged_gate(**_merged_from_args(a))
        except GateInputError as exc:
            print(f"\n{'=' * 70}\n[G-DISJOINT] COULD NOT EVALUATE: {exc}\n"
                  f"{'=' * 70}", file=sys.stderr)
            return 2
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(json.dumps(report, indent=2, sort_keys=True))
        _print_merged(report, out)
        if not report["passed"]:
            bad = sorted(k for k, c in report["comparisons"].items()
                         if not c["passed"])
            print(f"\n{'=' * 70}\n"
                  f"[G-DISJOINT] ***** MERGED GATE FAILED *****\n"
                  f"[G-DISJOINT] violated comparison(s): {', '.join(bad) or 'none'}\n"
                  f"[G-DISJOINT] strata_root_overlap = "
                  f"{report['strata_root_overlap']}\n"
                  f"[G-DISJOINT] The corpus is CONTAMINATED — DO NOT score it.\n"
                  f"{'=' * 70}", file=sys.stderr)
            return 1
        print(f"[G-DISJOINT] PASS — {len(report['comparisons'])} comparison(s) "
              f"x 3 layers all empty, strata_root_overlap = 0.")
        return 0

    a.out = a.out or str(DEFAULT_OUT)
    spent_dir, new_dir = Path(a.spent_dir), Path(a.new_dir)
    spent_arms = Path(a.spent_arms) if a.spent_arms else spent_dir / "ARMS.json"
    new_arms = Path(a.new_arms) if a.new_arms else new_dir / "ARMS.json"

    try:
        report = run_gate(
            spent_arms=spent_arms, new_arms=new_arms,
            spent_legs=leg_paths(spent_dir, a.spent_leg_glob),
            new_legs=leg_paths(new_dir, a.new_leg_glob))
    except GateInputError as exc:
        print(f"\n{'=' * 70}\n[G-DISJOINT] COULD NOT EVALUATE: {exc}\n{'=' * 70}",
              file=sys.stderr)
        return 2

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True))

    for name, L in sorted(report["layers"].items()):
        print(f"[G-DISJOINT] {name:20s} spent={L['n_spent']:6d} "
              f"new={L['n_new']:6d} intersection={L['n_intersection']:6d}")
    print(f"[G-DISJOINT] sha256(spent rid list) = {report['sha256_spent_rid_list']}")
    print(f"[G-DISJOINT] sha256(new   rid list) = {report['sha256_new_rid_list']}")
    if a.out:
        print(f"[G-DISJOINT] -> {a.out}")

    if not report["passed"]:
        bad = sorted(k for k, L in report["layers"].items() if L["n_intersection"])
        print(f"\n{'=' * 70}\n"
              f"[G-DISJOINT] ***** GATE FAILED *****\n"
              f"[G-DISJOINT] {report['n_layers_violated']} of 3 identity layers "
              f"OVERLAP the spent corpus: {', '.join(bad)}\n"
              f"[G-DISJOINT] The fresh corpus is CONTAMINATED — it re-uses "
              f"positions that already selected the read rule.\n"
              f"[G-DISJOINT] DO NOT score it. Rebuild the corpus from a clean "
              f"deck-seed band.\n{'=' * 70}", file=sys.stderr)
        return 1

    print("[G-DISJOINT] PASS — all three intersections are empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
