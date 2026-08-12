"""Unit tests for the 2026-08-12 overnight chain's python helpers.

Covered (pure parts only — nothing here plays a game, claims a real band, ssh's anywhere
or imports carc_rs):

  scripts/classical_search/chain_capability_probe.py
      parse_doses / cell_tag / cand_leaf_spec / check_split_total / harness_has_flags
  scripts/classical_search/claim_next_band.py
      next_free_band / read_bands / the end-to-end claim against a TEMP registry, incl.
      the sentinel memoization that stops a resume from burning a second band
  scripts/classical_search/menu_block_summary.py
      the 2026-08-12 additions: --expect-cand-leaf-hash and the champ_leaf_hash fallback
      (the gate that catches a candidate arm which silently ran the champion leaf)
  scripts/classical_search/chain_compare_cell_tables.py
      the two-box candidate-leaf agreement gate, plus source-level regression guards on
      denial_simsplit_chain.sh for the 2026-08-12 BLOCKED_D1 post-mortem

The value of these tests is narrow and specific: every one of them guards a failure mode
that produces a CLEAN-LOOKING WRONG NUMBER rather than a crash.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CS = REPO / "scripts" / "classical_search"
sys.path.insert(0, str(CS))

import chain_capability_probe as probe          # noqa: E402
import chain_compare_cell_tables as cellcmp     # noqa: E402
import claim_next_band as claimer               # noqa: E402

CHAMP = "a36d2e15a3b3d71d"
CHAIN_SH = CS / "denial_simsplit_chain.sh"


# --------------------------------------------------------------------------- #
# parse_doses — the "never default to a dose" contract                         #
# --------------------------------------------------------------------------- #
def test_parse_doses_happy():
    assert probe.parse_doses("1.0,2.0") == [1.0, 2.0]
    assert probe.parse_doses(" 0.5 , 1 , 2 , 4 ") == [0.5, 1.0, 2.0, 4.0]


@pytest.mark.parametrize("spec", [None, "", "   ", ","])
def test_parse_doses_refuses_empty(spec):
    with pytest.raises(ValueError):
        probe.parse_doses(spec)


def test_parse_doses_refuses_zero_identity_dose():
    # dose 0.0 == the champion leaf byte-for-byte; its hash could not be distinguished
    # from a silently-default-off candidate, which is the whole failure mode being gated.
    with pytest.raises(ValueError, match="IDENTITY"):
        probe.parse_doses("0")


def test_parse_doses_refuses_dupes_negatives_junk_and_overflow():
    for bad in ("1.0,1.0", "-1", "one", "1,2,3,4,5"):
        with pytest.raises(ValueError):
            probe.parse_doses(bad)
    assert probe.parse_doses("1,2,3,4,5", max_cells=5) == [1.0, 2.0, 3.0, 4.0, 5.0]


# --------------------------------------------------------------------------- #
# cell naming / spec                                                           #
# --------------------------------------------------------------------------- #
def test_cell_tag_is_filesystem_safe_and_carries_both_thresholds():
    t = probe.cell_tag(1.0, 5, 3)
    assert t == "d1_denial_d1_s5_o3"
    assert probe.cell_tag(0.5, 8.0, 2) == "d1_denial_d0p5_s8_o2"
    # two doses at different thresholds must never collide on one directory
    assert probe.cell_tag(1.0, 5, 3) != probe.cell_tag(1.0, 8, 2)
    for ch in "/ .":
        assert ch not in t


def test_cand_leaf_spec_always_writes_thresholds():
    s = probe.cand_leaf_spec(2.0, 8.0, 2)
    assert s == {"denial_dose": 2.0, "denial_size_min": 8.0, "denial_open_max": 2}
    assert json.loads(json.dumps(s)) == s


# --------------------------------------------------------------------------- #
# the fixed-per-turn-total rule for the sims split                             #
# --------------------------------------------------------------------------- #
def test_check_split_total_enforces_two_times_sims():
    ok, msg = probe.check_split_total(2064, 688, 1376)
    assert ok and "2752" in msg
    ok, msg = probe.check_split_total(2064, 700, 1376)
    assert not ok and "confounds" in msg
    ok, _ = probe.check_split_total(2752, 0, 1376)
    assert not ok                      # a zero-sim arm is not a split


def test_harness_has_flags_reads_the_help_text():
    ok, missing = probe.harness_has_flags("... --sims-tile N --sims-meeple N ...",
                                          ["--sims-tile", "--sims-meeple"])
    assert ok and missing == []
    ok, missing = probe.harness_has_flags("--sims N --k-dets N",
                                          ["--sims-tile", "--sims-meeple"])
    assert not ok and missing == ["--sims-tile", "--sims-meeple"]


# --------------------------------------------------------------------------- #
# band claiming                                                                #
# --------------------------------------------------------------------------- #
def test_next_free_band_goes_above_the_high_water_mark():
    existing = {103_000_000_000, 120_000_000_000, 108_000_000_000}
    assert claimer.next_free_band(existing) == 121_000_000_000
    # never fills a GAP below the high-water mark (unregistered probe bands live there)
    assert claimer.next_free_band(existing) not in existing
    assert claimer.next_free_band(set()) == claimer.STEP
    assert claimer.next_free_band({121_000_000_000}, floor=115_000_000_000) == 122_000_000_000


def _mini_registry(tmp_path: Path) -> Path:
    p = tmp_path / "BAND_REGISTRY.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["band_seed_start", "label", "tier", "status", "claimed_date",
                    "decision_influenced", "evidence_or_claim", "notes"])
        w.writerow(["# TIERS: dev = reusable development band", "", "", "", "", "", "", ""])
        w.writerow([120_000_000_000, "prior, with a comma and \"quotes\"", "claim",
                    "retired", "2026-08-10", "yes", "docs/x.md", "notes"])
    return p


def _claim(reg: Path, sentinel: Path, extra=()):
    return subprocess.run(
        [sys.executable, str(CS / "claim_next_band.py"),
         "--label", "D1 - TEST, with a comma", "--notes", 'n "q" ,', "--evidence", "docs/e.md",
         "--registry", str(reg), "--sentinel", str(sentinel), *extra],
        capture_output=True, text=True, check=True)


def test_claim_next_band_appends_one_valid_row_and_is_idempotent(tmp_path):
    reg = _mini_registry(tmp_path)
    sent = tmp_path / "BAND_D1"

    r = _claim(reg, sent)
    band = int(r.stdout.strip().splitlines()[-1])
    assert band == 121_000_000_000
    rows = list(csv.reader(reg.open(newline="")))
    assert len(rows) == 4
    new = rows[-1]
    assert len(new) == 8 and new[0] == "121000000000"
    assert new[2] == "claim" and new[3] == "claimed" and new[5] == "pending"
    assert 'n "q" ,' == new[7]          # csv.writer round-trips the quoting

    # RESUME: a second run must re-use the band and append NOTHING. Burning a band per
    # restart would also split one cell's decks across two bands (forbidden pooling).
    r2 = _claim(reg, sent)
    assert int(r2.stdout.strip().splitlines()[-1]) == band
    assert len(list(csv.reader(reg.open(newline="")))) == 4


def test_claim_next_band_dry_run_touches_nothing(tmp_path):
    reg = _mini_registry(tmp_path)
    sent = tmp_path / "BAND_D1"
    before = reg.read_text()
    r = _claim(reg, sent, extra=("--dry-run",))
    assert "121000000000" in r.stdout
    assert reg.read_text() == before
    assert not sent.exists()


# --------------------------------------------------------------------------- #
# menu_block_summary — the candidate-hash gate                                 #
# --------------------------------------------------------------------------- #
def _cell(tmp_path: Path, cand_hash: str, champ_field="champ_leaf_hash",
          champ_hash=CHAMP) -> Path:
    d = tmp_path / "cell"
    d.mkdir()
    (d / "seed1_a0.json").write_text("{}")
    json.dump({"n": 200, "W": 100, "D": 0, "L": 100, "elo": 0.0,
               "elo_sig_1sigma": 24.0, "paired_z": 0.1, "paired_mean_margin": 0.0},
              (d / "summary.json").open("w"))
    json.dump({"code_rev": "abc", "rules_profile": {"name": "fixed_v1", "r9_env_ok": True},
               "config": {"cand_leaf_hash": cand_hash, champ_field: champ_hash,
                          "paired": True}},
              (d / "manifest.json").open("w"))
    return d


def _summarize(cell: Path, out: Path, expect: str | None):
    args = [sys.executable, str(CS / "menu_block_summary.py"), "--dir", str(cell),
            "--label", "t", "--out", str(out)]
    if expect:
        args += ["--expect-cand-leaf-hash", expect]
    subprocess.run(args, capture_output=True, text=True, check=True)
    return json.loads(out.read_text())


def test_expected_cand_hash_matching_is_clean(tmp_path):
    cell = _cell(tmp_path, "b80f7673fd5abc17")
    got = _summarize(cell, tmp_path / "o.json", "b80f7673fd5abc17")
    assert got["wiring_gates_clean"] is True
    assert got["expected_cand_leaf_hash"] == "b80f7673fd5abc17"
    # the ablation harness names the opponent hash champ_leaf_hash; the fallback must
    # pick it up, otherwise the opponent-side gate is VACUOUS on every such cell
    assert got["wiring"]["opp_leaf_hash"] == CHAMP
    assert got["wiring"]["opp_leaf_hash_field"] == "champ_leaf_hash"


def test_candidate_that_silently_ran_the_champion_leaf_is_caught(tmp_path):
    cell = _cell(tmp_path, CHAMP)                      # knob never reached the leaf
    got = _summarize(cell, tmp_path / "o.json", "b80f7673fd5abc17")
    assert got["wiring_gates_clean"] is False
    assert "READ_BLOCK" in got
    assert any("CHAMPION'S HASH" in g for g in got["wiring_gate_failures"])


def test_hash_gate_is_opt_in(tmp_path):
    cell = _cell(tmp_path, CHAMP)
    got = _summarize(cell, tmp_path / "o.json", None)
    assert got["wiring_gates_clean"] is True           # unchanged for pre-existing callers
    assert "expected_cand_leaf_hash" not in got


# --------------------------------------------------------------------------- #
# chain_compare_cell_tables — the two-box candidate-leaf agreement gate        #
#                                                                             #
# Post-mortem of the 2026-08-12 BLOCKED_D1 false positive. The old gate was    #
#   diff -q $SHARE/d1_cells.tsv $LSHARE/d1_cells.tsv                           #
# run on the LOCAL box, and it was broken twice over:                          #
#   (a) $LSHARE is the LAPTOP's mount prefix — an empty stub locally — so diff #
#       exited 2 on a missing file and the chain reported "hashes disagree"    #
#       about a table it had never read. It could never pass.                  #
#   (b) worse, both prefixes name ONE physical file on the CIFS store, so once #
#       (a) was fixed the gate would compare a file to ITSELF and pass         #
#       unconditionally — vacuous exactly when it mattered.                    #
# Every test below pins one of those two, or the real disagreement the gate    #
# exists to catch.                                                             #
# --------------------------------------------------------------------------- #
ROW_A = "d1_denial_d1_s5_o3\t{\"denial_dose\": 1.0}\teffeca41772e3e78\n"
ROW_B = "d1_denial_d4_s5_o3\t{\"denial_dose\": 4.0}\t451b61ccfa10b29e\n"


def _table(p: Path, text: str) -> Path:
    p.write_text(text)
    return p


def test_cells_gate_passes_on_two_distinct_agreeing_files(tmp_path):
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A + ROW_B)
    b = _table(tmp_path / "d1_cells.laptop.tsv", ROW_A + ROW_B)
    rc, msg = cellcmp.compare_cell_tables(a, b)
    assert rc == cellcmp.RC_OK
    assert "2 cell(s) agree" in msg and "distinct files" in msg


def test_cells_gate_refuses_a_same_file_comparison(tmp_path):
    """THE root cause. One physical file under two names must NEVER read as agreement."""
    a = _table(tmp_path / "d1_cells.tsv", ROW_A + ROW_B)
    b = tmp_path / "laptop_view_of_the_same_file.tsv"
    os.link(a, b)                                  # what $SHARE/x vs $LSHARE/x really is
    rc, msg = cellcmp.compare_cell_tables(a, b)
    assert rc == cellcmp.RC_SAME_FILE
    assert "SAME PHYSICAL FILE" in msg
    # and it must not be rescuable by the contents happening to match
    assert rc != cellcmp.RC_OK


def test_cells_gate_blocks_when_the_remote_table_is_absent(tmp_path):
    """A laptop probe that never ran / never persisted is a BLOCK, not a pass."""
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A)
    rc, msg = cellcmp.compare_cell_tables(a, tmp_path / "d1_cells.laptop.tsv")
    assert rc == cellcmp.RC_REMOTE_MISSING
    assert "MISSING or EMPTY" in msg
    # an empty file is the same story, not a different one
    rc2, _ = cellcmp.compare_cell_tables(a, _table(tmp_path / "empty.tsv", ""))
    assert rc2 == cellcmp.RC_REMOTE_MISSING


def test_cells_gate_blocks_a_stale_remote_table(tmp_path):
    """A table left over from an EARLIER run is not this run's second opinion."""
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A)
    b = _table(tmp_path / "d1_cells.laptop.tsv", ROW_A)
    os.utime(b, (1_000_000, 1_000_000))
    rc, msg = cellcmp.compare_cell_tables(a, b, newer_than=2_000_000)
    assert rc == cellcmp.RC_REMOTE_STALE and "STALE" in msg
    assert cellcmp.compare_cell_tables(a, b, newer_than=500_000)[0] == cellcmp.RC_OK


