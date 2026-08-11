"""Tests for the JCZ disagreement miner (`scripts/jcz_mining/mine_disagreements.py`).

Pre-registration: `measurement/jcz_mining_20260809/MINING_PREREG.md`.

Every test here exists to catch ONE specific way this instrument could produce a
plausible-but-wrong verdict without crashing. The failure modes, in the order they
are pinned below:

  1. THE `DEAD` PRIMITIVE READING A HARDCODED SCHEDULE. `DEAD` is the whole located
     hole (PREREG §3.0). If it were hardcoded to `{1: 0.5, 2: 0.2}` the stratifier
     would silently mis-split the moment the leaf's `closure_p` changed — and it
     ALREADY HAS: the live production table is `{1: 0.5, 2: 0.2, 3: 0.05}`, so a
     3-open city is LIVE, not DEAD as §3.0's prose example says.
  2. THE STRATUM PREDICATES DRIFTING FROM THE PRE-REGISTERED TEXT — especially the
     two deliberate non-firings (same class + same deadness at a different location
     must NOT fire A) and the `k_remaining <= K_LATE` boundary.
  3. THE CONTROL MATCH SILENTLY BECOMING A CLASS CONTRAST or reusing pool members.
     Without exactness on `ply_class` an A-minus-C contrast reads TILE-vs-MEEPLE;
     without without-replacement the control's n is a lie.
  4. TWO SCORED POSITIONS FROM ONE GAME, which would break the singleton-cluster
     design the CR1 sandwich rests on (PREREG §4).
  5. A PYTHONHASHSEED-SALTED ORDERING, which would make the sample irreproducible
     across processes and boxes while looking perfectly deterministic in one.
  6. THE REPLAYED ROOT NOT BEING THE POSITION JCZ STOOD IN. The alignment gate
     re-inverts JCZ's own wire payload in our independently replayed position; if
     it ever fails, every comparison downstream is between two different positions.
  7. THE ARMS BEING SWAPPED. `position_delta` returns `mean(V_B - V_A)`, so if OUR
     pick were in `pick_b` the sign of the entire readout would flip and the
     decision map would read backwards.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO / "scripts/jcz_mining/mine_disagreements.py"
CORPUS = REPO / "measurement/jcz_match_20260809/confirm.jsonl"

for _p in ("scripts/jcz_mining", "scripts/jcz_match", "scripts/jcz_oracle",
           "scripts/measurement_infra", "scripts/analyzer", "scripts/human_anchor"):
    p = str(REPO / _p)
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load("mine_disagreements", "scripts/jcz_mining/mine_disagreements.py")

#: The schedule PREREG §3.0's worked example assumes. Used as a SYNTHETIC cfg here,
#: deliberately NOT read from production — these tests pin the rule, not the table.
CFG_PREREG = SimpleNamespace(closure_p={1: 0.5, 2: 0.2})
#: A schedule with a third entry: proves the classifier reads the cfg it is given.
CFG_WIDE = SimpleNamespace(closure_p={1: 0.5, 2: 0.2, 3: 0.1})


# --------------------------------------------------------------------------- #
# 1. the DEAD primitive (PREREG §3.0)                                           #
# --------------------------------------------------------------------------- #
class TestDeadBoundaries:
    """Catches: a `DEAD` classifier that is right in the middle and wrong at the
    edges, or one that quietly hardcodes the closure schedule."""

    @pytest.mark.parametrize("open_n,expect_dead", [(1, False), (2, False), (3, True),
                                                    (4, True), (0, True), (-1, True)])
    def test_city_open_n_boundaries(self, open_n, expect_dead):
        assert M.meeple_is_dead("CITY", CFG_PREREG, open_n=open_n) is expect_dead

    def test_finished_city_is_dead_whatever_its_open_n_says(self):
        assert M.meeple_is_dead("CITY", CFG_PREREG, finished=True, open_n=1) is True

    @pytest.mark.parametrize("needed,expect_dead", [(1, False), (2, False), (3, True),
                                                    (0, True), (-2, True)])
    def test_cloister_needed_boundaries(self, needed, expect_dead):
        assert M.meeple_is_dead("CLOISTER", CFG_PREREG, needed=needed) is expect_dead

    def test_farmer_and_road_are_always_dead(self):
        """Farms never close, and open/closed road points are equal — so both are
        priced through `base` alone with no closure term that could see them."""
        assert M.meeple_is_dead("FIELD", CFG_WIDE) is True
        assert M.meeple_is_dead("ROAD", CFG_WIDE) is True

    def test_schedule_is_read_from_the_passed_cfg_not_hardcoded(self):
        """THE test of PREREG §3.0's "never hardcoded" clause. Same `open_n`, two
        configs, opposite answers — which is only possible if the table is read."""
        assert M.meeple_is_dead("CITY", CFG_PREREG, open_n=3) is True
        assert M.meeple_is_dead("CITY", CFG_WIDE, open_n=3) is False
        assert M.meeple_is_dead("CLOISTER", CFG_PREREG, needed=3) is True
        assert M.meeple_is_dead("CLOISTER", CFG_WIDE, needed=3) is False

    def test_a_zero_valued_entry_is_dead_not_live(self):
        """`closure_p.get(n, 0.0) == 0.0` is the rule — an explicit 0.0 entry must
        read the same as a missing one, not as "present therefore live"."""
        cfg = SimpleNamespace(closure_p={1: 0.5, 2: 0.0})
        assert M.meeple_is_dead("CITY", cfg, open_n=2) is True

    def test_unknown_class_raises_rather_than_defaulting(self):
        with pytest.raises(ValueError):
            M.meeple_is_dead("KNIGHT", CFG_PREREG, open_n=1)


# --------------------------------------------------------------------------- #
# 2. the stratum predicates (PREREG §3.1 / §3.2 / §3.3)                          #
# --------------------------------------------------------------------------- #
def _row(dead_o, dead_t, live_o=None, live_t=None, k=10, **kw):
    r = {"dead_vec_ours": dead_o, "dead_vec_theirs": dead_t,
         "live_vec_ours": live_o or [], "live_vec_theirs": live_t or [],
         "k_remaining": k}
    r.update(kw)
    return r


class TestStratumPredicates:
    """Catches: A/B drifting from the pre-registered text, and in particular the
    two NON-firings that keep each stratum from being diluted with the noise the
    candidate terms cannot explain."""

    def test_a_fires_on_a_count_difference(self):
        r = _row({"CITY": 2}, {"CITY": 1})
        assert M.stratum_for(r, 14) == M.STRAT_A

    def test_a_fires_on_a_class_difference_at_equal_count(self):
        """Farmer-vs-knight at the same count is exactly the S4 category-convex
        lock-up discrimination our free-count curve cannot represent."""
        r = _row({"FIELD": 1}, {"ROAD": 1})
        assert M.stratum_for(r, 14) == M.STRAT_A

    def test_a_does_not_fire_on_farmer_here_vs_farmer_there(self):
        """PREREG §3.1's deliberate non-firing: same class, same deadness, different
        LOCATION is a `base`-points discrimination, not a commitment-pricing one."""
        r = _row({"FIELD": 1, "CITY": 1}, {"CITY": 1, "FIELD": 1})
        assert M.stratum_for(r, 14) != M.STRAT_A

    def test_zero_entries_are_not_a_difference(self):
        r = _row({"FIELD": 1, "ROAD": 0}, {"FIELD": 1})
        assert M.stratum_for(r, 14) != M.STRAT_A

    def test_b_fires_only_when_not_a(self):
        """A has precedence: a row whose dead-vecs ALSO differ is A, never B, no
        matter how loudly the live-vecs disagree."""
        r = _row({"CITY": 1}, {"CITY": 2}, [[["CITY", 1], 1]], [[["CITY", 2], 1]], k=5)
        assert M.stratum_for(r, 14) == M.STRAT_A

    def test_b_fires_on_live_vec_difference_when_late(self):
        r = _row({"CITY": 1}, {"CITY": 1}, [[["CITY", 1], 1]], [[["CITY", 2], 1]], k=5)
        assert M.stratum_for(r, 14) == M.STRAT_B

    def test_b_needs_a_live_vec_difference(self):
        r = _row({"CITY": 1}, {"CITY": 1}, [[["CITY", 1], 1]], [[["CITY", 1], 1]], k=5)
        assert M.stratum_for(r, 14) is None

    @pytest.mark.parametrize("k,expect", [(13, "STRAT_B"), (14, "STRAT_B"), (15, None)])
    def test_k_late_boundary_is_inclusive(self, k, expect):
        """`K_LATE = 14` is JCZ's own phase constant (`totalSize > 14` at 2 players),
        so 14 itself is INSIDE the region where their phase behaviour differs."""
        r = _row({}, {}, [[["CITY", 1], 1]], [[["CITY", 2], 1]], k=k)
        got = M.stratum_for(r, 14)
        assert got == (M.STRAT_B if expect else None)

    def test_pool_is_everything_else(self):
        r = _row({"CITY": 1}, {"CITY": 1}, [[["CITY", 1], 1]], [[["CITY", 1], 1]], k=30)
        assert M.stratum_for(r, 14) is None

    def test_live_vec_reads_the_same_before_and_after_a_disk_round_trip(self):
        """The in-process form is a Counter keyed by tuples; the on-disk form is a
        list of `[[class, n], count]`. If the predicate read them differently, a
        stratum could change identity just by being written out and read back."""
        counter = {("CITY", 2): 1, ("CLOISTER", 1): 2}
        as_json = json.loads(json.dumps(M.live_vec_json(counter)))
        assert M.live_vecs_differ(counter, as_json) is False


# --------------------------------------------------------------------------- #
# 3. CONTROL matching (PREREG §3.3)                                             #
# --------------------------------------------------------------------------- #
def _mrow(rid, gap, cls="TILE", game=None, ply=0, phase="EARLY"):
    return {"rid": rid, "root_id": game or rid, "ply": ply,
            "ply_class": cls, "phase_bucket": phase, "our_leaf_gap": gap}


class TestControlMatching:
    """Catches: the control silently becoming a different question — a class
    contrast, a PHASE contrast, a severity contrast, or an n inflated by reuse.

    The two exact-match fields are pinned the same way because they fail the same
    way: a stratum drawing its control from the wrong cell produces a perfectly
    plausible number that answers a different question. STRAT-B is the live case —
    it is late-deck by construction, so an unbucketed control lands mid-game.
    """

    def test_nearest_neighbour_without_replacement_in_descending_target_order(self):
        targets = [_mrow("t1", 0.50), _mrow("t2", 0.10)]
        pool = [_mrow("c1", 0.49), _mrow("c2", 0.48), _mrow("c3", 0.11)]
        got = M.match_control(targets, pool)
        assert [c["rid"] for c in got] == ["c1", "c3"]
        assert got[0]["matched_to"] == "t1" and got[1]["matched_to"] == "t2"
        assert len({c["rid"] for c in got}) == 2          # no reuse

    def test_exactness_on_ply_class_beats_a_closer_gap(self):
        """A MEEPLE pool member sitting exactly on the target's gap must still be
        refused by a TILE target — otherwise A-minus-C reads as TILE-minus-MEEPLE."""
        targets = [_mrow("t1", 0.50, "TILE")]
        pool = [_mrow("m_exact", 0.50, "MEEPLE"), _mrow("t_far", 0.90, "TILE")]
        got = M.match_control(targets, pool)
        assert [c["rid"] for c in got] == ["t_far"]

    def test_exactness_on_phase_bucket_beats_a_closer_gap(self):
        """The STRAT-B confound, pinned: an EARLY pool member sitting exactly on a
        LATE target's gap must still be refused, or the B-minus-C contrast reads
        late-deck-vs-mid-game instead of "their deck-graded closure pricing"."""
        targets = [_mrow("t_late", 0.50, phase="LATE")]
        pool = [_mrow("e_exact", 0.50, phase="EARLY"),
                _mrow("l_far", 0.90, phase="LATE")]
        got = M.match_control(targets, pool)
        assert [c["rid"] for c in got] == ["l_far"]

    def test_exactness_on_phase_bucket_holds_in_the_other_direction(self):
        """Symmetric: an EARLY target must not take a LATE member either, so A
        (mostly EARLY) gets an early-game control rather than borrowing B's."""
        targets = [_mrow("t_early", 0.50, phase="EARLY")]
        pool = [_mrow("l_exact", 0.50, phase="LATE"),
                _mrow("e_far", 0.90, phase="EARLY")]
        got = M.match_control(targets, pool)
        assert [c["rid"] for c in got] == ["e_far"]

    def test_both_exact_fields_apply_together(self):
        """Only the member matching on BOTH is eligible, even when each of the
        three near-misses is closer on `our_leaf_gap` than the eligible one."""
        targets = [_mrow("t", 0.50, cls="TILE", phase="LATE")]
        pool = [_mrow("wrong_class", 0.50, cls="MEEPLE", phase="LATE"),
                _mrow("wrong_phase", 0.51, cls="TILE", phase="EARLY"),
                _mrow("wrong_both", 0.52, cls="MEEPLE", phase="EARLY"),
                _mrow("right", 0.90, cls="TILE", phase="LATE")]
        got = M.match_control(targets, pool)
        assert [c["rid"] for c in got] == ["right"]

    def test_match_key_is_the_documented_pair(self):
        """`STRATA.json` reports `MATCH_KEY` verbatim; if the constant and the
        matcher drifted apart the readout would misdescribe how C was built."""
        assert M.MATCH_KEY == ("ply_class", "phase_bucket")

    def test_phase_bucket_boundary_matches_strat_b_gate(self):
        """The bucket is not a new axis — it is B's own gate, same threshold, same
        inclusive boundary. If they drifted, B's own members could bucket EARLY."""
        assert M.phase_bucket({"k_remaining": 13}, 14) == "LATE"
        assert M.phase_bucket({"k_remaining": 14}, 14) == "LATE"
        assert M.phase_bucket({"k_remaining": 15}, 14) == "EARLY"

    def test_a_target_with_no_same_class_partner_is_skipped_not_cross_matched(self):
        targets = [_mrow("t_meeple", 0.5, "MEEPLE"), _mrow("t_tile", 0.4, "TILE")]
        pool = [_mrow("c_tile", 0.45, "TILE")]
        got = M.match_control(targets, pool)
        assert [c["rid"] for c in got] == ["c_tile"]
        assert got[0]["matched_to"] == "t_tile"

    def test_short_pool_truncates_rather_than_reusing(self):
        got = M.match_control([_mrow("t1", 0.5), _mrow("t2", 0.4)], [_mrow("c1", 0.45)])
        assert len(got) == 1 and got[0]["rid"] == "c1"

    def test_control_honours_one_position_per_game(self):
        """Two pool rows from ONE game can supply at most one control position."""
        targets = [_mrow("t1", 0.5), _mrow("t2", 0.4)]
        pool = [_mrow("c1", 0.50, game="G", ply=1), _mrow("c2", 0.40, game="G", ply=2)]
        got = M.match_control(targets, pool)
        assert len(got) == 1 and got[0]["rid"] == "c1"

    def test_already_claimed_games_are_refused(self):
        targets = [_mrow("t1", 0.5)]
        pool = [_mrow("c1", 0.50, game="G"), _mrow("c2", 0.30, game="H")]
        got = M.match_control(targets, pool, claimed={"G"})
        assert [c["rid"] for c in got] == ["c2"]

    def test_match_gap_diff_is_recorded_for_the_diagnostics(self):
        got = M.match_control([_mrow("t1", 0.50)], [_mrow("c1", 0.42)])
        assert got[0]["match_gap_diff"] == pytest.approx(0.08)


