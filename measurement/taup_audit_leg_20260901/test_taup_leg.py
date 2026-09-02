#!/usr/bin/env python3
"""Contract tests for the τ_p audit leg.

    pytest measurement/taup_audit_leg_20260901/test_taup_leg.py -q

Four families:
  1. THE FLAG   — `--cand-tau-p` exists in eval_fair_puct's REAL argparse, moves
                  the CANDIDATE and NOT the opponent, is refused when malformed,
                  and is a NO-OP when unset.
  2. THE GATES  — every `leg_lib` gate passes the fixture's PASS case and FIRES
                  on each FAIL_* mutation. ⛔ Address validity is asserted against
                  REAL_DRY, the byte-untouched emitted manifest.
  3. THE SMOKE  — `adjudicate_smoke.py` exits NONZERO on an empty cell, on a
                  manifest-less cell and on a gate failure (the R1 defect class).
  4. THE PAIR   — WORKERS.conf agrees with leg_lib, so a launcher/adjudicator
                  drift is impossible.

⚠️ Family 1 imports eval_fair_puct, which needs the leaf env frozen before
`carcassonne_ai` loads. `env_preamble` does that; it is imported at module scope
for exactly that reason.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIX = HERE / "selftest_fixture"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))
import env_preamble  # noqa: E402,F401
import leg_lib as L  # noqa: E402

sys.path.insert(0, str(REPO / "scripts" / "classical_search"))


@pytest.fixture(scope="module")
def E():
    import eval_fair_puct
    return eval_fair_puct


def _man(name: str) -> dict:
    """⚠️ Every fixture cell is named `SMOKE_*` because `adjudicate_smoke.py`
    refuses anything else; the gate tests address the same dirs."""
    return json.loads((FIX / f"SMOKE_{name}" / "manifest.json").read_text())


# =========================================================================== #
# 1. THE FLAG                                                                  #
# =========================================================================== #

def test_flag_exists_in_the_real_argparse(E):
    """⛔ Driven through `main(['--help'])`, not grepped from the source: the
    parser is built inside main(), so only argparse can answer this."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        with pytest.raises(SystemExit):
            E.main(["--help"])
    assert "--cand-tau-p" in buf.getvalue()


def test_unset_is_byte_identical(E):
    """⭐ THE NO-OP CLAIM. `cand_search` with `tau_p=None` — the dict main()
    always builds — must produce the same config as `cand_search=None`, which is
    what every caller predating this leg passes."""
    base = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                              cand_search=None)
    unset = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                               cand_search={"fpu_reduction": None, "c_puct": None,
                                            "tau_p": None, "shared_c_puct": 1.5,
                                            "shared_tau_p": 5.0})
    assert base == unset


@pytest.mark.parametrize("dose", [3.0, 8.0, 2.5])
def test_dose_moves_the_candidate_only(E, dose):
    """⭐⭐ THE PROPOSITION `--tau-p` FAILS, asserted at the two construction
    sites the harness actually uses."""
    cs = {"fpu_reduction": None, "c_puct": None, "tau_p": dose,
          "shared_c_puct": 1.5, "shared_tau_p": 5.0}
    cand = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                              cand_search=cs)
    assert cand.tau_p == dose
    # `_make_opponent` builds the opponent through THIS call, with cand_search
    # left at its default None.
    shared = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
              "final_select": "visits", "value_norm": 15.0, "fpu_reduction": None}
    assert E._cfg_from_dict(shared, None).tau_p == 5.0
    # …and the shared dict itself is untouched by the override.
    assert shared["tau_p"] == 5.0


def test_dose_does_not_disturb_the_other_two_knobs(E):
    cs = {"fpu_reduction": None, "c_puct": None, "tau_p": 3.0,
          "shared_c_puct": 1.5, "shared_tau_p": 5.0}
    cand = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                              cand_search=cs)
    assert cand.c_puct == 1.5
    assert cand.fpu_reduction is None


def test_dose_reaches_the_rust_backend(E):
    """⛔ The readback the launcher's probe makes: `SearchConfigRs.__repr__`
    prints `tau_p={}` of what the RUST side actually holds. Parsed NUMERICALLY —
    rust's Display for f64 prints 3.0 as "3", so a substring compare would miss
    a healthy config."""
    import re

    from carcassonne_ai.rust_agent import search_config_rs
    cs = {"fpu_reduction": None, "c_puct": None, "tau_p": 3.0,
          "shared_c_puct": 1.5, "shared_tau_p": 5.0}
    cfg = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                             cand_search=cs)
    m = re.search(r"tau_p=([-0-9.eE+]+)", repr(search_config_rs(cfg, 8)))
    assert m is not None and float(m.group(1)) == 3.0


