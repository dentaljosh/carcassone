"""Contract tests for the Stage-1b TERMINAL-GROUNDED TIE ARBITRATION instruments
(scripts/tiletie/split_tiearb2.py, scripts/tiletie/analyze_tiearb2.py;
measurement/tiearb2_20260816/).

Pure plan/stat surgery -- no engine import, no search, no share writes, no
oracle record opened. Every fixture is synthetic and lives under tmp_path.

The centrepiece is section D: `_reference_branch` re-transcribes READ_RULE §4
INDEPENDENTLY of the implementation, and an `itertools.product` sweep straddles
every bar (including NaN) on both arms, both slices and the cost gate.
"""
from __future__ import annotations

import itertools
import json
import math
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import analyze_tiletie as AT       # noqa: E402
import analyze_tiearb as TA1       # noqa: E402
import analyze_tiearb2 as TB       # noqa: E402
import split_tiearb2 as SP         # noqa: E402


NAN = float("nan")
M = 8                              # the synthetic world count (sel/eva = 4 each)


# =========================================================================== #
# A. split_tiearb2.py -- the DESIGN §5.4 stratified symmetric half-split
# =========================================================================== #
def _arms_fixture(n_roots=40, pos_per_root=2, seed=7):
    """A synthetic ARMS.json-shaped dict spanning all 18 cells."""
    rng = random.Random(seed)
    arms = {}
    for i in range(n_roots):
        root = f"sp_{i:04d}"
        for k in range(pos_per_root):
            rid = f"tt_{root}_p{10 + k:02d}"
            n_arms = rng.choice([2, 3, 4, 5])
            arms[rid] = {
                "root_id": root,
                "stratum": "selfplay", "rules_profile": "walled",
                "phase_bucket": rng.choice(list(SP.PHASES)),
                "capped": False, "ply": 10 + k,
                "arms": [100 + j for j in range(n_arms)],
                "champ_arm_index": rng.choice([0] + list(range(n_arms))),
            }
    return arms


def test_all_eighteen_cells_are_declared_in_a_fixed_order():
    assert len(SP.ALL_CELLS) == 18 == len(set(SP.ALL_CELLS))
    assert SP.ALL_CELLS[0] == "early|2|T"
    assert SP.ALL_CELLS[-1] == "late|4-5|F"
    assert SP.SPLIT_SEED == 20260816


def test_arm_count_bucket_boundaries():
    assert SP.arm_count_bucket(2) == "2"
    assert SP.arm_count_bucket(3) == "3"
    assert SP.arm_count_bucket(4) == SP.arm_count_bucket(5) == "4-5"
    with pytest.raises(ValueError):
        SP.arm_count_bucket(1)


def test_position_cell_reads_the_three_axes():
    meta = {"phase_bucket": "mid", "arms": [1, 2, 3], "champ_arm_index": 0}
    assert SP.position_cell(meta) == "mid|3|T"
    meta["champ_arm_index"] = 2
    assert SP.position_cell(meta) == "mid|3|F"
    meta["phase_bucket"] = "nonsense"
    with pytest.raises(ValueError):
        SP.position_cell(meta)


def test_modal_cell_takes_the_majority():
    pairs = [("p3", "mid|2|T"), ("p1", "mid|2|T"), ("p2", "late|3|F")]
    assert SP.modal_cell(pairs) == "mid|2|T"


def test_modal_cell_tie_break_is_the_lexicographically_smallest_rid():
    # 1-1 tie; "p1" < "p2" so the cell holding p1 wins, whatever the input order.
    a = [("p2", "late|3|F"), ("p1", "mid|2|T")]
    b = list(reversed(a))
    assert SP.modal_cell(a) == SP.modal_cell(b) == "mid|2|T"
    # and the tie-break is on the RID, not on the cell name's own order
    c = [("p1", "late|3|F"), ("p2", "mid|2|T")]
    assert SP.modal_cell(c) == "late|3|F"


def test_modal_cell_rejects_an_empty_root():
    with pytest.raises(ValueError):
        SP.modal_cell([])


def test_split_balances_every_cell_to_within_one_root():
    split = SP.build_split(_arms_fixture(n_roots=60))
    assert split["balance_ok"] is True
    assert len(split["cells"]) == 18
    for cell, d in split["cells"].items():
        assert abs(d["n_S1_roots"] - d["n_S2_roots"]) <= 1, cell
        assert d["n_S1_roots"] + d["n_S2_roots"] == d["n_roots"]


def test_split_is_a_partition_of_the_roots_and_no_root_straddles():
    arms = _arms_fixture(n_roots=41, pos_per_root=3)
    split = SP.build_split(arms)
    s1, s2 = set(split["S1_roots"]), set(split["S2_roots"])
    all_roots = {m["root_id"] for m in arms.values()}
    assert s1 | s2 == all_roots
    assert not (s1 & s2)
    assert len(split["S1_roots"]) + len(split["S2_roots"]) == len(all_roots)
    # every POSITION of a root lands on that root's side -> no game straddles
    assert (split["n_S1_positions"] + split["n_S2_positions"]) == len(arms)
    assert split["n_roots"] == len(all_roots)


def test_split_is_reproducible_from_the_seed_and_independent_of_input_order():
    arms = _arms_fixture(n_roots=33)
    a = SP.build_split(arms)
    shuffled = dict(reversed(list(arms.items())))
    b = SP.build_split(shuffled)
    assert SP.canonical(a) == SP.canonical(b)
    # a different seed is a different carve (with overwhelming probability)
    c = SP.build_split(arms, seed=12345)
    assert c["S1_roots"] != a["S1_roots"]


def test_split_main_writes_and_verifies(tmp_path, capsys):
    arms_p = tmp_path / "ARMS.json"
    arms_p.write_text(json.dumps(_arms_fixture(n_roots=24)))
    out = tmp_path / "SPLIT.json"
    assert SP.main(["--arms", str(arms_p), "--out", str(out)]) == 0
    capsys.readouterr()
    assert out.is_file()
    doc = json.loads(out.read_text())
    assert doc["schema"] == SP.SCHEMA
    assert doc["seed"] == 20260816
    assert doc["balance_ok"] is True
    # --verify re-derives and asserts byte identity
    assert SP.main(["--arms", str(arms_p), "--out", str(out), "--verify"]) == 0
    capsys.readouterr()


def test_split_verify_fails_on_a_tampered_file(tmp_path, capsys):
    arms_p = tmp_path / "ARMS.json"
    arms_p.write_text(json.dumps(_arms_fixture(n_roots=20)))
    out = tmp_path / "SPLIT.json"
    SP.main(["--arms", str(arms_p), "--out", str(out)])
    capsys.readouterr()
    doc = json.loads(out.read_text())
    doc["S1_roots"], doc["S2_roots"] = doc["S2_roots"], doc["S1_roots"]
    out.write_text(json.dumps(doc))
    with pytest.raises(SystemExit, match="reproducibility FAILED"):
        SP.main(["--arms", str(arms_p), "--out", str(out), "--verify"])
    capsys.readouterr()


