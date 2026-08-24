"""Contracts for `scripts/tiletie/build_everyply_plan.py` — the EVERY-PLY probe's
sampling frame, allocation, seeded draw and committed order.

Unit tests only. No engine, no champion, no judge, no subprocess, no oracle value.
Two classes of test:

  1. **Arithmetic against the design's own published numbers.** Every expected
     figure below is copied from `measurement/everyply_probe_20260823/DESIGN.md`
     (itself transcribed from `measurement/everyply_probe_plan_20260823/PLAN.md`),
     so the estimator is checked against the pre-registered arithmetic rather than
     against itself. If the builder and the DESIGN ever disagree, these fail.
  2. **Structural properties** the READ_RULE's gates assume — the chunk partition,
     the per-game cap, the holdout disjointness, determinism under a fixed seed.

Covers:
  * the §2.1/§2.2 frame reproduced off the TRACKED census (the `G-FRAME` substrate)
  * gap-cut boundaries, including the half-open convention at 0.25 and 1.5
  * largest-remainder allocation, incl. the DESIGN's own n=900 -> 225/337/338
  * the §2.3 variance price sum(w^2/f), incl. the REJECTED f=(0.40,0.30,0.30)
  * `chunk_slices` exact partition (the unbiased-prefix property)
  * the global per-game cap and the single-shuffle cross-stratum fairness
  * the seeded holdout split over the CLUSTER unit
  * the §7.1 se(kappa) table, cell for cell, at n in {400,600,900} x q in {.5,.76,.9}
  * the §6.3 reachability thresholds that the branch table's arithmetic rests on,
    incl. the declared `UB95 := kappa_hat + 2.0*se` convention
  * the §5 SIZE-1 cost headline 16.2 / 22.3 / 29.1 worker-h
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "scripts" / "tiletie",):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import build_everyply_plan as EP  # noqa: E402

CENSUS = REPO / "measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl"


# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #
def _row(game_id, ply, gap, *, tie=False, n_legal=10, phase="mid"):
    return {
        "ply_class": "TILE", "corpus": "synthetic",
        "game_id": game_id, "deck_seed": game_id, "ply": ply,
        "seat": ply % 2, "k_remaining": 40, "phase_bucket": phase,
        "n_legal": n_legal, "top1": gap + 1.0, "top2": 1.0, "gap": gap,
        "tie_exact": tie, "tie_size_exact": 1,
    }


@pytest.fixture(scope="module")
def real_rows():
    if not CENSUS.is_file():
        pytest.skip(f"tracked census absent: {CENSUS}")
    return EP.load_census(CENSUS)


def _synthetic(n_games=60, per_game=12):
    """A census with a known A/B/C mix and plenty of per-game supply."""
    rows, gaps = [], [0.1, 0.2, 0.4, 0.8, 1.2, 1.4, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    for g in range(n_games):
        for p in range(per_game):
            rows.append(_row(1000 + g, p, gaps[p % len(gaps)]))
    return rows


# --------------------------------------------------------------------------- #
# 1. the frame, off the tracked census                                         #
# --------------------------------------------------------------------------- #
def test_frame_reproduces_design_population_table(real_rows):
    """DESIGN §2.1 — the numbers the whole design is sized on."""
    r = EP.frame_report(real_rows)
    assert r["tile_plies"] == 31827
    assert r["games"] == 449
    assert r["tied_exact"] == 20322
    assert r["nontied"] == 11505
    assert r["nontied_forced_n_legal_lt_2"] == 0
    assert r["tied_exact"] + r["nontied"] == r["tile_plies"]


def test_frame_reproduces_design_strata(real_rows):
    """DESIGN §2.2 — 1,147 / 4,936 / 5,422 and their shares."""
    r = EP.frame_report(real_rows)
    assert r["strata"]["A"]["n"] == 1147
    assert r["strata"]["B"]["n"] == 4936
    assert r["strata"]["C"]["n"] == 5422
    assert sum(r["strata"][s]["n"] for s in EP.STRATA) == r["nontied"]
    assert r["strata"]["A"]["share_of_nontied"] == pytest.approx(0.0997, abs=5e-4)
    assert r["strata"]["B"]["share_of_nontied"] == pytest.approx(0.4290, abs=5e-4)
    assert r["strata"]["C"]["share_of_nontied"] == pytest.approx(0.4713, abs=5e-4)


def test_frame_reproduces_per_game_per_seat_and_n_legal(real_rows):
    """DESIGN §2.1/§2.2: 12.81 non-tied plies/game/seat; stratum A 1.277; mean n_legal 27.55."""
    r = EP.frame_report(real_rows)
    assert r["per_game"]["nontied_per_seat"] == pytest.approx(12.81, abs=0.01)
    assert r["strata"]["A"]["per_game_per_seat"] == pytest.approx(1.277, abs=0.002)
    assert r["n_legal"]["mean"] == pytest.approx(27.55, abs=0.01)
    assert r["n_legal"]["median"] == 27
    assert r["n_legal"]["max"] == 88


def test_frame_reproduces_design_gap_cdf(real_rows):
    """DESIGN §2.2's supporting CDF over the non-tied class."""
    cdf = EP.frame_report(real_rows)["gap_cdf_over_nontied"]
    for cut, want in (("0.05", 0.0116), ("0.1", 0.0287), ("0.25", 0.0997),
                      ("0.5", 0.1787), ("1.0", 0.4008), ("1.5", 0.5287),
                      ("2.0", 0.6189), ("3.0", 0.7501), ("5.0", 0.8708)):
        assert cdf[cut] == pytest.approx(want, abs=5e-4), cut


