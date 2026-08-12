"""Tests for the E4 autopsy extraction + stratification stage
(scripts/analyzer/autopsy_extract.py).

Only the PURE helpers and the pure-stdlib `census` / `sample` modes are in scope here —
no `carcassonne_ai`, no engine, no search. `emit()` (the engine pass) is out of scope by
design; it needs a live archive replay and is not something a fast unit suite should run.

What's pinned, matching the module's own risk list:

  1. THE STRATA BOUNDARIES — `phase_third`'s tercile cuts, `is_degenerate`'s <= eps rule,
     `collapse_structure`'s symmetric-difference-then-priority collapse, `primary_stratum`'s
     DEG-dominates rule, and `commit_direction`'s four-way meeple-economy label. Silent
     drift in any of these silently reshuffles which ply lands in which stratum.
  2. THE SIZING ARITHMETIC — `size_stratum`'s n formula and its three binding regimes
     (power / population / n_max), and `allocate_proportional`'s exact-sum, never-over-
     supply apportionment. A sign or off-by-one error here mis-powers a whole stratum.
  3. THE CANDIDATE FILTER — `candidate_plies` selects Joshua's disagreement plies and
     ONLY those; every exclusion clause (wrong actor, forced, exact, missing arm, missing
     ΔQ, ineligible, agreeing) is exercised, and the human_player seat is read from the
     artifact rather than assumed to be 0.
  4. THE PURE-STDLIB MODES END TO END — `census` (stratum counts, touch/contested
     marginals, meeple-commit counters, markdown emission) and `sample` (power-based
     per-stratum n, proportional sub-allocation, deterministic seeded draw, per-epoch
     position files) against small synthetic `plies_*.jsonl` inputs built in `tmp_path`.
  5. THE SIGN CONTRACT ON THE REAL FILE — `arm A = the champion's pick, arm B = Joshua's`
     is the sign the whole downstream scorer relies on (`position_delta` returns B - A).
     If the real emitted `plies_fixed_v1.jsonl` exists on disk, every row is checked
     against it directly.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO / "scripts/analyzer"))
sys.path.insert(0, str(REPO / "scripts/human_anchor"))
sys.path.insert(0, str(REPO / "scripts/measurement_infra"))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


AE = _load("autopsy_extract", "scripts/analyzer/autopsy_extract.py")


def _read_jsonl(path: Path) -> list:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list) -> Path:
    with path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


# --------------------------------------------------------------------------- #
# 1. phase_third — tercile cuts on k_remaining                                  #
# --------------------------------------------------------------------------- #
class TestPhaseThird:
    """Pins the exact tercile boundaries: [48,71]=opening, [24,47]=middle, [0,23]=endgame."""

    def test_opening_at_observed_max_71(self):
        """71 is k_remaining at ply 0 (the full 71-tile deck) — must read opening."""
        assert AE.phase_third(71) == "opening"

    def test_opening_lower_boundary_48(self):
        assert AE.phase_third(48) == "opening"

    def test_middle_upper_boundary_47(self):
        """One tile below the opening cut must already be middle."""
        assert AE.phase_third(47) == "middle"

    def test_middle_lower_boundary_24(self):
        assert AE.phase_third(24) == "middle"

    def test_endgame_upper_boundary_23(self):
        """One tile below the middle cut must already be endgame."""
        assert AE.phase_third(23) == "endgame"

    def test_endgame_at_zero(self):
        assert AE.phase_third(0) == "endgame"


# --------------------------------------------------------------------------- #
# 2. is_degenerate — the leaf-indifference test                                 #
# --------------------------------------------------------------------------- #
class TestIsDegenerate:
    """Pins the <= (not <) comparison, using float-clean values to avoid FP-rounding
    noise at the boundary (1.0 + 1e-9 is not exactly representable, so the exact-eps
    case is pinned with round binary values instead of the tiny production epsilon)."""

    def test_exactly_at_eps_is_degenerate(self):
        assert AE.is_degenerate(0.0, 2.0, eps=2.0) is True

    def test_just_above_eps_is_not_degenerate(self):
        assert AE.is_degenerate(0.0, 2.0 + 1e-6, eps=2.0) is False

    def test_default_eps_matches_the_module_constant(self):
        assert AE.DEGENERATE_EPS == pytest.approx(1e-9)
        assert AE.is_degenerate(1.0, 1.0) is True                 # identical leaves
        assert AE.is_degenerate(1.0, 1.0 + 1e-6) is False          # well above default eps


# --------------------------------------------------------------------------- #
# 3. collapse_structure — symmetric-difference-then-priority collapse           #
# --------------------------------------------------------------------------- #
class TestCollapseStructure:
    def test_symmetric_difference_wins_over_union(self):
        """(a) The arms differ ONLY on "road" (both touch "farm"), so the symmetric
        difference — not the higher-priority "farm" in the union — decides."""
        assert AE.collapse_structure({"farm", "road"}, {"farm"}) == "road"

    def test_structure_priority_applies_within_the_chosen_pool(self):
        """(b) farm > cloister > city > road, applied within the sym-diff pool here."""
        assert AE.collapse_structure({"city", "farm"}, set()) == "farm"

    def test_identical_nonempty_sets_fall_through_to_the_union(self):
        """(c) sym-diff is empty when both arms touch the same set, so the union
        (== that same set) decides — a "where exactly", not "what kind", disagreement."""
        assert AE.collapse_structure({"city"}, {"city"}) == "city"

    def test_both_empty_is_neutral(self):
        """(d) Neither arm touches anything scoring-relevant -> the NEUTRAL constant."""
        assert AE.collapse_structure(set(), set()) == AE.NEUTRAL
        assert AE.NEUTRAL == "neutral"

    def test_accepts_lists_as_well_as_sets(self):
        """(e) `emit()` passes sorted LISTS (`touch["best"] = sorted(tt)`); the function
        must accept them, not just sets."""
        assert AE.collapse_structure(["city", "farm"], []) == "farm"


# --------------------------------------------------------------------------- #
# 4. primary_stratum — DEG dominance + uppercasing                              #
# --------------------------------------------------------------------------- #
class TestPrimaryStratum:
    def test_degenerate_dominates_regardless_of_structure(self):
        assert AE.primary_stratum(True, "farm") == "DEG"
        assert AE.primary_stratum(True, "neutral") == "DEG"
        assert AE.primary_stratum(True, "road") == "DEG"

    def test_uppercased_structure_when_not_degenerate(self):
        assert AE.primary_stratum(False, "city") == "CITY"
        assert AE.primary_stratum(False, "farm") == "FARM"
        assert AE.primary_stratum(False, "road") == "ROAD"
        assert AE.primary_stratum(False, "cloister") == "CLOISTER"

    def test_neutral_maps_to_neutral_uppercase(self):
        assert AE.primary_stratum(False, "neutral") == "NEUTRAL"


# --------------------------------------------------------------------------- #
# 5. commit_direction — the meeple-economy axis                                 #
# --------------------------------------------------------------------------- #
class TestCommitDirection:
    def test_tile_decision_is_not_applicable(self):
        assert AE.commit_direction("tile", "road", "pass") == "n/a"

    def test_hold_when_champion_commits_and_he_keeps_his(self):
        assert AE.commit_direction("meeple", "road", "pass") == "hold"

    def test_spend_when_he_commits_and_champion_keeps_its(self):
        assert AE.commit_direction("meeple", "pass", "road") == "spend"

    def test_swap_when_both_commit_to_different_targets(self):
        assert AE.commit_direction("meeple", "road", "city") == "swap"

    def test_both_pass_when_neither_commits(self):
        assert AE.commit_direction("meeple", "pass", "pass") == "both_pass"


# --------------------------------------------------------------------------- #
# 6. size_stratum — power-based n, and the three binding regimes                #
# --------------------------------------------------------------------------- #
class TestSizeStratum:
    def test_power_regime_arithmetic(self):
        """n = ceil((z*sd/target_effect)^2) when neither population nor n_max caps it."""
        d = AE.size_stratum(1000, 4.445, 1.25, z=2.0, n_max=None)
        need = math.ceil((2.0 * 4.445 / 1.25) ** 2)
        assert d["n_needed"] == need == 51
        assert d["n"] == 51
        assert d["binding"] == "power"

    def test_population_regime_binding(self):
        """A population below the power requirement caps n and flags "population"."""
        d = AE.size_stratum(10, 4.445, 1.25, z=2.0, n_max=None)
        assert d["n_needed"] == 51
        assert d["n"] == 10
        assert d["binding"] == "population"

    def test_n_max_regime_binding(self):
        """A compute cap below the power requirement (but not below population) flags
        "n_max", distinct from "population"."""
        d = AE.size_stratum(1000, 4.445, 1.25, z=2.0, n_max=20)
        assert d["n_needed"] == 51
        assert d["n"] == 20
        assert d["binding"] == "n_max"

    def test_mde_at_n_formula(self):
        d = AE.size_stratum(1000, 4.445, 1.25, z=2.0, n_max=None)
        assert d["mde_at_n"] == pytest.approx(2.0 * 4.445 / math.sqrt(d["n"]))

    def test_n_never_exceeds_population(self):
        """Even a huge power requirement cannot select more than the stratum has."""
        d = AE.size_stratum(5, 100.0, 0.001, z=5.0, n_max=None)
        assert d["n"] <= 5
        assert d["binding"] == "population"


# --------------------------------------------------------------------------- #
# 7. allocate_proportional — exact-sum, never-over-supply apportionment         #
# --------------------------------------------------------------------------- #
class TestAllocateProportional:
    def test_shares_sum_exactly_to_min_total_supply(self):
        counts = {"a": 3, "b": 5, "c": 2}
        got = AE.allocate_proportional(counts, 4)
        assert sum(got.values()) == min(4, sum(counts.values()))

    def test_no_share_exceeds_its_supply(self):
        counts = {"a": 3, "b": 5, "c": 2}
        got = AE.allocate_proportional(counts, 100)
        assert all(got[k] <= counts[k] for k in counts)

    def test_total_larger_than_supply_returns_the_whole_supply(self):
        counts = {"a": 3, "b": 2}
        assert AE.allocate_proportional(counts, 100) == counts

    def test_nonpositive_total_returns_all_zero(self):
        counts = {"a": 3, "b": 2}
        assert AE.allocate_proportional(counts, 0) == {"a": 0, "b": 0}
        assert AE.allocate_proportional(counts, -5) == {"a": 0, "b": 0}

    def test_determinism(self):
        counts = {"a": 3, "b": 5, "c": 2}
        assert AE.allocate_proportional(counts, 4) == AE.allocate_proportional(counts, 4)


# --------------------------------------------------------------------------- #
# 8. candidate_plies — the whole disagreement population, unselected on ΔQ      #
# --------------------------------------------------------------------------- #
#: One ply of every excluded kind, plus one fully-eligible ply per actor, so every
#: filter clause in `candidate_plies` is exercised by a single artifact.
_CANDIDATE_PLIES = [
    {"ply": 0, "actor": 0, "action_best": 10, "action_played": 20, "delta_q": 0.1},
    {"ply": 1, "actor": 1, "action_best": 11, "action_played": 21, "delta_q": 0.2},
    {"ply": 2, "actor": 1, "forced": True,
     "action_best": 1, "action_played": 2, "delta_q": 0.1},                       # forced
    {"ply": 3, "actor": 1, "exact": True,
     "action_best": 1, "action_played": 2, "delta_q": 0.1},                       # exact-tail
    {"ply": 4, "actor": 1, "action_best": None, "action_played": 2, "delta_q": 0.1},   # no best
    {"ply": 5, "actor": 1, "action_best": 1, "action_played": None, "delta_q": 0.1},   # no played
    {"ply": 6, "actor": 1, "action_best": 1, "action_played": 2, "delta_q": None},     # no dQ
    {"ply": 7, "actor": 1, "action_best": 1, "action_played": 2, "delta_q": 0.1,
     "played_eligible": False},                                                   # ineligible
    {"ply": 8, "actor": 1, "action_best": 1, "action_played": 2, "delta_q": 0.1,
     "agrees": True},                                                             # agrees
]


class TestCandidatePlies:
    def test_selects_only_valid_disagreement_plies(self):
        """Every exclusion clause is present: wrong actor, forced, exact, missing
        action_best, missing action_played, missing delta_q, played_eligible=False,
        and agrees=True are all dropped; only the fully-eligible actor-1 ply survives."""
        art = {"human_player": 1, "plies": _CANDIDATE_PLIES}
        got = AE.candidate_plies(art)
        assert [p["ply"] for p in got] == [1]

    def test_respects_a_nonzero_human_player(self):
        """human_player is read off the artifact, never hardcoded to seat 0: the SAME
        plies list yields ply 0 (actor 0) under human_player=0, and ply 1 (actor 1)
        under human_player=1."""
        got_hp0 = AE.candidate_plies({"human_player": 0, "plies": _CANDIDATE_PLIES})
        got_hp1 = AE.candidate_plies({"human_player": 1, "plies": _CANDIDATE_PLIES})
        assert [p["ply"] for p in got_hp0] == [0]
        assert [p["ply"] for p in got_hp1] == [1]


# --------------------------------------------------------------------------- #
# 9. census — pure-stdlib stratum counts, marginals, meeple-commit, markdown    #
# --------------------------------------------------------------------------- #
#: Six synthetic disagreement plies spanning DEG/FARM/CITY/ROAD/NEUTRAL (CLOISTER
#: deliberately absent, to also pin the zero-row case), three games, two epochs, and
#: all three meeple_commit directions (hold / spend / swap).
_CENSUS_ROWS = [
    {"stratum": "DEG", "game_label": "g1", "abs_delta_q": 0.5, "phase_third": "opening",
     "decision_type": "tile", "bucket": "blunder", "rules_profile": "fixed_v1",
     "touch_best": ["farm", "cloister"], "touch_played": ["farm", "cloister"],
     "contested_best": ["farm"], "contested_played": [], "degenerate": True,
     "structure": "farm", "meeple_axis": None,
     "move_kind_best": "tile", "move_kind_played": "tile"},
    {"stratum": "FARM", "game_label": "g1", "abs_delta_q": 1.0, "phase_third": "opening",
     "decision_type": "meeple", "bucket": "inaccuracy", "rules_profile": "fixed_v1",
     "touch_best": ["farm"], "touch_played": [],
     "contested_best": [], "contested_played": [], "degenerate": False,
     "structure": "farm", "meeple_axis": "farm->pass",
     "move_kind_best": "farm", "move_kind_played": "pass"},           # champion places, he passes
    {"stratum": "CITY", "game_label": "g2", "abs_delta_q": 2.0, "phase_third": "middle",
     "decision_type": "meeple", "bucket": "blunder", "rules_profile": "walled",
     "touch_best": [], "touch_played": ["city"],
     "contested_best": [], "contested_played": ["city"], "degenerate": False,
     "structure": "city", "meeple_axis": "pass->city",
     "move_kind_best": "pass", "move_kind_played": "city"},           # he places, champion passes
    {"stratum": "ROAD", "game_label": "g2", "abs_delta_q": 0.3, "phase_third": "endgame",
     "decision_type": "meeple", "bucket": "within_noise", "rules_profile": "walled",
     "touch_best": ["road"], "touch_played": ["city"],
     "contested_best": [], "contested_played": [], "degenerate": False,
     "structure": "road", "meeple_axis": "road->city",
     "move_kind_best": "road", "move_kind_played": "city"},           # both place, different targets
    {"stratum": "NEUTRAL", "game_label": "g3", "abs_delta_q": 0.05, "phase_third": "opening",
     "decision_type": "tile", "bucket": "within_noise", "rules_profile": "fixed_v1",
     "touch_best": [], "touch_played": [],
     "contested_best": [], "contested_played": [], "degenerate": False,
     "structure": "neutral", "meeple_axis": None,
     "move_kind_best": "tile", "move_kind_played": "tile"},
    {"stratum": "FARM", "game_label": "g3", "abs_delta_q": 1.5, "phase_third": "middle",
     "decision_type": "tile", "bucket": "blunder", "rules_profile": "fixed_v1",
     "touch_best": ["farm", "city"], "touch_played": ["farm"],
     "contested_best": ["farm"], "contested_played": ["farm"], "degenerate": False,
     "structure": "farm", "meeple_axis": None,
     "move_kind_best": "tile", "move_kind_played": "tile"},
]


class TestCensus:
    def _write(self, tmp_path: Path) -> Path:
        return _write_jsonl(tmp_path / "plies.jsonl", _CENSUS_ROWS)

    def test_stratum_counts_and_disagreement_totals(self, tmp_path):
        p = self._write(tmp_path)
        rep = AE.census([p], tmp_path / "CENSUS.json", tmp_path / "CENSUS.md")
        assert rep["n_disagreements"] == 6
        assert rep["n_games"] == 3
        expect_n = {"DEG": 1, "FARM": 2, "CLOISTER": 0, "CITY": 1, "ROAD": 1, "NEUTRAL": 1}
        for stratum, n in expect_n.items():
            assert rep["by_stratum"][stratum]["n"] == n, stratum
        assert rep["by_stratum"]["FARM"]["mean_abs_delta_q"] == pytest.approx(1.25)
        assert rep["by_stratum"]["CLOISTER"]["mean_abs_delta_q"] is None

    def test_touch_marginals_count_a_ply_once_per_type_either_arm_touches(self, tmp_path):
        p = self._write(tmp_path)
        rep = AE.census([p], tmp_path / "CENSUS.json")
        # row1(DEG): farm,cloister both arms | row2(FARM): farm best-only
        # row3(CITY): city played-only      | row4(ROAD): road best, city played
        # row5(NEUTRAL): nothing            | row6(FARM): farm+city best, farm played
        assert rep["touch_marginals"] == {"farm": 3, "cloister": 1, "city": 3, "road": 1}
        assert rep["contested_marginals"] == {"farm": 2, "cloister": 0, "city": 1, "road": 0}

    def test_meeple_commit_counters(self, tmp_path):
        p = self._write(tmp_path)
        rep = AE.census([p], tmp_path / "CENSUS.json")
        assert rep["meeple_commit"] == {
            "champion_places_he_passes": 1,     # row2: farm->pass
            "he_places_champion_passes": 1,     # row3: pass->city
            "both_place_different_targets": 1,  # row4: road->city
        }

    def test_markdown_file_is_written_and_nonempty(self, tmp_path):
        p = self._write(tmp_path)
        md = tmp_path / "CENSUS.md"
        AE.census([p], tmp_path / "CENSUS.json", md)
        assert md.exists()
        assert md.stat().st_size > 0
        assert "disagreement census" in md.read_text()


# --------------------------------------------------------------------------- #
# 10. sample — power-based draw -> positions jsonl                              #
# --------------------------------------------------------------------------- #
class TestSample:
    """20 FARM-stratum plies (population > power requirement -> genuine sub-selection)
    and 3 CITY-stratum plies (population < --min-n -> underpowered-by-construction).
    All other PRIMARY_STRATA are empty on purpose, so their n is 0 by the population cap
    with no special-casing needed.

    Sizing is pinned at target_effect=1.0, sd_points=2.0, z=2.0 -> n_needed =
    ceil((2*2/1)^2) = 16 exactly (a float-clean boundary, no ceil-rounding ambiguity).
    """

    TARGET_EFFECT = 1.0
    SD_POINTS = 2.0
    Z = 2.0
    MIN_N = 5

    @staticmethod
    def _rows() -> list:
        rows = []
        for i in range(20):
            rows.append({
                "rid": f"farm_g{i % 4}_p{i}", "stratum": "FARM",
                "game_label": f"g{i % 4}", "ply": i,
                "phase_third": ["opening", "middle", "endgame"][i % 3],
                "decision_type": "tile" if i % 2 == 0 else "meeple",
                "commit_direction": ("n/a" if i % 2 == 0
                                     else ["hold", "spend", "swap", "both_pass"][i % 4]),
                "rules_profile": "fixed_v1" if i % 2 == 0 else "walled",
                "bucket": "blunder",
                "action_best": 1000 + i, "action_played": 2000 + i,
                "pick_a": 1000 + i, "pick_b": 2000 + i,
            })
        for i in range(3):
            rows.append({
                "rid": f"city_g{i}_p{i}", "stratum": "CITY",
                "game_label": f"gc{i}", "ply": i,
                "phase_third": "opening", "decision_type": "meeple",
                "commit_direction": "hold", "rules_profile": "fixed_v1",
                "bucket": "inaccuracy",
                "action_best": 5000 + i, "action_played": 6000 + i,
                "pick_a": 5000 + i, "pick_b": 6000 + i,
            })
        return rows

    def _write(self, tmp_path: Path) -> Path:
        return _write_jsonl(tmp_path / "plies.jsonl", self._rows())

    def _run(self, tmp_path: Path, seed: int, inputs_path: Path, tag: str | None = None):
        tag = tag if tag is not None else str(seed)
        out = tmp_path / f"SAMPLE_{tag}.json"
        positions = tmp_path / f"positions_{tag}.jsonl"
        rep = AE.sample([inputs_path], out, positions,
                        target_effect=self.TARGET_EFFECT, sd_points=self.SD_POINTS,
                        z=self.Z, n_max=None, seed=seed, min_n=self.MIN_N)
        return rep, positions

    def test_n_selected_equals_sum_of_per_stratum_sizes(self, tmp_path):
        p = self._write(tmp_path)
        rep, _ = self._run(tmp_path, 20260812, p)
        assert rep["n_selected"] == sum(rep["per_stratum"].values())
        # FARM: pop 20 > need 16 -> power-bound at 16. CITY: pop 3 < need 16 -> all 3.
        assert rep["per_stratum"]["FARM"] == 16
        assert rep["per_stratum"]["CITY"] == 3
        assert rep["n_selected"] == 19

    def test_never_selects_more_than_the_stratum_population(self, tmp_path):
        p = self._write(tmp_path)
        rep, _ = self._run(tmp_path, 1, p)
        assert rep["per_stratum"]["FARM"] <= 20
        assert rep["per_stratum"]["CITY"] <= 3
        for stratum in ("DEG", "CLOISTER", "ROAD", "NEUTRAL"):
            assert rep["per_stratum"][stratum] == 0

    def test_determinism_same_seed_gives_identical_rid_list(self, tmp_path):
        p = self._write(tmp_path)
        _, pos_a = self._run(tmp_path, 42, p, tag="det_a")
        _, pos_b = self._run(tmp_path, 42, p, tag="det_b")
        rids_a = sorted(r["rid"] for r in _read_jsonl(pos_a))
        rids_b = sorted(r["rid"] for r in _read_jsonl(pos_b))
        assert rids_a and rids_a == rids_b

    def test_different_seed_respects_sizes_even_if_rids_differ(self, tmp_path):
        p = self._write(tmp_path)
        rep_a, pos_a = self._run(tmp_path, 20260812, p, tag="seed_a")
        rep_c, pos_c = self._run(tmp_path, 999, p, tag="seed_c")
        # The sizing is a function of population/formula, not of the seed.
        assert rep_a["per_stratum"] == rep_c["per_stratum"]
        rids_a = sorted(r["rid"] for r in _read_jsonl(pos_a))
        rids_c = sorted(r["rid"] for r in _read_jsonl(pos_c))
        # Empirically these two seeds DO draw a different subset of the 20 FARM rows;
        # the contract is "may differ", not "must differ" -- sizes above are the law.
        assert rids_a != rids_c

    def test_per_epoch_positions_files_union_to_positions_jsonl(self, tmp_path):
        p = self._write(tmp_path)
        rep, positions = self._run(tmp_path, 7, p, tag="union")
        master_rows = _read_jsonl(positions)
        master_rids = {r["rid"] for r in master_rows}
        union_rids = set()
        for profile, path_str in rep["positions_files"].items():
            sub_rows = _read_jsonl(Path(path_str))
            assert all(r["rules_profile"] == profile for r in sub_rows)
            union_rids |= {r["rid"] for r in sub_rows}
        assert union_rids == master_rids
        assert sum(len(_read_jsonl(Path(p2))) for p2 in rep["positions_files"].values()) \
            == len(master_rows)

    def test_emitted_rows_carry_the_pick_a_pick_b_sign_contract(self, tmp_path):
        """`oracle_score_pilot`'s position_delta returns mean(V_B - V_A), so pick_a MUST
        be action_best and pick_b MUST be action_played for delta to equal
        V(played) - V(best) — the sign the whole scored readout depends on."""
        p = self._write(tmp_path)
        _, positions = self._run(tmp_path, 7, p, tag="sign")
        rows = _read_jsonl(positions)
        assert rows
        for r in rows:
            assert r["pick_a"] == r["action_best"]
            assert r["pick_b"] == r["action_played"]

    def test_underpowered_strata_flags_the_low_population_stratum(self, tmp_path):
        p = self._write(tmp_path)
        rep, _ = self._run(tmp_path, 7, p, tag="under")
        # CITY has population 3, below --min-n 5 -> flagged regardless of power formula.
        assert "CITY" in rep["underpowered_strata"]
        # FARM's powered n (16) clears --min-n 5 -> NOT flagged.
        assert "FARM" not in rep["underpowered_strata"]


# --------------------------------------------------------------------------- #
# 11. sign contract against the REAL emitted file, if present                   #
# --------------------------------------------------------------------------- #
REAL_PLIES = REPO / "measurement/e4_autopsy_20260812/plies_fixed_v1.jsonl"


@pytest.mark.skipif(not REAL_PLIES.exists(),
                    reason="measurement/e4_autopsy_20260812/plies_fixed_v1.jsonl has not "
                           "been emitted")
class TestSignContractAgainstRealEmittedFile:
    def test_every_row_matches_the_extraction_design(self):
        """Guards that the ON-DISK emission is consistent with the module's own contract:
        arm A is always the champion's pick, arm B is always Joshua's, the two arms are
        never the same action, root_player is his seat, and every row lands in a known
        primary stratum."""
        rows = _read_jsonl(REAL_PLIES)
        assert rows
        for r in rows:
            assert r["pick_a"] == r["action_best"]
            assert r["pick_b"] == r["action_played"]
            assert r["action_best"] != r["action_played"]
            assert r["root_player"] == r["human_player"]
            assert r["stratum"] in AE.PRIMARY_STRATA
