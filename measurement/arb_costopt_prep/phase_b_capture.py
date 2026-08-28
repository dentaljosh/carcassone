#!/usr/bin/env python3
"""ARBCOST component (i) — phase x B capture table with cluster-robust CIs.

Reads ONLY banked artifacts. No playouts, no games. See PREREG.md sections 2, 3.1-3.3.

Emits: PHASE_B_CAPTURE.json
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# --- PREREG 2.1: PHASE_CUTS verbatim from
# scripts/measurement_infra/sample_agreement_roots.py:96, INCLUDING the
# strict-cut fall-through (k==48 and k==24 match no interval -> "late").
PHASE_CUTS = {"early": (48, 10 ** 9), "mid": (24, 48), "late": (-1, 24)}


def phase_bucket(k_remaining: int) -> str:
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k_remaining < hi:
            return name
    return "late"


def k_from_ply(ply: int) -> int:
    """PREREG 2.1 recovery for corpora that do not carry phase_bucket."""
    return 72 - ply // 2


BOOT_REPS = 2000
BOOT_SEED = 20260819
B_LADDER = [1, 2, 4, 8, 16, 32, 64]
PHASES = ["early", "mid", "late"]


class RootBoot:
    """Percentile ROOT bootstrap, ONE shared resample draw.

    Re-implementation of scripts/tiletie/analyze_widening.py::RootBoot so that
    every statistic in this file lives on the same reps x G root-index draw
    (differences and their terms coherent replicate-by-replicate).
    """

    def __init__(self, rows, reps=BOOT_REPS, seed=BOOT_SEED):
        self.rows = list(rows)
        self.reps = int(reps)
        self.roots = sorted({r["root_id"] for r in self.rows})
        self.g = len(self.roots)
        self._pos = {rt: i for i, rt in enumerate(self.roots)}
        if self.g >= 2:
            rng = np.random.default_rng(seed)
            self.idx = rng.integers(0, self.g, size=(self.reps, self.g))
        else:
            self.idx = None

    def _sums(self, key, mask=None):
        s = np.zeros(self.g, dtype=np.float64)
        c = np.zeros(self.g, dtype=np.float64)
        vals = []
        for r in self.rows:
            if mask is not None and not mask(r):
                continue
            v = r.get(key)
            if v is None or v != v:
                continue
            i = self._pos[r["root_id"]]
            s[i] += float(v)
            c[i] += 1.0
            vals.append(float(v))
        return s, c, vals

    def _reps_of(self, key, mask=None):
        s, c, vals = self._sums(key, mask)
        if not vals or self.idx is None:
            return None, vals
        tot = c[self.idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out = s[self.idx].sum(axis=1) / tot
        return out, vals

    @staticmethod
    def _pct(out):
        srt = np.sort(out[np.isfinite(out)])
        n = srt.size
        if n == 0:
            return None, None, None
        lo = float(srt[int(0.025 * n)])
        hi = float(srt[min(n - 1, int(0.975 * n))])
        se = float(srt.std(ddof=1)) if n > 1 else float("nan")
        return lo, hi, se

    def stat(self, key, mask=None):
        out, vals = self._reps_of(key, mask)
        n = len(vals)
        value = (sum(vals) / n) if n else None
        n_roots = len({r["root_id"] for r in self.rows
                       if (mask is None or mask(r)) and r.get(key) is not None})
        if out is None:
            return {"value": value, "ci95": [None, None], "se_root": None,
                    "z": None, "n": n, "n_roots": n_roots}
        lo, hi, se = self._pct(out)
        z = (value / se) if (se and se == se and se > 0 and value is not None) else None
        return {"value": value, "ci95": [lo, hi], "se_root": se, "z": z,
                "n": n, "n_roots": n_roots}

    def contrast(self, key, mask_a, mask_b):
        """mean(key | mask_a) - mean(key | mask_b) on the SAME root draw."""
        ra, va = self._reps_of(key, mask_a)
        rb, vb = self._reps_of(key, mask_b)
        if ra is None or rb is None:
            return {"value": None, "ci95": [None, None], "se_root": None, "z": None}
        value = (sum(va) / len(va)) - (sum(vb) / len(vb))
        d = ra - rb
        lo, hi, se = self._pct(d)
        z = (value / se) if (se and se == se and se > 0) else None
        return {"value": value, "ci95": [lo, hi], "se_root": se, "z": z,
                "n_a": len(va), "n_b": len(vb)}


def load_jsonl(p):
    with open(p) as fh:
        return [json.loads(line) for line in fh if line.strip()]


# --------------------------------------------------------------------------- #
def validate_phase_recovery(out):
    """PREREG 2.1 falsifier #1 -- publish agreement BEFORE reading any phase number."""
    v = {}
    census = os.path.join(
        REPO, "measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl")
    n = ok_k = ok_p = ok_true = 0
    for line in open(census):
        d = json.loads(line)
        n += 1
        ok_k += int(k_from_ply(d["ply"]) == d["k_remaining"])
        ok_p += int(phase_bucket(k_from_ply(d["ply"])) == d["phase_bucket"])
        ok_true += int(phase_bucket(d["k_remaining"]) == d["phase_bucket"])
    v["census_tile_plies"] = n
    v["census_k_formula_exact"] = ok_k / n
    v["census_phase_from_recovered_k_agree"] = ok_p / n
    v["census_phase_from_true_k_agree"] = ok_true / n
    for tag, path, in (("A", "measurement/tiearb_widening_20260817/shared_run_r4/"
                             "verdicts/per_position_s1.jsonl"),
                       ("B", "measurement/tiearb_20260816/per_position.jsonl")):
        rows = load_jsonl(os.path.join(REPO, path))
        agree = sum(phase_bucket(k_from_ply(r["ply"])) == r["phase_bucket"]
                    for r in rows) / len(rows)
        v[f"corpus_{tag}_phase_recovery_agree"] = agree
    arms = json.load(open(os.path.join(
        REPO, "measurement/tiearb_widening_20260817/rung3_r5/corpus/"
              "positions_s2/ARMS.json")))
    agree = sum(phase_bucket(a["k_remaining"]) == a["phase_bucket"]
                for a in arms.values()) / len(arms)
    v["corpus_C_stored_phase_consistent_with_stored_k"] = agree
    v["corpus_C_phase_source"] = "ARMS.json::phase_bucket (stored, not recovered)"
    v["falsifier_1_threshold"] = 0.98
    v["falsifier_1_fired"] = bool(min(
        v["census_phase_from_recovered_k_agree"],
        v["corpus_A_phase_recovery_agree"],
        v["corpus_B_phase_recovery_agree"]) < 0.98)
    out["phase_recovery_validation"] = v


