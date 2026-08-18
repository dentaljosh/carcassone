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

──────────────────────────────────────────────────────────────────────────────
W5/R4 — the `--r4` mode: SEVEN comparisons + pre-committed digest EXCLUSIONS
──────────────────────────────────────────────────────────────────────────────
R3.3's pair died by gate failure on exactly ONE `c_position_digest` collision —
zero root overlap, zero rid overlap, a genuine cross-band board TRANSPOSITION
(`PREREG_FAILURE.md`). The three-layer gate did its job; what was missing was a
rule for what to DO about a transposition. R4 supplies it, pre-committed, and
widens the comparison set to cover the cases R4's own band structure creates:

    s1_vs_tiletie0812   s1_vs_tiearb2_0816   } the four ARMS-vs-ARMS
    s2_vs_tiletie0812   s2_vs_tiearb2_0816   } vs the two SPENT corpora
    base_vs_extension   — PER STRATUM, all three layers. 135e9 vs 137e9 WITHIN
                          one stratum: impossible in R3's contiguous band,
                          EXPECTED (order-1 at FULL) in R4's.
    s1_vs_s2            — all three layers. The LARGEST previously-unmeasured
                          case (~1-2 events at FULL, ~3.4x base<->extension) and
                          the one R4-3 rule 2 already claimed to govern.
    s1s2_vs_exclude_rids — b_rid ONLY (a rid TEXT list has no board layer).