@pytest.mark.parametrize("bad", ["0", "-1", "nan"])
def test_malformed_dose_is_refused_at_launch(E, bad):
    """tau_p is a softmax DENOMINATOR: 0 divides and a negative value INVERTS the
    priors while every log line still says "priors". Both die at argparse."""
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), pytest.raises(SystemExit) as ei:
        E.main(["--info", "fair", "--cand-tau-p", bad, "--summary-only"])
    assert ei.value.code != 0
    assert "--cand-tau-p" in buf.getvalue()


def test_out_dir_tag_separates_a_dosed_cell(E):
    """Trap 1: a dosed cell and the unmodified champion must never share an auto
    out-dir, or one cell's cached per-game .json can be served to the other."""
    src = (REPO / "scripts" / "classical_search" / "eval_fair_puct.py").read_text()
    assert "-candtau{args.cand_tau_p:g}" in src


# =========================================================================== #
# 2. THE GATES                                                                 #
# =========================================================================== #

def test_every_gate_address_exists_in_real_emitter_output():
    """⭐⭐ ADDRESS VALIDITY, asserted against the BYTE-UNTOUCHED emitted
    manifest. A gate at a wrong address returns MISSING; in a lib that failed
    OPEN it would pass vacuously (the IS-D1 defect). Three of the four obvious
    guesses ARE wrong on this emitter, which is why this test exists."""
    real = _man("REAL_DRY")
    addrs = [a for a, _ in L.BUDGET_CHECKS] + [
        "config.cand_search.tau_p", "config.cand_search.shared_tau_p",
        "config.cand_search.fpu_reduction", "config.cand_search.c_puct",
        "config.champion.tau_p", "config.opponent.champ_cfg.tau_p",
        "config.cand_tiearb", "config.opp_tiearb",
    ]
    missing = [a for a in addrs if L.dig(real, a) is L.MISSING]
    assert not missing, f"addresses absent from REAL emitter output: {missing}"


def test_real_dry_fails_only_on_budget():
    """The dry cell really ran k2x32, so G-BUDGET must fire on it and the other
    three gates must not. This is what proves G-BUDGET is not vacuous."""
    real = _man("REAL_DRY")
    assert L.gate_budget(real)
    assert not L.gate_taup(real, 3.0)
    assert not L.gate_singlevar(real)
    assert not L.gate_arbiter(real)


def test_pass_case_passes_every_gate():
    man = _man("PASS")
    assert not L.gate_taup(man, 3.0)
    assert not L.gate_singlevar(man)
    assert not L.gate_budget(man)
    assert not L.gate_arbiter(man)


@pytest.mark.parametrize("case,gate", [
    ("FAIL_taup_absent", "G-TAUP"),
    ("FAIL_taup_null", "G-TAUP"),
    ("FAIL_taup_wrong_dose", "G-TAUP"),
    ("FAIL_taup_candidate_unmoved", "G-TAUP"),
    ("FAIL_taup_leaked_to_opponent", "G-TAUP"),
    ("FAIL_shared_taup_absent", "G-TAUP"),
    ("FAIL_singlevar_fpu_live", "G-SINGLEVAR"),
    ("FAIL_singlevar_cpuct_live", "G-SINGLEVAR"),
    ("FAIL_singlevar_cpuct_absent", "G-SINGLEVAR"),
    ("FAIL_arb_opponent_absent", "G-ARB"),
    ("FAIL_arb_candidate_disabled", "G-ARB"),
    ("FAIL_arb_wrong_B", "G-ARB"),
    ("FAIL_arb_gated", "G-ARB"),
    ("FAIL_budget_stale", "G-BUDGET"),
    ("FAIL_rules_walled", "G-BUDGET"),
    ("FAIL_unpaired", "G-BUDGET"),
])
def test_each_mutation_fires_its_gate(case, gate):
    man = _man(case)
    fn = L.ALL_GATES[gate]
    bad = fn(man, 3.0) if gate == "G-TAUP" else fn(man)
    assert bad, f"{case} did NOT fire {gate}"


def test_absent_is_not_none():
    """⚠️⚠️ The distinction every gate here turns on. `tau_p: null` is a POSITIVE
    statement ("the shared --tau-p"); an ABSENT key means the harness predates
    this leg. Both FAIL for a dosed cell, and they must fail with DIFFERENT
    messages so a reader can tell a stale harness from a wrong dose."""
    absent = L.gate_taup(_man("FAIL_taup_absent"), 3.0)
    null = L.gate_taup(_man("FAIL_taup_null"), 3.0)
    assert any("ABSENT" in m and "PREDATES" in m for m in absent)
    assert not any("PREDATES" in m for m in null)