def test_assert_frame_refuses_a_changed_census():
    """The design cannot be silently re-based by an edited census."""
    with pytest.raises(SystemExit, match="no longer reproduces"):
        EP.assert_frame(EP.frame_report(_synthetic()))


def test_rid_is_unique_over_the_whole_census(real_rows):
    rids = [EP.rid_of(r) for r in real_rows]
    assert len(rids) == len(set(rids))


# --------------------------------------------------------------------------- #
# 2. stratum cuts                                                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("gap,want", [
    (0.01, "A"), (0.25, "A"),            # upper edge of A is CLOSED
    (0.2500001, "B"), (1.0, "B"), (1.5, "B"),   # upper edge of B is CLOSED
    (1.5000001, "C"), (99.0, "C"),
])
def test_stratum_cut_boundaries(gap, want):
    assert EP.stratum_of(gap) == want


@pytest.mark.parametrize("gap", [0.0, -1.0])
def test_stratum_rejects_non_positive_gap(gap):
    """The non-tied class has gap > 0 by construction; a zero is an instrument defect."""
    with pytest.raises(ValueError):
        EP.stratum_of(gap)


def test_nontied_filters_ties_and_forced_plies():
    rows = [_row(1, 0, 1.0), _row(1, 1, 0.0, tie=True), _row(1, 2, 1.0, n_legal=1)]
    assert [EP.rid_of(r) for r in EP.nontied_rows(rows)] == ["ep_1_0"]


# --------------------------------------------------------------------------- #
# 3. allocation and the variance price                                         #
# --------------------------------------------------------------------------- #
def test_allocate_reproduces_design_n900():
    """DESIGN §2.3 states f=(.25,.375,.375) at n=900 => 225 / 337 / 338."""
    assert EP.allocate(900) == {"A": 225, "B": 337, "C": 338}


def test_allocate_size1_pool():
    assert EP.allocate(450) == {"A": 112, "B": 169, "C": 169}


@pytest.mark.parametrize("n", [0, 1, 7, 13, 100, 401, 450, 900, 1000])
def test_allocate_always_sums_to_n(n):
    a = EP.allocate(n)
    assert sum(a.values()) == n
    assert all(v >= 0 for v in a.values())


def test_variance_price_is_one_under_proportional_allocation(real_rows):
    """The identity that makes the 1.123 meaningful: f == w costs exactly 1.0."""
    w = {s: EP.frame_report(real_rows)["strata"][s]["share_of_nontied"] for s in EP.STRATA}
    assert EP.variance_price(w, w) == pytest.approx(1.0, abs=1e-12)


def test_variance_price_matches_design_1_123(real_rows):
    """DESIGN §2.3: sum(w^2/f) = 1.123 => se inflated 1.06x."""
    w = {s: EP.frame_report(real_rows)["strata"][s]["share_of_nontied"] for s in EP.STRATA}
    vp = EP.variance_price(w)
    assert vp == pytest.approx(1.123, abs=1e-3)
    assert vp ** 0.5 == pytest.approx(1.06, abs=5e-3)