# --------------------------------------------------------------------------- #
# 4. sampling: one position per game, A before B before C (PREREG §4)            #
# --------------------------------------------------------------------------- #
def _cand(rid, game, ply, *, cls="TILE", gap=1.0, k=10, seat=0,
          dead_o=None, dead_t=None, live_o=None, live_t=None):
    return {
        "rid": rid, "root_id": game, "game_label": game,
        "deck_seed": 100 + int(ply), "champ_seat": 1 - int(seat), "jcz_seat": int(seat),
        "ply": int(ply), "root_player": int(seat), "actions": [1, 2, 3, 4, 5, 6],
        "ply_class": cls, "pick_a": 11, "pick_b": 22, "n_legal": 5,
        "k_remaining": int(k), "leaf_ours": gap, "leaf_theirs": 0.0,
        "our_leaf_gap": float(gap), "leaf_tie": False,
        "dead_vec_ours": dead_o if dead_o is not None else {"CITY": 1},
        "dead_vec_theirs": dead_t if dead_t is not None else {"CITY": 1},
        "live_vec_ours": live_o or [], "live_vec_theirs": live_t or [],
        "merge_exposure_differs": False, "chain_ours": [11], "chain_theirs": [22],
        "rules_profile": "fixed_v1", "search_pick": None, "stratum": None,
    }