# --------------------------------------------------------------------------- #
def corpus_A(out):
    path = os.path.join(REPO, "measurement/tiearb_widening_20260817/shared_run_r4/"
                              "verdicts/per_position_s1.jsonl")
    rows = load_jsonl(path)
    boot = RootBoot(rows)
    res = {
        "path": os.path.relpath(path, REPO),
        "n": len(rows), "n_roots": boot.g,
        "primary_key_template": "arb_j4_E64_B{b}",
        "primary_key_note": ("the R4 read-out's OWN ladder key -- "
                             "analyze_widening.py::ladder_block reads arb_j4_*, "
                             "J=4 is the deployed cap"),
        "phase_counts": dict(Counter(r["phase_bucket"] for r in rows)),
        "bands_pooled": ["135e9 (retained, 551)", "137e9 (fresh, 793)"],
        "ladder": {}, "ladder_full": {}, "companions": {}, "contrasts": {},
    }

    def m_all(_r):
        return True

    def m_ph(p):
        return lambda r: r["phase_bucket"] == p

    def m_midlate(r):
        return r["phase_bucket"] in ("mid", "late")

    for b in B_LADDER:
        k = f"arb_j4_E64_B{b}"
        res["ladder"][f"B{b}"] = {
            "ALL": boot.stat(k),
            **{p: boot.stat(k, m_ph(p)) for p in PHASES},
        }
        kf = f"arb_full_E64_B{b}"
        res["ladder_full"][f"B{b}"] = {
            "ALL": boot.stat(kf),
            **{p: boot.stat(kf, m_ph(p)) for p in PHASES},
        }
        res["contrasts"][f"B{b}"] = {
            "early_minus_mid": boot.contrast(k, m_ph("early"), m_ph("mid")),
            "early_minus_late": boot.contrast(k, m_ph("early"), m_ph("late")),
            "early_minus_midlate": boot.contrast(k, m_ph("early"), m_midlate),
        }
    for k in ("ora_full_E64", "rnd_E64"):
        res["companions"][k] = {"ALL": boot.stat(k),
                                **{p: boot.stat(k, m_ph(p)) for p in PHASES}}
        res["contrasts"][k] = {
            "early_minus_mid": boot.contrast(k, m_ph("early"), m_ph("mid")),
            "early_minus_late": boot.contrast(k, m_ph("early"), m_ph("late")),
            "early_minus_midlate": boot.contrast(k, m_ph("early"), m_midlate),
        }
    # arb - rnd (capture over a random tie-break), computed per position
    for r in rows:
        for b in B_LADDER:
            r[f"amr_B{b}"] = r[f"arb_j4_E64_B{b}"] - r["rnd_E64"]
    boot2 = RootBoot(rows)
    res["arb_minus_rnd"] = {
        f"B{b}": {"ALL": boot2.stat(f"amr_B{b}"),
                  **{p: boot2.stat(f"amr_B{b}", m_ph(p)) for p in PHASES}}
        for b in B_LADDER}
    # E=16 sub-read, secondary
    res["ladder_E16"] = {
        f"B{b}": {"ALL": boot.stat(f"arb_j4_E16_B{b}"),
                  **{p: boot.stat(f"arb_j4_E16_B{b}", m_ph(p)) for p in PHASES}}
        for b in B_LADDER}
    out["corpus_A"] = res


