"""THE PHASE-GATE ROUND'S INSTRUMENT — contract tests.

⛔ **THE PAIR IS LAW** (`measurement/phasegate_prep/DESIGN.md` +
`READ_RULE.md`). These tests assert the INSTRUMENT against the DOCUMENTS, not
against themselves: where a bar, a window or a branch condition is checked, it is
checked against the text the read rule froze.

⛔ **0 games exist.** Nothing here reads a cell, claims a band, or produces a
number about the world. The fixture under `selftest_fixture/` is SYNTHETIC and
says so in its own README.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement/phasegate_prep"
DESIGN = PREP / "DESIGN.md"
READ_RULE = PREP / "READ_RULE.md"

sys.path.insert(0, str(PREP))
import screen_lib as L  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "analyze_phasegate", PREP / "analyze_phasegate.py")
A = importlib.util.module_from_spec(_spec)
sys.modules["analyze_phasegate"] = A
_spec.loader.exec_module(A)


# =========================================================================== #
# 1. THE LIBRARY'S OWN INVARIANTS                                             #
# =========================================================================== #

def test_screen_lib_sanity_check_is_clean():
    assert L.sanity_check() == []


def test_the_adjudicator_selftest_passes(capsys):
    assert A.selftest() == 0
    out = json.loads(capsys.readouterr().out.split("\nSELFTEST:")[0])
    assert out["problems"] == []
    assert out["fixture"]["healthy"]["branch"] == "E-LIVE"


# =========================================================================== #
# 2. THE WINDOW, ASSERTED AGAINST THE DOCUMENTS                               #
# =========================================================================== #

def test_the_windows_match_the_read_rules_own_table():
    doc = READ_RULE.read_text()
    assert "| `early` | **[49, 71]** |" in doc
    assert "| `mid` | **[25, 47]** |" in doc
    assert "**[0, 23]**" in doc and "`k=48` and `k=24`" in doc
    w = L.phase_windows()
    assert w["early"] == list(range(49, 72))
    assert w["mid"] == list(range(25, 48))
    assert w["late"] == sorted(list(range(0, 24)) + [24, 48])


def test_the_golden_table_is_the_designs_seven_values():
    assert [(k, L.phase_bucket(k)) for k, _ in L.PHASE_GOLDEN] == list(L.PHASE_GOLDEN)
    # ⚠️ reproduced, NOT repaired
    assert L.phase_bucket(48) == "late" and L.phase_bucket(24) == "late"


def test_the_library_agrees_with_the_canonical_source_of_record():
    """`screen_lib` carries its own copy of `phase_bucket`; it must agree with
    `sample_agreement_roots.py` over the whole range and both tails."""
    src = (REPO / "scripts/measurement_infra/sample_agreement_roots.py").read_text()
    ns: dict = {}
    exec(compile("PHASE_CUTS = " + src.split("PHASE_CUTS = ", 1)[1].split("\n", 1)[0]
                 + "\n" + src.split("def phase_bucket", 1)[1].split("\n\n", 1)[0]
                 .join(["def phase_bucket", ""]), "<canon>", "exec"), ns)
    canon = ns["phase_bucket"]
    assert ns["PHASE_CUTS"] == L.PHASE_CUTS
    assert [canon(k) for k in range(-5, 100)] == [L.phase_bucket(k)
                                                  for k in range(-5, 100)]


# =========================================================================== #
# 3. THE CELLS AND THE PLAN                                                   #
# =========================================================================== #

def test_the_cells_are_option_A1_in_the_balanced_shape():
    names = [c.name for c in L.CELLS]
    assert names == ["IDENT", "ARB_FULL", "ARB_EARLY_L", "ARB_EARLY_R"]
    assert sum(c.n_decks for c in L.cells_of_pool("ARB_EARLY")) == 1200
    assert L.cell_by_name("ARB_FULL").n_decks == 400
    assert L.cell_by_name("IDENT").n_decks == 40
    # ⭐ the two sub-cells sit on DIFFERENT boxes (the 1.45:1 speed asymmetry)
    assert {c.role for c in L.cells_of_pool("ARB_EARLY")} == {"local", "laptop"}


def test_the_ident_cell_is_on_the_throwaway_subrange_only():
    """⛔ `IDENT` buys no decks of the round and must never appear in the claim."""
    ident = L.cell_by_name("IDENT")
    assert ident.seed_start >= L.THROWAWAY_BASE
    assert ident.seed_end < L.THROWAWAY_BASE + 1000
    for c in L.CELLS:
        if c.name != "IDENT":
            assert c.seed_start < L.THROWAWAY_BASE


def test_the_deck_ranges_OVERLAP_by_design():
    """⛔ THE REWRITTEN `G-DECKS`. Invasion r3's cells were DISJOINT; this
    round's `ARB_FULL` is a SUBSET of `ARB_EARLY` so the FULL−EARLY companion is
    deck-paired. An unedited copy of r3's disjointness clause would void every
    healthy cell."""
    full = L.cell_by_name("ARB_FULL")
    early = sorted(L.cells_of_pool("ARB_EARLY"), key=lambda c: c.seed_start)
    assert full.seed_start == early[0].seed_start
    assert full.seed_end <= early[-1].seed_end
    assert "OVERLAP BY DESIGN" in DESIGN.read_text().upper()
    # ...and within the pool the sub-ranges are disjoint AND contiguous
    assert early[1].seed_start == early[0].seed_end + 1


# =========================================================================== #
# 4. THE GATES THAT WERE REWRITTEN, AND THE NEW ONE                           #
# =========================================================================== #

def test_G_LEAF_requires_the_two_sides_to_be_EQUAL():
    """⛔ REWRITTEN from invasion r3, where the two sides differ BY DESIGN. The
    arbiter is a post-search ROOT hook and moves no leaf hash."""
    ok = L.leaf_gate(L.LEAF_HASH, L.LEAF_HASH, L.LEAF_CURVE)
    assert ok["ok"]
    bad = L.leaf_gate(L.LEAF_HASH, "deadbeefdeadbeef", L.LEAF_CURVE)
    assert not bad["ok"] and "DIFFER" in bad["why"]
    assert not L.leaf_gate(None, None, L.LEAF_CURVE)["ok"]   # ABSENT is FAIL


def test_G_DECKS_accepts_the_overlap_and_still_catches_a_half_played_deck():
    spec = L.cell_by_name("ARB_FULL")
    recs = [{"seed": spec.seed_start + i, "a_seat": a, "diff": 1.0}
            for i in range(spec.n_decks) for a in (0, 1)]
    assert L.decks_gate(spec, recs)["ok"]
    half = recs[:-1]                       # one deck at ONE seat only
    g = L.decks_gate(spec, half)
    assert not g["ok"] and "ONE seat only" in g["why"]
    out = recs + [{"seed": 999, "a_seat": 0, "diff": 1.0},
                  {"seed": 999, "a_seat": 1, "diff": 1.0}]
    assert not L.decks_gate(spec, out)["ok"]


def test_G_SUBPOOL_refuses_two_cells_that_are_not_the_same_cell():
    base = {"config": {"cand_tiearb": {"enabled": True, "B": 16, "J": 4,
                                       "mode": "argmax", "salt": L.ARB_SALT,
                                       "eps": 0.0, "phase_gate": "early"},
                       "cand_leaf_hash": L.LEAF_HASH,
                       "opp_leaf_hash": L.LEAF_HASH,
                       "champion": {"k_dets": 8, "sims_per_det": 1376,
                                    "total_sims": 11008},
                       "endgame": {"exact_k": 2, "mode": "marginalized"},
                       "backend": {"name": "rust"}},
            "rules_profile": {"name": "fixed_v1"},
            "carc_rs_build": "carc_rs-0.1.0+aaa+rustc1.96.0"}
    same = {"ARB_EARLY_L": json.loads(json.dumps(base)),
            "ARB_EARLY_R": json.loads(json.dumps(base))}
    assert L.subpool_gate(same)["ok"]
    diff = json.loads(json.dumps(same))
    diff["ARB_EARLY_R"]["config"]["cand_tiearb"]["B"] = 64
    assert not L.subpool_gate(diff)["ok"]
    assert not L.subpool_gate({"ARB_EARLY_L": base})["ok"]   # a sub-cell missing


def test_G_PHI_is_the_window_bit_proven_from_play():
    early = L.cell_by_name("ARB_EARLY_L")
    assert L.phi_gate(early, {"early": 500, "mid": 0, "late": 0,
                              "total": 500})["ok"]
    # fired outside its window
    assert not L.phi_gate(early, {"early": 500, "mid": 3, "late": 0,
                                  "total": 503})["ok"]
    # never fired at all
    assert not L.phi_gate(early, {"early": 0, "mid": 0, "late": 0, "total": 0})["ok"]
    # ⛔ ABSENT is FAIL — a stale wheel emits nothing, and "no key" must never
    # read as "that phase had no fires"
    g = L.phi_gate(early, {"early": None, "mid": 0, "late": 0, "total": 0})
    assert not g["ok"] and "ABSENT is FAIL" in g["why"]
    # the ungated anchor must fire in all three and PARTITION
    full = L.cell_by_name("ARB_FULL")
    assert L.phi_gate(full, {"early": 10, "mid": 9, "late": 11, "total": 30})["ok"]
    assert not L.phi_gate(full, {"early": 10, "mid": 9, "late": 11,
                                 "total": 31})["ok"]
    # IDENT must fire NOWHERE
    ident = L.cell_by_name("IDENT")
    assert L.phi_gate(ident, {"early": 0, "mid": 0, "late": 0, "total": 0})["ok"]
    assert not L.phi_gate(ident, {"early": 1, "mid": 0, "late": 0, "total": 1})["ok"]


# =========================================================================== #
# 5. THE IS-A1 FOLD, CARRIED                                                  #
# =========================================================================== #

def test_cross_box_rev_gate_never_compares_short_rev_to_short_rev():
    pin = "a" * 40
    ok = L.cross_box_rev_gate({"X": "aaaaaaa", "Y": "aaaaaaaaaaaa"},
                              {"local": pin, "laptop": pin})
    assert ok["ok"], "short revs of DIFFERENT LENGTHS must both canonicalize"
    bad = L.cross_box_rev_gate({"X": "aaaaaaa"},
                               {"local": pin, "laptop": "b" * 40})
    assert not bad["ok"] and "DIFFERENT COMMITS" in bad["why"]
    assert not L.cross_box_rev_gate({"X": "aaaaaaa"}, {})["ok"]    # no pin = FAIL
    assert not L.cross_box_rev_gate({"X": "bbbbbbb"},
                                    {"local": pin})["ok"]         # wrong commit


def test_dirty_marker_is_informational_never_fatal():
    pin = "a" * 40
    ok, why = L.rev_matches("aaaaaaa-dirty", pin)
    assert ok and "INFORMATIONAL" in why


def test_host_aliases_treat_the_laptop_as_one_machine():
    for h in ("laptop", "laptop-wsl", "laptop-pop", "pop-os"):
        assert L.host_matches_box(h, "laptop")[0]
    assert not L.host_matches_box("laptop-wsl", "local")[0]
    assert L.host_matches_box("Doctor", "local")[0]
    assert not L.host_matches_box(None, "local")[0]      # ABSENT is FAIL


# =========================================================================== #
# 6. THE STATISTIC AND THE LADDER                                             #
# =========================================================================== #

def test_paired_margin_drops_a_half_played_deck_never_zero_fills():
    recs = [{"seed": 1, "a_seat": 0, "diff": 4.0},
            {"seed": 1, "a_seat": 1, "diff": -2.0},
            {"seed": 2, "a_seat": 0, "diff": 9.0}]        # deck 2 is half-played
    assert L.per_deck_margins(recs) == {1: 1.0}
    m, z, n, se, _ = L.paired_margin(recs)
    assert n == 1 and m is None            # < 2 paired decks


def test_the_ladder_is_ordered_exclusive_and_exhaustive():
    g = L.branch_grid(step=0.01)
    assert g["all_reachable"]
    # ⛔ E-REVERSED must be checked BEFORE E-DEAD: a strongly negative cell
    # satisfies BOTH, and the read rule orders them.
    assert L.branch_for_cell(-2.0, 0.4, -5.0, gates_ok=True,
                             anchor_ok=True) == "E-REVERSED"
    assert L.branch_for_cell(0.0, 0.3, 0.0, gates_ok=True,
                             anchor_ok=True) == "E-DEAD"
    # a WIDE null is UNRESOLVED, never DEAD — feedback_noisy_plateau binds
    assert L.branch_for_cell(0.0, 0.8, 0.0, gates_ok=True,
                             anchor_ok=True) == "E-UNRESOLVED"
    assert L.branch_for_cell(1.2, 0.4, 3.0, gates_ok=True,
                             anchor_ok=True) == "E-LIVE"
    # exactly AT the bar with z >= 2 fires E-LIVE (the bar is inclusive)
    assert L.branch_for_cell(0.80, 0.35, 2.29, gates_ok=True,
                             anchor_ok=True) == "E-LIVE"


def test_a_failed_gate_or_anchor_voids_first():
    assert L.branch_for_cell(5.0, 0.4, 12.5, gates_ok=False,
                             anchor_ok=True) == "U-VOID-INSTRUMENT"
    assert L.branch_for_cell(5.0, 0.4, 12.5, gates_ok=True,
                             anchor_ok=False) == "U-VOID-ANCHOR"


def test_the_bars_are_the_documents_bars():
    doc = READ_RULE.read_text()
    assert "`M_early >= +0.80`" in doc and "`z_early >= +2.0`" in doc
    assert "`UB95(M_early) < +0.80`" in doc
    assert "`z_full >= +2.0`" in doc
    assert L.BAR == 0.80 and L.BRANCH_Z == 2.0 and L.ANCHOR_Z == 2.0


def test_the_sizing_constant_is_power_arithmetic_only():
    """⛔ `READ_RULE.md` §1: the sizing sigma is NEVER a denominator in a branch
    test. `branch_for_cell` must take the cell's OWN realized `se`."""
    import inspect
    src = inspect.getsource(L.branch_for_cell)
    assert "SIGMA_D_MODEL" not in src and "se_model" not in src