def test_split_verify_refuses_when_the_file_is_absent(tmp_path):
    arms_p = tmp_path / "ARMS.json"
    arms_p.write_text(json.dumps(_arms_fixture(n_roots=6)))
    with pytest.raises(SystemExit, match="does not exist"):
        SP.main(["--arms", str(arms_p), "--out", str(tmp_path / "nope.json"),
                 "--verify"])


def test_split_refuses_a_missing_arms_file(tmp_path):
    with pytest.raises(SystemExit, match="ARMS.json not found"):
        SP.main(["--arms", str(tmp_path / "absent.json"),
                 "--out", str(tmp_path / "S.json")])


# =========================================================================== #
# B. arb_at_budget -- the DESIGN §5.2 selection-budget clipping
# =========================================================================== #
def _rec(values_a, values_b, pick_a, pick_b, *, seeds=None, crn=True, checksum=True):
    seeds = seeds if seeds is not None else list(range(1, M + 1))
    return {"values_a": list(values_a), "values_b": list(values_b),
            "world_seeds": list(seeds), "playout_seeds": [s + 1000 for s in seeds],
            "crn_verified": crn, "checksum_ok": checksum,
            "pick_a": pick_a, "pick_b": pick_b, "distinct_afterstates": M,
            "m": M, "ok": True, "elapsed_secs": 1.0,
            "world_seed_salt": "tiletie-v1"}


def _fixture(if_rows, arb_rows, *, rid="p1", root="R1", champ_arm_index=0,
             n_positions=1):
    n_arms = len(if_rows)
    actions = [100 + i for i in range(n_arms)]
    arms_index, if_by, arb_by = {}, {}, {}
    for i in range(n_positions):
        r = rid if n_positions == 1 else f"{rid}_{i}"
        rt = root if n_positions == 1 else f"{root}_{i}"
        arms_index[r] = {"root_id": rt, "stratum": "selfplay", "rules_profile": "walled",
                         "phase_bucket": "mid", "capped": False, "ply": 40,
                         "arms": actions, "champ_arm_index": champ_arm_index}
        if_by[r] = {leg: _rec(if_rows[0], if_rows[leg], actions[0], actions[leg])
                    for leg in range(1, n_arms)}
        arb_by[r] = {leg: _rec(arb_rows[0], arb_rows[leg], actions[0], actions[leg])
                     for leg in range(1, n_arms)}
    return arms_index, if_by, arb_by


_RATES = {"by_stratum": {"selfplay": {"scale_all": 1.0, "scale_strict": 1.0}}}


def _const(v):
    return [float(v)] * M


def test_budget_16_is_bit_identical_to_stage1_crossfit_regret():
    """⭐ THE HONEST ARM MUST BE BIT-IDENTICAL TO STAGE 1's ESTIMATOR.

    `analyze_tiearb` computes `a_arb` as `crossfit_regret(matrix_arb, sel, eva,
    champ)[1]` and prices it as `_sub_mean(if[a_arb], eva) - _sub_mean(if[champ],
    eva)`. `arb_at_budget(..., B=len(sel))` must reproduce BOTH exactly -- `==`,
    not `approx`.
    """
    rng = random.Random(20260816)
    for _ in range(200):
        n_arms = rng.choice([2, 3, 4, 5])
        matrix_if = [[rng.uniform(-9, 9) for _ in range(M)] for _ in range(n_arms)]
        matrix_arb = [[rng.uniform(-9, 9) for _ in range(M)] for _ in range(n_arms)]
        champ = rng.randrange(n_arms)
        for swap in (False, True):
            sel, eva = AT.parity_indices(M, base=1, swap=swap)
            got, a_got = TB.arb_at_budget(matrix_arb, matrix_if, sel, eva, champ,
                                          len(sel))
            _sec, a_ref = AT.crossfit_regret(matrix_arb, sel, eva, champ)
            ref = (AT._sub_mean(matrix_if[a_ref], eva)
                   - AT._sub_mean(matrix_if[champ], eva))
            assert a_got == a_ref
            assert got == ref            # BIT-identical, not approx


def test_sec_arb_at_full_budget_is_the_arb_judges_own_crossfit_headroom():
    """SEC-ARB is `arb_at_budget(matrix_arb, matrix_arb, ...)` and at full budget
    that IS `crossfit_regret(matrix_arb, ...)` -- bit-identical, which is exactly
    why its capture fraction against its own headroom is 1 BY CONSTRUCTION."""
    rng = random.Random(5)
    for _ in range(50):
        mat = [[rng.uniform(-5, 5) for _ in range(M)] for _ in range(4)]
        champ = rng.randrange(4)
        sel, eva = AT.parity_indices(M, base=1)
        got, _ = TB.arb_at_budget(mat, mat, sel, eva, champ, len(sel))
        ref, _ = AT.crossfit_regret(mat, sel, eva, champ)
        assert got == ref


def test_smaller_budget_uses_a_strict_ascending_prefix_of_the_same_worlds():
    """The budget touches SELECTION only, and only as a prefix of `sorted(sel)`."""
    sel, eva = AT.parity_indices(M, base=1)
    assert sel == sorted(sel)                       # parity_indices is ascending
    # arm 1 wins on the first two selection worlds, arm 2 wins over all four.
    mat_arb = [_const(0.0), [0.0] * M, [0.0] * M]
    for j, s in enumerate(sel):
        mat_arb[1][s] = 10.0 if j < 2 else -10.0
        mat_arb[2][s] = 0.0 if j < 2 else 100.0
    mat_if = [_const(0.0), _const(1.0), _const(5.0)]
    v1, a1 = TB.arb_at_budget(mat_arb, mat_if, sel, eva, 0, 2)
    v2, a2 = TB.arb_at_budget(mat_arb, mat_if, sel, eva, 0, 4)
    assert a1 == 1 and a2 == 2                      # more worlds -> better arm
    assert v1 == pytest.approx(1.0) and v2 == pytest.approx(5.0)
    assert v2 > v1                                  # strictly improved selection


def test_pricing_is_never_clipped_by_the_budget():
    """Two runs at different B that happen to pick the SAME arm must price it
    identically -- the evaluation half is never touched."""
    sel, eva = AT.parity_indices(M, base=1)
    mat_arb = [_const(0.0), _const(9.0), _const(1.0)]     # arm 1 wins at EVERY B
    mat_if = [[0.0] * M, [float(j) for j in range(M)], _const(-3.0)]
    vals = {b: TB.arb_at_budget(mat_arb, mat_if, sel, eva, 0, b) for b in (1, 2, 4)}
    assert {v[1] for v in vals.values()} == {1}
    assert vals[1][0] == vals[2][0] == vals[4][0]
    # and the priced value uses the FULL eva half, not a prefix of it
    assert vals[1][0] == pytest.approx(AT._sub_mean(mat_if[1], eva)
                                       - AT._sub_mean(mat_if[0], eva))


def test_budget_is_clamped_to_the_selection_half_and_rejects_zero():
    sel, eva = AT.parity_indices(M, base=1)
    mat = [_const(0.0), _const(1.0)]
    assert TB.arb_at_budget(mat, mat, sel, eva, 0, 999) == TB.arb_at_budget(
        mat, mat, sel, eva, 0, len(sel))
    with pytest.raises(ValueError):
        TB.arb_at_budget(mat, mat, sel, eva, 0, 0)