def _a(rid, game, ply, **kw):
    return _cand(rid, game, ply, dead_o={"CITY": 2}, dead_t={"CITY": 1}, **kw)


def _b(rid, game, ply, **kw):
    kw.setdefault("k", 5)
    return _cand(rid, game, ply, live_o=[[["CITY", 1], 1]], live_t=[[["CITY", 2], 1]], **kw)


def _pool(rid, game, ply, **kw):
    # k defaults LATE so the synthetic pool can actually supply controls for the
    # synthetic (LATE) targets — the matcher is exact on `phase_bucket`.
    kw.setdefault("k", 10)
    return _cand(rid, game, ply, **kw)


def _write(tmp_path, rows, name="cand.jsonl"):
    p = tmp_path / name
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


class TestSamplingClaimsGamesInOrder:
    """Catches: two scored positions from one game (which would break the
    singleton-cluster design the CR1 sandwich rests on), and a precedence order
    that lets B or C poach a game A wanted."""

    def _assign(self, tmp_path, rows, **kw):
        cand = _write(tmp_path, rows)
        kw.setdefault("k_late", 14)
        kw.setdefault("n_target", 5)
        kw.setdefault("min_n", 1)
        return M.assign(cand, tmp_path / "STRATA.json", tmp_path / "pos.jsonl", **kw)

    def test_no_game_supplies_two_scored_positions(self, tmp_path, capsys):
        rows = [_a("a1", "G1", 1), _b("b1", "G1", 2), _pool("p1", "G1", 3),
                _b("b2", "G2", 1), _pool("p2", "G2", 2),
                _pool("p3", "G3", 1), _pool("p4", "G4", 1),
                _a("a2", "G5", 1)]
        st = self._assign(tmp_path, rows)
        scored = st["rows"][M.STRAT_A] + st["rows"][M.STRAT_B] + st["rows"][M.STRAT_C]
        games = [r["root_id"] for r in scored]
        assert len(games) == len(set(games)), f"a game was scored twice: {games}"

    def test_a_claims_before_b_and_b_before_c(self, tmp_path, capsys):
        rows = [_a("a1", "G1", 1), _b("b1", "G1", 2),      # A must win G1
                _b("b2", "G2", 1), _pool("p2", "G2", 2),   # B must win G2
                _pool("p3", "G3", 1)]                      # only G3 is left for C
        st = self._assign(tmp_path, rows)
        assert [r["root_id"] for r in st["rows"][M.STRAT_A]] == ["G1"]
        assert [r["root_id"] for r in st["rows"][M.STRAT_B]] == ["G2"]
        assert [r["root_id"] for r in st["rows"][M.STRAT_C]] == ["G3"]

    def test_gate_is_recorded_and_drives_the_exit_code(self, tmp_path):
        rows = [_a(f"a{i}", f"G{i}", 1) for i in range(3)]
        cand = _write(tmp_path, rows)
        rc = M.main(["assign", "--candidates", str(cand),
                     "--out", str(tmp_path / "S.json"),
                     "--positions", str(tmp_path / "p.jsonl"), "--min-n", "25"])
        assert rc == 3
        assert json.loads((tmp_path / "S.json").read_text())["gate_ok"] is False

    def test_positions_files_split_ab_from_c(self, tmp_path, capsys):
        rows = [_a("a1", "G1", 1), _b("b1", "G2", 1), _pool("p1", "G3", 1),
                _pool("p2", "G4", 1)]
        self._assign(tmp_path, rows)
        allrows = [json.loads(x) for x in (tmp_path / "pos.jsonl").read_text().splitlines()]
        ab = [json.loads(x) for x in (tmp_path / "pos_AB.jsonl").read_text().splitlines()]
        assert {r["stratum"] for r in ab} <= {M.STRAT_A, M.STRAT_B}
        assert M.STRAT_C in {r["stratum"] for r in allrows}
        assert len(ab) < len(allrows)

    def test_phase_bucket_is_stamped_and_reported(self, tmp_path, capsys):
        """`phase_bucket` is a function of `k_late`, an `assign` parameter — so it
        must be stamped at assign time and travel on every emitted row, or the
        readout cannot say what C was matched on."""
        rows = [_a("a1", "G1", 1, k=5), _a("a2", "G2", 1, k=30),
                _pool("p1", "G3", 1, k=5), _pool("p2", "G4", 1, k=30)]
        st = self._assign(tmp_path, rows)
        for r in st["rows"][M.STRAT_A] + st["rows"][M.STRAT_C]:
            assert r["phase_bucket"] == ("LATE" if r["k_remaining"] <= 14 else "EARLY")
        assert st["control_match"]["match_key"] == ["ply_class", "phase_bucket"]
        assert st["strata"][M.STRAT_A]["by_phase_bucket"] == {"LATE": 1, "EARLY": 1}

    def test_control_is_phase_matched_to_its_target(self, tmp_path, capsys):
        """The end-to-end version of the STRAT-B confound: a LATE stratum must draw
        a LATE control even when an EARLY pool member has a much closer gap."""
        rows = [_b("b1", "G1", 1, k=5, gap=1.0),
                _pool("near_early", "G2", 1, k=30, gap=1.0),
                _pool("far_late", "G3", 1, k=6, gap=9.0)]
        st = self._assign(tmp_path, rows)
        assert [r["rid"] for r in st["rows"][M.STRAT_C]] == ["far_late"]
        assert st["strata"][M.STRAT_C]["by_phase_bucket"] == {"LATE": 1}

    def test_seat_balance_is_within_one_when_the_pool_allows(self, tmp_path, capsys):
        rows = [_a(f"a{i}", f"G{i}", 1, seat=i % 2) for i in range(8)]
        st = self._assign(tmp_path, rows, n_target=4)
        seats = st["strata"][M.STRAT_A]["by_jcz_seat"]
        assert abs(seats.get("0", 0) - seats.get("1", 0)) <= 1

    def test_a_one_sided_stratum_still_reaches_n_target(self, tmp_path, capsys):
        """Balance is a preference, not a cap: if every candidate is one seat the
        stratum must still fill, otherwise the run silently comes in under n."""
        rows = [_a(f"a{i}", f"G{i}", 1, seat=0) for i in range(6)]
        st = self._assign(tmp_path, rows, n_target=4)
        assert st["strata"][M.STRAT_A]["n"] == 4