Semantics (DESIGN R4-3):
  * rid and root layers stay ZERO-TOLERANCE — a shared rid or root is a corpus
    LEAK, never a transposition.
  * digest collisions are EXCLUDED and COUNTED, resolved by a TOTAL ORDER
    (spent < 135e9 < 137e9 < 138e9; the later position leaves), with S1<->S2
    excluding the S2 rid regardless of band, and a lexicographically-later-rid
    tiebreak that makes the order total in advance.
  * the bound is `⌈0.005 x n⌉` per stratum, evaluated ONCE against the FROZEN
    `FLOORS.json` denominator — so it cannot grow with the corpus and a VOID is
    not curable by generating more games.
  * the exclusion is OUTCOME-INDEPENDENT by construction: the digest is a
    function of the BOARD alone, computed before any value exists.

    python scripts/tiletie/gate_disjoint.py --r4 \
        --s1-dir RUN/corpus/positions_s1 --s2-dir RUN/corpus/positions_s2 \
        --floors RUN/FLOORS.json --out RUN/GATE_DISJOINT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

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
DEFAULT_MERGED_OUT = (REPO / "measurement/tiearb_widening_20260817/shared_run_r4/"
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


def load_digest_map(paths) -> tuple[dict, int]:
    """`sha256(checksum) -> sorted [rid]` over every leg line, plus `n_lines`.

    The R4 gate must NAME the colliding positions (the total order decides which
    side is excluded), so the digest set is not enough — the map is. A line
    without a `rid` gets a synthetic `<file>#<lineno>` handle: it can still
    resolve a collision, and it only ever occurs on a SPENT corpus's legs, which
    are never the excluded side (spent is rank 0 in the total order)."""
    out: dict = {}
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
            d = hashlib.sha256(str(rec["checksum"]).encode()).hexdigest()
            rid = str(rec.get("rid") or f"{p.name}#{i}")
            out.setdefault(d, set()).add(rid)
    return {d: sorted(v) for d, v in out.items()}, n_lines


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


# --------------------------------------------------------------------------- #
# R4 — the SEVEN-comparison form with pre-committed digest EXCLUSIONS            #
# --------------------------------------------------------------------------- #
#: DESIGN R4-3 rule 1 — the TOTAL ORDER. On a digest collision the HIGHER-ordered
#: (later) position is excluded and the earlier is never touched. Being total, it
#: leaves no pair unruled — including the case R4's own band structure created and
#: R3's contiguous band made impossible: base <-> extension WITHIN one stratum.
BAND_ORDER = ("spent", "135e9", "137e9", "138e9")
BAND_RANGES = {
    "135e9": (135000000000, 135000000849),     # base, RETAINED as valid input
    "137e9": (137000000000, 137999999999),     # extension
    "138e9": (138000000000, 138000000499),     # top-up, RESERVED
}
#: R3's top-up reservation, RELEASED UNUSED. A seed from it anywhere is a FAIL.
RELEASED_BAND = (136000000000, 136999999999)

_SEED_RE = re.compile(r"(\d{11,})")

R4_COMPARISONS = (
    "s1_vs_tiletie0812", "s1_vs_tiearb2_0816",
    "s2_vs_tiletie0812", "s2_vs_tiearb2_0816",
    "base_vs_extension", "s1_vs_s2", "s1s2_vs_exclude_rids",
)


def band_of_rid(rid: str) -> str:
    """Which committed band a rid's deck seed lies in — `135e9` / `137e9` /
    `138e9` / `released136e9` / `unknown`.

    A rid carries its game's deck seed (`tt_sp_<deck_seed>_p<ply>`), so the band
    is a property of the position's own identity and needs no side table."""
    m = _SEED_RE.search(str(rid))
    if not m:
        return "unknown"
    seed = int(m.group(1))
    for name, (lo, hi) in BAND_RANGES.items():
        if lo <= seed <= hi:
            return name
    if RELEASED_BAND[0] <= seed <= RELEASED_BAND[1]:
        return "released136e9"
    return "unknown"


def _rank(band: str) -> int:
    return BAND_ORDER.index(band) if band in BAND_ORDER else len(BAND_ORDER)


def resolve_collision(a_rid: str, b_rid: str, *, a_band: str, b_band: str,
                      a_stratum=None, b_stratum=None) -> dict:
    """DESIGN R4-3 rules 1-3: WHICH side of one digest collision is excluded.

    * **Rule 2 first** — an `S1 <-> S2` collision excludes the **S2** rid
      REGARDLESS of band. S1 is the B-ladder's primary; S2 is the rider, and two
      strata sharing a board would contaminate the independent-replication rider
      that compares them.
    * **Rule 1** — otherwise the total order decides: the later band is excluded.
    * **Rule 3** — same-rank pairs are out of scope by construction (no
      comparison measures a stratum-band against itself). The deterministic
      tiebreak — **the lexicographically-later rid** — is implemented anyway, so
      the rule is total IN ADVANCE rather than after the first surprise.
    """
    strata = {a_stratum, b_stratum}
    if strata == {"S1", "S2"}:
        excluded = a_rid if a_stratum == "S2" else b_rid
        return {"excluded_rid": excluded,
                "excluded_stratum": "S2", "rule": "R4-3 rule 2 (S1<->S2 => S2)"}
    ra, rb = _rank(a_band), _rank(b_band)
    if ra != rb:
        later = a_rid if ra > rb else b_rid
        return {"excluded_rid": later,
                "excluded_stratum": (a_stratum if ra > rb else b_stratum),
                "rule": f"R4-3 rule 1 (total order: {BAND_ORDER})"}
    later = max(a_rid, b_rid)
    return {"excluded_rid": later,
            "excluded_stratum": (a_stratum if later == a_rid else b_stratum),
            "rule": "R4-3 rule 3 tiebreak (same rank => lexicographically-later "
                    "rid); same-rank pairs are OUT OF SCOPE by construction and "
                    "this branch exists only to make the order total in advance"}


def _layer_block(identity, n_new, n_ref, n_int, **extra):
    return {"identity": identity, "n_new": n_new, "n_ref": n_ref,
            "n_intersection": n_int, **extra}


def compare_r4(a: dict, b: dict, *, name: str, digest_excludes=True) -> dict:
    """ONE R4 comparison. Sides are `{rids, roots, digests: {d: [rid]},
    n_lines, stratum, label}`.

    The rid and root layers stay **ZERO-TOLERANCE** — a shared rid or root is a
    corpus LEAK, never a transposition. The digest layer is **recorded and
    resolved**, not fatal-on-first: each collision is named and the total order
    says which side leaves."""
    inter_r = a["roots"] & b["roots"]
    inter_i = a["rids"] & b["rids"]
    shared = sorted(set(a["digests"]) & set(b["digests"]))
    collisions = []

    def _band(side, rid):
        """⚠️ The total order is over CORPORA, not over rid spellings. A SPENT
        reference is rank 0 BY IDENTITY — its rids carry banked seeds (28e9…)
        that lie in none of R4's committed ranges, so ranking it by
        `band_of_rid` would score it `unknown`, sort it LAST, and exclude the
        BANKED position instead of ours — the exact inversion of R4-3 rule 1
        ("the earlier is never touched"). Caught by the fixture; it would
        otherwise have fired on the first real spent-corpus collision."""
        return "spent" if side.get("stratum") == "spent" else band_of_rid(rid)

    for d in shared:
        for ar in a["digests"][d]:
            for br in b["digests"][d]:
                res = resolve_collision(
                    ar, br, a_band=_band(a, ar), b_band=_band(b, br),
                    a_stratum=a.get("stratum"), b_stratum=b.get("stratum"))
                collisions.append({
                    "digest": d, "a_rid": ar, "b_rid": br,
                    "a_band": _band(a, ar), "b_band": _band(b, br),
                    "a_side": a.get("label"), "b_side": b.get("label"),
                    **res})
    layers = {
        "a_root_id": _layer_block("root_id (the GAME) from ARMS.json values",
                                  len(a["roots"]), len(b["roots"]), len(inter_r),
                                  zero_tolerance=True),
        "b_rid": _layer_block("rid (the (game, ply) POSITION) from ARMS.json keys",
                              len(a["rids"]), len(b["rids"]), len(inter_i),
                              zero_tolerance=True),
        "c_position_digest": _layer_block(
            "sha256(checksum) = game.string_representation(board) at the tied root",
            len(a["digests"]), len(b["digests"]), len(shared),
            zero_tolerance=False,
            n_new_leg_lines=a.get("n_lines"), n_ref_leg_lines=b.get("n_lines")),
    }
    zero_bad = sum(1 for k, L in layers.items()
                   if L.get("zero_tolerance") and L["n_intersection"])
    return {
        "name": name,
        "inputs": {"a": a.get("label"), "b": b.get("label")},
        "layers": layers,
        "digest_collisions": collisions if digest_excludes else [],
        "n_digest_collisions": len(collisions),
        "n_zero_tolerance_layers_violated": zero_bad,
        # `passed` is the ZERO-TOLERANCE verdict (READ_RULE §2b(i)): the digest
        # layer is excluded-and-counted, never a pass conjunct.
        "passed": zero_bad == 0,
    }


def _side(*, label, arms=None, legs=(), rids=None, stratum=None,
          seed_range=None) -> dict:
    """Build one comparison side. `seed_range` restricts it to a band sub-set —
    that is how `base_vs_extension` splits ONE stratum into its two bands."""
    if rids is not None:
        return {"label": label, "stratum": stratum, "rids": set(rids),
                "roots": set(), "digests": {}, "n_lines": 0, "rid_only": True}
    r = load_rids(arms)
    roots = load_root_ids(arms)
    dmap, n_lines = load_digest_map(legs)
    if seed_range is not None:
        lo, hi = seed_range
        def _in(x):
            m = _SEED_RE.search(str(x))
            return bool(m) and lo <= int(m.group(1)) <= hi
        r = {x for x in r if _in(x)}
        arms_idx = _load_arms(arms)
        roots = {str(v["root_id"]) for k, v in arms_idx.items() if k in r}
        dmap = {d: [x for x in v if _in(x)] for d, v in dmap.items()}
        dmap = {d: v for d, v in dmap.items() if v}
    return {"label": label, "stratum": stratum, "rids": r, "roots": roots,
            "digests": dmap, "n_lines": n_lines, "rid_only": False}


def load_carried_exclusions(path) -> dict:
    """Exclusions ALREADY APPLIED at build time, carried forward into the final
    gate report.

    R4-3 rule 5 requires the exclusions to happen **before** `POSITIONS_PLAN` is
    frozen — so by the time the FINAL corpus exists, the excluded rids are gone
    and a fresh gate run would report `n_excluded == 0`, silently losing the
    record and making the bound vacuous. The corpus driver therefore runs the
    gate ONCE on a throwaway PROBE build (which still contains the colliding
    rids), applies the exclusions, and carries that report's own exclusion block
    into the final one. What the final `GATE_DISJOINT.json` reports is
    `carried + residual`, which is the true count the bound must be measured
    against."""
    p = Path(path)
    if not p.is_file():
        raise GateInputError(f"carried-exclusions file not found: {p}")
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise GateInputError(f"{p}: not JSON ({exc})") from exc
    out = {}
    for s, v in (d.get("digest_exclusions") or {}).items():
        out[s] = {"rids": list(v.get("rids") or []),
                  "evidence": list(v.get("evidence") or [])}
    return out


def run_r4_gate(*, strata: dict, refs: dict, floors: dict, exclude_rids=None,
                base_range=None, extension_range=None, carried=None) -> dict:
    """The R4 `G-DISJOINT` report — SEVEN comparisons + the exclusion block.

    `strata` = `{"S1": {"arms", "legs"}, "S2": {...}}` (S2 optional: `S1 ONLY`)
    `refs`   = `{"tiletie0812": {...}, "tiearb2_0816": {...}}`
    `floors` = the loaded `FLOORS.json` — the FROZEN exclusion denominator.
    """
    import floors as FL                                            # noqa: E402

    base_range = base_range or BAND_RANGES["135e9"]
    extension_range = extension_range or BAND_RANGES["137e9"]

    sides = {s: _side(label=f"{s} (all bands)", arms=v["arms"], legs=v["legs"],
                      stratum=s)
             for s, v in sorted(strata.items())}
    ref_sides = {n: _side(label=n, arms=v["arms"], legs=v["legs"],
                          stratum="spent")
                 for n, v in sorted(refs.items())}

    comparisons: dict = {}
    # (1-4) the four ARMS-vs-ARMS comparisons against the two SPENT corpora
    for s in sorted(sides):
        for n in sorted(ref_sides):
            key = f"{s.lower()}_vs_{n}"
            comparisons[key] = compare_r4(sides[s], ref_sides[n], name=key)

    # (5) base_vs_extension — PER STRATUM, all three layers. The intra-stratum
    # cross-band case R3's contiguous band made impossible and R4's base+extension
    # structure makes EXPECTED (order-1 at FULL).
    by_stratum, agg = {}, []
    for s, v in sorted(strata.items()):
        a = _side(label=f"{s} base 135e9", arms=v["arms"], legs=v["legs"],
                  stratum=s, seed_range=base_range)
        b = _side(label=f"{s} extension 137e9", arms=v["arms"], legs=v["legs"],
                  stratum=s, seed_range=extension_range)
        c = compare_r4(a, b, name=f"base_vs_extension[{s}]")
        by_stratum[s] = c
        agg.append(c)
    comparisons["base_vs_extension"] = _aggregate("base_vs_extension", agg,
                                                  by_stratum)

    # (6) s1_vs_s2 — all three layers. The LARGEST previously-unmeasured case
    # (~1-2 expected events at FULL, ~3.4x base<->extension), and the one R4-3
    # rule 2 already claimed to govern.
    if "S1" in sides and "S2" in sides:
        comparisons["s1_vs_s2"] = compare_r4(sides["S1"], sides["S2"],
                                             name="s1_vs_s2")
    else:
        comparisons["s1_vs_s2"] = _not_applicable(
            "s1_vs_s2", "S2 does not exist (FLOORS.json n2 == 0, the S1 ONLY "
                        "row): rung 3 was NOT BOUGHT, so there is no second "
                        "stratum to compare")

    # (7) s1s2_vs_exclude_rids — b_rid ONLY (a rid TEXT list has no root and no
    # board layer; the missing layers are ABSENT, never fabricated as zero)
    txts = [Path(p) for p in (exclude_rids or ())]
    excl_rids: set = set()
    for t in txts:
        excl_rids |= load_rid_txt(t)
    union = set().union(*(s["rids"] for s in sides.values())) if sides else set()
    comparisons[EXCLUDE_COMPARISON] = compare_rid_list(
        union, excl_rids,
        inputs={"new_strata": sorted(sides),
                "ref_rid_txts": [str(p) for p in txts]})
    comparisons[EXCLUDE_COMPARISON]["name"] = EXCLUDE_COMPARISON
    comparisons[EXCLUDE_COMPARISON]["n_digest_collisions"] = 0
    comparisons[EXCLUDE_COMPARISON]["digest_collisions"] = []

    # §2b(vi) requires ALL SEVEN comparisons PRESENT. On the `S1 ONLY` row the
    # S2-side ones cannot be computed — so they are present-and-explained, never
    # silently dropped: a reader iterating the seven must never find a hole and
    # have to decide for itself whether it means "clean" or "not run".
    for name in R4_COMPARISONS:
        if name not in comparisons:
            comparisons[name] = _not_applicable(
                name, "S2 does not exist (FLOORS.json n2 == 0, the S1 ONLY "
                      "row): rung 3 was NOT BOUGHT, so this comparison has no "
                      "second side")

    # ---- the R4-3 exclusion block ------------------------------------------ #
    per_stratum: dict = {}
    carried = carried or {}
    for s in sorted(sides):
        rids, evid = set(), []
        for cname, c in comparisons.items():
            for col in c.get("digest_collisions", []):
                if col.get("excluded_stratum") == s:
                    rids.add(col["excluded_rid"])
                    evid.append({"comparison": cname, **col})
        n_residual = len(rids)
        carried_rids = set(carried.get(s, {}).get("rids") or ())
        rids |= carried_rids
        evid = list(carried.get(s, {}).get("evidence") or []) + evid
        bound, den, den_src = FL.exclusion_bound(floors, s)
        n = len(rids)
        per_stratum[s] = {
            # READ_RULE §2b names `carried` and `residual` EXACTLY (R4-0.2):
            # `carried` is the exclusion count measured on the PROBE build,
            # `residual` the fresh collisions in the FINAL build (expected 0),
            # and the bound is evaluated on `carried + residual`.
            "carried": len(carried_rids),
            "residual": n_residual,
            "n_excluded": n,
            # ⚠️ A nonzero `residual` is additionally a DETERMINISM DEFECT: the
            # final build saw a collision the probe did not, on the same corpus
            # under the same rules. The count still binds the bound, but the
            # defect is reported separately because it questions the instrument,
            # not the corpus.
            "determinism_defect": bool(n_residual),
            # ⚠️ THE BOUND IS EVALUATED ON `carried + residual` — the rule's own
            # arithmetic (R4-0.2) — NOT on `n_excluded`. The two differ only
            # when a rid is BOTH carried and re-observed, which is exactly the
            # non-healthy case; taking the sum is the conservative reading and
            # voids earlier, which is the direction a bound should err in.
            "bound_basis": len(carried_rids) + n_residual,
            "rids": sorted(rids),
            "rate": (n / den) if den else None,
            "bound_n": bound,
            "denominator": den,
            # ⚠️ an ADDRESS G-DISJOINT reads — ABSENT IS FAIL, so it is always
            # emitted, whether or not anything was excluded
            "denominator_source": den_src,
            "bound_fraction": FL.EXCLUSION_BOUND_FRACTION,
            "void": bool(len(carried_rids) + n_residual > bound),
            "evidence": evid,
            "note": "the bound is evaluated ONCE, on carried + residual "
                    "(R4-0.2), at the FINAL gate, against the FROZEN "
                    "FLOORS.json denominator. `carried` is the count measured "
                    "on the PROBE build — the build that still contains the "
                    "colliding rids — which is what makes rules 5 and 7 "
                    "simultaneously satisfiable instead of jointly vacuous. A "
                    "VOID stratum stays VOID: it is NOT curable by generating "
                    "more games, because the denominator does not grow with "
                    "the corpus. The answer to a VOID is a new prereg.",
        }

    # rid/root layers are zero-tolerance on EVERY comparison; the digest layer is
    # not a pass conjunct at all — only the per-stratum bound is.
    zero_bad = sorted(k for k, c in comparisons.items() if not c["passed"])
    voids = sorted(s for s, v in per_stratum.items() if v["void"])
    names = sorted(sides)
    overlap = 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            overlap += len(sides[names[i]]["roots"] & sides[names[j]]["roots"])

    released = sorted({r for s in sides.values() for r in s["rids"]
                       if band_of_rid(r) == "released136e9"})

    return {
        "gate": "G-DISJOINT",
        "mode": "r4",
        "goal": "no widening stratum shares a game or a position with any banked "
                "corpus or with the other stratum; shared BOARDS are excluded "
                "under the R4-3 total order and counted against a frozen bound",
        "disclosure_policy": "counts, rids and digests of EXCLUDED positions only "
                             "— the exclusion must be auditable, so the excluded "
                             "rids are named (READ_RULE §2b: always printed)",
        "total_order": list(BAND_ORDER),
        "comparisons": comparisons,
        "comparisons_expected": list(R4_COMPARISONS),
        "digest_exclusions": per_stratum,
        "strata_root_overlap": overlap,
        "released_band_seeds_found": released,
        "n_comparisons_violated": len(zero_bad),
        "voided_strata": voids,
        "passed": (not zero_bad) and overlap == 0 and not voids and not released,
        "floors": {"option_label": floors.get("option_label"),
                   "n1": floors.get("n1"), "n2": floors.get("n2")},
    }


def _aggregate(name, parts, by_stratum) -> dict:
    """`base_vs_extension` is ONE comparison evaluated PER STRATUM. The top-level
    `layers` are the summed counts (zero iff every stratum is zero, which is what
    a reader iterating `comparisons.<name>.layers.<layer>.n_intersection`
    needs), and `by_stratum` carries each stratum's own three layers."""
    layers = {}
    for lname in ("a_root_id", "b_rid", "c_position_digest"):
        layers[lname] = {
            "identity": (parts[0]["layers"][lname]["identity"] if parts
                         else lname),
            "n_new": sum(p["layers"][lname]["n_new"] for p in parts),
            "n_ref": sum(p["layers"][lname]["n_ref"] for p in parts),
            "n_intersection": sum(p["layers"][lname]["n_intersection"]
                                  for p in parts),
            "zero_tolerance": lname != "c_position_digest",
        }
    cols = [c for p in parts for c in p["digest_collisions"]]
    zero_bad = sum(1 for L in layers.values()
                   if L["zero_tolerance"] and L["n_intersection"])
    return {"name": name, "per_stratum": True,
            "by_stratum": {k: v for k, v in by_stratum.items()},
            "layers": layers, "digest_collisions": cols,
            "n_digest_collisions": len(cols),
            "n_zero_tolerance_layers_violated": zero_bad,
            "passed": zero_bad == 0}


def _not_applicable(name, why) -> dict:
    """A comparison that cannot exist on this corpus shape (S1 ONLY). It is
    PRESENT with zero counts and an explicit reason — never silently dropped,
    because §2b(vi) requires all seven to be present."""
    layers = {k: {"identity": k, "n_new": 0, "n_ref": 0, "n_intersection": 0,
                  "zero_tolerance": k != "c_position_digest",
                  "not_applicable": True}
              for k in ("a_root_id", "b_rid", "c_position_digest")}
    return {"name": name, "layers": layers, "digest_collisions": [],
            "n_digest_collisions": 0, "n_zero_tolerance_layers_violated": 0,
            "passed": True, "not_applicable": True, "reason": why}


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


def _print_r4(report: dict, out_path) -> None:
    """Counts, the exclusion block, and the loud banners. ALWAYS prints the
    exclusion block, whether or not anything was excluded (READ_RULE §2b)."""
    for cname in report["comparisons_expected"]:
        c = report["comparisons"].get(cname)
        if c is None:
            print(f"[G-DISJOINT] {cname:24s} ***** ABSENT *****")
            continue
        bits = " ".join(
            f"{k[0]}={c['layers'][k]['n_intersection']}"
            for k in ("a_root_id", "b_rid", "c_position_digest")
            if k in c["layers"])
        na = " (n/a: " + c.get("reason", "")[:40] + ")" if c.get("not_applicable") else ""
        print(f"[G-DISJOINT] {cname:24s} {bits} "
              f"digest_collisions={c.get('n_digest_collisions', 0)}{na}")
    print(f"[G-DISJOINT] strata_root_overlap = {report['strata_root_overlap']}")
    for s, v in sorted(report["digest_exclusions"].items()):
        print(f"[G-DISJOINT] exclusions[{s}] carried={v['carried']} "
              f"residual={v['residual']} n_excluded={v['n_excluded']} "
              f"rate={v['rate']:.5f} bound={v['bound_n']} "
              f"(denominator {v['denominator']} from {v['denominator_source']}) "
              f"void={v['void']}")
        if v.get("determinism_defect"):
            print(f"[G-DISJOINT]   ⚠️ DETERMINISM DEFECT: residual="
                  f"{v['residual']} — the FINAL build saw a collision the PROBE "
                  f"did not, on the same corpus under the same rules.",
                  file=sys.stderr)
        for rid in v["rids"]:
            print(f"[G-DISJOINT]   excluded rid: {rid}")
    if out_path:
        print(f"[G-DISJOINT] -> {out_path}")
    if report["released_band_seeds_found"]:
        print(f"\n{'=' * 70}\n[G-DISJOINT] ***** RELEASED BAND 136e9 SEEN *****\n"
              f"[G-DISJOINT] 136e9 was RELEASED UNUSED and must appear in NO "
              f"file. {len(report['released_band_seeds_found'])} rid(s) carry "
              f"it.\n{'=' * 70}", file=sys.stderr)
    if report["voided_strata"]:
        print(f"\n{'=' * 70}\n[G-DISJOINT] ***** STRATUM VOID *****\n"
              f"[G-DISJOINT] {', '.join(report['voided_strata'])} exceeded the "
              f"exclusion bound.\n"
              f"[G-DISJOINT] At that density, transposition degeneracy is a "
              f"PROPERTY OF THE GENERATOR and 'fresh corpus' is the wrong "
              f"description — a DIFFERENT FINDING, which must surface rather "
              f"than be absorbed.\n"
              f"[G-DISJOINT] A VOID IS NOT CURABLE BY GENERATING MORE GAMES: "
              f"the denominator is frozen in FLOORS.json. The answer is a new "
              f"prereg.\n{'=' * 70}", file=sys.stderr)
    if report["n_comparisons_violated"]:
        bad = sorted(k for k, c in report["comparisons"].items() if not c["passed"])
        print(f"\n{'=' * 70}\n[G-DISJOINT] ***** ZERO-TOLERANCE LAYER VIOLATED "
              f"*****\n[G-DISJOINT] {', '.join(bad)}\n"
              f"[G-DISJOINT] A shared rid or root is a CORPUS LEAK, never a "
              f"transposition. DO NOT score this corpus.\n{'=' * 70}",
              file=sys.stderr)
    if report["passed"]:
        print(f"[G-DISJOINT] PASS — {len(report['comparisons'])} comparison(s); "
              f"zero-tolerance layers clean; no stratum void.")


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

    r = ap.add_argument_group(
        "R4 mode — SEVEN comparisons + pre-committed digest exclusions")
    r.add_argument("--r4", action="store_true",
                   help="emit the R4 G-DISJOINT report (READ_RULE §2b)")
    r.add_argument("--floors", default=None,
                   help="RUN/FLOORS.json — the FROZEN exclusion denominator. "
                        "REQUIRED by --r4: the bound is evaluated against it, "
                        "not against the realized corpus size")
    r.add_argument("--carry-exclusions", default=None, metavar="PROBE_GATE_JSON",
                   help="a PROBE-build gate report whose exclusions were already "
                        "applied; its counts are carried into this report so the "
                        "bound is measured against the TRUE total, not against "
                        "the post-exclusion residual")
    a = ap.parse_args(argv)

    if a.r4:
        import floors as FL                                        # noqa: E402
        out = a.out or str(DEFAULT_MERGED_OUT)
        try:
            if not a.floors:
                raise GateInputError(
                    "--r4 requires --floors: R4-3 rule 7 evaluates the exclusion "
                    "bound ONCE, against the denominator recorded in "
                    "RUN/FLOORS.json, so that a VOID cannot be cured by "
                    "generating more games")
            floors = FL.load(a.floors)
            resolved = _merged_from_args(a)
            carried = (load_carried_exclusions(a.carry_exclusions)
                       if a.carry_exclusions else None)
            report = run_r4_gate(strata=resolved["strata"],
                                 refs=resolved["refs"],
                                 floors=floors,
                                 exclude_rids=resolved["exclude_rids"],
                                 carried=carried)
        except (GateInputError, FL.FloorsError) as exc:
            print(f"\n{'=' * 70}\n[G-DISJOINT] COULD NOT EVALUATE: {exc}\n"
                  f"{'=' * 70}", file=sys.stderr)
            return 2
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(report, indent=2, sort_keys=True))
        _print_r4(report, out)
        if not report["passed"]:
            return 1
        return 0

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