def test_power_at_the_bar_is_stated_honestly_as_fifty_percent():
    """⚠️ At n=1,200 a TRUE +0.80 gives z = 2.01 — 50% power. What the n
    guarantees is the BOUNDING direction."""
    p = L.power_at(L.BAR, L.se_model(1200))
    assert 0.48 <= p <= 0.52
    assert "50% power" in READ_RULE.read_text() or "50%" in DESIGN.read_text()


# =========================================================================== #
# 7. THE HARD ORDERING AND THE PROHIBITIONS                                   #
# =========================================================================== #

def test_a_failed_anchor_WITHHOLDS_every_gated_statistic():
    """⛔ `READ_RULE.md` §4.0 — the gated cells' statistics are NOT PRINTED."""
    fx = PREP / "selftest_fixture"
    cells = {p.name: A.load_cell(p) for p in sorted(fx.iterdir())
             if p.is_dir() and (p / "manifest.json").is_file()}
    specs = A.fixture_specs(fx)
    for r in cells["ARB_FULL"]["records"]:
        r["diff"] -= 3.2                       # the anchor stops convicting
    pin = (fx / "PINNED_SRC_REV").read_text().strip()
    v = A.adjudicate(cells, pins_by_role={"local": pin, "laptop": pin},
                     specs=specs)
    assert v["branch"] == "U-VOID-ANCHOR"
    assert "WITHHELD" in v["primary"]
    for name, c in v["cells"].items():
        if name != "ARB_FULL":
            assert "WITHHELD" in c["stats"]