# --------------------------------------------------------------------------- #
# 4b. the search-pick backfill (PREREG §2.1 / §3.4, context-only column)          #
# --------------------------------------------------------------------------- #
class TestSearchPickBackfill:
    """Catches: a backfill that silently perturbs the sampling frame.

    `search-pick` rewrites STRATA.json and both positions files IN PLACE after the
    frame has been assigned and committed. If it reordered a row, coerced an int,
    or dropped a key, the damage would not look like an error — it would look like
    a result, because the scorer would simply score a slightly different frame.
    The engine is stubbed here so these pin the PLUMBING, not the champion.
    """

    def _build(self, tmp_path):
        rows = [_a("a1", "G1", 1, gap=3.0), _a("a2", "G2", 1, gap=2.0),
                _b("b1", "G3", 1, gap=1.5), _pool("p1", "G4", 1, gap=2.5),
                _pool("p2", "G5", 1, gap=1.4)]
        cand = _write(tmp_path, rows)
        M.assign(cand, tmp_path / "S.json", tmp_path / "pos.jsonl",
                 k_late=14, n_target=5, min_n=1)
        return tmp_path / "S.json", tmp_path / "pos.jsonl", tmp_path / "pos_AB.jsonl"

    @staticmethod
    def _stub(picks_by_rid, monkeypatch, err_for=()):
        def fake(item):
            rid = item[0]
            if rid in err_for:
                return rid, None, "RuntimeError: stubbed failure"
            return rid, picks_by_rid.get(rid, 999), None
        monkeypatch.setattr(M, "_sp_cell", fake)
        monkeypatch.setattr(M, "_sp_init", lambda: None)

    def test_only_the_two_backfill_fields_change(self, tmp_path, monkeypatch, capsys):
        S, P, AB = self._build(tmp_path)
        before_rows = [json.loads(x) for x in P.read_text().splitlines() if x.strip()]
        before_frames = {r["rid"]: M._frame_of(r) for r in before_rows}
        before_strata = json.loads(S.read_text())

        self._stub({r["rid"]: 4242 for r in before_rows}, monkeypatch)
        M.search_pick_backfill(S, P, AB, workers=1)

        after_rows = [json.loads(x) for x in P.read_text().splitlines() if x.strip()]
        assert [r["rid"] for r in after_rows] == [r["rid"] for r in before_rows]
        for r in after_rows:
            assert r["search_pick"] == 4242
            assert M._frame_of(r) == before_frames[r["rid"]]
        after_strata = json.loads(S.read_text())
        for k in (M.STRAT_A, M.STRAT_B, M.STRAT_C):
            for b, a in zip(before_strata["rows"][k], after_strata["rows"][k]):
                assert M._frame_of(a) == M._frame_of(b)
        # every non-`rows` key of STRATA.json survives, plus one additive summary
        assert set(after_strata) - set(before_strata) == {"search_pick_backfill"}

    def test_a_second_run_is_a_no_op(self, tmp_path, monkeypatch, capsys):
        """Idempotence is what makes this resumable: a run interrupted halfway must
        be re-runnable without recomputing (or re-deciding) anything already done."""
        S, P, AB = self._build(tmp_path)
        self._stub({}, monkeypatch)
        M.search_pick_backfill(S, P, AB, workers=1)
        first = (json.loads(S.read_text())["rows"], P.read_bytes(), AB.read_bytes())
        summary = M.search_pick_backfill(S, P, AB, workers=1)
        assert summary["n_computed_this_run"] == 0
        # The ROWS and both positions files are byte-identical. The only thing that
        # legitimately moves is the run's own bookkeeping in the additive top-level
        # `search_pick_backfill` block (`n_computed_this_run`, `wall_secs`).
        assert (json.loads(S.read_text())["rows"], P.read_bytes(), AB.read_bytes()) == first

    def test_a_failing_row_is_recorded_and_retried_not_fatal(self, tmp_path,
                                                             monkeypatch, capsys):
        """Best-effort by contract: the column must never be able to block the run.
        A null pick stays in the todo set, so the next run retries it."""
        S, P, AB = self._build(tmp_path)
        rids = [r["rid"] for r in json.loads(S.read_text())["rows"][M.STRAT_A]]
        self._stub({}, monkeypatch, err_for={rids[0]})
        summary = M.search_pick_backfill(S, P, AB, workers=1)
        assert summary["n_errors"] == 1
        assert summary["n_with_search_pick"] == summary["n_sampled"] - 1
        bad = next(r for r in json.loads(S.read_text())["rows"][M.STRAT_A]
                   if r["rid"] == rids[0])
        assert bad["search_pick"] is None and "stubbed failure" in bad["search_pick_error"]
        self._stub({rids[0]: 7}, monkeypatch)
        again = M.search_pick_backfill(S, P, AB, workers=1)
        assert again["n_computed_this_run"] == 1 and again["n_errors"] == 0

    def test_files_still_load_through_the_scorer_loader(self, tmp_path, monkeypatch,
                                                        capsys):
        S, P, AB = self._build(tmp_path)
        self._stub({}, monkeypatch)
        M.search_pick_backfill(S, P, AB, workers=1)
        OSP = _load("oracle_score_pilot", "scripts/measurement_infra/oracle_score_pilot.py")
        for p in (P, AB):
            rows = OSP.load_positions_jsonl(p)
            assert rows and len({r["rid"] for r in rows}) == len(rows)

    def test_ab_path_is_derived_when_not_given(self, tmp_path, monkeypatch, capsys):
        S, P, AB = self._build(tmp_path)
        self._stub({}, monkeypatch)
        summary = M.search_pick_backfill(S, P, None, workers=1)
        assert [f["path"] for f in summary["positions_files"]] == [str(P), str(AB)]

    def test_frame_guard_fires_on_a_perturbation(self):
        """The guard itself, in isolation — it is the one thing standing between a
        buggy rewrite and a silently re-sampled frame."""
        before = [{"rid": "x", "ply": 3}, {"rid": "y", "ply": 4}]
        M.assert_frame_unchanged(before, [dict(r) for r in before], "ok")
        with pytest.raises(AssertionError):
            M.assert_frame_unchanged(before, [{"rid": "x", "ply": 3}, {"rid": "y", "ply": 5}], "w")
        with pytest.raises(AssertionError):
            M.assert_frame_unchanged(before, [{"rid": "x", "ply": 3}], "w")
        with pytest.raises(AssertionError):
            M.assert_frame_unchanged(before, [{"rid": "x"}, {"rid": "y", "ply": 4}], "w")

    def test_backfill_fields_are_exactly_the_two(self):
        assert M.BACKFILL_FIELDS == ("search_pick", "search_pick_error")
        assert M._frame_of({"a": 1, "search_pick": 2, "search_pick_error": "e"}) == {"a": 1}