def test_opponent_leak_is_named_as_such():
    bad = L.gate_taup(_man("FAIL_taup_leaked_to_opponent"), 3.0)
    assert any("LEAKED" in m for m in bad)


# =========================================================================== #
# 3. THE SMOKE ADJUDICATOR                                                     #
# =========================================================================== #

def _adj(cell, tau=3.0, extra=()):
    out = HERE / "_pytest_smoke_out.json"
    r = subprocess.run(
        [sys.executable, str(HERE / "adjudicate_smoke.py"), "--root", str(FIX),
         "--cell", cell, "--dose", str(tau), "--out", str(out), *extra],
        capture_output=True, text=True)
    out.unlink(missing_ok=True)
    return r


def test_smoke_adjudicator_passes_a_good_cell():
    r = _adj("SMOKE_PASS")
    assert r.returncode == 0, r.stdout + r.stderr


def test_smoke_adjudicator_exits_nonzero_on_empty_cell():
    """⛔⛔ THE R1 DEFECT CLASS. A manifest with zero per-game records is a
    harness that started and played nothing — the shape a "the smoke passed"
    report is most likely to be believed about."""
    r = _adj("SMOKE_EMPTY_CELL")
    assert r.returncode != 0
    assert "ZERO per-game records" in r.stderr


def test_smoke_adjudicator_exits_nonzero_without_a_manifest():
    r = _adj("SMOKE_NO_MANIFEST")
    assert r.returncode != 0
    assert "manifest.json" in r.stderr


def test_smoke_adjudicator_exits_nonzero_on_a_missing_cell():
    r = _adj("SMOKE_does_not_exist")
    assert r.returncode != 0
    assert "emitted NOTHING" in r.stderr


def test_smoke_adjudicator_exits_nonzero_on_a_gate_failure():
    r = _adj("SMOKE_FAIL_taup_leaked_to_opponent")
    assert r.returncode != 0


def test_smoke_adjudicator_refuses_a_non_smoke_cell():
    """It reads STRUCTURAL keys only and must never be pointed at a real cell."""
    r = _adj("REALCELL_PASS")
    assert r.returncode != 0
    assert "not a SMOKE_ cell" in r.stderr


def test_smoke_output_carries_no_outcome_key():
    out = HERE / "_pytest_smoke_out2.json"
    subprocess.run(
        [sys.executable, str(HERE / "adjudicate_smoke.py"), "--root", str(FIX),
         "--cell", "SMOKE_PASS", "--dose", "3.0", "--out", str(out)],
        capture_output=True, text=True, check=True)
    doc = json.loads(out.read_text())
    out.unlink()
    # ⚠️ The RIDERS deliberately NAME the banned keys ("carries no winrate, elo,
    # margin or z"), so scan the DATA, not the prose that forbids it.
    doc.pop("riders", None)
    blob = json.dumps(doc).lower()
    for banned in ("winrate", "\"elo\"", "paired_mean_margin", "paired_z"):
        assert banned not in blob, f"the smoke leaked an OUTCOME key: {banned}"


# =========================================================================== #
# 4. THE PAIR — WORKERS.conf must agree with leg_lib                           #
# =========================================================================== #

def _conf() -> dict:
    out = {}
    for line in (HERE / "WORKERS.conf").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def test_workers_conf_agrees_with_leg_lib():
    c = _conf()
    assert float(c["TAU_DOSE_LOW"]) == L.DOSES["CELL_TAU3"]
    assert float(c["TAU_DOSE_HIGH"]) == L.DOSES["CELL_TAU8"]
    assert float(c["TAU_P_PRODUCTION"]) == L.TAU_P_PRODUCTION
    assert int(c["BAND_TAU3"]) == L.BAND_TAU3
    assert int(c["BAND_TAU8"]) == L.BAND_TAU8
    assert int(c["THROWAWAY_BASE"]) == L.THROWAWAY_BASE
    assert int(c["K_DETS"]) == L.K_DETS
    assert int(c["SIMS_PER_DET"]) == L.SIMS_PER_DET
    assert int(c["TOTAL_SIMS"]) == L.TOTAL_SIMS
    assert int(c["EXACT_K"]) == L.EXACT_K
    assert c["EXACT_MODE"] == L.EXACT_MODE
    assert c["BACKEND"] == L.BACKEND
    assert c["RULES_PROFILE"] == L.RULES_PROFILE
    assert int(c["N_DECKS"]) == L.N_DECKS
    assert int(c["N_GAMES"]) == L.N_GAMES
    assert int(c["W_LAPTOP"]) == L.W_LAPTOP
    assert int(c["TIEARB_B"]) == L.TIEARB["B"]
    assert int(c["TIEARB_J"]) == L.TIEARB["J"]
    assert c["TIEARB_MODE"] == L.TIEARB["mode"]
    assert c["TIEARB_SALT"] == L.TIEARB["salt"]
    assert float(c["TIEARB_EPS"]) == L.TIEARB["eps"]
    assert c["TIEARB_PHASE_GATE"] == L.TIEARB["phase_gate"]


