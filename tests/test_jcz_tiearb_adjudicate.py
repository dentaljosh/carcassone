#!/usr/bin/env python3
"""Unit tests for `measurement/jcz_tiearb_20260817/adjudicate.py` — the MECHANICAL
ADJUDICATOR for the JCZ out-of-lineage pricing of the tie arbiter.

Everything here runs on SYNTHETIC JSONL fixtures built in `tmp_path`: no real
games, no rust, no JVM, no cluster, single-threaded. The point is that each §3
gate can be failed EXACTLY ONE AT A TIME (so a `U-UNREADABLE` names the right
gate), that the §4 branch table fires in its committed order, that `D` / `z_D` are
the arithmetic the read-rule specifies, and that §4.3's companion table — CELL A's
absolute result above all — is printed on `U-UNREADABLE` too.

The healthy fixture is deliberately built to satisfy every gate: 320 decks × 2
seatings × 2 cells (the `G-N` floor), one band, one binary sha, a degenerate
commit range, and a two-sided pre-flight.
"""
from __future__ import annotations

import importlib.util
import json
import math
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ADJ_PATH = REPO / "measurement/jcz_tiearb_20260817/adjudicate.py"

_spec = importlib.util.spec_from_file_location("jcz_tiearb_adjudicate", ADJ_PATH)
adj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adj)


# --------------------------------------------------------------------------- #
# Fixture construction                                                          #
# --------------------------------------------------------------------------- #
BAND = 133_000_000_000
LEAF = "a36d2e15a3b3d71d"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
BINSHA = "a4318fd59d9d8349"
N_DECKS = adj.N_COMMON_FLOOR              # 320 — the G-N deck floor, exactly
FUTURE = time.time() + 3600.0             # every record finishes AFTER the sentinel


def manifest(*, cell_b: bool, leaf=LEAF, rules="fixed_v1", r9="1",
             jcz_rev=None, binsha=BINSHA, commit=COMMIT, tiearb_on_a=False) -> dict:
    """A minimal manifest carrying every witness the §3 gates read, at the
    addresses `scripts/jcz_match/match.py` actually writes them to."""
    m = {
        "schema": "carcassonne-jcz-match/v1",
        "our_git_rev": commit,
        "jcz_git_rev": jcz_rev or adj.WORKERS_CONF_FALLBACK["JCZ_REV"],
        "jcz_jar": adj.WORKERS_CONF_FALLBACK["JCZ_JAR"],
        "jcz_jar_sha256_16": adj.WORKERS_CONF_FALLBACK["JCZ_JAR_SHA256"][:16],
        "jcz_ai_class": adj.WORKERS_CONF_FALLBACK["JCZ_AI_CLASS"],
        "jcz_ai_config": {},
        "tile_set": "basic:2",
        "rules_profile": rules,
        "r9_env": r9,
        "rules_manifest": {"name": rules, "r9_env_ok": True},
        "carc_rs_binary_sha": binsha,
        "cand_leaf_hash": leaf,
        "champion_manifest": {"leaf_hashes": {"harness_leaf_hash": leaf},
                              "code_commit": commit},
    }
    if cell_b or tiearb_on_a:
        m["champ_tiearb"] = {"enabled": True, "B": 16, "J": 4, "mode": "argmax",
                             "salt": "tiearb2-deploy-v1", "eps": 0.0}
    return m


