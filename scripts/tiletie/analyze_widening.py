#!/usr/bin/env python3
"""W3 — the tie-arbiter WIDENING analyzer (rungs 2 `B>16` + 3 `J>4`).

ONE invocation, ONE read-out, both rungs. It emits, at the EXACT spellings
`measurement/tiearb_widening_20260817/shared_run_r4/READ_RULE.md` addresses
(rev R4; the R3.3 pair in `shared_run/` is SPENT-BY-GATE-FAILURE):

    verdicts/READOUT.json            the addressed machine surface (`READOUT::…`)
    verdicts/READOUT.md              the harness REPORT (see the blindness rule)
    verdicts/per_position_s1.jsonl   §4/§5's recompute fallback
    verdicts/per_position_s2.jsonl
    verdicts/SEALED_G_REPLICATE.json the G-REPLICATE z's — SEALED

Address map (every one is a pre-registered branch input or gate input):

    widening.gates.crn.{ok,witness_kinds}                        G-CRN
    widening.gates.uncapped                                      G-UNCAPPED (fb)
    widening.gates.arms.{n_arms,n_arms_complete,include_partial,ok}   G-ARMS
    widening.completion.{s1_n,s2_n,s1_max_per_root,s2_max_per_root}   G-COMPLETE
    widening.stage1_replication.{pass,per_rung_inside_envelope,
                                 arb16_convicts,envelope_inflation}   G-REPLICATE
    widening.delta.d_16_64.{value,ci95,se_root}                  §4 rung 2 PRIMARY
    widening.delta.d_16_32.{value,ci95,se_root}                  §4 secondary
    widening.b_ladder.E64.B{1,2,4,8,16,32,64}.{arb,ci95,se}      §4 ladder
    widening.b_ladder.E16.B{…}.{arb,ci95,se}                     §4 sub-read
    widening.j_rider.s2.{delta_ora,ci95_ora,r_ora,ci95_r_ora,ora_j4_ci95,
                         delta_arb,ci95_arb,n_capped,xfree_window}    §5 PRIMARY
    widening.j_rider.s1_replication.{…}                          §5 rider
    widening.j_rider.interaction.{arb_full_64_minus_16,
                                  arb_full_16_minus_j4_16}       §5 rider
    widening.j_rider.d_draw.{n_checked,agreement_rate}           §5 rider

⚠️ BLINDNESS — the two rules this module implements mechanically
   1. `G-REPLICATE`'s natural inputs ARE outcome statistics. Its z's therefore
      go to `SEALED_G_REPLICATE.json` and NOWHERE else: `READOUT.json` and
      `READOUT.md` carry only `pass` / `per_rung_inside_envelope` /
      `arb16_convicts` / `envelope_inflation`. Nothing in this module prints a
      G-REPLICATE z (READ_RULE §7, REVIEW_R1 dimension note).
   2. On ANY gate FAIL the `READOUT.md` REPORT prints GATE INPUTS ONLY — no
      `arb`, no `ora`, no Δ, no CI, no per-position statistic — so that a fixing
      session can read the failure report and stay blind. `READOUT.json` is the
      machine surface the READ_RULE addresses and is always complete; the fixing
      session reads the `.md`.

Statistics, all as pre-registered (`DESIGN.md` §6 / `READ_RULE.md` §3):
  * `arb(B, E)`  — SELECT on `sorted(sel)[:B]`, PRICE on `sorted(eva)[:E]`,
    via `analyze_tiearb2.arb_at_budget` (bit-identical to Stage 1 at B=16/E=full).
  * `ora(E)`     — `analyze_tiletie.crossfit_regret` on the same folds.
  * Both symmetrised over the two parity folds, exactly as Stage 2 does.
  * `J = 4` sub-read: the SAME CRN worlds, restricted to the rows whose arm is in
    the recorded `subset_j4` (plus the champion comparator, which both pools must
    contain for `Δ_ora` to be a difference of like quantities).
  * SEs/CIs: percentile ROOT bootstrap, 2,000 reps, seed 20260819, cluster =
    root, ONE shared resample draw across every statistic (so ratios and
    differences stay coherent). Significance is `lower(CI95) > 0`, once, here.

`S1` and `S2` are NEVER pooled (different `E` ⇒ different `ora` estimand).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import analyze_tiletie as AT                                       # noqa: E402
import analyze_tiearb as TA                                        # noqa: E402
import analyze_tiearb2 as A2                                       # noqa: E402

# --- committed constants — NOT new numbers ---------------------------------- #
# ⚠️ These are W3's OWN constants and are deliberately NOT inherited from
# `analyze_tiearb2`, whose `B_LADDER` stops at 16 and whose harness defaults are
# the `M = 32` era (W2, closed-as-verified). Inheriting them would silently cap
# the widening ladder at the very rung this run exists to look above.
B_LADDER = (1, 2, 4, 8, 16, 32, 64)          # DESIGN §2 / READ_RULE §4 — 7 rungs
E_LEVELS_S1 = (64, 16)                       # E=64 primary, E=16 sub-read
E_LEVELS_S2 = (16,)                          # DESIGN §4 "why S2 runs at M=32"
M_EXPECTED_S1 = 128
M_EXPECTED_S2 = 32
BOOT_REPS = 2000                             # DESIGN §6
BOOT_SEED = 20260819                         # DESIGN §6
PARITY_BASE = A2.PARITY_BASE                 # Stage 1's convention (=1)
RND_SEED = 20260819
ENVELOPE_INFLATION = 2.0                     # R1 / CL-068, applied to G-REPLICATE
D1664_FLOOR = 0.040                          # READ_RULE §4 committed floor
D1632_FLOOR = 0.036                          # secondary, never a branch input

#: READ_RULE §3's PRE-REGISTERED power arithmetic. §3 requires the REALIZED
#: quantities to be printed BESIDE these brackets — on the report surface, not
#: only in the JSON — so a reader sees the design's variance model graded by the
#: run rather than having to recompute it. A realized `se` outside the bracket
#: changes NO branch (the realized CI governs and the floor is fixed); it is a
#: disclosure about the design, and printing it is how it stops being a gotcha.
SE_BRACKET = (0.0179, 0.0200)                # §3, `se` of Δ(16→64)
SD_DELTA_BRACKET = (0.9, 1.4)                # §3, `sd_Δ`


def vs_bracket(value, bracket) -> dict:
    """`{realized, bracket, position, inside}` — the realized quantity graded
    against its PRE-REGISTERED bracket, never the other way round."""
    lo, hi = bracket
    if value is None or value != value:
        return {"realized": value, "bracket": [lo, hi], "position": "ABSENT",
                "inside": None}
    pos = "INSIDE" if lo <= value <= hi else ("ABOVE" if value > hi else "BELOW")
    return {"realized": value, "bracket": [lo, hi], "position": pos,
            "inside": pos == "INSIDE"}
PRED_LEGACY = 1.400                          # order-statistic arithmetic
PRED_DEDUPED = 1.244
PRED_DELTA_LEGACY = 0.1382                   # Stage-1b-derived magnitudes
PRED_DELTA_DEDUPED = 0.0842
G_COMPLETE_S1_FLOOR = 1283                   # 95% of 1,350
G_COMPLETE_S2_FLOOR = 1045                   # 95% of 1,100
S1_MAX_PER_ROOT = 4                          # mining ceiling
S2_MAX_PER_ROOT = 3


# --------------------------------------------------------------------------- #
# the ONE shared root bootstrap                                                 #
# --------------------------------------------------------------------------- #
class RootBoot:
    """Percentile root bootstrap with ONE shared resample draw.

    Every statistic in the read-out is computed on the SAME `reps x G` root-index
    draw, so a ratio (`R_ora`) and its numerator/denominator, and a difference and
    its two terms, are coherent replicate-by-replicate. Rows contribute their
    record weight (root sums / root counts), the `analyze_tiletie.bootstrap_roots`
    convention.
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

    # -- internals ---------------------------------------------------------- #
    def _sums(self, key):
        s = np.zeros(self.g, dtype=np.float64)
        c = np.zeros(self.g, dtype=np.float64)
        vals, rts = [], []
        for r in self.rows:
            v = r.get(key)
            if v is None or v != v:
                continue
            i = self._pos[r["root_id"]]
            s[i] += float(v)
            c[i] += 1.0
            vals.append(float(v))
            rts.append(r["root_id"])
        return s, c, vals, rts

    def _replicates(self, key):
        s, c, vals, _ = self._sums(key)
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

    # -- public ------------------------------------------------------------- #
    def stat(self, key):
        """`{value, ci95, se_root, z, n, n_roots, significant}` for one key."""
        out, vals = self._replicates(key)
        n = len(vals)
        value = (sum(vals) / n) if n else None
        if out is None:
            return {"value": value, "ci95": [None, None], "se_root": None,
                    "z": None, "n": n, "n_roots": self.g, "significant": None}
        lo, hi, se = self._pct(out)
        z = (value / se) if (se and se == se and se > 0 and value is not None) else None
        return {"value": value, "ci95": [lo, hi], "se_root": se, "z": z,
                "n": n, "n_roots": self.g,
                "significant": bool(lo is not None and lo > 0)}

    def ratio(self, num_key, den_key):
        """`mean(num)/mean(den)` with a CI from the SAME resample draw."""
        num, nvals = self._replicates(num_key)
        den, dvals = self._replicates(den_key)
        nmean = (sum(nvals) / len(nvals)) if nvals else None
        dmean = (sum(dvals) / len(dvals)) if dvals else None
        value = (nmean / dmean) if (nmean is not None and dmean not in (None, 0)) else None
        if num is None or den is None:
            return {"value": value, "ci95": [None, None], "se_root": None,
                    "n": len(nvals), "n_roots": self.g}
        with np.errstate(invalid="ignore", divide="ignore"):
            rep = num / den
        lo, hi, se = self._pct(rep)
        return {"value": value, "ci95": [lo, hi], "se_root": se,
                "n": len(nvals), "n_roots": self.g}


def _empty_stat():
    return {"value": None, "ci95": [None, None], "se_root": None, "z": None,
            "n": 0, "n_roots": 0, "significant": None}


# --------------------------------------------------------------------------- #
# per-position assembly                                                         #
# --------------------------------------------------------------------------- #
def world_witness_key(rec: dict) -> str:
    """Which per-world CRN witness a record carries — the literal contract of
    `run_tiletie.world_witness_key`, re-stated here so the analyzer never has to
    import the (engine-bearing) driver. `afterstate_deck_hash_a` is the python
    leg's; `world_deck_hash` is the rust ARB leg's; a leg set mixing them is a
    harness error, not a CRN failure."""
    if "afterstate_deck_hash_a" in rec:
        return "afterstate_deck_hash_a"
    if "world_deck_hash" in rec:
        return "world_deck_hash"
    return ""


def _sym(xs):
    return (xs[0] + xs[1]) / 2.0


def _sub_rows(matrix, idxs):
    return [matrix[i] for i in idxs]


#: §D4.18 — the ONE failure class this analyzer may drop rather than raise on.
#: `WindowTruncationError` is the KNOWN instrument limitation of the encoder at
#: extreme board extents (PUCT reaches a node whose every legal action falls
#: outside the 25-wide window), studied in `measurement/window_truncation_20260813/`.
#: It is not data corruption — and any OTHER class is a different question that
#: count is the wrong axis for, so it RAISES regardless of how few records carry it.
KNOWN_FAILURE_CLASS = "WindowTruncationError"
KNOWN_FAILURE_CAUSE = "window_truncation"
WINDOW_TRUNCATION_STUDY = "measurement/window_truncation_20260813/"

#: ⚠️ VERBATIM from §D4.18(c). Printed whether or not anything was dropped.
SELECTION_EFFECT_SENTENCE = (
    "The 4 dropped rids are not a random subsample. WindowTruncationError fires "
    "at extreme board extents, so the dropped set is correlated with board "
    "geometry — late-game, large-extent positions. At 4 / 1,344 = 0.30% the "
    "maximum arithmetic influence on the primary is bounded by "
    "(4/1,340)·|Δ|_max ≈ 0.003·|Δ|_max, a fraction of se ≈ 0.02 for any "
    "plausible |Δ|_max; the point of this note is that the correlation is "
    "DISCLOSED rather than argued away, so it is not rediscovered later as a "
    "gotcha. Diagnostic class and study: "
    + WINDOW_TRUNCATION_STUDY)


def diagnostic_class(record: dict) -> dict:
    """The failure's CLASS and CAUSE, from the record's own `error` field.

    `error` reads `"<ClassName>: <message> [cause=<cause> …]"`, so the class is
    the token before the first colon and the cause is the `cause=` marker. Both
    are reported; the class is what the drop licence is matched on.
    """
    err = record.get("error")
    if not isinstance(err, str) or not err.strip():
        return {"diagnostic_class": None, "cause": None, "error": err}
    cls = err.split(":", 1)[0].strip() or None
    cause = None
    if "cause=" in err:
        cause = err.split("cause=", 1)[1].split()[0].strip().rstrip("]").strip()
    return {"diagnostic_class": cls, "cause": cause, "error": err[:200]}