@pytest.mark.skipif(not CORPUS.exists(), reason="the n=400 JCZ match corpus is not on disk")
class TestSearchPickRealRoots:
    """The engine leg, deliberately at FIXTURE SCALE (2 games -> a couple of rows,
    a few seconds of champion search). Catches: the backfill replaying the root by
    a different path from `extract`/the scorer, which would silently make the
    context column describe a different position from the one being scored."""

    def test_backfill_computes_a_real_pick_and_preserves_the_frame(self, tmp_path):
        out, rows, _meta = _run_extract(tmp_path, 2)
        M.assign(out, tmp_path / "S.json", tmp_path / "pos.jsonl",
                 k_late=14, n_target=2, min_n=1)
        S = tmp_path / "S.json"
        before = {r["rid"]: M._frame_of(r)
                  for k in (M.STRAT_A, M.STRAT_B, M.STRAT_C)
                  for r in json.loads(S.read_text())["rows"][k]}
        assert 0 < len(before) <= 6, f"fixture scale guard: {len(before)} rows"

        r = subprocess.run(
            [sys.executable, str(MODULE_PATH), "search-pick", "--strata", str(S),
             "--positions", str(tmp_path / "pos.jsonl")],
            capture_output=True, text=True, cwd=str(REPO))
        assert r.returncode == 0, r.stderr

        strata = json.loads(S.read_text())
        got = [x for k in (M.STRAT_A, M.STRAT_B, M.STRAT_C) for x in strata["rows"][k]]
        assert strata["search_pick_backfill"]["n_errors"] == 0, [
            x["search_pick_error"] for x in got if x.get("search_pick_error")]
        for x in got:
            assert isinstance(x["search_pick"], int)
            assert M._frame_of(x) == before[x["rid"]]
        s = strata["search_pick_backfill"]
        assert s["search_agrees_with_ours"] + s["search_agrees_with_theirs"] \
            + s["search_agrees_with_neither"] == s["n_with_search_pick"]


