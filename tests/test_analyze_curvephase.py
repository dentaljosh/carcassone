"""Tests for the PRE-REGISTERED Part-C beta-ladder analysis.

Script under test: scripts/classical_search/analyze_curvephase.py
Prereg (binding):  measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part C
                   (+ AMENDMENT 1 wiring gate, AMENDMENT 2 review fixes)

Fixtures reproduce the REAL emitter's on-disk shape, copied field-for-field from a real
`eval_fair_puct` cell (the voided band-1.15e11 `cp_b0p0`): per-game records at
``seed<band+i>_a<seat>.json`` carrying seed / a_seat / score_p0 / score_p1 / diff, a
``summary.json`` carrying n / elo / elo_sig_1sigma / paired_z / paired_mean_margin /
n_paired, and a ``manifest.json`` whose provenance lives at ``rules_profile.{name,r9_env_ok}``,
``config.backend.name``, ``config.band_seed_start``, ``config.cand_leaf_hash`` and
``config.cand_leaf_cfg.v29_phase_beta``.

Covered, in the order the review named them:
  (a) SIGN CONVENTION — `diff` is ALREADY candidate-minus-opponent, so a candidate that is
      +delta better in BOTH seatings must yield a per-deck margin of +delta and, when delta
      scales with beta, a POSITIVE fitted slope. Under the 2026-08-10 double flip this reads
      ~0 by construction; the test asserts the fixed behaviour and pins the old bug's value.
  (b) the AMENDMENT-1 gate: |paired margin z| < 2.0 AND |elo| < 50, margin z primary.
  (c) manifest enforcement (prereg §6.2/§8) happy and sad paths.
  (d) the mean_margin_recomputed vs paired_mean_margin tripwire.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CS = REPO / "scripts" / "classical_search"
SCRIPT = CS / "analyze_curvephase.py"

sys.path.insert(0, str(CS))
_spec = importlib.util.spec_from_file_location("analyze_curvephase", SCRIPT)
az = importlib.util.module_from_spec(_spec)
sys.modules["analyze_curvephase"] = az
_spec.loader.exec_module(az)

BAND = 116_000_000_000
PROD = az.PROD_LEAF_HASH


# --------------------------------------------------------------------------- #
# fixture builders (mirror the real emitter's layout)                          #
# --------------------------------------------------------------------------- #
def _paired_stats(decks):
    """The harness's own `_paired_z`: mean/z of the per-deck seat-balanced `diff`."""
    ds = [(d0 + d1) / 2.0 for d0, d1 in decks.values()]
    mean = sum(ds) / len(ds)
    if len(ds) < 2:
        return mean, float("nan"), len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    return mean, (mean / se if se > 0 else float("nan")), len(ds)


def write_cell(root: Path, cell: str, beta: float, decks: dict, *,
               prefix: str = "cp_", band: int = BAND, n_expected: int = 200,
               elo: float | None = None, paired_z: float | None = None,
               paired_mean_margin: float | None = None,
               rules_profile: str = "fixed_v1", r9_env_ok: bool = True,
               backend: str = "rust", cand_leaf_hash: str | None = None,
               manifest_beta: float | None = None,
               write_summary: bool = True, write_manifest: bool = True,
               n_games: int | None = None) -> Path:
    """`decks` maps deck seed-offset -> (diff_at_seat0, diff_at_seat1).

    `diff` is the CANDIDATE-MINUS-OPPONENT margin the harness emits directly — the
    fixtures store exactly what `eval_fair_puct._save` would write, no flip.
    """
    d = root / f"{prefix}{cell}"
    d.mkdir(parents=True, exist_ok=True)
    if cand_leaf_hash is None:
        # distinct per SIGNED beta — the ladder is bracketed, so +0.3 and -0.3 are two cells
        cand_leaf_hash = (PROD if beta == 0.0 else
                          f"{'beef' if beta > 0 else 'feed'}beef{int(abs(beta) * 100):04d}bee")
    if manifest_beta is None:
        manifest_beta = beta

    for i, (off, (d0, d1)) in enumerate(sorted(decks.items())):
        seed = band + int(off)
        for seat, diff in ((0, d0), (1, d1)):
            # score_p0/score_p1 are reconstructed so that the emitter's own
            # `diff = (s0-s1) if a_seat==0 else (s1-s0)` holds exactly.
            base = 100
            s0, s1 = ((base + diff, base) if seat == 0 else (base, base + diff))
            (d / f"seed{seed}_a{seat}.json").write_text(json.dumps({
                "seed": seed, "a_seat": seat, "info": "fair", "exact_k": 2,
                "k_dets": 8, "sims": 1376, "rung_sims": 800,
                "score_p0": int(s0), "score_p1": int(s1), "diff": int(diff),
                "won_by_champ": diff > 0, "drew": diff == 0,
                "elapsed_s": 1.0, "moves": 142, "deck_hash": f"{seed:016x}",
                "opponent": "fair-champion",
            }))

    if write_summary:
        mean, z, npair = _paired_stats(decks)
        n = n_games if n_games is not None else 2 * len(decks)
        (d / "summary.json").write_text(json.dumps({
            "info": "fair", "exact_k": 2, "k_dets": 8, "sims": 1376,
            "opponent": "fair-champion", "n": n,
            "W": sum(1 for v in decks.values() for x in v if x > 0),
            "D": sum(1 for v in decks.values() for x in v if x == 0),
            "L": sum(1 for v in decks.values() for x in v if x < 0),
            "elo": 0.0 if elo is None else elo,
            "elo_sig_1sigma": 24.6,
            "avg_diff": mean,
            "paired_mean_margin": mean if paired_mean_margin is None else paired_mean_margin,
            "paired_z": z if paired_z is None else paired_z,
            "n_paired": npair,
        }))

    if write_manifest:
        (d / "manifest.json").write_text(json.dumps({
            "kind": "eval_fair_puct", "game": "base", "code_rev": "testrev",
            "rules_profile": {"name": rules_profile, "r9_env_ok": r9_env_ok,
                              "r9_env_expected": True},
            "config": {
                "info": "fair",
                "champion": {"leaf_cfg": {"v29_phase_beta": manifest_beta,
                                          "v29_phase_norm": 1.0}},
                "band_seed_start": band, "seed_start": band,
                "n": n_expected, "paired": True,
                "cand_leaf_hash": cand_leaf_hash,
                "cand_leaf_cfg": {"v29_phase_beta": manifest_beta,
                                  "v29_phase_norm": 1.0},
                "opp_leaf_hash": PROD,
                "backend": {"name": backend, "requested": backend},
            },
        }))
    return d