def collect_failed_records(arms_index, if_by_rid, arb_by_rid) -> dict:
    """{rid: [{judge, leg, diagnostic_class, cause, error}, …]} across BOTH judges.

    A record is FAILED if it says `ok: False` or if it carries no values to
    dereference — the shape that crashed `build_rows` (a failed record has no
    `values_a` / `values_b` at all).
    """
    out: dict = {}
    for judge, by_rid in (("clair-puct", if_by_rid), ("tier1-greedy", arb_by_rid)):
        for rid in arms_index:
            for leg, rec in sorted((by_rid.get(rid) or {}).items()):
                if not isinstance(rec, dict):
                    continue
                broken = (rec.get("ok") is False
                          or rec.get("values_a") is None
                          or rec.get("values_b") is None)
                if broken:
                    out.setdefault(rid, []).append(
                        {"judge": judge, "leg": leg, **diagnostic_class(rec)})
    return out


def failed_record_block(failed: dict, *, n_planned=None) -> dict:
    """§D4.18(3) — the TYPED accounting, printed whether or not anything failed."""
    rows = sorted(
        ({"rid": rid,
          "legs": sorted({f["leg"] for f in fs}),
          "judges": sorted({f["judge"] for f in fs}),
          "n_records": len(fs),
          "diagnostic_class": sorted({str(f["diagnostic_class"]) for f in fs}),
          "cause": sorted({str(f["cause"]) for f in fs})}
         for rid, fs in failed.items()), key=lambda r: r["rid"])
    return {
        "n_failed_rids": len(rows),
        "n_failed_records": sum(r["n_records"] for r in rows),
        "n_planned": n_planned,
        "by_rid": rows,
        "policy": "WHOLE-RID DROP across BOTH judges, before any contrast — the "
                  "consequence of G-ARMS' `include_partial == false` (a rid with "
                  "a valueless arm is not analysable), not a new policy. The "
                  "paired per-position contrast needs the IF side, so a "
                  "half-present rid is not a contrast.",
        "known_class": KNOWN_FAILURE_CLASS,
        "unknown_class_rule": "any failed record whose diagnostic class is NOT "
                              "the known class RAISES and escalates, regardless "
                              "of count — a novel failure class is a different "
                              "question, and count is the wrong axis for it",
        "study": WINDOW_TRUNCATION_STUDY,
        "selection_effect": SELECTION_EFFECT_SENTENCE,
        "consumed_by": "G-COMPLETE alone, on the POST-DROP analysed count "
                       "(G-CRN and G-ARMS are computed over surviving/ok "
                       "records only, so there is nothing to double-count)",
    }


def build_rows(arms_index: dict, if_by_rid: dict, arb_by_rid: dict, *,
               e_levels, m_expected, parity_base=PARITY_BASE,
               rnd_seed=RND_SEED, stratum_tag="S1"):
    """Assemble the arms x worlds matrices per position and evaluate every §4/§5
    statistic on them, for the FULL deduped arm set and its `J=4` sub-read.

    `include_partial_arms=False` semantics inherited verbatim from
    `analyze_tiletie.build_positions`: a position missing any PLANNED leg in
    either judge is EXCLUDED and counted.
    """
    rows = []
    counts = {"planned": 0, "absent_if": 0, "absent_arb": 0, "armset_mismatch": 0,
              "partial": 0, "champ_arm_absent": 0, "analysed": 0,
              "m_mismatch": 0, "e_short": 0, "j4_absent": 0, "failed_rid": 0}

    # ---- §D4.18: failed records, resolved BEFORE any contrast -------------- #
    failed = collect_failed_records(arms_index, if_by_rid, arb_by_rid)
    unknown = [dict(f, rid=rid) for rid, fs in sorted(failed.items()) for f in fs
               if f["diagnostic_class"] != KNOWN_FAILURE_CLASS]
    if unknown:
        raise SystemExit(
            "REFUSING: {} failed record(s) carry a diagnostic class that is NOT "
            "the known {!r}: {}. §D4.18 licenses a WHOLE-RID DROP for the known "
            "encoder-window limitation ({}) and NOTHING else — a novel failure "
            "class is a different question, and COUNT IS THE WRONG AXIS for it. "
            "Escalate; do not drop.".format(
                len(unknown), KNOWN_FAILURE_CLASS,
                [{k: v for k, v in u.items() if k in
                  ("rid", "judge", "leg", "diagnostic_class", "cause")}
                 for u in unknown[:5]],
                WINDOW_TRUNCATION_STUDY))
    arms_gate = {"n_arms": 0, "n_arms_complete": 0}
    crn = {"witness_kinds": defaultdict(set), "per_leg": defaultdict(
        lambda: {"n_ok": 0, "n_crn_verified": 0, "n_records": 0}),
        "n_records": 0, "n_crn_verified": 0}
    uncapped = {"n_rids": 0, "n_prefix_ok": 0, "n_append_ok": 0, "n_violation": 0,
                "violations": []}

    for rid, meta in sorted(arms_index.items()):
        counts["planned"] += 1
        # ⭐ WHOLE-RID DROP, across BOTH judges, before ANY contrast. This loop
        # is per-rid, so one `continue` removes the rid from both matrices, the
        # CRN counters, the arm accounting and every downstream statistic —
        # complete-case on intact rids, which is what `G-ARMS`'
        # `include_partial == false` already implies.
        if rid in failed:
            counts["failed_rid"] += 1
            continue
        arms = meta["arms"]
        n_arms = len(arms)
        need = list(range(1, n_arms))
        if_legs = if_by_rid.get(rid, {})
        arb_legs = arb_by_rid.get(rid, {})
        have_if = sorted(k for k in if_legs if k in need)
        have_arb = sorted(k for k in arb_legs if k in need)

        # ---- G-UNCAPPED, per rid: the EXACT prefix+append identity ---------- #
        full = meta.get("arms_full")
        if full is not None:
            uncapped["n_rids"] += 1
            prefix_ok = list(arms[:len(full)]) == list(full)
            extra = len(arms) - len(full)
            append_ok = (extra == 0) or (
                extra == 1
                and meta.get("champ_arm_action") == arms[-1]
                and meta.get("champ_arm_index") == len(arms) - 1)
            uncapped["n_prefix_ok"] += bool(prefix_ok)
            uncapped["n_append_ok"] += bool(append_ok)
            if not (prefix_ok and append_ok):
                uncapped["n_violation"] += 1
                if len(uncapped["violations"]) < 20:
                    uncapped["violations"].append(
                        {"rid": rid, "prefix_ok": prefix_ok,
                         "append_ok": append_ok, "n_arms": len(arms),
                         "n_arms_full": len(full)})

        if not have_if:
            counts["absent_if"] += 1
            continue
        if not have_arb:
            counts["absent_arb"] += 1
            continue
        if have_if != have_arb:
            counts["armset_mismatch"] += 1
            continue
        if [r for r in need if r not in if_legs]:
            counts["partial"] += 1
            continue

        arm_order = [0] + have_if
        champ_idx = meta.get("champ_arm_index")
        if champ_idx not in arm_order:
            counts["champ_arm_absent"] += 1
            continue
        champ_pos = arm_order.index(champ_idx)

        # ---- matrices + the CRN / completeness witnesses -------------------- #
        # ⚠️ §D4.18(1): a record that is `ok: False` — or that simply carries no
        # values — is NEVER dereferenced. The pre-pass above already drops such
        # rids, so reaching this is a defect rather than a data condition; it is
        # guarded anyway, because the crash it replaces was a KeyError on
        # `ref["values_a"]` of a failed record, and a guard that only exists
        # upstream is one refactor away from being absent.
        unusable = [(jn, r) for jn, legs in (("if", if_legs), ("arb", arb_legs))
                    for r in have_if
                    if (legs.get(r) or {}).get("ok") is False
                    or (legs.get(r) or {}).get("values_a") is None
                    or (legs.get(r) or {}).get("values_b") is None]
        if unusable:
            counts["failed_rid"] += 1
            continue

        mats = {}
        for jname, legs in (("if", if_legs), ("arb", arb_legs)):
            ref = legs[have_if[0]]
            va0 = ref["values_a"]
            for r in have_if:
                rec = legs[r]
                crn["n_records"] += 1
                crn["n_crn_verified"] += bool(rec.get("crn_verified"))
                kind = world_witness_key(rec)
                crn["witness_kinds"][jname].add(kind)
                pl = crn["per_leg"][f"{jname}/leg{r}"]
                pl["n_records"] += 1
                pl["n_ok"] += bool(rec.get("ok", True))
                pl["n_crn_verified"] += bool(rec.get("crn_verified"))
            mats[jname] = [list(va0)] + [list(legs[r]["values_b"]) for r in have_if]

        matrix_if, matrix_arb = mats["if"], mats["arb"]
        m = len(matrix_if[0])

        # G-ARMS: every FULL-SET arm scored on ALL M worlds — per arm, not per ply
        arms_gate["n_arms"] += n_arms
        arms_gate["n_arms_complete"] += sum(
            1 for ri, ra in zip(matrix_if, matrix_arb)
            if len(ri) == m and len(ra) == m)

        if m != m_expected:
            counts["m_mismatch"] += 1

        sel0, eva0 = AT.parity_indices(m, base=parity_base, swap=False)
        if min(len(sel0), len(eva0)) < max(e_levels):
            counts["e_short"] += 1
            continue

        # ---- the J = 4 sub-read pool --------------------------------------- #
        subset = meta.get("subset_j4")
        if not subset:
            counts["j4_absent"] += 1
            continue
        sub_set = set(subset)
        j4_idx = [p for p, ai in enumerate(arm_order) if arms[ai] in sub_set]
        if champ_pos not in j4_idx:
            # the champion comparator must live in BOTH pools, else Δ_ora is a
            # difference of unlike quantities (its champ term would not cancel)
            j4_idx = sorted(j4_idx + [champ_pos])
        champ_pos_j4 = j4_idx.index(champ_pos)
        mif_j4 = _sub_rows(matrix_if, j4_idx)
        marb_j4 = _sub_rows(matrix_arb, j4_idx)

        a_rnd = TA.rnd_arm_position(rid, len(arm_order), rnd_seed)

        acc = defaultdict(list)
        for swap in (False, True):
            sel, eva = AT.parity_indices(m, base=parity_base, swap=swap)
            sel_sorted, eva_sorted = sorted(sel), sorted(eva)
            for e in e_levels:
                eva_e = eva_sorted[:e]
                ora_full, _ = AT.crossfit_regret(matrix_if, sel, eva_e, champ_pos)
                ora_j4, _ = AT.crossfit_regret(mif_j4, sel, eva_e, champ_pos_j4)
                acc[f"ora_full_E{e}"].append(ora_full)
                acc[f"ora_j4_E{e}"].append(ora_j4)
                acc[f"rnd_E{e}"].append(
                    AT._sub_mean(matrix_if[a_rnd], eva_e)
                    - AT._sub_mean(matrix_if[champ_pos], eva_e))
                for b in B_LADDER:
                    if b > len(sel_sorted):
                        continue
                    acc[f"arb_full_E{e}_B{b}"].append(
                        A2.arb_at_budget(matrix_arb, matrix_if, sel, eva_e,
                                         champ_pos, b)[0])
                    acc[f"arb_j4_E{e}_B{b}"].append(
                        A2.arb_at_budget(marb_j4, mif_j4, sel, eva_e,
                                         champ_pos_j4, b)[0])

        row = {
            "rid": rid, "root_id": meta["root_id"],
            "stratum_tag": stratum_tag, "stratum": meta.get("stratum"),
            "rules_profile": meta.get("rules_profile"),
            "ply": meta.get("ply"), "phase_bucket": meta.get("phase_bucket"),
            "capped_at_4": bool(meta.get("capped_at_4")),
            "champ_outside_tieset": bool(meta.get("champ_outside_tieset")),
            "n_distinct_afterstates": meta.get("n_distinct_afterstates"),
            "m": m, "m_expected": m_expected,
            "n_arms_planned": n_arms, "n_arms_scored": len(arm_order),
            "n_arms_full": len(full) if full is not None else None,
            "n_arms_j4": len(j4_idx),
            "n_worlds_per_arm": [len(r) for r in matrix_if],
            "champ_pos": champ_pos, "arm_order": arm_order,
        }
        for k, v in acc.items():
            row[k] = _sym(v)
        # the pre-registered contrasts, per position (CRN-paired within position)
        for e in e_levels:
            if f"arb_j4_E{e}_B64" in row and f"arb_j4_E{e}_B16" in row:
                row[f"d_16_64_E{e}"] = row[f"arb_j4_E{e}_B64"] - row[f"arb_j4_E{e}_B16"]
            if f"arb_j4_E{e}_B32" in row and f"arb_j4_E{e}_B16" in row:
                row[f"d_16_32_E{e}"] = row[f"arb_j4_E{e}_B32"] - row[f"arb_j4_E{e}_B16"]
            row[f"d_ora_E{e}"] = row[f"ora_full_E{e}"] - row[f"ora_j4_E{e}"]
            if f"arb_full_E{e}_B16" in row:
                row[f"d_arb_E{e}"] = (row[f"arb_full_E{e}_B16"]
                                      - row[f"arb_j4_E{e}_B16"])
            if f"arb_full_E{e}_B64" in row and f"arb_full_E{e}_B16" in row:
                row[f"i_full_64_minus_16_E{e}"] = (row[f"arb_full_E{e}_B64"]
                                                   - row[f"arb_full_E{e}_B16"])
        rows.append(row)
        counts["analysed"] += 1

    crn_out = {
        "witness_kinds": {k: sorted(v) for k, v in crn["witness_kinds"].items()},
        "per_leg": {k: dict(v) for k, v in sorted(crn["per_leg"].items())},
        "n_records": crn["n_records"], "n_crn_verified": crn["n_crn_verified"],
    }
    return (rows, counts, arms_gate, crn_out, uncapped,
            failed_record_block(failed, n_planned=counts["planned"]))