# --------------------------------------------------------------------------- #
# 5. determinism                                                                #
# --------------------------------------------------------------------------- #
class TestDeterminism:
    """Catches: a PYTHONHASHSEED-salted ordering. It looks perfectly deterministic
    inside one process and silently re-samples on the next box."""

    def test_sha_int_is_sha256_derived_not_python_hash(self):
        import hashlib
        want = int.from_bytes(
            hashlib.sha256("a|1|2".encode()).digest()[:8], "big") & 0x7FFFFFFF
        assert M._sha_int("a", 1, 2) == want

    def test_sha_int_matches_the_house_helper(self):
        """`oracle_score_pilot` derives the CRN world seeds the same way; if these
        two ever diverged the artifacts would stop being comparable."""
        OSP = _load("oracle_score_pilot", "scripts/measurement_infra/oracle_score_pilot.py")
        assert M._sha_int("world", "r", 3) == OSP._sha_int("world", "r", 3)

    def test_assign_is_byte_identical_across_hash_seeds(self, tmp_path):
        rows = ([_a(f"a{i}", f"GA{i}", 1, gap=1.0 + i, seat=i % 2) for i in range(6)]
                + [_b(f"b{i}", f"GB{i}", 1, gap=0.5 + i, seat=i % 2) for i in range(6)]
                + [_pool(f"p{i}", f"GP{i}", 1, gap=0.4 + i, seat=i % 2) for i in range(12)])
        cand = _write(tmp_path, rows)
        outs = []
        for seed in ("0", "1", "12345"):
            d = tmp_path / f"run{seed}"
            d.mkdir()
            env = {**os.environ, "PYTHONHASHSEED": seed}
            r = subprocess.run(
                [sys.executable, str(MODULE_PATH), "assign", "--candidates", str(cand),
                 "--out", str(d / "S.json"), "--positions", str(d / "p.jsonl"),
                 "--n-target", "3", "--min-n", "1"],
                capture_output=True, text=True, env=env, cwd=str(REPO))
            assert r.returncode == 0, r.stderr
            # The only legitimate per-run difference is the output PATH the artifact
            # stamps, which is a property of the invocation, not of the sampling.
            outs.append(((d / "S.json").read_text().replace(str(d), "<OUT>"),
                         (d / "p.jsonl").read_text()))
        assert outs[0] == outs[1] == outs[2]

    def test_rerunning_assign_in_place_reproduces_the_same_bytes(self, tmp_path):
        rows = [_a(f"a{i}", f"G{i}", 1, gap=float(i)) for i in range(5)]
        cand = _write(tmp_path, rows)
        first = None
        for _ in range(2):
            M.assign(cand, tmp_path / "S.json", tmp_path / "p.jsonl",
                     k_late=14, n_target=3, min_n=1)
            got = ((tmp_path / "S.json").read_bytes(), (tmp_path / "p.jsonl").read_bytes())
            first = got if first is None else first
            assert got == first


