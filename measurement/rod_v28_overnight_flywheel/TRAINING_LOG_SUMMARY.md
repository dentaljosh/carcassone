# RoD v2.8 Overnight Flywheel — Training Log Summary

> Appended per iteration by `scripts/rod_v28/overnight_iter_screen.py`. MEASUREMENT ONLY. Cheap screens are catastrophe detectors, **not strength verdicts** (real evals run tomorrow on selected checkpoints).

## iter_02  (warm-from RoD_iter_01)  —  **HEALTHY**

- ckpt `325a53b20b23…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 20.8 min · train: 9590 steps, 31.2 min (metrics 30.4)
- train_pol [1.5686, 1.5549, 1.5482] · val_pol [0.2912, 0.2911, 0.2921] · train_val [0.0058, 0.0057, 0.0056]
- policy_entropy 1.5505 (baseline 1.7463, floor 0.8731) · value_corr 0.36
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_02 vs RoD_iter_01 = 6W/12L/0D, wr 0.333, elo -120.4±87 (NOT a verdict)
- screens: all cheap screens nominal

## iter_03  (warm-from RoD_iter_02)  —  **HEALTHY**

- ckpt `0f16cb3da6ee…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 22.0 min · train: 9597 steps, 29.6 min (metrics 28.9)
- train_pol [1.565, 1.5488, 1.5403] · val_pol [0.2564, 0.2569, 0.2572] · train_val [0.0057, 0.0056, 0.0055]
- policy_entropy 1.5475 (baseline 1.7463, floor 0.8731) · value_corr 0.3923
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_03 vs RoD_iter_02 = 7W/11L/0D, wr 0.389, elo -78.5±84 (NOT a verdict)
- screens: all cheap screens nominal

## iter_04  (warm-from RoD_iter_03)  —  **HEALTHY**

- ckpt `45018d6ac461…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 21.9 min · train: 9537 steps, 29.8 min (metrics 29.1)
- train_pol [1.5756, 1.5642, 1.5521] · val_pol [0.276, 0.2762, 0.2769] · train_val [0.0058, 0.0058, 0.0057]
- policy_entropy 1.5863 (baseline 1.7463, floor 0.8731) · value_corr 0.4487
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_04 vs RoD_iter_03 = 8W/10L/0D, wr 0.444, elo -38.8±82 (NOT a verdict)
- screens: all cheap screens nominal

## iter_05  (warm-from RoD_iter_04)  —  **HEALTHY**

- ckpt `5a144c16a786…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 20.8 min · train: 9459 steps, 29.4 min (metrics 28.6)
- train_pol [1.5869, 1.5713, 1.5605] · val_pol [0.2325, 0.2326, 0.2331] · train_val [0.006, 0.0059, 0.0058]
- policy_entropy 1.5513 (baseline 1.7463, floor 0.8731) · value_corr 0.442
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_05 vs RoD_iter_04 = 8W/10L/0D, wr 0.444, elo -38.8±82 (NOT a verdict)
- screens: all cheap screens nominal

## iter_06  (warm-from RoD_iter_05)  —  **HEALTHY**

- ckpt `21e638ea1d40…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 20.8 min · train: 9550 steps, 30.1 min (metrics 29.4)
- train_pol [1.5645, 1.5485, 1.5419] · val_pol [0.2886, 0.289, 0.2896] · train_val [0.0063, 0.0062, 0.0061]
- policy_entropy 1.5558 (baseline 1.7463, floor 0.8731) · value_corr 0.4333
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_06 vs RoD_iter_05 = 5W/12L/1D, wr 0.306, elo -142.6±89 (NOT a verdict)
- screens: all cheap screens nominal

## iter_07  (warm-from RoD_iter_06)  —  **HEALTHY**

- ckpt `ab0a4c8f36c3…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 20.8 min · train: 9546 steps, 30.6 min (metrics 29.8)
- train_pol [1.5719, 1.5595, 1.5513] · val_pol [0.2636, 0.264, 0.2644] · train_val [0.0065, 0.0064, 0.0063]
- policy_entropy 1.5384 (baseline 1.7463, floor 0.8731) · value_corr 0.4103
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_07 vs RoD_iter_06 = 8W/8L/2D, wr 0.500, elo +0.0±82 (NOT a verdict)
- screens: all cheap screens nominal

## iter_08  (warm-from RoD_iter_07)  —  **HEALTHY**

