#!/usr/bin/env python3
"""tiearb2_20260816 phase 5b — layer-(c) BOARD-DIGEST exclusions, unit tests.

`gate_disjoint.py`'s layer (c) is `sha256(checksum)` — the BOARD. Unlike layers
(a) `root_id` and (b) `rid`, it is NOT guaranteed by the fresh deck-seed band,
because Carcassonne boards TRANSPOSE. `emit_digest_exclusions.py` is the minimal
response: drop the handful of offending positions, keep the corpus.

Covers, WITHOUT importing the engine, `carcassonne_ai`, numpy or torch:

  * rule (a) — a fresh rid whose board digest is in the SPENT corpus is dropped,
    even though its rid and root are unique (i.e. layers a/b see nothing)
  * rule (b) — a digest duplicated WITHIN the fresh corpus keeps the
    lexicographically smallest rid and drops the rest
  * the two rules overlapping (a duplicated board that is ALSO spent)
  * the counts-only disclosure policy of the JSON report
  * idempotence — a second run over the same inputs yields the same set, and
    re-running over the ALREADY-EXCLUDED corpus is a no-op
  * the emitted `.txt` parses the way `build_positions.py --exclude-rids` parses
    it, and excluding the emitted rids really does drive layer (c) to 0
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import emit_digest_exclusions as EDX  # noqa: E402
import gate_disjoint as GD  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures — the same minimal corpus shape test_tiearb2_corpus.py uses          #
# --------------------------------------------------------------------------- #
def _write_corpus(root: Path, positions: list[dict]) -> Path:
    """(ARMS.json + positions_walled_leg1.jsonl) carrying only the fields the
    gate and the emitter read."""
    root.mkdir(parents=True, exist_ok=True)
    arms = {p["rid"]: {"root_id": p["root_id"], "arms": [1, 2]} for p in positions}
    (root / "ARMS.json").write_text(json.dumps(arms, indent=2, sort_keys=True))
    (root / "positions_walled_leg1.jsonl").write_text("".join(
        json.dumps({"rid": p["rid"], "root_id": p["root_id"],
                    "checksum": p["checksum"], "pick_a": 1, "pick_b": 2}) + "\n"
        for p in positions))
    return root


def _p(rid_tag: str, checksum: str) -> dict:
    """One position. rid and root_id are derived from `rid_tag` so every fixture
    position is unique on layers (a) and (b) unless a test says otherwise."""
    return {"rid": f"tt_sp_{rid_tag}_p2", "root_id": f"sp_{rid_tag}",
            "checksum": checksum}


def _emit(tmp_path, new_dir, spent_dir, *, name="EXCLUDE"):
    out = tmp_path / f"{name}.txt"
    rep_path = tmp_path / f"{name}.json"
    rc = EDX.main(["--new-dir", str(new_dir), "--spent-dir", str(spent_dir),
                   "--out", str(out), "--report", str(rep_path)])
    rids = _parse_exclude_file(out)
    return rc, rids, json.loads(rep_path.read_text()), out


def _parse_exclude_file(path: Path) -> set[str]:
    """`build_positions.load_exclude_rids` re-implemented (strips `#` comments
    and blank lines) so the test needs no engine-adjacent import."""
    return {ln.split("#", 1)[0].strip()
            for ln in Path(path).read_text().splitlines()
            if ln.split("#", 1)[0].strip()}


@pytest.fixture()
def spent(tmp_path) -> Path:
    """A 4-board spent corpus. One board per rid — exactly how the real spent
    corpus is built (733 rids / 733 distinct checksums)."""
    return _write_corpus(tmp_path / "spent", [
        _p("2800000001", "BOARD::S1"), _p("2800000002", "BOARD::S2"),
        _p("2800000003", "BOARD::S3"), _p("2800000004", "BOARD::S4"),
    ])


# --------------------------------------------------------------------------- #
# 1. rule (a) — spent overlap                                                   #
# --------------------------------------------------------------------------- #
def test_rule_a_drops_a_fresh_rid_whose_board_is_spent(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::N1"),
        _p("2810000002", "BOARD::S2"),      # transposition into the spent corpus
        _p("2810000003", "BOARD::N3"),
    ])
    rc, rids, rep, _ = _emit(tmp_path, new, spent)
    assert rc == 0
    assert rids == {"tt_sp_2810000002_p2"}
    assert rep["n_spent_overlap"] == 1
    assert rep["n_internal_dupes"] == 0
    assert rep["n_total_excluded"] == 1


def test_rule_a_fires_where_layers_a_and_b_see_nothing(tmp_path, spent):
    """The whole point: rid and root_id are unique, so ONLY the board identity
    can catch it. Asserted through the real gate, not by inspection."""
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::S1"), _p("2810000002", "BOARD::N2"),
    ])
    out = tmp_path / "DISJ.json"
    rc = GD.main(["--spent-dir", str(spent), "--new-dir", str(new),
                  "--out", str(out)])
    rep = json.loads(out.read_text())
    assert rc == 1
    assert rep["layers"]["a_root_id"]["n_intersection"] == 0
    assert rep["layers"]["b_rid"]["n_intersection"] == 0
    assert rep["layers"]["c_position_digest"]["n_intersection"] == 1

    _, rids, _, _ = _emit(tmp_path, new, spent)
    assert rids == {"tt_sp_2810000001_p2"}


def test_no_overlap_emits_an_empty_list(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::N1"), _p("2810000002", "BOARD::N2"),
    ])
    rc, rids, rep, path = _emit(tmp_path, new, spent)
    assert rc == 0
    assert rids == set()
    assert rep["n_total_excluded"] == 0
    assert path.read_text().startswith("#"), "header written even when empty"


# --------------------------------------------------------------------------- #
# 2. rule (b) — internal duplicates, smallest rid wins                          #
# --------------------------------------------------------------------------- #
def test_rule_b_keeps_the_lexicographically_smallest_rid(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000009", "BOARD::DUP"),     # written FIRST but lexicographically
        _p("2810000004", "BOARD::DUP"),     # ... larger than this one
        _p("2810000005", "BOARD::N5"),
    ])
    rc, rids, rep, _ = _emit(tmp_path, new, spent)
    assert rc == 0
    assert rids == {"tt_sp_2810000009_p2"}, "the SMALLER rid must be kept"
    assert rep["n_internal_dupes"] == 1
    assert rep["n_internal_dupe_digest_groups"] == 1
    assert rep["n_spent_overlap"] == 0


def test_rule_b_file_order_does_not_change_the_survivor(tmp_path, spent):
    """Same two positions, opposite file order — the keep decision is a property
    of the rids, not of who was written first."""
    keep = {}
    for tag, order in (("fwd", [4, 9]), ("rev", [9, 4])):
        new = _write_corpus(tmp_path / f"new_{tag}", [
            _p(f"281000000{i}", "BOARD::DUP") for i in order])
        _, rids, _, _ = _emit(tmp_path, new, spent, name=f"EXCLUDE_{tag}")
        keep[tag] = rids
    assert keep["fwd"] == keep["rev"] == {"tt_sp_2810000009_p2"}


def test_rule_b_drops_all_but_one_of_a_triple(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::DUP"), _p("2810000002", "BOARD::DUP"),
        _p("2810000003", "BOARD::DUP"),
    ])
    _, rids, rep, _ = _emit(tmp_path, new, spent)
    assert rids == {"tt_sp_2810000002_p2", "tt_sp_2810000003_p2"}
    assert rep["n_internal_dupes"] == 2
    assert rep["n_internal_dupe_digest_groups"] == 1


def test_the_two_rules_union_and_report_their_intersection(tmp_path, spent):
    """A board that is BOTH duplicated inside the fresh corpus and present in the
    spent one: rule (a) takes every copy, so the union is 2 while the two rule
    counts are 2 and 1. `n_excluded_by_both_rules` keeps that unambiguous."""
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::S1"), _p("2810000002", "BOARD::S1"),
        _p("2810000003", "BOARD::N3"),
    ])
    _, rids, rep, _ = _emit(tmp_path, new, spent)
    assert rids == {"tt_sp_2810000001_p2", "tt_sp_2810000002_p2"}
    assert rep["n_spent_overlap"] == 2
    assert rep["n_internal_dupes"] == 1
    assert rep["n_excluded_by_both_rules"] == 1
    assert rep["n_total_excluded"] == 2


# --------------------------------------------------------------------------- #
# 3. the exclusions really do close layer (c)                                   #
# --------------------------------------------------------------------------- #
def test_excluding_the_emitted_rids_makes_the_gate_pass(tmp_path, spent):
    positions = [
        _p("2810000001", "BOARD::N1"),
        _p("2810000002", "BOARD::S2"),      # rule (a)
        _p("2810000003", "BOARD::DUP"),
        _p("2810000004", "BOARD::DUP"),     # rule (b)
        _p("2810000005", "BOARD::S4"),      # rule (a)
    ]
    new = _write_corpus(tmp_path / "new", positions)
    _, rids, rep, _ = _emit(tmp_path, new, spent)
    assert rep["n_spent_overlap"] == 2
    assert rep["n_internal_dupes"] == 1
    assert rep["n_total_excluded"] == 3

    rebuilt = _write_corpus(tmp_path / "rebuilt",
                            [p for p in positions if p["rid"] not in rids])
    out = tmp_path / "DISJ2.json"
    rc = GD.main(["--spent-dir", str(spent), "--new-dir", str(rebuilt),
                  "--out", str(out)])
    gate = json.loads(out.read_text())
    assert rc == 0 and gate["passed"] is True
    assert gate["n_layers_violated"] == 0
    c = gate["layers"]["c_position_digest"]
    assert c["n_intersection"] == 0
    assert c["n_new"] == c["n_new_leg_lines"] == len(positions) - 3
    # the report predicted exactly that shape before the rebuild happened
    assert rep["n_new_leg_lines_after_exclusion"] == c["n_new_leg_lines"]
    assert rep["n_new_distinct_digests_after_exclusion"] == c["n_new"]


# --------------------------------------------------------------------------- #
# 4. idempotence                                                                #
# --------------------------------------------------------------------------- #
def test_running_twice_yields_the_same_exclusion_set(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::S1"), _p("2810000002", "BOARD::DUP"),
        _p("2810000003", "BOARD::DUP"), _p("2810000004", "BOARD::N4"),
    ])
    rc1, rids1, rep1, path1 = _emit(tmp_path, new, spent, name="E1")
    rc2, rids2, rep2, path2 = _emit(tmp_path, new, spent, name="E2")
    assert rc1 == rc2 == 0
    assert rids1 == rids2
    assert path1.read_text() == path2.read_text(), "the file rewrites, not appends"
    assert rep1["sha256_excluded_rid_list"] == rep2["sha256_excluded_rid_list"]


def test_rerunning_over_the_already_excluded_corpus_is_a_noop(tmp_path, spent):
    positions = [
        _p("2810000001", "BOARD::S1"), _p("2810000002", "BOARD::DUP"),
        _p("2810000003", "BOARD::DUP"), _p("2810000004", "BOARD::N4"),
    ]
    new = _write_corpus(tmp_path / "new", positions)
    _, rids, _, _ = _emit(tmp_path, new, spent, name="E1")
    rebuilt = _write_corpus(tmp_path / "rebuilt",
                            [p for p in positions if p["rid"] not in rids])
    _, rids2, rep2, _ = _emit(tmp_path, rebuilt, spent, name="E2")
    assert rids2 == set(), "a corpus already free of layer-(c) overlap excludes 0"
    assert rep2["n_total_excluded"] == 0


def test_the_excluded_rid_sha256_is_the_gates_id_list_fingerprint(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::S1"), _p("2810000002", "BOARD::S2"),
    ])
    _, rids, rep, _ = _emit(tmp_path, new, spent)
    assert rep["sha256_excluded_rid_list"] == GD.sha256_of_ids(rids)


# --------------------------------------------------------------------------- #
# 5. disclosure policy + input handling                                         #
# --------------------------------------------------------------------------- #
def test_report_is_counts_only(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::S1"), _p("2810000002", "BOARD::DUP"),
        _p("2810000003", "BOARD::DUP"),
    ])
    _, rids, rep, _ = _emit(tmp_path, new, spent)
    blob = json.dumps(rep)
    for rid in rids | {"tt_sp_2810000002_p2", "tt_sp_2810000001_p2"}:
        assert rid not in blob, f"report leaked the rid {rid!r}"
    for checksum in ("BOARD::S1", "BOARD::DUP", "BOARD::S2"):
        assert checksum not in blob, f"report leaked the checksum {checksum!r}"
        assert EDX.digest_of(checksum) not in blob, "report leaked a digest"
    assert "COUNTS ONLY" in rep["disclosure_policy"]


def test_digest_identity_is_byte_for_byte_the_gates(tmp_path):
    """If the emitter and the gate ever disagreed on the digest, an exclusion
    list could 'fix' a layer the gate still reads as violated."""
    corpus = _write_corpus(tmp_path / "c", [_p("2810000001", "BOARD::X")])
    legs = GD.leg_paths(corpus, EDX.LEG_GLOB)
    gate_digests, n_lines = GD.load_digests(legs)
    pairs = EDX.load_rid_digests(legs)
    assert n_lines == len(pairs) == 1
    assert {d for _, d in pairs} == gate_digests
    assert EDX.digest_of("BOARD::X") == hashlib.sha256(b"BOARD::X").hexdigest()


def test_missing_leg_files_exit_2_not_an_empty_list(tmp_path, spent):
    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "E.txt"
    rc = EDX.main(["--new-dir", str(empty), "--spent-dir", str(spent),
                   "--out", str(out), "--report", ""])
    assert rc == 2
    assert not out.exists(), "no exclusion file may be written on a failed read"


def test_a_leg_line_without_a_rid_exits_2(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [_p("2810000001", "BOARD::N1")])
    (new / "positions_walled_leg1.jsonl").write_text(
        json.dumps({"checksum": "BOARD::N1"}) + "\n")
    rc = EDX.main(["--new-dir", str(new), "--spent-dir", str(spent),
                   "--out", str(tmp_path / "E.txt"), "--report", ""])
    assert rc == 2


def test_emitted_file_parses_the_way_build_positions_parses_it(tmp_path, spent):
    new = _write_corpus(tmp_path / "new", [
        _p("2810000001", "BOARD::S1"), _p("2810000002", "BOARD::N2"),
    ])
    _, rids, _, path = _emit(tmp_path, new, spent)
    text = path.read_text()
    assert text.startswith("#"), "header comment expected (self-documenting)"
    assert _parse_exclude_file(path) == rids
    body = [ln for ln in text.splitlines() if not ln.startswith("#")]
    assert body == sorted(body), "rid list must be sorted"


# --------------------------------------------------------------------------- #
# 6. the driver wires phase 5b in                                               #
# --------------------------------------------------------------------------- #
DRIVER = REPO / "scripts/tiletie/build_tiearb2_corpus.sh"


def test_driver_builds_and_consumes_the_combined_exclusion_list():
    text = DRIVER.read_text()
    assert "emit_digest_exclusions.py" in text
    assert "EXCLUDE_RIDS_all.txt" in text
    assert "EXCLUDE_RIDS_digest.txt" in text
    # the REAL build must consume the combined list, never the spent list alone
    assert 'build_positions_into "$POSITIONS" "$EXCLUDE_ALL"' in text
    # ... and the digest list must come from the throwaway probe, not the corpus
    assert 'build_positions_into "$PROBE" "$EXCLUDE_RIDS"' in text
    assert '--new-dir "$PROBE"' in text


def test_driver_still_hard_codes_no_worker_count():
    text = DRIVER.read_text()
    assert "W_LOCAL" in text and "--workers \"$W_LOCAL\"" in text
    for bad in ("--workers 30", "--workers 14", "--workers 22", "nice -n 19 "):
        assert bad not in text, f"hard-coded {bad!r} in the driver"