# --------------------------------------------------------------------------- #
# gates the analyzer OWNS (READ_RULE §2 addresses under READOUT::widening.*)     #
# --------------------------------------------------------------------------- #
def crn_gate(crn_by_stratum: dict, smoke_manifests: list) -> dict:
    """`G-CRN`: per-judge smoke witness true; `n_crn_verified == n_ok` on every
    leg; EXACTLY ONE witness kind per judge."""
    kinds, per_leg = defaultdict(set), {}
    n_rec = n_ver = 0
    leg_ok = True
    for tag, c in sorted(crn_by_stratum.items()):
        for j, ks in c["witness_kinds"].items():
            kinds[j] |= set(ks)
        for leg, v in c["per_leg"].items():
            per_leg[f"{tag}/{leg}"] = v
            if v["n_crn_verified"] != v["n_ok"]:
                leg_ok = False
        n_rec += c["n_records"]
        n_ver += c["n_crn_verified"]
    one_kind = bool(kinds) and all(len(v) == 1 and "" not in v
                                   for v in kinds.values())
    smokes = {}
    smoke_ok = bool(smoke_manifests)
    for p in smoke_manifests:
        p = Path(p)
        if not p.is_file():
            smokes[str(p)] = None
            smoke_ok = False
            continue
        man = json.loads(p.read_text())
        val = man.get("crn_cross_leg_identical")
        smokes[p.name] = val
        if val is not True:
            smoke_ok = False
    return {
        "ok": bool(leg_ok and one_kind and smoke_ok),
        "witness_kinds": {k: sorted(v) for k, v in sorted(kinds.items())},
        "exactly_one_kind_per_judge": one_kind,
        "legs_consistent": leg_ok,
        "smoke_crn_cross_leg_identical": smokes,
        "smoke_ok": smoke_ok,
        "n_records": n_rec, "n_crn_verified": n_ver,
        "per_leg": per_leg,
        "resolved_at": "READOUT::widening.gates.crn",
    }


def uncapped_gate(plans: dict, uncapped_by_stratum: dict) -> dict:
    """`G-UNCAPPED` (the `READOUT` fallback address): `uncapped == true` and
    `cap_j == null` on both strata, plus the per-rid prefix+append identity.

    ⚠️ A naive `arms == arms_full` fails ~16% of rids BY DESIGN — the champion
    pick is APPENDED when its transposition rep is absent from the tie set
    (`champ_outside_tieset` 15.6–17.3% on the banked corpora; rust does the
    identical append). The conjunct is the exact prefix+append identity."""
    per = {}
    ok = bool(plans)
    for tag, plan in sorted(plans.items()):
        u = uncapped_by_stratum.get(tag, {})
        this = {
            "uncapped": plan.get("uncapped"),
            "cap_j": plan.get("cap_j"),
            "n_rids": u.get("n_rids", 0),
            "n_prefix_ok": u.get("n_prefix_ok", 0),
            "n_append_ok": u.get("n_append_ok", 0),
            "n_violation": u.get("n_violation", 0),
            "violations": u.get("violations", []),
        }
        this["ok"] = bool(this["uncapped"] is True and this["cap_j"] is None
                          and this["n_rids"] > 0 and this["n_violation"] == 0)
        ok = ok and this["ok"]
        per[tag] = this
    return {"ok": ok, "by_stratum": per,
            "resolved_at": "READOUT::widening.gates.uncapped"}


def arms_gate_block(arms_by_stratum: dict, include_partial=False) -> dict:
    """`G-ARMS`: every full-set arm scored on ALL `M` worlds — per ARM, not per
    ply. `n_arms_complete == n_arms` and `include_partial == false`."""
    n = sum(v["n_arms"] for v in arms_by_stratum.values())
    c = sum(v["n_arms_complete"] for v in arms_by_stratum.values())
    return {"n_arms": n, "n_arms_complete": c,
            "include_partial": bool(include_partial),
            "ok": bool(n > 0 and n == c and not include_partial),
            "by_stratum": {k: dict(v) for k, v in sorted(arms_by_stratum.items())},
            "resolved_at": "READOUT::widening.gates.arms"}


def completion_block(rows_s1, rows_s2, floors=None, void_witness=None) -> dict:
    """`G-COMPLETE` (R4 §2a, REPLACES the R3.3 row).

    R3's floors were computed from RAW CENSUS ROWS and were unreachable by 27x
    on S2 (`PREREG_FAILURE` §2): raw rows are not positions — qualification and
    the design's own afterstate dedupe both apply. R4's floors are PARAMETERS
    committed in `RUN/FLOORS.json` before the extension band is claimed, sized
    from the MEASURED rates (`r_S1 = 1.574`, `r_S2cap = 0.206`), and the
    conjunct is `s_n >= ceil(0.95 x n)`.

    ⚠️ Both counts are evaluated AFTER the §2b exclusions — an exclusion can
    never be used to explain away a shortfall after the fact.

    ⚠️ If `n2 == 0` (the `S1 ONLY` row) rung 3 DOES NOT RUN: its branch table is
    not adjudicated and the read-out states the J question was NOT BOUGHT —
    never that it was answered. Absence of a purchase is not a result."""
    def _per_root(rows):
        d = defaultdict(int)
        for r in rows:
            d[r["root_id"]] += 1
        return max(d.values()) if d else 0

    s2_capped = [r for r in rows_s2 if r["capped_at_4"]]
    s1_n, s2_n = len(rows_s1), len(s2_capped)
    s1_mpr, s2_mpr = _per_root(rows_s1), _per_root(s2_capped)

    if floors:
        n1, n2 = int(floors["n1"]), int(floors["n2"])
        f1 = int(floors.get("gate_floor_s1", math.ceil(0.95 * n1)))
        f2 = int(floors.get("gate_floor_s2", math.ceil(0.95 * n2)))
        label = floors.get("option_label")
    else:
        n1 = n2 = None
        f1, f2 = G_COMPLETE_S1_FLOOR, G_COMPLETE_S2_FLOOR
        label = "R3.3 constants (no FLOORS.json given)"
    rung3 = bool(n2) if floors else True
    ok = bool(s1_n >= f1 and s1_mpr <= S1_MAX_PER_ROOT)
    # ⭐ §D4.16's void scope, applied to THIS gate's S2 conjunct — same positive
    # witness, same Reading A. A conjunct addressing a stratum a pre-registered
    # rule VOIDED is not FAILED (nothing failed) and not PASSED (nothing was
    # checked): it is NOT EVALUATED, and the block says so. `rung3_bought` stays
    # TRUE — the run purchased the J question at n2 and then lost it to a void,
    # and "not bought" is the one phrase the owner ruling forbids.
    s2_void = bool((void_witness or {}).get("void"))
    if rung3 and not s2_void:
        ok = ok and bool(s2_n >= f2 and s2_mpr <= S2_MAX_PER_ROOT)
    return {
        "s2_conjunct": ("VOID (stratum) — not evaluated" if s2_void
                        else "evaluated"),
        "s2_void": s2_void,
        "s2_void_witness": ({k: (void_witness or {}).get(k)
                             for k in ("address", "value", "source", "why")}
                            if s2_void else None),
        "s1_n": s1_n, "s2_n": s2_n,
        "s1_max_per_root": s1_mpr, "s2_max_per_root": s2_mpr,
        "s1_n_all": len(rows_s1), "s2_n_all": len(rows_s2),
        "s1_floor": f1, "s2_floor": f2,
        "n1_committed": n1, "n2_committed": n2, "option_label": label,
        "rung3_bought": rung3,
        "rung3_note": (None if rung3 else
                       "n2 == 0 (the S1 ONLY row): the rung-3 question was NOT "
                       "BOUGHT — not answered, not null, not inconclusive. "
                       "Absence of a purchase is not a result."),
        "s1_ceiling": S1_MAX_PER_ROOT, "s2_ceiling": S2_MAX_PER_ROOT,
        "evaluated_after_exclusions": True,
        "ok": ok,
        "resolved_at": "READOUT::widening.completion",
    }


def band_block(verify_paths) -> dict:
    """`G-BAND` (R4 §2c) — generalised from TWO files to N.

    Each generated range emits its OWN `verify-champgames` file and is checked
    against ITS OWN range, with its own committed floor. Never one invocation
    over a widened band: that would report `n_out_of_band == 0` for a seed lying
    in neither range — R3's B1 defect, generalised."""
    files, seen_seeds_sha = {}, {}
    ok = bool(verify_paths)
    for p in verify_paths:
        p = Path(p)
        name = p.name
        if not p.is_file():
            files[name] = {"present": False, "ok": False,
                           "why": "verify file absent"}
            ok = False
            continue
        d = json.loads(p.read_text())
        band = d.get("seed_band")
        released = bool(band and 136000000000 <= int(band[0]) <= 136999999999)
        this_ok = bool(d.get("band_ok") is True
                       and d.get("n_out_of_band") == 0
                       and d.get("n_duplicate_seeds") == 0
                       and not released)
        files[name] = {
            "present": True, "band_ok": d.get("band_ok"),
            "seed_band": band, "n_out_of_band": d.get("n_out_of_band"),
            "n_duplicate_seeds": d.get("n_duplicate_seeds"),
            "n_games_realized": d.get("n_games_realized"),
            "sha256_of_sorted_seeds": d.get("sha256_of_sorted_seeds"),
            "released_band_136e9": released,
            "ok": this_ok, "path": str(p),
        }
        ok = ok and this_ok
        sha = d.get("sha256_of_sorted_seeds")
        if sha:
            seen_seeds_sha.setdefault(sha, []).append(name)
    # "no seed appears in two files" — the digest is the only handle the emitter
    # publishes (no seed list exists anywhere by design), so identical digests
    # across two files is the detectable case.
    dupes = {k: v for k, v in seen_seeds_sha.items() if len(v) > 1}
    if dupes:
        ok = False
    return {"ok": ok, "files": files, "n_files": len(files),
            "duplicate_seed_digests": dupes,
            "note": "each file checked against ITS OWN range, floors tabular; "
                    "136e9 is RELEASED UNUSED and must appear in NO file",
            "resolved_at": "READOUT::widening.gates.band"}


WORLD_SEED_SALT_OF_RECORD = "tiletie-v1"
DEPLOYED_CAP_J_OF_RECORD = 4


def salt_gate(run_manifests, plans: dict, arms_by_stratum: dict,
              leg_manifests=()) -> dict:
    """`G-SALT` — emitted HERE because it is emitted nowhere else.

    ⚠️ WHY THIS EXISTS. `G-SALT`'s addresses are scoring-time emissions
    (`RUN_MANIFEST_*::world_seed_salt` is written by `run_tiletie` at leg launch),
    so the pre-scoring 4b address audit cannot bind them — and the acceptance
    harness rightly stopped trying. But a gate that leaves the pre-scoring audit
    and is not picked up at ADJUDICATION is a gate that stopped existing. The
    analyzer runs after the legs, sees the manifests, and is therefore the place
    the conjuncts actually bind.

    The three conjuncts, verbatim (READ_RULE §2):
      * `world_seed_salt == "tiletie-v1"` — a MODULE CONSTANT, not a flag, which
        is exactly why it is READ from what the run emitted rather than assumed;
      * `deployed_cap_j == 4`;
      * `cap_seed` present for EVERY rid.
    """
    per, ok = {}, bool(run_manifests or plans)
    salts_seen = set()
    for p in run_manifests or ():
        p = Path(p)
        tag = "S2" if "_S2" in p.name.upper() else "S1"
        entry = per.setdefault(tag, {})
        if not p.is_file():
            entry.update({"run_manifest": str(p), "present": False,
                          "salt_ok": False})
            ok = False
            continue
        d = json.loads(p.read_text())
        salt = d.get("world_seed_salt")
        salts_seen.add(salt)
        entry.update({"run_manifest": str(p), "present": True,
                      "world_seed_salt": salt,
                      "salt_ok": salt == WORLD_SEED_SALT_OF_RECORD})
        ok = ok and entry["salt_ok"]

    for tag, plan in sorted((plans or {}).items()):
        entry = per.setdefault(tag, {})
        cap_j = plan.get("deployed_cap_j")
        entry["deployed_cap_j"] = cap_j
        entry["deployed_cap_j_ok"] = cap_j == DEPLOYED_CAP_J_OF_RECORD
        arms = (arms_by_stratum or {}).get(tag) or {}
        missing = [r for r, v in arms.items() if v.get("cap_seed") is None]
        entry["n_rids"] = len(arms)
        entry["n_cap_seed_missing"] = len(missing)
        entry["cap_seed_examples_missing"] = sorted(missing)[:10]
        entry["cap_seed_ok"] = bool(arms) and not missing
        ok = ok and entry["deployed_cap_j_ok"] and entry["cap_seed_ok"]

    legs = []
    for p in leg_manifests or ():
        p = Path(p)
        if not p.is_file():
            continue
        d = json.loads(p.read_text())
        legs.append({"path": str(p),
                     "resolved_config.world_seed_salt":
                         (d.get("resolved_config") or {}).get("world_seed_salt")})
    leg_ok = (all(x["resolved_config.world_seed_salt"] == WORLD_SEED_SALT_OF_RECORD
                  for x in legs) if legs else None)

    return {
        "ok": bool(ok and (leg_ok is not False)),
        "expected_world_seed_salt": WORLD_SEED_SALT_OF_RECORD,
        "expected_deployed_cap_j": DEPLOYED_CAP_J_OF_RECORD,
        "by_stratum": per,
        "distinct_salts_seen": sorted(s for s in salts_seen if s is not None),
        "leg_fallback": {"n_checked": len(legs), "ok": leg_ok, "legs": legs[:20]},
        "note": "the salt is a MODULE CONSTANT (run_tiletie.WORLD_SEED_SALT), "
                "not a flag — so the conjunct is that the run RECORDED the "
                "constant of record, not that a flag was passed. Bound here "
                "because the pre-scoring address audit cannot reach a "
                "scoring-time emission.",
        "resolved_at": "READOUT::widening.gates.salt",
    }