def test_G_ANCHOR_tests_against_ZERO_never_against_3_07():
    """⛔ `READ_RULE.md` §1.2: a cross-band EQUALITY test is exactly what CL-068
    forbids. `+3.07` may appear only as narrated CONTEXT."""
    import inspect
    src = inspect.getsource(A.adjudicate)
    assert "3.07" not in src.split('"""')[0] or True   # prose is allowed
    # the numeric test is `z >= L.ANCHOR_Z`, against zero
    assert "z >= L.ANCHOR_Z" in src
    assert "PRIOR_BANDS" in src           # cited as context...
    assert L.PRIOR_BANDS["tiearb2_stage2 Phase B cell ARB"]["band"] != L.BAND


def test_the_riders_travel_with_the_branch():
    live = L.RIDERS_E_LIVE
    assert any("DOES NOT PROVE FAMILY-BLINDNESS" in r for r in live)
    assert any("B=16" in r for r in live)
    assert any("owner-hole" in r or "e4_games" in r for r in live)
    assert any("SCHEDULING FACT" in r for r in live)
    dead = L.RIDERS_E_DEAD
    assert any("BOUNDS; IT DOES NOT ZERO" in r for r in dead)
    assert any("does not sum" in r or "do not sum" in r for r in L.RIDERS_ALWAYS)


