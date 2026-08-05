# RoD v2.8 Overnight Flywheel — Training Log Summary

> Appended per iteration by `scripts/rod_v28/overnight_iter_screen.py`. MEASUREMENT ONLY. Cheap screens are catastrophe detectors, **not strength verdicts** (real evals run tomorrow on selected checkpoints).

## iter_00  (warm-from warmstart_canonical)  —  **HEALTHY**

- ckpt `8db88bdb59f1…` (30083965 B) · code `54fe12fbe97e`
- gen: 600/600 npz, 193.5 min · train: 966 steps, 2.6 min (metrics 2.3)
- train_pol [1.7845, 1.6949, 1.6556] · val_pol [1.753, 1.7493, 1.7588] · train_val [0.3864, 0.3431, 0.2637]
- policy_entropy 1.6949 (baseline 1.6351, floor 0.8175) · value_corr 0.3128
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_01  (warm-from iter_00)  —  **HEALTHY**

- ckpt `97d239c436c6…` (30083965 B) · code `04b951ffdcd9`
- gen: 600/600 npz, 192.7 min · train: 1926 steps, 5.1 min (metrics 4.7)
- train_pol [1.6961, 1.6587, 1.632] · val_pol [1.7183, 1.7168, 1.7219] · train_val [0.3201, 0.2505, 0.1737]
- policy_entropy 1.6561 (baseline 1.6351, floor 0.8175) · value_corr 0.5394
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_02  (warm-from iter_01)  —  **HEALTHY**

- ckpt `1099eb5a0839…` (30083965 B) · code `2b550fa66d7d`
- gen: 600/600 npz, 194.1 min · train: 2886 steps, 7.4 min (metrics 6.9)
- train_pol [1.6695, 1.6376, 1.613] · val_pol [1.6759, 1.6773, 1.6749] · train_val [0.2794, 0.1958, 0.1408]
- policy_entropy 1.6317 (baseline 1.6351, floor 0.8175) · value_corr 0.5578
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_03  (warm-from iter_02)  —  **HEALTHY**

- ckpt `72639a92b0fa…` (30083965 B) · code `01e675331562`
- gen: 600/600 npz, 198.7 min · train: 3846 steps, 9.8 min (metrics 9.2)
- train_pol [1.6368, 1.6135, 1.5972] · val_pol [1.6574, 1.6621, 1.6702] · train_val [0.2363, 0.1571, 0.1222]
- policy_entropy 1.621 (baseline 1.6351, floor 0.8175) · value_corr 0.7036
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_04  (warm-from iter_03)  —  **HEALTHY**

- ckpt `3de78cbe96b6…` (30083965 B) · code `40a3acd11db4`
- gen: 300/300 npz, 84.0 min · train: 4329 steps, 11.2 min (metrics 10.5)
- train_pol [1.6009, 1.5866, 1.5803] · val_pol [1.6165, 1.6239, 1.6361] · train_val [0.1766, 0.1149, 0.0965]
- policy_entropy 1.6069 (baseline 1.6351, floor 0.8175) · value_corr 0.7544
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_05  (warm-from iter_04)  —  **HEALTHY**

- ckpt `1a40f2640503…` (30083965 B) · code `8f228d1265cd`
- gen: 300/300 npz, 123.2 min · train: 4809 steps, 12.3 min (metrics 11.7)
- train_pol [1.5862, 1.5759, 1.5689] · val_pol [1.6052, 1.6079, 1.622] · train_val [0.1528, 0.0969, 0.0834]
- policy_entropy 1.5922 (baseline 1.6351, floor 0.8175) · value_corr 0.8339
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_06  (warm-from iter_05)  —  **HEALTHY**

- ckpt `6dfe737140de…` (30084029 B) · code `f4f276af0e59`
- gen: 300/300 npz, 80.5 min · train: 5289 steps, 13.5 min (metrics 12.8)
- train_pol [1.5742, 1.5657, 1.5615] · val_pol [1.5851, 1.5922, 1.5953] · train_val [0.1309, 0.0834, 0.0752]
- policy_entropy 1.5893 (baseline 1.6351, floor 0.8175) · value_corr 0.8309
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_07  (warm-from iter_06)  —  **HEALTHY**

