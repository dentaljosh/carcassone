# SEMANTIC_TEST_REPORT — evaluation-ruler contracts

Generated at code_rev `328594e`. **35/35 passed**, 0 skipped, 0 failed (pytest rc=0).

These deterministic contracts pin the *meaning* of the eval pipeline's
numbers (value sign, tie/farm scoring, phase/turn transitions, FPU,
transposition de-dup, the visit→replay→trainer round trip, mask/index
alignment, and a real-checkpoint proof the v2.7 leaf executes).

| Contract | Test | Status | Time (s) | Note |
|---|---|---|---|---|
| c1 — Higher final score → positive value for that player | `test_c1_higher_score_maps_to_positive_value` | ✅ passed | 0.06 |  |
| c10 — Legal mask shape + policy-index alignment | `test_c10_legal_mask_shape_and_applicability` | ✅ passed | 0.01 |  |
| c11 — Real checkpoint: v2.7 residual leaf actually executes | `test_c11_real_checkpoint_residual_leaf_actually_runs` | ✅ passed | 0.92 |  |
| c2 — Value antisymmetry AND winner-sign mapping (independent) | `test_c2_value_is_antisymmetric` | ✅ passed | 0.42 |  |
| c2 — Value antisymmetry AND winner-sign mapping (independent) | `test_c2_winner_sign_mapping_independent_of_antisymmetry` | ✅ passed | 0.05 |  |
| c3 — Tied-feature scoring pays all tied owners full | `test_c3_tie_distribution_credits_both_scores` | ✅ passed | 0.00 |  |
| c3 — Tied-feature scoring pays all tied owners full | `test_c3_tie_pays_all_tied_owners` | ✅ passed | 0.00 |  |
| c4 — Farm scoring matches deduped reference | `test_c4_farm_points_match_deduped_reference` | ✅ passed | 0.06 |  |
| c5 — tile→meeple transition keeps the acting player | `test_c5_tile_to_meeple_keeps_acting_player` | ✅ passed | 0.04 |  |
| c6 — meeple→tile transition advances the acting player | `test_c6_meeple_to_tile_advances_acting_player` | ✅ passed | 0.04 |  |
| c7 — FPU stored + reorders search (perspective penalty) | `test_c7_fpu_stored_and_reorders_search` | ✅ passed | 0.02 |  |
| c8 — Equivalent-action aliases + visit-mass de-dup (C2) | `test_c8_equivalent_actions_exist_and_visits_dedup` | ✅ passed | 0.01 |  |
| c9 — visit → replay .npz → streaming trainer-load round trip | `test_c9_selfplay_policy_survives_save_and_streaming_load` | ✅ passed | 2.05 |  |
| — | `test_blend_set_but_never_blended_raises` | ✅ passed | 0.00 |  |
| — | `test_build_eval_provenance_structure` | ✅ passed | 0.01 |  |
| — | `test_claims_v1_but_ran_v2_7_raises` | ✅ passed | 0.00 |  |
| — | `test_claims_v2_7_but_ran_v1_raises` | ✅ passed | 0.00 |  |
| — | `test_deck_hash_deterministic_and_seed_sensitive` | ✅ passed | 0.00 |  |
| — | `test_git_commit_and_dirty_shape` | ✅ passed | 0.01 |  |
| — | `test_matched_v2_7_passes` | ✅ passed | 0.00 |  |
| — | `test_missing_counters_for_side_is_not_a_contradiction` | ✅ passed | 0.00 |  |
| — | `test_pure_v2_7_clean_passes` | ✅ passed | 0.00 |  |
| — | `test_pure_v2_7_with_value_leak_raises` | ✅ passed | 0.00 |  |
| — | `test_residual_fired_passes` | ✅ passed | 0.00 |  |
| — | `test_residual_set_but_never_fired_raises` | ✅ passed | 0.00 |  |
| — | `test_seed_guard_accepts_clean_floor` | ✅ passed | 0.00 |  |
| — | `test_seed_guard_rejects_selfplay_namespace` | ✅ passed | 0.00 |  |
| — | `test_sha256_file_matches_hashlib` | ✅ passed | 0.00 |  |
| — | `test_sha256_file_missing_returns_none` | ✅ passed | 0.00 |  |
| — | `test_spec_from_heuristic_mcts_reads_leaf` | ✅ passed | 0.01 |  |
| — | `test_spec_from_neural_mcts_reads_leaf_cfg` | ✅ passed | 0.01 |  |
| — | `test_v25_wrapped_counters_increment_on_call` | ✅ passed | 0.00 |  |
| — | `test_v25_wrapped_residual_counter_increments` | ✅ passed | 0.00 |  |
| — | `test_v2_7_neural_but_leaf_never_ran_raises` | ✅ passed | 0.00 |  |
| — | `test_validate_evaluator_block_never_raises_on_missing_dep` | ✅ passed | 0.01 |  |

_Source suites: tests/test_semantic_eval_contracts.py, tests/test_eval_provenance.py_
