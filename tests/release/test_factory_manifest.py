"""F1 property: the champion factory manifest == PRODUCTION.yaml intent, is byte-stable,
and its hash constants agree with the authoritative harness/snapshot dialects (no drift,
no copy divergence). The factory is the R1/R7-class runtime guard for the classical
champion; if it can be spoofed the whole audit is worthless."""
import json

import pytest

from carcassonne_ai import champion_factory as cf
from carcassonne_ai import eval_provenance as ep


def test_spec_matches_production_yaml():
    spec = cf.load_production_spec()
    assert spec.champion_id == "puct_priors_v29_bmild_cap8"
    assert (spec.c_puct, spec.tau_p, spec.value_norm) == (1.5, 5.0, 15.0)
    assert spec.leaf_quantize == "float" and spec.final_select == "visits"
    assert (spec.k_dets, spec.sims_per_det) == (4, 688)
    assert spec.exact_max_k == 2
    assert tuple(spec.curve) == cf.CURVE125
    assert (spec.bonus_cap, spec.opp_bonus_cap) == (8.0, 8.0)


def test_fair_manifest_matches_intent():
    m = cf.resolved_manifest("fair")
    assert m["agent_class"] == "FairHeuristicPriorAgent"
    assert m["fair_deploy"] == {
        "k_dets": 4, "sims_per_det": 688, "total_sims": 2752, "exact_max_k": 2,
        "endgame": "marginalized expectiminimax (honest hidden-bag), no alpha-beta"}
    assert m["leaf"]["curve125"] == list(cf.CURVE125)
    assert m["leaf"]["bonus_cap"] == 8.0 and m["leaf"]["value_blend"] == 0.0
    # reuse_tree rides from the YAML but is INERT in fair deploy.
    assert m["search"]["reuse_tree"] is True
    assert m["search"]["reuse_tree_effective"] is False


def test_manifest_byte_stable_across_two_constructions():
    a = cf.make_production_champion("fair", seed=1).manifest
    b = cf.make_production_champion("fair", seed=2).manifest
    # seed does not enter the manifest -> byte-identical (no timestamps either).
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_manifest_hashes_are_the_three_verified_dialects():
    m = cf.resolved_manifest("fair")
    assert m["leaf_hashes"] == {
        "harness_leaf_hash": "a36d2e15a3b3d71d",
        "frozen_config_hash_meeple_k0": "6dfffd57051690f2",
        "frozen_config_hash_meeple_k2": "158f17ff76adaa02",
    }


def test_factory_hashes_agree_with_authoritative_single_sources():
    """The factory constants must equal what the harness (_leaf_hash) and the snapshot
    (_frozen_config_hash) actually compute — point, don't copy: a copy that silently
    drifts is exactly the failure this audit exists to prevent."""
    import dataclasses as dc

    from c5_leaf_override import _leaf_hash
    from snapshot import _frozen_config_hash

    leaf = cf.production_leaf_cfg()
    assert _leaf_hash(leaf) == cf.LEAF_HASH_HARNESS
    assert _frozen_config_hash(dc.replace(leaf, meeple_k=0.0)) == cf.LEAF_HASH_FROZEN_MK0
    assert _frozen_config_hash(leaf) == cf.LEAF_HASH_FROZEN_MK2


def test_leaf_value_panel_is_the_golden():
    m = cf.resolved_manifest("fair")
    assert m["leaf_value_panel"] == {
        "empty_meeples_3v7_float": -6.25, "empty_meeples_7v3_float": 6.25,
        "empty_meeples_0v7_int": -16, "empty_meeples_5v5_float": 0.0}


def test_meeple_dedup_off_leaves_the_manifest_byte_identical():
    """The flag-gated MEEPLE-DEDUP search must be INVISIBLE when off: no manifest key,
    therefore no config_hash / leaf_hash drift and no re-review of the champion."""
    agent = cf.make_production_champion("fair", seed=1)
    assert "meeple_dedup" not in agent.manifest
    assert getattr(agent, "meeple_dedup", None) is None      # = inherit the env flag
    assert json.dumps(agent.manifest, sort_keys=True) == json.dumps(
        cf.resolved_manifest("fair"), sort_keys=True)


def test_meeple_dedup_on_is_stamped_without_moving_any_hash():
    """When on it MUST be visible in the manifest — and it must still not perturb the
    leaf/config hashes, which describe the leaf and the config, not the search mask."""
    off = cf.make_production_champion("fair", seed=1)
    on = cf.make_production_champion("fair", seed=1, meeple_dedup=True)
    assert on.manifest["meeple_dedup"]["enabled"] is True
    assert on.manifest["meeple_dedup"]["source"] == "kwarg"
    assert on.meeple_dedup is True
    assert on.manifest["search"] == off.manifest["search"]
    assert on.manifest["leaf_hashes"] == off.manifest["leaf_hashes"]
    # ... and the ONLY difference is that one added key.
    assert set(on.manifest) - set(off.manifest) == {"meeple_dedup"}
    assert {k: v for k, v in on.manifest.items() if k != "meeple_dedup"} == off.manifest


def test_intra_turn_reuse_off_leaves_the_manifest_byte_identical():
    """The flag-gated C3-INTRA within-turn tree carry must be INVISIBLE when off: no
    manifest key, therefore no config_hash / leaf_hash drift and no re-review."""
    agent = cf.make_production_champion("fair", seed=1)
    assert "intra_turn_reuse" not in agent.manifest
    assert getattr(agent, "intra_reuse", None) is None       # = inherit the env flag
    assert json.dumps(agent.manifest, sort_keys=True) == json.dumps(
        cf.resolved_manifest("fair"), sort_keys=True)