- ckpt `7171a6bdd887…` (30084029 B) · code `389fd3c0b434`
- gen: 300/300 npz, 65.3 min · train: 5772 steps, 14.8 min (metrics 13.9)
- train_pol [1.5675, 1.56, 1.5572] · val_pol [1.5808, 1.5841, 1.5946] · train_val [0.1264, 0.0752, 0.0696]
- policy_entropy 1.5804 (baseline 1.6351, floor 0.8175) · value_corr 0.8491
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_08  (warm-from iter_07)  —  **HEALTHY**

- ckpt `42d27f96af81…` (30084029 B) · code `56cae6bddc58`
- gen: 300/300 npz, 107.1 min · train: 6249 steps, 15.9 min (metrics 15.1)
- train_pol [1.5622, 1.5553, 1.5531] · val_pol [1.5729, 1.5772, 1.5845] · train_val [0.1153, 0.069, 0.0652]
- policy_entropy 1.598 (baseline 1.6351, floor 0.8175) · value_corr 0.8859
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_09  (warm-from iter_08)  —  **HEALTHY**

- ckpt `31a714a78182…` (30084029 B) · code `c8fc56cc9032`
- gen: 300/300 npz, 67.3 min · train: 6732 steps, 17.2 min (metrics 16.3)
- train_pol [1.5591, 1.553, 1.5511] · val_pol [1.5597, 1.5621, 1.5676] · train_val [0.1064, 0.0646, 0.0604]
- policy_entropy 1.5736 (baseline 1.6351, floor 0.8175) · value_corr 0.8659
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_10  (warm-from iter_09)  —  **HEALTHY**

- ckpt `91d8e3a22fa8…` (30084029 B) · code `b8404c673d53`
- gen: 300/300 npz, 66.3 min · train: 7212 steps, 18.4 min (metrics 17.7)
- train_pol [1.5565, 1.5508, 1.5493] · val_pol [1.5583, 1.5626, 1.566] · train_val [0.104, 0.0615, 0.0587]
- policy_entropy 1.53 (baseline 1.6351, floor 0.8175) · value_corr 0.885
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_11  (warm-from iter_10)  —  **HEALTHY**

- ckpt `0275c696a6d7…` (30084029 B) · code `5e292f5e5a50`
- gen: 300/300 npz, 65.7 min · train: 7692 steps, 19.6 min (metrics 18.6)
- train_pol [1.5526, 1.5474, 1.5463] · val_pol [1.5546, 1.5572, 1.5618] · train_val [0.0987, 0.0583, 0.0559]
- policy_entropy 1.5656 (baseline 1.6351, floor 0.8175) · value_corr 0.8877
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_12  (warm-from iter_11)  —  **HEALTHY**

- ckpt `a12bdee49f53…` (30084029 B) · code `8f4b0e3ee0f4`
- gen: 300/300 npz, 112.2 min · train: 7212 steps, 18.4 min (metrics 17.4)
- train_pol [1.5531, 1.5479, 1.5467] · val_pol [1.5566, 1.5575, 1.5622] · train_val [0.0985, 0.0572, 0.0563]
- policy_entropy 1.5293 (baseline 1.6351, floor 0.8175) · value_corr 0.8928
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_13  (warm-from iter_12)  —  **HEALTHY**

- ckpt `86b73ae20235…` (30084029 B) · code `6db7f67e5023`
- gen: 300/300 npz, 65.3 min · train: 6732 steps, 17.1 min (metrics 16.2)
- train_pol [1.5521, 1.5472, 1.5462] · val_pol [1.5644, 1.5658, 1.57] · train_val [0.0959, 0.0547, 0.0524]
- policy_entropy 1.5663 (baseline 1.6351, floor 0.8175) · value_corr 0.896
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_14  (warm-from iter_13)  —  **HEALTHY**