def corpus_B(out):
    path = os.path.join(REPO, "measurement/tiearb_20260816/per_position.jsonl")
    rows = load_jsonl(path)
    boot = RootBoot(rows)

    def m_ph(p):
        return lambda r: r["phase_bucket"] == p

    def m_midlate(r):
        return r["phase_bucket"] in ("mid", "late")

    scale_all = rows[0]["scale_all"]
    scale_strict = rows[0]["scale_strict"]
    res = {
        "path": os.path.relpath(path, REPO),
        "n": len(rows), "n_roots": boot.g,
        "effective_rung": ("B~16 -- m=32 CRN worlds, cross-fit half-M selection "
                           "(16 selection worlds); NOT a B ladder"),
        "phase_counts": dict(Counter(r["phase_bucket"] for r in rows)),
        "rules_profiles": dict(Counter(r["rules_profile"] for r in rows)),
        "strata": dict(Counter(r["stratum"] for r in rows)),
        "slices": dict(Counter(r.get("slice") for r in rows)),
        "scale_all": scale_all, "scale_strict": scale_strict,
        "scaling_note": ("READOUT.md quotes mean x scale_all; this file prints the "
                         "UNSCALED record mean and the scaled value beside it"),
        "stats": {}, "contrasts": {},
        "status_note": ("Stage-1b read rule is SPENT and its holdout BURNED. Used "
                        "here ONLY as a phase-contrast replicate."),
    }
    for k in ("arb", "ora", "rnd", "arb_minus_rnd"):
        cell = {"ALL": boot.stat(k), **{p: boot.stat(k, m_ph(p)) for p in PHASES}}
        for c in cell.values():
            if c["value"] is not None:
                c["value_scaled_all"] = c["value"] * scale_all
        res["stats"][k] = cell
        res["contrasts"][k] = {
            "early_minus_mid": boot.contrast(k, m_ph("early"), m_ph("mid")),
            "early_minus_late": boot.contrast(k, m_ph("early"), m_ph("late")),
            "early_minus_midlate": boot.contrast(k, m_ph("early"), m_midlate),
        }
    # holdout-only sanity (blind slice), reported not read
    hold = [r for r in rows if r.get("slice") == "holdout"]
    bh = RootBoot(hold)
    res["holdout_only"] = {"n": len(hold), "n_roots": bh.g,
                           "arb": {"ALL": bh.stat("arb"),
                                   **{p: bh.stat("arb", m_ph(p)) for p in PHASES}}}
    out["corpus_B"] = res


