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

The value of these tests is narrow and specific: every one of them guards a failure mode
that produces a CLEAN-LOOKING WRONG NUMBER rather than a crash.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CS = REPO / "scripts" / "classical_search"
sys.path.insert(0, str(CS))

import chain_capability_probe as probe          # noqa: E402
import claim_next_band as claimer               # noqa: E402

CHAMP = "a36d2e15a3b3d71d"


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