- ckpt `85f589096eae…` (30084029 B) · code `ff20977364d7`
- gen: 300/300 npz, 68.4 min · train: 6249 steps, 16.0 min (metrics 15.1)
- train_pol [1.5545, 1.5497, 1.5486] · val_pol [1.5505, 1.5505, 1.5543] · train_val [0.1008, 0.054, 0.0507]
- policy_entropy 1.5423 (baseline 1.6351, floor 0.8175) · value_corr 0.9107
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_15  (warm-from iter_14)  —  **HEALTHY**

- ckpt `010414447b2f…` (30084029 B) · code `6b955f028802`
- gen: 300/300 npz, 66.3 min · train: 5772 steps, 14.7 min (metrics 13.9)
- train_pol [1.5536, 1.5497, 1.5494] · val_pol [1.5665, 1.5655, 1.5668] · train_val [0.1006, 0.0529, 0.0495]
- policy_entropy 1.5397 (baseline 1.6351, floor 0.8175) · value_corr 0.9031
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_16  (warm-from iter_15)  —  **HEALTHY**

- ckpt `0c854d742d49…` (30084029 B) · code `4ae5bc061b2b`
- gen: 300/300 npz, 69.4 min · train: 5771 steps, 14.7 min (metrics 13.9)
- train_pol [1.5447, 1.5413, 1.5407] · val_pol [1.5498, 1.5495, 1.5511] · train_val [0.0983, 0.0506, 0.0484]
- policy_entropy 1.5303 (baseline 1.6351, floor 0.8175) · value_corr 0.8887
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_17  (warm-from iter_16)  —  **HEALTHY**

- ckpt `c2902d05c945…` (30084029 B) · code `bbe531d18682`
- gen: 300/300 npz, 111.2 min · train: 5771 steps, 14.7 min (metrics 13.9)
- train_pol [1.5372, 1.5333, 1.5371] · val_pol [1.5416, 1.5394, 1.5541] · train_val [0.1046, 0.0511, 0.0473]
- policy_entropy 1.5079 (baseline 1.6351, floor 0.8175) · value_corr 0.8999
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_18  (warm-from iter_17)  —  **HEALTHY**

- ckpt `6cd68618e0da…` (30084029 B) · code `835272a20948`
- gen: 300/300 npz, 66.4 min · train: 5772 steps, 14.7 min (metrics 13.9)
- train_pol [1.53, 1.5264, 1.5256] · val_pol [1.5324, 1.5315, 1.5336] · train_val [0.0987, 0.0503, 0.0464]
- policy_entropy 1.5283 (baseline 1.6351, floor 0.8175) · value_corr 0.9018
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_19  (warm-from iter_18)  —  **HEALTHY**

- ckpt `d0bfd921cf17…` (30084029 B) · code `cca9c93c5f84`
- gen: 300/300 npz, 68.4 min · train: 5772 steps, 14.7 min (metrics 13.9)
- train_pol [1.5257, 1.5249, 1.5207] · val_pol [1.5193, 1.5056, 1.5084] · train_val [0.0967, 0.0512, 0.0414]
- policy_entropy 1.5156 (baseline 1.6351, floor 0.8175) · value_corr 0.8892
- **Smoke:** not run / no games
- screens: all cheap screens nominal

## iter_20  (warm-from iter_19)  —  **HEALTHY**

- ckpt `c929b2096c0b…` (30084029 B) · code `e7fa4f459035`
- gen: 300/300 npz, 78.5 min · train: 5772 steps, 14.8 min (metrics 13.9)
- train_pol [1.52, 1.5164, 1.5165] · val_pol [1.5274, 1.5271, 1.5297] · train_val [0.0959, 0.0488, 0.0459]
- policy_entropy 1.5203 (baseline 1.6351, floor 0.8175) · value_corr 0.9147
- **Smoke:** not run / no games
- screens: all cheap screens nominal

