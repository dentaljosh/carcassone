"""Contract tests for `scripts/tiletie/probe_pickers.py` — the three-picker probe.

What is actually asserted here (the four things the harness's honesty rests on):

  1. **The estimator is REUSED, not copied.** `probe_pickers` must not define its
     own `parity_indices` / `crossfit_regret` / `cluster_robust` / `bootstrap_roots`
     / `paired_ratio_bootstrap` / `aggregate` / `zero_rates`, and the objects it
     binds must BE `analyze_tiletie`'s and `analyze_tiearb`'s.
  2. **The CRN derivation is `oracle_score_pilot`'s, bit-for-bit.** Checked against
     the SEEDS BANKED ON DISK in the spent corpus, not against a re-implementation.
  3. **The learned picker's split is by `root_id` and leaks nothing.**
  4. **The known-good gate reproduces `arb = 0.2065` on real records.**

Plus: `oracle_score_pilot.py` is unmodified on disk (the v2.9 policy is injected at
its documented dispatch seam, process-locally), the production leaf really is
`a36d2e15a3b3d71d`, and a tiny end-to-end over a handful of real records.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import probe_pickers as PP                                          # noqa: E402
import analyze_tiletie as AT                                        # noqa: E402
import analyze_tiearb as ATB                                        # noqa: E402
import oracle_score_pilot as OSP                                    # noqa: E402
import run_tiletie as RT                                            # noqa: E402

IF_ROOT = Path(PP.DEFAULT_IF_RECORDS)
HAVE_SHARE = IF_ROOT.is_dir()
share_only = pytest.mark.skipif(not HAVE_SHARE,
                                reason="the spent corpus lives on /mnt/c/carc-shared")


# --------------------------------------------------------------------------- #
# 1. estimator reuse — imports, not copies                                      #
# --------------------------------------------------------------------------- #
REUSED_FROM_AT = ("parity_indices", "crossfit_regret", "cluster_robust",
                  "bootstrap_roots", "zero_rates", "aggregate", "load_plan",
                  "discover_records", "pts_to_elo", "_sub_mean")
REUSED_FROM_ATB = ("build_positions", "merge_arb_records", "resolve_records_root",
                   "paired_ratio_bootstrap", "rnd_arm_position")


def test_modules_are_the_real_ones_not_vendored_copies():
    assert PP.AT is AT
    assert PP.ATB is ATB
    assert PP.OSP is OSP
    assert PP.RT is RT
    assert ATB.AT is AT, "analyze_tiearb must itself still be reusing analyze_tiletie"


@pytest.mark.parametrize("name", REUSED_FROM_AT)
def test_probe_pickers_does_not_redefine_analyze_tiletie_estimators(name):
    src = Path(PP.__file__).read_text()
    assert f"def {name}(" not in src, (
        f"probe_pickers defines its own {name} — it must import analyze_tiletie's")
    assert hasattr(AT, name)


@pytest.mark.parametrize("name", REUSED_FROM_ATB)
def test_probe_pickers_does_not_redefine_analyze_tiearb_machinery(name):
    src = Path(PP.__file__).read_text()
    assert f"def {name}(" not in src, (
        f"probe_pickers defines its own {name} — it must import analyze_tiearb's")
    assert hasattr(ATB, name)


def test_the_capture_path_calls_the_imported_estimators():
    """`price_picks` is the ONLY generalised line; it must still route through the
    imported parity split and sub-mean, and `aggregate_picker` through the imported
    aggregate + paired ratio bootstrap."""
    import inspect
    price = inspect.getsource(PP.price_picks)
    assert "AT.parity_indices(" in price
    assert "AT._sub_mean(" in price
    assert "ATB.PARITY_BASE" in price
    agg = inspect.getsource(PP.aggregate_picker)
    assert "AT.aggregate(" in agg
    assert "ATB.paired_ratio_bootstrap(" in agg
    for p in (PP.picker_tier1, PP.picker_v29):
        assert "AT.crossfit_regret(" in inspect.getsource(p)


def test_constants_are_the_tiearb_run_s_own():
    assert PP.N_POSITIONS_OF_RECORD == 733
    assert PP.N_ROOTS_OF_RECORD == 399
    assert ATB.M_EXPECTED == 32
    assert RT.WORLD_SEED_SALT == "tiletie-v1"
    assert ATB.PARITY_BASE == 1


# --------------------------------------------------------------------------- #
# 2. CRN — oracle_score_pilot's derivation, bit-for-bit against banked seeds     #
# --------------------------------------------------------------------------- #
def _sample_if_records(n=6):
    recs = sorted(IF_ROOT.rglob("records/*.json"))
    assert recs, f"no banked records under {IF_ROOT}"
    rng = random.Random(PP.PROBE_SEED)
    return [json.loads(p.read_text()) for p in rng.sample(recs, min(n, len(recs)))]


@share_only
def test_crn_seed_derivation_matches_banked_records_bit_for_bit():
    """The seeds this harness would generate for (rid, j, salt) MUST equal the ones
    already on disk — that is what makes a new leg CRN-paired with the spent ones."""
    for rec in _sample_if_records():
        rid, m, salt = rec["rid"], int(rec["m"]), rec["world_seed_salt"]
        assert salt == RT.WORLD_SEED_SALT and m == ATB.M_EXPECTED
        ws = OSP.world_seeds(rid, m, salt)
        ps = [OSP.playout_seed(rid, j, salt) for j in range(m)]
        assert ws == [int(x) for x in rec["world_seeds"]], rid
        assert ps == [int(x) for x in rec["playout_seeds"]], rid


def test_probe_pickers_never_re_derives_a_seed():
    src = Path(PP.__file__).read_text()
    assert "def world_seed" not in src and "def playout_seed" not in src
    assert "sha256" not in src, (
        "a hash literal in this file means a seed is being re-derived; import "
        "oracle_score_pilot.world_seed / .playout_seed instead")
    assert "OSP.world_seed(" in src and "OSP.playout_seed(" in src


# --------------------------------------------------------------------------- #
# 3. the v2.9 policy and its injection seam                                     #
# --------------------------------------------------------------------------- #
def test_oracle_score_pilot_is_unmodified_on_disk():
    """The v2.9 policy is registered PROCESS-LOCALLY. The ruler stays byte-identical
    for every other caller, so no other measurement is re-instrumented by this work."""
    rel = "scripts/measurement_infra/oracle_score_pilot.py"
    rc = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel])
    assert rc.returncode == 0, f"{rel} has uncommitted modifications"
    text = (REPO / rel).read_text()
    assert "v29" not in text and "probe_pickers" not in text


def test_production_leaf_is_the_champion_leaf():
    from carcassonne_ai import champion_factory as CF
    prov = CF.verify_leaf(CF.production_leaf_cfg())
    assert prov["hashes"]["harness_leaf_hash"] == "a36d2e15a3b3d71d"
    assert CF.LEAF_HASH_HARNESS == "a36d2e15a3b3d71d"


def test_registration_is_additive_idempotent_and_dispatches():
    original = getattr(OSP.build_continuation_agent, "_wrapped_original",
                       OSP.build_continuation_agent)
    PP.register_v29_policy()
    PP.register_v29_policy()                       # idempotent
    assert PP.V29_POLICY in OSP.ORACLE_POLICIES
    assert getattr(OSP.build_continuation_agent, "_wrapped_original") is original
    assert OSP.ORACLE_POLICIES["tier1-greedy"]["uses_oracle_sims"] is False


def test_v29_policy_is_rejected_on_a_non_python_backend():
    PP.register_v29_policy()
    with pytest.raises(ValueError, match="python-only"):
        OSP.build_continuation_agent(None, policy=PP.V29_POLICY, sims=0, seed=0,
                                     backend="rust")


def test_v29_greedy_argmaxes_the_production_leaf():
    """The policy IS 1-ply argmax of the production flat leaf on the child state —
    checked against an independent recomputation, not against itself."""
    from carcassonne_ai import champion_factory as CF, flat_leaf
    import root_replay as RR
    from carcassonne_ai import rules_profile as RP

    plan = PP.read_plan_legs(PP.DEFAULT_PLAN_DIR)
    row = None
    for key, rows in sorted(plan.items()):
        if key.startswith("walled/"):
            for _rid, line in rows:
                d = json.loads(line)
                if d.get("actions"):
                    row = d
                    break
        if row:
            break
    assert row is not None
    prof = RP.resolve("walled")
    if RP.r9_env_on() != prof.r9_env_expected:
        pytest.skip("CARCASSONNE_FIX_R9 latch does not match the 'walled' profile")
    game, board = RR.replay_actions(row["deck_seed"], row["actions"], row["ply"])

    cfg = CF.production_leaf_cfg()
    bag = bool(getattr(cfg, "bag_close", False))
    mover = int(board.state.current_player)
    legal = np.flatnonzero(game.get_valid_moves(board))
    want = {}
    for a in legal:
        child, _ = game.get_next_state(board, int(a))
        want[int(a)] = flat_leaf.flat_virtual_score_v2_float(child.state, mover, cfg, bag)
    best = max(want.values())
    got = PP.V29GreedyPlayer(game, seed=7).choose_action(board)
    assert want[int(got)] == best
    # deterministic in the seed (the playout_seed only fixes the tie-break)
    assert PP.V29GreedyPlayer(game, seed=7).choose_action(board) == got


# --------------------------------------------------------------------------- #
# 4. the chunk shape                                                            #
# --------------------------------------------------------------------------- #
def test_chunks_partition_the_corpus_and_keep_a_rid_s_legs_together(tmp_path):
    legs = PP.read_plan_legs(PP.DEFAULT_PLAN_DIR)
    rids = sorted({rid for rows in legs.values() for rid, _ in rows})
    assert len(rids) == PP.N_POSITIONS_OF_RECORD
    parts = [set(PP.chunk_rids(rids, k, 8)) for k in range(1, 9)]
    assert set().union(*parts) == set(rids)
    assert sum(len(p) for p in parts) == len(rids), "chunks overlap"
    # every leg of the corpus is written exactly once across the 8 chunks, because
    # chunking is BY rid — a position's arms can never be split across chunks.
    total_in = sum(len(rows) for rows in legs.values())
    total_out = 0
    for k, part in enumerate(parts, start=1):
        kept = PP.write_chunk_legs(legs, part, tmp_path / f"chunk{k}")
        assert kept and all(l["n"] > 0 for l in kept)
        total_out += sum(l["n"] for l in kept)
    assert total_out == total_in == 1468


def test_parse_chunk_rejects_garbage():
    assert PP.parse_chunk("3/8") == (3, 8)
    with pytest.raises(SystemExit):
        PP.parse_chunk("banana")
    with pytest.raises(SystemExit):
        PP.chunk_rids(["a", "b"], 9, 8)


# --------------------------------------------------------------------------- #
# 5. the learned picker — root split, no leakage, pairwise labels               #
# --------------------------------------------------------------------------- #
def test_root_folds_is_a_partition_of_roots():
    roots = [f"r{i}" for i in range(37)]
    folds = PP.root_folds(roots, 5, PP.PROBE_SEED)
    assert len(folds) == 5
    flat = [r for f in folds for r in f]
    assert sorted(flat) == sorted(roots)
    assert len(set(flat)) == len(roots)
    # deterministic
    assert PP.root_folds(roots, 5, PP.PROBE_SEED) == folds


def test_training_rows_never_contain_a_held_out_root():
    """The leakage guard, exercised on the real shape: positions of a held-out root
    contribute NO training pair, even though other positions of other roots do."""
    feats = {f"p{i}": [[float(i), 1.0], [float(i) + 1, 0.0]] for i in range(12)}
    labels = {f"p{i}": {"root_id": f"root{i % 4}", "arm_order": [0, 1],
                        "labels": [0.0, float(i % 3)]} for i in range(12)}
    folds = PP.root_folds([v["root_id"] for v in labels.values()], 4, PP.PROBE_SEED)
    for te_roots in folds:
        te = set(te_roots)
        tr_rids = [r for r in labels if labels[r]["root_id"] not in te]
        te_rids = [r for r in labels if labels[r]["root_id"] in te]
        assert te_rids, "a fold must hold something out"
        X, y, groups = PP.pairwise_rows(feats, labels, tr_rids)
        assert not (set(groups) & te), "a held-out root leaked into training"
        assert X.shape[0] == len(y) == len(groups)


def test_pairwise_rows_are_antisymmetric_and_drop_tied_labels():
    feats = {"a": [[1.0, 0.0], [0.0, 1.0]], "b": [[2.0, 2.0], [2.0, 2.0]]}
    labels = {"a": {"root_id": "R", "arm_order": [0, 1], "labels": [1.0, 0.0]},
              "b": {"root_id": "R", "arm_order": [0, 1], "labels": [5.0, 5.0]}}
    X, y, groups = PP.pairwise_rows(feats, labels, ["a", "b"])
    assert X.shape[0] == 2, "one ordered pair -> two antisymmetric rows; ties dropped"
    assert np.allclose(X[0], -X[1])
    assert set(y.tolist()) == {0, 1}
    assert groups == ["R", "R"]


def test_net_picker_is_argmax_and_fold_independent():
    pick = PP.picker_net({"p": [0.1, 0.9, 0.5]})
    row = {"rid": "p", "arm_order": [0, 1, 2], "champ_pos": 0}
    assert pick(row, [[0.0]], 0, [0], [1]) == 1
    assert pick(row, [[0.0]], 1, [1], [0]) == 1     # world-independent by construction
    assert pick({"rid": "missing", "arm_order": [0, 1]}, [[0.0]], 0, [0], [1]) is None


def test_net_asymmetry_caveat_is_printed_beside_a_net_number():
    src = Path(PP.__file__).read_text()
    assert "NET_ASYMMETRY_CAVEAT" in src
    assert 'if "net" in blocks:' in src, "the caveat must be conditioned on a net read"


# --------------------------------------------------------------------------- #
# 6. honesty rails, enforced in code                                            #
# --------------------------------------------------------------------------- #
def test_grade_runs_the_knowngood_gate_before_anything_else():
    import inspect
    src = inspect.getsource(PP.cmd_grade)
    i_gate = src.index("require_knowngood(")
    for later in ("picker_v29(", "picker_net(", "load_net_scores("):
        assert src.index(later) > i_gate, f"{later} is read before the known-good gate"
    assert "SystemExit" in inspect.getsource(PP.require_knowngood)


def test_no_flag_can_skip_the_gate():
    src = Path(PP.__file__).read_text()
    assert "--skip-knowngood" not in src and "--force" not in src


def test_tier1_is_always_in_the_table_so_no_picker_is_read_alone():
    import inspect
    src = inspect.getsource(PP.cmd_grade)
    assert 'blocks["tier1"] = aggregate_picker(' in src
    assert "if args.picker" not in src.split('blocks["tier1"]')[0].split(
        "require_knowngood")[-1], "tier1 must be unconditional"


def test_ceiling_caveat_names_the_measured_ceiling():
    assert "+0.048" in PP.CEILING_CAVEAT
    assert "[0.450, 1.320]" in PP.CEILING_CAVEAT
    assert "INCLUDES 1" in PP.CEILING_CAVEAT


# --------------------------------------------------------------------------- #
# 7. real records — the known-good gate and a tiny end-to-end                   #
# --------------------------------------------------------------------------- #
class _Args:
    if_records = PP.DEFAULT_IF_RECORDS
    arb_records = list(PP.DEFAULT_ARB_ROOTS)
    v29_records = PP.DEFAULT_V29_ROOT
    plan_dir = str(PP.DEFAULT_PLAN_DIR)
    full_supply_plan = None
    holdout_roots = str(PP.DEFAULT_HOLDOUT)
    out_dir = None
    boot_seed = 20260816
    rnd_seed = 20260816


@pytest.fixture(scope="module")
def real_inputs():
    if not HAVE_SHARE:
        pytest.skip("the spent corpus lives on /mnt/c/carc-shared")
    return PP.load_grade_inputs(_Args())


@share_only
def test_knowngood_reproduces_the_published_arb_bit_for_bit(real_inputs):
    kg = PP.run_knowngood(real_inputs, 20260816)
    assert kg["ok"], json.dumps(kg, indent=2)[:2000]
    assert kg["reproduced"]["n"] == 733 and kg["reproduced"]["n_roots"] == 399
    assert abs(kg["reproduced"]["arb"] - 0.2065) < 5e-5
    assert abs(kg["reproduced"]["ora"] - 0.2545) < 5e-5
    assert kg["max_abs_position_delta"] == 0.0


@share_only
def test_matrix_for_matches_the_tiearb_assembly(real_inputs):
    """`matrix_for` must reproduce analyze_tiearb's `[values_a] + [values_b...]`."""
    for row in real_inputs["rows"][:8]:
        legs = real_inputs["if_by_rid"][row["rid"]]
        have = row["arm_order"][1:]
        want = [list(legs[have[0]]["values_a"])] + [list(legs[r]["values_b"])
                                                    for r in have]
        assert PP.matrix_for(legs, row["arm_order"]) == want
        assert len(want) == len(row["arm_order"])
        assert all(len(v) == ATB.M_EXPECTED for v in want)