def test_rejected_allocation_costs_more_exactly_as_design_says(real_rows):
    """DESIGN §2.3 rejected f=(0.40,0.30,0.30) at '1.17x se for no branch benefit'."""
    w = {s: EP.frame_report(real_rows)["strata"][s]["share_of_nontied"] for s in EP.STRATA}
    alt = {"A": 0.40, "B": 0.30, "C": 0.30}
    assert EP.variance_price(w, alt) ** 0.5 == pytest.approx(1.17, abs=5e-3)
    assert EP.variance_price(w, alt) > EP.variance_price(w)


# --------------------------------------------------------------------------- #
# 4. chunking — the unbiased-prefix property                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n,chunks", [(450, 4), (400, 4), (11, 4), (7, 7), (5, 1), (13, 3)])
def test_chunk_slices_partition_exactly(n, chunks):
    order = [f"r{i}" for i in range(n)]
    cuts = EP.chunk_slices(order, chunks)
    assert len(cuts) == chunks
    flat = [r for c in cuts for r in c]
    assert flat == order                      # contiguous AND order-preserving
    assert len(set(flat)) == n                # no overlap
    assert max(len(c) for c in cuts) - min(len(c) for c in cuts) <= 1


def test_chunk_slices_rejects_zero_chunks():
    with pytest.raises(ValueError):
        EP.chunk_slices(["a"], 0)


def test_committed_order_is_deterministic_and_input_order_independent():
    a = EP.committed_order(["c", "a", "b", "d"])
    b = EP.committed_order(["d", "b", "a", "c"])
    assert a == b                              # sorted FIRST, so input order is irrelevant
    assert sorted(a) == ["a", "b", "c", "d"]
    assert EP.committed_order(["a", "b", "c", "d"], seed=1) != a


# --------------------------------------------------------------------------- #
# 5. the draw — the global per-game cap                                        #
# --------------------------------------------------------------------------- #
def test_draw_respects_the_global_per_game_cap():
    rows = EP.nontied_rows(_synthetic())
    got = EP.draw(rows, EP.allocate(120), cap_per_game=2)
    counts = {}
    for r in got:
        counts[r["game_id"]] = counts.get(r["game_id"], 0) + 1
    assert max(counts.values()) <= 2
    assert len(got) == 120


def test_draw_fills_every_stratum_quota_exactly():
    rows = EP.nontied_rows(_synthetic())
    quota = EP.allocate(120)
    got = EP.draw(rows, quota, cap_per_game=2)
    realized = {s: sum(1 for r in got if EP.stratum_of(float(r["gap"])) == s)
                for s in EP.STRATA}
    assert realized == quota


def test_draw_is_deterministic_under_the_committed_seed():
    rows = EP.nontied_rows(_synthetic())
    a = [EP.rid_of(r) for r in EP.draw(rows, EP.allocate(90), 2)]
    b = [EP.rid_of(r) for r in EP.draw(rows, EP.allocate(90), 2)]
    assert a == b
    c = [EP.rid_of(r) for r in EP.draw(rows, EP.allocate(90), 2, seed=999)]
    assert c != a


def test_draw_refuses_rather_than_silently_shrinking_when_the_cap_binds():
    """A quota the cap cannot fill is a REFUSAL, never a short draw."""
    rows = EP.nontied_rows(_synthetic(n_games=5, per_game=12))
    with pytest.raises(SystemExit, match="could not fill"):
        EP.draw(rows, EP.allocate(60), cap_per_game=2)   # 5 games x 2 = 10 max


def test_draw_cap_is_global_not_per_stratum():
    """The single global shuffle is what makes the cap fair across strata: a game
    cannot contribute 1 to A *and* 1 to B under a global cap of 1."""
    rows = EP.nontied_rows(_synthetic(n_games=200))
    got = EP.draw(rows, EP.allocate(120), cap_per_game=1)
    ids = [r["game_id"] for r in got]
    assert len(ids) == 120
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------- #
# 6. the holdout split — over the CLUSTER unit, before any draw                #
# --------------------------------------------------------------------------- #
def test_split_games_is_disjoint_covering_and_sized():
    games = list(range(400))
    sp = EP.split_games(games, 0.25)
    assert set(sp["holdout"]) & set(sp["dev"]) == set()
    assert sorted(sp["holdout"] + sp["dev"]) == games
    assert len(sp["holdout"]) == 100