def record(*, deck, seat, margin, cell_b, fired=5, errors=0, real=None,
           counts=None, final_agree=True, **mkw) -> dict:
    margin = int(margin)
    winner = "champ" if margin > 0 else ("jcz" if margin < 0 else "draw")
    r = {
        "schema": "carcassonne-jcz-match/v1",
        "deck_seed": deck, "champ_seat": seat,
        "margin_champ_minus_jcz": margin,
        "champ_score": 70 + margin, "jcz_score": 70,
        "winner": winner, "final_agree": final_agree, "replay_ok": True,
        "void": None, "void_detail": None,
        "real": dict(real or {}), "counts": dict(counts or {}),
        "ms_per_move_champ": 2100.0 if cell_b else 780.0,
        "ms_per_move_jcz": 39.0,
        "wall_secs": 266.0 if cell_b else 98.0,
        "finished_at": FUTURE,
        "moves_by_seat": {"0": 71, "1": 71}, "n_actions": 142,
        "manifest": manifest(cell_b=cell_b, **mkw),
    }
    if cell_b:
        r["champ_tiearb"] = {
            "tile_plies": 36, "fired_plies": fired, "fires": fired,
            "pickchanges": 2, "arms_total": 4 * fired, "playouts_total": 64 * fired,
            "secs": 9.57 * fired, "errors": errors, "first_error": None,
            "partial_argmax": 0, "max_plies": 40, "mode": "argmax", "B": 16, "J": 4}
    return r


def write_cells(tmp_path: Path, *, diffs, n_decks=N_DECKS, band=BAND,
                a_kw=None, b_kw=None, a_rec=None, b_rec=None):
    """Write CELL A / CELL B archives.

    `diffs` is a callable `deck_index -> (a_margin, b_margin)`; both seatings of a
    deck get the same margin, so the per-deck paired observation IS that margin and
    `D` is exactly `mean(b - a)` over decks — hand-checkable.
    """
    a_path, b_path = tmp_path / "cell_a.jsonl", tmp_path / "cell_b.jsonl"
    for path, is_b in ((a_path, False), (b_path, True)):
        lines = []
        for i in range(n_decks):
            ma, mb = diffs(i)
            for seat in (0, 1):
                kw = dict((b_kw or {}) if is_b else (a_kw or {}))
                extra = dict((b_rec or {}) if is_b else (a_rec or {}))
                if extra.get("_first_only") and not (i == 0 and seat == 0):
                    extra = {}
                extra.pop("_first_only", None)
                lines.append(json.dumps(record(
                    deck=band + i, seat=seat, margin=(mb if is_b else ma),
                    cell_b=is_b, **kw, **extra)))
        path.write_text("\n".join(lines) + "\n")
    return a_path, b_path


def write_support(tmp_path: Path, *, band=BAND, commit=COMMIT, binsha=BINSHA,
                  pick_changed=True, bits_unchanged=True):
    """The band sentinel + the `verdicts/PREFLIGHT_<host>_FIRST.json` witness."""
    sentinel = tmp_path / "BAND_CLAIM.txt"
    sentinel.write_text(f"{band}\nJCZ out-of-lineage pricing\nclaimed 2026-08-17\n")
    verdicts = tmp_path / "verdicts"
    verdicts.mkdir(exist_ok=True)
    (verdicts / "PREFLIGHT_testbox_FIRST.json").write_text(json.dumps({
        "kind": "jcz_tiearb_preflight", "host": "testbox",
        "toolchain": {"code_rev": commit}, "carc_rs_binary_sha": binsha,
        "all_preflight_pass": True,
        "two_sided": {"pick_changed": pick_changed,
                      "root_leaf_value_bits_unchanged": bits_unchanged},
    }))
    return sentinel, verdicts


def run(tmp_path, a_path, b_path, sentinel, verdicts, capsys=None):
    """Invoke `main()` exactly as the CLI does, and return `(readout, stdout)`."""
    out_json = tmp_path / "READOUT.json"
    rc = adj.main(["--cell-a", str(a_path), "--cell-b", str(b_path),
                   "--json", str(out_json), "--band-claim", str(sentinel),
                   "--verdicts-dir", str(verdicts), "--run-dir", str(tmp_path),
                   "--repo", str(REPO)])
    assert rc == 0, "exit MUST be 0 on every branch, U-UNREADABLE included"
    stdout = capsys.readouterr().out if capsys is not None else ""
    return json.loads(out_json.read_text()), stdout