def union_block(corpus_union_path) -> dict:
    """R4-0.5 §3 — the corpus's COMPOSITION, surfaced on the read-out.

    R4's `n` is a **MIXTURE**: retained band-135e9 positions (read read-only out
    of the SPENT R3.3 run and COPIED in) plus freshly generated 137e9 extension
    positions. A reader must be able to see that split, because "n = 1350" says
    nothing about how much of it predates this prereg. This is not a caveat on
    the estimand — the retained positions were never scored, so nothing about
    them is an outcome — it is a disclosure about the corpus's construction."""
    if not corpus_union_path or not Path(corpus_union_path).is_file():
        return {"present": False,
                "source": str(corpus_union_path) if corpus_union_path else None,
                "by_stratum": {}, "totals": {},
                "note": "CORPUS_UNION.json not supplied to the analyzer"}
    d = json.loads(Path(corpus_union_path).read_text())
    per = {}
    for s, v in sorted((d.get("by_stratum") or {}).items()):
        per[s] = {
            "n_retained": v.get("n_retained"),
            "n_fresh": v.get("n_fresh"),
            "origin_commit": v.get("origin_commit"),
            "banked_dir": v.get("banked_dir"),
            "copied_not_symlinked": v.get("copied_not_symlinked"),
            "n_excluded_rids_applied": v.get("n_excluded_rids_applied"),
        }
    return {
        "present": True, "source": str(corpus_union_path),
        "by_stratum": per, "totals": d.get("totals") or {},
        "note": "the retained positions are NOT pre-cleared: they entered the "
                "probe build and were gated exactly like fresh ones. 'Already "
                "gated under R3' is not a status any position holds — R3's gate "
                "FAILED, so nothing was ever passed.",
    }


#: §D4.16 — the rung-3 void token. ⚠️ It must NOT collide with any rung-3 branch
#: token, and no `X-` token may appear anywhere in the READOUT on this path.
VOID_S2 = "VOID_S2"

#: The POSITIVE witness, by dotted address. Absence is NOT a witness.
VOID_WITNESS_ADDRESS = "GATE_DISJOINT.json::digest_exclusions.{stratum}.void"

VOID_REASON = ("stratum voided at G-DISJOINT per PREREG_FAILURE_S2.md and "
               "ADJUDICATION_R4_GATES.md Reading A")

#: The owner ruling forbids the nearest available phrases by name. They are
#: carried INLINE on the block so the prohibition cannot be separated from the
#: status it qualifies.
VOID_FORBIDDEN_READINGS = [
    'not "not bought" — the run BOUGHT rung 3 at n2 = 1100',
    'not "answered" — no estimand was read',
    'not "inconclusive" — nothing was measured to be inconclusive about',
    # ⚠️ §D4.17 takes OPTION (b): the six rung-3 branch tokens are NOT
    # enumerated here. Naming them — even to forbid them — leaves a naive
    # downstream grep finding a branch token in this READOUT, which is the
    # actual risk; and they are enumerated in the READ_RULE, which is where a
    # reader looks for them. The prohibition is stated WITHOUT the names, so
    # zero occurrences is checkable by a naive grep over both output files.
    "not any rung-3 branch of the READ_RULE's branch table (they are "
    "enumerated there and are deliberately NOT named here): the table was "
    "never evaluated",
]

#: The S1-side rung-3 riders are real measurements, so they are REPORTED —
#: suppressing measured quantities is worse — but the prohibition travels WITH
#: the number, because inferring a branch from them is the live risk of
#: reporting them at all.
S1_RIDER_PROHIBITION = (
    "REPORTED, ADJUDICATES NOTHING. These are real S1 measurements, but with "
    "rung 3 VOID they have NO PRIMARY TO RIDE ON: no rung-3 branch may be "
    "inferred from them, in either direction. They are not a substitute "
    "estimand, not a partial read, and not evidence for or against any "
    "X-branch."
)


def void_stratum_witness(gate_disjoint_path, stratum: str = "S2") -> dict:
    """⭐ §D4.16's POSITIVE WITNESS — `GATE_DISJOINT.json::digest_exclusions.
    <stratum>.void == true`, read from the artifact.

    **ABSENCE IS NEVER A VOID.** This returns `void=False` for a missing file, a
    missing block, a missing stratum and a `null`; only a literal `true` is a
    witness. That asymmetry is the D4 lesson: missing inputs are an assembly
    defect wearing the shape of a decision, and a guard keyed on absence alone
    would have silently blessed D4's 551 never-scored rids.
    """
    address = VOID_WITNESS_ADDRESS.format(stratum=stratum)
    out = {"void": False, "stratum": stratum, "address": address,
           "source": str(gate_disjoint_path) if gate_disjoint_path else None,
           "present": False, "value": None, "voided_strata": None}
    if not gate_disjoint_path or not Path(gate_disjoint_path).is_file():
        out["why"] = "GATE_DISJOINT.json absent — absence is NOT a void witness"
        return out
    try:
        d = json.loads(Path(gate_disjoint_path).read_text())
    except json.JSONDecodeError as exc:
        out["why"] = f"GATE_DISJOINT.json unreadable ({exc})"
        return out
    out["present"] = True
    out["voided_strata"] = d.get("voided_strata")
    per = d.get("digest_exclusions") or {}
    row = None
    for key, val in per.items():                    # tolerate S2 / s2 spelling
        if str(key).upper() == str(stratum).upper() and isinstance(val, dict):
            row = val
            break
    if row is None:
        out["why"] = (f"no digest_exclusions row for {stratum!r} — a missing row "
                      f"is not a witness")
        return out
    out["value"] = row.get("void")
    out["void"] = row.get("void") is True
    out["why"] = ("positive witness: void is true" if out["void"] else
                  f"void is {row.get('void')!r}, not true — NOT a void witness")
    return out


