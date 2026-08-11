# Step-2 PeNS Weaned Flywheel — LIVE STATUS

**State:** ERROR
**Updated:** 2026-06-30T18:10:37Z
**Arm:** B (treatment: blend annealed, dropout rising) · **Tag:** step2_pens_armBprime

iter 3 gen FAILED (rc=1, npz=2). See logs/gen_local_it3.log.

---
- Leaf value: (1-blend)*h_v2.9 + blend*scalar_mlp(feat89); blend/dropout scheduled per iter.
- In-loop VALUE objective: ranking (arm B': per-group ListNet over in-loop backed-up search-Q).
- Recipe: GAMES 250 · SIMS 100 · policy-epochs 3 · value-epochs 6 · batch 256 · VLW 1.5 · eval_n 200
- Seeds: policy=iter_02.pt scalar=warmstart.pt; eval-ref=iter_02.pt
- Cluster: 2-box (local+laptop) if gen supports --shared-claim, else LOCAL-ONLY
- MEASUREMENT/EXPLORATORY — no promotion, PRODUCTION.yaml/champion/v2.7/v2.9 UNCHANGED.