def flat(beta, deck):
    """A β-flat ladder with real deck noise.

    An all-zero ladder has zero residual variance, so both the cluster-robust SE and the
    harness's paired z come out NaN and every gate reads "broken" for the wrong reason.
    This generator keeps the fitted slope at ~0 while giving each cell a finite paired z.
    """
    v = ((deck * 37) % 11) - 5 + ((deck * 7 + int(round(beta * 10)) * 3) % 5) - 2
    return (v, v)


def full_ladder(root: Path, margin_for, **kw):
    """Write all five cells. `margin_for(beta, deck)` -> (diff_seat0, diff_seat1)."""
    for cell, beta in az.CELLS.items():
        decks = {i: margin_for(beta, i) for i in range(1, 11)}
        write_cell(root, cell, beta, decks, **kw.get(cell, {}))
    return root


def run(root: Path, n_expected: int = 20, prefix: str = "cp_"):
    cells = az.collect(root, prefix, n_expected)
    for c in cells:
        az.check_tripwire(c["cell"], c.get("mean_margin_recomputed"),
                          c.get("paired_mean_margin"))
    return cells


def analyze(root: Path, n_expected: int = 20, monkeypatch=None, capsys=None):
    """Drive main() the way the launcher does, and return the parsed readout."""
    out = root / "readout.json"
    argv = ["analyze_curvephase.py", "--run-root", str(root),
            "--n-expected", str(n_expected), "--out", str(out)]
    old = sys.argv
    sys.argv = argv
    try:
        az.main()
    finally:
        sys.argv = old
    return json.loads(out.read_text())


# --------------------------------------------------------------------------- #
# (a) SIGN CONVENTION                                                          #
# --------------------------------------------------------------------------- #
class TestSignConvention:
    def test_candidate_better_in_both_seatings_reads_positive(self, tmp_path):
        """+delta in BOTH seatings must give a per-deck margin of +delta, not 0."""
        delta = 6
        write_cell(tmp_path, "b0p0", 0.0, {i: (delta, delta) for i in range(1, 11)})
        dm = az.deck_margins(tmp_path / "cp_b0p0")
        assert len(dm) == 10
        assert all(m == pytest.approx(delta) for m in dm.values())

    def test_old_double_flip_would_read_zero(self, tmp_path):
        """Pin the bug: the retired `diff * (+1 if a_seat==0 else -1)` cancels the effect."""
        delta = 6
        write_cell(tmp_path, "b0p0", 0.0, {i: (delta, delta) for i in range(1, 11)})
        per = {}
        for f in (tmp_path / "cp_b0p0").glob("seed*.json"):
            g = json.loads(f.read_text())
            per.setdefault(g["seed"], {})[g["a_seat"]] = (
                float(g["diff"]) * (1.0 if g["a_seat"] == 0 else -1.0))
        old = {s: (v[0] + v[1]) / 2.0 for s, v in per.items()}
        assert all(m == pytest.approx(0.0) for m in old.values())

    def test_slope_is_positive_when_delta_scales_with_beta(self, tmp_path):
        """margin = 10*beta in both seatings of every deck => fitted slope = +10."""
        full_ladder(tmp_path, lambda beta, deck: (10 * beta, 10 * beta))
        cells = run(tmp_path)
        pts = [(s, c["beta"], m) for c in cells
               for s, m in az.deck_margins(tmp_path / f"cp_{c['cell']}").items()]
        fit = az.fit_within_deck_slope(pts)
        assert fit["slope"] == pytest.approx(10.0)
        assert fit["n_decks"] == 10

    def test_slope_is_negative_for_a_negative_dose_response(self, tmp_path):
        # 10 keeps every dose an exact integer (`diff` is an int field on the wire).
        full_ladder(tmp_path, lambda beta, deck: (-10 * beta, -10 * beta))
        pts = [(s, b, m) for cell, b in az.CELLS.items()
               for s, m in az.deck_margins(tmp_path / f"cp_{cell}").items()]
        assert az.fit_within_deck_slope(pts)["slope"] == pytest.approx(-10.0)