# --------------------------------------------------------------------------- #
# 6/7. the real corpus: alignment, invariants, and the sign convention            #
# --------------------------------------------------------------------------- #
SUB_SIGN = r"""
import json, sys, importlib.util
mod_path, cand_path = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("M", mod_path)
M = importlib.util.module_from_spec(spec); sys.modules["M"] = M; spec.loader.exec_module(M)
M.prepare_env()                       # rules + leaf env BEFORE carcassonne_ai
import root_replay as RR
from carcassonne_ai import champion_factory as CF, flat_leaf, rules_profile
prof = rules_profile.activate("fixed_v1")
cfg = CF.production_leaf_cfg(); CF.verify_leaf(cfg)
bag = bool(getattr(cfg, "bag_close", False))
out = []
rows = [json.loads(l) for l in open(cand_path) if l.strip()][:6]
for row in rows:
    seat = int(row["jcz_seat"])
    g, board = RR.replay_actions(row["deck_seed"], row["actions"], row["ply"],
                                 game_kwargs=prof.game_kwargs())
    leaf = lambda st: float(flat_leaf.flat_virtual_score_v2_float(st, seat, cfg, bag))
    vals = M.chain_values(g, board, seat, leaf, row["ply_class"])
    pick, v, chain, tie = M.argmax_chain(vals)
    out.append({"rid": row["rid"], "pick": int(pick), "leaf": v,
                "chain": [int(a) for a in chain], "tie": bool(tie),
                "current_player": int(board.state.current_player)})
print(json.dumps(out))
"""