def test_budget_ladder_is_monotone_in_information_not_in_value():
    """More selection worlds cannot be WORSE in expectation -- the property that
    makes `B-ANOMALY` a noise signature rather than a finding. Checked as an
    average over random draws (a single position may go either way)."""
    rng = random.Random(3)
    tot = {1: 0.0, 4: 0.0}
    for _ in range(400):
        truth = [rng.gauss(0, 1) for _ in range(3)]
        mat_arb = [[t + rng.gauss(0, 2) for _ in range(M)] for t in truth]
        mat_if = [[t + rng.gauss(0, 0.1) for _ in range(M)] for t in truth]
        sel, eva = AT.parity_indices(M, base=1)
        for b in (1, 4):
            tot[b] += TB.arb_at_budget(mat_arb, mat_if, sel, eva, 0, b)[0]
    assert tot[4] > tot[1]


# =========================================================================== #
# C. build_positions -- the estimator wiring
# =========================================================================== #
def _sym_crossfit(matrix, champ_pos):
    out = []
    for swap in (False, True):
        sel, eva = AT.parity_indices(M, base=1, swap=swap)
        r, _ = AT.crossfit_regret(matrix, sel, eva, champ_pos)
        out.append(r)
    return (out[0] + out[1]) / 2.0


def test_ora_equals_symmetrized_crossfit_regret_and_arb_H_equals_stage1():
    if_rows = [_const(0.0), _const(1.0), _const(3.0)]
    arb_rows = [_const(5.0), _const(1.0), _const(0.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=1)
    rows, _i, _c, _n = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S1"},
                                          rnd_seed=20260816, b_star=2)
    r = rows[0]
    assert r["champ_pos"] == 1
    assert r["ora"] == pytest.approx(_sym_crossfit(if_rows, 1))
    # Stage 1's `arb` on the identical fixture
    s1rows, *_ = TA1.build_positions(arms, ifb, arbb, _RATES, set(), rnd_seed=20260816)
    assert r["arb_H"] == s1rows[0]["arb"]           # bit-identical
    assert r["arb_b16"] == r["arb_H"]
    assert r["sec_H"] == s1rows[0]["sec"]
    assert r["arm0_H"] == s1rows[0]["arm0"]
    assert r["rnd"] == s1rows[0]["rnd"]
    assert r["slice"] == "S1"


def test_every_ladder_rung_is_emitted_per_position():
    if_rows = [_const(0.0), _const(1.0), _const(3.0)]
    arb_rows = [_const(5.0), _const(1.0), _const(0.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=1)
    rows, *_ = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S2"},
                                  rnd_seed=1, b_star=4)
    r = rows[0]
    for b in TB.B_LADDER:
        assert f"arb_b{b}" in r
        assert len(r[f"a_arb_b{b}_folds"]) == 2
    assert r["arb_C"] == r["arb_b4"]
    assert r["b_C"] == 4 and r["b_H"] == 16
    assert r["agree_hc"] is (r["a_arb_b16_folds"] == r["a_arb_b4_folds"])


def test_agree_hc_is_true_when_b_star_is_16():
    if_rows = [_const(0.0), _const(1.0), _const(3.0)]
    arb_rows = [_const(0.0), _const(1.0), _const(9.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    rows, *_ = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S1"},
                                  rnd_seed=1, b_star=16)
    assert rows[0]["agree_hc"] is True
    assert rows[0]["arb_C"] == rows[0]["arb_H"]


def test_realized_world_seed_salt_is_read_off_the_records_not_assumed():
    """DESIGN §0.A withdrew §4.5's `tiearb2-v1`; the read-out must therefore report
    the salt the records actually carry, never a hardcoded string."""
    if_rows = [_const(0.0), _const(1.0)]
    arb_rows = [_const(0.0), _const(2.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    _rows, _i, cross, _c = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S1"},
                                              rnd_seed=1, b_star=2)
    assert cross["world_seed_salt_if"] == ["tiletie-v1"]
    assert cross["world_seed_salt_arb"] == ["tiletie-v1"]
    # a record without the field simply contributes nothing (never a crash)
    for leg in arbb["p1"].values():
        leg.pop("world_seed_salt")
    _rows, _i, cross2, _c = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S1"},
                                               rnd_seed=1, b_star=2)
    assert cross2["world_seed_salt_arb"] == []


def test_unsplit_root_is_counted_and_still_analysed():
    if_rows = [_const(0.0), _const(1.0)]
    arb_rows = [_const(0.0), _const(1.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    rows, _i, _c, counts = TB.build_positions(arms, ifb, arbb, _RATES, {},
                                              rnd_seed=1, b_star=2)
    assert len(rows) == 1 and rows[0]["slice"] is None
    assert counts["unsplit"] == 1


def test_integrity_exclusions_mirror_stage1():
    if_rows = [_const(0.0), _const(1.0), _const(2.0)]
    arb_rows = [_const(0.0), _const(1.0), _const(2.0)]
    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    del arbb["p1"][2]                                  # G-ARMSET
    rows, _i, _cr, counts = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S1"},
                                               rnd_seed=1, b_star=2)
    assert rows == [] and counts["armset_mismatch"] == 1
    assert counts["armset_mismatch_frac"] == pytest.approx(1.0)

    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    arbb["p1"][1]["world_seeds"][3] = 999999           # G-CRN
    _rows, _i, cross, _c = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S1"},
                                              rnd_seed=1, b_star=2)
    assert cross["crn_cross_mismatch"] == 1

    arms, ifb, arbb = _fixture(if_rows, arb_rows, champ_arm_index=0)
    arms["p1"]["champ_arm_index"] = 7                  # champion arm absent
    rows, _i, _cr, counts = TB.build_positions(arms, ifb, arbb, _RATES, {"R1": "S1"},
                                               rnd_seed=1, b_star=2)
    assert rows == [] and counts["champ_arm_absent"] == 1


# =========================================================================== #
# D. decide_branch -- the READ_RULE §3/§4 truth table, re-transcribed
# =========================================================================== #
ALL_GATES = ("G-CRN", "G-ARM", "G-VA", "G-ARMSET", "G-SPLIT", "G-N", "G-DENOM")


def _pre(**over):
    d = {g: True for g in ALL_GATES}
    d.update(over)
    return d


def _reference_branch(H, C, slices, rho):
    """READ_RULE §4 transcribed INDEPENDENTLY of `analyze_tiearb2`.

    `H`/`C` = (z, F, F_fixed, gboot); `slices` = {s: (z_ora, rnd, arb_H, arb_C)}.
    Returns (branch, p, q, ANY_R_H, ANY_R_C, informative, drifted).
    """
    def ge(x, bar):
        return bool(x == x and x >= bar)

    def le(x, bar):
        return bool(x == x and x <= bar)

    informative = [s for s in ("S1", "S2") if ge(slices[s][0], 2.0)]
    d_rnd = abs(slices["S1"][1] - slices["S2"][1])
    drifted = ge(d_rnd, 0.20)

    def arm(stat, idx):
        z, F, Ff, gb = stat
        C_z = ge(z, 2.0)
        RBAR = ge(Ff, 0.35) and (ge(F, 0.35) or bool(gb))
        ANY_R = ge(Ff, 0.35) or (ge(F, 0.35) and not bool(gb))
        if not informative:
            C_split = False
        else:
            oks = []
            for s in informative:
                arb_s = slices[s][idx]
                rnd_s = slices[s][1]
                oks.append(ge(arb_s, 0.0)
                           or (drifted and ge(arb_s - rnd_s, 0.0)))
            C_split = all(oks)
        return (C_z and RBAR and C_split), ANY_R

    pass_H, any_H = arm(H, 2)
    pass_C, any_C = arm(C, 3)
    p = pass_H
    q = bool(pass_C and le(rho, 1.20))
    #: READ_RULE §4's five conditions, each written INDEPENDENTLY (no if/elif
    #: chain) so the caller can assert that EXACTLY ONE fires -- which is the
    #: exclusivity+exhaustiveness property §4.1 claims.
    fired = [nm for nm, cond in (
        ("A-DEPLOYABLE", p and q),
        ("A-COSTLY", p and not q),
        ("B-ANOMALY", (not p) and q),
        ("P-PARTIAL2", (not p) and (not q) and (any_H or any_C)),
        ("F-FLAT2", (not p) and (not q) and (not any_H) and (not any_C)),
    ) if cond]
    return fired, p, q, any_H, any_C, informative, drifted


def _call(H, C, slices, rho, pre=None):
    arms_stats = {"H": {"z": H[0], "F": H[1], "F_fixed": H[2], "gboot": H[3]},
                  "C": {"z": C[0], "F": C[1], "F_fixed": C[2], "gboot": C[3]}}
    sl = {s: {"z_ora": v[0], "rnd": v[1], "arb": {"H": v[2], "C": v[3]}}
          for s, v in slices.items()}
    return TB.decide_branch(arms_stats, sl, rho, pre if pre is not None else _pre())


# --- the grids: every bar straddled, NaN in every position ------------------ #
_ZS = (1.0, 1.9999, 2.0, 3.5, NAN)
_FS = (0.0, 0.34, 0.35, 0.9, NAN)
_GBS = (False, True)
_RHOS = (1.19, 1.20, 1.21)

#: slice configurations: (z_ora_S1, rnd_S1, arb_H_S1, arb_C_S1),
#:                       (z_ora_S2, rnd_S2, arb_H_S2, arb_C_S2)
#: chosen to exercise: both informative / one / none; drifted / not; the escape
#: clause opening and NOT opening; NaN in a slice arb and in a slice z.
_SLICE_CFGS = (
    # both informative, both positive, no drift
    {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, 0.10, 0.25, 0.15)},
    # both informative, S2 negative, NO drift -> C_split fails
    {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, 0.10, -0.05, -0.02)},
    # both informative, S2 negative but DRIFTED and arb-rnd >= 0 -> escape opens
    {"S1": (3.0, 0.13, 0.30, 0.20), "S2": (3.0, -0.30, -0.05, -0.02)},
    # DRIFTED but S2 negative on BOTH arb_s and arb_s - rnd_s -> still fails
    {"S1": (3.0, 0.13, 0.30, 0.20), "S2": (3.0, 0.40, -0.60, -0.70)},
    # only S1 informative; S2 negative but UNINFORMATIVE -> never FAIL
    {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (1.0, 0.10, -0.90, -0.90)},
    # only S2 informative
    {"S1": (0.5, 0.05, -0.90, -0.90), "S2": (2.0, 0.10, 0.25, 0.15)},
    # NEITHER informative -> C_split is False for both arms
    {"S1": (1.9999, 0.05, 0.30, 0.20), "S2": (0.0, 0.10, 0.25, 0.15)},
    # NaN z_ora on one slice, NaN arb on the other
    {"S1": (NAN, 0.05, 0.30, 0.20), "S2": (3.0, 0.10, NAN, 0.15)},
    # NaN rnd -> D_rnd is NaN -> never drifted
    {"S1": (3.0, NAN, -0.10, -0.10), "S2": (3.0, 0.10, -0.10, -0.10)},
)