# --------------------------------------------------------------------------- #
# (b) AMENDMENT-1 WIRING GATE                                                  #
# --------------------------------------------------------------------------- #
class TestAmendedGate:
    def _ladder_with_identity(self, tmp_path, elo, paired_z):
        """Flat ladder whose identity cell reports the given (elo, paired margin z)."""
        full_ladder(tmp_path, flat,
                    b0p0={"elo": elo, "paired_z": paired_z})
        return analyze(tmp_path)

    def test_large_margin_z_breaks_the_instrument_even_at_small_elo(self, tmp_path):
        r = self._ladder_with_identity(tmp_path, elo=10.0, paired_z=2.5)
        assert r["identity_gate"] == "INSTRUMENT-BROKEN"
        assert r["verdict"] == "INSTRUMENT-BROKEN"

    def test_elo_30_with_small_margin_z_passes_the_amended_gate(self, tmp_path):
        """The retired |elo| < 25 bar would have false-fired here — AMENDMENT 1's point."""
        r = self._ladder_with_identity(tmp_path, elo=30.0, paired_z=0.5)
        assert r["identity_gate"] == "OK"
        assert r["verdict"] != "INSTRUMENT-BROKEN"

    def test_elo_60_breaks_the_instrument(self, tmp_path):
        r = self._ladder_with_identity(tmp_path, elo=60.0, paired_z=0.5)
        assert r["identity_gate"] == "INSTRUMENT-BROKEN"
        assert r["verdict"] == "INSTRUMENT-BROKEN"

    def test_gate_bounds_are_the_amended_ones(self):
        assert (az.GATE_MARGIN_Z, az.GATE_ELO) == (2.0, 50.0)