def test_intra_turn_reuse_on_is_stamped_without_moving_any_hash():
    """When on it MUST be visible in the manifest — including the budget semantics, since
    ON does more total work per turn at equal nominal sims and a reader of the manifest
    must not mistake the cell for an equal-work comparison."""
    off = cf.make_production_champion("fair", seed=1)
    on = cf.make_production_champion("fair", seed=1, intra_reuse=True)
    assert on.manifest["intra_turn_reuse"]["enabled"] is True
    assert on.manifest["intra_turn_reuse"]["source"] == "kwarg"
    assert "equal-WALL-CLOCK" in on.manifest["intra_turn_reuse"]["budget_semantics"]
    assert on.intra_reuse is True
    assert on.manifest["search"] == off.manifest["search"]
    assert on.manifest["leaf_hashes"] == off.manifest["leaf_hashes"]
    # ... and the ONLY difference is that one added key.
    assert set(on.manifest) - set(off.manifest) == {"intra_turn_reuse"}
    assert {k: v for k, v in on.manifest.items()
            if k != "intra_turn_reuse"} == off.manifest


def test_exact_budget_omitted_keeps_the_agent_default():
    """Omitting the kwarg must reach the solver with the agent's OWN default — the
    desktop/production path has to stay bit-identical to before the kwarg existed
    (measurement/ANDROID_WALLCLOCK_MEMO_20260728.md lever #1)."""
    from carcassonne_ai.fair_agent import DEFAULT_EXACT_BUDGET

    agent = cf.make_production_champion("fair", seed=1)
    assert DEFAULT_EXACT_BUDGET == 2_000_000       # the figure the memo measured against
    assert agent._exact_budget == 2_000_000
    assert "exact_budget" not in agent.manifest
    assert json.dumps(agent.manifest, sort_keys=True) == json.dumps(
        cf.resolved_manifest("fair"), sort_keys=True)


def test_exact_budget_reaches_the_solver_config():
    """The kwarg must actually bind on the constructed agent — a forward that stopped at
    the factory would leave the phone pinned at 2,000,000 nodes while claiming otherwise."""
    agent = cf.make_production_champion("fair", seed=1, exact_budget=100_000)
    assert agent._exact_budget == 100_000


def test_exact_budget_is_stamped_without_moving_any_hash():
    """Stamped whenever set (unlike dedup/intra it is stamped even though it is expected
    never to fire — the branch where it DOES fire is a PIMC fallback, i.e. a play change),
    and it must not perturb the leaf/config hashes: it bounds the solver, not the leaf."""
    off = cf.make_production_champion("fair", seed=1)
    on = cf.make_production_champion("fair", seed=1, exact_budget=100_000)
    assert on.manifest["exact_budget"]["nodes"] == 100_000
    assert on.manifest["exact_budget"]["default"] == 2_000_000
    assert on.manifest["exact_budget"]["source"] == "kwarg"
    assert "BudgetExceeded" in on.manifest["exact_budget"]["scope"]
    assert on.manifest["search"] == off.manifest["search"]
    assert on.manifest["leaf_hashes"] == off.manifest["leaf_hashes"]
    # ... and the ONLY difference is that one added key.
    assert set(on.manifest) - set(off.manifest) == {"exact_budget"}
    assert {k: v for k, v in on.manifest.items() if k != "exact_budget"} == off.manifest


def test_exact_budget_rejects_clairvoyant_mode():
    """The clairvoyant agent has no endgame solver; accepting the kwarg there would
    silently do nothing (the intra_reuse precedent)."""
    with pytest.raises(ValueError, match="FAIR-mode"):
        cf.make_production_champion("clairvoyant", seed=1, sims=8, verify=False,
                                    exact_budget=100_000)


def test_verify_raises_on_wrong_curve_and_caps():
    import dataclasses as dc
    with pytest.raises(ep.ProvenanceError):
        cf.verify_leaf(dc.replace(cf.production_leaf_cfg(), v29_meeple_curve=cf.CURVE100))
    with pytest.raises(ep.ProvenanceError):
        cf.verify_leaf(dc.replace(cf.production_leaf_cfg(), bonus_cap=5.0))
    with pytest.raises(ep.ProvenanceError):
        cf.verify_leaf(dc.replace(cf.production_leaf_cfg(), value_blend=0.25))


def test_fair_agent_is_the_production_shape():
    agent = cf.make_production_champion("fair", seed=101)
    assert type(agent).__name__ == "FairHeuristicPriorAgent"
    assert agent._sims == 688 and agent._k_dets == 4 and agent._exact_max_k == 2
    assert agent._exact_endgame is True
    assert hasattr(agent, "manifest")


def test_clairvoyant_agent_uses_reuse_tree():
    agent = cf.make_production_champion("clairvoyant", seed=5)
    assert type(agent).__name__ == "HeuristicPriorAgent"
    assert agent.simulations == 2752
    assert agent._reuse_tree is True   # YAML reuse_tree=true is live in clairvoyant mode
    assert agent.manifest["mode"] == "clairvoyant"


def test_yaml_leaf_hash_field_is_a_recorded_dialect():
    """The PRODUCTION.yaml leaf_hash field (whatever the F1 correction set it to) must be
    ONE of the three runtime-verified dialects — never an unreproducible string."""
    spec = cf.load_production_spec()
    assert spec.yaml_leaf_hash in {
        cf.LEAF_HASH_HARNESS, cf.LEAF_HASH_FROZEN_MK0, cf.LEAF_HASH_FROZEN_MK2}