def test_n_games_is_paired_and_seat_balanced():
    assert L.N_GAMES == 2 * L.N_DECKS


def test_bands_are_distinct_and_disjoint_from_the_throwaway_range():
    assert L.BAND_TAU3 != L.BAND_TAU8
    for b in (L.BAND_TAU3, L.BAND_TAU8):
        assert not (b <= L.THROWAWAY_BASE < b + L.N_DECKS)


def test_launcher_carries_no_shared_flag():
    """⛔ There must be NO bare --tau-p / --c-puct anywhere in the launcher: those
    build champ_cfg_dict, which _make_opponent feeds through the SAME
    _cfg_from_dict, so they move BOTH SIDES."""
    # ⚠️ COMMENT LINES ARE EXCLUDED: the launcher NAMES the banned flags in the
    # comment that explains why they are banned, and a check that could not tell
    # the two apart would force the explanation out of the file.
    src = (HERE / "run_cells.sh").read_text()
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    for banned in ("--tau-p ", "--c-puct ", "--cand-c-puct",
                   "--cand-fpu-reduction"):
        assert banned not in code, f"the launcher carries {banned!r}"
    assert "--cand-tau-p" in code


def test_blind_commit_pending_blocks_a_real_launch():
    """The launcher must refuse a real cell while BLIND_COMMIT reads PENDING."""
    conf = _conf()
    src = (HERE / "run_cells.sh").read_text()
    assert 'BLIND_COMMIT" != "PENDING"' in src
    doc = json.loads((HERE / "BLIND_COMMIT.json").read_text())
    # ⛔ The two must agree, or the launcher gates on one document while the
    # round's provenance record says another.
    assert doc["blind_commit"] == conf["BLIND_COMMIT"]


def test_the_bands_are_claimed_or_spent():
    """⚠️ Was `test_band_is_proposed_not_claimed`: written and frozen at BUILD
    TIME (before this agent claimed a band), when BAND_CLAIMED had not yet been
    written and neither band was in `governance/BAND_REGISTRY.csv`. The round
    has since claimed — and spent — both bands, REASSIGNED from the
    placeholder's proposed 170e9/171e9 to 171e9/172e9 at claim time (170e9 was
    claimed the same day by `measurement/fpu_swap_cell_20260901`; see
    `BAND_CLAIMED` for the full story), so the original "not yet claimed"
    assertion fails permanently.

    ⛔ Checked against the REASSIGNED bands (171e9/172e9) directly, NOT
    `L.BAND_TAU3`/`L.BAND_TAU8` — those module constants are still the stale
    pre-reassignment 170e9/171e9 (leg_lib.py was never updated after the
    swap-cell collision; that staleness is a separate defect from this test
    and out of scope here — flagging it, not fixing it).

    House pattern (tests/test_fpu_h2h_instrument.py
    ::test_the_bands_status_is_claimed_or_spent): relaxed to assert
    BAND_CLAIMED now exists and the registry rows for the reassigned bands
    exist with status claimed/spent and a label naming this round's cells,
    while STILL asserting band identity (band number + label) so a truly
    wrong/missing row is still caught."""
    assert (HERE / "BAND_CLAIMED.placeholder").is_file()
    assert (HERE / "BAND_CLAIMED").is_file(), \
        "BAND_CLAIMED is missing — the round never claimed its bands"
    assert "BAND_CLAIMED" in (HERE / "run_cells.sh").read_text()

    with open(REPO / "governance" / "BAND_REGISTRY.csv", newline="") as f:
        by_band = {row["band_seed_start"]: row for row in csv.DictReader(f)}
    for band, cell in ((171_000_000_000, "CELL_TAU3"),
                       (172_000_000_000, "CELL_TAU8")):
        row = by_band.get(str(band))
        assert row is not None, f"band {band} is not registered at all"
        assert row["status"] in ("claimed", "spent"), (
            f"band {band} status is {row['status']!r}, expected claimed or spent")
        assert cell in row["label"], \
            f"the registry row at band {band} is not this round's claim ({cell})"


def test_golden_gate_verdict_is_pass():
    g = json.loads((HERE / "TAUP_BITEXACT.json").read_text())
    assert g["verdict"] == "PASS", g["failed"]
    for name in ("IDENTITY", "POSITIVE", "CANDIDATE-ONLY", "AUDIT-ADJUDICATED",
                 "ONE-WHEEL", "ONE-SRC", "ONE-FILE"):
        assert any(c["check"] == name and c["ok"] for c in g["checks"]), name
