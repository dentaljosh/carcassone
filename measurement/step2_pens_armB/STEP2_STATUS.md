# Step-2 PeNS Weaned Flywheel — LIVE STATUS

**State:** RUNNING
**Updated:** 2026-06-30T13:29:13Z
**Arm:** B (treatment: blend annealed, dropout rising) · **Tag:** step2_pens_armB

iter 6 IN PROGRESS — blend=0.55 dropout=0.17. Completed: 5. Stage: gen.

---
- Leaf value: (1-blend)*h_v2.9 + blend*scalar_mlp(feat89); blend/dropout scheduled per iter.
- Recipe: GAMES 250 · SIMS 100 · policy-epochs 3 · value-epochs 6 · batch 256 · VLW 1.5 · eval_n 80
- Seeds: policy=iter_02.pt scalar=warmstart.pt; eval-ref=iter_02.pt
- Cluster: LOCAL-ONLY
- MEASUREMENT/EXPLORATORY — no promotion, PRODUCTION.yaml/champion/v2.7/v2.9 UNCHANGED.
