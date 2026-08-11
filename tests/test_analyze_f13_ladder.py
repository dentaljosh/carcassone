"""Tests for the PRE-REGISTERED F13 exact-K ladder analysis.

Script under test: scripts/classical_search/analyze_f13_ladder.py
Prereg (binding):  measurement/exact_k_ladder_20260803/PREREG_DRAFT.md

The fixtures reproduce the REAL emitter's on-disk shape (verified against
`eval_puct_priors._save` / `_result_path` / `write_manifest`):
  * per-game records at ``seed<012d>_a<seat>.json`` carrying
    seed / a_seat / diff (cand - opponent) / won_by_cand / drew / game_timeout and
    the `f13_*` counter block;
  * a per-cell ``manifest.json`` whose AUTHORITATIVE per-arm K lives at
    ``config.exact_tail.{cand_exact_k,opp_exact_k}``. Two manifest generations exist:
    OLD cells (pre 2026-08-04) stamp the CANDIDATE's `exact_k` into the round-robin
    ``config.opponent`` block too (emitter defect, fixed in eval_puct_priors), NEW cells
    stamp the opponent's own K there. The parser sources exact_tail and must yield the
    SAME incumbent K for both (`TestIncumbentK`).

Covered, in the order the brief names them:
  * per-rung stat math against hand-computed values;
  * the censoring stamp firing above the threshold and NOT at/below it;
  * branch 4 (control-positive) DOMINATING a would-be branch-2 result;
  * branch 2 firing only when uncensored (censored-positive -> branch 3);
  * the trend fit on a known-slope synthetic;
  * the refuse-to-report path when the decks are not shared across rungs.
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
SCRIPT = CS / "analyze_f13_ladder.py"

sys.path.insert(0, str(CS))
_spec = importlib.util.spec_from_file_location("analyze_f13_ladder", SCRIPT)
az = importlib.util.module_from_spec(_spec)
sys.modules["analyze_f13_ladder"] = az
_spec.loader.exec_module(az)

BAND = 106_000_000_000


# --------------------------------------------------------------------------- #
# fixture builders (mirror the real emitter's layout)                          #
# --------------------------------------------------------------------------- #
def write_cell(root: Path, name: str, cand_k: int, decks: dict, *, band: int = BAND,
               opp_k: int = 4, latch_per_game: int = 4, cap_hits_per_game: int = 0,
               champ_cap_hits: int = 0, n_planned: int | None = None,
               cand_sims: int = 2750, rules_profile: str = "fixed_v1",
               r9_env_ok: bool = True, timeouts: set | None = None,
               write_summary: bool = True, legacy_opp_block: bool = False) -> Path:
    """`decks` maps deck seed -> (diff_at_seat0, diff_at_seat1).

    `legacy_opp_block=True` reproduces a PRE-2026-08-04 manifest, whose
    ``config.opponent.exact_k`` carries the CANDIDATE's K (the emitter defect).
    """
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    timeouts = timeouts or set()
    games = []
    for seed, (d0, d1) in decks.items():
        for seat, diff in ((0, d0), (1, d1)):
            g = {
                "seed": int(seed), "a_seat": seat, "cand_sims": cand_sims,
                "champ_sims": cand_sims,
                "score_p0": 0, "score_p1": 0, "diff": int(diff),
                "won_by_cand": bool(diff > 0), "drew": bool(diff == 0),
                "elapsed_s": 1.0, "moves": 142, "deck_hash": "deadbeef",
                "cand_prefix_moves": 71, "cand_exact_moves": 4,
                "cand_prefix_secs": 1.0, "cand_solver_secs": 1.0, "cand_timeouts": 0,
                "champ_prefix_moves": 71, "champ_exact_moves": 4,
                "champ_prefix_secs": 1.0, "champ_solver_secs": 1.0,
                "champ_timeouts": 0, "latch_k": cand_k,
                "game_timeout": (seed, seat) in timeouts,
                "f13_on": True, "cand_tail_k": cand_k, "champ_tail_k": opp_k,
                "cand_latch_solves": latch_per_game, "champ_latch_solves": latch_per_game,
                "cand_capped_attempts": latch_per_game if cand_k >= 5 else 0,
                "champ_capped_attempts": 0,
                "cand_cap_hits": cap_hits_per_game, "champ_cap_hits": champ_cap_hits,
                "cand_fallback_depth": 1 if cap_hits_per_game else 0,
                "champ_fallback_depth": 0,
                "cand_eff_k_final": cand_k - 1 if cap_hits_per_game else cand_k,
                "champ_eff_k_final": opp_k,
                "cand_max_solve_secs": 12.5, "champ_max_solve_secs": 3.0,
            }
            (d / f"seed{int(seed):012d}_a{seat}.json").write_text(json.dumps(g))
            games.append(g)
    manifest = {
        "kind": "eval_puct_priors", "game": "carcassonne_base_farmers",
        "code_rev": "abc1234", "host": "testbox",
        "rules_profile": {"name": rules_profile, "r9_env_ok": r9_env_ok},
        "config": {
            "seed_start": band, "n": n_planned if n_planned is not None else len(games),
            "paired": True, "exp_id": f"f13_exactk{cand_k}_fixed_v1_vs_champk{opp_k}",
            "cand_sims": cand_sims, "champ_sims": cand_sims,
            # Legacy pre-F13 top-level field = the CANDIDATE's K on both generations.
            "exact_k": cand_k,
            "candidate": {"kind": "puct", "exact_k": cand_k},
            # NEW (default): the opponent block carries the OPPONENT's K.
            # legacy_opp_block=True: the pre-2026-08-04 emitter defect, where it
            # carried the candidate's K. The parser must not read either one.
            "opponent": {"kind": "puct",
                         "exact_k": cand_k if legacy_opp_block else opp_k},
            "exact_tail": {
                "cand_exact_k": cand_k, "opp_exact_k": opp_k,
                "wall_caps": {"5": 300.0, "6": 600.0},
                "wall_caps_spec": "5:300,6:600", "k_floor": 4, "solver": "rust",
                "censor_threshold": 0.20, "ladder_engaged": True,
            },
        },
    }
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2))
    if write_summary:
        rung = az.rung_stats(az.load_cell(d))
        (d / "summary.json").write_text(json.dumps({
            "n": rung["n"], "W": rung["W"], "D": rung["D"], "L": rung["L"],
            "winrate": rung["winrate"], "elo": rung["elo"],
            "elo_sig_1sigma": rung["elo_sig_1sigma"],
            "paired_mean_margin": rung["paired_mean_margin"],
            "paired_z": rung["paired_z"], "n_paired": rung["n_paired"],
        }, default=str))
    return d


def pair(margin: float) -> tuple[int, int]:
    """Two integer seat diffs whose mean is `margin` (margins are multiples of 0.5)."""
    lo = math.floor(margin)
    hi = int(2 * margin) - lo
    assert (lo + hi) / 2.0 == margin, margin
    return lo, hi


# =========================================================================== #
# 1. per-rung stat math                                                       #
# =========================================================================== #
class TestRungStats:
    def test_hand_computed(self, tmp_path):
        # 4 decks x 2 seats. diffs (cand - opp):
        #   deck0 (+10, +2) -> margin  6.0
        #   deck1 ( -4,  0) -> margin -2.0
        #   deck2 ( +6, +6) -> margin  6.0
        #   deck3 ( -2, -8) -> margin -5.0
        decks = {BAND + 0: (10, 2), BAND + 1: (-4, 0),
                 BAND + 2: (6, 6), BAND + 3: (-2, -8)}
        d = write_cell(tmp_path, "f13_fixed_v1_k5", 5, decks)
        r = az.rung_stats(az.load_cell(d))

        assert (r["n"], r["W"], r["D"], r["L"]) == (8, 4, 1, 3)
        assert r["winrate"] == pytest.approx(0.5625)          # (4 + 0.5) / 8
        assert r["elo"] == pytest.approx(400 * math.log10(0.5625 / 0.4375))
        assert r["elo"] == pytest.approx(43.66, abs=0.02)
        assert r["elo_sig_1sigma"] == pytest.approx(
            (400 / math.log(10)) * math.sqrt(0.5625 * 0.4375 / 8) / (0.5625 * 0.4375))
        assert r["elo_mde_2sigma"] == pytest.approx(2 * r["elo_sig_1sigma"])
        # paired margin: mean of [6, -2, 6, -5] = 1.25
        assert r["n_paired"] == 4
        assert r["paired_mean_margin"] == pytest.approx(1.25)
        assert r["paired_se"] == pytest.approx(2.80995, abs=1e-4)
        assert r["paired_z"] == pytest.approx(0.44485, abs=1e-4)
        assert r["margin_mde_2sigma"] == pytest.approx(5.6199, abs=1e-3)
        assert r["avg_diff"] == pytest.approx((10 + 2 - 4 + 0 + 6 + 6 - 2 - 8) / 8)
        # counters: 8 games x 4 latch solves, no cap hits
        assert r["latch_solves"] == 32
        assert r["cap_hits"] == 0
        assert r["censored_rate"] == 0.0
        assert r["censored"] is False
        assert r["stamp"] == "ok"

    def test_game_timeouts_excluded_from_strength_but_not_from_censoring(self, tmp_path):
        decks = {BAND + i: (4, 4) for i in range(4)}
        d = write_cell(tmp_path, "f13_fixed_v1_k6", 6, decks,
                       latch_per_game=4, cap_hits_per_game=1,
                       timeouts={(BAND + 3, 0), (BAND + 3, 1)})
        r = az.rung_stats(az.load_cell(d))
        assert r["n"] == 6 and r["game_timeouts"] == 2
        assert r["n_paired"] == 3                       # the abandoned deck drops out
        # censoring counts ALL 8 games (solver behaviour, not the strength sample)
        assert r["latch_solves"] == 32 and r["cap_hits"] == 8
        assert r["censored_rate"] == pytest.approx(0.25)


# =========================================================================== #
# 1b. per-arm K provenance: BOTH manifest generations must parse identically  #
# =========================================================================== #
class TestIncumbentK:
    """`config.exact_tail` is the authoritative per-arm K.

    The emitter's round-robin `config.opponent` block used to stamp the CANDIDATE's
    `exact_k` (fixed 2026-08-04 -> it now stamps `_opp_exact_k`), so cells written on
    either side of that fix are on disk. The parser reads exact_tail and must return
    the same incumbent K for both.
    """

    def test_new_manifest_opponent_block_reports_the_opponents_k(self, tmp_path):
        d = write_cell(tmp_path, "f13_fixed_v1_k6", 6, {BAND: (1, 1)}, opp_k=4)
        man = json.loads((d / "manifest.json").read_text())["config"]
        assert man["candidate"]["exact_k"] == 6
        assert man["opponent"]["exact_k"] == 4       # fixed emitter: the incumbent's K
        c = az.load_cell(d)
        assert (c["cand_k"], c["opp_k"]) == (6, 4)

    def test_old_defective_manifest_still_parses_to_the_right_incumbent_k(self, tmp_path):
        """Back-compat: a pre-fix cell lies in config.opponent; exact_tail does not."""
        d = write_cell(tmp_path, "f13_fixed_v1_k6", 6, {BAND: (1, 1)}, opp_k=4,
                       legacy_opp_block=True)
        man = json.loads((d / "manifest.json").read_text())["config"]
        assert man["opponent"]["exact_k"] == 6       # the old defect, on purpose
        c = az.load_cell(d)
        assert c["cand_k"] == 6
        assert c["opp_k"] == 4                       # NOT 6 — read from exact_tail

    def test_both_generations_agree(self, tmp_path):
        new = az.load_cell(write_cell(tmp_path / "new", "f13_fixed_v1_k6", 6,
                                      {BAND: (1, 1)}, opp_k=4))
        old = az.load_cell(write_cell(tmp_path / "old", "f13_fixed_v1_k6", 6,
                                      {BAND: (1, 1)}, opp_k=4, legacy_opp_block=True))
        assert (new["cand_k"], new["opp_k"]) == (old["cand_k"], old["opp_k"]) == (6, 4)

    def test_symmetric_cell_reports_the_same_k_on_both_arms(self, tmp_path):
        d = write_cell(tmp_path, "f13_fixed_v1_k4", 4, {BAND: (1, 1)}, opp_k=4)
        man = json.loads((d / "manifest.json").read_text())["config"]
        assert man["candidate"]["exact_k"] == man["opponent"]["exact_k"] == 4
        c = az.load_cell(d)
        assert (c["cand_k"], c["opp_k"]) == (4, 4)


# =========================================================================== #
# 2. the censoring stamp                                                      #
# =========================================================================== #
class TestCensoring:
    def test_fires_strictly_above_threshold(self, tmp_path):
        # 5 latch solves/game, 2 cap hits/game -> rate 0.40 > 0.20
        decks = {BAND + i: (2, 2) for i in range(4)}
        d = write_cell(tmp_path, "f13_fixed_v1_k6", 6, decks,
                       latch_per_game=5, cap_hits_per_game=2)
        r = az.rung_stats(az.load_cell(d))
        assert r["censored_rate"] == pytest.approx(0.40)
        assert r["censored"] is True
        assert r["stamp"] == "NOT-A-VERDICT"
        assert "NOT A VERDICT" in r["censor_banner"]

    def test_does_not_fire_at_or_below_threshold(self, tmp_path):
        # 5 latch solves/game, 1 cap hit/game -> rate exactly 0.20; the rule is ">20%"
        decks = {BAND + i: (2, 2) for i in range(4)}
        d = write_cell(tmp_path, "f13_fixed_v1_k6", 6, decks,
                       latch_per_game=5, cap_hits_per_game=1)
        r = az.rung_stats(az.load_cell(d))
        assert r["censored_rate"] == pytest.approx(0.20)
        assert r["censored"] is False
        assert r["stamp"] == "ok"

    def test_uses_exact_tail_own_functions(self, tmp_path):
        """The censoring statistic must come from exact_tail, not a second copy."""
        import exact_tail as et
        assert az.et is et
        assert et.censored_rate(1, 5) == pytest.approx(0.20)
        assert et.is_censored(0.20) is False and et.is_censored(0.2001) is True
        assert az.rung_stats(az.load_cell(write_cell(
            tmp_path, "f13_fixed_v1_k5", 5, {BAND: (1, 1)},
            latch_per_game=10, cap_hits_per_game=3)))["censored_rate_capped"] == \
            pytest.approx(et.censored_rate_capped(6, 20))


# =========================================================================== #
# 3. the trend (the PRIMARY statistic)                                        #
# =========================================================================== #
def known_slope_ladder(tmp_path, *, slopes=(1.5, 0.5, 1.5, 0.5), ks=(2, 3, 5),
                       n_decks=4, band=BAND, **kw):
    """margin(deck s, rung K) = slope_s * (K - 2) — so the K=2 control sits at 0."""
    for k in ks:
        decks = {}
        for i in range(n_decks):
            decks[band + i] = pair(slopes[i % len(slopes)] * (k - 2))
        write_cell(tmp_path, f"f13_fixed_v1_k{k}", k, decks, band=band, **kw)
    return sorted(tmp_path.glob("f13_fixed_v1_k*"))


class TestTrend:
    def test_known_slope(self, tmp_path):
        dirs = known_slope_ladder(tmp_path)
        rungs = [az.rung_stats(az.load_cell(d)) for d in dirs]
        tr = az.trend(rungs)
        assert tr["ok"] is True
        assert tr["n_shared_decks"] == 4
        assert sorted(tr["k"]) == [2, 3, 5]
        # per-deck slopes are exactly (1.5, 0.5, 1.5, 0.5): mean 1.0,
        # sd(ddof=1) = 0.57735, se = 0.288675, z = 3.4641
        assert tr["slope"] == pytest.approx(1.0, abs=1e-9)
        assert tr["se"] == pytest.approx(0.288675, abs=1e-5)
        assert tr["z"] == pytest.approx(3.4641, abs=1e-3)
        assert tr["slope_mde_2sigma"] == pytest.approx(0.57735, abs=1e-4)

    def test_identity_anchor_is_off_by_default_and_changes_the_fit(self, tmp_path):
        dirs = known_slope_ladder(tmp_path)
        rungs = [az.rung_stats(az.load_cell(d)) for d in dirs]
        off = az.trend(rungs)
        on = az.trend(rungs, include_identity_anchor=True)
        assert off["include_identity_anchor"] is False
        assert on["include_identity_anchor"] is True
        assert az.INCUMBENT_K in on["k"] and az.INCUMBENT_K not in off["k"]
        assert on["slope"] != pytest.approx(off["slope"], abs=1e-9)

    def test_refuses_when_decks_not_shared(self, tmp_path):
        # disjoint deck ranges per rung: the CRN structure the design rests on is absent
        write_cell(tmp_path, "f13_fixed_v1_k2", 2,
                   {BAND + i: (0, 0) for i in range(4)})
        write_cell(tmp_path, "f13_fixed_v1_k5", 5,
                   {BAND + 100 + i: (3, 3) for i in range(4)})
        rungs = [az.rung_stats(az.load_cell(d))
                 for d in sorted(tmp_path.glob("f13_fixed_v1_k*"))]
        tr = az.trend(rungs)
        assert tr["ok"] is False
        assert tr["slope"] is None and tr["z"] is None
        assert "NOT shared" in tr["refusal"] and "REFUSING" in tr["refusal"]
        # ... and the decision map cannot claim the null without it
        dec = az.decide(rungs, tr)
        assert dec["primary_branch"] is None
        assert "INCOMPLETE" in dec["label"]

    def test_refuses_across_bands(self, tmp_path):
        write_cell(tmp_path, "f13_fixed_v1_k2", 2,
                   {BAND + i: (0, 0) for i in range(4)}, band=BAND)
        write_cell(tmp_path, "f13_fixed_v1_k5", 5,
                   {BAND + i: (3, 3) for i in range(4)}, band=BAND + 5_000_000_000)
        rungs = [az.rung_stats(az.load_cell(d))
                 for d in sorted(tmp_path.glob("f13_fixed_v1_k*"))]
        tr = az.trend(rungs)
        assert tr["ok"] is False
        assert "MULTIPLE seed bands" in tr["refusal"]

    def test_refuses_with_a_single_rung(self, tmp_path):
        write_cell(tmp_path, "f13_fixed_v1_k5", 5, {BAND + i: (1, 1) for i in range(4)})
        rungs = [az.rung_stats(az.load_cell(d))
                 for d in sorted(tmp_path.glob("f13_fixed_v1_k*"))]
        tr = az.trend(rungs)
        assert tr["ok"] is False and "rung" in tr["refusal"]

    def test_warns_on_thin_shared_subset(self, tmp_path):
        write_cell(tmp_path, "f13_fixed_v1_k2", 2,
                   {BAND + i: (0, 0) for i in range(10)})
        write_cell(tmp_path, "f13_fixed_v1_k5", 5,
                   {BAND + i: (1, 2) for i in range(3)})
        rungs = [az.rung_stats(az.load_cell(d))
                 for d in sorted(tmp_path.glob("f13_fixed_v1_k*"))]
        tr = az.trend(rungs)
        assert tr["ok"] is True
        assert "shared" in tr.get("warning", "")


# =========================================================================== #
# 4. the decision map                                                         #
# =========================================================================== #
class TestDecisionMap:
    def test_branch4_control_positive_dominates_a_would_be_branch2(self, tmp_path):
        # K=2 control reads strongly POSITIVE (shallower beats production == impossible)
        write_cell(tmp_path, "f13_fixed_v1_k2", 2,
                   {BAND + i: (7 - 2 * (i % 2), 7 - 2 * (i % 2)) for i in range(6)})
        # ... alongside a K=5 rung that on its own would fire branch 2
        write_cell(tmp_path, "f13_fixed_v1_k5", 5,
                   {BAND + i: (9 - 2 * (i % 2), 9 - 2 * (i % 2)) for i in range(6)})
        res = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))
        dec = res["decision"]
        assert dec["primary_branch"] == 4
        assert dec["suppressed"] is True
        assert any("negative-control" in a for a in dec["alarms"])
        assert all(f["branch"] == 4 for f in dec["fired"])
        assert "INSTRUMENT ALARM" in res["markdown"]
        assert "BRANCH 4" in res["markdown"]

    def test_branch4_also_fires_on_incumbent_cap_hit(self, tmp_path):
        write_cell(tmp_path, "f13_fixed_v1_k2", 2, {BAND + i: (0, 0) for i in range(4)})
        write_cell(tmp_path, "f13_fixed_v1_k5", 5, {BAND + i: (0, 0) for i in range(4)},
                   champ_cap_hits=1)
        res = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))
        assert res["decision"]["primary_branch"] == 4
        assert any("INCUMBENT arm hit a wall cap" in a
                   for a in res["decision"]["alarms"])

    def test_branch2_fires_when_uncensored(self, tmp_path):
        known_slope_ladder(tmp_path)   # trend z = 3.46, K=5 rung z = 3.46, uncensored
        res = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))
        dec = res["decision"]
        assert dec["primary_branch"] == 2
        assert any(f["branch"] == 2 for f in dec["fired"])
        # the 2026-08-04 amendment: a screen positive buys a CONFIRM, not the net
        assert "11008" in dec["action"] and "2750" in dec["action"]
        assert "does NOT fund the endgame net" in dec["action"]

    def test_branch2_does_not_fire_when_censored_branch3_does(self, tmp_path):
        # same numbers, but the K=5 rung is censored at 0.50 and the K=3 rung is
        # flat, so the trend cannot carry branch 2 on its own either.
        write_cell(tmp_path, "f13_fixed_v1_k2", 2,
                   {BAND + i: (1 - 2 * (i % 2), 0) for i in range(6)})
        write_cell(tmp_path, "f13_fixed_v1_k5", 5,
                   {BAND + i: (9 - 2 * (i % 2), 9 - 2 * (i % 2)) for i in range(6)},
                   latch_per_game=4, cap_hits_per_game=2)
        res = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))
        k5 = [r for r in res["rungs"] if r["cand_k"] == 5][0]
        assert k5["censored"] is True and k5["paired_z"] > 2
        # the DECIDING trend is fitted on uncensored rungs only, so the censored K=5
        # rung cannot smuggle itself into branch 2 through the trend either.
        assert res["trend"]["ok"] is False
        assert res["trend_all_rungs"]["ok"] is True     # reported, but diagnostic only
        dec = res["decision"]
        assert dec["primary_branch"] == 3
        assert any(f["branch"] == 3 for f in dec["fired"])
        assert "raise" in dec["action"].lower() and "n=200" in dec["action"]

    def test_branch1_powered_null(self, tmp_path):
        # small, sign-mixed margins at every rung; a real spread so z is finite
        import random
        rng = random.Random(7)
        for k in (2, 3, 5, 6):
            decks = {BAND + i: pair(rng.choice([-1.0, -0.5, 0.0, 0.5, 1.0]))
                     for i in range(40)}
            write_cell(tmp_path, f"f13_fixed_v1_k{k}", k, decks)
        res = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))
        dec, tr = res["decision"], res["trend"]
        assert tr["ok"] is True
        assert abs(tr["z"]) < 2
        assert all(abs(r["paired_z"]) < 2 for r in res["rungs"])
        assert dec["primary_branch"] == 1
        assert "STILLBORN" in dec["action"]
        assert "TRANSFERS" in dec["action"]

    def test_branch1_blocked_when_a_rung_is_censored(self, tmp_path):
        for k in (2, 5):
            decks = {BAND + i: (0, 1) for i in range(6)}
            write_cell(tmp_path, f"f13_fixed_v1_k{k}", k, decks,
                       latch_per_game=4, cap_hits_per_game=(2 if k == 5 else 0))
        res = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))
        assert res["decision"]["primary_branch"] is None
        assert "censored" in res["decision"]["action"]


# =========================================================================== #
# 5. power reporting + outputs                                                #
# =========================================================================== #
class TestOutputs:
    def test_power_is_printed_beside_every_estimate(self, tmp_path):
        known_slope_ladder(tmp_path)
        md = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))["markdown"]
        assert "## Power" in md
        assert "±12 elo" in md or "+/-12 elo" in md
        assert "2σ MDE" in md
        assert "UNRESOLVED, not absent" in md

    def test_markdown_table_and_verdict_json(self, tmp_path, capsys):
        known_slope_ladder(tmp_path)
        vj = tmp_path / "V.json"
        rc = az.main(["--out-root", str(tmp_path), "--band", str(BAND),
                      "--verdict-json", str(vj)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "| rung | K | n |" in out
        assert "f13_fixed_v1_k5" in out
        v = json.loads(vj.read_text())
        assert v["meta"]["schema"] == az.SCHEMA
        assert v["meta"]["prereg"].endswith("PREREG_DRAFT.md")
        assert v["meta"]["band"] == BAND
        assert {r["name"] for r in v["rungs"]} == {
            "f13_fixed_v1_k2", "f13_fixed_v1_k3", "f13_fixed_v1_k5"}
        assert v["decision"]["primary_branch"] == 2
        assert v["trend"]["ok"] is True
        assert "_margins" not in v["rungs"][0]

    def test_discovery_filters_by_band_and_ladder_flag(self, tmp_path):
        write_cell(tmp_path, "f13_fixed_v1_k5", 5, {BAND + i: (1, 1) for i in range(3)})
        # a throwaway SMOKE cell on the launcher's BAND+9e8 band must not be picked up
        write_cell(tmp_path, "f13_fixed_v1_k6", 6, {BAND + 900_000_000 + i: (9, 9)
                                                    for i in range(3)},
                   band=BAND + 900_000_000)
        found = az.discover_cells(tmp_path, BAND, None)
        assert [p.name for p in found] == ["f13_fixed_v1_k5"]
        assert len(az.discover_cells(tmp_path, None, None)) == 2

    def test_warns_on_wrong_profile_wrong_sims_and_partial_cell(self, tmp_path):
        write_cell(tmp_path, "f13_fixed_v1_k5", 5, {BAND + i: (1, 1) for i in range(3)},
                   rules_profile="walled", r9_env_ok=False, cand_sims=11008,
                   n_planned=400)
        res = az.analyze(sorted(tmp_path.glob("f13_fixed_v1_k*")))
        blob = " ".join(res["warnings"])
        assert "fixed_v1" in blob and "2750" in blob and "PARTIAL" in blob

    def test_crosscheck_flags_a_summary_that_disagrees(self, tmp_path):
        d = write_cell(tmp_path, "f13_fixed_v1_k5", 5,
                       {BAND + i: (i - 1, i - 1) for i in range(4)})
        s = json.loads((d / "summary.json").read_text())
        s["paired_z"] = 99.0
        (d / "summary.json").write_text(json.dumps(s))
        res = az.analyze([d])
        assert any("paired_z" in w for w in res["warnings"])