_ARM_CFGS = tuple(itertools.product(_ZS, _FS, _FS, _GBS))


def test_branch_sweep_is_exclusive_exhaustive_and_matches_the_reference():
    """⭐ The machine sweep READ_RULE §4.1 names. `_reference_branch` is an
    INDEPENDENT re-transcription; the grid straddles every bar including NaN."""
    n = 0
    branches_seen = set()
    # the arm grid is 5*5*5*2 = 250 per arm; sweeping H x C fully would be 62,500
    # x 9 slice cfgs x 3 rhos. We sweep the FULL arm grid on H against a small
    # spanning set on C, and the FULL grid on C against a spanning set on H, so
    # every arm cell is visited on both sides.
    c_span = ((3.5, 0.9, 0.9, False), (1.0, 0.9, 0.9, False),
              (3.5, 0.0, 0.0, False), (NAN, NAN, NAN, True))
    h_span = c_span
    cases = ([(h, c) for h in _ARM_CFGS for c in c_span]
             + [(h, c) for c in _ARM_CFGS for h in h_span])
    for H, C in cases:
        for slices in _SLICE_CFGS:
            for rho in _RHOS:
                got = _call(H, C, slices, rho)
                (fired, p, q, any_H, any_C,
                 informative, drifted) = _reference_branch(H, C, slices, rho)
                # ⭐ EXACTLY ONE branch condition fires, on every cell
                assert len(fired) == 1, (H, C, slices, rho, fired)
                assert got["branch"] == fired[0], (H, C, slices, rho,
                                                   got["branch"], fired)
                assert got["p"] is p and got["q"] is q
                assert got["arms"]["H"]["ANY_R"] is any_H
                assert got["arms"]["C"]["ANY_R"] is any_C
                assert got["informative_slices"] == informative
                assert got["baseline_drifted"] is drifted
                assert got["branch"] in TB.BRANCH_TEXT
                assert got["read"] == TB.BRANCH_TEXT[got["branch"]][1]
                # READ_RULE §4.1: RBAR(x) => ANY_R(x)
                for x in ("H", "C"):
                    assert (not got["arms"][x]["RBAR"]) or got["arms"][x]["ANY_R"]
                branches_seen.add(got["branch"])
                n += 1
    # pin the cell count so a shrunk grid fails LOUDLY
    assert len(_ARM_CFGS) == 250
    assert len(cases) == 250 * 4 * 2 == 2000
    assert n == 2000 * len(_SLICE_CFGS) * len(_RHOS) == 54000
    # every non-U branch was actually exercised by the grid
    assert branches_seen == {"A-DEPLOYABLE", "A-COSTLY", "B-ANOMALY",
                             "P-PARTIAL2", "F-FLAT2"}


def test_the_p_q_grid_is_exactly_partitioned():
    """READ_RULE §4.1's (p, q) table, asserted cell by cell -- and that exactly
    one branch name matches every cell."""
    seen = {}
    for H, C in itertools.product(
            ((3.5, 0.9, 0.9, False), (1.0, 0.9, 0.9, False), (3.5, 0.0, 0.0, False)),
            ((3.5, 0.9, 0.9, False), (1.0, 0.9, 0.9, False), (3.5, 0.0, 0.0, False))):
        for rho in (1.19, 1.21):
            slices = {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, 0.10, 0.25, 0.15)}
            got = _call(H, C, slices, rho)
            p, q = got["p"], got["q"]
            expect = {(True, True): "A-DEPLOYABLE", (True, False): "A-COSTLY",
                      (False, True): "B-ANOMALY"}.get((p, q))
            if expect is None:
                expect = ("P-PARTIAL2"
                          if (got["arms"]["H"]["ANY_R"] or got["arms"]["C"]["ANY_R"])
                          else "F-FLAT2")
            assert got["branch"] == expect
            seen[(p, q)] = seen.get((p, q), 0) + 1
    # all four (p, q) cells were actually exercised
    assert set(seen) == {(True, True), (True, False), (False, True), (False, False)}