@share_only
def test_tiny_end_to_end_on_a_handful_of_real_records(real_inputs):
    """price_picks + aggregate_picker over 8 real positions: finite numbers, arms in
    range, and the tier1 picker's per-position value identical to the tiearb join's."""
    rows = real_inputs["rows"][:8]
    priced = PP.price_picks(rows, real_inputs["if_by_rid"],
                            PP.picker_tier1(real_inputs["arb_by_rid"]))
    assert len(priced) == len(rows)
    for a, b in zip(rows, priced):
        assert b["arb"] is not None
        assert a["arb"] == b["arb"], a["rid"]
        assert all(0 <= p < len(a["arm_order"]) for p in b["picker_arms"])
    block = PP.aggregate_picker(priced, rows, 20260816)
    assert block["n"] == 8
    assert np.isfinite(block["arb"]["mean"])
    assert np.isfinite(block["ora"]["mean"])
    assert block["F"] is not None


@share_only
def test_crn_cross_witness_is_clean_for_the_banked_judges(real_inputs):
    """(IF, tier1-greedy) is CRN-paired on disk — the witness this harness will
    apply to (IF, v29) must read 0 mismatches on the pair we already trust."""
    w = PP.crn_cross_witness(real_inputs["if_by_rid"], real_inputs["arb_by_rid"],
                             real_inputs["rows"])
    assert w["crn_cross_mismatch"] == 0
    assert w["seed_cross_mismatch"] == 0
    assert w["arm_cross_mismatch"] == 0
    assert w["compared_legs"] == 1468


