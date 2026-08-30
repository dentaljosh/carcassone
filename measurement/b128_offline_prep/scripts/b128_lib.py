#!/usr/bin/env python3
"""B=128 offline capture-ladder extension — shared library.

Loads the banked shared_run_r4 S1 instrument, assembles the arms x worlds
matrices exactly as `scripts/tiletie/analyze_widening.build_rows` does, and
evaluates the capture ladder with the PUBLISHED primitives:

    analyze_tiletie.parity_indices     (the cross-fit parity split)
    analyze_tiearb2.arb_at_budget      (select on sorted(sel)[:B], price on eva)
    analyze_widening._sym              (mean of the two folds)

Nothing in the estimator is re-derived here. The arm-order / J=4 plumbing IS
re-stated (build_rows is monolithic and also loads records), and it is validated
by the bit-identity gate in `gate_identity.py` — see PREREG.md §3, G-ID-1.

The M=256 extension is legal because `world_seed/playout_seed =
sha256(tag|rid|j|salt)` and M never enters the derivation (PREREG.md §1).
"""
from __future__ import annotations

import glob
import json
import os
import struct
import sys
from collections import defaultdict

REPO = "/home/doctor/projects/carcassone"
#: Repo/worktree root the corpus + published analyzers are read from. Overridable
#: with CARC_WT so the runner can execute on a second box out of a share copy
#: (the laptop's repo root, whose corpus + `scripts/tiletie` are the same
#: committed files). Values are box-invariant: the rust playout is bit-identical.
WT = os.environ.get("CARC_WT") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
for _p in (os.path.join(WT, "scripts", "tiletie"),
           os.path.join(WT, "scripts", "measurement_infra"),
           os.path.join(WT, "src"), os.path.join(WT, "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import analyze_tiletie as AT      # noqa: E402
import analyze_tiearb as TA       # noqa: E402
import analyze_tiearb2 as A2      # noqa: E402

# --- constants, verbatim from analyze_widening.py -------------------------- #
PARITY_BASE = A2.PARITY_BASE        # == 1
RND_SEED = 20260819
E_LEVELS = (64, 16)
B_LADDER_PUBLISHED = (1, 2, 4, 8, 16, 32, 64)
BOOT_REPS = 2000
BOOT_SEED = 20260819
SALT = "tiletie-v1"

CHUNKS = os.path.join(WT, "measurement/tiearb_widening_20260817/chunks/s1")
#: ⚠️ The share mount path differs by box: /mnt/c/carc-shared locally,
#: /mnt/carc-shared inside an ssh to the laptop. CARC_SHARE_ROOT overrides.
SHARE_ROOT = os.environ.get("CARC_SHARE_ROOT", "/mnt/c/carc-shared")
SHARE = os.path.join(SHARE_ROOT, "tiearb_widening_20260817/chunks/s1")
BANKED_ROWS = os.path.join(
    WT, "measurement/tiearb_widening_20260817/shared_run_r4/verdicts/per_position_s1.jsonl")


def f64bits(x) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _sym(xs):
    """analyze_widening._sym, verbatim."""
    return (xs[0] + xs[1]) / 2.0


def _sub_rows(matrix, idxs):
    return [matrix[i] for i in idxs]


# --------------------------------------------------------------------------- #
# loading                                                                       #
# --------------------------------------------------------------------------- #
def load_arms() -> dict:
    arms = {}
    for f in sorted(glob.glob(os.path.join(CHUNKS, "chunk*/ARMS.json"))):
        for rid, meta in json.load(open(f)).items():
            prev = arms.get(rid)
            if prev is not None and prev != meta:
                raise SystemExit(f"ARMS.json conflict for {rid}")
            arms[rid] = meta
    return arms


def load_positions() -> dict:
    """(leg, rid) -> position row (deck_seed, actions, ply, pick_a, pick_b, ...)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(CHUNKS, "chunk*/positions_walled_leg*.jsonl"))):
        leg = int(os.path.basename(f).split("leg")[1].split(".")[0])
        for line in open(f):
            if line.strip():
                d = json.loads(line)
                out[(leg, d["rid"])] = d
    return out


def load_records(judge: str) -> dict:
    """rid -> {leg: record}. `judge` in {'tier1-greedy', 'clair-puct'}."""
    by_rid = defaultdict(dict)
    pat = os.path.join(SHARE, f"chunk*/{judge}/walled/leg*/records/*.json")
    for f in glob.glob(pat):
        leg = int(f.split("/walled/leg")[1].split("/")[0])
        d = json.load(open(f))
        rid = d["rid"]
        if leg in by_rid[rid]:
            raise SystemExit(f"duplicate record {judge} leg{leg} {rid}")
        by_rid[rid][leg] = d
    return dict(by_rid)


def load_banked_rows() -> dict:
    return {json.loads(l)["rid"]: json.loads(l)
            for l in open(BANKED_ROWS) if l.strip()}


# --------------------------------------------------------------------------- #
# per-position assembly — mirrors analyze_widening.build_rows                    #
# --------------------------------------------------------------------------- #
def assemble(arms_index, if_by_rid, arb_by_rid, ext_by_rid=None):
    """Yield per-rid assembled position dicts.

    `ext_by_rid`, if given, is {rid: {leg: {'values_a': [...], 'values_b': [...]}}}
    carrying the NEW worlds; each banked value list is EXTENDED (never replaced)
    by concatenation, which is PREREG G-ID-5.
    """
    out, counts = {}, defaultdict(int)
    for rid, meta in sorted(arms_index.items()):
        counts["planned"] += 1
        arms = meta["arms"]
        n_arms = len(arms)
        need = list(range(1, n_arms))
        if_legs = if_by_rid.get(rid, {})
        arb_legs = arb_by_rid.get(rid, {})
        have_if = sorted(k for k in if_legs if k in need)
        have_arb = sorted(k for k in arb_legs if k in need)
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
        unusable = [1 for legs in (if_legs, arb_legs) for r in have_if
                    if (legs.get(r) or {}).get("ok") is False
                    or (legs.get(r) or {}).get("values_a") is None
                    or (legs.get(r) or {}).get("values_b") is None]
        if unusable:
            counts["failed_rid"] += 1
            continue

        mats = {}
        for jname, legs in (("if", if_legs), ("arb", arb_legs)):
            ref = legs[have_if[0]]
            va0 = list(ref["values_a"])
            rows = [va0] + [list(legs[r]["values_b"]) for r in have_if]
            if jname == "arb" and ext_by_rid is not None:
                ex = ext_by_rid[rid]
                rows[0] = rows[0] + list(ex[have_if[0]]["values_a"])
                for i, r in enumerate(have_if, start=1):
                    rows[i] = rows[i] + list(ex[r]["values_b"])
            mats[jname] = rows

        subset = meta.get("subset_j4")
        if not subset:
            counts["j4_absent"] += 1
            continue
        sub_set = set(subset)
        j4_idx = [p for p, ai in enumerate(arm_order) if arms[ai] in sub_set]
        if champ_pos not in j4_idx:
            j4_idx = sorted(j4_idx + [champ_pos])
        champ_pos_j4 = j4_idx.index(champ_pos)

        out[rid] = {
            "rid": rid, "meta": meta, "arm_order": arm_order,
            "champ_pos": champ_pos, "j4_idx": j4_idx,
            "champ_pos_j4": champ_pos_j4, "have_legs": have_if,
            "matrix_if": mats["if"], "matrix_arb": mats["arb"],
        }
        counts["analysed"] += 1
    return out, dict(counts)


def ladder_row(pos, b_ladder, e_levels=E_LEVELS, parity_base=PARITY_BASE,
               rnd_seed=RND_SEED, m_arb=None):
    """Every §5 ladder statistic for one position, published primitives only.

    `m_arb` (default len(matrix_arb[0])) is the world count the PARITY SPLIT is
    taken over. `matrix_if` may be SHORTER than `m_arb`: the ladder only ever
    indexes `sorted(eva)[:E]`, and that set is a subset of {0..127} at every
    m_arb in {128, 256, 512} (PREREG §1). Asserted, never assumed.
    """
    matrix_if, matrix_arb = pos["matrix_if"], pos["matrix_arb"]
    champ_pos, champ_pos_j4 = pos["champ_pos"], pos["champ_pos_j4"]
    mif_j4 = _sub_rows(matrix_if, pos["j4_idx"])
    marb_j4 = _sub_rows(matrix_arb, pos["j4_idx"])
    m = int(m_arb if m_arb is not None else len(matrix_arb[0]))
    m_if = len(matrix_if[0])
    for r in matrix_arb:
        if len(r) != m:
            raise SystemExit(f"{pos['rid']}: ragged arb matrix ({len(r)} != {m})")
    for r in matrix_if:
        if len(r) != m_if:
            raise SystemExit(f"{pos['rid']}: ragged if matrix")

    a_rnd = TA.rnd_arm_position(pos["rid"], len(pos["arm_order"]), rnd_seed)
    acc = defaultdict(list)
    for swap in (False, True):
        sel, eva = AT.parity_indices(m, base=parity_base, swap=swap)
        sel_sorted, eva_sorted = sorted(sel), sorted(eva)
        for e in e_levels:
            eva_e = eva_sorted[:e]
            if eva_e and max(eva_e) >= m_if:
                raise SystemExit(
                    f"{pos['rid']}: eva index {max(eva_e)} exceeds the banked "
                    f"oracle world count {m_if} — PREREG §1.1 violated")
            acc[f"ora_full_E{e}"].append(
                AT.crossfit_regret(matrix_if, sel, eva_e, champ_pos)[0]
                if max(sel) < m_if else float("nan"))
            acc[f"ora_j4_E{e}"].append(
                AT.crossfit_regret(mif_j4, sel, eva_e, champ_pos_j4)[0]
                if max(sel) < m_if else float("nan"))
            acc[f"rnd_E{e}"].append(
                AT._sub_mean(matrix_if[a_rnd], eva_e)
                - AT._sub_mean(matrix_if[champ_pos], eva_e))
            for b in b_ladder:
                if b > len(sel_sorted):
                    continue
                acc[f"arb_full_E{e}_B{b}"].append(
                    A2.arb_at_budget(matrix_arb, matrix_if, sel, eva_e,
                                     champ_pos, b)[0])
                acc[f"arb_j4_E{e}_B{b}"].append(
                    A2.arb_at_budget(marb_j4, mif_j4, sel, eva_e,
                                     champ_pos_j4, b)[0])
    meta = pos["meta"]
    row = {"rid": pos["rid"], "root_id": meta["root_id"],
           "ply": meta.get("ply"), "phase_bucket": meta.get("phase_bucket"),
           "stratum": meta.get("stratum"), "rules_profile": meta.get("rules_profile"),
           "capped_at_4": bool(meta.get("capped_at_4")),
           "champ_pos": pos["champ_pos"], "arm_order": pos["arm_order"],
           "n_arms_j4": len(pos["j4_idx"]), "m": m, "m_if": m_if}
    for k, v in acc.items():
        if len(v) == 2:
            row[k] = _sym(v)
    return row


def shifted_seed_fns(j0: int, salt: str = SALT):
    """(world_seeds_shifted, playout_seed_shifted) covering worlds [j0, j0+m).

    Both delegate to `oracle_score_pilot`'s own functions at the SHIFTED index,
    so the emitted seeds are exactly `world_seeds(rid, j0+m, salt)[j0:j0+m]`.
    """
    from oracle_score_pilot import playout_seed, world_seed

    def world_seeds_shifted(rid, m, s):
        return [world_seed(rid, j0 + j, s) for j in range(int(m))]

    def playout_seed_shifted(rid, j, s):
        return playout_seed(rid, j0 + int(j), s)

    return world_seeds_shifted, playout_seed_shifted
