# RoD v2.8 Overnight Flywheel — Training Log Summary

> Appended per iteration by `scripts/rod_v28/overnight_iter_screen.py`. MEASUREMENT ONLY. Cheap screens are catastrophe detectors, **not strength verdicts** (real evals run tomorrow on selected checkpoints).

## iter_00  (warm-from warmstart_canonical)  —  **HEALTHY**

- ckpt `25f2aacfaa98…` (29694845 B) · code `abcab194adb4`
- gen: 600/600 npz, 192.4 min · train: 966 steps, 2.5 min (metrics 2.3)
- train_pol [1.8208, 1.7088, 1.6558] · val_pol [1.7811, 1.7574, 1.7601] · train_val [0.394, 0.3818, 0.3715]
- policy_entropy 1.7092 (baseline 1.6475, floor 0.8237) · value_corr 0.3544
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_01  (warm-from iter_00)  —  **HEALTHY**

- ckpt `95761a6155d9…` (29694845 B) · code `abcab194adb4`
- gen: 600/600 npz, 194.5 min · train: 1926 steps, 4.9 min (metrics 4.5)
- train_pol [1.6881, 1.6419, 1.6146] · val_pol [1.6945, 1.7064, 1.7059] · train_val [0.3751, 0.3656, 0.3486]
- policy_entropy 1.6611 (baseline 1.6475, floor 0.8237) · value_corr 0.3905
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_02  (warm-from iter_01)  —  **HEALTHY**

- ckpt `ad205e82e69a…` (29694845 B) · code `54fe12fbe97e`
- gen: 600/600 npz, 189.3 min · train: 2886 steps, 7.3 min (metrics 6.8)
- train_pol [1.6449, 1.6183, 1.6023] · val_pol [1.652, 1.6647, 1.6741] · train_val [0.3638, 0.3346, 0.2934]
- policy_entropy 1.6107 (baseline 1.6475, floor 0.8237) · value_corr 0.4223
- **Smoke:** not run / no games
- screens: all cheap screens nominal