@share_only
def test_label_collection_reports_shape_mismatches_rather_than_forcing_them():
    lab = PP.collect_labels(_Args())
    assert lab["n_rids"] > 0
    assert lab["n_arm_labels"] >= 2 * lab["n_rids"]
    for p in lab["shape_problems"]:
        assert "why" in p and "rid" in p
    for rid, v in list(lab["labels"].items())[:20]:
        assert len(v["labels"]) == len(v["arm_order"])
        assert all(np.isfinite(x) for x in v["labels"])


# =========================================================================== #
# STAGE-1 FREE TIER — P1 / P2 / P3 + the pre-registered near-tie filter        #
# (measurement/tienet_stage1_plan_20260823/PLAN.md §9.2, §6.4)                 #
# =========================================================================== #
def test_pair_agreement_drops_target_ties_and_halves_predictor_ties():
    """The accuracy convention must match `pairwise_rows`' own, or the label sweep
    and the model's training set are measuring different things."""
    # perfect / reversed
    assert PP.pair_agreement([3.0, 2.0, 1.0], [3.0, 2.0, 1.0]) == (3.0, 3)
    assert PP.pair_agreement([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == (0.0, 3)
    # a TARGET tie carries no order -> not counted at all
    assert PP.pair_agreement([1.0, 2.0], [5.0, 5.0]) == (0.0, 0)
    # a PREDICTOR tie is a coin flip at pick time -> half credit, never full
    assert PP.pair_agreement([1.0, 1.0], [2.0, 1.0]) == (0.5, 1)
    # the degenerate constant model must read 0.5, not 1.0
    agree, tot = PP.pair_agreement([0.0] * 4, [4.0, 3.0, 2.0, 1.0])
    assert tot == 6 and agree / tot == 0.5


def test_se_pairs_for_is_the_crn_paired_standard_error():
    rng = np.random.default_rng(20260823)
    mat = rng.normal(size=(3, 32)).tolist()
    sep = PP.se_pairs_for(mat)
    assert set(sep) == {"0,1", "0,2", "1,2"}, "keys must be JSON-safe 'i,j' strings"
    arr = np.asarray(mat)
    for i, j in ((0, 1), (0, 2), (1, 2)):
        d = arr[i] - arr[j]
        want = float(np.std(d, ddof=1) / np.sqrt(arr.shape[1]))
        assert sep[f"{i},{j}"] == pytest.approx(want, rel=1e-12)
    # PAIRED, not the unpaired sd*sqrt(2)/sqrt(m): on CRN-correlated arms it is
    # strictly SMALLER, which is what makes it the conservative near-tie filter.
    base = rng.normal(size=32)
    corr = [(base + 0.01 * rng.normal(size=32)).tolist(),
            (base + 0.01 * rng.normal(size=32)).tolist()]
    a = np.asarray(corr)
    unpaired = float(np.std(a[0], ddof=1) * np.sqrt(2) / np.sqrt(32))
    assert PP.se_pairs_for(corr)["0,1"] < unpaired
    assert json.loads(json.dumps(sep)) == sep


def test_kappa_zero_reproduces_stage0_and_kappa_monotonically_shrinks_the_pool():
    """PLAN.md §6.4: `kappa=0` MUST reproduce stage-0 exactly (exact ties only).
    Larger kappa must be a strict SUBSET — never a re-weighting, never a new pair."""
    feats = {f"p{i}": [[float(i), 1.0], [0.0, float(i)]] for i in range(6)}
    labels = {}
    for i in range(6):
        mat = [[0.0] * 8, [float(i) * 0.05] * 4 + [float(i) * 0.05 + 0.4] * 4]
        labels[f"p{i}"] = {"root_id": f"R{i % 3}", "arm_order": [0, 1],
                           "labels": [float(np.mean(m)) for m in mat],
                           "se_pairs": PP.se_pairs_for(mat)}
    rids = sorted(labels)
    n0 = PP.pairwise_rows(feats, labels, rids, kappa=0.0)[0].shape[0]
    # kappa=0 is byte-identical to the un-parameterised stage-0 call
    assert np.array_equal(PP.pairwise_rows(feats, labels, rids)[0],
                          PP.pairwise_rows(feats, labels, rids, kappa=0.0)[0])
    counts = [PP.pairwise_rows(feats, labels, rids, kappa=k)[0].shape[0]
              for k in (0.0, 0.5, 1.0, 2.0)]
    assert counts[0] == n0
    assert counts == sorted(counts, reverse=True), "kappa must only ever remove pairs"


def test_labels_from_records_is_a_refactor_not_a_change(real_inputs):
    """`collect_labels`' body was factored out so a second judge can reuse it. The
    factored path must produce BIT-IDENTICAL labels to the stage-0 one."""
    arms_index = json.loads(Path(PP.DEFAULT_PLAN_DIR, "ARMS.json").read_text())
    got = PP.labels_from_records(real_inputs["arb_by_rid"], arms_index)
    old = PP.collect_labels(_Args())
    assert set(got["labels"]) == set(old["labels"])
    for rid, v in old["labels"].items():
        assert got["labels"][rid]["labels"] == v["labels"], rid
        assert got["labels"][rid]["arm_order"] == v["arm_order"], rid


def test_m_waiver_is_explicit_and_subsets_the_FIRST_worlds():
    """PLAN.md §3.1: an m=128 corpus is admitted only by an EXPLICIT waiver, and
    the subset is the FIRST 32 ordered CRN worlds — an exact estimand match."""
    legs = {1: {"values_a": [1.0] * 32 + [99.0] * 96,
                "values_b": [2.0] * 32 + [99.0] * 96,
                "m": 128, "world_seed_salt": RT.WORLD_SEED_SALT,
                "pick_a": 10, "pick_b": 11}}
    arms_index = {"rid1": {"arms": [10, 11], "root_id": "R", "rules_profile": "walled"}}
    # default: REFUSED, and counted rather than coerced
    out = PP.labels_from_records({"rid1": legs}, arms_index)
    assert out["labels"] == {}
    assert out["shape_problems"][0]["why"].startswith("m=128")
    # explicit waiver: admitted, first 32 worlds only, and the waiver is recorded
    out = PP.labels_from_records({"rid1": legs}, arms_index,
                                 allow_m=(32, 128), subset_worlds=32)
    assert out["labels"]["rid1"]["labels"] == [1.0, 2.0], "the 99.0 tail must be cut"
    assert out["labels"]["rid1"]["m"] == 32
    assert out["labels"]["rid1"]["m_record"] == 128
    assert out["labels"]["rid1"]["worlds_subset"] is True
    assert out["n_subset_worlds"] == 1


def test_crossfit_ranker_holds_out_every_root_it_grades():
    feats = {f"p{i}": [[float(i), 1.0, 0.0], [0.0, float(i), 1.0]] for i in range(40)}
    labels = {f"p{i}": {"root_id": f"R{i % 8}", "arm_order": [0, 1],
                        "labels": [0.0, float(i % 5) - 2.0]} for i in range(40)}
    rids = [r for r in sorted(labels) if labels[r]["labels"][0] != labels[r]["labels"][1]]
    res = PP.crossfit_ranker(feats, labels, rids, kfold=4, split_seed=PP.PROBE_SEED,
                             model="pairwise-logistic", min_pairs=2)
    # every root that got a score was held out of the fold that scored it, and the
    # folds together grade every root exactly once
    all_roots = {labels[r]["root_id"] for r in rids}
    graded = {labels[r]["root_id"] for r in res["scores_by_rid"]}
    assert graded == all_roots, "the cross-fit must grade every root"
    assert sum(f.get("n_test_rids", 0) for f in res["folds"]) == len(rids)
    for f in res["folds"]:
        assert f["n_train_roots"] == res["n_roots"] - len(
            PP.root_folds(sorted(all_roots), 4, PP.PROBE_SEED)[f["fold"]])
    assert res["oof_pairs"] > 0
    assert 0.0 <= res["oof_acc"] <= 1.0
    assert res["n_roots"] == len({labels[r]["root_id"] for r in rids})


def test_the_p3_bar_and_its_read_rule_are_committed_and_unmoved():
    """The whole point of P3 is that the branch was written down BEFORE the number.
    If the bar or the rule doc drifts, the pre-registration is worthless."""
    assert PP.P3_ALIVE_BAR == 0.55
    assert PP.GATE_FRACTION == 0.50
    rule = REPO / PP.P3_RULE_DOC
    assert rule.is_file(), f"{PP.P3_RULE_DOC} must exist before any P3 fit"
    txt = rule.read_text()
    assert "0.55" in txt and "DEAD" in txt and "ALIVE" in txt
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch",
                              PP.P3_RULE_DOC], capture_output=True)
    assert tracked.returncode == 0, "the read rule must be COMMITTED, not just written"