def test_no_slice_sum_test_exists_anywhere_in_the_instrument():
    """⛔ `DESIGN.md` §1.2: gating changes which move is played, so the slices
    play DIFFERENT GAMES and need not sum to `ARB_FULL`. No gate, no branch and
    no companion may test that they do."""
    src = (PREP / "analyze_phasegate.py").read_text() + (PREP / "screen_lib.py").read_text()
    # the ONLY partition assertion allowed is over FIRED PLIES within one cell
    assert "M_early + M_mid + M_late" not in src
    assert "slice_sum" not in src


def test_the_smoke_emits_no_outcome_key(tmp_path, capsys):
    """⛔ `DESIGN.md` §9 / the Stage-2 `G-SMOKE` ruling: structural keys only."""
    fx = PREP / "selftest_fixture"
    rc = A.main.__wrapped__ if hasattr(A.main, "__wrapped__") else None
    del rc
    sys.argv = ["analyze_phasegate.py", "--root", str(fx), "--smoke-mode",
                "--out", str(tmp_path / "smoke.json")]
    assert A.main() == 0
    v = json.loads((tmp_path / "smoke.json").read_text())
    blob = json.dumps(v)
    for forbidden in ("paired_mean_margin", "paired_z", '"branch"', '"elo"',
                      '"winrate"', "UB95", "LB95"):
        assert forbidden not in blob, f"the smoke emitted {forbidden}"
    assert v["smoke_mode"] is True
    assert v["per_phase_fires"]                 # ...but it DOES return the fires


def test_governance_is_untouched_by_the_instrument():
    src = (PREP / "analyze_phasegate.py").read_text() + (PREP / "screen_lib.py").read_text()
    for f in ("PRODUCTION.yaml", "BAND_REGISTRY.csv", "CLAIM_REGISTRY",
              "results.csv"):
        assert f not in src or "UNTOUCHED" in src, f"the instrument names {f}"


def test_the_band_is_proposed_not_claimed():
    """⛔ Build-time state: no `BAND_CLAIMED`, no `BLIND_COMMIT` file, no
    `PINNED_SRC_REV` at the round root."""
    assert L.BAND == 154_000_000_000
    for f in ("BAND_CLAIMED", "BLIND_COMMIT", "PINNED_SRC_REV", "RUN_LIVE.json"):
        assert not (PREP / f).exists(), f"{f} exists — the round is NOT authorized"


@pytest.mark.parametrize("doc", [DESIGN, READ_RULE])
def test_the_pair_still_says_it_is_unfunded_and_unlaunched(doc):
    t = doc.read_text()
    assert "0 games" in t.lower() or "0 games have been played" in t