def _run_extract(tmp_path, n_games: int):
    out = tmp_path / "cand.jsonl"
    r = subprocess.run(
        [sys.executable, str(MODULE_PATH), "extract", "--corpus", str(CORPUS),
         "--out", str(out), "--limit-games", str(n_games)],
        capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    rows = [json.loads(x) for x in out.read_text().splitlines() if x.strip()]
    meta = json.loads(out.with_suffix(".meta.json").read_text())
    return out, rows, meta


@pytest.mark.skipif(not CORPUS.exists(), reason="the n=400 JCZ match corpus is not on disk")
class TestRealCorpusPin:
    """Catches: a replayed root that is NOT the position JCZ stood in, and any
    invariant of the emitted row breaking silently on real data.

    `extract` runs in a SUBPROCESS on purpose — `CARCASSONNE_FIX_R9` is an
    import-time latch, so a test process that has already imported the engine at
    the default profile could not run it honestly.
    """

    @pytest.fixture(scope="class")
    def run(self, tmp_path_factory):
        return _run_extract(tmp_path_factory.mktemp("extract3"), 3)

    def test_the_alignment_gate_passed_on_every_checked_ply(self, run):
        """THE free ground-truth check: JCZ's own wire payload, re-inverted in our
        independently replayed position, must yield the action the archive recorded.
        A single failure means our replay and their game had parted."""
        _out, _rows, meta = run
        assert meta["alignment_checked"] > 0
        assert meta["alignment_failed"] == 0, meta["alignment_failures"]
        assert meta["alignment_ok"] == meta["alignment_checked"]
        assert meta["games_skipped_alignment"] == 0
        assert meta["games_used"] == 3

    def test_every_emitted_row_is_a_real_disagreement(self, run):
        _out, rows, _meta = run
        assert rows
        for r in rows:
            assert r["pick_a"] != r["pick_b"]
            assert r["leaf_tie"] is False
            assert r["n_legal"] >= 2
            assert r["root_player"] == r["jcz_seat"]
            assert r["ply_class"] in ("TILE", "MEEPLE")
            assert r["rules_profile"] == "fixed_v1"
            assert r["stratum"] is None
            assert r["rid"] == f"{r['deck_seed']}_{r['champ_seat']}_p{r['ply']}"
            assert r["root_id"] == r["game_label"] == f"{r['deck_seed']}_{r['champ_seat']}"

    def test_our_leaf_gap_is_non_negative_by_construction(self, run):
        """Our chain argmax ranges over a space containing THEIR chain, so a
        negative gap would mean the two arms are not in the same chain space —
        which would make the CONTROL match (which matches on this quantity)
        meaningless."""
        _out, rows, _meta = run
        for r in rows:
            assert r["our_leaf_gap"] >= -M.GAP_EPS
            assert r["our_leaf_gap"] == pytest.approx(r["leaf_ours"] - r["leaf_theirs"])

    def test_chains_have_the_pre_registered_shape(self, run):
        _out, rows, _meta = run
        for r in rows:
            assert r["chain_ours"][0] == r["pick_a"]
            assert r["chain_theirs"][0] == r["pick_b"]
            assert len(r["chain_ours"]) == len(r["chain_theirs"]), (
                "the two arms must run to the same point in the turn, or the leaf "
                "comparison is mid-turn against end-of-turn")
            if r["ply_class"] == "MEEPLE":
                assert len(r["chain_ours"]) == 1

    def test_rows_round_trip_through_the_scorer_loader(self, run):
        out, rows, _meta = run
        OSP = _load("oracle_score_pilot", "scripts/measurement_infra/oracle_score_pilot.py")
        loaded = OSP.load_positions_jsonl(out)     # raises on a duplicate rid
        assert len(loaded) == len(rows)
        assert len({r["rid"] for r in loaded}) == len(loaded)
        for r in loaded:
            assert r["actions"] and 0 <= r["ply"] < len(r["actions"])
            assert isinstance(r["root_id"], str)

    def test_meta_records_the_schedule_it_actually_ran_under(self, run):
        """PREREG §3.0 mandates reading `closure_p` from the loaded config. The meta
        must therefore stamp the RESOLVED table, so a readout can never quote the
        prose's assumed schedule instead of the one that classified the meeples."""
        _out, _rows, meta = run
        assert meta["closure_p"], "the resolved closure schedule is not stamped"
        assert meta["leaf_cfg_hash"]

    def test_counts_is_a_pure_dry_run_over_the_real_rows(self, run):
        out, rows, _meta = run
        frame = M.count_frame(rows, 14)
        assert frame["n_candidates"] == len(rows)
        totals = sum(frame["strata"][k]["n"] for k in (M.STRAT_A, M.STRAT_B, "POOL"))
        assert totals == len(rows), "the three buckets must partition the candidates"
        assert set(frame["strat_b_ladder"]) == {"14", "20", "28"}


@pytest.mark.skipif(not CORPUS.exists(), reason="the n=400 JCZ match corpus is not on disk")
class TestSignConvention:
    """Catches: the arms being swapped. `oracle_score_pilot.position_delta` returns
    `mean(V_B - V_A)`, so `pick_a` MUST be OURS and `pick_b` THEIRS for the reported
    Δ to read "their pick minus our pick" (PREREG §5). If they were swapped every
    verdict in the decision map would invert while every number stayed plausible."""

    def test_pick_a_is_our_leaf_argmax_re_derived_from_scratch(self, tmp_path):
        out, rows, _meta = _run_extract(tmp_path, 1)
        assert rows
        r = subprocess.run([sys.executable, "-c", SUB_SIGN, str(MODULE_PATH), str(out)],
                           capture_output=True, text=True, cwd=str(REPO))
        assert r.returncode == 0, r.stderr
        got = json.loads(r.stdout.strip().splitlines()[-1])
        assert got
        by_rid = {x["rid"]: x for x in got}
        for row in rows[:len(got)]:
            g = by_rid[row["rid"]]
            assert g["pick"] == row["pick_a"], (
                "the re-derived leaf argmax must be pick_a (OURS); if it came back "
                "equal to pick_b the arms are swapped and every Δ reads backwards")
            assert g["pick"] != row["pick_b"]
            assert g["tie"] is False
            assert g["current_player"] == row["jcz_seat"]
            assert g["leaf"] == pytest.approx(row["leaf_ours"])
            assert g["chain"] == row["chain_ours"]