def test_cells_gate_catches_a_genuine_candidate_leaf_disagreement(tmp_path):
    """The contamination the gate exists for: two boxes, two different candidate leaves."""
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A + ROW_B)
    other = ROW_B.replace("451b61ccfa10b29e", "deadbeefdeadbeef")
    b = _table(tmp_path / "d1_cells.laptop.tsv", ROW_A + other)
    rc, msg = cellcmp.compare_cell_tables(a, b)
    assert rc == cellcmp.RC_DIFFER
    assert "d1_denial_d4_s5_o3" in msg and "deadbeefdeadbeef" in msg
    assert "451b61ccfa10b29e" in msg              # names BOTH sides, no hand re-derivation


def test_cells_gate_catches_a_cell_present_on_only_one_box(tmp_path):
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A + ROW_B)
    b = _table(tmp_path / "d1_cells.laptop.tsv", ROW_A)
    rc, msg = cellcmp.compare_cell_tables(a, b)
    assert rc == cellcmp.RC_DIFFER and "ABSENT on laptop" in msg


def test_cells_gate_is_not_flaky_on_crlf_or_a_missing_trailing_newline(tmp_path):
    """Transport noise across the share must not fake a contamination BLOCK."""
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A + ROW_B)
    b = _table(tmp_path / "d1_cells.laptop.tsv",
               (ROW_A + ROW_B).replace("\n", "\r\n").rstrip("\r\n"))
    assert cellcmp.compare_cell_tables(a, b)[0] == cellcmp.RC_OK