def test_split_games_is_deterministic_and_seed_sensitive():
    games = list(range(400))
    assert EP.split_games(games, 0.25) == EP.split_games(games, 0.25)
    assert EP.split_games(games, 0.25, seed=7) != EP.split_games(games, 0.25)


def test_split_seed_is_not_the_draw_seed():
    """A shared seed would correlate the split with the draw. It is offset by 1."""
    games = sorted({1000 + g for g in range(60)})
    assert EP.split_games(games, 0.25, seed=EP.PERMUTATION_SEED)["holdout"] != \
        sorted(games)[:15]


# --------------------------------------------------------------------------- #
# 7. se(kappa) — the DESIGN §7.1 dispersion table, cell for cell               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n,q,want", [
    (400, 0.50, 0.068), (400, 0.76, 0.084), (400, 0.90, 0.091),
    (600, 0.50, 0.055), (600, 0.76, 0.068), (600, 0.90, 0.074),
    (900, 0.50, 0.045), (900, 0.76, 0.056), (900, 0.90, 0.061),
    (1200, 0.50, 0.039), (1200, 0.76, 0.048), (1200, 0.90, 0.053),
])
def test_se_kappa_matches_the_design_table(n, q, want):
    assert EP.se_kappa(n, q) == pytest.approx(want, abs=6e-4)


def test_se_kappa_scales_as_one_over_root_n():
    assert EP.se_kappa(400, 0.76) / EP.se_kappa(1600, 0.76) == pytest.approx(2.0, abs=1e-9)


def test_se_kappa_rejects_zero_n():
    with pytest.raises(ValueError):
        EP.se_kappa(0, 0.76)


# --------------------------------------------------------------------------- #
# 8. reachability — the arithmetic the branch table rests on                   #
# --------------------------------------------------------------------------- #
KAPPA_STAR = 0.15          # DESIGN §4.1 / READ_RULE §4 — the fund bar
KAPPA_CLEAN = 0.35         # DESIGN §4.1 — the clean bar
UB95_K = 2.0               # READ_RULE §1 — the DECLARED upper-bound convention


def test_harm_and_fund_thresholds_at_the_interim_n400():
    """DESIGN §6.3: at n=400, q=0.76 both fire only at |kappa_hat| >= 0.168."""
    se = EP.se_kappa(400, 0.76)
    assert 2.0 * se == pytest.approx(0.168, abs=1e-3)
    assert max(KAPPA_STAR, 2.0 * se) == pytest.approx(0.168, abs=1e-3)


def test_fund_threshold_at_n900_is_the_bar_not_the_z():
    """DESIGN §6.3: at n=900 the z-conjunct STOPS BINDING — 2*se falls below
    kappa*, so E-FUND's effective threshold is the bar itself, +0.150.
    (At n=400 it is the other way round: the z binds at 0.168 > 0.150.)"""
    se900 = EP.se_kappa(900, 0.76)
    assert 2.0 * se900 < KAPPA_STAR
    assert max(KAPPA_STAR, 2.0 * se900) == pytest.approx(0.150, abs=1e-9)
    se400 = EP.se_kappa(400, 0.76)
    assert 2.0 * se400 > KAPPA_STAR


def test_flatnull_reachability_is_marginal_at_n400_and_clears_at_n900():
    """DESIGN §6.3's two honest limits, as arithmetic:
    E-FLATNULL needs kappa_hat < kappa* - 2*se  =>  -0.018 at n=400, +0.038 at n=900."""
    assert KAPPA_STAR - UB95_K * EP.se_kappa(400, 0.76) == pytest.approx(-0.018, abs=1e-3)
    assert KAPPA_STAR - UB95_K * EP.se_kappa(900, 0.76) == pytest.approx(+0.038, abs=1e-3)


def test_screen_cannot_convict_the_fundable_effect_at_n400():
    """DESIGN §6.3: a TRUE kappa = +0.15 reads z = 1.8 at n=400 — below the +2.0 bar."""
    assert KAPPA_STAR / EP.se_kappa(400, 0.76) == pytest.approx(1.79, abs=0.02)


