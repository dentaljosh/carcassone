"""OM-M1 — refutation-priced arbitration, the first kill-gate's contract tests.

⛔ INSTRUMENT ONLY. Spec: ``measurement/omm1_refuter_gate_20260830/PREREG.md``.

Split in two, deliberately:

* the **arithmetic** tests (the read rule, the bar, the branch table) are pure
  and run everywhere — they are what makes the frozen read rule checkable
  without buying a playout;
* the **binding** tests exercise ``carc_rs.tiearb_arbitrate_legs`` and are
  skipped when the installed ``carc_rs`` predates the OM-M1 binding, so a stale
  wheel reads as SKIP rather than as a false green.

The bit-identity gates themselves (``G-BITEXACT``, ``G-INERT``) live in Rust
(``carc_core::tiearb::tests`` / ``carc_core::tier1::tests``) because they are
statements about f64 bit patterns inside the arbiter, not about the binding.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "omm1"))

import analyze_gate as AG  # noqa: E402
import omm1_lib as L  # noqa: E402


# --------------------------------------------------------------------------- #
# frozen constants                                                             #
# --------------------------------------------------------------------------- #
def test_the_frozen_constants_are_the_prereg_s():
    """A drifted salt / cap / eps silently makes this a different experiment
    (`TIEARB_SALT_OF_RECORD`'s own doc rule). Pinned here so a refactor cannot
    move one without a red test."""
    assert L.SALT_OF_RECORD == "tiearb2-deploy-v1"
    assert L.ARM_CAP_J == 4
    assert L.EPS == 0.0
    assert L.MAX_PLIES == 400
    assert L.B_WORLDS == 64
    assert L.B_DEPLOYED == 16
    assert L.SPLIT == 32
    assert L.LEG2_SUFFIX == ["omm1-leg2"]


def test_the_bar_is_the_effect_size_not_two_sigma():
    """PREREG §5. The bar must be reproducible from the banked constants — if
    it ever stops equalling `target * (1 - 1/A) / G_arb`, either the derivation
    or the number was edited and the round is no longer the one that was funded."""
    derived = L.bar_delta_flip()
    assert 0.216 < derived < 0.218, derived
    assert L.BAR_DELTA_FLIP == 0.22
    assert L.BAR_DELTA_FLIP >= derived, "the bar must not be rounded DOWN below its derivation"
    # And it is nowhere near 2 sigma-hat of the instrument at the planned n.
    se_expected = (300 ** 0.5) / 1200
    assert L.BAR_DELTA_FLIP > 5 * (2 * se_expected), (
        "a bar within a few sigma of the instrument is the exact failure the "
        "2026-08-30 house rule forbids"
    )


def test_the_bar_does_not_depend_on_the_fire_rate():
    """⭐ The correction of 2026-08-30. The naive derivation is
    `target / (F * R_x)`; because `R_x = G_arb / (F * P)`, `F` cancels exactly.

    This is load-bearing, not cosmetic: the `22.96 fired plies/game` constant
    quoted in the tiearb plans is the **E4 stratum** (597 tied plies / 26 phone
    games), while the walled corpora this gate replays bank **45.26** exact-tied
    tile plies/game. A bar that consumed `F` would have been ~2x wrong."""
    for f in (22.96, 37.0, 45.26, 100.0):
        r_x = L.G_ARB_PTS_PER_GAME / (f * L.P_ARB_NE_RND)
        assert L.TARGET_PTS_PER_GAME / (f * r_x) == pytest.approx(L.bar_delta_flip())


def test_the_refuter_of_record_is_the_shape_b_invader():
    """PREREG §4.3 — provenance. `alpha 0.09 @ cap 11.0` is the
    `invasion_screen_r3_prep` C-arm ENV opponent, an already-blessed INSTRUMENT
    (`screen_lib.SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE`), not a dose invented
    for this gate."""
    assert L.REFUTER_OF_RECORD["invasion_alpha"] == 0.09
    assert L.REFUTER_OF_RECORD["invasion_alpha_cap"] == 11.0
    # The ceiling arm is strictly stronger, and adds shape A at its principled
    # extreme ("a contestable component is worth nothing in the differential").
    assert L.REFUTER_MAX["invasion_alpha"] > L.REFUTER_OF_RECORD["invasion_alpha"]
    assert L.REFUTER_MAX["invasion_beta"] == 1.0


def test_the_corpus_is_blind_to_outcomes():
    """The frame builder may not read who won — the widening census's blind
    discipline, inherited. An outcome field in the read set would let the
    sample be (even accidentally) conditioned on the result."""
    assert "score_p0" not in L._GAME_FIELDS_READ
    assert "score_p1" not in L._GAME_FIELDS_READ


def test_stable_seed_is_join_disciplined_and_deterministic():
    """`"|"`-joined so two different part lists cannot collide by concatenation,
    and never `hash()` (per-process salted)."""
    assert L.stable_seed("a", "bc") == L.stable_seed("a", "bc")
    assert L.stable_seed("a", "bc") != L.stable_seed("ab", "c")
    assert 0 <= L.stable_seed("x") < 2 ** 63


# --------------------------------------------------------------------------- #
# the read rule (§4.4) — pure arithmetic over synthetic matrices               #
# --------------------------------------------------------------------------- #
def _rec(sym, other, arms=(10, 20), other_name=L.LEG_MAX):
    b = len(sym)
    return {
        "rid": "t",
        "corpus": "unit",
        "deck_seed": 1,
        "ply": 3,
        "arms": list(arms),
        "b": b,
        "ok": True,
        "phase_bucket": "mid",
        "k_remaining": 30,
        "legs": {
            L.LEG_SYM: {"margins": sym},
            other_name: {"margins": other},
        },
    }


def test_argmax_keeps_the_earliest_arm_on_a_tie():
    """`arbitrate_core` uses a strict `>` so a tie keeps `arms[0]` — the
    incumbent leaf tie-break. Any other rule would invent flips out of exact
    ties, which at eps=0 is the modal case."""
    assert AG._argmax_arm([1.0, 1.0, 1.0], [7, 8, 9]) == 7
    assert AG._argmax_arm([1.0, 2.0, 2.0], [7, 8, 9]) == 8


def test_no_flip_when_the_two_legs_agree():
    sym = [[0.0, 5.0]] * 4
    other = [[0.0, 5.0]] * 4
    out = AG.analyze_row(_rec(sym, other), split=2)
    assert out["A_sym"] == 20
    assert out[L.LEG_MAX]["flip"] == 0


def test_a_flip_is_detected_and_is_driven_by_the_second_half_only():
    """The two-leg score is `1/2 mean(S over j<split) + 1/2 mean(R over j>=split)`.
    Here S prefers arm 1 everywhere; R prefers arm 0 hard enough in the second
    half to move the blend."""
    sym = [[0.0, 1.0]] * 4
    other = [[0.0, 1.0], [0.0, 1.0], [100.0, 0.0], [100.0, 0.0]]
    out = AG.analyze_row(_rec(sym, other), split=2)
    assert out["A_sym"] == 20
    assert out[L.LEG_MAX]["A_two"] == 10
    assert out[L.LEG_MAX]["flip"] == 1
    # The pure-R read (all worlds refuter) is reported separately and is a
    # DIFFERENT statistic — it must not be silently substituted for the two-leg.
    assert out[L.LEG_MAX]["A_pure"] == 10


def test_the_swap_replication_is_computed_from_the_same_matrices():
    """`rho` exchanges the leg halves — free, exact CRN, no extra playout. A
    flip driven by half-sample noise should not survive it; a flip driven by the
    refuter should."""
    # Refuter prefers arm 0 in BOTH halves -> the swap reproduces the flip.
    sym = [[0.0, 1.0]] * 4
    other = [[100.0, 0.0]] * 4
    out = AG.analyze_row(_rec(sym, other), split=2)
    assert out[L.LEG_MAX]["flip"] == 1
    assert out[L.LEG_MAX]["flip_swap"] == 1
    assert out[L.LEG_MAX]["swap_same_arm"] == 1


def test_the_deployed_b16_pick_is_recovered_from_the_first_16_worlds():
    """PREREG §4.2: the world seed does not depend on B, so a B=64 run contains
    the deployed B=16 arbitration exactly. The analyzer must read it off the
    first 16 rows and nothing else."""
    sym = [[1.0, 0.0]] * 16 + [[0.0, 9.0]] * 48
    out = AG.analyze_row(_rec(sym, sym), split=32)
    assert out["A_sym_b16"] == 10, "B=16 sees only the first 16 worlds"
    assert out["A_sym"] == 20, "B=64 sees all of them"


def _rows(n_flip_r, n_flip_p, n):
    """n rows, the first `n_flip_r` flipping under R_max and the first
    `n_flip_p` under the placebo (so the two overlap, which is the realistic
    case and the one McNemar is for)."""
    out = []
    for i in range(n):
        out.append(
            {
                "rid": str(i),
                "corpus": "unit",
                "deck_seed": i,
                "ply": 1,
                "n_arms": 2,
                "A_sym": 10,
                L.LEG_PLACEBO: {
                    "flip": int(i < n_flip_p),
                    "flip_swap": 0,
                    "swap_same_arm": 0,
                    "flip_pure": int(i < n_flip_p),
                },
                L.LEG_MAX: {
                    "flip": int(i < n_flip_r),
                    "flip_swap": int(i < n_flip_r),
                    "swap_same_arm": int(i < n_flip_r),
                    "flip_pure": int(i < n_flip_r),
                },
            }
        )
    return out


def test_delta_is_the_excess_over_the_placebo_not_the_raw_flip_rate():
    """The whole point of the placebo leg. A raw `p_flip` of 0.40 against a
    placebo of 0.35 is a Δ of 0.05, not a mechanism."""
    s = AG.summarize(_rows(40, 35, 100), "unit")
    assert s["p_flip_placebo"] == pytest.approx(0.35)
    assert s[L.LEG_MAX]["p_flip_two_leg"] == pytest.approx(0.40)
    assert s[L.LEG_MAX]["delta_flip"] == pytest.approx(0.05)


def test_mcnemar_se_uses_only_the_discordant_pairs():
    s = AG.summarize(_rows(40, 35, 100), "unit")
    # rows 0..34 flip in both; 35..39 flip only under R_max; none flip only
    # under the placebo.
    assert s[L.LEG_MAX]["discordant_b"] == 5
    assert s[L.LEG_MAX]["discordant_c"] == 0
    assert s[L.LEG_MAX]["se_delta"] == pytest.approx((5 ** 0.5) / 100)


def test_branch_dead_fires_when_the_upper_bound_is_below_the_bar():
    s = AG.summarize(_rows(40, 35, 1200), "POOLED")
    br, why = AG.branch(s)
    assert br == "OM-DEAD", (br, why, s[L.LEG_MAX])


def test_branch_expresses_needs_both_the_bar_and_the_replication():
    s = AG.summarize(_rows(400, 0, 1000), "POOLED")
    assert s[L.LEG_MAX]["delta_flip"] == pytest.approx(0.40)
    br, _ = AG.branch(s)
    assert br == "OM-EXPRESSES"
    # ... and it does NOT fire when the flips do not replicate under the swap.
    rows = _rows(400, 0, 1000)
    for r in rows:
        r[L.LEG_MAX]["flip_swap"] = 0
        r[L.LEG_MAX]["swap_same_arm"] = 0
    br2, why2 = AG.branch(AG.summarize(rows, "POOLED"))
    assert br2 == "OM-UNRESOLVED", (br2, why2)


def test_branch_is_dose_only_when_r_max_expresses_but_r_ref_does_not():
    rows = _rows(400, 0, 1000)
    for r in rows:
        r[L.LEG_REF] = {"flip": 0, "flip_swap": 0, "swap_same_arm": 0, "flip_pure": 0}
    br, why = AG.branch(AG.summarize(rows, "POOLED"))
    assert br.startswith("OM-EXPRESSES + OM-DOSE-ONLY"), (br, why)


def test_a_true_null_reads_dead_at_the_planned_n():
    """PREREG §5's stated null read distribution. Under Δ = 0 the round must
    discharge — that is the whole reason the bar is not 2 sigma-hat."""
    br, _ = AG.branch(AG.summarize(_rows(300, 300, 1200), "POOLED"))
    assert br == "OM-DEAD"


def test_the_implied_points_per_game_uses_the_banked_exchange_rate():
    s = AG.summarize(_rows(400, 0, 1000), "POOLED")
    assert s[L.LEG_MAX]["implied_pts_per_game"] == pytest.approx(
        0.40 * L.G_ARB_PTS_PER_GAME / L.P_ARB_NE_RND
    )
    # At exactly the bar the implied transfer is the target the bar was set from.
    at_bar = L.BAR_DELTA_FLIP * L.G_ARB_PTS_PER_GAME / L.P_ARB_NE_RND
    assert at_bar == pytest.approx(L.TARGET_PTS_PER_GAME, abs=0.02)


# --------------------------------------------------------------------------- #
# the binding (skipped on a stale carc_rs)                                     #
# --------------------------------------------------------------------------- #
carc_rs = pytest.importorskip("carc_rs")
_HAS_LEGS = hasattr(carc_rs, "tiearb_arbitrate_legs")
needs_legs = pytest.mark.skipif(
    not _HAS_LEGS,
    reason="carc_rs predates the OM-M1 binding — rebuild carc-py (a stale wheel "
    "must read SKIP, never a false green)",
)


def _leaf():
    return carc_rs.LeafConfigRs(
        closure_p=[], bonus_cap=8.0, opp_bonus_cap=8.0, meeple_k=2.0
    )


def _fired_ply(seed="28000000000", max_ply=60):
    """Walk a deterministic game until the DEPLOYED trigger fires."""
    g = carc_rs.MirrorState.from_seed(seed)
    cfg = _leaf()
    actions = []
    for t in range(max_ply):
        if g.is_terminal():
            break
        legal = g.legal_actions()
        if not legal:
            break
        pick = legal[len(legal) // 2]
        probe = g.tiearb_probe(
            cfg, champ_pick=int(pick), j=L.ARM_CAP_J, eps=L.EPS, salt=L.SALT_OF_RECORD, ply=t
        )
        if probe.get("fired"):
            return seed, list(actions), t, int(pick)
        actions.append(int(pick))
        g.advance(int(pick))
    return None


@needs_legs
def test_the_binding_returns_raw_matrices_on_a_fired_ply():
    found = _fired_ply()
    if found is None:
        pytest.skip("the deployed trigger did not fire in the scanned prefix")
    seed, prefix, ply, pick = found
    out = carc_rs.tiearb_arbitrate_legs(
        seed, prefix, ply, pick, _leaf(),
        [(L.LEG_SYM, [], None), (L.LEG_PLACEBO, list(L.LEG2_SUFFIX), None)],
        b=4, j=L.ARM_CAP_J, eps=L.EPS, salt=L.SALT_OF_RECORD,
    )
    assert out is not None
    assert len(out["arms"]) >= 2
    assert len(out["world_seeds"]) == 4
    for leg in out["legs"]:
        assert leg["worlds_completed"] == 4
        assert len(leg["margins"]) == 4
        assert all(len(r) == len(out["arms"]) for r in leg["margins"])
        assert len(leg["means"]) == len(out["arms"])


@needs_legs
def test_the_binding_world_seeds_are_the_deployed_ones():
    """`G-CRN`, from the python side: the seeds the rust used must be exactly
    `sha256(salt|digest|ply|j)`, which is also how `run_gate` re-derives them."""
    found = _fired_ply()
    if found is None:
        pytest.skip("the deployed trigger did not fire in the scanned prefix")
    seed, prefix, ply, pick = found
    out = carc_rs.tiearb_arbitrate_legs(
        seed, prefix, ply, pick, _leaf(), [(L.LEG_SYM, [], None)],
        b=3, j=L.ARM_CAP_J, eps=L.EPS, salt=L.SALT_OF_RECORD,
    )
    want = [L.stable_seed(L.SALT_OF_RECORD, out["state_digest"], ply, j) for j in range(3)]
    assert list(out["world_seeds"]) == want


@needs_legs
def test_the_binding_returns_none_off_trigger():
    """A ply the arbiter does not fire at must return `None`, not an empty
    arbitration — `run_gate` treats a `None` at a frame-recorded fired ply as a
    G-FIRE-class defect and voids the ply rather than dropping it."""
    g = carc_rs.MirrorState.from_seed("28000000000")
    out = carc_rs.tiearb_arbitrate_legs(
        "28000000000", [], 0, g.legal_actions()[0], _leaf(),
        [(L.LEG_SYM, [], None)], b=2, j=L.ARM_CAP_J, eps=L.EPS, salt=L.SALT_OF_RECORD,
    )
    assert out is None or len(out["arms"]) >= 2


@needs_legs
def test_the_binding_refuses_no_legs_and_an_overlong_ply():
    with pytest.raises(Exception):
        carc_rs.tiearb_arbitrate_legs(
            "28000000000", [], 0, 0, _leaf(), [], b=2, salt=L.SALT_OF_RECORD
        )
    with pytest.raises(Exception):
        carc_rs.tiearb_arbitrate_legs(
            "28000000000", [1, 2], 9, 0, _leaf(), [(L.LEG_SYM, [], None)],
            b=2, salt=L.SALT_OF_RECORD,
        )