def corpus_C(out):
    """Corpus C phase-resolved capture, in the arbiter's OWN currency.

    rung3_r5 has no clairvoyant oracle leg banked in-repo, so it cannot produce a
    judge-priced capture. What it CAN produce, phase-resolved, is the arbiter's own
    decision margin |G| -- the size of the gap the arbiter is resolving. That is the
    quantity the racing simulation trades against, so it is reported here, clearly
    labelled as NOT a capture replicate.
    """
    import glob
    base = os.path.join(REPO, "measurement/tiearb_widening_20260817/rung3_r5")
    arms = json.load(open(os.path.join(
        base, "corpus/positions_s2/ARMS.json")))
    recs = defaultdict(dict)
    bad_delta = 0
    n_files = 0
    for f in glob.glob(os.path.join(
            base, "legs/s2/tier1-greedy/walled/leg*/records/*.json")):
        d = json.load(open(f))
        n_files += 1
        pwd = np.asarray(d["per_world_delta"], dtype=float)
        va = np.asarray(d["values_a"], dtype=float)
        vb = np.asarray(d["values_b"], dtype=float)
        if not np.allclose(pwd, vb - va, atol=1e-9):
            bad_delta += 1
            continue
        recs[d["rid"]][d["pick_b"]] = (va, vb)
    res = {"n_record_files": n_files, "n_rids": len(recs),
           "bad_per_world_delta": bad_delta,
           "falsifier_2_rate": bad_delta / max(1, n_files),
           "note": ("NOT a judge-priced capture replicate -- rung3_r5 banks no "
                    "clairvoyant leg in-repo. Reports the arbiter's own full-m "
                    "decision margin (the gap racing trades against), phase-resolved."),
           "caveat_stratum": ("EVERY rid is capped_at_4=true (n_arms>=5): the "
                              "J-widening stratum, NOT the deployment arm mix "
                              "(deployed Abar = 3.0022)."),
           "by_phase": {}}
    per = defaultdict(list)
    for rid, d in recs.items():
        a = arms.get(rid)
        if not a:
            continue
        va = next(iter(d.values()))[0]
        mat = [va] + [d[p][1] for p in a["arms"][1:] if p in d]
        idx = {act: i for i, act in enumerate(a["arms"])}
        j4 = [idx[x] for x in a["subset_j4"] if idx.get(x, 99) < len(mat)]
        if len(j4) < 2:
            continue
        M = np.vstack([mat[i] for i in j4])
        means = M.mean(axis=1)
        order = np.argsort(-means, kind="stable")
        gap = float(means[order[0]] - means[order[1]])
        per[a["phase_bucket"]].append(gap)
        per["ALL"].append(gap)
    for p, v in per.items():
        v = np.asarray(v)
        res["by_phase"][p] = {
            "n": int(v.size), "mean_top2_gap": float(v.mean()),
            "median_top2_gap": float(np.median(v)),
            "frac_gap_lt_0.25": float((v < 0.25).mean()),
            "frac_gap_lt_1.0": float((v < 1.0).mean()),
        }
    out["corpus_C_margin_profile"] = res


def main():
    out = {"artifact": "PHASE_B_CAPTURE",
           "prereg": "measurement/arb_costopt_prep/PREREG.md",
           "generated_by": "measurement/arb_costopt_prep/phase_b_capture.py",
           "estimator": ("record mean; percentile ROOT bootstrap, cluster=root, "
                         "2000 reps, seed 20260819 (analyze_widening.RootBoot "
                         "convention). Phase contrasts on the SAME draw."),
           "phase_cuts": {k: list(v) for k, v in PHASE_CUTS.items()},
           "phase_cut_source": ("scripts/measurement_infra/sample_agreement_roots.py"
                               ":96 verbatim, strict-cut fall-through reproduced "
                               "(k==48 and k==24 -> 'late')"),
           "judge_family_label": ("ABSOLUTE capture levels are IN-FAMILY judge-priced "
                                  "(clair-puct IF judge / tier1-greedy ARB judge). "
                                  "The WITHIN-CORPUS PHASE CONTRAST is the robust part."),
           "cross_band_label": ("CL-068: corpora are NEVER pooled; any cross-corpus "
                               "statement gets sigma inflated 2x."),
           }
    validate_phase_recovery(out)
    corpus_A(out)
    corpus_B(out)
    corpus_C(out)
    dst = os.path.join(HERE, "PHASE_B_CAPTURE.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote", dst)


if __name__ == "__main__":
    main()