def healthy(tmp_path, diffs, **kw):
    a, b = write_cells(tmp_path, diffs=diffs, **kw)
    s, v = write_support(tmp_path)
    return a, b, s, v


# --------------------------------------------------------------------------- #
# 1-3 — the branch table on healthy cells                                       #
# --------------------------------------------------------------------------- #
def test_large_positive_D_is_J_CONFIRMED(tmp_path, capsys):
    # per-deck diff alternates 2 / 4 -> D = 3.0, sd = 1.0, z = 3/(1/sqrt(320)) ~ 53.7
    a, b, s, v = healthy(tmp_path, lambda i: (0, 2 + 2 * (i % 2)))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert out["branch"] == "J-CONFIRMED"
    assert out["D"] == pytest.approx(3.0)
    assert out["z_D"] > 2.0
    assert out["n_common"] == N_DECKS


def test_zero_D_is_J_NULL_BOUNDED(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, lambda i: (0, 1 if i % 2 else -1))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert out["D"] == pytest.approx(0.0)
    assert out["branch"] == "J-NULL-BOUNDED"


def test_large_negative_D_is_J_REVERSED(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, lambda i: (0, -2 - 2 * (i % 2)))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert out["branch"] == "J-REVERSED"
    assert out["D"] == pytest.approx(-3.0)
    assert out["z_D"] <= -2.0


def test_J_SIGN_fires_between_1_and_2_sigma(tmp_path, capsys):
    """A `z_D` in `[+1.0, +2.0)` must select `J-SIGN`, not `J-CONFIRMED`."""
    # spread chosen so mean stays +1 while sd is large enough to hold z under 2.
    a, b, s, v = healthy(tmp_path, lambda i: (0, 13 if i % 2 else -11))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == []
    assert 1.0 <= out["z_D"] < 2.0, out["z_D"]
    assert out["branch"] == "J-SIGN"


# --------------------------------------------------------------------------- #
# 5 — the arithmetic, hand-checked                                              #
# --------------------------------------------------------------------------- #
def test_D_and_z_D_are_hand_checkable(tmp_path, capsys):
    """4 decks, per-deck diffs 1/2/3/4.

        D    = 2.5
        var  = ((1.5)^2+(0.5)^2+(0.5)^2+(1.5)^2)/3 = 5/3
        se   = sqrt((5/3)/4) = 0.6454972243679028
        z_D  = 2.5 / 0.6454972243679028 = 3.872983346207417
    """
    a, b = write_cells(tmp_path, diffs=lambda i: (0, i + 1), n_decks=4)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["n_common"] == 4
    assert out["D"] == pytest.approx(2.5)
    assert out["se_D"] == pytest.approx(math.sqrt((5.0 / 3.0) / 4.0))
    assert out["z_D"] == pytest.approx(3.872983346207417)
    # the §1 recomputation witness must agree, and G-WITNESS must therefore pass
    assert out["preconditions"]["G-WITNESS"] is True
    assert out["z_D_witness"]["recomputed"]["z_D"] == pytest.approx(out["z_D"])
    # n that would resolve D to 2 sigma at the realized dispersion: 4*(2/3.873)^2 -> 2
    assert out["D_block"]["n_to_resolve_D_2sigma_decks"] == 2
    # ...and this run is SHORT, so it is U-UNREADABLE via G-N, not adjudicated
    assert out["branch"] == "U-UNREADABLE"
    assert "G-N" in out["failed_preconditions"]


def test_naive_difference_is_reported_as_a_diagnostic(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, lambda i: (0, 2 + 2 * (i % 2)))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["D_block"]["naive_summary_difference_DIAGNOSTIC"] == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# 4 — each gate failing INDIVIDUALLY                                            #
# --------------------------------------------------------------------------- #
def _flat(i):
    """The healthy per-deck margins: CELL A flat at 0, CELL B alternating 2/4 —
    `D` = +3.0 with sd 1.0, which convicts comfortably at n = 320 decks."""
    return (0, 2 + 2 * (i % 2))