def test_p3_is_walled_off_from_the_capture_statistic():
    """PLAN.md §9.2's rail, enforced in code: P3 may never emit a capture number."""
    src = Path(PP.__file__).read_text()
    body = src[src.index("def p3_feature_informativeness"):
               src.index("def cmd_preflight")]
    for banned in ("aggregate_picker", "paired_ratio_bootstrap", "price_picks",
                   "F_lo", "F_hi"):
        assert banned not in body, f"P3 must not touch {banned} — it is not a capture read"
    assert "DIAGNOSTIC" in PP.p3_feature_informativeness.__doc__.upper()


def test_free_tier_carries_the_plan_s_honesty_rails_verbatim():
    assert "CANCEL EXACTLY" in PP.R1_COLLINEARITY_NOTE
    assert "collinear" in PP.R1_COLLINEARITY_NOTE
    assert "10-15%" in PP.FREE_TIER_PRIOR
    assert "POWERED KILL" in PP.FREE_TIER_PRIOR
    src = Path(PP.__file__).read_text()
    body = src[src.index("def cmd_preflight"):]
    for rail in ("CEILING_CAVEAT", "R1_COLLINEARITY_NOTE", "NET_ASYMMETRY_CAVEAT",
                 "FREE_TIER_PRIOR"):
        assert rail in body, f"cmd_preflight must carry {rail} into its artifact"


@share_only
def test_preflight_reproduces_stage0_s_own_inner_cv_folds(real_inputs):
    """The P3 CONTROL. The arbiter-label arm re-runs stage-0's fit; if it does not
    reproduce GRADE_net.json's per-fold inner-CV accuracies, P3 is void."""
    pre = json.loads((REPO / "measurement/tienet_stage1_plan_20260823"
                      / "PREFLIGHT.json").read_text())
    published = json.loads(
        (REPO / "measurement/tiletie_probe_20260822/GRADE_net.json").read_text()
    )["witnesses"]["net_model"]["folds"]
    want = sorted(f["inner_cv_acc"] for f in published if f.get("inner_cv_acc"))
    got = sorted(pre["P3"]["arms"]["arbiter"]["inner_cv_acc_folds"])
    assert len(got) == len(want)
    for a, b in zip(got, want):
        assert abs(a - b) < 5e-4, (got, want)
    assert pre["P3"]["control"]["ok"] is True