# --------------------------------------------------------------------------- #
# (c) MANIFEST ENFORCEMENT (prereg §6.2 / §8)                                  #
# --------------------------------------------------------------------------- #
class TestManifestEnforcement:
    def test_happy_path_no_void_and_band_recorded(self, tmp_path):
        full_ladder(tmp_path, flat)
        r = analyze(tmp_path)
        assert r["void_cells"] == []
        assert r["band_seed_start"] == BAND
        assert r["identity_gate"] == "OK"
        assert r["verdict"] == "C-KILL"
        # review C5/C2 wording: the kill must read as a BOUNDED null. "phase axis is dead"
        # may appear ONLY inside the explicit prohibition, never as the claim itself.
        assert "~+/-22 elo" in r["why"]
        assert "endpoint spread ~45 elo" in r["why"]
        assert "BOUNDED null" in r["why"]
        assert r["why"].lower().count("dead") == 1
        assert "NEVER as 'the phase axis is dead'" in r["why"]

    def test_wrong_rules_profile_voids_the_cell(self, tmp_path):
        full_ladder(tmp_path, flat,
                    b0p3={"rules_profile": "walled"})
        r = analyze(tmp_path)
        assert r["void_cells"] == ["b0p3"]
        assert any("rules_profile" in x for c in r["cells"] for x in c["void_reasons"])
        # one void non-identity cell => excluded and noted, verdict still reads
        assert r["verdict"] == "C-KILL"
        assert "b0p3 is VOID" in r["why"]

    def test_r9_off_and_wrong_backend_void_the_cell(self, tmp_path):
        full_ladder(tmp_path, flat,
                    b0p3={"r9_env_ok": False}, bm0p3={"backend": "python"})
        r = analyze(tmp_path)
        assert sorted(r["void_cells"]) == ["b0p3", "bm0p3"]
        assert r["verdict"] == "ABORT-STAGE"

    def test_identity_cell_with_non_production_hash_is_instrument_broken(self, tmp_path):
        full_ladder(tmp_path, flat,
                    b0p0={"cand_leaf_hash": "0000000000000000"})
        r = analyze(tmp_path)
        assert r["verdict"] == "INSTRUMENT-BROKEN"
        assert "b0p0" in r["void_cells"]

    def test_nonzero_beta_cell_with_production_hash_is_void(self, tmp_path):
        """The free positive control: the phase knob must have MOVED the leaf."""
        full_ladder(tmp_path, flat,
                    b0p6={"cand_leaf_hash": PROD})
        r = analyze(tmp_path)
        assert r["void_cells"] == ["b0p6"]
        assert any("never reached the leaf" in x
                   for c in r["cells"] for x in c["void_reasons"])

    def test_two_beta_cells_sharing_a_hash_are_void(self, tmp_path):
        full_ladder(tmp_path, flat,
                    b0p3={"cand_leaf_hash": "abcabcabcabcabca"},
                    b0p6={"cand_leaf_hash": "abcabcabcabcabca"})
        r = analyze(tmp_path)
        assert "b0p6" in r["void_cells"] or "b0p3" in r["void_cells"]
        assert any("shared with cell" in x for c in r["cells"] for x in c["void_reasons"])

    def test_manifest_beta_must_match_the_cell(self, tmp_path):
        full_ladder(tmp_path, flat,
                    bm0p6={"manifest_beta": -0.3})
        r = analyze(tmp_path)
        assert r["void_cells"] == ["bm0p6"]
        assert any("v29_phase_beta" in x for c in r["cells"] for x in c["void_reasons"])

    def test_band_mismatch_voids_the_deviating_cell(self, tmp_path):
        full_ladder(tmp_path, flat,
                    b0p6={"band": 117_000_000_000})
        r = analyze(tmp_path)
        assert r["void_cells"] == ["b0p6"]
        assert r["band_seed_start"] == BAND

    def test_missing_manifest_is_provenance_unreadable_not_broken(self, tmp_path):
        """MISSING evidence is not CONTRADICTING evidence — analyzer defect, cells not void."""
        full_ladder(tmp_path, flat,
                    b0p3={"write_manifest": False})
        r = analyze(tmp_path)
        assert r["verdict"] == "PROVENANCE-UNREADABLE"
        assert r["void_cells"] == []

    def test_incomplete_cell_is_void_and_excluded(self, tmp_path):
        full_ladder(tmp_path, lambda beta, deck: (10 * beta, 10 * beta),
                    b0p6={"n_games": 4})
        r = analyze(tmp_path, n_expected=20)
        assert r["void_cells"] == ["b0p6"]
        assert any("< 90%" in x for c in r["cells"] for x in c["void_reasons"])


# --------------------------------------------------------------------------- #
# (d) THE TRIPWIRE                                                             #
# --------------------------------------------------------------------------- #
class TestTripwire:
    def test_agreement_is_silent(self, tmp_path):
        write_cell(tmp_path, "b0p0", 0.0, {i: (3, 5) for i in range(1, 11)})
        cells = az.collect(tmp_path, "cp_", 20)
        c = cells[[x["cell"] for x in cells].index("b0p0")]
        assert c["mean_margin_recomputed"] == pytest.approx(4.0)
        assert c["paired_mean_margin"] == pytest.approx(4.0)
        az.check_tripwire("b0p0", c["mean_margin_recomputed"], c["paired_mean_margin"])

    def test_mismatch_raises(self, tmp_path):
        """A summary whose paired_mean_margin disagrees must hard-error, not be reported."""
        write_cell(tmp_path, "b0p0", 0.0, {i: (3, 5) for i in range(1, 11)},
                   paired_mean_margin=2.185)
        cells = az.collect(tmp_path, "cp_", 20)
        c = cells[[x["cell"] for x in cells].index("b0p0")]
        with pytest.raises(az.TripwireError) as e:
            az.check_tripwire("b0p0", c["mean_margin_recomputed"], c["paired_mean_margin"])
        assert "paired_mean_margin" in str(e.value)
        assert "2.185" in str(e.value)

    def test_main_refuses_a_verdict_on_a_tripped_cell(self, tmp_path):
        full_ladder(tmp_path, flat,
                    b0p3={"paired_mean_margin": 7.0})
        with pytest.raises(az.TripwireError):
            analyze(tmp_path)

    def test_tolerance_is_1e_6(self, tmp_path):
        assert az.MARGIN_TOL == 1e-6
        az.check_tripwire("x", 1.0, 1.0 + 5e-7)
        with pytest.raises(az.TripwireError):
            az.check_tripwire("x", 1.0, 1.0 + 5e-6)