def test_u_unreadable_preempts_every_gate_and_every_reading():
    n = 0
    for gate in ALL_GATES:
        for H in ((3.5, 0.9, 0.9, False), (1.0, 0.1, 0.1, True)):
            for rho in (1.19, 1.21):
                got = _call(H, (3.5, 0.9, 0.9, False),
                            {"S1": (3.0, 0.0, 0.5, 0.5), "S2": (3.0, 0.0, 0.5, 0.5)},
                            rho, _pre(**{gate: False}))
                assert got["branch"] == "U-UNREADABLE"
                assert got["failed_preconditions"] == [gate]
                assert got["p"] is None and got["q"] is None
                assert got["arms"] == {}
                n += 1
    assert n == len(ALL_GATES) * 4


def test_u_unreadable_lists_every_failed_gate():
    got = _call((9.0, 9.0, 9.0, False), (9.0, 9.0, 9.0, False),
                {"S1": (9.0, 0.0, 9.0, 9.0), "S2": (9.0, 0.0, 9.0, 9.0)}, 0.1,
                _pre(**{"G-N": False, "G-DENOM": False}))
    assert got["branch"] == "U-UNREADABLE"
    assert got["failed_preconditions"] == ["G-DENOM", "G-N"]


# --- C_split semantics, stated one property per test ------------------------ #
_GOOD = (3.5, 0.9, 0.9, False)


def test_c_split_treats_a_non_informative_slice_as_uninformative_not_fail():
    slices = {"S1": (3.0, 0.05, 0.30, 0.20),
              "S2": (1.0, 0.05, -5.0, -5.0)}      # hugely negative but UNINFORMATIVE
    got = _call(_GOOD, _GOOD, slices, 1.0)
    assert got["informative_slices"] == ["S1"]
    assert got["arms"]["H"]["C_split"] is True
    assert got["arms"]["H"]["slice_ok"]["S2"] is None
    assert got["branch"] == "A-DEPLOYABLE"


def test_c_split_requires_at_least_one_informative_slice():
    slices = {"S1": (1.0, 0.05, 5.0, 5.0), "S2": (1.0, 0.05, 5.0, 5.0)}
    got = _call(_GOOD, _GOOD, slices, 1.0)
    assert got["informative_slices"] == []
    assert got["arms"]["H"]["C_split"] is False
    assert got["branch"] == "P-PARTIAL2"          # ANY_R still fires
    assert any("C_split" in s and "NO slice is INFORMATIVE" in s
               for s in got["failed_conjuncts"]["H"])


def test_escape_clause_opens_only_when_the_baseline_drifted():
    # arb_S2 < 0 but arb_S2 - rnd_S2 > 0.
    drifted = {"S1": (3.0, 0.15, 0.30, 0.20), "S2": (3.0, -0.30, -0.05, -0.02)}
    not_drifted = {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, -0.10, -0.05, -0.02)}
    assert abs(0.15 - (-0.30)) >= TB.DRIFT_BAR
    assert abs(0.05 - (-0.10)) < TB.DRIFT_BAR
    g1 = _call(_GOOD, _GOOD, drifted, 1.0)
    assert g1["baseline_drifted"] is True
    assert g1["arms"]["H"]["C_split"] is True
    assert g1["escape_clause_used"]["H"]["S2"] is True
    assert g1["escape_clause_used"]["H"]["S1"] is False     # S1 passed directly
    g2 = _call(_GOOD, _GOOD, not_drifted, 1.0)
    assert g2["baseline_drifted"] is False
    assert g2["arms"]["H"]["C_split"] is False
    assert g2["escape_clause_used"]["H"]["S2"] is False


def test_a_slice_negative_on_both_statistics_fails_even_when_drifted():
    slices = {"S1": (3.0, 0.10, 0.30, 0.20), "S2": (3.0, 0.40, -0.60, -0.70)}
    got = _call(_GOOD, _GOOD, slices, 1.0)
    assert got["baseline_drifted"] is True
    assert got["arms"]["H"]["C_split"] is False
    assert got["escape_clause_used"]["H"]["S2"] is False
    assert "C_split" in " ".join(got["failed_conjuncts"]["H"])


def test_c_split_keys_on_the_slice_numerator_not_a_slice_F():
    """READ_RULE §4: a noisy slice DENOMINATOR cannot flip the conjunct -- the
    branch function is never handed a slice `F`."""
    import inspect
    src = inspect.getsource(TB.decide_branch)
    assert "F_s" not in src and "slice_F" not in src
    # the only slice inputs are z_ora, rnd and arb
    slices = {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, 0.05, 0.30, 0.20)}
    got = _call(_GOOD, _GOOD, slices, 1.0)
    assert got["arms"]["H"]["C_split"] is True


def test_deploy_bar_is_inclusive_and_nan_never_deploys():
    slices = {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, 0.05, 0.30, 0.20)}
    assert _call(_GOOD, _GOOD, slices, 1.20)["DEPLOY"] is True
    assert _call(_GOOD, _GOOD, slices, 1.2000001)["DEPLOY"] is False
    assert _call(_GOOD, _GOOD, slices, NAN)["DEPLOY"] is False
    assert _call(_GOOD, _GOOD, slices, None)["DEPLOY"] is False
    assert _call(_GOOD, _GOOD, slices, NAN)["branch"] == "A-COSTLY"


def test_g_boot_voids_F_as_a_branch_input():
    slices = {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, 0.05, 0.30, 0.20)}
    # F below bar, F_fixed above, G-BOOT FIRED => the conjunct rests on F_fixed
    fired = (3.0, 0.1, 0.9, True)
    assert _call(fired, fired, slices, 1.0)["branch"] == "A-DEPLOYABLE"
    not_fired = (3.0, 0.1, 0.9, False)
    got = _call(not_fired, not_fired, slices, 1.0)
    assert got["arms"]["H"]["RBAR"] is False
    assert got["arms"]["H"]["ANY_R"] is True         # F_fixed alone still >= bar
    assert got["branch"] == "P-PARTIAL2"


def test_nan_never_fires_a_conjunct():
    slices = {"S1": (NAN, NAN, NAN, NAN), "S2": (NAN, NAN, NAN, NAN)}
    got = _call((NAN, NAN, NAN, False), (NAN, NAN, NAN, False), slices, NAN)
    assert got["branch"] == "F-FLAT2"
    for x in ("H", "C"):
        a = got["arms"][x]
        assert (a["C_z"], a["RBAR"], a["ANY_R"], a["C_split"], a["PASS"]) == (
            False, False, False, False, False)
    assert got["baseline_drifted"] is False
    assert got["DEPLOY"] is False


