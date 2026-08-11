# RoD v2.8 Overnight Flywheel — Training Log Summary

> Appended per iteration by `scripts/rod_v28/overnight_iter_screen.py`. MEASUREMENT ONLY. Cheap screens are catastrophe detectors, **not strength verdicts** (real evals run tomorrow on selected checkpoints).

## iter_00  (warm-from warmstart_canonical)  —  **HEALTHY**

- ckpt `cf9323975965…` (30083901 B) · code `8a0e79dd8184`
- gen: 600/600 npz, 730.0 min · train: 966 steps, 3.4 min (metrics 3.0)
- train_pol [1.7401, 1.6558, 1.6202] · val_pol [1.7083, 1.7039, 1.7139] · train_val [0.4387, 0.3913, 0.2942]
- policy_entropy 1.6726 (baseline 1.6004, floor 0.8002) · value_corr 0.3592
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_01  (warm-from iter_00)  —  **HEALTHY**

- ckpt `4939c6696fa2…` (30083965 B) · code `e58db474ce88`
- gen: 600/600 npz, 768.7 min · train: 1926 steps, 5.0 min (metrics 4.6)
- train_pol [1.6558, 1.62, 1.5959] · val_pol [1.6506, 1.661, 1.6656] · train_val [0.3648, 0.2816, 0.2002]
- policy_entropy 1.6074 (baseline 1.6004, floor 0.8002) · value_corr 0.4319
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_02  (warm-from iter_01)  —  **HEALTHY**

- ckpt `28f6eef7b483…` (30083965 B) · code `e58db474ce88`
- gen: 600/600 npz, 685.5 min · train: 2886 steps, 7.4 min (metrics 7.0)
- train_pol [1.6271, 1.5999, 1.5814] · val_pol [1.627, 1.6378, 1.6386] · train_val [0.3024, 0.2129, 0.1562]
- policy_entropy 1.5808 (baseline 1.6004, floor 0.8002) · value_corr 0.5691
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_03  (warm-from iter_02)  —  **HEALTHY**

- ckpt `6e2679908d79…` (30083965 B) · code `e58db474ce88`
- gen: 600/600 npz, 673.3 min · train: 3846 steps, 9.8 min (metrics 9.3)
- train_pol [1.6026, 1.5792, 1.5611] · val_pol [1.6094, 1.6152, 1.6165] · train_val [0.2609, 0.1708, 0.1359]
- policy_entropy 1.5707 (baseline 1.6004, floor 0.8002) · value_corr 0.6564
- **Smoke:** not run / no games
- screens: all cheap screens nominal

