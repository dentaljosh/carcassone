#!/usr/bin/env python3
"""ARBCOST component (ii) — flip-weighted racing + arm-pruning simulation.

Exact offline replay over the BANKED CRN per-world margin matrices of
measurement/tiearb_widening_20260817/rung3_r5 (6,602 pairs / 1,060 positions, m=32).
No playouts are run. See PREREG.md section 3.4.

Emits: RACING_SIM.json
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BASE = os.path.join(REPO, "measurement/tiearb_widening_20260817/rung3_r5")

Z_THRESHOLDS = [1.5, 2.0, 2.5, 3.0]
T_START = 4                      # PREREG 3.4: first check at t = 4 worlds
PRUNE_CHECKPOINTS = (8, 16)      # PREREG 3.4
BOOT_REPS = 2000
BOOT_SEED = 20260819


# --------------------------------------------------------------------------- #
def load_matrices():
    """rid -> (arm_actions, M[arms x m], meta). Star-of-pairs reconstruction."""
    arms_meta = json.load(open(os.path.join(
        BASE, "corpus/positions_s2/ARMS.json")))
    pairs = defaultdict(dict)
    va_by_rid = {}
    diag = {"n_record_files": 0, "bad_per_world_delta": 0,
            "values_a_inconsistent_rids": 0, "world_seeds_inconsistent_rids": 0}
    seeds_by_rid = defaultdict(set)
    va_seen = defaultdict(set)
    for f in glob.glob(os.path.join(
            BASE, "legs/s2/tier1-greedy/walled/leg*/records/*.json")):
        d = json.load(open(f))
        diag["n_record_files"] += 1
        va = np.asarray(d["values_a"], dtype=float)
        vb = np.asarray(d["values_b"], dtype=float)
        pwd = np.asarray(d["per_world_delta"], dtype=float)
        if not np.allclose(pwd, vb - va, atol=1e-9):
            diag["bad_per_world_delta"] += 1
            continue
        rid = d["rid"]
        va_seen[rid].add(tuple(va))
        seeds_by_rid[rid].add(tuple(d["world_seeds"]))
        pairs[rid][d["pick_b"]] = vb
        va_by_rid[rid] = va
    diag["values_a_inconsistent_rids"] = sum(1 for v in va_seen.values() if len(v) > 1)
    diag["world_seeds_inconsistent_rids"] = sum(
        1 for v in seeds_by_rid.values() if len(v) > 1)
    out = {}
    for rid, d in pairs.items():
        meta = arms_meta.get(rid)
        if meta is None or rid in {r for r, v in va_seen.items() if len(v) > 1}:
            continue
        acts = meta["arms"]
        rows, kept = [va_by_rid[rid]], [acts[0]]
        for a in acts[1:]:
            if a in d:
                rows.append(d[a])
                kept.append(a)
        M = np.vstack(rows)
        out[rid] = (kept, M, meta)
    diag["n_rids"] = len(out)
    diag["falsifier_2_rate"] = diag["bad_per_world_delta"] / max(
        1, diag["n_record_files"])
    diag["falsifier_3_fired"] = bool(diag["values_a_inconsistent_rids"])
    return out, diag


def deployed_subset(kept, M, meta):
    """The deployed J=4 arm set (ARMS.json::subset_j4), as rows of M."""
    idx = {a: i for i, a in enumerate(kept)}
    sel = [idx[a] for a in meta["subset_j4"] if a in idx]
    if len(sel) < 2:
        return None
    return M[sel, :]


# --------------------------------------------------------------------------- #
def _leader_pair(run_sum, t):
    means = run_sum / t
    order = np.argsort(-means, kind="stable")
    return int(order[0]), int(order[1])


def simulate(M, z, prune: bool):
    """Return (playouts_used, decision_arm, n_worlds_used).

    Worlds are consumed in banked order. Every world consumed costs one playout
    per ACTIVE arm (CRN: one determinization shared by all arms).
    Racing statistic (PREREG 3.4): leader-vs-runner-up paired margin
    d_bar_t / (sd_t/sqrt(t)), ddof=1, first check at t = T_START.
    Pruning (variant): at t in PRUNE_CHECKPOINTS drop every arm whose paired
    deficit behind the leader clears the same z.
    """
    A, m = M.shape
    active = list(range(A))
    playouts = 0
    run_sum = np.zeros(A)
    run_sq = np.zeros((A, A))        # not needed; paired sd computed from slices
    for t in range(1, m + 1):
        playouts += len(active)
        run_sum[active] += M[active, t - 1]
        if t < T_START or len(active) < 2:
            continue
        sub = M[np.ix_(active, range(t))]
        means = sub.mean(axis=1)
        order = np.argsort(-means, kind="stable")
        lead = active[order[0]]
        # prune trailing arms at the checkpoints
        if prune and t in PRUNE_CHECKPOINTS and len(active) > 2:
            keep = [lead]
            for oi in order[1:]:
                a = active[oi]
                dpair = M[lead, :t] - M[a, :t]
                sd = dpair.std(ddof=1) if t > 1 else 0.0
                se = sd / np.sqrt(t) if sd > 0 else 0.0
                if se > 0 and (dpair.mean() / se) >= z:
                    continue          # convincingly behind -> drop
                keep.append(a)
            active = sorted(keep)
            if len(active) < 2:
                return playouts, lead, t
            sub = M[np.ix_(active, range(t))]
            means = sub.mean(axis=1)
            order = np.argsort(-means, kind="stable")
            lead = active[order[0]]
        runner = active[order[1]] if len(active) > 1 else None
        if runner is None:
            return playouts, lead, t
        dpair = M[lead, :t] - M[runner, :t]
        sd = dpair.std(ddof=1) if t > 1 else 0.0
        if sd > 0 and (dpair.mean() / (sd / np.sqrt(t))) >= z:
            return playouts, lead, t
        if sd == 0 and dpair.mean() > 0:
            return playouts, lead, t
    return playouts, int(np.argmax(M.mean(axis=1))), m


def reference(M):
    means = M.mean(axis=1)
    return int(np.argsort(-means, kind="stable")[0]), means


# --------------------------------------------------------------------------- #
class RootBoot:
    """Root bootstrap over rids (one position per root here: rid == cluster)."""

    def __init__(self, keys, reps=BOOT_REPS, seed=BOOT_SEED):
        self.keys = list(keys)
        self.g = len(self.keys)
        rng = np.random.default_rng(seed)
        self.idx = rng.integers(0, self.g, size=(reps, self.g))

    def ci(self, vec):
        v = np.asarray(vec, dtype=float)
        reps = v[self.idx].mean(axis=1)
        srt = np.sort(reps)
        n = srt.size
        return {"value": float(v.mean()),
                "ci95": [float(srt[int(0.025 * n)]),
                         float(srt[min(n - 1, int(0.975 * n))])],
                "se": float(srt.std(ddof=1))}


def run_block(mats, rids, arm_mode, prune, boot):
    """One (arm_mode, prune) block over the given rids, all z thresholds."""
    block = {}
    for z in Z_THRESHOLDS:
        frac, flip, loss, wu = [], [], [], []
        b64_hi, b64_lo, stopped = [], [], []
        for rid in rids:
            kept, M, meta = mats[rid]
            X = deployed_subset(kept, M, meta) if arm_mode == "j4" else M
            if X is None or X.shape[0] < 2:
                continue
            A, m = X.shape
            ref, means = reference(X)
            p, dec, t = simulate(X, z, prune)
            frac.append(p / (A * m))
            f = int(dec != ref)
            flip.append(f)
            loss.append(float(means[ref] - means[dec]) if f else 0.0)
            wu.append(t / m)
            # --- B=64 BRACKET (see PREREG-declared transfer caveat, extended).
            # A z-threshold on a paired mean fires at an ABSOLUTE world index that
            # does not depend on the budget; only the denominator changes. For a
            # position that fired at t < m the same t applies at B=64 => t/64.
            # For a position that never fired by m=32 the true fire index is > 32
            # and <= 64 (or never): UPPER = 64/64 = 1.0, LOWER = 32/64.
            fired = t < m
            stopped.append(int(fired))
            b64_hi.append((t if fired else 2 * m) / (2 * m))
            b64_lo.append((t if fired else m) / (2 * m))
        block[f"z{z}"] = {
            "n_positions": len(frac),
            "playout_fraction": boot.ci(frac),
            "worlds_used_fraction": boot.ci(wu),
            "sign_flip_rate": boot.ci(flip),
            "capture_weighted_loss_arbiter_currency": boot.ci(loss),
            "fired_before_m_rate": boot.ci(stopped),
            "b64_worlds_fraction_upper_bound": boot.ci(b64_hi),
            "b64_worlds_fraction_lower_bound": boot.ci(b64_lo),
        }
    return block


def main():
    mats, diag = load_matrices()
    phase = {rid: mats[rid][2]["phase_bucket"] for rid in mats}
    all_rids = sorted(mats)
    midlate = [r for r in all_rids if phase[r] in ("mid", "late")]
    early = [r for r in all_rids if phase[r] == "early"]

    out = {
        "artifact": "RACING_SIM",
        "prereg": "measurement/arb_costopt_prep/PREREG.md",
        "generated_by": "measurement/arb_costopt_prep/racing_sim.py",
        "source": ("measurement/tiearb_widening_20260817/rung3_r5/legs/s2/"
                   "tier1-greedy/walled/leg*/records/*.json + "
                   "corpus/positions_s2/ARMS.json"),
        "m_worlds": 32,
        "deployed_B": 64,
        "transfer_caveat": ("the banked matrices carry m=32 CRN worlds; the DEPLOYED "
                            "arbiter runs B=64. Fractions transfer approximately: at "
                            "B=64 the running SE shrinks faster, so a z-threshold "
                            "fires at a SMALLER world index and the fraction quoted "
                            "here is an UPPER bound on the B=64 fraction."),
        "stratum_caveat": ("every rid is capped_at_4=true (n_arms >= 5) -- the "
                           "J-widening stratum, NOT the deployment arm mix "
                           "(deployed Abar = 3.0022). Arm-count-sensitive quantities "
                           "(pruning gain) are therefore OPTIMISTIC vs deployment."),
        "loss_currency_label": ("capture_weighted_loss is |full-m mean margin between "
                                "the reference arm and the arm actually chosen|, in "
                                "the ARBITER'S OWN tier1-greedy terminal-playout "
                                "points. It is NOT judge-priced capture and is NOT "
                                "commensurable with PHASE_B_CAPTURE.json numbers."),
        "rule": {"first_check_t": T_START, "z_thresholds": Z_THRESHOLDS,
                 "prune_checkpoints": list(PRUNE_CHECKPOINTS),
                 "statistic": "leader-vs-runner-up paired margin, ddof=1",
                 "world_order": "banked order (world_seeds as recorded)"},
        "diagnostics": diag,
        "phase_counts": dict(Counter(phase.values())),
    }

    boot_all = RootBoot(all_rids)
    boot_ml = RootBoot(midlate)
    boot_e = RootBoot(early)

    for arm_mode in ("j4", "full"):
        for prune in (False, True):
            tag = f"{arm_mode}_{'prune' if prune else 'race'}"
            out[tag] = {
                "ALL": run_block(mats, all_rids, arm_mode, prune, boot_all),
                "MIDLATE": run_block(mats, midlate, arm_mode, prune, boot_ml),
                "EARLY": run_block(mats, early, arm_mode, prune, boot_e),
            }

    # --- per-phase noise profile: why racing is WORSE early, not better -------
    noise = {}
    for name, rr in (("ALL", all_rids), ("early", early),
                     ("mid", [r for r in all_rids if phase[r] == "mid"]),
                     ("late", [r for r in all_rids if phase[r] == "late"])):
        sds, gaps, snr, plies = [], [], [], []
        for rid in rr:
            kept, M, meta = mats[rid]
            X = deployed_subset(kept, M, meta)
            if X is None or X.shape[0] < 2:
                continue
            means = X.mean(axis=1)
            o = np.argsort(-means, kind="stable")
            dpair = X[o[0]] - X[o[1]]
            sd = float(dpair.std(ddof=1))
            g = float(means[o[0]] - means[o[1]])
            sds.append(sd)
            gaps.append(g)
            if sd > 0:
                snr.append(g / sd)
        noise[name] = {
            "n": len(sds),
            "mean_paired_sd_top2": float(np.mean(sds)),
            "mean_top2_gap": float(np.mean(gaps)),
            "mean_snr_gap_over_sd": float(np.mean(snr)),
            "median_snr_gap_over_sd": float(np.median(snr)),
        }
    out["paired_noise_profile_j4"] = noise
    out["paired_noise_note"] = (
        "racing fires on gap/sd, not gap. EARLY has the LARGEST gaps AND the "
        "largest per-world sd; the ratio is what decides, and it is worst early. "
        "=> racing and the phase gate are COMPLEMENTS, not substitutes.")

    # playout-length profile by phase (feeds the cost model)
    plies = defaultdict(list)
    for f in glob.glob(os.path.join(
            BASE, "legs/s2/tier1-greedy/walled/leg*/records/*.json")):
        d = json.load(open(f))
        meta = json.load
        ph = None
        rid = d["rid"]
        if rid in mats:
            ph = mats[rid][2]["phase_bucket"]
        if ph is None:
            continue
        pl = list(d["playout_plies_a"]) + list(d["playout_plies_b"])
        plies[ph].append(float(np.mean(pl)))
        plies["ALL"].append(float(np.mean(pl)))
    out["playout_plies_by_phase"] = {
        k: {"n_records": len(v), "mean_plies": float(np.mean(v))}
        for k, v in plies.items()}

    # arm-count profile for the transfer caveat
    n_arms = Counter(len(mats[r][0]) for r in all_rids)
    out["arm_counts_full"] = dict(sorted(n_arms.items()))
    out["mean_arms_full"] = float(np.mean([len(mats[r][0]) for r in all_rids]))
    out["mean_arms_j4"] = float(np.mean(
        [deployed_subset(*mats[r]).shape[0] for r in all_rids
         if deployed_subset(*mats[r]) is not None]))

    dst = os.path.join(HERE, "RACING_SIM.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote", dst)


if __name__ == "__main__":
    main()