def test_clean_bar_is_reachable_at_both_read_points():
    """E-CLEAN's z-conjunct is satisfied at kappa_hat = 0.35 at BOTH n."""
    for n in (400, 900):
        assert KAPPA_CLEAN / EP.se_kappa(n, 0.76) >= 2.0


def test_per_stratum_se_at_n900_is_a_sign_read_only():
    """DESIGN §6.3: 225/337/338 => 0.105 / 0.086 / 0.086 at q=0.76.

    ⚠️ These are WITHIN-stratum figures and therefore carry NO stratification
    penalty — the 1.06 is the price of population-reweighting the POOL. Using
    the pooled helper here would read 0.112/0.091/0.091 and silently contradict
    the DESIGN."""
    for n, want in ((225, 0.105), (337, 0.086), (338, 0.086)):
        assert EP.se_kappa_stratum(n, 0.76) == pytest.approx(want, abs=1e-3)
        assert EP.se_kappa(n, 0.76) > EP.se_kappa_stratum(n, 0.76)


def test_stratification_penalty_applies_to_the_pool_only():
    """The pooled/within-stratum ratio is exactly the committed 1.06."""
    assert EP.se_kappa(400, 0.76) / EP.se_kappa_stratum(400, 0.76) == pytest.approx(
        EP.STRATIFICATION_SE_PENALTY, abs=1e-12)


def test_near_tie_only_deployment_is_arithmetically_dead(real_rows):
    """DESIGN §4.2: an A-only deployment needs kappa_A >= 1.38/(1.277*0.31) = 3.49
    pts/ply, ~14x the tied-ply oracle CEILING of +0.2545. Free to state pre-run."""
    a_per_game_per_seat = EP.frame_report(real_rows)["strata"]["A"]["per_game_per_seat"]
    needed = 1.38 / (a_per_game_per_seat * 0.31)
    assert needed == pytest.approx(3.49, abs=0.02)
    assert needed / 0.2545 > 13.0


# --------------------------------------------------------------------------- #
# 9. cost                                                                      #
# --------------------------------------------------------------------------- #
def test_cost_table_reproduces_the_size1_headline():
    """DESIGN §5.3 / PLAN §0: SIZE-1 = 16.2 / 22.3 / 29.1 worker-h, ~1.4 h at W=16."""
    c = EP.cost_table(450, 400)
    assert c["lo"]["total_wh"] == pytest.approx(16.2, abs=0.15)
    assert c["central"]["total_wh"] == pytest.approx(22.3, abs=0.15)
    assert c["hi"]["total_wh"] == pytest.approx(29.1, abs=0.15)
    assert c["central"]["total_wh"] / 16.0 == pytest.approx(1.4, abs=0.05)


def test_cost_is_monotone_in_the_bracket():
    c = EP.cost_table(450, 400)
    assert c["lo"]["total_wh"] < c["central"]["total_wh"] < c["hi"]["total_wh"]


def test_selective_pricing_is_cheaper_than_full_arm_pricing():
    """DESIGN §3.4's economy: m_sel (1.8-2.6) vs m_full = 2*(K-1) = 6.0."""
    assert EP.M_FULL == 6.0
    assert all(m < EP.M_FULL for m in EP.M_SEL_BRACKET)
    c = EP.cost_table(450, 400)
    full_if_wh = 400 * EP.M_FULL * EP.M_WORLDS * EP.C_IF_BRACKET[1] / 3600.0
    assert full_if_wh / c["central"]["if_pricing_selective_wh"] == pytest.approx(
        EP.M_FULL / 2.2, abs=1e-6)


