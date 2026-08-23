"""Contracts for the every-ply probe's two OWED BUILDS —
`scripts/tiletie/build_everyply_corpus.py` and `scripts/tiletie/analyze_everyply.py`.

Sibling of `tests/test_everyply_plan.py` (which owns the sampling frame and is NOT
edited by this file). Unit tests only: no engine, no champion, no judge, no real
`probe_pickers` subprocess, no oracle value. Every expected figure is copied from
`measurement/everyply_probe_20260823/{DESIGN.md,READ_RULE.md}`, so the analyser is
checked against the pre-registration rather than against itself.

Covers:
  * the READ_RULE §3 GATE TRUTH TABLE — every one of the eleven gates PASSING, and
    EACH ONE's own fail mode, including `G-KNOWNGOOD` refusing on a failed
    `probe_pickers.py knowngood` (rc != 0 / ok:false / absent — ABSENT IS FAIL)
  * the §1 from-scratch WITNESS, and that a disagreement is U-UNREADABLE
  * the §4 BRANCH SWEEP in order, first-match-wins, INCLUDING the §0.A structural
    block of `E-CLEAN`/`E-FUND` and the mandatory n-to-resolve print
  * the holdout being untouched by any code path until its own gate
  * REUSE-BY-IMPORT: the estimators are `analyze_tiletie`'s objects, not clones,
    and the corpus builder's seams are `build_positions`'s objects
  * ZERO-FILL UNBIASEDNESS on a constructed case (§5.2 property 1 / `G-ZEROFILL`)
  * the two-estimator rule: the DESIGN §2.3 stratification penalty prices the
    POOL only, never a within-stratum read
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "scripts" / "tiletie", REPO / "scripts" / "measurement_infra"):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import analyze_everyply as A          # noqa: E402
import analyze_tiletie as AT          # noqa: E402
import build_everyply_corpus as EC    # noqa: E402
import build_everyply_plan as EP      # noqa: E402
import build_positions as BP          # noqa: E402

LEAF = A.LEAF_HASH_OF_RECORD
TIEARB = json.dumps({"B": 64, "J": 4, "enabled": True, "eps": 0.0, "mode": "argmax",
                     "salt": "tiearb2-deploy-v1"}, sort_keys=True)
W_CENSUS = {"A": 0.09969578444154715, "B": 0.4290308561495002, "C": 0.4712733594089526}


# --------------------------------------------------------------------------- #
# fixtures — a synthetic corpus with FULL control of a_arb and kappa            #
# --------------------------------------------------------------------------- #
def _row(rid, kappa=0.0, stratum="B", root=None, slice_="dev", **kw):
    r = {"rid": rid, "root_id": root or rid, "gap_stratum": stratum, "slice": slice_,
         "chunk": 1, "kappa": float(kappa), "kappa_fold1": float(kappa),
         "kappa_fold2": float(kappa), "pickchg": kappa != 0.0,
         "pickchg_fold1": kappa != 0.0, "pickchg_fold2": kappa != 0.0,
         "priced": kappa != 0.0, "zero_filled": kappa == 0.0,
         "arm_builder": "leaf_topk", "champ_leaf_hash": LEAF, "champ_tiearb": TIEARB,
         "champ_k_dets": 8, "champ_sims_per_det": 1376, "rules_profile": "walled",
         "scale_all": 1.0, "m": 32, "n_arms": 4, "n_arms_priced": 2,
         "champ_action": 1, "arm_order_actions": [1, 2, 3, 4],
         "a_arb_folds": [2, 2], "a_arb_positions": [1, 1], "ply": 10,
         "phase_bucket": "mid", "gap": 1.0}
    r.update(kw)
    return r


def _rec(rid, m, va, vb, pick_a, pick_b, **kw):
    rec = {"rid": rid, "m": m, "values_a": list(va), "values_b": list(vb),
           "world_seeds": [1000 + i for i in range(m)],
           "playout_seeds": [2000 + i for i in range(m)],
           "crn_verified": True, "checksum_ok": True, "ok": True,
           "pick_a": pick_a, "pick_b": pick_b, "rules_profile": "walled"}
    rec.update(kw)
    return rec


def _write_rec(root, judge, leg, rec):
    d = Path(root) / judge / "walled" / f"leg{leg}" / "records"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rec['rid']}.json").write_text(json.dumps(rec))


def _arms_entry(rid, arms, stratum="B", slice_="dev", **kw):
    e = {"arms": [int(a) for a in arms], "root_id": rid, "stratum": "selfplay",
         "source": "champ_games", "rules_profile": "walled", "game_label": rid,
         "deck_seed": 28000000000, "ply": 10, "seat": 0, "k_remaining": 40,
         "phase_bucket": "mid", "tercile": 0, "n_legal": 10, "n_cand": 10,
         "tie_size_exact": None, "gap": 1.0, "capped": False, "dropped_actions": [],
         "dedupe_dropped_actions": [], "n_distinct_afterstates": 10,
         "arms_full": list(arms), "subset_j4": list(arms), "subset_j4_id": "deadbeef",
         "capped_at_4": False, "cap_seed": 1, "champ_action": int(arms[0]),
         "champ_arm_index": 0, "champ_arm_action": int(arms[0]),
         "champ_outside_tieset": False, "champ_pick_missing": False,
         "archive_path": None, "gap_stratum": stratum, "slice": slice_, "chunk": 1,
         "champ_pos": 0, "arm_builder": "leaf_topk", "pooled_rank_of_champ": None,
         "champ_k_dets": 8, "champ_sims_per_det": 1376, "champ_backend": "rust",
         "champ_leaf_hash": LEAF, "champ_tiearb": TIEARB,
         "rules_profile_stamp": "walled", "band": EC.BAND, "corpus": EC.CORPUS}
    e.update(kw)
    return e


def _write_plan_dir(d, arms_index, *, n_planned, n_dropped=0, mode="arms"):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    (d / "ARMS.json").write_text(json.dumps(arms_index))
    (d / "POSITIONS_PLAN.json").write_text(json.dumps({
        "schema": EC.SCHEMA, "mode": mode, "rules_profile": "walled", "files": {},
        "afterstate_dedupe": {"applied": True, "n_qualifying_before_drop": n_planned,
                              "n_dropped_all_transposition": n_dropped,
                              "n_dropped_with_action_played_outside_tieset": 0},
        "everyply": {"n_planned": n_planned, "n_built": len(arms_index),
                     "n_dropped_lt2_distinct": n_dropped,
                     "dropped_lt2_distinct_rate": n_dropped / n_planned,
                     "n_error": 0, "arm_builder": "leaf_topk"},
    }))
    (d / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps({"rows": []}))
    return d


def _write_pair(d):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    (d / "FRAME.json").write_text(json.dumps({"population": {
        "strata": {s: {"share_of_nontied": W_CENSUS[s]} for s in EP.STRATA}}}))
    (d / "PLAN_SUMMARY.json").write_text(json.dumps({
        "max_abs_f_deviation_pp": 0.111, "population_weights_w": dict(W_CENSUS)}))
    return d


@pytest.fixture()
def corpus(tmp_path):
    """One 3-position synthetic corpus: 1 priced-and-changed, 1 priced-but-champ,
    1 zero-filled. `m = 4` so the parity folds are readable by eye."""
    pair = _write_pair(tmp_path / "pair")
    m = 4
    arb_root, if_root = tmp_path / "arb", tmp_path / "if"
    arms_idx, if_idx = {}, {}

    # p1: arm 2 (leg 1) wins the SELECTION worlds in both folds -> a_arb = 200.
    #     IF prices {100, 200}; the eva-means give kappa = +1.0.
    arms_idx["ep_1_10"] = _arms_entry("ep_1_10", [100, 200, 300], stratum="A")
    _write_rec(arb_root, "tier1-greedy", 1,
               _rec("ep_1_10", m, [0, 0, 0, 0], [5, 5, 5, 5], 100, 200))
    _write_rec(arb_root, "tier1-greedy", 2,
               _rec("ep_1_10", m, [0, 0, 0, 0], [-5, -5, -5, -5], 100, 300))
    if_idx["ep_1_10"] = _arms_entry("ep_1_10", [100, 200], stratum="A",
                                    arms_to_price=[100, 200], zero_filled=False)
    _write_rec(if_root, "clair-puct", 1,
               _rec("ep_1_10", m, [0, 0, 0, 0], [1, 1, 1, 1], 100, 200))

    # p2: the champion arm wins the SELECTION worlds in both folds, but the IF
    #     plan priced two arms anyway -> a_arb == champ -> kappa == 0 by pricing.
    arms_idx["ep_2_10"] = _arms_entry("ep_2_10", [100, 200, 300], stratum="B")
    _write_rec(arb_root, "tier1-greedy", 1,
               _rec("ep_2_10", m, [9, 9, 9, 9], [0, 0, 0, 0], 100, 200))
    _write_rec(arb_root, "tier1-greedy", 2,
               _rec("ep_2_10", m, [9, 9, 9, 9], [0, 0, 0, 0], 100, 300))
    if_idx["ep_2_10"] = _arms_entry("ep_2_10", [100, 200], stratum="B",
                                    arms_to_price=[100, 200], zero_filled=False)
    _write_rec(if_root, "clair-puct", 1,
               _rec("ep_2_10", m, [3, 3, 3, 3], [7, 7, 7, 7], 100, 200))

    # p3: singleton arms_to_price -> ZERO-FILLED, no IF record at all.
    arms_idx["ep_3_10"] = _arms_entry("ep_3_10", [100, 200, 300], stratum="C",
                                      slice_="holdout")
    _write_rec(arb_root, "tier1-greedy", 1,
               _rec("ep_3_10", m, [9, 9, 9, 9], [0, 0, 0, 0], 100, 200))
    _write_rec(arb_root, "tier1-greedy", 2,
               _rec("ep_3_10", m, [9, 9, 9, 9], [0, 0, 0, 0], 100, 300))
    if_idx["ep_3_10"] = _arms_entry("ep_3_10", [100], stratum="C", slice_="holdout",
                                    arms_to_price=[100], zero_filled=True)

    _write_plan_dir(pair / "positions_chunk1", arms_idx, n_planned=4, n_dropped=0)
    _write_plan_dir(pair / "positions_if_chunk1", if_idx, n_planned=4, n_dropped=0,
                    mode="selective")
    return {"pair": pair, "arb": arb_root, "if": if_root,
            "arms": arms_idx, "if_arms": if_idx}


def _build(corpus, tmp_path, monkeypatch, *, blind_ok=True, knowngood_ok=True,
           extra_argv=()):
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)

    def _fake_kg(out_dir, python_exe=None, timeout=7200):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / "KNOWNGOOD.json").write_text(json.dumps(
            {"ok": bool(knowngood_ok), "reproduced": {"arb": 0.2065}, "delta": {}}))
        return {"rc": 0 if knowngood_ok else 1, "cmd": [], "stdout_tail": "",
                "stderr_tail": ""}

    monkeypatch.setattr(A, "invoke_knowngood", _fake_kg)
    if blind_ok:
        monkeypatch.setattr(A, "gate_blind", lambda *a, **k: A._gate(
            "G-BLIND", True, "stubbed in tests", {}, "stub"))
    argv = ["--arb-records", str(corpus["arb"]), "--if-records", str(corpus["if"]),
            "--plan-dir", str(corpus["pair"]), "--out-dir", str(out),
            "--n-priced-planned", "3", *extra_argv]
    return A.build_readout(A.parse_args(argv))


# --------------------------------------------------------------------------- #
# 1. REUSE BY IMPORT — the estimators are analyze_tiletie's OBJECTS, not clones #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", [
    "parity_indices", "crossfit_regret", "cluster_robust", "bootstrap_roots",
    "aggregate", "load_plan", "discover_records", "pts_to_elo", "_sub_mean"])
def test_analyser_uses_analyze_tiletie_objects_not_clones(name):
    assert getattr(A.AT, name) is getattr(AT, name)


@pytest.mark.parametrize("name", [
    "dedupe_tie_actions", "_seeded_cap", "build_arms_index", "write_leg_files",
    "cost_plan", "load_champ_games", "_stable_seed", "_subset_id"])
def test_corpus_builder_uses_build_positions_objects_not_clones(name):
    assert getattr(EC.BP, name) is getattr(BP, name)


@pytest.mark.parametrize("name", ["parity_indices", "crossfit_regret"])
def test_corpus_selective_uses_analyze_tiletie_objects(name):
    assert getattr(EC.AT, name) is getattr(AT, name)


@pytest.mark.parametrize("sym", [
    "def parity_indices", "def crossfit_regret", "def cluster_robust",
    "def bootstrap_roots", "def aggregate", "def discover_records", "def load_plan"])
def test_analyser_defines_no_local_estimator_clone(sym):
    """DESIGN §6.2: imported UNMODIFIED, never re-implemented."""
    src = (REPO / "scripts/tiletie/analyze_everyply.py").read_text()
    assert sym not in src


def test_neither_new_file_edits_an_existing_module():
    """DESIGN §6.3: NEW FILES ONLY — no monkeypatching of the shared seams at
    import time, and no writes into build_positions / analyze_tiletie."""
    for p in ("analyze_everyply.py", "build_everyply_corpus.py"):
        src = (REPO / "scripts/tiletie" / p).read_text()
        assert "AT." in src or "BP." in src
        assert "AT.crossfit_regret =" not in src
        assert "BP.dedupe_tie_actions =" not in src


# --------------------------------------------------------------------------- #
# 2. the two estimators — the penalty prices the POOL only (DESIGN §2.3)        #
# --------------------------------------------------------------------------- #
def test_pooled_estimator_is_the_population_reweighted_mean():
    rows = ([_row(f"a{i}", 1.0, "A", root=f"r{i}") for i in range(4)]
            + [_row(f"b{i}", 2.0, "B", root=f"s{i}") for i in range(4)]
            + [_row(f"c{i}", 3.0, "C", root=f"t{i}") for i in range(4)])
    got = A.kappa_pooled(rows, W_CENSUS, 11)
    want = W_CENSUS["A"] * 1.0 + W_CENSUS["B"] * 2.0 + W_CENSUS["C"] * 3.0
    assert got["mean"] == pytest.approx(want, abs=1e-12)
    # equal-n sampling is NOT proportional, so the pooled read differs from the
    # naive unweighted mean -- that difference IS the reweighting.
    assert got["mean"] != pytest.approx(2.0, abs=1e-6)


def test_within_stratum_estimator_reweights_nothing():
    rows = ([_row(f"a{i}", 1.0, "A", root=f"r{i}") for i in range(3)]
            + [_row(f"b{i}", 7.0, "B", root=f"s{i}") for i in range(5)])
    A.kappa_pooled(rows, W_CENSUS, 11)          # stamps w_scale on every row
    assert A.kappa_stratum(rows, "A", 11)["mean"] == pytest.approx(1.0, abs=1e-12)
    assert A.kappa_stratum(rows, "B", 11)["mean"] == pytest.approx(7.0, abs=1e-12)


def test_stratification_penalty_is_a_planning_figure_on_the_pool_only():
    """DESIGN §2.3 / §7.1 SHARPENED: EP.se_kappa carries 1.06; the within-stratum
    helper must not, and the analyser must call the RIGHT one in each place."""
    assert EP.se_kappa(400, 0.76) / EP.se_kappa_stratum(400, 0.76) == pytest.approx(
        EP.STRATIFICATION_SE_PENALTY, abs=1e-12)
    src = (REPO / "scripts/tiletie/analyze_everyply.py").read_text()
    assert "EP.se_kappa_stratum(" in src          # per-stratum print
    assert "EP.se_kappa(" in src                  # pooled planning print


def test_realized_pooled_se_is_not_multiplied_by_the_penalty_again():
    """The penalty is REALIZED in `w_scale`; multiplying by 1.06 on top would
    double-count it. Checked BEHAVIOURALLY: the pooled se must equal a from-scratch
    cluster sandwich on the weighted values, which contains no penalty factor."""
    rows = ([_row(f"a{i}", 0.4 + 0.05 * i, "A", root=f"r{i}") for i in range(5)]
            + [_row(f"b{i}", -0.3 + 0.02 * i, "B", root=f"s{i}") for i in range(9)]
            + [_row(f"c{i}", 0.11 * i, "C", root=f"t{i}") for i in range(6)])
    pooled = A.kappa_pooled(rows, W_CENSUS, 11)
    hand = A.recompute_witness(rows, W_CENSUS)          # no 1.06 anywhere in it
    assert pooled["se_cluster"] == pytest.approx(hand["se"], abs=1e-15)
    assert pooled["se_cluster"] != pytest.approx(
        hand["se"] * EP.STRATIFICATION_SE_PENALTY, abs=1e-9)


# --------------------------------------------------------------------------- #
# 3. ZERO-FILL UNBIASEDNESS — a constructed case (DESIGN §5.2 property 1)       #
# --------------------------------------------------------------------------- #
def test_zero_fill_is_exactly_unbiased_and_dropping_zeros_inflates():
    """kappa[p] == 0 IDENTICALLY when both folds' a_arb are the champion, so the
    un-priced positions must enter the mean AS EXACT ZEROS and enter n."""
    priced = [_row(f"p{i}", 0.6, "B", root=f"r{i}") for i in range(4)]
    zeros = [_row(f"z{i}", 0.0, "B", root=f"s{i}") for i in range(6)]
    rows = priced + zeros
    full = A.kappa_stratum(rows, "B", 11)["mean"]
    assert full == pytest.approx(0.6 * 4 / 10, abs=1e-12)     # = 0.24, the TRUE mean
    dropped = A.kappa_stratum(priced, "B", 11)["mean"]
    assert dropped == pytest.approx(0.6, abs=1e-12)
    assert dropped / full == pytest.approx(10 / 4, abs=1e-12)  # exactly n/n_priced
    assert all(r["zero_filled"] for r in zeros)


def test_zero_filled_positions_enter_n_and_the_cluster_structure():
    priced = [_row(f"p{i}", 0.6, "B", root=f"r{i}") for i in range(4)]
    zeros = [_row(f"z{i}", 0.0, "B", root=f"s{i}") for i in range(6)]
    agg = A.kappa_stratum(priced + zeros, "B", 11)
    assert agg["n"] == 10
    assert agg["n_roots"] == 10


def test_zero_fill_identity_holds_end_to_end(corpus, tmp_path, monkeypatch):
    v, rows = _build(corpus, tmp_path, monkeypatch)
    p = v["primary"]
    assert p["n_priced"] + p["n_zero"] == p["n_analysed"] == 3
    assert p["n_zero"] == 1
    kz = [r for r in rows if r["zero_filled"]]
    assert len(kz) == 1 and kz[0]["kappa"] == 0.0


# --------------------------------------------------------------------------- #
# 4. per-position kappa — the cross-fit, on records we control                  #
# --------------------------------------------------------------------------- #
def test_kappa_per_position_is_the_crossfit_capture(corpus, tmp_path, monkeypatch):
    _v, rows = _build(corpus, tmp_path, monkeypatch)
    by_rid = {r["rid"]: r for r in rows}
    # p1: a_arb = 200 in both folds; IF eva-mean(200) - eva-mean(100) = 1 - 0 = 1.
    assert by_rid["ep_1_10"]["a_arb_folds"] == [200, 200]
    assert by_rid["ep_1_10"]["kappa"] == pytest.approx(1.0, abs=1e-12)
    assert by_rid["ep_1_10"]["pickchg"] is True
    # p2: a_arb IS the champion; kappa priced to exactly 0 even though IF ran.
    assert by_rid["ep_2_10"]["a_arb_folds"] == [100, 100]
    assert by_rid["ep_2_10"]["kappa"] == pytest.approx(0.0, abs=1e-12)
    assert by_rid["ep_2_10"]["pickchg"] is False


def test_a_arb_is_crossfit_regret_a_plus_verbatim():
    """The analyser's a_arb and the corpus builder's selective a_arb are the SAME
    imported call, so the argmax tie-break cannot drift between them."""
    matrix = [[0, 0, 0, 0], [5, 5, 5, 5], [-5, -5, -5, -5]]
    keep, picks = EC.selective_arms(matrix, 0, 4, 1)
    sel, eva = AT.parity_indices(4, base=1)
    _h, a_plus = AT.crossfit_regret(matrix, sel, eva, 0)
    assert picks[0] == int(a_plus)
    assert keep == [0, 1]                       # {champ} U {a_arb fold1, fold2}


def test_selective_arms_singleton_when_the_arbiter_agrees_with_the_champion():
    matrix = [[9, 9, 9, 9], [0, 0, 0, 0], [0, 0, 0, 0]]
    keep, picks = EC.selective_arms(matrix, 0, 4, 1)
    assert keep == [0] and picks == [0, 0]


# --------------------------------------------------------------------------- #
# 5. GATE TRUTH TABLE — every gate PASSES, and every gate's own FAIL mode       #
# --------------------------------------------------------------------------- #
def test_all_eleven_gates_pass_on_a_healthy_run(corpus, tmp_path, monkeypatch):
    v, _rows = _build(corpus, tmp_path, monkeypatch)
    ids = [g["id"] for g in v["gates"]]
    assert ids == list(A.GATE_IDS)               # READ_RULE §3 table ORDER
    failed = [g["id"] for g in v["gates"] if not g["ok"]]
    assert failed == [], failed
    assert v["witness_gate"]["ok"] is True
    assert all(g["address"] for g in v["gates"])  # every gate names its address


def test_gate_knowngood_runs_the_subcommand_first_and_refuses_on_failure(tmp_path,
                                                                        monkeypatch):
    calls = []

    def _fake(out_dir, python_exe=None, timeout=7200):
        calls.append(str(out_dir))
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / "KNOWNGOOD.json").write_text(json.dumps({"ok": True}))
        return {"rc": 0, "cmd": [], "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(A, "invoke_knowngood", _fake)
    g = A.gate_knowngood(tmp_path)
    assert calls == [str(tmp_path)]              # it RAN, it did not just read
    assert g["ok"] is True and g["id"] == "G-KNOWNGOOD"
    assert "probe_pickers.py knowngood" in g["address"]


@pytest.mark.parametrize("rc,payload", [
    (1, {"ok": True}),        # the subcommand itself failed
    (0, {"ok": False}),       # it ran and did NOT reproduce arb=+0.2065
    (0, None),                # ABSENT IS FAIL
])
def test_gate_knowngood_fail_modes(tmp_path, monkeypatch, rc, payload):
    def _fake(out_dir, python_exe=None, timeout=7200):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        if payload is not None:
            (Path(out_dir) / "KNOWNGOOD.json").write_text(json.dumps(payload))
        return {"rc": rc, "cmd": [], "stdout_tail": "", "stderr_tail": "x"}

    monkeypatch.setattr(A, "invoke_knowngood", _fake)
    assert A.gate_knowngood(tmp_path)["ok"] is False


def test_gate_knowngood_uses_the_knowngood_subcommand_only():
    """DESIGN §6.2: grade/preflight/sweep call require_knowngood against constants
    hard-pinned to the OLD 733/399 corpus and would be FAIL-ALWAYS here."""
    src = (REPO / "scripts/tiletie/analyze_everyply.py").read_text()
    assert '"knowngood"' in src
    for bad in ('"grade"', '"preflight"', '"sweep"'):
        assert bad not in src


def test_gate_crn_fails_on_an_unverified_record(corpus, tmp_path, monkeypatch):
    _write_rec(corpus["arb"], "tier1-greedy", 1,
               _rec("ep_1_10", 4, [0, 0, 0, 0], [5, 5, 5, 5], 100, 200,
                    crn_verified=False))
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}
    assert g["G-CRN"]["ok"] is False
    assert v["branch"] == "U-UNREADABLE"


def test_gate_crn_fails_on_a_cross_judge_seed_divergence(corpus, tmp_path, monkeypatch):
    bad = _rec("ep_1_10", 4, [0, 0, 0, 0], [1, 1, 1, 1], 100, 200)
    bad["world_seeds"] = [7, 7, 7, 7]
    _write_rec(corpus["if"], "clair-puct", 1, bad)
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert {x["id"]: x for x in v["gates"]}["G-CRN"]["ok"] is False


def test_gate_cover_fails_when_the_champion_is_not_arm_zero(corpus, tmp_path,
                                                            monkeypatch):
    idx = dict(corpus["arms"])
    idx["ep_1_10"] = dict(idx["ep_1_10"], champ_action=200)
    _write_plan_dir(corpus["pair"] / "positions_chunk1", idx, n_planned=4)
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}["G-COVER"]
    assert g["ok"] is False and g["realized"]["champ_not_arm0"] == 1
    assert "INSTRUMENT DEFECT" in g["detail"]


def test_gate_armset_fails_when_the_if_plan_prices_a_foreign_arm(corpus, tmp_path,
                                                                 monkeypatch):
    idx = dict(corpus["if_arms"])
    idx["ep_1_10"] = _arms_entry("ep_1_10", [100, 999], stratum="A")
    _write_plan_dir(corpus["pair"] / "positions_if_chunk1", idx, n_planned=4,
                    mode="selective")
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}["G-ARMSET"]
    assert g["ok"] is False and g["realized"]["not_a_subset"] == 1


def test_gate_armset_fails_on_an_order_disagreement(corpus, tmp_path, monkeypatch):
    idx = dict(corpus["if_arms"])
    idx["ep_1_10"] = _arms_entry("ep_1_10", [200, 100], stratum="A")
    _write_plan_dir(corpus["pair"] / "positions_if_chunk1", idx, n_planned=4,
                    mode="selective")
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert {x["id"]: x for x in v["gates"]}["G-ARMSET"]["ok"] is False


def test_gate_armset_documents_the_subset_reading(corpus, tmp_path, monkeypatch):
    """READ_RULE §3 words G-ARMSET as 'the two arm_order lists equal'; under the
    §5.2 selective economy that literal reading is FAIL-ALWAYS, which §3.1
    forbids. The applied reading must be PRINTED, not silently substituted."""
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}["G-ARMSET"]
    detail = g["detail"].lower()
    assert "fail-always" in detail and "subsequence" in detail


def test_gate_zerofill_fails_when_a_zero_fill_was_not_actually_a_zero(corpus, tmp_path,
                                                                     monkeypatch):
    """A position the IF plan zero-filled whose ARB records say a_arb != champ."""
    _write_rec(corpus["arb"], "tier1-greedy", 1,
               _rec("ep_3_10", 4, [0, 0, 0, 0], [9, 9, 9, 9], 100, 200))
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}["G-ZEROFILL"]
    assert g["ok"] is False and g["realized"]["zerofill_defect"] == 1


def test_gate_distinct_fails_above_ten_percent(corpus, tmp_path, monkeypatch):
    _write_plan_dir(corpus["pair"] / "positions_chunk1", corpus["arms"],
                    n_planned=100, n_dropped=11)
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}["G-DISTINCT"]
    assert g["ok"] is False and g["realized"]["rate"] == pytest.approx(0.11)


def test_gate_distinct_passes_at_the_bar(corpus, tmp_path, monkeypatch):
    _write_plan_dir(corpus["pair"] / "positions_chunk1", corpus["arms"],
                    n_planned=100, n_dropped=10)
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert {x["id"]: x for x in v["gates"]}["G-DISTINCT"]["ok"] is True


@pytest.mark.parametrize("summary", [
    {"max_abs_f_deviation_pp": 3.5, "population_weights_w": dict(W_CENSUS)},
    {"max_abs_f_deviation_pp": 0.111,
     "population_weights_w": {"A": 0.2, "B": 0.4, "C": 0.4}},
    {"population_weights_w": dict(W_CENSUS)},          # ABSENT IS FAIL
])
def test_gate_frame_fail_modes(corpus, tmp_path, monkeypatch, summary):
    (corpus["pair"] / "PLAN_SUMMARY.json").write_text(json.dumps(summary))
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert {x["id"]: x for x in v["gates"]}["G-FRAME"]["ok"] is False


def _write_selection(pair, arms_index, *, holdout=(), stratum_override=None):
    rows = []
    for rid, meta in arms_index.items():
        rows.append({"rid": rid, "game_id": meta["root_id"],
                     "deck_seed": meta["deck_seed"], "ply": meta["ply"],
                     "seat": 0, "k_remaining": 40, "n_legal": 10, "gap": 1.0,
                     "top1": 2.0, "top2": 1.0, "phase_bucket": "mid",
                     "stratum": (stratum_override or {}).get(rid, meta["gap_stratum"]),
                     "slice": "holdout" if meta["root_id"] in holdout else "dev",
                     "chunk": 1})
    (pair / "SELECTION.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in rows))
    (pair / "HOLDOUT_GAMES.json").write_text(json.dumps({"holdout": list(holdout)}))
    return ["--selection", str(pair / "SELECTION.jsonl"),
            "--holdout-games", str(pair / "HOLDOUT_GAMES.json")]


def test_gate_frame_also_checks_the_committed_selection_and_root_split(
        corpus, tmp_path, monkeypatch):
    extra = _write_selection(corpus["pair"], corpus["arms"], holdout=["ep_3_10"])
    v, _ = _build(corpus, tmp_path, monkeypatch, extra_argv=extra)
    g = {x["id"]: x for x in v["gates"]}["G-FRAME"]
    assert g["ok"] is True
    assert g["realized"]["rids_off_the_committed_selection"] == 0
    assert g["realized"]["slice_disagreements_vs_HOLDOUT_GAMES"] == 0


def test_gate_frame_fails_on_a_stratum_stamp_that_left_the_committed_draw(
        corpus, tmp_path, monkeypatch):
    extra = _write_selection(corpus["pair"], corpus["arms"], holdout=["ep_3_10"],
                             stratum_override={"ep_1_10": "C"})
    v, _ = _build(corpus, tmp_path, monkeypatch, extra_argv=extra)
    g = {x["id"]: x for x in v["gates"]}["G-FRAME"]
    assert g["ok"] is False and g["realized"]["stratum_stamp_disagreements"] == 1


def test_gate_frame_fails_when_a_row_straddles_the_dev_holdout_boundary(
        corpus, tmp_path, monkeypatch):
    extra = _write_selection(corpus["pair"], corpus["arms"], holdout=["ep_1_10"])
    v, _ = _build(corpus, tmp_path, monkeypatch, extra_argv=extra)
    g = {x["id"]: x for x in v["gates"]}["G-FRAME"]
    assert g["ok"] is False
    assert g["realized"]["slice_disagreements_vs_HOLDOUT_GAMES"] >= 1


def test_gate_n_is_eighty_five_percent_of_the_planned_read_point():
    assert A.gate_n(340, 400)["ok"] is True
    assert A.gate_n(339, 400)["ok"] is False
    assert A.gate_n(340, 400)["realized"]["floor"] == 340


def test_gate_epoch_names_the_dialect_and_fails_on_the_wrong_hash(corpus, tmp_path,
                                                                  monkeypatch):
    idx = {k: dict(v, champ_leaf_hash="6dfffd57051690f2")
           for k, v in corpus["arms"].items()}
    _write_plan_dir(corpus["pair"] / "positions_chunk1", idx, n_planned=4)
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}["G-EPOCH"]
    assert g["ok"] is False
    assert "harness_leaf_hash" in g["address"] and "6dfffd57051690f2" in g["detail"]


def test_gate_epoch_fails_on_a_non_walled_leg(corpus, tmp_path, monkeypatch):
    _write_rec(corpus["if"], "clair-puct", 1,
               _rec("ep_1_10", 4, [0, 0, 0, 0], [1, 1, 1, 1], 100, 200,
                    rules_profile="fixed_v1"))
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert {x["id"]: x for x in v["gates"]}["G-EPOCH"]["ok"] is False


def test_gate_champ_fails_on_a_mid_run_champion_change(corpus, tmp_path, monkeypatch):
    idx = dict(corpus["arms"])
    idx["ep_2_10"] = dict(idx["ep_2_10"], champ_sims_per_det=688, champ_k_dets=4)
    _write_plan_dir(corpus["pair"] / "positions_chunk1", idx, n_planned=4)
    v, _ = _build(corpus, tmp_path, monkeypatch)
    g = {x["id"]: x for x in v["gates"]}["G-CHAMP"]
    assert g["ok"] is False
    assert sorted(g["realized"]["sims_per_det"]) == [688, 1376]


def test_gate_champ_fails_on_a_changed_tiearb_block(corpus, tmp_path, monkeypatch):
    idx = dict(corpus["arms"])
    idx["ep_2_10"] = dict(idx["ep_2_10"], champ_tiearb='{"B": 16}')
    _write_plan_dir(corpus["pair"] / "positions_chunk1", idx, n_planned=4)
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert {x["id"]: x for x in v["gates"]}["G-CHAMP"]["ok"] is False


@pytest.mark.parametrize("sha", ["", "not-a-sha", "0" * 39, "z" * 40])
def test_gate_blind_refuses_a_missing_or_placeholder_commit(tmp_path, sha):
    d = tmp_path / "pair"
    d.mkdir()
    (d / "BLIND_COMMIT").write_text(sha)
    g = A.gate_blind(d / "BLIND_COMMIT", d, [tmp_path / "none"])
    assert g["ok"] is False
    assert any("BLIND_COMMIT" in p for p in g["realized"]["problems"])


def test_gate_blind_is_fail_closed_when_the_file_is_absent(tmp_path):
    d = tmp_path / "pair"
    d.mkdir()
    g = A.gate_blind(d / "BLIND_COMMIT", d, [])
    assert g["ok"] is False


def test_gate_blind_reads_section_4_of_the_real_read_rule():
    """The §4-byte-identity check must actually FIND §4 in the pair of record."""
    rr = (REPO / "measurement/everyply_probe_20260823/READ_RULE.md").read_text()
    sec = A._section4(rr)
    assert sec.startswith("## §4 — THE BRANCHES")
    assert "E-FLATNULL" in sec and "E-UNRESOLVED" in sec
    assert "## §5" not in sec


def test_unreadable_when_any_gate_fails(corpus, tmp_path, monkeypatch):
    """READ_RULE §4: ANY §3 gate FAILS => U-UNREADABLE and NO branch may fire."""
    v, _ = _build(corpus, tmp_path, monkeypatch, blind_ok=False)
    assert v["branch"] == "U-UNREADABLE"
    assert "G-BLIND" in v["adjudication"]["failed_gates"]
    assert "FULLY ACCEPTABLE OUTCOME" in v["adjudication"]["licence"]


# --------------------------------------------------------------------------- #
# 6. the §1 WITNESS                                                            #
# --------------------------------------------------------------------------- #
def test_witness_reproduces_the_analyser_from_scratch():
    rows = ([_row(f"a{i}", 0.5 + 0.1 * i, "A", root=f"r{i % 3}") for i in range(6)]
            + [_row(f"b{i}", -0.2 * i, "B", root=f"s{i % 4}") for i in range(8)]
            + [_row(f"c{i}", 0.3, "C", root=f"t{i}") for i in range(7)])
    pooled = A.kappa_pooled(rows, W_CENSUS, 11)
    wit = A.recompute_witness(rows, W_CENSUS)
    assert wit["kappa"] == pytest.approx(pooled["mean"], abs=A.WITNESS_TOL)
    assert wit["se"] == pytest.approx(pooled["se_cluster"], abs=A.WITNESS_TOL)
    assert "never a branch input" in wit["note"].lower()


def test_witness_disagreement_is_unreadable(corpus, tmp_path, monkeypatch):
    monkeypatch.setattr(A, "recompute_witness",
                        lambda rows, w: {"kappa": 99.0, "se": 1.0, "z": 99.0,
                                         "n": len(rows), "n_roots": 1,
                                         "note": "stub"})
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert v["witness_gate"]["ok"] is False
    assert v["branch"] == "U-UNREADABLE"
    assert "WITNESS" in v["adjudication"]["failed_gates"]


# --------------------------------------------------------------------------- #
# 7. THE BRANCH SWEEP — §4 in order, first match wins, §0.A structural block    #
# --------------------------------------------------------------------------- #
class _Hold:
    """A holdout stand-in that records whether the branch table touched it."""

    def __init__(self, mean=0.0):
        self._m = mean
        self.reads = 0
        self.reads_before_decision = 0
        self.decided = False

    def decide(self):
        self.decided = True

    def value(self):
        self.reads += 1
        if not self.decided:
            self.reads_before_decision += 1
        return {"mean": self._m}


ALL_POS = {"A": 0.1, "B": 0.1, "C": 0.1}
ALL_NEG = {"A": -0.1, "B": -0.1, "C": -0.1}


@pytest.mark.parametrize("kappa,se,strata,kill_only,want", [
    # E-HARM: kappa <= -0.15 AND z <= -2
    (-0.30, 0.05, ALL_NEG, True, "E-HARM"),
    (-0.30, 0.05, ALL_NEG, False, "E-HARM"),
    (-0.30, 0.30, ALL_NEG, True, "E-UNRESOLVED"),      # z fails
    (-0.10, 0.01, ALL_NEG, True, "E-FLATNULL"),        # bar fails; UB95 < 0.15
    # E-CLEAN / E-FUND: blocked at SIZE-1, fall through
    (0.50, 0.05, ALL_POS, True, "E-UNRESOLVED"),
    (0.50, 0.05, ALL_POS, False, "E-CLEAN"),
    (0.20, 0.05, ALL_POS, True, "E-UNRESOLVED"),
    (0.20, 0.05, ALL_POS, False, "E-FUND"),
    # E-FLATNULL: UB95 = kappa + 2*se < 0.15
    (0.00, 0.05, ALL_POS, True, "E-FLATNULL"),
    (-0.019, 0.084, ALL_POS, True, "E-FLATNULL"),      # just past the §4 threshold
    (-0.018, 0.084, ALL_POS, True, "E-UNRESOLVED"),    # UB95 == 0.150 exactly: `<` is STRICT
    (0.00, 0.084, ALL_POS, True, "E-UNRESOLVED"),      # 0.168 > 0.15 -> not parked
    # residual
    (0.10, 0.05, ALL_POS, True, "E-UNRESOLVED"),
])
def test_branch_sweep(kappa, se, strata, kill_only, want):
    h = _Hold(0.05)
    adj = A.decide_branch(kappa, se, kappa / se, strata, h, kill_only=kill_only)
    assert adj["branch"] == want


def test_section_0A_blocks_the_positive_branches_and_records_it():
    h = _Hold(0.05)
    adj = A.decide_branch(0.50, 0.05, 10.0, ALL_POS, h, kill_only=True)
    assert adj["branch"] == "E-UNRESOLVED"
    assert adj["blocked_by_section_0A"] == ["E-CLEAN", "E-FUND"]
    assert "KILL-ONLY" in adj["section_0A"]
    # §0.A's own words: a positive kappa_hat at SIZE-1 is an UNRESOLVED READING,
    # and that is a DECLARED limit of the funded size, not a discovered one.
    assert "UNRESOLVED READING" in adj["section_0A"]
    assert "DECLARED LIMIT OF THE FUNDED SIZE" in adj["section_0A"]


def test_section_0A_block_never_reads_the_holdout():
    """DESIGN §6.4: the holdout enters E-FUND ONLY, and E-FUND cannot fire."""
    h = _Hold(-9.0)
    adj = A.decide_branch(0.20, 0.05, 4.0, ALL_POS, h, kill_only=True)
    assert adj["branch"] == "E-UNRESOLVED"
    assert h.reads_before_decision == 0
    assert "kappa_holdout_ge_0" not in adj["conjuncts"]["E-FUND"]


def test_e_fund_reads_the_holdout_only_when_it_can_actually_fire():
    h = _Hold(-9.0)                       # a NEGATIVE holdout kills the conjunct
    adj = A.decide_branch(0.20, 0.05, 4.0, ALL_POS, h, kill_only=False)
    assert h.reads_before_decision == 1
    assert adj["conjuncts"]["E-FUND"]["kappa_holdout_ge_0"] is False
    assert adj["branch"] == "E-UNRESOLVED"


def test_first_match_wins_precedence_is_the_read_rule_order():
    assert A.BRANCH_ORDER == ("E-HARM", "E-CLEAN", "E-FUND", "E-FLATNULL",
                              "E-UNRESOLVED")
    assert A.KILL_ONLY_BLOCKED == ("E-CLEAN", "E-FUND")


def test_e_clean_requires_two_of_three_strata_nonnegative():
    h = _Hold(1.0)
    mixed = {"A": -1.0, "B": -1.0, "C": 1.0}
    adj = A.decide_branch(0.50, 0.05, 10.0, mixed, h, kill_only=False)
    assert adj["branch"] == "E-UNRESOLVED"
    assert adj["conjuncts"]["E-CLEAN"]["ge2of3_strata_nonneg"] is False


def test_ub95_uses_the_declared_2_0_not_1_96():
    h = _Hold(0.0)
    adj = A.decide_branch(0.0, 0.05, 0.0, ALL_POS, h)
    assert adj["ub95"] == pytest.approx(0.10, abs=1e-12)
    assert "2.0" in adj["ub95_convention"]
    assert A.UB95_K == 2.0


def test_flatnull_threshold_reproduces_the_read_rule_note():
    """READ_RULE §4's ⚠️ note: at n=400, q=0.76, se=0.084 => E-FLATNULL needs
    kappa_hat < 0.15 - 2(0.084) = -0.018."""
    se = EP.se_kappa(400, 0.76)
    assert A.KAPPA_STAR - A.UB95_K * se == pytest.approx(-0.018, abs=1e-3)


# --------------------------------------------------------------------------- #
# 8. the mandatory prints                                                      #
# --------------------------------------------------------------------------- #
def test_e_unresolved_prints_the_n_that_would_resolve_it(corpus, tmp_path, monkeypatch):
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert v["branch"] in ("E-UNRESOLVED", "E-FLATNULL", "E-HARM")
    ntr = v["n_to_resolve"]
    assert ntr["n"] is not None and ntr["n_ceil"] >= 1
    assert "REALIZED dispersion" in ntr["why"]
    assert "898" in ntr["why"]                 # the supply ceiling travels with it


def test_n_to_resolve_scales_as_one_over_kappa_squared():
    a = A.n_to_resolve(0.10, 0.08, 400)["n"]
    b = A.n_to_resolve(0.20, 0.08, 400)["n"]
    assert a / b == pytest.approx(4.0, abs=1e-9)
    assert A.n_to_resolve(0.0, 0.08, 400)["n"] is None


def test_n_cell_is_printed_at_both_na_ends():
    e = A.elo_chain(0.20)
    assert set(e) == {"conservative_NA_0.31", "optimistic_NA_0.85", "rider"}
    lo, hi = e["conservative_NA_0.31"], e["optimistic_NA_0.85"]
    assert lo["pts_per_game"] == pytest.approx(0.20 * 12.812 * 0.31, abs=1e-12)
    assert hi["elo"] == pytest.approx(7.79 * hi["pts_per_game"], abs=1e-12)
    # DESIGN §4.3's own table: kappa=0.20 => +6.2 .. +17.0 elo
    assert lo["elo"] == pytest.approx(6.2, abs=0.1)
    assert hi["elo"] == pytest.approx(17.0, abs=0.1)
    # the conservative chain needs a MUCH bigger cell than n=800
    assert lo["n_cell"] > 800 > hi["n_cell"]
    assert "MAY NEVER BE QUOTED BARE" in e["rider"]


def test_elo_chain_matches_the_design_bracket_at_kappa_star():
    e = A.elo_chain(0.15)
    assert e["conservative_NA_0.31"]["elo"] == pytest.approx(4.6, abs=0.1)
    assert e["optimistic_NA_0.85"]["elo"] == pytest.approx(12.7, abs=0.1)


def test_readout_prints_all_nine_rails_and_the_scope_fence(corpus, tmp_path,
                                                           monkeypatch):
    v, _ = _build(corpus, tmp_path, monkeypatch)
    md = A.render(v)
    assert len(v["honesty_rails"]) == 9
    for r in v["honesty_rails"]:
        assert r["title"] in md
    for probe in ("PRIOR-AGAINST 1", "PRIOR-AGAINST 2", "PRIOR-AGAINST 3",
                  "INCUMBENT ASYMMETRY", "FUNDING VERDICT, NEVER AN EXCLUSION",
                  "UNDER-READ THE GAME CELL", "NO DEPLOY IS LICENSED",
                  "SEC-ARB", "CURRENCY"):
        assert probe in md, probe
    assert "3.49" in md and "0.2545" in md          # the §4.3 C scope fence
    assert "KILL-ONLY" in md                        # §0.A, on every branch
    assert "NOT DIRECTLY COMPARABLE TO THE TIED-PLY arb = +0.2065" in md


def test_readout_prints_the_arm_builder_and_the_gates_with_addresses(corpus, tmp_path,
                                                                     monkeypatch):
    v, _ = _build(corpus, tmp_path, monkeypatch)
    md = A.render(v)
    assert v["arm_builder"] == ["leaf_topk"]
    assert "arm builder" in md and "leaf_topk" in md
    for gid in A.GATE_IDS:
        assert gid in md


def test_readout_reports_the_holdout_on_every_branch_after_adjudication(
        corpus, tmp_path, monkeypatch):
    v, _ = _build(corpus, tmp_path, monkeypatch)
    h = v["holdout"]
    assert h["n_holdout_positions"] == 1
    assert h["reads_before_decision"] == 0        # untouched until its gate
    assert "E-FUND ONLY" in h["note"]


def test_scale_all_is_one_and_stamped(corpus, tmp_path, monkeypatch):
    v, rows = _build(corpus, tmp_path, monkeypatch)
    assert A.SCALE_ALL == 1.0
    assert v["primary"]["scale_all"] == 1.0
    assert all(r["scale_all"] == 1.0 for r in rows)


def test_no_band_is_claimed_on_any_branch(corpus, tmp_path, monkeypatch):
    v, _ = _build(corpus, tmp_path, monkeypatch)
    assert v["band"] == 28000000000 and v["corpus"] == "champ449"
    assert "NO deck band" in v["governance"]
    assert "BAND_REGISTRY" in v["governance"]


def test_q_and_phi_are_reported_they_reprice_any_topup(corpus, tmp_path, monkeypatch):
    v, _ = _build(corpus, tmp_path, monkeypatch)
    q = v["q"]
    assert q["pooled"] == pytest.approx(1 / 3, abs=1e-12)
    assert set(q["by_stratum"]) == {"A", "B", "C"}
    assert q["planning_central"] == 0.76
    assert v["phi_nontied"]["phi_nontied_per_game_per_seat"] == pytest.approx(
        12.812, abs=1e-9)


# --------------------------------------------------------------------------- #
# 9. corpus builder — arm construction and the named build risk                 #
# --------------------------------------------------------------------------- #
def test_pooled_ranking_key_is_pooled_q_argmax_own_key():
    agg_n = {5: 10.0, 7: 10.0, 9: 4.0}
    agg_w = {5: 1.0, 7: 5.0, 9: 4.0}
    ranked = EC.pooled_ranking(agg_n, agg_w, 2)
    assert ranked[0] == 9                       # Q = 1.0 beats 0.5 and 0.1
    assert ranked == [9, 7, 5]


def test_pooled_ranking_head_is_the_champion_pick_by_construction():
    import importlib

    fa = importlib.import_module("carcassonne_ai.fair_agent")
    agg_n = {5: 10.0, 7: 10.0, 9: 4.0}
    agg_w = {5: 1.0, 7: 5.0, 9: 4.0}
    assert EC.pooled_ranking(agg_n, agg_w, 2)[0] == fa.pooled_q_argmax(agg_n, agg_w, 2)


def test_pooled_ranking_min_visits_eligibility_matches():
    agg_n = {5: 1.0, 7: 10.0}
    agg_w = {5: 100.0, 7: 1.0}
    assert EC.pooled_ranking(agg_n, agg_w, 2) == [7]       # 5 is ineligible
    assert EC.pooled_ranking({5: 1.0}, {5: 100.0}, 2) == [5]   # fallback: all visited


def test_arms_from_ranking_forces_the_champion_to_arm_zero_and_dedupes():
    # 9 and 3 transpose to the same afterstate (repr 3); 1 is its own group.
    repr_of = {7: 7, 3: 3, 9: 3, 1: 1}
    assert EC.arms_from_ranking([9, 3, 7, 1], 7, repr_of, 4) == [7, 9, 1]
    assert EC.arms_from_ranking([3, 9, 1], 3, repr_of, 4) == [3, 1]


def test_arms_from_ranking_unions_a_champion_outside_the_ranking():
    repr_of = {1: 1, 2: 2, 3: 3}
    assert EC.arms_from_ranking([2, 3], 1, repr_of, 4)[0] == 1


def test_arms_from_ranking_respects_k():
    repr_of = {i: i for i in range(10)}
    assert EC.arms_from_ranking(list(range(10)), 0, repr_of, 4) == [0, 1, 2, 3]


def test_afterstate_dedupe_is_build_positions_own_validator():
    """The entry this module builds must satisfy `dedupe_tie_actions`' validation
    (a stale map FAILS LOUDLY there) — that is what makes the reuse real."""
    entry = {"action_groups": [[1, 4], [2], [3]], "repr_actions": [1, 2, 3],
             "n_distinct_afterstates": 3, "all_transposition": False}
    ded = BP.dedupe_tie_actions([1, 2, 3, 4], entry)
    assert ded["kept"] == [1, 2, 3] and ded["repr_of"][4] == 1
    with pytest.raises(ValueError, match="stale afterstate map"):
        BP.dedupe_tie_actions([1, 2, 3], entry)


def test_pooled_q_is_refused_on_a_non_python_backend(monkeypatch):
    """DESIGN §3.1's named BUILD RISK, made mechanical: the pooled root Q lives
    only in the PYTHON `fair_agent.pooled_q_argmax` hook."""
    import carcassonne_ai.mirror_protocol as MP

    # A real `Execution` (dict-based: only `backend`/`is_rust` are properties,
    # `rust_threads`/`source` are dict keys) -- a bare-attribute stand-in here
    # previously masked the `ex.rust_threads`/`ex.source` AttributeError that
    # `check_arm_builder_backend` actually raises against the real class.
    ex = MP.Execution(backend="rust", rust_threads=1, parallel_workers=None,
                       profile="desktop", source="profile")
    monkeypatch.setattr(MP, "resolve_execution", lambda *a, **k: ex)
    with pytest.raises(SystemExit, match="pooled_q"):
        EC.check_arm_builder_backend("pooled_q")
    got = EC.check_arm_builder_backend("leaf_topk")
    assert got["backend"] == "rust" and got["arm_builder"] == "leaf_topk"


def test_production_champion_block_reads_the_governance_file():
    b = EC.production_champion_block()
    assert b["leaf_hash"] == LEAF
    assert b["leaf_hash_dialect"] == "harness_leaf_hash"
    assert b["tiearb"]["enabled"] is True and b["tiearb"]["B"] == 64
    assert b["tiearb"]["eps"] == 0.0 and b["tiearb"]["J"] == 4
    assert "NOT the built agent's manifest" in b["tiearb_address"]


def test_corpus_records_root_resolution_handles_both_shapes(tmp_path):
    (tmp_path / "tier1-greedy").mkdir()
    assert EC.resolve_records_root(tmp_path, "tier1-greedy").name == "tier1-greedy"
    assert EC.resolve_records_root(tmp_path, "clair-puct") == tmp_path


def test_corpus_selection_loader_preserves_the_committed_order(tmp_path):
    p = tmp_path / "SELECTION.jsonl"
    p.write_text("".join(json.dumps({"rid": f"ep_{i}", "chunk": 1 + i % 2}) + "\n"
                         for i in range(6)))
    got = EC.load_selection(p, chunk=1)
    assert [r["rid"] for r in got] == ["ep_0", "ep_2", "ep_4"]
    assert [r["rid"] for r in EC.load_selection(p, chunk=1, limit=2)] == ["ep_0", "ep_2"]


def test_selective_mode_end_to_end_emits_a_priceable_if_plan(corpus, tmp_path):
    """`--mode selective` on real files: the 2.19x economy, the zero-fill record,
    and a plan `run_tiletie.check_positions` would accept."""
    plan_dir = corpus["pair"] / "positions_chunk1"
    # give the arms plan the leg files the selective stage reads its rows from
    src = []
    for rid, meta in corpus["arms"].items():
        src.append({"rid": rid, "root_id": meta["root_id"],
                    "deck_seed": meta["deck_seed"], "ply": meta["ply"],
                    "root_player": meta["seat"], "pick_a": meta["arms"][0],
                    "pick_b": meta["arms"][1], "checksum": "CKS",
                    "rules_profile": "walled", "stratum": "selfplay",
                    "game_label": rid, "action_played": meta["arms"][0],
                    "action_best": meta["arms"][1], "actions": [1, 2, 3, 4]})
    leg = plan_dir / "positions_walled_leg1.jsonl"
    leg.write_text("".join(json.dumps(x) + "\n" for x in src))
    plan = json.loads((plan_dir / "POSITIONS_PLAN.json").read_text())
    plan["files"] = {"walled/leg1": {"path": str(leg), "n": len(src)}}
    (plan_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan))

    out = tmp_path / "if_out"
    zf = tmp_path / "ZEROFILL_chunk1.json"
    argv = ["--mode", "selective", "--plan-dir", str(plan_dir),
            "--arb-records", str(corpus["arb"]), "--m", "4",
            "--out-dir", str(out), "--zerofill-out", str(zf)]
    got = EC.build_selective_mode(EC.parse_args(argv))

    assert got["selective"]["planned"] == 3
    assert got["selective"]["priced"] == 1        # only ep_1_10 changes the pick
    assert got["selective"]["zero"] == 2
    assert got["afterstate_dedupe"]["applied"] is True
    idx = json.loads((out / "ARMS.json").read_text())
    assert idx["ep_1_10"]["arms"] == [100, 200]
    assert idx["ep_2_10"]["arms"] == [100] and idx["ep_2_10"]["zero_filled"] is True
    # a singleton emits NO leg file line -- that IS the saving
    lines = [json.loads(x) for x in
             (out / "positions_walled_leg1.jsonl").read_text().splitlines() if x.strip()]
    assert [x["rid"] for x in lines] == ["ep_1_10"]
    z = json.loads(zf.read_text())
    assert z["n_zero"] == 2 and {r["rid"] for r in z["rows"]} == {"ep_2_10", "ep_3_10"}
    assert all(r["kappa"] == 0.0 for r in z["rows"])
    assert "ZERO-FILLED, never" in z["rows"][0]["why"]


def test_corpus_parse_args_accepts_the_launchers_exact_invocations():
    a = EC.parse_args(["--mode", "arms", "--selection", "S.jsonl", "--chunk", "1",
                       "--out-dir", "D", "--rules-profile", "walled",
                       "--workers", "16"])
    assert a.mode == "arms" and a.chunk == 1 and a.arm_builder == "pooled_q"
    b = EC.parse_args(["--mode", "selective", "--plan-dir", "P", "--arb-records", "R",
                       "--m", "32", "--out-dir", "D", "--zerofill-out", "Z.json"])
    assert b.mode == "selective" and b.m == 32
    c = EC.parse_args(["--mode", "arms", "--selection", "S.jsonl", "--chunk", "1",
                       "--limit", "20", "--out-dir", "D", "--rules-profile", "walled",
                       "--workers", "16"])
    assert c.limit == 20
    for bad in (["--mode", "arms", "--out-dir", "D"],
                ["--mode", "selective", "--out-dir", "D"]):
        with pytest.raises(SystemExit):
            EC.parse_args(bad)


def test_analyser_parse_args_accepts_the_launchers_exact_invocation(tmp_path):
    argv = []
    for k in range(1, 5):
        argv += ["--arb-records", f"/o/arb/chunk{k}", "--if-records", f"/o/if/chunk{k}"]
    argv += ["--plan-dir", str(tmp_path), "--selection", "S.jsonl",
             "--holdout-games", "H.json", "--knowngood", "K.json",
             "--blind-commit", "B", "--boot-seed", "20260823",
             "--out-dir", str(tmp_path)]
    a = A.parse_args(argv)
    assert len(a.arb_records) == 4 and len(a.if_records) == 4
    assert a.kill_only is True                  # READ_RULE §0.A is the DEFAULT
    assert a.boot_seed == 20260823
    with pytest.raises(SystemExit):
        A.parse_args(["--plan-dir", str(tmp_path), "--out-dir", str(tmp_path)])


# --------------------------------------------------------------------------- #
# 10. the launcher's refusal checks                                            #
# --------------------------------------------------------------------------- #
def test_both_owed_builds_exist_where_the_launcher_looks():
    for f in ("build_everyply_corpus.py", "analyze_everyply.py"):
        assert (REPO / "scripts" / "tiletie" / f).is_file()


def test_launcher_dry_run_reaches_the_analyze_stage():
    """`run_probe_DRAFT.sh --dry-run` must no longer refuse on the OWED BUILDS.

    ⚠️ The launcher redirects each stage into `logs/<stage>.log`, so the `[dry-run]`
    command echoes land there, not on stdout. Any log file this test creates is
    removed again — a test must not leave artifacts in a measurement dir.
    """
    d = REPO / "measurement/everyply_probe_20260823"
    logs = d / "logs"
    before = {p.name for p in logs.glob("*")} if logs.is_dir() else set()
    existed = logs.is_dir()
    try:
        p = subprocess.run(["bash", str(d / "run_probe_DRAFT.sh"), "local",
                            "--stage", "all", "--dry-run"],
                           capture_output=True, text=True, timeout=300, cwd=str(REPO))
        assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
        assert "OWED BUILD missing" not in p.stdout
        assert "STAGE analyze DONE" in p.stdout
        assert "NO BAND IS CLAIMED ON ANY BRANCH" in p.stdout
        echoed = "\n".join(f.read_text() for f in logs.glob("*.log"))
        assert "build_everyply_corpus.py" in echoed
        assert "analyze_everyply.py" in echoed
        assert "--mode selective" in echoed
    finally:
        if logs.is_dir():
            for f in logs.glob("*"):
                if f.name not in before:
                    f.unlink()
            if not existed and not any(logs.iterdir()):
                logs.rmdir()