def test_cells_gate_refuses_a_malformed_table_rather_than_calling_it_agreement(tmp_path):
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A)
    b = _table(tmp_path / "d1_cells.laptop.tsv", "d1_denial_d1_s5_o3\tonly-two-fields\n")
    assert cellcmp.compare_cell_tables(a, b)[0] == cellcmp.RC_REMOTE_BAD
    c = _table(tmp_path / "bad_local.tsv", "junk\n")
    assert cellcmp.compare_cell_tables(c, b)[0] == cellcmp.RC_LOCAL_BAD


def test_cells_gate_cli_exit_codes_match_the_library(tmp_path):
    a = _table(tmp_path / "d1_cells.local.tsv", ROW_A)
    b = _table(tmp_path / "d1_cells.laptop.tsv", ROW_A.replace("effeca", "aaaaaa"))
    r = subprocess.run([sys.executable, str(CS / "chain_compare_cell_tables.py"),
                        "--local", str(a), "--remote", str(b)],
                       capture_output=True, text=True)
    assert r.returncode == cellcmp.RC_DIFFER
    assert "[cells-gate] FAIL" in r.stderr
    b.write_text(ROW_A)
    r = subprocess.run([sys.executable, str(CS / "chain_compare_cell_tables.py"),
                        "--local", str(a), "--remote", str(b)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "[cells-gate] PASS" in r.stdout


# --------------------------------------------------------------------------- #
# source-level regression guards on the chain itself                           #
# --------------------------------------------------------------------------- #
def test_chain_compares_two_box_distinct_basenames_under_the_local_prefix():
    """Both halves of the 2026-08-12 bug, pinned in the shell source.

    The comparison runs on the LOCAL box, so every path it is handed must carry the LOCAL
    mount prefix ($OUT), and the two probe outputs must have DIFFERENT basenames or the
    comparison is of one file with itself.
    """
    src = CHAIN_SH.read_text()
    assert "CELLS_PROBE_LOCAL=$OUT/d1_cells.local.tsv" in src
    assert "CELLS_PROBE_LAPTOP_HERE=$OUT/d1_cells.laptop.tsv" in src      # LOCAL prefix
    assert "CELLS_PROBE_LAPTOP_REMOTE=$LOUT/d1_cells.laptop.tsv" in src   # laptop writes
    # the gate is handed the LOCAL-prefix path, never the $LOUT one
    assert '--remote "$CELLS_PROBE_LAPTOP_HERE"' in src
    assert "$CELLS_PROBE_LAPTOP_REMOTE" not in src.split("--remote")[1][:400]
    # the dead byte-diff on the laptop prefix must not come back
    assert 'diff -q "$CELLS_TSV_LOCAL" "$CELLS_TSV_LAPTOP"' not in src


def _laptop_probe_heredoc() -> str:
    src = CHAIN_SH.read_text()
    body = src.split('cat > "$LOGS/_laptop_D1_probe.sh" <<EOF', 1)[1].lstrip("\n")
    return body.split("\nEOF\n", 1)[0]


def test_laptop_probe_script_exports_the_canonical_champion_leaf_env():
    """Without these the laptop hashes curve100, not the champion — every candidate hash it
    derives would belong to a different leaf dialect and the agreement gate would block on a
    difference that is really a missing export."""
    h = _laptop_probe_heredoc()
    for need in ("CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25",
                 "CARCASSONNE_V25_CAP=8", "CARCASSONNE_V25_OPP_CAP=8",
                 "CARCASSONNE_V25_MEEPLE_K=2.0", "CARCASSONNE_USE_FLAT_LEAF=1",
                 "CARCASSONNE_FIX_R9=1"):
        assert need in h, f"laptop probe script lost {need}"
    assert h.splitlines()[0].startswith("cd /home/doctor/projects/carcassone")  # cd on line 1


def test_laptop_probe_persists_its_own_verdict_json():
    """The laptop's evidence must survive as a verdict, not only as a log line."""
    h = _laptop_probe_heredoc()
    assert "--json-out $LAPTOP_JSON_REMOTE" in h
    assert "--cells-out $CELLS_PROBE_LAPTOP_REMOTE" in h
    src = CHAIN_SH.read_text()
    assert 'cp -f "$LAPTOP_JSON_HERE" "$DIR/verdicts/D1_capability_laptop.json"' in src
    assert "left NO verdict JSON" in src            # missing JSON is a hard BLOCK


def test_chain_promotes_the_canonical_cells_table_only_after_the_gate():
    """A run that blocks must leave no d1_cells.tsv for a launcher to pick up."""
    src = CHAIN_SH.read_text()
    gate = src.index("$CELLCMP")
    promote = src.index('cp -f "$CELLS_PROBE_LOCAL" "$CELLS_TSV_LOCAL"')
    launch = src.index('cat > "$LOGS/_laptop_D1.sh"')
    assert gate < promote < launch
    # nothing writes the canonical table before the promotion
    assert '--cells-out "$CELLS_TSV_LOCAL"' not in src
