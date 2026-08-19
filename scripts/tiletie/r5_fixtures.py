#!/usr/bin/env python3
"""rung3_r5's A1 fixture set — `measurement/tiearb_widening_20260817/rung3_r5/
DESIGN.md` §R5-FINAL.i, `READ_RULE.md` §1 (`A1 [pre-corpus]`, spec commit
`bed67165`).

`A1` is the static schema pass: **before the blind commit**, every
`[post-corpus]` / `[post-scoring]` address named anywhere in `READ_RULE.md`
must resolve against a COMMITTED fixture — key presence and JSON type only,
**never a value**. This module is the fixture emitter (`--emit`) and the A1
checker (`--check` / `check_a1`).

⭐ THE DIRECTION THAT MATTERS (R5-6.1's diagnosis, restated as a build
requirement): completeness is asserted over the **MARKER LIST**
(`A1_MARKERS` below — one entry per address READ_RULE actually names), never
over "do the 9 filenames on disk exist". R4's A1 leak was exactly the
inverse of this: a fixture-filename checklist that never noticed
`RUN_MANIFEST` wasn't on it. Here, deleting or corrupting ANY fixture file
makes every marker that resolves through it FAIL — there is no filename list
for a marker to silently fall outside of.

The nine fixtures (DESIGN §R5-FINAL.i's own list):
    CORPUS_R5.fixture.json          RUN_MANIFEST_R5.fixture.json
    GATE_INTERNAL_DUPE.fixture.json leg_manifest.fixture.json   <- resolved_config.*
    GATE_DISJOINT_R5.fixture.json   READOUT.fixture.json        <- widening.*
    SMOKE_R5.fixture.json           D_DRAW.fixture.json
    MERGE_REPORT_s2.fixture.json

Three are produced by the REAL emitters on a tiny synthetic corpus
(`CORPUS_R5`, `GATE_INTERNAL_DUPE` via `build_r5_corpus.build`;
`GATE_DISJOINT_R5` via `gate_disjoint.run_r5_gate`) so those fixtures cannot
drift from what the real tools actually write. `D_DRAW` reuses
`widening_fixtures.make_d_draw` — the shape is already established and
committed for the R4 campaign. The remaining five
(`RUN_MANIFEST_R5`/`leg_manifest`/`READOUT`/`SMOKE_R5`/`MERGE_REPORT_s2`) are
hand-built, seeded-RNG-free synthetic dicts: no engine, no replay, no
playout — only the key SHAPE A1 audits.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

REPO = Path(__file__).resolve().parents[2]

import build_r5_corpus as BR5                                       # noqa: E402
import gate_disjoint as GD                                          # noqa: E402
import widening_fixtures as WF                                      # noqa: E402

RUN = REPO / "measurement/tiearb_widening_20260817/rung3_r5"
FIXTURE_DIR = RUN / "fixtures"

FIXTURE_NAMES = (
    "CORPUS_R5.fixture.json", "GATE_INTERNAL_DUPE.fixture.json",
    "GATE_DISJOINT_R5.fixture.json", "SMOKE_R5.fixture.json",
    "MERGE_REPORT_s2.fixture.json", "RUN_MANIFEST_R5.fixture.json",
    "leg_manifest.fixture.json", "READOUT.fixture.json",
    "D_DRAW.fixture.json",
)


# --------------------------------------------------------------------------- #
# marker list — one entry per READ_RULE §2 address, NOT one per filename       #
# --------------------------------------------------------------------------- #
#: `marker -> (fixture_filename, dotted_key_path, expected_type)`.
#: `dotted_key_path` may contain a `*` segment meaning "any key at this
#: position" (`comparisons.*.layers.a_root_id.n_intersection`), for addresses
#: keyed by a comparison/chunk name A1 does not enumerate.
A1_MARKERS = {
    # G-CORPUS -- RUN/CORPUS_R5.json
    "G-CORPUS::leg_path": ("CORPUS_R5.fixture.json", "leg_path", str),
    "G-CORPUS::leg_sha256": ("CORPUS_R5.fixture.json", "leg_sha256", str),
    "G-CORPUS::r4_exclusion_list_sha256": (
        "CORPUS_R5.fixture.json", "r4_exclusion_list_sha256", str),
    "G-CORPUS::n_in": ("CORPUS_R5.fixture.json", "n_in", int),
    "G-CORPUS::n_excluded_r5": ("CORPUS_R5.fixture.json", "n_excluded_r5", int),
    "G-CORPUS::n_positions": ("CORPUS_R5.fixture.json", "n_positions", int),
    "G-CORPUS::excluded_rids": ("CORPUS_R5.fixture.json", "excluded_rids", list),
    # G-BAND -- RUN/CORPUS_R5.json (same artifact, DIFFERENT gate)
    "G-BAND::n_distinct_seeds": ("CORPUS_R5.fixture.json", "n_distinct_seeds", int),
    "G-BAND::max_positions_per_seed": (
        "CORPUS_R5.fixture.json", "max_positions_per_seed", int),
    "G-BAND::n_out_of_band": ("CORPUS_R5.fixture.json", "n_out_of_band", int),
    "G-BAND::n_seeds_136e9": ("CORPUS_R5.fixture.json", "n_seeds_136e9", int),
    "G-BAND::seed_ranges": ("CORPUS_R5.fixture.json", "seed_ranges", dict),

    # G-INTERNAL-DUPE -- RUN/GATE_INTERNAL_DUPE.json
    "G-INTERNAL-DUPE::n_positions": (
        "GATE_INTERNAL_DUPE.fixture.json", "n_positions", int),
    "G-INTERNAL-DUPE::n_dupe_groups": (
        "GATE_INTERNAL_DUPE.fixture.json", "n_dupe_groups", int),
    "G-INTERNAL-DUPE::n_dupe_positions": (
        "GATE_INTERNAL_DUPE.fixture.json", "n_dupe_positions", int),
    "G-INTERNAL-DUPE::d_internal": (
        "GATE_INTERNAL_DUPE.fixture.json", "d_internal", float),
    "G-INTERNAL-DUPE::ply_histogram": (
        "GATE_INTERNAL_DUPE.fixture.json", "ply_histogram", dict),
    "G-INTERNAL-DUPE::band_pairs": (
        "GATE_INTERNAL_DUPE.fixture.json", "band_pairs", list),
    "G-INTERNAL-DUPE::leg_sha256": (
        "GATE_INTERNAL_DUPE.fixture.json", "leg_sha256", str),

    # G-DISJOINT -- RUN/GATE_DISJOINT_R5.json
    "G-DISJOINT::passed": ("GATE_DISJOINT_R5.fixture.json", "passed", bool),
    "G-DISJOINT::comparisons.<name>.layers.a_root_id.n_intersection": (
        "GATE_DISJOINT_R5.fixture.json",
        "comparisons.*.layers.a_root_id.n_intersection", int),
    "G-DISJOINT::comparisons.<name>.layers.b_rid.n_intersection": (
        "GATE_DISJOINT_R5.fixture.json",
        "comparisons.*.layers.b_rid.n_intersection", int),

    # G-M -- pre-leg (RUN/SMOKE_R5.json, top level)
    "G-M(pre-leg)::m_worlds": ("SMOKE_R5.fixture.json", "m_worlds", int),
    "SMOKE::oracle_sims": ("SMOKE_R5.fixture.json", "oracle_sims", int),
    "SMOKE::arb_backend": ("SMOKE_R5.fixture.json", "arb_backend", str),
    "SMOKE::c_worker_secs_per_playout": (
        "SMOKE_R5.fixture.json", "c_worker_secs_per_playout", float),
    "SMOKE::crn_cross_leg_identical": (
        "SMOKE_R5.fixture.json", "crn_cross_leg_identical", bool),

    # G-M -- post (RUN/RUN_MANIFEST_R5.json)
    "G-M(post)::m_worlds": ("RUN_MANIFEST_R5.fixture.json", "m_worlds", int),
    "G-M(post)::b_ceiling_from_m": (
        "RUN_MANIFEST_R5.fixture.json", "b_ceiling_from_m", int),
    # G-SALT -- RUN/RUN_MANIFEST_R5.json
    "G-SALT::world_seed_salt": (
        "RUN_MANIFEST_R5.fixture.json", "world_seed_salt", str),
    # G-BACKEND -- RUN/RUN_MANIFEST_R5.json
    "G-BACKEND::arb_backend": ("RUN_MANIFEST_R5.fixture.json", "arb_backend", str),
    "G-BACKEND::resolved_backend_by_leg": (
        "RUN_MANIFEST_R5.fixture.json", "resolved_backend_by_leg", dict),
    "G-BACKEND::arb_legal_mask_cache": (
        "RUN_MANIFEST_R5.fixture.json", "arb_legal_mask_cache", bool),

    # fallbacks -- RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json
    "G-M(fallback)::resolved_config.m": (
        "leg_manifest.fixture.json", "resolved_config.m", int),
    "G-SALT(fallback)::resolved_config.world_seed_salt": (
        "leg_manifest.fixture.json", "resolved_config.world_seed_salt", str),
    "G-BACKEND(fallback)::resolved_config.legal_mask_cache": (
        "leg_manifest.fixture.json", "resolved_config.legal_mask_cache", bool),

    # G-COMPLETE / G-FAILED / G-DDRAW -- READOUT::widening.*
    "G-COMPLETE::widening.completion.s2_n": (
        "READOUT.fixture.json", "widening.completion.s2_n", int),
    "G-FAILED::widening.failed.n_failed_rids": (
        "READOUT.fixture.json", "widening.failed.n_failed_rids", int),
    "G-FAILED::widening.failed.n_attempted": (
        "READOUT.fixture.json", "widening.failed.n_attempted", int),
    "G-FAILED::widening.failed.rate": (
        "READOUT.fixture.json", "widening.failed.rate", float),
    "G-FAILED::widening.failed.by_class": (
        "READOUT.fixture.json", "widening.failed.by_class", dict),
    "G-DDRAW::widening.j_rider.d_draw.d_draw_ran": (
        "READOUT.fixture.json", "widening.j_rider.d_draw.d_draw_ran", bool),

    # G-DDRAW -- RUN/D_DRAW.json (existence + shape witness)
    "G-DDRAW::D_DRAW.json": ("D_DRAW.fixture.json", "n_checked", int),

    # G-TWOBOX -- RUN/MERGE_REPORT_s2.json
    "G-TWOBOX::preserved_from_existing": (
        "MERGE_REPORT_s2.fixture.json", "preserved_from_existing", dict),
    "G-TWOBOX::per_chunk_execution": (
        "MERGE_REPORT_s2.fixture.json", "by_chunk.*.execution", dict),
    "G-TWOBOX::carc_rs_build_equality": (
        "MERGE_REPORT_s2.fixture.json", "by_chunk.*.execution.carc_rs_build", str),
    "G-TWOBOX::carc_rs_binary_sha_constancy": (
        "MERGE_REPORT_s2.fixture.json", "carc_rs_binary_sha_constancy", dict),
}


# --------------------------------------------------------------------------- #
# dotted-path resolution, with a `*` wildcard for unenumerated keys            #
# --------------------------------------------------------------------------- #
class A1Error(RuntimeError):
    """A marker could not be resolved — missing fixture file, missing key,
    or wrong JSON type. A1 must FAIL loudly on any of these, never coerce."""


def resolve_path(obj, dotted_path: str):
    """Walk `dotted_path` (dot-separated, `*` = "any key here") through
    `obj`. Raises `A1Error` with a precise reason on any miss."""
    cur = obj
    parts = dotted_path.split(".")
    for i, part in enumerate(parts):
        so_far = ".".join(parts[: i + 1])
        if part == "*":
            if not isinstance(cur, dict) or not cur:
                raise A1Error(f"{so_far}: expected a non-empty object to "
                              f"wildcard into, got {type(cur).__name__}")
            cur = next(iter(cur.values()))
            continue
        if not isinstance(cur, dict):
            raise A1Error(f"{so_far}: expected an object, got "
                          f"{type(cur).__name__}")
        if part not in cur:
            raise A1Error(f"{so_far}: key not present")
        cur = cur[part]
    return cur


def _type_ok(value, expected_type) -> bool:
    # bool is a subclass of int in python -- an explicit int marker must NOT
    # accept a bool, and vice versa, or a wrong-typed value would silently pass
    if expected_type is int and isinstance(value, bool):
        return False
    if expected_type is bool and not isinstance(value, bool):
        return False
    if expected_type is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, expected_type)


def check_a1(fixtures_dir=FIXTURE_DIR, markers=None) -> dict:
    """The A1 static schema pass. For EVERY marker in `markers` (default
    `A1_MARKERS`), resolve its fixture file + key path and check the JSON
    type — never a value. Returns `{markers: {name: {ok, reason?}}, passed,
    n_markers, n_failed, missing_files}`.

    ⭐ Iterates the MARKER LIST, not `fixtures_dir`'s own file listing — a
    missing/deleted fixture FILE makes every marker that names it FAIL,
    rather than silently reducing the file count A1 checks against."""
    markers = markers if markers is not None else A1_MARKERS
    fixtures_dir = Path(fixtures_dir)
    cache: dict = {}
    results = {}
    for name, (fname, path, typ) in sorted(markers.items()):
        try:
            if fname not in cache:
                fp = fixtures_dir / fname
                if not fp.is_file():
                    raise A1Error(f"fixture file not found: {fp}")
                try:
                    cache[fname] = json.loads(fp.read_text())
                except json.JSONDecodeError as exc:
                    raise A1Error(f"{fp}: not JSON ({exc})") from exc
            value = resolve_path(cache[fname], path)
            if not _type_ok(value, typ):
                raise A1Error(f"{fname}::{path}: expected type "
                              f"{typ.__name__}, got {type(value).__name__}")
            results[name] = {"ok": True, "fixture": fname, "path": path}
        except A1Error as exc:
            results[name] = {"ok": False, "fixture": fname, "path": path,
                             "reason": str(exc)}
    n_failed = sum(1 for v in results.values() if not v["ok"])
    return {
        "pass": "A1", "audit": "key presence + JSON type only, never a value",
        "markers": results,
        "n_markers": len(results),
        "n_failed": n_failed,
        "passed": n_failed == 0,
    }


# --------------------------------------------------------------------------- #
# fixture emission                                                             #
# --------------------------------------------------------------------------- #
def _emit_corpus_and_dupe_fixtures(dest: Path) -> None:
    """`CORPUS_R5.fixture.json` + `GATE_INTERNAL_DUPE.fixture.json`, produced
    by the REAL `build_r5_corpus.build()` on a tiny synthetic leg — so these
    two fixtures cannot drift from what the real builder actually writes."""
    tmp = Path(tempfile.mkdtemp(prefix="r5_fixture_corpus_"))
    leg = tmp / "positions_walled_leg1.jsonl"
    # 6 rows: 2 banked (135e9), 4 extension (137e9); one same-band dupe pair
    # in the extension band, plus one seed OUTSIDE both declared ranges (so
    # the fixture's n_out_of_band exercises a nonzero shape once and this
    # tool is proven against a non-trivial input, not just the healthy case).
    rows = [
        {"rid": "tt_sp_135000000350_p10", "root_id": "sp_135000000350",
         "deck_seed": 135000000350, "ply": 10, "checksum": "A"},
        {"rid": "tt_sp_135000000351_p12", "root_id": "sp_135000000351",
         "deck_seed": 135000000351, "ply": 12, "checksum": "B"},
        {"rid": "tt_sp_137000000508_p2", "root_id": "sp_137000000508",
         "deck_seed": 137000000508, "ply": 2, "checksum": "DUPE"},
        {"rid": "tt_sp_137000000509_p2", "root_id": "sp_137000000509",
         "deck_seed": 137000000509, "ply": 2, "checksum": "DUPE"},
        {"rid": "tt_sp_137000000510_p20", "root_id": "sp_137000000510",
         "deck_seed": 137000000510, "ply": 20, "checksum": "C"},
        {"rid": "tt_oob_1_p5", "root_id": "oob_1",
         "deck_seed": 1, "ply": 5, "checksum": "D"},
    ]
    leg.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    r4_gate = tmp / "GATE_DISJOINT.json"
    r4_gate.write_text(json.dumps({"digest_exclusions": {"S2": {"rids": []}}}))

    corpus_report, dupe_report = BR5.build(
        leg_path=leg, r4_gate_disjoint_path=r4_gate,
        expect_leg_sha256="", expect_exclusion_sha256="")
    (dest / "CORPUS_R5.fixture.json").write_text(
        json.dumps(corpus_report, indent=2, sort_keys=True))
    (dest / "GATE_INTERNAL_DUPE.fixture.json").write_text(
        json.dumps(dupe_report, indent=2, sort_keys=True))


def _emit_disjoint_fixture(dest: Path) -> None:
    """`GATE_DISJOINT_R5.fixture.json`, produced by the REAL
    `gate_disjoint.run_r5_gate()` on tiny synthetic ARMS.json corpora."""
    tmp = Path(tempfile.mkdtemp(prefix="r5_fixture_disjoint_"))
    s2_dir = tmp / "positions_s2"
    WF.make_corpus(s2_dir, n_positions=4, m=32, seed=5, rid_prefix="r5s2",
                   band_lo=135000000350)
    ref1 = tmp / "ref1"
    WF.make_corpus(ref1, n_positions=2, m=32, seed=9, rid_prefix="spent1",
                   band_lo=28000000000)
    ref2 = tmp / "ref2"
    WF.make_corpus(ref2, n_positions=2, m=32, seed=13, rid_prefix="spent2",
                   band_lo=29000000000)
    # REVIEW_R4 P1: --r5 refuses an empty exclude-rids reference, so the
    # fixture needs a non-empty (synthetic, but non-trivial) one too.
    report = GD.run_r5_gate(
        s2_arms=s2_dir / "ARMS.json",
        refs={"tiletie0812": ref1 / "ARMS.json", "tiearb2_0816": ref2 / "ARMS.json"},
        exclude_ref_rids={"some_unrelated_excluded_rid"})
    (dest / "GATE_DISJOINT_R5.fixture.json").write_text(
        json.dumps(report, indent=2, sort_keys=True))


def _emit_hand_built_fixtures(dest: Path) -> None:
    """The five fixtures with no dedicated real emitter in this build round —
    hand-built, no engine/replay/playout, key SHAPE only (matching
    `widening_fixtures.py`'s own "fabricated from a seeded RNG, meaningless
    by construction" convention)."""
    (dest / "SMOKE_R5.fixture.json").write_text(json.dumps({
        "schema": "carcassonne-tiletie-run/v1", "driver": "run_tiletie --smoke",
        "m_worlds": 32, "oracle_sims": 100, "judge": "clair-puct",
        "backend": "python", "arb_backend": "rust",
        "arb_legal_mask_cache": True, "stratum": "s2",
        "c_worker_secs_per_playout": 0.191824,
        "crn_cross_leg_identical": True,
    }, indent=2, sort_keys=True))

    (dest / "RUN_MANIFEST_R5.fixture.json").write_text(json.dumps({
        "stratum": "S2", "world_seed_salt": "tiletie-v1",
        "m_worlds": 32, "b_ceiling_from_m": 16,
        "arb_backend": "rust", "arb_legal_mask_cache": True,
        "resolved_backend_by_leg": {"tier1-greedy/walled": "rust"},
        "git_rev": "0123456",
    }, indent=2, sort_keys=True))

    (dest / "leg_manifest.fixture.json").write_text(json.dumps({
        "judge": "tier1-greedy", "profile": "walled", "leg": 1,
        "n_ok": 4, "n_crn_verified": 4,
        "resolved_config": {
            "world_seed_salt": "tiletie-v1", "m": 32,
            "legal_mask_cache": True, "backend": "rust",
        },
    }, indent=2, sort_keys=True))

    (dest / "READOUT.fixture.json").write_text(json.dumps({
        "widening": {
            "completion": {"s2_n": 1007},
            "failed": {"n_failed_rids": 0, "n_attempted": 1060,
                      "rate": 0.0, "by_class": {}},
            "j_rider": {"d_draw": {"d_draw_ran": True}},
        },
    }, indent=2, sort_keys=True))

    (dest / "MERGE_REPORT_s2.fixture.json").write_text(json.dumps({
        "stratum": "s2",
        "preserved_from_existing": {"n_preserved": 0},
        "by_chunk": {"0": {"execution": {
            "carc_rs_build": "abcdef0123456789abcdef0123456789abcdef01",
            "carc_rs_binary_sha": "fedcba9876543210",
            "carc_rs_path": "/opt/carc_rs/target/release/librust.so",
        }}},
        "carc_rs_binary_sha_constancy": {"ok": True, "boxes": {}},
    }, indent=2, sort_keys=True))


def emit_committed_fixtures(dest=FIXTURE_DIR) -> Path:
    """Write the committed A1 fixture set (9 files)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    _emit_corpus_and_dupe_fixtures(dest)
    _emit_disjoint_fixture(dest)
    _emit_hand_built_fixtures(dest)
    WF.make_d_draw(dest / "D_DRAW.fixture.json", n_checked=100, n_agree=98,
                   n_unreconstructible=1)
    return dest


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--emit", action="store_true",
                    help="(re)write the committed fixture set")
    ap.add_argument("--check", action="store_true",
                    help="run the A1 marker-completeness pass")
    ap.add_argument("--dest", default=str(FIXTURE_DIR))
    a = ap.parse_args(argv)

    if a.emit:
        d = emit_committed_fixtures(a.dest)
        print(f"[r5-fixtures] committed fixture set -> {d}")

    if a.check:
        report = check_a1(a.dest)
        for name, v in sorted(report["markers"].items()):
            status = "OK  " if v["ok"] else "FAIL"
            extra = "" if v["ok"] else f" ({v['reason']})"
            print(f"[A1] {status} {name}{extra}")
        print(f"[A1] {report['n_markers'] - report['n_failed']}/"
              f"{report['n_markers']} markers resolved")
        if not report["passed"]:
            print(f"\n{'=' * 70}\n[A1] ***** COMPLETENESS FAILED — "
                  f"{report['n_failed']} marker(s) unresolved *****\n"
                  f"{'=' * 70}", file=sys.stderr)
            return 1

    if not a.emit and not a.check:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