def test_failed_conjuncts_names_exactly_which_one():
    slices = {"S1": (3.0, 0.05, 0.30, 0.20), "S2": (3.0, 0.05, 0.30, 0.20)}
    got = _call((1.0, 0.9, 0.9, False), _GOOD, slices, 1.0)
    assert got["failed_conjuncts"]["H"] == ["C_z (z >= +2.0)"]
    assert got["failed_conjuncts"]["C"] == []
    got = _call((3.0, 0.1, 0.1, False), _GOOD, slices, 1.0)
    assert got["failed_conjuncts"]["H"] == [
        "RBAR ((F_fixed >= 0.35) and ((F >= 0.35) or G-BOOT fired))"]


def test_bars_are_the_committed_constants():
    assert TB.RATIO_BAR == 0.35
    assert TB.Z_BAR == 2.0
    assert TB.FIXED_DENOM == 0.2803
    assert TB.GBOOT_BAR == 0.05
    assert TB.DRIFT_BAR == 0.20
    assert TB.RHO_BAR == 1.20
    assert TB.B_LADDER == (1, 2, 4, 8, 16)
    assert TB.B_HONEST == 16
    assert TB.M_EXPECTED == 32
    assert TB.BOOT_REPS == 20000
    assert TB.T_CHAMP == 13.7552
    assert TB.T_PHONE == 1.551
    # ⭐ the CORPUS block: Stage 1's hard-coded floors are now parameters
    assert TB.CORPUS["n_floor_pooled"] == 1040
    assert TB.CORPUS["n_floor_slice"] == 400
    assert TA1.N_FLOOR_POOLED == 650 and TA1.N_FLOOR_HOLDOUT == 158   # untouched


# =========================================================================== #
# E. cost -- rho ladder, B*, and the RUN_MANIFEST key-spelling bug fix
# =========================================================================== #
def test_rho_ladder_matches_the_design_arithmetic():
    lad = TB.rho_ladder(3.0027, 2.1236)
    for b in TB.B_LADDER:
        d = lad[str(b)]
        assert d["rho_wall"] == pytest.approx(3.0027 * b * 2.1236 / 13.7552)
        assert d["rho_amortized"] == pytest.approx(d["rho_wall"] * 22.96 / 72.0)
        assert d["rho_phone"] == pytest.approx(3.0027 * b * 2.1236 / 1.551)
    # DESIGN §7.2's advance arithmetic: B=1,2 legal; 4,8,16 not
    assert [b for b in TB.B_LADDER if lad[str(b)]["legal"]] == [1, 2]
    assert TB.b_star_from_cost(3.0027, 2.1236) == 2
    assert TB.b_star_from_cost(3.0027, 2.5197) == 2     # the other end of the bracket


def test_b_star_falls_back_to_one_when_no_budget_qualifies():
    assert TB.b_star_from_cost(3.0, 100.0) == 1
    assert TB.rho_ladder(None, 2.0) == {}
    assert TB.rho_ladder(3.0, None) == {}


