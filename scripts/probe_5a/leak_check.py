#!/usr/bin/env python3
"""Probe §5A diagnostic — is tempo_only's +44.7% an oracle leak?

Correlate each tempo feature with oracle_q (h6400 teacher), referenced against the
leaf's OWN correlation. A tempo feature correlating with oracle NEAR the leaf level
is expected (it is legit board info); one correlating FAR ABOVE the leaf would be a
leak. Vectorized alignment: sort both sides by (game_seed, ply, ordinal)."""
import numpy as np

d = np.load("/home/doctor/carc_step1_gate/dataset_both/aux.npz", allow_pickle=False)
t = np.load("/home/doctor/carc_step1_gate/tempo_5a/tempo_resid.npz", allow_pickle=True)
oq = d["oracle_q"].astype(np.float64); leaf = d["leaf_q"].astype(np.float64)
gs_d, ply_d, gid_d = d["game_seed"], d["ply"], d["group_id"]

# dataset within-group ordinal (rows are group-contiguous) -> i - group_start[i]
n = len(gid_d)
start = np.zeros(n, np.int64)
_, first = np.unique(gid_d, return_index=True)
gstart = {int(gid_d[f]): f for f in first}
ord_d = np.array([i - gstart[int(gid_d[i])] for i in range(n)], np.int64)

# sort keys
kd = np.lexsort((ord_d, ply_d.astype(np.int64), gs_d))
gs_t, ply_t, ci_t = t["game_seed"], t["ply"], t["child_index"]
kt = np.lexsort((ci_t.astype(np.int64), ply_t.astype(np.int64), gs_t))

# verify identical key sequences
assert np.array_equal(gs_d[kd], gs_t[kt]) and np.array_equal(ply_d[kd].astype(np.int64), ply_t[kt].astype(np.int64)) \
    and np.array_equal(ord_d[kd], ci_t[kt].astype(np.int64)), "key mismatch — alignment failed"

oq_s = oq[kd]; leaf_s = leaf[kd]
T = t["tempo"][kt].astype(np.float64)
names = [str(x) for x in t["tempo_names"]]

def corr(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float((a @ b) / (np.sqrt((a @ a) * (b @ b)) + 1e-12))

print(f"aligned rows = {len(oq_s)}")
print(f"  leaf_q vs oracle_q : {corr(leaf_s, oq_s):+.3f}   <-- the leaf's own corr (reference ceiling)")
print("  --- tempo features vs oracle_q ---")
for k, nm in enumerate(names):
    c = corr(T[:, k], oq_s)
    flag = "  <-- EXCEEDS leaf (leak?)" if abs(c) > abs(corr(leaf_s, oq_s)) else ""
    print(f"  {nm:22s} : {c:+.3f}{flag}")
