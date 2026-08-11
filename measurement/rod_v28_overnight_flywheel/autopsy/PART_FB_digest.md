# RoD v2.8 iter_08 autopsy — Part F + Part B(cached) [free, on-disk only]

## Part F — training curves (final-epoch; *value_outcome_corr is the key diagnostic*)

name | VLW | val_pol | val_val | train_own | pol_entropy | value_outcome_corr
--- | --- | --- | --- | --- | --- | ---
PARENT_champ(fw2_it8) | 1.0 | 0.2581 | 0.0041 | 0.0961 | 1.5295 | 0.5101
RoD1(cont_it01) | 1.5 | 0.2699 | 0.0060 | 0.1089 | 1.5429 | 0.4126
ov_it02 | 1.5 | 0.2921 | 0.0073 | 0.0958 | 1.5505 | 0.3600
ov_it03 | 1.5 | 0.2572 | 0.0060 | 0.0964 | 1.5475 | 0.3923
ov_it04 | 1.5 | 0.2769 | 0.0052 | 0.0976 | 1.5863 | 0.4487
ov_it05 | 1.5 | 0.2331 | 0.0053 | 0.0959 | 1.5513 | 0.4420
ov_it06 | 1.5 | 0.2896 | 0.0071 | 0.0976 | 1.5558 | 0.4333
ov_it07 | 1.5 | 0.2644 | 0.0079 | 0.0974 | 1.5384 | 0.4103
ov_it08 | 1.5 | 0.2692 | 0.0078 | 0.0969 | 1.5941 | 0.3969
ov_it09 | 1.5 | 0.3172 | 0.0071 | 0.0939 | 1.5536 | 0.4337
ov_it10 | 1.5 | 0.2883 | 0.0059 | 0.0956 | 1.5825 | 0.4519
ov_it11 | 1.5 | 0.2702 | 0.0060 | 0.0945 | 1.5605 | 0.4513
ov_it12 | 1.5 | 0.3198 | 0.0066 | 0.0947 | 1.5890 | 0.4451
ov_it13 | 1.5 | 0.3177 | 0.0065 | 0.0985 | 1.5049 | 0.4322
ov_it14 | 1.5 | 0.2881 | 0.0063 | 0.0992 | 1.5161 | 0.4414
ov_it15 | 1.5 | 0.2772 | 0.0062 | 0.0966 | 1.5573 | 0.4877
ov_it16 | 1.5 | 0.2495 | 0.0063 | 0.0988 | 1.4908 | 0.4630
ov_it17 | 1.5 | 0.2477 | 0.0079 | 0.0990 | 1.5658 | 0.4677

CSV: measurement/rod_v28_overnight_flywheel/autopsy/training_curves.csv
NOTE: val_pol/val_val are each iter's fit to ITS OWN self-play val split (different distributions) -> compare with care. value_outcome_corr (normalized corr of value head vs game outcome) and pol_entropy are the cross-comparable signals. VLW changed 1.0->1.5 at RoD1 (confounds val_val level).

## Part B (CACHED half) — root-move agreement on 1000 fixed midgame positions
(heur3200 = v2.8 deep ruler; 'rod' = RoD1 = continuation iter_01; 'parent' = champion fw2_it8)
Covers the parent->RoD1 leg ONLY. RoD1->iter08(OV) leg = the one missing label run.

band | n | RoD1≡h3200 | parent≡h3200 | RoD1≡parent | parent≠h3200 | rod_fixed_parent_miss
--- | --- | --- | --- | --- | --- | ---
opening | 200 | 0.540 | 0.585 | 0.770 | 0.415 | 0.045
early_mid | 200 | 0.570 | 0.595 | 0.675 | 0.405 | 0.075
mid | 200 | 0.475 | 0.495 | 0.625 | 0.505 | 0.070
late_mid | 200 | 0.480 | 0.475 | 0.625 | 0.525 | 0.055
pre_endgame | 200 | 0.490 | 0.450 | 0.565 | 0.550 | 0.095
**ALL** | 1000 | 0.511 | 0.520 | 0.652 | 0.480 | 0.068

Of 480 positions where PARENT disagrees with h3200: RoD1 moved TO h3200 in 68 (14.2%) -> the rest RoD1 stayed off-ruler or went elsewhere.
RoD1 diverged from parent on 348/1000 positions (34.8%): TOWARD h3200=68, AWAY from h3200=77, neither=203.  net-toward = -9 (anti-aligned).

ROOT_AUDIT source: measurement/rod_v28_continuation/ROOT_AUDIT_V28.jsonl

Sharpness (teacher_gap_q = h3200 best_Q - 2nd_Q; higher = sharper/more decisive) + n_legal by band:
band | n | mean teacher_gap_q | mean n_legal
--- | --- | --- | ---
opening | 200 | 0.0331 | 22.9
early_mid | 200 | 0.0315 | 28.3
mid | 200 | 0.0268 | 34.8
late_mid | 200 | 0.0240 | 38.5
pre_endgame | 200 | 0.0343 | 40.5