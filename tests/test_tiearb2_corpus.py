#!/usr/bin/env python3
"""tiearb2_20260816 CORPUS ASSEMBLY — unit tests.

Covers, WITHOUT importing the engine, `carcassonne_ai`, numpy or torch:

  * the spent-corpus rid exclusion file (733 rids, exactly the ARMS.json keys)
  * the G-DISJOINT gate's three identity layers, on SYNTHETIC fixtures built to
    isolate each layer (rid-only overlap, root-only overlap, digest-only overlap
    — the last with distinct rids AND distinct roots, so only layer (c) can see
    it), plus the clean case
  * the champ-games seed-band / realized-count assertion
  * the shadow repo root that lets the UNMODIFIED transposition_census.py read a
    champ-games file it has no flag for

The gate's real spent-side inputs are read once (a read-only repo artifact) to
pin the 733 / 399 counts the exclusion list and the gate both depend on.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import gate_disjoint as GD  # noqa: E402
import tiearb2_corpus_lib as LIB  # noqa: E402

SPENT_POOLED = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
SPENT_ARMS = SPENT_POOLED / "ARMS.json"

N_SPENT_RIDS = 733
N_SPENT_ROOTS = 399


# --------------------------------------------------------------------------- #
# synthetic corpus fixtures                                                     #
# --------------------------------------------------------------------------- #
def _write_corpus(root: Path, positions: list[dict]) -> Path:
    """Write a minimal (ARMS.json + positions_walled_leg1.jsonl) corpus.

    `positions` items: {"rid", "root_id", "checksum"}. Mirrors only the fields
    the gate reads — deliberately NOT a full build_positions output, so the test
    cannot accidentally depend on anything else."""
    root.mkdir(parents=True, exist_ok=True)
    arms = {p["rid"]: {"root_id": p["root_id"], "arms": [1, 2]} for p in positions}
    (root / "ARMS.json").write_text(json.dumps(arms, indent=2, sort_keys=True))
    (root / "positions_walled_leg1.jsonl").write_text("".join(
        json.dumps({"rid": p["rid"], "root_id": p["root_id"],
                    "checksum": p["checksum"], "pick_a": 1, "pick_b": 2}) + "\n"
        for p in positions))
    return root


def _pos(tag: str, n: int, *, first: int = 0) -> list[dict]:
    return [{"rid": f"tt_sp_{tag}{i}_p7", "root_id": f"sp_{tag}{i}",
             "checksum": f"BOARD::{tag}::{i}"} for i in range(first, first + n)]


@pytest.fixture()
def spent_dir(tmp_path) -> Path:
    return _write_corpus(tmp_path / "spent", _pos("A", 10))


def _run(tmp_path, spent, new, name="DISJ.json"):
    out = tmp_path / name
    rc = GD.main(["--spent-dir", str(spent), "--new-dir", str(new),
                  "--out", str(out)])
    return rc, (json.loads(out.read_text()) if out.exists() else None)


# --------------------------------------------------------------------------- #
# 1. exclude-rid file generation                                                #
# --------------------------------------------------------------------------- #
def test_spent_arms_has_the_expected_shape():
    """Pins the two counts every downstream assertion is written against."""
    arms = json.loads(SPENT_ARMS.read_text())
    assert len(arms) == N_SPENT_RIDS
    assert len({v["root_id"] for v in arms.values()}) == N_SPENT_ROOTS


def test_emit_exclude_rids_matches_arms_keys_exactly(tmp_path):
    out = tmp_path / "EXCLUDE_RIDS.txt"
    rids = LIB.emit_exclude_rids(SPENT_ARMS, out)
    assert len(rids) == N_SPENT_RIDS
    assert rids == sorted(set(rids)), "rid list must be sorted and duplicate-free"
    assert set(rids) == set(json.loads(SPENT_ARMS.read_text()))


def test_exclude_rids_file_parses_the_way_build_positions_parses_it(tmp_path):
    """`build_positions.load_exclude_rids` strips `#` comments and blank lines —
    re-implemented here so the test needs no engine-adjacent import."""
    out = tmp_path / "EXCLUDE_RIDS.txt"
    LIB.emit_exclude_rids(SPENT_ARMS, out)
    text = out.read_text()
    assert text.startswith("#"), "header comment expected (self-documenting)"
    parsed = {ln.split("#", 1)[0].strip()
              for ln in text.splitlines() if ln.split("#", 1)[0].strip()}
    assert parsed == set(json.loads(SPENT_ARMS.read_text()))
    assert len(parsed) == N_SPENT_RIDS


# --------------------------------------------------------------------------- #
# 2. G-DISJOINT — the three layers                                              #
# --------------------------------------------------------------------------- #
def test_gate_passes_on_fully_disjoint_corpora(tmp_path, spent_dir):
    new = _write_corpus(tmp_path / "new", _pos("B", 12))
    rc, rep = _run(tmp_path, spent_dir, new)
    assert rc == 0
    assert rep["passed"] is True
    assert rep["n_layers_violated"] == 0
    L = rep["layers"]
    assert L["a_root_id"]["n_intersection"] == 0
    assert L["b_rid"]["n_intersection"] == 0
    assert L["c_position_digest"]["n_intersection"] == 0
    assert L["b_rid"]["n_spent"] == 10 and L["b_rid"]["n_new"] == 12
    assert L["c_position_digest"]["n_new_leg_lines"] == 12


def test_gate_fails_on_rid_overlap(tmp_path, spent_dir):
    """A shared rid necessarily shares its root and its board too — all three
    layers must fire, and the exit code must be 1."""
    shared = _pos("A", 2)                       # identical to two spent rows
    new = _write_corpus(tmp_path / "new", shared + _pos("B", 5))
    rc, rep = _run(tmp_path, spent_dir, new)
    assert rc == 1
    assert rep["passed"] is False
    assert rep["n_layers_violated"] == 3
    assert rep["layers"]["b_rid"]["n_intersection"] == 2


def test_gate_fails_on_root_overlap_only(tmp_path, spent_dir):
    """Same GAME, different ply and different board: layers (b) and (c) are
    clean, so only the root layer can catch it. This is the case a naive
    rid-only check would wave through."""
    same_root = [{"rid": "tt_sp_A3_p99", "root_id": "sp_A3",
                  "checksum": "BOARD::NEW::unique"}]
    new = _write_corpus(tmp_path / "new", same_root + _pos("B", 4))
    rc, rep = _run(tmp_path, spent_dir, new)
    assert rc == 1
    L = rep["layers"]
    assert L["a_root_id"]["n_intersection"] == 1
    assert L["b_rid"]["n_intersection"] == 0
    assert L["c_position_digest"]["n_intersection"] == 0
    assert rep["n_layers_violated"] == 1


def test_gate_fails_on_position_digest_overlap_only(tmp_path, spent_dir):
    """The strongest layer: a DIFFERENT game at a DIFFERENT ply that reaches a
    board the spent corpus already scored. rid and root_id are both clean."""
    transposed = [{"rid": "tt_sp_Z9_p41", "root_id": "sp_Z9",
                   "checksum": "BOARD::A::4"}]     # == spent row 4's board
    new = _write_corpus(tmp_path / "new", transposed + _pos("B", 3))
    rc, rep = _run(tmp_path, spent_dir, new)
    assert rc == 1
    L = rep["layers"]
    assert L["a_root_id"]["n_intersection"] == 0
    assert L["b_rid"]["n_intersection"] == 0
    assert L["c_position_digest"]["n_intersection"] == 1
    assert rep["n_layers_violated"] == 1


def test_gate_report_leaks_no_identity_values(tmp_path, spent_dir):
    """Counts only: no rid, root_id, checksum or raw digest may appear."""
    new = _write_corpus(tmp_path / "new", _pos("A", 3) + _pos("B", 3))
    _rc, rep = _run(tmp_path, spent_dir, new)
    blob = json.dumps(rep)
    for forbidden in ("tt_sp_A0_p7", "sp_A0", "BOARD::A::0",
                      hashlib.sha256(b"BOARD::A::0").hexdigest()):
        assert forbidden not in blob, f"{forbidden!r} leaked into the report"


def test_gate_records_both_rid_list_digests(tmp_path, spent_dir):
    new = _write_corpus(tmp_path / "new", _pos("B", 4))
    _rc, rep = _run(tmp_path, spent_dir, new)
    expect_spent = hashlib.sha256(
        "".join(f"tt_sp_A{i}_p7\n" for i in range(10)).encode()).hexdigest()
    assert rep["sha256_spent_rid_list"] == expect_spent
    assert rep["sha256_new_rid_list"] != expect_spent
    # stable + order-independent
    assert GD.sha256_of_ids(["b", "a"]) == GD.sha256_of_ids(["a", "b"])


def test_gate_exits_2_when_an_input_is_missing(tmp_path, spent_dir):
    rc, rep = _run(tmp_path, spent_dir, tmp_path / "does_not_exist")
    assert rc == 2
    assert rep is None, "no report may be written when the gate cannot evaluate"


def test_gate_exits_2_when_a_leg_line_has_no_checksum(tmp_path, spent_dir):
    new = _write_corpus(tmp_path / "new", _pos("B", 2))
    (new / "positions_walled_leg1.jsonl").write_text(
        json.dumps({"rid": "tt_sp_B0_p7", "root_id": "sp_B0"}) + "\n")
    rc, _rep = _run(tmp_path, spent_dir, new)
    assert rc == 2


def test_gate_against_the_real_spent_corpus_is_self_overlapping(tmp_path):
    """Sanity: the spent corpus compared with ITSELF must fail all three layers
    at full size. If this ever passed, the gate would be measuring nothing."""
    rep = GD.run_gate(
        spent_arms=SPENT_ARMS, new_arms=SPENT_ARMS,
        spent_legs=GD.leg_paths(SPENT_POOLED, GD.SPENT_LEG_GLOB),
        new_legs=GD.leg_paths(SPENT_POOLED, GD.NEW_LEG_GLOB))
    assert rep["passed"] is False
    assert rep["layers"]["b_rid"]["n_intersection"] == N_SPENT_RIDS
    assert rep["layers"]["a_root_id"]["n_intersection"] == N_SPENT_ROOTS
    assert rep["layers"]["c_position_digest"]["n_intersection"] == N_SPENT_RIDS
    assert rep["layers"]["c_position_digest"]["n_spent_leg_lines"] == N_SPENT_RIDS


# --------------------------------------------------------------------------- #
# 3. champ-games seed band / realized count                                     #
# --------------------------------------------------------------------------- #
def _champ_games(path: Path, seeds) -> Path:
    path.write_text("".join(
        json.dumps({"deck_seed": s, "actions": [1, 2, 3], "n_plies": 3}) + "\n"
        for s in seeds))
    return path


def test_seed_band_accepts_the_declared_band(tmp_path):
    p = _champ_games(tmp_path / "cg.jsonl",
                     range(LIB.SEED_LO_DEFAULT, LIB.SEED_LO_DEFAULT + 850))
    rep = LIB.verify_champ_games(p, expect_games=850)
    assert rep["n_games_realized"] == 850
    assert rep["band_ok"] and rep["count_ok"]
    assert rep["seed_min_observed"] == LIB.SEED_LO_DEFAULT
    assert rep["seed_max_observed"] == LIB.SEED_HI_DEFAULT
    assert rep["shortfall_vs_expected"] == 0


def test_seed_band_rejects_the_spent_bands_seeds(tmp_path):
    """The old corpus band (28000000xxx) must be refused outright — it is the
    exact contamination this corpus exists to avoid."""
    p = _champ_games(tmp_path / "cg.jsonl",
                     [LIB.SEED_LO_DEFAULT, 28000000000, 28000000449])
    with pytest.raises(ValueError, match="OUTSIDE the declared band"):
        LIB.verify_champ_games(p)


def test_seed_band_rejects_an_off_by_one_above_the_band(tmp_path):
    p = _champ_games(tmp_path / "cg.jsonl", [LIB.SEED_HI_DEFAULT + 1])
    with pytest.raises(ValueError, match="OUTSIDE the declared band"):
        LIB.verify_champ_games(p)


def test_realized_count_below_the_floor_is_refused(tmp_path):
    p = _champ_games(tmp_path / "cg.jsonl",
                     range(LIB.SEED_LO_DEFAULT, LIB.SEED_LO_DEFAULT + 700))
    with pytest.raises(ValueError, match="only 700 games realized"):
        LIB.verify_champ_games(p, expect_games=850, min_games=850)
    # ... but an EXPLICIT lower floor is honoured, and the shortfall is reported
    rep = LIB.verify_champ_games(p, expect_games=850, min_games=650)
    assert rep["n_games_realized"] == 700
    assert rep["shortfall_vs_expected"] == 150
    assert rep["count_ok"] is True


def test_duplicate_seed_is_refused(tmp_path):
    p = _champ_games(tmp_path / "cg.jsonl",
                     [LIB.SEED_LO_DEFAULT, LIB.SEED_LO_DEFAULT])
    with pytest.raises(ValueError, match="duplicated deck_seed"):
        LIB.verify_champ_games(p)


def test_empty_corpus_is_refused(tmp_path):
    p = _champ_games(tmp_path / "cg.jsonl", [])
    with pytest.raises(ValueError, match="ZERO games collected"):
        LIB.verify_champ_games(p)


def test_verify_cli_print_n_emits_only_the_count(tmp_path, capsys):
    p = _champ_games(tmp_path / "cg.jsonl",
                     range(LIB.SEED_LO_DEFAULT, LIB.SEED_LO_DEFAULT + 5))
    rc = LIB.main(["verify-champgames", "--path", str(p), "--min-games", "1",
                   "--print-n", "--out", str(tmp_path / "rep.json")])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "5"
    assert json.loads((tmp_path / "rep.json").read_text())["n_games_realized"] == 5


# --------------------------------------------------------------------------- #
# 4. shadow repo root (the transposition_census.py champ-games workaround)      #
# --------------------------------------------------------------------------- #
def test_shadow_root_relocates_REPO_and_the_champ_games_path(tmp_path):
    cg = _champ_games(tmp_path / "cg.jsonl", [LIB.SEED_LO_DEFAULT])
    shadow = tmp_path / "_shadow_repo"
    entry = LIB.stage_shadow(shadow, champ_games=cg)

    # the entry script IS the real script (same inode), not a copy
    real = REPO / "scripts" / "tiletie" / LIB.SHADOW_ENTRY
    assert os.stat(entry).st_ino == os.stat(real).st_ino
    assert entry.read_text() == real.read_text()

    # ... but its `Path(__file__).resolve().parents[2]` is the SHADOW root
    assert entry.resolve() == entry
    assert entry.resolve().parents[2] == shadow.resolve()

    # ... and that root's champ_games.jsonl is OUR corpus
    linked = shadow / "measurement" / "champ_action_logs" / "champ_games.jsonl"
    assert linked.is_symlink()
    assert linked.resolve() == cg.resolve()
    assert (shadow / "measurement" / "e4_games").is_dir()


def test_shadow_root_imports_resolve_back_to_the_real_repo(tmp_path):
    """build_positions / chain_census / measurement_infra are SYMLINKED, so they
    keep the real repo as their own REPO — only transposition_census's two data
    paths move."""
    cg = _champ_games(tmp_path / "cg.jsonl", [LIB.SEED_LO_DEFAULT])
    shadow = tmp_path / "_shadow_repo"
    LIB.stage_shadow(shadow, champ_games=cg)
    for name in LIB.SHADOW_TILETIE_SYMLINKS:
        p = shadow / "scripts" / "tiletie" / name
        assert p.is_symlink()
        assert p.resolve() == (REPO / "scripts" / "tiletie" / name).resolve()
    mi = shadow / "scripts" / "measurement_infra"
    assert mi.is_symlink()
    assert (mi / "root_replay.py").is_file()


def test_shadow_root_is_rebuilt_from_scratch_each_time(tmp_path):
    cg = _champ_games(tmp_path / "cg.jsonl", [LIB.SEED_LO_DEFAULT])
    shadow = tmp_path / "_shadow_repo"
    LIB.stage_shadow(shadow, champ_games=cg)
    stale = shadow / "scripts" / "tiletie" / "STALE_LEFTOVER.py"
    stale.write_text("# should not survive a restage\n")
    LIB.stage_shadow(shadow, champ_games=cg)
    assert not stale.exists()


def test_shadow_root_refuses_a_missing_champ_games(tmp_path):
    with pytest.raises(FileNotFoundError):
        LIB.stage_shadow(tmp_path / "_shadow_repo",
                         champ_games=tmp_path / "nope.jsonl")


# --------------------------------------------------------------------------- #
# 5. the driver itself                                                          #
# --------------------------------------------------------------------------- #
DRIVER = REPO / "scripts" / "tiletie" / "build_tiearb2_corpus.sh"
WORKERS_CONF = REPO / "measurement" / "tiearb2_20260816" / "WORKERS.conf"


def test_driver_exists_is_executable_and_sources_workers_conf():
    assert DRIVER.is_file() and os.access(DRIVER, os.X_OK)
    text = DRIVER.read_text()
    assert "WORKERS.conf" in text
    assert "$W_LOCAL" in text, "worker count must come from WORKERS.conf"
    assert "nice -n" in text


def test_driver_hard_codes_no_worker_count():
    """The one-line bump W_LOCAL 14 -> 30 must be the ONLY edit needed."""
    import re
    text = DRIVER.read_text()
    assert not re.search(r"--workers\s+\d", text)
    assert "W_LOCAL=" not in text, "W_LOCAL is set in WORKERS.conf, not here"


def test_driver_does_not_self_launch():
    text = DRIVER.read_text()
    for banned in ("setsid nohup scripts", "& disown\n", "crontab", "at now"):
        # the usage comment mentions setsid; assert it is only ever a COMMENT
        for line in text.splitlines():
            if banned.strip() in line:
                assert line.lstrip().startswith("#"), f"self-launch: {line!r}"


def test_driver_passes_the_afterstate_map_explicitly():
    """Its default globs the SPENT 2026-08-12 census dir — relying on the
    default would dedupe the fresh corpus against the wrong map."""
    text = DRIVER.read_text()
    assert "--afterstate-map" in text
    assert "afterstate_map_walled.json" in text
    assert "tiletie_pricing_20260812/census" not in text


def test_workers_conf_defines_what_the_driver_reads():
    text = WORKERS_CONF.read_text()
    for var in ("W_LOCAL=", "NICE=", "SHARE_LOCAL=", "RUN_ID="):
        assert var in text