def test_healthy_fixture_passes_every_gate(tmp_path, capsys):
    """The control for every negative test below: if this ever fails, the gate
    tests are not isolating anything."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"] == {g: True for g in adj.ALL_GATES}, \
        out["failed_preconditions"]


def test_G_BAND_fails_on_a_wrong_band(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, band=BAND)
    s, v = write_support(tmp_path, band=BAND + 5_000_000_000)   # sentinel disagrees
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["branch"] == "U-UNREADABLE"
    assert out["failed_preconditions"] == ["G-BAND"]
    assert out["precondition_detail"]["G-BAND"]["record_deck_sets_agree_with_band"] \
        is False


def test_G_BAND_fails_when_the_sentinel_postdates_game_1(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, _flat)
    import os
    os.utime(s, (FUTURE + 10_000, FUTURE + 10_000))
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-BAND"]
    assert out["precondition_detail"]["G-BAND"]["claimed_before_game_1"] is False


def test_G_LEAF_fails_on_a_wrong_leaf_hash(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"leaf": "deadbeefdeadbeef"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-LEAF"]
    obs = out["precondition_detail"]["G-LEAF"]["observed"][out["cell_b"]]
    assert obs["cand_leaf_hash"] == "deadbeefdeadbeef"
    assert obs["resolved_at"] == "cand_leaf_hash"       # the address is REPORTED


def test_G_LEAF_resolves_the_harness_native_address(tmp_path, capsys):
    """With no top-level `cand_leaf_hash`, the gate must resolve the hash where
    `match.py` actually writes it — and say so in `resolved_at`."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        lines = []
        for line in p.read_text().splitlines():
            r = json.loads(line)
            r["manifest"].pop("cand_leaf_hash")
            lines.append(json.dumps(r))
        p.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-LEAF"] is True
    assert (out["precondition_detail"]["G-LEAF"]["observed"][out["cell_a"]]
            ["resolved_at"] == "champion_manifest.leaf_hashes.harness_leaf_hash")


def test_G_ARB_fails_when_CELL_A_carries_a_champ_tiearb_key(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, a_kw={"tiearb_on_a": True})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-ARB"]
    assert out["precondition_detail"]["G-ARB"]["cell_a"][
        "champ_tiearb_addresses_found"] == ["manifest.champ_tiearb"]