def test_manifest_cost_reads_BOTH_key_spellings():
    """⚠️ Stage 1's `cost_block` read `elapsed_secs`/`playouts`; run_tiletie writes
    `wall_secs`/`n`, which is why the committed Stage-1 READOUT carries
    `c_tier1 = null` from that path. Both spellings are read here."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        # run_tiletie's REAL shape
        (d / "RUN_MANIFEST_chunk1.json").write_text(json.dumps({"legs": [
            {"judge": "tier1-greedy", "n": 10, "workers": 4, "wall_secs": 100.0}]}))
        out = TB.manifest_cost(d, m=32)
        assert out["playouts"] == 10 * 2 * 32
        assert out["playouts_source"] == "n x 2 x m"
        assert out["key_spelling_seen"] == ["wall_secs"]
        assert out["c_from_elapsed_secs"] is None
        assert out["c_from_wall_times_workers"] == pytest.approx(400.0 / 640)
        # the other spelling
        (d / "RUN_MANIFEST_chunk2.json").write_text(json.dumps({"legs": [
            {"elapsed_secs": 640.0, "playouts": 640}]}))
        out = TB.manifest_cost(d, m=32)
        assert out["key_spelling_seen"] == ["elapsed_secs", "wall_secs"]
        assert out["playouts"] == 640 + 640
        assert out["sum_elapsed_secs"] == 640.0
        assert out["n_legs"] == 2


def test_manifest_cost_on_the_committed_stage1_manifests_is_no_longer_null():
    """Regression witness for the fix: Stage 1's own manifests, read with the
    corrected key spellings, now yield a NUMBER where `analyze_tiearb.cost_block`
    yields None."""
    d = REPO / "measurement/tiearb_20260816"
    if not any(d.glob("RUN_MANIFEST_chunk*.json")):
        pytest.skip("Stage-1 manifests not present")
    old = TA1.cost_block(d)
    new = TB.manifest_cost(d, m=32)
    assert old["c_tier1_worker_s_per_playout"] is None          # the BUG
    assert new["c_from_wall_times_workers"] is not None         # the FIX
    assert "wall_secs" in new["key_spelling_seen"]
    assert new["playouts"] and new["playouts"] > 0


def test_read_pilot_finds_b_star_at_any_nesting_depth(tmp_path):
    p = tmp_path / "PILOT.json"
    p.write_text(json.dumps({"cost": {"c_tier1_worker_s_per_playout": 2.1236},
                             "mechanical_rule": {"B_star": 2},
                             "g_repro": {"ok": 43}}))
    d = TB.read_pilot(p)
    assert d["present"] is True
    assert d["B_star"] == 2
    assert d["c_tier1_worker_s_per_playout"] == pytest.approx(2.1236)
    assert d["g_repro"] == {"ok": 43}
    absent = TB.read_pilot(tmp_path / "nope.json")
    assert absent["present"] is False and absent["B_star"] is None


# =========================================================================== #
# F. aggregation wiring
# =========================================================================== #
def _agg_rows(n=24, seed=19):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        r = {"rid": f"p{i}", "root_id": f"R{i % 6}", "stratum": "selfplay",
             "rules_profile": "walled", "phase_bucket": "mid", "capped": bool(i % 3),
             "ply": 40, "slice": "S1" if i % 2 else "S2", "champ_pos": 0,
             "n_arms_scored": 3, "m": M,
             "ora": rng.uniform(0, 3), "ora_p1": rng.uniform(0, 3),
             "rnd": rng.uniform(-1, 1), "a_rnd": 0, "a_ora_folds": [0, 1],
             "agree_hc": True, "scale_all": 0.74, "scale_strict": 0.78}
        for b in TB.B_LADDER:
            r[f"arb_b{b}"] = rng.uniform(-1, 2)
            r[f"a_arb_b{b}_folds"] = [0, 1]
        for arm, b in (("H", 16), ("C", 2)):
            r[f"b_{arm}"] = b
            r[f"arb_{arm}"] = r[f"arb_b{b}"]
            r[f"arb_{arm}_p1"] = rng.uniform(-1, 2)
            r[f"sec_{arm}"] = rng.uniform(-1, 1)
            r[f"arm0_{arm}"] = rng.uniform(-1, 1)
            r[f"arb_{arm}_minus_rnd"] = r[f"arb_{arm}"] - r["rnd"]
            r[f"a_arb_{arm}_folds"] = [0, 1]
            r[f"pickchg_{arm}"] = True
            r[f"sel_agree_{arm}"] = False
        rows.append(r)
    return rows


def test_agg_block_and_cuts_and_ladder_wire_through_analyze_tiletie(monkeypatch):
    monkeypatch.setattr(TB, "BOOT_REPS", 200)
    rows = _agg_rows()
    blk = TB.agg_block(rows, seed=1)
    assert blk["n"] == 24 and blk["n_roots"] == 6
    assert blk["positions_per_root"] == pytest.approx(4.0)
    for name, _k in TB.STAT_KEYS:
        for suf in ("_all", "_discriminable"):
            a = blk[name + suf]
            for sub in ("mean", "se_cluster", "z", "boot_lo", "boot_hi",
                        "sd_positions", "n", "n_roots", "frac_boot_le_0"):
                assert sub in a
    assert blk["arb_H_all"]["mean"] == pytest.approx(
        0.74 * blk["arb_H_discriminable"]["mean"])

    lad = TB.ladder_block(rows, blk["ora_all"]["mean"])
    assert sorted(int(k) for k in lad) == list(TB.B_LADDER)
    for b in TB.B_LADDER:
        d = lad[str(b)]
        assert d["F_fixed"] == pytest.approx(d["arb"] / TB.FIXED_DENOM)
    # the B=16 rung IS the honest arm
    assert lad["16"]["arb"] == pytest.approx(blk["arb_H_all"]["mean"])

    cuts = TB.cut_blocks(rows)
    assert "phase:mid" in cuts and "arms:3" in cuts and "capped_only" in cuts
    for d in cuts.values():
        assert d["F_fixed_point"] == pytest.approx(d["arb"] / TB.FIXED_DENOM)

    comp = TB.composition(rows)
    assert set(comp) == {"pooled", "S1", "S2"}
    assert comp["pooled"]["n"] == 24
    assert comp["S1"]["n"] + comp["S2"]["n"] == 24


def test_load_split_rejects_a_root_in_both_slices(tmp_path):
    p = tmp_path / "SPLIT.json"
    p.write_text(json.dumps({"S1_roots": ["a", "b"], "S2_roots": ["b"]}))
    with pytest.raises(SystemExit, match="BOTH slices"):
        TB.load_split(p)
    p.write_text(json.dumps({"S1_roots": ["a"], "S2_roots": ["b"]}))
    m, _doc = TB.load_split(p)
    assert m == {"a": "S1", "b": "S2"}


# =========================================================================== #
# G. end-to-end smoke -- SYNTHETIC records only, under tmp_path
# =========================================================================== #
def _e2e_corpus(tmp_path, n_pos=24, arb_agrees=True):
    """A complete synthetic run tree: plan dir + both judges' record trees +
    SPLIT.json + PILOT.json. (Adapted from tests/test_tiearb.py::_e2e_corpus.)"""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    if_root = tmp_path / "if" / "clair-puct"
    arb_root = tmp_path / "arb" / "tier1-greedy"

    arms = {}
    rng = random.Random(2026)
    for i in range(n_pos):
        rid = f"tt_sp_{i:04d}_p40"
        root = f"sp_{i:04d}"
        arms[rid] = {"root_id": root, "stratum": "selfplay", "rules_profile": "walled",
                     "phase_bucket": ["early", "mid", "late"][i % 3], "capped": False,
                     "ply": 40, "arms": [100, 101, 102], "champ_arm_index": i % 2}
        if_rows = [[rng.gauss(0.0, 0.5) for _ in range(M)],
                   [rng.gauss(0.3, 0.5) for _ in range(M)],
                   [rng.gauss(1.6, 0.5) for _ in range(M)]]
        if arb_agrees:
            arb_rows = [[v + rng.gauss(0, 0.2) for v in r] for r in if_rows]
        else:
            arb_rows = [[-v + rng.gauss(0, 0.2) for v in r] for r in if_rows]
        for _name, root_dir, mat in (("if", if_root, if_rows),
                                     ("arb", arb_root, arb_rows)):
            for leg in (1, 2):
                d = root_dir / "walled" / f"leg{leg}" / "records"
                d.mkdir(parents=True, exist_ok=True)
                rec = _rec(mat[0], mat[leg], 100, 100 + leg)
                rec["rid"] = rid
                (d / f"{rid}.json").write_text(json.dumps(rec))

    plan = {"schema": "x", "afterstate_dedupe": {
                "applied": True, "n_qualifying_before_drop": n_pos + 2,
                "n_dropped_all_transposition": 2,
                "n_dropped_with_action_played_outside_tieset": 0},
            "cap_j": 4, "m_worlds": M, "max_arms": 5, "mean_arms": 3.0,
            "n_positions": n_pos,
            "counts_by_stratum": {"selfplay": n_pos},
            "files": {}, "out_dir": str(plan_dir)}
    (plan_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan))
    (plan_dir / "ARMS.json").write_text(json.dumps(arms))
    (plan_dir / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps(
        {"rows": [{"stratum": "selfplay", "action_played_outside_tieset": False}] * 2}))

    split = SP.build_split(arms)
    split_p = tmp_path / "SPLIT.json"
    split_p.write_text(json.dumps(split, indent=1, sort_keys=True))
    pilot_p = tmp_path / "PILOT.json"
    pilot_p.write_text(json.dumps({
        "cost": {"c_tier1_worker_s_per_playout": 2.1236},
        "mechanical_rule": {"B_star": 2}, "g_repro": {"ok": 43}, "co_tenant": None}))
    return plan_dir, if_root, arb_root, split_p, pilot_p


def _e2e_argv(plan_dir, if_root, arb_root, split_p, pilot_p, out):
    return ["--if-records", str(if_root), "--arb-records", str(arb_root),
            "--plan-dir", str(plan_dir), "--split", str(split_p),
            "--pilot", str(pilot_p), "--out-dir", str(out)]


HEADINGS = [
    "## 1. The primary statistics",
    "## 2. The single-fold",
    "## 3. `C-RND` per slice",
    "## 4. `C-ARM0` and `SEC-ARB`",
    "## 5. The full B-ladder",
    "## 6. `PICKCHG`, coverage and `AGREE_HC`",
    "## 7. The §5.6 sign check",
    "## 8. The bound chain",
    "## 9. Realized `n`, roots",
    "## 10. Every §3 gate",
    "## 11. Realized `c_tier1`",
    "## 12. Cuts",
    "## 13. Direct comparison to Stage 1",
]


def test_end_to_end_unreadable_when_G_N_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(TB, "BOOT_REPS", 200)
    fx = _e2e_corpus(tmp_path)
    out = tmp_path / "out"
    assert TB.main(_e2e_argv(*fx, out)) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    # the real floors (1040 / 400) cannot be met by a 24-position fixture
    assert v["adjudication"]["branch"] == "U-UNREADABLE"
    assert "G-N" in v["adjudication"]["failed_preconditions"]
    assert (out / "READOUT.md").is_file()
    assert (out / "per_position.jsonl").is_file()


def test_end_to_end_readable_branch_and_all_thirteen_sections_in_order(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(TB, "BOOT_REPS", 400)
    fx = _e2e_corpus(tmp_path, arb_agrees=True)
    out = tmp_path / "out"
    argv = _e2e_argv(*fx, out) + ["--n-floor-pooled", "10", "--n-floor-slice", "4"]
    assert TB.main(argv) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    adj = v["adjudication"]
    assert adj["branch"] in {"A-DEPLOYABLE", "A-COSTLY", "B-ANOMALY",
                             "P-PARTIAL2", "F-FLAT2"}
    assert adj["failed_preconditions"] == []
    assert all(v["preconditions"].values()), v["preconditions"]
    # an agreeing arbiter captures a large positive fraction on both arms
    for x in ("H", "C"):
        assert v["primary"]["pooled"]["arms"][x]["arb"] > 0
    assert v["primary"]["pooled"]["arms"]["H"]["F"] > 0.5
    assert v["completion"]["n_analysed"] == 24
    assert v["completion"]["n_S1"] + v["completion"]["n_S2"] == 24
    assert v["completion"]["n_unsplit"] == 0
    assert v["cost"]["B_star"] == 2
    assert v["cost"]["B_star_matches_cost_rule"] is True
    # scale_all from the analytic zeros is applied (2 dropped of 26 qualifying)
    row = json.loads((out / "per_position.jsonl").read_text().splitlines()[0])
    assert row["scale_all"] == pytest.approx(1.0 - 2.0 / 26.0)
    for b in TB.B_LADDER:                       # the whole ladder is per-position
        assert f"arb_b{b}" in row
    assert row["arb_H"] == row["arb_b16"]
    assert row["arb_C"] == row["arb_b2"]

    md = (out / "READOUT.md").read_text()
    for i, head in enumerate(HEADINGS, start=1):
        assert head in md, (i, head)
    order = [md.index(h) for h in HEADINGS]
    assert order == sorted(order)
    assert "AUDIT-ONLY, CIRCULAR" in md
    assert "NEVER A BRANCH INPUT" in md
    assert "NEVER adjudicated on" in md
    assert "AGREE_HC" in md
    assert "CROSS-CORPUS" in md
    # the salt is READ, not asserted: DESIGN §0.A withdrew `tiearb2-v1`, so the
    # header must quote what the RECORDS carry, not a hardcoded design string.
    assert "realized salt `tiletie-v1`" in md
    assert "salt `tiearb2-v1`" not in md
    assert v["completion"]["world_seed_salt_realized"] == ["tiletie-v1"]
    assert v["completion"]["world_seed_salt_agrees_across_judges"] is True


def test_end_to_end_honest_arm_reproduces_stage1_estimator_on_the_same_records(
        tmp_path, monkeypatch, capsys):
    """The strongest form of the B=16 identity: the WHOLE pipeline, arm H, against
    `analyze_tiearb`'s own per-position `arb` on byte-identical records."""
    monkeypatch.setattr(TB, "BOOT_REPS", 200)
    monkeypatch.setattr(TA1, "BOOT_REPS", 200)
    plan_dir, if_root, arb_root, split_p, pilot_p = _e2e_corpus(tmp_path)
    hr = tmp_path / "HOLDOUT_ROOTS.json"
    hr.write_text(json.dumps({"holdout_roots": []}))
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    TB.main(_e2e_argv(plan_dir, if_root, arb_root, split_p, pilot_p, out1)
            + ["--n-floor-pooled", "10", "--n-floor-slice", "4"])
    TA1.main(["--if-records", str(if_root), "--arb-records", str(arb_root),
              "--plan-dir", str(plan_dir),
              "--full-supply-plan", str(plan_dir / "POSITIONS_PLAN.json"),
              "--holdout-roots", str(hr), "--out-dir", str(out2)])
    capsys.readouterr()
    new = {json.loads(l)["rid"]: json.loads(l)
           for l in (out1 / "per_position.jsonl").read_text().splitlines()}
    old = {json.loads(l)["rid"]: json.loads(l)
           for l in (out2 / "per_position.jsonl").read_text().splitlines()}
    assert set(new) == set(old) and len(new) == 24
    for rid in new:
        assert new[rid]["arb_H"] == old[rid]["arb"]     # bit-identical
        assert new[rid]["arb_b16"] == old[rid]["arb"]
        assert new[rid]["ora"] == old[rid]["ora"]
        assert new[rid]["rnd"] == old[rid]["rnd"]
        assert new[rid]["sec_H"] == old[rid]["sec"]