def _floors_n2(floors_path):
    """`FLOORS.json::n2` — READ, never edited. `rung3_bought` there is CORRECT
    and stays frozen: it is a true statement about what was PURCHASED."""
    if not floors_path or not Path(floors_path).is_file():
        return None
    try:
        return int(json.loads(Path(floors_path).read_text())["n2"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def void_rung3_block(witness: dict, n2, floors_source=None) -> dict:
    """The rung-3 block on the void path (§D4.16's table).

    ⚠️ `bought = true` with `n2` read from `FLOORS.json` — the run PURCHASED the
    J question and then lost it to a stratum void. `FLOORS.json::rung3_bought`
    is CORRECT and stays frozen: flipping it would falsify the record AND make
    this read-out emit "not bought", the one phrase the owner ruling forbids.
    """
    return {
        # both spellings carry the SAME non-X token: `status` is what §D4.16
        # names, `branch` is the address every existing consumer reads. Neither
        # may ever be an X-token on this path.
        "status": VOID_S2,
        "branch": VOID_S2,
        "bought": True,
        "n2": n2,
        "n2_source": floors_source or "FLOORS.json::n2",
        "estimand_read": False,
        "reason": VOID_REASON,
        "forbidden_readings": list(VOID_FORBIDDEN_READINGS),
        "obligation_inherited_by": {
            "successor": "rung3_r5",
            "includes": "I7's dedupe-partition conditional, which stays "
                        "UNMEASURED — W9 / D-DRAW was skipped as moot",
        },
        "witness": {k: witness.get(k) for k in
                    ("address", "value", "source", "voided_strata", "why")},
        "note": "the rung-3 branch table was NEVER EVALUATED. This is not a "
                "branch, and it is not a failure of one.",
    }


def exclusions_block(gate_disjoint_path) -> dict:
    """R4 §7a.2 — the digest-exclusion block, printed on EVERY branch, whether
    or not anything was excluded. Surfaced from `GATE_DISJOINT.json`."""
    if not gate_disjoint_path or not Path(gate_disjoint_path).is_file():
        return {"present": False, "by_stratum": {},
                "source": str(gate_disjoint_path) if gate_disjoint_path else None,
                "note": "GATE_DISJOINT.json not supplied to the analyzer"}
    d = json.loads(Path(gate_disjoint_path).read_text())
    per = d.get("digest_exclusions") or {}
    return {
        "present": True,
        "source": str(gate_disjoint_path),
        "by_stratum": {s: {"n_excluded": v.get("n_excluded"),
                           "carried": v.get("carried"),
                           "residual": v.get("residual"),
                           "determinism_defect": v.get("determinism_defect"),
                           "rate": v.get("rate"),
                           "bound_n": v.get("bound_n"),
                           "denominator": v.get("denominator"),
                           "denominator_source": v.get("denominator_source"),
                           "rids": v.get("rids"),
                           "void": v.get("void")}
                       for s, v in sorted(per.items())},
        "voided_strata": d.get("voided_strata"),
        "total_order": d.get("total_order"),
        "n_comparisons": len(d.get("comparisons") or {}),
        "note": "the digest is a function of the BOARD alone, computed at "
                "corpus-build time BEFORE any value exists — the exclusion is "
                "outcome-independent by construction",
    }


def ci95_of(v) -> list:
    """ALWAYS a 2-list. ⚠️ A bare `None`, a short list or a non-list becomes
    `[None, None]` — a TYPED ABSENCE — because `stat.get("ci95", [None, None])`
    does NOT protect a key that is PRESENT WITH None: the default never fires,
    and the next subscript raises. That is the shape that crashed W3."""
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return [v[0], v[1]]
    return [None, None]


def ladder_stat(b_ladder: dict, e, b) -> dict:
    """⭐ THE ONE CONSTRUCTOR for a ladder rung's stat, used at EVERY site.

    Two shapes for the same field is what put a present-with-None `ci95` into
    `replication_gate`: one call site defaulted to `{"value": None, "ci95":
    [None, None]}` and survived a missing rung, the other defaulted to `{}` and
    handed on `.get("ci95") -> None`. A missing rung is now a TYPED ABSENCE
    everywhere — never a bare-None `ci95`, and never a traceback — and it says
    WHICH layer was missing so the read-out can be acted on.
    """
    lad = (b_ladder or {}).get(f"E{e}")
    rung = (lad or {}).get(f"B{b}")
    if not isinstance(rung, dict):
        return {
            "value": None, "ci95": [None, None], "se": None, "z": None,
            "absent": True,
            # `lad is None` (the E level was never built) and `lad == {}` (built
            # but empty) are DIFFERENT upstream faults and say so separately
            "why": (f"no E{e} ladder exists — that E level was not requested"
                    if lad is None else
                    f"the E{e} ladder has no B{b} rung — no row carried "
                    f"`arb_j4_E{e}_B{b}` (a rung above the cross-fit selection "
                    f"half, or an empty row set)"),
        }
    return {"value": rung.get("arb"), "ci95": ci95_of(rung.get("ci95")),
            "se": rung.get("se"), "z": rung.get("z"), "absent": False,
            "why": None}


def replication_gate(ladder_e16: dict, arb16_stat: dict, reference: dict,
                     inflation=ENVELOPE_INFLATION) -> tuple:
    """`G-REPLICATE` — binds BOTH rungs (ONE shared instrument check, NOT two
    independent confirmations).

    Returns `(public_block, sealed_block)`. The PUBLIC block is booleans only;
    every z lives in the SEALED block, which goes to
    `verdicts/SEALED_G_REPLICATE.json` and is printed by nothing.

    A FAIL means **UNINTERPRETABLE, never FAIL-the-lever** — the fresh corpus is
    a different population.
    """
    ref_rungs = (reference or {}).get("rungs") or {}
    per_rung, per_rung_naive, sealed_rungs = {}, {}, {}
    for b in (1, 2, 4, 8, 16):
        key = f"B{b}"
        run = ladder_e16.get(key) or {}
        ref = ref_rungs.get(str(b)) or ref_rungs.get(key) or {}
        rv, rse = run.get("arb"), run.get("se")
        fv, fse = ref.get("arb"), ref.get("se")
        if None in (rv, rse, fv, fse):
            per_rung[key] = False
            per_rung_naive[key] = False
            sealed_rungs[key] = {"z": None, "reason": "input absent",
                                 "run_arb": rv, "run_se": rse,
                                 "ref_arb": fv, "ref_se": fse}
            continue
        sigma = math.sqrt(float(rse) ** 2 + float(fse) ** 2)
        z = (float(rv) - float(fv)) / sigma if sigma > 0 else float("nan")
        inside_inflated = bool(abs(z) <= 2.0 * inflation) if z == z else False
        inside_naive = bool(abs(z) <= 2.0) if z == z else False
        per_rung[key] = inside_inflated
        per_rung_naive[key] = inside_naive
        sealed_rungs[key] = {"z": z, "sigma": sigma, "run_arb": rv, "run_se": rse,
                             "ref_arb": fv, "ref_se": fse,
                             "inside_naive_2sigma": inside_naive,
                             "inside_inflated_2sigma": inside_inflated}

    # ⚠️ NORMALISED, not `.get(..., default)`: the default does NOT fire on a
    # key that is present with `None`, which is exactly how a bare None reached
    # this subscript. The gate now evaluates to its OWN absence semantics — a
    # conjunct that cannot convict is FALSE, and FALSE here reads UNINTERPRETABLE
    # — instead of raising.
    arb16_ci = ci95_of(arb16_stat.get("ci95"))
    convicts = bool(arb16_ci[0] is not None and arb16_ci[0] > 0)
    arb16_absent = bool(arb16_stat.get("absent")) or arb16_ci[0] is None
    passed = bool(per_rung and all(per_rung.values()) and convicts)
    caveat = bool(any(per_rung[k] and not per_rung_naive[k] for k in per_rung))
    public = {
        "pass": passed,
        "per_rung_inside_envelope": per_rung,
        "arb16_convicts": convicts,
        # the conjunct states WHY it could not convict rather than reading as a
        # measured non-conviction — absence and refutation are different facts
        "arb16_input_absent": arb16_absent,
        "arb16_absent_why": arb16_stat.get("why") if arb16_absent else None,
        "envelope_inflation": inflation,
        "naive_envelope_caveat": caveat,
        "reads": "UNINTERPRETABLE on FAIL — never FAIL-the-lever; the fresh "
                 "corpus is a different population. Binds BOTH rungs: one shared "
                 "instrument check, NOT two independent confirmations.",
        "resolved_at": "READOUT::widening.stage1_replication",
    }
    sealed = {
        "SEALED": "G-REPLICATE z-statistics. WRITE-ONLY: this file is NOT an "
                  "address, no gate resolves against it, the harness never "
                  "prints it and a fixing session never opens it (READ_RULE §7; "
                  "REVIEW_R2 §N4). G-REPLICATE has NO fallback — a missing or "
                  "null boolean block on the READOUT is a FAIL, and the fix is "
                  "in W3, never in the seal.",
        "reference_source": (reference or {}).get("source"),
        "per_rung": sealed_rungs,
        "per_rung_inside_envelope_naive": per_rung_naive,
        "arb16": {"value": arb16_stat.get("value"), "ci95": arb16_ci,
                  "z": arb16_stat.get("z"), "absent": arb16_absent,
                  "why": arb16_stat.get("why")},
        "envelope_inflation": inflation,
        "pass": passed,
    }
    return public, sealed


# --------------------------------------------------------------------------- #
# BRANCH TABLES — READ_RULE §4 and §5, implemented literally                     #
# --------------------------------------------------------------------------- #
def _lo(stat):
    ci = (stat or {}).get("ci95") or [None, None]
    return ci[0]


def _hi(stat):
    ci = (stat or {}).get("ci95") or [None, None]
    return ci[1]


def _fin(x):
    return x is not None and x == x


def decide_rung2(d1664: dict, arb64: dict, arb16: dict) -> dict:
    """READ_RULE §4. Read in order; FIRST match wins; the table is TOTAL (row 5).

    1 W-NOISY     : lower(CI95(arb_64)) <= 0   (broadened per REVIEW_R2 N14 —
                    total, and it captures the negative case; a significantly
                    NEGATIVE level carries a mandatory "mechanism anomaly" print)
    2 W-REVERSAL  : upper(CI95(Δ)) < 0
    3 W-RISING    : lower(CI95(Δ)) > 0 and Δ >= +0.040 and lower(CI95(arb_64)) > 0
                    and arb(64) > arb(16)
    4 W-SATURATED : 0 in CI95(Δ) and lower(CI95(arb_64)) > 0
    5 W-INCONCLUSIVE (catch-all)

    The `+0.040` floor is deliberately a POINT test on `Δ`, stated separately
    from significance so neither can be quietly traded for the other
    (READ_RULE §3).
    """
    dv, dlo, dhi = d1664.get("value"), _lo(d1664), _hi(d1664)
    a64lo, a64hi = _lo(arb64), _hi(arb64)
    a64, a16 = arb64.get("value"), arb16.get("value")
    if not (_fin(dlo) and _fin(dhi) and _fin(a64lo) and _fin(a64hi)):
        return {"branch": "W-INCONCLUSIVE",
                "reason": "degenerate / absent CI (row 5 catch-all)",
                "mechanism_anomaly_print": False}
    if a64lo <= 0:
        neg = bool(a64hi < 0)
        return {"branch": "W-NOISY",
                "reason": "arb_64 does not convict positive: "
                          "lower(CI95(arb_64)) <= 0",
                "mechanism_anomaly_print": neg,
                "mandatory_print": (
                    "the LEVEL is significantly NEGATIVE — a MECHANISM ANOMALY, "
                    "not a 'noisy' reading, and it must not be reported as one"
                    if neg else None)}
    if dhi < 0:
        return {"branch": "W-REVERSAL",
                "reason": "upper(CI95(d_16_64)) < 0 — a strictly larger CRN "
                          "sample cannot be worse in expectation for a "
                          "consistent selector ⇒ mechanism anomaly, not a finding",
                "mechanism_anomaly_print": True}
    if (dlo > 0 and _fin(dv) and dv >= D1664_FLOOR and a64lo > 0
            and _fin(a64) and _fin(a16) and a64 > a16):
        return {"branch": "W-RISING",
                "reason": f"lower(CI)>0, d>={D1664_FLOOR}, arb_64 convicts, "
                          f"arb(64)>arb(16)",
                "mechanism_anomaly_print": False}
    if dlo <= 0 <= dhi and a64lo > 0:
        return {"branch": "W-SATURATED",
                "reason": "0 in CI95(d_16_64) and arb_64 convicts — B=16 is on "
                          "the plateau to within +0.04 pts/tied ply",
                "mechanism_anomaly_print": False}
    # row 5, and the LEVEL/INCREMENT RESIDUE the read-out must name (R3 C6)
    residue = bool(dlo > 0 and _fin(dv) and dv >= D1664_FLOOR
                   and _fin(a64) and _fin(a16) and a64 <= a16)
    return {"branch": "W-INCONCLUSIVE",
            "reason": ("the LEVEL/INCREMENT RESIDUE: Δ is significant AND above "
                       "the +0.040 floor while arb(64) <= arb(16) — the two "
                       "readings DISAGREE, which the read-out must report as an "
                       "INSTRUMENT QUESTION, not as a finding"
                       if residue else
                       "none of rows 1-4 (includes a significant d BELOW the "
                       "+0.040 floor)"),
            "level_increment_residue": residue,
            "mechanism_anomaly_print": False}


def decide_rung3(d_ora: dict, r_ora: dict, ora_j4: dict, d_arb: dict) -> dict:
    """READ_RULE §5. Pre-branch guard first, then the main table (or the
    committed `Δ_ora`-only sub-table when the guard fires). `X-NOISE` rides on
    whichever branch fires and never changes it."""
    guard = not (_fin(_lo(ora_j4)) and _lo(ora_j4) > 0)
    dlo, dhi, dv = _lo(d_ora), _hi(d_ora), d_ora.get("value")
    noise = bool(_fin(_hi(d_arb)) and _hi(d_arb) < 0 and _fin(dlo) and dlo > 0)

    if guard:
        # Δ_ora-only sub-table — the ratio is degenerate and is NOT reported
        if not (_fin(dlo) and _fin(dhi)):
            br, why = "X-INCONCLUSIVE-D", "degenerate / absent CI"
        elif dlo > 0 and _fin(dv) and dlo <= PRED_DELTA_LEGACY <= dhi:
            br, why = "X-CONFIRMED-D", "+0.1382 in CI95(delta_ora)"
        elif dlo > PRED_DELTA_LEGACY:
            br, why = "X-ABOVE-D", "lower(CI95(delta_ora)) > +0.1382"
        elif dlo > 0 and dhi < PRED_DELTA_LEGACY and dhi >= PRED_DELTA_DEDUPED:
            br, why = "X-PARTIAL-D", "resolved below the legacy magnitude"
        elif dlo > 0 and dhi < PRED_DELTA_DEDUPED:
            br, why = "X-BELOW-D", "resolved below BOTH magnitudes"
        elif dlo <= 0 <= dhi and dhi < PRED_DELTA_DEDUPED:
            br, why = "X-FREE-D", "0 in CI95(delta_ora) and upper < +0.0842"
        else:
            br, why = "X-INCONCLUSIVE-D", "none of the sub-table rows"
        return {"branch": br, "reason": why, "guard_fired": True,
                "r_ora_reported": False, "x_noise": noise}

    rlo, rhi = _lo(r_ora), _hi(r_ora)
    if not (_fin(dlo) and _fin(dhi)):
        return {"branch": "X-INCONCLUSIVE", "reason": "degenerate / absent CI",
                "guard_fired": False, "r_ora_reported": True, "x_noise": noise}
    sig = dlo > 0
    if sig and _fin(rlo) and _fin(rhi) and rlo <= PRED_LEGACY <= rhi:
        br, why = "X-CONFIRMED", "lower(CI95(delta_ora))>0 and 1.400 in CI95(R_ora)"
    elif sig and _fin(rlo) and rlo > PRED_LEGACY:
        br, why = "X-ABOVE", "lower(CI95(R_ora)) > 1.400"
    elif sig and _fin(rhi) and rhi < PRED_LEGACY and rhi >= PRED_DEDUPED:
        br, why = "X-PARTIAL", "upper(CI95(R_ora)) < 1.400 and >= 1.244"
    elif sig and _fin(rhi) and rhi < PRED_DEDUPED:
        br, why = "X-BELOW", "upper(CI95(R_ora)) < 1.244 — below BOTH predictions"
    elif (not sig) and dlo <= 0 <= dhi and dhi < PRED_DELTA_DEDUPED:
        br, why = "X-FREE", "0 in CI95(delta_ora) and upper < +0.0842"
    else:
        br, why = "X-INCONCLUSIVE", "none of rows 1-5"
    return {"branch": br, "reason": why, "guard_fired": False,
            "r_ora_reported": True, "x_noise": noise}


def xfree_window(d_ora: dict) -> dict:
    """READ_RULE §5 mandatory print (iii): the interval of POINT ESTIMATES for
    which `X-FREE` was reachable at the REALIZED se.

    `X-FREE` needs `0 in CI95(Δ)` AND `upper(CI95(Δ)) < +0.0842` simultaneously.
    With realized half-width `h`, a point estimate `p` reaches it iff
    `-h <= p <= h` and `p + h < 0.0842`, i.e. `p in [-h, min(h, 0.0842 - h))`.
    At `sd_Δ = 1.4` this requires `p <= +0.0015` — essentially zero or negative,
    so a NON-firing `X-FREE` is not evidence against the cap being free."""
    lo, hi, v = _lo(d_ora), _hi(d_ora), d_ora.get("value")
    if not (_fin(lo) and _fin(hi)):
        return {"half_width": None, "lo": None, "hi": None, "empty": None,
                "point_estimate": v, "reachable_for_point_estimate": None,
                "note": "CI absent — the window is undefined"}
    h = (hi - lo) / 2.0
    wlo = -h
    whi = min(h, PRED_DELTA_DEDUPED - h)
    empty = not (whi > wlo)
    needs_negative = bool(whi <= 0.0)
    reach = bool(_fin(v) and (wlo <= v < whi)) if not empty else False
    if empty:
        note = ("EMPTY at the realized se — X-FREE was UNREACHABLE, so its "
                "non-firing is not evidence against the cap being free")
    elif needs_negative:
        note = ("NEAR-EMPTY: at the realized se X-FREE required a strictly "
                "NEGATIVE point estimate, so its non-firing is not evidence "
                "against the cap being free (REVIEW_R1 §9)")
    else:
        note = ("X-FREE was reachable only for point estimates in [lo, hi) — "
                "at sd_Δ = 1.4 that bar is +0.0015, i.e. essentially zero")
    return {"half_width": h, "lo": wlo, "hi": whi, "empty": bool(empty),
            "requires_negative_point_estimate": needs_negative,
            "point_estimate": v, "reachable_for_point_estimate": reach,
            "note": note}


# --------------------------------------------------------------------------- #
# assembly of the READOUT blocks                                                #
# --------------------------------------------------------------------------- #
def ladder_block(boot: RootBoot, e: int, rows) -> dict:
    """`widening.b_ladder.E<e>` — `B{b}.{arb, ci95, se, z, n, n_roots}`."""
    out = {}
    for b in B_LADDER:
        key = f"arb_j4_E{e}_B{b}"
        if not any(key in r for r in rows):
            continue
        s = boot.stat(key)
        out[f"B{b}"] = {"arb": s["value"], "ci95": s["ci95"], "se": s["se_root"],
                        "z": s["z"], "n": s["n"], "n_roots": s["n_roots"],
                        "significant": s["significant"]}
    return out


def j_rider_block(rows, e: int, reps, seed) -> dict:
    """`widening.j_rider.<slice>` on the CAPPED plies of `rows` at evaluation
    width `e`. `Δ_ora` adjudicates; `Δ_arb` rides as the deployable quantity."""
    capped = [r for r in rows if r["capped_at_4"]]
    if not capped:
        return {"delta_ora": None, "ci95_ora": [None, None], "r_ora": None,
                "ci95_r_ora": None, "r_ora_reported": False,
                "ora_j4_ci95": [None, None],
                "delta_arb": None, "ci95_arb": [None, None], "n_capped": 0,
                "xfree_window": xfree_window({}), "n_roots": 0}
    b = RootBoot(capped, reps=reps, seed=seed)
    d_ora = b.stat(f"d_ora_E{e}")
    ora_j4 = b.stat(f"ora_j4_E{e}")
    ora_full = b.stat(f"ora_full_E{e}")
    d_arb = b.stat(f"d_arb_E{e}")
    # READ_RULE §5 pre-branch guard. When it fires the ratio is DEGENERATE and is
    # NOT reported: both `r_ora` and `ci95_r_ora` go to `null` TOGETHER, and
    # `r_ora_reported` is the witness that distinguishes "legitimately null" from
    # "broken" (READ_RULE §1.2's CLOSED allow_null table, rows 1-2). Emitting
    # `[null, null]` for the CI instead of `null` would put the two addresses in
    # different states at the same moment, which the table forbids.
    guard = not (_fin(_lo(ora_j4)) and _lo(ora_j4) > 0)
    r = ({"value": None, "ci95": None, "se_root": None}
         if guard else b.ratio(f"ora_full_E{e}", f"ora_j4_E{e}"))
    return {
        "e_worlds": e,
        "delta_ora": d_ora["value"], "ci95_ora": d_ora["ci95"],
        "se_ora": d_ora["se_root"], "z_ora": d_ora["z"],
        "significant_ora": d_ora["significant"],
        "r_ora": r["value"], "ci95_r_ora": r["ci95"],
        "r_ora_reported": not guard,
        "ora_j4": ora_j4["value"], "ora_j4_ci95": ora_j4["ci95"],
        "ora_full": ora_full["value"], "ora_full_ci95": ora_full["ci95"],
        "delta_arb": d_arb["value"], "ci95_arb": d_arb["ci95"],
        "n_capped": len(capped), "n_roots": b.g,
        "xfree_window": xfree_window(d_ora),
        "_d_ora": d_ora, "_r_ora": r, "_ora_j4": ora_j4, "_d_arb": d_arb,
    }


def _strip_private(obj):
    """Drop the `_`-prefixed working values before the block is published."""
    if isinstance(obj, dict):
        return {k: _strip_private(v) for k, v in obj.items()
                if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_strip_private(v) for v in obj]
    return obj


# --------------------------------------------------------------------------- #
# the markdown REPORT (blindness-protected)                                     #
# --------------------------------------------------------------------------- #
def _f(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return str(x)
    try:
        return "n/a" if x != x else f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def _ci(c, nd=4):
    c = c or [None, None]
    return f"[{_f(c[0], nd)}, {_f(c[1], nd)}]"


def render_md(v: dict) -> str:
    """The harness REPORT. On ANY gate FAIL it prints GATE INPUTS ONLY — no
    `arb`, no `ora`, no Δ, no CI, no per-position statistic (READ_RULE §7). It
    never prints a `G-REPLICATE` z on any branch."""
    w = v["widening"]
    gates = w["gates_summary"]
    L = ["# TIE-ARBITER WIDENING — READ-OUT (rungs 2 + 3)", "",
         f"generated: {v['generated_utc']}", "",
         "> Significance is ONE test everywhere: `lower(CI95) > 0` on the",
         "> percentile ROOT bootstrap (2,000 reps, seed 20260819, cluster = root).",
         "> `G-REPLICATE` z-statistics are SEALED and appear nowhere in this file.",
         "", "## Gates", "",
         "| gate | verdict | resolved_at |", "|---|---|---|"]
    for name, g in sorted(gates.items()):
        L.append(f"| `{name}` | {'PASS' if g['ok'] else 'FAIL'} | "
                 f"`{g.get('resolved_at') or 'UNRESOLVED'}` |")
    L += ["",
          f"analyzer-owned gates: **{'ALL PASS' if w['gates_ok'] else 'FAIL'}**",
          ""]

    if not w["gates_ok"]:
        L += ["## ⛔ W-UNREADABLE — GATE INPUTS ONLY", "",
              "READ_RULE §7: on any gate FAIL this report prints gate inputs and",
              "nothing else — no `arb`, no `ora`, no Δ, no CI, no per-position",
              "statistic — so a fixing session can read it and stay blind.", "",
              "```json",
              # GATE INPUTS ONLY. The config block is deliberately NOT dumped:
              # it carries the ladder/E levels, and a fixing session has no use
              # for anything but the failing gate's own inputs.
              json.dumps({"gates": w["gates"],
                          "completion": w["completion"],
                          # R4 §2b: the exclusion block is ALWAYS printed,
                          # whether or not anything was excluded — and it is a
                          # gate input, so it is safe on a gate-fail report
                          "exclusions": w.get("exclusions"),
                          "corpus_union": w.get("corpus_union"),
                          "stage1_replication": w["stage1_replication"],
                          "plan_dirs": w["config"]["plan_dirs"],
                          "position_counts": w["config"]["counts"]},
                         indent=2, sort_keys=True, default=str),
              "```", "",
              "Nothing is licensed. No branch of either rung fires — not even",
              "for information.", ""]
        return "\n".join(L)

    b2, b3 = w["branch"]["rung2"], w["branch"]["rung3"]
    L += ["## Rung 2 — `B > 16` (S1, primary `Δ(16→64)` at E = 64)", "",
          f"**BRANCH: `{b2['branch']}`** — {b2['reason']}", "",
          f"- `Δ(16→64)` = {_f(w['delta']['d_16_64']['value'])} "
          f"CI95 {_ci(w['delta']['d_16_64']['ci95'])} "
          f"se_root {_f(w['delta']['d_16_64']['se_root'])} "
          f"(committed floor +{D1664_FLOOR})",
          f"- `Δ(16→32)` = {_f(w['delta']['d_16_32']['value'])} "
          f"CI95 {_ci(w['delta']['d_16_32']['ci95'])} — reported with its CI, "
          f"**never a branch input on its own**",
          # ⚠️ READ_RULE §3: the REALIZED quantities printed BESIDE the
          # PRE-REGISTERED brackets, on the report surface — a requirement
          # already in force, not a new disclosure.
          f"- **realized `se` {_f((w['delta'].get('se_vs_bracket') or {}).get('realized'))} "
          f"vs the pre-registered §3 bracket "
          f"{_ci((w['delta'].get('se_vs_bracket') or {}).get('bracket'))} — "
          f"**{(w['delta'].get('se_vs_bracket') or {}).get('position')}**"
          + ("**. The design's variance model under-predicted; this changes NO "
             "branch — the REALIZED CI governs and the floor is fixed — and it "
             "is printed because §3 requires the realized quantity beside its "
             "bracket."
             if (w['delta'].get('se_vs_bracket') or {}).get('position') == "ABOVE"
             else "**.")
          + f" `sd_Δ` bracket {_ci(w['delta'].get('sd_delta_bracket'))}.", "",
          "| B | arb (E=64) | CI95 | se | arb (E=16) | CI95 | se |",
          "|---|---|---|---|---|---|---|"]
    e64, e16 = w["b_ladder"].get("E64", {}), w["b_ladder"].get("E16", {})
    for b in B_LADDER:
        k = f"B{b}"
        a, c = e64.get(k), e16.get(k)
        if not a and not c:
            continue
        L.append(f"| {b} | {_f((a or {}).get('arb'))} | {_ci((a or {}).get('ci95'))} "
                 f"| {_f((a or {}).get('se'))} | {_f((c or {}).get('arb'))} | "
                 f"{_ci((c or {}).get('ci95'))} | {_f((c or {}).get('se'))} |")
    L += ["",
          "A null here means **\"no rung above 16 is worth ≥ +0.04 pts/tied "
          "ply\"**, NOT `Δ = 0`: the saturating-exp (+0.017) and √B-noise "
          "(+0.021) models are not resolved by this design.", "",
          "## Rung 3 — `J > 4` (S2 capped plies, primary `Δ_ora`)", ""]
    if not w["completion"].get("rung3_bought", True):
        L += ["**THE RUNG-3 QUESTION WAS NOT BOUGHT.**", "",
              w["completion"]["rung3_note"], "",
              "Its branch table is not adjudicated and its riders are not "
              "printed. The `J` question is neither answered, nor null, nor "
              "inconclusive — it was not purchased.", ""]
        L += _exclusion_lines(w)
        return "\n".join(L)
    if b3.get("status") == VOID_S2:
        # ⚠️ §D4.16 — no `X-` token may appear anywhere in this report on the
        # void path, and the forbidden readings are printed WITH the status.
        ob = b3["obligation_inherited_by"]
        L += [f"**STATUS: `{b3['status']}`** — {b3['reason']}", "",
              f"- **bought: `true`** at `n2 = {b3['n2']}` "
              f"(`{b3['n2_source']}`) — the J question WAS purchased and then "
              f"lost to a stratum void",
              f"- **estimand_read: `false`** — the branch table was NEVER "
              f"evaluated",
              f"- witness: `{b3['witness']['address']}` = "
              f"`{b3['witness']['value']}` (`{b3['witness']['source']}`)",
              f"- **obligation inherited by `{ob['successor']}`** — "
              f"{ob['includes']}", "",
              "**THIS READING IS FORBIDDEN AS:**", ""]
        L += [f"- {r}" for r in b3["forbidden_readings"]]
        L += ["", "### S1-side rung-3 riders — REPORTED, ADJUDICATING NOTHING", "",
              w["j_rider"]["s1_riders_prohibition"], "",
              f"- S1 replication `Δ_ora` = "
              f"{_f(w['j_rider']['s1_replication'].get('delta_ora'))} "
              f"CI95 {_ci(w['j_rider']['s1_replication'].get('ci95_ora'))} "
              f"(n_capped {w['j_rider']['s1_replication'].get('n_capped')})",
              f"- interaction `arb_full(64−16)` = "
              f"{_f((w['j_rider']['interaction'].get('arb_full_64_minus_16') or {}).get('value'))} "
              f"(n_capped_s1 {w['j_rider']['interaction'].get('n_capped_s1')})", ""]
        L += _exclusion_lines(w)
        return "\n".join(L)
    L += [f"**BRANCH: `{b3['branch']}`** — {b3['reason']}", ""]
    s2 = w["j_rider"]["s2"]
    L += [f"- `Δ_ora` = {_f(s2['delta_ora'])} CI95 {_ci(s2['ci95_ora'])} "
          f"(n_capped {s2['n_capped']})",
          f"- `R_ora` = {_f(s2['r_ora'])} CI95 {_ci(s2['ci95_r_ora'])} "
          f"— reported: {_f(s2['r_ora_reported'])}",
          f"- `ora_J4` CI95 {_ci(s2['ora_j4_ci95'])} (the pre-branch guard)",
          f"- `Δ_arb` = {_f(s2['delta_arb'])} CI95 {_ci(s2['ci95_arb'])} "
          f"— deploy rider",
          f"- `X-NOISE` rider fired: {_f(b3.get('x_noise'))}", "",
          "**X-FREE attainability at the REALIZED se:** "
          f"window [{_f(s2['xfree_window']['lo'])}, "
          f"{_f(s2['xfree_window']['hi'])}) — "
          f"{'EMPTY' if s2['xfree_window']['empty'] else 'non-empty'}. "
          f"{s2['xfree_window']['note']}", "",
          "Mandatory prints: this design **cannot separate 1.400 from 1.244** "
          "(Δ = 0.054 ⇒ z 1.28–2.00); **+0.0842 is unresolved at the top of the "
          "`sd_Δ` bracket** (z 1.995 at `sd_Δ` = 1.4).", "",
          "### Riders", ""]
    s1r = w["j_rider"]["s1_replication"]
    inter = w["j_rider"]["interaction"]
    L += [f"- S1 replication (`E=64`, non-adjudicating): `Δ_ora` "
          f"{_f(s1r['delta_ora'])} CI95 {_ci(s1r['ci95_ora'])} "
          f"(n_capped {s1r['n_capped']})",
          f"- B×J interaction: `arb_full(64)−arb_full(16)` "
          f"{_f((inter.get('arb_full_64_minus_16') or {}).get('value'))} · "
          f"`arb_full(16)−arb_J4(16)` "
          f"{_f((inter.get('arb_full_16_minus_j4_16') or {}).get('value'))}",
          f"- `D-DRAW`: n_checked {w['j_rider']['d_draw']['n_checked']}, "
          f"agreement_rate {_f(w['j_rider']['d_draw']['agreement_rate'])} "
          f"— reports the magnitude of `I7`'s dedupe-partition conditional; "
          f"adjudicates nothing.",
          f"- Shared cell `arb(B=16, J≤4, E=16)` = "
          f"{_f((e16.get('B16') or {}).get('arb'))} "
          f"CI95 {_ci((e16.get('B16') or {}).get('ci95'))} — ONE number, "
          f"declared shared, identical in both rungs' sections.", "",
          "### Mandatory riders (READ_RULE §6)", "",
          "`R1` σ-inflation (within-run CRN-paired primaries take NONE; banked "
          "contrasts take 2×) · `R2` translation caveat (Stage-1b under-predicted "
          "Phase B's game cell by 3.9×; no game cell is sized here) · `R3` "
          "`I7-draw-scope` (instrument draw, NOT nested in `j`; licence "
          "conditional on the unverified dedupe partition) · `R4` two currencies, "
          "never converted · `R5` PRODUCTION.yaml untouched, no claim minted · "
          "`R6` the N4 waiver above B=16 is OPEN, re-priced at the flip decision · "
          "`R7` the phone is out of scope · `R8` `|z| < 2` is never \"refuted\".",
          ""]
    L += _exclusion_lines(w)
    return "\n".join(L)


def _exclusion_lines(w: dict) -> list:
    """R4 §7a's mandatory additions: the supply chain against committed, the
    digest-exclusion block (ALWAYS, whether or not anything was excluded), and
    the predecessor's disposition in one line."""
    c, x, p = w["completion"], w.get("exclusions") or {}, w.get("predecessor") or {}
    u = w.get("corpus_union") or {}
    L = ["", "## R4 §7a — supply, composition, exclusions, predecessor", ""]
    # R4-0.5 §3: R4's `n` is a MIXTURE and the reader must see its composition.
    L += ["### Corpus composition — RETAINED vs FRESH", ""]
    if not u.get("present"):
        L += ["`CORPUS_UNION.json` was not supplied to the analyzer, so the "
              "retained-vs-fresh split is UNRESOLVED here — read it at the "
              "stamp's own address.", ""]
    else:
        tot = u.get("totals") or {}
        L += ["| stratum | retained (135e9) | fresh (137e9) | origin commit | copied |",
              "|---|---|---|---|---|"]
        for s, v in sorted(u["by_stratum"].items()):
            oc = (v.get("origin_commit") or "untracked")[:12]
            L.append(f"| {s} | {v.get('n_retained')} | {v.get('n_fresh')} | "
                     f"`{oc}` | {_f(v.get('copied_not_symlinked'))} |")
        L += ["",
              f"**Totals:** {tot.get('n_retained')} retained + "
              f"{tot.get('n_fresh')} fresh = {tot.get('n_total')} "
              f"(retained fraction {_f(tot.get('retained_fraction'), 3)}). "
              f"The retained positions were read READ-ONLY out of the SPENT "
              f"R3.3 run and **COPIED** in — never symlinked, and "
              f"`shared_run/` was never written to.", "",
              u.get("note", ""), ""]
    L += ["### Supply and floors", "",
         f"- **Supply realized vs committed:** S1 {c['s1_n']} against floor "
         f"{c['s1_floor']} (committed n₁ {c.get('n1_committed')}); "
         f"S2 capped {c['s2_n']} against floor {c['s2_floor']} "
         f"(committed n₂ {c.get('n2_committed')}); option "
         f"`{c.get('option_label')}`. Both counts are AFTER the §2b exclusions.",
         "", "### Digest exclusions (R4 §2b — printed whether or not any fired)",
         ""]
    if not x.get("present"):
        L += ["`GATE_DISJOINT.json` was not supplied to the analyzer, so the "
              "exclusion counters are UNRESOLVED here — read them at the gate "
              "file's own address.", ""]
    else:
        L += ["| stratum | n_excluded | rate | bound | denominator | source | void |",
              "|---|---|---|---|---|---|---|"]
        for s, v in sorted(x["by_stratum"].items()):
            L.append(f"| {s} | {v['n_excluded']} | {_f(v['rate'], 5)} | "
                     f"{v['bound_n']} | {v['denominator']} | "
                     f"`{v['denominator_source']}` | {_f(v['void'])} |")
        L += ["",
              "`n_excluded` = `carried` (measured on the PROBE build, which is "
              "where the bound is judged) + `residual` (fresh collisions in the "
              "FINAL build, expected 0). A nonzero `residual` is additionally a "
              "**determinism defect**."]
        L += ["", "The digest is a function of the **board alone**, computed at "
              "corpus-build time **before any value exists** — the exclusion is "
              "outcome-independent by construction, which is exactly why it is "
              "legitimate here and was not in the 2026-08-14 open-city void. "
              "A stratum over the bound is **VOID, not excluded-and-continued**, "
              "and **a VOID is not curable by generating more games**.", ""]
    if p:
        L += [f"- **Predecessor:** pair `{p.get('pair')}` is "
              f"{p.get('disposition')}. {p.get('corpus')}. "
              f"{p.get('sizing_dependence')}.", ""]
    return L


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan-dir-s1", required=True)
    ap.add_argument("--plan-dir-s2", default=None)
    ap.add_argument("--if-records-s1", action="append", default=None)
    ap.add_argument("--arb-records-s1", action="append", default=None)
    ap.add_argument("--if-records-s2", action="append", default=None)
    ap.add_argument("--arb-records-s2", action="append", default=None)
    ap.add_argument("--smoke-manifest", action="append", default=None,
                    help="per-judge SMOKE_MANIFEST_S1_<judge>.json (repeatable)")
    ap.add_argument("--stage1b-ladder", required=True,
                    help="the banked Stage-1b (B<=16, E=16) ladder the "
                         "G-REPLICATE envelope is taken against: "
                         '{"source":…, "rungs": {"1": {"arb":…, "se":…}, …}}')
    ap.add_argument("--d-draw", default=None,
                    help="D-DRAW report: {n_checked, agreement_rate}")
    ap.add_argument("--floors", default=None,
                    help="RUN/FLOORS.json — the committed G-COMPLETE floors "
                         "(R4 §2a). Without it the R3.3 constants are used and "
                         "the read-out says so")
    ap.add_argument("--champ-games-verify", action="append", default=None,
                    help="CHAMP_GAMES_VERIFY{,_EXT,_TOPUP}.json (repeatable) — "
                         "G-BAND's N-file form (R4 §2c)")
    ap.add_argument("--run-manifest", action="append", default=None,
                    help="RUN_MANIFEST_{S1,S2}.json (repeatable) — G-SALT's "
                         "primary. Scoring-time emissions, so the pre-scoring "
                         "address audit cannot bind them; the analyzer can")
    ap.add_argument("--leg-manifest", action="append", default=None,
                    help="leg manifest(s) for G-SALT's resolved_config fallback")
    ap.add_argument("--corpus-union", default=None,
                    help="RUN/corpus/CORPUS_UNION.json — the retained-vs-fresh "
                         "composition of the corpus (R4-0.5 §3). R4's n is a "
                         "MIXTURE and the read-out must show its composition")
    ap.add_argument("--gate-disjoint", default=None,
                    help="RUN/GATE_DISJOINT.json — surfaces the R4 §2b "
                         "digest-exclusion counters on the READOUT")
    ap.add_argument("--m-expected-s1", type=int, default=M_EXPECTED_S1)
    ap.add_argument("--m-expected-s2", type=int, default=M_EXPECTED_S2)
    ap.add_argument("--boot-reps", type=int, default=BOOT_REPS)
    ap.add_argument("--boot-seed", type=int, default=BOOT_SEED)
    ap.add_argument("--rnd-seed", type=int, default=RND_SEED)
    ap.add_argument("--parity-base", type=int, choices=(0, 1), default=PARITY_BASE)
    ap.add_argument("--e-levels-s1", default=",".join(str(e) for e in E_LEVELS_S1))
    ap.add_argument("--e-levels-s2", default=",".join(str(e) for e in E_LEVELS_S2))
    ap.add_argument("--out-dir", required=True,
                    help="RUN/verdicts — READOUT.{json,md}, per_position_*.jsonl, "
                         "SEALED_G_REPLICATE.json")
    return ap.parse_args(argv)


def _load_records(roots):
    if not roots:
        return {}, {}, [], []
    by_rid, present, not_ok, resolved = TA.merge_arb_records(roots)
    return by_rid, present, not_ok, resolved


#: §D4.18(d) — the move-aside is ENFORCED, not remembered.
INVALID_SUFFIX_CONVENTION = ".invalid-<reason>"


def refuse_to_overwrite(out_dir: Path) -> None:
    """A superseded READOUT is EVIDENCE and stays readable; what must be
    impossible is mistaking it for a verdict (§D4.7's discipline, §D4.18(d)).

    So the analyzer refuses to overwrite one. The move-aside then leaves a
    readable record of the gap instead of a silent replacement.
    """
    existing = [p for p in (Path(out_dir) / "READOUT.json",
                            Path(out_dir) / "READOUT.md",
                            Path(out_dir) / "SEALED_G_REPLICATE.json")
                if p.is_file()]
    if not existing:
        return
    raise SystemExit(
        "REFUSING to overwrite an existing read-out: "
        + ", ".join(str(p) for p in existing)
        + f". §D4.18(d): a superseded artifact is EVIDENCE and stays readable — "
        f"what must be impossible is mistaking it for a verdict. Move it aside "
        f"with a suffix that makes invalidity obvious ON SIGHT "
        f"(`READOUT.json{INVALID_SUFFIX_CONVENTION}`, e.g. "
        f"`READOUT.json.invalid-empty-rowset`), the same discipline as "
        f"`CORPUS_UNION.defective_r4.5.json`, and NAME THE MOVE in the "
        f"read-out's provenance so the gap in the record is documented rather "
        f"than silent. Then re-run.")


def main(argv=None) -> int:
    a = parse_args(argv)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # ⚠️ BEFORE any work: a stale read-out must be moved aside, never overwritten
    refuse_to_overwrite(out_dir)

    e_s1 = tuple(int(x) for x in str(a.e_levels_s1).split(",") if x.strip())
    e_s2 = tuple(int(x) for x in str(a.e_levels_s2).split(",") if x.strip())

    strata = {}
    for tag, plan_dir, ifr, arbr, e_lev, m_exp in (
            ("S1", a.plan_dir_s1, a.if_records_s1, a.arb_records_s1, e_s1,
             a.m_expected_s1),
            ("S2", a.plan_dir_s2, a.if_records_s2, a.arb_records_s2, e_s2,
             a.m_expected_s2)):
        if not plan_dir:
            continue
        bundle = AT.load_plan(plan_dir)
        if_by, if_present, if_notok, if_res = _load_records(ifr)
        arb_by, arb_present, arb_notok, arb_res = _load_records(arbr)
        rows, counts, arms_g, crn, unc, failed_block = build_rows(
            bundle["arms"], if_by, arb_by, e_levels=e_lev, m_expected=m_exp,
            parity_base=a.parity_base, rnd_seed=a.rnd_seed, stratum_tag=tag)
        strata[tag] = {"plan": bundle["plan"], "plan_dir": str(plan_dir),
                       "rows": rows, "counts": counts, "arms": arms_g,
                       "failed_records": failed_block,
                       "crn": crn, "uncapped": unc, "e_levels": list(e_lev),
                       "m_expected": m_exp,
                       "records": {"if": if_res, "arb": arb_res,
                                   "if_present": if_present,
                                   "arb_present": arb_present,
                                   "n_if_not_ok": len(if_notok),
                                   "n_arb_not_ok": len(arb_notok)}}

    if "S1" not in strata:
        raise SystemExit("REFUSING: S1 is the rung-2 stratum and is mandatory")

    rows_s1 = strata["S1"]["rows"]
    rows_s2 = strata.get("S2", {}).get("rows", [])

    # ---- per-position fallback surfaces (READ_RULE §4/§5) ------------------- #
    for tag, rows in (("s1", rows_s1), ("s2", rows_s2)):
        p = out_dir / f"per_position_{tag}.jsonl"
        p.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))

    # ---- rung 2 ------------------------------------------------------------ #
    boot1 = RootBoot(rows_s1, reps=a.boot_reps, seed=a.boot_seed)
    b_ladder = {"m_expected": a.m_expected_s1,
                "m_observed": sorted({r["m"] for r in rows_s1}),
                "e_levels": list(e_s1)}
    for e in e_s1:
        b_ladder[f"E{e}"] = ladder_block(boot1, e, rows_s1)
    e_primary = e_s1[0]
    delta = {
        "d_16_64": boot1.stat(f"d_16_64_E{e_primary}"),
        "d_16_32": boot1.stat(f"d_16_32_E{e_primary}"),
        "e_worlds": e_primary,
        "committed_floor_d_16_64": D1664_FLOOR,
        "committed_floor_d_16_32": D1632_FLOOR,
        # READ_RULE §3 — the realized se BESIDE its pre-registered bracket
        "se_vs_bracket": vs_bracket(
            boot1.stat(f"d_16_64_E{e_primary}").get("se_root"), SE_BRACKET),
        "sd_delta_bracket": list(SD_DELTA_BRACKET),
    }
    # ONE constructor, here and at the G-REPLICATE site below (see `ladder_stat`)
    arb64_stat = ladder_stat(b_ladder, e_primary, 64)
    arb16_stat = ladder_stat(b_ladder, e_primary, 16)
    rung2 = decide_rung2(delta["d_16_64"], arb64_stat, arb16_stat)

    # ---- rung 3 ------------------------------------------------------------ #
    j_s2 = j_rider_block(rows_s2, e_s2[0] if e_s2 else 16, a.boot_reps, a.boot_seed)
    j_s1 = j_rider_block(rows_s1, e_primary, a.boot_reps, a.boot_seed)
    capped_s1 = [r for r in rows_s1 if r["capped_at_4"]]
    binter = RootBoot(capped_s1, reps=a.boot_reps, seed=a.boot_seed)
    interaction = {
        "arb_full_64_minus_16": binter.stat(f"i_full_64_minus_16_E{e_primary}"),
        "arb_full_16_minus_j4_16": binter.stat(f"d_arb_E{e_primary}"),
        "n_capped_s1": len(capped_s1), "e_worlds": e_primary,
    }
    # ⭐ §D4.16 — the VOID-STRATUM GUARD, and it fires on a POSITIVE WITNESS
    # CONJOINED with absent inputs, never on absence alone. If S2 inputs are
    # missing and `GATE_DISJOINT::digest_exclusions.S2.void` is not literally
    # true, this RAISES: missing inputs are exactly what D4 was — an assembly
    # defect wearing the shape of a decision — and a guard keyed on absence
    # would have silently blessed D4's 551 never-scored rids.
    s2_witness = void_stratum_witness(a.gate_disjoint, "S2")
    s2_inputs_present = bool(rows_s2)
    rung3_void = None
    if s2_inputs_present:
        rung3 = decide_rung3(j_s2["_d_ora"], j_s2["_r_ora"], j_s2["_ora_j4"],
                             j_s2["_d_arb"])
    elif s2_witness["void"]:
        rung3_void = void_rung3_block(s2_witness, n2=_floors_n2(a.floors),
                                      floors_source=(str(a.floors) + "::n2")
                                      if a.floors else None)
        rung3 = rung3_void
    else:
        raise SystemExit(
            "REFUSING: S2 inputs are ABSENT and there is no positive void "
            f"witness ({s2_witness['address']} = {s2_witness['value']!r}; "
            f"{s2_witness.get('why')}). ABSENCE IS NOT A VOID — missing inputs "
            "are an assembly defect wearing the shape of a decision (that is "
            "exactly what D4 was: 551 committed rids silently never scored). "
            "Supply the S2 inputs, or supply the GATE_DISJOINT.json whose "
            "digest_exclusions.S2.void is true.")

    # `D-DRAW` is W9's probe (`RUN/D_DRAW.json`). Until it has run every
    # `d_draw.*` address is `null`, and `d_draw_ran` is the witness that makes
    # that null legitimate rather than broken (READ_RULE §1.2, row 3). It
    # reports the MAGNITUDE of rider `I7`'s unverified dedupe-partition
    # conditional and adjudicates NOTHING.
    d_draw = {"d_draw_ran": False, "n_checked": None, "n_agree": None,
              "agreement_rate": None, "n_unreconstructible": None,
              "git_rev": None, "source": a.d_draw,
              "adjudicates": "nothing — a reported magnitude, never a branch input"}
    if a.d_draw and Path(a.d_draw).is_file():
        dd = json.loads(Path(a.d_draw).read_text())
        d_draw.update({
            "d_draw_ran": True,
            "n_checked": dd.get("n_checked"),
            "n_agree": dd.get("n_agree"),
            "agreement_rate": dd.get("agreement_rate"),
            "n_unreconstructible": dd.get("n_unreconstructible"),
            "git_rev": dd.get("git_rev"),
            "source": str(a.d_draw)})

    # ---- gates ------------------------------------------------------------- #
    crn = crn_gate({t: s["crn"] for t, s in strata.items()},
                   a.smoke_manifest or [])
    unc = uncapped_gate({t: s["plan"] for t, s in strata.items()},
                        {t: s["uncapped"] for t, s in strata.items()})
    arms = arms_gate_block({t: s["arms"] for t, s in strata.items()})

    floors = None
    if a.floors:
        import floors as FL                                        # noqa: E402
        floors = FL.load(a.floors)
    completion = completion_block(rows_s1, rows_s2, floors,
                                  void_witness=void_stratum_witness(
                                      a.gate_disjoint, "S2"))
    salt = salt_gate(a.run_manifest or [],
                     {t_: s["plan"] for t_, s in strata.items()},
                     {t_: AT.load_plan(s["plan_dir"])["arms"]
                      for t_, s in strata.items()},
                     a.leg_manifest or [])
    band = band_block(a.champ_games_verify or [])
    exclusions = exclusions_block(a.gate_disjoint)
    union = union_block(a.corpus_union)

    ref = json.loads(Path(a.stage1b_ladder).read_text())
    e16_ladder = b_ladder.get("E16", {})
    # ⚠️ the SAME constructor as the rung-2 site. The previous `or {}` here left
    # `ci95` PRESENT WITH None, which `.get("ci95", [None, None])` inside the
    # gate could not default away — and the next subscript raised.
    repl_public, repl_sealed = replication_gate(
        e16_ladder, ladder_stat(b_ladder, 16, 16), ref)
    (out_dir / "SEALED_G_REPLICATE.json").write_text(
        json.dumps(repl_sealed, indent=2, sort_keys=True))

    gates = {"crn": crn, "uncapped": unc, "arms": arms, "band": band,
             "salt": salt}
    gates_summary = {
        "G-CRN": {"ok": crn["ok"], "resolved_at": crn["resolved_at"]},
        "G-UNCAPPED": {"ok": unc["ok"], "resolved_at": unc["resolved_at"]},
        "G-ARMS": {"ok": arms["ok"], "resolved_at": arms["resolved_at"]},
        "G-BAND": {"ok": band["ok"], "resolved_at": band["resolved_at"]},
        "G-SALT": {"ok": salt["ok"], "resolved_at": salt["resolved_at"]},
        "G-COMPLETE": {"ok": completion["ok"],
                       "resolved_at": completion["resolved_at"]},
        "G-REPLICATE": {"ok": repl_public["pass"],
                        "resolved_at": repl_public["resolved_at"]},
    }
    gates_ok = all(g["ok"] for g in gates_summary.values())

    widening = {
        "gates": gates,
        "gates_summary": gates_summary,
        "gates_ok": gates_ok,
        "completion": completion,
        # §D4.18(3)+(6) — TYPED, per stratum, printed whether or not anything
        # failed, and carrying the selection-effect sentence verbatim.
        "failed_records": {t: s["failed_records"] for t, s in strata.items()},
        "exclusions": exclusions,
        "corpus_union": union,
        "predecessor": {
            "pair": "604edc83",
            "disposition": "SPENT-BY-GATE-FAILURE — frozen history; never "
                           "amended, revived or re-read",
            "corpus": "band 135e9's 850 games are REUSABLE INPUT, not a prior "
                      "result: the run stopped PRE-SCORING, so no arb, ora, "
                      "delta, CI or per-position value was ever computed",
            "sizing_dependence": "R4's n is sized from rates measured on that "
                                 "same corpus, so it is NOT statistically "
                                 "independent of its STRUCTURE — a "
                                 "nuisance-parameter read, never an estimand "
                                 "dependence (PREREG_FAILURE §3.4)",
        },
        "stage1_replication": repl_public,
        "delta": delta,
        "b_ladder": b_ladder,
        "j_rider": {
            # ⚠️ on the void path the S2 slice is replaced by an explicit void
            # stub: its degenerate form still carries an `xfree_window` NOTE
            # naming `X-FREE`, and §D4.16 forbids ANY X-token anywhere in the
            # READOUT on this path.
            "s2": ({"void": True, "status": VOID_S2, "n_capped": 0,
                    "note": "no S2 stratum was read — see branch.rung3"}
                   if rung3_void else _strip_private(j_s2)),
            # ⚠️ §D4.16: the S1-side rung-3 riders are REAL MEASUREMENTS and are
            # reported — suppressing measured quantities is worse — but the
            # prohibition travels WITH the number, because inferring a rung-3
            # branch from them is the live risk of reporting them at all.
            "s1_riders_prohibition": (S1_RIDER_PROHIBITION if rung3_void
                                      else None),
            # ⚠️ the rider's `xfree_window` is an ATTAINABILITY ANNOTATION for a
            # branch that was never evaluated — with rung 3 void it has no
            # referent, and its explanatory note names an X-token, which §D4.16
            # forbids anywhere in this READOUT. Dropped WITH its reason, never
            # silently.
            "s1_replication": dict(
                _strip_private(j_s1),
                **({"adjudicates": S1_RIDER_PROHIBITION,
                    "xfree_window": {
                        "void": True,
                        "note": "attainability annotation DROPPED: with rung 3 "
                                "void there is no branch for it to annotate, "
                                "and no branch token may appear in this "
                                "read-out"}}
                   if rung3_void else {})),
            "interaction": dict(interaction,
                                **({"adjudicates": S1_RIDER_PROHIBITION}
                                   if rung3_void else {})),
            "d_draw": d_draw,
        },
        "branch": {
            "rung2": rung2 if gates_ok else
            {"branch": "W-UNREADABLE",
             "reason": "a gate binding this rung FAILED; no branch fires"},
            # ⚠️ the VOID takes precedence over the gate-fail substitution: a
            # stratum a pre-registered rule voided is unreadable for a reason
            # that is not a gate failure, and `W-UNREADABLE` would mis-state it.
            "rung3": rung3_void if rung3_void else (
                rung3 if gates_ok else
                {"branch": "W-UNREADABLE",
                 "reason": "a gate binding this rung FAILED; no branch fires"}),
        },
        "config": {
            "b_ladder": list(B_LADDER),
            "e_levels_s1": list(e_s1), "e_levels_s2": list(e_s2),
            "m_expected_s1": a.m_expected_s1, "m_expected_s2": a.m_expected_s2,
            "boot_reps": a.boot_reps, "boot_seed": a.boot_seed,
            "rnd_seed": a.rnd_seed, "parity_base": a.parity_base,
            "significance": "lower(CI95) > 0 on the percentile root bootstrap",
            "pooling": "S1 and S2 are NEVER pooled (different E ⇒ different ora)",
            "plan_dirs": {t: s["plan_dir"] for t, s in strata.items()},
            "records": {t: s["records"] for t, s in strata.items()},
            "counts": {t: s["counts"] for t, s in strata.items()},
            "stage1b_ladder": str(a.stage1b_ladder),
        },
    }
    # §D4.18(d): the move-aside must be NAMED in the read-out's provenance, so
    # the gap in the record is documented rather than silent. Detected from the
    # artifacts themselves — the executor moves the file, the analyzer records
    # it, and neither has to remember.
    superseded = sorted(str(p.name) for p in out_dir.glob("*.invalid-*"))
    verdict = {"generated_utc": AT._now_utc(),
               "run": "tiearb_widening_20260817 shared_run_r4",
               "provenance": {
                   "superseded_artifacts": superseded,
                   "note": ("a superseded read-out is EVIDENCE and stays "
                            "readable; what must be impossible is mistaking it "
                            "for a verdict. The analyzer REFUSES to overwrite "
                            "one, so this list is the documented gap in the "
                            "record rather than a silent replacement."
                            if superseded else
                            "no superseded read-out was moved aside for this run"),
               },
               "widening": widening}

    (out_dir / "READOUT.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True, default=str))
    (out_dir / "READOUT.md").write_text(render_md(verdict))
    print(f"[widening] READOUT -> {out_dir / 'READOUT.json'}")
    print(f"[widening] report  -> {out_dir / 'READOUT.md'}")
    print(f"[widening] gates_ok = {gates_ok} | rung2 = "
          f"{widening['branch']['rung2']['branch']} | rung3 = "
          f"{widening['branch']['rung3']['branch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
