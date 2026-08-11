# Part D — root-action deeper-search audit (1620 positions)

## Search sharpness by depth (mean over all positions)
agent | mean_entropy(nats) | mean_top_share | mean_chosen_share | mean_n_children
--- | --- | --- | --- | ---
h3200 | 3.519 | 0.051 | 0.051 | 38.2
h6400 | 3.494 | 0.062 | 0.062 | 38.2
h12800 | 3.445 | 0.079 | 0.079 | 38.2
rod1 | 2.572 | 0.270 | 0.196 | 26.8

## Pairwise top-1 agreement (overall | by phase)
pair | overall | opening | midgame | late_mid | pre_endgame | endgame
--- | --- | --- | --- | --- | --- | ---
h3200~h6400 | 0.743 | 0.84 | 0.73 | 0.74 | 0.71 | 0.71
h6400~h12800 | 0.765 | 0.78 | 0.78 | 0.76 | 0.75 | 0.76
h3200~h12800 | 0.715 | 0.77 | 0.69 | 0.73 | 0.70 | 0.70
rod1~h3200 | 0.515 | 0.66 | 0.56 | 0.56 | 0.50 | 0.39
rod1~h6400 | 0.516 | 0.64 | 0.54 | 0.56 | 0.51 | 0.40
rod1~h12800 | 0.503 | 0.62 | 0.51 | 0.53 | 0.52 | 0.40

## Stability of h3200->h6400->h12800 choice chain
- agree3 (search saturated):  1070/1620 (66%)
- converged (deep STABLE new decision: h6400!=h3200, h12800==h6400):  169/1620 (10%)
- unstable (all three differ = noise):  160/1620 (10%)
- partial (other):  221/1620 (14%)

by phase: opening[16c/14u/270]  midgame[37c/22u/270]  late_mid[25c/28u/270]  pre_endgame[38c/46u/360]  endgame[53c/50u/450]

## Learned (RoD1) placement vs the ladder
- RoD1 == h3200 but != h6400 (stuck at shallow ceiling): 82
- RoD1 == h6400 but != h3200 (already deep): 83
- RoD1 == both (h3200==h6400 anyway): 753
- RoD1 == neither: 702

## Deep disagreements (h12800 != h3200)
- total: 462/1620  (29% of positions)
- **CONVERGED (h6400==h12800 != h3200 = stable deeper-search preference): 169/462**
  by phase: opening:16, midgame:37, late_mid:25, pre_endgame:38, endgame:53
- RoD1 sides WITH the deep move on these: 86/462
- written: measurement/deeper_search_ruler/root_audit/disagreements.csv