# --------------------------------------------------------------------------- #
# 10. end-to-end                                                               #
# --------------------------------------------------------------------------- #
def test_build_end_to_end_on_the_real_census(tmp_path):
    if not CENSUS.is_file():
        pytest.skip("tracked census absent")
    s = EP.build(CENSUS, tmp_path, n=450, cap_per_game=2, holdout_frac=0.25,
                 chunks=4, n_priced=400)

    assert s["n_pool"] == 450
    assert s["max_positions_per_game"] <= 2
    assert s["max_abs_f_deviation_pp"] < 3.0          # READ_RULE G-FRAME's own bar
    assert s["n_dev_positions"] + s["n_holdout_positions"] == 450
    assert s["variance_price_sum_w2_over_f"] == pytest.approx(1.123, abs=1e-3)

    order = json.loads((tmp_path / "POSITION_ORDER.json").read_text())
    sel = [json.loads(x) for x in (tmp_path / "SELECTION.jsonl").read_text().splitlines()]
    assert order["n"] == 450
    assert sum(order["chunk_sizes"]) == 450
    assert len(sel) == 450
    assert [x["rid"] for x in sel] == order["order"]   # SELECTION is IN committed order
    assert len({x["rid"] for x in sel}) == 450

    hold = set(json.loads((tmp_path / "HOLDOUT_GAMES.json").read_text())["holdout"])
    for x in sel:
        assert x["slice"] == ("holdout" if x["game_id"] in hold else "dev")
        assert x["stratum"] == EP.stratum_of(float(x["gap"]))
        assert x["deck_seed"] == x["game_id"]          # the replay key
        assert 1 <= x["chunk"] <= 4
        assert x["n_legal"] >= 2

    frame = json.loads((tmp_path / "FRAME.json").read_text())["population"]
    assert frame["nontied"] == 11505


def test_build_is_reproducible_bit_for_bit(tmp_path):
    if not CENSUS.is_file():
        pytest.skip("tracked census absent")
    a, b = tmp_path / "a", tmp_path / "b"
    EP.build(CENSUS, a, n=200, cap_per_game=2, holdout_frac=0.25, chunks=4)
    EP.build(CENSUS, b, n=200, cap_per_game=2, holdout_frac=0.25, chunks=4)
    for name in ("POSITION_ORDER.json", "SELECTION.jsonl", "HOLDOUT_GAMES.json"):
        assert (a / name).read_text() == (b / name).read_text(), name


def test_build_writes_nothing_outside_out_dir(tmp_path):
    if not CENSUS.is_file():
        pytest.skip("tracked census absent")
    out = tmp_path / "nested" / "out"
    EP.build(CENSUS, out, n=120, cap_per_game=2, holdout_frac=0.25, chunks=2)
    assert sorted(p.name for p in out.iterdir()) == [
        "FRAME.json", "HOLDOUT_GAMES.json", "PLAN_SUMMARY.json",
        "POSITION_ORDER.json", "SELECTION.jsonl"]
    assert sorted(p.name for p in (tmp_path / "nested").iterdir()) == ["out"]


def test_cap2_supply_ceiling_fits_size1_but_not_size2(real_rows):
    """DESIGN §5.4 / BAND_NOTE §4.3 — the hard supply constraint the PLAN does not state.

    449 games x cap 2 = 898 max constructible positions. SIZE-1 (pool 450, priced
    400) fits; SIZE-2 as the plan states it (pool 1,000, priced n=900) does NOT.
    Pinned here so a future 'just add n' ask cannot skip it.
    """
    n_games = EP.frame_report(real_rows)["games"]
    ceiling = n_games * 2
    assert n_games == 449
    assert ceiling == 898
    assert 450 <= ceiling and 400 <= ceiling      # SIZE-1 fits
    assert 1000 > ceiling and 900 > ceiling       # SIZE-2 does not


def test_draw_refuses_an_over_supply_request_on_the_real_census(real_rows):
    """The ceiling is ENFORCED, not merely documented."""
    nt = EP.nontied_rows(real_rows)
    with pytest.raises(SystemExit, match="could not fill"):
        EP.draw(nt, EP.allocate(1000), cap_per_game=2)


def test_holdout_is_a_root_split_not_a_position_split(tmp_path):
    """No game may straddle the dev/holdout boundary — the cluster is the unit."""
    if not CENSUS.is_file():
        pytest.skip("tracked census absent")
    EP.build(CENSUS, tmp_path, n=450, cap_per_game=2, holdout_frac=0.25, chunks=4)
    sel = [json.loads(x) for x in (tmp_path / "SELECTION.jsonl").read_text().splitlines()]
    by_game = {}
    for x in sel:
        by_game.setdefault(x["game_id"], set()).add(x["slice"])
    assert all(len(v) == 1 for v in by_game.values())