def test_end_to_end_disagreeing_arbiter_does_not_capture(tmp_path, monkeypatch,
                                                         capsys):
    monkeypatch.setattr(TB, "BOOT_REPS", 400)
    fx = _e2e_corpus(tmp_path, arb_agrees=False)
    out = tmp_path / "out"
    assert TB.main(_e2e_argv(*fx, out)
                   + ["--n-floor-pooled", "10", "--n-floor-slice", "4"]) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    P = v["primary"]["pooled"]
    assert P["arms"]["H"]["arb"] < P["ora"]
    assert P["arms"]["H"]["F"] < 0.35
    assert v["adjudication"]["branch"] in {"F-FLAT2", "P-PARTIAL2", "B-ANOMALY"}


def test_end_to_end_g_split_fails_when_a_root_is_missing_from_the_split(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(TB, "BOOT_REPS", 200)
    plan_dir, if_root, arb_root, split_p, pilot_p = _e2e_corpus(tmp_path)
    doc = json.loads(split_p.read_text())
    doc["S1_roots"] = doc["S1_roots"][1:]              # drop one root
    split_p.write_text(json.dumps(doc))
    out = tmp_path / "out"
    assert TB.main(_e2e_argv(plan_dir, if_root, arb_root, split_p, pilot_p, out)
                   + ["--n-floor-pooled", "10", "--n-floor-slice", "4"]) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    assert v["preconditions"]["G-SPLIT"] is False
    assert v["adjudication"]["branch"] == "U-UNREADABLE"
    assert "G-SPLIT" in v["adjudication"]["failed_preconditions"]


def test_b_star_override_is_recorded_as_a_deviation(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(TB, "BOOT_REPS", 200)
    fx = _e2e_corpus(tmp_path)
    out = tmp_path / "out"
    assert TB.main(_e2e_argv(*fx, out) + ["--b-star", "8",
                                          "--n-floor-pooled", "10",
                                          "--n-floor-slice", "4"]) == 0
    capsys.readouterr()
    v = json.loads((out / "READOUT.json").read_text())
    assert v["cost"]["B_star"] == 8
    assert "DEVIATION" in v["cost"]["B_star_source"]
    assert v["cost"]["B_star_matches_cost_rule"] is False
    assert v["adjudication"]["DEPLOY"] is False        # rho_wall(8) >> 1.20
    row = json.loads((out / "per_position.jsonl").read_text().splitlines()[0])
    assert row["arb_C"] == row["arb_b8"]


def test_sign_check_is_reused_unmodified_from_stage1():
    rows = [{"arb": 1.0, "scale_all": 1.0, "pickchg": True}] * 8
    a = TA1.sign_check(rows, aggregate_mean=1.0)
    assert a["corroboration"] == "CORROBORATES"
    assert TB.BENCH is TA1.BENCH
    assert math.isnan(TA1.binom_two_sided(0, 0))