def test_G_ARB_fails_on_an_unauthorized_rung(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = []
    for line in b.read_text().splitlines():
        r = json.loads(line)
        r["manifest"]["champ_tiearb"]["B"] = 32        # ⛔ B may not be expanded
        r["champ_tiearb"]["B"] = 32
        lines.append(json.dumps(r))
    b.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-ARB"]
    assert out["precondition_detail"]["G-ARB"]["cell_b"]["checks"]["B"]["ok"] is False


def test_G_FIRE_fails_below_the_phi_effective_floor(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_rec={"fired": 0})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-FIRE"]
    assert out["precondition_detail"]["G-FIRE"]["phi_effective"] == 0.0


def test_G_FIRE_binds_on_phi_effective_not_raw_phi(tmp_path, capsys):
    """The inert surface §0.B describes: fires every ply, errors on every one."""
    a, b = write_cells(tmp_path, diffs=_flat, b_rec={"fired": 5, "errors": 5})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    det = out["precondition_detail"]["G-FIRE"]
    assert det["phi"] == pytest.approx(5.0)             # raw phi clears the floor
    assert det["phi_effective"] == pytest.approx(0.0)   # ...the effective rate does not
    assert "G-FIRE" in out["failed_preconditions"]


def test_G_J13_fails_when_the_positive_control_is_one_sided(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    s, v = write_support(tmp_path, pick_changed=False)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-J13"]


def test_G_J13_fails_when_absent(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    s, v = write_support(tmp_path)
    for f in v.glob("PREFLIGHT_*"):
        f.unlink()
    out, _ = run(tmp_path, a, b, s, v, capsys)
    # the pre-flight also supplies G-TOOL's commit-range witness, so both fail:
    # ABSENT IS FAIL, in both gates, which is the fail-closed posture.
    assert "G-J13" in out["failed_preconditions"]
    assert out["branch"] == "U-UNREADABLE"


def test_G_RULES_fails_with_r9_off(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"r9": "0"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-RULES"]


def test_G_DIVERGE_fails_on_one_REAL_divergence(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat,
                       b_rec={"real": {"SCORE_MISMATCH": 1}, "_first_only": True})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-DIVERGE"]
    assert out["divergence_ledger"][out["cell_b"]]["REAL"] == {"SCORE_MISMATCH": 1}


def test_G_DIVERGE_tolerates_the_two_classified_benign_classes(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat,
                       b_rec={"counts": {"WALL_LEGALITY": 1,
                                         "UNPLACEABLE_REDRAW": 3}})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["preconditions"]["G-DIVERGE"] is True
    assert out["branch"] == "J-CONFIRMED"


def test_G_JCZ_fails_on_a_different_jcz_revision(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"jcz_rev": "f" * 40})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-JCZ"]
    assert out["precondition_detail"]["G-JCZ"]["identical_across_cells"] is False


def test_G_TOOL_fails_when_the_binary_sha_differs_across_cells(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"binsha": "ffffffffffffffff"})
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-TOOL"]
    det = out["precondition_detail"]["G-TOOL"]["same_box_binary_sha"]
    assert det["equal_across_cells"] is False


def test_G_TOOL_passes_on_a_degenerate_commit_range(tmp_path, capsys):
    """READ_RULE §3.1: a healthy run of this launcher produces a DEGENERATE range
    (pre-flight and manifest at the same commit) and MUST pass. Stage 2 lost an
    adjudication to a version of this conjunct that fired on every healthy run."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    cr = out["precondition_detail"]["G-TOOL"]["commit_range"]
    assert cr["empty"] is True and cr["resolved"] is True
    assert "DEGENERATE" in cr["reason"]
    assert out["preconditions"]["G-TOOL"] is True


def test_G_TOOL_voids_on_an_unresolved_commit_range(tmp_path, capsys):
    """A manifest commit that does not parse is UNRESOLVED, and unresolved VOIDS —
    it is not treated as 'nothing changed'."""
    a, b = write_cells(tmp_path, diffs=_flat)
    for p in (a, b):
        lines = []
        for line in p.read_text().splitlines():
            r = json.loads(line)
            r["manifest"]["our_git_rev"] = "not-a-commit"
            r["manifest"]["champion_manifest"]["code_commit"] = "not-a-commit"
            lines.append(json.dumps(r))
        p.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert "G-TOOL" in out["failed_preconditions"]
    assert out["precondition_detail"]["G-TOOL"]["commit_range"]["resolved"] is False


def test_G_N_fails_below_the_deck_floor(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, n_decks=N_DECKS - 1)
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-N"]
    assert out["precondition_detail"]["G-N"]["n_common"] == N_DECKS - 1
    assert out["precondition_detail"]["G-N"]["n_common_floor"] == 320


def test_G_PLY_fails_when_the_ply_witness_is_absent(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = []
    for line in b.read_text().splitlines():
        r = json.loads(line)
        r["champ_tiearb"].pop("partial_argmax")   # absent is unknown-not-zero
        lines.append(json.dumps(r))
    b.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-PLY"]


def test_G_PLY_fails_on_a_nonzero_partial_argmax(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat)
    lines = []
    for i, line in enumerate(b.read_text().splitlines()):
        r = json.loads(line)
        if i == 0:
            r["champ_tiearb"]["partial_argmax"] = 1   # CRN pairing broken in play
        lines.append(json.dumps(r))
    b.write_text("\n".join(lines) + "\n")
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["failed_preconditions"] == ["G-PLY"]


def test_missing_archive_is_U_UNREADABLE_and_still_exits_zero(tmp_path, capsys):
    a, b, s, v = healthy(tmp_path, _flat)
    out, stdout = run(tmp_path, a, tmp_path / "does_not_exist.jsonl", s, v, capsys)
    assert out["branch"] == "U-UNREADABLE"
    assert "CELL A" in stdout


# --------------------------------------------------------------------------- #
# 6 — §4.3's companion table is printed on U-UNREADABLE too                      #
# --------------------------------------------------------------------------- #
def test_companion_table_is_printed_on_U_UNREADABLE(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_kw={"leaf": "deadbeefdeadbeef"})
    s, v = write_support(tmp_path)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["branch"] == "U-UNREADABLE"
    # ⭐ item 7 — CELL A's absolute result, and the 2026-08-09 reading beside it
    assert "CELL A's ABSOLUTE RESULT vs JCZ" in stdout
    assert "+111.4" in stdout and "0.655" in stdout
    assert "1.8-2.2" in stdout and "REGRESSION TRIPWIRE" in stdout
    # the other seven items
    for item in ("item 1", "item 2", "item 3", "item 4", "item 5", "item 6",
                 "item 8"):
        assert f"§4.3 {item}" in stdout, item
    # item 4 — the §0.C field-name trap, named, with the fields printed
    assert "FIELD-NAME TRAP" in stdout
    assert "ms_per_move_champ" in stdout and "ms_per_move_jcz" in stdout
    assert "2.71" in stdout and "266" in stdout        # DESIGN §6.2's prediction
    # item 8 — the two classified-benign classes named
    assert "WALL_LEGALITY" in stdout and "UNPLACEABLE_REDRAW" in stdout
    # the failed gate is named with its realized value
    assert "G-LEAF" in stdout and "deadbeefdeadbeef" in stdout


def test_dilution_statement_is_verbatim_when_errors_are_nonzero(tmp_path, capsys):
    a, b = write_cells(tmp_path, diffs=_flat, b_rec={"fired": 20, "errors": 1})
    s, v = write_support(tmp_path)
    out, stdout = run(tmp_path, a, b, s, v, capsys)
    assert out["dilution"]["statement_required"] is True
    assert "The bias runs toward the champion, so a" in stdout
    assert "lower bound" in stdout


def test_readout_json_carries_the_re_adjudication_keys(tmp_path, capsys):
    """The orchestrating session re-adjudicates BLIND by reading `branch` and
    `failed_preconditions` out of READOUT.json without rendering the statistics —
    so those keys, and every gate's {PASS, realized}, must be there."""
    a, b, s, v = healthy(tmp_path, _flat)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    for k in ("branch", "failed_preconditions", "D", "se_D", "z_D", "n_common",
              "cells", "preconditions", "precondition_detail"):
        assert k in out, k
    assert set(out["preconditions"]) == set(adj.ALL_GATES)
    assert out["D_block"]["n_to_resolve_D_2sigma_decks"] is not None
    for cell in out["cells"].values():
        for k in ("elo", "win_rate", "paired_margin_mean", "paired_margin_sem",
                  "paired_margin_z", "ms_ratio", "worker_s_per_game"):
            assert k in cell, k


# --------------------------------------------------------------------------- #
# Unit-level checks on the pieces                                               #
# --------------------------------------------------------------------------- #
def test_deck_pairing_matches_the_jcz_analyzer(tmp_path):
    """`per_deck_balanced` must reproduce `scripts/jcz_match/analyze.py`'s own
    `paired_margin_mean` / `n_paired_decks` — the deck pairing is never a variant."""
    a, _ = write_cells(tmp_path, diffs=lambda i: (i % 7 - 3, 0), n_decks=20)
    mod, prov = adj._import_jcz_analyze(REPO)
    assert prov["imported"] is True, prov
    recs = mod.load(a)
    summary = mod.analyze(recs)
    mine = adj.per_deck_balanced([r for r in recs if not r.get("void")])
    assert len(mine) == summary["n_paired_decks"]
    assert (sum(mine.values()) / len(mine)) == pytest.approx(
        summary["paired_margin_mean"])


def test_half_pair_decks_are_dropped(tmp_path, capsys):
    """A deck with only one seating is not seat-balanced and must not enter `D`."""
    a, b = write_cells(tmp_path, diffs=_flat, n_decks=10)
    lines = b.read_text().splitlines()
    b.write_text("\n".join(lines[:-1]) + "\n")     # drop one seating of the last deck
    s, v = write_support(tmp_path)
    out, _ = run(tmp_path, a, b, s, v, capsys)
    assert out["n_common"] == 9


def test_paired_stats_is_the_eval_fair_puct_convention():
    mean, se, z, n = adj.paired_stats([1.0, 2.0, 3.0, 4.0])
    assert (mean, n) == (2.5, 4)
    assert se == pytest.approx(math.sqrt((5.0 / 3.0) / 4.0))
    assert z == pytest.approx(2.5 / se)
    assert adj.paired_stats([1.0]) == (None, None, None, 1)


def test_n_to_reach_uses_absolute_z_and_refuses_zero():
    assert adj.n_to_reach(400, 4.0) == 100
    assert adj.n_to_reach(400, -4.0) == 100      # a negative D is resolved by J-REVERSED
    assert adj.n_to_reach(400, 0.0) is None
    assert adj.n_to_reach(400, float("nan")) is None
    assert adj.n_to_reach(0, 4.0) is None


def test_workers_conf_is_parsed_not_hard_coded():
    conf, meta = adj.parse_workers_conf(
        REPO / "measurement/jcz_tiearb_20260817/WORKERS.conf")
    assert meta["parsed"] is True
    assert conf["CHAMP_LEAF_HASH"] == LEAF
    assert conf["CELL_A"] == "jcz_CHAMP_deploy11008"
    assert conf["CELL_B"] == "jcz_ARB_B16J4_deploy11008"
    assert conf["TIEARB_B"] == "16" and conf["TIEARB_J"] == "4"
    assert conf["RUN_DIR"].endswith("measurement/jcz_tiearb_20260817")   # $VAR expanded


def test_workers_conf_fallback_is_flagged(tmp_path):
    conf, meta = adj.parse_workers_conf(tmp_path / "nope.conf")
    assert meta["parsed"] is False and "error" in meta
    assert conf["CHAMP_LEAF_HASH"] == LEAF        # the documented literal


def test_branch_order_puts_U_UNREADABLE_first():
    gates = {g: {"PASS": True} for g in adj.ALL_GATES}
    assert adj.decide_branch(gates, 5.0, 9.0)["branch"] == "J-CONFIRMED"
    bad = dict(gates, **{"G-BAND": {"PASS": False}})
    got = adj.decide_branch(bad, 5.0, 9.0)
    assert got["branch"] == "U-UNREADABLE" and got["failed_preconditions"] == ["G-BAND"]


def test_no_branch_matched_is_explicit_not_silent():
    gates = {g: {"PASS": True} for g in adj.ALL_GATES}
    got = adj.decide_branch(gates, None, float("nan"))
    assert got["branch"] == "U-UNREADABLE"
    assert got["no_branch_matched"] is True
    assert "no_branch_matched" in got or got["failed_preconditions"] == ["NO-BRANCH"]


def test_z_witness_disagreement_voids():
    ok, realized = adj.gate_witness({"D": 1.0, "se_D": 0.5, "z_D": 2.0, "n_common": 10},
                                    {"D": 1.0, "se_D": 0.5, "z_D": 2.5, "n_common": 10})
    assert ok is False
    assert realized["fields"]["z_D"]["agree"] is False
    ok2, _ = adj.gate_witness({"D": 1.0, "se_D": 0.5, "z_D": 2.0, "n_common": 10},
                              {"D": 1.0, "se_D": 0.5, "z_D": 2.0 + 1e-15,
                               "n_common": 10})
    assert ok2 is True