- ckpt `5843b3cf0d17…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 22.0 min · train: 9465 steps, 29.8 min (metrics 29.1)
- train_pol [1.5814, 1.5697, 1.5615] · val_pol [0.2685, 0.2687, 0.2692] · train_val [0.0063, 0.0061, 0.006]
- policy_entropy 1.5941 (baseline 1.7463, floor 0.8731) · value_corr 0.3969
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_08 vs RoD_iter_07 = 9W/7L/2D, wr 0.556, elo +38.8±82 (NOT a verdict)
- screens: all cheap screens nominal

## iter_09  (warm-from RoD_iter_08)  —  **HEALTHY**

- ckpt `58a82fa2dd63…` (29715325 B) · code `fbada68bfae6`
- gen: 400/400 npz, 21.9 min · train: 9488 steps, 29.4 min (metrics 28.7)
- train_pol [1.5791, 1.566, 1.5569] · val_pol [0.316, 0.3158, 0.3172] · train_val [0.0068, 0.0066, 0.0065]
- policy_entropy 1.5536 (baseline 1.7463, floor 0.8731) · value_corr 0.4337
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_09 vs RoD_iter_08 = 7W/11L/0D, wr 0.389, elo -78.5±84 (NOT a verdict)
- screens: all cheap screens nominal

## iter_10  (warm-from RoD_iter_09)  —  **HEALTHY**

- ckpt `559ef7774095…` (29715325 B) · code `077b8edd3585`
- gen: 400/400 npz, 21.9 min · train: 9509 steps, 30.4 min (metrics 29.6)
- train_pol [1.5704, 1.5598, 1.5499] · val_pol [0.2876, 0.2878, 0.2883] · train_val [0.0066, 0.0065, 0.0063]
- policy_entropy 1.5825 (baseline 1.7463, floor 0.8731) · value_corr 0.4519
- **Smoke (n=18, catastrophe detector ONLY):** RoD_iter_10 vs RoD_iter_09 = 7W/10L/1D, wr 0.417, elo -58.5±83 (NOT a verdict)
- screens: all cheap screens nominal

## iter_11  (warm-from RoD_iter_10)  —  **HEALTHY**

- ckpt `074697e1d4ae…` (29715325 B) · code `bdc6c66081c2`
- gen: 400/400 npz, 20.8 min · train: 9424 steps, 28.9 min (metrics 28.2)
- train_pol [1.5973, 1.5843, 1.5758] · val_pol [0.2691, 0.2689, 0.2702] · train_val [0.0058, 0.0057, 0.0056]
- policy_entropy 1.5605 (baseline 1.7463, floor 0.8731) · value_corr 0.4513
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_12  (warm-from RoD_iter_11)  —  **HEALTHY**

- ckpt `6a77feb969fd…` (29715325 B) · code `bdc6c66081c2`
- gen: 400/400 npz, 20.8 min · train: 9433 steps, 29.8 min (metrics 29.1)
- train_pol [1.59, 1.5744, 1.5671] · val_pol [0.3194, 0.3196, 0.3198] · train_val [0.0065, 0.0064, 0.0062]
- policy_entropy 1.589 (baseline 1.7463, floor 0.8731) · value_corr 0.4451
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_13  (warm-from RoD_iter_12)  —  **HEALTHY**

- ckpt `7d69a398af74…` (29715325 B) · code `d368ef52d544`
- gen: 400/400 npz, 0.0 min · train: 9457 steps, 29.7 min (metrics 29.0)
- train_pol [1.5888, 1.5761, 1.5674] · val_pol [0.3152, 0.3151, 0.3177] · train_val [0.0064, 0.0062, 0.0061]
- policy_entropy 1.5049 (baseline 1.7463, floor 0.8731) · value_corr 0.4322
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_14  (warm-from RoD_iter_13)  —  **HEALTHY**

- ckpt `7717648534ce…` (29715325 B) · code `d368ef52d544`
- gen: 400/400 npz, 20.8 min · train: 9653 steps, 30.7 min (metrics 29.9)
- train_pol [1.5388, 1.5263, 1.5179] · val_pol [0.2871, 0.2871, 0.2881] · train_val [0.0071, 0.0069, 0.0068]
- policy_entropy 1.5161 (baseline 1.7463, floor 0.8731) · value_corr 0.4414
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_15  (warm-from RoD_iter_14)  —  **HEALTHY**

- ckpt `f4d7fc1f37b7…` (29715325 B) · code `d368ef52d544`
- gen: 400/400 npz, 20.8 min · train: 9573 steps, 29.7 min (metrics 29.0)
- train_pol [1.5564, 1.5449, 1.5361] · val_pol [0.2772, 0.2771, 0.2772] · train_val [0.0068, 0.0067, 0.0065]
- policy_entropy 1.5573 (baseline 1.7463, floor 0.8731) · value_corr 0.4877
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_16  (warm-from RoD_iter_15)  —  **HEALTHY**

- ckpt `2c261d2f25ec…` (29715325 B) · code `d368ef52d544`
- gen: 400/400 npz, 20.8 min · train: 9521 steps, 31.0 min (metrics 30.0)
- train_pol [1.5658, 1.553, 1.5396] · val_pol [0.2474, 0.2477, 0.2495] · train_val [0.0069, 0.0068, 0.0066]
- policy_entropy 1.4908 (baseline 1.7463, floor 0.8731) · value_corr 0.463
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_17  (warm-from RoD_iter_16)  —  **HEALTHY**

- ckpt `3f2a3b4e0602…` (29715325 B) · code `d368ef52d544`
- gen: 400/400 npz, 20.8 min · train: 9675 steps, 30.3 min (metrics 29.6)
- train_pol [1.5451, 1.5288, 1.5219] · val_pol [0.2471, 0.2475, 0.2477] · train_val [0.0066, 0.0064, 0.0063]
- policy_entropy 1.5658 (baseline 1.7463, floor 0.8731) · value_corr 0.4677
- **Smoke:** not run / no games
- screens: all cheap screens nominal

